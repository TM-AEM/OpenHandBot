"""OHB2-08-05 Batch 3R-FIX2: هوية الانتقال الدائمة (`transition_seq`) بدل وصف الحالة.

المراجعة المستقلة لـ Batch 3R-FIX لقت عيب HIGH: القيد الموحّد كان على
(المحادثة، `transition_status`) — يعني **وصف الحالة** — فانتقالان مختلفان بنفس الحالة
(`finished` معلّق ثم `finished` جديد) كانوا يتعاملوا كأنهم نفس الحدث، والثاني يتفقد.
الإصلاح: الهوية بقت **رقم عصر الاكتشاف** (`transition_seq`) من `note_transition`:
يزيد مرة واحدة عند اكتشاف انتقال جديد، ويثبت خلال إعادات المحاولة، ويُشارَك بين العاملين.

الاختبارات دي بتغطي:
- السيناريو القاتل: A معلّق (فشل تسليم) ثم انتقال B حقيقي بنفس الحالة ⇒ حدثين منفصلين.
- إعادة المحاولة لنفس الانتقال ⇒ نفس الصف (مفيش ازدواج).
- التنسيق عبر العاملين لنفس الانتقال لسه شغّال (H-1).
- حماية الاحتفاظ (M-1) لسه شغّالة.
"""
from __future__ import annotations

import asyncio

from telegram.error import TelegramError

from bot.db import Database, INBOX_DELIVERY_PENDING
from bot.notifier import Notifier
from bot.watcher import MAX_WATCH_NOTIFY_RETRIES, Watcher


# ------------------------------------------------------------------ helpers
class CombinedClient:
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


def conv(cid="c1", status="finished", title="عنوان"):
    return {"id": cid, "title": title, "execution_status": status}


def seed(db, cid="c1", last_state="running"):
    db.upsert_notification_state(
        cid, status=last_state, notified_status=last_state, updated_at="t"
    )


# ============================== 1: انتقال B حقيقي بنفس الحالة مايتفقدش (العيب الأصلي)
def test_undelivered_a_then_same_status_b_not_lost(tmp_path):
    """A (finished) تسليمه فشل ⇒ معلّق؛ بعدين running ثم finished تاني = انتقال B.

    لازم B ياخد **حدثًا منفصلًا** ويتسلّم، مش يتعامل كأنه نفس A (العيب اللي لقيته المراجعة).
    """
    db = Database(str(tmp_path / "t.sqlite3"))
    by_id = {"c1": conv(status="finished")}
    client = CombinedClient(by_id)
    seed(db, "c1", "running")

    bot = Bot(fail=True)
    n = Notifier(client, db, bot, chat_id=1)

    asyncio.run(n.tick())                       # A=finished: الإرسال فشل ⇒ معلّق
    assert db.count_inbox() == 1
    assert db.list_inbox()[0].delivery_status == INBOX_DELIVERY_PENDING

    by_id["c1"] = conv(status="running")
    asyncio.run(n.tick())                       # رجع running (عصر جديد)
    by_id["c1"] = conv(status="finished")
    asyncio.run(n.tick())                       # B=finished: انتقال حقيقي جديد

    # حدثان منفصلان برقمي عصر مختلفين (مش صف واحد).
    seqs = sorted(it.transition_seq for it in db.list_inbox())
    assert db.count_inbox() == 2
    assert seqs == [1, 2]

    bot.fail = False
    asyncio.run(n.tick())                       # الاسترجاع يوصّل A، والمعالجة توصّل B

    assert len(bot.sent) == 2                   # رسالتان لانتقالين مختلفين
    assert all(it.delivery_status == "delivered" for it in db.list_inbox())
    db.close()


# ============================== 2: إعادة المحاولة لنفس الانتقال ⇒ نفس الحدث
def test_retry_reuses_same_event(tmp_path):
    """فشل تسليم متكرّر لنفس الانتقال ⇒ نفس الصف (نفس الهوية)، مفيش ازدواج."""
    db = Database(str(tmp_path / "t.sqlite3"))
    client = CombinedClient({"c1": conv(status="finished")})
    seed(db, "c1", "running")
    bot = Bot(fail=True)
    n = Notifier(client, db, bot, chat_id=1)

    for _ in range(3):
        asyncio.run(n.tick())

    assert db.count_inbox() == 1               # صف واحد بس
    assert db.list_inbox()[0].transition_seq == 1
    db.close()


# ============================== 3: انتقالات بنفس الحالة بأرقام عصر متزايدة
def test_recurring_status_gets_increasing_epochs(tmp_path):
    """finished→running→finished→running→finished ⇒ ثلاثة أرقام عصر مختلفة."""
    db = Database(str(tmp_path / "t.sqlite3"))
    by_id = {"c1": conv(status="finished")}
    client = CombinedClient(by_id)
    seed(db, "c1", "running")
    bot = Bot()
    n = Notifier(client, db, bot, chat_id=1)

    # finished→running→finished→running→finished = 3 انتقالات نهائية بنفس الحالة.
    for _ in range(2):
        asyncio.run(n.tick())                  # finished
        by_id["c1"] = conv(status="running")
        asyncio.run(n.tick())                  # running
        by_id["c1"] = conv(status="finished")
    asyncio.run(n.tick())                      # finished الأخير

    assert db.count_inbox() == 3
    assert sorted(it.transition_seq for it in db.list_inbox()) == [1, 2, 3]
    assert len(bot.sent) == 3
    db.close()


