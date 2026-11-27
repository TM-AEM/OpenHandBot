"""صندوق الصادر: تسليم البرومتات بضمان at-most-once + worker واحد مالك.

- كل برومت بيتسجّل 'pending' قبل أي إرسال (في handlers._send_prompt).
- التسليم بياخد 'pending' ذرّياً ويحوّله 'claimed'، وبعدين 'sending' قبل الـ POST بالظبط (db.claim_outbox).
- نتيجة غامضة (timeout/انقطاع/إلغاء) ⇒ 'unknown' ومايتعادش تلقائياً أبداً.
- worker واحد بس بيعالج العناصر المؤهّلة طول ما البوت شغال (outbox.py:OutboxWorker).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from telegram.error import TelegramError

from . import db as db_module
from .db import (
    CREATION_CLAIMED,
    CREATION_FAILED,
    CREATION_PENDING,
    CREATION_STARTING,
    CREATION_UNKNOWN,
    OUTBOX_CLAIMED,
    OUTBOX_DISCARDED,
    OUTBOX_FAILED,
    OUTBOX_PENDING,
    OUTBOX_REVIEW_KIND_SUMMARY_DOCUMENT,
    OUTBOX_SENDING,
    OUTBOX_SENT,
    OUTBOX_UNKNOWN,
)
from .errors import ApiError, describe_status, error_text
from .review.authorization import (
    AUTHORIZATION_DATABASE_UNAVAILABLE,
    DELIVERY_CONVERSATION_MISMATCH,
    ReviewAuthorizationError,
    revalidate_review_authorization,
)

log = logging.getLogger(__name__)

# OHB2-POST-PUB-01/F02: أنواع مراجع أعمال الإكمال المحلي المعلّقة (جدول completion_pending).
COMPLETION_KIND_OUTBOX = "outbox"
COMPLETION_KIND_CREATION = "creation"

# فشل مؤكّد (4xx) مش هينجح بإعادة المحاولة؛ غيره (شبكة/مهلة/5xx/429) ممكن يتعاود لو الإرسال مابدأش.
PERMANENT_STATUS = 400
# OHB2-N10-05: 429 (rate limit) **مش** رفض دائم — هو إشارة إعادة محاولة (`errors.describe_status`
# بتقول «جرّب تاني بعد شوية»، والـ Runbook كمان). تصنيفه 'failed' نهائي كان بيسيب البرومت/الشات
# مايتبعتش أبدًا عند rate limit عابر. الغموض عند مرحلة الـ POST (sending ⇒ unknown) هو اللي بيحمي
# at-most-once، مش تصنيف الفشل — فأول ما الـ POST يبدأ، 429 كمان بيتسجّل 'unknown' (مش إعادة تلقائية).
# ملاحظة: بنستثني 429 بس حسب دليل OpenHands؛ لو اتأكد إن الـ API بيرجّع 408/425 كمان، يتضافوا هنا.
RETRYABLE_STATUSES = frozenset({429})

# حد إعادة المحاولة الآمنة (TASK 53): كل مرة إرسال مابدأش فيها (sandbox مش جاهز أو فشل
# قبل الـ POST) بتزوّد attempts. بعد ما attempts يوصل الحد ده، بنوقف المحاولات ونعلّم
# السجل 'failed' — عشان السجل مايفضلش يتعاود للأبد، والإشعار مايتكرّرش كل دورة.
# السجلات اللي الـ POST بتاعها بدأ (sending/unknown) خارج الحد ده تمامًا: عمرها ما
# تتاخد تلقائيًا تاني (at-most-once). الحد ده مابيغيّرش أي حاجة في مسار النجاح.
MAX_OUTBOX_ATTEMPTS = 5

# إشعار موحّد للعمليات الغامضة (مايتعادش تلقائياً — محتاجة مراجعة يدوية).
_UNKNOWN_CREATION_NOTICE = (
    "مش قادرين نتأكد إن الشات الجديد بدأ. راجعه من الموقع قبل ما تعيد المحاولة."
)

# إشعارات مسار الإرسال: إشعار واحد عند أول محاولة آمنة فاشلة (مؤقّت)، وإشعار واحد
# عند استنفاد الحد (نهائي). ما بنكرّرش نفس الرسالة كل دورة.
_SANDBOX_NOT_READY_NOTICE = "الـ sandbox مش قادر يشتغل، جرّب تفتح الشات من الموقع."
_OUTBOX_EXHAUSTED_NOTICE = (
    "تعذّر إرسال البرومت بعد عدة محاولات. جرّب تفتح الشات من الموقع وابعت البرومت من هناك."
)
# هدف مختار اتأكد إنه غير موجود/اتحذف (مش خطأ عابر). لا نوجّه البرومت لشات آخر.
_TARGET_UNAVAILABLE_NOTICE = (
    "الشات المحدد مش موجود أو اتشال. افتح شات تاني وابعت رسالتك."
)
# Empty/ambiguous metadata is not deletion proof. Keep the target and retry safely.
_TARGET_UNCERTAIN_NOTICE = (
    "مش قادرين نتأكد إن الشات المحدد موجود. جرّب تاني، ولو استمرت المشكلة افتحه من الموقع."
)

# OHB2-POST-PUB-01/F02: نصوص الإكمال المحلي (ثابتة ⇒ الإشعار القابل للتعافي يعيد نفس النص).
_OUTBOX_SENT_NOTICE = "اتبعت ✅ الشات اتضاف للمتابعة."
_CREATION_DONE_LINK_TEMPLATE = "بدأ الشات ✅\n{link}"

# OHB2-TELEGRAM-MESSAGE-CLEANUP: مرحلتان متتاليتان بعد نجاح التسليم.
CLEANUP_ORIGINAL_DELAY_SECONDS = 5.0
CLEANUP_CONFIRMATION_DELAY_SECONDS = 5.0
CLEANUP_RETRY_DELAY_SECONDS = 5.0
MAX_CLEANUP_ATTEMPTS = 3
_cleanup_tasks: set[asyncio.Task] = set()
_cleanup_keys: set[int] = set()


def _creation_done_notice(base_url: str, conversation_id: str) -> str:
    link = f"{base_url.rstrip('/')}/canvas/conversations/{conversation_id}"
    return _CREATION_DONE_LINK_TEMPLATE.format(link=link)


def now_iso() -> str:
    """طابع زمني UTC بترتيب ISO-8601 (بيترتّب نصيّاً صح)."""
    return datetime.now(timezone.utc).isoformat()


def _utcnow() -> datetime:
    """ساعة UTC واحدة؛ بنقراها مرة واحدة في العملية اللي محتاجة طابع زمني متّسق."""
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def grouping_mature_before(window: timedelta | None = None, now: datetime | None = None) -> str:
    """حدّ نضج سجل 'pending' قبل الحجز = نهاية نافذة الخمول الحالية.

    السجل يمثّل دفعة NEW-04؛ `updated_at` بيتحدّث مع كل جزء، والنافذة دي بتضمن إن الـ
    worker ما يحجزش قبل مرور 3 ثوانٍ من آخر جزء. بنقرأ db_module.GROUP_WINDOW وقت
    النداء (مش كقيمة افتراضية متثبّتة) عشان الاختبارات تقدر تصغّر النافذة بشكل حتمي.
    """
    current = now or datetime.now(timezone.utc)
    return _iso(current - (window if window is not None else db_module.GROUP_WINDOW))


async def safe_send(bot, chat_id: int, text: str) -> None:
    """إرسال رسالة تيليجرام من غير ما يرمي (فشل الإشعار مايأثرش على حالة الصندوق)."""
    try:
        await bot.send_message(chat_id=chat_id, text=text)
    except TelegramError as exc:
        log.warning("فشل إرسال رسالة تيليجرام (%s)", type(exc).__name__)


async def safe_send_checked_message(bot, chat_id: int, text: str) -> tuple[bool, object | None]:
    """يرسل رسالة ويحتفظ بكائن Telegram Message الناتج (لو رجع).

    الفشل يُبلَّغ كـ `(False, None)`؛ النجاح `(True, message_or_None)` — بعض الاختبارات
    والـ fake bots بترجّع None من `send_message`، فما نعتبرش None فشلًا.
    """
    try:
        message = await bot.send_message(chat_id=chat_id, text=text)
        return True, message
    except TelegramError as exc:
        log.warning("فشل إرسال رسالة تيليجرام (%s)", type(exc).__name__)
        return False, None


async def safe_send_checked(bot, chat_id: int, text: str) -> bool:
    """OHB2-POST-PUB-01/F02: زي `safe_send` بس **بترجّع** هل الإرسال نجح.

    بنستخدمها في مسار الإكمال المحلي القابل للتعافي: لو الإرسال فشل، بنسيب العمل المعلّق
    عشان يتعافى (بدون إعادة أي عملية خارجية). عقد «مفيش exactly-once»: نجاح الإرسال هنا
    معناه إن تيليجرام قبل الرسالة، مش ضمان عدم التكرار لو انقطع بين الإرسال والتسجيل.
    """
    delivered, _ = await safe_send_checked_message(bot, chat_id, text)
    return delivered


async def _safe_delete_message(bot, chat_id: int, message_id: int) -> bool:
    """يحذف رسالة تيليجرام بأمان؛ الحذف المتكرر/الفاشل لا يغيّر نتيجة التسليم."""
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except TelegramError as exc:
        # BadRequest «message to delete not found» حالة سليمة (محذوفة بالفعل).
        log.info(
            "تعذّر حذف رسالة تيليجرام %s/%s (%s) — لا يؤثر على التسليم",
            chat_id, message_id, type(exc).__name__,
        )
        return False
    except Exception as exc:  # noqa: BLE001 — فشل الحذف لا يغيّر نجاح التسليم
        log.warning(
            "خطأ غير متوقّع عند حذف رسالة تيليجرام %s/%s (%s)",
            chat_id, message_id, type(exc).__name__,
        )
        return False


async def _delete_after_delivery(
    bot,
    chat_id: int,
    original_message_ids: tuple[int, ...],
    confirmation_message_id: int | None,
    *,
    sleep=asyncio.sleep,
) -> None:
    """T+5: حذف رسائل المالك الأصلية، ثم T+10: حذف رسالة التأكيد."""
    try:
        await sleep(CLEANUP_ORIGINAL_DELAY_SECONDS)
        for message_id in original_message_ids:
            await _safe_delete_message(bot, chat_id, message_id)
        await sleep(CLEANUP_CONFIRMATION_DELAY_SECONDS)
        if confirmation_message_id is not None:
            await _safe_delete_message(bot, chat_id, confirmation_message_id)
    except asyncio.CancelledError:
        # إيقاف التطبيق/إلغاء المهمة: لا ندّعي أن الحذف اكتمل.
        raise
    except Exception as exc:  # noqa: BLE001 — مهمة تنظيف لا تُسقط الـ worker
        log.warning("فشل جدولة/تنفيذ حذف رسائل بعد التسليم (%s)", type(exc).__name__)


async def cancel_cleanup_tasks() -> None:
    """يلغي مهام الحذف المعلّقة عند إغلاق التطبيق (بلا ادّعاء إتمام الحذف)."""
    tasks = tuple(_cleanup_tasks)
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    _cleanup_tasks.clear()
    _cleanup_keys.clear()


def _cleanup_delay_seconds(next_at: str | None) -> float:
    due = db_module._parse_iso(next_at)
    if due is None:
        return 0.0
    return max(0.0, (due - datetime.now(timezone.utc)).total_seconds())


async def _delete_message_for_cleanup(bot, chat_id: int, message_id: int) -> bool:
    """Delete one tracked message; treat Telegram's already-absent reply as success."""
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except TelegramError as exc:
        text = str(exc).lower()
        if "not found" in text or "message to delete not found" in text:
            return True
        log.info(
            "تعذّر حذف رسالة تيليجرام %s/%s (%s) — سيُعاد المحاولة",
            chat_id, message_id, type(exc).__name__,
        )
        return False
    except Exception as exc:  # noqa: BLE001 — cleanup failure never changes delivery
        log.warning(
            "خطأ غير متوقّع عند حذف رسالة تيليجرام %s/%s (%s)",
            chat_id, message_id, type(exc).__name__,
        )
        return False


