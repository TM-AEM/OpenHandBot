"""OHB2-MANUAL-POLLING-OUTCOME-AND-ACK-BOUNDARY-CORRECTION — اختبارات انحدار.

بتغطّي الخمس محاور:
1. النتيجة الدائمة تُكتب **ذرّيًا** مع عملية القاعدة اللي بتنفّذ نية التحديث (دليل إقرار
   مُـcommit، مش رجوع الـ handler).
2. الفشل المُبتلَع/الغامض مايتقبلش كنجاح (fail-closed) + معالج الأخطاء بيسجّل الفشل.
3. حدّ الإقرار = أطول بادئة مؤهّلة بترتيب الاستقبال (فجوات، فشل أول/وسط/آخر، حجز لاحق).
4. كتابة النتائج + الحدّ المحلي ذرّية (معاملة واحدة) وrestart-safe.
5. سلوك crash/retry للآثار الجانبية الخارجية (reposearch/حذف الشات) — إعادة تنفيذ آمنة
   مقابل عدم تكرار خطِر.

مفيش شبكة/قاعدة حيّة: قاعدة معزولة في `tmp_path` وعملاء وهميين.
"""
from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from telegram import Chat, Message, Update, User

import bot.handlers as h
from bot import outbox
from bot import update_outcomes as uo
from bot.db import Database
from tests.test_one_shot_awaiting_atomicity import (  # noqa: F401
    CID_A,
    OWNER_ID,
    U_REPOS,
    FakeOpenHands,
    ReposClient,
    _conv,
    _harness,
    _raise_operational,
)


def _db(tmp_path) -> Database:
    return Database(str(Path(tmp_path) / "outcome.sqlite3"))


def _text_update(update_id: int, text: str = "برومت") -> Update:
    chat = Chat(id=99, type="private")
    msg = Message(message_id=5, date=None, chat=chat, from_user=User(id=OWNER_ID, first_name="o", is_bot=False), text=text)
    return Update(update_id=update_id, message=msg)


# ============================================================================
# 1) التصنيف وحدّ الإقرار (وحدة نقيّة)
# ============================================================================
def test_ack_eligible_set_is_fail_closed():
    for outcome in (
        uo.DURABLE_COMPLETED,
        uo.DURABLE_INTENT_RECORDED,
        uo.EXPLICITLY_IGNORED,
        uo.DUPLICATE_COMPLETED,
    ):
        assert uo.is_ack_eligible(outcome) is True
    for outcome in (
        uo.FAILED_TRANSIENT,
        uo.FAILED_PERMANENT,
        uo.PARTIAL_OR_UNKNOWN,
        None,
        "",
        "unknown_garbage",
    ):
        assert uo.is_ack_eligible(outcome) is False


def test_boundary_longest_eligible_prefix_with_gaps():
    """فجوات في المعرّفات: الحدّ = آخر تحديث في أطول بادئة مؤهّلة (مش max+1)."""
    received = [5, 7, 9, 12]
    outcomes = {
        5: uo.DURABLE_COMPLETED,
        7: uo.DURABLE_INTENT_RECORDED,
        9: uo.EXPLICITLY_IGNORED,
        12: uo.DURABLE_COMPLETED,
    }
    assert uo.acknowledgment_boundary(received, outcomes) == 12


def test_boundary_stops_at_first_failure_middle():
    received = [5, 7, 9, 12]
    outcomes = {
        5: uo.DURABLE_COMPLETED,
        7: uo.FAILED_PERMANENT,
        9: uo.DURABLE_COMPLETED,
        12: uo.DURABLE_COMPLETED,
    }
    # 9 و12 ناجحين لكن محجوبين بفشل 7.
    assert uo.acknowledgment_boundary(received, outcomes) == 5


def test_boundary_first_failure_returns_none():
    received = [5, 7]
    outcomes = {5: uo.PARTIAL_OR_UNKNOWN, 7: uo.DURABLE_COMPLETED}
    assert uo.acknowledgment_boundary(received, outcomes) is None


def test_boundary_last_failure_keeps_earlier_prefix():
    received = [5, 7, 9]
    outcomes = {5: uo.DURABLE_COMPLETED, 7: uo.DURABLE_COMPLETED, 9: uo.FAILED_TRANSIENT}
    assert uo.acknowledgment_boundary(received, outcomes) == 7


