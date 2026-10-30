"""المُبلّغ العام: إشعارات استباقية بكل المحادثات (مش المتابَعة بس).

- بيستخدم نفس `OpenHandsClient` والقاعدة `Database` وأداة الإرسال `send_long`.
- اللقطات متخزّنة في SQLite (`notification_state`) مش ملف JSON.
- أول تشغيل (مفيش لقطة سابقة) = تأسيس خط أساس بدون إشعار عن المحادثات المنتهية الموجودة.
- ملكية الإشعار للمحادثات المتابَعة تفضل للمراقب (`Watcher`)؛ المُبلّغ بيسجّل لقطتها
  (وبيعلّم `notified_status`) لكن مايبعتش لها — عشان ما يحصلش ازدواج.
- التعطيل بوقف التسليم بس، مع استمرار تحديث اللقطات وتعليم الحالة ⇒ مفيش تراكم قديم
  يتّبع عند إعادة التفعيل.

OHB2-08-01: علامة التسليم المعلّق بقت **دائمة** في جدول `notifier_pending` (مش تلميح
in-memory). بتتكتب بعد ما تليجرام يأكّد الإرسال وقبل التسجيل الدائم، وبتفضل بعد إعادة
تشغيل العملية ⇒ الدورة الجاية تسوّيها **قبل أي إرسال** بدل ما تعيد الإرسال أعمى.

ملاحظة صريحة (مفيش exactly-once): تليجرام مابيرجّعش مفتاح idempotency لـ `sendMessage`.
فيه نافذة غامضة غير قابلة للإزالة بين ما تليجرام **يقبل** الرسالة وما نسجّل التسليم
**بشكل دائم** محليًا: لو العملية اتقطعت جوّه النافذة دي، بعد إعادة التشغيل ممكن الرسالة
تتبعت تاني (احتمال ازدواج). بنضيّق النافذة (علامة write-ahead + تسجيل ذرّي) لكن ما
بنلغيهاش، وبنفضّل استرجاع آمن وعدم يقين صريح على فقد إشعار بصمت.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from telegram.error import RetryAfter, TelegramError

from .db import NotificationState
from .errors import ApiError
from .messages import SANDBOX_ERROR, get_status, is_terminal
from .sender import send_long

log = logging.getLogger(__name__)

# أقصى عدد محاولات تسليم فاشلة متتالية لإشعار محادثة واحدة قبل الاستسلام (متخزّن في
# SQLite فمايتصفّرش بإعادة التشغيل). ما بيمنعش باقي المحادثات من الإشعار.
MAX_NOTIFY_RETRIES = 5

# سقف أمان لعدد الصفحات في دورة واحدة: يمنع حلقة لا نهائية لو الـ API رجّع مؤشرات
# فريدة بلا نهاية (النموذج كان محدود بتكرار المؤشر بس).
MAX_PAGES = 200

STATUS_MESSAGES = {
    "finished": "✅ انتهى تنفيذ المهمة في OpenHands.",
    "error": "❌ حدث خطأ أثناء تنفيذ المهمة.",
    "stuck": "⚠️ يبدو أن وكيل OpenHands عالق.",
    "waiting_for_confirmation": "⏸️ الوكيل ينتظر تأكيدك.",
    SANDBOX_ERROR: "❌ حدث خطأ في بيئة تنفيذ OpenHands.",
}
_DEFAULT_MESSAGE = "⚠️ تغيّرت حالة المحادثة."


def _retry_after_seconds(exc: RetryAfter) -> float:
    """مدة الانتظار اللي تليجرام طلبها (`retry_after`). int ثواني أو timedelta."""
    value = exc.retry_after
    if isinstance(value, timedelta):
        return max(0.0, value.total_seconds())
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0


def _parse_retry_deadline(raw: str | None) -> datetime | None:
    """يحلّل موعد إعادة محاولة دائم (UTC ISO). None لو القيمة فاضية/تالفة (fail-safe)."""
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def format_notification(conv: dict, status: str, base_url: str) -> str:
    """نص إشعار عربي واحد (خام، يتهرّب عند الإرسال)."""
    title = conv.get("title") or "محادثة بدون عنوان"
    message = STATUS_MESSAGES.get(status, _DEFAULT_MESSAGE)
    link = f"{base_url.rstrip('/')}/conversations/{conv.get('id')}"
    return f"{message}\n\nالمحادثة: {title}\nالحالة: {status}\n{link}"


class Notifier:
    def __init__(
        self,
        client,
        db,
        bot,
        chat_id: int,
        interval: int = 25,
        base_url: str = "https://app.all-hands.dev",
        page_size: int = 50,
        clock=None,
        allowed_chats=None,
    ) -> None:
        if not isinstance(interval, int) or isinstance(interval, bool) or interval <= 0:
            raise ValueError("فترة المُبلّغ لازم تكون رقم صحيح موجب")
        if not isinstance(page_size, int) or isinstance(page_size, bool) or page_size <= 0:
            raise ValueError("حجم صفحة المُبلّغ لازم يكون رقم صحيح موجب")
        # وجهات الإشعار المسموحة (محادثات خاصة للمستخدمين المسموحين). الافتراضي = owner.
        self._allowed_chats = frozenset(allowed_chats) if allowed_chats else None
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._client = client
        self._db = db
        self._bot = bot
        self._chat_id = chat_id
        self._interval = interval
        self._base_url = base_url
        self._page_size = page_size
        # OHB2-08-01: علامة التسليم المعلّق بقت **دائمة** في `db.notifier_pending`. مفيش
        # تلميح in-memory بيحمل دليل تسليم (كان بيضيع بإعادة التشغيل). الدورة الجاية
        # بتقرأ العلامة من القاعدة وتكمّل التسجيل **قبل أي إرسال**.
        #
        # OHB2-08-02R: مواعيد إعادة المحاولة بعد RetryAfter بقت **دائمة لكل محادثة** في
        # `db.notifier_retry_not_before` (UTC ISO)، مش مؤقّت in-memory. كده الموعد بيفضل
        # بعد إعادة التشغيل، و429 لمحادثة ما بيوقفش باقي المحادثات.
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    def _deadline_iso(self, delay_seconds: float) -> str:
        """موعد إعادة محاولة مطلق (UTC ISO) = ساعة المُبلّغ + المدة. يستخدم `_clock`
        القابل للحقن في الاختبارات (ساعة وهمية)."""
        return (self._clock() + timedelta(seconds=delay_seconds)).isoformat()

    def record_notification_sent(self, conversation_id: str, status: str, now: str) -> None:
        """نقطة التنسيق مع المراقب: يسجّل إشعار حالة نهائية اتّبع من المالك (المراقب).

        بتتنادى بعد تأكيد تليجرام بس، بنفس الحالة المعيارية، عشان المُبلّغ ما يعيدش
        الإشعار لو المتابعة اتشالت. **بتسيب أي استثناء قاعدة يطلع** (مش بتسكته) عشان
        المراقب يعرف إن التسجيل فشل: مايشيلش المتابعة ويحتفظ بحالة معلّقة ويعيد المحاولة.
        """
        self._db.record_notification_sent(conversation_id, status, now)

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
                log.exception("خطأ في دورة المُبلّغ")
            await asyncio.sleep(self._interval)

    # ------------------------------------------------------------------ fetch
    async def _fetch_all(self) -> list[dict]:
        """يجيب كل المحادثات بتتبّع الـ cursor بأمان.

        بيرمي ApiError لو الـ cursor اتكرّر أو الرد/العناصر شكلها غير متوقع — قبل أي
        كتابة حالة، فمايتخزّنش رد مبتور.
        """
        conversations: list[dict] = []
        page_id = None
        seen: set[str] = set()
        pages = 0
        while True:
            result = await self._client.search_conversations(limit=self._page_size, page_id=page_id)
            if not isinstance(result, dict):
                raise ApiError("رد بحث المحادثات شكله غير متوقع")
            items = result.get("items")
            if not isinstance(items, list):
                raise ApiError("رد بحث المحادثات مفيهوش عناصر")
            conversations.extend(it for it in items if isinstance(it, dict))
            next_page = result.get("next_page_id")
            if not next_page:
                break
            if next_page in seen:
                raise ApiError("تكرار في مؤشر ترقيم المحادثات")
            seen.add(next_page)
            page_id = next_page
            pages += 1
            if pages >= MAX_PAGES:
                raise ApiError("عدد صفحات ترقيم المحادثات تعدّى الحد الآمن")
        return conversations

    # ------------------------------------------------------------------- tick
    async def tick(self) -> None:
        # لقطة أول تشغيل (فاضية = مفيش أي لقطة سابقة) لتأسيس خط الأساس بدون إشعار.
        first_run = not self._db.has_notification_states()
        try:
            conversations = await self._fetch_all()
        except ApiError as exc:
            # عطل مؤقت: ما نلمسش اللقطات المخزّنة، ونعيد المحاولة الدورة الجاية.
            log.warning("تعذّر جلب المحادثات للمُبلّغ (%s)، هيتعاود", type(exc).__name__)
            return

        enabled = self._db.get_notifications_enabled()
        now = self._clock().isoformat()
        for conv in conversations:
            cid = conv.get("id")
            if not cid:
                continue
            try:
                await self._process(conv, first_run, enabled, now)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                # عزل الأخطاء: محادثة واحدة ما توقفش الدورة. نسجّل النوع بس (ممكن يحوي أسرار).
                log.error("خطأ غير متوقع في إشعار المحادثة %s (%s)", cid, type(exc).__name__)

    async def _process(self, conv: dict, first_run: bool, enabled: bool, now: str) -> None:
        cid = conv.get("id")
        status = get_status(conv)

        # OHB2-08-01: تسليم معلّق **دائم** من دورة سابقة (تليجرام أكّد بس التسجيل فشل،
        # أو استرجاع بعد إعادة تشغيل): نسوّيه (نسجّل الحالة اللي اتّبعت فعلًا ونمسح
        # العلامة) **قبل** أي قرار إرسال. لو التسجيل لسه فاشل، نستنى الدورة الجاية —
        # ما نرسلش تاني. ده اللي بيمنع الإرسال الأعمى بعد restart.
        pending = self._db.get_notifier_pending(cid)
        if pending is not None:
            try:
                self._db.reconcile_notifier_pending(cid, now)
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "تعذّر تسجيل إشعار المحادثة %s المعلّق (%s)، هنعيد المحاولة في الدورة الجاية",
                    cid, type(exc).__name__,
                )
                return

        # OHB2-08-02R: موعد إعادة المحاولة **الدائم** للمحادثة دي بعد RetryAfter. لو لسه
        # ما عدّاش، نتخطّى المحادثة دي بس (مش الدورة كلها) — 429 لمحادثة ما بيوقفش باقي
        # المحادثات. لو الموعد عدّى (أو القيمة تالفة) نمسحه ونكمّل عادي. موعد **منتهي** أو
        # غير صالح ⇒ إعادة محاولة (fail-safe)، مش فقد إشعار.
        raw_deadline = self._db.get_retry_not_before(cid)
        if raw_deadline is not None:
            deadline = _parse_retry_deadline(raw_deadline)
            if deadline is not None and self._clock() < deadline:
                return
            try:
                self._db.clear_retry_not_before(cid)
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "تعذّر مسح موعد إعادة محاولة إشعار %s (%s)، هيتخطّى",
                    cid, type(exc).__name__,
                )

        # أول تشغيل (مفيش لقطة سابقة خالص): تأسيس خط أساس بدون إشعار — حتى عن
        # المحادثات المنتهية الموجودة، عشان ما نغرقش المستخدم بإشعارات قديمة.
        if first_run:
            self._db.upsert_notification_state(
                cid, status=status, notified_status=status, retry_count=0, updated_at=now
            )
            return

        # نقرأ اللقطة الطازجة **هنا** (مش من بداية الدورة): المراقب أو أي كاتب تاني ممكن
        # يكون علّم نفس الحالة أثناء مرحلة جلب المُبلّغ. القراءة المتأخرة دي بتسدّ نافذة
        # الازدواج المؤكّدة (stale snapshot). محادثة ظهرت بعد خط الأساس ⇒ لقطة جديدة.
        snap = self._db.get_notification_state(cid) or NotificationState(cid)

        terminal = is_terminal(status)
        # انتقال مؤهّل = حالة نهائية لسه ماتعاملناش معاها (`notified_status` لسه مش
        # نفس الحالة). تكرار نفس الحالة النهائية ما بيعملش إشعار تاني.
        eligible = terminal and snap.notified_status != status
        if not eligible:
            # مفيش إشعار: نحدّث الحالة المرصودة ونعلّم إننا حاسبناها.
            self._db.upsert_notification_state(
                cid, status=status, notified_status=status, updated_at=now
            )
            return

        if not enabled or self._db.is_watched(cid):
            # تسليم مكتوم (معطّل أو ملكية المراقب): نعلّم الحالة "محسوبة" عشان إعادة
            # التفعيل أو إزالة المتابعة ما تبعتش إشعار قديم متأخر.
            self._db.upsert_notification_state(
                cid, status=status, notified_status=status, retry_count=0, updated_at=now
            )
            return

        if snap.retry_count >= MAX_NOTIFY_RETRIES:
            # استنفدنا ميزانية الإشعار: نعلّمه من غير محاولة عشان مايحجبش باقي المحادثات.
            log.warning("تخطّي إشعار المحادثة %s: استنفدنا المحاولات (%d)", cid, snap.retry_count)
            self._db.upsert_notification_state(
                cid, status=status, notified_status=status, retry_count=0, updated_at=now
            )
            return

        try:
            await send_long(self._chat_id, format_notification(conv, status, self._base_url), self._bot)
        except RetryAfter as exc:
            # OHB2-08-02R: تليجرام طلب انتظار (429). **مش** فشل دائم: ما نزوّدش عدّاد
            # المحاولات، وما نعلّمش الحالة. نسجّل موعد إعادة محاولة **دائم** (UTC) للمحادثة
            # دي بس، فالحالة تفضل مؤهّلة وباقي المحادثات ما بتتأثّرش. لو الكتابة فشلت،
            # نتخطّى بلا عدّاد (fail-safe: ممكن نحاول بدري، مش نفقد إشعار).
            delay = _retry_after_seconds(exc)
            try:
                self._db.set_retry_not_before(cid, self._deadline_iso(delay))
            except Exception as exc2:  # noqa: BLE001
                log.warning(
                    "تعذّر تسجيل موعد إعادة محاولة إشعار %s (%s)؛ هنحاول الدورة الجاية",
                    cid, type(exc2).__name__,
                )
            log.warning(
                "تليجرام طلب انتظار %.0f ثانية لإشعار المحادثة %s (429)، هنعيد بعد كده",
                delay, cid,
            )
            return
        except TelegramError as exc:
            # فشل التسليم: نحدّث الحالة المرصودة بس **من غير** ما نعلّمها "محسوبة"
            # (notified_status يفضل زي ما هو) عشان يتعاود. العدّاد مستمر ومحدود.
            count = self._db.bump_notification_retry(cid, now)
            self._db.upsert_notification_state(cid, status=status, updated_at=now)
            log.warning(
                "فشل إشعار المحادثة %s (%s)، المحاولة %d/%d",
                cid, type(exc).__name__, count, MAX_NOTIFY_RETRIES,
            )
            if count >= MAX_NOTIFY_RETRIES:
                log.warning("استسلمنا من إشعار المحادثة %s بعد %d محاولة فاشلة", cid, count)
            return

        # تليجرام أكّد النجاح. OHB2-08-01: نسجّل **علامة تسليم معلّق دائمة** الأول (بعد
        # التأكيد وقبل التسجيل الدائم). لو الكتابة نفسها فشلت، ما بنسجّلش النجاح الدائم
        # (notified_status يفضل زي ما هو) فالحالة تفضل مؤهّلة، لكن **مفيش علامة دائمة** —
        # ده يسيب نافذة إعادة إرسال عند إعادة التشغيل بالظبط، وبنعترف بيها (مفيش exactly-once).
        try:
            self._db.set_notifier_pending(cid, status, now)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "تعذّر تسجيل علامة تسليم إشعار %s (%s)؛ ممكن يتعاد الإرسال بعد إعادة تشغيل",
                cid, type(exc).__name__,
            )
            return

        # تسجيل ذرّي: ينجح أو يفشل مع بعض. لو نجح، العلامة اتمسحت واللقطة اتحدّثت ⇒ مفيش
        # إعادة إرسال. لو فشل، العلامة **تفضل** ⇒ الدورة الجاية تسوّيها (مفيش فقد دليل).
        try:
            self._db.reconcile_notifier_pending(cid, now)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "تعذّر تسجيل إشعار المحادثة %s بعد تسليم ناجح (%s)، هنعيد المحاولة قبل أي إرسال",
                cid, type(exc).__name__,
            )
