"""اختبارات worker الصندوق الواحد: دورة الحياة، الحجز الذرّي، at-most-once."""
import asyncio
from types import SimpleNamespace

import pytest

from bot.db import Database
from bot.errors import ApiError
from bot.outbox import OutboxWorker, outbox_recover


class Client:
    """عميل OpenHands fake مع تحكّم في سلوك الإرسال."""

    def __init__(self, conv=None, send_error=None, on_send=None):
        self._conv = conv if conv is not None else {
            "id": "c1", "title": "شات", "execution_status": "running", "sandbox_status": "RUNNING",
        }
        self._send_error = send_error
        self._on_send = on_send
        self.sent = []

    async def get_conversations(self, ids):
        return [self._conv] if self._conv else []

    async def resume_sandbox(self, sandbox_id):
        pass

    async def send_message(self, conversation_id, text):
        if self._on_send is not None:
            self._on_send()
        if self._send_error is not None:
            raise self._send_error
        self.sent.append((conversation_id, text))


class Bot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id=None, text=None, **kw):
        self.sent.append(text)


def make_db(tmp_path):
    return Database(str(tmp_path / "t.sqlite3"))


def add_pending(db, conversation_id="c1", chat_id=99, text="برومت"):
    return db.add_outbox(conversation_id, chat_id, text, "2026-01-01T00:00:00+00:00")


def make_worker(db, client=None, bot=None, **kw):
    return OutboxWorker(client or Client(), db, bot or Bot(), **kw)


# ------------------------------------------------------------ atomic claiming
def test_claim_is_atomic_oldest_first(tmp_path):
    db = make_db(tmp_path)
    a = add_pending(db, text="a")
    b = add_pending(db, text="b")
    first = db.claim_outbox("t1")
    second = db.claim_outbox("t2")
    third = db.claim_outbox("t3")
    assert first.id == a and first.status == "claimed"
    assert second.id == b and second.status == "claimed"
    assert third is None  # مفيش pending تاني
    assert db.list_outbox_by_status("pending") == []


def test_claim_never_returns_same_record_twice(tmp_path):
    db = make_db(tmp_path)
    add_pending(db)
    first = db.claim_outbox("t1")
    second = db.claim_outbox("t2")
    assert first.id == 1
    assert second is None  # السجل اتحجز خلاص ⇒ مستحيل يرجع تاني


def test_claim_does_not_take_unknown_failed_sent(tmp_path):
    db = make_db(tmp_path)
    oid = add_pending(db)
    db.set_outbox_status(oid, "unknown", "t")
    assert db.claim_outbox("t") is None


def test_oldest_pending_id(tmp_path):
    db = make_db(tmp_path)
    assert db.oldest_pending_id() is None
    a = add_pending(db)
    add_pending(db)
    assert db.oldest_pending_id() == a


# ------------------------------------------------------------ worker lifecycle
def test_single_tick_processes_one_and_leaves_state(tmp_path):
    db = make_db(tmp_path)
    add_pending(db)
    worker = make_worker(db)
    asyncio.run(worker._tick())
    assert db.get_outbox(1).status == "sent"


def test_empty_outbox_does_not_busy_loop(tmp_path):
    db = make_db(tmp_path)
    worker = make_worker(db, poll_interval=0.001, max_idle=0.5)
    # دورة على صندوق فاضي ما بترجّعش شغل.
    assert asyncio.run(worker._tick()) is False

    # _run بينام نوم طويل (max_idle) عند الخمول، مش دورة سريعة متكرّرة.
    delays = []

    class Stop(Exception):
        pass

    async def fake_sleep(delay):
        delays.append(delay)
        raise Stop()

    worker._sleep = fake_sleep
    with pytest.raises(Stop):
        asyncio.run(worker._run())
    assert delays == [0.5]


class FakeTask:
    def __init__(self):
        self._done = False

    def done(self):
        return self._done

    def cancel(self):
        self._done = True


def test_start_creates_exactly_one_task(tmp_path, monkeypatch):
    db = make_db(tmp_path)
    worker = make_worker(db)
    created = []

    def fake_create_task(coro):
        created.append(coro)
        coro.close()
        return FakeTask()

    monkeypatch.setattr(asyncio, "create_task", fake_create_task)
    worker.start()
    worker.start()  # تاني مايعملش task جديد
    assert len(created) == 1


