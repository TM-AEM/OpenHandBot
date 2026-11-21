"""OHB2-WP-07 (NEW-DEF-03) — ذرّية تغيير حالة المراقبة ونتيجة التحديث (watch/unwatch).

السياق: مساري `watch_conversation` و`unwatch_conversation` كانوا بيكتبوا تغيير الحالة
المحلية في commit مستقل **قبل** تسجيل نتيجة التحديث (`mark_durable_completed`) — commit
تانٍ. عطل بين الكتابتين كان يسيب تغيير حالة **بلا** نتيجة ⇒ حدّ الإقرار بيتوقف بلا سبب
(أو `last_state` مفقود في مسار watch). الإصلاح: الحالة + `last_state` + النتيجة في
**معاملة واحدة** (`BEGIN IMMEDIATE`)، وتعديل تيليجرام يفضل **برّه** المعاملة.

هذه الاختبارات **سلوكية** (بتقود الـ handlers الحقيقية عبر `Application.process_update`
لما يكون مناسبًا، وبتنادي الـ handler مباشرةً للسيناريوهات الدقيقة) و**مميِّزة**: لو
رجع أي مسار لكتابتين منفصلتين، أو اتسجّلت نتيجة بلا حالة، أو بقي تغيير حالة بلا نتيجة
عند فشل، بتفشل. مفيش شبكة: `Bot.send_message`/`Message.edit_text`/`answer_callback_query`
بتُعترض وقاعدة SQLite معزولة في `tmp_path`.
"""
from __future__ import annotations

import asyncio
import sqlite3

import pytest
from telegram import CallbackQuery, Chat, Message, Update, User
from telegram.error import BadRequest, TimedOut

import bot.app as app_mod
from bot import outbox
from bot import update_outcomes as uo
from bot.db import Database
from bot.watcher import Watcher
from tests.test_duplicate_update_dispatch import (
    CHAT_ID,
    CID_A,
    OWNER_ID,
    FakeOpenHands,
    _conv,
    make_config,
)

USER = User(id=OWNER_ID, first_name="o", is_bot=False)


class _FakeClient:
    """عميل OpenHands وهمي فاضي (مسار المراقب ما بيحتاجش شبكة)."""

    def __init__(self, by_id=None):
        self._by_id = by_id or {}

    async def get_conversations(self, ids):
        return [self._by_id[i] for i in ids if i in self._by_id]


class _FakeBot:
    async def send_message(self, *a, **kw):
        return None

    async def send_document(self, *a, **kw):
        return None
SUCCESS_WATCH = "تمام، الشات اتضاف للمتابعة ✅"
SUCCESS_UNWATCH = "تمام، اتشال من المتابعة."


# ============================================================================
# أدوات مساعدة (نفس نمط tests/test_wp07_f1_notification_failure.py)
# ============================================================================
async def _anoop(*_a, **_k):
    return True


def _patch_telegram(monkeypatch, *, send_exc=None, edit_exc=None):
    async def _send_message(self, chat_id=None, text=None, **kw):
        if send_exc is not None:
            raise send_exc
        m = Message(message_id=1, date=None, chat=Chat(id=chat_id or CHAT_ID, type="private"))
        m.set_bot(self)
        return m

    async def _edit_message_text(self, *a, **kw):
        if edit_exc is not None:
            raise edit_exc
        m = Message(message_id=1, date=None, chat=Chat(id=CHAT_ID, type="private"))
        m.set_bot(self)
        return m

    monkeypatch.setattr("telegram.Bot.send_message", _send_message)
    monkeypatch.setattr("telegram.Message.edit_text", _edit_message_text)
    monkeypatch.setattr("telegram.Bot.answer_callback_query", _anoop)
    monkeypatch.setattr("telegram.Bot.set_my_commands", _anoop)
    monkeypatch.setattr("telegram.Bot.set_chat_menu_button", _anoop)


def _build_app(tmp_path, monkeypatch, *, client=None, send_exc=None, edit_exc=None):
    app = app_mod.build_application(make_config(tmp_path))
    app._initialized = True  # نتخطّى initialize() (شبكة حقيقية)
    app.bot._bot_user = User(id=1, first_name="bot", is_bot=True, username="ohb_test_bot")
    if client is not None:
        app.bot_data["client"] = client
    _patch_telegram(monkeypatch, send_exc=send_exc, edit_exc=edit_exc)
    return app


