"""OHB2-STABILIZATION-F02/F06: اختبارات مركّزة على الكود الحقيقي (بدون mocks غير ضرورية).

- F02 atomicity: الانتقال النهائي (sent/done) + intent الإكمال في معاملة واحدة، وكل حدود
  الـ crash، والتعافي بعد restart، ومسارا outbox/creation، والتسوية المتحفّظة للصفوف القديمة.
- F02 fairness: عنصر فاشل أول مايعطّلش عنصر سليم؛ backoff دائم؛ الاستنفاد ظاهر؛ الحجز الآمن.
- F06 readiness/liveness: فصل واضح بين الاتنين، ورفض ادّعاء READY قبل التحقق أو بعد فشله.
"""
from __future__ import annotations

import asyncio
import sqlite3

import pytest
from starlette.testclient import TestClient

from bot.config import Config
from bot.db import Database
from bot.outbox import (
    COMPLETION_KIND_CREATION,
    COMPLETION_KIND_OUTBOX,
    COMPLETION_MAX_ATTEMPTS,
    CompletionWorker,
    completion_recover,
    now_iso,
)
from bot.web import build_web_app
from bot.web.app import MiniApp
from tests._miniapp_helpers import BOT_TOKEN

OWNER = 555


def _cfg(**over) -> Config:
    base = dict(
        telegram_bot_token=BOT_TOKEN,
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({OWNER}),
        owner_id=OWNER,
        mini_app_cookie_secure=False,
    )
    base.update(over)
    return Config(**base)


def _mkdb(tmp_path) -> Database:
    return Database(str(tmp_path / "t.sqlite3"))


class _Bot:
    def __init__(self, fail=False):
        self.sent: list[str] = []
        self.fail = fail

    async def send_message(self, chat_id, text):
        if self.fail:
            from telegram.error import TelegramError

            raise TelegramError("boom")
        self.sent.append(text)


class _Client:
    """عميل خارجي وهمي بيرجّع شات موجود ويرمي لو حد حاول يعمل POST في مسار الإكمال."""

    def __init__(self, conv=None):
        self._conv = conv or {
            "id": "c1", "title": "شات", "execution_status": "running",
            "sandbox_status": "RUNNING",
        }

    async def get_conversations(self, ids):
        return [self._conv]

    async def send_message(self, cid, text):
        pass


class _ExplodeClient:
    async def get_conversations(self, ids):
        raise AssertionError("الإكمال المحلي مايعملش أي استدعاء خارجي (at-most-once)")

    async def send_message(self, *a, **k):
        raise AssertionError("الإكمال المحلي مايعملش أي استدعاء خارجي (at-most-once)")


class _App:
    """بديل بسيط لكائن التطبيق (bot_data بس) لاختبارات التعافي."""

    def __init__(self, db, bot):
        self.bot_data = {"db": db}
        self.bot = bot


# ============================================================ F02 ATOMICITY
def test_atomic_outbox_sent_and_intent_commit_together(tmp_path):
    """نجاح POST: 'sent' + intent الإكمال لازم يكونوا موجودين مع بعض بعد النجاح."""
    db = _mkdb(tmp_path)
    oid = db.add_outbox("c1", 99, "برومت", now_iso())
    db.set_outbox_status(oid, "claimed", now_iso())
    db.set_outbox_status(oid, "sending", now_iso())
    ok = db.complete_outbox_sent(
        oid, now_iso(), chat_id=99, conversation_id="c1", title="T",
        last_state="running", submitted_at="t0", notice_text="نص",
    )
    assert ok is True
    assert db.get_outbox(oid).status == "sent"
    pending = db.get_completion_pending(COMPLETION_KIND_OUTBOX, oid)
    assert pending is not None  # مستحيل يبقى sent من غير intent
    assert pending.conversation_id == "c1"


def test_atomic_outbox_cas_failure_writes_nothing(tmp_path):
    """لو الحالة اتحسمت بحالة أحدث: مفيش 'sent' ولا intent (مفيش نجاح وهمي)."""
    db = _mkdb(tmp_path)
    oid = db.add_outbox("c1", 99, "برومت", now_iso())
    db.set_outbox_status(oid, "unknown", now_iso())  # حسم أحدث
    ok = db.complete_outbox_sent(
        oid, now_iso(), chat_id=99, conversation_id="c1", notice_text="نص",
    )
    assert ok is False
    assert db.get_outbox(oid).status == "unknown"
    assert db.get_completion_pending(COMPLETION_KIND_OUTBOX, oid) is None


