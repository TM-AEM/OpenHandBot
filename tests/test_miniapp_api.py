"""اختبارات الـ API والجلسات للـ Mini App (OHB2-05)."""
from __future__ import annotations

import time

import pytest
from starlette.testclient import TestClient

from bot.config import Config
from bot.web import build_web_app
from bot.web.app import COOKIE_NAME, MAX_BODY_BYTES
from tests._miniapp_helpers import BOT_TOKEN, make_init_data

OWNER = 555
OTHER = 999


def make_config(**over) -> Config:
    base = dict(
        telegram_bot_token=BOT_TOKEN,
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({OWNER}),
        owner_id=OWNER,
        mini_app_cookie_secure=False,
    )
    base.update(over)
    return Config(**base)


@pytest.fixture
def client() -> TestClient:
    return TestClient(build_web_app(make_config(), None))


# ----------------------------------------------------------------- health
def test_health_ok_and_no_secrets(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert BOT_TOKEN not in r.text
    assert "openhands" not in r.text.lower() or body["service"] == "openhandbot-mini"


def test_health_security_headers(client):
    r = client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "no-store"


# ------------------------------------------------------------------- auth
def test_auth_valid_sets_httponly_strict_cookie(client):
    r = client.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    assert r.status_code == 200 and r.json()["ok"] is True
    raw_cookie = r.headers.get("set-cookie", "")
    assert COOKIE_NAME in raw_cookie
    assert "HttpOnly" in raw_cookie
    assert "SameSite=strict" in raw_cookie.lower() or "samesite=strict" in raw_cookie.lower()
    assert "Path=/" in raw_cookie
    # مفيش توكن البوت ولا أي سر في الرد.
    assert BOT_TOKEN not in r.text


def test_auth_missing_initdata(client):
    r = client.post("/api/v1/auth", json={})
    assert r.status_code == 401
    assert r.json()["error"] == "missing_initdata"


def test_auth_invalid_signature(client):
    raw = make_init_data(OWNER)
    r = client.post("/api/v1/auth", json={"initData": raw[:-3] + "zzz"})
    assert r.status_code == 401
    assert r.json()["error"] == "invalid_initdata"


def test_auth_expired_initdata(client):
    old = int(time.time()) - (300 + 120)
    r = client.post("/api/v1/auth", json={"initData": make_init_data(OWNER, auth_date=old)})
    assert r.status_code == 401


def test_auth_unauthorized_user(client):
    r = client.post("/api/v1/auth", json={"initData": make_init_data(OTHER)})
    assert r.status_code == 403
    assert r.json()["error"] == "forbidden"


def test_auth_bad_json(client):
    r = client.post("/api/v1/auth", content=b"not json", headers={"content-type": "application/json"})
    assert r.status_code == 400
    assert r.json()["error"] == "bad_request"


def test_auth_oversized_body_rejected(client):
    big = b'{"initData": "' + b"a" * (MAX_BODY_BYTES + 100) + b'"}'
    r = client.post("/api/v1/auth", content=big, headers={"content-type": "application/json"})
    assert r.status_code == 413
    assert r.json()["error"] == "payload_too_large"


# -------------------------------------------------------------- bootstrap
def test_bootstrap_requires_session(client):
    r = client.get("/api/v1/app/bootstrap")
    assert r.status_code == 401
    assert r.json()["error"] == "unauthenticated"


def test_bootstrap_after_auth(client):
    client.post("/api/v1/auth", json={"initData": make_init_data(OWNER, first_name="منى")})
    r = client.get("/api/v1/app/bootstrap")
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["display_name"] == "منى"
    assert body["mini_app"]["direction"] == "rtl"
    assert "settings" in body and "notifications_enabled" in body["settings"]
    # مفيش أسرار ولا معرّفات داخلية في الرد.
    assert BOT_TOKEN not in r.text
    assert str(OWNER) not in r.text


def test_bootstrap_reads_notifications_from_db(tmp_path):
    from bot.db import Database

    db = Database(str(tmp_path / "t.sqlite3"))
    try:
        db.set_notifications_enabled(False)
        c = TestClient(build_web_app(make_config(), db))
        c.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
        r = c.get("/api/v1/app/bootstrap")
        assert r.json()["settings"]["notifications_enabled"] is False
    finally:
        db.close()


def test_bootstrap_with_forged_cookie_rejected(client):
    client.cookies.set(COOKIE_NAME, "totally-made-up")
    r = client.get("/api/v1/app/bootstrap")
    assert r.status_code == 401


def test_logout_revokes_session(client):
    client.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    assert client.get("/api/v1/app/bootstrap").status_code == 200
    r = client.post("/api/v1/auth/logout")
    assert r.status_code == 200
    # الكوكي اتمسح ⇒ الطلب الجاي غير مصادق.
    client.cookies.clear()
    assert client.get("/api/v1/app/bootstrap").status_code == 401


# ---------------------------------------------------------------- sessions
def test_session_expiry(monkeypatch):
    from bot.web.sessions import SessionStore

    store = SessionStore(ttl=10)
    session = store.create(1, now=1000.0)
    assert store.get(session.token, now=1005.0) is not None
    assert store.get(session.token, now=1011.0) is None


def test_session_tokens_unique_and_opaque():
    from bot.web.sessions import SessionStore

    store = SessionStore(ttl=60)
    a = store.create(1).token
    b = store.create(1).token
    assert a != b
    assert len(a) >= 32


# ------------------------------------------------------------------ static
def test_index_and_static_served(client):
    assert client.get("/").status_code == 200
    assert client.get("/mini/").status_code == 200
    css = client.get("/mini/styles.css")
    assert css.status_code == 200
    assert "immutable" in css.headers.get("cache-control", "")


def test_static_unknown_path_falls_back_to_index(client):
    r = client.get("/mini/does-not-exist")
    assert r.status_code == 200
    assert "OpenHandBot" in r.text


def test_path_traversal_blocked(client):
    r = client.get("/mini/..%2f..%2fmain.py")
    assert r.status_code == 200  # يرجّع الـ index، مش ملف خارجي
    assert "import" not in r.text


def test_api_unknown_route_404(client):
    assert client.get("/api/v1/nope").status_code == 404
