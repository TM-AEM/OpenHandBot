"""NTF-05: اختبارات المُبلّغ العام (اللقطات، الخط الأساس، الانتقالات، sandbox_error،
التعطيل، الازدواج مع المراقب، إعادة المحاولة، الترقيم، الأخطاء المؤقتة)."""
import asyncio
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from telegram.error import RetryAfter, TelegramError

from bot.db import Database
from bot.notifier import MAX_NOTIFY_RETRIES, Notifier, get_status, is_terminal
from bot.watcher import Watcher


class FakeBot:
    def __init__(self, fail=False):
        self.sent = []
        self.chat_ids = []
        self.fail = fail

    async def send_message(self, chat_id=None, text=None, parse_mode=None, **kw):
        if self.fail:
            raise TelegramError("boom")
        self.sent.append(text)
        self.chat_ids.append(chat_id)

    async def send_document(self, chat_id=None, document=None, **kw):
        if self.fail:
            raise TelegramError("boom")
        self.sent.append("DOC")
        self.chat_ids.append(chat_id)


class FakeSearchClient:
    """يخدم `search_conversations` من خريطة صفحات (page_id -> رد)."""

    def __init__(self, pages):
        self._pages = pages
        self.calls = []

    async def search_conversations(self, limit=20, page_id=None):
        self.calls.append(page_id)
        result = self._pages[page_id]
        if isinstance(result, Exception):
            raise result
        return result


def conv(cid, status, sandbox=None, title="عنوان"):
    d = {"id": cid, "title": title, "execution_status": status}
    if sandbox is not None:
        d["sandbox_status"] = sandbox
    return d


def one_page(items):
    return {None: {"items": items, "next_page_id": None}}


def make_notifier(tmp_path, pages, **kw):
    db = Database(str(tmp_path / "t.sqlite3"))
    bot = kw.pop("bot", None) or FakeBot()
    client = FakeSearchClient(pages)
    n = Notifier(client, db, bot, chat_id=1, base_url="https://app.all-hands.dev", **kw)
    return n, db, bot


def seed(db, cid, status, notified=None):
    """لقطة محادثة مرصودة. `notified` = آخر حالة اتعاملنا معاها (افتراضيًا نفس status)."""
    db.upsert_notification_state(cid, status=status, notified_status=status if notified is None else notified, updated_at="t")


# ------------------------------------------------------------- helpers/semantics
def test_get_status_maps_sandbox_error():
    assert get_status(conv("c", "finished")) == "finished"
    assert get_status({"id": "c"}) == "unknown"
    assert get_status(conv("c", "running", sandbox="ERROR")) == "sandbox_error"
    assert get_status(conv("c", "running", sandbox="MISSING")) == "sandbox_error"
    assert get_status(conv("c", "running", sandbox="RUNNING")) == "running"


def test_is_terminal_includes_sandbox_error():
    for s in ("finished", "error", "stuck", "waiting_for_confirmation", "sandbox_error"):
        assert is_terminal(s)
    for s in ("running", "idle", "paused", None, "unknown"):
        assert not is_terminal(s)


# --------------------------------------------------------------------- baseline
def test_baseline_first_run_records_without_notifying(tmp_path):
    n, db, bot = make_notifier(tmp_path, one_page([conv("c1", "finished"), conv("c2", "error")]))
    asyncio.run(n.tick())
    assert bot.sent == []
    assert db.get_notification_state("c1").status == "finished"
    assert db.get_notification_state("c2").status == "error"


def test_first_run_with_sandbox_error_does_not_notify(tmp_path):
    n, db, bot = make_notifier(tmp_path, one_page([conv("c1", "running", sandbox="ERROR")]))
    asyncio.run(n.tick())
    assert bot.sent == []
    assert db.get_notification_state("c1").status == "sandbox_error"


# ------------------------------------------------------------------ transitions
@pytest.mark.parametrize(
    "status,sandbox",
    [
        ("finished", None),
        ("error", None),
        ("stuck", None),
        ("waiting_for_confirmation", None),
        ("running", "ERROR"),  # => sandbox_error
    ],
)
def test_transition_to_each_terminal_status_notifies(tmp_path, status, sandbox):
    n, db, bot = make_notifier(tmp_path, one_page([conv("c1", status, sandbox=sandbox)]))
    seed(db, "c1", "running")
    asyncio.run(n.tick())
    assert len(bot.sent) == 1
    expected = "sandbox_error" if sandbox else status
    assert expected in bot.sent[0]
    assert db.get_notification_state("c1").notified_status == expected


def test_repeated_polling_of_terminal_status_does_not_renotify(tmp_path):
    n, db, bot = make_notifier(tmp_path, one_page([conv("c1", "finished")]))
    seed(db, "c1", "running")
    asyncio.run(n.tick())
    assert len(bot.sent) == 1
    asyncio.run(n.tick())  # نفس الحالة النهائية
    assert len(bot.sent) == 1  # مفيش تكرار


def test_new_conversation_after_baseline_notifies(tmp_path):
    pages = {None: {"items": [conv("c1", "running")], "next_page_id": None}}
    n, db, bot = make_notifier(tmp_path, pages)
    asyncio.run(n.tick())  # خط أساس: c1
    pages[None] = {"items": [conv("c1", "running"), conv("c2", "finished")], "next_page_id": None}
    asyncio.run(n.tick())
    assert len(bot.sent) == 1
    # المحادثة الجديدة (c2) هي اللي اتبعتت، مش القديمة (c1).
    assert "conversations/c2" in bot.sent[0]
    assert "conversations/c1" not in bot.sent[0]


