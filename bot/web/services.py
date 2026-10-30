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
import time

from ..errors import ApiError
from ..messages import get_status, pr_url, state_label, truncate
from .. import features
from .. import outbox
from .. import db as db_module

log = logging.getLogger(__name__)

PAGE_SIZE = 10
MAX_PROMPT_CHARS = 8000
MAX_REPO_LEN = 200
MAX_ID_LEN = 200
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


class ValidationError(ValueError):
    """مدخل غير صالح من العميل (بترجع 400 بشكل منظّم)."""


def _require_id(value: str | None) -> str:
    text = (value or "").strip()
    if not text or len(text) > MAX_ID_LEN or any(ch.isspace() for ch in text):
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


def _page(value) -> int:
    try:
        page = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, page)


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


class MiniAppService:
    """عمليات الـ Mini App فوق نفس client/db/outbox بتاع البوت."""

    def __init__(self, config, db, client=None, application=None) -> None:
        self._config = config
        self._db = db
        self._client = client
        self._application = application

    # ------------------------------------------------------------ helpers
    def _require_client(self):
        if self._client is None:
            raise ApiError("خدمة OpenHands مش متاحة دلوقتي.", 503)
        return self._client

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
        }

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
        convs = await client.get_conversations([cid])
        if not convs:
            raise ApiError("الشات مش موجود.", 404)
        conv = convs[0]
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
        client = self._require_client()
        convs = await client.get_conversations([cid])
        if not convs:
            raise ApiError("الشات مش موجود.", 404)
        return _conversation_dto(convs[0], cid in self._watched_ids())

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
        client = self._require_client()
        convs = await client.get_conversations([cid])
        if not convs:
            raise ApiError("الشات مش موجود.", 404)
        conv = convs[0]
        self._db.add_watched(cid, conv.get("title", ""), self._config.owner_id, new_lifecycle=False)
        self._db.set_last_state(cid, conv.get("execution_status") or "")
        return {"ok": True, "watched": True}

    def unwatch(self, conversation_id: str) -> dict:
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
