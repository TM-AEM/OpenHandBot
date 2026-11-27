"""OHB2-AUTO-REVIEW-R5: durable lifecycle, membership, leases, recovery, delivery."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from bot.db import (
    AUTO_REVIEW_LIFECYCLE_DELIVERY_PENDING,
    AUTO_REVIEW_LIFECYCLE_TERMINAL,
    AUTO_REVIEW_OBSERVATION_ALREADY,
    AUTO_REVIEW_OBSERVATION_CONFLICT,
    AUTO_REVIEW_OBSERVATION_DEFERRED,
    AUTO_REVIEW_RESERVATION_ALREADY,
    AUTO_REVIEW_RESERVATION_CONFLICT,
    AUTO_REVIEW_RESERVATION_INVALID,
    AUTO_REVIEW_RESERVATION_NEW,
    AUTO_REVIEW_SCOPE_CONVERSATION,
    AUTO_REVIEW_SCOPE_POLICY_CONVERSATION_WIDE,
    AUTO_REVIEW_STAGE_BLIND,
    AUTO_REVIEW_STATUS_RESERVED,
    AUTO_REVIEW_STATUS_TERMINAL,
    AutoReviewLeaseLost,
    AutoReviewMembership,
    Database,
)
from bot.review.collector import EvidenceCollectionError
from bot.review.evidence import ReviewEvidence
from bot.review.github import (
    WorkflowJob,
    WorkflowJobsEvidence,
    WorkflowRun,
    WorkflowRunsEvidence,
)
from bot.review.llm import ModelResponse, ProviderBinding
from bot.review.schema import parse_blind_review
from bot.review.worker import ReviewPipelineError, ReviewRunner, ReviewWorker

SHA1 = "a" * 40
SHA2 = "b" * 40
SHA3 = "c" * 40
SHA4 = "d" * 40
T0 = "2026-11-25T00:00:00+00:00"
T1 = "2026-11-25T00:00:01+00:00"
T2 = "2026-11-25T00:00:02+00:00"
T301 = "2026-11-25T00:05:01+00:00"
T303 = "2026-11-25T00:05:03+00:00"
REPORT = "implementation report"


def diff():
    return (
        "diff --git a/src/x.py b/src/x.py\n"
        "--- a/src/x.py\n"
        "+++ b/src/x.py\n"
        "@@ -1 +1 @@\n"
        "-old\n+new\n"
    )


def runs(head, ci_state="success"):
    return WorkflowRunsEvidence(
        repository="owner/repo",
        head_sha=head,
        runs=(
            WorkflowRun(
                run_id=1,
                name="verify",
                head_sha=head,
                head_branch="agent/x",
                status="completed",
                conclusion="success",
                event="push",
                run_attempt=1,
                created_at=None,
                updated_at=None,
            ),
        ),
        status="verified",
        observed_head_shas=(head,),
        ci_state=ci_state,
    )


def jobs(head, run_id=1):
    return WorkflowJobsEvidence(
        repository="owner/repo",
        run_id=run_id,
        head_sha=head,
        jobs=(
            WorkflowJob(
                job_id=10,
                run_id=run_id,
                name="test",
                head_sha=head,
                status="completed",
                conclusion="success",
                started_at=None,
                completed_at=None,
            ),
        ),
        status="verified",
        observed_head_shas=(head,),
    )


def evid(membership, ci_state="success"):
    return ReviewEvidence.from_raw_diff(
        repository=membership.repository_full_name,
        pr_number=membership.pr_number,
        branch=membership.branch,
        base_sha=membership.base_sha,
        head_sha=membership.head_sha,
        diff_text=diff(),
        max_input_chars=20_000,
        ci_runs=runs(membership.head_sha, ci_state=ci_state),
        ci_jobs=(jobs(membership.head_sha),),
        sha_status="verified",
        ci_jobs_complete=True,
    )


def member(pr, head, base=SHA1, name="owner/repo"):
    return AutoReviewMembership(1, name, pr, "agent/x", base, head)


def make_db(tmp_path):
    return Database(str(tmp_path / "review.sqlite3"))


def snapshot(db):
    return db.get_or_create_auto_review_provider_snapshot(
        provider="testprovider",
        api_base="https://reviewer.invalid/v1",
        model="model-a",
        config={"max_input_chars": 20000},
        now=T0,
    )


def provider_binding(db):
    snap = snapshot(db)
    config = SimpleNamespace(
        reviewer_provider=snap.provider,
        reviewer_api_base=snap.api_base,
        reviewer_model=snap.model,
        reviewer_api_key="test-review-key",
    )
    return ProviderBinding.from_config(config, snap)


def reserve(db, members, *, conv="conv-1", chat=7, key=None):
    db.add_watched(conv, "test conversation", chat)
    return db.reserve_conversation_review(
        conversation_id=conv,
        chat_id=chat,
        memberships=tuple(members),
        provider_snapshot_id=snapshot(db).id,
        reserved_by="test",
        implementation_report=REPORT,
        reservation_key=key,
        now=T0,
    )


def mark_adversarial_validated(db, review_id, claim):
    db._conn.execute(
        "UPDATE auto_reviews SET stage='adversarial_validated' WHERE id=?",
        (int(review_id),),
    )
    db._conn.commit()


class FakeProvider:
    def __init__(self, blind=None, adversarial=None):
        self.blind = blind
        self.adversarial = adversarial
        self.calls = []

    async def complete(self, request):
        self.calls.append(request.stage)
        if request.stage == "blind":
            if callable(self.blind):
                return ModelResponse(self.blind(), 200, "testprovider", "model-a")
            return ModelResponse(blind_json(), 200, "testprovider", "model-a")
        if callable(self.adversarial):
            return ModelResponse(self.adversarial(), 200, "testprovider", "model-a")
        bl = parse_blind_review(blind_json())
        return ModelResponse(adversarial_json(bl.fingerprint), 200, "testprovider", "model-a")


class FakeCollector:
    def __init__(self, error=None, ci_state="success"):
        self.error = error
        self.ci_state = ci_state
        self.calls = []

    async def collect(self, membership, *, architecture_decisions, max_input_chars):
        self.calls.append(membership.pr_number)
        if self.error is not None:
            raise EvidenceCollectionError(self.error)
        return evid(membership, ci_state=self.ci_state)


def blind_json():
    return json.dumps(
        {
            "schema_version": "r4.v1",
            "stage": "blind",
            "assessment": "clean",
            "summary": "clean",
            "findings": [],
            "reviewed_files": ["src/x.py"],
            "evidence_gaps": [],
        }
    )


def adversarial_json(sha):
    return json.dumps(
        {
            "schema_version": "r4.v1",
            "stage": "adversarial",
            "blind_review_sha256": sha,
            "assessment": "concur",
            "summary": "concur",
            "findings": [],
            "challenges": [],
            "reviewed_files": ["src/x.py"],
            "evidence_gaps": [],
        }
    )


def runner(db, provider=None, collector=None):
    return ReviewRunner(
        db,
        provider or FakeProvider(),
        collector or FakeCollector(),
        max_input_chars=20_000,
        clock=lambda: datetime.fromisoformat(T2),
        provider_binding=provider_binding(db),
        owner_id=7,
    )


def test_schema_scope_and_memberships_are_persisted(tmp_path):
    db = make_db(tmp_path)
    members = (member(1, SHA2), member(2, SHA4, base=SHA3))
    result = reserve(db, members)
    assert result.outcome == AUTO_REVIEW_RESERVATION_NEW
    cycle = db.get_auto_review(result.review_id)
    assert cycle.scope == AUTO_REVIEW_SCOPE_CONVERSATION
    assert cycle.scope_policy == AUTO_REVIEW_SCOPE_POLICY_CONVERSATION_WIDE
    assert cycle.chat_id == 7
    assert cycle.membership_count == 2
    assert db.get_auto_review_memberships(result.review_id) == tuple(
        sorted(members, key=lambda item: (item.repository_id, item.pr_number))
    )
    assert db._conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_invalid_and_duplicate_reservations_do_not_mutate(tmp_path):
    db = make_db(tmp_path)
    assert reserve(db, []).outcome == AUTO_REVIEW_RESERVATION_INVALID
    assert reserve(db, (member(1, "not-a-sha"),)).outcome == AUTO_REVIEW_RESERVATION_INVALID
    assert reserve(
        db,
        (AutoReviewMembership(1, "owner/repo", 1, "", SHA1, SHA2),),
    ).outcome == AUTO_REVIEW_RESERVATION_INVALID
    assert db._conn.execute("SELECT count(*) FROM auto_reviews").fetchone()[0] == 0

    first = reserve(db, (member(1, SHA2),))
    duplicate = reserve(db, (member(1, SHA2),))
    conflict = reserve(db, (member(1, SHA3),))
    assert first.outcome == AUTO_REVIEW_RESERVATION_NEW
    assert duplicate.outcome == AUTO_REVIEW_RESERVATION_ALREADY
    assert duplicate.existing_id == first.review_id
    assert conflict.outcome == AUTO_REVIEW_RESERVATION_CONFLICT
    assert db._conn.execute("SELECT count(*) FROM auto_reviews").fetchone()[0] == 1


def test_conversation_wide_scope_blocks_mixed_prs_until_terminal(tmp_path):
    db = make_db(tmp_path)
    first = reserve(db, (member(1, SHA2),))
    second = reserve(db, (member(2, SHA4, base=SHA3),))
    assert first.outcome == AUTO_REVIEW_RESERVATION_NEW
    assert second.outcome == AUTO_REVIEW_RESERVATION_CONFLICT
    assert len(db.get_auto_review_memberships(first.review_id)) == 1

    db._conn.execute(
        "UPDATE auto_reviews SET status=?, lifecycle_state=?, terminal_reason=? WHERE id=?",
        (AUTO_REVIEW_STATUS_TERMINAL, AUTO_REVIEW_LIFECYCLE_TERMINAL, "test", first.review_id),
    )
    db._conn.commit()
    later = reserve(db, (member(2, SHA4, base=SHA3),))
    assert later.outcome == AUTO_REVIEW_RESERVATION_NEW
    assert len(db.get_auto_review_memberships(later.review_id)) == 1


def test_new_pr_is_persisted_as_pending_not_mutating_active(tmp_path):
    db = make_db(tmp_path)
    first = reserve(db, (member(1, SHA2),))
    observed = db.observe_auto_review_membership(
        conversation_id="conv-1", membership=member(2, SHA4, base=SHA3), now=T1
    )
    assert observed.outcome == AUTO_REVIEW_OBSERVATION_DEFERRED
    assert observed.review_id == first.review_id
    assert len(db.get_auto_review_memberships(first.review_id)) == 1
    assert db.list_pending_auto_review_memberships("conv-1") == (
        member(2, SHA4, base=SHA3),
    )
    assert db.observe_auto_review_membership(
        conversation_id="conv-1", membership=member(1, SHA2), now=T1
    ).outcome == AUTO_REVIEW_OBSERVATION_ALREADY
    assert db.observe_auto_review_membership(
        conversation_id="conv-1", membership=member(1, SHA3), now=T1
    ).outcome == AUTO_REVIEW_OBSERVATION_CONFLICT


def test_lease_takeover_fences_stale_worker(tmp_path):
    db = make_db(tmp_path)
    review_id = reserve(db, (member(1, SHA2),)).review_id
    old = db.claim_auto_review(owner="worker-old", now=T1, lease_seconds=300)
    assert old is not None
    db.begin_auto_review_stage(
        review_id, AUTO_REVIEW_STAGE_BLIND, old.lease_token, old.lease_epoch, now=T2
    )
    db.save_auto_review_stage(
        review_id,
        1,
        1,
        "blind",
        "validated",
        lease_token=old.lease_token,
        lease_epoch=old.lease_epoch,
        evidence_sha256="e" * 64,
        output_json=blind_json(),
        validation_json="{}",
        now=T2,
    )
    new = db.claim_auto_review(owner="worker-new", now=T301, lease_seconds=300)
    assert new is not None
    assert new.lease_epoch == old.lease_epoch + 1
    assert db.renew_auto_review_lease(old.review_id, old.lease_token, now=T301) is False
    with pytest.raises(AutoReviewLeaseLost):
        db.complete_auto_review(
            review_id,
            lease_token=old.lease_token,
            lease_epoch=old.lease_epoch,
            verdict="PASS",
            report_ref="review:1",
            delivery_text="result",
            now=T301,
        )
    assert db.get_auto_review(review_id).lifecycle_state == "active"


def test_review_worker_runs_conversation_wide_and_delivers_once(tmp_path):
    db = make_db(tmp_path)
    result = reserve(db, (member(1, SHA2), member(2, SHA4, base=SHA3)))
    provider = FakeProvider()
    collector = FakeCollector()
    worker = ReviewWorker(
        db, runner(db, provider, collector), owner="worker-1",
        clock=lambda: datetime.fromisoformat(T2),
    )
    claim = worker._claim()
    assert claim is not None
    asyncio.run(worker._process(claim))
    cycle = db.get_auto_review(result.review_id)
    assert cycle.lifecycle_state == AUTO_REVIEW_LIFECYCLE_DELIVERY_PENDING
    assert cycle.verdict == "PASS"
    assert provider.calls == ["blind", "adversarial", "blind", "adversarial"]
    assert collector.calls == [1, 2]
    outbox = db.get_auto_review_outbox(result.review_id)
    assert len(outbox) == 1
    assert db.schedule_auto_review_delivery(result.review_id, now=T2) == outbox[0].id
    assert len(db.get_auto_review_outbox(result.review_id)) == 1
    db.set_outbox_status(outbox[0].id, "sent", T2)
    cycle = db.get_auto_review(result.review_id)
    assert cycle.status == AUTO_REVIEW_STATUS_TERMINAL
    assert cycle.delivery_state == "sent"
    assert cycle.terminal_reason == "delivered"


def test_terminal_outbox_unknown_and_failed_are_not_reported_as_sent(tmp_path):
    db = make_db(tmp_path)
    for status, expected in (("unknown", "unknown"), ("failed", "failed")):
        result = reserve(db, (member(1, SHA2),), conv=f"conv-{status}")
        claim = db.claim_auto_review(owner="w", now=T1)
        mark_adversarial_validated(db, result.review_id, claim)
        db.complete_auto_review(
            result.review_id,
            lease_token=claim.lease_token,
            lease_epoch=claim.lease_epoch,
            verdict="PASS",
            report_ref="review",
            delivery_text="result",
            now=T2,
        )
        outbox_id = db.schedule_auto_review_delivery(result.review_id, now=T2)
        db.set_outbox_status(outbox_id, status, T2)
        cycle = db.get_auto_review(result.review_id)
        assert cycle.delivery_state == expected
        assert cycle.status == AUTO_REVIEW_STATUS_TERMINAL
        assert cycle.terminal_reason != "delivered"


def test_retryable_failure_is_bounded_and_permanent_fails_once(tmp_path):
    db = make_db(tmp_path)
    result = reserve(db, (member(1, SHA2),))
    collector = FakeCollector(error="provider_timeout")
    worker = ReviewWorker(
        db, runner(db, FakeProvider(), collector), owner="worker-1",
        clock=lambda: datetime.fromisoformat(T2),
    )
    claim = worker._claim()
    asyncio.run(worker._process(claim))
    cycle = db.get_auto_review(result.review_id)
    assert cycle.lifecycle_state == "retry_wait"
    assert cycle.attempts == 1

    second_dir = tmp_path / "second"
    second_dir.mkdir()
    db2 = make_db(second_dir)
    result2 = reserve(db2, (member(1, SHA2),))
    collector2 = FakeCollector(error="compare_head_sha_mismatch")
    worker2 = ReviewWorker(
        db2, runner(db2, FakeProvider(), collector2), owner="worker-2",
        clock=lambda: datetime.fromisoformat(T2),
    )
    claim2 = worker2._claim()
    asyncio.run(worker2._process(claim2))
    cycle2 = db2.get_auto_review(result2.review_id)
    assert cycle2.lifecycle_state == AUTO_REVIEW_LIFECYCLE_DELIVERY_PENDING
    assert cycle2.verdict == "BLOCKED"
    assert db2.claim_auto_review(owner="other", now=T301) is None
    assert len(db2.get_auto_review_outbox(result2.review_id)) == 1


def test_verdict_is_durable_before_outbox_and_recovered(tmp_path):
    db = make_db(tmp_path)
    result = reserve(db, (member(1, SHA2),))
    claim = db.claim_auto_review(owner="w", now=T1)
    mark_adversarial_validated(db, result.review_id, claim)
    db.complete_auto_review(
        result.review_id,
        lease_token=claim.lease_token,
        lease_epoch=claim.lease_epoch,
        verdict="PASS",
        report_ref="review",
        delivery_text="result",
        now=T2,
    )
    db._conn.close()
    reopened = Database(str(tmp_path / "review.sqlite3"))
    assert reopened.get_auto_review(result.review_id).verdict == "PASS"
    assert reopened.ensure_pending_auto_review_deliveries(now=T2) == 1
    assert len(reopened.get_auto_review_outbox(result.review_id)) == 1


def test_membership_and_evidence_snapshots_are_immutable(tmp_path):
    db = make_db(tmp_path)
    result = reserve(db, (member(1, SHA2),))
    with pytest.raises(sqlite3.IntegrityError):
        db._conn.execute(
            "UPDATE auto_review_memberships SET head_sha=? WHERE review_id=?",
            (SHA3, result.review_id),
        )
    db._conn.rollback()
    claim = db.claim_auto_review(owner="w", now=T1)
    db.save_auto_review_evidence(
        result.review_id,
        member(1, SHA2),
        lease_token=claim.lease_token,
        lease_epoch=claim.lease_epoch,
        evidence_sha256="e" * 64,
        diff_sha256="f" * 64,
        coverage_complete=True,
        ci_state="success",
        evidence_json="{}",
        now=T2,
    )
    with pytest.raises(sqlite3.IntegrityError):
        db._conn.execute(
            "UPDATE auto_review_evidence SET ci_state='failure' WHERE review_id=?",
            (result.review_id,),
        )
    db._conn.rollback()


def test_migration_preserves_existing_auto_review_row(tmp_path):
    path = tmp_path / "old.sqlite3"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE auto_review_provider_snapshots (
            id INTEGER PRIMARY KEY, provider TEXT NOT NULL, api_base TEXT NOT NULL,
            model TEXT NOT NULL, config_json TEXT NOT NULL,
            config_fingerprint TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE auto_reviews (
            id INTEGER PRIMARY KEY, reservation_key TEXT NOT NULL UNIQUE,
            conversation_id TEXT NOT NULL, repository_id INTEGER NOT NULL,
            repository_full_name TEXT NOT NULL, pr_number INTEGER,
            branch TEXT NOT NULL, base_sha TEXT, head_sha TEXT NOT NULL,
            scope TEXT NOT NULL, status TEXT NOT NULL, stage TEXT NOT NULL,
            terminal_reason TEXT, ci_run_id TEXT, ci_conclusion TEXT,
            verdict TEXT, report_ref TEXT, provider_snapshot_id INTEGER NOT NULL,
            rounds INTEGER NOT NULL, reserved_by TEXT NOT NULL,
            reserved_at TEXT NOT NULL, created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL, error_class TEXT, error_detail TEXT
        );
        INSERT INTO auto_review_provider_snapshots
        (id, provider, api_base, model, config_json, config_fingerprint, created_at)
        VALUES(1,'p','https://x.invalid','m','{}','f'*64,'2026-11-25');
        INSERT INTO auto_reviews
        (id,reservation_key,conversation_id,repository_id,repository_full_name,pr_number,
         branch,base_sha,head_sha,scope,status,stage,provider_snapshot_id,rounds,
         reserved_by,reserved_at,created_at,updated_at)
        VALUES(1,'old','conv',1,'owner/repo',1,'agent/x','a'*40,'b'*40,
               'conversation','reserved','reserved',1,0,'old','2026-11-25',
               '2026-11-25','2026-11-25');
        """
    )
    conn.commit()
    conn.close()
    db = Database(str(path))
    cols = {row[1] for row in db._conn.execute("PRAGMA table_info(auto_reviews)")}
    assert {"chat_id", "lifecycle_state", "worker_state", "delivery_state"} <= cols
    cycle = db.get_auto_review(1)
    assert cycle is not None
    assert cycle.conversation_id == "conv"
    assert cycle.lifecycle_state == "queued"
    assert db._conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_resume_after_blind_reuses_validated_stage(tmp_path):
    db = make_db(tmp_path)
    result = reserve(db, (member(1, SHA2),))
    first_claim = db.claim_auto_review(owner="old", now=T1)
    old_runner = runner(db, FakeProvider(), FakeCollector())
    cycle = db.get_auto_review(result.review_id)
    membership = db.get_auto_review_memberships(result.review_id)[0]
    evidence = evid(membership)
    asyncio.run(old_runner._blind(first_claim, cycle, membership, evidence))
    assert db.get_auto_review_stage(result.review_id, 1, 1, "blind").status == "validated"

    new_claim = db.claim_auto_review(owner="new", now=T303)
    assert new_claim is not None
    new_provider = FakeProvider()
    new_runner = ReviewRunner(
        db,
        new_provider,
        FakeCollector(),
        max_input_chars=20_000,
        clock=lambda: datetime.fromisoformat("2026-11-25T00:05:02+00:00"),
        provider_binding=provider_binding(db),
        owner_id=7,
    )
    asyncio.run(new_runner.run(new_claim))
    assert new_provider.calls == ["adversarial"]
    assert db.get_auto_review(result.review_id).verdict == "PASS"


