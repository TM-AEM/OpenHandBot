"""OHB2-N10-22: عقد الإقلاع Zero-Touch — تأكيدات موحّدة (بدون شبكة/بوت).

بيغطّي المسار الحقيقي: تحقق الإعداد → تجهيز المجلدات → بناء التطبيق → دورة حياة الـ workers →
إغلاق نظيف. مفيش polling ولا شبكة.
"""

from __future__ import annotations

import asyncio
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bot.bootstrap as boot  # noqa: E402
import bot.config as config  # noqa: E402
from bot.app import build_application  # noqa: E402
from bot.config import Config  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _required_env(tmp_path: Path, **extra: str) -> dict:
    env = {
        "TELEGRAM_BOT_TOKEN": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        "OPENHANDS_API_KEY": "sk-test-not-real",
        "ALLOWED_TELEGRAM_ID": "1",
        "DB_PATH": str(tmp_path / "bot_state.sqlite3"),
    }
    env.update(extra)
    return env


def _config(tmp_path: Path, **over) -> Config:
    kw = dict(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        openhands_api_key="sk-test-not-real",
        allowed_telegram_ids=frozenset({1}),
        owner_id=1,
        db_path=str(tmp_path / "t.sqlite3"),
    )
    kw.update(over)
    return Config(**kw)


@pytest.fixture()
def quiet_app(monkeypatch):
    """يعطّل بدء الـ workers/الشبكة — بنختبر التجميع والدورة بس."""
    async def _noop(*a, **k):
        return None

    monkeypatch.setattr("telegram.Bot.set_my_commands", _noop)
    monkeypatch.setattr("telegram.Bot.set_chat_menu_button", _noop)
    for cls in ("OutboxWorker", "CreationWorker"):
        monkeypatch.setattr(f"bot.outbox.{cls}.start", lambda self: None)
        monkeypatch.setattr(f"bot.outbox.{cls}.stop", _noop)
    monkeypatch.setattr("bot.watcher.Watcher.start", lambda self: None)
    monkeypatch.setattr("bot.watcher.Watcher.stop", _noop)
    monkeypatch.setattr("bot.notifier.Notifier.start", lambda self: None)
    monkeypatch.setattr("bot.notifier.Notifier.stop", _noop)
    return monkeypatch


# --------------------------------------------------------------- config / bootstrap


def test_fresh_env_only_startup_is_ready(tmp_path):
    res = boot.prepare_runtime(_required_env(tmp_path), version_info=(3, 13, 0))
    assert res.ready is True
    assert res.config.owner_id == 1
    assert Path(res.config.db_path).parent.exists()  # المجلد اتجهّز
    assert not Path(res.config.db_path).exists()  # مفيش قاعدة مُنشأة قبل التطبيق


def test_bootstrap_status_is_feature_neutral(tmp_path):
    # الإقلاع مايدّعيش جاهزية أي ميزة خارج نواة التشغيل.
    res = boot.prepare_runtime(_required_env(tmp_path), version_info=(3, 13, 0))
    assert res.ready is True
    assert "backup" not in res.status()
    assert res.blockers == []


def test_invalid_required_config_fails_safely_without_secret(tmp_path):
    env = _required_env(tmp_path)
    del env["TELEGRAM_BOT_TOKEN"]
    with pytest.raises(config.ConfigError) as exc:
        boot.prepare_runtime(env, version_info=(3, 13, 0))
    # الرسالة بتذكر **اسم** المتغيّر الناقص، مش أي قيمة سر.
    assert "TELEGRAM_BOT_TOKEN" in str(exc.value)
    assert env["OPENHANDS_API_KEY"] not in str(exc.value)


def test_bootstrap_status_and_log_contain_no_secret(tmp_path, caplog):
    import logging

    boot.setup_logging("INFO")
    with caplog.at_level(logging.INFO, logger="bootstrap"):
        res = boot.prepare_runtime(_required_env(tmp_path), version_info=(3, 13, 0))
    blob = repr(res.status()) + "\n".join(r.getMessage() for r in caplog.records)
    assert "sk-test-not-real" not in blob
    assert "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11" not in blob


# --------------------------------------------------------------- app / process


def test_single_application_no_second_process(tmp_path, quiet_app):
    from telegram.ext import Application

    app = build_application(_config(tmp_path))
    assert isinstance(app, Application)
    # مفيش أي spawn لعملية/thread في مسار الإقلاع.
    for rel in ("main.py", "bot/app.py", "bot/bootstrap.py"):
        src = (ROOT / rel).read_text()
        for forbidden in ("os.exec", "subprocess", "multiprocessing", "os.fork"):
            assert forbidden not in src, f"{rel} فيه {forbidden}"


def test_mini_app_disabled_starts_no_server(tmp_path, quiet_app):
    app = build_application(_config(tmp_path))

    async def run():
        await app.post_init(app)
        assert app.bot_data.get("mini_app_server") is None
        await app.post_shutdown(app)

    asyncio.run(run())


def test_repeated_post_init_does_not_duplicate_workers(tmp_path, quiet_app):
    app = build_application(_config(tmp_path))

    async def run():
        await app.post_init(app)
        first = {k: id(app.bot_data.get(k)) for k in ("outbox_worker", "watcher", "notifier")}
        await app.post_init(app)  # إعادة تهيئة مكرّرة
        second = {k: id(app.bot_data.get(k)) for k in ("outbox_worker", "watcher", "notifier")}
        assert first == second  # نفس الـ worker (مفيش ازدواج)
        await app.post_shutdown(app)

    asyncio.run(run())


def test_graceful_shutdown_closes_db(tmp_path, quiet_app):
    app = build_application(_config(tmp_path))
    db = app.bot_data["db"]

    async def run():
        await app.post_init(app)
        await app.post_shutdown(app)

    asyncio.run(run())
    with pytest.raises(sqlite3.ProgrammingError):
        db._conn.execute("SELECT 1")  # الاتصال اتقفل عند الإغلاق


# --------------------------------------------------------------- database safety


def test_existing_db_preserved_across_restart(tmp_path, quiet_app):
    cfg = _config(tmp_path)
    app1 = build_application(cfg)
    app1.bot_data["db"].add_outbox("c1", 1, "برومت مهم", "t")
    app1.bot_data["db"].close()

    app2 = build_application(cfg)
    try:
        assert app2.bot_data["db"].count_outbox("pending") == 1  # البيانات محفوظة
    finally:
        app2.bot_data["db"].close()


# --------------------------------------------------------------- scope guards


def test_core_has_no_backup_references():
    """النواة (main/bootstrap/app) مابتلمسش أي مكوّن نسخ ولا بتدّعي جاهزيته."""
    import ast

    for rel in ("main.py", "bot/bootstrap.py", "bot/app.py"):
        src = (ROOT / rel).read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert not name.startswith("tools"), f"{rel} بيستورد {name}"
                assert name != "bot.backup_lifecycle", f"{rel} بيستورد {name}"