def test_boundary_missing_outcome_is_ineligible():
    received = [5, 7]
    outcomes = {5: uo.DURABLE_COMPLETED}  # 7 مالوش نتيجة مسجّلة
    assert uo.acknowledgment_boundary(received, outcomes) == 5


def test_boundary_empty_received_is_none():
    assert uo.acknowledgment_boundary([], {}) is None


def test_boundary_not_max_plus_one_even_when_later_succeeds():
    """لو استخدمنا max+1 كنا هنقبل 12 رغم فشل 7 — لازم نرفض."""
    received = [5, 7, 12]
    outcomes = {5: uo.DURABLE_COMPLETED, 7: uo.FAILED_PERMANENT, 12: uo.DURABLE_COMPLETED}
    boundary = uo.acknowledgment_boundary(received, outcomes)
    assert boundary == 5
    assert boundary != max(received)


# ============================================================================
# 2) النتيجة الدائمة ذرّية مع العملية الدائمة
# ============================================================================
def test_durable_intent_recorded_atomically_with_outbox(tmp_path):
    db = _db(tmp_path)
    out_id = db.add_or_group_outbox(CID_A, 99, "برومت", outbox.now_iso(), update_id=5001)
    assert out_id != 0
    assert db.update_outcome(5001) == uo.DURABLE_INTENT_RECORDED
    assert db.is_update_acknowledgment_eligible(5001) is True
    db.close()


def test_durable_intent_recorded_atomically_with_creation_job(tmp_path):
    db = _db(tmp_path)
    job_id = db.add_creation_job(99, "owner/repo", "برومت", outbox.now_iso(), update_id=5002)
    assert job_id != 0
    assert db.update_outcome(5002) == uo.DURABLE_INTENT_RECORDED
    db.close()


def test_durable_completed_for_one_shot_reposearch_consume(tmp_path):
    db = _db(tmp_path)
    db.set_awaiting(OWNER_ID, "", "reposearch")
    assert db.consume_one_shot_awaiting(OWNER_ID, "reposearch", 5003, outbox.now_iso()) is True
    assert db.update_outcome(5003) == uo.DURABLE_COMPLETED
    db.close()


def test_durable_completed_for_notifications_toggle(tmp_path):
    db = _db(tmp_path)
    db.toggle_notifications_once(5004, outbox.now_iso())
    assert db.update_outcome(5004) == uo.DURABLE_COMPLETED
    db.close()


def test_outcome_atomic_with_rollback(tmp_path, monkeypatch):
    """عطل جوه المعاملة ⇒ **مفيش** نتيجة دائمة (الاتنين يتراجعوا معًا)."""
    db = _db(tmp_path)
    db.set_awaiting(OWNER_ID, CID_A, "reply")
    monkeypatch.setattr(db, "_mark_processed_nocommit", _raise_operational)
    with pytest.raises(sqlite3.OperationalError):
        db.add_or_group_outbox(
            CID_A, 99, "برومت", outbox.now_iso(), reengage=True,
            update_id=5100, consume_awaiting=(OWNER_ID, "reply"),
        )
    assert db.update_outcome(5100) is None
    assert db.is_update_acknowledgment_eligible(5100) is False
    assert db.get_awaiting(OWNER_ID) == (CID_A, "reply")
    db.close()


def test_duplicate_client_ref_records_duplicate_completed(tmp_path):
    db = _db(tmp_path)
    first = db.add_or_group_outbox(CID_A, 99, "برومت", outbox.now_iso(), client_ref="ref-1")
    assert first != 0
    again = db.add_or_group_outbox(
        CID_A, 99, "برومت", outbox.now_iso(), client_ref="ref-1", update_id=5200
    )
    assert again == first
    assert db.update_outcome(5200) == uo.DUPLICATE_COMPLETED
    db.close()


def test_no_update_id_means_no_outcome_row(tmp_path):
    """مسار Mini App (بدون update_id) ⇒ مفيش صف نتيجة (no-op)."""
    db = _db(tmp_path)
    db.add_or_group_outbox(CID_A, 99, "برومت", outbox.now_iso())
    assert db.count_processed_updates() == 0
    db.close()


