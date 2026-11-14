"""OHB2-C7-RESURRECTION-FIX: منع إحياء شات محذوف عبر سباق الإكمال المتأخّر.

الباگ الأصلي: طلب OpenHands في حالة 'sending'، المستخدم يحذف الشات، الـ POST الخارجي
ينجح بعد الحذف، ثم مسار 'sending→sent' **ينشئ** صف completion_pending **بعد** الحذف،
فيتخطّى حرس «get_completion_pending is None» ويُحيي الشات (add_watched) وقد يبعت إشعارًا.

الاختبارات هنا:
1) السباق الكامل: sending → delete → نجاح خارجي → finalize → verify مفيش إحياء/إشعار/إعادة POST.
2) مسار الإكمال: intent اتسجّل قبل الحذف، ثم worker بعد الحذف ⇒ مفيش إحياء.
3) إعادة التفاعل الصريح (watch/prompt) بتشيل الشاهد وتبدأ دورة نظيفة.
4) التزامن على اتصالين + إعادة تشغيل + callbacks مكرّرة + حجز worker بايت.

كله بعملاء وهميين وقواعد معزولة (مفيش أي اتصال بتليجرام/OpenHands/GitHub).
"""
from __future__ import annotations

import asyncio
import os

from bot import outbox
from bot.db import (
    COMPLETION_KIND_CREATION,
    COMPLETION_KIND_OUTBOX,
    CREATION_STARTING,
    CREATION_UNKNOWN,
    OUTBOX_SENDING,
    OUTBOX_SENT,
    OUTBOX_UNKNOWN,
    Database,
)

OWNER = 555
CID = "c1"


def _db(tmp_path) -> Database:
    return Database(os.path.join(str(tmp_path), "res.sqlite3"))


class _RecordingBot:
    """بوت وهمي يسجّل كل إشعار — لازم يفضل فاضي بعد الحذف."""

    def __init__(self):
        self.sent: list[str] = []

    async def send_message(self, chat_id=None, text=None, **kw):
        self.sent.append(text)


class _ControlledClient:
    """عميل وهمي: شات RUNNING + عدّاد POST + barrier (Event) للتحكم في لحظة النجاح."""

    def __init__(self):
        self.send_calls = 0
        self.post_started = asyncio.Event()
        self.release = asyncio.Event()

    async def get_conversations(self, ids):
        return [{"id": CID, "title": "شات", "sandbox_status": "RUNNING"}]

    async def send_message(self, conversation_id, text):
        self.send_calls += 1
        self.post_started.set()
        await self.release.wait()  # نوقف بعد ما دخلنا حالة in-flight (بعد CAS sending)


# ============================================================ 1) السباق الكامل
def test_inflight_sending_delete_then_success_does_not_resurrect(tmp_path):
    """التكرار الحرفي للباگ: sending → delete → نجاح → finalize ⇒ مفيش إحياء/إشعار/POST تاني."""
    db = _db(tmp_path)
    now = outbox.now_iso()
    db.add_watched(CID, "شات", chat_id=OWNER)
    oid = db.add_outbox(CID, OWNER, "برومت", now)
    claimed = db.claim_outbox(now)
    assert claimed is not None and claimed.id == oid

    client = _ControlledClient()
    bot = _RecordingBot()

    async def scenario():
        # نبدأ الـ POST (يوصل 'sending' ثم يقف عند الـ barrier).
        task = asyncio.create_task(outbox._post_claimed(client, db, bot, claimed))
        await client.post_started.wait()
        assert db.get_outbox(oid).status == OUTBOX_SENDING  # in-flight فعلًا

        # المستخدم يحذف الشات أثناء in-flight.
        db.delete_conversation(CID, now)
        assert db.get_watched(CID) is None
        assert db.is_deleted(CID) is True

        # الـ POST الخارجي ينجح بعد الحذف.
        client.release.set()
        await task

    asyncio.run(scenario())

    # الأثر الخارجي: الـ POST تم فعلًا (خارجيًا ناجح) — لكن مفيش إحياء محلي.
    assert client.send_calls == 1  # مفيش إعادة POST تانية
    assert db.get_outbox(oid).status == OUTBOX_SENT  # الحالة النهائية اتثبتت (تم خارجيًا)
    assert db.get_completion_pending(COMPLETION_KIND_OUTBOX, oid) is None  # مفيش عمل إكمال
    assert db.get_watched(CID) is None  # مفيش إحياء
    assert bot.sent == []  # مفيش إشعار قديم
    assert db.is_deleted(CID) is True  # الشاهد لسه موجود


