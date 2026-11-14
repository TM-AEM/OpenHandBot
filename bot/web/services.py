"""طبقة خدمات الـ Mini App (OHB2-06).

الهدف: واجهة عملية لقدرات OpenHandBot الموجودة **من غير تكرار منطق الأعمال**.
كل دالة هنا بتنادي نفس الطبقات اللي البوت بينادي عليها:
- `OpenHandsClient` (قراءة/إرسال لـ OpenHands Cloud).
- `Database` (نفس المالك الواحد، قراءة/كتابة).
- `bot.outbox` (نفس مسار الصندوق المتين للبرومتات والشات الجديد — مش إرسال مباشر).

الخدمة **ما بتبدأش أي worker**: بتنبّه الـ worker المالك الموجود (نفس عملية البوت)
عبر `application.bot_data`. النتيجة: مفيش ازدواج إرسال ولا مالك قاعدة بيانات تاني.
"""
from __future__ import annotations

import logging
import math
import time

from ..errors import ApiError, ResponseTooLargeError
from ..messages import get_status, pr_url, state_label, truncate
from ..openhands_client import collect_conversations
from .. import features
from .. import outbox
from .. import deletion
from .. import db as db_module
from ..db import (
    INBOX_DELETE_DELETED,
    INBOX_DELETE_MISSING,
    INBOX_PAGE_SIZE,
    MAX_PAGE,
    MAX_SQLITE_INT,
)
from ..files import (
    CONVERSATION_ERRORS,
    FILE_CONTENT_STATUSES,
    FILE_STATUS_ERRORS,
    FileService,
    FileStatus,
    IdentityCache,
    authorize_conversation,
    file_status_message,
    is_safe_workspace_path,
    is_valid_conversation_id,
)

log = logging.getLogger(__name__)

PAGE_SIZE = 10
MAX_PROMPT_CHARS = 8000
MAX_REPO_LEN = 200
# OHB2-PHASE1B: حدّ أعلى لنص الرد الكامل اللي بيتحوّل للواجهة عند «نسخ الرد الكامل».
# المعاينة العادية في التفاصيل محدودة بـ 4000 محرف؛ النسخ الكامل بياخد النص الأطول
# (محدود) عشان مايتقصّش بصريًا، مع سقف صلب يمنع تضخيم ذاكرة/رد غير محدود.
MAX_FULL_REPLY_CHARS = 100_000
# OHB2-07: معرّف العملية اللي العميل يولّده (idempotency). قاصر على حروف/أرقام/شرطة
# وشرطة سفلية، بطول محدود، عشان ما يتحوّلش لقناة حقن أو مفتاح ضخم في الذاكرة/القاعدة.
MAX_REF_LEN = 64

# OHB2-07: خرائط حالة العملية الداخلية لحالة واجهة واضحة. أي حالة مش معروفة ⇒ 'unknown'
# (fail closed: ما نأكّدش نجاح حاجة مش متأكدين منها).
_OUTBOX_STATES = {
    db_module.OUTBOX_PENDING: "pending",
    db_module.OUTBOX_CLAIMED: "pending",
    db_module.OUTBOX_SENDING: "pending",
    db_module.OUTBOX_SENT: "accepted",
    db_module.OUTBOX_FAILED: "failed",
    db_module.OUTBOX_UNKNOWN: "ambiguous",
    db_module.OUTBOX_DISCARDED: "discarded",
}
_CREATION_STATES = {
    db_module.CREATION_PENDING: "pending",
    db_module.CREATION_CLAIMED: "pending",
    db_module.CREATION_STARTING: "pending",
    db_module.CREATION_DONE: "accepted",
    db_module.CREATION_FAILED: "failed",
    db_module.CREATION_UNKNOWN: "ambiguous",
    db_module.CREATION_DISCARDED: "discarded",
}
# OHB2-09-05: الحالات النهائية للصندوق (نفس مجموعة البوت في handlers). التسوية اليدوية
# على سجل نهائي ⇒ 409 (مفيش تغيير)، عشان ما نلخبطش حالة محسومة.
_TERMINAL_OUTBOX = {db_module.OUTBOX_SENT, db_module.OUTBOX_FAILED, db_module.OUTBOX_DISCARDED}
# OHB2-N10-28C: `discard` مسموح بس للسجلات المؤهّلة **قبل الإرسال** (pending/claimed).
# لو الـ POST ممكن يكون بدأ (sending/unknown) ما بنشطبش وما بندّعيش إلغاء — بنرجّع الحالة
# الحالية بعلامة "الإلغاء غير مؤكد" (حدّ الإلغاء C2). ده يمنع ادّعاء إلغاء وهمي.
_DISCARDABLE_OUTBOX = {db_module.OUTBOX_PENDING, db_module.OUTBOX_CLAIMED}
_NOT_CONFIRMED_OUTBOX = {db_module.OUTBOX_SENDING, db_module.OUTBOX_UNKNOWN}
# OHB2-PHASE1D: نفس مجموعات الحدّ لطلب الشات الجديد (creation job) — parity مع البوت.
# الحالات النهائية: done/failed/discarded. الإلغاء (cancel/discard) مسموح **بس** في
# `pending`/`claimed` (اللي الكود بيثبت إن الـ POST لسه مابدأش). `starting`/`unknown`
# = الـ POST ممكن يكون بدأ ⇒ مفيش ادّعاء إلغاء (not_confirmed). `done` ⇒ فيه محادثة
# بعيدة، مستحيل نلغيه أو نعمل POST تاني (at-most-once محفوظ).
_TERMINAL_CREATION = {db_module.CREATION_DONE, db_module.CREATION_FAILED, db_module.CREATION_DISCARDED}
_DISCARDABLE_CREATION = {db_module.CREATION_PENDING, db_module.CREATION_CLAIMED}
_NOT_CONFIRMED_CREATION = {db_module.CREATION_STARTING, db_module.CREATION_UNKNOWN}
# OHB2-PHASE1D: وصف آمن لحدّ POST البدء (للعرض فقط؛ القرار النهائي في `reconcile_creation`).
#   not_started : الكود بيثبت إن POST البدء لسه مابدأش (pending/claimed).
#   uncertain   : POST البدء ممكن يكون بدأ ونتيجته غامضة (starting/unknown).
#   started     : POST البدء اتأكد ونجح (done) — فيه محادثة بعيدة.
#   failed      : رفض نهائي مؤكد (failed).
#   cancelled   : اتلغى قبل الإرسال (discarded).
_CREATION_POST_STATE = {
    db_module.CREATION_PENDING: "not_started",
    db_module.CREATION_CLAIMED: "not_started",
    db_module.CREATION_STARTING: "uncertain",
    db_module.CREATION_UNKNOWN: "uncertain",
    db_module.CREATION_DONE: "started",
    db_module.CREATION_FAILED: "failed",
    db_module.CREATION_DISCARDED: "cancelled",
}


def _creation_post_started(job) -> bool:
    """هل POST البدء **بدأ فعلاً** (أو ممكن يكون بدأ) لهذا الطلب؟

    `task_id` دليل قاطع: الكود بيسجّله **بس** بعد ما `client.start_conversation`
    يرجّعه (`outbox.py`)، وبيفضل محفوظ بعد التعافي (بيتحجز `claimed` بـ `RETURNING *`
    والاستعادة بترجّعه `pending`). فأي صف عليه `task_id` = الـ POST اترجع ⇒ **مستحيل**
    نعتبره "لسه مابدأش" حتى لو حالته `pending`/`claimed` (قبل الإصلاح ده كان بيدّي
    إلغاء كاذب ويحوّل شات بعيد حقيقي لـ 'discarded' من غير تسجيل conversation_id).
    """
    return bool(getattr(job, "task_id", None)) or job.status not in _DISCARDABLE_CREATION


class ValidationError(ValueError):
    """مدخل غير صالح من العميل (بترجع 400 بشكل منظّم)."""


class CodedApiError(ApiError):
    """خطأ منظّم برمز ثابت — الـ route بيحوّله لرد JSON فيه `error` = الرمز.

    بيستخدمه مسار الملفات (OHB2-09-02) وتسوية الصندوق (OHB2-09-05) عشان الردود
    تكون قابلة للقراءة آليًا (رمز ثابت) مش نص حر.
    """

    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message, status_code)
        self.code = code


# اسم قديم محفوظ للتوافق الداخلي (كان خاص بمسار الملفات).
FileApiError = CodedApiError


# خرائط حالة FileService ⇒ (رمز ثابت، حالة HTTP). BINARY/NOT_UTF8 مش أخطاء: بترجع
# 200 مع حقل status (المحتوى موجود لكن مش نص). أي حالة مش معروفة ⇒ upstream_error.
# الرسايل والرموز بقت مشتركة في bot/files.py (مصدر واحد للحقيقة مع مسار البوت).
_FILE_STATUS_ERRORS = FILE_STATUS_ERRORS
_FILE_CONTENT_STATUSES = FILE_CONTENT_STATUSES


