"""OHB2-C7: حذف الشات محليًا (بوت + Mini App) — أمان/اتساق/تكافؤ.

بيغطّي الـ 15 بند المطلوبين:
1) المالك يقدر يحذف شاته. 2) مالك تاني مايقدرش. 3) غير مصادَق مرفوض. 4) معرّف غير صالح
آمن. 5) التأكيد مطلوب في الواجهتين. 6) الحذف المتكرّر idempotent. 7) تزامن الحذف مع
إكمال الـ worker ما يفسدش الحالة. 8) الأعمال المعلّقة ما تعيدش إنشاء شات محذوف.
9) عامل الإكمال ما يسلّمش إشعار قديم بعد الحذف. 10) التعافي بعد restart يحافظ على الحذف.
11) مفيش حذف بعيد لـ OpenHands. 12) تكافؤ البوت والـ Mini App. 13) إنشاء شات مستقل لسه
شغال. 14) ربط المستودع لسه شغال. 15) سلوك unwatch ما اتغيّرش.

كله بعملاء وهميين وقواعد معزولة — مفيش أي اتصال بتليجرام/OpenHands/GitHub.
"""
from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace

import httpx
from starlette.testclient import TestClient

import bot.handlers as h
from bot import outbox
from bot.config import Config
from bot.db import Database
from bot.openhands_client import OpenHandsClient
from bot.web import build_web_app
from tests._miniapp_helpers import BOT_TOKEN, make_init_data

OWNER = 555
OTHER = 999
ORIGIN = "https://app.test"
OWNER_UUID = "owner-uuid-123"
CID = "c1"


def _db(tmp_path) -> Database:
    return Database(os.path.join(str(tmp_path), "del.sqlite3"))


# ============================================================ Mini App side
class _Body(httpx.AsyncByteStream):
    def __init__(self, data: bytes):
        self._data = data

    async def __aiter__(self):
        yield self._data


class MockAPI:
    """MockTransport: هوية المالك + شات واحد + عدّادات لمسارات الحذف البعيد (لازم تفضل 0)."""

    def __init__(self):
        self.owner_uuid = OWNER_UUID
        self.conv_owner = OWNER_UUID
        self.convs_present = True
        self.deleted_remote_calls = 0  # أي نداء حذف بعيد (DELETE) — لازم يفضل 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        method = request.method
        if method == "DELETE":
            # لو الكود حاول يحذف الشات بعيدًا، نرصدها (المطلوب: مفيش حذف بعيد).
            self.deleted_remote_calls += 1
            return httpx.Response(200, json={"ok": True})
        if path == "/api/v1/users/me":
            if self.owner_uuid is None:
                return httpx.Response(200, json={})
            return httpx.Response(200, json={"id": self.owner_uuid, "role": "owner"})
        if path == "/api/v1/app-conversations":
            if not self.convs_present:
                return httpx.Response(200, json=[])
            conv = {"id": CID, "title": "شات", "execution_status": "running"}
            if self.conv_owner is not None:
                conv["created_by_user_id"] = self.conv_owner
            return httpx.Response(200, json=[conv])
        if path.endswith("/events/search"):
            return httpx.Response(200, json={"items": []})
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


def make_client(api: MockAPI, db) -> TestClient:
    client = OpenHandsClient(
        "https://example.test", "key", transport=httpx.MockTransport(api.handler)
    )
    return TestClient(build_web_app(make_config(), db, client=client), raise_server_exceptions=False)


def login(tc: TestClient) -> None:
    assert tc.post("/api/v1/auth", json={"initData": make_init_data(OWNER)}).status_code == 200


def test_miniapp_owner_can_delete(tmp_path):
    api, db = MockAPI(), _db(tmp_path)
    db.add_watched(CID, "شات", chat_id=OWNER)
    tc = make_client(api, db)
    login(tc)
    r = tc.delete(f"/api/v1/conversations/{CID}", headers={"origin": ORIGIN})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["deleted"] is True and body["local_only"] is True
    assert db.get_watched(CID) is None  # اتشال محليًا
    assert api.deleted_remote_calls == 0  # مفيش حذف بعيد


