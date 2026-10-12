"""اختبارات إنشاء الشات الجديد بأمان (creation job) + at-most-once + التعافي."""
import asyncio

import pytest

from bot.db import Database
from bot.errors import ApiError
from bot.outbox import CreationWorker, creation_recover


class Bot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id=None, text=None, **kw):
        self.sent.append(text)


class CreationClient:
    """عميل fake لإنشاء الشات: تحكّم في start_conversation/wait_for_start."""

    def __init__(self, task_id="task-1", conv="conv-1", start_error=None, wait_error=None,
                 poll_results=None):
        self._task_id = task_id
        self._conv = conv
        self._start_error = start_error
        self._wait_error = wait_error
        self._poll_results = list(poll_results) if poll_results else None
        self.start_calls = 0
        self.poll_calls = 0

    async def start_conversation(self, text, repo, branch=None):
        self.start_calls += 1
        if isinstance(self._start_error, BaseException):
            raise self._start_error
        return self._task_id

    async def wait_for_start(self, task_id, timeout=180.0, interval=3.0):
        self.poll_calls += 1
        if isinstance(self._wait_error, BaseException):
            raise self._wait_error
        if self._poll_results:
            value = self._poll_results.pop(0)
            if isinstance(value, BaseException):
                raise value
            return value
        return self._conv


def make_db(tmp_path):
    return Database(str(tmp_path / "t.sqlite3"))


def add_job(db, chat_id=99, repo="o/r", text="برومت"):
    return db.add_creation_job(chat_id, repo, text, "2026-01-01T00:00:00+00:00")


def make_worker(db, client=None, base_url="https://app.all-hands.dev", **kw):
    return CreationWorker(client or CreationClient(), db, Bot(), base_url, **kw)


# ------------------------------------------------------------ persistence + happy path
def test_creation_request_persisted_before_post(tmp_path):
    db = make_db(tmp_path)
    client = CreationClient()
    worker = make_worker(db, client)
    jid = add_job(db)
    asyncio.run(worker._tick())
    assert client.start_calls == 1
    job = db.get_creation_job(jid)
    assert job.status == "done"
    assert job.conversation_id == "conv-1"
    assert job.task_id == "task-1"  # الـ API رجّعه فعلاً
    assert db.is_watched("conv-1")


def test_confirmed_creation_not_repeated_after_restart(tmp_path):
    db = make_db(tmp_path)
    client = CreationClient()
    worker = make_worker(db, client)
    jid = add_job(db)
    asyncio.run(worker._tick())
    assert client.start_calls == 1
    # restart: التعافي مايلمسش 'done'، والـ worker مايلاقيش شغل.
    app = _app(db)
    asyncio.run(creation_recover(app))
    assert db.get_creation_job(jid).status == "done"
    asyncio.run(worker._tick())
    assert client.start_calls == 1  # ما اتعادش


def _app(db, bot=None):
    from types import SimpleNamespace

    return SimpleNamespace(bot_data={"db": db}, bot=bot or Bot())


# ------------------------------------------------------------ crash / cancellation
def test_crash_before_post_is_recoverable(tmp_path):
    # إلغاء قبل POST البدء ⇒ 'claimed' (ملكية) ⇒ التعافي يرجّعه 'pending' (آمن).
    db = make_db(tmp_path)
    jid = add_job(db)
    claimed = db.claim_creation_job("t")
    assert claimed.status == "claimed"
    asyncio.run(creation_recover(_app(db)))
    assert db.get_creation_job(jid).status == "pending"


def test_cancellation_during_start_post_is_unknown(tmp_path):
    db = make_db(tmp_path)

    async def cancel(*a, **k):
        raise asyncio.CancelledError()

    client = CreationClient()
    client.start_conversation = cancel
    worker = make_worker(db, client)
    jid = add_job(db)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(worker._tick())
    assert db.get_creation_job(jid).status == "unknown"


def test_ambiguous_start_error_is_unknown_and_never_retried(tmp_path):
    db = make_db(tmp_path)
    client = CreationClient(start_error=ApiError("timeout", None))
    worker = make_worker(db, client)
    jid = add_job(db)
    asyncio.run(worker._tick())
    assert db.get_creation_job(jid).status == "unknown"
    asyncio.run(worker._tick())
    asyncio.run(worker._tick())
    assert client.start_calls == 1  # غامض ⇒ مفيش إعادة تلقائية


def test_permanent_start_error_is_failed(tmp_path):
    db = make_db(tmp_path)
    client = CreationClient(start_error=ApiError("bad", 422))
    worker = make_worker(db, client)
    jid = add_job(db)
    asyncio.run(worker._tick())
    assert db.get_creation_job(jid).status == "failed"


