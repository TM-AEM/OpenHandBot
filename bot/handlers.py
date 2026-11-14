"""أوامر تيليجرام وأزرارها. كل الرسايل عربي، والمستخدم المالك بس يترد عليه."""
from __future__ import annotations

import asyncio
import io
import logging
import sqlite3
import time
from datetime import datetime, timezone

from telegram import InputFile, Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationHandlerStop, ContextTypes

from . import keyboards as kb
from . import outbox
from . import deletion
from . import update_outcomes
from .attachment_text import validate_accompanying_text
# OHB2-SW03: سياسة إعادة المحاولة **المشتركة** معرّفة في طبقة القاعدة (مصدر واحد)، وبنعيد
# تصديرها بأسماء الوحدة دي عشان التوافق الخلفي مع الاستدعاءات/الاختبارات القائمة.
from .db import (
    DEDUPE_RETRY_DELAYS as _DEDUPE_RETRY_DELAYS,
    AttachmentRoutingState,
    is_transient_sqlite_error as _is_transient_sqlite_error,
)
from .errors import ApiError, OperationalApiFailure, ResponseTooLargeError, error_text
from .file_cache import FileCache
from .openhands_client import collect_conversations
from .files import (
    CONVERSATION_ERRORS,
    FileService,
    FileStatus,
    authorize_conversation_detailed,
    file_status_message,
)
from .messages import escape_html, format_conversation_view, format_cost, pr_url, state_label
from .sender import TextDocumentTooLargeError, send_copyable, send_long, send_text_document

log = logging.getLogger(__name__)

PAGE_SIZE = 10
REPOS_PAGE_SIZE = 8
FILES_PAGE_SIZE = 10
# TASK 55 (المرحلة B/C): كاش قصير للتبادل الأخير (copy/full) وكاش قايمة الشاتات.
# الرام محدود (308MB على Katabump) فبنحدّ عدد المداخل.
EXCHANGE_TTL = 45.0
EXCHANGE_CACHE_MAX = 20
LIST_TTL = 45.0


def _allowed(update: Update, config) -> bool:
    """مستخدم مسموح *و* في محادثة خاصة. صلاحية المستخدم ما تعنيش صلاحية أي جروب."""
    user = update.effective_user
    if not (user and config.is_allowed(user.id)):
        return False
    chat = getattr(update, "effective_chat", None)
    return chat is not None and getattr(chat, "type", None) == "private"


class _MessageAdapter:
    """يخلي Message يبان زي CallbackQuery بالنسبة لـ edit_message_text."""

    def __init__(self, message) -> None:
        self._message = message

    async def edit_message_text(self, text: str, **kwargs) -> None:
        await self._message.edit_text(text, **kwargs)


async def _safe_edit(query, text: str, **kwargs) -> bool:
    """يرجّع True لو اتعدّلت الرسالة، وFalse لو مفيش تغيير (زر تحديث)."""
    try:
        await query.edit_message_text(text, **kwargs)
        return True
    except Exception as exc:  # noqa: BLE001
        if "not modified" not in str(exc).lower():
            raise
        return False


async def _edit_or_send(query, text: str, chat_id: int, bot, **kwargs) -> bool:
    """يعدّل الرسالة الحالية؛ ولو طويلة عليها يبعتها مقسّمة من جديد.

    بيرجّع True لو اتعرض العرض فعلاً (اتعدّلت الرسالة أو اتبعتت من جديد)، وFalse لو
    فشل العرض (خطأ تيليجرام زي رسالة قديمة/مش قابلة للتعديل، أو فشل الإرسال البديل عند
    الطول). الفشل بيتسجّل بنوعه بس (من غير نص الاستثناء، ممكن يحتوي أسرار) عشان ما يتخفيش
    — بس ما يوقّفش معالج الـ callback (مفيش استثناء بيطلع للمستدعي). اللي بينده لازم ياخد
    باله من القيمة الراجعة قبل أي تغيير في الحالة.
    """
    try:
        await query.edit_message_text(escape_html(text), parse_mode=ParseMode.HTML, **kwargs)
        return True
    except Exception as exc:  # noqa: BLE001
        message = str(exc).lower()
        if "not modified" in message:
            return True  # العرض نفسه موجود بالفعل — مش فشل
        if "too long" in message:
            try:
                await send_long(chat_id, text, bot)
                return True
            except Exception as send_exc:  # noqa: BLE001 — فشل الإرسال البديل = فشل عرض
                log.warning("فشل إرسال العرض البديل (%s)", type(send_exc).__name__)
                return False
        log.warning("فشل عرض الشات (%s)", type(exc).__name__)
        return False


def _file_cache(context: ContextTypes.DEFAULT_TYPE) -> FileCache:
    """ذاكرة الملفات المؤقتة المحدودة (LRU) من bot_data (بتتعمل مرة واحدة)."""
    return context.bot_data.setdefault("file_cache", FileCache())


def _identity_cache(context: ContextTypes.DEFAULT_TYPE):
    """كاش هوية المالك المشترك على مستوى البوت (OHB2-09-A2-04).

    مربوط بالعميل المشترك الواحد (`bot_data["client"]`) عشان `/users/me` يتنادى مرة
    واحدة عبر كل مسارات الشات في البوت. الكاش مقيّد بالعميل: لو العميل اتغيّر (بناء
    جديد) بنعمل كاش جديد، فما يتسرّبش بين اعتمادين/جلسات.
    """
    from .files import IdentityCache

    client = context.bot_data["client"]
    entry = context.bot_data.get("identity_cache")
    if entry is not None and entry[0] is client:
        return entry[1]
    cache = IdentityCache(client)
    context.bot_data["identity_cache"] = (client, cache)
    return cache


def _files_service(context: ContextTypes.DEFAULT_TYPE) -> FileService:
    """`FileService` فوق نفس العميل المشترك وكاش الهوية المشترك (مفيش عميل تاني).

    F-1: بنمرّر قاعدة بيانات البوت كمان عشان `FileService.authorize` يفرض شاهد الحذف
    قبل أي قراءة ملفات (نفس الحماية اللي بيمرّ بيها مسار البوت).
    """
    return FileService(
        context.bot_data["client"],
        identity=_identity_cache(context),
        db=context.bot_data.get("db"),
    )


def _is_expected_upstream_rejection(exc: ApiError | None) -> bool:
    """OHB2-SW-07: هل `UPSTREAM_ERROR` ده **رفض 4xx متوقّع** (لا ينتشر)؟

    `authorize_conversation_detailed` بترجّع `UPSTREAM_ERROR` عند أي `ApiError` من
    `get_conversations` أو `/users/me`. لازم نفرّق:

    - **4xx متوقّع** (401/403/404/409/410/422): نتيجة مستخدم متوقّعة (مفتاح غلط/غير
      مصرّح/مورد مش موجود) ⇒ **رجوع عادي** بعد الرسالة. ده يحفظ تمييز 403/404 ويمنع
      تحويل الرفض المصرّح لفشل عابر.
    - **5xx / 429 / بلا `status_code`** (مهلة/انقطاع): فشل تشغيلي ⇒ **ينتشر**.

    لما مفيش استثناء أصلي (مسار الرفض المشتقّ زي `DELETED`) ⇒ رفض متوقّع (مفيش رفع).
    """
    return exc is None or outbox.is_permanent(exc)


async def _authorized_conversation_status(
    client, context: ContextTypes.DEFAULT_TYPE, conversation_id: str, *, allow_deleted: bool = False
):
    """زي `_authorized_conversation` لكن بترجّع **الحالة والاستثناء الأصلي**:
    `(conv | None, status, message, exc | None)`.

    OHB2-SW-07: المسارات المعنية بانتشار الفشل التشغيلي (فتح/نسخ/رد كامل) محتاجة تفرّق
    بين `UPSTREAM_ERROR` **التشغيلي** (5xx/429/بلا كود ⇒ ينتشر بعد العرض) و`UPSTREAM_ERROR`
    **المتوقّع** (4xx: 401/403/404 ⇒ رجوع عادي)، والرفض المشتقّ (`NOT_FOUND`/`DELETED`/
    `UNAUTHORIZED` ⇒ رجوع عادي). `_authorized_conversation` (الغلاف) بتفضل ترجّع
    `(conv, message)` زي ما هي عشان باقي المستدعين مايتغيّروش.
    """
    conv, status, error, exc = await authorize_conversation_detailed(
        client, _identity_cache(context), conversation_id, context.bot_data.get("db"),
        allow_deleted=allow_deleted,
    )
    if conv is not None:
        return conv, FileStatus.OK, None, None
    if status is FileStatus.UPSTREAM_ERROR:
        # رسالة الخطأ المتنقّحة لو موجودة (مسار `get_conversations`)، وإلا الرسالة
        # الافتراضية (مسار الهوية `/users/me` اللي بيرجّع None). في الحالتين الاستثناء
        # الأصلي بيتنقل عشان التصنيف 4xx/تشغيلي (OHB2-SW-07).
        message = error or CONVERSATION_ERRORS[FileStatus.UPSTREAM_ERROR][2]
        return None, status, message, exc
    _code, _http, message = CONVERSATION_ERRORS.get(
        status, ("upstream_error", 502, "تعذّر الوصول للشات دلوقتي، جرّب تاني.")
    )
    return None, status, message, None


async def _authorized_conversation(
    client, context: ContextTypes.DEFAULT_TYPE, conversation_id: str, *, allow_deleted: bool = False
):
    """يفوّض شات عبر **نفس** تنفيذ `FileService` (ملكية/معرّف/فشل مغلق).

    يرجّع `(conv | None, message)`؛ لو `conv` فاضي فـ `message` رسالة عربي آمنة. عند
    فشل upstream (429/503/مهلة/انقطاع) بنعرض رسالة الخطأ المتنقّحة (زي مسار البوت
    القديم)، ولسه **مفيش أي جلب بيانات محمية** غير الميتاداتا المتفوَّض عليها.

    F-1: بنمرّر قاعدة بيانات البوت (`bot_data["db"]`) عشان فرض شاهد الحذف يحصل **قبل**
    أي نداء بعيد — أي مسار بيمرّ من هنا (فتح/حالة/تكلفة/رد/تصدير/ملفات/متابعة/حذف)
    يرفض الشات المتشاهد برسالة «مش موجود» من غير أي كشف. `allow_deleted=True` استثناء
    مقصود لعمليتي watch/حذف بس (زي طبقة الـ Mini App).
    """
    conv, _status, message, _exc = await _authorized_conversation_status(
        client, context, conversation_id, allow_deleted=allow_deleted
    )
    return conv, message


def _store_exchange(context, conversation_id, user_text, reply):
    """يخزّن آخر تبادل (برومت مستخدم + رد agent) لكاش قصير، ويحافظ على الحد الأقصى."""
    cache = context.bot_data.setdefault("exchange_cache", {})
    cache[conversation_id] = (time.monotonic(), user_text, reply)
    while len(cache) > EXCHANGE_CACHE_MAX:
        cache.pop(next(iter(cache)))  # الأقدم أولاً (ترتيب الإدخال)


async def _get_exchange(context, conversation_id):
    """آخر تبادل من الكاش لو لسه طازة، وإلا من الـ API (وبيخزّنه).

    الكاش بيخدم أزرار copy/full بس — فتح الشات (open) بيقرا طازة دايماً.
    """
    cache = context.bot_data.setdefault("exchange_cache", {})
    hit = cache.get(conversation_id)
    if hit and time.monotonic() - hit[0] < EXCHANGE_TTL:
        return hit[1], hit[2]
    user_text, reply = await context.bot_data["client"].get_last_exchange(conversation_id)
    _store_exchange(context, conversation_id, user_text, reply)
    return user_text, reply


async def _guard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    cfg = context.bot_data["config"]
    if not _allowed(update, cfg):
        chat = getattr(update, "effective_chat", None)
        log.info(
            "تجاهل تحديث غير مسموح (مستخدم=%s، نوع الشات=%s)",
            update.effective_user and update.effective_user.id,
            getattr(chat, "type", None),
        )
        # OHB2-MANUAL-POLLING-HANDLER-OUTCOME: رفض تفويض مقصود ⇒ نتيجة صريحة
        # `explicitly_ignored` (مفيش إعادة معالجة لاحقة). سلوك التفويض ما بيتغيّرش.
        _authorization_ignored(update, context)
        return False
    return True


# OHB2-DUPLICATE-TELEGRAM-PROMPT-DISPATCH: سقف نافذة الاحتفاظ بمعرّفات التحديثات المعالَجة.
# ضخم عمدًا (مش «آخر N ثانية» زمني) عشان منعرّضش إعادة تسليم قديمة لمعالجة تانية، وفي
# نفس الوقت السجل مايكبرش بلا حدود (تقليم دوري عند الإقلاع بس — مفيش جدولة جديدة).
PROCESSED_UPDATES_KEEP = 50_000

# OHB2-TRANSIENT-DB-FAILURE: ميزانية إعادة محاولة **محدودة** لفشل SQLite **عابر** بس
# (busy/locked)، عند فحص حاجز التحديث. الميزانية صغيرة عمدًا: الحاجز مسار ساخن (كل تحديث)،
# والانتظار بيأخّر كل التحديثات التانية (المعالجة تسلسلية). `busy_timeout=5000` في القاعدة
# بيغطّي معظم حالات القفل، فالمحاولات دي احتياطية لحالات نادرة. مجموع الانتظار ≈ 0.25+0.5+1
# = 1.75 ثانية كحد أقصى، وبعدها **فشل مقفول** (زي السلوك الأصلي). ملاحظة: في وضع WAL القراءة
# مش بتتحاصر بالكتّاب، فالفشل العابر الحقيقي ضيّق جدًا؛ الفشل الدائم (قاعدة تالفة/مقفولة) **مش**
# هيتعاد، فبيرجع فشل مقفول فورًا.
# OHB2-SW03: `_DEDUPE_RETRY_DELAYS` و`_is_transient_sqlite_error` بقت مستوردة من `bot/db.py`
# (سياسة واحدة مشتركة مع الـ Mini App). التصدير باسم الوحدة دي محفوظ للتوافق الخلفي.


async def _check_update_processed_with_retry(db, update_id: int) -> bool:
    """يفحص «معالَج» مع إعادة محاولة **محدودة** للفشل العابر بس.

    ده **مش** ضمان no-loss: بعد استنفاد الميزانية (أو عند فشل دائم) بنرفع الاستثناء عشان
    المتصل يفشل **مقفول** (نفس السلوك الأصلي). القيمة المضافة: نافذة فشل عابر ضيّقة جدًا
    بتتغطّى بمحاولات قصيرة بدل ما تتسبّب في إسقاط تحديث فورًا.
    """
    delay = 0.0
    attempt = 0
    while True:
        try:
            return db.update_is_processed(update_id)
        except Exception as exc:  # noqa: BLE001 — التصنيف بيقرّر: عابر يُعاد، دائم يُرفع
            if not _is_transient_sqlite_error(exc) or attempt >= len(_DEDUPE_RETRY_DELAYS):
                raise
            delay = _DEDUPE_RETRY_DELAYS[attempt]
            attempt += 1
            log.warning(
                "حاجز التحديث (%s): فشل SQLite عابر (%s) — إعادة محاولة %d/%d بعد %.2fث",
                update_id, type(exc).__name__, attempt, len(_DEDUPE_RETRY_DELAYS), delay,
            )
            await asyncio.sleep(delay)


async def _is_deleted_with_retry(db, conversation_id: str) -> bool:
    """يقرأ شاهد الحذف مع إعادة محاولة **محدودة** للفشل العابر بس (SW-01).

    نفس سياسة `_check_update_processed_with_retry`: الفشل العابر (SQLite BUSY/LOCKED)
    بيتغطّى بمحاولات قصيرة (`_DEDUPE_RETRY_DELAYS`)، وبعد استنفاد الميزانية (أو عند فشل
    دائم) **بنرفع الاستثناء الأصلي**. ممنوع نرجّع `False` عند الفشل (ده كان بيحوّل الفشل
    إلى «متشاهد» ويولّد رسالة حذف كاذبة)؛ وممنوع نرجّع `True` كمان. القراءة الناجحة بس هي
    اللي بتحدّد «متشاهد» من «مش متشاهد».
    """
    delay = 0.0
    attempt = 0
    while True:
        try:
            return db.is_deleted(conversation_id)
        except Exception as exc:  # noqa: BLE001 — التصنيف بيقرّر: عابر يُعاد، دائم يُرفع
            if not _is_transient_sqlite_error(exc) or attempt >= len(_DEDUPE_RETRY_DELAYS):
                raise
            delay = _DEDUPE_RETRY_DELAYS[attempt]
            attempt += 1
            log.warning(
                "فحص شاهد الحذف (%s): فشل SQLite عابر (%s) — إعادة محاولة %d/%d بعد %.2fث",
                conversation_id, type(exc).__name__, attempt, len(_DEDUPE_RETRY_DELAYS), delay,
            )
            await asyncio.sleep(delay)


