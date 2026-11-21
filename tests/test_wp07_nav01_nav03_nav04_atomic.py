"""OHB2-WP-07 (NEW-DEF-03) — اختبارات انحدار على **ذرّية مسح حالة الانتظار مع كتابة نتيجة
التحديث** في معالجَي القراءة/التنقّل المتبقّيين:

- NAV-01 `handlers.start`
- NAV-03 `handlers.list_conversations`
- NAV-04 `handlers.list_watches`

العيب المشترك: `clear_awaiting` (commit مستقل في أول المعالج) ثم `mark_explicitly_ignored`
(commit تانٍ في نهاية الفرع). عطل بينهم يسيب حالة ممسوحة **بلا** نتيجة دائمة. والأسوأ:
المسح كان بيحصل **قبل** نداءات ممكن ترفع (`reply_text` / بحث API / `list_watched` / العرض)
⇒ فشل تشغيلي بعد مسح مسبق = مسح بلا نتيجة.

**قاعدة الترتيب المطبَّقة:** الاستدعاء الذرّي بعد **كل** عملية لازم تنجح قبل تأهيل التحديث،
وعلى كل فرع خروج. `list_conversations` فيه **خمسة** مخارج، كل واحد ليه تعامل مختلف:
مسح+`explicitly_ignored` للنجاح/الرفض المتوقّع، ومسح+**نتيجة فشل** لفرع فشل القاعدة.
"""
from __future__ import annotations

import asyncio

import pytest

import bot.handlers as h
from bot import update_outcomes as uo
from bot.db import Database
from bot.errors import ApiError

from tests.test_handlers import (
    CQ,
    F1ListClient,
    FakeClient,
    _t55_cb_update,
    make_context,
    make_update,
)

OWNER_ID = 1


def _cb(data, update_id, user_id=OWNER_ID):
    update = _t55_cb_update(CQ(data), user_id=user_id)
    update.update_id = update_id
    return update


