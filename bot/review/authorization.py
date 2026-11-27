"""D-03 current-owner revalidation for review execution and delivery.

This module is intentionally a read-only policy check. It does not start workers,
call providers, send Telegram messages, or mutate review state. Every caller must
revalidate at the point where the protected action is about to happen; no cached
authorization result is accepted.
"""
from __future__ import annotations

from bot.db import (
    AUTO_REVIEW_LIFECYCLE_ACTIVE,
    AUTO_REVIEW_LIFECYCLE_DELIVERY_PENDING,
    AUTO_REVIEW_LIFECYCLE_QUEUED,
    AUTO_REVIEW_LIFECYCLE_RETRY_WAIT,
    AUTO_REVIEW_STAGE_DELIVERY,
    AUTO_REVIEW_STATUS_RESERVED,
)

OWNER_CONFIG_MISSING = "owner_config_missing"
OWNER_CONFIG_MALFORMED = "owner_config_malformed"
CYCLE_MISSING = "review_cycle_missing"
CYCLE_NOT_EXECUTABLE = "review_cycle_not_executable"
CYCLE_CHAT_MISSING = "review_cycle_chat_missing"
OWNER_CHAT_MISMATCH = "review_owner_chat_mismatch"
DELIVERY_TARGET_MISMATCH = "review_delivery_target_mismatch"
DELIVERY_CONVERSATION_MISMATCH = "review_delivery_conversation_mismatch"
CONVERSATION_DELETED = "review_conversation_deleted"
CONVERSATION_NOT_WATCHED = "review_conversation_not_watched"
WATCHED_CHAT_MISSING = "review_watched_chat_missing"
WATCHED_CHAT_MISMATCH = "review_watched_chat_mismatch"
WATCHED_OWNER_MISMATCH = "review_watched_owner_mismatch"
AUTHORIZATION_DATABASE_UNAVAILABLE = "review_authorization_database_unavailable"

_EXECUTION_LIFECYCLES = frozenset(
    (AUTO_REVIEW_LIFECYCLE_QUEUED, AUTO_REVIEW_LIFECYCLE_ACTIVE, AUTO_REVIEW_LIFECYCLE_RETRY_WAIT)
)
_DELIVERY_LIFECYCLES = frozenset((AUTO_REVIEW_LIFECYCLE_DELIVERY_PENDING,))


class ReviewAuthorizationError(RuntimeError):
    """Fail-closed authorization error with a safe, secret-free reason code."""

    def __init__(self, code: str, *, retryable: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


def revalidate_review_authorization(
    db,
    *,
    owner_id,
    cycle,
    target_chat_id=None,
    phase: str = "execution",
) -> None:
    """Revalidate the current owner and persisted conversation relationships.

    ``phase`` is ``execution`` before a provider stage or ``delivery`` before a
    Telegram report send. The caller must pass the actual delivery target in the
    delivery phase; ``cycle.chat_id`` alone is not proof of the target.
    """
    if phase not in ("execution", "delivery"):
        raise ReviewAuthorizationError(CYCLE_NOT_EXECUTABLE)

    if owner_id is None or owner_id == 0:
        raise ReviewAuthorizationError(OWNER_CONFIG_MISSING)
    if not isinstance(owner_id, int) or isinstance(owner_id, bool) or owner_id < 0:
        raise ReviewAuthorizationError(OWNER_CONFIG_MALFORMED)

    if cycle is None:
        raise ReviewAuthorizationError(CYCLE_MISSING)
    if cycle.status != AUTO_REVIEW_STATUS_RESERVED:
        raise ReviewAuthorizationError(CYCLE_NOT_EXECUTABLE)
    allowed_lifecycles = (
        _DELIVERY_LIFECYCLES if phase == "delivery" else _EXECUTION_LIFECYCLES
    )
    if cycle.lifecycle_state not in allowed_lifecycles:
        raise ReviewAuthorizationError(CYCLE_NOT_EXECUTABLE)
    if phase == "delivery" and cycle.stage != AUTO_REVIEW_STAGE_DELIVERY:
        raise ReviewAuthorizationError(CYCLE_NOT_EXECUTABLE)

    if (
        not isinstance(cycle.chat_id, int)
        or isinstance(cycle.chat_id, bool)
        or cycle.chat_id <= 0
    ):
        raise ReviewAuthorizationError(CYCLE_CHAT_MISSING)
    if cycle.chat_id != owner_id:
        raise ReviewAuthorizationError(OWNER_CHAT_MISMATCH)

    if phase == "delivery":
        if (
            not isinstance(target_chat_id, int)
            or isinstance(target_chat_id, bool)
            or target_chat_id <= 0
        ):
            raise ReviewAuthorizationError(DELIVERY_TARGET_MISMATCH)
        if target_chat_id != cycle.chat_id or target_chat_id != owner_id:
            raise ReviewAuthorizationError(DELIVERY_TARGET_MISMATCH)

    try:
        deleted = db.is_deleted_with_retry(cycle.conversation_id)
    except Exception as exc:  # noqa: BLE001 - a read failure is never authorization success
        raise ReviewAuthorizationError(
            AUTHORIZATION_DATABASE_UNAVAILABLE, retryable=True
        ) from exc
    if deleted:
        raise ReviewAuthorizationError(CONVERSATION_DELETED)

    try:
        watched = db.get_watched(cycle.conversation_id)
    except Exception as exc:  # noqa: BLE001 - fail closed, do not infer missing ownership
        raise ReviewAuthorizationError(
            AUTHORIZATION_DATABASE_UNAVAILABLE, retryable=True
        ) from exc
    if watched is None:
        raise ReviewAuthorizationError(CONVERSATION_NOT_WATCHED)
    if (
        not isinstance(watched.chat_id, int)
        or isinstance(watched.chat_id, bool)
        or watched.chat_id <= 0
    ):
        raise ReviewAuthorizationError(WATCHED_CHAT_MISSING)
    if watched.chat_id != owner_id:
        raise ReviewAuthorizationError(WATCHED_OWNER_MISMATCH)
    if watched.chat_id != cycle.chat_id:
        raise ReviewAuthorizationError(WATCHED_CHAT_MISMATCH)
