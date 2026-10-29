import asyncio
import sqlite3

import pytest
from telegram.error import TelegramError

from bot.db import Database
from bot.notifier import Notifier
from bot.watcher import MISSING_LIMIT, Watcher


class FakeClient:
    def __init__(self, by_id, reply=None):
        self._by_id = by_id
        self._reply = reply

    async def get_conversations(self, ids):
        return [self._by_id[i] for i in ids if i in self._by_id]

    async def get_last_reply(self, conversation_id):
        return self._reply


class FakeBot:
    def __init__(self):
        self.sent = []
        self.chat_ids = []

    async def send_message(self, chat_id=None, text=None, parse_mode=None, **kw):
        self.sent.append(text)
        self.chat_ids.append(chat_id)

    async def send_document(self, chat_id=None, document=None, **kw):
        self.sent.append("DOC")
        self.chat_ids.append(chat_id)


def test_finished_triggers_notification_and_removes(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "عنوان")
    client = FakeClient({"c1": {"id": "c1", "title": "عنوان", "execution_status": "finished"}}, reply="تم")
    bot = FakeBot()
    w = Watcher(client, db, bot, chat_id=1)

    asyncio.run(w.tick())

    assert len(bot.sent) == 1
    assert "انتهى الشات" in bot.sent[0]
    assert "تم" in bot.sent[0]
    assert db.list_watched() == []


def test_running_updates_state_without_notify(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1")
    client = FakeClient({"c1": {"id": "c1", "execution_status": "running"}})
    bot = FakeBot()
    w = Watcher(client, db, bot, chat_id=1)

    asyncio.run(w.tick())

    assert bot.sent == []
    assert db.list_watched()[0].last_state == "running"


def test_no_double_notify_when_already_done(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1")
    db.set_last_state("c1", "finished")
    client = FakeClient({"c1": {"id": "c1", "execution_status": "finished"}})
    bot = FakeBot()
    w = Watcher(client, db, bot, chat_id=1)

    asyncio.run(w.tick())

    assert bot.sent == []


def test_waiting_for_confirmation_mentions_site(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1")
    client = FakeClient({"c1": {"id": "c1", "execution_status": "waiting_for_confirmation"}})
    bot = FakeBot()
    w = Watcher(client, db, bot, chat_id=1)

    asyncio.run(w.tick())

    assert "تأكيد" in bot.sent[0]


def test_missing_conversation_is_not_silently_dropped(tmp_path):
    # اتبدّل سلوك الحذف الصامت: غياب شات دورة أو اتنين (عطل مؤقت محتمل) ما يشيلوش المتابعة.
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("gone", "اتمسح")
    client = FakeClient({})  # الشات مش موجود في الـ API
    bot = FakeBot()
    w = Watcher(client, db, bot, chat_id=1)

    asyncio.run(w.tick())
    asyncio.run(w.tick())

    assert bot.sent == []
    assert db.is_watched("gone")


def test_notification_goes_to_chat_that_started_it(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "عنوان", chat_id=555)
    client = FakeClient({"c1": {"id": "c1", "title": "عنوان", "execution_status": "finished"}}, reply="تم")
    bot = FakeBot()
    w = Watcher(client, db, bot, chat_id=1)  # الافتراضي 1، بس الشات بدأ من 555

    asyncio.run(w.tick())

    assert bot.chat_ids == [555]


class FailFirstBot(FakeBot):
    """بيفشل في إرسال أول شات بس (عشان نختبر العزل)."""

    def __init__(self, fail_text):
        super().__init__()
        self._fail_text = fail_text

    async def send_message(self, chat_id=None, text=None, parse_mode=None, **kw):
        if self._fail_text in (text or ""):
            raise TelegramError("boom secret-token-should-not-be-logged")
        await super().send_message(chat_id=chat_id, text=text, parse_mode=parse_mode, **kw)


def test_watcher_one_failure_does_not_block_others(tmp_path, caplog):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "first")
    db.add_watched("c2", "second")
    client = FakeClient(
        {
            "c1": {"id": "c1", "title": "first", "execution_status": "finished"},
            "c2": {"id": "c2", "title": "second", "execution_status": "finished"},
        },
        reply="تم",
    )
    bot = FailFirstBot("first")  # إشعار c1 بيفشل، c2 المفروض ينجح
    w = Watcher(client, db, bot, chat_id=1)

    with caplog.at_level("WARNING"):
        asyncio.run(w.tick())

    # c2 اتبعتله إشعار واتشال من المتابعة.
    assert any("second" in t for t in bot.sent)
    assert not db.is_watched("c2")
    # c1 فشل يبعت وفضل متابَع عشان يتعاود.
    assert db.is_watched("c1")
    # الخطأ اتسجّل مع معرّف الشات ونوع الاستثناء، من غير ما يسرّب نص الاستثناء الحسّاس.
    assert "c1" in caplog.text
    assert "TelegramError" in caplog.text
    assert "secret-token-should-not-be-logged" not in caplog.text


def test_watcher_failure_then_success_retries(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "first")
    client = FakeClient({"c1": {"id": "c1", "title": "first", "execution_status": "finished"}}, reply="تم")
    bot = FailFirstBot("first")
    w = Watcher(client, db, bot, chat_id=1)

    asyncio.run(w.tick())  # يفشل
    assert db.is_watched("c1")

    # دورة تانية بعد ما المشكلة اتحلّت: ينجح ويتشال.
    bot._fail_text = "never"
    asyncio.run(w.tick())
    assert not db.is_watched("c1")


def test_watcher_unexpected_error_is_isolated_per_conversation(tmp_path, caplog):
    # 4B: خطأ برمجي غير متوقع في شات واحد ما يوقفش الدورة؛ باقي الشاتات بتتعالج،
    # والخطأ بيتسجّل بنوعه بس (من غير نص الاستثناء).
    class PickyBot(FakeBot):
        async def send_message(self, chat_id=None, text=None, parse_mode=None, **kw):
            if "first" in (text or ""):
                raise RuntimeError("bug with secret-token-xyz")
            await super().send_message(chat_id=chat_id, text=text, parse_mode=parse_mode, **kw)

    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "first")
    db.add_watched("c2", "second")
    client = FakeClient(
        {
            "c1": {"id": "c1", "title": "first", "execution_status": "finished"},
            "c2": {"id": "c2", "title": "second", "execution_status": "finished"},
        },
        reply="تم",
    )
    bot = PickyBot()

    with caplog.at_level("ERROR"):
        asyncio.run(Watcher(client, db, bot, chat_id=1).tick())

    assert any("second" in t for t in bot.sent)
    assert not db.is_watched("c2")
    assert db.is_watched("c1")  # فشل، فيتعاود
    assert "RuntimeError" in caplog.text and "c1" in caplog.text
    assert "secret-token-xyz" not in caplog.text


# ------------------------------------------------ U01 stale-report prevention
# الـ API مابيرجّعش معرّف يربط البرومت الجديد بالـ run بتاعه، فالحماية "fail closed":
# بنسجّل الحالة الفعلية قبل البرومت، والمراقب ماينبّهش غير على انتقال حقيقي
# (حالة مش منتهية قبل → حالة منتهية بعد).

def test_stale_report_not_delivered_when_new_run_unverified(tmp_path):
    # تقرير قديم موجود، والبرومت الجديد اتقبل بس الـ run الجديد لسه مش متأكَّد إنه بدأ:
    # الحالة المرصودة لسه finished (نفس البيسلاين) → مفيش إشعار، والمراقبة تفضل.
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "شات")
    db.set_last_state("c1", "finished")  # البيسلاين اللي _deliver_outbox بيسجّله
    client = FakeClient({"c1": {"id": "c1", "title": "شات", "execution_status": "finished"}}, reply="تقرير قديم")
    bot = FakeBot()

    asyncio.run(Watcher(client, db, bot, chat_id=1).tick())

    assert bot.sent == []              # ما اتبعتش تقرير قديم
    assert db.is_watched("c1")         # لسه متابَع
    assert db.list_watched()[0].last_state == "finished"