async def _delete_cleanup_ids(bot, chat_id: int, ids: tuple[int, ...]) -> bool:
    ok = True
    for message_id in ids:
        if not await _delete_message_for_cleanup(bot, chat_id, message_id):
            ok = False
    return ok


async def _run_persisted_cleanup(db, bot, outbox_id: int, *, sleep=asyncio.sleep) -> None:
    """Resume the durable two-stage cleanup from the outbox row.

    Stage 1: originals + tracked acknowledgements at T+5.
    Stage 2: the final completion notice at T+10.
    A partial deletion is persisted and retried; it is never reported as complete.
    """
    while True:
        item = db.get_outbox(outbox_id)
        if item is None:
            return
        if item.cleanup_state == db_module.CLEANUP_ORIGINALS_PENDING:
            delay = _cleanup_delay_seconds(item.cleanup_next_at)
            if delay > 0:
                await sleep(delay)
            item = db.get_outbox(outbox_id)
            if item is None or item.cleanup_state != db_module.CLEANUP_ORIGINALS_PENDING:
                continue
            ids = tuple(dict.fromkeys(item.telegram_message_ids + item.ack_message_ids))
            if not await _delete_cleanup_ids(bot, item.chat_id, ids):
                attempts = db.record_outbox_cleanup_retry(
                    outbox_id, now_iso(),
                    delay_seconds=CLEANUP_RETRY_DELAY_SECONDS,
                    error="تعذّر حذف رسائل البرومت الأصلية/الإقرار",
                )
                if attempts >= MAX_CLEANUP_ATTEMPTS:
                    db.mark_outbox_cleanup_failed(
                        outbox_id, "استنفد محاولات حذف رسائل البرومت/الإقرار"
                    )
                    return
                continue
            if item.cleanup_confirmation_message_id is None:
                db.mark_outbox_cleanup_failed(
                    outbox_id, "معرّف رسالة التأكيد غير متاح — لا ندّعي اكتمال التنظيف"
                )
                return
            db.mark_outbox_cleanup_originals_done(
                outbox_id, now_iso(), delay_seconds=CLEANUP_CONFIRMATION_DELAY_SECONDS
            )
            continue
        if item.cleanup_state == db_module.CLEANUP_CONFIRMATION_PENDING:
            delay = _cleanup_delay_seconds(item.cleanup_next_at)
            if delay > 0:
                await sleep(delay)
            item = db.get_outbox(outbox_id)
            if item is None or item.cleanup_state != db_module.CLEANUP_CONFIRMATION_PENDING:
                continue
            confirmation_id = item.cleanup_confirmation_message_id
            if confirmation_id is None:
                db.mark_outbox_cleanup_failed(
                    outbox_id, "معرّف رسالة التأكيد غير متاح — لا ندّعي اكتمال التنظيف"
                )
                return
            if await _delete_message_for_cleanup(bot, item.chat_id, confirmation_id):
                db.mark_outbox_cleanup_done(outbox_id)
                return
            attempts = db.record_outbox_cleanup_retry(
                outbox_id, now_iso(),
                delay_seconds=CLEANUP_RETRY_DELAY_SECONDS,
                error="تعذّر حذف رسالة التأكيد",
            )
            if attempts >= MAX_CLEANUP_ATTEMPTS:
                db.mark_outbox_cleanup_failed(
                    outbox_id, "استنفد محاولات حذف رسالة التأكيد"
                )
                return
            continue
        return


def schedule_delivery_cleanup(
    bot,
    chat_id: int,
    original_message_ids: tuple[int, ...],
    confirmation_message_id: int | None,
    *,
    key: int | None = None,
    ack_message_ids: tuple[int, ...] = (),
    db=None,
    outbox_id: int | None = None,
    sleep=asyncio.sleep,
) -> None:
    """Schedule cleanup once per outbox row.

    With `db`/`outbox_id`, the durable row state is authoritative and a restart can
    resume the same cleanup. Without them, the legacy one-shot task is kept for
    existing callers/tests that do not have a persisted outbox row.
    """
    if key is not None and key in _cleanup_keys:
        return
    if db is not None and outbox_id is not None:
        task_coro = _run_persisted_cleanup(db, bot, outbox_id, sleep=sleep)
    else:
        if not original_message_ids and not ack_message_ids and confirmation_message_id is None:
            return
        task_coro = _delete_after_delivery(
            bot,
            chat_id,
            tuple(original_message_ids) + tuple(ack_message_ids),
            confirmation_message_id,
            sleep=sleep,
        )
    if key is not None:
        _cleanup_keys.add(key)
    task = asyncio.create_task(task_coro)
    _cleanup_tasks.add(task)

    def _done(completed: asyncio.Task) -> None:
        _cleanup_tasks.discard(completed)
        if key is not None:
            _cleanup_keys.discard(key)

    task.add_done_callback(_done)


def resume_outbox_cleanup(app) -> None:
    """Reschedule durable cleanup rows after restart using existing cleanup tasks."""
    db = app.bot_data["db"]
    for item in db.list_outbox_cleanup_pending():
        schedule_delivery_cleanup(
            app.bot,
            item.chat_id,
            item.telegram_message_ids,
            item.cleanup_confirmation_message_id,
            key=item.id,
            ack_message_ids=item.ack_message_ids,
            db=db,
            outbox_id=item.id,
        )


def safe_error_label(exc: ApiError) -> str:
    """وصف مختصر آمن للخطأ (من غير نص الاستثناء أو جسم الرد الخام)."""
    if exc.status_code is not None:
        return f"HTTP {exc.status_code}"
    return "تعذّر الاتصال (نتيجة غامضة)"


def safe_exception_label(exc: BaseException) -> str:
    """وصف مختصر آمن لأي استثناء (من غير النص الخام، ممكن يحوي أسرار).

    OHB2-WP-05 (DEF-012): فروع الاستطلاع العامة كانت بتستدعي `safe_error_label`
    المخصّص لـ `ApiError` فقط، فكان أي استثناء غير `ApiError` يرمي `AttributeError`.
    هنا بنميّز: `ApiError` ⇒ التسمية الموجودة؛ غيره ⇒ نوع الاستثناء فقط.
    """
    if isinstance(exc, ApiError):
        return safe_error_label(exc)
    return f"خطأ غير متوقع ({type(exc).__name__})"


def is_permanent(exc: ApiError) -> bool:
    """رفض نهائي مؤكد؟ (4xx) — غير كده غامض/مؤقت.

    استثناء: 429 (rate limit) مؤقت/قابل لإعادة المحاولة، فمش نهائي (OHB2-N10-05).
    """
    return (
        exc.status_code is not None
        and PERMANENT_STATUS <= exc.status_code < 500
        and exc.status_code not in RETRYABLE_STATUSES
    )


async def get_conversation(client, conversation_id: str) -> dict:
    convs = await client.get_conversations([conversation_id])
    return convs[0] if convs else {}


# ------------------------------------------------------------- F02 completion
async def _complete_outbox(db, bot, item, base_url: str = "") -> None:
    """إكمال الأثر المحلي للـ outbox (إشعار + تسجيل متابعة) — idempotent وقابل للتعافي.

    بيفترض إن صف `completion_pending` (kind=outbox) مسجّل بالفعل. الترتيب:
    1) نسجّل المتابعة/الحالة (idempotent)، 2) نبعت الإشعار عبر
    `safe_send_checked_message`، 3) لو الإرسال نجح **بس** نشيل العمل المعلّق،
    4) نجدول حذف رسائل المالك الأصلية ثم رسالة التأكيد بعد التأخيرين. لو الإرسال فشل
    (TelegramError)، بنسيب العمل المعلّق ⇒ تعافٍ لاحق. فشل خطوة التسجيل (1) بيطلع
    استثناء ويسيب العمل المعلّق كمان (يتعافى). الإكمال المحلي **ما بيعملش** أي POST
    خارجي (at-most-once محفوظ).
    """
    # OHB2-C7: حرس عدم الإحياء — لو الشات اتحذف محليًا (صف الإكمال اتشال في نفس معاملة
    # الحذف)، ما نعيدش إنشاء المتابعة ولا نبعت إشعار لشات ملغي. الفحص + الكتابة في نفس
    # البلوك المتزامن (مفيش await بينهم)، فالحذف ما يقدرش يتخلّل بينهم.
    # OHB2-C7 (RESURRECTION-FIX): لو `item is None` فده معناه إن intent الإكمال اتمنع لأن
    # الشات متشاهد حذف (POST نجح خارجيًا بس مفيش عمل محلي) ⇒ مفيش حاجة نعملها.
    if item is None or db.get_completion_pending(COMPLETION_KIND_OUTBOX, item.ref_id) is None:
        return
    if db.is_deleted(item.conversation_id):
        return
    db.add_watched(item.conversation_id, item.title or "", item.chat_id)
    db.set_last_state(item.conversation_id, item.last_state or "")
    db.mark_submitted(item.conversation_id, item.submitted_at or now_iso())
    # لا نعلن «اتضاف للمتابعة» إلا بعد التحقق الفعلي من تسجيل المتابعة.
    if not db.is_watched(item.conversation_id):
        log.warning("إكمال %s: المتابعة لم تُسجَّل — لن نعلن النجاح", item.ref_id)
        return
    notice = item.notice_text or _OUTBOX_SENT_NOTICE
    delivered, confirmation = await safe_send_checked_message(bot, item.chat_id, notice)
    if delivered:
        # التنظيف يبدأ فقط الآن: بعد تأكيد POST + تسجيل المتابعة + إرسال التأكيد.
        try:
            outbox_item = db.get_outbox(item.ref_id)
            original_ids = (
                outbox_item.telegram_message_ids if outbox_item is not None else ()
            )
            ack_ids = outbox_item.ack_message_ids if outbox_item is not None else ()
            confirmation_id = getattr(confirmation, "message_id", None)
            if not isinstance(confirmation_id, int) or isinstance(confirmation_id, bool):
                confirmation_id = None
            if original_ids and confirmation_id is None:
                log.warning(
                    "إكمال %s: اتأكد التسليم لكن معرّف رسالة التأكيد غير متاح — "
                    "حذف التأكيد غير مضمون", item.ref_id,
                )
            # Persist the plan before clearing the completion intent, so a restart can
            # resume. If this write fails, completion_pending stays and is recovered.
            db.begin_outbox_cleanup(
                item.ref_id,
                confirmation_id,
                now_iso(),
                delay_seconds=CLEANUP_ORIGINAL_DELAY_SECONDS,
            )
            db.clear_completion_pending(COMPLETION_KIND_OUTBOX, item.ref_id)
            schedule_delivery_cleanup(
                bot,
                item.chat_id,
                original_ids,
                confirmation_id,
                key=item.ref_id,
                ack_message_ids=ack_ids,
                db=db,
                outbox_id=item.ref_id,
            )
        except Exception as exc:  # noqa: BLE001 — فشل الجدولة لا يغيّر نجاح التسليم
            log.warning(
                "تعذّر جدولة حذف رسائل التسليم للسجل %s (%s)",
                item.ref_id, type(exc).__name__,
            )