# ============================================================================
# 3) معالج الأخطاء: الفشل المُبتلَع مايتقبلش كنجاح
# ============================================================================
def test_processing_error_handler_records_permanent_failure(tmp_path, monkeypatch):
    hh = _harness(tmp_path, monkeypatch)
    update = _text_update(6001)
    ctx = SimpleNamespace(bot_data={"db": hh.db}, error=RuntimeError("boom"))
    asyncio.run(h.handle_processing_error(update, ctx))
    assert hh.db.update_outcome(6001) == uo.FAILED_PERMANENT
    assert hh.db.update_failure(6001) == uo.FAILED_PERMANENT
    assert hh.db.is_update_acknowledgment_eligible(6001) is False
    # الفشل **مايتكتبش** في جدول الديدَب ⇒ إعادة التسليم لسه تنفّذ.
    assert hh.db.update_is_processed(6001) is False


def test_processing_error_handler_classifies_transient_sqlite(tmp_path, monkeypatch):
    hh = _harness(tmp_path, monkeypatch)
    update = _text_update(6002)
    exc = sqlite3.OperationalError("database is locked")
    ctx = SimpleNamespace(bot_data={"db": hh.db}, error=exc)
    asyncio.run(h.handle_processing_error(update, ctx))
    assert hh.db.update_outcome(6002) == uo.FAILED_TRANSIENT


def test_processing_error_handler_classifies_cancelled_as_unknown(tmp_path, monkeypatch):
    hh = _harness(tmp_path, monkeypatch)
    update = _text_update(6003)
    ctx = SimpleNamespace(bot_data={"db": hh.db}, error=asyncio.CancelledError())
    asyncio.run(h.handle_processing_error(update, ctx))
    assert hh.db.update_outcome(6003) == uo.PARTIAL_OR_UNKNOWN


def test_processing_error_handler_ignores_handler_stop_and_none(tmp_path, monkeypatch):
    from telegram.ext import ApplicationHandlerStop

    hh = _harness(tmp_path, monkeypatch)
    ctx = SimpleNamespace(bot_data={"db": hh.db}, error=ApplicationHandlerStop())
    asyncio.run(h.handle_processing_error(_text_update(6004), ctx))
    assert hh.db.update_outcome(6004) is None
    ctx2 = SimpleNamespace(bot_data={"db": hh.db}, error=None)
    asyncio.run(h.handle_processing_error(_text_update(6005), ctx2))
    assert hh.db.update_outcome(6005) is None


def test_error_handler_registered_on_application(tmp_path):
    from bot import app as app_mod
    from tests.test_duplicate_update_dispatch import make_config

    app = app_mod.build_application(make_config(tmp_path))
    assert h.handle_processing_error in app.error_handlers


def test_swallowed_durable_failure_is_not_acknowledged_end_to_end(tmp_path, monkeypatch):
    """عطل في الكتابة الدائمة ⇒ رجوع `process_update` (PTB بيبتلع) لكن **مش** مؤهّل."""
    hh = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")}))
    hh.db.set_awaiting(OWNER_ID, CID_A, "reply")
    calls = {"n": 0}
    original = hh.db.add_or_group_outbox

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            _raise_operational()
        return original(*a, **k)

    monkeypatch.setattr(hh.db, "add_or_group_outbox", flaky)
    hh.process(hh.text_update(6100, "برومت"))
    assert calls["n"] == 1
    # مفيش نتيجة مؤهّلة، وفيه فشل مسجّل (من معالج الأخطاء).
    assert hh.db.is_update_acknowledgment_eligible(6100) is False
    assert hh.db.update_failure(6100) is not None


def test_explicitly_ignored_plain_text_is_acknowledged(tmp_path, monkeypatch):
    """رسالة بلا توجيه ⇒ مسار مُتجاهَل صريح ⇒ نتيجة مؤهّلة (مفيش إعادة معالجة)."""
    hh = _harness(tmp_path, monkeypatch)
    hh.process(hh.text_update(6200, "نص حر"))
    assert hh.db.update_outcome(6200) == uo.EXPLICITLY_IGNORED
    assert hh.db.is_update_acknowledgment_eligible(6200) is True