def test_inflight_completion_worker_after_delete_does_not_resurrect(tmp_path):
    """intent اتسجّل قبل الحذف، ثم الـ worker يشتغل بعد الحذف ⇒ مفيش إحياء/إشعار."""
    db = _db(tmp_path)
    now = outbox.now_iso()
    db.add_watched(CID, "شات", chat_id=OWNER)
    oid = db.add_outbox(CID, OWNER, "برومت", now)
    db.set_outbox_status(oid, OUTBOX_SENDING, now)
    # finalize ناجح **قبل** الحذف ⇒ intent موجود.
    assert db.complete_outbox_sent(
        oid, now, chat_id=OWNER, conversation_id=CID, title="شات",
        last_state="running", notice_text="n",
    ) is True
    item = db.get_completion_pending(COMPLETION_KIND_OUTBOX, oid)
    assert item is not None

    # الحذف بعده (بيشيل intent في نفس المعاملة).
    db.delete_conversation(CID, now)
    assert db.get_completion_pending(COMPLETION_KIND_OUTBOX, oid) is None

    bot = _RecordingBot()
    asyncio.run(outbox._complete_outbox(db, bot, item))
    assert bot.sent == []
    assert db.get_watched(CID) is None


# ============================================================ 2) إعادة التفاعل الصريح
def test_explicit_reengagement_watch_clears_tombstone(tmp_path):
    """المستخدم يعيد المتابعة صريح ⇒ الشاهد يتشال ويبدأ من جديد."""
    db = _db(tmp_path)
    now = outbox.now_iso()
    db.add_watched(CID, "شات", chat_id=OWNER)
    db.delete_conversation(CID, now)
    assert db.is_deleted(CID) is True

    # مسار غير صريح (worker) ⇒ مرفوض (مفيش إحياء).
    db.add_watched(CID, "شات", chat_id=OWNER)
    assert db.get_watched(CID) is None and db.is_deleted(CID) is True

    # مسار صريح (المستخدم ضغط متابعة) ⇒ يشيل الشاهد ويضيف.
    db.add_watched(CID, "شات", chat_id=OWNER, new_lifecycle=False, reengage=True)
    assert db.get_watched(CID) is not None and db.is_deleted(CID) is False


def test_explicit_reengagement_prompt_clears_tombstone(tmp_path):
    """المستخدم يبعت برومت صريح ⇒ الشاهد يتشال والطلب يتسجّل؛ وغير الصريح يُرفض."""
    db = _db(tmp_path)
    now = outbox.now_iso()
    db.delete_conversation(CID, now)

    # غير صريح ⇒ مرفوض (0 = مفيش سجل).
    assert db.add_or_group_outbox(CID, OWNER, "نص", now) == 0
    # صريح ⇒ يشيل الشاهد ويسجّل.
    oid = db.add_or_group_outbox(CID, OWNER, "نص", now, reengage=True)
    assert oid > 0 and db.is_deleted(CID) is False


# ============================================================ 3) التزامن / إعادة التشغيل
def test_tombstone_survives_restart(tmp_path):
    """الشاهد دائم: بعد إعادة تشغيل القاعدة، الإحياء لسه ممنوع."""
    path = os.path.join(str(tmp_path), "restart.sqlite3")
    db = Database(path)
    now = outbox.now_iso()
    db.add_watched(CID, "شات", chat_id=OWNER)
    db.delete_conversation(CID, now)
    db.close()

    db2 = Database(path)  # "restart"
    assert db2.is_deleted(CID) is True
    db2.add_watched(CID, "شات", chat_id=OWNER)
    assert db2.get_watched(CID) is None  # مفيش إحياء بعد إعادة التشغيل


