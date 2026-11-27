"""OHB2-WP01 Stage 1 N1/N2 remediation and T1-T7 regression tests.

Isolated temporary databases and staging roots only. No Telegram/OpenHands
network calls, no production credentials, and no real attachment data.
"""
from __future__ import annotations

import asyncio
import sqlite3
import threading
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import bot.handlers as h
from bot.attachments import (
    AcceptOutcome,
    AcceptResult,
    AttachmentReaper,
    AttachmentService,
    StageStatus,
    StagingStore,
    staging_root_for,
)
from bot.db import (
    ATTACHMENT_BATCH_CANCELLED,
    ATTACHMENT_BATCH_DELIVERED,
    ATTACHMENT_BATCH_DISPATCHING,
    ATTACHMENT_BATCH_EXPIRED,
    ATTACHMENT_BATCH_FAILED,
    ATTACHMENT_BATCH_INTENT_RECORDED,
    ATTACHMENT_BATCH_PENDING,
    ATTACHMENT_BATCH_REAPABLE_STATUSES,
    ATTACHMENT_BATCH_REJECTED,
    ATTACHMENT_BATCH_UNCERTAIN,
    ATTACHMENT_ITEM_REAPED,
    ATTACHMENT_ITEM_STORED,
    Database,
)

from tests.test_handlers import make_context, make_update

OWNER = 1
OTHER = 2
CID = "11111111222233334444555566667777"
TOKEN = "a" * 32


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None = None) -> str:
    return (dt or _now()).isoformat()


def _db(tmp_path) -> Database:
    return Database(str(tmp_path / "state.sqlite3"))


def _batch(db: Database, batch_id: str = "b1", status: str = ATTACHMENT_BATCH_PENDING) -> str:
    db.create_attachment_batch(batch_id, OWNER, CID, _iso(), status=status)
    return batch_id


def _item(
    db: Database,
    batch_id: str = "b1",
    *,
    item_id: str = "i1",
    status: str = ATTACHMENT_ITEM_STORED,
) -> None:
    db.add_attachment_item(
        item_id,
        batch_id,
        staging_token=TOKEN,
        display_name="a.txt",
        size_bytes=1,
        status=status,
        now=_iso(),
    )


def _staging_file(tmp_path, token: str = TOKEN, data: bytes = b"keep") -> None:
    root = staging_root_for(str(tmp_path / "state.sqlite3"))
    root.mkdir(parents=True, exist_ok=True)
    (root / token).write_bytes(data)


def _store(tmp_path, db: Database) -> StagingStore:
    return StagingStore(db, str(tmp_path / "state.sqlite3"))


def _store_call(store: StagingStore, *, item_id: str = "i1", row_created: bool = False):
    return store.store(
        telegram_id=OWNER,
        batch_id="b1",
        item_id=item_id,
        display_name="a.txt",
        chunks=[b"data"],
        row_created=row_created,
    )


async def _store_call_async(store: StagingStore, *, item_id: str = "i1"):
    return await store.store_async(
        telegram_id=OWNER,
        batch_id="b1",
        item_id=item_id,
        display_name="a.txt",
        chunks=[b"data"],
    )


# ============================================================================
# N1 — reject every non-pending parent before storage
# ============================================================================
NON_PENDING_STATES = [
    ATTACHMENT_BATCH_INTENT_RECORDED,
    ATTACHMENT_BATCH_DISPATCHING,
    ATTACHMENT_BATCH_UNCERTAIN,
    ATTACHMENT_BATCH_DELIVERED,
    ATTACHMENT_BATCH_EXPIRED,
    ATTACHMENT_BATCH_REJECTED,
    ATTACHMENT_BATCH_FAILED,
    ATTACHMENT_BATCH_CANCELLED,
    "future_status",
    "",
]


@pytest.mark.parametrize("status", NON_PENDING_STATES)
@pytest.mark.parametrize("path", ["sync", "async"])
def test_n1_store_rejects_non_pending_before_item_or_bytes(tmp_path, status, path):
    db = _db(tmp_path)
    _batch(db, status=status)
    store = _store(tmp_path, db)

    if path == "sync":
        res = _store_call(store)
    else:
        res = asyncio.run(_store_call_async(store))

    assert res.status is StageStatus.REJECTED_BATCH
    assert db.list_attachment_items("b1") == []
    root = staging_root_for(str(tmp_path / "state.sqlite3"))
    assert not root.exists() or list(root.iterdir()) == []
    assert db.get_attachment_batch("b1").status == status
    db.close()


