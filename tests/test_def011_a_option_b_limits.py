"""OHB2-WP07-DEF011-A — Option B: حدود سعة الـ staging (10 ملفات/دفعة + 64 MiB كلي).

التفعيل المعتمد (2026-11-21) بيتحقّن من 3 زوايا:
- **الربط الإنتاجي:** `handlers._attachment_service` بيبني المخزن الإنتاجي بالحدّين.
- **السلوك:** سقف 3 MiB لكل ملف لسه مفعّل؛ 10 ملفات تتقبل و11 يترفض؛ السقف الكلي
  (64 MiB) بيتطبّق عند الحد بالظبط وتحته وفوقه؛ السعة مشتركة بين الدفعات.
- **السلامة:** رفض الحصة ما بيسيبش ملف جزئي؛ الكتابة الفاشلة ما بتاكلش سعة؛ الحذف
  idempotent؛ الانتهاء بيسترجع سعة الـ staging بس (بيانات C2 برّه ما بتُلمسش)؛ إعادة
  البناء من الملفات الفعلية؛ الملفات اليتيمة بتُحسب وما بتُحذفش.

كل الاختبارات معزولة (tmp_path + SQLite مؤقّت)، بلا شبكة/تيليجرام/OpenHands.
"""

from __future__ import annotations

import asyncio
import pathlib
import re
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from bot import attachments as attachments_mod
from bot import db as db_module
from bot import handlers
from bot.attachments import (
    MAX_ATTACHMENT_BYTES,
    AttachmentReaper,
    AttachmentService,
    StageStatus,
    StagingStore,
    staging_total_bytes,
)
from bot.db import Database
from bot.files import IdentityCache

from tests.test_repair_plan_01_resource_staging import (
    CID,
    OWNER_ID,
    FakeClient,
    add_batch,
    make_store,
    _run,
)

T0_DT = datetime(2026, 11, 11, tzinfo=timezone.utc)
EXPIRED_AT = T0_DT + timedelta(minutes=20)

# القيم المعتمدة في Option B (نفس ثوابت الوحدة المرجعية).
OPTION_B_ITEMS = 10
OPTION_B_TOTAL = 64 * 1024 * 1024


# ------------------------------------------------------------------ مساعدات
def _service(db, store):
    client = FakeClient()
    return AttachmentService(db, store, client, IdentityCache(client))


async def _accept(service, name, payload=b"x", *, now=T0_DT, update_id=None):
    async def factory():
        return iter([payload])

    return await service.accept(
        telegram_id=OWNER_ID,
        conversation_id=CID,
        display_name=name,
        declared_size=None,
        update_id=update_id,
        now=now,
        chunks_factory=factory,
    )


def _store(db, store, item_id, payload, *, batch_id="b1", name="a.txt"):
    return store.store(
        telegram_id=OWNER_ID,
        batch_id=batch_id,
        item_id=item_id,
        display_name=name,
        chunks=[payload],
    )


def _sparse(path, size):
    """ملف فعلي بحجم منطقي `size` (sparse) — بيتحسب في `staging_total_bytes`."""
    with open(path, "wb") as handle:
        handle.truncate(size)


def _reaper(db, tmp_path):
    return AttachmentReaper(db, str(tmp_path / "state.sqlite3"))


# ============================================================ 1) الربط الإنتاجي
class _FakeCtx:
    def __init__(self, db, db_path):
        self.bot_data = {
            "db": db,
            "config": SimpleNamespace(db_path=db_path),
            "client": FakeClient(),
        }


def test_production_wiring_enables_option_b_limits(tmp_path):
    """المخزن الإنتاجي بيتبني بـ 10 ملفات/دفعة و64 MiB كلي، وسقف 3 MiB لسه مفعّل."""
    db_path = str(tmp_path / "state.sqlite3")
    db = Database(db_path)
    try:
        ctx = _FakeCtx(db, db_path)
        service = handlers._attachment_service(ctx)
        store = service.store

        assert store.max_items_per_batch == OPTION_B_ITEMS == 10
        assert store.max_total_bytes == OPTION_B_TOTAL == 64 * 1024 * 1024
        assert store.max_bytes == MAX_ATTACHMENT_BYTES == 3 * 1024 * 1024
        assert store.quota_enabled is True

        # مخزن واحد مُخزَّن مؤقتًا (مفيش نسخة تانية بقفل تاني).
        assert handlers._attachment_service(ctx).store is store
    finally:
        db.close()


def test_default_store_stays_unenforced():
    """الافتراضي في `StagingStore` لسه `None` (مفيش فرض ضمني لأي مستدعٍ آخر)."""
    import inspect

    signature = inspect.signature(StagingStore.__init__)
    assert signature.parameters["max_items_per_batch"].default is None
    assert signature.parameters["max_total_bytes"].default is None
    assert signature.parameters["max_bytes_per_batch"].default is None


