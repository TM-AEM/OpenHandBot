"""DEF-011 — إثبات نقل الإدخال/الإخراج البحت خارج حلقة الأحداث + حدود الملكية.

يغطّي المصفوفة المعتمَدة (T-1 … T-14) كما هي قابلة للتطبيق بعد قرار
«التوائم الإضافية» (additive async twins) الموثّق في
`docs/reviews/OHB2-WP07-DEF011-PHASE1-DISCREPANCY-REPORT.md`:

- T-1/T-4: عمل القرص الحاجب ما بيحجبش حلقة الأحداث (نبض حلقة حتمي، بلا `sleep` عشوائي).
- T-2/T-3/T-8: عمليات القرص المعتمَدة بتتنفّذ فعلًا **خارج** خيط الحلقة.
- T-5/T-6: عمليات SQLite بتفضل على خيط مالك القاعدة، وما بتعبرش لخيط عامل.
- T-7/T-9/T-10: الإلغاء أثناء الكتابة، نشر الأخطاء، والتضارب.
- T-11/T-12: الحصص الافتراضية معطّلة (D-12) وعدد الجداول 17 (بلا تغيير مخطط).
- T-13/T-14: ازدواج التحديث ودلالات القبول بدون تغيير.

**بلا `sleep` عشوائي:** كل التزامن عبر `anyio.Event`/`threading.Event` وخيوط محدّدة.
"""

import asyncio
import threading
from datetime import datetime, timezone

import anyio
import pytest

from bot.attachments import (
    AttachmentReaper,
    OpportunisticSweeper,
    StageStatus,
    StagingStore,
)
from bot.db import Database

OWNER_ID = 111
CID = "11111111222233334444555566667777"
T0 = "2026-11-11T00:00:00+00:00"
_TEST_NOW = datetime(2026, 11, 11, 0, 5, tzinfo=timezone.utc)


def make_store(tmp_path, **kw):
    db_path = str(tmp_path / "state.sqlite3")
    db = Database(db_path)
    kw.setdefault("clock", lambda: _TEST_NOW)
    return db, StagingStore(db, db_path, **kw)


def make_store_in(parent, name, **kw):
    target = parent / name
    target.mkdir(parents=True, exist_ok=True)
    return make_store(target, **kw)


def add_batch(db, batch_id="b1"):
    db.create_attachment_batch(batch_id, OWNER_ID, CID, T0)


def _store_kwargs(**over):
    kw = dict(
        telegram_id=OWNER_ID, batch_id="b1", item_id="i1",
        display_name="note.txt", chunks=[b"hello"],
    )
    kw.update(over)
    return kw


# --------------------------------------------------------------------------
# T-2 / T-3 / T-8 — عمليات القرص المعتمَدة خارج خيط الحلقة
# --------------------------------------------------------------------------
def test_T2_store_async_write_runs_off_event_loop_thread(tmp_path):
    """T-2: الكتابة الفعلية بتتنفّذ على خيط **غير** خيط الحلقة."""
    db, store = make_store(tmp_path)
    add_batch(db)

    loop_thread = threading.get_ident()
    seen: list[int] = []
    real_write = store._write_to_path

    def spy(path, chunks, cap):
        seen.append(threading.get_ident())
        return real_write(path, chunks, cap)

    store._write_to_path = spy

    async def run():
        return await store.store_async(**_store_kwargs())

    res = asyncio.run(run())
    assert res.status is StageStatus.STORED
    assert len(seen) == 1
    assert seen[0] != loop_thread, "الكتابة اتنفّذت على خيط الحلقة ⇒ مفيش نقل"


def test_T3_sync_store_path_stays_on_calling_thread(tmp_path):
    """T-3 (ضابط): المسار المتزامن التاريخي بيفضل على خيط المتصل (سلوك محفوظ)."""
    db, store = make_store(tmp_path)
    add_batch(db)
    seen: list[int] = []
    real_write = store._write_to_path

    def spy(path, chunks, cap):
        seen.append(threading.get_ident())
        return real_write(path, chunks, cap)

    store._write_to_path = spy
    res = store.store(**_store_kwargs())
    assert res.status is StageStatus.STORED
    assert seen == [threading.get_ident()]


def test_T8_store_async_reads_head_off_loop_thread(tmp_path):
    """T-8: قراءة البصمة (`_read_head`) بتتنفّذ برضه خارج خيط الحلقة."""
    import bot.attachments as att

    db, store = make_store(tmp_path)
    add_batch(db)

    loop_thread = threading.get_ident()
    seen: list[int] = []
    real_head = att._read_head

    def spy(path):
        seen.append(threading.get_ident())
        return real_head(path)

    att._read_head = spy
    try:
        async def run():
            return await store.store_async(**_store_kwargs())

        res = asyncio.run(run())
    finally:
        att._read_head = real_head

    assert res.status is StageStatus.STORED
    assert seen and all(t != loop_thread for t in seen)


# --------------------------------------------------------------------------
# T-1 / T-4 — الحلقة ما بتتحجبش (نبض حتمي)
# --------------------------------------------------------------------------
def test_T1_event_loop_stays_responsive_during_large_write(tmp_path):
    """T-1: أثناء كتابة 3 MiB، مهمة نبض على الحلقة بتفضل تتنفّذ (مش متجمّدة)."""
    db, store = make_store(tmp_path)
    add_batch(db)

    payload = b"x" * (3 * 1024 * 1024)
    ticks = {"n": 0}

    async def run():
        stop = anyio.Event()

        async def heartbeat():
            # نبض حتمي: بينبض لحد ما الكتابة تخلص. لو الحلقة اتحجبت، `n` هيفضل صفر
            # (مفيش `sleep` عشوائي — الحدث بيتفتح بعد الكتابة).
            while not stop.is_set():
                ticks["n"] += 1
                await anyio.sleep(0)

        async with anyio.create_task_group() as tg:
            tg.start_soon(heartbeat)
            res = await store.store_async(**_store_kwargs(chunks=[payload]))
            stop.set()
        return res

    res = asyncio.run(run())
    assert res.status is StageStatus.STORED
    assert res.size_bytes == len(payload)
    assert ticks["n"] > 0, "الحلقة ما نبضتش خالص ⇒ اتحجبت"


def test_T4_sweep_async_filesystem_tail_off_loop_thread(tmp_path):
    """T-4: مسح الجذر في الكنسة بيتنفّذ خارج خيط الحلقة، والكنسة تفضل صحيحة."""
    db, store = make_store(tmp_path)
    add_batch(db)
    root = store.ensure_root()
    (root / "untracked_file").write_bytes(b"orphan")

    reaper = AttachmentReaper(db, store.root)
    loop_thread = threading.get_ident()
    seen: list[int] = []
    real_tail = reaper._sweep_fs_tail

    def spy(known, report, plan):
        seen.append(threading.get_ident())
        return real_tail(known, report, plan)

    reaper._sweep_fs_tail = spy

    from datetime import datetime, timezone

    async def run():
        return await reaper.sweep_async(now=datetime.now(timezone.utc))

    rep = asyncio.run(run())
    assert seen and seen[0] != loop_thread
    assert rep.untracked_left >= 1


def test_T4b_maybe_sweep_async_offloads_and_keeps_throttle(tmp_path):
    """T-4b: الغلاف `maybe_sweep_async` بينقل المسح ويحافظ على الخنق/النجاح."""
    db, store = make_store(tmp_path)
    add_batch(db)
    reaper = AttachmentReaper(db, store.root)
    clock = {"t": 100.0}
    sweeper = OpportunisticSweeper(reaper, min_interval=10.0, clock=lambda: clock["t"])

    from datetime import datetime, timezone

    async def run():
        first = await sweeper.maybe_sweep_async(now=datetime.now(timezone.utc))
        second = await sweeper.maybe_sweep_async(now=datetime.now(timezone.utc))
        clock["t"] += 11.0
        third = await sweeper.maybe_sweep_async(now=datetime.now(timezone.utc))
        return first, second, third

    first, second, third = asyncio.run(run())
    assert first is not None          # الأولى اشتغلت
    assert second is None             # مخنوقة داخل النافذة
    assert third is not None          # مؤهّلة بعد النافذة
    assert sweeper.last_success_at is not None


