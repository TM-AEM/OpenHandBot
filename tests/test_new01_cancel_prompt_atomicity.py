"""NEW-01: cancellation and prompt acceptance at the outbox boundary.

All tests use the real SQLite-backed handler/outbox path with deterministic barriers.
No Telegram or OpenHands network calls are made.
"""
from __future__ import annotations

import asyncio
import sqlite3
from types import SimpleNamespace

import pytest

import bot.handlers as h
from bot import outbox
from bot.db import Database
from tests.test_handlers import make_context, make_update

OWNER = 1
CID = "A"


def _route(ctx):
    db = ctx.bot_data["db"]
    db.set_last_accessed_conversation(OWNER, CID)
    db.set_awaiting(OWNER, CID, "route", title=CID)
    return db


def _prompt_update(update_id: int, text: str = "برومت"):
    update = make_update(OWNER, text)
    update.update_id = update_id
    return update


def _ack_reply(replies, message_id=700):
    async def reply(text, **kw):
        replies.append(text)
        return SimpleNamespace(message_id=message_id)
    return reply


def test_new01_r1_cancel_committed_during_preparation_rejects_prompt(tmp_path, monkeypatch):
    async def scenario():
        ctx = make_context(OWNER, tmp_path)
        db = _route(ctx)
        started = asyncio.Event()
        release = asyncio.Event()

        async def blocked(_db, _cid):
            started.set()
            await release.wait()
            return False

        monkeypatch.setattr(h, "_is_deleted_with_retry", blocked)
        prompt = _prompt_update(9101)
        cancel = make_update(OWNER, "/cancel")
        cancel.update_id = 9102

        task = asyncio.create_task(h.handle_text(prompt, ctx))
        await started.wait()
        await h.cancel_route(cancel, ctx)
        release.set()
        await task

        assert db.is_routing_paused(OWNER) is True
        assert db.get_awaiting(OWNER) == (None, None)
        assert db.count_outbox() == 0
        assert prompt.message.replies == []

    asyncio.run(scenario())


def test_new01_r1b_reply_state_cancel_during_preparation_rejects_prompt(tmp_path, monkeypatch):
    async def scenario():
        ctx = make_context(OWNER, tmp_path)
        db = ctx.bot_data["db"]
        db.set_last_accessed_conversation(OWNER, CID)
        db.set_awaiting(OWNER, CID, "reply")
        started = asyncio.Event()
        release = asyncio.Event()

        async def blocked(_db, _cid):
            started.set()
            await release.wait()
            return False

        monkeypatch.setattr(h, "_is_deleted_with_retry", blocked)
        prompt = _prompt_update(9105)
        task = asyncio.create_task(h.handle_text(prompt, ctx))
        await started.wait()
        await h.cancel_route(make_update(OWNER, "/cancel"), ctx)
        release.set()
        await task

        assert db.is_routing_paused(OWNER) is True
        assert db.get_awaiting(OWNER) == (None, None)
        assert db.count_outbox() == 0
        assert prompt.message.replies == []

    asyncio.run(scenario())


def test_new01_r2_accepted_prompt_survives_later_cancel(tmp_path):
    async def scenario():
        ctx = make_context(OWNER, tmp_path)
        db = _route(ctx)
        prompt = _prompt_update(9111)
        prompt.message.reply_text = _ack_reply(prompt.message.replies)
        cancel = make_update(OWNER, "/cancel")
        cancel.update_id = 9112

        await h.handle_text(prompt, ctx)
        accepted = db.list_outbox_by_status("pending")
        assert len(accepted) == 1
        assert accepted[0].conversation_id == CID

        await h.cancel_route(cancel, ctx)

        assert db.is_routing_paused(OWNER) is True
        still_accepted = db.list_outbox_by_status("pending")
        assert [item.id for item in still_accepted] == [accepted[0].id]

    asyncio.run(scenario())


def test_new01_r3_concurrent_cancel_and_acceptance_have_serial_order(tmp_path, monkeypatch):
    async def scenario():
        ctx = make_context(OWNER, tmp_path)
        db = _route(ctx)
        prompt_started = asyncio.Event()
        release_prompt = asyncio.Event()

        async def blocked(_db, _cid):
            prompt_started.set()
            await release_prompt.wait()
            return False

        monkeypatch.setattr(h, "_is_deleted_with_retry", blocked)
        prompt = _prompt_update(9121)
        cancel = make_update(OWNER, "/cancel")
        cancel.update_id = 9122
        cancel_committed = asyncio.Event()
        release_cancel = asyncio.Event()

        async def cancel_reply(text, **kw):
            cancel_committed.set()
            await release_cancel.wait()

        cancel.message.reply_text = cancel_reply
        prompt_task = asyncio.create_task(h.handle_text(prompt, ctx))
        await prompt_started.wait()
        cancel_task = asyncio.create_task(h.cancel_route(cancel, ctx))
        await cancel_committed.wait()
        release_prompt.set()
        await prompt_task
        release_cancel.set()
        await cancel_task

        assert db.is_routing_paused(OWNER) is True
        assert db.get_awaiting(OWNER) == (None, None)
        assert db.count_outbox() == 0
        assert prompt.message.replies == []

    asyncio.run(scenario())


