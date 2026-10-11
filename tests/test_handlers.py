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


class FakeClient:
    def __init__(self, items):
        self._items = items

    async def search_conversations(self, limit=20, page_id=None):
        return {"items": self._items[:limit], "next_page_id": None}


def _list_update(user_id, page):
    msg = FakeMessage()
    q = FakeQuery()
    q.data = f"list:{page}"
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_chat=SimpleNamespace(id=99),
        message=msg,
        callback_query=q,
    )


def test_list_conversations_paginates_locally(tmp_path):
    items = [{"id": f"c{i}", "title": f"شات {i}", "execution_status": "running"} for i in range(15)]
    ctx = make_context(1, tmp_path, client=FakeClient(items))

    update = _list_update(1, 0)
    asyncio.run(h.list_conversations(update, ctx))
    first = update.callback_query.edits[-1]
    assert "صفحة 1" in first

    update = _list_update(1, 1)
    asyncio.run(h.list_conversations(update, ctx))
    second = update.callback_query.edits[-1]
    assert "صفحة 2" in second


def test_list_conversations_ignores_non_owner(tmp_path):
    ctx = make_context(1, tmp_path, client=FakeClient([]))
    update = _list_update(999, 0)
    asyncio.run(h.list_conversations(update, ctx))
    assert update.callback_query.edits == []


class DetailClient:
    def __init__(self, conv, files=None, content="", blob=b"zip"):
        self._conv = conv
        self._files = files or []
        self._content = content
        self._blob = blob

    async def get_conversations(self, ids):
        return [self._conv] if self._conv else []

    async def list_files(self, conversation_id, path=""):
        return self._files

    async def read_file(self, conversation_id, file_path):
        return self._content

    async def export_conversation(self, conversation_id):
        return self._blob


class FakeBotWithDocs:
    def __init__(self):
        self.sent = []
        self.documents = []

    async def send_message(self, chat_id=None, text=None, **kw):
        self.sent.append(text)

    async def send_document(self, chat_id=None, document=None, **kw):
        self.documents.append(document)


def _cb_update(user_id, data):
    q = FakeQuery()
    q.data = data
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_chat=SimpleNamespace(id=99),
        message=SimpleNamespace(),
        callback_query=q,
    )


def _ctx_with(tmp_path, client):
    ctx = make_context(1, tmp_path, client=client)
    ctx.bot = FakeBotWithDocs()
    return ctx


def test_show_status_reports_state(tmp_path):
    client = DetailClient({"id": "c1", "title": "شات", "execution_status": "running", "sandbox_status": "RUNNING"})
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "status:c1")
    asyncio.run(h.show_status(update, ctx))
    assert "شغال" in update.callback_query.edits[-1]
    assert "RUNNING" in update.callback_query.edits[-1]


def test_show_cost_reports_metrics(tmp_path):
    client = DetailClient({"id": "c1", "metrics": {"model_name": "m", "accumulated_cost": 2.5}})
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "cost:c1")
    asyncio.run(h.show_cost(update, ctx))
    assert "$2.5" in update.callback_query.edits[-1]


def test_list_files_caches_and_paginates(tmp_path):
    files = [f"f{i}.py" for i in range(12)]
    ctx = _ctx_with(tmp_path, DetailClient({"id": "c1"}, files=files))
    update = _cb_update(1, "files:c1:0")
    asyncio.run(h.list_files(update, ctx))
    assert ctx.bot_data["file_cache"]["c1"] == files
    assert "صفحة 1" in update.callback_query.edits[-1]


def test_show_file_sends_document(tmp_path):
    ctx = _ctx_with(tmp_path, DetailClient({"id": "c1"}, files=["a/b/main.py"], content="hello"))
    ctx.bot_data["file_cache"] = {"c1": ["a/b/main.py"]}
    update = _cb_update(1, "file:c1:0")
    asyncio.run(h.show_file(update, ctx))
    assert len(ctx.bot.documents) == 1


def test_export_sends_zip(tmp_path):
    ctx = _ctx_with(tmp_path, DetailClient({"id": "c1"}))
    update = _cb_update(1, "export:c1")
    asyncio.run(h.export_conversation(update, ctx))
    assert len(ctx.bot.documents) == 1
