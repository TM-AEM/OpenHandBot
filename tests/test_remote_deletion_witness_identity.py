"""OHB2-PR6: اختبارات هُوية الشاهد المتينة + compare-and-swap (إصلاح TS-1 + سباق lost-update).

بتغطّي:
- الترحيل الآمن من مخططات قديمة (بدون الأعمدة الجديدة) + idempotency + الاستمرار بعد الانقطاع.
- استقلال التصنيف عن الوقت تمامًا (طوابع متطابقة/ساعة رايحة ورا/دقّة خشنة/تطبيع/إعادة تشغيل).
- سباق lost-update: محاولة قديمة ما تطمسش حالة أحدث مؤكّدة (‏CAS على ملكية المحاولة).
- دورة الحياة الكاملة + منع الإحياء + عدم طمس الحالة.

كلها بقواعد SQLite حقيقية (وبعضها باتصالين/threads) — مفيش اعتماد على mocks للبريديكيت فقط.
"""
from __future__ import annotations

import asyncio
import os
import sqlite3
import threading

from bot import deletion, outbox
from bot.db import Database
from bot.errors import ApiError

CID = "c1"
LEGACY_TS = "2026-01-01T00:00:00Z"


# ------------------------------------------------------------------ helpers
def _path(tmp_path, name="w.sqlite3"):
    return os.path.join(str(tmp_path), name)


class FakeClient:
    """عميل وهمي متحكَّم فيه (نفس عقد `tests/test_remote_deletion.py`)."""

    def __init__(self, delete_behaviour="ok", exists=False, exists_error=False, exists_seq=None):
        self.delete_behaviour = delete_behaviour
        self.exists = exists
        self.exists_error = exists_error
        self.exists_seq = list(exists_seq) if exists_seq is not None else None
        self.delete_calls = 0
        self.exists_calls = 0

    async def delete_conversation(self, conversation_id):
        self.delete_calls += 1
        b = self.delete_behaviour
        if b == "ok":
            return True
        if b == "404":
            raise ApiError("الشات مش موجود.", 404)
        if b == "unknown":
            raise ApiError("تعذّر الاتصال بـ OpenHands (ReadTimeout).")
        if isinstance(b, tuple) and b[0] == "status":
            raise ApiError("خطأ من OpenHands.", b[1])
        raise AssertionError(f"behaviour غير معروف: {b!r}")

    async def conversation_exists(self, conversation_id):
        self.exists_calls += 1
        if self.exists_seq is not None:
            idx = min(self.exists_calls - 1, len(self.exists_seq) - 1)
            val = self.exists_seq[idx]
            if val == "error":
                raise ApiError("تعذّر الاتصال بـ OpenHands.", None)
            return val
        if self.exists_error:
            raise ApiError("تعذّر الاتصال بـ OpenHands.", None)
        return self.exists


def _run(client, db, cid=CID):
    return asyncio.run(deletion.delete_conversation_remote(client, db, cid))


def _row(db, cid=CID):
    r = db._conn.execute(
        "SELECT conversation_id, deleted_at, remote_state, remote_updated_at, "
        "witness_origin, witness_attempt_id, witness_preexisting "
        "FROM deleted_conversations WHERE conversation_id=?",
        (cid,),
    ).fetchone()
    return None if r is None else dict(r)


def _seed_legacy(db, cid=CID, ts=LEGACY_TS):
    """شاهد قديم: حذف محلي سابق، remote_state=NULL (نفس إنتاج F2/R1)."""
    db.add_watched(cid, "شات", chat_id=1)
    db.delete_conversation(cid, ts)
    assert db.is_deleted(cid) is True


def _make_old_schema(path, columns=("conversation_id", "deleted_at", "remote_state", "remote_updated_at"),
                     rows=()):
    """ينشئ قاعدة بمخطط قديم صريح (بدون أعمدة الهُوية الجديدة) + صفوف.

    كل الأعمدة TEXT إلا `witness_preexisting` (لو موجود في مخطط قديم افتراضي).
    """
    conn = sqlite3.connect(path)
    collist = ", ".join(
        "witness_preexisting INTEGER NOT NULL DEFAULT 0" if c == "witness_preexisting" else f"{c} TEXT"
        for c in columns
    )
    pk = ", PRIMARY KEY(conversation_id)" if "conversation_id" in columns else ""
    conn.execute(f"CREATE TABLE deleted_conversations ({collist}{pk})")
    for row in rows:
        placeholders = ", ".join("?" for _ in row)
        conn.execute(f"INSERT INTO deleted_conversations VALUES ({placeholders})", row)
    conn.commit()
    conn.close()


