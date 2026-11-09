"""F-1 regression: فرض شاهد الحذف (tombstone) على **كل** مسارات الوصول للشات.

العيب F-1 (من التدقيق الشامل): القوائم والتصدير كانوا بيحترموا `is_deleted`، لكن
مسارات القراءة/التفاعل التانية (`detail`/`status`/`cost`/`reply`/`files`/`file` في
الـ Mini App، و`open_conversation` وغيره في البوت) كانوا بيوصلوا لبيانات OpenHands
رغم وجود شاهد حذف محلي. الاختبارات دي بتثبت الفرض الموحّد:

- كل مسار قراءة/تفاعل يرفض الشات المتشاهد **قبل** أي نداء بعيد (صفر نداءات).
- الرد آمن: «مش موجود» (404) في الـ Mini App، ورسالة عربية آمنة في البوت — من غير
  أي محتوى/عنوان/تكلفة/حالة.
- الحالات الثلاثة مغطّاة: `deleted` (محلي/مؤكّد)، `deleting`، `uncertain`.
- الشات غير المحذوف لسه شغّال (مفيش كسر للسلوك العادي).
- شات تاني (غير متشاهد) مش متأثّر.
- فحص الملكية لسه سارٍ (403 لمالك تاني).
- إعادة التفاعل الصريح (`watch`) وإعادة محاولة الحذف لسه شغّالين على شات متشاهد.

الاختبارات بتضرب المسار الحقيقي (Starlette route + معالج البوت) مش الدالة المساعدة بس.
مفيش أي نداء شبكة/تيليجرام/OpenHands حقيقي.
"""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from starlette.testclient import TestClient

import bot.handlers as h
from bot import outbox
from bot.config import Config
from bot.db import INBOX_KIND_TERMINAL, Database
from bot.openhands_client import OpenHandsClient
from bot.watcher import Watcher
from bot.web import build_web_app
from tests._miniapp_helpers import BOT_TOKEN, make_init_data
from tests.test_handlers import FakeMessage, _cb_update, _ctx_with
from tests.test_b06_file_routing import _seed_files

OWNER = 555
OTHER = 999
OWNER_UUID = "owner-uuid-123"
CID = "c1"
CID2 = "c2"
ORIGIN = "https://app.test"

# محتوى حسّاس لازم **مايظهرش أبدًا** في أي رد لشات متشاهد.
SECRET_TITLE = "TOP_SECRET_TITLE"
SECRET_REPLY = "TOP_SECRET_REPLY"
SECRET_FILE = "TOP_SECRET_FILE"
SECRET_ZIP = b"PK\x03\x04TOP_SECRET_ZIP"
SAFE_BOT_MESSAGE = "الشات مش موجود."
SAFE_BOT_FILE_MESSAGE = "الشات أو الملف مش موجود."


# ============================================================ Mini App scaffolding
class _Body(httpx.AsyncByteStream):
    def __init__(self, data: bytes):
        self._data = data

    async def __aiter__(self):
        yield self._data


class MockAPI:
    """معالج MockTransport قابل للضبط + عدّادات لكل نقطة محمية (إثبات صفر نداءات)."""

    def __init__(self):
        self.owner_uuid = OWNER_UUID
        self.conv_owner = OWNER_UUID
        self.convs_present = True
        self.convs_calls = 0
        self.events_calls = 0
        self.files_calls = 0
        self.file_calls = 0
        self.export_calls = 0
        self.delete_calls = 0

    @property
    def protected_calls(self) -> int:
        """إجمالي النداءات البعيدة المحمية (تفويض/قراءة محتوى) — لازم 0 بعد الرفض."""
        return (
            self.convs_calls
            + self.events_calls
            + self.files_calls
            + self.file_calls
            + self.export_calls
        )

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        method = request.method
        if path == "/api/v1/users/me":
            if self.owner_uuid is None:
                return httpx.Response(200, json={})
            return httpx.Response(200, json={"id": self.owner_uuid, "role": "owner"})
        if path == "/api/v1/app-conversations" and method == "GET":
            self.convs_calls += 1
            if not self.convs_present:
                return httpx.Response(200, json=[])
            ids = request.url.params.get_list("ids") or [CID]
            out = []
            for cid in ids:
                conv = {"id": cid, "title": SECRET_TITLE, "execution_status": "running"}
                if self.conv_owner is not None:
                    conv["created_by_user_id"] = self.conv_owner
                out.append(conv)
            return httpx.Response(200, json=out)
        if path.endswith("/events/search"):
            self.events_calls += 1
            kind = request.url.params.get("kind__eq")
            if kind == "MessageEvent":
                return httpx.Response(
                    200,
                    json={
                        "items": [
                            {
                                "kind": "MessageEvent",
                                "source": "agent",
                                "timestamp": "2026-01-01T00:00:02Z",
                                "llm_message": {"content": [{"type": "text", "text": SECRET_REPLY}]},
                            }
                        ]
                    },
                )
            return httpx.Response(200, json={"items": []})
        if path.endswith("/files"):
            self.files_calls += 1
            return httpx.Response(200, json=["a/b/main.py"])
        if path.endswith("/file"):
            self.file_calls += 1
            return httpx.Response(200, stream=_Body(json.dumps(SECRET_FILE).encode()))
        if path.endswith("/download"):
            self.export_calls += 1
            return httpx.Response(200, stream=_Body(SECRET_ZIP))
        if method == "DELETE" and "/app-conversations/" in path:
            self.delete_calls += 1
            return httpx.Response(200, json={"success": True})
        return httpx.Response(404, json={"detail": "no"})


