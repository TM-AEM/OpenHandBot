"""OHB2-P0-A4 — كنس/انتهاء الـ staging + التعافي + المراقبة (محلي فقط).

يغطّي نطاق R4 Stage A4 (D-09-R2):
- فرض مهلة الدفعة من `T0` **الأصلي الثابت** (15 دقيقة)، بلا تمديد/تصفير.
- ترتيب آمن: **DB-أولًا** (وسم الدفعة/العنصر) قبل أي حذف بايتات.
- فشل حذف بعد القرار الدائم ⇒ **مرئي وقابل لإعادة المحاولة** (مفيش نجاح كاذب).
- idempotent + جزئي متعدّد العناصر + حالات التعافي (دلاء/عناصر/ملفات مفقودة، يتيمة، مقاطَعة).
- حصر صارم (symlink/مسار خارج الجذر/مقطع غير آمن) ⇒ **يُترك ويُرصد** (بلا متابعة/تخمين).
- حالة غامضة/غير معروفة ⇒ **تُترك** (بلا تخمين) وتُرصد.
- **D-35:** دليل الهوية (`attachment_message_identity`) **ينجو** كل مسارات A4، وبلا cascade.
- **مفيش worker/مجدول/عملية/مالك قاعدة جديد**: الكنس يُستدعى من hook الإقلاع الموجود.

الساعات **محقونة** (`now` صريح) ⇒ مفيش sleeps/هشاشة زمنية. قاعدة+مجلد مؤقتان (بلا شبكة).
"""
from __future__ import annotations

import os
import pathlib
from datetime import datetime, timezone

import pytest

from bot import attachments
from bot.attachments import (
    AttachmentReaper,
    staging_root_for,
)
from bot.db import (
    ATTACHMENT_BATCH_DELIVERED,
    ATTACHMENT_BATCH_EXPIRED,
    ATTACHMENT_BATCH_INTENT_RECORDED,
    ATTACHMENT_BATCH_PENDING,
    ATTACHMENT_BATCH_REJECTED,
    ATTACHMENT_ITEM_REAPED,
    ATTACHMENT_ITEM_STORED,
    Database,
)

OWNER_A = 1
OWNER_B = 2
CID_A = "11111111222233334444555566667777"
CID_B = "99999999888877776666555544443333"
T0 = "2026-11-14T10:00:00+00:00"
NOW_LIVE = datetime(2026, 11, 14, 10, 5, tzinfo=timezone.utc)      # داخل المهلة
NOW_EXACT = datetime(2026, 11, 14, 10, 15, tzinfo=timezone.utc)    # عند الحدّ بالظبط
NOW_AFTER = datetime(2026, 11, 14, 10, 16, tzinfo=timezone.utc)    # بعد الحدّ


def make_db(tmp_path) -> tuple[Database, str]:
    db_path = str(tmp_path / "state.sqlite3")
    return Database(db_path), db_path


def add_batch(db, batch_id, *, telegram_id=OWNER_A, conversation_id=CID_A, t0=T0,
              status=ATTACHMENT_BATCH_PENDING):
    db.create_attachment_batch(batch_id, telegram_id, conversation_id, t0, status=status)
    return batch_id


def add_item(db, item_id, batch_id, *, token, status=ATTACHMENT_ITEM_STORED):
    db.add_attachment_item(
        item_id, batch_id, staging_token=token, display_name="n.txt",
        size_bytes=3, status=status,
    )
    return item_id


def write_staged(db, db_path, token, data=b"abc"):
    root = staging_root_for(db_path)
    root.mkdir(parents=True, exist_ok=True)
    (root / token).write_bytes(data)
    return root / token


def reaper(db, db_path) -> AttachmentReaper:
    return AttachmentReaper(db, db_path)


# ============================================================================
# 1) دلالات الانتهاء من T0 الثابت
# ============================================================================
def test_pending_batch_expires_at_exact_boundary_and_is_reaped(tmp_path):
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1")
    add_item(db, "i1", "b1", token="a" * 32)
    f = write_staged(db, db_path, "a" * 32)
    rep = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_EXPIRED
    assert not f.exists()
    assert rep.files_deleted == 1


def test_pending_batch_at_exact_deadline_is_expired(tmp_path):
    # الحدّ بالظبط = منتهية (now >= deadline) — حتمي.
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1")
    add_item(db, "i1", "b1", token="b" * 32)
    write_staged(db, db_path, "b" * 32)
    reaper(db, db_path).sweep(now=NOW_EXACT)
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_EXPIRED


