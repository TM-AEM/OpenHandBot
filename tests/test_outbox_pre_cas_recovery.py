"""OHB2-LOG01-F01: تعافي pre-CAS للاستثناءات غير المتوقّعة + سلامة حدّ الـ CAS.

F-01 (مؤكّد): استثناء غير متوقّع في `_post_claimed` **قبل** CAS `claimed`⇒`sending`
كان بيسيب السجل عالقًا 'claimed' لحد إعادة تشغيل العملية. الإصلاح: مسار تعافي آمن
(OPT-1) بيستخدم نفس `bump_outbox_attempt`/`MAX_OUTBOX_ATTEMPTS`/CAS من 'claimed'.

الحدّ الحاسم: الاستثناءات **قبل** الـ CAS آمنة (الـ POST مابدأش)، وبعد الـ CAS ممنوعة
تمامًا من أي رجوع لـ 'pending' (at-most-once: ممكن الـ POST يكون اتقبل). الاختبارات دي
بتثبّت الحدّ ده: (1) تعافي pre-CAS لـ 'pending'، (2) CAS محروس بالحالة، (3) سياسة
المحاولات، (4) عدم دهس تغيير متوازي، (5) فشل التعافي مايدّعيش نجاحًا، (6) فشل الـ CAS
مايعملش POST، (7) نجاح الـ CAS بينفّذ التسلسل بعد الـ CAS، (8) خطأ بعد الـ CAS مايرجّعش
'sending' لـ 'pending'، (9) مفيش POST تاني بعد احتمال قبول الأول، (10) الإلغاء مايتكتمش،
(11) سلوك ApiError زي ما هو، (12) حماية F-1 سليمة.

قواعد معزولة (tmp_path)، عملاء/بوتات وهمية، لا شبكة ولا تيليجرام.
"""
from __future__ import annotations

import asyncio
import sqlite3

import pytest

from bot import outbox
from bot.db import (
    OUTBOX_CLAIMED,
    OUTBOX_DISCARDED,
    OUTBOX_FAILED,
    OUTBOX_PENDING,
    OUTBOX_SENDING,
    OUTBOX_SENT,
    OUTBOX_UNKNOWN,
    Database,
)
from bot.errors import ApiError
from bot.outbox import _post_claimed

CID = "conv-1"
OWNER = 4242
TEXT = "برومت مهم"


# --------------------------------------------------------------- fakes / helpers
class RecordingBot:
    def __init__(self):
        self.sent: list[str] = []

    async def send_message(self, chat_id=None, text=None, **kw):
        self.sent.append(text)


class Client:
    """عميل وهمي مرن: سلوك قابل للتحكّم في القراءة/الإرسال."""

    def __init__(self, *, conv=None, get_error=None, send_error=None):
        self._conv = conv if conv is not None else {
            "id": CID, "title": "شات", "execution_status": "running", "sandbox_status": "RUNNING",
        }
        self._get_error = get_error
        self._send_error = send_error
        self.send_calls: list[tuple[str, str]] = []

    async def get_conversations(self, ids):
        if self._get_error is not None:
            raise self._get_error
        return [self._conv] if self._conv else []

    async def resume_sandbox(self, sandbox_id):  # pragma: no cover - مش بيتنادى في الاختبارات
        raise AssertionError("resume_sandbox مش المفروض يتنادى هنا")

    async def send_message(self, conversation_id, text):
        self.send_calls.append((conversation_id, text))
        if self._send_error is not None:
            raise self._send_error


def make_db(tmp_path, cls=Database, name="outbox.sqlite3"):
    return cls(str(tmp_path / name))


def add_and_claim(db, *, attempts=0):
    """يسجّل سجلًا ويحجزه فعليًا ('claimed')، ويرفع attempts، ويرجّع الصف."""
    oid = db.add_outbox(CID, OWNER, TEXT, outbox.now_iso())
    claimed = db.claim_outbox(outbox.now_iso())
    assert claimed is not None and claimed.id == oid
    for _ in range(attempts):
        db.set_outbox_status(oid, OUTBOX_CLAIMED, outbox.now_iso(), bump=True)
    return db.get_outbox(oid)


def run(client, db, bot, item):
    asyncio.run(_post_claimed(client, db, bot, item))