# ============================== 4: نفس الانتقال بين العاملين ⇒ صف واحد (H-1)
def test_same_transition_cross_worker_dedup(tmp_path):
    """المراقب والمُبلّل على **نفس** الانتقال ⇒ حدث منطقي واحد ورسالة واحدة (H-1)."""
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "عنوان")
    db.set_last_state("c1", "running")
    seed(db, "c1", "running")
    client = CombinedClient({"c1": conv(status="finished")}, reply="تم")

    wf = Watcher(client, db, Bot(fail=True), chat_id=1)
    for _ in range(MAX_WATCH_NOTIFY_RETRIES):
        asyncio.run(wf.tick())
    assert not db.is_watched("c1")
    assert db.count_inbox() == 1               # حدث المراقب معلّق

    bot = Bot()
    n = Notifier(client, db, bot, chat_id=1)
    w = Watcher(client, db, bot, chat_id=1)
    w.set_owner_delivery(lambda cid, st, now: n.record_notification_sent(cid, st, now))
    asyncio.run(w.tick())
    asyncio.run(n.tick())

    assert len(bot.sent) == 1
    assert db.count_inbox() == 1
    assert db.list_inbox()[0].delivery_status == "delivered"
    db.close()


# ============================== 5: التمييز بالهوية مش بوصف الحالة (مستوى القاعدة)
def test_db_identity_is_seq_not_status(tmp_path):
    """إدراج مباشر: نفس الحالة برقم عصر مختلف ⇒ صفان؛ نفس الرقم ⇒ محجوب."""
    db = Database(str(tmp_path / "t.sqlite3"))
    a = db.add_inbox_event(
        "c1", "t", "proactive", "A", "t",
        event_key="k1", transition_status="finished", transition_seq=1,
    )
    b = db.add_inbox_event(
        "c1", "t", "proactive", "B", "t",
        event_key="k2", transition_status="finished", transition_seq=2,
    )
    assert a is not None and b is not None
    assert db.count_inbox() == 2

    # نفس العصر ⇒ القيد الموحّد يرفض (نفس الانتقال).
    dup = db.add_inbox_event(
        "c1", "t", "proactive", "A'", "t",
        event_key="k3", transition_status="finished", transition_seq=1,
    )
    assert dup is None
    assert db.count_inbox() == 2
    db.close()


# ============================== 6: حماية الاحتفاظ (M-1) لسه شغّالة
def test_retention_protection_unchanged(tmp_path):
    """الصفوف المعلّقة/غير المقروءة محميّة من التقليم (M-1) — لسه شغّال بعد التغيير."""
    db = Database(str(tmp_path / "t.sqlite3"))
    # انتقالان معلّقان (seq=1,2) مايتقلّموش أبدًا رغم ضغط صفوف مقروءة كثيرة.
    e1 = db.add_inbox_event(
        "c1", "t", "proactive", "A", "t", event_key="k1", transition_seq=1
    )
    e2 = db.add_inbox_event(
        "c1", "t", "proactive", "B", "t", event_key="k2", transition_seq=2
    )
    for i in range(60):
        db.add_inbox_item("c1", "t", "terminal", f"x{i}", f"t{i}")
    db.mark_all_inbox_read("tr")
    db.add_inbox_item("c1", "t", "terminal", "trig", "t")

    ids = {it.id for it in db.list_inbox(limit=10000)}
    assert e1 in ids and e2 in ids            # المعلّقة محميّة
    db.close()


# ============================== 7: الفهرس الموحّد على الهوية مش على وصف الحالة
def _index_columns(conn, name):
    rows = conn.execute(f"PRAGMA index_info({name})").fetchall()
    return [r[2] for r in rows] if rows else None


def test_unique_index_on_transition_seq(tmp_path):
    """الفهرس الموحّد بقى على (المحادثة، transition_seq)، والقديم (على الحالة) اتشال."""
    db = Database(str(tmp_path / "t.sqlite3"))
    assert _index_columns(db._conn, "idx_inbox_transition_seq_unique") == [
        "conversation_id", "transition_seq",
    ]
    assert _index_columns(db._conn, "idx_inbox_transition_unique") is None
    db.close()


def test_migration_swaps_old_status_index(tmp_path):
    """قاعدة فيها الفهرس القديم (على transition_status) تتصلّح عند الفتح: يتشال ويتحط الجديد."""
    path = str(tmp_path / "old.sqlite3")
    db = Database(path)
    db._conn.execute("DROP INDEX IF EXISTS idx_inbox_transition_seq_unique")
    db._conn.execute("DROP INDEX IF EXISTS idx_inbox_transition_unique")
    db._conn.execute(
        "CREATE UNIQUE INDEX idx_inbox_transition_unique "
        "ON notification_inbox(conversation_id, transition_status) "
        "WHERE transition_status IS NOT NULL AND delivery_status='pending'"
    )
    db._conn.execute(
        "INSERT INTO notification_inbox(conversation_id, title, kind, message, created_at, "
        "delivery_status, transition_status) "
        "VALUES('c1','t','proactive','قديم','t0','delivered','finished')"
    )
    db._conn.commit()
    db.close()

    db2 = Database(path)  # الفتح التاني يعمل التبديل
    assert _index_columns(db2._conn, "idx_inbox_transition_unique") is None
    assert _index_columns(db2._conn, "idx_inbox_transition_seq_unique") == [
        "conversation_id", "transition_seq",
    ]
    assert db2.count_inbox() == 1  # مفيش فقد بيانات
    db2.close()