def test_atomic_transaction_rolls_back_both_on_failure(tmp_path, monkeypatch):
    """فشل داخل المعاملة (بعد UPDATE الحالة وقبل الـ commit) ⇒ **ولا** صف يتثبت."""
    db = _mkdb(tmp_path)
    oid = db.add_outbox("c1", 99, "برومت", now_iso())
    db.set_outbox_status(oid, "claimed", now_iso())
    db.set_outbox_status(oid, "sending", now_iso())

    def boom(*a, **k):
        raise sqlite3.OperationalError("simulated mid-transaction failure")

    # الفشل بيحصل جوه المعاملة بعد ما الحالة 'sent' اتكتبت (لسه ماتعملهاش commit).
    monkeypatch.setattr(db, "_upsert_completion_pending_nocommit", boom)
    with pytest.raises(sqlite3.OperationalError):
        db.complete_outbox_sent(
            oid, now_iso(), chat_id=99, conversation_id="c1", notice_text="نص",
        )
    monkeypatch.undo()

    # **ولا** أثر اتثبت: الحالة لسه 'sending' ومفيش intent (الـ rollback نجح).
    assert db.get_outbox(oid).status == "sending"
    assert db.get_completion_pending(COMPLETION_KIND_OUTBOX, oid) is None


def test_crash_after_commit_recovers_completion(tmp_path):
    """crash بعد الـ commit: intent الإكمال ثابت ⇒ يتعافى بعد restart بدون أي POST."""
    db = _mkdb(tmp_path)
    oid = db.add_outbox("c1", 99, "برومت", now_iso())
    db.set_outbox_status(oid, "claimed", now_iso())
    db.set_outbox_status(oid, "sending", now_iso())
    assert db.complete_outbox_sent(
        oid, now_iso(), chat_id=99, conversation_id="c1", title="T",
        last_state="running", submitted_at="t0", notice_text="اتبعت ✅",
    )
    # "إعادة تشغيل" — نفس القاعدة، اتصال جديد.
    db2 = Database(str(tmp_path / "t.sqlite3"))
    assert db2.count_completion_pending() == 1
    bot = _Bot()
    worker = CompletionWorker(_ExplodeClient(), db2, bot)
    asyncio.run(worker._tick())
    assert db2.count_completion_pending() == 0
    assert db2.is_watched("c1")
    assert any("اتبعت" in s for s in bot.sent)
    assert db2.get_outbox(oid).status == "sent"  # مفيش POST مكرّر


def test_creation_atomic_done_and_intent(tmp_path):
    """مسار creation: 'done' + intent في معاملة واحدة، والتعافي مايعيدش إنشاء الشات."""
    from bot import outbox as ob

    db = _mkdb(tmp_path)
    jid = db.add_creation_job(99, "o/r", "text", now_iso())
    db.set_creation_status(jid, "claimed", now_iso())
    bot = _Bot(fail=True)
    asyncio.run(ob._finish_creation(_Client(), db, bot, jid, 99, "o/r", "conv-1", "https://x"))
    assert db.get_creation_job(jid).status == "done"
    pending = db.get_completion_pending(COMPLETION_KIND_CREATION, jid)
    assert pending is not None and pending.conversation_id == "conv-1"

    ok_bot = _Bot()
    worker = CompletionWorker(_ExplodeClient(), db, ok_bot)
    asyncio.run(worker._tick())
    assert db.get_completion_pending(COMPLETION_KIND_CREATION, jid) is None
    assert any("conv-1" in s for s in ok_bot.sent)
    assert db.get_creation_job(jid).status == "done"  # مفيش إعادة إنشاء


def test_creation_cas_failure_writes_nothing(tmp_path):
    from bot import outbox as ob

    db = _mkdb(tmp_path)
    jid = db.add_creation_job(99, "o/r", "text", now_iso())
    db.set_creation_status(jid, "discarded", now_iso())  # المستخدم شطب
    asyncio.run(ob._finish_creation(_Client(), db, _Bot(), jid, 99, "o/r", "conv-1", "https://x"))
    assert db.get_creation_job(jid).status == "discarded"
    assert db.get_completion_pending(COMPLETION_KIND_CREATION, jid) is None


