"""OHB2-N10-25: دورة حياة التطبيق الأساسية.

مفيش شبكة ولا polling حقيقي. بنعترض بدء الـ workers (بتعمل tasks) عشان الاختبار يبقى
مركّز على دورة حياة النواة + ملكية واحدة + الإغلاق النظيف.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.app import build_application  # noqa: E402
from bot.config import Config  # noqa: E402


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    async def _noop(self, *a, **k):
        return True

    monkeypatch.setattr("telegram.Bot.set_my_commands", _noop)
    monkeypatch.setattr("telegram.Bot.set_chat_menu_button", _noop)
    # نعترض بدء/إيقاف الـ workers التانية (بتعمل tasks) — النواة هي محور الاختبار.
    monkeypatch.setattr("bot.outbox.OutboxWorker.start", lambda self: None)
    monkeypatch.setattr("bot.outbox.CreationWorker.start", lambda self: None)
    monkeypatch.setattr("bot.watcher.Watcher.start", lambda self: None)
    monkeypatch.setattr("bot.notifier.Notifier.start", lambda self: None)

    async def _stop(self):
        return None

    monkeypatch.setattr("bot.outbox.OutboxWorker.stop", _stop)
    monkeypatch.setattr("bot.outbox.CreationWorker.stop", _stop)
    monkeypatch.setattr("bot.watcher.Watcher.stop", _stop)
    monkeypatch.setattr("bot.notifier.Notifier.stop", _stop)


def _config(tmp_path) -> Config:
    return Config(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({1}),
        owner_id=1,
        db_path=str(tmp_path / "t.sqlite3"),
    )


def test_build_application_has_no_backup_state(tmp_path):
    # التطبيق النووي مايعرّفش ولا يستدعي أي مكوّن نسخ.
    app = build_application(_config(tmp_path))
    assert "backup_config" not in app.bot_data
    assert "backup_lifecycle" not in app.bot_data


def test_post_init_starts_core_workers_once(tmp_path):
    app = build_application(_config(tmp_path))

    async def run():
        await app.post_init(app)
        await app.post_init(app)  # إعادة تهيئة ⇒ ما تعملش workers تانية
        assert app.bot_data.get("outbox_worker") is not None
        assert app.bot_data.get("watcher") is not None
        assert app.bot_data.get("notifier") is not None
        assert "backup_lifecycle" not in app.bot_data

    asyncio.run(run())


def test_post_shutdown_closes_core_resources(tmp_path):
    app = build_application(_config(tmp_path))
    db = app.bot_data["db"]

    async def run():
        await app.post_init(app)
        await app.post_shutdown(app)

    asyncio.run(run())
    # الاتصال اتقفل عند الإغلاق النظيف (مفيش تسريب موارد).
    import sqlite3

    with pytest.raises(sqlite3.ProgrammingError):
        db._conn.execute("SELECT 1")


def test_build_application_returns_single_application(tmp_path):
    from telegram.ext import Application

    app = build_application(_config(tmp_path))
    assert isinstance(app, Application)
    # ملك polling واحد: التطبيق الوحيد ده هو اللي main بيعمل عليه run_polling.


# ---------------------------------------------------------------- DB safety


def test_database_wal_and_busy_timeout(tmp_path):
    from bot.db import Database

    db = Database(str(tmp_path / "t.sqlite3"))
    try:
        assert db._conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert db._conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    finally:
        db.close()


def test_database_new_init_and_restart_preserves_data(tmp_path):
    from bot.db import Database

    path = str(tmp_path / "t.sqlite3")
    db = Database(path)
    db.add_outbox("c1", 1, "برومت مهم", "t")
    db.close()
    # إعادة فتح نفس القاعدة: نفس البيانات، مفيش إعادة تهيئة مدمرة.
    db2 = Database(path)
    try:
        assert db2.count_outbox("pending") == 1
    finally:
        db2.close()
