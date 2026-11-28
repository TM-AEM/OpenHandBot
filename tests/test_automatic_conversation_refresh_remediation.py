"""Regression tests for the automatic conversation refresh remediation."""
import asyncio
import sqlite3
from types import SimpleNamespace

import pytest
from telegram.error import BadRequest

import bot.handlers as h
from bot import outbox
from bot.db import Database
from bot.errors import ApiError
from bot.files import FileStatus, IdentityCache, authorize_conversation_detailed
from bot.messages import is_terminal
from bot.refresh import (
    ConversationRefreshService,
    ConversationRefreshWorker,
    REFRESH_MAX_CONCURRENT,
)
from tests.test_automatic_conversation_refresh import (
    CID,
    OWNER_ID,
    Clock,
    FakeBot,
    FakeClient,
    FakeConfig,
    make_service,
    parse,
    record,
)

CID2 = "b" * 32


class ListClient(FakeClient):
    async def search_conversations(self, limit=100, page_id=None):
        return {"items": [self.conv], "next_page_id": None}

    async def list_files(self, conversation_id):
        return []


class FakeQ:
    def __init__(self, data, message_id=100):
        self.data = data
        self.message = SimpleNamespace(chat_id=OWNER_ID, message_id=message_id)
        self.edits = []

    async def answer(self, *args, **kwargs):
        return None

    async def edit_message_text(self, text, **kwargs):
        self.edits.append((text, kwargs))


def _update(q, update_id=1):
    return SimpleNamespace(
        update_id=update_id,
        effective_user=SimpleNamespace(id=OWNER_ID),
        effective_chat=SimpleNamespace(id=OWNER_ID, type="private"),
        message=SimpleNamespace(reply_text=None),
        callback_query=q,
    )


def _ctx(db, service, client, bot):
    return SimpleNamespace(
        bot=bot,
        bot_data={
            "config": FakeConfig(),
            "db": db,
            "client": client,
            "refresh_service": service,
            "identity_cache": (client, IdentityCache(client)),
        },
    )


def _claim(service):
    return service.db.claim_due_conversation_view(
        service.now_iso(), service.deadline(120)
    )


def _due_target(service):
    record(service)
    service.request_immediate(CID, OWNER_ID)
    target = _claim(service)
    assert target is not None
    return target


def _record_on(service, conversation_id=CID, message_id=100, text="قديم"):
    service.record_view(
        telegram_id=OWNER_ID,
        conversation_id=conversation_id,
        chat_id=OWNER_ID,
        message_id=message_id,
        text=text,
        markup=None,
        terminal=False,
    )
    return next(
        view
        for view in service.db.list_conversation_views()
        if view.conversation_id == conversation_id and view.message_id == message_id
    )


def test_navigation_supersedes_claimed_target_delete_and_menu(tmp_path):
    for handler, data in (
        (h.delete_conversation_prompt, f"delete:{CID}"),
        (h.show_menu, "menu"),
        (h.show_status, f"status:{CID}"),
        (h.show_cost, f"cost:{CID}"),
        (h.list_files, f"files:{CID}:0"),
        (h.reply_prompt, f"reply:{CID}"),
        (h.list_conversations, "list:0"),
    ):
        client = ListClient(exchange=("برومت", "رد"))
        bot = FakeBot()
        clock = Clock()
        case_dir = tmp_path / handler.__name__
        case_dir.mkdir()
        db, service = make_service(case_dir, client=client, bot=bot, clock=clock)
        target = _due_target(service)
        q = FakeQ(data)
        update = _update(q)
        ctx = _ctx(db, service, client, bot)

        asyncio.run(handler(update, ctx))

        after = db.get_conversation_view(OWNER_ID, CID)
        assert after is not None
        assert after.active is False
        assert after.superseded is True
        assert bot.edits == []
        assert q.edits
        asyncio.run(service.refresh(target))
        assert bot.edits == []