def test_no_external_post_during_completion_recovery(tmp_path):
    """التعافي/التسوية مايعملوش أي POST خارجي (العميل بيرمي لو اتنادى)."""
    db = _mkdb(tmp_path)
    oid = db.add_outbox("c1", 99, "برومت", now_iso())
    db.set_outbox_status(oid, "sent", now_iso())  # صف قديم من غير intent
    app = _App(db, _Bot())
    asyncio.run(completion_recover(app))
    worker = CompletionWorker(_ExplodeClient(), db, _Bot())
    asyncio.run(worker._tick())
    assert db.count_completion_pending() == 0


def test_legacy_sent_row_surfaced_not_auto_reconciled(tmp_path):
    """صف sent قديم من غير intent **مايتسوّاش تلقائيًا** (تجنّب إشعارات مكرّرة) لكنه ظاهر."""
    db = _mkdb(tmp_path)
    oid = db.add_outbox("c1", 99, "برومت", now_iso())
    db.set_outbox_status(oid, "sent", now_iso())
    app = _App(db, _Bot())
    asyncio.run(completion_recover(app))  # مفيش تسوية تلقائية
    assert db.count_completion_pending() == 0
    assert db.count_legacy_unresolved_completions() == 1  # ظاهر للمشغّل
    # التسوية اليدوية الصريحة بتنشئ intent من الحقول الموجودة (بدون POST).
    assert db.reconcile_legacy_completion(COMPLETION_KIND_OUTBOX, oid, now_iso()) is True
    pending = db.get_completion_pending(COMPLETION_KIND_OUTBOX, oid)
    assert pending is not None and pending.conversation_id == "c1" and pending.chat_id == 99


def test_legacy_done_creation_reconciled(tmp_path):
    db = _mkdb(tmp_path)
    jid = db.add_creation_job(99, "o/r", "text", now_iso())
    db._conn.execute(
        "UPDATE creation_jobs SET status='done', conversation_id='conv-9' WHERE id=?", (jid,)
    )
    db._conn.commit()
    assert db.count_legacy_unresolved_completions() == 1
    assert db.reconcile_legacy_completion(COMPLETION_KIND_CREATION, jid, now_iso()) is True
    pending = db.get_completion_pending(COMPLETION_KIND_CREATION, jid)
    assert pending is not None and pending.conversation_id == "conv-9"
    assert db.count_legacy_unresolved_completions() == 0


def test_legacy_row_without_conversation_id_left_untouched(tmp_path):
    """صف غير كافي البيانات (conversation_id فاضي) مايتسوّاش — مفيش اختلاق نجاح."""
    db = _mkdb(tmp_path)
    oid = db.add_outbox("c1", 99, "برومت", now_iso())
    db._conn.execute(
        "UPDATE outbox SET conversation_id='', status='sent' WHERE id=?", (oid,)
    )
    db._conn.commit()
    assert db.count_legacy_unresolved_completions() == 0
    assert db.reconcile_legacy_completion(COMPLETION_KIND_OUTBOX, oid, now_iso()) is False
    assert db.get_completion_pending(COMPLETION_KIND_OUTBOX, oid) is None


def test_completion_recovery_does_not_repost_external(tmp_path):
    """التعافي/التسوية مايعملوش أي POST خارجي (العميل بيرمي لو اتنادى)."""
    db = _mkdb(tmp_path)
    oid = db.add_outbox("c1", 99, "برومت", now_iso())
    db.set_outbox_status(oid, "sent", now_iso())
    app = _App(db, _Bot())
    asyncio.run(completion_recover(app))
    # التسوية اليدوية كمان مابتعملش POST.
    assert db.reconcile_legacy_completion(COMPLETION_KIND_OUTBOX, oid, now_iso()) is True
    worker = CompletionWorker(_ExplodeClient(), db, _Bot())
    asyncio.run(worker._tick())
    assert db.count_completion_pending() == 0
    assert db.is_watched("c1")


