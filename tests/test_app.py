"""اختبارات دورة حياة التطبيق: worker واحد مالك، ترتيب التعافي، إيقاف نظيف."""
import asyncio
import re

import pytest
from telegram import BotCommand, BotCommandScopeChat, MenuButtonCommands
from telegram.ext import CallbackQueryHandler, CommandHandler

from bot.app import BOT_COMMANDS, build_application
from bot.config import Config
from bot.db import Database
from bot.outbox import CreationWorker, OutboxWorker


@pytest.fixture(autouse=True)
def _no_network_commands(monkeypatch):
    """يمنع أي نداء شبكة حقيقي لتسجيل قائمة الأوامر أثناء اختبارات دورة الحياة."""

    async def _noop_my_commands(self, commands, scope=None, **kw):
        return True

    async def _noop_menu_button(self, chat_id=None, menu_button=None, **kw):
        return True

    monkeypatch.setattr("telegram.Bot.set_my_commands", _noop_my_commands)
    monkeypatch.setattr("telegram.Bot.set_chat_menu_button", _noop_menu_button)


def make_config(tmp_path) -> Config:
    return Config(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({1}),
        owner_id=1,
        db_path=str(tmp_path / "t.sqlite3"),
    )


def test_build_application_wires_lifecycle_and_state(tmp_path):
    app = build_application(make_config(tmp_path))
    assert callable(app.post_init)
    assert callable(app.post_shutdown)
    assert isinstance(app.bot_data["db"], Database)
    assert "client" in app.bot_data and "config" in app.bot_data
    assert "outbox_worker" not in app.bot_data  # مايتعملش غير بعد post_init


def test_copy_and_full_patterns_registered_without_clash(tmp_path):
    # TASK 55 (المرحلة B): نمطا copy:/full: متسجّلين، وما بيتعارضوش مع cost:/files:.
    app = build_application(make_config(tmp_path))
    patterns = [
        h.pattern.pattern
        for group in app.handlers.values()
        for h in group
        if isinstance(h, CallbackQueryHandler) and h.pattern
    ]
    assert "^copy:" in patterns and "^full:" in patterns
    copy_full = [p for p in patterns if p in ("^copy:", "^full:")]
    for data in ("copy:abc", "full:abc"):
        assert any(re.match(p, data) for p in copy_full)
    for other in ("cost:abc", "files:abc:0", "file:abc:0:0", "open:abc"):
        assert not any(re.match(p, other) for p in copy_full)


def test_post_init_single_worker_after_recovery_and_clean_shutdown(tmp_path, monkeypatch):
    calls = {"worker_start": 0, "worker_stop": 0, "watcher_start": 0, "watcher_stop": 0}
    order = []

    real_recover = __import__("bot.handlers", fromlist=["outbox_recover"]).outbox_recover

    async def recording_recover(application):
        order.append("recover")
        await real_recover(application)

    def fake_worker_start(self):
        calls["worker_start"] += 1
        order.append("worker_start")

    async def fake_worker_stop(self):
        calls["worker_stop"] += 1

    def fake_watcher_start(self):
        calls["watcher_start"] += 1

    async def fake_watcher_stop(self):
        calls["watcher_stop"] += 1

    monkeypatch.setattr("bot.handlers.outbox_recover", recording_recover)
    monkeypatch.setattr("bot.outbox.OutboxWorker.start", fake_worker_start)
    monkeypatch.setattr("bot.outbox.OutboxWorker.stop", fake_worker_stop)
    monkeypatch.setattr("bot.watcher.Watcher.start", fake_watcher_start)
    monkeypatch.setattr("bot.watcher.Watcher.stop", fake_watcher_stop)

    app = build_application(make_config(tmp_path))
    db = app.bot_data["db"]
    db.add_outbox("c1", 1, "برومت", "t")  # عنصر مؤهّل موجود عند البدء

    async def lifecycle():
        await app.post_init(app)
        worker = app.bot_data["outbox_worker"]
        assert isinstance(worker, OutboxWorker)
        # التعافي (لتحويل 'sending' المتروك) خلص قبل ما الـ worker يبدأ.
        assert order[0] == "recover"
        assert order[1] == "worker_start"
        # التعافي مالمسش 'pending' (الـ worker هو المسؤول عنه).
        assert db.count_outbox("pending") == 1
        # الإيقاف بينادي stop ويستنّاه (asyncio.run مايرجعش غير لما الـ await يخلص).
        await app.post_shutdown(app)

    asyncio.run(lifecycle())

    assert calls["worker_start"] == 1  # worker واحد بالظبط
    assert calls["watcher_start"] == 1
    assert calls["worker_stop"] == 1  # اتقفل بنظافة
    assert calls["watcher_stop"] == 1


