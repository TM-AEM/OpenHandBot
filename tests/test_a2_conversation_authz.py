"""OHB2-09-A2-02: تكافؤ التفويض عبر كل مسارات الشات في الـ Mini App.

بيغطّي (table-driven) المسارات اللي بتوصل لبيانات شات محدّد:
`GET /conversations/{id}`، `/status`، `/cost`، `/files`، `/file`، و`POST`/`DELETE`
`/conversations/{id}/watch`. لكل مسار بنختبر:

- المالك الصح (200/نجاح).
- مالك تاني (403 unauthorized).
- مالك فاضي/null (403 فشل مغلق).
- هوية `/users/me` مش معروفة (403 فشل مغلق).
- شات مش موجود (404).
- معرّف غير صالح (400).
- مستخدم غير مصادَق (401).
- **إثبات إن البيانات المحمية ما اتجابتش** عند فشل التفويض (عدّادات النداءات).

الاختبارات بتضرب المسار الحقيقي (Starlette route) مش الدالة المساعدة بس.
"""
from __future__ import annotations

import json

import httpx
import pytest
from starlette.testclient import TestClient

from bot.config import Config
from bot.openhands_client import OpenHandsClient
from bot.web import build_web_app
from tests._miniapp_helpers import BOT_TOKEN, make_init_data

OWNER = 555
OTHER = 999
OWNER_UUID = "owner-uuid-123"
CID = "c1"
ORIGIN = "https://app.test"


class _Body(httpx.AsyncByteStream):
    def __init__(self, data: bytes):
        self._data = data

    async def __aiter__(self):
        yield self._data


class MockAPI:
    """معالج MockTransport قابل للضبط + عدّادات لكل نقطة محمية."""

    def __init__(self):
        self.owner_uuid = OWNER_UUID
        self.conv_owner = OWNER_UUID
        self.convs_present = True
        self.files = ["src/main.py"]
        self.contents = {"src/main.py": "print(1)\n"}
        # عدّادات النداءات المحمية (لإثبات إنها ما بتتنادش عند فشل التفويض)
        self.events_calls = 0
        self.files_calls = 0
        self.file_calls = 0
        self.convs_calls = 0  # نداءات جلب قايمة الشات (تفويض الملكية) — M2 regression

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v1/users/me":
            if self.owner_uuid is None:
                return httpx.Response(200, json={})
            return httpx.Response(200, json={"id": self.owner_uuid, "role": "owner"})
        if path == "/api/v1/app-conversations":
            self.convs_calls += 1
            if not self.convs_present:
                return httpx.Response(200, json=[])
            conv = {"id": CID, "title": "شات", "execution_status": "running"}
            if self.conv_owner is not None:
                conv["created_by_user_id"] = self.conv_owner
            return httpx.Response(200, json=[conv])
        if path.endswith("/events/search"):
            self.events_calls += 1
            return httpx.Response(200, json={"items": []})
        if path.endswith("/files"):
            self.files_calls += 1
            return httpx.Response(200, json=list(self.files))
        if path.endswith("/file"):
            self.file_calls += 1
            content = self.contents.get(request.url.params.get("file_path"), "")
            return httpx.Response(200, stream=_Body(json.dumps(content).encode()))
        return httpx.Response(404, json={"detail": "no"})


def make_config(**over) -> Config:
    base = dict(
        telegram_bot_token=BOT_TOKEN,
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({OWNER}),
        owner_id=OWNER,
        mini_app_cookie_secure=False,
        mini_app_allowed_origins=frozenset({ORIGIN}),
    )
    base.update(over)
    return Config(**base)


def make_client(api: MockAPI, *, features_off=False, monkeypatch=None, db=None) -> TestClient:
    if features_off and monkeypatch is not None:
        monkeypatch.setattr("bot.features.DEFERRED_FEATURES_HIDDEN", False)
    client = OpenHandsClient(
        "https://example.test", "key", transport=httpx.MockTransport(api.handler)
    )
    return TestClient(build_web_app(make_config(), db, client=client), raise_server_exceptions=False)