def test_wait_error_status_is_unknown_and_never_reposted(tmp_path):
    # نفس شكل "ERROR" (ApiError بلا status_code) جاي من wait_for_start ⇒ 'unknown'
    # ومفيش إعادة POST تلقائية (الـ task_id محفوظ، فالتعافي يستطلع بس).
    db = make_db(tmp_path)
    client = CreationClient(wait_error=ApiError("فشل بدء الشات على OpenHands", None))
    worker = make_worker(db, client)
    jid = add_job(db)
    asyncio.run(worker._tick())
    assert db.get_creation_job(jid).status == "unknown"
    assert client.start_calls == 1
    asyncio.run(worker._tick())
    asyncio.run(worker._tick())
    assert client.start_calls == 1  # unknown ⇒ مفيش إعادة POST


# ------------------------------------------------------------ task id + resume
def test_task_id_persisted_and_recovery_polls_without_repost(tmp_path):
    db = make_db(tmp_path)
    jid = add_job(db)
    # محاكاة: الـ POST اتعمل واتسجّل task_id، بس العملية اتقطعت قبل الاستطلاع.
    db.set_creation_starting(jid, "t", task_id="task-1")

    client = CreationClient(conv="conv-9")
    worker = make_worker(db, client)

    app = _app(db)
    asyncio.run(creation_recover(app))
    assert db.get_creation_job(jid).status == "pending"  # للاستطلاع فقط

    asyncio.run(worker._tick())
    assert client.start_calls == 0  # مفيش POST تاني
    assert client.poll_calls == 1
    job = db.get_creation_job(jid)
    assert job.status == "done"
    assert job.conversation_id == "conv-9"


def test_starting_without_task_id_recovers_unknown(tmp_path):
    db = make_db(tmp_path)
    jid = add_job(db)
    db.set_creation_starting(jid, "t")  # اتعمل POST بس الـ task_id مش معروف
    asyncio.run(creation_recover(_app(db)))
    assert db.get_creation_job(jid).status == "unknown"


def test_creation_recovery_is_idempotent(tmp_path):
    db = make_db(tmp_path)
    jid = add_job(db)
    db.set_creation_starting(jid, "t", task_id="task-1")
    asyncio.run(creation_recover(_app(db)))
    asyncio.run(creation_recover(_app(db)))  # تاني مايغيّرش حاجة
    assert db.get_creation_job(jid).status == "pending"


# ------------------------------------------------------------ worker integrity
def test_creation_claim_is_atomic_oldest_first(tmp_path):
    db = make_db(tmp_path)
    a = add_job(db)
    b = add_job(db)
    first = db.claim_creation_job("t1")
    second = db.claim_creation_job("t2")
    third = db.claim_creation_job("t3")
    assert (first.id, first.status) == (a, "claimed")
    assert (second.id, second.status) == (b, "claimed")
    assert third is None


def test_two_creation_workers_cannot_start_same_job_twice(tmp_path):
    db = make_db(tmp_path)
    add_job(db)
    client = CreationClient()
    w1 = make_worker(db, client)
    w2 = make_worker(db, client)

    async def scenario():
        await asyncio.gather(w1._tick(), w2._tick())

    asyncio.run(scenario())
    assert client.start_calls == 1  # الحجز الذرّي: بدء واحد بس


def test_creation_and_outbox_workers_are_independent(tmp_path):
    # البرومت (outbox) وطلب الشات (creation) في جدولين منفصلين: مفيش تنافس.
    db = make_db(tmp_path)
    add_job(db)
    oid = db.add_outbox("c1", 99, "برومت", "t")
    db.claim_outbox("t")  # الـ outbox اتحجز
    job = db.claim_creation_job("t")  # الـ creation لسه يقدر يتحجز
    assert job is not None
    assert db.get_outbox(oid).status == "claimed"


def test_creation_starting_persisted_before_post(tmp_path):
    # نتأكد إن 'starting' بيتسجّل فعلاً قبل POST البدء (حد الغموض).
    db = make_db(tmp_path)
    jid = add_job(db)
    observed = {}

    class ProbeClient(CreationClient):
        async def start_conversation(self, text, repo, branch=None):
            observed["status_at_post"] = db.get_creation_job(jid).status
            return await super().start_conversation(text, repo, branch)

    worker = make_worker(db, ProbeClient())
    asyncio.run(worker._tick())
    assert observed["status_at_post"] == "starting"