# --------------------------------------------------------------------------
# T-5 / T-6 — ملكية SQLite محفوظة
# --------------------------------------------------------------------------
def test_T5_sqlite_calls_stay_on_loop_thread_during_store_async(tmp_path):
    """T-5: كل نداءات قاعدة البيانات أثناء `store_async` بتحصل على خيط الحلقة."""
    db, store = make_store(tmp_path)
    add_batch(db)

    loop_thread = threading.get_ident()
    db_threads: list[int] = []
    real_mark = db.try_mark_attachment_item_stored

    def spy(*a, **kw):
        db_threads.append(threading.get_ident())
        return real_mark(*a, **kw)

    db.try_mark_attachment_item_stored = spy

    async def run():
        return await store.store_async(**_store_kwargs())

    res = asyncio.run(run())
    assert res.status is StageStatus.STORED
    assert db_threads, "مافيش نداء قاعدة اتسجّل"
    assert all(t == loop_thread for t in db_threads), (
        "نداء قاعدة حصل على خيط عامل ⇒ خرق حدود الملكية"
    )


def test_T6_no_database_object_crosses_to_worker_thread(tmp_path):
    """T-6: الخيط العامل ما بيمسكش `_db`/`_conn` — الوظيفة المنقولة بتاخد مسار/بايتات بس."""
    db, store = make_store(tmp_path)
    add_batch(db)

    captured = {}

    def fake_write(path, chunks, cap):
        # نسجّل ما هو متاح للخيط العامل: لازم يكون مسار/قطع/سقف فقط.
        captured["args"] = (type(path).__name__, cap)
        captured["has_db"] = hasattr(store, "_db")
        return 0  # صفر بايت ⇒ رفض نظيف بلا كتابة

    store._write_to_path = fake_write

    async def run():
        return await store.store_async(**_store_kwargs())

    res = asyncio.run(run())
    # الوظيفة المنقولة بتاخد مسار/سقف فقط؛ مفيش تمرير لكائن القاعدة.
    assert captured["args"][0] == "PosixPath"
    assert isinstance(captured["args"][1], int)
    assert res.status is StageStatus.REJECTED_EMPTY


def test_T6b_worker_function_receives_no_db_reference(tmp_path):
    """T-6b: التحقّق من توقيع دالة الكتابة المنقولة — بلا أي وسيط قاعدة بيانات."""
    import inspect

    params = set(inspect.signature(StagingStore._store_write).parameters)
    assert params == {"self", "path", "chunks", "cap", "item_id", "token"}
    assert "db" not in params and "_db" not in params


# --------------------------------------------------------------------------
# T-7 / T-9 / T-10 — الإلغاء، نشر الأخطاء، التضارب
# --------------------------------------------------------------------------
def test_T7_cancel_during_write_never_claims_stored(tmp_path):
    """T-7: إلغاء المهمة أثناء الكتابة ⇒ **مافيش ادّعاء `stored`**، والعنصر يفضل
    `pending`، والكنسة بتحصده لاحقًا (`pending → reaped` + حذف الملف) — تعافي مصمَّم.

    ده نفس مسار «انهيار بين الكتابة والوسم» بالظبط: القرار النهائي (`_store_finalize`)
    ما اتنفّذش ⇒ مفيش صف `stored`، والكنس (A4) هو المسؤول عن التحصيل، **مش** حذف صامت
    وقت الإلغاء (شوف `test_case12_orphan_filesystem_file_preserved`).

    **F-02 (مقوّى):** الاختبار بيتحقّق كمان من **ملكية القفل** ومن **عدم تداخل الكُتّاب**،
    مش بس غياب حالة `stored`. الإلغاء الخام (`Task.cancel`) ما بيحرّرش `_accept_lock`
    قبل ما العامل يخلص، وعدد الكُتّاب المتزامنين بيفضل **1**.
    """
    db, store = make_store(tmp_path)
    add_batch(db)
    root = store.ensure_root()

    started = threading.Event()
    release = threading.Event()
    guard = threading.Lock()
    state = {"active": 0, "max_concurrent": 0, "lock_held_after_cancel": None}

    def slow_write(path, chunks, cap):
        with guard:
            state["active"] += 1
            state["max_concurrent"] = max(state["max_concurrent"], state["active"])
        try:
            started.set()
            release.wait(timeout=10)
            with open(path, "wb") as fh:
                fh.write(b"partial")
            return 7
        finally:
            with guard:
                state["active"] -= 1

    store._write_to_path = slow_write

    async def run():
        task = asyncio.ensure_future(store.store_async(**_store_kwargs()))
        while not started.is_set():
            await anyio.sleep(0)
        task.cancel()
        # نمنح الحلقة فرصة كي يُسلَّم الإلغاء فعلًا قبل فحص القفل (وإلا فالفحص سابق لأوانه).
        for _ in range(20):
            await anyio.sleep(0)
        # F-02: بعد الإلغاء الخام المُسلَّم لازم القفل يفضل محتجز لأن العامل لسه بيكتب.
        state["lock_held_after_cancel"] = store._accept_lock.locked()
        # العامل لازم يخلص قبل ما الإلغاء ينتشر ⇒ نفكّه ثم ننتظر المهمة.
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        state["lock_after"] = store._accept_lock.locked()

    asyncio.run(run())
    # 0) F-02: القفل محتجز لحظة الإلغاء، والكاتب المتزامن الأقصى = 1.
    assert state["lock_held_after_cancel"] is True, "القفل اتحرّر قبل ما العامل يخلص"
    assert state["lock_after"] is False, "القفل ما اتحرّرش بعد انتهاء العامل"
    assert state["max_concurrent"] == 1, "أكتر من كاتب واحد في القسم الحرج"
    # 1) الضمانة الأساسية: مفيش عنصر اتوسم `stored` رغم إلغاء الكتابة.
    items = db.list_attachment_items("b1")
    assert [it for it in items if it.status == "stored"] == [], "ادّعاء stored رغم الإلغاء"
    assert [it.status for it in items] == ["pending"], "الحالة اتغيّرت رغم الإلغاء"
    # 2) البايتات اليتيمة موجودة (الخيط العامل كمّل) — الكنس هو المسؤول عنها.
    assert list(root.iterdir()), "متوقّع ملف يتيم بعد الإلغاء"

    # 3) الكنس يحصدها: `pending → reaped` والملف يتحذف (تعافي مصمَّم، مش تسرّب).
    from datetime import datetime, timezone

    rep = AttachmentReaper(db, store.root).sweep(now=datetime.now(timezone.utc))
    assert rep.cleaned >= 1, "الكنس ما حصدش العنصر المعلّق"
    assert list(root.iterdir()) == [], "ملف يتيم اتبقّى بعد الكنس"
    assert db.get_attachment_item("i1").status == "reaped"


def test_T9_oserror_maps_to_write_failed(tmp_path):
    """T-9: `OSError` جوه الخيط العامل ⇒ `WRITE_FAILED` (عقد الخطأ محفوظ)."""
    db, store = make_store(tmp_path)
    add_batch(db)

    def boom(path, chunks, cap):
        raise OSError("disk on fire")

    store._write_to_path = boom

    async def run():
        return await store.store_async(**_store_kwargs())

    res = asyncio.run(run())
    assert res.status is StageStatus.WRITE_FAILED
    assert res.error == "OSError"