# ==================================================== 2) سقف الملف الواحد
def test_per_file_3mib_limit_still_enforced(tmp_path):
    """3 MiB بالظبط يمرّ، و3 MiB + 1 يترفض (سقف الملف محفوظ)."""
    db, store = make_store(
        tmp_path, max_items_per_batch=OPTION_B_ITEMS, max_total_bytes=OPTION_B_TOTAL
    )
    add_batch(db)

    exact = _store(db, store, "i-exact", b"x" * MAX_ATTACHMENT_BYTES)
    assert exact.status is StageStatus.STORED

    over = _store(db, store, "i-over", b"x" * (MAX_ATTACHMENT_BYTES + 1))
    assert over.status is StageStatus.REJECTED_SIZE

    assert len(list(store.root.iterdir())) == 1
    assert staging_total_bytes(store.root) == MAX_ATTACHMENT_BYTES


# ==================================================== 3) سقف عدد الملفات
def test_ten_files_accepted_eleventh_rejected(tmp_path):
    """10 ملفات تتقبل، والـ 11 يترفض، بلا ملف جزئي."""
    db, store = make_store(
        tmp_path, max_items_per_batch=OPTION_B_ITEMS, max_total_bytes=OPTION_B_TOTAL
    )
    add_batch(db)
    service = _service(db, store)

    async def run():
        return [await _accept(service, f"f{i}.txt", b"x") for i in range(11)]

    results = _run(run())
    assert sum(1 for r in results if r.stage is StageStatus.STORED) == 10
    assert results[-1].stage is StageStatus.REJECTED_QUOTA
    assert len(list(store.root.iterdir())) == 10
    assert staging_total_bytes(store.root) == 10


# ============================================ 4) السقف الكلي عند 64 MiB
def test_aggregate_64mib_boundary_below_exact_above(tmp_path):
    """تحت 64 MiB يمرّ، وعند الحد بالظبط وفوقه يترفض — بلا ملف جزئي."""
    db, store = make_store(
        tmp_path, max_items_per_batch=OPTION_B_ITEMS, max_total_bytes=OPTION_B_TOTAL
    )
    add_batch(db)
    store.ensure_root()

    # ملف يتيم بحجم 64 MiB − 1 ⇒ المتبقّي 1 بايت بالظبط.
    orphan = store.root / ("a" * 32)
    _sparse(orphan, OPTION_B_TOTAL - 1)
    assert staging_total_bytes(store.root) == OPTION_B_TOTAL - 1

    below = _store(db, store, "i-below", b"x")
    assert below.status is StageStatus.STORED
    assert staging_total_bytes(store.root) == OPTION_B_TOTAL
    files_at_limit = {p.name for p in store.root.iterdir()}
    assert len(files_at_limit) == 2  # اليتيم + الملف المخزَّن

    # عند الحد بالظبط ⇒ مفيش سعة ⇒ رفض قبل أي كتابة/صف.
    exact = _store(db, store, "i-exact", b"y")
    assert exact.status is StageStatus.REJECTED_QUOTA
    assert {p.name for p in store.root.iterdir()} == files_at_limit

    # فوق الحد (ملف يتيم إضافي 1 بايت) ⇒ رفض برضه.
    _sparse(store.root / ("b" * 32), 1)
    above = _store(db, store, "i-above", b"z")
    assert above.status is StageStatus.REJECTED_QUOTA
    assert {p.name for p in store.root.iterdir()} == files_at_limit | {"b" * 32}

    # الملف اليتيم الأصلي ما اتغيّرش.
    assert orphan.exists()
    assert orphan.stat().st_size == OPTION_B_TOTAL - 1


def test_aggregate_rejection_via_accept_leaves_no_file(tmp_path):
    """الرفض بسبب السعة الكلية في مسار `accept` ما بيسيبش ملف جزئي."""
    db, store = make_store(tmp_path, max_total_bytes=100)
    add_batch(db)
    store.ensure_root()
    orphan = store.root / ("e" * 32)
    _sparse(orphan, 100)
    service = _service(db, store)

    result = _run(_accept(service, "a.txt", b"x" * 10))

    assert result.stage is StageStatus.REJECTED_QUOTA
    assert {p.name for p in store.root.iterdir()} == {orphan.name}
    assert staging_total_bytes(store.root) == 100
    # الصف الوصفي محفوظ (row-first) بلا ملف ⇒ مش بيستهلك سعة، ويُكنس عند الانتهاء.
    items = db.list_attachment_items("b1")
    assert len(items) == 1 and items[0].status == "pending"


