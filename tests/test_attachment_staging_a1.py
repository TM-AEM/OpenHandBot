"""OHB2-P0-A1 — اختبارات المخزن المحلي الآمن + التحقّق + تسلسل row-first.

نطاق A1: جذر staging محلي (0700) بجانب قاعدة البيانات، تحقّق حجم/نوع، أسماء مُعتِمة،
حصر في الجذر، وتسلسل row-first. **لا** دورة حياة دفعة (A2)، ولا نص مصاحب (A3)، ولا
كنس/تنظيف (A4)، ولا نقل/تسليم بعيد (B). كل الاختبارات معزولة (tmp_path + sqlite مؤقّت).

مرجع التصميم: `docs/proposals/OHB2-P0-STAGED-IMPLEMENTATION-PLAN.md` (R4) Stage A1 + §3.3.
"""

import os
import re
import sqlite3

import pytest

from bot import attachments
from bot.attachments import (
    MAX_ATTACHMENT_BYTES,
    StageStatus,
    StagingStore,
    sanitize_display_name,
    staging_root_for,
)
from bot.db import ATTACHMENT_BATCH_PENDING, ATTACHMENT_ITEM_STORED, Database

_TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")


def make_store(tmp_path, *, max_bytes=MAX_ATTACHMENT_BYTES):
    db_path = str(tmp_path / "state.sqlite3")
    db = Database(db_path)
    store = StagingStore(db, db_path, max_bytes=max_bytes)
    return db, store, db_path


def add_batch(db, batch_id="b1", telegram_id=111, conversation_id="conv-a"):
    db.create_attachment_batch(batch_id, telegram_id, conversation_id, "2026-11-11T00:00:00+00:00")


def staged_files(store):
    root = store.root
    if not root.exists():
        return []
    return sorted(p.name for p in root.iterdir())


# ------------------------------------------------------------------ A. التخزين السليم
def test_valid_attachment_is_stored_and_item_marked_stored(tmp_path):
    db, store, _ = make_store(tmp_path)
    add_batch(db)
    payload = b"hello, this is a text note"
    res = store.store(
        telegram_id=111, batch_id="b1", item_id="i1",
        display_name="note.txt", chunks=[payload],
    )
    assert res.status is StageStatus.STORED
    assert res.size_bytes == len(payload)
    # ملف واحد فقط باسم مُعتِم، والمحتوى مطابق.
    files_here = staged_files(store)
    assert files_here == [res.staging_token]
    assert (store.root / res.staging_token).read_bytes() == payload
    # حالة العنصر = stored + الحجم الفعلي.
    items = db.list_attachment_items("b1")
    assert len(items) == 1
    assert items[0].status == ATTACHMENT_ITEM_STORED
    assert items[0].size_bytes == len(payload)
    assert items[0].staging_token == res.staging_token


def test_staging_root_is_0700_and_beside_db(tmp_path):
    db, store, db_path = make_store(tmp_path)
    add_batch(db)
    store.store(telegram_id=111, batch_id="b1", item_id="i1",
                display_name="a.txt", chunks=[b"x"])
    root = store.ensure_root()
    assert root == staging_root_for(db_path)
    assert root.parent == tmp_path  # بجانب قاعدة البيانات (نفس مجلد الحالة)
    assert (os.stat(str(root)).st_mode & 0o777) == 0o700


# ----------------------------------------------------- B. رفض النوع (امتداد/بصمة)
@pytest.mark.parametrize("name", ["evil.exe", "run.sh", "a.py", "app.bat", "x.ps1", "lib.so"])
def test_denied_extension_rejected_without_file(tmp_path, name):
    db, store, _ = make_store(tmp_path)
    add_batch(db)
    res = store.store(telegram_id=111, batch_id="b1", item_id="i1",
                      display_name=name, chunks=[b"MZ... or script"])
    assert res.status is StageStatus.REJECTED_TYPE
    assert staged_files(store) == []          # مفيش ملف اتكتب
    assert db.list_attachment_items("b1") == []  # ومفيش صف عنصر


def test_denied_magic_bytes_rejected_even_with_safe_extension(tmp_path):
    # امتداد مسموح لكن المحتوى تنفيذي (ELF) ⇒ مرفوض بعد الكتابة، بلا `stored` وبلا ملف.
    db, store, _ = make_store(tmp_path)
    add_batch(db)
    res = store.store(telegram_id=111, batch_id="b1", item_id="i1",
                      display_name="report.txt", chunks=[b"\x7fELF\x02\x01\x01\x00rest"])
    assert res.status is StageStatus.REJECTED_TYPE
    assert staged_files(store) == []
    items = db.list_attachment_items("b1")
    assert len(items) == 1 and items[0].status == ATTACHMENT_BATCH_PENDING  # فشل ⇒ pending


