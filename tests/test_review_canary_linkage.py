"""R7 canary D-01 B / D-02 explicit-list linkage tests (mocked, isolated DB)."""

from __future__ import annotations

import asyncio
import sqlite3
import threading

import pytest

from bot.db import Database
from bot.review.canary_linkage import (
    CANARY_SOURCE,
    CreationJobRepositoryLinkSource,
    CanaryLinkageService,
)
from bot.review.github import (
    BranchVerification,
    GitHubTransportError,
)
from bot.review.resolver import (
    BRANCH_MOVED,
    COMPARE_MISMATCH,
    CONVERSATION_LINK_UNAVAILABLE,
    DUPLICATE_PR_MEMBERSHIP,
    INVALID_RESOLUTION_REQUEST,
    MALFORMED_EXTERNAL_RESPONSE,
    MISSING_CONVERSATION_REPOSITORY_LINK,
    PR_NOT_OPEN,
    PR_REPOSITORY_MISMATCH,
    REPOSITORY_ID_MISMATCH,
    UNAUTHORIZED_CONVERSATION,
    ConversationMembershipResolver,
    MembershipResolutionError,
)
from tests.test_review_resolver import (
    A,
    B,
    C,
    CHAT,
    CONV,
    OTHER_REPO_ID,
    PR,
    REPO,
    REPO_ID,
    T0,
    compare,
    pull_request,
    repository,
    unchanged,
)

OTHER_CONV = "conv-other"


class FakeGitHub:
    def __init__(
        self,
        *,
        repository_values=None,
        repository_error=None,
        pull_requests=None,
        compares=None,
        branch_results=None,
        pull_request_error=None,
    ):
        self.repository_values = list(repository_values or [])
        self.repository_error = repository_error
        self.pull_requests = dict(
            pull_requests if pull_requests is not None else {PR: pull_request()}
        )
        self.compares = dict(compares or {(A, B): compare(A, B)})
        self.branch_results = list(branch_results or [])
        self.pull_request_error = pull_request_error
        self.calls = []

    async def get_repository(self, repository_name):
        self.calls.append(("get_repository", repository_name))
        if self.repository_error is not None:
            raise self.repository_error
        if self.repository_values:
            value = self.repository_values.pop(0)
            if isinstance(value, Exception):
                raise value
            return value
        return repository()

    async def get_pull_request(self, repository_name, number):
        self.calls.append(("get_pull_request", repository_name, number))
        if self.pull_request_error is not None:
            raise self.pull_request_error
        return self.pull_requests.get(number)

    async def verify_branch_sha(self, repository_name, branch, expected_sha):
        self.calls.append(("verify_branch_sha", repository_name, branch, expected_sha))
        if self.branch_results:
            return self.branch_results.pop(0)
        return unchanged(branch, expected_sha)

    async def compare(self, repository_name, base_sha, head_sha):
        self.calls.append(("compare", repository_name, base_sha, head_sha))
        result = self.compares.get((base_sha, head_sha))
        return compare(base_sha, head_sha) if result is None else result


class FakeOpenHands:
    def __init__(self, *, conversations=None, error=None):
        self.conversations = (
            list(conversations)
            if conversations is not None
            else [{"id": CONV, "selected_repository": REPO}]
        )
        self.error = error
        self.calls = []

    async def get_conversations(self, conversation_ids):
        self.calls.append(tuple(conversation_ids))
        if self.error is not None:
            raise self.error
        return list(self.conversations)


def make_db(tmp_path, *, watched=True):
    db = Database(str(tmp_path / "canary.sqlite3"))
    if watched:
        db.add_watched(CONV, "canary target", CHAT)
    return db


def make_job(db, *, repo=REPO, conversation_id=CONV, chat_id=CHAT):
    job_id = db.add_creation_job(chat_id, repo, "task", T0)
    if conversation_id is not None:
        db.set_creation_done(job_id, T0, conversation_id)
    return job_id