def test_miniapp_non_owner_cannot_delete(tmp_path):
    api, db = MockAPI(), _db(tmp_path)
    api.conv_owner = "someone-else"
    db.add_watched(CID, "شات", chat_id=OWNER)
    tc = make_client(api, db)
    login(tc)
    r = tc.delete(f"/api/v1/conversations/{CID}", headers={"origin": ORIGIN})
    assert r.status_code == 403 and r.json()["error"] == "unauthorized"
    assert db.get_watched(CID) is not None  # ما اتشالش
    assert api.deleted_remote_calls == 0


def test_miniapp_unauthenticated_rejected(tmp_path):
    api, db = MockAPI(), _db(tmp_path)
    db.add_watched(CID, "شات", chat_id=OWNER)
    tc = make_client(api, db)
    r = tc.delete(f"/api/v1/conversations/{CID}", headers={"origin": ORIGIN})
    assert r.status_code == 401
    assert db.get_watched(CID) is not None


def test_miniapp_requires_origin(tmp_path):
    api, db = MockAPI(), _db(tmp_path)
    tc = make_client(api, db)
    login(tc)
    r = tc.delete(f"/api/v1/conversations/{CID}", headers={"origin": "https://evil.test"})
    assert r.status_code == 403


def test_miniapp_invalid_id_safe(tmp_path):
    api, db = MockAPI(), _db(tmp_path)
    tc = make_client(api, db)
    login(tc)
    r = tc.delete("/api/v1/conversations/bad id!", headers={"origin": ORIGIN})
    assert r.status_code == 400


def test_miniapp_repeated_delete_idempotent(tmp_path):
    api, db = MockAPI(), _db(tmp_path)
    db.add_watched(CID, "شات", chat_id=OWNER)
    tc = make_client(api, db)
    login(tc)
    r1 = tc.delete(f"/api/v1/conversations/{CID}", headers={"origin": ORIGIN})
    r2 = tc.delete(f"/api/v1/conversations/{CID}", headers={"origin": ORIGIN})
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["summary"]["watched_deleted"] == 1
    assert r2.json()["summary"]["watched_deleted"] == 0  # idempotent


# ============================================================ bot handlers
class _FakeQuery:
    def __init__(self, data):
        self.data = data
        self.edits = []
        self.markups = []
        self.answered = 0
        self.message = SimpleNamespace(chat_id=OWNER)

    async def answer(self):
        self.answered += 1

    async def edit_message_text(self, text, **kw):
        self.edits.append(text)
        self.markups.append(kw.get("reply_markup"))


class _FakeMessage:
    def __init__(self):
        self.replies = []

    async def reply_text(self, text, **kw):
        self.replies.append(text)


def _cb_update(user_id, data):
    q = _FakeQuery(data)
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_chat=SimpleNamespace(id=OWNER, type="private"),
        message=_FakeMessage(),
        callback_query=q,
    )


class _BotClient:
    """عميل وهمي كفاية لتفويض الشات: `/users/me` + `get_conversations` (مع الملكية)."""

    def __init__(self, conv=None, owner_uuid=OWNER_UUID, created_by=OWNER_UUID):
        self._conv = conv if conv is not None else {"id": CID, "title": "شات", "execution_status": "running"}
        self._owner_uuid = owner_uuid
        self._created_by = created_by
        self.deleted_remote_calls = 0

    async def get_conversations(self, ids):
        if self._conv is None:
            return []
        conv = dict(self._conv)
        if self._created_by is not None:
            conv["created_by_user_id"] = self._created_by
        return [conv]

    async def get_current_user(self):
        if self._owner_uuid is None:
            return {}
        return {"id": self._owner_uuid}

    async def delete_conversation(self, conversation_id):  # لو الكود حاول حذف بعيد
        self.deleted_remote_calls += 1


class _FakeConfig:
    def __init__(self, allowed):
        self.allowed_telegram_ids = frozenset({allowed})
        self.owner_id = allowed
        self.mini_app_url = ""

    def is_allowed(self, user_id):
        return user_id in self.allowed_telegram_ids


def _ctx(tmp_path, client):
    ctx = SimpleNamespace()
    ctx.bot_data = {
        "config": _FakeConfig(OWNER),
        "db": _db(tmp_path),
        "client": client,
    }
    ctx.bot = SimpleNamespace(sent=[], send_message=None)
    return ctx


