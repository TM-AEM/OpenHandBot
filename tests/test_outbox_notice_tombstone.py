"""OHB2-RESIDUAL: إشعارات مسار الإرسال ما توصلش لشات أخد شاهد حذف أثناء التحضير.

المسار: `_post_claimed` بيقرأ الشات/بيشغّل الـ sandbox (نداءات فيها `await`). لو الـ sandbox
مش جاهز، المسار بيبعت **إشعارًا للمستخدم** (`_SANDBOX_NOT_READY_NOTICE` عند أول محاولة،
`_OUTBOX_EXHAUSTED_NOTICE` عند استنفاد الحد). لو الحذف اتخلّل خلال التحضير (شاهد اتكتب بعد
حرس المدخل)، قبل الإصلاح كان الإشعار يتبعت لشات **اتحذف**.

الإصلاح: حرس شاهد (fail-closed) قبل كل إرسال إشعار مستخدم في المسار ده — فشل قراءة الشاهد
⇒ تخطّي الإرسال. النصوص نفسها خالية من المحتوى (مفيش إفصاح محتوى)، فالتصنيف LOW، لكن
الاتساق مع فرض F-1 (مفيش تفاعل مع شات محذوف) يقتضي التخطّي.

قواعد معزولة (tmp_path)، عملاء/بوتات وهمية، لا شبكة ولا تيليجرام.
"""
from __future__ import annotations

import asyncio

from bot import outbox
from bot.db import OUTBOX_CLAIMED, OUTBOX_FAILED, OUTBOX_PENDING, Database
from bot.errors import ApiError

OWNER = 4242
CID = "conv-1"
SECRET = "TOP_SECRET_PROMPT"


def make_db(tmp_path) -> Database:
    return Database(str(tmp_path / "notice.sqlite3"))


def add_pending(db, cid=CID, chat_id=OWNER, text=SECRET):
    return db.add_outbox(cid, chat_id, text, outbox.now_iso())


def claim(db, oid, extra_attempts=0):
    """يحجز السجل فعلاً ('claimed')، ويرفع attempts بمقدار `extra_attempts`، ويرجّع الصف."""
    claimed = db.claim_outbox(outbox.now_iso())
    assert claimed is not None and claimed.id == oid
    for _ in range(extra_attempts):
        db.set_outbox_status(oid, OUTBOX_CLAIMED, outbox.now_iso(), bump=True)
    return db.get_outbox(oid)


class TombstoningClient:
    """عميل وهمي: الشات 'مش جاهز' (sandbox_status=ERROR من غير sandbox_id).

    أول نداء بعيد **بيكتب شاهد الحذف** — يحاكي حذفًا اتخلّل خلال التحضير (بعد حرس المدخل
    وقبل أي إشعار). ما بيعملش أي إرسال محتوى.
    """

    def __init__(self, db, cid=CID, tombstone=True):
        self._db = db
        self._cid = cid
        self._tombstone = tombstone
        self.get_calls: list[list[str]] = []
        self.sent: list[tuple[str, str]] = []

    async def get_conversations(self, ids):
        self.get_calls.append(list(ids))
        if self._tombstone:
            self._db.begin_remote_deletion(self._cid, outbox.now_iso())
        return [{"id": ids[0], "title": "شات", "sandbox_status": "ERROR",
                 "sandbox_id": None, "execution_status": "error"}]

    async def resume_sandbox(self, sandbox_id):  # pragma: no cover - مش بيتنادى هنا
        raise AssertionError("resume_sandbox مش المفروض يتنادى (sandbox_id فاضي)")

    async def send_message(self, conversation_id, text):
        self.sent.append((conversation_id, text))


class RecordingBot:
    def __init__(self):
        self.sent: list[str] = []

    async def send_message(self, chat_id=None, text=None, **kw):
        self.sent.append(text)


def test_first_attempt_notice_suppressed_when_tombstoned_during_prep(tmp_path):
    db = make_db(tmp_path)
    oid = add_pending(db)
    item = claim(db, oid)  # 'claimed'، attempts=0 ⇒ أول محاولة
    client, bot = TombstoningClient(db), RecordingBot()

    asyncio.run(outbox._post_claimed(client, db, bot, item))

    assert client.sent == []            # مفيش إرسال محتوى
    assert bot.sent == []               # مفيش إشعار لشات محذوف
    assert db.get_outbox(oid).status == OUTBOX_PENDING  # محاولة آمنة ⇒ يتعاود لاحقًا


