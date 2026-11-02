"""اختبارات Mini App Files API (OHB2-09-02).

بتستخدم `OpenHandsClient` حقيقي فوق `httpx.MockTransport` (نفس مسار البثّ الخام)،
وما تعملش أي نداء شبكة حقيقي. بتتحقّق من: المصادقة، التفويض، رفض المالك الفاضي،
معرّفات غير صالحة، مسارات غير صالحة، الملف مش في القايمة، قايمة/معاينة ناجحة،
تعيين الحجم الكبير، فشل upstream، المهلة، ثبات الـ schema، ومفيش رجوع للقراءة
غير المحدودة.
"""
from __future__ import annotations

import json

import httpx
from starlette.testclient import TestClient

from bot.config import Config
from bot.openhands_client import OpenHandsClient
from bot.web import build_web_app
from tests._miniapp_helpers import BOT_TOKEN, make_init_data

OWNER = 555
OWNER_UUID = "owner-uuid-123"
CID = "c1"


class _Body(httpx.AsyncByteStream):
    def __init__(self, data: bytes):
        self._data = data

    async def __aiter__(self):
        yield self._data


def _json_body(obj) -> _Body:
    return _Body(json.dumps(obj).encode())


class MockAPI:
    """معالج MockTransport قابل للضبط لسيناريوهات الملفات."""

    def __init__(self):
        self.owner_uuid = OWNER_UUID
        self.conv_owner = OWNER_UUID
        self.files = ["src/main.py", "notes.txt"]
        self.contents = {"src/main.py": "print('hi')\n", "notes.txt": "مرحبا"}
        self.read_file_calls = 0
        self.list_calls = 0
        self.file_status = 200
        self.file_body_override = None  # bytes | None
        self.fail_body = False  # نقل يفشل أثناء قراءة جسم الملف

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v1/users/me":
            if self.owner_uuid is None:
                return httpx.Response(200, json={})
            return httpx.Response(200, json={"id": self.owner_uuid, "role": "owner"})
        if path == "/api/v1/app-conversations":
            if self.conv_owner is None:
                return httpx.Response(200, json=[{"id": CID}])
            return httpx.Response(200, json=[{"id": CID, "created_by_user_id": self.conv_owner}])
        if path.endswith("/files"):
            self.list_calls += 1
            return httpx.Response(200, json=list(self.files))
        if path.endswith("/file"):
            self.read_file_calls += 1
            if self.fail_body:
                raise httpx.ReadTimeout("انقطع")
            if self.file_status >= 400:
                return httpx.Response(
                    self.file_status, stream=_Body(json.dumps({"detail": "boom"}).encode())
                )
            if self.file_body_override is not None:
                return httpx.Response(200, stream=_Body(self.file_body_override))
            content = self.contents.get(request.url.params.get("file_path"), "")
            return httpx.Response(200, stream=_json_body(content))
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


def make_client(api: MockAPI) -> tuple[TestClient, OpenHandsClient]:
    client = OpenHandsClient(
        "https://example.test", "key", transport=httpx.MockTransport(api.handler)
    )
    web = build_web_app(make_config(), None, client=client)
    return TestClient(web), client


def login(tc: TestClient) -> None:
    r = tc.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    assert r.status_code == 200


# ------------------------------------------------------------------- auth
def test_files_requires_auth():
    tc, _ = make_client(MockAPI())
    r = tc.get(f"/api/v1/conversations/{CID}/files")
    assert r.status_code == 401 and r.json()["error"] == "unauthenticated"
    r2 = tc.get(f"/api/v1/conversations/{CID}/file", params={"path": "src/main.py"})
    assert r2.status_code == 401


# ----------------------------------------------------------------- listing
def test_list_files_success():
    api = MockAPI()
    tc, _ = make_client(api)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/files")
    assert r.status_code == 200
    body = r.json()
    assert body["conversation_id"] == CID
    assert body["files"] == ["src/main.py", "notes.txt"]


def test_list_files_invalid_conversation_id():
    tc, _ = make_client(MockAPI())
    login(tc)
    r = tc.get("/api/v1/conversations/bad id!/files")
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_conversation"


def test_list_files_unauthorized_other_owner():
    api = MockAPI()
    api.conv_owner = "someone-else"
    tc, _ = make_client(api)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/files")
    assert r.status_code == 403
    assert r.json()["error"] == "unauthorized"


def test_list_files_null_owner_fails_closed():
    api = MockAPI()
    api.conv_owner = None  # created_by_user_id ناقص
    tc, _ = make_client(api)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/files")
    assert r.status_code == 403 and r.json()["error"] == "unauthorized"


def test_list_files_owner_identity_unknown_fails_closed():
    api = MockAPI()
    api.owner_uuid = None  # /users/me ما رجّعش id
    tc, _ = make_client(api)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/files")
    assert r.status_code == 403 and r.json()["error"] == "unauthorized"


