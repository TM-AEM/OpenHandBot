"""U01 + سلوك المراقب: الانتهاء يتثبت بتقرير أحدث من وقت البرومبت، من غير حذف صامت."""
import asyncio
from datetime import datetime, timedelta, timezone

from telegram.error import TelegramError

from bot.db import Database
from bot.errors import ApiError
from bot.openhands_client import OpenHandsClient, parse_timestamp
from bot.watcher import MISSING_LIMIT, Watcher

T0 = datetime(2026, 10, 12, 10, 0, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self, now=T0):
        self.now = now

    def __call__(self):
        return self.now


class Client:
    """reports: قايمة (timestamp, text) بترتيب أي؛ get_reply_since بيطبّق نفس قاعدة الحقيقي."""

    def __init__(self, conv, reports=(), events_error=None):
        self._conv = conv
        self._reports = list(reports)
        self._events_error = events_error
        self.last_reply_calls = 0

    async def get_conversations(self, ids):
        return [self._conv[i] for i in ids if i in self._conv]

    async def get_reply_since(self, conversation_id, since):
        if self._events_error:
            raise self._events_error
        newer = [(ts, t) for ts, t in self._reports if ts > since]
        return max(newer)[1] if newer else None

    async def get_last_reply(self, conversation_id):
        self.last_reply_calls += 1
        return "تقرير قديم (آخر رد)"


class Bot:
    def __init__(self, fail=False):
        self.sent = []
        self._fail = fail

    async def send_message(self, chat_id=None, text=None, parse_mode=None, **kw):
        if self._fail:
            raise TelegramError("boom")
        self.sent.append(text)


def setup(tmp_path, state, last_state="finished", submitted=T0, title="شات", cid="c1"):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched(cid, title, chat_id=5)
    db.set_last_state(cid, last_state)
    db.mark_submitted(cid, submitted.isoformat())
    return db


def conv(state, cid="c1"):
    return {cid: {"id": cid, "title": "شات", "execution_status": state}}


def run(w):
    asyncio.run(w.tick())


# 1) شات كان finished قبل البرومبت: التقرير القديم ما يتبعتش ----------------------
def test_prompt_to_already_finished_chat_sends_no_stale_completion(tmp_path):
    db = setup(tmp_path, "finished")
    old_report = (T0 - timedelta(hours=1), "تقرير قديم")
    client = Client(conv("finished"), reports=[old_report])
    bot = Bot()
    clock = Clock(T0 + timedelta(minutes=1))

    run(Watcher(client, db, bot, chat_id=1, clock=clock))

    assert bot.sent == []
    assert db.is_watched("c1")
    assert client.last_reply_calls == 0  # ما استخدمناش "آخر رد" أبداً


def test_new_report_after_submission_is_delivered_alone(tmp_path):
    db = setup(tmp_path, "finished")
    reports = [(T0 - timedelta(hours=1), "تقرير قديم"), (T0 + timedelta(seconds=40), "تقرير جديد")]
    client = Client(conv("finished"), reports=reports)
    bot = Bot()

    run(Watcher(client, db, bot, chat_id=1, clock=Clock(T0 + timedelta(minutes=1))))

    assert len(bot.sent) == 1
    assert "تقرير جديد" in bot.sent[0]
    assert "تقرير قديم" not in bot.sent[0]
    assert not db.is_watched("c1")


def test_event_exactly_at_submission_time_is_not_new(tmp_path):
    db = setup(tmp_path, "finished")
    client = Client(conv("finished"), reports=[(T0, "نفس اللحظة")])
    bot = Bot()
    run(Watcher(client, db, bot, chat_id=1, clock=Clock(T0 + timedelta(minutes=1))))
    assert bot.sent == []


def test_finished_without_new_report_reports_explicitly_after_timeout(tmp_path):
    db = setup(tmp_path, "finished")
    client = Client(conv("finished"), reports=[(T0 - timedelta(hours=1), "قديم")])
    bot = Bot()

    run(Watcher(client, db, bot, chat_id=1, clock=Clock(T0 + timedelta(minutes=11))))

    assert len(bot.sent) == 1
    assert "لم يظهر تقرير جديد" in bot.sent[0]
    assert "قديم" not in bot.sent[0]
    assert not db.is_watched("c1")  # إزالة بعد إشعار صريح، مش صامتة


def test_timeout_notice_failure_keeps_watch(tmp_path):
    db = setup(tmp_path, "finished")
    client = Client(conv("finished"))
    run(Watcher(client, db, Bot(fail=True), chat_id=1, clock=Clock(T0 + timedelta(minutes=11))))
    assert db.is_watched("c1")


def test_transient_events_error_keeps_watch_and_state(tmp_path):
    db = setup(tmp_path, "finished", last_state="running")
    client = Client(conv("finished"), events_error=ApiError("خطأ", 503))
    bot = Bot()

    run(Watcher(client, db, bot, chat_id=1, clock=Clock(T0 + timedelta(minutes=1))))

    assert bot.sent == []
    assert db.is_watched("c1")
    assert db.list_watched()[0].last_state == "running"