async def _complete_creation(db, bot, item, base_url: str = "") -> None:
    """إكمال الأثر المحلي لطلب الشات الجديد (إشعار الرابط + تسجيل متابعة).

    زي `_complete_outbox` بالظبط: idempotent، بيسيب العمل المعلّق لو الإشعار فشل،
    وما بيعملش أي POST خارجي (ما بيعيدش إنشاء الشات أبدًا — الرابط/المعرّف محفوظين).
    لو `notice_text` فاضي (صف مسترجع من تسوية قديمة) بنبني الرابط من معرّف المحادثة.
    """
    # OHB2-C7: حرس عدم الإحياء (زي `_complete_outbox`) — شات اتحذف محليًا مايتعادش
    # إنشاء متابعته ولا يتبعتله إشعار.
    # OHB2-C7 (RESURRECTION-FIX): `item is None` ⇒ intent الإكمال اتمنع لشات متشاهد ⇒ تخطّي.
    if item is None or db.get_completion_pending(COMPLETION_KIND_CREATION, item.ref_id) is None:
        return
    if db.is_deleted(item.conversation_id):
        return
    db.add_watched(item.conversation_id, item.title or "", item.chat_id)
    db.set_last_state(item.conversation_id, item.last_state or "running")
    notice = item.notice_text or _creation_done_notice(base_url, item.conversation_id)
    delivered = await safe_send_checked(bot, item.chat_id, notice)
    if delivered:
        db.clear_completion_pending(COMPLETION_KIND_CREATION, item.ref_id)


async def wait_running(client, conversation_id: str, interval: float, timeout: float) -> str:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        await asyncio.sleep(interval)
        conv = await get_conversation(client, conversation_id)
        status = str(conv.get("sandbox_status", "")).upper()
        if status == "RUNNING":
            return status
    return "UNKNOWN"


async def deliver_outbox(client, db, bot, outbox_id: int) -> None:
    """مسار مباشر: نحجز **السجل المطلوب نفسه** ذرّياً ثم نرسله عبر _post_claimed.

    OHB2-WP-05 (DEF-008): كان بيستدعي `claim_outbox` غير المُقيَّد بالمعرّف، فيمكن أن
    يحجز ويرسل سجلًا آخر (أقدم) غير المطلوب، ويتخطّى تأخير النضج (`GROUP_WINDOW`).
    دلوقتي بنحجز `outbox_id` نفسه ذرّياً (`claim_outbox_by_id`) عشان ما نلمسش سجلًا
    تاني، ونكمل عبر `_post_claimed` (نفس مسار الـ worker).
    """
    item = db.get_outbox(outbox_id)
    if item is None or item.status != OUTBOX_PENDING:
        return
    claimed = db.claim_outbox_by_id(outbox_id, now_iso())
    if claimed is None:
        return
    await _post_claimed(client, db, bot, claimed)


def _tombstoned(db, conversation_id: str) -> bool:
    """هل الشات عليه شاهد حذف فعّال؟ **فشل مغلق**: أي خطأ قراءة ⇒ نعتبره متشاهد.

    نفس سلوك حرّاس المراقب/المُبلّل: مسار إشعار المستخدم مايتكلّمش مع شات محذوف، وفشل
    قراءة الشاهد أأمن نتيجته تخطّي الإرسال (مش إرسال محتمل لشات محذوف).

    **قصدًا** حرّاس **القرار** في `_post_claimed` (المدخل + حدّ CAS) بتستخدم `db.is_deleted`
    مباشرةً: خطأ قراءة هناك المفروض يطلع استثناء **قبل أي إرسال**. والحرس اللي بيمسك الاستثناء
    غير المتوقّع (F-01) بعد كده بيرجّع السجل **'pending'** بـ CAS من 'claimed' (الـ POST
    مابدأش ⇒ آمن)، أو 'failed' عند استنفاد الحد — والـ CAS من 'claimed' بس، فمستحيل يلخبط
    سجل اتشطب/اتحسم بالتوازي. الحرس fail-closed ده للـ **إشعارات** بس، عشان خطأ عابر مايخلّيش
    الإشعار يروح لشات محذوف.
    """
    try:
        return db.is_deleted(conversation_id)
    except Exception:  # noqa: BLE001 — قاعدة غير متاحة ⇒ فشل مغلق (تخطّي)
        log.warning(
            "تعذّر قراءة شاهد الحذف للشات %s؛ هيتخطّى إشعار المستخدم (فشل مغلق).",
            conversation_id,
        )
        return True


def _is_selected_target(db, chat_id: int, conversation_id: str) -> bool:
    """هل الشات هو الهدف المحفوظ؟ فشل القراءة ⇒ False (ما نصنّفش حذفًا بلا دليل)."""
    try:
        return db.get_last_accessed_conversation(chat_id) == conversation_id
    except Exception as exc:  # noqa: BLE001 — غياب الدليل لا يساوي حذفًا
        log.warning(
            "تعذّر قراءة هدف التوجيه المحفوظ %s (%s)",
            conversation_id,
            type(exc).__name__,
        )
        return False


def _clear_unavailable_selection(db, chat_id: int, conversation_id: str) -> bool:
    """يمسح هدف التوجيه غير المتاح **ذرّيًّا**، فقط لو ما زال هو الهدف الحالي.

    الشات/الـ chat_id هنا مالك خاص (outbox owner)، ومسح هدف آخر ممنوع. العملية كلها
    في معاملة واحدة: أي فشل يرجع False، والحالة القديمة تفضل كما هي. الفشل لا يغيّر
    نتيجة التسليم، لكنه يمنع إرسال إشعار «تم التعامل مع الهدف» على أنه نجاح.
    """
    try:
        db.clear_unavailable_selection(chat_id, conversation_id)
        return True
    except Exception:  # noqa: BLE001 — مسح اختياري لا يغيّر حكم التسليم
        log.exception(
            "تعذّر مسح هدف التوجيه غير المتاح %s",
            conversation_id,
        )
        return False


async def _recover_pre_cas_unexpected(db, bot, item, exc: BaseException) -> None:
    """F-01: تعافي آمن لاستثناء **غير متوقّع** وقع في مرحلة ما قبل CAS الإرسال.

    المرحلة دي كلها قبل CAS `claimed`⇒`sending`، يعني الـ POST **مابدأش** خالص، فالسجل
    ممكن يفضل 'claimed' لو الاستثناء خرج من نداء بعيد (قراءة الشات/تشغيل الـ sandbox).
    من غير التعافي ده السجل يفضل عالقًا لحد إعادة تشغيل العملية. نرجّعه **'pending'** بنفس
    سياسة المحاولات الموجودة بالظبط (نفس `bump_outbox_attempt`/`MAX_OUTBOX_ATTEMPTS`/CAS من
    'claimed') — مفيش سياسة جديدة ولا إعادة إرسال ولا حلقة.

    - مفيش `await` بين قراءة العدّاد والـ CAS، والـ CAS من 'claimed' بس: أي تغيير متوازي
      (شطب/حسم) ⇒ rowcount=0 ⇒ ما بنلمسش حاجة (مفيش clobber، مفيش إحياء).
    - لو عملية التعافي نفسها فشلت (قاعدة غير متاحة) بنسجّل الفشل **مع** الاستثناء الأصلي
      وما بنعلنش نجاح (مفيش ادّعاء تعافٍ وهمي).
    """
    outbox_id = item.id
    label = f"خطأ غير متوقع ({type(exc).__name__})"
    try:
        attempts = db.bump_outbox_attempt(outbox_id, now_iso(), label)
    except Exception:  # noqa: BLE001 — فشل التعافي نفسه: نسجّل الاستثناء الأصلي، ما نعلنش نجاح
        log.exception(
            "فشل تعافي السجل %s بعد خطأ غير متوقّع قبل CAS الإرسال (%s)",
            outbox_id, type(exc).__name__,
        )
        return
    if attempts == 0:
        # السجل مش مملوك لينا دلوقتي (اتشطب/اتحسم بالتوازي) ⇒ ما نلمسش حاجة.
        return
    try:
        if attempts >= MAX_OUTBOX_ATTEMPTS:
            changed = db.set_outbox_status_if_in(
                outbox_id, OUTBOX_FAILED, now_iso(), {OUTBOX_CLAIMED},
                f"استنفد {attempts} محاولات",
            )
            if changed and not _tombstoned(db, item.conversation_id):
                await safe_send(bot, item.chat_id, _OUTBOX_EXHAUSTED_NOTICE)
        else:
            changed = db.set_outbox_status_if_in(
                outbox_id, OUTBOX_PENDING, now_iso(), {OUTBOX_CLAIMED}, label
            )
            if changed:
                log.info("تعافي pre-CAS: السجل %s رجع 'pending' (خطأ غير متوقّع)", outbox_id)
                if attempts == 1 and not _tombstoned(db, item.conversation_id):
                    await safe_send(bot, item.chat_id, f"فشل الإرسال: {error_text(exc)}")
    except Exception:  # noqa: BLE001 — فشل كتابة التعافي: نسجّل، وما نعلنش نجاح
        log.exception(
            "فشل كتابة تعافي السجل %s بعد خطأ غير متوقّع قبل CAS الإرسال", outbox_id
        )