# ============================================================ A. الترحيل والهُوية المتينة
def test_migration_from_mid_schema_adds_identity_and_backfills_legacy(tmp_path):
    """ترحيل من مخطط Mini App (4 أعمدة) ⇒ يضيف أعمدة الهُوية ويوسم الصفوف القديمة 1."""
    p = _path(tmp_path)
    _make_old_schema(p, rows=[
        (CID, LEGACY_TS, None, None),
        ("c2", "2026-01-02T00:00:00Z", "confirmed", "2026-01-02T00:00:00Z"),
    ])
    db = Database(p)
    cols = {r["name"] for r in db._conn.execute("PRAGMA table_info(deleted_conversations)")}
    assert {"witness_origin", "witness_attempt_id", "witness_preexisting"} <= cols
    # الصفوف القديمة كلها «سابقة لأي محاولة» ⇒ preexisting=1 (بغضّ النظر عن الطابع).
    for cid in (CID, "c2"):
        assert db.is_legacy_witness(cid) is True, cid
    assert db.is_legacy_witness("missing") is False


def test_migration_from_very_old_schema_two_columns(tmp_path):
    """ترحيل من مخطط أقدم (عمودين فقط: conversation_id, deleted_at)."""
    p = _path(tmp_path)
    _make_old_schema(p, columns=("conversation_id", "deleted_at"), rows=[(CID, LEGACY_TS)])
    db = Database(p)
    assert db.is_deleted(CID) is True
    assert db._conn.execute(
        "SELECT deleted_at FROM deleted_conversations WHERE conversation_id=?", (CID,)
    ).fetchone()["deleted_at"] == LEGACY_TS
    assert db.is_legacy_witness(CID) is True


def test_migration_preserves_deleted_at_and_unrelated_fields(tmp_path):
    """الترحيل ما يغيّرش deleted_at ولا باقي الأعمدة."""
    p = _path(tmp_path)
    _make_old_schema(p, rows=[(CID, LEGACY_TS, "uncertain", "2026-02-02T00:00:00Z")])
    db = Database(p)
    r = _row(db)
    assert r["deleted_at"] == LEGACY_TS
    assert r["remote_state"] == "uncertain"
    assert r["remote_updated_at"] == "2026-02-02T00:00:00Z"


def test_migration_is_idempotent(tmp_path):
    """فتح القاعدة مرات متعددة ما يغيّرش الهُوية ولا البيانات (الترحيل idempotent)."""
    p = _path(tmp_path)
    _make_old_schema(p, rows=[(CID, LEGACY_TS, None, None)])
    db1 = Database(p)
    snap1 = _row(db1)
    db1.close()
    db2 = Database(p)
    assert _row(db2) == snap1
    db2.close()
    db3 = Database(p)
    assert _row(db3) == snap1
    assert db3.is_legacy_witness(CID) is True


def test_migration_interrupted_then_rerun_is_safe(tmp_path):
    """انقطاع جزئي (عمود جديد أُضيف بلا backfill) ⇒ إعادة الفتح تكمّل بأمان."""
    p = _path(tmp_path)
    # نحاكي ترحيلًا انقطع بعد إضافة witness_origin فقط (بلا witness_preexisting/backfill).
    conn = sqlite3.connect(p)
    conn.execute(
        "CREATE TABLE deleted_conversations (conversation_id TEXT PRIMARY KEY, deleted_at TEXT, "
        "remote_state TEXT, remote_updated_at TEXT, witness_origin TEXT)"
    )
    conn.execute("INSERT INTO deleted_conversations(conversation_id, deleted_at, witness_origin) "
                 "VALUES (?,?,?)", (CID, LEGACY_TS, None))
    conn.commit()
    conn.close()
    db = Database(p)
    # الترحيل أكمل الأعمدة الناقصة ووسم الصف القديم.
    assert db.is_legacy_witness(CID) is True
    assert _row(db)["deleted_at"] == LEGACY_TS


def test_migration_does_not_reclassify_existing_new_attempt_rows(tmp_path):
    """صف من محاولة جديدة (origin='attempt', preexisting=0) ما يتحوّلش لقديم عند إعادة الفتح."""
    p = _path(tmp_path)
    db = Database(p)
    db.add_watched(CID, "شات", chat_id=1)
    db.begin_remote_deletion(CID, outbox.now_iso())
    assert db.is_legacy_witness(CID) is False
    db.close()
    db2 = Database(p)
    assert db2.is_legacy_witness(CID) is False  # ما اتصنّفش قديم بالغلط


