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


# --------------------------------------------------------------------- outbox
def test_outbox_persist_and_read(tmp_path):
    db = make_db(tmp_path)
    oid = db.add_outbox("c1", 99, "برومت", "2026-01-01T00:00:00+00:00")
    item = db.get_outbox(oid)
    assert item.conversation_id == "c1"
    assert item.chat_id == 99
    assert item.text == "برومت"
    assert item.status == "pending"
    assert item.error is None
    assert item.created_at == "2026-01-01T00:00:00+00:00"
    assert item.updated_at == "2026-01-01T00:00:00+00:00"


def test_outbox_status_transition_updates_updated_at_only(tmp_path):
    db = make_db(tmp_path)
    oid = db.add_outbox("c1", 99, "x", "t0")
    db.set_outbox_status(oid, "sending", "t1")
    assert db.get_outbox(oid).status == "sending"
    assert db.get_outbox(oid).updated_at == "t1"
    db.set_outbox_status(oid, "sent", "t2")
    item = db.get_outbox(oid)
    assert item.status == "sent"
    assert item.created_at == "t0"
    assert item.updated_at == "t2"


def test_outbox_error_metadata_stored(tmp_path):
    db = make_db(tmp_path)
    oid = db.add_outbox("c1", 99, "x", "t0")
    db.set_outbox_status(oid, "failed", "t1", "HTTP 422")
    assert db.get_outbox(oid).error == "HTTP 422"


def test_outbox_list_by_status_and_count(tmp_path):
    db = make_db(tmp_path)
    a = db.add_outbox("c1", 1, "a", "t")
    b = db.add_outbox("c2", 1, "b", "t")
    db.set_outbox_status(b, "unknown", "t", "timeout")
    assert [i.id for i in db.list_outbox_by_status("pending")] == [a]
    assert [i.id for i in db.list_outbox_by_status("unknown")] == [b]
    assert db.count_outbox() == 2
    assert db.count_outbox("pending") == 1
    assert db.count_outbox("sent") == 0


def test_outbox_get_missing_returns_none(tmp_path):
    db = make_db(tmp_path)
    assert db.get_outbox(999) is None


def test_outbox_table_added_to_old_database_non_destructively(tmp_path):
    import sqlite3

    path = str(tmp_path / "old.sqlite3")
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE watched (conversation_id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '',"
        " last_state TEXT, chat_id INTEGER);"
        "CREATE TABLE user_state (telegram_id INTEGER PRIMARY KEY, awaiting_conversation_id TEXT,"
        " awaiting_kind TEXT);"
    )
    conn.execute("INSERT INTO watched(conversation_id, title) VALUES('c1','قديم')")
    conn.commit()
    conn.close()

    db = Database(path)
    # البيانات القديمة اتّحفظت، وجدول outbox اتضاف.
    assert db.list_watched()[0].conversation_id == "c1"
    oid = db.add_outbox("c1", 9, "برومت", "t")
    assert db.get_outbox(oid).status == "pending"


# ---------------------------------------------------- outbox claim / attempts
def test_outbox_attempts_defaults_zero_and_bumps(tmp_path):
    db = make_db(tmp_path)
    oid = db.add_outbox("c1", 9, "x", "t")
    assert db.get_outbox(oid).attempts == 0
    db.set_outbox_status(oid, "pending", "t1", "sandbox غير جاهز", bump=True)
    assert db.get_outbox(oid).attempts == 1
    db.set_outbox_status(oid, "sent", "t2")  # من غير bump
    assert db.get_outbox(oid).attempts == 1


def test_claim_sets_claimed_and_is_single_shot(tmp_path):
    db = make_db(tmp_path)
    a = db.add_outbox("c1", 9, "a", "t")
    b = db.add_outbox("c2", 9, "b", "t")
    first = db.claim_outbox("t1")
    second = db.claim_outbox("t2")
    third = db.claim_outbox("t3")
    assert (first.id, first.status) == (a, "claimed")
    assert (second.id, second.status) == (b, "claimed")
    assert third is None


def test_oldest_pending_id_ignores_non_pending(tmp_path):
    db = make_db(tmp_path)
    a = db.add_outbox("c1", 9, "a", "t")
    b = db.add_outbox("c2", 9, "b", "t")
    assert db.oldest_pending_id() == a
    db.set_outbox_status(a, "sent", "t")
    assert db.oldest_pending_id() == b


