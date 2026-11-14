"""OHB2-LARGE-FILE-REAL-HTTP: Mini App routes against a real local upstream server.

The Mini App routes are exercised through Starlette's `TestClient` (the actual ASGI
application and its real response construction), while the upstream OpenHands side is a
real HTTP server on 127.0.0.1 — not `httpx.MockTransport`. Authentication stays fully
isolated: `initData` is generated locally with the test bot token, no Telegram call.

Verified here: successful preview/export byte integrity and headers; preview and export
size boundaries (limit and limit+1); truncation and premature chunked termination never
produce a successful complete download; non-identity encoding and redirects are rejected.
"""
from __future__ import annotations

import json

from starlette.testclient import TestClient

from bot.config import Config
from bot.openhands_client import MAX_EXPORT_BYTES, MAX_FILE_RESPONSE_BYTES, OpenHandsClient
from bot.web import build_web_app

from tests._miniapp_helpers import BOT_TOKEN, make_init_data
from tests._real_http import (
    RealHTTPServer,
    Router,
    chunked_response,
    http_response,
    json_response,
    truncated_response,
)

OWNER = 555
OTHER = 999
OWNER_UUID = "owner-uuid-123"
CID = "c1"
FILE_PATH = "src/main.py"


def make_config(upstream_url: str, **over) -> Config:
    base = dict(
        telegram_bot_token=BOT_TOKEN,
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({OWNER}),
        owner_id=OWNER,
        openhands_base_url=upstream_url,
        mini_app_cookie_secure=False,
    )
    base.update(over)
    return Config(**base)


def build(upstream: RealHTTPServer) -> TestClient:
    client = OpenHandsClient(upstream.url, "key", timeout=30.0)
    app = build_web_app(make_config(upstream.url), None, client=client)
    return TestClient(app, raise_server_exceptions=False)


def login(tc: TestClient, user_id: int = OWNER) -> None:
    resp = tc.post("/api/v1/auth", json={"initData": make_init_data(user_id)})
    assert resp.status_code == 200


def auth_router(**over) -> Router:
    """Upstream routes for a normal authorized conversation; overridable per test."""
    conv_owner = over.get("conv_owner", OWNER_UUID)
    identity = over.get("identity", OWNER_UUID)
    files = over.get("files", [FILE_PATH])
    router = Router()
    if identity is None:
        router.add("/api/v1/users/me", json_response({}))
    else:
        router.add("/api/v1/users/me", json_response({"id": identity, "role": "owner"}))
    if conv_owner is None:
        router.add("/api/v1/app-conversations", json_response([{"id": CID}]))
    else:
        router.add("/api/v1/app-conversations", json_response([{"id": CID, "created_by_user_id": conv_owner}]))
    router.add(f"/api/v1/app-conversations/{CID}/files", json_response(list(files)))
    return router


# ============================================================== preview: success
def test_miniapp_preview_success_exact_bytes():
    """مسار المعاينة: نص مطابق + `size_bytes` دقيق، من upstream حقيقي."""
    text = "def main():\n    return 42\n"
    router = auth_router()
    router.add(f"/api/v1/app-conversations/{CID}/file", json_response(text))
    srv = RealHTTPServer(router)
    try:
        tc = build(srv)
        login(tc)
        resp = tc.get(f"/api/v1/conversations/{CID}/file", params={"path": FILE_PATH})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["text"] == text
        assert body["size_bytes"] == len(text.encode("utf-8"))
        assert body["truncated"] is False
    finally:
        srv.shutdown()


def test_miniapp_preview_empty_file():
    """ملف فاضي حقيقي ⇒ 200 مع نص فاضي."""
    router = auth_router()
    router.add(f"/api/v1/app-conversations/{CID}/file", json_response(""))
    srv = RealHTTPServer(router)
    try:
        tc = build(srv)
        login(tc)
        resp = tc.get(f"/api/v1/conversations/{CID}/file", params={"path": FILE_PATH})
        assert resp.status_code == 200
        assert resp.json()["text"] == ""
        assert resp.json()["size_bytes"] == 0
    finally:
        srv.shutdown()


def test_miniapp_preview_exactly_at_limit_accepted():
    """عند حد المعاينة بالضبط (256 KiB خام) ⇒ 200."""
    raw = b'"' + b"a" * (MAX_FILE_RESPONSE_BYTES - 2) + b'"'
    router = auth_router()
    router.add(f"/api/v1/app-conversations/{CID}/file", lambda _r: http_response(200, body=raw))
    srv = RealHTTPServer(router)
    try:
        tc = build(srv)
        login(tc)
        resp = tc.get(f"/api/v1/conversations/{CID}/file", params={"path": FILE_PATH})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
    finally:
        srv.shutdown()


