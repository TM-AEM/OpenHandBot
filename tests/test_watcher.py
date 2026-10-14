import asyncio

from telegram.error import TelegramError

from bot.db import Database
from bot.watcher import Watcher


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

