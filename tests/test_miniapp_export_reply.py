"""OHB2-PHASE1B: اختبارات تصدير الشات + الرد الكامل في الـ Mini App.

بتستخدم `OpenHandsClient` حقيقي فوق `httpx.MockTransport` (نفس مسار البثّ الخام)،
وما تعملش أي نداء شبكة/تيليجرام/OpenHands حقيقي. بتتحقّق من:

- المصادقة (401 لغير المسجّل) ومنع تجاوز هوية الجلسة بمعرّف من العميل.
- ملكية الشات server-side (403 لمالك تاني/مالك ناقص).
- التصدير الناجح: نوع المحتوى، اسم التنزيل الآمن، وحماية هيدر الحقن.
- حدود الحجم (413) وعدم إنتاج تصدير «ناجح» كاذب عند فشل التنزيل.
- شاهد الحذف المحلي: مفيش تصدير/إحياء لشات محذوف.
- الرد الكامل: النص الكامل (مش مقصوص)، ورفض غير المصرّح.
"""
from __future__ import annotations

import sqlite3

import httpx
from starlette.testclient import TestClient

from bot.config import Config
from bot.openhands_client import MAX_EXPORT_BYTES, OpenHandsClient
from bot.db import Database
from bot.web import build_web_app
from bot.web.services import MAX_FULL_REPLY_CHARS, export_filename
from tests._miniapp_helpers import BOT_TOKEN, make_init_data

OWNER = 555
OTHER = 999
OWNER_UUID = "owner-uuid-123"
CID = "c1"
ZIP = b"PK\x03\x04fake-zip-bytes"


class _Body(httpx.AsyncByteStream):
    def __init__(self, data: bytes):
        self._data = data

    async def __aiter__(self):
        yield self._data


class MockAPI:
    """معالج MockTransport قابل للضبط لسيناريوهات التصدير/الرد."""

    def __init__(self):
        self.owner_uuid = OWNER_UUID
        self.conv_owner = OWNER_UUID
        self.convs_present = True
        self.export_status = 200
        self.export_bytes = ZIP
        self.export_headers = {}
        self.export_calls = 0
        self.reply_text = "رد كامل\nسطر تاني\nمرحبا بالعالم"

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v1/users/me":
            if self.owner_uuid is None:
                return httpx.Response(200, json={})
            return httpx.Response(200, json={"id": self.owner_uuid, "role": "owner"})
        if path == "/api/v1/app-conversations":
            if not self.convs_present:
                return httpx.Response(200, json=[])
            conv = {"id": CID, "title": "شات"}
            if self.conv_owner is not None:
                conv["created_by_user_id"] = self.conv_owner
            return httpx.Response(200, json=[conv])
        if path.endswith("/download"):
            self.export_calls += 1
            if self.export_status >= 400:
                return httpx.Response(self.export_status, json={"detail": "boom"})
            return httpx.Response(
                200, stream=_Body(self.export_bytes), headers=self.export_headers
            )
        if path.endswith("/events/search"):
            kind = request.url.params.get("kind__eq")
            if kind == "MessageEvent":
                return httpx.Response(
                    200,
                    json={
                        "items": [
                            {
                                "kind": "MessageEvent",
                                "source": "user",
                                "timestamp": "2026-01-01T00:00:01Z",
                                "llm_message": {"content": [{"type": "text", "text": "برومت"}]},
                            },
                            {
                                "kind": "MessageEvent",
                                "source": "agent",
                                "timestamp": "2026-01-01T00:00:02Z",
                                "llm_message": {
                                    "content": [{"type": "text", "text": self.reply_text}]
                                },
                            },
                        ]
                    },
                )
            return httpx.Response(200, json={"items": []})
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


def make_client(api: MockAPI, db=None) -> TestClient:
    client = OpenHandsClient(
        "https://example.test", "key", transport=httpx.MockTransport(api.handler)
    )
    return TestClient(build_web_app(make_config(), db, client=client), raise_server_exceptions=False)


