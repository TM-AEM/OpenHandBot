"""Focused tests for `/chat` and durable last-accessed conversation tracking."""
from __future__ import annotations

import asyncio

from bot import update_outcomes as uo
from bot.app import BOT_COMMANDS
from bot.db import Database
import bot.handlers as h

from tests.test_4b import OpenClient, Q, cb_update
from tests.test_handlers import make_context, make_update

OWNER = 1


def _open(ctx, conversation_id: str, *, title: str = "شات") -> None:
    ctx.bot_data["client"] = OpenClient(
        {"id": conversation_id, "title": title, "execution_status": "finished"}
    )
    asyncio.run(h.open_conversation(cb_update(Q(f"open:{conversation_id}")), ctx))


def _chat(ctx, user_id: int = OWNER):
    update = make_update(user_id, "/chat")
    asyncio.run(h.chat(update, ctx))
    return update


def test_chat_opens_last_accessed_conversation(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    _open(ctx, "A", title="الأول")
    _open(ctx, "B", title="الأخير")

    update = _chat(ctx)

    assert ctx.bot_data["db"].get_awaiting(OWNER) == ("B", "route")
    assert ctx.bot_data["db"].get_last_accessed_conversation(OWNER) == "B"
    assert update.message.replies
    assert "B" not in update.message.replies[0]  # لا نعرض IDs داخلية


def test_opening_another_conversation_updates_last_accessed(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    _open(ctx, "A")
    assert ctx.bot_data["db"].get_last_accessed_conversation(OWNER) == "A"

    _open(ctx, "B")
    assert ctx.bot_data["db"].get_last_accessed_conversation(OWNER) == "B"


def test_chat_does_not_create_conversation_or_send_prompt(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    _open(ctx, "A")

    _chat(ctx)

    assert ctx.bot_data["db"].count_outbox() == 0
    assert ctx.bot_data["db"].get_awaiting(OWNER) == ("A", "route")


def test_chat_without_history_points_to_start(tmp_path):
    ctx = make_context(OWNER, tmp_path)

    update = _chat(ctx)

    assert update.message.replies
    assert "مفيش شات سابق" in update.message.replies[0]
    assert "/start" in update.message.replies[0]
    assert ctx.bot_data["db"].get_awaiting(OWNER) == (None, None)


def test_chat_clears_inaccessible_last_conversation(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    _open(ctx, "A")
    ctx.bot_data["client"] = OpenClient(None)  # آخر شات مابقاش موجود/متاح

    update = _chat(ctx)

    assert update.message.replies
    assert "مش موجود" in update.message.replies[0]
    assert ctx.bot_data["db"].get_last_accessed_conversation(OWNER) is None
    # لا نبدّل التوجيه الحالي ولا نختار شاتًا آخر بصمت.
    assert ctx.bot_data["db"].get_awaiting(OWNER) == ("A", "route")


def test_chat_owner_isolation(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    ctx.bot_data["db"].set_last_accessed_conversation(OWNER, "A")

    update = _chat(ctx, user_id=999)

    assert update.message.replies == []
    assert ctx.bot_data["db"].get_last_accessed_conversation(OWNER) == "A"
    assert ctx.bot_data["db"].get_last_accessed_conversation(999) is None


def test_last_accessed_survives_database_reopen(tmp_path):
    db_path = str(tmp_path / "restart.sqlite3")
    db = Database(db_path)
    db.set_last_accessed_conversation(OWNER, "A")
    db.close()

    reopened = Database(db_path)
    try:
        assert reopened.get_last_accessed_conversation(OWNER) == "A"
    finally:
        reopened.close()


def test_start_clears_route_but_chat_restores_last_accessed(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    _open(ctx, "A")

    asyncio.run(h.start(make_update(OWNER, "/start"), ctx))
    assert ctx.bot_data["db"].get_awaiting(OWNER) == (None, None)

    _chat(ctx)
    assert ctx.bot_data["db"].get_awaiting(OWNER) == ("A", "route")


def test_reply_selection_updates_last_accessed(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    ctx.bot_data["client"] = OpenClient(
        {"id": "B", "title": "B", "execution_status": "finished"}
    )
    update = cb_update(Q("reply:B"))
    update.update_id = 9001

    asyncio.run(h.reply_prompt(update, ctx))

    assert ctx.bot_data["db"].get_last_accessed_conversation(OWNER) == "B"
    assert ctx.bot_data["db"].get_awaiting(OWNER) == ("B", "reply")
    assert ctx.bot_data["db"].update_outcome(9001) == uo.DURABLE_COMPLETED


def test_start_behavior_unchanged(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    _open(ctx, "A")
    update = make_update(OWNER, "/start")
    update.update_id = 9101

    asyncio.run(h.start(update, ctx))

    assert update.message.replies
    assert ctx.bot_data["db"].get_awaiting(OWNER) == (None, None)
    assert ctx.bot_data["db"].update_outcome(9101) == uo.EXPLICITLY_IGNORED


def test_chat_without_history_does_not_select_arbitrary_conversation(tmp_path):
    class _UnexpectedClient:
        async def get_conversations(self, _ids):
            raise AssertionError("no remote call should happen without history")

    ctx = make_context(OWNER, tmp_path)
    ctx.bot_data["client"] = _UnexpectedClient()

    update = _chat(ctx)

    assert "مفيش شات سابق" in update.message.replies[0]
    assert ctx.bot_data["db"].get_awaiting(OWNER) == (None, None)


def test_chat_command_registered_above_start(tmp_path):
    names = [name for name, _ in BOT_COMMANDS]
    assert names[0] == "chat"
    assert names[1] == "start"


def test_chat_help_text_and_existing_commands_intact():
    assert "/chat" in h.HELP_TEXT
    assert h.HELP_TEXT.index("/chat") < h.HELP_TEXT.index("/start")
    for command in (
        "/start",
        "/app",
        "/help",
        "/notifications",
        "/cancel",
        "/attachments",
        "/attachments_clear",
        "/attachments_cancel",
        "/outbox",
        "/outbox_status",
        "/outbox_discard",
        "/outbox_mark_sent",
    ):
        assert command in h.HELP_TEXT