def source(db, *, openhands=None, github=None):
    return CreationJobRepositoryLinkSource(
        db,
        openhands or FakeOpenHands(),
        github or FakeGitHub(),
        owner_id=CHAT,
    )


def resolver(db, *, github=None, openhands=None):
    return ConversationMembershipResolver(
        db,
        github or FakeGitHub(),
        source(db, openhands=openhands, github=github),
        clock=lambda: T0,
    )


def service(db, *, github=None, openhands=None, max_pr_candidates=20):
    return CanaryLinkageService(
        db,
        resolver(db, github=github, openhands=openhands),
        owner_id=CHAT,
        max_pr_candidates=max_pr_candidates,
    )


def snapshot(db):
    return db.get_or_create_auto_review_provider_snapshot(
        provider="testprovider",
        api_base="https://reviewer.invalid/v1",
        model="model-a",
        config={"max_input_chars": 20000},
        now=T0,
    )


def assert_no_cycles(db):
    assert db._conn.execute("SELECT COUNT(*) FROM auto_reviews").fetchone()[0] == 0


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------- D-01 B


def test_valid_bot_created_conversation_resolves_exact_membership(tmp_path):
    db = make_db(tmp_path)
    make_job(db)
    github = FakeGitHub()
    result = run(service(db, github=github).resolve(
        conversation_id=CONV, chat_id=CHAT, pr_numbers=(PR,)
    ))
    item = result.memberships[0]
    assert item.membership.repository_id == REPO_ID
    assert item.membership.repository_full_name == REPO
    assert item.provenance.source == CANARY_SOURCE
    assert [call[0] for call in github.calls] == [
        "get_repository",
        "get_repository",
        "get_pull_request",
        "verify_branch_sha",
        "compare",
        "get_pull_request",
        "verify_branch_sha",
        "get_repository",
    ]
    assert_no_cycles(db)


def test_missing_creation_job_fails_closed(tmp_path):
    db = make_db(tmp_path)
    github = FakeGitHub()
    with pytest.raises(MembershipResolutionError) as info:
        run(service(db, github=github).resolve(
            conversation_id=CONV, chat_id=CHAT, pr_numbers=(PR,)
        ))
    assert info.value.code == MISSING_CONVERSATION_REPOSITORY_LINK
    assert github.calls == []
    assert_no_cycles(db)


def test_job_without_conversation_identity_is_not_used(tmp_path):
    db = make_db(tmp_path)
    make_job(db, conversation_id=None)
    github = FakeGitHub()
    with pytest.raises(MembershipResolutionError) as info:
        run(service(db, github=github).resolve(
            conversation_id=CONV, chat_id=CHAT, pr_numbers=(PR,)
        ))
    assert info.value.code == MISSING_CONVERSATION_REPOSITORY_LINK
    assert github.calls == []
    assert_no_cycles(db)


def test_creation_job_for_another_conversation_is_not_reused(tmp_path):
    db = make_db(tmp_path)
    make_job(db, conversation_id=OTHER_CONV)
    github = FakeGitHub()
    with pytest.raises(MembershipResolutionError) as info:
        run(service(db, github=github).resolve(
            conversation_id=CONV, chat_id=CHAT, pr_numbers=(PR,)
        ))
    assert info.value.code == MISSING_CONVERSATION_REPOSITORY_LINK
    assert github.calls == []
    assert_no_cycles(db)


def test_two_done_jobs_for_one_conversation_are_ambiguous(tmp_path):
    db = make_db(tmp_path)
    make_job(db, repo=REPO)
    make_job(db, repo="owner/other")
    github = FakeGitHub()
    with pytest.raises(MembershipResolutionError) as info:
        run(service(db, github=github).resolve(
            conversation_id=CONV, chat_id=CHAT, pr_numbers=(PR,)
        ))
    assert info.value.code == MISSING_CONVERSATION_REPOSITORY_LINK
    assert github.calls == []
    assert_no_cycles(db)


