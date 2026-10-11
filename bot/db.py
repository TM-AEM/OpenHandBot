"""قاعدة بيانات SQLite لحفظ الشاتات المتابَعة وحالة الحوار."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

ACTIVE_STATES = {"finished", "error", "stuck", "waiting_for_confirmation"}


@dataclass
class Watched:
    conversation_id: str
    title: str
    last_state: str | None


class Database:
    def __init__(self, path: str) -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS watched (
                conversation_id TEXT PRIMARY KEY,
                title           TEXT NOT NULL DEFAULT '',
                last_state      TEXT
            );
            CREATE TABLE IF NOT EXISTS user_state (
                telegram_id INTEGER PRIMARY KEY,
                awaiting_conversation_id TEXT,
                awaiting_kind            TEXT,
                pending_repo             TEXT
            );
            """
        )
        self._conn.commit()

    # ----------------------------------------------------------------- watched
    def add_watched(self, conversation_id: str, title: str = "") -> None:
        self._conn.execute(
            "INSERT INTO watched(conversation_id, title) VALUES(?, ?) "
            "ON CONFLICT(conversation_id) DO UPDATE SET title=excluded.title",
            (conversation_id, title),
        )
        self._conn.commit()

    def remove_watched(self, conversation_id: str) -> None:
        self._conn.execute("DELETE FROM watched WHERE conversation_id=?", (conversation_id,))
        self._conn.commit()

    def list_watched(self) -> list[Watched]:
        rows = self._conn.execute(
            "SELECT conversation_id, title, last_state FROM watched"
        ).fetchall()
        return [Watched(r["conversation_id"], r["title"], r["last_state"]) for r in rows]

    def set_last_state(self, conversation_id: str, state: str) -> None:
        self._conn.execute(
            "UPDATE watched SET last_state=? WHERE conversation_id=?", (state, conversation_id)
        )
        self._conn.commit()

    # -------------------------------------------------------------- user state
    def set_awaiting(self, telegram_id: int, conversation_id: str | None, kind: str | None) -> None:
        self._conn.execute(
            "INSERT INTO user_state(telegram_id, awaiting_conversation_id, awaiting_kind) "
            "VALUES(?, ?, ?) ON CONFLICT(telegram_id) DO UPDATE SET "
            "awaiting_conversation_id=excluded.awaiting_conversation_id, "
            "awaiting_kind=excluded.awaiting_kind",
            (telegram_id, conversation_id, kind),
        )
        self._conn.commit()

    def clear_awaiting(self, telegram_id: int) -> None:
        self.set_awaiting(telegram_id, None, None)

    def get_awaiting(self, telegram_id: int) -> tuple[str | None, str | None]:
        row = self._conn.execute(
            "SELECT awaiting_conversation_id, awaiting_kind FROM user_state WHERE telegram_id=?",
            (telegram_id,),
        ).fetchone()
        if not row:
            return None, None
        return row["awaiting_conversation_id"], row["awaiting_kind"]

    def close(self) -> None:
        self._conn.close()
