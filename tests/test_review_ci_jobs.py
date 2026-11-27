"""R7 F-01: documented CI job completeness is required for PASS."""

from __future__ import annotations

import asyncio

import pytest

from bot.db import AutoReviewMembership
from bot.review.ci_contract import jobs_complete
from bot.review.collector import EvidenceCollectionError, GitHubEvidenceCollector
from bot.review.evidence import EvidenceError, ReviewEvidence, StageEvidenceValidation
from bot.review.github import (
    BranchVerification,
    ChangedFile,
    CompareResult,
    GitHubPaginationError,
    GitHubTransportError,
    RepositoryIdentity,
    WorkflowJob,
    WorkflowJobsEvidence,
    WorkflowRun,
    WorkflowRunsEvidence,
)
from bot.review.verdict import (
    VERDICT_BLOCKED,
    VERDICT_PASS,
    evaluate_verdict,
)

A = "a" * 40
B = "b" * 40
C = "c" * 40
VERIFY_PATH = ".github/workflows/verify.yml"


def diff():
    return (
        "diff --git a/src/x.py b/src/x.py\n"
        "--- a/src/x.py\n"
        "+++ b/src/x.py\n"
        "@@ -1 +1 @@\n"
        "-old\n+new\n"
    )


def run(*, head_sha=B, path=VERIFY_PATH, name="Verify agent branch", run_id=7):
    return WorkflowRunsEvidence(
        repository="owner/repo",
        head_sha=head_sha,
        runs=(
            WorkflowRun(
                run_id=run_id,
                name=name,
                head_sha=head_sha,
                head_branch="agent/x",
                status="completed",
                conclusion="success",
                event="push",
                run_attempt=1,
                created_at=None,
                updated_at=None,
                path=path,
            ),
        ),
        status="verified",
        observed_head_shas=(head_sha,),
        ci_state="success",
    )


def job(
    name,
    *,
    job_id=1,
    run_id=7,
    head_sha=B,
    status="completed",
    conclusion="success",
):
    return WorkflowJob(
        job_id=job_id,
        run_id=run_id,
        name=name,
        head_sha=head_sha,
        status=status,
        conclusion=conclusion,
        started_at=None,
        completed_at=None,
    )


def job_group(*items, run_id=7, head_sha=B, status="verified"):
    return WorkflowJobsEvidence(
        repository="owner/repo",
        run_id=run_id,
        head_sha=head_sha,
        jobs=tuple(items),
        status=status,
        observed_head_shas=(head_sha,),
    )


def verify_jobs():
    return job_group(
        job("Validate requested SHA", job_id=1),
        job("Python 3.11 checks", job_id=2),
        job("Python 3.13 checks", job_id=3),
        job("Frontend tests (Node)", job_id=4),
    )


def evidence(*, ci_runs=None, ci_jobs=None, head_sha=B):
    ci_runs = ci_runs or run(head_sha=head_sha)
    ci_jobs = (verify_jobs(),) if ci_jobs is None else ci_jobs
    return ReviewEvidence.from_raw_diff(
        repository="owner/repo",
        pr_number=3,
        branch="agent/x",
        base_sha=A,
        head_sha=head_sha,
        diff_text=diff(),
        max_input_chars=20_000,
        ci_runs=ci_runs,
        ci_jobs=ci_jobs,
        sha_status="verified",
        ci_jobs_complete=jobs_complete(ci_runs, ci_jobs),
    )


def validation(stage):
    return StageEvidenceValidation(
        stage=stage,
        accepted=(),
        rejected=(),
        reviewed_files=("src/x.py",),
        evidence_gaps=(),
        sha_status="verified",
        coverage_complete=True,
        stage_valid=True,
    )


def verdict(evidence_value):
    return evaluate_verdict(
        evidence=evidence_value,
        blind_validation=validation("blind"),
        adversarial_validation=validation("adversarial"),
        blind_stage_ok=True,
        adversarial_stage_ok=True,
        blind_assessment="clean",
        adversarial_assessment="concur",
    )


def test_all_expected_jobs_present_and_successful_can_pass():
    value = evidence()
    assert value.ci_jobs_complete is True
    assert verdict(value).verdict == VERDICT_PASS