def test_stop_cancels_and_awaits(tmp_path):
    db = make_db(tmp_path)
    worker = make_worker(db)

    async def scenario():
        worker.start()
        task = worker._task
        await worker.stop()
        assert worker._task is None
        assert task.cancelled()

    asyncio.run(scenario())


def test_cancellation_during_post_is_unknown(tmp_path):
    db = make_db(tmp_path)
    add_pending(db)

    def on_send():
        raise asyncio.CancelledError()

    worker = make_worker(db, client=Client(on_send=on_send))
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(worker._tick())
    assert db.get_outbox(1).status == "unknown"


# ------------------------------------------------------------ retry policy
def test_safe_pre_post_failure_is_retried_after_backoff(tmp_path, monkeypatch):
    db = make_db(tmp_path)
    add_pending(db)

    class Boom:
        async def get_conversations(self, ids):
            raise ApiError("تعذّر الاتصال", None)

    worker = make_worker(db, client=Boom())
    asyncio.run(worker._tick())  # فشل قبل الـ POST
    assert db.get_outbox(1).status == "pending"  # آمن يتعاود
    assert worker._consecutive_failures == 1
    assert worker._next_delay() > worker._poll_interval  # backoff

    # نعدّي نافذة التجميع (القرار 2): السجل بقى ناضج ⇒ الـ worker يحجزه فورًا.
    monkeypatch.setattr("bot.outbox.grouping_mature_before", lambda *a, **k: "9999-12-31T23:59:59+00:00")

    # لما ينجح، الـ backoff يتصفّر.
    worker._client = Client()
    asyncio.run(worker._tick())
    assert db.get_outbox(1).status == "sent"
    assert worker._consecutive_failures == 0


def test_ambiguous_post_is_unknown_and_never_retried(tmp_path):
    db = make_db(tmp_path)
    add_pending(db)
    worker = make_worker(db, client=Client(send_error=ApiError("timeout", None)))
    asyncio.run(worker._tick())
    assert db.get_outbox(1).status == "unknown"
    # دورات تانية ما تعيدوش إرساله أبداً.
    asyncio.run(worker._tick())
    asyncio.run(worker._tick())
    assert db.get_outbox(1).status == "unknown"


def test_permanent_failure_is_failed_and_not_retried(tmp_path):
    db = make_db(tmp_path)
    add_pending(db)
    worker = make_worker(db, client=Client(send_error=ApiError("bad", 422)))
    asyncio.run(worker._tick())
    assert db.get_outbox(1).status == "failed"
    assert worker._consecutive_failures == 0  # مش إعادة تلقائية ⇒ مفيش backoff تراكمي
    asyncio.run(worker._tick())
    assert db.get_outbox(1).status == "failed"


def test_two_records_processed_independently(tmp_path):
    db = make_db(tmp_path)
    add_pending(db, text="a")
    add_pending(db, text="b")

    calls = {"n": 0}

    def on_send():
        calls["n"] += 1
        if calls["n"] == 1:
            raise ApiError("timeout", None)  # الأول غامض

    worker = make_worker(db, client=Client(on_send=on_send))
    asyncio.run(worker._tick())  # يعالج a ⇒ unknown
    asyncio.run(worker._tick())  # يعالج b ⇒ sent
    assert db.get_outbox(1).status == "unknown"
    assert db.get_outbox(2).status == "sent"


def test_no_duplicate_submission_across_ticks(tmp_path):
    db = make_db(tmp_path)
    add_pending(db)
    client = Client()
    worker = make_worker(db, client=client)
    for _ in range(5):
        asyncio.run(worker._tick())
    assert client.sent == [("c1", "برومت")]  # إرسال واحد بس
    assert db.get_outbox(1).status == "sent"


