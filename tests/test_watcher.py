import asyncio

from bot.db import Database
from bot.watcher import Watcher


class FakeClient:
    def __init__(self, by_id, reply=None):
        self._by_id = by_id
        self._reply = reply

    async def get_conversations(self, ids):
        return [self._by_id[i] for i in ids if i in self._by_id]

    async def get_last_reply(self, conversation_id):
        return self._reply


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id=None, text=None, parse_mode=None, **kw):
        self.sent.append(text)

    async def send_document(self, chat_id=None, document=None, **kw):
        self.sent.append("DOC")


def test_finished_triggers_notification_and_removes(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "عنوان")
    client = FakeClient({"c1": {"id": "c1", "title": "عنوان", "execution_status": "finished"}}, reply="تم")
    bot = FakeBot()
    w = Watcher(client, db, bot, chat_id=1)

    asyncio.run(w.tick())

    assert len(bot.sent) == 1
    assert "انتهى الشات" in bot.sent[0]
    assert "تم" in bot.sent[0]
    assert db.list_watched() == []


def test_running_updates_state_without_notify(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1")
    client = FakeClient({"c1": {"id": "c1", "execution_status": "running"}})
    bot = FakeBot()
    w = Watcher(client, db, bot, chat_id=1)

    asyncio.run(w.tick())

    assert bot.sent == []
    assert db.list_watched()[0].last_state == "running"


def test_no_double_notify_when_already_done(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1")
    db.set_last_state("c1", "finished")
    client = FakeClient({"c1": {"id": "c1", "execution_status": "finished"}})
    bot = FakeBot()
    w = Watcher(client, db, bot, chat_id=1)

    asyncio.run(w.tick())

    assert bot.sent == []


def test_waiting_for_confirmation_mentions_site(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1")
    client = FakeClient({"c1": {"id": "c1", "execution_status": "waiting_for_confirmation"}})
    bot = FakeBot()
    w = Watcher(client, db, bot, chat_id=1)

    asyncio.run(w.tick())

    assert "تأكيد" in bot.sent[0]