# ------------------------------------------------------------------ disabled mode
def test_disabled_suppresses_delivery_but_records_snapshot(tmp_path):
    n, db, bot = make_notifier(tmp_path, one_page([conv("c1", "finished")]))
    seed(db, "c1", "running")
    db.set_notifications_enabled(False)
    asyncio.run(n.tick())
    assert bot.sent == []
    st = db.get_notification_state("c1")
    assert st.status == "finished"
    # مفيش تراكم: الحالة اتعلمت كـ"متخطّاة".
    assert st.notified_status == "finished"


def test_re_enabling_does_not_send_backlog(tmp_path):
    class MutableClient:
        def __init__(self):
            self.state = "running"

        async def search_conversations(self, limit=20, page_id=None):
            return {"items": [conv("c1", self.state)], "next_page_id": None}

    db = Database(str(tmp_path / "t.sqlite3"))
    bot = FakeBot()
    client = MutableClient()
    n = Notifier(client, db, bot, chat_id=1)
    seed(db, "c1", "running")
    db.set_notifications_enabled(False)

    client.state = "finished"
    asyncio.run(n.tick())  # الانتقال حصل والإشعار معطّل
    st = db.get_notification_state("c1")
    assert st.status == "finished"  # اللقطة اتحدّثت
    assert st.notified_status == "finished"  # واتعلّمت "محسوبة" (سياسة الإسقاط)

    db.set_notifications_enabled(True)
    asyncio.run(n.tick())  # نفس الحالة بعد التفعيل
    assert bot.sent == []  # مفيش إشعار قديم متأخر (الإسقاط)

    # انتقال نهائي *جديد* لاحق لسه بيوصل — يعني الإسقاط مش بيعطّل المُبلّغ نهائيًا.
    client.state = "error"
    asyncio.run(n.tick())
    assert len(bot.sent) == 1
    assert "error" in bot.sent[0]


# ------------------------------------------------------------------- dedupe/watch
def test_watched_conversation_snapshot_recorded_without_delivery(tmp_path):
    n, db, bot = make_notifier(tmp_path, one_page([conv("c1", "finished")]))
    db.add_watched("c1", "عنوان")
    seed(db, "c1", "running")
    asyncio.run(n.tick())
    assert bot.sent == []
    # اللقطة اتعلمت "محسوبة" رغم إن التسليم اتخطّى (ملكية المراقب).
    assert db.get_notification_state("c1").notified_status == "finished"


def test_no_duplicate_after_unwatch(tmp_path):
    n, db, bot = make_notifier(tmp_path, one_page([conv("c1", "finished")]))
    db.add_watched("c1", "عنوان")
    seed(db, "c1", "running")
    asyncio.run(n.tick())  # اتخطّى (متزاوج مع المراقب)
    db.remove_watched("c1")
    asyncio.run(n.tick())  # بعد إزالة المتابعة
    assert bot.sent == []  # مفيش إشعار مكرّر


def test_watcher_notification_then_notifier_does_not_duplicate(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "عنوان")

    class Combined:
        async def search_conversations(self, limit=20, page_id=None):
            return {"items": [conv("c1", "finished")], "next_page_id": None}

        async def get_conversations(self, ids):
            return [conv("c1", "finished")]

        async def get_last_reply(self, cid):
            return "تم"

    bot = FakeBot()
    asyncio.run(Watcher(Combined(), db, bot, chat_id=1).tick())
    assert len(bot.sent) == 1  # المراقب بلّغ
    db.remove_watched("c1")
    asyncio.run(Notifier(Combined(), db, bot, chat_id=1).tick())
    assert len(bot.sent) == 1  # المُبلّغ ما كرّرش


def test_watcher_send_during_notifier_fetch_does_not_duplicate(tmp_path):
    """سباق مؤكّد (NTF-06/07.1): المراقب بيبلّغ *أثناء* مرحلة جلب المُبلّغ.

    المُبلّغ بيقرأ اللقطة قبل الجلب؛ لو اعتمد عليها كان هيعيد نفس الإشعار. القراءة
    الطازجة وقت قرار التسليم بتسدّ النافذة. الاختبار ده متشابك (مش تتابعي).
    """
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "عنوان")
    db.upsert_notification_state("c1", status="running", notified_status="running", updated_at="t")
    sent: list[str] = []

    class Bot:
        async def send_message(self, chat_id=None, text=None, **kw):
            sent.append(text)

        async def send_document(self, chat_id=None, document=None, **kw):
            sent.append("DOC")

    class WatcherClient:
        async def get_conversations(self, ids):
            return [conv("c1", "finished")]

        async def get_last_reply(self, cid):
            return "تم"

    class NotifierClient:
        async def search_conversations(self, limit=20, page_id=None):
            # محاكاة المراقب وهو ببلّغ *أثناء* جلب المُبلّغ (نفس الحلقة، متشابك).
            await Watcher(WatcherClient(), db, Bot(), chat_id=1).tick()
            return {"items": [conv("c1", "finished")], "next_page_id": None}

    asyncio.run(Notifier(NotifierClient(), db, Bot(), chat_id=1).tick())
    assert len(sent) == 1, f"expected 1 notification, got {len(sent)}: {sent}"


