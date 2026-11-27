"""Read-only R3 evidence collection for one PR membership (R5).

No GitHub request is made unless a caller explicitly constructs a GitHub client and
invokes this collector. Tests inject a fake client or a fake collector.
"""
from __future__ import annotations

from typing import Protocol

from bot.db import AutoReviewMembership
from bot.review.ci_contract import jobs_complete
from bot.review.evidence import (
    EvidenceError,
    ReviewEvidence,
    diff_text_from_compare,
)
from bot.review.eligibility import repository_eligibility_code
from bot.review.github import (
    GitHubClient,
    GitHubError,
    GitHubNotFoundError,
    GitHubRedirectError,
    GitHubRepoNotAllowed,
    GitHubRepositoryIdentityMismatch,
    RepositoryIdentity,
)


class EvidenceCollectionError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ReviewEvidenceCollector(Protocol):
    async def collect(
        self,
        membership: AutoReviewMembership,
        *,
        architecture_decisions: tuple[str, ...],
        max_input_chars: int,
    ) -> ReviewEvidence: ...


class GitHubEvidenceCollector:
    """Collect exact compare/Actions evidence through the R3 read-only client."""

    def __init__(self, client: GitHubClient) -> None:
        if client is None:
            raise EvidenceCollectionError("invalid_github_client")
        self._client = client

    async def collect(
        self,
        membership: AutoReviewMembership,
        *,
        architecture_decisions: tuple[str, ...],
        max_input_chars: int,
    ) -> ReviewEvidence:
        try:
            await self._verify_repository(membership)
            await self._verify_branch(membership)
            compare = await self._client.compare(
                membership.repository_full_name,
                membership.base_sha,
                membership.head_sha,
            )
            if compare.status != "verified":
                raise EvidenceCollectionError(f"compare_{compare.status}")
            if (
                compare.repository.casefold()
                != membership.repository_full_name.casefold()
                or compare.base_sha != membership.base_sha
                or compare.head_sha != membership.head_sha
            ):
                raise EvidenceCollectionError("compare_membership_mismatch")
            runs = await self._client.get_workflow_runs_for_sha(
                membership.repository_full_name, membership.head_sha
            )
            jobs = tuple(
                [
                    await self._client.list_run_jobs(
                        membership.repository_full_name,
                        run.run_id,
                        membership.head_sha,
                    )
                    for run in runs.runs
                ]
            )
            # Re-check after all reads: a branch move or repository eligibility
            # change during collection must not become stale evidence.
            await self._verify_branch(membership)
            await self._verify_repository(membership)
            return ReviewEvidence.from_compare(
                compare,
                diff_text=diff_text_from_compare(compare),
                max_input_chars=max_input_chars,
                branch=membership.branch,
                pr_number=membership.pr_number,
                ci_runs=runs,
                ci_jobs=jobs,
                architecture_decisions=architecture_decisions,
                ci_jobs_complete=jobs_complete(runs, jobs),
            )
        except EvidenceCollectionError:
            raise
        except EvidenceError as exc:
            raise EvidenceCollectionError(exc.code) from exc
        except ValueError as exc:
            raise EvidenceCollectionError("invalid_branch_or_sha") from exc
        except GitHubError as exc:
            raise EvidenceCollectionError(type(exc).__name__) from exc

    async def _verify_repository(self, membership: AutoReviewMembership) -> None:
        try:
            repository = await self._client.get_repository(
                membership.repository_full_name
            )
        except GitHubRepoNotAllowed as exc:
            raise EvidenceCollectionError("repository_not_allowed") from exc
        except GitHubNotFoundError as exc:
            raise EvidenceCollectionError("repository_not_found") from exc
        except GitHubRedirectError as exc:
            raise EvidenceCollectionError("repository_redirect_rejected") from exc
        except GitHubRepositoryIdentityMismatch as exc:
            raise EvidenceCollectionError("repository_rename_ambiguous") from exc
        except GitHubError as exc:
            raise EvidenceCollectionError(type(exc).__name__) from exc
        if not isinstance(repository, RepositoryIdentity):
            raise EvidenceCollectionError("malformed_repository_identity")
        if (
            repository.repository_id != membership.repository_id
            or repository.full_name.casefold()
            != membership.repository_full_name.casefold()
        ):
            raise EvidenceCollectionError("repository_identity_mismatch")
        eligibility = repository_eligibility_code(repository)
        if eligibility is not None:
            raise EvidenceCollectionError(eligibility)

    async def _verify_branch(self, membership: AutoReviewMembership) -> None:
        verification = await self._client.verify_branch_sha(
            membership.repository_full_name,
            membership.branch,
            membership.head_sha,
        )
        if verification.status != "unchanged":
            raise EvidenceCollectionError(f"branch_{verification.status}")