def test_exhausted_notice_suppressed_when_tombstoned_during_prep(tmp_path):
    db = make_db(tmp_path)
    oid = add_pending(db)
    item = claim(db, oid, extra_attempts=outbox.MAX_OUTBOX_ATTEMPTS - 1)
    client, bot = TombstoningClient(db), RecordingBot()

    asyncio.run(outbox._post_claimed(client, db, bot, item))

    assert client.sent == [] and bot.sent == []
    assert db.get_outbox(oid).status == OUTBOX_FAILED  # استنفاد مسجّل، لكن بلا إشعار


class ApiErrorTombstoningClient:
    """عميل وهمي: **بيكتب شاهد الحذف ثم يرمي `ApiError`** من النداء البعيد (شبكة/5xx/مهلة).

    يحاكي المسار الشائع: الحرس عند المدخل عدّى (الشاهد لسه ماكانش موجود)، الشاهد اتكتب
    خلال `await` قراءة الشات، والاستثناء وقع في معالج `except ApiError` — اللي كان قبل
    الإصلاح بيبعت الإشعار لشات محذوف.
    """

    def __init__(self, db, cid=CID, tombstone=True, status_code=503):
        self._db = db
        self._cid = cid
        self._tombstone = tombstone
        self._status_code = status_code
        self.sent: list[tuple[str, str]] = []

    async def get_conversations(self, ids):
        if self._tombstone:
            self._db.begin_remote_deletion(self._cid, outbox.now_iso())
        raise ApiError("network down", self._status_code)

    async def resume_sandbox(self, sandbox_id):  # pragma: no cover - مش بيتنادى هنا
        raise AssertionError("resume_sandbox مش المفروض يتنادى")

    async def send_message(self, conversation_id, text):
        self.sent.append((conversation_id, text))


def test_apierror_first_attempt_notice_suppressed_when_tombstoned(tmp_path):
    """المسار: شاهد اتكتب أثناء النداء البعيد اللي رمى ApiError (محاولة أولى)."""
    db = make_db(tmp_path)
    oid = add_pending(db)
    item = claim(db, oid)  # attempts=0 ⇒ أول محاولة ⇒ إشعار "فشل الإرسال"
    client, bot = ApiErrorTombstoningClient(db), RecordingBot()

    asyncio.run(outbox._post_claimed(client, db, bot, item))

    assert bot.sent == []                                # مفيش إشعار لشات محذوف
    assert db.get_outbox(oid).status == OUTBOX_PENDING   # محاولة آمنة ⇒ يتعاود


def test_apierror_exhausted_notice_suppressed_when_tombstoned(tmp_path):
    """المسار: شاهد اتكتب أثناء النداء البعيد اللي رمى ApiError (استنفاد الحد)."""
    db = make_db(tmp_path)
    oid = add_pending(db)
    item = claim(db, oid, extra_attempts=outbox.MAX_OUTBOX_ATTEMPTS - 1)
    client, bot = ApiErrorTombstoningClient(db), RecordingBot()

    asyncio.run(outbox._post_claimed(client, db, bot, item))

    assert bot.sent == []
    assert db.get_outbox(oid).status == OUTBOX_FAILED


def test_apierror_notice_still_sent_when_no_tombstone(tmp_path):
    """ضبط سالب: من غير شاهد، إشعار فشل الإرسال بيتبعت عادي."""
    db = make_db(tmp_path)
    oid = add_pending(db)
    item = claim(db, oid)
    client, bot = ApiErrorTombstoningClient(db, tombstone=False), RecordingBot()

    asyncio.run(outbox._post_claimed(client, db, bot, item))

    assert len(bot.sent) == 1 and bot.sent[0].startswith("فشل الإرسال:")


def test_sandbox_notice_still_sent_when_no_tombstone(tmp_path):
    """ضبط سالب (المسار السعيد): من غير شاهد، إشعار 'الـ sandbox مش جاهز' بيتبعت عادي."""
    db = make_db(tmp_path)
    oid = add_pending(db)
    item = claim(db, oid)
    client, bot = TombstoningClient(db, tombstone=False), RecordingBot()

    asyncio.run(outbox._post_claimed(client, db, bot, item))

    assert bot.sent == [outbox._SANDBOX_NOT_READY_NOTICE]
