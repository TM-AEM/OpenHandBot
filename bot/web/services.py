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

from ..errors import ApiError
from ..messages import get_status, pr_url, state_label, truncate
from .. import features
from .. import outbox
from .. import db as db_module
from ..db import INBOX_PAGE_SIZE
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
    db_module.OUTBOX_DISCARDED: "failed",
}
_CREATION_STATES = {
    db_module.CREATION_PENDING: "pending",
    db_module.CREATION_CLAIMED: "pending",
    db_module.CREATION_STARTING: "pending",
    db_module.CREATION_DONE: "accepted",
    db_module.CREATION_FAILED: "failed",
    db_module.CREATION_UNKNOWN: "ambiguous",
    db_module.CREATION_DISCARDED: "failed",
}
# OHB2-09-05: الحالات النهائية للصندوق (نفس مجموعة البوت في handlers). التسوية اليدوية
# على سجل نهائي ⇒ 409 (مفيش تغيير)، عشان ما نلخبطش حالة محسومة.
_TERMINAL_OUTBOX = {db_module.OUTBOX_SENT, db_module.OUTBOX_FAILED, db_module.OUTBOX_DISCARDED}
# الحالات غير النهائية اللي `discard` يقدر يحوّلها (شرط CAS الذرّي — OHB2-09-05-R1).
_NON_TERMINAL_OUTBOX = {
    db_module.OUTBOX_PENDING,
    db_module.OUTBOX_CLAIMED,
    db_module.OUTBOX_SENDING,
    db_module.OUTBOX_UNKNOWN,
}


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


