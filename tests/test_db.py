import sqlite3

import pytest

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


def test_bump_outbox_attempt_is_atomic_and_returns_new_count(tmp_path):
    # TASK 53: bump_outbox_attempt بترجّع العدّاد الفعلي بعد الزيادة (RETURNING)،
    # وبتسيب الحالة 'pending' (محاولة مابدأتش ⇒ آمنة)، وبتحفظ الخطأ.
    db = make_db(tmp_path)
    oid = db.add_outbox("c1", 9, "x", "t")
    assert db.bump_outbox_attempt(oid, "t1", "سبب") == 1
    assert db.bump_outbox_attempt(oid, "t2", "سبب") == 2
    item = db.get_outbox(oid)
    assert item.status == "pending"
    assert item.attempts == 2
    assert item.error == "سبب"


def test_bump_outbox_attempt_missing_record_returns_zero(tmp_path):
    db = make_db(tmp_path)
    assert db.bump_outbox_attempt(999, "t", None) == 0


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


# ---------------------------------------------- TASK 54: watched retry_count
def test_watched_retry_count_defaults_zero(tmp_path):
    db = make_db(tmp_path)
    db.add_watched("c1", "عنوان")
    assert db.list_watched()[0].retry_count == 0


def test_increment_watched_retry_is_atomic_and_returns_new_count(tmp_path):
    db = make_db(tmp_path)
    db.add_watched("c1")
    assert db.increment_watched_retry("c1") == 1
    assert db.increment_watched_retry("c1") == 2
    assert db.list_watched()[0].retry_count == 2


def test_increment_watched_retry_missing_record_returns_zero(tmp_path):
    db = make_db(tmp_path)
    assert db.increment_watched_retry("nope") == 0


def test_advance_watched_state_resets_retry_count(tmp_path):
    db = make_db(tmp_path)
    db.add_watched("c1")
    db.increment_watched_retry("c1")
    db.increment_watched_retry("c1")
    assert db.list_watched()[0].retry_count == 2
    db.advance_watched_state("c1", "running")
    w = db.list_watched()[0]
    assert w.last_state == "running"
    assert w.retry_count == 0  # بداية دورة إشعار جديدة ⇒ ميزانية كاملة


def test_add_watched_resets_retry_count_new_lifecycle(tmp_path):
    db = make_db(tmp_path)
    db.add_watched("c1", "عنوان")
    db.increment_watched_retry("c1")
    db.increment_watched_retry("c1")
    assert db.list_watched()[0].retry_count == 2
    db.add_watched("c1", "عنوان محدّث")  # متابعة جديدة ⇒ تصفير
    assert db.list_watched()[0].retry_count == 0


def test_retry_count_persists_across_reopen(tmp_path):
    path = str(tmp_path / "t.sqlite3")
    db = make_db(tmp_path)
    db.add_watched("c1")
    db.increment_watched_retry("c1")
    db.increment_watched_retry("c1")
    db.increment_watched_retry("c1")
    db.close()

    reopened = Database(path)
    assert reopened.list_watched()[0].retry_count == 3  # نجا من إعادة الفتح
    reopened.close()


def test_migration_adds_retry_count_to_existing_watched(tmp_path):
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

    db = Database(path)  # الترحيل يضيف العمود من غير ما يفقد الصف
    w = db.list_watched()[0]
    assert w.conversation_id == "c1"
    assert w.retry_count == 0  # الصف القديم ياخد ميزانية كاملة
    assert db.increment_watched_retry("c1") == 1




# ================================= NTF-19: stable watch identity ==========================
def test_watch_seq_present_and_persisted(tmp_path):
    db = make_db(tmp_path)
    db.add_watched("c1", "t")
    seq = db.get_watched("c1").watch_seq
    assert seq  # معرّف غير فاضي
    db2 = Database(str(tmp_path / "t.sqlite3"))  # إعادة فتح (restart)
    assert db2.get_watched("c1").watch_seq == seq  # ثابت عبر إعادة التشغيل