def login(tc: TestClient) -> None:
    assert tc.post("/api/v1/auth", json={"initData": make_init_data(OWNER)}).status_code == 200


# ------------------------------------------------------------------- auth
def test_export_requires_auth():
    tc = make_client(MockAPI())
    r = tc.get(f"/api/v1/conversations/{CID}/export")
    assert r.status_code == 401 and r.json()["error"] == "unauthenticated"


def test_reply_requires_auth():
    tc = make_client(MockAPI())
    r = tc.get(f"/api/v1/conversations/{CID}/reply")
    assert r.status_code == 401 and r.json()["error"] == "unauthenticated"


def test_client_supplied_identity_cannot_override_session():
    """معرّف مستخدم من العميل (query/body) مايتّبعش — الهوية من الجلسة بس."""
    api = MockAPI()
    api.conv_owner = "someone-else"
    tc = make_client(api)
    login(tc)
    # حتّى مع `?user_id=<OWNER>` مزيّف، الملكية بتتفحص server-side ⇒ 403.
    r = tc.get(f"/api/v1/conversations/{CID}/export", params={"user_id": OWNER, "telegram_id": OWNER})
    assert r.status_code == 403
    assert api.export_calls == 0


# ------------------------------------------------------------------ export
def test_export_authorized_success_headers_and_name():
    api = MockAPI()
    tc = make_client(api)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/export")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    cd = r.headers["content-disposition"]
    assert cd == f'attachment; filename="conversation-{CID}.zip"'
    assert r.content == ZIP
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "no-store"
    assert api.export_calls == 1


def test_export_other_owner_forbidden_no_download():
    api = MockAPI()
    api.conv_owner = "someone-else"
    tc = make_client(api)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/export")
    assert r.status_code == 403 and r.json()["error"] == "unauthorized"
    assert api.export_calls == 0


def test_export_null_owner_fails_closed():
    api = MockAPI()
    api.conv_owner = None
    tc = make_client(api)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/export")
    assert r.status_code == 403
    assert api.export_calls == 0


def test_export_unknown_identity_fails_closed():
    api = MockAPI()
    api.owner_uuid = None
    tc = make_client(api)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/export")
    assert r.status_code == 403
    assert api.export_calls == 0


def test_export_missing_conversation_safe():
    api = MockAPI()
    api.convs_present = False
    tc = make_client(api)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/export")
    assert r.status_code == 404 and r.json()["error"] == "not_found"
    assert api.export_calls == 0


def test_export_invalid_conversation_id():
    tc = make_client(MockAPI())
    login(tc)
    r = tc.get("/api/v1/conversations/bad%20id%21/export")
    assert r.status_code == 400
    assert r.json()["error"] == "bad_request"


def test_export_upstream_failure_is_not_false_success():
    """فشل التنزيل البعيد ⇒ مفيش ملف ولا نجاح كاذب."""
    api = MockAPI()
    api.export_status = 503
    tc = make_client(api)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/export")
    assert r.status_code >= 400
    assert "content-disposition" not in r.headers
    assert api.export_calls == 1


def test_export_oversize_rejected_safely():
    """عدّى الحد الصلب ⇒ 413 منظّم (مفيش بَافِر غير محدود، مفيش ملف)."""
    api = MockAPI()
    api.export_bytes = b"x" * (MAX_EXPORT_BYTES + 1)
    tc = make_client(api)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/export")
    assert r.status_code == 413
    assert r.json()["error"] == "too_large"
    assert "content-disposition" not in r.headers


def test_export_declared_oversize_content_length_rejected():
    """`Content-Length` معلن أكبر من الحد ⇒ رفض قبل القراءة (413)."""
    api = MockAPI()
    api.export_bytes = b""
    api.export_headers = {"Content-Length": str(MAX_EXPORT_BYTES + 1)}
    tc = make_client(api)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/export")
    assert r.status_code == 413