def test_legacy_and_new_witness_identity_columns(tmp_path):
    """قيم الهُوية الصريحة: شاهد قديم preexisting=1، محاولة جديدة preexisting=0."""
    db = Database(_path(tmp_path, "a.sqlite3"))
    _seed_legacy(db)
    db.begin_remote_deletion(CID, outbox.now_iso())
    r = _row(db)
    assert r["witness_preexisting"] == 1
    assert r["witness_origin"] == "attempt"
    assert r["witness_attempt_id"]

    db2 = Database(_path(tmp_path, "b.sqlite3"))
    db2.add_watched(CID, "شات", chat_id=1)
    aid = db2.begin_remote_deletion(CID, outbox.now_iso())
    r2 = _row(db2)
    assert r2["witness_preexisting"] == 0
    assert r2["witness_attempt_id"] == aid


# ============================================================ B. استقلال التصنيف عن الوقت
def test_ts1_identical_timestamps_legacy_survives(tmp_path):
    """TS-1: طابع المحاولة == deleted_at (ساعة خشنة) ⇒ الشاهد القديم يفضل قديم وينجو."""
    p = _path(tmp_path)
    db = Database(p)
    _seed_legacy(db, ts=LEGACY_TS)
    db.begin_remote_deletion(CID, LEGACY_TS)  # طابع متطابق تمامًا
    assert db.is_legacy_witness(CID) is True
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=True), db))
    assert db.is_deleted(CID) is True
    assert db.remote_deletion_state(CID) is None


def test_ts1_clock_moves_backward_legacy_survives(tmp_path):
    """TS-1: الساعة رجعت ورا (طابع المحاولة أقدم من deleted_at) ⇒ يفضل قديم."""
    db = Database(_path(tmp_path))
    _seed_legacy(db, ts="2026-05-05T00:00:00Z")
    db.begin_remote_deletion(CID, "2020-01-01T00:00:00Z")  # أقدم (رجوع ساعة/NTP)
    assert db.is_legacy_witness(CID) is True


def test_ts1_new_witness_stays_new_when_clock_moves_backward(tmp_path):
    """TS-1: شاهد جديد (مفيش شاهد قبله) يفضل «جديد» حتى لو طابع المحاولة أقدم من deleted_at."""
    db = Database(_path(tmp_path))
    db.add_watched(CID, "شات", chat_id=1)
    db.begin_remote_deletion(CID, "2020-01-01T00:00:00Z")
    assert db.is_legacy_witness(CID) is False


def test_ts1_several_operations_same_tick(tmp_path):
    """TS-1: عمليات متعددة في نفس التِك (طوابع متطابقة) ⇒ التصنيف ما بيتبدّلش."""
    db = Database(_path(tmp_path))
    _seed_legacy(db, ts="2026-03-03T00:00:00Z")
    for _ in range(5):
        db.begin_remote_deletion(CID, "2026-03-03T00:00:00Z")
        assert db.is_legacy_witness(CID) is True
    # وشاهد جديد بيفضل جديد بنفس التِك.
    db2 = Database(_path(tmp_path, "b.sqlite3"))
    db2.add_watched(CID, "شات", chat_id=1)
    for _ in range(5):
        db2.begin_remote_deletion(CID, "2026-04-04T00:00:00Z")
        assert db2.is_legacy_witness(CID) is False


def test_ts1_timestamp_serialization_variants_do_not_matter(tmp_path):
    """TS-1: اختلاف صيغة الطابع (تطبيع/تسلسل) ما يأثّرش على التصنيف."""
    db = Database(_path(tmp_path))
    _seed_legacy(db, ts="2026-01-01T00:00:00+00:00")   # صيغة إنتاج
    db.begin_remote_deletion(CID, "2026-01-01T00:00:00Z")  # صيغة مختلفة/مطبّعة
    assert db.is_legacy_witness(CID) is True


def test_ts1_classification_survives_crash_and_restart(tmp_path):
    """TS-1: التصنيف ينجو من الإغلاق/إعادة الفتح مع طوابع متطابقة."""
    p = _path(tmp_path)
    db = Database(p)
    _seed_legacy(db, ts="2026-01-01T00:00:00Z")
    db.begin_remote_deletion(CID, "2026-01-01T00:00:00Z")
    db.close()
    db2 = Database(p)
    assert db2.is_legacy_witness(CID) is True