def test_job_owned_by_another_chat_is_rejected(tmp_path):
    db = make_db(tmp_path)
    make_job(db, chat_id=CHAT + 1)
    github = FakeGitHub()
    with pytest.raises(MembershipResolutionError) as info:
        run(service(db, github=github).resolve(
            conversation_id=CONV, chat_id=CHAT, pr_numbers=(PR,)
        ))
    assert info.value.code == MISSING_CONVERSATION_REPOSITORY_LINK
    assert github.calls == []
    assert_no_cycles(db)


def test_database_read_failure_fails_closed(tmp_path, monkeypatch):
    db = make_db(tmp_path)
    make_job(db)
    github = FakeGitHub()

    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("forced read failure")

    monkeypatch.setattr(db, "list_done_creation_jobs_for_conversation", fail)
    with pytest.raises(MembershipResolutionError) as info:
        run(service(db, github=github).resolve(
            conversation_id=CONV, chat_id=CHAT, pr_numbers=(PR,)
        ))
    assert info.value.code == CONVERSATION_LINK_UNAVAILABLE
    assert github.calls == []
    assert_no_cycles(db)


def test_malformed_repository_name_is_rejected(tmp_path):
    db = make_db(tmp_path)
    make_job(db, repo="not-a-repository")
    github = FakeGitHub()
    with pytest.raises(MembershipResolutionError) as info:
        run(service(db, github=github).resolve(
            conversation_id=CONV, chat_id=CHAT, pr_numbers=(PR,)
        ))
    assert info.value.code == MISSING_CONVERSATION_REPOSITORY_LINK
    assert github.calls == []
    assert_no_cycles(db)


def test_untrusted_openhands_candidate_cannot_override_job(tmp_path):
    db = make_db(tmp_path)
    make_job(db, repo=REPO)
    openhands = FakeOpenHands(
        conversations=[{"id": CONV, "selected_repository": "evil/repo"}]
    )
    github = FakeGitHub()
    with pytest.raises(MembershipResolutionError) as info:
        run(service(db, github=github, openhands=openhands).resolve(
            conversation_id=CONV, chat_id=CHAT, pr_numbers=(PR,)
        ))
    assert info.value.code == MISSING_CONVERSATION_REPOSITORY_LINK
    assert github.calls == []
    assert_no_cycles(db)


def test_openhands_missing_selected_repository_is_rejected(tmp_path):
    db = make_db(tmp_path)
    make_job(db, repo=REPO)
    openhands = FakeOpenHands(conversations=[{"id": CONV}])
    github = FakeGitHub()
    with pytest.raises(MembershipResolutionError) as info:
        run(service(db, github=github, openhands=openhands).resolve(
            conversation_id=CONV, chat_id=CHAT, pr_numbers=(PR,)
        ))
    assert info.value.code == MISSING_CONVERSATION_REPOSITORY_LINK
    assert github.calls == []
    assert_no_cycles(db)


def test_numeric_repository_id_mismatch_fails_closed(tmp_path):
    db = make_db(tmp_path)
    make_job(db)
    github = FakeGitHub(
        repository_values=[
            repository(),
            repository(repository_id=OTHER_REPO_ID),
        ]
    )
    with pytest.raises(MembershipResolutionError) as info:
        run(service(db, github=github).resolve(
            conversation_id=CONV, chat_id=CHAT, pr_numbers=(PR,)
        ))
    assert info.value.code == REPOSITORY_ID_MISMATCH
    assert_no_cycles(db)


def test_canonical_full_name_mismatch_is_rejected(tmp_path):
    db = make_db(tmp_path)
    make_job(db)
    github = FakeGitHub(repository_values=[repository(full_name="owner/renamed")])
    with pytest.raises(MembershipResolutionError) as info:
        run(service(db, github=github).resolve(
            conversation_id=CONV, chat_id=CHAT, pr_numbers=(PR,)
        ))
    assert info.value.code == MISSING_CONVERSATION_REPOSITORY_LINK
    assert_no_cycles(db)


