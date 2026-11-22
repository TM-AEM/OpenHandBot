"""OHB2-WP01 — attachment lifecycle, terminal clearance, and truthful messaging.

Deterministic tests only: real SQLite files in tmp_path, no Telegram/OpenHands network.
The owner-approved policy is OD-01 Option C (explicit per-batch clearance for
expired/rejected only) and OD-03 Option A (document intake default-off).
"""
from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

import bot.handlers as h
from bot import update_outcomes as uo
from bot.db import (
    ATTACHMENT_BATCH_DELIVERED,
    ATTACHMENT_BATCH_EXPIRED,
    ATTACHMENT_BATCH_FAILED,
    ATTACHMENT_BATCH_INTENT_RECORDED,
    ATTACHMENT_BATCH_PENDING,
    ATTACHMENT_BATCH_REJECTED,
    ATTACHMENT_TERMINAL_CLEARANCE_KEY_PREFIX,
    AttachmentBatchIntegrityError,
    AttachmentRoutingState,
    Database,
)

from tests.test_handlers import make_context, make_update

OWNER = 1
OTHER = 2
CID = "11111111222233334444555566667777"
CID_B = "22222222333344445555666677778888"


def _db(tmp_path) -> Database:
    return Database(str(tmp_path / "wp01.sqlite3"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _expired_t0() -> str:
    return _iso(_now() - timedelta(minutes=20))


def _live_t0() -> str:
    return _iso(_now() - timedelta(minutes=1))


def _batch(
    db: Database,
    batch_id: str,
    status: str,
    *,
    owner: int = OWNER,
    cid: str = CID,
    t0: str | None = None,
) -> str:
    db.create_attachment_batch(
        batch_id,
        owner,
        cid,
        t0 or (_expired_t0() if status in (ATTACHMENT_BATCH_EXPIRED,) else _live_t0()),
        status=status,
    )
    return batch_id


def _identity(db: Database, batch_id: str, *, message_id: int = 77, owner: int = OWNER) -> None:
    db._conn.execute(
        "INSERT INTO attachment_message_identity"
        "(telegram_id, chat_id, message_id, batch_id, conversation_id, created_at) "
        "VALUES(?, ?, ?, ?, ?, ?)",
        (owner, 99, message_id, batch_id, CID, _iso(_now())),
    )
    db._conn.commit()


def _classify(db: Database, *, message_id: int | None = None):
    return db.classify_attachment_routing(
        OWNER,
        now_iso=_iso(_now()),
        chat_id=99 if message_id is not None else None,
        message_id=message_id,
    )


# ============================================================================
# Database-level clearance contract
# ============================================================================
@pytest.mark.parametrize("status", [ATTACHMENT_BATCH_EXPIRED, ATTACHMENT_BATCH_REJECTED])
def test_explicit_clearance_succeeds_for_expired_and_rejected(tmp_path, status):
    db = _db(tmp_path)
    batch_id = _batch(db, "b1", status)
    assert _classify(db).state is AttachmentRoutingState.TERMINAL_UNPROVEN
    assert db.clear_attachment_terminal_batch(OWNER, batch_id, now=_iso(_now())) == "cleared"
    assert db.is_attachment_terminal_cleared(OWNER, batch_id) is True
    assert _classify(db).state is AttachmentRoutingState.NONE
    db.close()


def test_cancel_alone_does_not_clear_terminal_block(tmp_path):
    db = _db(tmp_path)
    batch_id = _batch(db, "b1", ATTACHMENT_BATCH_EXPIRED)
    ctx = make_context(OWNER, tmp_path)
    ctx.bot_data["db"] = db
    update = make_update(OWNER, "/cancel")
    update.update_id = 7001

    asyncio.run(h.cancel_route(update, ctx))

    assert db.is_attachment_terminal_cleared(OWNER, batch_id) is False
    assert _classify(db).state is AttachmentRoutingState.TERMINAL_UNPROVEN
    assert db.get_attachment_batch(batch_id).status == ATTACHMENT_BATCH_EXPIRED
    db.close()


def test_cancel_does_not_delete_active_batch_data(tmp_path):
    db = _db(tmp_path)
    batch_id = _batch(db, "b1", ATTACHMENT_BATCH_PENDING, t0=_live_t0())
    db.add_attachment_item("i1", batch_id, staging_token="tok", display_name="a.txt",
                           size_bytes=1, status="stored", now=_iso(_now()))
    ctx = make_context(OWNER, tmp_path)
    ctx.bot_data["db"] = db
    update = make_update(OWNER, "/cancel")
    update.update_id = 7004

    asyncio.run(h.cancel_route(update, ctx))

    assert db.get_attachment_batch(batch_id).status == ATTACHMENT_BATCH_PENDING
    assert db.get_attachment_item("i1").status == "stored"
    assert db.count_attachment_batches() == 1
    assert db.count_attachment_items() == 1
    assert db.is_attachment_terminal_cleared(OWNER, batch_id) is False
    db.close()


@pytest.mark.parametrize("status", [ATTACHMENT_BATCH_DELIVERED, ATTACHMENT_BATCH_FAILED])
def test_clearance_rejected_for_delivered_and_failed(tmp_path, status):
    db = _db(tmp_path)
    batch_id = _batch(db, "b1", status)
    assert db.clear_attachment_terminal_batch(OWNER, batch_id, now=_iso(_now())) == "not_eligible"
    assert db.is_attachment_terminal_cleared(OWNER, batch_id) is False
    assert _classify(db).state is AttachmentRoutingState.TERMINAL_UNPROVEN
    db.close()


def test_clearance_rejected_for_pending_and_intent_recorded(tmp_path):
    db = _db(tmp_path)
    for status in (ATTACHMENT_BATCH_PENDING, ATTACHMENT_BATCH_INTENT_RECORDED):
        batch_id = _batch(db, f"b-{status}", status)
        assert (
            db.clear_attachment_terminal_batch(OWNER, batch_id, now=_iso(_now()))
            == "not_eligible"
        )
    db.close()


def test_clearance_is_owner_scoped(tmp_path):
    db = _db(tmp_path)
    batch_id = _batch(db, "b1", ATTACHMENT_BATCH_EXPIRED, owner=OWNER)
    assert db.clear_attachment_terminal_batch(OTHER, batch_id, now=_iso(_now())) == "not_found"
    assert db.is_attachment_terminal_cleared(OWNER, batch_id) is False
    assert _classify(db).state is AttachmentRoutingState.TERMINAL_UNPROVEN
    db.close()


def test_clearance_is_per_batch_not_owner_wide(tmp_path):
    db = _db(tmp_path)
    first = _batch(db, "b1", ATTACHMENT_BATCH_EXPIRED)
    second = _batch(db, "b2", ATTACHMENT_BATCH_REJECTED, cid=CID_B)
    assert db.clear_attachment_terminal_batch(OWNER, first, now=_iso(_now())) == "cleared"
    assert _classify(db).state is AttachmentRoutingState.TERMINAL_UNPROVEN
    assert db.clear_attachment_terminal_batch(OWNER, second, now=_iso(_now())) == "cleared"
    assert _classify(db).state is AttachmentRoutingState.NONE
    db.close()


def test_clearance_is_idempotent_and_does_not_duplicate_records(tmp_path):
    db = _db(tmp_path)
    batch_id = _batch(db, "b1", ATTACHMENT_BATCH_EXPIRED)
    assert db.clear_attachment_terminal_batch(OWNER, batch_id, now=_iso(_now())) == "cleared"
    assert db.clear_attachment_terminal_batch(OWNER, batch_id, now=_iso(_now())) == "already_cleared"
    rows = db._conn.execute(
        "SELECT COUNT(*) c FROM settings WHERE key=?",
        (f"{ATTACHMENT_TERMINAL_CLEARANCE_KEY_PREFIX}{batch_id}",),
    ).fetchone()["c"]
    assert rows == 1
    db.close()


def test_duplicate_update_does_not_repeat_clearance(tmp_path):
    db = _db(tmp_path)
    batch_id = _batch(db, "b1", ATTACHMENT_BATCH_EXPIRED)
    update_id = 7002
    db.mark_update_outcome(update_id, _iso(_now()), uo.DURABLE_COMPLETED)
    assert (
        db.clear_attachment_terminal_batch(
            OWNER, batch_id, now=_iso(_now()), update_id=update_id
        )
        == "duplicate"
    )
    assert db.is_attachment_terminal_cleared(OWNER, batch_id) is False
    db.close()


def test_database_failure_rolls_back_clearance(tmp_path, monkeypatch):
    db = _db(tmp_path)
    batch_id = _batch(db, "b1", ATTACHMENT_BATCH_EXPIRED)

    def boom(*args, **kwargs):
        raise sqlite3.OperationalError("simulated outcome failure")

    monkeypatch.setattr(db, "mark_update_outcome", boom)
    with pytest.raises(sqlite3.OperationalError):
        db.clear_attachment_terminal_batch(
            OWNER, batch_id, now=_iso(_now()), update_id=7003
        )
    assert db.is_attachment_terminal_cleared(OWNER, batch_id) is False
    assert _classify(db).state is AttachmentRoutingState.TERMINAL_UNPROVEN
    db.close()


def test_clearance_does_not_delete_batch_item_or_identity(tmp_path):
    db = _db(tmp_path)
    batch_id = _batch(db, "b1", ATTACHMENT_BATCH_REJECTED)
    db.add_attachment_item("i1", batch_id, staging_token="tok", display_name="a.txt",
                           size_bytes=1, status="stored", now=_iso(_now()))
    _identity(db, batch_id)
    keep = tmp_path / "keep.bin"
    keep.write_bytes(b"keep")
    before = (
        db.count_attachment_batches(),
        db.count_attachment_items(),
        db.count_message_identities(),
    )
    assert db.clear_attachment_terminal_batch(OWNER, batch_id, now=_iso(_now())) == "cleared"
    after = (
        db.count_attachment_batches(),
        db.count_attachment_items(),
        db.count_message_identities(),
    )
    assert after == before
    assert keep.read_bytes() == b"keep"
    assert db.get_attachment_batch(batch_id).status == ATTACHMENT_BATCH_REJECTED
    assert db.get_attachment_item("i1").status == "stored"
    db.close()


def test_clearance_persists_across_database_reopen(tmp_path):
    path = str(tmp_path / "persist.sqlite3")
    db = Database(path)
    batch_id = _batch(db, "b1", ATTACHMENT_BATCH_EXPIRED)
    assert db.clear_attachment_terminal_batch(OWNER, batch_id, now=_iso(_now())) == "cleared"
    db.close()

    reopened = Database(path)
    assert reopened.is_attachment_terminal_cleared(OWNER, batch_id) is True
    assert _classify(reopened).state is AttachmentRoutingState.NONE
    reopened.close()


def test_unknown_status_fails_closed_and_cannot_be_cleared(tmp_path):
    db = _db(tmp_path)
    batch_id = _batch(db, "b1", "future_status")
    assert db.clear_attachment_terminal_batch(OWNER, batch_id, now=_iso(_now())) == "not_eligible"
    with pytest.raises(AttachmentBatchIntegrityError):
        _classify(db)
    db.close()


def test_terminal_associated_still_blocks_after_clearance(tmp_path):
    db = _db(tmp_path)
    batch_id = _batch(db, "b1", ATTACHMENT_BATCH_EXPIRED)
    _identity(db, batch_id, message_id=88)
    assert db.clear_attachment_terminal_batch(OWNER, batch_id, now=_iso(_now())) == "cleared"
    assert _classify(db, message_id=88).state is AttachmentRoutingState.TERMINAL_ASSOCIATED
    assert _classify(db).state is AttachmentRoutingState.NONE
    db.close()


def test_delivered_or_failed_with_forged_clearance_key_still_blocks(tmp_path):
    db = _db(tmp_path)
    batch_id = _batch(db, "b1", ATTACHMENT_BATCH_DELIVERED)
    db.set_setting(f"{ATTACHMENT_TERMINAL_CLEARANCE_KEY_PREFIX}{batch_id}", str(OWNER))
    assert _classify(db).state is AttachmentRoutingState.TERMINAL_UNPROVEN
    db.close()


def test_unresolved_expired_pending_and_live_states_survive_clearance(tmp_path):
    db = _db(tmp_path)
    cleared = _batch(db, "cleared", ATTACHMENT_BATCH_EXPIRED)
    assert db.clear_attachment_terminal_batch(OWNER, cleared, now=_iso(_now())) == "cleared"

    _batch(db, "intent", ATTACHMENT_BATCH_INTENT_RECORDED)
    assert _classify(db).state is AttachmentRoutingState.UNRESOLVED
    db._conn.execute("UPDATE attachment_batches SET status='expired' WHERE batch_id='intent'")
    db._conn.commit()

    _batch(db, "old-pending", ATTACHMENT_BATCH_PENDING, t0=_expired_t0())
    assert _classify(db).state is AttachmentRoutingState.EXPIRED_PENDING
    db._conn.execute("UPDATE attachment_batches SET status='expired' WHERE batch_id='old-pending'")
    db._conn.commit()

    _batch(db, "live", ATTACHMENT_BATCH_PENDING, t0=_live_t0())
    assert _classify(db).state is AttachmentRoutingState.LIVE
    db.close()


# ============================================================================
# Handler command behavior
# ============================================================================
def test_clear_command_requires_explicit_confirm(tmp_path):
    db = _db(tmp_path)
    batch_id = _batch(db, "b1", ATTACHMENT_BATCH_EXPIRED)
    ctx = make_context(OWNER, tmp_path)
    ctx.bot_data["db"] = db
    update = make_update(OWNER, "/attachments_clear")
    update.update_id = 7101
    ctx.args = [batch_id]
    asyncio.run(h.attachments_clear(update, ctx))
    assert "confirm" in update.message.replies[0]
    assert db.is_attachment_terminal_cleared(OWNER, batch_id) is False
    db.close()


def test_clear_command_success_only_after_durable_commit(tmp_path):
    db = _db(tmp_path)
    batch_id = _batch(db, "b1", ATTACHMENT_BATCH_REJECTED)
    ctx = make_context(OWNER, tmp_path)
    ctx.bot_data["db"] = db
    update = make_update(OWNER, "/attachments_clear")
    update.update_id = 7102
    ctx.args = [batch_id, "confirm"]
    asyncio.run(h.attachments_clear(update, ctx))
    assert db.is_attachment_terminal_cleared(OWNER, batch_id) is True
    assert db.update_outcome(7102) == uo.DURABLE_COMPLETED
    assert update.message.replies == [
        "تم إخلاء الدفعة دي صراحةً. لو فيه دفعات نهائية تانية غير مُخلّاة، هتفضل محجوبة."
    ]
    db.close()


@pytest.mark.parametrize("status", [ATTACHMENT_BATCH_DELIVERED, ATTACHMENT_BATCH_FAILED])
def test_clear_command_rejects_non_clearable_status(tmp_path, status):
    db = _db(tmp_path)
    batch_id = _batch(db, "b1", status)
    ctx = make_context(OWNER, tmp_path)
    ctx.bot_data["db"] = db
    update = make_update(OWNER, "/attachments_clear")
    update.update_id = 7103
    ctx.args = [batch_id, "confirm"]
    asyncio.run(h.attachments_clear(update, ctx))
    assert db.is_attachment_terminal_cleared(OWNER, batch_id) is False
    assert "expired" in update.message.replies[0] and "rejected" in update.message.replies[0]
    db.close()


def test_clear_command_duplicate_update_does_not_overwrite_outcome(tmp_path):
    db = _db(tmp_path)
    batch_id = _batch(db, "b1", ATTACHMENT_BATCH_EXPIRED)
    update_id = 7106
    db.mark_update_outcome(update_id, _iso(_now()), uo.DURABLE_COMPLETED)
    ctx = make_context(OWNER, tmp_path)
    ctx.bot_data["db"] = db
    update = make_update(OWNER, "/attachments_clear")
    update.update_id = update_id
    ctx.args = [batch_id, "confirm"]
    asyncio.run(h.attachments_clear(update, ctx))
    assert db.is_attachment_terminal_cleared(OWNER, batch_id) is False
    assert db.update_outcome(update_id) == uo.DURABLE_COMPLETED
    assert "اتعالج قبل كده" in update.message.replies[0]
    db.close()


def test_clear_command_database_failure_emits_no_success(tmp_path, monkeypatch):
    db = _db(tmp_path)
    batch_id = _batch(db, "b1", ATTACHMENT_BATCH_EXPIRED)

    def boom(*args, **kwargs):
        raise sqlite3.OperationalError("simulated failure")

    monkeypatch.setattr(db, "clear_attachment_terminal_batch", boom)
    ctx = make_context(OWNER, tmp_path)
    ctx.bot_data["db"] = db
    update = make_update(OWNER, "/attachments_clear")
    update.update_id = 7104
    ctx.args = [batch_id, "confirm"]
    with pytest.raises(sqlite3.OperationalError):
        asyncio.run(h.attachments_clear(update, ctx))
    assert update.message.replies == []
    db.close()


def test_attachments_list_is_owner_scoped(tmp_path):
    db = _db(tmp_path)
    _batch(db, "mine", ATTACHMENT_BATCH_EXPIRED, owner=OWNER)
    _batch(db, "theirs", ATTACHMENT_BATCH_EXPIRED, owner=OTHER)
    ctx = make_context(OWNER, tmp_path)
    ctx.bot_data["db"] = db
    update = make_update(OWNER, "/attachments")
    update.update_id = 7105
    asyncio.run(h.attachments_list(update, ctx))
    assert "mine" in update.message.replies[0]
    assert "theirs" not in update.message.replies[0]
    assert db.update_outcome(7105) == uo.EXPLICITLY_IGNORED
    db.close()


# ============================================================================
# DEF-011-C / NEW-DEF-06 messaging
# ============================================================================
def test_unsupported_message_does_not_offer_documents_when_intake_disabled(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    update = make_update(OWNER, "photo")
    update.update_id = 7201
    asyncio.run(h.handle_unsupported_attachment(update, ctx))
    assert update.message.replies == [h.UNSUPPORTED_ATTACHMENT_TEXT]
    assert "مستند" not in update.message.replies[0]


def test_unsupported_message_offers_documents_only_when_intake_enabled(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    ctx.bot_data["config"].attachment_document_intake_enabled = True
    update = make_update(OWNER, "photo")
    update.update_id = 7202
    asyncio.run(h.handle_unsupported_attachment(update, ctx))
    assert update.message.replies == [h.UNSUPPORTED_ATTACHMENT_DOCUMENT_ENABLED_TEXT]
    assert "مستند" in update.message.replies[0]


def test_accepted_and_duplicate_messages_are_distinct_and_truthful():
    assert h.ATTACHMENT_ACCEPTED_TEXT != h.ATTACHMENT_DUPLICATE_TEXT
    assert "حفظه محليًا" in h.ATTACHMENT_ACCEPTED_TEXT
    assert "مش مرفوع" in h.ATTACHMENT_ACCEPTED_TEXT
    assert "مفيش نسخة جديدة" in h.ATTACHMENT_DUPLICATE_TEXT
    assert "Mini App" not in h.ATTACHMENT_ACCEPTED_TEXT
