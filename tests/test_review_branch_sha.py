"""R7 F-03: explicit branch/SHA verification around R5 evidence collection."""

from __future__ import annotations

import asyncio

import pytest

from bot.db import AutoReviewMembership
from bot.review.collector import EvidenceCollectionError, GitHubEvidenceCollector
from bot.review.github import (
    BranchVerification,
    ChangedFile,
    CompareResult,
    GitHubTransportError,
    RepositoryIdentity,
    WorkflowJob,
    WorkflowJobsEvidence,
    WorkflowRun,
    WorkflowRunsEvidence,
)

A = "a" * 40
B = "b" * 40
C = "c" * 40


def membership(head_sha=B):
    return AutoReviewMembership(1, "owner/repo", 3, "agent/x", A, head_sha)


def compare(*, head_sha=B):
    return CompareResult(
        repository="owner/repo",
        base_sha=A,
        head_sha=head_sha,
        merge_base_sha=A,
        status="verified",
        ahead_by=1,
        behind_by=0,
        files=(
            ChangedFile("src/x.py", "modified", 1, 1, 2, "@@ -1 +1 @@\n-old\n+new\n"),
        ),
        commits=(head_sha,),
        observed_base_sha=A,
        observed_head_sha=head_sha,
    )


def runs(*, head_sha=B):
    return WorkflowRunsEvidence(
        repository="owner/repo",
        head_sha=head_sha,
        runs=(
            WorkflowRun(
                run_id=7,
                name="Verify agent branch",
                head_sha=head_sha,
                head_branch="agent/x",
                status="completed",
                conclusion="success",
                event="push",
                run_attempt=1,
                created_at=None,
                updated_at=None,
                path=".github/workflows/verify.yml",
            ),
        ),
        status="verified",
        observed_head_shas=(head_sha,),
        ci_state="success",
    )


def jobs(*, head_sha=B, run_id=7):
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


def unchanged():
    return BranchVerification("owner/repo", "agent/x", B, B, "unchanged")


class FakeGitHub:
    def __init__(self, *, verify_results=None, compare_result=None, runs_result=None):
        self.verify_results = list(verify_results or [unchanged(), unchanged()])
        self.compare_result = compare_result or compare()
        self.runs_result = runs_result or runs()
        self.calls = []

    async def get_repository(self, repository):
        self.calls.append(("repo", repository))
        return RepositoryIdentity(1, "owner/repo", 1, "owner", True, False, False, "main")

    async def verify_branch_sha(self, repository, branch, expected_sha):
        self.calls.append(("verify", repository, branch, expected_sha))
        result = self.verify_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    async def compare(self, repository, base_sha, head_sha):
        self.calls.append(("compare", repository, base_sha, head_sha))
        return self.compare_result

    async def get_workflow_runs_for_sha(self, repository, head_sha):
        self.calls.append(("runs", repository, head_sha))
        return self.runs_result

    async def list_run_jobs(self, repository, run_id, head_sha):
        self.calls.append(("jobs", repository, run_id, head_sha))
        return jobs(head_sha=head_sha, run_id=run_id)


def collect(client, head_sha=B):
    return asyncio.run(
        GitHubEvidenceCollector(client).collect(
            membership(head_sha),
            architecture_decisions=(),
            max_input_chars=20_000,
        )
    )


def test_exact_branch_sha_match_collects_evidence():
    client = FakeGitHub()
    result = collect(client)
    assert result.head_sha == B
    assert [call[0] for call in client.calls] == [
        "repo",
        "verify",
        "compare",
        "runs",
        "jobs",
        "verify",
        "repo",
    ]


def test_branch_moved_before_collection_is_rejected():
    moved = BranchVerification("owner/repo", "agent/x", B, C, "moved")
    client = FakeGitHub(verify_results=[moved])
    with pytest.raises(EvidenceCollectionError) as info:
        collect(client)
    assert info.value.code == "branch_moved"
    assert client.calls == [
        ("repo", "owner/repo"),
        ("verify", "owner/repo", "agent/x", B),
    ]


def test_branch_moved_during_collection_is_rejected():
    moved = BranchVerification("owner/repo", "agent/x", B, C, "moved")
    client = FakeGitHub(verify_results=[unchanged(), moved])
    with pytest.raises(EvidenceCollectionError) as info:
        collect(client)
    assert info.value.code == "branch_moved"
    assert [call[0] for call in client.calls] == [
        "repo",
        "verify",
        "compare",
        "runs",
        "jobs",
        "verify",
    ]


def test_malformed_requested_sha_is_rejected():
    client = FakeGitHub(verify_results=[ValueError("bad sha")])
    with pytest.raises(EvidenceCollectionError) as info:
        collect(client, head_sha="not-a-sha")
    assert info.value.code == "invalid_branch_or_sha"
    assert client.calls == [
        ("repo", "owner/repo"),
        ("verify", "owner/repo", "agent/x", "not-a-sha"),
    ]


def test_compare_result_sha_mismatch_is_rejected():
    client = FakeGitHub(compare_result=compare(head_sha=C))
    with pytest.raises(EvidenceCollectionError) as info:
        collect(client)
    assert info.value.code == "compare_membership_mismatch"
    assert [call[0] for call in client.calls] == ["repo", "verify", "compare"]


def test_workflow_run_sha_mismatch_is_rejected():
    client = FakeGitHub(runs_result=runs(head_sha=C))
    with pytest.raises(EvidenceCollectionError) as info:
        collect(client)
    assert info.value.code == "ci_sha_mismatch"


def test_branch_verification_failure_is_explicit():
    client = FakeGitHub(verify_results=[GitHubTransportError("verify failed")])
    with pytest.raises(EvidenceCollectionError) as info:
        collect(client)
    assert info.value.code == "GitHubTransportError"


def test_branch_response_missing_required_sha_is_rejected():
    missing = BranchVerification("owner/repo", "agent/x", B, None, "missing")
    client = FakeGitHub(verify_results=[missing])
    with pytest.raises(EvidenceCollectionError) as info:
        collect(client)
    assert info.value.code == "branch_missing"