def test_same_name_recreated_repository_is_not_distinguishable(tmp_path):
    # D-01 B has no creation-time numeric ID. This test records the documented
    # limitation: a same-name repository with a new numeric ID is accepted.
    db = make_db(tmp_path)
    make_job(db)
    github = FakeGitHub(
        repository_values=[
            repository(repository_id=OTHER_REPO_ID),
            repository(repository_id=OTHER_REPO_ID),
            repository(repository_id=OTHER_REPO_ID),
        ],
        pull_requests={
            PR: pull_request(
                head_repo_id=OTHER_REPO_ID,
                base_repo_id=OTHER_REPO_ID,
            )
        },
    )
    result = run(service(db, github=github).resolve(
        conversation_id=CONV, chat_id=CHAT, pr_numbers=(PR,)
    ))
    assert result.memberships[0].membership.repository_id == OTHER_REPO_ID
    assert_no_cycles(db)


def test_missing_github_identity_is_rejected(tmp_path):
    db = make_db(tmp_path)
    make_job(db)
    github = FakeGitHub(repository_values=[None])
    with pytest.raises(MembershipResolutionError) as info:
        run(service(db, github=github).resolve(
            conversation_id=CONV, chat_id=CHAT, pr_numbers=(PR,)
        ))
    assert info.value.code == MISSING_CONVERSATION_REPOSITORY_LINK
    assert_no_cycles(db)


def test_github_verification_failure_fails_closed(tmp_path):
    db = make_db(tmp_path)
    make_job(db)
    github = FakeGitHub(repository_error=GitHubTransportError("token=SENTINEL"))
    with pytest.raises(MembershipResolutionError) as info:
        run(service(db, github=github).resolve(
            conversation_id=CONV, chat_id=CHAT, pr_numbers=(PR,)
        ))
    assert info.value.code == CONVERSATION_LINK_UNAVAILABLE
    assert "SENTINEL" not in str(info.value)
    assert_no_cycles(db)


# ------------------------------------------------------- D-02 explicit list


def test_single_explicit_pr_resolves(tmp_path):
    db = make_db(tmp_path)
    make_job(db)
    result = run(service(db).resolve(
        conversation_id=CONV, chat_id=CHAT, pr_numbers=(PR,)
    ))
    assert [item.membership.pr_number for item in result.memberships] == [PR]


def test_multiple_explicit_prs_are_preserved_and_sorted(tmp_path):
    db = make_db(tmp_path)
    make_job(db)
    github = FakeGitHub(
        pull_requests={
            PR: pull_request(),
            5: pull_request(number=5, head_sha=C),
        },
        compares={(A, B): compare(A, B), (A, C): compare(A, C)},
    )
    result = run(service(db, github=github).resolve(
        conversation_id=CONV, chat_id=CHAT, pr_numbers=(5, PR)
    ))
    assert [item.membership.pr_number for item in result.memberships] == [PR, 5]
    assert [item.membership.head_sha for item in result.memberships] == [B, C]


def test_non_owner_submission_is_rejected_before_external_dependencies(tmp_path):
    db = make_db(tmp_path)
    make_job(db)
    github = FakeGitHub()
    openhands = FakeOpenHands()
    with pytest.raises(MembershipResolutionError) as info:
        run(service(db, github=github, openhands=openhands).resolve(
            conversation_id=CONV, chat_id=CHAT + 1, pr_numbers=(PR,)
        ))
    assert info.value.code == UNAUTHORIZED_CONVERSATION
    assert github.calls == []
    assert openhands.calls == []
    assert_no_cycles(db)


def test_empty_pr_list_is_rejected(tmp_path):
    db = make_db(tmp_path)
    make_job(db)
    github = FakeGitHub()
    with pytest.raises(MembershipResolutionError) as info:
        run(service(db, github=github).resolve(
            conversation_id=CONV, chat_id=CHAT, pr_numbers=[]
        ))
    assert info.value.code == INVALID_RESOLUTION_REQUEST
    assert github.calls == []
    assert_no_cycles(db)