def test_confirmed_new_run_completes_and_delivers_own_report(tmp_path):
    # البرومت الجديد اتأكد إنه بدأ (الحالة بقت running)، وبعدين خلص → يتسلّم تقريره.
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "شات")
    db.set_last_state("c1", "finished")  # البيسلاين (منتهي قبل البرومت)
    bot = FakeBot()

    # 1) الـ run الجديد بدأ: الحالة بقت running → مفيش إشعار، بس بنسجّل الحالة.
    running = FakeClient({"c1": {"id": "c1", "execution_status": "running"}})
    asyncio.run(Watcher(running, db, bot, chat_id=1).tick())
    assert bot.sent == []
    assert db.list_watched()[0].last_state == "running"

    # 2) الـ run الجديد خلص: الانتقال running → finished حقيقي → يتسلّم تقريره ويتشال.
    finished = FakeClient({"c1": {"id": "c1", "title": "شات", "execution_status": "finished"}}, reply="تقرير جديد")
    asyncio.run(Watcher(finished, db, bot, chat_id=1).tick())
    assert len(bot.sent) == 1
    assert "تقرير جديد" in bot.sent[0]
    assert "تقرير قديم" not in bot.sent[0]
    assert not db.is_watched("c1")


def test_stale_completion_event_cannot_complete_new_prompt_watch(tmp_path):
    # حتى لو الـ API لسه بيرجّع حدث/تقرير الانتهاء القديم وحالة finished والحالة
    # المسجَّلة finished، مفيش انتقال → مفيش إشعار لانهائي، والمراقبة تفضل (fail closed).
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "شات")
    db.set_last_state("c1", "finished")
    client = FakeClient({"c1": {"id": "c1", "execution_status": "finished"}}, reply="تقرير قديم")
    bot = FakeBot()

    for _ in range(3):
        asyncio.run(Watcher(client, db, bot, chat_id=1).tick())

    assert bot.sent == []
    assert db.is_watched("c1")


def test_watcher_still_isolates_and_retries_with_new_baseline(tmp_path, caplog):
    # تأكيد إن سلوك TASK 04A-2 لسه سليم مع البيسلاين الجديد: فشل إشعار شات
    # مايوقفش باقي الشاتات، والفاشل يفضل متابَع.
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "first")
    db.add_watched("c2", "second")
    for cid in ("c1", "c2"):
        db.set_last_state(cid, "running")  # انتقال حقيقي: running → finished
    client = FakeClient(
        {
            "c1": {"id": "c1", "title": "first", "execution_status": "finished"},
            "c2": {"id": "c2", "title": "second", "execution_status": "finished"},
        },
        reply="تم",
    )
    bot = FailFirstBot("first")

    with caplog.at_level("WARNING"):
        asyncio.run(Watcher(client, db, bot, chat_id=1).tick())

    assert any("second" in t for t in bot.sent)
    assert not db.is_watched("c2")
    assert db.is_watched("c1")
    assert "TelegramError" in caplog.text


# ------------------------------------ TASK 54: bounded persistent notify retries
from bot.watcher import MAX_WATCH_NOTIFY_RETRIES


def _finished_client():
    return FakeClient({"c1": {"id": "c1", "title": "first", "execution_status": "finished"}}, reply="تم")


def test_legacy_notify_failure_increments_persistent_counter(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "first")
    w = Watcher(_finished_client(), db, FailFirstBot("first"), chat_id=1)

    asyncio.run(w.tick())

    assert db.is_watched("c1")  # لسه بيتعاود
    assert db.list_watched()[0].retry_count == 1  # العدّاد اتخزّن


def test_legacy_notify_retries_stop_at_limit_and_remove(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "first")
    w = Watcher(_finished_client(), db, FailFirstBot("first"), chat_id=1)

    for i in range(1, MAX_WATCH_NOTIFY_RETRIES):
        asyncio.run(w.tick())
        assert db.is_watched("c1")  # تحت الحد ⇒ لسه متابَع
        assert db.list_watched()[0].retry_count == i

    asyncio.run(w.tick())  # المحاولة رقم الحد
    assert not db.is_watched("c1")  # استسلمنا ومسحنا المتابعة


def test_legacy_no_repeat_after_exhaustion(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "first")
    bot = FailFirstBot("first")
    w = Watcher(_finished_client(), db, bot, chat_id=1)

    for _ in range(MAX_WATCH_NOTIFY_RETRIES + 5):
        asyncio.run(w.tick())

    # بعد الاستنفاد مفيش أي محاولة إضافية (السجل اتشال).
    assert db.list_watched() == []
    assert len(bot.sent) == 0  # كل المحاولات فشلت فمفيش رسالة ناجحة


