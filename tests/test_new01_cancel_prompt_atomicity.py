"""Obsolete NEW-01 cancellation regressions replaced after forwarding removal.

The forwarding-only `/cancel` and `cancelroute` controls were removed. These tests keep
the still-relevant acceptance-boundary behavior for ordinary selected-target prompts and
verify that legacy cancellation state cannot block or redirect new messages.
"""
from __future__ import annotations

import asyncio

import bot.handlers as h
from bot.db import Database
from tests.test_handlers import make_context, make_update

OWNER = 1
CID = "A"


def _selected(ctx):
    db = ctx.bot_data["db"]
    db.set_last_accessed_conversation(OWNER, CID)
    return db


def _prompt_update(update_id: int, text: str = "برومت"):
    update = make_update(OWNER, text)
    update.update_id = update_id
    return update


def test_cancel_controls_are_removed():
    assert not hasattr(h, "cancel_route")
    assert not hasattr(h, "cancel_route_button")


def test_legacy_pause_state_does_not_block_ordinary_prompt(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    db = _selected(ctx)
    db.set_setting(f"routing_paused:{OWNER}", "1")

    asyncio.run(h.handle_text(_prompt_update(9101), ctx))

    assert [item.conversation_id for item in db.list_outbox_by_status("pending")] == [CID]


def test_destination_change_during_preparation_rejects_prompt(tmp_path, monkeypatch):
    async def scenario():
        ctx = make_context(OWNER, tmp_path)
        db = _selected(ctx)
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
        release.set()
        await task

        assert db.count_outbox() == 0
        assert prompt.message.replies
        assert "تغيّر الشات المختار" in prompt.message.replies[0]

    asyncio.run(scenario())


def test_rejected_prompt_does_not_reappear_after_restart(tmp_path, monkeypatch):
    async def scenario():
        ctx = make_context(OWNER, tmp_path)
        db = _selected(ctx)
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
        db.set_last_accessed_conversation(OWNER, "B")
        release.set()
        await task
        db.close()

        reopened = Database(str(tmp_path / "t.sqlite3"))
        ctx.bot_data["db"] = reopened
        try:
            later = _prompt_update(9162)
            await h.handle_text(later, ctx)
            assert [item.conversation_id for item in reopened.list_outbox_by_status("pending")] == ["B"]
            assert all("تغيّر الشات المختار" not in text for text in later.message.replies)
        finally:
            reopened.close()

    asyncio.run(scenario())