def _cb_update(app, update_id: int, data: str) -> Update:
    chat = Chat(id=CHAT_ID, type="private")
    msg = Message(message_id=5, date=None, chat=chat, from_user=USER, text=None)
    msg.set_bot(app.bot)
    cq = CallbackQuery(id="cq", from_user=USER, chat_instance="ci", data=data, message=msg)
    cq.set_bot(app.bot)
    up = Update(update_id=update_id, callback_query=cq)
    up.set_bot(app.bot)
    return up


def _drive(app, update: Update) -> None:
    async def go():
        await app.process_update(update)
        await asyncio.sleep(0.05)

    asyncio.run(go())


# ============================================================================
# 1) نجاح: الحالة والنتيجة بيتحفظوا مع بعض
# ============================================================================
def test_watch_success_commits_state_and_outcome_together(tmp_path, monkeypatch):
    client = FakeOpenHands({CID_A: _conv(CID_A)})
    app = _build_app(tmp_path, monkeypatch, client=client)
    db = app.bot_data["db"]

    _drive(app, _cb_update(app, 7001, f"watch:{CID_A}"))

    assert db.is_watched(CID_A) is True
    assert db.get_watched(CID_A).last_state == "running"
    assert db.update_outcome(7001) == uo.DURABLE_COMPLETED
    assert db.is_update_acknowledgment_eligible(7001) is True
    db.close()


def test_unwatch_success_commits_state_and_outcome_together(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)
    db = app.bot_data["db"]
    db.add_watched(CID_A)

    _drive(app, _cb_update(app, 7002, f"unwatch:{CID_A}"))

    assert db.is_watched(CID_A) is False
    assert db.update_outcome(7002) == uo.DURABLE_COMPLETED
    assert db.is_update_acknowledgment_eligible(7002) is True
    db.close()


# ============================================================================
# 2) فشل الكتابة/الـ commit ⇒ ولا حالة ولا نتيجة (ذرّية كاملة)
# ============================================================================
class _CommitFailsConn:
    """بروكسي اتصال: كل حاجة تفوّض للاتصال الحقيقي، لكن `commit` بيفشل (فشل دائم)."""

    def __init__(self, conn):
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def commit(self):
        raise sqlite3.OperationalError("disk I/O error")


