"""D-05: reject repository rename, transfer, and redirect substitution.

All tests are local and deterministic. The HTTP tests use ``httpx.MockTransport``;
the resolver tests use an isolated temporary SQLite database and fake GitHub client.
No external API call or credential is used.
"""
from __future__ import annotations

import asyncio

import httpx
import pytest

from bot.review.github import (
    GitHubClient,
    GitHubMalformedResponse,
    GitHubNotFoundError,
    GitHubRedirectError,
    GitHubRepositoryIdentityMismatch,
    GitHubServerError,
)
from bot.review.resolver import (
    GITHUB_UNAVAILABLE,
    MALFORMED_EXTERNAL_RESPONSE,
    PR_REPOSITORY_MISMATCH,
    REPOSITORY_ID_MISMATCH,
    REPOSITORY_REDIRECT_REJECTED,
    REPOSITORY_RENAME_AMBIGUOUS,
    ConversationMembershipResolver,
    MembershipResolutionError,
)
from tests.test_review_resolver import (
    CHAT,
    CONV,
    OTHER_REPO_ID,
    PR,
    REPO,
    REPO_ID,
    T0,
    FakeGitHub,
    FakeLinkSource,
    assert_no_review_rows,
    make_db,
    pull_request,
    repository,
    resolve,
)

TOKEN = "ghp_FAKE_D05_TOKEN_1234567890"


def _run_client(handler, method, *args):
    async def runner():
        async with GitHubClient(
            TOKEN,
            allowed_repositories={REPO},
            transport=httpx.MockTransport(handler),
        ) as client:
            return await getattr(client, method)(*args)

    return asyncio.run(runner())


def _repo_payload(*, full_name=REPO):
    return {
        "id": REPO_ID,
        "full_name": full_name,
        "owner": {"id": 1, "login": "owner"},
        "private": True,
        "fork": False,
        "archived": False,
        "default_branch": "main",
    }


# --------------------------------------------------------------- HTTP boundary
def test_exact_canonical_full_name_is_accepted_case_insensitively():
    def handler(request):
        assert request.url.path == "/repos/owner/repo"
        return httpx.Response(200, json=_repo_payload(full_name="Owner/Repo"))

    identity = _run_client(handler, "get_repository", REPO)
    assert identity.repository_id == REPO_ID
    assert identity.full_name == "Owner/Repo"


def test_different_repository_full_name_is_rejected():
    def handler(request):
        return httpx.Response(200, json=_repo_payload(full_name="owner/renamed"))

    with pytest.raises(GitHubRepositoryIdentityMismatch) as exc:
        _run_client(handler, "get_repository", REPO)
    assert "renamed" not in str(exc.value)


def test_repository_rename_and_transfer_are_both_rejected():
    for name in ("newowner/repo", "owner/renamed", "newowner/renamed"):
        def handler(request, name=name):
            return httpx.Response(200, json=_repo_payload(full_name=name))

        with pytest.raises(GitHubRepositoryIdentityMismatch):
            _run_client(handler, "get_repository", REPO)


def test_missing_or_malformed_repository_identity_is_rejected():
    for payload in ({}, {"id": REPO_ID}, {"id": REPO_ID, "full_name": "not-a-repo"}):
        def handler(request, payload=payload):
            return httpx.Response(200, json=payload)

        with pytest.raises(GitHubMalformedResponse):
            _run_client(handler, "get_repository", REPO)


@pytest.mark.parametrize("code", [301, 302, 303, 307, 308])
def test_old_name_redirect_is_rejected(code):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(
            code, headers={"location": "https://api.github.com/repos/newowner/repo"}
        )

    with pytest.raises(GitHubRedirectError) as exc:
        _run_client(handler, "get_repository", REPO)
    assert exc.value.status_code == code
    assert len(calls) == 1


def test_redirect_chain_cannot_bypass_validation():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        if len(calls) == 1:
            return httpx.Response(
                302, headers={"location": "https://api.github.com/repos/owner/repo2"}
            )
        return httpx.Response(200, json=_repo_payload(full_name="owner/repo2"))

    with pytest.raises(GitHubRedirectError):
        _run_client(handler, "get_repository", REPO)
    assert len(calls) == 1


def test_pull_request_redirect_is_rejected():
    def handler(request):
        return httpx.Response(
            301, headers={"location": "https://api.github.com/repos/newowner/repo/pulls/3"}
        )

    with pytest.raises(GitHubRedirectError):
        _run_client(handler, "get_pull_request", REPO, PR)


def test_redirect_without_location_is_rejected_safely():
    def handler(request):
        return httpx.Response(302)

    with pytest.raises(GitHubRedirectError):
        _run_client(handler, "get_repository", REPO)


