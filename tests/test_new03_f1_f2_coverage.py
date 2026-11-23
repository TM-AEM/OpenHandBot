"""NEW-03 coverage: BEGIN IMMEDIATE lock and handler cleanup-failure behavior."""
from __future__ import annotations

import asyncio
import logging
import sqlite3
import threading
from types import SimpleNamespace

from bot import handlers, outbox, update_outcomes
from bot.db import Database

OWNER = 1
CID = "A"
OTHER = "B"


def test_clear_unavailable_selection_holds_begin_immediate_write_lock(tmp_path):
    """Cleanup holds a write reservation before its first write; a competing writer waits.

    The hook pauses cleanup after BEGIN/reads but before DELETE. With BEGIN IMMEDIATE the
    competing BEGIN IMMEDIATE must fail. With a deferred BEGIN it succeeds, which is the
    mutation this test is designed to detect.
    """
    path = str(tmp_path / "f1-lock.sqlite3")
    db_cleanup = Database(path)
    db_writer = Database(path)
    cleanup_inside = threading.Event()
    allow_cleanup = threading.Event()
    errors: list[BaseException] = []
    try:
        db_cleanup.set_last_accessed_conversation(OWNER, CID)
        db_cleanup.set_awaiting(OWNER, CID, "route", title=CID)
        original_delete = db_cleanup._delete_setting_nocommit

        def blocked_delete(key: str) -> None:
            cleanup_inside.set()
            if not allow_cleanup.wait(timeout=5):
                raise AssertionError("cleanup was not released")
            original_delete(key)

        db_cleanup._delete_setting_nocommit = blocked_delete

        def cleanup() -> None:
            try:
                db_cleanup.clear_unavailable_selection(OWNER, CID)
            except BaseException as exc:  # pragma: no cover - asserted below
                errors.append(exc)

        thread = threading.Thread(target=cleanup, daemon=True)
        thread.start()
        assert cleanup_inside.wait(timeout=5)

        db_writer._conn.execute("PRAGMA busy_timeout=50")
        locked_error = None
        writer_started = False
        try:
            try:
                db_writer._conn.execute("BEGIN IMMEDIATE")
                writer_started = True
            except sqlite3.OperationalError as exc:
                locked_error = exc
        finally:
            allow_cleanup.set()
            if writer_started:
                db_writer._conn.rollback()
            thread.join(timeout=5)

        assert not thread.is_alive()
        assert not errors
        assert isinstance(locked_error, sqlite3.OperationalError), (
            "competing writer entered while cleanup held BEGIN IMMEDIATE"
        )
        assert db_writer.get_last_accessed_conversation(OWNER) is None
        assert db_writer.get_awaiting(OWNER) == (None, None)

        # The same writer must be able to proceed once cleanup has committed.
        db_writer._conn.execute("BEGIN IMMEDIATE")
        key = db_writer._last_accessed_key(OWNER)
        db_writer._conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, OTHER),
        )
        db_writer._conn.commit()
        assert db_writer.get_last_accessed_conversation(OWNER) == OTHER
    finally:
        db_cleanup.close()
        db_writer.close()


def test_handler_cleanup_failure_logs_and_preserves_routing(
    tmp_path, monkeypatch, caplog
):
    """A real handler deletion path survives cleanup failure without false success."""
    db = Database(str(tmp_path / "f2-handler.sqlite3"))
    try:
        db.delete_conversation(CID, outbox.now_iso(), remote_confirmed=True)
        db.set_last_accessed_conversation(OWNER, CID)
        db.set_awaiting(OWNER, CID, "route", title=CID)

        calls: list[tuple[int, str]] = []

        def failing_cleanup(telegram_id: int, conversation_id: str) -> None:
            calls.append((telegram_id, conversation_id))
            raise sqlite3.OperationalError("injected F2 cleanup failure")

        monkeypatch.setattr(db, "clear_unavailable_selection", failing_cleanup)

        class _Message:
            def __init__(self) -> None:
                self.text = "prompt"
                self.replies: list[str] = []

            async def reply_text(self, text: str) -> None:
                self.replies.append(text)

        update = SimpleNamespace(
            update_id=7001,
            effective_user=SimpleNamespace(id=OWNER),
            effective_chat=SimpleNamespace(id=OWNER),
            message=_Message(),
        )
        context = SimpleNamespace(bot_data={"db": db})

        with caplog.at_level(logging.ERROR):
            asyncio.run(handlers._send_prompt(update, context, CID, "prompt"))

        assert calls == [(OWNER, CID)]
        assert update.message.replies == [
            "الشات ده اتحذف — مش ممكن نبعت له رسايل. افتح شات تاني."
        ]
        assert outbox._TARGET_UNAVAILABLE_NOTICE not in update.message.replies
        assert db.get_last_accessed_conversation(OWNER) == CID
        assert db.get_awaiting(OWNER) == (CID, "route")
        assert db.is_deleted(CID) is True
        assert db.remote_deletion_state(CID) == db.REMOTE_CONFIRMED
        assert db.count_outbox() == 0
        assert db.update_outcome(7001) == update_outcomes.EXPLICITLY_IGNORED
        assert any(
            "تعذّر مسح هدف التوجيه المحذوف" in record.message
            for record in caplog.records
        )
    finally:
        db.close()