def test_pending_batch_just_before_deadline_is_untouched(tmp_path):
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1")
    add_item(db, "i1", "b1", token="c" * 32)
    f = write_staged(db, db_path, "c" * 32)
    rep = reaper(db, db_path).sweep(now=NOW_LIVE)
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_PENDING
    assert f.exists()
    assert rep.files_deleted == 0


def test_retry_does_not_extend_ttl(tmp_path):
    # إعادة الكنس لا تمدّد المهلة: نفس T0، نفس الحدّ.
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1")
    add_item(db, "i1", "b1", token="d" * 32)
    write_staged(db, db_path, "d" * 32)
    reaper(db, db_path).sweep(now=NOW_LIVE)  # لسه حيّة
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_PENDING
    reaper(db, db_path).sweep(now=NOW_AFTER)  # بعد الحدّ ⇒ منتهية
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_EXPIRED


def test_malformed_t0_is_treated_as_expired_and_left_for_investigation(tmp_path):
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1", t0="not-a-timestamp")
    add_item(db, "i1", "b1", token="e" * 32)
    f = write_staged(db, db_path, "e" * 32)
    reaper(db, db_path).sweep(now=NOW_LIVE)
    # t0 غير صالح ⇒ pending "مش حيّة" ⇒ تُوسم expired ثم تُترك للتحقيق (بلا حذف).
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_EXPIRED
    assert f.exists()  # لم تُحذف (t0 غير صالح ⇒ قرار غير مؤكَّد)


def test_missing_t0_is_treated_as_expired(tmp_path):
    db, db_path = make_db(tmp_path)
    db.create_attachment_batch("b1", OWNER_A, CID_A, "")  # t0 فاضي
    reaper(db, db_path).sweep(now=NOW_LIVE)
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_EXPIRED


# ============================================================================
# 2) ترتيب DB-أولًا + فشل الحذف مرئي/قابل لإعادة المحاولة
# ============================================================================
def test_db_transition_precedes_filesystem_deletion(tmp_path, monkeypatch):
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1", status=ATTACHMENT_BATCH_DELIVERED)
    add_item(db, "i1", "b1", token="f" * 32)
    f = write_staged(db, db_path, "f" * 32)

    order = []
    real_unlink = os.unlink

    def _spy_unlink(path, *a, **k):
        order.append(("unlink", db.get_attachment_item("i1").status))
        return real_unlink(path, *a, **k)

    monkeypatch.setattr(os, "unlink", _spy_unlink)
    reaper(db, db_path).sweep(now=NOW_AFTER)
    # عند لحظة الحذف، العنصر كان **موسومًا** `reaped` بالفعل ⇒ DB-أولًا مثبَت.
    assert order and order[0][1] == ATTACHMENT_ITEM_REAPED
    assert not f.exists()


def test_filesystem_failure_after_transition_is_retryable_and_visible(tmp_path, monkeypatch):
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1", status=ATTACHMENT_BATCH_DELIVERED)
    add_item(db, "i1", "b1", token="g" * 32)
    f = write_staged(db, db_path, "g" * 32)

    def _boom(path, *a, **k):
        raise OSError("simulated unlink failure")

    monkeypatch.setattr(os, "unlink", _boom)
    rep = reaper(db, db_path).sweep(now=NOW_AFTER)
    # القرار الدائم اتخذ، والحذف فشل ⇒ العنصر reaped + الملف لسه موجود + الحصيلة retry.
    assert db.get_attachment_item("i1").status == ATTACHMENT_ITEM_REAPED
    assert f.exists()
    assert rep.retry >= 1 and rep.cleaned == 0

    # إعادة المحاولة (بعد إصلاح الحذف) تنجح ⇒ idempotent، بلا نجاح كاذب في المرة الأولى.
    monkeypatch.undo()
    rep2 = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert not f.exists()
    assert rep2.files_deleted == 1


def test_repeated_cleanup_is_idempotent(tmp_path):
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1", status=ATTACHMENT_BATCH_REJECTED)
    add_item(db, "i1", "b1", token="h" * 32)
    write_staged(db, db_path, "h" * 32)
    r1 = reaper(db, db_path).sweep(now=NOW_AFTER)
    r2 = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert r1.files_deleted == 1
    assert r2.files_deleted == 0  # مفيش شيء تاني يُحذف
    assert db.get_attachment_item("i1").status == ATTACHMENT_ITEM_REAPED