# ============================================================== F02 FAIRNESS
def test_failing_first_record_does_not_starve_healthy_second(tmp_path):
    """عنصر أول فاشل مايعطّلش عنصر تاني سليم (head-of-line blocking اتصلح)."""
    db = _mkdb(tmp_path)
    db.add_completion_pending(
        COMPLETION_KIND_OUTBOX, 1, 99, "c-bad", now_iso(),
        title="bad", notice_text="نص", submitted_at="t0",
    )
    db.add_completion_pending(
        COMPLETION_KIND_OUTBOX, 2, 99, "c-ok", now_iso(),
        title="ok", notice_text="نص", submitted_at="t0",
    )

    class SelectiveBot:
        def __init__(self):
            self.sent = []

        async def send_message(self, chat_id, text):
            # الإكمال بيسجّل المتابعة **قبل** الإشعار، فالرفض بيرمي استثناء جوه المعالجة.
            raise RuntimeError("boom")

    # العنصر الأول فشل ⇒ بقى مجدول (next_attempt_at مستقبلي) ⇒ مش مؤهّل.
    worker = CompletionWorker(None, db, SelectiveBot())
    asyncio.run(worker._tick())
    bad = db.get_completion_pending(COMPLETION_KIND_OUTBOX, 1)
    assert bad is not None and bad.next_attempt_at is not None

    # العنصر التاني (سليم) المفروض يتكمل في الدورة اللي بعدها، مش يستنى الأول.
    ok_bot = _Bot()
    worker2 = CompletionWorker(None, db, ok_bot)
    asyncio.run(worker2._tick())
    assert db.get_completion_pending(COMPLETION_KIND_OUTBOX, 2) is None  # اتكمل
    assert db.get_completion_pending(COMPLETION_KIND_OUTBOX, 1) is not None  # لسه مجدول


def test_retry_delay_prevents_immediate_retry(tmp_path):
    """بعد الفشل، العنصر مايتاخدش تاني في نفس اللحظة (backoff دائم)."""
    db = _mkdb(tmp_path)
    db.add_completion_pending(
        COMPLETION_KIND_OUTBOX, 1, 99, "c1", now_iso(), title="T", notice_text="نص",
    )
    worker = CompletionWorker(None, db, _Bot(fail=True))
    asyncio.run(worker._tick())
    row = db.get_completion_pending(COMPLETION_KIND_OUTBOX, 1)
    assert row.attempts == 1 and row.next_attempt_at is not None
    # دورة تانية فورًا: مفيش عنصر مؤهّل (مفيش محاولة متكرّرة فورية).
    assert worker._claim() is None
    assert db.get_completion_pending(COMPLETION_KIND_OUTBOX, 1).attempts == 1


def test_exhausted_record_visible_and_excluded(tmp_path):
    """العنصر اللي استنفد يصبح ظاهر (exhausted) ومستبعد من المؤهّل، مايتشالش."""
    db = _mkdb(tmp_path)
    db.add_completion_pending(
        COMPLETION_KIND_OUTBOX, 1, 99, "c1", now_iso(), title="T", notice_text="نص",
    )
    worker = CompletionWorker(None, db, _Bot(fail=True))
    for _ in range(COMPLETION_MAX_ATTEMPTS):
        db._conn.execute("UPDATE completion_pending SET next_attempt_at=NULL")
        db._conn.commit()
        asyncio.run(worker._tick())
    row = db.get_completion_pending(COMPLETION_KIND_OUTBOX, 1)
    assert row is not None and row.exhausted == 1
    assert db.list_completion_exhausted() and db.list_completion_exhausted()[0].ref_id == 1
    # مستبعد من المؤهّل: حتى لو موعد المحاولة حان.
    db._conn.execute("UPDATE completion_pending SET next_attempt_at=NULL")
    db._conn.commit()
    assert worker._claim() is None
    stats = db.completion_stats(now_iso())
    assert stats["exhausted"] == 1 and stats["eligible"] == 0


def test_rearm_exhausted_makes_eligible_again(tmp_path):
    db = _mkdb(tmp_path)
    db.add_completion_pending(
        COMPLETION_KIND_OUTBOX, 1, 99, "c1", now_iso(), title="T", notice_text="نص",
    )
    worker = CompletionWorker(None, db, _Bot(fail=True))
    for _ in range(COMPLETION_MAX_ATTEMPTS):
        db._conn.execute("UPDATE completion_pending SET next_attempt_at=NULL")
        db._conn.commit()
        asyncio.run(worker._tick())
    assert db.get_completion_pending(COMPLETION_KIND_OUTBOX, 1).exhausted == 1
    assert db.rearm_completion_pending(COMPLETION_KIND_OUTBOX, 1, now_iso()) is True
    ok_bot = _Bot()
    asyncio.run(CompletionWorker(None, db, ok_bot)._tick())
    assert db.count_completion_pending() == 0  # اكتمل بعد إعادة التأهيل