def test_shebang_script_rejected(tmp_path):
    db, store, _ = make_store(tmp_path)
    add_batch(db)
    res = store.store(telegram_id=111, batch_id="b1", item_id="i1",
                      display_name="notes.txt", chunks=[b"#!/bin/sh\nrm -rf /"])
    assert res.status is StageStatus.REJECTED_TYPE
    assert staged_files(store) == []


# ------------------------------------------------------------- C. فرض الحد الأقصى
def test_declared_oversize_rejected_before_any_row_or_file(tmp_path):
    db, store, _ = make_store(tmp_path)
    add_batch(db)
    res = store.store(telegram_id=111, batch_id="b1", item_id="i1",
                      display_name="big.txt", chunks=[b"x"], declared_size=MAX_ATTACHMENT_BYTES + 1)
    assert res.status is StageStatus.REJECTED_SIZE
    assert staged_files(store) == []
    assert db.list_attachment_items("b1") == []  # مفيش صف كمان


def test_actual_oversize_rejected_midwrite_leaves_pending_no_file(tmp_path):
    db, store, _ = make_store(tmp_path, max_bytes=10)
    add_batch(db)
    res = store.store(telegram_id=111, batch_id="b1", item_id="i1",
                      display_name="big.txt", chunks=[b"12345", b"67890", b"X"])  # 11 > 10
    assert res.status is StageStatus.REJECTED_SIZE
    assert staged_files(store) == []  # الملف الجزئي اتمسح
    items = db.list_attachment_items("b1")
    assert len(items) == 1 and items[0].status == ATTACHMENT_BATCH_PENDING


def test_exact_max_size_accepted(tmp_path):
    db, store, _ = make_store(tmp_path, max_bytes=10)
    add_batch(db)
    res = store.store(telegram_id=111, batch_id="b1", item_id="i1",
                      display_name="ok.txt", chunks=[b"1234567890"])
    assert res.status is StageStatus.STORED
    assert res.size_bytes == 10


def test_empty_payload_rejected(tmp_path):
    db, store, _ = make_store(tmp_path)
    add_batch(db)
    res = store.store(telegram_id=111, batch_id="b1", item_id="i1",
                      display_name="empty.txt", chunks=[])
    assert res.status is StageStatus.REJECTED_EMPTY
    assert staged_files(store) == []
    assert db.list_attachment_items("b1")[0].status == ATTACHMENT_BATCH_PENDING


# ------------------------------------------ D. أسماء آمنة / اجتياز / مسار مطلق
def test_display_name_normalization_strips_path_components():
    assert sanitize_display_name("../../etc/passwd") == "passwd"
    assert sanitize_display_name("/etc/passwd") == "passwd"
    assert sanitize_display_name("C:\\Windows\\evil.txt") == "evil.txt"
    assert sanitize_display_name("..") is None
    assert sanitize_display_name("") is None
    assert sanitize_display_name(None) is None
    assert sanitize_display_name("a\x00b.txt") == "ab.txt"


def test_traversal_display_name_stored_under_token_only(tmp_path):
    db, store, _ = make_store(tmp_path)
    add_batch(db)
    res = store.store(telegram_id=111, batch_id="b1", item_id="i1",
                      display_name="../../../../tmp/escape.txt", chunks=[b"data"])
    assert res.status is StageStatus.STORED
    # الملف اتخزّن بالتوكن جوه الجذر فقط؛ الاسم كبيانات وصفية بس.
    assert staged_files(store) == [res.staging_token]
    item = db.list_attachment_items("b1")[0]
    assert item.display_name == "escape.txt"
    assert item.staging_token == res.staging_token
    # مفيش ملف هرب خارج الجذر.
    assert not (tmp_path.parent / "escape.txt").exists()
    assert not os.path.exists("/tmp/escape.txt")


def test_absolute_path_display_name_does_not_control_storage_path(tmp_path):
    db, store, _ = make_store(tmp_path)
    add_batch(db)
    res = store.store(telegram_id=111, batch_id="b1", item_id="i1",
                      display_name="/etc/passwd", chunks=[b"data"])
    assert res.status is StageStatus.STORED
    assert staged_files(store) == [res.staging_token]
    assert (store.root / res.staging_token).is_file()


# --------------------------------------------- E. حصر الجذر / symlink / بلا استبدال
def test_symlinked_staging_root_is_rejected(tmp_path):
    db, store, _ = make_store(tmp_path)
    add_batch(db)
    outside = tmp_path / "outside"
    outside.mkdir()
    # نحوّل الجذر لـ symlink يشاور بره.
    os.symlink(str(outside), str(store.root))
    res = store.store(telegram_id=111, batch_id="b1", item_id="i1",
                      display_name="a.txt", chunks=[b"data"])
    assert res.status is StageStatus.WRITE_FAILED
    assert list(outside.iterdir()) == []  # مفيش كتابة بره الجذر