# -------------------------------------------------------------------- retries
def test_telegram_failure_keeps_state_and_retries(tmp_path):
    n, db, bot = make_notifier(tmp_path, one_page([conv("c1", "finished")]), bot=FakeBot(fail=True))
    seed(db, "c1", "running")
    asyncio.run(n.tick())
    st = db.get_notification_state("c1")
    assert st.retry_count == 1
    assert st.notified_status == "running"  # مااتعلّمش كـ"محسوبة"

    bot.fail = False
    asyncio.run(n.tick())
    st = db.get_notification_state("c1")
    assert st.notified_status == "finished"
    assert st.retry_count == 0


def test_retry_exhaustion_skips_without_blocking(tmp_path):
    n, db, bot = make_notifier(tmp_path, one_page([conv("c1", "finished")]), bot=FakeBot(fail=True))
    seed(db, "c1", "running")
    db.upsert_notification_state("c1", retry_count=MAX_NOTIFY_RETRIES)
    asyncio.run(n.tick())
    assert bot.sent == []
    st = db.get_notification_state("c1")
    assert st.notified_status == "finished"  # اتخطّى، ومايحجبش باقي المحادثات
    assert st.retry_count == 0


def test_one_failure_does_not_block_other_conversations(tmp_path):
    n, db, bot = make_notifier(
        tmp_path, one_page([conv("c1", "finished"), conv("c2", "error")]), bot=FakeBot(fail=True)
    )
    seed(db, "c1", "running")
    seed(db, "c2", "running")
    asyncio.run(n.tick())
    # الاتنين اتعالجوا (عزل لكل محادثة): عدّاد محاولة لكل واحد.
    assert db.get_notification_state("c1").retry_count == 1
    assert db.get_notification_state("c2").retry_count == 1


# ------------------------------------------------------------------ pagination
def test_follows_pagination_cursors(tmp_path):
    pages = {
        None: {"items": [conv("a", "running")], "next_page_id": "p1"},
        "p1": {"items": [conv("b", "error")], "next_page_id": "p2"},
        "p2": {"items": [conv("c", "stuck")], "next_page_id": None},
    }
    n, db, bot = make_notifier(tmp_path, pages)
    asyncio.run(n.tick())
    assert bot.sent == []  # خط أساس
    assert set(db.list_notification_states()) == {"a", "b", "c"}


def test_repeated_cursor_aborts_without_corrupting_state(tmp_path):
    pages = {
        None: {"items": [conv("a", "running")], "next_page_id": "p1"},
        "p1": {"items": [conv("b", "running")], "next_page_id": "p1"},  # تكرار
    }
    n, db, bot = make_notifier(tmp_path, pages)
    asyncio.run(n.tick())
    assert db.list_notification_states() == {}  # ما اتكتبش أي لقطة


def test_malformed_payload_is_handled(tmp_path):
    for bad in (["not", "a", "dict"], {"items": "nope"}, {"noitems": []}):
        n, db, bot = make_notifier(tmp_path, {None: bad})
        asyncio.run(n.tick())
        assert db.list_notification_states() == {}
        assert bot.sent == []


def test_transient_api_failure_preserves_state(tmp_path):
    from bot.errors import ApiError

    n, db, bot = make_notifier(tmp_path, {None: ApiError("تعذّر الاتصال")})
    seed(db, "c1", "running")
    asyncio.run(n.tick())
    assert db.get_notification_state("c1").status == "running"  # ما اتلمستش
    assert bot.sent == []


def test_page_cap_bounds_unbounded_cursors(tmp_path):
    # مؤشرات فريدة بلا نهاية: لازم نتوقف عند الحد الآمن بدل حلقة لا نهائية.
    counter = {"n": 0}

    class EndlessClient:
        async def search_conversations(self, limit=20, page_id=None):
            counter["n"] += 1
            return {"items": [conv(f"c{counter['n']}", "running")], "next_page_id": f"p{counter['n']}"}

    db = Database(str(tmp_path / "t.sqlite3"))
    n = Notifier(EndlessClient(), db, FakeBot(), chat_id=1)
    asyncio.run(n.tick())
    assert counter["n"] <= 201  # توقف عند الحد الآمن
    assert db.list_notification_states() == {}  # ما اتكتبش لقطة (فشل الدورة)


# ------------------------------------------------------------------- lifecycle
def test_start_stop_single_task(tmp_path):
    n, db, bot = make_notifier(tmp_path, one_page([]))

    async def run():
        n.start()
        task = n._task
        assert task is not None and not task.done()
        await n.stop()
        assert n._task is task

    asyncio.run(run())


# ------------------------------------------------- sandbox-status alignment (NTF-09)
class _TerminalClient:
    def __init__(self, conv):
        self._conv = conv

    async def search_conversations(self, limit=20, page_id=None):
        return {"items": [self._conv], "next_page_id": None}

    async def get_conversations(self, ids):
        return [self._conv]

    async def get_last_reply(self, cid):
        return "تم"

    async def get_reply_since(self, cid, since):
        return "تقرير"