def test_bot_delete_requires_confirmation(tmp_path):
    """ضغطة الحذف الأولى تعرض تأكيد — مش بتحذف فورًا."""
    client = _BotClient()
    ctx = _ctx(tmp_path, client)
    db = ctx.bot_data["db"]
    db.add_watched(CID, "شات", chat_id=OWNER)
    update = _cb_update(OWNER, f"delete:{CID}")
    asyncio.run(h.delete_conversation_prompt(update, ctx))
    assert db.get_watched(CID) is not None  # لسه موجود — محتاج تأكيد
    assert any("متأكد" in t for t in update.callback_query.edits)
    # فيه زر تأكيد + زر إلغاء
    markup = update.callback_query.markups[-1]
    datas = [b.callback_data for row in markup.inline_keyboard for b in row]
    assert f"deleteok:{CID}" in datas and f"open:{CID}" in datas


def test_bot_delete_confirm_owner_ok(tmp_path):
    client = _BotClient()
    ctx = _ctx(tmp_path, client)
    db = ctx.bot_data["db"]
    db.add_watched(CID, "شات", chat_id=OWNER)
    update = _cb_update(OWNER, f"deleteok:{CID}")
    asyncio.run(h.delete_conversation_confirm(update, ctx))
    assert db.get_watched(CID) is None  # اتحذف محليًا
    assert client.deleted_remote_calls == 0  # مفيش حذف بعيد
    assert any("اتشال" in t for t in update.callback_query.edits)


def test_bot_delete_confirm_non_owner_rejected(tmp_path):
    client = _BotClient(created_by="someone-else")
    ctx = _ctx(tmp_path, client)
    db = ctx.bot_data["db"]
    db.add_watched(CID, "شات", chat_id=OWNER)
    update = _cb_update(OWNER, f"deleteok:{CID}")
    asyncio.run(h.delete_conversation_confirm(update, ctx))
    assert db.get_watched(CID) is not None  # ما اتشالش (تفويض فشل)
    assert client.deleted_remote_calls == 0


def test_bot_delete_ignores_disallowed_user(tmp_path):
    client = _BotClient()
    ctx = _ctx(tmp_path, client)
    db = ctx.bot_data["db"]
    db.add_watched(CID, "شات", chat_id=OWNER)
    update = _cb_update(OTHER, f"deleteok:{CID}")
    asyncio.run(h.delete_conversation_confirm(update, ctx))
    assert db.get_watched(CID) is not None  # مش مسموح ⇒ مفيش حذف
    assert update.callback_query.edits == []


# ============================================================ consistency
def test_delete_is_idempotent_and_transactional(tmp_path):
    db = _db(tmp_path)
    now = outbox.now_iso()
    db.add_watched(CID, "شات", chat_id=OWNER)
    db.add_completion_pending(outbox.COMPLETION_KIND_OUTBOX, 7, OWNER, CID, now, title="T", notice_text="n")
    s1 = db.delete_conversation(CID, now)
    assert s1["watched_deleted"] == 1 and s1["completion_deleted"] == 1
    s2 = db.delete_conversation(CID, now)
    assert all(v == 0 for v in s2.values())  # idempotent


def test_delete_discards_pending_outbox(tmp_path):
    db = _db(tmp_path)
    now = outbox.now_iso()
    oid = db.add_outbox(CID, OWNER, "برومت", now)
    s = db.delete_conversation(CID, now)
    assert s["outbox_discarded"] == 1
    assert db.get_outbox(oid).status == "discarded"


def test_delete_removes_creation_completion_intent(tmp_path):
    """طلب شات جديد 'done' (منتهي) مايتلمسش، لكن intent الإكمال المرتبط بالشات يتشال."""
    db = _db(tmp_path)
    now = outbox.now_iso()
    jid = db.add_creation_job(OWNER, "o/r", "نص", now)
    db.set_creation_done(jid, now, CID)  # ربط الشات + حالة نهائية
    db.add_completion_pending(outbox.COMPLETION_KIND_CREATION, jid, OWNER, CID, now, title="o/r", notice_text="n")
    db.delete_conversation(CID, now)
    # الطلب المنتهي تاريخيًا بيفضل 'done' (مفيش تدمير لأثر)، بس intent الإكمال اتشال.
    assert db.get_creation_job(jid).status == "done"
    assert db.get_completion_pending(outbox.COMPLETION_KIND_CREATION, jid) is None