def test_T10_collision_still_rejected(tmp_path):
    """T-10: تصادم `O_EXCL` ⇒ `WRITE_FAILED` بسبب `collision` (محفوظ)."""
    from bot.attachments import _CollisionError

    db, store = make_store(tmp_path)
    add_batch(db)

    def collide(path, chunks, cap):
        raise _CollisionError()

    store._write_to_path = collide

    async def run():
        return await store.store_async(**_store_kwargs())

    res = asyncio.run(run())
    assert res.status is StageStatus.WRITE_FAILED
    assert res.error == "collision"


def test_T10b_size_limit_still_enforced(tmp_path):
    """T-10b: سقف الملف (3 MiB) لسه مفروض على المسار المنقول."""
    from bot.attachments import MAX_ATTACHMENT_BYTES

    db, store = make_store(tmp_path)
    add_batch(db)

    too_big = b"x" * (MAX_ATTACHMENT_BYTES + 1)

    async def run():
        return await store.store_async(**_store_kwargs(chunks=[too_big]))

    res = asyncio.run(run())
    assert res.status in (StageStatus.REJECTED_SIZE, StageStatus.REJECTED_QUOTA)
    assert list(store.root.iterdir()) == []


# --------------------------------------------------------------------------
# T-11 / T-12 — D-12 كما هي، والمخطط بلا تغيير
# --------------------------------------------------------------------------
def test_T11_aggregate_quotas_remain_disabled_by_default(tmp_path):
    """T-11: الحصص التجميعية لسه معطّلة افتراضيًّا (D-12 محفوظ، مفيش سجل حجز)."""
    db, store = make_store(tmp_path)
    assert store.quota_enabled is False
    assert store._max_items_per_batch is None
    assert store._max_total_bytes is None
    assert store._max_bytes_per_batch is None


def test_T11b_no_reservation_ledger_introduced():
    """T-11b: مفيش أي سجل حجز/تحفّظ حصص اتضاف للوحدة."""
    import bot.attachments as att

    src = open(att.__file__, encoding="utf-8").read()
    for banned in ("reserve", "reservation", "release_reservation", "reserved_bytes"):
        assert banned not in src, f"ظهر عنصر سجل حجز ممنوع: {banned}"


def test_T12_schema_table_count_unchanged():
    """T-12: عدد الجداول 17 — مفيش تغيير مخطط."""
    import bot.db as dbmod

    src = open(dbmod.__file__, encoding="utf-8").read()
    import re

    tables = set(re.findall(r"CREATE TABLE IF NOT EXISTS ([a-z_]+)", src))
    assert len(tables) == 17, f"عدد الجداول اتغيّر: {sorted(tables)}"


# --------------------------------------------------------------------------
# T-13 / T-14 — دلالات القبول بدون تغيير
# --------------------------------------------------------------------------
def test_T13_store_async_matches_sync_result_exactly(tmp_path):
    """T-13: نفس المدخلات ⇒ نفس النتيجة على المسارين (تكافؤ سلوكي)."""
    db1, store1 = make_store_in(tmp_path, "a")
    db2, store2 = make_store_in(tmp_path, "b")
    add_batch(db1)
    add_batch(db2)

    sync_res = store1.store(**_store_kwargs(chunks=[b"abc"]))
    async_res = asyncio.run(store2.store_async(**_store_kwargs(chunks=[b"abc"])))

    assert sync_res.status is async_res.status is StageStatus.STORED
    assert sync_res.size_bytes == async_res.size_bytes == 3
    # البايتات المكتوبة مطابقة.
    assert (store1.root / sync_res.staging_token).read_bytes() == b"abc"
    assert (store2.root / async_res.staging_token).read_bytes() == b"abc"


def test_T13b_store_async_rejects_unknown_batch_like_sync(tmp_path):
    """T-13b: دفعة غير موجودة ⇒ `REJECTED_BATCH` على المسارين."""
    db, store = make_store(tmp_path)
    async_res = asyncio.run(store.store_async(**_store_kwargs(batch_id="ghost")))
    sync_res = store.store(**_store_kwargs(batch_id="ghost"))
    assert async_res.status is StageStatus.REJECTED_BATCH
    assert sync_res.status is StageStatus.REJECTED_BATCH


def test_T14_store_async_serializes_concurrent_accepts(tmp_path):
    """T-14: القبول المتزامن ما بيتجاوزش السقف — نفس النموذج المتسلسل محفوظ."""
    db, store = make_store(tmp_path, max_items_per_batch=3)
    add_batch(db)

    async def run():
        tasks = [
            store.store_async(**_store_kwargs(item_id=f"i{n}", display_name=f"c{n}.txt",
                                              chunks=[b"x"]))
            for n in range(12)
        ]
        return await asyncio.gather(*tasks)

    results = asyncio.run(run())
    stored = sum(1 for r in results if r.status is StageStatus.STORED)
    rejected = sum(1 for r in results if r.status is StageStatus.REJECTED_QUOTA)
    assert stored == 3, f"تجاوز السقف: {stored} مخزَّن"
    assert rejected == 9
    assert len(list(store.root.iterdir())) == 3


# --------------------------------------------------------------------------
# F-02 — الإلغاء الخام ما بيحرّرش `_accept_lock` تحت كاتب شغّال
# --------------------------------------------------------------------------
class _WriterProbe:
    """كاتب مُجهَّز بأحداث مزامنة (بلا أي `sleep` للترتيب).

    بيسجّل أقصى عدد كُتّاب متزامنين، وبيعلّق كل استدعاء على `release`.
    """

    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()
        self._guard = threading.Lock()
        self._active = 0
        self.max_concurrent = 0
        self.calls = 0

    def __call__(self, path, chunks, cap):
        with self._guard:
            self.calls += 1
            self._active += 1
            self.max_concurrent = max(self.max_concurrent, self._active)
        try:
            self.started.set()
            self.release.wait(timeout=10)
            with open(path, "wb") as fh:
                fh.write(b"payload")
            return 7
        finally:
            with self._guard:
                self._active -= 1


def test_F02_lock_held_while_worker_writes_after_raw_cancel(tmp_path):
    """F-02: `asyncio.Task.cancel()` الخام أثناء الكتابة ما بيحرّرش `_accept_lock`.

    القبول الثاني **ما يقدرش** يدخل قسم الكتابة قبل ما العامل الأول يخلص،
    وعدد الكُتّاب المتزامنين بيفضل **1** بالظبط.
    """
    db, store = make_store(tmp_path)
    add_batch(db)
    root = store.ensure_root()
    probe = _WriterProbe()
    store._write_to_path = probe

    observed = {}

    async def run():
        first = asyncio.ensure_future(
            store.store_async(**_store_kwargs(item_id="i1"))
        )
        while not probe.started.is_set():
            await anyio.sleep(0)

        # (1)(2) العامل الأول دخل واتعلّق جوه الكتابة ⇒ إلغاء خام للمهمة المستدعية.
        first.cancel()
        # (3)(4) العامل لسه شغّال والقفل لازم يفضل محتجز.
        observed["lock_held"] = store._accept_lock.locked()
        observed["worker_active"] = probe.max_concurrent

        # (5) قبول ثانٍ أثناء بقاء العامل الأول شغّال.
        second = asyncio.ensure_future(
            store.store_async(**_store_kwargs(item_id="i2"))
        )
        # نمنح الحلقة فرصة حقيقية كي يدخل الثاني لو القفل كان متحرّرًا.
        for _ in range(50):
            await anyio.sleep(0)
        observed["second_blocked"] = not second.done()

        # (6) نُفرج عن العامل الأول؛ (7) الإلغاء ينتشر بعد ما العامل يخلص.
        probe.release.set()
        with pytest.raises(asyncio.CancelledError):
            await first

        # (8)(9) القبول الثاني يكمل بعد ما الأول خلص — كاتب واحد فقط في أي لحظة.
        result2 = await second
        observed["second_status"] = result2.status
        observed["max_concurrent"] = probe.max_concurrent
        return result2

    result2 = asyncio.run(run())

    # (3)(4) القفل محتجز رغم الإلغاء الخام.
    assert observed["lock_held"] is True, "القفل اتحرّر والعامل لسه بيكتب"
    assert observed["worker_active"] == 1
    # (5) القبول الثاني ما دخلش القسم الحرج prematurely.
    assert observed["second_blocked"] is True, "القبول الثاني دخل قبل ما العامل الأول يخلص"
    # (8)(9) القبول الثاني نجح بعد كده، وكاتب واحد فقط في أي لحظة.
    assert observed["second_status"] is StageStatus.STORED
    assert observed["max_concurrent"] == 1, "أكتر من كاتب واحد متزامن"
    assert result2.status is StageStatus.STORED

    # (10) حالة نهائية متّسقة: عنصر `stored` واحد فقط، والعنصر المُلغي `pending`.
    items = db.list_attachment_items("b1")
    by_id = {it.item_id: it.status for it in items}
    assert by_id == {"i1": "pending", "i2": "stored"}
    # العامل الأول كمّل كتابته قبل ما الإلغاء ينتشر ⇒ ملفّه اليتيم موجود (تعافي بالكنس).
    orphan_token = db.get_attachment_item("i1").staging_token
    assert orphan_token in {p.name for p in root.iterdir()}

    # الكنس يحصد العنصر المعلّق وملفه اليتيم (تعافي مصمَّم، مش تسرّب).
    from datetime import datetime, timezone

    rep = AttachmentReaper(db, store.root).sweep(now=datetime.now(timezone.utc))
    assert rep.cleaned >= 1
    assert db.get_attachment_item("i1").status == "reaped"
    # ملف اليتيم بتاع i1 اتحصد تحديدًا.
    assert orphan_token not in {p.name for p in root.iterdir()}


