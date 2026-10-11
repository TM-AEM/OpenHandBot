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
