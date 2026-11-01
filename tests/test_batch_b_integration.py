"""OHB2-09-BATCH-B — اختبارات دمج/تكافؤ عبر الطبقات (بوت ↔ Mini App ↔ الواجهة).

بتغطّي الفجوة اللي ماكانتش متغطّاة: التكافؤ بين مسار البوت ومسار الـ Mini App على
**نفس** الحالات، وتطابق رموز الخطأ اللي السيرفر بيرجّعها مع مفاتيح الواجهة في
`files.js` (عشان أي حالة جديدة تتكسر عندنا لو الواجهة مش عارفاها).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import httpx
from starlette.testclient import TestClient

from bot.config import Config
from bot.errors import ApiError
from bot.files import FileStatus, file_status_message
from bot.openhands_client import OpenHandsClient
from bot.web import build_web_app
from tests._miniapp_helpers import BOT_TOKEN, make_init_data

OWNER = 555
OWNER_UUID = "owner-uuid-123"
CID = "c1"
STATIC = Path(__file__).resolve().parent.parent / "bot" / "web" / "static"


class _Body(httpx.AsyncByteStream):
    def __init__(self, data: bytes):
        self._data = data

    async def __aiter__(self):
        yield self._data


class MockAPI:
    def __init__(self, *, owner_uuid=OWNER_UUID, conv_owner=OWNER_UUID):
        self.owner_uuid = owner_uuid
        self.conv_owner = conv_owner
        self.files = ["src/main.py"]

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v1/users/me":
            if self.owner_uuid is None:
                return httpx.Response(200, json={})
            return httpx.Response(200, json={"id": self.owner_uuid})
        if path == "/api/v1/app-conversations":
            if self.conv_owner is None:
                return httpx.Response(200, json=[{"id": CID}])
            return httpx.Response(200, json=[{"id": CID, "created_by_user_id": self.conv_owner}])
        if path.endswith("/files"):
            return httpx.Response(200, json=list(self.files))
        if path.endswith("/file"):
            return httpx.Response(200, stream=_Body(json.dumps("print('hi')\n").encode()))
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


def make_client(api: MockAPI) -> TestClient:
    client = OpenHandsClient("https://example.test", "key", transport=httpx.MockTransport(api.handler))
    web = build_web_app(make_config(), None, client=client)
    tc = TestClient(web)
    assert tc.post("/api/v1/auth", json={"initData": make_init_data(OWNER)}).status_code == 200
    return tc


# ------------------------------------------------------------------ static keys
def _js_keys(var_name: str) -> set[str]:
    src = (STATIC / "files.js").read_text(encoding="utf-8")
    m = re.search(rf"var {var_name} = \{{(.*?)\}};", src, re.S)
    assert m, f"{var_name} مش موجود في files.js"
    return set(re.findall(r"([A-Za-z_][\w]*)\s*:", m.group(1)))


def test_backend_error_codes_are_all_known_to_frontend():
    # كل رمز خطأ ممكن يرجّعه السيرفر لازم يكون معرّف في الواجهة (files.js).
    labels = _js_keys("ERROR_LABELS")
    backend_codes = {
        "unauthenticated",
        "forbidden",
        "bad_origin",
        "rate_limited",
        "invalid_conversation",
        "invalid_path",
        "not_found",
        "unauthorized",
        "too_large",
        "upstream_error",
        "api_error",
    }
    missing = backend_codes - labels
    assert not missing, f"رموز خطأ في السيرفر مش في الواجهة: {missing}"


def test_frontend_preview_status_values_match_backend_enum():
    content = _js_keys("CONTENT_STATUS")
    # قيم الحالة اللي السيرفر بيرجّعها في مسار المعاينة الناجح.
    assert content == {"ok", "binary", "not_utf8", "too_large"}


# ------------------------------------------------------------------ cross-layer flows
def test_list_then_preview_full_flow_matches_contract():
    tc = make_client(MockAPI())
    listing = tc.get(f"/api/v1/conversations/{CID}/files")
    assert listing.status_code == 200 and listing.json()["files"] == ["src/main.py"]
    preview = tc.get(f"/api/v1/conversations/{CID}/file", params={"path": "src/main.py"})
    assert preview.status_code == 200
    body = preview.json()
    assert body["status"] == "ok" and body["text"] == "print('hi')\n"


def test_other_owner_file_preview_is_403_unauthorized():
    tc = make_client(MockAPI(conv_owner="someone-else"))
    r = tc.get(f"/api/v1/conversations/{CID}/file", params={"path": "src/main.py"})
    assert r.status_code == 403 and r.json()["error"] == "unauthorized"


def test_null_owner_fails_closed_403():
    tc = make_client(MockAPI(conv_owner=None))
    r = tc.get(f"/api/v1/conversations/{CID}/files")
    assert r.status_code == 403 and r.json()["error"] == "unauthorized"


def test_invalid_conversation_id_400():
    tc = make_client(MockAPI())
    r = tc.get("/api/v1/conversations/bad%20id!/files")
    assert r.status_code == 400 and r.json()["error"] == "invalid_conversation"


# ------------------------------------------------------------------ message parity
def test_bot_and_miniapp_share_file_status_messages():
    """نفس الحالة ⇒ نفس الرسالة العربية في البوت والـ Mini App (مصدر واحد)."""
    from bot.web.services import MiniAppService

    for status in (
        FileStatus.UNAUTHORIZED,
        FileStatus.NOT_FOUND,
        FileStatus.INVALID_PATH,
        FileStatus.TOO_LARGE,
        FileStatus.BINARY,
        FileStatus.NOT_UTF8,
    ):
        web_err = MiniAppService._file_error(status, None)
        assert str(web_err) == file_status_message(status, None), status


def test_upstream_error_prefers_redacted_detail_both_layers():
    """فشل upstream: الطبقتين بيعرضوا رسالة ApiError المتنقّحة (مش تفاصيل خام)."""
    from bot.web.services import MiniAppService

    exc = ApiError("تعذّر الاتصال بخدمة الملفات", 503)
    from bot.errors import error_text

    web_err = MiniAppService._file_error(FileStatus.UPSTREAM_ERROR, error_text(exc))
    assert str(web_err) == error_text(exc)
    assert str(web_err) == file_status_message(FileStatus.UPSTREAM_ERROR, error_text(exc))
