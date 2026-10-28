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
    OUTBOX_SENT,
    OUTBOX_UNKNOWN,
)
from .errors import ApiError, describe_status, error_text

log = logging.getLogger(__name__)

# فشل مؤكّد (4xx) مش هينجح بإعادة المحاولة؛ غيره (شبكة/مهلة/5xx) ممكن يتعاود لو الإرسال مابدأش.
PERMANENT_STATUS = 400

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


def safe_error_label(exc: ApiError) -> str:
    """وصف مختصر آمن للخطأ (من غير نص الاستثناء أو جسم الرد الخام)."""
    if exc.status_code is not None:
        return f"HTTP {exc.status_code}"
    return "تعذّر الاتصال (نتيجة غامضة)"


def is_permanent(exc: ApiError) -> bool:
    """رفض نهائي مؤكد؟ (4xx) — غير كده غامض/مؤقت."""
    return exc.status_code is not None and PERMANENT_STATUS <= exc.status_code < 500


async def get_conversation(client, conversation_id: str) -> dict:
    convs = await client.get_conversations([conversation_id])
    return convs[0] if convs else {}


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
    """مسار مباشر: لو العنصر 'pending' نجرّب الإرسال عبر _post_claimed.

    (الـ worker بيحجز ذرّياً بنفسه عبر db.claim_outbox وبيستخدم _post_claimed.)
    """
    item = db.get_outbox(outbox_id)
    if item is None or item.status != OUTBOX_PENDING:
        return
    await _post_claimed(client, db, bot, item)


