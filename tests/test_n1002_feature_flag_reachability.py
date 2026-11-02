"""OHB2-N10-02: انحدار لـ M2 — يثبّت **مدى** مفتاح `DEFERRED_FEATURES_HIDDEN` الفعلي،
عشان التوثيق ما يبعدش عن الكود.

العيب (M2): README/PLAN2_BASELINE كانوا بيقولوا إن المفتاح الواحد بيخفي «المجموعة كلها»،
لكن مسارات الملفات/التكلفة في الـ Mini App مسجّلة **دايمًا** (محميّة بالتصريح، مش بالمفتاح)،
فبتفضل متاحة لما المفتاح `True`. الـ Mini App بيعرض الملفات/التكلفة من غير شرط مفتاح
(`app.js` بينادي `renderFilesSection`/`renderCostSection` على طول).

الفجوة اللي سمحت بمرور العيب: الاختبارات كانت بتغطّي المفتاح على المتابعات بس، مفيش اختبار
بيثبّت إن مسارات الملفات/التكلفة بتفضل متاحة (وإن المتابعات بتتقفل) لما المفتاح `True`.

الفشل اللي الاختبار هيكتشفه: تغيير مدى المفتاح (مثلاً قفل مسار الملفات بالمفتاح) من غير
تحديث التوثيق — أو العكس.
"""
from __future__ import annotations

from types import SimpleNamespace

import httpx
from starlette.testclient import TestClient

from bot.config import Config
from bot.openhands_client import OpenHandsClient
from bot.web import build_web_app
from tests._miniapp_helpers import BOT_TOKEN, make_init_data

OWNER = 555
OWNER_UUID = "owner-uuid-123"


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/api/v1/users/me":
        return httpx.Response(200, json={"id": OWNER_UUID})
    if path == "/api/v1/app-conversations":
        return httpx.Response(200, json=[{"id": "c1", "created_by_user_id": OWNER_UUID}])
    if path.endswith("/events/search"):
        return httpx.Response(200, json={"items": []})
    if path.endswith("/files"):
        return httpx.Response(200, json=["a.py"])
    return httpx.Response(404, json={"detail": "no"})


def _client(monkeypatch, hidden: bool):
    monkeypatch.setattr("bot.features.DEFERRED_FEATURES_HIDDEN", hidden)
    client = OpenHandsClient(
        "https://example.test", "k", transport=httpx.MockTransport(_handler)
    )
    cfg = Config(
        telegram_bot_token=BOT_TOKEN,
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({OWNER}),
        owner_id=OWNER,
        mini_app_cookie_secure=False,
    )
    db = SimpleNamespace(list_watched=lambda: [], get_notifications_enabled=lambda: True)
    tc = TestClient(build_web_app(cfg, db, client=client), raise_server_exceptions=False)
    assert tc.post("/api/v1/auth", json={"initData": make_init_data(OWNER)}).status_code == 200
    return tc


def test_flag_true_keeps_files_cost_reachable_but_hides_watches(monkeypatch):
    """المفتاح `True`: الملفات/التكلفة تفضل متاحة (محميّة بالتصريح)؛ المتابعات تتقفل."""
    tc = _client(monkeypatch, hidden=True)
    assert tc.get("/api/v1/conversations/c1/cost").status_code == 200
    assert tc.get("/api/v1/conversations/c1/files").status_code == 200
    assert tc.get("/api/v1/watches").status_code == 404
    assert tc.get("/api/v1/app/bootstrap").json()["features"]["watches"] is False


def test_flag_false_exposes_watches(monkeypatch):
    """المفتاح `False` (حالة الإصدار): المتابعات متاحة كذلك."""
    tc = _client(monkeypatch, hidden=False)
    assert tc.get("/api/v1/watches").status_code == 200
    assert tc.get("/api/v1/app/bootstrap").json()["features"]["watches"] is True
