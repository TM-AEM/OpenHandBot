"""حلقة استطلاع مخصّصة (Stage 2، Option A) — بديل Updater بتاع PTB.

الخلفية (ADR OHB2-TELEGRAM-ACK-ARCHITECTURE، §§18/22/23/25/30): في إعداد PTB الافتراضي
(`run_polling`) بيقدّم `_last_update_id` **لحظة الطابور** (قبل تنفيذ الـ handler) ⇒ تيليجرام
بيعتبر التحديث **مقروءًا** قبل ما يتعالج. الحلقة دي بتفصل الاتنين: بنسحب بـ offset مبني على
**الحدّ الدائم المؤهّل** (`settings.acknowledgment_boundary`)، وبنقدّم الـ offset **بس** بعد ما
نتيجة التحديث الدائمة تتثبّت.

التصميم:
- `Application` مبني بـ `updater(None)` ⇒ PTB بيسييب `update_queue` + `_update_fetcher`
  (بيوزّع على نفس الـ handlers)، **بس مفيش Updater** ⇒ مفيش سحب تلقائي ⇒ **مفيش poller تاني**.
- حلقة **واحدة** بتستدعي `bot.get_updates` بنفسها وبتغذّي `application.update_queue`.
- التسلسل إجباري: `await update_queue.put(u)` ثم `await update_queue.join()` — حاجز اكتمال
  مُتحقَّق من المصدر (PTB بينادي `task_done()` في `finally` بعد ما `process_update` تخلّص).
  ده **مش** دليل نجاح (PTB بيبتلع الاستثناءات) ⇒ الحكم **من القاعدة** (نتيجة مُسجَّلة).

الإقرار الفعلي عند تيليجرام بيحصل **بس** لما نداء `getUpdates` الجاي يستخدم offset أعلى —
واللي بيحصل **بعد** تثبيت النتيجة الدائمة. مفيش ادّعاء exactly-once خارجي (at-most-once
+ إعادة تسليم idempotent).
"""
from __future__ import annotations

import asyncio
import logging
import signal

from telegram.error import TelegramError

from . import outbox
from . import update_outcomes

log = logging.getLogger(__name__)

# D1: أنواع التحديثات المدعومة فعليًا (تسجيل الـ handlers في `bot/app.py`). كل نوع تاني
# مابيوصلش أصلًا ⇒ مفيش «مفيش handler مطابق» للأنواع دي. الأنواع جوّه النوع الواحد (زي
# `message` بنوع مش مدعوم، أو `callback_query` بـ pattern مش مطابق) بتغطّيها آلية الـ fallback.
ALLOWED_UPDATES: tuple[str, ...] = ("message", "callback_query")

# مهلة الاستطلاع الطويل (ثواني). الحلقة بتصحى كل دورة عشان تتحقق من الإيقاف.
POLL_TIMEOUT_SECONDS = 30
# حدود إعادة المحاولة على الأخطاء العابرة (شبكة/تيليجرام).
BACKOFF_START_SECONDS = 1.0
BACKOFF_MAX_SECONDS = 30.0


