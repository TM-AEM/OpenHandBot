"""OHB2-SW-04 + OHB2-SW-05: اختبارات انحدار (تفويض upstream + فشل التسليم).

SW-04: `_authorized_conversation` كان بيخسّر التمييز بين «فشل خدمة upstream» و«رفض
تفويض عادي»، لأن `IdentityCache.owner_id()` كان بيحوّل أي `ApiError` من `/users/me`
لـ None ⇒ الحالة بتتحوّل `UNAUTHORIZED` (403) بدل `UPSTREAM_ERROR` (502). الإصلاح
بيحفظ التفصيل لكل المسارات مع بقاء الفشل **فشل مغلق** (مفيش نجاح كاذب، مفيش عملية
بتتنفّذ من غير تفويض مؤكّد).

SW-05: `_edit_or_send()` بيرجّع False لو فشل العرض، لكن `show_status`/`show_cost`
كانوا بيتجاهلوا القيمة، ومسار «too long» كان بيرمي الاستثناء بدل ما يرجّع False.
الإصلاح بيخلّي كل مستدعي متأثّر يتعامل مع الفشل صريح (لوج)، و`_edit_or_send` ما
بيرميش استثناء للخارج في أي فرع فشل.

الاختبارات دي حقيقية (مفيش mocks للكود المختبر): بتستخدم نفس كود البوت و Mini App
الحقيقي فوق عميل وهمي، ومفيش أي نداء شبكة.
"""
from __future__ import annotations

import asyncio
import logging
import pathlib
import sys

import httpx
import pytest
from starlette.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import bot.handlers as h  # noqa: E402
from bot.config import Config  # noqa: E402
from bot.errors import ApiError  # noqa: E402
from bot.files import (  # noqa: E402
    FileStatus,
    IdentityCache,
    authorize_conversation_detailed,
)
from bot.openhands_client import OpenHandsClient  # noqa: E402
from bot.web import build_web_app  # noqa: E402
from tests._miniapp_helpers import BOT_TOKEN, make_init_data  # noqa: E402
from tests.test_handlers import (  # noqa: E402
    CONV55,
    CQ,
    ExchangeClient,
    RecBot,
    _t55_cb_update,
    make_context,
)

UNAUTH_TEXT = "مش مسموح لك بالوصول للشات ده."
UPSTREAM_TEXT = "تعذّر الوصول للشات دلوقتي، جرّب تاني."
UPSTREAM_API = ApiError("خدمة OpenHands مش متاحة دلوقتي.", 503)


# =====================================================================
# عملاء الاختبار (bot): فشل upstream في نقطة محدّدة
# =====================================================================
class ConversationsUpstreamClient(ExchangeClient):
    """فشل `get_conversations` (نقطة الميتاداتا) — upstream في أول التفويض."""

    async def get_conversations(self, ids):
        raise UPSTREAM_API


class IdentityUpstreamClient(ExchangeClient):
    """`get_conversations` بينجح لكن `/users/me` (الهوية) بيفشل — upstream متأخّر.

    ده بالظبط المسار اللي كان بيتلبّس كـ `UNAUTHORIZED` قبل الإصلاح.
    """

    async def get_current_user(self):
        raise UPSTREAM_API


class IdentityMissingClient(ExchangeClient):
    """`/users/me` رجّع بلا id ⇒ هوية مش متأكّدة (لسه `UNAUTHORIZED`)."""

    async def get_current_user(self):
        return {}


def _run(handler, data, client):
    """يشغّل handler كولباك ويرجّع `(ctx, q, exc)`.

    OHB2-SW-07: بعض المسارات (open/copy) بقت ترفع `OperationalApiFailure` عند الفشل
    التشغيلي بعد عرض الرسالة؛ بنلتقطها هنا عشان الاختبارات تفحص **الرسالة المعروضة**
    (التمييز upstream/unauthorized) وتأكّد سلوك الانتشار في نفس الوقت. المسارات التانية
    (status/cost/txt/watch/...) لسه بترجع عاديًّا ⇒ `exc` تبقى None.
    """
    ctx = make_context(1, pathlib.Path(_tmpdir()), client=client)
    ctx.bot = RecBot()
    q = CQ(data)
    exc = None
    try:
        asyncio.run(handler(_t55_cb_update(q), ctx))
    except h.OperationalApiFailure as caught:  # noqa: PERF203 — الانتشار المتوقّع للمسارات المعنية
        exc = caught
    return ctx, q, exc