def test_watch_seq_stable_across_reads_and_unrelated_updates(tmp_path):
    db = make_db(tmp_path)
    db.add_watched("c1", "t")
    seq = db.get_watched("c1").watch_seq
    assert db.get_watched("c1").watch_seq == seq
    assert db.list_watched()[0].watch_seq == seq
    db.set_last_state("c1", "running")  # تحديث حقل غير متعلّق
    db.update_watched_title("c1", "عنوان جديد")
    assert db.get_watched("c1").watch_seq == seq  # ما اتغيّرش
    assert db.list_watched()[0].watch_seq == seq


def test_delete_and_recreate_gets_new_identity_even_same_timestamp(tmp_path):
    db = make_db(tmp_path)
    db.add_watched("c1", "t")
    first = db.get_watched("c1").watch_seq
    # نفرض نفس وقت الإنشاء بالظبط (محاكاة نفس دقة الوقت) — المعرّف لازم يفضل مختلف.
    db._conn.execute("UPDATE watched SET added_at=? WHERE conversation_id=?", ("FIXED", "c1"))
    db._conn.commit()
    db.remove_watched("c1")
    db.add_watched("c1", "t")
    db._conn.execute("UPDATE watched SET added_at=? WHERE conversation_id=?", ("FIXED", "c1"))
    db._conn.commit()
    second = db.get_watched("c1").watch_seq
    assert first != second  # معرّف جديد رغم تطابق الطابع الزمني


def test_migration_adds_watch_seq_to_existing_rows(tmp_path):
    import sqlite3

    path = str(tmp_path / "old.sqlite3")
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE watched (conversation_id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '',"
        " last_state TEXT, chat_id INTEGER, added_at TEXT, retry_count INTEGER NOT NULL DEFAULT 0,"
        " pending_delivery_state TEXT);"
    )
    conn.execute("INSERT INTO watched(conversation_id, title, added_at) VALUES('c1','قديم','2020')")
    conn.commit()
    conn.close()

    db = Database(path)  # الترحيل بيضيف العمود
    cols = {r["name"] for r in db._conn.execute("PRAGMA table_info(watched)")}
    assert "watch_seq" in cols
    legacy_seq = db.get_watched("c1").watch_seq
    assert legacy_seq  # الصف القديم ليه معرّف صالح
    # القراءات المتكرّرة (وكمان إعادة الفتح) ترجّع نفس المعرّف
    assert db.get_watched("c1").watch_seq == legacy_seq
    assert db.list_watched()[0].watch_seq == legacy_seq
    assert Database(path).get_watched("c1").watch_seq == legacy_seq


def test_rewatch_new_timestamp_gets_new_identity(tmp_path):
    db = make_db(tmp_path)
    db.add_watched("c1", "t")
    db._conn.execute("UPDATE watched SET added_at=? WHERE conversation_id=?", ("2020", "c1"))
    db._conn.commit()
    first = db.get_watched("c1").watch_seq
    db.add_watched("c1", "t")  # وقت أحدث ⇒ دورة جديدة ⇒ معرّف جديد
    assert db.get_watched("c1").watch_seq != first


# ============================ NTF-20: pending delivery across new lifecycle ================
def _seed_ns(db, cid="c1", status="running"):
    db.add_watched(cid, "t")
    db.set_last_state(cid, "running")
    db.upsert_notification_state(cid, status=status, notified_status=status, updated_at="t")


def test_new_lifecycle_reconciles_durable_pending(tmp_path):
    """NTF-20: دورة جديدة مع علامة دائمة ⇒ تتسجّل (notified_status) وتُمسح، والدليل محفوظ."""
    db = make_db(tmp_path)
    _seed_ns(db)
    db.set_pending_delivery("c1", "finished")
    db.add_watched("c1", "t", new_lifecycle=True)
    assert db.get_watched("c1").pending_delivery_state is None
    assert db.get_notification_state("c1").notified_status == "finished"  # مفيش فقد


def test_new_lifecycle_without_pending_starts_clean(tmp_path):
    db = make_db(tmp_path)
    _seed_ns(db)
    old = db.get_watched("c1").watch_seq
    db.add_watched("c1", "t", new_lifecycle=True)
    w = db.get_watched("c1")
    assert w.pending_delivery_state is None
    assert w.watch_seq != old  # معرّف جديد


