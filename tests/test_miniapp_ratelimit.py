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


# ============================================ OHB2-AUDIT-FIX-03: independent windows
# الباگ المؤكَّد: المحدّد كان بيحسب عدد الأحداث في **أوسع** نافذة ويقارنه بكل حد،
# فحد الدقيقة كان بيتصرف زي حد الساعة. الإصلاح: كل نافذة تتقيس لوحدها.

MINUTE_HOUR = [Limit(10, 60.0), Limit(30, 3600.0)]


def test_minute_limit_independent_of_hour_window():
    """10 محاولات موزّعة على دقايق مختلفة خلال ساعة، ثم الـ11 جوه نفس الدقيقة ⇒ مسموح."""
    clock = FakeClock()
    lim = SlidingWindowLimiter(MINUTE_HOUR, clock=clock)
    for i in range(10):  # محاولة واحدة كل دقيقة: t=0,60,...,540
        clock.now = i * 60.0
        assert lim.allow("k")[0] is True, f"محاولة {i} لازم تنجح"
    clock.now = 541.0  # جوه نفس دقيقة المحاولة العاشرة (540)
    allowed, retry = lim.allow("k")
    assert allowed is True, "الدقيقة فيها حدثين بس ⇒ مش المفروض تتحجب"
    assert retry == 0.0


def test_eleventh_attempt_in_same_minute_blocked():
    """11 محاولة جوه دقيقة واحدة ⇒ الـ11 تتحجب بحد الدقيقة (retry≈60)."""
    clock = FakeClock()
    lim = SlidingWindowLimiter(MINUTE_HOUR, clock=clock)
    for _ in range(10):
        assert lim.allow("k")[0] is True
    allowed, retry = lim.allow("k")
    assert allowed is False
    assert retry == pytest.approx(60.0)


def test_thirtieth_within_hour_allowed_thirty_first_blocked():
    """30 محاولة خلال ساعة (دقيقة كل مرة) ⇒ الـ31 تتحجب بحد الساعة فقط."""
    clock = FakeClock()
    lim = SlidingWindowLimiter(MINUTE_HOUR, clock=clock)
    for i in range(30):  # t=0,60,...,1740
        clock.now = i * 60.0
        assert lim.allow("k")[0] is True, f"محاولة {i} لازم تنجح"
    clock.now = 1741.0
    allowed, retry = lim.allow("k")
    assert allowed is False
    # الدقيقة فيها حدثين بس ⇒ الحجب من الساعة، والـretry من أقدم حدث جوه الساعة (t=0).
    assert retry == pytest.approx(3600.0 - 1741.0)


def test_minute_events_expire_while_hourly_remain():
    """أحداث الدقيقة تخرج بينما أحداث الساعة باقية ⇒ المفتاح يرجع مسموح."""
    clock = FakeClock()
    lim = SlidingWindowLimiter(MINUTE_HOUR, clock=clock)
    for _ in range(10):
        assert lim.allow("k")[0] is True  # كلهم عند t=0
    assert lim.allow("k")[0] is False  # الدقيقة متجاوزة
    clock.advance(60.1)  # خرجت أحداث الدقيقة (لكن العشرة لسه جوه الساعة)
    allowed, retry = lim.allow("k")
    assert allowed is True, "أحداث الدقيقة خرجت ⇒ مسموح (الساعة لسه 10 < 30)"
    assert retry == 0.0
    assert lim.retry_after("k") == 0.0


def test_hourly_events_expire_and_recover():
    """أحداث الساعة تخرج ⇒ المفتاح يرجع مسموح."""
    clock = FakeClock()
    lim = SlidingWindowLimiter(MINUTE_HOUR, clock=clock)
    for i in range(30):  # محاولة كل دقيقة (t=0,60,...,1740) ⇒ الدقيقة عمرها ما تتجاوز
        clock.now = i * 60.0
        assert lim.allow("k")[0] is True
    clock.now = 1741.0
    allowed, retry = lim.allow("k")
    assert allowed is False
    assert retry == pytest.approx(3600.0 - 1741.0)  # من أقدم حدث جوه الساعة (t=0)
    clock.advance(3600.1)  # خرجت كل أحداث الساعة
    assert lim.allow("k")[0] is True