@pytest.mark.parametrize("sandbox", ["ERROR", "MISSING"])
def test_watcher_then_notifier_single_notification_for_sandbox_error(tmp_path, sandbox):
    """عيب مؤكّد (NTF-08/09.1): نفس المحادثة، المراقب والمُبلّغ لازم يستخدموا نفس الحالة.

    execution_status نهائي + sandbox_status=ERROR/MISSING ⇒ الاتنين "sandbox_error"،
    فإشعار واحد بس، واللقطة متسقة (notified_status == status).
    """
    c = {"id": "c1", "title": "عنوان", "execution_status": "finished", "sandbox_status": sandbox}
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "عنوان")
    db.set_last_state("c1", "running")
    db.upsert_notification_state("c1", status="running", notified_status="running", updated_at="t")
    sent = []

    class Bot:
        async def send_message(self, chat_id=None, text=None, **kw):
            sent.append(text)

        async def send_document(self, chat_id=None, document=None, **kw):
            sent.append("DOC")

    client = _TerminalClient(c)
    notifier = Notifier(client, db, Bot(), chat_id=1)
    # نفس ربط التطبيق: المراقب يسجّل عبر المُبلّغ (نقطة التنسيق) قبل إزالة المتابعة.
    asyncio.run(
        Watcher(
            client, db, Bot(), chat_id=1,
            on_owner_delivery=lambda cid, st, now: notifier.record_notification_sent(cid, st, now),
        ).tick()
    )
    assert len(sent) == 1  # المراقب بلّغ مرة واحدة
    asyncio.run(notifier.tick())
    assert len(sent) == 1  # المُبلّغ ما كرّرش نفس الحالة
    st = db.get_notification_state("c1")
    assert st.status == "sandbox_error"
    assert st.notified_status == "sandbox_error"  # لقطة متسقة


# --------------------------- NTF-11: persistence-failure retry in the notifier
class _FailFinalStateDb(Database):
    """بتفشل لما تسجّل حالة نهائية ناجحة (`notified_status == status`)، وبعدها بتنجح.

    كتابات التسليم المكتوم/الخط الأساسي ما بتمرّرش notified_status منفصل، فما بتتأثرش.
    """

    def __init__(self, path, fails):
        self._fails = fails
        self.persist_attempts = 0
        super().__init__(path)

    def upsert_notification_state(self, conversation_id, **kw):
        final = (
            kw.get("notified_status") is not Database._UNCHANGED
            and kw.get("status") is not Database._UNCHANGED
            and kw["notified_status"] == kw["status"]
            and is_terminal(kw["status"])
        )
        if final:
            self.persist_attempts += 1
            if self.persist_attempts <= self._fails:
                raise sqlite3.OperationalError("disk I/O error")
        super().upsert_notification_state(conversation_id, **kw)


def _flaky_notifier(tmp_path, convs, fails):
    db = _FailFinalStateDb(str(tmp_path / "t.sqlite3"), fails=fails)
    for cid in {c["id"] for c in convs}:
        db.upsert_notification_state(cid, status="running", notified_status="running", updated_at="t")
    bot = FakeBot()
    client = FakeSearchClient(one_page(convs))
    n = Notifier(client, db, bot, chat_id=1, base_url="https://app.all-hands.dev")
    return n, db, bot, client


def test_notifier_persist_failure_retries_before_resend(tmp_path):
    """إرسال نجح وتسجيل فشل ⇒ الدورة الجاية تعيد التسجيل قبل أي إرسال (NTF-11.3.4/5)."""
    n, db, bot, _ = _flaky_notifier(tmp_path, [conv("c1", "finished")], fails=1)

    asyncio.run(n.tick())  # إرسال نجح، تسجيل فشل
    assert len(bot.sent) == 1
    assert db.get_notification_state("c1").notified_status == "running"  # ما اتسجّلش

    asyncio.run(n.tick())  # إعادة تسجيل (نجحت) — مافيش إرسال تاني
    assert len(bot.sent) == 1
    assert db.get_notification_state("c1").notified_status == "finished"


def test_notifier_persist_failure_then_status_change_no_blind_duplicate(tmp_path):
    """الحالة اتغيّرت قبل نجاح التسجيل: الأحدث بس بيوصل، بدون تكرار القديم (NTF-11.3.7)."""
    n, db, bot, client = _flaky_notifier(tmp_path, [conv("c1", "finished")], fails=1)

    asyncio.run(n.tick())  # finished اتسلّم، تسجيل فشل
    assert len(bot.sent) == 1

    client._pages[None] = {"items": [conv("c1", "error")], "next_page_id": None}
    asyncio.run(n.tick())  # إعادة تسجيل finished (نجحت) + الانتقال لـ error اتسلّم
    assert len(bot.sent) == 2  # مفيش تكرار لـ finished
    assert db.get_notification_state("c1").notified_status == "error"


def test_notifier_persistent_db_failure_does_not_block_others(tmp_path):
    """فشل قاعدة مستمر لمحادثة ما يمنعش باقي المحادثات (NTF-11.3.6)."""
    n, db, bot, _ = _flaky_notifier(
        tmp_path, [conv("c1", "finished"), conv("c2", "error")], fails=999
    )

    asyncio.run(n.tick())
    assert len(bot.sent) == 2  # الاتنين اتبعتوا رغم فشل التسجيل
    assert db.get_notification_state("c1").notified_status == "running"
    assert db.get_notification_state("c2").notified_status == "running"

    asyncio.run(n.tick())  # لسه فاشل ⇒ مفيش إعادة إرسال أعمى
    assert len(bot.sent) == 2


