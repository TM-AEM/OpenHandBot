"""D-06: private, explicitly allowlisted repository eligibility.

Deterministic local tests only: an isolated SQLite database, fake GitHub clients,
and ``httpx.MockTransport`` for allowlist/HTTP checks. No live API call is made.
"""
from __future__ import annotations

import asyncio

import httpx
import pytest

from bot.db import AutoReviewMembership
from bot.review.collector import EvidenceCollectionError, GitHubEvidenceCollector
from bot.review.eligibility import (
    REPOSITORY_ARCHIVED,
    REPOSITORY_IS_FORK,
    REPOSITORY_NOT_PRIVATE,
)
from bot.review.github import (
    GitHubClient,
    GitHubForbiddenError,
    GitHubNotFoundError,
    GitHubRepoNotAllowed,
    GitHubServerError,
)
from bot.review.resolver import (
    GITHUB_UNAVAILABLE,
    GITHUB_UNAUTHORIZED,
    MALFORMED_EXTERNAL_RESPONSE,
    REPOSITORY_NOT_FOUND,
    MembershipResolutionError,
)
from tests.test_review_branch_sha import (
    compare as branch_compare,
    jobs as branch_jobs,
    runs as branch_runs,
    unchanged as branch_unchanged,
)
from tests.test_review_resolver import (
    OTHER_REPO_ID,
    PR,
    REPO,
    REPO_ID,
    FakeGitHub,
    assert_no_review_rows,
    make_db,
    repository,
    resolve,
)

TOKEN = "ghp_FAKE_D06_TOKEN_1234567890"


def _repo_payload(*, private=True, fork=False, archived=False):
    return {
        "id": REPO_ID,
        "full_name": REPO,
        "owner": {"id": 1, "login": "owner"},
        "private": private,
        "fork": fork,
        "archived": archived,
        "default_branch": "main",
    }


def _run_client(handler, method, *args, allowed=None):
    async def runner():
        async with GitHubClient(
            TOKEN,
            allowed_repositories={REPO} if allowed is None else allowed,
            transport=httpx.MockTransport(handler),
        ) as client:
            return await getattr(client, method)(*args)

    return asyncio.run(runner())


# ------------------------------------------------------------------ allowlist
def test_exact_allowlisted_private_repository_is_recognized():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, json=_repo_payload())

    identity = _run_client(handler, "get_repository", REPO)
    assert identity.private is True
    assert identity.fork is False
    assert identity.archived is False
    assert len(calls) == 1


def test_non_allowlisted_repository_is_rejected_before_http():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, json=_repo_payload())

    with pytest.raises(GitHubRepoNotAllowed):
        _run_client(handler, "get_repository", "other/repo")
    assert calls == []


def test_empty_allowlist_fails_closed():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, json=_repo_payload())

    with pytest.raises(GitHubRepoNotAllowed):
        _run_client(handler, "get_repository", REPO, allowed=())
    assert calls == []


def test_duplicate_normalized_allowlist_entries_are_rejected():
    with pytest.raises(ValueError):
        GitHubClient(
            TOKEN, allowed_repositories=["Owner/Repo", "owner/repo"]
        )


def test_prefix_and_wildcard_allowlist_entries_do_not_broaden_eligibility():
    with pytest.raises(ValueError):
        GitHubClient(TOKEN, allowed_repositories={"owner/*"})
    with pytest.raises(GitHubRepoNotAllowed):
        _run_client(
            lambda request: httpx.Response(200, json=_repo_payload()),
            "get_repository",
            "owner/repo2",
        )


def test_allowlist_normalization_is_exact_and_case_insensitive():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, json=_repo_payload())

    identity = _run_client(handler, "get_repository", "OWNER/REPO")
    assert identity.full_name == REPO
    assert calls == ["https://api.github.com/repos/owner/repo"]


# ------------------------------------------------------- visibility and state
def test_public_allowlisted_repository_is_rejected(tmp_path):
    db = make_db(tmp_path)
    github = FakeGitHub(repository_value=repository(private=False))
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github)
    assert info.value.code == REPOSITORY_NOT_PRIVATE
    assert_no_review_rows(db)


def test_missing_visibility_is_rejected(tmp_path):
    db = make_db(tmp_path)
    github = FakeGitHub(repository_value=repository(private=None))
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github)
    assert info.value.code == REPOSITORY_NOT_PRIVATE
    assert_no_review_rows(db)


def test_private_fork_is_rejected(tmp_path):
    db = make_db(tmp_path)
    github = FakeGitHub(repository_value=repository(private=True, fork=True))
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github)
    assert info.value.code == REPOSITORY_IS_FORK
    assert_no_review_rows(db)


def test_private_archived_repository_is_rejected(tmp_path):
    db = make_db(tmp_path)
    github = FakeGitHub(repository_value=repository(private=True, archived=True))
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github)
    assert info.value.code == REPOSITORY_ARCHIVED
    assert_no_review_rows(db)


