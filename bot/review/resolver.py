"""R7-B01 conversation-to-PR-to-exact-SHA resolution primitives.

This module is deliberately a verifier, not a discovery engine. A caller must
supply a trusted conversation repository link through an injected source. The
source is the unresolved owner decision; this module never reads prompt text,
branch names, PR descriptions, or arbitrary conversation metadata as proof of
repository ownership.

The resolver verifies the supplied link and every explicitly supplied PR number
against the read-only GitHub client, then returns immutable membership values
compatible with the existing R2/R5 reservation API. It does not start a worker,
call a provider, or write review cycles.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from bot.db import (
    AUTO_REVIEW_RESERVATION_INVALID,
    AutoReviewMembership,
    AutoReviewReservation,
    Database,
)
from bot.review.eligibility import repository_eligibility_code
from bot.review.github import (
    BranchVerification,
    CompareResult,
    GitHubAuthError,
    GitHubClient,
    GitHubError,
    GitHubForbiddenError,
    GitHubMalformedResponse,
    GitHubNotFoundError,
    GitHubPaginationError,
    GitHubRateLimitError,
    GitHubRedirectError,
    GitHubRepoNotAllowed,
    GitHubRepositoryIdentityMismatch,
    GitHubResponseError,
    GitHubResponseTooLarge,
    GitHubServerError,
    GitHubShaMismatchError,
    GitHubTransportError,
    PullRequestIdentity,
    RepositoryIdentity,
)

_CONVERSATION_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

# Safe reason codes. They intentionally contain no token, response body, or
# caller-supplied repository/PR text.
MISSING_CONVERSATION_REPOSITORY_LINK = "missing_conversation_repository_link"
CONVERSATION_LINK_UNAVAILABLE = "conversation_link_unavailable"
CONVERSATION_LINK_MISMATCH = "conversation_link_mismatch"
UNAUTHORIZED_CONVERSATION = "unauthorized_conversation"
CONVERSATION_AUTHORIZATION_UNAVAILABLE = "conversation_authorization_unavailable"
INVALID_RESOLUTION_REQUEST = "invalid_resolution_request"
DUPLICATE_PR_MEMBERSHIP = "duplicate_pr_membership"
REPOSITORY_NOT_ALLOWED = "repository_not_allowed"
REPOSITORY_NOT_FOUND = "repository_not_found"
REPOSITORY_ID_MISMATCH = "repository_id_mismatch"
REPOSITORY_RENAME_AMBIGUOUS = "repository_rename_ambiguous"
REPOSITORY_REDIRECT_REJECTED = "repository_redirect_rejected"
PR_NOT_FOUND = "pr_not_found"
PR_REPOSITORY_MISMATCH = "pr_repository_mismatch"
PR_FORK_AMBIGUOUS = "pr_fork_ambiguous"
PR_NOT_OPEN = "pr_not_open"
PR_HEAD_MOVED = "pr_head_moved"
BRANCH_MOVED = "branch_moved"
BRANCH_MISSING = "branch_missing"
BRANCH_BLOCKED = "branch_blocked"
COMPARE_MISMATCH = "compare_mismatch"
MALFORMED_EXTERNAL_RESPONSE = "malformed_external_response"
GITHUB_UNAUTHORIZED = "github_unauthorized"
GITHUB_UNAVAILABLE = "github_unavailable"
GITHUB_ERROR = "github_error"


class MembershipResolutionError(RuntimeError):
    """Fail-closed resolution error with a safe reason code."""

    def __init__(self, code: str, *, retryable: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class ConversationRepositoryLink:
    """A caller-supplied, unverified claim about a conversation's repository.

    ``source`` is audit provenance only. It is not proof of ownership; the
    resolver still verifies the immutable repository ID and full name through
    GitHub. The concrete source remains an owner decision.
    """

    conversation_id: str
    repository_id: int
    repository_full_name: str
    source: str


class ConversationRepositoryLinkSource(Protocol):
    async def resolve(self, conversation_id: str) -> ConversationRepositoryLink | None: ...


@dataclass(frozen=True)
class MembershipProvenance:
    conversation_id: str
    source: str
    repository_id: int
    repository_full_name: str
    pr_number: int
    head_ref: str
    head_sha: str
    base_sha: str
    verified_at: str


@dataclass(frozen=True)
class ResolvedMembership:
    membership: AutoReviewMembership
    provenance: MembershipProvenance


@dataclass(frozen=True)
class ResolutionResult:
    conversation_id: str
    chat_id: int
    memberships: tuple[ResolvedMembership, ...]


class ConversationMembershipResolver:
    """Verify an explicit conversation/repository link and explicit PR numbers."""

    def __init__(
        self,
        db: Database,
        github: GitHubClient,
        link_source: ConversationRepositoryLinkSource,
        *,
        clock=None,
    ) -> None:
        if db is None or github is None or link_source is None:
            raise ValueError("resolver dependencies are required")
        self._db = db
        self._github = github
        self._link_source = link_source
        self._clock = clock or (lambda: datetime.now(timezone.utc).isoformat())

    async def resolve(
        self,
        *,
        conversation_id: str,
        chat_id: int,
        pr_numbers: tuple[int, ...] | list[int],
    ) -> ResolutionResult:
        ordered_numbers = _validate_request(conversation_id, chat_id, pr_numbers)
        await self._authorize(conversation_id, chat_id)
        link = await self._load_link(conversation_id)
        repository = await self._load_repository(link)
        resolved: list[ResolvedMembership] = []
        for number in ordered_numbers:
            pr = await self._load_pull_request(repository, number)
            self._validate_pull_request(repository, pr)
            await self._verify_branch(repository, pr.head_ref, pr.head_sha)
            base_sha = await self._resolve_base_sha(repository, pr)
            membership = AutoReviewMembership(
                repository_id=repository.repository_id,
                repository_full_name=repository.full_name,
                pr_number=pr.pr_number,
                branch=pr.head_ref,
                base_sha=base_sha,
                head_sha=pr.head_sha,
            )
            resolved.append(
                ResolvedMembership(
                    membership=membership,
                    provenance=MembershipProvenance(
                        conversation_id=conversation_id,
                        source=link.source,
                        repository_id=repository.repository_id,
                        repository_full_name=repository.full_name,
                        pr_number=pr.pr_number,
                        head_ref=pr.head_ref,
                        head_sha=pr.head_sha,
                        base_sha=base_sha,
                        verified_at=self._clock(),
                    ),
                )
            )
        # Re-read the PR heads and branch tips after all reads. A change during
        # resolution must fail closed rather than become stale evidence.
        for item in resolved:
            await self._reverify_pull_request(repository, item.membership)
            await self._verify_branch(
                repository, item.membership.branch, item.membership.head_sha
            )
        # D-05: re-read the repository identity after every PR/branch read. A
        # rename/transfer during resolution must not leave a previously valid
        # identity authorizing later reservation or execution.
        await self._reverify_repository(repository)
        return ResolutionResult(
            conversation_id=conversation_id,
            chat_id=chat_id,
            memberships=tuple(resolved),
        )

    async def _authorize(self, conversation_id: str, chat_id: int) -> None:
        try:
            if self._db.is_deleted(conversation_id):
                raise MembershipResolutionError(UNAUTHORIZED_CONVERSATION)
            watched = self._db.get_watched(conversation_id)
        except MembershipResolutionError:
            raise
        except Exception as exc:
            raise MembershipResolutionError(
                CONVERSATION_AUTHORIZATION_UNAVAILABLE, retryable=True
            ) from exc
        if watched is None or watched.chat_id != chat_id:
            raise MembershipResolutionError(UNAUTHORIZED_CONVERSATION)

    async def _load_link(self, conversation_id: str) -> ConversationRepositoryLink:
        try:
            link = await self._link_source.resolve(conversation_id)
        except (GitHubRedirectError, GitHubRepositoryIdentityMismatch) as exc:
            raise _map_github_error(exc) from exc
        except Exception as exc:
            raise MembershipResolutionError(
                CONVERSATION_LINK_UNAVAILABLE, retryable=True
            ) from exc
        if link is None:
            raise MembershipResolutionError(MISSING_CONVERSATION_REPOSITORY_LINK)
        if not isinstance(link, ConversationRepositoryLink):
            raise MembershipResolutionError(MALFORMED_EXTERNAL_RESPONSE)
        if link.conversation_id != conversation_id:
            raise MembershipResolutionError(CONVERSATION_LINK_MISMATCH)
        if (
            not isinstance(link.repository_id, int)
            or isinstance(link.repository_id, bool)
            or link.repository_id <= 0
            or not isinstance(link.repository_full_name, str)
            or not _REPO_RE.fullmatch(link.repository_full_name)
            or not isinstance(link.source, str)
            or not link.source
            or len(link.source) > 64
            or any(ch.isspace() or ord(ch) < 32 for ch in link.source)
        ):
            raise MembershipResolutionError(INVALID_RESOLUTION_REQUEST)
        return link

    async def _load_repository(
        self, link: ConversationRepositoryLink
    ) -> RepositoryIdentity:
        try:
            repository = await self._github.get_repository(link.repository_full_name)
        except GitHubRepoNotAllowed as exc:
            raise MembershipResolutionError(REPOSITORY_NOT_ALLOWED) from exc
        except GitHubNotFoundError as exc:
            raise MembershipResolutionError(REPOSITORY_NOT_FOUND) from exc
        except Exception as exc:
            raise _map_github_error(exc) from exc
        if not isinstance(repository, RepositoryIdentity):
            raise MembershipResolutionError(MALFORMED_EXTERNAL_RESPONSE)
        if repository.repository_id != link.repository_id:
            raise MembershipResolutionError(REPOSITORY_ID_MISMATCH)
        if repository.full_name.casefold() != link.repository_full_name.casefold():
            raise MembershipResolutionError(REPOSITORY_RENAME_AMBIGUOUS)
        eligibility = repository_eligibility_code(repository)
        if eligibility is not None:
            raise MembershipResolutionError(eligibility)
        return repository

    async def _reverify_repository(self, expected: RepositoryIdentity) -> None:
        """D-05: reject a repository identity change after the first verification."""
        try:
            current = await self._github.get_repository(expected.full_name)
        except Exception as exc:
            raise _map_github_error(exc) from exc
        if not isinstance(current, RepositoryIdentity):
            raise MembershipResolutionError(MALFORMED_EXTERNAL_RESPONSE)
        if current.repository_id != expected.repository_id:
            raise MembershipResolutionError(REPOSITORY_ID_MISMATCH)
        if current.full_name.casefold() != expected.full_name.casefold():
            raise MembershipResolutionError(REPOSITORY_RENAME_AMBIGUOUS)
        eligibility = repository_eligibility_code(current)
        if eligibility is not None:
            raise MembershipResolutionError(eligibility)

    async def _load_pull_request(
        self, repository: RepositoryIdentity, pr_number: int
    ) -> PullRequestIdentity:
        try:
            pr = await self._github.get_pull_request(
                repository.full_name, pr_number
            )
        except GitHubNotFoundError as exc:
            raise MembershipResolutionError(PR_NOT_FOUND) from exc
        except Exception as exc:
            raise _map_github_error(exc) from exc
        if not isinstance(pr, PullRequestIdentity) or pr.pr_number != pr_number:
            raise MembershipResolutionError(MALFORMED_EXTERNAL_RESPONSE)
        return pr

    @staticmethod
    def _validate_pull_request(
        repository: RepositoryIdentity, pr: PullRequestIdentity
    ) -> None:
        if (
            pr.pr_number <= 0
            or pr.repository_id != repository.repository_id
            or pr.repository_full_name.casefold() != repository.full_name.casefold()
            or pr.base_repository_id != repository.repository_id
            or pr.base_repository_full_name.casefold() != repository.full_name.casefold()
        ):
            raise MembershipResolutionError(PR_REPOSITORY_MISMATCH)
        if (
            pr.head_repository_id != repository.repository_id
            or pr.head_repository_full_name.casefold() != repository.full_name.casefold()
        ):
            raise MembershipResolutionError(PR_FORK_AMBIGUOUS)
        if pr.state != "open" or pr.merged:
            raise MembershipResolutionError(PR_NOT_OPEN)
        if (
            not isinstance(pr.head_ref, str)
            or not pr.head_ref
            or any(ch.isspace() or ord(ch) < 32 for ch in pr.head_ref)
            or not _SHA_RE.fullmatch(pr.head_sha)
            or not _SHA_RE.fullmatch(pr.base_sha)
        ):
            raise MembershipResolutionError(INVALID_RESOLUTION_REQUEST)

    async def _verify_branch(
        self, repository: RepositoryIdentity, branch: str, head_sha: str
    ) -> BranchVerification:
        try:
            verification = await self._github.verify_branch_sha(
                repository.full_name, branch, head_sha
            )
        except Exception as exc:
            raise _map_github_error(exc) from exc
        if not isinstance(verification, BranchVerification):
            raise MembershipResolutionError(MALFORMED_EXTERNAL_RESPONSE)
        if verification.status == "moved":
            raise MembershipResolutionError(BRANCH_MOVED)
        if verification.status == "missing":
            raise MembershipResolutionError(BRANCH_MISSING)
        if verification.status == "blocked":
            raise MembershipResolutionError(BRANCH_BLOCKED)
        if verification.status != "unchanged":
            raise MembershipResolutionError(INVALID_RESOLUTION_REQUEST)
        return verification

    async def _resolve_base_sha(
        self, repository: RepositoryIdentity, pr: PullRequestIdentity
    ) -> str:
        first = await self._compare(repository, pr.base_sha, pr.head_sha)
        if first.status == "verified":
            return first.base_sha
        if first.status != "merge_base_mismatch" or not first.merge_base_sha:
            raise MembershipResolutionError(COMPARE_MISMATCH)
        second = await self._compare(repository, first.merge_base_sha, pr.head_sha)
        if second.status != "verified":
            raise MembershipResolutionError(COMPARE_MISMATCH)
        return second.base_sha

    async def _compare(
        self, repository: RepositoryIdentity, base_sha: str, head_sha: str
    ) -> CompareResult:
        try:
            result = await self._github.compare(
                repository.full_name, base_sha, head_sha
            )
        except Exception as exc:
            raise _map_github_error(exc) from exc
        if not isinstance(result, CompareResult):
            raise MembershipResolutionError(MALFORMED_EXTERNAL_RESPONSE)
        if (
            not _SHA_RE.fullmatch(result.base_sha)
            or not _SHA_RE.fullmatch(result.head_sha)
            or result.repository.casefold() != repository.full_name.casefold()
            or result.base_sha != base_sha
            or result.head_sha != head_sha
            or result.observed_base_sha != base_sha
            or result.observed_head_sha != head_sha
        ):
            raise MembershipResolutionError(COMPARE_MISMATCH)
        return result

    async def _reverify_pull_request(
        self, repository: RepositoryIdentity, membership: AutoReviewMembership
    ) -> None:
        current = await self._load_pull_request(repository, membership.pr_number)
        self._validate_pull_request(repository, current)
        if (
            current.head_sha != membership.head_sha
            or current.head_ref != membership.branch
        ):
            raise MembershipResolutionError(PR_HEAD_MOVED)


def reserve_resolved_memberships(
    db: Database,
    result: ResolutionResult,
    *,
    provider_snapshot_id: int,
    reserved_by: str,
    implementation_report: str = "",
    now: str | None = None,
) -> AutoReviewReservation:
    """Reserve a verified result through the existing atomic R2/R5 API."""
    if not isinstance(result, ResolutionResult) or not result.memberships:
        return AutoReviewReservation(AUTO_REVIEW_RESERVATION_INVALID, detail="resolution")
    if (
        not isinstance(result.conversation_id, str)
        or not result.conversation_id
        or not isinstance(result.chat_id, int)
        or isinstance(result.chat_id, bool)
        or result.chat_id <= 0
    ):
        return AutoReviewReservation(AUTO_REVIEW_RESERVATION_INVALID, detail="conversation")
    try:
        watched = db.get_watched(result.conversation_id)
        if (
            db.is_deleted(result.conversation_id)
            or watched is None
            or watched.chat_id != result.chat_id
        ):
            return AutoReviewReservation(
                AUTO_REVIEW_RESERVATION_INVALID, detail="conversation"
            )
    except Exception:
        return AutoReviewReservation(AUTO_REVIEW_RESERVATION_INVALID, detail="conversation")
    memberships: list[AutoReviewMembership] = []
    seen: set[tuple[int, int]] = set()
    for item in result.memberships:
        if not isinstance(item, ResolvedMembership):
            return AutoReviewReservation(AUTO_REVIEW_RESERVATION_INVALID, detail="resolution")
        if not isinstance(item.provenance, MembershipProvenance):
            return AutoReviewReservation(AUTO_REVIEW_RESERVATION_INVALID, detail="provenance")
        provenance = item.provenance
        membership = item.membership
        if (
            not isinstance(provenance.source, str)
            or not provenance.source
            or not isinstance(provenance.verified_at, str)
            or not provenance.verified_at
            or not isinstance(provenance.repository_full_name, str)
            or not isinstance(membership.repository_full_name, str)
            or provenance.conversation_id != result.conversation_id
            or provenance.repository_id != membership.repository_id
            or provenance.repository_full_name.casefold()
            != membership.repository_full_name.casefold()
            or provenance.pr_number != membership.pr_number
            or provenance.head_ref != membership.branch
            or provenance.head_sha != membership.head_sha
            or provenance.base_sha != membership.base_sha
        ):
            return AutoReviewReservation(AUTO_REVIEW_RESERVATION_INVALID, detail="provenance")
        key = (membership.repository_id, membership.pr_number)
        if key in seen:
            return AutoReviewReservation(
                AUTO_REVIEW_RESERVATION_INVALID, detail="duplicate_membership"
            )
        seen.add(key)
        memberships.append(item.membership)
    return db.reserve_conversation_review(
        conversation_id=result.conversation_id,
        chat_id=result.chat_id,
        memberships=tuple(memberships),
        provider_snapshot_id=provider_snapshot_id,
        reserved_by=reserved_by,
        implementation_report=implementation_report,
        now=now,
    )


def _validate_request(
    conversation_id: str, chat_id: int, pr_numbers: tuple[int, ...] | list[int]
) -> tuple[int, ...]:
    if not isinstance(conversation_id, str) or not _CONVERSATION_RE.fullmatch(
        conversation_id
    ):
        raise MembershipResolutionError(INVALID_RESOLUTION_REQUEST)
    if not isinstance(chat_id, int) or isinstance(chat_id, bool) or chat_id <= 0:
        raise MembershipResolutionError(INVALID_RESOLUTION_REQUEST)
    if not isinstance(pr_numbers, (tuple, list)) or not pr_numbers:
        raise MembershipResolutionError(INVALID_RESOLUTION_REQUEST)
    ordered: list[int] = []
    for number in pr_numbers:
        if not isinstance(number, int) or isinstance(number, bool) or number <= 0:
            raise MembershipResolutionError(INVALID_RESOLUTION_REQUEST)
        ordered.append(number)
    if len(set(ordered)) != len(ordered):
        raise MembershipResolutionError(DUPLICATE_PR_MEMBERSHIP)
    return tuple(sorted(ordered))


def _map_github_error(exc: Exception) -> MembershipResolutionError:
    if isinstance(exc, GitHubRepoNotAllowed):
        return MembershipResolutionError(REPOSITORY_NOT_ALLOWED)
    if isinstance(exc, (GitHubAuthError, GitHubForbiddenError)):
        return MembershipResolutionError(GITHUB_UNAUTHORIZED)
    if isinstance(exc, GitHubRedirectError):
        return MembershipResolutionError(REPOSITORY_REDIRECT_REJECTED)
    if isinstance(exc, GitHubRepositoryIdentityMismatch):
        return MembershipResolutionError(REPOSITORY_RENAME_AMBIGUOUS)
    if isinstance(
        exc,
        (
            GitHubRateLimitError,
            GitHubServerError,
            GitHubTransportError,
        ),
    ):
        return MembershipResolutionError(GITHUB_UNAVAILABLE, retryable=True)
    if isinstance(
        exc,
        (
            GitHubMalformedResponse,
            GitHubResponseTooLarge,
            GitHubPaginationError,
            GitHubShaMismatchError,
            GitHubResponseError,
        ),
    ):
        return MembershipResolutionError(MALFORMED_EXTERNAL_RESPONSE)
    if isinstance(exc, GitHubError):
        return MembershipResolutionError(GITHUB_ERROR)
    if isinstance(exc, ValueError):
        return MembershipResolutionError(INVALID_RESOLUTION_REQUEST)
    return MembershipResolutionError(GITHUB_ERROR)