def test_two_connections_delete_commits_then_late_finalize_blocked(tmp_path):
    """اتصالين منفصلين: الحذف يعمل commit، ثم finalize متأخّر على الاتصال التاني يُمنع."""
    path = os.path.join(str(tmp_path), "two.sqlite3")
    a = Database(path)
    b = Database(path)
    now = outbox.now_iso()
    a.add_watched(CID, "شات", chat_id=OWNER)
    oid = a.add_outbox(CID, OWNER, "برومت", now)
    a.set_outbox_status(oid, OUTBOX_SENDING, now)

    # اتصال A يحذف (commit).
    a.delete_conversation(CID, now)
    # اتصال B (متأخّر) يحاول يثبّت 'sent' + intent ⇒ الحالة النهائية تثبت، الـ intent يُمنع.
    assert b.complete_outbox_sent(
        oid, now, chat_id=OWNER, conversation_id=CID, title="شات", notice_text="n"
    ) is True
    assert b.get_completion_pending(COMPLETION_KIND_OUTBOX, oid) is None
    assert b.get_watched(CID) is None
    assert b.is_deleted(CID) is True
    a.close()
    b.close()


def test_duplicate_completion_callback_no_resurrect(tmp_path):
    """callback مكرّر لـ completion (بعد الحذف) ⇒ idempotent، مفيش إحياء."""
    db = _db(tmp_path)
    now = outbox.now_iso()
    db.add_watched(CID, "شات", chat_id=OWNER)
    db.add_completion_pending(
        COMPLETION_KIND_OUTBOX, 7, OWNER, CID, now, title="T", notice_text="n"
    )
    item = db.get_completion_pending(COMPLETION_KIND_OUTBOX, 7)
    db.delete_conversation(CID, now)
    bot = _RecordingBot()
    # نعمل الإكمال مرتين بنفس العنصر القديم (callback مكرّر).
    asyncio.run(outbox._complete_outbox(db, bot, item))
    asyncio.run(outbox._complete_outbox(db, bot, item))
    assert bot.sent == []
    assert db.get_watched(CID) is None


def test_stale_worker_claim_after_delete_blocked(tmp_path):
    """worker حجز عنصر إكمال (claim) ثم الحذف ⇒ الـ claim ما يحييش."""
    db = _db(tmp_path)
    now = outbox.now_iso()
    db.add_watched(CID, "شات", chat_id=OWNER)
    oid = db.add_outbox(CID, OWNER, "برومت", now)
    db.set_outbox_status(oid, OUTBOX_SENDING, now)
    db.complete_outbox_sent(oid, now, chat_id=OWNER, conversation_id=CID, title="شات")
    # worker يحجز العنصر (lease).
    claimed = db.claim_completion_due(now, now)
    assert claimed is not None
    # الحذف بعده (يشيل intent).
    db.delete_conversation(CID, now)
    bot = _RecordingBot()
    asyncio.run(outbox._complete_outbox(db, bot, claimed))
    assert bot.sent == []
    assert db.get_watched(CID) is None


def test_creation_completion_blocked_when_tombstoned(tmp_path):
    """نفس الحماية على مسار إنشاء الشات: done + intent، حذف، ثم worker ⇒ مفيش إحياء."""
    db = _db(tmp_path)
    now = outbox.now_iso()
    jid = db.add_creation_job(OWNER, "o/r", "نص", now)
    db.set_creation_status(jid, CREATION_STARTING, now)
    assert db.complete_creation_done(
        jid, now, CID, chat_id=OWNER, title="o/r", notice_text="n"
    ) is True
    item = db.get_completion_pending(COMPLETION_KIND_CREATION, jid)
    assert item is not None
    db.delete_conversation(CID, now)
    bot = _RecordingBot()
    asyncio.run(outbox._complete_creation(db, bot, item))
    assert bot.sent == []
    assert db.get_watched(CID) is None


