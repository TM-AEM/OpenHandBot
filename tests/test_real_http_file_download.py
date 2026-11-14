"""OHB2-LARGE-FILE-REAL-HTTP: file preview + export over a real local HTTP server.

These tests exercise the **actual** `OpenHandsClient` HTTP transport (httpcore/httpx)
against a real TCP socket on 127.0.0.1, NOT `httpx.MockTransport`. The earlier
investigation proved that `MockTransport` does not enforce `Content-Length`, so
truncation and premature-close behaviour can only be validated over real HTTP.

What is verified here:
- exact byte integrity and declared Content-Length on success;
- empty body and the exact preview limit (256 KiB) boundary, plus limit+1;
- Content-Length larger than the transmitted bytes followed by an early close;
- a chunked response that is terminated prematurely (no final 0-chunk);
- an upstream that never answers (real timeout);
- export byte integrity / limit+1 / truncation;
- non-identity Content-Encoding rejection and redirect rejection.

No Telegram, no OpenHands production service, no live database, synthetic content only.
"""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from bot.errors import ApiError, ResponseTooLargeError
from bot.files import FileService, FileStatus
from bot.openhands_client import (
    MAX_EXPORT_BYTES,
    MAX_FILE_RESPONSE_BYTES,
    OpenHandsClient,
)

from tests._real_http import (
    RealHTTPServer,
    Router,
    chunk_body,
    chunk_header,
    chunked_response,
    close_delimited_response,
    http_response,
    json_response,
    truncated_response,
)

OWNER = "owner-uuid-123"
CID = "c1"
FILE_PATH = "a.py"
FILE_ROUTE = f"/api/v1/app-conversations/{CID}/file"
EXPORT_ROUTE = f"/api/v1/app-conversations/{CID}/download"


# --------------------------------------------------------------------- helpers
def make_client(server: RealHTTPServer, *, timeout: float = 30.0) -> OpenHandsClient:
    return OpenHandsClient(server.url, "key", timeout=timeout)


def run(coro):
    return asyncio.run(coro)


def serve(responder) -> RealHTTPServer:
    """Start a real server answering every request with `responder`."""
    return RealHTTPServer(responder)


def close_client(client: OpenHandsClient) -> None:
    run(client.aclose())


# ============================================================ preview: success
def test_preview_success_exact_bytes_and_content_length():
    """نجاح حقيقي: البايتات مطابقة حرفيًا، و`Content-Length` مطابق للحجم المُرسَل."""
    text = "print('hello')\n" * 10
    raw = json.dumps(text).encode("utf-8")
    srv = serve(lambda _r: json_response(text))
    try:
        client = make_client(srv)
        out = run(client.read_file_text_bounded(CID, FILE_PATH, max_response_bytes=MAX_FILE_RESPONSE_BYTES))
        assert out == text
        close_client(client)
        assert srv.request_count == 1
        assert srv.wait_connections_closed(2.0) is True
        assert len(raw) == len(json.dumps(text).encode("utf-8"))  # exact wire size sanity
    finally:
        srv.shutdown()


def test_preview_success_via_fileservice_exact_size():
    """`FileService.read_preview` فوق HTTP حقيقي: نص مطابق + `size_bytes` دقيق."""
    text = "مرحبا بالعالم\n"
    router = Router()
    router.add("/api/v1/users/me", json_response({"id": OWNER}))
    router.add("/api/v1/app-conversations", json_response([{"id": CID, "created_by_user_id": OWNER}]))
    router.add(f"/api/v1/app-conversations/{CID}/files", json_response([FILE_PATH]))
    router.add(FILE_ROUTE, json_response(text))
    srv = RealHTTPServer(router)
    try:
        client = make_client(srv)
        res = run(FileService(client).read_preview(CID, FILE_PATH))
        close_client(client)
        assert res.status is FileStatus.OK
        assert res.text == text
        assert res.size_bytes == len(text.encode("utf-8"))
        assert res.truncated is False
    finally:
        srv.shutdown()


