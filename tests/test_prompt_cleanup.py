"""Deterministic tests for post-delivery Telegram message cleanup.

The five/ten-second delays are injected as a fake sleep: no real waits, no network.
"""
from __future__ import annotations

import asyncio

import pytest
from telegram.error import TelegramError

import bot.handlers as handlers
from bot import outbox
from bot.db import (
    OUTBOX_SENT,
    OUTBOX_UNKNOWN,
    Database,
)
from bot.outbox import (
    COMPLETION_KIND_OUTBOX,
    _complete_outbox,
    _delete_after_delivery,
    _post_claimed,
    _safe_delete_message,
)

CID = "conv-cleanup"
OWNER = 4242
TEXT = "برومت مهم"
EXACT = "اتبعت ✅ الشات اتضاف للمتابعة."


class FakeMessage:
    def __init__(self, message_id: int):
        self.message_id = message_id


class FakeBot:
    def __init__(self, *, send_error=None, delete_error=None, next_message_id=500):
        self.send_error = send_error
        self.delete_error = delete_error
        self.next_message_id = next_message_id
        self.sent: list[tuple[int, str]] = []
        self.deleted: list[tuple[int, int]] = []

    async def send_message(self, chat_id=None, text=None, **kw):
        if self.send_error is not None:
            raise self.send_error
        self.sent.append((chat_id, text))
        message = FakeMessage(self.next_message_id)
        self.next_message_id += 1
        return message

    async def delete_message(self, chat_id=None, message_id=None, **kw):
        if self.delete_error is not None:
            raise self.delete_error
        self.deleted.append((chat_id, message_id))


class FakeClient:
    def __init__(self, *, send_error=None):
        self.send_error = send_error
        self.send_calls: list[tuple[str, str]] = []

    async def get_conversations(self, ids):
        return [{
            "id": CID,
            "title": "شات",
            "execution_status": "running",
            "sandbox_status": "RUNNING",
        }]

    async def send_message(self, conversation_id, text):
        self.send_calls.append((conversation_id, text))
        if self.send_error is not None:
            raise self.send_error


class FakeSleep:
    def __init__(self):
        self.delays: list[float] = []

    async def __call__(self, delay):
        self.delays.append(delay)


def _db(tmp_path):
    return Database(str(tmp_path / "cleanup.sqlite3"))


def _sent_item(db, *, message_ids=(11, 12)):
    oid = db.add_or_group_outbox(
        CID, OWNER, TEXT, outbox.now_iso(), telegram_message_id=message_ids[0]
    )
    for message_id in message_ids[1:]:
        assert db.add_or_group_outbox(
            CID, OWNER, TEXT, outbox.now_iso(), telegram_message_id=message_id
        ) == oid
    db.set_outbox_status(oid, OUTBOX_SENT, outbox.now_iso())
    db.add_completion_pending(
        COMPLETION_KIND_OUTBOX, oid, OWNER, CID, outbox.now_iso(),
        title="شات", last_state="running", notice_text=EXACT,
    )
    return oid, db.get_completion_pending(COMPLETION_KIND_OUTBOX, oid)


def _claimed_item(db, *, message_ids=(11,)):
    oid = db.add_outbox(
        CID, OWNER, TEXT, outbox.now_iso(), telegram_message_id=message_ids[0]
    )
    item = db.claim_outbox(outbox.now_iso())
    assert item is not None and item.id == oid
    return oid, item


def test_original_not_deleted_when_confirmation_send_fails(tmp_path, monkeypatch):
    db = _db(tmp_path)
    _, pending = _sent_item(db)
    bot = FakeBot(send_error=TelegramError("telegram down"))
    scheduled = []
    monkeypatch.setattr(outbox, "schedule_delivery_cleanup", lambda *a, **k: scheduled.append((a, k)))

    asyncio.run(_complete_outbox(db, bot, pending))

    assert bot.sent == []
    assert bot.deleted == []
    assert scheduled == []
    assert db.get_completion_pending(COMPLETION_KIND_OUTBOX, pending.ref_id) is not None


def test_original_not_deleted_for_pending_or_unknown_delivery(tmp_path, monkeypatch):
    db = _db(tmp_path)
    _, item = _claimed_item(db)
    bot = FakeBot()
    scheduled = []
    monkeypatch.setattr(outbox, "schedule_delivery_cleanup", lambda *a, **k: scheduled.append((a, k)))

    asyncio.run(_post_claimed(FakeClient(send_error=RuntimeError("ambiguous")), db, bot, item))

    assert db.get_outbox(item.id).status == OUTBOX_UNKNOWN
    assert scheduled == []
    assert bot.deleted == []


