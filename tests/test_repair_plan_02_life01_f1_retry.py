"""OHB2-REPAIR-PLAN-02/LIFE-01/F1 — فشل الكنسة + أهلية إعادة المحاولة (محلي فقط).

المرجع: مراجعة LIFE-01 المستقلة — F1: `AttachmentReaper.sweep()` بيمسك فشل القاعدة
ويرجّع `SweepReport(errors>0)` **بدل** ما يرمي، و`OpportunisticSweeper.maybe_sweep()`
كان بيعامل التقرير ده كنجاح وبيقدّم ختم آخر تشغيل ⇒ مفيش إعادة محاولة مقصودة.

القواعد المفروضة هنا:
- تقرير رجع `errors>0` = **فشل/فشل جزئي** ⇒ **ما يتقدّمش** ختم آخر نجاح.
- استثناء من `sweep()` = فشل ⇒ ما يتقدّمش ختم النجاح.
- تقرير `errors==0` = نجاح ⇒ يتقدّم ختم النجاح.
- إعادة المحاولة **محدودة**: خنق على «آخر محاولة» (نجاح أو فشل) بفاصل `min_interval`
  ⇒ مفيش كنسة كاملة على كل tick (حلقة ضيّقة)، وأول tick مؤهّل بعد الخنق بيعيد المحاولة.
- `Watcher` بلا sweeper = السلوك السابق بالظبط.

الساعات محقونة (ساعة رتيبة مزيّفة) ⇒ مفيش انتظار حقيقي 60 ثانية. قاعدة SQLite حقيقية.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from bot.attachments import (
    AttachmentReaper,
    OpportunisticSweeper,
    SweepReport,
)
from bot.db import Database
from bot.watcher import Watcher

OWNER_A = 1
CID_A = "11111111222233334444555566667777"
T0 = "2026-11-14T10:00:00+00:00"
NOW_AFTER = datetime(2026, 11, 14, 10, 16, tzinfo=timezone.utc)


class FakeClock:
    """ساعة رتيبة مزيّفة (تتقدّم يدويًّا) — بلا sleeps."""

    def __init__(self, start: float = 1000.0) -> None:
        self.t = float(start)

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += float(seconds)


def make_db(tmp_path):
    db_path = str(tmp_path / "state.sqlite3")
    return Database(db_path), db_path


def make_sweeper(db, db_path, *, clock=None, min_interval=60.0):
    reaper = AttachmentReaper(db, db_path)
    return OpportunisticSweeper(reaper, min_interval=min_interval, clock=clock)


# ============================================================================
# 1) تقرير ناجح (errors==0) ⇒ يتقدّم ختم النجاح
# ============================================================================
def test_successful_zero_error_report_advances_success_timestamp(tmp_path):
    db, db_path = make_db(tmp_path)
    sweeper = make_sweeper(db, db_path, clock=FakeClock())
    assert sweeper.last_success_at is None
    rep = sweeper.maybe_sweep(now=NOW_AFTER)
    assert rep is not None and rep.errors == 0
    assert sweeper.last_success_at is not None  # نجاح كامل ⇒ الختم اتقدّم


# ============================================================================
# 2) تقرير رجع errors>0 ⇒ **ما يتقدّمش** ختم النجاح (الجوهر بتاع F1)
# ============================================================================
def test_returned_error_report_does_not_advance_success_timestamp(tmp_path, monkeypatch):
    db, db_path = make_db(tmp_path)
    reaper = AttachmentReaper(db, db_path)

    def error_report(*, now):
        return SweepReport(errors=2, scanned=1)

    monkeypatch.setattr(reaper, "sweep", error_report)
    sweeper = OpportunisticSweeper(reaper, clock=FakeClock())
    rep = sweeper.maybe_sweep(now=NOW_AFTER)
    assert rep is not None and rep.errors == 2  # التقرير بيوصل للرصد كما هو
    assert sweeper.last_success_at is None  # لكن **مش** نجاح


# ============================================================================
# 3) استثناء ⇒ **ما يتقدّمش** ختم النجاح
# ============================================================================
def test_exception_does_not_advance_success_timestamp(tmp_path, monkeypatch):
    db, db_path = make_db(tmp_path)
    reaper = AttachmentReaper(db, db_path)

    def boom(*, now):
        raise RuntimeError("fs failure")

    monkeypatch.setattr(reaper, "sweep", boom)
    sweeper = OpportunisticSweeper(reaper, clock=FakeClock())
    assert sweeper.maybe_sweep(now=NOW_AFTER) is None
    assert sweeper.last_success_at is None


# ============================================================================
# 4) مسار فشل القاعدة **الإنتاجي** الحقيقي: `AttachmentReaper.sweep()` نفسه بيمسك
#    فشل القاعدة ويرجّع تقرير أخطاء (مش استثناء) ⇒ لازم يتحسب فشلًا.
# ============================================================================
def test_production_db_error_path_returns_error_report_not_success(tmp_path, monkeypatch):
    db, db_path = make_db(tmp_path)
    reaper = AttachmentReaper(db, db_path)

    def db_down(*, now_iso):
        raise RuntimeError("db down")

    # كسر مسار القاعدة الحقيقي جوه `sweep` (خطوة «جلب الدفعات المنتهية»).
    monkeypatch.setattr(db, "list_expired_pending_attachment_batches", db_down)
    sweeper = OpportunisticSweeper(reaper, clock=FakeClock())
    rep = sweeper.maybe_sweep(now=NOW_AFTER)
    # التقرير الحقيقي من `AttachmentReaper.sweep` بيحمل errors>=1 ⇒ فشل، مش نجاح.
    assert rep is not None and rep.errors >= 1
    assert sweeper.last_success_at is None


# ============================================================================
# 5) إعادة المحاولة المحدودة: فشل ⇒ خنق، وبعد الخنق إعادة محاولة ناجحة
# ============================================================================
def test_failed_attempt_is_bounded_then_retried(tmp_path, monkeypatch):
    db, db_path = make_db(tmp_path)
    reaper = AttachmentReaper(db, db_path)
    clock = FakeClock()
    sweeper = OpportunisticSweeper(reaper, clock=clock, min_interval=60.0)

    state = {"fail": True, "calls": 0}
    real_sweep = reaper.sweep

    def flaky(*, now):
        state["calls"] += 1
        if state["fail"]:
            return SweepReport(errors=1)
        return real_sweep(now=now)

    monkeypatch.setattr(reaper, "sweep", flaky)
    # المحاولة الأولى: مؤهّلة ⇒ تنفّذ وترجّع فشلًا (مفيش ختم نجاح).
    rep1 = sweeper.maybe_sweep(now=NOW_AFTER)
    assert rep1 is not None and rep1.errors == 1
    assert sweeper.last_success_at is None
    # جوه نافذة الخنق ⇒ **مفيش** محاولة (مفيش حلقة ضيّقة).
    clock.advance(5.0)
    assert sweeper.maybe_sweep(now=NOW_AFTER) is None
    assert state["calls"] == 1
    # بعد الخنق ⇒ إعادة المحاولة مؤهّلة وبتنجح.
    state["fail"] = False
    clock.advance(60.0)
    rep2 = sweeper.maybe_sweep(now=NOW_AFTER)
    assert rep2 is not None and rep2.errors == 0
    assert state["calls"] == 2
    assert sweeper.last_success_at is not None  # النجاح اللاحق سجّل الختم


# ============================================================================
# 6) الفشل المتكرّر ما بيعملش كنسة كاملة على كل tick (مفيش حلقة غير محدودة)
# ============================================================================
def test_repeated_failures_do_not_create_per_tick_loop(tmp_path, monkeypatch):
    db, db_path = make_db(tmp_path)
    reaper = AttachmentReaper(db, db_path)
    clock = FakeClock()
    sweeper = OpportunisticSweeper(reaper, clock=clock, min_interval=60.0)

    calls = {"n": 0}

    def failing(*, now):
        calls["n"] += 1
        return SweepReport(errors=1)

    monkeypatch.setattr(reaper, "sweep", failing)
    # 20 tick متتالي جوه نافذة الخنق ⇒ محاولة **واحدة** بس.
    for _ in range(20):
        sweeper.maybe_sweep(now=NOW_AFTER)
        clock.advance(1.0)
    assert calls["n"] == 1  # مفيش كنسة كاملة على كل tick
    assert sweeper.last_success_at is None


# ============================================================================
# 7) نجاح لاحق بعد فشل ⇒ يتقدّم ختم النجاح
# ============================================================================
def test_later_success_after_failure_advances_success_timestamp(tmp_path, monkeypatch):
    db, db_path = make_db(tmp_path)
    reaper = AttachmentReaper(db, db_path)
    clock = FakeClock()
    sweeper = OpportunisticSweeper(reaper, clock=clock, min_interval=60.0)
    real_sweep = reaper.sweep
    state = {"fail": True}

    def flaky(*, now):
        if state["fail"]:
            raise RuntimeError("temporary")
        return real_sweep(now=now)

    monkeypatch.setattr(reaper, "sweep", flaky)
    sweeper.maybe_sweep(now=NOW_AFTER)  # فشل
    assert sweeper.last_success_at is None
    state["fail"] = False
    clock.advance(60.0)
    sweeper.maybe_sweep(now=NOW_AFTER)  # نجاح
    assert sweeper.last_success_at is not None


# ============================================================================
# 8) فشل جزئي (errors>0 مع scanned/partial) ما يتقرّرش نجاحًا كاملًا
# ============================================================================
def test_partial_failure_is_not_reported_as_success(tmp_path, monkeypatch):
    db, db_path = make_db(tmp_path)
    reaper = AttachmentReaper(db, db_path)

    def partial(*, now):
        # كنسة اشتغلت جزئيًّا بس فيها خطأ قاعدة ⇒ مش نجاح.
        return SweepReport(scanned=3, cleaned=2, errors=1)

    monkeypatch.setattr(reaper, "sweep", partial)
    sweeper = OpportunisticSweeper(reaper, clock=FakeClock())
    rep = sweeper.maybe_sweep(now=NOW_AFTER)
    assert rep is not None and rep.errors == 1
    assert sweeper.last_success_at is None  # فشل جزئي ⇒ مفيش ختم نجاح


# ============================================================================
# 9) سلوك الخنق عند النجاح لسه صحيح
# ============================================================================
def test_successful_sweep_throttle_behavior_unchanged(tmp_path):
    db, db_path = make_db(tmp_path)
    clock = FakeClock()
    sweeper = make_sweeper(db, db_path, clock=clock, min_interval=60.0)
    assert sweeper.maybe_sweep(now=NOW_AFTER) is not None  # الأولى اشتغلت
    for _ in range(5):
        clock.advance(5.0)
        assert sweeper.maybe_sweep(now=NOW_AFTER) is None  # مخنوقة جوه النافذة
    clock.advance(60.0)
    assert sweeper.maybe_sweep(now=NOW_AFTER) is not None  # بعد النافذة مؤهّلة


# ============================================================================
# 10) Watcher بلا sweeper = السلوك السابق (مفيش كنس انتهاكي)
# ============================================================================
def test_watcher_without_sweeper_unchanged(tmp_path):
    from bot.attachments import staging_root_for

    db, db_path = make_db(tmp_path)
    db.create_attachment_batch("b1", OWNER_A, CID_A, T0)
    db.add_attachment_item("i1", "b1", staging_token="n" * 32,
                           display_name="n.txt", size_bytes=3, status="stored")
    root = staging_root_for(db_path)
    root.mkdir(parents=True, exist_ok=True)
    f = root / ("n" * 32)
    f.write_bytes(b"abc")

    class _NoClient:
        async def get_conversations(self, ids):  # pragma: no cover
            return []

    watcher = Watcher(_NoClient(), db, bot=None, chat_id=OWNER_A)
    asyncio.run(watcher.tick())
    assert f.exists()  # مفيش كنس انتهاكي بلا ربط
