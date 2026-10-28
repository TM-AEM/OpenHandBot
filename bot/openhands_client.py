"""عميل رقيق للـ OpenHands Cloud API (V1).

كل المسارات تحت {base_url}/api/v1.المصادقة بـ Authorization: Bearer.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx

from .errors import ApiError, describe_status

EVENTS_PER_PAGE = 20
SEARCH_LIMIT = 20
REPOS_PAGE_SIZE = 8
# TASK 55 (المرحلة A): حدود طلبي آخر تبادل. رسالة المستخدم ممكن تقع برا أول 20
# MessageEvent لو الـ agent عمل خطوات أدوات كتير، فبنفلتر بالنوع بدل ما نجرّب نلمّ كل حاجة.
EXCHANGE_MSG_LIMIT = 20
EXCHANGE_ACTION_LIMIT = 30


class OpenHandsClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0, transport=None) -> None:
        self._base = base_url.rstrip("/") + "/api/v1"
        self._client = httpx.AsyncClient(
            base_url=self._base,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
            timeout=timeout,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "OpenHandsClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    # ------------------------------------------------------------------ HTTP
    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            resp = await self._client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise ApiError(f"تعذّر الاتصال بـ OpenHands ({type(exc).__name__}).") from exc
        if resp.status_code >= 400:
            raise ApiError(describe_status(resp.status_code, _detail(resp)), resp.status_code)
        return resp

    async def _get(self, url: str, params: Any = None) -> Any:
        resp = await self._request("GET", url, params=params)
        return _decode_json(resp)

    # -------------------------------------------------------- conversations
    async def search_conversations(self, limit: int = SEARCH_LIMIT, page_id: str | None = None) -> dict:
        params: dict[str, Any] = {"limit": limit}
        if page_id:
            params["page_id"] = page_id
        data = await self._get("/app-conversations/search", params=params)
        items = data.get("items", data) if isinstance(data, dict) else data
        items = [it for it in items if it]
        items.sort(key=lambda it: it.get("updated_at") or "", reverse=True)
        next_page = data.get("next_page_id") if isinstance(data, dict) else None
        return {"items": items, "next_page_id": next_page}

    async def get_conversations(self, ids: list[str]) -> list[dict]:
        if not ids:
            return []
        params = [("ids", cid) for cid in ids]
        data = await self._get("/app-conversations", params=params)
        # الموثّق: مصفوفة (عناصرها ممكن تكون null). لو الشكل غير متوقع ما نفسّرش قايمة
        # فاضية كأن مفيش شات — نرمي خطأ API آمن عشان المستخدم مايتخدعش.
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict) and isinstance(data.get("items"), list):
            items = data["items"]
        else:
            raise ApiError("رد غير متوقع من OpenHands")
        return [it for it in items if isinstance(it, dict)]

    async def search_events(
        self,
        conversation_id: str,
        limit: int = EVENTS_PER_PAGE,
        kind: str | None = None,
    ) -> list[dict]:
        params: dict[str, Any] = {"sort_order": "TIMESTAMP_DESC", "limit": limit}
        if kind:
            params["kind__eq"] = kind
        data = await self._get(f"/conversation/{conversation_id}/events/search", params=params)
        items = data.get("items", data) if isinstance(data, dict) else data
        return [e for e in items if e]

    async def get_last_reply(self, conversation_id: str) -> str | None:
        """يرجّع آخر رد للـ agent أو تقرير FinishAction."""
        events = await self.search_events(conversation_id, limit=50)
        for event in events:
            text = _agent_report(event)
            if text:
                return text
        return None

    async def get_reply_since(self, conversation_id: str, since: datetime) -> str | None:
        """آخر رد/تقرير للـ agent حدث *بعد* `since` بالظبط، أو None (U01).

        الأحداث بترجع من الأحدث للأقدم. أي حدث من غير timestamp مفهوم مابيتحسبش
        (fail closed): ما نقدرش نثبت إنه أحدث من البرومبت.
        """
        events = await self.search_events(conversation_id, limit=50)
        for event in events:
            ts = parse_timestamp(event.get("timestamp"))
            if ts is None:
                continue
            if ts <= since:
                break
            text = _agent_report(event)
            if text:
                return text
        return None

    async def get_last_exchange(self, conversation_id: str) -> tuple[str | None, str | None]:
        """(آخر رسالة للمستخدم، آخر رد/تقرير للـ agent). أي منهم ممكن يكون None."""
        msg_events, action_events = await asyncio.gather(
            self.search_events(conversation_id, limit=EXCHANGE_MSG_LIMIT, kind="MessageEvent"),
            self.search_events(conversation_id, limit=EXCHANGE_ACTION_LIMIT, kind="ActionEvent"),
        )
        user_text: str | None = None
        agent_msg: tuple | None = None  # (timestamp | None, text)
        for event in msg_events:
            source = event.get("source")
            if source == "user":
                if user_text is None:
                    text = _message_text(event)
                    if text:
                        user_text = text
            elif source == "agent" and agent_msg is None:
                text = _agent_report(event)
                if text:
                    agent_msg = (parse_timestamp(event.get("timestamp")), text)
            if user_text is not None and agent_msg is not None:
                break
        finish: tuple | None = None
        for event in action_events:
            text = _agent_report(event)  # بيرجّع نص FinishAction بس لـ ActionEvent
            if text:
                finish = (parse_timestamp(event.get("timestamp")), text)
                break
        return user_text, _pick_newer(agent_msg, finish)

    async def list_files(self, conversation_id: str, path: str = "") -> list[str]:
        params: dict[str, Any] = {}
        if path:
            params["path"] = path
        data = await self._get(f"/app-conversations/{conversation_id}/files", params=params or None)
        items = data if isinstance(data, list) else data.get("items", [])
        return [f for f in items if isinstance(f, str)]

    async def read_file(self, conversation_id: str, file_path: str) -> str:
        """محتوى ملف واحد. الباراميتر اسمه `file_path` (مش `path`)."""
        data = await self._get(
            f"/app-conversations/{conversation_id}/file", params={"file_path": file_path}
        )
        return data if isinstance(data, str) else ""

    async def export_conversation(self, conversation_id: str) -> bytes:
        """تصدير الشات كـ zip (events + meta)، مش ملفات الـ workspace."""
        resp = await self._request("GET", f"/app-conversations/{conversation_id}/download")
        return resp.content

    async def send_message(self, conversation_id: str, text: str) -> None:
        body = {"role": "user", "content": [{"type": "text", "text": text}], "run": True}
        await self._request("POST", f"/app-conversations/{conversation_id}/send-message", json=body)

    async def resume_sandbox(self, sandbox_id: str) -> None:
        await self._request("POST", f"/sandboxes/{sandbox_id}/resume")

    async def start_conversation(
        self, initial_message: str, repository: str | None, branch: str | None = None
    ) -> str:
        body: dict[str, Any] = {
            "initial_message": {"content": [{"type": "text", "text": initial_message}]},
        }
        if repository:
            body["selected_repository"] = repository
        if branch:
            body["selected_branch"] = branch
        data = await self._request("POST", "/app-conversations", json=body)
        payload = data.json()
        task_id = payload.get("id")
        if not task_id:
            raise ApiError("الـ API ما رجّعش معرّف مهمة البدء")
        return task_id

    async def get_start_task(self, task_id: str) -> dict:
        """يقرأ حالة مهمة البدء (GET آمن قابل للتكرار — مش بينشئ أي حاجة).

        بترجّع dict المهمة (فاضي لو لسه مفيش بيانات). دي الطريقة الموثّقة الوحيدة
        لمتابعة مهمة بدء موجودة، فالاستطلاع بيها آمن.
        """
        data = await self._get("/app-conversations/start-tasks", params={"ids": task_id})
        tasks = data if isinstance(data, list) else data.get("items", [])
        return next((t for t in tasks if t), {}) or {}

    async def wait_for_start(self, task_id: str, timeout: float = 180.0, interval: float = 3.0) -> str:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            task = await self.get_start_task(task_id)
            if task:
                status = str(task.get("status", "")).upper()
                if status == "READY":
                    app_id = task.get("app_conversation_id")
                    if not app_id:
                        raise ApiError("المهمة جاهزة بس ما فيهاش app_conversation_id")
                    return app_id
                # "ERROR" هي القيمة الوحيدة الموثّقة للفشل في enum الـ API (مفيش "FAILED").
                # بنعتبرها غامضة (زي timeout): الـ API مابيقولش إنه مافيش شات اتعمل، فممنوع
                # نعيد POST تلقائياً. التصنيف النهائي بيحصل عند الـ caller (unknown مش failed).
                if status == "ERROR":
                    raise ApiError("فشل بدء الشات على OpenHands")
            await asyncio.sleep(interval)
        raise ApiError("انتهى وقت انتظار بدء الشات")

    async def search_repositories(self, query: str = "", limit: int = 100) -> list[dict]:
        params: dict[str, Any] = {"provider": "github", "limit": limit}
        if query:
            params["query"] = query
        data = await self._get("/git/repositories/search", params=params)
        items = data.get("items", data) if isinstance(data, dict) else data
        return [r for r in items if r]


def _decode_json(resp: httpx.Response) -> Any:
    """يفك جسم الرد كـ JSON، وأي جسم مش JSON يتحوّل لخطأ API آمن (مفيش JSONDecodeError خام).

    بيعيد استخدام نفس قواعد الـ API: خطأ بدون status_code (غامض)، ورسالة ثابتة مفيهاش
    أي جسم رد أو أسرار.
    """
    try:
        return resp.json()
    except ValueError as exc:
        raise ApiError("رد غير متوقع من OpenHands") from exc


def parse_timestamp(value: Any) -> datetime | None:
    """يحوّل طابع ISO-8601 لـ datetime واعي بالتوقيت. القيم غير المفهومة ⇒ None.

    الطوابع بدون منطقة زمنية بتتعامل كـ UTC.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _agent_report(event: dict) -> str | None:
    """نص رد الـ agent (MessageEvent من agent) أو تقرير FinishAction، وإلا None."""
    kind = event.get("kind")
    if kind == "MessageEvent" and event.get("source") == "agent":
        text = _message_text(event)
        if text:
            return text
    if kind == "ActionEvent":
        action = event.get("action") or {}
        if action.get("kind") == "FinishAction":
            text = action.get("message")
            if isinstance(text, str) and text.strip():
                return text
    return None


def _pick_newer(msg: tuple | None, finish: tuple | None) -> str | None:
    """الأحدث بالـ timestamp. عند التساوي أو غياب الطوابع: الأفضلية لتقرير FinishAction."""
    if msg is None:
        return finish[1] if finish else None
    if finish is None:
        return msg[1]
    (t_msg, text_msg), (t_fin, text_fin) = msg, finish
    if t_msg is not None and t_fin is not None:
        return text_msg if t_msg > t_fin else text_fin
    if t_msg is not None:
        return text_msg
    return text_fin


def _message_text(event: dict) -> str:
    message = event.get("llm_message") or {}
    parts = message.get("content") or []
    chunks = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("type") == "text"]
    return "".join(chunks).strip()


def _detail(resp: httpx.Response) -> str:
    """تفاصيل آمنة للخطأ: حقل `detail` من جسم JSON بس (موثّق ومحدود).

    أي جسم مش JSON (HTML/proxy/غير متوقع) مايتعرضش خالص — ممكن يحتوي تفاصيل حساسة.
    """
    try:
        data = resp.json()
    except ValueError:
        return ""
    if isinstance(data, dict) and "detail" in data:
        return str(data["detail"])[:300]
    return ""
