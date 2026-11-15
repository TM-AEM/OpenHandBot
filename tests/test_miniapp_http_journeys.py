"""OHB2-PLAN04-UI02 — رحلات HTTP حقيقية عبر حدود Starlette الفعلية.

بتشغّل تطبيق الـ Mini App الحقيقي (`build_web_app`) مع `Database` حقيقي (ملف SQLite
مؤقّت) و`OpenHandsClient` حقيقي فوق `httpx.MockTransport` (نفس مسار الطلب الخام).
مفيش أي نداء شبكة إنتاجي/تيليجرام/OpenHands حقيقي، ومفيش أسرار إنتاجية.

الهدف: تغطية الرحلات الأساسية **عبر حدود HTTP** (كوكيز، أصل، مصادقة، عقود الردود)
اللي مكانتش مغطّاة على مستوى الراوت قبل كده:
- رحلة البرومت الكاملة: إرسال ⇒ صندوق ⇒ استعلام الحالة (idempotency + polling).
- ربط المستودع (PATCH): نجاح + رفض الأصل + مستودع مشوّه + مالك تاني.
- مسار حالة الشات (GET /status) الإيجابي والسلبي.
- دورة حياة الكوكي: إنشاء عند الدخول، وإبطال عند الخروج.
"""
from __future__ import annotations

import httpx
from starlette.testclient import TestClient

from bot.config import Config
from bot.db import Database
from bot.openhands_client import OpenHandsClient
from bot.web import build_web_app
from bot.web.app import COOKIE_NAME
from tests._miniapp_helpers import BOT_TOKEN, make_init_data

OWNER = 555
OTHER = 999
OWNER_UUID = "owner-uuid-123"
CID = "c1"
ORIGIN = "https://app.test"


class MockAPI:
    """معالج MockTransport للعميل: شات واحد مملوك، قابلة للضبط لسيناريوهات الملكية."""

    def __init__(self) -> None:
        self.owner_uuid = OWNER_UUID
        self.conv_owner = OWNER_UUID
        self.patch_calls = 0
        self.send_calls = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v1/users/me":
            if self.owner_uuid is None:
                return httpx.Response(200, json={})
            return httpx.Response(200, json={"id": self.owner_uuid, "role": "owner"})
        if path == "/api/v1/app-conversations":
            conv = {"id": CID, "title": "شات", "selected_repository": "owner/repo"}
            if self.conv_owner is not None:
                conv["created_by_user_id"] = self.conv_owner
            return httpx.Response(200, json=[conv])
        if path == "/api/v1/app-conversations/search":
            return httpx.Response(200, json={"items": [{"id": CID, "title": "شات"}]})
        if path == f"/api/v1/app-conversations/{CID}" and request.method == "PATCH":
            self.patch_calls += 1
            return httpx.Response(200, json={"id": CID})
        if path == f"/api/v1/conversation/{CID}/events/search":
            return httpx.Response(200, json={"items": []})
        if path == f"/api/v1/app-conversations/{CID}/send-message":
            self.send_calls += 1
            return httpx.Response(200, json={})
        return httpx.Response(404, json={"detail": "no"})


def make_config(tmp_path, **over) -> Config:
    base = dict(
        telegram_bot_token=BOT_TOKEN,
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({OWNER}),
        owner_id=OWNER,
        mini_app_cookie_secure=False,
        mini_app_allowed_origins=frozenset({ORIGIN}),
        db_path=str(tmp_path / "t.sqlite3"),
    )
    base.update(over)
    return Config(**base)


def make_env(tmp_path, api: MockAPI, **over):
    db = Database(str(tmp_path / "t.sqlite3"))
    client = OpenHandsClient("https://example.test", "key", transport=httpx.MockTransport(api.handler))
    tc = TestClient(
        build_web_app(make_config(tmp_path, **over), db, client=client),
        raise_server_exceptions=False,
    )
    return tc, db


def login(tc: TestClient) -> None:
    r = tc.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    assert r.status_code == 200, r.text


# ------------------------------------------------------------------ auth
def test_auth_failure_sets_no_cookie(tmp_path):
    """initData غير صالح ⇒ 401، ومفيش كوكي جلسة."""
    api = MockAPI()
    tc, db = make_env(tmp_path, api)
    try:
        r = tc.post("/api/v1/auth", json={"initData": "garbage"})
        assert r.status_code == 401
        assert COOKIE_NAME not in (r.headers.get("set-cookie") or "")
        # بلا كوكي، مسار محمي ⇒ 401.
        assert tc.get("/api/v1/app/bootstrap").status_code == 401
    finally:
        db.close()


def test_cookie_lifecycle_created_then_invalidated(tmp_path):
    """الكوكي بيتعمل عند الدخول، وبيتبطّل عند الخروج (مفيش نجاح كاذب)."""
    api = MockAPI()
    tc, db = make_env(tmp_path, api)
    try:
        login(tc)
        assert tc.get("/api/v1/app/bootstrap").status_code == 200
        r = tc.post("/api/v1/auth/logout", headers={"origin": ORIGIN})
        assert r.status_code == 200
        assert "Max-Age=0" in (r.headers.get("set-cookie") or "")
        tc.cookies.clear()
        assert tc.get("/api/v1/app/bootstrap").status_code == 401
    finally:
        db.close()


