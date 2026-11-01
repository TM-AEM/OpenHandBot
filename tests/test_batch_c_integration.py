"""OHB2-09-BATCH-C — سيناريوهات دمج حقيقية عبر الطبقات (بوت ↔ Mini App ↔ الواجهة).

مكمّلة لـ `tests/test_batch_b_integration.py` (BATCH-B). هنا بنغطّي **20 سيناريو دمج
متكامل** (المطلوب في C3): كل سيناريو بيمرّ على أكتر من طبقة (route → service → ملفات/DB
→ عميل OpenHands مزيّف) ويثبت السلوك المُلاحَظ، مش الدالة الواحدة بس.

المبدأ: نضرب المسار الحقيقي (Starlette) على قاعدة بيانات حقيقية وعميل مزيّف، ونتحقّق
من الاستجابة **وعدّادات النداءات المحمية** (نثبت إن مفيش بيانات اتجابت قبل التفويض).
"""
from __future__ import annotations

import asyncio
import json
import time

import httpx
from starlette.testclient import TestClient

from bot.config import Config
from bot.db import Database
from bot.openhands_client import OpenHandsClient
from bot.web import build_web_app
from bot.web.app import MiniApp
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
    """عميل OpenHands مزيّف قابل للضبط + عدّادات للنداءات المحمية."""

    def __init__(self, *, owner_uuid=OWNER_UUID, conv_owner=OWNER_UUID, convs_present=True,
                 upstream_error=None):
        self.owner_uuid = owner_uuid
        self.conv_owner = conv_owner
        self.convs_present = convs_present
        self.upstream_error = upstream_error
        self.files = ["src/main.py"]
        self.contents = {"src/main.py": "print('hi')\n"}
        self.events_calls = 0
        self.files_calls = 0
        self.file_calls = 0
        # OHB2-09-BATCH-C: عدد نداءات جلب قايمة الشات (تفويض الملكية). بنستخدمه لإثبات
        # **ترتيب** النداءات: التفويض (جلب الشات) لازم يسبق أي قراءة محمية، ومفيش أي
        # قراءة/كتابة لما التفويض يفشل.
        self.convs_calls = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.upstream_error is not None:
            return httpx.Response(self.upstream_error, json={"detail": "boom"})
        path = request.url.path
        if path == "/api/v1/users/me":
            return httpx.Response(200, json={"id": self.owner_uuid} if self.owner_uuid else {})
        if path == "/api/v1/app-conversations":
            self.convs_calls += 1
            if not self.convs_present:
                return httpx.Response(200, json=[])
            conv = {"id": CID, "title": "شات", "execution_status": "running",
                    "metrics": {"accumulated_cost": 1.5, "model_name": "m",
                                "accumulated_token_usage": {"prompt_tokens": 10,
                                                            "completion_tokens": 4}}}
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


def make_app(api: MockAPI, db=None):
    client = OpenHandsClient("https://example.test", "key",
                             transport=httpx.MockTransport(api.handler))
    return TestClient(build_web_app(make_config(), db, client=client),
                      raise_server_exceptions=False)


def login(tc: TestClient, user_id: int = OWNER) -> None:
    r = tc.post("/api/v1/auth", json={"initData": make_init_data(user_id)})
    assert r.status_code == 200, r.text


# مسارات القراءة المحمية: (الاسم، دالة تبني المسار، params)
READ_ROUTES = [
    ("detail", lambda cid: f"/api/v1/conversations/{cid}", None),
    ("status", lambda cid: f"/api/v1/conversations/{cid}/status", None),
    ("cost", lambda cid: f"/api/v1/conversations/{cid}/cost", None),
    ("files", lambda cid: f"/api/v1/conversations/{cid}/files", None),
    ("file", lambda cid: f"/api/v1/conversations/{cid}/file", {"path": "src/main.py"}),
]


