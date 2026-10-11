from bot.db import Database


def make_db(tmp_path):
    return Database(str(tmp_path / "t.sqlite3"))


def test_add_and_list_watched(tmp_path):
    db = make_db(tmp_path)
    db.add_watched("c1", "عنوان")
    watched = db.list_watched()
    assert len(watched) == 1
    assert watched[0].conversation_id == "c1"
    assert watched[0].title == "عنوان"


def test_remove_watched(tmp_path):
    db = make_db(tmp_path)
    db.add_watched("c1")
    db.remove_watched("c1")
    assert db.list_watched() == []


def test_set_last_state(tmp_path):
    db = make_db(tmp_path)
    db.add_watched("c1")
    db.set_last_state("c1", "running")
    assert db.list_watched()[0].last_state == "running"


def test_awaiting_roundtrip(tmp_path):
    db = make_db(tmp_path)
    db.set_awaiting(5, "conv", "reply")
    assert db.get_awaiting(5) == ("conv", "reply")
    db.clear_awaiting(5)
    assert db.get_awaiting(5) == (None, None)


def test_add_watched_is_idempotent(tmp_path):
    db = make_db(tmp_path)
    db.add_watched("c1", "a")
    db.add_watched("c1", "b")
    assert len(db.list_watched()) == 1
    assert db.list_watched()[0].title == "b"


def test_is_watched(tmp_path):
    db = make_db(tmp_path)
    assert db.is_watched("c1") is False
    db.add_watched("c1")
    assert db.is_watched("c1") is True
    db.remove_watched("c1")
    assert db.is_watched("c1") is False


def test_add_watched_stores_chat_id(tmp_path):
    db = make_db(tmp_path)
    db.add_watched("c1", "عنوان", chat_id=555)
    assert db.list_watched()[0].chat_id == 555


def test_add_watched_keeps_existing_chat_id_when_none(tmp_path):
    db = make_db(tmp_path)
    db.add_watched("c1", "عنوان", chat_id=555)
    db.add_watched("c1", "عنوان محدّث")
    assert db.list_watched()[0].chat_id == 555


def test_migrates_old_schema_without_chat_id(tmp_path):
    import sqlite3

    path = str(tmp_path / "old.sqlite3")
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE watched (conversation_id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '',"
        " last_state TEXT);"
        "CREATE TABLE user_state (telegram_id INTEGER PRIMARY KEY, awaiting_conversation_id TEXT,"
        " awaiting_kind TEXT, pending_repo TEXT);"
    )
    conn.execute("INSERT INTO watched(conversation_id, title) VALUES('c1', 'قديم')")
    conn.commit()
    conn.close()

    db = Database(path)
    watched = db.list_watched()
    assert watched[0].conversation_id == "c1"
    assert watched[0].chat_id is None
    db.add_watched("c1", "قديم", chat_id=9)
    assert db.list_watched()[0].chat_id == 9
