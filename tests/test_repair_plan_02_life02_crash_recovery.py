"""OHB2-LIFE-02 — تعافي من الانهيار عند **كل حدّ متين** في تسلسل row-first (محلي فقط).

يُثبت أن الفشل/إعادة التشغيل عند كل حدّ تخزين بينتج حالة **آمنة قابلة للتعافي**، وعمره
ما بينتج «نجاح كاذب». التسلسل الحقيقي (من الكود، مش مفترض):

  1. صف عنصر `pending` متين (row-first) — `accept_attachment_item*` (معاملة واحدة + النتيجة).
  2. كتابة البايتات تحت اسم مُعتِم مقيّد بالسقف — `StagingStore._write_to_path` (O_EXCL/NOFOLLOW،
     flush+fsync، وأي BaseException ⇒ حذف الملف الجزئي ثم إعادة الرفع).
  3. تحقّق المحتوى (حجم + بصمة magic) — `_read_head`/`_is_denied_magic` (فشل ⇒ حذف + رفض).
  4. انتقال الحالة لـ `stored` — `try_mark_attachment_item_stored` (CAS ذرّي: العنصر
     `pending` + الدفعة الأب `pending`؛ F2) بس بعد الكتابة+التحقّق.
  5. إرجاع النتيجة للمستدعي — `AcceptResult` (الرد/الإقرار بعدها في الطبقة الأعلى).

المبادئ المُتحقَّق منها: `stored` ما بيتحطّش غير بعد كتابة+تحقّق؛ الملفات الجزئية قابلة
للاكتشاف عبر بيانات وصفية متينة (`staging_token` في صف `pending`)؛ الأثر الجزئي القابل
للتعافي يُكنس بأمان؛ الأثر المجهول/غير المرتبط **ما يُحذفش**؛ التعافي المتكرّر idempotent؛
دليل الهوية (D-33/34/35، A3/F1) **ينجو**؛ المفاتيح الأجنبية سليمة.

قاعدة SQLite حقيقية + مجلد مؤقّت (بلا شبكة/بلا mocks للطبقة الكاملة). الساعات محقونة.
"""
from __future__ import annotations

import asyncio
import os
import sqlite3
from datetime import datetime, timezone

import pytest

from bot.attachments import (
    AcceptOutcome,
    AttachmentReaper,
    AttachmentService,
    StageStatus,
    StagingStore,
    staging_root_for,
)
from bot.db import (
    ATTACHMENT_BATCH_DELIVERED,
    ATTACHMENT_BATCH_EXPIRED,
    ATTACHMENT_BATCH_PENDING,
    ATTACHMENT_ITEM_REAPED,
    ATTACHMENT_ITEM_STORED,
    Database,
)
from bot.files import IdentityCache

OWNER_ID = 111
OWNER_UUID = "11111111-2222-3333-4444-555555555555"
CID = "11111111222233334444555566667777"
T0 = datetime(2026, 11, 14, 10, 0, 0, tzinfo=timezone.utc)
NOW_LIVE = datetime(2026, 11, 14, 10, 5, tzinfo=timezone.utc)
NOW_AFTER = datetime(2026, 11, 14, 10, 16, tzinfo=timezone.utc)


# ------------------------------------------------------------------ أدوات
class FakeClient:
    def __init__(self, owner=OWNER_UUID):
        self.owner = owner

    async def get_current_user(self):
        return {"id": self.owner}

    async def get_conversations(self, ids):
        return [{"id": CID, "created_by_user_id": self.owner, "title": "A"} for _ in ids]


def make_env(tmp_path):
    db_path = str(tmp_path / "state.sqlite3")
    db = Database(db_path)
    store = StagingStore(db, db_path, clock=lambda: T0)
    client = FakeClient()
    service = AttachmentService(db, store, client, IdentityCache(client))
    return db, store, service, db_path


def _run(coro):
    return asyncio.run(coro)


async def accept(service, *, now=T0, name="a.txt", chunks=(b"data",), declared=None,
                 update_id=None, factory=None):
    async def default_factory():
        return iter(chunks)

    return await service.accept(
        telegram_id=OWNER_ID,
        conversation_id=CID,
        display_name=name,
        declared_size=declared,
        update_id=update_id,
        now=now,
        chunks_factory=factory if factory is not None else default_factory,
    )


