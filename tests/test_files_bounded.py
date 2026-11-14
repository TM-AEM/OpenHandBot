"""اختبارات مستوى النقل للحد الصلب على رد قراءة الملف (OHB2-09-01-FIX).

بتستخدم `httpx.MockTransport` مع تدفّق بايتات وهمي (`ChunkedStream`) عشان تختبر مسار
البثّ الحقيقي — مش `classify_text` على نص جاهز. بتتحقّق من: العدّ التراكمي، التوقّف عند
تجاوز الحد، إغلاق الرد، رفض Content-Length المسبق، فك JSON بعد الحد، والإلغاء.
مفيش أي طلب شبكة حقيقي.
"""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from bot.errors import ApiError, ResponseTooLargeError
from bot.files import FileService, FileStatus
from bot.openhands_client import (
    MAX_FILE_RESPONSE_BYTES,
    OpenHandsClient,
    _content_length,
)

OWNER = "owner-uuid-123"


class ChunkedStream(httpx.AsyncByteStream):
    """تدفّق بايتات وهمي بيسجّل كل قطع اتقرأت وكل إغلاق."""

    def __init__(self, chunks):
        self._chunks = list(chunks)
        self.consumed = 0
        self.closed = False
        self.started = False

    async def __aiter__(self):
        for chunk in self._chunks:
            self.consumed += 1
            yield chunk

    async def aclose(self):
        self.closed = True


class BlockingStream(httpx.AsyncByteStream):
    """تدفّق بيعمل بلوك للأبد بعد أول قطعة (لاختبار الإلغاء)."""

    def __init__(self):
        self.closed = False
        self.first_yielded = asyncio.Event()

    async def __aiter__(self):
        yield b'"aaaa'
        self.first_yielded.set()
        await asyncio.sleep(3600)  # block

    async def aclose(self):
        self.closed = True


def make_client(chunks, *, status=200, headers=None):
    stream = ChunkedStream(chunks)

    def handler(request):
        return httpx.Response(status, headers=headers, stream=stream)

    return OpenHandsClient("https://example.test", "key", transport=httpx.MockTransport(handler)), stream


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------- content_length
def test_content_length_helper_missing_and_invalid():
    resp = httpx.Response(200, headers={}, content=b"")
    assert _content_length(resp) is None
    resp2 = httpx.Response(200, headers={"content-length": "abc"}, content=b"")
    assert _content_length(resp2) is None
    resp3 = httpx.Response(200, headers={"content-length": "-5"}, content=b"")
    assert _content_length(resp3) is None
    resp4 = httpx.Response(200, headers={"content-length": "12"}, content=b"")
    assert _content_length(resp4) == 12


# ------------------------------------------------------------------- 1. below
def test_below_ceiling_ok_and_closes():
    body = json.dumps("hello").encode()
    client, stream = make_client([body])
    out = run(client.read_file_text_bounded("c1", "a.py", max_response_bytes=100))
    assert out == "hello"
    assert stream.closed is True
    assert stream.consumed == 1


# --------------------------------------------------------------- 2. exact ceiling
def test_exactly_at_ceiling_ok():
    raw = json.dumps("xxxxx").encode()  # b'"xxxxx"' == 7 bytes
    assert len(raw) == 7
    client, stream = make_client([raw])
    out = run(client.read_file_text_bounded("c1", "a.py", max_response_bytes=7))
    assert out == "xxxxx"
    assert stream.closed is True


# ------------------------------------------------------------ 3. one byte over
def test_one_byte_over_ceiling_raises():
    raw = json.dumps("xxxxx").encode()  # 7 bytes
    client, stream = make_client([raw])
    with pytest.raises(ResponseTooLargeError):
        run(client.read_file_text_bounded("c1", "a.py", max_response_bytes=6))
    assert stream.closed is True


# ----------------------------------------------- 4. over across multiple chunks
def test_over_ceiling_across_chunks_stops_early():
    # 5 قطع × 4 بايت = 20؛ الحد 8 ⇒ بيتوقف عند القطعة اللي هتعدّي (التالتة).
    chunks = [b"aaaa", b"bbbb", b"cccc", b"dddd", b"eeee"]
    client, stream = make_client(chunks)
    with pytest.raises(ResponseTooLargeError):
        run(client.read_file_text_bounded("c1", "a.py", max_response_bytes=8))
    assert stream.consumed == 3  # قفّل بدري: القطعتين الرابعة والخامسة ماتقروش
    assert stream.closed is True


