"""OHB2-P0-A3-TERMINAL-BATCH-ROUTING-COMPLETE-REMEDIATION — اختبارات عدائية على الحدّ الحقيقي.

بتشتغل على `Application.process_update` الحقيقي (نفس مسار الإنتاج) + قاعدة SQLite حقيقية +
عميل OpenHands وهمي (بلا شبكة). بتغطّي:

- **F2 (مُصلَح):** حالة دفعة **مجهولة/تالفة** ⇒ رفض مغلق (`failed_*` غير مؤهّل، بلا outbox
  وبلا نداء بعيد)، بدل ما تُصنَّف `NONE` وتسقط لمسار البرومت. وأخطاء قراءة القاعدة كذلك.
- **الحالات غير المحسومة/الحيّة (محفوظة):** تحجب/توجّه كما هو (لا انحدار).
- **F1 (مُصلَح — D-33/D-34/D-35):** النصّ المرتبط بدفعة **نهائية** أو **غير المُثبَت** الارتباط
  بها يفشل مغلقًا (`TERMINAL_ASSOCIATED`/`TERMINAL_UNPROVEN` ⇒ `REJECTED_INELIGIBLE`) — لا سقوط
  لمسار البرومت/`outbox`. دليل الهوية رسالة↔دفعة متين ومستقلّ عن تقليم `processed_updates`.

**مهم:** الاختبارات السبعة دي كانت `xfail(strict=True)` لحين حلّ F1؛ بُعد التنفيذ (D-34) صارت
**تنجح فعليًّا** (لا `xfail`) — أُزيلت العلامة فقط، بلا أي إضعاف للتأكيدات.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from telegram import Chat, Message

import bot.handlers as h_mod
from bot import update_outcomes as uo
from bot.db import (
    ATTACHMENT_BATCH_DELIVERED,
    ATTACHMENT_BATCH_DISPATCHING,
    ATTACHMENT_BATCH_EXPIRED,
    ATTACHMENT_BATCH_FAILED,
    ATTACHMENT_BATCH_INTENT_RECORDED,
    ATTACHMENT_BATCH_PENDING,
    ATTACHMENT_BATCH_REJECTED,
    ATTACHMENT_BATCH_UNCERTAIN,
    AttachmentBatchIntegrityError,
    AttachmentRoutingState,
    Database,
)

from tests.test_duplicate_update_dispatch import (
    CHAT_ID,
    CID_A,
    OWNER_ID,
    FakeOpenHands,
    Harness,
    _conv,
)

CID_B = "22222222333344445555666677778888"
U = 2_900_000  # نطاق معرّفات تحديث فريد عبر الملف

def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _live_t0() -> str:
    return _iso(datetime.now(timezone.utc) - timedelta(minutes=1))


def _expired_t0() -> str:
    return _iso(datetime.now(timezone.utc) - timedelta(minutes=20))


def _patch_telegram(monkeypatch):
    async def _send_message(self, chat_id=None, text=None, **kw):
        return Message(message_id=1, date=None, chat=Chat(id=chat_id, type="private"))

    async def _edit_message_text(self, text=None, **kw):
        return Message(message_id=1, date=None, chat=Chat(id=CHAT_ID, type="private"))

    async def _noop(self, *a, **k):
        return True

    monkeypatch.setattr("telegram.Bot.send_message", _send_message)
    monkeypatch.setattr("telegram.Bot.edit_message_text", _edit_message_text)
    monkeypatch.setattr("telegram.Bot.answer_callback_query", _noop)
    monkeypatch.setattr("telegram.Bot.set_my_commands", _noop)
    monkeypatch.setattr("telegram.Bot.set_chat_menu_button", _noop)


class _R:
    def __init__(self, h: Harness, replies: list[str]) -> None:
        self.h = h
        self.replies = replies

    @property
    def db(self) -> Database:
        return self.h.db

    def mkbatch(self, cid: str = CID_A, *, t0: str, batch_id: str,
                status: str = ATTACHMENT_BATCH_PENDING, owner: int = OWNER_ID) -> str:
        self.db.create_attachment_batch(batch_id, owner, cid, t0, status=status)
        return batch_id

    def route(self, cid: str = CID_A, kind: str = "route") -> None:
        self.db.set_awaiting(OWNER_ID, cid, kind, title="A")

    def process(self, update_id: int, text: str) -> None:
        self.h.process(self.h.text_update(update_id, text))

    def batch(self, batch_id: str):
        return self.db.get_attachment_batch(batch_id)


def _harness(tmp_path, monkeypatch, client=None) -> _R:
    _patch_telegram(monkeypatch)
    replies: list[str] = []

    async def _reply_text(self, text, **kw):
        replies.append(text)
        return Message(message_id=1, date=None, chat=self.chat)

    monkeypatch.setattr("telegram.Message.reply_text", _reply_text)
    h = Harness(tmp_path, client=client)
    return _R(h, replies)


def _client() -> FakeOpenHands:
    return FakeOpenHands({CID_A: _conv(CID_A, "owner/repo"), CID_B: _conv(CID_B, "owner/repo")})


def _no_remote(a: _R) -> None:
    assert a.db.count_outbox() == 0, "outbox row created"
    assert a.h.client.sends == [], f"remote send: {a.h.client.sends}"
    assert a.h.client.creates == [], f"remote create: {a.h.client.creates}"
    assert a.h.client.resumes == [], f"remote resume: {a.h.client.resumes}"


def _raw_status(db, batch_id: str, status) -> None:
    """يضبط حالة الصفّ مباشرةً (للحالات الشاذّة غير القابلة للإنشاء العادي)."""
    db._conn.execute("UPDATE attachment_batches SET status=? WHERE batch_id=?", (status, batch_id))
    db._conn.commit()


# ============================================================================
# F2 — الحالة المجهولة/التالفة ⇒ رفض مغلق (مُصلَح)
# ============================================================================
def test_f2_unknown_status_classify_raises_integrity(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.create_attachment_batch("b1", OWNER_ID, CID_A, _live_t0(), status="weird_future_status")
    with pytest.raises(AttachmentBatchIntegrityError):
        db.classify_attachment_routing(OWNER_ID, now_iso=_iso(datetime.now(timezone.utc)))


def test_f2_empty_status_classify_raises_integrity(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.create_attachment_batch("b1", OWNER_ID, CID_A, _live_t0(), status="")
    with pytest.raises(AttachmentBatchIntegrityError):
        db.classify_attachment_routing(OWNER_ID, now_iso=_iso(datetime.now(timezone.utc)))


def test_f2_unknown_status_never_reaches_outbox_or_remote(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1", status="weird_future_status")

    a.process(U + 1, "برومت")
    a.h.deliver_pending()

    outcome = a.db.update_outcome(U + 1)
    assert outcome == uo.FAILED_PERMANENT          # فشل تقني دائم، مش نجاح/رفض مؤهّل
    assert uo.is_ack_eligible(outcome) is False    # غير مؤهّل للإقرار (fail-closed)
    assert a.db.acknowledgment_boundary([U + 1]) is None  # الحدّ مايتقدّمش
    _no_remote(a)


def test_f2_future_status_never_reaches_outbox(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1", status="reconciling_v2")

    a.process(U + 2, "برومت")
    a.h.deliver_pending()

    assert a.db.update_outcome(U + 2) == uo.FAILED_PERMANENT
    _no_remote(a)


def test_f2_unknown_status_does_not_broaden_ack(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1", status="bogus")

    a.process(U + 3, "برومت")

    assert uo.is_ack_eligible(a.db.update_outcome(U + 3)) is False


def test_f2_db_read_error_fails_closed_not_none(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1")

    def _boom(*_a, **_k):
        raise sqlite3.OperationalError("simulated read failure")

    monkeypatch.setattr(a.db, "has_unknown_attachment_batch_status", _boom)
    a.process(U + 4, "برومت")

    outcome = a.db.update_outcome(U + 4)
    assert outcome is not None and not uo.is_ack_eligible(outcome)
    _no_remote(a)


def test_f2_unknown_status_is_owner_scoped(tmp_path):
    # حالة مجهولة لمستخدم **تاني** ما ترفعش استثناء للمالك (عزل).
    db = Database(str(tmp_path / "t.sqlite3"))
    db.create_attachment_batch("other", 999, CID_A, _live_t0(), status="weird")
    r = db.classify_attachment_routing(OWNER_ID, now_iso=_iso(datetime.now(timezone.utc)))
    assert r.state is AttachmentRoutingState.NONE


def test_f2_unknown_status_fails_closed_without_any_route(tmp_path, monkeypatch):
    # F2-2 (مراجعة عدائية): التصنيف بيتنادى **دائمًا** على مسار النصّ (بلا شرط route)،
    # فالحالة المجهولة تفشل مغلق حتى مع **غياب route نشط** (لا سقوط لمسار البرومت/outbox).
    a = _harness(tmp_path, monkeypatch, _client())
    # **مفيش** route مقصود.
    a.mkbatch(t0=_live_t0(), batch_id="b1", status="weird_status")

    a.process(U + 5, "برومت بلا route")
    a.h.deliver_pending()

    assert a.db.update_outcome(U + 5) == uo.FAILED_PERMANENT
    assert a.db.acknowledgment_boundary([U + 5]) is None
    _no_remote(a)


def test_f2_unknown_status_boundary_is_fail_closed_until_resolved(tmp_path, monkeypatch):
    # F2-1 (مراجعة عدائية): الحالة المجهولة **مقصود** إنها تفشل مغلق ⇒ الحدّ مايتقدّمش
    # عندها (حجب head-of-line = نفس سلوك أي فشل دائم، مش خاص بالحالة المجهولة). بمجرد ما
    # البيانات تترجع سليمة، التحديثات اللاحقة تتقدّم عاديًّا (مفيش حجب دائم إذا اتحلّت الحالة).
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1", status="weird_status")

    a.process(U + 6, "برومت أوّل")
    assert a.db.acknowledgment_boundary([U + 6]) is None  # محجوب عند الفشل (fail-closed)

    _raw_status(a.db, "b1", ATTACHMENT_BATCH_EXPIRED)  # البيانات اترجعت سليمة
    a.process(U + 7, "برومت تاني")

    # OHB2-P0-A3/D-34: بعد ما الدفعة صارت **نهائية**، النصّ غير المُثبَت الارتباط بها
    # (`TERMINAL_UNPROVEN`) يُرفض نهائيًّا (`REJECTED_INELIGIBLE`) — **لا** نيّة/لا برومت/لا
    # outbox (كان قبل كده يمرّ لمسار البرومت). الفشل المغلق مقصود ومؤهّل للإقرار.
    assert a.db.update_outcome(U + 7) == uo.REJECTED_INELIGIBLE
    assert a.h.client.sends == []
    assert a.db.count_outbox() == 0
    assert a.db.acknowledgment_boundary([U + 7]) == U + 7


# ============================================================================
# الحالات غير المحسومة ⇒ تحجب (محفوظة، لا انحدار)
# ============================================================================
@pytest.mark.parametrize("status", [ATTACHMENT_BATCH_INTENT_RECORDED,
                                     ATTACHMENT_BATCH_DISPATCHING,
                                     ATTACHMENT_BATCH_UNCERTAIN])
def test_unresolved_states_block(tmp_path, monkeypatch, status):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1", status=status)

    a.process(U + 10, "برومت")
    a.h.deliver_pending()

    assert a.db.update_outcome(U + 10) == uo.REJECTED_INELIGIBLE
    assert a.batch("b1").status == status
    assert a.replies == [h_mod.ATTACHMENT_TEXT_UNRESOLVED_TEXT]
    _no_remote(a)


def test_unresolved_blocks_across_conversations(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(cid=CID_B, t0=_live_t0(), batch_id="u", status=ATTACHMENT_BATCH_UNCERTAIN)

    a.process(U + 11, "برومت")
    assert a.db.update_outcome(U + 11) == uo.REJECTED_INELIGIBLE
    _no_remote(a)


# ============================================================================
# الحالات الحيّة/المنتهية (pending) ⇒ كما هو (محفوظ)
# ============================================================================
def test_live_unique_pending_records_intent(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1")

    a.process(U + 20, "نصّ مصاحب")
    assert a.batch("b1").status == ATTACHMENT_BATCH_INTENT_RECORDED
    assert a.batch("b1").intent_text == "نصّ مصاحب"
    assert a.db.update_outcome(U + 20) == uo.DURABLE_INTENT_RECORDED
    _no_remote(a)


def test_expired_pending_rejected(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_expired_t0(), batch_id="b1")

    a.process(U + 21, "برومت متأخّر")
    assert a.db.update_outcome(U + 21) == uo.REJECTED_INELIGIBLE
    assert a.batch("b1").status == ATTACHMENT_BATCH_PENDING
    assert a.batch("b1").intent_text is None
    _no_remote(a)


def test_invalid_t0_pending_rejected(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0="NOT-A-DATE", batch_id="b1")

    a.process(U + 22, "برومت")
    assert a.db.update_outcome(U + 22) == uo.REJECTED_INELIGIBLE
    _no_remote(a)


def test_invalid_now_fails_closed(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1")
    orig = a.db.classify_attachment_routing

    def _bad_now(telegram_id, *, now_iso, **_kw):
        return orig(telegram_id, now_iso="NOT-A-DATE")

    monkeypatch.setattr(a.db, "classify_attachment_routing", _bad_now)
    a.process(U + 23, "برومت")
    # «الآن» غير صالح ⇒ الدفعة مش حيّة ⇒ منتهية ⇒ رفض (لا سقوط).
    assert a.db.update_outcome(U + 23) == uo.REJECTED_INELIGIBLE
    _no_remote(a)


def test_multiple_live_pending_block(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(cid=CID_A, t0=_live_t0(), batch_id="b1")
    a.mkbatch(cid=CID_B, t0=_live_t0(), batch_id="b2")

    a.process(U + 24, "برومت")
    assert a.db.update_outcome(U + 24) == uo.REJECTED_INELIGIBLE
    _no_remote(a)


def test_live_pending_other_conversation_route_mismatch(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(cid=CID_B, t0=_live_t0(), batch_id="b1")

    a.process(U + 25, "برومت")
    assert a.db.update_outcome(U + 25) == uo.REJECTED_INELIGIBLE
    _no_remote(a)


# ============================================================================
# F1 — النصّ المرتبط بدفعة نهائية (مُعطَّل: الثابتة المطلوبة غير مُحقَّقة)
# ============================================================================
@pytest.mark.parametrize("status", [ATTACHMENT_BATCH_EXPIRED,
                                     ATTACHMENT_BATCH_REJECTED,
                                     ATTACHMENT_BATCH_FAILED])
def test_f1_terminal_associated_text_must_not_reach_outbox(tmp_path, monkeypatch, status):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)  # route نشط لنفس محادثة الدفعة النهائية
    a.mkbatch(t0=_live_t0(), batch_id="b1", status=status)

    a.process(U + 30, "نصّ قد يخصّ الدفعة النهائية")
    a.h.deliver_pending()

    # الثابتة المطلوبة (D-32 §E.4/§E.6): لا سقوط تلقائي ولا إرسال.
    assert a.db.count_outbox() == 0
    assert a.h.client.sends == []
    assert a.db.update_outcome(U + 30) != uo.DURABLE_INTENT_RECORDED


def test_f1_delivered_duplicate_text_must_not_be_replayed(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1", status=ATTACHMENT_BATCH_DELIVERED)
    _raw_status(a.db, "b1", ATTACHMENT_BATCH_DELIVERED)
    a.db._conn.execute("UPDATE attachment_batches SET intent_text=? WHERE batch_id=?",
                       ("النصّ القديم المستهلك", "b1"))
    a.db._conn.commit()

    a.process(U + 31, "النصّ القديم المستهلك")
    a.h.deliver_pending()

    assert a.h.client.sends == []   # ممنوع إعادة إرسال نصّ دفعة مُسلَّمة
    assert a.db.count_outbox() == 0


def test_f1_terminal_other_conversation_must_not_auto_route(tmp_path, monkeypatch):
    # دفعة نهائية لمحادثة أخرى + route لمحادثة مختلفة: الثابتة المطلوبة = لا ربط تلقائي.
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(cid=CID_B, t0=_live_t0(), batch_id="old", status=ATTACHMENT_BATCH_EXPIRED)

    a.process(U + 32, "نصّ")
    a.h.deliver_pending()

    assert a.db.count_outbox() == 0
    assert a.h.client.sends == []


def test_f1_multiple_terminal_batches_must_not_auto_route(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(cid=CID_A, t0=_live_t0(), batch_id="t1", status=ATTACHMENT_BATCH_EXPIRED)
    a.mkbatch(cid=CID_B, t0=_live_t0(), batch_id="t2", status=ATTACHMENT_BATCH_FAILED)

    a.process(U + 33, "نصّ")
    a.h.deliver_pending()

    assert a.db.count_outbox() == 0
    assert a.h.client.sends == []


# ============================================================================
# السباقات (races)
# ============================================================================
def test_race_classification_to_intent_fails_closed(tmp_path, monkeypatch):
    # الدفعة حيّة عند التصنيف لكن بتتحوّل «منتهية» قبل تسجيل النيّة ⇒ فشل مغلق (لا إرسال).
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1")
    orig = a.db.record_attachment_intent

    def _race(*args, **kwargs):
        _raw_status(a.db, "b1", ATTACHMENT_BATCH_EXPIRED)
        return orig(*args, **kwargs)

    monkeypatch.setattr(a.db, "record_attachment_intent", _race)
    a.process(U + 40, "نصّ مصاحب")

    assert a.batch("b1").status == ATTACHMENT_BATCH_EXPIRED
    assert a.db.update_outcome(U + 40) == uo.REJECTED_INELIGIBLE
    _no_remote(a)


def test_race_classification_to_ordinary_prompt_is_fail_closed(tmp_path, monkeypatch):
    # لو الحالة اتحوّلت «منتهية» بين التصنيف والمسار العادي: F1 قائم (مُعطَّل) ⇒ نوثّقه.
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1")

    orig = a.db.classify_attachment_routing

    def _flip_then_classify(telegram_id, *, now_iso, **_kw):
        _raw_status(a.db, "b1", ATTACHMENT_BATCH_EXPIRED)
        return orig(telegram_id, now_iso=now_iso)

    monkeypatch.setattr(a.db, "classify_attachment_routing", _flip_then_classify)
    a.process(U + 41, "نصّ")
    a.h.deliver_pending()

    # D-34: بعد ما الدفعة صارت نهائية بين التصنيف والمسار، النصّ **ما يوصلش** لمسار
    # البرومت/outbox ⇒ رفض نهائي `REJECTED_INELIGIBLE` (كان قبل كده يسقط — F1 مُصلَح).
    assert a.db.count_outbox() == 0
    assert a.h.client.sends == []
    assert a.db.update_outcome(U + 41) == uo.REJECTED_INELIGIBLE


# ============================================================================
# الإقرار: الحجب مؤهّل، الفشل التقني غير مؤهّل
# ============================================================================
def test_ack_boundary_advances_on_rejection(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1", status=ATTACHMENT_BATCH_INTENT_RECORDED)

    a.process(U + 50, "برومت")

    assert a.db.acknowledgment_boundary([U + 50]) == U + 50


def test_ack_boundary_does_not_advance_on_failure(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1", status="bogus")

    a.process(U + 51, "برومت")

    assert a.db.acknowledgment_boundary([U + 51]) is None


# ============================================================================
# العزل بين المستخدمين + لا انحدار للمسار العادي بلا دفعات
# ============================================================================
def test_no_batch_preserves_ordinary_prompt(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)

    a.process(U + 60, "برومت عادي")
    a.h.deliver_pending()

    assert a.h.client.sends == [(CID_A, "برومت عادي")]
    assert a.db.update_outcome(U + 60) == uo.DURABLE_INTENT_RECORDED


def test_terminal_other_user_does_not_affect_owner(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(cid=CID_A, t0=_live_t0(), batch_id="b1", status=ATTACHMENT_BATCH_EXPIRED, owner=999)

    a.process(U + 61, "برومت")
    a.h.deliver_pending()

    assert a.h.client.sends == [(CID_A, "برومت")]
