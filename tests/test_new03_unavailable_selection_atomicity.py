"""NEW-03: unavailable-selection cleanup is one atomic routing-state transition."""
from __future__ import annotations

import asyncio
import sqlite3
import threading
from types import SimpleNamespace

import pytest

from bot import handlers, outbox
from bot.db import Database, OUTBOX_FAILED, OUTBOX_PENDING
from bot.errors import ApiError

OWNER = 1
CID = "A"
OTHER = "B"


class _Bot:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_message(self, chat_id=None, text=None, **kw) -> None:
        self.sent.append(text)


class _NotFoundClient:
    async def get_conversations(self, ids):
        raise ApiError("missing", 404)

    async def resume_sandbox(self, sandbox_id):
        pass

    async def send_message(self, conversation_id, text):
        raise AssertionError("POST must not start for a missing conversation")


class _FailConnection:
    """Raise before executing a selected SQL statement, leaving rollback to the caller."""

    def __init__(self, conn, needle: str) -> None:
        self._conn = conn
        self._needle = needle

    def execute(self, sql, *args, **kwargs):
        if self._needle in sql:
            raise sqlite3.OperationalError("injected NEW-03 cleanup failure")
        return self._conn.execute(sql, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._conn, name)


def _selected_state(db: Database) -> None:
    db.set_last_accessed_conversation(OWNER, CID)
    db.set_awaiting(OWNER, CID, "route", title=CID)


def _claimed(db: Database):
    db.add_outbox(CID, OWNER, "prompt", outbox.now_iso())
    item = db.claim_outbox(outbox.now_iso())
    assert item is not None
    return item


def _assert_selected(db: Database, conversation_id: str = CID) -> None:
    assert db.get_last_accessed_conversation(OWNER) == conversation_id
    assert db.get_awaiting(OWNER) == (conversation_id, "route")


def test_atomic_success_clears_last_accessed_and_awaiting(tmp_path):
    db = Database(str(tmp_path / "success.sqlite3"))
    try:
        _selected_state(db)
        db.clear_unavailable_selection(OWNER, CID)
        assert db.get_last_accessed_conversation(OWNER) is None
        assert db.get_awaiting(OWNER) == (None, None)
    finally:
        db.close()


def test_atomic_success_preserves_unrelated_state_and_pending_batch(tmp_path):
    db = Database(str(tmp_path / "preserve.sqlite3"))
    try:
        _selected_state(db)
        db.set_setting("repo-selection", "owner/repo")
        outbox_id = db.add_outbox(CID, OWNER, "pending", outbox.now_iso())

        db.clear_unavailable_selection(OWNER, CID)

        assert db.get_setting("repo-selection") == "owner/repo"
        item = db.get_outbox(outbox_id)
        assert item is not None
        assert item.conversation_id == CID
        assert item.status == OUTBOX_PENDING
    finally:
        db.close()


def test_newer_selection_is_not_erased_by_stale_cleanup(tmp_path):
    db = Database(str(tmp_path / "stale.sqlite3"))
    try:
        db.set_last_accessed_conversation(OWNER, OTHER)
        db.set_awaiting(OWNER, OTHER, "route", title=OTHER)

        assert outbox._clear_unavailable_selection(db, OWNER, CID) is True

        _assert_selected(db, OTHER)
    finally:
        db.close()


def test_cleanup_preserves_newer_last_accessed_but_clears_old_awaiting(tmp_path):
    db = Database(str(tmp_path / "mixed-reverse.sqlite3"))
    try:
        db.set_last_accessed_conversation(OWNER, OTHER)
        db.set_awaiting(OWNER, CID, "route", title=CID)
        db.pause_routing(OWNER)

        db.clear_unavailable_selection(OWNER, CID)

        assert db.get_last_accessed_conversation(OWNER) == OTHER
        assert db.get_awaiting(OWNER) == (None, None)
        assert db.is_routing_paused(OWNER) is True
    finally:
        db.close()


def test_only_matching_awaiting_target_is_cleared(tmp_path):
    db = Database(str(tmp_path / "mixed.sqlite3"))
    try:
        db.set_last_accessed_conversation(OWNER, CID)
        db.set_awaiting(OWNER, OTHER, "route", title=OTHER)

        db.clear_unavailable_selection(OWNER, CID)

        assert db.get_last_accessed_conversation(OWNER) is None
        assert db.get_awaiting(OWNER) == (OTHER, "route")
    finally:
        db.close()


