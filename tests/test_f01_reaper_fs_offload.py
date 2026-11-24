"""F-01 — حذف البايتات (`_remove_file`) لازم يتنفّذ على خيط عامل، مش خيط الحلقة.

المراجعة المستقلة Batch 03 (F-01) أثبتت إن `_sweep_db_phase` كان بينادي `_remove_file`
(`os.lstat` + `os.unlink`) على خيط الحلقة، فالكنسة كانت بتحجب الحلقة لكل ملف. التيستات
دي بتجسّس **`_remove_file` نفسه** (مش `_sweep_fs_tail` بس) وبتفشل لو الحذف رجع تاني
جوه طور القاعدة.

المبدأ: مفيش `sleep` عشوائي — التزامن عبر `threading.Event`/`anyio`، والخيوط محدّدة.
"""

import asyncio
import os
import threading
from datetime import datetime, timezone

from bot.attachments import AttachmentReaper, OpportunisticSweeper
from bot.db import ATTACHMENT_BATCH_DELIVERED, ATTACHMENT_ITEM_STORED, Database

OWNER_ID = 111
CID = "11111111222233334444555566667777"
T0 = "2026-11-11T00:00:00+00:00"
NOW = "2026-11-19T00:00:00+00:00"
_TEST_NOW = datetime(2026, 11, 11, 0, 5, tzinfo=timezone.utc)


def make_reaper(tmp_path, *, items=1):
    """يبني دفعة نهائية (`delivered`) فيها `items` بايتات مخزّنة فعلًا على القرص."""
    from bot.attachments import StagingStore

    db_path = str(tmp_path / "state.sqlite3")
    db = Database(db_path)
    store = StagingStore(db, db_path, clock=lambda: _TEST_NOW)
    db.create_attachment_batch("b1", OWNER_ID, CID, T0)
    store.ensure_root()

    async def fill():
        for n in range(items):
            await store.store_async(
                telegram_id=OWNER_ID, batch_id="b1", item_id=f"i{n}",
                display_name=f"f{n}.txt", chunks=[b"hello"],
            )

    asyncio.run(fill())
    db.mark_attachment_batch_status("b1", ATTACHMENT_BATCH_DELIVERED, now=NOW)
    return db, store, AttachmentReaper(db, store.root)


def sweep(reaper, *, now=NOW):
    from datetime import datetime, timezone

    dt = datetime.fromisoformat(now).replace(tzinfo=timezone.utc)
    return asyncio.run(reaper.sweep_async(now=dt))


def test_F01_remove_file_runs_on_worker_thread(tmp_path):
    """F-01 (الأساس): كل نداء `_remove_file` بيتنفّذ على خيط **مش** خيط الحلقة."""
    db, store, reaper = make_reaper(tmp_path, items=3)
    loop_thread = threading.get_ident()
    seen: list[int] = []
    real = reaper._remove_file

    def spy(token):
        seen.append(threading.get_ident())
        return real(token)

    reaper._remove_file = spy

    rep = sweep(reaper)

    assert seen, "`_remove_file` مااتناداش خالص ⇒ التيست مش بيقيس اللي بيدّعي"
    assert all(t != loop_thread for t in seen), (
        f"حذف بايتات على خيط الحلقة: {seen.count(loop_thread)}/{len(seen)} (F-01)"
    )
    assert rep.files_deleted == 3


def test_F01_os_lstat_and_unlink_run_off_loop(tmp_path, monkeypatch):
    """F-01: `os.lstat` و `os.unlink` (العمليات الفعلية) ما بيتنفّذوش على خيط الحلقة."""
    db, store, reaper = make_reaper(tmp_path, items=2)
    loop_thread = threading.get_ident()
    on_loop = {"lstat": 0, "unlink": 0}
    real_lstat, real_unlink = os.lstat, os.unlink

    def lstat(p):
        if threading.get_ident() == loop_thread:
            on_loop["lstat"] += 1
        return real_lstat(p)

    def unlink(p):
        if threading.get_ident() == loop_thread:
            on_loop["unlink"] += 1
        return real_unlink(p)

    monkeypatch.setattr(os, "lstat", lstat)
    monkeypatch.setattr(os, "unlink", unlink)

    rep = sweep(reaper)

    assert rep.files_deleted == 2
    assert on_loop["lstat"] == 0, f"os.lstat على خيط الحلقة ×{on_loop['lstat']} (F-01)"
    assert on_loop["unlink"] == 0, f"os.unlink على خيط الحلقة ×{on_loop['unlink']} (F-01)"