def test_same_message_has_only_one_active_target(tmp_path):
    client = FakeClient(exchange=("برومت", "رد"))
    bot = FakeBot()
    db, service = make_service(tmp_path, client=client, bot=bot, clock=Clock())

    _record_on(service, CID, 100)
    _record_on(service, CID2, 100)
    service.request_immediate(CID2, OWNER_ID)

    assert db.count_active_conversation_views() == 1
    old = db.get_conversation_view(OWNER_ID, CID)
    new = db.get_conversation_view(OWNER_ID, CID2)
    assert old is not None and old.active is False and old.superseded is True
    assert new is not None and new.active is True
    target = _claim(service)
    assert target is not None and target.conversation_id == CID2
    asyncio.run(service.refresh(target))
    assert len(bot.edits) == 1
    assert bot.edits[0]["message_id"] == 100


def test_same_conversation_on_two_messages_has_two_independent_targets(tmp_path):
    client = FakeClient(exchange=("برومت", "رد"))
    bot = FakeBot()
    db, service = make_service(tmp_path, client=client, bot=bot, clock=Clock())
    _record_on(service, CID, 100)
    _record_on(service, CID, 200)
    assert db.count_active_conversation_views() == 2
    service.request_immediate(CID, OWNER_ID)

    first = _claim(service)
    assert first is not None
    asyncio.run(service.refresh(first))
    second = _claim(service)
    assert second is not None
    asyncio.run(service.refresh(second))

    assert len(bot.edits) == 2
    assert {edit["message_id"] for edit in bot.edits} == {100, 200}


def test_immediate_refresh_survives_older_worker_finish(tmp_path):
    clock = Clock()
    db, service = make_service(tmp_path, clock=clock)
    target = _due_target(service)
    service.request_immediate(CID, OWNER_ID)
    now = clock.now_iso()

    assert db.finish_conversation_view_refresh_owned(
        view_id=target.view_id,
        target_token=target.target_token,
        generation=target.generation,
        lease_token=target.lease_token,
        last_fingerprint="stale",
        active=True,
        next_check_at=service.deadline(35),
        now=now,
    ) is False
    row = db.get_conversation_view_by_id(target.view_id)
    assert row is not None and row.active is True
    assert row.next_check_at == now
    assert _claim(service) is not None


def test_superseded_target_rejects_stale_finish_defer_and_edit(tmp_path):
    client = FakeClient(exchange=("برومت", "رد"))
    bot = FakeBot()
    clock = Clock()
    db, service = make_service(tmp_path, client=client, bot=bot, clock=clock)
    target = _due_target(service)
    service.supersede_message(telegram_id=OWNER_ID, chat_id=OWNER_ID, message_id=100)

    assert db.finish_conversation_view_refresh_owned(
        view_id=target.view_id,
        target_token=target.target_token,
        generation=target.generation,
        lease_token=target.lease_token,
        last_fingerprint="stale",
        active=True,
        next_check_at=service.deadline(35),
        now=clock.now_iso(),
    ) is False
    assert db.defer_conversation_view_refresh_owned(
        view_id=target.view_id,
        target_token=target.target_token,
        generation=target.generation,
        lease_token=target.lease_token,
        next_check_at=service.deadline(35),
        now=clock.now_iso(),
    ) is False
    asyncio.run(service.refresh(target))
    row = db.get_conversation_view_by_id(target.view_id)
    assert row is not None and row.active is False and row.superseded is True
    assert bot.edits == []


def test_expired_lease_can_be_replaced_and_old_owner_rejected(tmp_path):
    clock = Clock()
    db, service = make_service(tmp_path, clock=clock)
    target_a = _due_target(service)
    db._conn.execute(
        "UPDATE conversation_views SET lease_until=? WHERE view_id=?",
        (clock.now_iso(), target_a.view_id),
    )
    db._conn.commit()
    target_b = _claim(service)
    assert target_b is not None
    assert target_b.lease_token != target_a.lease_token

    assert db.finish_conversation_view_refresh_owned(
        view_id=target_a.view_id,
        target_token=target_a.target_token,
        generation=target_a.generation,
        lease_token=target_a.lease_token,
        last_fingerprint="stale",
        active=True,
        next_check_at=service.deadline(35),
        now=clock.now_iso(),
    ) is False
    assert db.is_conversation_view_current(
        view_id=target_b.view_id,
        target_token=target_b.target_token,
        generation=target_b.generation,
        lease_token=target_b.lease_token,
    )


