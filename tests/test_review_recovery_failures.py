"""R7 missing coverage: DB, report, outbox, and branch-movement failures."""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime

import pytest

from bot.db import (
    AUTO_REVIEW_LIFECYCLE_RETRY_WAIT,
    AUTO_REVIEW_STATUS_RESERVED,
)
from bot.review.collector import GitHubEvidenceCollector
from bot.review.github import BranchVerification
from bot.review.report import ReviewReportError, ReviewReportService
from bot.review.worker import ReviewRunner, ReviewWorker
from tests._review_r6_helpers import (
    SHA2,
    T0,
    T1,
    T2,
    make_db,
    member,
    seed_completed_cycle,
    snapshot,
)
from tests.test_auto_review_lifecycle import (
    FakeProvider,
    provider_binding,
)
from tests.test_review_branch_sha import FakeGitHub, unchanged


def test_database_lock_does_not_acknowledge_or_persist_a_reservation(tmp_path):
    db = make_db(tmp_path)
    snap = snapshot(db)
    locker = sqlite3.connect(str(tmp_path / "review.sqlite3"), timeout=0.1)
    try:
        locker.execute("BEGIN IMMEDIATE")
        db._conn.execute("PRAGMA busy_timeout=1")
        with pytest.raises(sqlite3.OperationalError):
            db.reserve_conversation_review(
                conversation_id="conv-1",
                chat_id=7,
                memberships=(member(1, SHA2),),
                provider_snapshot_id=snap.id,
                reserved_by="test",
                implementation_report="report",
                now=T0,
            )
    finally:
        locker.rollback()
        locker.close()
    assert db._conn.execute("SELECT COUNT(*) FROM auto_reviews").fetchone()[0] == 0


def test_lifecycle_write_failure_leaves_the_cycle_active(tmp_path):
    db = make_db(tmp_path)
    result = db.reserve_conversation_review(
        conversation_id="conv-1",
        chat_id=7,
        memberships=(member(1, SHA2),),
        provider_snapshot_id=snapshot(db).id,
        reserved_by="test",
        implementation_report="report",
        now=T0,
    )
    claim = db.claim_auto_review(owner="worker", now=T1)
    assert claim is not None
    db._conn.execute(
        "UPDATE auto_reviews SET stage='adversarial_validated' WHERE id=?",
        (result.review_id,),
    )
    db._conn.commit()
    db._conn.execute(
        "CREATE TRIGGER r7_fail_completion BEFORE UPDATE ON auto_reviews "
        "BEGIN SELECT RAISE(ABORT, 'forced write failure'); END"
    )
    db._conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        db.complete_auto_review(
            result.review_id,
            lease_token=claim.lease_token,
            lease_epoch=claim.lease_epoch,
            verdict="PASS",
            report_ref="review-bbbbbbb.md",
            delivery_text="summary",
            now=T2,
        )
    cycle = db.get_auto_review(result.review_id)
    assert cycle is not None
    assert cycle.status == AUTO_REVIEW_STATUS_RESERVED
    assert cycle.verdict is None
    assert db._conn.execute(
        "SELECT COUNT(*) FROM auto_review_leases WHERE review_id=?",
        (result.review_id,),
    ).fetchone()[0] == 1


def test_report_generation_failure_does_not_create_outbox_or_sent(tmp_path, monkeypatch):
    db = make_db(tmp_path)
    review_id = seed_completed_cycle(db, (member(1, SHA2),))
    service = ReviewReportService(db, owner_id=7)

    def fail(*args, **kwargs):
        raise ReviewReportError("forced report failure")

    monkeypatch.setattr(service, "build", fail)
    with pytest.raises(ReviewReportError):
        service.prepare(review_id, now=T2)
    assert db.get_auto_review_report(review_id, 1) is None
    assert db.get_auto_review_outbox(review_id) == ()
    assert db.get_auto_review(review_id).lifecycle_state == "delivery_pending"
    # A later service instance recovers the pending report without a false send.
    recovered = ReviewReportService(db, owner_id=7).prepare(review_id, now=T2)
    assert recovered is not None
    assert len(db.get_auto_review_outbox(review_id)) == 1


def test_report_save_failure_does_not_create_outbox_or_sent(tmp_path, monkeypatch):
    db = make_db(tmp_path)
    review_id = seed_completed_cycle(db, (member(1, SHA2),))
    service = ReviewReportService(db, owner_id=7)

    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("forced report save failure")

    monkeypatch.setattr(db, "save_auto_review_report", fail)
    with pytest.raises(sqlite3.OperationalError):
        service.prepare(review_id, now=T2)
    assert db.get_auto_review_report(review_id, 1) is None
    assert db.get_auto_review_outbox(review_id) == ()
    monkeypatch.undo()
    assert service.prepare(review_id, now=T2) is not None
    assert len(db.get_auto_review_outbox(review_id)) == 1


def test_outbox_insertion_failure_keeps_verdict_pending(tmp_path, monkeypatch):
    db = make_db(tmp_path)
    review_id = seed_completed_cycle(db, (member(1, SHA2),))
    service = ReviewReportService(db, owner_id=7)

    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("forced outbox failure")

    monkeypatch.setattr(db, "schedule_auto_review_report_delivery", fail)
    with pytest.raises(sqlite3.OperationalError):
        service.prepare(review_id, now=T2)
    report = db.get_auto_review_report(review_id, 1)
    assert report is not None
    assert db.get_auto_review_outbox(review_id) == ()
    assert db.get_auto_review(review_id).lifecycle_state == "delivery_pending"
    monkeypatch.undo()
    assert service.ensure_pending(now=T2) == 1
    assert len(db.get_auto_review_outbox(review_id)) == 1


def test_branch_moves_between_discovery_and_final_validation_no_pass(tmp_path):
    db = make_db(tmp_path)
    db.add_watched("conv-1", "test conversation", 7)
    result = db.reserve_conversation_review(
        conversation_id="conv-1",
        chat_id=7,
        memberships=(member(1, SHA2),),
        provider_snapshot_id=snapshot(db).id,
        reserved_by="test",
        implementation_report="report",
        now=T0,
    )
    moved = BranchVerification(
        repository="owner/repo",
        branch="agent/x",
        expected_sha=SHA2,
        observed_sha="c" * 40,
        status="moved",
    )
    client = FakeGitHub(verify_results=[unchanged(), moved])
    provider = FakeProvider()
    runner = ReviewRunner(
        db,
        provider,
        GitHubEvidenceCollector(client),
        max_input_chars=20_000,
        clock=lambda: datetime.fromisoformat(T2),
        provider_binding=provider_binding(db),
        owner_id=7,
    )
    worker = ReviewWorker(
        db,
        runner,
        owner="worker",
        clock=lambda: datetime.fromisoformat(T2),
    )
    claim = worker._claim()
    assert claim is not None
    asyncio.run(worker._process(claim))
    cycle = db.get_auto_review(result.review_id)
    assert cycle is not None
    assert cycle.verdict is None
    assert cycle.lifecycle_state == AUTO_REVIEW_LIFECYCLE_RETRY_WAIT
    assert provider.calls == []
    assert db.get_auto_review_outbox(result.review_id) == ()