# ------------------------------------------------------------ recovery ordering
def test_recovery_before_worker_prevents_resubmission(tmp_path):
    # سجل 'sending' متروك من restart: التعافي يحوّله 'unknown' قبل ما الـ worker ياخده.
    db = make_db(tmp_path)
    oid = add_pending(db)
    db.set_outbox_status(oid, "sending", "t")

    class App:
        pass

    app = App()
    app.bot_data = {"db": db}
    app.bot = Bot()
    asyncio.run(outbox_recover(app))
    assert db.get_outbox(oid).status == "unknown"

    # الـ worker بعد التعافي مايلاقيش حاجة مؤهّلة ⇒ مفيش إعادة إرسال.
    client = Client()
    worker = make_worker(db, client=client)
    asyncio.run(worker._tick())
    assert client.sent == []
    assert db.get_outbox(oid).status == "unknown"


# ------------------------------------------------------------ cancellation stages
class BlockingClient(Client):
    """إرسال بيتعلّق على event عشان نتحكّم في لحظة الإلغاء."""

    def __init__(self, started, release, conv=None):
        super().__init__(conv=conv)
        self._started = started
        self._release = release

    async def send_message(self, conversation_id, text):
        self._started.set()
        await self._release.wait()
        self.sent.append((conversation_id, text))


def test_cancellation_before_post_leaves_claimed_then_recovers_pending(tmp_path):
    # إلغاء أثناء قراءة الشات (قبل الـ POST) ⇒ الإرسال مابدأش ⇒ 'claimed' (ملكية)،
    # والتعافي يرجّعه 'pending' (آمن، مفيش احتمال ازدواج).
    db = make_db(tmp_path)
    add_pending(db)

    class BlockingGet:
        def __init__(self):
            self.started = asyncio.Event()

        async def get_conversations(self, ids):
            self.started.set()
            await asyncio.Event().wait()  # يتعلّق للأبد

    client = BlockingGet()
    worker = make_worker(db, client=client)

    async def scenario():
        task = asyncio.ensure_future(worker._tick())
        await client.started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert db.get_outbox(1).status == "claimed"  # مابدأش POST ⇒ مش sending

    app = SimpleNamespace(bot_data={"db": db}, bot=Bot())
    asyncio.run(outbox_recover(app))
    assert db.get_outbox(1).status == "pending"  # آمن يتعاود بعد restart


def test_cancellation_during_post_leaves_unknown(tmp_path):
    db = make_db(tmp_path)
    add_pending(db)
    started = asyncio.Event()
    release = asyncio.Event()
    worker = make_worker(db, client=BlockingClient(started, release))

    async def scenario():
        task = asyncio.ensure_future(worker._tick())
        await started.wait()  # الـ POST بدأ فعلاً
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert db.get_outbox(1).status == "unknown"  # غامض ⇒ مش إعادة تلقائية


def test_shutdown_cancellation_during_post_marks_unknown(tmp_path):
    # إلغاء الـ worker نفسه (shutdown) أثناء الـ POST ⇒ 'unknown' + المهمة اتقفلت.
    db = make_db(tmp_path)
    add_pending(db)
    started = asyncio.Event()
    release = asyncio.Event()
    worker = make_worker(db, client=BlockingClient(started, release))

    async def scenario():
        worker.start()
        await started.wait()
        await worker.stop()  # cancel + await
        assert worker._task is None

    asyncio.run(scenario())
    assert db.get_outbox(1).status == "unknown"


# ------------------------------------------------------------ no-restart processing
def test_pending_is_processed_without_restart(tmp_path):
    db = make_db(tmp_path)
    add_pending(db)
    client = Client()
    worker = make_worker(db, client=client)

    async def scenario():
        worker.start()
        for _ in range(200):
            if db.get_outbox(1).status == "sent":
                break
            await asyncio.sleep(0.01)
        await worker.stop()

    asyncio.run(scenario())
    assert db.get_outbox(1).status == "sent"  # اتعالج وهو شغال، من غير restart


def test_wake_interrupts_idle_sleep_and_processes_prompt(tmp_path):
    db = make_db(tmp_path)
    client = Client()
    worker = make_worker(db, client=client, max_idle=30.0)

    async def scenario():
        worker.start()
        await asyncio.sleep(0.02)  # worker دخل نوم الخمول
        add_pending(db)  # برومت جديد
        worker.wake()  # زي ما الـ handler بيعمل
        for _ in range(200):
            if db.get_outbox(1).status == "sent":
                break
            await asyncio.sleep(0.01)
        await worker.stop()

    asyncio.run(scenario())
    assert db.get_outbox(1).status == "sent"