# ============================================================================
# 3) جزئي متعدّد العناصر + إعادة محاولة
# ============================================================================
def test_partial_multi_item_cleanup_then_retry(tmp_path, monkeypatch):
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1", status=ATTACHMENT_BATCH_DELIVERED)
    for i in range(3):
        add_item(db, f"i{i}", "b1", token=str(i) * 32)
        write_staged(db, db_path, str(i) * 32)

    real_unlink = os.unlink
    calls = {"n": 0}

    def _flaky(path, *a, **k):
        calls["n"] += 1
        if calls["n"] == 2:  # العنصر التاني يفشل مرة واحدة
            raise OSError("transient")
        return real_unlink(path, *a, **k)

    monkeypatch.setattr(os, "unlink", _flaky)
    rep = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert rep.partial >= 1  # اتحذف بعض + باقي محتاج إعادة محاولة
    root = staging_root_for(db_path)
    remaining = [p for p in root.iterdir()]
    assert len(remaining) == 1  # عنصر واحد باقي

    monkeypatch.undo()
    rep2 = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert rep2.files_deleted == 1
    assert not [p for p in staging_root_for(db_path).iterdir()]


# ============================================================================
# 4) حالات التعافي (دلاء/عناصر/ملفات مفقودة، يتيمة، مقاطَعة)
# ============================================================================
def test_batch_dir_missing_while_records_remain(tmp_path):
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1", status=ATTACHMENT_BATCH_EXPIRED)
    add_item(db, "i1", "b1", token="j" * 32)  # ملف غير مكتوب إطلاقًا (مجلد مفقود)
    rep = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert db.get_attachment_item("i1").status == ATTACHMENT_ITEM_REAPED
    assert rep.errors == 0  # غياب المجلد ليس خطأ


def test_batch_present_while_item_rows_missing(tmp_path):
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1", status=ATTACHMENT_BATCH_DELIVERED)  # دبوس بلا عناصر
    rep = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert rep.cleaned == 0 and rep.errors == 0  # لا شيء لکنسه (تُترك البيانات للتحقيق)


def test_db_item_present_while_file_missing(tmp_path):
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1", status=ATTACHMENT_BATCH_DELIVERED)
    add_item(db, "i1", "b1", token="k" * 32)  # ملف مفقود
    rep = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert db.get_attachment_item("i1").status == ATTACHMENT_ITEM_REAPED
    assert rep.cleaned == 1  # مفقود ⇒ نجاح (idempotent)


def test_unreferenced_file_is_left_and_reported(tmp_path):
    db, db_path = make_db(tmp_path)
    write_staged(db, db_path, "z" * 32)  # ملف بلا أي عنصر مطابق
    rep = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert (staging_root_for(db_path) / ("z" * 32)).exists()  # لم يُحذف (بلا تخمين)
    assert rep.untracked_left >= 1


def test_interrupted_creation_pending_item_no_file(tmp_path):
    # انقطاع بعد كتابة الصف `pending` وقبل كتابة البايتات ⇒ عند الانتهاء يُكنس بأمان.
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1")
    add_item(db, "i1", "b1", token="l" * 32, status=ATTACHMENT_BATCH_PENDING)
    reaper(db, db_path).sweep(now=NOW_AFTER)
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_EXPIRED
    assert db.get_attachment_item("i1").status == ATTACHMENT_ITEM_REAPED


def test_expired_partial_batch_is_reaped(tmp_path):
    # دفعة منتهية فيها عنصر stored + عنصر pending (جزئي) ⇒ الاثنان يُكنسان.
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1")
    add_item(db, "i1", "b1", token="m" * 32, status=ATTACHMENT_ITEM_STORED)
    add_item(db, "i2", "b1", token="n" * 32, status=ATTACHMENT_BATCH_PENDING)
    write_staged(db, db_path, "m" * 32)
    write_staged(db, db_path, "n" * 32)
    rep = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert rep.files_deleted == 2
    assert db.get_attachment_item("i1").status == ATTACHMENT_ITEM_REAPED
    assert db.get_attachment_item("i2").status == ATTACHMENT_ITEM_REAPED


def test_crash_after_transition_before_cleanup_recovered(tmp_path):
    # محاكاة انهيار بعد وسم العنصر `reaped` وقبل الحذف (ملف لسه موجود) ⇒ إعادة الكنس تكمل.
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1", status=ATTACHMENT_BATCH_DELIVERED)
    add_item(db, "i1", "b1", token="o" * 32, status=ATTACHMENT_ITEM_REAPED)
    f = write_staged(db, db_path, "o" * 32)
    rep = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert not f.exists()
    assert rep.files_deleted == 1