def test_watch_commit_failure_leaves_neither_state_nor_outcome(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    real_conn = db._conn
    db._conn = _CommitFailsConn(real_conn)

    with pytest.raises(sqlite3.OperationalError):
        db.add_watched_and_record_outcome(
            "c1", "شات", 99, "running", 7101, outbox.now_iso(), uo.DURABLE_COMPLETED,
        )

    assert real_conn.execute("SELECT 1 FROM watched WHERE conversation_id='c1'").fetchone() is None
    assert real_conn.execute(
        "SELECT 1 FROM processed_updates WHERE update_id=7101"
    ).fetchone() is None


def test_unwatch_commit_failure_leaves_state_and_outcome_untouched(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1")
    real_conn = db._conn
    db._conn = _CommitFailsConn(real_conn)

    with pytest.raises(sqlite3.OperationalError):
        db.remove_watched(
            "c1", update_id=7102, now=outbox.now_iso(), outcome=uo.DURABLE_COMPLETED,
        )

    assert real_conn.execute("SELECT 1 FROM watched WHERE conversation_id='c1'").fetchone() is not None
    assert real_conn.execute(
        "SELECT 1 FROM processed_updates WHERE update_id=7102"
    ).fetchone() is None


def test_watch_outcome_write_failure_rolls_back_state(tmp_path):
    """فشل كتابة النتيجة نفسها ⇒ الإضافة بتتراجع (مفيش متابعة بلا نتيجة)."""
    db = Database(str(tmp_path / "t.sqlite3"))

    def boom(*_a, **_k):
        raise sqlite3.OperationalError("disk I/O error")

    db.mark_update_outcome = boom
    with pytest.raises(sqlite3.OperationalError):
        db.add_watched_and_record_outcome(
            "c1", "شات", 99, "running", 7103, outbox.now_iso(), uo.DURABLE_COMPLETED,
        )

    assert db.is_watched("c1") is False
    assert db.update_outcome(7103) is None


def test_unwatch_outcome_write_failure_rolls_back_removal(tmp_path):
    """فشل كتابة النتيجة ⇒ الإزالة بتتراجع (الصف يفضل)."""
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1")

    def boom(*_a, **_k):
        raise sqlite3.OperationalError("disk I/O error")

    db.mark_update_outcome = boom
    with pytest.raises(sqlite3.OperationalError):
        db.remove_watched(
            "c1", update_id=7104, now=outbox.now_iso(), outcome=uo.DURABLE_COMPLETED,
        )

    assert db.is_watched("c1") is True
    assert db.update_outcome(7104) is None


def test_watch_watcher_persistence_failure_never_records_outcome(tmp_path):
    """فشل كتابة صف المتابعة ⇒ مفيش نتيجة مسجّلة (مفيش إقرار كاذب)."""
    db = Database(str(tmp_path / "t.sqlite3"))

    def boom(*_a, **_k):
        raise sqlite3.OperationalError("disk I/O error")

    db._add_watched_nocommit = boom
    with pytest.raises(sqlite3.OperationalError):
        db.add_watched_and_record_outcome(
            "c1", "شات", 99, "running", 7105, outbox.now_iso(), uo.DURABLE_COMPLETED,
        )

    assert db.update_outcome(7105) is None
    assert db.is_update_acknowledgment_eligible(7105) is False


# ============================================================================
# 3) التكرار: نفس التحديث مرتين ما يكرّرش الأثر ولا يفسد الحالة
# ============================================================================
def test_duplicate_watch_update_no_duplicate_state(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    now = outbox.now_iso()
    # `new_lifecycle=False` = نفس سلوك الـ handler (double-tap يحافظ على الدورة).
    db.add_watched_and_record_outcome(
        "c1", "شات", 99, "running", 7201, now, uo.DURABLE_COMPLETED, new_lifecycle=False,
    )
    first = db.get_watched("c1")

    # إعادة تسليم نفس التحديث (نفس update_id) — الأثر upsert غير ضار، مفيش صفوف زيادة.
    db.add_watched_and_record_outcome(
        "c1", "شات", 99, "running", 7201, now, uo.DURABLE_COMPLETED, new_lifecycle=False,
    )

    assert [w.conversation_id for w in db.list_watched()] == ["c1"]
    assert db.get_watched("c1").watch_seq == first.watch_seq  # نفس الدورة (double-tap)
    assert db.update_outcome(7201) == uo.DURABLE_COMPLETED


def test_duplicate_unwatch_update_consistent(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1")
    now = outbox.now_iso()

    db.remove_watched("c1", update_id=7202, now=now, outcome=uo.DURABLE_COMPLETED)
    db.remove_watched("c1", update_id=7202, now=now, outcome=uo.DURABLE_COMPLETED)  # no-op

    assert db.list_watched() == []
    assert db.update_outcome(7202) == uo.DURABLE_COMPLETED


# ============================================================================
# 4) فشل تيليجرام بعد الـ commit ⇒ F-1 محفوظ (حالة + نتيجة ثابتة، دليل فشل منفصل)
# ============================================================================
def _assert_f1_preserved(db: Database, update_id: int, *, failure: str) -> None:
    assert db.update_outcome(update_id) == uo.DURABLE_COMPLETED
    assert db.is_update_acknowledgment_eligible(update_id) is True
    assert db.update_is_processed(update_id) is True
    assert db.update_failure(update_id) == failure


def test_watch_telegram_timeout_preserves_commit(tmp_path, monkeypatch):
    client = FakeOpenHands({CID_A: _conv(CID_A)})
    app = _build_app(tmp_path, monkeypatch, client=client, edit_exc=TimedOut())
    db = app.bot_data["db"]

    _drive(app, _cb_update(app, 7301, f"watch:{CID_A}"))

    assert db.is_watched(CID_A) is True  # الالتزام المحلي ثابت (مفيش تراجع)
    _assert_f1_preserved(db, 7301, failure=uo.FAILED_TRANSIENT)
    db.close()


def test_unwatch_telegram_timeout_preserves_commit(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch, edit_exc=TimedOut())
    db = app.bot_data["db"]
    db.add_watched(CID_A)

    _drive(app, _cb_update(app, 7302, f"unwatch:{CID_A}"))

    assert db.is_watched(CID_A) is False
    _assert_f1_preserved(db, 7302, failure=uo.FAILED_TRANSIENT)
    db.close()


def test_watch_telegram_bad_request_no_rollback_no_replay(tmp_path, monkeypatch):
    """فشل تيليجرام دائم: الالتزام والنتيجة يفضلوا، والتحديث **مش** يتسجّل قابلًا لإعادة التنفيذ."""
    client = FakeOpenHands({CID_A: _conv(CID_A)})
    app = _build_app(
        tmp_path, monkeypatch, client=client, edit_exc=BadRequest("message can't be edited")
    )
    db = app.bot_data["db"]

    _drive(app, _cb_update(app, 7303, f"watch:{CID_A}"))

    assert db.is_watched(CID_A) is True
    assert db.update_outcome(7303) == uo.DURABLE_COMPLETED
    assert db.update_is_processed(7303) is True  # الديدَب مصدر الحقيقة ⇒ مفيش إعادة تنفيذ
    assert db.update_failure(7303) == uo.FAILED_PERMANENT
    db.close()


def test_unwatch_telegram_bad_request_no_rollback_no_replay(tmp_path, monkeypatch):
    app = _build_app(
        tmp_path, monkeypatch, edit_exc=BadRequest("message can't be edited")
    )
    db = app.bot_data["db"]
    db.add_watched(CID_A)

    _drive(app, _cb_update(app, 7304, f"unwatch:{CID_A}"))

    assert db.is_watched(CID_A) is False
    assert db.update_outcome(7304) == uo.DURABLE_COMPLETED
    assert db.update_is_processed(7304) is True
    assert db.update_failure(7304) == uo.FAILED_PERMANENT
    db.close()


def test_failure_recording_failure_does_not_downgrade_committed_outcome(tmp_path, monkeypatch):
    """تعذّر تسجيل دليل الفشل نفسه ⇒ النتيجة المؤهّلة الملتزمة ما تتخفّضش ولا تتلوّث."""
    client = FakeOpenHands({CID_A: _conv(CID_A)})
    app = _build_app(tmp_path, monkeypatch, client=client, edit_exc=TimedOut())
    db = app.bot_data["db"]

    real_mark = db.mark_update_outcome
    calls = {"n": 0}

    def flaky(update_id, now, outcome, **kw):
        # نداء الالتزام الذرّي ينجح؛ نداء تسجيل الفشل (بعد الـ commit) يفشل.
        calls["n"] += 1
        if calls["n"] > 1:
            raise sqlite3.OperationalError("disk I/O error")
        return real_mark(update_id, now, outcome, **kw)

    db.mark_update_outcome = flaky

    _drive(app, _cb_update(app, 7401, f"watch:{CID_A}"))

    assert db.is_watched(CID_A) is True
    assert db.update_outcome(7401) == uo.DURABLE_COMPLETED  # مفيش تخفيض
    assert db.is_update_acknowledgment_eligible(7401) is True
    db.close()


# ============================================================================
# 5) ثبات الالتزام بعد إغلاق/إعادة فتح القاعدة
# ============================================================================
def test_committed_state_and_outcome_survive_reopen(tmp_path):
    path = str(tmp_path / "t.sqlite3")
    db = Database(path)
    db.add_watched_and_record_outcome(
        "c1", "شات", 99, "running", 7501, outbox.now_iso(), uo.DURABLE_COMPLETED,
    )
    db.remove_watched(
        "c2", update_id=7502, now=outbox.now_iso(), outcome=uo.DURABLE_COMPLETED,
    )
    db.close()

    reopened = Database(path)
    assert reopened.is_watched("c1") is True
    assert reopened.get_watched("c1").last_state == "running"
    assert reopened.update_outcome(7501) == uo.DURABLE_COMPLETED
    assert reopened.update_outcome(7502) == uo.DURABLE_COMPLETED
    reopened.close()


# ============================================================================
# 6) الإلغاء ينتشر (مفيش كتم) — الحالة والنتيجة ما يتسجّلوش
# ============================================================================
def test_watch_cancellation_propagates_without_commit(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))

    def boom(*_a, **_k):
        raise asyncio.CancelledError()

    db._add_watched_nocommit = boom
    with pytest.raises(asyncio.CancelledError):
        db.add_watched_and_record_outcome(
            "c1", "شات", 99, "running", 7601, outbox.now_iso(), uo.DURABLE_COMPLETED,
        )

    assert db.is_watched("c1") is False
    assert db.update_outcome(7601) is None


def test_unwatch_cancellation_propagates_without_commit(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1")

    def boom(*_a, **_k):
        raise asyncio.CancelledError()

    db._remove_watched_nocommit = boom
    with pytest.raises(asyncio.CancelledError):
        db.remove_watched(
            "c1", update_id=7602, now=outbox.now_iso(), outcome=uo.DURABLE_COMPLETED,
        )

    assert db.is_watched("c1") is True
    assert db.update_outcome(7602) is None


# ============================================================================
# 7) ثوابت الاتساق: نتيجة بلا حالة / حالة بلا نتيجة مش ممكنة
# ============================================================================
def test_no_outcome_without_watcher_row_after_failure(tmp_path):
    """لو الشات عليه شاهد حذف (رفض إحياء) ⇒ مفيش صف **ومفيش** نتيجة (مش جزئي)."""
    db = Database(str(tmp_path / "t.sqlite3"))
    db.begin_remote_deletion("c1", outbox.now_iso())

    written = db.add_watched_and_record_outcome(
        "c1", "شات", 99, "running", 7701, outbox.now_iso(), uo.DURABLE_COMPLETED,
        reengage=False,
    )

    assert written is False
    assert db.is_watched("c1") is False
    assert db.update_outcome(7701) is None  # مفيش نتيجة بلا حالة
    assert db.is_update_acknowledgment_eligible(7701) is False


def test_watch_pending_delivery_reconciled_in_same_transaction(tmp_path):
    """دورة جديدة تسوّي أي تسليم معلّق **داخل نفس المعاملة** (الدليل ما يتفقدش)."""
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1")
    db.set_pending_delivery("c1", "finished")

    db.add_watched_and_record_outcome(
        "c1", "شات", 99, "running", 7801, outbox.now_iso(), uo.DURABLE_COMPLETED,
    )

    assert db.get_watched("c1").pending_delivery_state is None
    assert db.get_notification_state("c1").notified_status == "finished"
    assert db.update_outcome(7801) == uo.DURABLE_COMPLETED


def test_unwatch_completes_pending_delivery_in_same_transaction(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1")
    db.set_pending_delivery("c1", "finished")

    db.remove_watched(
        "c1", update_id=7802, now=outbox.now_iso(), outcome=uo.DURABLE_COMPLETED,
    )

    assert db.is_watched("c1") is False
    assert db.get_notification_state("c1").notified_status == "finished"  # دليل التسليم محفوظ
    assert db.update_outcome(7802) == uo.DURABLE_COMPLETED


def test_processed_updates_remains_authoritative_for_ack(tmp_path):
    """`update_failures` لا يجعل تحديثًا ملتزمًا قابلًا لإعادة التنفيذ."""
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched_and_record_outcome(
        "c1", "شات", 99, "running", 7901, outbox.now_iso(), uo.DURABLE_COMPLETED,
    )
    db.mark_update_outcome(7901, outbox.now_iso(), uo.FAILED_TRANSIENT, reason="TimedOut")

    assert db.update_is_processed(7901) is True
    assert db.is_update_acknowledgment_eligible(7901) is True


# ============================================================================
# 8) مسار المراقب (Watcher.unwatch) — الفرعان: تلميح مطابق وبدونه
# ============================================================================
def test_watcher_unwatch_with_matching_hint_is_atomic(tmp_path):
    """تلميح مطابق ⇒ إكمال التسجيل + النتيجة في معاملة واحدة (حالة + نتيجة)."""
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1", "شات", chat_id=99)
    w = Watcher(_FakeClient({}), db, _FakeBot(), chat_id=1)

    seq = db.get_watched("c1").watch_seq
    w._marker_pending["c1"] = ("finished", seq)  # تلميح مطابق لنفس الدورة

    w.unwatch(
        "c1", update_id=9901, now=outbox.now_iso(), outcome=uo.DURABLE_COMPLETED,
    )

    assert db.is_watched("c1") is False
    assert db.get_notification_state("c1").notified_status == "finished"
    assert db.update_outcome(9901) == uo.DURABLE_COMPLETED
    assert "c1" not in w._marker_pending


def test_watcher_unwatch_without_hint_is_atomic(tmp_path):
    """بدون تلميح ⇒ إزالة عادية + النتيجة في نفس المعاملة."""
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1")

    w = Watcher(_FakeClient({}), db, _FakeBot(), chat_id=1)

    w.unwatch("c1", update_id=9902, now=outbox.now_iso(), outcome=uo.DURABLE_COMPLETED)

    assert db.is_watched("c1") is False
    assert db.update_outcome(9902) == uo.DURABLE_COMPLETED


def test_watcher_unwatch_failure_keeps_state_and_hint(tmp_path):
    """فشل الكتابة ⇒ الصف والتلميح بيفضلوا (retry آمن)، مفيش نتيجة."""
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_watched("c1")
    w = Watcher(_FakeClient({}), db, _FakeBot(), chat_id=1)
    seq = db.get_watched("c1").watch_seq
    w._marker_pending["c1"] = ("finished", seq)

    def boom(*_a, **_k):
        raise sqlite3.OperationalError("disk I/O error")

    db.remove_watched_completing = boom

    with pytest.raises(sqlite3.OperationalError):
        w.unwatch("c1", update_id=9903, now=outbox.now_iso(), outcome=uo.DURABLE_COMPLETED)

    assert db.is_watched("c1") is True
    assert w._marker_pending["c1"] == ("finished", seq)  # التلميح بيفضل
    assert db.update_outcome(9903) is None
