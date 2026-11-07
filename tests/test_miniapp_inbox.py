"""OHB2-08-05: اختبارات صندوق الإشعارات عبر الـ Mini App API.

بتستخدم قاعدة البيانات الحقيقية (Database) وتطبيق الـ API الحقيقي، عشان تتأكد إن
الصندوق بيتسجّل، بيتقرأ بترقيم محدود، وبيتعلم كمقروء، ومحمي بالمصادقة/الأصل.
"""
from __future__ import annotations

from starlette.testclient import TestClient

from bot.config import Config
from bot.db import Database
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


# ------------------------------------------------------------------ auth
def test_inbox_requires_auth(tmp_path):
    c, _ = build(tmp_path, Database(str(tmp_path / "t.sqlite3")))
    assert c.get("/api/v1/notifications").status_code == 401
    assert c.post("/api/v1/notifications/1/read", json={}).status_code == 401
    assert c.post("/api/v1/notifications/read-all", json={}).status_code == 401


def test_inbox_read_mutations_require_origin(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_inbox_item("c1", "t", "terminal", "x", "t0")
    c, db = authed(tmp_path, db)
    # طلب تغيير حالة بدون Origin مسموح (same-origin من غير Origin header) — بس
    # لازم يكون من أصل مسموح لو الـ Origin موجود. هنا نجرب الأصل المرفوض.
    r = c.post("/api/v1/notifications/read-all", json={}, headers={"origin": "https://evil.test"})
    assert r.status_code == 403
    assert db.count_inbox(unread_only=True) == 1  # ما اتغيّرش


# ------------------------------------------------------------- list/read
def test_inbox_list_pagination_and_unread_count(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    for i in range(12):
        db.add_inbox_item("c1", f"t{i}", "terminal", f"m{i}", f"t{i}")
    c, db = authed(tmp_path, db)

    r = c.get("/api/v1/notifications?page=0")
    assert r.status_code == 200
    body = r.json()
    assert body["page"] == 0
    assert body["has_more"] is True
    assert body["unread_count"] == 12
    assert len(body["items"]) == 10
    # الأحدث أولًا + مفيش تسريب حقول داخلية.
    assert body["items"][0]["message"] == "m11"
    assert set(body["items"][0]) == {
        "id", "conversation_id", "title", "kind", "message", "created_at", "read",
        "archived", "deletable",
        "delivery_status", "delivery_attempts", "delivered_at",
    }

    r2 = c.get("/api/v1/notifications?page=1")
    assert len(r2.json()["items"]) == 2
    assert r2.json()["has_more"] is False


def test_inbox_unread_filter(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    a = db.add_inbox_item("c1", "t", "terminal", "x", "t0")
    db.add_inbox_item("c1", "t", "proactive", "y", "t1")
    db.mark_inbox_read(a, "t2")
    c, db = authed(tmp_path, db)

    body = c.get("/api/v1/notifications?unread=1").json()
    assert body["unread_count"] == 1
    assert [it["message"] for it in body["items"]] == ["y"]


def test_inbox_mark_read_and_unread_count(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    a = db.add_inbox_item("c1", "t", "terminal", "x", "t0")
    db.add_inbox_item("c1", "t", "terminal", "y", "t1")
    c, db = authed(tmp_path, db)

    r = c.post(f"/api/v1/notifications/{a}/read", json={}, headers={"origin": ORIGIN})
    assert r.status_code == 200
    assert r.json()["unread_count"] == 1

    # idempotent: إعادة التعليم ترجّع 200 ونفس العدّ.
    r2 = c.post(f"/api/v1/notifications/{a}/read", json={}, headers={"origin": ORIGIN})
    assert r2.status_code == 200 and r2.json()["unread_count"] == 1


def test_inbox_mark_read_missing_404(tmp_path):
    c, db = authed(tmp_path, Database(str(tmp_path / "t.sqlite3")))
    r = c.post("/api/v1/notifications/999/read", json={}, headers={"origin": ORIGIN})
    assert r.status_code == 404


def test_inbox_mark_read_invalid_id_400(tmp_path):
    c, db = authed(tmp_path, Database(str(tmp_path / "t.sqlite3")))
    r = c.post("/api/v1/notifications/abc/read", json={}, headers={"origin": ORIGIN})
    assert r.status_code == 400


def test_inbox_read_all(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    for i in range(3):
        db.add_inbox_item("c1", "t", "terminal", f"m{i}", "t0")
    c, db = authed(tmp_path, db)

    r = c.post("/api/v1/notifications/read-all", json={}, headers={"origin": ORIGIN})
    assert r.status_code == 200
    assert r.json()["marked"] == 3
    assert r.json()["unread_count"] == 0
    assert db.count_inbox(unread_only=True) == 0


def test_bootstrap_includes_inbox_unread_count(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_inbox_item("c1", "t", "terminal", "x", "t0")
    db.add_inbox_item("c1", "t", "proactive", "y", "t1")
    c, db = authed(tmp_path, db)

    body = c.get("/api/v1/app/bootstrap").json()
    assert body["inbox"]["unread_count"] == 2


def test_inbox_empty_when_db_missing(tmp_path):
    """من غير قاعدة بيانات: الصندوق يرجّع فاضي (مفيش انهيار) وبوتستراب عدّ=0."""
    c, _ = authed(tmp_path, None)
    r = c.get("/api/v1/notifications")
    assert r.status_code == 200
    assert r.json()["items"] == [] and r.json()["unread_count"] == 0
    assert c.get("/api/v1/app/bootstrap").json()["inbox"]["unread_count"] == 0


# ------------------------------------------- OHB2-08-05: idempotency + privacy
def test_inbox_duplicate_event_not_listed_twice(tmp_path):
    """حدث منطقي واحد (نفس event_key) ⇒ عنصر واحد بس في القايمة عبر الـ API."""
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_inbox_item("c1", "t", "terminal", "x", "t0", event_key="c1|terminal|s1|running")
    db.add_inbox_item("c1", "t", "terminal", "y", "t1", event_key="c1|terminal|s1|running")
    c, db = authed(tmp_path, db)

    body = c.get("/api/v1/notifications").json()
    assert len(body["items"]) == 1
    assert body["unread_count"] == 1


def test_inbox_dto_does_not_leak_event_key(tmp_path):
    """الـ DTO ما بيكشفش مفتاح الحدث الداخلي (مفيش حمولة داخلية)."""
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_inbox_item("c1", "t", "terminal", "x", "t0", event_key="secret-internal-key")
    c, db = authed(tmp_path, db)

    item = c.get("/api/v1/notifications").json()["items"][0]
    assert "event_key" not in item
    assert set(item) == {
        "id", "conversation_id", "title", "kind", "message", "created_at", "read",
        "archived", "deletable",
        "delivery_status", "delivery_attempts", "delivered_at",
    }
    assert "secret-internal-key" not in str(item)
    assert item["delivery_status"] == "delivered"  # متوافق للخلف: add_inbox_item = delivered


def test_inbox_non_owner_cannot_read_or_mutate(tmp_path):
    """مستخدم غير المالك ما يقدرش لا يقرا ولا يعلّم (مفيش تسريب بيانات عبر مستخدم تاني)."""
    db = Database(str(tmp_path / "t.sqlite3"))
    db.add_inbox_item("c1", "t", "terminal", "سرّي", "t0")
    c, db = build(tmp_path, db)
    r = c.post("/api/v1/auth", json={"initData": make_init_data(OTHER)})
    assert r.status_code == 403  # مش مسموح أصلاً
    assert c.get("/api/v1/notifications").status_code == 401
    assert db.count_inbox(unread_only=True) == 1  # ما اتغيّرش