def test_retry_after_reflects_each_exceeded_window():
    """Retry-After بيتحسب من النافذة المتجاوزة نفسها، مش من نافذة غير متعلّقة."""
    # حد الدقيقة بس متجاوز ⇒ retry من الدقيقة.
    clock = FakeClock()
    minute_only = SlidingWindowLimiter([Limit(10, 60.0)], clock=clock)
    for _ in range(10):
        minute_only.allow("k")
    clock.advance(15.0)
    allowed, retry = minute_only.allow("k")
    assert allowed is False and retry == pytest.approx(45.0)

    # حد الساعة بس متجاوز (والدقيقة فيها حدث واحد) ⇒ retry من الساعة.
    clock2 = FakeClock()
    hour_only = SlidingWindowLimiter([Limit(1, 3600.0)], clock=clock2)
    hour_only.allow("k")
    clock2.advance(15.0)
    allowed2, retry2 = hour_only.allow("k")
    assert allowed2 is False and retry2 == pytest.approx(3585.0)


def test_two_windows_retry_is_longest_required():
    """لو النافذتين متجاوزتين، retry = أطول انتظار مطلوب (مش الأقصر)."""
    clock = FakeClock()
    # نافذتان قصيرتان عشان نبني الحالة بسرعة: 2/10s و4/100s.
    lim = SlidingWindowLimiter([Limit(2, 10.0), Limit(4, 100.0)], clock=clock)
    assert lim.allow("k")[0] is True   # t=0
    assert lim.allow("k")[0] is True   # t=0 ⇒ النافذة القصيرة متجاوزة (2)
    clock.now = 20.0                   # النافذة القصيرة (10s) فضيت، الطويلة لسه فيها الـ2
    assert lim.allow("k")[0] is True   # t=20 (short=1, long=3)
    assert lim.allow("k")[0] is True   # t=20 (short=2, long=4)
    # عند t=20 الاتنين متجاوزتين: انتظار القصيرة = 10، انتظار الطويلة = 80 ⇒ الأطول يحكم.
    allowed, retry = lim.allow("k")
    assert allowed is False
    assert retry == pytest.approx(80.0)


def test_windows_independent_across_keys():
    """مفاتيح مستقلة: حجب مفتاح مايحجبش مفتاح تاني بأي نافذة."""
    clock = FakeClock()
    lim = SlidingWindowLimiter(MINUTE_HOUR, clock=clock)
    for _ in range(10):
        lim.allow("a")
    assert lim.allow("a")[0] is False  # a محجوب بالدقيقة
    assert lim.allow("b")[0] is True   # b مستقل تمامًا
    assert lim.allow("b")[0] is True


def test_boundary_event_exactly_at_window_edge_is_expired():
    """حدث عند حد النافذة بالظبط (t = now - window) يُعدّ خارجًا (سلوك حدّي دقيق)."""
    clock = FakeClock()
    lim = SlidingWindowLimiter([Limit(1, 60.0)], clock=clock)
    assert lim.allow("k")[0] is True  # t=0
    clock.now = 59.999
    assert lim.allow("k")[0] is False  # لسه جوه النافذة
    clock.now = 60.0
    assert lim.allow("k")[0] is True   # عند الحد بالظبط ⇒ خرج


def test_auth_limiter_enforces_both_windows_independently():
    """auth_limiter (10/دقيقة + 30/ساعة) بيطبّق النافذتين مستقلتين."""
    from bot.web.ratelimit import auth_limiter

    class _Cfg:
        mini_app_auth_rate_per_minute = 10
        mini_app_auth_rate_per_hour = 30
        mini_app_rate_max_keys = 100

    clock = FakeClock()
    lim = auth_limiter(_Cfg(), clock=clock)
    # 10 محاولات عبر دقايق مختلفة ⇒ كلها مسموحة (الدقيقة فيها حدث واحد).
    for i in range(10):
        clock.now = i * 60.0
        assert lim.allow("ip")[0] is True
    # الـ11 عند t=541 (نفس دقيقة الـ10) ⇒ مسموحة (الدقيقة فيها حدثين، الساعة 11<30).
    clock.now = 541.0
    assert lim.allow("ip")[0] is True