def login(tc: TestClient) -> None:
    assert tc.post("/api/v1/auth", json={"initData": make_init_data(OWNER)}).status_code == 200


# مسارات القراءة (GET) اللي بتوصل لبيانات محمية.
READ_ROUTES = [
    ("detail", lambda cid: f"/api/v1/conversations/{cid}", {}),
    ("status", lambda cid: f"/api/v1/conversations/{cid}/status", {}),
    ("cost", lambda cid: f"/api/v1/conversations/{cid}/cost", {}),
    ("files", lambda cid: f"/api/v1/conversations/{cid}/files", {}),
    ("file", lambda cid: f"/api/v1/conversations/{cid}/file", {"path": "src/main.py"}),
]


@pytest.mark.parametrize("name, path_fn, params", READ_ROUTES, ids=[r[0] for r in READ_ROUTES])
def test_read_route_owner_ok(name, path_fn, params):
    api = MockAPI()
    tc = make_client(api)
    login(tc)
    r = tc.get(path_fn(CID), params=params)
    assert r.status_code == 200, (name, r.text)


@pytest.mark.parametrize("name, path_fn, params", READ_ROUTES, ids=[r[0] for r in READ_ROUTES])
def test_read_route_other_owner_forbidden(name, path_fn, params):
    api = MockAPI()
    api.conv_owner = "someone-else"
    tc = make_client(api)
    login(tc)
    r = tc.get(path_fn(CID), params=params)
    assert r.status_code == 403, (name, r.status_code)
    assert r.json()["error"] == "unauthorized"
    assert api.events_calls == 0 and api.files_calls == 0 and api.file_calls == 0


@pytest.mark.parametrize("name, path_fn, params", READ_ROUTES, ids=[r[0] for r in READ_ROUTES])
def test_read_route_null_owner_fails_closed(name, path_fn, params):
    api = MockAPI()
    api.conv_owner = None  # created_by_user_id ناقص
    tc = make_client(api)
    login(tc)
    r = tc.get(path_fn(CID), params=params)
    assert r.status_code == 403, (name, r.status_code)
    assert r.json()["error"] == "unauthorized"
    assert api.events_calls == 0 and api.files_calls == 0 and api.file_calls == 0


@pytest.mark.parametrize("name, path_fn, params", READ_ROUTES, ids=[r[0] for r in READ_ROUTES])
def test_read_route_unknown_identity_fails_closed(name, path_fn, params):
    api = MockAPI()
    api.owner_uuid = None
    tc = make_client(api)
    login(tc)
    r = tc.get(path_fn(CID), params=params)
    assert r.status_code == 403, (name, r.status_code)
    assert api.events_calls == 0 and api.files_calls == 0 and api.file_calls == 0


@pytest.mark.parametrize("name, path_fn, params", READ_ROUTES, ids=[r[0] for r in READ_ROUTES])
def test_read_route_missing_conversation_404(name, path_fn, params):
    api = MockAPI()
    api.convs_present = False
    tc = make_client(api)
    login(tc)
    r = tc.get(path_fn(CID), params=params)
    assert r.status_code == 404, (name, r.status_code)
    assert api.events_calls == 0 and api.files_calls == 0 and api.file_calls == 0


@pytest.mark.parametrize("name, path_fn, params", READ_ROUTES, ids=[r[0] for r in READ_ROUTES])
def test_read_route_unauthenticated_401(name, path_fn, params):
    api = MockAPI()
    tc = make_client(api)
    r = tc.get(path_fn(CID), params=params)
    assert r.status_code == 401, (name, r.status_code)
    assert api.events_calls == 0 and api.files_calls == 0 and api.file_calls == 0


@pytest.mark.parametrize("name, path_fn, params", READ_ROUTES, ids=[r[0] for r in READ_ROUTES])
def test_read_route_invalid_id_400(name, path_fn, params):
    api = MockAPI()
    tc = make_client(api)
    login(tc)
    r = tc.get(path_fn("bad id!"), params=params)
    assert r.status_code == 400, (name, r.status_code)