def test_legacy_retry_count_survives_restart(tmp_path):
    path = str(tmp_path / "t.sqlite3")
    db = Database(path)
    db.add_watched("c1", "first")
    asyncio.run(Watcher(_finished_client(), db, FailFirstBot("first"), chat_id=1).tick())
    assert db.list_watched()[0].retry_count == 1
    db.close()

    # "إعادة تشغيل": قاعدة جديدة من نفس الملف + Watcher جديد.
    db2 = Database(path)
    asyncio.run(Watcher(_finished_client(), db2, FailFirstBot("first"), chat_id=1).tick())
    assert db2.list_watched()[0].retry_count == 2  # اتراكم، مارجعش صفر
    db2.close()


def test_legacy_new_lifecycle_resets_retry_budget(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "first")
    fail_bot = FailFirstBot("first")

    # فشل إشعار الانتهاء 3 مرات (تحت الحد).
    for _ in range(3):
        asyncio.run(Watcher(_finished_client(), db, fail_bot, chat_id=1).tick())
    assert db.list_watched()[0].retry_count == 3

    # الشات رجع لحالة غير منتهية (دورة إشعار جديدة) ⇒ العدّاد يتصفّر.
    running = FakeClient({"c1": {"id": "c1", "execution_status": "running"}})
    asyncio.run(Watcher(running, db, fail_bot, chat_id=1).tick())
    w = db.list_watched()[0]
    assert w.last_state == "running"
    assert w.retry_count == 0


def test_legacy_successful_notify_unchanged(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "first")
    bot = FakeBot()
    asyncio.run(Watcher(_finished_client(), db, bot, chat_id=1).tick())
    assert len(bot.sent) == 1  # إشعار ناجح زي قبل
    assert not db.is_watched("c1")  # اتشال



# --------------------------------------------------- on_owner_delivery hook (NTF-09)
class FailBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id=None, text=None, parse_mode=None, **kw):
        raise TelegramError("boom")

    async def send_document(self, chat_id=None, document=None, **kw):
        raise TelegramError("boom")


def test_owner_delivery_hook_fires_once_on_success(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "عنوان")
    calls = []
    w = Watcher(
        _finished_client(), db, FakeBot(), chat_id=1,
        on_owner_delivery=lambda cid, status, now: (
            calls.append((cid, status)), db.record_notification_sent(cid, status, now)
        ),
    )
    asyncio.run(w.tick())
    assert calls == [("c1", "finished")]  # مرة واحدة، بالحالة المعيارية
    assert db.get_notification_state("c1").notified_status == "finished"


def test_owner_delivery_hook_not_called_on_failure(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "عنوان")
    calls = []
    w = Watcher(
        _finished_client(), db, FailBot(), chat_id=1,
        on_owner_delivery=lambda cid, status, now: calls.append((cid, status)),
    )
    asyncio.run(w.tick())
    assert calls == []  # مفيش تأكيد تليجرام ⇒ مفيش تسجيل


def test_owner_delivery_hook_does_not_block_later_transition(tmp_path):
    """التسجيل بعد التسليم ما يمنعش انتقال نهائي *جديد* لاحق (حالة مختلفة)."""
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "عنوان")
    # المراقب يبلّغ "finished" ويسجّل عبر الـ hook.
    asyncio.run(
        Watcher(_finished_client(), db, FakeBot(), chat_id=1,
                on_owner_delivery=lambda c, s, n: db.record_notification_sent(c, s, n)).tick()
    )
    assert db.get_notification_state("c1").notified_status == "finished"
    assert not db.is_watched("c1")

    from bot.notifier import Notifier

    class ErrorClient:
        async def search_conversations(self, limit=20, page_id=None):
            return {"items": [{"id": "c1", "execution_status": "error"}], "next_page_id": None}

    bot = FakeBot()
    asyncio.run(Notifier(ErrorClient(), db, bot, chat_id=1).tick())
    # انتقال جديد لحالة نهائية مختلفة (error) لسه بيوصل — التسجيل ما كتمش المُبلّغ.
    assert len(bot.sent) == 1
    assert "error" in bot.sent[0]


# ------------------------------- NTF-11: persistence-failure retry (fault injection)
class _FlakyPersistDb(Database):
    """قاعدة بتفشل في تسجيل التسليم أول `fails` محاولة، وبعدها بتنجح (حقن فولت حتمي)."""

    def __init__(self, path, fails):
        self._fails = fails
        self.persist_attempts = 0
        super().__init__(path)

    def record_notification_sent(self, conversation_id, status, now, *, _commit=True):
        self.persist_attempts += 1
        if self.persist_attempts <= self._fails:
            raise sqlite3.OperationalError("disk I/O error")
        super().record_notification_sent(conversation_id, status, now, _commit=_commit)


def _seed_watch(db, cid="c1", title="عنوان", last_state="running"):
    db.add_watched(cid, title)
    db.set_last_state(cid, last_state)
    db.upsert_notification_state(
        cid, status=last_state, notified_status=last_state, updated_at="t"
    )


def test_watcher_persist_failure_does_not_remove_watched(tmp_path):
    """تليجرام قبِل بس التسجيل فشل ⇒ ما يتشالشش كإنه اتسجّل (NTF-11.3.1)."""
    db = _FlakyPersistDb(str(tmp_path / "t.sqlite3"), fails=99)
    _seed_watch(db)
    bot = FakeBot()
    w = Watcher(_finished_client(), db, bot, chat_id=1)

    asyncio.run(w.tick())

    assert len(bot.sent) == 1  # الإشعار نفسه اتبعت مرة واحدة
    assert db.is_watched("c1")  # لسه متابَع (ما اتشالشش)
    assert db.get_notification_state("c1").notified_status == "running"  # التسجيل ما نجحش
    assert db.persist_attempts == 1  # محاولة تسجيل واحدة (فشلت)


def test_watcher_persist_retry_succeeds_then_removes_without_resend(tmp_path):
    """إعادة التسجيل تنجح في الدورة الجاية ⇒ إزالة عادية بدون إعادة إرسال (NTF-11.3.2)."""
    db = _FlakyPersistDb(str(tmp_path / "t.sqlite3"), fails=1)
    _seed_watch(db)
    bot = FakeBot()
    w = Watcher(_finished_client(), db, bot, chat_id=1)

    asyncio.run(w.tick())  # إرسال + فشل تسجيل
    assert len(bot.sent) == 1
    assert db.is_watched("c1")

    asyncio.run(w.tick())  # إعادة تسجيل ناجحة ⇒ إزالة
    assert len(bot.sent) == 1  # مفيش إعادة إرسال
    assert not db.is_watched("c1")
    assert db.get_notification_state("c1").notified_status == "finished"


