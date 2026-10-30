"""تشغيل الـ Mini App (ASGI) جوه نفس عملية البوت (OHB2-05).

التصميم: عملية asyncio واحدة فيها:
- long polling بتاع البوت (python-telegram-bot) — زي ما هو، من غير أي تغيير.
- سيرفر Uvicorn بيستمع على منفذ الـ ingress، شغّال كـ task جنب البوت.

قرارات مهمة:
- بنربط الـ socket بنفسنا (`_bind_socket`) ونمرّره لـ Uvicorn. كده فشل الربط (منفذ
  مستخدم) يطلع `OSError` عادي نقدر نمسكه و**نوقف التشغيل بوضوح**، بدل ما Uvicorn
  ينادي `sys.exit(1)` جوه الـ event loop (asyncio بيعيد رميه ويقتل العملية كلها فجأة).
- بنعطّل `capture_signals` وقت التشغيل المتكامل: Uvicorn كـ task ما لازمش ياخد
  إشارات العملية لنفسه — البوت هو اللي بيمسك SIGINT/SIGTERM ويعمل إغلاق نظيف.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import socket
from contextlib import asynccontextmanager

import uvicorn
from starlette.applications import Starlette

log = logging.getLogger(__name__)
_BACKLOG = 2048
_START_TIMEOUT = 10.0


@contextlib.contextmanager
def _standalone_signals():
    """يعطّل استيلاء Uvicorn على إشارات العملية (وضع التشغيل المشترك)."""
    original = uvicorn.Server.capture_signals

    @contextlib.contextmanager
    def _noop(self):
        yield

    uvicorn.Server.capture_signals = _noop
    try:
        yield
    finally:
        uvicorn.Server.capture_signals = original


def _bind_socket(host: str, port: int) -> socket.socket:
    """يربط socket مملوك لنا. يرمي `OSError` لو المنفذ مستخدم (فشل سريع ونظيف)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
    except OSError:
        sock.close()
        raise
    return sock


def build_uvicorn_config(app: Starlette, host: str, port: int) -> uvicorn.Config:
    return uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
        server_header=False,
        lifespan="on",
    )


def make_uvicorn_server(app: Starlette, host: str, port: int) -> uvicorn.Server:
    return uvicorn.Server(build_uvicorn_config(app, host, port))


@asynccontextmanager
async def web_server_lifespan(app: Starlette, host: str, port: int):
    """يشغّل Uvicorn كـ task ويرجّع `(server, task)`. يستنى السيرفر يبدأ فعلاً."""
    sock = _bind_socket(host, port)
    server = make_uvicorn_server(app, host, port)
    task = None
    try:
        with _standalone_signals():
            task = asyncio.create_task(server.serve(sockets=[sock]), name="mini-app-uvicorn")
            loop = asyncio.get_running_loop()
            deadline = loop.time() + _START_TIMEOUT
            while not server.started and not task.done() and loop.time() < deadline:
                await asyncio.sleep(0.05)
        if task.done():
            # فشل مبكر (خطأ في lifespan التطبيق مثلاً) ⇒ نطلّع الاستثناء للـ caller.
            task.result()
        if not server.started:
            raise RuntimeError("الـ Mini App web server ما بدأش خلال المهلة")
        yield server, task
    finally:
        if task is not None:
            server.should_exit = True
            with contextlib.suppress(Exception):
                await asyncio.wait_for(task, timeout=_START_TIMEOUT)
        sock.close()