# ---------------------------------------------------------------- watch routes
def _watch_tc(api, monkeypatch, *, db=None):
    from bot.db import Database
    import tempfile, os

    if db is None:
        path = os.path.join(tempfile.mkdtemp(), "a2.sqlite3")
        db = Database(path)
    return make_client(api, features_off=True, monkeypatch=monkeypatch, db=db)


def test_watch_owner_ok(monkeypatch):
    api = MockAPI()
    tc = _watch_tc(api, monkeypatch)
    login(tc)
    r = tc.post(f"/api/v1/conversations/{CID}/watch", headers={"origin": ORIGIN})
    assert r.status_code == 200 and r.json() == {"ok": True, "watched": True}


def test_watch_other_owner_forbidden(monkeypatch):
    api = MockAPI()
    api.conv_owner = "someone-else"
    tc = _watch_tc(api, monkeypatch)
    login(tc)
    r = tc.post(f"/api/v1/conversations/{CID}/watch", headers={"origin": ORIGIN})
    assert r.status_code == 403 and r.json()["error"] == "unauthorized"


def test_watch_null_owner_fails_closed(monkeypatch):
    api = MockAPI()
    api.conv_owner = None
    tc = _watch_tc(api, monkeypatch)
    login(tc)
    r = tc.post(f"/api/v1/conversations/{CID}/watch", headers={"origin": ORIGIN})
    assert r.status_code == 403 and r.json()["error"] == "unauthorized"


def test_watch_missing_conversation_404(monkeypatch):
    api = MockAPI()
    api.convs_present = False
    tc = _watch_tc(api, monkeypatch)
    login(tc)
    r = tc.post(f"/api/v1/conversations/{CID}/watch", headers={"origin": ORIGIN})
    assert r.status_code == 404


def test_unwatch_requires_auth_and_origin(monkeypatch):
    api = MockAPI()
    tc = _watch_tc(api, monkeypatch)
    r = tc.delete(f"/api/v1/conversations/{CID}/watch", headers={"origin": ORIGIN})
    assert r.status_code == 401
    login(tc)
    r = tc.delete(f"/api/v1/conversations/{CID}/watch", headers={"origin": "https://evil.test"})
    assert r.status_code == 403


def test_unwatch_is_not_conversation_ownership_scoped_by_design(monkeypatch):
    """قرار OHB2-09-A2-02: unwatch **مابيتحقّقش** من ملكية الشات قصدًا.

    unwatch عملية على قايمة متابعات المالك نفسه (حالة مالك واحد)، مش قراءة بيانات شات،
    فبتفضل شغّالة حتى لو الشات مش موجود/غير مملوك دلوقتي (عشان ما يحصلش حالة عالقة،
    وتكافؤ مع أمر البوت). الحماية: جلسة المالك + origin (مُختبرة فوق) + معرّف صالح.
    """
    api = MockAPI()
    api.convs_present = False  # الشات مش موجود أصلاً عند OpenHands
    api.conv_owner = "someone-else"  # ومالك مختلف كمان
    tc = _watch_tc(api, monkeypatch)
    login(tc)
    r = tc.delete(f"/api/v1/conversations/{CID}/watch", headers={"origin": ORIGIN})
    assert r.status_code == 200 and r.json() == {"ok": True, "watched": False}
    assert api.events_calls == 0  # مفيش أي جلب بيانات شات


def test_upstream_lookup_failure_maps_to_502():
    def handler(request):
        if request.url.path == "/api/v1/users/me":
            return httpx.Response(200, json={"id": OWNER_UUID})
        if request.url.path == "/api/v1/app-conversations":
            return httpx.Response(500, json={"detail": "boom"})
        return httpx.Response(404, json={"detail": "no"})

    client = OpenHandsClient("https://example.test", "key", transport=httpx.MockTransport(handler))
    tc = TestClient(build_web_app(make_config(), None, client=client), raise_server_exceptions=False)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/cost")
    assert r.status_code == 502 and r.json()["error"] == "upstream_error"