def test_duplicate_callback_preserves_durable_pending(tmp_path):
    db = make_db(tmp_path)
    _seed_ns(db)
    db.set_pending_delivery("c1", "finished")
    old = db.get_watched("c1").watch_seq
    db.add_watched("c1", "t", new_lifecycle=False)  # إعادة نداء مكرّرة
    w = db.get_watched("c1")
    assert w.pending_delivery_state == "finished"  # الدليل محفوظ
    assert w.watch_seq == old  # المعرّف محفوظ


def test_reconcile_pending_delivery_records_and_clears(tmp_path):
    db = make_db(tmp_path)
    _seed_ns(db)
    db.set_pending_delivery("c1", "finished")
    assert db.reconcile_pending_delivery("c1") == "finished"
    assert db.get_watched("c1").pending_delivery_state is None
    assert db.get_notification_state("c1").notified_status == "finished"
    assert db.reconcile_pending_delivery("c1") is None  # مفيش حاجة تاني


class _RecordFailsOnReconcileDb(Database):
    """record_notification_sent يفشل ⇒ التسوية ترجع كاملة والعلامة تفضل (retry آمن)."""

    def record_notification_sent(self, cid, status, now, *, _commit=True):
        raise sqlite3.OperationalError("disk I/O error (record)")


def test_new_lifecycle_reconcile_failure_preserves_state(tmp_path):
    import sqlite3

    db = _RecordFailsOnReconcileDb(str(tmp_path / "t.sqlite3"))
    _seed_ns(db)
    db.set_pending_delivery("c1", "finished")
    old = db.get_watched("c1").watch_seq
    with pytest.raises(sqlite3.OperationalError):
        db.add_watched("c1", "t", new_lifecycle=True)
    w = db.get_watched("c1")
    assert w.pending_delivery_state == "finished"  # العلامة محفوظة
    assert w.watch_seq == old  # الدورة الجديدة ما اتعملتش
    assert db.get_notification_state("c1").notified_status == "running"  # مفيش تسجيل جزئي


# ==================== NTF-23: compare-and-swap removal by watch_seq ========================
def test_remove_watched_if_seq_removes_matching_lifecycle(tmp_path):
    db = make_db(tmp_path)
    db.add_watched("c1", "t")
    seq = db.get_watched("c1").watch_seq
    assert db.remove_watched_if_seq("c1", seq) is True
    assert not db.is_watched("c1")


def test_remove_watched_if_seq_missing_row_returns_false(tmp_path):
    db = make_db(tmp_path)
    assert db.remove_watched_if_seq("nope", "whatever") is False


def test_remove_watched_if_seq_changed_lifecycle_returns_false_and_preserves(tmp_path):
    db = make_db(tmp_path)
    db.add_watched("c1", "t")
    old_seq = db.get_watched("c1").watch_seq
    db.add_watched("c1", "t", new_lifecycle=True)  # دورة جديدة
    new_seq = db.get_watched("c1").watch_seq
    assert new_seq != old_seq
    assert db.remove_watched_if_seq("c1", old_seq) is False  # CAS فشل
    assert db.is_watched("c1")  # الدورة الجديدة سليمة
    assert db.get_watched("c1").watch_seq == new_seq


def test_remove_watched_if_seq_completes_pending_in_same_tx(tmp_path):
    db = make_db(tmp_path)
    _seed_ns(db)
    db.set_pending_delivery("c1", "finished")
    seq = db.get_watched("c1").watch_seq
    assert db.remove_watched_if_seq("c1", seq) is True
    assert not db.is_watched("c1")
    assert db.get_notification_state("c1").notified_status == "finished"  # الدليل محفوظ


class _RecordFailsOnCasDb(Database):
    """record_notification_sent يفشل ⇒ حذف CAS كامل يترجع (الصف يفضل، retry آمن)."""

    def record_notification_sent(self, cid, status, now, *, _commit=True):
        raise sqlite3.OperationalError("disk I/O error (record)")