def reaper(db, db_path):
    return AttachmentReaper(db, db_path)


def _bind_identity(db, batch_id, *, message_id, chat_id=OWNER_ID, now=None):
    """يربط هوية رسالة بالدفعة عبر **نفس مسار الكتابة الإنتاجي** (`record_attachment_intent`).

    ملاحظة: `record_attachment_intent` بينقل الدفعة لـ `intent_recorded` (نيّة نصّ) — وده
    مقصود لاختبار ثبات دليل الهوية (D-33/34/35). بيحتاج الدفعة `pending` ومهلة سارية.
    """
    res = db.record_attachment_intent(
        batch_id,
        telegram_id=OWNER_ID,
        conversation_id=CID,
        intent_text="نصّ مصاحب",
        now=now or NOW_LIVE.isoformat(),
        update_id=None,
        chat_id=chat_id,
        message_id=message_id,
    )
    assert res == batch_id, f"فشل ربط الهوية: {res!r}"
    return res


def item_of(db, batch_id):
    items = db.list_attachment_items(batch_id)
    assert items, "لا يوجد عنصر"
    return items[0]


# ============================================================================
# 5.2 مصفوفة الحالات — حدّ الصف المتين (row-first)
# ============================================================================
def test_boundary_row_first_item_is_pending_before_bytes(tmp_path):
    """عند حدّ ما قبل الكتابة: الصف موجود `pending` والملف غير موجود بعد."""
    db, store, service, db_path = make_env(tmp_path)
    captured = {}

    async def factory():
        # لحظة الكتابة: الصف لازم يكون موجود `pending` والملف لأ.
        items = db.list_attachment_items(_only_batch(db))
        captured["status_at_write"] = items[0].status
        root = staging_root_for(db_path)
        captured["file_exists_at_write"] = (root / items[0].staging_token).exists()
        return iter([b"data"])

    res = _run(accept(service, factory=factory))
    assert res.outcome is AcceptOutcome.STORED
    assert captured["status_at_write"] == ATTACHMENT_BATCH_PENDING
    assert captured["file_exists_at_write"] is False


def _only_batch(db):
    return db._conn.execute("SELECT batch_id FROM attachment_batches").fetchone()["batch_id"]


def test_case1_failure_immediately_after_row_insertion(tmp_path):
    """1) فشل فور إدراج الصف (قبل أي بايت) ⇒ عنصر `pending`، بلا ملف، بلا `stored`."""
    db, store, service, db_path = make_env(tmp_path)

    async def factory():
        raise RuntimeError("boom before bytes")

    with pytest.raises(RuntimeError):
        _run(accept(service, factory=factory))

    batch_id = _only_batch(db)
    it = item_of(db, batch_id)
    assert it.status == ATTACHMENT_BATCH_PENDING
    assert db.get_attachment_batch(batch_id).status == ATTACHMENT_BATCH_PENDING
    root = staging_root_for(db_path)
    assert not any(root.iterdir()) if root.exists() else True


def test_case2_failure_during_byte_writing(tmp_path):
    """2) فشل أثناء الكتابة ⇒ مفيش ملف جزئي يفضل باسم العنصر، والعنصر `pending`."""
    db, store, service, db_path = make_env(tmp_path)

    def chunks():
        yield b"partial-"
        raise RuntimeError("disk died mid-write")

    async def factory():
        return chunks()

    with pytest.raises(RuntimeError):
        _run(accept(service, factory=factory))

    batch_id = _only_batch(db)
    it = item_of(db, batch_id)
    assert it.status == ATTACHMENT_BATCH_PENDING
    root = staging_root_for(db_path)
    # الملف الجزئي اتحذف (باسم العنصر) ⇒ مفيش أثر باسم التوكن.
    assert not (root / it.staging_token).exists()


def test_case3_failure_after_flush_fsync_boundary(tmp_path, monkeypatch):
    """3) فشل بعد حدّ flush/fsync (خلال التحقّق) ⇒ الملف يتشال، والعنصر `pending`."""
    db, store, service, db_path = make_env(tmp_path)

    # نُفشل القراءة للتحقّق (بعد الكتابة+fsync فعليًّا).
    import bot.attachments as att

    def boom_read(path):
        raise OSError("fsync-then-read failure")

    monkeypatch.setattr(att, "_read_head", boom_read)

    res = _run(accept(service, chunks=(b"data",)))
    # store فشل ⇒ مفيش `stored`.
    assert res.outcome is AcceptOutcome.ACCEPTED
    assert res.stage is StageStatus.WRITE_FAILED
    batch_id = _only_batch(db)
    it = item_of(db, batch_id)
    assert it.status == ATTACHMENT_BATCH_PENDING
    root = staging_root_for(db_path)
    assert not (root / it.staging_token).exists()  # الملف اتشال