def test_n1_store_row_created_non_pending_does_not_write_or_change_row(tmp_path):
    db = _db(tmp_path)
    _batch(db, status=ATTACHMENT_BATCH_CANCELLED)
    _item(db, status=ATTACHMENT_BATCH_PENDING)
    store = _store(tmp_path, db)

    res = _store_call(store, row_created=True)

    assert res.status is StageStatus.REJECTED_BATCH
    assert db.get_attachment_item("i1").status == ATTACHMENT_BATCH_PENDING
    root = staging_root_for(str(tmp_path / "state.sqlite3"))
    assert not root.exists() or list(root.iterdir()) == []
    db.close()


def test_n1_null_batch_status_is_schema_rejected(tmp_path):
    db = _db(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        db.create_attachment_batch("b1", OWNER, CID, _iso(), status=None)
    assert db.get_attachment_batch("b1") is None
    db.close()


# ============================================================================
# N2 — authoritative reaping guard checks the parent state
# ============================================================================
INELIGIBLE_PARENT_STATES = [
    ATTACHMENT_BATCH_PENDING,
    ATTACHMENT_BATCH_INTENT_RECORDED,
    ATTACHMENT_BATCH_DISPATCHING,
    ATTACHMENT_BATCH_UNCERTAIN,
    ATTACHMENT_BATCH_CANCELLED,
    "future_status",
    "",
]


@pytest.mark.parametrize("status", INELIGIBLE_PARENT_STATES)
def test_n2_reaping_rejects_ineligible_parent(tmp_path, status):
    db = _db(tmp_path)
    _batch(db, status=status)
    _item(db, status=ATTACHMENT_ITEM_STORED)

    assert db.mark_attachment_item_reaped("i1") is False
    assert db.get_attachment_item("i1").status == ATTACHMENT_ITEM_STORED
    db.close()


@pytest.mark.parametrize("status", sorted(ATTACHMENT_BATCH_REAPABLE_STATUSES))
def test_n2_reaping_allows_only_approved_terminal_parents(tmp_path, status):
    db = _db(tmp_path)
    _batch(db, status=status)
    _item(db, status=ATTACHMENT_ITEM_STORED)

    assert db.mark_attachment_item_reaped("i1") is True
    assert db.get_attachment_item("i1").status == ATTACHMENT_ITEM_REAPED
    db.close()


def test_n2_reaping_preserves_orphan_item_policy(tmp_path):
    db = _db(tmp_path)
    _item(db, batch_id="missing-batch", status=ATTACHMENT_ITEM_STORED)

    assert db.mark_attachment_item_reaped("i1") is True
    assert db.get_attachment_item("i1").status == ATTACHMENT_ITEM_REAPED
    db.close()


# ============================================================================
# T1 — cancellation vs expiry CAS / reaper
# ============================================================================
def test_t1_cancel_and_expiry_race_has_one_winner_and_reaper_respects_it(tmp_path):
    path = str(tmp_path / "state.sqlite3")
    seed = Database(path)
    _batch(seed)
    _item(seed, status=ATTACHMENT_ITEM_STORED)
    _staging_file(tmp_path)
    seed.close()

    barrier = threading.Barrier(2)
    results: dict[str, object] = {}

    def cancel_worker():
        db = Database(path)
        try:
            barrier.wait(timeout=5)
            results["cancel"] = db.cancel_pending_attachment_batch(
                OWNER, "b1", now=_iso()
            )
        except BaseException as exc:  # noqa: BLE001 — surfaced as a test failure
            results["cancel_error"] = exc
        finally:
            db.close()

    def expiry_worker():
        db = Database(path)
        try:
            barrier.wait(timeout=5)
            results["expiry"] = db.try_transition_attachment_batch_status(
                "b1",
                expected_status=ATTACHMENT_BATCH_PENDING,
                new_status=ATTACHMENT_BATCH_EXPIRED,
                now=_iso(),
            )
        except BaseException as exc:  # noqa: BLE001 — surfaced as a test failure
            results["expiry_error"] = exc
        finally:
            db.close()

    threads = [threading.Thread(target=cancel_worker), threading.Thread(target=expiry_worker)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not any(thread.is_alive() for thread in threads)
    assert "cancel_error" not in results and "expiry_error" not in results, results

    db = Database(path)
    if results["cancel"] == "cancelled":
        assert results["expiry"] is False
        assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_CANCELLED
        report = AttachmentReaper(db, path).sweep(now=_now())
        assert report.files_deleted == 0
        assert db.get_attachment_item("i1").status == ATTACHMENT_ITEM_STORED
        assert (staging_root_for(path) / TOKEN).exists()
    else:
        assert results["cancel"] == "not_eligible"
        assert results["expiry"] is True
        assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_EXPIRED
        report = AttachmentReaper(db, path).sweep(now=_now())
        assert report.files_deleted == 1
        assert db.get_attachment_item("i1").status == ATTACHMENT_ITEM_REAPED
        assert not (staging_root_for(path) / TOKEN).exists()
    db.close()


# ============================================================================
# T2 — handler response for REJECTED_BATCH
# ============================================================================
class _FakeStore:
    max_bytes = 1024


class _FakeService:
    store = _FakeStore()

    def __init__(self, result):
        self.result = result
        self.calls = 0

    async def accept(self, **kwargs):
        self.calls += 1
        return self.result


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        (AcceptOutcome.REJECTED, h.ATTACHMENT_BATCH_CANCELLED_TEXT),
        (AcceptOutcome.ACCEPTED, h.ATTACHMENT_ERROR_TEXT),
    ],
)
def test_t2_handler_rejected_batch_does_not_report_success(
    tmp_path, monkeypatch, outcome, expected
):
    ctx = make_context(OWNER, tmp_path)
    db = ctx.bot_data["db"]
    db.set_last_accessed_conversation(OWNER, CID)
    update = make_update(OWNER, text="")
    update.update_id = 901
    update.message.document = SimpleNamespace(
        file_id="file-1", file_name="a.txt", file_size=1
    )

    service = _FakeService(AcceptResult(outcome, stage=StageStatus.REJECTED_BATCH))
    monkeypatch.setattr(h, "_attachment_service", lambda context: service)

    asyncio.run(h.handle_attachment(update, ctx))

    assert service.calls == 1
    assert update.message.replies == [expected]
    assert h.ATTACHMENT_ACCEPTED_TEXT not in update.message.replies
    db.close()