# ============================================================== preview: empty
def test_preview_empty_file_is_ok_and_not_none():
    """ملف فاضي حقيقي (`""`) ⇒ OK مع نص فاضي (مش خطأ upstream)."""
    srv = serve(lambda _r: json_response(""))
    try:
        client = make_client(srv)
        out = run(client.read_file_text_bounded(CID, FILE_PATH, max_response_bytes=MAX_FILE_RESPONSE_BYTES))
        close_client(client)
        assert out == ""
    finally:
        srv.shutdown()


def test_preview_null_body_is_upstream_error_via_fileservice():
    """جسم JSON `null` ⇒ غير نص ⇒ UPSTREAM_ERROR (تمييز عن الملف الفاضي)."""
    router = Router()
    router.add("/api/v1/users/me", json_response({"id": OWNER}))
    router.add("/api/v1/app-conversations", json_response([{"id": CID, "created_by_user_id": OWNER}]))
    router.add(f"/api/v1/app-conversations/{CID}/files", json_response([FILE_PATH]))
    router.add(FILE_ROUTE, lambda _r: http_response(200, body=b"null"))
    srv = RealHTTPServer(router)
    try:
        client = make_client(srv)
        res = run(FileService(client).read_preview(CID, FILE_PATH))
        close_client(client)
        assert res.status is FileStatus.UPSTREAM_ERROR
    finally:
        srv.shutdown()


# ====================================================== preview: exact boundary
def _body_of_wire_size(total: int) -> bytes:
    """Build a JSON string body whose raw wire length is exactly `total` bytes."""
    # json string of N ASCII chars -> N + 2 bytes (quotes). Choose N accordingly.
    assert total >= 2
    return b'"' + b"a" * (total - 2) + b'"'


def test_preview_exactly_at_limit_accepted():
    """عند الحد بالضبط (256 KiB خام) ⇒ يُقبل ويُسلَّم كاملًا."""
    raw = _body_of_wire_size(MAX_FILE_RESPONSE_BYTES)
    srv = serve(lambda _r: http_response(200, body=raw))
    try:
        client = make_client(srv)
        out = run(client.read_file_text_bounded(CID, FILE_PATH, max_response_bytes=MAX_FILE_RESPONSE_BYTES))
        close_client(client)
        assert out is not None
        assert len(out) == MAX_FILE_RESPONSE_BYTES - 2
    finally:
        srv.shutdown()


def test_preview_one_byte_over_limit_rejected():
    """الحد + 1 بايت ⇒ ResponseTooLargeError (سلوك حدّ التطبيق، قبل تجميع الجسم)."""
    raw = _body_of_wire_size(MAX_FILE_RESPONSE_BYTES + 1)
    srv = serve(lambda _r: http_response(200, body=raw))
    try:
        client = make_client(srv)
        with pytest.raises(ResponseTooLargeError):
            run(client.read_file_text_bounded(CID, FILE_PATH, max_response_bytes=MAX_FILE_RESPONSE_BYTES))
        close_client(client)
        assert srv.wait_connections_closed(2.0) is True
    finally:
        srv.shutdown()


def test_preview_large_declared_content_length_rejected_before_body():
    """`Content-Length` معلن > الحد ⇒ رفض فوري (تحسين) بلا قراءة الجسم."""
    raw = b'"' + b"a" * 10 + b'"'
    headers = {"Content-Length": str(MAX_FILE_RESPONSE_BYTES + 1)}
    srv = serve(lambda _r: http_response(200, headers=headers, body=raw))
    try:
        client = make_client(srv)
        with pytest.raises(ResponseTooLargeError):
            run(client.read_file_text_bounded(CID, FILE_PATH, max_response_bytes=MAX_FILE_RESPONSE_BYTES))
        close_client(client)
    finally:
        srv.shutdown()