def test_reconcile_legacy_refuses_tombstoned(tmp_path):
    """التسوية اليدوية القديمة ما بتعملش intent لشات متشاهد حذف."""
    db = _db(tmp_path)
    now = outbox.now_iso()
    oid = db.add_outbox(CID, OWNER, "برومت", now)
    db.set_outbox_status(oid, OUTBOX_SENT, now)  # صف 'sent' قديم من غير intent
    db.delete_conversation(CID, now)
    assert db.reconcile_legacy_completion(COMPLETION_KIND_OUTBOX, oid, now) is False
    assert db.get_completion_pending(COMPLETION_KIND_OUTBOX, oid) is None


def test_inbox_event_blocked_for_deleted_conversation(tmp_path):
    """مفيش حدث إشعار جديد لشات محذوف (منع إشعار قديم)."""
    db = _db(tmp_path)
    now = outbox.now_iso()
    db.delete_conversation(CID, now)
    assert db.add_inbox_item(CID, "شات", "k", "msg", now) is None


def test_add_completion_pending_blocked_when_tombstoned(tmp_path):
    """المسار المستقل add_completion_pending مايعملش intent لشات متشاهد."""
    db = _db(tmp_path)
    now = outbox.now_iso()
    db.delete_conversation(CID, now)
    db.add_completion_pending(COMPLETION_KIND_OUTBOX, 3, OWNER, CID, now, title="T")
    assert db.get_completion_pending(COMPLETION_KIND_OUTBOX, 3) is None


def test_notification_state_and_transition_blocked_when_tombstoned(tmp_path):
    """المُبلّل/المراقب مايعملوش/يحدّثوش لقطة إشعار أو انتقال لشات محذوف."""
    db = _db(tmp_path)
    now = outbox.now_iso()
    db.delete_conversation(CID, now)
    db.upsert_notification_state(CID, status="finished", notified_status="finished", updated_at=now)
    assert db.get_notification_state(CID) is None
    assert db.note_transition(CID, "finished", terminal=True, now=now) == 0
    assert db.get_notification_state(CID) is None


def test_reengagement_then_completion_works(tmp_path):
    """بعد إعادة تفاعل صريح، الإكمال يشتغل عادي (الشاهد اتشال ⇒ مفيش منع دائم)."""
    db = _db(tmp_path)
    now = outbox.now_iso()
    db.add_watched(CID, "شات", chat_id=OWNER)
    db.add_outbox(CID, OWNER, "برومت", now)
    db.delete_conversation(CID, now)
    # إعادة تفاعل صريح (برومت جديد).
    oid2 = db.add_or_group_outbox(CID, OWNER, "برومت تاني", now, reengage=True)
    assert oid2 > 0 and db.is_deleted(CID) is False
    db.set_outbox_status(oid2, OUTBOX_SENDING, now)
    assert db.complete_outbox_sent(
        oid2, now, chat_id=OWNER, conversation_id=CID, title="شات", notice_text="n"
    ) is True
    assert db.get_completion_pending(COMPLETION_KIND_OUTBOX, oid2) is not None


# ============================================================ 4) المُبلّل الاستباقي
class _SearchClient:
    def __init__(self, items):
        self._items = items

    async def search_conversations(self, limit=20, page_id=None):
        return {"items": self._items, "next_page_id": None}


class _NotifyBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id=None, text=None, parse_mode=None, **kw):
        self.sent.append(text)

    async def send_document(self, chat_id=None, document=None, **kw):
        self.sent.append("DOC")


def test_notifier_skips_locally_deleted_conversation(tmp_path):
    """شات اتحذف محليًا لكن لسه ظاهر في البحث البعيد ⇒ المُبلّل ما يبعتش إشعار 'جديد' له."""
    from bot.notifier import Notifier

    db = _db(tmp_path)
    now = outbox.now_iso()
    db.add_watched(CID, "شات", chat_id=OWNER)
    db.delete_conversation(CID, now)  # شال لقطة الإشعار + المتابعة، وكتب الشاهد
    assert db.is_deleted(CID) is True
    assert db.get_notification_state(CID) is None

    bot = _NotifyBot()
    client = _SearchClient([{"id": CID, "title": "شات", "execution_status": "finished"}])
    n = Notifier(client, db, bot, chat_id=OWNER, base_url="https://app.all-hands.dev")
    asyncio.run(n.tick())
    assert bot.sent == []  # مفيش إشعار لشات محذوف
    assert db.get_notification_state(CID) is None  # مفيش لقطة اتخلقت


