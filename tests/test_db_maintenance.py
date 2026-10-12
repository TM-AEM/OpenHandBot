"""TASK 04D-15: صيانة تكامل SQLite (فحص سريع، تحسين، checkpoint، وعدم الإسقاط)."""
import sqlite3

from bot.db import Database


def test_quick_and_full_check_pass_on_fresh_db(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    assert db.quick_check() is True
    assert db.integrity_check() is True
    db.close()


def test_run_startup_maintenance_returns_true_and_keeps_data(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "عنوان")
    assert db.run_startup_maintenance() is True
    # الصيانة ما بتمسحش بيانات.
    assert db.list_watched()[0].conversation_id == "c1"
    db.close()


def test_optimize_and_checkpoint_are_safe(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_or_group_outbox("c1", 1, "نص", "2026-01-01T00:00:00+00:00")
    db.optimize()
    db.checkpoint()
    assert db.quick_check() is True
    assert db.count_outbox("pending") == 1
    db.close()


def test_corrupt_file_is_rejected_at_open(tmp_path):
    # ملف مش قاعدة بيانات صالحة: الفتح نفسه بيرفض (ما بنسكتش على التلف).
    bad = tmp_path / "bad.sqlite3"
    bad.write_bytes(b"not a sqlite database at all" * 10)
    try:
        Database(str(bad))
    except sqlite3.DatabaseError:
        return
    raise AssertionError("كان لازم فتح قاعدة تالفة يرمي DatabaseError")


def test_check_failure_is_reported_not_raised(tmp_path, monkeypatch):
    # لو الفحص نفسه رمى (تلف حصل بعد الفتح)، run_startup_maintenance بترجّع False
    # من غير ما ترمي، عشان البوت يتعامل بهدوء.
    db = Database(str(tmp_path / "t.sqlite3"))

    def boom():
        raise sqlite3.DatabaseError("تلف")

    monkeypatch.setattr(db, "quick_check", boom)
    assert db.run_startup_maintenance() is False
    db.close()


def test_optimize_failure_does_not_break_startup(tmp_path, monkeypatch):
    # لو التحسين فشل بس القاعدة سليمة ⇒ التشغيل يكمل (True).
    db = Database(str(tmp_path / "t.sqlite3"))

    def boom():
        raise sqlite3.OperationalError("مش مدعوم")

    monkeypatch.setattr(db, "optimize", boom)
    assert db.run_startup_maintenance() is True
    db.close()


def test_wal_checkpoint_after_writes(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    for i in range(50):
        db.add_or_group_outbox(f"c{i}", 1, "x", "2026-01-01T00:00:00+00:00")
    db.checkpoint("TRUNCATE")
    assert db.quick_check() is True
    db.close()
