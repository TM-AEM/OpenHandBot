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


# =====================================================================
# TASK 55 (المرحلة A): get_last_exchange — آخر برومت مستخدم + آخر رد agent
# =====================================================================
import asyncio  # noqa: E402

from bot.openhands_client import (  # noqa: E402
    EXCHANGE_ACTION_LIMIT,
    EXCHANGE_MSG_LIMIT,
)


def _msg(source, text, ts=None):
    ev = {"kind": "MessageEvent", "source": source,
          "llm_message": {"content": [{"type": "text", "text": text}]}}
    if ts is not None:
        ev["timestamp"] = ts
    return ev


def _finish(text, ts=None):
    ev = {"kind": "ActionEvent", "action": {"kind": "FinishAction", "message": text}}
    if ts is not None:
        ev["timestamp"] = ts
    return ev


def _exchange_client(msg_items, action_items, recorder=None):
    def handler(request):
        kind = request.url.params.get("kind__eq")
        if recorder is not None:
            recorder.append((kind, request.url.params.get("limit"),
                             request.url.params.get("sort_order")))
        items = msg_items if kind == "MessageEvent" else action_items
        return httpx.Response(200, json={"items": items})

    return make_client(handler)


def test_exchange_returns_user_prompt_and_agent_reply():
    client = _exchange_client(
        [_msg("user", "برومتي"), _msg("agent", "ردي")],
        [],
    )
    assert asyncio.run(client.get_last_exchange("c")) == ("برومتي", "ردي")


def test_exchange_finish_newer_than_agent_message():
    client = _exchange_client(
        [_msg("user", "ب", "2026-01-01T00:00:00Z"), _msg("agent", "رد قديم", "2026-01-01T00:00:10Z")],
        [_finish("التقرير النهائي", "2026-01-01T00:00:20Z")],
    )
    assert asyncio.run(client.get_last_exchange("c")) == ("ب", "التقرير النهائي")


def test_exchange_agent_message_newer_than_finish():
    client = _exchange_client(
        [_msg("user", "ب", "2026-01-01T00:00:00Z"), _msg("agent", "رد أحدث", "2026-01-01T00:00:30Z")],
        [_finish("تقرير أقدم", "2026-01-01T00:00:20Z")],
    )
    assert asyncio.run(client.get_last_exchange("c")) == ("ب", "رد أحدث")


def test_exchange_no_user_messages():
    client = _exchange_client([_msg("agent", "ردي")], [])
    user_text, reply = asyncio.run(client.get_last_exchange("c"))
    assert user_text is None and reply == "ردي"


def test_exchange_no_reply_at_all():
    client = _exchange_client([_msg("user", "برومتي")], [])
    assert asyncio.run(client.get_last_exchange("c")) == ("برومتي", None)


def test_exchange_missing_timestamps_prefer_finish_without_raising():
    # لا طوابع على أي حدث: الأفضلية لتقرير FinishAction، ومايرميش استثناء.
    client = _exchange_client([_msg("user", "ب"), _msg("agent", "رد")], [_finish("تقرير")])
    assert asyncio.run(client.get_last_exchange("c")) == ("ب", "تقرير")


def test_exchange_unparseable_timestamp_prefers_finish():
    client = _exchange_client(
        [_msg("user", "ب", "not-a-date"), _msg("agent", "رد", "also-bad")],
        [_finish("تقرير", "still-bad")],
    )
    assert asyncio.run(client.get_last_exchange("c")) == ("ب", "تقرير")


def test_exchange_blank_text_is_skipped():
    client = _exchange_client(
        [_msg("user", "   "), _msg("user", "برومت حقيقي"), _msg("agent", "  "), _msg("agent", "رد حقيقي")],
        [],
    )
    assert asyncio.run(client.get_last_exchange("c")) == ("برومت حقيقي", "رد حقيقي")


def test_exchange_request_shape():
    recorder = []
    client = _exchange_client([_msg("user", "ب")], [], recorder=recorder)
    asyncio.run(client.get_last_exchange("c"))
    assert ("MessageEvent", str(EXCHANGE_MSG_LIMIT), "TIMESTAMP_DESC") in recorder
    assert ("ActionEvent", str(EXCHANGE_ACTION_LIMIT), "TIMESTAMP_DESC") in recorder


def test_exchange_api_error_propagates():
    def handler(request):
        return httpx.Response(500, json={"detail": "boom"})

    client = make_client(handler)
    with pytest.raises(ApiError):
        asyncio.run(client.get_last_exchange("c"))


def test_exchange_finish_action_uses_shared_parser():
    # ActionEvent بلا FinishAction (زي CmdRunAction) مايتحسبش رد.
    client = _exchange_client(
        [_msg("user", "ب")],
        [{"kind": "ActionEvent", "action": {"kind": "CmdRunAction", "command": "ls"}}],
    )
    assert asyncio.run(client.get_last_exchange("c")) == ("ب", None)



# =====================================================================
# OHB2-01: التحقق من شكل ردود OpenHands — رد غير متوقع ⇒ ApiError آمن
# =====================================================================
import asyncio as _asyncio  # noqa: E402


def _client_returning(payload):
    def handler(request):
        return httpx.Response(200, json=payload)

    return make_client(handler)


def test_search_conversations_non_list_items_raises():
    # items نوعها غلط (str) ⇒ خطأ آمن، مش نتيجة فاضية مضلّلة.
    client = _client_returning({"items": "nope"})
    with pytest.raises(ApiError):
        _asyncio.run(client.search_conversations())


def test_search_conversations_wrong_top_level_type_raises():
    client = _client_returning(42)
    with pytest.raises(ApiError):
        _asyncio.run(client.search_conversations())


def test_search_events_wrong_top_level_type_raises():
    client = _client_returning("not-a-list")
    with pytest.raises(ApiError):
        _asyncio.run(client.search_events("c1"))


def test_search_events_non_dict_members_are_dropped():
    client = _client_returning([{"kind": "MessageEvent"}, None, "x", 5])
    assert _asyncio.run(client.search_events("c1")) == [{"kind": "MessageEvent"}]


def test_list_files_wrong_top_level_type_raises():
    client = _client_returning({"nope": 1})
    with pytest.raises(ApiError):
        _asyncio.run(client.list_files("c1"))


def test_search_repositories_wrong_top_level_type_raises():
    client = _client_returning("bad")
    with pytest.raises(ApiError):
        _asyncio.run(client.search_repositories())


def test_get_start_task_wrong_top_level_type_raises():
    client = _client_returning(True)
    with pytest.raises(ApiError):
        _asyncio.run(client.get_start_task("t1"))


def test_malformed_json_body_raises_safe_api_error():
    def handler(request):
        return httpx.Response(200, content=b"<html>proxy error</html>")

    client = make_client(handler)
    with pytest.raises(ApiError):
        _asyncio.run(client.search_conversations())


def test_get_conversations_null_entries_preserved_as_dropped():
    # الموثّق: مصفوفة فيها null — بنسقطها وبنحتفظ بالـ dict بس.
    client = _client_returning([{"id": "a"}, None, "x"])
    assert _asyncio.run(client.get_conversations(["a"])) == [{"id": "a"}]
