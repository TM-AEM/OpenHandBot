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
    OUTBOX_FAILED,
    OUTBOX_PENDING,
    OUTBOX_SENDING,
    OUTBOX_UNKNOWN,
)
from .errors import ApiError, describe_status, error_text

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

# OHB2-POST-PUB-01/F02: نصوص الإكمال المحلي (ثابتة ⇒ الإشعار القابل للتعافي يعيد نفس النص).
_OUTBOX_SENT_NOTICE = "اتبعت ✅ الشات اتضاف للمتابعة."
_CREATION_DONE_LINK_TEMPLATE = "بدأ الشات ✅\n{link}"


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
    """حدّ النضج: أي برومت updated_at <= النتيجة دي بقى مستوفي نافذة التجميع.

    بنستخدمه في الحجز عشان ما ناخدش دفعة لسه بتتجمع. لو `now` مابيتزوّدش، بنستخدم
    الساعة الحقيقية. بنقرأ db_module.GROUP_WINDOW وقت النداء (مش كقيمة افتراضية متثبّتة) عشان
    الاختبارات تقدر تصغّر النافذة بشكل حتمي.
    """
    current = now or datetime.now(timezone.utc)
    return _iso(current - (window if window is not None else db_module.GROUP_WINDOW))


async def safe_send(bot, chat_id: int, text: str) -> None:
    """إرسال رسالة تيليجرام من غير ما يرمي (فشل الإشعار مايأثرش على حالة الصندوق)."""
    try:
        await bot.send_message(chat_id=chat_id, text=text)
    except TelegramError as exc:
        log.warning("فشل إرسال رسالة تيليجرام (%s)", type(exc).__name__)


async def safe_send_checked(bot, chat_id: int, text: str) -> bool:
    """OHB2-POST-PUB-01/F02: زي `safe_send` بس **بترجّع** هل الإرسال نجح.

    بنستخدمها في مسار الإكمال المحلي القابل للتعافي: لو الإرسال فشل، بنسيب العمل المعلّق
    عشان يتعافى (بدون إعادة أي عملية خارجية). عقد «مفيش exactly-once»: نجاح الإرسال هنا
    معناه إن تيليجرام قبل الرسالة، مش ضمان عدم التكرار لو انقطع بين الإرسال والتسجيل.
    """
    try:
        await bot.send_message(chat_id=chat_id, text=text)
        return True
    except TelegramError as exc:
        log.warning("فشل إرسال رسالة تيليجرام (%s)", type(exc).__name__)
        return False


def safe_error_label(exc: ApiError) -> str:
    """وصف مختصر آمن للخطأ (من غير نص الاستثناء أو جسم الرد الخام)."""
    if exc.status_code is not None:
        return f"HTTP {exc.status_code}"
    return "تعذّر الاتصال (نتيجة غامضة)"


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
    1) نسجّل المتابعة/الحالة (idempotent)، 2) نبعت الإشعار عبر `safe_send_checked`،
    3) لو الإرسال نجح **بس** نشيل العمل المعلّق. لو الإرسال فشل (TelegramError)، بنسيب
    العمل المعلّق ⇒ تعافٍ لاحق. فشل خطوة التسجيل (1) بيطلع استثناء ويسيب العمل المعلّق
    كمان (يتعافى). الإكمال المحلي **ما بيعملش** أي POST خارجي (at-most-once محفوظ).
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
    notice = item.notice_text or _OUTBOX_SENT_NOTICE
    delivered = await safe_send_checked(bot, item.chat_id, notice)
    if delivered:
        db.clear_completion_pending(COMPLETION_KIND_OUTBOX, item.ref_id)


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
    """مسار مباشر: لو العنصر 'pending' نحاول نحجزه ذرّياً ثم نرسله عبر _post_claimed.

    OHB2-N10-28C: بنحجز ذرّياً (`claim_outbox` بحجز أقدم pending) بدل read-then-write،
    عشان ما نتنافسش مع الـ worker على نفس السجل. لو الحجز رجّع سجل تاني، نكمّل بيه
    (نفس ترتيب الأقدم-أولاً)، وبكده ما نكرّرش معالجة سجل واحد من مسارين.
    """
    item = db.get_outbox(outbox_id)
    if item is None or item.status != OUTBOX_PENDING:
        return
    claimed = db.claim_outbox(now_iso())
    if claimed is None:
        return
    await _post_claimed(client, db, bot, claimed)