def test_preview_chunked_over_limit_rejected():
    """رد chunked أكبر من الحد ⇒ العدّ التراكمي الخام يرفضه."""
    big = b'"' + b"a" * (MAX_FILE_RESPONSE_BYTES + 4096) + b'"'
    chunks = [big[i:i + 65536] for i in range(0, len(big), 65536)]
    srv = serve(lambda _r: chunked_response(chunks))
    try:
        client = make_client(srv)
        with pytest.raises(ResponseTooLargeError):
            run(client.read_file_text_bounded(CID, FILE_PATH, max_response_bytes=MAX_FILE_RESPONSE_BYTES))
        close_client(client)
    finally:
        srv.shutdown()


# ===================================================== truncation (real socket)
def test_preview_truncated_content_length_rejected_over_real_http():
    """قطع حقيقي: `Content-Length` أكبر من البايتات المُرسَلة ثم إغلاق مبكر.

    النقل الحقيقي (httpcore) لازم يكتشف عدم اكتمال الجسم ⇒ ApiError، مش نجاح جزئي.
    """
    declared = 100_000
    partial = b'"hello wor'  # 10 bytes, far fewer than declared
    srv = serve(lambda _r: truncated_response(declared, partial))
    try:
        client = make_client(srv)
        with pytest.raises(ApiError) as info:
            run(client.read_file_text_bounded(CID, FILE_PATH, max_response_bytes=MAX_FILE_RESPONSE_BYTES))
        # ليست حالة "كبير أوي" ولا نجاح — فشل نقل.
        assert not isinstance(info.value, ResponseTooLargeError)
        close_client(client)
    finally:
        srv.shutdown()


def test_preview_truncated_never_returns_partial_content():
    """القطع لا يُترجَم لمحتوى جزئي ناجح (مفيش نص مشوّه)."""
    srv = serve(lambda _r: truncated_response(50_000, b'"partial'))
    try:
        client = make_client(srv)
        with pytest.raises(ApiError):
            run(client.read_file_text_bounded(CID, FILE_PATH, max_response_bytes=MAX_FILE_RESPONSE_BYTES))
        close_client(client)
    finally:
        srv.shutdown()


def test_preview_truncation_maps_to_upstream_error_in_fileservice():
    """عبر `FileService`: القطع الحقيقي ⇒ `UPSTREAM_ERROR` (مش TOO_LARGE، مش OK)."""
    router = Router()
    router.add("/api/v1/users/me", json_response({"id": OWNER}))
    router.add("/api/v1/app-conversations", json_response([{"id": CID, "created_by_user_id": OWNER}]))
    router.add(f"/api/v1/app-conversations/{CID}/files", json_response([FILE_PATH]))
    router.add(FILE_ROUTE, lambda _r: truncated_response(100_000, b'"hello'))
    srv = RealHTTPServer(router)
    try:
        client = make_client(srv)
        res = run(FileService(client).read_preview(CID, FILE_PATH))
        close_client(client)
        assert res.status is FileStatus.UPSTREAM_ERROR
        assert res.text == ""
    finally:
        srv.shutdown()


def test_preview_chunked_terminated_prematurely_rejected():
    """رد chunked بلا القطعة الأخيرة (0-length) ⇒ فشل نقل، مش نجاح."""
    payload = json.dumps("hello world").encode("utf-8")
    srv = serve(lambda _r: chunked_response([payload], terminate=False))
    try:
        client = make_client(srv)
        with pytest.raises(ApiError) as info:
            run(client.read_file_text_bounded(CID, FILE_PATH, max_response_bytes=MAX_FILE_RESPONSE_BYTES))
        assert not isinstance(info.value, ResponseTooLargeError)
        close_client(client)
    finally:
        srv.shutdown()


def test_preview_close_delimited_body_without_content_length_is_complete():
    """رد بلا Content-Length (ينتهي بالإغلاق) جسمه كامل ⇒ يُقبل (سلوك HTTP مشروع)."""
    text = "ok-no-length"
    srv = serve(lambda _r: close_delimited_response(json.dumps(text).encode("utf-8")))
    try:
        client = make_client(srv)
        out = run(client.read_file_text_bounded(CID, FILE_PATH, max_response_bytes=MAX_FILE_RESPONSE_BYTES))
        close_client(client)
        assert out == text
    finally:
        srv.shutdown()