def _require_id(value: str | None) -> str:
    """يتحقّق من معرّف الشات بشكل موحّد عبر كل مسارات الـ Mini App (F2, BATCH-C).

    قبل كده كان التحقق (مسافة/طول) أضعف من `files.is_valid_conversation_id` اللي
    بتستعمله مسارات الملفات، فمعرّف زي `a.b` كان يرجّع 404 في مسار و400 في مسار تاني.
    دلوقتي بنفرض **نفس** شكل المعرّف (حروف/أرقام/شرطة/شرطة سفلية، ≤64) هنا كمان، فكل
    المسارات بترفض المعرّف غير الصالح محليًا بنفس الرمز (400) قبل أي نداء upstream.
    """
    text = (value or "").strip()
    if not is_valid_conversation_id(text):
        raise ValidationError("معرّف غير صالح")
    return text


def _as_str(value, message: str) -> str:
    """يرجّع الحقل كنص، أو يرفضه بـ ValidationError.

    حقول JSON الخام ممكن تكون رقم/قائمة/كائن؛ `(value or "").strip()` عليها يضرب
    AttributeError (500). نفس نمط إصلاح OHB2-PHASE1D-F3، لكن في طبقة الخدمة عشان
    كل المسارات اللي بتمرّر حقول JSON تستفيد (مش مسار واحد).
    """
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValidationError(message)
    return value


def _require_text(value) -> str:
    text = _as_str(value, "النص لازم يكون نص").strip()
    if not text:
        raise ValidationError("النص مطلوب")
    if len(text) > MAX_PROMPT_CHARS:
        raise ValidationError("النص طويل أوي")
    return text


def _require_repo(value) -> str:
    text = _as_str(value, "اسم المستودع غير صالح").strip()
    if not text or len(text) > MAX_REPO_LEN:
        raise ValidationError("اسم المستودع غير صالح")
    parts = text.split("/")
    if len(parts) != 2 or not all(parts):
        raise ValidationError("اسم المستودع لازم يكون بالشكل owner/repo")
    if any(ch.isspace() for ch in text):
        raise ValidationError("اسم المستودع غير صالح")
    return text


def _optional_repo(value: str | None) -> str | None:
    """مستودع اختياري (OHB2: شات بمستودع أو بدونه).

    فاضي/غايب ⇒ None (شات بدون مستودع). لو فيه قيمة ⇒ نفس تحقق `_require_repo`
    الصارم (شكل owner/repo). كده ما بنسمحش بمستودع مشوّه، وبنسمح صريحًا ببدونه.
    """
    text = _as_str(value, "اسم المستودع غير صالح").strip()
    if not text:
        return None
    return _require_repo(text)


def _require_ref(value) -> str:
    """يتحقّق من معرّف العملية اللي العميل يولّده (idempotency) أو يرجّع فاضي."""
    text = _as_str(value, "معرّف العملية غير صالح").strip()
    if not text:
        return ""
    if len(text) > MAX_REF_LEN or not all(ch.isalnum() or ch in "-_" for ch in text):
        raise ValidationError("معرّف العملية غير صالح")
    return text


def _page_number(page) -> int:
    """يرجّع رقم الصفحة كـ int داخل `[0, MAX_PAGE]` أو يرفضه بـ ValidationError.

    AUD-04: نتحقق **قبل** أي ضرب. الرفض موحّد عبر كل مسارات الترقيم (400) — مفيش
    تكميم صامت لقيمة سالبة/ضخمة، عشان المدخل غير الصالح يبان للمستخدم بدل ما يتحوّل
    لصفحة أولى مضلّلة. القيم المسموحة (بما فيها 0 والصفحات الفاضية داخل السقف)
    بتتحفظ بنفس دلالات الترقيم القائمة.
    """
    try:
        value = int(page)
    except (TypeError, ValueError):
        raise ValidationError("رقم الصفحة غير صالح") from None
    if isinstance(page, bool) or (not isinstance(page, (int, str))):
        raise ValidationError("رقم الصفحة غير صالح")
    if value < 0 or value > MAX_PAGE:
        raise ValidationError("رقم الصفحة غير صالح")
    return value


def _page_offset(page, size: int) -> int:
    """يحوّل رقم صفحة إلى offset آمن أو يرفضه بـ ValidationError.

    AUD-04: كل مسارات الترقيم بتمرّ من هنا. بنتحقق إن `page` عدد صحيح داخل
    `[0, MAX_PAGE]` **قبل** أي ضرب، ونتأكد إن `offset = page × size` داخل نطاق
    SQLite (64-bit). كده مستحيل يوصل `offset` ضخم لـ SQLite ⇒ مفيش OverflowError/500،
    ومفيش استعلام بيتنفّذ بقيمة غير صالحة. نفس دلالة الرفض لكل المسارات (400).
    """
    value = _page_number(page)
    offset = value * int(size)
    if offset < 0 or offset > MAX_SQLITE_INT:
        raise ValidationError("رقم الصفحة غير صالح")
    return offset


def _conversation_dto(conv: dict, watched: bool) -> dict:
    status = get_status(conv)
    return {
        "id": conv.get("id") or conv.get("conversation_id") or "",
        "title": conv.get("title") or "",
        "repository": conv.get("selected_repository") or "",
        "status": status,
        "state_label": state_label(status),
        "updated_at": conv.get("updated_at") or "",
        "watched": watched,
    }


