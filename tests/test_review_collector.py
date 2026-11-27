"""R5: R3 evidence collection stays read-only and SHA-bound."""

from __future__ import annotations

import asyncio

import pytest

from bot.db import AutoReviewMembership
from bot.review.collector import EvidenceCollectionError, GitHubEvidenceCollector
from bot.review.evidence import ReviewEvidence, diff_text_from_compare
from bot.review.github import (
    BranchVerification,
    ChangedFile,
    CompareResult,
    RepositoryIdentity,
    WorkflowJob,
    WorkflowJobsEvidence,
    WorkflowRun,
    WorkflowRunsEvidence,
)

BASE = "a" * 40
HEAD = "b" * 40


def membership():
    return AutoReviewMembership(1, "owner/repo", 3, "agent/x", BASE, HEAD)


def compare(status="verified"):
    return CompareResult(
        repository="owner/repo",
        base_sha=BASE,
        head_sha=HEAD,
        merge_base_sha=BASE,
        status=status,
        ahead_by=1,
        behind_by=0,
        files=(
            ChangedFile(
                filename="src/x.py",
                status="modified",
                additions=1,
                deletions=1,
                changes=2,
                patch="@@ -1 +1 @@\n-old\n+new\n",
            ),
        )
        if status == "verified"
        else (),
        commits=(HEAD,),
        observed_base_sha=BASE,
        observed_head_sha=HEAD,
    )


def runs():
    return WorkflowRunsEvidence(
        repository="owner/repo",
        head_sha=HEAD,
        runs=(
            WorkflowRun(
                run_id=7,
                name="verify",
                head_sha=HEAD,
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
        observed_head_shas=(HEAD,),
        ci_state="success",
    )


def jobs():
    return WorkflowJobsEvidence(
        repository="owner/repo",
        run_id=7,
        head_sha=HEAD,
        jobs=(
            WorkflowJob(
                job_id=1,
                run_id=7,
                name="pytest",
                head_sha=HEAD,
                status="completed",
                conclusion="success",
                started_at=None,
                completed_at=None,
            ),
        ),
        status="verified",
        observed_head_shas=(HEAD,),
    )


class FakeGitHub:
    def __init__(self, compare_result=None, verify_results=None):
        self.compare_result = compare_result or compare()
        unchanged = BranchVerification(
            repository="owner/repo",
            branch="agent/x",
            expected_sha=HEAD,
            observed_sha=HEAD,
            status="unchanged",
        )
        self.verify_results = list(verify_results or [unchanged, unchanged])
        self.calls = []

    async def get_repository(self, repository):
        self.calls.append(("repo", repository))
        return RepositoryIdentity(1, "owner/repo", 1, "owner", True, False, False, "main")

    async def verify_branch_sha(self, repository, branch, expected_sha):
        self.calls.append(("verify", repository, branch, expected_sha))
        return self.verify_results.pop(0)

    async def compare(self, repository, base_sha, head_sha):
        self.calls.append(("compare", repository, base_sha, head_sha))
        return self.compare_result

    async def get_workflow_runs_for_sha(self, repository, head_sha):
        self.calls.append(("runs", repository, head_sha))
        return runs()

    async def list_run_jobs(self, repository, run_id, head_sha):
        self.calls.append(("jobs", repository, run_id, head_sha))
        return jobs()


def test_collector_binds_exact_compare_and_actions_evidence():
    client = FakeGitHub()
    result = asyncio.run(
        GitHubEvidenceCollector(client).collect(
            membership(), architecture_decisions=("D1",), max_input_chars=20_000
        )
    )
    assert isinstance(result, ReviewEvidence)
    assert result.repository == "owner/repo"
    assert result.pr_number == 3
    assert result.base_sha == BASE
    assert result.head_sha == HEAD
    assert result.branch == "agent/x"
    assert result.ci_state == "success"
    assert result.coverage_complete is True
    assert "diff --git a/src/x.py b/src/x.py" in result.diff_text
    assert result.fingerprint == result.fingerprint
    assert client.calls == [
        ("repo", "owner/repo"),
        ("verify", "owner/repo", "agent/x", HEAD),
        ("compare", "owner/repo", BASE, HEAD),
        ("runs", "owner/repo", HEAD),
        ("jobs", "owner/repo", 7, HEAD),
        ("verify", "owner/repo", "agent/x", HEAD),
        ("repo", "owner/repo"),
    ]


def test_collector_fails_closed_for_unverified_compare():
    client = FakeGitHub(compare("head_sha_mismatch"))
    with pytest.raises(EvidenceCollectionError) as info:
        asyncio.run(
            GitHubEvidenceCollector(client).collect(
                membership(), architecture_decisions=(), max_input_chars=20_000
            )
        )
    assert info.value.code == "compare_head_sha_mismatch"


def test_diff_helper_rejects_unverified_compare():
    with pytest.raises(Exception):
        diff_text_from_compare(compare("head_sha_mismatch"))
