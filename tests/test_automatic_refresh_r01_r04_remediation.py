"""Regression tests for OHB2-AUTOMATIC-REFRESH-R01-R04-REMEDIATION."""
import asyncio
import sqlite3
from types import SimpleNamespace

import pytest
from telegram.error import BadRequest, TelegramError

import bot.handlers as h
import bot.refresh as refresh_module
from bot import keyboards as kb
from bot.db import Database
from bot.message_edit import MessageEditCoordinator, get_message_edit_coordinator
from bot.refresh import ConversationRefreshService, RefreshInvalidationError
from bot.sender import send_long
from tests.test_automatic_conversation_refresh import (
    CID, OWNER_ID, Clock, FakeBot, FakeClient, FakeConfig, make_service, record,
)
from tests.test_automatic_conversation_refresh_remediation import (
    CID2, BlockingClient, FakeQ, _ctx, _update,
)


class SharedMessage:
    def __init__(self, *, chat_id=OWNER_ID, message_id=100):
        self.chat_id = chat_id
        self.message_id = message_id
        self.text = "old"
        self.edits = []

    async def edit_text(self, text, **kwargs):
        self.text = text
        self.edits.append(text)


class SharedBot:
    def __init__(self, message, *, block=False):
        self.message = message
        self.block = block
        self.edit_started = asyncio.Event()
        self.release = asyncio.Event()
        self.edits = []

    async def edit_message_text(self, **kwargs):
        self.edit_started.set()
        if self.block:
            await self.release.wait()
        self.message.text = kwargs["text"]
        self.edits.append((kwargs["chat_id"], kwargs["message_id"], kwargs["text"]))


class SharedQ:
    def __init__(self, message, data="menu"):
        self.data = data
        self.message = message
        self.edits = []

    async def answer(self, *args, **kwargs):
        return None

    async def edit_message_text(self, text, **kwargs):
        self.edits.append(text)
        await self.message.edit_text(text, **kwargs)


class MultiClient(FakeClient):
    async def get_conversations(self, ids):
        return [dict(self.conv, id=ids[0])]


class ParallelBot(SharedBot):
    def __init__(self):
        super().__init__(SharedMessage())
        self.started = {}
        self.release_all = asyncio.Event()
        self.edits = []

    async def edit_message_text(self, **kwargs):
        key = (kwargs["chat_id"], kwargs["message_id"])
        self.started.setdefault(key, asyncio.Event()).set()
        await self.release_all.wait()
        self.edits.append(key)


class FileBot(FakeBot):
    async def send_document(self, **kwargs):
        self.sent.append("file")


def _service_with_shared_bot(tmp_path, bot, client=None, cache=None):
    db = Database(str(tmp_path / "r01.sqlite3"))
    service = ConversationRefreshService(
        client or FakeClient(exchange=("برومت", "رد جديد")),
        db,
        bot,
        clock=Clock(),
        exchange_cache=cache,
    )
    return db, service


def _claim(service):
    return service.db.claim_due_conversation_view(
        service.now_iso(), service.deadline(120)
    )


def test_refresh_in_flight_navigation_waits_and_new_screen_wins(tmp_path):
    message = SharedMessage()
    bot = SharedBot(message, block=True)
    db, service = _service_with_shared_bot(tmp_path, bot)
    service.record_view(
        telegram_id=OWNER_ID,
        conversation_id=CID,
        chat_id=OWNER_ID,
        message_id=100,
        text="old",
        markup=kb.conversation_actions(CID),
        terminal=False,
    )
    service.request_immediate(CID, OWNER_ID)
    target = _claim(service)

    async def scenario():
        refresh_task = asyncio.create_task(service.refresh(target))
        await asyncio.wait_for(bot.edit_started.wait(), 1)
        q = SharedQ(message)
        context = SimpleNamespace(
            bot=bot,
            bot_data={
                "config": FakeConfig(),
                "db": db,
                "client": service.client,
                "refresh_service": service,
            },
        )
        navigation_task = asyncio.create_task(h.show_menu(_update(q), context))
        await asyncio.sleep(0)
        assert not navigation_task.done()
        assert q.edits == []
        bot.release.set()
        await refresh_task
        await navigation_task
        assert q.edits
        assert message.text == q.edits[-1]
        assert message.edits[-1] == q.edits[-1]

    asyncio.run(scenario())
    assert get_message_edit_coordinator().active_key_count() == 0
    assert not db.get_conversation_view(OWNER_ID, CID).active
    assert db.get_conversation_view(OWNER_ID, CID).superseded is True