# ============================================================ 1) happy-path E2E
def test_owner_full_flow_across_all_read_routes():
    api = MockAPI()
    tc = make_app(api)
    login(tc)
    for name, path_fn, params in READ_ROUTES:
        r = tc.get(path_fn(CID), params=params)
        assert r.status_code == 200, (name, r.status_code, r.text)
    # ملفات القراءة جابت بيانات فعلية (مش ردود فاضية وهمية).
    assert tc.get(f"/api/v1/conversations/{CID}/files").json()["files"] == ["src/main.py"]
    assert tc.get(f"/api/v1/conversations/{CID}/file",
                  params={"path": "src/main.py"}).json()["text"] == "print('hi')\n"
    # كل مسار بيجيب قايمة الملفات مرة واحدة (مفيش نداءات مكرّرة عبر المسارات).
    assert api.files_calls == 4 and api.file_calls == 2


# ==================================================== 2) cross-owner denied all
def test_cross_owner_denied_across_all_read_routes_no_protected_fetch():
    api = MockAPI(conv_owner="someone-else")
    tc = make_app(api)
    login(tc)
    for name, path_fn, params in READ_ROUTES:
        r = tc.get(path_fn(CID), params=params)
        assert r.status_code == 403 and r.json()["error"] == "unauthorized", (name, r.text)
    # مفيش أي نداء محمي اتعمل قبل التفويض.
    assert api.events_calls == 0 and api.files_calls == 0 and api.file_calls == 0


# ==================================================== 3) null owner fail-closed
def test_null_owner_fails_closed_across_all_read_routes():
    api = MockAPI(conv_owner=None)
    tc = make_app(api)
    login(tc)
    for name, path_fn, params in READ_ROUTES:
        r = tc.get(path_fn(CID), params=params)
        assert r.status_code == 403 and r.json()["error"] == "unauthorized", (name, r.text)
    assert api.events_calls == 0 and api.files_calls == 0 and api.file_calls == 0


# ================================================= 4) unauthenticated → 401 all
def test_unauthenticated_reads_all_401():
    api = MockAPI()
    tc = make_app(api)  # بدون login
    for name, path_fn, params in READ_ROUTES:
        r = tc.get(path_fn(CID), params=params)
        assert r.status_code == 401, (name, r.status_code, r.text)
    assert api.events_calls == 0 and api.files_calls == 0 and api.file_calls == 0


# =============================================== 5) unknown identity fail-closed
def test_unknown_identity_fails_closed_all_read_routes():
    # /users/me بيرجّع {} ⇒ الهوية مش معروفة ⇒ فشل مغلق (مش اعتماد على غياب البيانات).
    api = MockAPI(owner_uuid=None)
    tc = make_app(api)
    login(tc)
    for name, path_fn, params in READ_ROUTES:
        r = tc.get(path_fn(CID), params=params)
        assert r.status_code == 403 and r.json()["error"] == "unauthorized", (name, r.text)
    assert api.events_calls == 0 and api.files_calls == 0 and api.file_calls == 0


# ==================================================== 6) prompt authz + outbox
def test_prompt_other_owner_creates_no_outbox(tmp_path):
    api = MockAPI(conv_owner="someone-else")
    db = Database(str(tmp_path / "s6.sqlite3"))
    tc = make_app(api, db=db)
    login(tc)
    r = tc.post(f"/api/v1/conversations/{CID}/prompt", json={"text": "اعمل حاجة"},
                headers={"origin": ORIGIN})
    assert r.status_code == 403 and r.json()["error"] == "unauthorized"
    assert db.count_outbox("pending") == 0  # مفيش أي أثر (سجل صندوق) قبل التفويض


def test_prompt_owner_queues_then_reconcile_discard_is_terminal(tmp_path):
    api = MockAPI()
    db = Database(str(tmp_path / "s6b.sqlite3"))
    tc = make_app(api, db=db)
    login(tc)
    r = tc.post(f"/api/v1/conversations/{CID}/prompt", json={"text": "اعمل حاجة"},
                headers={"origin": ORIGIN})
    assert r.status_code == 200 and r.json()["queued"] is True
    oid = r.json()["outbox_id"]
    assert db.count_outbox("pending") == 1
    # تسوية يدوية: discard ⇒ نهائي، ومستحيل يرجع pending.
    d = tc.post("/api/v1/operations/outbox/reconcile", json={"id": oid, "action": "discard"},
                headers={"origin": ORIGIN})
    assert d.status_code == 200
    assert db.get_outbox(oid).status == "discarded"
    again = tc.post("/api/v1/operations/outbox/reconcile",
                    json={"id": oid, "action": "discard"}, headers={"origin": ORIGIN})
    assert again.status_code == 409 and again.json()["error"] == "already_terminal"