def test_one_expected_job_missing_blocks():
    group = job_group(
        job("Validate requested SHA", job_id=1),
        job("Python 3.11 checks", job_id=2),
        job("Frontend tests (Node)", job_id=4),
    )
    value = evidence(ci_jobs=(group,))
    assert value.ci_jobs_complete is False
    result = verdict(value)
    assert result.verdict == VERDICT_BLOCKED
    assert result.rule == "R4-CI-03"


def test_empty_job_list_blocks():
    value = evidence(ci_jobs=())
    assert value.ci_jobs_complete is False
    assert verdict(value).verdict == VERDICT_BLOCKED


def test_job_retrieval_failure_is_explicit():
    class FailingClient:
        async def get_repository(self, repository):
            return RepositoryIdentity(1, "owner/repo", 1, "owner", True, False, False, "main")

        async def verify_branch_sha(self, repository, branch, expected_sha):
            return BranchVerification(
                "owner/repo", branch, expected_sha, expected_sha, "unchanged"
            )

        async def compare(self, repository, base_sha, head_sha):
            return CompareResult(
                repository="owner/repo",
                base_sha=A,
                head_sha=B,
                merge_base_sha=A,
                status="verified",
                ahead_by=1,
                behind_by=0,
                files=(
                    ChangedFile("src/x.py", "modified", 1, 1, 2, "@@ -1 +1 @@\n-old\n+new\n"),
                ),
                commits=(B,),
                observed_base_sha=A,
                observed_head_sha=B,
            )

        async def get_workflow_runs_for_sha(self, repository, head_sha):
            return run()

        async def list_run_jobs(self, repository, run_id, head_sha):
            raise GitHubTransportError("transport failure")

    with pytest.raises(EvidenceCollectionError) as info:
        asyncio.run(
            GitHubEvidenceCollector(FailingClient()).collect(
                AutoReviewMembership(1, "owner/repo", 3, "agent/x", A, B),
                architecture_decisions=(),
                max_input_chars=20_000,
            )
        )
    assert info.value.code == "GitHubTransportError"


def test_incomplete_or_truncated_job_pagination_is_explicit():
    class Client:
        async def get_repository(self, repository):
            return RepositoryIdentity(1, "owner/repo", 1, "owner", True, False, False, "main")

        async def verify_branch_sha(self, repository, branch, expected_sha):
            return BranchVerification(
                "owner/repo", branch, expected_sha, expected_sha, "unchanged"
            )

        async def compare(self, repository, base_sha, head_sha):
            return CompareResult(
                repository="owner/repo",
                base_sha=A,
                head_sha=B,
                merge_base_sha=A,
                status="verified",
                ahead_by=1,
                behind_by=0,
                files=(
                    ChangedFile("src/x.py", "modified", 1, 1, 2, "@@ -1 +1 @@\n-old\n+new\n"),
                ),
                commits=(B,),
                observed_base_sha=A,
                observed_head_sha=B,
            )

        async def get_workflow_runs_for_sha(self, repository, head_sha):
            return run()

        async def list_run_jobs(self, repository, run_id, head_sha):
            raise GitHubPaginationError("pagination limit")

    with pytest.raises(EvidenceCollectionError) as info:
        asyncio.run(
            GitHubEvidenceCollector(Client()).collect(
                AutoReviewMembership(1, "owner/repo", 3, "agent/x", A, B),
                architecture_decisions=(),
                max_input_chars=20_000,
            )
        )
    assert info.value.code == "GitHubPaginationError"


def test_failed_job_blocks():
    group = job_group(
        job("Validate requested SHA", job_id=1),
        job("Python 3.11 checks", job_id=2),
        job("Python 3.13 checks", job_id=3),
        job("Frontend tests (Node)", job_id=4, conclusion="failure"),
    )
    value = evidence(ci_jobs=(group,))
    assert value.ci_jobs_complete is False
    assert verdict(value).verdict == VERDICT_BLOCKED