async def _retry_pre_cas(db, bot, item, reason: str, notice: str | None) -> None:
    """Safe pre-POST retry without clearing the selected target.

    Used for transient sandbox/metadata failures and for ambiguous empty metadata.
    A 404/410 from conversation metadata is handled separately as confirmed missing.
    """
    attempts = db.bump_outbox_attempt(item.id, now_iso(), reason)
    if attempts == 0:
        return
    if attempts >= MAX_OUTBOX_ATTEMPTS:
        db.set_outbox_status_if_in(
            item.id, OUTBOX_FAILED, now_iso(), {OUTBOX_CLAIMED},
            f"استنفد {attempts} محاولات ({reason})",
        )
        if not _tombstoned(db, item.conversation_id):
            await safe_send(bot, item.chat_id, _OUTBOX_EXHAUSTED_NOTICE)
        return
    db.set_outbox_status_if_in(
        item.id, OUTBOX_PENDING, now_iso(), {OUTBOX_CLAIMED}, reason
    )
    if attempts == 1 and notice and not _tombstoned(db, item.conversation_id):
        await safe_send(bot, item.chat_id, notice)


def _handle_review_authorization_failure(db, item, exc: ReviewAuthorizationError) -> None:
    """Fail closed without sending to an unauthorized target or losing recoverable work."""
    if exc.retryable:
        attempts = db.bump_outbox_attempt(item.id, now_iso(), exc.code)
        if attempts == 0:
            return
        if attempts >= MAX_OUTBOX_ATTEMPTS:
            db.set_outbox_status_if_in(
                item.id, OUTBOX_FAILED, now_iso(), {OUTBOX_CLAIMED}, exc.code
            )
        else:
            db.set_outbox_status_if_in(
                item.id, OUTBOX_PENDING, now_iso(), {OUTBOX_CLAIMED}, exc.code
            )
        return
    db.set_outbox_status_if_in(
        item.id, OUTBOX_FAILED, now_iso(), {OUTBOX_CLAIMED}, exc.code
    )
    log.warning("review delivery denied (%s)", exc.code)


def _review_authorization(db, item, review_owner_id) -> None:
    try:
        cycle = db.get_auto_review(item.review_id)
    except Exception as exc:  # noqa: BLE001 - never authorize from a failed read
        raise ReviewAuthorizationError(
            AUTHORIZATION_DATABASE_UNAVAILABLE, retryable=True
        ) from exc
    if cycle is not None and item.conversation_id != cycle.conversation_id:
        raise ReviewAuthorizationError(DELIVERY_CONVERSATION_MISMATCH)
    revalidate_review_authorization(
        db,
        owner_id=review_owner_id,
        cycle=cycle,
        target_chat_id=item.chat_id,
        phase="delivery",
    )


async def _post_claimed_review(db, bot, item, *, review_owner_id=None) -> None:
    """Deliver one persisted R6 report through the existing outbox row.

    The report is loaded from the immutable R6 table; the outbox row carries only
    the summary/filename/version intent. The CAS to ``sending`` happens before the
    Telegram call, so a duplicate completion cannot send the same report twice.
    """
    from telegram import InputFile
    from telegram.constants import ParseMode
    from telegram.error import BadRequest

    from .messages import escape_html
    from .review.report import review_actions_markup

    current = db.get_outbox(item.id)
    if current is None or current.status != OUTBOX_CLAIMED:
        return
    if item.review_kind not in (None, OUTBOX_REVIEW_KIND_SUMMARY_DOCUMENT):
        db.set_outbox_status_if_in(
            item.id, OUTBOX_FAILED, now_iso(), {OUTBOX_CLAIMED}, "unsupported_review_kind"
        )
        return
    if item.review_version is None:
        db.set_outbox_status_if_in(
            item.id, OUTBOX_FAILED, now_iso(), {OUTBOX_CLAIMED}, "review_version_missing"
        )
        return
    try:
        _review_authorization(db, item, review_owner_id)
    except ReviewAuthorizationError as exc:
        _handle_review_authorization_failure(db, item, exc)
        return
    report = db.get_auto_review_report(item.review_id, item.review_version)
    if (
        report is None
        or report.review_id != item.review_id
        or (item.review_report_id is not None and report.id != item.review_report_id)
    ):
        db.set_outbox_status_if_in(
            item.id, OUTBOX_FAILED, now_iso(), {OUTBOX_CLAIMED}, "review_report_missing"
        )
        log.warning("review delivery skipped: report missing for %s", item.review_id)
        return
    try:
        _review_authorization(db, item, review_owner_id)
    except ReviewAuthorizationError as exc:
        _handle_review_authorization_failure(db, item, exc)
        return
    if not db.set_outbox_status_if_in(
        item.id, OUTBOX_SENDING, now_iso(), {OUTBOX_CLAIMED}
    ):
        return
    try:
        _review_authorization(db, item, review_owner_id)
    except ReviewAuthorizationError as exc:
        db.set_outbox_status_if_in(
            item.id, OUTBOX_UNKNOWN, now_iso(), {OUTBOX_SENDING}, exc.code
        )
        log.warning("review delivery authorization changed before send (%s)", exc.code)
        return
    try:
        await bot.send_document(
            chat_id=item.chat_id,
            document=InputFile(report.content.encode("utf-8"), filename=report.filename),
            caption=escape_html(report.summary),
            parse_mode=ParseMode.HTML,
            reply_markup=review_actions_markup(report.review_id, report.version),
        )
    except asyncio.CancelledError:
        db.set_outbox_status_if_in(
            item.id, OUTBOX_UNKNOWN, now_iso(), {OUTBOX_SENDING}, "cancelled"
        )
        raise
    except BadRequest as exc:
        db.set_outbox_status_if_in(
            item.id, OUTBOX_FAILED, now_iso(), {OUTBOX_SENDING}, type(exc).__name__
        )
        log.warning("review delivery rejected (%s)", type(exc).__name__)
        return
    except TelegramError as exc:
        # Telegram accepted no confirmed result; never retry automatically after
        # the sending boundary. The cycle stays unknown, not sent.
        db.set_outbox_status_if_in(
            item.id, OUTBOX_UNKNOWN, now_iso(), {OUTBOX_SENDING}, type(exc).__name__
        )
        log.warning("review delivery ambiguous (%s)", type(exc).__name__)
        return
    except Exception as exc:  # noqa: BLE001 - after sending, at-most-once
        db.set_outbox_status_if_in(
            item.id, OUTBOX_UNKNOWN, now_iso(), {OUTBOX_SENDING}, type(exc).__name__
        )
        log.warning("review delivery unexpected failure (%s)", type(exc).__name__)
        return
    try:
        _review_authorization(db, item, review_owner_id)
    except ReviewAuthorizationError as exc:
        db.set_outbox_status_if_in(
            item.id, OUTBOX_UNKNOWN, now_iso(), {OUTBOX_SENDING}, exc.code
        )
        log.warning("review delivery authorization changed after send (%s)", exc.code)
        return
    db.set_outbox_status_if_in(item.id, OUTBOX_SENT, now_iso(), {OUTBOX_SENDING})
    return


