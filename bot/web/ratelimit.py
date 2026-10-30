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
from collections import deque
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
        self._events: dict[str, deque[float]] = {}
        self._widest = max(lim.window_seconds for lim in self._limits)

    def allow(self, key: str, now: float | None = None) -> tuple[bool, float]:
        """يسجّل حدث للمفتاح لو مسموح. يرجّع (مسموح، retry_after ثواني).

        لو اتمنع، ما بيتسجّلش أي حدث و`retry_after` = الوقت المتبقي لحد ما أقدم حدث
        في أكثر قاعدة متجاوزة يخرج من النافذة.
        """
        current = self._clock() if now is None else now
        bucket = self._events.get(key)
        if bucket is None:
            bucket = deque()
            self._events[key] = bucket
            self._evict_if_needed()
        else:
            self._prune(bucket, current)

        for lim in self._limits:
            if len(bucket) >= lim.max_events:
                oldest = bucket[0]
                retry = max(0.0, oldest + lim.window_seconds - current)
                return False, retry

        bucket.append(current)
        return True, 0.0

    def retry_after(self, key: str, now: float | None = None) -> float:
        """الوقت المتبقي لحد ما المفتاح يبقى مسموح تاني (0 لو مسموح دلوقتي)."""
        current = self._clock() if now is None else now
        bucket = self._events.get(key)
        if not bucket:
            return 0.0
        self._prune(bucket, current)
        wait = 0.0
        for lim in self._limits:
            if len(bucket) >= lim.max_events:
                wait = max(wait, max(0.0, bucket[0] + lim.window_seconds - current))
        return wait

    def reset(self) -> None:
        self._events.clear()

    def _prune(self, bucket: deque[float], now: float) -> None:
        cutoff = now - self._widest
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

    def _evict_if_needed(self) -> None:
        # الطرد بالترتيب (dict بترتيب الإدخال) للأقدم — كفاية لحماية الذاكرة.
        while len(self._events) > self._max_keys:
            oldest_key = next(iter(self._events))
            self._events.pop(oldest_key, None)


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