def test_restart_preserves_retry_schedule(tmp_path):
    """إعادة التشغيل بتحافظ على جدول إعادة المحاولة (مش بتعيد فورًا)."""
    db = _mkdb(tmp_path)
    db.add_completion_pending(
        COMPLETION_KIND_OUTBOX, 1, 99, "c1", now_iso(), title="T", notice_text="نص",
    )
    asyncio.run(CompletionWorker(None, db, _Bot(fail=True))._tick())
    db2 = Database(str(tmp_path / "t.sqlite3"))
    row = db2.get_completion_pending(COMPLETION_KIND_OUTBOX, 1)
    assert row.next_attempt_at is not None
    # بعد restart، العنصر لسه غير مؤهّل (الجدولة محفوظة).
    assert CompletionWorker(None, db2, _Bot())._claim() is None


def test_concurrent_claims_do_not_duplicate(tmp_path):
    """حجز متزامن: اتنين claims متتاليين مايرجّعوش نفس الصف (safe concurrent claiming)."""
    db = _mkdb(tmp_path)
    db.add_completion_pending(
        COMPLETION_KIND_OUTBOX, 1, 99, "c1", now_iso(), title="T", notice_text="نص",
    )
    first = db.claim_completion_due(now_iso(), "2099-01-01T00:00:00+00:00")
    second = db.claim_completion_due(now_iso(), "2099-01-01T00:00:00+00:00")
    assert first is not None and first.ref_id == 1
    assert second is None  # محجوز بإجارة ⇒ مش مؤهّل تاني


def test_idempotent_reprocess_after_lease_expiry(tmp_path):
    """انتهاء الإجارة (crash بعد الحجز) ⇒ الصف يرجع مؤهّل والإكمال idempotent."""
    db = _mkdb(tmp_path)
    db.add_completion_pending(
        COMPLETION_KIND_OUTBOX, 1, 99, "c1", now_iso(), title="T", notice_text="نص",
    )
    # إجارة في الماضي ⇒ الصف مؤهّل من جديد.
    db._conn.execute("UPDATE completion_pending SET next_attempt_at='2000-01-01T00:00:00+00:00'")
    db._conn.commit()
    bot = _Bot()
    asyncio.run(CompletionWorker(None, db, bot)._tick())
    assert db.count_completion_pending() == 0
    assert len(bot.sent) == 1  # مرة واحدة بس (idempotent)


# ======================================================= F06 READINESS/LIVENESS
def _app_ctx(db=None, **bot_data):
    class _A:
        pass

    a = _A()
    a.bot_data = dict(bot_data)
    if db is not None:
        a.bot_data["db"] = db
    return a


def test_liveness_healthy_even_when_not_ready(tmp_path):
    """liveness (/health) بيفضل 200 حتى لو الخدمة مش جاهزة (قاعدة مش متحقّقة)."""
    db = Database(str(tmp_path / "t.sqlite3"))  # integrity_ok = None ⇒ مش جاهز
    app = _app_ctx(db)
    client = TestClient(build_web_app(_cfg(), db, None, app))
    assert client.get("/health").status_code == 200
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/ready").status_code == 503


def test_readiness_false_before_db_verification(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    assert db.integrity_ok is None
    app = _app_ctx(db, outbox_worker=1, creation_worker=1, completion_worker=1,
                   watcher=1, notifier=1)
    client = TestClient(build_web_app(_cfg(), db, None, app))
    r = client.get("/ready")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["database"] == "not_ready"


def test_readiness_false_after_integrity_failure(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "t.sqlite3"))
    monkeypatch.setattr(db, "quick_check", lambda: False)
    db.run_startup_maintenance()
    app = _app_ctx(db, startup_failed="database_integrity")
    client = TestClient(build_web_app(_cfg(), db, None, app))
    r = client.get("/ready")
    assert r.status_code == 503
    assert r.json()["checks"]["startup"] == "failed"