def test_delete_does_not_touch_inflight_sending(tmp_path):
    """حالة 'sending' (الـ POST ممكن يكون بدأ) ما بتتلمسش — مفيش ادّعاء إلغاء غامض."""
    db = _db(tmp_path)
    now = outbox.now_iso()
    oid = db.add_outbox(CID, OWNER, "برومت", now)
    db.set_outbox_status(oid, "sending", now)
    s = db.delete_conversation(CID, now)
    assert s["outbox_discarded"] == 0
    assert db.get_outbox(oid).status == "sending"


def test_completion_worker_does_not_deliver_after_delete(tmp_path):
    """عامل الإكمال ما يسلّمش إشعار قديم بعد حذف الشات (حرس عدم الإحياء)."""
    db = _db(tmp_path)
    now = outbox.now_iso()
    db.add_completion_pending(outbox.COMPLETION_KIND_OUTBOX, 5, OWNER, CID, now, title="T", notice_text="n")
    item = db.get_completion_pending(outbox.COMPLETION_KIND_OUTBOX, 5)
    db.delete_conversation(CID, now)

    sent = []

    class _Bot:
        async def send_message(self, chat_id=None, text=None, **kw):
            sent.append(text)

    asyncio.run(outbox._complete_outbox(db, _Bot(), item))
    assert sent == []  # مفيش إشعار اتسلّم لشات ملغي
    assert db.get_watched(CID) is None  # ما اتعملش متابعة جديدة (مفيش إحياء)


def test_pending_job_cannot_recreate_deleted_conversation(tmp_path):
    """طلب شات جديد معلّق مرتبط بالشات بيشطب مع الحذف ⇒ الـ worker مايقدرش يحييه."""
    db = _db(tmp_path)
    now = outbox.now_iso()
    jid = db.add_creation_job(OWNER, "o/r", "نص", now)
    # نربط الشات بطلب لسه 'pending' (حالة حدّية: طلب معلّق ومعرّف الشات اتسجّل).
    db._conn.execute(
        "UPDATE creation_jobs SET conversation_id=? WHERE id=?", (CID, jid)
    )
    db._conn.commit()
    s = db.delete_conversation(CID, now)
    assert s["creation_discarded"] == 1
    assert db.get_creation_job(jid).status == "discarded"
    # الحجز الذرّي ما بيلاقيش الطلب (اتشطب) ⇒ مستحيل يبدأ/يحيي.
    assert db.claim_creation_job(now) is None


def test_restart_recovery_preserves_deletion(tmp_path):
    """التعافي بعد restart بيحافظ على الحذف (مفيش متابعة/إكمال رجعوا)."""
    path = os.path.join(str(tmp_path), "restart.sqlite3")
    db = Database(path)
    now = outbox.now_iso()
    db.add_watched(CID, "شات", chat_id=OWNER)
    db.add_completion_pending(outbox.COMPLETION_KIND_OUTBOX, 9, OWNER, CID, now, title="T", notice_text="n")
    db.delete_conversation(CID, now)
    db.close()
    db2 = Database(path)  # "restart"
    assert db2.get_watched(CID) is None
    assert db2.get_completion_pending(outbox.COMPLETION_KIND_OUTBOX, 9) is None
    assert db2.list_open_outbox() == []
    assert db2.list_open_creation_jobs() == []