def test_export_filename_safe_and_no_header_injection():
    """اسم الملف بيتنقّى ⇒ مفيش CR/LF/اقتباس/مسار (مفيش response-header injection)."""
    assert export_filename(CID) == f"conversation-{CID}.zip"
    # معرّف غير صالح ⇒ اسم افتراضي آمن (مفيش أي محرف من المدخل الخطر).
    dirty = 'a"\r\nX-Evil: 1/../b'
    name = export_filename(dirty)
    assert "\r" not in name and "\n" not in name and '"' not in name
    assert "/" not in name and "\\" not in name
    assert name == "conversation.zip"  # مفيش أي محرف من المدخل غير الصالح


def test_export_filename_sanitizes_partial_valid_id():
    # معرّف صالح الطول لكن فيه محارف مش مسموحة ⇒ اسم افتراضي آمن (مفيش < أو >).
    name = export_filename("c1<script>")
    assert "<" not in name and ">" not in name
    assert name == "conversation.zip"


# ----------------------------------------------------- deletion / tombstone
def test_export_deleted_conversation_not_exported(tmp_path):
    db = Database(str(tmp_path / "s.sqlite3"))
    db.delete_conversation(CID, "2026-01-01T00:00:00Z", remote_confirmed=True)
    assert db.is_deleted(CID) is True
    api = MockAPI()
    tc = make_client(api, db=db)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/export")
    assert r.status_code == 404 and r.json()["error"] == "not_found"
    assert api.export_calls == 0  # مفيش تنزيل ولا إحياء


def test_export_deleted_check_fails_closed(tmp_path):
    """قاعدة غير متاحة أثناء فحص الشاهد ⇒ رفض التصدير (فشل مغلق)، مفيش تنزيل."""
    db = Database(str(tmp_path / "s.sqlite3"))

    def boom(*_a, **_k):
        raise sqlite3.OperationalError("database is locked")

    db.is_deleted = boom  # type: ignore[assignment]
    api = MockAPI()
    tc = make_client(api, db=db)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/export")
    assert r.status_code >= 400
    assert api.export_calls == 0


def test_export_no_secrets_or_internal_metadata_in_body():
    api = MockAPI()
    tc = make_client(api)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/export")
    assert r.content == ZIP
    # مفيش أي أسرار/مفاتيح في الجسم (zip الخام بس).
    assert b"key" not in r.content
    assert OWNER_UUID.encode() not in r.content


# ------------------------------------------------------------- full reply
def test_full_reply_returns_complete_text():
    api = MockAPI()
    tc = make_client(api)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/reply")
    assert r.status_code == 200
    body = r.json()
    assert body["reply"] == api.reply_text
    assert body["reply_truncated"] is False
    assert body["conversation_id"] == CID


def test_full_reply_not_truncated_at_preview_limit():
    """المعاينة محدودة بـ 4000، لكن الرد الكامل مايتقصّش عند حد المعاينة."""
    api = MockAPI()
    api.reply_text = "ا" * 6000
    tc = make_client(api)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/reply")
    assert r.status_code == 200
    assert len(r.json()["reply"]) == 6000
    assert r.json()["reply_truncated"] is False


def test_full_reply_other_owner_forbidden():
    api = MockAPI()
    api.conv_owner = "someone-else"
    tc = make_client(api)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/reply")
    assert r.status_code == 403


def test_full_reply_hard_cap_sets_truncated_flag():
    api = MockAPI()
    api.reply_text = "ب" * (MAX_FULL_REPLY_CHARS + 50)
    tc = make_client(api)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/reply")
    assert r.status_code == 200
    assert r.json()["reply_truncated"] is True
    assert len(r.json()["reply"]) <= MAX_FULL_REPLY_CHARS + 2


def test_full_reply_no_reply_returns_empty():
    api = MockAPI()
    api.reply_text = ""
    tc = make_client(api)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/reply")
    assert r.status_code == 200
    assert r.json()["reply"] == ""


def test_full_reply_invalid_id():
    tc = make_client(MockAPI())
    login(tc)
    r = tc.get("/api/v1/conversations/bad%20id%21/reply")
    assert r.status_code == 400