def test_remove_watched_if_seq_rolls_back_on_record_failure(tmp_path):
    db = _RecordFailsOnCasDb(str(tmp_path / "t.sqlite3"))
    _seed_ns(db)
    db.set_pending_delivery("c1", "finished")
    seq = db.get_watched("c1").watch_seq
    with pytest.raises(sqlite3.OperationalError):
        db.remove_watched_if_seq("c1", seq)
    assert db.is_watched("c1")  # الحذف اترجع
    assert db.get_watched("c1").pending_delivery_state == "finished"  # العلامة محفوظة


def test_remove_watched_if_seq_changed_lifecycle_does_not_touch_pending(tmp_path):
    """NTF-23: CAS فاشل (دورة جديدة) ما يلمسش دليل الدورة الجديدة."""
    db = make_db(tmp_path)
    _seed_ns(db)
    old_seq = db.get_watched("c1").watch_seq
    db.add_watched("c1", "t", new_lifecycle=True)  # دورة جديدة
    db.set_pending_delivery("c1", "finished")  # دليل خاص بالدورة الجديدة
    assert db.remove_watched_if_seq("c1", old_seq) is False
    assert db.is_watched("c1")
    assert db.get_watched("c1").pending_delivery_state == "finished"  # ما اتمسحش


def test_increment_watched_retry_if_seq_cas(tmp_path):
    db = make_db(tmp_path)
    db.add_watched("c1", "t")
    seq = db.get_watched("c1").watch_seq
    assert db.increment_watched_retry_if_seq("c1", seq) == 1
    db.add_watched("c1", "t", new_lifecycle=True)  # دورة جديدة
    assert db.increment_watched_retry_if_seq("c1", seq) == 0  # CAS فشل
    assert db.get_watched("c1").retry_count == 0  # العدّاد الجديد ما اتلمسش


# =====================================================================
# OHB2-02: has_notification_states — استعلام EXISTS خفيف
# =====================================================================
def test_has_notification_states_false_when_empty(tmp_path):
    db = make_db(tmp_path)
    assert db.has_notification_states() is False


def test_has_notification_states_true_after_write(tmp_path):
    db = make_db(tmp_path)
    db.upsert_notification_state("c1", status="running", notified_status="running", retry_count=0)
    assert db.has_notification_states() is True


def test_has_notification_states_agrees_with_list(tmp_path):
    db = make_db(tmp_path)
    assert db.has_notification_states() == bool(db.list_notification_states())
    db.upsert_notification_state("c1", status="done", notified_status="done", retry_count=0)
    assert db.has_notification_states() == bool(db.list_notification_states())


# ==================== OHB2-08-04: SQLite index optimization ====================
def _index_columns(conn, index_name):
    """أعمدة فهرس بالترتيب (من PRAGMA index_info)، أو None لو الفهرس مش موجود."""
    rows = conn.execute(f"PRAGMA index_info({index_name})").fetchall()
    if not rows:
        return None
    return [r[2] for r in rows]


def _plan_text(conn, sql, params=()):
    rows = conn.execute("EXPLAIN QUERY PLAN " + sql, params).fetchall()
    return " | ".join(r[3] for r in rows)


def test_new_indexes_created_on_fresh_db(tmp_path):
    """OHB2-08-04: قاعدة جديدة بتاخد الفهرسين المركّبين بالأعمدة والترتيب المتوقّعين."""
    db = make_db(tmp_path)
    conn = db._conn
    assert _index_columns(conn, "idx_outbox_status_updated") == ["status", "updated_at"]
    assert _index_columns(conn, "idx_outbox_conv_chat_status") == [
        "conversation_id", "chat_id", "status",
    ]
    db.close()


def test_new_indexes_added_to_existing_db_without_data_loss(tmp_path):
    """OHB2-08-04: قاعدة قديمة (من غير الفهارس الجديدة) بتاخدها عند الفتح، والصفوف تفضل."""
    import sqlite3

    path = str(tmp_path / "old.sqlite3")
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE outbox (id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL,"
        " chat_id INTEGER NOT NULL, text TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',"
        " error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,"
        " attempts INTEGER NOT NULL DEFAULT 0, client_ref TEXT);"
    )
    conn.execute(
        "INSERT INTO outbox(conversation_id, chat_id, text, status, created_at, updated_at)"
        " VALUES('c1', 7, 'قديم', 'pending', 't0', 't0')"
    )
    conn.commit()
    conn.close()

    db = Database(path)
    conn = db._conn
    assert _index_columns(conn, "idx_outbox_status_updated") == ["status", "updated_at"]
    assert _index_columns(conn, "idx_outbox_conv_chat_status") == [
        "conversation_id", "chat_id", "status",
    ]
    # الصفوف محفوظة زي ما هي.
    item = db.list_outbox_by_status("pending")[0]
    assert item.conversation_id == "c1" and item.text == "قديم"
    db.close()


