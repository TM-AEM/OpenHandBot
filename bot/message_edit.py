"""Per-Telegram-message edit serialization.

Both the automatic refresh worker and every handler that replaces a tracked
screen must edit one Telegram message through this coordinator. The lock key is
``(chat_id, message_id)``; unrelated messages never block each other.

The coordinator stores only entries with active users. The entry count therefore
tracks concurrently edited messages, not the whole message history. There is
exactly one entry (and one ``asyncio.Lock``) per key in the dictionary; the
synchronous lookup/admission section guarantees no duplicate lock can be created
for a key while a user holds or waits for it.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncIterator

MessageKey = tuple[int, int]


def message_key(chat_id, message_id) -> MessageKey | None:
    """Return a valid Telegram message key, or None when either id is unusable."""
    if (
        isinstance(chat_id, int)
        and not isinstance(chat_id, bool)
        and chat_id != 0
        and isinstance(message_id, int)
        and not isinstance(message_id, bool)
        and message_id > 0
    ):
        return int(chat_id), int(message_id)
    return None


@dataclass
class _Entry:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    users: int = 0


class MessageEditCoordinator:
    """Serialize edits of the same Telegram message in this process."""

    def __init__(self) -> None:
        self._entries: dict[MessageKey, _Entry] = {}

    def active_key_count(self) -> int:
        """Number of message keys currently held or awaited (diagnostics/tests)."""
        return len(self._entries)

    @asynccontextmanager
    async def lock(self, chat_id, message_id) -> AsyncIterator[None]:
        """Hold the edit right for one Telegram message.

        Cancellation while waiting or while holding the lock is safe: ``users``
        is decremented in ``finally`` and the entry is removed as soon as no
        holder or waiter remains. Invalid ids are not tracked and therefore do
        not allocate locks.
        """
        key = message_key(chat_id, message_id)
        if key is None:
            yield
            return
        entry = self._entries.get(key)
        if entry is None:
            entry = _Entry()
            self._entries[key] = entry
        entry.users += 1
        try:
            async with entry.lock:
                yield
        finally:
            entry.users -= 1
            if entry.users == 0 and not entry.lock.locked():
                if self._entries.get(key) is entry:
                    del self._entries[key]


DEFAULT_MESSAGE_EDIT_COORDINATOR = MessageEditCoordinator()


def get_message_edit_coordinator() -> MessageEditCoordinator:
    """Process-wide coordinator shared by handlers and refresh."""
    return DEFAULT_MESSAGE_EDIT_COORDINATOR