def test_confirmation_immediately_after_success_and_exact_text(tmp_path, monkeypatch):
    db = _db(tmp_path)
    oid, pending = _sent_item(db)
    bot = FakeBot()
    calls = []
    monkeypatch.setattr(
        outbox, "schedule_delivery_cleanup",
        lambda *a, **k: calls.append((a, k)),
    )

    asyncio.run(_complete_outbox(db, bot, pending))

    assert bot.sent == [(OWNER, EXACT)]
    assert db.is_watched(CID) is True
    assert db.get_completion_pending(COMPLETION_KIND_OUTBOX, oid) is None
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[0] is bot
    assert args[1] == OWNER
    assert args[2] == (11, 12)
    assert args[3] == 500
    assert kwargs["key"] == oid


def test_confirmation_is_not_sent_for_failed_delivery(tmp_path):
    db = _db(tmp_path)
    _, item = _claimed_item(db)
    bot = FakeBot()
    client = FakeClient(send_error=RuntimeError("failed after post"))

    asyncio.run(_post_claimed(client, db, bot, item))

    assert [text for _, text in bot.sent if text == EXACT] == []
    assert db.get_outbox(item.id).status == OUTBOX_UNKNOWN


def test_delete_order_and_delays_are_sequential(tmp_path):
    bot = FakeBot()
    sleep = FakeSleep()

    asyncio.run(_delete_after_delivery(bot, OWNER, (11, 12), 500, sleep=sleep))

    assert sleep.delays == [
        outbox.CLEANUP_ORIGINAL_DELAY_SECONDS,
        outbox.CLEANUP_CONFIRMATION_DELAY_SECONDS,
    ]
    assert bot.deleted == [(OWNER, 11), (OWNER, 12), (OWNER, 500)]
    # رسالة التأكيد تُحذف بعد الأصل، وليس في نفس المرحلة.
    assert bot.deleted.index((OWNER, 500)) > bot.deleted.index((OWNER, 12))


def test_confirmation_and_original_have_separate_ids(tmp_path):
    bot = FakeBot(next_message_id=777)
    sleep = FakeSleep()

    asyncio.run(_delete_after_delivery(bot, OWNER, (11,), 777, sleep=sleep))

    assert (OWNER, 11) in bot.deleted
    assert (OWNER, 777) in bot.deleted
    assert 11 != 777


def test_deletion_failure_does_not_change_successful_delivery(tmp_path, monkeypatch):
    db = _db(tmp_path)
    oid, pending = _sent_item(db)
    bot = FakeBot(delete_error=TelegramError("already deleted"))
    monkeypatch.setattr(
        outbox, "schedule_delivery_cleanup",
        lambda *a, **k: None,
    )

    asyncio.run(_complete_outbox(db, bot, pending))

    assert db.get_outbox(oid).status == OUTBOX_SENT
    assert db.get_completion_pending(COMPLETION_KIND_OUTBOX, oid) is None


def test_schedule_failure_does_not_change_successful_delivery(tmp_path, monkeypatch):
    db = _db(tmp_path)
    oid, pending = _sent_item(db)
    bot = FakeBot()

    def _boom(*_a, **_k):
        raise RuntimeError("scheduler unavailable")

    monkeypatch.setattr(outbox, "schedule_delivery_cleanup", _boom)

    asyncio.run(_complete_outbox(db, bot, pending))

    assert db.get_outbox(oid).status == OUTBOX_SENT
    assert db.get_completion_pending(COMPLETION_KIND_OUTBOX, oid) is None
    assert bot.sent == [(OWNER, EXACT)]


def test_already_deleted_message_is_harmless():
    bot = FakeBot(delete_error=TelegramError("message to delete not found"))

    result = asyncio.run(_safe_delete_message(bot, OWNER, 11))

    assert result is False
    assert bot.deleted == []


def test_unrelated_message_is_never_deleted():
    bot = FakeBot()
    sleep = FakeSleep()

    asyncio.run(_delete_after_delivery(bot, OWNER, (11,), 500, sleep=sleep))

    assert (OWNER, 999) not in bot.deleted
    assert {message_id for _, message_id in bot.deleted} == {11, 500}