async def _remove_watched_with_retry(remover, conversation_id: str) -> None:
    """يُزيل متابعة الشات مع إعادة محاولة **محدودة** للفشل العابر بس (OHB2-SW-06).

    `remover` = `watcher.unwatch` (لو المراقب متاح) أو `db.remove_watched` — الاتنين
    معاملة `BEGIN IMMEDIATE` ذرّية بتكمّل أي تسليم معلّق ثم تحذف، والاتنين **idempotent**
    (الحذف المكرّر no-op) فإعادة المحاولة آمنة (مفيش ازدواج أثر خارجي: ما بتلمسش تليجرام).

    نفس سياسة `_is_deleted_with_retry`/`_check_update_processed_with_retry`: الفشل العابر
    (SQLite BUSY/LOCKED) بيتغطّى بمحاولات قصيرة (`_DEDUPE_RETRY_DELAYS` 0.25/0.5/1.0ث)،
    وبعد استنفاد الميزانية (أو عند فشل دائم زي I/O/قاعدة تالفة) **بنرفع الاستثناء الأصلي**
    (بـ traceback) بدل ما نبلعه. `asyncio.CancelledError` (BaseException) مايتـcaughtش هنا
    خالص ⇒ الإلغاء ينتشر زي ما هو.
    """
    attempt = 0
    while True:
        try:
            remover(conversation_id)
            return
        except Exception as exc:  # noqa: BLE001 — التصنيف بيقرّر: عابر يُعاد، دائم يُرفع
            if not _is_transient_sqlite_error(exc) or attempt >= len(_DEDUPE_RETRY_DELAYS):
                raise
            delay = _DEDUPE_RETRY_DELAYS[attempt]
            attempt += 1
            log.warning(
                "إلغاء متابعة الشات (%s): فشل SQLite عابر (%s) — إعادة محاولة %d/%d بعد %.2fث",
                conversation_id, type(exc).__name__, attempt, len(_DEDUPE_RETRY_DELAYS), delay,
            )
            await asyncio.sleep(delay)


def _is_operational_api_failure(exc: ApiError) -> bool:
    """OHB2-SW-07: هل الـ `ApiError` فشل upstream **حقيقي** لازم ينتشر بعد عرضه؟

    التصنيف (مصدر واحد: `outbox.is_permanent` — نفس عقد صندوق الصادر، بلا تكرار):

    - **4xx متوقّع** (404 مش موجود / 403 ممنوع / 410 اتمسح / 409 تعارض / 422 طلب غلط):
      نتيجة **مستخدم متوقّعة** ⇒ مفيش رفع (ترجع عاديًّا بعد الرسالة). ده اللي يحفظ
      تمييز 403/404/410 وما يحوّلش الرفض المصرّح أو المورد المحذوف لفشل عابر.
    - **5xx** (500/502/503/504): عطل خدمة upstream ⇒ **فشل تشغيلي** ⇒ ينتشر.
    - **429**: rate limit ⇒ **عابر** (`is_permanent` بيستثنيه) ⇒ ينتشر.
    - **بلا `status_code`** (مهلة/انقطاع اتصال/نتيجة غامضة): عابر ⇒ ينتشر.

    كده الفشل التشغيلي مايتحوّلش لـ «إتمام معالجة ناجح»، والمستخدم لسه شايف نفس الرسالة
    المتنقّحة قبل الرفع.
    """
    return not outbox.is_permanent(exc)


async def _raise_if_operational_api_failure(exc: ApiError) -> None:
    """يعرض رسالة الخطأ المتنقّحة (زي القديم) ثم **يرفع** لو الفشل تشغيلي (SW-07).

    الفشل المتوقّع (4xx) بيرجع عاديًّا (سلوك قديم محفوظ). الفشل التشغيلي بيُرفع كنوع
    `OperationalApiFailure` يحمل **نفس** الرسالة والكود ⇒ `error_text()` تفضل متسقة،
    ومعالج الأخطاء يقدر يرصده بدل ما يختفي. `asyncio.CancelledError` (BaseException)
    مايتـcaughtش هنا خالص ⇒ مفيش كتم إلغاء.
    """
    if _is_operational_api_failure(exc):
        raise OperationalApiFailure(error_text(exc), getattr(exc, "status_code", None))


async def dedupe_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """حاجز الإدخال: يضمن «تحديث تيليجرام واحد ⇒ قرار معالجة واحد» (OHB2-DUP-DISPATCH).

    مسجّل في **مجموعة أعلى أولوية** (group=-1) عشان يشتغل قبل كل الـ handlers التانية،
    ولأن PTB بينفّذ handler واحد بس لكل مجموعة، ده أول و آخر handler في المجموعة دي.

    السلوك:
    - تحديث من غير `update_id` صالح (مش Update حقيقي) ⇒ نتخطّى (ما بنمنعش أي حاجة).
    - `update_id` شُفناه قبل كده (مسجّل «معالَج») ⇒ **تحديث مكرّر** ⇒ نوقف المعالجة تمامًا
      (`ApplicationHandlerStop`) قبل أي عملية خارجية.
    - غير كده ⇒ نكمّل لمعالج واحد (المجموعة 0).

    P1 (إغلاق نافذة الفقد): الحاجز **فحص قراءة فقط** (`db.update_is_processed`). التسجيل
    نفسه بيحصل **ذرّيًا مع كتابة السجل الدائم** جوه معاملة `add_or_group_outbox` /
    `add_creation_job`. النتيجة:
    - لو العملية ماتت **قبل** كتابة السجل الدائم ⇒ مفيش تسجيل «معالَج» ⇒ إعادة التسليم
      بتنفّذ (مفيش فقد).
    - لو ماتت **بعد** الكتابة (اللي بتشمل التسجيل في نفس المعاملة) ⇒ السجل موجود ⇒ إعادة
      التسليم مكرّرة ⇒ تتخطّى (مفيش ازدواج).

    ملاحظة نطاق (مقصودة، وليست سهوًا): العمليات اللي **مابتعملش** سجل عمل دائم (رد/توجيه
    فقط: أوامر، تنقّل، أزرار قراءة) مش مسجّلة «معالَج»، فإعادة تسليمها بتعيد الرد. أغلبها
    قراءة/idempotent. التبديل `notif:toggle` (اللي بيغيّر حالة دائمة صغيرة) **بقى**
    مسجّلًا ذرّيًا مع التبديل (`Database.toggle_notifications_once`) — P3. باقي الأزرار
    اللي بتغيّر حالة صغيرة (`watch:`/`unwatch:`) قابلة للتكرار عمدًا: الضغطة المكرّرة
    بتعيد نفس الأثر (upsert/إزالة) فمفيش ضرر، ومنعها كان يحتاج مسارًا موازيًا بلا قيمة.
    الالتزام القائم «تحديث واحد ⇒ قرار إرسال/إنشاء واحد» محفوظ بالكامل.

    P2 (فشل القاعدة): فحص الحاجز بيتنفّذ عبر `_check_update_processed_with_retry`، اللي
    بيعيد المحاولة **محدودًا** (ميزانية صغيرة ≈ 1.75ث) للفشل **العابر** بس (SQLite
    busy/locked). لو الفشل **دائم** (قاعدة تالفة/مقفولة/جدول مش موجود) أو استنفدت الميزانية،
    بنفشل **مقفول**: بنسجّل التتبّع الكامل بنفسنا (`log.exception`)، وبنمنع الـ handlers
    الباقية (`ApplicationHandlerStop`) عشان مايحصلش معالجة مزدوجة. الإيقاف صريح (مش اعتمادًا على
    إن PTB بيوقف عند الاستثناء — اتأكّد إن PTB **بيكمّل** للمجموعة الجاية لو الاستثناء
    مش `ApplicationHandlerStop`، وبيبتلع الـ stop نفسه من غير ما يسجّله).

    **حدود P2 (موثّقة، غير مُصلَحة):** ده **مش** ضمان no-loss. `ApplicationHandlerStop`
    بيوقف المعالجة بس؛ مافيش requeue ولا تخزين للفشل. ومع `run_polling(drop_pending_updates=True)`
    الـ offset بيتقدّم عند **السحب** (قبل التنفيذ)، فالتحديث **مش** هيتسلّم تاني لو الإقلاع حصل بعده. كمان لو
    القاعدة غير متاحة، فمافيش وسيلة **آمنة** نثبّت بيها «التحديث ده مقبول ولسه محتاج معالجة»
    بدون كتابة في **نفس** القاعدة المعطوبة (أي وسيلة تانية = مخزن/worker جديد = ممنوع).
    لذا السلوك يفضل: **رفض آمن + تسجيل واضح**، مع احتمال **إسقاط** نادر لتحديث واحد وقت فشل
    **دائم/طويل**. إعادة المحاولة المحدودة بتضيّق نافذة الفشل **العابر** فقط؛ ما بتغطّيش الفشل
    الدائم. المسار المقبول الوحيد للتعافي هو ما تعالجه مسارات الاسترجاع الموجودة
    (outbox/creation) للسجلات اللي **اتكتبت** فعلًا؛ اللي **مااتكتبش** ما بيتعالجش.
    ضمان no-loss كامل يحتاج قرارًا معماريًا (إدارة offset مخصّصة أو طابور دائم قبل المعالجة)
    — بره نطاق ده التغيير ومحتاج موافقة صريحة.
    """
    update_id = getattr(update, "update_id", None)
    if not isinstance(update_id, int):
        return
    db = context.bot_data.get("db")
    if db is None:
        return  # مفيش قاعدة (استخدام غير معتاد/اختبار) ⇒ ما نمنعش المعالجة
    try:
        processed = await _check_update_processed_with_retry(db, update_id)
    except Exception as exc:  # noqa: BLE001 — فشل الحاجز ⇒ فشل مقفول صريح
        # لا نسيبه يكمّل كأن الفحص نجح. `ApplicationHandlerStop` بيوقف كل المجموعات (مفيش
        # معالجة مزدوجة)، بس PTB بيبتلعه من غير ما يسجّل أي حاجة — فبنسجّل التتبّع الكامل
        # بنفسنا هنا (مفيش توه صامت)، وبعدين بنوقف المعالجة صراحةً.
        log.exception(
            "فشل فحص حاجز التحديث (%s) — اتوقف معالجة التحديث (فشل مقفول)",
            update_id,
        )
        # OHB2-MANUAL-POLLING-HANDLER-OUTCOME: الفشل المقفول لازم يتسجّل **بثبات** كفشل
        # (غير مؤهّل للإقرار) بدل ما يفضل «مفيش نتيجة». كده **مستحيل** يتحوّل لتجاهل/نجاح
        # صامت. التسجيل هنا مباشرةً لأن `ApplicationHandlerStop` **مش** بيوصل لمعالج أخطاء
        # PTB. الفشل بيتكتب في `update_failures` بس (مش جدول الديدَب) ⇒ إعادة التسليم لسه
        # تنفّذ، فمفيش «ترخيص» مزدوج صامت.
        try:
            db.mark_update_outcome(
                update_id, outbox.now_iso(), _classify_failure(exc),
                reason=type(exc).__name__,
            )
        except Exception as rec_exc:  # noqa: BLE001 — تعذّر التسجيل ⇒ غير مؤهّل (آمن)
            log.warning(
                "تعذّر تسجيل فشل حاجز التحديث (%s): %s",
                update_id, type(rec_exc).__name__,
            )
        raise ApplicationHandlerStop
    if not processed:
        return
    log.info("تحديث تيليجرام مكرّر (%s) — اتخطّى قبل أي عملية", update_id)
    # أوقف أي handler تاني (بأي مجموعة) لنفس التحديث المكرّر.
    raise ApplicationHandlerStop


def _update_id(update: Update) -> int | None:
    """معرّف التحديث لو موجود وصالح، وإلا None (تحديثات الاختبار/الـ adapters).

    P1: بيتمرّر لـ `add_or_group_outbox`/`add_creation_job` عشان تسجيل «معالَج» يحصل
    **ذرّيًا** مع كتابة السجل الدائم.
    """
    value = getattr(update, "update_id", None)
    return value if isinstance(value, int) else None


def _classify_failure(exc: BaseException) -> str:
    """يصنّف فشل الـ handler لفئة نتيجة (OHB2-MANUAL-POLLING-OUTCOME).

    - `asyncio.CancelledError` (إلغاء/إغلاق) ⇒ `PARTIAL_OR_UNKNOWN` (مفيش حسم).
    - فشل SQLite **عابر** (BUSY/LOCKED) أو `ApiError` **تشغيلي** (5xx/429/بلا كود) ⇒
      `FAILED_TRANSIENT` (إعادة محاولة الدفعة).
    - أي حاجة تانية (فشل دائم/برمجي/رفض غير متوقّع) ⇒ `FAILED_PERMANENT`.

    التفويض للسياسة المشتركة في `update_outcomes.classify_error_outcome` (مصدر واحد)
    عشان معالج الأخطاء والـ handlers يستخدموا نفس القاعدة.
    """
    if isinstance(exc, asyncio.CancelledError):
        return update_outcomes.PARTIAL_OR_UNKNOWN
    transient = (isinstance(exc, sqlite3.Error) and _is_transient_sqlite_error(exc)) or (
        isinstance(exc, ApiError) and not outbox.is_permanent(exc)
    )
    return update_outcomes.classify_error_outcome(
        exc, transient=transient
    ) or update_outcomes.FAILED_PERMANENT