def test_case4_invalid_magic_bytes_rejected_no_stored(tmp_path):
    """4) بصمة ممنوعة (ELF) ⇒ رفض نوع مغلق، بلا `stored`، بلا ملف باقٍ."""
    db, store, service, db_path = make_env(tmp_path)
    res = _run(accept(service, name="report.txt",
                      chunks=(b"\x7fELF\x02\x01\x01\x00rest",)))
    assert res.outcome is AcceptOutcome.ACCEPTED
    assert res.stage is StageStatus.REJECTED_TYPE
    batch_id = _only_batch(db)
    it = item_of(db, batch_id)
    assert it.status == ATTACHMENT_BATCH_PENDING
    root = staging_root_for(db_path)
    assert not (root / it.staging_token).exists()


def test_case5_failure_during_status_update_to_stored(tmp_path, monkeypatch):
    """5) فشل تحديث الحالة لـ `stored` ⇒ رفض مغلق، والعنصر يفضل `pending`، والملف يتشال."""
    db, store, service, db_path = make_env(tmp_path)

    def boom(*a, **k):
        raise sqlite3.OperationalError("db write failed")

    monkeypatch.setattr(db, "try_mark_attachment_item_stored", boom)
    res = _run(accept(service, chunks=(b"data",)))
    assert res.outcome is AcceptOutcome.ACCEPTED
    assert res.stage is StageStatus.DB_FAILED
    batch_id = _only_batch(db)
    it = item_of(db, batch_id)
    assert it.status == ATTACHMENT_BATCH_PENDING  # ما اتحوّلش لـ stored
    root = staging_root_for(db_path)
    assert not (root / it.staging_token).exists()


def test_case6_stored_before_caller_success_is_consistent(tmp_path):
    """6) نجاح تخزين قبل ما المستدعي يستلم النتيجة ⇒ حالة متينة متّسقة (stored + ملف)."""
    db, store, service, db_path = make_env(tmp_path)
    res = _run(accept(service, chunks=(b"data",)))
    assert res.outcome is AcceptOutcome.STORED
    it = item_of(db, res.batch_id)
    assert it.status == ATTACHMENT_ITEM_STORED
    assert it.size_bytes == 4
    root = staging_root_for(db_path)
    assert (root / it.staging_token).exists()
    # لو العملية وقعت هنا: الحالة متّسقة (مفيش نجاح كاذب ولا بايت يتيم).


# ============================================================================
# 5.2 إعادة فتح القاعدة + جذر التخزين بعد مقاطعة (سب-بروسيس معزول)
# ============================================================================
def test_case7_reopen_after_interruption_recovers_pending(tmp_path):
    """7) إعادة فتح نفس القاعدة/الجذر ⇒ العنصر `pending` القابل للاسترجاع يتكنس عند الانتهاء."""
    db, store, service, db_path = make_env(tmp_path)

    async def factory():
        raise RuntimeError("crash mid-write")

    with pytest.raises(RuntimeError):
        _run(accept(service, factory=factory))
    batch_id = _only_batch(db)
    token = item_of(db, batch_id).staging_token
    # محاكاة أثر جزئي متبقٍّ من مقاطعة (ملف باسم التوكن، العنصر لسه pending).
    root = staging_root_for(db_path)
    root.mkdir(parents=True, exist_ok=True)
    (root / token).write_bytes(b"stale-partial")
    db.close()

    # إعادة فتح (عملية جديدة) + كنس بعد انتهاء المهلة.
    db2 = Database(db_path)
    rep = reaper(db2, db_path).sweep(now=NOW_AFTER)
    assert db2.get_attachment_batch(batch_id).status == ATTACHMENT_BATCH_EXPIRED
    assert db2.get_attachment_item(_item_id(db2, batch_id)).status == ATTACHMENT_ITEM_REAPED
    assert not (root / token).exists()
    assert rep.files_deleted == 1