def _require_text(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        raise ValidationError("النص مطلوب")
    if len(text) > MAX_PROMPT_CHARS:
        raise ValidationError("النص طويل أوي")
    return text


def _require_repo(value: str | None) -> str:
    text = (value or "").strip()
    if not text or len(text) > MAX_REPO_LEN:
        raise ValidationError("اسم المستودع غير صالح")
    parts = text.split("/")
    if len(parts) != 2 or not all(parts):
        raise ValidationError("اسم المستودع لازم يكون بالشكل owner/repo")
    if any(ch.isspace() for ch in text):
        raise ValidationError("اسم المستودع غير صالح")
    return text


def _require_ref(value: str | None) -> str:
    """يتحقّق من معرّف العملية اللي العميل يولّده (idempotency) أو يرجّع فاضي."""
    text = (value or "").strip()
    if not text:
        return ""
    if len(text) > MAX_REF_LEN or not all(ch.isalnum() or ch in "-_" for ch in text):
        raise ValidationError("معرّف العملية غير صالح")
    return text


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

    async def _authorize_conversation(self, conversation_id: str) -> dict:
        """يفوّض شات واحد عبر الخدمة المشتركة **قبل** أي جلب بيانات محمية (OHB2-09-A2-02).

        بترجّع الميتاداتا المتفوَّض عليها أو بترمي `FileApiError` منظّم (403/404/502).
        كل مسار شات في الـ Mini App بيعدي من هنا — مفيش مقارنة مالك مكرّرة في مسار.
        """
        client = self._require_client()
        if self._identity is None:
            self._identity = IdentityCache(client)
        conv, status = await authorize_conversation(client, self._identity, conversation_id)
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
        """ينبّه الـ worker المالك الموجود (نفس العملية) لو موجود — بدون إنشاء worker."""
        if self._application is None:
            return
        worker = self._application.bot_data.get(key)
        if worker is not None:
            worker.wake()

    def _list_cache(self):
        if self._application is None:
            return None
        return self._application.bot_data.get("list_cache")

    def _set_list_cache(self, items) -> None:
        if self._application is not None:
            self._application.bot_data["list_cache"] = (time.monotonic(), items)

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
    def list_notifications(self, page: int = 0, unread_only: bool = False) -> dict:
        """قايمة صندوق الإشعارات (الأحدث أولًا) بترقيم محدود على مستوى SQL.

        payload محدود (LIMIT/OFFSET) زي باقي القوايم؛ `unread_count` بيساعد الواجهة
        تعرض شارة غير المقروء من غير ما تجيب كل الصفحات. لو القاعدة مش متاحة، نرجّع
        فاضي بدل ما نكسّر الصفحة (زي `bootstrap`).
        """
        if self._db is None:
            return {"page": 0, "has_more": False, "unread_count": 0, "items": []}
        page = max(0, page)
        offset = page * INBOX_PAGE_SIZE
        items = self._db.list_inbox(
            limit=INBOX_PAGE_SIZE, offset=offset, unread_only=unread_only
        )
        # لو الصفحة فاضية بسبب تجاوز الحد، نرجع للأولى (زي قايمة المتابعات).
        if not items and page > 0:
            page, offset = 0, 0
            items = self._db.list_inbox(limit=INBOX_PAGE_SIZE, offset=0, unread_only=unread_only)
        total = self._db.count_inbox(unread_only=unread_only)
        return {
            "page": page,
            "has_more": total > offset + len(items),
            "unread_count": self._db.count_inbox(unread_only=True),
            "items": [self._inbox_dto(it) for it in items],
        }

    @staticmethod
    def _inbox_dto(item) -> dict:
        return {
            "id": item.id,
            "conversation_id": item.conversation_id,
            "title": item.title or "",
            "kind": item.kind or "",
            "message": item.message or "",
            "created_at": item.created_at or "",
            "read": not item.unread,
            # OHB2-08-05 (Batch 3R): حالة التسليم المتينة — عشان الواجهة تفرّق بين
            # إشعار اتسلّم وإشعار لسه معلّق أو فشل (event-first، مش تسجيل تاريخي بس).
            "delivery_status": getattr(item, "delivery_status", None) or "delivered",
            "delivery_attempts": int(getattr(item, "delivery_attempts", 0) or 0),
            "delivered_at": getattr(item, "delivered_at", None),
        }

    def mark_notification_read(self, item_id) -> dict:
        if self._db is None:
            raise ApiError("قاعدة البيانات مش متاحة دلوقتي.", 503)
        try:
            ident = int(item_id)
        except (TypeError, ValueError):
            raise ValidationError("معرّف الإشعار غير صالح")
        if ident <= 0:
            raise ValidationError("معرّف الإشعار غير صالح")
        ok = self._db.mark_inbox_read(ident, outbox.now_iso())
        if not ok:
            raise ApiError("الإشعار مش موجود.", 404)
        return {"ok": True, "unread_count": self._db.count_inbox(unread_only=True)}

    def mark_all_notifications_read(self) -> dict:
        if self._db is None:
            raise ApiError("قاعدة البيانات مش متاحة دلوقتي.", 503)
        changed = self._db.mark_all_inbox_read(outbox.now_iso())
        return {"ok": True, "marked": changed, "unread_count": self._db.count_inbox(unread_only=True)}

    # ------------------------------------------------------ conversations
    async def list_conversations(self, page: int = 0, refresh: bool = False) -> dict:
        client = self._require_client()
        cache = self._list_cache()
        # TASK 55 (G4): نفس كاش البوت القصير — مشارك بين البوت والـ Mini App.
        if not refresh and cache and time.monotonic() - cache[0] < 45.0:
            items = cache[1]
        else:
            result = await client.search_conversations(limit=100)
            items = result.get("items", [])
            if items:
                self._set_list_cache(items)
        page = max(0, page)
        start = page * PAGE_SIZE
        chunk = items[start : start + PAGE_SIZE]
        if not chunk and page > 0:
            page, start, chunk = 0, 0, items[:PAGE_SIZE]
        watched = self._watched_ids()
        return {
            "page": page,
            "has_more": len(items) > start + PAGE_SIZE,
            "items": [self._list_item(c, watched) for c in chunk],
        }

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
        return FileService(client, identity=self._identity)

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
        await self._authorize_conversation(cid)
        chat_id = self._config.owner_id
        outbox_id = self._db.add_or_group_outbox(
            cid, chat_id, body, outbox.now_iso(), client_ref=ref or None
        )
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
        """حالة عملية برومت (DTO آمن: مفيش نص البرومت ولا تفاصيل داخلية خام)."""
        if self._db is None:
            raise ApiError("قاعدة البيانات مش متاحة دلوقتي.", 503)
        item = self._db.get_outbox(outbox_id)
        if item is None:
            raise ApiError("العملية مش موجودة.", 404)
        return self._outbox_dto(item)

    def creation_operation(self, job_id: int) -> dict:
        """حالة عملية إنشاء شات (DTO آمن)."""
        if self._db is None:
            raise ApiError("قاعدة البيانات مش متاحة دلوقتي.", 503)
        job = self._db.get_creation_job(job_id)
        if job is None:
            raise ApiError("العملية مش موجودة.", 404)
        return self._creation_dto(job)

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
        item = self._db.get_outbox(outbox_id)
        if item is None:
            raise ApiError("العملية مش موجودة.", 404)
        status = item.status
        if action == "discard":
            if status in _TERMINAL_OUTBOX:
                raise CodedApiError("already_terminal", "العملية خلاص في حالة نهائية.", 409)
            # CAS ذرّي: شرط الحالة جوّه الـ UPDATE نفسه، فلو سجل تاني سبقنا وحسم الحالة
            # بين القراءة والكتابة، الـ rowcount=0 ⇒ ما بنغيّرش حاجة (مفيش سباق read-then-write).
            changed = self._db.set_outbox_status_if_in(
                outbox_id,
                db_module.OUTBOX_DISCARDED,
                outbox.now_iso(),
                _NON_TERMINAL_OUTBOX,
                "اتشال يدوياً",
            )
            if not changed:
                raise CodedApiError("already_terminal", "العملية خلاص في حالة نهائية.", 409)
            log.info("reconcile: outbox=%s discard", outbox_id)
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
                current = self._db.get_outbox(outbox_id)
                if current is not None and current.status == db_module.OUTBOX_SENT:
                    return self._outbox_dto(current)
                raise CodedApiError("invalid_state", "الأمر ده للسجلات 'unknown' بس.", 409)
            log.info("reconcile: outbox=%s mark_sent", outbox_id)
        return self._outbox_dto(self._db.get_outbox(outbox_id))

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
        return {
            "kind": "creation",
            "id": job.id,
            "repository": job.repo or "",
            "state": _CREATION_STATES.get(job.status, "unknown"),
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
        page = max(0, page)
        start = page * PAGE_SIZE
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
        conv = await self._authorize_conversation(cid)
        self._db.add_watched(cid, conv.get("title", ""), self._config.owner_id, new_lifecycle=False)
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
        page = max(0, page)
        start = page * 8
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
        repo = _require_repo(repository)
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