def test_terminal_completion_cannot_reactivate_after_prompt_immediate(tmp_path):
    clock = Clock()
    db, service = make_service(tmp_path, clock=clock)
    target = _due_target(service)
    service.request_immediate(CID, OWNER_ID)
    assert db.deactivate_conversation_view_owned(
        view_id=target.view_id,
        target_token=target.target_token,
        generation=target.generation,
        lease_token=target.lease_token,
        now=clock.now_iso(),
        superseded=False,
    ) is False
    row = db.get_conversation_view_by_id(target.view_id)
    assert row is not None and row.active is True
    assert row.next_check_at == clock.now_iso()


def test_empty_metadata_is_ambiguous_and_retried(tmp_path):
    client = FakeClient(exchange=("برومت", "رد"))
    client.conv = []
    bot = FakeBot()
    clock = Clock()
    db, service = make_service(tmp_path, client=client, bot=bot, clock=clock)
    target = record(service)

    asyncio.run(service.refresh(target))

    after = db.get_conversation_view(OWNER_ID, CID)
    assert after.active is True
    assert after.failures == 1
    assert parse(after.next_check_at) > clock.value
    assert bot.edits == []
    status = asyncio.run(
        authorize_conversation_detailed(
            client, IdentityCache(client), CID, db, empty_is_ambiguous=True
        )
    )[1]
    assert status is FileStatus.AMBIGUOUS


@pytest.mark.parametrize(
    "mutate, expected_active",
    [
        (lambda c: c.conv.update(created_by_user_id="other-owner"), False),
        (lambda c: setattr(c, "conv_error", ApiError("gone", 404)), False),
        (lambda c: setattr(c, "conv_error", ApiError("busy", 503)), True),
        (lambda c: setattr(c, "conv_error", ApiError("rate", 429)), True),
    ],
)
def test_metadata_classification_and_schedule_outcome(tmp_path, mutate, expected_active):
    client = FakeClient(exchange=("برومت", "رد"))
    mutate(client)
    bot = FakeBot()
    clock = Clock()
    db, service = make_service(tmp_path, client=client, bot=bot, clock=clock)
    target = record(service)

    asyncio.run(service.refresh(target))

    after = db.get_conversation_view(OWNER_ID, CID)
    assert after.active is expected_active
    assert bot.edits == []


def test_invalid_identifier_and_tombstone_stop_safely(tmp_path):
    client = FakeClient(exchange=("برومت", "رد"))
    bot = FakeBot()
    db, service = make_service(tmp_path, client=client, bot=bot, clock=Clock())
    service.record_view(
        telegram_id=OWNER_ID,
        conversation_id="bad/id",
        chat_id=OWNER_ID,
        message_id=101,
        text="x",
        markup=None,
        terminal=False,
    )
    target = db.get_conversation_view(OWNER_ID, "bad/id")
    asyncio.run(service.refresh(target))
    after = db.get_conversation_view(OWNER_ID, "bad/id")
    assert after.active is False and after.superseded is True

    record(service)
    db._conn.execute(
        "INSERT OR IGNORE INTO deleted_conversations(conversation_id, deleted_at) VALUES(?, ?)",
        (CID, outbox.now_iso()),
    )
    db._conn.commit()
    asyncio.run(service.refresh(record(service)))
    after = db.get_conversation_view(OWNER_ID, CID)
    assert after.active is False and after.superseded is True