# ------------------------------------------------------------ two workers safety
def test_two_workers_cannot_submit_same_record_twice(tmp_path):
    db = make_db(tmp_path)
    add_pending(db)
    client = Client()
    w1 = make_worker(db, client=client)
    w2 = make_worker(db, client=client)

    async def scenario():
        # تشغيل متزامن لدورتين من اتنين workers على نفس السجل.
        await asyncio.gather(w1._tick(), w2._tick())

    asyncio.run(scenario())
    assert client.sent == [("c1", "برومت")]  # إرسال واحد بس (الحجز الذرّي)
    assert db.get_outbox(1).status == "sent"


def test_app_and_recovery_tasks_do_not_double_submit(tmp_path):
    # التعافي (sending→unknown) + worker: مفيش إرسال مزدوج.
    db = make_db(tmp_path)
    oid = add_pending(db)
    db.set_outbox_status(oid, "sending", "t")
    client = Client()
    app = SimpleNamespace(bot_data={"db": db}, bot=Bot())
    asyncio.run(outbox_recover(app))
    worker = make_worker(db, client=client)
    asyncio.run(worker._tick())
    assert client.sent == []
    assert db.get_outbox(oid).status == "unknown"


# ------------------------------------------------ TASK 53: bounded retry cap
def _mature(monkeypatch):
    """يعدّي نافذة التجميع فورًا عشان الـ worker يحجز السجل في نفس الدورة."""
    monkeypatch.setattr(
        "bot.outbox.grouping_mature_before", lambda *a, **k: "9999-12-31T23:59:59+00:00"
    )


class NeverReadyClient:
    """الشات موجود بس الـ sandbox عمره ما بيبقى RUNNING (فشل آمن قبل الـ POST).

    من غير sandbox_id عشان نتخطّى resume + wait_running (اللي بينتظر 120 ثانية)،
    وندخل نفس مسار إعادة المحاولة الآمن مباشرةً.
    """

    def __init__(self):
        self.sends = []

    async def get_conversations(self, ids):
        return [{"id": "c1", "title": "شات", "sandbox_status": "STOPPED"}]

    async def send_message(self, conversation_id, text):
        self.sends.append((conversation_id, text))


def test_sandbox_not_ready_first_attempt_notifies_once_and_increments(tmp_path, monkeypatch):
    _mature(monkeypatch)
    db = make_db(tmp_path)
    add_pending(db)
    bot = Bot()
    worker = make_worker(db, client=NeverReadyClient(), bot=bot)

    asyncio.run(worker._tick())
    item = db.get_outbox(1)
    assert item.status == "pending"  # لسه تحت الحد ⇒ آمن يتعاود
    assert item.attempts == 1
    # إشعار واحد بس عند أول محاولة.
    assert sum("sandbox" in t for t in bot.sent) == 1

    # دورات تانية تحت الحد: attempts بيزيد، ومفيش تكرار للإشعار.
    asyncio.run(worker._tick())
    assert db.get_outbox(1).attempts == 2
    assert sum("sandbox" in t for t in bot.sent) == 1  # مفيش تكرار


def test_exhaustion_marks_failed_once_with_single_notification(tmp_path, monkeypatch):
    from bot.outbox import MAX_OUTBOX_ATTEMPTS

    _mature(monkeypatch)
    db = make_db(tmp_path)
    add_pending(db)
    bot = Bot()
    worker = make_worker(db, client=NeverReadyClient(), bot=bot)

    # نستنفد الحد بالظبط.
    for _ in range(MAX_OUTBOX_ATTEMPTS):
        asyncio.run(worker._tick())

    item = db.get_outbox(1)
    assert item.status == "failed"  # الحد استُوفي ⇒ نهائي
    assert item.attempts == MAX_OUTBOX_ATTEMPTS
    # إشعار نهائي واحد بس (استنفاد)، + إشعار مؤقّت واحد عند أول محاولة = 2 إجمالًا.
    assert sum("تعذّر إرسال البرومت" in t for t in bot.sent) == 1
    assert len(bot.sent) == 2

    # دورات إضافية: السجل 'failed' مش مؤهّل ⇒ مفيش إشعار ولا إعادة.
    for _ in range(3):
        asyncio.run(worker._tick())
    assert db.get_outbox(1).status == "failed"
    assert len(bot.sent) == 2  # مفيش تكرار