# ============================================================ C. سباق lost-update
def test_lost_update_stale_failure_does_not_clobber_confirmed(tmp_path):
    """السيناريو المبلَّغ عنه: A يشوف معلّق، B يؤكّد، A يكمّل بفشل قديم ⇒ ما يطمسش B."""
    db = Database(_path(tmp_path))
    db.add_watched(CID, "شات", chat_id=1)

    class Cl:
        def __init__(self):
            self.n = 0
            self.b_entered = asyncio.Event()
            self.a_done = asyncio.Event()

        async def delete_conversation(self, cid):
            self.n += 1
            if self.n == 1:  # B: يشوف معلّق ثم ينهار (فشل مؤكّد) بعد ما A يأكّد
                self.b_entered.set()
                await self.a_done.wait()
                raise ApiError("x", 403)
            return True  # A: نجاح ⇒ confirmed

        async def conversation_exists(self, cid):
            return False

    cl = Cl()

    async def main():
        b = asyncio.create_task(deletion.delete_conversation_remote(cl, db, CID))  # B (call 1)
        await cl.b_entered.wait()
        a = asyncio.create_task(deletion.delete_conversation_remote(cl, db, CID))  # A (call 2)
        ra = await a
        assert ra.status == deletion.STATUS_DELETED
        assert db.remote_deletion_state(CID) == db.REMOTE_CONFIRMED
        cl.a_done.set()  # خلّي B يفشل الآن
        rb = await b
        assert rb.status == deletion.STATUS_FAILED
        # B القديم ما طمسش تأكيد A.
        assert db.remote_deletion_state(CID) == db.REMOTE_CONFIRMED
        assert db.is_deleted(CID) is True

    asyncio.run(main())


def test_concurrent_two_deletion_attempts_confirmed_is_preserved(tmp_path):
    """محاولتان متزامنتان (نجاح + فشل) ⇒ 'confirmed' ما بتتطمسش."""
    db = Database(_path(tmp_path))
    db.add_watched(CID, "شات", chat_id=1)

    class Cl:
        def __init__(self):
            self.n = 0
            self.fail_entered = asyncio.Event()
            self.ok_done = asyncio.Event()

        async def delete_conversation(self, cid):
            self.n += 1
            if self.n == 1:
                self.fail_entered.set()
                await self.ok_done.wait()
                raise ApiError("x", 422)
            return True

        async def conversation_exists(self, cid):
            return False

    cl = Cl()

    async def main():
        f = asyncio.create_task(deletion.delete_conversation_remote(cl, db, CID))
        await cl.fail_entered.wait()
        ok = asyncio.create_task(deletion.delete_conversation_remote(cl, db, CID))
        await ok
        cl.ok_done.set()
        await f
        assert db.remote_deletion_state(CID) == db.REMOTE_CONFIRMED
        assert db.is_deleted(CID) is True

    asyncio.run(main())


def test_old_reconcile_does_not_overwrite_newer_deletion(tmp_path):
    """تسوية قديمة تكمل بعد ما محاولة أحدث بدأت ⇒ ملكية الأحدث محفوظة (رد CAS فاشل)."""
    db = Database(_path(tmp_path))
    db.add_watched(CID, "شات", chat_id=1)
    old_owner = db.begin_remote_deletion(CID, outbox.now_iso())

    class RacingClient(FakeClient):
        async def conversation_exists(self, cid):
            # أثناء التحقق، محاولة أحدث تبدأ وتسحب الملكية (interleaving فعلي).
            db.begin_remote_deletion(CID, outbox.now_iso())
            return True

    asyncio.run(deletion.reconcile_pending_deletions(RacingClient(exists=True), db))
    # التسوية القديمة (مالكها old_owner) ما شالتش الشاهد — ملكية الأحدث محفوظة.
    assert db.witness_attempt_id(CID) != old_owner
    assert db.is_deleted(CID) is True
    assert db.remote_deletion_state(CID) == db.REMOTE_DELETING


