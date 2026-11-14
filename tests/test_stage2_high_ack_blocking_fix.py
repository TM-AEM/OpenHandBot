"""OHB2-STAGE2-HIGH-ACK-BLOCKING-FIX — اختبارات انحدار لعيب حجب الإقرار (HIGH).

العيب المؤكَّد (مراجعة عدائية مستقلة على `907b20d`): `open_conversation`/`copy_reply`/
`full_reply` كانوا يرجعوا عاديًّا على مسارات **الرفض النهائي** (شات مش موجود/متشاهد/غير
مصرّح) + مسار **فشل عرض** فتح الشات، من غير ما يسجّلوا أي **نتيجة دائمة** ⇒
`collect_outcomes` تصنّفها `partial_or_unknown` (غير مؤهّل) ⇒ `commit_batch_outcomes`
ترفض الدفعة ⇒ الحدّ والـ offset يفضلوا ثابتين ⇒ تيليجرام يعيد تسليم نفس التحديث للأبد
ويحجب كل اللي بعده.

الإصلاح (أصغر تغيير آمن):
- **رفض نهائي مؤكّد** (NOT_FOUND/DELETED/UNAUTHORIZED، أو `conv is None` المتوقّع) ⇒
  `mark_explicitly_ignored` (نتيجة صريحة **مؤهّلة**، نفس دلالات §22.3 للرد/التنقّل/الرفض).
- **فشل عرض** المحتوى اللي المستخدم طلبه (فشل تعديل/إرسال تيليجرام) ⇒ `mark_display_failed`
  (`FAILED_TRANSIENT`، **غير مؤهّل** — فشل عابر قابل لإعادة المحاولة، مش نجاح ومش تجاهل).
- **الفشل التشغيلي upstream** (5xx/429/بلا كود) لسه **ينتشر** (SW-07) ⇒ مستحيل يتحوّل
  لتجاهل كاذب.

مفيش شبكة: قاعدة SQLite معزولة، عميل/بوت وهميين، نداء مباشر للـ handler + حلقة الاستطلاع
الحقيقية (`TelegramPoller`) في اختبارات الـ end-to-end.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from telegram import Update
from telegram.error import BadRequest
from telegram.ext import TypeHandler

import bot.handlers as h
from bot import update_outcomes as uo
from bot.errors import ApiError, OperationalApiFailure
from bot.polling import TelegramPoller

from tests.test_handlers import _cb_update, _ctx_with
from tests.test_stage2_custom_polling import _callback, _text, _with_started_app
from tests.test_duplicate_update_dispatch import OWNER_ID

CONV = {
    "id": "c1",
    "title": "شات",
    "execution_status": "finished",
    "selected_repository": "o/r",
}


class _AuthClient:
    """عميل وهمي بيتحكّم في نتيجة التفويض:

    - `conv=None` ⇒ `get_conversations` بترجّع `[]` ⇒ `NOT_FOUND`.
    - `owner="someone-else"` ⇒ `created_by_user_id` مش مطابق لهوية `/users/me` ⇒ `UNAUTHORIZED`.
    - الشات المتشاهد بيتحدّد بالـ tombstone في القاعدة ⇒ `DELETED`.
    - `open_error` ⇒ `ApiError` من `get_conversations` (مسار upstream).
    """

    OWNER_UUID = "owner-uuid-123"

    def __init__(self, conv=CONV, *, owner=None, open_error=None, reply="ردي"):
        self._conv = conv
        self._owner = owner or self.OWNER_UUID
        self._open_error = open_error
        self._reply = reply

    async def get_conversations(self, ids):
        if self._open_error is not None:
            raise self._open_error
        if not self._conv:
            return []
        return [
            {
                **self._conv,
                "created_by_user_id": self._conv.get("created_by_user_id", self._owner),
            }
        ]

    async def get_current_user(self):
        return {"id": self.OWNER_UUID}

    async def get_last_exchange(self, cid):
        return ("برومتي", self._reply)


def _update(update_id, data):
    update = _cb_update(OWNER_ID, data)
    update.update_id = update_id
    return update


class _FailingEditQuery:
    """كولباك يرمي `BadRequest` عند التعديل ⇒ `_edit_or_send` يرجّع False."""

    def __init__(self, data):
        self.data = data
        self.edits = []
        self.answered = 0
        self.message = SimpleNamespace(chat_id=99)

    async def answer(self):
        self.answered += 1

    async def edit_message_text(self, text, **kw):
        raise BadRequest("message to edit not found")


def _update_with_failing_edit(update_id, data):
    return SimpleNamespace(
        update_id=update_id,
        effective_user=SimpleNamespace(id=OWNER_ID),
        effective_chat=SimpleNamespace(id=99, type="private"),
        message=None,
        callback_query=_FailingEditQuery(data),
    )


# ============================================================================
# 1) open_conversation — الرفض النهائي (مش موجود/متشاهد/غير مصرّح)
# ============================================================================
def test_open_missing_records_eligible_ignored(tmp_path):
    ctx = _ctx_with(tmp_path, _AuthClient(conv=None))
    asyncio.run(h.open_conversation(_update(1001, "open:c1"), ctx))
    db = ctx.bot_data["db"]
    assert db.update_outcome(1001) == uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(1001) is True
    db.close()


def test_open_deleted_records_eligible_ignored(tmp_path):
    ctx = _ctx_with(tmp_path, _AuthClient())
    db = ctx.bot_data["db"]
    db.delete_conversation("c1", "2026-01-01T00:00:00+00:00")  # tombstone ⇒ DELETED
    asyncio.run(h.open_conversation(_update(1002, "open:c1"), ctx))
    assert db.update_outcome(1002) == uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(1002) is True
    db.close()


def test_open_unauthorized_records_eligible_ignored(tmp_path):
    ctx = _ctx_with(tmp_path, _AuthClient(owner="someone-else"))
    asyncio.run(h.open_conversation(_update(1003, "open:c1"), ctx))
    db = ctx.bot_data["db"]
    assert db.update_outcome(1003) == uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(1003) is True
    db.close()


# ============================================================================
# 2) open_conversation — فشل عرض المحتوى (فشل تسليم تيليجرام)
# ============================================================================
def test_open_display_failure_records_transient_not_ignored(tmp_path):
    """فشل عرض فتح الشات ⇒ `FAILED_TRANSIENT` (غير مؤهّل) — **مش** نجاح ومش تجاهل."""
    ctx = _ctx_with(tmp_path, _AuthClient())
    asyncio.run(h.open_conversation(_update_with_failing_edit(1004, "open:c1"), ctx))
    db = ctx.bot_data["db"]
    assert db.update_outcome(1004) == uo.FAILED_TRANSIENT
    assert db.is_update_acknowledgment_eligible(1004) is False
    assert db.update_failure(1004) == uo.FAILED_TRANSIENT
    # مفيش توجيه مفعّل (الفشل مايسبش حالة نصّية).
    assert db.get_awaiting(OWNER_ID) == (None, None)
    db.close()


def test_open_display_failure_does_not_become_success(tmp_path):
    """فشل العرض مش «نجاح صامت» ولا «تجاهل»: النتيجة غير مؤهّلة (fail-closed)."""
    ctx = _ctx_with(tmp_path, _AuthClient())
    asyncio.run(h.open_conversation(_update_with_failing_edit(1005, "open:c1"), ctx))
    db = ctx.bot_data["db"]
    assert db.update_outcome(1005) not in (uo.EXPLICITLY_IGNORED, uo.DURABLE_COMPLETED)
    assert db.is_update_acknowledgment_eligible(1005) is False
    db.close()


# ============================================================================
# 3) copy_reply — الرفض النهائي
# ============================================================================
@pytest.mark.parametrize("deleted", [False, True], ids=["missing", "deleted"])
def test_copy_missing_or_deleted_records_eligible_ignored(tmp_path, deleted):
    ctx = _ctx_with(tmp_path, _AuthClient(conv=None if not deleted else CONV))
    db = ctx.bot_data["db"]
    if deleted:
        db.delete_conversation("c1", "2026-01-01T00:00:00+00:00")
    asyncio.run(h.copy_reply(_update(1100, "copy:c1"), ctx))
    assert db.update_outcome(1100) == uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(1100) is True
    db.close()


def test_copy_unauthorized_records_eligible_ignored(tmp_path):
    ctx = _ctx_with(tmp_path, _AuthClient(owner="someone-else"))
    asyncio.run(h.copy_reply(_update(1101, "copy:c1"), ctx))
    db = ctx.bot_data["db"]
    assert db.update_outcome(1101) == uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(1101) is True
    db.close()


# ============================================================================
# 4) full_reply — الرفض النهائي
# ============================================================================
@pytest.mark.parametrize("deleted", [False, True], ids=["missing", "deleted"])
def test_full_missing_or_deleted_records_eligible_ignored(tmp_path, deleted):
    ctx = _ctx_with(tmp_path, _AuthClient(conv=None if not deleted else CONV))
    db = ctx.bot_data["db"]
    if deleted:
        db.delete_conversation("c1", "2026-01-01T00:00:00+00:00")
    asyncio.run(h.full_reply(_update(1200, "full:c1"), ctx))
    assert db.update_outcome(1200) == uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(1200) is True
    db.close()


def test_full_unauthorized_records_eligible_ignored(tmp_path):
    ctx = _ctx_with(tmp_path, _AuthClient(owner="someone-else"))
    asyncio.run(h.full_reply(_update(1201, "full:c1"), ctx))
    db = ctx.bot_data["db"]
    assert db.update_outcome(1201) == uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(1201) is True
    db.close()


# ============================================================================
# 5) المسارات الناجحة القائمة — لازم تفضل مؤهّلة (مفيش انحدار)
# ============================================================================
def test_open_success_still_eligible(tmp_path):
    ctx = _ctx_with(tmp_path, _AuthClient())
    asyncio.run(h.open_conversation(_update(1301, "open:c1"), ctx))
    db = ctx.bot_data["db"]
    assert db.update_outcome(1301) == uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(1301) is True
    db.close()


def test_copy_success_still_eligible(tmp_path):
    ctx = _ctx_with(tmp_path, _AuthClient(reply="ردي"))
    asyncio.run(h.copy_reply(_update(1302, "copy:c1"), ctx))
    db = ctx.bot_data["db"]
    assert db.update_outcome(1302) == uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(1302) is True
    db.close()


def test_full_success_still_eligible(tmp_path):
    ctx = _ctx_with(tmp_path, _AuthClient(reply="ردي"))
    asyncio.run(h.full_reply(_update(1303, "full:c1"), ctx))
    db = ctx.bot_data["db"]
    assert db.update_outcome(1303) == uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(1303) is True
    db.close()


def test_copy_no_reply_still_eligible(tmp_path):
    ctx = _ctx_with(tmp_path, _AuthClient(reply=None))
    asyncio.run(h.copy_reply(_update(1304, "copy:c1"), ctx))
    db = ctx.bot_data["db"]
    assert db.update_outcome(1304) == uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(1304) is True
    db.close()


# ============================================================================
# 6) الفشل التشغيلي upstream — لسه ينتشر، ومش يتحوّل لتجاهل كاذب
# ============================================================================
@pytest.mark.parametrize(
    "handler,data",
    [
        (h.open_conversation, "open:c1"),
        (h.copy_reply, "copy:c1"),
        (h.full_reply, "full:c1"),
    ],
    ids=["open", "copy", "full"],
)
def test_operational_upstream_error_propagates_not_ignored(tmp_path, handler, data):
    ctx = _ctx_with(tmp_path, _AuthClient(open_error=ApiError("server", 500)))
    with pytest.raises(OperationalApiFailure):
        asyncio.run(handler(_update(1400, data), ctx))
    db = ctx.bot_data["db"]
    # لسه بلا نتيجة مؤهّلة (الفشل التشغيلي مايتسجّلش «تجاهل» ولا «نجاح»).
    assert db.update_outcome(1400) != uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(1400) is False
    db.close()


@pytest.mark.parametrize(
    "handler,data",
    [
        (h.open_conversation, "open:c1"),
        (h.copy_reply, "copy:c1"),
        (h.full_reply, "full:c1"),
    ],
    ids=["open", "copy", "full"],
)
def test_expected_4xx_rejection_records_ignored(tmp_path, handler, data):
    """رفض 4xx متوقّع (404) ⇒ نتيجة صريحة مؤهّلة (مفيش رفع)."""
    ctx = _ctx_with(tmp_path, _AuthClient(open_error=ApiError("reject 404", 404)))
    asyncio.run(handler(_update(1401, data), ctx))
    db = ctx.bot_data["db"]
    assert db.update_outcome(1401) == uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(1401) is True
    db.close()


# ============================================================================
# 7) إعادة التسليم — مفيش أثر جانبي مكرّر (الديدَب يمنع التنفيذ التاني)
# ============================================================================
def test_terminal_rejection_marks_update_processed(tmp_path):
    """بعد تسجيل `explicitly_ignored`، التحديث «معالَج» ⇒ إعادة تسليمه تُتخطّى (ديدَب)."""
    ctx = _ctx_with(tmp_path, _AuthClient(conv=None))
    db = ctx.bot_data["db"]
    asyncio.run(h.copy_reply(_update(1500, "copy:c1"), ctx))
    assert db.update_outcome(1500) == uo.EXPLICITLY_IGNORED
    assert db.update_is_processed(1500) is True
    db.close()


# ============================================================================
# 8) end-to-end عبر حلقة الاستطلاع الحقيقية (TelegramPoller)
# ============================================================================
def test_e2e_terminal_rejection_advances_boundary_and_offset(tmp_path, monkeypatch):
    """التحديث الحاجب (copy لشات مش موجود) ⇒ نتيجة دائمة ⇒ الحدّ والـ offset يتقدّموا،

    والتحديث اللي بعده يتعالج.
    """
    async def run(app, install_bot):
        app.bot_data["client"] = _AuthClient(conv=None)
        db = app.bot_data["db"]
        poller = TelegramPoller(app, db)

        blocked = await poller.process_updates([_callback(app, 2001, "copy:c1")])
        assert blocked == 2001
        assert db.update_outcome(2001) == uo.EXPLICITLY_IGNORED
        assert db.is_update_acknowledgment_eligible(2001) is True
        assert poller._next_offset == 2002  # الـ offset اتقدّم

        nxt = await poller.process_updates([_callback(app, 2002, "copy:c1")])
        assert nxt == 2002
        assert poller._next_offset == 2003

    asyncio.run(_with_started_app(tmp_path, monkeypatch, run))


def test_e2e_no_outcome_would_stall_boundary(tmp_path, monkeypatch):
    """إثبات السبب (mutation-style): لو الـ handler رجع **بلا نتيجة**، الحدّ/الـ offset

    يفضلوا ثابتين — وده بالظبط اللي كان العيب بيعمله قبل الإصلاح.
    """
    async def run(app, install_bot):
        app.bot_data["client"] = _AuthClient(conv=None)
        db = app.bot_data["db"]

        # نستبدل handler النسخ بـ no-op بيرجع بلا أي نتيجة (يحاكي العيب القديم).
        group0 = app.handlers[0]
        idx = next(
            i for i, hh in enumerate(group0)
            if getattr(hh, "callback", None) is h.copy_reply
        )

        async def noop(update, context):
            return

        group0[idx] = TypeHandler(Update, noop, strict=False)

        poller = TelegramPoller(app, db)
        boundary = await poller.process_updates([_callback(app, 2101, "copy:c1")])
        assert boundary is None
        assert poller._next_offset is None
        # مفيش نتيجة مؤهّلة ⇒ الحلقة تسجّل `partial_or_unknown` (غير مؤهّل) ⇒ حجب fail-closed.
        assert db.update_outcome(2101) == uo.PARTIAL_OR_UNKNOWN
        assert db.is_update_acknowledgment_eligible(2101) is False

    asyncio.run(_with_started_app(tmp_path, monkeypatch, run))


def test_e2e_unresolved_earlier_update_still_blocks_boundary(tmp_path, monkeypatch):
    """تحديث غير مؤهّل سابق لسه يحجز الحدّ (البادئة المتّصلة المؤهّلة — §30.3).

    أول تحديث نصّي + handler بيرمي ⇒ `failed_permanent` (غير مؤهّل)؛ التاني رفض نهائي
    (مؤهّل) ⇒ الحدّ يفضل None والـ offset مايتقدّمش (مفيش تجاوز فوق غير المؤهّل).
    """
    async def run(app, install_bot):
        app.bot_data["client"] = _AuthClient(conv=None)
        db = app.bot_data["db"]

        async def boom(update, context):
            raise RuntimeError("boom")

        group0 = app.handlers[0]
        idx = next(
            i for i, hh in enumerate(group0)
            if getattr(hh, "callback", None) is h.handle_text
        )
        group0[idx] = TypeHandler(Update, boom, strict=False)

        poller = TelegramPoller(app, db)
        boundary = await poller.process_updates(
            [_text(app, 2201), _callback(app, 2202, "copy:c1")]
        )
        assert boundary is None  # أول تحديث غير مؤهّل ⇒ مفيش إقرار
        assert poller._next_offset is None
        assert db.update_outcome(2201) == uo.FAILED_PERMANENT
        # التاني اتعالج وسجّل نتيجة مؤهّلة، بس الحدّ اتوقف عند الأول (مفيش تجاوز).
        assert db.update_outcome(2202) == uo.EXPLICITLY_IGNORED

    asyncio.run(_with_started_app(tmp_path, monkeypatch, run))