def test_no_silent_overwrite_on_token_collision(tmp_path, monkeypatch):
    db, store, _ = make_store(tmp_path)
    add_batch(db)
    monkeypatch.setattr(attachments, "new_staging_token", lambda: "f" * 32)
    root = store.ensure_root()
    victim = root / ("f" * 32)
    victim.write_bytes(b"ORIGINAL")  # ملف قائم بالاسم المُعتِم
    res = store.store(telegram_id=111, batch_id="b1", item_id="i1",
                      display_name="a.txt", chunks=[b"NEW"])
    assert res.status is StageStatus.WRITE_FAILED
    assert victim.read_bytes() == b"ORIGINAL"  # ما اتعملهوش استبدال
    assert db.list_attachment_items("b1")[0].status == ATTACHMENT_BATCH_PENDING


def test_staging_root_confinement_token_has_no_separators(tmp_path):
    db, store, _ = make_store(tmp_path)
    add_batch(db)
    res = store.store(telegram_id=111, batch_id="b1", item_id="i1",
                      display_name="a.txt", chunks=[b"data"])
    assert _TOKEN_RE.match(res.staging_token)
    assert "/" not in res.staging_token and ".." not in res.staging_token
    # المسار النهائي جوه الجذر فعلاً.
    real_root = os.path.realpath(str(store.root))
    real_file = os.path.realpath(str(store.root / res.staging_token))
    assert real_file.startswith(real_root + os.sep)


# ------------------------------------------------- F. الملكية والربط بالدفعة
def test_store_rejects_unknown_batch(tmp_path):
    db, store, _ = make_store(tmp_path)
    res = store.store(telegram_id=111, batch_id="ghost", item_id="i1",
                      display_name="a.txt", chunks=[b"data"])
    assert res.status is StageStatus.REJECTED_BATCH
    assert staged_files(store) == []


def test_store_rejects_wrong_owner(tmp_path):
    db, store, _ = make_store(tmp_path)
    add_batch(db, telegram_id=111)
    res = store.store(telegram_id=222, batch_id="b1", item_id="i1",
                      display_name="a.txt", chunks=[b"data"])
    assert res.status is StageStatus.REJECTED_BATCH
    assert staged_files(store) == []
    assert db.list_attachment_items("b1") == []


def test_store_rejects_invalid_conversation_id_on_batch(tmp_path):
    db, store, _ = make_store(tmp_path)
    db.create_attachment_batch("b1", 111, "../../evil", "2026-11-11T00:00:00+00:00")
    res = store.store(telegram_id=111, batch_id="b1", item_id="i1",
                      display_name="a.txt", chunks=[b"data"])
    assert res.status is StageStatus.REJECTED_BATCH
    assert staged_files(store) == []


# ------------------------------------------------ G. تسلسل row-first (مُثبَت)
def test_row_first_db_row_exists_before_bytes_are_written(tmp_path, monkeypatch):
    db, store, _ = make_store(tmp_path)
    add_batch(db)
    observed = {}

    real_open = os.open

    def spy_open(path, flags, *args, **kwargs):
        # عند لحظة إنشاء ملف الـ staging، لازم يكون صف العنصر موجود بالفعل (`pending`).
        if os.path.basename(str(path)) and os.path.dirname(os.path.realpath(str(path))) == \
                os.path.realpath(str(store.root)):
            observed["items_at_open"] = db.list_attachment_items("b1")
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", spy_open)

    events = []

    def chunks():
        events.append("bytes")
        yield b"payload"

    res = store.store(telegram_id=111, batch_id="b1", item_id="i1",
                      display_name="a.txt", chunks=chunks())
    assert res.status is StageStatus.STORED
    # الصف كان موجود (pending) لحظة فتح ملف الكتابة ⇒ row-first مُثبَت.
    assert "items_at_open" in observed
    assert [i.item_id for i in observed["items_at_open"]] == ["i1"]
    assert observed["items_at_open"][0].status == ATTACHMENT_BATCH_PENDING


def test_stored_only_after_write_completes(tmp_path, monkeypatch):
    db, store, _ = make_store(tmp_path)
    add_batch(db)
    seen = {}

    def chunks():
        # قبل أول بايت: العنصر لسه مش stored.
        seen["before"] = db.list_attachment_items("b1")[0].status
        yield b"payload"

    res = store.store(telegram_id=111, batch_id="b1", item_id="i1",
                      display_name="a.txt", chunks=chunks())
    assert seen["before"] == ATTACHMENT_BATCH_PENDING
    assert res.status is StageStatus.STORED
    assert db.list_attachment_items("b1")[0].status == ATTACHMENT_ITEM_STORED