# ================================================ 7) reconcile mark_sent parity
def test_reconcile_mark_sent_only_from_unknown_then_conflict(tmp_path):
    api = MockAPI()
    db = Database(str(tmp_path / "s7.sqlite3"))
    oid = db.add_or_group_outbox(CID, OWNER, "x", "t", client_ref="r1")
    tc = make_app(api, db=db)
    login(tc)
    # من pending ⇒ 409 (mark_sent للسجلات unknown بس).
    bad = tc.post("/api/v1/operations/outbox/reconcile",
                  json={"id": oid, "action": "mark_sent"}, headers={"origin": ORIGIN})
    assert bad.status_code == 409 and bad.json()["error"] == "invalid_state"
    # من unknown ⇒ sent (نهائي)، والنداء التاني idempotent.
    db.set_outbox_status(oid, "unknown", "t2")
    ok = tc.post("/api/v1/operations/outbox/reconcile",
                 json={"id": oid, "action": "mark_sent"}, headers={"origin": ORIGIN})
    assert ok.status_code == 200 and ok.json()["state"] == "accepted"
    again = tc.post("/api/v1/operations/outbox/reconcile",
                    json={"id": oid, "action": "mark_sent"}, headers={"origin": ORIGIN})
    assert again.status_code == 200 and again.json()["state"] == "accepted"
    assert db.get_outbox(oid).status == "sent"


# ==================================================== 8) watch / unwatch parity
def test_watch_owner_adds_then_unwatch_removes(tmp_path):
    api = MockAPI()
    db = Database(str(tmp_path / "s8.sqlite3"))
    tc = make_app(api, db=db)
    login(tc)
    w = tc.post(f"/api/v1/conversations/{CID}/watch", json={}, headers={"origin": ORIGIN})
    assert w.status_code == 200 and w.json()["watched"] is True
    assert db.is_watched(CID) is True
    u = tc.delete(f"/api/v1/conversations/{CID}/watch", headers={"origin": ORIGIN})
    assert u.status_code == 200 and u.json()["watched"] is False
    assert db.is_watched(CID) is False


def test_watch_other_owner_not_added(tmp_path):
    api = MockAPI(conv_owner="someone-else")
    db = Database(str(tmp_path / "s8b.sqlite3"))
    tc = make_app(api, db=db)
    login(tc)
    r = tc.post(f"/api/v1/conversations/{CID}/watch", json={}, headers={"origin": ORIGIN})
    assert r.status_code == 403 and r.json()["error"] == "unauthorized"
    assert db.is_watched(CID) is False  # مفيش شات غير مملوك في قايمة المتابعات


# ==================================================== 9) cost envelope safe
def test_cost_route_returns_denomination_neutral_envelope():
    api = MockAPI()
    tc = make_app(api)
    login(tc)
    body = tc.get(f"/api/v1/conversations/{CID}/cost").json()
    assert body["accumulated_cost"] == 1.5
    assert "cost_usd" not in body and "usd" not in json.dumps(body).lower()
    assert body["total_tokens"] is None  # مفيش تمثيل كاذب لحقل غايب


def test_cost_route_missing_metrics_is_all_none():
    api = MockAPI()
    api._conv_metrics_off = True

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/app-conversations":
            return httpx.Response(200, json=[{"id": CID, "created_by_user_id": OWNER_UUID}])
        return api.handler(request)

    client = OpenHandsClient("https://example.test", "key",
                             transport=httpx.MockTransport(handler))
    tc = TestClient(build_web_app(make_config(), None, client=client),
                    raise_server_exceptions=False)
    login(tc)
    body = tc.get(f"/api/v1/conversations/{CID}/cost").json()
    assert body["accumulated_cost"] is None and body["model"] is None
    assert body["prompt_tokens"] is None and body["total_tokens"] is None