# --------------------------------------------------------- prompt route (B2-06-04)
def _prompt_tc(api, db):
    """عميل موصَّل بقاعدة حقيقية عشان نتأكد إن **مفيش سجل صندوق** عند رفض التفويض."""
    client = OpenHandsClient(
        "https://example.test", "key", transport=httpx.MockTransport(api.handler)
    )
    tc = TestClient(
        build_web_app(make_config(), db, client=client), raise_server_exceptions=False
    )
    login(tc)
    return tc


def test_prompt_owner_queues_outbox(tmp_path):
    from bot.db import Database

    api = MockAPI()
    db = Database(str(tmp_path / "a2prompt.sqlite3"))
    tc = _prompt_tc(api, db)
    r = tc.post(
        f"/api/v1/conversations/{CID}/prompt",
        json={"text": "اعمل حاجة"},
        headers={"origin": ORIGIN},
    )
    assert r.status_code == 200 and r.json()["queued"] is True
    assert db.count_outbox("pending") == 1  # المالك سجّل برومت


def test_prompt_other_owner_forbidden_no_outbox(tmp_path):
    from bot.db import Database

    api = MockAPI()
    api.conv_owner = "someone-else"
    db = Database(str(tmp_path / "a2prompt.sqlite3"))
    tc = _prompt_tc(api, db)
    r = tc.post(
        f"/api/v1/conversations/{CID}/prompt",
        json={"text": "اعمل حاجة"},
        headers={"origin": ORIGIN},
    )
    assert r.status_code == 403 and r.json()["error"] == "unauthorized"
    assert db.count_outbox("pending") == 0  # مفيش سجل صندوق قبل التفويض
    assert api.events_calls == 0


def test_prompt_null_owner_fails_closed_no_outbox(tmp_path):
    from bot.db import Database

    api = MockAPI()
    api.conv_owner = None
    db = Database(str(tmp_path / "a2prompt.sqlite3"))
    tc = _prompt_tc(api, db)
    r = tc.post(
        f"/api/v1/conversations/{CID}/prompt",
        json={"text": "اعمل حاجة"},
        headers={"origin": ORIGIN},
    )
    assert r.status_code == 403 and r.json()["error"] == "unauthorized"
    assert db.count_outbox("pending") == 0


def test_prompt_missing_conversation_404_no_outbox(tmp_path):
    from bot.db import Database

    api = MockAPI()
    api.convs_present = False
    db = Database(str(tmp_path / "a2prompt.sqlite3"))
    tc = _prompt_tc(api, db)
    r = tc.post(
        f"/api/v1/conversations/{CID}/prompt",
        json={"text": "اعمل حاجة"},
        headers={"origin": ORIGIN},
    )
    assert r.status_code == 404
    assert db.count_outbox("pending") == 0


def test_prompt_invalid_id_400(tmp_path):
    from bot.db import Database

    api = MockAPI()
    db = Database(str(tmp_path / "a2prompt.sqlite3"))
    tc = _prompt_tc(api, db)
    r = tc.post(
        "/api/v1/conversations/bad id!/prompt",
        json={"text": "اعمل حاجة"},
        headers={"origin": ORIGIN},
    )
    assert r.status_code == 400
    assert db.count_outbox("pending") == 0


def test_prompt_unauthenticated_401(tmp_path):
    from bot.db import Database

    api = MockAPI()
    db = Database(str(tmp_path / "a2prompt.sqlite3"))
    client = OpenHandsClient(
        "https://example.test", "key", transport=httpx.MockTransport(api.handler)
    )
    tc = TestClient(
        build_web_app(make_config(), db, client=client), raise_server_exceptions=False
    )
    r = tc.post(
        f"/api/v1/conversations/{CID}/prompt",
        json={"text": "اعمل حاجة"},
        headers={"origin": ORIGIN},
    )
    assert r.status_code == 401
    assert db.count_outbox("pending") == 0