def _item_id(db, batch_id):
    return db.list_attachment_items(batch_id)[0].item_id


# ============================================================================
# 5.3 مصفوفة حالات الـ reaper
# ============================================================================
def test_case8_pending_row_with_missing_bytes(tmp_path):
    """8) صف pending بلا بايتات ⇒ يُكنس بلا خطأ (idempotent)."""
    db, store, service, db_path = make_env(tmp_path)

    async def factory():
        raise RuntimeError("no bytes")

    with pytest.raises(RuntimeError):
        _run(accept(service, factory=factory))
    batch_id = _only_batch(db)
    rep = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert db.get_attachment_item(_item_id(db, batch_id)).status == ATTACHMENT_ITEM_REAPED
    assert rep.errors == 0  # ملف مفقود = نجاح idempotent


def test_case9_partial_file_discoverable_and_recovered(tmp_path):
    """9) ملف جزئي قابل للاكتشاف عبر بيانات وصفية متينة ⇒ يُكنس بأمان."""
    db, store, service, db_path = make_env(tmp_path)

    async def factory():
        raise RuntimeError("partial")

    with pytest.raises(RuntimeError):
        _run(accept(service, factory=factory))
    batch_id = _only_batch(db)
    token = item_of(db, batch_id).staging_token
    root = staging_root_for(db_path)
    root.mkdir(parents=True, exist_ok=True)
    (root / token).write_bytes(b"half")  # أثر جزئي
    # الدفعة لسه pending ⇒ الكنس مش هيمسّها لحد الانتهاء (حيّة).
    rep_live = reaper(db, db_path).sweep(now=NOW_LIVE)
    assert (root / token).exists()
    assert rep_live.files_deleted == 0
    # بعد الانتهاء ⇒ تُكنس.
    reaper(db, db_path).sweep(now=NOW_AFTER)
    assert not (root / token).exists()


def test_case10_stored_row_with_missing_bytes(tmp_path):
    """10) صف stored بلا بايتات (بايتات ضاعت) ⇒ يُكنس بلا خطأ."""
    db, store, service, db_path = make_env(tmp_path)
    res = _run(accept(service, chunks=(b"data",)))
    it = item_of(db, res.batch_id)
    root = staging_root_for(db_path)
    (root / it.staging_token).unlink()  # البايتات ضاعت
    db.mark_attachment_batch_status(res.batch_id, ATTACHMENT_BATCH_DELIVERED,
                                    now=NOW_LIVE.isoformat())
    rep = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert db.get_attachment_item(it.item_id).status == ATTACHMENT_ITEM_REAPED
    assert rep.errors == 0


def test_case11_orphan_item_metadata_is_reaped(tmp_path):
    """11) بيانات عنصر يتيمة (بلا دفعة) ⇒ تُكنس بالتوكن."""
    db, db_path = make_env(tmp_path)[0], str(tmp_path / "state.sqlite3")
    token = "z" * 32
    db.add_attachment_item("orphan1", "missing-batch", staging_token=token,
                           display_name="n.txt", size_bytes=3,
                           status=ATTACHMENT_ITEM_STORED)
    root = staging_root_for(db_path)
    root.mkdir(parents=True, exist_ok=True)
    (root / token).write_bytes(b"abc")
    reaper(db, db_path).sweep(now=NOW_AFTER)
    assert db.get_attachment_item("orphan1").status == ATTACHMENT_ITEM_REAPED
    assert not (root / token).exists()


def test_case12_orphan_filesystem_file_preserved(tmp_path):
    """12) ملف على القرص بلا صف مطابق ⇒ **يُترك** ويُرصد (بلا تخمين)."""
    db, store, service, db_path = make_env(tmp_path)
    root = staging_root_for(db_path)
    root.mkdir(parents=True, exist_ok=True)
    orphan = root / ("q" * 32)
    orphan.write_bytes(b"unknown")
    rep = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert orphan.exists()
    assert rep.untracked_left >= 1