# ==================================================== 10) bootstrap inbox badge
def test_bootstrap_unread_count_matches_inbox(tmp_path):
    api = MockAPI()
    db = Database(str(tmp_path / "s10.sqlite3"))
    db.add_inbox_event(CID, "شات", "state", "رسالة", "2026-01-01T00:00:00+00:00",
                       event_key="e1")
    db.add_inbox_event(CID, "شات", "state", "رسالة", "2026-01-01T00:00:01+00:00",
                       event_key="e2")
    tc = make_app(api, db=db)
    login(tc)
    boot = tc.get("/api/v1/app/bootstrap").json()
    assert boot["inbox"]["unread_count"] == 2
    # ونفس القيمة من مسار الإشعارات (GET /notifications).
    inbox = tc.get("/api/v1/notifications")
    assert inbox.status_code == 200
    assert len(inbox.json()["items"]) == 2


# ==================================================== 11) upstream outage → 502
def test_upstream_outage_maps_to_502_all_read_routes():
    api = MockAPI(upstream_error=503)
    tc = make_app(api)
    login(tc)
    for name, path_fn, params in READ_ROUTES:
        r = tc.get(path_fn(CID), params=params)
        assert r.status_code == 502 and r.json()["error"] == "upstream_error", (name, r.text)


# ==================================================== 12) missing conversation
def test_missing_conversation_404_all_read_routes():
    api = MockAPI(convs_present=False)
    tc = make_app(api)
    login(tc)
    for name, path_fn, params in READ_ROUTES:
        r = tc.get(path_fn(CID), params=params)
        assert r.status_code == 404, (name, r.status_code, r.text)
    assert api.files_calls == 0 and api.file_calls == 0

# =====================================================================
# OHB2-09-BATCH-C (C3 completion): 5 سيناريوهات إضافية عبر الطبقات.
# الهدف: نوصل لـ 20 سيناريو دمج حقيقي (15 الأصليين + 5 جداد)، كل واحد على حدود
# تطبيق حقيقية ومختلفة، مع إثبات الترتيب/الفشل المغلق/الذرّية.
# =====================================================================


# ---------------------------------------- 16) prompt idempotency across API+DB
def test_prompt_duplicate_ref_is_idempotent_and_persists_one_row(tmp_path):
    """تكرار نفس `client_ref` (double-tap) عبر الـ route الحقيقي ⇒ سجل صندوق واحد.

    الحدود: route (POST /prompt) → تفويض الملكية → `add_or_group_outbox` (SQLite حقيقي).
    بنثبت: نفس `outbox_id`، صف واحد في القاعدة، مفيش نص برومت في DTO الحالة، والحالة
    `pending` (لسه ما اتبعتتش).
    """
    api = MockAPI()
    db = Database(str(tmp_path / "s16.sqlite3"))
    tc = make_app(api, db=db)
    login(tc)
    body = {"text": "اعمل حاجة", "client_ref": "ref-xyz"}
    r1 = tc.post(f"/api/v1/conversations/{CID}/prompt", json=body, headers={"origin": ORIGIN})
    r2 = tc.post(f"/api/v1/conversations/{CID}/prompt", json=body, headers={"origin": ORIGIN})
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["outbox_id"] == r2.json()["outbox_id"]
    assert db.count_outbox("pending") == 1 and db.count_outbox() == 1
    assert r1.json()["operation"]["state"] == "pending"
    assert "text" not in r1.json()["operation"]
    # التفويض (جلب الشات) اتعمل قبل التسجيل، مرة لكل طلب.
    assert api.convs_calls == 2


