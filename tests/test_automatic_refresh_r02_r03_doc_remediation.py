"""Regression tests for OHB2-AUTOMATIC-REFRESH-R02-R03-DOC-REMEDIATION."""
import asyncio
import logging
import sqlite3

import pytest

import bot.db as db_module
import bot.handlers as h
import bot.refresh as refresh_module
from bot import update_outcomes
from bot.refresh import RefreshInvalidationError
from tests.test_automatic_conversation_refresh import (
    CID,
    OWNER_ID,
    Clock,
    FakeBot,
    FakeClient,
    make_service,
    record,
)
from tests.test_automatic_conversation_refresh_remediation import (
    BlockingClient,
    FakeQ,
    _claim,
    _ctx,
    _update,
)


def _target_for_refresh(tmp_path, *, client=None, bot=None):
    db, service = make_service(
        tmp_path,
        client=client or FakeClient(exchange=("برومت", "رد جديد")),
        bot=bot or FakeBot(),
        clock=Clock(),
    )
    target = record(service)
    service.request_immediate(CID, OWNER_ID)
    return db, service, target


def _row_has_clean_lease(row) -> bool:
    return row is not None and row.lease_token is None and row.lease_until is None


def _write_legacy_conversation_view(path):
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
    conn.execute(
        "INSERT INTO conversation_views VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (
            OWNER_ID, CID, OWNER_ID, 100, "fp", 1, 0, None, None,
            "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00",
        ),
    )
    conn.commit()
    conn.close()


def test_cancellation_immediately_after_claim_releases_lease(tmp_path, monkeypatch):
    db, service, target = _target_for_refresh(tmp_path)

    def cancel_after_claim(_target):
        raise asyncio.CancelledError

    monkeypatch.setattr(service, "_current_target", cancel_after_claim)

    async def scenario():
        with pytest.raises(asyncio.CancelledError):
            await service.refresh(target)

    asyncio.run(scenario())
    row = db.get_conversation_view_by_id(target.view_id)
    assert _row_has_clean_lease(row)
    assert row.active is True and row.superseded is False
    assert _claim(service) is not None


