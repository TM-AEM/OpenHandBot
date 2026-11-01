"""OHB2-08-05 Batch 3R-FIX: اختبارات إزالة ازدواج الإشعار عبر العاملين (H-1).

السيناريو القاتل اللي لقاه المراجع المستقل: محادثة متابَعة توصل لحالة نهائية، المراقب
يستنفد محاولات التسليم فبيشيل المتابعة والحدث يفضل `pending`؛ بعدها المراقب يسترجع الحدث
ويبعته، والمُبلّل **مستقلًا** يشوف نفس الانتقال فيبعت إشعارًا استباقيًا تاني ⇒ رسالتين
لتليجرام لانتقال واحد. الإصلاح: هوية انتقال موحّدة (`transition_status` = الحالة المرصودة)
+ قيد تفرّد جزئي (محادثة، حالة) للصفوف المعلّقة + تنسيق تسليم المالك عند الاسترجاع.

بيختبر الاختبارات **عدد رسائل تليجرام الفعلي** و**عدد صفوف الحدث المنطقي** مع بعض.
"""
from __future__ import annotations

import asyncio
import sqlite3

from telegram.error import RetryAfter, TelegramError

from bot.db import Database, INBOX_DELIVERY_PENDING
from bot.notifier import Notifier
from bot.watcher import MAX_WATCH_NOTIFY_RETRIES, Watcher


# ------------------------------------------------------------------ helpers
class CombinedClient:
    """عميل يخدم المراقب (`get_conversations`) والمُبلّل (`search_conversations`).

    `by_id` مرجع قابل للتعديل عشان نغيّر حالة المحادثة بين الدورات (انتقالات).
    """

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


class FailReconcileDb(Database):
    """قاعدة بتفشل في التسوية الذرّية أول `fails` مرة (حقن فولت حتمي)."""

    def __init__(self, path, fails=1):
        self._fails = fails
        self.attempts = 0
        super().__init__(path)

    def reconcile_notifier_pending(self, conversation_id, now):
        self.attempts += 1
        if self.attempts <= self._fails:
            raise sqlite3.OperationalError("disk I/O error")
        return super().reconcile_notifier_pending(conversation_id, now)


def wire(w: Watcher, n: Notifier) -> None:
    """يربط المراقب بالمُبلّل زي الإنتاج (نقطة تنسيق تسليم المالك)."""
    w.set_owner_delivery(
        lambda cid, status, now: n.record_notification_sent(cid, status, now)
    )


def seed_watch(db, cid="c1", title="عنوان", last_state="running"):
    db.add_watched(cid, title)
    db.set_last_state(cid, last_state)
    db.upsert_notification_state(
        cid, status=last_state, notified_status=last_state, updated_at="t"
    )


def conv(cid="c1", status="finished", title="عنوان"):
    return {"id": cid, "title": title, "execution_status": status}


def exhaust_watch(db, client, cid="c1"):
    """يستنفد محاولات المراقب ⇒ إزالة المتابعة والحدث يفضل pending. يرجّع الحدث."""
    w = Watcher(client, db, Bot(fail=True), chat_id=1)
    for _ in range(MAX_WATCH_NOTIFY_RETRIES):
        asyncio.run(w.tick())
    assert not db.is_watched(cid)
    items = db.list_inbox()
    assert len(items) == 1 and items[0].delivery_status == INBOX_DELIVERY_PENDING
    return items[0]


