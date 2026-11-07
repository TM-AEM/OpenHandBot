"""OHB2-PHASE1C: اختبارات إدارة الصندوق (فلتر غير المقروء + أرشفة + حذف نهائي آمن).

بتستخدم قاعدة البيانات الحقيقية وتطبيق الـ API الحقيقي (نفس نمط `test_miniapp_inbox.py`).
بتغطّي: صحة الفلترة، عزل الأرشفة، أهلية الحذف النهائي المفروضة على السيرفر، حفظ دليل
العمليات المعلّقة/الغامضة، منع الوصول عبر مستخدم تاني، ورفض النجاح الكاذب عند فشل القاعدة.
"""
from __future__ import annotations

import sqlite3

from starlette.testclient import TestClient

from bot.config import Config
from bot.db import (
    Database,
    INBOX_DELIVERY_PENDING,
)
from bot.web import build_web_app
from tests._miniapp_helpers import BOT_TOKEN, make_init_data

OWNER = 555
OTHER = 999
ORIGIN = "https://app.test"


def make_config(tmp_path, **over) -> Config:
    base = dict(
        telegram_bot_token=BOT_TOKEN,
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({OWNER}),
        owner_id=OWNER,
        db_path=str(tmp_path / "t.sqlite3"),
        mini_app_cookie_secure=False,
        mini_app_allowed_origins=frozenset({ORIGIN}),
    )
    base.update(over)
    return Config(**base)


def build(tmp_path, db=None, **over):
    cfg = make_config(tmp_path, **over)
    app = build_web_app(cfg, db)
    return TestClient(app, raise_server_exceptions=False), db


def authed(tmp_path, db=None, **over):
    c, db = build(tmp_path, db, **over)
    r = c.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    assert r.status_code == 200
    return c, db


def seed(db, cid="c1", kind="terminal", message="m", *, read=False, event=False):
    """يضيف إشعارًا (delivered افتراضيًا) ويرجّع معرّفه، مع تعليمه مقروءًا عند الطلب."""
    if event:
        ident = db.add_inbox_event(cid, "t", kind, message, "t0", chat_id=1)
    else:
        ident = db.add_inbox_item(cid, "t", kind, message, "t0")
    if read:
        db.mark_inbox_read(ident, "t1")
    return ident