# -------------------------------------------------------- 5. single oversized chunk
def test_single_oversized_chunk_raises_without_accumulating():
    client, stream = make_client([b"z" * 5000])
    with pytest.raises(ResponseTooLargeError):
        run(client.read_file_text_bounded("c1", "a.py", max_response_bytes=16))
    assert stream.consumed == 1
    assert stream.closed is True


# ------------------------------------------------------- 6. missing Content-Length
def test_missing_content_length_still_bounded():
    client, stream = make_client([b"a" * 100])  # مفيش هيدر content-length
    with pytest.raises(ResponseTooLargeError):
        run(client.read_file_text_bounded("c1", "a.py", max_response_bytes=10))
    assert stream.closed is True


# ------------------------------------- 7. misleading small Content-Length
def test_misleading_small_content_length_still_bounded():
    # الهيدر بيقول 5 بس البثّ الفعلي 100 ⇒ العدّ التراكمي هو اللي بيمسك.
    client, stream = make_client([b"a" * 100], headers={"content-length": "5"})
    with pytest.raises(ResponseTooLargeError):
        run(client.read_file_text_bounded("c1", "a.py", max_response_bytes=10))
    assert stream.closed is True


# --------------------------------- 8. large declared Content-Length rejected early
def test_large_content_length_rejected_before_reading():
    client, stream = make_client([b'"ok"'], headers={"content-length": "999999"})
    with pytest.raises(ResponseTooLargeError):
        run(client.read_file_text_bounded("c1", "a.py", max_response_bytes=100))
    assert stream.consumed == 0  # ماقرأناش ولا قطعة
    assert stream.closed is True


# ---------------------------------------- 9. JSON escaping larger than decoded
def test_json_escaped_wire_larger_than_decoded():
    raw = json.dumps("a\nb").encode()  # b'"a\\nb"' == 6 bytes؛ المفكوك 3 محارف
    assert len(raw) == 6 and len("a\nb") == 3
    client, stream = make_client([raw])
    assert run(client.read_file_text_bounded("c1", "a.py", max_response_bytes=6)) == "a\nb"
    client2, _ = make_client([raw])
    with pytest.raises(ResponseTooLargeError):
        run(client2.read_file_text_bounded("c1", "a.py", max_response_bytes=5))


# ------------------------------------------------------------ 10. invalid JSON
def test_invalid_json_below_ceiling_raises_api_error():
    client, stream = make_client([b"not json at all"])
    with pytest.raises(ApiError):
        run(client.read_file_text_bounded("c1", "a.py", max_response_bytes=100))
    assert stream.closed is True


# ------------------------------------------------------- 11. non-success status
def test_non_success_status_maps_to_api_error():
    client, stream = make_client([b'{"detail":"nope"}'], status=404)
    with pytest.raises(ApiError) as info:
        run(client.read_file_text_bounded("c1", "a.py", max_response_bytes=100))
    assert info.value.status_code == 404
    assert stream.closed is True


# --------------------------------------------------------- 12. non-string body
def test_non_string_json_returns_none():
    client, stream = make_client([b'{"a": 1}'])
    assert run(client.read_file_text_bounded("c1", "a.py", max_response_bytes=100)) is None
    assert stream.closed is True


# ------------------------------------------------- 13. negative limit rejected
def test_negative_limit_rejected():
    client, _ = make_client([b'"x"'])
    with pytest.raises(ValueError):
        run(client.read_file_text_bounded("c1", "a.py", max_response_bytes=-1))


# ---------------------------------------------------- 14. cancellation closes
def test_cancellation_closes_response_and_propagates():
    async def scenario():
        stream = BlockingStream()

        def handler(request):
            return httpx.Response(200, stream=stream)

        client = OpenHandsClient("https://example.test", "key", transport=httpx.MockTransport(handler))
        task = asyncio.create_task(
            client.read_file_text_bounded("c1", "a.py", max_response_bytes=1000)
        )
        await stream.first_yielded.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return stream

    stream = asyncio.run(scenario())
    assert stream.closed is True