# ============================================ 5) F1: حرس إشعارات التعافي بعد الحذف
class _RecoveryApp:
    """تطبيق مصغّر لتعافي الإقلاع (نفس شكل `SimpleNamespace(bot_data, bot)`)."""

    def __init__(self, db, bot=None, client=None):
        self.bot_data = {"db": db, "client": client}
        self.bot = bot or _RecordingBot()


def test_outbox_recover_suppresses_notice_for_deleted_but_keeps_unknown(tmp_path):
    """F1: صف 'sending' لشات محذوف ⇒ الحالة تتحوّل 'unknown' (تعافي لازم)، لكن مفيش إشعار."""
    db = _db(tmp_path)
    now = outbox.now_iso()
    db.add_watched(CID, "شات", chat_id=OWNER)
    oid = db.add_outbox(CID, OWNER, "برومت", now)
    db.set_outbox_status(oid, OUTBOX_SENDING, now)
    db.delete_conversation(CID, now)  # بيشيل المتابعة + يكتب الشاهد (بيسيب صف 'sending')

    bot = _RecordingBot()
    asyncio.run(outbox.outbox_recover(_RecoveryApp(db, bot=bot)))

    assert db.get_outbox(oid).status == OUTBOX_UNKNOWN  # التعافي لازم اتّم
    assert bot.sent == []  # مفيش إشعار لشات ملغي
    assert db.get_watched(CID) is None  # مفيش إحياء
    assert db.get_completion_pending(COMPLETION_KIND_OUTBOX, oid) is None  # مفيش intent
    assert db.is_deleted(CID) is True  # الشاهد لسه موجود


def test_outbox_recover_notifies_active_conversation(tmp_path):
    """F1: صف 'sending' لشات نشِط ⇒ نفس سلوك التعافي والإشعار الأصلي."""
    db = _db(tmp_path)
    now = outbox.now_iso()
    oid = db.add_outbox(CID, OWNER, "برومت", now)
    db.set_outbox_status(oid, OUTBOX_SENDING, now)

    bot = _RecordingBot()
    asyncio.run(outbox.outbox_recover(_RecoveryApp(db, bot=bot)))

    assert db.get_outbox(oid).status == OUTBOX_UNKNOWN
    assert any("مش متأكدين" in s for s in bot.sent)  # الإشعار الأصلي اتّبعت
    assert db.is_deleted(CID) is False


def test_creation_recover_suppresses_notice_for_deleted_but_keeps_unknown(tmp_path):
    """F1: طلب 'starting' بلا task_id لشات محذوف ⇒ 'unknown' (تعافي لازم) بدون إشعار."""
    db = _db(tmp_path)
    now = outbox.now_iso()
    jid = db.add_creation_job(OWNER, "o/r", "نص", now)
    db.set_creation_status(jid, CREATION_STARTING, now)  # POST بدأ، task_id مجهول
    # نربط الطلب بالشات (حالة حدّية: طلب 'starting' بيحمل conversation_id).
    db._conn.execute("UPDATE creation_jobs SET conversation_id=? WHERE id=?", (CID, jid))
    db._conn.commit()
    db.delete_conversation(CID, now)

    bot = _RecordingBot()
    asyncio.run(outbox.creation_recover(_RecoveryApp(db, bot=bot)))

    assert db.get_creation_job(jid).status == CREATION_UNKNOWN  # التعافي لازم اتّم
    assert bot.sent == []  # مفيش إشعار لشات ملغي
    assert db.get_watched(CID) is None  # مفيش إحياء
    assert db.get_completion_pending(COMPLETION_KIND_CREATION, jid) is None
    assert db.is_deleted(CID) is True


