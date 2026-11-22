"""U04: استهلاك حالة التوجيه مرة واحدة، تأكيد الحفظ سريع، والتزامن التسلسلي."""
import asyncio
import time

import pytest
from telegram import Update
from telegram.ext import TypeHandler

import bot.handlers as h
from bot.app import build_application
from bot.config import Config
from bot.db import Database
from bot import outbox

from tests.test_handlers import make_context, make_update
from tests.test_stage2_custom_polling import _with_started_app


def test_take_awaiting_consumes_once(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.set_awaiting(1, "conv-A", "reply")
    assert db.take_awaiting(1)[:2] == ("conv-A", "reply")
    assert db.take_awaiting(1)[:2] == (None, None)
    assert db.get_awaiting(1) == (None, None)


def test_take_awaiting_without_state(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    assert db.take_awaiting(7)[:2] == (None, None)


def test_concurrent_messages_consume_state_exactly_once(tmp_path):
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "conv-A", "reply")
    updates = [make_update(1, text=f"msg{i}") for i in range(10)]

    async def go():
        await asyncio.gather(*(h.handle_text(u, ctx) for u in updates))

    asyncio.run(go())

    items = db.list_outbox_by_status("pending")
    assert len(items) == 1                       # برومبت واحد بس اتسجّل
    assert items[0].conversation_id == "conv-A"  # للشات الصح
    hints = [u for u in updates if u.message.replies and "/start" in u.message.replies[0]]
    assert len(hints) == 9                       # الباقي أخد الرد الافتراضي، مفيش إرسال تاني


def test_state_change_between_messages_routes_to_latest_chat(tmp_path):
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "conv-A", "reply")
    db.set_awaiting(1, "conv-B", "reply")  # المستخدم فتح شات تاني قبل ما يكتب
    asyncio.run(h.handle_text(make_update(1, "x"), ctx))
    assert [i.conversation_id for i in db.list_outbox_by_status("pending")] == ["conv-B"]


def test_ack_stays_under_one_second_while_slow_export_runs(tmp_path):
    ctx = make_context(1, tmp_path)
    ctx.bot_data["db"].set_awaiting(1, "conv-A", "reply")
    update = make_update(1, text="برومبت")

    async def slow_export():
        await asyncio.sleep(2)  # تصدير/قايمة ملفات بطيئة

    async def go():
        export_task = asyncio.create_task(slow_export())
        await asyncio.sleep(0)  # الأمر البطيء بدأ
        start = time.perf_counter()
        await h.handle_text(update, ctx)
        elapsed = time.perf_counter() - start
        export_task.cancel()
        return elapsed

    elapsed = asyncio.run(go())

    assert update.message.replies == ["وصل ✅"]
    assert elapsed < 1.0
    assert ctx.bot_data["db"].count_outbox("pending") == 1  # اتحفظ بثبات قبل التأكيد


def test_ack_means_durably_saved(tmp_path):
    ctx = make_context(1, tmp_path)
    ctx.bot_data["db"].set_awaiting(1, "conv-A", "reply")
    update = make_update(1, text="مهم")
    seen = {}

    original = update.message.reply_text

    async def reply_text(text, **kw):
        # لحظة التأكيد: السجل لازم يكون موجود فعلاً من اتصال تاني (يعني committed)
        other = Database(str(tmp_path / "t.sqlite3"))
        seen["count"] = other.count_outbox("pending")
        other.close()
        await original(text, **kw)

    update.message.reply_text = reply_text
    asyncio.run(h.handle_text(update, ctx))
    assert seen["count"] == 1


def test_application_requires_sequential_updates(tmp_path):
    config = Config(
        telegram_bot_token="123456:ABC-test-token",
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({1}),
        owner_id=1,
        db_path=str(tmp_path / "t.sqlite3"),
    )
    app = build_application(config)
    try:
        # PTB 22.8: concurrent_updates(False) ⇒ max_concurrent_updates == 1.
        # A truthiness check would also pass for True (256) and must not be used.
        assert app.concurrent_updates == 1
        assert app._update_processor.max_concurrent_updates == 1
    finally:
        app.bot_data["db"].close()


