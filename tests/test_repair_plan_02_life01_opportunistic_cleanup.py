"""OHB2-LIFE-01 — كنس انتهاكي **محدود** من tick عامل **موجود** (محلي فقط).

المرجع المعماري: A4 staged plan §5 بند 7 + «Stage A4» — الكنس يُستدعى من hook بدء تشغيل
**موجود** و/أو **tick عامل موجود**، بلا عامل/مجدول/عملية/مالك قاعدة جديد. LIFE-01 بتستخدم
tick `Watcher` **الموجود** (مفيش نقطة كنس عند الإدخال — R-3، ومفيش عامل جديد).

يغطّي (متطلّبات 4.5):
1. دفعة منتهية ⇒ تُكنس على trigger مؤهّل.
2. دفعة حيّة ⇒ تُصان (بلا حذف).
3. `T0` الأصلي **ما بيتصفّرش**.
4. trigger واحد يعمل شغلًا **محدودًا** (كنسة واحدة).
5. تحديثات/ticks متكرّرة ⇒ مفيش كنسة كاملة على كل tick (خنق).
6. triggers متزامنة/متداخلة ⇒ تتسلسل بأمان (حرس إعادة دخول).
7. فشل الكنسة **ما بيُبلَّغش** كنجاح.
8. الكنسة الفاشلة **تُعاد** على trigger مؤهّل لاحق.
9. الكنسات المتكرّرة idempotent.
10. مسارات غير آمنة/غير مرتبطة/مجهولة ⇒ **ما تُحذفش**.
11. كنس الإقلاع (A4) يفضل شغّالًا.
12. مفيش عامل/مهمّة/عملية/اتصال قاعدة جديد.

الساعات **محقونة** (ساعة رتيبة مزيّفة للخنق + `now` صريح للكنس) ⇒ مفيش sleeps.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

from bot import attachments
from bot.attachments import (
    AttachmentReaper,
    OpportunisticSweeper,
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
from bot.watcher import Watcher

OWNER_A = 1
CID_A = "11111111222233334444555566667777"
T0 = "2026-11-14T10:00:00+00:00"
NOW_LIVE = datetime(2026, 11, 14, 10, 5, tzinfo=timezone.utc)      # داخل المهلة
NOW_AFTER = datetime(2026, 11, 14, 10, 16, tzinfo=timezone.utc)    # بعد الحدّ


# ------------------------------------------------------------------ أدوات
class FakeClock:
    """ساعة رتيبة مزيّفة (تتقدّم يدويًّا) — بلا sleeps ومفيش هشاشة زمنية."""

    def __init__(self, start: float = 1000.0) -> None:
        self.t = float(start)

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += float(seconds)


def make_db(tmp_path):
    db_path = str(tmp_path / "state.sqlite3")
    return Database(db_path), db_path


def add_batch(db, batch_id, *, status=ATTACHMENT_BATCH_PENDING, t0=T0):
    db.create_attachment_batch(batch_id, OWNER_A, CID_A, t0, status=status)
    return batch_id


def add_item(db, item_id, batch_id, *, token, status=ATTACHMENT_ITEM_STORED):
    db.add_attachment_item(
        item_id, batch_id, staging_token=token, display_name="n.txt",
        size_bytes=3, status=status,
    )
    return item_id


def write_staged(db_path, token, data=b"abc"):
    root = staging_root_for(db_path)
    root.mkdir(parents=True, exist_ok=True)
    (root / token).write_bytes(data)
    return root / token


def make_sweeper(db, db_path, *, clock=None, min_interval=60.0):
    reaper = AttachmentReaper(db, db_path)
    return OpportunisticSweeper(reaper, min_interval=min_interval, clock=clock)


# ============================================================================
# 1) دفعة منتهية ⇒ تُكنس على trigger مؤهّل
# ============================================================================
def test_expired_batch_is_cleaned_on_eligible_trigger(tmp_path):
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1")
    add_item(db, "i1", "b1", token="a" * 32)
    f = write_staged(db_path, "a" * 32)
    sweeper = make_sweeper(db, db_path)
    rep = sweeper.maybe_sweep(now=NOW_AFTER)
    assert rep is not None
    assert rep.files_deleted == 1
    assert not f.exists()
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_EXPIRED
    assert db.get_attachment_item("i1").status == ATTACHMENT_ITEM_REAPED


# ============================================================================
# 2) دفعة حيّة ⇒ تُصان (بلا حذف)
# ============================================================================
def test_active_batch_is_preserved(tmp_path):
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1")
    add_item(db, "i1", "b1", token="b" * 32)
    f = write_staged(db_path, "b" * 32)
    sweeper = make_sweeper(db, db_path)
    rep = sweeper.maybe_sweep(now=NOW_LIVE)
    assert rep is not None
    assert rep.files_deleted == 0
    assert f.exists()
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_PENDING


# ============================================================================
# 3) T0 الأصلي ما بيتصفّرش
# ============================================================================
def test_original_t0_not_reset_by_opportunistic_sweep(tmp_path):
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1")
    add_item(db, "i1", "b1", token="c" * 32)
    write_staged(db_path, "c" * 32)
    sweeper = make_sweeper(db, db_path)
    sweeper.maybe_sweep(now=NOW_LIVE)     # لسه حيّة
    assert db.get_attachment_batch("b1").t0 == T0
    sweeper.maybe_sweep(now=NOW_AFTER)    # منتهية
    assert db.get_attachment_batch("b1").t0 == T0  # الختم الأصلي ما اتغيّرش


# ============================================================================
# 4) trigger واحد يعمل شغلًا محدودًا (كنسة واحدة)
# ============================================================================
def test_single_trigger_runs_one_bounded_sweep(tmp_path, monkeypatch):
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1")
    add_item(db, "i1", "b1", token="d" * 32)
    write_staged(db_path, "d" * 32)
    calls = []
    reaper = AttachmentReaper(db, db_path)
    real_sweep = reaper.sweep

    def counting_sweep(*, now):
        calls.append(now)
        return real_sweep(now=now)

    monkeypatch.setattr(reaper, "sweep", counting_sweep)
    sweeper = OpportunisticSweeper(reaper, clock=FakeClock())
    sweeper.maybe_sweep(now=NOW_AFTER)
    assert len(calls) == 1  # كنسة واحدة بالظبط لكل trigger مؤهّل


# ============================================================================
# 5) تحديثات/ticks متكرّرة ⇒ مفيش كنسة كاملة على كل tick (خنق)
# ============================================================================
def test_repeated_triggers_are_throttled(tmp_path):
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1")
    add_item(db, "i1", "b1", token="e" * 32)
    write_staged(db_path, "e" * 32)
    clock = FakeClock()
    sweeper = make_sweeper(db, db_path, clock=clock, min_interval=60.0)

    assert sweeper.maybe_sweep(now=NOW_AFTER) is not None  # الأولى اشتغلت
    # كل الـ ticks اللي جوه النافذة ⇒ تتخطّى (None)، بلا كنسة كاملة.
    for _ in range(5):
        clock.advance(5.0)
        assert sweeper.maybe_sweep(now=NOW_AFTER) is None
    # بعد النافذة ⇒ كنسة جديدة مؤهّلة.
    clock.advance(60.0)
    assert sweeper.maybe_sweep(now=NOW_AFTER) is not None


def test_throttled_second_sweep_does_not_touch_files(tmp_path, monkeypatch):
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1")
    add_item(db, "i1", "b1", token="f" * 32)
    write_staged(db_path, "f" * 32)
    clock = FakeClock()
    sweeper = make_sweeper(db, db_path, clock=clock, min_interval=60.0)
    sweeper.maybe_sweep(now=NOW_AFTER)  # بتكنس

    # ضع ملف جديد لدفعة منتهية تانية؛ الكنسة المخنوقة **ما** توصلوش.
    add_batch(db, "b2", status=ATTACHMENT_BATCH_DELIVERED)
    add_item(db, "i2", "b2", token="g" * 32)
    f2 = write_staged(db_path, "g" * 32)
    clock.advance(1.0)
    assert sweeper.maybe_sweep(now=NOW_AFTER) is None  # مخنوقة
    assert f2.exists()  # ما اتلمستش


# ============================================================================
# 6) triggers متداخلة ⇒ تتسلسل بأمان (حرس إعادة دخول)
# ============================================================================
def test_reentrant_trigger_is_coalesced(tmp_path, monkeypatch):
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1")
    add_item(db, "i1", "b1", token="h" * 32)
    write_staged(db_path, "h" * 32)
    reaper = AttachmentReaper(db, db_path)
    sweeper = OpportunisticSweeper(reaper, clock=FakeClock())

    seen = []
    real_sweep = reaper.sweep

    def reentrant_sweep(*, now):
        seen.append("outer")
        # محاولة trigger تانية **أثناء** الكنسة ⇒ لازم تتخطّى (حرس إعادة الدخول).
        inner = sweeper.maybe_sweep(now=now)
        seen.append(("inner", inner))
        return real_sweep(now=now)

    monkeypatch.setattr(reaper, "sweep", reentrant_sweep)
    outer = sweeper.maybe_sweep(now=NOW_AFTER)
    assert outer is not None
    assert ("inner", None) in seen  # الداخلية اتخطّت (None) ⇒ مفيش تداخل


# ============================================================================
# 7) فشل الكنسة ما بيُبلَّغش كنجاح
# ============================================================================
def test_failed_sweep_is_not_reported_as_success(tmp_path, monkeypatch):
    db, db_path = make_db(tmp_path)
    reaper = AttachmentReaper(db, db_path)

    def boom(*, now):
        raise RuntimeError("fs failure")

    monkeypatch.setattr(reaper, "sweep", boom)
    sweeper = OpportunisticSweeper(reaper, clock=FakeClock())
    assert sweeper.maybe_sweep(now=NOW_AFTER) is None  # مش نجاح


# ============================================================================
# 8) الكنسة الفاشلة تُعاد على trigger مؤهّل لاحق (مفيش كبت دائم)
# ============================================================================
def test_failed_sweep_is_retried_on_next_eligible_trigger(tmp_path, monkeypatch):
    db, db_path = make_db(tmp_path)
    reaper = AttachmentReaper(db, db_path)
    clock = FakeClock()
    sweeper = OpportunisticSweeper(reaper, clock=clock, min_interval=60.0)

    state = {"fail": True, "ok": 0}
    real_sweep = reaper.sweep

    def flaky(*, now):
        if state["fail"]:
            raise RuntimeError("temporary")
        state["ok"] += 1
        return real_sweep(now=now)

    monkeypatch.setattr(reaper, "sweep", flaky)
    # فشل ⇒ ما بيستهلكش الخنق (الزمن ما اتقدّمش) ⇒ trigger تالي فورًا مسموح.
    assert sweeper.maybe_sweep(now=NOW_AFTER) is None
    state["fail"] = False
    rep = sweeper.maybe_sweep(now=NOW_AFTER)  # نفس اللحظة الرتيبة ⇒ لسه مؤهّل
    assert rep is not None
    assert state["ok"] == 1


# ============================================================================
# 9) الكنسات المتكرّرة idempotent
# ============================================================================
def test_repeated_sweeps_are_idempotent(tmp_path):
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1")
    add_item(db, "i1", "b1", token="i" * 32)
    f = write_staged(db_path, "i" * 32)
    clock = FakeClock()
    sweeper = make_sweeper(db, db_path, clock=clock, min_interval=0.0)
    r1 = sweeper.maybe_sweep(now=NOW_AFTER)
    r2 = sweeper.maybe_sweep(now=NOW_AFTER)
    assert r1.files_deleted == 1
    assert r2.files_deleted == 0  # لا شيء لکنسه
    assert not f.exists()
    assert db.get_attachment_item("i1").status == ATTACHMENT_ITEM_REAPED


# ============================================================================
# 10) مسارات غير آمنة/غير مرتبطة/مجهولة ⇒ ما تُحذفش
# ============================================================================
def test_unknown_and_unsafe_paths_are_not_deleted(tmp_path):
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1")
    add_item(db, "i1", "b1", token="j" * 32)
    write_staged(db_path, "j" * 32)
    root = staging_root_for(db_path)
    # ملف غير مرتبط بأي عنصر (لا يُحذف — بلا تخمين).
    orphan = root / ("k" * 32)
    orphan.write_bytes(b"orphan")
    # symlink غير آمن (لا يُتبع/لا يُحذف).
    target = tmp_path / "outside.txt"
    target.write_bytes(b"outside")
    link = root / ("l" * 32)
    os.symlink(str(target), str(link))

    sweeper = make_sweeper(db, db_path)
    rep = sweeper.maybe_sweep(now=NOW_AFTER)
    assert orphan.exists()   # غير مرتبط ⇒ يُترك
    assert link.exists()     # symlink ⇒ يُترك
    assert target.exists()   # الهدف خارج الجذر سليم
    assert rep.untracked_left >= 1
    assert rep.unsafe_left >= 1


# ============================================================================
# 11) كنس الإقلاع (A4) يفضل شغّالًا — عبر tick المراقب **الموجود**
# ============================================================================
def test_watcher_tick_runs_opportunistic_sweep(tmp_path):
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1")
    add_item(db, "i1", "b1", token="m" * 32)
    f = write_staged(db_path, "m" * 32)
    sweeper = make_sweeper(db, db_path)

    class _NoClient:
        async def get_conversations(self, ids):  # pragma: no cover — مفيش متابعات
            return []

    watcher = Watcher(_NoClient(), db, bot=None, chat_id=OWNER_A,
                      opportunistic_sweeper=sweeper)
    asyncio.run(watcher.tick())
    assert not f.exists()
    assert db.get_attachment_item("i1").status == ATTACHMENT_ITEM_REAPED


def test_watcher_without_sweeper_is_unchanged(tmp_path):
    # بلا ربط ⇒ السلوك السابق بالظبط (مفيش كنس من الـ tick).
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1")
    add_item(db, "i1", "b1", token="n" * 32)
    f = write_staged(db_path, "n" * 32)

    class _NoClient:
        async def get_conversations(self, ids):  # pragma: no cover
            return []

    watcher = Watcher(_NoClient(), db, bot=None, chat_id=OWNER_A)
    asyncio.run(watcher.tick())
    assert f.exists()  # مفيش كنس انتهاكي بلا ربط


# ============================================================================
# 12) مفيش عامل/مهمّة/عملية/اتصال قاعدة جديد
# ============================================================================
def test_sweeper_introduces_no_worker_task_or_connection(tmp_path):
    db, db_path = make_db(tmp_path)
    before_conn = db._conn
    reaper = AttachmentReaper(db, db_path)
    sweeper = OpportunisticSweeper(reaper, clock=FakeClock())
    # مفيش واجهة عامل/مهمّة على الغلاف.
    assert not hasattr(sweeper, "start")
    assert not hasattr(sweeper, "stop")
    assert not hasattr(sweeper, "run")
    sweeper.maybe_sweep(now=NOW_AFTER)
    assert db._conn is before_conn  # نفس اتصال القاعدة الوحيد


def test_attachments_module_has_no_asyncio_or_task():
    src = open(attachments.__file__, encoding="utf-8").read()
    assert "asyncio" not in src
    assert "create_task" not in src


def test_watcher_sweep_does_not_create_task(tmp_path, monkeypatch):
    db, db_path = make_db(tmp_path)
    add_batch(db, "b1")
    add_item(db, "i1", "b1", token="o" * 32)
    write_staged(db_path, "o" * 32)
    sweeper = make_sweeper(db, db_path)
    created = []
    real_create = asyncio.create_task

    def spy(coro, *a, **k):
        created.append(coro)
        return real_create(coro, *a, **k)

    monkeypatch.setattr(asyncio, "create_task", spy)

    class _NoClient:
        async def get_conversations(self, ids):  # pragma: no cover
            return []

    watcher = Watcher(_NoClient(), db, bot=None, chat_id=OWNER_A,
                      opportunistic_sweeper=sweeper)
    asyncio.run(watcher.tick())
    assert created == []  # الكنسة الانتهاكية متزامنة ⇒ مفيش مهمّة جديدة