def test_creation_recover_notifies_active_conversation(tmp_path):
    """F1: طلب 'starting' بلا task_id لشات نشِط ⇒ نفس سلوك التعافي والإشعار الأصلي."""
    db = _db(tmp_path)
    now = outbox.now_iso()
    jid = db.add_creation_job(OWNER, "o/r", "نص", now)
    db.set_creation_status(jid, CREATION_STARTING, now)

    bot = _RecordingBot()
    asyncio.run(outbox.creation_recover(_RecoveryApp(db, bot=bot)))

    assert db.get_creation_job(jid).status == CREATION_UNKNOWN
    assert len(bot.sent) == 1  # إشعار «مش قادرين نتأكد» الأصلي


def test_recovery_repeated_restart_no_delayed_stale_notice(tmp_path):
    """F1: إعادة تشغيل متكرّرة ⇒ الشاهد دائم، ومفيش إشعار قديم متأخّر ولا إعادة POST."""
    path = os.path.join(str(tmp_path), "restart.sqlite3")
    db = Database(path)
    now = outbox.now_iso()
    oid = db.add_outbox(CID, OWNER, "برومت", now)
    db.set_outbox_status(oid, OUTBOX_SENDING, now)
    db.delete_conversation(CID, now)
    db.close()

    bot = _RecordingBot()
    for _ in range(3):  # 3 «إعادات تشغيل»
        db2 = Database(path)
        asyncio.run(outbox.outbox_recover(_RecoveryApp(db2, bot=bot)))
        assert db2.get_outbox(oid).status == OUTBOX_UNKNOWN
        assert db2.is_deleted(CID) is True  # الشاهد دائم عبر كل إعادة تشغيل
        db2.close()

    assert bot.sent == []  # مفيش إشعار متأخّر ولا مكرّر


def test_outbox_recover_concurrent_delete_no_new_notice_but_inflight_may_arrive(tmp_path):
    """E-1: الحذف يتخلّل عند نقطة الـ await أثناء إشعار التعافي.

    السلوك الحقيقي (مش «مفيش إشعار»): `outbox_recover` بيفحص الشاهد (`is_deleted`) **مرة
    واحدة قبل** `await safe_send`. فالإشعار اللي **بدأ قبل** الحذف بيكمّل (إشعار «طاير» —
    residual مقبول وموثّق)، بينما أي صف يتعالج **بعد** كتابة الشاهد لازم يتخطّى بلا إشعار.
    بنسجّل لحظة بدء كل إرسال وهل الشات كان محذوف ساعتها، عشان نفرّق الإشعار «الطاير» من
    إشعار جديد للشات الملغي. الاختبار بيفشل لو التعافي ابتدأ إشعار جديد بعد الحذف.
    """
    db = _db(tmp_path)
    now = outbox.now_iso()
    first = db.add_outbox(CID, OWNER, "برومت", now)        # يتعالج قبل الحذف
    second = db.add_outbox(CID, OWNER, "برومت تاني", now)  # يتعالج بعد الحذف
    db.set_outbox_status(first, OUTBOX_SENDING, now)
    db.set_outbox_status(second, OUTBOX_SENDING, now)

    entered = asyncio.Event()
    release = asyncio.Event()

    class _InFlightRecordingBot:
        """بوت وهمي يسجّل (نص الإشعار، هل الشات محذوف **لحظة بدء الإرسال**).

        التسجيل لحظة الدخول بيفرّق حالتين: إشعار بدأ قبل الحذف (is_deleted=False ⇒ «طاير»،
        مسموح) عن إشعار ابتدأه التعافي **بعد** الحذف (is_deleted=True ⇒ ممنوع).
        """

        def __init__(self):
            self.events: list[tuple[str, bool]] = []

        async def send_message(self, chat_id=None, text=None, **kw):
            self.events.append((text, db.is_deleted(CID)))
            entered.set()
            await release.wait()

    bot = _InFlightRecordingBot()

    async def scenario():
        task = asyncio.create_task(outbox.outbox_recover(_RecoveryApp(db, bot=bot)))
        await entered.wait()  # أول إشعار بدأ (بعد فحص الشاهد = لسه غير محذوف)
        db.delete_conversation(CID, now)  # الحذف يتخلّل عند نقطة الـ await
        release.set()
        await task

    asyncio.run(scenario())

    # إشعار واحد بس، وابتدأ **قبل** الحذف ⇒ إشعار «طاير» مسموح (الـ residual الموثّق).
    assert len(bot.events) == 1
    text, deleted_at_start = bot.events[0]
    assert deleted_at_start is False  # بدأ والشات لسه مش محذوف
    assert "مش متأكدين" in text  # إشعار التعافي الأصلي
    # التعافي **ماابتدأش** أي إشعار بعد كتابة الشاهد (مفيش إشعار جديد للصف التاني الملغي).
    assert all(is_deleted is False for _, is_deleted in bot.events)
    # التعافي اتمّ للصفّين: الاتنين unknown (الحالة بتتحوّل حتى للشات الملغي).
    assert db.get_outbox(first).status == OUTBOX_UNKNOWN
    assert db.get_outbox(second).status == OUTBOX_UNKNOWN
    # مفيش إحياء، الشاهد لسه موجود، ومفيش intent جديد.
    assert db.get_watched(CID) is None
    assert db.is_deleted(CID) is True
    assert db.get_completion_pending(COMPLETION_KIND_OUTBOX, first) is None


