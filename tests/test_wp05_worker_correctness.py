"""OHB2-WP-05 — اختبارات الانحدار للعمال، وإبطال الكاش، وحماية حلقة المؤشّر.

يغطّي المتطلبات المتبقية في `WP-05` فوق ما هو منفَّذ بالفعل (`DEF-007`، `DEF-008`):
- `DEF-012`: فروع الاستطلاع (`wait_for_start`) لازم تحوّل الطلب من `claimed`/`starting`
  إلى `unknown` عند أي استثناء غير `ApiError`، وكمان عند `CancelledError` (مع إعادة الرمي).
- `NEW-DEF-02`: اكتمال إنشاء الشات في الإنتاج (`CreationWorker` -> `_finish_creation`)
  لازم يبطل `list_cache`.
- `NEW-DEF-05`: مؤشّر مكرّر في `collect_conversations` يوقف فورًا بلا `truncated` كاذب.
"""
import asyncio

import pytest

from bot.db import Database
from bot.openhands_client import collect_conversations
from bot.outbox import CREATION_UNKNOWN, CreationWorker, creation_recover


class Bot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id=None, text=None, **kw):
        self.sent.append(text)


def _app(db):
    from types import SimpleNamespace

    return SimpleNamespace(bot_data={"db": db}, bot=Bot())


class CreationClient:
    """عميل fake: تحكّم في `start_conversation`/`wait_for_start`."""

    def __init__(self, task_id="task-1", conv="conv-1", wait_error=None):
        self._task_id = task_id
        self._conv = conv
        self._wait_error = wait_error
        self.start_calls = 0
        self.poll_calls = 0

    async def start_conversation(self, text, repo, branch=None):
        self.start_calls += 1
        return self._task_id

    async def wait_for_start(self, task_id, timeout=180.0, interval=3.0):
        self.poll_calls += 1
        if isinstance(self._wait_error, BaseException):
            raise self._wait_error
        return self._conv


def make_db(tmp_path):
    return Database(str(tmp_path / "t.sqlite3"))


def add_job(db, chat_id=99, repo="o/r", text="برومت"):
    return db.add_creation_job(chat_id, repo, text, "2026-01-01T00:00:00+00:00")


def _resume_pending(db, jid):
    """يحاكي تعافي restart: 'starting' + task_id ⇒ 'pending' (استطلاع فقط)."""
    db.set_creation_starting(jid, "t", task_id="task-1")
    asyncio.run(creation_recover(_app(db)))
    assert db.get_creation_job(jid).status == "pending"


# ------------------------------------------------------------ DEF-012: fresh POST branch
@pytest.mark.parametrize("exc", [RuntimeError("boom"), ValueError("bad json")])
def test_wait_for_start_unexpected_error_marks_unknown(tmp_path, exc):
    """خطأ غير متوقّع في فرع POST البدء ⇒ 'unknown' (مش 'claimed'/'starting' للأبد)."""
    db = make_db(tmp_path)
    client = CreationClient(wait_error=exc)
    bot = Bot()
    worker = CreationWorker(client, db, bot, "https://app.all-hands.dev")
    jid = add_job(db)
    asyncio.run(worker._tick())
    job = db.get_creation_job(jid)
    assert job.status == CREATION_UNKNOWN
    assert client.start_calls == 1
    assert bot.sent  # إشعار الغموض اتبعت
    # مفيش إعادة POST تلقائية (task_id محفوظ ⇒ التعافي يستطلع بس).
    asyncio.run(worker._tick())
    assert client.start_calls == 1


# ------------------------------------------------------------ DEF-012: resumed branch
@pytest.mark.parametrize("exc", [RuntimeError("boom"), KeyError("k")])
def test_resumed_wait_for_start_unexpected_error_marks_unknown(tmp_path, exc):
    """خطأ غير متوقّع في فرع الاستطلاع المستأنَف ⇒ 'unknown' (مش متروك في 'claimed')."""
    db = make_db(tmp_path)
    jid = add_job(db)
    _resume_pending(db, jid)
    client = CreationClient(wait_error=exc)
    bot = Bot()
    worker = CreationWorker(client, db, bot, "https://app.all-hands.dev")
    asyncio.run(worker._tick())
    job = db.get_creation_job(jid)
    assert job.status == CREATION_UNKNOWN
    assert client.start_calls == 0  # مسار الاستطلاع فقط، مفيش POST
    assert bot.sent


def test_resumed_wait_for_start_cancelled_reraises_and_marks_unknown(tmp_path):
    """CancelledError في الفرع المستأنَف ⇒ 'unknown' ثم إعادة الرمي (الإلغاء ينتشر)."""
    db = make_db(tmp_path)
    jid = add_job(db)
    _resume_pending(db, jid)
    client = CreationClient(wait_error=asyncio.CancelledError())
    worker = CreationWorker(client, db, Bot(), "https://app.all-hands.dev")
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(worker._tick())
    assert db.get_creation_job(jid).status == CREATION_UNKNOWN


# ------------------------------------------------------------ NEW-DEF-02: cache invalidation
def test_finish_creation_invokes_on_created_callback(tmp_path):
    """اكتمال إنشاء الشات (الإنتاج) يبطل الكاش عبر `on_created` بعد الـ commit."""
    db = make_db(tmp_path)
    jid = add_job(db)
    invalidated = []
    worker = CreationWorker(
        CreationClient(conv="conv-7"), db, Bot(), "https://app.all-hands.dev",
        on_created=lambda: invalidated.append(True),
    )
    asyncio.run(worker._tick())
    job = db.get_creation_job(jid)
    assert job.status == "done"
    assert job.conversation_id == "conv-7"
    assert invalidated == [True]


def test_on_created_failure_does_not_break_creation(tmp_path):
    """فشل إبطال الكاش (تحسين) مايفشّلش الإكمال."""
    db = make_db(tmp_path)

    def boom():
        raise RuntimeError("cache down")

    worker = CreationWorker(
        CreationClient(), db, Bot(), "https://app.all-hands.dev", on_created=boom
    )
    jid = add_job(db)
    asyncio.run(worker._tick())
    assert db.get_creation_job(jid).status == "done"  # الإكمال نجح رغم فشل الإبطال


# ------------------------------------------------------------ NEW-DEF-05: cursor loop
def test_collect_conversations_halts_on_repeated_cursor():
    class Repeats:
        def __init__(self):
            self.calls = 0

        async def search_conversations(self, limit=100, page_id=None):
            self.calls += 1
            return {"items": [{"id": "c1"}], "next_page_id": "same"}

    c = Repeats()
    out = asyncio.run(collect_conversations(c, max_pages=20))
    assert c.calls == 2                 # توقّف عند أول تكرار (مش لحد 20)
    assert out["truncated"] is False    # مفيش صفحات إضافية حقيقية
    assert [i["id"] for i in out["items"]] == ["c1"]


def test_collect_conversations_distinct_cursors_reach_max_and_truncate():
    class Growing:
        def __init__(self):
            self.calls = 0

        async def search_conversations(self, limit=100, page_id=None):
            self.calls += 1
            return {"items": [{"id": f"c{self.calls}"}], "next_page_id": f"p{self.calls}"}

    c = Growing()
    out = asyncio.run(collect_conversations(c, max_pages=3))
    assert c.calls == 3
    assert out["truncated"] is True