def test_old_revert_cas_does_not_overwrite_newer_state(tmp_path):
    """CAS على مالك قديم ما يطمسش حالة أحدث (يرجّع False ويتجاهل)."""
    db = Database(_path(tmp_path))
    db.add_watched(CID, "شات", chat_id=1)
    old = db.begin_remote_deletion(CID, outbox.now_iso())
    new = db.begin_remote_deletion(CID, outbox.now_iso())  # محاولة أحدث سحبت الملكية
    assert old != new
    assert db.revert_remote_deletion_cas(CID, old, None, None) is False
    assert db.witness_attempt_id(CID) == new
    assert db.remote_deletion_state(CID) == db.REMOTE_DELETING


def test_confirmation_vs_definite_failure_ordering(tmp_path):
    """تأكيد ثم فشل مؤكّد (بالتسلسل) ⇒ التأكيد يفضل."""
    db = Database(_path(tmp_path))
    db.add_watched(CID, "شات", chat_id=1)
    _run(FakeClient("ok"), db)
    assert db.remote_deletion_state(CID) == db.REMOTE_CONFIRMED
    res = _run(FakeClient(("status", 403)), db)  # idempotent (confirmed سابقًا)
    assert res.status == deletion.STATUS_DELETED
    assert db.remote_deletion_state(CID) == db.REMOTE_CONFIRMED


def test_confirmation_vs_ambiguous_present(tmp_path):
    """تأكيد ثم نتيجة مبهمة+موجود ⇒ الشاهد القديم المؤكّد ما يتحذفش بالغلط."""
    db = Database(_path(tmp_path))
    db.add_watched(CID, "شات", chat_id=1)
    _run(FakeClient("ok"), db)
    owner = db.witness_attempt_id(CID)
    # محاولة قديمة تحاول تشيل الشاهد بملكية قديمة ⇒ تفشل.
    assert db.clear_witness_cas(CID, "stale-owner") is False
    assert db.is_deleted(CID) is True
    assert db.witness_attempt_id(CID) == owner


def test_concurrent_startup_reconciliation_preserves_legacy(tmp_path):
    """تسويتا إقلاع متزامنتان (اتصالان مستقلان) ⇒ الشاهد القديم ينجو دائمًا."""
    p = _path(tmp_path)
    db = Database(p)
    _seed_legacy(db)
    db.begin_remote_deletion(CID, outbox.now_iso())
    db2 = Database(p)
    barrier = threading.Barrier(2)

    def worker(d):
        barrier.wait()
        asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=True), d))

    ts = [threading.Thread(target=worker, args=(db,)), threading.Thread(target=worker, args=(db2,))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert db.is_deleted(CID) is True
    assert db.remote_deletion_state(CID) is None


def test_concurrent_reconcile_and_new_deletion(tmp_path):
    """تسوية (موجود) تتزامن مع حذف جديد ⇒ محاولة الحذف الأحدث ما تتطمسش."""
    p = _path(tmp_path)
    db = Database(p)
    db.add_watched(CID, "شات", chat_id=1)
    owner = db.begin_remote_deletion(CID, outbox.now_iso())
    # محاولة أحدث بدأت (سحبت الملكية) قبل ما التسوية القديمة تقرّر «موجود».
    newer = db.begin_remote_deletion(CID, outbox.now_iso())
    assert newer != owner
    # التسوية القديمة تحاول تشيل بملكيتها القديمة ⇒ تفشل (ما تطمسش الأحدث).
    assert db.clear_witness_cas(CID, owner) is False
    assert db.witness_attempt_id(CID) == newer


def test_restart_between_competing_operations(tmp_path):
    """إعادة تشغيل بين عمليتين متنافستين ⇒ الملكية محفوظة والحالة الأحدث تنجو."""
    p = _path(tmp_path)
    db = Database(p)
    db.add_watched(CID, "شات", chat_id=1)
    old_owner = db.begin_remote_deletion(CID, outbox.now_iso())
    db.close()
    db2 = Database(p)
    # بعد إعادة التشغيل، محاولة جديدة تسحب الملكية.
    new_owner = db2.begin_remote_deletion(CID, outbox.now_iso())
    assert new_owner != old_owner
    assert db2.revert_remote_deletion_cas(CID, old_owner, None, None) is False
    assert db2.witness_attempt_id(CID) == new_owner


# ============================================================ D. دورة الحياة الكاملة
def test_lifecycle_new_success(tmp_path):
    db = Database(_path(tmp_path))
    db.add_watched(CID, "شات", chat_id=1)
    assert _run(FakeClient("ok"), db).status == deletion.STATUS_DELETED
    assert db.remote_deletion_state(CID) == db.REMOTE_CONFIRMED
    assert db.get_watched(CID) is None


def test_lifecycle_new_definite_failure_no_witness(tmp_path):
    db = Database(_path(tmp_path))
    db.add_watched(CID, "شات", chat_id=1)
    assert _run(FakeClient(("status", 403)), db).status == deletion.STATUS_FAILED
    assert db.is_deleted(CID) is False
    assert db.remote_deletion_state(CID) is None


def test_lifecycle_new_uncertain_pending(tmp_path):
    db = Database(_path(tmp_path))
    db.add_watched(CID, "شات", chat_id=1)
    assert _run(FakeClient("unknown", exists_error=True), db).status == deletion.STATUS_PENDING
    assert db.remote_deletion_state(CID) == db.REMOTE_UNCERTAIN
    assert db.is_deleted(CID) is True


def test_lifecycle_legacy_preserved_on_present(tmp_path):
    db = Database(_path(tmp_path))
    _seed_legacy(db)
    assert _run(FakeClient("404", exists=True), db).status == deletion.STATUS_FAILED
    assert db.is_deleted(CID) is True
    assert db.remote_deletion_state(CID) is None
    assert _row(db)["deleted_at"] == LEGACY_TS


def test_lifecycle_two_read_absence_confirms(tmp_path):
    db = Database(_path(tmp_path))
    db.add_watched(CID, "شات", chat_id=1)
    assert _run(FakeClient("404", exists_seq=[False, False]), db).status == deletion.STATUS_DELETED
    assert db.remote_deletion_state(CID) == db.REMOTE_CONFIRMED
    assert deletion._ABSENCE_CONFIRMATIONS == 2


def test_lifecycle_single_missing_read_does_not_confirm(tmp_path):
    db = Database(_path(tmp_path))
    _seed_legacy(db)
    db.begin_remote_deletion(CID, outbox.now_iso())
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists_seq=[False, True]), db))
    assert db.is_deleted(CID) is True
    assert db.remote_deletion_state(CID) is None


