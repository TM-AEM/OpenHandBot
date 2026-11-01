"""OHB2-09-A2-03: التحقق الرقمي الصارم لقيم التكلفة.

بيغطّي:
- الوحدة `_as_number`/`_cost_dto` مباشرةً (كل الحالات: None/0/سالبة/bool/NaN/±Inf/
  نص/كائن/قايمة/مفاتيح ناقصة).
- المسار الحقيقي: JSON upstream فيه `NaN`/`Infinity` **خام** (بايثون `json.loads`
  بيقبلهم افتراضيًا) ⇒ لازم يتصفّروا لـ None، ومفيش انهيار في `JSONResponse`
  (`allow_nan=False`)، ومفيش رقم غير محدود يوصل للواجهة.

العقد: اسم الحقل `accumulated_cost`، بلا عملة، وبلا تحويل عملة.
"""
from __future__ import annotations

import math

import httpx
import pytest
from starlette.testclient import TestClient

from bot.config import Config
from bot.openhands_client import OpenHandsClient
from bot.web import build_web_app
from bot.web.services import _as_number, _cost_dto
from tests._miniapp_helpers import BOT_TOKEN, make_init_data

OWNER = 555
OWNER_UUID = "owner-uuid-123"
CID = "c1"


# ---------------------------------------------------------------- unit: _as_number
@pytest.mark.parametrize(
    "value, expected",
    [
        (None, None),
        (0, 0),
        (0.0, 0.0),
        (2.5, 2.5),
        (7, 7),
        (-3, -3),
        (-0.5, -0.5),
        (10**30, 10**30),  # عدد صحيح ضخم: محفوظ كنوعه بلا فقد دقة
        (True, None),
        (False, None),
        (float("nan"), None),
        (float("inf"), None),
        (float("-inf"), None),
        ("1.5", None),
        ({}, None),
        ([], None),
    ],
)
def test_as_number_rejects_non_finite_and_non_numbers(value, expected):
    assert _as_number(value) == expected
    # أي قيمة مقبولة لازم تكون محدودة فعلاً.
    result = _as_number(value)
    if result is not None:
        assert math.isfinite(result)


def test_as_number_preserves_int_type_no_precision_loss():
    big = 10**30 + 1
    assert _as_number(big) == big
    assert isinstance(_as_number(big), int)  # مفيش تحويل float


# ---------------------------------------------------------------- unit: _cost_dto
def test_cost_dto_denomination_neutral_field_names():
    dto = _cost_dto({"id": CID, "metrics": {"accumulated_cost": 3.5}})
    assert set(dto.keys()) == {
        "conversation_id",
        "accumulated_cost",
        "model",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
    }
    assert "cost_usd" not in dto


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), True, "x", {}, []])
def test_cost_dto_bad_cost_is_none(bad):
    assert _cost_dto({"id": CID, "metrics": {"accumulated_cost": bad}})["accumulated_cost"] is None


def test_cost_dto_zero_and_negative_preserved():
    assert _cost_dto({"id": CID, "metrics": {"accumulated_cost": 0}})["accumulated_cost"] == 0
    assert _cost_dto({"id": CID, "metrics": {"accumulated_cost": -1.25}})["accumulated_cost"] == -1.25


def test_cost_dto_missing_metrics_all_none():
    assert _cost_dto({"id": CID}) == {
        "conversation_id": CID,
        "accumulated_cost": None,
        "model": None,
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
    }


def test_cost_dto_malformed_metrics_does_not_crash():
    dto = _cost_dto({"id": CID, "metrics": "not-a-dict"})
    assert dto["accumulated_cost"] is None


# ---------------------------------------------------------------- route-level
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


def _client(raw_conv_json: bytes) -> TestClient:
    def handler(request):
        if request.url.path == "/api/v1/app-conversations":
            return httpx.Response(200, content=raw_conv_json, headers={"content-type": "application/json"})
        if request.url.path == "/api/v1/users/me":
            return httpx.Response(200, json={"id": OWNER_UUID})
        return httpx.Response(404, json={"detail": "no"})

    client = OpenHandsClient("https://example.test", "key", transport=httpx.MockTransport(handler))
    return TestClient(build_web_app(make_config(), None, client=client), raise_server_exceptions=False)


def _login(tc: TestClient) -> None:
    assert tc.post("/api/v1/auth", json={"initData": make_init_data(OWNER)}).status_code == 200


@pytest.mark.parametrize("literal", [b"NaN", b"Infinity", b"-Infinity"])
def test_route_nan_infinity_never_reach_frontend(literal):
    """`json.loads` بيقبل NaN/Infinity الخام؛ لازم المسار يرجّع 200 وNone مش 500."""
    raw = (
        b'[{"id":"c1","created_by_user_id":"owner-uuid-123","metrics":{"accumulated_cost":'
        + literal
        + b"}}]"
    )
    tc = _client(raw)
    _login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/cost")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["accumulated_cost"] is None
    # الرد نفسه مايحتويش NaN/Infinity خام.
    low = r.text.lower()
    assert "nan" not in low and "infinity" not in low


def test_route_large_finite_int_is_preserved():
    raw = (
        b'[{"id":"c1","created_by_user_id":"owner-uuid-123","metrics":{"accumulated_cost":'
        + str(10**30).encode()
        + b"}}]"
    )
    tc = _client(raw)
    _login(tc)
    body = tc.get(f"/api/v1/conversations/{CID}/cost").json()
    assert body["accumulated_cost"] == 10**30
