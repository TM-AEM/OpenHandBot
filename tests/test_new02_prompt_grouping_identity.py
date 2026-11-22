"""NEW-02 identity/cleanup safety, updated for NEW-04 approved time-window grouping."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from types import SimpleNamespace

import pytest
from telegram.error import TelegramError

import bot.handlers as h
from bot import outbox
from bot.db import (
    CLEANUP_DONE,
    CLEANUP_FAILED,
    OUTBOX_PENDING,
    OUTBOX_SENT,
    Database,
)
from bot.errors import ApiError
from tests.test_handlers import make_context, make_update
from tests.test_outbox import Client, make_worker

OWNER = 1
CID = "A"
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


def _reply(ack_id):
    async def reply(text, **kw):
        return SimpleNamespace(message_id=ack_id)
    return reply


def _route(ctx):
    db = ctx.bot_data["db"]
    db.set_last_accessed_conversation(OWNER, CID)
    db.set_awaiting(OWNER, CID, "route", title=CID)
    return db


def _make_sent(db, *, originals, acks, confirmation=CONFIRM):
    oid = db.add_outbox(CID, OWNER, "prompt", outbox.now_iso(), originals[0])
    for message_id in originals[1:]:
        assert db.add_or_group_outbox(
            CID, OWNER, "part", outbox.now_iso(),
            telegram_message_id=message_id, reply_to_message_id=originals[0],
        ) == oid
    for message_id in acks:
        assert db.add_outbox_ack_message_id(oid, message_id) is True
    db.set_outbox_status(oid, OUTBOX_SENT, outbox.now_iso())
    assert db.begin_outbox_cleanup(
        oid, confirmation, outbox.now_iso(),
        delay_seconds=outbox.CLEANUP_ORIGINAL_DELAY_SECONDS,
    )
    return oid


def _async(coro):
    return asyncio.run(coro)


def test_new02_r1_temporal_window_groups_approved_new04(tmp_path, monkeypatch):
    fixed = "2026-11-22T00:00:00+00:00"
    monkeypatch.setattr(outbox, "now_iso", lambda: fixed)

    async def scenario():
        ctx = make_context(OWNER, tmp_path)
        db = _route(ctx)
        first = make_update(OWNER, "رسالة مستقلة أولى")
        first.update_id = 1001
        first.message.message_id = 101
        first.message.reply_text = _reply(201)
        second = make_update(OWNER, "رسالة مستقلة ثانية")
        second.update_id = 1002
        second.message.message_id = 102
        second.message.reply_text = _reply(202)

        await h.handle_text(first, ctx)
        await h.handle_text(second, ctx)

        rows = db.list_outbox_by_status(OUTBOX_PENDING)
        # NEW-04 explicitly approves time-window grouping: both messages share one
        # durable batch, while each original/ack identity remains tracked for cleanup.
        assert len(rows) == 1
        assert rows[0].text == "رسالة مستقلة أولى\nرسالة مستقلة ثانية"
        assert rows[0].telegram_message_ids == (101, 102)
        assert rows[0].ack_message_ids == (201, 202)
        assert rows[0].created_at == fixed

    _async(scenario())


def test_new02_r2_cleanup_isolation_between_independent_prompts(tmp_path):
    db = Database(str(tmp_path / "r2.sqlite3"))
    try:
        first = _make_sent(db, originals=(11,), acks=(21,), confirmation=901)
        second = _make_sent(db, originals=(31,), acks=(41,), confirmation=902)
        bot = FakeBot()

        _async(outbox._run_persisted_cleanup(db, bot, first, sleep=FakeSleep()))

        assert {message_id for _, message_id in bot.deleted} == {11, 21, 901}
        other = db.get_outbox(second)
        assert other.cleanup_state != CLEANUP_DONE
        assert other.telegram_message_ids == (31,)
        assert other.ack_message_ids == (41,)
    finally:
        db.close()


def test_new02_r3_explicit_reply_parts_form_one_batch_and_cleanup(tmp_path):
    async def scenario():
        ctx = make_context(OWNER, tmp_path)
        db = _route(ctx)
        first = make_update(OWNER, "الجزء الأول")
        first.update_id = 1101
        first.message.message_id = 11
        first.message.reply_text = _reply(21)
        second = make_update(OWNER, "الجزء الثاني")
        second.update_id = 1102
        second.message.message_id = 12
        second.message.reply_to_message = SimpleNamespace(message_id=11)
        second.message.reply_text = _reply(22)

        await h.handle_text(first, ctx)
        await h.handle_text(second, ctx)

        rows = db.list_outbox_by_status(OUTBOX_PENDING)
        assert len(rows) == 1
        item = rows[0]
        assert item.text == "الجزء الأول\nالجزء الثاني"
        assert item.telegram_message_ids == (11, 12)
        assert item.ack_message_ids == (21, 22)
        db.set_outbox_status(item.id, OUTBOX_SENT, outbox.now_iso())
        assert db.begin_outbox_cleanup(
            item.id, CONFIRM, outbox.now_iso(),
            delay_seconds=outbox.CLEANUP_ORIGINAL_DELAY_SECONDS,
        )
        bot = FakeBot()
        await outbox._run_persisted_cleanup(db, bot, item.id, sleep=FakeSleep())
        assert {message_id for _, message_id in bot.deleted} == {11, 12, 21, 22, CONFIRM}

    _async(scenario())


def test_new02_r4_interleaved_prompts_keep_membership(tmp_path):
    db = Database(str(tmp_path / "r4.sqlite3"))
    try:
        first = _make_sent(db, originals=(11, 12), acks=(21, 22), confirmation=901)
        second = _make_sent(db, originals=(31, 32), acks=(41, 42), confirmation=902)
        bot = FakeBot()

        _async(outbox._run_persisted_cleanup(db, bot, first, sleep=FakeSleep()))

        assert {message_id for _, message_id in bot.deleted} == {11, 12, 21, 22, 901}
        assert db.get_outbox(second).telegram_message_ids == (31, 32)
        assert db.get_outbox(second).ack_message_ids == (41, 42)
        assert db.get_outbox(second).cleanup_state != CLEANUP_DONE
    finally:
        db.close()


def test_new02_r4_reply_can_target_older_pending_batch(tmp_path, monkeypatch):
    clock = iter(
        [
            "2026-11-22T00:00:00+00:00",
            "2026-11-22T00:00:04+00:00",
            "2026-11-22T00:00:05+00:00",
        ]
    )
    monkeypatch.setattr(outbox, "now_iso", lambda: next(clock))

    async def scenario():
        ctx = make_context(OWNER, tmp_path)
        db = _route(ctx)
        first = make_update(OWNER, "الأول")
        first.update_id = 1251
        first.message.message_id = 11
        first.message.reply_text = _reply(21)
        independent = make_update(OWNER, "مستقل")
        independent.update_id = 1252
        independent.message.message_id = 12
        independent.message.reply_text = _reply(22)
        continuation = make_update(OWNER, "تكملة الأول")
        continuation.update_id = 1253
        continuation.message.message_id = 13
        continuation.message.reply_to_message = SimpleNamespace(message_id=11)
        continuation.message.reply_text = _reply(23)

        await h.handle_text(first, ctx)
        await h.handle_text(independent, ctx)
        await h.handle_text(continuation, ctx)

        rows = db.list_outbox_by_status(OUTBOX_PENDING)
        assert len(rows) == 2
        assert rows[0].telegram_message_ids == (11, 13)
        assert rows[0].ack_message_ids == (21, 23)
        assert rows[1].telegram_message_ids == (12,)
        assert rows[1].ack_message_ids == (22,)

    _async(scenario())


def test_new02_r5_duplicate_update_does_not_duplicate_membership(tmp_path):
    async def scenario():
        ctx = make_context(OWNER, tmp_path)
        db = _route(ctx)
        update = make_update(OWNER, "رسالة")
        update.update_id = 1201
        update.message.message_id = 11
        update.message.reply_text = _reply(21)

        await h.handle_text(update, ctx)
        await h.handle_text(update, ctx)

        rows = db.list_outbox_by_status(OUTBOX_PENDING)
        assert len(rows) == 1
        assert rows[0].telegram_message_ids == (11,)
        assert rows[0].ack_message_ids == (21,)

    _async(scenario())


def test_new02_r6_partial_cleanup_failure_isolated(tmp_path):
    db = Database(str(tmp_path / "r6.sqlite3"))
    try:
        first = _make_sent(db, originals=(11, 12), acks=(21, 22), confirmation=901)
        second = _make_sent(db, originals=(31,), acks=(41,), confirmation=902)
        bot = FakeBot(fail_always={12})

        _async(outbox._run_persisted_cleanup(db, bot, first, sleep=FakeSleep()))

        item = db.get_outbox(first)
        assert item.cleanup_state == CLEANUP_FAILED
        assert (OWNER, 12) not in bot.deleted
        assert (OWNER, 901) not in bot.deleted
        assert db.get_outbox(second).cleanup_state != CLEANUP_FAILED
        assert db.get_outbox(second).telegram_message_ids == (31,)
    finally:
        db.close()


def test_new02_r7_restart_preserves_each_batch_membership(tmp_path):
    path = str(tmp_path / "r7.sqlite3")
    db = Database(path)
    try:
        first = _make_sent(db, originals=(11, 12), acks=(21, 22), confirmation=901)
        second = _make_sent(db, originals=(31,), acks=(41,), confirmation=902)
    finally:
        db.close()

    reopened = Database(path)
    try:
        bot = FakeBot()
        _async(outbox._run_persisted_cleanup(reopened, bot, first, sleep=FakeSleep()))
        assert {message_id for _, message_id in bot.deleted} == {11, 12, 21, 22, 901}
        assert reopened.get_outbox(second).telegram_message_ids == (31,)
        assert reopened.get_outbox(second).ack_message_ids == (41,)
        assert reopened.get_outbox(second).cleanup_state != CLEANUP_DONE
    finally:
        reopened.close()


def test_new02_r8_concurrent_prompts_group_without_lost_membership(tmp_path):
    async def scenario():
        ctx = make_context(OWNER, tmp_path)
        db = _route(ctx)
        updates = []
        for i in range(4):
            update = make_update(OWNER, f"مستقل {i}")
            update.update_id = 1300 + i
            update.message.message_id = 300 + i
            update.message.reply_text = _reply(400 + i)
            updates.append(update)

        await asyncio.gather(*(h.handle_text(update, ctx) for update in updates))

        rows = db.list_outbox_by_status(OUTBOX_PENDING)
        assert len(rows) == 1
        assert rows[0].telegram_message_ids == tuple(300 + i for i in range(4))
        assert sorted(rows[0].ack_message_ids) == [400 + i for i in range(4)]
        assert rows[0].text.split("\n") == [f"مستقل {i}" for i in range(4)]

    _async(scenario())


def test_new02_r9_outbox_delivery_remains_per_prompt(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "r9.sqlite3"))
    try:
        first = db.add_outbox(CID, OWNER, "أول", "2026-01-01T00:00:00+00:00")
        second = db.add_outbox(CID, OWNER, "تاني", "2026-01-01T00:00:00+00:00")
        client = Client()
        worker = make_worker(db, client=client)
        monkeypatch.setattr("bot.db.GROUP_WINDOW", timedelta(0))

        _async(worker._tick())
        _async(worker._tick())

        assert client.sent == [(CID, "أول"), (CID, "تاني")]
        assert db.get_outbox(first).status == OUTBOX_SENT
        assert db.get_outbox(second).status == OUTBOX_SENT
    finally:
        db.close()


def test_new02_r10_cleanup_timing_is_per_batch(tmp_path):
    db = Database(str(tmp_path / "r10.sqlite3"))
    try:
        first = _make_sent(db, originals=(11,), acks=(21,), confirmation=901)
        second = _make_sent(db, originals=(31,), acks=(41,), confirmation=902)
        sleep_first = FakeSleep()
        sleep_second = FakeSleep()

        _async(outbox._run_persisted_cleanup(db, FakeBot(), first, sleep=sleep_first))
        assert sleep_first.delays == pytest.approx(
            [outbox.CLEANUP_ORIGINAL_DELAY_SECONDS, outbox.CLEANUP_CONFIRMATION_DELAY_SECONDS],
            abs=0.1,
        )
        assert db.get_outbox(second).cleanup_state != CLEANUP_DONE

        _async(outbox._run_persisted_cleanup(db, FakeBot(), second, sleep=sleep_second))
        assert sleep_second.delays == pytest.approx(
            [outbox.CLEANUP_ORIGINAL_DELAY_SECONDS, outbox.CLEANUP_CONFIRMATION_DELAY_SECONDS],
            abs=0.1,
        )
    finally:
        db.close()


def test_new02_r11_no_unknown_or_malformed_id_deletion(tmp_path):
    db = Database(str(tmp_path / "r11.sqlite3"))
    try:
        oid = db.add_outbox(CID, OWNER, "بدون IDs", outbox.now_iso())
        db.set_outbox_status(oid, OUTBOX_SENT, outbox.now_iso())
        assert db.add_outbox_ack_message_id(oid, 0) is False
        assert db.add_outbox_ack_message_id(oid, -1) is False
        assert db.begin_outbox_cleanup(
            oid, CONFIRM, outbox.now_iso(),
            delay_seconds=outbox.CLEANUP_ORIGINAL_DELAY_SECONDS,
        )
        bot = FakeBot()
        _async(outbox._run_persisted_cleanup(db, bot, oid, sleep=FakeSleep()))

        assert bot.deleted == [(OWNER, CONFIRM)]
        assert db.get_outbox(oid).cleanup_state == CLEANUP_DONE
    finally:
        db.close()


def test_new02_r9_delivery_failure_does_not_corrupt_other_prompt(tmp_path, monkeypatch):
    class FailFirstClient(Client):
        def __init__(self):
            super().__init__()
            self.calls = 0

        async def send_message(self, conversation_id, text):
            self.calls += 1
            if self.calls == 1:
                raise ApiError("upstream unavailable", 503)
            self.sent.append((conversation_id, text))

    db = Database(str(tmp_path / "r9b.sqlite3"))
    try:
        first = db.add_outbox(CID, OWNER, "أول", "2026-01-01T00:00:00+00:00")
        second = db.add_outbox(CID, OWNER, "تاني", "2026-01-01T00:00:00+00:00")
        client = FailFirstClient()
        worker = make_worker(db, client=client)
        monkeypatch.setattr("bot.db.GROUP_WINDOW", timedelta(0))

        _async(worker._tick())
        _async(worker._tick())

        assert db.get_outbox(first).status == "unknown"
        assert db.get_outbox(second).status == OUTBOX_SENT
        assert client.sent == [(CID, "تاني")]
    finally:
        db.close()