async def _post_claimed(client, db, bot, item) -> None:
    """يحاول الـ POST لعنصر محجوز (claimed) ولسه الإرسال مابدأش.

    at-most-once: بنسجّل 'sending' بـ **CAS ذرّي** (`claimed`⇒`sending`) فوراً قبل الـ POST
    بالظبط. لو المستخدم شطب العنصر أثناء التحضير (قراءة الشات/تشغيل الـ sandbox)، الـ CAS
    هيفشل (rowcount=0) وما بنبعتش الـ POST خالص — فمفيش إرسال بعد إلغاء، ومفيش ادّعاء إلغاء
    وهمي. أي إلغاء/انقطاع قبل كده بيسيب 'claimed' ⇒ يتعافى 'pending' (آمن، الـ POST مابدأش).
    أي إلغاء/انقطاع بعد الـ CAS بيسيب 'sending' ⇒ يتعافى 'unknown' (غامض، مايتعادش تلقائياً).
    """
    outbox_id = item.id
    conversation_id = item.conversation_id
    chat_id = item.chat_id
    text = item.text

    try:
        conv = await get_conversation(client, conversation_id)
        sandbox_id = conv.get("sandbox_id")
        status = str(conv.get("sandbox_status", "")).upper()

        if status != "RUNNING" and sandbox_id:
            await client.resume_sandbox(sandbox_id)
            status = await wait_running(client, conversation_id, interval=3.0, timeout=120.0)

        if status != "RUNNING":
            # البرومت ماتبعتش خالص ⇒ آمن يتعاود — بس بحد (TASK 53). بنزوّد attempts
            # ذرّياً (بس لو لسه 'claimed'، ما نحييش سجل اتشطب)؛ أول محاولة بتبلّغ (مؤقّت)،
            # وبعد استنفاد الحد نعلّمه 'failed' مرة واحدة (CAS من 'claimed').
            attempts = db.bump_outbox_attempt(outbox_id, now_iso(), "sandbox غير جاهز")
            if attempts == 0:
                # السجل مش مملوك لينا دلوقتي (اتشطب/اتغيّر) ⇒ ما نلمسش حاجة.
                return
            if attempts >= MAX_OUTBOX_ATTEMPTS:
                db.set_outbox_status_if_in(
                    outbox_id, OUTBOX_FAILED, now_iso(), {OUTBOX_CLAIMED},
                    f"استنفد {attempts} محاولات (sandbox غير جاهز)",
                )
                await safe_send(bot, chat_id, _OUTBOX_EXHAUSTED_NOTICE)
            else:
                # محاولة آمنة فاشلة (قبل الـ POST) ⇒ نرجّع السجل مؤهّل 'pending' بـ CAS
                # (الـ worker ياخده تاني بعد backoff). CAS من 'claimed' بس.
                db.set_outbox_status_if_in(
                    outbox_id, OUTBOX_PENDING, now_iso(), {OUTBOX_CLAIMED},
                    "sandbox غير جاهز",
                )
                if attempts == 1:
                    await safe_send(bot, chat_id, _SANDBOX_NOT_READY_NOTICE)
            return

        # الإرسال هيبدأ حالاً: CAS 'claimed'⇒'sending' بثبات قبل الـ POST مباشرة (الـ commit
        # جوّه set_outbox_status_if_in). ده آخر حد آمن: بعده النتيجة غامضة. لو الـ CAS
        # فشل (المستخدم شطب العنصر في الأثناء) ⇒ مفيش POST خالص.
        submitted_at = now_iso()  # قبل الـ POST: أي حدث للـ run الجديد لازم يكون أحدث منه
        if not db.set_outbox_status_if_in(
            outbox_id, OUTBOX_SENDING, submitted_at, {OUTBOX_CLAIMED}
        ):
            log.info("تخطّي الإرسال: السجل %s مش مملوك (اتشطب/اتغيّر قبل الـ POST)", outbox_id)
            return
        try:
            await client.send_message(conversation_id, text)
        except ApiError as exc:
            # رفض مؤكد (4xx) ⇒ 'failed'؛ غير كده (شبكة/مهلة/5xx) ⇒ 'unknown' — مش إعادة
            # تلقائية. CAS من 'sending' بس: لو حالة أحدث (نهائية) حسمت السجل، ما نلخبطهاش.
            if is_permanent(exc):
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
            # اتقطع أثناء الإرسال (shutdown) ⇒ النتيجة غامضة، مايتعادش تلقائياً.
            db.set_outbox_status_if_in(
                outbox_id, OUTBOX_UNKNOWN, now_iso(), {OUTBOX_SENDING}, "اتقطع أثناء الإرسال"
            )
            raise

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
    except ApiError as exc:
        # فشل قبل الـ POST (قراءة الشات / تشغيل الـ sandbox): الإرسال مابدأش ⇒ آمن يتعاود،
        # بس بحد (TASK 53): أول محاولة بتبلّغ (مؤقّت)، وبعد استنفاد الحد نعلّمه 'failed'
        # مرة واحدة. بنزوّد attempts بس لو لسه مملوك (claimed) — عشان ما نحييش سجل اتشطب.
        attempts = db.bump_outbox_attempt(outbox_id, now_iso(), safe_error_label(exc))
        if attempts == 0:
            return
        if attempts >= MAX_OUTBOX_ATTEMPTS:
            db.set_outbox_status_if_in(
                outbox_id, OUTBOX_FAILED, now_iso(), {OUTBOX_CLAIMED},
                f"استنفد {attempts} محاولات",
            )
            await safe_send(bot, chat_id, _OUTBOX_EXHAUSTED_NOTICE)
        else:
            # محاولة آمنة فاشلة (قبل الـ POST) ⇒ نرجّع السجل 'pending' بـ CAS من 'claimed'.
            db.set_outbox_status_if_in(
                outbox_id, OUTBOX_PENDING, now_iso(), {OUTBOX_CLAIMED},
                safe_error_label(exc),
            )
            if attempts == 1:
                await safe_send(bot, chat_id, f"فشل الإرسال: {error_text(exc)}")


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
    - القرار 2: ما بيحجزش سجل 'pending' غير لما يستوفي نافذة التجميع (db_module.GROUP_WINDOW)،
      فكل الرسايل اللي وصلت خلال النافذة بتتجمّع في سجل واحد وبتتبعت مرة واحدة.
    """

    def _claim(self):
        # قراءة ساعة واحدة: نفس اللحظة بتحدّد حدّ النضج ووقت الحجز، فمفيش عدم اتّساق
        # بين حساب التأخير واللحظة اللي بنحجز فيها. حجز ذرّي للناضج (استوفى النافذة).
        now = _utcnow()
        return self._db.claim_outbox(_iso(now), mature_before=grouping_mature_before(now=now))

    async def _process(self, item) -> None:
        await _post_claimed(self._client, self._db, self._bot, item)

    def _is_retry_pending(self, item) -> bool:
        after = self._db.get_outbox(item.id)
        return after is not None and after.status == OUTBOX_PENDING

    def _next_delay(self) -> float:
        # فيه 'pending' لسه في نافذة التجميع ⇒ ننام بالظبط لحد ما يستوفي (بدل لفّ فاضي).
        # الحالات المؤقّتة (backoff) وأي حالة تانية زي ما هي.
        if self._consecutive_failures:
            return super()._next_delay()
        remaining = self._remaining_until_mature()
        if remaining is None:
            return self._poll_interval
        return min(remaining, self._max_idle)

    def _idle_delay(self) -> float:
        # مفيش حجز (الدفعة لسه بتتجمّع): ننام لحد ما تستوفي النافذة، مش خمول طويل،
        # عشان الإرسال يحصل بعد ~1.5 ثانية من آخر رسالة (القرار 2).
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


async def _start_conversation(client, db, bot, job, base_url: str) -> None:
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
        await _finish_creation(client, db, bot, job_id, chat_id, repo, conversation_id, base_url)
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

    await _finish_creation(client, db, bot, job_id, chat_id, repo, conversation_id, base_url)


async def _finish_creation(
    client, db, bot, job_id: int, chat_id: int, repo, conversation_id: str, base_url: str
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

    def __init__(self, client, db, bot, base_url: str, poll_interval: float = 2.0, max_idle: float = 30.0) -> None:
        super().__init__(client, db, bot, poll_interval=poll_interval, max_idle=max_idle)
        self._base_url = base_url

    async def _process(self, item) -> None:
        await _start_conversation(self._client, self._db, self._bot, item, self._base_url)

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
