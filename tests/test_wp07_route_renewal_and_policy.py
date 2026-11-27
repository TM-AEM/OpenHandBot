"""OHB2-WP-07 — ordinary text must not create or renew forwarding route state.

The forwarding window was removed. Whitespace and ordinary prompts keep only the persisted
last-accessed target; neither writes a `route` awaiting state.
"""
from __future__ import annotations

import asyncio

import bot.handlers as h


def _ctx(tmp_path):
    return __import__("tests.test_handlers", fromlist=["make_context"]).make_context(1, tmp_path)


def _text_update(text, update_id):
    from types import SimpleNamespace

    msg = SimpleNamespace(text=text, replies=[], edit_text=None)

    async def _reply(t, **kw):
        msg.replies.append(t)
        return msg

    msg.reply_text = _reply
    return SimpleNamespace(
        update_id=update_id,
        effective_user=SimpleNamespace(id=1),
        effective_chat=SimpleNamespace(id=99, type="private"),
        message=msg,
        callback_query=None,
    )


def test_whitespace_does_not_create_route_or_outbox(tmp_path):
    ctx = _ctx(tmp_path)
    db = ctx.bot_data["db"]
    db.set_last_accessed_conversation(1, "c1")

    asyncio.run(h.handle_text(_text_update("   ", 9100), ctx))

    assert db.get_awaiting(1) == (None, None)
    assert db.count_outbox() == 0
    assert db.get_last_accessed_conversation(1) == "c1"


def test_text_uses_last_accessed_without_creating_route_state(tmp_path):
    ctx = _ctx(tmp_path)
    db = ctx.bot_data["db"]
    db.set_last_accessed_conversation(1, "c1")

    asyncio.run(h.handle_text(_text_update("برومت", 9102), ctx))

    assert db.get_awaiting(1) == (None, None)
    assert [item.conversation_id for item in db.list_outbox_by_status("pending")] == ["c1"]
    assert db.get_last_accessed_conversation(1) == "c1"