def test_concurrent_delete_and_completion_no_corruption(tmp_path):
    """حذف متزامن مع إكمال: الحالة النهائية متّسقة (مفيش متابعة/إكمال متبقّي).

    بنخلّي الإكمال يقطع عند أول `await` (إرسال الإشعار)، ووقتها ننفّذ الحذف — ده
    التداخل الحقيقي على نفس الـ event loop (مفيش threads، نفس اتصال SQLite).
    """
    db = _db(tmp_path)
    now = outbox.now_iso()
    db.add_watched(CID, "شات", chat_id=OWNER)
    db.add_completion_pending(outbox.COMPLETION_KIND_OUTBOX, 3, OWNER, CID, now, title="T", notice_text="n")
    item = db.get_completion_pending(outbox.COMPLETION_KIND_OUTBOX, 3)

    started = asyncio.Event()
    release = asyncio.Event()

    class _Bot:
        async def send_message(self, chat_id=None, text=None, **kw):
            started.set()
            await release.wait()  # نقطة التداخل: الحذف يحصل هنا

    async def scenario():
        task = asyncio.create_task(outbox._complete_outbox(db, _Bot(), item))
        await started.wait()  # الإكمال وصل للإرسال (بعد ما عمل add_watched)
        # دلوقتي نحذف — بينما الإكمال واقف عند الإرسال.
        db.delete_conversation(CID, now)
        release.set()
        await task

    asyncio.run(scenario())
    # الحذف اتشال، والإكمال اكمّل من غير ما يحيي المتابعة (get_completion_pending=None
    # عند الإرسال ⇒ clear_completion_pending no-op، والإشعار اتسلّم للأثر).
    assert db.get_watched(CID) is None
    assert db.get_completion_pending(outbox.COMPLETION_KIND_OUTBOX, 3) is None


# ============================================================ invariants kept
def test_standalone_creation_still_works(tmp_path):
    """إنشاء شات بدون مستودع لسه شغال (Feature A ما اتكسرش)."""
    from bot.web.services import MiniAppService

    class _CreateClient:
        async def search_conversations(self, limit=100, page_id=None):
            return {"items": [], "next_page_id": None}

        async def start_conversation(self, text, repository):
            assert repository is None  # بدون مستودع
            return "task-1"

    db = _db(tmp_path)
    svc = MiniAppService(make_config(), db, _CreateClient())
    res = asyncio.run(svc.create_chat("", "ابدأ شات"))
    assert res["queued"] is True and res["job_id"] > 0
    # الطلب اتسجّل بلا مستودع (repo=None) ولسه مؤهّل للـ worker.
    job = db.get_creation_job(res["job_id"])
    assert job.repo is None and job.status == "pending"
    # المسار الداخلي: بدون مستودع لازم يقبل (مفيش رفض لفراغ المستودع).
    from bot.web.services import _optional_repo

    assert _optional_repo("") is None
    assert _optional_repo("  ") is None
    assert _optional_repo("owner/repo") == "owner/repo"


def test_repository_association_still_works(tmp_path):
    """ربط المستودع لسه شغال (Feature B ما اتكسرش)."""
    api, db = MockAPI(), _db(tmp_path)

    class _PatchClient(OpenHandsClient):
        async def update_conversation_repository(self, conversation_id, repository):
            return {"id": conversation_id, "selected_repository": repository}

    client = _PatchClient(
        "https://example.test", "key", transport=httpx.MockTransport(api.handler)
    )
    tc = TestClient(build_web_app(make_config(), db, client=client), raise_server_exceptions=False)
    login(tc)
    r = tc.patch(
        f"/api/v1/conversations/{CID}/repository",
        json={"repository": "owner/repo"},
        headers={"origin": ORIGIN},
    )
    assert r.status_code == 200, r.text


def test_unwatch_behavior_unchanged(tmp_path):
    """unwatch لسه شغال ومابيتحقّقش من ملكية الشات (سلوك مقصود) — الحذف الجديد لا يغيّره."""
    api, db = MockAPI(), _db(tmp_path)
    api.convs_present = False  # الشات مش موجود أصلاً (زي اختبار A2-02)
    db.add_watched(CID, "شات", chat_id=OWNER)
    tc = make_client(api, db)
    login(tc)
    r = tc.delete(f"/api/v1/conversations/{CID}/watch", headers={"origin": ORIGIN})
    assert r.status_code == 200 and r.json() == {"ok": True, "watched": False}
    assert db.get_watched(CID) is None


def test_delete_never_calls_remote_api(tmp_path):
    """تأكيد صريح: مسار الحذف مابيعملش أي نداء DELETE بعيد (local-only)."""
    api, db = MockAPI(), _db(tmp_path)
    db.add_watched(CID, "شات", chat_id=OWNER)
    tc = make_client(api, db)
    login(tc)
    tc.delete(f"/api/v1/conversations/{CID}", headers={"origin": ORIGIN})
    assert api.deleted_remote_calls == 0


