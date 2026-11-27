"""OHB2-OPENHANDS-WAIT-UNTIL-TERMINAL-STATUS regression coverage.

These tests exercise the real Watcher/Database path with fake OpenHands clients and a
fake Telegram bot. No network or production task submission is used.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from bot.db import (
    INBOX_DELIVERY_DELIVERED,
    INBOX_KIND_TERMINAL,
    REPORT_STATE_DELIVERED,
    REPORT_STATE_PENDING,
    REPORT_STATE_SENDING,
    REPORT_STATE_TIMED_OUT,
    REPORT_STATE_UNCERTAIN,
    Database,
)
from bot.errors import ApiError
from bot.messages import (
    TASK_CANCELLED,
    TASK_COMPLETED,
    TASK_FAILED,
    TASK_PROVIDER_FINISHED,
    TASK_REPORT_AVAILABLE,
    TASK_REPORT_PENDING,
    TASK_REPORT_UNCERTAIN,
    TASK_RUNNING,
    TASK_TIMED_OUT,
    TASK_UNKNOWN,
    task_state,
    task_state_label,
)
from bot.watcher import MAX_POLL_BACKOFF_SECONDS, Watcher
from bot.web.services import _conversation_dto
from telegram.error import TelegramError

T0 = datetime(2026, 11, 27, 10, 0, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self, now=T0):
        self.now = now

    def __call__(self):
        return self.now


class FakeClient:
    def __init__(self, state="running", *, report=None, conversations_error=None, events_error=None):
        self.state = state
        self.report = report
        self.conversations_error = conversations_error
        self.events_error = events_error
        self.conversation_calls = 0
        self.event_calls = 0

    async def get_conversations(self, ids):
        self.conversation_calls += 1
        if self.conversations_error is not None:
            raise self.conversations_error
        return [
            {"id": cid, "title": "شات", "execution_status": self.state}
            for cid in ids
        ]

    async def get_reply_since(self, conversation_id, since):
        self.event_calls += 1
        if self.events_error is not None:
            raise self.events_error
        return self.report

    async def get_last_reply(self, conversation_id):
        return None


class FakeBot:
    def __init__(self, fail=False, fail_exc=None):
        self.sent = []
        self.fail = fail
        self.fail_exc = fail_exc

    async def send_message(self, chat_id=None, text=None, parse_mode=None, **kwargs):
        if self.fail:
            raise self.fail_exc or RuntimeError("telegram failure")
        self.sent.append(text)


def make_db(tmp_path, *, state="running", submitted=T0):
    db = Database(str(tmp_path / "wait.sqlite3"))
    db.add_watched("c1", "شات", chat_id=5)
    db.set_last_state("c1", state)
    db.mark_submitted("c1", submitted.isoformat())
    return db


def run_tick(db, client, *, now, bot=None):
    bot = bot or FakeBot()
    asyncio.run(Watcher(client, db, bot, chat_id=1, clock=Clock(now)).tick())
    return bot


def test_running_after_ten_minutes_remains_tracked(tmp_path):
    db = make_db(tmp_path)
    bot = run_tick(db, FakeClient("running"), now=T0 + timedelta(minutes=11))
    assert bot.sent == []
    assert db.is_watched("c1")
    assert db.get_watched("c1").last_state == "running"


def test_temporary_polling_timeout_does_not_complete(tmp_path):
    db = make_db(tmp_path)
    bot = run_tick(
        db,
        FakeClient(conversations_error=ApiError("temporary", 503)),
        now=T0 + timedelta(minutes=11),
    )
    assert bot.sent == []
    assert db.is_watched("c1")
    assert db.get_watched("c1").last_state == "running"


def test_missing_final_report_does_not_imply_success(tmp_path):
    db = make_db(tmp_path, state="running")
    bot = run_tick(db, FakeClient("finished"), now=T0 + timedelta(minutes=11))
    assert bot.sent == []
    assert db.is_watched("c1")
    watched = db.get_watched("c1")
    assert watched.last_state == "finished"
    assert watched.report_state == REPORT_STATE_PENDING
    assert watched.conversation_id == "c1"


def test_report_arriving_after_multiple_polling_cycles_is_delivered(tmp_path):
    db = make_db(tmp_path, state="running")
    client = FakeClient("finished")
    first = run_tick(db, client, now=T0 + timedelta(minutes=11))
    assert first.sent == [] and db.is_watched("c1")

    client.report = "التقرير النهائي"
    second = run_tick(db, client, now=T0 + timedelta(minutes=12))
    assert len(second.sent) == 1
    assert "التقرير النهائي" in second.sent[0]
    assert not db.is_watched("c1")


def test_provider_failure_is_failed_not_completed(tmp_path):
    db = make_db(tmp_path, state="running")
    bot = run_tick(db, FakeClient("error"), now=T0 + timedelta(minutes=2))
    assert len(bot.sent) == 1
    assert "خطأ" in bot.sent[0]
    assert not db.is_watched("c1")
    assert task_state("error") == TASK_FAILED


def test_confirmed_cancellation_is_cancelled(tmp_path):
    db = make_db(tmp_path, state="running")
    bot = run_tick(db, FakeClient("cancelled"), now=T0 + timedelta(minutes=2))
    assert len(bot.sent) == 1
    assert "اتلغى" in bot.sent[0]
    assert not db.is_watched("c1")
    assert task_state("cancelled") == TASK_CANCELLED


def test_unknown_provider_state_is_not_success(tmp_path):
    db = make_db(tmp_path, state="running")
    bot = run_tick(db, FakeClient("mystery_state"), now=T0 + timedelta(minutes=11))
    assert bot.sent == []
    assert db.is_watched("c1")
    assert db.get_watched("c1").last_state == "mystery_state"
    assert task_state("mystery_state") == TASK_UNKNOWN


def test_missing_status_field_is_unknown_and_not_success(tmp_path):
    db = make_db(tmp_path, state="running")

    class MissingStatusClient(FakeClient):
        async def get_conversations(self, ids):
            return [{"id": cid, "title": "شات"} for cid in ids]

    bot = run_tick(db, MissingStatusClient(), now=T0 + timedelta(minutes=11))
    assert bot.sent == []
    assert db.is_watched("c1")
    assert db.get_watched("c1").last_state == "unknown"
    assert task_state("unknown") == TASK_UNKNOWN


def test_transient_provider_error_is_retried_safely(tmp_path):
    db = make_db(tmp_path, state="running")
    client = FakeClient("running")
    client.conversations_error = ApiError("network", 503)
    first = run_tick(db, client, now=T0 + timedelta(minutes=1))
    assert first.sent == [] and db.is_watched("c1")

    client.conversations_error = None
    client.state = "finished"
    client.report = "تقرير بعد الخطأ"
    second = run_tick(db, client, now=T0 + timedelta(minutes=2))
    assert len(second.sent) == 1
    assert "تقرير بعد الخطأ" in second.sent[0]


def test_repeated_transient_failures_do_not_complete_and_persist_backoff(tmp_path):
    db = make_db(tmp_path, state="running")
    client = FakeClient(conversations_error=ApiError("network", 503))
    first = run_tick(db, client, now=T0 + timedelta(minutes=1))
    assert first.sent == []
    assert db.is_watched("c1")
    watched = db.get_watched("c1")
    assert watched.poll_failures == 1
    assert watched.next_check_at is not None

    second = run_tick(db, client, now=T0 + timedelta(minutes=2))
    assert second.sent == []
    watched = db.get_watched("c1")
    assert watched.poll_failures >= 2
    assert watched.last_state == "running"
    assert watched.report_state is None


def test_poll_backoff_is_bounded():
    watcher = Watcher(FakeClient(), Database(":memory:"), FakeBot(), chat_id=1, interval=60)
    assert watcher._backoff_delay(1) == 60
    assert watcher._backoff_delay(2) == 120
    assert watcher._backoff_delay(10) == MAX_POLL_BACKOFF_SECONDS


def test_restart_recovery_resumes_running_task(tmp_path):
    path = str(tmp_path / "restart.sqlite3")
    db = Database(path)
    db.add_watched("c1", "شات", chat_id=5)
    db.set_last_state("c1", "running")
    db.mark_submitted("c1", T0.isoformat())
    db.close()

    db2 = Database(path)
    client = FakeClient("running")
    bot = run_tick(db2, client, now=T0 + timedelta(minutes=11))
    assert bot.sent == []
    assert db2.is_watched("c1")
    assert db2.get_watched("c1").last_verified_at is not None
    assert len(db2.list_watched()) == 1
    assert db2.get_watched("c1").conversation_id == "c1"

    client.state = "finished"
    client.report = "تقرير بعد restart"
    bot2 = run_tick(db2, client, now=T0 + timedelta(minutes=12))
    assert len(bot2.sent) == 1
    assert "تقرير بعد restart" in bot2.sent[0]
    assert not db2.is_watched("c1")


def test_duplicate_terminal_responses_do_not_duplicate_delivery(tmp_path):
    db = make_db(tmp_path, state="running")
    client = FakeClient("finished", report="تقرير")
    first = run_tick(db, client, now=T0 + timedelta(minutes=2))
    second = run_tick(db, client, now=T0 + timedelta(minutes=3))
    assert len(first.sent) == 1
    assert second.sent == []
    assert not db.is_watched("c1")


def test_restart_after_delivery_does_not_resend(tmp_path):
    path = str(tmp_path / "delivery.sqlite3")
    db = Database(path)
    db.add_watched("c1", "شات", chat_id=5)
    db.set_last_state("c1", "running")
    db.mark_submitted("c1", T0.isoformat())
    client = FakeClient("finished", report="تقرير")
    first = run_tick(db, client, now=T0 + timedelta(minutes=2))
    assert len(first.sent) == 1
    db.close()

    db2 = Database(path)
    second = run_tick(db2, client, now=T0 + timedelta(minutes=3))
    assert second.sent == []
    assert db2.list_watched() == []


def test_delayed_report_is_not_replaced_by_timeout_completion(tmp_path):
    db = make_db(tmp_path, state="running")
    client = FakeClient("finished")
    first = run_tick(db, client, now=T0 + timedelta(minutes=11))
    assert first.sent == [] and db.is_watched("c1")

    # After the old 10-minute threshold, a delayed report must still be delivered.
    client.report = "تقرير متأخر"
    second = run_tick(db, client, now=T0 + timedelta(minutes=30))
    assert len(second.sent) == 1
    assert "تقرير متأخر" in second.sent[0]
    assert not db.is_watched("c1")


def test_terminal_report_timeout_is_timed_out_not_completed(tmp_path):
    db = make_db(tmp_path, state="running")
    bot = run_tick(db, FakeClient("finished"), now=T0 + timedelta(hours=25))
    assert len(bot.sent) == 1
    assert "لم يتم اعتبار المهمة مكتملة" in bot.sent[0]
    assert not db.is_watched("c1")
    assert task_state("finished") == TASK_PROVIDER_FINISHED
    assert task_state("finished", REPORT_STATE_TIMED_OUT) == TASK_TIMED_OUT
    assert TASK_TIMED_OUT == "timed_out"


def test_permanent_database_error_does_not_complete(tmp_path, monkeypatch):
    db = make_db(tmp_path, state="running")

    def boom(*args, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(db, "note_transition", boom)
    bot = run_tick(
        db,
        FakeClient("finished", report="تقرير"),
        now=T0 + timedelta(minutes=2),
    )
    assert bot.sent == []
    assert db.is_watched("c1")


def test_task_state_mapping_never_marks_unknown_as_completed():
    assert task_state("finished") == TASK_PROVIDER_FINISHED
    assert task_state("finished", REPORT_STATE_DELIVERED) == TASK_COMPLETED
    assert task_state("finished", REPORT_STATE_PENDING) == TASK_REPORT_PENDING
    assert task_state("finished", REPORT_STATE_SENDING) == TASK_REPORT_AVAILABLE
    assert task_state("finished", REPORT_STATE_UNCERTAIN) == TASK_REPORT_UNCERTAIN
    assert task_state("finished", "timed_out") == TASK_TIMED_OUT
    assert task_state("error") == TASK_FAILED
    assert task_state("stuck") == TASK_FAILED
    assert task_state("sandbox_error") == TASK_FAILED
    assert task_state("cancelled") == TASK_CANCELLED
    assert task_state("canceled") == TASK_CANCELLED
    assert task_state("FINISHED") == TASK_PROVIDER_FINISHED
    assert task_state("running") == TASK_RUNNING
    assert task_state("waiting_for_confirmation") == TASK_UNKNOWN
    assert task_state("mystery") == TASK_UNKNOWN
    assert task_state_label(TASK_REPORT_PENDING) == "التقرير قيد الانتظار"


# ---------------------------------------------------------------- P2-1
def test_finished_then_error_after_pending_report_notifies_failure(tmp_path):
    db = make_db(tmp_path, state="running")
    client = FakeClient("finished")
    first = run_tick(db, client, now=T0 + timedelta(minutes=11))
    assert first.sent == [] and db.is_watched("c1")
    assert db.get_watched("c1").report_state == REPORT_STATE_PENDING

    client.state = "error"
    second = run_tick(db, client, now=T0 + timedelta(minutes=12))
    assert len(second.sent) == 1
    assert "خطأ" in second.sent[0]
    assert not db.is_watched("c1")


def test_finished_then_cancelled_after_pending_report_notifies_cancellation(tmp_path):
    db = make_db(tmp_path, state="running")
    client = FakeClient("finished")
    first = run_tick(db, client, now=T0 + timedelta(minutes=11))
    assert first.sent == [] and db.is_watched("c1")

    client.state = "cancelled"
    second = run_tick(db, client, now=T0 + timedelta(minutes=12))
    assert len(second.sent) == 1
    assert "اتلغى" in second.sent[0]
    assert not db.is_watched("c1")


def test_finished_then_canceled_spelling_notifies_cancellation(tmp_path):
    db = make_db(tmp_path, state="running")
    client = FakeClient("finished")
    first = run_tick(db, client, now=T0 + timedelta(minutes=11))
    assert first.sent == [] and db.is_watched("c1")

    client.state = "canceled"
    second = run_tick(db, client, now=T0 + timedelta(minutes=12))
    assert len(second.sent) == 1
    assert "اتلغى" in second.sent[0]
    assert not db.is_watched("c1")


def test_finished_then_error_after_restart_notifies_failure(tmp_path):
    path = str(tmp_path / "transition.sqlite3")
    db = Database(path)
    db.add_watched("c1", "شات", chat_id=5)
    db.set_last_state("c1", "running")
    db.mark_submitted("c1", T0.isoformat())
    first = run_tick(db, FakeClient("finished"), now=T0 + timedelta(minutes=11))
    assert first.sent == [] and db.is_watched("c1")
    db.close()

    db2 = Database(path)
    second = run_tick(
        db2, FakeClient("error"), now=T0 + timedelta(minutes=12)
    )
    assert len(second.sent) == 1
    assert "خطأ" in second.sent[0]
    assert not db2.is_watched("c1")


def test_terminal_transition_retry_does_not_duplicate(tmp_path):
    db = make_db(tmp_path, state="running")
    client = FakeClient("finished")
    first = run_tick(db, client, now=T0 + timedelta(minutes=11))
    assert first.sent == [] and db.is_watched("c1")

    client.state = "error"
    failing = FakeBot(fail=True, fail_exc=TelegramError("rejected"))
    second = run_tick(db, client, now=T0 + timedelta(minutes=12), bot=failing)
    assert second.sent == [] and db.is_watched("c1")

    third = run_tick(db, client, now=T0 + timedelta(minutes=13))
    assert len(third.sent) == 1
    assert "خطأ" in third.sent[0]
    assert not db.is_watched("c1")


# ---------------------------------------------------------------- P2-2
def test_send_failure_before_acceptance_retries(tmp_path):
    db = make_db(tmp_path, state="running")
    client = FakeClient("finished", report="تقرير")
    first = run_tick(
        db,
        client,
        now=T0 + timedelta(minutes=2),
        bot=FakeBot(fail=True, fail_exc=TelegramError("rejected")),
    )
    assert first.sent == []
    assert db.is_watched("c1")
    assert db.get_watched("c1").report_state == REPORT_STATE_PENDING

    second = run_tick(db, client, now=T0 + timedelta(minutes=3))
    assert len(second.sent) == 1
    assert "تقرير" in second.sent[0]
    assert not db.is_watched("c1")


def test_db_marker_failure_after_success_does_not_resend(tmp_path):
    db = make_db(tmp_path, state="running")
    client = FakeClient("finished", report="تقرير")
    original = db.set_report_state

    def fail_delivered(cid, state):
        if state == REPORT_STATE_DELIVERED:
            raise RuntimeError("marker write failed")
        return original(cid, state)

    db.set_report_state = fail_delivered
    first = run_tick(db, client, now=T0 + timedelta(minutes=2))
    assert len(first.sent) == 1
    assert db.is_watched("c1")
    assert db.get_watched("c1").report_state == REPORT_STATE_SENDING

    db.set_report_state = original
    second = run_tick(db, client, now=T0 + timedelta(minutes=3))
    assert second.sent == []
    assert not db.is_watched("c1")


def test_restart_during_uncertain_delivery_does_not_resend(tmp_path):
    path = str(tmp_path / "uncertain.sqlite3")
    db = Database(path)
    db.add_watched("c1", "شات", chat_id=5)
    db.set_last_state("c1", "running")
    db.mark_submitted("c1", T0.isoformat())
    db.set_report_state("c1", REPORT_STATE_SENDING)
    db.close()

    db2 = Database(path)
    client = FakeClient("finished", report="تقرير")
    first = run_tick(db2, client, now=T0 + timedelta(minutes=2))
    assert first.sent == []
    assert db2.is_watched("c1")
    assert db2.get_watched("c1").report_state == REPORT_STATE_UNCERTAIN

    second = run_tick(db2, client, now=T0 + timedelta(minutes=3))
    assert second.sent == []
    assert db2.is_watched("c1")


def test_pending_delivery_event_is_recovered_without_resend(tmp_path):
    path = str(tmp_path / "pending-event.sqlite3")
    db = Database(path)
    db.add_watched("c1", "شات", chat_id=5)
    db.set_last_state("c1", "running")
    db.mark_submitted("c1", T0.isoformat())
    watcher = Watcher(FakeClient(), db, FakeBot(), chat_id=1, clock=Clock())
    _add_terminal_event(db, watcher, delivered=False)
    db.set_report_state("c1", REPORT_STATE_SENDING)
    db.close()

    db2 = Database(path)
    bot = run_tick(db2, FakeClient("finished", report="تقرير"), now=T0 + timedelta(minutes=2))
    assert bot.sent == []
    assert db2.is_watched("c1")
    assert db2.get_watched("c1").report_state == REPORT_STATE_UNCERTAIN


def test_delivered_event_reconciles_uncertain_delivery_without_resend(tmp_path):
    path = str(tmp_path / "delivered-event.sqlite3")
    db = Database(path)
    db.add_watched("c1", "شات", chat_id=5)
    db.set_last_state("c1", "running")
    db.mark_submitted("c1", T0.isoformat())
    watcher = Watcher(FakeClient(), db, FakeBot(), chat_id=1, clock=Clock())
    event_id = _add_terminal_event(db, watcher, delivered=True)
    assert db.get_inbox_item(event_id).delivery_status == INBOX_DELIVERY_DELIVERED
    db.set_report_state("c1", REPORT_STATE_SENDING)
    db.close()

    db2 = Database(path)
    bot = run_tick(db2, FakeClient("finished", report="تقرير"), now=T0 + timedelta(minutes=2))
    assert bot.sent == []
    assert not db2.is_watched("c1")


def test_uncertain_delivery_timeout_is_not_completed(tmp_path):
    db = make_db(tmp_path, state="finished")
    db.set_report_state("c1", REPORT_STATE_SENDING)
    bot = run_tick(db, FakeClient("finished", report="تقرير"), now=T0 + timedelta(hours=25))
    assert len(bot.sent) == 1
    assert "لم يتم اعتبار المهمة مكتملة" in bot.sent[0]
    assert not db.is_watched("c1")


def _add_terminal_event(db, watcher, *, delivered):
    watched = db.get_watched("c1")
    seq = db.note_transition("c1", "finished", terminal=True, now=T0.isoformat())
    key = watcher._inbox_event_key(watched, INBOX_KIND_TERMINAL, seq)
    event_id = db.add_inbox_event(
        "c1", "شات", INBOX_KIND_TERMINAL, "تقرير", T0.isoformat(),
        event_key=key, chat_id=5, transition_status="finished", transition_seq=seq,
    )
    assert event_id is not None
    if delivered:
        db.mark_inbox_delivered(event_id, T0.isoformat())
    return event_id


# ---------------------------------------------------------------- P2-3
def test_mini_app_dto_separates_provider_and_task_state():
    base = {"id": "c1", "execution_status": "finished"}
    pending = _conversation_dto(base, True, REPORT_STATE_PENDING)
    assert pending["status"] == "finished"
    assert pending["state_label"] == "منتهي"
    assert pending["task_state"] == TASK_REPORT_PENDING
    assert pending["task_state_label"] == "التقرير قيد الانتظار"

    delivered = _conversation_dto(base, True, REPORT_STATE_DELIVERED)
    assert delivered["task_state"] == TASK_COMPLETED
    assert delivered["task_state_label"] == "مكتمل"

    available = _conversation_dto(base, True, REPORT_STATE_SENDING)
    assert available["task_state"] == TASK_REPORT_AVAILABLE

    uncertain = _conversation_dto(base, True, REPORT_STATE_UNCERTAIN)
    assert uncertain["task_state"] == TASK_REPORT_UNCERTAIN

    timeout = _conversation_dto(base, True, REPORT_STATE_TIMED_OUT)
    assert timeout["task_state"] == TASK_TIMED_OUT
    assert timeout["task_state_label"] == "انتهت المهلة"

    provider_only = _conversation_dto(base, False)
    assert provider_only["task_state"] == TASK_PROVIDER_FINISHED

    running = _conversation_dto({"id": "c5", "execution_status": "running"}, True, REPORT_STATE_PENDING)
    assert running["task_state"] == TASK_RUNNING
    assert running["status"] == "running"
    assert running["state_label"] == "شغال"

    failed = _conversation_dto({"id": "c2", "execution_status": "error"}, True, REPORT_STATE_PENDING)
    assert failed["task_state"] == TASK_FAILED
    cancelled = _conversation_dto({"id": "c3", "execution_status": "cancelled"}, True, REPORT_STATE_PENDING)
    assert cancelled["task_state"] == TASK_CANCELLED
    unknown = _conversation_dto({"id": "c4", "execution_status": "mystery"}, True, REPORT_STATE_PENDING)
    assert unknown["task_state"] == TASK_UNKNOWN