@pytest.mark.parametrize("pr_numbers", [(0,), (-1,), (True,), ("3",), (3.0,), (None,)])
def test_malformed_pr_identifier_is_rejected(tmp_path, pr_numbers):
    db = make_db(tmp_path)
    make_job(db)
    github = FakeGitHub()
    with pytest.raises(MembershipResolutionError) as info:
        run(service(db, github=github).resolve(
            conversation_id=CONV, chat_id=CHAT, pr_numbers=pr_numbers
        ))
    assert info.value.code == INVALID_RESOLUTION_REQUEST
    assert github.calls == []
    assert_no_cycles(db)


def test_duplicate_pr_is_rejected(tmp_path):
    db = make_db(tmp_path)
    make_job(db)
    github = FakeGitHub()
    with pytest.raises(MembershipResolutionError) as info:
        run(service(db, github=github).resolve(
            conversation_id=CONV, chat_id=CHAT, pr_numbers=(PR, PR)
        ))
    assert info.value.code == DUPLICATE_PR_MEMBERSHIP
    assert github.calls == []
    assert_no_cycles(db)


def test_excessive_pr_list_is_rejected(tmp_path):
    db = make_db(tmp_path)
    make_job(db)
    github = FakeGitHub()
    with pytest.raises(MembershipResolutionError) as info:
        run(service(db, github=github, max_pr_candidates=2).resolve(
            conversation_id=CONV, chat_id=CHAT, pr_numbers=(1, 2, 3)
        ))
    assert info.value.code == INVALID_RESOLUTION_REQUEST
    assert github.calls == []
    assert_no_cycles(db)


def test_pr_from_another_repository_is_rejected(tmp_path):
    db = make_db(tmp_path)
    make_job(db)
    github = FakeGitHub(
        pull_requests={PR: pull_request(base_repo_id=OTHER_REPO_ID)}
    )
    with pytest.raises(MembershipResolutionError) as info:
        run(service(db, github=github).resolve(
            conversation_id=CONV, chat_id=CHAT, pr_numbers=(PR,)
        ))
    assert info.value.code == PR_REPOSITORY_MISMATCH
    assert_no_cycles(db)


def test_missing_pr_metadata_is_rejected(tmp_path):
    db = make_db(tmp_path)
    make_job(db)
    github = FakeGitHub(pull_requests={})
    with pytest.raises(MembershipResolutionError) as info:
        run(service(db, github=github).resolve(
            conversation_id=CONV, chat_id=CHAT, pr_numbers=(PR,)
        ))
    assert info.value.code == MALFORMED_EXTERNAL_RESPONSE
    assert_no_cycles(db)


def test_branch_movement_before_reservation_is_rejected(tmp_path):
    db = make_db(tmp_path)
    make_job(db)
    github = FakeGitHub(
        branch_results=[BranchVerification(REPO, "agent/x", B, C, "moved")]
    )
    with pytest.raises(MembershipResolutionError) as info:
        run(service(db, github=github).resolve(
            conversation_id=CONV, chat_id=CHAT, pr_numbers=(PR,)
        ))
    assert info.value.code == BRANCH_MOVED
    assert_no_cycles(db)


def test_branch_movement_during_validation_is_rejected(tmp_path):
    db = make_db(tmp_path)
    make_job(db)
    github = FakeGitHub(
        branch_results=[
            unchanged(),
            BranchVerification(REPO, "agent/x", B, C, "moved"),
        ]
    )
    with pytest.raises(MembershipResolutionError) as info:
        run(service(db, github=github).resolve(
            conversation_id=CONV, chat_id=CHAT, pr_numbers=(PR,)
        ))
    assert info.value.code == BRANCH_MOVED
    assert_no_cycles(db)