async def _post_claimed(client, db, bot, item, *, review_owner_id=None) -> None:
    """يحاول الـ POST لعنصر محجوز (claimed) ولسه الإرسال مابدأش.

    at-most-once: بنسجّل 'sending' بـ **CAS ذرّي** (`claimed`⇒`sending`) فوراً قبل الـ POST
    بالظبط. لو المستخدم شطب العنصر أثناء التحضير (قراءة الشات/تشغيل الـ sandbox)، الـ CAS
    هيفشل (rowcount=0) وما بنبعتش الـ POST خالص — فمفيش إرسال بعد إلغاء، ومفيش ادّعاء إلغاء
    وهمي. أي إلغاء/انقطاع قبل كده بيسيب 'claimed' ⇒ يتعافى 'pending' (آمن، الـ POST مابدأش).
    أي إلغاء/انقطاع بعد الـ CAS بيسيب 'sending' ⇒ يتعافى 'unknown' (غامض، مايتعادش تلقائياً).

    F-1: بنفرض **شاهد الحذف** (fail-closed) مرتين قبل أي إرسال حامل للمحتوى: عند المدخل
    (قبل أي نداء بعيد) وفورًا قبل CAS الإرسال (بعد التحضير اللي فيه `await` طويل). كده
    أي شاهد يُكتب في **أي لحظة قبل** نجاح CAS `claimed`⇒`sending` بيمنع الإرسال تمامًا —
    ونعلّم السجل `discarded` (CAS من `claimed`). الحدّ الوحيد اللي مابيتغطّاش محليًا هو
    شاهد يُكتب **بعد** نجاح الـ CAS/بدء الـ POST فعلًا: ساعتها الحسم خارجي (شبكة/خدمة
    بعيدة) ومابيتسحبش — والـ CAS في المسار بيتعامل معاه بأمان (النتيجة الغامضة ⇒ 'unknown'
    بلا إعادة إرسال تلقائية).

    F-01: استثناء **غير متوقّع** في مرحلة ما قبل CAS الإرسال (الـ POST مابدأش) مايسيبش السجل
    عالقًا 'claimed': بنرجّعه 'pending' بـ CAS من 'claimed' وبنفس سياسة المحاولات (شوف
    `_recover_pre_cas_unexpected`). أما بعد نجاح الـ CAS، الحالة 'sending' **ما تتلمسش**
    تلقائيًا (at-most-once: ممكن الـ POST يكون اتقبل) — أي استثناء هناك يتحسم داخليًا
    (ApiError ⇒ failed/unknown، CancelledError ⇒ unknown، عام ⇒ unknown) ومايتعادش أبدًا.
    """
    if item.review_id is not None and (
        item.review_kind == OUTBOX_REVIEW_KIND_SUMMARY_DOCUMENT
        or item.review_report_id is not None
    ):
        await _post_claimed_review(db, bot, item, review_owner_id=review_owner_id)
        return

    outbox_id = item.id
    conversation_id = item.conversation_id
    chat_id = item.chat_id
    text = item.text

    # F-1 (إغلاق TOCTOU الحذف): الشات ممكن ياخد شاهد حذف **قبل** ما نوصل هنا. حذف الـ Mini App
    # بيكتب الشاهد و'deleting' **قبل** النداء البعيد (`deletion.delete_conversation_remote`
    # عبر `begin_remote_deletion`)، وسجلات الصندوق **ما بتتشطبش** غير في الإنهاء النهائي
    # (`delete_conversation`) — يعني خلال نافذة deleting/uncertain السجل يفضل 'pending'/'claimed'
    # والـ CAS 'claimed'⇒'sending' بينجح، فيتبعت محتوى شات اتحذف. الحرس ده أول حاجة (fail-closed
    # عند فشل القراءة): لو فيه شاهد ⇒ مفيش أي نداء بعيد خالص، ونعلّم السجل 'discarded' (CAS من
    # 'claimed') عشان مايتعاودش تلقائيًا ومايفضلش عالقًا. فيه حرس **تاني** عند حدّ الـ CAS
    # (قبل الإرسال مباشرة) لتغطية شاهد يُكتب أثناء التحضير (الحالة 3).
    #
    # الحرس ده **جوه** try المرحلة pre-CAS عن قصد (F-01): فشل قراءة الشاهد (SQLite عابر)
    # استثناء غير متوقّع **قبل** الـ CAS ⇒ لازم يتعافى 'pending' (إعادة محاولة) مش يسيب
    # السجل عالقًا 'claimed'. وده بيحقّق النية الموثّقة في `_tombstoned` (الـ worker يرجّع
    # السجل 'pending'). الحماية نفسها محفوظة: الشاهد بيتفحص **قبل** أي نداء بعيد.
    try:
        if db.is_deleted(conversation_id):
            db.set_outbox_status_if_in(
                outbox_id, OUTBOX_DISCARDED, now_iso(), {OUTBOX_CLAIMED}, "اتحذف قبل الإرسال"
            )
            log.info("تخطّي الإرسال: الشات %s عليه شاهد حذف (قبل أي نداء بعيد)", conversation_id)
            return

        try:
            conv = await get_conversation(client, conversation_id)
        except ApiError as exc:
            # Only the conversation metadata call can prove the selected conversation is
            # missing. A 404 from sandbox resume is a sandbox failure, not deletion.
            if exc.status_code in (404, 410) and _is_selected_target(
                db, chat_id, conversation_id
            ):
                db.set_outbox_status_if_in(
                    outbox_id, OUTBOX_FAILED, now_iso(), {OUTBOX_CLAIMED},
                    f"HTTP {exc.status_code}",
                )
                cleared = _clear_unavailable_selection(db, chat_id, conversation_id)
                if cleared and not _tombstoned(db, conversation_id):
                    await safe_send(bot, chat_id, _TARGET_UNAVAILABLE_NOTICE)
                return
            await _retry_pre_cas(
                db, bot, item, safe_error_label(exc), f"فشل الإرسال: {error_text(exc)}"
            )
            return
        if not conv and _is_selected_target(db, chat_id, conversation_id):
            # Empty metadata is ambiguous, not deletion proof. Preserve the target and
            # retry; never fall back to another conversation.
            await _retry_pre_cas(
                db, bot, item, "بيانات الشات فارغة/غامضة", _TARGET_UNCERTAIN_NOTICE
            )
            return
        sandbox_id = conv.get("sandbox_id")
        status = str(conv.get("sandbox_status", "")).upper()

        try:
            if status != "RUNNING" and sandbox_id:
                await client.resume_sandbox(sandbox_id)
                status = await wait_running(
                    client, conversation_id, interval=3.0, timeout=120.0
                )
        except ApiError as exc:
            # Sandbox resume/wait failures (including 404) are transient for routing:
            # the conversation may still exist. Keep the selected target.
            await _retry_pre_cas(db, bot, item, safe_error_label(exc), _SANDBOX_NOT_READY_NOTICE)
            return

        if status != "RUNNING":
            await _retry_pre_cas(db, bot, item, "sandbox غير جاهز", _SANDBOX_NOT_READY_NOTICE)
            return

        # الإرسال هيبدأ حالاً: CAS 'claimed'⇒'sending' بثبات قبل الـ POST مباشرة (الـ commit
        # جوّه set_outbox_status_if_in). ده آخر حد آمن: بعده النتيجة غامضة. لو الـ CAS
        # فشل (المستخدم شطب العنصر في الأثناء) ⇒ مفيش POST خالص.
        #
        # F-1 (إغلاق السباق في النافذة): حرس المدخل فوق بيفحص الشاهد **مرة** قبل التحضير،
        # لكن التحضير (get_conversation ثم resume_sandbox/wait_running — لحد 120 ثانية)
        # فيه `await` طويل. لو الحذف اتخلّل خلاله (الحالة 3)، حرس المدخل بيبقى عدّى. نعيد
        # الفحص هنا **فورًا قبل CAS الإرسال**، ومفيش `await` بين الفحص والـ CAS ⇒ الإرسال
        # مايبدأش أبدًا لو الشاهد اتكتب في أي لحظة قبل حدّ الـ CAS. ده أقوى حدّ محلي ممكن
        # (بعد الـ CAS الحسم خارجي ولا يمكن سحبه). CAS من 'claimed' بس (ما نلخبطش حسمًا أحدث).
        if db.is_deleted(conversation_id):
            db.set_outbox_status_if_in(
                outbox_id, OUTBOX_DISCARDED, now_iso(), {OUTBOX_CLAIMED}, "اتحذف قبل الإرسال"
            )
            log.info("تخطّي الإرسال: الشات %s اتشاهد أثناء التحضير (قبل الـ CAS)", conversation_id)
            return
        submitted_at = now_iso()  # قبل الـ POST: أي حدث للـ run الجديد لازم يكون أحدث منه
        if not db.set_outbox_status_if_in(
            outbox_id, OUTBOX_SENDING, submitted_at, {OUTBOX_CLAIMED}
        ):
            log.info("تخطّي الإرسال: السجل %s مش مملوك (اتشطب/اتغيّر قبل الـ POST)", outbox_id)
            return
    except ApiError as exc:
        # Any remaining ApiError here is pre-POST and not a confirmed metadata deletion.
        # Keep the target and retry safely.
        await _retry_pre_cas(
            db, bot, item, safe_error_label(exc), f"فشل الإرسال: {error_text(exc)}"
        )
        return
    except Exception as exc:  # noqa: BLE001 — F-01: خطأ غير متوقّع **قبل** CAS الإرسال
        # أي استثناء غير `ApiError` (خطأ برمجي/فكّ ترميز/قاعدة بيانات محلية...) قبل CAS
        # `claimed`⇒`sending` معناه الـ POST **مابدأش** ⇒ آمن نرجّع السجل 'pending' بدل ما
        # يفضل عالقًا لحد إعادة التشغيل. التعافي بنفس سياسة المحاولات والـ CAS من 'claimed'.
        #
        # ⚠️ النطاق مهم: الحرس ده بيغطّي **مرحلة ما قبل الـ CAS فقط**. الـ `try` الرئيسي
        # بيتقفل عند نجاح CAS الإرسال؛ أي استثناء بعده (بما فيه `client.send_message`)
        # بيتعالج جوه الـ `try` الداخلي المخصص (ApiError/CancelledError/عام) **مش** هنا،
        # فمستحيل نصنّف فشل ما بعد الـ CAS على إنه آمن. و`asyncio.CancelledError` مش
        # سليل `Exception` (BaseException) فمابيتـcaughtش هنا خالص ⇒ مفيش كتم إلغاء.
        await _recover_pre_cas_unexpected(db, bot, item, exc)
        return

    # ===================== POST-CAS (السجل بقى 'sending' بثبات) =====================
    # المنطقة دي بتشتغل **بس** لو الـ try اللي فوق خلص طبيعيًا، يعني CAS `claimed`⇒`sending`
    # نجح (فشل الـ CAS بيرجع من جوه الـ try قبل ما نوصل هنا). من هنا الـ POST ممكن يبدأ،
    # والنتيجة غامضة، فممنوع أي رجوع تلقائي لـ 'pending' وممنوع أي POST تاني.
    try:
        await client.send_message(conversation_id, text)
    except ApiError as exc:
        # رفض مؤكد (4xx) ⇒ 'failed'؛ غير كده (شبكة/مهلة/5xx/429) ⇒ 'unknown' — مش إعادة
        # تلقائية. CAS من 'sending' بس: لو حالة أحدث (نهائية) حسمت السجل، ما نلخبطهاش.
        if exc.status_code in (404, 410) and _is_selected_target(db, chat_id, conversation_id):
            # 404/410 بعد CAS للهدف المحفوظ = الخدمة أكّدت إنه غير موجود/اتحذف؛ لا fallback.
            db.set_outbox_status_if_in(
                outbox_id, OUTBOX_FAILED, now_iso(), {OUTBOX_SENDING},
                f"HTTP {exc.status_code}",
            )
            cleared = _clear_unavailable_selection(db, chat_id, conversation_id)
            if cleared and not _tombstoned(db, conversation_id):
                await safe_send(bot, chat_id, _TARGET_UNAVAILABLE_NOTICE)
        elif is_permanent(exc):
            db.set_outbox_status_if_in(
                outbox_id, OUTBOX_FAILED, now_iso(), {OUTBOX_SENDING},
                f"HTTP {exc.status_code}",
            )
            await safe_send(bot, chat_id, f"البرومت اترفض: {describe_status(exc.status_code)}")
        else:
            db.set_outbox_status_if_in(
                outbox_id, OUTBOX_UNKNOWN, now_iso(), {OUTBOX_SENDING},
                safe_error_label(exc),
            )
            await safe_send(
                bot, chat_id,
                "مش قادرين نتأكد إن البرومت وصل. راجعه من الموقع قبل ما تعيد الإرسال.",
            )
        return
    except asyncio.CancelledError:
        # اتقطع أثناء الإرسال (shutdown) ⇒ النتيجة غامضة، مايتعادش تلقائياً. نعلّم 'unknown'
        # من 'sending' بس، و**نعيد رفع** الإلغاء (ممنوع كتمه).
        db.set_outbox_status_if_in(
            outbox_id, OUTBOX_UNKNOWN, now_iso(), {OUTBOX_SENDING}, "اتقطع أثناء الإرسال"
        )
        raise
    except Exception:  # noqa: BLE001 — خطأ غير متوقّع **بعد** الـ POST
        # الـ POST ممكن يكون اتقبل بالفعل ⇒ at-most-once: ممنوع أي إعادة تلقائية. نسجّل
        # 'unknown' (CAS من 'sending' بس) ونبلّغ المستخدم يراجع، وما نعملش أي POST تاني.
        log.exception("خطأ غير متوقّع بعد CAS الإرسال للسجل %s", outbox_id)
        db.set_outbox_status_if_in(
            outbox_id, OUTBOX_UNKNOWN, now_iso(), {OUTBOX_SENDING}, "خطأ غير متوقّع بعد الإرسال"
        )
        await safe_send(
            bot, chat_id,
            "مش قادرين نتأكد إن البرومت وصل. راجعه من الموقع قبل ما تعيد الإرسال.",
        )
        return

    if not db.complete_outbox_sent(
        outbox_id,
        now_iso(),
        chat_id=chat_id,
        conversation_id=conversation_id,
        title=conv.get("title", ""),
        last_state=conv.get("execution_status") or "",
        submitted_at=submitted_at,
        notice_text=_OUTBOX_SENT_NOTICE,
    ):
        # حالة أحدث حسمت السجل (نظرياً) ⇒ ما نعلنش نجاح فوق حسم أحدث.
        log.info("السجل %s اتحسم بحالة أحدث قبل تسجيل 'sent'", outbox_id)
        return
    # OHB2-POST-PUB-01/F02 + OHB2-STABILIZATION-F02: الانتقال 'sent' وintent الإكمال
    # المحلي اتسجّلوا في **معاملة واحدة** (مستحيل يبقى 'sent' من غير intent). دلوقتي
    # ننفّذ الإكمال المحلي (إشعار + متابعة) — idempotent وقابل للتعافي، وبدون أي POST
    # خارجي (at-most-once محفوظ). نبدأ المتابعة من الحالة الفعلية المرصودة للشات، مش
    # "running" مفترضة (السبب في تقرير TASK 04A-3): الـ API مابيرجّعش معرّف run يربط
    # البرومت الجديد بالـ run بتاعه، فتسجيل "running" ممكن يدّي المراقب انتقال وهمي.
    await _complete_outbox(
        db, bot, db.get_completion_pending(COMPLETION_KIND_OUTBOX, outbox_id)
    )


