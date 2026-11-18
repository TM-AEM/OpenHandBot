"""OHB2 F-02 / `DEF-007` — اختبار انحدار **تمييزي** لسلوك `return` في `bot/notifier.py`.

السياق (`DEF-007`): `Notifier._process` كان بيلتقط فشل `clear_retry_not_before`، يسجّل
«هيتخطّى»، وبعدين **يكمّل** لمسار الإشعار رغم فشل المسح (إشعار رغم إن موعد إعادة المحاولة
لسه قايم). الإصلاح = `return` (إنهاء معالجة المحادثة دي عند النقطة الصح).

الاختبار يفشل لو اتشال/اتحطّ الـ `return` في مكان غلط: من غير `return`، المحادثة الهدف
هتكمّل لمسار الإشعار وتُسجَّل/تُرسَل **خطأً**.
"""
import asyncio

from bot.db import Database
from bot.notifier import Notifier


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id=None, text=None, parse_mode=None, **kw):
        self.sent.append(text)

    async def send_document(self, chat_id=None, document=None, **kw):
        self.sent.append("DOC")


class FakeSearchClient:
    def __init__(self, items):
        self._items = items

    async def search_conversations(self, limit=20, page_id=None):
        return {"items": self._items, "next_page_id": None}


def _conv(cid, status):
    return {"id": cid, "title": cid, "execution_status": status}


def test_notifier_returns_on_clear_retry_deadline_failure(tmp_path):
    """فشل `clear_retry_not_before` لشات عليه موعد منتهي ⇒ `return` (مفيش إشعار، مفيش تسجيل).

    على السلوك القديم (من غير `return`): المعالجة كانت هتكمّل لمسار الإشعار ⇒ رسالة لتيليجرام.
    """
    db = Database(str(tmp_path / "t.sqlite3"))
    # خط أساس: الحالة السابقة "running" ⇒ انتقال لـ "finished" مؤهّل لإشعار.
    db.upsert_notification_state("c1", status="running", notified_status="running", updated_at="t")
    db.set_retry_not_before("c1", "2000-01-01T00:00:00+00:00")  # منتهي ⇒ يتنادى المسح

    def boom(_cid):
        raise RuntimeError("db down")

    db.clear_retry_not_before = boom

    bot = FakeBot()
    n = Notifier(FakeSearchClient([_conv("c1", "finished")]), db, bot, chat_id=1)
    asyncio.run(n.tick())

    # مفيش إرسال (تخطّي فعلي)، والحالة مااتسجّلتش كـ"محسوبة" (لسه هتتعاود).
    assert bot.sent == []
    assert db.count_inbox() == 0
    assert db.get_notification_state("c1").notified_status == "running"
    # الموعد لسه قايم (المسح فشل) ⇒ إعادة محاولة الدورة الجاية.
    assert db.get_retry_not_before("c1") == "2000-01-01T00:00:00+00:00"


def test_notifier_return_is_isolated_per_conversation(tmp_path):
    """فشل مسح موعد c1 مايمنعش معالجة c2 (اللي مسح موعده ينجح) — التخطّي لكل محادثة."""
    db = Database(str(tmp_path / "t.sqlite3"))
    db.upsert_notification_state("c1", status="running", notified_status="running", updated_at="t")
    db.upsert_notification_state("c2", status="running", notified_status="running", updated_at="t")
    db.set_retry_not_before("c1", "2000-01-01T00:00:00+00:00")
    db.set_retry_not_before("c2", "2000-01-01T00:00:00+00:00")

    real_clear = db.clear_retry_not_before

    def selective(cid):
        if cid == "c1":
            raise RuntimeError("db down")
        return real_clear(cid)

    db.clear_retry_not_before = selective

    bot = FakeBot()
    n = Notifier(FakeSearchClient([_conv("c1", "finished"), _conv("c2", "finished")]), db, bot, chat_id=1)
    asyncio.run(n.tick())

    assert len(bot.sent) == 1  # c2 بس اتبعت
    assert db.get_retry_not_before("c1") == "2000-01-01T00:00:00+00:00"  # لسه قايم
    assert db.get_retry_not_before("c2") is None  # اتمسح
