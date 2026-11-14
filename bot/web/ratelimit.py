"""محدّد معدّل بسيط في الذاكرة (OHB2-06 / S2).

التصميم:
- صفر تبعيات، نافذة منزلقة (sliding window) بعدّاد طوابع زمنية لكل مفتاح.
- ساعة قابلة للحقن (`clock`) عشان الاختبارات تبقى حتمية (مفيش `sleep`).
- كل مفتاح عنده deque بطوابع الأحداث جوه أوسع نافذة؛ بنشيل القديم عند كل فحص.
- عدد المفاتيح محدود (`max_keys`) مع طرد الأقدم (LRU) عشان الذاكرة ما تكبرش بلا حد.
- `allow` بترجّع `(مسموح, retry_after_ثواني)`. لو اتمنع، مفيش أي تسجيل للحدث.
- مش بيسجّل أي بيانات حساسة (المفاتيح معرّفات مستعارة، مش توكنات).

ملاحظة: العملية واحدة، فالمحدّد ده صالح كحماية داخل العملية. مع عمليات متعددة
لازم مخزن مشترك (Redis) — خارج النطاق دلوقتي.
"""
from __future__ import annotations

import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Limit:
    """قاعدة واحدة: `max_events` حدث كحد أقصى خلال `window_seconds`."""

    max_events: int
    window_seconds: float

    def __post_init__(self) -> None:
        if self.max_events <= 0:
            raise ValueError("max_events لازم يكون موجب")
        if self.window_seconds <= 0:
            raise ValueError("window_seconds لازم تكون موجبة")


class SlidingWindowLimiter:
    """محدّد نافذة منزلقة في الذاكرة، بيتحقن بساعة للاختبارات."""

    def __init__(
        self,
        limits: list[Limit],
        *,
        clock: Callable[[], float] = time.monotonic,
        max_keys: int = 4096,
    ) -> None:
        if not limits:
            raise ValueError("لازم قاعدة واحدة على الأقل")
        self._limits = list(limits)
        self._clock = clock
        self._max_keys = max(1, int(max_keys))
        self._events: OrderedDict[str, deque[float]] = OrderedDict()
        self._widest = max(lim.window_seconds for lim in self._limits)

    def allow(self, key: str, now: float | None = None) -> tuple[bool, float]:
        """يسجّل حدث للمفتاح لو مسموح. يرجّع (مسموح، retry_after ثواني).

        كل قاعدة بتتحسب على نافذتها **بمفردها** (عدد الأحداث اللي جوه نافذتها بس).
        لو أكثر من قاعدة متجاوزة، `retry_after` = أطول انتظار مطلوب (لحد ما كل
        النوافذ المتجاوزة تبقى سليمة). لو اتمنع، ما بيتسجّلش أي حدث (مع تحديث الحداثة).
        """
        current = self._clock() if now is None else now
        bucket = self._events.get(key)
        if bucket is None:
            bucket = deque()
            self._events[key] = bucket
            self._evict_if_needed()
        else:
            # وصول لمفتاح موجود ⇒ يحدّث حداثته (LRU) سواء اتسمح أو اتمنع.
            self._touch(key)
            self._prune(bucket, current)

        blocked = self._blocked_retry(bucket, current)
        if blocked is not None:
            return False, blocked

        bucket.append(current)
        return True, 0.0

    def retry_after(self, key: str, now: float | None = None) -> float:
        """الوقت المتبقي لحد ما المفتاح يبقى مسموح تاني (0 لو مسموح دلوقتي)."""
        current = self._clock() if now is None else now
        bucket = self._events.get(key)
        if bucket is None:
            return 0.0
        self._touch(key)  # وصول لمفتاح موجود ⇒ يحدّث حداثته (LRU)
        self._prune(bucket, current)
        return self._blocked_retry(bucket, current) or 0.0

    def _blocked_retry(self, bucket: deque[float], current: float) -> float | None:
        """أطول انتظار مطلوب لو أي نافذة متجاوزة، أو None لو كل النوافذ سليمة.

        لكل نافذة متجاوزة، الانتظار = الوقت المتبقي لحد ما **أقدم حدث جوه النافذة دي**
        يخرج منها. النتيجة مش بتخلط نوافذ غير متعلّقة.
        """
        wait: float | None = None
        for lim in self._limits:
            in_window = self._events_within(bucket, current, lim.window_seconds)
            if in_window >= lim.max_events:
                earliest = self._earliest_within(bucket, current, lim.window_seconds)
                window_wait = max(0.0, earliest + lim.window_seconds - current)
                wait = window_wait if wait is None else max(wait, window_wait)
        return wait

    @staticmethod
    def _events_within(bucket: deque[float], current: float, window_seconds: float) -> int:
        """عدد الأحداث اللي جوه النافذة المحدّدة (أحدث من `current - window`)."""
        cutoff = current - window_seconds
        return sum(1 for t in bucket if t > cutoff)

    @staticmethod
    def _earliest_within(bucket: deque[float], current: float, window_seconds: float) -> float:
        """أقدم حدث جوه النافذة المحدّدة (أول واحد بيخرج منها)."""
        cutoff = current - window_seconds
        for t in bucket:
            if t > cutoff:
                return t
        return current  # نظريًا ما يوصلش: بيتنادى بس لما النافذة متجاوزة

    def reset(self) -> None:
        self._events.clear()

    def _prune(self, bucket: deque[float], now: float) -> None:
        cutoff = now - self._widest
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

    def _touch(self, key: str) -> None:
        """يعلّم المفتاح كـ«الأحدث استعمالًا» بنقله لآخر OrderedDict (LRU)."""
        self._events.move_to_end(key)

    def _evict_if_needed(self) -> None:
        # الطرد بترتيب الحداثة: أقدم مفتاح في OrderedDict = الأقل استعمالًا (LRU).
        while len(self._events) > self._max_keys:
            self._events.popitem(last=False)


def auth_limiter(config, *, clock: Callable[[], float] = time.monotonic) -> SlidingWindowLimiter:
    """محدّد لمسار /auth (لكل IP): 10/دقيقة و30/ساعة افتراضيًا (قابل للضبط)."""
    return SlidingWindowLimiter(
        [
            Limit(config.mini_app_auth_rate_per_minute, 60.0),
            Limit(config.mini_app_auth_rate_per_hour, 3600.0),
        ],
        clock=clock,
        max_keys=config.mini_app_rate_max_keys,
    )


def api_limiter(config, *, clock: Callable[[], float] = time.monotonic) -> SlidingWindowLimiter:
    """محدّد للمسارات المصادَقة (لكل جلسة): 60/دقيقة افتراضيًا (قابل للضبط)."""
    return SlidingWindowLimiter(
        [Limit(config.mini_app_api_rate_per_minute, 60.0)],
        clock=clock,
        max_keys=config.mini_app_rate_max_keys,
    )