def test_F01_no_filesystem_syscall_on_loop_during_sweep(tmp_path, monkeypatch):
    """F-01 (شامل): مفيش أي `lstat`/`unlink`/`open`/`iterdir` على خيط الحلقة في كنسة كاملة."""
    db, store, reaper = make_reaper(tmp_path, items=4)
    (store.root / "untracked").write_bytes(b"orphan")
    loop_thread = threading.get_ident()
    hits = {"lstat": 0, "unlink": 0, "open": 0, "iterdir": 0}

    real = {"lstat": os.lstat, "unlink": os.unlink, "open": os.open}
    for name, fn in real.items():
        def make(fn=fn, name=name):
            def wrapper(*a, **k):
                if threading.get_ident() == loop_thread:
                    hits[name] += 1
                return fn(*a, **k)
            return wrapper
        monkeypatch.setattr(os, name, make())

    from pathlib import Path

    real_iterdir = Path.iterdir

    def iterdir(self):
        if threading.get_ident() == loop_thread:
            hits["iterdir"] += 1
        return real_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", iterdir)

    rep = sweep(reaper)

    assert rep.files_deleted == 4
    assert hits == {"lstat": 0, "unlink": 0, "open": 0, "iterdir": 0}, (
        f"عمليات قرص على خيط الحلقة: {hits} (F-01)"
    )


def test_F01_mutation_remove_file_back_in_db_phase_is_detected(tmp_path):
    """F-01 (طفرة): لو رجّعنا `_remove_file` جوه طور القاعدة، التيست لازم يفشل.

    بيثبت إن التيست بيكشف العيب الأصلي بالتحديد — مش بس إن `_sweep_fs_tail` في خيط عامل.
    """
    db, store, reaper = make_reaper(tmp_path, items=2)
    loop_thread = threading.get_ident()
    seen: list[int] = []
    real = reaper._remove_file

    def spy(token):
        seen.append(threading.get_ident())
        return real(token)

    reaper._remove_file = spy

    # طفرة: نخلّي طور القاعدة ينفّذ الحذف بنفسه (السلوك المعطوب الأصلي).
    real_plan_batch = reaper._plan_batch

    def mutant_plan_batch(batch, known_tokens, plan):
        before = len(plan.cleanups)
        real_plan_batch(batch, known_tokens, plan)
        for cleanup in plan.cleanups[before:]:
            reaper._remove_file(cleanup.token)  # عبر spy ⇒ حذف على خيط الحلقة = F-01
        del plan.cleanups[before:]

    reaper._plan_batch = mutant_plan_batch

    sweep(reaper)

    assert seen, "الطفرة مااتنفّذتش ⇒ التيست مش بيثبت حاجة"
    on_loop = seen.count(loop_thread)
    assert on_loop > 0, (
        "التيست ما كشفش الطفرة: الحذف اتنفّذ على خيط الحلقة والمفروض يفشل هنا (F-01)"
    )


def test_F01_db_phase_performs_no_file_deletion(tmp_path):
    """F-01: طور القاعدة (`_sweep_db_phase`) ما بينادي `_remove_file` خالص."""
    db, store, reaper = make_reaper(tmp_path, items=3)
    calls: list[str] = []
    real = reaper._remove_file

    def spy(token):
        calls.append("x")
        return real(token)

    reaper._remove_file = spy

    report, known, plan = reaper._new_sweep_report()
    ok = reaper._sweep_db_phase(NOW, report, known, plan)

    assert ok is True
    assert calls == [], "طور القاعدة نفّذ حذف بايتات (F-01)"
    # القرارات اتاخدت (وسم reaped) والحذف اتجدول بس.
    assert len(plan.cleanups) == 3
    items = db.list_attachment_items("b1")
    assert all(it.status == "reaped" for it in items)


def test_F01_db_phase_marks_reaped_before_any_deletion(tmp_path):
    """F-01 (ترتيب): الوسم `reaped` (قرار القاعدة) بيحصل **قبل** أي حذف بايتات."""
    db, store, reaper = make_reaper(tmp_path, items=2)
    order: list[str] = []
    real_remove = reaper._remove_file
    real_mark = db.mark_attachment_item_reaped

    def mark(item_id):
        order.append("db_mark")
        return real_mark(item_id)

    def remove(token):
        order.append("fs_delete")
        return real_remove(token)

    db.mark_attachment_item_reaped = mark
    reaper._remove_file = remove

    rep = sweep(reaper)

    assert rep.files_deleted == 2
    assert order, "مافيش أحداث اتسجّلت"
    first_delete = order.index("fs_delete")
    assert "db_mark" in order[:first_delete], (
        f"حذف قبل قرار القاعدة: {order} (F-01 ترتيب)"
    )


def test_F01_startup_path_uses_safe_async_sweep(tmp_path):
    """F-01: مسار الإقلاع (`sweep_async` زي `bot/app.py`) بيحذف على خيط عامل."""
    db, store, reaper = make_reaper(tmp_path, items=2)
    loop_thread = threading.get_ident()
    seen: list[int] = []
    real = reaper._remove_file

    def spy(token):
        seen.append(threading.get_ident())
        return real(token)

    reaper._remove_file = spy

    from datetime import datetime, timezone

    asyncio.run(reaper.sweep_async(now=datetime.now(timezone.utc)))

    assert seen and all(t != loop_thread for t in seen)


