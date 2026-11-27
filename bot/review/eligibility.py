"""D-06 repository eligibility checks shared by resolution and evidence collection.

Eligibility is deliberately a pure metadata check: the caller must obtain the
identity from the authoritative GitHub client and must also enforce allowlist and
D-03/D-05 checks at its own boundary. A full name is not a permanent identity.
"""
from __future__ import annotations

from bot.review.github import RepositoryIdentity

REPOSITORY_NOT_PRIVATE = "repository_not_private"
REPOSITORY_IS_FORK = "repository_is_fork"
REPOSITORY_ARCHIVED = "repository_archived"
MALFORMED_REPOSITORY_IDENTITY = "malformed_repository_identity"


def repository_eligibility_code(repository: object) -> str | None:
    """Return a safe D-06 reason code, or None when the metadata is eligible."""
    if not isinstance(repository, RepositoryIdentity):
        return MALFORMED_REPOSITORY_IDENTITY
    if repository.private is not True:
        return REPOSITORY_NOT_PRIVATE
    if repository.fork is not False:
        return REPOSITORY_IS_FORK
    if repository.archived is not False:
        return REPOSITORY_ARCHIVED
    return None