def test_head_sha_mismatch_is_rejected(tmp_path):
    db = make_db(tmp_path)
    make_job(db)
    github = FakeGitHub(compares={(A, B): compare(A, B, observed_head=C)})
    with pytest.raises(MembershipResolutionError) as info:
        run(service(db, github=github).resolve(
            conversation_id=CONV, chat_id=CHAT, pr_numbers=(PR,)
        ))
    assert info.value.code == COMPARE_MISMATCH
    assert_no_cycles(db)


def test_invalid_sha_is_rejected(tmp_path):
    db = make_db(tmp_path)
    make_job(db)
    github = FakeGitHub(
        pull_requests={PR: pull_request(head_sha="not-a-sha")}
    )
    with pytest.raises(MembershipResolutionError) as info:
        run(service(db, github=github).resolve(
            conversation_id=CONV, chat_id=CHAT, pr_numbers=(PR,)
        ))
    assert info.value.code == INVALID_RESOLUTION_REQUEST
    assert_no_cycles(db)


def test_partial_list_with_one_invalid_pr_creates_no_cycle(tmp_path):
    db = make_db(tmp_path)
    make_job(db)
    github = FakeGitHub(
        pull_requests={
            PR: pull_request(),
            5: pull_request(number=5, state="closed"),
        },
        compares={(A, B): compare(A, B)},
    )
    snap = snapshot(db)
    with pytest.raises(MembershipResolutionError) as info:
        run(service(db, github=github).resolve_and_reserve(
            conversation_id=CONV,
            chat_id=CHAT,
            pr_numbers=(PR, 5),
            provider_snapshot_id=snap.id,
            reserved_by="owner",
            now=T0,
        ))
    assert info.value.code == PR_NOT_OPEN
    assert_no_cycles(db)


def test_retry_with_identical_list_is_idempotent(tmp_path):
    db = make_db(tmp_path)
    make_job(db)
    github = FakeGitHub()
    snap = snapshot(db)
    first = run(service(db, github=github).resolve_and_reserve(
        conversation_id=CONV,
        chat_id=CHAT,
        pr_numbers=(PR,),
        provider_snapshot_id=snap.id,
        reserved_by="owner",
        now=T0,
    ))
    second = run(service(db, github=github).resolve_and_reserve(
        conversation_id=CONV,
        chat_id=CHAT,
        pr_numbers=(PR,),
        provider_snapshot_id=snap.id,
        reserved_by="owner",
        now=T0,
    ))
    assert first.outcome == "newly_reserved"
    assert second.outcome == "already_reserved"
    assert second.existing_id == first.review_id


def test_retry_with_conflicting_list_does_not_mutate(tmp_path):
    db = make_db(tmp_path)
    make_job(db)
    snap = snapshot(db)
    first = run(service(db).resolve_and_reserve(
        conversation_id=CONV,
        chat_id=CHAT,
        pr_numbers=(PR,),
        provider_snapshot_id=snap.id,
        reserved_by="owner",
        now=T0,
    ))
    changed_github = FakeGitHub(
        pull_requests={PR: pull_request(head_sha=C)},
        compares={(A, C): compare(A, C)},
    )
    second = run(service(db, github=changed_github).resolve_and_reserve(
        conversation_id=CONV,
        chat_id=CHAT,
        pr_numbers=(PR,),
        provider_snapshot_id=snap.id,
        reserved_by="owner",
        now=T0,
    ))
    assert second.outcome == "conflicting_identity"
    memberships = db.get_auto_review_memberships(first.review_id)
    assert len(memberships) == 1
    assert memberships[0].head_sha == B


def test_membership_snapshot_is_immutable(tmp_path):
    db = make_db(tmp_path)
    make_job(db)
    snap = snapshot(db)
    reserved = run(service(db).resolve_and_reserve(
        conversation_id=CONV,
        chat_id=CHAT,
        pr_numbers=(PR,),
        provider_snapshot_id=snap.id,
        reserved_by="owner",
        now=T0,
    ))
    with pytest.raises(sqlite3.IntegrityError):
        db._conn.execute(
            "UPDATE auto_review_memberships SET head_sha=? WHERE review_id=?",
            (C, reserved.review_id),
        )
    db._conn.rollback()


