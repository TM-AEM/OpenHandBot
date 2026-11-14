"""OHB2-P0-A3/F1-1a+F1-1b — التوجيه الواعي بحالة الدفعة (D-32).

المشكلة (F1-1a/F1-1b): استعلامات A3 كانت مقيّدة بـ`status=pending` فقط، فدفعة بحالة
**غير `pending`** (`intent_recorded`/`dispatching`/`uncertain`/`delivered`/`expired`/
`rejected`/`failed`) ما كانتش تُلاحظ ⇒ نصّ تالٍ **يسقط لمسار البرومت العادي** (outbox/إرسال).

سياسة **D-32** (محسومة):
- حالات **غير محسومة** (`intent_recorded`/`dispatching`/`uncertain`) ⇒ **تحجب** البرومت العادي.
- حالات **نهائية** (`delivered`/`expired`/`rejected`/`failed`) ⇒ **ما بتحجبش** برومتًا جديدًا
  بذاتها، لكن **لا** تحويل/إحياء تلقائي لنصّ قديم.
- مفيش دفعة ذات صلة ⇒ البرومت العادي كما هو.

الاختبارات بتشتغل على `Application.process_update` الحقيقي + قاعدة SQLite حقيقية + عميل
وهمي (بلا شبكة). بتغطّي **كل حالة على حدة** + العزل بين المستخدمين + عدم وجود آثار بعيدة.
"""
from __future__ import annotations

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

CID_B = "22222222333344445555666677778888"   # محادثة تانية صالحة (32 محرف hex)

U_F1 = 2_300_000  # نطاق معرّفات تحديث فريد عبر الملف


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


class _F1:
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


def _harness(tmp_path, monkeypatch, client=None) -> _F1:
    _patch_telegram(monkeypatch)
    replies: list[str] = []

    async def _reply_text(self, text, **kw):
        replies.append(text)
        return Message(message_id=1, date=None, chat=self.chat)

    monkeypatch.setattr("telegram.Message.reply_text", _reply_text)
    h = Harness(tmp_path, client=client)
    return _F1(h, replies)


def _client() -> FakeOpenHands:
    return FakeOpenHands({CID_A: _conv(CID_A, "owner/repo"), CID_B: _conv(CID_B, "owner/repo")})


def _no_remote(a: _F1) -> None:
    """لا آثار بعيدة ولا صفّ outbox (محلي فقط)."""
    assert a.db.count_outbox() == 0
    assert a.h.client.sends == [] and a.h.client.creates == [] and a.h.client.resumes == []


