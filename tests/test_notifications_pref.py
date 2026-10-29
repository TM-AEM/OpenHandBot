"""NTF-02: تفضيل الإشعارات المستمر — الافتراضي مفعّل، بيبقى بعد إعادة الفتح، ويتبدّل."""
import sqlite3

from bot.db import Database


def test_default_enabled_on_fresh_db(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    assert db.get_notifications_enabled() is True


def test_toggle_off_and_on(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.set_notifications_enabled(False)
    assert db.get_notifications_enabled() is False
    db.set_notifications_enabled(True)
    assert db.get_notifications_enabled() is True


def test_persistence_across_reopen(tmp_path):
    path = str(tmp_path / "t.sqlite3")
    db = Database(path)
    db.set_notifications_enabled(False)
    db.close()

    db2 = Database(path)
    assert db2.get_notifications_enabled() is False
    db2.close()


def test_setting_is_not_a_secret_and_isolated(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.set_setting("unrelated_flag", "x")
    assert db.get_notifications_enabled() is True  # مفتاح تاني ما يأثرش
    assert db.get_setting("unrelated_flag") == "x"


def test_unknown_value_defaults_to_disabled(tmp_path):
    # أي قيمة مش ضمن {1,true,yes,on} تُعتبر معطّلة (fail-safe: ما نبعتش إشعارات غلط).
    db = Database(str(tmp_path / "t.sqlite3"))
    db.set_setting(Database.NOTIFICATIONS_KEY, "maybe")
    assert db.get_notifications_enabled() is False


def test_migration_from_existing_db_without_settings_table(tmp_path):
    """قاعدة أُنشئت بالنسخة الحالية (بدون جدول settings) بتترقّى إضافيًا."""
    path = str(tmp_path / "legacy.sqlite3")
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE watched (conversation_id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '',"
        " last_state TEXT, chat_id INTEGER, submitted_at TEXT, added_at TEXT,"
        " retry_count INTEGER NOT NULL DEFAULT 0);"
    )
    conn.execute("INSERT INTO watched(conversation_id, title) VALUES('c1', 'عنوان')")
    conn.commit()
    conn.close()

    db = Database(path)  # الترقية بتحصل هنا (CREATE TABLE IF NOT EXISTS settings)
    assert db.get_notifications_enabled() is True
    assert len(db.list_watched()) == 1  # بيانات قديمة ما اتلمستش
    db.set_notifications_enabled(False)
    assert db.get_notifications_enabled() is False
    db.close()


def test_migration_adds_notification_state_table(tmp_path):
    """قاعدة قديمة (بدون settings/notification_state) بتاخد الجدولين إضافيًا."""
    path = str(tmp_path / "legacy2.sqlite3")
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE watched (conversation_id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '',"
        " last_state TEXT, chat_id INTEGER, submitted_at TEXT, added_at TEXT,"
        " retry_count INTEGER NOT NULL DEFAULT 0);"
    )
    conn.commit()
    conn.close()

    db = Database(path)
    assert db.list_notification_states() == {}
    db.upsert_notification_state("c1", status="running", notified_status=None, updated_at="t")
    assert db.get_notification_state("c1").status == "running"
    assert db.get_notification_state("c1").notified_status is None
    db.close()


def test_narrow_update_does_not_clobber_other_columns(tmp_path):
    """التحديث الضيّق مايدهسش أعمدة كتبها كاتب تاني (زي المراقب)."""
    db = Database(str(tmp_path / "t.sqlite3"))
    db.upsert_notification_state("c1", status="running", notified_status=None)
    # المراقب سجّل إن إشعار "finished" اتبعت فعلًا.
    db.record_notification_sent("c1", "finished", "t1")
    # المُبلّغ حدّث الحالة المرصودة بس — مايفسدش notified_status.
    db.upsert_notification_state("c1", status="finished")
    st = db.get_notification_state("c1")
    assert st.status == "finished"
    assert st.notified_status == "finished"  # اتكتب من record_notification_sent وفضل
    db.close()


def test_migration_adds_pending_delivery_state_column(tmp_path):
    """NTF-13: قاعدة قديمة (بدون pending_delivery_state) بتاخد العمود إضافيًا، والكتابة
    الضيّقة تشتغل من غير ما تلمس باقي الأعمدة."""
    path = str(tmp_path / "legacy3.sqlite3")
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE watched (conversation_id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '',"
        " last_state TEXT, chat_id INTEGER, submitted_at TEXT, added_at TEXT,"
        " retry_count INTEGER NOT NULL DEFAULT 0);"
    )
    conn.execute("INSERT INTO watched(conversation_id, title) VALUES('c1', 'عنوان')")
    conn.commit()
    conn.close()

    db = Database(path)
    assert db.list_watched()[0].pending_delivery_state is None  # عمود جديد بقيمة NULL
    db.set_pending_delivery("c1", "finished")
    assert db.list_watched()[0].pending_delivery_state == "finished"
    db.clear_pending_delivery("c1")
    assert db.list_watched()[0].pending_delivery_state is None
    db.close()


# --------------------------------- NTF-15.1: atomic remove_watched (H-2)
import pytest  # noqa: E402


class _RecFailsBeforeWriteDb(Database):
    """record_notification_sent يرمي قبل أي كتابة (فشل قبل أي أثر)."""

    def record_notification_sent(self, cid, status, now, *, _commit=True):
        raise sqlite3.OperationalError("disk I/O error (record)")


class _RecFailsAfterInsertDb(Database):
    """record_notification_sent يكتب INSERT ثم يرمي (فشل بعد محاولة كتابة وقبل commit)."""

    def record_notification_sent(self, cid, status, now, *, _commit=True):
        self._conn.execute(
            "INSERT OR IGNORE INTO notification_state(conversation_id) VALUES(?)", (cid,)
        )
        raise sqlite3.OperationalError("disk I/O error (record post-insert)")


def _seed_watched(db, cid="c1"):
    db.add_watched(cid, "t")
    db.set_last_state(cid, "running")
    db.upsert_notification_state(cid, status="running", notified_status="running", updated_at="t")


def test_remove_watched_rolls_back_when_record_fails_before_write(tmp_path):
    db = _RecFailsBeforeWriteDb(str(tmp_path / "t.sqlite3"))
    _seed_watched(db)
    db.set_pending_delivery("c1", "finished")
    with pytest.raises(sqlite3.OperationalError):
        db.remove_watched("c1")
    assert db.is_watched("c1")  # الحذف اترجع
    assert db.get_notification_state("c1").notified_status == "running"  # مفيش تسجيل


def test_remove_watched_rolls_back_when_record_fails_after_insert(tmp_path):
    db = _RecFailsAfterInsertDb(str(tmp_path / "t.sqlite3"))
    _seed_watched(db)
    db.set_pending_delivery("c1", "finished")
    with pytest.raises(sqlite3.OperationalError):
        db.remove_watched("c1")
    assert db.is_watched("c1")  # لسه متابَع
    assert db.get_notification_state("c1").notified_status == "running"


def test_remove_watched_commits_record_and_deletion_together(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    _seed_watched(db)
    db.set_pending_delivery("c1", "finished")
    db.remove_watched("c1")
    assert not db.is_watched("c1")
    assert db.get_notification_state("c1").notified_status == "finished"


def test_remove_watched_rolls_back_when_delete_fails(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    _seed_watched(db)
    db.set_pending_delivery("c1", "finished")
    # حاجز على الحذف: الفشل بعد ما التسجيل اتحاول ⇒ لازم يرجع كله.
    db._conn.execute(
        "CREATE TRIGGER block_del BEFORE DELETE ON watched "
        "BEGIN SELECT RAISE(ABORT, 'blocked'); END"
    )
    db._conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        db.remove_watched("c1")
    assert db.is_watched("c1")  # الحذف فشل ⇒ الصف باقي
    assert db.get_notification_state("c1").notified_status == "running"  # والتسجيل اترجع


def test_remove_watched_missing_row_is_noop(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.remove_watched("nope")  # مفيش استثناء
    assert not db.is_watched("nope")
