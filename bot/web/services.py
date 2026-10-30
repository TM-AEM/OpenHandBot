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

log = logging.getLogger(__name__)

PAGE_SIZE = 10
MAX_PROMPT_CHARS = 8000
MAX_REPO_LEN = 200
MAX_ID_LEN = 200


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

    async def send_prompt(self, conversation_id: str, text: str) -> dict:
        """يسجّل البرومت في الصندوق المتين (نفس مسار البوت) وينبّه الـ worker المالك."""
        cid = _require_id(conversation_id)
        body = _require_text(text)
        if self._db is None:
            raise ApiError("قاعدة البيانات مش متاحة دلوقتي.", 503)
        chat_id = self._config.owner_id
        outbox_id = self._db.add_or_group_outbox(cid, chat_id, body, outbox.now_iso())
        self._drop_list_cache()
        self._wake("outbox_worker")
        return {"ok": True, "queued": True, "outbox_id": outbox_id}

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
    async def create_chat(self, repository: str, text: str) -> dict:
        """يسجّل طلب شات جديد في جدول المهام المتين وينبّه الـ worker المالك."""
        repo = _require_repo(repository)
        body = _require_text(text)
        if self._db is None:
            raise ApiError("قاعدة البيانات مش متاحة دلوقتي.", 503)
        job_id = self._db.add_creation_job(self._config.owner_id, repo, body, outbox.now_iso())
        self._drop_list_cache()
        self._wake("creation_worker")
        return {"ok": True, "queued": True, "job_id": job_id}