def test_repeated_initialization_is_idempotent(tmp_path):
    """OHB2-08-04: فتح القاعدة مرارًا لا يكرّر الفهارس ولا يرمي."""
    path = str(tmp_path / "t.sqlite3")
    for _ in range(3):
        db = Database(path)
        names = [r[1] for r in db._conn.execute("PRAGMA index_list(outbox)").fetchall()]
        assert names.count("idx_outbox_status_updated") == 1
        assert names.count("idx_outbox_conv_chat_status") == 1
        db.close()


def test_maturity_query_uses_status_updated_index(tmp_path):
    """OHB2-08-04: استعلام النضج (موعد نوم الـ worker) يستخدم الفهرس المركّب بدل ترتيب مؤقّت."""
    db = make_db(tmp_path)
    plan = _plan_text(
        db._conn,
        "SELECT updated_at FROM outbox WHERE status='pending' ORDER BY updated_at LIMIT 1",
    )
    assert "idx_outbox_status_updated" in plan
    assert "TEMP B-TREE FOR ORDER BY" not in plan.upper()
    db.close()


def test_grouping_query_uses_conv_chat_status_index(tmp_path):
    """OHB2-08-04: استعلام التجميع يستخدم فهرس الوجهة+الحالة."""
    db = make_db(tmp_path)
    plan = _plan_text(
        db._conn,
        "SELECT id, text, updated_at, client_ref FROM outbox "
        "WHERE conversation_id=? AND chat_id=? AND status=? ORDER BY id DESC LIMIT 1",
        ("c1", 1, "pending"),
    )
    assert "idx_outbox_conv_chat_status" in plan
    db.close()


def test_claim_path_unchanged_by_new_indexes(tmp_path):
    """OHB2-08-04: مسار الحجز الذرّي (rowid) ما اتغيّرش بالفهارس الجديدة."""
    db = make_db(tmp_path)
    plan = _plan_text(
        db._conn,
        "UPDATE outbox SET status='claimed', updated_at=? WHERE id=("
        "SELECT id FROM outbox WHERE status='pending' ORDER BY id LIMIT 1) RETURNING *",
        ("t",),
    )
    assert "INTEGER PRIMARY KEY (rowid=?)" in plan
    db.close()


def test_claim_and_list_behavior_intact_with_indexes(tmp_path):
    """OHB2-08-04: الحجز والعدّ والقوائم لسه شغالين صح بعد الفهارس."""
    db = make_db(tmp_path)
    for i in range(3):
        db.add_outbox(f"c{i}", 1, f"p{i}", "t0")
    claimed = db.claim_outbox("t1")
    assert claimed is not None and claimed.status == "claimed"
    assert db.count_outbox("pending") == 2
    assert len(db.list_open_outbox()) == 3
    db.close()


def test_batch1_persistence_intact_after_index_migration(tmp_path):
    """OHB2-08-04: علامات التسليم المعلّق ومواعيد RetryAfter (Batch 1) لسه بتفضل بعد إعادة الفتح."""
    path = str(tmp_path / "t.sqlite3")
    db = Database(path)
    db.add_watched("c1", "t")
    db.set_notifier_pending("c1", "finished", "2026-01-01T00:00:00+00:00")
    db.set_retry_not_before("c1", "2030-01-01T00:00:00+00:00")
    db.close()

    db2 = Database(path)  # إعادة فتح ⇒ تشغيل _migrate تاني (idempotent)
    assert db2.get_notifier_pending("c1") == "finished"
    assert db2.get_retry_not_before("c1") == "2030-01-01T00:00:00+00:00"
    db2.close()