def test_miniapp_preview_one_byte_over_limit_is_413():
    """الحد + 1 ⇒ 413 `too_large` (سلوك حدّ التطبيق)."""
    raw = b'"' + b"a" * (MAX_FILE_RESPONSE_BYTES - 1) + b'"'
    router = auth_router()
    router.add(f"/api/v1/app-conversations/{CID}/file", lambda _r: http_response(200, body=raw))
    srv = RealHTTPServer(router)
    try:
        tc = build(srv)
        login(tc)
        resp = tc.get(f"/api/v1/conversations/{CID}/file", params={"path": FILE_PATH})
        assert resp.status_code == 413
        assert resp.json()["error"] == "too_large"
    finally:
        srv.shutdown()


def test_miniapp_preview_truncated_is_502_not_success():
    """قطع حقيقي عبر المسار ⇒ 502 `upstream_error`، مفيش محتوى جزئي ناجح."""
    router = auth_router()
    router.add(f"/api/v1/app-conversations/{CID}/file", lambda _r: truncated_response(100_000, b'"partial'))
    srv = RealHTTPServer(router)
    try:
        tc = build(srv)
        login(tc)
        resp = tc.get(f"/api/v1/conversations/{CID}/file", params={"path": FILE_PATH})
        assert resp.status_code == 502
        assert resp.json()["error"] == "upstream_error"
    finally:
        srv.shutdown()


def test_miniapp_preview_chunked_truncated_is_502():
    """chunked بلا 0-chunk عبر المسار ⇒ 502، مفيش نجاح."""
    payload = json.dumps("hello").encode("utf-8")
    router = auth_router()
    router.add(f"/api/v1/app-conversations/{CID}/file", lambda _r: chunked_response([payload], terminate=False))
    srv = RealHTTPServer(router)
    try:
        tc = build(srv)
        login(tc)
        resp = tc.get(f"/api/v1/conversations/{CID}/file", params={"path": FILE_PATH})
        assert resp.status_code == 502
    finally:
        srv.shutdown()


def test_miniapp_preview_gzip_rejected_is_502():
    """`Content-Encoding: gzip` عبر المسار ⇒ 502 (رفض آمن)."""
    import gzip

    router = auth_router()
    router.add(
        f"/api/v1/app-conversations/{CID}/file",
        lambda _r: http_response(200, headers={"Content-Encoding": "gzip"}, body=gzip.compress(b'"x"')),
    )
    srv = RealHTTPServer(router)
    try:
        tc = build(srv)
        login(tc)
        resp = tc.get(f"/api/v1/conversations/{CID}/file", params={"path": FILE_PATH})
        assert resp.status_code == 502
    finally:
        srv.shutdown()


def test_miniapp_preview_other_owner_is_403_no_read():
    """مالك مختلف ⇒ 403، وصفر نداء قراءة ملف (fail closed) — مع upstream حقيقي."""
    router = auth_router(conv_owner="someone-else")
    read_hits = {"n": 0}

    def file_responder(_r):
        read_hits["n"] += 1
        return json_response("should-not-be-read")

    router.add(f"/api/v1/app-conversations/{CID}/file", file_responder)
    srv = RealHTTPServer(router)
    try:
        tc = build(srv)
        login(tc)
        resp = tc.get(f"/api/v1/conversations/{CID}/file", params={"path": FILE_PATH})
        assert resp.status_code == 403
        assert read_hits["n"] == 0
    finally:
        srv.shutdown()


# =============================================================== export: routes
def test_miniapp_export_success_headers_and_exact_bytes():
    """مسار التصدير: بايتات مطابقة + `Content-Length` مطابق + اسم تنزيل آمن."""
    payload = b"PK\x03\x04" + bytes(range(256)) * 8
    router = auth_router()
    router.add(f"/api/v1/app-conversations/{CID}/download", lambda _r: http_response(200, body=payload))
    srv = RealHTTPServer(router)
    try:
        tc = build(srv)
        login(tc)
        resp = tc.get(f"/api/v1/conversations/{CID}/export")
        assert resp.status_code == 200
        assert resp.content == payload
        assert resp.headers["content-type"] == "application/zip"
        assert resp.headers["content-disposition"] == f'attachment; filename="conversation-{CID}.zip"'
        assert int(resp.headers["content-length"]) == len(payload)
        assert resp.headers["x-content-type-options"] == "nosniff"
    finally:
        srv.shutdown()