# ---------------------------------------- 17) prompt authz failure => no row
def test_prompt_cross_owner_denied_creates_no_row_and_no_protected_fetch(tmp_path):
    """طلب برومت لشات مش بتاع المالك ⇒ 403، مفيش صف صندوق، مفيش قراءة محمية.

    مختلف عن السيناريو 6: هنا بنضيف إثبات **ترتيب** النداءات — التفويض بيجيب الشات
    مرة واحدة، ومفيش أي نداء ملفات/أحداث، والقاعدة فاضية تمامًا.
    """
    api = MockAPI(conv_owner="someone-else")
    db = Database(str(tmp_path / "s17.sqlite3"))
    tc = make_app(api, db=db)
    login(tc)
    r = tc.post(f"/api/v1/conversations/{CID}/prompt", json={"text": "x"},
                headers={"origin": ORIGIN})
    assert r.status_code == 403 and r.json()["error"] == "unauthorized"
    assert db.count_outbox() == 0
    assert api.convs_calls == 1  # التفويض بس
    assert api.events_calls == 0 and api.files_calls == 0 and api.file_calls == 0


# ------------------------- 18) unwatch unavailable conversation via real route
def test_unwatch_unavailable_conversation_via_route_returns_ok(tmp_path, monkeypatch):
    """إلغاء متابعة شات **مش موجود** عند OpenHands ⇒ 200 ومفيش أي جلب بيانات شات.

    الحدود: route (DELETE /watch) → `MiniAppService.unwatch` (مابيفوّضش ملكية قصدًا).
    مختلف عن `test_unwatch_is_not_conversation_ownership_scoped_by_design` (بيسحب
    طريقة الخدمة مباشرة) — هنا بنضرب الـ route الحقيقي مع Origin صالح ونثبت إن مفيش
    `get_conversations` اتعمل خالص.
    """
    import bot.features as features

    monkeypatch.setattr(features, "is_hidden", lambda name: False)
    api = MockAPI(convs_present=False, conv_owner="someone-else")
    db = Database(str(tmp_path / "s18.sqlite3"))
    tc = make_app(api, db=db)
    login(tc)
    r = tc.delete(f"/api/v1/conversations/{CID}/watch", headers={"origin": ORIGIN})
    assert r.status_code == 200 and r.json() == {"ok": True, "watched": False}
    assert api.convs_calls == 0  # مفيش تفويض/جلب شات خالص


# ---------------------- 19) watch then unwatch: only caller's watch list changes
def test_watch_then_unwatch_unavailable_changes_only_own_watchlist(tmp_path, monkeypatch):
    """إضافة شات للمتابعة ثم إلغاؤها والشات بقى **مش متاح** ⇒ القايمة بترجع فاضية.

    الحدود: POST /watch (تفويض ملكية ناجح → إضافة) ثم DELETE /watch (مابيفوّضش →
    إزالة). بنثبت إن التغيير محصور في **قايمة متابعات المالك** ومفيش جلب بيانات في
    مسار الإلغاء.
    """
    import bot.features as features

    monkeypatch.setattr(features, "is_hidden", lambda name: False)
    api = MockAPI()
    db = Database(str(tmp_path / "s19.sqlite3"))
    tc = make_app(api, db=db)
    login(tc)
    w = tc.post(f"/api/v1/conversations/{CID}/watch", json={}, headers={"origin": ORIGIN})
    assert w.status_code == 200 and w.json()["watched"] is True
    assert db.is_watched(CID) is True
    convs_after_watch = api.convs_calls

    # الشات بقى مش متاح عند OpenHands.
    api.convs_present = False
    u = tc.delete(f"/api/v1/conversations/{CID}/watch", headers={"origin": ORIGIN})
    assert u.status_code == 200 and u.json()["watched"] is False
    assert db.is_watched(CID) is False
    assert db.list_watched() == []
    # مسار الإلغاء ما جابش الشات خالص (التغيير محصور في قايمة المالك).
    assert api.convs_calls == convs_after_watch