def test_resume_after_adversarial_reuses_both_stages(tmp_path):
    db = make_db(tmp_path)
    result = reserve(db, (member(1, SHA2),))
    claim = db.claim_auto_review(owner="old", now=T1)
    first_runner = runner(db, FakeProvider(), FakeCollector())
    cycle = db.get_auto_review(result.review_id)
    membership = db.get_auto_review_memberships(result.review_id)[0]
    evidence = evid(membership)
    blind, blind_validation = asyncio.run(
        first_runner._blind(claim, cycle, membership, evidence)
    )
    asyncio.run(
        first_runner._adversarial(
            claim, cycle, membership, evidence, blind, blind_validation
        )
    )
    new_claim = db.claim_auto_review(owner="new", now=T303)
    assert new_claim is not None
    provider = FakeProvider()
    new_runner = ReviewRunner(
        db,
        provider,
        FakeCollector(),
        max_input_chars=20_000,
        clock=lambda: datetime.fromisoformat("2026-11-25T00:05:02+00:00"),
        provider_binding=provider_binding(db),
        owner_id=7,
    )
    asyncio.run(new_runner.run(new_claim))
    assert provider.calls == []
    assert db.get_auto_review(result.review_id).verdict == "PASS"


def test_conversation_aggregate_fails_if_any_pr_ci_fails(tmp_path):
    db = make_db(tmp_path)
    result = reserve(db, (member(1, SHA2), member(2, SHA4, base=SHA3)))
    collector = FakeCollector(ci_state="failure")
    worker = ReviewWorker(
        db, runner(db, FakeProvider(), collector), owner="worker-1",
        clock=lambda: datetime.fromisoformat(T2),
    )
    claim = worker._claim()
    asyncio.run(worker._process(claim))
    cycle = db.get_auto_review(result.review_id)
    assert cycle.verdict == "FAIL"
    assert "FAIL" in cycle.delivery_text