def test_list_files_upstream_failure():
    def handler(request):
        if request.url.path == "/api/v1/users/me":
            return httpx.Response(200, json={"id": OWNER_UUID})
        if request.url.path == "/api/v1/app-conversations":
            return httpx.Response(200, json=[{"id": CID, "created_by_user_id": OWNER_UUID}])
        if request.url.path.endswith("/files"):
            return httpx.Response(500, json={"detail": "x"})
        return httpx.Response(404, json={"detail": "no"})

    client = OpenHandsClient("https://example.test", "key", transport=httpx.MockTransport(handler))
    tc = TestClient(build_web_app(make_config(), None, client=client))
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/files")
    assert r.status_code == 502 and r.json()["error"] == "upstream_error"


# ----------------------------------------------------------------- preview
def test_preview_success():
    tc, _ = make_client(MockAPI())
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/file", params={"path": "src/main.py"})
    assert r.status_code == 200
    body = r.json()
    assert body == {
        "conversation_id": CID,
        "path": "src/main.py",
        "status": "ok",
        "text": "print('hi')\n",
        "truncated": False,
        "size_bytes": len("print('hi')\n".encode()),
    }


def test_preview_invalid_path_rejected_locally():
    api = MockAPI()
    tc, _ = make_client(api)
    login(tc)
    for bad in ["/etc/passwd", "../secret", "a/../../b", "a\\b", "a\x00b", ""]:
        r = tc.get(f"/api/v1/conversations/{CID}/file", params={"path": bad})
        assert r.status_code == 400, bad
        assert r.json()["error"] == "invalid_path", bad
    assert api.read_file_calls == 0  # مفيش قراءة لأي مسار مرفوض


def test_preview_file_not_in_listing():
    api = MockAPI()
    tc, _ = make_client(api)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/file", params={"path": "not-listed.txt"})
    assert r.status_code == 404 and r.json()["error"] == "not_found"
    assert api.read_file_calls == 0  # الملف مش في القايمة ⇒ مفيش قراءة


def test_preview_oversized_maps_to_too_large():
    api = MockAPI()
    api.file_body_override = b"x" * (300 * 1024)  # > 256 KiB
    tc, _ = make_client(api)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/file", params={"path": "src/main.py"})
    assert r.status_code == 413 and r.json()["error"] == "too_large"


def test_preview_upstream_error():
    api = MockAPI()
    api.file_status = 500
    tc, _ = make_client(api)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/file", params={"path": "src/main.py"})
    assert r.status_code == 502 and r.json()["error"] == "upstream_error"


def test_preview_timeout_maps_to_upstream_error():
    api = MockAPI()
    api.fail_body = True
    tc, _ = make_client(api)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/file", params={"path": "src/main.py"})
    assert r.status_code == 502 and r.json()["error"] == "upstream_error"


def test_preview_unauthorized_other_owner():
    api = MockAPI()
    api.conv_owner = "someone-else"
    tc, _ = make_client(api)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/file", params={"path": "src/main.py"})
    assert r.status_code == 403 and r.json()["error"] == "unauthorized"


def test_preview_binary_status_ok_envelope():
    api = MockAPI()
    api.contents["src/main.py"] = "a\x00b"
    tc, _ = make_client(api)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/file", params={"path": "src/main.py"})
    assert r.status_code == 200
    assert r.json()["status"] == "binary"
    assert r.json()["text"] == ""


# ---------------------------------------------- no unbounded read fallback
def test_preview_never_calls_unbounded_read_methods():
    api = MockAPI()
    tc, client = make_client(api)
    login(tc)
    calls = {"read_file": 0, "read_file_text": 0}

    async def _spy_read_file(*a, **kw):
        calls["read_file"] += 1
        raise AssertionError("read_file غير محدود اتنادى")

    async def _spy_read_file_text(*a, **kw):
        calls["read_file_text"] += 1
        raise AssertionError("read_file_text غير محدود اتنادى")

    client.read_file = _spy_read_file  # type: ignore[method-assign]
    client.read_file_text = _spy_read_file_text  # type: ignore[method-assign]
    r = tc.get(f"/api/v1/conversations/{CID}/file", params={"path": "src/main.py"})
    assert r.status_code == 200
    assert calls == {"read_file": 0, "read_file_text": 0}
    assert api.read_file_calls == 1  # بس المسار المحدود


def test_responses_do_not_leak_secrets():
    api = MockAPI()
    tc, _ = make_client(api)
    login(tc)
    for resp in (
        tc.get(f"/api/v1/conversations/{CID}/files"),
        tc.get(f"/api/v1/conversations/{CID}/file", params={"path": "src/main.py"}),
    ):
        assert BOT_TOKEN not in resp.text
        assert "Authorization" not in resp.text
        assert "Bearer" not in resp.text
        # مفيش مسار داخلي للسيرفر في الرد.
        assert "/home/" not in resp.text and "/workspace/" not in resp.text


def test_file_error_response_schema_is_stable():
    api = MockAPI()
    api.conv_owner = "someone-else"
    tc, _ = make_client(api)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/files")
    assert set(r.json().keys()) == {"error", "message"}
    assert isinstance(r.json()["error"], str) and isinstance(r.json()["message"], str)