# ============================================================================
# 1) التصنيف (وحدة القاعدة): مصدر قرار واحد — كل حالة على حدة
# ============================================================================
def test_classify_no_batch_is_none(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    r = db.classify_attachment_routing(OWNER_ID, now_iso=_iso(datetime.now(timezone.utc)))
    assert r.state is AttachmentRoutingState.NONE


@pytest.mark.parametrize("status", [ATTACHMENT_BATCH_INTENT_RECORDED,
                                     ATTACHMENT_BATCH_DISPATCHING,
                                     ATTACHMENT_BATCH_UNCERTAIN])
def test_classify_unresolved_states(tmp_path, status):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.create_attachment_batch("b1", OWNER_ID, CID_A, _live_t0(), status=status)
    r = db.classify_attachment_routing(OWNER_ID, now_iso=_iso(datetime.now(timezone.utc)))
    assert r.state is AttachmentRoutingState.UNRESOLVED
    assert [b.batch_id for b in r.unresolved_batches] == ["b1"]


@pytest.mark.parametrize("status", [ATTACHMENT_BATCH_DELIVERED,
                                     ATTACHMENT_BATCH_EXPIRED,
                                     ATTACHMENT_BATCH_REJECTED,
                                     ATTACHMENT_BATCH_FAILED])
def test_classify_terminal_states(tmp_path, status):
    # OHB2-P0-A3/D-34: دفعة نهائية + **لا** دليل هوية للرسالة ⇒ `TERMINAL_UNPROVEN`
    # (فشل مغلق). غياب دليل الهوية **ليس** دليلًا على رسالة جديدة.
    db = Database(str(tmp_path / "t.sqlite3"))
    db.create_attachment_batch("b1", OWNER_ID, CID_A, _live_t0(), status=status)
    r = db.classify_attachment_routing(OWNER_ID, now_iso=_iso(datetime.now(timezone.utc)))
    assert r.state is AttachmentRoutingState.TERMINAL_UNPROVEN


def test_classify_terminal_with_identity_is_associated(tmp_path):
    # OHB2-P0-A3/D-34: دفعة نهائية + دليل هوية للرسالة ⇒ `TERMINAL_ASSOCIATED` (فشل مغلق).
    db = Database(str(tmp_path / "t.sqlite3"))
    db.create_attachment_batch("b1", OWNER_ID, CID_A, _live_t0(),
                               status=ATTACHMENT_BATCH_DELIVERED)
    db._conn.execute(
        "INSERT INTO attachment_message_identity "
        "(telegram_id, chat_id, message_id, batch_id, conversation_id, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (OWNER_ID, CHAT_ID, 5, "b1", CID_A, _iso(datetime.now(timezone.utc))),
    )
    db._conn.commit()
    r = db.classify_attachment_routing(
        OWNER_ID, now_iso=_iso(datetime.now(timezone.utc)), chat_id=CHAT_ID, message_id=5
    )
    assert r.state is AttachmentRoutingState.TERMINAL_ASSOCIATED


def test_classify_live_single_pending(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.create_attachment_batch("b1", OWNER_ID, CID_A, _live_t0())
    r = db.classify_attachment_routing(OWNER_ID, now_iso=_iso(datetime.now(timezone.utc)))
    assert r.state is AttachmentRoutingState.LIVE
    assert r.live_batches[0].batch_id == "b1"


def test_classify_multi_live_pending(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.create_attachment_batch("b1", OWNER_ID, CID_A, _live_t0())
    db.create_attachment_batch("b2", OWNER_ID, CID_B, _live_t0())
    r = db.classify_attachment_routing(OWNER_ID, now_iso=_iso(datetime.now(timezone.utc)))
    assert r.state is AttachmentRoutingState.MULTI_LIVE


def test_classify_expired_pending(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.create_attachment_batch("b1", OWNER_ID, CID_A, _expired_t0())
    r = db.classify_attachment_routing(OWNER_ID, now_iso=_iso(datetime.now(timezone.utc)))
    assert r.state is AttachmentRoutingState.EXPIRED_PENDING


def test_classify_invalid_t0_pending_is_expired_pending_not_none(tmp_path):
    # F-1: دفعة `pending` بـ`t0` غير صالح **مش حيّة** ⇒ لازم تتصنّف «منتهية» (فشل مغلق)،
    # مش `NONE` (اللي كان بيسمح بالسقوط لمسار البرومت العادي).
    db = Database(str(tmp_path / "t.sqlite3"))
    db.create_attachment_batch("b1", OWNER_ID, CID_A, "NOT-A-DATE")
    r = db.classify_attachment_routing(OWNER_ID, now_iso=_iso(datetime.now(timezone.utc)))
    assert r.state is AttachmentRoutingState.EXPIRED_PENDING


def test_classify_unresolved_beats_live(tmp_path):
    # غير محسومة + حيّة معًا ⇒ **غير محسومة** تحجب (أولوية الترتيب).
    db = Database(str(tmp_path / "t.sqlite3"))
    db.create_attachment_batch("u", OWNER_ID, CID_A, _live_t0(),
                               status=ATTACHMENT_BATCH_INTENT_RECORDED)
    db.create_attachment_batch("l", OWNER_ID, CID_B, _live_t0())
    r = db.classify_attachment_routing(OWNER_ID, now_iso=_iso(datetime.now(timezone.utc)))
    assert r.state is AttachmentRoutingState.UNRESOLVED


def test_classify_is_owner_scoped(tmp_path):
    # عزل: دفعة غير محسومة لمستخدم تاني **ما تأثّرش** تصنيف المالك.
    db = Database(str(tmp_path / "t.sqlite3"))
    db.create_attachment_batch("other", 999, CID_A, _live_t0(),
                               status=ATTACHMENT_BATCH_INTENT_RECORDED)
    r = db.classify_attachment_routing(OWNER_ID, now_iso=_iso(datetime.now(timezone.utc)))
    assert r.state is AttachmentRoutingState.NONE


# ============================================================================
# 2) الحالات غير المحسومة **تحجب** البرومت العادي (كل حالة على حدة) — F1-1a
# ============================================================================
@pytest.mark.parametrize("status", [ATTACHMENT_BATCH_INTENT_RECORDED,
                                     ATTACHMENT_BATCH_DISPATCHING,
                                     ATTACHMENT_BATCH_UNCERTAIN])
def test_unresolved_state_blocks_ordinary_prompt(tmp_path, monkeypatch, status):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1", status=status)

    a.process(U_F1 + 1, "برومت")
    a.h.deliver_pending()

    assert a.db.update_outcome(U_F1 + 1) == uo.REJECTED_INELIGIBLE
    assert uo.is_ack_eligible(a.db.update_outcome(U_F1 + 1)) is True
    assert a.batch("b1").status == status          # ما اتلمستش
    assert a.replies == [h_mod.ATTACHMENT_TEXT_UNRESOLVED_TEXT]
    _no_remote(a)


def test_unresolved_in_other_conversation_still_blocks(tmp_path, monkeypatch):
    # دفعة غير محسومة في محادثة أخرى لنفس المستخدم ⇒ **تحجب** (لا توجيه صامت لمحادثة أخرى).
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)  # route لمحادثة مختلفة عن الدفعة
    a.mkbatch(cid=CID_B, t0=_live_t0(), batch_id="b1", status=ATTACHMENT_BATCH_INTENT_RECORDED)

    a.process(U_F1 + 2, "برومت")
    a.h.deliver_pending()

    assert a.db.update_outcome(U_F1 + 2) == uo.REJECTED_INELIGIBLE
    assert a.batch("b1").status == ATTACHMENT_BATCH_INTENT_RECORDED
    _no_remote(a)


def test_multiple_unresolved_batches_block(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(cid=CID_A, t0=_live_t0(), batch_id="u1", status=ATTACHMENT_BATCH_INTENT_RECORDED)
    a.mkbatch(cid=CID_B, t0=_live_t0(), batch_id="u2", status=ATTACHMENT_BATCH_UNCERTAIN)

    a.process(U_F1 + 3, "برومت")

    assert a.db.update_outcome(U_F1 + 3) == uo.REJECTED_INELIGIBLE
    _no_remote(a)


def test_conflicting_pending_and_unresolved_blocks(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(cid=CID_A, t0=_live_t0(), batch_id="live", status=ATTACHMENT_BATCH_PENDING)
    a.mkbatch(cid=CID_A, t0=_live_t0(), batch_id="unres", status=ATTACHMENT_BATCH_INTENT_RECORDED)

    a.process(U_F1 + 4, "برومت")

    assert a.db.update_outcome(U_F1 + 4) == uo.REJECTED_INELIGIBLE
    assert a.batch("live").status == ATTACHMENT_BATCH_PENDING   # ما اتحوّلش لنيّة
    assert a.batch("unres").status == ATTACHMENT_BATCH_INTENT_RECORDED
    _no_remote(a)


def test_unresolved_duplicate_update_single_rejection(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1", status=ATTACHMENT_BATCH_INTENT_RECORDED)

    a.process(U_F1 + 5, "برومت")
    a.process(U_F1 + 5, "برومت")  # مكرّر ⇒ حاجز الديدَب

    assert a.db.update_outcome(U_F1 + 5) == uo.REJECTED_INELIGIBLE
    assert len(a.replies) == 1     # ردّ واحد بس
    _no_remote(a)


# ============================================================================
# 3) الحالات النهائية ⇒ **فشل مغلق** عند غياب دليل الهوية (D-34) — ألغى سلوك D-32 بند 2 القديم
# ============================================================================
@pytest.mark.parametrize("status", [ATTACHMENT_BATCH_DELIVERED,
                                     ATTACHMENT_BATCH_EXPIRED,
                                     ATTACHMENT_BATCH_REJECTED,
                                     ATTACHMENT_BATCH_FAILED])
def test_terminal_state_blocks_unproven_new_prompt(tmp_path, monkeypatch, status):
    # OHB2-P0-A3/D-34: دفعة نهائية + نصّ بلا دليل هوية ⇒ `TERMINAL_UNPROVEN` ⇒ رفض نهائي.
    # غياب دليل الهوية **ليس** دليلًا على برومت جديد ⇒ **لا** سقوط لمسار البرومت/`outbox`.
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1", status=status)

    a.process(U_F1 + 10, "نصّ بلا دليل هوية")
    a.h.deliver_pending()

    assert a.db.update_outcome(U_F1 + 10) == uo.REJECTED_INELIGIBLE
    assert a.h.client.sends == []
    assert a.db.count_outbox() == 0
    assert a.batch("b1").status == status  # الدفعة النهائية ما اتلمستش


def test_terminal_batch_other_conversation_blocks_new_text(tmp_path, monkeypatch):
    # OHB2-P0-A3/D-34 (N-2): دفعة نهائية لمحادثة **أخرى** ⇒ النصّ غير المُثبَت الارتباط بها
    # يُرفض (لا إحياء/لا تحويل/لا استبدال محادثة). سلوك الحجب عبر المحادثات **مُعتمد ومُفصَح عنه**.
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(cid=CID_B, t0=_live_t0(), batch_id="old", status=ATTACHMENT_BATCH_EXPIRED)

    a.process(U_F1 + 11, "برومت")
    a.h.deliver_pending()

    assert a.db.update_outcome(U_F1 + 11) == uo.REJECTED_INELIGIBLE
    assert a.h.client.sends == []
    assert a.db.count_outbox() == 0
    assert a.batch("old").status == ATTACHMENT_BATCH_EXPIRED


def test_delivered_batch_text_is_not_replayed(tmp_path, monkeypatch):
    # نصّ دفعة `delivered` (مستهلك) **ما يتكرّرش/يُعاد تفسيره** ⇒ فشل مغلق (D-34).
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1", status=ATTACHMENT_BATCH_DELIVERED)
    # نحاكي نصًّا مخزَّنًا للدفعة (اتستهلك عند التسليم).
    a.db._conn.execute(
        "UPDATE attachment_batches SET intent_text=? WHERE batch_id=?",
        ("النصّ القديم المستهلك", "b1"),
    )
    a.db._conn.commit()

    a.process(U_F1 + 12, "رسالة جديدة")
    a.h.deliver_pending()

    # D-34: النصّ غير المُثبَت الارتباط بدفعة نهائية يُرفض (لا إرسال، لا إعادة تفسير للنصّ القديم).
    assert a.db.update_outcome(U_F1 + 12) == uo.REJECTED_INELIGIBLE
    assert a.h.client.sends == []
    assert a.db.count_outbox() == 0
    assert a.batch("b1").intent_text == "النصّ القديم المستهلك"  # ما اتعادش/اتغيّرش


# ============================================================================
# 4) دفعة `pending` منتهية ⇒ لا سقوط لمسار البرومت (لا تحويل/إحياء) — F1-1a
# ============================================================================
def test_expired_pending_text_does_not_fall_through(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_expired_t0(), batch_id="b1")

    a.process(U_F1 + 20, "برومت متأخّر")
    a.h.deliver_pending()

    assert a.db.update_outcome(U_F1 + 20) == uo.REJECTED_INELIGIBLE
    assert a.batch("b1").status == ATTACHMENT_BATCH_PENDING
    assert a.batch("b1").intent_text is None
    assert a.replies == [h_mod.ATTACHMENT_TEXT_EXPIRED_TEXT]
    _no_remote(a)


def test_invalid_t0_pending_text_does_not_fall_through(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0="NOT-A-DATE", batch_id="b1")

    a.process(U_F1 + 21, "برومت")
    a.h.deliver_pending()

    assert a.db.update_outcome(U_F1 + 21) == uo.REJECTED_INELIGIBLE
    _no_remote(a)


# ============================================================================
# 5) الحالة الحيّة الوحيدة: مسار النصّ المصاحب كما هو (لا تراجع)
# ============================================================================
def test_live_single_batch_routes_to_attachment_path(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1")

    a.process(U_F1 + 30, "نصّ مصاحب")

    assert a.batch("b1").status == ATTACHMENT_BATCH_INTENT_RECORDED
    assert a.batch("b1").intent_text == "نصّ مصاحب"
    assert a.db.update_outcome(U_F1 + 30) == uo.DURABLE_INTENT_RECORDED
    _no_remote(a)


def test_no_batch_preserves_ordinary_prompt(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)

    a.process(U_F1 + 31, "برومت عادي")
    a.h.deliver_pending()

    assert a.h.client.sends == [(CID_A, "برومت عادي")]
    assert a.db.update_outcome(U_F1 + 31) == uo.DURABLE_INTENT_RECORDED


# ============================================================================
# 6) فشل القاعدة أثناء التصنيف ⇒ فشل مغلق غير مؤهّل (fail-closed)
# ============================================================================
def test_db_failure_during_classify_is_not_ack_eligible(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1")

    def _boom(*_a, **_k):
        raise RuntimeError("simulated classify failure")

    monkeypatch.setattr(a.db, "classify_attachment_routing", _boom)

    a.process(U_F1 + 40, "برومت")  # الاستثناء بيتبلع في PTB (يسجّل فشل)

    outcome = a.db.update_outcome(U_F1 + 40)
    assert outcome is not None and not uo.is_ack_eligible(outcome)
    _no_remote(a)


def test_unresolved_rejection_is_ack_eligible_via_boundary(tmp_path, monkeypatch):
    # حدّ الإقرار الحقيقي: رفض غير المحسومة مؤهّل ⇒ الحدّ يتقدّم.
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1", status=ATTACHMENT_BATCH_INTENT_RECORDED)

    a.process(U_F1 + 41, "برومت")

    outcomes = {U_F1 + 41: a.db.update_outcome(U_F1 + 41)}
    assert uo.acknowledgment_boundary([U_F1 + 41], outcomes) == U_F1 + 41