def test_watcher_send_failure_records_nothing(tmp_path):
    """فشل إرسال تليجرام ⇒ مفيش تسجيل تسليم ناجح (NTF-11.3.3)."""
    db = Database(str(tmp_path / "t.sqlite3"))
    _seed_watch(db)
    w = Watcher(_finished_client(), db, FailBot(), chat_id=1)

    asyncio.run(w.tick())

    assert db.is_watched("c1")  # لسه متابَع (إعادة محاولة)
    assert db.get_notification_state("c1").notified_status == "running"  # ما اتسجّلش


# --------------------------- NTF-13: durable pending-delivery marker (H1/M2/H2)
def _stateful_client(status="finished"):
    """عميل بيقدر نغيّر حالته بين الدورات (لمحاكاة انتقال A→B)."""
    box = {"status": status}

    class C:
        async def get_conversations(self, ids):
            return [{"id": "c1", "title": "t", "execution_status": box["status"]}]

        async def get_last_reply(self, cid):
            return "تم"

    return box, C()


def test_unwatch_while_pending_completes_record_no_notifier_duplicate(tmp_path):
    """NTF-13.1 (Case 10): إزالة متابعة خارجية أثناء تسليم معلّق ⇒ مايتسيبش حالة قديمة.

    التسلسل: المراقب بلّغ finished (اتقبل) لكن التسجيل فشل ⇒ علامة معلّقة. بعدها
    إزالة متابعة خارجية ⇒ لازم التسجيل يتكمّل، والمُبلّغ مايبعتش نفس الحالة تاني.
    """
    from bot.notifier import Notifier

    db = _FlakyPersistDb(str(tmp_path / "t.sqlite3"), fails=1)
    _seed_watch(db)
    wbot = FakeBot()
    w = Watcher(_finished_client(), db, wbot, chat_id=1)

    asyncio.run(w.tick())  # إرسال + فشل تسجيل + علامة معلّقة
    assert len(wbot.sent) == 1
    assert db.is_watched("c1")
    assert db.list_watched()[0].pending_delivery_state == "finished"  # العلامة الدائمة
    assert db.get_notification_state("c1").notified_status == "running"  # لسه ماتسجّلش

    db.remove_watched("c1")  # إزالة متابعة خارجية أثناء التعليق
    assert not db.is_watched("c1")
    assert db.get_notification_state("c1").notified_status == "finished"  # اتكمّل عند الإزالة

    nbot = FakeBot()

    class _SearchClient:
        async def search_conversations(self, limit=20, page_id=None):
            return {
                "items": [{"id": "c1", "title": "t", "execution_status": "finished"}],
                "next_page_id": None,
            }

    asyncio.run(Notifier(_SearchClient(), db, nbot, chat_id=1).tick())
    assert nbot.sent == []  # المُبلّغ ما كرّرش الإشعار (مفيش ازدواج)
    assert db.get_notification_state("c1").notified_status == "finished"


def test_rewatch_after_pending_clears_marker(tmp_path):
    """NTF-13/15: إعادة المتابعة بعد تسليم معلّق ⇒ العلامة القديمة تتصفّر.

    NTF-15: `remove_watched` بقى ذرّي — لو التسجيل فشل مايحذفش؛ هنا التسجيل بينجح
    (fails=1) فالحذف يكمل، وبعدها إعادة المتابعة تمسح العلامة.
    """
    db = _FlakyPersistDb(str(tmp_path / "t.sqlite3"), fails=1)
    _seed_watch(db)
    asyncio.run(Watcher(_finished_client(), db, FakeBot(), chat_id=1).tick())
    assert db.list_watched()[0].pending_delivery_state == "finished"

    db.remove_watched("c1")  # ذرّي: يسجّل finished ثم يحذف
    assert not db.is_watched("c1")
    db.add_watched("c1", "t")  # إعادة متابعة
    assert db.list_watched()[0].pending_delivery_state is None


def test_pending_retry_records_delivered_status_then_newer_transition(tmp_path):
    """NTF-13.2 (M2): A معلّقة، الشات بيتحوّل B ⇒ يتسجّل A (اللي اتّبعت) ثم B (الجديد)."""
    db = _FlakyPersistDb(str(tmp_path / "t.sqlite3"), fails=1)
    _seed_watch(db)
    box, client = _stateful_client("finished")
    bot = FakeBot()
    w = Watcher(client, db, bot, chat_id=1)

    asyncio.run(w.tick())  # A=finished اتّبعت، تسجيل فشل
    assert len(bot.sent) == 1
    assert db.is_watched("c1")

    box["status"] = "error"  # انتقال أحدث قبل نجاح التسجيل
    asyncio.run(w.tick())  # استرجاع يسجّل A=finished ثم B=error
    assert len(bot.sent) == 2  # finished ثم error، بدون تكرار
    assert "منتهي" in bot.sent[0] or "انتهى" in bot.sent[0]
    assert db.get_notification_state("c1").notified_status == "error"
    assert not db.is_watched("c1")  # اتشال بعد B


def test_pending_retry_failure_keeps_marker_and_no_blind_resend(tmp_path):
    """NTF-13.2: فشل التسجيل مرتين ⇒ العلامة تفضل، ومافيش إعادة إرسال أعمى."""
    db = _FlakyPersistDb(str(tmp_path / "t.sqlite3"), fails=2)
    _seed_watch(db)
    box, client = _stateful_client("finished")
    bot = FakeBot()
    w = Watcher(client, db, bot, chat_id=1)

    asyncio.run(w.tick())  # إرسال + فشل تسجيل (المحاولة 1)
    assert len(bot.sent) == 1

    box["status"] = "error"
    asyncio.run(w.tick())  # استرجاع يفشل (المحاولة 2) ⇒ لسه معلّق، مفيش إرسال تاني
    assert len(bot.sent) == 1
    assert db.is_watched("c1")
    assert db.list_watched()[0].pending_delivery_state == "finished"


def test_restart_recovers_pending_and_records_without_resend(tmp_path):
    """NTF-13.3 (H2): بعد إعادة التشغيل، العلامة الدائمة تخلّي التسجيل يتكمّل بلا إعادة إرسال."""
    path = str(tmp_path / "t.sqlite3")
    db = _FlakyPersistDb(path, fails=99)
    _seed_watch(db)
    bot1 = FakeBot()
    asyncio.run(Watcher(_finished_client(), db, bot1, chat_id=1).tick())  # إرسال + فشل تسجيل
    assert len(bot1.sent) == 1
    assert db.list_watched()[0].pending_delivery_state == "finished"

    db2 = Database(path)  # إعادة تشغيل: مفيش حالة in-memory، بس العلامة على القرص
    bot2 = FakeBot()
    asyncio.run(Watcher(_finished_client(), db2, bot2, chat_id=1).tick())
    assert bot2.sent == []  # مفيش إعادة إرسال (العلامة استرجعت التسجيل)
    assert not db2.is_watched("c1")
    assert db2.get_notification_state("c1").notified_status == "finished"


