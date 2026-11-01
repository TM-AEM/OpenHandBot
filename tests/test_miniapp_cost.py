"""اختبارات Mini App Cost & Usage API (OHB2-09-04).

بتستخدم `OpenHandsClient` حقيقي فوق `httpx.MockTransport`. بتتحقّق من تحويل بيانات
`metrics` غير الموثوقة لملخّص منظّم (أرقام/None)، ومن المصادقة والثبات وعدم التسريب.
"""
from __future__ import annotations

import httpx
from starlette.testclient import TestClient

from bot.config import Config
from bot.openhands_client import OpenHandsClient
from bot.web import build_web_app
from tests._miniapp_helpers import BOT_TOKEN, make_init_data

OWNER = 555
CID = "c1"
# OHB2-09-A2-02: مسار الشات بقى بيتحقّق من الملكية ⇒ لازم هوية `/users/me` تطابق
# `created_by_user_id` بتاع الشات.
OWNER_UUID = "owner-uuid-123"


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


def client_for(conv: dict) -> TestClient:
    conv = {"created_by_user_id": OWNER_UUID, **conv}

    def handler(request):
        if request.url.path == "/api/v1/app-conversations":
            return httpx.Response(200, json=[conv])
        if request.url.path == "/api/v1/users/me":
            return httpx.Response(200, json={"id": OWNER_UUID})
        return httpx.Response(404, json={"detail": "no"})

    client = OpenHandsClient("https://example.test", "key", transport=httpx.MockTransport(handler))
    return TestClient(build_web_app(make_config(), None, client=client))


def login(tc: TestClient) -> None:
    r = tc.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    assert r.status_code == 200


def test_cost_requires_auth():
    tc = client_for({"id": CID})
    r = tc.get(f"/api/v1/conversations/{CID}/cost")
    assert r.status_code == 401 and r.json()["error"] == "unauthenticated"


def test_cost_success_full_metrics():
    tc = client_for({
        "id": CID,
        "metrics": {
            "accumulated_cost": 1.2345,
            "model_name": "gpt-4o",
            "accumulated_token_usage": {
                "prompt_tokens": 100,
                "completion_tokens": 40,
                "total_tokens": 140,
            },
        },
    })
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/cost")
    assert r.status_code == 200
    assert r.json() == {
        "conversation_id": CID,
        "accumulated_cost": 1.2345,
        "model": "gpt-4o",
        "prompt_tokens": 100,
        "completion_tokens": 40,
        "total_tokens": 140,
    }


def test_cost_missing_metrics_all_none():
    tc = client_for({"id": CID})
    login(tc)
    body = tc.get(f"/api/v1/conversations/{CID}/cost").json()
    assert body == {
        "conversation_id": CID,
        "accumulated_cost": None,
        "model": None,
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
    }


def test_cost_weird_metric_types_are_nulled_not_crashed():
    tc = client_for({
        "id": CID,
        "metrics": {
            "accumulated_cost": "abc",  # مش رقم
            "model_name": 123,  # مش نص
            "accumulated_token_usage": "not-a-dict",
        },
    })
    login(tc)
    body = tc.get(f"/api/v1/conversations/{CID}/cost").json()
    assert body["accumulated_cost"] is None
    assert body["model"] is None
    assert body["prompt_tokens"] is None


def test_cost_bool_is_not_a_number():
    tc = client_for({"id": CID, "metrics": {"accumulated_cost": True}})
    login(tc)
    assert tc.get(f"/api/v1/conversations/{CID}/cost").json()["accumulated_cost"] is None


def test_cost_model_from_usage_fallback_and_truncated():
    tc = client_for({
        "id": CID,
        "metrics": {"accumulated_token_usage": {"model": "m" * 500}},
    })
    login(tc)
    model = tc.get(f"/api/v1/conversations/{CID}/cost").json()["model"]
    assert model == "m" * 200  # مقصوص لطول آمن


def test_cost_unknown_conversation_404():
    def handler(request):
        return httpx.Response(200, json=[])  # مفيش شات

    client = OpenHandsClient("https://example.test", "key", transport=httpx.MockTransport(handler))
    tc = TestClient(build_web_app(make_config(), None, client=client))
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/cost")
    assert r.status_code == 404


def test_cost_invalid_conversation_id_400():
    tc = client_for({"id": CID})
    login(tc)
    r = tc.get("/api/v1/conversations/bad id/cost")
    assert r.status_code == 400 and r.json()["error"] == "bad_request"


def test_cost_response_schema_is_stable_and_no_secret_leak():
    tc = client_for({"id": CID, "metrics": {"accumulated_cost": 0.5}})
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/cost")
    assert set(r.json().keys()) == {
        "conversation_id", "accumulated_cost", "model",
        "prompt_tokens", "completion_tokens", "total_tokens",
    }
    assert BOT_TOKEN not in r.text and "Bearer" not in r.text


# ============================== OHB2-09-04-R1: no fabricated currency denomination
def test_cost_response_has_no_currency_symbol_or_usd():
    """العقد مايثبّتش عملة ⇒ الرد مايحتويش أي رمز عملة ولا اسم عملة."""
    tc = client_for({"id": CID, "metrics": {"accumulated_cost": 3.5}})
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/cost")
    assert r.status_code == 200
    body = r.json()
    # اسم الحقل مطابق للعقد (accumulated_cost) — مش cost_usd.
    assert "accumulated_cost" in body
    assert "cost_usd" not in body
    low = r.text.lower()
    assert "usd" not in low and "$" not in r.text and "usd" not in low
    assert "dollar" not in low