def test_bot_and_miniapp_delete_are_consistent(tmp_path):
    """تكافؤ: الاتنين بيشيلوا نفس السجل المحلي (watched) بدون حذف بعيد."""
    # Mini App
    api, mdb = MockAPI(), _db(tmp_path)
    mdb.add_watched(CID, "شات", chat_id=OWNER)
    tc = make_client(api, mdb)
    login(tc)
    assert tc.delete(f"/api/v1/conversations/{CID}", headers={"origin": ORIGIN}).status_code == 200
    assert mdb.get_watched(CID) is None

    # البوت
    client = _BotClient()
    ctx = _ctx(tmp_path, client)
    bdb = ctx.bot_data["db"]
    bdb.add_watched(CID, "شات", chat_id=OWNER)
    update = _cb_update(OWNER, f"deleteok:{CID}")
    asyncio.run(h.delete_conversation_confirm(update, ctx))
    assert bdb.get_watched(CID) is None
    assert api.deleted_remote_calls == 0 and client.deleted_remote_calls == 0


# ===================================================== PHASE6-ALIGN: shared lifecycle
def test_both_interfaces_share_same_backend_lifecycle(tmp_path, monkeypatch):
    """PHASE6-ALIGN: الواجهتين لازم يعدّوا من **نفس** الدالة الخلفية (مفيش مسارين).

    نرقّب `Database.delete_conversation` (نفس كائن القاعدة) ونتأكد إن مسار البوت
    ومسار الـ Mini App بينادوا عليه بنفس المعرّف — دليل ملموس على «دورة حياة واحدة».
    """
    from bot.db import Database

    calls: list[str] = []
    original = Database.delete_conversation

    def _spy(self, conversation_id, now):
        calls.append(conversation_id)
        return original(self, conversation_id, now)

    monkeypatch.setattr(Database, "delete_conversation", _spy)

    # Mini App
    api, mdb = MockAPI(), _db(tmp_path)
    mdb.add_watched(CID, "شات", chat_id=OWNER)
    tc = make_client(api, mdb)
    login(tc)
    assert tc.delete(f"/api/v1/conversations/{CID}", headers={"origin": ORIGIN}).status_code == 200

    # البوت
    client = _BotClient()
    ctx = _ctx(tmp_path, client)
    bctx_db = ctx.bot_data["db"]
    bctx_db.add_watched(CID, "شات", chat_id=OWNER)
    asyncio.run(h.delete_conversation_confirm(_cb_update(OWNER, f"deleteok:{CID}"), ctx))

    # نفس الدالة الخلفية اتنادت مرتين (واحدة لكل واجهة) بنفس المعرّف.
    assert calls.count(CID) == 2


def test_delete_route_registered_on_web_app():
    """PHASE6-ALIGN: مسار الحذف مسجّل فعلًا على تطبيق الـ Mini App بميثود DELETE."""
    from bot.web.app import API_PREFIX, build_web_app

    app = build_web_app(make_config(), _db(__import__("tempfile").mkdtemp()))
    target = f"{API_PREFIX}/conversations/{{conversation_id}}"
    routes = [r for r in app.routes if getattr(r, "path", None) == target]
    assert routes, f"لازم يكون فيه راوت {target}"
    methods = {m for r in routes for m in getattr(r, "methods", set()) or set()}
    assert "DELETE" in methods, "لازم المسار يدعم DELETE"


def test_bot_delete_menu_and_callbacks_wired():
    """PHASE6-ALIGN: زر الحذف وقوائم التأكيد/الإلغاء موجودين ومربوطين بالـ callback data."""
    from bot import keyboards as kb

    menu = kb.conversation_actions(CID, watched=False)
    datas = [b.callback_data for row in menu.inline_keyboard for b in row]
    assert f"delete:{CID}" in datas, "زر الحذف لازم يكون ظاهر في قايمة الشات"

    confirm = kb.delete_confirm_menu(CID)
    cdatas = [b.callback_data for row in confirm.inline_keyboard for b in row]
    assert f"deleteok:{CID}" in cdatas and f"open:{CID}" in cdatas, "تأكيد + إلغاء"