# ------------------------- 20) outbox CAS conflict across route + DB boundary
def test_reconcile_discard_loses_cas_race_returns_conflict(tmp_path):
    """سباق CAS على سجل الصندوق بين قراتين ⇒ 409 `already_terminal` من غير أي تغيير.

    الحدود: route (POST /outbox/reconcile) → `MiniAppService.reconcile_outbox` →
    `Database.set_outbox_status_if_in` (CAS ذرّي). بنحقن سجل حالته `discarded` **بعد**
    قراءة الخدمة وقبل الـ CAS، ونثبت إن الـ CAS بيرجّع rowcount=0 ⇒ 409 والصف يفضل
    `discarded` (مفيش read-then-write سباق).
    """
    api = MockAPI()
    db = Database(str(tmp_path / "s20.sqlite3"))
    oid = db.add_or_group_outbox(CID, OWNER, "x", "2026-01-01T00:00:00+00:00")
    tc = make_app(api, db=db)
    login(tc)

    real_get = db.get_outbox
    calls = {"n": 0}
    first_seen = {}

    def racing_get(outbox_id):
        item = real_get(outbox_id)
        calls["n"] += 1
        # أول قراءة (قبل الـ CAS) بتشوف `pending`؛ بعدها بنحسم السجل من برّه (thread تاني).
        if calls["n"] == 1:
            first_seen["status"] = item.status
            db.set_outbox_status(oid, "discarded", "2026-01-01T00:00:01+00:00")
        return item

    db.get_outbox = racing_get  # type: ignore[assignment]
    r = tc.post("/api/v1/operations/outbox/reconcile",
                json={"id": oid, "action": "discard"}, headers={"origin": ORIGIN})
    assert r.status_code == 409 and r.json()["error"] == "already_terminal"
    # القراءة الأولى شافت `pending` ⇒ الفحص المسبق **عدّى**، والـ 409 ده جاي من الـ CAS
    # الذرّي (rowcount=0) مش من الفحص المسبق.
    assert first_seen["status"] == "pending"
    assert db.get_outbox(oid).status == "discarded"


# ------------------- 21) expired session cannot reveal stale protected data
def test_expired_session_401_no_stale_protected_data(tmp_path):
    """جلسة انتهت صلاحيتها أثناء الاستخدام ⇒ 401، ومفيش أي بيانات شات محمية بترجع.

    الحدود: cookie → `SessionStore.get` (انتهاء TTL) → `_guarded` ⇒ 401، ومفيش نداء
    `get_conversations`/ملفات خالص. (مكمّل لاختبار وحدة `test_session_expiry`.)
    """
    api = MockAPI()
    app = MiniApp(make_config(), None, client=OpenHandsClient(
        "https://example.test", "key", transport=httpx.MockTransport(api.handler)))
    tc = TestClient(app.router, raise_server_exceptions=False)
    login(tc)  # بيسجّل جلسة صالحة دلوقتي
    # نعمل جلسة منتهية بندخلها يدوي (بدون انتظار حقيقي).
    expired = app.sessions.create(OWNER, {"display_name": "x"}, now=time.time() - 10_000)
    tc.cookies.set("ohb_session", expired.token)
    for path in (f"/api/v1/conversations/{CID}/files",
                 f"/api/v1/conversations/{CID}",
                 "/api/v1/app/bootstrap"):
        r = tc.get(path)
        assert r.status_code == 401, (path, r.status_code, r.text)
    assert api.convs_calls == 0 and api.files_calls == 0 and api.file_calls == 0


# ------- 22) Telegram reply_prompt authz failure → no awaiting, no upstream
def test_telegram_reply_prompt_denied_sets_no_awaiting_and_no_upstream(tmp_path):
    """فشل تفويض `reply_prompt` (مالك مختلف) ⇒ مفيش توجيه برومت ومفيش أي نداء محمي.

    الحدود: handler البوت → `_authorized_conversation` → عميل الشات. مختلف عن
    `test_reply_prompt_other_owner_denied_no_awaiting` (بيفحص awaiting بس) — هنا
    بنثبت كمان إن **مفيش** أي جلب قايمة ملفات/قراءة اتعمل (فشل مغلق قبل أي بيانات).
    """
    import bot.handlers as h
    from tests.test_b06_file_routing import FileFlowClient
    from tests.test_handlers import _cb_update, _ctx_with

    client = FileFlowClient(conv_owner="someone-else")
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "prompt:c1")
    asyncio.run(h.reply_prompt(update, ctx))
    conv_id, kind = ctx.bot_data["db"].get_awaiting(1)
    assert conv_id is None and kind is None  # مفيش توجيه برومت
    assert client.list_calls == 0 and client.read_calls == 0  # مفيش أي قراءة محمية
    assert "مش مسموح" in update.callback_query.edits[-1]

