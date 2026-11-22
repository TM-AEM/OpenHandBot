"""OHB2-WP-07 (NEW-DEF-03 / NAV-06) — اختبارات انحدار على **ذرّية تفعيل نافذة التوجيه مع
كتابة نتيجة التحديث** في `handlers.open_conversation`.

المشكلة: فتح الشات كان بيعمل عمليتين بـcommitين منفصلين:
`db.set_awaiting(..., "route")` ثم `mark_explicitly_ignored(...)`. عطل/انهيار بينهم كان
يفعّل **نافذة توجيه 10 دقايق** بلا أي سجل دائم لسببها.

الإصلاح: `Database.set_awaiting_and_record_outcome` بتعمل الاتنين في **معاملة واحدة**
(`BEGIN IMMEDIATE`): إما يتحفظوا معًا أو يتراجعوا معًا. الإرسال لتليجرام يفضل **برّه**
المعاملة (SQLite وتليجرام مش معاملة موزّعة واحدة — عقد OHB2 §F.1).

الاختبارات **مُميِّزة**: `test_display_success_commits_state_and_outcome_together`،
`test_failure_cannot_leave_awaiting_without_outcome` و
`test_previous_route_survives_failed_transaction` بتفشل على الكود القديم (commitين).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

import bot.handlers as h
from bot import update_outcomes as uo
from bot.db import AWAITING_TTL, Database

from tests.test_4b import Q, OpenClient, cb_update
from tests.test_handlers import make_context

OWNER_ID = 1


def _open_ctx(tmp_path, title="شات A"):
    client = OpenClient({"id": "A", "title": title, "execution_status": "finished"})
    return make_context(OWNER_ID, tmp_path, client=client)


def _cb_with_id(data, update_id):
    update = cb_update(Q(data))
    update.update_id = update_id
    return update


# ============================================================================
# 1) النجاح: الحالة والنتيجة في معاملة واحدة
# ============================================================================
def test_display_success_commits_state_and_outcome_together(tmp_path):
    """فتح الشات بنجاح ⇒ نافذة توجيه مفعّلة **و**نتيجة دائمة مؤهّلة للإقرار."""
    ctx = _open_ctx(tmp_path)
    db = ctx.bot_data["db"]

    asyncio.run(h.open_conversation(_cb_with_id("open:A", 7001), ctx))

    assert db.get_awaiting(OWNER_ID) == ("A", "route")
    assert db.update_outcome(7001) == uo.EXPLICITLY_IGNORED
    assert uo.is_ack_eligible(db.update_outcome(7001)) is True
    db.close()


def test_title_and_ttl_semantics_preserved(tmp_path):
    """العنوان المخزَّن ومهلة النافذة (10 دقايق) زي ما كانوا بالحرف."""
    ctx = _open_ctx(tmp_path, title="شات العنوان")
    db = ctx.bot_data["db"]

    asyncio.run(h.open_conversation(_cb_with_id("open:A", 7002), ctx))

    conv_id, kind, title, awaiting_at = db.awaiting_state(OWNER_ID)
    assert (conv_id, kind, title) == ("A", "route", "شات العنوان")
    assert awaiting_at is not None
    assert datetime.now(timezone.utc) - awaiting_at < AWAITING_TTL
    assert db.awaiting_is_expired(awaiting_at) is False
    db.close()


def test_empty_title_still_stored_as_empty_string(tmp_path):
    """شات بلا عنوان ⇒ العنوان `""` (نفس سلوك `conv.get("title") or ""` القديم)."""
    client = OpenClient({"id": "A", "execution_status": "finished"})
    ctx = make_context(OWNER_ID, tmp_path, client=client)
    db = ctx.bot_data["db"]

    asyncio.run(h.open_conversation(_cb_with_id("open:A", 7003), ctx))

    assert db.awaiting_state(OWNER_ID)[2] == ""
    db.close()


# ============================================================================
# 2) rollback: فشل المعاملة مايخلّيش حالة بلا نتيجة
# ============================================================================
def test_failure_cannot_leave_awaiting_without_outcome(tmp_path, monkeypatch):
    """الحاسم: صف الحالة اتكتب **ثم** فشلت كتابة النتيجة ⇒ الاتنين يتراجعوا.

    ده بالظبط نافذة العطل اللي كان الـcommitين المنفصلين بيسيبوها مفتوحة.
    """
    ctx = _open_ctx(tmp_path)
    db = ctx.bot_data["db"]

    original = db._set_awaiting_nocommit

    def _write_then_fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("outcome write failed")

    monkeypatch.setattr(db, "_set_awaiting_nocommit", _write_then_fail)
    with pytest.raises(RuntimeError):
        asyncio.run(h.open_conversation(_cb_with_id("open:A", 7004), ctx))

    assert db.get_awaiting(OWNER_ID) == (None, None), "نافذة توجيه اتفعّلت بلا نتيجة!"
    assert db.update_outcome(7004) is None
    db.close()


def test_handler_rolls_back_on_outcome_write_failure(tmp_path, monkeypatch):
    """فشل كتابة النتيجة فقط ⇒ ولا حاجة اتحفظت (لا حالة ولا نتيجة)."""
    ctx = _open_ctx(tmp_path)
    db = ctx.bot_data["db"]

    def _boom(*_a, **_k):
        raise RuntimeError("outcome write failed")

    monkeypatch.setattr(db, "mark_update_outcome", _boom)
    with pytest.raises(RuntimeError):
        asyncio.run(h.open_conversation(_cb_with_id("open:A", 7005), ctx))

    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.count_processed_updates() == 0
    db.close()


def test_previous_route_survives_failed_transaction(tmp_path, monkeypatch):
    """توجيه قائم سابق **مايتلمسش** لو المعاملة فشلت (مفيش حالة نص-مكتوبة)."""
    ctx = _open_ctx(tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-OLD", "reply", title="قديم")

    def _boom(*_a, **_k):
        raise RuntimeError("outcome write failed")

    monkeypatch.setattr(db, "mark_update_outcome", _boom)
    with pytest.raises(RuntimeError):
        asyncio.run(h.open_conversation(_cb_with_id("open:A", 7006), ctx))

    assert db.get_awaiting(OWNER_ID) == ("conv-OLD", "reply")
    db.close()


# ============================================================================
# 3) توافق `update_id=None`
# ============================================================================
def test_update_id_none_activates_route_without_outcome(tmp_path):
    """تحديث بلا معرّف (adapters/اختبارات): النافذة تتفعّل، ومفيش صف نتيجة (سلوك قديم)."""
    ctx = _open_ctx(tmp_path)
    db = ctx.bot_data["db"]

    asyncio.run(h.open_conversation(cb_update(Q("open:A")), ctx))

    assert db.get_awaiting(OWNER_ID) == ("A", "route")
    assert db.count_processed_updates() == 0
    db.close()


# ============================================================================
# 4) سلوك تيليجرام + فشل العرض
# ============================================================================
def test_display_failure_activates_nothing_and_records_transient(tmp_path):
    """فشل العرض ⇒ **مفيش** نافذة توجيه + نتيجة عابرة غير مؤهّلة (fail-closed)."""
    ctx = _open_ctx(tmp_path)
    db = ctx.bot_data["db"]

    q = Q("open:A")

    async def _fail(*_a, **_k):
        raise RuntimeError("Message can't be edited")

    q.edit_message_text = _fail
    update = cb_update(q)
    update.update_id = 7007

    asyncio.run(h.open_conversation(update, ctx))

    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.update_outcome(7007) == uo.FAILED_TRANSIENT
    assert uo.is_ack_eligible(db.update_outcome(7007)) is False
    db.close()


def test_telegram_display_text_unchanged(tmp_path):
    """نص العرض للمستخدم يعكس التوجيه الدائم + زر الإلغاء."""
    ctx = _open_ctx(tmp_path)
    q = Q("open:A")
    update = cb_update(q)
    update.update_id = 7008

    asyncio.run(h.open_conversation(update, ctx))

    shown = "".join(q.edits)
    assert "لحد ما تفتح/تختار شات تاني" in shown
    assert q.markups and q.markups[0] is not None
    ctx.bot_data["db"].close()


# ============================================================================
# 5) إعادة التسليم المكرّرة
# ============================================================================
def test_repeated_delivery_keeps_outcome_and_state_consistent(tmp_path):
    """إعادة تسليم نفس `update_id` ⇒ الحالة مفعّلة والنتيجة ثابتة (ما تنخفضش)."""
    ctx = _open_ctx(tmp_path)
    db = ctx.bot_data["db"]

    asyncio.run(h.open_conversation(_cb_with_id("open:A", 7009), ctx))
    asyncio.run(h.open_conversation(_cb_with_id("open:A", 7009), ctx))

    assert db.get_awaiting(OWNER_ID) == ("A", "route")
    assert db.update_outcome(7009) == uo.EXPLICITLY_IGNORED
    db.close()


# ============================================================================
# 6) الوحدة: المساعد الذرّي نفسه على مسار التفعيل
# ============================================================================
def test_helper_rolls_back_activation_when_outcome_write_fails(tmp_path, monkeypatch):
    """`set_awaiting_and_record_outcome`: فشل النتيجة ⇒ **مفيش** تفعيل توجيه ولا نتيجة."""
    db = Database(str(tmp_path / "unit.sqlite3"))

    def _boom(*_a, **_k):
        raise RuntimeError("outcome write failed")

    monkeypatch.setattr(db, "mark_update_outcome", _boom)
    with pytest.raises(RuntimeError):
        db.set_awaiting_and_record_outcome(
            OWNER_ID, "conv-A", "route", 8001, "2026-01-01T00:00:00+00:00",
            uo.EXPLICITLY_IGNORED, title="t",
        )

    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.update_outcome(8001) is None
    db.close()


def test_helper_without_update_id_activates_only(tmp_path):
    """`update_id=None` ⇒ تفعيل التوجيه بس، وبيرجّع False (سلوك المساعد المعتمد)."""
    db = Database(str(tmp_path / "unit2.sqlite3"))
    ok = db.set_awaiting_and_record_outcome(
        OWNER_ID, "conv-A", "route", None, "2026-01-01T00:00:00+00:00",
        uo.EXPLICITLY_IGNORED, title="t",
    )
    assert ok is False
    assert db.get_awaiting(OWNER_ID) == ("conv-A", "route")
    assert db.count_processed_updates() == 0
    db.close()
