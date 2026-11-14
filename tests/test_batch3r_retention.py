"""OHB2-08-05 Batch 3R-FIX: اختبارات سياسة الاحتفاظ (M-1).

السياسة الجديدة: الصفوف **المعلّقة** (`pending`) و**غير المقروءة** (`read_at IS NULL`)
**مايتقلّمش أبدًا**؛ المقروءة بس مؤهّلة للتقليم (الأقدم أولًا) لحد السقف لكل محادثة
(`INBOX_MAX_PER_CONVERSATION`) والسقف العام (`INBOX_MAX_TOTAL`) — والسقفين **سقفان ناعمان**
لو الصفوف المحمية لوحدها تعدّيهم.

بيختبر الاختبارات **صفوف فعلية بالمعرّفات** مش إجماليات بس.
"""
from __future__ import annotations

from bot.db import (
    Database,
    INBOX_MAX_PER_CONVERSATION,
    INBOX_MAX_TOTAL,
)


def make_db(tmp_path) -> Database:
    return Database(str(tmp_path / "t.sqlite3"))


def present_ids(db) -> set[int]:
    return {it.id for it in db.list_inbox(limit=10_000)}


def rows_of(db, cid) -> list:
    return [it for it in db.list_inbox(limit=10_000) if it.conversation_id == cid]


# =================================================== H: السقف لكل محادثة
def test_h_per_conversation_unread_survive_read_pruned_first(tmp_path):
    db = make_db(tmp_path)
    # cap+10 صف مُسلّم (مقروء بعد ما نعلّمهم)، ثم 5 صفوف غير مقروءة (محمية).
    read_ids = [
        db.add_inbox_item("c1", "t", "terminal", f"r{i}", "t0")
        for i in range(INBOX_MAX_PER_CONVERSATION + 10)
    ]
    db.mark_all_inbox_read("tr")
    unread_ids = [
        db.add_inbox_item("c1", "t", "terminal", f"u{i}", "t1") for i in range(5)
    ]
    ids = present_ids(db)
    # كل غير المقروء محفوظ (فوق السقف — سقف ناعم).
    assert set(unread_ids) <= ids
    # المقروءة اتقلّمت للسقف، الأقدم أولًا.
    read_kept = [i for i in read_ids if i in ids]
    assert len(read_kept) == INBOX_MAX_PER_CONVERSATION
    assert read_ids[0] not in ids               # أقدم مقروء اتشال
    assert read_ids[-1] in ids                  # أحدث مقروء محفوظ
    db.close()


# =================================================== I: السقف العام
def test_i_global_cap_pending_and_unread_survive_read_pruned(tmp_path):
    db = make_db(tmp_path)
    read_ids = [
        db.add_inbox_item(f"c{i % 60}", "t", "terminal", f"m{i}", f"t{i}")
        for i in range(INBOX_MAX_TOTAL + 20)
    ]
    db.mark_all_inbox_read("tr")
    unread_ids = [
        db.add_inbox_item(f"u{i}", "t", "terminal", f"un{i}", "t") for i in range(10)
    ]
    pending_ids = [
        db.add_inbox_event(f"p{i}", "t", "proactive", f"pn{i}", "t", event_key=f"pk{i}")
        for i in range(5)
    ]
    ids = present_ids(db)
    # المحمي (غير المقروء + المعلّق) كله عايش (سقف عام ناعم).
    assert set(unread_ids) <= ids
    assert set(pending_ids) <= ids
    # المقروءة اتقلّمت للسقف العام، الأقدم أولًا.
    read_kept = [i for i in read_ids if i in ids]
    assert len(read_kept) == INBOX_MAX_TOTAL
    assert read_ids[0] not in ids
    assert read_ids[-1] in ids
    db.close()


