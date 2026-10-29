"""المراقب: polling كل 20-30 ثانية وإشعار الانتهاء.

TASK 54: إشعارات الانتهاء ليها ميزانية محاولات مستمرة (MAX_WATCH_NOTIFY_RETRIES،
العدّاد في watched.retry_count). **مش تسليم exactly-once**: لو العملية اتقطعت بين ما
تيليجرام يقبل الرسالة وما نسجّل النجاح، ممكن الرسالة تتبعت تاني — لأن مفيش آلية
idempotency مثبَّتة بين تيليجرام وقاعدة البيانات.

NTF-13: بعد ما تيليجرام يقبل رسالة انتهاء، بنكتب **علامة تسليم معلّق** على صف المتابعة
(watched.pending_delivery_state) قبل التسجيل الدائم. العلامة دي بتخلّي إزالة المتابعة من
أي مسار (يدوي/المراقب) واسترجاع إعادة التشغيل يكمّلوا التسجيل بدل ما يسيبوا حالة قديمة
يعيد المُبلّغ إرسالها.

نافذة إعادة التشغيل (متبقّية وغير قابلة للإزالة): لو العملية اتقطعت **قبل** ما العلامة
تتكتب على القرص، بعد إعادة التشغيل مايبقاش فيه أثر للتسليم ⇒ ممكن يُعاد الإرسال. تيليجرام
مابيرجّعش تأكيد دائم نعتمد عليه لإثبات الاستلام بعد إعادة التشغيل، فالحالة دي غامضة
بطبيعتها. العلامة بتضيّق النافذة (بين قبول تيليجرام وكتابة العلامة) لكن ما بتلغيهاش،
وما بنزعمش exactly-once.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from telegram.error import TelegramError

from .errors import ApiError
from .messages import SANDBOX_ERROR, get_status, is_terminal, state_label
from .openhands_client import parse_timestamp
from .sender import send_long

log = logging.getLogger(__name__)

# U01: لو الشات وصل لحالة منتهية ومفيش تقرير أحدث من البرومبت بعد المهلة دي،
# نبلّغ صراحةً (مش نسكت ولا نبعت تقرير قديم).
START_TIMEOUT = timedelta(minutes=10)
# مهلة المتابعة الكاملة: بعدها إشعار واضح بدل حذف صامت.
FOLLOW_TIMEOUT = timedelta(hours=24)
# عدد الدورات المتتالية اللي الشات فيها مش ظاهر قبل ما نعتبره اتمسح فعلاً.
MISSING_LIMIT = 3
# TASK 54: أقصى عدد محاولات فاشلة متتالية لإشعار انتهاء واحد قبل ما نستسلم.
# العدّاد متخزّن في SQLite (watched.retry_count) فمابيتصفّرش بإعادة التشغيل، وبيرجع 0
# لما تبدأ دورة إشعار جديدة (حالة غير منتهية جديدة / إضافة متابعة).
MAX_WATCH_NOTIFY_RETRIES = 5
# حالات منتهية ممكن ما يطلعش فيها رد للـ agent، فانتقال حقيقي ليها كافي.
_NO_REPORT_STATES = {"error", "stuck", "waiting_for_confirmation", SANDBOX_ERROR}


class Watcher:
    def __init__(
        self,
        client,
        db,
        bot,
        chat_id: int,
        interval: int = 25,
        clock=None,
        allowed_chats=None,
        on_owner_delivery=None,
    ) -> None:
        if not isinstance(interval, int) or isinstance(interval, bool) or interval <= 0:
            raise ValueError("فترة المراقب لازم تكون رقم صحيح موجب")
        # وجهات الإشعار المسموحة (محادثات خاصة للمستخدمين المسموحين). أي شات متابَع
        # محفوظ له chat_id برّاها (مثلاً جروب قديم) الإشعار بيروح للوجهة الافتراضية.
        self._allowed_chats = frozenset(allowed_chats) if allowed_chats else None
        # نقطة التنسيق الاختيارية مع المُبلّغ العام: بتتنادى **بعد** ما تليجرام يأكّد
        # نجاح إشعار مملوك للمراقب، بنفس الحالة المعيارية. بتُستخدم لسدّ نافذة التسليم
        # المتبقية (بين فحص المُبلّغ للمتابعة وإرساله). بتبقى None في الاستخدام المستقل.
        self._on_owner_delivery = on_owner_delivery
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._misses: dict[str, int] = {}
        # NTF-15/17/19: محادثات اتّبعت لها رسالة انتهاء (تليجرام قبل) لكن كتابة **علامة التسليم
        # المعلّق** نفسها فشلت (خطأ SQLite قبل أي أثر دائم). بنسيب المتابعة (ما بنشيلهاش)
        # والقيمة = (الحالة اللي **اتّبعت فعلًا**, معرّف دورة المتابعة `watch_seq` ساعتها)،
        # عشان الدورة الجاية تعيد كتابة العلامة بالحالة الصح **قبل أي إرسال**، والإزالة
        # اليدوية تقدر تكمّل التسجيل الذرّي. المعرّف الثابت بيمنع تلميح قديم إنه يأثّر على
        # متابعة جديدة. مش مصدر الحقيقة (ده الصف الدائم `watched.pending_delivery_state`)؛
        # تلميح in-memory مكمّل. لو العملية قفلت قبل ما العلامة تتكتب، تيليجرام مابيرجّعش
        # تأكيد دائم ⇒ الحالة غامضة بطبيعتها (ممكن إعادة إرسال) — مش بنزعم exactly-once.
        self._marker_pending: dict[str, tuple[str, str]] = {}
        self._client = client
        self._db = db
        self._bot = bot
        self._default_chat_id = chat_id
        self._interval = interval
        self._task: asyncio.Task | None = None
        # NTF-20: ننسّق التلميح in-memory مع أي دورة متابعة جديدة يبدأها أي مستدعي
        # (`add_watched(new_lifecycle=True)`)، حتى لو المستدعي مايعرفش المراقب.
        db.on_new_watch_lifecycle = self._on_new_watch_lifecycle

    def _on_new_watch_lifecycle(self, conversation_id: str) -> None:
        """NTF-20: hook بيتنادى من `Database.add_watched` قبل بدء دورة متابعة جديدة.

        بيثبّت أي تلميح in-memory لنفس دورة المتابعة الحالية كعلامة دائمة (أو يمسحه لو
        كتابة العلامة فشلت أصلاً)، عشان الدورة الجديدة تسوّيها (تسجّل `notified_status`
        وتمسحها) بدل ما الدليل يتفقد. تلميح بمعرّف مختلف (دورة أحدث) بيتجاهله/يتشال.
        """
        w = self._db.get_watched(conversation_id)
        hint = self._marker_pending.get(conversation_id)
        # NTF-23: دورة متابعة جديدة ⇒ نصفّر عدّاد الغياب (قرار «مش موجود» قديم ما يتطبّقش
        # على دورة جديدة بنفس المحادثة).
        self._misses.pop(conversation_id, None)
        if hint is None:
            return
        if w is not None and hint[1] == w.watch_seq:
            self._db.set_pending_delivery(conversation_id, hint[0])
        self._marker_pending.pop(conversation_id, None)

    def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    def set_owner_delivery(self, callback) -> None:
        """يضبط نقطة التنسيق مع المُبلّغ بعد الإنشاء (المراقب بيتعمل قبل المُبلّغ).

        لسه بتبقى None في الاستخدام المستقل (مافيش hook) ⇒ التسجيل المباشر في القاعدة.
        """
        self._on_owner_delivery = callback

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                log.exception("خطأ في دورة المراقب")
            await asyncio.sleep(self._interval)

    async def tick(self) -> None:
        watched = self._db.list_watched()
        if not watched:
            return
        ids = [w.conversation_id for w in watched]
        try:
            convs = {c["id"]: c for c in await self._client.get_conversations(ids)}
        except ApiError as exc:
            log.warning("تعذّر جلب حالة الشاتات: %s", exc)
            return

        for w in watched:
            conv = convs.get(w.conversation_id)
            if not conv:
                await self._handle_missing(w)
                continue
            self._misses.pop(w.conversation_id, None)
            self._refresh_title(w, conv)
            state = get_status(conv)
            # NTF-15: عزل الأخطاء لكل شات (يشمل مسار الاسترجاع كمان). خطأ في محادثة واحدة
            # ما يوقفش باقي الدورة. بنسجّل النوع بس (مش النص، ممكن يحتوي أسرار).
            try:
                if not await self._handle_pending_recovery(w, state):
                    continue
                if parse_timestamp(w.submitted_at) is not None:
                    await self._process_submitted(w, conv, state)
                else:
                    await self._process_legacy(w, conv, state)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                log.error(
                    "خطأ غير متوقع في متابعة الشات %s (%s)", w.conversation_id, type(exc).__name__
                )

    def _refresh_title(self, w, conv: dict) -> None:
        """يخزّن العنوان الطازج للشات المتابَع (لو اتغيّر). معزول: أي خطأ ما يوقفش الدورة."""
        try:
            self._db.update_watched_title(w.conversation_id, conv.get("title") or "")
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "تعذّر تحديث عنوان الشات %s (%s)", w.conversation_id, type(exc).__name__
            )

    async def _handle_missing(self, w) -> None:
        """شات مش ظاهر في الرد: ممكن يكون عطل مؤقت، فنستنى كذا دورة ثم نبلّغ صراحةً."""
        count = self._misses.get(w.conversation_id, 0) + 1
        self._misses[w.conversation_id] = count
        if count < MISSING_LIMIT:
            return
        text = f"الشات «{w.title or 'بدون عنوان'}» لم يعد موجوداً على OpenHands، وتم إيقاف متابعته."
        if await self._deliver(w, text):
            self._misses.pop(w.conversation_id, None)
            self._db.remove_watched_if_seq(w.conversation_id, w.watch_seq)

    async def _process_legacy(self, w, conv: dict, state: str | None) -> None:
        """متابعة بدون برومبت مسجّل: الإشعار على انتقال حقيقي من حالة غير منتهية لمنتهية."""
        if is_terminal(state) and not is_terminal(w.last_state):
            try:
                delivered = await self._notify(w, conv, state)
            except TelegramError as exc:
                self._handle_notify_failure(w, exc)
                return
            if not delivered:
                return  # اتسلّم لتليجرام بس التسجيل فشل: هنسيبه متابَع ومانشيلوش
            self._db.remove_watched_if_seq(w.conversation_id, w.watch_seq)
            return
        if self._expired(w.added_at, FOLLOW_TIMEOUT) and not is_terminal(state):
            if await self._notify_timeout(w, conv, state):
                return
        self._db.advance_watched_state(w.conversation_id, state or "")

    async def _process_submitted(self, w, conv: dict, state: str | None) -> None:
        """U01: الانتهاء لازم يتثبت بتقرير أحدث من وقت إرسال البرومبت."""
        submitted = parse_timestamp(w.submitted_at)
        transition = is_terminal(state) and not is_terminal(w.last_state)
        if is_terminal(state):
            try:
                report = await self._client.get_reply_since(w.conversation_id, submitted)
            except ApiError as exc:
                log.warning(
                    "تعذّر جلب أحداث الشات %s (HTTP %s)، هيتعاود في الدورة الجاية",
                    w.conversation_id, getattr(exc, "status_code", "?"),
                )
                return  # عطل مؤقت: ما نغيّرش الحالة المسجّلة ولا نشيل المتابعة
            if report is not None or (state in _NO_REPORT_STATES and transition):
                try:
                    delivered = await self._notify(w, conv, state, report=report, fresh_only=True)
                except TelegramError as exc:
                    self._handle_notify_failure(w, exc)
                    return
                if not delivered:
                    return  # اتسلّم لتليجرام بس التسجيل فشل: هنسيبه متابَع ومانشيلوش
                self._db.remove_watched_if_seq(w.conversation_id, w.watch_seq)
                return
            if self._expired(w.submitted_at, START_TIMEOUT):
                title = conv.get("title") or w.title or "بدون عنوان"
                text = (
                    f"الشات «{title}»: لم يظهر تقرير جديد بعد البرومبت الأخير "
                    f"(مرّت أكثر من {int(START_TIMEOUT.total_seconds() // 60)} دقائق). "
                    f"الحالة الحالية: {state_label(state)}. راجع الشات من الموقع."
                )
                if await self._deliver(w, text):
                    self._db.remove_watched_if_seq(w.conversation_id, w.watch_seq)
                return
            return  # بنستنى تقرير أحدث؛ الحالة المسجّلة تفضل زي ما هي
        if self._expired(w.submitted_at, FOLLOW_TIMEOUT):
            if await self._notify_timeout(w, conv, state):
                return
        self._db.advance_watched_state(w.conversation_id, state or "")

    async def _notify_timeout(self, w, conv: dict, state: str | None) -> bool:
        title = conv.get("title") or w.title or "بدون عنوان"
        text = (
            f"انتهت مهلة متابعة الشات «{title}» (24 ساعة) والشات لسه مش منتهي "
            f"(الحالة: {state_label(state)}). تم إيقاف المتابعة، راجعه من الموقع."
        )
        if await self._deliver(w, text):
            self._db.remove_watched_if_seq(w.conversation_id, w.watch_seq)
            return True
        return False

    async def _deliver(self, w, text: str) -> bool:
        try:
            await send_long(self._destination(w), text, self._bot)
        except TelegramError as exc:
            self._log_delivery_failure(w, exc)
            return False
        return True

    def _destination(self, w) -> int:
        chat_id = w.chat_id or self._default_chat_id
        if self._allowed_chats is not None and chat_id not in self._allowed_chats:
            return self._default_chat_id
        return chat_id

    def _expired(self, since_iso: str | None, limit: timedelta) -> bool:
        since = parse_timestamp(since_iso)
        return since is not None and self._clock() - since > limit

    @staticmethod
    def _log_delivery_failure(w, exc: Exception) -> None:
        # عزل الأخطاء لكل شات؛ نسجّل النوع بس، مش نص الاستثناء (ممكن يحتوي أسرار).
        log.warning(
            "فشل إشعار الشات %s (%s)، هيتعاود في الدورة الجاية",
            w.conversation_id, type(exc).__name__,
        )

    def _on_persist_failure(self, w, state: str, exc: Exception) -> None:
        """فشل تسجيل تسليم اتّبع فعلًا (تليجرام أكّد بس SQLite رفض).

        NTF-13: العلامة الدائمة (watched.pending_delivery_state) **اتكتبت بالفعل** قبل
        محاولة التسجيل، فمافيش حالة in-memory محتاجة تحديث. بنسيب الشات متابَع (ما
        بنشيلوش كإن التسجيل نجح) ونسجّل تحذير؛ الدورة الجاية هتعيد التسجيل قبل أي إرسال.
        """
        log.warning(
            "تعذّر تسجيل تسليم الشات %s (%s)؛ هنسيبه متابَع ونعيد المحاولة قبل أي إرسال",
            w.conversation_id, type(exc).__name__,
        )

    def _handle_notify_failure(self, w, exc: Exception) -> None:
        """فشل إشعار انتهاء: يزوّد العدّاد المستمر، وبعد الحد يستسلم ويسيب المتابعة.

        العدّاد متخزّن في SQLite فمايتصفّرش بإعادة التشغيل. لما يوصل الحد بنشيل المتابعة
        عشان نفس الإشعار مايتحاولش تاني كل دورة. بنسجّل النوع بس (ممكن يحوي أسرار).
        NTF-23: العدّاد والإزالة مشروطان بمعرّف الدورة الملتقَط (`watch_seq`): لو دورة
        جديدة اتعملت أثناء await، قرار الفشل القديم ما يتطبّقش على الدورة الجديدة
        (ما نزوّدش عدّادها ولا نشيلها).
        """
        count = self._db.increment_watched_retry_if_seq(w.conversation_id, w.watch_seq)
        if count == 0:
            return  # الدورة اتغيّرت/الصف مش موجود ⇒ قرار قديم ما يتطبّقش
        if count >= MAX_WATCH_NOTIFY_RETRIES:
            log.warning(
                "استسلمنا من إشعار انتهاء الشات %s بعد %d محاولة فاشلة (%s)؛ هنوقف المتابعة",
                w.conversation_id, count, type(exc).__name__,
            )
            self._db.remove_watched_if_seq(w.conversation_id, w.watch_seq)
        else:
            self._log_delivery_failure(w, exc)

    async def _notify(
        self, w, conv: dict, state: str, report: str | None = None, fresh_only: bool = False
    ) -> bool:
        """يبعت إشعار انتهاء ويسجّله. True = اتسجّل التسليم، False = اتسلّم بس التسجيل فشل.

        بيرمي `TelegramError` لو الإرسال نفسه فشل (المستدعي بيتعامل معاها). أخطاء التسجيل
        (SQLite) بتتسجّل كحالة معلّقة وترجّع False — ما بترميش، فما بتتلخبطش مع فشل الإرسال.
        """
        title = conv.get("title") or "بدون عنوان"
        header = f"انتهى الشات: {title}\nالحالة: {state_label(state)}"
        if state == "waiting_for_confirmation":
            header += "\nالشات مستني تأكيدك، افتح الموقع للمتابعة."
        if fresh_only:
            # ما نجيبش "آخر رد" أبداً هنا: ممكن يبقى تقرير قديم. نستخدم بس التقرير
            # الأحدث من البرومبت اللي المراقب لقاه، أو نبعت العنوان بدونه.
            reply = report
        else:
            try:
                reply = await self._client.get_last_reply(w.conversation_id)
            except ApiError:
                reply = None
        text = header + ("\n\n" + reply if reply else "")
        await send_long(self._destination(w), text, self._bot)
        # NTF-13/15: تليجرام أكّد التسليم ⇒ نكتب **علامة التسليم المعلّق** على الصف أول
        # (قبل التسجيل الدائم). لو الكتابة نفسها فشلت، بنسيب المتابعة ونسجّل تلميح in-memory
        # عشان الدورة الجاية تعيد كتابة العلامة **قبل أي إرسال** بدل ما تعيد الإرسال.
        try:
            self._db.set_pending_delivery(w.conversation_id, state)
        except Exception as exc:  # noqa: BLE001
            row = self._db.get_watched(w.conversation_id)
            self._marker_pending[w.conversation_id] = (state, row.watch_seq if row else "")
            log.warning(
                "تعذّر تسجيل علامة تسليم الشات %s (%s)، هنعيد المحاولة قبل أي إرسال",
                w.conversation_id, type(exc).__name__,
            )
            return False
        self._marker_pending.pop(w.conversation_id, None)
        try:
            self._persist_delivery(w.conversation_id, state)
        except Exception as exc:  # noqa: BLE001
            self._on_persist_failure(w, state, exc)
            return False
        self._db.clear_pending_delivery(w.conversation_id)
        return True

    def _persist_delivery(self, conversation_id: str, state: str) -> None:
        """تسجيل تسليم حالة نهائية اتّبع فعلًا (تليجرام أكّد). بيرمي لو التسجيل فشل.

        بنسجّل عبر الـ hook لو موجود (نقطة التنسيق الصريحة مع المُبلّغ)، وإلا مباشرةً في
        القاعدة (استخدام المراقب المستقل). النداء بيحصل **قبل** ما المتابعة تتشال.
        """
        now = datetime.now(timezone.utc).isoformat()
        if self._on_owner_delivery is not None:
            self._on_owner_delivery(conversation_id, state, now)
        else:
            self._db.record_notification_sent(conversation_id, state, now)

    def unwatch(self, conversation_id: str) -> None:
        """يزيل متابعة يدويًا مع الحفاظ على عدم الإرسال المكرّر (NTF-17/20).

        NTF-20: بنسوّي أي تسليم معلّق **دائم** الأول (نسجّله ونمسح العلامة) قبل الحذف —
        عشان إزالة المتابعة ما تفقدش دليل تسليم ممكن تيليجرام يكون قبله بالفعل. كمان
        بنسوّي التلميح in-memory لو بيطابق نفس دورة المتابعة. لو التسجيل فشل، الاستثناء
        بيطلع والصف والعلامة بيفضلوا (retry آمن، مفيش حذف صامت).
        """
        reconciled = self._db.reconcile_pending_delivery(conversation_id)
        w = self._db.get_watched(conversation_id)
        hint = self._marker_pending.get(conversation_id)
        if reconciled is None and w is not None and hint is not None and hint[1] == w.watch_seq:
            # مفيش علامة دائمة، بس فيه تلميح لنفس الدورة ⇒ نكمّل التسجيل الذرّي.
            # بنكمّل التسجيل الأول؛ لو فشل، الاستثناء بيطلع والتلميح بيفضل (retry آمن).
            self._db.remove_watched_completing(conversation_id, hint[0])
            self._marker_pending.pop(conversation_id, None)
        else:
            # تسليم اتسوّى بالفعل، أو تلميح قديم/مفيش تلميح ⇒ إزالة عادية (مافيش إرسال مكرّر).
            self._marker_pending.pop(conversation_id, None)
            self._db.remove_watched(conversation_id)

    def request_new_lifecycle(
        self, conversation_id: str, title: str = "", chat_id: int | None = None
    ) -> None:
        """NTF-20: نقطة دخول صريحة لبدء دورة متابعة جديدة بأمان (بتنسيق مع التسليم المعلّق).

        بتفوّض لـ `db.add_watched(new_lifecycle=True)` اللي بيثبّت التلميح in-memory (عبر
        الـ hook) ويسوّي أي علامة دائمة (يسجّل `notified_status` ويمسحها) ويولّد `watch_seq`
        جديد — في معاملة واحدة. كده الدليل ما يتفقدش (مفيش إرسال مكرّر) والدورة الجديدة
        نظيفة، وأي تلميح قديم مايقدرش يأثّر عليها (المعرّف مختلف). لو التسجيل فشل، الاستثناء
        بيطلع والدورة الجديدة ما بتتعملش (مفيش فقد صامت).
        """
        self._db.add_watched(conversation_id, title, chat_id, new_lifecycle=True)

    async def _handle_pending_recovery(self, w, state: str | None) -> bool:
        """NTF-15/17: يعالج التسليم المعلّق قبل الإرسال. True = نكمّل المسار العادي، False = نتوقّف.

        حالتان:
        - العلامة الدائمة موجودة (تسليم اتّبعت بس تسجيله الدائم لسه معلّق، أو استرجاع إعادة
          تشغيل): نسجّلها (بدون إعادة إرسال) ونشيل العلامة؛ لو الحالة الحالية زي المعلّقة،
          الإشعار اتّبعت فعلًا ⇒ نشيل المتابعة ونقف؛ غير كده نكمّل عشان الحالة الأحدث توصل.
        - تلميح `_marker_pending` (الإرسال اتقبل بس كتابة العلامة نفسها فشلت): نعيد كتابة
          العلامة **قبل أي إرسال**؛ لو نجحت نكمّل الاسترجاع العادي، لو لسه فاشلة نقف
          (مفيش إعادة إرسال أعمى). التلميح بيتبط بمعرّف دورة المتابعة (`watch_seq`) فمتابعة
          اتعملت من جديد (معرّف مختلف) بتتجاهله. الاستثناءات بتطلع للمستدعي اللي بيعزلها لكل
          شات (M-1).
        """
        if w.pending_delivery_state is None and w.conversation_id in self._marker_pending:
            hint_state, hint_seq = self._marker_pending[w.conversation_id]
            if hint_seq == w.watch_seq:  # التلميح يخص نفس دورة المتابعة (مش دورة جديدة)
                self._db.set_pending_delivery(w.conversation_id, hint_state)
                self._marker_pending.pop(w.conversation_id, None)
                w = self._db.get_watched(w.conversation_id)
                if w is None:
                    return False
            else:
                self._marker_pending.pop(w.conversation_id, None)  # تلميح قديم: نتجاهله
        if w.pending_delivery_state is not None:
            if not self._recover_pending_delivery(w):
                return False
            if state == w.pending_delivery_state:
                self._db.remove_watched_if_seq(w.conversation_id, w.watch_seq)
                return False
        return True

    def _recover_pending_delivery(self, w) -> bool:
        """NTF-13: يسترجع/يكمّل تسليم معلّق. True = العلامة اتشالت (اتسجّلت)، False = لسه فاشلة.

        الحالة المتسجّلة هي **الحالة اللي اتّبعت فعلًا** (`w.pending_delivery_state`، مش
        الحالة الحالية). كده لو الشات اتحوّل A→B والحالة المعلّقة A، التسجيل بيسجّل A
        (اللي اتّبعت فعلًا)، والمستدعي بيكمّل مع B. لو التسجيل فشل، بنرجّع False والعلامة
        تفضل مكانها (مافيش إعادة إرسال أعمى، ولسه هنعيد المحاولة الدورة الجاية).
        """
        try:
            self._persist_delivery(w.conversation_id, w.pending_delivery_state)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "تعذّر تسجيل تسليم الشات %s (%s)، هنعيد المحاولة في الدورة الجاية",
                w.conversation_id, type(exc).__name__,
            )
            return False
        self._db.clear_pending_delivery(w.conversation_id)
        return True