# ---------------------------------------------------- 15. production default
def test_production_default_ceiling_is_256kib():
    assert MAX_FILE_RESPONSE_BYTES == 256 * 1024
    # جسم أكبر من الافتراضي بيتحد من غير ما نمرّر حد صريح.
    client, stream = make_client([b"a" * (MAX_FILE_RESPONSE_BYTES + 1)])
    with pytest.raises(ResponseTooLargeError):
        run(client.read_file_text_bounded("c1", "a.py"))
    assert stream.closed is True


# ==================================================== FileService integration
def _fs_client(file_body, *, max_response_bytes=None):
    """عميل حقيقي (MockTransport) بيخدم مسارات المستخدم/الشات/الملفات/القراءة."""
    calls = {"read_bounded": 0, "read_unbounded": 0, "files": 0}

    def handler(request):
        path = request.url.path
        if path == "/api/v1/users/me":
            return httpx.Response(200, json={"id": OWNER})
        if path == "/api/v1/app-conversations":
            return httpx.Response(200, json=[{"id": "c1", "created_by_user_id": OWNER}])
        if path.endswith("/files"):
            calls["files"] += 1
            return httpx.Response(200, json=["a.py"])
        if path.endswith("/file"):
            # نفس اسم الباراميتر الموثّق `file_path` محفوظ في مسار البثّ.
            assert request.url.params.get("file_path") == "a.py"
            # نمرّر stream= لضمان مسار البثّ الحقيقي.
            stream = ChunkedStream([file_body])
            return httpx.Response(200, stream=stream)
        return httpx.Response(404, json={"detail": "no"})

    client = OpenHandsClient("https://example.test", "key", transport=httpx.MockTransport(handler))
    return client, calls


def test_fileservice_reads_via_bounded_method():
    body = json.dumps("print('hi')\n").encode()
    client, calls = _fs_client(body)
    svc = FileService(client)
    res = run(svc.read_preview("c1", "a.py"))
    assert res.status is FileStatus.OK and res.text == "print('hi')\n"
    assert calls["files"] == 1


def test_fileservice_oversized_maps_to_too_large():
    # الحد 16 بايت؛ الجسم أكبر ⇒ FileService يرجّع TOO_LARGE صريح (مش upstream_error).
    client, _ = _fs_client(b'"' + b"x" * 100 + b'"')
    svc = FileService(client, max_bytes=16)
    res = run(svc.read_preview("c1", "a.py"))
    assert res.status is FileStatus.TOO_LARGE


def test_fileservice_never_falls_back_to_unbounded():
    """لو FileService ندى الطريقة غير المحدودة، الاختبار يفشل فورًا."""
    body = json.dumps("data").encode()
    client, _ = _fs_client(body)
    called = {"unbounded": False}

    async def boom(*a, **k):
        called["unbounded"] = True
        raise AssertionError("FileService must not call read_file_text")

    client.read_file_text = boom  # type: ignore[assignment]
    svc = FileService(client)
    res = run(svc.read_preview("c1", "a.py"))
    assert res.status is FileStatus.OK
    assert called["unbounded"] is False


def test_fileservice_authorization_precedes_read():
    calls = {"file": 0}

    def handler(request):
        path = request.url.path
        if path == "/api/v1/users/me":
            return httpx.Response(200, json={"id": OWNER})
        if path == "/api/v1/app-conversations":
            # مالك مختلف ⇒ لازم يترفض قبل أي قراءة.
            return httpx.Response(200, json=[{"id": "c1", "created_by_user_id": "other"}])
        if path.endswith("/files"):
            return httpx.Response(200, json=["a.py"])
        if path.endswith("/file"):
            calls["file"] += 1
            return httpx.Response(200, json="data")
        return httpx.Response(404, json={"detail": "no"})

    client = OpenHandsClient("https://example.test", "key", transport=httpx.MockTransport(handler))
    res = run(FileService(client).read_preview("c1", "a.py"))
    assert res.status is FileStatus.UNAUTHORIZED
    assert calls["file"] == 0