def _tmpdir() -> str:
    import tempfile

    return tempfile.mkdtemp()


# =====================================================================
# SW-04 — الحالات الأساسية للتمييز
# =====================================================================
def test_authorize_detailed_identity_upstream_is_upstream_error_not_unauthorized():
    client = IdentityUpstreamClient(CONV55)
    conv, status, err, _exc = asyncio.run(
        authorize_conversation_detailed(client, IdentityCache(client), "A", None)
    )
    assert conv is None
    assert status is FileStatus.UPSTREAM_ERROR  # مش UNAUTHORIZED
    assert status is not FileStatus.UNAUTHORIZED


def test_authorize_detailed_identity_missing_is_unauthorized():
    client = IdentityMissingClient(CONV55)
    conv, status, _err, _exc = asyncio.run(
        authorize_conversation_detailed(client, IdentityCache(client), "A", None)
    )
    assert conv is None
    assert status is FileStatus.UNAUTHORIZED


def test_owner_id_detailed_preserves_upstream_and_wrapper_still_returns_none():
    """`owner_id_detailed` بيفرّق؛ الـ wrapper القديم `owner_id` لسه None (توافق خلفي)."""
    client = IdentityUpstreamClient(CONV55)
    cache = IdentityCache(client)
    owner, status, _exc = asyncio.run(cache.owner_id_detailed())
    assert owner is None and status is FileStatus.UPSTREAM_ERROR
    # التوافق الخلفي: owner_id (المستخدم في المسارات التانية) لسه None عند الفشل.
    client2 = IdentityUpstreamClient(CONV55)
    assert asyncio.run(IdentityCache(client2).owner_id()) is None


def test_bot_open_conversations_upstream_preserved_message():
    _ctx, q, _exc = _run(h.open_conversation, "open:A", ConversationsUpstreamClient(CONV55))
    assert q.edits and q.edits[-1] == "خدمة OpenHands مش متاحة دلوقتي."
    assert UNAUTH_TEXT not in q.edits[-1]


def test_bot_open_identity_upstream_not_shown_as_unauthorized():
    _ctx, q, _exc = _run(h.open_conversation, "open:A", IdentityUpstreamClient(CONV55))
    assert q.edits, "لازم تظهر رسالة خطأ"
    assert q.edits[-1] == UPSTREAM_TEXT
    assert q.edits[-1] != UNAUTH_TEXT


def test_bot_open_identity_missing_still_unauthorized():
    """تحكّم مقابل: غياب الهوية لسه «مش مسموح» (السلوك القديم محفوظ)."""
    _ctx, q, _exc = _run(h.open_conversation, "open:A", IdentityMissingClient(CONV55))
    assert q.edits and q.edits[-1] == UNAUTH_TEXT


def test_bot_open_identity_upstream_sets_no_awaiting_route(tmp_path):
    """فشل upstream ما بيفتحش توجيه برومت (مفيش عملية من غير تفويض مؤكّد)، والفشل التشغيلي
    ينتشر بعد عرض الرسالة (OHB2-SW-07)."""
    ctx = make_context(1, tmp_path, client=IdentityUpstreamClient(CONV55))
    ctx.bot = RecBot()
    q = CQ("open:A")
    with pytest.raises(h.OperationalApiFailure):
        asyncio.run(h.open_conversation(_t55_cb_update(q), ctx))
    assert ctx.bot_data["db"].get_awaiting(1) == (None, None)


# =====================================================================
# SW-04 — كل مستدعي `_authorized_conversation` بيحفظ التفصيل
# =====================================================================
# (اسم، الـ handler، بيانات الكولباك) — كلهم بيمرّوا من `_authorized_conversation`.
_CALLERS = [
    ("open", h.open_conversation, "open:A"),
    ("status", h.show_status, "status:A"),
    ("cost", h.show_cost, "cost:A"),
    ("copy", h.copy_reply, "copy:A"),
    ("txt", h.send_reply_txt, "txt:A"),
    ("watch", h.watch_conversation, "watch:A"),
    ("delete_prompt", h.delete_conversation_prompt, "delete:A"),
    ("delete_confirm", h.delete_conversation_confirm, "deleteok:A"),
    ("export", h.export_conversation, "export:A"),
    ("reply_prompt", h.reply_prompt, "reply:A"),
]