def test_cap_boundary_exact_threshold(tmp_path, monkeypatch):
    # حدود دقيقة: عند attempts = الحد-1 لسه pending، وعند الحد يبقى failed.
    from bot.outbox import MAX_OUTBOX_ATTEMPTS

    _mature(monkeypatch)
    db = make_db(tmp_path)
    add_pending(db)
    worker = make_worker(db, client=NeverReadyClient(), bot=Bot())

    for i in range(1, MAX_OUTBOX_ATTEMPTS):
        asyncio.run(worker._tick())
        assert db.get_outbox(1).status == "pending", i
        assert db.get_outbox(1).attempts == i

    asyncio.run(worker._tick())  # المحاولة رقم الحد
    assert db.get_outbox(1).attempts == MAX_OUTBOX_ATTEMPTS
    assert db.get_outbox(1).status == "failed"


def test_exhaustion_transition_is_exactly_once_under_repeat(tmp_path, monkeypatch):
    # الانتقال النهائي ('failed') بيحصل مرة واحدة بس، حتى مع دورات متكررة.
    from bot.outbox import MAX_OUTBOX_ATTEMPTS

    _mature(monkeypatch)
    db = make_db(tmp_path)
    add_pending(db)
    worker = make_worker(db, client=NeverReadyClient(), bot=Bot())

    for _ in range(MAX_OUTBOX_ATTEMPTS + 5):
        asyncio.run(worker._tick())
    assert db.get_outbox(1).status == "failed"
    assert db.get_outbox(1).attempts == MAX_OUTBOX_ATTEMPTS  # مفيش زيادة بعد النهائي


def test_unknown_is_never_resent_even_with_cap(tmp_path, monkeypatch):
    # حماية at-most-once: 'unknown' (POST ممكن يكون اتقبل) مابيتاخدش أبداً، والحد مايأثرش.
    _mature(monkeypatch)
    db = make_db(tmp_path)
    add_pending(db)
    client = Client(send_error=ApiError("timeout", None))
    worker = make_worker(db, client=client, bot=Bot())

    asyncio.run(worker._tick())
    assert db.get_outbox(1).status == "unknown"
    for _ in range(10):
        asyncio.run(worker._tick())
    assert db.get_outbox(1).status == "unknown"  # ما اتعادش
    assert client.sent == []  # مفيش POST ناجح مكرّر


def test_sending_record_is_not_reclaimed_by_cap(tmp_path, monkeypatch):
    # 'sending' (POST بدأ) مابيتاخدش تلقائياً ولا يتحوّل 'failed' بسبب الحد.
    from bot.outbox import MAX_OUTBOX_ATTEMPTS

    _mature(monkeypatch)
    db = make_db(tmp_path)
    oid = add_pending(db)
    db.set_outbox_status(oid, "sending", "t0")
    client = Client()
    worker = make_worker(db, client=client, bot=Bot())

    for _ in range(MAX_OUTBOX_ATTEMPTS + 3):
        asyncio.run(worker._tick())
    assert db.get_outbox(oid).status == "sending"  # مالَمتْش
    assert client.sent == []


def test_success_path_unaffected_by_cap(tmp_path, monkeypatch):
    # مسار النجاح مااتغيرش: إرسال واحد + 'sent'، وattempts مش بتزيد.
    _mature(monkeypatch)
    db = make_db(tmp_path)
    add_pending(db)
    client = Client()
    worker = make_worker(db, client=client, bot=Bot())

    asyncio.run(worker._tick())
    assert db.get_outbox(1).status == "sent"
    assert db.get_outbox(1).attempts == 0
    assert client.sent == [("c1", "برومت")]


