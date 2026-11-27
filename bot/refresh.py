"""Automatic refresh of the rendered Telegram conversation view.

The manual refresh button used the same `open:<id>` callback as ordinary opening.
This module preserves that fetch/render path for a background worker:

- ownership, tombstone, and metadata authorization use the existing
  `files.authorize_conversation_detailed` implementation;
- the latest prompt, agent message, and FinishAction report come from the existing
  `OpenHandsClient.get_last_exchange` implementation;
- rendering reuses `messages.format_conversation_view` and
  `keyboards.conversation_actions`;
- scheduling is persisted in SQLite (`conversation_views`) so restart recovery does
  not depend on in-memory tasks.

Polling is intentionally separate from `watched`: an opened conversation is not a
follow-up, and automatic refresh must never alter `last_accessed` or the user's
default conversation. A single worker owns the refresh table and leases one row at a
time, so the same view cannot be refreshed concurrently.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone

from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden, RetryAfter, TelegramError

from . import keyboards as kb
from .db import ConversationView
from .errors import ApiError
from .files import FileStatus, IdentityCache, authorize_conversation_detailed
from .messages import escape_html, format_conversation_view, get_status, is_terminal
from .notifier import _retry_after_seconds
from .outbox import _BaseWorker, is_permanent

log = logging.getLogger(__name__)

REFRESH_INTERVAL_SECONDS = 35
MAX_REFRESH_BACKOFF_SECONDS = 15 * 60
REFRESH_LEASE_SECONDS = 120

_PERMANENT_EDIT_MARKERS = (
    "message to edit not found",
    "message can't be edited",
    "message_id_invalid",
    "chat not found",
    "bot was blocked",
    "not enough rights",
    "have no rights",
)


def view_fingerprint(text: str, markup) -> str:
    """Stable digest of the rendered text and keyboard.

    Telegram cannot tell us whether an edit is redundant, so this is the local
    no-op guard. It is derived only from the exact content we render.
    """
    try:
        keyboard = markup.to_dict() if markup is not None else None
    except Exception:  # noqa: BLE001 — fingerprint must never break rendering
        keyboard = None
    payload = json.dumps(
        {"text": text, "keyboard": keyboard},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ConversationRefreshService:
    def __init__(
        self,
        client,
        db,
        bot,
        *,
        identity: IdentityCache | None = None,
        mini_app_url: str = "",
        files_cb_factory=None,
        clock=None,
    ) -> None:
        self.client = client
        self.db = db
        self.bot = bot
        self._identity = identity or IdentityCache(client)
        self._mini_app_url = mini_app_url
        self._files_cb_factory = files_cb_factory
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._worker: ConversationRefreshWorker | None = None

    def attach_worker(self, worker: "ConversationRefreshWorker") -> None:
        self._worker = worker

    def now(self) -> datetime:
        value = self._clock()
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    def now_iso(self) -> str:
        return self.now().astimezone(timezone.utc).isoformat()

    def deadline(self, seconds: float) -> str:
        return (self.now() + timedelta(seconds=seconds)).astimezone(timezone.utc).isoformat()

    def wake(self) -> None:
        if self._worker is not None:
            self._worker.wake()

    def record_view(
        self,
        *,
        telegram_id: int,
        conversation_id: str,
        chat_id: int,
        message_id: int,
        text: str,
        markup,
        terminal: bool,
    ) -> None:
        """Record a view that was just rendered by an explicit open action.

        The open itself already fetched fresh data, so the next periodic check is one
        full interval away. A terminal view is stored inactive.
        """
        if not self._valid_target(telegram_id, chat_id, message_id):
            return
        fingerprint = view_fingerprint(text, markup)
        next_check = None if terminal else self.deadline(REFRESH_INTERVAL_SECONDS)
        try:
            self.db.upsert_conversation_view(
                telegram_id=telegram_id,
                conversation_id=conversation_id,
                chat_id=chat_id,
                message_id=message_id,
                last_fingerprint=fingerprint,
                active=not terminal,
                next_check_at=next_check,
                now=self.now_iso(),
            )
        except Exception as exc:  # noqa: BLE001 — view tracking must not break opening
            log.warning(
                "تعذّر تسجيل عرض الشات %s للتحديث التلقائي (%s)",
                conversation_id, type(exc).__name__,
            )
            return
        if not terminal:
            self.wake()

    def request_immediate(self, conversation_id: str, chat_id: int | None = None) -> None:
        """Mark an existing view due after a confirmed prompt POST.

        No target means the view was not opened after this feature was deployed; no
        synthetic message is created.
        """
        try:
            changed = self.db.request_conversation_view_refresh(
                conversation_id, chat_id=chat_id, now=self.now_iso()
            )
        except Exception as exc:  # noqa: BLE001 — confirmation must not become failure
            log.warning(
                "تعذّر جدولة تحديث فوري للشات %s (%s)",
                conversation_id, type(exc).__name__,
            )
            return
        if changed:
            self.wake()

    async def refresh(self, target: ConversationView) -> None:
        """Fetch fresh data, edit only on change, and persist the next schedule."""
        try:
            conv, status, _message, auth_exc = await authorize_conversation_detailed(
                self.client, self._identity, target.conversation_id, self.db
            )
            if conv is None:
                if status is FileStatus.UPSTREAM_ERROR and not (
                    auth_exc is not None and is_permanent(auth_exc)
                ):
                    self._defer(target, "فشل مؤقت في تفويض الشات")
                else:
                    self._deactivate(target)
                return

            try:
                user_text, reply = await self.client.get_last_exchange(target.conversation_id)
            except ApiError as exc:
                if is_permanent(exc):
                    self._deactivate(target)
                else:
                    self._defer(target, "فشل مؤقت في جلب آخر تبادل")
                return

            watched = self.db.is_watched(target.conversation_id)
            text, reply_cut = format_conversation_view(conv, user_text, reply)
            files_cb = (
                self._files_cb_factory(target.conversation_id)
                if self._files_cb_factory is not None
                else None
            )
            try:
                markup = kb.conversation_actions(
                    target.conversation_id,
                    watched,
                    has_reply=reply is not None,
                    reply_cut=reply_cut,
                    mini_app_url=self._mini_app_url,
                    files_cb=files_cb,
                )
            except ValueError:
                # A conversation id that cannot fit Telegram callback limits is a
                # permanent rendering failure, not a transient upstream failure.
                self._deactivate(target)
                return
            fingerprint = view_fingerprint(text, markup)
            terminal = is_terminal(get_status(conv))

            if fingerprint != target.last_fingerprint:
                outcome, retry_after = await self._edit(target, text, markup)
                if outcome == "retry":
                    self._defer(target, "Telegram RetryAfter", retry_after=retry_after)
                    return
                if outcome == "permanent":
                    self._deactivate(target)
                    return
                if outcome == "transient":
                    self._defer(target, "فشل مؤقت في تعديل رسالة تيليجرام")
                    return

            self.db.finish_conversation_view_refresh(
                telegram_id=target.telegram_id,
                conversation_id=target.conversation_id,
                last_fingerprint=fingerprint,
                active=not terminal,
                next_check_at=None if terminal else self.deadline(REFRESH_INTERVAL_SECONDS),
                now=self.now_iso(),
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — one conversation must not kill the worker
            log.warning(
                "خطأ غير متوقع في تحديث الشات %s (%s)",
                target.conversation_id, type(exc).__name__,
            )
            self._defer(target, "خطأ غير متوقع")

    async def _edit(self, target: ConversationView, text: str, markup) -> tuple[str, float | None]:
        try:
            await self.bot.edit_message_text(
                chat_id=target.chat_id,
                message_id=target.message_id,
                text=escape_html(text),
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
            return "ok", None
        except RetryAfter as exc:
            return "retry", _retry_after_seconds(exc)
        except (BadRequest, Forbidden) as exc:
            message = str(exc).lower()
            if "not modified" in message:
                return "ok", None
            if any(marker in message for marker in _PERMANENT_EDIT_MARKERS):
                return "permanent", None
            return "transient", None
        except (TelegramError, asyncio.TimeoutError):
            return "transient", None

    def _defer(
        self,
        target: ConversationView,
        reason: str,
        *,
        retry_after: float | None = None,
    ) -> None:
        failures = target.failures + 1
        delay = (
            min(max(float(retry_after), 1.0), float(MAX_REFRESH_BACKOFF_SECONDS))
            if retry_after is not None
            else self._backoff_delay(failures)
        )
        try:
            self.db.defer_conversation_view_refresh(
                telegram_id=target.telegram_id,
                conversation_id=target.conversation_id,
                next_check_at=self.deadline(delay),
                now=self.now_iso(),
            )
        except Exception as exc:  # noqa: BLE001 — DB failure must not become success
            log.warning(
                "تعذّر تأجيل تحديث الشات %s (%s) — %s",
                target.conversation_id, type(exc).__name__, reason,
            )

    def _deactivate(self, target: ConversationView) -> None:
        try:
            self.db.deactivate_conversation_view(
                target.telegram_id, target.conversation_id, self.now_iso()
            )
        except Exception as exc:  # noqa: BLE001 — DB failure must not become success
            log.warning(
                "تعذّر إيقاف تحديث الشات %s (%s)",
                target.conversation_id, type(exc).__name__,
            )

    @staticmethod
    def _backoff_delay(failures: int) -> float:
        exponent = min(max(int(failures), 1) - 1, 5)
        return min(
            float(REFRESH_INTERVAL_SECONDS) * (2 ** exponent),
            float(MAX_REFRESH_BACKOFF_SECONDS),
        )

    @staticmethod
    def _valid_target(telegram_id, chat_id, message_id) -> bool:
        return all(
            isinstance(value, int) and not isinstance(value, bool) and value > 0
            for value in (telegram_id, chat_id, message_id)
        )


class ConversationRefreshWorker(_BaseWorker):
    """Single owner of the persisted conversation-view refresh schedule."""

    def __init__(
        self,
        service: ConversationRefreshService,
        *,
        poll_interval: float = 1.0,
        max_idle: float = float(REFRESH_INTERVAL_SECONDS),
    ) -> None:
        super().__init__(
            service.client, service.db, service.bot,
            poll_interval=poll_interval, max_idle=max_idle,
        )
        self._service = service
        service.attach_worker(self)

    def _claim(self):
        now = self._service.now_iso()
        return self._service.db.claim_due_conversation_view(
            now, self._service.deadline(REFRESH_LEASE_SECONDS)
        )

    async def _process(self, item) -> None:
        await self._service.refresh(item)

    def _is_retry_pending(self, item) -> bool:
        row = self._service.db.get_conversation_view(item.telegram_id, item.conversation_id)
        return bool(row is not None and row.active and row.failures > 0)

    def _due_delay(self) -> float:
        remaining = self._service.db.seconds_until_next_conversation_refresh(
            self._service.now_iso()
        )
        if remaining is None:
            return self._max_idle
        return max(0.05, min(remaining, self._max_idle))

    def _next_delay(self) -> float:
        if self._consecutive_failures:
            return super()._next_delay()
        return self._due_delay()

    def _idle_delay(self) -> float:
        return self._due_delay()