def _as_number(value):
    """رقم **محدود (finite)** أو None (OHB2-09-A2-03).

    بيرفض:
    - `bool` (نوع رقمي في بايثون لكن مش إحصائية صالحة).
    - أي حاجة مش `int`/`float`.
    - `NaN` و `+Infinity` و `-Infinity`: مش أرقام نقدية صالحة. مهم إن `json.loads`
      **بيقبلهم افتراضيًا** (`parse_constant` الافتراضي) فممكن يوصلوا من upstream،
      وكذلك `JSONResponse` عندنا مع `allow_nan=False` هيرمي لو عدّوا — فلازم نرفضهم هنا.

    بنحافظ على نوع القيمة (int يفضل int، float يفضل float) عشان ما نفقدش دقة أعداد
    صحيحة كبيرة (تحويل int ضخم لـ float بيفقد دقة أو بيرمي OverflowError).
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    # int دايماً محدود؛ بنفحص الـ float بس عشان ما نحاولش تحويل int ضخم لـ float.
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _as_int(value) -> int | None:
    n = _as_number(value)
    if n is None:
        return None
    try:
        return int(n)
    except (TypeError, ValueError, OverflowError):
        return None


def _cost_dto(conv: dict) -> dict:
    """OHB2-09-04: ملخّص تكلفة/استهلاك منظّم من حقل `metrics` (بيانات غير موثوقة).

    - `metrics` مش dict ⇒ كله فاضي (مفيش انهيار على شكل غير متوقّع).
    - `accumulated_cost` قيمة **محدودة** (int/float) أو None؛ NaN/±Infinity/bool/أي
      شكل تاني ⇒ None (مفيش تمثيل كاذب، ومفيش كسر للـ JSON serialization).
    - بنحافظ على نوع القيمة (مفيش تحويل float غير ضروري) ⇒ دقة الأعداد الصحيحة الكبيرة
      محفوظة، والقيم السالبة بتُحفظ زي ما هي (مفيش تطبيع صامت) حسب عقد upstream.
    - **العملة مش محدّدة**: العقد الموثّق (`docs/API_NOTES.md`) بيسمّي الحقل
      `accumulated_cost` **من غير** أي عملة مثبتة (لا USD ولا غيره)، فالـ API مايدّعيش
      عملة. بنحافظ على اسم العقد `accumulated_cost` (مش `cost_usd`) عشان ما ننسبش
      للقيمة وحدة نقدية غير مثبتة (OHB2-09-04-R1).
    - التوكنز أعداد صحيحة أو None.
    - بنرجّع رقم الموديل نصّي قصير (حد 200) من غير أي محتوى تاني من metrics.
    """
    metrics = conv.get("metrics")
    metrics = metrics if isinstance(metrics, dict) else {}
    usage = metrics.get("accumulated_token_usage")
    usage = usage if isinstance(usage, dict) else {}

    cost = _as_number(metrics.get("accumulated_cost"))
    model = metrics.get("model_name") or usage.get("model")
    if not isinstance(model, str) or not model.strip():
        model = None
    else:
        model = model.strip()[:MAX_REPO_LEN]

    return {
        "conversation_id": conv.get("id") or conv.get("conversation_id") or "",
        "accumulated_cost": cost,
        "model": model,
        "prompt_tokens": _as_int(usage.get("prompt_tokens")),
        "completion_tokens": _as_int(usage.get("completion_tokens")),
        "total_tokens": _as_int(usage.get("total_tokens")),
    }


# OHB2-PHASE1B: تصدير الشات من الـ Mini App بنفس صيغة البوت (zip من OpenHands) ونفس
# الحدود. اسم الملف بيتولّد من معرّف **متفوَّض عليه** (بعد التحقق)، وبيتنقّى لمجموعة
# محارف آمنة عشان مايتحوّلش لقناة حقن في الهيدر (CR/LF) أو مسار.
EXPORT_CONTENT_TYPE = "application/zip"
_EXPORT_NAME_SAFE = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
)


def export_filename(conversation_id: str) -> str:
    """اسم ملف تنزيل آمن (`conversation-<id>.zip`).

    المعرّف لازم يكون **صالح** (حروف/أرقام/`-`/`_` بطول محدود) — نتأكد تاني هنا
    (دفاع بعمق) وبعدين ننقّي أي محرف تاني. النتيجة قاصر على محارف آمنة ⇒ مفيش CR/LF
    ولا اقتباس ولا مسار، فمفيش response-header injection ولا اجتياز مسار.
    """
    cid = conversation_id if is_valid_conversation_id(conversation_id) else ""
    safe = "".join(ch for ch in cid if ch in _EXPORT_NAME_SAFE)
    return f"conversation-{safe}.zip" if safe else "conversation.zip"


class MiniAppService:
    """عمليات الـ Mini App فوق نفس client/db/outbox بتاع البوت."""

    def __init__(self, config, db, client=None, application=None) -> None:
        self._config = config
        self._db = db
        self._client = client
        self._application = application
        # OHB2-09-A2-02: كاش هوية واحد لكل خدمة (نفس العميل) — نداء `/users/me` واحد
        # لكل العمليات بدل ما كل مسار يجيبه لوحده. مفيش أي ضعف في العقد: نفس المقارنة.
        self._identity = IdentityCache(client) if client is not None else None

    # ------------------------------------------------------------ helpers
    def _require_client(self):
        if self._client is None:
            raise ApiError("خدمة OpenHands مش متاحة دلوقتي.", 503)
        return self._client

    async def _authorize_conversation(self, conversation_id: str, *, allow_deleted: bool = False) -> dict:
        """يفوّض شات واحد عبر الخدمة المشتركة **قبل** أي جلب بيانات محمية (OHB2-09-A2-02).

        بترجّع الميتاداتا المتفوَّض عليها أو بترمي `FileApiError` منظّم (403/404/502).
        كل مسار شات في الـ Mini App بيعدي من هنا — مفيش مقارنة مالك مكرّرة في مسار.

        F-1: بنمرّر قاعدة البيانات المالكة (`self._db`) عشان فرض شاهد الحذف يحصل **قبل**
        أي نداء بعيد — الشات المتشاهد يُرفض بـ `DELETED` ⇒ رد «مش موجود» (404).
        `allow_deleted=True` استثناء مقصود لعمليتين صريحتين بس (مش قراءة): **إعادة
        التفاعل (`watch`)** و**إعادة محاولة الحذف** — دول بيعتمدوا على طبقة القاعدة
        (reengage/CAS الحذف) للتعامل مع الحالة المتشاهدة بأمان.
        """
        client = self._require_client()
        if self._identity is None:
            self._identity = IdentityCache(client)
        conv, status = await authorize_conversation(
            client, self._identity, conversation_id, self._db, allow_deleted=allow_deleted
        )
        if conv is None:
            raise self._conversation_error(status)
        return conv

    @staticmethod
    def _conversation_error(status: FileStatus) -> CodedApiError:
        code, http, message = CONVERSATION_ERRORS.get(
            status, ("upstream_error", 502, "تعذّر الوصول للشات دلوقتي.")
        )
        return CodedApiError(code, message, http)

    def _wake(self, key: str) -> None:
        """ينبّه الـ worker المالك الموجود (نفس العملية) لو موجود — بدون إنشاء worker.

        بعض كيانات `bot_data` (Watcher/Notifier) **ملهاش** `wake()`؛ النداء الأعمى عليها
        كان يضرب AttributeError (500) بعد حذف بعيد **نجح بالفعل**، فيبان للمستخدم فشل
        مش موجود. بننادي `wake()` بس لو موجودة فعلاً، وأي استثناء من التنبيه نفسه
        (مش من العملية الأصلية) بنبتلعه بعد تسجيله — التنبيه ثانوي ومستحيل يفشّل عملية
        نجحت. (ده مش إخفاء خطأ: العملية الأصلية مسجّلة ومُرجَعة بحالتها الحقيقية.)
        """
        if self._application is None:
            return
        worker = self._application.bot_data.get(key)
        wake = getattr(worker, "wake", None)
        if not callable(wake):
            return
        try:
            wake()
        except Exception:  # noqa: BLE001 — تنبيه ثانوي لا يفشّل عملية نجحت
            log.warning("فشل تنبيه الـ worker %r بعد عملية ناجحة؛ بنتجاهله.", key)

    def _list_cache(self):
        if self._application is None:
            return None
        return self._application.bot_data.get("list_cache")

    def _set_list_cache(self, items, truncated: bool = False) -> None:
        if self._application is not None:
            self._application.bot_data["list_cache"] = (time.monotonic(), items, truncated)

    def _drop_list_cache(self) -> None:
        if self._application is not None:
            self._application.bot_data.pop("list_cache", None)

    # --------------------------------------------------------- bootstrap
    def bootstrap(self, session) -> dict:
        return {
            "user": {"display_name": session.profile.get("display_name", "")},
            "settings": {"notifications_enabled": self.notifications_enabled()},
            "mini_app": {"version": 1, "locale": "ar", "direction": "rtl"},
            # OHB2-06: نعرض حالة الميزات عشان الواجهة تخفي المؤجّلة (القرار 4).
            "features": {"watches": not features.is_hidden("followups")},
            # OHB2-08-05: عدد الإشعارات غير المقروءة لشارة الصندوق (صفر لو مفيش قاعدة).
            "inbox": {"unread_count": self._inbox_unread_count()},
        }

    def _inbox_unread_count(self) -> int:
        if self._db is None:
            return 0
        try:
            return self._db.count_inbox(unread_only=True)
        except Exception:  # noqa: BLE001 - القراءة ما تكسّرش الصفحة
            return 0

    def notifications_enabled(self) -> bool:
        if self._db is None:
            return True
        try:
            return bool(self._db.get_notifications_enabled())
        except Exception:  # noqa: BLE001 - القراءة ما تكسّرش الصفحة
            return True

    def set_notifications(self, enabled: bool) -> bool:
        if self._db is None:
            raise ApiError("قاعدة البيانات مش متاحة دلوقتي.", 503)
        self._db.set_notifications_enabled(bool(enabled))
        return bool(enabled)

    # ------------------------------------------------------ notification inbox
    def list_notifications(
        self, page: int = 0, unread_only: bool = False, archived: bool = False
    ) -> dict:
        """قايمة صندوق الإشعارات (الأحدث أولًا) بترقيم محدود على مستوى SQL.

        payload محدود (LIMIT/OFFSET) زي باقي القوايم؛ `unread_count` بيساعد الواجهة
        تعرض شارة غير المقروء من غير ما تجيب كل الصفحات. لو القاعدة مش متاحة، نرجّع
        فاضي بدل ما نكسّر الصفحة (زي `bootstrap`).

        OHB2-PHASE1C: `archived=False` (الافتراضي) = الصندوق النشط؛ `archived=True` =
        عرض الأرشيف. `unread_count` بيفضل على النشط دايمًا (الأرشيف ما بيأثّرش على الشارة).
        """
        if self._db is None:
            return {"page": 0, "has_more": False, "unread_count": 0, "items": []}
        page = _page_number(page)
        offset = _page_offset(page, INBOX_PAGE_SIZE)
        items = self._db.list_inbox(
            limit=INBOX_PAGE_SIZE, offset=offset, unread_only=unread_only, archived=archived
        )
        # لو الصفحة فاضية بسبب تجاوز الحد، نرجع للأولى (زي قايمة المتابعات).
        if not items and page > 0:
            page, offset = 0, 0
            items = self._db.list_inbox(
                limit=INBOX_PAGE_SIZE, offset=0, unread_only=unread_only, archived=archived
            )
        total = self._db.count_inbox(unread_only=unread_only, archived=archived)
        return {
            "page": page,
            "has_more": total > offset + len(items),
            "unread_count": self._db.count_inbox(unread_only=True),
            "items": [self._inbox_dto(it) for it in items],
        }

    def _inbox_dto(self, item) -> dict:
        # OHB2-PHASE1C: هل السيرفر يعتبر الصف مؤهّلًا للحذف النهائي؟ بنستدعي **نفس** فحص
        # الأهلية بتاع مسار الحذف (`inbox_item_delete_eligibility`) عشان الإشارة للواجهة
        # ما تختلفش عن التنفيذ أبدًا. القرار النهائي بيتفرض على السيرفر وقت الحذف نفسه.
        deletable = False
        if self._db is not None and item.id is not None:
            deletable = self._db.inbox_item_delete_eligibility(item.id) == INBOX_DELETE_DELETED
        return {
            "id": item.id,
            "conversation_id": item.conversation_id,
            "title": item.title or "",
            "kind": item.kind or "",
            "message": item.message or "",
            "created_at": item.created_at or "",
            "read": not item.unread,
            # OHB2-PHASE1C: محور الأرشفة (مستقل) — الواجهة تعرف تعرض زر أرشفة/استرجاع.
            "archived": bool(item.archived),
            "deletable": deletable,
            # OHB2-08-05 (Batch 3R): حالة التسليم المتينة — عشان الواجهة تفرّق بين
            # إشعار اتسلّم وإشعار لسه معلّق أو فشل (event-first، مش تسجيل تاريخي بس).
            "delivery_status": getattr(item, "delivery_status", None) or "delivered",
            "delivery_attempts": int(getattr(item, "delivery_attempts", 0) or 0),
            "delivered_at": getattr(item, "delivered_at", None),
        }

    def mark_notification_read(self, item_id) -> dict:
        if self._db is None:
            raise ApiError("قاعدة البيانات مش متاحة دلوقتي.", 503)
        ident = self._inbox_item_id(item_id)
        ok = self._db.mark_inbox_read(ident, outbox.now_iso())
        if not ok:
            raise ApiError("الإشعار مش موجود.", 404)
        return {"ok": True, "unread_count": self._db.count_inbox(unread_only=True)}

    def mark_all_notifications_read(self) -> dict:
        if self._db is None:
            raise ApiError("قاعدة البيانات مش متاحة دلوقتي.", 503)
        changed = self._db.mark_all_inbox_read(outbox.now_iso())
        return {"ok": True, "marked": changed, "unread_count": self._db.count_inbox(unread_only=True)}

    @staticmethod
    def _inbox_item_id(item_id) -> int:
        """يتحقّق من معرّف عنصر الصندوق (عدد صحيح موجب) أو يرفع ValidationError."""
        try:
            ident = int(item_id)
        except (TypeError, ValueError):
            raise ValidationError("معرّف الإشعار غير صالح")
        if ident <= 0 or ident > MAX_SQLITE_INT:
            raise ValidationError("معرّف الإشعار غير صالح")
        return ident

    def archive_notification(self, item_id) -> dict:
        """يؤرشف إشعار (idempotent، قابل للعكس). ما بيغيّرش التسليم/القراءة/العملية."""
        if self._db is None:
            raise ApiError("قاعدة البيانات مش متاحة دلوقتي.", 503)
        ident = self._inbox_item_id(item_id)
        ok = self._db.archive_inbox_item(ident, outbox.now_iso())
        if not ok:
            raise ApiError("الإشعار مش موجود.", 404)
        return {
            "ok": True,
            "archived": True,
            "unread_count": self._db.count_inbox(unread_only=True),
        }

    def unarchive_notification(self, item_id) -> dict:
        """يلغي أرشفة إشعار (idempotent) ويرجّعه للصندوق النشط بنفس الهوية."""
        if self._db is None:
            raise ApiError("قاعدة البيانات مش متاحة دلوقتي.", 503)
        ident = self._inbox_item_id(item_id)
        ok = self._db.unarchive_inbox_item(ident)
        if not ok:
            raise ApiError("الإشعار مش موجود.", 404)
        return {
            "ok": True,
            "archived": False,
            "unread_count": self._db.count_inbox(unread_only=True),
        }

    def delete_notification(self, item_id) -> dict:
        """يحذف إشعار نهائيًا **بس لو مؤهّل** (القرار بيتفرض على السيرفر).

        الصفوف المحمية (معلّقة/فاشلة/غير مقروءة/مرجع تسوية) بترجّع 409 و`deleted: false`
        من غير أي تغيير ⇒ مفيش نجاح كاذب ولا فقد دليل تشغيلي.
        """
        if self._db is None:
            raise ApiError("قاعدة البيانات مش متاحة دلوقتي.", 503)
        ident = self._inbox_item_id(item_id)
        verdict = self._db.delete_inbox_item(ident)
        if verdict == INBOX_DELETE_MISSING:
            raise ApiError("الإشعار مش موجود.", 404)
        if verdict != INBOX_DELETE_DELETED:
            # محمي: الإشعار لسه بيحمل دليلًا تشغيليًا (تسليم/تسوية) أو لسه ما اتقراش.
            raise ApiError("الإشعار ده محمي من الحذف النهائي.", 409)
        return {
            "ok": True,
            "deleted": True,
            "unread_count": self._db.count_inbox(unread_only=True),
        }

    # ------------------------------------------------------ conversations
    async def list_conversations(self, page: int = 0, refresh: bool = False) -> dict:
        client = self._require_client()
        cache = self._list_cache()
        # TASK 55 (G4): نفس كاش البوت القصير — مشارك بين البوت والـ Mini App.
        if not refresh and cache and time.monotonic() - cache[0] < 45.0:
            items = cache[1]
            truncated = cache[2] if len(cache) > 2 else False
        else:
            # OHB2-AUDIT-FIX-05: نتبع كل صفحات البحث (next_page_id بحد أقصى) بدل صفحة
            # واحدة، فالشاتات الأقدم تبقى قابلة للوصول (مش إخفاء صامت بعد أول 100).
            collected = await collect_conversations(client)
            items = collected["items"]
            truncated = collected["truncated"]
            if items:
                self._set_list_cache(items, truncated)
        # OHB2-C7: الشاتات المحذوفة محليًا (tombstone) لازم تختفي من القايمة فورًا.
        # مصدر القايمة بعيد (search) فمش عارف بالحذف المحلي؛ نفلترها قبل الترقيم عشان
        # الشات المحذوف ما يظهرش تاني بعد refresh (من غير انتظار دورة البوت).
        items = self._without_deleted(items)
        page = _page_number(page)
        start = _page_offset(page, PAGE_SIZE)
        chunk = items[start : start + PAGE_SIZE]
        if not chunk and page > 0:
            page, start, chunk = 0, 0, items[:PAGE_SIZE]
        watched = self._watched_ids()
        return {
            "page": page,
            "has_more": len(items) > start + PAGE_SIZE,
            "truncated": truncated,
            "items": [self._list_item(c, watched) for c in chunk],
        }

    def _without_deleted(self, items: list[dict]) -> list[dict]:
        """يشيل أي شات عليه شاهد حذف محلي (OHB2-C7) من قايمة الـ Mini App.

        OHB2-SW03 (كان OHB2-AUDIT-FIX-04): فشل قراءة الشواهد **مايتحوّلش** لقايمة فاضية.
        بنستخدم `db.is_deleted_with_retry` (إعادة محدودة للعابر BUSY/LOCKED ثم رفع الاستثناء
        الأصلي)، والفشل بينتشر لحد ما الـ route يحوّله لـ 500 عام — بدل رد 200 فاضي مضلّل.
        الفراغ الحقيقي (مدخل فاضي أو كل الشاتات متشاهدة) لسه بيرجّع `[]` بشكل مشروع.
        """
        if self._db is None or not items:
            return items
        return [c for c in items if not self._db.is_deleted_with_retry(c.get("id") or "")]

    def _list_item(self, conv: dict, watched: set[str]) -> dict:
        status = get_status(conv)
        cid = conv.get("id") or ""
        return {
            "id": cid,
            "title": conv.get("title") or "",
            "repository": conv.get("selected_repository") or "",
            "status": status,
            "state_label": state_label(status),
            "updated_at": conv.get("updated_at") or "",
            "watched": cid in watched,
        }

    def _watched_ids(self) -> set[str]:
        if self._db is None:
            return set()
        try:
            return {w.conversation_id for w in self._db.list_watched()}
        except Exception:  # noqa: BLE001
            return set()

    async def get_conversation(self, conversation_id: str) -> dict:
        cid = _require_id(conversation_id)
        client = self._require_client()
        # OHB2-09-A2-02: تفويض على مستوى الشات **قبل** جلب أي بيانات محمية (آخر تبادل).
        conv = await self._authorize_conversation(cid)
        user_text, reply = await client.get_last_exchange(cid)
        reply_text, cut = truncate(reply, 4000)
        watched = cid in self._watched_ids()
        dto = _conversation_dto(conv, watched)
        dto.update(
            {
                "sandbox_status": conv.get("sandbox_status") or "",
                "pr_url": pr_url(conv) or "",
                "last_prompt": truncate(user_text, 2000)[0],
                "last_reply": reply_text,
                "reply_truncated": cut,
            }
        )
        return dto

    async def get_status(self, conversation_id: str) -> dict:
        cid = _require_id(conversation_id)
        conv = await self._authorize_conversation(cid)
        return _conversation_dto(conv, cid in self._watched_ids())

    async def get_full_reply(self, conversation_id: str) -> dict:
        """OHB2-PHASE1B: الرد الكامل للـ assistant (مصدر زر «نسخ الرد الكامل»).

        التفويض أولًا (نفس عقد الملكية)، ثم **نفس** `get_last_exchange` اللي البوت
        بيستخدمه. بترجّع النص الكامل (بلا قصّ بصري) + علم `reply_truncated` لو عدّى
        السقف الصلب `MAX_FULL_REPLY_CHARS` (حالة نادرة جدًا). مفيش أي معرّفات داخلية
        ولا بيانات غير مصرّح بها — النص بس + العلم.
        """
        cid = _require_id(conversation_id)
        client = self._require_client()
        await self._authorize_conversation(cid)
        _user_text, reply = await client.get_last_exchange(cid)
        text, cut = truncate(reply, MAX_FULL_REPLY_CHARS)
        return {"conversation_id": cid, "reply": text, "reply_truncated": cut}

    async def export_conversation(self, conversation_id: str):
        """OHB2-PHASE1B: تصدير الشات (zip) للمستخدم المصرّح له — نفس صيغة البوت.

        بترجّع `(data, filename)` أو بترمي `CodedApiError` منظّم. الترتيب المهم:

        1. **التفويض قبل أي تنزيل** (ملكية الشات من `/users/me` + `created_by_user_id`،
           فشل مغلق) — مفيش ثقة في أي هوية من العميل، والمستخدم جاي من الجلسة.
        2. **فحص شاهد الحذف المحلي** بعد التفويض وقبل التنزيل: شات محذوف/مُعلَّم لا
           يُصدَّر ولا يُحيا من بيانات محلية قديمة (نفس حماية الحذف البعيد).
        3. تنزيل **محدود** بنفس `OpenHandsClient.export_conversation` (سقف صلب
           `MAX_EXPORT_BYTES` عبر `_read_capped`، ومفيش تجميع غير محدود).
        4. فشل التنزيل/عدّى الحد ⇒ خطأ منظّم، **مفيش** تصدير «ناجح» كاذب.
        """
        cid = _require_id(conversation_id)
        client = self._require_client()
        await self._authorize_conversation(cid)
        # شاهد الحذف المحلي (لو فيه قاعدة مربوطة): شات محذوف/مُعلَّم لا يُصدَّر ولا يُحيا
        # من بيانات محلية قديمة. من غير قاعدة (وضع مستقل) مفيش شواهد محلية نحترمها —
        # نفس سلوك `_watched_ids`. أي فشل قراءة ⇒ فشل مغلق (مفيش تصدير).
        if self._db is not None:
            try:
                if self._db.is_deleted(cid):
                    # نفس رسالة «مش موجود» عشان ما نسيبش استنتاج وجود شات متحذف.
                    raise CodedApiError("not_found", "الشات مش موجود.", 404)
            except CodedApiError:
                raise
            except Exception:  # noqa: BLE001 — قاعدة غير متاحة ⇒ فشل مغلق
                log.warning("تعذّر قراءة شاهد الحذف؛ بنرفض التصدير (فشل مغلق).")
                raise ApiError("قاعدة البيانات مش متاحة دلوقتي.", 503)
        try:
            data = await client.export_conversation(cid)
        except ResponseTooLargeError:
            raise CodedApiError(
                "too_large", "التصدير كبير أوي للتنزيل الآمن. جرّب شات أصغر.", 413
            )
        return data, export_filename(cid)

    async def associate_repository(self, conversation_id: str, repository: str) -> dict:
        """يربط مستودع بشات موجود (OHB2: إدارة الشاتات).

        تفويض ملكية الشات أولاً (نفس عقد كل مسارات الشات)، ثم PATCH على نفس الشات.
        المستودع لازم يكون بالشكل owner/repo؛ مفيش إنشاء شات جديد ولا أي كتابة محلية.
        """
        cid = _require_id(conversation_id)
        repo = _require_repo(repository)
        await self._authorize_conversation(cid)
        client = self._require_client()
        await client.update_conversation_repository(cid, repo)
        conv = await self._authorize_conversation(cid)
        return _conversation_dto(conv, cid in self._watched_ids())

    async def delete_conversation(self, conversation_id: str) -> dict:
        """حذف الشات **من OpenHands نفسه** ثم تثبيت الحذف محليًا (OHB2-MINIAPP).

        التفويض أولاً (معرّف صالح ⇒ ملكية الشات server-side)، وبعدين:
        1. وسم الحذف الجاري (شاهد + 'deleting') في القاعدة — قبل أي نداء بعيد.
        2. `DELETE /app-conversations/{id}` (Bearer) على OpenHands.
        3. الحذف المحلي + 'confirmed' **بس** بعد تأكيد OpenHands (200) أو إثبات الغياب
           بقراءات متتالية. 404 **مبهم** (غياب أو فشل خدمة داخلي) ⇒ نفس التسوية، مش نجاح تلقائي.

        الفشل المؤكّد (400/401/403) والنتيجة المجهولة (404/429/5xx/انقطاع) **مايترجّعوش نجاح**:
        الفشل المؤكّد ⇒ خطأ منظّم (الشات لسه موجود)، والمجهول ⇒ خطأ 'pending' (الشات متقفل
        محليًا بس الحذف البعيد لسه مش متأكد). مفيش fallback صامت لحذف محلي فقط.
        """
        cid = _require_id(conversation_id)
        if self._db is None:
            raise ApiError("قاعدة البيانات مش متاحة دلوقتي.", 503)
        client = self._require_client()
        # idempotent: حذف بعيد **مؤكّد سابقًا** ⇒ نجاح بدون نداء تاني. الشات بقى غايب
        # بعيدًا فتفويض الملكية كان هيرجّع 404؛ بدل كده نعتبره نجاح (الحذف اتعمل فعلًا).
        # آمن: الراوت (`_guarded`) بيفرض جلسة + مستخدم مسموح + Origin قبل ما نوصل هنا،
        # والشاهد المؤكّد ما بيتكتبش غير بعد حذف متفاوَض عليه من نفس المالك.
        state = self._db.remote_deletion_state(cid)
        if state == self._db.REMOTE_CONFIRMED:
            return {"ok": True, "deleted": True, "remote_deleted": True, "conversation_id": cid}
        # تفويض الملكية **قبل** أي حذف (مفيش IDOR). بيرمي CodedApiError منظّم عند الرفض.
        # F-1: `allow_deleted=True` — إعادة محاولة الحذف عملية صريحة على شات ممكن يكون
        # متشاهد (deleting/uncertain). لو الحالة أصلًا معلّقة وOpenHands خلاص حذفه (`not_found`)،
        # نمرّ لتسوية التحقق (قراءتان متتاليتان) من غير كسر 403/502.
        try:
            await self._authorize_conversation(cid, allow_deleted=True)
        except CodedApiError as exc:
            if not (
                exc.code == "not_found"
                and state in (self._db.REMOTE_DELETING, self._db.REMOTE_UNCERTAIN)
            ):
                raise
        result = await deletion.delete_conversation_remote(client, self._db, cid)
        # نبلّغ أي worker مالك (نفس العملية) إن فيه تغيير — من غير إنشاء worker جديد.
        for key in ("outbox_worker", "creation_worker", "completion_worker", "watcher", "notifier"):
            self._wake(key)
        if result.status != deletion.STATUS_DELETED:
            raise CodedApiError(
                result.code or "remote_delete_failed",
                result.message,
                result.http_status or 502,
            )
        self._drop_list_cache()
        return {
            "ok": True,
            "deleted": True,
            "remote_deleted": True,
            "conversation_id": cid,
        }

    def list_pending_deletions(self) -> dict:
        """قايمة عمليات الحذف البعيد المعلّقة ('deleting'/'uncertain') للعرض والتسوية اليدوية."""
        if self._db is None:
            raise ApiError("قاعدة البيانات مش متاحة دلوقتي.", 503)
        return {"items": self._db.list_pending_remote_deletions_detail()}

    async def reconcile_deletion(self, conversation_id: str) -> dict:
        """تسوية يدوية لحذف بعيد معلّق عبر التحقق من الوجود (GET) بدون إعادة إرسال DELETE."""
        cid = _require_id(conversation_id)
        if self._db is None:
            raise ApiError("قاعدة البيانات مش متاحة دلوقتي.", 503)
        client = self._require_client()
        state, pre_updated_at = self._db.remote_deletion_metadata(cid)
        if state == self._db.REMOTE_CONFIRMED:
            return {
                "ok": True,
                "deleted": True,
                "remote_deleted": True,
                "conversation_id": cid,
                "status": "deleted",
                "message": deletion.DELETED_MESSAGE,
            }
        if state not in (self._db.REMOTE_DELETING, self._db.REMOTE_UNCERTAIN):
            raise CodedApiError("not_pending", "مفيش عملية حذف معلّقة للشات ده.", 409)
        try:
            await self._authorize_conversation(cid, allow_deleted=True)
        except CodedApiError as exc:
            if exc.code == "upstream_error":
                attempt_id = self._db.claim_remote_reconcile(cid)
                if attempt_id is not None:
                    ts = pre_updated_at if pre_updated_at is not None else outbox.now_iso()
                    self._db.revert_remote_deletion_cas(
                        cid, attempt_id, self._db.REMOTE_UNCERTAIN, ts
                    )
                raise CodedApiError("remote_delete_pending", deletion.PENDING_MESSAGE, 503)
            if exc.code != "not_found":
                raise
        result = await deletion.reconcile_pending_deletion(client, self._db, cid)
        for key in ("outbox_worker", "creation_worker", "completion_worker", "watcher", "notifier"):
            self._wake(key)
        if result.status != deletion.STATUS_DELETED:
            raise CodedApiError(
                result.code or "remote_delete_failed",
                result.message,
                result.http_status or 502,
            )
        self._drop_list_cache()
        return {
            "ok": True,
            "deleted": True,
            "remote_deleted": True,
            "conversation_id": cid,
            "status": "deleted",
            "message": result.message,
        }

    async def get_cost(self, conversation_id: str) -> dict:
        """OHB2-09-04: تكلفة/استهلاك شات واحد (من نفس نداء التفاصيل — مفيش نداء إضافي)."""
        cid = _require_id(conversation_id)
        # OHB2-09-A2-02: نفس عقد الملكية قبل قراءة المقاييس الخاصة.
        conv = await self._authorize_conversation(cid)
        return _cost_dto(conv)

    # ------------------------------------------------------------ files (OHB2-09-02)
    def _files(self) -> FileService:
        """`FileService` فوق **نفس** العميل المشترك وكاش الهوية المشترك (بدون عميل تاني).

        التحقق من الملكية/المسار/الـ allowlist كله جوّه `FileService` — الـ route
        ما بيكرّرش أي منطق تفويض. بنمرّر كاش الهوية بتاع الخدمة عشان كل العمليات
        (تفاصيل/تكلفة/ملفات/تصدير) تشارك نداء `/users/me` واحد.
        """
        client = self._require_client()
        if self._identity is None:
            self._identity = IdentityCache(client)
        return FileService(client, identity=self._identity, db=self._db)

    async def list_files(self, conversation_id: str) -> dict:
        """قايمة ملفات شات مصرّح به (نتيجة منظّمة، مفيش استثناءات للـ route)."""
        if not is_valid_conversation_id(conversation_id):
            raise FileApiError("invalid_conversation", "معرّف الشات غير صالح.", 400)
        listing = await self._files().list_files(conversation_id)
        if listing.status is FileStatus.OK:
            return {"conversation_id": conversation_id, "files": list(listing.files)}
        raise self._file_error(listing.status, listing.error)

    async def read_file_preview(self, conversation_id: str, path: str) -> dict:
        """معاينة نصية محدودة لملف من قايمة الشات (allowlist + حد صلب)."""
        if not is_valid_conversation_id(conversation_id):
            raise FileApiError("invalid_conversation", "معرّف الشات غير صالح.", 400)
        if not is_safe_workspace_path(path):
            raise FileApiError("invalid_path", "مسار الملف غير صالح.", 400)
        content = await self._files().read_preview(conversation_id, path)
        if content.status in _FILE_CONTENT_STATUSES:
            return {
                "conversation_id": conversation_id,
                "path": content.path,
                "status": content.status.value,
                "text": content.text,
                "truncated": content.truncated,
                "size_bytes": content.size_bytes,
            }
        raise self._file_error(content.status, content.error)

    @staticmethod
    def _file_error(status: FileStatus, error: str | None) -> FileApiError:
        code, http = _FILE_STATUS_ERRORS.get(status, ("upstream_error", 502))
        return FileApiError(code, file_status_message(status, error), http)

    async def send_prompt(
        self, conversation_id: str, text: str, client_ref: str | None = None
    ) -> dict:
        """يسجّل البرومت في الصندوق المتين (نفس مسار البوت) وينبّه الـ worker المالك.

        `client_ref` (OHB2-07): معرّف عملية من العميل. لو نفس العملية اتبعتت تاني
        (double-tap/إعادة محاولة)، بنرجّع نفس السجل بدل ما نعمل برومت مكرّر.
        """
        cid = _require_id(conversation_id)
        body = _require_text(text)
        ref = _require_ref(client_ref)
        if self._db is None:
            raise ApiError("قاعدة البيانات مش متاحة دلوقتي.", 503)
        # OHB2-09-A2-02: تفويض ملكية الشات **قبل** تسجيل أي برومت في الصندوق — نفس
        # عقد باقي مسارات الشات (تفاصيل/حالة/تكلفة/ملفات/متابعة). كده مستخدم مصادَق
        # (مش المالك) مايقدرش يوجّه برومت لشات مش بتاعه. مفيش أي أثر (سجل صندوق) قبل القرار.
        # F-1: `allow_deleted=True` مقصود — إرسال برومت من الـ Mini App **مش** مسار قراءة،
        # ورده المتّفق عليه (والموثّق/المُختبَر) للشات المتشاهد هو **409 conversation_deleted**
        # من طبقة القاعدة (الفحص الذرّي جوّه `add_or_group_outbox` مع `reengage=False`)،
        # مش 404. كده مفيش تفاعل مع شات متشاهد، والقاعدة هي الحاجز الموثوق (race-safe).
        await self._authorize_conversation(cid, allow_deleted=True)
        chat_id = self._config.owner_id
        # OHB2-AUDIT-FIX-01: `reengage=False` — مسار الـ Mini App **مش** إعادة تفاعل صريح
        # (إعادة المتابعة عند الـ Mini App بتحصل عبر `watch`، مش عبر إرسال برومت). كده أي
        # برومت لشات متشاهد يُرفض (سواء بحمل `client_ref` أو لأ)، ومستحيل يحيي شات اتحذف.
        outbox_id = self._db.add_or_group_outbox(
            cid, chat_id, body, outbox.now_iso(), client_ref=ref or None
        )
        # 0 = التسجيل اترفض (الشات اتحذف). ما نرجّعش «queued: true» كاذبة — خطأ واضح.
        if not outbox_id:
            raise CodedApiError("conversation_deleted", "الشات اتحذف — مش ممكن نبعت له.", 409)
        self._drop_list_cache()
        self._wake("outbox_worker")
        return {
            "ok": True,
            "queued": True,
            "outbox_id": outbox_id,
            "operation": self.outbox_operation(outbox_id),
        }

    # --------------------------------------------------- operation status
    def outbox_operation(self, outbox_id: int) -> dict:
        """حالة عملية برومت (DTO آمن: مفيش نص البرومت ولا تفاصيل داخلية خام).

        OHB2-PHASE1D: البحث **مقيّد بالمالك** (نفس `owner_id`) — أي id لمستخدم تاني ⇒ 404
        (مفيش تسريب وجود صف ولا محتوى غيره).
        """
        if self._db is None:
            raise ApiError("قاعدة البيانات مش متاحة دلوقتي.", 503)
        item = self._db.get_outbox(outbox_id, self._config.owner_id)
        if item is None:
            raise ApiError("العملية مش موجودة.", 404)
        return self._outbox_dto(item)

    def creation_operation(self, job_id: int) -> dict:
        """حالة عملية إنشاء شات (DTO آمن).

        OHB2-PHASE1D: البحث **مقيّد بالمالك** — أي job لمستخدم تاني ⇒ 404.
        """
        if self._db is None:
            raise ApiError("قاعدة البيانات مش متاحة دلوقتي.", 503)
        job = self._db.get_creation_job(job_id, self._config.owner_id)
        if job is None:
            raise ApiError("العملية مش موجودة.", 404)
        return self._creation_dto(job)

    def list_creation_jobs(self, page: int = 0) -> dict:
        """قايمة طلبات الشات الجديد **المملوكة للمالك** (قراءة فقط) + الترقيم.

        OHB2-PHASE1D: نطاق المالك مفروض في الاستعلام؛ الترقيم offset ثابت؛ أي محاولة
        تمرير معرّف مستخدم من الواجهة مُتجاهَلة (المصدر الوحيد هو `config.owner_id`).
        """
        if self._db is None:
            raise ApiError("قاعدة البيانات مش متاحة دلوقتي.", 503)
        page = _page_number(page)
        jobs, has_more = self._db.list_creation_jobs_for_owner(
            self._config.owner_id, page=page, page_size=PAGE_SIZE
        )
        return {
            "page": page,
            "has_more": has_more,
            "items": [self._creation_dto(j) for j in jobs],
        }

    def reconcile_outbox(self, outbox_id: int, action: str) -> dict:
        """OHB2-09-05: تسوية يدوية لعملية برومت معلّقة (parity مع أوامر البوت).

        - `discard`: أي سجل غير نهائي ⇒ `discarded` (نهائي). سجل نهائي ⇒ 409.
        - `mark_sent`: سجل حالته `unknown` بس ⇒ `sent` (تأكيد المالك، مش إثبات من
          OpenHands). `sent` أصلاً ⇒ no-op (نرجّعه زي ما هو، idempotent). أي حالة
          تانية ⇒ 409 (نفس سلوك أمر البوت).
        - التحويل لـ `sent`/`discarded` نهائي: مستحيل يرجع `pending`، فمفيش إعادة
          إرسال تلقائي (at-most-once محفوظ). التسوية **مابتعملش** أي إرسال شبكة.
        """
        if action not in ("discard", "mark_sent"):
            raise ValidationError("إجراء غير معروف")
        if self._db is None:
            raise ApiError("قاعدة البيانات مش متاحة دلوقتي.", 503)
        item = self._db.get_outbox(outbox_id, self._config.owner_id)
        if item is None:
            raise ApiError("العملية مش موجودة.", 404)
        status = item.status
        if action == "discard":
            if status in _TERMINAL_OUTBOX:
                raise CodedApiError("already_terminal", "العملية خلاص في حالة نهائية.", 409)
            if status in _NOT_CONFIRMED_OUTBOX:
                # OHB2-N10-28C: الـ POST ممكن يكون بدأ ⇒ مفيش ادّعاء إلغاء. نرجّع الحالة
                # الحالية بعلامة "الإلغاء غير مؤكد" (مفيش تغيير في القاعدة).
                log.info("reconcile: outbox=%s discard not confirmed (state=%s)", outbox_id, status)
                dto = self._outbox_dto(item)
                dto["cancellation"] = "not_confirmed"
                return dto
            # CAS ذرّي: شرط الحالة جوّه الـ UPDATE نفسه، فلو سجل تاني سبقنا وحسم الحالة
            # بين القراءة والكتابة، الـ rowcount=0 ⇒ ما بنغيّرش حاجة (مفيش سباق read-then-write).
            changed = self._db.set_outbox_status_if_in(
                outbox_id,
                db_module.OUTBOX_DISCARDED,
                outbox.now_iso(),
                _DISCARDABLE_OUTBOX,
                "اتشال يدوياً",
            )
            if not changed:
                # حد تاني حسم السجل بين القراءة والـ CAS ⇒ نرجّع الحالة الحقيقية.
                current = self._db.get_outbox(outbox_id, self._config.owner_id)
                if current is not None and current.status in _NOT_CONFIRMED_OUTBOX:
                    dto = self._outbox_dto(current)
                    dto["cancellation"] = "not_confirmed"
                    return dto
                raise CodedApiError("already_terminal", "العملية خلاص في حالة نهائية.", 409)
            log.info("reconcile: outbox=%s discard", outbox_id)
            result = self._outbox_dto(self._db.get_outbox(outbox_id, self._config.owner_id))
            result["cancellation"] = "discarded"
            return result
        else:  # mark_sent
            if status == db_module.OUTBOX_SENT:
                return self._outbox_dto(item)  # idempotent: معَلّم sent بالفعل
            if status != db_module.OUTBOX_UNKNOWN:
                raise CodedApiError("invalid_state", "الأمر ده للسجلات 'unknown' بس.", 409)
            changed = self._db.set_outbox_status_if_in(
                outbox_id,
                db_module.OUTBOX_SENT,
                outbox.now_iso(),
                {db_module.OUTBOX_UNKNOWN},
                "أكّده المالك",
            )
            if not changed:
                # حد تاني حسم السجل بين القراءة والكتابة ⇒ ما بنغيّرش حاجة.
                current = self._db.get_outbox(outbox_id, self._config.owner_id)
                if current is not None and current.status == db_module.OUTBOX_SENT:
                    return self._outbox_dto(current)
                raise CodedApiError("invalid_state", "الأمر ده للسجلات 'unknown' بس.", 409)
            log.info("reconcile: outbox=%s mark_sent", outbox_id)
        return self._outbox_dto(self._db.get_outbox(outbox_id, self._config.owner_id))

    def reconcile_creation(self, job_id: int, action: str) -> dict:
        """OHB2-PHASE1D: تسوية يدوية لطلب شات جديد معلّق (parity مع أوامر البوت).

        - `cancel`   : نفس دلالات `discard_creation_job` — مسموح **بس** في `pending`/
          `claimed` (اللي الكود بيثبت إن POST البدء لسه مابدأش). CAS ذرّي ⇒ `discarded`
          (نهائي، مستحيل يرجع `pending` ⇒ مفيش إعادة POST). لو الـ POST ممكن يكون بدأ
          (`starting`/`unknown`) ⇒ مفيش ادّعاء إلغاء: نرجّع الحالة الحالية + علامة
          `cancellation="not_confirmed"` والقاعدة ماتتغيّرش. حالة نهائية ⇒ 409.
        - `mark_sent` (`done`): مسموح **بس** من `unknown` ⇒ `done` (تأكيد المالك، مش إثبات
          من OpenHands). `done` أصلاً ⇒ no-op (idempotent). أي حالة تانية ⇒ 409.

        التسوية **مابتعملش** أي POST شبكة، والتحويلات نهائية (at-most-once محفوظ).
        البحث مقيّد بالمالك.
        """
        if action not in ("cancel", "mark_sent"):
            raise ValidationError("إجراء غير معروف")
        if self._db is None:
            raise ApiError("قاعدة البيانات مش متاحة دلوقتي.", 503)
        job = self._db.get_creation_job(job_id, self._config.owner_id)
        if job is None:
            raise ApiError("العملية مش موجودة.", 404)
        status = job.status
        if action == "cancel":
            if status in _TERMINAL_CREATION:
                raise CodedApiError("already_terminal", "العملية خلاص في حالة نهائية.", 409)
            # OHB2-PHASE1D-F1: وجود `task_id` = الـ POST البدء رجع فعلاً ⇒ مفيش ادّعاء
            # "قبل الإرسال" وممنوع الشطب (كان بيضيّع conversation_id ويحوّل شات بعيد
            # حقيقي لـ discarded). نرجّع الحالة الحالية + علامة "not_confirmed".
            if status in _NOT_CONFIRMED_CREATION or _creation_post_started(job):
                # الـ POST ممكن يكون بدأ ⇒ مفيش ادّعاء إلغاء. نرجّع الحالة الحالية + علامة.
                log.info("reconcile: creation=%s cancel not confirmed (state=%s)", job_id, status)
                dto = self._creation_dto(job)
                dto["cancellation"] = "not_confirmed"
                return dto
            # CAS ذرّي: الشرط جوّه الـ UPDATE ⇒ لو الـ worker حجز/بدأ بين القراءة والكتابة
            # الـ rowcount=0 (مفيش clobber). نفس دلالات أمر البوت `outbox_discard`.
            outcome = self._db.discard_creation_job(
                job_id, outbox.now_iso(), "اتلغى يدوياً", chat_id=self._config.owner_id
            )
            if outcome == "discarded":
                log.info("reconcile: creation=%s cancel", job_id)
                result = self._creation_dto(self._db.get_creation_job(job_id, self._config.owner_id))
                result["cancellation"] = "discarded"
                return result
            current = self._db.get_creation_job(job_id, self._config.owner_id)
            if current is not None and current.status in _NOT_CONFIRMED_CREATION:
                dto = self._creation_dto(current)
                dto["cancellation"] = "not_confirmed"
                return dto
            raise CodedApiError("already_terminal", "العملية خلاص في حالة نهائية.", 409)
        # mark_sent ⇒ done
        if status == db_module.CREATION_DONE:
            return self._creation_dto(job)  # idempotent
        if status != db_module.CREATION_UNKNOWN:
            raise CodedApiError("invalid_state", "الأمر ده للطلبات 'ambiguous' بس.", 409)
        changed = self._db.set_creation_status_if_in(
            job_id,
            db_module.CREATION_DONE,
            outbox.now_iso(),
            {db_module.CREATION_UNKNOWN},
            "أكّده المالك",
            chat_id=self._config.owner_id,
        )
        if not changed:
            current = self._db.get_creation_job(job_id, self._config.owner_id)
            if current is not None and current.status == db_module.CREATION_DONE:
                return self._creation_dto(current)
            raise CodedApiError("invalid_state", "الأمر ده للطلبات 'ambiguous' بس.", 409)
        log.info("reconcile: creation=%s mark_sent", job_id)
        return self._creation_dto(self._db.get_creation_job(job_id, self._config.owner_id))

    def find_outbox_operation(self, conversation_id: str, client_ref: str) -> dict | None:
        """يبحث عن عملية برومت بمعرّف العميل (للاستعلام بعد نتيجة غامضة) أو None."""
        if self._db is None:
            raise ApiError("قاعدة البيانات مش متاحة دلوقتي.", 503)
        cid = _require_id(conversation_id)
        ref = _require_ref(client_ref)
        if not ref:
            raise ValidationError("معرّف العملية مطلوب")
        item = self._db.find_outbox_by_ref(cid, self._config.owner_id, ref)
        return self._outbox_dto(item) if item else None

    def find_creation_operation(self, client_ref: str) -> dict | None:
        """يبحث عن عملية إنشاء شات بمعرّف العميل (للاستعلام بعد نتيجة غامضة) أو None."""
        if self._db is None:
            raise ApiError("قاعدة البيانات مش متاحة دلوقتي.", 503)
        ref = _require_ref(client_ref)
        if not ref:
            raise ValidationError("معرّف العملية مطلوب")
        job = self._db.find_creation_job_by_ref(self._config.owner_id, ref)
        return self._creation_dto(job) if job else None

    @staticmethod
    def _outbox_dto(item) -> dict:
        return {
            "kind": "prompt",
            "id": item.id,
            "conversation_id": item.conversation_id,
            "state": _OUTBOX_STATES.get(item.status, "unknown"),
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }

    @staticmethod
    def _creation_dto(job) -> dict:
        status = job.status
        terminal = status in _TERMINAL_CREATION
        # OHB2-PHASE1D-F1: حدّ الإرسال بيتحسب بالحالة **ووجود task_id**. أي صف عليه
        # task_id = الـ POST البدء رجع فعلاً ⇒ ممنوع ندّعي "لسه مابدأش" وممنوع نسمح
        # بإلغاء يدّعي إنه قبل الإرسال (كان بيحوّل شات بعيد حقيقي لـ discarded ويضيّع
        # conversation_id). مفيش أي تراجع في at-most-once: الإلغاء لسه CAS على الحالات.
        post_started = _creation_post_started(job)
        return {
            "kind": "creation",
            "id": job.id,
            "repository": job.repo or "",
            "state": _CREATION_STATES.get(status, "unknown"),
            # OHB2-PHASE1D: حقول آمنة مشتقّة على السيرفر (مش من الواجهة) لوصف حدّ الإرسال
            # والعمليات المتاحة. القرار النهائي يفضل جوّه `reconcile_creation` (إعادة فحص).
            "post_state": ("uncertain" if post_started else "not_started")
            if status in _DISCARDABLE_CREATION
            else _CREATION_POST_STATE.get(status, "uncertain"),
            "terminal": terminal,
            "cancellable": status in _DISCARDABLE_CREATION and not post_started,
            "resolvable": status == db_module.CREATION_UNKNOWN,
            "conversation_id": job.conversation_id or "",
            "created_at": job.created_at,
            "updated_at": job.updated_at,
        }

    # ----------------------------------------------------------- watches
    def list_watches(self, page: int = 0) -> dict:
        if features.is_hidden("followups"):
            raise ApiError("الميزة دي مش متاحة دلوقتي.", 404)
        if self._db is None:
            raise ApiError("قاعدة البيانات مش متاحة دلوقتي.", 503)
        items = self._db.list_watched()
        page = _page_number(page)
        start = _page_offset(page, PAGE_SIZE)
        chunk = items[start : start + PAGE_SIZE]
        if not chunk and page > 0:
            page, start, chunk = 0, 0, items[:PAGE_SIZE]
        return {
            "page": page,
            "has_more": len(items) > start + PAGE_SIZE,
            "items": [
                {
                    "id": w.conversation_id,
                    "title": w.title or "",
                    "last_state": w.last_state or "",
                    "added_at": w.added_at or "",
                }
                for w in chunk
            ],
        }

    async def watch(self, conversation_id: str) -> dict:
        cid = _require_id(conversation_id)
        if features.is_hidden("followups"):
            raise ApiError("الميزة دي مش متاحة دلوقتي.", 404)
        if self._db is None:
            raise ApiError("قاعدة البيانات مش متاحة دلوقتي.", 503)
        # OHB2-09-A2-02: نفس عقد الملكية قبل إضافة الشات للمتابعة (مفيش شات غير مملوك).
        # F-1: `allow_deleted=True` — زر «متابعة» هو **إعادة التفاعل الصريح** الوحيد
        # الموثّق اللي بيشيل الشاهد ويبدأ دورة نظيفة (طبقة القاعدة عبر `reengage=True`).
        # ده مش مسار قراءة، فبنستثنيه من فرض الشاهد عن قصد.
        conv = await self._authorize_conversation(cid, allow_deleted=True)
        self._db.add_watched(cid, conv.get("title", ""), self._config.owner_id, new_lifecycle=False, reengage=True)
        self._db.set_last_state(cid, conv.get("execution_status") or "")
        return {"ok": True, "watched": True}

    def unwatch(self, conversation_id: str) -> dict:
        """يلغي متابعة الشات. **مابيتحقّقش من ملكية الشات قصدًا** (OHB2-09-A2-02).

        السبب: دي عملية على **قايمة متابعات المالك نفسه** (حالة مالك واحد)، مش قراءة
        بيانات شات. فرض شرط وجود/ملكية الشات هنا كان هيمنع إلغاء متابعة شات اتحذف أو
        اتغيّر من ناحية OpenHands (حالة عالقة)، وكمان كان هيكسر التكافؤ مع أمر البوت
        `unwatch_conversation` (اللي مابيفحصش الملكية برضه). الحماية المطلوبة موجودة:
        جلسة المالك + origin/CSRF (state_changing) + معرّف صالح، والإزالة محصورة في
        قايمة المالك. عشان كده unwatch **مستثنى** من فحص الملكية عن قصد، بعكس المسارات
        اللي بترجّع بيانات (تفاصيل/حالة/تكلفة/ملفات/تصدير/متابعة-إضافة).
        """
        cid = _require_id(conversation_id)
        if features.is_hidden("followups"):
            raise ApiError("الميزة دي مش متاحة دلوقتي.", 404)
        if self._db is None:
            raise ApiError("قاعدة البيانات مش متاحة دلوقتي.", 503)
        # نمرّ عبر المراقب لو موجود (زي البوت) عشان أي تسليم معلّق يتحلّ ذرّيًا.
        remover = self._db.remove_watched
        if self._application is not None:
            watcher = self._application.bot_data.get("watcher")
            if watcher is not None:
                remover = watcher.unwatch
        remover(cid)
        return {"ok": True, "watched": False}

    # -------------------------------------------------------- repositories
    async def list_repositories(self, query: str = "", page: int = 0) -> dict:
        client = self._require_client()
        repos = await client.search_repositories(query=(query or "").strip())
        page = _page_number(page)
        start = _page_offset(page, 8)
        chunk = repos[start : start + 8]
        if not chunk and page > 0:
            page, start, chunk = 0, 0, repos[:8]
        return {
            "page": page,
            "has_more": len(repos) > start + 8,
            "items": [
                {
                    "full_name": r.get("full_name") or "",
                    "private": bool(r.get("private")),
                }
                for r in chunk
            ],
        }

    # ------------------------------------------------------------ new chat
    async def create_chat(
        self, repository: str, text: str, client_ref: str | None = None
    ) -> dict:
        """يسجّل طلب شات جديد في جدول المهام المتين وينبّه الـ worker المالك.

        `client_ref` (OHB2-07): معرّف عملية من العميل. لو نفس الطلب اتبعت تاني
        (double-tap/إعادة محاولة)، بنرجّع نفس الطلب بدل ما نبدأ شات مكرّر.
        """
        repo = _optional_repo(repository)
        body = _require_text(text)
        ref = _require_ref(client_ref)
        if self._db is None:
            raise ApiError("قاعدة البيانات مش متاحة دلوقتي.", 503)
        job_id = self._db.add_creation_job(
            self._config.owner_id, repo, body, outbox.now_iso(), client_ref=ref or None
        )
        self._drop_list_cache()
        self._wake("creation_worker")
        return {
            "ok": True,
            "queued": True,
            "job_id": job_id,
            "operation": self.creation_operation(job_id),
        }
