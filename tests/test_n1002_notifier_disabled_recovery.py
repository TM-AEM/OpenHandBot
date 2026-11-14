"""OHB2-N10-02: انحدار لعيب M1 — استرجاع الأحداث الاستباقية المعلّقة لازم يحترم إعداد
الإشعارات العام، زي المسار العادي (`_process`).

العيب (M1): `Notifier._recover_pending_events` كان بيسترجع كل الأحداث الاستباقية المعلّقة
**من غير** ما يقرأ `notifications_enabled`، فحدث `proactive` اكتُشف قبل التعطيل واتسلّم في
دورة لاحقة رغم إن الإشعارات متعطّلة.

الفجوة اللي سمحت بمرور العيب: مفيش اختبار بيجمع «الإشعارات متعطّلة» مع «حدث معلّق موجود
مسبقًا». الاختبارات الحالية بتغطّي التعطيل في المسار العادي (`_process`) بس.

الفشل اللي الاختبارات دي هتكتشفه: إرسال استباقي غير مصرّح به وقت التعطيل، أو فقد إشعار
انتقال نهائي لمتابعة صريحة بعد الإصلاح (اللي **لازم** يفضل شغّال).
"""
from __future__ import annotations

import asyncio

from telegram.error import TelegramError

from bot.db import Database, INBOX_DELIVERY_PENDING
from bot.notifier import Notifier
from bot.watcher import Watcher


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


class SearchClient:
    """مُبلّل من غير أي محادثات ظاهرة ⇒ المسار العادي مش هيعالج حاجة، فالاسترجاع بس شغّال."""

    async def search_conversations(self, limit=20, page_id=None):
        return {"items": [], "next_page_id": None}


def conv(cid="c1", status="finished", title="عنوان"):
    return {"id": cid, "title": title, "execution_status": status}


def _status(db, eid):
    return {it.id: it.delivery_status for it in db.list_inbox()}.get(eid)


def test_disabled_does_not_recover_pending_proactive(tmp_path):
    """M1: مع الإشعارات متعطّلة، حدث استباقي معلّق مايتسلّمش ويفضل `pending`."""
    db = Database(str(tmp_path / "t.sqlite3"))
    eid = db.add_inbox_event(
        "c1", "t", "proactive", "pmsg", "t",
        event_key="k1", chat_id=1, transition_status="finished", transition_seq=1,
    )
    db.set_notifications_enabled(False)

    bot = Bot()
    n = Notifier(SearchClient(), db, bot, chat_id=1)
    asyncio.run(n.tick())

    assert bot.sent == []                          # مفيش إرسال وقت التعطيل
    assert _status(db, eid) == INBOX_DELIVERY_PENDING
    db.close()


def test_reenable_then_delivers_pending_proactive(tmp_path):
    """بعد إعادة التفعيل، الحدث المعلّق يتسلّم (مفيش فقد صامت)."""
    db = Database(str(tmp_path / "t.sqlite3"))
    eid = db.add_inbox_event(
        "c1", "t", "proactive", "pmsg", "t",
        event_key="k1", chat_id=1, transition_status="finished", transition_seq=1,
    )
    db.set_notifications_enabled(False)
    bot = Bot()
    n = Notifier(SearchClient(), db, bot, chat_id=1)
    asyncio.run(n.tick())
    assert bot.sent == []

    db.set_notifications_enabled(True)
    asyncio.run(n.tick())
    assert bot.sent == ["pmsg"]
    assert _status(db, eid) == "delivered"
    db.close()


def test_disabled_still_recovers_stuck_watched_terminal(tmp_path):
    """الإصلاح ما بيكسرش F-1: حدث انتقال نهائي لمتابعة عالقة يتسلّم حتى والإشعارات متعطّلة.

    المتابعة الصريحة مش بتتأثر بمفتاح الإشعارات العام (نفس عقد المسار العادي)، فحرس M1
    بيتطبّق على الاستباقي بس.
    """
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "عنوان")
    db.set_last_state("c1", "running")
    db.upsert_notification_state("c1", status="running", notified_status="running", updated_at="t")
    client = CombinedClient({"c1": conv()})

    # المراقب يكتشف انتقالًا نهائيًا وتسليمه يفشل ⇒ حدث `pending` والمتابعة تفضل.
    w = Watcher(client, db, Bot(fail=True), chat_id=1)
    asyncio.run(w.tick())
    db.set_last_state("c1", "finished")           # المتابعة «عالقة» (المسار النشط مش هيعيد)
    db.set_notifications_enabled(False)           # الإشعارات العامة متعطّلة

    bot = Bot()
    n = Notifier(client, db, bot, chat_id=1)
    for _ in range(3):
        asyncio.run(n.tick())

    assert len(bot.sent) == 1                       # الحدث النهائي المعلّق اتسلّم رغم التعطيل
    assert db.list_inbox()[0].delivery_status == "delivered"
    db.close()