def test_first_mutation_failure_rolls_back_all_state(tmp_path):
    db = Database(str(tmp_path / "first-fail.sqlite3"))
    try:
        _selected_state(db)
        original = db._conn
        db._conn = _FailConnection(original, "DELETE FROM settings")
        try:
            with pytest.raises(sqlite3.OperationalError, match="injected NEW-03"):
                db.clear_unavailable_selection(OWNER, CID)
        finally:
            db._conn = original
        _assert_selected(db)
    finally:
        db.close()


def test_second_mutation_failure_rolls_back_first_mutation(tmp_path):
    db = Database(str(tmp_path / "second-fail.sqlite3"))
    try:
        _selected_state(db)
        original = db._conn
        db._conn = _FailConnection(original, "UPDATE user_state")
        try:
            with pytest.raises(sqlite3.OperationalError, match="injected NEW-03"):
                db.clear_unavailable_selection(OWNER, CID)
        finally:
            db._conn = original
        _assert_selected(db)
    finally:
        db.close()


class _FailCommitConnection:
    def __init__(self, conn) -> None:
        self._conn = conn

    def commit(self):
        raise sqlite3.OperationalError("injected NEW-03 commit failure")

    def __getattr__(self, name):
        return getattr(self._conn, name)


def test_commit_failure_rolls_back_all_state(tmp_path):
    db = Database(str(tmp_path / "commit-fail.sqlite3"))
    try:
        _selected_state(db)
        original = db._conn
        db._conn = _FailCommitConnection(original)
        try:
            with pytest.raises(sqlite3.OperationalError, match="injected NEW-03 commit"):
                db.clear_unavailable_selection(OWNER, CID)
        finally:
            db._conn = original
        _assert_selected(db)
    finally:
        db.close()


@pytest.mark.parametrize("needle", ["DELETE FROM settings", "UPDATE user_state"])
def test_failed_atomic_cleanup_does_not_emit_unavailable_notice(tmp_path, needle):
    db = Database(str(tmp_path / "no-notice.sqlite3"))
    try:
        _selected_state(db)
        item = _claimed(db)
        original = db._conn
        db._conn = _FailConnection(original, needle)
        bot = _Bot()
        try:
            asyncio.run(outbox._post_claimed(_NotFoundClient(), db, bot, item))
        finally:
            db._conn = original

        assert db.get_outbox(item.id).status == OUTBOX_FAILED
        _assert_selected(db)
        assert outbox._TARGET_UNAVAILABLE_NOTICE not in bot.sent
    finally:
        db.close()


def test_successful_atomic_cleanup_still_emits_existing_notice(tmp_path):
    db = Database(str(tmp_path / "notice.sqlite3"))
    try:
        _selected_state(db)
        item = _claimed(db)
        bot = _Bot()

        asyncio.run(outbox._post_claimed(_NotFoundClient(), db, bot, item))

        assert db.get_outbox(item.id).status == OUTBOX_FAILED
        assert db.get_last_accessed_conversation(OWNER) is None
        assert db.get_awaiting(OWNER) == (None, None)
        assert outbox._TARGET_UNAVAILABLE_NOTICE in bot.sent
    finally:
        db.close()