# ------------------------------------------ OHB2-08-05: صندوق الإشعارات
def test_inbox_add_and_list_newest_first(tmp_path):
    db = make_db(tmp_path)
    a = db.add_inbox_item("c1", "عنوان", "terminal", "رسالة أولى", "2026-01-01T00:00:00+00:00")
    b = db.add_inbox_item("c1", "عنوان", "proactive", "رسالة تانية", "2026-01-01T00:01:00+00:00")
    items = db.list_inbox()
    assert [it.id for it in items] == [b, a]  # الأحدث أولًا
    assert items[0].message == "رسالة تانية"
    assert items[0].kind == "proactive"
    assert items[0].unread is True and items[0].read_at is None
    db.close()


def test_inbox_unread_count_and_mark_read(tmp_path):
    db = make_db(tmp_path)
    a = db.add_inbox_item("c1", "t", "terminal", "x", "t0")
    db.add_inbox_item("c1", "t", "terminal", "y", "t1")
    assert db.count_inbox() == 2
    assert db.count_inbox(unread_only=True) == 2
    assert db.mark_inbox_read(a, "t2") is True
    assert db.count_inbox(unread_only=True) == 1
    # idempotent: إعادة التعليم ما تكسّرش ومازالت True.
    assert db.mark_inbox_read(a, "t3") is True
    assert db.count_inbox(unread_only=True) == 1
    db.close()


def test_inbox_mark_read_missing_returns_false(tmp_path):
    db = make_db(tmp_path)
    assert db.mark_inbox_read(999, "t") is False
    db.close()


def test_inbox_mark_all_read(tmp_path):
    db = make_db(tmp_path)
    db.add_inbox_item("c1", "t", "terminal", "x", "t0")
    db.add_inbox_item("c2", "t", "proactive", "y", "t1")
    changed = db.mark_all_inbox_read("t2")
    assert changed == 2
    assert db.count_inbox(unread_only=True) == 0
    assert db.mark_all_inbox_read("t3") == 0  # مفيش غير مقروء تاني
    db.close()


def test_inbox_list_unread_only_and_paging(tmp_path):
    db = make_db(tmp_path)
    ids = [db.add_inbox_item("c1", "t", "terminal", f"m{i}", f"t{i}") for i in range(5)]
    db.mark_inbox_read(ids[0], "tx")  # الأقدم مقروء
    page0 = db.list_inbox(limit=2, offset=0)
    page1 = db.list_inbox(limit=2, offset=2)
    assert len(page0) == 2 and len(page1) == 2
    assert {it.id for it in page0}.isdisjoint({it.id for it in page1})
    unread = db.list_inbox(unread_only=True)
    assert ids[0] not in [it.id for it in unread]
    assert len(unread) == 4
    db.close()


def test_inbox_message_truncated(tmp_path):
    from bot.db import INBOX_MAX_MESSAGE_CHARS

    db = make_db(tmp_path)
    db.add_inbox_item("c1", "t", "terminal", "x" * (INBOX_MAX_MESSAGE_CHARS + 500), "t0")
    item = db.list_inbox()[0]
    assert len(item.message) == INBOX_MAX_MESSAGE_CHARS
    db.close()


def test_inbox_pruned_per_conversation(tmp_path):
    from bot.db import INBOX_MAX_PER_CONVERSATION

    db = make_db(tmp_path)
    for i in range(INBOX_MAX_PER_CONVERSATION + 10):
        db.add_inbox_item("c1", "t", "terminal", f"m{i}", "t0")
    # غير المقروءة محمية (Batch 3R-FIX)؛ بعد ما تتعلّم مقروءة، إدراج إضافي يستدعي التقليم.
    db.mark_all_inbox_read("tr")
    db.add_inbox_item("c1", "t", "terminal", "mZ", "t1")  # صف غير مقروء (يستدعي تقليم c1)
    db.add_inbox_item("c2", "t", "terminal", "other", "t0")  # محادثة تانية ما تتأثّرش
    kept = db.list_inbox(limit=1000)
    c1 = [it for it in kept if it.conversation_id == "c1"]
    read_c1 = [it for it in c1 if not it.unread]
    unread_c1 = [it for it in c1 if it.unread]
    # المقروءة اتقلّمت للسقف، والصف غير المقروء (mZ) محفوظ فوق السقف (سقف ناعم).
    assert len(read_c1) == INBOX_MAX_PER_CONVERSATION
    assert [it.message for it in unread_c1] == ["mZ"]
    assert len([it for it in kept if it.conversation_id == "c2"]) == 1
    assert c1[0].message == "mZ"  # الأحدث أولًا
    assert all(it.message != "m0" for it in c1)  # الأقدم المقروء اتشال
    db.close()


