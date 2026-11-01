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
import uuid
from datetime import datetime, timedelta, timezone

from telegram.error import RetryAfter, TelegramError

from .db import (
    INBOX_CLAIM_LEASE,
    INBOX_DELIVERY_MAX_ATTEMPTS,
    INBOX_KIND_PROACTIVE,
    INBOX_KIND_TERMINAL,
    NotificationState,
)
from .errors import ApiError
from .messages import SANDBOX_ERROR, get_status, is_terminal
from .sender import send_long

log = logging.getLogger(__name__)

# أقصى عدد محاولات تسليم فاشلة متتالية لإشعار محادثة واحدة قبل الاستسلام (متخزّن في
# SQLite فمايتصفّرش بإعادة التشغيل). ما بيمنعش باقي المحادثات من الإشعار.
MAX_NOTIFY_RETRIES = 5

# OHB2-08-05 (Batch 3R-FIX2-F1): مدة صلاحية حجز الحدث (claim lease). حجز أقدم من كده
# بيتخطّى/يتحرّر (العملية اللي أخدته وقعت قبل ما تحرّره) ⇒ الحدث ما يعلقش محجوزًا للأبد.
# أطول من أي إرسال عادي (ثوانٍ) فمايسببش إرسالًا مزدوجًا عمليًا. المصدر الموحّد في `db`.
_CLAIM_LEASE = INBOX_CLAIM_LEASE

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

    def _proactive_event_key(self, conversation_id: str, status: str, seq: int) -> str:
        """مفتاح هوية الحدث الاستباقي = (المحادثة، النوع، رقم عصر الانتقال الدائم).

        OHB2-08-05 (Batch 3R-FIX2): `seq` = عصر **الاكتشاف** (من `note_transition`) — يزيد
        مرة واحدة عند اكتشاف انتقال جديد (حتى لنفس الحالة)، ويثبت خلال كل إعادات المحاولة
        لنفس الانتقال. فـ `finished→running→finished` بيدي رقمين مختلفين ⇒ حدثين منفصلين،
        وإعادة الاستطلاع/إعادة التشغيل لنفس الانتقال بتعيد نفس المفتاح ⇒ مفيش تكرار.
        """
        return f"{conversation_id}|{INBOX_KIND_PROACTIVE}|{seq}"

    def _record_inbox_event(
        self, conv: dict, conversation_id: str, status: str, seq: int
    ) -> int | None:
        """يسجّل **الحدث** الاستباقي في الصندوق (delivery_status='pending') ويرجّع معرّفه.

        بيتنادى عند لحظة اكتشاف الانتقال، **قبل** أي إرسال (event-first). idempotent بنفس
        `event_key`. معزول: أي خطأ قاعدة بيتسجّل تحذير بس، لكن بنرجّع None (مفيش ضمان ربط).

        OHB2-08-05 (Batch 3R-FIX2): بنمرّر `transition_seq=seq` كهوية الانتقال الموحّدة
        (والـ `transition_status=status` وصفية بس). لو المراقب سجّل صفًا معلّقًا لنفس الانتقال
        (نفس الرقم)، القيد الموحّد يرفض صفنا ونرجّع معرّف **نفس** الصف (عشان التسليم يعلّمه،
        مش يسجّل حدثًا منافسًا). انتقال مختلف بنفس الحالة ليه رقم مختلف ⇒ صف منفصل.
        """
        try:
            title = conv.get("title") or "محادثة بدون عنوان"
            message = format_notification(conv, status, self._base_url)
            key = self._proactive_event_key(conversation_id, status, seq)
            event_id = self._db.add_inbox_event(
                conversation_id, title, INBOX_KIND_PROACTIVE, message,
                self._clock().isoformat(), event_key=key, chat_id=self._chat_id,
                transition_status=status, transition_seq=seq,
            )
            if event_id is None:
                # `event_id=None` يعني إما (أ) نفس الـ event_key مسجّل قبل كده (إعادة
                # محاولة لنفس الحدث)، أو (ب) القيد الموحّد رفض صفًا منافسًا (نفس الانتقال
                # مسجّل من عامل تاني). نرجّع معرّف صفنا لو موجود؛ وإلا None (المستدعي بيميّز
                # المشترك عبر `find_pending_transition(seq)`).
                existing = self._db.find_inbox_by_event_key(key)
                return existing.id if existing else None
            return event_id
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "تعذّر تسجيل حدث الصندوق للمحادثة %s (%s)",
                conversation_id, type(exc).__name__,
            )
            return None

    def _record_inbox(self, conv: dict, conversation_id: str, status: str) -> None:
        """متوافق للخلف: يسجّل حدثًا استباقيًا (delivery_status='pending').

        بيُستخدم عصر الانتقال الحالي (من `note_transition`) عشان الهوية تفضل متسقة مع
        المسار الأساسي. معزول: أي خطأ بيتسجّل تحذير بس.
        """
        seq = self._db.note_transition(conversation_id, status, terminal=True, now=self._clock().isoformat())
        self._record_inbox_event(conv, conversation_id, status, seq)

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

        present = {c.get("id") for c in conversations if c.get("id")}
        # OHB2-08-05 (Batch 3R): استرجاع/إعادة محاولة أحداث الصندوق الاستباقية المعلّقة اللي
        # محادثاتها **اختفت من البحث** (المسار العادي مش هيعالجها) — مش اللي لسه ظاهرة
        # (دي مملوكة لـ `_process` وبتتعاد محاولتها هناك، فإعادة المحاولة هنا هتكرّر الإرسال).
        await self._recover_pending_events(exclude_cids=present)
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

    async def _recover_pending_events(self, *, exclude_cids: set[str] | None = None) -> None:
        """يعيد محاولة أحداث الصندوق المعلّقة (event-first recovery).

        بيسترجع الأحداث الاستباقية (`proactive`) وأحداث الانتقال النهائي (`terminal`)، مع
        استثناء المحادثات اللي عليها علامة تسليم معلّق (`notifier_pending` — مملوكة للمسار
        العادي)، والمحادثات الموجودة في `exclude_cids` (ظاهرة في البحث الحالي ⇒ `_process`
        هيعالجها؛ إعادة المحاولة هنا هتكرّر الإرسال).

        OHB2-08-05 (Batch 3R-FIX2-F1): كمان بيسترجع الحدث **الكانوني الحالي** (`transition_seq
        == notification_state.transition_seq`) لمحادثة **متابَعة عالقة** (المسار النشط للمراقب
        مش هيعيد المحاولة) — `_watched_event_stuck`. الأحداث غير المتابَعة (بأي نوع) بيفضل
        يتولّاها استرجاع المراقب، فمافيش ازدواج.
        """
        now = self._clock().isoformat()
        claim_cutoff = (self._clock() - _CLAIM_LEASE).isoformat()
        try:
            due = self._db.list_due_pending_inbox(
                now,
                kinds=(INBOX_KIND_PROACTIVE,),
                exclude_watched=False,
                unclaimed=True,
                claim_cutoff=claim_cutoff,
            )
            due += self._db.list_due_pending_inbox(
                now,
                kinds=(INBOX_KIND_TERMINAL,),
                exclude_watched=False,
                unclaimed=True,
                claim_cutoff=claim_cutoff,
            )
            in_flight = self._db.list_notifier_pending()
        except Exception as exc:  # noqa: BLE001
            log.warning("تعذّر جلب أحداث الصندوق المعلّقة (%s)", type(exc).__name__)
            return
        seen: set[int] = set()
        for item in due:
            if item.id in seen:
                continue
            seen.add(item.id)
            if item.conversation_id in in_flight:
                continue
            if self._watched_event_stuck(item):
                # F-1: الحدث الكانوني الحالي لمحادثة متابَعة عالقة ⇒ إحنا مالكينه (نكمّل).
                pass
            elif item.kind == INBOX_KIND_TERMINAL:
                # حدث انتقال نهائي مش عالق-متابَعة ⇒ مسار المراقب مالكه (نشط أو استرجاعه).
                continue
            elif exclude_cids is not None and item.conversation_id in exclude_cids:
                # OHB2-08-05 (Batch 3R-FIX2): المحادثة ظاهرة في البحث الحالي ⇒ `_process`
                # هيعالج **الانتقال الحالي** (أحدث عصر). نتخطّى الحدث اللي هو نفس الانتقال
                # الحالي (عشان ما نبعتهوش مرتين)، لكن **نوصّل** أي حدث قديم اتجاوزه انتقال
                # أحدث (superseded) — عشان إشعار انتقال حقيقي مايتفقدش لما يبقى معلّقًا
                # والانتقال الأحدث عدّاه (السبب الجذري اللي المراجعة لقيته).
                state = self._db.get_notification_state(item.conversation_id)
                current_seq = state.transition_seq if state is not None else None
                if item.transition_seq is None or item.transition_seq == current_seq:
                    continue
            if item.delivery_attempts >= INBOX_DELIVERY_MAX_ATTEMPTS:
                # OHB2-08-05 (Batch 3R-FIX): استنفدنا ميزانية الحدث (بدون RetryAfter) —
                # نعلّمه `failed` بشكل صريح بدل تركه معلّقًا للأبد. الحدث **بيفضل** ظاهرًا.
                try:
                    self._db.mark_inbox_failed(item.id, self._clock().isoformat())
                except Exception as exc:  # noqa: BLE001
                    log.warning(
                        "تعذّر تصنيف الحدث %s فاشلًا (%s)", item.id, type(exc).__name__
                    )
                continue
            try:
                await self._deliver_pending_event(item)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                log.error(
                    "خطأ في استرجاع حدث الصندوق %s (%s)", item.id, type(exc).__name__
                )

    def _watched_event_stuck(self, item) -> bool:
        """F-1: هل الحدث المعلّق ده هو الحدث **الكانوني الحالي** لمحادثة متابَعة **عالقة**؟

        المتابعة العالقة = `watched.last_state` **نهائي** (المسار النشط للمراقب
        `is_terminal(state) and not is_terminal(w.last_state)` بقى False، فمابيرجعش يحاول
        تاني ⇒ الحدث يفضل معلّق للأبد لحد ما المتابعة تتشال). في الحالة دي بنتولّى الاسترجاع
        هنا. لو `last_state` لسه **غير نهائي**، المسار النشط للمراقب هيعيد المحاولة (ويوصّل
        أو يشيل المتابعة بعد الاستنفاد ⇒ المُبلّل يسترجع وقتها) ⇒ **مش بتاعنا** (نتفادى
        الازدواج مع المسار النشط).

        كمان: العصر **الحالي** (`transition_seq == notification_state.transition_seq`) بتاعنا
        دايمًا. OHB2-08-05 (Batch 3R-FIX2-N2): بنتولّى كمان الانتقال النهائي **المتجاوز**
        (superseded) لمتابعة عالقة لو هو أعلى عصر معلّق ومافيش صف معلّق بعصر أحدث — عشان
        ما يعلقش للأبد (كان مسار المراقب بيتخطّاه والمراقب `exclude_watched=True`).

        شرط أخير: المتابعة موجودة (`get_watched` مش None) — حدث لمحادثة غير متابَعة
        بيتولّاه استرجاع المراقب (بلا استثناء المتابَعة) ⇒ **مش** بتاعنا.
        """
        w = self._db.get_watched(item.conversation_id)
        if w is None:
            return False
        if not is_terminal(w.last_state):
            return False
        if item.transition_seq is None:
            return False
        state = self._db.get_notification_state(item.conversation_id)
        current_seq = state.transition_seq if state is not None else None
        if item.transition_seq == current_seq:
            # العصر الحالي ⇒ بتاعنا دايمًا (F-1).
            return True
        # OHB2-08-05 (Batch 3R-FIX2-N2): انتقال نهائي **متجاوز** (superseded) لمتابعة عالقة.
        # كان بيتخطّى (نوع terminal ⇒ مسار المراقب) والمراقب ما بيسترجعش المتابَعة ⇒ يعلق
        # للأبد. بنتولّاه لو هو أعلى عصر معلّق (الهوية الكانونية دلوقتي) ومافيش صف معلّق
        # بعصر أحدث — الشرط الأخير بيمنع ترتيبًا معكوسًا لو الأحدث لسه مااتسجّلش.
        if item.kind != INBOX_KIND_TERMINAL:
            return False
        if current_seq is None or current_seq <= item.transition_seq:
            return False
        latest = self._db.find_latest_pending_transition(item.conversation_id)
        return latest is not None and latest.transition_seq == item.transition_seq

    async def _deliver_pending_event(self, item) -> None:
        """يبعت حدثًا معلّقًا (استرجاع) ويحدّث حالته. الحدث **بيفضل موجود** دايمًا.

        OHB2-08-05 (Batch 3R-FIX2-F1): بيحجز الصف **ذرّيًا** قبل الإرسال (claim lease)،
        فلو العاملين حاولوا نفس الحدث معًا واحد بس يبعت (التاني بيشوف الحجز ويسيب). الحجز
        بيتشال في `record_inbox_attempt`/`mark_inbox_delivered`/`set_inbox_retry_deadline`.
        """
        claim = uuid.uuid4().hex
        now = self._clock().isoformat()
        cutoff = (self._clock() - _CLAIM_LEASE).isoformat()
        if not self._db.claim_pending_inbox(item.id, claim, now, cutoff=cutoff):
            return  # عامل تاني حجزه/سلّمه لحظة كده ⇒ ما نرسلش
        dest = item.chat_id if item.chat_id is not None else self._chat_id
        if self._allowed_chats is not None and dest not in self._allowed_chats:
            dest = self._chat_id
        try:
            await send_long(dest, item.message, self._bot)
        except RetryAfter as exc:
            self._db.set_inbox_retry_deadline(
                item.id, self._deadline_iso(_retry_after_seconds(exc))
            )
            return
        except TelegramError as exc:
            exhausted = (item.delivery_attempts + 1) >= INBOX_DELIVERY_MAX_ATTEMPTS
            self._db.record_inbox_attempt(
                item.id, now, error=type(exc).__name__, mark_failed=exhausted
            )
            return
        except Exception:
            # فشل غير متوقّع قبل التسجيل: نحرّر الحجز عشان الحدث مايتعلّقش محجوز للأبد.
            self._db.clear_inbox_claim(item.id, claim)
            raise
        self._db.mark_inbox_delivered(item.id, now)
        # OHB2-08-05 (Batch 3R-FIX): لو الحدث المسترجَع ممثّل للانتقال **الحالي** للحالة
        # (`transition_status`)، نسجّل الانتقال "مُبلّغ" عشان المُبلّل مايعيدش إرسال نفس
        # الانتقال الاستباقي لاحقًا (مصدر الازدواج في H-1). معزول: أي خطأ هنا ما يبطّلش
        # التسليم (الحدث اتعلّم delivered بالفعل).
        # Batch 3R-FIX2: ننسّق بس لو الحدث هو **العصر الحالي** — حدث قديم اتجاوزه انتقال
        # أحدث (superseded) مايدوسش على `notified_status` الحالي (ده كان ممكن يسبّب ازدواج
        # للانتقال الحالي).
        state = self._db.get_notification_state(item.conversation_id)
        current_seq = state.transition_seq if state is not None else None
        if (
            item.transition_status
            and item.transition_seq is not None
            and item.transition_seq == current_seq
        ):
            try:
                self._db.record_notification_sent(
                    item.conversation_id, item.transition_status, now
                )
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "تعذّر تسجيل انتقال %s مُبلّغ بعد الاسترجاع (%s)",
                    item.conversation_id, type(exc).__name__,
                )

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
        # OHB2-08-05 (Batch 3R-FIX2): نسجّل **عصر الاكتشاف** (idempotent) — يثبت خلال كل
        # إعادات المحاولة لنفس الانتقال، ويزيد مرة واحدة لكل انتقال جديد (حتى بنفس الحالة
        # بعد رجوع غير نهائي). ده الهوية الموحّدة بين المراقب والمُبلّل، ومصدر قيد التفرّد.
        seq = self._db.note_transition(cid, status, terminal=terminal, now=now)
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
            # التفعيل أو إزالة المتابعة ما تبعتش إشعار قديم متأخر. (مفيش حدث في الصندوق.)
            self._db.upsert_notification_state(
                cid, status=status, notified_status=status, retry_count=0, updated_at=now
            )
            return

        # حدث أولًا (event-first): نسجّل الحدث قبل أي إرسال عشان مايتفقدش لو تليجرام فشل.
        # الهوية = رقم عصر الانتقال (`seq`)، والوصف = `status`.
        event_id = self._record_inbox_event(conv, cid, status, seq)

        # OHB2-08-05 (Batch 3R-FIX2): لو `_record_inbox_event` رجّعت None، فيه صف انتقال
        # معلّق **مشترك** بنفس الهوية (نفس عصر الانتقال) سجّله العامل التاني. ساعتها إحنا
        # **مش** مالكين الحدث: ما نبعتش (التاني هيسترجعه ويبعت مرة واحدة) وما نعلّمش الحالة
        # محسوبة (عشان ما نحجبش إشعار انتقال حقيقي). انتقال مختلف بنفس الحالة ليه رقم مختلف
        # ⇒ مش مشترك (مايتحجبش).
        shared = self._db.find_pending_transition(cid, seq) if event_id is None else None
        if shared is not None:
            log.info(
                "المحادثة %s: انتقال %s (عصر %d) مسجّل بالفعل من عامل تاني (حدث %d)؛ المُبلّل هيتخطّى",
                cid, status, seq, shared.id,
            )
            return

        if snap.retry_count >= MAX_NOTIFY_RETRIES:
            # استنفدنا ميزانية الإشعار: نعلّم الحدث `failed` (باقي ظاهر للمستخدم) بدل ما
            # يفضل معلّق للأبد، ونسجّل الحالة محسوبة عشان مايحجبش باقي المحادثات.
            log.warning("تخطّي إشعار المحادثة %s: استنفدنا المحاولات (%d)", cid, snap.retry_count)
            if event_id is not None:
                self._db.record_inbox_attempt(
                    event_id, now, error="retry_exhausted", mark_failed=True
                )
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
            if event_id is not None:
                self._db.set_inbox_retry_deadline(event_id, self._deadline_iso(delay))
            log.warning(
                "تليجرام طلب انتظار %.0f ثانية لإشعار المحادثة %s (429)، هنعيد بعد كده",
                delay, cid,
            )
            return
        except TelegramError as exc:
            # فشل التسليم: نحدّث الحالة المرصودة بس **من غير** ما نعلّمها "محسوبة"
            # (notified_status يفضل زي ما هو) عشان يتعاود. العدّاد مستمر ومحدود.
            count = self._db.bump_notification_retry(cid, now)
            if event_id is not None:
                self._db.record_inbox_attempt(event_id, now, error=type(exc).__name__)
            self._db.upsert_notification_state(cid, status=status, updated_at=now)
            log.warning(
                "فشل إشعار المحادثة %s (%s)، المحاولة %d/%d",
                cid, type(exc).__name__, count, MAX_NOTIFY_RETRIES,
            )
            if count >= MAX_NOTIFY_RETRIES:
                log.warning("استسلمنا من إشعار المحادثة %s بعد %d محاولة فاشلة", cid, count)
            return

        # تليجرام أكّد النجاح. OHB2-08-01: نسجّل **علامة تسليم معلّق دائمة** الأول (بعد
        # التأكيد وقبل التسجيل الدائم)، مربوطة بحدث الصندوق وهوية الانتقال (Batch 3R).
        # لو الكتابة نفسها فشلت، ما بنسجّلش النجاح الدائم (notified_status يفضل زي ما هو)
        # فالحالة تفضل مؤهّلة، لكن **مفيش علامة دائمة** — نافذة إعادة إرسال معترف بيها
        # (مفيش exactly-once). الحدث يفضل `pending` وبيتعاود بالاسترجاع.
        try:
            self._db.set_notifier_pending(
                cid, status, now, event_id=event_id, transition_seq=seq
            )
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "تعذّر تسجيل علامة تسليم إشعار %s (%s)؛ ممكن يتعاد الإرسال بعد إعادة تشغيل",
                cid, type(exc).__name__,
            )
            return

        # تسجيل ذرّي: ينجح أو يفشل مع بعض. لو نجح، العلامة اتمسحت واللقطة اتحدّثت والحدث
        # اتعلّم `delivered` والعدّاد اترقّى ⇒ مفيش إعادة إرسال. لو فشل، العلامة **تفضل**.
        try:
            self._db.reconcile_notifier_pending(cid, now)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "تعذّر تسجيل إشعار المحادثة %s بعد تسليم ناجح (%s)، هنعيد المحاولة قبل أي إرسال",
                cid, type(exc).__name__,
            )