def test_aggregate_capacity_is_shared_across_batches(tmp_path):
    """السقف الكلي مشترك بين الدفعات (نفس جذر الـ staging)."""
    db, store = make_store(tmp_path, max_total_bytes=10)
    add_batch(db, "b1")
    add_batch(db, "b2")

    r1 = _store(db, store, "i1", b"123456", batch_id="b1")
    assert r1.status is StageStatus.STORED  # 6

    r2 = _store(db, store, "i2", b"12345", batch_id="b2")
    assert r2.status is StageStatus.REJECTED_QUOTA  # 6 + 5 > 10

    r3 = _store(db, store, "i3", b"1234", batch_id="b2")
    assert r3.status is StageStatus.STORED  # 6 + 4 == 10


# ==================================== 5) التزامن (القفل + التسلسل الفعلي)
def test_concurrent_intake_cannot_bypass_item_limit(tmp_path):
    """15 قبولًا متزامنًا مع سقف 10 ⇒ 10 بالظبط، والباقي رفض."""
    db, store = make_store(tmp_path, max_items_per_batch=OPTION_B_ITEMS)
    add_batch(db)

    async def run():
        tasks = [
            store.store_async(
                telegram_id=OWNER_ID,
                batch_id="b1",
                item_id=f"i{n}",
                display_name=f"c{n}.txt",
                chunks=[b"x"],
            )
            for n in range(15)
        ]
        return await asyncio.gather(*tasks)

    results = _run(run())
    assert sum(1 for r in results if r.status is StageStatus.STORED) == 10
    assert sum(1 for r in results if r.status is StageStatus.REJECTED_QUOTA) == 5
    assert len(list(store.root.iterdir())) == 10


def test_concurrent_intake_cannot_bypass_global_byte_limit(tmp_path):
    """10 قبولات متزامنة × 30 بايت مع سقف 100 ⇒ 3 بس، بلا تجاوز."""
    db, store = make_store(tmp_path, max_total_bytes=100)
    add_batch(db)

    async def run():
        tasks = [
            store.store_async(
                telegram_id=OWNER_ID,
                batch_id="b1",
                item_id=f"i{n}",
                display_name=f"c{n}.txt",
                chunks=[b"x" * 30],
            )
            for n in range(10)
        ]
        return await asyncio.gather(*tasks)

    results = _run(run())
    assert sum(1 for r in results if r.status is StageStatus.STORED) == 3
    assert sum(1 for r in results if r.status is StageStatus.REJECTED_QUOTA) == 7
    assert staging_total_bytes(store.root) == 90
    assert len(list(store.root.iterdir())) == 3


# ==================================== 6) الفشل والاسترجاع والحذف المتكرر
def test_failed_write_does_not_consume_capacity(tmp_path, monkeypatch):
    """فشل `fsync` ⇒ `WRITE_FAILED`، مفيش ملف، مفيش سعة مستهلكة، والصف يفضل pending."""
    db, store = make_store(
        tmp_path, max_items_per_batch=OPTION_B_ITEMS, max_total_bytes=OPTION_B_TOTAL
    )
    add_batch(db)

    def _boom(_fd):
        raise OSError("simulated fsync failure")

    monkeypatch.setattr(attachments_mod.os, "fsync", _boom)
    result = _store(db, store, "i1", b"x" * 10)

    assert result.status is StageStatus.WRITE_FAILED
    assert list(store.root.iterdir()) == []
    assert staging_total_bytes(store.root) == 0
    items = db.list_attachment_items("b1")
    assert len(items) == 1 and items[0].status == "pending"


def test_interrupted_partial_file_is_accounted_and_reclaimed(tmp_path):
    """ملف جزئي من انقطاع بيتحسب بعد إعادة البناء، والانتهاء بيسترجع السعة."""
    db_path = str(tmp_path / "state.sqlite3")
    db = Database(db_path)
    try:
        store = StagingStore(db, db_path, max_total_bytes=100, clock=lambda: T0_DT)
        add_batch(db)
        store.ensure_root()

        # محاكاة انقطاع: صف pending + ملف جزئي 60 بايت.
        db.add_attachment_item(
            "i1", "b1", staging_token="c" * 32, display_name="a.txt", status="pending"
        )
        (store.root / ("c" * 32)).write_bytes(b"x" * 60)
        assert staging_total_bytes(store.root) == 60

        # إعادة بناء مخزن جديد: المحاسبة من الملفات الفعلية ⇒ المتبقّي 40.
        fresh = StagingStore(db, db_path, max_total_bytes=100, clock=lambda: T0_DT)
        ok = _store(db, fresh, "i2", b"y" * 40)
        assert ok.status is StageStatus.STORED
        assert staging_total_bytes(store.root) == 100

        too_big = _store(db, fresh, "i3", b"z")
        assert too_big.status is StageStatus.REJECTED_QUOTA

        report = AttachmentReaper(db, db_path).sweep(now=EXPIRED_AT)
        assert report.files_deleted >= 2
        assert staging_total_bytes(store.root) == 0
    finally:
        db.close()