def test_queue_producers_are_serialized(tmp_path, monkeypatch):
    """Two concurrent queue producers cannot overlap handler execution.

    This exercises the real PTB update_queue/fetcher path, not direct
    Application.process_update() calls (which bypass the update processor).
    """
    async def run(app, install_bot):
        events = []
        started = []
        active = {"n": 0, "max": 0}
        first_started = asyncio.Event()
        second_started = asyncio.Event()
        release_first = asyncio.Event()

        async def record(update, context):
            active["n"] += 1
            active["max"] = max(active["max"], active["n"])
            started.append(update.update_id)
            events.append(("start", update.update_id))
            if len(started) == 1:
                first_started.set()
                await release_first.wait()
            else:
                second_started.set()
            events.append(("end", update.update_id))
            active["n"] -= 1

        app.add_handler(TypeHandler(Update, record), group=-2)
        updates = [Update(update_id=101), Update(update_id=102)]

        async def producer(update):
            await app.update_queue.put(update)

        try:
            await asyncio.gather(*(producer(u) for u in updates))
            await asyncio.wait_for(first_started.wait(), timeout=2)
            try:
                await asyncio.wait_for(second_started.wait(), timeout=0.05)
            except asyncio.TimeoutError:
                pass
            else:
                pytest.fail("second update started before the first completed")
            assert len(started) == 1
            assert active["max"] == 1
            release_first.set()
            await asyncio.wait_for(app.update_queue.join(), timeout=2)
            assert len(started) == 2
            assert [e[0] for e in events] == ["start", "end", "start", "end"]
            assert active["max"] == 1
            assert app.update_queue._unfinished_tasks == 0
            assert app.update_queue.qsize() == 0
        finally:
            release_first.set()

    asyncio.run(_with_started_app(tmp_path, monkeypatch, run))


def test_queue_continues_after_handler_exception(tmp_path, monkeypatch):
    async def run(app, install_bot):
        seen = []
        errors = []

        async def record(update, context):
            seen.append(update.update_id)
            if update.update_id == 201:
                raise RuntimeError("boom")

        async def on_error(update, context):
            errors.append((update.update_id, type(context.error).__name__))

        app.add_handler(TypeHandler(Update, record), group=-2)
        app.add_error_handler(on_error)
        await app.update_queue.put(Update(update_id=201))
        await app.update_queue.put(Update(update_id=202))
        await asyncio.wait_for(app.update_queue.join(), timeout=2)

        assert seen == [201, 202]
        assert errors == [(201, "RuntimeError")]
        assert app.update_queue._unfinished_tasks == 0
        assert app.update_queue.qsize() == 0

    asyncio.run(_with_started_app(tmp_path, monkeypatch, run))


def test_successful_send_records_submission_time_for_watcher(tmp_path):
    from datetime import datetime, timezone

    from tests.test_outbox import Bot, Client, add_pending, make_db

    db = make_db(tmp_path)
    oid = add_pending(db, conversation_id="c1", chat_id=99)
    before = datetime.now(timezone.utc)

    asyncio.run(outbox.deliver_outbox(Client(), db, Bot(), oid))

    watched = db.list_watched()
    assert len(watched) == 1 and watched[0].submitted_at
    submitted = datetime.fromisoformat(watched[0].submitted_at)
    assert before <= submitted <= datetime.now(timezone.utc)


def test_failed_send_does_not_start_a_submitted_watch(tmp_path):
    from bot.errors import ApiError
    from tests.test_outbox import Bot, Client, add_pending, make_db

    db = make_db(tmp_path)
    oid = add_pending(db, conversation_id="c1", chat_id=99)
    client = Client(send_error=ApiError("رفض", 422))

    asyncio.run(outbox.deliver_outbox(client, db, Bot(), oid))

    assert db.list_watched() == []