def test_F02_worker_failure_after_cancel_releases_lock_and_never_stores(tmp_path):
    """F-02: فشل العامل **بعد** الإلغاء ⇒ القفل يتحرّر، ومفيش ادّعاء `stored`.

    العامل بيرمي `OSError` بعد الإلغاء؛ لازم الإلغاء ينتشر (مش الفشل)، والقفل
    يتحرّر في الآخر، والعنصر يفضل `pending` (fail closed).
    """
    db, store = make_store(tmp_path)
    add_batch(db)
    root = store.ensure_root()

    started = threading.Event()
    release = threading.Event()

    def failing_write(path, chunks, cap):
        started.set()
        release.wait(timeout=10)
        raise OSError("disk on fire after cancel")

    store._write_to_path = failing_write

    observed = {}

    async def run():
        task = asyncio.ensure_future(store.store_async(**_store_kwargs()))
        while not started.is_set():
            await anyio.sleep(0)
        task.cancel()
        for _ in range(20):
            await anyio.sleep(0)
        observed["lock_held"] = store._accept_lock.locked()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        observed["lock_after"] = store._accept_lock.locked()

    asyncio.run(run())

    assert observed["lock_held"] is True, "القفل اتحرّر قبل ما العامل يخلص"
    # الإلغاء انتشر، والقفل اتحرّر بعد ما العامل خلص (فشل) — مفيش تسريب قفل.
    assert observed["lock_after"] is False, "القفل ما اتحرّرش بعد انتهاء العامل"
    # fail closed: العنصر يفضل `pending`، ومفيش ملف جزئي باسم العنصر.
    assert db.get_attachment_item("i1").status == "pending"
    assert list(root.iterdir()) == [], "متوقّع عدم بقاء ملف جزئي بعد فشل العامل"


def test_F02_repeated_raw_cancel_keeps_single_writer(tmp_path):
    """F-02: إلغاءات خام متتالية مع قبول متزامن ⇒ كاتب واحد بس في أي لحظة، والقفل متّسق."""
    db, store = make_store(tmp_path)
    add_batch(db)
    probe = _WriterProbe()
    store._write_to_path = probe

    async def run():
        for n in range(3):
            probe.started.clear()
            probe.release.clear()
            victim = asyncio.ensure_future(
                store.store_async(**_store_kwargs(item_id=f"r{n}"))
            )
            while not probe.started.is_set():
                await anyio.sleep(0)
            victim.cancel()
            for _ in range(20):
                await anyio.sleep(0)
            # القفل لازم يفضل محتجز رغم الإلغاء الخام (العامل لسه جوّه الكتابة).
            assert store._accept_lock.locked() is True
            # قبول متزامن أثناء بقاء العامل شغّال ⇒ ما يقدرش يدخل قسم الكتابة.
            rival = asyncio.ensure_future(
                store.store_async(**_store_kwargs(item_id=f"s{n}"))
            )
            for _ in range(50):
                await anyio.sleep(0)
            assert rival.done() is False, "قبول متزامن دخل قبل ما العامل يخلص"
            # نُفرج؛ الإلغاء ينتشر بعد ما العامل يخلص، والقبول المتزامن يكمل بعده.
            probe.release.set()
            with pytest.raises(asyncio.CancelledError):
                await victim
            await rival
            assert store._accept_lock.locked() is False

    asyncio.run(run())
    assert probe.max_concurrent == 1, "أكتر من كاتب واحد متزامن"
    # العناصر المُلغاة فضلت `pending` (مفيش ادّعاء `stored` من إلغاء).
    items = {it.item_id: it.status for it in db.list_attachment_items("b1")}
    for n in range(3):
        assert items[f"r{n}"] == "pending"
        assert items[f"s{n}"] == "stored"


# --------------------------------------------------------------------------
# T-8b — مسار القراءة المحلية المقيّدة (bot/handlers.py)
# --------------------------------------------------------------------------
def test_T8b_local_capped_read_runs_off_event_loop_thread(tmp_path, monkeypatch):
    """T-8b: `_read_local_capped` بيتنفّذ خارج خيط الحلقة (مسار Bot API محلي)."""
    from types import SimpleNamespace

    from bot import handlers

    payload = b"local-bytes"
    local_file = tmp_path / "tg_local.bin"
    local_file.write_bytes(payload)

    loop_thread = threading.get_ident()
    seen: list[int] = []
    real_read = handlers._read_local_capped

    def spy(path, max_bytes):
        seen.append(threading.get_ident())
        return real_read(path, max_bytes)

    monkeypatch.setattr(handlers, "_read_local_capped", spy)

    class _Bot:
        async def get_file(self, file_id=None, **kw):
            return SimpleNamespace(file_path=str(local_file))

    ctx = SimpleNamespace(bot=_Bot())

    async def run():
        factory = await handlers._download_attachment_chunks(ctx, "f1", 1024)
        return b"".join(factory)

    out = asyncio.run(run())
    assert out == payload
    assert seen and all(t != loop_thread for t in seen), "القراءة حصلت على خيط الحلقة"


def test_T8c_local_capped_read_enforces_cap(tmp_path):
    """T-8c: سقف البايت لسه مفروض على المسار المنقول (رفض مغلق)."""
    from types import SimpleNamespace

    from bot import handlers
    from bot.attachments import AttachmentTooLargeError

    local_file = tmp_path / "big.bin"
    local_file.write_bytes(b"x" * 2048)

    class _Bot:
        async def get_file(self, file_id=None, **kw):
            return SimpleNamespace(file_path=str(local_file))

    ctx = SimpleNamespace(bot=_Bot())

    async def run():
        return await handlers._download_attachment_chunks(ctx, "f1", 1024)

    with pytest.raises(AttachmentTooLargeError):
        asyncio.run(run())


# ==========================================================================
# F-02 — انحدار الإلغاء قبل بدء العامل (atomic worker-start gate)
# ==========================================================================
# المشكلة: `anyio.to_thread.run_sync` بينفّذ checkpoint قبل إنشاء العامل، فإلغاء خام
# واحد ممكن يخلّي العامل ما يتنادىش خالص ⇒ انتظار إشارة إتمام لن تأتي ⇒ `_accept_lock`
# محتجز للأبد. الاختبارات دي بتغطي كل انتقالات دورة الحياة + حالات M1–M8.