def test_readiness_true_only_after_required_startup(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    assert db.run_startup_maintenance() is True
    app = _app_ctx(db, outbox_worker=1, creation_worker=1, completion_worker=1,
                   watcher=1, notifier=1)
    client = TestClient(build_web_app(_cfg(), db, None, app))
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_worker_startup_failure_cannot_produce_false_ready(tmp_path):
    """قاعدة سليمة بس worker مش شغّال ⇒ مش جاهز (مفيش READY وهمي)."""
    db = Database(str(tmp_path / "t.sqlite3"))
    db.run_startup_maintenance()
    app = _app_ctx(db, outbox_worker=1, creation_worker=None, completion_worker=1,
                   watcher=1, notifier=1)
    client = TestClient(build_web_app(_cfg(), db, None, app))
    r = client.get("/ready")
    assert r.status_code == 503
    assert r.json()["checks"]["creation_worker"] == "not_started"


def test_ready_and_status_responses_have_no_secrets(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.run_startup_maintenance()
    app = _app_ctx(db, outbox_worker=1, creation_worker=1, completion_worker=1,
                   watcher=1, notifier=1)
    client = TestClient(build_web_app(_cfg(), db, None, app))
    for path in ("/health", "/ready", "/status"):
        text = client.get(path).text
        assert BOT_TOKEN not in text
        assert "k" != text  # مفيش مفتاح خام
        assert "openhands" not in text.lower()


def test_status_surface_reports_completion_counts(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.run_startup_maintenance()
    db.add_completion_pending(
        COMPLETION_KIND_OUTBOX, 1, 99, "c1", now_iso(), title="T", notice_text="نص",
    )
    cw = CompletionWorker(None, db, _Bot())
    app = _app_ctx(db, outbox_worker=1, creation_worker=1, completion_worker=cw,
                   watcher=1, notifier=1)
    client = TestClient(build_web_app(_cfg(), db, None, app))
    body = client.get("/status").json()
    assert body["liveness"] == "ok"
    assert body["completion"]["pending"] == 1


def test_health_has_no_rate_limit_and_ready_too(tmp_path):
    cfg = _cfg(mini_app_api_rate_per_minute=1)
    db = Database(str(tmp_path / "t.sqlite3"))
    db.run_startup_maintenance()
    app = _app_ctx(db, outbox_worker=1, creation_worker=1, completion_worker=1,
                   watcher=1, notifier=1)
    c = TestClient(build_web_app(cfg, db, None, app))
    for _ in range(5):
        assert c.get("/health").status_code == 200
        assert c.get("/ready").status_code == 200


def test_miniapp_without_application_context_is_ready(tmp_path):
    """استخدام مستقل بدون سياق تطبيق ⇒ مفيش فشل معروف ⇒ جاهز (توافق للخلف)."""
    db = Database(str(tmp_path / "t.sqlite3"))
    mini = MiniApp(_cfg(), db, None, None)
    ready, payload = mini.readiness()
    assert ready is True and payload["status"] == "ready"


# ==================================================== MIGRATION / COMPAT
def test_migration_adds_completion_scheduling_columns(tmp_path):
    """قاعدة بجدول إكمال قديم (بدون أعمدة الجدولة) تترقّى إضافيًا وغير مدمّر."""
    path = str(tmp_path / "old.sqlite3")
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE completion_pending (
            ref_kind TEXT NOT NULL, ref_id INTEGER NOT NULL, chat_id INTEGER NOT NULL,
            conversation_id TEXT NOT NULL, title TEXT NOT NULL DEFAULT '',
            last_state TEXT, submitted_at TEXT, notice_text TEXT NOT NULL DEFAULT '',
            attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            PRIMARY KEY (ref_kind, ref_id)
        );
        INSERT INTO completion_pending
            (ref_kind, ref_id, chat_id, conversation_id, created_at, updated_at)
            VALUES ('outbox', 1, 99, 'c1', '2020-01-01T00:00:00+00:00', '2020-01-01T00:00:00+00:00');
        """
    )
    conn.commit()
    conn.close()
    db = Database(path)  # يعمل migration
    cols = {r["name"] for r in db._conn.execute("PRAGMA table_info(completion_pending)")}
    assert {"next_attempt_at", "failures", "exhausted"} <= cols
    row = db.get_completion_pending(COMPLETION_KIND_OUTBOX, 1)  # الصف القديم لسه موجود
    assert row is not None and row.exhausted == 0 and row.next_attempt_at is None
    stats = db.completion_stats(now_iso())
    assert stats["pending"] == 1 and stats["eligible"] == 1