# ============================================================================
# NAV-01 — start
# ============================================================================
def test_start_clears_state_and_records_outcome_atomically(tmp_path):
    """النجاح ⇒ الحالة اتمسحت والنتيجة `explicitly_ignored` (مؤهّلة) في معاملة واحدة."""
    ctx = make_context(OWNER_ID, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    update = make_update(OWNER_ID, "/start")
    update.update_id = 7401
    asyncio.run(h.start(update, ctx))

    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.update_outcome(7401) == uo.EXPLICITLY_IGNORED
    assert uo.is_ack_eligible(db.update_outcome(7401)) is True
    db.close()


def test_start_rollback_leaves_state_and_outcome_untouched(tmp_path, monkeypatch):
    """فشل كتابة النتيجة ⇒ **مفيش** مسح للحالة (الاتنين يتراجعوا)."""
    ctx = make_context(OWNER_ID, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    def _boom(*_a, **_k):
        raise RuntimeError("outcome write failed")

    monkeypatch.setattr(db, "mark_update_outcome", _boom)
    update = make_update(OWNER_ID, "/start")
    update.update_id = 7402
    with pytest.raises(RuntimeError):
        asyncio.run(h.start(update, ctx))

    assert db.get_awaiting(OWNER_ID) == ("conv-A", "route"), "مسح حالة بلا نتيجة!"
    assert db.update_outcome(7402) is None
    db.close()


def test_start_send_failure_does_not_qualify_update(tmp_path):
    """فشل الإرسال (reply_text) ⇒ **مفيش** مسح ولا نتيجة مؤهّلة.

    ده حارس الترتيب: `reply_text` الخام ممكن يرفع. لو المسح+النتيجة حصلوا قبله كان
    الفشل يتحوّل لنجاح مؤهّل (fail-open للحدّ).
    """
    ctx = make_context(OWNER_ID, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    update = make_update(OWNER_ID, "/start")
    update.update_id = 7403

    async def _fail(*_a, **_k):
        raise RuntimeError("telegram send failed")

    update.message.reply_text = _fail
    with pytest.raises(RuntimeError):
        asyncio.run(h.start(update, ctx))

    assert db.get_awaiting(OWNER_ID) == ("conv-A", "route"), "الحالة اتمسحت قبل الفشل!"
    assert db.update_outcome(7403) is None
    db.close()


def test_start_update_id_none_clears_without_outcome(tmp_path):
    """`update_id=None` ⇒ مسح بس، ومفيش صف نتيجة (سلوك قديم)."""
    ctx = make_context(OWNER_ID, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    asyncio.run(h.start(make_update(OWNER_ID, "/start"), ctx))

    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.count_processed_updates() == 0
    db.close()


def test_start_unauthorized_clears_nothing(tmp_path):
    """غير مصرّح ⇒ `_guard` يرجّع False قبل أي مسح؛ النتيجة من مسار التفويض."""
    ctx = make_context(OWNER_ID, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(999, "conv-x", "reply")

    update = make_update(999, "/start")
    update.update_id = 7404
    asyncio.run(h.start(update, ctx))

    assert db.get_awaiting(999) == ("conv-x", "reply")
    assert db.update_outcome(7404) == uo.EXPLICITLY_IGNORED
    db.close()


# ============================================================================
# NAV-04 — list_watches
# ============================================================================
def test_list_watches_empty_clears_and_records_atomically(tmp_path):
    """فرع «مفيش متابعات» ⇒ مسح + `explicitly_ignored` معًا."""
    ctx = make_context(OWNER_ID, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    asyncio.run(h.list_watches(_cb("watched:0", 7501), ctx))

    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.update_outcome(7501) == uo.EXPLICITLY_IGNORED
    assert uo.is_ack_eligible(db.update_outcome(7501)) is True
    db.close()


def test_list_watches_items_clears_and_records_atomically(tmp_path):
    """فرع عرض القايمة ⇒ مسح + `explicitly_ignored` معًا."""
    ctx = make_context(OWNER_ID, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")
    db.add_watched("c1", "شات 1", chat_id=1)

    asyncio.run(h.list_watches(_cb("watched:0", 7502), ctx))

    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.update_outcome(7502) == uo.EXPLICITLY_IGNORED
    db.close()


def test_list_watches_rollback_leaves_state_untouched(tmp_path, monkeypatch):
    """فشل كتابة النتيجة ⇒ **مفيش** مسح للحالة."""
    ctx = make_context(OWNER_ID, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    def _boom(*_a, **_k):
        raise RuntimeError("outcome write failed")

    monkeypatch.setattr(db, "mark_update_outcome", _boom)
    with pytest.raises(RuntimeError):
        asyncio.run(h.list_watches(_cb("watched:0", 7503), ctx))

    assert db.get_awaiting(OWNER_ID) == ("conv-A", "route"), "مسح حالة بلا نتيجة!"
    assert db.update_outcome(7503) is None
    db.close()


def test_list_watches_db_read_failure_does_not_clear_state(tmp_path):
    """فشل `list_watched()` ⇒ الحالة **مااتمسحتش** (المسح بقى بعد القراءة، مش قبلها)."""
    ctx = make_context(OWNER_ID, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    def _boom(*_a, **_k):
        raise RuntimeError("db down")

    db.list_watched = _boom
    with pytest.raises(RuntimeError):
        asyncio.run(h.list_watches(_cb("watched:0", 7504), ctx))

    assert db.get_awaiting(OWNER_ID) == ("conv-A", "route"), "الحالة اتمسحت قبل فشل القراءة!"
    assert db.update_outcome(7504) is None
    db.close()


def test_list_watches_update_id_none_clears_without_outcome(tmp_path):
    """`update_id=None` ⇒ مسح بس."""
    ctx = make_context(OWNER_ID, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    asyncio.run(h.list_watches(_t55_cb_update(CQ("watched:0")), ctx))

    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.count_processed_updates() == 0
    db.close()


# ============================================================================
# NAV-03 — list_conversations: كل المخارج الخمسة
# ============================================================================
def test_nav03_exit_success_display(tmp_path):
    """مخرج 5 (العرض العادي) ⇒ مسح + `explicitly_ignored`."""
    client = FakeClient([{"id": "c1", "title": "شات", "execution_status": "running"}])
    ctx = make_context(OWNER_ID, tmp_path, client=client)
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    update = _cb("list:0", 7601)
    asyncio.run(h.list_conversations(update, ctx))

    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.update_outcome(7601) == uo.EXPLICITLY_IGNORED
    assert uo.is_ack_eligible(db.update_outcome(7601)) is True
    db.close()


def test_nav03_exit_empty_list(tmp_path):
    """مخرج 4 (قايمة فاضية) ⇒ مسح + `explicitly_ignored`."""
    ctx = make_context(OWNER_ID, tmp_path, client=FakeClient([]))
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    update = _cb("list:0", 7602)
    asyncio.run(h.list_conversations(update, ctx))

    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.update_outcome(7602) == uo.EXPLICITLY_IGNORED
    db.close()


def test_nav03_exit_expected_4xx_rejection(tmp_path):
    """مخرج 2 (رفض 4xx متوقّع) ⇒ مسح + `explicitly_ignored` (نتيجة مستخدم صريحة)."""
    from tests.test_sw07_api_handler_failure_propagation import ListClient

    ctx = make_context(OWNER_ID, tmp_path, client=ListClient(ApiError("forbidden", 403)))
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    update = _cb("list:0", 7603)
    asyncio.run(h.list_conversations(update, ctx))

    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.update_outcome(7603) == uo.EXPLICITLY_IGNORED
    db.close()


@pytest.mark.parametrize("code", [500, 503, 429, None])
def test_nav03_exit_operational_failure_never_qualifies(tmp_path, code):
    """مخرج 1 (فشل تشغيلي) ⇒ **مفيش** مسح ولا نتيجة مؤهّلة؛ الاستثناء ينتشر.

    لو المسح+`explicitly_ignored` حصلوا قبل نداء الـ API (زي الكود القديم)، كان التحديث
    يتأهّل ثم يفشل ⇒ فشل يتحوّل لنجاح ويُحجب الحدّ.
    """
    from tests.test_sw07_api_handler_failure_propagation import ListClient

    ctx = make_context(OWNER_ID, tmp_path, client=ListClient(ApiError("upstream", code)))
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    update = _cb("list:0", 7604)
    with pytest.raises(h.OperationalApiFailure):
        asyncio.run(h.list_conversations(update, ctx))

    assert db.get_awaiting(OWNER_ID) == ("conv-A", "route"), "الحالة اتمسحت قبل الفشل!"
    assert db.update_outcome(7604) is None
    assert db.update_failure(7604) is None or not uo.is_ack_eligible(db.update_outcome(7604))
    db.close()


def test_nav03_exit_db_filter_failure_records_failure_not_ignored(tmp_path):
    """مخرج 3 (فشل فلترة القاعدة) ⇒ مسح + **نتيجة فشل** (مش `explicitly_ignored`)."""
    client = F1ListClient(
        list_items=[{"id": "c1", "title": "شات", "execution_status": "running"}],
        conv={"id": "c1", "title": "شات"},
    )
    ctx = make_context(OWNER_ID, tmp_path, client=client)
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    def boom(_cid):
        raise RuntimeError("db down")

    db.is_deleted = boom  # type: ignore[assignment]

    update = _cb("list:0", 7605)
    asyncio.run(h.list_conversations(update, ctx))

    # الحالة اتمسحت (نفس السلوك القديم) لكن النتيجة **فشل**، مش تجاهل مؤهّل.
    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.update_failure(7605) == uo.FAILED_PERMANENT
    assert uo.is_ack_eligible(db.update_outcome(7605) or uo.FAILED_PERMANENT) is False
    db.close()


def test_nav03_rollback_leaves_state_untouched(tmp_path, monkeypatch):
    """فشل كتابة النتيجة على مخرج النجاح ⇒ **مفيش** مسح للحالة."""
    client = FakeClient([{"id": "c1", "title": "شات", "execution_status": "running"}])
    ctx = make_context(OWNER_ID, tmp_path, client=client)
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    def _boom(*_a, **_k):
        raise RuntimeError("outcome write failed")

    monkeypatch.setattr(db, "mark_update_outcome", _boom)
    with pytest.raises(RuntimeError):
        asyncio.run(h.list_conversations(_cb("list:0", 7606), ctx))

    assert db.get_awaiting(OWNER_ID) == ("conv-A", "route"), "مسح حالة بلا نتيجة!"
    assert db.update_outcome(7606) is None
    db.close()


def test_nav03_update_id_none_clears_without_outcome(tmp_path):
    """`update_id=None` ⇒ مسح بس على مخرج النجاح."""
    client = FakeClient([{"id": "c1", "title": "شات", "execution_status": "running"}])
    ctx = make_context(OWNER_ID, tmp_path, client=client)
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    asyncio.run(h.list_conversations(_t55_cb_update(CQ("list:0")), ctx))

    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.count_processed_updates() == 0
    db.close()


def test_nav03_unauthorized_clears_nothing(tmp_path):
    """غير مصرّح ⇒ مفيش مسح ولا مساس بالقايمة."""
    ctx = make_context(OWNER_ID, tmp_path, client=FakeClient([]))
    db = ctx.bot_data["db"]
    db.set_awaiting(999, "conv-x", "reply")

    asyncio.run(h.list_conversations(_cb("list:0", 7607, user_id=999), ctx))

    assert db.get_awaiting(999) == ("conv-x", "reply")
    assert db.update_outcome(7607) == uo.EXPLICITLY_IGNORED
    db.close()


# ============================================================================
# إعادة التسليم — الثلاثة
# ============================================================================
@pytest.mark.parametrize(
    "runner,uid",
    [
        ("start", 7701),
        ("list_conversations", 7702),
        ("list_watches", 7703),
    ],
)
def test_repeated_delivery_keeps_outcome_stable(tmp_path, runner, uid):
    """إعادة تسليم نفس `update_id` ⇒ النتيجة ثابتة والحالة ممسوحة."""
    client = FakeClient([{"id": "c1", "title": "شات", "execution_status": "running"}])
    ctx = make_context(OWNER_ID, tmp_path, client=client)
    db = ctx.bot_data["db"]

    def call():
        if runner == "start":
            update = make_update(OWNER_ID, "/start")
            update.update_id = uid
            asyncio.run(h.start(update, ctx))
        elif runner == "list_conversations":
            asyncio.run(h.list_conversations(_cb("list:0", uid), ctx))
        else:
            asyncio.run(h.list_watches(_cb("watched:0", uid), ctx))

    call()
    call()

    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.update_outcome(uid) == uo.EXPLICITLY_IGNORED
    db.close()


# ============================================================================
# الوحدة: المساعد الذرّي على مسار المسح
# ============================================================================
def test_helper_rolls_back_clear_when_outcome_write_fails(tmp_path, monkeypatch):
    """`clear_awaiting_and_record_outcome`: فشل النتيجة ⇒ الحالة **مااتمسحتش**."""
    db = Database(str(tmp_path / "unit.sqlite3"))
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    def _boom(*_a, **_k):
        raise RuntimeError("outcome write failed")

    monkeypatch.setattr(db, "mark_update_outcome", _boom)
    with pytest.raises(RuntimeError):
        db.clear_awaiting_and_record_outcome(
            OWNER_ID, 7801, "2026-01-01T00:00:00+00:00", uo.EXPLICITLY_IGNORED
        )

    assert db.get_awaiting(OWNER_ID) == ("conv-A", "route")
    assert db.update_outcome(7801) is None
    db.close()