def test_migration_adds_attempts_to_existing_outbox(tmp_path):
    import sqlite3

    path = str(tmp_path / "old.sqlite3")
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE watched (conversation_id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '',"
        " last_state TEXT, chat_id INTEGER);"
        "CREATE TABLE user_state (telegram_id INTEGER PRIMARY KEY, awaiting_conversation_id TEXT,"
        " awaiting_kind TEXT);"
        "CREATE TABLE outbox (id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL,"
        " chat_id INTEGER NOT NULL, text TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',"
        " error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);"
    )
    conn.execute("INSERT INTO outbox(conversation_id, chat_id, text, status, created_at, updated_at)"
                 " VALUES('c1', 9, 'قديم', 'pending', 't', 't')")
    conn.commit()
    conn.close()

    db = Database(path)  # المفروض تضيف عمود attempts من غير ما تفقد الصف
    item = db.get_outbox(1)
    assert item.text == "قديم"
    assert item.attempts == 0
    db.set_outbox_status(1, "pending", "t2", None, bump=True)
    assert db.get_outbox(1).attempts == 1



# ---------------------------------------------------- creation jobs (04A-6)
def test_creation_job_defaults_and_fields(tmp_path):
    db = make_db(tmp_path)
    jid = db.add_creation_job(99, "o/r", "برومت", "t")
    job = db.get_creation_job(jid)
    assert job.status == "pending"
    assert job.repo == "o/r"
    assert job.text == "برومت"
    assert job.task_id is None
    assert job.conversation_id is None
    assert job.attempts == 0


def test_claim_creation_job_atomic_oldest_first(tmp_path):
    db = make_db(tmp_path)
    a = db.add_creation_job(99, None, "a", "t")
    b = db.add_creation_job(99, None, "b", "t")
    first = db.claim_creation_job("t1")
    second = db.claim_creation_job("t2")
    third = db.claim_creation_job("t3")
    assert (first.id, first.status) == (a, "claimed")
    assert (second.id, second.status) == (b, "claimed")
    assert third is None


def test_set_creation_starting_records_task_id_only_when_given(tmp_path):
    db = make_db(tmp_path)
    a = db.add_creation_job(99, None, "a", "t")
    b = db.add_creation_job(99, None, "b", "t")
    db.set_creation_starting(a, "t")
    db.set_creation_starting(b, "t", task_id="task-9")
    assert db.get_creation_job(a).task_id is None  # مفيش اختراع معرّف
    assert db.get_creation_job(b).task_id == "task-9"
    assert db.get_creation_job(a).status == "starting"


def test_set_creation_done_stores_conversation_id(tmp_path):
    db = make_db(tmp_path)
    jid = db.add_creation_job(99, None, "a", "t")
    db.set_creation_done(jid, "t", "conv-7")
    job = db.get_creation_job(jid)
    assert job.status == "done"
    assert job.conversation_id == "conv-7"


def test_open_creation_jobs_and_counts(tmp_path):
    db = make_db(tmp_path)
    a = db.add_creation_job(99, None, "a", "t")
    b = db.add_creation_job(99, None, "b", "t")
    db.set_creation_status(b, "done", "t")
    assert [j.id for j in db.list_open_creation_jobs()] == [a]
    assert db.count_creation_jobs("done") == 1
    assert db.oldest_pending_creation_id() == a


def test_creation_attempts_bump(tmp_path):
    db = make_db(tmp_path)
    jid = db.add_creation_job(99, None, "a", "t")
    db.set_creation_status(jid, "pending", "t", "safe", bump=True)
    assert db.get_creation_job(jid).attempts == 1


def test_migration_adds_creation_jobs_table_to_old_db(tmp_path):
    import sqlite3

    path = str(tmp_path / "old.sqlite3")
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE watched (conversation_id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '',"
        " last_state TEXT, chat_id INTEGER);"
        "CREATE TABLE user_state (telegram_id INTEGER PRIMARY KEY, awaiting_conversation_id TEXT,"
        " awaiting_kind TEXT);"
        "CREATE TABLE outbox (id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL,"
        " chat_id INTEGER NOT NULL, text TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',"
        " error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);"
    )
    conn.commit()
    conn.close()

    db = Database(path)  # لازم يضيف جدول creation_jobs من غير ما يفقد أي حاجة
    jid = db.add_creation_job(99, "o/r", "برومت", "t")
    assert db.get_creation_job(jid).status == "pending"
    assert db.count_creation_jobs("pending") == 1


def test_list_open_outbox_excludes_terminal(tmp_path):
    db = make_db(tmp_path)
    a = db.add_outbox("c1", 99, "a", "t")
    b = db.add_outbox("c2", 99, "b", "t")
    db.set_outbox_status(b, "sent", "t")
    assert [i.id for i in db.list_open_outbox()] == [a]