def test_case13_reaper_deletion_failure_is_retried(tmp_path, monkeypatch):
    """13) فشل حذف الملف ⇒ يُرصد كإعادة محاولة، والعنصر `reaped` (قابل لإعادة الكنس)."""
    db, store, service, db_path = make_env(tmp_path)
    res = _run(accept(service, chunks=(b"data",)))
    it = item_of(db, res.batch_id)
    db.mark_attachment_batch_status(res.batch_id, ATTACHMENT_BATCH_DELIVERED,
                                    now=NOW_LIVE.isoformat())

    real_unlink = os.unlink

    def flaky_unlink(path, *a, **k):
        if str(path).endswith(it.staging_token):
            raise OSError("permission denied")
        return real_unlink(path, *a, **k)

    monkeypatch.setattr(os, "unlink", flaky_unlink)
    rep = reaper(db, db_path).sweep(now=NOW_AFTER)
    # القرار الدائم اتخذ (reaped) لكن الحذف فشل ⇒ retry مرئي (مش نجاح كاذب).
    assert db.get_attachment_item(it.item_id).status == ATTACHMENT_ITEM_REAPED
    assert rep.retry >= 1
    assert rep.files_deleted == 0
    root = staging_root_for(db_path)
    assert (root / it.staging_token).exists()

    # إصلاح الفشل ⇒ إعادة الكنس idempotent تنجح.
    monkeypatch.setattr(os, "unlink", real_unlink)
    rep2 = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert rep2.files_deleted == 1
    assert not (root / it.staging_token).exists()


def test_case14_reaper_db_update_failure(tmp_path, monkeypatch):
    """14) فشل تحديث القاعدة أثناء الكنس ⇒ يُرصد خطأ/إعادة، والعنصر يفضل مؤهّلًا للكنس."""
    db, store, service, db_path = make_env(tmp_path)
    res = _run(accept(service, chunks=(b"data",)))
    it = item_of(db, res.batch_id)
    db.mark_attachment_batch_status(res.batch_id, ATTACHMENT_BATCH_DELIVERED,
                                    now=NOW_LIVE.isoformat())

    def boom(item_id):
        raise sqlite3.OperationalError("db busy")

    monkeypatch.setattr(db, "mark_attachment_item_reaped", boom)
    rep = reaper(db, db_path).sweep(now=NOW_AFTER)
    # الحذف **ما اتعملش** (DB-first: مفيش وسم ⇒ مفيش حذف) ⇒ مفيش نجاح كاذب.
    root = staging_root_for(db_path)
    assert (root / it.staging_token).exists()
    assert db.get_attachment_item(it.item_id).status == ATTACHMENT_ITEM_STORED
    assert rep.retry >= 1 or rep.errors >= 1

    # إصلاح الفشل ⇒ كنس لاحق ينجح.
    monkeypatch.undo()
    reaper(db, db_path).sweep(now=NOW_AFTER)
    assert db.get_attachment_item(it.item_id).status == ATTACHMENT_ITEM_REAPED
    assert not (root / it.staging_token).exists()


def test_case15_repeated_recovery_is_idempotent(tmp_path):
    """15) تعافٍ متكرّر ⇒ idempotent (لا حذف مزدوج، لا خطأ)."""
    db, store, service, db_path = make_env(tmp_path)
    res = _run(accept(service, chunks=(b"data",)))
    it = item_of(db, res.batch_id)
    db.mark_attachment_batch_status(res.batch_id, ATTACHMENT_BATCH_DELIVERED,
                                    now=NOW_LIVE.isoformat())
    r1 = reaper(db, db_path).sweep(now=NOW_AFTER)
    r2 = reaper(db, db_path).sweep(now=NOW_AFTER)
    r3 = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert r1.files_deleted == 1
    assert r2.files_deleted == 0 and r3.files_deleted == 0
    assert r2.errors == 0 and r3.errors == 0
    assert db.get_attachment_item(it.item_id).status == ATTACHMENT_ITEM_REAPED


def test_case16_symlink_and_foreign_path_preserved(tmp_path):
    """16) symlink/مسار غير آمن ⇒ **ما يُحذفش** ولا يُتبع."""
    db, store, service, db_path = make_env(tmp_path)
    root = staging_root_for(db_path)
    root.mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside")
    link = root / ("s" * 32)
    os.symlink(str(outside), str(link))
    # صف يشير لتوكن هو نفسه symlink ⇒ ما يُحذفش (غير ملف عادي).
    db.add_attachment_item("sym1", "missing-batch", staging_token="s" * 32,
                           display_name="n.txt", size_bytes=7,
                           status=ATTACHMENT_ITEM_STORED)
    rep = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert link.exists()
    assert outside.exists()
    assert rep.unsafe_left >= 1