# ============================================================================
# 5) حالات غير معروفة / غامضة ⇒ تُترك وتُرصد
# ============================================================================
def test_unknown_batch_status_is_left_and_reported(tmp_path):
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1", status="future_status_xyz")
    add_item(db, "i1", "b1", token="p" * 32)
    f = write_staged(db, db_path, "p" * 32)
    rep = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert db.get_attachment_batch("b1").status == "future_status_xyz"  # لم تُلمس
    assert f.exists()  # لم تُحذف (حالة غير معروفة)
    assert rep.errors >= 1  # مُرصودة كحالة تحتاج تحقيق


def test_unresolved_intent_recorded_is_untouched(tmp_path):
    # `intent_recorded` = غير محسوم (D-32) ⇒ **يُترك** (بلا كنس)، حتى لو بايتات موجودة.
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1", status=ATTACHMENT_BATCH_INTENT_RECORDED)
    add_item(db, "i1", "b1", token="q" * 32)
    f = write_staged(db, db_path, "q" * 32)
    rep = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_INTENT_RECORDED
    assert f.exists()
    assert rep.skipped >= 1 and rep.files_deleted == 0


def test_unknown_item_status_is_left(tmp_path):
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1", status=ATTACHMENT_BATCH_DELIVERED)
    add_item(db, "i1", "b1", token="r" * 32, status="weird_item_status")
    f = write_staged(db, db_path, "r" * 32)
    rep = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert f.exists()  # حالة عنصر غير معروفة ⇒ يُترك
    assert db.get_attachment_item("i1").status == "weird_item_status"
    assert rep.retry >= 1


def test_orphan_item_without_batch_is_reaped(tmp_path):
    # عنصر بلا دفعة أب (دبوس مفقود) ⇒ يُكنس، ويُرصد.
    db, db_path = make_db(tmp_path)
    # ندرج عنصرًا بمعرّف دفعة غير موجود — نعطّل FK مؤقّتًا للاختبار فقط.
    db._conn.execute("PRAGMA foreign_keys=OFF")
    add_item(db, "i1", "ghost-batch", token="s" * 32)
    db._conn.execute("PRAGMA foreign_keys=ON")
    f = write_staged(db, db_path, "s" * 32)
    reaper(db, db_path).sweep(now=NOW_AFTER)
    assert not f.exists()
    assert db.get_attachment_item("i1").status == ATTACHMENT_ITEM_REAPED


# ============================================================================
# 5b) OHB2-P0-A4-LOW-FINDINGS-REMEDIATION (F-1): العنصر اليتيم `reaped` يُعاد حذفه
# ============================================================================
def _add_orphan_reaped_item(db, item_id, token):
    """عنصر بحالة `reaped` بمعرّف دفعة **غير موجود** (يتيم) — FK مؤقّتًا للاختبار فقط."""
    db._conn.execute("PRAGMA foreign_keys=OFF")
    add_item(db, item_id, "ghost-batch", token=token, status=ATTACHMENT_ITEM_REAPED)
    db._conn.execute("PRAGMA foreign_keys=ON")
    return item_id


def test_orphan_reaped_item_with_remaining_bytes_is_reaped(tmp_path):
    # F-1: عنصر يتيم **مكنوس سابقًا** (reaped) لكن بايتاته لسه موجودة (فشل حذف سابق)
    # ⇒ الكنسة الجديدة تعيد الحذف بأمان (كان يتخطّاه قبل الإصلاح).
    db, db_path = make_db(tmp_path)
    _add_orphan_reaped_item(db, "i1", "R" * 32)
    f = write_staged(db, db_path, "R" * 32)
    rep = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert not f.exists()  # البايتات المتبقية اتشالت
    assert rep.orphans_left == 0  # مفيش يتيم متبقٍّ
    # الحالة تفضل `reaped` (بلا حاجة لتغييرها — القرار الدائم متخذ بالفعل).
    assert db.get_attachment_item("i1").status == ATTACHMENT_ITEM_REAPED