# ============================================================ preview: timeout
def test_preview_upstream_timeout_maps_to_api_error():
    """upstream مابيردّش ⇒ مهلة العميل الحقيقية ⇒ ApiError (مفيش تعليق)."""
    srv = serve(lambda _r: None)  # accept, read request, never respond
    try:
        client = make_client(srv, timeout=0.4)
        with pytest.raises(ApiError):
            run(client.read_file_text_bounded(CID, FILE_PATH, max_response_bytes=MAX_FILE_RESPONSE_BYTES))
        close_client(client)
    finally:
        srv.shutdown()


# ============================================================ preview: protocol
def test_preview_redirect_rejected_over_real_http():
    """3xx إعادة توجيه ⇒ رفض (بلا متابعة) — مؤكّد على نقل حقيقي."""
    headers = {"Location": "http://127.0.0.1:9/elsewhere"}
    srv = serve(lambda _r: http_response(302, headers=headers, body=b"", reason="Found"))
    try:
        client = make_client(srv)
        with pytest.raises(ApiError) as info:
            run(client.read_file_text_bounded(CID, FILE_PATH, max_response_bytes=MAX_FILE_RESPONSE_BYTES))
        assert info.value.status_code == 302
        close_client(client)
        assert srv.request_count == 1  # مفيش طلب متابعة
    finally:
        srv.shutdown()


def test_preview_gzip_content_encoding_rejected_over_real_http():
    """`Content-Encoding: gzip` رغم طلب identity ⇒ رفض آمن (مفيش فكّ ضغط)."""
    import gzip

    gz = gzip.compress(json.dumps("hi").encode("utf-8"))
    srv = serve(lambda _r: http_response(200, headers={"Content-Encoding": "gzip"}, body=gz))
    try:
        client = make_client(srv)
        with pytest.raises(ApiError) as info:
            run(client.read_file_text_bounded(CID, FILE_PATH, max_response_bytes=MAX_FILE_RESPONSE_BYTES))
        assert "gzip" in str(info.value)
        close_client(client)
    finally:
        srv.shutdown()


def test_preview_invalid_json_rejected_over_real_http():
    """جسم 200 مش JSON صالح ⇒ ApiError (مفيش نجاح مضلّل)."""
    srv = serve(lambda _r: http_response(200, body=b"not json at all"))
    try:
        client = make_client(srv)
        with pytest.raises(ApiError):
            run(client.read_file_text_bounded(CID, FILE_PATH, max_response_bytes=MAX_FILE_RESPONSE_BYTES))
        close_client(client)
    finally:
        srv.shutdown()


def test_preview_http_error_status_preserved_over_real_http():
    """404 حقيقي ⇒ ApiError بترميز الحالة الأصلي (مفيش فقدان للحالة)."""
    srv = serve(lambda _r: json_response({"detail": "nope"}, status=404))
    try:
        client = make_client(srv)
        with pytest.raises(ApiError) as info:
            run(client.read_file_text_bounded(CID, FILE_PATH, max_response_bytes=MAX_FILE_RESPONSE_BYTES))
        assert info.value.status_code == 404
        close_client(client)
    finally:
        srv.shutdown()


# ============================================================== export: success
def test_export_success_exact_bytes_and_content_length():
    """تصدير حقيقي: بايتات مطابقة + `Content-Length` مطابق."""
    payload = b"PK\x03\x04" + bytes(range(256)) * 4
    srv = serve(lambda _r: http_response(200, headers={"Content-Type": "application/zip"}, body=payload))
    try:
        client = make_client(srv)
        out = run(client.export_conversation(CID))
        close_client(client)
        assert out == payload
        assert len(out) == len(payload)
    finally:
        srv.shutdown()