async def outbox_recover(app) -> None:
    """تعافي الصندوق عند بدء التشغيل (idempotent عبر إعادات التشغيل).

    - 'pending' : مالمستش خالص ⇒ آمن يتعاود (الـ worker بياخده بعد كده).
    - 'claimed' : الـ worker كان ماسكه بس الـ POST مابدأش ⇒ نرجّعه 'pending' (آمن).
    - 'sending' : بدأ قبل الـ restart والنتيجة مش محسومة ⇒ 'unknown' (مش إعادة
      تلقائية)، وبنبلّغ المستخدم إن فيه برومت ممكن يكون وصل.
    - 'sent'/'unknown'/'failed': تتسيب زي ما هي، مايتبعتش تاني.
    """
    db = app.bot_data["db"]
    bot = app.bot
    for item in db.list_outbox_by_status(OUTBOX_CLAIMED):
        # ملكية متروكة من restart: الإرسال مابدأش ⇒ آمن يرجع مؤهّل.
        db.set_outbox_status(item.id, OUTBOX_PENDING, now_iso(), "ملكية متروكة من restart")
    for item in db.list_outbox_by_status(OUTBOX_SENDING):
        db.set_outbox_status(item.id, OUTBOX_UNKNOWN, now_iso(), "اتقطع قبل ما نأكد الإرسال")
        # OHB2-C7-F1: تعافي الحالة ('sending'⇒'unknown') **لازم** ومابيتخطّاش، بس إشعار
        # التعافي للمستخدم اختياري. لو الشات عليه شاهد حذف دائم (الحذف سايب صف 'sending'
        # عن قصد، عشان الغموض) ما نبعتش إشعار لشات ملغي. مفيش هنا إعادة POST (الحالة
        # 'unknown' مش مؤهّلة أصلاً) ولا أي إحياء محلي.
        if db.is_deleted(item.conversation_id):
            continue
        await safe_send(
            bot, item.chat_id,
            "فيه برومت ممكن يكون اتبعت قبل إعادة التشغيل بس مش متأكدين. "
            "راجعه من الموقع قبل ما تعيد الإرسال.",
        )


class _BaseWorker:
    """منطق worker واحد مالك مشترك (نوم/backoff/wake/start/stop). مفيهوش منطق تسليم.

    - عند الخمول: نوم طويل (max_idle) — مفيش استعلامات متكرّرة وهو فاضي.
    - عند وجود عمل: دورة سريعة + backoff عند الفشل الآمن المؤقّت.
    - wake() بيقطع النوم فوراً لما يوصل عمل جديد.
    """

    def __init__(self, client, db, bot, poll_interval: float = 2.0, max_idle: float = 30.0) -> None:
        self._client = client
        self._db = db
        self._bot = bot
        self._poll_interval = poll_interval
        self._max_idle = max_idle
        self._task: asyncio.Task | None = None
        self._wake: asyncio.Event | None = None
        self._consecutive_failures = 0

    def start(self) -> None:
        # worker واحد بس: لو فيه task شغال ما نعملش واحد تاني.
        if self._task is not None and not self._task.done():
            return
        self._wake = asyncio.Event()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        task = self._task
        if task is None:
            return
        self._task = None
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    def wake(self) -> None:
        """يوقّظ الـ worker فوراً (بعد تسجيل عمل جديد)."""
        if self._wake is not None:
            self._wake.set()

    async def _run(self) -> None:
        while True:
            try:
                did_work = await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                log.exception("خطأ في دورة الـ worker")
                self._consecutive_failures += 1
                did_work = True
            # خمول ⇒ نوم طويل (مفيش استعلامات متكرّرة على صندوق فاضي)؛ شغل ⇒ دورة
            # سريعة/backoff. wake() بيقطع النوم فوراً.
            await self._sleep(self._next_delay() if did_work else self._idle_delay())

    def _next_delay(self) -> float:
        # backoff أسّي محدود للفشل الآمن المؤقّت؛ وإلا دورة سريعة عشان نلتقط الجديد.
        if self._consecutive_failures:
            return min(self._poll_interval * (2 ** self._consecutive_failures), self._max_idle)
        return self._poll_interval

    def _idle_delay(self) -> float:
        """مدة النوم لما الدورة ملقيتش عمل. الافتراضي: خمول طويل."""
        return self._max_idle

    def _reschedule_on_wake(self, delay: float) -> float | None:
        """عند الاستيقاظ من wake() أثناء النوم: هل نعيد الجدولة بمدّة جديدة؟

        الافتراضي None ⇒ ندخل الدورة فوراً. الـ workers اللي محتاجة نوم أدق (تجميع)
        بترجّع مدّة، والـ loop هيكمل نوم بيها.
        """
        return None

    async def _sleep(self, delay: float) -> None:
        wake = self._wake
        if wake is None:
            await asyncio.sleep(delay)
            return
        while True:
            try:
                await asyncio.wait_for(wake.wait(), timeout=delay)
            except asyncio.TimeoutError:
                return
            # اتوقّظنا (عمل جديد). الافتراضي: نرجع ندخل الدورة فوراً.
            wake.clear()
            reschedule = self._reschedule_on_wake(delay)
            if reschedule is None:
                return
            delay = reschedule

    async def _tick(self) -> bool:
        """دورة واحدة: تحجز عنصراً وتعالجه. ما بتنامش (النوم في _run)."""
        item = self._claim()
        if item is None:
            return False
        await self._process(item)
        # فشل آمن مؤقّت رجّع العنصر مؤهّل ⇒ backoff. أي حالة نهائية ⇒ reset.
        if self._is_retry_pending(item):
            self._consecutive_failures += 1
        else:
            self._consecutive_failures = 0
        return True

    def _claim(self):
        raise NotImplementedError

    async def _process(self, item) -> None:
        raise NotImplementedError

    def _is_retry_pending(self, item) -> bool:
        """هل العنصر رجع للحالة المؤهّلة (فشل آمن مؤقّت) ⇒ backoff؟"""
        raise NotImplementedError


class OutboxWorker(_BaseWorker):
    """worker واحد مالك لصندوق البرومتات: يعالج 'pending' ويراعي at-most-once.

    - الفشل الآمن المؤقّت (قبل الـ POST أو sandbox مش جاهز) بيدخل pending تاني، فالعنصر
      يفضل مؤهّل وتتطبق عليه الـ backoff — لحد MAX_OUTBOX_ATTEMPTS محاولات، وبعدها
      نعلّمه 'failed' (نهائي) بإشعار واحد (TASK 53). 'unknown'/'failed'/'sent' مش مؤهّلة
      أصلاً، فمستحيل يتعاودوا تلقائياً.
    - NEW-04: ما بيحجزش سجل 'pending' قبل ما يعدّي تأخير النضج (db_module.GROUP_WINDOW).
      الرسائل المتتالية بتتجمّع وقت القبول في نفس السجل وبتحدّث updated_at، فالـ worker
      بيستنى 3 ثوانٍ من آخر جزء قبل ما يبعت الدفعة كاملة مرة واحدة.
    """

    def __init__(
        self,
        client,
        db,
        bot,
        poll_interval: float = 2.0,
        max_idle: float = 30.0,
        *,
        review_owner_id: int | None = None,
    ) -> None:
        super().__init__(client, db, bot, poll_interval=poll_interval, max_idle=max_idle)
        self._review_owner_id = review_owner_id

    def _claim(self):
        # قراءة ساعة واحدة: نفس اللحظة بتحدّد حدّ النضج ووقت الحجز، فمفيش عدم اتّساق
        # بين حساب التأخير واللحظة اللي بنحجز فيها. حجز ذرّي للناضج (استوفى النافذة).
        now = _utcnow()
        return self._db.claim_outbox(_iso(now), mature_before=grouping_mature_before(now=now))

    async def _process(self, item) -> None:
        await _post_claimed(
            self._client,
            self._db,
            self._bot,
            item,
            review_owner_id=self._review_owner_id,
        )

    def _is_retry_pending(self, item) -> bool:
        after = self._db.get_outbox(item.id)
        return after is not None and after.status == OUTBOX_PENDING

    def _next_delay(self) -> float:
        # فيه 'pending' لسه في تأخير النضج ⇒ ننام بالظبط لحد ما يستوفي (بدل لفّ فاضي).
        # الحالات المؤقّتة (backoff) وأي حالة تانية زي ما هي.
        if self._consecutive_failures:
            return super()._next_delay()
        remaining = self._remaining_until_mature()
        if remaining is None:
            return self._poll_interval
        return min(remaining, self._max_idle)

    def _idle_delay(self) -> float:
        # مفيش حجز (السجل لسه في تأخير النضج): ننام لحد ما يستوفي، مش خمول طويل.
        remaining = self._remaining_until_mature()
        if remaining is None:
            return self._max_idle
        return min(remaining, self._max_idle)

    def _remaining_until_mature(self) -> float | None:
        """ثواني النوم لحد نضج أقدم 'pending'. None لو مفيش 'pending'.

        قراءة ساعة واحدة بتتمرّر للاستعلام، فمفيش قراءتين ممكن يخلّوا القيمة
        غير متّسقة مع حدّ النضج اللي بنحجز بيه.
        """
        return self._db.seconds_until_mature_at(_utcnow(), db_module.GROUP_WINDOW)

    def _reschedule_on_wake(self, delay: float) -> float | None:
        # نوم تجميع دقيق: wake() من برومت جديد بتمنع الرجوع الفوري للدورة؛ بنعيد حساب
        # المدة عشان نستنى آخر نافذة. لو مفيش 'pending' (اتحجز/اتصفّى) نرجع ندخل الدورة.
        # حتى لو الـ loop اتأخّر، الـ claim بيفلتر بالنضج فالدفعة ما تتجزّاش.
        fresh = self._remaining_until_mature()
        return delay if fresh is None else fresh


