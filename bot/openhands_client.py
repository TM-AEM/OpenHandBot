"""عميل رقيق للـ OpenHands Cloud API (V1).

كل المسارات تحت {base_url}/api/v1.المصادقة بـ Authorization: Bearer.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import httpx

from .errors import ApiError, ResponseTooLargeError, describe_status

EVENTS_PER_PAGE = 20
SEARCH_LIMIT = 20
REPOS_PAGE_SIZE = 8
# TASK 55 (المرحلة A): حدود طلبي آخر تبادل. رسالة المستخدم ممكن تقع برا أول 20
# MessageEvent لو الـ agent عمل خطوات أدوات كتير، فبنفلتر بالنوع بدل ما نجرّب نلمّ كل حاجة.
EXCHANGE_MSG_LIMIT = 20
EXCHANGE_ACTION_LIMIT = 30

# OHB2-09-01-FIX: حد صلب على بايتات جسم رد قراءة الملف (بثّ تراكمي).
# مطابق لـ `files.MAX_PREVIEW_BYTES` عشان الاتنين يفضلوا متسقين (مفيش استيراد دائري:
# الملفات بتستورد العميل، فالعميل مايستوردش الملفات). أي تعديل في حد المعاينة لازم
# يتنعكس هنا برضه.
MAX_FILE_RESPONSE_BYTES = 256 * 1024
# حد صلب لجسم رد الأخطاء (تفاصيل `detail`) — منع تخزين جسم خطأ ضخم.
MAX_ERROR_DETAIL_BYTES = 8 * 1024
# OHB2-09-03: حد صلب لتنزيل تصدير الشات (zip أحداث+ميتا). التنزيل بيتحمّل في الذاكرة
# قبل الإرسال على تيليجرام، فبنديه حد. الرد عادةً مضغوط أصلاً (zip)، فبنطلب `identity`
# وبنقرا الخام عشان نمنع أي تضخيم من ضغط إضافي.
MAX_EXPORT_BYTES = 16 * 1024 * 1024


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
        # OHB2-N10-28D: 3xx إعادة توجيه **مش** نجاح — كل endpoints الـ API بترجّع 2xx
        # مباشر، وأي redirect (301/302/303/307/308) معناه رد غير متوقّع (proxy/login)
        # وممنوع نعتبره عملية ناجحة أو نتبع وجهته (مفيش forward لهيدر Authorization).
        if 300 <= resp.status_code < 400:
            raise ApiError("رد إعادة توجيه غير متوقّع من OpenHands.", resp.status_code)
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
        items = _as_items(data)
        items = [it for it in items if isinstance(it, dict) and it]
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
        items = _as_items(data)
        return [e for e in items if isinstance(e, dict) and e]

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
        items = _as_items(data)
        return [f for f in items if isinstance(f, str)]

    async def read_file(self, conversation_id: str, file_path: str) -> str:
        """محتوى ملف واحد. الباراميتر اسمه `file_path` (مش `path`)."""
        data = await self._get(
            f"/app-conversations/{conversation_id}/file", params={"file_path": file_path}
        )
        return data if isinstance(data, str) else ""

    async def read_file_text(self, conversation_id: str, file_path: str) -> str | None:
        """نص ملف واحد، أو None لو الرد مش نص (شكل غير متوقع — آمن للتمييز عن ملف فاضي).

        (OHB2-09-01) بتفرّق بين ملف فاضي فعلاً (`""`) ورد مش نص: طبقة الملفات الآمنة
        بتعامل None كخطأ upstream بدل ما تعرض ملف فاضي مضلّل.

        تحذير: دي الطريقة **غير المحدودة** (httpx بيلمّ الجسم كله في الذاكرة). استخدمها
        بس لمدخلات موثوقة/صغيرة. مسار قراءة الملفات في `FileService` بيستخدم
        `read_file_text_bounded` بدلها.
        """
        data = await self._get(
            f"/app-conversations/{conversation_id}/file", params={"file_path": file_path}
        )
        return data if isinstance(data, str) else None

    async def read_file_text_bounded(
        self,
        conversation_id: str,
        file_path: str,
        max_response_bytes: int = MAX_FILE_RESPONSE_BYTES,
    ) -> str | None:
        """نص ملف واحد مع حد **صلب** على بايتات جسم الرد (OHB2-09-01-FIX/FIX2).

        - بنطلب `Accept-Encoding: identity` وبنقرا من `aiter_raw()` — يعني **مفيش فكّ ضغط**
          على مستوى التطبيق، فمفيش تضخيم ذاكرة من gzip/deflate قبل العدّ.
        - لو السيرفر تجاهل الطلب ورجّع `Content-Encoding` غير `identity`، بنرفض الرد
          بأمان (ApiError) بدل ما نفكّ ضغطه على مسار غير محدود.
        - العدّ التراكمي بيتطبّق على البايتات الخام **قبل** الإضافة للتراكم؛ أول ما تعدّي
          الحد ⇒ `ResponseTooLargeError` قبل تجميع الجسم كله وقبل فك JSON.
        - `Content-Length` (بايتات مشفّرة) مجرّد تحسين؛ العدّ التراكمي هو الضمان.
        - فك JSON بعد ما الجسم يثبت إنه داخل الحد. `None` لو الرد مش نص.
        """
        if max_response_bytes < 0:
            raise ValueError("max_response_bytes لازم يكون >= 0")
        limit = int(max_response_bytes)
        try:
            async with self._client.stream(
                "GET",
                f"/app-conversations/{conversation_id}/file",
                params={"file_path": file_path},
                headers={"Accept-Encoding": "identity"},
            ) as resp:
                # OHB2-POST-PUB-01 (F03): 3xx إعادة توجيه **مش** محتوى — بنرفضها صراحةً
                # قبل أي قراءة جسم، فمفيش متابعة لإعادة التوجيه ومفيش تفسير لجسم الـ redirect
                # كمحتوى ملف. (زي `_request`: كل الـ endpoints بترجّع 2xx مباشر.)
                if 300 <= resp.status_code < 400:
                    raise ApiError(
                        "رد إعادة توجيه غير متوقّع من OpenHands.", resp.status_code
                    )
                if resp.status_code >= 400:
                    # قراءة محدودة للتفاصيل؛ لو عدّت الحد بنرميها ونسيب الحالة الأصلية.
                    # لو القراءة نفسها فشلت (نقل أو حالة تدفّق)، بنسيب الحالة الأصلية برضه
                    # بدل ما نستبدلها بخطأ اتصال عام (H2) — مفيش فقدان لحالة الـ HTTP.
                    try:
                        body = await self._read_capped_or_empty(resp, MAX_ERROR_DETAIL_BYTES)
                    except (httpx.HTTPError, httpx.StreamError):
                        body = b""
                    raise ApiError(
                        describe_status(resp.status_code, _detail_from_bytes(body)),
                        resp.status_code,
                    )
                encoding = _content_encoding(resp)
                if encoding is not None and encoding != "identity":
                    # ترميز مش متوقّع (تجاهل السيرفر `identity`) ⇒ رفض آمن بدون فكّ ضغط.
                    raise ApiError(f"ترميز محتوى غير متوقّع من OpenHands ({encoding}).")
                declared = _content_length(resp)
                if declared is not None and declared > limit:
                    raise ResponseTooLargeError()
                body = await self._read_capped(resp, limit)
        except httpx.HTTPError as exc:
            raise ApiError(f"تعذّر الاتصال بـ OpenHands ({type(exc).__name__}).") from exc
        try:
            data = json.loads(body)
        except ValueError as exc:
            raise ApiError("رد غير متوقع من OpenHands") from exc
        return data if isinstance(data, str) else None

    @staticmethod
    async def _read_capped(resp: httpx.Response, limit: int) -> bytes:
        """يقرأ الجسم **الخام** (بدون فكّ ضغط) على قطع مع حد تراكمي صلب.

        العدّ مستقل عن حدود القطع. أي قطع هي اللي هتعدّي الحد **ما بتتضافش** للتراكم.
        """
        buf = bytearray()
        async for chunk in resp.aiter_raw():
            if len(buf) + len(chunk) > limit:
                raise ResponseTooLargeError()
            buf += chunk
        return bytes(buf)

    @staticmethod
    async def _read_capped_or_empty(resp: httpx.Response, limit: int) -> bytes:
        """زي `_read_capped` بس بيرجّع `b""` لو عدّى الحد (لتفاصيل الأخطاء، مافيش رفع)."""
        try:
            return await OpenHandsClient._read_capped(resp, limit)
        except ResponseTooLargeError:
            return b""

    async def get_current_user(self) -> dict:
        """هوية المستخدم الحالي (`/users/me`) — بتُستخدم للتحقق من ملكية الشات."""
        data = await self._get("/users/me")
        return data if isinstance(data, dict) else {}

    async def export_conversation(
        self, conversation_id: str, max_bytes: int = MAX_EXPORT_BYTES
    ) -> bytes:
        """تصدير الشات كـ zip (events + meta)، مش ملفات الـ workspace.

        OHB2-09-03: قراءة **محدودة** بنفس مسار الملفات الآمن — `Accept-Encoding: identity`
        + قراءة خام (`aiter_raw`) على قطع مع حد تراكمي صلب. قبل كده كان `resp.content`
        بيجمّع الجسم كله في الذاكرة بلا حد (ويفكّ ضغط تلقائي لو السيرفر ضغط).
        """
        if max_bytes < 0:
            raise ValueError("max_bytes لازم يكون >= 0")
        limit = int(max_bytes)
        try:
            async with self._client.stream(
                "GET",
                f"/app-conversations/{conversation_id}/download",
                headers={"Accept-Encoding": "identity"},
            ) as resp:
                # OHB2-POST-PUB-01 (F03): نفس سياسة إعادة التوجيه الصارمة — 3xx مرفوضة
                # صراحةً قبل أي قراءة، فمفيش متابعة ومفيش تفسير لجسم الـ redirect كتصدير.
                if 300 <= resp.status_code < 400:
                    raise ApiError(
                        "رد إعادة توجيه غير متوقّع من OpenHands.", resp.status_code
                    )
                if resp.status_code >= 400:
                    try:
                        body = await self._read_capped_or_empty(resp, MAX_ERROR_DETAIL_BYTES)
                    except (httpx.HTTPError, httpx.StreamError):
                        body = b""
                    raise ApiError(
                        describe_status(resp.status_code, _detail_from_bytes(body)),
                        resp.status_code,
                    )
                encoding = _content_encoding(resp)
                if encoding is not None and encoding != "identity":
                    raise ApiError(f"ترميز محتوى غير متوقّع من OpenHands ({encoding}).")
                declared = _content_length(resp)
                if declared is not None and declared > limit:
                    raise ResponseTooLargeError(
                        "ملف التصدير كبير أوي للتنزيل الآمن."
                    )
                return await self._read_capped(resp, limit)
        except httpx.HTTPError as exc:
            raise ApiError(f"تعذّر الاتصال بـ OpenHands ({type(exc).__name__}).") from exc

    async def send_message(self, conversation_id: str, text: str) -> None:
        body = {"role": "user", "content": [{"type": "text", "text": text}], "run": True}
        await self._request("POST", f"/app-conversations/{conversation_id}/send-message", json=body)

    async def resume_sandbox(self, sandbox_id: str) -> None:
        await self._request("POST", f"/sandboxes/{sandbox_id}/resume")

    async def update_conversation_repository(self, conversation_id: str, repository: str) -> dict:
        """يربط/يغيّر مستودع شات موجود (PATCH آمن على نفس الشات).

        OpenHands: `PATCH /app-conversations/{id}` بـ `selected_repository`. بترجّع
        الميتاداتا المحدّثة (مش بتعمل شات جديد ولا بتلمس أي بيانات محمية).
        """
        body: dict[str, Any] = {"selected_repository": repository}
        resp = await self._request("PATCH", f"/app-conversations/{conversation_id}", json=body)
        return _decode_json(resp)

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
        resp = await self._request("POST", "/app-conversations", json=body)
        # OHB2-N10-28D: فك JSON آمن — جسم HTML/نص (بروكسي/صفحة خطأ) كان بيرمي ValueError
        # خام من غير ما يعدّي حدود الأخطاء المتوقّعة، فساب طلب الشات عالق 'starting'.
        # بنحوّله لـ ApiError غامض (بلا status_code) زي أي رد غير متوقّع.
        try:
            payload = resp.json()
        except ValueError as exc:
            raise ApiError("رد غير متوقّع من OpenHands") from exc
        if not isinstance(payload, dict):
            raise ApiError("رد غير متوقّع من OpenHands")
        task_id = payload.get("id")
        # معرّف البدء لازم يكون نص غير فاضي. أي نوع تاني (رقم/None) أو نص فاضي ⇒ خطأ
        # آمن، مفيش استبدال صامت بقيمة مفقودة.
        if not isinstance(task_id, str) or not task_id.strip():
            raise ApiError("الـ API ما رجّعش معرّف مهمة البدء")
        return task_id

    async def get_start_task(self, task_id: str) -> dict:
        """يقرأ حالة مهمة البدء (GET آمن قابل للتكرار — مش بينشئ أي حاجة).

        بترجّع dict المهمة (فاضي لو لسه مفيش بيانات). دي الطريقة الموثّقة الوحيدة
        لمتابعة مهمة بدء موجودة، فالاستطلاع بيها آمن.
        """
        data = await self._get("/app-conversations/start-tasks", params={"ids": task_id})
        tasks = _as_items(data)
        return next((t for t in tasks if isinstance(t, dict) and t), {}) or {}

    async def wait_for_start(self, task_id: str, timeout: float = 180.0, interval: float = 3.0) -> str:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            task = await self.get_start_task(task_id)
            if task:
                status = str(task.get("status", "")).upper()
                if status == "READY":
                    app_id = task.get("app_conversation_id")
                    # OHB2-N10-28D: لازم معرّف نصي غير فاضي؛ أي نوع تاني ⇒ خطأ آمن
                    # (ما نمرّرش معرّف مشوّه كأنه صالح).
                    if not isinstance(app_id, str) or not app_id.strip():
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
        items = _as_items(data)
        return [r for r in items if isinstance(r, dict) and r]


def _as_items(data: Any) -> list:
    """يستخرج قايمة العناصر من رد API بشكل آمن.

    الموثّق: إما قايمة مباشرة أو dict فيه `items`. أي شكل تاني (str/int/None/dict بدون
    items) ⇒ خطأ API آمن بدل ما نرجع نتيجة فاضية مضلّلة.
    """
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]
    raise ApiError("رد غير متوقع من OpenHands")


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


def _content_length(resp: httpx.Response) -> int | None:
    """طول الجسم المعلن من الهيدر، أو None لو غايب/غير صالح (سالب/غير رقمي)."""
    raw = resp.headers.get("content-length")
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _content_encoding(resp: httpx.Response) -> str | None:
    """ترميز المحتوى المُعلن (مصغّر)، أو None لو غايب/فاضي (يعني body مافيهوش ترميز)."""
    raw = resp.headers.get("content-encoding")
    if raw is None:
        return None
    value = raw.strip().lower()
    return value or None


def _detail_from_bytes(body: bytes) -> str:
    """نفس سياسة `_detail` بس من بايتات (للردود المبثوثة). آمنة ومحدودة."""
    try:
        data = json.loads(body)
    except ValueError:
        return ""
    if isinstance(data, dict) and "detail" in data:
        return str(data["detail"])[:300]
    return ""


# OHB2-AUDIT-FIX-05: عدد أقصى لصفحات البحث عند لمّ قايمة الشات. الباگ الأصلي كان بطلب
# صفحة واحدة (limit=100) ويهمل next_page_id ⇒ الشاتات الأقدم بقت غير قابلة للوصول. دلوقتي
# بنتبع next_page_id لحد حد معقول (بدون حلقة لا نهائية لو السيرفر رجّع next_page_id غلط).
CONVERSATIONS_MAX_PAGES = 20


async def collect_conversations(
    client, limit: int = 100, max_pages: int = CONVERSATIONS_MAX_PAGES
) -> dict:
    """يجمع شاتات عبر **كل** صفحات البحث (يتبع `next_page_id`) لحد حد أقصى.

    بيرجّع `{"items": [...], "truncated": bool}`. `truncated=True` لو فيه صفحات إضافية
    لسه موجودة بعد الحد (المستخدم لازم يعرف إن القايمة مش كاملة، مش إخفاء صامت).
    الأخطاء بتطلع للمستدعي زي ما هي (نفس سياسة الـ client).
    """
    items: list[dict] = []
    page_id: str | None = None
    pages = 0
    while pages < max(1, int(max_pages)):
        result = await client.search_conversations(limit=limit, page_id=page_id)
        items.extend(result.get("items", []))
        pages += 1
        page_id = result.get("next_page_id")
        if not page_id:
            break
    return {"items": items, "truncated": bool(page_id)}
