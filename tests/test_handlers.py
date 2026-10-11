import asyncio
from types import SimpleNamespace

import bot.handlers as h
from bot.db import Database


class FakeMessage:
    def __init__(self):
        self.replies = []

    async def reply_text(self, text, **kw):
        self.replies.append(text)


class FakeQuery:
    def __init__(self):
        self.edits = []
        self.message = SimpleNamespace(chat_id=99)

    async def answer(self):
        pass

    async def edit_message_text(self, text, **kw):
        self.edits.append(text)


def make_update(user_id, text="hi"):
    msg = FakeMessage()
    msg.text = text
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_chat=SimpleNamespace(id=99),
        message=msg,
        callback_query=None,
    )


class FakeConfig:
    def __init__(self, allowed_id):
        self.allowed_telegram_ids = frozenset({allowed_id})
        self.owner_id = allowed_id
        self.openhands_base_url = "https://app.all-hands.dev"

    def is_allowed(self, user_id):
        return user_id in self.allowed_telegram_ids


def make_context(allowed_id, tmp_path, client=None):
    ctx = SimpleNamespace()
    ctx.bot_data = {
        "config": FakeConfig(allowed_id),
        "db": Database(str(tmp_path / "t.sqlite3")),
        "client": client,
    }
    ctx.bot = SimpleNamespace(sent=[], send_message=None)
    return ctx


def test_handle_text_ignores_non_owner(tmp_path):
    ctx = make_context(1, tmp_path)
    update = make_update(999)
    asyncio.run(h.handle_text(update, ctx))
    assert update.message.replies == []


def test_handle_text_owner_without_state_gets_hint(tmp_path):
    ctx = make_context(1, tmp_path)
    update = make_update(1)
    asyncio.run(h.handle_text(update, ctx))
    assert len(update.message.replies) == 1
    assert "/start" in update.message.replies[0]


def test_reply_acks_instantly_then_background(tmp_path, monkeypatch):
    ctx = make_context(1, tmp_path)
    ctx.bot_data["db"].set_awaiting(1, "conv-1", "reply")
    update = make_update(1, text="برومت")

    scheduled = []

    def fake_create_task(coro):
        scheduled.append(coro)
        coro.close()
        return None

    monkeypatch.setattr(asyncio, "create_task", fake_create_task)
    asyncio.run(h.handle_text(update, ctx))

    assert update.message.replies == ["وصل ✅"]
    assert len(scheduled) == 1
    # الحالة اتشالت بعد الإرسال
    assert ctx.bot_data["db"].get_awaiting(1) == (None, None)


def test_start_ignores_non_owner(tmp_path):
    ctx = make_context(1, tmp_path)
    update = make_update(999)
    asyncio.run(h.start(update, ctx))
    assert update.message.replies == []


def test_start_owner_gets_menu(tmp_path):
    ctx = make_context(1, tmp_path)
    update = make_update(1)
    asyncio.run(h.start(update, ctx))
    assert len(update.message.replies) == 1
