"""OHB2-08 Batch 3R-FIX2-F1: استرجاع حدث الانتقال النهائي المعلّق أثناء بقاء المتابعة.

المراجعة المستقلة أثبتت عيب دورة تسليم (F-1): حدث انتقال نهائي بيفضل `pending` للأبد لحد
ما المتابعة تتشال، لأن:
- المُبلّل يستثني المحادثات المتابَعة من الاسترجاع، ويتخطّى معالجتها الاستباقية.
- المراقب ما بيعيدش المحاولة لأن الحالة النهائية اتسجّلت بالفعل (`watched.last_state` نهائي)
  فشرط الانتقال النشط (`is_terminal(state) and not is_terminal(w.last_state)`) بقى False.

الإصلاح: المُبلّل بيسترجع حدث الانتقال النهائي **الحالي** للمحادثة المتابَعة **العالقة**
(اللي مسار المراقب النشط مش هيعيد المحاولة لها)، بحجز ذرّي (`claim_pending_inbox`) يمنع
إرسال نفس الحدث من العاملين معًا. الاختبارات بتستخدم قاعدة حقيقية ومسارات العاملين الحقيقية.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from telegram.error import RetryAfter, TelegramError

from bot.db import Database, INBOX_DELIVERY_PENDING
from bot.notifier import Notifier
from bot.watcher import Watcher


# ------------------------------------------------------------------ helpers
class CombinedClient:
    """عميل يخدم المراقب (`get_conversations`) والمُبلّل (`search_conversations`)."""

    def __init__(self, by_id, reply=None):
        self.by_id = by_id
        self._reply = reply

    async def get_conversations(self, ids):
        return [self.by_id[i] for i in ids if i in self.by_id]

    async def get_last_reply(self, conversation_id):
        return self._reply

    async def search_conversations(self, limit=20, page_id=None):
        return {"items": list(self.by_id.values()), "next_page_id": None}


class Bot:
    def __init__(self, fail=False):
        self.sent = []
        self.fail = fail

    async def send_message(self, chat_id=None, text=None, parse_mode=None, **kw):
        if self.fail:
            raise TelegramError("boom")
        self.sent.append(text)

    async def send_document(self, chat_id=None, document=None, **kw):
        if self.fail:
            raise TelegramError("boom")
        self.sent.append("DOC")


class RetryAfterBot(Bot):
    def __init__(self, seconds=30, fail_once=True):
        super().__init__()
        self._seconds = seconds
        self._fail_once = fail_once

    async def send_message(self, chat_id=None, text=None, parse_mode=None, **kw):
        if self._fail_once:
            self._fail_once = False
            raise RetryAfter(self._seconds)
        self.sent.append(text)


def conv(cid="c1", status="finished", title="عنوان"):
    return {"id": cid, "title": title, "execution_status": status}


def seed_watch(db, cid="c1", last_state="running"):
    db.add_watched(cid, "عنوان")
    db.set_last_state(cid, last_state)
    db.upsert_notification_state(
        cid, status=last_state, notified_status=last_state, updated_at="t"
    )


def leave_terminal_event_pending(db, client, cid="c1"):
    """المراقب يكتشف انتقالًا نهائيًا، تسليمه يفشل ⇒ حدث `pending` والمتابعة تفضل.

    يرجّع صف الحدث المعلّق (canonical).
    """
    w = Watcher(client, db, Bot(fail=True), chat_id=1)
    asyncio.run(w.tick())
    assert db.is_watched(cid)
    items = db.list_inbox()
    assert len(items) == 1 and items[0].delivery_status == INBOX_DELIVERY_PENDING
    return items[0]


def mark_watch_stuck(db, cid="c1", terminal="finished"):
    """يسجّل الحالة النهائية على صف المتابعة — زي ما المسار النشط (re-watch/persist) بيعمل.

    بعدها شرط الانتقال النشط (`is_terminal(state) and not is_terminal(w.last_state)`) بقى
    False، فمسار المراقب النشط ما بيعيدش المحاولة ⇒ الحدث يبقى معلّق للأبد من غير الإصلاح.
    """
    db.set_last_state(cid, terminal)


# ============================================ A: استرجاع F-1 أثناء بقاء المتابعة
def test_f1_recovery_while_watched(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    seed_watch(db)
    client = CombinedClient({"c1": conv()})
    event = leave_terminal_event_pending(db, client)
    mark_watch_stuck(db)

    bot = Bot()
    n = Notifier(client, db, bot, chat_id=1)
    for _ in range(3):
        asyncio.run(n.tick())

    items = db.list_inbox()
    assert len(bot.sent) == 1                       # رسالة واحدة بس
    assert len(items) == 1                          # نفس الصف الواحد (مفيش حدث تاني)
    assert items[0].id == event.id
    assert items[0].delivery_status == "delivered"
    assert db.is_watched("c1")                      # المتابعة **لسه** موجودة
    db.close()


def test_f1_not_duplicated_once_delivered(tmp_path):
    """بعد الاسترجاع، دورات إضافية ما تبعتش تاني (العصر اتعلّم مُبلّغ)."""
    db = Database(str(tmp_path / "t.sqlite3"))
    seed_watch(db)
    client = CombinedClient({"c1": conv()})
    leave_terminal_event_pending(db, client)
    mark_watch_stuck(db)

    bot = Bot()
    n = Notifier(client, db, bot, chat_id=1)
    for _ in range(5):
        asyncio.run(n.tick())
    assert len(bot.sent) == 1
    assert db.count_inbox() == 1
    db.close()


# ============================================ B: استرجاع عبر العاملين
def test_cross_worker_watcher_then_notifier(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    seed_watch(db)
    client = CombinedClient({"c1": conv()})
    leave_terminal_event_pending(db, client)
    mark_watch_stuck(db)

    bot = Bot()
    w = Watcher(client, db, bot, chat_id=1)
    n = Notifier(client, db, bot, chat_id=1)
    asyncio.run(w.tick())   # استرجاع المراقب: يستثني المتابَعة ⇒ مش بتاعه
    asyncio.run(n.tick())   # المُبلّل يسترجع الحدث العالق

    assert len(bot.sent) == 1
    assert db.count_inbox() == 1
    assert db.list_inbox()[0].delivery_status == "delivered"
    db.close()


def test_cross_worker_notifier_then_watcher(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    seed_watch(db)
    client = CombinedClient({"c1": conv()})
    leave_terminal_event_pending(db, client)
    mark_watch_stuck(db)

    bot = Bot()
    w = Watcher(client, db, bot, chat_id=1)
    n = Notifier(client, db, bot, chat_id=1)
    asyncio.run(n.tick())   # المُبلّل أولًا: يسترجع الحدث العالق
    asyncio.run(w.tick())   # المراقب: مفيش انتقال نشط ⇒ ما يبعش

    assert len(bot.sent) == 1
    assert db.count_inbox() == 1
    assert db.list_inbox()[0].delivery_status == "delivered"
    db.close()


def test_cross_worker_separate_connections_concurrent(tmp_path):
    """اتصالان منفصلان على نفس الملف، العاملان يتنافسان في نفس اللحظة ⇒ إرسال واحد."""
    path = str(tmp_path / "t.sqlite3")
    db_seed = Database(path)
    seed_watch(db_seed)
    client = CombinedClient({"c1": conv()})
    leave_terminal_event_pending(db_seed, client)
    mark_watch_stuck(db_seed)
    db_seed.close()

    db_w = Database(path)   # اتصال المراقب
    db_n = Database(path)   # اتصال المُبلّل
    bot_w, bot_n = Bot(), Bot()
    w = Watcher(client, db_w, bot_w, chat_id=1)
    n = Notifier(client, db_n, bot_n, chat_id=1)

    async def both():
        await asyncio.gather(w.tick(), n.tick())

    asyncio.run(both())

    assert len(bot_w.sent) + len(bot_n.sent) == 1   # إرسال واحد بس عبر العاملين
    assert db_w.count_inbox() == 1
    assert db_w.list_inbox()[0].delivery_status == "delivered"
    db_w.close()
    db_n.close()


def test_two_notifier_recoveries_concurrent_claim(tmp_path):
    """مُبلّلان على اتصالين منفصلين يتنافسان على نفس الحدث ⇒ الحجز الذرّي يمنع الازدواج."""
    path = str(tmp_path / "t.sqlite3")
    db_seed = Database(path)
    seed_watch(db_seed)
    client = CombinedClient({"c1": conv()})
    leave_terminal_event_pending(db_seed, client)
    mark_watch_stuck(db_seed)
    db_seed.close()

    db1, db2 = Database(path), Database(path)
    bot1, bot2 = Bot(), Bot()
    n1 = Notifier(client, db1, bot1, chat_id=1)
    n2 = Notifier(client, db2, bot2, chat_id=1)

    async def both():
        await asyncio.gather(n1.tick(), n2.tick())

    asyncio.run(both())

    assert len(bot1.sent) + len(bot2.sent) == 1
    assert db1.count_inbox() == 1
    assert db1.list_inbox()[0].delivery_status == "delivered"
    db1.close()
    db2.close()


# ============================================ C: عدم الازدواج مع المسار النشط
def test_no_duplicate_while_active_path_owns(tmp_path):
    """المتابعة لسه غير عالقة (`last_state` غير نهائي) ⇒ المُبلّل ما يسترجعش (المراقب مالك)."""
    db = Database(str(tmp_path / "t.sqlite3"))
    seed_watch(db)   # last_state = running (غير نهائي)
    client = CombinedClient({"c1": conv()})
    leave_terminal_event_pending(db, client)   # الحدث معلّق، المتابعة لسه غير عالقة

    bot = Bot()
    n = Notifier(client, db, bot, chat_id=1)
    for _ in range(3):
        asyncio.run(n.tick())

    # المُبلّل ما بعتش (المسار النشط للمراقب لسه هيعيد المحاولة)
    assert len(bot.sent) == 0
    assert db.list_inbox()[0].delivery_status == INBOX_DELIVERY_PENDING
    db.close()


# ============================================ D: الحفاظ على مواعيد RetryAfter
def test_retry_after_preserves_deadline_and_claim(tmp_path):
    """RetryAfter على مسار الاسترجاع: يسجّل الموعد ويحرّر الحجز (الحدث يفضل قابلًا للاسترجاع)."""
    db = Database(str(tmp_path / "t.sqlite3"))
    seed_watch(db)
    client = CombinedClient({"c1": conv()})
    leave_terminal_event_pending(db, client)
    mark_watch_stuck(db)

    bot = RetryAfterBot(seconds=30, fail_once=True)
    n = Notifier(client, db, bot, chat_id=1)
    asyncio.run(n.tick())   # 429: يجدول إعادة المحاولة ويحرّر الحجز

    item = db.list_inbox()[0]
    assert item.delivery_status == INBOX_DELIVERY_PENDING
    assert item.next_retry_at is not None      # الموعد اتسجّل
    assert item.claim_token is None            # الحجز اتحرّر
    assert len(bot.sent) == 0

    # الدورة الجاية (بعد الموعد) توصّل الحدث
    db.set_inbox_retry_deadline(item.id, None)
    asyncio.run(n.tick())
    assert len(bot.sent) == 1
    assert db.list_inbox()[0].delivery_status == "delivered"
    db.close()


# ============================================ E: مفيش حدث ثاني لنفس الانتقال
def test_no_second_event_created(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    seed_watch(db)
    client = CombinedClient({"c1": conv()})
    event = leave_terminal_event_pending(db, client)
    mark_watch_stuck(db)

    bot = Bot()
    n = Notifier(client, db, bot, chat_id=1)
    w = Watcher(client, db, bot, chat_id=1)
    for _ in range(3):
        asyncio.run(n.tick())
        asyncio.run(w.tick())

    items = db.list_inbox()
    assert len(items) == 1 and items[0].id == event.id
    assert len(bot.sent) == 1
    db.close()


# ============================================ F: الحجز القديم (عملية وقعت) بيتحرّر
def test_stale_claim_expires_and_recovers(tmp_path):
    """حجز معلّق من عملية وقعت (claim_at قديم) بيتخطّاه الاسترجاع ⇒ الحدث ما يعلقش للأبد."""
    db = Database(str(tmp_path / "t.sqlite3"))
    seed_watch(db)
    client = CombinedClient({"c1": conv()})
    event = leave_terminal_event_pending(db, client)
    mark_watch_stuck(db)

    # نحاكي عملية وقعت بعد ما حجزت الحدث وقبل ما تحرّره.
    assert db.claim_pending_inbox(event.id, "dead-worker-token", "2000-01-01T00:00:00+00:00")
    assert db.list_inbox()[0].claim_token == "dead-worker-token"

    bot = Bot()
    n = Notifier(client, db, bot, chat_id=1)
    asyncio.run(n.tick())

    assert len(bot.sent) == 1
    item = db.list_inbox()[0]
    assert item.delivery_status == "delivered"
    assert item.claim_token is None
    db.close()


def test_fresh_claim_blocks_recovery(tmp_path):
    """حجز حديث (مش منتهي) بيمنع الاسترجاع (العامل التاني لسه بيحاول)."""
    db = Database(str(tmp_path / "t.sqlite3"))
    seed_watch(db)
    client = CombinedClient({"c1": conv()})
    event = leave_terminal_event_pending(db, client)
    mark_watch_stuck(db)

    now = datetime.now(timezone.utc).isoformat()
    assert db.claim_pending_inbox(event.id, "live-worker-token", now)  # حجز حديث

    bot = Bot()
    n = Notifier(client, db, bot, chat_id=1)
    asyncio.run(n.tick())

    assert len(bot.sent) == 0
    assert db.list_inbox()[0].claim_token == "live-worker-token"
    db.close()


# ============================================ G: نفس العلق للحدث الاستباقي (نفس السبب الجذري)
def test_proactive_pending_event_recovers_while_watched(tmp_path):
    """حدث استباقي معلّق ثم المستخدم راقب المحادثة (نهائية) ⇒ كان يعلق؛ بقى يتسترجع."""
    db = Database(str(tmp_path / "t.sqlite3"))
    db.upsert_notification_state(
        "c1", status="running", notified_status="running", updated_at="t"
    )
    client = CombinedClient({"c1": conv()})
    asyncio.run(Notifier(client, db, Bot(fail=True), chat_id=1).tick())   # استباقي معلّق

    event = db.list_inbox()[0]
    assert event.kind == "proactive" and event.delivery_status == INBOX_DELIVERY_PENDING

    # المستخدم يضيف متابعة لمحادثة **نهائية** (مسار المراقب النشط ما هيعيد المحاولة).
    db.add_watched("c1", "عنوان")
    db.set_last_state("c1", "finished")

    bot = Bot()
    n = Notifier(client, db, bot, chat_id=1)
    w = Watcher(client, db, bot, chat_id=1)
    for _ in range(3):
        asyncio.run(n.tick())
        asyncio.run(w.tick())

    assert len(bot.sent) == 1
    assert db.count_inbox() == 1 and db.list_inbox()[0].id == event.id
    assert db.list_inbox()[0].delivery_status == "delivered"
    assert db.is_watched("c1")
    db.close()