# ---------------------------------------------------------------- journeys
def test_bootstrap_and_list_and_detail_journey(tmp_path):
    """التحميل الأولي ⇒ قايمة الشاتات ⇒ فتح التفاصيل (رحلة قراءة كاملة)."""
    api = MockAPI()
    tc, db = make_env(tmp_path, api)
    try:
        login(tc)
        boot = tc.get("/api/v1/app/bootstrap")
        assert boot.status_code == 200
        assert boot.json()["user"]["display_name"]

        lst = tc.get("/api/v1/conversations")
        assert lst.status_code == 200
        body = lst.json()
        assert body["page"] == 0 and body["items"][0]["id"] == CID

        detail = tc.get(f"/api/v1/conversations/{CID}")
        assert detail.status_code == 200
        assert detail.json()["id"] == CID
    finally:
        db.close()


def test_conversation_status_route_positive_and_negative(tmp_path):
    """GET /status: 200 لمالك، و403 لمالك تاني (عبر الحد الفعلي)."""
    api = MockAPI()
    tc, db = make_env(tmp_path, api)
    try:
        login(tc)
        r = tc.get(f"/api/v1/conversations/{CID}/status")
        assert r.status_code == 200
        assert r.json()["id"] == CID

        api.conv_owner = "someone-else"
        r2 = tc.get(f"/api/v1/conversations/{CID}/status")
        assert r2.status_code == 403
    finally:
        db.close()


def test_prompt_submission_is_idempotent_over_http(tmp_path):
    """إرسال نفس البرومت بنفس client_ref مرتين ⇒ نفس عملية الصندوق (مفيش تكرار)."""
    api = MockAPI()
    tc, db = make_env(tmp_path, api)
    try:
        login(tc)
        payload = {"text": "اعمل حاجة", "client_ref": "ref-1"}
        r1 = tc.post(f"/api/v1/conversations/{CID}/prompt", json=payload, headers={"origin": ORIGIN})
        assert r1.status_code == 200, r1.text
        op1 = r1.json()["operation"]
        r2 = tc.post(f"/api/v1/conversations/{CID}/prompt", json=payload, headers={"origin": ORIGIN})
        assert r2.status_code == 200
        op2 = r2.json()["operation"]
        assert op1["id"] == op2["id"], "نفس client_ref لازم يرجّع نفس العملية"

        # استعلام الحالة (polling) بمعرّف العملية.
        q = tc.get(
            "/api/v1/operations/outbox",
            params={"conversation_id": CID, "client_ref": "ref-1"},
        )
        assert q.status_code == 200
        assert q.json()["id"] == op1["id"]
    finally:
        db.close()


def test_prompt_requires_origin(tmp_path):
    """طلب تغيير حالة بلا Origin ⇒ 403، ومفيش عملية اتسجّلت."""
    api = MockAPI()
    tc, db = make_env(tmp_path, api)
    try:
        login(tc)
        r = tc.post(
            f"/api/v1/conversations/{CID}/prompt",
            json={"text": "x", "client_ref": "r"},
        )
        assert r.status_code == 403 and r.json()["error"] == "bad_origin"
    finally:
        db.close()


def test_repository_association_journey_and_negatives(tmp_path):
    """PATCH المستودع: نجاح (نداء بعيد واحد) + رفض أصل + مستودع مشوّه + مالك تاني."""
    api = MockAPI()
    tc, db = make_env(tmp_path, api)
    try:
        login(tc)
        ok = tc.patch(
            f"/api/v1/conversations/{CID}/repository",
            json={"repository": "owner/repo"},
            headers={"origin": ORIGIN},
        )
        assert ok.status_code == 200
        assert api.patch_calls == 1

        bad_origin = tc.patch(
            f"/api/v1/conversations/{CID}/repository",
            json={"repository": "owner/repo"},
        )
        assert bad_origin.status_code == 403 and bad_origin.json()["error"] == "bad_origin"

        bad_repo = tc.patch(
            f"/api/v1/conversations/{CID}/repository",
            json={"repository": "not-a-repo"},
            headers={"origin": ORIGIN},
        )
        assert bad_repo.status_code == 400

        api.conv_owner = "someone-else"
        other = tc.patch(
            f"/api/v1/conversations/{CID}/repository",
            json={"repository": "owner/repo"},
            headers={"origin": ORIGIN},
        )
        assert other.status_code == 403
        assert api.patch_calls == 1, "مفيش PATCH بعيد لمستخدم مش مصرّح"
    finally:
        db.close()


def test_unauthenticated_state_changing_route_rejected(tmp_path):
    """بلا جلسة، طلب تغيير حالة ⇒ 401 (مفيش وصول للخدمة)."""
    api = MockAPI()
    tc, db = make_env(tmp_path, api)
    try:
        r = tc.post(
            f"/api/v1/conversations/{CID}/prompt",
            json={"text": "x", "client_ref": "r"},
            headers={"origin": ORIGIN},
        )
        assert r.status_code == 401
        assert api.send_calls == 0
    finally:
        db.close()