# ================================================= PHASE6-UI: list hides deleted
class _ListClient:
    """عميل وهمي بسيط: search بيرجّع نفس الشاتات دايمًا (بعيد ⇒ مش عارف بالحذف المحلي)."""

    def __init__(self, items):
        self._items = items

    async def search_conversations(self, limit=100, page_id=None):
        return {"items": list(self._items), "next_page_id": None}

    async def get_conversations(self, ids):
        return [dict(i) for i in self._items if i["id"] in ids]

    async def get_current_user(self):
        return {"id": OWNER_UUID}


class _FakeApp:
    def __init__(self):
        self.bot_data = {}


def test_miniapp_list_hides_locally_deleted(tmp_path):
    """بعد الحذف المحلي، الشات لازم يختفي من قايمة الـ Mini App (مصدر القايمة بعيد).

    ده يمنع «رجوع الشات بعد refresh» — مفيش حالة عميل قديمة تعرضه تاني.
    """
    db = _db(tmp_path)
    items = [
        {"id": "c1", "title": "واحد", "execution_status": "running", "created_by_user_id": OWNER_UUID},
        {"id": "c2", "title": "اتنين", "execution_status": "running", "created_by_user_id": OWNER_UUID},
    ]
    app = _FakeApp()
    client = _ListClient(items)
    tc = TestClient(
        build_web_app(make_config(), db, client=client, application=app),
        raise_server_exceptions=False,
    )
    login(tc)

    r = tc.get("/api/v1/conversations?refresh=1")
    assert r.status_code == 200, r.text
    assert [i["id"] for i in r.json()["items"]] == ["c1", "c2"]

    # حذف محلي لـ c1 عبر المسار الحقيقي.
    assert tc.delete("/api/v1/conversations/c1", headers={"origin": ORIGIN}).status_code == 200

    r2 = tc.get("/api/v1/conversations?refresh=1")
    ids = [i["id"] for i in r2.json()["items"]]
    assert "c1" not in ids, "الشات المحذوف محليًا لازم يختفي من القايمة"
    assert ids == ["c2"]


def test_miniapp_list_cache_refresh_still_hides_deleted(tmp_path):
    """حتى مع الكاش القصير المشارك: الشات المحذوف ما يظهرش بعد refresh."""
    db = _db(tmp_path)
    items = [
        {"id": "c1", "title": "واحد", "execution_status": "running", "created_by_user_id": OWNER_UUID},
        {"id": "c2", "title": "اتنين", "execution_status": "running", "created_by_user_id": OWNER_UUID},
    ]
    app = _FakeApp()
    client = _ListClient(items)
    tc = TestClient(
        build_web_app(make_config(), db, client=client, application=app),
        raise_server_exceptions=False,
    )
    login(tc)

    assert tc.get("/api/v1/conversations").status_code == 200  # يملأ الكاش
    assert tc.delete("/api/v1/conversations/c1", headers={"origin": ORIGIN}).status_code == 200
    # من غير refresh (من الكاش) برضه لازم يختفي.
    r = tc.get("/api/v1/conversations")
    assert "c1" not in [i["id"] for i in r.json()["items"]]


# ===================================== OHB2-AUDIT-FIX-04: fail-closed tombstone filter
class _RaisingDB:
    """قاعدة وهمية: `is_deleted` بترمي (محاكاة قاعدة غير متاحة/تالفة)."""

    def is_deleted(self, conversation_id):
        raise RuntimeError("database unavailable")


def test_bot_without_deleted_fails_closed_on_db_error():
    """handlers._without_deleted: خطأ قاعدة ⇒ قايمة فاضية (مش القايمة غير المفلترة)."""
    items = [{"id": "c1"}, {"id": "c2"}]
    assert h._without_deleted(_RaisingDB(), items) == []


def test_bot_without_deleted_empty_input_short_circuits():
    """مدخل فاضي ⇒ فاضي (مفيش نداء للقاعدة أصلًا)."""
    assert h._without_deleted(_RaisingDB(), []) == []