# حالات الشات --------------------------------------------------------------
def test_waiting_for_confirmation_after_real_transition_notifies(tmp_path):
    db = setup(tmp_path, "x", last_state="running")
    client = Client(conv("waiting_for_confirmation"))
    bot = Bot()
    run(Watcher(client, db, bot, chat_id=1, clock=Clock(T0 + timedelta(minutes=1))))
    assert len(bot.sent) == 1 and "تأكيد" in bot.sent[0]
    assert not db.is_watched("c1")


def test_stale_waiting_for_confirmation_without_transition_does_not_notify(tmp_path):
    db = setup(tmp_path, "x", last_state="waiting_for_confirmation")
    client = Client(conv("waiting_for_confirmation"))
    bot = Bot()
    run(Watcher(client, db, bot, chat_id=1, clock=Clock(T0 + timedelta(minutes=1))))
    assert bot.sent == []
    assert db.is_watched("c1")


import pytest


@pytest.mark.parametrize("state", ["idle", "paused", "running"])
def test_idle_and_paused_keep_watching_without_notify(tmp_path, state):
    db = setup(tmp_path, state)
    bot = Bot()
    run(Watcher(Client(conv(state)), db, bot, chat_id=1, clock=Clock(T0 + timedelta(minutes=2))))
    assert bot.sent == []
    assert db.is_watched("c1")
    assert db.list_watched()[0].last_state == state


def test_follow_timeout_gives_explicit_notice_not_silent_delete(tmp_path):
    db = setup(tmp_path, "running", last_state="running")
    client = Client(conv("running"))
    bot = Bot()
    run(Watcher(client, db, bot, chat_id=1, clock=Clock(T0 + timedelta(hours=25))))
    assert len(bot.sent) == 1 and "24 ساعة" in bot.sent[0]
    assert not db.is_watched("c1")


def test_follow_timeout_not_reached_keeps_watching(tmp_path):
    db = setup(tmp_path, "running", last_state="running")
    bot = Bot()
    run(Watcher(Client(conv("running")), db, bot, chat_id=1, clock=Clock(T0 + timedelta(hours=23))))
    assert bot.sent == [] and db.is_watched("c1")


# شات مفقود -----------------------------------------------------------------
def test_missing_conversation_notifies_after_repeated_misses(tmp_path):
    db = setup(tmp_path, "x")
    bot = Bot()
    w = Watcher(Client({}), db, bot, chat_id=1, clock=Clock(T0))
    for _ in range(MISSING_LIMIT - 1):
        run(w)
        assert bot.sent == [] and db.is_watched("c1")
    run(w)
    assert len(bot.sent) == 1 and "لم يعد موجوداً" in bot.sent[0]
    assert not db.is_watched("c1")


def test_missing_counter_resets_when_conversation_reappears(tmp_path):
    db = setup(tmp_path, "x", last_state="running")
    bot = Bot()
    present = Client(conv("running"))
    w = Watcher(Client({}), db, bot, chat_id=1, clock=Clock(T0))
    for _ in range(MISSING_LIMIT - 1):
        run(w)
    w._client = present
    run(w)  # ظهر تاني → العدّاد يتصفّر
    w._client = Client({})
    for _ in range(MISSING_LIMIT - 1):
        run(w)
    assert bot.sent == [] and db.is_watched("c1")


def test_missing_notice_failure_keeps_watch(tmp_path):
    db = setup(tmp_path, "x")
    w = Watcher(Client({}), db, Bot(fail=True), chat_id=1, clock=Clock(T0))
    for _ in range(MISSING_LIMIT + 2):
        run(w)
    assert db.is_watched("c1")


