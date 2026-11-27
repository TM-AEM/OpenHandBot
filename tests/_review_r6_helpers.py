"""Shared deterministic fixtures for R6 report/delivery/callback tests (not a test)."""
from __future__ import annotations

import hashlib
import json

from bot.db import AutoReviewMembership, Database
from bot.review.schema import parse_blind_review

SHA1 = "a" * 40
SHA2 = "b" * 40
SHA3 = "c" * 40
SHA4 = "d" * 40
T0 = "2026-11-25T00:00:00+00:00"
T1 = "2026-11-25T00:00:01+00:00"
T2 = "2026-11-25T00:00:02+00:00"


def member(pr, head, base=SHA1, name="owner/repo", repo_id=1):
    return AutoReviewMembership(repo_id, name, pr, "agent/x", base, head)


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


def reserve(db, members, *, conv="conv-1", chat=7):
    db.add_watched(conv, "test conversation", chat)
    return db.reserve_conversation_review(
        conversation_id=conv,
        chat_id=chat,
        memberships=tuple(members),
        provider_snapshot_id=snapshot(db).id,
        reserved_by="test",
        implementation_report="implementation report",
        now=T0,
    )


def finding(
    finding_id,
    severity="medium",
    *,
    claim="claim",
    description="description",
    file="src/x.py",
    line_start=1,
    line_end=1,
    quote=None,
):
    return {
        "id": finding_id,
        "severity": severity,
        "category": "correctness",
        "claim": claim,
        "description": description,
        "file": file,
        "line_start": line_start,
        "line_end": line_end,
        "confidence": "high",
        "evidence_quote": quote,
        "ci_run_id": 1,
        "ci_job_id": None,
        "ci_status": "success",
        "commit_sha": None,
        "recommendation": None,
    }


def blind_json(findings=None, *, assessment=None, gaps=None):
    findings = list(findings or [])
    if assessment is None:
        assessment = "findings" if findings else "clean"
    return json.dumps(
        {
            "schema_version": "r4.v1",
            "stage": "blind",
            "assessment": assessment,
            "summary": "blind summary",
            "findings": findings,
            "reviewed_files": ["src/x.py"],
            "evidence_gaps": list(gaps or []),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def adversarial_json(blind_text, findings=None, *, assessment="concur", gaps=None):
    findings = list(findings or [])
    blind = parse_blind_review(blind_text)
    return json.dumps(
        {
            "schema_version": "r4.v1",
            "stage": "adversarial",
            "blind_review_sha256": blind.fingerprint,
            "assessment": assessment,
            "summary": "adversarial summary",
            "findings": findings,
            "challenges": [],
            "reviewed_files": ["src/x.py"],
            "evidence_gaps": list(gaps or []),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def evidence_json(
    membership,
    *,
    coverage=True,
    ci_state="success",
    sha_status="verified",
    excluded=(),
    secret_redactions=(),
    jobs=None,
):
    return json.dumps(
        {
            "repository": membership.repository_full_name,
            "pr_number": membership.pr_number,
            "branch": membership.branch,
            "base_sha": membership.base_sha,
            "head_sha": membership.head_sha,
            "sha_status": sha_status,
            "coverage_complete": coverage,
            "excluded_paths": list(excluded),
            "secret_redactions": [list(item) for item in secret_redactions],
            "ci_state": ci_state,
            "files": [["src/x.py", "modified", 1, 1]],
            "ci_runs": [[1, "verify", "completed", ci_state]],
            "ci_jobs": list(jobs or []),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def seed_completed_cycle(
    db,
    members,
    *,
    verdict="PASS",
    blind_findings=None,
    adversarial_findings=None,
    coverage=True,
    ci_state="success",
    sha_status="verified",
    stage_status="validated",
    evidence_present=True,
    chat=7,
):
    result = reserve(db, members, chat=chat)
    assert result.review_id is not None
    review_id = result.review_id
    claim = db.claim_auto_review(owner="test-worker", now=T1, lease_seconds=300)
    assert claim is not None
    for item in members:
        if evidence_present:
            payload = evidence_json(
                item,
                coverage=coverage,
                ci_state=ci_state,
                sha_status=sha_status,
            )
            db._conn.execute(
                "INSERT INTO auto_review_evidence"
                "(review_id, repository_id, pr_number, head_sha, base_sha, "
                " evidence_sha256, diff_sha256, coverage_complete, ci_state, "
                " evidence_json, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    review_id,
                    item.repository_id,
                    item.pr_number,
                    item.head_sha,
                    item.base_sha,
                    hashlib.sha256(f"evidence-{item.pr_number}".encode()).hexdigest(),
                    hashlib.sha256(f"diff-{item.pr_number}".encode()).hexdigest(),
                    1 if coverage else 0,
                    ci_state,
                    payload,
                    T1,
                ),
            )
        if stage_status == "validated":
            blind_text = blind_json(blind_findings)
            adversarial_text = adversarial_json(
                blind_text, adversarial_findings, assessment="concur"
            )
            db._conn.execute(
                "INSERT INTO auto_review_stages"
                "(review_id, repository_id, pr_number, stage, status, attempt, "
                " evidence_sha256, output_json, output_sha256, validation_json, "
                " created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    review_id,
                    item.repository_id,
                    item.pr_number,
                    "blind",
                    "validated",
                    1,
                    hashlib.sha256(f"evidence-{item.pr_number}".encode()).hexdigest(),
                    blind_text,
                    hashlib.sha256(blind_text.encode()).hexdigest(),
                    json.dumps({"stage_valid": True, "accepted": 1, "rejected": []}),
                    T1,
                    T1,
                ),
            )
            db._conn.execute(
                "INSERT INTO auto_review_stages"
                "(review_id, repository_id, pr_number, stage, status, attempt, "
                " evidence_sha256, output_json, output_sha256, validation_json, "
                " created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    review_id,
                    item.repository_id,
                    item.pr_number,
                    "adversarial",
                    "validated",
                    1,
                    hashlib.sha256(f"evidence-{item.pr_number}".encode()).hexdigest(),
                    adversarial_text,
                    hashlib.sha256(adversarial_text.encode()).hexdigest(),
                    json.dumps({"stage_valid": True, "accepted": 1, "rejected": []}),
                    T1,
                    T1,
                ),
            )
        elif stage_status == "invalid":
            db._conn.execute(
                "INSERT INTO auto_review_stages"
                "(review_id, repository_id, pr_number, stage, status, attempt, "
                " evidence_sha256, output_json, output_sha256, validation_json, "
                " created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    review_id,
                    item.repository_id,
                    item.pr_number,
                    "blind",
                    "invalid",
                    1,
                    hashlib.sha256(f"evidence-{item.pr_number}".encode()).hexdigest(),
                    None,
                    None,
                    json.dumps(
                        {"stage_valid": False, "accepted": 0, "rejected": ["bad_quote"]}
                    ),
                    T1,
                    T1,
                ),
            )
    db._conn.execute(
        "UPDATE auto_reviews SET stage='adversarial_validated' WHERE id=?",
        (review_id,),
    )
    db._conn.commit()
    db.complete_auto_review(
        review_id,
        lease_token=claim.lease_token,
        lease_epoch=claim.lease_epoch,
        verdict=verdict,
        report_ref=f"review:{review_id}:{verdict}",
        delivery_text="legacy delivery text",
        now=T2,
    )
    return review_id