# ===================================================== 1) pre-CAS unexpected ⇒ pending
def test_unexpected_pre_cas_exception_recovers_to_pending(tmp_path):
    db = make_db(tmp_path)
    item = add_and_claim(db)
    client, bot = Client(get_error=RuntimeError("boom")), RecordingBot()

    run(client, db, bot, item)

    assert db.get_outbox(item.id).status == OUTBOX_PENDING   # رجع مؤهّل، مش عالق 'claimed'
    assert client.send_calls == []                           # مفيش POST (الـ CAS ماحصلش)
    # attempts=1 ⇒ إشعار "فشل الإرسال" واحد (نفس سلوك مسار ApiError الآمن)
    assert len(bot.sent) == 1 and bot.sent[0].startswith("فشل الإرسال:")


def test_unexpected_pre_cas_first_attempt_notifies_once(tmp_path):
    db = make_db(tmp_path)
    item = add_and_claim(db)
    client, bot = Client(get_error=ValueError("bad decode")), RecordingBot()

    run(client, db, bot, item)

    assert len(bot.sent) == 1 and bot.sent[0].startswith("فشل الإرسال:")


# ============================================ 2) guarded atomic CAS (state-guarded)
class ConcurrentSenderDb(Database):
    """يحاكي تغييرًا متوازيًا: السجل بقى 'sending' قبل CAS التعافي."""

    def __init__(self, path):
        super().__init__(path)
        self._injected = False

    def bump_outbox_attempt(self, outbox_id, now, error=None):
        n = super().bump_outbox_attempt(outbox_id, now, error)
        if n and not self._injected:
            self._injected = True
            self.set_outbox_status(outbox_id, OUTBOX_SENDING, now)
        return n


def test_recovery_cas_does_not_overwrite_concurrent_sending(tmp_path):
    db = make_db(tmp_path, ConcurrentSenderDb)
    item = add_and_claim(db)
    client, bot = Client(get_error=RuntimeError("boom")), RecordingBot()

    run(client, db, bot, item)

    # التعافي CAS من 'claimed' بس ⇒ فشل، وما نزلش السجل لـ 'pending'
    assert db.get_outbox(item.id).status == OUTBOX_SENDING
    assert bot.sent == []


class ConcurrentDiscardDb(Database):
    """يحاكي شطبًا متوازيًا: السجل بقى 'discarded' قبل CAS التعافي."""

    def __init__(self, path):
        super().__init__(path)
        self._injected = False

    def bump_outbox_attempt(self, outbox_id, now, error=None):
        n = super().bump_outbox_attempt(outbox_id, now, error)
        if n and not self._injected:
            self._injected = True
            self.set_outbox_status(outbox_id, OUTBOX_DISCARDED, now)
        return n


def test_recovery_cas_does_not_resurrect_concurrent_discard(tmp_path):
    db = make_db(tmp_path, ConcurrentDiscardDb)
    item = add_and_claim(db)
    client, bot = Client(get_error=RuntimeError("boom")), RecordingBot()

    run(client, db, bot, item)

    assert db.get_outbox(item.id).status == OUTBOX_DISCARDED   # مفيش إحياء
    assert bot.sent == []


# ==================================================== 3) retry / attempt-limit policy
def test_unexpected_pre_cas_respects_max_attempts(tmp_path):
    db = make_db(tmp_path)
    item = add_and_claim(db, attempts=outbox.MAX_OUTBOX_ATTEMPTS - 1)
    client, bot = Client(get_error=RuntimeError("boom")), RecordingBot()

    run(client, db, bot, item)

    assert db.get_outbox(item.id).status == OUTBOX_FAILED   # استنفاد ⇒ نهائي
    assert bot.sent == [outbox._OUTBOX_EXHAUSTED_NOTICE]
    assert client.send_calls == []


def test_unexpected_pre_cas_attempt_counter_increments(tmp_path):
    db = make_db(tmp_path)
    item = add_and_claim(db)  # attempts=0
    client, bot = Client(get_error=RuntimeError("boom")), RecordingBot()

    run(client, db, bot, item)

    assert db.get_outbox(item.id).attempts == 1


# ============================================ 5) recovery DB failure reported honestly
class FailingPendingWriteDb(Database):
    """يفشل في كتابة CAS التعافي (بدون ما يغيّر الحالة) ⇒ مفيش ادّعاء نجاح."""

    def set_outbox_status_if_in(self, outbox_id, new_status, now, allowed_statuses, error=None):
        if new_status == OUTBOX_PENDING:
            raise sqlite3.OperationalError("db down")
        return super().set_outbox_status_if_in(outbox_id, new_status, now, allowed_statuses, error)


