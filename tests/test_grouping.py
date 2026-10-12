"""TASK 04B-09: تجميع الرسايل المتتالية خلال 1.5 ثانية (القرار 2).

بنغطّي: حدود النافذة، سلوك التدفّق (flush)، حفظ الترتيب/المحتوى، عزل المجموعات
(مستخدم/شات/وجهة)، عدم الإرسال المزدوج، واستمرار الإرسال عند الإلغاء/الانتهاء،
مع دمج صحيح مع concurrent_updates(True).
"""
import asyncio
from datetime import datetime, timedelta, timezone

from bot.db import Database, GROUP_WINDOW
from tests.test_handlers import make_context, make_update
from tests.test_outbox import Client, add_pending, make_db, make_worker

import bot.handlers as h

T0 = datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc)


def _iso(dt):
    return dt.isoformat()


# ------------------------------------------------------------------ window const
def test_group_window_is_one_and_a_half_seconds():
    assert GROUP_WINDOW == timedelta(seconds=1.5)


# ------------------------------------------------------------------ DAO semantics
def test_messages_within_window_group_into_one_row():
    db = Database(":memory:")
    db.add_or_group_outbox("c1", 99, "أول", _iso(T0))
    db.add_or_group_outbox("c1", 99, "تاني", _iso(T0 + timedelta(seconds=1.0)))
    items = db.list_outbox_by_status("pending")
    assert len(items) == 1
    assert items[0].text == "أول\nتاني"
    db.close()


def test_message_after_window_creates_new_row():
    db = Database(":memory:")
    db.add_or_group_outbox("c1", 99, "أول", _iso(T0))
    db.add_or_group_outbox("c1", 99, "تاني", _iso(T0 + timedelta(seconds=2.0)))  # > 1.5
    items = db.list_outbox_by_status("pending")
    assert len(items) == 2
    db.close()


def test_window_boundary_is_inclusive():
    # بالظبط 1.5 ثانية ⇒ لسه جوّه النافذة (<=).
    db = Database(":memory:")
    db.add_or_group_outbox("c1", 99, "أ", _iso(T0))
    db.add_or_group_outbox("c1", 99, "ب", _iso(T0 + GROUP_WINDOW))
    assert len(db.list_outbox_by_status("pending")) == 1
    db.close()

    # 1.5 ثانية + جزء بسيط من أول رسالة ⇒ سجل جديد.
    db2 = Database(":memory:")
    db2.add_or_group_outbox("c1", 99, "أ", _iso(T0))
    db2.add_or_group_outbox("c1", 99, "ب", _iso(T0 + GROUP_WINDOW + timedelta(milliseconds=1)))
    assert len(db2.list_outbox_by_status("pending")) == 2
    db2.close()


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
def test_handler_groups_consecutive_messages_one_row(tmp_path):
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    # route (مستمر) عشان كل رسالة تستهلك الحالة وتتجّم مع اللي قبلها.
    db.set_awaiting(1, "A", "route")
    for text in ("سطر1", "سطر2", "سطر3"):
        asyncio.run(h.handle_text(make_update(1, text), ctx))
    items = db.list_outbox_by_status("pending")
    assert len(items) == 1
    assert items[0].text == "سطر1\nسطر2\nسطر3"


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


def test_concurrent_handler_messages_never_split_one_batch(tmp_path):
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(1, "A", "route")
    updates = [make_update(1, f"m{i}") for i in range(12)]

    async def go():
        await asyncio.gather(*(h.handle_text(u, ctx) for u in updates))

    asyncio.run(go())
    items = db.list_outbox_by_status("pending")
    # BEGIN IMMEDIATE بيمنع سجلين لنفس الدفعة؛ كل النصوص موجودة بالترتيب.
    assert len(items) == 1
    assert items[0].text.split("\n") == [f"m{i}" for i in range(12)]


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
    db.add_or_group_outbox("c1", 99, "أول", now)
    db.add_or_group_outbox("c1", 99, "تاني", now)  # نفس الدفعة
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
    # يحصل بعد ~1.5 ثانية مش بعد 30 ثانية.
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
        # نضيف 3 رسايل بسرعة (جوّه النافذة) قبل ما نبدأ الـ loop.
        db.add_or_group_outbox("c1", 99, "أ", datetime.now(timezone.utc).isoformat())
        db.add_or_group_outbox("c1", 99, "ب", datetime.now(timezone.utc).isoformat())
        db.add_or_group_outbox("c1", 99, "ج", datetime.now(timezone.utc).isoformat())
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
        db.add_or_group_outbox("c1", 99, "أ", datetime.now(timezone.utc).isoformat())
        worker.start()
        await asyncio.sleep(0.02)  # أثناء النافذة
        # رسالة جديدة ⇒ wake + تجميع مع الأولى.
        db.add_or_group_outbox("c1", 99, "ب", datetime.now(timezone.utc).isoformat())
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
    db.add_or_group_outbox("c1", 99, "أ", datetime.now(timezone.utc).isoformat())
    db.add_or_group_outbox("c1", 99, "ب", datetime.now(timezone.utc).isoformat())
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
    db.add_or_group_outbox("c1", 99, "أ", datetime.now(timezone.utc).isoformat())
    db.add_or_group_outbox("c1", 99, "ب", datetime.now(timezone.utc).isoformat())  # نفس الدفعة
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
    assert from_str == from_dt == 1.0
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

    before = T0 + timedelta(seconds=1.0)
    after = T0 + timedelta(seconds=2.0)
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