def test_retry_exhaustion_is_terminal_and_not_claimable(tmp_path):
    db = make_db(tmp_path)
    result = reserve(db, (member(1, SHA2),))
    for index in range(5):
        now = f"2026-11-25T00:{10 + index:02d}:00+00:00"
        claim = db.claim_auto_review(owner="worker", now=now)
        assert claim is not None
        outcome = db.fail_auto_review(
            result.review_id,
            lease_token=claim.lease_token,
            lease_epoch=claim.lease_epoch,
            error_class="provider_timeout",
            retryable=True,
            now=now,
        )
        if index < 4:
            assert outcome == "retry_wait"
        else:
            assert outcome == "terminal_failed"
    cycle = db.get_auto_review(result.review_id)
    assert cycle.lifecycle_state == AUTO_REVIEW_LIFECYCLE_DELIVERY_PENDING
    assert cycle.verdict == "BLOCKED"
    assert db.claim_auto_review(owner="worker", now="2026-11-25T00:20:00+00:00") is None
    assert db.ensure_pending_auto_review_deliveries(now=T2) == 1


def test_secret_in_model_output_is_not_persisted(tmp_path):
    db = make_db(tmp_path)
    result = reserve(db, (member(1, SHA2),))
    secret = "sk-review-SENTINEL-123456"
    def blind_with_secret():
        payload = json.loads(blind_json())
        payload["summary"] = secret
        return json.dumps(payload)

    provider = FakeProvider(blind=blind_with_secret)
    worker = ReviewWorker(
        db, runner(db, provider, FakeCollector()), owner="worker-1",
        clock=lambda: datetime.fromisoformat(T2),
    )
    claim = worker._claim()
    asyncio.run(worker._process(claim))
    cycle = db.get_auto_review(result.review_id)
    assert cycle.lifecycle_state == AUTO_REVIEW_LIFECYCLE_DELIVERY_PENDING
    assert cycle.verdict == "BLOCKED"
    rows = [dict(row) for row in db._conn.execute("SELECT * FROM auto_review_stages")]
    rows += [dict(row) for row in db._conn.execute("SELECT * FROM auto_reviews")]
    assert secret not in str(rows)
    assert db.get_auto_review_stage(result.review_id, 1, 1, "blind") is None