# ================================= NTF-15: H-1 / H-2 / M-1 =================================
def _two_client(states):
    class C:
        async def get_conversations(self, ids):
            return [
                {"id": cid, "title": "t", "execution_status": st}
                for cid, st in states.items() if cid in ids
            ]

        async def get_last_reply(self, cid):
            return "r"

    return C()


class _MarkerFailsDb(Database):
    """set_pending_delivery يفشل أول `fails` محاولة ثم ينجح (حقن فولت على حدود المعاملة)."""

    def __init__(self, path, fails):
        self._fails = fails
        self.marker_attempts = 0
        super().__init__(path)

    def set_pending_delivery(self, conversation_id, state):
        self.marker_attempts += 1
        if self.marker_attempts <= self._fails:
            raise sqlite3.OperationalError("disk I/O error (marker)")
        super().set_pending_delivery(conversation_id, state)


def test_marker_write_failure_recovers_without_resend(tmp_path):
    """NTF-15.2 (H-1): فشل كتابة العلامة بعد قبول تيليجرام ⇒ الدورة الجاية تعيد الكتابة،
    مفيش إعادة إرسال."""
    db = _MarkerFailsDb(str(tmp_path / "t.sqlite3"), fails=1)
    _seed_watch(db)
    bot = FakeBot()
    w = Watcher(_finished_client(), db, bot, chat_id=1)

    asyncio.run(w.tick())  # إرسال + فشل كتابة العلامة
    assert len(bot.sent) == 1
    assert db.is_watched("c1")
    assert db.list_watched()[0].pending_delivery_state is None  # العلامة ما اتكتبتش
    assert "c1" in w._marker_pending  # تلميح in-memory بالحالة اللي اتّبعت
    assert w._marker_pending["c1"][0] == "finished"

    asyncio.run(w.tick())  # إعادة كتابة العلامة + التسجيل، بدون إرسال تاني
    assert len(bot.sent) == 1  # مفيش إعادة إرسال
    assert not db.is_watched("c1")
    assert db.get_notification_state("c1").notified_status == "finished"
    assert w._marker_pending == {}


def test_repeated_marker_write_failures_then_recovery(tmp_path):
    """NTF-15.2: فشل كتابة العلامة عدة مرات ⇒ مفيش إعادة إرسال، وبعد ما SQLite يشتغل يتعافى."""
    db = _MarkerFailsDb(str(tmp_path / "t.sqlite3"), fails=3)
    _seed_watch(db)
    bot = FakeBot()
    w = Watcher(_finished_client(), db, bot, chat_id=1)

    asyncio.run(w.tick())  # إرسال + فشل علامة (1)
    assert len(bot.sent) == 1
    asyncio.run(w.tick())  # فشل علامة (2)
    asyncio.run(w.tick())  # فشل علامة (3)
    assert len(bot.sent) == 1  # مفيش إعادة إرسال أعمى
    assert db.is_watched("c1")

    asyncio.run(w.tick())  # SQLite اشتغل ⇒ العلامة تتكتب والتسجيل يتكمّل
    assert len(bot.sent) == 1
    assert not db.is_watched("c1")
    assert db.get_notification_state("c1").notified_status == "finished"


def test_remove_watched_atomic_failure_prevents_notifier_duplicate(tmp_path):
    """NTF-15.1 (H-2): فشل تسجيل التسليم جوه remove_watched ⇒ الصف مايتحذفش والمُبلّغ
    مايكرّرش."""
    from bot.notifier import Notifier

    class _RecordFails(Database):
        def record_notification_sent(self, cid, status, now, *, _commit=True):
            raise sqlite3.OperationalError("disk I/O error (record)")

    db = _RecordFails(str(tmp_path / "t.sqlite3"))
    _seed_watch(db)
    db.set_pending_delivery("c1", "finished")  # تسليم اتّبعت بس اتسجّل معلّق
    with pytest.raises(sqlite3.OperationalError):
        db.remove_watched("c1")
    assert db.is_watched("c1")  # الذرّية: الحذف اترجع
    assert db.get_notification_state("c1").notified_status == "running"

    nbot = FakeBot()

    class _SearchClient:
        async def search_conversations(self, limit=20, page_id=None):
            return {
                "items": [{"id": "c1", "title": "t", "execution_status": "finished"}],
                "next_page_id": None,
            }

    asyncio.run(Notifier(_SearchClient(), db, nbot, chat_id=1).tick())
    assert nbot.sent == []  # المُبلّغ بيسكت لأن الشات لسه متابَع ⇒ مفيش ازدواج


class _RecoveryFailsDb(Database):
    """record_notification_sent يفشل لمحادثة محددة بس (لعزل الأخطاء لكل شات)."""

    def __init__(self, path, bad_cid):
        self._bad = bad_cid
        super().__init__(path)

    def record_notification_sent(self, cid, status, now, *, _commit=True):
        if cid == self._bad:
            raise sqlite3.OperationalError("disk I/O error (record)")
        super().record_notification_sent(cid, status, now, _commit=_commit)


def test_recovery_failure_isolated_per_conversation(tmp_path):
    """NTF-15.3 (M-1): فشل استرجاع محادثة A ما يمنعش معالجة B في نفس الدورة."""
    db = _RecoveryFailsDb(str(tmp_path / "t.sqlite3"), bad_cid="c1")
    _seed_watch(db, cid="c1")
    _seed_watch(db, cid="c2")
    db.set_pending_delivery("c1", "finished")  # استرجاع c1 هيفشل
    bot = FakeBot()
    w = Watcher(_two_client({"c1": "finished", "c2": "finished"}), db, bot, chat_id=1)

    asyncio.run(w.tick())  # لازم مايرميش؛ c2 تتعالج عادي

    # c1 لسه متابَع بعلامته (قابل للاسترجاع)، وما اتبعتش
    c1 = db.get_watched("c1")
    assert c1 is not None and c1.pending_delivery_state == "finished"
    # c2 اتعالجت (اتشالت) واتسجّلت
    assert not db.is_watched("c2")
    assert db.get_notification_state("c2").notified_status == "finished"
    assert len(bot.sent) == 1  # إشعار c2 بس


