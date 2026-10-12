"""U04: استهلاك حالة التوجيه مرة واحدة، تأكيد الحفظ سريع، والتزامن مفعّل."""
import asyncio
import time

import bot.handlers as h
from bot.app import build_application
from bot.config import Config
from bot.db import Database
from bot import outbox

from tests.test_handlers import make_context, make_update


def test_pop_awaiting_consumes_once(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.set_awaiting(1, "conv-A", "reply")
    assert db.pop_awaiting(1) == ("conv-A", "reply")
    assert db.pop_awaiting(1) == (None, None)
    assert db.get_awaiting(1) == (None, None)


def test_pop_awaiting_without_state(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    assert db.pop_awaiting(7) == (None, None)


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


def test_application_enables_concurrent_updates(tmp_path):
    config = Config(
        telegram_bot_token="123456:ABC-test-token",
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({1}),
        owner_id=1,
        db_path=str(tmp_path / "t.sqlite3"),
    )
    app = build_application(config)
    assert app.concurrent_updates


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