# ----------------------------------------------- H. فشل جزئي / فشل قاعدة بيانات
def test_partial_write_failure_leaves_pending_and_no_file(tmp_path):
    db, store, _ = make_store(tmp_path)
    add_batch(db)

    def chunks():
        yield b"partial"
        raise OSError("download interrupted")

    res = store.store(telegram_id=111, batch_id="b1", item_id="i1",
                      display_name="a.txt", chunks=chunks())
    assert res.status is StageStatus.WRITE_FAILED
    assert staged_files(store) == []  # الملف الجزئي اتمسح
    assert db.list_attachment_items("b1")[0].status == ATTACHMENT_BATCH_PENDING


def test_db_failure_on_row_insert_is_fail_closed(tmp_path):
    db, store, _ = make_store(tmp_path)
    add_batch(db)

    def boom(*a, **k):
        raise sqlite3.OperationalError("db down")

    db.add_attachment_item = boom  # فشل تسجيل الصف
    res = store.store(telegram_id=111, batch_id="b1", item_id="i1",
                      display_name="a.txt", chunks=[b"data"])
    assert res.status is StageStatus.DB_FAILED
    assert staged_files(store) == []  # مفيش بايتات اتكتبت


def test_db_failure_on_status_update_unlinks_file(tmp_path):
    db, store, _ = make_store(tmp_path)
    add_batch(db)
    db.set_attachment_item_status = lambda *a, **k: False  # مفيش صف اتحدّث
    res = store.store(telegram_id=111, batch_id="b1", item_id="i1",
                      display_name="a.txt", chunks=[b"data"])
    assert res.status is StageStatus.DB_FAILED
    assert staged_files(store) == []
    assert db.list_attachment_items("b1")[0].status == ATTACHMENT_BATCH_PENDING


def test_get_batch_db_error_is_fail_closed(tmp_path):
    db, store, _ = make_store(tmp_path)
    add_batch(db)

    def boom(*a, **k):
        raise sqlite3.OperationalError("db down")

    db.get_attachment_batch = boom
    res = store.store(telegram_id=111, batch_id="b1", item_id="i1",
                      display_name="a.txt", chunks=[b"data"])
    assert res.status is StageStatus.DB_FAILED
    assert staged_files(store) == []


# ----------------------------------------------------------- I. بلا وصول عبر الحاويات
def test_staging_token_is_opaque_and_not_derived_from_input(tmp_path):
    db, store, _ = make_store(tmp_path)
    add_batch(db)
    res = store.store(telegram_id=111, batch_id="b1", item_id="i1",
                      display_name="secret-name.txt", chunks=[b"data"])
    assert _TOKEN_RE.match(res.staging_token)
    assert "secret" not in res.staging_token
    assert res.staging_token != res.item_id
    # توكنان مختلفان لنفس الاسم.
    res2 = store.store(telegram_id=111, batch_id="b1", item_id="i2",
                       display_name="secret-name.txt", chunks=[b"data"])
    assert res2.staging_token != res.staging_token


def test_item_without_token_or_missing_file_is_not_stored(tmp_path):
    db, store, _ = make_store(tmp_path)
    add_batch(db)
    # صف يتسجّل يدويًا بحالة pending وبلا توكن (تمثيل عنصر غير مكتمل) ⇒ مش stored.
    db.add_attachment_item("i-manual", "b1")
    item = db.list_attachment_items("b1")[0]
    assert item.status == ATTACHMENT_BATCH_PENDING
    assert item.staging_token is None


# ------------------------------------------------------ J. الحفاظ على سلوك A0
def test_a0_ttl_and_tables_still_intact(tmp_path):
    from datetime import timedelta

    from bot.db import ATTACHMENT_BATCH_TTL, AWAITING_TTL

    assert ATTACHMENT_BATCH_TTL == timedelta(minutes=15)
    assert ATTACHMENT_BATCH_TTL != AWAITING_TTL
    path = str(tmp_path / "t.sqlite3")
    Database(path)
    conn = sqlite3.connect(path)
    try:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()
    assert {"attachment_batches", "attachment_items"} <= names


def test_a0_owner_scope_unchanged(tmp_path):
    db, _, _ = make_store(tmp_path)
    add_batch(db, telegram_id=111)
    assert db.get_attachment_batch("b1", telegram_id=111) is not None
    assert db.get_attachment_batch("b1", telegram_id=222) is None


def test_gitignore_ignores_staging_dir(tmp_path):
    # القاعدة موجودة في .gitignore الفعلي للمستودع.
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    text = open(os.path.join(repo_root, ".gitignore"), encoding="utf-8").read()
    assert "attachment_staging/" in text
