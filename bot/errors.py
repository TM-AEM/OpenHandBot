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