# ================================= NTF-17: R-1 (marker-write failure + unwatch) ============
class _MarkerFailsThenOk(Database):
    """set_pending_delivery يفشل أول مرة ثم ينجح (لمحاكاة عودة SQLite)."""

    def __init__(self, path):
        self.n = 0
        super().__init__(path)

    def set_pending_delivery(self, conversation_id, state):
        self.n += 1
        if self.n == 1:
            raise sqlite3.OperationalError("disk I/O error (marker)")
        super().set_pending_delivery(conversation_id, state)


class _MarkerAlwaysFails(Database):
    """set_pending_delivery يفشل دايمًا (NTF-20: fail closed عند بدء دورة جديدة)."""

    def set_pending_delivery(self, conversation_id, state):
        raise sqlite3.OperationalError("disk I/O error (marker permanent)")


class _SearchFinishedClient:
    async def search_conversations(self, limit=20, page_id=None):
        return {
            "items": [{"id": "c1", "title": "t", "execution_status": "finished"}],
            "next_page_id": None,
        }


def _seed_full(db, cid="c1"):
    db.add_watched(cid, "t")
    db.set_last_state(cid, "running")
    db.upsert_notification_state(cid, status="running", notified_status="running", updated_at="t")


def test_r1_marker_write_failure_then_external_unwatch_no_notifier_duplicate(tmp_path):
    """NTF-17 R-1: الإرسال اتقبل + فشل كتابة العلامة، ثم إزالة متابعة خارجية عبر المراقب
    ⇒ المُبلّغ مايبعتش نفس الإشعار تاني."""
    from bot.notifier import Notifier

    db = _MarkerFailsThenOk(str(tmp_path / "t.sqlite3"))
    _seed_full(db)
    bot = FakeBot()
    w = Watcher(_finished_client(), db, bot, chat_id=1)
    asyncio.run(w.tick())  # إرسال + فشل كتابة العلامة
    assert len(bot.sent) == 1
    assert "c1" in w._marker_pending  # التلميح شايل الحالة اللي اتّبعت

    w.unwatch("c1")  # إزالة عبر المراقب: تكمّل التسجيل ذرّيًا
    assert not db.is_watched("c1")
    assert db.get_notification_state("c1").notified_status == "finished"
    assert "c1" not in w._marker_pending

    nbot = FakeBot()
    asyncio.run(Notifier(_SearchFinishedClient(), db, nbot, chat_id=1).tick())
    assert nbot.sent == []  # مفيش إرسال مكرّر


def test_r1_unwatch_persistence_failure_preserves_safe_state(tmp_path):
    """NTF-17: فشل التسجيل أثناء الإزالة ⇒ الصف والتلميح بيفضلوا، والمُبلّغ لسه بيسكت."""
    from bot.notifier import Notifier

    class _RecordFails(Database):
        def record_notification_sent(self, cid, status, now, *, _commit=True):
            raise sqlite3.OperationalError("disk I/O error (record)")

    db = _RecordFails(str(tmp_path / "t.sqlite3"))
    _seed_full(db)
    w = Watcher(_finished_client(), db, FakeBot(), chat_id=1)
    w._marker_pending["c1"] = ("finished", db.get_watched("c1").watch_seq)
    with pytest.raises(sqlite3.OperationalError):
        w.unwatch("c1")
    assert db.is_watched("c1")  # الحذف اترجع
    assert "c1" in w._marker_pending  # التلميح بيفضل (retry آمن)
    assert db.get_notification_state("c1").notified_status == "running"
    nbot = FakeBot()
    asyncio.run(Notifier(_SearchFinishedClient(), db, nbot, chat_id=1).tick())
    assert nbot.sent == []  # لسه متابَع ⇒ المُبلّغ بيسكت


def test_r1_stale_hint_does_not_affect_rewatched_conversation(tmp_path):
    """NTF-17/19: تلميح قديم (معرّف دورة مختلف) ما يأثّرش على متابعة اتعملت من جديد."""
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "t")
    db.set_last_state("c1", "running")
    w = Watcher(_finished_client(), db, FakeBot(), chat_id=1)
    w._marker_pending["c1"] = ("finished", "stale-watch-id")  # تلميح بمعرّف مختلف

    db.remove_watched("c1")  # إزالة خارجية مباشرة (التلميح القديم لسه في الذاكرة)
    db.add_watched("c1", "t")  # إعادة متابعة ⇒ معرّف جديد
    w.unwatch("c1")  # التلميح القديم لازم يتجاهله
    assert not db.is_watched("c1")
    assert db.get_notification_state("c1") is None or \
        db.get_notification_state("c1").notified_status in (None, "running")


def test_r1_hint_recovery_retry_completes(tmp_path):
    """NTF-17: بعد فشل كتابة العلامة، لسه ينفع نتعافى عبر الدورة الجاية (retry ناجح)."""
    db = _MarkerFailsThenOk(str(tmp_path / "t.sqlite3"))
    _seed_full(db)
    bot = FakeBot()
    w = Watcher(_finished_client(), db, bot, chat_id=1)
    asyncio.run(w.tick())  # فشل كتابة العلامة
    assert "c1" in w._marker_pending
    asyncio.run(w.tick())  # إعادة كتابة العلامة + التسجيل بدون إرسال
    assert len(bot.sent) == 1
    assert not db.is_watched("c1")
    assert db.get_notification_state("c1").notified_status == "finished"
    assert w._marker_pending == {}


# ================================= NTF-19: re-watch semantics =============================
def test_rewatch_duplicate_callback_preserves_pending_delivery(tmp_path):
    """NTF-19: إعادة نداء مكرّرة (new_lifecycle=False) أثناء تسليم معلّق ⇒ ما تفقدش
    الدليل: العلامة والمعرّف بيفضلوا، والدورة الجاية تكمّل بدون إعادة إرسال."""
    db = _MarkerFailsThenOk(str(tmp_path / "t.sqlite3"))
    _seed_full(db)
    bot = FakeBot()
    w = Watcher(_finished_client(), db, bot, chat_id=1)
    asyncio.run(w.tick())  # إرسال + فشل كتابة العلامة ⇒ تلميح in-memory
    assert len(bot.sent) == 1
    assert "c1" in w._marker_pending
    seq_before = db.get_watched("c1").watch_seq

    db.add_watched("c1", "t", new_lifecycle=False)  # إعادة نداء مكرّرة
    assert db.get_watched("c1").watch_seq == seq_before  # المعرّف محفوظ

    asyncio.run(w.tick())  # إعادة كتابة العلامة + التسجيل بدون إرسال تاني
    assert len(bot.sent) == 1  # مفيش إرسال مكرّر (الدليل ما اتفقدش)
    assert not db.is_watched("c1")
    assert db.get_notification_state("c1").notified_status == "finished"


