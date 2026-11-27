"""R7-B01: explicit conversation/repository/PR resolution and membership integrity."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from bot.db import AutoReviewMembership, Database
from bot.review.ci_contract import jobs_complete
from bot.review.collector import EvidenceCollectionError, GitHubEvidenceCollector
from bot.review.evidence import ReviewEvidence, StageEvidenceValidation
from bot.review.github import (
    BranchVerification,
    CompareResult,
    GitHubClient,
    GitHubMalformedResponse,
    GitHubRepoNotAllowed,
    GitHubTransportError,
    PullRequestIdentity,
    RepositoryIdentity,
    WorkflowJob,
    WorkflowJobsEvidence,
    WorkflowRun,
    WorkflowRunsEvidence,
)
from bot.review.resolver import (
    BRANCH_MOVED,
    COMPARE_MISMATCH,
    DUPLICATE_PR_MEMBERSHIP,
    GITHUB_UNAVAILABLE,
    INVALID_RESOLUTION_REQUEST,
    MALFORMED_EXTERNAL_RESPONSE,
    MISSING_CONVERSATION_REPOSITORY_LINK,
    PR_FORK_AMBIGUOUS,
    PR_NOT_OPEN,
    PR_REPOSITORY_MISMATCH,
    REPOSITORY_ID_MISMATCH,
    REPOSITORY_NOT_ALLOWED,
    REPOSITORY_RENAME_AMBIGUOUS,
    UNAUTHORIZED_CONVERSATION,
    ConversationMembershipResolver,
    ConversationRepositoryLink,
    MembershipResolutionError,
    ResolutionResult,
    reserve_resolved_memberships,
)
from bot.review.verdict import VERDICT_BLOCKED, evaluate_verdict

A = "a" * 40
B = "b" * 40
C = "c" * 40
REPO = "owner/repo"
REPO_ID = 101
OTHER_REPO_ID = 202
PR = 3
CHAT = 7
CONV = "conv-1"
T0 = "2026-11-25T00:00:00+00:00"


def repository(*, repository_id=REPO_ID, full_name=REPO, private=True, fork=False, archived=False):
    return RepositoryIdentity(
        repository_id=repository_id,
        full_name=full_name,
        owner_id=1,
        owner_login="owner",
        private=private,
        fork=fork,
        archived=archived,
        default_branch="main",
    )


def pull_request(
    *,
    number=PR,
    head_sha=B,
    base_sha=A,
    head_ref="agent/x",
    base_ref="main",
    head_repo_id=REPO_ID,
    head_repo_name=REPO,
    base_repo_id=REPO_ID,
    base_repo_name=REPO,
    state="open",
    merged=False,
):
    return PullRequestIdentity(
        pr_number=number,
        repository_id=base_repo_id,
        repository_full_name=base_repo_name,
        base_repository_id=base_repo_id,
        base_repository_full_name=base_repo_name,
        base_ref=base_ref,
        base_sha=base_sha,
        head_repository_id=head_repo_id,
        head_repository_full_name=head_repo_name,
        head_ref=head_ref,
        head_sha=head_sha,
        state=state,
        merged=merged,
        draft=False,
    )


def compare(
    base_sha,
    head_sha,
    *,
    repository_name=REPO,
    merge_base_sha=None,
    status="verified",
    observed_base=None,
    observed_head=None,
):
    return CompareResult(
        repository=repository_name,
        base_sha=base_sha,
        head_sha=head_sha,
        merge_base_sha=merge_base_sha if merge_base_sha is not None else base_sha,
        status=status,
        ahead_by=1,
        behind_by=0,
        files=(),
        commits=(head_sha,),
        observed_base_sha=observed_base if observed_base is not None else base_sha,
        observed_head_sha=observed_head if observed_head is not None else head_sha,
    )


def unchanged(branch="agent/x", sha=B):
    return BranchVerification(REPO, branch, sha, sha, "unchanged")


class FakeGitHub:
    def __init__(
        self,
        *,
        repository_value=None,
        pull_requests=None,
        compares=None,
        branch_results=None,
        repository_error=None,
        pull_request_error=None,
        compare_error=None,
        branch_error=None,
    ):
        self.repository_value = repository_value or repository()
        self.pull_requests = dict(pull_requests or {PR: pull_request()})
        self.compares = dict(compares or {(A, B): compare(A, B)})
        self.branch_results = list(branch_results or [unchanged(), unchanged()])
        self.repository_error = repository_error
        self.pull_request_error = pull_request_error
        self.compare_error = compare_error
        self.branch_error = branch_error
        self.calls = []

    async def get_repository(self, repository_name):
        self.calls.append(("get_repository", repository_name))
        if self.repository_error:
            raise self.repository_error
        return self.repository_value

    async def get_pull_request(self, repository_name, number):
        self.calls.append(("get_pull_request", repository_name, number))
        if self.pull_request_error:
            raise self.pull_request_error
        return self.pull_requests[number]

    async def verify_branch_sha(self, repository_name, branch, expected_sha):
        self.calls.append(("verify_branch_sha", repository_name, branch, expected_sha))
        if self.branch_error:
            raise self.branch_error
        if self.branch_results:
            return self.branch_results.pop(0)
        return unchanged(branch, expected_sha)

    async def compare(self, repository_name, base_sha, head_sha):
        self.calls.append(("compare", repository_name, base_sha, head_sha))
        if self.compare_error:
            raise self.compare_error
        result = self.compares.get((base_sha, head_sha))
        if result is None:
            return compare(base_sha, head_sha)
        return result


class FakeLinkSource:
    def __init__(self, link=None):
        self.link = link if link is not None else ConversationRepositoryLink(
            conversation_id=CONV,
            repository_id=REPO_ID,
            repository_full_name=REPO,
            source="owner_mapping",
        )
        self.calls = []

    async def resolve(self, conversation_id):
        self.calls.append(conversation_id)
        return self.link


class NoneLinkSource:
    async def resolve(self, conversation_id):
        return None


def make_db(tmp_path, *, watched=True):
    db = Database(str(tmp_path / "review.sqlite3"))
    if watched:
        db.add_watched(CONV, "review target", CHAT)
    return db


def resolver(db, github, link_source=None):
    return ConversationMembershipResolver(
        db,
        github,
        link_source or FakeLinkSource(),
        clock=lambda: T0,
    )


def resolve(db, github, *, pr_numbers=(PR,), link_source=None):
    return asyncio.run(
        resolver(db, github, link_source).resolve(
            conversation_id=CONV,
            chat_id=CHAT,
            pr_numbers=pr_numbers,
        )
    )


def assert_no_review_rows(db):
    assert db._conn.execute("SELECT COUNT(*) FROM auto_reviews").fetchone()[0] == 0


def provider_snapshot(db):
    return db.get_or_create_auto_review_provider_snapshot(
        provider="testprovider",
        api_base="https://reviewer.invalid/v1",
        model="model-a",
        config={"max_input_chars": 20000},
        now=T0,
    )


def test_valid_conversation_repository_link_resolves_exact_membership(tmp_path):
    db = make_db(tmp_path)
    github = FakeGitHub()
    result = resolve(db, github)
    assert len(result.memberships) == 1
    item = result.memberships[0]
    assert item.membership.repository_id == REPO_ID
    assert item.membership.repository_full_name == REPO
    assert item.membership.pr_number == PR
    assert item.membership.branch == "agent/x"
    assert item.membership.base_sha == A
    assert item.membership.head_sha == B
    assert item.provenance.source == "owner_mapping"
    assert item.provenance.verified_at == T0
    assert [call[0] for call in github.calls] == [
        "get_repository",
        "get_pull_request",
        "verify_branch_sha",
        "compare",
        "get_pull_request",
        "verify_branch_sha",
        "get_repository",
    ]
    assert_no_review_rows(db)


def test_missing_repository_association_fails_closed(tmp_path):
    db = make_db(tmp_path)
    github = FakeGitHub()
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github, link_source=NoneLinkSource())
    assert info.value.code == MISSING_CONVERSATION_REPOSITORY_LINK
    assert github.calls == []
    assert_no_review_rows(db)


def test_unauthorized_conversation_fails_before_github(tmp_path):
    db = make_db(tmp_path, watched=False)
    github = FakeGitHub()
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github)
    assert info.value.code == UNAUTHORIZED_CONVERSATION
    assert github.calls == []
    assert_no_review_rows(db)


def test_conversation_link_for_another_conversation_is_rejected(tmp_path):
    db = make_db(tmp_path)
    github = FakeGitHub()
    link = ConversationRepositoryLink(
        conversation_id="conv-other",
        repository_id=REPO_ID,
        repository_full_name=REPO,
        source="owner_mapping",
    )
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github, link_source=FakeLinkSource(link))
    assert info.value.code == "conversation_link_mismatch"
    assert github.calls == []
    assert_no_review_rows(db)


def test_repository_id_mismatch_fails_closed(tmp_path):
    db = make_db(tmp_path)
    github = FakeGitHub(repository_value=repository(repository_id=OTHER_REPO_ID))
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github)
    assert info.value.code == REPOSITORY_ID_MISMATCH
    assert_no_review_rows(db)


def test_repository_name_mismatch_or_rename_is_ambiguous(tmp_path):
    db = make_db(tmp_path)
    github = FakeGitHub(repository_value=repository(full_name="owner/renamed"))
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github)
    assert info.value.code == REPOSITORY_RENAME_AMBIGUOUS
    assert_no_review_rows(db)


def test_valid_multiple_prs_are_deterministically_ordered(tmp_path):
    db = make_db(tmp_path)
    github = FakeGitHub(
        pull_requests={5: pull_request(number=5, head_sha=C), PR: pull_request()},
        compares={(A, B): compare(A, B), (A, C): compare(A, C)},
        branch_results=[unchanged(), unchanged(), unchanged(), unchanged()],
    )
    result = resolve(db, github, pr_numbers=(5, PR))
    assert [item.membership.pr_number for item in result.memberships] == [PR, 5]
    assert [item.membership.head_sha for item in result.memberships] == [B, C]


def test_pr_from_another_repository_is_rejected(tmp_path):
    db = make_db(tmp_path)
    github = FakeGitHub(
        pull_requests={PR: pull_request(base_repo_id=OTHER_REPO_ID)}
    )
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github)
    assert info.value.code == PR_REPOSITORY_MISMATCH
    assert_no_review_rows(db)


def test_fork_pr_is_ambiguous(tmp_path):
    db = make_db(tmp_path)
    github = FakeGitHub(
        pull_requests={
            PR: pull_request(head_repo_id=OTHER_REPO_ID, head_repo_name="other/repo")
        }
    )
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github)
    assert info.value.code == PR_FORK_AMBIGUOUS
    assert_no_review_rows(db)


@pytest.mark.parametrize(
    "pr",
    [pull_request(state="closed"), pull_request(merged=True)],
)
def test_closed_or_merged_pr_is_rejected(tmp_path, pr):
    db = make_db(tmp_path)
    github = FakeGitHub(pull_requests={PR: pr})
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github)
    assert info.value.code == PR_NOT_OPEN
    assert_no_review_rows(db)


def test_head_branch_movement_is_rejected(tmp_path):
    db = make_db(tmp_path)
    github = FakeGitHub(
        branch_results=[BranchVerification(REPO, "agent/x", B, C, "moved")]
    )
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github)
    assert info.value.code == BRANCH_MOVED
    assert_no_review_rows(db)


def test_branch_movement_during_final_verification_is_rejected(tmp_path):
    db = make_db(tmp_path)
    github = FakeGitHub(
        branch_results=[
            unchanged(),
            BranchVerification(REPO, "agent/x", B, C, "moved"),
        ]
    )
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github)
    assert info.value.code == BRANCH_MOVED
    assert_no_review_rows(db)


def test_pr_head_sha_mismatch_in_compare_is_rejected(tmp_path):
    db = make_db(tmp_path)
    github = FakeGitHub(compares={(A, B): compare(A, B, observed_head=C)})
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github)
    assert info.value.code == COMPARE_MISMATCH
    assert_no_review_rows(db)


def test_malformed_pr_sha_is_rejected(tmp_path):
    db = make_db(tmp_path)
    github = FakeGitHub(pull_requests={PR: pull_request(head_sha="not-a-sha")})
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github)
    assert info.value.code == INVALID_RESOLUTION_REQUEST
    assert_no_review_rows(db)


def test_compare_result_from_another_repository_is_rejected(tmp_path):
    db = make_db(tmp_path)
    github = FakeGitHub(
        compares={(A, B): compare(A, B, repository_name="other/repo")}
    )
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github)
    assert info.value.code == COMPARE_MISMATCH
    assert_no_review_rows(db)


class _CollectorFake:
    def __init__(self, *, runs):
        self.runs = runs

    async def get_repository(self, repository_name):
        return repository()

    async def verify_branch_sha(self, repository_name, branch, expected_sha):
        return unchanged(branch, expected_sha)

    async def compare(self, repository_name, base_sha, head_sha):
        return compare(base_sha, head_sha)

    async def get_workflow_runs_for_sha(self, repository_name, head_sha):
        return self.runs

    async def list_run_jobs(self, repository_name, run_id, head_sha):
        return WorkflowJobsEvidence(
            repository=REPO,
            run_id=run_id,
            head_sha=head_sha,
            jobs=(),
            status="verified",
            observed_head_shas=(head_sha,),
        )


def test_workflow_run_sha_mismatch_is_rejected_after_resolution(tmp_path):
    db = make_db(tmp_path)
    result = resolve(db, FakeGitHub())
    membership = result.memberships[0].membership
    client = _CollectorFake(
        runs=WorkflowRunsEvidence(
            repository=REPO,
            head_sha=C,
            runs=(
                WorkflowRun(
                    run_id=1,
                    name="Verify agent branch",
                    head_sha=C,
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
            observed_head_shas=(C,),
            ci_state="success",
        )
    )
    with pytest.raises(EvidenceCollectionError) as info:
        asyncio.run(
            GitHubEvidenceCollector(client).collect(
                membership,
                architecture_decisions=(),
                max_input_chars=20_000,
            )
        )
    assert info.value.code == "ci_sha_mismatch"


def test_incomplete_ci_jobs_cannot_reach_pass_after_resolution(tmp_path):
    db = make_db(tmp_path)
    result = resolve(db, FakeGitHub())
    membership = result.memberships[0].membership
    runs = WorkflowRunsEvidence(
        repository=REPO,
        head_sha=B,
        runs=(
            WorkflowRun(
                run_id=1,
                name="Verify agent branch",
                head_sha=B,
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
        observed_head_shas=(B,),
        ci_state="success",
    )
    jobs = WorkflowJobsEvidence(
        repository=REPO,
        run_id=1,
        head_sha=B,
        jobs=(
            WorkflowJob(
                job_id=1,
                run_id=1,
                name="Validate requested SHA",
                head_sha=B,
                status="completed",
                conclusion="success",
                started_at=None,
                completed_at=None,
            ),
        ),
        status="verified",
        observed_head_shas=(B,),
    )
    evidence = ReviewEvidence.from_compare(
        compare(A, B),
        diff_text="",
        max_input_chars=20_000,
        branch=membership.branch,
        pr_number=membership.pr_number,
        ci_runs=runs,
        ci_jobs=(jobs,),
        ci_jobs_complete=jobs_complete(runs, (jobs,)),
    )
    validation = StageEvidenceValidation(
        stage="blind",
        accepted=(),
        rejected=(),
        reviewed_files=(),
        evidence_gaps=(),
        sha_status="verified",
        coverage_complete=True,
        stage_valid=True,
    )
    verdict = evaluate_verdict(
        evidence=evidence,
        blind_validation=validation,
        adversarial_validation=validation,
        blind_stage_ok=True,
        adversarial_stage_ok=True,
        blind_assessment="clean",
        adversarial_assessment="concur",
    )
    assert verdict.verdict == VERDICT_BLOCKED
    assert verdict.rule == "R4-CI-03"


def test_duplicate_pr_membership_is_rejected(tmp_path):
    db = make_db(tmp_path)
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, FakeGitHub(), pr_numbers=(PR, PR))
    assert info.value.code == DUPLICATE_PR_MEMBERSHIP
    assert_no_review_rows(db)


def test_conflicting_membership_does_not_mutate_active_cycle(tmp_path):
    db = make_db(tmp_path)
    first = resolve(db, FakeGitHub())
    snap = provider_snapshot(db)
    reserved = reserve_resolved_memberships(
        db, first, provider_snapshot_id=snap.id, reserved_by="test", now=T0
    )
    assert reserved.outcome == "newly_reserved"
    changed = resolve(
        db,
        FakeGitHub(
            pull_requests={PR: pull_request(head_sha=C)},
            compares={(A, C): compare(A, C)},
        ),
    )
    second = reserve_resolved_memberships(
        db, changed, provider_snapshot_id=snap.id, reserved_by="test", now=T0
    )
    assert second.outcome == "conflicting_identity"
    assert db.get_auto_review_memberships(reserved.review_id)[0].head_sha == B


def test_empty_resolution_result_never_partially_inserts(tmp_path):
    db = make_db(tmp_path)
    snap = provider_snapshot(db)
    result = reserve_resolved_memberships(
        db,
        ResolutionResult(conversation_id=CONV, chat_id=CHAT, memberships=()),
        provider_snapshot_id=snap.id,
        reserved_by="test",
        now=T0,
    )
    assert result.outcome == "invalid_input"
    assert_no_review_rows(db)


def test_repeated_resolution_is_idempotent(tmp_path):
    db = make_db(tmp_path)
    github = FakeGitHub()
    first = resolve(db, github)
    second = resolve(db, github)
    assert first == second
    snap = provider_snapshot(db)
    one = reserve_resolved_memberships(
        db, first, provider_snapshot_id=snap.id, reserved_by="test", now=T0
    )
    two = reserve_resolved_memberships(
        db, second, provider_snapshot_id=snap.id, reserved_by="test", now=T0
    )
    assert one.outcome == "newly_reserved"
    assert two.outcome == "already_reserved"


def test_new_pr_after_cycle_reservation_is_pending_not_mutating(tmp_path):
    db = make_db(tmp_path)
    first = resolve(db, FakeGitHub())
    snap = provider_snapshot(db)
    reserved = reserve_resolved_memberships(
        db, first, provider_snapshot_id=snap.id, reserved_by="test", now=T0
    )
    observation = db.observe_auto_review_membership(
        conversation_id=CONV,
        membership=AutoReviewMembership(
            repository_id=REPO_ID,
            repository_full_name=REPO,
            pr_number=5,
            branch="agent/y",
            base_sha=A,
            head_sha=C,
        ),
        now=T0,
    )
    assert observation.outcome == "deferred_active_cycle"
    memberships = db.get_auto_review_memberships(reserved.review_id)
    assert len(memberships) == 1
    assert memberships[0].pr_number == PR


def test_process_restart_recovery_returns_same_membership(tmp_path):
    db = make_db(tmp_path)
    first = resolve(db, FakeGitHub())
    second = resolve(db, FakeGitHub())
    assert first == second
    assert first.memberships[0].provenance.verified_at == T0


def test_api_unavailable_is_explicit(tmp_path):
    db = make_db(tmp_path)
    github = FakeGitHub(repository_error=GitHubTransportError("timeout"))
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github)
    assert info.value.code == GITHUB_UNAVAILABLE
    assert info.value.retryable is True
    assert_no_review_rows(db)


def test_malformed_external_response_is_explicit(tmp_path):
    db = make_db(tmp_path)
    github = FakeGitHub(repository_value={"not": "identity"})
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github)
    assert info.value.code == MALFORMED_EXTERNAL_RESPONSE
    assert_no_review_rows(db)


def test_user_controlled_repository_claim_cannot_bypass_allowlist(tmp_path):
    db = make_db(tmp_path)
    github = FakeGitHub(repository_error=GitHubRepoNotAllowed("not allowlisted"))
    link = ConversationRepositoryLink(
        conversation_id=CONV,
        repository_id=REPO_ID,
        repository_full_name="evil/repo",
        source="user_supplied",
    )
    with pytest.raises(MembershipResolutionError) as info:
        resolve(db, github, link_source=FakeLinkSource(link))
    assert info.value.code == REPOSITORY_NOT_ALLOWED
    assert_no_review_rows(db)


# ------------------------------------------------------------ GitHub parsing
TOKEN = "ghp_FAKE_RESOLVER_TOKEN_1234567890"


def _github_run(handler, method, *args):
    async def runner():
        async with GitHubClient(
            TOKEN,
            allowed_repositories={REPO},
            transport=httpx.MockTransport(handler),
        ) as client:
            return await getattr(client, method)(*args)

    return asyncio.run(runner())


def _repo_payload():
    return {
        "id": REPO_ID,
        "full_name": REPO,
        "owner": {"id": 1, "login": "owner"},
        "private": True,
        "fork": False,
        "archived": False,
        "default_branch": "main",
    }


def _pr_payload():
    return {
        "number": PR,
        "state": "open",
        "merged": False,
        "draft": False,
        "base": {
            "ref": "main",
            "sha": A,
            "repo": {"id": REPO_ID, "full_name": REPO},
        },
        "head": {
            "ref": "agent/x",
            "sha": B,
            "repo": {"id": REPO_ID, "full_name": REPO},
        },
    }


def test_github_repository_parser_returns_immutable_identity():
    def handler(request):
        assert request.url.path == "/repos/owner/repo"
        return httpx.Response(200, json=_repo_payload())

    identity = _github_run(handler, "get_repository", REPO)
    assert identity.repository_id == REPO_ID
    assert identity.full_name == REPO
    assert identity.default_branch == "main"


def test_github_pull_request_parser_binds_base_and_head():
    def handler(request):
        assert request.url.path == "/repos/owner/repo/pulls/3"
        return httpx.Response(200, json=_pr_payload())

    pr = _github_run(handler, "get_pull_request", REPO, PR)
    assert pr.pr_number == PR
    assert pr.base_repository_id == REPO_ID
    assert pr.head_repository_id == REPO_ID
    assert pr.head_ref == "agent/x"
    assert pr.head_sha == B


def test_github_pull_request_missing_head_repo_is_malformed():
    payload = _pr_payload()
    payload["head"]["repo"] = None

    def handler(request):
        return httpx.Response(200, json=payload)

    with pytest.raises(GitHubMalformedResponse):
        _github_run(handler, "get_pull_request", REPO, PR)


def test_github_pull_request_number_mismatch_is_malformed():
    payload = _pr_payload()
    payload["number"] = 99

    def handler(request):
        return httpx.Response(200, json=payload)

    with pytest.raises(GitHubMalformedResponse):
        _github_run(handler, "get_pull_request", REPO, PR)


def test_github_repository_missing_id_is_malformed():
    payload = _repo_payload()
    payload.pop("id")

    def handler(request):
        return httpx.Response(200, json=payload)

    with pytest.raises(GitHubMalformedResponse):
        _github_run(handler, "get_repository", REPO)