# ================================================= OHB2-PLAN-02-D: طرد LRU حقيقي
# الباگ المؤكَّد (Stage 0): الوصف بيقول LRU لكن الطرد كان بترتيب الإدراج (FIFO)،
# و`allow`/`retry_after` ما كانوش بيحدّثوا الحداثة. الإصلاح: أي وصول ناجح لمفتاح
# موجود يخلّيه «الأحدث استعمالًا»، والطرد عند تجاوز `max_keys` بيشيل الأقل حداثة.

def test_recent_successful_access_protects_key_from_eviction():
    """وصول `allow` ناجح لمفتاح موجود يحدّث حداثته ⇒ مايتطردش قبل مفتاح أقدم (Test A)."""
    clock = FakeClock()
    lim = SlidingWindowLimiter([Limit(5, 60.0)], clock=clock, max_keys=2)
    assert lim.allow("A")[0] is True   # A (الأقدم إدراجًا)
    assert lim.allow("B")[0] is True   # B
    assert lim.allow("A")[0] is True   # وصول ناجح لـ A ⇒ A الأحدث استعمالًا
    assert lim.allow("C")[0] is True   # إدخال C ⇒ تجاوز الحد ⇒ طرد الأقل حداثة (B)
    assert "A" in lim._events          # A محمي (اتستخدم مؤخّرًا)
    assert "B" not in lim._events      # B هو اللي يتطرد
    assert "C" in lim._events


def test_retry_after_updates_recency():
    """وصول `retry_after` لمفتاح موجود يحدّث حداثته ⇒ مايتطردش (Test B)."""
    clock = FakeClock()
    lim = SlidingWindowLimiter([Limit(5, 60.0)], clock=clock, max_keys=2)
    assert lim.allow("A")[0] is True   # A
    assert lim.allow("B")[0] is True   # B
    assert lim.retry_after("A") == 0.0  # وصول retry_after لـ A ⇒ A الأحدث
    assert lim.allow("C")[0] is True   # تجاوز ⇒ طرد الأقل حداثة (B)
    assert "A" in lim._events
    assert "B" not in lim._events
    assert "C" in lim._events


def test_least_recently_used_is_evicted_without_reaccess():
    """بدون إعادة وصول، الأقل حداثة = الأقدم إدراجًا ⇒ يتطرد أولًا (Test C)."""
    clock = FakeClock()
    lim = SlidingWindowLimiter([Limit(5, 60.0)], clock=clock, max_keys=2)
    assert lim.allow("old")[0] is True
    assert lim.allow("mid")[0] is True
    assert lim.allow("new")[0] is True  # تجاوز ⇒ طرد الأقل حداثة (old)
    assert "old" not in lim._events
    assert "mid" in lim._events
    assert "new" in lim._events


def test_ordered_dict_and_blocked_allow_updates_recency():
    """Blocked allow() برضه يحدّث الحداثة في OrderedDict من غير تسجيل حدث مرفوض."""
    from collections import OrderedDict

    clock = FakeClock()
    lim = SlidingWindowLimiter([Limit(1, 60.0)], clock=clock, max_keys=2)
    assert isinstance(lim._events, OrderedDict)
    assert lim.allow("A")[0] is True   # A الأحدث (1/1)
    assert lim.allow("B")[0] is True   # B الأحدث، A الأقدم
    clock.advance(10.0)
    allowed, retry = lim.allow("A")    # مرفوض ⇒ لكنه لمس A فيحدّث حداثته ويفضل B الأقدم
    assert allowed is False
    assert retry == pytest.approx(50.0)
    assert lim.allow("C")[0] is True   # يتطرد B (الأقدم)، A يفضل موجود وممنوع لحد نهاية نافذته
    assert "A" in lim._events
    assert "B" not in lim._events
    assert "C" in lim._events
    assert lim.allow("A")[0] is False
    clock.advance(50.1)
    assert lim.allow("A")[0] is True