def test_fileservice_preview_classification_still_effective():
    body = json.dumps("abcdefghij").encode()  # 10 محارف مفكوكة
    client, _ = _fs_client(body)
    svc = FileService(client, preview_chars=4)
    res = run(svc.read_preview("c1", "a.py"))
    assert res.status is FileStatus.OK and res.text == "abcd" and res.truncated is True


# ============================================ OHB2-09-01-FIX2: decompression-safe
def _client_capture(chunks, *, status=200, headers=None):
    """عميل بيسجّل الهيدرز المرسلة وبيخدم جسم بثّي خام."""
    stream = ChunkedStream(chunks)
    captured = {}

    def handler(request):
        captured["accept_encoding"] = request.headers.get("accept-encoding")
        return httpx.Response(status, headers=headers, stream=stream)

    return (
        OpenHandsClient("https://example.test", "key", transport=httpx.MockTransport(handler)),
        stream,
        captured,
    )


def test_request_sends_accept_encoding_identity():
    client, _, captured = _client_capture([json.dumps("hi").encode()])
    run(client.read_file_text_bounded("c1", "a.py", max_response_bytes=100))
    assert captured["accept_encoding"] == "identity"


def test_identity_response_succeeds():
    client, _, _ = _client_capture([json.dumps("hi").encode()], headers={"content-encoding": "identity"})
    assert run(client.read_file_text_bounded("c1", "a.py", max_response_bytes=100)) == "hi"


def test_missing_content_encoding_succeeds():
    client, _, _ = _client_capture([json.dumps("hi").encode()])
    assert run(client.read_file_text_bounded("c1", "a.py", max_response_bytes=100)) == "hi"


def test_gzip_response_rejected_safely_and_closed():
    import gzip

    gz = gzip.compress(json.dumps("hi").encode())
    client, stream, _ = _client_capture([gz], headers={"content-encoding": "gzip"})
    with pytest.raises(ApiError):
        run(client.read_file_text_bounded("c1", "a.py", max_response_bytes=100))
    assert stream.closed is True
    assert stream.consumed == 0  # مااتقراش خام أصلًا ⇒ مفيش فكّ ضغط


def test_deflate_response_rejected_safely_and_closed():
    import zlib

    df = zlib.compress(json.dumps("hi").encode())
    client, stream, _ = _client_capture([df], headers={"content-encoding": "deflate"})
    with pytest.raises(ApiError):
        run(client.read_file_text_bounded("c1", "a.py", max_response_bytes=100))
    assert stream.closed is True
    assert stream.consumed == 0


def test_unexpected_encoding_does_not_decompress():
    import gzip

    # payload ضخم مضغوط: لو حصل فكّ ضغط هيتخصّص ميجابايتات؛ لازم نرفض من غير قراءة.
    big = gzip.compress(b"a" * (4 * 1024 * 1024))
    client, stream, _ = _client_capture([big], headers={"content-encoding": "gzip"})
    with pytest.raises(ApiError):
        run(client.read_file_text_bounded("c1", "a.py", max_response_bytes=1024))
    assert stream.consumed == 0
    assert stream.closed is True


def test_server_ignoring_identity_cannot_bypass_policy():
    # السيرفر رجّع deflate رغم طلب identity ⇒ لازم يترفض، مافيش تجاوز.
    import zlib

    df = zlib.compress(json.dumps("x").encode())
    client, stream, captured = _client_capture([df], headers={"content-encoding": "deflate"})
    with pytest.raises(ApiError):
        run(client.read_file_text_bounded("c1", "a.py", max_response_bytes=100))
    assert captured["accept_encoding"] == "identity"
    assert stream.consumed == 0


def test_raw_limit_independent_of_content_length():
    # مفيش Content-Length + بايتات خام أكبر من الحد ⇒ الحد التراكمي بيمسك.
    client, stream, _ = _client_capture([b"a" * 200])
    with pytest.raises(ResponseTooLargeError):
        run(client.read_file_text_bounded("c1", "a.py", max_response_bytes=50))
    assert stream.closed is True


# --------------------------------------------- error-body classification (R3-2)
def test_404_small_error_body_keeps_status():
    client, stream, _ = _client_capture([b'{"detail":"nope"}'], status=404)
    with pytest.raises(ApiError) as info:
        run(client.read_file_text_bounded("c1", "a.py", max_response_bytes=100))
    assert info.value.status_code == 404
    assert stream.closed is True


