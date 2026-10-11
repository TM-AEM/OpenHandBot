"""المراقب: polling كل 20-30 ثانية وإشعار الانتهاء."""
from __future__ import annotations

import asyncio
import logging

from .errors import ApiError
from .messages import DONE_STATES, state_label
from .sender import send_long

log = logging.getLogger(__name__)


class Watcher:
    def __init__(self, client, db, bot, chat_id: int, interval: int = 25) -> None:
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
                # الشات اتمسح من OpenHands، مفيش فايدة نفضل نراقبه للأبد.
                log.info("إزالة شات مش موجود من المتابعة: %s", w.conversation_id)
                self._db.remove_watched(w.conversation_id)
                continue
            state = conv.get("execution_status")
            if state in DONE_STATES and w.last_state not in DONE_STATES:
                await self._notify(w, conv, state)
                self._db.remove_watched(w.conversation_id)
            else:
                self._db.set_last_state(w.conversation_id, state or "")

    async def _notify(self, w, conv: dict, state: str) -> None:
        title = conv.get("title") or "بدون عنوان"
        header = f"انتهى الشات: {title}\nالحالة: {state_label(state)}"
        if state == "waiting_for_confirmation":
            header += "\nالشات مستني تأكيدك، افتح الموقع للمتابعة."
        try:
            reply = await self._client.get_last_reply(w.conversation_id)
        except ApiError:
            reply = None
        text = header + ("\n\n" + reply if reply else "")
        await send_long(w.chat_id or self._default_chat_id, text, self._bot)
