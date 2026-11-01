"""OHB2-09-A2-05: بوابة أمان مدمجة عبر نقاط النهاية + طبقة الخدمة.

بتضيف على مصفوفة A2-02 إثبات إن **طبقة الخدمة نفسها** بتفرض التفويض (مش الـ route
بس)، وإن مفيش مسار بياخد بيانات محمية قبل التفويض، وإن التخطيط منظّم وثابت.

كمان بتغطّي البوابة المدمجة: كل الدوال المحمية بترفض المالك الغلط/الفاضي بنفس الرمز.
"""
from __future__ import annotations

import asyncio

import httpx
from starlette.testclient import TestClient

from bot.config import Config
from bot.openhands_client import OpenHandsClient
from bot.web import build_web_app
from bot.web.services import MiniAppService
from tests._miniapp_helpers import BOT_TOKEN, make_init_data

OWNER = 555
OWNER_UUID = "owner-uuid-123"
CID = "c1"


class _Body(httpx.AsyncByteStream):
    def __init__(self, data: bytes):
        self._data = data

    async def __aiter__(self):
        yield self._data


class MockAPI:
    def __init__(self, *, conv_owner=OWNER_UUID, owner_uuid=OWNER_UUID, convs_present=True):
        self.owner_uuid = owner_uuid
        self.conv_owner = conv_owner
        self.convs_present = convs_present
        self.events_calls = 0
        self.files_calls = 0
        self.file_calls = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v1/users/me":
            return httpx.Response(200, json={"id": self.owner_uuid} if self.owner_uuid else {})
        if path == "/api/v1/app-conversations":
            if not self.convs_present:
                return httpx.Response(200, json=[])
            conv = {"id": CID, "title": "شات", "execution_status": "running",
                    "metrics": {"accumulated_cost": 1.0}}
            if self.conv_owner is not None:
                conv["created_by_user_id"] = self.conv_owner
            return httpx.Response(200, json=[conv])
        if path.endswith("/events/search"):
            self.events_calls += 1
            return httpx.Response(200, json={"items": []})
        if path.endswith("/files"):
            self.files_calls += 1
            return httpx.Response(200, json=["a.py"])
        if path.endswith("/file"):
            self.file_calls += 1
            return httpx.Response(200, stream=_Body(b'"x"'))
        return httpx.Response(404, json={"detail": "no"})


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


def _client(api: MockAPI):
    return OpenHandsClient("https://example.test", "key", transport=httpx.MockTransport(api.handler))


# ---------------------------------------------------- service-layer enforcement
def _service(api: MockAPI) -> MiniAppService:
    return MiniAppService(make_config(), None, client=_client(api))


def test_service_get_conversation_rejects_wrong_owner_before_exchange():
    api = MockAPI(conv_owner="someone-else")
    svc = _service(api)
    try:
        asyncio.run(svc.get_conversation(CID))
        assert False, "المفروض يرفض"
    except Exception as exc:  # CodedApiError
        assert getattr(exc, "code", None) == "unauthorized"
    assert api.events_calls == 0  # مفيش جلب آخر تبادل قبل التفويض


def test_service_get_cost_rejects_null_owner():
    api = MockAPI(conv_owner=None)
    svc = _service(api)
    try:
        asyncio.run(svc.get_cost(CID))
        assert False, "المفروض يرفض"
    except Exception as exc:
        assert getattr(exc, "code", None) == "unauthorized"


def test_service_list_files_rejects_wrong_owner_before_listing():
    api = MockAPI(conv_owner="someone-else")
    svc = _service(api)
    try:
        asyncio.run(svc.list_files(CID))
        assert False, "المفروض يرفض"
    except Exception as exc:
        assert getattr(exc, "code", None) == "unauthorized"
    assert api.files_calls == 0  # مفيش جلب قايمة قبل التفويض


def test_service_watch_rejects_wrong_owner(tmp_path):
    import bot.features as features
    from bot.db import Database

    original = features.DEFERRED_FEATURES_HIDDEN
    features.DEFERRED_FEATURES_HIDDEN = False
    try:
        api = MockAPI(conv_owner="someone-else")
        db = Database(str(tmp_path / "g.sqlite3"))
        svc = MiniAppService(make_config(), db, client=_client(api))
        try:
            asyncio.run(svc.watch(CID))
            assert False, "المفروض يرفض"
        except Exception as exc:
            assert getattr(exc, "code", None) == "unauthorized"
    finally:
        features.DEFERRED_FEATURES_HIDDEN = original


# ---------------------------------------------------- stable error mapping
def test_error_mapping_is_stable_across_routes():
    api = MockAPI(conv_owner="someone-else")
    tc = TestClient(build_web_app(make_config(), None, client=_client(api)), raise_server_exceptions=False)
    assert tc.post("/api/v1/auth", json={"initData": make_init_data(OWNER)}).status_code == 200
    for path, params in [
        (f"/api/v1/conversations/{CID}", {}),
        (f"/api/v1/conversations/{CID}/status", {}),
        (f"/api/v1/conversations/{CID}/cost", {}),
        (f"/api/v1/conversations/{CID}/files", {}),
        (f"/api/v1/conversations/{CID}/file", {"path": "a.py"}),
    ]:
        r = tc.get(path, params=params)
        assert r.status_code == 403, (path, r.status_code)
        assert r.json() == {"error": "unauthorized", "message": r.json()["message"]}
        assert r.json()["error"] == "unauthorized"


def test_no_route_leaks_upstream_detail_on_authz_failure():
    api = MockAPI(conv_owner="someone-else")
    tc = TestClient(build_web_app(make_config(), None, client=_client(api)), raise_server_exceptions=False)
    tc.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    r = tc.get(f"/api/v1/conversations/{CID}/cost")
    assert "Bearer" not in r.text and BOT_TOKEN not in r.text