def make_config(**over) -> Config:
    base = dict(
        telegram_bot_token=BOT_TOKEN,
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({OWNER}),
        owner_id=OWNER,
        mini_app_cookie_secure=False,
        mini_app_allowed_origins=frozenset({ORIGIN}),
    )
    base.update(over)
    return Config(**base)


def make_client(api: MockAPI, db=None) -> TestClient:
    client = OpenHandsClient(
        "https://example.test", "key", transport=httpx.MockTransport(api.handler)
    )
    return TestClient(
        build_web_app(make_config(), db, client=client), raise_server_exceptions=False
    )


def login(tc: TestClient) -> None:
    assert tc.post("/api/v1/auth", json={"initData": make_init_data(OWNER)}).status_code == 200


# مسارات الـ Mini App اللي بتوصل لبيانات محمية (F-1).
READ_ROUTES = [
    ("detail", lambda cid: f"/api/v1/conversations/{cid}", {}),
    ("status", lambda cid: f"/api/v1/conversations/{cid}/status", {}),
    ("cost", lambda cid: f"/api/v1/conversations/{cid}/cost", {}),
    ("reply", lambda cid: f"/api/v1/conversations/{cid}/reply", {}),
    ("files", lambda cid: f"/api/v1/conversations/{cid}/files", {}),
    ("file", lambda cid: f"/api/v1/conversations/{cid}/file", {"path": "a/b/main.py"}),
    ("export", lambda cid: f"/api/v1/conversations/{cid}/export", {}),
]
ROUTE_IDS = [r[0] for r in READ_ROUTES]


def _seed_tombstone(db: Database, state: str) -> None:
    """يزرع شاهد حذف بالحالة المطلوبة: deleted / deleting / uncertain / legacy."""
    now = outbox.now_iso()
    if state == "deleted":
        db.delete_conversation(CID, now, remote_confirmed=True)
    elif state == "deleting":
        assert db.begin_remote_deletion(CID, now) is not None
    elif state == "uncertain":
        assert db.begin_remote_deletion(CID, now) is not None
        db.set_remote_deletion_state(CID, db.REMOTE_UNCERTAIN, now)
    elif state == "legacy":
        db.delete_conversation(CID, now)  # حذف محلي بلا نداء بعيد ⇒ remote_state=NULL
    else:  # pragma: no cover
        raise AssertionError(state)
    assert db.is_deleted(CID) is True


TOMBSTONE_STATES = ["deleted", "deleting", "uncertain", "legacy"]


# ============================================================ Mini App: enforcement
@pytest.mark.parametrize("state", TOMBSTONE_STATES)
@pytest.mark.parametrize("name, path_fn, params", READ_ROUTES, ids=ROUTE_IDS)
def test_miniapp_read_route_blocked_when_tombstoned(name, path_fn, params, state, tmp_path):
    """كل مسار قراءة يرفض الشات المتشاهد بـ 404 آمن، من غير أي نداء بعيد."""
    api = MockAPI()
    db = Database(str(tmp_path / f"{name}-{state}.sqlite3"))
    _seed_tombstone(db, state)
    tc = make_client(api, db=db)
    login(tc)
    r = tc.get(path_fn(CID), params=params)
    assert r.status_code == 404, (name, state, r.status_code, r.text)
    assert r.json().get("error") == "not_found", (name, state, r.text)
    assert api.protected_calls == 0, (name, state, "نداء بعيد بعد الرفض")
    # مفيش أي محتوى حسّاس اتكشف.
    body = r.text
    assert SECRET_TITLE not in body and SECRET_REPLY not in body and SECRET_FILE not in body