# ------------------------------- NTF-13.4: pending + later status == prior persisted
def test_notifier_pending_then_terminal_matching_prior_status_is_still_sent(tmp_path):
    """معلّق A، وبعدها حالة نهائية B = الحالة المسجّلة قبل A ⇒ B لسه توصل (مفيش فقد).

    التسلسل: المسجّل قبل A = "error"، والحالة الحالية "running"، في A=finished يبقى انتقال
    جديد ⇒ اتّبعت لكن التسجيل فشل. بعدها الحالة بقت "error" (= المسجّل قبل A). لازم B
    توصّل (انتقال أحدث بالنسبة لـ A)، من غير تكرار لـ A.
    """
    db = _FailFinalStateDb(str(tmp_path / "t.sqlite3"), fails=1)
    db.upsert_notification_state("c1", status="running", notified_status="error", updated_at="t")
    bot = FakeBot()
    client = FakeSearchClient(one_page([conv("c1", "finished")]))
    n = Notifier(client, db, bot, chat_id=1, base_url="https://app.all-hands.dev")

    asyncio.run(n.tick())  # A=finished اتّبعت، التسجيل فشل ⇒ معلّق
    assert len(bot.sent) == 1
    assert db.get_notification_state("c1").notified_status == "error"  # لسه ماتسجّلش

    client._pages[None] = {"items": [conv("c1", "error")], "next_page_id": None}
    asyncio.run(n.tick())  # استرجاع يسجّل finished ثم B=error
    assert len(bot.sent) == 2  # error لسه اتّبعت (مفيش فقد لانتقال)
    assert db.get_notification_state("c1").notified_status == "error"


# =====================================================================
# OHB2-02: أول تشغيل بيعتمد على EXISTS — مفيش تحميل كل اللقطات
# =====================================================================
def test_first_run_uses_exists_query_not_full_list(tmp_path):
    # نثبت إن tick() بيستخدم has_notification_states (EXISTS) مش list_notification_states.
    pages = one_page([conv("a", "running")])
    db = Database(str(tmp_path / "t.sqlite3"))
    bot = FakeBot()
    n = Notifier(FakeSearchClient(pages), db, bot, chat_id=1)
    called = {"exists": 0, "list": 0}
    real_exists = db.has_notification_states
    real_list = db.list_notification_states

    def spy_exists():
        called["exists"] += 1
        return real_exists()

    def spy_list():
        called["list"] += 1
        return real_list()

    db.has_notification_states = spy_exists
    db.list_notification_states = spy_list
    asyncio.run(n.tick())
    assert called["exists"] == 1
    assert called["list"] == 0
    assert bot.sent == []  # خط أساس بلا إشعار
    assert db.get_notification_state("a").notified_status == "running"


def test_second_run_is_not_first_run_after_baseline(tmp_path):
    # بعد تأسيس خط الأساس، الدورة الجاية مش "أول تشغيل" ⇒ انتقال نهائي بيتبعت.
    pages = one_page([conv("a", "running")])
    n, db, bot = make_notifier(tmp_path, pages)
    asyncio.run(n.tick())
    assert bot.sent == []
    n._client._pages[None] = {"items": [conv("a", "finished")], "next_page_id": None}
    asyncio.run(n.tick())
    assert len(bot.sent) == 1


# =====================================================================
# OHB2-08-01: استرجاع التسليم المعلّق الدائم (notifier_pending)
# =====================================================================
class _MarkerFailsDb(Database):
    """فشل كتابة علامة التسليم المعلّق (write-ahead) فقط — لمحاكاة فشل SQLite."""

    def __init__(self, path, *, fail_writes=999):
        self._fail_writes = fail_writes
        self.marker_attempts = 0
        super().__init__(path)

    def set_notifier_pending(self, conversation_id, state, now):
        self.marker_attempts += 1
        if self.marker_attempts <= self._fail_writes:
            raise sqlite3.OperationalError("disk I/O error (marker)")
        super().set_notifier_pending(conversation_id, state, now)


class _FlakyBot(FakeBot):
    """بيفشل أول N إرسال بـ TelegramError (خطأ شبكة مؤقّت)."""

    def __init__(self, fails=1):
        super().__init__()
        self._fails = fails

    async def send_message(self, chat_id=None, text=None, parse_mode=None, **kw):
        if self._fails > 0:
            self._fails -= 1
            raise TelegramError("boom")
        await super().send_message(chat_id=chat_id, text=text, parse_mode=parse_mode, **kw)


class _RetryAfterBot(FakeBot):
    """أول إرسال يرمي RetryAfter، وبعد كده ينجح."""

    def __init__(self, retry_after):
        super().__init__()
        self._retry_after = retry_after
        self.raised = 0

    async def send_message(self, chat_id=None, text=None, parse_mode=None, **kw):
        if self.raised == 0:
            self.raised += 1
            raise RetryAfter(self._retry_after)
        await super().send_message(chat_id=chat_id, text=text, parse_mode=parse_mode, **kw)


def test_notifier_marker_persisted_after_successful_send(tmp_path):
    """OHB2-08-01: بعد إرسال ناجح، العلامة الدائمة بتتكتب ثم تتمسح بالتسجيل الذرّي."""
    n, db, bot = make_notifier(tmp_path, one_page([conv("c1", "finished")]))
    seed(db, "c1", "running")

    asyncio.run(n.tick())

    assert len(bot.sent) == 1
    assert db.get_notification_state("c1").notified_status == "finished"
    assert db.get_notifier_pending("c1") is None  # اتسوّت واتمسحت
    db.close()