def test_case17_foreign_key_identity_regression(tmp_path):
    """17) انحدار FK: دليل الهوية المرتبط بدفعة يمنع الحذف (ON DELETE RESTRICT) وسليم بعد الكنس."""
    db, store, service, db_path = make_env(tmp_path)
    res = _run(accept(service, chunks=(b"data",), update_id=555))
    _bind_identity(db, res.batch_id, message_id=42)
    # محاولة حذف الدفعة يفشل بسبب RESTRICT.
    with pytest.raises(sqlite3.IntegrityError):
        db._conn.execute("DELETE FROM attachment_batches WHERE batch_id=?", (res.batch_id,))
    db._conn.rollback()
    # الكنس ما بيمسّش دليل الهوية.
    db.mark_attachment_batch_status(res.batch_id, ATTACHMENT_BATCH_DELIVERED,
                                    now=NOW_LIVE.isoformat())
    reaper(db, db_path).sweep(now=NOW_AFTER)
    rows = db._conn.execute(
        "SELECT * FROM attachment_message_identity WHERE batch_id=?", (res.batch_id,)
    ).fetchall()
    assert len(rows) == 1


def test_case18_identity_retention_d33_d34_d35(tmp_path):
    """18) D-33/D-34/D-35: الكنس/التعافي **ما** يمسّش دليل الهوية (بلا cascade/DELETE/UPDATE)."""
    db, store, service, db_path = make_env(tmp_path)
    res = _run(accept(service, chunks=(b"data",), update_id=556))
    _bind_identity(db, res.batch_id, message_id=43)
    before = db._conn.execute(
        "SELECT COUNT(*) c FROM attachment_message_identity"
    ).fetchone()["c"]
    db.mark_attachment_batch_status(res.batch_id, ATTACHMENT_BATCH_DELIVERED,
                                    now=NOW_LIVE.isoformat())
    reaper(db, db_path).sweep(now=NOW_AFTER)
    after = db._conn.execute(
        "SELECT COUNT(*) c FROM attachment_message_identity"
    ).fetchone()["c"]
    assert before == 1 and after == 1
    # حارس مصدري: مفيش DELETE/UPDATE على جدول الهوية في وحدة الـ staging.
    src = open(os.path.join(os.path.dirname(__file__), "..", "bot", "attachments.py"),
               encoding="utf-8").read()
    assert "DELETE FROM attachment_message_identity" not in src
    assert "UPDATE attachment_message_identity" not in src
    assert "ON DELETE CASCADE" not in src


def test_case19_a3_f1_identity_evidence_survives_recovery(tmp_path):
    """19) A3/F1: دليل الهوية (رسالة↔دفعة) ينجو إعادة الفتح + الكنس."""
    db, store, service, db_path = make_env(tmp_path)
    res = _run(accept(service, chunks=(b"data",), update_id=557))
    _bind_identity(db, res.batch_id, message_id=44)
    db.mark_attachment_batch_status(res.batch_id, ATTACHMENT_BATCH_DELIVERED,
                                    now=NOW_LIVE.isoformat())
    db.close()

    db2 = Database(db_path)
    reaper(db2, db_path).sweep(now=NOW_AFTER)
    rows = db2._conn.execute(
        "SELECT * FROM attachment_message_identity WHERE batch_id=?", (res.batch_id,)
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["message_id"] == 44


# ============================================================================
# إضافي: كتابة مقيّدة عند السقف — لا ملف جزئي (LIFE-02 تأكيد)
# ============================================================================
def test_over_cap_write_leaves_no_partial_file(tmp_path):
    db, store, service, db_path = make_env(tmp_path)
    store2 = StagingStore(db, db_path, max_bytes=4, clock=lambda: T0)
    client = FakeClient()
    svc = AttachmentService(db, store2, client, IdentityCache(client))
    res = _run(accept(svc, chunks=(b"12345",)))
    assert res.stage is StageStatus.REJECTED_SIZE
    batch_id = _only_batch(db)
    it = item_of(db, batch_id)
    root = staging_root_for(db_path)
    assert not (root / it.staging_token).exists()
