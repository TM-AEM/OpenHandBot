"""قاعدة بيانات SQLite لحفظ الشاتات المتابَعة وحالة الحوار."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass
class Watched:
    conversation_id: str
    title: str
    last_state: str | None
    chat_id: int | None = None


class Database:
    def __init__(self, path: str) -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # WAL + busy_timeout عشان الكتابة من الـ handlers والمراقب في وقت واحد
        # ما ترميش "database is locked".
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS watched (
                conversation_id TEXT PRIMARY KEY,
                title           TEXT NOT NULL DEFAULT '',
                last_state      TEXT,
                chat_id         INTEGER
            );
            CREATE TABLE IF NOT EXISTS user_state (
                telegram_id INTEGER PRIMARY KEY,
                awaiting_conversation_id TEXT,
                awaiting_kind            TEXT
            );
            """
        )
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        """يضيف الأعمدة الجديدة لقواعد موجودة من نسخ أقدم."""
        columns = {r["name"] for r in self._conn.execute("PRAGMA table_info(watched)")}
        if "chat_id" not in columns:
            self._conn.execute("ALTER TABLE watched ADD COLUMN chat_id INTEGER")

    # ----------------------------------------------------------------- watched
    def add_watched(self, conversation_id: str, title: str = "", chat_id: int | None = None) -> None:
        self._conn.execute(
            "INSERT INTO watched(conversation_id, title, chat_id) VALUES(?, ?, ?) "
            "ON CONFLICT(conversation_id) DO UPDATE SET title=excluded.title, "
            "chat_id=COALESCE(excluded.chat_id, watched.chat_id)",
            (conversation_id, title, chat_id),
        )
        self._conn.commit()

    def remove_watched(self, conversation_id: str) -> None:
        self._conn.execute("DELETE FROM watched WHERE conversation_id=?", (conversation_id,))
        self._conn.commit()

    def list_watched(self) -> list[Watched]:
        rows = self._conn.execute(
            "SELECT conversation_id, title, last_state, chat_id FROM watched"
        ).fetchall()
        return [
            Watched(r["conversation_id"], r["title"], r["last_state"], r["chat_id"]) for r in rows
        ]

    def is_watched(self, conversation_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM watched WHERE conversation_id=?", (conversation_id,)
        ).fetchone()
        return row is not None

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