@pytest.mark.parametrize("name, handler, data", _CALLERS, ids=[c[0] for c in _CALLERS])
def test_every_caller_preserves_identity_upstream(name, handler, data):
    """لكل مستدعي: فشل الهوية upstream مايتعرضش كـ «مش مسموح» (تمييز محفوظ)."""
    ctx, q, _exc = _run(handler, data, IdentityUpstreamClient(CONV55))
    shown = q.edits[-1] if q.edits else None
    if shown is None:
        # بعض المسارات (copy/txt) بترسل رسالة بدل التعديل.
        shown = ctx.bot.messages[-1][0] if ctx.bot.messages else ""
    assert shown, f"{name}: مفيش أي رد للمستخدم"
    assert shown != UNAUTH_TEXT, f"{name}: upstream اتلبّس كرفض تفويض"
    assert "مش مسموح" not in shown, f"{name}: upstream اتلبّس كرفض تفويض"


@pytest.mark.parametrize("name, handler, data", _CALLERS, ids=[c[0] for c in _CALLERS])
def test_every_caller_identity_missing_still_denies(name, handler, data):
    """لكل مستدعي: غياب الهوية لسه رفض (مفيش تفويض من غير هوية)."""
    ctx, q, _exc = _run(handler, data, IdentityMissingClient(CONV55))
    shown = q.edits[-1] if q.edits else (ctx.bot.messages[-1][0] if ctx.bot.messages else "")
    assert shown == UNAUTH_TEXT, f"{name}: {shown!r}"


def test_identity_upstream_does_not_permit_watch(tmp_path):
    """فشل upstream مايضيفش متابعة (مفيش عملية بتتنفّذ من غير تفويض)."""
    ctx = make_context(1, tmp_path, client=IdentityUpstreamClient(CONV55))
    ctx.bot = RecBot()
    asyncio.run(h.watch_conversation(_t55_cb_update(CQ("watch:A")), ctx))
    assert ctx.bot_data["db"].list_watched() == []


def test_identity_upstream_does_not_permit_reply_prompt(tmp_path):
    ctx = make_context(1, tmp_path, client=IdentityUpstreamClient(CONV55))
    ctx.bot = RecBot()
    asyncio.run(h.reply_prompt(_t55_cb_update(CQ("reply:A")), ctx))
    assert ctx.bot_data["db"].get_awaiting(1) == (None, None)


def test_identity_upstream_does_not_permit_export_download(tmp_path):
    """فشل upstream ⇒ مفيش مستند تصدير ومفيش نداء تنزيل."""
    calls = {"export": 0}

    class ExportGuardClient(IdentityUpstreamClient):
        async def export_conversation(self, cid):
            calls["export"] += 1
            return (b"zip", "x.zip")

    ctx = make_context(1, tmp_path, client=ExportGuardClient(CONV55))
    ctx.bot = RecBot()
    asyncio.run(h.export_conversation(_t55_cb_update(CQ("export:A")), ctx))
    assert calls["export"] == 0
    assert ctx.bot.documents == []


def test_list_files_identity_upstream_not_shown_as_unauthorized(tmp_path):
    """مسار الملفات كمان: فشل الهوية upstream ⇒ رسالة upstream (مش «مش مسموح»)."""
    ctx = make_context(1, tmp_path, client=IdentityUpstreamClient(CONV55))
    ctx.bot = RecBot()
    q = CQ("files:A:0")
    asyncio.run(h.list_files(_t55_cb_update(q), ctx))
    assert q.edits and q.edits[-1] != UNAUTH_TEXT
    assert "مش مسموح" not in q.edits[-1]


# =====================================================================
# SW-04 — Mini App API: 502 upstream_error مش 403 unauthorized
# =====================================================================
OWNER = 555
OWNER_UUID = "owner-uuid-123"
CID = "c1"


class _Body(httpx.AsyncByteStream):
    def __init__(self, data: bytes):
        self._data = data

    async def __aiter__(self):
        yield self._data


class MiniApi:
    """`/users/me` بيرجّع 500 (upstream)، الشات موجود ومملوك."""

    def __init__(self, *, me_status=500, me_uuid=OWNER_UUID, conv_owner=OWNER_UUID):
        self.me_status = me_status
        self.me_uuid = me_uuid
        self.conv_owner = conv_owner

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v1/users/me":
            if self.me_status >= 400:
                return httpx.Response(self.me_status, json={"detail": "boom"})
            return httpx.Response(200, json={"id": self.me_uuid})
        if path == "/api/v1/app-conversations":
            return httpx.Response(200, json=[{"id": CID, "created_by_user_id": self.conv_owner}])
        if path.endswith("/events/search"):
            return httpx.Response(200, json={"items": []})
        if path.endswith("/files"):
            return httpx.Response(200, json=["a.txt"])
        return httpx.Response(404, json={"detail": "no"})