def test_successful_refresh_updates_exchange_cache_and_copy_reads_it(tmp_path):
    client = FakeClient(exchange=("برومت", "رد جديد"))
    bot = FakeBot()
    clock = Clock()
    cache = {}
    db = Database(str(tmp_path / "cache.sqlite3"))
    service = ConversationRefreshService(
        client, db, bot, clock=clock, exchange_cache=cache
    )
    target = record(service)
    cache[CID] = (0.0, "برومت قديم", "رد قديم")

    asyncio.run(service.refresh(target))

    assert cache[CID][1:] == ("برومت", "رد جديد")
    ctx = SimpleNamespace(bot_data={"client": client, "exchange_cache": cache})
    assert asyncio.run(h._get_exchange(ctx, CID)) == ("برومت", "رد جديد")


def test_failed_or_superseded_refresh_does_not_poison_exchange_cache(tmp_path):
    client = FakeClient(exchange=("برومت", "رد جديد"))
    bot = FakeBot()
    bot.edit_error = BadRequest("message to edit not found")
    cache = {}
    db = Database(str(tmp_path / "cache_fail.sqlite3"))
    service = ConversationRefreshService(
        client, db, bot, clock=Clock(), exchange_cache=cache
    )
    asyncio.run(service.refresh(record(service)))
    assert CID not in cache

    bot.edit_error = None
    target = _due_target(service)
    service.supersede_message(telegram_id=OWNER_ID, chat_id=OWNER_ID, message_id=100)
    asyncio.run(service.refresh(target))
    assert CID not in cache


def test_two_conversations_have_independent_cache_entries(tmp_path):
    client = FakeClient(exchange=("برومت", "رد"))
    bot = FakeBot()
    cache = {}
    db = Database(str(tmp_path / "cache_two.sqlite3"))
    service = ConversationRefreshService(
        client, db, bot, clock=Clock(), exchange_cache=cache
    )
    _record_on(service, CID, 100)
    _record_on(service, CID2, 200)
    service.request_immediate(CID, OWNER_ID)
    service.request_immediate(CID2, OWNER_ID)
    target_a = _claim(service)
    asyncio.run(service.refresh(target_a))
    target_b = _claim(service)
    asyncio.run(service.refresh(target_b))
    assert CID in cache and CID2 in cache


def test_deletion_removes_view_rows_and_retention_prunes_only_inactive(tmp_path):
    db, service = make_service(tmp_path, clock=Clock())
    record(service)
    summary = db.delete_conversation(CID, service.now_iso())
    assert summary["views_deleted"] == 1
    assert db.list_conversation_views() == []

    _record_on(service, CID, 100)
    _record_on(service, CID2, 200)
    db._conn.execute(
        "UPDATE conversation_views SET active=0, superseded=1, updated_at=? "
        "WHERE conversation_id=?",
        ("2000-01-01T00:00:00+00:00", CID2),
    )
    db._conn.commit()
    removed = db.prune_inactive_conversation_views("2020-01-01T00:00:00+00:00")
    assert removed == 1
    assert db.get_conversation_view(OWNER_ID, CID).active is True


def test_long_message_fallback_records_actual_replacement_message(tmp_path):
    bot = FakeBot()
    new_message = SimpleNamespace(chat_id=OWNER_ID, message_id=777)

    async def send_message(chat_id=None, text=None, **kwargs):
        return new_message

    bot.send_message = send_message
    q = FakeQ(f"open:{CID}")

    async def too_long(text, **kwargs):
        raise BadRequest("Message is too long")

    q.edit_message_text = too_long
    update = _update(q)
    ctx = SimpleNamespace(bot=bot, bot_data={})

    displayed, message = asyncio.run(
        h._display_conversation_view(update, ctx, "x", q=q, return_message=True)
    )
    assert displayed is True
    assert message is new_message


def test_worker_claims_one_due_view_at_a_time_and_uses_fair_order(tmp_path):
    client = FakeClient(exchange=("برومت", "رد"))
    bot = FakeBot()
    db, service = make_service(tmp_path, client=client, bot=bot, clock=Clock())
    _record_on(service, CID, 100)
    _record_on(service, CID2, 200)
    service.request_immediate(CID, OWNER_ID)
    service.request_immediate(CID2, OWNER_ID)
    worker = ConversationRefreshWorker(service, poll_interval=0.01)
    assert worker.max_concurrent == REFRESH_MAX_CONCURRENT == 1

    first = worker._claim()
    assert first is not None
    # The worker may lease the next different row, but the first row stays leased:
    # it cannot be claimed again until its own finish/defer/release.
    second = worker._claim()
    assert second is not None and second.view_id != first.view_id
    assert db.is_conversation_view_current(
        view_id=first.view_id,
        target_token=first.target_token,
        generation=first.generation,
        lease_token=first.lease_token,
    )
    asyncio.run(worker._process(first))


