"""OHB2-08 Batch 3R-FIX2-N1-N2: إصلاحان مُتحقَّق منهما من مراجعة F-1 المستقلة.

N-1 (HIGH): مفتاح حدث المراقب كان على `watch_seq` + `last_state` — والاتنين ما بيتغيّرش
لما التسليم يفشل ⇒ انتقال نهائي تانٍ بنفس الحالة كان يعيد استخدام نفس المفتاح ويتفقد،
وممكن يوصل محتوى قديم. الإصلاح: مفتاح أحداث الانتقال بيتبنى على هوية الانتقال الدائمة
(`transition_seq`) — نفس هوية المُبلّل.

N-2 (MEDIUM): حدث انتقال نهائي **متجاوز** (superseded) لمحادثة **متابَعة عالقة** كان يعلق
للأبد (المُبلّل كان بيتخطّى الـ superseded، والمراقب `exclude_watched=True`). الإصلاح:
المُبلّل بيتولّاه لو هو أعلى عصر معلّق (الهوية الكانونية) ومافيش صف معلّق بعصر أحدث.

الاختبارات دي بتشتغل على مسارات العاملين الحقيقية وقاعدة مؤقتة (tmp_path).
"""
from __future__ import annotations

import asyncio

from telegram.error import TelegramError

from bot.db import Database, INBOX_DELIVERY_PENDING
from bot.notifier import Notifier
from bot.watcher import Watcher


# ------------------------------------------------------------------ helpers
class CombinedClient:
    def __init__(self, by_id, replies=None):
        self.by_id = by_id
        self.replies = replies if replies is not None else {}

    async def get_conversations(self, ids):
        return [self.by_id[i] for i in ids if i in self.by_id]

    async def get_last_reply(self, conversation_id):
        return self.replies.get(conversation_id)

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


def conv(status="finished", title="عنوان"):
    return {"id": "c1", "title": title, "execution_status": status}


def watch(db, cid="c1", last_state="running"):
    """يسجّل متابعة + حالة لقطة (زي مسار إضافة المتابعة الحقيقي)."""
    db.add_watched(cid, "عنوان")
    db.set_last_state(cid, last_state)
    db.upsert_notification_state(cid, status=last_state, notified_status=last_state, updated_at="t")


def terminal_pending(db):
    return [it for it in db.list_inbox() if it.kind == "terminal"]


# ================================================= N-1: هوية حدث المراقب
def test_n1_event_key_uses_transition_seq(tmp_path):
    """مفتاح حدث الانتقال بيتبنى على `transition_seq` (مش `last_state` المتغيّر)."""
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "t")
    db.set_last_state("c1", "running")
    w = Watcher(CombinedClient({}), db, Bot(), chat_id=1)
    wk = db.get_watched("c1")
    k1 = w._inbox_event_key(wk, "terminal", 1)
    k2 = w._inbox_event_key(wk, "terminal", 2)
    assert k1 != k2                         # انتقالان مختلفان ⇒ مفتاحان مختلفان
    assert k1 == w._inbox_event_key(wk, "terminal", 1)   # نفس الانتقال ⇒ نفس المفتاح (idempotent)
    assert k1.endswith("|1") and k2.endswith("|2")       # الهوية = transition_seq
    # مفتاح الأنواع غير الانتقالية لسه على دورة المتابعة + الحالة (سلوك قديم محفوظ).
    assert w._inbox_event_key(wk, "timeout") == f"c1|timeout|{wk.watch_seq}|running"
    db.close()


def test_n1_recurring_terminal_gets_distinct_events(tmp_path):
    """finished (فشل) → running → finished (فشل) ⇒ **حدثان منفصلان** (مش صف واحد)."""
    db = Database(str(tmp_path / "t.sqlite3"))
    by_id = {"c1": conv(status="finished")}
    client = CombinedClient(by_id, replies={"c1": "R1"})
    watch(db, "c1", "running")
    bot = Bot(fail=True)
    w = Watcher(client, db, bot, chat_id=1)
    n = Notifier(client, db, bot, chat_id=1)

    asyncio.run(w.tick()); asyncio.run(n.tick())     # finished#1 يفشل ⇒ معلّق
    by_id["c1"] = conv(status="running")
    asyncio.run(w.tick()); asyncio.run(n.tick())     # رجع running (عصر جديد)
    by_id["c1"] = conv(status="finished")
    client.replies["c1"] = "R2"
    asyncio.run(w.tick()); asyncio.run(n.tick())     # finished#2 يفشل ⇒ معلّق

    items = terminal_pending(db)
    assert len(items) == 2                                   # حدثان منفصلان
    assert sorted(it.transition_seq for it in items) == [1, 2]
    assert len({it.event_key for it in items}) == 2          # مفاتيح مختلفة
    db.close()


