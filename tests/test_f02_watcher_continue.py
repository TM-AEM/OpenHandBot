"""OHB2 F-02 / `DEF-007` — اختبار انحدار **تمييزي** لسلوك `continue` في `bot/watcher.py`.

السياق (`DEF-007`): `Watcher.tick` كان بيلتقط فشل `clear_retry_not_before`، يسجّل
«هيتخطّى»، وبعدين **يكمّل** لمسار الإشعار رغم فشل المسح (تناقض السجل مع السلوك + إشعار
مكرّر محتمل رغم إن موعد إعادة المحاولة لسه قايم). الإصلاح = `continue` (تخطّي الشات فعلاً).

الاختبار يفشل لو اتشال/اتحطّ الـ `continue` في مكان غلط: من غير التخطّي، الشات الهدف
(اللي عليه موعد منتهي وفشل مسحه) هيتبلّغ **خطأً** فوق الشات التاني المستقل.
"""
import asyncio

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

    async def send_message(self, chat_id=None, text=None, parse_mode=None, **kw):
        self.sent.append(text)

    async def send_document(self, chat_id=None, document=None, **kw):
        self.sent.append("DOC")


def test_watcher_skips_conversation_when_clear_retry_deadline_fails(tmp_path):
    """فشل `clear_retry_not_before` لشات عليه موعد منتهي ⇒ تخطّي ذلك الشات (مفيش إشعار)،
    والاستمرار للشات المستقل التالي.

    على السلوك القديم (من غير `continue`): الشات الهدف كان هيتبلّغ كمان ⇒ رسالتان بدل واحدة.
    """
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "الهدف")
    db.add_watched("c2", "المستقل")
    # موعد إعادة محاولة **منتهي** لـ c1 ⇒ الكود بيحاول يمسحه (والمسح هيفشل).
    db.set_retry_not_before("c1", "2000-01-01T00:00:00+00:00")

    client = FakeClient(
        {
            "c1": {"id": "c1", "title": "الهدف", "execution_status": "finished"},
            "c2": {"id": "c2", "title": "المستقل", "execution_status": "finished"},
        },
        reply="تم",
    )
    bot = FakeBot()
    w = Watcher(client, db, bot, chat_id=1)

    def boom(_cid):
        raise RuntimeError("db down")

    db.clear_retry_not_before = boom  # فشل المسح للشات الهدف فقط

    asyncio.run(w.tick())

    # الشات المستقل اتعالج (رسالة واحدة)؛ الشات الهدف اتخطّى (مفيش رسالة عنه).
    assert len(bot.sent) == 1
    assert "المستقل" in bot.sent[0]
    assert all("الهدف" not in t for t in bot.sent)
    # الهدف لسه متابَع (تخطّي، مش إزالة) — الموعد لسه قايم لأنه مامسحش.
    watched_ids = {x.conversation_id for x in db.list_watched()}
    assert watched_ids == {"c1"}
    assert db.get_retry_not_before("c1") == "2000-01-01T00:00:00+00:00"


def test_watcher_skip_is_isolated_per_conversation(tmp_path):
    """فشل مسح موعد الشات الهدف مايمنعش معالجة شات تاني عليه موعد مسحه **ينجح**.

    يثبت إن التخطّي محدود بالشات الهدف (مش الدورة كلها) وإن الشات التاني يتعالج عادي.
    """
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "الهدف")
    db.add_watched("c2", "سليم")
    db.set_retry_not_before("c1", "2000-01-01T00:00:00+00:00")  # منتهي ⇒ يتنادى المسح
    db.set_retry_not_before("c2", "2000-01-01T00:00:00+00:00")  # منتهي ⇒ المسح ينجح

    client = FakeClient(
        {
            "c1": {"id": "c1", "title": "الهدف", "execution_status": "finished"},
            "c2": {"id": "c2", "title": "سليم", "execution_status": "finished"},
        },
        reply="تم",
    )
    bot = FakeBot()
    w = Watcher(client, db, bot, chat_id=1)

    real_clear = db.clear_retry_not_before

    def selective(cid):
        if cid == "c1":
            raise RuntimeError("db down")
        return real_clear(cid)

    db.clear_retry_not_before = selective

    asyncio.run(w.tick())

    assert len(bot.sent) == 1
    assert "سليم" in bot.sent[0]
    assert db.get_retry_not_before("c2") is None  # اتمسح بنجاح
    assert db.get_retry_not_before("c1") == "2000-01-01T00:00:00+00:00"  # لسه قايم