# ------------------------------------------------- F2 (BATCH-C): توحيد رفض المعرّف
def test_space_free_invalid_id_is_400_across_read_routes():
    """F2: معرّف غير صالح **بدون مسافة** (زي `a.b`) لازم يترفض محليًا 400 في **كل**
    مسارات القراءة بنفس الرمز (كان قبل كده 404 في مسار الملفات و400 في غيره)، ومفيش
    أي نداء upstream للمسار المحمي."""
    api = MockAPI()
    tc = make_client(api)
    login(tc)
    for name, path_fn, params in READ_ROUTES:
        r = tc.get(path_fn("a.b"), params=params)
        assert r.status_code == 400, (name, r.status_code, r.text)
    assert api.events_calls == 0 and api.files_calls == 0 and api.file_calls == 0


def test_space_free_invalid_id_is_400_for_prompt(tmp_path):
    """F2: نفس التوحيد على مسار الإرسال (POST /prompt) — 400 محلي بدون سجل صندوق."""
    from bot.db import Database

    api = MockAPI()
    db = Database(str(tmp_path / "a2f2.sqlite3"))
    client = OpenHandsClient(
        "https://example.test", "key", transport=httpx.MockTransport(api.handler)
    )
    tc = TestClient(
        build_web_app(make_config(), db, client=client), raise_server_exceptions=False
    )
    login(tc)
    r = tc.post(
        "/api/v1/conversations/a.b/prompt",
        json={"text": "x"},
        headers={"origin": ORIGIN},
    )
    assert r.status_code == 400
    assert db.count_outbox("pending") == 0


def test_space_free_invalid_id_is_400_and_no_upstream_across_all_read_routes():
    """M2 regression (BATCH-C FC3): ضعف تحقّق المعرّف في طبقة الخدمة (`_require_id`) لازم
    يبان في **كل** مسارات القراءة. قبل التقوية كان `_require_id` بيتحقّق من المسافة/الطول
    بس، فمعرّف زي `a.b` كان يعدّي للطبقة تحت ويوصل upstream (أو يرجّع 404) بدل 400 محلي.
    الاختبار بيضرب المعرّف غير الصالح على كل المسارات ويثبت: 400 محلي + صفر نداء upstream.

    (الاختبارات اللي كانت موجودة بتغطّي المعرّف اللي فيه مسافة `bad id!` اللي `_require_id`
    القديم كان بيرفضه أصلاً، فمكانتش بتكشف ضعف المعرّف اللي بلا مسافة.)"""
    api = MockAPI()
    tc = make_client(api)
    login(tc)
    for name, path_fn, params in READ_ROUTES:
        r = tc.get(path_fn("a.b"), params=params)
        assert r.status_code == 400, (name, r.status_code, r.text)
    # مفيش أي نداء upstream خالص (الرفض محلي بالكامل).
    assert api.convs_calls == 0
    assert api.events_calls == 0 and api.files_calls == 0 and api.file_calls == 0


def test_authenticated_but_disallowed_session_is_forbidden_and_revoked():
    """M4/M10 (BATCH-C): جلسة صالحة لمستخدم **بره الـ allowlist** لازم تترفض 403
    (`forbidden`) **وتتسحب** فورًا من مخزن الجلسات (منع استخدامها تاني). ده يغطّي فرع
    الـ allowlist في `_guarded` (سقوط مستخدم من القائمة بعد ما كانت جلسة قايمة)."""
    from bot.web.app import MiniApp

    api = MockAPI()
    client = OpenHandsClient("https://example.test", "key",
                             transport=httpx.MockTransport(api.handler))
    app = MiniApp(make_config(), None, client=client)
    tc = TestClient(app.router, raise_server_exceptions=False)
    sess = app.sessions.create(OTHER, {"display_name": "x"})
    tc.cookies.set("ohb_session", sess.token)
    r = tc.get(f"/api/v1/conversations/{CID}/files")
    assert r.status_code == 403 and r.json()["error"] == "forbidden"
    assert app.sessions.get(sess.token) is None  # الجلسة اتسحبت (revoke)
    assert api.files_calls == 0