def test_list_conversations_db_failure_records_failure(tmp_path, monkeypatch):
    """`list_conversations` بتلتقط فشل القاعدة وتعرض رسالة ⇒ لازم تتسجّل كفشل."""
    from tests.test_handlers import CQ, _t55_cb_update, make_context, F1ListClient

    client = F1ListClient(
        list_items=[{"id": "c1", "title": "شات", "execution_status": "running"}],
        conv={"id": "c1", "title": "شات"},
    )
    ctx = make_context(1, tmp_path, client=client)

    def boom(_cid):
        raise RuntimeError("db down")

    ctx.bot_data["db"].is_deleted = boom  # type: ignore[assignment]
    update = _t55_cb_update(CQ("list:0"))
    update.update_id = 6300
    asyncio.run(h.list_conversations(update, ctx))
    assert ctx.bot_data["db"].update_failure(6300) == uo.FAILED_PERMANENT


def test_delete_confirm_db_failure_records_failure(tmp_path, monkeypatch):
    from tests.test_handlers import CQ, _t55_cb_update, make_context, F1ListClient

    client = F1ListClient(conv={"id": "c1", "title": "شات"})
    ctx = make_context(1, tmp_path, client=client)
    ctx.bot_data["db"].add_watched("c1", "شات", chat_id=99)

    def boom(*_a, **_k):
        raise sqlite3.Error("boom")

    monkeypatch.setattr(ctx.bot_data["db"], "delete_conversation", boom)
    update = _t55_cb_update(CQ("deleteok:c1"))
    update.update_id = 6400
    asyncio.run(h.delete_conversation_confirm(update, ctx))
    assert ctx.bot_data["db"].update_failure(6400) == uo.FAILED_PERMANENT


# ============================================================================
# 4) المعاملة الذرّية للنتائج + الحدّ المحلي (restart-safe)
# ============================================================================
def test_commit_batch_outcomes_persists_boundary_atomically(tmp_path):
    db = _db(tmp_path)
    boundary = db.commit_batch_outcomes(
        [(10, uo.DURABLE_COMPLETED), (12, uo.DURABLE_INTENT_RECORDED), (15, uo.EXPLICITLY_IGNORED)],
        outbox.now_iso(),
    )
    assert boundary == 15
    assert db.get_acknowledgment_boundary() == 15
    assert db.is_update_acknowledgment_eligible(10) is True
    assert db.is_update_acknowledgment_eligible(15) is True
    db.close()


def test_commit_batch_outcomes_stops_at_failure_and_persists(tmp_path):
    db = _db(tmp_path)
    boundary = db.commit_batch_outcomes(
        [(10, uo.DURABLE_COMPLETED), (12, uo.FAILED_PERMANENT), (15, uo.DURABLE_COMPLETED)],
        outbox.now_iso(),
    )
    assert boundary == 10
    assert db.get_acknowledgment_boundary() == 10
    # اللاحق الناجح **مش** بيكسر الحجز.
    assert db.is_update_acknowledgment_eligible(15) is False or db.update_outcome(15) == uo.DURABLE_COMPLETED
    db.close()


def test_commit_batch_outcomes_first_failure_keeps_previous_boundary(tmp_path):
    db = _db(tmp_path)
    db.commit_batch_outcomes([(10, uo.DURABLE_COMPLETED)], outbox.now_iso())
    boundary = db.commit_batch_outcomes(
        [(12, uo.PARTIAL_OR_UNKNOWN), (15, uo.DURABLE_COMPLETED)], outbox.now_iso()
    )
    assert boundary is None  # الدفعة الجديدة كلها محجوبة من أولها
    assert db.get_acknowledgment_boundary() == 10  # الحدّ السابق محفوظ
    db.close()


def test_commit_batch_outcomes_rolls_back_on_error(tmp_path, monkeypatch):
    db = _db(tmp_path)
    original = db._outcome_in_txn

    def boom(_uid):
        raise sqlite3.OperationalError("simulated crash during boundary computation")

    monkeypatch.setattr(db, "_outcome_in_txn", boom)
    with pytest.raises(sqlite3.OperationalError):
        db.commit_batch_outcomes([(10, uo.DURABLE_COMPLETED)], outbox.now_iso())
    monkeypatch.setattr(db, "_outcome_in_txn", original)
    # مفيش نتيجة اتـcommit، ومفيش حدّ.
    assert db.update_outcome(10) is None
    assert db.get_acknowledgment_boundary() is None
    db.close()


