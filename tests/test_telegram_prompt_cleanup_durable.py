"""Durable cleanup regressions for long/multi-message Telegram prompts.

No real sleeps or network: a controllable fake sleep and fake Telegram bot.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from telegram.error import TelegramError

from bot import outbox
from bot.db import (
    CLEANUP_CONFIRMATION_PENDING,
    CLEANUP_DONE,
    CLEANUP_FAILED,
    CLEANUP_ORIGINALS_PENDING,
    OUTBOX_PENDING,
    OUTBOX_SENT,
    Database,
)

OWNER = 4242
CID = "conv-durable"
CONFIRM = 900


class FakeBot:
    def __init__(self, *, fail_once=(), fail_always=()):
        self.deleted: list[tuple[int, int]] = []
        self.fail_once = set(fail_once)
        self.fail_always = set(fail_always)

    async def delete_message(self, chat_id=None, message_id=None, **kw):
        if message_id in self.fail_always or message_id in self.fail_once:
            self.fail_once.discard(message_id)
            raise TelegramError("temporary delete failure")
        self.deleted.append((chat_id, message_id))


class FakeSleep:
    def __init__(self):
        self.delays: list[float] = []

    async def __call__(self, delay):
        self.delays.append(delay)


def _db(tmp_path):
    return Database(str(tmp_path / "durable.sqlite3"))


def _sent_batch(db, originals=(11, 12), acks=(21, 22)):
    oid = db.add_or_group_outbox(
        CID, OWNER, "جزء أول", outbox.now_iso(), telegram_message_id=originals[0]
    )
    for message_id in originals[1:]:
        assert db.add_or_group_outbox(
            CID, OWNER, "جزء تاني", outbox.now_iso(),
            telegram_message_id=message_id, reply_to_message_id=originals[0],
        ) == oid
    for message_id in acks:
        assert db.add_outbox_ack_message_id(oid, message_id) is True
    db.set_outbox_status(oid, OUTBOX_SENT, outbox.now_iso())
    return oid


def _begin(db, oid, *, confirmation_id=CONFIRM):
    assert db.begin_outbox_cleanup(
        oid, confirmation_id, outbox.now_iso(),
        delay_seconds=outbox.CLEANUP_ORIGINAL_DELAY_SECONDS,
    )


def test_multi_message_batch_deletes_all_originals_acks_then_confirmation(tmp_path):
    db = _db(tmp_path)
    oid = _sent_batch(db)
    _begin(db, oid)
    bot = FakeBot()
    sleep = FakeSleep()

    asyncio.run(outbox._run_persisted_cleanup(db, bot, oid, sleep=sleep))

    assert bot.deleted == [
        (OWNER, 11), (OWNER, 12), (OWNER, 21), (OWNER, 22), (OWNER, CONFIRM),
    ]
    assert sleep.delays == pytest.approx(
        [outbox.CLEANUP_ORIGINAL_DELAY_SECONDS, outbox.CLEANUP_CONFIRMATION_DELAY_SECONDS],
        abs=0.1,
    )
    assert db.get_outbox(oid).cleanup_state == CLEANUP_DONE


def test_cleanup_never_deletes_unrelated_consecutive_message(tmp_path):
    db = _db(tmp_path)
    oid = _sent_batch(db, originals=(11,), acks=())
    # A separate outbox row/message is not part of this logical batch.
    other = db.add_outbox(CID, OWNER, "رسالة مستقلة", outbox.now_iso(), telegram_message_id=999)
    _begin(db, oid)
    bot = FakeBot()

    asyncio.run(outbox._run_persisted_cleanup(db, bot, oid, sleep=FakeSleep()))

    assert (OWNER, 999) not in bot.deleted
    assert db.get_outbox(other).telegram_message_ids == (999,)


def test_two_batches_have_independent_cleanup_ownership(tmp_path):
    db = _db(tmp_path)
    first = _sent_batch(db, originals=(11,), acks=(21,))
    second = _sent_batch(db, originals=(31,), acks=(41,))
    _begin(db, first)
    bot = FakeBot()

    asyncio.run(outbox._run_persisted_cleanup(db, bot, first, sleep=FakeSleep()))

    assert {message_id for _, message_id in bot.deleted} == {11, 21, CONFIRM}
    assert db.get_outbox(second).cleanup_state == ""
    assert db.get_outbox(second).telegram_message_ids == (31,)


def test_partial_deletion_failure_is_persisted_and_not_reported_done(tmp_path):
    db = _db(tmp_path)
    oid = _sent_batch(db)
    _begin(db, oid)
    bot = FakeBot(fail_always={12})

    asyncio.run(outbox._run_persisted_cleanup(db, bot, oid, sleep=FakeSleep()))

    item = db.get_outbox(oid)
    assert item.cleanup_state == CLEANUP_FAILED
    assert item.cleanup_attempts == outbox.MAX_CLEANUP_ATTEMPTS
    assert (OWNER, CONFIRM) not in bot.deleted
    assert (OWNER, 12) not in bot.deleted


def test_transient_deletion_failure_retries_then_completes(tmp_path):
    db = _db(tmp_path)
    oid = _sent_batch(db)
    _begin(db, oid)
    bot = FakeBot(fail_once={12})
    sleep = FakeSleep()

    asyncio.run(outbox._run_persisted_cleanup(db, bot, oid, sleep=sleep))

    assert (OWNER, 12) in bot.deleted
    assert (OWNER, CONFIRM) in bot.deleted
    assert db.get_outbox(oid).cleanup_state == CLEANUP_DONE
    assert db.get_outbox(oid).cleanup_attempts == 0


def test_restart_before_first_deletion_resumes_from_sqlite(tmp_path):
    db_path = str(tmp_path / "restart.sqlite3")
    db = Database(db_path)
    oid = _sent_batch(db)
    _begin(db, oid)
    db.close()

    reopened = Database(db_path)
    try:
        bot = FakeBot()
        asyncio.run(
            outbox._run_persisted_cleanup(reopened, bot, oid, sleep=FakeSleep())
        )
        assert {message_id for _, message_id in bot.deleted} == {
            11, 12, 21, 22, CONFIRM,
        }
        assert reopened.get_outbox(oid).cleanup_state == CLEANUP_DONE
    finally:
        reopened.close()


def test_restart_between_original_and_confirmation_deletion(tmp_path):
    db_path = str(tmp_path / "restart-mid.sqlite3")
    db = Database(db_path)
    oid = _sent_batch(db)
    _begin(db, oid)
    # Simulate a completed first stage before the process died.
    assert db.mark_outbox_cleanup_originals_done(
        oid, outbox.now_iso(), delay_seconds=outbox.CLEANUP_CONFIRMATION_DELAY_SECONDS
    )
    db.close()

    reopened = Database(db_path)
    try:
        bot = FakeBot()
        asyncio.run(
            outbox._run_persisted_cleanup(reopened, bot, oid, sleep=FakeSleep())
        )
        assert bot.deleted == [(OWNER, CONFIRM)]
        assert reopened.get_outbox(oid).cleanup_state == CLEANUP_DONE
    finally:
        reopened.close()


def test_recover_schedules_each_pending_row_once(tmp_path, monkeypatch):
    db = _db(tmp_path)
    oid = _sent_batch(db)
    _begin(db, oid)
    created = []

    class FakeTask:
        def add_done_callback(self, callback):
            self.callback = callback

    def fake_create_task(coro):
        coro.close()
        task = FakeTask()
        created.append(task)
        return task

    monkeypatch.setattr(outbox.asyncio, "create_task", fake_create_task)
    app = SimpleNamespace(bot_data={"db": db}, bot=FakeBot())
    outbox._cleanup_keys.clear()

    outbox.resume_outbox_cleanup(app)
    outbox.resume_outbox_cleanup(app)

    assert len(created) == 1
    outbox._cleanup_keys.clear()
    outbox._cleanup_tasks.clear()


def test_pending_or_failed_delivery_cannot_start_cleanup(tmp_path):
    db = _db(tmp_path)
    oid = db.add_or_group_outbox(CID, OWNER, "لسه", outbox.now_iso(), telegram_message_id=11)

    assert db.begin_outbox_cleanup(
        oid, CONFIRM, outbox.now_iso(), delay_seconds=5.0
    ) is False
    assert db.get_outbox(oid).cleanup_state == ""
    assert db.get_outbox(oid).status == OUTBOX_PENDING


def test_missing_confirmation_id_does_not_claim_cleanup_complete(tmp_path):
    db = _db(tmp_path)
    oid = _sent_batch(db, originals=(11,), acks=())
    _begin(db, oid, confirmation_id=None)
    bot = FakeBot()

    asyncio.run(outbox._run_persisted_cleanup(db, bot, oid, sleep=FakeSleep()))

    item = db.get_outbox(oid)
    assert item.cleanup_state == CLEANUP_FAILED
    assert item.cleanup_confirmation_message_id is None
    assert (OWNER, 11) in bot.deleted


def test_duplicate_scheduling_is_deduplicated_by_outbox_id(tmp_path, monkeypatch):
    db = _db(tmp_path)
    oid = _sent_batch(db)
    _begin(db, oid)
    created = []

    class FakeTask:
        def add_done_callback(self, callback):
            self.callback = callback

    def fake_create_task(coro):
        coro.close()
        created.append(FakeTask())
        return created[-1]

    monkeypatch.setattr(outbox.asyncio, "create_task", fake_create_task)
    outbox._cleanup_keys.clear()
    outbox.schedule_delivery_cleanup(
        FakeBot(), OWNER, (11, 12), CONFIRM,
        key=oid, ack_message_ids=(21, 22), db=db, outbox_id=oid,
    )
    outbox.schedule_delivery_cleanup(
        FakeBot(), OWNER, (11, 12), CONFIRM,
        key=oid, ack_message_ids=(21, 22), db=db, outbox_id=oid,
    )

    assert len(created) == 1
    outbox._cleanup_keys.clear()
    outbox._cleanup_tasks.clear()


def test_cleanup_state_stages_are_explicit(tmp_path):
    db = _db(tmp_path)
    oid = _sent_batch(db)
    _begin(db, oid)
    assert db.get_outbox(oid).cleanup_state == CLEANUP_ORIGINALS_PENDING
    assert db.mark_outbox_cleanup_originals_done(
        oid, outbox.now_iso(), delay_seconds=5.0
    )
    assert db.get_outbox(oid).cleanup_state == CLEANUP_CONFIRMATION_PENDING


class _ConfirmBot:
    def __init__(self):
        self.sent = []
        self.deleted = []

    async def send_message(self, chat_id=None, text=None, **kw):
        self.sent.append((chat_id, text))
        return SimpleNamespace(message_id=CONFIRM)

    async def delete_message(self, chat_id=None, message_id=None, **kw):
        self.deleted.append((chat_id, message_id))


def test_completion_persists_cleanup_plan_with_tracked_ack_ids(tmp_path, monkeypatch):
    from bot.outbox import COMPLETION_KIND_OUTBOX, _complete_outbox

    db = _db(tmp_path)
    oid = db.add_or_group_outbox(
        CID, OWNER, "برومت", outbox.now_iso(), telegram_message_id=11
    )
    assert db.add_outbox_ack_message_id(oid, 21) is True
    db.set_outbox_status(oid, OUTBOX_SENT, outbox.now_iso())
    db.add_completion_pending(
        COMPLETION_KIND_OUTBOX, oid, OWNER, CID, outbox.now_iso(),
        title="شات", last_state="running", notice_text="اتبعت ✅",
    )
    pending = db.get_completion_pending(COMPLETION_KIND_OUTBOX, oid)
    scheduled = []
    monkeypatch.setattr(
        outbox, "schedule_delivery_cleanup",
        lambda *a, **k: scheduled.append((a, k)),
    )

    bot = _ConfirmBot()
    asyncio.run(_complete_outbox(db, bot, pending))

    item = db.get_outbox(oid)
    assert item.cleanup_state == CLEANUP_ORIGINALS_PENDING
    assert item.cleanup_confirmation_message_id == CONFIRM
    assert item.ack_message_ids == (21,)
    assert scheduled and scheduled[0][1]["ack_message_ids"] == (21,)
    assert scheduled[0][1]["db"] is db
    assert scheduled[0][1]["outbox_id"] == oid

    asyncio.run(outbox._run_persisted_cleanup(db, bot, oid, sleep=FakeSleep()))
    assert {message_id for _, message_id in bot.deleted} == {11, 21, CONFIRM}
    assert db.get_outbox(oid).cleanup_state == CLEANUP_DONE