def test_500_oversized_error_body_keeps_status_not_too_large():
    big = b"x" * (8 * 1024 + 500)  # أكبر من MAX_ERROR_DETAIL_BYTES
    client, stream, _ = _client_capture([big], status=500)
    with pytest.raises(ApiError) as info:
        run(client.read_file_text_bounded("c1", "a.py", max_response_bytes=1024))
    assert info.value.status_code == 500
    assert not isinstance(info.value, ResponseTooLargeError)
    assert stream.closed is True


def test_oversized_error_body_stops_reading_early():
    # قطع كتير أكبر من حد التفاصيل ⇒ بيتوقف بدري (مش بيلمّ الجسم كله).
    chunks = [b"x" * 4096 for _ in range(10)]
    client, stream, _ = _client_capture(chunks, status=500)
    with pytest.raises(ApiError) as info:
        run(client.read_file_text_bounded("c1", "a.py", max_response_bytes=1024))
    assert info.value.status_code == 500
    assert stream.consumed < len(chunks)  # ماقرأناش كل القطع
    assert stream.closed is True


def test_oversized_error_body_not_mapped_to_too_large_by_fileservice():
    calls = {"file": 0}

    class _Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"x" * (8 * 1024 + 500)

    def handler(request):
        path = request.url.path
        if path == "/api/v1/users/me":
            return httpx.Response(200, json={"id": OWNER})
        if path == "/api/v1/app-conversations":
            return httpx.Response(200, json=[{"id": "c1", "created_by_user_id": OWNER}])
        if path.endswith("/files"):
            return httpx.Response(200, json=["a.py"])
        if path.endswith("/file"):
            calls["file"] += 1
            return httpx.Response(500, stream=_Stream())
        return httpx.Response(404, json={"detail": "no"})

    client = OpenHandsClient("https://example.test", "key", transport=httpx.MockTransport(handler))
    res = run(FileService(client).read_preview("c1", "a.py"))
    assert res.status is FileStatus.UPSTREAM_ERROR  # مش TOO_LARGE
    assert calls["file"] == 1


def test_cancellation_during_error_body_propagates_and_closes():
    async def scenario():
        stream = BlockingStream()

        def handler(request):
            return httpx.Response(500, stream=stream)

        client = OpenHandsClient("https://example.test", "key", transport=httpx.MockTransport(handler))
        task = asyncio.create_task(client.read_file_text_bounded("c1", "a.py", max_response_bytes=1000))
        await stream.first_yielded.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return stream

    stream = asyncio.run(scenario())
    assert stream.closed is True


# --------------------------------------------------- _content_encoding helper
def test_content_encoding_helper():
    from bot.openhands_client import _content_encoding

    assert _content_encoding(httpx.Response(200, headers={})) is None
    assert _content_encoding(httpx.Response(200, headers={"content-encoding": "  "})) is None
    assert _content_encoding(httpx.Response(200, headers={"content-encoding": "GZIP"})) == "gzip"
    assert _content_encoding(httpx.Response(200, headers={"content-encoding": "identity"})) == "identity"


# ============================== OHB2-09-01-HARDEN: exotic encoding coverage (H1)
def _reject_encoding(headers):
    """يرجّع (استُثني؟, القطع المقروءة, اتقفل؟) لرد بترميز معيّن."""
    stream = ChunkedStream([b"whatever-bytes-should-not-be-read"])
    captured = {}

    def handler(request):
        captured["ae"] = request.headers.get("accept-encoding")
        return httpx.Response(200, headers=headers, stream=stream)

    client = OpenHandsClient(
        "https://example.test", "key", transport=httpx.MockTransport(handler)
    )
    raised = False
    try:
        run(client.read_file_text_bounded("c1", "a.py", max_response_bytes=1000))
    except ApiError:
        raised = True
    return raised, stream.consumed, stream.closed, captured.get("ae")