def test_notifier_marker_survives_restart_and_recovers_without_resend(tmp_path):
    """العلامة تفضل بعد إعادة تشغيل، والدورة الجاية تسوّيها بدون إرسال تاني."""
    path = str(tmp_path / "t.sqlite3")
    # الحالة اللي بعد الإرسال الناجح بس التسجيل الدائم لسه معلّق (زي ما لو العملية قفلت).
    db = Database(path)
    seed(db, "c1", "running")
    db.set_notifier_pending("c1", "finished", "t")
    db.close()

    db2 = Database(path)  # إعادة تشغيل: نفس القاعدة
    assert db2.get_notifier_pending("c1") == "finished"  # العلامة باقية
    bot = FakeBot()
    n = Notifier(FakeSearchClient(one_page([conv("c1", "finished")])), db2, bot, chat_id=1)

    asyncio.run(n.tick())

    assert bot.sent == []  # مفيش إعادة إرسال أعمى
    assert db2.get_notification_state("c1").notified_status == "finished"  # اتسجّل
    assert db2.get_notifier_pending("c1") is None  # العلامة اتمسحت
    db2.close()


def test_notifier_reconcile_failure_retains_marker_then_recovers(tmp_path):
    """فشل التسجيل ⇒ العلامة تفضل ⇒ الدورة الجاية تكمل بدون إرسال تاني (idempotent)."""
    n, db, bot = make_notifier(tmp_path, one_page([conv("c1", "finished")]))
    seed(db, "c1", "running")
    db.set_notifier_pending("c1", "finished", "t")  # علامة معلّقة (تسجيل فشل سابقًا)
    real = db.reconcile_notifier_pending
    state = {"fail": True}

    def flaky(cid, now):
        if state["fail"]:
            raise sqlite3.OperationalError("disk I/O error (reconcile)")
        return real(cid, now)

    db.reconcile_notifier_pending = flaky

    asyncio.run(n.tick())  # الاسترجاع فشل ⇒ مفيش إرسال، والعلامة باقية
    assert bot.sent == []
    assert db.get_notifier_pending("c1") == "finished"

    state["fail"] = False
    asyncio.run(n.tick())  # الاسترجاع نجح ⇒ اتسجّل واتمسح، بدون إرسال
    assert bot.sent == []
    assert db.get_notification_state("c1").notified_status == "finished"
    assert db.get_notifier_pending("c1") is None
    db.close()


def test_notifier_recovery_idempotent_repeated_ticks(tmp_path):
    """تسوية متكررة لنفس العلامة idempotent: مفيش إرسال ولا أثر إضافي."""
    n, db, bot = make_notifier(tmp_path, one_page([conv("c1", "finished")]))
    seed(db, "c1", "running")
    db.set_notifier_pending("c1", "finished", "t")

    for _ in range(3):
        asyncio.run(n.tick())

    assert bot.sent == []
    assert db.get_notification_state("c1").notified_status == "finished"
    assert db.get_notifier_pending("c1") is None
    db.close()


def test_notifier_marker_write_failure_is_acknowledged_window(tmp_path):
    """لو كتابة العلامة نفسها فشلت: مفيش تسجيل دائم (الحالة تفضل مؤهّلة) — نافذة معترف بيها."""
    db = _MarkerFailsDb(str(tmp_path / "t.sqlite3"))
    seed(db, "c1", "running")
    bot = FakeBot()
    n = Notifier(FakeSearchClient(one_page([conv("c1", "finished")])), db, bot, chat_id=1)

    asyncio.run(n.tick())  # الإرسال نجح، كتابة العلامة فشلت ⇒ ما اتسجّلش
    assert len(bot.sent) == 1
    assert db.get_notification_state("c1").notified_status == "running"  # ما اتسجّلش
    assert db.get_notifier_pending("c1") is None  # مفيش علامة دائمة (النافذة المعلنة)
    db.close()


def test_notifier_watched_owner_marker_does_not_duplicate(tmp_path):
    """OHB2-08-01: محادثة مملوكة للمراقب ما بتتكرّرش — المُبلّغ يسجّل اللقطة بدون إرسال."""
    n, db, bot = make_notifier(tmp_path, one_page([conv("c1", "finished")]))
    seed(db, "c1", "running")
    db.add_watched("c1", "عنوان")
    db.set_last_state("c1", "running")

    asyncio.run(n.tick())

    assert bot.sent == []  # المُبلّغ ما بعتش (ملكية المراقب)
    assert db.get_notifier_pending("c1") is None  # مفيش علامة معلّقة للمُبلّغ
    assert db.get_notification_state("c1").notified_status == "finished"
    db.close()


def test_notifier_retry_budget_still_enforced(tmp_path):
    """ميزانية المحاولات لسه شغالة (ما اتغيّرتش) — بعد الحد مايتحاولش تاني."""
    n, db, bot = make_notifier(tmp_path, one_page([conv("c1", "finished")]), bot=_FlakyBot(fails=999))
    seed(db, "c1", "running")

    for _ in range(MAX_NOTIFY_RETRIES):
        asyncio.run(n.tick())
    assert len(bot.sent) == 0  # كل المحاولات فشلت (إرسال)
    assert db.get_notification_state("c1").retry_count == MAX_NOTIFY_RETRIES

    asyncio.run(n.tick())  # استنفدنا الميزانية ⇒ تخطّي وتعليم (مفيش محاولة إضافية)
    assert db.get_notification_state("c1").notified_status == "finished"
    db.close()