@pytest.mark.parametrize(
    "error, code",
    [
        (GitHubNotFoundError("missing"), REPOSITORY_NOT_FOUND),
        (GitHubForbiddenError("forbidden"), GITHUB_UNAUTHORIZED),
        (GitHubServerError("server"), GITHUB_UNAVAILABLE),
    ],
)
def test_repository_api_errors_fail_closed(tmp_path, error, code):
    db = make_db(tmp_path)
    github = FakeGitHub(repository_error=error)
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github)
    assert info.value.code == code
    assert_no_review_rows(db)


def test_malformed_repository_metadata_is_rejected(tmp_path):
    db = make_db(tmp_path)
    github = FakeGitHub(repository_value={"not": "identity"})
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github)
    assert info.value.code == MALFORMED_EXTERNAL_RESPONSE
    assert_no_review_rows(db)


# ------------------------------------------------------- PR association
def test_private_allowlisted_repository_and_pr_resolve(tmp_path):
    db = make_db(tmp_path)
    result = resolve(db, FakeGitHub())
    assert result.memberships[0].membership.repository_id == REPO_ID
    assert result.memberships[0].membership.pr_number == PR
    assert_no_review_rows(db)


def test_cross_repository_pr_is_rejected(tmp_path):
    db = make_db(tmp_path)
    from tests.test_review_resolver import pull_request

    github = FakeGitHub(
        pull_requests={PR: pull_request(base_repo_id=OTHER_REPO_ID)}
    )
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github)
    assert info.value.code == "pr_repository_mismatch"
    assert_no_review_rows(db)


def test_fork_pr_is_rejected(tmp_path):
    db = make_db(tmp_path)
    from tests.test_review_resolver import pull_request

    github = FakeGitHub(
        pull_requests={
            PR: pull_request(
                head_repo_id=OTHER_REPO_ID,
                head_repo_name="other/repo",
            )
        }
    )
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github)
    assert info.value.code == "pr_fork_ambiguous"
    assert_no_review_rows(db)


# ------------------------------------------------------- revalidation boundary
class SequenceGitHub(FakeGitHub):
    def __init__(self, *, repository_values):
        super().__init__()
        self._repository_values = list(repository_values)

    async def get_repository(self, repository_name):
        self.calls.append(("get_repository", repository_name))
        value = self._repository_values.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


@pytest.mark.parametrize(
    "final, code",
    [
        (repository(private=False), REPOSITORY_NOT_PRIVATE),
        (repository(fork=True), REPOSITORY_IS_FORK),
        (repository(archived=True), REPOSITORY_ARCHIVED),
    ],
)
def test_eligibility_change_after_pr_reads_is_rejected(tmp_path, final, code):
    db = make_db(tmp_path)
    github = SequenceGitHub(repository_values=[repository(), final])
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github)
    assert info.value.code == code
    assert_no_review_rows(db)


def test_collector_revalidates_eligibility_before_evidence():
    class PublicClient:
        async def get_repository(self, repository_name):
            return repository(private=False)

    membership = AutoReviewMembership(REPO_ID, REPO, PR, "agent/x", "a" * 40, "b" * 40)
    with pytest.raises(EvidenceCollectionError) as info:
        asyncio.run(
            GitHubEvidenceCollector(PublicClient()).collect(
                membership,
                architecture_decisions=(),
                max_input_chars=20_000,
            )
        )
    assert info.value.code == REPOSITORY_NOT_PRIVATE


def test_collector_rejects_missing_repository_identity():
    class MissingClient:
        async def get_repository(self, repository_name):
            return None

    membership = AutoReviewMembership(REPO_ID, REPO, PR, "agent/x", "a" * 40, "b" * 40)
    with pytest.raises(EvidenceCollectionError) as info:
        asyncio.run(
            GitHubEvidenceCollector(MissingClient()).collect(
                membership,
                architecture_decisions=(),
                max_input_chars=20_000,
            )
        )
    assert info.value.code == "malformed_repository_identity"


def test_collector_revalidates_eligibility_after_evidence():
    class SequenceClient:
        def __init__(self):
            self.repo_results = [repository(), repository(private=False)]

        async def get_repository(self, repository_name):
            return self.repo_results.pop(0)

        async def verify_branch_sha(self, repository_name, branch, expected_sha):
            return branch_unchanged()

        async def compare(self, repository_name, base_sha, head_sha):
            return branch_compare()

        async def get_workflow_runs_for_sha(self, repository_name, head_sha):
            return branch_runs()

        async def list_run_jobs(self, repository_name, run_id, head_sha):
            return branch_jobs(run_id=run_id, head_sha=head_sha)

    membership = AutoReviewMembership(
        REPO_ID, REPO, PR, "agent/x", "a" * 40, "b" * 40
    )
    with pytest.raises(EvidenceCollectionError) as info:
        asyncio.run(
            GitHubEvidenceCollector(SequenceClient()).collect(
                membership,
                architecture_decisions=(),
                max_input_chars=20_000,
            )
        )
    assert info.value.code == REPOSITORY_NOT_PRIVATE