async def _post_claimed(client, db, bot, item) -> None:
    """يحاول الـ POST لعنصر محجوز (claimed/pending) ولسه الإرسال مابدأش.

    at-most-once: بنسجّل 'sending' بثبات فوراً قبل الـ POST بالظبط. أي إلغاء/انقطاع
    قبل كده (مرحلة التحضير: قراءة الشات/تشغيل الـ sandbox) بيسيب الحالة 'claimed'
    أو 'pending' ⇒ يتعافى 'pending' (آمن، لأن الـ POST مابدأش). أي إلغاء/انقطاع بعد
    كده بيسيب 'sending' ⇒ يتعافى 'unknown' (غامض، مايتعادش تلقائياً أبداً).
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
            # ذرّياً؛ أول محاولة بتبلّغ (مؤقّت)، وبعد استنفاد الحد نعلّمه 'failed' مرة واحدة.
            attempts = db.bump_outbox_attempt(outbox_id, now_iso(), "sandbox غير جاهز")
            if attempts >= MAX_OUTBOX_ATTEMPTS:
                db.set_outbox_status(
                    outbox_id, OUTBOX_FAILED, now_iso(),
                    f"استنفد {attempts} محاولات (sandbox غير جاهز)",
                )
                await safe_send(bot, chat_id, _OUTBOX_EXHAUSTED_NOTICE)
            elif attempts == 1:
                await safe_send(bot, chat_id, _SANDBOX_NOT_READY_NOTICE)
            return

        # الإرسال هيبدأ حالاً: نسجّل 'sending' بثبات قبل الـ POST مباشرة (الـ commit
        # جوّه set_outbox_status). ده آخر حد آمن: بعده النتيجة غامضة.
        submitted_at = now_iso()  # قبل الـ POST: أي حدث للـ run الجديد لازم يكون أحدث منه
        db.set_outbox_status(outbox_id, OUTBOX_SENDING, submitted_at)
        try:
            await client.send_message(conversation_id, text)
        except ApiError as exc:
            # رفض مؤكد (4xx) ⇒ 'failed'؛ غير كده (شبكة/مهلة/5xx) ⇒ 'unknown' — مش إعادة تلقائية.
            if is_permanent(exc):
                db.set_outbox_status(outbox_id, OUTBOX_FAILED, now_iso(), f"HTTP {exc.status_code}")
                await safe_send(bot, chat_id, f"البرومت اترفض: {describe_status(exc.status_code)}")
            else:
                db.set_outbox_status(outbox_id, OUTBOX_UNKNOWN, now_iso(), safe_error_label(exc))
                await safe_send(
                    bot, chat_id,
                    "مش قادرين نتأكد إن البرومت وصل. راجعه من الموقع قبل ما تعيد الإرسال.",
                )
            return
        except asyncio.CancelledError:
            # اتقطع أثناء الإرسال (shutdown) ⇒ النتيجة غامضة، مايتعادش تلقائياً.
            db.set_outbox_status(outbox_id, OUTBOX_UNKNOWN, now_iso(), "اتقطع أثناء الإرسال")
            raise

        db.set_outbox_status(outbox_id, OUTBOX_SENT, now_iso())
        await safe_send(bot, chat_id, "اتبعت ✅ الشات اتضاف للمتابعة.")
        # نبدأ المتابعة من الحالة الفعلية المرصودة للشات، مش من "running" مفترضة.
        # الـ API مابيرجّعش أي معرّف (run id / event id) يربط البرومت الجديد بالـ run
        # بتاعه، فمفيش طريقة نأكد بيها إن الـ run الجديد بدأ. لو الشات كان منتهي قبل
        # الإرسال وحالته لسه "finished" (الـ run الجديد ماتحدّثش بعد)، تسجيل "running"
        # كان هيدّي المراقب انتقال وهمي ويسلّم تقرير قديم. بتسجيل الحالة الفعلية
        # بنسيب المراقب يسلّم بس لما يشوف انتقال حقيقي من حالة مش منتهية لحالة منتهية
        # (fail closed). التفاصيل في تقرير TASK 04A-3.
        db.add_watched(conversation_id, conv.get("title", ""), chat_id)
        db.set_last_state(conversation_id, conv.get("execution_status") or "")
        # U01: المراقب مابيعلنش الانتهاء غير بتقرير أحدث من وقت الإرسال ده.
        db.mark_submitted(conversation_id, submitted_at)
    except ApiError as exc:
        # فشل قبل الـ POST (قراءة الشات / تشغيل الـ sandbox): الإرسال مابدأش ⇒ آمن يتعاود،
        # بس بحد (TASK 53): أول محاولة بتبلّغ (مؤقّت)، وبعد استنفاد الحد نعلّمه 'failed' مرة واحدة.
        attempts = db.bump_outbox_attempt(outbox_id, now_iso(), safe_error_label(exc))
        if attempts >= MAX_OUTBOX_ATTEMPTS:
            db.set_outbox_status(
                outbox_id, OUTBOX_FAILED, now_iso(), f"استنفد {attempts} محاولات"
            )
            await safe_send(bot, chat_id, _OUTBOX_EXHAUSTED_NOTICE)
        elif attempts == 1:
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
            db.set_creation_status(job_id, CREATION_UNKNOWN, now_iso(), safe_error_label(exc))
            await safe_send(bot, chat_id, _UNKNOWN_CREATION_NOTICE)
            return
        await _finish_creation(client, db, bot, job_id, chat_id, repo, conversation_id, base_url)
        return

    # مفيش task_id معروف ⇒ إحنا (بإذن الله) أول من يعمل POST. نسجّل 'starting' أولاً.
    db.set_creation_starting(job_id, now_iso())
    try:
        task_id = await client.start_conversation(text, repo)
    except ApiError as exc:
        if is_permanent(exc):
            db.set_creation_status(job_id, CREATION_FAILED, now_iso(), f"HTTP {exc.status_code}")
            await safe_send(bot, chat_id, f"فشل بدء الشات: {describe_status(exc.status_code)}")
        else:
            # فشل قبل ما نتأكد إن الـ POST اتعمل ⇒ غامض، مايتعادش تلقائياً.
            db.set_creation_status(job_id, CREATION_UNKNOWN, now_iso(), safe_error_label(exc))
            await safe_send(bot, chat_id, _UNKNOWN_CREATION_NOTICE)
        return
    except asyncio.CancelledError:
        # اتقطع أثناء POST البدء ⇒ غامض، مايتعادش تلقائياً.
        db.set_creation_status(job_id, CREATION_UNKNOWN, now_iso(), "اتقطع أثناء POST البدء")
        raise

    # الـ task_id اترجّع فعلاً ⇒ نسجّله (مش مخترع). لو التسجيل فشل (قاعدة مقفولة/انقطاع)،
    # الحالة تفضل 'starting' بلا task_id ⇒ التعافي يتعامل معاها كغامضة (مايعملش POST تاني).
    db.set_creation_starting(job_id, now_iso(), task_id=task_id)

    try:
        conversation_id = await client.wait_for_start(task_id)
    except ApiError as exc:
        db.set_creation_status(job_id, CREATION_UNKNOWN, now_iso(), safe_error_label(exc))
        await safe_send(bot, chat_id, _UNKNOWN_CREATION_NOTICE)
        return
    except asyncio.CancelledError:
        db.set_creation_status(job_id, CREATION_UNKNOWN, now_iso(), "اتقطع أثناء استطلاع البدء")
        raise

    await _finish_creation(client, db, bot, job_id, chat_id, repo, conversation_id, base_url)


async def _finish_creation(
    client, db, bot, job_id: int, chat_id: int, repo, conversation_id: str, base_url: str
) -> None:
    """اتأكد بدء الشات: نسجّل 'done' + نتابع الشات + نبلّغ الرابط."""
    db.set_creation_done(job_id, now_iso(), conversation_id)
    db.add_watched(conversation_id, repo or "", chat_id)
    db.set_last_state(conversation_id, "running")
    link = f"{base_url.rstrip('/')}/canvas/conversations/{conversation_id}"
    await safe_send(bot, chat_id, f"بدأ الشات ✅\n{link}")


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
