"""OHB2 F-01 / `DEF-008` — اختبار انحدار **تمييزي** لسلوك الحجز المقيَّد بالمعرّف في
`deliver_outbox`.

الفرق المُثبَت (لا مجرد نجاح الاستدعاء):
- السلوك القديم: `deliver_outbox` كان يستدعي `db.claim_outbox()` غير المُقيَّد بالمعرّف
  (أقدم `pending` أولاً) فيحجز ويرسل **سجلاً آخر أقدم** غير المطلوب ويترك الهدف `pending`.
- السلوك الحالي: يستدعي `db.claim_outbox_by_id(outbox_id, ...)` فيحجز **السجل المطلوب نفسه**
  فقط ولا يلمس أي سجل آخر مؤهّل.

الاختبارات بتفشل على السلوك القديم (ترسل السجل الأقدم وتترك الهدف `pending`).
"""
import asyncio

from bot.db import Database
from bot.outbox import deliver_outbox


class RecordingClient:
    """عميل fake بيسجّل نداءات الإرسال ويرجّع محادثة لكل معرّف مطلوب."""

    def __init__(self, convs):
        self._convs = convs
        self.sent = []

    async def get_conversations(self, ids):
        return [self._convs[i] for i in ids if i in self._convs]

    async def resume_sandbox(self, sandbox_id):
        pass

    async def send_message(self, conversation_id, text):
        self.sent.append((conversation_id, text))


class Bot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id=None, text=None, **kw):
        self.sent.append(text)


def _db(tmp_path):
    return Database(str(tmp_path / "t.sqlite3"))


def _running(cid):
    return {"id": cid, "title": cid, "execution_status": "running", "sandbox_status": "RUNNING"}


def test_deliver_outbox_claims_only_target_leaves_older_pending(tmp_path):
    """سجل أقدم مؤهّل (id أصغر) + سجل هدف: الحجز المقيَّد يرسل الهدف فقط ويترك الأقدم `pending`.

    على السلوك القديم (أقدم `pending` أولاً) كان هيرسل «OLDER» ويترك الهدف `pending`.
    """
    db = _db(tmp_path)
    older = db.add_outbox("c-older", 99, "OLDER", "2026-01-01T00:00:00+00:00")
    target = db.add_outbox("c-target", 99, "TARGET", "2026-01-01T00:00:01+00:00")
    assert older < target  # «older» فعلاً id أصغر (اللي السلوك القديم كان هيمسكه)

    client = RecordingClient({"c-older": _running("c-older"), "c-target": _running("c-target")})
    asyncio.run(deliver_outbox(client, db, Bot(), target))

    assert client.sent == [("c-target", "TARGET")]  # الهدف بس اترسل
    assert db.get_outbox(target).status == "sent"
    assert db.get_outbox(older).status == "pending"  # السجل الأقدم ما اتلمسش
    assert db.count_outbox("pending") == 1


def test_deliver_outbox_claims_only_target_among_many_pending(tmp_path):
    """تلات سجلات `pending`: إرسال الأوسط يحجز/يرسل الأوسط بس، ويسيب الأقدم والأحدث `pending`."""
    db = _db(tmp_path)
    a = db.add_outbox("c-a", 99, "A", "2026-01-01T00:00:00+00:00")
    b = db.add_outbox("c-b", 99, "B", "2026-01-01T00:00:01+00:00")
    c = db.add_outbox("c-c", 99, "C", "2026-01-01T00:00:02+00:00")

    client = RecordingClient({cid: _running(cid) for cid in ("c-a", "c-b", "c-c")})
    asyncio.run(deliver_outbox(client, db, Bot(), b))

    assert client.sent == [("c-b", "B")]
    assert db.get_outbox(b).status == "sent"
    assert db.get_outbox(a).status == "pending"
    assert db.get_outbox(c).status == "pending"
    assert db.count_outbox("pending") == 2