def test_cancellation_during_metadata_releases_lease_and_allows_next_claim(tmp_path):
    client = BlockingClient(exchange=("برومت", "رد جديد"))
    db, service, target = _target_for_refresh(tmp_path, client=client)

    async def scenario():
        task = asyncio.create_task(service.refresh(target))
        await asyncio.wait_for(client.fetch_started.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    row = db.get_conversation_view_by_id(target.view_id)
    assert _row_has_clean_lease(row)
    assert _claim(service) is not None


def test_db_error_immediately_after_claim_releases_lease(tmp_path, monkeypatch):
    db, service, target = _target_for_refresh(tmp_path)
    original_get = db.get_conversation_view_by_id

    def fail_read(_view_id):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(db, "get_conversation_view_by_id", fail_read)

    with pytest.raises(sqlite3.OperationalError):
        asyncio.run(service.refresh(target))

    row = original_get(target.view_id)
    assert _row_has_clean_lease(row)
    assert row.active is True and row.superseded is False
    assert _claim(service) is not None


def test_db_error_during_early_validation_releases_lease(tmp_path, monkeypatch):
    db, service, target = _target_for_refresh(tmp_path)
    original_get = db.get_conversation_view_by_id

    def fail_read(_view_id):
        raise sqlite3.OperationalError("unable to open database file")

    # _current_target is the first post-claim validation read.
    monkeypatch.setattr(db, "get_conversation_view_by_id", fail_read)

    with pytest.raises(sqlite3.OperationalError):
        asyncio.run(service.refresh(target))

    row = original_get(target.view_id)
    assert _row_has_clean_lease(row)
    assert _claim(service) is not None


def test_db_error_during_post_fetch_validation_cleans_lease(tmp_path, monkeypatch):
    db, service, target = _target_for_refresh(tmp_path)

    def fail_is_watched(_conversation_id):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(db, "is_watched", fail_is_watched)
    asyncio.run(service.refresh(target))

    row = db.get_conversation_view_by_id(target.view_id)
    assert _row_has_clean_lease(row)
    assert row.active is True and row.superseded is False
    assert row.failures == 1


def test_normal_unexpected_exception_cleans_lease_after_defer(tmp_path):
    client = FakeClient(exchange=("برومت", "رد"), exchange_error=RuntimeError("boom"))
    db, service, target = _target_for_refresh(tmp_path, client=client)

    asyncio.run(service.refresh(target))

    row = db.get_conversation_view_by_id(target.view_id)
    assert _row_has_clean_lease(row)
    assert row.active is True and row.superseded is False
    assert row.failures == 1
    assert row.next_check_at is not None


def test_cleanup_does_not_release_a_newer_lease(tmp_path):
    db, service, target = _target_for_refresh(tmp_path)
    old = service._ensure_lease(target)
    assert old is not None
    assert db.release_conversation_view_lease(
        view_id=old.view_id, lease_token=old.lease_token, now=service.now_iso()
    ) is True
    newer = db.claim_conversation_view(
        view_id=old.view_id,
        now=service.now_iso(),
        lease_until=service.deadline(120),
    )
    assert newer is not None

    asyncio.run(service.refresh(old))

    row = db.get_conversation_view_by_id(old.view_id)
    assert row.lease_token == newer.lease_token
    assert row.generation == newer.generation
    assert row.active is True and row.superseded is False


def test_cleanup_after_supersede_preserves_superseded_state(tmp_path):
    db, service, target = _target_for_refresh(tmp_path)
    claimed = service._ensure_lease(target)
    assert claimed is not None
    db.invalidate_conversation_views_for_message(
        telegram_id=OWNER_ID,
        chat_id=OWNER_ID,
        message_id=100,
        now=service.now_iso(),
    )

    asyncio.run(service.refresh(claimed))

    row = db.get_conversation_view_by_id(target.view_id)
    assert row is not None
    assert row.active is False and row.superseded is True
    assert _row_has_clean_lease(row)
    assert _claim(service) is None


def test_cleanup_after_delete_does_not_recreate_target(tmp_path):
    db, service, target = _target_for_refresh(tmp_path)
    claimed = service._ensure_lease(target)
    assert claimed is not None
    db.delete_conversation(CID, service.now_iso())

    asyncio.run(service.refresh(claimed))

    assert db.get_conversation_view_by_id(target.view_id) is None
    assert db.list_conversation_views() == []


def test_cleanup_failure_is_observable_and_does_not_corrupt_newer_lease(tmp_path, monkeypatch, caplog):
    db, service, target = _target_for_refresh(tmp_path)
    old = service._ensure_lease(target)
    assert old is not None
    assert db.release_conversation_view_lease(
        view_id=old.view_id, lease_token=old.lease_token, now=service.now_iso()
    ) is True
    newer = db.claim_conversation_view(
        view_id=old.view_id,
        now=service.now_iso(),
        lease_until=service.deadline(120),
    )
    assert newer is not None

    def fail_release(**_kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(db, "release_conversation_view_lease", fail_release)
    with caplog.at_level(logging.WARNING, logger="bot.refresh"):
        asyncio.run(service.refresh(old))

    row = db.get_conversation_view_by_id(old.view_id)
    assert row.lease_token == newer.lease_token
    assert row.generation == newer.generation
    assert any(
        record.name == "bot.refresh" and record.levelno >= logging.WARNING
        for record in caplog.records
    )


@pytest.mark.parametrize("error_text", ["database is locked", "database table is locked"])
def test_transient_invalidation_succeeds_within_budget(tmp_path, monkeypatch, error_text):
    db, service = make_service(
        tmp_path, client=FakeClient(exchange=("برومت", "رد")), bot=FakeBot(), clock=Clock()
    )
    record(service)
    original = db.invalidate_conversation_views_for_message
    calls = 0

    def flaky(**kwargs):
        nonlocal calls
        calls += 1
        if calls <= 2:
            raise sqlite3.OperationalError(error_text)
        return original(**kwargs)

    monkeypatch.setattr(db, "invalidate_conversation_views_for_message", flaky)
    monkeypatch.setattr(refresh_module, "DEDUPE_RETRY_DELAYS", (0.0, 0.0, 0.0))

    changed = asyncio.run(
        service.supersede_message_with_retry(
            telegram_id=OWNER_ID, chat_id=OWNER_ID, message_id=100
        )
    )
    assert calls == 3
    assert changed == 1
    assert db.get_conversation_view(OWNER_ID, CID).superseded is True


@pytest.mark.parametrize("error_text", ["database is locked", "database table is locked"])
def test_transient_invalidation_exhaustion_is_transient_and_blocks_screen(
    tmp_path, monkeypatch, error_text
):
    db, service = make_service(
        tmp_path, client=FakeClient(exchange=("برومت", "رد")), bot=FakeBot(), clock=Clock()
    )
    record(service)
    calls = 0

    def busy(**_kwargs):
        nonlocal calls
        calls += 1
        raise sqlite3.OperationalError(error_text)

    monkeypatch.setattr(db, "invalidate_conversation_views_for_message", busy)
    monkeypatch.setattr(refresh_module, "DEDUPE_RETRY_DELAYS", (0.0, 0.0, 0.0))
    q = FakeQ("menu")

    with pytest.raises(RefreshInvalidationError) as info:
        asyncio.run(h.show_menu(_update(q), _ctx(db, service, service.client, service.bot)))

    assert calls == 4
    assert info.value.transient is True
    assert h._classify_failure(info.value) == update_outcomes.FAILED_TRANSIENT
    assert q.edits == []
    row = db.get_conversation_view(OWNER_ID, CID)
    assert row.active is True and row.superseded is False


def test_permanent_invalidation_failure_is_not_transient(tmp_path, monkeypatch):
    db, service = make_service(
        tmp_path, client=FakeClient(exchange=("برومت", "رد")), bot=FakeBot(), clock=Clock()
    )
    record(service)
    calls = 0

    def permanent(**_kwargs):
        nonlocal calls
        calls += 1
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(db, "invalidate_conversation_views_for_message", permanent)
    q = FakeQ("menu")

    with pytest.raises(RefreshInvalidationError) as info:
        asyncio.run(h.show_menu(_update(q), _ctx(db, service, service.client, service.bot)))

    assert calls == 1
    assert info.value.transient is False
    assert h._classify_failure(info.value) == update_outcomes.FAILED_PERMANENT
    assert q.edits == []
    row = db.get_conversation_view(OWNER_ID, CID)
    assert row.active is True and row.superseded is False


def test_unexpected_database_error_is_not_silently_successful(tmp_path, monkeypatch):
    db, service = make_service(
        tmp_path, client=FakeClient(exchange=("برومت", "رد")), bot=FakeBot(), clock=Clock()
    )
    record(service)

    def broken(**_kwargs):
        raise sqlite3.DatabaseError("database disk image is malformed")

    monkeypatch.setattr(db, "invalidate_conversation_views_for_message", broken)
    q = FakeQ("menu")

    with pytest.raises(RefreshInvalidationError) as info:
        asyncio.run(h.show_menu(_update(q), _ctx(db, service, service.client, service.bot)))

    assert info.value.transient is False
    assert h._classify_failure(info.value) == update_outcomes.FAILED_PERMANENT
    assert q.edits == []


def test_legacy_conversation_view_migration_rolls_back_on_failure(tmp_path, monkeypatch):
    path = tmp_path / "legacy.sqlite3"
    _write_legacy_conversation_view(path)
    monkeypatch.setattr(db_module, "CONVERSATION_VIEWS_TABLE_SQL", "CREATE TABLE broken (")

    with pytest.raises(sqlite3.OperationalError):
        db_module.Database(str(path))

    conn = sqlite3.connect(path)
    try:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(conversation_views)")]
        count = conn.execute("SELECT COUNT(*) FROM conversation_views").fetchone()[0]
        legacy_tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='conversation_views_legacy'"
            )
        }
    finally:
        conn.close()
    assert "view_id" not in columns
    assert count == 1
    assert legacy_tables == set()
