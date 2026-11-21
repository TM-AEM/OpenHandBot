"""OHB2-WP-07 (DEF-013/NEW-DEF-03) — اختبارات انحدار على **ذرّية مسح حالة الانتظار مع
كتابة نتيجة التحديث**.

المشكلة المُبلَّغ عنها (تأكيد مستقل): مسارات `/cancel` (رسالة/زر) وفرع الحالة المنتهية في
`handle_text` كانت بتعمل `clear_awaiting` (commit مستقل) **قبل** تسجيل النتيجة
(`mark_durable_completed`/`mark_explicitly_ignored`) — commit تانٍ. عطل/انهيار بين الكتابتين
كان يسيب حالة انتظار ممسوحة **بلا** نتيجة مسجّلة ⇒ إعادة التسليم تقع في الفرع العام (تلميح
`/start`) بدل السلوك الصحيح، وتفقد الحجز على حدّ الإقرار.

الإصلاح: `Database.clear_awaiting_and_record_outcome` بتعمل الاتنين في **معاملة واحدة**
(`BEGIN IMMEDIATE`): إما يتحفظوا معًا أو يتراجعوا معًا. الإرسال لتليجرام يفضل **برّه**
المعاملة (SQLite وتليجرام مش معاملة موزّعة واحدة).

الاختبارات **مُميِّزة** (بتفشل على الكود القديم): لو رجعنا للمسح بمعاملة مستقلة،
`test_helper_rolls_back_state_when_outcome_write_fails` و
`test_expired_branch_is_atomic_on_outcome_failure` و
`test_cancel_route_is_atomic_on_outcome_failure` بتفشل.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

import bot.handlers as h
from bot import update_outcomes as uo
from bot.db import Database

from tests.test_handlers import make_context, make_update

OWNER_ID = 1


def _aged(minutes):
    return datetime.now(timezone.utc) - timedelta(minutes=minutes)


# ============================================================================
# 1) الوحدة: `clear_awaiting_and_record_outcome` — ذرّية (rollback عند فشل الكتابة)
# ============================================================================
def test_helper_clears_state_and_records_outcome(tmp_path):
    db = Database(str(tmp_path / "a.sqlite3"))
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")
    assert db.get_awaiting(OWNER_ID) == ("conv-A", "route")

    ok = db.clear_awaiting_and_record_outcome(
        OWNER_ID, 5001, "2026-01-01T00:00:00+00:00", uo.DURABLE_COMPLETED
    )
    assert ok is True
    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.update_outcome(5001) == uo.DURABLE_COMPLETED
    db.close()


def test_helper_rolls_back_state_when_outcome_write_fails(tmp_path, monkeypatch):
    """الحاسم: فشل كتابة النتيجة **مايخلّيش** الحالة ممسوحة (الاتنين يتراجعوا).

    على الكود القديم (مسح بـcommit مستقل) كانت الحالة هتفضل ممسوحة ⇒ الاختبار يفشل.
    """
    db = Database(str(tmp_path / "b.sqlite3"))
    db.set_awaiting(OWNER_ID, "conv-A", "reply")

    def _boom(*_a, **_k):
        raise RuntimeError("outcome write failed")

    monkeypatch.setattr(db, "mark_update_outcome", _boom)
    with pytest.raises(RuntimeError):
        db.clear_awaiting_and_record_outcome(
            OWNER_ID, 5002, "2026-01-01T00:00:00+00:00", uo.EXPLICITLY_IGNORED
        )
    # الحالة **مااتلمستش** (المعاملة اترجعت بالكامل).
    assert db.get_awaiting(OWNER_ID) == ("conv-A", "reply")
    assert db.update_outcome(5002) is None
    db.close()


def test_helper_without_update_id_clears_only(tmp_path):
    db = Database(str(tmp_path / "c.sqlite3"))
    db.set_awaiting(OWNER_ID, "conv-A", "reply")
    ok = db.clear_awaiting_and_record_outcome(
        OWNER_ID, None, "2026-01-01T00:00:00+00:00", uo.DURABLE_COMPLETED
    )
    assert ok is False
    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.count_processed_updates() == 0
    db.close()


# ============================================================================
# 2) فرع الحالة المنتهية في `handle_text` (DEF-013)
# ============================================================================
def test_expired_branch_records_ignored_and_clears_state(tmp_path):
    ctx = make_context(OWNER_ID, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "reply", now=_aged(11))
    update = make_update(OWNER_ID, "رسالة متأخرة")
    update.update_id = 5101

    asyncio.run(h.handle_text(update, ctx))

    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.update_outcome(5101) == uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(5101) is True
    assert "انتهت مهلة" in update.message.replies[0]


def test_expired_branch_is_atomic_on_outcome_failure(tmp_path, monkeypatch):
    """الحاسم: فشل تسجيل النتيجة في فرع الانتهاء **مايسيبش** الحالة ممسوحة بلا نتيجة.

    على الكود القديم (مسح بـcommit مستقل ثم `mark_explicitly_ignored` اللي بيبتلع الفشل)
    كانت الحالة هتفضل ممسوحة ⇒ الاختبار يفشل.
    """
    ctx = make_context(OWNER_ID, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "reply", now=_aged(11))
    update = make_update(OWNER_ID, "رسالة متأخرة")
    update.update_id = 5102

    def _boom(*_a, **_k):
        raise RuntimeError("db down")

    monkeypatch.setattr(db, "mark_update_outcome", _boom)
    with pytest.raises(RuntimeError):
        asyncio.run(h.handle_text(update, ctx))

    # مفيش مسح جزئي: الحالة لسه موجودة (المعاملة اترجعت).
    assert db.get_awaiting(OWNER_ID) == ("conv-A", "reply")
    assert db.update_outcome(5102) is None


# ============================================================================
# 3) `/cancel` (رسالة + زر) (NEW-DEF-03)
# ============================================================================
def test_cancel_route_message_records_durable_completed(tmp_path):
    ctx = make_context(OWNER_ID, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")
    update = make_update(OWNER_ID, "/cancel")
    update.update_id = 5201

    asyncio.run(h.cancel_route(update, ctx))

    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.update_outcome(5201) == uo.DURABLE_COMPLETED
    assert "اتلغى" in update.message.replies[0]


def test_cancel_route_is_atomic_on_outcome_failure(tmp_path, monkeypatch):
    """الحاسم: فشل تسجيل النتيجة في `/cancel` **مايسيبش** الحالة ممسوحة.

    على الكود القديم (مسح بـcommit مستقل) كانت الحالة هتفضل ممسوحة ⇒ الاختبار يفشل.
    """
    ctx = make_context(OWNER_ID, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")
    update = make_update(OWNER_ID, "/cancel")
    update.update_id = 5202

    def _boom(*_a, **_k):
        raise RuntimeError("db down")

    monkeypatch.setattr(db, "mark_update_outcome", _boom)
    with pytest.raises(RuntimeError):
        asyncio.run(h.cancel_route(update, ctx))

    assert db.get_awaiting(OWNER_ID) == ("conv-A", "route")
    assert db.update_outcome(5202) is None


# ============================================================================
# 4) ضبط التوجيه + النتيجة ذرّيًّا (NEW-DEF-03): reply_prompt / pick_repo / ...
# ============================================================================
def test_set_helper_rolls_back_state_when_outcome_write_fails(tmp_path, monkeypatch):
    """الحاسم: فشل كتابة النتيجة **مايخلّيش** حالة التوجيه مضبوطة (الاتنين يتراجعوا)."""
    db = Database(str(tmp_path / "d.sqlite3"))
    db.set_awaiting(OWNER_ID, "old", "route", title="t")

    def _boom(*_a, **_k):
        raise RuntimeError("outcome write failed")

    monkeypatch.setattr(db, "mark_update_outcome", _boom)
    with pytest.raises(RuntimeError):
        db.set_awaiting_and_record_outcome(
            OWNER_ID, "conv-B", "reply", 5300, "2026-01-01T00:00:00+00:00",
            uo.DURABLE_COMPLETED,
        )
    # الحالة القديمة **مااتلمستش** (المعاملة اترجعت بالكامل).
    assert db.get_awaiting(OWNER_ID) == ("old", "route")
    assert db.update_outcome(5300) is None
    db.close()


def test_reply_prompt_is_atomic_on_outcome_failure(tmp_path, monkeypatch):
    """الحاسم: فشل تسجيل النتيجة في `reply_prompt` **مايسيبش** حالة `reply` مضبوطة.

    على الكود القديم (`set_awaiting` بـcommit مستقل ثم `mark_durable_completed`) كانت
    الحالة هتفضل مضبوطة بلا نتيجة ⇒ الاختبار يفشل.
    """
    from tests.test_handlers import DetailClient, _cb_update

    ctx = make_context(OWNER_ID, tmp_path, client=DetailClient({"id": "c1", "title": "شات"}))
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "old", "route", title="t")
    update = _cb_update(OWNER_ID, "reply:c1")
    update.update_id = 5301

    def _boom(*_a, **_k):
        raise RuntimeError("db down")

    monkeypatch.setattr(db, "mark_update_outcome", _boom)
    with pytest.raises(RuntimeError):
        asyncio.run(h.reply_prompt(update, ctx))

    assert db.get_awaiting(OWNER_ID) == ("old", "route")
    assert db.update_outcome(5301) is None