def test_orphan_reaped_item_second_sweep_is_idempotent(tmp_path):
    # F-1: إعادة الكنس آمنة (ملف مفقود = لا عمل)، بلا خطأ.
    db, db_path = make_db(tmp_path)
    _add_orphan_reaped_item(db, "i1", "S" * 32)
    f = write_staged(db, db_path, "S" * 32)
    r1 = reaper(db, db_path).sweep(now=NOW_AFTER)
    r2 = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert not f.exists()  # اتحذف في الكنسة الأولى
    assert r1.orphans_left == 0 and r2.orphans_left == 0  # لا شيء متبقٍّ في المرّتين


def test_orphan_reaped_item_deletion_failure_is_retryable_and_observable(tmp_path, monkeypatch):
    # F-1: فشل الحذف على عنصر يتيم `reaped` يبقى **مرئيًّا** (orphans_left) وقابلًا لإعادة المحاولة.
    db, db_path = make_db(tmp_path)
    _add_orphan_reaped_item(db, "i1", "T" * 32)
    f = write_staged(db, db_path, "T" * 32)

    def _boom(path, *a, **k):
        raise OSError("simulated unlink failure")

    monkeypatch.setattr(os, "unlink", _boom)
    rep = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert f.exists()  # مفيش حذف فعلي
    assert rep.orphans_left == 1  # مرئي

    monkeypatch.undo()
    rep2 = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert not f.exists()  # إعادة المحاولة تنجح
    assert rep2.orphans_left == 0


def test_orphan_reaped_item_of_live_batch_is_not_deleted(tmp_path):
    # F-1 سلامة: عنصر `reaped` يخصّ دفعة **حيّة** (صف الدفعة موجود) ⇒ **لا يُحذف** (يُحمى بفحص
    # انتماء الدفعة). الكنس اليتيم لا يلمس إلا العناصر بلا صفّ دفعة.
    db, db_path = make_db(tmp_path)
    add_batch(db, "live", t0="2026-11-14T10:10:00+00:00")  # حيّة عند NOW_AFTER (حدّها 10:25)
    add_item(db, "i1", "live", token="U" * 32, status=ATTACHMENT_ITEM_REAPED)
    f = write_staged(db, db_path, "U" * 32)
    rep = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert f.exists()  # لم يُحذف
    assert rep.orphans_left == 0
    assert db.get_attachment_batch("live").status == ATTACHMENT_BATCH_PENDING


def test_orphan_reaped_item_of_terminal_batch_handled_by_batch_path(tmp_path):
    # F-1 سلامة: عنصر `reaped` يخصّ دفعة **نهائية** ⇒ يتولّاه مسار الدفعة (لا يتضاعف الحذف)،
    # ولا يُحتسب كـ يتيم.
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1", status=ATTACHMENT_BATCH_DELIVERED)
    add_item(db, "i1", "b1", token="V" * 32, status=ATTACHMENT_ITEM_REAPED)
    f = write_staged(db, db_path, "V" * 32)
    rep = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert not f.exists()
    assert rep.files_deleted == 1  # حُذف مرة واحدة عبر مسار الدفعة
    assert rep.orphans_left == 0


def test_orphan_reaped_item_cross_owner_and_conversation_isolation(tmp_path):
    # F-1 عزل: عنصر يتيم `reaped` لمستخدم/محادثة أخرى لا يتأثر بالكنس العام؛ والعزل سليم.
    db, db_path = make_db(tmp_path)
    # عنصر يتيم (بلا دفعة) يخصّ (مفهوميًّا) مالكًا آخر — الكنس العام يمرّ عليه لأنه بلا دفعة،
    # لكن عنصر مالك حيّ لسه محمي.
    add_batch(db, "otherlive", telegram_id=OWNER_B, conversation_id=CID_B,
              t0="2026-11-14T10:10:00+00:00")
    add_item(db, "ib", "otherlive", token="W" * 32, status=ATTACHMENT_ITEM_REAPED)
    fb = write_staged(db, db_path, "W" * 32)
    rep = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert fb.exists()  # دفعة مالك آخر حيّة ⇒ محمية
    assert rep.orphans_left == 0
    assert db.get_attachment_batch("otherlive").status == ATTACHMENT_BATCH_PENDING


def test_orphan_reaped_item_symlink_is_protected(tmp_path):
    # F-1 حصر: توكن عنصر يتيم `reaped` هو symlink لملف خارج الجذر ⇒ **لا حذف** للملف الهدف.
    db, db_path = make_db(tmp_path)
    _add_orphan_reaped_item(db, "i1", "X" * 32)
    root = staging_root_for(db_path)
    root.mkdir(parents=True, exist_ok=True)
    outside = pathlib.Path(db_path).parent / "outside-target"
    outside.write_bytes(b"secret")
    os.symlink(str(outside), str(root / ("X" * 32)))
    rep = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert outside.exists()  # الهدف لم يُلمس
    assert (root / ("X" * 32)).is_symlink()  # الرابط نفسه لم يُحذف
    assert rep.files_deleted == 0