@pytest.mark.parametrize("name, path_fn, params", READ_ROUTES, ids=ROUTE_IDS)
def test_miniapp_read_route_ok_when_not_deleted(name, path_fn, params):
    """تحكّم موجب: من غير شاهد، كل مسار قراءة شغّال عادي (مفيش كسر للسلوك)."""
    api = MockAPI()
    tc = make_client(api, db=Database(":memory:"))
    login(tc)
    r = tc.get(path_fn(CID), params=params)
    assert r.status_code == 200, (name, r.status_code, r.text)
    assert api.protected_calls >= 1  # المسار العادي بيوصل فعلًا للمصدر


def test_miniapp_unrelated_conversation_unaffected_by_tombstone(tmp_path):
    """شاهد على شات مايأثّرش على شات تاني (مفيش حجب عرضي)."""
    api = MockAPI()
    db = Database(str(tmp_path / "unrelated.sqlite3"))
    db.delete_conversation(CID, outbox.now_iso(), remote_confirmed=True)
    tc = make_client(api, db=db)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID2}")
    assert r.status_code == 200 and api.convs_calls == 1
    r2 = tc.get(f"/api/v1/conversations/{CID}")
    assert r2.status_code == 404


def test_miniapp_ownership_still_enforced_when_not_deleted():
    """من غير شاهد: مالك تاني ⇒ 403 (فحص الملكية لسه سارٍ — الفرض ما ضعفش التفويض)."""
    api = MockAPI()
    api.conv_owner = "someone-else"
    tc = make_client(api, db=Database(":memory:"))
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/status")
    assert r.status_code == 403 and r.json()["error"] == "unauthorized"


def test_miniapp_tombstone_wins_over_ownership_no_remote_call(tmp_path):
    """شات متشاهد + مالك مختلف ⇒ 404 (الشاهد أولًا) و**صفر** نداء بعيد."""
    api = MockAPI()
    api.conv_owner = "someone-else"
    db = Database(str(tmp_path / "owner-vs-tomb.sqlite3"))
    db.delete_conversation(CID, outbox.now_iso(), remote_confirmed=True)
    tc = make_client(api, db=db)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}")
    assert r.status_code == 404
    assert api.protected_calls == 0


def test_miniapp_tombstone_check_fails_closed_on_db_error(tmp_path, monkeypatch):
    """قاعدة غير متاحة أثناء فحص الشاهد ⇒ 404 (فشل مغلق)، مفيش أي نداء بعيد."""
    api = MockAPI()
    db = Database(str(tmp_path / "failclosed.sqlite3"))

    def boom(*_a, **_k):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(db, "is_deleted", boom)
    tc = make_client(api, db=db)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/files")
    assert r.status_code == 404 and r.json()["error"] == "not_found"
    assert api.protected_calls == 0


def test_miniapp_export_remains_protected(tmp_path):
    """التصدير لسه محمي (سلوك قائم ما اترجعش للخلف)."""
    api = MockAPI()
    db = Database(str(tmp_path / "export.sqlite3"))
    db.delete_conversation(CID, outbox.now_iso(), remote_confirmed=True)
    tc = make_client(api, db=db)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/export")
    assert r.status_code == 404 and r.json()["error"] == "not_found"
    assert api.export_calls == 0


# ---------------------------------------- Mini App: lifecycle ops still allowed
def test_miniapp_watch_on_tombstoned_reengages(tmp_path):
    """زر «متابعة» (إعادة تفاعل صريح) لسه شغّال على شات متشاهد ويشيل الشاهد."""
    api = MockAPI()
    db = Database(str(tmp_path / "watch.sqlite3"))
    db.delete_conversation(CID, outbox.now_iso(), remote_confirmed=True)
    tc = make_client(api, db=db)
    login(tc)
    r = tc.post(
        f"/api/v1/conversations/{CID}/watch", headers={"origin": ORIGIN}, json={}
    )
    assert r.status_code == 200 and r.json()["watched"] is True
    assert api.convs_calls >= 1  # الـ watch بيقرا ميتاداتا الشات فعلًا (مش حجب)
    assert db.is_deleted(CID) is False  # الشاهد اتشال (إعادة تفاعل صريح)
    assert db.get_watched(CID) is not None