_F02_TIMEOUT = 2.0


def _f02_make(tmp_path):
    db, store = make_store(tmp_path)
    add_batch(db)
    return db, store


def _f02_statuses(db):
    return [it.status for it in db.list_attachment_items("b1")]


def _f02_plain_writer(store, counter):
    """كاتب بسيط يعدّ النداءات (يثبت هل الكتابة حصلت فعلًا)."""

    def _w(path, chunks, cap):
        counter.append(1)
        with open(path, "wb") as fh:
            fh.write(b"x")
        return 1

    store._write_to_path = _w


def _f02_blocking_writer(store):
    """كاتب يحجب نفسه حتى يُفكّ، ويسجّل أقصى تزامن."""
    entered = threading.Event()
    release = threading.Event()
    state = {"active": 0, "max": 0, "writes": 0}
    guard = threading.Lock()

    def _w(path, chunks, cap):
        with guard:
            state["active"] += 1
            state["max"] = max(state["max"], state["active"])
            state["writes"] += 1
        try:
            entered.set()
            release.wait(timeout=10)
            with open(path, "wb") as fh:
                fh.write(b"p")
            return 7
        finally:
            with guard:
                state["active"] -= 1

    store._write_to_path = _w
    return entered, release, state


async def _f02_cancel_after_ticks(store, ticks, item_id="i1"):
    """يشغّل store_async ثم يلغي إلغاءً خامًا بعد `ticks` دورة حلقة.

    يرجّع (outcome, lock_held_after). outcome ∈ {completed, cancelled, HANG}.
    الانتظار محدود بـ`_F02_TIMEOUT` ⇒ لا تعليق للاختبار نفسه.
    """
    task = asyncio.ensure_future(store.store_async(**_store_kwargs(item_id=item_id)))
    for _ in range(ticks):
        await anyio.sleep(0)
    task.cancel()
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=_F02_TIMEOUT)
        outcome = "completed"
    except (asyncio.TimeoutError, TimeoutError):
        outcome = "HANG"
    except asyncio.CancelledError:
        outcome = "cancelled"
    return outcome, store._accept_lock.locked()


def _f02_cancel_then_finish(tmp_path, writer_factory):
    """يلغي أثناء الكتابة ثم يفكّ الكاتب لينتهي (نجاح أو استثناء)."""
    db, store = _f02_make(tmp_path)
    entered = threading.Event()
    release = threading.Event()

    def _w(path, chunks, cap):
        entered.set()
        release.wait(timeout=10)
        return writer_factory(path)

    store._write_to_path = _w

    async def run():
        task = asyncio.ensure_future(store.store_async(**_store_kwargs(item_id="i1")))
        while not entered.is_set():
            await anyio.sleep(0)
        task.cancel()
        for _ in range(10):
            await anyio.sleep(0)
        release.set()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=_F02_TIMEOUT)
        except asyncio.CancelledError:
            pass

    try:
        asyncio.run(run())
    finally:
        release.set()
    return db, store


# ---------------------------------------------------------------- 1 / 2 / 4
def test_f02_case01_cancel_before_submission(tmp_path):
    """1: إلغاء قبل التقديم ⇒ القفل يتحرّر، مفيش كتابة، مفيش stored."""
    db, store = _f02_make(tmp_path)
    writes = []
    _f02_plain_writer(store, writes)

    async def run():
        return await _f02_cancel_after_ticks(store, 0)

    outcome, held = asyncio.run(run())
    assert outcome == "cancelled", f"متوقّع cancelled، جاي {outcome}"
    assert held is False, "القفل فضل محتجز بعد إلغاء قبل التقديم"
    assert writes == [], "حصلت كتابة رغم الإلغاء قبل البدء"
    assert "stored" not in _f02_statuses(db), "ادّعاء stored رغم الإلغاء"


def test_f02_case02_cancel_at_initial_checkpoint(tmp_path):
    """2: إلغاء عند أول checkpoint في anyio ⇒ لا تعليق، القفل يتحرّر."""
    db, store = _f02_make(tmp_path)
    writes = []
    _f02_plain_writer(store, writes)

    async def run():
        return await _f02_cancel_after_ticks(store, 2)

    outcome, held = asyncio.run(run())
    assert outcome == "cancelled", f"متوقّع cancelled، جاي {outcome}"
    assert held is False, "القفل فضل محتجز بعد إلغاء عند الـcheckpoint"
    assert "stored" not in _f02_statuses(db)


def test_f02_case04_cancel_after_submission_before_worker(tmp_path):
    """4: إلغاء بعد التقديم وقبل تنفيذ العامل — عبر نطاق ticks.

    لكل tick: **ممنوع** التعليق. القفل يتحرّر دائمًا بعد الإرجاع، ومفيش `stored`.
    """
    for ticks in (2, 3, 4, 6, 8):
        sub = tmp_path / f"t{ticks}"
        sub.mkdir(parents=True, exist_ok=True)
        db, store = _f02_make(sub)
        writes = []
        _f02_plain_writer(store, writes)

        async def run(_s=store):
            return await _f02_cancel_after_ticks(_s, ticks)

        outcome, held = asyncio.run(run())
        assert outcome != "HANG", f"تعليق عند ticks={ticks} — الانحدار رجع"
        assert held is False, f"القفل محتجز بعد الإرجاع عند ticks={ticks}"
        assert "stored" not in _f02_statuses(db), f"stored رغم الإلغاء عند ticks={ticks}"


# ---------------------------------------------------------------- 3 (limiter)
def test_f02_case03_cancel_while_waiting_for_limiter(tmp_path):
    """3: إلغاء أثناء انتظار حدّ الخيوط (limiter) ⇒ لا تعليق، لا كتابة."""
    db, store = _f02_make(tmp_path)
    writes = []
    _f02_plain_writer(store, writes)
    from anyio import to_thread as _tt

    async def run():
        limiter = _tt.current_default_thread_limiter()
        original = limiter.total_tokens
        limiter.total_tokens = 1
        hog_release = threading.Event()
        hog_started = threading.Event()

        def hog():
            hog_started.set()
            hog_release.wait(timeout=10)

        hog_task = asyncio.ensure_future(_tt.run_sync(hog))
        try:
            while not hog_started.is_set():
                await anyio.sleep(0)
            task = asyncio.ensure_future(
                store.store_async(**_store_kwargs(item_id="i1"))
            )
            for _ in range(3):
                await anyio.sleep(0)
            task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=_F02_TIMEOUT)
                outcome = "completed"
            except (asyncio.TimeoutError, TimeoutError):
                outcome = "HANG"
            except asyncio.CancelledError:
                outcome = "cancelled"
            return outcome, store._accept_lock.locked()
        finally:
            hog_release.set()
            try:
                await asyncio.wait_for(asyncio.shield(hog_task), timeout=_F02_TIMEOUT)
            except Exception:
                pass
            limiter.total_tokens = original

    outcome, held = asyncio.run(run())
    assert outcome == "cancelled", f"متوقّع cancelled، جاي {outcome}"
    assert held is False, "القفل فضل محتجز بعد إلغاء أثناء انتظار الـlimiter"
    assert writes == [], "حصلت كتابة رغم أن العامل ما بدأش"


