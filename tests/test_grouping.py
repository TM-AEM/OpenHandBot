"""NEW-04: تجميع تلقائي بنافذة خمول 3 ثوانٍ، مع الحفاظ على هوية NEW-02.

بنغطّي: التجميع داخل النافذة، إعادة ضبط العدّاد مع كل جزء، الحدّ عند 3 ثوانٍ،
الترتيب حسب Telegram message_id، منع تكرار نفس الرسالة، عزل المستخدم/الشات/الوجهة،
تأخير نضج الـ worker، وعدم الإرسال المزدوج أو إعادة إرسال حالة غامضة.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from bot.db import Database, GROUP_WINDOW
from tests.test_handlers import make_context, make_update
from tests.test_outbox import Client, add_pending, make_db, make_worker

import bot.handlers as h

T0 = datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc)


def _iso(dt):
    return dt.isoformat()


# ------------------------------------------------------------------ window const
def test_group_window_is_three_seconds():
    assert GROUP_WINDOW == timedelta(seconds=3)


# ------------------------------------------------------------------ DAO semantics
def test_messages_within_window_group_into_one_row():
    db = Database(":memory:")
    db.add_or_group_outbox("c1", 99, "أول", _iso(T0), telegram_message_id=11)
    db.add_or_group_outbox(
        "c1", 99, "تاني", _iso(T0 + timedelta(seconds=2.5)),
        telegram_message_id=12,
    )
    db.add_or_group_outbox(
        "c1", 99, "تالت", _iso(T0 + timedelta(seconds=5.0)),
        telegram_message_id=13,
    )
    items = db.list_outbox_by_status("pending")
    assert len(items) == 1
    assert items[0].text == "أول\nتاني\nتالت"
    assert items[0].telegram_message_ids == (11, 12, 13)
    assert items[0].updated_at == _iso(T0 + timedelta(seconds=5.0))
    db.close()


def test_reply_linked_messages_group_into_one_row():
    db = Database(":memory:")
    first = db.add_or_group_outbox(
        "c1", 99, "أول", _iso(T0), telegram_message_id=11
    )
    second = db.add_or_group_outbox(
        "c1", 99, "تاني", _iso(T0 + timedelta(seconds=1.0)),
        telegram_message_id=12, reply_to_message_id=11,
    )
    assert second == first
    items = db.list_outbox_by_status("pending")
    assert len(items) == 1
    assert items[0].text == "أول\nتاني"
    assert items[0].telegram_message_ids == (11, 12)
    db.close()


def test_message_after_window_creates_new_row():
    db = Database(":memory:")
    db.add_or_group_outbox("c1", 99, "أول", _iso(T0), telegram_message_id=11)
    db.add_or_group_outbox(
        "c1", 99, "تاني", _iso(T0 + GROUP_WINDOW + timedelta(milliseconds=1)),
        telegram_message_id=12,
    )
    items = db.list_outbox_by_status("pending")
    assert len(items) == 2
    assert [item.text for item in items] == ["أول", "تاني"]
    db.close()


def test_exact_window_boundary_groups():
    db = Database(":memory:")
    db.add_or_group_outbox("c1", 99, "أول", _iso(T0), telegram_message_id=11)
    db.add_or_group_outbox(
        "c1", 99, "تاني", _iso(T0 + GROUP_WINDOW), telegram_message_id=12
    )
    items = db.list_outbox_by_status("pending")
    assert len(items) == 1
    assert items[0].text == "أول\nتاني"
    db.close()


def test_reply_relationship_groups_regardless_of_window():
    db = Database(":memory:")
    db.add_or_group_outbox("c1", 99, "أ", _iso(T0), telegram_message_id=11)
    db.add_or_group_outbox(
        "c1", 99, "ب", _iso(T0 + GROUP_WINDOW + timedelta(seconds=5)),
        telegram_message_id=12, reply_to_message_id=11,
    )
    assert len(db.list_outbox_by_status("pending")) == 1
    db.close()


def test_duplicate_message_id_does_not_duplicate_content():
    db = Database(":memory:")
    oid = db.add_or_group_outbox("c1", 99, "أول", _iso(T0), telegram_message_id=11)
    again = db.add_or_group_outbox(
        "c1", 99, "أول-مكرر", _iso(T0 + timedelta(seconds=1)),
        telegram_message_id=11, update_id=9001,
    )
    assert again == oid
    item = db.get_outbox(oid)
    assert item.text == "أول"
    assert item.telegram_message_ids == (11,)
    db.close()


def test_out_of_order_message_ids_are_sorted_for_display():
    db = Database(":memory:")
    oid = db.add_or_group_outbox("c1", 99, "ثاني", _iso(T0), telegram_message_id=12)
    db.add_or_group_outbox(
        "c1", 99, "أول", _iso(T0 + timedelta(seconds=1)), telegram_message_id=11
    )
    item = db.get_outbox(oid)
    assert item.text == "أول\nثاني"
    assert item.telegram_message_ids == (11, 12)
    db.close()


def test_client_ref_rows_are_not_time_grouped():
    db = Database(":memory:")
    first = db.add_or_group_outbox(
        "c1", 99, "أ", _iso(T0), client_ref="r1"
    )
    second = db.add_or_group_outbox(
        "c1", 99, "ب", _iso(T0 + timedelta(seconds=1)), client_ref="r2"
    )
    assert first != second
    assert len(db.list_outbox_by_status("pending")) == 2
    db.close()


def test_grouping_isolated_by_conversation_and_chat():
    db = Database(":memory:")
    db.add_or_group_outbox("c1", 99, "x", _iso(T0))
    db.add_or_group_outbox("c2", 99, "y", _iso(T0))  # وجهة تانية ⇒ سجل منفصل
    db.add_or_group_outbox("c1", 55, "z", _iso(T0))  # شات تيليجرام تاني ⇒ سجل منفصل
    assert len(db.list_outbox_by_status("pending")) == 3
    db.close()


def test_only_pending_rows_are_grouped_not_sent():
    db = Database(":memory:")
    oid = db.add_or_group_outbox("c1", 99, "أول", _iso(T0))
    db.set_outbox_status(oid, "sent", _iso(T0))
    # بعد الإرسال، رسالة جديدة ⇒ سجل جديد (مفيش تجميع مع سجل منتهي).
    db.add_or_group_outbox("c1", 99, "تاني", _iso(T0))
    assert len(db.list_outbox_by_status("pending")) == 1
    assert db.get_outbox(oid).status == "sent"
    db.close()


# ------------------------------------------------------------------ handler level
def test_handler_groups_rapid_messages_into_one_row(tmp_path):
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "A", "route")
    for i, text in enumerate(("سطر1", "سطر2", "سطر3"), start=1):
        update = make_update(1, text)
        update.update_id = 100 + i
        update.message.message_id = 200 + i
        asyncio.run(h.handle_text(update, ctx))
    items = db.list_outbox_by_status("pending")
    assert len(items) == 1
    assert items[0].text == "سطر1\nسطر2\nسطر3"
    assert items[0].telegram_message_ids == (201, 202, 203)


def test_handler_new_row_after_window(tmp_path, monkeypatch):
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "A", "route")
    clock = ["2026-01-01T00:00:00+00:00"]
    monkeypatch.setattr("bot.outbox.now_iso", lambda: clock[0])
    for i, (when, text) in enumerate(
        (
            ("2026-01-01T00:00:00+00:00", "أول"),
            ("2026-01-01T00:00:02+00:00", "تاني"),
            ("2026-01-01T00:00:05.100000+00:00", "تالت"),
        ),
        start=1,
    ):
        clock[0] = when
        update = make_update(1, text)
        update.update_id = 150 + i
        update.message.message_id = 250 + i
        asyncio.run(h.handle_text(update, ctx))
    items = db.list_outbox_by_status("pending")
    assert len(items) == 2
    assert [item.text for item in items] == ["أول\nتاني", "تالت"]
    assert [item.telegram_message_ids for item in items] == [(251, 252), (253,)]


def test_handler_groups_explicit_reply_parts(tmp_path):
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "A", "route")
    first = make_update(1, "سطر1")
    first.update_id = 301
    first.message.message_id = 11
    second = make_update(1, "سطر2")
    second.update_id = 302
    second.message.message_id = 12
    second.message.reply_to_message = SimpleNamespace(message_id=11)
    asyncio.run(h.handle_text(first, ctx))
    asyncio.run(h.handle_text(second, ctx))
    items = db.list_outbox_by_status("pending")
    assert len(items) == 1
    assert items[0].text == "سطر1\nسطر2"
    assert items[0].telegram_message_ids == (11, 12)


def test_handler_isolates_two_conversations(tmp_path):
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "A", "reply")
    asyncio.run(h.handle_text(make_update(1, "للـ A"), ctx))
    db.set_awaiting(1, "B", "reply")
    asyncio.run(h.handle_text(make_update(1, "للـ B"), ctx))
    items = db.list_outbox_by_status("pending")
    assert {i.conversation_id for i in items} == {"A", "B"}
    assert len(items) == 2


def test_concurrent_handler_messages_group_without_loss(tmp_path):
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "A", "route")
    updates = []
    for i in range(12):
        update = make_update(1, f"m{i}")
        update.update_id = 400 + i
        update.message.message_id = 500 + i
        updates.append(update)

    async def go():
        await asyncio.gather(*(h.handle_text(u, ctx) for u in updates))

    asyncio.run(go())
    items = db.list_outbox_by_status("pending")
    assert len(items) == 1
    assert items[0].text.split("\n") == [f"m{i}" for i in range(12)]
    assert items[0].telegram_message_ids == tuple(500 + i for i in range(12))


# ------------------------------------------------------------------ worker gating
def test_worker_does_not_claim_until_window_matures(tmp_path):
    db = make_db(tmp_path)
    add_pending(db)  # updated_at = 2026-01-01 (قديم ⇒ ناضج فورًا)
    worker = make_worker(db, client=Client())
    # قديم ⇒ ناضج ⇒ يتقال فورًا (مفيش تأخير).
    assert asyncio.run(worker._tick()) is True
    assert db.get_outbox(1).status == "sent"


def test_worker_waits_for_fresh_batch_then_sends_once(tmp_path, monkeypatch):
    db = make_db(tmp_path)
    now = datetime.now(timezone.utc).isoformat()
    db.add_or_group_outbox("c1", 99, "أول", now, telegram_message_id=11)
    db.add_or_group_outbox(
        "c1", 99, "تاني", now, telegram_message_id=12, reply_to_message_id=11
    )
    client = Client()
    worker = make_worker(db, client=client)
    # لسه جوّه النافذة ⇒ مفيش حجز.
    assert asyncio.run(worker._tick()) is False
    assert client.sent == []
    # النافذة عدّت (بنصغّرها لصفر) ⇒ حجز وإرسال مرة واحدة بالنص المجمّع.
    monkeypatch.setattr("bot.db.GROUP_WINDOW", timedelta(0))
    assert asyncio.run(worker._tick()) is True
    assert client.sent == [("c1", "أول\nتاني")]


def test_next_delay_sleeps_until_maturity(tmp_path):
    db = make_db(tmp_path)
    now = datetime.now(timezone.utc).isoformat()
    db.add_or_group_outbox("c1", 99, "أول", now)
    worker = make_worker(db, client=Client())
    delay = worker._next_delay()
    assert 0 < delay <= GROUP_WINDOW.total_seconds() + 0.01


def test_idle_delay_waits_for_group_not_long_idle(tmp_path):
    # انحدار: الدفعة الطازة بتنام لحد نافذة التجميع (مش الخمول الطويل)، عشان الإرسال
    # يحصل بعد ~3 ثوانٍ مش بعد 30 ثانية.
    db = make_db(tmp_path)
    now = datetime.now(timezone.utc).isoformat()
    db.add_or_group_outbox("c1", 99, "أول", now)
    worker = make_worker(db, client=Client())  # max_idle الافتراضي 30s
    assert worker._max_idle > GROUP_WINDOW.total_seconds()
    delay = worker._idle_delay()
    assert 0 < delay <= GROUP_WINDOW.total_seconds() + 0.01


def test_idle_delay_long_when_box_empty(tmp_path):
    db = make_db(tmp_path)
    worker = make_worker(db, client=Client())
    assert worker._idle_delay() == worker._max_idle  # مفيش عمل ⇒ خمول طويل


# ------------------------------------------------------------------ real loop
def test_run_loop_flushes_group_without_manual_tick(tmp_path, monkeypatch):
    """اختبار حتمي للـ loop الحقيقي: نافذة 50ms، الرسايل بتتجمّع وبتتبعت مرة واحدة."""
    monkeypatch.setattr("bot.db.GROUP_WINDOW", timedelta(milliseconds=50))
    db = make_db(tmp_path)
    client = Client()
    worker = make_worker(db, client=client, poll_interval=0.01, max_idle=0.05)

    async def scenario():
        # ثلاثة أجزاء مرتبطة بردّ صريح قبل ما نبدأ الـ loop.
        db.add_or_group_outbox(
            "c1", 99, "أ", datetime.now(timezone.utc).isoformat(), telegram_message_id=11
        )
        db.add_or_group_outbox(
            "c1", 99, "ب", datetime.now(timezone.utc).isoformat(),
            telegram_message_id=12, reply_to_message_id=11,
        )
        db.add_or_group_outbox(
            "c1", 99, "ج", datetime.now(timezone.utc).isoformat(),
            telegram_message_id=13, reply_to_message_id=11,
        )
        worker.start()
        # نستنى لحد ما يبعت (نافذة 50ms + هامش).
        for _ in range(100):
            if client.sent:
                break
            await asyncio.sleep(0.02)
        await worker.stop()

    asyncio.run(scenario())
    assert client.sent == [("c1", "أ\nب\nج")]  # إرسال واحد بالنص المجمّع كامل
    assert db.get_outbox(1).status == "sent"


def test_wake_during_sleep_still_flushes_single_group(tmp_path, monkeypatch):
    """wake() جت من رسالة جديدة أثناء النوم ⇒ الدفعة لسه بتتجمّع وبتتبعت مرة واحدة."""
    monkeypatch.setattr("bot.db.GROUP_WINDOW", timedelta(milliseconds=60))
    db = make_db(tmp_path)
    client = Client()
    worker = make_worker(db, client=client, poll_interval=0.01, max_idle=0.05)

    async def scenario():
        db.add_or_group_outbox(
            "c1", 99, "أ", datetime.now(timezone.utc).isoformat(), telegram_message_id=11
        )
        worker.start()
        await asyncio.sleep(0.02)  # أثناء النافذة
        # ردّ صريح على الجزء الأول ⇒ wake + تجميع مع الأولى.
        db.add_or_group_outbox(
            "c1", 99, "ب", datetime.now(timezone.utc).isoformat(),
            telegram_message_id=12, reply_to_message_id=11,
        )
        worker.wake()
        for _ in range(100):
            if client.sent:
                break
            await asyncio.sleep(0.02)
        await worker.stop()

    asyncio.run(scenario())
    assert client.sent == [("c1", "أ\nب")]


def test_cancelled_group_is_flushed_after_restart(tmp_path, monkeypatch):
    """لو البوت قفل والدفعة لسه 'pending'، التشغيل الجديد بيبعت النص المجمّع مرة واحدة."""
    db = make_db(tmp_path)
    db.add_or_group_outbox(
        "c1", 99, "أ", datetime.now(timezone.utc).isoformat(), telegram_message_id=11
    )
    db.add_or_group_outbox(
        "c1", 99, "ب", datetime.now(timezone.utc).isoformat(),
        telegram_message_id=12, reply_to_message_id=11,
    )
    # restart: نفس قاعدة البيانات، worker جديد.
    client = Client()
    worker = make_worker(db, client=client)
    monkeypatch.setattr("bot.db.GROUP_WINDOW", timedelta(0))
    asyncio.run(worker._tick())
    assert client.sent == [("c1", "أ\nب")]  # مرة واحدة، مفيش ازدواج


# ------------------------------------------------------------------ at-most-once
def test_grouped_batch_is_sent_at_most_once_after_ambiguous(tmp_path, monkeypatch):
    """نتيجة غامضة على الدفعة المجمّعة ⇒ unknown، ومستحيل تتبعت تاني."""
    from bot.errors import ApiError

    db = make_db(tmp_path)
    db.add_or_group_outbox(
        "c1", 99, "أ", datetime.now(timezone.utc).isoformat(), telegram_message_id=11
    )
    db.add_or_group_outbox(
        "c1", 99, "ب", datetime.now(timezone.utc).isoformat(),
        telegram_message_id=12, reply_to_message_id=11,
    )
    client = Client(send_error=ApiError("timeout", None))
    worker = make_worker(db, client=client)
    monkeypatch.setattr("bot.db.GROUP_WINDOW", timedelta(0))  # نافذة عدّت ⇒ الدفعة جاهزة
    asyncio.run(worker._tick())
    assert db.get_outbox(1).status == "unknown"
    assert client.sent == []  # فشل ⇒ مفيش إرسال ناجح
    # دورات تانية ما بتعيدش الإرسال.
    client._send_error = None
    asyncio.run(worker._tick())
    asyncio.run(worker._tick())
    assert client.sent == []


# ------------------------------------------------------- FINAL-02 timing consistency
def test_seconds_until_mature_at_matches_string_variant():
    # نفس اللحظة عبر المسارين (نص/dt) تعطي نفس النتيجة — اتّساق قراءة الساعة.
    from bot.db import Database

    db = Database(":memory:")
    db.add_or_group_outbox("c1", 99, "أ", _iso(T0))
    from_str = db.seconds_until_mature(_iso(T0 + timedelta(seconds=0.5)), GROUP_WINDOW)
    from_dt = db.seconds_until_mature_at(T0 + timedelta(seconds=0.5), GROUP_WINDOW)
    assert from_str == from_dt == 2.5
    db.close()


def test_seconds_until_mature_zero_when_already_mature():
    from bot.db import Database

    db = Database(":memory:")
    db.add_or_group_outbox("c1", 99, "أ", _iso(T0))
    assert db.seconds_until_mature_at(T0 + GROUP_WINDOW, GROUP_WINDOW) == 0.0
    assert db.seconds_until_mature_at(T0 + timedelta(seconds=5), GROUP_WINDOW) == 0.0
    db.close()


def test_seconds_until_mature_none_when_no_pending():
    from bot.db import Database

    db = Database(":memory:")
    assert db.seconds_until_mature_at(T0, GROUP_WINDOW) is None
    db.close()


def test_delay_and_claim_use_single_consistent_timestamp(tmp_path):
    # الحالة الحرجة: صف بينضج بالظبط عند الحد. بنثبّت الساعة على اللحظة دي في المسارين،
    # فثواني النضج = 0، والحجز بنفس اللحظة ينضج ويرسل مرة واحدة، من غير نوم ولا تأخير.
    db = make_db(tmp_path)
    db.add_or_group_outbox("c1", 99, "أ", _iso(T0))
    client = Client()
    worker = make_worker(db, client=client)

    import bot.outbox as ob

    fixed_now = T0 + GROUP_WINDOW  # بالظبط على الحد ⇒ ناضج (<=)
    orig_utcnow = ob._utcnow
    ob._utcnow = lambda: fixed_now  # type: ignore[assignment]
    try:
        assert worker._remaining_until_mature() == 0.0
        assert worker._idle_delay() == 0.0
        assert asyncio.run(worker._tick()) is True
        assert client.sent == [("c1", "أ")]
    finally:
        ob._utcnow = orig_utcnow  # type: ignore[assignment]


def test_maturing_row_is_claimed_on_next_schedule(tmp_path):
    # صف مش ناضج في اللحظة الأولى (نوم > 0)، وبعد ما ينضج يتحجز ويتسلّم مرة واحدة.
    db = make_db(tmp_path)
    db.add_or_group_outbox("c1", 99, "أ", _iso(T0))
    client = Client()
    worker = make_worker(db, client=client)

    import bot.outbox as ob

    before = T0 + timedelta(seconds=2.5)
    after = T0 + timedelta(seconds=3.0)
    orig = ob._utcnow

    ob._utcnow = lambda: before  # type: ignore[assignment]
    try:
        assert worker._remaining_until_mature() == 0.5  # لسه جوّه النافذة
        assert asyncio.run(worker._tick()) is False  # مش ناضج ⇒ مفيش حجز
        assert client.sent == []
    finally:
        ob._utcnow = orig  # type: ignore[assignment]

    ob._utcnow = lambda: after  # type: ignore[assignment]
    try:
        assert worker._remaining_until_mature() == 0.0  # نضج
        assert asyncio.run(worker._tick()) is True
        assert client.sent == [("c1", "أ")]
    finally:
        ob._utcnow = orig  # type: ignore[assignment]
