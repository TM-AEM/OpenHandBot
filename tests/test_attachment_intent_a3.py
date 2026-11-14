"""OHB2-P0-A3 — اختبارات النصّ المصاحب والنيّة المحلية المتينة (D-27/D-29/D-30).

بتغطّي المتطلّبات الدقيقة لـ R4 Stage A3 (محلي فقط — بلا إرسال بعيد):
- نصّ مؤهّل داخل المهلة ⇒ نيّة متينة: النصّ + `intent_recorded` + `durable_intent_recorded`
  **ذرّيًّا** (معاملة واحدة).
- دفعة واحدة بالضبط ⇒ ربط فريد؛ غموض (أكثر من دفعة حيّة، أو دفعة لمحادثة أخرى، أو لا route،
  أو route لمحادثة مختلفة) ⇒ **فشل مغلق** (`rejected_ineligible`).
- دفعة منتهية ⇒ لا إحياء/لا تحويل تلقائي لبرومت ⇒ `rejected_ineligible`.
- نصّ غير مؤهّل (D-28) ⇒ `rejected_ineligible` + ردّ أفضل-جهد.
- `rejected_ineligible` مؤهّلة للإقرار؛ `failed_*` غير مؤهّلة (الفشل التقني fail-closed).
- لا صفّ `outbox` ولا نداء بعيد في مسار A3.
- التعليقات (captions) خارج النطاق (D-31): رسالة بلا `text` ⇒ مش من مسار A3.

بيستخدم التطبيق الحقيقي (`Application.process_update`) وقاعدة SQLite حقيقية، وعميل مزيّف
(بلا شبكة). الساعات **محقونة** عبر `t0` للدفعة (مفيش sleeps).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from telegram import Chat, Message, Update, User

import bot.handlers as h_mod
from bot import outbox
from bot import update_outcomes as uo
from bot.db import (
    ATTACHMENT_BATCH_INTENT_RECORDED,
    ATTACHMENT_BATCH_PENDING,
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

# نطاق معرّفات تحديث فريد عبر الملف (تجنّب التصادم مع ملفات اختبار تانية).
U_A3 = 2_200_000


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# t0 حيّ (داخل المهلة) و t0 منتهٍ (خارجها) — محسوبان وقت التشغيل.
def _live_t0() -> str:
    return _iso(_now() - timedelta(minutes=1))


def _expired_t0() -> str:
    return _iso(_now() - timedelta(minutes=20))


def _patch_telegram(monkeypatch):
    """يعترض نداءات تيليجرام (بلا شبكة) ويلتقط ردود `Message.reply_text`."""

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


class _A3:
    """غلاف صغير حول `Harness` يلتقط ردود `reply_text` ويعرّف مساعدات الدفعات."""

    def __init__(self, h: Harness, replies: list[str]) -> None:
        self.h = h
        self.replies = replies

    @property
    def db(self) -> Database:
        return self.h.db

    def mkbatch(self, cid: str = CID_A, *, t0: str, batch_id: str, status: str = ATTACHMENT_BATCH_PENDING) -> str:
        self.db.create_attachment_batch(batch_id, OWNER_ID, cid, t0, status=status)
        return batch_id

    def route(self, cid: str = CID_A, kind: str = "route") -> None:
        self.db.set_awaiting(OWNER_ID, cid, kind, title="A")

    def tombstone(self, cid: str = CID_A) -> None:
        self.db._conn.execute(
            "INSERT OR IGNORE INTO deleted_conversations(conversation_id, deleted_at) "
            "VALUES(?, ?)",
            (cid, outbox.now_iso()),
        )
        self.db._conn.commit()

    def process(self, update_id: int, text: str) -> None:
        self.h.process(self.h.text_update(update_id, text))

    def batch(self, batch_id: str):
        return self.db.get_attachment_batch(batch_id)


def _harness(tmp_path, monkeypatch, client=None) -> _A3:
    _patch_telegram(monkeypatch)
    replies: list[str] = []

    async def _reply_text(self, text, **kw):
        replies.append(text)
        return Message(message_id=1, date=None, chat=self.chat)

    monkeypatch.setattr("telegram.Message.reply_text", _reply_text)
    h = Harness(tmp_path, client=client)
    return _A3(h, replies)


def _client() -> FakeOpenHands:
    return FakeOpenHands({CID_A: _conv(CID_A, "owner/repo"), CID_B: _conv(CID_B, "owner/repo")})


# ============================================================================
# 1) النجاح: نصّ مؤهّل داخل المهلة ⇒ نيّة متينة ذرّيًّا (بلا outbox/بلا شبكة)
# ============================================================================
def test_eligible_text_within_deadline_records_intent_atomically(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1")

    a.process(U_A3 + 1, "أرسل هذا النصّ مع الملف")

    batch = a.batch("b1")
    assert batch.status == ATTACHMENT_BATCH_INTENT_RECORDED
    assert batch.intent_text == "أرسل هذا النصّ مع الملف"
    assert a.db.update_outcome(U_A3 + 1) == uo.DURABLE_INTENT_RECORDED
    assert uo.is_ack_eligible(a.db.update_outcome(U_A3 + 1)) is True
    # محلي فقط: لا صفّ outbox، ولا نداء بعيد (إرسال/إنشاء/resume).
    assert a.db.count_outbox() == 0
    assert a.h.client.sends == [] and a.h.client.creates == [] and a.h.client.resumes == []
    assert a.replies == [h_mod.ATTACHMENT_TEXT_RECORDED_TEXT]


def test_normalized_text_is_stored_verbatim(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1")

    a.process(U_A3 + 2, "سطر1\r\nسطر2\rسطر3")

    assert a.batch("b1").intent_text == "سطر1\nسطر2\nسطر3"


def test_t0_is_not_changed_by_intent(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    t0 = _live_t0()
    a.mkbatch(t0=t0, batch_id="b1")

    a.process(U_A3 + 3, "نصّ")

    assert a.batch("b1").t0 == t0  # المهلة ما اتمدّتش (I6)


# ============================================================================
# 2) النصّ غير المؤهّل (D-28) ⇒ rejected_ineligible + ردّ
# ============================================================================
@pytest.mark.parametrize(
    "text",
    ["   ", "\t\n", "a\x00b", "a\x07b", "x" * 4097],
    ids=["whitespace", "tab_lf", "nul", "c0", "too_long"],
)
def test_ineligible_text_is_rejected_with_durable_outcome(tmp_path, monkeypatch, text):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1")

    a.process(U_A3 + 10, text)

    assert a.db.update_outcome(U_A3 + 10) == uo.REJECTED_INELIGIBLE
    assert uo.is_ack_eligible(a.db.update_outcome(U_A3 + 10)) is True
    batch = a.batch("b1")
    assert batch.status == ATTACHMENT_BATCH_PENDING  # ما اتحوّلش لنيّة
    assert batch.intent_text is None
    assert a.db.count_outbox() == 0
    assert a.replies == [h_mod.ATTACHMENT_TEXT_AMBIGUOUS_TEXT]


# ============================================================================
# 3) الغموض ⇒ فشل مغلق (D-29)
# ============================================================================
def test_more_than_one_live_batch_is_fail_closed(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(cid=CID_A, t0=_live_t0(), batch_id="b1")
    a.mkbatch(cid=CID_B, t0=_live_t0(), batch_id="b2")

    a.process(U_A3 + 20, "نصّ")

    assert a.db.update_outcome(U_A3 + 20) == uo.REJECTED_INELIGIBLE
    assert a.batch("b1").status == ATTACHMENT_BATCH_PENDING
    assert a.batch("b2").status == ATTACHMENT_BATCH_PENDING
    assert a.batch("b1").intent_text is None and a.batch("b2").intent_text is None
    assert a.replies == [h_mod.ATTACHMENT_TEXT_AMBIGUOUS_TEXT]


def test_two_live_batches_same_conversation_is_fail_closed(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(cid=CID_A, t0=_live_t0(), batch_id="b1")
    a.mkbatch(cid=CID_A, t0=_live_t0(), batch_id="b2")

    a.process(U_A3 + 23, "نصّ")

    assert a.db.update_outcome(U_A3 + 23) == uo.REJECTED_INELIGIBLE
    assert a.batch("b1").status == ATTACHMENT_BATCH_PENDING
    assert a.batch("b2").status == ATTACHMENT_BATCH_PENDING


def test_live_batch_for_other_conversation_is_fail_closed(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_B)  # route لمحادثة مختلفة عن دفعة النصّ
    a.mkbatch(cid=CID_A, t0=_live_t0(), batch_id="b1")

    a.process(U_A3 + 21, "نصّ")

    assert a.db.update_outcome(U_A3 + 21) == uo.REJECTED_INELIGIBLE
    assert a.batch("b1").status == ATTACHMENT_BATCH_PENDING


def test_live_batch_without_route_is_fail_closed(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.mkbatch(cid=CID_A, t0=_live_t0(), batch_id="b1")  # بلا set_awaiting

    a.process(U_A3 + 22, "نصّ")

    assert a.db.update_outcome(U_A3 + 22) == uo.REJECTED_INELIGIBLE
    assert a.batch("b1").status == ATTACHMENT_BATCH_PENDING


# ============================================================================
# 4) الدفعة المنتهية ⇒ لا إحياء/لا تحويل تلقائي لبرومت (D-29 بند 5)
# ============================================================================
def test_expired_batch_text_is_rejected_not_revived(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_expired_t0(), batch_id="b1")

    a.process(U_A3 + 30, "برومت متأخّر")

    assert a.db.update_outcome(U_A3 + 30) == uo.REJECTED_INELIGIBLE
    batch = a.batch("b1")
    assert batch.status == ATTACHMENT_BATCH_PENDING  # ما اتحوّلش لنيّة
    assert batch.intent_text is None
    # **لا** تحويل لبرومت عادي (مفيش صفّ outbox).
    assert a.db.count_outbox() == 0
    assert a.replies == [h_mod.ATTACHMENT_TEXT_EXPIRED_TEXT]


def test_expired_batch_does_not_block_live_batch(tmp_path, monkeypatch):
    # دفعة حيّة واحدة + دفعة منتهية ⇒ الدفعة الحيّة موجودة ⇒ نصّ يروح للحيّة (مفيش غموض
    # لأن `list_live` بترجّع واحدة). نتأكّد إن المنتهية **ما بتحجبش** الحيّة.
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(cid=CID_A, t0=_live_t0(), batch_id="live")
    a.mkbatch(cid=CID_B, t0=_expired_t0(), batch_id="dead")

    a.process(U_A3 + 31, "نصّ")

    assert a.db.update_outcome(U_A3 + 31) == uo.DURABLE_INTENT_RECORDED
    assert a.batch("live").status == ATTACHMENT_BATCH_INTENT_RECORDED
    assert a.batch("dead").status == ATTACHMENT_BATCH_PENDING


# ============================================================================
# 5) شاهد الحذف ⇒ فشل مغلق
# ============================================================================
def test_deleted_conversation_text_is_rejected(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1")
    a.tombstone(CID_A)

    a.process(U_A3 + 40, "نصّ")

    assert a.db.update_outcome(U_A3 + 40) == uo.REJECTED_INELIGIBLE
    assert a.batch("b1").intent_text is None
    assert a.db.count_outbox() == 0


# ============================================================================
# 6) لا دفعة معلّقة ⇒ مسار البرومت العادي كما هو (A0/A2 بلا تراجع)
# ============================================================================
def test_no_pending_batch_routes_to_normal_prompt(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)

    a.process(U_A3 + 50, "برومت عادي")
    a.h.deliver_pending()

    assert a.h.client.sends == [(CID_A, "برومت عادي")]
    assert a.db.count_outbox("pending") == 0  # اتسلّم وخرج من الـ pending
    # المسار العادي بيسجّل نيّة إرسال متينة (A2/B) — مش رفض A3 ولا نيّة مرفقات.
    assert a.db.update_outcome(U_A3 + 50) == uo.DURABLE_INTENT_RECORDED


def test_caption_without_text_is_not_accompanied_path(tmp_path, monkeypatch):
    # D-31: التعليقات خارج النطاق — رسالة بلا `text` ⇒ مش من مسار A3 (تتجاهلها المعالجات).
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1")

    chat = Chat(id=CHAT_ID, type="private")
    msg = Message(
        message_id=5, date=None, chat=chat,
        from_user=User(id=OWNER_ID, first_name="o", is_bot=False),
        text=None, caption="تعليق على صورة",
    )
    msg.set_bot(a.h.app.bot)
    up = Update(update_id=U_A3 + 51, message=msg)
    up.set_bot(a.h.app.bot)
    a.h.process(up)

    # الدفعة ما اتلمستش، ومفيش نتيجة نيّة A3 (رسالة بلا text مابتوصلش لمسار A3؛
    # لو وصلت لمعالج غير مطابق بتتسجّل `explicitly_ignored` — مش نيّة ولا رفض A3).
    assert a.batch("b1").status == ATTACHMENT_BATCH_PENDING
    assert a.batch("b1").intent_text is None
    assert a.db.update_outcome(U_A3 + 51) != uo.DURABLE_INTENT_RECORDED
    assert a.db.update_outcome(U_A3 + 51) != uo.REJECTED_INELIGIBLE


# ============================================================================
# 7) الفشل التقني fail-closed + سباق النيّة + التكرار
# ============================================================================
def test_db_failure_during_intent_is_not_ack_eligible(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1")

    def _boom(*_a, **_k):
        raise RuntimeError("simulated db failure")

    monkeypatch.setattr(a.db, "record_attachment_intent", _boom)

    a.process(U_A3 + 60, "نصّ")  # الاستثناء بيتبلع في PTB (بيسجّل فشل)

    outcome = a.db.update_outcome(U_A3 + 60)
    assert outcome is not None and not uo.is_ack_eligible(outcome)
    assert a.db.count_outbox() == 0


def test_intent_write_is_atomic_on_failure(tmp_path, monkeypatch):
    # F-3 (مراجعة عدائية مستقلة): إثبات **الذرّية** بحقن عطل بين كتابة النصّ/الحالة وكتابة
    # النتيجة. لو الاتنين مش في معاملة واحدة، الحالة هتفضل `intent_recorded` بعد العطل.
    # لازم **الكل يتراجع**: الدفعة تفضل `pending` بلا نصّ، ومفيش نتيجة.
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1")

    calls = {"n": 0}
    real = a.db._mark_processed_nocommit

    def _boom(*args, **kwargs):
        calls["n"] += 1
        raise RuntimeError("injected failure after batch UPDATE, before outcome")

    monkeypatch.setattr(a.db, "_mark_processed_nocommit", _boom)

    a.process(U_A3 + 90, "نصّ")  # الاستثناء بيتبلع في PTB (بيسجّل فشل)

    assert calls["n"] == 1  # العطل اتحقن فعلاً جوه المعاملة
    batch = a.batch("b1")
    assert batch.status == ATTACHMENT_BATCH_PENDING  # **اترجعت** (مفيش كتابة جزئية)
    assert batch.intent_text is None
    # العطل التقني اتسجّل `failed_*` (غير مؤهّل) — مفيش نيّة دائمة (`durable_intent_recorded`).
    outcome = a.db.update_outcome(U_A3 + 90)
    assert outcome != uo.DURABLE_INTENT_RECORDED
    assert not uo.is_ack_eligible(outcome)
    assert a.db.count_outbox() == 0
    monkeypatch.setattr(a.db, "_mark_processed_nocommit", real)


def test_intent_race_without_prior_outcome_is_fail_closed(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1")

    monkeypatch.setattr(a.db, "record_attachment_intent", lambda *a, **k: None)

    a.process(U_A3 + 61, "نصّ")

    assert a.db.update_outcome(U_A3 + 61) == uo.REJECTED_INELIGIBLE
    assert a.batch("b1").status == ATTACHMENT_BATCH_PENDING


def test_duplicate_update_does_not_double_record(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1")

    a.process(U_A3 + 70, "نصّ")
    a.process(U_A3 + 70, "نصّ")  # نفس update_id ⇒ حاجز الديدَب يوقفه

    assert a.db.update_outcome(U_A3 + 70) == uo.DURABLE_INTENT_RECORDED
    assert a.batch("b1").status == ATTACHMENT_BATCH_INTENT_RECORDED
    assert a.db.count_processed_updates() == 1
    assert len(a.replies) == 1  # ردّ واحد بس


def test_pending_batch_with_invalid_t0_does_not_fall_through_to_prompt(tmp_path, monkeypatch):
    # F-1 (مراجعة عدائية مستقلة): دفعة `pending` بـ`t0` غير صالح **مش حيّة** ⇒ لازم **تتعتبر
    # «مش حيّة»** كمان (fail-closed) عشان النصّ **مايتسرّبش** لمسار البرومت العادي/`outbox`.
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0="NOT-A-DATE", batch_id="b1")

    a.process(U_A3 + 91, "نصّ")

    assert a.db.update_outcome(U_A3 + 91) == uo.REJECTED_INELIGIBLE  # مش مسار برومت
    assert a.batch("b1").status == ATTACHMENT_BATCH_PENDING
    assert a.batch("b1").intent_text is None
    assert a.db.count_outbox() == 0  # مفيش صفّ outbox (مفيش إرسال بعيد)
    assert a.replies == [h_mod.ATTACHMENT_TEXT_EXPIRED_TEXT]


def test_text_after_intent_recorded_is_blocked(tmp_path, monkeypatch):
    # D-32/F1-1a: دفعة `intent_recorded` (غير محسومة) ⇒ **تحجب** البرومت العادي (fail-closed).
    # (كان الاختبار القديم يتوقّع المرور للمسار العادي — وده بالظبط عيب F1-1a.)
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1", status=ATTACHMENT_BATCH_INTENT_RECORDED)

    a.process(U_A3 + 71, "برومت بعد النيّة")
    a.h.deliver_pending()

    assert a.db.update_outcome(U_A3 + 71) == uo.REJECTED_INELIGIBLE
    assert a.h.client.sends == []                 # مفيش إرسال بعيد
    assert a.db.count_outbox() == 0               # مفيش صفّ outbox
    assert a.batch("b1").status == ATTACHMENT_BATCH_INTENT_RECORDED  # ما اتلمستش
    assert a.replies == [h_mod.ATTACHMENT_TEXT_UNRESOLVED_TEXT]


# ============================================================================
# 8) وحدة القاعدة: record_attachment_intent ذرّي ويفرض الملكية/المهلة
# ============================================================================
def test_record_attachment_intent_rejects_wrong_owner(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    t0 = _live_t0()
    db.create_attachment_batch("b1", 999, CID_A, t0)
    res = db.record_attachment_intent(
        "b1", telegram_id=OWNER_ID, conversation_id=CID_A,
        intent_text="نصّ", now=_iso(_now()), update_id=None,
    )
    assert res is None
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_PENDING


def test_record_attachment_intent_rejects_expired(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.create_attachment_batch("b1", OWNER_ID, CID_A, _expired_t0())
    res = db.record_attachment_intent(
        "b1", telegram_id=OWNER_ID, conversation_id=CID_A,
        intent_text="نصّ", now=_iso(_now()), update_id=None,
    )
    assert res is None
    assert db.get_attachment_batch("b1").intent_text is None


def test_record_attachment_intent_is_idempotent_per_batch(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.create_attachment_batch("b1", OWNER_ID, CID_A, _live_t0())
    now = _iso(_now())
    assert db.record_attachment_intent(
        "b1", telegram_id=OWNER_ID, conversation_id=CID_A,
        intent_text="نصّ أول", now=now, update_id=None,
        chat_id=CHAT_ID, message_id=5,
    ) == "b1"
    # محاولة تانية على نفس الدفعة ⇒ مش `pending` ⇒ None (بلا كتابة).
    assert db.record_attachment_intent(
        "b1", telegram_id=OWNER_ID, conversation_id=CID_A,
        intent_text="نصّ تانٍ", now=now, update_id=None,
        chat_id=CHAT_ID, message_id=6,
    ) is None
    assert db.get_attachment_batch("b1").intent_text == "نصّ أول"


def test_record_rejected_ineligible_without_update_id_is_false(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    assert db.record_rejected_ineligible(now=_iso(_now()), update_id=None) is False


# ============================================================================
# 9) فصل المهلة 10/15 دقيقة (I4/I6) — الدفعة لا تلمس AWAITING_TTL
# ============================================================================
def test_attachment_window_is_independent_from_routing_ttl(tmp_path, monkeypatch):
    from bot.db import ATTACHMENT_BATCH_TTL, AWAITING_TTL

    assert ATTACHMENT_BATCH_TTL == timedelta(minutes=15)
    assert AWAITING_TTL == timedelta(minutes=10)
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1")
    a.process(U_A3 + 80, "نصّ")
    # حالة route (10د) ما اتغيّرتش بواسطة A3 (مفيش استهلاك/مسح).
    assert a.db.get_awaiting(OWNER_ID) == (CID_A, "route")
