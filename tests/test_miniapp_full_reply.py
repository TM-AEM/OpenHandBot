"""OHB2-PHASE1B: اختبارات الرد الكامل في الـ Mini App.

بتستخدم `OpenHandsClient` حقيقي فوق `httpx.MockTransport` (نفس مسار البثّ الخام)،
وما تعملش أي نداء شبكة/تيليجرام/OpenHands حقيقي. بتتحقّق من:

- المصادقة (401 لغير المسجّل) ومنع تجاوز هوية الجلسة بمعرّف من العميل.
- ملكية الشات server-side (403 لمالك تاني/مالك ناقص).
- الرد الكامل: النص الكامل (مش مقصوص)، ورفض غير المصرّح.
"""
from __future__ import annotations

import httpx
from starlette.testclient import TestClient

from bot.config import Config
from bot.openhands_client import OpenHandsClient
from bot.web import build_web_app
from bot.web.services import MAX_FULL_REPLY_CHARS
from tests._miniapp_helpers import BOT_TOKEN, make_init_data

OWNER = 555
OWNER_UUID = "owner-uuid-123"
CID = "c1"


class MockAPI:
    """معالج MockTransport قابل للضبط لسيناريوهات الرد."""

    def __init__(self):
        self.owner_uuid = OWNER_UUID
        self.conv_owner = OWNER_UUID
        self.convs_present = True
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
    r = tc.get(f"/api/v1/conversations/{CID}/reply", params={"user_id": OWNER, "telegram_id": OWNER})
    assert r.status_code == 403


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