def test_orphan_reaped_item_unsafe_token_is_protected(tmp_path):
    # F-1 حصر: توكن غير آمن (اجتياز مسار) على عنصر يتيم `reaped` ⇒ لا حذف خارج الجذر.
    db, db_path = make_db(tmp_path)
    _add_orphan_reaped_item(db, "i1", "../escape")
    root = staging_root_for(db_path)
    root.mkdir(parents=True, exist_ok=True)
    escape = pathlib.Path(db_path).parent / "escape"
    escape.write_bytes(b"x")
    rep = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert escape.exists()  # ملف خارج الجذر لم يُلمس
    assert rep.files_deleted == 0


def test_orphan_reaped_item_does_not_delete_identity_evidence(tmp_path):
    # F-1/D-35: كنس عنصر يتيم `reaped` **لا** يمسّ دليل الهوية (`attachment_message_identity`).
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1")
    _bind_identity(db, "b1", chat_id=777, message_id=8)
    _add_orphan_reaped_item(db, "i1", "Y" * 32)
    f = write_staged(db, db_path, "Y" * 32)
    reaper(db, db_path).sweep(now=NOW_AFTER)
    assert not f.exists()  # العنصر اليتيم اتكنس
    assert db.message_identity_batch_id(OWNER_A, 777, 8) == "b1"  # دليل الهوية باقٍ
    assert db.count_message_identities() == 1


# ============================================================================
# 6) العزل بين المالكين/المحادثات (الكنس لا يلمس الحيّ)
# ============================================================================
def test_live_pending_batch_of_other_owner_untouched(tmp_path):
    db, db_path = make_db(tmp_path)
    add_batch(db, "live", telegram_id=OWNER_B, conversation_id=CID_B,
              t0="2026-11-14T10:10:00+00:00")  # حيّة عند NOW_AFTER (حدّها 10:25)
    add_item(db, "il", "live", token="t" * 32)
    fl = write_staged(db, db_path, "t" * 32)
    add_batch(db, "dead", telegram_id=OWNER_A, conversation_id=CID_A,
              status=ATTACHMENT_BATCH_DELIVERED)
    add_item(db, "id", "dead", token="u" * 32)
    write_staged(db, db_path, "u" * 32)
    reaper(db, db_path).sweep(now=NOW_AFTER)
    assert db.get_attachment_batch("live").status == ATTACHMENT_BATCH_PENDING
    assert fl.exists()  # دفعة حيّة (مالك آخر) لم تُلمس
    assert db.get_attachment_item("il").status == ATTACHMENT_ITEM_STORED


# ============================================================================
# 7) حصر صارم: symlink / مسار غير آمن
# ============================================================================
def test_symlink_entry_is_not_followed_or_deleted(tmp_path):
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1", status=ATTACHMENT_BATCH_DELIVERED)
    add_item(db, "i1", "b1", token="v" * 32)
    root = staging_root_for(db_path)
    root.mkdir(parents=True, exist_ok=True)
    # هدف خارج الجذر + symlink باسم التوكن يشير إليه.
    outside = tmp_path / "outside_target.bin"
    outside.write_bytes(b"secret")
    os.symlink(str(outside), str(root / ("v" * 32)))
    rep = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert outside.exists()          # الهدف لم يُحذف (ما تبعناش الرابط)
    assert outside.read_bytes() == b"secret"
    assert (root / ("v" * 32)).is_symlink()  # الرابط نفسه تُرك
    assert rep.unsafe_left >= 1


def test_symlink_inside_root_is_left_not_removed(tmp_path):
    # symlink هدفه **داخل** الجذر: `_is_within` بيمرّ، فحاجز lstat (رفض غير الملف العادي)
    # هو الحماية الوحيدة ⇒ لازم يُترك بلا حذف (ما نمسحش الرابط ولا نتبعه).
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1", status=ATTACHMENT_BATCH_DELIVERED)
    add_item(db, "i1", "b1", token="Z" * 32)
    root = staging_root_for(db_path)
    root.mkdir(parents=True, exist_ok=True)
    target = root / ("Y" * 32)
    target.write_bytes(b"target-bytes")
    os.symlink(str(target), str(root / ("Z" * 32)))
    reaper(db, db_path).sweep(now=NOW_AFTER)
    assert (root / ("Z" * 32)).is_symlink()   # الرابط تُرك
    assert target.exists()                    # الهدف لم يُلمس