def test_notifier_baseline_first_run_unaffected(tmp_path):
    """السلوك الأساسي (خط الأساس بلا إشعار) لسه زي ما هو."""
    n, db, bot = make_notifier(tmp_path, one_page([conv("c1", "finished")]))
    asyncio.run(n.tick())
    assert bot.sent == []
    assert db.get_notification_state("c1").notified_status == "finished"
    assert db.get_notifier_pending("c1") is None
    db.close()


# =====================================================================
# OHB2-08-02: التعامل مع Telegram RetryAfter (429)
# =====================================================================
def test_retry_after_int_does_not_increment_retry_counter(tmp_path):
    """RetryAfter(int) ⇒ مفيش استهلاك لميزانية المحاولات، والحالة تفضل مؤهّلة."""
    bot = _RetryAfterBot(30)
    n, db, _ = make_notifier(tmp_path, one_page([conv("c1", "finished")]), bot=bot)
    seed(db, "c1", "running")

    asyncio.run(n.tick())

    assert bot.raised == 1
    assert bot.sent == []  # ما اتبعتش (تليجرام رفض بـ 429)
    assert db.get_notification_state("c1").retry_count == 0  # ما اتزوّدش
    assert db.get_notification_state("c1").notified_status == "running"  # لسه مؤهّلة
    db.close()


def test_retry_after_timedelta_normalized(tmp_path):
    """RetryAfter(timedelta) بيتعامل معاه صح (مفيش عدّاد، الحالة مؤهّلة)."""
    from datetime import timedelta

    bot = _RetryAfterBot(timedelta(seconds=12))
    n, db, _ = make_notifier(tmp_path, one_page([conv("c1", "finished")]), bot=bot)
    seed(db, "c1", "running")

    asyncio.run(n.tick())

    assert db.get_notification_state("c1").retry_count == 0
    assert db.get_notification_state("c1").notified_status == "running"
    db.close()


def test_retry_after_skips_further_ticks_until_window(tmp_path):
    """طالما نافذة الانتظار شغالة، الدورات بتتخطّى (مفيش إرسال ولا استهلاك محاولة)."""
    bot = _RetryAfterBot(30)
    n, db, _ = make_notifier(tmp_path, one_page([conv("c1", "finished")]), bot=bot)
    seed(db, "c1", "running")

    asyncio.run(n.tick())  # 429 ⇒ ضبط النافذة
    asyncio.run(n.tick())  # جوّه النافذة ⇒ تخطّي

    assert bot.raised == 1  # محاولة إرسال واحدة بس
    assert db.get_notification_state("c1").retry_count == 0
    assert db.get_notification_state("c1").notified_status == "running"
    db.close()


def test_retry_after_window_expiry_allows_resend(tmp_path):
    """بعد ما الموعد الدائم يعدّي، الإرسال يتعاد ويستقرّ (مافيش عدّاد اتاكل)."""
    bot = _RetryAfterBot(1)
    n, db, _ = make_notifier(tmp_path, one_page([conv("c1", "finished")]), bot=bot)
    seed(db, "c1", "running")

    asyncio.run(n.tick())  # 429 ⇒ موعد دائم في المستقبل
    assert db.get_retry_not_before("c1") is not None
    db.set_retry_not_before("c1", "2000-01-01T00:00:00+00:00")  # موعد منتهي
    asyncio.run(n.tick())  # الإرسال نجح

    assert len(bot.sent) == 1
    assert db.get_notification_state("c1").notified_status == "finished"
    db.close()


# =====================================================================
# OHB2-08-02R: مواعيد إعادة المحاولة الدائمة (restart-safe + لكل محادثة)
# =====================================================================
class _AlwaysRetryAfterBot(FakeBot):
    """كل إرسال يرمي RetryAfter (429 دائم لمحاكاة نافذة تليجرام)."""

    def __init__(self, retry_after):
        super().__init__()
        self._retry_after = retry_after
        self.raised = 0

    async def send_message(self, chat_id=None, text=None, parse_mode=None, **kw):
        self.raised += 1
        raise RetryAfter(self._retry_after)


class _DeadlineFailsDb(Database):
    """فشل كتابة موعد إعادة المحاولة فقط — لمحاكاة فشل SQLite."""

    def __init__(self, path):
        super().__init__(path)

    def set_retry_not_before(self, conversation_id, not_before_iso):
        raise sqlite3.OperationalError("disk I/O error (deadline)")