def _authorization_ignored(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يسجّل **نتيجة صريحة** لمسار رفض التفويض (غير مصرّح/محادثة غير خاصة) ⇒
    `EXPLICITLY_IGNORED` (دليل دائم ⇒ مؤهّل للإقرار، مفيش إعادة معالجة لاحقة).

    ده **رفض مقصود** (رسالة غير مالك/جروب) مش فشل — ما بنعرضش أي بيانات ومش بنغيّر
    سلوك التفويض. معرّف `update_id` بتاع تيليجرام غير سري، والكتابة بتتخطّى في
    الاختبارات (مفيش `update_id` صالح) عن طريق `mark_explicitly_ignored`.
    """
    mark_explicitly_ignored(update, context)


def record_update_failure(
    update: Update, context: ContextTypes.DEFAULT_TYPE, exc: BaseException
) -> str | None:
    """يسجّل **فشل/غموض** التحديث بثبات (best-effort) ⇒ مستحيل يتحوّل لنجاح.

    بيتنادى من مسارين:
    1. **معالج الأخطاء** (`handle_processing_error`) لأي استثناء بيوصل لـ PTB — بما فيه
       اللي الـ handler بيبتلعه في `except` ثم يرجّع (PTB بيبتلعه ويرجّع عاديًّا).
    2. مسارات الـ handler اللي بتلتقط استثناء وتعرّض رسالة للمستخدم ثم ترجع عاديًّا
       (زي `delete_conversation_confirm`/`list_conversations`/`send_reply_txt`) — بنسجّل
       الفشل **من جوّه** الـ handler عشان قرار الإقرار يفضل صحيح.

    الفشل المُسجَّل ⇒ `processed_updates.outcome` غير مؤهّل + صف في `update_failures`،
    فحدّ الإقرار بيتوقف عنده (fail-closed). لو الكتابة نفسها فشلت (قاعدة معطوبة) بنسجّل
    تحذير ونسيبها: غياب النتيجة = غير مؤهّل (الاتجاه الآمن).

    بترجّع فئة النتيجة المسجّلة (أو None لو مفيش `update_id`/قاعدة).
    """
    update_id = _update_id(update)
    db = context.bot_data.get("db") if getattr(context, "bot_data", None) else None
    if update_id is None or db is None:
        return None
    outcome = _classify_failure(exc)
    try:
        db.mark_update_outcome(
            update_id, outbox.now_iso(), outcome, reason=type(exc).__name__
        )
    except Exception as rec_exc:  # noqa: BLE001 — تعذّر التسجيل ⇒ غير مؤهّل (آمن)
        log.warning(
            "تعذّر تسجيل فشل التحديث (%s): %s", update_id, type(rec_exc).__name__
        )
        return outcome
    log.warning(
        "تحديث فاشل (%s): نتيجة=%s سبب=%s — مش مؤهّل للإقرار",
        update_id, outcome, type(exc).__name__,
    )
    return outcome


def mark_explicitly_ignored(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يسجّل نتيجة `explicitly_ignored` **بثبات** لمسار مُتجاهَل صريح (بلا نية دائمة).

    مسارات الرد/التنقّل/الأوامر مالهاش عمل دائم، فبتُسجَّل «مُتجاهَل صريح» ⇒ مؤهّلة
    للإقرار (مفيش إعادة معالجة لاحقة)، وبتفرّقها عن «مفيش نتيجة» (غير مؤهّل). best-effort:
    لو تعذّر التسجيل بنسجّل تحذير ونسيبها (غياب النتيجة = غير مؤهّل = آمن).
    """
    update_id = _update_id(update)
    db = context.bot_data.get("db") if getattr(context, "bot_data", None) else None
    if update_id is None or db is None:
        return
    try:
        db.mark_update_outcome(
            update_id, outbox.now_iso(), update_outcomes.EXPLICITLY_IGNORED
        )
    except Exception as exc:  # noqa: BLE001 — تعذّر التسجيل ⇒ غير مؤهّل (آمن)
        log.warning(
            "تعذّر تسجيل تجاهل التحديث (%s): %s", update_id, type(exc).__name__
        )


def mark_durable_completed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يسجّل نتيجة `durable_completed` **بثبات** لعملية محلية **اتـcommit بالفعل**.

    بتُنادى **بعد** ما التغيير الدائم المحلي يخلص (مش قبله) ⇒ ما بتدّعيش نجاحًا قبل
    الـ commit. لو تعذّر التسجيل بنسجّل تحذير ونسيبها (غياب النتيجة = غير مؤهّل = آمن).
    """
    update_id = _update_id(update)
    db = context.bot_data.get("db") if getattr(context, "bot_data", None) else None
    if update_id is None or db is None:
        return
    try:
        db.mark_update_outcome(
            update_id, outbox.now_iso(), update_outcomes.DURABLE_COMPLETED
        )
    except Exception as exc:  # noqa: BLE001 — تعذّر التسجيل ⇒ غير مؤهّل (آمن)
        log.warning(
            "تعذّر تسجيل اكتمال التحديث (%s): %s", update_id, type(exc).__name__
        )


def mark_ambiguous_external(
    update: Update, context: ContextTypes.DEFAULT_TYPE, reason: str
) -> None:
    """يسجّل نتيجة **غامضة** لعملية خارجية فشلت (نتيجة غير محسومة) ⇒ `PARTIAL_OR_UNKNOWN`.

    بيتنادى بعد ما المسار يعرض رسالة الفشل **ويرجع عاديًّا** (بدل ما ينتشر) — عشان النتيجة
    تفضل موثّقة كـ «غير محسومة» ومستحيل تتحسب نجاح/تجاهل (fail-closed). لو تعذّر التسجيل
    بنسجّل تحذير ونسيبها (غياب النتيجة = غير مؤهّل = آمن).
    """
    update_id = _update_id(update)
    db = context.bot_data.get("db") if getattr(context, "bot_data", None) else None
    if update_id is None or db is None:
        return
    try:
        db.mark_update_outcome(
            update_id, outbox.now_iso(), update_outcomes.PARTIAL_OR_UNKNOWN, reason=reason
        )
    except Exception as exc:  # noqa: BLE001 — تعذّر التسجيل ⇒ غير مؤهّل (آمن)
        log.warning(
            "تعذّر تسجيل غموض التحديث (%s): %s", update_id, type(exc).__name__
        )


def mark_display_failed(
    update: Update, context: ContextTypes.DEFAULT_TYPE, reason: str
) -> None:
    """يسجّل **فشل عرض** المحتوى المطلوب (فشل تعديل/إرسال تيليجرام) ⇒ `FAILED_TRANSIENT`.

    العرض هو المحتوى الوحيد اللي المستخدم طلبه، ففشله (تسليم تيليجرام) فشل عابر
    (قابل لإعادة المحاولة)، **مش** نجاح ومش تجاهل مقصود ⇒ غير مؤهّل للإقرار.
    """
    update_id = _update_id(update)
    db = context.bot_data.get("db") if getattr(context, "bot_data", None) else None
    if update_id is None or db is None:
        return
    try:
        db.mark_update_outcome(
            update_id, outbox.now_iso(), update_outcomes.FAILED_TRANSIENT, reason=reason
        )
    except Exception as exc:  # noqa: BLE001 — تعذّر التسجيل ⇒ غير مؤهّل (آمن)
        log.warning(
            "تعذّر تسجيل فشل عرض التحديث (%s): %s", update_id, type(exc).__name__
        )


def mark_failed_permanent(
    update: Update, context: ContextTypes.DEFAULT_TYPE, reason: str
) -> None:
    """يسجّل فشلًا **دائمًا** مؤكّدًا (مفيش إعادة محاولة مفيدة) ⇒ `FAILED_PERMANENT`.

    (مثال: الرد أكبر من حد الملف النصي ⇒ مفيش داعي لإعادة المحاولة.)
    """
    update_id = _update_id(update)
    db = context.bot_data.get("db") if getattr(context, "bot_data", None) else None
    if update_id is None or db is None:
        return
    try:
        db.mark_update_outcome(
            update_id, outbox.now_iso(), update_outcomes.FAILED_PERMANENT, reason=reason
        )
    except Exception as exc:  # noqa: BLE001 — تعذّر التسجيل ⇒ غير مؤهّل (آمن)
        log.warning(
            "تعذّر تسجيل الفشل الدائم (%s): %s", update_id, type(exc).__name__
        )


def mark_operational_failure(
    update: Update, context: ContextTypes.DEFAULT_TYPE, reason: str
) -> None:
    """يسجّل فشل upstream **تشغيلي** (5xx/429/مهلة/انقطاع) ⇒ `FAILED_TRANSIENT`.

    OHB2-STAGE4-F1: مسارات العرض (`show_status`/`show_cost`) بترجع عاديًّا بعد عرض رسالة
    الفشل، فمن غير تسجيل صريح كان التحديث ياخد نتيجة مؤهّلة (تجاهل/نجاح) أو «مفيش نتيجة».
    الفشل التشغيلي **مش** رفض نهائي مؤكّد ⇒ ممنوع يتسجّل `explicitly_ignored`؛ لازم
    `FAILED_TRANSIENT` (غير مؤهّل، fail-closed) عشان الحدّ **مايتقدّمش** فوقه.

    **صارم (strict) عن قصد:** لو تعذّر تسجيل النتيجة (قاعدة معطوبة) بنرفع الاستثناء بدل ما
    نبلعه. ده مسار فشل تشغيلي، فمنعرض رسالة المستخدم **قبل** النداء (بره الدالة)، والرفع
    هنا بيفضل آمن: (أ) `collect_outcomes` بتشوف «مفيش نتيجة» ⇒ `partial_or_unknown` (غير
    مؤهّل، نفس نتيجة الفشل) ⇒ الحدّ مايتقدّمش؛ (ب) معالج الأخطاء بيسجّل الفشل بثبات (best-effort).
    ممنوع هنا نرجّع «نجاح صامت» (وده اللي كان بيمنع تسجيل الفشل).
    """
    update_id = _update_id(update)
    db = context.bot_data.get("db") if getattr(context, "bot_data", None) else None
    if update_id is None or db is None:
        return
    db.mark_update_outcome(
        update_id, outbox.now_iso(), update_outcomes.FAILED_TRANSIENT, reason=reason
    )


async def handle_processing_error(
    update: object, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """معالج أخطاء PTB: يسجّل فشل التحديث **بثبات** بدل ما يُبتلع كنجاح.

    PTB بينده المعالج ده لأي استثناء في handler (`process_update` ⇒ `process_error`)،
    و**بدونه** كان بيسجّل الاستثناء ويرجّع عاديًّا ⇒ رجوع `process_update` يبان نجاح.
    دلوقتي الفشل بيتسجّل في القاعدة (غير مؤهّل للإقرار) ⇒ قرار الإقرار صحيح.

    ما بيعملش أي عملية خارجية، وما بيعيدش رفع الاستثناء (PTB بيعتبر إن معالج الأخطاء
    تعامل معاه)، وما بيكتبش نص الاستثناء (احتمال أسرار) — النوع بس.
    """
    exc = getattr(context, "error", None)
    if exc is None or isinstance(exc, ApplicationHandlerStop):
        return  # مفيش خطأ حقيقي (أو إيقاف مقصود مش فشل)
    if isinstance(update, Update):
        record_update_failure(update, context, exc)
    log.error("فشل معالجة تحديث (نوع=%s) — اتسجّل كفشل، مش نجاح.", type(exc).__name__)


def _mini_app_url(context: ContextTypes.DEFAULT_TYPE) -> str:
    """رابط الـ Mini App لو الميزة **مفعّلة** ومهيّأة، وإلا فاضي.

    لازم الاتنين: `MINI_APP_ENABLED=1` **و** رابط `MINI_APP_URL` صالح. كده ما بنعرضش
    زر web_app لرابط ميت (الميزة مفعّلة بلا سيرفر شغّال، أو رابط بدون تفعيل).
    """
    cfg = context.bot_data.get("config")
    if cfg is None or not getattr(cfg, "mini_app_enabled", False):
        return ""
    return getattr(cfg, "mini_app_url", "") or ""


def _mini_app_diagnostic(context: ContextTypes.DEFAULT_TYPE) -> str:
    """سبب عدم إتاحة الـ Mini App — **بدون أي أسرار** (أسماء إعدادات بس)."""
    cfg = context.bot_data.get("config")
    if cfg is None:
        return "الإعداد غير متاح."
    if not getattr(cfg, "mini_app_enabled", False):
        return "الميزة مقفولة (MINI_APP_ENABLED=0)."
    if not (getattr(cfg, "mini_app_url", "") or ""):
        return "الرابط العام (MINI_APP_URL) غير مهيّأ."
    return "الإعداد غير مكتمل."


MINI_APP_UNAVAILABLE = (
    "التطبيق المصغّر مش متاح دلوقتي. الأوامر والأزرار العادية شغالة زي ما هي."
)


HELP_TEXT = (
    "أنا بوت تحكمك في OpenHands Cloud. الأوامر المتاحة:\n"
    "/start — القائمة الرئيسية\n"
    "/app — فتح التطبيق المصغّر (Mini App)\n"
    "/help — هذه المساعدة\n"
    "/notifications — ضبط الإشعارات الاستباقية\n"
    "/cancel — إلغاء التوجيه الحالي\n"
    "\n"
    "صيانة الصندوق (للمالك):\n"
    "/outbox — السجلات المعلّقة\n"
    "/outbox_status — تفاصيل سجل واحد\n"
    "/outbox_discard — شطب سجل (يتطلب confirm)\n"
    "/outbox_mark_sent — تأكيد إرسال سجل (يتطلب confirm)"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    context.bot_data["db"].clear_awaiting(update.effective_user.id)
    await update.message.reply_text(
        "أهلاً 👋\nأنا بوت تحكمك في OpenHands Cloud.\n"
        "اختار من الأزرار تحت، أو افتح شات وابعتله برومت.",
        reply_markup=kb.main_menu(_mini_app_url(context)),
    )
    mark_explicitly_ignored(update, context)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    await update.message.reply_text(HELP_TEXT)
    mark_explicitly_ignored(update, context)


async def app_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    url = _mini_app_url(context)
    if not url:
        await update.message.reply_text(
            f"{MINI_APP_UNAVAILABLE}\nالسبب: {_mini_app_diagnostic(context)}"
        )
        mark_explicitly_ignored(update, context)
        return
    await update.message.reply_text("افتح التطبيق من الزر:", reply_markup=kb.mini_app_launch(url))
    mark_explicitly_ignored(update, context)


async def app_open(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        # OHB2-MANUAL-POLLING-HANDLER-OUTCOME: رفض تفويض مقصود ⇒ نتيجة صريحة.
        _authorization_ignored(update, context)
        return
    url = _mini_app_url(context)
    if not url:
        await q.edit_message_text(
            f"{MINI_APP_UNAVAILABLE}\nالسبب: {_mini_app_diagnostic(context)}",
            reply_markup=kb.main_menu(_mini_app_url(context)),
        )
        mark_explicitly_ignored(update, context)
        return
    await q.edit_message_text("افتح التطبيق من الزر:", reply_markup=kb.mini_app_launch(url))
    mark_explicitly_ignored(update, context)


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        # OHB2-MANUAL-POLLING-HANDLER-OUTCOME: رفض تفويض مقصود ⇒ نتيجة صريحة.
        _authorization_ignored(update, context)
        return
    context.bot_data["db"].clear_awaiting(update.effective_user.id)  # تنقّل = خروج من أي توجيه
    await q.edit_message_text(
        "أهلاً 👋 اختار من الأزرار:", reply_markup=kb.main_menu(_mini_app_url(context))
    )
    mark_explicitly_ignored(update, context)


def _notifications_text(enabled: bool) -> str:
    state = "مفعّلة ✅" if enabled else "متوقفة ⛔"
    return (
        f"إشعارات OpenHands الاستباقية: {state}\n\n"
        "لما تكون مفعّلة، هبلّغك لما أي محادثة توصل لحالة نهائية "
        "(انتهت/خطأ/متعلّقة/مستنية تأكيد/خطأ بيئة).\n"
        "الإيقاف بيوقف الإشعارات الاستباقية بس — باقي أوامر البوت وأزراره زي ما هي."
    )


async def notifications_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    db = context.bot_data["db"]
    await update.message.reply_text(
        _notifications_text(db.get_notifications_enabled()),
        reply_markup=kb.notifications_menu(db.get_notifications_enabled()),
    )
    mark_explicitly_ignored(update, context)


async def notifications_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        # OHB2-MANUAL-POLLING-HANDLER-OUTCOME: رفض تفويض مقصود ⇒ نتيجة صريحة.
        _authorization_ignored(update, context)
        return
    db = context.bot_data["db"]
    enabled = db.get_notifications_enabled()
    await q.edit_message_text(_notifications_text(enabled), reply_markup=kb.notifications_menu(enabled))
    mark_explicitly_ignored(update, context)


async def notifications_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not _allowed(update, context.bot_data["config"]):
        # OHB2-MANUAL-POLLING-HANDLER-OUTCOME: رفض تفويض مقصود ⇒ نتيجة صريحة.
        _authorization_ignored(update, context)
        await q.answer()
        return
    db = context.bot_data["db"]
    # P3: التبديل + علامة «معالَج» في **معاملة واحدة** ⇒ إعادة تسليم نفس التحديث
    # (`update_id` متكرر) ما بتعكسش الحالة تاني؛ تحديث مختلف بيكمل التبديل عادي.
    new_state = db.toggle_notifications_once(_update_id(update), outbox.now_iso())
    if new_state is None:
        await q.answer()  # تحديث مكرّر: مفيش تبديل تاني (ومافيش عرض مضلّل)
        return
    # OHB2-SW09: التبديل اتعمّل (commit) بالفعل فوق. فشل تأكيد الكولباك بعد الـ commit
    # (استثناء تيليجرام/شبكة) **مايوقفش** تحديث الواجهة اللي بعده — التفضيل اتغيّر فعلًا
    # ولازم الرسالة تعكس الحالة الجديدة. بنلفّ الـ answer لوحده بس (أضيق حدود ممكنة)،
    # وبنكمّل للـ edit_message_text بالحالة المعمّلة. `except Exception` مايلتقطش
    # `asyncio.CancelledError` (BaseException) ⇒ الإلغاء ينتشر زي ما هو. بنسجّل نوع الخطأ
    # بس (من غير نص الاستثناء، ممكن يحتوي أسرار).
    try:
        await q.answer("تم التحديث ✅")
    except Exception as exc:  # noqa: BLE001 — فشل تأكيد الكولباك مايوقفش تحديث الواجهة
        log.warning("تعذّر الرد على الكولباك بعد تبديل الإشعارات (%s)", type(exc).__name__)
    await q.edit_message_text(
        _notifications_text(new_state), reply_markup=kb.notifications_menu(new_state)
    )


def _without_deleted(db, items: list[dict]) -> list[dict]:
    """يشيل الشاتات المحذوفة محليًا (tombstone) من قايمة شاتات البوت (OHB2-F1).

    القايمة بتيجي من بحث بعيد مش عارف بالحذف المحلي، فبندمجها مع شاهد الحذف قبل الترقيم
    عشان الشات المحذوف ما يظهرش لا من كاش قديم ولا من بحث جديد.

    OHB2-SW03 (كان OHB2-AUDIT-FIX-04): فشل قراءة شواهد الحذف **مايتحوّلش** لقايمة فاضية.
    بنستخدم `db.is_deleted_with_retry` (إعادة محدودة للعابر BUSY/LOCKED ثم رفع الاستثناء
    الأصلي). الفشل **بينتشر** للمستدعي بدل ما يُلبَس لبوس «مفيش شاتات» — الفراغ الحقيقي
    (مدخل فاضي أو كل الشاتات متشاهدة) لسه بيرجّع `[]` بشكل مشروع، لكن فشل القاعدة **مش**
    فراغ. حماية F-1 نفسها ما اتغيّرتش: الشات المتشاهد لسه بيُفلتر.
    """
    if not items:
        return items
    return [c for c in items if not db.is_deleted_with_retry(c.get("id") or "")]


async def list_conversations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        # OHB2-MANUAL-POLLING-HANDLER-OUTCOME: رفض تفويض مقصود ⇒ نتيجة صريحة.
        _authorization_ignored(update, context)
        return
    context.bot_data["db"].clear_awaiting(update.effective_user.id)  # تنقّل = خروج من أي توجيه
    page = int(q.data.split(":", 1)[1])
    client = context.bot_data["client"]
    # نجيب كل صفحات البحث (نتبع next_page_id بحد أقصى). `collect_conversations` بيرجّع
    # القايمة مرتّبة بـ `updated_at` تنازليًا وبدون تكرارات (عقد ترتيب صريح، مش معتمد على
    # ترتيب الـ API الخام) — فالترقيم ثابت عبر الصفحات.
    # TASK 55 (G4): كاش قصير للقايمة عشان الضغط على «المزيد» ما يعملش طلب API كل مرة.
    cache = context.bot_data.get("list_cache")
    if cache and time.monotonic() - cache[0] < LIST_TTL:
        items = cache[1]
        truncated = cache[2] if len(cache) > 2 else False
    else:
        try:
            collected = await collect_conversations(client)
        except ApiError as exc:
            # OHB2-SW-07: نعرض الرسالة المتنقّحة (زي القديم)؛ ولو الفشل تشغيلي (5xx/429/
            # بلا كود) نرفعه بعد العرض بدل ما يتحوّل لـ «إتمام معالجة ناجح». رفض 4xx
            # المتوقّع (404/403/410) يفضل رجوع عادي (نتيجة مستخدم متوقّعة).
            await _safe_edit(q, error_text(exc))
            await _raise_if_operational_api_failure(exc)
            # وصلنا هنا ⇒ رفض 4xx متوقّع (الفشل التشغيلي اترفع فوق) ⇒ نتيجة مستخدم صريحة.
            mark_explicitly_ignored(update, context)
            return
        items = collected["items"]
        truncated = collected["truncated"]
        if items:
            context.bot_data["list_cache"] = (time.monotonic(), items, truncated)
    # OHB2-F1: الشاتات المحذوفة محليًا لازم تختفي من القايمة قبل الترقيم — سواء جاية من
    # كاش قديم أو من بحث بعيد جديد (البحث مش عارف بالحذف المحلي).
    # OHB2-SW03: فشل قراءة الشواهد (بعد الإعادة المحدودة) **مايتحوّلش** لقايمة فاضية ولا
    # لرسالة «ما فيهاش شاتات» الكاذبة — بنعرض رسالة فشل عامة (من غير تفاصيل داخلية) وبنرجع.
    try:
        items = _without_deleted(context.bot_data["db"], items)
    except Exception as exc:  # noqa: BLE001 — فشل قاعدة بعد الإعادة المحدودة ⇒ فشل صريح
        log.exception("تعذّر فلترة الشواهد في قايمة الشاتات (%s)", type(exc).__name__)
        # OHB2-MANUAL-POLLING-OUTCOME: فشل القاعدة المُبتلَع (بنعرض رسالة ونرجع عاديًّا)
        # لازم يتسجّل كفشل ⇒ مايتقبلش كنجاح.
        record_update_failure(update, context, exc)
        await _safe_edit(
            q, "تعذّر عرض الشاتات دلوقتي، جرّب تاني.",
            reply_markup=kb.main_menu(_mini_app_url(context)),
        )
        return
    if not items:
        await _safe_edit(q, "ما فيهاش شاتات.", reply_markup=kb.main_menu(_mini_app_url(context)))
        mark_explicitly_ignored(update, context)
        return
    start = page * PAGE_SIZE
    chunk = items[start : start + PAGE_SIZE]
    if not chunk:
        page, start = 0, 0
        chunk = items[:PAGE_SIZE]
    has_more = len(items) > start + PAGE_SIZE
    header = f"آخر الشاتات (صفحة {page + 1}):"
    if truncated:
        # OHB2-AUDIT-FIX-05: القايمة أطول من الحد المسموح ⇒ نعلن ده بدل إخفاء صامت.
        header += f"\n(القايمة طويلة — بنعرض أحدث {len(items)} شات.)"
    await _safe_edit(
        q,
        header,
        reply_markup=kb.conversations_menu(chunk, page, has_more),
    )
    mark_explicitly_ignored(update, context)


async def open_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        # OHB2-MANUAL-POLLING-HANDLER-OUTCOME: رفض تفويض مقصود ⇒ نتيجة صريحة.
        _authorization_ignored(update, context)
        return
    conversation_id = q.data.split(":", 1)[1]
    client = context.bot_data["client"]
    # OHB2-09-06: تفويض ملكية الشات أولًا (نفس عقد FileService)، بعدين نجيب آخر تبادل طازة.
    # (فتح الشات بيقرا طازة دايماً — مش من كاش copy/full.)
    conv, status, message, auth_exc = await _authorized_conversation_status(client, context, conversation_id)
    if conv is None:
        # OHB2-SW-05: ناخد بالنا من نتيجة العرض؛ فشل عرض رسالة الرفض يتسجّل بدل ما يتخفي.
        if not await _edit_or_send(q, message, q.message.chat_id, context.bot):
            log.warning("تعذّر عرض رسالة رفض فتح الشات %s (فشل تسليم تيليجرام).", conversation_id)
        # OHB2-SW-07: فشل upstream **تشغيلي** (5xx/429/مهلة/انقطاع) ينتشر بعد عرض الرسالة
        # بدل ما يتحوّل لإتمام ناجح. رفض 4xx المتوقّع (401/403/404/410) + الرفض المشتقّ
        # (NOT_FOUND/DELETED/UNAUTHORIZED) يرجّع عادي — ممنوع نحوّل الرفض المصرّح لفشل عابر.
        if status is FileStatus.UPSTREAM_ERROR and not _is_expected_upstream_rejection(auth_exc):
            await _raise_if_operational_api_failure(auth_exc)
        # OHB2-STAGE2-HIGH-ACK-BLOCKING-FIX: رفض نهائي مؤكّد (مش موجود/متشاهد/غير مصرّح) ⇒
        # نتيجة صريحة مؤهّلة للإقرار، وإلا كان الحدّ يتوقف عنده للأبد (حجب fail-closed بلا
        # سبب). الفشل التشغيلي فوق **بيرفع** قبل السطر ده ⇒ مستحيل يتحوّل لتجاهل كاذب.
        mark_explicitly_ignored(update, context)
        return
    try:
        user_text, reply = await client.get_last_exchange(conversation_id)
    except ApiError as exc:
        # نفس المسار المتسامح لرسالة الخطأ: مفيش توجيه جديد ولا انهيار في الـ callback.
        if not await _edit_or_send(q, error_text(exc), q.message.chat_id, context.bot):
            log.warning("تعذّر عرض خطأ آخر تبادل للشات %s (فشل تسليم تيليجرام).", conversation_id)
        await _raise_if_operational_api_failure(exc)
        mark_explicitly_ignored(update, context)
        return
    _store_exchange(context, conversation_id, user_text, reply)
    db = context.bot_data["db"]
    watched = db.is_watched(conversation_id)
    text, reply_cut = format_conversation_view(conv, user_text, reply)
    if reply is not None:
        text += (
            "\n\n📋 زر «عرض للنسخ اليدوي» بيبعتلك الرد جوه code block عشان تنسخه يدويًا "
            "(بوتات تيليجرام ما بتكتبش في الحافظة تلقائيًا) — أو انسخ بضغطة من الـ Mini App "
            "أو نزّله كـ «ملف النص» (.txt)."
        )
    text += "\n\n✉️ رسايلك الجاية هتتبعت للشات ده (10 دقايق من آخر نشاط). للإلغاء: زر إلغاء التوجيه أو /cancel."
    markup = kb.conversation_actions(
        conversation_id,
        watched,
        has_reply=reply is not None,
        reply_cut=reply_cut,
        mini_app_url=_mini_app_url(context),
    )
    # القرار 1: بعد فتح الشات، رسايلك الجاية بتتوجّه له 10 دقايق من آخر نشاط (مع زر إلغاء).
    # بنفعّل التوجيه بس بعد ما العرض يظهر فعلاً، عشان فشل العرض ما يسبش توجيه مفعّل من غير
    # ما تشوف الشات (وما نلمسش أي توجيه قائم لو الفتح فشل).
    if await _edit_or_send(q, text, q.message.chat_id, context.bot, reply_markup=markup):
        db.set_awaiting(update.effective_user.id, conversation_id, "route", title=conv.get("title") or "")
        mark_explicitly_ignored(update, context)
    else:
        # OHB2-STAGE2-HIGH-ACK-BLOCKING-FIX: العرض هو المحتوى اللي المستخدم طلبه؛ فشل تسليمه
        # فشل **عابر** (قابل لإعادة المحاولة) — نفس سياسة show_status/show_cost — **مش** نجاح
        # ومش تجاهل. بدون التسجيل كان التحديث يفضل بلا نتيجة (غير مؤهّل) بلا تمييز للسبب.
        log.warning("تعذّر عرض الشات %s (فشل تعديل/إرسال تيليجرام).", conversation_id)
        mark_display_failed(update, context, "open_display_failed")


async def copy_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """TASK 55 (المرحلة B): يبعت رد الـ agent جوه code block قابل للنسخ بضغطة."""
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        # OHB2-MANUAL-POLLING-HANDLER-OUTCOME: رفض تفويض مقصود ⇒ نتيجة صريحة.
        _authorization_ignored(update, context)
        return
    conversation_id = q.data.split(":", 1)[1]
    chat_id = q.message.chat_id
    # OHB2-09-06: تفويض ملكية الشات قبل قراءة آخر تبادل (نفس عقد FileService).
    _conv, status, message, auth_exc = await _authorized_conversation_status(
        context.bot_data["client"], context, conversation_id
    )
    if _conv is None:
        await context.bot.send_message(chat_id, escape_html(message), parse_mode=ParseMode.HTML)
        # OHB2-SW-07: فشل upstream تشغيلي (5xx/429/بلا كود) ينتشر بعد الرسالة؛ رفض 4xx
        # المتوقّع + الرفض المشتقّ يرجّع عادي.
        if status is FileStatus.UPSTREAM_ERROR and not _is_expected_upstream_rejection(auth_exc):
            await _raise_if_operational_api_failure(auth_exc)
        # OHB2-STAGE2-HIGH-ACK-BLOCKING-FIX: رفض نهائي مؤكّد ⇒ نتيجة صريحة مؤهّلة للإقرار
        # (الفشل التشغيلي فوق بيرفع قبلها ⇒ مستحيل يتحوّل لتجاهل كاذب).
        mark_explicitly_ignored(update, context)
        return
    try:
        _, reply = await _get_exchange(context, conversation_id)
    except ApiError as exc:
        await context.bot.send_message(chat_id, escape_html(error_text(exc)), parse_mode=ParseMode.HTML)
        await _raise_if_operational_api_failure(exc)
        mark_explicitly_ignored(update, context)
        return
    if not reply:
        await context.bot.send_message(chat_id, "لسه مفيش رد للشات ده.")
        mark_explicitly_ignored(update, context)
        return
    await send_copyable(chat_id, reply, context.bot)
    mark_explicitly_ignored(update, context)


async def full_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """TASK 55 (المرحلة B): يبعت الرد الكامل (نفس منطق send_long)."""
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        # OHB2-MANUAL-POLLING-HANDLER-OUTCOME: رفض تفويض مقصود ⇒ نتيجة صريحة.
        _authorization_ignored(update, context)
        return
    conversation_id = q.data.split(":", 1)[1]
    chat_id = q.message.chat_id
    # OHB2-09-06: تفويض ملكية الشات قبل قراءة آخر تبادل (نفس عقد FileService).
    _conv, status, message, auth_exc = await _authorized_conversation_status(
        context.bot_data["client"], context, conversation_id
    )
    if _conv is None:
        await context.bot.send_message(chat_id, escape_html(message), parse_mode=ParseMode.HTML)
        # OHB2-SW-07: فشل upstream تشغيلي (5xx/429/بلا كود) ينتشر بعد الرسالة؛ رفض 4xx
        # المتوقّع + الرفض المشتقّ يرجّع عادي.
        if status is FileStatus.UPSTREAM_ERROR and not _is_expected_upstream_rejection(auth_exc):
            await _raise_if_operational_api_failure(auth_exc)
        # OHB2-STAGE2-HIGH-ACK-BLOCKING-FIX: رفض نهائي مؤكّد ⇒ نتيجة صريحة مؤهّلة للإقرار
        # (الفشل التشغيلي فوق بيرفع قبلها ⇒ مستحيل يتحوّل لتجاهل كاذب).
        mark_explicitly_ignored(update, context)
        return
    try:
        _, reply = await _get_exchange(context, conversation_id)
    except ApiError as exc:
        await context.bot.send_message(chat_id, escape_html(error_text(exc)), parse_mode=ParseMode.HTML)
        await _raise_if_operational_api_failure(exc)
        mark_explicitly_ignored(update, context)
        return
    if not reply:
        await context.bot.send_message(chat_id, "لسه مفيش رد للشات ده.")
        mark_explicitly_ignored(update, context)
        return
    await send_long(chat_id, reply, context.bot)
    mark_explicitly_ignored(update, context)


async def send_reply_txt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """OHB2-BOT-REPLY-TXT-FILE-BUTTON: يبعت **الرد الكامل** كملف `.txt` قابل للتنزيل.

    إجراء منفصل تمامًا عن «نسخ الرد» (callback مختلف `txt:`، ومسار إرسال مختلف:
    `send_document` بدل `<pre>`). المصدر هو **نفس** مصدر copy/full — آخر تبادل كامل من
    الـ API (`get_last_exchange`، بلا حدّ تقسيم الرسايل)، مش نص رسالة تيليجرام واحدة.

    التفويض: نفس عقد `_authorized_conversation` (ملكية/معرّف/شاهد حذف/فشل مغلق) قبل أي
    قراءة أو إرسال — فمستحيل مستخدم يجيب رد حد تاني بتغيير الـ callback data.
    """
    q = update.callback_query
    try:
        await q.answer()
    except Exception as exc:  # noqa: BLE001 — فشل إجابة الكولباك (استعلام قديم) مايوقفش التنزيل
        log.warning("تعذّر الرد على الكولباك (%s)", type(exc).__name__)
    if not _allowed(update, context.bot_data["config"]):
        # OHB2-MANUAL-POLLING-HANDLER-OUTCOME: رفض تفويض مقصود ⇒ نتيجة صريحة.
        _authorization_ignored(update, context)
        return
    conversation_id = q.data.split(":", 1)[1]
    chat_id = q.message.chat_id
    _conv, message = await _authorized_conversation(context.bot_data["client"], context, conversation_id)
    if _conv is None:
        await context.bot.send_message(chat_id, escape_html(message), parse_mode=ParseMode.HTML)
        mark_explicitly_ignored(update, context)
        return
    try:
        _, reply = await _get_exchange(context, conversation_id)
    except ApiError as exc:
        await context.bot.send_message(chat_id, escape_html(error_text(exc)), parse_mode=ParseMode.HTML)
        if outbox.is_permanent(exc):
            mark_explicitly_ignored(update, context)
        else:
            mark_ambiguous_external(update, context, "send_txt_upstream_failed")
        return
    if not reply:
        await context.bot.send_message(chat_id, "لسه مفيش رد للشات ده.")
        mark_explicitly_ignored(update, context)
        return
    reply_to = getattr(q.message, "message_id", None)
    try:
        await send_text_document(chat_id, reply, context.bot, reply_to_message_id=reply_to)
    except TextDocumentTooLargeError:
        # الحد الأقصى للحجم ⇒ مفيش إعادة محاولة مفيدة ⇒ فشل **دائم**.
        await context.bot.send_message(chat_id, "الرد كبير أوي للتنزيل كملف نصي.")
        mark_failed_permanent(update, context, "text_document_too_large")
        return
    except Exception as exc:  # noqa: BLE001 — فشل الإرسال ⇒ ما ندّعيش النجاح؛ رسالة صريحة
        log.warning("فشل إرسال ملف الرد النصي (%s)", type(exc).__name__)
        # OHB2-MANUAL-POLLING-OUTCOME: فشل الإرسال الخارجي المُبتلَع ⇒ تسجيل فشل
        # (مايتقبلش كنجاح).
        record_update_failure(update, context, exc)
        await context.bot.send_message(chat_id, "تعذّر إرسال ملف النص دلوقتي، جرّب تاني.")
        return
    mark_explicitly_ignored(update, context)


async def list_watches(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        # OHB2-MANUAL-POLLING-HANDLER-OUTCOME: رفض تفويض مقصود ⇒ نتيجة صريحة.
        _authorization_ignored(update, context)
        return
    context.bot_data["db"].clear_awaiting(update.effective_user.id)  # تنقّل = خروج من أي توجيه
    page = int(q.data.split(":", 1)[1])
    items = context.bot_data["db"].list_watched()
    if not items:
        await _safe_edit(q, "مفيش شاتات متابَعة.", reply_markup=kb.main_menu(_mini_app_url(context)))
        mark_explicitly_ignored(update, context)
        return
    start = page * PAGE_SIZE
    chunk = items[start : start + PAGE_SIZE]
    if not chunk:
        page, start = 0, 0
        chunk = items[:PAGE_SIZE]
    has_more = len(items) > start + PAGE_SIZE
    await _safe_edit(
        q,
        f"متابعاتي (صفحة {page + 1}) — {len(items)} شات:",
        reply_markup=kb.watches_menu(chunk, page, has_more),
    )
    mark_explicitly_ignored(update, context)


async def watch_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        # OHB2-MANUAL-POLLING-HANDLER-OUTCOME: رفض تفويض مقصود ⇒ نتيجة صريحة.
        _authorization_ignored(update, context)
        return
    conversation_id = q.data.split(":", 1)[1]
    client = context.bot_data["client"]
    db = context.bot_data["db"]
    # OHB2-09-06/A2-02: نفس عقد ملكية الشات قبل الإضافة (مفيش شات غير مملوك للمتابعة).
    # F-1: `allow_deleted=True` — زر «متابعة» إعادة تفاعل صريح (طبقة القاعدة بتشيل الشاهد
    # عبر `reengage=True`)، فمش مسار قراءة.
    conv, message = await _authorized_conversation(
        client, context, conversation_id, allow_deleted=True
    )
    if conv is None:
        await _safe_edit(q, message)
        mark_explicitly_ignored(update, context)
        return
    # NTF-19: لو الشات متابَع بالفعل، الضغطة دي إعادة نداء مكرّرة (double-tap) ⇒ نحافظ على
    # المعرّف والعلامة المعلّقة (new_lifecycle=False). لو مش متابَع، الصف مش موجود فالـ INSERT
    # بيعمل دورة جديدة بمعرّف جديد تلقائيًا.
    db.add_watched(
        conversation_id, conv.get("title", ""), q.message.chat_id,
        new_lifecycle=False, reengage=True,
    )
    db.set_last_state(conversation_id, conv.get("execution_status") or "")
    await _safe_edit(
        q, "تمام، الشات اتضاف للمتابعة ✅", reply_markup=kb.conversation_actions(conversation_id, True)
    )
    mark_durable_completed(update, context)


async def unwatch_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        # OHB2-MANUAL-POLLING-HANDLER-OUTCOME: رفض تفويض مقصود ⇒ نتيجة صريحة.
        _authorization_ignored(update, context)
        return
    conversation_id = q.data.split(":", 1)[1]
    # NTF-17: نمرّ عبر المراقب (لو موجود) عشان أي تسليم معلّق في الذاكرة يتكمّل ذرّيًا،
    # ومايحصلش إرسال مكرّر بعد إزالة المتابعة.
    watcher = context.bot_data.get("watcher")
    remover = watcher.unwatch if watcher is not None else context.bot_data["db"].remove_watched
    try:
        # OHB2-SW-06: إعادة محاولة **محدودة** للفشل العابر (SQLite BUSY/LOCKED) بس.
        await _remove_watched_with_retry(remover, conversation_id)
    except sqlite3.Error:
        # OHB2-SW-06: الفشل الدائم (أو استنفاد إعادة المحاولات) مايتحوّلش لنجاح كاذب —
        # نعرض رسالة متنقّحة + زر المحاولة، وبعدين **نرفع الاستثناء الأصلي** (بـ traceback)
        # عشان المتصل/الإطار يشوف الفشل (مفيش ابتلاع، وفرصة إعادة محاولة حقيقية قائمة).
        log.exception("تعذّر إزالة متابعة الشات %s", conversation_id)
        # نبني نفس قائمة المتابعات تاني عشان زر المحاولة يفضل متاح (الشات لسه متابَع).
        try:
            items = context.bot_data["db"].list_watched()
            markup = kb.watches_menu(items[:PAGE_SIZE], 0, len(items) > PAGE_SIZE)
        except sqlite3.Error:
            markup = None
        await _safe_edit(
            q,
            "تعذّر إلغاء المتابعة دلوقتي (خطأ مؤقت في قاعدة البيانات). جرّب تاني.",
            reply_markup=markup,
        )
        raise
    await _safe_edit(q, "تمام، اتشال من المتابعة.")
    mark_durable_completed(update, context)


async def delete_conversation_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """OHB2-MINIAPP: يعرض تأكيد حذف الشات **من OpenHands**. تفويض الملكية قبل أي حذف."""
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        # OHB2-MANUAL-POLLING-HANDLER-OUTCOME: رفض تفويض مقصود ⇒ نتيجة صريحة.
        _authorization_ignored(update, context)
        return
    conversation_id = q.data.split(":", 1)[1]
    # F-1: `allow_deleted=True` — أول ضغطة على 🗑 عملية صريحة على شات ممكن يكون متشاهد
    # (deleting/uncertain). الحذف المحلي بيسيب الشات في `deleted_conversations`، فحجب
    # شاشة التأكيد كان بيقطع إعادة المحاولة الموثّقة (نفس ما اتصلح في زر التأكيد
    # `deleteok:` والـ Mini App). الحماية الحقيقية في CAS الحذف جوه `delete_conversation`.
    conv, message = await _authorized_conversation(
        context.bot_data["client"], context, conversation_id, allow_deleted=True
    )
    if conv is None:
        await _safe_edit(q, message)
        mark_explicitly_ignored(update, context)
        return
    title = conv.get("title") or "بدون عنوان"
    await _safe_edit(
        q,
        f"متأكد إنك عايز تحذف الشات «{title}»؟\n"
        "ده هيحذفه نهائيًا من OpenHands نفسه (مش إخفاء محلي) — العملية مش قابلة للرجوع.",
        reply_markup=kb.delete_confirm_menu(conversation_id),
    )
    mark_explicitly_ignored(update, context)


async def delete_conversation_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """OHB2-MINIAPP: تأكيد حذف الشات **من OpenHands** ثم محليًا. تفويض الملكية إلزامي."""
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        # OHB2-MANUAL-POLLING-HANDLER-OUTCOME: رفض تفويض مقصود ⇒ نتيجة صريحة.
        _authorization_ignored(update, context)
        return
    conversation_id = q.data.split(":", 1)[1]
    client = context.bot_data["client"]
    db = context.bot_data["db"]
    # تفويض الملكية **قبل** أي حذف — العميل بيبعت المعرّف بس، والملكية بتتأكد server-side.
    # F-1: `allow_deleted=True` — إعادة محاولة الحذف عملية صريحة على شات ممكن يكون متشاهد
    # (deleting/uncertain)؛ الحماية الحقيقية في طبقة القاعدة (CAS الحذف)، مش في حجب القراءة.
    conv, status, message, _auth_exc = await _authorized_conversation_status(
        client, context, conversation_id, allow_deleted=True
    )
    if conv is None:
        pending_state = db.remote_deletion_state(conversation_id)
        if not (
            status is FileStatus.NOT_FOUND
            and pending_state in (db.REMOTE_DELETING, db.REMOTE_UNCERTAIN)
        ):
            await _safe_edit(q, message)
            mark_explicitly_ignored(update, context)
            return
    try:
        result = await deletion.delete_conversation_remote(client, db, conversation_id)
    except sqlite3.Error as exc:
        log.exception("تعذّر حذف الشات %s", conversation_id)
        # OHB2-MANUAL-POLLING-OUTCOME: الفشل المُبتلَع (بنعرض رسالة ونرجع عاديًّا) لازم
        # يتسجّل كفشل ⇒ مايتقبلش كنجاح.
        record_update_failure(update, context, exc)
        await _safe_edit(q, "تعذّر الحذف دلوقتي (خطأ مؤقت في قاعدة البيانات). جرّب تاني.")
        return
    # نجاح الحذف (المؤكّد) ⇒ ترتيب/محتوى القايمة اتغيّر ⇒ نبطّل كاش القايمة (زي البرومت/
    # بدء الشات). مابنبطّلوش في حالات الفشل/النتيجة المجهولة (الشات ممكن لسه بعيدًا).
    if result.status == deletion.STATUS_DELETED:
        context.bot_data.pop("list_cache", None)
    await _safe_edit(
        q,
        result.message,
        reply_markup=kb.main_menu(_mini_app_url(context)),
    )
    if result.status == deletion.STATUS_DELETED:
        mark_durable_completed(update, context)
    elif result.status == deletion.STATUS_FAILED:
        mark_ambiguous_external(update, context, "delete_confirmed_remote_failed")
    else:
        mark_ambiguous_external(update, context, "delete_result_pending")


async def show_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        # OHB2-MANUAL-POLLING-HANDLER-OUTCOME: رفض تفويض مقصود ⇒ نتيجة صريحة.
        _authorization_ignored(update, context)
        return
    conversation_id = q.data.split(":", 1)[1]
    # OHB2-09-06: تفويض الشات عبر نفس عقد FileService (ملكية + فشل مغلق) قبل أي عرض.
    # OHB2-STAGE4-F1: نستخدم المسار المفصّل عشان نفرّق بين **فشل تشغيلي** (5xx/429/مهلة/
    # انقطاع) و**رفض نهائي مؤكّد** (مش موجود/متشاهد/غير مصرّح). قبل كده كان الاتنين
    # بيتسجّلوا `explicitly_ignored` مؤهّل ⇒ تحديث عرض فاشل تشغيليًّا كان بيتقبل كأنه اتعالج.
    conv, status, message, auth_exc = await _authorized_conversation_status(
        context.bot_data["client"], context, conversation_id
    )
    if conv is None:
        await _safe_edit(q, message)
        # OHB2-STAGE4-F1: الفشل التشغيلي (5xx/429/بلا كود) ⇒ فشل عابر **غير مؤهّل**
        # (fail-closed) — نفس سياسة open/copy/full. الحدّ مايتقدّمش فوقه، وإعادة التسليم
        # بعد التعافي تنفّذ تاني. ممنوع يتحوّل لتجاهل/نجاح (وده كان عيب F1).
        if status is FileStatus.UPSTREAM_ERROR and not _is_expected_upstream_rejection(auth_exc):
            mark_operational_failure(update, context, "show_status_upstream_failure")
            return
        # رفض نهائي مؤكّد (مش موجود/متشاهد/غير مصرّح) ⇒ نتيجة صريحة مؤهّلة للإقرار (مفيش
        # نية دائمة، زي باقي مسارات الرفض) ⇒ الحدّ يتقدّم ⇒ مفيش حجب أبدي.
        mark_explicitly_ignored(update, context)
        return
    lines = [
        f"العنوان: {conv.get('title') or 'بدون عنوان'}",
        f"الحالة: {state_label(conv.get('execution_status'))}",
        f"الـ sandbox: {conv.get('sandbox_status') or 'غير معروف'}",
    ]
    link = pr_url(conv)
    if link:
        lines.append(f"الـ PR: {link}")
    # OHB2-SW-05: لازم ناخد بالنا من القيمة الراجعة — العرض ده هو المحتوى الوحيد اللي
    # المستخدم طلبه، ففشل عرضه (False) لازم يتسجّل صريح بدل ما نرجّع وكأننا نجحنا.
    if not await _edit_or_send(
        q, "\n".join(lines), q.message.chat_id, context.bot,
        reply_markup=kb.conversation_actions(conversation_id),
    ):
        log.warning("تعذّر عرض حالة الشات %s (فشل تعديل/إرسال تيليجرام).", conversation_id)
        mark_display_failed(update, context, "show_status_display_failed")
        return
    # OHB2-PLAN-01-STAGE4: العرض اتحقق فعلاً (اتعدّلت الرسالة أو اتبعتت من جديد) ⇒ مسار
    # قراءة/تنقّل ناجح (مفيش نية دائمة) ⇒ نتيجة صريحة مؤهّلة، زي باقي مسارات العرض
    # (open_conversation/copy_reply/…). بدونها كان التحديث الناجح يفضل **بلا نتيجة**
    # (غير مؤهّل) ⇒ حجب fail-closed للحدّ من غير سبب.
    mark_explicitly_ignored(update, context)


async def show_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        # OHB2-MANUAL-POLLING-HANDLER-OUTCOME: رفض تفويض مقصود ⇒ نتيجة صريحة.
        _authorization_ignored(update, context)
        return
    conversation_id = q.data.split(":", 1)[1]
    # OHB2-09-A2-02: نفس عقد ملكية الشات قبل قراءة المقاييس (بدل get_conversations الخام).
    # OHB2-STAGE4-F1: نفس منطق show_status — مسار مفصّل للتفريق بين الفشل التشغيلي
    # (5xx/429/مهلة/انقطاع) والرفض النهائي المؤكّد (مش موجود/متشاهد/غير مصرّح).
    conv, status, message, auth_exc = await _authorized_conversation_status(
        context.bot_data["client"], context, conversation_id
    )
    if conv is None:
        await _safe_edit(q, message)
        # OHB2-STAGE4-F1: الفشل التشغيلي ⇒ `failed_transient` غير مؤهّل (fail-closed)،
        # ممنوع يتحوّل لتجاهل/نجاح. رفض نهائي مؤكّد ⇒ `explicitly_ignored` مؤهّل.
        if status is FileStatus.UPSTREAM_ERROR and not _is_expected_upstream_rejection(auth_exc):
            mark_operational_failure(update, context, "show_cost_upstream_failure")
            return
        mark_explicitly_ignored(update, context)
        return
    # OHB2-SW-05: نفس منطق show_status — فشل عرض التكلفة يتسجّل بدل ما يتجاهله الكود.
    if not await _edit_or_send(
        q, format_cost(conv.get("metrics")), q.message.chat_id, context.bot,
        reply_markup=kb.conversation_actions(conversation_id),
    ):
        log.warning("تعذّر عرض تكلفة الشات %s (فشل تعديل/إرسال تيليجرام).", conversation_id)
        mark_display_failed(update, context, "show_cost_display_failed")
        return
    # OHB2-PLAN-01-STAGE4: نفس منطق show_status — نجاح العرض ⇒ نتيجة صريحة مؤهّلة.
    mark_explicitly_ignored(update, context)


async def export_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        # OHB2-MANUAL-POLLING-HANDLER-OUTCOME: رفض تفويض مقصود ⇒ نتيجة صريحة.
        _authorization_ignored(update, context)
        return
    conversation_id = q.data.split(":", 1)[1]
    client = context.bot_data["client"]
    # OHB2-09-A2-01: تفويض على مستوى الشات **قبل أي تنزيل** — نفس عقد FileService
    # (المعرّف + هوية المالك من /users/me + `created_by_user_id`، وفشل مغلق). بنستخدم
    # نفس خدمة الملفات المشتركة عشان مايبقاش فيه نسخة تانية من منطق التفويض.
    conv, message = await _authorized_conversation(client, context, conversation_id)
    if conv is None:
        log.info("export: رفض تفويض الشات (ref=%s)", conversation_id)
        await _safe_edit(q, message)
        mark_explicitly_ignored(update, context)
        return
    try:
        data = await client.export_conversation(conversation_id)
    except ResponseTooLargeError:
        # OHB2-09-06: التصدير محدود؛ عدّى الحد ⇒ رسالة صريحة (مش خطأ عام)، مفيش مستند.
        await _safe_edit(q, "التصدير كبير أوي للتنزيل الآمن. جرّب شات أصغر.")
        mark_explicitly_ignored(update, context)
        return
    except ApiError as exc:
        await _safe_edit(q, error_text(exc))
        # فشل التصدير الخارجي المُبتلَع ⇒ نتيجة **غامضة** (مايتحسبش نجاح/تجاهل).
        mark_ambiguous_external(update, context, "export_upstream_failed")
        return
    buffer = io.BytesIO(data)
    await context.bot.send_document(
        chat_id=q.message.chat_id,
        document=InputFile(buffer, filename=f"conversation-{conversation_id[:8]}.zip"),
    )
    mark_explicitly_ignored(update, context)


async def list_files(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        # OHB2-MANUAL-POLLING-HANDLER-OUTCOME: رفض تفويض مقصود ⇒ نتيجة صريحة.
        _authorization_ignored(update, context)
        return
    parts = q.data.split(":")
    if len(parts) < 2:
        await _safe_edit(q, _FILES_EXPIRED)
        mark_explicitly_ignored(update, context)
        return
    conversation_id = parts[1]
    # أزرار قديمة (بدون gen) أو صفحة مش رقم ⇒ نتجاهلها بأمان برسالة ودّية.
    try:
        page = int(parts[-1])
    except ValueError:
        await _safe_edit(q, _FILES_EXPIRED)
        mark_explicitly_ignored(update, context)
        return
    # OHB2-09-06: عبر FileService المشترك (تفويض الملكية + allowlist للمسارات الآمنة).
    listing = await _files_service(context).list_files(conversation_id)
    if listing.status is not FileStatus.OK:
        await _safe_edit(q, file_status_message(listing.status, listing.error))
        if listing.status is FileStatus.UPSTREAM_ERROR:
            # فشل upstream ⇒ نتيجة غامضة (غير مؤهّلة).
            mark_ambiguous_external(update, context, "files_listing_upstream_error")
        else:
            mark_explicitly_ignored(update, context)
        return
    files = list(listing.files)
    if not files:
        await _safe_edit(q, "ما فيهاش ملفات.", reply_markup=kb.conversation_actions(conversation_id))
        mark_explicitly_ignored(update, context)
        return
    # نخزّن القايمة عشان الـ callback data (حد 64 بايت) ما يشيلش المسار الكامل.
    # ذاكرة مؤقتة محدودة (LRU) مع نسخة لكل شات: أي زر قديم (نسخة أقدم/اتشال) بيرجّع «مش موجود».
    gen = _file_cache(context).put(conversation_id, files)
    start = page * FILES_PAGE_SIZE
    chunk = files[start : start + FILES_PAGE_SIZE]
    has_more = len(files) > start + FILES_PAGE_SIZE
    await _safe_edit(
        q,
        f"ملفات الشات (صفحة {page + 1}):",
        reply_markup=kb.files_menu(conversation_id, chunk, start, page, has_more, gen),
    )
    mark_explicitly_ignored(update, context)


async def show_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        # OHB2-MANUAL-POLLING-HANDLER-OUTCOME: رفض تفويض مقصود ⇒ نتيجة صريحة.
        _authorization_ignored(update, context)
        return
    try:
        _, conversation_id, gen_raw, index_raw = q.data.split(":", 3)
        gen, index = int(gen_raw), int(index_raw)
    except ValueError:
        await _safe_edit(q, _FILES_EXPIRED)
        mark_explicitly_ignored(update, context)
        return
    # النسخة والاتشاف لازم يطابقوا الحالة الحالية للذاكرة: أي زر قديم (نسخة أقدم)، أو
    # ملف اتشال/اتغير، أو شات مش موجود ⇒ «مش موجود» من غير أي كشف لمحتوى الشات.
    found = _file_cache(context).get(conversation_id, gen)
    if found is None:
        await _safe_edit(q, _FILE_MISSING)
        mark_explicitly_ignored(update, context)
        return
    files, _ = found
    if index >= len(files):
        await _safe_edit(q, _FILE_MISSING)
        mark_explicitly_ignored(update, context)
        return
    path = files[index]
    # OHB2-09-06: قراءة **محدودة** عبر FileService (allowlist + حد صلب + تصنيف نص)،
    # مش `client.read_file` غير المحدود. يمنع تحميل ملف ضخم في الذاكرة.
    content = await _files_service(context).read_preview(conversation_id, path)
    if content.status is not FileStatus.OK:
        # ثنائي/ترميز غير مدعوم/كبير/مش موجود/غير مصرّح ⇒ رسالة واضحة بدل محتوى مشوّه.
        await _safe_edit(q, file_status_message(content.status, content.error))
        if content.status is FileStatus.UPSTREAM_ERROR:
            mark_ambiguous_external(update, context, "file_preview_upstream_error")
        else:
            mark_explicitly_ignored(update, context)
        return
    body = content.text or ""
    name = path.rsplit("/", 1)[-1] or "file.txt"
    if content.truncated:
        body += "\n\n… (المعاينة مقصوصة — الملف أكبر من حد العرض الآمن.)"
    buffer = io.BytesIO(body.encode("utf-8"))
    await context.bot.send_document(
        chat_id=q.message.chat_id, document=InputFile(buffer, filename=name)
    )
    mark_explicitly_ignored(update, context)


async def reply_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        # OHB2-MANUAL-POLLING-HANDLER-OUTCOME: رفض تفويض مقصود ⇒ نتيجة صريحة.
        _authorization_ignored(update, context)
        return
    conversation_id = q.data.split(":", 1)[1]
    db = context.bot_data["db"]
    # OHB2-09-A2-02/B2-06-04: تفويض ملكية الشات **قبل** أي توجيه لبرومت — نفس عقد
    # باقي مسارات الشات (ملفات/حالة/تفاصيل/تصدير). كده مايتفتحش توجيه برومت لشات
    # مش مملوك (فشل مغلق عند غياب/عدم تطابق المالك).
    conv, message = await _authorized_conversation(
        context.bot_data["client"], context, conversation_id
    )
    if conv is None:
        await _safe_edit(q, message)
        mark_explicitly_ignored(update, context)
        return
    db.set_awaiting(update.effective_user.id, conversation_id, "reply")
    await _safe_edit(
        q,
        "ابعت البرومت اللي عايز تبعته للشات ده دلوقتي.",
        reply_markup=kb.conversation_actions(conversation_id),
    )
    mark_durable_completed(update, context)


# OHB2-UNSUPPORTED-FILE-SAFE-REJECTION: رسالة الرفض الوحيدة للمرفقات غير المدعومة.
# نص ثابت عربي، **ما بيوعدش** بحفظ/طابور/تسليم، وبيوجّه المستخدم للنص العادي.
UNSUPPORTED_ATTACHMENT_TEXT = (
    "إرسال الملفات غير مدعوم حاليًا. "
    "يمكنك إرسال رسالتك كنص، وسيتم التعامل معها كالمعتاد."
)

# OHB2-P0-A2: نصوص رد مسار المرفقات المدعومة (بلا وعد بإرسال — الإرسال مرحلة A3/B).
ATTACHMENT_ACCEPTED_TEXT = (
    "استلمت الملف ✅ — ابعت أوامرك (النص المصاحب) خلال 15 دقيقة من أول ملف."
)
ATTACHMENT_UNSUPPORTED_TYPE_TEXT = (
    "نوع الملف ده غير مسموح. ابعت ملف نصي/مستند مدعوم، أو رسالتك كنص."
)
ATTACHMENT_TOO_LARGE_TEXT = (
    "حجم الملف كبير أوي (الحد الأقصى 3 ميجابايت). ابعت ملف أصغر."
)
ATTACHMENT_AUTH_FAILED_TEXT = (
    "مش قادر أتحقّق من صلاحية الشات دلوقتي. جرّب تاني."
)
ATTACHMENT_ERROR_TEXT = (
    "تعذّر استلام الملف دلوقتي. جرّب تاني."
)

# OHB2-P0-A3/D-27..D-30: نصوص ردّ مسار النصّ المصاحب (محلي فقط — لا وعد بإرسال بعيد).
ATTACHMENT_TEXT_RECORDED_TEXT = (
    "وصل ✅ — حفظت النصّ المصاحب مع الملفات المعلّقة."
)
ATTACHMENT_TEXT_AMBIGUOUS_TEXT = (
    "مش قادر أحدّد الملفات المقصودة بالنصّ ده. اختار الشات المطلوب وابعت الملفات والنصّ من جديد."
)
ATTACHMENT_TEXT_EXPIRED_TEXT = (
    "فاتت مهلة الملفات المعلّقة (15 دقيقة). ابعت الملفات تاني مع النصّ المصاحب."
)
# OHB2-P0-A3/D-32 (F1-1a): دفعة **غير محسومة** (نيّة/إرسال معلّق) موجودة ⇒ النصّ محجوب.
ATTACHMENT_TEXT_UNRESOLVED_TEXT = (
    "فيه ملفات معلّقة لسه بتتجهّز للنصّ ده. استنّى شويّة وجرّب تاني، أو افتح شات جديد."
)


def _attachment_display_name(message) -> str | None:
    """اسم الملف المعروض من رسالة تيليجرام (مستند: `file_name`، وإلا None).

    **بيانات وصفية غير موثوقة** — A1 بيطبّعها ويخزّنها كنص وصفة بس (عمرها ما تُستخدم
    كمسار). الصور/الصوت/الفيديو مالهاش اسم ⇒ None.
    """
    document = getattr(message, "document", None)
    if document is not None:
        return getattr(document, "file_name", None)
    return None


def _attachment_declared_size(message) -> int | None:
    """الحجم المُعلَن غير الموثوق من رسالة تيليجرام (`file_size`)، أو None.

    A2 بيطبّعه (`normalize_declared_size`) قبل تمريره لـ A1؛ الحجم الفعلي المُتدفّق
    بيفضل مرجعي في A1.
    """
    for attr in ("document", "audio", "video", "voice", "video_note", "animation"):
        obj = getattr(message, attr, None)
        if obj is not None and getattr(obj, "file_size", None) is not None:
            return obj.file_size
    return None


def _attachment_file_id(message) -> str | None:
    """`file_id` لأكبر ملف في الرسالة (مستند/صور/وسائط)، أو None لو مش متاح."""
    document = getattr(message, "document", None)
    if document is not None and getattr(document, "file_id", None):
        return document.file_id
    photo = getattr(message, "photo", None)
    if photo:
        # آخر عنصر = أكبر مقاس (ترتيب تيليجرام).
        return getattr(photo[-1], "file_id", None)
    for attr in ("audio", "video", "voice", "video_note", "animation"):
        obj = getattr(message, attr, None)
        if obj is not None and getattr(obj, "file_id", None):
            return obj.file_id
    return None


def _attachment_service(context: ContextTypes.DEFAULT_TYPE):
    from .attachments import AttachmentService, StagingStore

    db = context.bot_data["db"]
    store = context.bot_data.get("attachment_store")
    if store is None:
        store = StagingStore(db, context.bot_data["config"].db_path)
        context.bot_data["attachment_store"] = store
    return AttachmentService(db, store, context.bot_data["client"], _identity_cache(context))


async def _download_attachment_chunks(context, file_id: str):
    """مُكرِّر بايتات الملف من تيليجرام (مقيّد بحجم A1 أثناء الكتابة).

    `download_to_memory` بتقرا الملف كامل في الذاكرة (سقف PTB 20MB)؛ A1 بيكتب بحد
    3 MiB فبيرفض أي ملف أكبر أثناء الكتابة (قبل أي تجاوز فعلي للقرص بكتير).
    """
    tg_file = await context.bot.get_file(file_id)
    buffer = io.BytesIO()
    await tg_file.download_to_memory(buffer)
    return iter([buffer.getvalue()])


async def handle_attachment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """OHB2-P0-A2: قبول آمن لمرفق مدعوم — ربط بمستخدم+محادثة+دفعة، `T0` عند أول ملف.

    المدخل غير موثوق بالكامل. التسلسل (fail-closed):
    - التفويض (`_guard`) ⇒ مستخدم مالك في محادثة خاصة.
    - محادثة صريحة مفتوحة (`route`) ⇒ بدونها نرفض (مفيش توجيه = مفيش محادثة مختارة،
      ومفيش إنشاء شات جديد كبديل — البند 6 في R4).
    - تفويض ملكية المحادثة + شاهد الحذف (fail closed) **قبل** أي قبول دائم.
    - الرد **بعد** كتابة النية الدائمة (row-first) ⇒ فشل الرد = فشل مُسجّل (مش نجاح كاذب).

    مفيش إرسال بعيد (A3/B)، ومفيش إنشاء شات، ومفيش لمس لمسار النص.
    """
    if not await _guard(update, context):
        return
    message = update.message
    telegram_id = update.effective_user.id
    db = context.bot_data["db"]
    update_id = _update_id(update)

    # محادثة صريحة مفتوحة: مفيش توجيه ⇒ مفيش محادثة مختارة ⇒ رفض (مفيش fallback).
    conversation_id, kind, _title, _at = db.awaiting_state(telegram_id)
    if kind != "route" or not conversation_id:
        try:
            await message.reply_text(
                "افتح شات الأول (من القائمة) وابعت الملف جواه، عشان نعرف نبعته فين."
            )
        except Exception as exc:  # noqa: BLE001 — فشل الرد ⇒ فشل مُسجّل، مش نجاح صامت
            record_update_failure(update, context, exc)
            raise
        mark_explicitly_ignored(update, context)
        return

    file_id = _attachment_file_id(message)
    display_name = _attachment_display_name(message)
    declared_size = _attachment_declared_size(message)
    if not file_id:
        # رسالة مرفق بلا ملف قابل للتنزيل ⇒ رفض آمن (بلا قبول دائم).
        try:
            await message.reply_text(ATTACHMENT_UNSUPPORTED_TYPE_TEXT)
        except Exception as exc:  # noqa: BLE001
            record_update_failure(update, context, exc)
            raise
        mark_explicitly_ignored(update, context)
        return

    from .attachments import AcceptOutcome

    service = _attachment_service(context)

    async def _chunks_factory():
        return await _download_attachment_chunks(context, file_id)

    now = datetime.now(timezone.utc)
    try:
        result = await service.accept(
            telegram_id=telegram_id,
            conversation_id=conversation_id,
            display_name=display_name,
            declared_size=declared_size,
            update_id=update_id,
            now=now,
            chunks_factory=_chunks_factory,
        )
    except Exception as exc:  # noqa: BLE001 — فشل غير متوقّع ⇒ فشل مُسجّل (مش نجاح كاذب)
        record_update_failure(update, context, exc)
        raise

    # اختيار الرسالة حسب النتيجة. الرد **بعد** النية الدائمة (row-first).
    stage_value = result.stage.value if result.stage is not None else None
    if result.outcome is AcceptOutcome.STORED:
        reply = ATTACHMENT_ACCEPTED_TEXT
    elif result.outcome is AcceptOutcome.ACCEPTED:
        # اتقبل بثبات بس البايتات ماتخزّنتش (حجم/نوع فعلي) ⇒ نقول الحقيقة للمستخدم.
        if stage_value == "rejected_size":
            reply = ATTACHMENT_TOO_LARGE_TEXT
        elif stage_value in ("rejected_type", "rejected_name"):
            reply = ATTACHMENT_UNSUPPORTED_TYPE_TEXT
        else:
            reply = ATTACHMENT_ERROR_TEXT
    elif result.outcome is AcceptOutcome.REJECTED:
        if stage_value == "rejected_size":
            reply = ATTACHMENT_TOO_LARGE_TEXT
        else:
            reply = ATTACHMENT_UNSUPPORTED_TYPE_TEXT
    elif result.outcome is AcceptOutcome.AUTH_FAILED:
        reply = ATTACHMENT_AUTH_FAILED_TEXT
    elif result.outcome is AcceptOutcome.DUPLICATE:
        # إعادة تسليم لتحديث اتقبل قبل كده (حاجز التكرار group=-1 عادةً بيوقفها قبل هنا):
        # مفيش عنصر جديد ⇒ رد القبول نفسه (idempotent وصادق)، وبلا لمس النتيجة الدائمة
        # (`duplicate_completed` اتكتبت ذرّيًّا جوّه الكتابة) — F-4.
        reply = ATTACHMENT_ACCEPTED_TEXT
    else:
        reply = ATTACHMENT_ERROR_TEXT

    try:
        await message.reply_text(reply)
    except Exception as exc:  # noqa: BLE001 — فشل الرد ⇒ فشل مُسجّل (مش نجاح كاذب)
        record_update_failure(update, context, exc)
        raise

    # الرد نجح. النتيجة الدائمة اتكتبت ذرّيًّا مع القبول (durable_intent_recorded)؛
    # مسارات الرفض بلا قبول دائم ⇒ تجاهل صريح (مؤهّل للإقرار). أي فشل تخزين بعد القبول
    # بيسيب العنصر `pending` (يتكنس في A4) — النتيجة الدائمة تفضل `durable_intent_recorded`
    # (دليل دائم موجود) فما بنكتبش فوقها.
    if result.outcome in (AcceptOutcome.REJECTED, AcceptOutcome.AUTH_FAILED):
        mark_explicitly_ignored(update, context)


async def handle_unsupported_attachment(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """يرفض المرفقات/الوسائط غير المدعومة برسالة واحدة، **بدون أي أثر جانبي**.

    المدخل غير موثوق: **ما بننزّلش** ملف (`get_file`/تنزيل)، **ما بنحفظش** ولا معرّف ملف
    ولا مسار ولا تعليق (caption)، **ما بنسجّلش** أي بيانات، **ما بنعملش** نداء OpenHands،
    **ما بننشئش** شات، **ما بنحطّش** برومت في الصندوق، **وما بنعدّلش** رسالة المستخدم.

    فشل إرسال الرد **مايتحوّلش** لنجاح كاذب: بنسجّل فشل التحديث (غير مؤهّل للإقرار) ونعيد
    رفع الاستثناء لمعالج أخطاء PTB (نفس سياسة الأخطاء القائمة). النجاح ⇒ `explicitly_ignored`
    (مفيش نية دائمة)، مثل باقي مسارات القراءة/التنقّل.
    """
    if not await _guard(update, context):
        return
    try:
        await update.message.reply_text(UNSUPPORTED_ATTACHMENT_TEXT)
    except Exception as exc:  # noqa: BLE001 — فشل الرد ⇒ فشل مُسجّل، مش نجاح صامت
        record_update_failure(update, context, exc)
        raise
    mark_explicitly_ignored(update, context)


async def handle_unmatched_update(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """الـ fallback: يسجّل `explicitly_ignored` لأي تحديث **مفيش له handler مطابق**.

    مسجَّل كـ `TypeHandler(Update)` في **آخر** group 0 (أدنى أولوية) ⇒ بيتنادى **بس** لو
    محدش قبله (ولا أي group تانية) تعامل مع التحديث (مفيش handler مطابق فعلاً).

    قواعد السلامة (D1):
    - **ما بيكتبش فوق نتيجة محفوظة**: لو التحديث شاف handler فعلي (أو معالج أخطاء) وسجّل
      نتيجة (نجاح/فشل/تجاهل/غموض) ⇒ `update_outcome` بترجّع قيمة ⇒ بنخرج فورًا.
    - **ما بيحوّلش استثناء لتجاهل**: الـ fallback ما بيتنادىش أصلًا لو handler مطابق رفع
      استثناء (PTB بيروح لمعالج الأخطاء ⇒ `record_update_failure`)، ولا بيكتب نتيجة لمفيش
      `update_id` صالح.
    - **مكرّر** (`dedupe_update` في group -1 ⇒ `ApplicationHandlerStop`) ⇒ الـ fallback ما
      بيشتغلش خالص.

    النتيجة: تحديث مفيش له handler (زي رسالة نوع مش مدعوم، أو `callback_query` بـ pattern مش
    مطابق) بيتسجّل «مُتجاهَل صريح» ⇒ **مؤهّل للإقرار** (مايحجبش الحدّ للأبد)، **بدون** أي أثر
    جانبي خارجي (مفيش إرسال، مفيش نداء OpenHands).
    """
    update_id = _update_id(update)
    db = context.bot_data.get("db") if getattr(context, "bot_data", None) else None
    if update_id is None or db is None:
        return
    try:
        if db.update_outcome(update_id) is not None:
            return  # فيه نتيجة محفوظة (نجاح/فشل/تجاهل) ⇒ ممنوع نكتب فوقها
        db.mark_update_outcome(
            update_id, outbox.now_iso(), update_outcomes.EXPLICITLY_IGNORED
        )
    except Exception as exc:  # noqa: BLE001 — تعذّر التسجيل ⇒ غير مؤهّل (آمن، fail-closed)
        log.warning(
            "تعذّر تسجيل تجاهل تحديث غير مطابق (%s): %s", update_id, type(exc).__name__
        )


async def _handle_accompanying_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """OHB2-P0-A3/D-27/D-29/D-30: يربط النصّ المصاحب بدفعة واحدة بالضبط (محلي فقط).

    ترجّع **True** لو تعاملت مع التحديث (نيّة متينة أو رفض نهائي مسجّل)، و**False** لو
    التحديث مالوش علاقة بدفعة معلّقة (يمشي لمسار البرومت العادي زي ما هو).

    السياسة (fail-closed، D-29/D-32/D-34):
    - **`NONE` مُتحقَّق** (لا دفعة ذات صلة بالمالك بعد استنفاد كل الفحوص) ⇒ False (سلوك A0/A2).
    - **دفعة غير محسومة** (`intent_recorded`/`dispatching`/`uncertain`) ⇒ **تحجب** البرومت
      العادي (فشل مغلق) — حتى لو لمحادثة أخرى (D-32). الرفض نهائي مؤهّل للإقرار.
    - **دفعة حيّة واحدة بالضبط** ⇒ نصّ **مؤهّل** (D-28) ⇒ نيّة متينة (`intent_recorded` + النصّ +
      دليل الهوية + `durable_intent_recorded`) ذرّيًّا؛ نصّ **غير مؤهّل** ⇒ `rejected_ineligible`.
    - **أكثر من دفعة حيّة**، أو **دفعة حيّة لمحادثة أخرى**، أو **لا route**، أو **route لمحادثة
      مختلفة**، أو **شاهد حذف** ⇒ **غموض ⇒ فشل مغلق**: `rejected_ineligible` (نهائي) + ردّ
      توضيحي. **مفيش** ربط بأحدث دفعة، **مفيش** استبدال محادثة، **مفيش** تحويل لبرومت عادي.
    - **دفعة `pending` منتهية** (بلا حيّة) ⇒ `rejected_ineligible` (لا إحياء/لا تحويل تلقائي).
    - **دفعة نهائية** (`delivered`/`expired`/`rejected`/`failed`) ⇒ **فشل مغلق (D-34)**:
      `TERMINAL_UNPROVEN` عند غياب دليل هوية الرسالة، و`TERMINAL_ASSOCIATED` عند وجوده ⇒ كلاهما
      `rejected_ineligible` (لا سقوط لمسار البرومت/`_send_prompt`/`outbox`، ولا تحويل/إحياء
      تلقائي). غياب دليل الهوية **ليس** دليلًا على رسالة جديدة.

    **محلي فقط:** لا نداء بعيد، ولا صفّ `outbox`، ولا إرسال. «إعادة التحقّق» (D-26) = هوية route
    + ملكية تيليجرام (المستخدم نفسه مالك الحالة والدفعة) + الربط بالضبط + صلاحية الدفعة + شاهد
    الحذف — كلها محليًّا.
    """
    message = update.message
    text = getattr(message, "text", None)
    if not isinstance(text, str):
        return False
    db = context.bot_data["db"]
    telegram_id = update.effective_user.id
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()

    # تصنيف صريح (D-32/D-34): مصدر قرار واحد. أي عطل في القاعدة ⇒ استثناء ⇒ فشل مسجَّل غير مؤهّل.
    # الهوية القانونية للرسالة تُمرَّر للتصنيف لتمييز الحالة النهائية المرتبطة عن غير المُثبَتة.
    routing = db.classify_attachment_routing(
        telegram_id,
        now_iso=now_iso,
        chat_id=getattr(update.effective_chat, "id", None),
        message_id=getattr(message, "message_id", None),
    )
    state = routing.state

    if state is AttachmentRoutingState.NONE:
        # `NONE` مُتحقَّق فقط: لا دفعة ذات صلة بالمالك ⇒ البرومت العادي كما هو (A0/A2)،
        # رَهينةً بفحوص route/الملكية/المحادثة المستقلة في `handle_text` بعده.
        return False

    if state in (
        AttachmentRoutingState.TERMINAL_ASSOCIATED,
        AttachmentRoutingState.TERMINAL_UNPROVEN,
    ):
        # OHB2-P0-A3/D-34: نصّ **مرتبط** بدفعة نهائية أو **غير مُثبَت** الارتباط بها ⇒ فشل مغلق.
        # لا سقوط لمسار البرومت/`_send_prompt`/`outbox`، ولا تحويل/إحياء/استبدال/تخمين. غياب
        # دليل الهوية **ليس** دليلًا على رسالة جديدة. رفض نهائي مؤهّل للإقرار (`REJECTED_INELIGIBLE`).
        await _reject_accompanying_text(
            update, context, ATTACHMENT_TEXT_AMBIGUOUS_TEXT, reason="terminal_unproven"
        )
        return True

    if state is AttachmentRoutingState.UNRESOLVED:
        # دفعة/دفعات غير محسومة (نيّة/إرسال معلّق) ⇒ تحجب البرومت العادي (D-32/F1-1a).
        await _reject_accompanying_text(
            update, context, ATTACHMENT_TEXT_UNRESOLVED_TEXT, reason="unresolved_batch"
        )
        return True

    if state is AttachmentRoutingState.MULTI_LIVE:
        # غموض على مستوى المستخدم (أكثر من دفعة حيّة، نفس المحادثة أو عبر محادثات) ⇒ فشل مغلق.
        await _reject_accompanying_text(
            update, context, ATTACHMENT_TEXT_AMBIGUOUS_TEXT, reason="multi_batch"
        )
        return True

    if state is AttachmentRoutingState.EXPIRED_PENDING:
        # دفعة/دفعات `pending` **منتهية** بس ⇒ لا إحياء ولا تحويل تلقائي (D-29 بند 5).
        await _reject_accompanying_text(
            update, context, ATTACHMENT_TEXT_EXPIRED_TEXT, reason="expired_batch"
        )
        return True

    # state is AttachmentRoutingState.LIVE — دفعة حيّة واحدة بالضبط.
    batch = routing.live_batches[0]
    route_cid, route_kind, _route_title, _route_at = db.awaiting_state(telegram_id)
    if (
        route_kind != "route"
        or not route_cid
        or route_cid != batch.conversation_id
    ):
        # لا route، أو route لمحادثة مختلفة عن دفعة النصّ ⇒ لا ربط/لا استبدال (فشل مغلق).
        await _reject_accompanying_text(
            update, context, ATTACHMENT_TEXT_AMBIGUOUS_TEXT, reason="route_mismatch"
        )
        return True

    # شاهد الحذف (fail-closed): شات محذوف ⇒ لا نيّة (فشل مغلق، بلا تفصيل).
    try:
        if db.is_deleted(batch.conversation_id):
            await _reject_accompanying_text(
                update, context, ATTACHMENT_TEXT_AMBIGUOUS_TEXT, reason="deleted"
            )
            return True
    except Exception as exc:  # noqa: BLE001 — تعذّر فحص الحذف ⇒ فشل مغلق مسجَّل (غير مؤهّل)
        record_update_failure(update, context, exc)
        raise

    validation = validate_accompanying_text(text)
    if not validation.eligible:
        await _reject_accompanying_text(
            update, context, ATTACHMENT_TEXT_AMBIGUOUS_TEXT,
            reason=f"text_{validation.eligibility.value}",
        )
        return True

    # نيّة محلية متينة (ذرّية). أي عطل تقني ⇒ فشل مسجَّل (غير مؤهّل)، مش رفض نهائي.
    try:
        batch_id = db.record_attachment_intent(
            batch.batch_id,
            telegram_id=telegram_id,
            conversation_id=batch.conversation_id,
            intent_text=validation.normalized,
            now=now_iso,
            update_id=_update_id(update),
            chat_id=getattr(update.effective_chat, "id", None),
            message_id=getattr(message, "message_id", None),
        )
    except Exception as exc:  # noqa: BLE001 — عطل قاعدة ⇒ فشل تقني مُسجَّل (fail-closed)
        record_update_failure(update, context, exc)
        raise

    if batch_id is None:
        # غيّر حالته/سباق حالة/تكرار تحديث ⇒ مفيش نيّة جديدة. لو التحديث اتسجّل قبل كده
        # (duplicate_completed) النتيجة موجودة ⇒ نقفل بهدوء. غير كده ⇒ رفض نهائي (fail-closed).
        uid = _update_id(update)
        if uid is not None and db.update_outcome(uid) is not None:
            return True
        await _reject_accompanying_text(
            update, context, ATTACHMENT_TEXT_AMBIGUOUS_TEXT, reason="intent_race"
        )
        return True

    # النيّة الدائمة اتكتبت (النتيجة `durable_intent_recorded` ذرّيًّا جوّه). الرد **بعد**
    # الالتزام (row-first) ⇒ فشل الرد = فشل مُسجَّل (مش نجاح كاذب).
    try:
        await message.reply_text(ATTACHMENT_TEXT_RECORDED_TEXT)
    except Exception as exc:  # noqa: BLE001 — فشل الرد ⇒ فشل مُسجَّل، مش نجاح صامت
        record_update_failure(update, context, exc)
        raise
    return True


async def _reject_accompanying_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    reply: str,
    *,
    reason: str,
) -> None:
    """D-30: يثبّت رفضًا نهائيًّا `rejected_ineligible` **قبل** ردّ أفضل-جهد واحد.

    **الترتيب:** (1) النتيجة الدائمة تُـcommit أولًا؛ (2) محاولة ردّ واحدة أفضل-جهد. لو الردّ
    فشل **بعد** الالتزام، **ما بنحوّلش** الرفض النهائي لفشل قابل لإعادة المحاولة (مفيش exactly-once
    ولا تسليم مضمون للردّ). نافذة الفشل الموثّقة: انهيار بين الالتزام والردّ ⇒ قد يُفقَد الردّ
    (القرار `rejected_ineligible` يفضل ثابتًا ومؤهّلًا للإقرار).
    """
    db = context.bot_data["db"]
    try:
        db.record_rejected_ineligible(
            now=outbox.now_iso(), update_id=_update_id(update), reason=reason
        )
    except Exception as exc:  # noqa: BLE001 — تعذّر تثبيت النتيجة ⇒ غير مؤهّل (fail-closed)
        record_update_failure(update, context, exc)
        raise
    try:
        await update.message.reply_text(reply)
    except Exception as exc:  # noqa: BLE001 — ردّ أفضل-جهد: الرفض الدائم يفضل ثابتًا
        log.warning(
            "تعذّر إرسال ردّ الرفض (%s) — النتيجة الدائمة محفوظة (best-effort، بلا exactly-once)",
            type(exc).__name__,
        )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    db = context.bot_data["db"]
    telegram_id = update.effective_user.id
    # OHB2-P0-A3/D-29: فرع النصّ المصاحب **قبل** أي مسار برومت عادي (وقبل فحص انتهاء route)
    # عشان نصّ قد يخصّ دفعة معلّقة ما يتسرّبش لمسار البرومت/الـ outbox. الفحص **محلي فقط**
    # (بلا نداء بعيد)؛ وبيرجّع True لو تعامل مع التحديث (نيّة متينة أو رفض نهائي).
    if await _handle_accompanying_text(update, context):
        return
    # P1 (OHB2-ONE-SHOT-CRASH): قراءة **بدون استهلاك**. الحالات لمرة واحدة (reply/newchat/
    # reposearch) بتتستهلك **ذرّيًا مع كتابة السجل الدائم** جوه
    # add_or_group_outbox/add_creation_job (أو consume_one_shot_awaiting لبحث المستودعات)
    # ⇒ مفيش نافذة بين استهلاك الحالة وكتابة العمل يضيع فيها البرومت لو العملية ماتت.
    # `route` مستمر (مش لمرة واحدة): بنجدّد مهلته هنا فقط.
    pending, kind, title, awaiting_at = db.awaiting_state(telegram_id)
    if kind in ("reply", "newchat", "reposearch", "route") and db.awaiting_is_expired(awaiting_at):
        # حالة منتهية: نمسحها ونبلّغ (نفس سلوك `take_awaiting` القديم، بدون استهلاك مسبق).
        db.clear_awaiting(telegram_id)
        await update.message.reply_text(
            "انتهت مهلة التوجيه (10 دقايق من آخر نشاط). افتح الشات تاني وابعت برومتك."
        )
        # البرومت **مااتنفّذش** عمدًا (الحالة منتهية) ⇒ تجاهل صريح (مفيش نية دائمة معلّقة).
        mark_explicitly_ignored(update, context)
        return
    if kind == "route" and pending:
        db.renew_awaiting(telegram_id)  # route مستمر: كل رسالة بتجدّد المهلة
    if kind in ("reply", "route") and pending:
        consume = (telegram_id, "reply") if kind == "reply" else None
        await _send_prompt(
            update, context, pending, update.message.text,
            title if kind == "route" else None, consume_awaiting=consume,
        )
    elif kind == "newchat":
        await _start_new_chat(
            update, context, pending, update.message.text,
            consume_awaiting=(telegram_id, "newchat"),
        )
    elif kind == "reposearch":
        query = update.message.text.strip()
        sent = await update.message.reply_text("اختار مستودع للشات الجديد:\nبحث: " + query)
        await _show_repos(_MessageAdapter(sent), context, page=0, query=query)
        # P1: نستهلك حالة البحث **بعد** ما القايمة تتبعت (عطل قبل كده ⇒ إعادة التسليم تعيد
        # التنفيذ؛ قايمة مكرّرة غير ضارة)، والاستهلاك + علامة «معالَج» في معاملة واحدة.
        db.consume_one_shot_awaiting(
            telegram_id, "reposearch", _update_id(update), outbox.now_iso()
        )
    else:
        # OHB2-MANUAL-POLLING-OUTCOME: مسار مُتجاهَل صريح (مفيش نية دائمة) ⇒ نتيجة
        # `explicitly_ignored` (دليل دائم ⇒ مؤهّل للإقرار، مفيش إعادة معالجة لاحقة).
        mark_explicitly_ignored(update, context)
        await update.message.reply_text("ابعت /start للقائمة، أو افتح شات عشان تبعتله برومت.")


async def cancel_route(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/cancel: يلغي أي توجيه أو انتظار معلّق."""
    if not await _guard(update, context):
        return
    context.bot_data["db"].clear_awaiting(update.effective_user.id)
    await update.message.reply_text("اتلغى التوجيه. ابعت /start للقائمة.")
    mark_durable_completed(update, context)


async def cancel_route_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        # OHB2-MANUAL-POLLING-HANDLER-OUTCOME: رفض تفويض مقصود ⇒ نتيجة صريحة.
        _authorization_ignored(update, context)
        return
    context.bot_data["db"].clear_awaiting(update.effective_user.id)
    await _safe_edit(q, "اتلغى التوجيه ✅", reply_markup=kb.main_menu(_mini_app_url(context)))
    mark_durable_completed(update, context)


async def _send_prompt(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    conversation_id: str,
    text: str,
    title: str | None = None,
    consume_awaiting: tuple[int, str] | None = None,
) -> None:
    """يسجّل البرومت في الصندوق (بثبات) قبل أي إرسال، ويرد 'وصل' فوراً."""
    if not text.strip():
        # نص فاضي/مسافات ⇒ مفيش نية دائمة ⇒ تجاهل صريح (مفيش إعادة معالجة لاحقة).
        mark_explicitly_ignored(update, context)
        return
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    # F-1: الشات المتشاهد ممنوع من أي تفاعل — نرفض **قبل** تسجيل أي برومت. مسار البوت
    # ده بينادي `reengage=True` (من غير client_ref)، واللي طبقة القاعدة بتعتبره إعادة
    # تفاعل صريح (بيشيل الشاهد). فلو الشات اتحذف محليًا بعد ما التوجيه اتفتح (سباق)،
    # لازم نرفض هنا بدل ما نحيي الشات — ده فرض F-1 على مسار الإرسال.
    # SW-01: «متشاهد» بتتقرّر من **نجاح** القراءة بس. أي فشل قراءة (عابر بعد استنفاد
    # المحاولات المحدودة، أو دائم) **بيطلع** للمستدعي ⇒ مفيش رسالة حذف كاذبة، ومفيش رجوع
    # عادي كأن البرومت اتحفظ. الفشل العابر (BUSY/LOCKED) بس هو اللي بيُعاد محدودًا.
    deleted = await _is_deleted_with_retry(db, conversation_id)
    if deleted:
        await update.message.reply_text(
            "الشات ده اتحذف — مش ممكن نبعت له رسايل. افتح شات تاني."
        )
        mark_explicitly_ignored(update, context)
        return
    # نسجّل 'pending' قبل ما نبدأ أي إرسال، عشان البرومت مايضيعش لو العملية اتقطعت.
    # القرار 2: لو فيه برومت لنفس الوجهة اتسجّل خلال 1.5 ثانية، بيتجمّع معاه في سجل واحد.
    # P1: بنمرّر `update_id` عشان تسجيل «معالَج» يحصل **ذرّيًا مع** كتابة السجل الدائم (نفس
    # المعاملة) ⇒ لو العملية ماتت قبل الكتابة، الحاجز مايتسجّلش ⇒ إعادة التسليم بتنفّذ (مفيش
    # فقد)؛ ولو اتكتب، إعادة التسليم مكرّرة ⇒ تتخطّى (مفيش ازدواج). القيمة 0 معناها إن
    # التحديث ده اتسجّل للتوّ (فوز بسباق تزامن) ⇒ مانبعثش تأكيد كاذب، اللي فاز بيتأكد.
    out_id = db.add_or_group_outbox(
        conversation_id, chat_id, text, outbox.now_iso(), reengage=True,
        update_id=_update_id(update), consume_awaiting=consume_awaiting,
    )
    if out_id == 0:
        # فوز بسباق تزامن: الفائز سجّل النتيجة الدائمة ذرّيًا؛ مفيش نتيجة تانية هنا
        # (غياب النتيجة = غير مؤهّل = آمن).
        return
    # TASK 55 (C): ترتيب القايمة بيتغيّر بعد البرومت ⇒ نبطّل كاش القايمة.
    context.bot_data.pop("list_cache", None)
    # تأكيد الحفظ بيذكر الشات المستهدف (القرار 1) عشان رسالة ماتروحش لشات غلط من غير ما تلاحظ.
    ack = "وصل ✅" if not title else f"وصل ✅ ← «{title[:40]}»"
    await update.message.reply_text(ack)
    worker = context.bot_data.get("outbox_worker")
    if worker is not None:
        # worker واحد مالك؛ بنوقّظه بدل ما نعمل task جديد لكل برومت.
        worker.wake()


async def _deliver_outbox(client, db, bot, outbox_id: int) -> None:
    await outbox.deliver_outbox(client, db, bot, outbox_id)


async def outbox_recover(app) -> None:
    await outbox.outbox_recover(app)


async def creation_recover(app) -> None:
    await outbox.creation_recover(app)


async def start_new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        # OHB2-MANUAL-POLLING-HANDLER-OUTCOME: رفض تفويض مقصود ⇒ نتيجة صريحة.
        _authorization_ignored(update, context)
        return
    context.bot_data["db"].clear_awaiting(update.effective_user.id)  # تنقّل = خروج من أي توجيه
    await _show_repos(q, context, page=0, query="", user_id=update.effective_user.id)
    mark_explicitly_ignored(update, context)


_NAV_EXPIRED = "القايمة دي انتهت، افتح «شات جديد» من القائمة تاني."
_FILES_EXPIRED = "قايمة الملفات دي قديمة، افتح «الملفات» من الشات تاني."
_FILE_MISSING = "الملف مش موجود، افتح قايمة الملفات تاني."


def _repo_nav(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> dict:
    return context.bot_data.setdefault("repo_nav", {}).get(user_id) or {}


async def repos_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        # OHB2-MANUAL-POLLING-HANDLER-OUTCOME: رفض تفويض مقصود ⇒ نتيجة صريحة.
        _authorization_ignored(update, context)
        return
    try:
        _, gen_raw, page_raw = q.data.split(":", 2)
        gen, page = int(gen_raw), int(page_raw)
    except ValueError:
        await _safe_edit(q, _NAV_EXPIRED, reply_markup=kb.main_menu(_mini_app_url(context)))
        mark_explicitly_ignored(update, context)
        return
    nav = _repo_nav(context, update.effective_user.id)
    if nav.get("gen") != gen:  # زر من قايمة أقدم
        await _safe_edit(q, _NAV_EXPIRED, reply_markup=kb.main_menu(_mini_app_url(context)))
        mark_explicitly_ignored(update, context)
        return
    await _show_repos(q, context, page=page, query=nav.get("query", ""), user_id=update.effective_user.id)
    mark_explicitly_ignored(update, context)


async def repo_search_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        # OHB2-MANUAL-POLLING-HANDLER-OUTCOME: رفض تفويض مقصود ⇒ نتيجة صريحة.
        _authorization_ignored(update, context)
        return
    context.bot_data["db"].set_awaiting(update.effective_user.id, "", "reposearch")
    await _safe_edit(q, "ابعت كلمة للبحث في المستودعات.")
    mark_durable_completed(update, context)


async def _show_repos(
    q, context: ContextTypes.DEFAULT_TYPE, page: int, query: str, user_id: int | None = None
) -> None:
    client = context.bot_data["client"]
    if user_id is None:
        user_id = context.bot_data["config"].owner_id
    try:
        repos = await client.search_repositories(query=query)
    except ApiError as exc:
        await _safe_edit(q, error_text(exc))
        # OHB2-SW-07: فشل بحث المستودعات التشغيلي (5xx/429/بلا كود) ينتشر بعد عرض
        # الرسالة بدل ما يتحوّل لإتمام ناجح؛ رفض 4xx المتوقّع يرجّع عادي.
        await _raise_if_operational_api_failure(exc)
        return
    start = page * REPOS_PAGE_SIZE
    chunk = repos[start : start + REPOS_PAGE_SIZE]
    if not chunk:
        await _safe_edit(
            q,
            "ما لقيتش مستودعات. تقدر تبدأ شات بدون مستودع.",
            reply_markup=kb.repos_empty_menu(),
        )
        return
    # الأسماء الكاملة والبحث بيتخزّنوا هنا؛ الأزرار بتحمل رقم النسخة والفهرس بس (حد 64 بايت).
    gen = context.bot_data["repo_gen"] = context.bot_data.get("repo_gen", 0) + 1
    context.bot_data.setdefault("repo_nav", {})[user_id] = {
        "gen": gen,
        "query": query,
        "names": [r.get("full_name") or "" for r in repos],
    }
    has_more = len(repos) > start + REPOS_PAGE_SIZE
    title = "اختار مستودع للشات الجديد:" + (f"\nبحث: {query}" if query else "")
    await _safe_edit(
        q, title, reply_markup=kb.repositories_menu(chunk, page, has_more, gen, start=start)
    )


async def pick_repo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        # OHB2-MANUAL-POLLING-HANDLER-OUTCOME: رفض تفويض مقصود ⇒ نتيجة صريحة.
        _authorization_ignored(update, context)
        return
    try:
        _, gen_raw, idx_raw = q.data.split(":", 2)
        gen, idx = int(gen_raw), int(idx_raw)
    except ValueError:
        await _safe_edit(q, _NAV_EXPIRED, reply_markup=kb.main_menu(_mini_app_url(context)))
        mark_explicitly_ignored(update, context)
        return
    nav = _repo_nav(context, update.effective_user.id)
    names = nav.get("names") or []
    if nav.get("gen") != gen or not 0 <= idx < len(names) or not names[idx]:
        await _safe_edit(q, _NAV_EXPIRED, reply_markup=kb.main_menu(_mini_app_url(context)))
        mark_explicitly_ignored(update, context)
        return
    repo = names[idx]
    context.bot_data["db"].set_awaiting(update.effective_user.id, repo, "newchat")
    await _safe_edit(q, f"المستودع: {repo}\nابعت البرومت اللي عايز تبدأ بيه الشات (بعد 10 دقايق من غير رد هتتلغي).")
    mark_durable_completed(update, context)


async def new_chat_no_repo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """شات جديد من غير مستودع (المهمة OHB2: إنشاء شات بمستودع أو بدونه)."""
    q = update.callback_query
    await q.answer()
    if not _allowed(update, context.bot_data["config"]):
        # OHB2-MANUAL-POLLING-HANDLER-OUTCOME: رفض تفويض مقصود ⇒ نتيجة صريحة.
        _authorization_ignored(update, context)
        return
    context.bot_data["db"].set_awaiting(update.effective_user.id, None, "newchat")
    await _safe_edit(
        q,
        "شات من غير مستودع.\nابعت البرومت اللي عايز تبدأ بيه الشات (بعد 10 دقايق من غير رد هتتلغي).",
    )
    mark_durable_completed(update, context)


async def _start_new_chat(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    repo: str | None,
    text: str,
    consume_awaiting: tuple[int, str] | None = None,
) -> None:
    if not text.strip():
        mark_explicitly_ignored(update, context)
        return
    db = context.bot_data["db"]
    chat_id = update.effective_chat.id
    # نسجّل طلب الشات الجديد (بثبات) قبل أي POST بدء، عشان مايضيعش لو العملية اتقطعت.
    # P1: `update_id` ⇒ تسجيل «معالَج» **ذرّيًا مع** كتابة السجل الدائم (نفس المعاملة).
    # P1: `consume_awaiting` ⇒ استهلاك حالة `newchat` **في نفس المعاملة** (مفيش نافذة فقد).
    # القيمة 0 معناها إن نفس التحديث اتسجّل للتوّ (فوز بسباق تزامن) ⇒ مانبدأش شات تاني
    # ولا نأكّد تأكيد كاذب.
    job_id = db.add_creation_job(
        chat_id, repo, text, outbox.now_iso(),
        update_id=_update_id(update), consume_awaiting=consume_awaiting,
    )
    if job_id == 0:
        # فوز بسباق تزامن: الفائز سجّل النتيجة ذرّيًا؛ مفيش نتيجة تانية هنا.
        return
    await update.message.reply_text("وصل ✅ جاري بدء شات جديد.")
    worker = context.bot_data.get("creation_worker")
    if worker is not None:
        worker.wake()


async def _create_chat(context: ContextTypes.DEFAULT_TYPE, chat_id: int, repo: str | None, text: str) -> None:
    """مسار متزامن مباشر (للاستخدام من الاختبارات): يسجّل job وينفّذه فوراً.

    (الحماية الذرّية لحدّ الإلغاء بتحصل جوه `_start_conversation`: CAS 'pending'/'claimed'
    ⇒ 'starting' قبل الـ POST، فأي شطب متزامن يوقف الإرسال الفعلي.)
    """
    client = context.bot_data["client"]
    db = context.bot_data["db"]
    bot = context.bot
    job_id = db.add_creation_job(chat_id, repo, text, outbox.now_iso())
    job = db.get_creation_job(job_id)
    await outbox._start_conversation(
        client, db, bot, job, context.bot_data["config"].openhands_base_url
    )
    # TASK 55 (C): بعد نجاح بدء الشات، ترتيب القايمة اتغيّر ⇒ نبطّل كاش القايمة.
    context.bot_data.pop("list_cache", None)


# ------------------------------------------------ manual outbox reconciliation
# أوامر المالك فقط لمراجعة/حل سجلات الصندوق الغامضة. كلها بتمر بـ _guard أولاً.
#
# مرجع السجل لازم يحدّد النوع صراحةً: "prompt:<id>" أو "creation:<id>". السبب إن
# جدولي outbox و creation_jobs معرّفاتهم الرقمية ممكن تتقاطع (1 في الاتنين)، فمرجع
# رقمي مجرّد كان يقدر يختار السجل الغلط. المرجع لازم يحل لجدول واحد وسجل واحد بس،
# وأي مرجع ناقص/غير صالح/غامض بيفشل مقفول (fail closed) من غير أي تغيير في الحالة.
_TERMINAL_OUTBOX = {"sent", "failed", "discarded"}
_TERMINAL_CREATION = {"done", "failed", "discarded"}

_REF_TYPES = {
    "prompt": ("outbox", "برومت"),
    "creation": ("creation", "طلب شات"),
}


def _safe_ts(value: str | None) -> str:
    """طابع زمني آمن للعرض (تاريخ + ساعة بدون كسور، وبدون أي بيانات حساسة)."""
    if not value:
        return "?"
    text = str(value).replace("T", " ")
    return text[:16]


def _parse_ref(token: str | None) -> tuple[str, int] | None:
    """يحلّل مرجع "<type>:<id>" لـ (نوع، معرّف). None لو ناقص/غير صالح/غامض.

    - النوع لازم يكون بالضبط "prompt" أو "creation" (بدون اختلاف حالة).
    - المعرّف لازم صحيح موجب.
    - أي مرجع رقمي مجرّد (بدون نوع) مرفوض عشان مايختارش جدول بالغلط.
    """
    if not token:
        return None
    raw = token.strip()
    if ":" not in raw:
        return None
    type_raw, _, id_raw = raw.partition(":")
    if type_raw not in _REF_TYPES:
        return None
    id_raw = id_raw.strip()
    if not id_raw.isdigit():
        return None
    value = int(id_raw)
    if value <= 0:
        return None
    return (type_raw, value)


def _get_record(db, ref: tuple[str, int]):
    """يرجّع السجل من الجدول اللي المرجع بيحدّده بالظبط (مش بحث في الاتنين)."""
    kind, rid = ref
    if kind == "prompt":
        return db.get_outbox(rid)
    return db.get_creation_job(rid)


def _outbox_usage(name: str) -> str:
    return f"استخدام: /{name} <prompt:id | creation:id> — مثال: /{name} prompt:3"


async def outbox_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/outbox — عرض محدود للسجلات غير المنتهية (بدون نص البرومت أو أي أسرار)."""
    if not await _guard(update, context):
        return
    db = context.bot_data["db"]
    items = db.list_open_outbox()
    jobs = db.list_open_creation_jobs()
    lines = ["📤 صندوق الصادر (غير المنتهي):"]
    if not items:
        lines.append("• مفيش برومتات معلّقة.")
    for item in items:
        lines.append(
            f"• prompt:{item.id} | الحالة: {item.status} | محاولات: {item.attempts} "
            f"| آخر تحديث: {_safe_ts(item.updated_at)}"
        )
    lines.append("🆕 طلبات شات جديد (غير المنتهية):")
    if not jobs:
        lines.append("• مفيش طلبات معلّقة.")
    for job in jobs:
        lines.append(
            f"• creation:{job.id} | الحالة: {job.status} | محاولات: {job.attempts} "
            f"| آخر تحديث: {_safe_ts(job.updated_at)}"
        )
    await update.message.reply_text("\n".join(lines))
    mark_explicitly_ignored(update, context)


async def outbox_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/outbox_status <prompt:id|creation:id> — تفاصيل سجل واحد بدون نص/أسرار."""
    if not await _guard(update, context):
        return
    db = context.bot_data["db"]
    args = list(context.args or [])
    ref = _parse_ref(args[0] if args else None)
    if ref is None:
        await update.message.reply_text(_outbox_usage("outbox_status"))
        mark_explicitly_ignored(update, context)
        return
    kind, rid = ref
    record = _get_record(db, ref)  # الجدول محدد بالنوع — مفيش بحث في الاتنين
    if record is None:
        await update.message.reply_text(f"مفيش سجل بالمعرّف {kind}:{rid}.")
        mark_explicitly_ignored(update, context)
        return
    if kind == "prompt":
        await update.message.reply_text(
            f"برومت prompt:{record.id}\n"
            f"الحالة: {record.status}\n"
            f"المحادثة: {record.conversation_id}\n"
            f"محاولات: {record.attempts}\n"
            f"آخر خطأ: {record.error or '—'}\n"
            f"آخر تحديث: {_safe_ts(record.updated_at)}"
        )
        mark_explicitly_ignored(update, context)
        return
    await update.message.reply_text(
        f"طلب شات creation:{record.id}\n"
        f"الحالة: {record.status}\n"
        f"المستودع: {record.repo or '—'}\n"
        f"معرّف المهمة: {record.task_id or '—'}\n"
        f"المحادثة: {record.conversation_id or '—'}\n"
        f"محاولات: {record.attempts}\n"
        f"آخر خطأ: {record.error or '—'}\n"
        f"آخر تحديث: {_safe_ts(record.updated_at)}"
    )
    mark_explicitly_ignored(update, context)


async def outbox_discard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/outbox_discard <prompt:id|creation:id> confirm — يتخلّص من سجل (نهائي). idempotent."""
    if not await _guard(update, context):
        return
    db = context.bot_data["db"]
    args = list(context.args or [])
    ref = _parse_ref(args[0] if args else None)
    if ref is None:
        await update.message.reply_text(_outbox_usage("outbox_discard"))
        mark_explicitly_ignored(update, context)
        return
    kind, rid = ref
    label = _REF_TYPES[kind][1]
    if len(args) < 2 or args[1].strip().lower() != "confirm":
        await update.message.reply_text(
            f"تأكيد مطلوب: /outbox_discard {kind}:{rid} confirm\n"
            "ده هيعلّم السجل 'discarded' (نهائي) من غير أي إعادة إرسال."
        )
        mark_explicitly_ignored(update, context)
        return
    record = _get_record(db, ref)  # الجدول محدد بالنوع — مفيش بحث في الاتنين
    if record is None:
        await update.message.reply_text(f"مفيش سجل بالمعرّف {kind}:{rid}.")
        mark_explicitly_ignored(update, context)
        return
    terminal = _TERMINAL_OUTBOX if kind == "prompt" else _TERMINAL_CREATION
    if record.status in terminal:
        await update.message.reply_text(
            f"{label} {kind}:{rid} خلاص في حالة نهائية ({record.status}) — مفيش تغيير."
        )
        mark_explicitly_ignored(update, context)
        return
    # OHB2-N10-28C: شطب **ذرّي** مع حدّ إلغاء واضح. الشطب بيتنفّذ بس لو لسه مؤهّل قبل
    # الإرسال (pending/claimed). لو الـ POST ممكن يكون بدأ (sending/unknown) ما بنشطبش
    # وما بندّعيش إلغاء — بنبلّغ إن الإلغاء غير مؤكد ونسيب السجل للاستعلام/التسوية.
    if kind == "prompt":
        outcome = db.discard_outbox(rid, outbox.now_iso(), "اتشال يدوياً")
    else:
        outcome = db.discard_creation_job(rid, outbox.now_iso(), "اتشال يدوياً")
    if outcome == "discarded":
        log.info("discard: ref=%s:%s status=discarded", kind, rid)
        await update.message.reply_text(f"تم تعليم {label} {kind}:{rid} كـ 'discarded'.")
        mark_durable_completed(update, context)
        return
    if outcome == "not_confirmed":
        # الشطب بعد ما الـ POST ممكن يكون بدأ ⇒ مفيش ادّعاء إلغاء (C2 Case 3) — النتيجة
        # غامضة (الـ POST ممكن يكون اتنفّذ) ⇒ غير مؤهّلة.
        await update.message.reply_text(
            f"{label} {kind}:{rid} ممكن يكون بدأ الإرسال بالفعل — الإلغاء غير مؤكد.\n"
            "استعلم عن الحالة من الموقع، ولو مش متأكد استخدم /outbox_status أو /outbox_mark_sent."
        )
        mark_ambiguous_external(update, context, "outbox_discard_not_confirmed")
        return
    # بين القراءة والشطب حد تاني حسم السجل (نهائي) ⇒ مفيش تغيير.
    current = _get_record(db, ref)
    status_now = current.status if current is not None else "؟"
    await update.message.reply_text(
        f"{label} {kind}:{rid} خلاص في حالة نهائية ({status_now}) — مفيش تغيير."
    )
    mark_explicitly_ignored(update, context)


async def outbox_mark_sent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/outbox_mark_sent <prompt:id|creation:id> confirm — تأكيد المالك إن العملية الغامضة نجحت."""
    if not await _guard(update, context):
        return
    db = context.bot_data["db"]
    args = list(context.args or [])
    ref = _parse_ref(args[0] if args else None)
    if ref is None:
        await update.message.reply_text(_outbox_usage("outbox_mark_sent"))
        mark_explicitly_ignored(update, context)
        return
    kind, rid = ref
    label = _REF_TYPES[kind][1]
    if len(args) < 2 or args[1].strip().lower() != "confirm":
        await update.message.reply_text(
            f"تأكيد مطلوب: /outbox_mark_sent {kind}:{rid} confirm\n"
            "ده تأكيد منك إن العملية نجحت فعلاً (مش إثبات من OpenHands). "
            "مش هيعيد أي إرسال، بس بيقفل السجل."
        )
        mark_explicitly_ignored(update, context)
        return
    record = _get_record(db, ref)  # الجدول محدد بالنوع — مفيش بحث في الاتنين
    if record is None:
        await update.message.reply_text(f"مفيش سجل بالمعرّف {kind}:{rid}.")
        mark_explicitly_ignored(update, context)
        return
    if record.status == "unknown":
        # 'unknown' → حالة نهائية (sent/done): تفضل نهائية ومستحيل ترجع 'pending'،
        # فمفيش إعادة إرسال أو إنشاء تلقائي (at-most-once محفوظ). OHB2-N10-28C: CAS ذرّي
        # من 'unknown' بس، عشان ما نقلبش حالة أحدث حسمها حد تاني (مفيش read-then-write).
        if kind == "prompt":
            changed = db.set_outbox_status_if_in(
                rid, "sent", outbox.now_iso(), {"unknown"}, "أكّده المالك"
            )
            final = "sent"
        else:
            changed = db.set_creation_status_if_in(
                rid, "done", outbox.now_iso(), {"unknown"}, "أكّده المالك"
            )
            final = "done"
        if not changed:
            # سبقنا كاتب تاني وحسم السجل بين القراءة والكتابة ⇒ ما نغيّرش حاجة.
            current = _get_record(db, ref)
            status_now = current.status if current is not None else "؟"
            if status_now == final:
                await update.message.reply_text(
                    f"{label} {kind}:{rid} معَلّم '{final}' بالفعل — مفيش تغيير."
                )
            else:
                await update.message.reply_text(
                    f"{label} {kind}:{rid} حالته '{status_now}' — الأمر ده لـ 'unknown' بس."
                )
                mark_explicitly_ignored(update, context)
            return
        log.info("mark_sent: ref=%s:%s unknown->%s", kind, rid, final)
        await update.message.reply_text(
            f"تم تعليم {label} {kind}:{rid} كـ '{final}' (تأكيد منك — مش إثبات من OpenHands)."
        )
        mark_durable_completed(update, context)
        return
    already = "sent" if kind == "prompt" else "done"
    if record.status == already:
        await update.message.reply_text(f"{label} {kind}:{rid} معَلّم '{already}' بالفعل — مفيش تغيير.")
        mark_explicitly_ignored(update, context)
        return
    await update.message.reply_text(
        f"{label} {kind}:{rid} حالته '{record.status}' — الأمر ده لـ 'unknown' بس."
    )
    mark_explicitly_ignored(update, context)