def test_path_traversal_token_is_rejected(tmp_path):
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1", status=ATTACHMENT_BATCH_DELIVERED)
    add_item(db, "i1", "b1", token="../evil")
    outside = tmp_path / "evil"
    outside.write_bytes(b"do-not-delete")
    reaper(db, db_path).sweep(now=NOW_AFTER)
    assert outside.exists()  # مسار خارج الجذر لم يُحذف
    assert outside.read_bytes() == b"do-not-delete"


def test_absolute_token_is_rejected(tmp_path):
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1", status=ATTACHMENT_BATCH_DELIVERED)
    victim = tmp_path / "victim"
    victim.write_bytes(b"x")
    add_item(db, "i1", "b1", token=str(victim))
    reaper(db, db_path).sweep(now=NOW_AFTER)
    assert victim.exists()


# ============================================================================
# 8) D-35: دليل الهوية ينجو كل مسارات A4 (بلا cascade)
# ============================================================================
def _bind_identity(db, batch_id, *, chat_id=500, message_id=7):
    res = db.record_attachment_intent(
        batch_id, telegram_id=OWNER_A, conversation_id=CID_A, intent_text="نصّ",
        now=T0, update_id=None, chat_id=chat_id, message_id=message_id,
    )
    assert res == batch_id


def test_identity_evidence_survives_reaping(tmp_path):
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1")
    add_item(db, "i1", "b1", token="w" * 32)
    write_staged(db, db_path, "w" * 32)
    _bind_identity(db, "b1")
    assert db.message_identity_batch_id(OWNER_A, 500, 7) == "b1"
    # نحوّل الدفعة نهائية ثم نكنس.
    db.mark_attachment_batch_status("b1", ATTACHMENT_BATCH_DELIVERED, now=T0)
    reaper(db, db_path).sweep(now=NOW_AFTER)
    # دليل الهوية لسه موجود (لم يُحذف مع الكنس/الحالة).
    assert db.message_identity_batch_id(OWNER_A, 500, 7) == "b1"
    assert db.count_message_identities() == 1


def test_identity_evidence_survives_expiry_transition(tmp_path):
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1")
    add_item(db, "i1", "b1", token="x" * 32)
    write_staged(db, db_path, "x" * 32)
    _bind_identity(db, "b1", chat_id=501, message_id=8)  # ⇒ intent_recorded
    # محاكاة قرار الانتهاء على الدفعة ثم كنسة: دليل الهوية ينجو.
    db.mark_attachment_batch_status("b1", ATTACHMENT_BATCH_EXPIRED, now=T0)
    reaper(db, db_path).sweep(now=NOW_AFTER)
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_EXPIRED
    assert db.message_identity_batch_id(OWNER_A, 501, 8) == "b1"
    assert db.count_message_identities() == 1


def test_no_cascade_delete_of_identity_and_restrict_preserved(tmp_path):
    import sqlite3

    db, db_path = make_db(tmp_path)
    add_batch(db, "b1")
    _bind_identity(db, "b1", chat_id=502, message_id=9)
    # FK RESTRICT محفوظ: حذف دفعة لها دليل هوية يفشل.
    with pytest.raises(sqlite3.IntegrityError):
        db._conn.execute("DELETE FROM attachment_batches WHERE batch_id='b1'")
    db._conn.rollback()
    assert db.message_identity_batch_id(OWNER_A, 502, 9) == "b1"


def test_no_identity_delete_in_cleanup_source():
    # فحص مصدري: A4 ما بيعملش أي حذف/تعديل لدليل الهوية (لا cascade ولا DELETE/UPDATE).
    src = pathlib.Path(attachments.__file__).read_text(encoding="utf-8")
    assert "DELETE FROM attachment_message_identity" not in src
    assert "UPDATE attachment_message_identity" not in src
    assert "ON DELETE CASCADE" not in src


# ============================================================================
# 9) معمارية: مفيش worker/مجدول/عملية/مالك قاعدة جديد
# ============================================================================
def test_reaper_introduces_no_worker_or_task():
    # الكنسة متزامنة (بلا start/_run/asyncio) ⇒ مفيش worker/مجدول جديد.
    assert not hasattr(AttachmentReaper, "start")
    assert not hasattr(AttachmentReaper, "stop")
    src = pathlib.Path(attachments.__file__).read_text(encoding="utf-8")
    assert "asyncio" not in src
    assert "create_task" not in src