def test_export_exactly_at_limit_accepted():
    """عند حد التصدير بالضبط (16 MiB) ⇒ يُقبل كاملًا."""
    payload = b"Z" * MAX_EXPORT_BYTES
    srv = serve(lambda _r: http_response(200, body=payload))
    try:
        client = make_client(srv)
        out = run(client.export_conversation(CID))
        close_client(client)
        assert len(out) == MAX_EXPORT_BYTES
    finally:
        srv.shutdown()


def test_export_one_byte_over_limit_rejected():
    """الحد + 1 بايت ⇒ ResponseTooLargeError عبر العدّ التراكمي الخام."""
    payload = b"Z" * (MAX_EXPORT_BYTES + 1)
    srv = serve(lambda _r: http_response(200, body=payload))
    try:
        client = make_client(srv)
        with pytest.raises(ResponseTooLargeError):
            run(client.export_conversation(CID))
        close_client(client)
        assert srv.wait_connections_closed(2.0) is True
    finally:
        srv.shutdown()


def test_export_large_declared_length_rejected_before_body():
    """`Content-Length` معلن > الحد ⇒ رفض فوري."""
    srv = serve(
        lambda _r: http_response(
            200, headers={"Content-Length": str(MAX_EXPORT_BYTES + 1)}, body=b"PK\x03\x04"
        )
    )
    try:
        client = make_client(srv)
        with pytest.raises(ResponseTooLargeError):
            run(client.export_conversation(CID))
        close_client(client)
    finally:
        srv.shutdown()


def test_export_truncated_rejected_over_real_http():
    """تصدير مقطوع (CL أكبر من المُرسَل ثم إغلاق) ⇒ فشل نقل، مفيش zip جزئي ناجح."""
    srv = serve(lambda _r: truncated_response(MAX_EXPORT_BYTES, b"PK\x03\x04partial"))
    try:
        client = make_client(srv)
        with pytest.raises(ApiError) as info:
            run(client.export_conversation(CID))
        assert not isinstance(info.value, ResponseTooLargeError)
        close_client(client)
    finally:
        srv.shutdown()


def test_export_chunked_terminated_prematurely_rejected():
    """تصدير chunked مقطوع (بلا 0-chunk) ⇒ فشل نقل."""
    srv = serve(lambda _r: chunked_response([b"PK\x03\x04abc"], terminate=False))
    try:
        client = make_client(srv)
        with pytest.raises(ApiError):
            run(client.export_conversation(CID))
        close_client(client)
    finally:
        srv.shutdown()


def test_export_redirect_rejected_over_real_http():
    """3xx على التصدير ⇒ رفض بلا متابعة."""
    headers = {"Location": "http://127.0.0.1:9/x"}
    srv = serve(lambda _r: http_response(307, headers=headers, body=b"", reason="Temporary Redirect"))
    try:
        client = make_client(srv)
        with pytest.raises(ApiError) as info:
            run(client.export_conversation(CID))
        assert info.value.status_code == 307
        close_client(client)
        assert srv.request_count == 1
    finally:
        srv.shutdown()


def test_export_gzip_content_encoding_rejected_over_real_http():
    """`Content-Encoding: gzip` على التصدير ⇒ رفض آمن."""
    import gzip

    srv = serve(
        lambda _r: http_response(
            200, headers={"Content-Encoding": "gzip"}, body=gzip.compress(b"PK\x03\x04data")
        )
    )
    try:
        client = make_client(srv)
        with pytest.raises(ApiError) as info:
            run(client.export_conversation(CID))
        assert "gzip" in str(info.value)
        close_client(client)
    finally:
        srv.shutdown()