def test_miniapp_delete_retry_on_tombstoned_reaches_remote(tmp_path):
    """إعادة محاولة الحذف على شات متشاهد لسه بتبلغ OpenHands (مفيش حجب للحذف)."""
    api = MockAPI()
    db = Database(str(tmp_path / "delretry.sqlite3"))
    # شات بحالة 'uncertain' (شاهد قائم) ⇒ الحذف لازم يفضل ممكن.
    _seed_tombstone(db, "uncertain")
    tc = make_client(api, db=db)
    login(tc)
    r = tc.delete(f"/api/v1/conversations/{CID}", headers={"origin": ORIGIN})
    assert r.status_code == 200 and r.json()["deleted"] is True
    assert api.delete_calls == 1  # نداء الحذف البعيد حصل فعلًا


# ============================================================ Bot scaffolding
class CountingClient:
    """عميل بيعدّ كل نداء بعيد. الشات المتشاهد لازم يرجّع **صفر** نداءات."""

    def __init__(self):
        self.calls: list[tuple] = []

    async def get_conversations(self, ids):
        self.calls.append(("get_conversations", tuple(ids)))
        return [{"id": ids[0], "title": SECRET_TITLE, "created_by_user_id": OWNER_UUID}]

    async def get_current_user(self):
        self.calls.append(("get_current_user",))
        return {"id": OWNER_UUID}

    async def get_last_exchange(self, cid):
        self.calls.append(("get_last_exchange", cid))
        return ("TOP_SECRET_PROMPT", SECRET_REPLY)

    async def list_files(self, cid, path=""):
        self.calls.append(("list_files", cid))
        return ["a/b/main.py"]

    async def read_file_text_bounded(self, cid, p, max_response_bytes=None):
        self.calls.append(("read_file_text_bounded", cid, p))
        return SECRET_FILE

    async def export_conversation(self, cid):
        self.calls.append(("export_conversation", cid))
        return SECRET_ZIP

    async def send_message(self, cid, text):
        self.calls.append(("send_message", cid, text))

    async def delete_conversation(self, cid):
        self.calls.append(("delete_conversation", cid))
        return True


# (اسم المعالج، callback_data، مكان ظهور الرد المتوقّع، الرسالة الآمنة المتوقّعة)
BOT_READ_HANDLERS = [
    ("open", "open:c1", "edit", SAFE_BOT_MESSAGE),
    ("status", "status:c1", "edit", SAFE_BOT_MESSAGE),
    ("cost", "cost:c1", "edit", SAFE_BOT_MESSAGE),
    ("reply", "reply:c1", "edit", SAFE_BOT_MESSAGE),
    ("copy", "copy:c1", "sent", SAFE_BOT_MESSAGE),
    ("full", "full:c1", "sent", SAFE_BOT_MESSAGE),
    ("export", "export:c1", "edit", SAFE_BOT_MESSAGE),
    ("files", "files:c1:0:0", "edit", SAFE_BOT_FILE_MESSAGE),
    ("file", "file:c1:0:0", "edit", SAFE_BOT_FILE_MESSAGE),
]
BOT_HANDLER_IDS = [x[0] for x in BOT_READ_HANDLERS]

# المعالجات اللي بترد بمستند عند النجاح (تصدير/معاينة ملف): تحقّق النجاح بوجود مستند.
BOT_DOC_HANDLERS = {"export", "file"}

_HANDLER_FUNCS = {
    "open": h.open_conversation,
    "status": h.show_status,
    "cost": h.show_cost,
    "reply": h.reply_prompt,
    "copy": h.copy_reply,
    "full": h.full_reply,
    "export": h.export_conversation,
    "files": h.list_files,
    "file": h.show_file,
}


def _bot_outputs(update, where: str, ctx) -> list[str]:
    if where == "edit":
        return list(update.callback_query.edits)
    if where == "sent":
        return list(ctx.bot.sent)
    # 'doc': مستندات مُرسَلة (تصدير/معاينة ملف) — بنرجّع عددها كنص للتحقّق من وجود رد.
    return [f"doc:{len(ctx.bot.documents)}"] if ctx.bot.documents else []


