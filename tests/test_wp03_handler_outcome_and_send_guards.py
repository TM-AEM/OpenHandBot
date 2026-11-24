"""OHB2-WP-03 — اختبارات انحدار: نتائج المعالجات، انتشار فشل `Stage4-F1` التشغيلي،
وحراسة نداءات الإرسال الخام (`DEF-003`, `DEF-004`, `NEW-DEF-04`).

العقد المُثبَّت هنا (كل المسارات بلا شبكة حقيقية؛ عملاء/بوتات وهمية فقط):

- **`DEF-004`:** فشل التفويض **التشغيلي** (`5xx`/`429`/بلا كود) في مواقع التفويض الستة
  يحفظ دلالات fail-closed (غير مؤهّل للإقرار): مسارات العرض بتسجّل `failed_transient`،
  و`copy`/`full`/`txt` بتنتشر (`OperationalApiFailure`)؛ بينما **الرفض النهائي المتوقّع**
  (`4xx`) يرجّع عاديًّا ⇒ `explicitly_ignored` (مؤهّل).
- **`NEW-DEF-04`:** فشل تسليم تيليجرام (`TelegramError`/`TimedOut`) على نداءات الإرسال
  الخام (`send_message`/`send_copyable`/`send_long`/`send_document`) بيتسجّل
  `mark_display_failed` (`failed_transient`) بدل ما يرمي `FAILED_PERMANENT`.
- **`DEF-003`:** مسارات `outcome=None` اتقفلت: سباق `outbox_mark_sent` (`status_now == final`)،
  فشل `reposearch` عند `4xx` (الحالة تفضل قائمة)، وفشل `consume_one_shot_awaiting`.
- **`_safe_send_html`:** بيلتقط `(TelegramError, asyncio.TimeoutError)` بس، وما بيكتمش
  `asyncio.CancelledError`.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from telegram.error import BadRequest, TimedOut

import bot.handlers as h
from bot import deletion
from bot import update_outcomes as uo
from bot.errors import ApiError, OperationalApiFailure, ResponseTooLargeError
from bot.sender import TextDocumentTooLargeError

from tests.test_handlers import (
    CONV55,
    CQ,
    DetailClient,
    ExchangeClient,
    FakeBotWithDocs,
    _ctx_with,
    _t55_cb_update,
    make_context,
    make_update,
)

OWNER_ID = 1


# ============================================================================
# عملاء/بوتات وهمية
# ============================================================================
class _AuthClient:
    """عميل تفويض: `open_error` ⇒ `get_conversations` بترمي (مسار upstream)."""

    OWNER_UUID = "owner-uuid-123"

    def __init__(self, conv=CONV55, *, open_error=None):
        self._conv = conv
        self._open_error = open_error

    async def get_conversations(self, ids):
        if self._open_error is not None:
            raise self._open_error
        if not self._conv:
            return []
        return [{**self._conv, "created_by_user_id": self.OWNER_UUID}]

    async def get_current_user(self):
        return {"id": self.OWNER_UUID}


class _ExportClient(ExchangeClient):
    """عميل يدعم التصدير + فشل تسليم مبرمَج."""

    def __init__(self, conv=CONV55, *, export_error=None, blob=b"zip", exchange_error=None):
        super().__init__(conv, exchange_error=exchange_error)
        self._export_error = export_error
        self._blob = blob

    async def export_conversation(self, cid):
        if self._export_error is not None:
            raise self._export_error
        return self._blob


class FailSendBot(FakeBotWithDocs):
    """بوت يرمي `TelegramError` مبرمَجًا على `send_message` و/أو `send_document`."""

    def __init__(self, *, fail_message=None, fail_document=None):
        super().__init__()
        self._fail_message = fail_message
        self._fail_document = fail_document

    async def send_message(self, chat_id=None, text=None, **kw):
        if self._fail_message is not None:
            raise self._fail_message
        await super().send_message(chat_id, text, **kw)

    async def send_document(self, chat_id=None, document=None, **kw):
        if self._fail_document is not None:
            raise self._fail_document
        await super().send_document(chat_id, document, **kw)


def _cb(tmp_path, client, data, update_id, bot=None):
    ctx = _ctx_with(tmp_path, client)
    if bot is not None:
        ctx.bot = bot
    update = _t55_cb_update(CQ(data))
    update.update_id = update_id
    return update, ctx


def _run_cb(handler, tmp_path, client, data, update_id, bot=None):
    """يشغّل handler كولباك، ويلتقط `OperationalApiFailure` لو انتشر (SW-07)."""
    update, ctx = _cb(tmp_path, client, data, update_id, bot)
    raised = None
    try:
        asyncio.run(handler(update, ctx))
    except OperationalApiFailure as exc:
        raised = exc
    return update, ctx, raised


# ============================================================================
# 1) `_safe_send_html` — وحدة
# ============================================================================
def test_safe_send_html_returns_false_on_telegram_error():
    class _Boom:
        async def send_message(self, *a, **kw):
            raise TimedOut()

    assert asyncio.run(h._safe_send_html(_Boom(), 99, "نص")) is False


def test_safe_send_html_returns_true_on_success():
    bot = FakeBotWithDocs()
    assert asyncio.run(h._safe_send_html(bot, 99, "نص <b>")) is True
    assert bot.sent  # اتبعتت رسالة واحدة


def test_safe_send_html_propagates_cancelled_error():
    class _Cancel:
        async def send_message(self, *a, **kw):
            raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(h._safe_send_html(_Cancel(), 99, "نص"))


# ============================================================================
# 2) مصفوفة 503 (تشغيلي) مقابل 404 (رفض نهائي) على مواقع التفويض الأربعة للعرض
# ============================================================================
# (اسم، الـ handler، بيانات الكولباك) — كلهم مسارات عرض (بتسجّل فشلًا ولا تنتشر).
_DISPLAY_SITES = [
    ("watch", h.watch_conversation, "watch:A"),
    ("delete_prompt", h.delete_conversation_prompt, "delete:A"),
    ("delete_confirm", h.delete_conversation_confirm, "deleteok:A"),
    ("reply_prompt", h.reply_prompt, "reply:A"),
]


@pytest.mark.parametrize("exc", [
    pytest.param(ApiError("internal", 500), id="http500"),
    pytest.param(ApiError("service unavailable", 503), id="http503"),
    pytest.param(ApiError("too many requests", 429), id="http429"),
    pytest.param(ApiError("انتهى الوقت"), id="timeout"),
])
@pytest.mark.parametrize("name, handler, data", _DISPLAY_SITES, ids=[c[0] for c in _DISPLAY_SITES])
def test_display_site_operational_failure_is_transient(name, handler, data, exc, tmp_path):
    update, ctx, raised = _run_cb(handler, tmp_path, _AuthClient(open_error=exc), data, 8100)
    assert raised is None, f"{name}: مسار العرض المفروض ما ينتشرش"
    db = ctx.bot_data["db"]
    assert db.update_outcome(8100) == uo.FAILED_TRANSIENT, f"{name}"
    assert db.is_update_acknowledgment_eligible(8100) is False, f"{name}"


@pytest.mark.parametrize("code", [404, 403, 410])
@pytest.mark.parametrize("name, handler, data", _DISPLAY_SITES, ids=[c[0] for c in _DISPLAY_SITES])
def test_display_site_expected_rejection_is_ignored(name, handler, data, code, tmp_path):
    update, ctx, raised = _run_cb(
        handler, tmp_path, _AuthClient(open_error=ApiError(f"reject {code}", code)), data, 8101
    )
    assert raised is None, f"{name}"
    assert ctx.bot_data["db"].update_outcome(8101) == uo.EXPLICITLY_IGNORED, f"{name}"


# ============================================================================
# 3) `export_conversation` — فشل التفويض/التصدير/التسليم
# ============================================================================
def test_export_auth_operational_failure_is_transient(tmp_path):
    _update, ctx, raised = _run_cb(
        h.export_conversation, tmp_path, _AuthClient(open_error=ApiError("down", 503)),
        "export:A", 8200,
    )
    assert raised is None
    assert ctx.bot_data["db"].update_outcome(8200) == uo.FAILED_TRANSIENT


def test_export_auth_expected_rejection_is_ignored(tmp_path):
    _update, ctx, _r = _run_cb(
        h.export_conversation, tmp_path, _AuthClient(open_error=ApiError("gone", 404)),
        "export:A", 8201,
    )
    assert ctx.bot_data["db"].update_outcome(8201) == uo.EXPLICITLY_IGNORED


def test_export_operational_api_failure_is_transient_not_ambiguous(tmp_path):
    _update, ctx, _r = _run_cb(
        h.export_conversation, tmp_path, _ExportClient(export_error=ApiError("down", 503)),
        "export:A", 8202,
    )
    # كان `mark_ambiguous_external`؛ أدق دلوقتي: فشل تشغيلي ⇒ failed_transient.
    assert ctx.bot_data["db"].update_outcome(8202) == uo.FAILED_TRANSIENT


def test_export_expected_api_rejection_is_ignored(tmp_path):
    _update, ctx, _r = _run_cb(
        h.export_conversation, tmp_path, _ExportClient(export_error=ApiError("gone", 404)),
        "export:A", 8203,
    )
    assert ctx.bot_data["db"].update_outcome(8203) == uo.EXPLICITLY_IGNORED


def test_export_document_delivery_failure_is_transient(tmp_path):
    bot = FailSendBot(fail_document=TimedOut())
    _update, ctx, _r = _run_cb(
        h.export_conversation, tmp_path, _ExportClient(), "export:A", 8204, bot=bot
    )
    assert ctx.bot_data["db"].update_outcome(8204) == uo.FAILED_TRANSIENT
    assert ctx.bot_data["db"].is_update_acknowledgment_eligible(8204) is False


# ============================================================================
# 4) `send_reply_txt` — التفويض ينتشر؛ فشل تسليم المستند ⇒ display
# ============================================================================
def test_send_reply_txt_auth_operational_failure_propagates(tmp_path):
    _update, ctx, raised = _run_cb(
        h.send_reply_txt, tmp_path, _AuthClient(open_error=ApiError("down", 503)),
        "txt:A", 8300,
    )
    assert isinstance(raised, OperationalApiFailure)
    # الانتشار قبل أي تسجيل ⇒ مفيش تجاهل/نجاح كاذب (المعالج يسجّل failed_transient).
    assert ctx.bot_data["db"].update_outcome(8300) is None


def test_send_reply_txt_auth_expected_rejection_is_ignored(tmp_path):
    _update, ctx, raised = _run_cb(
        h.send_reply_txt, tmp_path, _AuthClient(open_error=ApiError("gone", 404)),
        "txt:A", 8301,
    )
    assert raised is None
    assert ctx.bot_data["db"].update_outcome(8301) == uo.EXPLICITLY_IGNORED


def test_send_reply_txt_document_delivery_failure_is_transient(tmp_path):
    bot = FailSendBot(fail_document=TimedOut())
    _update, ctx, _r = _run_cb(
        h.send_reply_txt, tmp_path, ExchangeClient(CONV55, reply="ردي"), "txt:A", 8302, bot=bot
    )
    assert ctx.bot_data["db"].update_outcome(8302) == uo.FAILED_TRANSIENT


# ============================================================================
# 5) `copy_reply` / `full_reply` — فشل تسليم الرد ⇒ display (NEW-DEF-04)
# ============================================================================
@pytest.mark.parametrize("exc", [
    pytest.param(TimedOut(), id="timedout"),
    pytest.param(BadRequest("chat not found"), id="badrequest"),
])
def test_copy_reply_delivery_failure_is_transient(exc, tmp_path):
    bot = FailSendBot(fail_message=exc)
    _update, ctx, raised = _run_cb(
        h.copy_reply, tmp_path, ExchangeClient(CONV55, reply="ردي"), "copy:A", 8400, bot=bot
    )
    assert raised is None  # فشل العرض مُلتقَط، مش منتَشر
    assert ctx.bot_data["db"].update_outcome(8400) == uo.FAILED_TRANSIENT


def test_full_reply_delivery_failure_is_transient(tmp_path):
    bot = FailSendBot(fail_message=TimedOut())
    _update, ctx, _r = _run_cb(
        h.full_reply, tmp_path, ExchangeClient(CONV55, reply="ر" * 5000), "full:A", 8401, bot=bot
    )
    assert ctx.bot_data["db"].update_outcome(8401) == uo.FAILED_TRANSIENT


def test_copy_reply_success_still_ignored(tmp_path):
    _update, ctx, _r = _run_cb(
        h.copy_reply, tmp_path, ExchangeClient(CONV55, reply="ردي"), "copy:A", 8402
    )
    assert ctx.bot_data["db"].update_outcome(8402) == uo.EXPLICITLY_IGNORED


# ============================================================================
# 6) `show_file` — فشل تسليم معاينة الملف ⇒ display (DEF-004)
# ============================================================================
def _run_show_file(tmp_path, client, paths, index, update_id, bot):
    from bot.file_cache import FileCache

    ctx = _ctx_with(tmp_path, client)
    ctx.bot = bot
    cache = FileCache()
    gen = cache.put("A", list(paths))
    ctx.bot_data["file_cache"] = cache
    update = _t55_cb_update(CQ(f"file:A:{gen}:{index}"))
    update.update_id = update_id
    asyncio.run(h.show_file(update, ctx))
    return ctx


def test_show_file_document_delivery_failure_is_transient(tmp_path):
    client = DetailClient({"id": "A", "title": "شات"}, files=["a.py"], content="hello")
    bot = FailSendBot(fail_document=TimedOut())
    ctx = _run_show_file(tmp_path, client, ["a.py"], 0, 8500, bot)
    assert ctx.bot_data["db"].update_outcome(8500) == uo.FAILED_TRANSIENT


def test_show_file_success_is_ignored(tmp_path):
    client = DetailClient({"id": "A", "title": "شات"}, files=["a.py"], content="hello")
    ctx = _run_show_file(tmp_path, client, ["a.py"], 0, 8501, FakeBotWithDocs())
    assert ctx.bot_data["db"].update_outcome(8501) == uo.EXPLICITLY_IGNORED


# ============================================================================
# 7) `reposearch` (DEF-003) — 4xx يحفظ الحالة، وفشل الاستهلاك يسجّل تجاهلًا
# ============================================================================
class _ReposClient(ExchangeClient):
    """عميل بحث مستودعات بفشل/نجاح مبرمَج."""

    def __init__(self, *, search_error=None, repos=None):
        super().__init__(CONV55)
        self._search_error = search_error
        self._repos = repos if repos is not None else [{"full_name": "owner/repo"}]

    async def search_repositories(self, query="", limit=100):
        if self._search_error is not None:
            raise self._search_error
        return list(self._repos)


class _EditMessage:
    """رسالة fake بتدعم `reply_text` و`edit_text` (زي مسار `reposearch` الحقيقي)."""

    def __init__(self):
        self.replies = []
        self.edits = []

    async def reply_text(self, text, **kw):
        self.replies.append(text)
        return self

    async def edit_text(self, text, **kw):
        self.edits.append(text)


def _text_update(text, update_id):
    msg = _EditMessage()
    msg.text = text
    return SimpleNamespace(
        update_id=update_id,
        effective_user=SimpleNamespace(id=OWNER_ID),
        effective_chat=SimpleNamespace(id=99, type="private"),
        message=msg,
        callback_query=None,
    )


def test_reposearch_4xx_preserves_state_and_records_ignored(tmp_path):
    client = _ReposClient(search_error=ApiError("forbidden", 403))
    ctx = make_context(OWNER_ID, tmp_path, client=client)
    ctx.bot_data["db"].set_awaiting(OWNER_ID, "", "reposearch")
    update = _text_update("bot", 8600)
    asyncio.run(h.handle_text(update, ctx))
    db = ctx.bot_data["db"]
    # 4xx (رفض متوقّع) ⇒ مفيش استهلاك للحالة (تقدر تعيد المحاولة) + تجاهل صريح.
    assert db.get_awaiting(OWNER_ID) == ("", "reposearch")
    assert db.update_outcome(8600) == uo.EXPLICITLY_IGNORED


def test_reposearch_consume_false_records_ignored(tmp_path, monkeypatch):
    """سباق: الحالة اتغيّرت بين القراءة والاستهلاك ⇒ مفيش `outcome=None`."""
    client = _ReposClient()
    ctx = make_context(OWNER_ID, tmp_path, client=client)
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "", "reposearch")
    monkeypatch.setattr(db, "consume_one_shot_awaiting", lambda *a, **k: False)
    update = _text_update("bot", 8601)
    asyncio.run(h.handle_text(update, ctx))
    assert db.update_outcome(8601) == uo.EXPLICITLY_IGNORED


# ============================================================================
# 8) `outbox_mark_sent` (DEF-003) — سباق CAS ⇒ تجاهل صريح (مش outcome=None)
# ============================================================================
def test_outbox_mark_sent_cas_race_records_ignored(tmp_path, monkeypatch):
    ctx = make_context(OWNER_ID, tmp_path, client=_AuthClient())
    ctx.bot = FakeBotWithDocs()
    ctx.args = ["prompt:1", "confirm"]
    db = ctx.bot_data["db"]
    oid = db.add_outbox("c1", 99, "برومت", "t")
    db.set_outbox_status(oid, "unknown", "t")
    # نحاكي خسارة السباق: كاتب تاني حسم السجل للحالة النهائية قبل كتابتنا.
    monkeypatch.setattr(db, "set_outbox_status_if_in", lambda *a, **k: False)
    monkeypatch.setattr(db, "get_outbox", lambda rid: SimpleNamespace(status="sent"))
    update = make_update(OWNER_ID, "/outbox_mark_sent prompt:1 confirm")
    update.update_id = 8700
    asyncio.run(h.outbox_mark_sent(update, ctx))
    assert db.update_outcome(8700) == uo.EXPLICITLY_IGNORED


# ============================================================================
# 9) `_send_prompt`/`_start_new_chat` (DEF-003) — `out_id==0`/`job_id==0`
#    مع تغيّر الحالة (مش سباق تزامن) ⇒ تجاهل صريح بدل `outcome=None`
# ============================================================================
def test_send_prompt_state_changed_records_ignored(tmp_path, monkeypatch):
    ctx = make_context(OWNER_ID, tmp_path, client=_AuthClient())
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "A", "reply")
    monkeypatch.setattr(db, "add_or_group_outbox", lambda *a, **k: 0)  # حالة اتغيّرت
    update = _text_update("برومت", 8800)
    asyncio.run(h.handle_text(update, ctx))
    assert db.update_outcome(8800) == uo.EXPLICITLY_IGNORED


def test_start_new_chat_state_changed_records_ignored(tmp_path, monkeypatch):
    ctx = make_context(OWNER_ID, tmp_path, client=_AuthClient())
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "owner/repo", "newchat")
    monkeypatch.setattr(db, "add_creation_job", lambda *a, **k: 0)  # حالة اتغيّرت
    update = _text_update("برومت", 8801)
    asyncio.run(h.handle_text(update, ctx))
    assert db.update_outcome(8801) == uo.EXPLICITLY_IGNORED


def test_send_prompt_concurrent_winner_keeps_winner_outcome(tmp_path, monkeypatch):
    """سباق تزامن (الفائز سجّل نتيجة دائمة) ⇒ ما نكتبش فوقها بنتيجة تانية."""
    ctx = make_context(OWNER_ID, tmp_path, client=_AuthClient())
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "A", "reply")
    db.mark_update_outcome(8802, "t", uo.DURABLE_INTENT_RECORDED)
    monkeypatch.setattr(db, "add_or_group_outbox", lambda *a, **k: 0)
    update = _text_update("برومت", 8802)
    asyncio.run(h.handle_text(update, ctx))
    assert db.update_outcome(8802) == uo.DURABLE_INTENT_RECORDED


# ============================================================================
# 10) فروع نتائج `DEF-004` الدقيقة: رفض نهائي مؤهّل مقابل غموض غير مؤهّل
#     (كانت بلا اختبار مباشر: تغيير النتيجة لـ `explicitly_ignored` ما كانش يكسر أي اختبار.)
# ============================================================================
def test_send_reply_txt_oversized_records_permanent(tmp_path, monkeypatch):
    """`TextDocumentTooLargeError` ⇒ `mark_failed_permanent` (غير مؤهّل)، مش تجاهل مؤهّل.

    الحد الأقصى لحجم ملف `.txt` رفض نهائي مؤكّد (مفيش إعادة محاولة مفيدة) ⇒ لازم يوقف
    الحدّ (fail-closed). لو اتحوّل لتجاهل مؤهّل كان هيتخطّى التحديث رغم إن العملية فشلت.
    """
    def boom(*_a, **_k):
        raise TextDocumentTooLargeError()

    monkeypatch.setattr(h, "send_text_document", boom)
    _update, ctx, raised = _run_cb(
        h.send_reply_txt, tmp_path, ExchangeClient(CONV55, reply="ردي"), "txt:A", 9100
    )
    assert raised is None
    db = ctx.bot_data["db"]
    assert db.update_outcome(9100) == uo.FAILED_PERMANENT
    assert db.is_update_acknowledgment_eligible(9100) is False


def test_export_response_too_large_records_ignored(tmp_path):
    """`ResponseTooLargeError` (رفض 4xx متوقّع) ⇒ `explicitly_ignored` مؤهّل (مش غموض).

    التصدير المحدود اللي عدّى السقف رفض نهائي معروف ⇒ مفيش إعادة محاولة، والتحديث مؤهّل
    للإقرار. الاختبار يثبّت إن المسار بيسجّل نتيجة **صريحة** (مش `None` ومش `partial_or_unknown`).
    """
    _update, ctx, _raised = _run_cb(
        h.export_conversation, tmp_path,
        _ExportClient(export_error=ResponseTooLargeError()), "export:A", 9101,
    )
    db = ctx.bot_data["db"]
    assert db.update_outcome(9101) == uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(9101) is True


def test_delete_confirm_remote_failed_records_ambiguous(tmp_path, monkeypatch):
    """فشل الحذف البعيد المؤكّد (`STATUS_FAILED`) ⇒ `PARTIAL_OR_UNKNOWN` (غير مؤهّل).

    الحذف البعيد فشل مؤكّد لكن مفيش يأس (الشات لسه موجود، محتاج إعادة محاولة) ⇒ نتيجة
    غامضة fail-closed، مش نجاح ومش تجاهل مؤهّل.
    """
    async def fake_remote(_client, _db, cid):
        return deletion.DeletionResult(
            deletion.STATUS_FAILED, deletion.FAILED_MESSAGE, cid, http_status=400
        )

    monkeypatch.setattr(deletion, "delete_conversation_remote", fake_remote)
    _update, ctx, _raised = _run_cb(
        h.delete_conversation_confirm, tmp_path, _AuthClient(), "deleteok:A", 9102
    )
    db = ctx.bot_data["db"]
    assert db.update_outcome(9102) == uo.PARTIAL_OR_UNKNOWN
    assert db.is_update_acknowledgment_eligible(9102) is False



# ============================================================================
# 11) WP03-AUD-01/02: required display failure must not become ignored
# ============================================================================
class _FailingEditQ(CQ):
    """كولباك fake بيفشل في تعديل الرسالة (فشل عرض تيليجرام مبرمَج)."""

    async def edit_message_text(self, text, **kw):
        raise TimedOut()


_REPLY_HANDLERS = [
    pytest.param(h.copy_reply, "copy:A", id="copy_reply"),
    pytest.param(h.full_reply, "full:A", id="full_reply"),
    pytest.param(h.send_reply_txt, "txt:A", id="send_reply_txt"),
]


def _run_reply_handler(handler, tmp_path, client, data, update_id, *, fail_display=False):
    ctx = _ctx_with(tmp_path, client)
    if fail_display:
        ctx.bot = FailSendBot(fail_message=TimedOut())
    update = _t55_cb_update(CQ(data))
    update.update_id = update_id
    asyncio.run(handler(update, ctx))
    return ctx


@pytest.mark.parametrize("handler, data", _REPLY_HANDLERS)
def test_expected_rejection_display_success_keeps_ignored(handler, data, tmp_path):
    ctx = _run_reply_handler(
        handler, tmp_path, _AuthClient(open_error=ApiError("gone", 404)), data, 9200
    )
    db = ctx.bot_data["db"]
    assert db.update_outcome(9200) == uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(9200) is True


@pytest.mark.parametrize("handler, data", _REPLY_HANDLERS)
def test_expected_rejection_display_failure_is_transient(handler, data, tmp_path):
    ctx = _run_reply_handler(
        handler,
        tmp_path,
        _AuthClient(open_error=ApiError("gone", 404)),
        data,
        9201,
        fail_display=True,
    )
    db = ctx.bot_data["db"]
    assert db.update_outcome(9201) == uo.FAILED_TRANSIENT
    assert db.is_update_acknowledgment_eligible(9201) is False


@pytest.mark.parametrize("handler, data", _REPLY_HANDLERS)
def test_exchange_rejection_display_success_keeps_ignored(handler, data, tmp_path):
    ctx = _run_reply_handler(
        handler,
        tmp_path,
        ExchangeClient(CONV55, exchange_error=ApiError("gone", 404)),
        data,
        9202,
    )
    db = ctx.bot_data["db"]
    assert db.update_outcome(9202) == uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(9202) is True


@pytest.mark.parametrize("handler, data", _REPLY_HANDLERS)
def test_exchange_rejection_display_failure_is_transient(handler, data, tmp_path):
    ctx = _run_reply_handler(
        handler,
        tmp_path,
        ExchangeClient(CONV55, exchange_error=ApiError("gone", 404)),
        data,
        9203,
        fail_display=True,
    )
    db = ctx.bot_data["db"]
    assert db.update_outcome(9203) == uo.FAILED_TRANSIENT
    assert db.is_update_acknowledgment_eligible(9203) is False


@pytest.mark.parametrize("handler, data", _REPLY_HANDLERS)
def test_no_reply_display_success_keeps_ignored(handler, data, tmp_path):
    ctx = _run_reply_handler(
        handler, tmp_path, ExchangeClient(CONV55, reply=None), data, 9204
    )
    db = ctx.bot_data["db"]
    assert db.update_outcome(9204) == uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(9204) is True


@pytest.mark.parametrize("handler, data", _REPLY_HANDLERS)
def test_no_reply_display_failure_is_transient(handler, data, tmp_path):
    ctx = _run_reply_handler(
        handler,
        tmp_path,
        ExchangeClient(CONV55, reply=None),
        data,
        9205,
        fail_display=True,
    )
    db = ctx.bot_data["db"]
    assert db.update_outcome(9205) == uo.FAILED_TRANSIENT
    assert db.is_update_acknowledgment_eligible(9205) is False


def _run_open_handler(tmp_path, client, q, update_id):
    ctx = _ctx_with(tmp_path, client)
    update = _t55_cb_update(q)
    update.update_id = update_id
    asyncio.run(h.open_conversation(update, ctx))
    return ctx


def test_open_rejection_display_success_keeps_ignored(tmp_path):
    ctx = _run_open_handler(
        tmp_path, _AuthClient(open_error=ApiError("gone", 404)), CQ("open:A"), 9210
    )
    db = ctx.bot_data["db"]
    assert db.update_outcome(9210) == uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(9210) is True


def test_open_rejection_display_failure_is_transient(tmp_path):
    ctx = _run_open_handler(
        tmp_path,
        _AuthClient(open_error=ApiError("gone", 404)),
        _FailingEditQ("open:A"),
        9211,
    )
    db = ctx.bot_data["db"]
    assert db.update_outcome(9211) == uo.FAILED_TRANSIENT
    assert db.is_update_acknowledgment_eligible(9211) is False


def test_open_exchange_error_display_success_keeps_ignored(tmp_path):
    ctx = _run_open_handler(
        tmp_path,
        ExchangeClient(CONV55, exchange_error=ApiError("gone", 404)),
        CQ("open:A"),
        9212,
    )
    db = ctx.bot_data["db"]
    assert db.update_outcome(9212) == uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(9212) is True


def test_open_exchange_error_display_failure_is_transient(tmp_path):
    ctx = _run_open_handler(
        tmp_path,
        ExchangeClient(CONV55, exchange_error=ApiError("gone", 404)),
        _FailingEditQ("open:A"),
        9213,
    )
    db = ctx.bot_data["db"]
    assert db.update_outcome(9213) == uo.FAILED_TRANSIENT
    assert db.is_update_acknowledgment_eligible(9213) is False


def test_open_no_reply_display_success_keeps_ignored(tmp_path):
    ctx = _run_open_handler(
        tmp_path, ExchangeClient(CONV55, reply=None), CQ("open:A"), 9214
    )
    db = ctx.bot_data["db"]
    assert db.update_outcome(9214) == uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(9214) is True
    assert db.get_awaiting(1) == ("A", "route")


def test_open_no_reply_display_failure_is_transient(tmp_path):
    ctx = _run_open_handler(
        tmp_path, ExchangeClient(CONV55, reply=None), _FailingEditQ("open:A"), 9215
    )
    db = ctx.bot_data["db"]
    assert db.update_outcome(9215) == uo.FAILED_TRANSIENT
    assert db.is_update_acknowledgment_eligible(9215) is False
    assert db.get_awaiting(1) == (None, None)


class _FailingMessage:
    """رسالة fake بترفض الإرسال (فشل عرض مسار `/chat` بدون كولباك)."""

    async def reply_text(self, text, **kw):
        raise TimedOut()


def _run_chat_command(tmp_path, client, update_id, *, fail_display=False):
    ctx = _ctx_with(tmp_path, client)
    ctx.bot_data["db"].set_last_accessed_conversation(OWNER_ID, "A")
    update = make_update(OWNER_ID)
    if fail_display:
        update.message = _FailingMessage()
    update.update_id = update_id
    asyncio.run(h.chat(update, ctx))
    return ctx


def test_chat_rejection_display_success_keeps_ignored(tmp_path):
    ctx = _run_chat_command(
        tmp_path, _AuthClient(open_error=ApiError("gone", 404)), 9220
    )
    db = ctx.bot_data["db"]
    assert db.update_outcome(9220) == uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(9220) is True


def test_chat_rejection_display_failure_is_transient(tmp_path):
    ctx = _run_chat_command(
        tmp_path,
        _AuthClient(open_error=ApiError("gone", 404)),
        9221,
        fail_display=True,
    )
    db = ctx.bot_data["db"]
    assert db.update_outcome(9221) == uo.FAILED_TRANSIENT
    assert db.is_update_acknowledgment_eligible(9221) is False


def test_chat_no_reply_display_success_keeps_ignored(tmp_path):
    ctx = _run_chat_command(
        tmp_path, ExchangeClient(CONV55, reply=None), 9222
    )
    db = ctx.bot_data["db"]
    assert db.update_outcome(9222) == uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(9222) is True
    assert db.get_awaiting(OWNER_ID) == ("A", "route")


def test_chat_no_reply_display_failure_is_transient(tmp_path):
    ctx = _run_chat_command(
        tmp_path, ExchangeClient(CONV55, reply=None), 9223, fail_display=True
    )
    db = ctx.bot_data["db"]
    assert db.update_outcome(9223) == uo.FAILED_TRANSIENT
    assert db.is_update_acknowledgment_eligible(9223) is False
    assert db.get_awaiting(OWNER_ID) == (None, None)
