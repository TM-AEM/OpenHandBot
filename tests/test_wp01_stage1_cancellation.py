"""OHB2-WP01 Stage 1 — safe active attachment-batch cancellation.

Deterministic tests only: temporary SQLite files, local temporary staging files,
fake Telegram objects, and explicit events/locks instead of sleeps for races.
"""
from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timedelta, timezone

import pytest

import bot.handlers as h
from bot import update_outcomes as uo
from bot.attachments import (
    AttachmentReaper,
    AttachmentService,
    StagingStore,
    StageStatus,
    staging_root_for,
)
from bot.db import (
    ATTACHMENT_BATCH_CANCELLED,
    ATTACHMENT_BATCH_DELIVERED,
    ATTACHMENT_BATCH_EXPIRED,
    ATTACHMENT_BATCH_FAILED,
    ATTACHMENT_BATCH_INTENT_RECORDED,
    ATTACHMENT_BATCH_PENDING,
    ATTACHMENT_BATCH_REJECTED,
    ATTACHMENT_ITEM_STORED,
    AttachmentBatchStateChanged,
    AttachmentRoutingState,
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


def _batch(
    db: Database,
    batch_id: str = "b1",
    status: str = ATTACHMENT_BATCH_PENDING,
    *,
    owner: int = OWNER,
    cid: str = CID,
    t0: str | None = None,
) -> str:
    db.create_attachment_batch(
        batch_id,
        owner,
        cid,
        t0 or _iso(),
        status=status,
    )
    return batch_id


def _item(
    db: Database,
    batch_id: str = "b1",
    *,
    item_id: str = "i1",
    token: str = TOKEN,
    status: str = ATTACHMENT_ITEM_STORED,
) -> None:
    db.add_attachment_item(
        item_id,
        batch_id,
        staging_token=token,
        display_name="a.txt",
        size_bytes=1,
        status=status,
        now=_iso(),
    )


def _identity(db: Database, batch_id: str = "b1", *, message_id: int = 77) -> None:
    db._conn.execute(
        "INSERT INTO attachment_message_identity"
        "(telegram_id, chat_id, message_id, batch_id, conversation_id, created_at) "
        "VALUES(?, ?, ?, ?, ?, ?)",
        (OWNER, 99, message_id, batch_id, CID, _iso()),
    )
    db._conn.commit()


def _staging_file(tmp_path, token: str = TOKEN, data: bytes = b"keep") -> None:
    root = staging_root_for(str(tmp_path / "state.sqlite3"))
    root.mkdir(parents=True, exist_ok=True)
    (root / token).write_bytes(data)


def _classify(db: Database):
    return db.classify_attachment_routing(OWNER, now_iso=_iso())


def _ctx(tmp_path, db: Database):
    ctx = make_context(OWNER, tmp_path)
    ctx.bot_data["db"] = db
    ctx.bot_data["attachment_store"] = StagingStore(db, str(tmp_path / "state.sqlite3"))
    return ctx


def _cancel_update(ctx, update_id: int, batch_id: str = "b1", *, confirm: bool = True):
    update = make_update(OWNER, "/attachments_cancel")
    update.update_id = update_id
    update.args = [batch_id, "confirm"] if confirm else [batch_id]
    ctx.args = update.args
    return update


# ============================================================================
# A. Cancellation contract
# ============================================================================
def test_owned_pending_is_cancelled_and_all_data_is_preserved(tmp_path):
    db = _db(tmp_path)
    _batch(db)
    _item(db)
    _identity(db)
    _staging_file(tmp_path)
    before = (
        db.count_attachment_batches(),
        db.count_attachment_items(),
        db.count_message_identities(),
    )

    result = db.cancel_pending_attachment_batch(
        OWNER, "b1", now=_iso(), update_id=8101
    )

    assert result == "cancelled"
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_CANCELLED
    assert db.get_attachment_item("i1").status == ATTACHMENT_ITEM_STORED
    assert (
        db.count_attachment_batches(),
        db.count_attachment_items(),
        db.count_message_identities(),
    ) == before
    assert (staging_root_for(str(tmp_path / "state.sqlite3")) / TOKEN).read_bytes() == b"keep"
    assert db.update_outcome(8101) == uo.DURABLE_COMPLETED
    assert _classify(db).state is AttachmentRoutingState.CANCELLED
    db.close()


def test_wrong_owner_and_unknown_id_do_not_change_anything(tmp_path):
    db = _db(tmp_path)
    _batch(db, owner=OWNER)
    assert db.cancel_pending_attachment_batch(OTHER, "b1", now=_iso()) == "not_found"
    assert db.cancel_pending_attachment_batch(OWNER, "missing", now=_iso()) == "not_found"
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_PENDING
    db.close()


@pytest.mark.parametrize(
    "status",
    [
        ATTACHMENT_BATCH_INTENT_RECORDED,
        "dispatching",
        "uncertain",
        ATTACHMENT_BATCH_DELIVERED,
        ATTACHMENT_BATCH_EXPIRED,
        ATTACHMENT_BATCH_REJECTED,
        ATTACHMENT_BATCH_FAILED,
    ],
)
def test_ineligible_states_are_not_changed(tmp_path, status):
    db = _db(tmp_path)
    _batch(db, status=status)
    assert db.cancel_pending_attachment_batch(OWNER, "b1", now=_iso()) == "not_eligible"
    assert db.get_attachment_batch("b1").status == status
    db.close()


def test_cancelled_is_idempotent_and_does_not_transition_again(tmp_path):
    db = _db(tmp_path)
    _batch(db, status=ATTACHMENT_BATCH_CANCELLED)
    _item(db)
    result = db.cancel_pending_attachment_batch(OWNER, "b1", now=_iso(), update_id=8102)
    assert result == "already_cancelled"
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_CANCELLED
    assert db.get_attachment_item("i1").status == ATTACHMENT_ITEM_STORED
    assert db.update_outcome(8102) == uo.EXPLICITLY_IGNORED
    db.close()


def test_duplicate_update_does_not_overwrite_or_cancel(tmp_path):
    db = _db(tmp_path)
    _batch(db)
    db.mark_update_outcome(8103, _iso(), uo.DURABLE_COMPLETED)
    assert db.cancel_pending_attachment_batch(
        OWNER, "b1", now=_iso(), update_id=8103
    ) == "duplicate"
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_PENDING
    assert db.update_outcome(8103) == uo.DURABLE_COMPLETED
    db.close()


def test_database_failure_rolls_back_cancellation(tmp_path, monkeypatch):
    db = _db(tmp_path)
    _batch(db)

    def boom(*args, **kwargs):
        raise RuntimeError("simulated outcome failure")

    monkeypatch.setattr(db, "mark_update_outcome", boom)
    with pytest.raises(RuntimeError):
        db.cancel_pending_attachment_batch(OWNER, "b1", now=_iso(), update_id=8104)
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_PENDING
    db.close()


def test_cancelled_state_persists_across_database_reopen(tmp_path):
    path = str(tmp_path / "persist.sqlite3")
    db = Database(path)
    _batch(db)
    assert db.cancel_pending_attachment_batch(OWNER, "b1", now=_iso()) == "cancelled"
    db.close()
    reopened = Database(path)
    assert reopened.get_attachment_batch("b1").status == ATTACHMENT_BATCH_CANCELLED
    assert _classify(reopened).state is AttachmentRoutingState.CANCELLED
    reopened.close()


def test_two_concurrent_cancellation_attempts_are_safe(tmp_path):
    db = _db(tmp_path)
    _batch(db)
    store = StagingStore(db, str(tmp_path / "state.sqlite3"))
    service = AttachmentService(db, store, None, None)

    async def run():
        return await asyncio.gather(
            service.cancel_pending_batch(
                telegram_id=OWNER, batch_id="b1", now=_iso(), update_id=8111
            ),
            service.cancel_pending_batch(
                telegram_id=OWNER, batch_id="b1", now=_iso(), update_id=8112
            ),
        )

    results = asyncio.run(run())
    assert sorted(results) == ["already_cancelled", "cancelled"]
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_CANCELLED
    db.close()


def test_append_item_cannot_land_in_cancelled_batch(tmp_path):
    db = _db(tmp_path)
    _batch(db)
    batch = db.get_attachment_batch("b1")
    assert db.cancel_pending_attachment_batch(OWNER, "b1", now=_iso()) == "cancelled"
    with pytest.raises(AttachmentBatchStateChanged):
        db.accept_attachment_item(
            batch,
            item_id="late",
            display_name="late.txt",
            now=_iso(),
            staging_token="b" * 32,
        )
    assert db.count_attachment_items() == 0
    db.close()


# ============================================================================
# B. Storage safety
# ============================================================================
def _pending_store_env(tmp_path):
    db = _db(tmp_path)
    _batch(db)
    _item(db, token=TOKEN, status=ATTACHMENT_BATCH_PENDING)
    store = StagingStore(db, str(tmp_path / "state.sqlite3"))
    return db, store


def test_store_prepare_rejects_cancelled_batch(tmp_path):
    db = _db(tmp_path)
    _batch(db, status=ATTACHMENT_BATCH_CANCELLED)
    store = StagingStore(db, str(tmp_path / "state.sqlite3"))
    res = store.store(
        telegram_id=OWNER,
        batch_id="b1",
        item_id="i1",
        display_name="x.txt",
        chunks=[b"x"],
    )
    assert res.status is StageStatus.REJECTED_BATCH
    assert not staging_root_for(str(tmp_path / "state.sqlite3")).exists()
    db.close()


def test_store_async_cannot_persist_into_cancelled_batch(tmp_path):
    db = _db(tmp_path)
    _batch(db, status=ATTACHMENT_BATCH_CANCELLED)
    _item(db, token=TOKEN)
    store = StagingStore(db, str(tmp_path / "state.sqlite3"))

    async def run():
        return await store.store_async(
            telegram_id=OWNER,
            batch_id="b1",
            item_id="i1",
            display_name="x.txt",
            chunks=[b"x"],
            row_created=True,
            staging_token=TOKEN,
        )

    res = asyncio.run(run())
    assert res.status is StageStatus.REJECTED_BATCH
    assert not (staging_root_for(str(tmp_path / "state.sqlite3")) / TOKEN).exists()
    db.close()


def test_sync_store_cannot_persist_into_cancelled_batch(tmp_path):
    db = _db(tmp_path)
    _batch(db, status=ATTACHMENT_BATCH_CANCELLED)
    _item(db, token=TOKEN)
    store = StagingStore(db, str(tmp_path / "state.sqlite3"))
    res = store.store(
        telegram_id=OWNER,
        batch_id="b1",
        item_id="i1",
        display_name="x.txt",
        chunks=[b"x"],
        row_created=True,
        staging_token=TOKEN,
    )
    assert res.status is StageStatus.REJECTED_BATCH
    assert not (staging_root_for(str(tmp_path / "state.sqlite3")) / TOKEN).exists()
    db.close()


def test_cancellation_wins_before_store_async_preparation(tmp_path):
    db, store = _pending_store_env(tmp_path)
    service = AttachmentService(db, store, None, None)

    async def run():
        result = await service.cancel_pending_batch(
            telegram_id=OWNER, batch_id="b1", now=_iso(), update_id=8121
        )
        stage = await store.store_async(
            telegram_id=OWNER,
            batch_id="b1",
            item_id="i1",
            display_name="x.txt",
            chunks=[b"x"],
            row_created=True,
            staging_token=TOKEN,
        )
        return result, stage

    result, stage = asyncio.run(run())
    assert result == "cancelled"
    assert stage.status is StageStatus.REJECTED_BATCH
    assert not (staging_root_for(str(tmp_path / "state.sqlite3")) / TOKEN).exists()
    assert db.get_attachment_item("i1").status == ATTACHMENT_BATCH_PENDING
    db.close()


def test_store_async_wins_and_cancellation_preserves_stored_file(tmp_path):
    db, store = _pending_store_env(tmp_path)
    service = AttachmentService(db, store, None, None)
    started = threading.Event()
    release = threading.Event()
    db_called_while_store_running = []

    def chunks():
        yield b"a"
        started.set()
        assert release.wait(5)
        yield b"b"

    original_cancel = db.cancel_pending_attachment_batch

    def cancel_spy(*args, **kwargs):
        # The guard must not release the store until the write/finalize is done.
        db_called_while_store_running.append(
            db.get_attachment_item("i1").status == ATTACHMENT_ITEM_STORED
        )
        return original_cancel(*args, **kwargs)

    db.cancel_pending_attachment_batch = cancel_spy

    async def run():
        nonlocal store_task
        store_task = asyncio.create_task(
            store.store_async(
                telegram_id=OWNER,
                batch_id="b1",
                item_id="i1",
                display_name="x.txt",
                chunks=chunks(),
                row_created=True,
                staging_token=TOKEN,
            )
        )
        assert await asyncio.to_thread(started.wait, 5)
        cancel_task = asyncio.create_task(
            service.cancel_pending_batch(
                telegram_id=OWNER, batch_id="b1", now=_iso(), update_id=8122
            )
        )
        # Let the cancellation task enter its guard; it must wait for the store.
        await asyncio.sleep(0)
        release.set()
        stage = await store_task
        result = await cancel_task
        return stage, result

    store_task = None
    stage, result = asyncio.run(run())
    assert stage.status is StageStatus.STORED
    assert result == "cancelled"
    assert db_called_while_store_running == [True]
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_CANCELLED
    assert db.get_attachment_item("i1").status == ATTACHMENT_ITEM_STORED
    assert (staging_root_for(str(tmp_path / "state.sqlite3")) / TOKEN).read_bytes() == b"ab"
    db.close()


def test_sync_store_wins_and_cancellation_preserves_stored_file(tmp_path):
    db, store = _pending_store_env(tmp_path)
    service = AttachmentService(db, store, None, None)
    started = threading.Event()
    release = threading.Event()
    db_called_while_store_running = []
    original_cancel = db.cancel_pending_attachment_batch

    def chunks():
        yield b"a"
        started.set()
        assert release.wait(5)
        yield b"b"

    def cancel_spy(*args, **kwargs):
        db_called_while_store_running.append(
            db.get_attachment_item("i1").status == ATTACHMENT_ITEM_STORED
        )
        return original_cancel(*args, **kwargs)

    db.cancel_pending_attachment_batch = cancel_spy

    async def run():
        nonlocal store_task
        store_task = asyncio.create_task(
            asyncio.to_thread(
                store.store,
                telegram_id=OWNER,
                batch_id="b1",
                item_id="i1",
                display_name="x.txt",
                chunks=chunks(),
                row_created=True,
                staging_token=TOKEN,
            )
        )
        assert await asyncio.to_thread(started.wait, 5)
        cancel_task = asyncio.create_task(
            service.cancel_pending_batch(
                telegram_id=OWNER, batch_id="b1", now=_iso(), update_id=8123
            )
        )
        await asyncio.sleep(0)
        release.set()
        stage = await store_task
        result = await cancel_task
        return stage, result

    store_task = None
    stage, result = asyncio.run(run())
    assert stage.status is StageStatus.STORED
    assert result == "cancelled"
    assert db_called_while_store_running == [True]
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_CANCELLED
    assert db.get_attachment_item("i1").status == ATTACHMENT_ITEM_STORED
    assert (staging_root_for(str(tmp_path / "state.sqlite3")) / TOKEN).read_bytes() == b"ab"
    db.close()


# ============================================================================
# C. Reaper safety
# ============================================================================
def _sweep(db, tmp_path):
    return AttachmentReaper(db, str(tmp_path / "state.sqlite3")).sweep(now=_now())


def test_cancelled_batch_is_excluded_from_sweep_and_files_remain(tmp_path):
    db = _db(tmp_path)
    _batch(db, status=ATTACHMENT_BATCH_CANCELLED)
    _item(db, status=ATTACHMENT_ITEM_STORED)
    _identity(db)
    _staging_file(tmp_path)
    before = (db.count_attachment_batches(), db.count_attachment_items(),
              db.count_message_identities())
    report = _sweep(db, tmp_path)
    assert report.files_deleted == 0
    assert report.skipped >= 1
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_CANCELLED
    assert db.get_attachment_item("i1").status == ATTACHMENT_ITEM_STORED
    assert (db.count_attachment_batches(), db.count_attachment_items(),
            db.count_message_identities()) == before
    assert (staging_root_for(str(tmp_path / "state.sqlite3")) / TOKEN).exists()
    db.close()


def test_plan_batch_explicitly_skips_cancelled(tmp_path):
    db = _db(tmp_path)
    _batch(db, status=ATTACHMENT_BATCH_CANCELLED)
    reaper = AttachmentReaper(db, str(tmp_path / "state.sqlite3"))
    from bot.attachments import SweepPlan

    plan = SweepPlan()
    reaper._plan_batch(db.get_attachment_batch("b1"), set(), plan)
    assert plan.immediate
    assert plan.immediate[0].outcome.value == "skipped"
    assert plan.immediate[0].reason == "cancelled_non_reapable"
    db.close()


@pytest.mark.parametrize(
    "status",
    [ATTACHMENT_BATCH_CANCELLED, ATTACHMENT_BATCH_INTENT_RECORDED, ATTACHMENT_BATCH_DELIVERED],
)
def test_mark_expired_cas_does_not_overwrite_non_pending(tmp_path, status):
    db = _db(tmp_path)
    _batch(db, t0=_iso(_now() - timedelta(minutes=20)))
    batch = db.get_attachment_batch("b1")
    db.mark_attachment_batch_status("b1", status, now=_iso())
    reaper = AttachmentReaper(db, str(tmp_path / "state.sqlite3"))
    report = {"errors": 0, "skipped": 0}
    reaper._mark_expired(batch, _iso(), report)
    assert db.get_attachment_batch("b1").status == status
    assert report["skipped"] == 1
    db.close()


def test_item_reaping_rejects_cancelled_parent(tmp_path):
    db = _db(tmp_path)
    _batch(db, status=ATTACHMENT_BATCH_CANCELLED)
    _item(db, status=ATTACHMENT_ITEM_STORED)
    assert db.mark_attachment_item_reaped("i1") is False
    assert db.get_attachment_item("i1").status == ATTACHMENT_ITEM_STORED
    db.close()


def test_existing_terminal_reaping_still_works(tmp_path):
    db = _db(tmp_path)
    _batch(db, status=ATTACHMENT_BATCH_EXPIRED)
    _item(db, status=ATTACHMENT_ITEM_STORED)
    _staging_file(tmp_path)
    report = _sweep(db, tmp_path)
    assert report.files_deleted == 1
    assert not (staging_root_for(str(tmp_path / "state.sqlite3")) / TOKEN).exists()
    assert db.get_attachment_item("i1").status == "reaped"
    db.close()


# ============================================================================
# D. Command behavior
# ============================================================================
def test_command_registered_in_bot_commands_and_help():
    from bot.app import BOT_COMMANDS

    assert "attachments_cancel" in {name for name, _ in BOT_COMMANDS}
    assert "/attachments_cancel" in h.HELP_TEXT


def test_command_success_only_after_commit_and_preserves_data(tmp_path):
    db = _db(tmp_path)
    _batch(db)
    _item(db)
    _staging_file(tmp_path)
    ctx = _ctx(tmp_path, db)
    update = _cancel_update(ctx, 8201)
    asyncio.run(h.attachments_cancel(update, ctx))
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_CANCELLED
    assert db.update_outcome(8201) == uo.DURABLE_COMPLETED
    assert update.message.replies == [
        "اتلغت معالجة الدفعة. الملفات والبيانات محفوظة محليًا ومش هتتحذف تلقائيًا."
    ]
    assert db.get_attachment_item("i1").status == ATTACHMENT_ITEM_STORED
    assert (staging_root_for(str(tmp_path / "state.sqlite3")) / TOKEN).exists()
    db.close()


def test_command_requires_exact_arguments(tmp_path):
    db = _db(tmp_path)
    _batch(db)
    ctx = _ctx(tmp_path, db)
    for args in ([], ["b1"], ["b1", "nope"], ["b1", "confirm", "extra"]):
        update = _cancel_update(ctx, 8202)
        ctx.args = args
        asyncio.run(h.attachments_cancel(update, ctx))
        assert "الاستخدام" in update.message.replies[0]
        assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_PENDING
    db.close()


def test_command_is_owner_scoped_and_does_not_leak(tmp_path):
    db = _db(tmp_path)
    _batch(db, owner=OTHER)
    ctx = _ctx(tmp_path, db)
    update = _cancel_update(ctx, 8203)
    asyncio.run(h.attachments_cancel(update, ctx))
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_PENDING
    assert "مفيش دفعة" in update.message.replies[0]
    assert "b1" not in update.message.replies[0]
    db.close()


@pytest.mark.parametrize(
    "status",
    [ATTACHMENT_BATCH_INTENT_RECORDED, ATTACHMENT_BATCH_EXPIRED, ATTACHMENT_BATCH_REJECTED],
)
def test_command_rejects_ineligible_states(tmp_path, status):
    db = _db(tmp_path)
    _batch(db, status=status)
    ctx = _ctx(tmp_path, db)
    update = _cancel_update(ctx, 8204)
    asyncio.run(h.attachments_cancel(update, ctx))
    assert db.get_attachment_batch("b1").status == status
    assert "pending" in update.message.replies[0]
    db.close()


def test_command_already_cancelled_and_duplicate_are_safe(tmp_path):
    db = _db(tmp_path)
    _batch(db)
    ctx = _ctx(tmp_path, db)
    asyncio.run(h.attachments_cancel(_cancel_update(ctx, 8205), ctx))
    second = _cancel_update(ctx, 8206)
    asyncio.run(h.attachments_cancel(second, ctx))
    assert "ملغاة بالفعل" in second.message.replies[0]
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_CANCELLED

    db2_dir = tmp_path / "other"
    db2_dir.mkdir()
    db2 = Database(str(db2_dir / "state.sqlite3"))
    _batch(db2)
    db2.mark_update_outcome(8207, _iso(), uo.DURABLE_COMPLETED)
    ctx2 = _ctx(db2_dir, db2)
    duplicate = _cancel_update(ctx2, 8207)
    asyncio.run(h.attachments_cancel(duplicate, ctx2))
    assert "اتعالج قبل كده" in duplicate.message.replies[0]
    assert db2.get_attachment_batch("b1").status == ATTACHMENT_BATCH_PENDING
    db.close()
    db2.close()


def test_command_database_failure_has_no_success_reply(tmp_path, monkeypatch):
    db = _db(tmp_path)
    _batch(db)
    ctx = _ctx(tmp_path, db)

    def boom(*args, **kwargs):
        raise RuntimeError("simulated cancellation failure")

    monkeypatch.setattr(db, "cancel_pending_attachment_batch", boom)
    update = _cancel_update(ctx, 8208)
    with pytest.raises(RuntimeError):
        asyncio.run(h.attachments_cancel(update, ctx))
    assert update.message.replies == []
    db.close()


def test_cancelled_routing_is_non_blocking_for_text(tmp_path):
    db = _db(tmp_path)
    _batch(db, status=ATTACHMENT_BATCH_CANCELLED)
    ctx = _ctx(tmp_path, db)
    update = make_update(OWNER, "prompt")
    update.update_id = 8210
    assert asyncio.run(h._handle_accompanying_text(update, ctx)) is False
    assert update.message.replies == []
    db.close()