def test_navigation_wins_before_refresh_acquires_edit_right(tmp_path):
    client = BlockingClient(exchange=("برومت", "رد جديد"))
    bot = FakeBot()
    db, service = _service_with_shared_bot(tmp_path, bot, client=client)
    service.record_view(
        telegram_id=OWNER_ID,
        conversation_id=CID,
        chat_id=OWNER_ID,
        message_id=100,
        text="old",
        markup=kb.conversation_actions(CID),
        terminal=False,
    )
    target = db.get_conversation_view(OWNER_ID, CID)

    async def scenario():
        refresh_task = asyncio.create_task(service.refresh(target))
        await asyncio.wait_for(client.fetch_started.wait(), 1)
        q = FakeQ("menu")
        context = _ctx(db, service, client, bot)
        await h.show_menu(_update(q), context)
        client.release_fetch.set()
        await refresh_task
        assert q.edits
        assert bot.edits == []

    asyncio.run(scenario())


def test_two_different_messages_can_edit_independently(tmp_path):
    bot = ParallelBot()
    client = MultiClient(exchange=("برومت", "رد جديد"))
    db, service = _service_with_shared_bot(tmp_path, bot, client=client)
    service.record_view(
        telegram_id=OWNER_ID, conversation_id=CID, chat_id=OWNER_ID,
        message_id=100, text="old", markup=None, terminal=False,
    )
    service.record_view(
        telegram_id=OWNER_ID, conversation_id=CID2, chat_id=OWNER_ID,
        message_id=200, text="old", markup=None, terminal=False,
    )
    t1 = db.get_conversation_view(OWNER_ID, CID)
    t2 = db.get_conversation_view(OWNER_ID, CID2)
    bot.started[(OWNER_ID, 100)] = asyncio.Event()
    bot.started[(OWNER_ID, 200)] = asyncio.Event()

    async def scenario():
        task1 = asyncio.create_task(service.refresh(t1))
        task2 = asyncio.create_task(service.refresh(t2))
        await asyncio.gather(
            asyncio.wait_for(bot.started[(OWNER_ID, 100)].wait(), 1),
            asyncio.wait_for(bot.started[(OWNER_ID, 200)].wait(), 1),
        )
        bot.release_all.set()
        await asyncio.gather(task1, task2)
        assert set(bot.edits) == {(OWNER_ID, 100), (OWNER_ID, 200)}

    asyncio.run(scenario())


def test_two_conversations_same_message_do_not_interleave_stale_edit(tmp_path):
    message = SharedMessage()
    bot = SharedBot(message, block=True)
    db, service = _service_with_shared_bot(tmp_path, bot)
    service.record_view(
        telegram_id=OWNER_ID, conversation_id=CID, chat_id=OWNER_ID,
        message_id=100, text="old", markup=None, terminal=False,
    )
    service.request_immediate(CID, OWNER_ID)
    old_target = _claim(service)

    async def scenario():
        old_task = asyncio.create_task(service.refresh(old_target))
        await asyncio.wait_for(bot.edit_started.wait(), 1)
        service.record_view(
            telegram_id=OWNER_ID, conversation_id=CID2, chat_id=OWNER_ID,
            message_id=100, text="old2", markup=None, terminal=False,
        )
        new_target = db.get_conversation_view(OWNER_ID, CID2)
        new_task = asyncio.create_task(service.refresh(new_target))
        await asyncio.sleep(0)
        bot.release.set()
        await old_task
        await new_task
        assert db.get_conversation_view(OWNER_ID, CID).superseded is True
        assert db.get_conversation_view(OWNER_ID, CID2).superseded is False

    asyncio.run(scenario())


def test_cancellation_releases_edit_right(tmp_path):
    message = SharedMessage()
    bot = SharedBot(message, block=True)
    db, service = _service_with_shared_bot(tmp_path, bot)
    service.record_view(
        telegram_id=OWNER_ID, conversation_id=CID, chat_id=OWNER_ID,
        message_id=100, text="old", markup=None, terminal=False,
    )
    service.request_immediate(CID, OWNER_ID)
    target = _claim(service)

    async def scenario():
        refresh_task = asyncio.create_task(service.refresh(target))
        await asyncio.wait_for(bot.edit_started.wait(), 1)
        refresh_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await refresh_task
        q = SharedQ(message)
        context = SimpleNamespace(
            bot=bot,
            bot_data={
                "config": FakeConfig(),
                "db": db,
                "client": service.client,
                "refresh_service": service,
            },
        )
        await h.show_menu(_update(q), context)
        assert q.edits
        assert message.text == q.edits[-1]

    asyncio.run(scenario())