def test_n1_failed_old_event_does_not_block_new_transition(tmp_path):
    """حدث فاشل قديم ما يمنعش إنشاء حدث الانتقال الأحدث."""
    db = Database(str(tmp_path / "t.sqlite3"))
    by_id = {"c1": conv(status="finished")}
    client = CombinedClient(by_id, replies={"c1": "R1"})
    watch(db, "c1", "running")
    bot = Bot(fail=True)
    w = Watcher(client, db, bot, chat_id=1)
    n = Notifier(client, db, bot, chat_id=1)

    asyncio.run(w.tick()); asyncio.run(n.tick())     # finished#1 معلّق
    by_id["c1"] = conv(status="running")
    asyncio.run(w.tick()); asyncio.run(n.tick())
    by_id["c1"] = conv(status="finished")
    client.replies["c1"] = "R2"
    asyncio.run(w.tick()); asyncio.run(n.tick())     # finished#2

    items = terminal_pending(db)
    assert len(items) == 2
    assert any(it.transition_seq == 2 for it in items)       # الأحدث اتسجّل
    db.close()


def test_n1_repeated_poll_of_same_transition_is_idempotent(tmp_path):
    """إعادة استطلاع نفس الانتقال (فشل متكرّر) ⇒ صف واحد بس (نفس الهوية)."""
    db = Database(str(tmp_path / "t.sqlite3"))
    by_id = {"c1": conv(status="finished")}
    client = CombinedClient(by_id, replies={"c1": "R"})
    watch(db, "c1", "running")
    bot = Bot(fail=True)
    w = Watcher(client, db, bot, chat_id=1)
    n = Notifier(client, db, bot, chat_id=1)

    for _ in range(3):
        asyncio.run(w.tick()); asyncio.run(n.tick())

    items = terminal_pending(db)
    assert len(items) == 1
    assert items[0].transition_seq == 1
    db.close()


def test_n1_content_matches_transition(tmp_path):
    """كل حدث بيوصّل **محتوى انتقاله** (الأول R1، التاني R2) — مش محتوى قديم."""
    db = Database(str(tmp_path / "t.sqlite3"))
    by_id = {"c1": conv(status="finished")}
    client = CombinedClient(by_id, replies={"c1": "R1"})
    watch(db, "c1", "running")
    bot = Bot(fail=True)
    w = Watcher(client, db, bot, chat_id=1)
    n = Notifier(client, db, bot, chat_id=1)

    asyncio.run(w.tick()); asyncio.run(n.tick())
    by_id["c1"] = conv(status="running")
    asyncio.run(w.tick()); asyncio.run(n.tick())
    by_id["c1"] = conv(status="finished")
    client.replies["c1"] = "R2"
    asyncio.run(w.tick()); asyncio.run(n.tick())

    bot.fail = False
    for _ in range(4):
        asyncio.run(w.tick()); asyncio.run(n.tick())

    assert len(bot.sent) == 2
    joined = "\n".join(bot.sent)
    assert "R1" in joined and "R2" in joined               # محتوى كل انتقال وصل
    db.close()


# ================================================= N-2: الحدث المتجاوز العالق
def _seed_superseded_watched(db, *, watch_state="finished", current_seq=2):
    """ينشئ: متابعة عالقة + حدث انتقال **متجاوز** معلّق (عصر 1) وحالة عصر أحدث (2)."""
    db.add_watched("c1", "عنوان")
    db.set_last_state("c1", watch_state)
    db.upsert_notification_state("c1", status="running", notified_status="running", updated_at="t")
    eid = db.add_inbox_event(
        "c1", "t", "terminal", "OLD", "t",
        transition_status="finished", transition_seq=1,
    )
    db.upsert_notification_state(
        "c1", status="finished", notified_status="finished", updated_at="t",
        transition_seq=current_seq,
    )
    return eid