def test_lifecycle_unverifiable_keeps_pending_and_no_resurrection(tmp_path):
    db = Database(_path(tmp_path))
    # مفيش متابعة مبدئية (زي حالة mini-app/web) ⇒ الشاهد موجود بلا watched.
    _run(FakeClient("404", exists_error=True), db)
    assert db.remote_deletion_state(CID) == db.REMOTE_UNCERTAIN
    # محاولة إعادة إحياء غير صريحة (worker/outbox) ⇒ مرفوضة بسبب الشاهد (ما اتحذفش محليًا).
    db.add_watched(CID, "شات", chat_id=1, new_lifecycle=False)
    assert db.get_watched(CID) is None
    assert db.is_deleted(CID) is True
    # التسوية مع تعذّر التحقق ⇒ تفضل معلّقة (مفيش تخمين).
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists_error=True), db))
    assert db.remote_deletion_state(CID) == db.REMOTE_UNCERTAIN
    assert CID in db.list_pending_remote_deletions()


def test_lifecycle_crash_during_deleting_then_restart_reconcile(tmp_path):
    p = _path(tmp_path)
    db = Database(p)
    db.add_watched(CID, "شات", chat_id=1)
    db.begin_remote_deletion(CID, outbox.now_iso())  # انهيار أثناء 'deleting'
    db.close()
    db2 = Database(p)
    assert db2.list_pending_remote_deletions_with_owner()[0][0] == CID
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=False), db2))
    assert db2.remote_deletion_state(CID) == db2.REMOTE_CONFIRMED


def test_lifecycle_no_stale_overwrite_across_restart(tmp_path):
    """إعادة تشغيل بعد تأكيد: محاولة معلّقة قديمة ما تطمسش 'confirmed' (سقف أعلى)."""
    p = _path(tmp_path)
    db = Database(p)
    db.add_watched(CID, "شات", chat_id=1)
    stale_owner = db.begin_remote_deletion(CID, outbox.now_iso())
    # محاولة أحدث تسحب الملكية ثم يؤكّد الحذف محليًا (نفس مسار `_finalize`).
    newer_owner = db.begin_remote_deletion(CID, outbox.now_iso())
    assert newer_owner != stale_owner
    db.delete_conversation(CID, outbox.now_iso(), remote_confirmed=True)
    db.close()
    db2 = Database(p)
    assert db2.remote_deletion_state(CID) == db2.REMOTE_CONFIRMED
    # المحاولة القديمة ما تقدرش تطمس التأكيد (لا مسح ولا كتابة).
    assert db2.clear_witness_cas(CID, stale_owner) is False
    assert db2.revert_remote_deletion_cas(CID, stale_owner, None, None) is False
    # ولا حتى المالك الحالي يقدر (confirmed نهائي).
    assert db2.clear_witness_cas(CID, newer_owner) is False
    assert db2.is_deleted(CID) is True
    assert db2.remote_deletion_state(CID) == db2.REMOTE_CONFIRMED