@pytest.mark.parametrize("state", TOMBSTONE_STATES)
@pytest.mark.parametrize(
    "name, data, where, safe", BOT_READ_HANDLERS, ids=BOT_HANDLER_IDS
)
def test_bot_handler_blocked_when_tombstoned(name, data, where, safe, state, tmp_path):
    """كل معالج قراءة/تفاعل في البوت يرفض الشات المتشاهد من غير أي نداء بعيد."""
    client = CountingClient()
    ctx = _ctx_with(tmp_path, client)
    db = ctx.bot_data["db"]
    _seed_tombstone(db, state)
    # show_file لازم قايمة ملفات مُخزّنة مسبقًا عشان يوصل لمرحلة التفويض (مش «ملف مش موجود»).
    if name == "file":
        gen = _seed_files(ctx, ["a/b/main.py"])
        data = f"file:c1:{gen}:0"
    update = _cb_update(1, data)
    asyncio.run(_HANDLER_FUNCS[name](update, ctx))

    outputs = _bot_outputs(update, where, ctx)
    assert outputs, (name, state, "مفيش رد للمستخدم")
    assert any(safe in out for out in outputs), (name, state, outputs)
    assert ctx.bot.documents == [], (name, state, "مستند اتسلّم لشات متشاهد")
    assert client.calls == [], (name, state, "نداء بعيد بعد رفض الشات المتشاهد", client.calls)
    # مفيش أي محتوى حسّاس اتكشف.
    joined = "\n".join(outputs)
    assert SECRET_TITLE not in joined and SECRET_REPLY not in joined and SECRET_FILE not in joined
    # مفيش توجيه برومت اتعمل.
    assert db.get_awaiting(1) == (None, None)


@pytest.mark.parametrize(
    "name, data, where, safe", BOT_READ_HANDLERS, ids=BOT_HANDLER_IDS
)
def test_bot_handler_ok_when_not_deleted(name, data, where, safe, tmp_path):
    """تحكّم موجب: من غير شاهد، المعالجات شغّالة عادي (بتوصل للمصدر فعلًا)."""
    client = CountingClient()
    ctx = _ctx_with(tmp_path, client)
    if name == "file":
        gen = _seed_files(ctx, ["a/b/main.py"])
        data = f"file:c1:{gen}:0"
    update = _cb_update(1, data)
    asyncio.run(_HANDLER_FUNCS[name](update, ctx))
    if name in BOT_DOC_HANDLERS:
        assert ctx.bot.documents, (name, "المسار العادي ما بعتش مستند")
    else:
        outputs = _bot_outputs(update, where, ctx)
        assert outputs, (name, "مفيش رد")
    assert client.calls, (name, "المسار العادي ماوصلش للمصدر")


def test_bot_ownership_still_enforced_when_not_deleted(tmp_path):
    """من غير شاهد: مالك مختلف ⇒ رسالة «مش مسموح» (الملكية لسه سارية)."""
    from tests.test_b06_file_routing import FileFlowClient

    client = FileFlowClient(conv_owner="someone-else")
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "open:c1")
    asyncio.run(h.open_conversation(update, ctx))
    assert "مش مسموح" in update.callback_query.edits[-1]


def test_bot_open_rejects_tombstoned_without_remote_call(tmp_path):
    """المسار السابع المحدّد: `handlers.open_conversation` يرفض المتشاهد بلا نداء بعيد."""
    client = CountingClient()
    ctx = _ctx_with(tmp_path, client)
    db = ctx.bot_data["db"]
    db.delete_conversation(CID, outbox.now_iso(), remote_confirmed=True)
    update = _cb_update(1, "open:c1")
    asyncio.run(h.open_conversation(update, ctx))
    assert update.callback_query.edits[-1] == SAFE_BOT_MESSAGE
    assert client.calls == []
    # مفيش توجيه رسايل اتفتح على شات محذوف.
    assert db.get_awaiting(1) == (None, None)


def test_bot_send_prompt_blocked_for_tombstoned(tmp_path):
    """إرسال نص على شات متشاهد (بعد فتح التوجيه) ⇒ مرفوض، مفيش صف صندوق، مفيش إحياء.

    السباق الحقيقي: المستخدم فتح توجيه برومت (`awaiting`) على شات، وبعدين الشات اتحذف
    **محليًا** (شاهد محلي). الحالتان 'deleting'/'uncertain' **بتحافظ** على `awaiting`
    (أما الحذف المؤكّد/`delete_conversation` فبيشيله ذرّيًا، فمفيش سباق من المسار ده)،
    فبالتالي النص المتأخّر بيوصل لـ `_send_prompt`. قبل F-1 ده كان بيحيي الشات (لأن مسار
    البوت بينادي `reengage=True`). دلوقتي مرفوض قبل أي كتابة.
    """
    for state in ("deleting", "uncertain"):
        client = CountingClient()
        sub = tmp_path / state
        sub.mkdir()
        ctx = _ctx_with(sub, client)
        db = ctx.bot_data["db"]
        db.set_awaiting(1, CID, "reply")
        _seed_tombstone(db, state)
        assert db.get_awaiting(1) == (CID, "reply"), state  # التوجيه لسه قائم (سباق)
        update = _cb_update(1, "x")
        update.message = FakeMessage()
        update.message.text = "برومت متأخّر"
        asyncio.run(h.handle_text(update, ctx))
        assert db.count_outbox() == 0, state  # مفيش برومت اتسجّل
        assert db.is_deleted(CID) is True, state  # الشاهد ما اتشالش (مفيش إحياء)
        assert client.calls == [], state
        assert any("اتحذف" in r for r in update.message.replies), (state, update.message.replies)


