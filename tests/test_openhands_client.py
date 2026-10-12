import httpx
import pytest

from bot.errors import ApiError
from bot.openhands_client import OpenHandsClient


def make_client(handler):
    transport = httpx.MockTransport(handler)
    return OpenHandsClient("https://example.test", "key", transport=transport)


def test_search_conversations_sorts_desc_and_drops_nulls():
    def handler(request):
        assert request.url.path == "/api/v1/app-conversations/search"
        assert request.url.params["limit"] == "20"
        return httpx.Response(
            200,
            json={
                "items": [
                    {"id": "a", "updated_at": "2026-01-01T00:00:00Z"},
                    None,
                    {"id": "b", "updated_at": "2026-03-01T00:00:00Z"},
                ],
                "next_page_id": "p2",
            },
        )

    import asyncio

    client = make_client(handler)
    result = asyncio.run(client.search_conversations())
    assert [it["id"] for it in result["items"]] == ["b", "a"]
    assert result["next_page_id"] == "p2"


def test_get_conversations_uses_repeated_ids():
    seen = {}

    def handler(request):
        seen["params"] = request.url.params.get_list("ids")
        return httpx.Response(200, json=[{"id": "a"}, None])

    import asyncio

    client = make_client(handler)
    out = asyncio.run(client.get_conversations(["a", "b"]))
    assert seen["params"] == ["a", "b"]
    assert out == [{"id": "a"}]


def test_pagination_uses_page_id_param():
    seen = {}

    def handler(request):
        seen["page_id"] = request.url.params.get("page_id")
        return httpx.Response(200, json={"items": [], "next_page_id": None})

    import asyncio

    client = make_client(handler)
    asyncio.run(client.search_conversations(page_id="cursor-1"))
    assert seen["page_id"] == "cursor-1"


def test_get_last_reply_prefers_agent_message():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "items": [
                    {"kind": "ConversationStateUpdateEvent", "source": "environment"},
                    {
                        "kind": "MessageEvent",
                        "source": "agent",
                        "llm_message": {"content": [{"type": "text", "text": "التقرير النهائي"}]},
                    },
                ]
            },
        )

    import asyncio

    client = make_client(handler)
    assert asyncio.run(client.get_last_reply("c")) == "التقرير النهائي"


def test_get_last_reply_uses_finish_action():
    def handler(request):
        return httpx.Response(
            200,
            json={"items": [{"kind": "ActionEvent", "action": {"kind": "FinishAction", "message": "خلصت"}}]},
        )

    import asyncio

    client = make_client(handler)
    assert asyncio.run(client.get_last_reply("c")) == "خلصت"


def test_send_message_409_raises_arabic_error():
    def handler(request):
        return httpx.Response(409, json={"detail": "Sandbox is PAUSED."})

    import asyncio

    client = make_client(handler)
    with pytest.raises(ApiError) as exc:
        asyncio.run(client.send_message("c", "hi"))
    assert exc.value.status_code == 409
    assert "واقف" in str(exc.value)


def test_wait_for_start_returns_app_conversation_id():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(200, json=[{"status": "STARTING"}])
        return httpx.Response(200, json=[{"status": "READY", "app_conversation_id": "conv-1"}])

    import asyncio

    client = make_client(handler)
    out = asyncio.run(client.wait_for_start("task", timeout=5, interval=0))
    assert out == "conv-1"


def test_wait_for_start_error_status_is_ambiguous():
    # "ERROR" هو القيمة الموثّقة الوحيدة للفشل. لازم تبقى غامضة (ApiError بلا
    # status_code) عشان الـ caller يصنّفها 'unknown' مش 'failed' ⇒ مفيش إعادة POST.
    def handler(request):
        return httpx.Response(200, json=[{"status": "ERROR", "detail": "boom"}])

    import asyncio

    client = make_client(handler)
    with pytest.raises(ApiError) as exc:
        asyncio.run(client.wait_for_start("task", timeout=5, interval=0))
    assert exc.value.status_code is None


def test_wait_for_start_failed_is_not_a_documented_enum_value():
    # "FAILED" مش في enum الـ API ⇒ لازم يتجاهلها (يستمر في الاستطلاع) لحد ما يوصل
    # READY، مش يعتبرها فشل. ده بيثبّت إزالة الفرع الميت.
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(200, json=[{"status": "FAILED"}])
        return httpx.Response(200, json=[{"status": "READY", "app_conversation_id": "conv-9"}])

    import asyncio

    client = make_client(handler)
    out = asyncio.run(client.wait_for_start("task", timeout=5, interval=0))
    assert out == "conv-9"


def test_wait_for_start_timeout_is_ambiguous():
    def handler(request):
        return httpx.Response(200, json=[{"status": "WAITING_FOR_SANDBOX"}])

    import asyncio

    client = make_client(handler)
    with pytest.raises(ApiError) as exc:
        asyncio.run(client.wait_for_start("task", timeout=0.05, interval=0.01))
    assert exc.value.status_code is None  # مهلة ⇒ غامض ⇒ unknown


def test_list_files():
    def handler(request):
        assert request.url.path == "/api/v1/app-conversations/c1/files"
        return httpx.Response(200, json=["a.py", "b/c.py", 5])

    import asyncio

    client = make_client(handler)
    assert asyncio.run(client.list_files("c1")) == ["a.py", "b/c.py"]


def test_read_file_uses_file_path_param():
    seen = {}

    def handler(request):
        seen["file_path"] = request.url.params.get("file_path")
        return httpx.Response(200, json="print('hi')\n")

    import asyncio

    client = make_client(handler)
    assert asyncio.run(client.read_file("c1", "main.py")) == "print('hi')\n"
    assert seen["file_path"] == "main.py"


def test_export_conversation_returns_bytes():
    def handler(request):
        assert request.url.path == "/api/v1/app-conversations/c1/download"
        return httpx.Response(200, content=b"PK\x03\x04zip")

    import asyncio

    client = make_client(handler)
    assert asyncio.run(client.export_conversation("c1")) == b"PK\x03\x04zip"


def test_search_repositories():
    def handler(request):
        assert request.url.params["provider"] == "github"
        assert request.url.params["query"] == "bot"
        return httpx.Response(200, json={"items": [{"full_name": "x/y"}, None]})

    import asyncio

    client = make_client(handler)
    assert asyncio.run(client.search_repositories(query="bot")) == [{"full_name": "x/y"}]