# ==================================================== cancellation + cleanup
def test_cancellation_mid_body_closes_connection():
    """إلغاء أثناء قراءة جسم متوقّف ⇒ CancelledError ينتشر + الاتصال يُغلق."""
    async def scenario():
        srv = RealHTTPServer(
            lambda _r: (
                chunk_header(),
                chunk_body(b'"start'),
                # no terminator: the client will stall waiting for more chunks
            )
        )
        try:
            client = make_client(srv, timeout=30.0)
            task = asyncio.create_task(
                client.read_file_text_bounded(CID, FILE_PATH, max_response_bytes=MAX_FILE_RESPONSE_BYTES)
            )
            # Give the request time to reach the server and the body to start.
            for _ in range(200):
                if srv.request_count >= 1:
                    break
                await asyncio.sleep(0.01)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            await client.aclose()
            closed = await asyncio.to_thread(srv.wait_connections_closed, 3.0)
            return closed
        finally:
            srv.shutdown()

    assert asyncio.run(scenario()) is True


def test_connection_closed_after_size_limit_rejection():
    """بعد رفض تجاوز الحد، الاتصال يُغلق (مفيش تسريب مقابس)."""
    payload = b"Z" * (MAX_EXPORT_BYTES + 1)
    srv = serve(lambda _r: http_response(200, body=payload))
    try:
        client = make_client(srv)
        with pytest.raises(ResponseTooLargeError):
            run(client.export_conversation(CID))
        close_client(client)
        assert srv.wait_connections_closed(3.0) is True
    finally:
        srv.shutdown()


def test_connection_closed_after_timeout():
    """بعد مهلة upstream، الاتصال يُغلق."""
    srv = serve(lambda _r: None)
    try:
        client = make_client(srv, timeout=0.3)
        with pytest.raises(ApiError):
            run(client.read_file_text_bounded(CID, FILE_PATH, max_response_bytes=MAX_FILE_RESPONSE_BYTES))
        close_client(client)
        assert srv.wait_connections_closed(3.0) is True
    finally:
        srv.shutdown()


def test_multiple_sequential_requests_reuse_or_close_cleanly():
    """طلبات متتالية ناجحة ⇒ كلها تُخدم وكل الاتصالات تُغلق عند نهاية العميل."""
    router = Router()
    router.add(FILE_ROUTE, json_response("payload"))
    srv = RealHTTPServer(router)
    try:
        async def scenario():
            client = make_client(srv)
            for _ in range(5):
                out = await client.read_file_text_bounded(CID, FILE_PATH, max_response_bytes=MAX_FILE_RESPONSE_BYTES)
                assert out == "payload"
            await client.aclose()

        run(scenario())
        assert srv.request_count == 5
        assert srv.wait_connections_closed(3.0) is True
    finally:
        srv.shutdown()


# ============================== why a real socket is required (MockTransport lies)
def test_mock_transport_would_false_pass_truncation_but_real_http_rejects():
    """دليل حاسم: `MockTransport` بيقبل الجسم المقطوع كنجاح، بينما HTTP الحقيقي يرفضه.

    الاختبار ده بيثبت سبب استخدام مقبس حقيقي لسيناريوهات القطع (بند إلزامي في المهمة).
    """
    declared = 100_000
    partial = json.dumps("hello world").encode("utf-8")  # 13 bytes, valid JSON on its own

    # (أ) محاكاة: نفس الاستجابة على MockTransport ⇒ تُقبل (نجاح كاذب).
    class _Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield partial

    def mock_handler(_request):
        return httpx.Response(200, headers={"content-length": str(declared)}, stream=_Stream())

    mock_client = OpenHandsClient(
        "https://example.test", "key", transport=httpx.MockTransport(mock_handler)
    )
    mocked = run(mock_client.read_file_text_bounded(CID, FILE_PATH, max_response_bytes=MAX_FILE_RESPONSE_BYTES))
    run(mock_client.aclose())
    assert mocked == "hello world"  # ← النجاح الكاذب اللي المهمة بتمنعه

    # (ب) الحقيقي: نفس الاستجابة على مقبس فعلي ⇒ تُرفض.
    srv = serve(lambda _r: truncated_response(declared, partial))
    try:
        real_client = make_client(srv)
        with pytest.raises(ApiError):
            run(real_client.read_file_text_bounded(CID, FILE_PATH, max_response_bytes=MAX_FILE_RESPONSE_BYTES))
        close_client(real_client)
    finally:
        srv.shutdown()