def test_recovery_write_failure_leaves_row_claimed_no_false_success(tmp_path):
    db = make_db(tmp_path, FailingPendingWriteDb)
    item = add_and_claim(db)
    client, bot = Client(get_error=RuntimeError("boom")), RecordingBot()

    run(client, db, bot, item)  # مايرميش: التعافي بيسجّل الفشل ويرجع

    assert db.get_outbox(item.id).status == OUTBOX_CLAIMED   # مفيش تعافٍ وهمي


class FailingBumpDb(Database):
    def bump_outbox_attempt(self, *a, **k):
        raise sqlite3.OperationalError("db down")


def test_recovery_bump_failure_leaves_row_claimed_no_false_success(tmp_path):
    db = make_db(tmp_path, FailingBumpDb)
    item = add_and_claim(db)
    client, bot = Client(get_error=RuntimeError("boom")), RecordingBot()

    run(client, db, bot, item)

    assert db.get_outbox(item.id).status == OUTBOX_CLAIMED


# ===================================================== 6) CAS failure ⇒ no Telegram POST
class FailingSendingCasDb(Database):
    """يحاكي فشل CAS الإرسال (السجل مش مملوك) بلا كتابة."""

    def set_outbox_status_if_in(self, outbox_id, new_status, now, allowed_statuses, error=None):
        if new_status == OUTBOX_SENDING:
            return False
        return super().set_outbox_status_if_in(outbox_id, new_status, now, allowed_statuses, error)


def test_cas_failure_never_posts(tmp_path):
    db = make_db(tmp_path, FailingSendingCasDb)
    item = add_and_claim(db)
    client, bot = Client(), RecordingBot()  # sandbox RUNNING ⇒ هيوصل لحدّ الـ CAS

    run(client, db, bot, item)

    assert client.send_calls == []                       # مفيش POST خالص
    assert db.get_outbox(item.id).status == OUTBOX_CLAIMED


# ============================================ 7) successful CAS ⇒ full post-CAS sequence
def test_successful_cas_runs_post_cas_sequence(tmp_path):
    db = make_db(tmp_path)
    item = add_and_claim(db)
    client, bot = Client(), RecordingBot()

    run(client, db, bot, item)

    assert client.send_calls == [(CID, TEXT)]            # POST واحد بالظبط
    assert db.get_outbox(item.id).status == OUTBOX_SENT
    assert bot.sent == [outbox._OUTBOX_SENT_NOTICE]
    # intent الإكمال المحلي اتنفّذ واتشال بعد نجاح الإشعار
    assert db.get_completion_pending(outbox.COMPLETION_KIND_OUTBOX, item.id) is None
    assert db.is_watched(CID)


# ==================================== 8+9) post-CAS unexpected ⇒ unknown, no second POST
def test_post_cas_unexpected_exception_sets_unknown_not_pending(tmp_path):
    db = make_db(tmp_path)
    item = add_and_claim(db)
    client, bot = Client(send_error=RuntimeError("boom after post")), RecordingBot()

    run(client, db, bot, item)

    assert db.get_outbox(item.id).status == OUTBOX_UNKNOWN   # مش 'pending' ولا 'claimed'
    assert db.get_outbox(item.id).status != OUTBOX_PENDING


def test_post_cas_failure_cannot_trigger_second_post(tmp_path):
    db = make_db(tmp_path)
    item = add_and_claim(db)
    client, bot = Client(send_error=RuntimeError("boom after post")), RecordingBot()

    run(client, db, bot, item)

    assert len(client.send_calls) == 1                        # POST واحد بس، مفيش إعادة


# ================================================================ 10) CancelledError
def test_cancelled_error_pre_cas_propagates_and_stays_claimed(tmp_path):
    db = make_db(tmp_path)
    item = add_and_claim(db)
    client, bot = Client(get_error=asyncio.CancelledError()), RecordingBot()

    with pytest.raises(asyncio.CancelledError):
        run(client, db, bot, item)

    assert db.get_outbox(item.id).status == OUTBOX_CLAIMED    # ماتكتمش وماتغيّرش