async def _start_conversation(client, db, bot, job, base_url: str, on_created=None) -> None:
    """ينشئ شات جديد بأمان at-most-once.

    - 'starting' يتسجّل بثبات قبل POST البدء بالظبط (حد الغموض): أي إلغاء/انقطاع قبله
      بيسيب 'claimed'/'pending' ⇒ يتعافى 'pending' (آمن). بعده ⇒ 'unknown' (غامض).
    - لو الـ task_id اتسجّل بالفعل (تعافٍ): نستطلع بس (GET آمن)، ما بنعملش POST تاني.
    - لو مفيش task_id والعملية 'starting': نتخطّى (غامض) — مستحيل نعمل POST تاني.
    """
    job_id = job.id
    chat_id = job.chat_id
    repo = job.repo
    text = job.text

    # مسار الاستطلاع فقط: الـ task_id اتعمل قبل كده (POST بدأ فعلاً) ⇒ GET آمن بس.
    # ده بيتحقق بوجود الـ task_id مش بحالة السجل، لأن الـ worker بيحجز 'claimed'
    # والسجل المستعاد بيحمل task_id محفوظ.
    if job.task_id:
        try:
            conversation_id = await client.wait_for_start(job.task_id)
        except ApiError as exc:
            # CAS من الحالات غير النهائية بس: لو المستخدم شطب الطلب أثناء الاستطلاع،
            # ما نعلّمش 'unknown' فوق شطب أحدث (مفيش clobber).
            db.set_creation_status_if_in(
                job_id, CREATION_UNKNOWN, now_iso(),
                {CREATION_CLAIMED, CREATION_STARTING}, safe_error_label(exc),
            )
            await safe_send(bot, chat_id, _UNKNOWN_CREATION_NOTICE)
            return
        except asyncio.CancelledError:
            # OHB2-WP-05 (DEF-012): إلغاء أثناء الاستطلاع المستأنَف ⇒ 'unknown' ثم إعادة
            # الرمي (الإلغاء ينتشر زي ما هو)، عشان الطلب ما يفضلش 'claimed'/'starting'.
            db.set_creation_status_if_in(
                job_id, CREATION_UNKNOWN, now_iso(),
                {CREATION_CLAIMED, CREATION_STARTING}, "اتقطع أثناء استطلاع البدء",
            )
            raise
        except Exception as exc:  # noqa: BLE001 — أي فشل غير متوقّع في الاستطلاع لازم يتسجّل
            # OHB2-WP-05 (DEF-012): أي خطأ غير `ApiError` كان بيفضّل الطلب
            # 'claimed'/'starting' للأبد لحد restart. نعامله كغامض: 'unknown' + إشعار.
            db.set_creation_status_if_in(
                job_id, CREATION_UNKNOWN, now_iso(),
                {CREATION_CLAIMED, CREATION_STARTING}, safe_exception_label(exc),
            )
            await safe_send(bot, chat_id, _UNKNOWN_CREATION_NOTICE)
            return
        await _finish_creation(
            client, db, bot, job_id, chat_id, repo, conversation_id, base_url, on_created
        )
        return

    # مفيش task_id معروف ⇒ إحنا (بإذن الله) أول من يعمل POST. نسجّل 'starting' أولاً
    # بـ CAS من 'claimed': لو المستخدم شطب الطلب بين الحجز والـ POST، الـ CAS يفشل
    # وما بنبعتش الـ POST خالص (at-most-once: الشطب قبل الإرسال الفعلي بيوقف الإرسال).
    if not db.claim_creation_starting(job_id, now_iso()):
        log.info("تخطّي POST البدء: الطلب %s مش مملوك (اتشطب/اتغيّر قبل الـ POST)", job_id)
        return
    try:
        task_id = await client.start_conversation(text, repo)
    except ApiError as exc:
        if is_permanent(exc):
            db.set_creation_status_if_in(
                job_id, CREATION_FAILED, now_iso(), {CREATION_STARTING},
                f"HTTP {exc.status_code}",
            )
            await safe_send(bot, chat_id, f"فشل بدء الشات: {describe_status(exc.status_code)}")
        else:
            # فشل قبل ما نتأكد إن الـ POST اتعمل ⇒ غامض، مايتعادش تلقائياً.
            db.set_creation_status_if_in(
                job_id, CREATION_UNKNOWN, now_iso(), {CREATION_STARTING},
                safe_error_label(exc),
            )
            await safe_send(bot, chat_id, _UNKNOWN_CREATION_NOTICE)
        return
    except asyncio.CancelledError:
        # اتقطع أثناء POST البدء ⇒ غامض، مايتعادش تلقائياً.
        db.set_creation_status_if_in(
            job_id, CREATION_UNKNOWN, now_iso(), {CREATION_STARTING}, "اتقطع أثناء POST البدء"
        )
        raise
    except ValueError:
        # OHB2-N10-28D: رد بدء مش JSON (جسم HTML/نص) كان بيرمي ValueError خام من غير
        # ما يعدّي حدود الأخطاء المتوقّعة ⇒ الطلب يفضل 'starting' للأبد لحد restart.
        # الـ client المفروض يحوّل ده لـ ApiError دلوقتي، بس كحماية مزدوجة بنعامله زي
        # أي فشل غامض: 'unknown' (مفيش إعادة POST تلقائية، مفيش ادّعاء فشل/نجاح).
        db.set_creation_status_if_in(
            job_id, CREATION_UNKNOWN, now_iso(), {CREATION_STARTING}, "رد بدء غير متوقّع"
        )
        await safe_send(bot, chat_id, _UNKNOWN_CREATION_NOTICE)
        return

    # الـ task_id اترجّع فعلاً ⇒ نسجّله (مش مخترع). لو التسجيل فشل (قاعدة مقفولة/انقطاع)،
    # الحالة تفضل 'starting' بلا task_id ⇒ التعافي يتعامل معاها كغامضة (مايعملش POST تاني).
    db.set_creation_starting(job_id, now_iso(), task_id=task_id)

    try:
        conversation_id = await client.wait_for_start(task_id)
    except ApiError as exc:
        db.set_creation_status_if_in(
            job_id, CREATION_UNKNOWN, now_iso(),
            {CREATION_CLAIMED, CREATION_STARTING}, safe_error_label(exc),
        )
        await safe_send(bot, chat_id, _UNKNOWN_CREATION_NOTICE)
        return
    except asyncio.CancelledError:
        db.set_creation_status_if_in(
            job_id, CREATION_UNKNOWN, now_iso(),
            {CREATION_CLAIMED, CREATION_STARTING}, "اتقطع أثناء استطلاع البدء",
        )
        raise
    except Exception as exc:  # noqa: BLE001 — أي فشل غير متوقّع في الاستطلاع لازم يتسجّل
        # OHB2-WP-05 (DEF-012): فرع POST البدء كان بيلتقط `ApiError`/`CancelledError`/
        # `ValueError` بس؛ أي خطأ غير متوقّع كان بيسيب الطلب 'claimed'/'starting'.
        # نعامله كغامض (مفيش إعادة POST تلقائية، مفيش ادّعاء فشل/نجاح).
        db.set_creation_status_if_in(
            job_id, CREATION_UNKNOWN, now_iso(),
            {CREATION_CLAIMED, CREATION_STARTING}, safe_exception_label(exc),
        )
        await safe_send(bot, chat_id, _UNKNOWN_CREATION_NOTICE)
        return

    await _finish_creation(
        client, db, bot, job_id, chat_id, repo, conversation_id, base_url, on_created
    )


async def _finish_creation(
    client, db, bot, job_id: int, chat_id: int, repo, conversation_id: str, base_url: str,
    on_created=None,
) -> None:
    """اتأكد بدء الشات: نسجّل 'done' (CAS) + نتابع الشات + نبلّغ الرابط (قابل للتعافي).

    OHB2-N10-28C: التسجيل بـ CAS من حالة غير نهائية؛ لو المستخدم شطب الطلب أثناء
    الاستطلاع، ما نعلّمش 'done' فوق شطب أحدث (مفيش نجاح وهمي).

    OHB2-STABILIZATION-F02: الانتقال 'done' وintent الإكمال المحلي (إشعار الرابط + تسجيل
    المتابعة) بيتسجّلوا في **معاملة واحدة** — مستحيل يبقى 'done' من غير intent محفوظ.
    الإكمال المحلي ما بيعملش أي POST خارجي (الرابط/المعرّف محفوظين، ما فيش إنشاء شات مكرّر).
    """
    notice = _creation_done_notice(base_url, conversation_id)
    if not db.complete_creation_done(
        job_id, now_iso(), conversation_id,
        chat_id=chat_id, title=repo or "", last_state="running", notice_text=notice,
    ):
        log.info("الطلب %s اتحسم بحالة أحدث قبل تسجيل 'done'", job_id)
        return
    # OHB2-WP-05 (NEW-DEF-02): الشات الجديد بقى موجود فعلًا (commit ناجح) ⇒ نبلّغ كاش
    # قايمة الشات بإنه باطل، وإلا الشات الجديد يفضل مختفي من «شاتاتي» لحد انتهاء LIST_TTL.
    # النداء بعد الـ commit فقط (مفيش إبطال كاذب)، وفشله مايفشّلش الإكمال (الكاش تحسين،
    # مش صحة) ⇒ نتسجّل النوع بس.
    if on_created is not None:
        try:
            on_created()
        except Exception as exc:  # noqa: BLE001 — إبطال الكاش تحسين، مش شرط صحة
            log.warning("تعذّر إبطال كاش القايمة بعد إنشاء شات (%s)", type(exc).__name__)
    await _complete_creation(
        db, bot, db.get_completion_pending(COMPLETION_KIND_CREATION, job_id), base_url
    )


