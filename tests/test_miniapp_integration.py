"""اختبارات دمج الـ Mini App مع عملية البوت الواحدة (OHB2-05).

بتثبت: السيرفر بيبدأ ويقف بنظافة، فشل الربط بيوقف التشغيل بوضوح (مش بصمت)،
مفيش سيرفر تاني عند إعادة التهيئة، ومفيش مالك تاني لقاعدة البيانات.
"""
from __future__ import annotations

import asyncio
import socket

import httpx
import pytest

from bot.app import build_application
from bot.config import Config
from bot.db import Database
from bot.web import build_web_app
from bot.web.runner import web_server_lifespan
from tests._miniapp_helpers import BOT_TOKEN


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def make_config(tmp_path, **over) -> Config:
    base = dict(
        telegram_bot_token=BOT_TOKEN,
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({1}),
        owner_id=1,
        db_path=str(tmp_path / "t.sqlite3"),
        mini_app_cookie_secure=False,
    )
    base.update(over)
    return Config(**base)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """ما نعملش أي نداء شبكة حقيقي لتسجيل الأوامر وقت اختبارات الدورة."""

    async def _noop(self, *a, **kw):
        return True

    monkeypatch.setattr("telegram.Bot.set_my_commands", _noop)
    monkeypatch.setattr("telegram.Bot.set_chat_menu_button", _noop)


def test_web_lifespan_starts_serves_and_stops(tmp_path):
    app = build_web_app(make_config(tmp_path), None)
    port = free_port()

    async def scenario():
        async with web_server_lifespan(app, "127.0.0.1", port) as (server, task):
            assert server.started is True
            async with httpx.AsyncClient() as http:
                r = await http.get(f"http://127.0.0.1:{port}/health")
            assert r.status_code == 200
            assert r.json()["status"] == "ok"
        # بعد الخروج: المهمة خلصت والمنفذ اتحرر.
        assert task.done()

    asyncio.run(scenario())

    # المنفذ اتحرر (نقدر نربط عليه تاني).
    probe = socket.socket()
    try:
        probe.bind(("127.0.0.1", port))
    finally:
        probe.close()


def test_web_lifespan_port_in_use_fails_fast(tmp_path):
    app = build_web_app(make_config(tmp_path), None)
    port = free_port()
    holder = socket.socket()
    holder.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    holder.bind(("127.0.0.1", port))
    holder.listen(1)
    try:
        async def scenario():
            with pytest.raises(BaseException):
                async with web_server_lifespan(app, "127.0.0.1", port):
                    pass

        asyncio.run(scenario())
    finally:
        holder.close()


def test_build_application_mini_app_disabled_by_default(tmp_path):
    app = build_application(make_config(tmp_path))
    assert "mini_app" not in app.bot_data

    async def run():
        await app.post_init(app)
        assert app.bot_data.get("mini_app_server") is None
        await app.post_shutdown(app)

    asyncio.run(run())


def test_build_application_mini_app_enabled_requires_url(tmp_path):
    with pytest.raises(RuntimeError):
        build_application(make_config(tmp_path, mini_app_enabled=True, mini_app_url=""))


def test_build_application_wires_mini_app_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setattr("bot.outbox.OutboxWorker.start", lambda self: None)
    monkeypatch.setattr("bot.outbox.CreationWorker.start", lambda self: None)
    monkeypatch.setattr("bot.watcher.Watcher.start", lambda self: None)

    async def _stop(self):
        return None

    monkeypatch.setattr("bot.outbox.OutboxWorker.stop", _stop)
    monkeypatch.setattr("bot.outbox.CreationWorker.stop", _stop)
    monkeypatch.setattr("bot.watcher.Watcher.stop", _stop)

    port = free_port()
    cfg = make_config(
        tmp_path,
        mini_app_enabled=True,
        mini_app_url="https://example.test/mini/",
        mini_app_port=port,
    )
    app = build_application(cfg)
    assert "mini_app" in app.bot_data

    async def run():
        await app.post_init(app)
        server = app.bot_data["mini_app_server"]
        assert server is not None and server.started is True
        async with httpx.AsyncClient() as http:
            r = await http.get(f"http://127.0.0.1:{port}/health")
        assert r.status_code == 200
        await app.post_shutdown(app)
        assert app.bot_data["mini_app_task"].done()

    asyncio.run(run())