def test_cancelled_error_post_cas_propagates_and_sets_unknown(tmp_path):
    db = make_db(tmp_path)
    item = add_and_claim(db)
    client, bot = Client(send_error=asyncio.CancelledError()), RecordingBot()

    with pytest.raises(asyncio.CancelledError):
        run(client, db, bot, item)

    assert db.get_outbox(item.id).status == OUTBOX_UNKNOWN    # غامض، مفيش إعادة
    assert len(client.send_calls) == 1


# ==================================================== 11) ApiError behavior unchanged
def test_pre_cas_apierror_retryable_returns_pending_no_post(tmp_path):
    db = make_db(tmp_path)
    item = add_and_claim(db)
    client, bot = Client(get_error=ApiError("down", 503)), RecordingBot()

    run(client, db, bot, item)

    assert db.get_outbox(item.id).status == OUTBOX_PENDING
    assert client.send_calls == []                            # حرس الـ return: مفيش POST
    assert len(bot.sent) == 1 and bot.sent[0].startswith("فشل الإرسال:")


def test_post_cas_apierror_permanent_sets_failed(tmp_path):
    db = make_db(tmp_path)
    item = add_and_claim(db)
    client, bot = Client(send_error=ApiError("bad request", 400)), RecordingBot()

    run(client, db, bot, item)

    assert db.get_outbox(item.id).status == OUTBOX_FAILED
    assert len(client.send_calls) == 1


def test_post_cas_apierror_transient_sets_unknown(tmp_path):
    db = make_db(tmp_path)
    item = add_and_claim(db)
    client, bot = Client(send_error=ApiError("gateway", 503)), RecordingBot()

    run(client, db, bot, item)

    assert db.get_outbox(item.id).status == OUTBOX_UNKNOWN
    assert len(client.send_calls) == 1


# ===================================================== 12) F-1 tombstone protections
class TombstoningFailClient:
    """يكتب شاهد الحذف **خلال** النداء البعيد ثم يرمي استثناءً غير متوقّع."""

    def __init__(self, db):
        self._db = db
        self.send_calls: list[tuple[str, str]] = []

    async def get_conversations(self, ids):
        self._db.begin_remote_deletion(CID, outbox.now_iso())
        raise RuntimeError("boom after tombstone")

    async def resume_sandbox(self, sandbox_id):  # pragma: no cover - مش بيتنادى
        raise AssertionError("resume_sandbox مش المفروض يتنادى")

    async def send_message(self, conversation_id, text):
        self.send_calls.append((conversation_id, text))


def test_unexpected_pre_cas_with_tombstone_recovers_but_no_notice(tmp_path):
    db = make_db(tmp_path)
    item = add_and_claim(db)
    client, bot = TombstoningFailClient(db), RecordingBot()

    run(client, db, bot, item)

    assert db.get_outbox(item.id).status == OUTBOX_PENDING    # تعافٍ آمن (قبل الـ CAS)
    assert client.send_calls == []                            # مفيش POST
    assert bot.sent == []                                     # مفيش إشعار لشات محذوف (fail-closed)


def test_entry_tombstone_still_discards_without_remote_call(tmp_path):
    db = make_db(tmp_path)
    item = add_and_claim(db)
    db.begin_remote_deletion(CID, outbox.now_iso())
    client, bot = Client(), RecordingBot()

    run(client, db, bot, item)

    assert db.get_outbox(item.id).status == OUTBOX_DISCARDED
    assert client.send_calls == []


# ============================================= 13) worker lifecycle integration (bounded)
from datetime import timedelta  # noqa: E402

from bot.outbox import OutboxWorker  # noqa: E402


def test_worker_recovers_unexpected_pre_cas_then_redelivers(tmp_path, monkeypatch):
    """دورة worker: استثناء غير متوقّع في محاولة، ثم نجاح — إرسال واحد بالظبط."""
    monkeypatch.setattr("bot.db.GROUP_WINDOW", timedelta(0))  # كل 'pending' ناضج فورًا
    db = make_db(tmp_path)
    oid = db.add_outbox(CID, OWNER, TEXT, outbox.now_iso())

    class FlakyClient(Client):
        def __init__(self):
            super().__init__()
            self.calls = 0

        async def get_conversations(self, ids):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("first prep fails")
            return [self._conv]

    client, bot = FlakyClient(), RecordingBot()
    worker = OutboxWorker(client, db, bot)

    async def drive():
        assert await worker._tick() is True          # محاولة 1: تعافي pre-CAS ⇒ pending
        assert await worker._tick() is True          # محاولة 2: نجاح

    asyncio.run(drive())

    assert db.get_outbox(oid).status == OUTBOX_SENT
    assert len(client.send_calls) == 1               # إرسال واحد بس (at-most-once)