def test_bot_send_prompt_fails_closed_on_db_error(tmp_path, monkeypatch):
    """SW-01: قاعدة غير متاحة أثناء فحص الشاهد ⇒ الاستثناء **بيطلع** (مفيش رسالة حذف كاذبة).

    السلوك الصحيح: فشل قراءة الشاهد **مش** دليل على إن الشات متشاهد. بنرفع الاستثناء
    (فشل مقفول صريح) بدل ما نحوّله لـ `deleted=True` ونبعت رسالة حذف مضلّلة ونرجع عاديًّا.
    """
    client = CountingClient()
    ctx = _ctx_with(tmp_path, client)
    db = ctx.bot_data["db"]
    db.set_awaiting(1, CID, "reply")

    def boom(*_a, **_k):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(db, "is_deleted", boom)
    update = _cb_update(1, "x")
    update.message = FakeMessage()
    update.message.text = "برومت"
    with pytest.raises(RuntimeError):
        asyncio.run(h.handle_text(update, ctx))
    assert db.count_outbox() == 0  # مفيش برومت اتسجّل
    assert client.calls == []  # مفيش أي نداء بعيد
    assert not any("اتحذف" in r for r in update.message.replies)  # مفيش رسالة حذف كاذبة
    assert db.get_awaiting(1) == (CID, "reply")  # التوجيه ما اتستهلكش (لا فقد)


def test_bot_watch_on_tombstoned_still_reengages(tmp_path):
    """زر «متابعة» في البوت لسه إعادة تفاعل صريح على شات متشاهد (ما اتكسرش)."""
    from tests.test_b06_file_routing import FileFlowClient

    client = FileFlowClient()
    ctx = _ctx_with(tmp_path, client)
    db = ctx.bot_data["db"]
    db.delete_conversation(CID, outbox.now_iso(), remote_confirmed=True)
    update = _cb_update(1, "watch:c1")
    asyncio.run(h.watch_conversation(update, ctx))
    assert client.list_calls == 0  # الـ watch مابيقراش ملفات
    assert db.is_deleted(CID) is False  # الشاهد اتشال
    assert db.get_watched(CID) is not None


def test_bot_delete_retry_on_tombstoned_reaches_remote(tmp_path):
    """إعادة محاولة الحذف في البوت على شات متشاهد لسه بتبلغ OpenHands."""
    client = CountingClient()
    ctx = _ctx_with(tmp_path, client)
    db = ctx.bot_data["db"]
    _seed_tombstone(db, "uncertain")
    update = _cb_update(1, "deleteok:c1")
    asyncio.run(h.delete_conversation_confirm(update, ctx))
    assert ("delete_conversation", CID) in client.calls
    assert db.remote_deletion_state(CID) == db.REMOTE_CONFIRMED


def test_bot_delete_prompt_reachable_on_tombstoned(tmp_path):
    """أول ضغطة 🗑 (`delete:`) على شات متشاهد لسه بتعرض شاشة التأكيد (إعادة محاولة موثّقة).

    الفجوة (MEDIUM من المراجعة المستقلة): `delete_conversation_prompt` ماكانش بياخد
    `allow_deleted=True` (عكس `deleteok:`)، فالحذف الجاري (deleting/uncertain) كان بيتحجب
    عند أول خطوة ⇒ إعادة المحاولة مستحيلة من البوت. الاختبار بيثبت إن شاشة التأكيد بتوصل
    (markup فيه زر التأكيد) وإن التفويض لسه شغّال.
    """
    for state in ("deleting", "uncertain", "deleted"):
        client = CountingClient()
        sub = tmp_path / state
        sub.mkdir()
        ctx = _ctx_with(sub, client)
        db = ctx.bot_data["db"]
        _seed_tombstone(db, state)
        update = _cb_update(1, f"delete:{CID}")
        asyncio.run(h.delete_conversation_prompt(update, ctx))
        assert update.callback_query.edits, (state, "مفيش شاشة تأكيد")
        assert "متأكد" in update.callback_query.edits[-1], (state, update.callback_query.edits)
        assert update.callback_query.edits_markup[-1] is not None, (state, "مفيش زر تأكيد")