def test_inbox_survives_reopen(tmp_path):
    path = str(tmp_path / "t.sqlite3")
    db = Database(path)
    db.add_inbox_item("c1", "t", "terminal", "x", "t0")
    db.close()
    db2 = Database(path)  # إعادة فتح ⇒ CREATE TABLE IF NOT EXISTS تاني (idempotent)
    assert db2.count_inbox() == 1
    assert db2.list_inbox()[0].message == "x"
    db2.close()


def test_inbox_upgrades_old_db_without_table(tmp_path):
    """قاعدة قديمة من غير جدول الصندوق بتاخده عند الفتح (إضافي، من غير فقد)."""
    path = str(tmp_path / "old.sqlite3")
    db = Database(path)
    db.add_watched("c1", "قديم")
    db._conn.execute("DROP TABLE notification_inbox")  # نحاكي قاعدة أقدم من OHB2-08-05
    db._conn.commit()
    db.close()

    db2 = Database(path)
    assert [w.conversation_id for w in db2.list_watched()] == ["c1"]  # البيانات القديمة سليمة
    db2.add_inbox_item("c1", "t", "terminal", "جديد", "t0")
    assert db2.count_inbox() == 1
    db2.close()


# --------------------------------- OHB2-08-05: هوية الحدث + التقليم العام
def test_inbox_event_key_dedup_same_event(tmp_path):
    """نفس `event_key` ⇒ مفيش صف جديد (الرجوع None)، والإدراج الأول يرجّع معرّف."""
    db = make_db(tmp_path)
    a = db.add_inbox_item("c1", "t", "terminal", "x", "t0", event_key="c1|terminal|seq1|running")
    b = db.add_inbox_item("c1", "t", "terminal", "x", "t1", event_key="c1|terminal|seq1|running")
    assert a == 1 and b is None
    assert db.count_inbox() == 1
    # الحدث نفسه بنص مختلف لسه مرفوض (الهوية هي المفتاح مش النص).
    assert db.add_inbox_item("c1", "t", "terminal", "نص مختلف", "t2",
                             event_key="c1|terminal|seq1|running") is None
    assert db.count_inbox() == 1
    db.close()


def test_inbox_event_key_different_events_coexist(tmp_path):
    """مفاتيح مختلفة ⇒ صفوف مختلفة (حتى نفس المحادثة والنوع)."""
    db = make_db(tmp_path)
    db.add_inbox_item("c1", "t", "terminal", "x", "t0", event_key="c1|terminal|seq1|running")
    db.add_inbox_item("c1", "t", "terminal", "y", "t1", event_key="c1|terminal|seq2|running")
    db.add_inbox_item("c1", "t", "timeout", "z", "t2", event_key="c1|timeout|seq2|running")
    assert db.count_inbox() == 3
    db.close()


def test_inbox_null_event_key_not_deduped(tmp_path):
    """من غير مفتاح (سلوك قديم): كل إدراج بيعمل صف — قيد التفرّد الجزئي ما بيمسّش NULL."""
    db = make_db(tmp_path)
    db.add_inbox_item("c1", "t", "terminal", "x", "t0")
    db.add_inbox_item("c1", "t", "terminal", "y", "t1")
    assert db.count_inbox() == 2
    db.close()


def test_inbox_event_key_unique_index_enforced(tmp_path):
    """القيد على مستوى القاعدة: الإدراج المباشر بنفس المفتاح يفشل (مش الذاكرة)."""
    db = make_db(tmp_path)
    db.add_inbox_item("c1", "t", "terminal", "x", "t0", event_key="k1")
    with pytest.raises(sqlite3.IntegrityError):
        db._conn.execute(
            "INSERT INTO notification_inbox(conversation_id, title, kind, message, created_at, "
            "read_at, event_key) VALUES('c1','t','terminal','y','t1',NULL,'k1')"
        )
    db.close()