# =================================================== A: ازدواج بعد استنفاد المحاولات
def test_a_no_cross_worker_duplicate_after_retry_exhaustion(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    seed_watch(db)
    client = CombinedClient({"c1": conv()}, reply="تم")

    old = exhaust_watch(db, client)
    assert old.kind == "terminal" and old.transition_status == "finished"

    # المراقب يسترجع الحدث المعلّق (يوصّله) + المُبلّل يشوف نفس الانتقال.
    bot = Bot()
    n = Notifier(client, db, bot, chat_id=1)
    w = Watcher(client, db, bot, chat_id=1)
    wire(w, n)
    asyncio.run(w.tick())   # استرجاع الحدث المعلّق
    asyncio.run(n.tick())   # المُبلّل: نفس الانتقال ⇒ مفيش إشعار منافس

    assert len(bot.sent) == 1                       # رسالة واحدة بس
    assert db.count_inbox() == 1                    # حدث منطقي واحد
    assert db.list_inbox()[0].delivery_status == "delivered"
    db.close()


# =================================================== B: ترتيب عكسي (المُبلّل أولًا)
def test_b_reverse_order_notifier_first_then_watcher_recovery(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    seed_watch(db)
    client = CombinedClient({"c1": conv()}, reply="تم")

    exhaust_watch(db, client)

    bot = Bot()
    n = Notifier(client, db, bot, chat_id=1)
    w = Watcher(client, db, bot, chat_id=1)
    wire(w, n)
    asyncio.run(n.tick())   # المُبلّل أولًا: يشوف الانتقال (مسجّل من المراقب) ⇒ يتخطّى
    asyncio.run(w.tick())   # بعدها المراقب يسترجع ويوصل الحدث

    assert len(bot.sent) == 1
    assert db.count_inbox() == 1
    assert db.list_inbox()[0].delivery_status == "delivered"
    db.close()


# =================================================== C: إعادة تشغيل بين العاملين
def test_c_restart_between_workers_no_duplicate(tmp_path):
    path = str(tmp_path / "t.sqlite3")
    db = Database(path)
    seed_watch(db)
    client = CombinedClient({"c1": conv()}, reply="تم")
    exhaust_watch(db, client)
    db.close()  # إعادة تشغيل العملية

    db2 = Database(path)  # نفس الملف ⇒ الحالة دائمة
    assert db2.count_inbox() == 1
    assert db2.list_inbox()[0].delivery_status == INBOX_DELIVERY_PENDING

    bot = Bot()
    n = Notifier(client, db2, bot, chat_id=1)
    w = Watcher(client, db2, bot, chat_id=1)
    wire(w, n)
    asyncio.run(w.tick())
    asyncio.run(n.tick())

    assert len(bot.sent) == 1
    assert db2.count_inbox() == 1
    assert db2.list_inbox()[0].delivery_status == "delivered"
    db2.close()


# =================================================== D: انتقال جديد حقيقي
def test_d_genuine_new_transition_is_distinct(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    by_id = {"c1": conv(status="finished")}
    client = CombinedClient(by_id)
    db.upsert_notification_state("c1", status="running", notified_status="running", updated_at="t")
    bot = Bot()
    n = Notifier(client, db, bot, chat_id=1)

    asyncio.run(n.tick())            # finished (انتقال 1)
    assert len(bot.sent) == 1 and db.count_inbox() == 1

    by_id["c1"] = conv(status="running")
    asyncio.run(n.tick())            # رجع running ⇒ مفيش إشعار
    assert len(bot.sent) == 1

    by_id["c1"] = conv(status="finished")
    asyncio.run(n.tick())            # finished تاني = انتقال جديد ⇒ إشعار تاني + حدث تاني
    assert len(bot.sent) == 2
    assert db.count_inbox() == 2
    assert all(it.delivery_status == "delivered" for it in db.list_inbox())
    db.close()


# =================================================== E: استطلاع مكرّر لنفس الحالة
def test_e_duplicate_polling_no_new_event(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    client = CombinedClient({"c1": conv()})
    db.upsert_notification_state("c1", status="running", notified_status="running", updated_at="t")
    bot = Bot()
    n = Notifier(client, db, bot, chat_id=1)

    for _ in range(3):
        asyncio.run(n.tick())

    assert len(bot.sent) == 1
    assert db.count_inbox() == 1
    db.close()


# =================================================== F: RetryAfter يحفظ الهوية
def test_f_retry_after_preserves_identity_and_deadline(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    client = CombinedClient({"c1": conv()})
    db.upsert_notification_state("c1", status="running", notified_status="running", updated_at="t")
    bot = RetryAfterBot(seconds=30)
    n = Notifier(client, db, bot, chat_id=1)

    asyncio.run(n.tick())            # 429 ⇒ الحدث pending بموعد دائم، مفيش إرسال
    items = db.list_inbox()
    assert items[0].delivery_status == INBOX_DELIVERY_PENDING
    assert items[0].transition_status == "finished"
    assert db.get_retry_not_before("c1") is not None   # موعد دائم

    db.clear_retry_not_before("c1")
    asyncio.run(n.tick())            # نجاح ⇒ نفس الصف delivered (مفيش حدث تاني)

    assert len(bot.sent) == 1
    assert db.count_inbox() == 1
    assert db.list_inbox()[0].delivery_status == "delivered"
    db.close()


# =================================================== G: فشل معاملة التسوية
def test_g_reconcile_failure_no_false_delivered_then_recovers(tmp_path):
    db = FailReconcileDb(str(tmp_path / "t.sqlite3"), fails=1)
    client = CombinedClient({"c1": conv()})
    db.upsert_notification_state("c1", status="running", notified_status="running", updated_at="t")
    bot = Bot()
    n = Notifier(client, db, bot, chat_id=1)

    asyncio.run(n.tick())   # تليجرام قبِل، بس التسوية فشلت ⇒ الحدث يفضل pending
    assert len(bot.sent) == 1
    items = db.list_inbox()
    assert items[0].delivery_status == INBOX_DELIVERY_PENDING   # مفيش delivered كاذب
    assert db.get_notifier_pending("c1") == "finished"          # العلامة الدائمة موجودة
    assert db.get_notification_state("c1").notified_status == "running"

    asyncio.run(n.tick())   # التسوية تنجح ⇒ نفس الصف delivered، مفيش إعادة إرسال
    assert len(bot.sent) == 1
    assert db.count_inbox() == 1
    assert db.list_inbox()[0].delivery_status == "delivered"

    # انتقال مختلف (error) لسه مؤهّل — الفشل ما كتمش باقي الانتقالات.
    client.by_id["c1"] = conv(status="error")
    asyncio.run(n.tick())
    assert len(bot.sent) == 2
    db.close()


def test_g2_persistent_reconcile_failure_blocks_without_false_delivered(tmp_path):
    """فشل التسوية المستمر ما يعلّمش الحدث delivered كاذبًا، ويوقف المعالجة (آمن)."""
    path = str(tmp_path / "t.sqlite3")
    db = FailReconcileDb(path, fails=99)
    client = CombinedClient({"c1": conv()})
    db.upsert_notification_state("c1", status="running", notified_status="running", updated_at="t")
    bot = Bot()
    n = Notifier(client, db, bot, chat_id=1)

    asyncio.run(n.tick())   # تليجرام قبِل، التسوية فشلت ⇒ الحدث pending والعلامة باقية
    assert len(bot.sent) == 1
    assert db.list_inbox()[0].delivery_status == INBOX_DELIVERY_PENDING
    assert db.get_notification_state("c1").notified_status == "running"

    # انتقال مختلف (error): العلامة المعلّقة لسه ما اتسوّتش ⇒ نتخطّى (مفيش إرسال أعمى
    # ومفيش تسجيل كاذب) — إشارة on the safe side.
    client.by_id["c1"] = conv(status="error")
    asyncio.run(n.tick())
    assert len(bot.sent) == 1                                    # مفيش إرسال جديد
    assert db.get_notification_state("c1").notified_status == "running"  # مفيش تسجيل كاذب
    assert all(it.delivery_status == INBOX_DELIVERY_PENDING for it in db.list_inbox())
    db.close()

    # بعد ما الفشل يزول (قاعدة سليمة على نفس الملف): التسوية تنجح والانتقال الجديد يوصل.
    db2 = Database(path)
    n2 = Notifier(client, db2, bot, chat_id=1)
    asyncio.run(n2.tick())
    assert len(bot.sent) == 2
    assert db2.get_notification_state("c1").notified_status == "error"
    assert all(it.delivery_status == "delivered" for it in db2.list_inbox())
    db2.close()
