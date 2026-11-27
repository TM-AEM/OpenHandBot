"""Canary-only conversation repository linkage and explicit PR-list entry point.

D-01 B uses one durable ``creation_jobs`` row as the repository candidate. D-02
accepts only an explicit owner-supplied PR list. This module never discovers PRs,
starts a worker, or calls a provider. It is intentionally not wired into ``bot.app``.
"""
from __future__ import annotations

import re

from bot.db import AutoReviewReservation, Database
from bot.review.github import GitHubClient, RepositoryIdentity
from bot.review.resolver import (
    DUPLICATE_PR_MEMBERSHIP,
    INVALID_RESOLUTION_REQUEST,
    UNAUTHORIZED_CONVERSATION,
    ConversationMembershipResolver,
    ConversationRepositoryLink,
    MembershipResolutionError,
    ResolutionResult,
    reserve_resolved_memberships,
)

CANARY_SOURCE = "canary_creation_job"
MAX_CANARY_PR_CANDIDATES = 20

_CONVERSATION_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class CreationJobRepositoryLinkSource:
    """Resolve a repository only from one exact bot-created conversation job.

    The local job is the source; OpenHands ``selected_repository`` is an equality
    check only, never a fallback. GitHub supplies the numeric repository identity.
    """

    def __init__(self, db: Database, openhands, github: GitHubClient, *, owner_id: int):
        if db is None or openhands is None or github is None:
            raise ValueError("creation-job link dependencies are required")
        if not isinstance(owner_id, int) or isinstance(owner_id, bool) or owner_id <= 0:
            raise ValueError("owner_id must be a positive integer")
        self._db = db
        self._openhands = openhands
        self._github = github
        self._owner_id = owner_id

    async def resolve(self, conversation_id: str) -> ConversationRepositoryLink | None:
        if not isinstance(conversation_id, str) or not _CONVERSATION_RE.fullmatch(
            conversation_id
        ):
            return None

        jobs = self._db.list_done_creation_jobs_for_conversation(conversation_id)
        if len(jobs) != 1:
            return None
        job = jobs[0]
        if job.conversation_id != conversation_id or job.chat_id != self._owner_id:
            return None

        repository = _normalize_repository(job.repo)
        if repository is None:
            return None

        conversations = await self._openhands.get_conversations([conversation_id])
        if not isinstance(conversations, list) or len(conversations) != 1:
            return None
        conversation = conversations[0]
        if not isinstance(conversation, dict) or conversation.get("id") != conversation_id:
            return None
        selected = conversation.get("selected_repository")
        selected_repository = _normalize_repository(selected)
        if (
            selected_repository is None
            or selected_repository.casefold() != repository.casefold()
        ):
            return None

        identity = await self._github.get_repository(repository)
        if not isinstance(identity, RepositoryIdentity):
            return None
        if (
            not isinstance(identity.repository_id, int)
            or isinstance(identity.repository_id, bool)
            or identity.repository_id <= 0
            or not isinstance(identity.full_name, str)
            or identity.full_name.casefold() != repository.casefold()
        ):
            return None
        return ConversationRepositoryLink(
            conversation_id=conversation_id,
            repository_id=identity.repository_id,
            repository_full_name=identity.full_name,
            source=CANARY_SOURCE,
        )


class CanaryLinkageService:
    """Owner-only entry point for an explicit, bounded PR list.

    This is not PR discovery: every PR number must be supplied by the configured
    owner. The existing resolver performs all repository/PR/SHA verification and
    the existing reservation API persists one immutable conversation-wide snapshot.
    """

    def __init__(
        self,
        db: Database,
        resolver: ConversationMembershipResolver,
        *,
        owner_id: int,
        max_pr_candidates: int = MAX_CANARY_PR_CANDIDATES,
    ) -> None:
        if db is None or resolver is None:
            raise ValueError("canary linkage dependencies are required")
        if not isinstance(owner_id, int) or isinstance(owner_id, bool) or owner_id <= 0:
            raise ValueError("owner_id must be a positive integer")
        if (
            not isinstance(max_pr_candidates, int)
            or isinstance(max_pr_candidates, bool)
            or not 1 <= max_pr_candidates <= 100
        ):
            raise ValueError("max_pr_candidates must be in [1, 100]")
        self._db = db
        self._resolver = resolver
        self._owner_id = owner_id
        self._max_pr_candidates = max_pr_candidates

    async def resolve(
        self,
        *,
        conversation_id: str,
        chat_id: int,
        pr_numbers: tuple[int, ...] | list[int],
    ) -> ResolutionResult:
        if (
            not isinstance(chat_id, int)
            or isinstance(chat_id, bool)
            or chat_id != self._owner_id
        ):
            raise MembershipResolutionError(UNAUTHORIZED_CONVERSATION)
        ordered = _validate_owner_pr_numbers(pr_numbers, self._max_pr_candidates)
        return await self._resolver.resolve(
            conversation_id=conversation_id,
            chat_id=chat_id,
            pr_numbers=ordered,
        )

    async def resolve_and_reserve(
        self,
        *,
        conversation_id: str,
        chat_id: int,
        pr_numbers: tuple[int, ...] | list[int],
        provider_snapshot_id: int,
        reserved_by: str,
        implementation_report: str = "",
        now: str | None = None,
    ) -> AutoReviewReservation:
        result = await self.resolve(
            conversation_id=conversation_id,
            chat_id=chat_id,
            pr_numbers=pr_numbers,
        )
        return reserve_resolved_memberships(
            self._db,
            result,
            provider_snapshot_id=provider_snapshot_id,
            reserved_by=reserved_by,
            implementation_report=implementation_report,
            now=now,
        )


def _normalize_repository(value) -> str | None:
    if not isinstance(value, str) or not _REPO_RE.fullmatch(value):
        return None
    owner, repo = value.split("/", 1)
    if owner in {".", ".."} or repo in {".", ".."}:
        return None
    if any(ch.isspace() or ord(ch) < 32 for ch in value):
        return None
    return value


def _validate_owner_pr_numbers(
    pr_numbers, max_candidates: int
) -> tuple[int, ...]:
    if not isinstance(pr_numbers, (tuple, list)) or not pr_numbers:
        raise MembershipResolutionError(INVALID_RESOLUTION_REQUEST)
    if len(pr_numbers) > max_candidates:
        raise MembershipResolutionError(INVALID_RESOLUTION_REQUEST)
    ordered: list[int] = []
    for number in pr_numbers:
        if not isinstance(number, int) or isinstance(number, bool) or number <= 0:
            raise MembershipResolutionError(INVALID_RESOLUTION_REQUEST)
        ordered.append(number)
    if len(set(ordered)) != len(ordered):
        raise MembershipResolutionError(DUPLICATE_PR_MEMBERSHIP)
    return tuple(sorted(ordered))
