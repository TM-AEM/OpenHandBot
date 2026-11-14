"""OHB2-N10-28D: تقوية عقد HTTP مع OpenHands + دورة حياة طلب الشات.

بيغطّي: التحقق من الحالة (رفض إعادة التوجيه 3xx، ومعالجة 4xx/5xx)، وفك JSON آمن
(HTML/نص/مصفوفة/أنواع غلط)، والتحقق من المعرّفات المطلوبة، وعدم كشف الأسرار في
الاستثناءات، وحالة طلب الشات بعد رد مشوّه (unknown مش 'starting').
"""
import asyncio

import httpx
import pytest

from bot.db import Database
from bot.errors import ApiError
from bot.openhands_client import OpenHandsClient
from bot.outbox import CreationWorker

from tests.test_outbox import Bot


def _client(handler, key="key"):
    return OpenHandsClient("https://example.test", key, transport=httpx.MockTransport(handler))


# ================================================== الحالة (2xx/3xx/4xx/5xx)
def test_start_conversation_success_returns_task_id():
    def handler(request):
        assert request.method == "POST"
        assert request.url.path == "/api/v1/app-conversations"
        return httpx.Response(201, json={"id": "task-1"})

    assert asyncio.run(_client(handler).start_conversation("x", "o/r")) == "task-1"


def test_redirects_are_rejected_not_followed():
    seen = {"n": 0}

    def handler(request):
        seen["n"] += 1
        return httpx.Response(302, headers={"location": "https://evil.test/steal"})

    client = _client(handler)
    with pytest.raises(ApiError) as ei:
        asyncio.run(client.search_conversations())
    assert ei.value.status_code == 302
    assert seen["n"] == 1  # مفيش طلب تاني (مفيش متابعة لإعادة التوجيه)


def test_all_redirect_codes_rejected():
    for code in (301, 302, 303, 307, 308):
        client = _client(lambda r, c=code: httpx.Response(c, headers={"location": "x"}))
        with pytest.raises(ApiError) as ei:
            asyncio.run(client.get_current_user())
        assert ei.value.status_code == code


def test_error_statuses_raise_api_error_with_code():
    for code in (400, 401, 403, 404, 409, 429, 500, 502, 503, 504):
        client = _client(lambda r, c=code: httpx.Response(c, json={"detail": "x"}))
        with pytest.raises(ApiError) as ei:
            asyncio.run(client.search_conversations())
        assert ei.value.status_code == code


# ================================================== فك JSON آمن + التحقق
def test_start_conversation_malformed_body_is_safe_api_error():
    def handler(request):
        return httpx.Response(200, content=b"<html>proxy error</html>")

    with pytest.raises(ApiError):
        asyncio.run(_client(handler).start_conversation("x", "o/r"))


def test_start_conversation_non_dict_body_is_safe_api_error():
    for payload in ([1, 2, 3], "text", 42, True):
        client = _client(lambda r, p=payload: httpx.Response(200, json=p))
        with pytest.raises(ApiError):
            asyncio.run(client.start_conversation("x", "o/r"))


def test_start_conversation_missing_or_invalid_id_is_safe_api_error():
    for payload in ({}, {"id": None}, {"id": ""}, {"id": "   "}, {"id": 123}, {"id": ["a"]}):
        client = _client(lambda r, p=payload: httpx.Response(200, json=p))
        with pytest.raises(ApiError):
            asyncio.run(client.start_conversation("x", "o/r"))


def test_wait_for_start_ready_with_invalid_id_is_safe_api_error():
    def handler(request):
        return httpx.Response(200, json=[{"status": "READY", "app_conversation_id": 5}])

    with pytest.raises(ApiError):
        asyncio.run(_client(handler).wait_for_start("t", timeout=0.05, interval=0))


def test_empty_body_on_json_endpoint_is_safe_api_error():
    def handler(request):
        return httpx.Response(200, content=b"")

    with pytest.raises(ApiError):
        asyncio.run(_client(handler).get_current_user())


# ================================================== عدم كشف الأسرار
def test_api_key_never_appears_in_exception_or_headers():
    secret = "SUPER-SECRET-KEY-123"
    seen_auth = {}

    def handler(request):
        seen_auth["auth"] = request.headers.get("authorization")
        return httpx.Response(401, json={"detail": "unauthorized"})

    client = _client(handler, key=secret)
    with pytest.raises(ApiError) as ei:
        asyncio.run(client.search_conversations())
    assert secret not in str(ei.value)
    assert secret not in repr(ei.value)
    assert seen_auth["auth"] == f"Bearer {secret}"  # بيتبعت للـ API بس مش بيتعرض في الخطأ


# ================================================== دورة حياة طلب الشات
def test_malformed_start_response_marks_job_unknown_not_starting(tmp_path):
    """رد بدء مش JSON (HTML) ⇒ الطلب 'unknown' مش عالق 'starting' للأبد."""
    def handler(request):
        if request.method == "POST" and request.url.path == "/api/v1/app-conversations":
            return httpx.Response(200, content=b"<html>bad gateway</html>")
        return httpx.Response(200, json={})

    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(99, "o/r", "برومت", "t")
    worker = CreationWorker(_client(handler), db, Bot(), "https://app.all-hands.dev")
    asyncio.run(worker._tick())
    job = db.get_creation_job(jid)
    assert job.status == "unknown"     # مش 'starting'
    assert job.task_id is None
    # ambiguous ⇒ مفيش إعادة POST تلقائية.
    starts = {"n": 0}

    def counting(request):
        if request.method == "POST":
            starts["n"] += 1
        return httpx.Response(200, content=b"<html>bad gateway</html>")

    worker2 = CreationWorker(_client(counting), db, Bot(), "https://app.all-hands.dev")
    asyncio.run(worker2._tick())
    assert starts["n"] == 0  # 'unknown' مش مؤهّل ⇒ مفيش POST تاني


def test_definite_start_rejection_marks_job_failed(tmp_path):
    def handler(request):
        return httpx.Response(422, json={"detail": "bad repo"})

    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(99, "o/r", "برومت", "t")
    worker = CreationWorker(_client(handler), db, Bot(), "https://app.all-hands.dev")
    asyncio.run(worker._tick())
    assert db.get_creation_job(jid).status == "failed"


def test_ambiguous_start_timeout_marks_unknown(tmp_path):
    def handler(request):
        raise httpx.ConnectError("boom")

    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(99, "o/r", "برومت", "t")
    worker = CreationWorker(_client(handler), db, Bot(), "https://app.all-hands.dev")
    asyncio.run(worker._tick())
    assert db.get_creation_job(jid).status == "unknown"


def test_valid_start_records_task_id_and_done(tmp_path):
    def handler(request):
        if request.method == "POST" and request.url.path == "/api/v1/app-conversations":
            return httpx.Response(201, json={"id": "task-77"})
        if request.url.path == "/api/v1/app-conversations/start-tasks":
            assert request.url.params.get("ids") == "task-77"
            return httpx.Response(200, json=[{"status": "READY", "app_conversation_id": "conv-1"}])
        return httpx.Response(200, json={})

    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(99, "o/r", "برومت", "t")
    worker = CreationWorker(_client(handler), db, Bot(), "https://app.all-hands.dev")
    asyncio.run(worker._tick())
    job = db.get_creation_job(jid)
    assert job.status == "done"
    assert job.task_id == "task-77"
    assert job.conversation_id == "conv-1"
