"""TASK 04B-08: اختبارات المسارات السلبية لسلوك الملفات/التصدير (بدون حدّ حجم مصطنع).

بنغطّي: قيم قايمة ملفات غريبة، فهارس ملفات غير صالحة، محتوى فاضي، فشل التصدير،
وقيم إرجاع غير متوقعة — مع رسائل خطأ آمنة من غير تسريب أسرار أو أجسام خام.
"""
import asyncio

import httpx
import pytest

import bot.handlers as h
from bot.errors import ApiError
from bot.file_cache import FileCache
from bot.openhands_client import OpenHandsClient
from tests.test_handlers import DetailClient, _cb_update, _ctx_with

# ------------------------------------------------------------------ client layer


def make_client(handler):
    return OpenHandsClient("https://example.test", "key", transport=httpx.MockTransport(handler))


def test_list_files_malformed_top_level_returns_empty():
    # جسم مش list ومش dict فيه items ⇒ قايمة فاضية بأمان (مش انهيار).
    def handler(request):
        return httpx.Response(200, json={"unexpected": True})

    assert asyncio.run(make_client(handler).list_files("c1")) == []


def test_list_files_non_string_entries_are_dropped():
    def handler(request):
        return httpx.Response(200, json=["ok.py", None, 5, {"x": 1}, ["nested"]])

    assert asyncio.run(make_client(handler).list_files("c1")) == ["ok.py"]


def test_list_files_non_json_body_raises_safe_apierror():
    def handler(request):
        return httpx.Response(200, content=b"<html>not json</html>")

    with pytest.raises(ApiError) as exc:
        asyncio.run(make_client(handler).list_files("c1"))
    assert "html" not in str(exc.value).lower()  # مفيش جسم خام
    assert "OpenHands" in str(exc.value)


def test_read_file_malformed_returns_empty_string():
    # الباراميتر file_path بيرجّع نص خام؛ أي حاجة تانية ⇒ "" بأمان.
    def handler(request):
        return httpx.Response(200, json={"not": "a string"})

    assert asyncio.run(make_client(handler).read_file("c1", "main.py")) == ""


def test_export_failure_raises_safe_error_no_body_leak():
    def handler(request):
        return httpx.Response(500, content=b"internal stack trace secret")

    with pytest.raises(ApiError) as exc:
        asyncio.run(make_client(handler).export_conversation("c1"))
    assert exc.value.status_code == 500
    assert "stack trace" not in str(exc.value)
    assert "secret" not in str(exc.value)


def test_export_large_response_is_returned_intact():
    # بنثبت إن الاستجابة الكبيرة بتتسلم كاملة (مفيش قص صامت)، ونوثّق إن مفيش حدّ حجم لسه.
    big = b"PK\x03\x04" + b"x" * (2 * 1024 * 1024)

    def handler(request):
        return httpx.Response(200, content=big)

    assert asyncio.run(make_client(handler).export_conversation("c1")) == big


# ----------------------------------------------------------------- handler layer


class FailingFileClient(DetailClient):
    def __init__(self, conv, files_error=None, read_error=None, export_error=None):
        super().__init__(conv)
        self._files_error = files_error
        self._read_error = read_error
        self._export_error = export_error

    async def list_files(self, conversation_id, path=""):
        if self._files_error:
            raise self._files_error
        return await super().list_files(conversation_id, path)

    async def read_file(self, conversation_id, file_path):
        if self._read_error:
            raise self._read_error
        return await super().read_file(conversation_id, file_path)

    async def export_conversation(self, conversation_id):
        if self._export_error:
            raise self._export_error
        return await super().export_conversation(conversation_id)


def test_list_files_empty_shows_message(tmp_path):
    ctx = _ctx_with(tmp_path, DetailClient({"id": "c1"}, files=[]))
    update = _cb_update(1, "files:c1:0")
    asyncio.run(h.list_files(update, ctx))
    assert "ما فيهاش ملفات" in update.callback_query.edits[-1]


def test_list_files_api_error_shows_safe_message(tmp_path):
    client = FailingFileClient({"id": "c1"}, files_error=ApiError("مفتاح غلط", 401))
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "files:c1:0")
    asyncio.run(h.list_files(update, ctx))
    assert "مفتاح" in update.callback_query.edits[-1]


def test_show_file_invalid_index_is_safe(tmp_path):
    ctx = _ctx_with(tmp_path, DetailClient({"id": "c1"}, files=["a.py"]))
    cache = FileCache(); gen = cache.put("c1", ["a.py"]); ctx.bot_data["file_cache"] = cache
    update = _cb_update(1, f"file:c1:{gen}:5")  # فهرس برّه الحدود
    asyncio.run(h.show_file(update, ctx))
    assert ctx.bot.documents == []
    assert "مش موجود" in update.callback_query.edits[-1]


def test_show_file_without_cache_entry_is_safe(tmp_path):
    ctx = _ctx_with(tmp_path, DetailClient({"id": "c1"}))
    update = _cb_update(1, "file:c1:1:0")  # مفيش cache خالص
    asyncio.run(h.show_file(update, ctx))
    assert ctx.bot.documents == []
    assert "مش موجود" in update.callback_query.edits[-1]


def test_show_file_empty_content_still_sends_document(tmp_path):
    ctx = _ctx_with(tmp_path, DetailClient({"id": "c1"}, content=""))
    cache = FileCache(); gen = cache.put("c1", ["a.py"]); ctx.bot_data["file_cache"] = cache
    update = _cb_update(1, f"file:c1:{gen}:0")
    asyncio.run(h.show_file(update, ctx))
    assert len(ctx.bot.documents) == 1  # ملف فاضي لسه بيتبعت


def test_show_file_api_error_is_safe(tmp_path):
    client = FailingFileClient({"id": "c1"}, read_error=ApiError("مش موجود", 404))
    ctx = _ctx_with(tmp_path, client)
    cache = FileCache(); gen = cache.put("c1", ["a.py"]); ctx.bot_data["file_cache"] = cache
    update = _cb_update(1, f"file:c1:{gen}:0")
    asyncio.run(h.show_file(update, ctx))
    assert ctx.bot.documents == []
    assert update.callback_query.edits  # رسالة خطأ ظهرت


def test_export_api_error_is_safe_no_document(tmp_path):
    client = FailingFileClient({"id": "c1"}, export_error=ApiError("خدمة مش متاحة", 503))
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "export:c1")
    asyncio.run(h.export_conversation(update, ctx))
    assert ctx.bot.documents == []
    assert update.callback_query.edits
