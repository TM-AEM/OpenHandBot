"""TASK 04C-15: تخزين العنوان الطازج للشاتات المتابَعة عند تغيّره."""
import asyncio

from bot.db import Database
from bot.watcher import Watcher
from tests.test_watcher import FakeBot, FakeClient


def _watcher(db, convs):
    client = FakeClient(convs)
    bot = FakeBot()
    return Watcher(client, db, bot, chat_id=1)


def test_title_persisted_when_changed(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "قديم")
    w = _watcher(db, {"c1": {"id": "c1", "title": "جديد", "execution_status": "running"}})
    asyncio.run(w.tick())
    assert db.list_watched()[0].title == "جديد"


def test_title_not_written_when_unchanged(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "نفسه")
    assert db.update_watched_title("c1", "نفسه") is False  # مفيش تغيير ⇒ مفيش كتابة
    w = _watcher(db, {"c1": {"id": "c1", "title": "نفسه", "execution_status": "running"}})
    asyncio.run(w.tick())
    assert db.list_watched()[0].title == "نفسه"


def test_empty_title_is_ignored(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "محفوظ")
    w = _watcher(db, {"c1": {"id": "c1", "title": "", "execution_status": "running"}})
    asyncio.run(w.tick())
    assert db.list_watched()[0].title == "محفوظ"  # ما بيمسحش العنوان القديم


def test_missing_row_no_insert(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    assert db.update_watched_title("ghost", "x") is False
    assert db.list_watched() == []


def test_title_change_does_not_break_state_notification(tmp_path):
    # تغيير العنوان ما يأثرش على منطق الإشعار بحالة الشات.
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "قديم")
    w = _watcher(db, {"c1": {"id": "c1", "title": "جديد", "execution_status": "finished"}})
    asyncio.run(w.tick())
    # finished ⇒ السجل بيتشال بعد الإشعار، فنتأكد إن الإشعار اتبعت فعلاً.
    assert any("انتهى الشات" in s for s in w._bot.sent)
    assert db.list_watched() == []