def test_post_init_repeated_does_not_create_second_worker(tmp_path, monkeypatch):
    created = []

    real_start = OutboxWorker.start

    def counting_start(self):
        created.append(self)
        real_start(self)

    monkeypatch.setattr("bot.outbox.OutboxWorker.start", counting_start)
    monkeypatch.setattr("bot.outbox.CreationWorker.start", counting_start)
    monkeypatch.setattr("bot.watcher.Watcher.start", lambda self: None)

    app = build_application(make_config(tmp_path))

    async def lifecycle():
        await app.post_init(app)
        await app.post_init(app)
        await app.post_init(app)
        worker = app.bot_data["outbox_worker"]
        creation = app.bot_data["creation_worker"]
        await worker.stop()
        await creation.stop()

    asyncio.run(lifecycle())
    # worker واحد لكل جدول (outbox + creation) عبر إعادات التهيئة.
    assert len(created) == 2


def test_creation_worker_wired_and_recovered_before_start(tmp_path, monkeypatch):
    order = []

    async def recording_outbox_recover(application):
        order.append("outbox_recover")

    async def recording_creation_recover(application):
        order.append("creation_recover")

    def fake_start(self):
        order.append("start")

    async def fake_stop(self):
        pass

    monkeypatch.setattr("bot.handlers.outbox_recover", recording_outbox_recover)
    monkeypatch.setattr("bot.handlers.creation_recover", recording_creation_recover)
    monkeypatch.setattr("bot.outbox.OutboxWorker.start", fake_start)
    monkeypatch.setattr("bot.outbox.CreationWorker.start", fake_start)
    monkeypatch.setattr("bot.outbox.OutboxWorker.stop", fake_stop)
    monkeypatch.setattr("bot.outbox.CreationWorker.stop", fake_stop)
    monkeypatch.setattr("bot.watcher.Watcher.start", lambda self: None)
    monkeypatch.setattr("bot.watcher.Watcher.stop", fake_stop)

    app = build_application(make_config(tmp_path))
    creation = None

    async def lifecycle():
        nonlocal creation
        await app.post_init(app)
        creation = app.bot_data["creation_worker"]
        assert isinstance(creation, CreationWorker)
        await app.post_shutdown(app)

    asyncio.run(lifecycle())
    # التعافي (الاتنين) خلص قبل أي worker يبدأ.
    assert order[:2] == ["outbox_recover", "creation_recover"]
    assert "start" in order[2:]
    assert creation is not None


def test_post_init_registers_notifier_and_wires_owner_delivery(tmp_path, monkeypatch):
    """NTF-25: التطبيق بيسجّل المُبلّغ في bot_data['notifier'] وبيربط المراقب بيه عبر
    set_owner_delivery، وما بيعملش task مراقب/مُبلّغ تاني عند إعادة التهيئة."""
    calls = {"watcher_start": 0, "watcher_stop": 0, "notifier_start": 0, "notifier_stop": 0}
    seen = {}

    def fake_watcher_start(self):
        calls["watcher_start"] += 1

    async def fake_watcher_stop(self):
        calls["watcher_stop"] += 1

    def fake_notifier_start(self):
        calls["notifier_start"] += 1

    async def fake_notifier_stop(self):
        calls["notifier_stop"] += 1

    def fake_set_owner_delivery(self, callback):
        seen["callback"] = callback

    monkeypatch.setattr("bot.watcher.Watcher.start", fake_watcher_start)
    monkeypatch.setattr("bot.watcher.Watcher.stop", fake_watcher_stop)
    monkeypatch.setattr("bot.notifier.Notifier.start", fake_notifier_start)
    monkeypatch.setattr("bot.notifier.Notifier.stop", fake_notifier_stop)
    monkeypatch.setattr("bot.watcher.Watcher.set_owner_delivery", fake_set_owner_delivery)

    app = build_application(make_config(tmp_path))

    async def lifecycle():
        await app.post_init(app)
        await app.post_init(app)  # إعادة تهيئة مكرّرة: مفيش task تاني
        watcher = app.bot_data["watcher"]
        notifier = app.bot_data["notifier"]
        # نقطة التنسيق مربوطة، والمُبلّغ بيوصّل التسجيل للقاعدة فعلاً (مش mock للمُبلّغ).
        assert callable(seen["callback"])
        seen["callback"]("c1", "finished", "2026-01-01T00:00:00+00:00")
        assert app.bot_data["db"].get_notification_state("c1").notified_status == "finished"
        await app.post_shutdown(app)
        return watcher, notifier

    watcher, notifier = asyncio.run(lifecycle())

    from bot.notifier import Notifier as _Notifier
    from bot.watcher import Watcher as _Watcher
    assert isinstance(watcher, _Watcher)
    assert isinstance(notifier, _Notifier)
    # task واحد لكل مكوّن عبر إعادات التهيئة.
    assert calls["watcher_start"] == 1
    assert calls["notifier_start"] == 1
    # إيقاف نظيف للاتنين.
    assert calls["watcher_stop"] == 1
    assert calls["notifier_stop"] == 1