@pytest.mark.parametrize("code, expected", [(404, GitHubNotFoundError), (500, GitHubServerError)])
def test_repository_api_errors_fail_closed(code, expected):
    def handler(request):
        return httpx.Response(code, json={"message": "SECRET-BODY"})

    with pytest.raises(expected) as exc:
        _run_client(handler, "get_repository", REPO)
    assert "SECRET-BODY" not in str(exc.value)


# -------------------------------------------------------- resolver revalidation
class SequenceGitHub(FakeGitHub):
    def __init__(self, *, repo_results, pr_results=None):
        super().__init__()
        self._repo_results = list(repo_results)
        self._pr_results = list(pr_results or [])

    async def get_repository(self, repository_name):
        self.calls.append(("get_repository", repository_name))
        value = self._repo_results.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    async def get_pull_request(self, repository_name, number):
        if self._pr_results:
            self.calls.append(("get_pull_request", repository_name, number))
            value = self._pr_results.pop(0)
            if isinstance(value, Exception):
                raise value
            return value
        return await super().get_pull_request(repository_name, number)


def test_repository_rename_after_pr_reads_is_rejected(tmp_path):
    db = make_db(tmp_path)
    github = SequenceGitHub(
        repo_results=[repository(), repository(full_name="owner/renamed")]
    )
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github)
    assert info.value.code == REPOSITORY_RENAME_AMBIGUOUS
    assert_no_review_rows(db)


def test_repository_transfer_after_pr_reads_is_rejected(tmp_path):
    db = make_db(tmp_path)
    github = SequenceGitHub(
        repo_results=[repository(), repository(full_name="newowner/repo")]
    )
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github)
    assert info.value.code == REPOSITORY_RENAME_AMBIGUOUS
    assert_no_review_rows(db)


def test_repository_id_change_after_pr_reads_is_rejected(tmp_path):
    db = make_db(tmp_path)
    github = SequenceGitHub(
        repo_results=[repository(), repository(repository_id=OTHER_REPO_ID)]
    )
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github)
    assert info.value.code == REPOSITORY_ID_MISMATCH
    assert_no_review_rows(db)


def test_redirect_during_resolution_maps_to_explicit_reason(tmp_path):
    db = make_db(tmp_path)
    github = SequenceGitHub(
        repo_results=[
            repository(),
            GitHubRedirectError("redirect", status_code=302),
        ]
    )
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github)
    assert info.value.code == REPOSITORY_REDIRECT_REJECTED
    assert_no_review_rows(db)


def test_identity_mismatch_from_client_maps_to_rename_reason(tmp_path):
    db = make_db(tmp_path)
    github = SequenceGitHub(
        repo_results=[GitHubRepositoryIdentityMismatch("changed")]
    )
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github)
    assert info.value.code == REPOSITORY_RENAME_AMBIGUOUS
    assert_no_review_rows(db)


def test_pull_request_repository_change_after_first_read_is_rejected(tmp_path):
    db = make_db(tmp_path)
    github = SequenceGitHub(
        repo_results=[repository(), repository()],
        pr_results=[
            pull_request(),
            pull_request(base_repo_id=OTHER_REPO_ID, base_repo_name="other/repo"),
        ],
    )
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github)
    assert info.value.code == PR_REPOSITORY_MISMATCH
    assert_no_review_rows(db)


def test_api_error_after_pr_reads_fails_closed(tmp_path):
    db = make_db(tmp_path)
    github = SequenceGitHub(
        repo_results=[repository(), GitHubServerError("temporary")]
    )
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github)
    assert info.value.code == GITHUB_UNAVAILABLE
    assert info.value.retryable is True
    assert_no_review_rows(db)


def test_malformed_identity_after_pr_reads_fails_closed(tmp_path):
    db = make_db(tmp_path)
    github = SequenceGitHub(repo_results=[repository(), None])
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github)
    assert info.value.code == MALFORMED_EXTERNAL_RESPONSE
    assert_no_review_rows(db)


def test_real_client_redirect_maps_to_redirect_reason(tmp_path):
    db = make_db(tmp_path)

    def handler(request):
        return httpx.Response(
            302, headers={"location": "https://api.github.com/repos/newowner/repo"}
        )

    async def runner():
        async with GitHubClient(
            TOKEN,
            allowed_repositories={REPO},
            transport=httpx.MockTransport(handler),
        ) as client:
            resolver = ConversationMembershipResolver(
                db, client, FakeLinkSource(), clock=lambda: T0
            )
            return await resolver.resolve(
                conversation_id=CONV, chat_id=CHAT, pr_numbers=(PR,)
            )

    with pytest.raises(MembershipResolutionError) as info:
        asyncio.run(runner())
    assert info.value.code == REPOSITORY_REDIRECT_REJECTED
    assert_no_review_rows(db)
