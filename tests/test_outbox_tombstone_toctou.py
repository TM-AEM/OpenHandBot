"""OHB2-OUTBOX-TOMBSTONE-TOCTOU: هل يمكن إرسال محتوى شات بعد أخذه شاهد حذف؟

الخطر الحقيقي (مش نافذة TOCTOU ضيّقة): حذف الـ Mini App بيكتب **الشاهد + 'deleting'**
**قبل** النداء البعيد (`deletion.delete_conversation_remote` → `db.begin_remote_deletion`)،
وسجلات الصندوق **ما بتتشطبش** غير في الإنهاء النهائي (`db.delete_conversation`). يعني خلال
نافذة deleting/uncertain السجل يفضل 'pending'/'claimed'، والـ CAS 'claimed'⇒'sending'
بينجح ⇒ كان ممكن يتبعت محتوى شات اتحذف.

الإصلاح: حرس شاهد (fail-closed) في **أول** `_post_claimed` قبل أي نداء بعيد.

هذه الاختبارات تثبت **منع النداء البعيد** و**غياب الإفصاح** (مش الحالة النهائية بس)،
وتوثّق الحدّ الوحيد غير القابل للتغطية: شاهد يُكتب **بعد** ما الإرسال الخارجي بدأ فعلًا.

لا شبكة ولا تليجرام ولا OpenHands حقيقي: عملاء/بوتات وهمية وقواعد معزولة (tmp_path).
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from bot import outbox
from bot.db import (
    OUTBOX_CLAIMED,
    OUTBOX_DISCARDED,
    OUTBOX_PENDING,
    OUTBOX_SENDING,
    OUTBOX_SENT,
    OUTBOX_UNKNOWN,
    Database,
)
from bot.errors import ApiError

OWNER = 4242
OTHER = 9999
CID = "conv-1"
CID2 = "conv-2"
SECRET = "TOP_SECRET_PROMPT"


def make_db(tmp_path) -> Database:
    return Database(str(tmp_path / "toctou.sqlite3"))


def add_pending(db, cid=CID, chat_id=OWNER, text=SECRET):
    return db.add_outbox(cid, chat_id, text, outbox.now_iso())


class RecordingClient:
    """عميل وهمي: يسجّل كل نداء بعيد. أي نداء = إفصاح محتمل."""

    def __init__(self, status="RUNNING"):
        self._status = status
        self.get_calls: list[list[str]] = []
        self.resume_calls: list[str] = []
        self.sent: list[tuple[str, str]] = []

    async def get_conversations(self, ids):
        self.get_calls.append(list(ids))
        return [{"id": ids[0], "title": "شات", "sandbox_status": self._status,
                 "sandbox_id": "sb-1", "execution_status": "running"}]

    async def resume_sandbox(self, sandbox_id):
        self.resume_calls.append(sandbox_id)

    async def send_message(self, conversation_id, text):
        self.sent.append((conversation_id, text))


class RecordingBot:
    def __init__(self):
        self.sent: list[str] = []

    async def send_message(self, chat_id=None, text=None, **kw):
        self.sent.append(text)


def tombstone_in_progress(db, cid=CID):
    """يحاكي حذف الـ Mini App الجاري: شاهد + 'deleting'، وسجلات الصندوق **لسه موجودة**."""
    attempt = db.begin_remote_deletion(cid, outbox.now_iso())
    assert attempt is not None
    assert db.is_deleted(cid) is True


# ---------------------------------------------------------------------------
# (أ) شاهد موجود **قبل** الحجز
# ---------------------------------------------------------------------------
def test_tombstone_before_claim_worker_sends_nothing(tmp_path):
    """حذف جارٍ (deleting) قبل الحجز: الـ worker يحجز السجل لكن مايبعتش — صفر نداء بعيد."""
    db = make_db(tmp_path)
    oid = add_pending(db)
    tombstone_in_progress(db)  # الشاهد اتكتب قبل ما الـ worker يحجز

    client, bot = RecordingClient(), RecordingBot()
    claimed = db.claim_outbox(outbox.now_iso())  # claim_outbox مابيفلترش الشاهد (بحكم التصميم)
    assert claimed is not None and claimed.id == oid
    asyncio.run(outbox._post_claimed(client, db, bot, claimed))

    assert client.get_calls == [] and client.resume_calls == [] and client.sent == []
    assert bot.sent == []
    assert db.get_outbox(oid).status == OUTBOX_DISCARDED  # نهائي، مش 'pending' (مايتعاودش)
    assert SECRET not in str(client.sent)


def test_tombstone_before_claim_worker_tick_sends_nothing(tmp_path):
    """نفس الحالة عبر دورة الـ worker الكاملة (tick) — صفر إفصاح."""
    db = make_db(tmp_path)
    # طابع قديم عشان يستوفي نافذة التجميع فيتحجز فعلًا في الدورة.
    oid = add_pending(db, text=SECRET)
    db.set_outbox_status(oid, OUTBOX_PENDING, "2020-01-01T00:00:00+00:00")
    tombstone_in_progress(db)
    client, bot = RecordingClient(), RecordingBot()
    worker = outbox.OutboxWorker(client, db, bot, poll_interval=0.01, max_idle=0.02)
    asyncio.run(worker._tick())
    assert client.sent == [] and bot.sent == []
    assert db.get_outbox(oid).status == OUTBOX_DISCARDED


# ---------------------------------------------------------------------------
# (ب) شاهد يُكتب **بعد** الحجز وقبل الإرسال
# ---------------------------------------------------------------------------
def test_tombstone_after_claim_before_dispatch_sends_nothing(tmp_path):
    db = make_db(tmp_path)
    oid = add_pending(db)
    claimed = db.claim_outbox(outbox.now_iso())
    assert claimed is not None
    assert db.get_outbox(oid).status == OUTBOX_CLAIMED
    tombstone_in_progress(db)  # الحذف يتخلّل بين الحجز والإرسال

    client, bot = RecordingClient(), RecordingBot()
    asyncio.run(outbox._post_claimed(client, db, bot, claimed))
    assert client.get_calls == [] and client.sent == [] and bot.sent == []
    assert db.get_outbox(oid).status == OUTBOX_DISCARDED


# ---------------------------------------------------------------------------
# (ج) شاهد عند حدّ الفحص النهائي (uncertain) — قبل CAS الإرسال مباشرة
# ---------------------------------------------------------------------------
def test_tombstone_uncertain_at_final_boundary_sends_nothing(tmp_path):
    db = make_db(tmp_path)
    oid = add_pending(db)
    claimed = db.claim_outbox(outbox.now_iso())
    # حذف جارٍ ثم فشل/انقطاع ⇒ 'uncertain' (شاهد فعّال، السجل لسه مؤهّل)
    tombstone_in_progress(db)
    db.set_remote_deletion_state(CID, db.REMOTE_UNCERTAIN, outbox.now_iso())

    client, bot = RecordingClient(), RecordingBot()
    asyncio.run(outbox._post_claimed(client, db, bot, claimed))
    assert client.sent == [] and bot.sent == []
    assert db.get_outbox(oid).status == OUTBOX_DISCARDED


def test_tombstone_via_direct_deliver_outbox_sends_nothing(tmp_path):
    """المسار المباشر `deliver_outbox` (handlers._deliver_outbox) محروس كذلك."""
    db = make_db(tmp_path)
    oid = add_pending(db)
    tombstone_in_progress(db)
    client, bot = RecordingClient(), RecordingBot()
    asyncio.run(outbox.deliver_outbox(client, db, bot, oid))
    assert client.sent == [] and bot.sent == []
    assert db.get_outbox(oid).status == OUTBOX_DISCARDED


# ---------------------------------------------------------------------------
# (د) شاهد يُكتب **بعد** ما الإرسال بدأ (الحدّ غير القابل للتغطية — يُوثَّق بصدق)
# ---------------------------------------------------------------------------
class BlockingClient(RecordingClient):
    """يوقف `send_message` عند حاجز للتحكم في لحظة الإفصاح (in-flight)."""

    def __init__(self):
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def send_message(self, conversation_id, text):
        self.sent.append((conversation_id, text))
        self.started.set()
        await self.release.wait()


def test_tombstone_after_dispatch_began_is_an_unavoidable_inflight_limitation(tmp_path):
    """شاهد يُكتب بعد بدء الإرسال الخارجي ⇒ الإفصاح وقع فعلًا (حدّ خارجي، غير قابل للسحب).

    ده **ليس** سباق قابل للإصلاح محليًا: لحظة بدء الـ POST، المحتوى خرج من نطاق SQLite.
    الاختبار يوثّق الحدّ بصدق: الإرسال يحصل **مرة واحدة** بالظبط، ولا إعادة إرسال تلقائية.
    """
    db = make_db(tmp_path)
    oid = add_pending(db)
    claimed = db.claim_outbox(outbox.now_iso())
    client, bot = BlockingClient(), RecordingBot()

    async def scenario():
        task = asyncio.create_task(outbox._post_claimed(client, db, bot, claimed))
        await client.started.wait()  # الـ POST دخل فعلاً (بعد CAS 'sending')
        assert db.get_outbox(oid).status == OUTBOX_SENDING
        tombstone_in_progress(db)  # الحذف يتخلّل **أثناء** الإرسال
        client.release.set()
        await task

    asyncio.run(scenario())

    # الحدّ: المحتوى اتبعت فعلًا (مرة واحدة) — مفيش طريقة محلية تسحبه.
    assert client.sent == [(CID, SECRET)]
    assert db.get_outbox(oid).status == OUTBOX_SENT  # الحسم استمر (الـ POST تم)
    assert db.get_outbox(oid).attempts == 0  # مفيش إعادة محاولة


# ---------------------------------------------------------------------------
# (هـ) مطالبة قديمة/مسترجَعة (stale claimed) ما تتجاوزش الفحص
# ---------------------------------------------------------------------------
def test_stale_claimed_recovered_then_tombstoned_does_not_bypass(tmp_path):
    """سجل 'claimed' قديم ⇒ التعافي يرجّعه 'pending' ⇒ حجز جديد ⇒ الحرس يمنع الإرسال."""
    db = make_db(tmp_path)
    oid = add_pending(db)
    claimed = db.claim_outbox(outbox.now_iso())
    assert claimed is not None
    tombstone_in_progress(db)

    bot = RecordingBot()
    app = SimpleNamespace(bot_data={"db": db}, bot=bot)
    asyncio.run(outbox.outbox_recover(app))  # claimed ⇒ pending (تعافي restart)
    assert db.get_outbox(oid).status == OUTBOX_PENDING

    client = RecordingClient()
    reclaimed = db.claim_outbox(outbox.now_iso())
    assert reclaimed is not None and reclaimed.id == oid
    asyncio.run(outbox._post_claimed(client, db, bot, reclaimed))
    assert client.sent == [] and bot.sent == []
    assert db.get_outbox(oid).status == OUTBOX_DISCARDED


def test_recovery_of_tombstoned_sending_does_not_notify(tmp_path):
    """'sending' متشاهد عند الإقلاع ⇒ 'unknown' بلا إشعار (مافيهوش إحياء ولا إعادة إرسال)."""
    db = make_db(tmp_path)
    oid = add_pending(db)
    db.set_outbox_status(oid, OUTBOX_SENDING, outbox.now_iso())
    tombstone_in_progress(db)
    bot = RecordingBot()
    app = SimpleNamespace(bot_data={"db": db}, bot=bot)
    asyncio.run(outbox.outbox_recover(app))
    assert db.get_outbox(oid).status == OUTBOX_UNKNOWN
    assert bot.sent == []  # مفيش إشعار لشات ملغي
    assert db.get_outbox(oid).status != OUTBOX_PENDING  # مش مؤهّل لإعادة إرسال


# ---------------------------------------------------------------------------
# (و) الشات السليم لسه بيتبعت (مفيش انحدار)
# ---------------------------------------------------------------------------
def test_healthy_conversation_still_sends(tmp_path):
    db = make_db(tmp_path)
    oid = add_pending(db)
    claimed = db.claim_outbox(outbox.now_iso())
    client, bot = RecordingClient(), RecordingBot()
    asyncio.run(outbox._post_claimed(client, db, bot, claimed))
    assert client.sent == [(CID, SECRET)]
    assert db.get_outbox(oid).status == OUTBOX_SENT
    assert bot.sent  # إشعار النجاح


# ---------------------------------------------------------------------------
# (ز) شات تاني غير متأثّر (عزل)
# ---------------------------------------------------------------------------
def test_tombstoned_conversation_does_not_affect_other(tmp_path):
    db = make_db(tmp_path)
    oid1 = add_pending(db, cid=CID, text="SECRET-ONE")
    oid2 = add_pending(db, cid=CID2, text="OK-TWO")
    tombstone_in_progress(db, cid=CID)  # c1 بس متشاهد

    client, bot = RecordingClient(), RecordingBot()
    first = db.claim_outbox(outbox.now_iso())
    assert first.id == oid1
    asyncio.run(outbox._post_claimed(client, db, bot, first))  # c1 ⇒ مرفوض
    second = db.claim_outbox(outbox.now_iso())
    assert second.id == oid2
    asyncio.run(outbox._post_claimed(client, db, bot, second))  # c2 ⇒ يتبعت

    assert client.sent == [(CID2, "OK-TWO")]
    assert db.get_outbox(oid1).status == OUTBOX_DISCARDED
    assert db.get_outbox(oid2).status == OUTBOX_SENT


# ---------------------------------------------------------------------------
# (ح) الملكية/التفويض كما هي
# ---------------------------------------------------------------------------
def test_ownership_scope_still_enforced(tmp_path):
    """`get_outbox` بنطاق chat_id يفضل يفرض الملكية (الحرس ما أضعفهاش)."""
    db = make_db(tmp_path)
    oid = add_pending(db, chat_id=OWNER)
    assert db.get_outbox(oid, chat_id=OWNER) is not None
    assert db.get_outbox(oid, chat_id=OTHER) is None  # مالك تاني ⇒ مرفوض


def test_tombstoned_item_with_wrong_owner_is_not_claimed(tmp_path):
    """السجل المتشاهد بتاع مالك تاني مايتحجزش من مسار المالك (نطاق chat_id)."""
    db = make_db(tmp_path)
    oid = add_pending(db, chat_id=OWNER)
    tombstone_in_progress(db)
    assert db.get_outbox(oid, chat_id=OTHER) is None
    assert db.get_outbox(oid, chat_id=OWNER) is not None


# ---------------------------------------------------------------------------
# (ط) مفيش إعادة إرسال بعد نتيجة غامضة (at-most-once محفوظ)
# ---------------------------------------------------------------------------
def test_ambiguous_outcome_is_not_resent(tmp_path):
    """رد غامض (5xx) ⇒ 'unknown'، إرسال واحد بس، ومفيش إعادة تلقائية."""
    db = make_db(tmp_path)
    oid = add_pending(db)

    class FlakyClient(RecordingClient):
        async def send_message(self, conversation_id, text):
            self.sent.append((conversation_id, text))
            raise ApiError("boom", status_code=500)

    client, bot = RecordingClient(), RecordingBot()
    flaky = FlakyClient()
    claimed = db.claim_outbox(outbox.now_iso())
    asyncio.run(outbox._post_claimed(flaky, db, bot, claimed))
    assert len(flaky.sent) == 1
    assert db.get_outbox(oid).status == OUTBOX_UNKNOWN

    # محاولة تانية: 'unknown' مش مؤهّل ⇒ مفيش حجز ⇒ مفيش إعادة إرسال.
    assert db.claim_outbox(outbox.now_iso()) is None
    worker = outbox.OutboxWorker(client, db, bot, poll_interval=0.01, max_idle=0.02)
    asyncio.run(worker._tick())
    assert client.sent == []
    assert db.get_outbox(oid).status == OUTBOX_UNKNOWN


# ---------------------------------------------------------------------------
# (ج-2) شاهد يُكتب **أثناء** التحضير (الحالة 3) — بعد حرس المدخل، قبل CAS الإرسال
# ---------------------------------------------------------------------------
class TombstoneDuringPrepClient(RecordingClient):
    """يضع الشاهد أثناء `get_conversations` (نافذة التحضير بعد حرس المدخل)."""

    def __init__(self, db, cid=CID):
        super().__init__()
        self._db = db
        self._cid = cid

    async def get_conversations(self, ids):
        self.get_calls.append(list(ids))
        # الحذف يتخلّل هنا: الشاهد اتكتب **بعد** حرس المدخل وقبل CAS الإرسال.
        self._db.begin_remote_deletion(self._cid, outbox.now_iso())
        return [{"id": ids[0], "title": "شات", "sandbox_status": "RUNNING",
                 "sandbox_id": "sb-1", "execution_status": "running"}]


def test_tombstone_during_prep_window_sends_nothing(tmp_path):
    """شاهد يُكتب أثناء `get_conversations` (نافذة التحضير) ⇒ مفيش إرسال (الحالة 3).

    قبل الحرس الثاني: الحرس الأول عدّى (الشات كان حيّ عند المدخل)، فالإرسال كان بيحصل.
    بعده: الحرس الثاني (فورًا قبل CAS الإرسال، بلا `await` بينهم) بيمنع الإرسال تمامًا.
    """
    db = make_db(tmp_path)
    oid = add_pending(db)
    claimed = db.claim_outbox(outbox.now_iso())
    assert claimed is not None and db.is_deleted(CID) is False

    client, bot = TombstoneDuringPrepClient(db), RecordingBot()
    asyncio.run(outbox._post_claimed(client, db, bot, claimed))

    assert client.get_calls == [[CID]]  # نداء التحضير حصل (GET فقط)
    assert client.sent == []  # لكن مفيش إرسال محتوى خالص
    assert bot.sent == []
    assert SECRET not in str(client.sent)
    assert db.get_outbox(oid).status == OUTBOX_DISCARDED
    assert db.is_deleted(CID) is True


def test_tombstone_during_prep_worker_tick_sends_nothing(tmp_path):
    """نفس الحالة عبر دورة الـ worker الكاملة — صفر إفصاح."""
    db = make_db(tmp_path)
    oid = add_pending(db, text=SECRET)
    db.set_outbox_status(oid, OUTBOX_PENDING, "2020-01-01T00:00:00+00:00")
    client, bot = TombstoneDuringPrepClient(db), RecordingBot()
    worker = outbox.OutboxWorker(client, db, bot, poll_interval=0.01, max_idle=0.02)
    asyncio.run(worker._tick())
    assert client.sent == [] and bot.sent == []
    assert db.get_outbox(oid).status == OUTBOX_DISCARDED
