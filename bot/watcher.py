"""المراقب: polling كل 20-30 ثانية وإشعار الانتهاء."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from telegram.error import TelegramError

from .errors import ApiError
from .messages import DONE_STATES, state_label
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
# حالات منتهية ممكن ما يطلعش فيها رد للـ agent، فانتقال حقيقي ليها كافي.
_NO_REPORT_STATES = {"error", "stuck", "waiting_for_confirmation"}


class Watcher:
    def __init__(
        self, client, db, bot, chat_id: int, interval: int = 25, clock=None, allowed_chats=None
    ) -> None:
        if not isinstance(interval, int) or isinstance(interval, bool) or interval <= 0:
            raise ValueError("فترة المراقب لازم تكون رقم صحيح موجب")
        # وجهات الإشعار المسموحة (محادثات خاصة للمستخدمين المسموحين). أي شات متابَع
        # محفوظ له chat_id برّاها (مثلاً جروب قديم) الإشعار بيروح للوجهة الافتراضية.
        self._allowed_chats = frozenset(allowed_chats) if allowed_chats else None
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._misses: dict[str, int] = {}
        self._client = client
        self._db = db
        self._bot = bot
        self._default_chat_id = chat_id
        self._interval = interval
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._run())

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
            state = conv.get("execution_status")
            try:
                if parse_timestamp(w.submitted_at) is not None:
                    await self._process_submitted(w, conv, state)
                else:
                    await self._process_legacy(w, conv, state)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                # عزل الأخطاء: خطأ غير متوقع في شات واحد ما يوقفش باقي الدورة. بنسجّل
                # النوع بس (مش نص الاستثناء، ممكن يحتوي أسرار) وهيتعاود في الدورة الجاية.
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
            self._db.remove_watched(w.conversation_id)

    async def _process_legacy(self, w, conv: dict, state: str | None) -> None:
        """متابعة بدون برومبت مسجّل: الإشعار على انتقال حقيقي من حالة غير منتهية لمنتهية."""
        if state in DONE_STATES and w.last_state not in DONE_STATES:
            try:
                await self._notify(w, conv, state)
            except TelegramError as exc:
                self._log_delivery_failure(w, exc)
                return
            self._db.remove_watched(w.conversation_id)
            return
        if self._expired(w.added_at, FOLLOW_TIMEOUT) and state not in DONE_STATES:
            if await self._notify_timeout(w, conv, state):
                return
        self._db.set_last_state(w.conversation_id, state or "")

    async def _process_submitted(self, w, conv: dict, state: str | None) -> None:
        """U01: الانتهاء لازم يتثبت بتقرير أحدث من وقت إرسال البرومبت."""
        submitted = parse_timestamp(w.submitted_at)
        transition = state in DONE_STATES and w.last_state not in DONE_STATES
        if state in DONE_STATES:
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
                    await self._notify(w, conv, state, report=report, fresh_only=True)
                except TelegramError as exc:
                    self._log_delivery_failure(w, exc)
                    return
                self._db.remove_watched(w.conversation_id)
                return
            if self._expired(w.submitted_at, START_TIMEOUT):
                title = conv.get("title") or w.title or "بدون عنوان"
                text = (
                    f"الشات «{title}»: لم يظهر تقرير جديد بعد البرومبت الأخير "
                    f"(مرّت أكثر من {int(START_TIMEOUT.total_seconds() // 60)} دقائق). "
                    f"الحالة الحالية: {state_label(state)}. راجع الشات من الموقع."
                )
                if await self._deliver(w, text):
                    self._db.remove_watched(w.conversation_id)
                return
            return  # بنستنى تقرير أحدث؛ الحالة المسجّلة تفضل زي ما هي
        if self._expired(w.submitted_at, FOLLOW_TIMEOUT):
            if await self._notify_timeout(w, conv, state):
                return
        self._db.set_last_state(w.conversation_id, state or "")

    async def _notify_timeout(self, w, conv: dict, state: str | None) -> bool:
        title = conv.get("title") or w.title or "بدون عنوان"
        text = (
            f"انتهت مهلة متابعة الشات «{title}» (24 ساعة) والشات لسه مش منتهي "
            f"(الحالة: {state_label(state)}). تم إيقاف المتابعة، راجعه من الموقع."
        )
        if await self._deliver(w, text):
            self._db.remove_watched(w.conversation_id)
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

    async def _notify(
        self, w, conv: dict, state: str, report: str | None = None, fresh_only: bool = False
    ) -> None:
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