def test_second_cycle_for_same_conversation_is_blocked(tmp_path):
    db = make_db(tmp_path)
    make_job(db)
    snap = snapshot(db)
    first = run(service(db).resolve_and_reserve(
        conversation_id=CONV,
        chat_id=CHAT,
        pr_numbers=(PR,),
        provider_snapshot_id=snap.id,
        reserved_by="owner",
        now=T0,
    ))
    second = run(service(
        db,
        github=FakeGitHub(
            pull_requests={5: pull_request(number=5, head_sha=C)},
            compares={(A, C): compare(A, C)},
        ),
    ).resolve_and_reserve(
        conversation_id=CONV,
        chat_id=CHAT,
        pr_numbers=(5,),
        provider_snapshot_id=snap.id,
        reserved_by="owner",
        now=T0,
    ))
    assert second.outcome == "conflicting_identity"
    assert len(db.get_auto_review_memberships(first.review_id)) == 1


def test_full_mocked_path_reserves_one_conversation_wide_cycle(tmp_path):
    db = make_db(tmp_path)
    make_job(db)
    snap = snapshot(db)
    reserved = run(service(db).resolve_and_reserve(
        conversation_id=CONV,
        chat_id=CHAT,
        pr_numbers=(PR,),
        provider_snapshot_id=snap.id,
        reserved_by="owner",
        now=T0,
    ))
    cycle = db.get_auto_review(reserved.review_id)
    assert cycle is not None
    assert cycle.scope == "conversation"
    assert cycle.scope_policy == "conversation-wide"
    assert [m.pr_number for m in db.get_auto_review_memberships(cycle.id)] == [PR]


def test_database_failure_rolls_back_all_partial_state(tmp_path):
    db = make_db(tmp_path)
    make_job(db)
    snap = snapshot(db)
    locker = sqlite3.connect(str(tmp_path / "canary.sqlite3"), timeout=0.1)
    try:
        locker.execute("BEGIN IMMEDIATE")
        db._conn.execute("PRAGMA busy_timeout=1")
        with pytest.raises(sqlite3.OperationalError):
            run(service(db).resolve_and_reserve(
                conversation_id=CONV,
                chat_id=CHAT,
                pr_numbers=(PR,),
                provider_snapshot_id=snap.id,
                reserved_by="owner",
                now=T0,
            ))
    finally:
        locker.rollback()
        locker.close()
    assert_no_cycles(db)


def test_linkage_has_no_provider_or_telegram_calls(tmp_path):
    class Sink:
        def __init__(self):
            self.calls = []

    provider = Sink()
    telegram = Sink()
    db = make_db(tmp_path)
    make_job(db)
    result = run(service(db).resolve(
        conversation_id=CONV, chat_id=CHAT, pr_numbers=(PR,)
    ))
    assert result.memberships
    assert provider.calls == []
    assert telegram.calls == []


def test_concurrent_canary_reservations_have_one_winner(tmp_path):
    path = str(tmp_path / "canary.sqlite3")
    db1 = Database(path)
    db1.add_watched(CONV, "canary target", CHAT)
    make_job(db1)
    snap = snapshot(db1)
    barrier = threading.Barrier(2)
    results = []
    errors = []

    def worker():
        try:
            db = Database(path)
            barrier.wait(timeout=10)
            results.append(
                run(service(db).resolve_and_reserve(
                    conversation_id=CONV,
                    chat_id=CHAT,
                    pr_numbers=(PR,),
                    provider_snapshot_id=snap.id,
                    reserved_by="owner",
                    now=T0,
                ))
            )
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert not errors
    assert sorted(item.outcome for item in results) == [
        "already_reserved",
        "newly_reserved",
    ]
    assert db1._conn.execute("SELECT COUNT(*) FROM auto_reviews").fetchone()[0] == 1
