"""OHB2-REPAIR-PLAN-02/LIFE-01 — اختبار ربط التشغيل الحقيقي (`app._post_init`).

المراجعة المستقلة لاحظت إن اختبارات LIFE-01 كانت بتعمل `Watcher` يدويًّا وما بتثبتش
الربط الفعلي من `app._post_init`. الاختبار ده بيشغّل مسار الإقلاع الحقيقي وبيتحقّق:

- الـ runtime بينشئ **`AttachmentReaper` واحد** (المالك الحقيقي: نفس اتصال القاعدة الوحيد).
- `OpportunisticSweeper` بيلفّ نفس الـ reaper.
- نفس الـ sweeper ده بيتُمرَّر لـ `Watcher` الفعلي (مش غيره).
- مفيش reaper/مالك قاعدة/عامل تاني.
- كنس الإقلاع (A4) لسه مربوط وفعّال (بيكنس دفعة منتهية عند الإقلاع).
- `Watcher` بلا sweeper = السلوك السابق (مفيش كنس انتهاكي).

بلا شبكة (أوامر تيليجرام متقيّدة) وبلا tasks خلفية حقيقية (start/stop متقيّدة).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from bot.app import build_application
from bot.attachments import (
    OPPORTUNISTIC_SWEEP_MIN_INTERVAL_SECONDS,
    AttachmentReaper,
    OpportunisticSweeper,
    staging_root_for,
)
from bot.config import Config
from bot.db import (
    ATTACHMENT_BATCH_PENDING,
    ATTACHMENT_ITEM_REAPED,
    Database,
)
from bot.watcher import Watcher


@pytest.fixture(autouse=True)
def _no_network_or_background(monkeypatch):
    """يمنع أي نداء شبكة أو task خلفية حقيقية أثناء اختبار الإقلاع."""

    async def _noop_my_commands(self, commands, scope=None, **kw):
        return True

    async def _noop_menu_button(self, chat_id=None, menu_button=None, **kw):
        return True

    monkeypatch.setattr("telegram.Bot.set_my_commands", _noop_my_commands)
    monkeypatch.setattr("telegram.Bot.set_chat_menu_button", _noop_menu_button)

    def _start(self):
        return None

    async def _stop(self):
        return None

    monkeypatch.setattr("bot.watcher.Watcher.start", _start)
    monkeypatch.setattr("bot.watcher.Watcher.stop", _stop)
    monkeypatch.setattr("bot.notifier.Notifier.start", _start)
    monkeypatch.setattr("bot.notifier.Notifier.stop", _stop)
    monkeypatch.setattr("bot.outbox.OutboxWorker.start", _start)
    monkeypatch.setattr("bot.outbox.CreationWorker.start", _start)
    monkeypatch.setattr("bot.outbox.CompletionWorker.start", _start)
    monkeypatch.setattr("bot.outbox.OutboxWorker.stop", _stop)
    monkeypatch.setattr("bot.outbox.CreationWorker.stop", _stop)
    monkeypatch.setattr("bot.outbox.CompletionWorker.stop", _stop)


def make_config(tmp_path) -> Config:
    return Config(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({1}),
        owner_id=1,
        db_path=str(tmp_path / "t.sqlite3"),
    )


def _write_expired_batch_with_file(db, db_path):
    """دفعة منتهية + عنصر pending + ملف staging ⇒ كنس الإقلاع المفروض يمسحها."""
    t0 = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    db.create_attachment_batch("startup-b1", 1, "11111111222233334444555566667777", t0)
    db.add_attachment_item("startup-i1", "startup-b1", staging_token="s" * 32,
                           display_name="n.txt", size_bytes=3, status=ATTACHMENT_BATCH_PENDING)
    root = staging_root_for(db_path)
    root.mkdir(parents=True, exist_ok=True)
    f = root / ("s" * 32)
    f.write_bytes(b"abc")
    return f


def test_post_init_wires_single_reaper_sweeper_into_watcher(tmp_path):
    config = make_config(tmp_path)
    app = build_application(config)
    db = app.bot_data["db"]

    # كنس الإقلاع: نجهّز دفعة منتهية قبل الـ post_init.
    startup_file = _write_expired_batch_with_file(db, config.db_path)

    async def lifecycle():
        await app.post_init(app)

    asyncio.run(lifecycle())

    watcher = app.bot_data["watcher"]
    assert isinstance(watcher, Watcher)
    sweeper = watcher._opportunistic_sweeper
    # نفس الغلاف المحدود/المخنوق، بفاصل الخنق الافتراضي.
    assert isinstance(sweeper, OpportunisticSweeper)
    assert sweeper._min_interval == OPPORTUNISTIC_SWEEP_MIN_INTERVAL_SECONDS
    # بيلفّ reaper حقيقي.
    assert isinstance(sweeper.reaper, AttachmentReaper)
    # **نفس** المالك الحقيقي: نفس اتصال القاعدة الوحيد (مفيش مالك/اتصال تاني).
    assert sweeper.reaper._db is db
    assert sweeper.reaper._db._conn is db._conn
    # جذر الـ staging هو المتوقّع لمسار القاعدة.
    assert sweeper.reaper.root == staging_root_for(config.db_path)
    # كنس الإقلاع (A4) اشتغل فعلًا: الدفعة المنتهية اتكنست والملف اتشال.
    assert not startup_file.exists()
    assert db.get_attachment_item("startup-i1").status == ATTACHMENT_ITEM_REAPED


def test_post_init_repeated_does_not_create_second_reaper_or_watcher(tmp_path):
    config = make_config(tmp_path)
    app = build_application(config)

    async def lifecycle():
        await app.post_init(app)
        first_watcher = app.bot_data["watcher"]
        first_sweeper = first_watcher._opportunistic_sweeper
        await app.post_init(app)  # إعادة تهيئة مكرّرة
        assert app.bot_data["watcher"] is first_watcher  # مفيش watcher تاني
        assert first_watcher._opportunistic_sweeper is first_sweeper  # مفيش sweeper تاني

    asyncio.run(lifecycle())
    # مفيش عامل مراقب إضافي ولا reaper إضافي.
    assert app.bot_data["watcher"] is not None


def test_watcher_without_sweeper_keeps_old_behavior():
    # بلا ربط ⇒ `_opportunistic_sweeper is None` ⇒ السلوك السابق (مفيش كنس من الـ tick).
    import tempfile
    import os

    d = tempfile.mkdtemp()
    db = Database(os.path.join(d, "s.sqlite3"))

    class _NoClient:
        async def get_conversations(self, ids):  # pragma: no cover
            return []

    watcher = Watcher(_NoClient(), db, bot=None, chat_id=1)
    assert watcher._opportunistic_sweeper is None