def test_idle_and_paused_remain_non_terminal_under_existing_policy():
    # Provider semantics are not redefined here; the owner decision is documented.
    assert is_terminal("idle") is False
    assert is_terminal("paused") is False


def test_old_conversation_view_schema_is_migrated(tmp_path):
    path = tmp_path / "old.sqlite3"
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
        CREATE INDEX idx_conversation_views_due
            ON conversation_views(active, next_check_at, lease_until);
        """
    )
    conn.executemany(
        "INSERT INTO conversation_views VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        [
            (OWNER_ID, CID, OWNER_ID, 100, "fp", 1, 0, None, None,
             "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
            (OWNER_ID, CID2, OWNER_ID, 100, "fp2", 1, 0, None, None,
             "2026-01-02T00:00:00+00:00", "2026-01-02T00:00:00+00:00"),
        ],
    )
    conn.commit()
    conn.close()

    db = Database(str(path))
    views = db.list_conversation_views()
    assert len(views) == 2
    assert all(view.view_id is not None and view.target_token for view in views)
    assert db.count_active_conversation_views() == 1
    assert sum(view.superseded for view in views) == 1
    assert db.get_conversation_view(OWNER_ID, CID2).active is True


class BlockingClient(FakeClient):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fetch_started = asyncio.Event()
        self.release_fetch = asyncio.Event()

    async def get_last_exchange(self, conversation_id):
        self.fetch_started.set()
        await self.release_fetch.wait()
        return self.exchange


def test_invalidation_while_refresh_is_fetching_prevents_edit(tmp_path):
    client = BlockingClient(exchange=("برومت", "رد جديد"))
    bot = FakeBot()
    clock = Clock()
    db, service = make_service(tmp_path, client=client, bot=bot, clock=clock)
    target = _due_target(service)

    async def scenario():
        task = asyncio.create_task(service.refresh(target))
        await asyncio.wait_for(client.fetch_started.wait(), timeout=1)
        service.supersede_message(
            telegram_id=OWNER_ID, chat_id=OWNER_ID, message_id=100
        )
        client.release_fetch.set()
        await task

    asyncio.run(scenario())

    row = db.get_conversation_view_by_id(target.view_id)
    assert row is not None and row.active is False and row.superseded is True
    assert bot.edits == []


def test_new_target_on_same_message_rejects_old_owner_finish_and_edit(tmp_path):
    client = FakeClient(exchange=("برومت", "رد"))
    bot = FakeBot()
    clock = Clock()
    db, service = make_service(tmp_path, client=client, bot=bot, clock=clock)
    old = _due_target(service)
    _record_on(service, CID2, 100)

    assert db.finish_conversation_view_refresh_owned(
        view_id=old.view_id,
        target_token=old.target_token,
        generation=old.generation,
        lease_token=old.lease_token,
        last_fingerprint="stale",
        active=True,
        next_check_at=service.deadline(35),
        now=clock.now_iso(),
    ) is False
    asyncio.run(service.refresh(old))
    assert bot.edits == []
    assert db.count_active_conversation_views() == 1
    assert db.get_conversation_view(OWNER_ID, CID2).active is True


def test_superseded_target_is_not_reactivated_by_prompt_success(tmp_path):
    db, service = make_service(tmp_path, clock=Clock())
    record(service)
    service.supersede_message(telegram_id=OWNER_ID, chat_id=OWNER_ID, message_id=100)
    assert service.request_immediate(CID, OWNER_ID) is None
    row = db.get_conversation_view(OWNER_ID, CID)
    assert row.active is False and row.superseded is True
    assert _claim(service) is None