def test_miniapp_export_one_byte_over_limit_is_413():
    """الحد + 1 (16 MiB + 1) عبر المسار ⇒ 413 `too_large`، مفيش ملف."""
    payload = b"Z" * (MAX_EXPORT_BYTES + 1)
    router = auth_router()
    router.add(f"/api/v1/app-conversations/{CID}/download", lambda _r: http_response(200, body=payload))
    srv = RealHTTPServer(router)
    try:
        tc = build(srv)
        login(tc)
        resp = tc.get(f"/api/v1/conversations/{CID}/export")
        assert resp.status_code == 413
        assert resp.json()["error"] == "too_large"
        assert "content-disposition" not in resp.headers
    finally:
        srv.shutdown()


def test_miniapp_export_truncated_is_not_success():
    """تصدير مقطوع ⇒ رد خطأ، مفيش `Content-Disposition` ولا بايتات جزئية ناجحة."""
    router = auth_router()
    router.add(
        f"/api/v1/app-conversations/{CID}/download",
        lambda _r: truncated_response(MAX_EXPORT_BYTES, b"PK\x03\x04partial"),
    )
    srv = RealHTTPServer(router)
    try:
        tc = build(srv)
        login(tc)
        resp = tc.get(f"/api/v1/conversations/{CID}/export")
        assert resp.status_code >= 400
        assert "content-disposition" not in resp.headers
    finally:
        srv.shutdown()


def test_miniapp_export_chunked_truncated_is_not_success():
    """chunked مقطوع ⇒ رد خطأ، مفيش تنزيل."""
    router = auth_router()
    router.add(
        f"/api/v1/app-conversations/{CID}/download",
        lambda _r: chunked_response([b"PK\x03\x04abc"], terminate=False),
    )
    srv = RealHTTPServer(router)
    try:
        tc = build(srv)
        login(tc)
        resp = tc.get(f"/api/v1/conversations/{CID}/export")
        assert resp.status_code >= 400
        assert "content-disposition" not in resp.headers
    finally:
        srv.shutdown()


def test_miniapp_export_redirect_rejected():
    """3xx على التصدير ⇒ رد خطأ، مفيش متابعة ولا تنزيل."""
    router = auth_router()
    router.add(
        f"/api/v1/app-conversations/{CID}/download",
        lambda _r: http_response(307, headers={"Location": "http://127.0.0.1:9/x"}, body=b""),
    )
    srv = RealHTTPServer(router)
    try:
        tc = build(srv)
        login(tc)
        resp = tc.get(f"/api/v1/conversations/{CID}/export")
        assert resp.status_code >= 400
        assert "content-disposition" not in resp.headers
    finally:
        srv.shutdown()


def test_miniapp_export_gzip_rejected():
    """`Content-Encoding: gzip` على التصدير ⇒ رد خطأ."""
    import gzip

    router = auth_router()
    router.add(
        f"/api/v1/app-conversations/{CID}/download",
        lambda _r: http_response(200, headers={"Content-Encoding": "gzip"}, body=gzip.compress(b"PK\x03\x04x")),
    )
    srv = RealHTTPServer(router)
    try:
        tc = build(srv)
        login(tc)
        resp = tc.get(f"/api/v1/conversations/{CID}/export")
        assert resp.status_code >= 400
    finally:
        srv.shutdown()


def test_miniapp_export_requires_auth_before_upstream():
    """بلا مصادقة ⇒ 401 وصفر نداءات upstream (الخادم الحقيقي ما اتلمسش)."""
    router = auth_router()
    router.add(f"/api/v1/app-conversations/{CID}/download", lambda _r: http_response(200, body=b"PK"))
    srv = RealHTTPServer(router)
    try:
        tc = build(srv)
        resp = tc.get(f"/api/v1/conversations/{CID}/export")
        assert resp.status_code == 401
        assert srv.request_count == 0
    finally:
        srv.shutdown()


def test_miniapp_other_owner_export_forbidden_no_download():
    """مالك مختلف ⇒ 403، وصفر نداء تنزيل."""
    router = auth_router(conv_owner="someone-else")
    hits = {"n": 0}

    def download_responder(_r):
        hits["n"] += 1
        return http_response(200, body=b"PK\x03\x04zip")

    router.add(f"/api/v1/app-conversations/{CID}/download", download_responder)
    srv = RealHTTPServer(router)
    try:
        tc = build(srv)
        login(tc)
        resp = tc.get(f"/api/v1/conversations/{CID}/export")
        assert resp.status_code == 403
        assert hits["n"] == 0
    finally:
        srv.shutdown()