async def _raising_edit(**kwargs):
    raise TelegramError("network down")


def test_network_failure_releases_edit_right(tmp_path):
    message = SharedMessage()
    bot = SharedBot(message, block=False)
    bot.edit_message_text = _raising_edit
    db, service = _service_with_shared_bot(tmp_path, bot)
    service.record_view(
        telegram_id=OWNER_ID, conversation_id=CID, chat_id=OWNER_ID,
        message_id=100, text="old", markup=None, terminal=False,
    )

    async def scenario():
        await service.refresh(db.get_conversation_view(OWNER_ID, CID))
        q = SharedQ(message)
        context = SimpleNamespace(
            bot=bot,
            bot_data={
                "config": FakeConfig(),
                "db": db,
                "client": service.client,
                "refresh_service": service,
            },
        )
        await h.show_menu(_update(q), context)
        assert q.edits
        assert message.text == q.edits[-1]

    asyncio.run(scenario())
    assert get_message_edit_coordinator().active_key_count() == 0


def test_coordinator_has_one_lock_per_key_and_cleans_up():
    coordinator = MessageEditCoordinator()

    async def scenario():
        first_entered = asyncio.Event()
        release = asyncio.Event()
        order = []

        async def holder(name):
            async with coordinator.lock(OWNER_ID, 100):
                order.append(name)
                first_entered.set()
                await release.wait()

        first = asyncio.create_task(holder("first"))
        await asyncio.wait_for(first_entered.wait(), 1)
        second = asyncio.create_task(holder("second"))
        await asyncio.sleep(0)
        assert order == ["first"]
        assert coordinator.active_key_count() == 1
        release.set()
        await asyncio.gather(first, second)
        assert coordinator.active_key_count() == 0

    asyncio.run(scenario())


def test_permanent_invalidation_failure_blocks_navigation(tmp_path):
    client = FakeClient(exchange=("برومت", "رد"))
    bot = FakeBot()
    db, service = make_service(tmp_path, client=client, bot=bot)
    record(service)
    q = FakeQ("menu")
    context = _ctx(db, service, client, bot)
    original = db.invalidate_conversation_views_for_message

    def fail(**kwargs):
        raise sqlite3.OperationalError("disk I/O error")

    db.invalidate_conversation_views_for_message = fail
    try:
        with pytest.raises(RefreshInvalidationError):
            asyncio.run(h.show_menu(_update(q), context))
        assert q.edits == []
        assert db.get_conversation_view(OWNER_ID, CID).active is True
    finally:
        db.invalidate_conversation_views_for_message = original

    asyncio.run(h.show_menu(_update(q), context))
    assert q.edits
    assert db.get_conversation_view(OWNER_ID, CID).superseded is True


def test_busy_invalidation_retries_then_succeeds(tmp_path, monkeypatch):
    client = FakeClient(exchange=("برومت", "رد"))
    bot = FakeBot()
    db, service = make_service(tmp_path, client=client, bot=bot)
    record(service)
    original = db.invalidate_conversation_views_for_message
    calls = 0

    def flaky(**kwargs):
        nonlocal calls
        calls += 1
        if calls <= 2:
            raise sqlite3.OperationalError("database is locked")
        return original(**kwargs)

    db.invalidate_conversation_views_for_message = flaky
    monkeypatch.setattr(refresh_module, "DEDUPE_RETRY_DELAYS", (0.0, 0.0, 0.0))
    changed = asyncio.run(
        service.supersede_message_with_retry(
            telegram_id=OWNER_ID, chat_id=OWNER_ID, message_id=100
        )
    )
    assert calls == 3
    assert changed == 1
    assert db.get_conversation_view(OWNER_ID, CID).superseded is True