# ------------------------------------------------------- 5 / 6 / 12 / 15
def test_f02_case05_cancel_after_worker_start(tmp_path):
    """5: إلغاء بعد بدء العامل ⇒ القفل يفضل محتجز لحد ما الكتابة تخلص."""
    db, store = _f02_make(tmp_path)
    entered, release, state = _f02_blocking_writer(store)

    async def run():
        task = asyncio.ensure_future(store.store_async(**_store_kwargs(item_id="i1")))
        while not entered.is_set():
            await anyio.sleep(0)
        task.cancel()
        for _ in range(20):
            await anyio.sleep(0)
        held_at_cancel = store._accept_lock.locked()
        release.set()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=_F02_TIMEOUT)
        except asyncio.CancelledError:
            pass
        return held_at_cancel, store._accept_lock.locked()

    try:
        held_at_cancel, held_after = asyncio.run(run())
    finally:
        release.set()
    assert held_at_cancel is True, "القفل اتحرّر قبل ما العامل يخلص"
    assert held_after is False, "القفل ما اتحرّرش بعد انتهاء العامل"
    assert state["writes"] == 1, f"متوقّع كتابة واحدة، جاي {state['writes']}"
    assert "stored" not in _f02_statuses(db), "ادّعاء stored رغم الإلغاء"


def test_f02_case06_cancel_during_filesystem_write(tmp_path):
    """6: إلغاء أثناء الكتابة ⇒ لا تداخل، العنصر pending، مفيش stored."""
    db, store = _f02_make(tmp_path)
    entered, release, state = _f02_blocking_writer(store)

    async def run():
        task = asyncio.ensure_future(store.store_async(**_store_kwargs(item_id="i1")))
        while not entered.is_set():
            await anyio.sleep(0)
        task.cancel()
        for _ in range(10):
            await anyio.sleep(0)
        release.set()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=_F02_TIMEOUT)
        except asyncio.CancelledError:
            pass

    try:
        asyncio.run(run())
    finally:
        release.set()
    assert state["max"] == 1, f"أكتر من كاتب متزامن: {state['max']}"
    assert _f02_statuses(db) == ["pending"], f"حالة غير متوقّعة: {_f02_statuses(db)}"


def test_f02_case12_no_overlapping_acceptance(tmp_path):
    """12: قبولان متزامنان ⇒ تزامن أقصى = 1 (تسلسل محفوظ)."""
    db, store = _f02_make(tmp_path)
    entered, release, state = _f02_blocking_writer(store)

    async def run():
        t1 = asyncio.ensure_future(store.store_async(**_store_kwargs(item_id="i1")))
        while not entered.is_set():
            await anyio.sleep(0)
        t2 = asyncio.ensure_future(store.store_async(**_store_kwargs(item_id="i2")))
        for _ in range(20):
            await anyio.sleep(0)
        t2_blocked = not t2.done()
        release.set()
        try:
            await asyncio.wait_for(asyncio.shield(t1), timeout=_F02_TIMEOUT)
        except Exception:
            pass
        try:
            await asyncio.wait_for(asyncio.shield(t2), timeout=_F02_TIMEOUT)
        except Exception:
            pass
        return t2_blocked

    try:
        t2_blocked = asyncio.run(run())
    finally:
        release.set()
    assert t2_blocked is True, "القبول التاني ما اتحجبش رغم كاتب نشط"
    assert state["max"] == 1, f"تداخل كُتّاب: {state['max']}"


def test_f02_case15_lock_released_on_every_exit_path(tmp_path):
    """15/M7: القفل يتحرّر بعد كل مسار خروج مسموح (نجاح/رفض/خطأ/إلغاء)."""
    # (أ) نجاح
    (tmp_path / "ok").mkdir(parents=True, exist_ok=True)
    db, store = _f02_make(tmp_path / "ok")
    writes = []
    _f02_plain_writer(store, writes)
    res = asyncio.run(store.store_async(**_store_kwargs(item_id="i1")))
    assert store._accept_lock.locked() is False, "القفل محتجز بعد نجاح"
    assert res.status == StageStatus.STORED, f"متوقّع STORED، جاي {res.status}"

    # (ب) رفض قبل الكتابة (نوع محظور)
    (tmp_path / "rej").mkdir(parents=True, exist_ok=True)
    db2, store2 = _f02_make(tmp_path / "rej")
    res2 = asyncio.run(
        store2.store_async(**_store_kwargs(item_id="i1", display_name="x.exe"))
    )
    assert store2._accept_lock.locked() is False, "القفل محتجز بعد رفض"
    assert res2.status == StageStatus.REJECTED_TYPE

    # (ج) خطأ في العامل
    (tmp_path / "err").mkdir(parents=True, exist_ok=True)
    db3, store3 = _f02_make(tmp_path / "err")

    def _boom(path, chunks, cap):
        raise OSError("boom")

    store3._write_to_path = _boom
    # `_store_write` بيربط `OSError` بـ`WRITE_FAILED` (مش بيرفعه) — العقد محفوظ.
    res3 = asyncio.run(store3.store_async(**_store_kwargs(item_id="i1")))
    assert res3.status == StageStatus.WRITE_FAILED, f"متوقّع WRITE_FAILED، جاي {res3.status}"
    assert store3._accept_lock.locked() is False, "القفل محتجز بعد خطأ العامل"

    # (د) إلغاء قبل البدء
    (tmp_path / "canc").mkdir(parents=True, exist_ok=True)
    db4, store4 = _f02_make(tmp_path / "canc")
    w4 = []
    _f02_plain_writer(store4, w4)

    async def _run4():
        return await _f02_cancel_after_ticks(store4, 2)

    out4, held4 = asyncio.run(_run4())
    assert out4 == "cancelled"
    assert held4 is False, "القفل محتجز بعد إلغاء"


# ------------------------------------------------------------- 7 / 8 / 9 / M4
def test_f02_case07_worker_success_after_cancellation(tmp_path):
    """7: العامل ينجح بعد إلغاء المستدعي ⇒ **مفيش** ادّعاء stored (fail-closed)."""

    def _ok(path):
        with open(path, "wb") as fh:
            fh.write(b"done")
        return (5, b"done!")

    db, _ = _f02_cancel_then_finish(tmp_path, _ok)
    assert _f02_statuses(db) == ["pending"], f"حالة غير متوقّعة: {_f02_statuses(db)}"


def test_f02_case08_oserror_during_cancellation_path(tmp_path):
    """8: `OSError` في مسار الإلغاء ⇒ pending، لا stored، لا تعليق."""

    def _oserr(path):
        raise OSError("disk gone")

    db, _ = _f02_cancel_then_finish(tmp_path, _oserr)
    assert _f02_statuses(db) == ["pending"], f"حالة غير متوقّعة: {_f02_statuses(db)}"


def test_f02_case09_unexpected_worker_exception(tmp_path):
    """9: استثناء غير متوقّع (RuntimeError) ⇒ يُنقل للمستدعي، لا يُبتلع."""
    db, store = _f02_make(tmp_path)

    def _boom(path, chunks, cap):
        raise RuntimeError("unexpected")

    store._write_to_path = _boom
    with pytest.raises(RuntimeError, match="unexpected"):
        asyncio.run(store.store_async(**_store_kwargs(item_id="i1")))
    assert store._accept_lock.locked() is False
    assert _f02_statuses(db) == ["pending"]


def test_f02_M4_worker_exception_not_masked_as_stored(tmp_path):
    """M4: استثناء العامل في مسار الإلغاء **ما** يتحوّلش لنجاح مخزَّن."""

    def _oserr(path):
        raise OSError("nope")

    db, _ = _f02_cancel_then_finish(tmp_path, _oserr)
    statuses = _f02_statuses(db)
    assert "stored" not in statuses, f"ادّعاء stored رغم فشل الكتابة: {statuses}"
    assert statuses == ["pending"]


# ------------------------------------------------------- 10 / 11 / M5 (early)
def test_f02_case10_unconditional_completion_signaling(tmp_path):
    """10: إشارة الإتمام غير مشروطة — حتى `BaseException` لا يعلّق المستدعي."""
    db, store = _f02_make(tmp_path)

    class _Boom(BaseException):
        pass

    def _boom(path, chunks, cap):
        raise _Boom()

    store._write_to_path = _boom
    with pytest.raises(_Boom):
        asyncio.run(
            asyncio.wait_for(
                store.store_async(**_store_kwargs(item_id="i1")), timeout=_F02_TIMEOUT
            )
        )
    assert store._accept_lock.locked() is False