def _mini_config():
    return Config(
        telegram_bot_token=BOT_TOKEN,
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({OWNER}),
        owner_id=OWNER,
        mini_app_cookie_secure=False,
    )


def _mini_client(api: MiniApi) -> TestClient:
    client = OpenHandsClient(
        "https://example.test", "key", transport=httpx.MockTransport(api.handler)
    )
    tc = TestClient(build_web_app(_mini_config(), None, client=client))
    assert tc.post("/api/v1/auth", json={"initData": make_init_data(OWNER)}).status_code == 200
    return tc


def test_miniapp_identity_upstream_is_502_not_403():
    tc = _mini_client(MiniApi(me_status=500))
    r = tc.get(f"/api/v1/conversations/{CID}")
    assert r.status_code == 502, r.text
    assert r.json()["error"] == "upstream_error"


def test_miniapp_identity_missing_still_403_unauthorized():
    tc = _mini_client(MiniApi(me_status=200, me_uuid=None))
    r = tc.get(f"/api/v1/conversations/{CID}")
    assert r.status_code == 403 and r.json()["error"] == "unauthorized"


def test_miniapp_files_identity_upstream_is_502_not_403():
    tc = _mini_client(MiniApi(me_status=503))
    r = tc.get(f"/api/v1/conversations/{CID}/files")
    assert r.status_code == 502, r.text
    assert r.json()["error"] == "upstream_error"


# =====================================================================
# SW-05 — `_edit_or_send` بيمنع الفشل الصامت ويرجّع False بوضوح
# =====================================================================
class _EditQuery:
    def __init__(self, exc):
        self._exc = exc

    async def edit_message_text(self, text, **kw):
        if self._exc is not None:
            raise self._exc


class _SendBot:
    def __init__(self, send_exc=None):
        self.sent = []
        self._send_exc = send_exc

    async def send_message(self, chat_id=None, text=None, **kw):
        if self._send_exc is not None:
            raise self._send_exc
        self.sent.append(text)


def test_edit_or_send_success_returns_true_and_no_send():
    bot = _SendBot()
    assert asyncio.run(h._edit_or_send(_EditQuery(None), "نص", 1, bot)) is True
    assert bot.sent == []  # مفيش إرسال بديل عند نجاح التعديل


def test_edit_or_send_not_modified_is_success():
    bot = _SendBot()
    q = _EditQuery(RuntimeError("Message is not modified"))
    assert asyncio.run(h._edit_or_send(q, "نص", 1, bot)) is True
    assert bot.sent == []


def test_edit_or_send_too_long_fallback_success_single_send():
    bot = _SendBot()
    q = _EditQuery(RuntimeError("Message is too long"))
    assert asyncio.run(h._edit_or_send(q, "نص", 1, bot)) is True
    assert len(bot.sent) == 1  # إرسال بديل واحد بس (مفيش تكرار)


def test_edit_or_send_too_long_fallback_failure_returns_false_no_raise():
    """فشل الإرسال البديل ⇒ False، **بدون** استثناء للخارج (كان بيرمي قبل الإصلاح)."""
    bot = _SendBot(send_exc=RuntimeError("flood control exceeded"))
    q = _EditQuery(RuntimeError("Message is too long"))
    assert asyncio.run(h._edit_or_send(q, "نص", 1, bot)) is False


def test_edit_or_send_other_failure_returns_false():
    bot = _SendBot()
    q = _EditQuery(RuntimeError("message to edit not found"))
    assert asyncio.run(h._edit_or_send(q, "نص", 1, bot)) is False
    assert bot.sent == []


def test_edit_or_send_failure_logs_type_only_no_secret(caplog):
    """اللوج بيذكر نوع الاستثناء بس — مفيش نص الاستثناء (ممكن يحتوي أسرار)."""
    secret = "super-secret-token-XYZ"
    q = _EditQuery(RuntimeError(f"boom {secret}"))
    with caplog.at_level(logging.WARNING):
        assert asyncio.run(h._edit_or_send(q, "نص", 1, _SendBot())) is False
    text = " ".join(r.getMessage() for r in caplog.records)
    assert "RuntimeError" in text
    assert secret not in text


