"""تشغيل الـ Mini App (ASGI) جوه نفس عملية البوت (OHB2-05).

التصميم: عملية asyncio واحدة فيها:
- long polling بتاع البوت (python-telegram-bot) — زي ما هو، من غير أي تغيير.
- سيرفر Uvicorn بيستمع على منفذ الـ ingress، شغّال كـ task جنب البوت.

`_standalone_signals`:
- لما Uvicorn يشتغل كـ task مش السيرفر الرئيسي، لازم ما ياخدش إشارات العملية لنفسه
  (ده بيخلي البوت يمسك SIGINT/SIGTERM ويعمل إغلاق نظيف). بنعطّل capture_signals وقت
  التشغيل المتكامل. الإغلاق لسه نظيف: البوت بيوقف الـ lifespan (startup/shutdown).
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

import uvicorn
from starlette.applications import Starlette

log = logging.getLogger(__name__)


@contextlib.contextmanager
def _standalone_signals():
    """يعطّل استيلاء Uvicorn على إشارات العملية (وضع التشغيل المشترك)."""
    original = uvicorn.Server.capture_signals

    @contextlib.contextmanager
    def _noop(self):  # pragma: no cover - سلوك متكامل
        yield

    uvicorn.Server.capture_signals = _noop
    try:
        yield
    finally:
        uvicorn.Server.capture_signals = original


def build_uvicorn_config(app: Starlette, host: str, port: int) -> uvicorn.Config:
    return uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
        server_header=False,
        # بنشيل اتصالات التطوير في الإنتاج.
        lifespan="on",
    )


def make_uvicorn_server(app: Starlette, host: str, port: int) -> uvicorn.Server:
    return uvicorn.Server(build_uvicorn_config(app, host, port))


@asynccontextmanager
async def web_server_lifespan(app: Starlette, host: str, port: int):
    """يشغّل Uvicorn كـ task ويرجّع `(server, task)`. يستنى السيرفر يبدأ فعلاً."""
    server = make_uvicorn_server(app, host, port)
    with _standalone_signals():
        task = asyncio.create_task(server.serve(), name="mini-app-uvicorn")
        for _ in range(200):  # لحد ~10 ثواني
            if server.started or task.done():
                break
            await asyncio.sleep(0.05)
    if task.done():
        # لو السيرفر مات فورًا (منفذ مستخدم مثلاً) نسيب الاستثناء يطلع للـ caller.
        task.result()
    try:
        yield server, task
    finally:
        server.should_exit = True
        with contextlib.suppress(Exception):
            await asyncio.wait_for(task, timeout=10)