def test_n2_superseded_terminal_recovers_while_watched(tmp_path):
    """حدث نهائي متجاوز لمتابعة **عالقة** ⇒ المُبلّل يسترجعه (ما يعلقش للأبد)."""
    db = Database(str(tmp_path / "t.sqlite3"))
    eid = _seed_superseded_watched(db)
    client = CombinedClient({"c1": conv(status="finished")})
    bot = Bot()
    n = Notifier(client, db, bot, chat_id=1)

    for _ in range(3):
        asyncio.run(n.tick())

    assert db.get_inbox_item(eid).delivery_status == "delivered"
    assert len(bot.sent) == 1
    db.close()


def test_n2_superseded_not_recovered_when_not_stuck(tmp_path):
    """متابعة **غير عالقة** (`last_state` غير نهائي) ⇒ المُبلّل ما يسترجعش (المراقب مالك)."""
    db = Database(str(tmp_path / "t.sqlite3"))
    eid = _seed_superseded_watched(db, watch_state="running")
    client = CombinedClient({"c1": conv(status="finished")})
    bot = Bot()
    n = Notifier(client, db, bot, chat_id=1)

    for _ in range(3):
        asyncio.run(n.tick())

    assert db.get_inbox_item(eid).delivery_status == INBOX_DELIVERY_PENDING
    assert len(bot.sent) == 0
    db.close()


def test_n2_newer_pending_event_is_recovered_first(tmp_path):
    """لو فيه صف معلّق بعصر أحدث، الأقدم المتجاوز ما يسبقوش (مافيش ترتيب معكوس)."""
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "عنوان")
    db.set_last_state("c1", "finished")
    db.upsert_notification_state("c1", status="running", notified_status="running", updated_at="t")
    old = db.add_inbox_event("c1", "t", "terminal", "OLD", "t",
                             transition_status="finished", transition_seq=1)
    new = db.add_inbox_event("c1", "t", "terminal", "NEW", "t",
                             transition_status="finished", transition_seq=2)
    db.upsert_notification_state("c1", status="finished", notified_status="finished",
                                 updated_at="t", transition_seq=2)
    client = CombinedClient({"c1": conv(status="finished")})
    bot = Bot()
    n = Notifier(client, db, bot, chat_id=1)

    # العصر الحالي (2) يتسلّم أولًا (المسار العادي في _recover يعالجه كـ current).
    asyncio.run(n.tick())
    assert db.get_inbox_item(new).delivery_status == "delivered"
    assert db.get_inbox_item(old).delivery_status == INBOX_DELIVERY_PENDING
    # وبعد ما الأحدث اتسلّم، الأقدم (بقى أعلى معلّق) يتسلّم في الدورة اللي بعدها.
    asyncio.run(n.tick())
    assert db.get_inbox_item(old).delivery_status == "delivered"
    db.close()


def test_n2_current_epoch_still_delivered_once(tmp_path):
    """العصر الحالي لسه exactly-once (الحجز الذرّي) بعد التعديل."""
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "عنوان")
    db.set_last_state("c1", "finished")
    db.upsert_notification_state("c1", status="finished", notified_status="finished",
                                 updated_at="t", transition_seq=1)
    eid = db.add_inbox_event("c1", "t", "terminal", "CUR", "t",
                             transition_status="finished", transition_seq=1)
    client = CombinedClient({"c1": conv(status="finished")})
    bot = Bot()
    n = Notifier(client, db, bot, chat_id=1)

    for _ in range(3):
        asyncio.run(n.tick())

    assert db.get_inbox_item(eid).delivery_status == "delivered"
    assert len(bot.sent) == 1
    assert db.count_inbox() == 1
    db.close()


def test_n2_timeout_kind_not_recovered_by_notifier(tmp_path):
    """الأنواع غير الانتقالية (timeout) لمتابعة عالقة ما بيسترجعهاش المُبلّل (المراقب مالكها)."""
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "عنوان")
    db.set_last_state("c1", "finished")
    db.upsert_notification_state("c1", status="finished", notified_status="finished",
                                 updated_at="t", transition_seq=1)
    eid = db.add_inbox_event("c1", "t", "timeout", "TO", "t")
    client = CombinedClient({"c1": conv(status="finished")})
    bot = Bot()
    n = Notifier(client, db, bot, chat_id=1)

    asyncio.run(n.tick())
    assert db.get_inbox_item(eid).delivery_status == INBOX_DELIVERY_PENDING
    assert len(bot.sent) == 0
    db.close()