def test_post_init_repeated_does_not_start_second_web_server(tmp_path, monkeypatch):
    monkeypatch.setattr("bot.outbox.OutboxWorker.start", lambda self: None)
    monkeypatch.setattr("bot.outbox.CreationWorker.start", lambda self: None)
    monkeypatch.setattr("bot.watcher.Watcher.start", lambda self: None)

    async def _stop(self):
        return None

    monkeypatch.setattr("bot.outbox.OutboxWorker.stop", _stop)
    monkeypatch.setattr("bot.outbox.CreationWorker.stop", _stop)
    monkeypatch.setattr("bot.watcher.Watcher.stop", _stop)

    port = free_port()
    cfg = make_config(
        tmp_path,
        mini_app_enabled=True,
        mini_app_url="https://example.test/mini/",
        mini_app_port=port,
    )
    app = build_application(cfg)

    async def run():
        await app.post_init(app)
        first = app.bot_data["mini_app_server"]
        await app.post_init(app)  # إعادة تهيئة مكرّرة
        assert app.bot_data["mini_app_server"] is first
        await app.post_shutdown(app)

    asyncio.run(run())


def test_single_database_owner(tmp_path, monkeypatch):
    """العملية بتبني كائن Database واحد بس، والـ Mini App بيشاركه (مفيش مالك تاني)."""
    created: list[Database] = []
    real_init = Database.__init__

    def counting_init(self, path):
        real_init(self, path)
        created.append(self)

    monkeypatch.setattr(Database, "__init__", counting_init)
    monkeypatch.setattr("bot.outbox.OutboxWorker.start", lambda self: None)
    monkeypatch.setattr("bot.outbox.CreationWorker.start", lambda self: None)
    monkeypatch.setattr("bot.watcher.Watcher.start", lambda self: None)

    async def _stop(self):
        return None

    monkeypatch.setattr("bot.outbox.OutboxWorker.stop", _stop)
    monkeypatch.setattr("bot.outbox.CreationWorker.stop", _stop)
    monkeypatch.setattr("bot.watcher.Watcher.stop", _stop)

    port = free_port()
    cfg = make_config(
        tmp_path,
        mini_app_enabled=True,
        mini_app_url="https://example.test/mini/",
        mini_app_port=port,
    )
    app = build_application(cfg)
    assert len(created) == 1
    assert app.bot_data["db"] is created[0]

    async def run():
        await app.post_init(app)
        await app.post_shutdown(app)

    asyncio.run(run())


def test_post_init_fails_fast_when_port_in_use(tmp_path, monkeypatch):
    """فشل ربط المنفذ بيوقف التشغيل بوضوح (مش بصمت) — نفس قاعدة المنفذ المستخدم."""
    monkeypatch.setattr("bot.outbox.OutboxWorker.start", lambda self: None)
    monkeypatch.setattr("bot.outbox.CreationWorker.start", lambda self: None)
    monkeypatch.setattr("bot.watcher.Watcher.start", lambda self: None)

    async def _stop(self):
        return None

    monkeypatch.setattr("bot.outbox.OutboxWorker.stop", _stop)
    monkeypatch.setattr("bot.outbox.CreationWorker.stop", _stop)
    monkeypatch.setattr("bot.watcher.Watcher.stop", _stop)

    port = free_port()
    holder = socket.socket()
    holder.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    holder.bind(("127.0.0.1", port))
    holder.listen(1)
    try:
        cfg = make_config(
            tmp_path,
            mini_app_enabled=True,
            mini_app_url="https://example.test/mini/",
            mini_app_port=port,
        )
        app = build_application(cfg)

        async def run():
            with pytest.raises(OSError):
                await app.post_init(app)

        asyncio.run(run())
    finally:
        holder.close()