# =========================================================== 1. فلتر غير المقروء
def test_unread_filter_returns_only_unread(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    seed(db, message="read-1", read=True)
    seed(db, message="unread-1")
    seed(db, message="read-2", read=True)
    seed(db, message="unread-2")
    c, db = authed(tmp_path, db)

    body = c.get("/api/v1/notifications?unread=1").json()
    assert [it["message"] for it in body["items"]] == ["unread-2", "unread-1"]
    assert all(it["read"] is False for it in body["items"])
    assert body["unread_count"] == 2


def test_all_filter_returns_everything_newest_first(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    seed(db, message="a", read=True)
    seed(db, message="b")
    seed(db, message="c", read=True)
    c, db = authed(tmp_path, db)

    body = c.get("/api/v1/notifications").json()
    assert [it["message"] for it in body["items"]] == ["c", "b", "a"]


def test_read_items_never_leak_into_unread(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    for i in range(6):
        seed(db, message=f"r{i}", read=True)
    seed(db, message="only-unread")
    c, db = authed(tmp_path, db)

    body = c.get("/api/v1/notifications?unread=1").json()
    assert [it["message"] for it in body["items"]] == ["only-unread"]


def test_unread_filter_pagination_and_ordering(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    # 12 غير مقروء + 5 مقروء (مايظهروش في الفلتر).
    for i in range(12):
        seed(db, message=f"u{i}")
    for i in range(5):
        seed(db, message=f"r{i}", read=True)
    c, db = authed(tmp_path, db)

    p0 = c.get("/api/v1/notifications?unread=1&page=0").json()
    assert p0["page"] == 0 and p0["has_more"] is True
    assert len(p0["items"]) == 10
    assert p0["items"][0]["message"] == "u11"  # الأحدث أولًا
    p1 = c.get("/api/v1/notifications?unread=1&page=1").json()
    assert p1["page"] == 1 and p1["has_more"] is False
    assert len(p1["items"]) == 2
    # مفيش تكرار بين الصفحتين، وكلهم غير مقروءين.
    ids = [it["id"] for it in p0["items"]] + [it["id"] for it in p1["items"]]
    assert len(ids) == len(set(ids)) == 12
    assert all(it["read"] is False for it in p0["items"] + p1["items"])


def test_filter_does_not_mark_items_read(tmp_path):
    """تفعيل فلتر غير المقروء / عرضه مايغيّرش حالة القراءة على السيرفر."""
    db = Database(str(tmp_path / "t.sqlite3"))
    ident = seed(db, message="x")
    c, db = authed(tmp_path, db)

    c.get("/api/v1/notifications?unread=1")
    c.get("/api/v1/notifications")
    assert db.get_inbox_item(ident).read_at is None
    assert db.count_inbox(unread_only=True) == 1


def test_unread_filter_requires_auth(tmp_path):
    c, _ = build(tmp_path, Database(str(tmp_path / "t.sqlite3")))
    assert c.get("/api/v1/notifications?unread=1").status_code == 401


def test_other_user_cannot_read_inbox(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    seed(db, message="secret")
    c, db = build(tmp_path, db)
    r = c.post("/api/v1/auth", json={"initData": make_init_data(OTHER)})
    assert r.status_code == 403
    assert c.get("/api/v1/notifications").status_code == 401
    assert c.get("/api/v1/notifications?unread=1").status_code == 401


# ================================================================== 2. الأرشفة
def test_archive_hides_from_active_and_shows_in_archived_view(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    ident = seed(db, message="keep")
    other = seed(db, message="archive-me", read=True)
    c, db = authed(tmp_path, db)

    r = c.post(f"/api/v1/notifications/{other}/archive", json={}, headers={"origin": ORIGIN})
    assert r.status_code == 200 and r.json()["archived"] is True

    active = c.get("/api/v1/notifications").json()
    assert [it["id"] for it in active["items"]] == [ident]
    arch = c.get("/api/v1/notifications?archived=1").json()
    assert [it["id"] for it in arch["items"]] == [other]
    assert arch["items"][0]["archived"] is True


def test_archive_is_idempotent(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    ident = seed(db, message="x", read=True)
    c, db = authed(tmp_path, db)

    first = c.post(f"/api/v1/notifications/{ident}/archive", json={}, headers={"origin": ORIGIN})
    assert first.status_code == 200
    stamp = db.get_inbox_item(ident).archived_at
    second = c.post(f"/api/v1/notifications/{ident}/archive", json={}, headers={"origin": ORIGIN})
    assert second.status_code == 200 and second.json()["archived"] is True
    # وقت الأرشفة الأصلي ما اتغيّرش (idempotent).
    assert db.get_inbox_item(ident).archived_at == stamp


def test_archive_does_not_change_delivery_or_operation_state(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    # حدث معلّق (delivery_status='pending') مربوط بعلامة تسوية دائمة + صف outbox.
    ident = db.add_inbox_event("c1", "t", "terminal", "m", "t0", chat_id=42)
    db.set_notifier_pending("c1", "finished", "t0", event_id=ident, transition_seq=1)
    outbox_id = db.add_or_group_outbox("c1", 42, "hello", "t0", client_ref="ref-1")

    c, db = authed(tmp_path, db)
    r = c.post(f"/api/v1/notifications/{ident}/archive", json={}, headers={"origin": ORIGIN})
    assert r.status_code == 200

    item = db.get_inbox_item(ident)
    assert item.archived is True
    assert item.delivery_status == INBOX_DELIVERY_PENDING  # التسليم ما اتغيّرش
    assert item.read_at is None  # القراءة ما اتغيّرتش
    # دليل التسوية الدائم لسه موجود، وصف العملية لسه موجود.
    assert db.get_notifier_pending("c1") == "finished"
    assert db.get_notifier_pending_row("c1")[0] == ident
    assert db.get_outbox(outbox_id) is not None


def test_unarchive_restores_to_active_inbox(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    ident = seed(db, message="x", read=True)
    c, db = authed(tmp_path, db)

    c.post(f"/api/v1/notifications/{ident}/archive", json={}, headers={"origin": ORIGIN})
    r = c.post(f"/api/v1/notifications/{ident}/unarchive", json={}, headers={"origin": ORIGIN})
    assert r.status_code == 200 and r.json()["archived"] is False
    assert [it["id"] for it in c.get("/api/v1/notifications").json()["items"]] == [ident]
    assert c.get("/api/v1/notifications?archived=1").json()["items"] == []


def test_archive_missing_item_404(tmp_path):
    c, db = authed(tmp_path, Database(str(tmp_path / "t.sqlite3")))
    r = c.post("/api/v1/notifications/999/archive", json={}, headers={"origin": ORIGIN})
    assert r.status_code == 404


def test_archive_invalid_id_400(tmp_path):
    c, db = authed(tmp_path, Database(str(tmp_path / "t.sqlite3")))
    r = c.post("/api/v1/notifications/abc/archive", json={}, headers={"origin": ORIGIN})
    assert r.status_code == 400


def test_archive_requires_origin(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    ident = seed(db, message="x")
    c, db = authed(tmp_path, db)
    r = c.post(f"/api/v1/notifications/{ident}/archive", json={}, headers={"origin": "https://evil.test"})
    assert r.status_code == 403
    assert db.get_inbox_item(ident).archived is False  # ما اتغيّرش


def test_archive_db_failure_is_not_false_success(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    ident = seed(db, message="x")
    c, db = authed(tmp_path, db)

    def boom(*_a, **_k):
        raise sqlite3.OperationalError("database is locked")

    db.archive_inbox_item = boom  # type: ignore[assignment]
    r = c.post(f"/api/v1/notifications/{ident}/archive", json={}, headers={"origin": ORIGIN})
    assert r.status_code >= 400  # مفيش 200 كاذب
    assert db.get_inbox_item(ident).archived is False


def test_archived_items_excluded_from_unread_badge_count(tmp_path):
    """الأرشيف مايزوّدش شارة غير المقروء (الشارة على الصندوق النشط بس)."""
    db = Database(str(tmp_path / "t.sqlite3"))
    unread_active = seed(db, message="active-unread")
    archived_unread = seed(db, message="archived-unread")
    db.archive_inbox_item(archived_unread, "t1")
    c, db = authed(tmp_path, db)

    body = c.get("/api/v1/notifications").json()
    assert [it["id"] for it in body["items"]] == [unread_active]
    assert body["unread_count"] == 1  # المؤرشف غير المقروء مش محسوب
    assert db.count_inbox(unread_only=True) == 1


def test_pagination_consistent_after_archive(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    ids = [seed(db, message=f"m{i}", read=True) for i in range(12)]
    c, db = authed(tmp_path, db)
    c.post(f"/api/v1/notifications/{ids[0]}/archive", json={}, headers={"origin": ORIGIN})

    p0 = c.get("/api/v1/notifications?page=0").json()
    assert len(p0["items"]) == 10 and p0["has_more"] is True
    p1 = c.get("/api/v1/notifications?page=1").json()
    assert len(p1["items"]) == 1 and p1["has_more"] is False
    all_ids = [it["id"] for it in p0["items"] + p1["items"]]
    assert ids[0] not in all_ids  # المؤرشف برّا الصندوق النشط
    assert len(all_ids) == len(set(all_ids)) == 11


# ======================================================= 3. الحذف النهائي الآمن
def test_delete_eligible_delivered_read_item(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    ident = seed(db, message="x", read=True)
    c, db = authed(tmp_path, db)

    assert c.get("/api/v1/notifications").json()["items"][0]["deletable"] is True
    r = c.delete(f"/api/v1/notifications/{ident}", headers={"origin": ORIGIN})
    assert r.status_code == 200 and r.json()["deleted"] is True
    assert db.get_inbox_item(ident) is None


def test_pending_item_cannot_be_deleted(tmp_path):
    """حدث لسه بيتسلّم (pending) محمي من الحذف النهائي (دليل تسليم معلّق)."""
    db = Database(str(tmp_path / "t.sqlite3"))
    ident = db.add_inbox_event("c1", "t", "terminal", "m", "t0", chat_id=1)
    db.mark_inbox_read(ident, "t1")  # مقروء بس لسه معلّق
    c, db = authed(tmp_path, db)

    assert c.get("/api/v1/notifications").json()["items"][0]["deletable"] is False
    r = c.delete(f"/api/v1/notifications/{ident}", headers={"origin": ORIGIN})
    assert r.status_code == 409
    assert r.json().get("deleted") is not True  # مفيش نجاح كاذب
    assert db.get_inbox_item(ident) is not None  # لسه موجود


def test_unread_item_cannot_be_deleted(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    ident = seed(db, message="x")  # delivered لكن غير مقروء
    c, db = authed(tmp_path, db)

    r = c.delete(f"/api/v1/notifications/{ident}", headers={"origin": ORIGIN})
    assert r.status_code == 409
    assert db.get_inbox_item(ident) is not None


def test_failed_delivery_item_cannot_be_deleted(tmp_path):
    """فشل تسليم (failed) دليل تشغيلي ⇒ مايتحذفش نهائيًا."""
    db = Database(str(tmp_path / "t.sqlite3"))
    ident = db.add_inbox_event("c1", "t", "terminal", "m", "t0", chat_id=1)
    db.mark_inbox_failed(ident, "t1", error="TelegramError")
    db.mark_inbox_read(ident, "t2")
    c, db = authed(tmp_path, db)

    assert db.get_inbox_item(ident).delivery_status == "failed"
    r = c.delete(f"/api/v1/notifications/{ident}", headers={"origin": ORIGIN})
    assert r.status_code == 409
    assert db.get_inbox_item(ident) is not None


def test_reconciliation_evidence_cannot_be_deleted(tmp_path):
    """صف مرجع لعلامة تسوية معلّقة (`notifier_pending.event_id`) مايتحذفش نهائيًا."""
    db = Database(str(tmp_path / "t.sqlite3"))
    ident = db.add_inbox_event("c1", "t", "terminal", "m", "t0", chat_id=1)
    db.mark_inbox_read(ident, "t1")
    # الصف دلوقتي delivered+read (مؤهّل ظاهريًا) بس مربوط بعلامة تسوية معلّقة.
    db.set_notifier_pending("c1", "finished", "t1", event_id=ident, transition_seq=1)
    c, db = authed(tmp_path, db)

    r = c.delete(f"/api/v1/notifications/{ident}", headers={"origin": ORIGIN})
    assert r.status_code == 409  # محمي: دليل تسوية
    assert db.get_inbox_item(ident) is not None
    assert db.get_notifier_pending_row("c1")[0] == ident


def test_delete_missing_item_404(tmp_path):
    c, db = authed(tmp_path, Database(str(tmp_path / "t.sqlite3")))
    assert c.delete("/api/v1/notifications/999", headers={"origin": ORIGIN}).status_code == 404


def test_delete_invalid_id_400(tmp_path):
    c, db = authed(tmp_path, Database(str(tmp_path / "t.sqlite3")))
    assert c.delete("/api/v1/notifications/abc", headers={"origin": ORIGIN}).status_code == 400


def test_delete_requires_origin(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    ident = seed(db, message="x", read=True)
    c, db = authed(tmp_path, db)
    r = c.delete(f"/api/v1/notifications/{ident}", headers={"origin": "https://evil.test"})
    assert r.status_code == 403
    assert db.get_inbox_item(ident) is not None


def test_delete_db_failure_is_not_false_success(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    ident = seed(db, message="x", read=True)
    c, db = authed(tmp_path, db)

    def boom(*_a, **_k):
        raise sqlite3.OperationalError("disk I/O error")

    db.delete_inbox_item = boom  # type: ignore[assignment]
    r = c.delete(f"/api/v1/notifications/{ident}", headers={"origin": ORIGIN})
    assert r.status_code >= 400
    assert db.get_inbox_item(ident) is not None  # لسه موجود (مفيش حذف وهمي)


def test_delete_does_not_touch_operation_records(tmp_path):
    """حذف إشعار نهائيًا مايمسّش صفوف العملية/التسوية/المتابعة."""
    db = Database(str(tmp_path / "t.sqlite3"))
    ident = seed(db, message="x", read=True)
    outbox_id = db.add_or_group_outbox("c1", 42, "hello", "t0", client_ref="ref-1")
    db.set_notifier_pending("c2", "finished", "t0", event_id=999, transition_seq=1)

    c, db = authed(tmp_path, db)
    assert c.delete(f"/api/v1/notifications/{ident}", headers={"origin": ORIGIN}).status_code == 200
    assert db.get_inbox_item(ident) is None
    assert db.get_outbox(outbox_id) is not None
    assert db.get_notifier_pending("c2") == "finished"


def test_other_user_cannot_mutate(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    ident = seed(db, message="x", read=True)
    c, db = build(tmp_path, db)
    r = c.post("/api/v1/auth", json={"initData": make_init_data(OTHER)})
    assert r.status_code == 403
    assert c.post(f"/api/v1/notifications/{ident}/archive", json={}, headers={"origin": ORIGIN}).status_code == 401
    assert c.post(f"/api/v1/notifications/{ident}/unarchive", json={}, headers={"origin": ORIGIN}).status_code == 401
    assert c.delete(f"/api/v1/notifications/{ident}", headers={"origin": ORIGIN}).status_code == 401
    assert db.get_inbox_item(ident) is not None
    assert db.get_inbox_item(ident).archived is False


def test_delete_eligibility_helper_direct(tmp_path):
    """فحص الأهلية المباشر على طبقة القاعدة (pending/unread/read-delivered)."""
    db = Database(str(tmp_path / "t.sqlite3"))
    pending = db.add_inbox_event("c1", "t", "terminal", "m", "t0", chat_id=1)
    unread = seed(db, message="u")
    ready = seed(db, message="r", read=True)

    assert db.inbox_item_delete_eligibility(pending) == "protected"
    assert db.inbox_item_delete_eligibility(unread) == "protected"
    assert db.inbox_item_delete_eligibility(ready) == "deleted"
    assert db.inbox_item_delete_eligibility(123456) == "missing"
    assert db.delete_inbox_item(ready) == "deleted"
    assert db.delete_inbox_item(ready) == "missing"  # اتشال فعلًا


def test_dto_deletable_matches_delete_path(tmp_path):
    """إشارة `deletable` في الـ DTO لازم تطابق نتيجة مسار الحذف الفعلية (مفيش تناقض)."""
    db = Database(str(tmp_path / "t.sqlite3"))
    pending = db.add_inbox_event("c1", "t", "terminal", "m", "t0", chat_id=1)
    db.mark_inbox_read(pending, "t1")
    ready = seed(db, message="ready", read=True)
    c, db = authed(tmp_path, db)

    by_id = {it["id"]: it for it in c.get("/api/v1/notifications").json()["items"]}
    assert by_id[pending]["deletable"] is False
    assert by_id[ready]["deletable"] is True
    # القرار المعلن في الـ DTO لازم يطابق التنفيذ الفعلي.
    assert c.delete(f"/api/v1/notifications/{pending}", headers={"origin": ORIGIN}).status_code == 409
    assert c.delete(f"/api/v1/notifications/{ready}", headers={"origin": ORIGIN}).status_code == 200

