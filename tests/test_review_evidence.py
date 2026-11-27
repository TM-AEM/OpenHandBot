"""R4: evidence validation, line coverage, SHA/CI provenance, and stale evidence."""

from __future__ import annotations

import pytest

from bot.review.evidence import (
    EvidenceError,
    ReviewEvidence,
    validate_adversarial_binding,
    validate_stage_output,
)
from bot.review.github import (
    ChangedFile,
    CompareResult,
    WorkflowJob,
    WorkflowJobsEvidence,
    WorkflowRun,
    WorkflowRunsEvidence,
)
from bot.review.schema import (
    AdversarialReviewOutput,
    BlindReviewOutput,
    Challenge,
    Finding,
)

A = "a" * 40
B = "b" * 40


def diff(path="src/x.py", body="+new\n+added\n"):
    return (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        "@@ -1,2 +1,4 @@\n"
        " old\n"
        f"{body}"
        " context\n"
    )


def evidence(*, diff_text=None, sha_status="verified", ci_runs=None, ci_jobs=(), max_chars=20_000):
    return ReviewEvidence.from_raw_diff(
        repository="owner/repo",
        pr_number=1,
        branch="agent/x",
        base_sha=A,
        head_sha=B,
        diff_text=diff_text if diff_text is not None else diff(),
        max_input_chars=max_chars,
        ci_runs=ci_runs,
        ci_jobs=ci_jobs,
        architecture_decisions=("D1",),
        sha_status=sha_status,
    )


def finding(**over):
    value = {
        "id": "F-1",
        "severity": "medium",
        "category": "correctness",
        "claim": "claim",
        "description": "description",
        "file": "src/x.py",
        "line_start": 2,
        "line_end": 2,
        "confidence": "high",
        "evidence_quote": "+new",
        "ci_run_id": None,
        "ci_job_id": None,
        "ci_status": None,
        "commit_sha": None,
        "recommendation": None,
    }
    value.update(over)
    return Finding(**value)


def blind(findings=(), reviewed=("src/x.py",), gaps=()):
    return BlindReviewOutput(
        schema_version="r4.v1",
        stage="blind",
        assessment="findings" if findings else "clean",
        summary="summary",
        findings=tuple(findings),
        reviewed_files=tuple(reviewed),
        evidence_gaps=tuple(gaps),
    )


def adversarial(blind_output, findings=(), challenges=(), reviewed=("src/x.py",), gaps=()):
    return AdversarialReviewOutput(
        schema_version="r4.v1",
        stage="adversarial",
        blind_review_sha256=blind_output.fingerprint,
        assessment="concur",
        summary="summary",
        findings=tuple(findings),
        challenges=tuple(challenges),
        reviewed_files=tuple(reviewed),
        evidence_gaps=tuple(gaps),
    )


def runs(*, ci_state="success", head_sha=B, run_id=1, name="verify", conclusion="success"):
    run = WorkflowRun(
        run_id=run_id,
        name=name,
        head_sha=head_sha,
        head_branch="agent/x",
        status="completed",
        conclusion=conclusion,
        event="push",
        run_attempt=1,
        created_at=None,
        updated_at=None,
    )
    return WorkflowRunsEvidence(
        repository="owner/repo",
        head_sha=head_sha,
        runs=(run,),
        status="verified",
        observed_head_shas=(head_sha,),
        ci_state=ci_state,
    )


def jobs(*, head_sha=B, run_id=1, job_id=10, conclusion="success"):
    job = WorkflowJob(
        job_id=job_id,
        run_id=run_id,
        name="test",
        head_sha=head_sha,
        status="completed",
        conclusion=conclusion,
        started_at=None,
        completed_at=None,
    )
    return WorkflowJobsEvidence(
        repository="owner/repo",
        run_id=run_id,
        head_sha=head_sha,
        jobs=(job,),
        status="verified",
        observed_head_shas=(head_sha,),
    )


def test_diff_line_coverage_and_valid_finding_provenance():
    result = validate_stage_output(blind([finding()]), evidence())
    assert result.stage_valid is True
    assert result.accepted == (finding(),)
    assert result.accepted[0].id == "F-1"
    assert result.rejected == ()