def test_repeated_sweep_is_idempotent_and_releases_once(tmp_path):
    """كنس متكرر idempotent: الملف بيتحذف مرة واحدة والسعة بتتحرّر."""
    db, store = make_store(tmp_path, max_total_bytes=100)
    add_batch(db)
    _run(_accept(_service(db, store), "a.txt", b"x" * 10))

    reaper = _reaper(db, tmp_path)
    first = reaper.sweep(now=EXPIRED_AT)
    assert first.files_deleted >= 1
    assert staging_total_bytes(store.root) == 0

    second = reaper.sweep(now=EXPIRED_AT + timedelta(minutes=5))
    assert second.files_deleted == 0
    assert staging_total_bytes(store.root) == 0


def test_repeated_intake_after_release(tmp_path):
    """بعد تحرير السعة بالانتهاء، القبول يرجع يشتغل (تكرار الإدخال)."""
    db, store = make_store(tmp_path, max_items_per_batch=2)
    add_batch(db)
    service = _service(db, store)

    async def two():
        return [await _accept(service, f"f{i}.txt", b"x") for i in range(3)]

    results = _run(two())
    assert [r.stage for r in results] == [
        StageStatus.STORED,
        StageStatus.STORED,
        StageStatus.REJECTED_QUOTA,
    ]

    _reaper(db, tmp_path).sweep(now=EXPIRED_AT)
    assert staging_total_bytes(store.root) == 0

    # دفعة جديدة بعد الانتهاء تقبل من جديد.
    add_batch(db, "b2")
    async def again():
        return await _accept(service, "g.txt", b"y")

    assert _run(again()).stage is StageStatus.STORED


# ================================================ 7) الانتهاء وبيانات C2
def test_expiry_releases_staging_and_preserves_outside_data(tmp_path):
    """الانتهاء بيسترجع سعة الـ staging بس؛ ملف برّه الجذر (C2) ما بيتلمسش."""
    db, store = make_store(tmp_path, max_total_bytes=100)
    add_batch(db)
    _run(_accept(_service(db, store), "a.txt", b"x" * 10))

    c2 = tmp_path / "conversation_copy.txt"
    c2.write_bytes(b"keep-me")

    _reaper(db, tmp_path).sweep(now=EXPIRED_AT)

    assert staging_total_bytes(store.root) == 0
    assert c2.read_bytes() == b"keep-me"
    # سجل الدفعة/العنصر محفوظ (استرجاع staging فقط، مش حذف السجل).
    batch = db.get_attachment_batch("b1")
    assert batch is not None and batch.status == "expired"
    items = db.list_attachment_items("b1")
    assert len(items) == 1 and items[0].status == "reaped"


# ================================================ 8) الملفات اليتيمة
def test_orphan_file_counts_toward_limit_and_is_never_deleted(tmp_path):
    """ملف يتيم بيُحسب في السقف الكلي، وما بيتحذفش حتى بعد الكنس."""
    db, store = make_store(tmp_path, max_total_bytes=100)
    add_batch(db)
    store.ensure_root()
    orphan = store.root / ("d" * 32)
    _sparse(orphan, 100)

    rejected = _store(db, store, "i1", b"x")
    assert rejected.status is StageStatus.REJECTED_QUOTA
    assert orphan.exists() and orphan.stat().st_size == 100

    _reaper(db, tmp_path).sweep(now=EXPIRED_AT)
    assert orphan.exists()
    assert staging_total_bytes(store.root) == 100


# ================================================ 9) بلا مخطّط/سجل حجز
def test_no_schema_migration_or_reservation_ledger():
    """26 جدولًا (R2/R5/R6 أضافوا جداول المراجعة)، ومفيش سجل حجز في وحدة المرفقات."""
    source = pathlib.Path(attachments_mod.__file__).read_text(encoding="utf-8")
    for banned in ("reserve", "reservation", "release_reservation", "reserved_bytes"):
        assert banned not in source, f"ظهر عنصر سجل حجز ممنوع: {banned}"

    db_source = pathlib.Path(db_module.__file__).read_text(encoding="utf-8")
    tables = set(re.findall(r"CREATE TABLE IF NOT EXISTS ([a-z_]+)", db_source))
    assert len(tables) == 26, f"عدد الجداول اتغيّر: {sorted(tables)}"
    assert {
        "auto_reviews",
        "auto_review_provider_snapshots",
        "auto_review_memberships",
        "auto_review_stages",
        "auto_review_evidence",
        "auto_review_leases",
        "auto_review_reports",
        "auto_review_owner_acceptance",
    } <= tables