def test_new01_r4_destination_change_during_preparation_rejects_prompt(tmp_path, monkeypatch):
    async def scenario():
        ctx = make_context(OWNER, tmp_path)
        db = _route(ctx)
        started = asyncio.Event()
        release = asyncio.Event()

        async def blocked(_db, _cid):
            started.set()
            await release.wait()
            return False

        monkeypatch.setattr(h, "_is_deleted_with_retry", blocked)
        prompt = _prompt_update(9131)
        task = asyncio.create_task(h.handle_text(prompt, ctx))
        await started.wait()
        db.set_last_accessed_conversation(OWNER, "B")
        db.set_awaiting(OWNER, "B", "route", title="B")
        release.set()
        await task

        assert db.count_outbox() == 0
        assert prompt.message.replies
        assert "تغيّر الشات المختار" in prompt.message.replies[0]

    asyncio.run(scenario())


def test_new01_r5_busy_retry_does_not_bypass_pause(tmp_path):
    path = str(tmp_path / "busy.sqlite3")
    db = Database(path)
    writer = Database(path)
    try:
        _route(SimpleNamespace(bot_data={"db": db}))
        db._conn.execute("PRAGMA busy_timeout=0")
        writer._conn.execute("BEGIN IMMEDIATE")
        with pytest.raises(sqlite3.OperationalError):
            db.add_or_group_outbox(
                CID, OWNER, "برومت", outbox.now_iso(),
                update_id=9141, expected_routing=(OWNER, CID),
            )
        writer._conn.rollback()
        writer.close()

        db.pause_routing(OWNER)
        out_id = db.add_or_group_outbox(
            CID, OWNER, "برومت", outbox.now_iso(),
            update_id=9142, expected_routing=(OWNER, CID),
        )
        assert out_id == 0
        assert db.count_outbox() == 0
    finally:
        db.close()


def test_new01_r6_failure_at_acceptance_boundary_does_not_ack(tmp_path):
    class FailInsertConnection:
        def __init__(self, conn):
            self._conn = conn

        def __getattr__(self, name):
            return getattr(self._conn, name)

        def execute(self, sql, *args, **kwargs):
            if "INSERT INTO outbox" in sql:
                raise sqlite3.OperationalError("injected acceptance failure")
            return self._conn.execute(sql, *args, **kwargs)

    async def scenario():
        ctx = make_context(OWNER, tmp_path)
        db = _route(ctx)
        original = db._conn
        prompt = _prompt_update(9151)
        db._conn = FailInsertConnection(original)
        try:
            with pytest.raises(sqlite3.OperationalError):
                await h.handle_text(prompt, ctx)
        finally:
            db._conn = original

        assert prompt.message.replies == []
        assert db.count_outbox() == 0

    asyncio.run(scenario())


def test_new01_r7_rejected_prompt_does_not_reappear_after_restart(tmp_path, monkeypatch):
    async def scenario():
        ctx = make_context(OWNER, tmp_path)
        db = _route(ctx)
        started = asyncio.Event()
        release = asyncio.Event()

        async def blocked(_db, _cid):
            started.set()
            await release.wait()
            return False

        monkeypatch.setattr(h, "_is_deleted_with_retry", blocked)
        prompt = _prompt_update(9161)
        task = asyncio.create_task(h.handle_text(prompt, ctx))
        await started.wait()
        await h.cancel_route(make_update(OWNER, "/cancel"), ctx)
        release.set()
        await task
        db.close()

        reopened = Database(str(tmp_path / "t.sqlite3"))
        ctx.bot_data["db"] = reopened
        try:
            assert reopened.is_routing_paused(OWNER) is True
            later = _prompt_update(9162)
            await h.handle_text(later, ctx)
            assert reopened.count_outbox() == 0
            assert all("وصل ✅" not in text for text in later.message.replies)
            assert any("التوجيه متوقف" in text for text in later.message.replies)
        finally:
            reopened.close()

    asyncio.run(scenario())


def test_new01_r8_duplicate_update_cannot_bypass_cancel_guard(tmp_path, monkeypatch):
    async def scenario():
        ctx = make_context(OWNER, tmp_path)
        db = _route(ctx)
        started = asyncio.Event()
        release = asyncio.Event()

        async def blocked(_db, _cid):
            started.set()
            await release.wait()
            return False

        monkeypatch.setattr(h, "_is_deleted_with_retry", blocked)
        prompt = _prompt_update(9172)
        task = asyncio.create_task(h.handle_text(prompt, ctx))
        await started.wait()
        await h.cancel_route(make_update(OWNER, "/cancel"), ctx)
        release.set()
        await task

        # Retrying the same Telegram update after cancellation must not create a row.
        await h.handle_text(prompt, ctx)

        assert db.count_outbox() == 0
        assert all("وصل ✅" not in text for text in prompt.message.replies)
        assert any("التوجيه متوقف" in text for text in prompt.message.replies)

    asyncio.run(scenario())
