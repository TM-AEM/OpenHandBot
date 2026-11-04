"""OHB2-N10-28C: سلامة تزامن الصندوق وحدود الإلغاء.

بيغطّي: (1) الشطب الذرّي مع تمييز حدّ الإلغاء (discarded / not_confirmed / terminal)،
(2) تخطّي الإرسال لما السجل يتشطب أثناء التحضير (CAS قبل الـ POST)، (3) عدم إحياء سجل
اتشطب عبر عدّاد المحاولات، (4) عدم إرسال نفس السجل مرتين من مسارين، (5) حدّ الإلغاء
في مسار إنشاء الشات.
"""
import asyncio

from bot import outbox
from bot.outbox import OutboxWorker, _post_claimed

from tests.test_outbox import Bot, add_pending, make_db


def _sub(tmp_path, name):
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    return d


# ============================================================ discard_outbox (DB)
def test_discard_outbox_before_send_is_discarded(tmp_path):
    db = make_db(tmp_path)
    oid = add_pending(db)
    assert db.discard_outbox(oid, "t2", "اتشال") == "discarded"
    assert db.get_outbox(oid).status == "discarded"


def test_discard_outbox_claimed_is_discarded(tmp_path):
    db = make_db(tmp_path)
    oid = add_pending(db)
    db.claim_outbox("t")
    assert db.discard_outbox(oid, "t2") == "discarded"
    assert db.get_outbox(oid).status == "discarded"


def test_discard_outbox_after_send_may_have_started_is_not_confirmed(tmp_path):
    for status in ("sending", "unknown"):
        db = make_db(_sub(tmp_path, status))
        oid = add_pending(db)
        db.set_outbox_status(oid, status, "t1")
        assert db.discard_outbox(oid, "t2") == "not_confirmed"
        assert db.get_outbox(oid).status == status  # مفيش تغيير — مفيش ادّعاء إلغاء


def test_discard_outbox_terminal_is_terminal(tmp_path):
    for status in ("sent", "failed", "discarded"):
        db = make_db(_sub(tmp_path, status))
        oid = add_pending(db)
        db.set_outbox_status(oid, status, "t1")
        assert db.discard_outbox(oid, "t2") == "terminal"
        assert db.get_outbox(oid).status == status


def test_discard_outbox_missing_record_is_terminal(tmp_path):
    db = make_db(tmp_path)
    assert db.discard_outbox(999, "t") == "terminal"


def test_discard_creation_job_boundaries(tmp_path):
    db = make_db(tmp_path)
    # pending ⇒ discarded
    jid = db.add_creation_job(99, "o/r", "x", "t")
    assert db.discard_creation_job(jid, "t2") == "discarded"
    # starting (ممكن يكون بدأ) ⇒ not_confirmed
    jid2 = db.add_creation_job(99, "o/r", "x", "t")
    db.set_creation_status(jid2, "starting", "t1")
    assert db.discard_creation_job(jid2, "t2") == "not_confirmed"
    assert db.get_creation_job(jid2).status == "starting"
    # done (نهائي) ⇒ terminal
    jid3 = db.add_creation_job(99, "o/r", "x", "t")
    db.set_creation_status(jid3, "done", "t1")
    assert db.discard_creation_job(jid3, "t2") == "terminal"


# ============================================ لا إحياء لسجل مش مملوك (bump CAS)
def test_bump_outbox_attempt_does_not_resurrect_a_discarded_record(tmp_path):
    db = make_db(tmp_path)
    oid = add_pending(db)
    db.set_outbox_status(oid, "discarded", "t1")
    assert db.bump_outbox_attempt(oid, "t2", "سبب") == 0  # مش 'claimed' ⇒ مفيش لمس
    assert db.get_outbox(oid).status == "discarded"  # الحالة النهائية محفوظة


def test_bump_outbox_attempt_requires_claimed(tmp_path):
    db = make_db(tmp_path)
    oid = add_pending(db)
    # 'pending' لسه ما اتحجزش ⇒ مفيش لمس (بيحجز الـ worker أولاً).
    assert db.bump_outbox_attempt(oid, "t", "سبب") == 0
    db.claim_outbox("t")
    assert db.bump_outbox_attempt(oid, "t", "سبب") == 1


# ==================================== تخطّي الإرسال لما السجل يتشطب أثناء التحضير
class _CancelDuringPrepClient:
    """يشطب السجل (من «مستخدم تاني») أثناء قراءة الشات، ثم يرجّع sandbox جاهز.

    الـ CAS قبل الـ POST (`claimed`⇒`sending`) لازم يفشل ⇒ مفيش إرسال خالص.
    """

    def __init__(self, db, oid):
        self._db = db
        self._oid = oid
        self.sends = []

    async def get_conversations(self, ids):
        self._db.discard_outbox(self._oid, "t2", "اتشال في الأثناء")
        return [{"id": "c1", "title": "شات", "sandbox_status": "RUNNING"}]

    async def send_message(self, conversation_id, text):
        self.sends.append((conversation_id, text))