def test_f02_case11_early_abandonment_without_waiting(tmp_path):
    """11/M5: التخلّي المبكر ⇒ مفيش انتظار لعامل لن يبدأ، والقفل يُعاد استخدامه."""
    db, store = _f02_make(tmp_path)
    writes = []
    _f02_plain_writer(store, writes)

    async def run():
        first = await _f02_cancel_after_ticks(store, 3, item_id="i1")
        second = await asyncio.wait_for(
            store.store_async(**_store_kwargs(item_id="i2")), timeout=_F02_TIMEOUT
        )
        return first, second

    (outcome, held), second = asyncio.run(run())
    assert outcome == "cancelled"
    assert held is False, "القفل فضل محتجز ⇒ التخلّي المبكر ما اشتغلش"
    assert second.status == StageStatus.STORED, "القبول التاني ما نجحش بعد التخلّي"
    assert len(writes) == 1, f"متوقّع كتابة واحدة (للقبول التاني)، جاي {len(writes)}"


# ------------------------------------------------------------ 13 / 14 / M1 / M2
def test_f02_case13_anyio_scope_already_cancelled_at_drain(tmp_path):
    """13/M2: نطاق anyio ملغى فعلًا لحظة التصريف ⇒ الدرع يمنع تحرير القفل تحت كاتب.

    المسار اللي بيوصل للتصريف: إلغاء **نطاق anyio** + إلغاء **خام** معًا. بدون الدرع
    الخارجي، `run_sync` بيعمل checkpoint قبل درعه الداخلي ⇒ الـcheckpoint بيشوف النطاق
    الملغى ويرفع فورًا ⇒ القفل يتحرّر والخيط لسه بيكتب (`held_while_writing=False`).
    ده مُثبَت تجريبيًا بمقارنة مشغّل/غير مشغّل.
    """
    db, store = _f02_make(tmp_path)
    entered = threading.Event()
    release = threading.Event()
    state = {"writes": 0}

    def _w(path, chunks, cap):
        state["writes"] += 1
        entered.set()
        release.wait(timeout=10)
        with open(path, "wb") as fh:
            fh.write(b"p")
        return 7

    store._write_to_path = _w

    async def run():
        scope = anyio.CancelScope()

        async def in_scope():
            with scope:
                return await store.store_async(**_store_kwargs(item_id="i1"))

        outer = asyncio.ensure_future(in_scope())
        while not entered.is_set():
            await anyio.sleep(0)
        scope.cancel()      # إلغاء نطاق anyio
        outer.cancel()      # + إلغاء خام ⇒ بيدخل مسار التصريف
        for _ in range(30):
            await anyio.sleep(0)
        held = store._accept_lock.locked()   # ← الفاصل: لازم True
        release.set()
        try:
            await asyncio.wait_for(asyncio.shield(outer), timeout=_F02_TIMEOUT)
        except (asyncio.CancelledError, asyncio.TimeoutError, TimeoutError):
            pass
        return held, store._accept_lock.locked()

    try:
        held_while_writing, held_after = asyncio.run(run())
    finally:
        release.set()
    assert held_while_writing is True, (
        "القفل اتحرّر والنطاق ملغى أثناء التصريف — الدرع الخارجي مش شغّال"
    )
    assert held_after is False, "القفل ما اتحرّرش بعد انتهاء العامل"
    assert state["writes"] == 1
    assert "stored" not in _f02_statuses(db)


def test_f02_M1_anyio_fail_after_during_write(tmp_path):
    """M1: `fail_after` (إلغاء نطاق anyio) أثناء الكتابة ⇒ لا تعليق، القفل يتحرّر.

    الإلغاء بيستهدف مهمة `store_async` نفسها (مش مهمة الاختبار) — عشان نقيس
    سلوك التصريف تحت إلغاء نطاق anyio، مش إلغاء المُشغِّل.
    """
    db, store = _f02_make(tmp_path)
    entered = threading.Event()
    release = threading.Event()
    state = {"writes": 0}

    def _w(path, chunks, cap):
        state["writes"] += 1
        entered.set()
        release.wait(timeout=10)
        with open(path, "wb") as fh:
            fh.write(b"p")
        return 7

    store._write_to_path = _w

    async def run():
        # نفكّ العامل من داخل الحلقة أثناء التصريف (مش بعد انتهاء المهلة).
        asyncio.get_running_loop().call_later(0.15, release.set)
        try:
            with anyio.fail_after(0.05):
                task = asyncio.ensure_future(
                    store.store_async(**_store_kwargs(item_id="i1"))
                )
                while not entered.is_set():
                    await anyio.sleep(0)
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=_F02_TIMEOUT)
                    return "completed"
                except (asyncio.TimeoutError, TimeoutError):
                    return "HANG"
                except asyncio.CancelledError:
                    return "cancelled"
        finally:
            release.set()

    try:
        outcome = asyncio.run(run())
    finally:
        release.set()
    assert outcome != "HANG", "تعليق مع fail_after"
    assert state["writes"] == 1, f"متوقّع كتابة واحدة، جاي {state['writes']}"
    assert store._accept_lock.locked() is False, "القفل محتجز بعد fail_after"
    assert "stored" not in _f02_statuses(db)


# ------------------------------------------------------------- 16 / M8 / M3
def test_f02_case16_shutdown_completion_with_pending_cancellation(tmp_path):
    """16/M8: إغلاق الحلقة بعد إلغاء واحد معلّق ⇒ لا تعليق للعملية."""
    db, store = _f02_make(tmp_path)
    writes = []
    _f02_plain_writer(store, writes)

    async def run():
        task = asyncio.ensure_future(store.store_async(**_store_kwargs(item_id="i1")))
        for _ in range(2):
            await anyio.sleep(0)
        task.cancel()
        return task

    task = asyncio.run(run())
    assert task.done(), "المهمة ما خلصتش بعد teardown الحلقة"
    assert store._accept_lock.locked() is False, "القفل محتجز بعد teardown"


def test_f02_M3_double_cancel_before_gate(tmp_path):
    """M3: إلغاءان متتاليان قبل البوّابة ⇒ لا تعليق (حالة إلغاء وحد مُغطّاة)."""
    db, store = _f02_make(tmp_path)
    writes = []
    _f02_plain_writer(store, writes)

    async def run():
        task = asyncio.ensure_future(store.store_async(**_store_kwargs(item_id="i1")))
        for _ in range(2):
            await anyio.sleep(0)
        task.cancel()
        task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=_F02_TIMEOUT)
            return "completed"
        except (asyncio.TimeoutError, TimeoutError):
            return "HANG"
        except asyncio.CancelledError:
            return "cancelled"

    outcome = asyncio.run(run())
    assert outcome != "HANG", "تعليق مع إلغاءين قبل البوّابة"
    assert store._accept_lock.locked() is False, "القفل محتجز"
    assert "stored" not in _f02_statuses(db)


