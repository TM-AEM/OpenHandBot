"""R4: deterministic verdict precedence and fail-closed rules."""

from __future__ import annotations

import pytest

from bot.review.evidence import (
    FindingValidation,
    ReviewEvidence,
    StageEvidenceValidation,
)
from bot.review.github import (
    WorkflowJob,
    WorkflowJobsEvidence,
    WorkflowRun,
    WorkflowRunsEvidence,
)
from bot.review.schema import Finding
from bot.review.verdict import (
    VERDICT_BLOCKED,
    VERDICT_FAIL,
    VERDICT_PASS,
    VERDICT_PASS_WITH_NOTES,
    evaluate_verdict,
)

A = "a" * 40
B = "b" * 40


def diff(body="+new\n"):
    return (
        "diff --git a/src/x.py b/src/x.py\n"
        "--- a/src/x.py\n"
        "+++ b/src/x.py\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        f"{body}"
    )


def runs(*, ci_state="success", conclusion="success", name="verify"):
    run = WorkflowRun(
        run_id=1,
        name=name,
        head_sha=B,
        head_branch="agent/x",
        status="completed" if ci_state in ("success", "failure") else "in_progress",
        conclusion=conclusion if ci_state in ("success", "failure") else None,
        event="push",
        run_attempt=1,
        created_at=None,
        updated_at=None,
    )
    return WorkflowRunsEvidence(
        repository="owner/repo",
        head_sha=B,
        runs=(run,),
        status="verified",
        observed_head_shas=(B,),
        ci_state=ci_state,
    )


def jobs(*, head_sha=B, run_id=1):
    return WorkflowJobsEvidence(
        repository="owner/repo",
        run_id=run_id,
        head_sha=head_sha,
        jobs=(
            WorkflowJob(
                job_id=10,
                run_id=run_id,
                name="test",
                head_sha=head_sha,
                status="completed",
                conclusion="success",
                started_at=None,
                completed_at=None,
            ),
        ),
        status="verified",
        observed_head_shas=(head_sha,),
    )


def evidence(*, ci_state="success", diff_text=None, sha_status="verified"):
    return ReviewEvidence.from_raw_diff(
        repository="owner/repo",
        pr_number=1,
        branch="agent/x",
        base_sha=A,
        head_sha=B,
        diff_text=diff_text if diff_text is not None else diff(),
        max_input_chars=20_000,
        ci_runs=runs(ci_state=ci_state),
        ci_jobs=(jobs(),),
        sha_status=sha_status,
        # Verdict precedence tests isolate CI completeness; F-01 owns the
        # documented workflow-contract checks.
        ci_jobs_complete=True,
    )


def finding(severity="medium", finding_id="F-1"):
    return Finding(
        id=finding_id,
        severity=severity,
        category="correctness",
        claim="claim",
        description="description",
        file="src/x.py",
        line_start=2,
        line_end=2,
        confidence="high",
        evidence_quote="+new",
    )


def validation(
    stage="blind",
    *,
    accepted=(),
    rejected=(),
    gaps=(),
    valid=True,
    sha_status="verified",
    coverage=True,
    reason=None,
):
    return StageEvidenceValidation(
        stage=stage,
        accepted=tuple(accepted),
        rejected=tuple(rejected),
        reviewed_files=("src/x.py",),
        evidence_gaps=tuple(gaps),
        sha_status=sha_status,
        coverage_complete=coverage,
        stage_valid=valid,
        invalid_reason=reason,
    )


def evaluate(
    *,
    ev=None,
    blind=None,
    adv=None,
    blind_ok=True,
    adv_ok=True,
    blind_assessment="clean",
    adv_assessment="concur",
    notes=(),
):
    return evaluate_verdict(
        evidence=ev or evidence(),
        blind_validation=blind or validation(),
        adversarial_validation=adv or validation(stage="adversarial"),
        blind_stage_ok=blind_ok,
        adversarial_stage_ok=adv_ok,
        blind_assessment=blind_assessment,
        adversarial_assessment=adv_assessment,
        notes=notes,
    )