def test_concurrent_cancel_and_cleanup_serialize(tmp_path):
    path = str(tmp_path / "cancel-race.sqlite3")
    db_cleanup = Database(path)
    db_cancel = Database(path)
    try:
        _selected_state(db_cleanup)
        barrier = threading.Barrier(2)
        results: dict[str, object] = {}
        errors: list[BaseException] = []

        def cleanup():
            try:
                barrier.wait(timeout=5)
                results["cleanup"] = outbox._clear_unavailable_selection(
                    db_cleanup, OWNER, CID
                )
            except BaseException as exc:  # pragma: no cover - surfaced below
                errors.append(exc)

        def cancel():
            try:
                barrier.wait(timeout=5)
                db_cancel.clear_awaiting_and_record_outcome(
                    OWNER,
                    None,
                    outbox.now_iso(),
                    "cancelled",
                    pause_routing=True,
                )
            except BaseException as exc:  # pragma: no cover - surfaced below
                errors.append(exc)

        threads = [threading.Thread(target=cleanup), threading.Thread(target=cancel)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        assert not errors
        assert results["cleanup"] is True
        assert db_cleanup.is_routing_paused(OWNER) is True
        assert db_cleanup.get_last_accessed_conversation(OWNER) is None
        assert db_cleanup.get_awaiting(OWNER) == (None, None)
    finally:
        db_cleanup.close()
        db_cancel.close()


def test_cleanup_and_outbox_finalization_do_not_redirect_pending_batch(tmp_path):
    path = str(tmp_path / "finalize-race.sqlite3")
    db_cleanup = Database(path)
    db_finalize = Database(path)
    try:
        _selected_state(db_cleanup)
        outbox_id = db_cleanup.add_outbox(CID, OWNER, "pending", outbox.now_iso())
        barrier = threading.Barrier(2)
        results: dict[str, object] = {}
        errors: list[BaseException] = []

        def cleanup():
            try:
                barrier.wait(timeout=5)
                results["cleanup"] = outbox._clear_unavailable_selection(
                    db_cleanup, OWNER, CID
                )
            except BaseException as exc:  # pragma: no cover - surfaced below
                errors.append(exc)

        def finalize():
            try:
                barrier.wait(timeout=5)
                results["claimed"] = db_finalize.claim_outbox(outbox.now_iso())
            except BaseException as exc:  # pragma: no cover - surfaced below
                errors.append(exc)

        threads = [threading.Thread(target=cleanup), threading.Thread(target=finalize)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        assert not errors
        assert results["cleanup"] is True
        rows = db_cleanup.list_outbox_by_status(
            "pending"
        ) + db_cleanup.list_outbox_by_status("claimed")
        assert len(rows) == 1
        assert rows[0].id == outbox_id
        assert rows[0].conversation_id == CID
        assert db_cleanup.get_last_accessed_conversation(OWNER) is None
        assert db_cleanup.get_awaiting(OWNER) == (None, None)
    finally:
        db_cleanup.close()
        db_finalize.close()


def test_concurrent_prompt_acceptance_and_cleanup_remain_consistent(tmp_path):
    path = str(tmp_path / "accept-race.sqlite3")
    db_cleanup = Database(path)
    db_accept = Database(path)
    try:
        _selected_state(db_cleanup)
        barrier = threading.Barrier(2)
        results: dict[str, object] = {}
        errors: list[BaseException] = []

        def cleanup():
            try:
                barrier.wait(timeout=5)
                results["cleanup"] = outbox._clear_unavailable_selection(
                    db_cleanup, OWNER, CID
                )
            except BaseException as exc:  # pragma: no cover - surfaced below
                errors.append(exc)

        def accept():
            try:
                barrier.wait(timeout=5)
                results["outbox_id"] = db_accept.add_or_group_outbox(
                    CID,
                    OWNER,
                    "prompt",
                    outbox.now_iso(),
                    update_id=9901,
                    expected_routing=(OWNER, CID),
                )
            except BaseException as exc:  # pragma: no cover - surfaced below
                errors.append(exc)

        threads = [threading.Thread(target=cleanup), threading.Thread(target=accept)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        assert not errors
        assert results["cleanup"] is True
        rows = db_cleanup.list_outbox_by_status(OUTBOX_PENDING)
        assert all(row.conversation_id == CID for row in rows)
        assert db_cleanup.get_last_accessed_conversation(OWNER) is None
        assert db_cleanup.get_awaiting(OWNER) == (None, None)
    finally:
        db_cleanup.close()
        db_accept.close()


def test_handler_deleted_target_uses_atomic_cleanup(monkeypatch):
    class _HandlerDB:
        REMOTE_CONFIRMED = "confirmed"

        def __init__(self) -> None:
            self.cleared: list[tuple[int, str]] = []

        def remote_deletion_state(self, conversation_id):
            return self.REMOTE_CONFIRMED

        def clear_unavailable_selection(self, telegram_id, conversation_id):
            self.cleared.append((telegram_id, conversation_id))

    class _Message:
        def __init__(self) -> None:
            self.text = "prompt"
            self.replies: list[str] = []

        async def reply_text(self, text):
            self.replies.append(text)

    db = _HandlerDB()
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=OWNER),
        effective_chat=SimpleNamespace(id=OWNER),
        message=_Message(),
    )
    context = SimpleNamespace(bot_data={"db": db})

    async def _deleted(_db, _cid):
        return True

    monkeypatch.setattr(handlers, "_is_deleted_with_retry", _deleted)
    monkeypatch.setattr(handlers, "mark_explicitly_ignored", lambda *_a, **_k: None)

    asyncio.run(handlers._send_prompt(update, context, CID, "prompt"))

    assert db.cleared == [(OWNER, CID)]
    assert any("اتحذف" in reply for reply in update.message.replies)