# =================================================== J: حماية المعلّق
def test_j_pending_never_pruned_even_with_old_ids(tmp_path):
    db = make_db(tmp_path)
    # معلّقة بمعرّفات قديمة (اتسجّلت الأول).
    pending_ids = [
        db.add_inbox_event("cold", "t", "proactive", f"p{i}", "t", event_key=f"pk{i}")
        for i in range(10)
    ]
    # مقروءة أحدث بكتير (عشان التقليم يشتغل).
    for i in range(INBOX_MAX_TOTAL + 20):
        db.add_inbox_item(f"c{i % 60}", "t", "terminal", f"m{i}", f"t{i}")
    db.mark_all_inbox_read("tr")
    db.add_inbox_item("cz", "t", "terminal", "trigger", "t")  # يستدعي التقليم
    ids = present_ids(db)
    assert set(pending_ids) <= ids               # كل المعلّق عايش رغم قِدَم معرّفاته
    assert len([it for it in db.list_inbox(limit=10_000) if it.delivery_pending]) == 10
    db.close()


# =================================================== K: تغيّر حالة القراءة
def test_k_marking_read_makes_rows_eligible(tmp_path):
    db = make_db(tmp_path)
    ids = [
        db.add_inbox_item("c1", "t", "terminal", f"u{i}", "t0")
        for i in range(INBOX_MAX_PER_CONVERSATION + 10)
    ]
    # غير مقروءة ⇒ محمية (كله عايش).
    assert len(rows_of(db, "c1")) == INBOX_MAX_PER_CONVERSATION + 10
    # بعد ما تتعلّم مقروءة ⇒ مؤهّلة للتقليم العادي.
    db.mark_all_inbox_read("tr")
    db.add_inbox_item("c1", "t", "terminal", "trigger", "t1")  # يستدعي التقليم
    read_kept = [i for i in ids if i in present_ids(db)]
    assert len(read_kept) == INBOX_MAX_PER_CONVERSATION
    assert ids[0] not in present_ids(db)
    db.close()


# =================================================== L: توزيع مختلط بين المحادثات
def test_l_mixed_distribution_isolated_pruning(tmp_path):
    db = make_db(tmp_path)
    # محادثة A: غير مقروءة (محمية). محادثة B: مقروءة (قابلة للتقليم).
    a_ids = [
        db.add_inbox_item("A", "t", "terminal", f"a{i}", "t0")
        for i in range(INBOX_MAX_PER_CONVERSATION + 10)
    ]
    b_ids = [
        db.add_inbox_item("B", "t", "terminal", f"b{i}", "t0")
        for i in range(INBOX_MAX_PER_CONVERSATION + 10)
    ]
    # نعلّم B بس مقروءة (A تفضل محمية).
    for i in b_ids:
        db.mark_inbox_read(i, "tr")
    db.add_inbox_item("B", "t", "terminal", "triggerB", "t1")  # يستدعي تقليم B (والعام)
    ids = present_ids(db)
    # A: كل غير المقروء محفوظ.
    assert set(a_ids) <= ids
    # B: اتقلّمت للسقف، الأقدم اتشال.
    b_kept = [i for i in b_ids if i in ids]
    assert len(b_kept) == INBOX_MAX_PER_CONVERSATION
    assert b_ids[0] not in ids
    db.close()


def test_l2_pruning_one_conversation_does_not_touch_protected_in_another(tmp_path):
    db = make_db(tmp_path)
    protected = [
        db.add_inbox_event("P", "t", "proactive", f"p{i}", "t", event_key=f"pk{i}")
        for i in range(20)
    ]
    # محادثة تانية: مقروءة كتير ⇒ تتقلّم من غير ما تلمس P.
    for i in range(INBOX_MAX_TOTAL + 30):
        db.add_inbox_item(f"c{i % 40}", "t", "terminal", f"m{i}", f"t{i}")
    db.mark_all_inbox_read("tr")
    db.add_inbox_item("cz", "t", "terminal", "trigger", "t")
    assert set(protected) <= present_ids(db)
    db.close()