@pytest.mark.parametrize(
    "value",
    ["br", "zstd", "x-gzip", "compress", "gzip, deflate", "identity, gzip", "gzip, identity"],
)
def test_exotic_single_and_comma_encodings_rejected_before_read(value):
    raised, consumed, closed, ae = _reject_encoding({"content-encoding": value})
    assert raised is True
    assert consumed == 0  # مفيش بايت خام اتقرا ⇒ مفيش فكّ ضغط
    assert closed is True
    assert ae == "identity"


def test_duplicate_content_encoding_headers_rejected():
    h = httpx.Headers([(b"content-encoding", b"identity"), (b"content-encoding", b"gzip")])
    raised, consumed, closed, _ = _reject_encoding(h)
    assert raised is True
    assert consumed == 0
    assert closed is True


def test_malformed_encoding_values_rejected_not_decompressed():
    # قيم غريبة/بمسافات داخلية: أي حاجة غير identity بالحرف ⇒ رفض (fail closed).
    for value in ["gzip ", " gzip", "gzip;q=1", "identity,", ",identity", "  gzip  "]:
        raised, consumed, closed, _ = _reject_encoding({"content-encoding": value})
        assert raised is True, value
        assert consumed == 0, value
        assert closed is True, value


# ================================ OHB2-09-01-HARDEN: error-status preservation (H2)
class _FailBodyStream(httpx.AsyncByteStream):
    """تدفّق بيفشل أثناء القراءة (نقل) — لاختبار فقدان الحالة."""

    def __init__(self):
        self.closed = False

    async def __aiter__(self):
        raise httpx.ReadTimeout("انقطع")
        yield b""  # pragma: no cover

    async def aclose(self):
        self.closed = True


def test_error_body_transport_failure_preserves_original_status():
    stream = _FailBodyStream()

    def handler(request):
        return httpx.Response(503, stream=stream)

    client = OpenHandsClient(
        "https://example.test", "key", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(ApiError) as info:
        run(client.read_file_text_bounded("c1", "a.py", max_response_bytes=1000))
    assert info.value.status_code == 503  # الحالة الأصلية محفوظة
    assert not isinstance(info.value, ResponseTooLargeError)
    assert stream.closed is True


def test_error_body_transport_failure_not_mapped_to_too_large_by_fileservice():
    class _Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            raise httpx.ReadTimeout("x")
            yield b""

    def handler(request):
        path = request.url.path
        if path == "/api/v1/users/me":
            return httpx.Response(200, json={"id": OWNER})
        if path == "/api/v1/app-conversations":
            return httpx.Response(200, json=[{"id": "c1", "created_by_user_id": OWNER}])
        if path.endswith("/files"):
            return httpx.Response(200, json=["a.py"])
        if path.endswith("/file"):
            return httpx.Response(500, stream=_Stream())
        return httpx.Response(404, json={"detail": "no"})

    client = OpenHandsClient("https://example.test", "key", transport=httpx.MockTransport(handler))
    res = run(FileService(client).read_preview("c1", "a.py"))
    assert res.status is FileStatus.UPSTREAM_ERROR  # مش TOO_LARGE


def test_success_body_transport_failure_does_not_leak_status():
    # فشل النقل على مسار النجاح (200) ⇒ خطأ اتصال عام (مفيش حالة HTTP نسيبة).
    stream = _FailBodyStream()

    def handler(request):
        return httpx.Response(200, stream=stream)

    client = OpenHandsClient("https://example.test", "key", transport=httpx.MockTransport(handler))
    with pytest.raises(ApiError) as info:
        run(client.read_file_text_bounded("c1", "a.py", max_response_bytes=1000))
    assert info.value.status_code is None
    assert stream.closed is True


def test_error_body_stream_consumed_preserves_original_status():
    # جسم خطأ غير قابل للبثّ (اتقرا مقدمًا) ⇒ `StreamConsumed` (RuntimeError مش HTTPError).
    # لازم تفضل الحالة الأصلية موجودة، مش خطأ عام ولا TOO_LARGE.
    def handler(request):
        return httpx.Response(502, json={"detail": "boom"})

    client = OpenHandsClient("https://example.test", "key", transport=httpx.MockTransport(handler))
    with pytest.raises(ApiError) as info:
        run(client.read_file_text_bounded("c1", "a.py", max_response_bytes=1000))
    assert info.value.status_code == 502
    assert not isinstance(info.value, ResponseTooLargeError)