def test_cancelled_job_blocks():
    group = job_group(
        job("Validate requested SHA", job_id=1),
        job("Python 3.11 checks", job_id=2),
        job("Python 3.13 checks", job_id=3),
        job("Frontend tests (Node)", job_id=4, conclusion="cancelled"),
    )
    value = evidence(ci_jobs=(group,))
    assert value.ci_jobs_complete is False
    assert verdict(value).verdict == VERDICT_BLOCKED


def test_duplicate_job_records_block():
    group = job_group(
        job("Validate requested SHA", job_id=1),
        job("Python 3.11 checks", job_id=2),
        job("Python 3.13 checks", job_id=2),
        job("Frontend tests (Node)", job_id=4),
    )
    value = evidence(ci_jobs=(group,))
    assert value.ci_jobs_complete is False
    assert verdict(value).verdict == VERDICT_BLOCKED


def test_job_belonging_to_another_run_is_rejected():
    group = job_group(
        job("Validate requested SHA", job_id=1, run_id=9),
        job("Python 3.11 checks", job_id=2, run_id=9),
        job("Python 3.13 checks", job_id=3, run_id=9),
        job("Frontend tests (Node)", job_id=4, run_id=9),
        run_id=9,
    )
    with pytest.raises(EvidenceError) as info:
        evidence(ci_jobs=(group,))
    assert info.value.code == "ci_job_mismatch"


def test_evidence_for_another_sha_is_rejected():
    with pytest.raises(EvidenceError) as info:
        evidence(ci_runs=run(head_sha=C), ci_jobs=(verify_jobs(),), head_sha=B)
    assert info.value.code == "ci_sha_mismatch"


def test_direct_evidence_without_completeness_is_not_complete():
    value = ReviewEvidence.from_raw_diff(
        repository="owner/repo",
        pr_number=3,
        branch="agent/x",
        base_sha=A,
        head_sha=B,
        diff_text=diff(),
        max_input_chars=20_000,
        ci_runs=run(),
        ci_jobs=(verify_jobs(),),
        sha_status="verified",
    )
    assert value.ci_jobs_complete is False
    assert verdict(value).verdict == VERDICT_BLOCKED


def test_unknown_workflow_contract_cannot_establish_completeness():
    ci_runs = run(path=".github/workflows/unknown.yml", name="Unknown")
    group = job_group(job("only-job", job_id=1))
    value = evidence(ci_runs=ci_runs, ci_jobs=(group,))
    assert value.ci_jobs_complete is False
    assert verdict(value).verdict == VERDICT_BLOCKED


def test_job_group_from_another_repository_blocks():
    group = WorkflowJobsEvidence(
        repository="other/repo",
        run_id=7,
        head_sha=B,
        jobs=(
            job("Validate requested SHA", job_id=1),
            job("Python 3.11 checks", job_id=2),
            job("Python 3.13 checks", job_id=3),
            job("Frontend tests (Node)", job_id=4),
        ),
        status="verified",
        observed_head_shas=(B,),
    )
    value = evidence(ci_jobs=(group,))
    assert value.ci_jobs_complete is False
    assert verdict(value).verdict == VERDICT_BLOCKED


def test_duplicate_workflow_run_records_block():
    duplicate = run()
    runs = WorkflowRunsEvidence(
        repository=duplicate.repository,
        head_sha=duplicate.head_sha,
        runs=(duplicate.runs[0], duplicate.runs[0]),
        status="verified",
        observed_head_shas=duplicate.observed_head_shas,
        ci_state="success",
    )
    value = evidence(ci_runs=runs, ci_jobs=(verify_jobs(),))
    assert value.ci_jobs_complete is False
    assert verdict(value).verdict == VERDICT_BLOCKED


def test_ci_matrix_prefix_contract_is_covered():
    ci_runs = run(path=".github/workflows/ci.yml", name="CI")
    group = job_group(
        job("Tests & lint (3.11)", job_id=1),
        job("Tests & lint (3.13)", job_id=2),
        job("Frontend tests (Node)", job_id=3),
    )
    assert jobs_complete(ci_runs, (group,)) is True
    assert evidence(ci_runs=ci_runs, ci_jobs=(group,)).ci_jobs_complete is True
