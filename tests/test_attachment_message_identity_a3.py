"""OHB2-P0-A3/D-33/D-34/D-35 — هوية رسالة↔دفعة متينة + فرض المفاتيح الأجنبية.

يغطّي مصفوفة السيناريوهات المطلوبة في تصميم R2 (قسم 9):
- فرض `PRAGMA foreign_keys=ON` على **اتصال الإنتاج الحقيقي** (سلوك SQLite فعلي، لا فحص نصّ SQL).
- دليل الهوية `(telegram_id, chat_id, message_id)` المتين والمستقلّ عن تقليم `processed_updates`.
- الفشل المغلق للنصّ المرتبط بدفعة نهائية/غير مُثبَت (`TERMINAL_ASSOCIATED`/`TERMINAL_UNPROVEN`).
- حماية N-2 (حجب عبر المحادثات) وسلامة الإقرار (لا تقدّم للحدّ عند فشل غير محسوم).

مهم: الاختبارات بتفتح الاتصال عبر **نفس مسار الإنتاج** (`bot.db.Database`)، مش اتصال يدوي.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest
import bot.db as db_mod
from bot import update_outcomes as uo
from bot.db import (
    ATTACHMENT_BATCH_DELIVERED,
    ATTACHMENT_BATCH_EXPIRED,
    ATTACHMENT_BATCH_INTENT_RECORDED,
    ATTACHMENT_BATCH_PENDING,
    AttachmentRoutingState,
    Database,
    normalize_message_identity,
)

from tests.test_attachment_terminal_routing_remediation import (
    CID_B,
    _client,
    _expired_t0,
    _harness,
    _iso,
    _live_t0,
    _no_remote,
    _raw_status,
)
from tests.test_duplicate_update_dispatch import CHAT_ID, CID_A, OWNER_ID

# نطاق معرّفات تحديث فريد (لا يتقاطع مع الملفات الأخرى).
U_ID = 2_950_000
MSG_ID = 5  # نفس `message_id` اللي بيبنيه Harness.text_update


def _identity_row(db: Database, *, telegram_id=OWNER_ID, chat_id=CHAT_ID, message_id=MSG_ID):
    return db.message_identity_batch_id(telegram_id, chat_id, message_id)


def _bind(db: Database, batch_id: str, *, chat_id: int = CHAT_ID, message_id: int = MSG_ID,
          conversation_id: str = CID_A, created_at: str | None = None) -> None:
    """يربط هوية رسالة بدفعة عبر **نفس مسار الكتابة الإنتاجي** (`record_attachment_intent`)."""
    res = db.record_attachment_intent(
        batch_id, telegram_id=OWNER_ID, conversation_id=conversation_id,
        intent_text="نصّ", now=created_at or _iso(datetime.now(timezone.utc)),
        update_id=None, chat_id=chat_id, message_id=message_id,
    )
    assert res == batch_id


# ============================================================================
# 1) فرض المفاتيح الأجنبية على اتصال الإنتاج الحقيقي (سلوك SQLite فعلي)
# ============================================================================
def test_production_connection_enables_foreign_keys(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    assert db._conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_fk_rejects_deleting_referenced_batch(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.create_attachment_batch("b1", OWNER_ID, CID_A, _live_t0())
    _bind(db, "b1")

    with pytest.raises(sqlite3.IntegrityError):
        db._conn.execute("DELETE FROM attachment_batches WHERE batch_id='b1'")
    db._conn.rollback()

    # بعد التراجع: الدفعة ودليل الهوية سليمان (لا حذف، لا cascade).
    assert db.get_attachment_batch("b1") is not None
    assert _identity_row(db) == "b1"


def test_fk_rejects_nonexistent_referenced_batch(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    with pytest.raises(sqlite3.IntegrityError):
        db._conn.execute(
            "INSERT INTO attachment_message_identity "
            "(telegram_id, chat_id, message_id, batch_id, conversation_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (OWNER_ID, CHAT_ID, MSG_ID, "does-not-exist", CID_A, _iso(datetime.now(timezone.utc))),
        )
    db._conn.rollback()
    assert db.count_message_identities() == 0


def test_fk_pragma_set_before_transactions_on_all_paths(tmp_path):
    # مسار التهيئة الوحيد في المشروع هو `Database.__init__`؛ نتحقّق أنه لا يوجد
    # `sqlite3.connect` آخر (اتصال ثانٍ بلا فرض FK) في كود الإنتاج.
    import pathlib

    root = pathlib.Path(db_mod.__file__).resolve().parent
    hits = []
    for py in root.rglob("*.py"):
        for line in py.read_text(encoding="utf-8").splitlines():
            if "sqlite3.connect" in line:
                hits.append((py.name, line.strip()))
    assert hits == [(pathlib.Path(db_mod.__file__).name, "self._conn = sqlite3.connect(path, check_same_thread=False)")]


def test_connection_init_failure_propagates(tmp_path, monkeypatch):
    # فشل تفعيل FK ⇒ استثناء (fail-closed)، لا متابعة بلا حماية.
    real_connect = sqlite3.connect

    class _Proxy:
        """وكيل شفّاف حول اتصال حقيقي يرفض تفعيل FK (محاكاة فشل التفعيل)."""

        def __init__(self, conn):
            object.__setattr__(self, "_c", conn)

        def execute(self, sql, *a, **k):
            if sql.strip().upper().startswith("PRAGMA FOREIGN_KEYS"):
                raise sqlite3.OperationalError("cannot change foreign_keys")
            return self._c.execute(sql, *a, **k)

        def __getattr__(self, name):
            return getattr(self._c, name)

        def __setattr__(self, name, value):
            setattr(self._c, name, value)

    monkeypatch.setattr(
        db_mod.sqlite3, "connect",
        lambda path, **kw: _Proxy(real_connect(path, **kw)),
    )
    with pytest.raises(sqlite3.OperationalError):
        Database(str(tmp_path / "t.sqlite3"))


# ============================================================================
# 2) تحقّق الهوية التطبيقي (SQLite ديناميكي ⇒ التحقّق إلزامي في بايثون)
# ============================================================================
@pytest.mark.parametrize("bad", [
    (None, CHAT_ID, MSG_ID),
    (OWNER_ID, None, MSG_ID),
    (OWNER_ID, CHAT_ID, None),
    (0, CHAT_ID, MSG_ID),
    (OWNER_ID, 0, MSG_ID),
    (OWNER_ID, CHAT_ID, 0),
    (-1, CHAT_ID, MSG_ID),
    (OWNER_ID, -5, MSG_ID),
    (True, CHAT_ID, MSG_ID),
    ("1", CHAT_ID, MSG_ID),
    (1.0, CHAT_ID, MSG_ID),
])
def test_normalize_message_identity_rejects_bad(bad):
    assert normalize_message_identity(*bad) is None


def test_normalize_message_identity_accepts_positive_ints():
    assert normalize_message_identity(1, 2, 3) == (1, 2, 3)


def test_missing_identity_blocks_intent_persistence(tmp_path):
    # هوية ناقصة (بلا chat_id/message_id) ⇒ لا نيّة متينة (فشل مغلق، لا كتابة بلا دليل هوية).
    db = Database(str(tmp_path / "t.sqlite3"))
    db.create_attachment_batch("b1", OWNER_ID, CID_A, _live_t0())
    res = db.record_attachment_intent(
        "b1", telegram_id=OWNER_ID, conversation_id=CID_A, intent_text="نصّ",
        now=_iso(datetime.now(timezone.utc)), update_id=None,
    )
    assert res is None
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_PENDING
    assert db.count_message_identities() == 0


# ============================================================================
# 3) الربط القانوني + المثابرة المستقلة عن تقليم processed_updates
# ============================================================================
def test_identity_binding_is_durable_and_persisted(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.create_attachment_batch("b1", OWNER_ID, CID_A, _live_t0())
    _bind(db, "b1")
    assert _identity_row(db) == "b1"
    assert db.count_message_identities() == 1


def test_identity_survives_processed_updates_pruning(tmp_path):
    # D-35: التقليم مايلمسش دليل الهوية (مستقلّ تمامًا).
    db = Database(str(tmp_path / "t.sqlite3"))
    db.create_attachment_batch("b1", OWNER_ID, CID_A, _live_t0())
    now = _iso(datetime.now(timezone.utc))
    assert db.record_attachment_intent(
        "b1", telegram_id=OWNER_ID, conversation_id=CID_A, intent_text="نصّ",
        now=now, update_id=U_ID, chat_id=CHAT_ID, message_id=MSG_ID,
    ) == "b1"
    assert db.count_processed_updates() >= 1
    db.prune_processed_updates(keep=0, boundary=U_ID)
    assert db.count_processed_updates() == 0  # سجل التحديثات اتقلّم
    assert _identity_row(db) == "b1"          # دليل الهوية لسه موجود


def test_identity_is_owner_scoped(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.create_attachment_batch("b1", OWNER_ID, CID_A, _live_t0())
    _bind(db, "b1")
    # نفس (chat_id, message_id) لكن مالك آخر ⇒ مفيش دليل (عزل).
    assert db.message_identity_batch_id(999, CHAT_ID, MSG_ID) is None


def test_same_message_id_different_chat_is_distinct(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.create_attachment_batch("b1", OWNER_ID, CID_A, _live_t0())
    _bind(db, "b1", chat_id=CHAT_ID, message_id=MSG_ID)
    assert db.message_identity_batch_id(OWNER_ID, CHAT_ID + 1, MSG_ID) is None


def test_rebinding_same_message_to_different_batch_fails_closed(tmp_path):
    # نفس الرسالة مستحيل تتربط بدفعة تانية صامتًا ⇒ IntegrityError (تعارض) + rollback.
    db = Database(str(tmp_path / "t.sqlite3"))
    db.create_attachment_batch("b1", OWNER_ID, CID_A, _live_t0())
    db.create_attachment_batch("b2", OWNER_ID, CID_A, _live_t0())
    _bind(db, "b1")
    with pytest.raises(sqlite3.IntegrityError):
        db.record_attachment_intent(
            "b2", telegram_id=OWNER_ID, conversation_id=CID_A, intent_text="تانٍ",
            now=_iso(datetime.now(timezone.utc)), update_id=None,
            chat_id=CHAT_ID, message_id=MSG_ID,
        )
    assert _identity_row(db) == "b1"  # الربط الأصلي ما اتغيّرش
    assert db.get_attachment_batch("b2").status == ATTACHMENT_BATCH_PENDING


# ============================================================================
# 4) الحالة النهائية المرتبطة مقابل غير المُثبَتة (D-34)
# ============================================================================
def test_terminal_with_identity_is_associated(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.create_attachment_batch("b1", OWNER_ID, CID_A, _live_t0())
    _bind(db, "b1")
    _raw_status(db, "b1", ATTACHMENT_BATCH_DELIVERED)
    r = db.classify_attachment_routing(
        OWNER_ID, now_iso=_iso(datetime.now(timezone.utc)), chat_id=CHAT_ID, message_id=MSG_ID
    )
    assert r.state is AttachmentRoutingState.TERMINAL_ASSOCIATED


def test_terminal_without_identity_is_unproven(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.create_attachment_batch("b1", OWNER_ID, CID_A, _live_t0(), status=ATTACHMENT_BATCH_EXPIRED)
    r = db.classify_attachment_routing(
        OWNER_ID, now_iso=_iso(datetime.now(timezone.utc)), chat_id=CHAT_ID, message_id=MSG_ID
    )
    assert r.state is AttachmentRoutingState.TERMINAL_UNPROVEN


# ============================================================================
# 5) سلوك الحدّ الحقيقي: نصّ مرتبط بدفعة نهائية ⇒ لا سقوط (end-to-end)
# ============================================================================
def test_terminal_associated_text_fails_closed_end_to_end(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1")
    # نربط هوية الرسالة بالدفعة عبر مسار الإنتاج، ثم نحوّل الدفعة نهائية.
    _bind(a.db, "b1")
    _raw_status(a.db, "b1", ATTACHMENT_BATCH_DELIVERED)

    a.process(U_ID + 1, "نصّ مرتبط")
    a.h.deliver_pending()

    assert a.db.update_outcome(U_ID + 1) == uo.REJECTED_INELIGIBLE
    _no_remote(a)


def test_terminal_other_conversation_still_blocks_n2(tmp_path, monkeypatch):
    # N-2: دفعة نهائية لمحادثة أخرى ⇒ النصّ غير المُثبَت يُرفض (لا استبدال محادثة).
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(cid=CID_B, t0=_live_t0(), batch_id="old", status=ATTACHMENT_BATCH_EXPIRED)

    a.process(U_ID + 2, "برومت")
    a.h.deliver_pending()

    assert a.db.update_outcome(U_ID + 2) == uo.REJECTED_INELIGIBLE
    _no_remote(a)


# ============================================================================
# 6) لا سقوط صامت لنصّ محادثة أخرى بينما دفعة نهائية قائمة
# ============================================================================
def test_new_message_other_conversation_while_terminal_exists(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(cid=CID_B, t0=_live_t0(), batch_id="t", status=ATTACHMENT_BATCH_DELIVERED)

    # نصّ في المحادثة A مع route إلى A، لكن دفعة نهائية (B) قائمة ⇒ فشل مغلق (D-34).
    a.process(U_ID + 3, "برومت في A")
    a.h.deliver_pending()

    assert a.db.update_outcome(U_ID + 3) == uo.REJECTED_INELIGIBLE
    _no_remote(a)


# ============================================================================
# 7) سلامة الإقرار: رفض نهائي ⇒ الحدّ يتقدّم؛ فشل تقني ⇒ لا يتقدّم
# ============================================================================
def test_ack_advances_on_terminal_rejection(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1", status=ATTACHMENT_BATCH_EXPIRED)
    a.process(U_ID + 4, "نصّ")
    assert a.db.acknowledgment_boundary([U_ID + 4]) == U_ID + 4


def test_ack_does_not_advance_on_db_failure(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1")

    def _boom(*_a, **_k):
        raise RuntimeError("simulated db failure")

    monkeypatch.setattr(a.db, "record_attachment_intent", _boom)
    a.process(U_ID + 5, "نصّ مصاحب")
    assert a.db.acknowledgment_boundary([U_ID + 5]) is None
    _no_remote(a)


# ============================================================================
# 8) تكرار التسليم: لا ازدواج دليل هوية ولا إعادة نيّة
# ============================================================================
def test_duplicate_delivery_does_not_duplicate_identity(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1")

    a.process(U_ID + 6, "نصّ مصاحب")
    assert a.db.count_message_identities() == 1
    # إعادة تسليم نفس الـupdate_id ⇒ `duplicate_completed`، بلا كتابة إضافية.
    a.process(U_ID + 6, "نصّ مصاحب")
    assert a.db.count_message_identities() == 1
    assert a.db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_INTENT_RECORDED


# ============================================================================
# 9) دفعة `pending` منتهية ⇒ لا سقوط (انحدار A3 محفوظ)
# ============================================================================
def test_expired_pending_still_rejected(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_expired_t0(), batch_id="b1")
    a.process(U_ID + 7, "نصّ")
    assert a.db.update_outcome(U_ID + 7) == uo.REJECTED_INELIGIBLE
    _no_remote(a)


# ============================================================================
# 10) `NONE` مُتحقَّق ⇒ مسار البرومت العادي محفوظ (A0/A2)
# ============================================================================
def test_verified_none_preserves_ordinary_prompt(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.process(U_ID + 8, "برومت عادي")
    a.h.deliver_pending()
    assert a.h.client.sends == [(CID_A, "برومت عادي")]
    assert a.db.count_message_identities() == 0


# ============================================================================
# 11) معرّفات غير صالحة على الحدّ الحقيقي (chat/message غائب) ⇒ لا سقوط صامت
# ============================================================================
def test_handler_missing_message_id_does_not_crash_terminal(tmp_path, monkeypatch):
    a = _harness(tmp_path, monkeypatch, _client())
    a.route(CID_A)
    a.mkbatch(t0=_live_t0(), batch_id="b1", status=ATTACHMENT_BATCH_EXPIRED)
    up = a.h.text_update(U_ID + 9, "نصّ")
    # نحذف message_id لمحاكاة رسالة بلا هوية (نادر) ⇒ التصنيف يفشل مغلقًا لا ينهار.
    object.__setattr__(up.message, "message_id", None)
    a.h.process(up)
    assert a.db.update_outcome(U_ID + 9) == uo.REJECTED_INELIGIBLE
    _no_remote(a)