def test_F01_watcher_path_uses_safe_async_sweep(tmp_path):
    """F-01: مسار tick المراقب (`maybe_sweep_async` زي `bot/watcher.py`) بيحذف برّه الحلقة."""
    db, store, reaper = make_reaper(tmp_path, items=2)
    sweeper = OpportunisticSweeper(reaper, min_interval=0.0, clock=lambda: 1000.0)
    loop_thread = threading.get_ident()
    seen: list[int] = []
    real = reaper._remove_file

    def spy(token):
        seen.append(threading.get_ident())
        return real(token)

    reaper._remove_file = spy

    from datetime import datetime, timezone

    rep = asyncio.run(sweeper.maybe_sweep_async(now=datetime.now(timezone.utc)))

    assert rep is not None and rep.files_deleted == 2
    assert seen and all(t != loop_thread for t in seen)


def test_F01_sqlite_never_called_from_worker_thread(tmp_path):
    """F-01: ملكية SQLite محفوظة — مفيش نداء قاعدة من خيط العامل وقت الكنسة."""
    db, store, reaper = make_reaper(tmp_path, items=3)
    loop_thread = threading.get_ident()
    off_loop: list[str] = []
    real_mark = db.mark_attachment_item_reaped

    def mark(item_id):
        if threading.get_ident() != loop_thread:
            off_loop.append("mark_attachment_item_reaped")
        return real_mark(item_id)

    db.mark_attachment_item_reaped = mark

    rep = sweep(reaper)

    assert rep.files_deleted == 3
    assert off_loop == [], f"نداءات قاعدة من خيط عامل: {off_loop}"


def test_F01_missing_file_is_absent_and_idempotent(tmp_path):
    """F-01: ملف مفقود ⇒ `absent` (نجاح idempotent)، والكنسة المتكرّرة آمنة.

    ملاحظة: `absent` ⇒ `CLEANED` (reconciled) هو سلوك **سابق** محفوظ حرفيًّا، مش تغيير.
    """
    db, store, reaper = make_reaper(tmp_path, items=1)
    # احذف البايتات يدويًا (محاكاة فشل/فقد) قبل الكنسة.
    for entry in list(store.root.iterdir()):
        entry.unlink()

    rep1 = sweep(reaper)
    assert rep1.files_deleted == 0
    assert rep1.cleaned == 1  # reconciled (absent) ⇒ دفعة منظّفة (سلوك سابق)
    assert rep1.errors == 0 and rep1.retry == 0

    # كنسة تانية: العنصر مكنوس سابقًا وبايتاته غايبة ⇒ لسه `absent`، بلا أخطاء/حذف.
    rep2 = sweep(reaper)
    assert rep2.files_deleted == 0
    assert rep2.errors == 0 and rep2.retry == 0
    assert rep2.cleaned == 1  # نفس دلالة `absent` السابقة — آمنة ومتكرّرة


def test_F01_filesystem_error_maps_to_retry(tmp_path, monkeypatch):
    """F-01: فشل حذف (OSError) ⇒ `retry` (مش نجاح كاذب)، والملف يفضل."""
    db, store, reaper = make_reaper(tmp_path, items=1)
    real_unlink = os.unlink

    def boom(p):
        if str(p).startswith(str(store.root)):
            raise OSError("simulated unlink failure")
        return real_unlink(p)

    monkeypatch.setattr(os, "unlink", boom)

    rep = sweep(reaper)

    assert rep.files_deleted == 0
    assert rep.retry >= 1, "فشل الحذف مااتسجّلش كإعادة محاولة"
    assert len(list(store.root.iterdir())) == 1, "الملف اتشال رغم فشل الحذف"


def test_F01_database_error_maps_to_retry_and_no_deletion(tmp_path):
    """F-01: فشل الوسم في القاعدة ⇒ `retry` وبلا حذف بايتات (fail-closed)."""
    db, store, reaper = make_reaper(tmp_path, items=1)

    def boom(_item_id):
        raise RuntimeError("db mark failure")

    db.mark_attachment_item_reaped = boom

    rep = sweep(reaper)

    assert rep.retry >= 1
    assert rep.files_deleted == 0
    assert len(list(store.root.iterdir())) == 1, "حذف بايتات رغم فشل قرار القاعدة"


def test_F01_orphan_cleanup_also_off_loop(tmp_path):
    """F-01: العناصر اليتيمة (بلا دفعة) بتتحذف برّه الحلقة كمان."""
    db, store, reaper = make_reaper(tmp_path, items=1)
    db._conn.execute("PRAGMA foreign_keys=OFF")
    db.add_attachment_item(
        "i_orphan", "missing-batch", staging_token="a" * 32,
        display_name="n.txt", size_bytes=1, status=ATTACHMENT_ITEM_STORED,
    )
    db._conn.execute("PRAGMA foreign_keys=ON")
    loop_thread = threading.get_ident()
    seen: list[int] = []
    real = reaper._remove_file

    def spy(token):
        seen.append(threading.get_ident())
        return real(token)

    reaper._remove_file = spy

    sweep(reaper)

    assert seen and all(t != loop_thread for t in seen), "حذف يتيم على خيط الحلقة (F-01)"