# =====================================================================
# OHB2-03: تسجيل قائمة الأوامر + عدم الانحراف عن الـ handlers
# =====================================================================
def _command_names(app):
    names = set()
    for group in app.handlers.values():
        for h in group:
            if isinstance(h, CommandHandler) and h.commands:
                names.update(h.commands)
    return names


def test_bot_commands_match_registered_command_handlers(tmp_path):
    app = build_application(make_config(tmp_path))
    registered = _command_names(app)
    listed = {name for name, _ in BOT_COMMANDS}
    # مفيش أمر متسجّل بدون وصف في القائمة، والعكس.
    assert registered == listed


def test_bot_commands_are_valid_and_arabic_described():
    for name, desc in BOT_COMMANDS:
        assert name == name.lower() and " " not in name
        assert 1 <= len(name) <= 32
        assert desc.strip()
        assert len(desc) <= 256


def test_register_commands_sets_owner_scope_and_commands_menu():
    """_register_commands يبعت set_my_commands بنطاق شات المالك ويثبّت زر «الأوامر»."""
    calls = {"commands": None, "scope": None, "menu": "unset", "menu_chat": None}

    class FakeBot:
        async def set_my_commands(self, commands, scope=None, **kw):
            calls["commands"] = commands
            calls["scope"] = scope

        async def set_chat_menu_button(self, chat_id=None, menu_button=None, **kw):
            calls["menu"] = menu_button
            calls["menu_chat"] = chat_id

    from types import SimpleNamespace

    from bot.app import _register_commands

    app = SimpleNamespace(bot=FakeBot())
    asyncio.run(_register_commands(app, owner_id=777))

    assert isinstance(calls["scope"], BotCommandScopeChat)
    assert calls["scope"].chat_id == 777
    assert all(isinstance(c, BotCommand) for c in calls["commands"])
    assert [c.command for c in calls["commands"]] == [n for n, _ in BOT_COMMANDS]
    assert isinstance(calls["menu"], MenuButtonCommands)
    assert calls["menu_chat"] == 777


def test_post_init_command_registration_failure_is_non_fatal(tmp_path, monkeypatch):
    """لو تسجيل الأوامر فشل (شبكة)، الـ post_init يكمّل وما يرميش."""
    async def boom(application, owner_id):
        raise RuntimeError("network down")

    monkeypatch.setattr("bot.app._register_commands", boom)
    monkeypatch.setattr("bot.outbox.OutboxWorker.start", lambda self: None)
    monkeypatch.setattr("bot.outbox.CreationWorker.start", lambda self: None)
    monkeypatch.setattr("bot.watcher.Watcher.start", lambda self: None)
    monkeypatch.setattr("bot.notifier.Notifier.start", lambda self: None)

    app = build_application(make_config(tmp_path))

    async def lifecycle():
        await app.post_init(app)
        await app.post_shutdown(app)

    asyncio.run(lifecycle())  # مايرميش رغم فشل التسجيل
    assert app.bot_data.get("watcher") is not None
