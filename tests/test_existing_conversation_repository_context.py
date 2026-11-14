"""OHB2-TELEGRAM-EXISTING-CONVERSATION-REPOSITORY-CONTEXT-FIX — اختبارات انحدار.

المشكلة المُبلَّغ عنها: إرسال برومت جوه شات تيليجرام موجود (مربوط بمستودع OpenHands)
كان بيخلّي البوت يعمل شات OpenHands **جديد** بنفس البرومت **من غير** مستودع، بدل ما
يبعت البرومت للشات الموجود ويحافظ على المستودع/الـ workspace.

الاختبارات دي بتثبّت المسار الصح بايت-بايت عبر **عميل OpenHands حقيقي** (مع
`httpx.MockTransport`، مفيش نداءات إنتاج) و**قاعدة SQLite معزولة**، وبتراقب النداءات
الشبكة الفعلية: لازم نشوف `POST /app-conversations/{existing_id}/send-message`،
و**صفر** نداءات `POST /app-conversations` (الإنشاء). أي ارتداد للمشكلة الأصلية
(إنشاء شات جديد بدل الإرسال) هيكسر `assert` الإنشاء = صفر.

كل السيناريوهات المطلوبة في المهمة متغطّاة هنا:
- برومت لشات موجود مربوط بمستودع.
- معرّف الشات الصحيح بيوصل لـ API إرسال الرسالة.
- سياق المستودع/الـ sandbox محفوظ.
- مفيش شات جديد أثناء الإرسال العادي.
- برومتات متتالية تفضل في نفس الشات.
- شات موجود مستقل (بدون مستودع) لسه شغال.
- إنشاء شات مستقل جديد لسه شغال.
- إنشاء شات مربوط بمستودع لسه شغال.
- ربط مستودع لاحقًا مدعوم (PATCH على نفس الشات).
- تعيين شات ناقص/غير صالح يفشل بأمان (مفيش إنشاء بديل).
- وصول غير مصرّح بيه مايقدرش يشغّل إنشاء أو إرسال.
- إعادة المحاولة/التعافي مابتكرّرش شات جديد.
- الإرسال المتزامن بيحافظ على هوية الشات المقصود.
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import httpx

import bot.handlers as h
from bot.db import Database
from bot.openhands_client import OpenHandsClient

OWNER_ID = 1
OWNER_UUID = "owner-uuid-123"
# معرّف 32 حرف (شكل UUID الحقيقي) عشان يعدّي تحقق مسار الـ API.
CID = "11111111222233334444555566667777"
CID_STANDALONE = "aaaaaaaaaaaabbbbccccddddeeeeeeee"


class RecordingAPI:
    """خادم OpenHands وهمي بيسجّل كل نداء، وبيخدم حالات الشاتات المعرَّفة.

    `conversations`: {id: dict} — الشاتات اللي الـ GET بيرجّعها (الباقي غايب ⇒ 404/فاضي).
    """

    def __init__(self, conversations: dict[str, dict] | None = None) -> None:
        self.conversations = conversations or {}
        self.calls: list[tuple[str, str, dict | None]] = []
        self.resumed_sandboxes: list[str] = []
        self.send_bodies: list[tuple[str, dict]] = []
        self.create_bodies: list[dict] = []
        self.patch_bodies: list[tuple[str, dict]] = []
        # بعد أي resume، الشات يبقى RUNNING (زي ما الـ sandbox بيصحى فعلاً).
        self._resumed = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = None
        if request.content:
            try:
                body = json.loads(request.content.decode("utf-8"))
            except ValueError:
                body = None
        path = request.url.path
        self.calls.append((request.method, path, body))

        if path == "/api/v1/users/me":
            return httpx.Response(200, json={"id": OWNER_UUID})

        if path == "/api/v1/app-conversations":
            if request.method == "POST":
                # نداء الإنشاء — أي وصول هنا في مسار برومت شات موجود = الباگ.
                self.create_bodies.append(body or {})
                return httpx.Response(200, json={"id": "task-created"})
            # GET ?ids=... ⇒ نرجّع الشاتات المطلوبة الموجودة بس (زي الـ API).
            ids = request.url.params.get_list("ids")
            found = []
            for i in ids:
                if i not in self.conversations:
                    continue
                conv = dict(self.conversations[i])
                if self._resumed and conv.get("sandbox_status") == "PAUSED":
                    conv["sandbox_status"] = "RUNNING"
                found.append(conv)
            return httpx.Response(200, json=found)

        if path == "/api/v1/app-conversations/start-tasks":
            return httpx.Response(
                200, json=[{"status": "READY", "app_conversation_id": CID}]
            )

        if path.startswith("/api/v1/app-conversations/") and path.endswith("/send-message"):
            cid = path[len("/api/v1/app-conversations/") : -len("/send-message")]
            self.send_bodies.append((cid, body or {}))
            return httpx.Response(200, json={"ok": True})

        if path.endswith("/events/search"):
            return httpx.Response(200, json={"items": []})

        if path.startswith("/api/v1/sandboxes/") and path.endswith("/resume"):
            sandbox_id = path[len("/api/v1/sandboxes/") : -len("/resume")]
            self.resumed_sandboxes.append(sandbox_id)
            self._resumed = True
            return httpx.Response(200, json={"ok": True})

        if path.startswith("/api/v1/app-conversations/") and request.method == "PATCH":
            cid = path[len("/api/v1/app-conversations/") :]
            self.patch_bodies.append((cid, body or {}))
            conv = dict(self.conversations.get(cid, {"id": cid}))
            conv.update(body or {})
            self.conversations[cid] = conv
            return httpx.Response(200, json=conv)

        if path.startswith("/api/v1/app-conversations/") and path.endswith("/files"):
            return httpx.Response(200, json=[])

        return httpx.Response(404, json={"detail": "no"})

    # ---- مساعدات تحقّق
    def create_calls(self) -> list[tuple[str, str, dict | None]]:
        return [c for c in self.calls if c[0] == "POST" and c[1] == "/api/v1/app-conversations"]

    def send_calls(self) -> list[tuple[str, str, dict | None]]:
        return [c for c in self.calls if c[1].endswith("/send-message")]


class FakeBot:
    def __init__(self) -> None:
        self.notices: list[str] = []

    async def send_message(self, chat_id=None, text=None, **kw) -> None:  # noqa: ANN001
        self.notices.append(text or "")


class FakeConfig:
    def __init__(self, allowed: set[int]) -> None:
        self.allowed_telegram_ids = frozenset(allowed)
        self.owner_id = OWNER_ID
        self.openhands_base_url = "https://x.test"
        self.mini_app_enabled = False
        self.mini_app_url = ""

    def is_allowed(self, user_id: int) -> bool:
        return user_id in self.allowed_telegram_ids


class _Msg:
    def __init__(self) -> None:
        self.replies: list[str] = []

    async def reply_text(self, text, **kw) -> None:  # noqa: ANN001
        self.replies.append(text)


class _Query:
    def __init__(self, data: str) -> None:
        self.data = data
        self.edits: list[str] = []
        self.markups: list[object] = []
        self.message = SimpleNamespace(chat_id=99)

    async def answer(self) -> None:
        pass

    async def edit_message_text(self, text, **kw) -> None:  # noqa: ANN001
        self.edits.append(text)
        self.markups.append(kw.get("reply_markup"))


def _text_update(user_id: int, text: str) -> SimpleNamespace:
    msg = _Msg()
    msg.text = text
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_chat=SimpleNamespace(id=99, type="private"),
        message=msg,
        callback_query=None,
    )


def _callback_update(user_id: int, data: str) -> SimpleNamespace:
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_chat=SimpleNamespace(id=99, type="private"),
        callback_query=_Query(data),
        message=SimpleNamespace(chat_id=99),
    )


def _conv(cid: str, repo: str | None, *, sandbox: str = "RUNNING", sandbox_id: str = "sb-1") -> dict:
    conv = {
        "id": cid,
        "title": f"شات {cid[:4]}",
        "execution_status": "running",
        "sandbox_status": sandbox,
        "sandbox_id": sandbox_id,
        "created_by_user_id": OWNER_UUID,
    }
    if repo:
        conv["selected_repository"] = repo
    return conv


def _ctx(tmp_path, api: RecordingAPI) -> SimpleNamespace:
    client = OpenHandsClient("https://x.test", "key", transport=httpx.MockTransport(api.handler))
    ctx = SimpleNamespace(
        bot_data={
            "config": FakeConfig({OWNER_ID}),
            "db": Database(str(tmp_path / "t.sqlite3")),
            "client": client,
        },
        bot=FakeBot(),
    )
    return ctx


def _deliver(ctx, outbox_id: int) -> None:
    """تشغيل مسار التسليم المباشر (بدون نافذة تجميع 1.5 ثانية غير حتمية)."""
    asyncio.run(
        h._deliver_outbox(ctx.bot_data["client"], ctx.bot_data["db"], ctx.bot, outbox_id)
    )


def _send_and_deliver(ctx, text: str = "برومت") -> int:
    update = _text_update(OWNER_ID, text)
    asyncio.run(h.handle_text(update, ctx))
    rows = ctx.bot_data["db"].list_outbox_by_status("pending")
    assert rows, "المفروض البرومت اتسجّل في الصندوق"
    oid = rows[-1].id
    _deliver(ctx, oid)
    return oid


# ------------------------------------------------------------------ المسار الأساسي
def test_prompt_to_repo_linked_conversation_reuses_existing_conversation(tmp_path):
    """البرومت يتبعت للشات الموجود، والمستودع/الـ sandbox يفضلوا كما هم، ومفيش إنشاء."""
    api = RecordingAPI({CID: _conv(CID, "owner/repo")})
    ctx = _ctx(tmp_path, api)

    asyncio.run(h.open_conversation(_callback_update(OWNER_ID, f"open:{CID}"), ctx))
    assert ctx.bot_data["db"].get_awaiting(OWNER_ID) == (CID, "route")

    _send_and_deliver(ctx, "برومت للمستودع")

    # معرّف الشات الصحيح وصل لـ API الإرسال، والمحتوى كما هو.
    assert [c[1] for c in api.send_calls()] == [f"/api/v1/app-conversations/{CID}/send-message"]
    assert api.send_bodies[0][1]["content"][0]["text"] == "برومت للمستودع"
    # مفيش أي شات جديد اتعمل.
    assert api.create_calls() == []
    # مفيش طلب إنشاء مسجّل محليًا.
    assert ctx.bot_data["db"].list_open_creation_jobs() == []
    # المستودع محفوظ على الشات (مفيش تغيير).
    assert api.conversations[CID]["selected_repository"] == "owner/repo"
    assert api.conversations[CID]["sandbox_id"] == "sb-1"


def test_no_creation_endpoint_is_hit_for_ordinary_message_submission(tmp_path):
    """تأكيد مباشر: مسار الإرسال العادي مابيلمسش نقطة الإنشاء خالص."""
    api = RecordingAPI({CID: _conv(CID, "owner/repo")})
    ctx = _ctx(tmp_path, api)

    asyncio.run(h.open_conversation(_callback_update(OWNER_ID, f"open:{CID}"), ctx))
    _send_and_deliver(ctx, "مرحبا")

    assert api.create_calls() == []
    assert api.create_bodies == []
    # نقطة الإرسال اتلمست مرة واحدة بس (نفس الشات).
    assert len(api.send_calls()) == 1


def test_multiple_consecutive_prompts_remain_in_same_conversation(tmp_path):
    """برومتات متتالية تفضل في نفس الشات (مفيش تبديل ولا إنشاء)."""
    api = RecordingAPI({CID: _conv(CID, "owner/repo")})
    ctx = _ctx(tmp_path, api)

    asyncio.run(h.open_conversation(_callback_update(OWNER_ID, f"open:{CID}"), ctx))
    for i in range(3):
        _send_and_deliver(ctx, f"رسالة {i}")

    assert [c[1] for c in api.send_calls()] == [
        f"/api/v1/app-conversations/{CID}/send-message"
    ] * 3
    assert api.create_calls() == []


def test_repository_and_sandbox_context_preserved_on_resume(tmp_path):
    """لو الـ sandbox مش شغّال، بنعمله resume بنفس `sandbox_id` بتاع الشات (مش sandbox جديد)."""
    api = RecordingAPI({CID: _conv(CID, "owner/repo", sandbox="PAUSED", sandbox_id="sb-repo-9")})
    ctx = _ctx(tmp_path, api)

    asyncio.run(h.open_conversation(_callback_update(OWNER_ID, f"open:{CID}"), ctx))
    _send_and_deliver(ctx, "برومت")

    assert api.resumed_sandboxes == ["sb-repo-9"]
    assert [c[1] for c in api.send_calls()] == [f"/api/v1/app-conversations/{CID}/send-message"]
    assert api.create_calls() == []


# ------------------------------------------------------- شاتات مستقلة (بدون مستودع)
def test_existing_standalone_conversation_still_usable(tmp_path):
    """شات موجود من غير مستودع: البرومت يتبعت له عادي، ومفيش إنشاء."""
    api = RecordingAPI({CID_STANDALONE: _conv(CID_STANDALONE, None)})
    ctx = _ctx(tmp_path, api)

    asyncio.run(
        h.open_conversation(_callback_update(OWNER_ID, f"open:{CID_STANDALONE}"), ctx)
    )
    _send_and_deliver(ctx, "برومت مستقل")

    assert [c[1] for c in api.send_calls()] == [
        f"/api/v1/app-conversations/{CID_STANDALONE}/send-message"
    ]
    assert api.create_calls() == []


def test_new_standalone_conversation_creation_still_works(tmp_path):
    """إنشاء شات جديد **بدون** مستودع لسه شغال: POST إنشاء بلا `selected_repository`."""
    api = RecordingAPI()
    ctx = _ctx(tmp_path, api)

    asyncio.run(h._create_chat(ctx, 99, None, "ابدأ من غير مستودع"))

    assert len(api.create_calls()) == 1
    assert "selected_repository" not in api.create_bodies[0]
    job = ctx.bot_data["db"].list_creation_jobs_by_status("done")
    assert len(job) == 1 and job[0].conversation_id == CID


def test_repo_linked_conversation_creation_still_works(tmp_path):
    """إنشاء شات جديد **بمستودع** لسه شغال: POST إنشاء فيه `selected_repository`."""
    api = RecordingAPI()
    ctx = _ctx(tmp_path, api)

    asyncio.run(h._create_chat(ctx, 99, "owner/repo", "ابدأ بمستودع"))

    assert len(api.create_calls()) == 1
    assert api.create_bodies[0]["selected_repository"] == "owner/repo"


def test_repository_can_be_associated_later_on_existing_conversation(tmp_path):
    """ربط مستودع لاحقًا (PATCH) على شات موجود لسه مدعوم — بدون إنشاء شات جديد."""
    api = RecordingAPI({CID_STANDALONE: _conv(CID_STANDALONE, None)})
    ctx = _ctx(tmp_path, api)

    asyncio.run(
        ctx.bot_data["client"].update_conversation_repository(CID_STANDALONE, "owner/late")
    )
    assert api.patch_bodies == [(CID_STANDALONE, {"selected_repository": "owner/late"})]
    assert api.conversations[CID_STANDALONE]["selected_repository"] == "owner/late"
    assert api.create_calls() == []


# ------------------------------------------------------------- فشل آمن
def test_missing_conversation_mapping_fails_safely_without_creation(tmp_path):
    """لو الشات مش موجود، مفيش إنشاء بديل ومفيش إرسال — البرومت يفضل مؤهّل لإعادة المحاولة."""
    api = RecordingAPI({})  # مفيش شاتات موجودة
    ctx = _ctx(tmp_path, api)
    # توجيه لشات مش موجود (رد على معرّف قديم/غير صالح).
    ctx.bot_data["db"].set_awaiting(OWNER_ID, CID, "reply")

    oid = _send_and_deliver(ctx, "برومت لشات ضايع")

    assert api.create_calls() == []
    assert api.send_calls() == []
    # مفيش طلب إنشاء مسجّل، والبرومت لسه مؤهّل (مفيش ادّعاء نجاح كاذب).
    assert ctx.bot_data["db"].list_open_creation_jobs() == []
    assert ctx.bot_data["db"].get_outbox(oid).status == "pending"


def test_unauthorized_access_cannot_trigger_creation_or_submission(tmp_path):
    """مستخدم مش مسموح مايقدرش يشغّل إرسال ولا إنشاء (لا توجيه ولا صندوق)."""
    api = RecordingAPI({CID: _conv(CID, "owner/repo")})
    ctx = _ctx(tmp_path, api)

    update = _text_update(999, "محاولة غير مصرّح بيها")
    asyncio.run(h.handle_text(update, ctx))

    assert api.create_calls() == []
    assert api.send_calls() == []
    assert ctx.bot_data["db"].count_outbox() == 0
    assert update.message.replies == []


# ----------------------------------------------------- إعادة المحاولة/التعافي
def test_outbox_recovery_does_not_create_duplicate_conversation(tmp_path):
    """التعافي بعد restart مايعملش شات جديد ولا إرسال مكرّر لبرومت خلص."""
    api = RecordingAPI({CID: _conv(CID, "owner/repo")})
    ctx = _ctx(tmp_path, api)

    asyncio.run(h.open_conversation(_callback_update(OWNER_ID, f"open:{CID}"), ctx))
    _send_and_deliver(ctx, "برومت مرة واحدة")

    before_sends = len(api.send_calls())
    before_creates = len(api.create_calls())

    # تعافي الصندوق (idempotent) — زي _post_init بعد restart.
    app = SimpleNamespace(bot_data=ctx.bot_data, bot=ctx.bot)
    asyncio.run(h.outbox_recover(app))
    asyncio.run(h.outbox_recover(app))

    assert len(api.send_calls()) == before_sends  # مفيش إرسال تاني
    assert len(api.create_calls()) == before_creates == 0  # مفيش إنشاء خالص


def test_retry_of_same_prompt_does_not_create_conversation(tmp_path):
    """إعادة محاولة برومت معلّق آمنة (sandbox مش جاهز) مايتحوّلش لإنشاء شات جديد."""
    api = RecordingAPI({CID: _conv(CID, "owner/repo", sandbox="PAUSED", sandbox_id="sb-x")})
    # نخلي resume يفشل ⇒ المحاولة تفضل آمنة/مؤهّلة (قبل أي POST).
    orig = api.handler

    def failing_resume(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/resume"):
            api.calls.append((request.method, request.url.path, None))
            return httpx.Response(503, json={"detail": "busy"})
        return orig(request)

    client = OpenHandsClient("https://x.test", "key", transport=httpx.MockTransport(failing_resume))
    ctx = SimpleNamespace(
        bot_data={
            "config": FakeConfig({OWNER_ID}),
            "db": Database(str(tmp_path / "t.sqlite3")),
            "client": client,
        },
        bot=FakeBot(),
    )

    asyncio.run(h.open_conversation(_callback_update(OWNER_ID, f"open:{CID}"), ctx))
    _send_and_deliver(ctx, "برومت")

    assert api.create_calls() == []
    assert api.send_calls() == []
    # البرومت لسه مؤهّل لإعادة المحاولة (فشل آمن قبل الإرسال).
    assert len(ctx.bot_data["db"].list_outbox_by_status("pending")) == 1


# --------------------------------------------------------- التزامن
def test_concurrent_prompts_preserve_conversation_identity(tmp_path):
    """رسايل متزامنة كتير كلها تفضل موجّهة لنفس الشات المقصود، ومفيش إنشاء."""
    api = RecordingAPI({CID: _conv(CID, "owner/repo")})
    ctx = _ctx(tmp_path, api)

    asyncio.run(h.open_conversation(_callback_update(OWNER_ID, f"open:{CID}"), ctx))
    updates = [_text_update(OWNER_ID, f"م{i}") for i in range(10)]

    async def go():
        await asyncio.gather(*(h.handle_text(u, ctx) for u in updates))

    asyncio.run(go())

    rows = ctx.bot_data["db"].list_outbox_by_status("pending")
    assert {r.conversation_id for r in rows} == {CID}  # كلها لنفس الشات
    assert len(rows) == 1  # تجميع في سجل واحد (القرار 2)
    assert api.create_calls() == []