def test_busy_invalidation_exhaustion_raises_and_keeps_target(tmp_path, monkeypatch):
    client = FakeClient(exchange=("برومت", "رد"))
    bot = FakeBot()
    db, service = make_service(tmp_path, client=client, bot=bot)
    record(service)
    calls = 0

    def busy(**kwargs):
        nonlocal calls
        calls += 1
        raise sqlite3.OperationalError("database is locked")

    db.invalidate_conversation_views_for_message = busy
    monkeypatch.setattr(refresh_module, "DEDUPE_RETRY_DELAYS", (0.0, 0.0, 0.0))
    with pytest.raises(RefreshInvalidationError):
        asyncio.run(
            service.supersede_message_with_retry(
                telegram_id=OWNER_ID, chat_id=OWNER_ID, message_id=100
            )
        )
    assert calls == 4
    row = db.get_conversation_view(OWNER_ID, CID)
    assert row.active is True and row.superseded is False


def test_unleased_refresh_cannot_overwrite_prompt_immediate(tmp_path):
    client = BlockingClient(exchange=("برومت", "رد جديد"))
    bot = FakeBot()
    clock = Clock()
    db = Database(str(tmp_path / "r03.sqlite3"))
    cache = {}
    service = ConversationRefreshService(
        client, db, bot, clock=clock, exchange_cache=cache
    )
    target = record(service)

    async def scenario():
        task = asyncio.create_task(service.refresh(target))
        await asyncio.wait_for(client.fetch_started.wait(), 1)
        service.request_immediate(CID, OWNER_ID)
        scheduled = db.get_conversation_view(OWNER_ID, CID).next_check_at
        client.release_fetch.set()
        await task
        after = db.get_conversation_view(OWNER_ID, CID)
        assert after.next_check_at == scheduled
        assert after.lease_token is None
        assert bot.edits == []
        assert cache == {}

    asyncio.run(scenario())


def test_unleased_refresh_cannot_overwrite_superseded_target(tmp_path):
    client = BlockingClient(exchange=("برومت", "رد جديد"))
    bot = FakeBot()
    db, service = make_service(tmp_path, client=client, bot=bot)
    target = record(service)

    async def scenario():
        task = asyncio.create_task(service.refresh(target))
        await asyncio.wait_for(client.fetch_started.wait(), 1)
        service.supersede_message(
            telegram_id=OWNER_ID, chat_id=OWNER_ID, message_id=100
        )
        client.release_fetch.set()
        await task
        assert bot.edits == []
        row = db.get_conversation_view(OWNER_ID, CID)
        assert row.active is False and row.superseded is True

    asyncio.run(scenario())


def test_unleased_refresh_cannot_edit_deleted_target(tmp_path):
    client = BlockingClient(exchange=("برومت", "رد جديد"))
    bot = FakeBot()
    db, service = make_service(tmp_path, client=client, bot=bot)
    target = record(service)

    async def scenario():
        task = asyncio.create_task(service.refresh(target))
        await asyncio.wait_for(client.fetch_started.wait(), 1)
        db.delete_conversation(CID, service.now_iso())
        client.release_fetch.set()
        await task
        assert bot.edits == []
        assert db.list_conversation_views() == []

    asyncio.run(scenario())


def test_two_unleased_refreshes_cannot_overlap(tmp_path):
    client = BlockingClient(exchange=("برومت", "رد جديد"))
    bot = FakeBot()
    db, service = make_service(tmp_path, client=client, bot=bot)
    target = record(service)

    async def scenario():
        first = asyncio.create_task(service.refresh(target))
        await asyncio.wait_for(client.fetch_started.wait(), 1)
        await service.refresh(db.get_conversation_view(OWNER_ID, CID))
        assert bot.edits == []
        client.release_fetch.set()
        await first
        assert len(bot.edits) == 1

    asyncio.run(scenario())


def test_unleased_refresh_normal_caller_still_works(tmp_path):
    client = FakeClient(exchange=("برومت", "رد جديد"))
    bot = FakeBot()
    db, service = make_service(tmp_path, client=client, bot=bot)
    target = record(service)
    asyncio.run(service.refresh(target))
    assert len(bot.edits) == 1
    assert db.get_conversation_view(OWNER_ID, CID).active is True


def test_long_registration_has_no_refresh_target(tmp_path):
    client = FakeClient(exchange=("برومت", "رد"))
    bot = FakeBot()
    db, service = make_service(tmp_path, client=client, bot=bot)
    message = SimpleNamespace(chat_id=OWNER_ID, message_id=777)
    context = SimpleNamespace(bot_data={"refresh_service": service})
    h._register_conversation_view(
        context,
        telegram_id=OWNER_ID,
        conversation_id=CID,
        message=message,
        text="x" * 5000,
        markup=None,
        conv={"execution_status": "running"},
    )
    assert db.list_conversation_views() == []