def test_discard_during_prep_prevents_post(tmp_path):
    db = make_db(tmp_path)
    oid = add_pending(db)
    db.claim_outbox("t")  # الـ worker حجزه
    item = db.get_outbox(oid)
    client = _CancelDuringPrepClient(db, oid)

    asyncio.run(_post_claimed(client, db, Bot(), item))

    assert client.sends == []                      # مفيش POST بعد الإلغاء
    assert db.get_outbox(oid).status == "discarded"  # الإلغاء محفوظ، مفيش 'sending'


def test_deliver_outbox_claims_atomically_then_posts(tmp_path):
    # المسار المباشر بيحجز ذرّياً ثم يرسل عبر _post_claimed (بدل read-then-write).
    from tests.test_outbox import Client

    db = make_db(tmp_path)
    oid = add_pending(db)
    client = Client()
    asyncio.run(outbox.deliver_outbox(client, db, Bot(), oid))
    assert client.sent == [("c1", "برومت")]
    assert db.get_outbox(oid).status == "sent"


# ================================== مساران ما يرسلوش نفس السجل مرتين (حجز ذرّي)
def test_two_outbox_workers_cannot_send_same_record_twice(tmp_path):
    from tests.test_outbox import Client

    db = make_db(tmp_path)
    add_pending(db)
    client = Client()
    w1 = OutboxWorker(client, db, Bot())
    w2 = OutboxWorker(client, db, Bot())

    async def scenario():
        await asyncio.gather(w1._tick(), w2._tick())

    asyncio.run(scenario())
    assert len(client.sent) == 1  # الحجز الذرّي: إرسال واحد بس


# ============================================ CAS على حالات التسوية اليدوية
def test_set_outbox_status_if_in_cannot_resurrect_discarded(tmp_path):
    db = make_db(tmp_path)
    oid = add_pending(db)
    db.set_outbox_status(oid, "discarded", "t1")
    # محاولة تعليمه sent من 'sending' (حالة مش مسموحة) ⇒ مفيش تغيير.
    assert db.set_outbox_status_if_in(oid, "sent", "t2", {"sending"}) is False
    assert db.get_outbox(oid).status == "discarded"


def test_finish_creation_done_cannot_clobber_discard(tmp_path):
    db = make_db(tmp_path)
    jid = db.add_creation_job(99, "o/r", "x", "t")
    db.set_creation_status(jid, "starting", "t1")
    db.set_creation_status(jid, "discarded", "t2")
    # محاولة تعليمه done من (claimed/starting) ⇒ مفيش تغيير (اتشطب أحدث).
    assert db.finish_creation_done(jid, "t3", "conv-1") is False
    assert db.get_creation_job(jid).status == "discarded"


def test_claim_creation_starting_fails_after_discard(tmp_path):
    db = make_db(tmp_path)
    jid = db.add_creation_job(99, "o/r", "x", "t")
    db.claim_creation_job("t")
    db.discard_creation_job(jid, "t2")  # المستخدم شطب بين الحجز والـ POST
    assert db.claim_creation_starting(jid, "t3") is False  # ⇒ مفيش POST
    assert db.get_creation_job(jid).status == "discarded"


def test_claim_creation_starting_succeeds_for_pending_and_claimed(tmp_path):
    db = make_db(tmp_path)
    # pending (المسار المتزامن المباشر)
    a = db.add_creation_job(99, "o/r", "a", "t")
    assert db.claim_creation_starting(a, "t2") is True
    assert db.get_creation_job(a).status == "starting"
    # claimed (الـ worker)
    b = db.add_creation_job(99, "o/r", "b", "t")
    db.claim_creation_job("t2")
    assert db.claim_creation_starting(b, "t3", task_id="task-9") is True
    assert db.get_creation_job(b).task_id == "task-9"


# ============================ تكامل: شطب أثناء التحضير يمنع POST (creation)
def test_creation_discard_before_post_prevents_start(tmp_path):
    from tests.test_creation import CreationClient, add_job, make_worker

    db = make_db(tmp_path)
    jid = add_job(db)
    client = CreationClient()
    worker = make_worker(db, client)

    # نحاكي مستخدم شطب الطلب بين الحجز والـ POST: CAS (claim_creation_starting)
    # لازم يفشل ⇒ ما نناديش start_conversation خالص (at-most-once).
    real_claim = db.claim_creation_starting

    def claim_after_discard(job_id, now, task_id=None):
        db.discard_creation_job(job_id, now)
        return real_claim(job_id, now, task_id)

    db.claim_creation_starting = claim_after_discard  # type: ignore[assignment]
    asyncio.run(worker._tick())
    assert client.start_calls == 0  # مفيش POST خالص
    assert db.get_creation_job(jid).status == "discarded"