# ------------------------------------------------------------ 17 / 18 / M6
def test_f02_case17_T7_strengthened_pre_start(tmp_path):
    """17: تقوية T7 — تغطية نافذة ما قبل البدء التي كان T7 يفوّتها.

    T7 الأصلي بيستنّى `started` **داخل** دالة الكتابة ⇒ العامل بدأ بالفعل، فما يقدرش
    يكشف أي نافذة قبل البدء. هنا بنغطي النافذتين صراحةً:
      (أ) إلغاء قبل البدء ⇒ مفيش كتابة + القفل يتحرّر (اللي T7 كان بيفوّته).
      (ب) إلغاء أثناء الكتابة ⇒ القفل يفضل محتجز (اللي T7 بيغطّيه).
    """
    (tmp_path / "pre").mkdir(parents=True, exist_ok=True)
    db_a, store_a = _f02_make(tmp_path / "pre")
    writes_a = []
    _f02_plain_writer(store_a, writes_a)

    async def run_a():
        return await _f02_cancel_after_ticks(store_a, 3)

    outcome_a, held_a = asyncio.run(run_a())
    assert outcome_a != "HANG", "T7-strengthened: تعليق في نافذة ما قبل البدء"
    assert held_a is False, "T7-strengthened: القفل محتجز بعد إلغاء قبل البدء"
    assert writes_a == [], "T7-strengthened: كتابة حصلت رغم أن العامل ما بدأش"

    (tmp_path / "mid").mkdir(parents=True, exist_ok=True)
    db_b, store_b = _f02_make(tmp_path / "mid")
    entered, release, state = _f02_blocking_writer(store_b)

    async def run_b():
        task = asyncio.ensure_future(store_b.store_async(**_store_kwargs(item_id="i1")))
        while not entered.is_set():
            await anyio.sleep(0)
        task.cancel()
        for _ in range(20):
            await anyio.sleep(0)
        held = store_b._accept_lock.locked()
        release.set()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=_F02_TIMEOUT)
        except asyncio.CancelledError:
            pass
        return held

    try:
        held_b = asyncio.run(run_b())
    finally:
        release.set()
    assert held_b is True, "T7-strengthened: القفل اتحرّر تحت كاتب نشط"
    assert state["max"] == 1


def test_f02_case18_no_await_while_holding_gate():
    """18/M6: إثبات ساكن — مفيش `await` جوه أي كتلة `with _gate:`."""
    import inspect as _inspect

    src = _inspect.getsource(StagingStore.store_async)
    lines = src.splitlines()
    checked = 0
    in_block = False
    block_indent = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("with _gate:"):
            in_block = True
            block_indent = len(line) - len(line.lstrip())
            checked += 1
            continue
        if in_block:
            if not stripped:
                continue
            cur_indent = len(line) - len(line.lstrip())
            if cur_indent <= block_indent:
                in_block = False
                continue
            assert "await" not in stripped, (
                f"`await` جوه كتلة البوّابة (ممنوع — تعليق محتمل): {stripped}"
            )
    assert checked >= 2, f"متوقّع كتلتا بوّابة على الأقل، لقيت {checked}"



# ==========================================================================
# F-02-REV-01 — انحدار: العامل المهجور ممنوع يكتب وممنوع يتداخل مع قبول تاني
# ==========================================================================
# العيب اللي بيكشفه الاختبار ده (طفرة M4′): لو اتشال فحص `abandoned` من العامل مع
# إبقاء البوّابة سليمة، العامل المهجور بيكتب **بعد** ما المستدعي خرج بالفعل ⇒
# `_accept_lock` اتحرّر ⇒ قبول تاني بيدخل في نفس اللحظة ⇒ كاتبان متزامنان على القرص.
#
# السيناريو مُجبَر حتميًا (مش نوم كوسيلة تزامن أساسية): بنلفّ `threading.Lock` اللي
# بيتعمل جوه `store_async` بغلاف بيحبس **خيط العامل** قبل ما ياخد البوّابة. ساعتها
# المستدعي (خيط الحلقة) بيكسب البوّابة أولًا ⇒ `abandoned=True` و`_needs_drain=False`.
# بعدها بنفكّ العامل: الكود الصح بيرجع بدون كتابة، والطفرة بتكتب ⇒ تداخل مقيس.
def test_f02_REV01_abandoned_worker_must_not_write_and_must_not_overlap(
    tmp_path, monkeypatch
):
    import bot.attachments as _att

    db, store = _f02_make(tmp_path)

    main_ident = threading.get_ident()
    worker_at_gate = threading.Event()
    worker_may_proceed = threading.Event()
    worker_gate_acquisitions = []
    real_lock_factory = threading.Lock

    class _ControlledGate:
        """بوّابة حقيقية، لكن خيط العامل بيتحبس قبل ما ياخدها (ترتيب حتمي)."""

        def __init__(self):
            self._real = real_lock_factory()

        def acquire(self, *args, **kwargs):
            if threading.get_ident() != main_ident:
                worker_gate_acquisitions.append(1)
                worker_at_gate.set()
                worker_may_proceed.wait(timeout=_F02_TIMEOUT * 3)
            return self._real.acquire(*args, **kwargs)

        def release(self):
            return self._real.release()

        def locked(self):
            return self._real.locked()

        def __enter__(self):
            self.acquire()
            return self

        def __exit__(self, *exc):
            self.release()
            return False

    class _ThreadingShim:
        Lock = _ControlledGate
        Event = threading.Event

    monkeypatch.setattr(_att, "threading", _ThreadingShim)

    entered_second = threading.Event()
    release = threading.Event()
    guard = threading.Lock()
    state = {"active": 0, "max": 0, "writes": {}}

    def _writer(path, chunks, cap):
        tag = chunks[0] if chunks else b"?"
        with guard:
            state["active"] += 1
            state["max"] = max(state["max"], state["active"])
            state["writes"][tag] = state["writes"].get(tag, 0) + 1
            if tag == b"i2":
                entered_second.set()
        try:
            release.wait(timeout=_F02_TIMEOUT * 3)
            with open(path, "wb") as fh:
                fh.write(b"p")
            return 7
        finally:
            with guard:
                state["active"] -= 1

    store._write_to_path = _writer

    async def _wait_event(ev, timeout=_F02_TIMEOUT):
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while not ev.is_set():
            if loop.time() > deadline:
                return False
            await asyncio.sleep(0.001)
        return True

    async def run():
        t1 = asyncio.ensure_future(
            store.store_async(**_store_kwargs(item_id="i1", chunks=[b"i1"]))
        )
        reached_gate = await _wait_event(worker_at_gate)

        t1.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(t1), timeout=_F02_TIMEOUT)
            outcome = "completed"
        except (asyncio.TimeoutError, TimeoutError):
            outcome = "HANG"
        except asyncio.CancelledError:
            outcome = "cancelled"
        lock_free_after_abandon = not store._accept_lock.locked()

        # العامل يكمل دلوقتي: الكود الصح بيرجع بدون كتابة، والطفرة بتكتب.
        worker_may_proceed.set()

        t2 = asyncio.ensure_future(
            store.store_async(**_store_kwargs(item_id="i2", chunks=[b"i2"]))
        )
        second_started = await _wait_event(entered_second)
        max_conc = state["max"]
        writes_i1 = state["writes"].get(b"i1", 0)

        release.set()
        try:
            await asyncio.wait_for(asyncio.shield(t2), timeout=_F02_TIMEOUT)
        except Exception:
            pass
        return reached_gate, outcome, lock_free_after_abandon, second_started, max_conc, writes_i1

    try:
        (
            reached_gate,
            outcome,
            lock_free_after_abandon,
            second_started,
            max_conc,
            writes_i1,
        ) = asyncio.run(run())
    finally:
        release.set()
        worker_may_proceed.set()

    assert reached_gate is True, "خيط العامل ما وصلش للبوّابة — السيناريو ما اتحققش"
    assert outcome == "cancelled", f"المستدعي ما اتلغاش كما هو متوقّع: {outcome}"
    assert lock_free_after_abandon is True, "القفل ما اتحرّرش بعد التخلّي"
    assert len(worker_gate_acquisitions) >= 1, (
        "العامل ما وصلش للبوّابة أصلًا — الاختبار ممكن ينجح زائفًا"
    )
    assert second_started is True, "القبول التاني ما وصلش للكتابة — القياس غير صالح"
    assert writes_i1 == 0, (
        "العامل المهجور كتب على القرص — فحص `abandoned` مش شغّال (عيب M4′)"
    )
    assert max_conc == 1, f"تداخل كُتّاب على القرص: max_concurrent_writers={max_conc}"