def test_implementation_report_secret_is_redacted_before_persistence(tmp_path):
    db = make_db(tmp_path)
    secret = "sk-report-SENTINEL-123456"
    result = db.reserve_conversation_review(
        conversation_id="conv-1",
        chat_id=7,
        memberships=(member(1, SHA2),),
        provider_snapshot_id=snapshot(db).id,
        reserved_by="test",
        implementation_report=f"report {secret}",
        now=T0,
    )
    assert result.outcome == AUTO_REVIEW_RESERVATION_NEW
    cycle = db.get_auto_review(result.review_id)
    assert secret not in cycle.implementation_report
    assert secret not in str(dict(db._conn.execute("SELECT * FROM auto_reviews").fetchone()))


def test_claim_ignores_legacy_per_pr_rows(tmp_path):
    db = make_db(tmp_path)
    snap = snapshot(db)
    result = db.reserve_auto_review(
        reservation_key="v1:per_pr:conv:1:1:" + SHA2,
        conversation_id="conv",
        repository_id=1,
        repository_full_name="owner/repo",
        head_sha=SHA2,
        scope="per_pr",
        pr_number=1,
        provider_snapshot_id=snap.id,
        reserved_by="test",
        now=T0,
    )
    assert result.outcome == AUTO_REVIEW_RESERVATION_NEW
    assert db.claim_auto_review(owner="worker", now=T1) is None


