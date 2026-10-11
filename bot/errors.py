"""تحويل أخطاء الـ API لرسائل عربي قصيرة."""
from __future__ import annotations


class ApiError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


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
    detail = (detail or "").strip()
    if detail and status_code not in (401, 403):
        return f"{base}\n{detail}"
    return base