# ================================ 6) OHB2-AUDIT-FIX-01: سباق برومت الـ Mini App
def test_miniapp_ref_prompt_cannot_resurrect_tombstoned(tmp_path):
    """عمليات الـ Mini App (بحمل `client_ref`) مستحيل تحيي شات متشاهد.

    ده الـ race الحقيقي: الـ POST بدأ قبل الحذف وخلص بعده (await شبكة). الـ client_ref
    كان بيشيل الشاهد الأول قبل فحص الـ idempotency ⇒ إحياء. دلوقتي مرفوض بلا أثر.
    """
    db = _db(tmp_path)
    now = outbox.now_iso()
    db.add_watched(CID, "شات", chat_id=OWNER)
    db.delete_conversation(CID, now)
    assert db.is_deleted(CID) is True

    # نفس العملية (client_ref) بحمل/بدون reengage ⇒ مرفوضة دايمًا، بلا أي كتابة.
    assert db.add_or_group_outbox(CID, OWNER, "نص", now, client_ref="r1") == 0
    assert db.add_or_group_outbox(CID, OWNER, "نص", now, client_ref="r1", reengage=True) == 0
    assert db.is_deleted(CID) is True      # الشاهد ما اتشالش
    assert db.count_outbox() == 0          # مفيش صف صندوق اتخلق
    assert db.get_watched(CID) is None     # مفيش إحياء


def test_client_ref_prompt_on_active_conversation_still_queues(tmp_path):
    """تحكّم موجب: على شات نشِط (مفيش شاهد)، برومت الـ Mini App يشتغل عادي."""
    db = _db(tmp_path)
    now = outbox.now_iso()
    oid = db.add_or_group_outbox(CID, OWNER, "نص", now, client_ref="r1")
    assert oid > 0
    assert db.count_outbox() == 1
    assert db.is_deleted(CID) is False


def test_bot_no_ref_explicit_reengagement_still_clears_tombstone(tmp_path):
    """مسار البوت (من غير client_ref) لسه بيتصرف كإعادة تفاعل صريح (مش مكسور)."""
    db = _db(tmp_path)
    now = outbox.now_iso()
    db.add_watched(CID, "شات", chat_id=OWNER)
    db.delete_conversation(CID, now)
    oid = db.add_or_group_outbox(CID, OWNER, "نص", now, reengage=True)
    assert oid > 0 and db.is_deleted(CID) is False
    # وغير الصريح (retry/recovery) لسه مرفوض.
    db.delete_conversation(CID, now)
    assert db.add_or_group_outbox(CID, OWNER, "نص", now) == 0
    assert db.is_deleted(CID) is True