class TelegramPoller:
    """حلقة `getUpdates` واحدة داخل نفس العملية — بديل Updater.

    مسؤولياتها: `deleteWebhook(drop_pending_updates=False)` عند الإقلاع، سحب التحديثات
    بالـ offset الصحيح، التوزيع + الانتظار، تحديد النتائج من القاعدة (مع fallback للتحديثات
    غير المطابقة)، وتثبيت النتائج + الحدّ **في معاملة واحدة** ثم تقديم الـ offset.
    """

    def __init__(
        self,
        application,
        db,
        *,
        allowed_updates: tuple[str, ...] = ALLOWED_UPDATES,
        poll_timeout: int = POLL_TIMEOUT_SECONDS,
    ) -> None:
        self.application = application
        self.db = db
        self.allowed_updates = tuple(allowed_updates)
        self.poll_timeout = poll_timeout
        # الـ offset اللي هنبعت به في `getUpdates` الجاي. None = «من أقدم تحديث غير مؤكَّد»
        # (تيليجرام مايأكّدش حاجة لما نبعت None ⇒ المعلّق محفوظ).
        self._next_offset: int | None = None
        self._stop = asyncio.Event()
        self._backoff = BACKOFF_START_SECONDS

    # ------------------------------------------------------------------ lifecycle
    def stop(self) -> None:
        """يطلب إيقاف الحلقة (بيستخدمه معالج الإشارة أو الاختبار)."""
        self._stop.set()

    async def bootstrap(self) -> None:
        """إقلاع آمن: `deleteWebhook(drop_pending_updates=False)` ثم حساب offset البداية.

        **مابيمسحش** المعلّق أبدًا (D2). لو فيه حدّ دائم `B` ⇒ نستأنف من `B+1`؛ لو مفيش ⇒
        `None` (من أقدم غير مؤكَّد) ⇒ **حفظ المعلّق**. ما بنستنتجش «تثبيت جديد» من غياب الحدّ.
        """
        await self._delete_webhook_with_retry()
        boundary = self.db.get_acknowledgment_boundary()
        self._next_offset = None if boundary is None else boundary + 1
        log.info(
            "استطلاع مخصّص: الحدّ الدائم=%s ⇒ offset البداية=%s (allowed_updates=%s)",
            boundary, self._next_offset, list(self.allowed_updates),
        )

    async def _delete_webhook_with_retry(self) -> None:
        """`deleteWebhook(drop_pending_updates=False)` مع إعادة محاولة للأخطاء العابرة.

        حاسم: `getUpdates` **محجوبة** وقت وجود webhook فعّال ⇒ لازم الحذف ينجح قبل السحب.
        """
        while not self._stop.is_set():
            try:
                await self.application.bot.delete_webhook(drop_pending_updates=False)
                return
            except TelegramError as exc:
                log.warning(
                    "تعذّر حذف الـ webhook (%s) — إعادة محاولة بعد %.1fث",
                    type(exc).__name__, self._backoff,
                )
                await self._sleep_backoff()

    # ------------------------------------------------------------------ loop
    async def run(self) -> None:
        """يشغّل الحلقة لحد الإيقاف. بيحطّ معالجات إشارات لـ SIGINT/SIGTERM."""
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._stop.set)
            except (NotImplementedError, RuntimeError):  # ويندوز/لوب مخصّص
                pass
        await self.bootstrap()
        while not self._stop.is_set():
            try:
                updates = await self.fetch()
            except TelegramError as exc:
                log.warning(
                    "فشل سحب التحديثات (%s) — إعادة محاولة بعد %.1fث",
                    type(exc).__name__, self._backoff,
                )
                await self._sleep_backoff()
                continue
            except Exception as exc:  # noqa: BLE001 — فشل داخلي غير متوقّع: نلوج بوضوح
                log.exception("فشل غير متوقّع في حلقة الاستطلاع (%s)", type(exc).__name__)
                await self._sleep_backoff()
                continue
            self._backoff = BACKOFF_START_SECONDS
            if not updates:
                continue
            try:
                await self.process_updates(updates)
            except TelegramError as exc:
                log.warning(
                    "فشل تثبيت/معالجة دفعة (%s) — إعادة المحاولة في الدورة الجاية",
                    type(exc).__name__,
                )
                await self._sleep_backoff()
            except Exception as exc:  # noqa: BLE001 — ممنوع كتم صامت
                log.exception("فشل معالجة دفعة تحديثات (%s)", type(exc).__name__)
                await self._sleep_backoff()

    async def fetch(self):
        """سحب تحديثات بالـ offset الحالي. مفصولة عشان الاختبار يحاكيها بسهولة."""
        return await self.application.bot.get_updates(
            offset=self._next_offset,
            timeout=self.poll_timeout,
            allowed_updates=self.allowed_updates,
        )

    # ------------------------------------------------------------------ batch
    async def process_updates(self, updates) -> int | None:
        """يعالج دفعة: توزيع + انتظار، تحديد النتائج، تثبيت ذرّي، تقديم الـ offset.

        بترجّع الحدّ الجديد (أو None). الـ offset بيتقدّم **بس** لو الحدّ طلع قيمة (يعني
        فيه بادئة مؤهّلة)؛ لو أول تحديث غير مؤهّل ⇒ الحدّ مايتقدّمش ⇒ إعادة تسليم.
        """
        for update in updates:
            await self.dispatch_and_wait(update)
        pairs = self.collect_outcomes(updates)
        new_boundary = self.db.commit_batch_outcomes(pairs, outbox.now_iso())
        self.advance_offset(new_boundary)
        if new_boundary is None and updates:
            # حجب head-of-line مقصود (fail-closed): أول تحديث غير مؤهّل بيمنع تقدّم الحدّ ⇒
            # إعادة تسليم لاحقة. بنلوج بوضوح للمراقبة (مفيش تغيير دلالات).
            log.warning(
                "حدّ الإقرار مااتقدّمش: أول تحديث غير مؤهّل (%s) بيحجز الدفعة — إعادة تسليم.",
                getattr(updates[0], "update_id", None),
            )
        return new_boundary

    async def dispatch_and_wait(self, update) -> None:
        """يحطّ التحديث في طابور PTB وينتظر اكتمال معالجته (نجاح أو فشل مُسجَّل)."""
        await self.application.update_queue.put(update)
        await self.application.update_queue.join()

    def collect_outcomes(self, updates) -> list[tuple[int, str]]:
        """يبني نتائج الدفعة **بترتيب الاستقبال** من القاعدة (مصدر الحكم، مش رجوع الدالة).

        - نتيجة مُسجَّلة (نجاح/فشل/تجاهل/غموض/مكرّر) ⇒ **بنحتفظ بها كما هي**.
        - تحديث مطابق: الـ handler بيسجّل نتيجته بنفسه (بما فيها الفشل اللي معالج الأخطاء
          بيسجّله) ⇒ بنلاقيها مُسجَّلة.
        - تحديث **مفيش له أي handler مطابق**: الـ fallback (`handle_unmatched_update`، آخر
          handler في group 0) بيسجّل `EXPLICITLY_IGNORED` ⇒ بنلاقيها مُسجَّلة.
        - **مفيش نتيجة** (مثلاً كتابة فشلت، أو استثناء مالوش معالج أخطاء ناجح) ⇒
          `PARTIAL_OR_UNKNOWN` (غير مؤهّل، fail-closed) ⇒ الحدّ يتوقف عنده.
        """
        pairs: list[tuple[int, str]] = []
        for update in updates:
            update_id = getattr(update, "update_id", None)
            if not isinstance(update_id, int):
                continue
            outcome = self.db.update_outcome(update_id)
            if outcome is None:
                outcome = update_outcomes.PARTIAL_OR_UNKNOWN
            pairs.append((update_id, outcome))
        return pairs

    def advance_offset(self, new_boundary: int | None) -> None:
        """يقدّم offset السحب **بس** لو فيه بادئة مؤهّلة (الحدّ قيمة).

        الحدّ نفسه مونوتوني (بيحرسه `commit_batch_outcomes`) ⇒ الـ offset مايتراجعش.
        """
        if new_boundary is not None:
            self._next_offset = new_boundary + 1

    # ------------------------------------------------------------------ helpers
    async def _sleep_backoff(self) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=self._backoff)
        except asyncio.TimeoutError:
            pass
        self._backoff = min(self._backoff * 2, BACKOFF_MAX_SECONDS)


async def run_bot(application) -> None:
    """يشغّل البوت بالحلقة المخصّصة (بديل `Application.run_polling`).

    نفس مسؤوليات `run_polling`: تهيئة ← `post_init` ← `start` ← الاستطلاع ← `stop` ←
    `shutdown` ← `post_shutdown`. **مفيش** Updater ومفيش poller تاني. `shutdown` مضمون في
    كل الحالات (حتى لو `post_init` رمى استثناء) عشان مايسبش موارد معلّقة.
    """
    await application.initialize()
    started = False
    try:
        if application.post_init is not None:
            await application.post_init(application)
        if application.bot_data.get("startup_failed"):
            log.error(
                "إقلاع متوقف: %s — مفيش استطلاع ولا workers.",
                application.bot_data.get("startup_failed"),
            )
            return
        await application.start()
        started = True
        poller = TelegramPoller(application, application.bot_data["db"])
        application.bot_data["poller"] = poller
        await poller.run()
    finally:
        if started:
            await application.stop()
            if application.post_stop is not None:
                await application.post_stop(application)
        await application.shutdown()
        if application.post_shutdown is not None:
            await application.post_shutdown(application)