def test_nonexistent_line_is_rejected_and_not_accepted():
    result = validate_stage_output(blind([finding(line_start=99, line_end=99)]), evidence())
    assert result.stage_valid is False
    assert result.accepted == ()
    assert result.rejected[0].reason == "line_not_in_diff"
    assert result.invalid_findings == 1


@pytest.mark.parametrize(
    "bad,reason",
    [
        (finding(file="../secret.py"), "invalid_path"),
        (finding(file="/etc/passwd"), "invalid_path"),
        (finding(file="src/other.py"), "file_not_in_diff"),
        (finding(evidence_quote="not in patch"), "evidence_quote_not_found"),
        (finding(commit_sha="c" * 40), "commit_sha_mismatch"),
        (finding(ci_run_id=999), "ci_run_not_found"),
        (finding(ci_job_id=999), "ci_job_not_found"),
    ],
)

def test_unverifiable_findings_are_rejected(bad, reason):
    result = validate_stage_output(
        blind([bad]), evidence(ci_runs=runs(), ci_jobs=(jobs(),))
    )
    assert result.stage_valid is False
    assert result.accepted == ()
    assert result.rejected[0].reason == reason


def test_ci_claim_without_ci_evidence_is_rejected():
    result = validate_stage_output(blind([finding(ci_run_id=1)]), evidence())
    assert result.stage_valid is False
    assert result.rejected[0].reason == "ci_evidence_missing"


def test_valid_ci_references_are_accepted_and_fabricated_status_is_rejected():
    accepted = finding(ci_run_id=1, ci_job_id=10, ci_status="success")
    result = validate_stage_output(
        blind([accepted]), evidence(ci_runs=runs(), ci_jobs=(jobs(),))
    )
    assert result.stage_valid is True
    assert result.accepted[0].ci_job_id == 10
    bad = finding(ci_run_id=1, ci_status="failure")
    result = validate_stage_output(
        blind([bad]), evidence(ci_runs=runs(), ci_jobs=(jobs(),))
    )
    assert result.stage_valid is False
    assert result.rejected[0].reason == "ci_status_mismatch"


def test_sha_and_ci_binding_mismatches_are_rejected():
    with pytest.raises(EvidenceError) as info:
        evidence(ci_runs=runs(head_sha="c" * 40))
    assert info.value.code == "ci_sha_mismatch"
    with pytest.raises(EvidenceError) as info:
        evidence(ci_jobs=(jobs(head_sha="c" * 40),))
    assert info.value.code == "ci_jobs_not_verified"


def test_stale_or_unverified_sha_blocks_stage():
    result = validate_stage_output(blind([finding()]), evidence(sha_status="unverified"))
    assert result.stage_valid is False
    assert result.invalid_reason == "sha_unverified"


def test_excluded_file_and_incomplete_coverage_are_blocked():
    excluded = (
        "diff --git a/docs/README.md b/docs/README.md\n"
        "--- a/docs/README.md\n"
        "+++ b/docs/README.md\n"
        "@@ -1 +1 @@\n"
        "-old\n+new\n"
    )
    review = evidence(diff_text=excluded)
    assert review.excluded_paths == ("docs/README.md",)
    assert review.coverage_complete is False
    result = validate_stage_output(blind([], reviewed=()), review)
    assert result.stage_valid is False
    assert result.invalid_reason == "diff_coverage_incomplete"


def test_reviewed_files_must_match_expected_coverage():
    result = validate_stage_output(blind([], reviewed=()), evidence())
    assert result.stage_valid is False
    assert result.invalid_reason == "reviewed_files_mismatch"


def test_model_evidence_gaps_are_blocked():
    result = validate_stage_output(blind(gaps=("cannot verify line",)), evidence())
    assert result.stage_valid is False
    assert result.invalid_reason == "model_evidence_gaps"


def test_secret_redaction_is_recorded_as_secret_evidence():
    secret_diff = diff(body='+token = "ghp_SECRET_EVIDENCE_1234567890"\n+safe\n')
    review = evidence(diff_text=secret_diff)
    assert review.secret_detected is True
    assert review.secret_redactions