def test_worker_does_not_loop_forever_on_persistent_unexpected_error(tmp_path, monkeypatch):
    """خطأ مستمر: بعد MAX_OUTBOX_ATTEMPTS يتوقف السجل نهائيًا (مفيش حلقة لا نهائية)."""
    monkeypatch.setattr("bot.db.GROUP_WINDOW", timedelta(0))
    db = make_db(tmp_path)
    oid = db.add_outbox(CID, OWNER, TEXT, outbox.now_iso())

    client, bot = Client(get_error=RuntimeError("always fails")), RecordingBot()
    worker = OutboxWorker(client, db, bot)

    async def drive():
        for _ in range(outbox.MAX_OUTBOX_ATTEMPTS + 5):
            if not await worker._tick():
                break

    asyncio.run(drive())

    assert db.get_outbox(oid).status == OUTBOX_FAILED
    assert db.get_outbox(oid).attempts == outbox.MAX_OUTBOX_ATTEMPTS
    assert client.send_calls == []                    # عمره ما بعت


# ===================================== 14) post-CAS completion failure ⇒ no second POST
class FailingCompletionDb(Database):
    """يفشل في كتابة intent الإكمال (بعد ما الـ POST ينجح) ⇒ استثناء بعد الـ 'sent'."""

    def complete_outbox_sent(self, *a, **k):
        raise RuntimeError("completion write failed")


def test_completion_write_failure_after_post_does_not_republish(tmp_path):
    """لو كتابة الإكمال فشلت بعد نجاح الـ POST، الاستثناء يطلع (مفيش ابتلاع) — ومفيش POST تاني."""
    db = make_db(tmp_path, FailingCompletionDb)
    item = add_and_claim(db)
    client, bot = Client(), RecordingBot()

    with pytest.raises(RuntimeError):
        run(client, db, bot, item)

    assert len(client.send_calls) == 1                 # POST واحد بس
    # السجل لسه 'sending' (الكتابة فشلت قبل الـ CAS) ⇒ مفيش ادّعاء 'sent' وهمي
    assert db.get_outbox(item.id).status == OUTBOX_SENDING


class FailingCompleteOutboxDb(Database):
    """يفشل في قراءة/كتابة الإكمال المحلي **بعد** ما السجل يبقى 'sent'."""

    def get_completion_pending(self, ref_kind, ref_id):
        raise RuntimeError("completion read failed")


def test_local_completion_failure_after_sent_does_not_republish(tmp_path):
    """السجل 'sent' خلاص ⇒ فشل الإكمال المحلي مايعملش POST تاني (at-most-once)."""
    db = make_db(tmp_path, FailingCompleteOutboxDb)
    item = add_and_claim(db)
    client, bot = Client(), RecordingBot()

    with pytest.raises(RuntimeError):
        run(client, db, bot, item)

    assert len(client.send_calls) == 1
    assert db.get_outbox(item.id).status == OUTBOX_SENT   # اتحسم كـ 'sent' (مفيش إعادة)


# =============================== 15) entry F-1 guard read failure ⇒ pre-CAS recovery
class EntryGuardFailDb(Database):
    """فشل قراءة شاهد الحذف عند مدخل `_post_claimed` (SQLite عابر) — قبل الـ CAS."""

    def is_deleted(self, conversation_id):
        raise sqlite3.OperationalError("db busy at entry")


def test_entry_guard_read_failure_recovers_to_pending_not_stuck(tmp_path):
    """فشل قراءة الشاهد عند المدخل استثناء غير متوقّع قبل الـ CAS ⇒ 'pending' مش عالق 'claimed'."""
    db = make_db(tmp_path, EntryGuardFailDb)
    item = add_and_claim(db)
    client, bot = Client(), RecordingBot()

    run(client, db, bot, item)  # مايرميش: تعافى

    assert db.get_outbox(item.id).status == OUTBOX_PENDING   # اتعافى، مش عالق
    assert client.send_calls == []                           # مفيش POST
