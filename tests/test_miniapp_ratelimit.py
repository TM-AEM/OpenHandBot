"""اختبارات محدّد المعدّل (OHB2-06 / S2) — بساعة مزيفة حتمية (مفيش sleep)."""
from __future__ import annotations

import pytest

from bot.web.ratelimit import Limit, SlidingWindowLimiter


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_allows_up_to_limit_then_blocks():
    clock = FakeClock()
    lim = SlidingWindowLimiter([Limit(3, 60.0)], clock=clock)
    for _ in range(3):
        assert lim.allow("k")[0] is True
    allowed, retry = lim.allow("k")
    assert allowed is False
    assert retry == pytest.approx(60.0)


def test_window_slides_and_recovers():
    clock = FakeClock()
    lim = SlidingWindowLimiter([Limit(2, 60.0)], clock=clock)
    assert lim.allow("k")[0]
    assert lim.allow("k")[0]
    assert lim.allow("k")[0] is False
    clock.advance(60.1)
    assert lim.allow("k")[0] is True


def test_retry_after_counts_down():
    clock = FakeClock()
    lim = SlidingWindowLimiter([Limit(1, 60.0)], clock=clock)
    assert lim.allow("k")[0]
    clock.advance(20.0)
    allowed, retry = lim.allow("k")
    assert allowed is False
    assert retry == pytest.approx(40.0)


def test_two_limits_most_restrictive_wins():
    clock = FakeClock()
    lim = SlidingWindowLimiter([Limit(10, 60.0), Limit(2, 3600.0)], clock=clock)
    assert lim.allow("k")[0]
    assert lim.allow("k")[0]
    allowed, retry = lim.allow("k")
    assert allowed is False
    # الحد الساعي هو اللي بيحكم.
    assert retry == pytest.approx(3600.0)


def test_keys_are_independent():
    clock = FakeClock()
    lim = SlidingWindowLimiter([Limit(1, 60.0)], clock=clock)
    assert lim.allow("a")[0]
    assert lim.allow("b")[0]
    assert lim.allow("a")[0] is False
    assert lim.allow("b")[0] is False


def test_blocked_request_is_not_recorded():
    clock = FakeClock()
    lim = SlidingWindowLimiter([Limit(1, 60.0)], clock=clock)
    assert lim.allow("k")[0]
    clock.advance(30.0)
    assert lim.allow("k")[0] is False  # مرفوض
    clock.advance(30.1)  # مرّت 60.1 من الحدث المسجّل الوحيد
    assert lim.allow("k")[0] is True


def test_expired_entries_are_pruned():
    clock = FakeClock()
    lim = SlidingWindowLimiter([Limit(5, 60.0)], clock=clock)
    lim.allow("k")
    clock.advance(120.0)
    lim.allow("k")  # بيفحص ويشيل القديم
    assert lim.retry_after("k") == 0.0


def test_max_keys_bounds_memory():
    clock = FakeClock()
    lim = SlidingWindowLimiter([Limit(1, 60.0)], clock=clock, max_keys=2)
    for i in range(50):
        lim.allow(f"key-{i}")
    # عدد المفاتيح المحفوظة ما يعديش الحد.
    assert len(lim._events) <= 2


def test_max_keys_evicts_oldest():
    clock = FakeClock()
    lim = SlidingWindowLimiter([Limit(1, 60.0)], clock=clock, max_keys=2)
    lim.allow("old")
    lim.allow("mid")
    lim.allow("new")
    assert "old" not in lim._events


def test_rejects_invalid_limit():
    with pytest.raises(ValueError):
        Limit(0, 60.0)
    with pytest.raises(ValueError):
        Limit(1, 0)


def test_requires_at_least_one_limit():
    with pytest.raises(ValueError):
        SlidingWindowLimiter([])


def test_reset_clears_state():
    clock = FakeClock()
    lim = SlidingWindowLimiter([Limit(1, 60.0)], clock=clock)
    assert lim.allow("k")[0]
    lim.reset()
    assert lim.allow("k")[0]
