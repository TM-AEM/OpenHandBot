"""OHB2-A4-F5: exact-deadline contract for classification, acceptance, and finalization.

The approved contract is:

- live: ``now < T0 + 15m``
- expired: ``now >= T0 + 15m``

All times are injected or supplied by a controlled clock. No sleeps and no live
Telegram/OpenHands calls are used.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from bot.attachments import (
    AcceptOutcome,
    AttachmentReaper,
    AttachmentService,
    BatchDecision,
    StageStatus,
    StagingStore,
    batch_is_expired,
    classify_incoming_file,
    staging_root_for,
)
from bot.db import (
    ATTACHMENT_BATCH_EXPIRED,
    ATTACHMENT_BATCH_PENDING,
    ATTACHMENT_ITEM_STORED,
    AttachmentBatchStateChanged,
    Database,
)
from bot.files import IdentityCache

OWNER_ID = 1
OWNER_UUID = "11111111-2222-3333-4444-555555555555"
CID = "11111111222233334444555566667777"
T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
DEADLINE = T0 + timedelta(minutes=15)
JUST_BEFORE = DEADLINE - timedelta(microseconds=1)
JUST_AFTER = DEADLINE + timedelta(microseconds=1)


class FakeClient:
    async def get_current_user(self):
        return {"id": OWNER_UUID}

    async def get_conversations(self, ids):
        return [
            {"id": CID, "created_by_user_id": OWNER_UUID, "title": "A"}
            for _ in ids
        ]


class StepClock:
    """Deterministic clock returning supplied values in order, then repeating the last."""

    def __init__(self, *values: datetime):
        self._values = list(values)

    def __call__(self) -> datetime:
        if len(self._values) > 1:
            return self._values.pop(0)
        return self._values[0]


def make_env(tmp_path, *, clock=None):
    db_path = str(tmp_path / "state.sqlite3")
    db = Database(db_path)
    store = StagingStore(db, db_path, clock=clock)
    client = FakeClient()
    service = AttachmentService(db, store, client, IdentityCache(client))
    return db, store, service, db_path


def make_batch(db, batch_id="b1", *, t0=T0):
    db.create_attachment_batch(batch_id, OWNER_ID, CID, t0.isoformat())
    return db.get_attachment_batch(batch_id)


def make_item(db, item_id="i1", batch_id="b1", *, status=ATTACHMENT_BATCH_PENDING):
    db.add_attachment_item(
        item_id,
        batch_id,
        staging_token="a" * 32,
        display_name="a.txt",
        size_bytes=3,
        status=status,
    )
    return db.get_attachment_item(item_id)


async def accept(service, *, now=T0, name="a.txt", chunks=(b"data",), update_id=None):
    async def factory():
        return iter(chunks)

    return await service.accept(
        telegram_id=OWNER_ID,
        conversation_id=CID,
        display_name=name,
        declared_size=None,
        update_id=update_id,
        now=now,
        chunks_factory=factory,
    )


def staged_names(db_path):
    root = staging_root_for(db_path)
    if not root.exists():
        return []
    return sorted(p.name for p in root.iterdir())


# ---------------------------------------------------------------- boundary


def test_batch_is_expired_and_classification_agree_at_boundary(tmp_path):
    db, _store, _service, _db_path = make_env(tmp_path)
    batch = make_batch(db)

    assert batch_is_expired(batch.t0, JUST_BEFORE) is False
    assert batch_is_expired(batch.t0, DEADLINE) is True
    assert batch_is_expired(batch.t0, JUST_AFTER) is True

    assert classify_incoming_file(
        db, telegram_id=OWNER_ID, conversation_id=CID, now=JUST_BEFORE
    ).decision is BatchDecision.APPEND
    assert classify_incoming_file(
        db, telegram_id=OWNER_ID, conversation_id=CID, now=DEADLINE
    ).decision is BatchDecision.EXPIRED
    assert classify_incoming_file(
        db, telegram_id=OWNER_ID, conversation_id=CID, now=JUST_AFTER
    ).decision is BatchDecision.EXPIRED


def test_service_at_exact_deadline_starts_new_batch(tmp_path):
    db, _store, service, _db_path = make_env(tmp_path, clock=lambda: T0)
    first = asyncio.run(accept(service, now=T0))
    assert first.outcome is AcceptOutcome.STORED

    second = asyncio.run(accept(service, now=DEADLINE, name="b.txt"))
    assert second.outcome is AcceptOutcome.STORED
    assert second.batch_id != first.batch_id
    assert db.get_attachment_batch(first.batch_id).status == ATTACHMENT_BATCH_EXPIRED
    assert len(db.list_attachment_items(first.batch_id)) == 1
    assert len(db.list_attachment_items(second.batch_id)) == 1


def test_a2_a4_live_and_expired_queries_agree_at_exact_deadline(tmp_path):
    db, _store, _service, _db_path = make_env(tmp_path)
    batch = make_batch(db)

    assert batch_is_expired(batch.t0, DEADLINE) is True
    assert db.list_live_pending_attachment_batches(OWNER_ID, now_iso=DEADLINE.isoformat()) == []
    expired = db.list_expired_pending_attachment_batches(now_iso=DEADLINE.isoformat())
    assert [b.batch_id for b in expired] == [batch.batch_id]
    assert db.has_expired_pending_attachment_batch(OWNER_ID, now_iso=DEADLINE.isoformat()) is True


# ---------------------------------------------------- atomic DB acceptance


def test_accept_attachment_item_rejects_exact_and_after_deadline(tmp_path):
    db, _store, _service, _db_path = make_env(tmp_path)
    batch = make_batch(db)

    accepted = db.accept_attachment_item(
        batch, item_id="i1", display_name="a.txt", now=JUST_BEFORE.isoformat()
    )
    assert accepted == "b1"
    assert db.get_attachment_item("i1").status == ATTACHMENT_BATCH_PENDING

    for item_id, now in (("i2", DEADLINE), ("i3", JUST_AFTER)):
        with pytest.raises(AttachmentBatchStateChanged):
            db.accept_attachment_item(
                batch, item_id=item_id, display_name="a.txt", now=now.isoformat()
            )

    assert len(db.list_attachment_items("b1")) == 1


def test_classified_live_then_accept_at_exact_deadline_rejects(tmp_path):
    db, _store, _service, _db_path = make_env(tmp_path)
    batch = make_batch(db)

    assert classify_incoming_file(
        db, telegram_id=OWNER_ID, conversation_id=CID, now=JUST_BEFORE
    ).decision is BatchDecision.APPEND

    with pytest.raises(AttachmentBatchStateChanged):
        db.accept_attachment_item(
            batch, item_id="i1", display_name="a.txt", now=DEADLINE.isoformat()
        )
    assert db.list_attachment_items("b1") == []


def test_accept_after_reaper_between_classification_and_acceptance_rejects(tmp_path):
    db, _store, _service, db_path = make_env(tmp_path)
    batch = make_batch(db)

    decision = classify_incoming_file(
        db, telegram_id=OWNER_ID, conversation_id=CID, now=JUST_BEFORE
    )
    assert decision.decision is BatchDecision.APPEND

    AttachmentReaper(db, db_path).sweep(now=DEADLINE)
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_EXPIRED

    with pytest.raises(AttachmentBatchStateChanged):
        db.accept_attachment_item(
            batch, item_id="i1", display_name="a.txt", now=DEADLINE.isoformat()
        )
    assert db.list_attachment_items("b1") == []


def test_duplicate_update_behavior_is_unchanged(tmp_path):
    db, _store, service, _db_path = make_env(tmp_path, clock=lambda: T0)
    first = asyncio.run(accept(service, now=T0, update_id=9001))
    duplicate = asyncio.run(accept(service, now=T0 + timedelta(seconds=1), update_id=9001))

    assert first.outcome is AcceptOutcome.STORED
    assert duplicate.outcome is AcceptOutcome.DUPLICATE
    assert len(db.list_attachment_items(first.batch_id)) == 1


# ------------------------------------------- slow storage and finalization


def test_finalization_at_exact_deadline_is_not_stored(tmp_path):
    db, _store, service, db_path = make_env(
        tmp_path, clock=StepClock(JUST_BEFORE, DEADLINE)
    )
    result = asyncio.run(accept(service, now=T0))

    assert result.outcome is AcceptOutcome.ACCEPTED
    assert result.stage is StageStatus.DB_FAILED
    assert db.get_attachment_item(result.item_id).status == ATTACHMENT_BATCH_PENDING
    assert staged_names(db_path) == []


def test_finalization_after_deadline_is_not_stored(tmp_path):
    db, _store, service, db_path = make_env(
        tmp_path, clock=StepClock(JUST_BEFORE, JUST_AFTER)
    )
    result = asyncio.run(accept(service, now=T0))

    assert result.outcome is AcceptOutcome.ACCEPTED
    assert result.stage is StageStatus.DB_FAILED
    assert db.get_attachment_item(result.item_id).status == ATTACHMENT_BATCH_PENDING
    assert staged_names(db_path) == []


def test_storage_prepare_at_exact_deadline_is_rejected_before_write(tmp_path):
    db, _store, service, db_path = make_env(tmp_path, clock=StepClock(DEADLINE))
    result = asyncio.run(accept(service, now=T0))

    assert result.outcome is AcceptOutcome.ACCEPTED
    assert result.stage is StageStatus.REJECTED_BATCH
    assert db.get_attachment_item(result.item_id).status == ATTACHMENT_BATCH_PENDING
    assert staged_names(db_path) == []


def test_storage_before_deadline_still_succeeds(tmp_path):
    db, _store, service, db_path = make_env(
        tmp_path, clock=StepClock(JUST_BEFORE, JUST_BEFORE)
    )
    result = asyncio.run(accept(service, now=T0))

    assert result.outcome is AcceptOutcome.STORED
    assert db.get_attachment_item(result.item_id).status == ATTACHMENT_ITEM_STORED
    assert len(staged_names(db_path)) == 1


def test_default_clock_reads_utc_at_invocation_not_construction(tmp_path, monkeypatch):
    first = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    second = first + timedelta(seconds=1)
    calls = []

    class StepDateTime:
        @classmethod
        def now(cls, tz=None):
            calls.append(tz)
            return first if len(calls) == 1 else second

    monkeypatch.setattr("bot.attachments.datetime", StepDateTime)
    db, store, _service, _db_path = make_env(tmp_path)

    assert store._deadline_now() == first
    assert store._deadline_now() == second
    assert calls == [timezone.utc, timezone.utc]


def test_default_clock_rejects_expired_direct_store_without_clock(tmp_path):
    db_path = str(tmp_path / "state.sqlite3")
    db = Database(db_path)
    expired_t0 = datetime.now(timezone.utc) - timedelta(hours=1)
    db.create_attachment_batch("b1", OWNER_ID, CID, expired_t0.isoformat())
    store = StagingStore(db, db_path)

    result = store.store(
        telegram_id=OWNER_ID, batch_id="b1", item_id="i1",
        display_name="a.txt", chunks=[b"data"],
    )

    assert result.status is StageStatus.REJECTED_BATCH
    assert db.get_attachment_item("i1") is None
    assert staged_names(db_path) == []


def test_default_clock_allows_live_direct_store_without_clock(tmp_path):
    db_path = str(tmp_path / "state.sqlite3")
    db = Database(db_path)
    live_t0 = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.create_attachment_batch("b1", OWNER_ID, CID, live_t0.isoformat())
    store = StagingStore(db, db_path)

    result = store.store(
        telegram_id=OWNER_ID, batch_id="b1", item_id="i1",
        display_name="a.txt", chunks=[b"data"],
    )

    assert result.status is StageStatus.STORED
    assert db.get_attachment_item("i1").status == ATTACHMENT_ITEM_STORED
    assert len(staged_names(db_path)) == 1


def test_explicit_clock_is_still_honored(tmp_path):
    fixed = JUST_BEFORE
    db, store, _service, _db_path = make_env(tmp_path, clock=lambda: fixed)
    make_batch(db)

    result = store.store(
        telegram_id=OWNER_ID, batch_id="b1", item_id="i1",
        display_name="a.txt", chunks=[b"data"],
    )

    assert store._deadline_now() == fixed
    assert result.status is StageStatus.STORED


def test_try_mark_none_uses_real_utc_and_rejects_expired(tmp_path):
    db, _store, _service, _db_path = make_env(tmp_path)
    expired_t0 = datetime.now(timezone.utc) - timedelta(hours=1)
    make_batch(db, t0=expired_t0)
    make_item(db)

    ok = db.try_mark_attachment_item_stored(
        "i1", size_bytes=3, staging_token="a" * 32, now=None
    )

    assert ok is False
    assert db.get_attachment_item("i1").status == ATTACHMENT_BATCH_PENDING


def test_try_mark_none_uses_real_utc_and_allows_live_batch(tmp_path):
    db, _store, _service, _db_path = make_env(tmp_path)
    live_t0 = datetime.now(timezone.utc) - timedelta(seconds=1)
    make_batch(db, t0=live_t0)
    make_item(db)

    ok = db.try_mark_attachment_item_stored(
        "i1", size_bytes=3, staging_token="a" * 32, now=None
    )

    assert ok is True
    assert db.get_attachment_item("i1").status == ATTACHMENT_ITEM_STORED


def test_try_mark_explicit_now_is_deterministic_and_deadline_checked(tmp_path):
    db, _store, _service, _db_path = make_env(tmp_path)
    make_batch(db)
    make_item(db)

    assert db.try_mark_attachment_item_stored(
        "i1", size_bytes=3, staging_token="a" * 32, now=JUST_BEFORE.isoformat()
    ) is True
    assert db.get_attachment_item("i1").status == ATTACHMENT_ITEM_STORED


def test_direct_finalization_cas_rejects_exact_deadline(tmp_path):
    db, _store, _service, _db_path = make_env(tmp_path)
    make_batch(db)
    make_item(db)

    ok = db.try_mark_attachment_item_stored(
        "i1", size_bytes=3, staging_token="a" * 32, now=DEADLINE.isoformat()
    )
    assert ok is False
    assert db.get_attachment_item("i1").status == ATTACHMENT_BATCH_PENDING


def test_reaper_expired_batch_during_prepare_cannot_be_overwritten(tmp_path, monkeypatch):
    db, store, _service, db_path = make_env(
        tmp_path, clock=StepClock(JUST_BEFORE, JUST_BEFORE)
    )
    make_batch(db)
    real_write = store._write_to_path

    def hooked(path, chunks, cap):
        written = real_write(path, chunks, cap)
        # The reaper's DB-first expiration decision, before it reaps the item/bytes.
        assert db.mark_attachment_batch_status(
            "b1", ATTACHMENT_BATCH_EXPIRED, now=DEADLINE.isoformat()
        ) is True
        return written

    monkeypatch.setattr(store, "_write_to_path", hooked)
    result = store.store(
        telegram_id=OWNER_ID, batch_id="b1", item_id="i1",
        display_name="a.txt", chunks=[b"data"],
    )

    assert result.status is StageStatus.DB_FAILED
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_EXPIRED
    assert db.get_attachment_item("i1").status == ATTACHMENT_BATCH_PENDING
    assert staged_names(db_path) == []


def test_full_reaper_during_prepare_does_not_store(tmp_path, monkeypatch):
    db, store, _service, db_path = make_env(
        tmp_path, clock=StepClock(JUST_BEFORE, JUST_BEFORE)
    )
    make_batch(db)
    real_write = store._write_to_path

    def hooked(path, chunks, cap):
        written = real_write(path, chunks, cap)
        AttachmentReaper(db, db_path).sweep(now=DEADLINE)
        return written

    monkeypatch.setattr(store, "_write_to_path", hooked)
    result = store.store(
        telegram_id=OWNER_ID, batch_id="b1", item_id="i1",
        display_name="a.txt", chunks=[b"data"],
    )

    assert result.status is not StageStatus.STORED
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_EXPIRED
    assert db.get_attachment_item("i1").status != ATTACHMENT_ITEM_STORED
    assert staged_names(db_path) == []


def test_cancellation_during_prepare_is_not_overwritten(tmp_path, monkeypatch):
    db, store, _service, db_path = make_env(tmp_path, clock=lambda: T0)
    make_batch(db)
    real_write = store._write_to_path

    def hooked(path, chunks, cap):
        written = real_write(path, chunks, cap)
        assert db.cancel_pending_attachment_batch(
            OWNER_ID, "b1", now=T0.isoformat()
        ) == "cancelled"
        return written

    monkeypatch.setattr(store, "_write_to_path", hooked)
    result = store.store(
        telegram_id=OWNER_ID, batch_id="b1", item_id="i1",
        display_name="a.txt", chunks=[b"data"],
    )

    assert result.status is StageStatus.DB_FAILED
    assert db.get_attachment_batch("b1").status != ATTACHMENT_BATCH_PENDING
    assert db.get_attachment_item("i1").status == ATTACHMENT_BATCH_PENDING
    assert staged_names(db_path) == []


def test_intent_during_prepare_is_not_overwritten(tmp_path, monkeypatch):
    db, store, _service, db_path = make_env(tmp_path, clock=lambda: T0)
    make_batch(db)
    real_write = store._write_to_path

    def hooked(path, chunks, cap):
        written = real_write(path, chunks, cap)
        assert db.record_attachment_intent(
            "b1",
            telegram_id=OWNER_ID,
            conversation_id=CID,
            intent_text="accompanying text",
            now=T0.isoformat(),
            update_id=None,
            chat_id=OWNER_ID,
            message_id=123,
        ) == "b1"
        return written

    monkeypatch.setattr(store, "_write_to_path", hooked)
    result = store.store(
        telegram_id=OWNER_ID, batch_id="b1", item_id="i1",
        display_name="a.txt", chunks=[b"data"],
    )

    assert result.status is StageStatus.DB_FAILED
    assert db.get_attachment_batch("b1").status != ATTACHMENT_BATCH_PENDING
    assert db.get_attachment_item("i1").status == ATTACHMENT_BATCH_PENDING
    assert staged_names(db_path) == []


def test_intent_at_exact_deadline_is_rejected(tmp_path):
    db, _store, _service, _db_path = make_env(tmp_path)
    make_batch(db)

    assert db.record_attachment_intent(
        "b1",
        telegram_id=OWNER_ID,
        conversation_id=CID,
        intent_text="text",
        now=DEADLINE.isoformat(),
        update_id=None,
        chat_id=OWNER_ID,
        message_id=124,
    ) is None
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_PENDING