def test_boundary_survives_restart(tmp_path):
    p = str(Path(tmp_path) / "restart.sqlite3")
    db = Database(p)
    db.commit_batch_outcomes(
        [(10, uo.DURABLE_COMPLETED), (12, uo.DURABLE_COMPLETED)], outbox.now_iso()
    )
    db.close()
    reopened = Database(p)
    assert reopened.get_acknowledgment_boundary() == 12
    assert reopened.is_update_acknowledgment_eligible(10) is True
    assert reopened.is_update_acknowledgment_eligible(12) is True
    reopened.close()


def test_boundary_query_uses_committed_outcomes(tmp_path):
    db = _db(tmp_path)
    db.commit_batch_outcomes(
        [(10, uo.DURABLE_COMPLETED), (12, uo.DURABLE_COMPLETED), (15, uo.FAILED_PERMANENT)],
        outbox.now_iso(),
    )
    assert db.acknowledgment_boundary([10, 12, 15]) == 12
    assert db.acknowledgment_boundary([10, 12]) == 12
    assert db.acknowledgment_boundary([15]) is None
    db.close()


# ============================================================================
# 5) الآثار الجانبية الخارجية: crash/retry
# ============================================================================
def test_reposearch_crash_before_consume_redelivery_duplicates_harmlessly(tmp_path, monkeypatch):
    """عطل قبل الاستهلاك ⇒ إعادة التسليم تعيد البحث (قائمة مكرّرة غير ضارة) وبعدها تتسجّل."""
    client = ReposClient()
    hh = _harness(tmp_path, monkeypatch, client)
    hh.db.set_awaiting(OWNER_ID, "", "reposearch")
    calls = {"n": 0}
    original = hh.db.consume_one_shot_awaiting

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            _raise_operational()
        return original(*a, **k)

    monkeypatch.setattr(hh.db, "consume_one_shot_awaiting", flaky)
    update = hh.text_update(U_REPOS, "bot")
    hh.process(update)
    assert hh.db.get_awaiting(OWNER_ID) == ("", "reposearch")  # الحالة باقية
    assert hh.db.is_update_acknowledgment_eligible(U_REPOS) is False

    hh.process(update)  # إعادة التسليم
    assert hh.db.update_outcome(U_REPOS) == uo.DURABLE_COMPLETED
    assert client.searches == ["bot", "bot"]  # البحث اتنفّذ مرتين (آمن: قائمة مكرّرة)


def test_durable_intent_recorded_is_not_external_success(tmp_path):
    """`durable_intent_recorded` دليل **نية** مش دليل إرسال خارجي (at-most-once محفوظ).

    لو العملية ماتت بعد الكتابة الدائمة وقبل POST، التسليم بيتم من الـ worker (مش من
    إعادة التحديث) — الإقرار مايدّعيش إن الإرسال الخارجي حصل.
    """
    db = _db(tmp_path)
    db.add_or_group_outbox(CID_A, 99, "برومت", outbox.now_iso(), update_id=7001)
    assert db.update_outcome(7001) == uo.DURABLE_INTENT_RECORDED
    # السجل لسه 'pending' ⇒ التسليم الخارجي لسه معلّق (مفيش ادّعاء نجاح خارجي).
    assert len(db.list_outbox_by_status("pending")) == 1
    db.close()


def test_duplicate_update_after_durable_intent_creates_no_second_record(tmp_path, monkeypatch):
    hh = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")}))
    hh.db.set_awaiting(OWNER_ID, CID_A, "route", title="A")
    update = hh.text_update(7100, "برومت")
    hh.process(update)
    assert hh.db.count_outbox() == 1
    hh.process(update)  # إعادة تسليم نفس التحديث
    assert hh.db.count_outbox() == 1  # مفيش سجل تاني (at-most-once)
    assert hh.db.update_outcome(7100) == uo.DURABLE_INTENT_RECORDED