def test_adversarial_binding_requires_exact_blind_fingerprint_and_known_ids():
    review = evidence()
    blind_result = blind([finding()])
    good = adversarial(blind_result, challenges=(Challenge("F-1", "supported", "checked"),))
    result = validate_adversarial_binding(good, blind_result, review)
    assert result.stage_valid is True
    bad = adversarial(blind_result, challenges=(Challenge("F-999", "supported", "x"),))
    result = validate_adversarial_binding(bad, blind_result, review)
    assert result.stage_valid is False
    assert result.invalid_reason == "unknown_blind_finding_reference"
    forged = AdversarialReviewOutput(
        schema_version="r4.v1",
        stage="adversarial",
        blind_review_sha256="0" * 64,
        assessment="concur",
        summary="s",
        findings=(),
        challenges=(),
        reviewed_files=("src/x.py",),
        evidence_gaps=(),
    )
    result = validate_adversarial_binding(forged, blind_result, review)
    assert result.invalid_reason == "blind_fingerprint_mismatch"


def test_compare_requires_verified_status_and_exact_file_coverage():
    compare = CompareResult(
        repository="owner/repo",
        base_sha=A,
        head_sha=B,
        merge_base_sha=A,
        status="verified",
        ahead_by=1,
        behind_by=0,
        files=(
            ChangedFile(
                "src/x.py",
                "modified",
                2,
                1,
                3,
                "@@ -1,2 +1,4 @@\n old\n+new\n+added\n context\n",
            ),
        ),
        commits=(),
        observed_base_sha=A,
        observed_head_sha=B,
    )
    review = ReviewEvidence.from_compare(
        compare,
        diff_text=diff(),
        max_input_chars=20_000,
        branch="agent/x",
        pr_number=1,
    )
    assert review.sha_status == "verified"
    bad = CompareResult(
        repository="owner/repo",
        base_sha=A,
        head_sha=B,
        merge_base_sha=A,
        status="head_sha_mismatch",
        ahead_by=0,
        behind_by=0,
        files=(),
        commits=(),
        observed_base_sha=A,
        observed_head_sha=None,
    )
    with pytest.raises(EvidenceError) as info:
        ReviewEvidence.from_compare(
            bad,
            diff_text=diff(),
            max_input_chars=20_000,
            branch="agent/x",
            pr_number=1,
        )
    assert info.value.code == "compare_not_verified"


def test_malformed_hunk_counts_are_rejected():
    malformed = diff().replace("@@ -1,2 +1,4 @@", "@@ -1,2 +1,5 @@")
    with pytest.raises(EvidenceError) as info:
        evidence(diff_text=malformed)
    assert info.value.code == "diff_hunk_count_mismatch"



def test_content_line_cannot_spoof_diff_path():
    spoof = (
        "diff --git a/src/x.py b/src/x.py\n"
        "--- a/src/x.py\n"
        "+++ b/src/x.py\n"
        "@@ -1 +1,2 @@\n"
        "-old\n"
        "++++ b/evil.py\n"
        "+--- a/evil.py\n"
    )
    review = evidence(diff_text=spoof)
    assert review.files_by_path["src/x.py"].new_lines == frozenset({1, 2})
    result = validate_stage_output(blind([finding(file="evil.py")]), review)
    assert result.stage_valid is False
    assert result.rejected[0].reason == "file_not_in_diff"

def test_empty_diff_allows_empty_reviewed_files():
    review = evidence(diff_text="")
    result = validate_stage_output(blind([], reviewed=()), review)
    assert result.stage_valid is True



def test_compare_coverage_mismatch_is_rejected():
    compare = CompareResult(
        repository="owner/repo",
        base_sha=A,
        head_sha=B,
        merge_base_sha=A,
        status="verified",
        ahead_by=1,
        behind_by=0,
        files=(
            ChangedFile(
                "src/x.py",
                "modified",
                2,
                1,
                3,
                "@@ -1,2 +1,4 @@\n old\n+new\n+added\n context\n",
            ),
        ),
        commits=(),
        observed_base_sha=A,
        observed_head_sha=B,
    )
    with pytest.raises(EvidenceError) as info:
        ReviewEvidence.from_compare(
            compare,
            diff_text=diff(path="src/other.py"),
            max_input_chars=20_000,
            branch="agent/x",
            pr_number=1,
        )
    assert info.value.code == "diff_coverage_mismatch"



def test_oversized_diff_is_rejected_not_truncated():
    with pytest.raises(EvidenceError) as info:
        evidence(diff_text=diff(body="+x" * 10_000), max_chars=2_000)
    assert info.value.code in {"diff_too_large", "diff_redaction_blocked"}