def test_long_registration_then_shrink_creates_only_new_target(tmp_path):
    client = FakeClient(exchange=("برومت", "رد"))
    bot = FakeBot()
    db, service = make_service(tmp_path, client=client, bot=bot)
    assert service.record_view(
        telegram_id=OWNER_ID, conversation_id=CID, chat_id=OWNER_ID,
        message_id=100, text="x" * 5000, markup=None, terminal=False,
    ) is None
    assert db.list_conversation_views() == []
    assert service.record_view(
        telegram_id=OWNER_ID, conversation_id=CID, chat_id=OWNER_ID,
        message_id=100, text="short", markup=None, terminal=False,
    ) is not None
    assert len(db.list_conversation_views()) == 1
    asyncio.run(service.refresh(db.get_conversation_view(OWNER_ID, CID)))
    assert len(bot.edits) == 1


def test_oversized_refresh_deactivates_and_does_not_retry(tmp_path):
    client = FakeClient(exchange=("برومت", "رد"))
    bot = FakeBot()
    bot.edit_error = BadRequest("Message is too long")
    db, service = make_service(tmp_path, client=client, bot=bot)
    target = record(service)
    asyncio.run(service.refresh(target))
    row = db.get_conversation_view_by_id(target.view_id)
    assert row.active is False
    assert row.superseded is True
    assert row.next_check_at is None
    assert _claim(service) is None


def test_file_long_fallback_returns_none(tmp_path):
    bot = FileBot()
    result = asyncio.run(send_long(OWNER_ID, "x" * 20000, bot))
    assert result is None
    assert bot.sent == ["file"]


def test_migration_keeps_newest_updated_at_not_insertion_order(tmp_path):
    import sqlite3

    path = tmp_path / "legacy_order.sqlite3"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE conversation_views (
            telegram_id INTEGER NOT NULL,
            conversation_id TEXT NOT NULL,
            chat_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            last_fingerprint TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            failures INTEGER NOT NULL DEFAULT 0,
            next_check_at TEXT,
            lease_until TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (telegram_id, conversation_id)
        );
        """
    )
    conn.executemany(
        "INSERT INTO conversation_views VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        [
            (OWNER_ID, CID, OWNER_ID, 100, "new", 1, 0, None, None,
             "2026-01-01T00:00:00+00:00", "2026-01-02T00:00:00+00:00"),
            (OWNER_ID, CID2, OWNER_ID, 100, "old", 1, 0, None, None,
             "2026-01-02T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
        ],
    )
    conn.commit()
    conn.close()

    db = Database(str(path))
    newest = db.get_conversation_view(OWNER_ID, CID)
    older = db.get_conversation_view(OWNER_ID, CID2)
    assert newest.active is True and newest.superseded is False
    assert older.active is False and older.superseded is True


def test_cache_is_not_written_after_post_finish_immediate_request(tmp_path):
    client = FakeClient(exchange=("برومت", "رد جديد"))
    bot = FakeBot()
    clock = Clock()
    db = Database(str(tmp_path / "r03_cache_race.sqlite3"))
    cache = {}
    service = ConversationRefreshService(client, db, bot, clock=clock, exchange_cache=cache)
    target = record(service)
    original = db.finish_conversation_view_refresh_owned

    def finish_then_prompt(**kwargs):
        result = original(**kwargs)
        service.request_immediate(CID, OWNER_ID)
        return result

    db.finish_conversation_view_refresh_owned = finish_then_prompt
    asyncio.run(service.refresh(target))
    assert cache == {}
    assert db.get_conversation_view(OWNER_ID, CID).next_check_at == clock.now_iso()


def test_long_replacement_retires_previous_target(tmp_path):
    client = FakeClient(exchange=("برومت", "رد"))
    bot = FakeBot()
    db, service = make_service(tmp_path, client=client, bot=bot)
    target = record(service)
    message = SimpleNamespace(chat_id=OWNER_ID, message_id=100)
    context = SimpleNamespace(bot_data={"refresh_service": service})
    h._register_conversation_view(
        context,
        telegram_id=OWNER_ID,
        conversation_id=CID,
        message=message,
        text="x" * 5000,
        markup=None,
        conv={"execution_status": "running"},
    )
    row = db.get_conversation_view_by_id(target.view_id)
    assert row.active is False
    assert row.superseded is True
    assert db.count_active_conversation_views() == 0