def test_reconcile_listing_with_owner_exposes_attempt(tmp_path):
    db = Database(_path(tmp_path))
    db.add_watched(CID, "شات", chat_id=1)
    aid = db.begin_remote_deletion(CID, outbox.now_iso())
    assert db.list_pending_remote_deletions_with_owner() == [(CID, aid)]


def test_new_attempt_does_not_clobber_confirmed(tmp_path):
    """(سقف أعلى) محاولة تبدأ والشات مؤكّد مسبقًا ⇒ ما تسحبش الملكية ولا تلغي التأكيد."""
    db = Database(_path(tmp_path))
    db.add_watched(CID, "شات", chat_id=1)
    owner = db.begin_remote_deletion(CID, outbox.now_iso())
    db.delete_conversation(CID, outbox.now_iso(), remote_confirmed=True)
    assert db.remote_deletion_state(CID) == db.REMOTE_CONFIRMED
    confirmed_owner = db.witness_attempt_id(CID)
    assert owner is not None
    # محاولة جديدة تبدأ بعد التأكيد ⇒ ممنوعة من سحب الملكية (begin يرجّع None).
    assert db.begin_remote_deletion(CID, outbox.now_iso()) is None
    assert db.remote_deletion_state(CID) == db.REMOTE_CONFIRMED
    assert db.witness_attempt_id(CID) == confirmed_owner


def test_stale_failure_redundant_if_newer_attempt_owns(tmp_path):
    """فشل مؤكّد من محاولة قديمة بعد ما محاولة أحدث بدأت ⇒ ما يطمسش حالة الأحدث."""
    db = Database(_path(tmp_path))
    db.add_watched(CID, "شات", chat_id=1)
    old = db.begin_remote_deletion(CID, outbox.now_iso())
    newer = db.begin_remote_deletion(CID, outbox.now_iso())
    assert old != newer
    # المحاولة القديمة تحاول ترجّع الحالة (فشل مؤكّد) بملكيتها القديمة ⇒ تفشل.
    assert db.revert_remote_deletion_cas(CID, old, "confirmed", outbox.now_iso()) is False
    assert db.witness_attempt_id(CID) == newer
    assert db.remote_deletion_state(CID) == db.REMOTE_DELETING


# ======================================== E. مراجعة مستقلة: «confirmed» حالة نهائية
class _GateClient:
    """عميل ببوّابات تحكّم (asyncio Events) لضبط ترتيب تسليم النتائج بدقّة."""

    def __init__(self, first_succeeds=True):
        self.first_succeeds = first_succeeds
        self.n = 0
        self.first_entered = asyncio.Event()
        self.second_entered = asyncio.Event()
        self.release_first = asyncio.Event()
        self.release_second = asyncio.Event()

    async def delete_conversation(self, conversation_id):
        self.n += 1
        if self.n == 1:
            self.first_entered.set()
            await self.release_first.wait()
            if self.first_succeeds:
                return True
            raise ApiError("x", 403)
        self.second_entered.set()
        await self.release_second.wait()
        raise ApiError("x", 403)

    async def conversation_exists(self, conversation_id):
        return False