def test_duplicate_completion_does_not_repeat_confirmation_or_schedule(tmp_path, monkeypatch):
    db = _db(tmp_path)
    oid, pending = _sent_item(db)
    bot = FakeBot()
    calls = []
    monkeypatch.setattr(
        outbox, "schedule_delivery_cleanup",
        lambda *a, **k: calls.append((a, k)),
    )

    asyncio.run(_complete_outbox(db, bot, pending))
    asyncio.run(_complete_outbox(db, bot, pending))

    assert bot.sent == [(OWNER, EXACT)]
    assert len(calls) == 1
    assert db.get_completion_pending(COMPLETION_KIND_OUTBOX, oid) is None


def test_send_prompt_does_not_schedule_cleanup_before_delivery(tmp_path, monkeypatch):
    from tests.test_handlers import make_context, make_update

    ctx = make_context(OWNER, tmp_path)
    ctx.bot_data["db"].set_awaiting(OWNER, CID, "reply")
    update = make_update(OWNER, "برومت")
    update.message.message_id = 322
    update.update_id = 12346
    calls = []
    monkeypatch.setattr(
        outbox, "schedule_delivery_cleanup",
        lambda *a, **k: calls.append((a, k)),
    )

    asyncio.run(handlers.handle_text(update, ctx))

    assert calls == []
    assert ctx.bot_data["db"].count_outbox("pending") == 1


def test_send_prompt_stores_original_telegram_message_id(tmp_path):
    from tests.test_handlers import make_context, make_update

    ctx = make_context(OWNER, tmp_path)
    ctx.bot_data["db"].set_awaiting(OWNER, CID, "reply")
    update = make_update(OWNER, "برومت")
    update.message.message_id = 321
    update.update_id = 12345

    asyncio.run(handlers.handle_text(update, ctx))

    item = ctx.bot_data["db"].get_outbox(1)
    assert item is not None
    assert item.telegram_message_ids == (321,)


def test_multiple_rapid_messages_keep_independent_ids(tmp_path):
    db = _db(tmp_path)

    oid = db.add_or_group_outbox(
        CID, OWNER, "أول", outbox.now_iso(), telegram_message_id=11
    )
    assert db.add_or_group_outbox(
        CID, OWNER, "تاني", outbox.now_iso(), telegram_message_id=12
    ) == oid
    other = db.add_or_group_outbox(
        "other-conversation", OWNER, "تالت", outbox.now_iso(), telegram_message_id=13
    )

    assert db.get_outbox(oid).telegram_message_ids == (11, 12)
    assert db.get_outbox(other).telegram_message_ids == (13,)


def test_existing_outbox_success_contract_remains_sent(tmp_path, monkeypatch):
    db = _db(tmp_path)
    oid, item = _claimed_item(db)
    bot = FakeBot()
    monkeypatch.setattr(outbox, "schedule_delivery_cleanup", lambda *a, **k: None)

    asyncio.run(_post_claimed(FakeClient(), db, bot, item))

    assert db.get_outbox(oid).status == OUTBOX_SENT
    assert bot.sent == [(OWNER, EXACT)]


def test_cleanup_task_tracking_can_be_cancelled():
    async def _run():
        task = asyncio.create_task(asyncio.sleep(3600))
        outbox._cleanup_tasks.add(task)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        outbox._cleanup_tasks.discard(task)

    asyncio.run(_run())
    assert all(t.done() for t in outbox._cleanup_tasks)


def test_schedule_is_deduplicated_by_outbox_key(monkeypatch):
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
    key = 987654321
    outbox._cleanup_keys.discard(key)

    outbox.schedule_delivery_cleanup(FakeBot(), OWNER, (11,), 500, key=key)
    outbox.schedule_delivery_cleanup(FakeBot(), OWNER, (11,), 500, key=key)

    assert len(created) == 1
    outbox._cleanup_keys.discard(key)
    outbox._cleanup_tasks.clear()


def test_cleanup_cancellation_propagates():
    async def cancelled_sleep(_delay):
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            _delete_after_delivery(FakeBot(), OWNER, (11,), 500, sleep=cancelled_sleep)
        )


def test_shutdown_cancels_pending_cleanup_tasks():
    async def _run():
        task = asyncio.create_task(asyncio.sleep(3600))
        outbox._cleanup_tasks.add(task)
        outbox._cleanup_keys.add(123456)
        await outbox.cancel_cleanup_tasks()
        return task

    task = asyncio.run(_run())

    assert task.cancelled() is True
    assert outbox._cleanup_tasks == set()
    assert outbox._cleanup_keys == set()