def test_miniapp_without_deleted_fails_closed_on_db_error(tmp_path):
    """MiniAppService._without_deleted: خطأ قاعدة ⇒ قايمة فاضية (فشل مغلق)."""
    from bot.web.services import MiniAppService

    svc = MiniAppService(make_config(), _RaisingDB())
    items = [{"id": "c1"}, {"id": "c2"}]
    assert svc._without_deleted(items) == []


def test_miniapp_list_hides_all_on_db_error(tmp_path):
    """تكاملي: قاعدة بتفشل في is_deleted ⇒ الـ API يرجّع قايمة فاضية (مفيش إظهار بالغلط)."""
    db = _db(tmp_path)
    items = [
        {"id": "c1", "title": "واحد", "execution_status": "running", "created_by_user_id": OWNER_UUID},
        {"id": "c2", "title": "اتنين", "execution_status": "running", "created_by_user_id": OWNER_UUID},
    ]
    app = _FakeApp()
    client = _ListClient(items)
    tc = TestClient(
        build_web_app(make_config(), db, client=client, application=app),
        raise_server_exceptions=False,
    )
    login(tc)
    assert tc.get("/api/v1/conversations?refresh=1").status_code == 200  # يملأ الكاش

    # نخرّب قراءة الشواهد فقط (بعد ما الكاش اتملى) ⇒ الفلترة تفشل ⇒ فشل مغلق.
    def _boom(_cid):
        raise RuntimeError("db down")

    db.is_deleted = _boom  # type: ignore[assignment]
    r = tc.get("/api/v1/conversations?refresh=1")
    assert r.status_code == 200
    assert r.json()["items"] == [], "لازم نخفي القايمة كلها بدل ما نعرّض شات محذوف"


# ================================== OHB2-AUDIT-FIX-05: Mini App list collects all pages
class _PagedListClient:
    """عميل وهمي بيدعم البحث بصفحات عبر next_page_id."""

    def __init__(self, pages):
        self._pages = pages
        self.calls = []

    async def search_conversations(self, limit=100, page_id=None):
        self.calls.append(page_id)
        return self._pages[page_id]

    async def get_current_user(self):
        return {"id": OWNER_UUID}


def _conv(cid):
    return {"id": cid, "title": cid, "execution_status": "running",
            "created_by_user_id": OWNER_UUID}


def test_miniapp_list_collects_all_pages(tmp_path):
    """الـ Mini App لازم يجمع كل الصفحات — الشات الأقدم (صفحة 2) يبقى قابل للوصول."""
    pages = {
        None: {"items": [_conv(f"c{i}") for i in range(10)], "next_page_id": "p2"},
        "p2": {"items": [_conv("c99")], "next_page_id": None},
    }
    client = _PagedListClient(pages)
    tc = TestClient(
        build_web_app(make_config(), _db(tmp_path), client=client, application=_FakeApp()),
        raise_server_exceptions=False,
    )
    login(tc)
    r = tc.get("/api/v1/conversations?refresh=1")
    assert r.status_code == 200, r.text
    body = r.json()
    # اتلمّت 11 شات (10 + c99) ⇒ الصفحة الأولى فيها 10 وhas_more=true (c99 على الصفحة 2).
    assert len(body["items"]) == 10
    assert body["has_more"] is True
    assert body["truncated"] is False
    assert client.calls == [None, "p2"]  # اتلمّت كل الصفحات
    r2 = tc.get("/api/v1/conversations?page=1")
    assert r2.status_code == 200, r2.text
    assert "c99" in [i["id"] for i in r2.json()["items"]]  # مش مخفي بعد أول صفحة


def test_miniapp_list_flags_truncation(tmp_path):
    """لو فيه صفحات أكتر من الحد ⇒ `truncated=true` (إعلان صريح، مش إخفاء صامت)."""

    class AlwaysMore:
        async def search_conversations(self, limit=100, page_id=None):
            return {"items": [_conv("c1")], "next_page_id": "more"}

        async def get_current_user(self):
            return {"id": OWNER_UUID}

    tc = TestClient(
        build_web_app(make_config(), _db(tmp_path), client=AlwaysMore(), application=_FakeApp()),
        raise_server_exceptions=False,
    )
    login(tc)
    r = tc.get("/api/v1/conversations?refresh=1")
    assert r.status_code == 200, r.text
    assert r.json()["truncated"] is True
