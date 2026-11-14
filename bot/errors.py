"""تحويل أخطاء الـ API لرسائل عربي قصيرة."""
from __future__ import annotations

import logging

# الأسرار المسجّلة (توكن البوت، مفتاح OpenHands). أي نص بيتعرض للمستخدم أو بيتسجّل
# بيعدّي على redact() عشان لو سر اتسرّب جوّه رسالة خطأ يتخفّى.
_SECRETS: set[str] = set()
_MIN_SECRET_LEN = 6


def register_secrets(*values: str | None) -> None:
    for value in values:
        value = (value or "").strip()
        if len(value) >= _MIN_SECRET_LEN:
            _SECRETS.add(value)


def clear_secrets() -> None:
    _SECRETS.clear()


def redact(text: str) -> str:
    out = str(text)
    # الأطول أولاً عشان سر جزء من سر تاني ما يسيبش باقي.
    for secret in sorted(_SECRETS, key=len, reverse=True):
        out = out.replace(secret, "***")
    return out


class RedactingFilter(logging.Filter):
    """فلتر logging بيخفي الأسرار المسجّلة من الرسالة والمعاملات والـ traceback."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001
            message = str(record.msg)
        record.msg = redact(message)
        record.args = ()
        if record.exc_info:
            # ما نطبعش traceback كامل: نسيب النوع بس عشان ما يتسرّبش نص الاستثناء.
            record.exc_text = None
            record.msg = f"{record.msg} [{record.exc_info[0].__name__ if record.exc_info[0] else 'error'}]"
            record.exc_info = None
        return True



class ApiError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(redact(message))
        self.status_code = status_code


class ResponseTooLargeError(ApiError):
    """رد upstream أكبر من الحد الآمن المسموح (OHB2-09-01-FIX).

    نوع مخصّص عشان طبقة الملفات تقدر تترجمه لحالة `too_large` بشكل صريح بدل
    ما تخلطه مع أخطاء upstream العامة.
    """

    def __init__(self, message: str = "حجم رد الملف كبير أوي للعرض الآمن.") -> None:
        super().__init__(message)


class OperationalApiFailure(ApiError):
    """فشل upstream **حقيقي/عابر** (5xx/429/مهلة/انقطاع) لازم **ينتشر** بعد عرضه للمستخدم.

    OHB2-SW-07: بعض المعالجات كانت بتلتقط أي `ApiError` وتعرض رسالة ثم ترجع عاديًّا،
    فالفشل التشغيلي (عطل OpenHands 5xx أو 429) كان بيُلبَس «إتمام معالجة ناجح» ويختفي
    من الرصد/معالج الأخطاء. النوع ده بيُرفع **بعد** عرض الرسالة المتنقّحة للمستخدم
    (فمفيش تغيير في تجربة المستخدم)، لكنه بيفضل استثناءً ⇒ يوصله معالج الأخطاء بدل ما
    يتحوّل لنجاح صامت.

    الفرق عن رفض 4xx المتوقّع (404/403/410/409/422): ده **نتيجة مستخدم متوقّعة** بتتعرض
    وترجع عاديًّا (مفيش رفع) — ممنوع نحوّل الرفض المصرّح أو المورد المحذوف لفشل عابر.

    لسه `ApiError`، فـ `error_text()` بترجّع رسالته المتنقّحة بالظبط (نفس نص المستخدم).
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message, status_code)


def error_text(exc: BaseException) -> str:
    """نص آمن للمستخدم: رسالة ApiError (متنقّحة)، وأي استثناء تاني ⇒ نص عام بدون تفاصيله."""
    if isinstance(exc, ApiError):
        return redact(str(exc))
    return "حصل خطأ غير متوقع، جرّب تاني."


_STATUS_MESSAGES = {
    401: "مفتاح OpenHands غير صحيح أو منتهي.",
    403: "مفتاح OpenHands مالوش صلاحية على العملية دي.",
    404: "الشات أو المورد مش موجود.",
    409: "الـ sandbox واقف أو لسه بيبدأ، محتاج تشغيل قبل الإرسال.",
    410: "الشات اتمسح أو sandbox بتاعه خلص.",
    422: "طلب غير صحيح للـ API.",
    429: "طلبات كتير على OpenHands، جرّب تاني بعد شوية.",
    500: "خطأ داخلي في OpenHands.",
    503: "خدمة OpenHands مش متاحة دلوقتي.",
}


def describe_status(status_code: int, detail: str = "") -> str:
    base = _STATUS_MESSAGES.get(status_code, f"خطأ من OpenHands ({status_code}).")
    detail = redact((detail or "").strip())
    if detail and status_code not in (401, 403):
        return f"{base}\n{detail}"
    return base