def test_confirmed_terminal_newer_owner_stale_failure(tmp_path):
    """(مراجعة) الترتيب المعاكس: محاولة أحدث (مالكة) تفشل بعد ما محاولة أقدم أكّدت الحذف.

    لازم 'confirmed' تفضل نهائية — ما ترجعش 'deleting' (منع lost-update).
    """
    db = Database(_path(tmp_path))
    db.add_watched(CID, "شات", chat_id=1)
    cl = _GateClient()

    async def scenario():
        # B: المحاولة الأقدم (بتأكّد الحذف)، بتبدأ الأولى ⇒ ملكية=B.
        b = asyncio.create_task(deletion.delete_conversation_remote(cl, db, CID))
        await cl.first_entered.wait()
        # A: محاولة أحدث بتبدأ بعد كده ⇒ ملكية=A.
        a = asyncio.create_task(deletion.delete_conversation_remote(cl, db, CID))
        await cl.second_entered.wait()
        # B (المالك القديم) تأكّد الحذف الأول.
        cl.release_first.set()
        rb = await b
        assert rb.status == deletion.STATUS_DELETED
        assert db.remote_deletion_state(CID) == db.REMOTE_CONFIRMED
        # A (المالك الأحدث) تفشل فشل مؤكّد وترجع لقطتها القديمة ⇒ ما تطمسش التأكيد.
        cl.release_second.set()
        ra = await a
        assert ra.status == deletion.STATUS_FAILED  # الفشل المؤكّد يبلّغ فشل صريح
        # لكن الحالة المحلية تفضل 'confirmed' (نهائية) والشاهد ما اتشالش (منع lost-update).
        assert db.remote_deletion_state(CID) == db.REMOTE_CONFIRMED
        assert db.is_deleted(CID) is True

    asyncio.run(scenario())


def test_reconcile_cannot_erase_confirmed_witness(tmp_path):
    """(مراجعة) تسوية إقلاع «الشات لسه موجود» ما تشيلش شاهدًا اتأكّد حذفه في الأثناء."""
    db = Database(_path(tmp_path))
    db.add_watched(CID, "شات", chat_id=1)
    owner = db.begin_remote_deletion(CID, outbox.now_iso())

    class _RacingPresent:
        async def conversation_exists(self, conversation_id):
            # عملية متزامنة أكّدت الحذف البعيد أثناء التسوية.
            db.delete_conversation(conversation_id, outbox.now_iso(), remote_confirmed=True)
            return True  # «الشات لسه موجود» — نتيجة قديمة

        async def delete_conversation(self, conversation_id):
            return True

    asyncio.run(deletion.reconcile_pending_deletions(_RacingPresent(), db))
    assert db.remote_deletion_state(CID) == db.REMOTE_CONFIRMED
    assert db.is_deleted(CID) is True
    assert db.witness_attempt_id(CID) == owner  # الشاهد ما اتشالش


def test_cas_refuses_confirmed_for_owner_and_stale(tmp_path):
    """(مراجعة) confirmed نهائية: لا clear ولا revert ينجحوا حتى لو المالك مطابق."""
    db = Database(_path(tmp_path))
    db.add_watched(CID, "شات", chat_id=1)
    owner = db.begin_remote_deletion(CID, outbox.now_iso())
    db.delete_conversation(CID, outbox.now_iso(), remote_confirmed=True)
    assert db.clear_witness_cas(CID, owner) is False
    assert db.revert_remote_deletion_cas(CID, owner, None, None) is False
    assert db.remote_deletion_state(CID) == db.REMOTE_CONFIRMED
    assert db.is_deleted(CID) is True


def test_migrated_legacy_pending_settles_on_present_reconcile(tmp_path):
    """(مراجعة) صف قديم معلّق بعد الترحيل (مالك NULL) بيتسوّى مع «موجود» والشاهد يفضل."""
    p = _path(tmp_path)
    # مخطط قديم فيه صف معلّق (remote_state='deleting') بدون أعمدة الهُوية الجديدة.
    _make_old_schema(p, rows=[(CID, LEGACY_TS, "deleting", LEGACY_TS)])
    db = Database(p)  # الترحيل يوسمه preexisting=1 ويسيب المالك NULL
    assert db.is_legacy_witness(CID) is True
    assert db.witness_attempt_id(CID) is None
    assert db.list_pending_remote_deletions_with_owner() == [(CID, None)]
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=True), db))
    assert db.remote_deletion_state(CID) is None  # اتحلّت — مابقيتش عالقة
    assert db.is_deleted(CID) is True             # الشاهد القديم اتحفظ


def test_legacy_pending_migration_survives_restart(tmp_path):
    """صف قديم معلّق (مالك NULL) + إعادة تشغيل ثم تسوية «موجود» ⇒ يفضل متسوّى والشاهد محفوظ."""
    p = _path(tmp_path)
    _make_old_schema(p, rows=[(CID, LEGACY_TS, "uncertain", LEGACY_TS)])
    db = Database(p)
    db.close()
    db2 = Database(p)
    assert db2.witness_attempt_id(CID) is None
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=True), db2))
    assert db2.remote_deletion_state(CID) is None
    assert db2.is_deleted(CID) is True