def test_inbox_event_key_migrated_onto_old_table(tmp_path):
    """قاعدة فيها جدول الصندوق من غير عمود المفتاح بتاخد العمود + القيد عند الفتح."""
    path = str(tmp_path / "old.sqlite3")
    db = Database(path)
    db._conn.execute("DROP TABLE notification_inbox")
    db._conn.execute(
        "CREATE TABLE notification_inbox ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL, "
        "title TEXT NOT NULL DEFAULT '', kind TEXT NOT NULL DEFAULT '', "
        "message TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, read_at TEXT)"
    )
    db._conn.execute(
        "INSERT INTO notification_inbox(conversation_id, title, kind, message, created_at) "
        "VALUES('c1','t','terminal','قديم','t0')"
    )
    db._conn.commit()
    db.close()

    db2 = Database(path)  # الفتح التاني يعمل ALTER + INDEX
    cols = {r["name"] for r in db2._conn.execute("PRAGMA table_info(notification_inbox)")}
    assert "event_key" in cols
    assert db2.count_inbox() == 1  # السجل القديم محفوظ (event_key=NULL)
    # القيد بقى شغال.
    db2.add_inbox_item("c1", "t", "terminal", "x", "t1", event_key="k")
    assert db2.add_inbox_item("c1", "t", "terminal", "x", "t2", event_key="k") is None
    db2.close()


def test_inbox_global_cap_prunes_oldest(tmp_path):
    """السقف العام بيحتفظ بأحدث INBOX_MAX_TOTAL عبر كل المحادثات (للمقروءة)."""
    from bot.db import INBOX_MAX_TOTAL

    db = make_db(tmp_path)
    # نتجاوز السقف بمحادثات مختلفة (عشان السقف لكل-محادثة ما يشتغلش).
    for i in range(INBOX_MAX_TOTAL + 25):
        db.add_inbox_item(f"c{i % 60}", "t", "terminal", f"m{i}", f"t{i}")
    db.mark_all_inbox_read("tr")  # المقروءة بس مؤهّلة للتقليم (Batch 3R-FIX)
    db.add_inbox_item("cZ", "t", "terminal", "mZ", "tZ")  # غير مقروء (يستدعي التقليم العام)
    # المقروءة اتقلّمت للسقف العام، والصف غير المقروء محفوظ فوقه (سقف ناعم).
    read_kept = [it for it in db.list_inbox(limit=1000) if not it.unread]
    unread_kept = [it for it in db.list_inbox(limit=1000) if it.unread]
    assert len(read_kept) == INBOX_MAX_TOTAL
    assert [it.message for it in unread_kept] == ["mZ"]
    # الأحدث محفوظ والأقدم المقروء اتشال.
    newest = db.list_inbox(limit=1)[0]
    assert newest.message == "mZ"
    assert all(it.message != "m0" for it in db.list_inbox(limit=1000))
    db.close()


def test_inbox_batch1_batch2_tables_preserved(tmp_path):
    """التغيير إضافي: جداول Batch 1/2 (watched/notification_state/outbox/...) لسه موجودة."""
    db = make_db(tmp_path)
    tables = {
        r["name"]
        for r in db._conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    for t in ("watched", "notification_state", "notifier_pending", "outbox", "creation_jobs",
              "notification_inbox"):
        assert t in tables
    db.close()


def test_inbox_created_at_and_event_key_roundtrip(tmp_path):
    """الحقول المحفوظة بترجع زي ما هي (created_at UTC ISO + event_key)."""
    db = make_db(tmp_path)
    db.add_inbox_item("c1", "عنوان", "proactive", "نص", "2026-10-13T00:00:00+00:00",
                      event_key="c1|proactive|finished")
    it = db.list_inbox()[0]
    assert it.created_at == "2026-10-13T00:00:00+00:00"
    assert it.event_key == "c1|proactive|finished"
    db.close()