def test_reservation_key_is_deterministic_and_conversation_independent(tmp_path):
    db = make_db(tmp_path)
    first = reserve(db, (member(1, SHA2),), conv="conv-a")
    second = reserve(db, (member(1, SHA2),), conv="conv-b")
    assert first.outcome == AUTO_REVIEW_RESERVATION_NEW
    assert second.outcome == AUTO_REVIEW_RESERVATION_NEW
    assert db.get_auto_review(first.review_id).conversation_id == "conv-a"
    assert db.get_auto_review(second.review_id).conversation_id == "conv-b"


def test_concurrent_reservation_has_one_winner(tmp_path):
    path = str(tmp_path / "review.sqlite3")
    db1 = Database(path)
    db2 = Database(path)
    snap = snapshot(db1)
    barrier = threading.Barrier(2)
    results = []
    errors = []

    def run(db):
        try:
            barrier.wait(timeout=10)
            results.append(
                db.reserve_conversation_review(
                    conversation_id="conv",
                    chat_id=1,
                    memberships=(member(1, SHA2),),
                    provider_snapshot_id=snap.id,
                    reserved_by="test",
                    implementation_report=REPORT,
                    now=T0,
                )
            )
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=run, args=(db,)) for db in (db1, db2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert not errors
    assert sorted(item.outcome for item in results) == [
        AUTO_REVIEW_RESERVATION_ALREADY,
        AUTO_REVIEW_RESERVATION_NEW,
    ]
    assert db1._conn.execute("SELECT count(*) FROM auto_reviews").fetchone()[0] == 1


def test_resume_after_evidence_does_not_require_rerunning_blind(tmp_path):
    db = make_db(tmp_path)
    result = reserve(db, (member(1, SHA2),))
    claim = db.claim_auto_review(owner="old", now=T1)
    first_runner = runner(db, FakeProvider(), FakeCollector())
    membership = db.get_auto_review_memberships(result.review_id)[0]
    evidence = evid(membership)
    first_runner._persist_evidence(claim, membership, evidence)
    new_claim = db.claim_auto_review(owner="new", now=T303)
    assert new_claim is not None
    provider = FakeProvider()
    new_runner = ReviewRunner(
        db,
        provider,
        FakeCollector(),
        max_input_chars=20_000,
        clock=lambda: datetime.fromisoformat("2026-11-25T00:05:02+00:00"),
        provider_binding=provider_binding(db),
        owner_id=7,
    )
    asyncio.run(new_runner.run(new_claim))
    assert provider.calls == ["blind", "adversarial"]
    assert db.get_auto_review(result.review_id).verdict == "PASS"


def test_changed_evidence_invalidates_a_persisted_stage(tmp_path):
    db = make_db(tmp_path)
    result = reserve(db, (member(1, SHA2),))
    claim = db.claim_auto_review(owner="old", now=T1)
    first_runner = runner(db, FakeProvider(), FakeCollector())
    cycle = db.get_auto_review(result.review_id)
    membership = db.get_auto_review_memberships(result.review_id)[0]
    evidence = evid(membership)
    asyncio.run(first_runner._blind(claim, cycle, membership, evidence))
    new_claim = db.claim_auto_review(owner="new", now=T303)
    changed = ReviewEvidence.from_raw_diff(
        repository="owner/repo",
        pr_number=1,
        branch="agent/x",
        base_sha=SHA1,
        head_sha=SHA2,
        diff_text=diff().replace("+new", "+changed"),
        max_input_chars=20_000,
        ci_runs=runs(SHA2),
        sha_status="verified",
    )
    new_runner = ReviewRunner(
        db,
        FakeProvider(),
        FakeCollector(),
        max_input_chars=20_000,
        clock=lambda: datetime.fromisoformat("2026-11-25T00:05:02+00:00"),
        provider_binding=provider_binding(db),
        owner_id=7,
    )
    with pytest.raises(ReviewPipelineError) as info:
        asyncio.run(new_runner._blind(new_claim, cycle, membership, changed))
    assert info.value.code == "stale_blind_evidence"


def test_terminal_cycle_is_not_claimed_again(tmp_path):
    db = make_db(tmp_path)
    result = reserve(db, (member(1, SHA2),))
    claim = db.claim_auto_review(owner="w", now=T1)
    mark_adversarial_validated(db, result.review_id, claim)
    db.complete_auto_review(
        result.review_id,
        lease_token=claim.lease_token,
        lease_epoch=claim.lease_epoch,
        verdict="PASS",
        report_ref="review",
        delivery_text="result",
        now=T2,
    )
    outbox_id = db.schedule_auto_review_delivery(result.review_id, now=T2)
    db.set_outbox_status(outbox_id, "sent", T2)
    assert db.claim_auto_review(owner="w", now=T303) is None
    assert db.ensure_pending_auto_review_deliveries(now=T303) == 0


def test_pending_pr_is_consumed_by_later_cycle(tmp_path):
    db = make_db(tmp_path)
    first = reserve(db, (member(1, SHA2),))
    db.observe_auto_review_membership(
        conversation_id="conv-1", membership=member(2, SHA4, base=SHA3), now=T1
    )
    db._conn.execute(
        "UPDATE auto_reviews SET status=?, lifecycle_state=?, terminal_reason=? WHERE id=?",
        (AUTO_REVIEW_STATUS_TERMINAL, AUTO_REVIEW_LIFECYCLE_TERMINAL, "test", first.review_id),
    )
    db._conn.commit()
    later = db.reserve_conversation_review(
        conversation_id="conv-1",
        chat_id=7,
        memberships=(member(2, SHA4, base=SHA3),),
        provider_snapshot_id=snapshot(db).id,
        reserved_by="test",
        implementation_report=REPORT,
        now=T2,
    )
    assert later.outcome == AUTO_REVIEW_RESERVATION_NEW
    assert db.list_pending_auto_review_memberships("conv-1") == ()
    assert {
        (item.repository_id, item.pr_number)
        for item in db.get_auto_review_memberships(later.review_id)
    } == {(1, 2)}


def test_renew_lease_extends_only_for_current_owner(tmp_path):
    db = make_db(tmp_path)
    result = reserve(db, (member(1, SHA2),))
    claim = db.claim_auto_review(owner="w", now=T1, lease_seconds=300)
    assert db.renew_auto_review_lease(
        result.review_id, claim.lease_token, now=T2, lease_seconds=300
    )
    lease = db._conn.execute("SELECT expires_at FROM auto_review_leases").fetchone()
    assert lease["expires_at"] == "2026-11-25T00:05:02+00:00"
    assert not db.renew_auto_review_lease(
        result.review_id, "wrong-token", now=T2, lease_seconds=300
    )


def test_exhausted_attempts_are_terminalized_on_claim(tmp_path):
    db = make_db(tmp_path)
    result = reserve(db, (member(1, SHA2),))
    for index in range(1, 6):
        now = (datetime.fromisoformat(T1) + timedelta(seconds=301 * index)).isoformat()
        claim = db.claim_auto_review(owner="worker", now=now, lease_seconds=300)
        assert claim is not None
    assert db.claim_auto_review(
        owner="worker", now="2026-11-25T02:00:00+00:00", lease_seconds=300
    ) is None
    cycle = db.get_auto_review(result.review_id)
    assert cycle.lifecycle_state == AUTO_REVIEW_LIFECYCLE_DELIVERY_PENDING
    assert cycle.verdict == "BLOCKED"
    assert db.ensure_pending_auto_review_deliveries(now="2026-11-25T02:00:00+00:00") == 1


def test_schedule_existing_outbox_syncs_terminal_status(tmp_path):
    db = make_db(tmp_path)
    result = reserve(db, (member(1, SHA2),))
    claim = db.claim_auto_review(owner="w", now=T1)
    mark_adversarial_validated(db, result.review_id, claim)
    db.complete_auto_review(
        result.review_id,
        lease_token=claim.lease_token,
        lease_epoch=claim.lease_epoch,
        verdict="PASS",
        report_ref="review",
        delivery_text="result",
        now=T2,
    )
    outbox_id = db.schedule_auto_review_delivery(result.review_id, now=T2)
    db.set_outbox_status(outbox_id, "sent", T2)
    db._conn.execute(
        "UPDATE auto_reviews SET lifecycle_state=?, delivery_state='none', status=? "
        "WHERE id=?",
        (AUTO_REVIEW_LIFECYCLE_DELIVERY_PENDING, AUTO_REVIEW_STATUS_RESERVED, result.review_id),
    )
    db._conn.commit()
    assert db.schedule_auto_review_delivery(result.review_id, now=T303) == outbox_id
    cycle = db.get_auto_review(result.review_id)
    assert cycle.status == AUTO_REVIEW_STATUS_TERMINAL
    assert cycle.delivery_state == "sent"


def test_direct_stage_secret_is_rejected(tmp_path):
    from bot.db import AutoReviewConflict

    db = make_db(tmp_path)
    result = reserve(db, (member(1, SHA2),))
    claim = db.claim_auto_review(owner="w", now=T1)
    with pytest.raises(AutoReviewConflict):
        db.save_auto_review_stage(
            result.review_id,
            1,
            1,
            "blind",
            "validated",
            lease_token=claim.lease_token,
            lease_epoch=claim.lease_epoch,
            evidence_sha256="e" * 64,
            output_json='{"summary":"sk-review-SENTINEL-123456"}',
            validation_json="{}",
            now=T2,
        )
    assert db.get_auto_review_stage(result.review_id, 1, 1, "blind") is None


def test_invalid_blind_never_runs_adversarial(tmp_path):
    db = make_db(tmp_path)
    result = reserve(db, (member(1, SHA2),))
    provider = FakeProvider(blind=lambda: "not-json")
    worker = ReviewWorker(
        db, runner(db, provider, FakeCollector()), owner="worker-1",
        clock=lambda: datetime.fromisoformat(T2),
    )
    claim = worker._claim()
    asyncio.run(worker._process(claim))
    assert "adversarial" not in provider.calls
    assert db.get_auto_review(result.review_id).lifecycle_state == "retry_wait"
    assert db.get_auto_review_stage(result.review_id, 1, 1, "adversarial") is None


def test_blind_evidence_failure_blocks_without_adversarial(tmp_path):
    db = make_db(tmp_path)
    result = reserve(db, (member(1, SHA2),))
    bad = json.loads(blind_json())
    bad["reviewed_files"] = ["not-the-file.py"]
    provider = FakeProvider(blind=lambda: json.dumps(bad))
    worker = ReviewWorker(
        db, runner(db, provider, FakeCollector()), owner="worker-1",
        clock=lambda: datetime.fromisoformat(T2),
    )
    claim = worker._claim()
    asyncio.run(worker._process(claim))
    assert provider.calls == ["blind"]
    cycle = db.get_auto_review(result.review_id)
    assert cycle.lifecycle_state == AUTO_REVIEW_LIFECYCLE_DELIVERY_PENDING
    assert cycle.verdict == "BLOCKED"
    assert db.get_auto_review_stage(result.review_id, 1, 1, "blind").status == "invalid"
    assert db.get_auto_review_stage(result.review_id, 1, 1, "adversarial") is None