def test_rewatch_new_lifecycle_reconciles_current_hint_and_gets_fresh_identity(tmp_path):
    """NTF-19/20: دورة متابعة جديدة بتاخد معرّف جديد، والتلميح الحالي (نفس الدورة) بيتسوّى
    (يتسجّل `notified_status`) بدل ما يتفقد — الدليل محفوظ، والدورة الجديدة نظيفة."""
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "t")
    db.set_last_state("c1", "running")
    db.upsert_notification_state("c1", status="running", notified_status="running", updated_at="t")
    w = Watcher(_finished_client(), db, FakeBot(), chat_id=1)
    old_seq = db.get_watched("c1").watch_seq
    w._marker_pending["c1"] = ("finished", old_seq)  # تلميح مرتبط بالدورة الحالية

    db.add_watched("c1", "t")  # دورة جديدة ⇒ معرّف جديد + تسوية التسليم المعلّق
    assert db.get_watched("c1").watch_seq != old_seq
    assert db.get_watched("c1").pending_delivery_state is None
    assert db.get_notification_state("c1").notified_status == "finished"  # الدليل محفوظ (مفيش فقد)
    assert "c1" not in w._marker_pending  # التلميح اتسوّى/اتشال


# ============================ NTF-20: new lifecycle preserves delivery evidence ===========
def _search_finished_client():
    class C:
        async def search_conversations(self, limit=20, page_id=None):
            return {
                "items": [{"id": "c1", "title": "t", "execution_status": "finished"}],
                "next_page_id": None,
            }
    return C()


def test_new_lifecycle_via_hook_reconciles_hint_no_duplicate(tmp_path):
    """NTF-20: تلميح in-memory (كتابة العلامة فشلت) + دورة جديدة عبر `add_watched` الحقيقي
    ⇒ الـ hook يثبّت الدليل ويتسوّى (notified_status)، والدورة الجديدة نظيفة، والمُبلّغ
    ما يكرّرش الإرسال بعد إزالة المتابعة."""
    db = _MarkerFailsThenOk(str(tmp_path / "t.sqlite3"))
    _seed_full(db)
    bot = FakeBot()
    w = Watcher(_finished_client(), db, bot, chat_id=1)
    asyncio.run(w.tick())
    assert len(bot.sent) == 1
    assert "c1" in w._marker_pending
    old_seq = db.get_watched("c1").watch_seq

    db.add_watched("c1", "t", new_lifecycle=True)  # المسار الحقيقي (بيستدعي الـ hook)
    assert db.get_notification_state("c1").notified_status == "finished"  # الدليل محفوظ
    assert db.get_watched("c1").watch_seq != old_seq  # دورة جديدة
    assert "c1" not in w._marker_pending  # التلميح اتسوّى

    w.unwatch("c1")
    assert not db.is_watched("c1")
    nbot = FakeBot()
    asyncio.run(Notifier(_search_finished_client(), db, nbot, chat_id=1).tick())
    assert nbot.sent == []  # مفيش ازدواج


def test_new_lifecycle_hook_failure_blocks_and_keeps_evidence(tmp_path):
    """NTF-20: لو تثبيت التلميح فشل (قاعدة بتفشل دايمًا)، الدورة الجديدة ترفض (fail closed)
    والدليل ما يضيعش (مفيش حذف صامت)."""
    db = _MarkerAlwaysFails(str(tmp_path / "t.sqlite3"))
    _seed_full(db)
    bot = FakeBot()
    w = Watcher(_finished_client(), db, bot, chat_id=1)
    asyncio.run(w.tick())
    assert "c1" in w._marker_pending

    with pytest.raises(sqlite3.OperationalError):
        db.add_watched("c1", "t", new_lifecycle=True)
    assert "c1" in w._marker_pending  # التلميح محفوظ
    assert db.get_watched("c1").pending_delivery_state is None  # لسه ما اتسجّلش


def test_unwatch_reconciles_durable_pending_no_duplicate(tmp_path):
    """NTF-20: إزالة متابعة مع علامة دائمة ⇒ تتسجّل (notified_status) قبل الحذف،
    والمُبلّغ ما يكرّرش الإرسال."""
    db = Database(str(tmp_path / "t.sqlite3"))
    _seed_full(db)
    db.set_pending_delivery("c1", "finished")
    w = Watcher(_finished_client(), db, FakeBot(), chat_id=1)

    w.unwatch("c1")
    assert not db.is_watched("c1")
    assert db.get_notification_state("c1").notified_status == "finished"  # الدليل محفوظ
    nbot = FakeBot()
    asyncio.run(Notifier(_search_finished_client(), db, nbot, chat_id=1).tick())
    assert nbot.sent == []  # مفيش ازدواج


def test_restart_with_durable_pending_notifier_suppressed(tmp_path):
    """NTF-20: إعادة تشغيل والعملية فيها علامة دائمة ⇒ المُبلّغ بيسكت (الدليل دائم)."""
    path = str(tmp_path / "t.sqlite3")
    db = Database(path)
    _seed_full(db)
    db.set_pending_delivery("c1", "finished")
    db.close()

    db2 = Database(path)  # إعادة فتح (restart)
    assert db2.get_watched("c1").pending_delivery_state == "finished"  # الدليل نجا
    nbot = FakeBot()
    asyncio.run(Notifier(_search_finished_client(), db2, nbot, chat_id=1).tick())
    assert nbot.sent == []  # مفيش ازدواج


# ==================== NTF-23: compare-and-swap removal (stale-snapshot race) ==============
class _BarrierClient:
    """get_conversations يستنى barrier، وبعدين يرجّع استجابة محدّدة (بلا sleeps)."""

    def __init__(self, response, reached=None, release=None):
        self._response = response
        self._reached = reached
        self._release = release

    async def get_conversations(self, ids):
        if self._reached is not None:
            self._reached.set()
        if self._release is not None:
            await self._release.wait()
        return self._response