def test_bot_delete_prompt_non_owner_still_rejected(tmp_path):
    """الفجوة اتصلحت من غير ما نكسر التفويض: مالك تاني لسه مرفوض عند شاشة التأكيد."""
    from tests.test_b06_file_routing import FileFlowClient

    client = FileFlowClient(conv_owner="someone-else")
    ctx = _ctx_with(tmp_path, client)
    db = ctx.bot_data["db"]
    _seed_tombstone(db, "uncertain")
    update = _cb_update(1, f"delete:{CID}")
    asyncio.run(h.delete_conversation_prompt(update, ctx))
    assert update.callback_query.edits[-1] == "مش مسموح لك بالوصول للشات ده."
    assert update.callback_query.edits_markup[-1] is None


# ============================================================ watcher (HIGH من المراجعة)
class WatcherClient:
    """عميل مراقب بيعدّ النداءات البعيدة (get_conversations/get_last_reply) + عنوان سرّي."""

    def __init__(self):
        self.conv_calls: list[tuple] = []
        self.reply_calls: list[str] = []
        self.title = SECRET_TITLE
        self.reply = SECRET_REPLY

    async def get_conversations(self, ids):
        self.conv_calls.append(tuple(ids))
        return [
            {"id": i, "title": self.title, "execution_status": "finished"} for i in ids
        ]

    async def get_last_reply(self, conversation_id):
        self.reply_calls.append(conversation_id)
        return self.reply


class WatcherBot:
    def __init__(self):
        self.sent: list[str] = []

    async def send_message(self, chat_id=None, text=None, parse_mode=None, **kw):
        self.sent.append(text)

    async def send_document(self, chat_id=None, document=None, **kw):
        self.sent.append("DOC")


@pytest.mark.parametrize("state", TOMBSTONE_STATES)
def test_watcher_skips_tombstoned_no_remote_no_send(state, tmp_path):
    """HIGH من المراجعة: المراقب مايلمسش شات متشاهد — صفر نداء بعيد وصفر إرسال.

    قبل الإصلاح: صف المتابعة بيفضل موجود في deleting/uncertain، فالمراقب كان بيجيب الحالة
    ويبعت «انتهى الشات» بمحتوى الشات المحذوف. بعد الإصلاح: بيتخطّى بالكامل.
    """
    db = Database(str(tmp_path / f"w-{state}.sqlite3"))
    db.add_watched(CID, SECRET_TITLE)
    _seed_tombstone(db, state)
    client = WatcherClient()
    bot = WatcherBot()
    asyncio.run(Watcher(client, db, bot, chat_id=1).tick())
    assert client.conv_calls == [], (state, client.conv_calls)
    assert client.reply_calls == [], (state, client.reply_calls)
    assert bot.sent == [], (state, bot.sent)
    assert SECRET_TITLE not in " ".join(bot.sent)


def test_watcher_fails_closed_on_db_error(tmp_path, monkeypatch):
    """قاعدة غير متاحة أثناء فحص الشاهد ⇒ المراقب يتخطّى (فشل مغلق)، صفر نداء/إرسال."""
    db = Database(str(tmp_path / "w-dberr.sqlite3"))
    db.add_watched(CID, SECRET_TITLE)
    client = WatcherClient()
    bot = WatcherBot()
    w = Watcher(client, db, bot, chat_id=1)

    def boom(*_a, **_k):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(db, "is_deleted", boom)
    asyncio.run(w.tick())
    assert client.conv_calls == []
    assert bot.sent == []


def test_watcher_normal_conversation_still_watched(tmp_path):
    """تحكّم موجب: شات غير محذوف لسه بيتتابع (مفيش كسر للسلوك العادي)."""
    db = Database(str(tmp_path / "w-ok.sqlite3"))
    db.add_watched(CID, "عنوان")
    client = WatcherClient()
    bot = WatcherBot()
    asyncio.run(Watcher(client, db, bot, chat_id=1).tick())
    assert client.conv_calls == [(CID,)]
    assert len(bot.sent) == 1 and "انتهى الشات" in bot.sent[0]


def test_watcher_pending_event_for_tombstoned_not_delivered(tmp_path):
    """حدث صندوق معلّق لشات اتشاهد **بعد** تسجيل الحدث مايتسلّمش (صفر إرسال).

    الاختبار بيُنشئ الحدث والشات **حيّين** الأول (لأن `_insert_inbox` نفسه يرفض الإدراج
    لشات متشاهد)، وبعدين يضع الشاهد ويشغّل دورة. من غير حرس المراقب الحدث كان هيتسلّم
    ويبعت `SECRET_REPLY`؛ بعده بيتخطّى.
    """
    db = Database(str(tmp_path / "w-pending.sqlite3"))
    # حدث معلّق لمحادثة **غير متابَعة** (عشان مسار الاسترجاع ياخده، مش مسار المتابعة النشط).
    iid = db.add_inbox_event(
        CID, SECRET_TITLE, INBOX_KIND_TERMINAL, SECRET_REPLY, outbox.now_iso(), chat_id=1
    )
    assert iid is not None, "الحدث ما اتسجّلش (لازم يتسجّل والشات حيّ)"
    _seed_tombstone(db, "uncertain")
    client = WatcherClient()
    bot = WatcherBot()
    asyncio.run(Watcher(client, db, bot, chat_id=1).tick())
    assert bot.sent == []
    assert client.conv_calls == [] and client.reply_calls == []