def test_sweep_is_invoked_from_existing_startup_hook_only():
    from bot import app as app_mod

    app_src = pathlib.Path(app_mod.__file__).read_text(encoding="utf-8")
    assert "AttachmentReaper(" in app_src
    # داخل _post_init (hook الإقلاع الموجود)، مش worker جديد.
    idx_post_init = app_src.index("async def _post_init")
    idx_sweep = app_src.index("AttachmentReaper(")
    assert idx_post_init < idx_sweep  # الاستدعاء جوه الـ hook


def test_reaper_does_not_create_second_sqlite_connection(tmp_path):
    # الكنسة بتستخدم نفس اتصال `Database` (مفيش مالك قاعدة تاني).
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1", status=ATTACHMENT_BATCH_DELIVERED)
    add_item(db, "i1", "b1", token="y" * 32)
    write_staged(db, db_path, "y" * 32)
    before = db._conn
    reaper(db, db_path).sweep(now=NOW_AFTER)
    assert db._conn is before


# ============================================================================
# 10) A3/F1: انحدارات التوجيه/الفشل المغلق تفضل سليمة (تأكيد سريع)
# ============================================================================
def test_terminal_unproven_still_fails_closed_after_a4(tmp_path):
    # الكنس لا يغيّر دلالة التصنيف: دفعة نهائية + بلا هوية ⇒ TERMINAL_UNPROVEN.
    from bot.db import AttachmentRoutingState

    db, db_path = make_db(tmp_path)
    add_batch(db, "b1", status=ATTACHMENT_BATCH_EXPIRED)
    r = db.classify_attachment_routing(OWNER_A, now_iso=NOW_AFTER.isoformat())
    assert r.state is AttachmentRoutingState.TERMINAL_UNPROVEN


# ============================================================================
# 11) تكامل hook الإقلاع الفعلي: _post_init يستدعي الكنس
# ============================================================================
def test_startup_post_init_runs_sweep_and_cleans_expired(tmp_path, monkeypatch):
    """يثبت أن الكنس مُوصَّل فعليًّا بـ `_post_init` (hook الإقلاع الموجود) — بلا worker جديد."""
    import asyncio

    from telegram.ext import Application

    from bot import app as app_mod
    from bot.config import Config

    db_path = str(tmp_path / "t.sqlite3")
    config = Config(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({OWNER_A}),
        owner_id=OWNER_A,
        db_path=db_path,
    )
    app = app_mod.build_application(config)

    # جهّز دفعة نهائية + بايت staging (بمسار الإنتاج نفسه) قبل الإقلاع.
    db = Database(db_path)
    db.create_attachment_batch("b1", OWNER_A, CID_A, T0, status=ATTACHMENT_BATCH_DELIVERED)
    db.add_attachment_item("i1", "b1", staging_token="A" * 32, status=ATTACHMENT_ITEM_STORED)
    f = write_staged(db, db_path, "A" * 32)
    db.close()

    # نتخطّى الشبكة/الـ workers: نعطّل كل ما يعتمد على شبكة، ونشغّل _post_init الحقيقي.
    async def _noop(*a, **k):
        return None

    monkeypatch.setattr(app_mod.handlers, "outbox_recover", _noop)
    monkeypatch.setattr(app_mod.handlers, "creation_recover", _noop)
    monkeypatch.setattr(app_mod, "completion_recover", _noop)
    monkeypatch.setattr(app_mod.deletion, "reconcile_pending_deletions", _noop)
    monkeypatch.setattr(app_mod, "_register_commands", _noop)
    # نمنع بدء الـ workers (نثبت إن الكنس مش worker جديد): نعطّل create_task عبر fake.
    started = []
    monkeypatch.setattr(Application, "create_task", lambda self, *a, **k: started.append(a))

    app.bot_data["db_checked"] = True
    db2 = app.bot_data["db"]
    monkeypatch.setattr(db2, "is_healthy", lambda: True)

    asyncio.run(app.post_init(app))

    # الكنس اشتغل من الـ hook: البايت اتشال والعنصر اتوسم reaped.
    assert not f.exists()
    assert db2.get_attachment_item("i1").status == ATTACHMENT_ITEM_REAPED
    # مفيش worker جديد بدأ من الكنس (الكنس متزامن جوه الـ hook).
    assert started == []