# =====================================================================
# SW-05 — كل مستدعي متأثّر بيتعامل مع False
# =====================================================================
def _status_ctx(tmp_path, client):
    ctx = make_context(1, tmp_path, client=client)
    ctx.bot = _SendBot(send_exc=RuntimeError("send down"))
    return ctx


@pytest.mark.parametrize(
    "name, handler, data",
    [("status", h.show_status, "status:A"), ("cost", h.show_cost, "cost:A")],
    ids=["status", "cost"],
)
def test_affected_caller_failed_delivery_logs_and_no_crash(name, handler, data, tmp_path, caplog):
    """فشل تعديل/إرسال ⇒ المعالج مايرميش، ويسجّل تحذير SW-05 صريح."""
    ctx = _status_ctx(tmp_path, ExchangeClient(CONV55))
    q = CQ(data)
    q.edit_message_text = _raise_edit_failure  # تعديل يفشل (رسالة قديمة)
    with caplog.at_level(logging.WARNING):
        asyncio.run(handler(_t55_cb_update(q), ctx))  # مايرميش
    text = " ".join(r.getMessage() for r in caplog.records)
    assert "تعذّر عرض" in text, f"{name}: مفيش لوج صريح لفشل التسليم"
    # مفيش ادعاء نجاح: مفيش رسالة «نجاح» اتبعتت.
    assert ctx.bot.sent == []


@pytest.mark.parametrize(
    "name, handler, data",
    [("status", h.show_status, "status:A"), ("cost", h.show_cost, "cost:A")],
    ids=["status", "cost"],
)
def test_affected_caller_success_unchanged(name, handler, data, tmp_path, caplog):
    """المسار الناجح زي ما هو: تعديل ناجح، مفيش لوج فشل، والماركب صح."""
    ctx = make_context(1, tmp_path, client=ExchangeClient(CONV55))
    ctx.bot = RecBot()
    q = CQ(data)
    with caplog.at_level(logging.WARNING):
        asyncio.run(handler(_t55_cb_update(q), ctx))
    assert q.edits, f"{name}: العرض الناجح لازم يعدّل الرسالة"
    assert q.markups and q.markups[-1] is not None  # أزرار الإجراءات موجودة
    assert not any("تعذّر عرض" in r.getMessage() for r in caplog.records)


async def _raise_edit_failure(text, **kw):
    raise RuntimeError("message to edit not found")


def test_open_authorization_denial_edit_failure_logs_no_crash(tmp_path, caplog):
    """SW-05: رسالة الرفض + فشل تعديل ⇒ لوج صريح، مفيش انهيار، مفيش توجيه جديد."""
    ctx = make_context(1, tmp_path, client=IdentityMissingClient(CONV55))
    ctx.bot = _SendBot(send_exc=RuntimeError("send down"))
    q = CQ("open:A")
    q.edit_message_text = _raise_edit_failure
    with caplog.at_level(logging.WARNING):
        asyncio.run(h.open_conversation(_t55_cb_update(q), ctx))  # مايرميش
    assert any("تعذّر عرض رسالة رفض" in r.getMessage() for r in caplog.records)
    assert ctx.bot_data["db"].get_awaiting(1) == (None, None)


def test_open_exchange_error_edit_failure_logs_no_crash(tmp_path, caplog):
    """SW-05/SW-07: خطأ آخر تبادل + فشل تعديل ⇒ لوج صريح، مفيش توجيه جديد، والفشل
    التشغيلي ينتشر بعد عرض/محاولة عرض الخطأ (مفيش إتمام كاذب)."""
    client = ExchangeClient(CONV55, exchange_error=UPSTREAM_API)
    ctx = make_context(1, tmp_path, client=client)
    ctx.bot = _SendBot(send_exc=RuntimeError("send down"))
    q = CQ("open:A")
    q.edit_message_text = _raise_edit_failure
    with caplog.at_level(logging.WARNING), pytest.raises(h.OperationalApiFailure):
        asyncio.run(h.open_conversation(_t55_cb_update(q), ctx))
    assert any("تعذّر عرض خطأ آخر تبادل" in r.getMessage() for r in caplog.records)
    assert ctx.bot_data["db"].get_awaiting(1) == (None, None)