def test_retry_after_persists_deadline_utc(tmp_path):
    """RetryAfter ⇒ موعد دائم UTC في المستقبل يتسجّل (مش in-memory)."""
    t0 = datetime(2030, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    bot = _RetryAfterBot(30)
    n, db, _ = make_notifier(
        tmp_path, one_page([conv("c1", "finished")]), bot=bot, clock=lambda: t0
    )
    seed(db, "c1", "running")

    asyncio.run(n.tick())

    assert db.get_retry_not_before("c1") == (t0 + timedelta(seconds=30)).isoformat()  # UTC ISO
    db.close()


def test_retry_after_deadline_survives_restart(tmp_path):
    """الموعد الدائم يفضل بعد إعادة التشغيل، والدورة الجديدة ما بتحاولش قبل ما يعدّي."""
    path = str(tmp_path / "t.sqlite3")
    db = Database(path)
    seed(db, "c1", "running")
    bot = _AlwaysRetryAfterBot(300)
    n1 = Notifier(FakeSearchClient(one_page([conv("c1", "finished")])), db, bot, chat_id=1)
    asyncio.run(n1.tick())  # 429 ⇒ موعد دائم
    assert bot.raised == 1
    assert db.get_retry_not_before("c1") is not None

    # إعادة تشغيل: كائن جديد، نفس القاعدة. الموعد لسه في المستقبل ⇒ تخطّي بدون إرسال.
    n2 = Notifier(FakeSearchClient(one_page([conv("c1", "finished")])), db, bot, chat_id=1)
    asyncio.run(n2.tick())
    assert bot.raised == 1  # مفيش محاولة إضافية
    assert db.get_notification_state("c1").retry_count == 0
    db.close()


def test_retry_after_remaining_delay_respected_after_restart(tmp_path):
    """بعد إعادة التشغيل، الموعد يعدّي بالوقت ⇒ الإرسال يتعاد."""
    path = str(tmp_path / "t.sqlite3")
    db = Database(path)
    seed(db, "c1", "running")
    bot = _RetryAfterBot(30)
    n1 = Notifier(FakeSearchClient(one_page([conv("c1", "finished")])), db, bot, chat_id=1)
    asyncio.run(n1.tick())  # 429
    db.set_retry_not_before("c1", "2000-01-01T00:00:00+00:00")  # نحاكي مرور الوقت

    n2 = Notifier(FakeSearchClient(one_page([conv("c1", "finished")])), db, bot, chat_id=1)
    asyncio.run(n2.tick())
    assert len(bot.sent) == 1
    assert db.get_notification_state("c1").notified_status == "finished"
    assert db.get_retry_not_before("c1") is None  # اتمسح
    db.close()


def test_retry_after_one_conversation_does_not_block_another(tmp_path):
    """429 لمحادثة ما بيوقفش محادثة تانية (مواعيد لكل محادثة)."""
    class _OneCid429Bot(FakeBot):
        def __init__(self):
            super().__init__()

        async def send_message(self, chat_id=None, text=None, parse_mode=None, **kw):
            if "c1" in text:
                raise RetryAfter(300)
            await super().send_message(chat_id=chat_id, text=text, parse_mode=parse_mode, **kw)

    pages = one_page([conv("c1", "finished"), conv("c2", "finished")])
    n, db, bot = make_notifier(tmp_path, pages, bot=_OneCid429Bot())
    seed(db, "c1", "running")
    seed(db, "c2", "running")

    asyncio.run(n.tick())

    assert db.get_retry_not_before("c1") is not None  # c1 مؤجّلة
    assert db.get_retry_not_before("c2") is None  # c2 ما اتأثّرتش
    assert db.get_notification_state("c2").notified_status == "finished"
    assert len(bot.sent) == 1  # c2 بس اللي اتبعتت
    db.close()


def test_retry_after_expired_deadline_allows_retry(tmp_path):
    """موعد منتهي ⇒ إعادة محاولة + مسح الموعد."""
    bot = _RetryAfterBot(30)
    n, db, _ = make_notifier(tmp_path, one_page([conv("c1", "finished")]), bot=bot)
    seed(db, "c1", "running")

    asyncio.run(n.tick())  # 429
    db.set_retry_not_before("c1", "2000-01-01T00:00:00+00:00")  # منتهي
    asyncio.run(n.tick())  # الإرسال نجح
    assert len(bot.sent) == 1
    assert db.get_retry_not_before("c1") is None
    db.close()


def test_retry_after_invalid_deadline_handled_safely(tmp_path):
    """موعد تالف ⇒ يتجاهله (fail-safe) ويعيد المحاولة، مش يفقد الإشعار."""
    bot = _RetryAfterBot(30)
    n, db, _ = make_notifier(tmp_path, one_page([conv("c1", "finished")]), bot=bot)
    seed(db, "c1", "running")

    asyncio.run(n.tick())  # 429
    db.set_retry_not_before("c1", "not-a-timestamp")  # تالف
    asyncio.run(n.tick())  # الإرسال نجح
    assert len(bot.sent) == 1
    assert db.get_notification_state("c1").notified_status == "finished"
    db.close()


def test_retry_after_deadline_write_failure_fail_safe(tmp_path):
    """لو كتابة الموعد فشلت: مفيش عدّاد، الحالة تفضل مؤهّلة (fail-safe)."""
    db = _DeadlineFailsDb(str(tmp_path / "t.sqlite3"))
    seed(db, "c1", "running")
    bot = _RetryAfterBot(30)
    n = Notifier(FakeSearchClient(one_page([conv("c1", "finished")])), db, bot, chat_id=1)

    asyncio.run(n.tick())
    assert db.get_notification_state("c1").retry_count == 0
    assert db.get_notification_state("c1").notified_status == "running"
    db.close()


def test_retry_after_deadline_does_not_affect_durable_marker(tmp_path):
    """OHB2-08-01 لسه سليم: الإرسال الناجح يسجّل الحالة رغم وجود موعد قديم منتهي."""
    bot = FakeBot()
    n, db, _ = make_notifier(tmp_path, one_page([conv("c1", "finished")]), bot=bot)
    seed(db, "c1", "running")
    db.set_retry_not_before("c1", "2000-01-01T00:00:00+00:00")

    asyncio.run(n.tick())
    assert len(bot.sent) == 1
    assert db.get_notification_state("c1").notified_status == "finished"
    assert db.get_notifier_pending("c1") is None
    db.close()