# ============================================================================
# T3 — /attachments_cancel preserves route/user_state
# ============================================================================
def test_t3_attachments_cancel_does_not_mutate_route_or_user_state(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    db = ctx.bot_data["db"]
    ctx.bot_data["attachment_store"] = _store(tmp_path, db)
    db.set_awaiting(OWNER, CID, "route", "chat")
    before = db.awaiting_state(OWNER)
    _batch(db)
    _item(db, status=ATTACHMENT_ITEM_STORED)
    _staging_file(tmp_path)

    update = make_update(OWNER, text="/attachments_cancel")
    update.update_id = 902
    update.args = ["b1", "confirm"]
    ctx.args = update.args

    asyncio.run(h.attachments_cancel(update, ctx))

    assert db.awaiting_state(OWNER) == before
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_CANCELLED
    assert db.get_attachment_item("i1").status == ATTACHMENT_ITEM_STORED
    assert (staging_root_for(str(tmp_path / "state.sqlite3")) / TOKEN).exists()
    db.close()


# ============================================================================
# T4 — /attachments_clear rejects cancelled batches
# ============================================================================
def test_t4_attachments_clear_rejects_cancelled_batch(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    db = ctx.bot_data["db"]
    _batch(db, status=ATTACHMENT_BATCH_CANCELLED)

    update = make_update(OWNER, text="/attachments_clear")
    update.update_id = 903
    update.args = ["b1", "confirm"]
    ctx.args = update.args

    asyncio.run(h.attachments_clear(update, ctx))

    assert update.message.replies == ["الإخلاء مسموح فقط لدفعة expired أو rejected."]
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_CANCELLED
    assert db.is_attachment_terminal_cleared(OWNER, "b1") is False
    assert db.clear_attachment_terminal_batch(OWNER, "b1", now=_iso()) == "not_eligible"
    db.close()


# ============================================================================
# T5 — direct acceptance vs cancellation interleaving
# ============================================================================
def test_t5_accept_and_cancel_interleaving_storage_wins_without_mixed_state(
    tmp_path, monkeypatch
):
    db = _db(tmp_path)
    _batch(db)
    store = _store(tmp_path, db)
    service = AttachmentService(db, store, None, None)

    async def fake_authorized(self, conversation_id, *, db):
        return conversation_id, "ok"

    monkeypatch.setattr(AttachmentService, "_authorized", fake_authorized)

    entered = asyncio.Event()
    release = asyncio.Event()

    async def chunks_factory():
        entered.set()
        await release.wait()
        return [b"data"]

    async def run():
        accept_task = asyncio.create_task(
            service.accept(
                telegram_id=OWNER,
                conversation_id=CID,
                display_name="a.txt",
                declared_size=1,
                update_id=904,
                now=_now(),
                chunks_factory=chunks_factory,
            )
        )
        await entered.wait()
        cancel_task = asyncio.create_task(
            service.cancel_pending_batch(
                telegram_id=OWNER, batch_id="b1", now=_iso()
            )
        )
        await asyncio.sleep(0)
        assert not cancel_task.done(), "cancellation entered the storage window"
        release.set()
        accepted = await accept_task
        cancelled = await cancel_task
        return accepted, cancelled

    accepted, cancelled = asyncio.run(run())

    assert accepted.outcome is AcceptOutcome.STORED
    assert accepted.stage is StageStatus.STORED
    assert cancelled == "cancelled"
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_CANCELLED
    item = db.get_attachment_item(accepted.item_id)
    assert item.status == ATTACHMENT_ITEM_STORED
    assert (staging_root_for(str(tmp_path / "state.sqlite3")) / item.staging_token).exists()
    db.close()


# ============================================================================
# T6 — SQLite lock/error behavior for the cancellation transaction
# ============================================================================
class _SignalConnection:
    """Small proxy used only to observe entry into BEGIN IMMEDIATE."""

    def __init__(self, conn, on_execute):
        self._conn = conn
        self._on_execute = on_execute

    def execute(self, sql, *args, **kwargs):
        self._on_execute(sql)
        return self._conn.execute(sql, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._conn, name)


def test_t6_cancellation_waits_for_configured_write_lock_then_commits(tmp_path):
    path = str(tmp_path / "state.sqlite3")
    db = Database(path)
    _batch(db)
    assert db._conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000

    blocker = sqlite3.connect(path, timeout=0)
    blocker.execute("BEGIN IMMEDIATE")
    entered = threading.Event()
    db._conn = _SignalConnection(
        db._conn,
        lambda sql: entered.set() if "BEGIN IMMEDIATE" in sql.upper() else None,
    )
    result: dict[str, object] = {}

    def worker():
        try:
            result["value"] = db.cancel_pending_attachment_batch(
                OWNER, "b1", now=_iso()
            )
        except BaseException as exc:  # noqa: BLE001 — surfaced as a test failure
            result["error"] = exc

    thread = threading.Thread(target=worker)
    thread.start()
    assert entered.wait(2)
    assert thread.is_alive(), "cancellation did not wait for the write lock"
    blocker.rollback()
    blocker.close()
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert "error" not in result, result
    assert result["value"] == "cancelled"
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_CANCELLED
    db.close()


def test_t6_permanent_db_error_does_not_report_success(tmp_path, monkeypatch):
    db = _db(tmp_path)
    _batch(db)

    def boom(*args, **kwargs):
        raise sqlite3.OperationalError("simulated permanent database failure")

    monkeypatch.setattr(db, "mark_update_outcome", boom)
    with pytest.raises(sqlite3.OperationalError):
        db.cancel_pending_attachment_batch(OWNER, "b1", now=_iso(), update_id=905)

    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_PENDING
    db.close()


# ============================================================================
# T7 — controlled commit-boundary fault injection + reopen
# ============================================================================
class _CommitProxy:
    def __init__(self, conn, *, before=None, after=None):
        self._conn = conn
        self._before = before
        self._after = after

    def commit(self):
        if self._before is not None:
            self._before()
        result = self._conn.commit()
        if self._after is not None:
            self._after()
        return result

    def __getattr__(self, name):
        return getattr(self._conn, name)


def test_t7_failure_before_commit_leaves_pending_after_reopen(tmp_path):
    path = str(tmp_path / "state.sqlite3")
    db = Database(path)
    _batch(db)
    db._conn = _CommitProxy(
        db._conn,
        before=lambda: (_ for _ in ()).throw(RuntimeError("fault before commit")),
    )

    with pytest.raises(RuntimeError):
        db.cancel_pending_attachment_batch(OWNER, "b1", now=_iso())

    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_PENDING
    db.close()
    reopened = Database(path)
    assert reopened.get_attachment_batch("b1").status == ATTACHMENT_BATCH_PENDING
    reopened.close()


def test_t7_failure_after_commit_is_durable_but_raises(tmp_path):
    path = str(tmp_path / "state.sqlite3")
    db = Database(path)
    _batch(db)
    db._conn = _CommitProxy(
        db._conn,
        after=lambda: (_ for _ in ()).throw(RuntimeError("fault after commit")),
    )

    with pytest.raises(RuntimeError):
        db.cancel_pending_attachment_batch(OWNER, "b1", now=_iso())

    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_CANCELLED
    db.close()
    reopened = Database(path)
    assert reopened.get_attachment_batch("b1").status == ATTACHMENT_BATCH_CANCELLED
    reopened.close()