def test_ci_failure_wins_even_with_successful_review_and_high_finding():
    result = evaluate(
        ev=evidence(ci_state="failure"),
        blind=validation(accepted=(finding("high"),)),
    )
    assert result.verdict == VERDICT_FAIL
    assert result.rule == "R4-CI-01"


def test_ci_failure_wins_over_failed_review_stage():
    result = evaluate(ev=evidence(ci_state="failure"), blind_ok=False, adv_ok=False)
    assert result.verdict == VERDICT_FAIL


def test_stale_sha_blocks_even_when_ci_failed():
    result = evaluate(
        ev=evidence(ci_state="failure", sha_status="unverified"),
        blind=validation(sha_status="unverified", valid=False),
        adv=validation(stage="adversarial", sha_status="unverified", valid=False),
    )
    assert result.verdict == VERDICT_BLOCKED
    assert result.rule == "R4-SHA-01"


def test_secret_in_diff_fails_even_with_successful_ci():
    result = evaluate(
        ev=evidence(
            diff_text=diff(body='+token = "ghp_VERDICT_SECRET_1234567890"\n')
        )
    )
    assert result.verdict == VERDICT_FAIL
    assert result.rule == "R4-SEC-01"


@pytest.mark.parametrize("severity", ["critical", "high"])

def test_valid_critical_or_high_fails(severity):
    result = evaluate(blind=validation(accepted=(finding(severity),)))
    assert result.verdict == VERDICT_FAIL
    assert result.rule == "R4-FINDING-01"


@pytest.mark.parametrize("severity", ["medium", "low"])

def test_only_medium_or_low_passes_with_notes(severity):
    result = evaluate(blind=validation(accepted=(finding(severity),)))
    assert result.verdict == VERDICT_PASS_WITH_NOTES
    assert result.rule == "R4-NOTES-01"


def test_duplicate_id_keeps_the_highest_severity():
    blind = finding("medium", "F-1")
    adversarial = finding("high", "F-1")
    result = evaluate(
        blind=validation(accepted=(blind,)),
        adv=validation(stage="adversarial", accepted=(adversarial,)),
    )
    assert result.verdict == VERDICT_FAIL
    assert result.valid_findings == (adversarial,)


def test_ci_success_and_no_findings_passes():
    result = evaluate()
    assert result.verdict == VERDICT_PASS
    assert result.rule == "R4-PASS-01"


@pytest.mark.parametrize("ci_state", ["missing", "pending", "cancelled", "skipped", "mixed"])

def test_ci_unavailable_blocks(ci_state):
    ev = evidence(ci_state="success") if ci_state == "missing" else evidence(ci_state=ci_state)
    if ci_state == "missing":
        ev = ReviewEvidence.from_raw_diff(
            repository="owner/repo",
            pr_number=1,
            branch="agent/x",
            base_sha=A,
            head_sha=B,
            diff_text=diff(),
            max_input_chars=20_000,
            ci_runs=None,
            sha_status="verified",
        )
    result = evaluate(ev=ev)
    assert result.verdict == VERDICT_BLOCKED


def test_failed_stage_or_invalid_findings_blocks():
    assert evaluate(blind_ok=False).verdict == VERDICT_BLOCKED
    assert evaluate(adv_ok=False).verdict == VERDICT_BLOCKED
    bad = FindingValidation(finding(), False, "line_not_in_diff")
    assert evaluate(blind=validation(rejected=(bad,), valid=False)).verdict == VERDICT_BLOCKED
    assert evaluate(blind=validation(gaps=("missing",), valid=False)).verdict == VERDICT_BLOCKED


def test_insufficient_evidence_and_dissent_block():
    assert evaluate(blind_assessment="insufficient_evidence").verdict == VERDICT_BLOCKED
    assert evaluate(adv_assessment="insufficient_evidence").verdict == VERDICT_BLOCKED
    assert evaluate(adv_assessment="dissent").verdict == VERDICT_BLOCKED


def test_model_recommendation_has_no_effect_and_owner_acceptance_is_absent():
    result = evaluate(
        notes=("model_recommendation=FAIL", "owner_acceptance=PASS"),
    )
    assert result.verdict == VERDICT_PASS
    assert "owner_acceptance" not in result.__dict__