async def creation_recover(app) -> None:
    """تعافي طلبات الشات الجديد عند بدء التشغيل (idempotent).

    - 'pending' : مالمستش خالص ⇒ آمن يتعاود (الـ worker بياخده بعد كده).
    - 'claimed' : ملكية متروكة من restart، والـ POST مابدأش ⇒ نرجّعه 'pending' (آمن).
    - 'starting' + task_id: الـ POST اتعمل ⇒ استطلاع GET آمن فقط ⇒ نرجّعه 'pending'
      عشان الـ worker يستطلع (ما بيعملش POST تاني).
    - 'starting' بدون task_id: POST ممكن يكون بدأ ومش معروف ⇒ 'unknown' (غامض)،
      مايتعادش تلقائياً + إشعار للمستخدم.
    - 'done'/'unknown'/'failed': تتسيب زي ما هي، مايتعادش.
    """
    db = app.bot_data["db"]
    bot = app.bot
    for job in db.list_creation_jobs_by_status(CREATION_CLAIMED):
        db.set_creation_status(job.id, CREATION_PENDING, now_iso(), "ملكية متروكة من restart")
    for job in db.list_creation_jobs_by_status(CREATION_STARTING):
        if job.task_id:
            # POST البدء اتعمل؛ الاستطلاع (GET) آمن ⇒ نرجّعه مؤهّل للاستطلاع بس.
            db.set_creation_status(job.id, CREATION_PENDING, now_iso(), "استكمال استطلاع البدء")
        else:
            db.set_creation_status(job.id, CREATION_UNKNOWN, now_iso(), "بدء غامض بدون task_id")
            # OHB2-C7-F1: الانتقال لـ 'unknown' (غامض) **لازم** ومابيتخطّاش (مافيهوش إعادة
            # POST)، بس إشعار التعافي اختياري. لو الشات عليه شاهد حذف دائم ما نبعتش إشعار
            # لشات ملغي. (شات 'starting' بلا task_id نادرًا ما بيحمل conversation_id، بس
            # الفحص آمن حتى لو None.)
            if db.is_deleted(job.conversation_id):
                continue
            await safe_send(bot, job.chat_id, _UNKNOWN_CREATION_NOTICE)


class CreationWorker(_BaseWorker):
    """worker الشات الجديد: يحجز 'pending' ذرّياً ويبدأ/يستطلع بأمان at-most-once.

    بيشتغل على جدول creation_jobs فقط (الـ OutboxWorker على جدول outbox)، والحجز الذرّي
    في كل جدول لوحده، فمستحيل يتنافسوا على نفس السجل. العمليتين ممكن يشتغلوا مع بعض بس
    كل واحد مالك جدوله (اتنين tasks — مش worker تاني على نفس الجدول).
    """

    def _claim(self):
        return self._db.claim_creation_job(now_iso())  # حجز ذرّي: pending ⇒ claimed

    def __init__(
        self, client, db, bot, base_url: str, poll_interval: float = 2.0,
        max_idle: float = 30.0, on_created=None,
    ) -> None:
        super().__init__(client, db, bot, poll_interval=poll_interval, max_idle=max_idle)
        self._base_url = base_url
        # OHB2-WP-05 (NEW-DEF-02): اختياري — إبطال كاش قايمة الشات بعد اكتمال إنشاء شات.
        self._on_created = on_created

    async def _process(self, item) -> None:
        await _start_conversation(
            self._client, self._db, self._bot, item, self._base_url, self._on_created
        )

    def _is_retry_pending(self, item) -> bool:
        after = self._db.get_creation_job(item.id)
        return after is not None and after.status == CREATION_PENDING


# OHB2-POST-PUB-01/F02 + OHB2-STABILIZATION-F02: أقصى عدد محاولات لإكمال الأثر المحلي قبل
# ما نعلّمه «مستنفد/مطلوب تدخّل» (`exhausted=1`). الإكمال المحلي **ما بيعملش** أي عملية
# خارجية، فالفشل هنا مجرد فشل إشعار (TelegramError) مش خطر ازدواج. العنصر المستنفد بيتسيب
# ظاهر (مايتشالش) ومستبعد من العناصر المؤهّلة ⇒ مايعطّلش العناصر السليمة.
COMPLETION_MAX_ATTEMPTS = 5
# backoff أسّي محدود بين محاولات الإكمال (ثواني): 5، 10، 20، 40 (ثم يثبت عند الحد).
COMPLETION_BASE_BACKOFF_SECONDS = 5.0
COMPLETION_MAX_BACKOFF_SECONDS = 300.0
# إجارة حجز قصيرة: الصف المحجوز يبقى غير مؤهّل للمدة دي، فمستحيل اتنين ياخدوه في نفس اللحظة.
COMPLETION_CLAIM_LEASE_SECONDS = 30.0


def _completion_backoff_seconds(attempts: int) -> float:
    """backoff أسّي محدود: 5، 10، 20، 40… لحد الحد. مستقل عن العشوائية (اختبار حتمي)."""
    exp = max(0, attempts - 1)
    return min(COMPLETION_BASE_BACKOFF_SECONDS * (2 ** exp), COMPLETION_MAX_BACKOFF_SECONDS)


def _completion_retry_at(now: str, attempts: int) -> str:
    base = datetime.fromisoformat(now)
    return (base + timedelta(seconds=_completion_backoff_seconds(attempts))).isoformat()


async def completion_recover(app) -> None:
    """تعافي الإكمال المحلي عند بدء التشغيل (idempotent).

    العناصر المؤجّلة اللي انتهت إجارتها تبقى مؤهّلة تلقائيًا (شرط `next_attempt_at <= now`)،
    والمستنفدة تفضل مستنفدة. **الصفوف القديمة** (`sent`/`done` من غير intent) **ما تتسوّاش
    تلقائيًا**: مستحيل نفرّق بأمان بين صف اكتمل فعلًا (الإكمال اتشال بعد النجاح) وصف وقع في
    نافذة الـ crash القديمة، فالتسوية التلقائية كانت هتبعت إشعارات مكرّرة. بدل كده بنسيبهم
    **ظاهرين للمشغّل** (عدّاد غير محلول) مع تسوية يدوية صريحة لكل مرجع (`reconcile_legacy_completion`).
    بدون أي POST خارجي في كل الحالات.
    """
    db = app.bot_data["db"]
    try:
        n = db.count_legacy_unresolved_completions()
        if n:
            log.warning(
                "إكمال محلي: %s صف قديم (sent/done) من غير intent — غير محلول، يحتاج "
                "تسوية يدوية صريحة (بدون أي إعادة POST)", n,
            )
    except Exception as exc:  # noqa: BLE001
        # فشل الرصد مايمنعش الإقلاع، بس يتسجّل بوضوح.
        log.error("فشل فحص الصفوف القديمة غير المحلولة (%s)", type(exc).__name__)


class CompletionWorker(_BaseWorker):
    """worker واحد مالك لإكمال الآثار المحلية المعلّقة (F02 + STABILIZATION-F02).

    بيعالج جدول `completion_pending` **بس**: مفيش أي عملية خارجية هنا (مفيش POST خارجي).
    - الحجز ذرّي (`claim_completion_due`): أقدم عنصر **مؤهّل** (غير مستنفد وموعد محاولته حان)
      ⇒ مستحيل اتنين ياخدوا نفس الصف (safe concurrent claiming + إجارة قصيرة للتعافي).
    - الفشل ⇒ جدولة إعادة محاولة دائمة (backoff أسّي محدود) + زيادة العدّاد. عند
      `COMPLETION_MAX_ATTEMPTS` نعلّمه `exhausted=1` (ظاهر للمشغّل، مستبعد من المؤهّل) بدل
      ما نلفّ عليه للأبد ⇒ **مايعطّلش** العناصر السليمة (fairness).
    - العناصر المستنفدة تتسيب ظاهرة (مايتشالش) ويقدر المشغّل يعيد تأهيلها (`rearm`).
    """

    def __init__(
        self, client, db, bot, base_url: str = "",
        poll_interval: float = 2.0, max_idle: float = 30.0,
    ) -> None:
        super().__init__(client, db, bot, poll_interval=poll_interval, max_idle=max_idle)
        self._base_url = base_url
        self._last_success_at: str | None = None
        self._last_failure_at: str | None = None

    def _claim(self):
        now = now_iso()
        lease_until = (
            datetime.fromisoformat(now)
            + timedelta(seconds=COMPLETION_CLAIM_LEASE_SECONDS)
        ).isoformat()
        return self._db.claim_completion_due(now, lease_until)

    async def _process(self, item) -> None:
        try:
            if item.ref_kind == COMPLETION_KIND_OUTBOX:
                await _complete_outbox(self._db, self._bot, item, self._base_url)
            else:
                await _complete_creation(self._db, self._bot, item, self._base_url)
        except Exception as exc:  # noqa: BLE001
            # فشل خطوة التسجيل المحلي (مش الإشعار) ⇒ جدولة إعادة محاولة وزيادة العدّاد.
            self._record_failure(item, type(exc).__name__)
            return
        # لو الإشعار فشل (العمل لسه موجود)، نجدوله كمان (backoff) — مايتشالش.
        if self._db.get_completion_pending(item.ref_kind, item.ref_id) is not None:
            self._record_failure(item, "إشعار فشل")
        else:
            self._last_success_at = now_iso()

    def _record_failure(self, item, error: str) -> None:
        now = now_iso()
        attempts = self._db.bump_completion_attempt(
            item.ref_kind, item.ref_id, now,
            error=error,
            next_attempt_at=_completion_retry_at(now, item.attempts + 1),
            max_attempts=COMPLETION_MAX_ATTEMPTS,
        )
        self._last_failure_at = now
        if attempts >= COMPLETION_MAX_ATTEMPTS:
            log.warning(
                "إكمال محلي %s/%s استنفد %s محاولات — مستنفد/مطلوب تدخّل (سايبه ظاهر، "
                "مستبعد من المؤهّل)", item.ref_kind, item.ref_id, attempts,
            )

    def _is_retry_pending(self, item) -> bool:
        # مؤقّت (لسه غير مستنفد) ⇒ backoff؛ مستنفد ⇒ حالة نهائية ⇒ reset.
        row = self._db.get_completion_pending(item.ref_kind, item.ref_id)
        return row is not None and not row.exhausted

    def _idle_delay(self) -> float:
        # مفيش عمل مؤهّل ⇒ خمول طويل (مفيش لفّ فاضي). العناصر المؤجّلة/المستنفدة مايتلكّش عليها.
        return self._max_idle

    def health(self) -> dict:
        """ملخّص صحة الـ worker (بلا محتوى حساس) للرصد/الجاهزية."""
        stats = self._db.completion_stats(now_iso())
        stats["last_success_at"] = self._last_success_at
        stats["last_failure_at"] = self._last_failure_at
        return stats