def test_m1_stale_tick_does_not_delete_new_lifecycle(tmp_path):
    """NTF-23 M-1: tick يلتقط دورة A ويتوقف في get_conversations؛ تُعمل دورة B لنفس
    المحادثة؛ الدورة القديمة تكمل ⇒ B تفضل متابَعة (CAS يفشل)."""
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "t")  # دورة A
    seq_a = db.get_watched("c1").watch_seq

    reached = asyncio.Event()
    release = asyncio.Event()
    client = _BarrierClient([], reached=reached, release=release)  # c1 مش ظاهر ⇒ missing
    w = Watcher(client, db, FakeBot(), chat_id=1)
    w._misses["c1"] = MISSING_LIMIT - 1  # دورة واحدة تكفي للإزالة

    async def run():
        task = asyncio.create_task(w.tick())
        await reached.wait()  # الدورة القديمة التقطت اللقطة وواقفة في await
        db.add_watched("c1", "t", new_lifecycle=True)  # دورة B
        seq_b = db.get_watched("c1").watch_seq
        assert seq_b != seq_a
        release.set()
        await task
        return seq_b

    seq_b = asyncio.run(run())
    assert db.is_watched("c1")  # B سليمة (السباق ما شالهاش)
    assert db.get_watched("c1").watch_seq == seq_b


def test_m1_stale_notify_failure_decision_does_not_touch_new_lifecycle(tmp_path):
    """NTF-23: قرار فشل الإشعار القديم (العدّاد/الإزالة) ما يتطبّقش على دورة جديدة."""
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "t")
    db.set_last_state("c1", "running")  # لازم last_state غير منتهية عشان مسار الإشعار
    reached = asyncio.Event()
    release = asyncio.Event()
    client = _BarrierClient([{"id": "c1", "title": "t", "execution_status": "finished"}],
                            reached=reached, release=release)
    # الإرسال بيفشل ⇒ _handle_notify_failure (قرار قديم مبني على seq_a)
    w = Watcher(client, db, FailFirstBot("انتهى الشات"), chat_id=1)

    async def run():
        task = asyncio.create_task(w.tick())
        await reached.wait()
        db.add_watched("c1", "t", new_lifecycle=True)  # دورة B أثناء await
        seq_b = db.get_watched("c1").watch_seq
        release.set()
        await task
        return seq_b

    seq_b = asyncio.run(run())
    # قرار الفشل القديم (seq_a) ما زوّدش عدّاد B ولا شالها
    assert db.is_watched("c1")
    assert db.get_watched("c1").watch_seq == seq_b
    assert db.get_watched("c1").retry_count == 0


def test_m1_stale_tick_preserves_new_lifecycle_pending_evidence(tmp_path):
    """NTF-23: لو دورة B عندها دليل تسليم معلّق، الدورة القديمة (CAS يفشل) ما تلمسوش."""
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "t")
    reached = asyncio.Event()
    release = asyncio.Event()
    client = _BarrierClient([], reached=reached, release=release)
    w = Watcher(client, db, FakeBot(), chat_id=1)
    w._misses["c1"] = MISSING_LIMIT - 1

    async def run():
        task = asyncio.create_task(w.tick())
        await reached.wait()
        db.add_watched("c1", "t", new_lifecycle=True)  # دورة B
        db.set_pending_delivery("c1", "finished")  # دليل خاص بـ B
        release.set()
        await task

    asyncio.run(run())
    assert db.is_watched("c1")
    assert db.get_watched("c1").pending_delivery_state == "finished"  # ما اتمسحش


def test_new_lifecycle_resets_miss_counter(tmp_path):
    """NTF-23: دورة جديدة بتصفّر عدّاد الغياب ⇒ ما تتشالش بقرار قديم."""
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "t")
    w = Watcher(FakeClient({"c1": {"id": "c1", "title": "t", "execution_status": "finished"}}),
                db, FakeBot(), chat_id=1)
    w._misses["c1"] = MISSING_LIMIT - 1
    db.add_watched("c1", "t", new_lifecycle=True)  # hook يصفّر العدّاد
    assert "c1" not in w._misses


# ==================== Decision A: disabling proactive notifications ======================
# Disabling the preference suppresses **proactive/global** notifications (the Notifier) but
# NOT notifications for conversations the user explicitly watches (the Watcher). These tests
# prove both halves against real component behavior (no source inspection).
def test_decision_a_disabled_suppresses_global_but_watched_still_notifies(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.set_notifications_enabled(False)  # الإشعارات الاستباقية متوقفة
    # c1 متابَعة صراحةً (اختيار المستخدم)؛ c2 عالمية (اتأسّس لها خط أساس سابقًا).
    db.add_watched("c1", "watched")
    db.set_last_state("c1", "running")
    db.upsert_notification_state("c1", status="running", notified_status="running", updated_at="t")
    db.upsert_notification_state("c2", status="running", notified_status="running", updated_at="t")

    both = {"c1": {"id": "c1", "title": "w", "execution_status": "finished"},
            "c2": {"id": "c2", "title": "g", "execution_status": "finished"}}

    # (1) المُبلّغ العام: c2 عالمية ⇒ مكتومة؛ c1 متابَعة (ملكية المراقب) ⇒ كمان مكتومة.
    nbot = FakeBot()
    notifier = Notifier(_search_finished_client(), db, nbot, chat_id=1)
    asyncio.run(notifier.tick())
    assert nbot.sent == []  # مفيش أي إشعار استباقي وهو متوقف

    # (2) المراقب: c1 متابَعة ⇒ **لسه بتبلّغ** رغم إن الإشعارات الاستباقية متوقفة.
    wbot = FakeBot()
    w = Watcher(FakeClient(both, reply="تم"), db, wbot, chat_id=1)
    asyncio.run(w.tick())
    assert len(wbot.sent) == 1
    assert "انتهى الشات" in wbot.sent[0]
    assert db.list_watched() == []  # c1 خلصت واتشالت
    # وc2 لسه من غير إشعار (ولا هي متابَعة).
    assert not db.is_watched("c2")


def test_decision_a_watched_notifies_even_when_global_disabled_directly(tmp_path):
    """تأكيد مباشر للنصف التاني: المراقب بيعمل tick عادي وهو مش قارئ للتفضيل."""
    db = Database(str(tmp_path / "t.sqlite3"))
    db.set_notifications_enabled(False)
    db.add_watched("c1", "t")
    bot = FakeBot()
    w = Watcher(
        FakeClient({"c1": {"id": "c1", "title": "t", "execution_status": "finished"}}, reply="r"),
        db, bot, chat_id=1,
    )
    asyncio.run(w.tick())
    assert len(bot.sent) == 1 and "انتهى الشات" in bot.sent[0]
