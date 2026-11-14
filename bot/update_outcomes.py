"""عقد **نتيجة معالجة التحديث** وحدّ الإقرار (OHB2-MANUAL-POLLING-OUTCOME).

المشكلة اللي بيحلّها: «رجوع الـ handler بنجاح» **مش** دليل إن التحديث وصل لنتيجته
الدائمة — PTB بيبتلع الاستثناءات (بيحوّلها لمعالج الأخطاء ويرجّع عاديًّا)، وبعض
المسارات بترجع بعد ما تعرض رسالة فشل للمستخدم. فمينفعش نبني قرار الإقرار على الرجوع.

الحل: **نتيجة دائمة** بتتكتب في **نفس معاملة القاعدة** اللي بتنفّذ نية التحديث
(`processed_updates.outcome`). الأهلية للإقرار بتتقرأ من العمود ده بس، والفشل **مقفول**:
أي تحديث مالوش نتيجة مؤهّلة مسجّلة ⇒ مش مؤهّل (حتى لو الـ handler رجع بنجاح).

المفاهيم:
- **التحديث (update)**: عنصر مفرد جوه دفعة (batch) من `getUpdates`.
- **الدفعة**: التحديثات بالترتيب اللي اتستقبلت بيه من تيليجرام.
- **حدّ الإقرار**: أطول **بادئة** مؤهّلة بترتيب الاستقبال. أول تحديث غير مؤهّل بيحجز
  كل اللي بعده (head-of-line blocking) — **مش** `max(update_id)+1`، ومش مطلوب إن
  المعرّفات تكون متتالية (الفجوات مقبولة).
- **الإقرار (acknowledgment)**: بيحصل عند تيليجرام **بس** لما `getUpdates` جاي بموضع
  (offset) أعلى من معرّف التحديث. تسجيل الموضع محليًا **مش** إقرار.
"""
from __future__ import annotations

import asyncio
from typing import Iterable

# ------------------------------------------------------------------ فئات النتيجة
# القيم دي بتتكتب في `processed_updates.outcome`. أي قيمة **غير** المذكورة في
# `_ACK_ELIGIBLE` غير مؤهّلة (fail-closed) — بما فيها الصفوف القديمة (NULL).
DURABLE_COMPLETED = "durable_completed"
DURABLE_INTENT_RECORDED = "durable_intent_recorded"
EXPLICITLY_IGNORED = "explicitly_ignored"
DUPLICATE_COMPLETED = "duplicate_completed"
# OHB2-P0-A3/D-30: نتيجة نهائية **متينة** لنصّ مصاحب مرفوض نهائيًّا (غير مؤهّل/غامض/منتهٍ).
# قرار دائم مُثبَّت في القاعدة ⇒ مؤهّل للإقرار (مفيش إعادة معالجة لاحقة).
REJECTED_INELIGIBLE = "rejected_ineligible"
FAILED_TRANSIENT = "failed_transient"
FAILED_PERMANENT = "failed_permanent"
PARTIAL_OR_UNKNOWN = "partial_or_unknown"

# الفئات المؤهّلة للإقرار: ليها دليل دائم في القاعدة (أو قرار تجاهل/رفض صريح مُوثَّق).
_ACK_ELIGIBLE = frozenset(
    {
        DURABLE_COMPLETED,
        DURABLE_INTENT_RECORDED,
        EXPLICITLY_IGNORED,
        DUPLICATE_COMPLETED,
        REJECTED_INELIGIBLE,
    }
)

# الفئات غير المؤهّلة صراحةً (fail-closed). بنعدّها هنا للتوثيق والاختبار.
_INELIGIBLE = frozenset(
    {FAILED_TRANSIENT, FAILED_PERMANENT, PARTIAL_OR_UNKNOWN, None, ""}
)


def is_ack_eligible(outcome: str | None) -> bool:
    """هل النتيجة دي مؤهّلة للإقرار؟ (fail-closed: أي قيمة تانية ⇒ False)."""
    return outcome in _ACK_ELIGIBLE


def classify_failure(exc: BaseException | None, *, transient: bool = False) -> str:
    """يصنّف فشل الـ handler لفئة نتيجة.

    `transient=True` (فشل عابر قابل لإعادة المحاولة — SQLite BUSY/LOCKED أو عطل شبكة
    مؤقّت) ⇒ `FAILED_TRANSIENT` (إعادة محاولة الدفعة). غير كده ⇒ `FAILED_PERMANENT`
    (يحتاج قرار تشغيلي). النتيجة الغامضة (`asyncio.CancelledError` / نتيجة خارجية
    غير محسومة) بتتسجّل `PARTIAL_OR_UNKNOWN` من مسار الاستدعاء مباشرة، مش من هنا.
    """
    return FAILED_TRANSIENT if transient else FAILED_PERMANENT


def classify_error_outcome(
    exc: BaseException | None, *, transient: bool = False
) -> str | None:
    """يصنّف استثناء من معالج أخطاء PTB لفئة نتيجة (أو None لو مش فشل حقيقي).

    - `exc is None` ⇒ None (مفيش خطأ).
    - `asyncio.CancelledError` ⇒ `PARTIAL_OR_UNKNOWN` (إلغاء/إغلاق — مفيش حسم).
    - `transient=True` (فشل عابر: SQLite BUSY/LOCKED أو `ApiError` تشغيلي) ⇒
      `FAILED_TRANSIENT`.
    - أي حاجة تانية ⇒ `FAILED_PERMANENT`.

    بيتنادى من معالج الأخطاء في طبقة الـ handlers (بيحوّل تصنيف sqlite/ApiError لـ
    `transient`)، عشان المعالج يقدر يتسجّل الفشل **بثبات** بدل ما يتبلع كنجاح.
    """
    if exc is None:
        return None
    if isinstance(exc, asyncio.CancelledError):
        return PARTIAL_OR_UNKNOWN
    return classify_failure(exc, transient=transient)


def acknowledgment_boundary(
    received: Iterable[int], outcomes: dict[int, str | None]
) -> int | None:
    """أطول بادئة مؤهّلة بترتيب الاستقبال ⇒ معرّف **آخر تحديث مؤهّل** (أو None).

    - `received`: معرّفات التحديثات بترتيب الاستقبال الفعلي (مش مرتّبة رقميًا).
    - `outcomes`: نتيجة كل `update_id` كما هي مسجّلة **بثبات** في القاعدة.
    - بترجّع `None` لو **أول** تحديث غير مؤهّل (مفيش أي إقرار ممكن).
    - بترجّع معرّف آخر تحديث في أطول بادئة كل عناصرها مؤهّلة.
    - بتتعامل مع الفجوات: المعرّفات مش مطلوب تكون متتالية.
    - **مش** `max(update_id)+1`: تحديث لاحق ناجح **مش** بيكسر الحجز اللي سبّبه فشل سابق.
    """
    boundary: int | None = None
    for update_id in received:
        if not is_ack_eligible(outcomes.get(update_id)):
            break  # أول غير مؤهّل بيحجز كل اللي بعده
        boundary = update_id
    return boundary