# ===================================================== notifier recovery (NEW-1 من المراجعة)
class NotifierSearchClient:
    """عميل بحث فاضي (مفيش محادثات ظاهرة) عشان مسار الاسترجاع يتولّى الحدث المعلّق."""

    def __init__(self):
        self.search_calls: list = []

    async def search_conversations(self, limit=20, page_id=None):
        self.search_calls.append(page_id)
        return {"items": [], "next_page_id": None}


class NotifierBot:
    def __init__(self):
        self.sent: list[str] = []

    async def send_message(self, chat_id=None, text=None, parse_mode=None, **kw):
        self.sent.append(text)

    async def send_document(self, chat_id=None, document=None, **kw):
        self.sent.append("DOC")


def _seed_pending_then_tombstone(db, state):
    """يُسجّل حدثًا استباقيًا **والشات حيّ**، ثم يضع الشاهد (ترتيب واقعي)."""
    from bot.db import INBOX_KIND_PROACTIVE

    iid = db.add_inbox_event(
        CID, SECRET_TITLE, INBOX_KIND_PROACTIVE, SECRET_REPLY, outbox.now_iso(), chat_id=1
    )
    assert iid is not None, "الحدث ما اتسجّلش (لازم يتسجّل والشات حيّ)"
    _seed_tombstone(db, state)
    return iid


@pytest.mark.parametrize("state", ["deleting", "uncertain"])
def test_notifier_recovery_skips_tombstoned(state, tmp_path):
    """NEW-1: المُبلّل مايسترجِعش حدثًا معلّقًا لشات متشاهد — صفر إرسال.

    قبل الإصلاح: صف الحدث بيفضل `pending` في deleting/uncertain، فالمُبلّل كان بيبعته
    (LEAK). بعده: بيتخطّى.
    """
    db = Database(str(tmp_path / f"n-{state}.sqlite3"))
    _seed_pending_then_tombstone(db, state)
    bot = NotifierBot()
    client = NotifierSearchClient()
    from bot.notifier import Notifier

    asyncio.run(Notifier(client, db, bot, chat_id=1, base_url="https://app.test").tick())
    assert bot.sent == [], (state, bot.sent)
    assert SECRET_REPLY not in " ".join(bot.sent)


def test_notifier_recovery_normal_event_still_delivered(tmp_path):
    """تحكّم موجب: حدث معلّق لشات **غير محذوف** لسه بيتسلّم (مفيش كسر للسلوك)."""
    from bot.db import INBOX_KIND_PROACTIVE
    from bot.notifier import Notifier

    db = Database(str(tmp_path / "n-ok.sqlite3"))
    db.add_inbox_event(
        CID, "عنوان", INBOX_KIND_PROACTIVE, "رسالة إشعار", outbox.now_iso(), chat_id=1
    )
    bot = NotifierBot()
    client = NotifierSearchClient()
    asyncio.run(Notifier(client, db, bot, chat_id=1, base_url="https://app.test").tick())
    assert len(bot.sent) == 1 and "رسالة إشعار" in bot.sent[0]


def test_notifier_recovery_fails_closed_on_db_error(tmp_path, monkeypatch):
    """قاعدة غير متاحة أثناء فحص الشاهد ⇒ المُبلّل يتخطّى (فشل مغلق)، صفر إرسال."""
    from bot.db import INBOX_KIND_PROACTIVE
    from bot.notifier import Notifier

    db = Database(str(tmp_path / "n-dberr.sqlite3"))
    db.add_inbox_event(
        CID, "عنوان", INBOX_KIND_PROACTIVE, SECRET_REPLY, outbox.now_iso(), chat_id=1
    )

    def boom(*_a, **_k):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(db, "is_deleted", boom)
    bot = NotifierBot()
    client = NotifierSearchClient()
    asyncio.run(Notifier(client, db, bot, chat_id=1, base_url="https://app.test").tick())
    assert bot.sent == []