# عزل الشاتات -----------------------------------------------------------------
def test_events_failure_for_one_chat_does_not_block_another(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    for cid in ("a", "b"):
        db.add_watched(cid, cid, chat_id=5)
        db.set_last_state(cid, "running")
        db.mark_submitted(cid, T0.isoformat())

    class Mixed(Client):
        async def get_reply_since(self, conversation_id, since):
            if conversation_id == "a":
                raise ApiError("x", 500)
            return "تقرير b"

    both = {**conv("finished", "a"), **conv("finished", "b")}
    bot = Bot()
    run(Watcher(Mixed(both), db, bot, chat_id=1, clock=Clock(T0 + timedelta(minutes=1))))

    assert any("تقرير b" in t for t in bot.sent)
    assert db.is_watched("a") and not db.is_watched("b")


# طبقة العميل ---------------------------------------------------------------
def test_parse_timestamp_variants():
    assert parse_timestamp("2026-10-12T10:00:00Z") == T0
    assert parse_timestamp("2026-10-12T10:00:00") == T0  # بدون منطقة = UTC
    assert parse_timestamp("2026-10-12T13:00:00+03:00") == T0
    assert parse_timestamp("garbage") is None and parse_timestamp(None) is None and parse_timestamp("") is None


def test_client_get_reply_since_filters_by_timestamp():
    import httpx

    def handler(request):
        events = [
            {"kind": "MessageEvent", "source": "agent", "timestamp": "2026-10-12T10:00:30Z",
             "llm_message": {"content": [{"type": "text", "text": "جديد"}]}},
            {"kind": "MessageEvent", "source": "user", "timestamp": "2026-10-12T10:00:10Z",
             "llm_message": {"content": [{"type": "text", "text": "برومبتي"}]}},
            {"kind": "MessageEvent", "source": "agent", "timestamp": "2026-10-12T09:00:00Z",
             "llm_message": {"content": [{"type": "text", "text": "قديم"}]}},
        ]
        return httpx.Response(200, json={"items": events})

    async def go(since):
        client = OpenHandsClient("https://x.test", "k", transport=httpx.MockTransport(handler))
        try:
            return await client.get_reply_since("c1", since)
        finally:
            await client.aclose()

    assert asyncio.run(go(T0)) == "جديد"
    assert asyncio.run(go(T0 + timedelta(seconds=40))) is None  # ما فيش أحدث


def test_client_events_without_timestamp_never_count():
    import httpx

    def handler(request):
        return httpx.Response(200, json={"items": [
            {"kind": "MessageEvent", "source": "agent",
             "llm_message": {"content": [{"type": "text", "text": "بدون وقت"}]}}]})

    async def go():
        client = OpenHandsClient("https://x.test", "k", transport=httpx.MockTransport(handler))
        try:
            return await client.get_reply_since("c1", T0)
        finally:
            await client.aclose()

    assert asyncio.run(go()) is None


# ------------------------- TASK 54: bounded persistent notify retries (submitted)
from bot.watcher import MAX_WATCH_NOTIFY_RETRIES


def test_submitted_notify_failure_increments_persistent_counter(tmp_path):
    db = setup(tmp_path, "finished", last_state="running")
    client = Client(conv("finished"), reports=[(T0 + timedelta(seconds=40), "تقرير جديد")])
    run(Watcher(client, db, Bot(fail=True), chat_id=1, clock=Clock(T0 + timedelta(minutes=1))))

    assert db.is_watched("c1")
    assert db.list_watched()[0].retry_count == 1


def test_submitted_notify_retries_stop_at_limit(tmp_path):
    db = setup(tmp_path, "finished", last_state="running")
    client = Client(conv("finished"), reports=[(T0 + timedelta(seconds=40), "تقرير جديد")])
    w = Watcher(client, db, Bot(fail=True), chat_id=1, clock=Clock(T0 + timedelta(minutes=1)))

    for i in range(1, MAX_WATCH_NOTIFY_RETRIES):
        run(w)
        assert db.is_watched("c1")
        assert db.list_watched()[0].retry_count == i

    run(w)  # المحاولة رقم الحد
    assert not db.is_watched("c1")  # استسلمنا


def test_submitted_no_repeat_after_exhaustion(tmp_path):
    db = setup(tmp_path, "finished", last_state="running")
    client = Client(conv("finished"), reports=[(T0 + timedelta(seconds=40), "تقرير جديد")])
    w = Watcher(client, db, Bot(fail=True), chat_id=1, clock=Clock(T0 + timedelta(minutes=1)))

    for _ in range(MAX_WATCH_NOTIFY_RETRIES + 4):
        run(w)
    assert not db.is_watched("c1")


def test_submitted_retry_count_survives_restart(tmp_path):
    path = str(tmp_path / "t.sqlite3")
    db = Database(path)
    db.add_watched("c1", "شات", chat_id=5)
    db.set_last_state("c1", "running")
    db.mark_submitted("c1", T0.isoformat())
    client = Client(conv("finished"), reports=[(T0 + timedelta(seconds=40), "تقرير جديد")])
    run(Watcher(client, db, Bot(fail=True), chat_id=1, clock=Clock(T0 + timedelta(minutes=1))))
    assert db.list_watched()[0].retry_count == 1
    db.close()

    db2 = Database(path)
    run(Watcher(client, db2, Bot(fail=True), chat_id=1, clock=Clock(T0 + timedelta(minutes=1))))
    assert db2.list_watched()[0].retry_count == 2  # اتراكم بعد "إعادة التشغيل"
    db2.close()


def test_submitted_successful_notify_unchanged(tmp_path):
    db = setup(tmp_path, "finished", last_state="running")
    client = Client(conv("finished"), reports=[(T0 + timedelta(seconds=40), "تقرير جديد")])
    bot = Bot()
    run(Watcher(client, db, bot, chat_id=1, clock=Clock(T0 + timedelta(minutes=1))))
    assert len(bot.sent) == 1
    assert "تقرير جديد" in bot.sent[0]
    assert not db.is_watched("c1")
