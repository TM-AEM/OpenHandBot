"""اختبارات تكامل ميزات الـ Mini App + أمان OHB2-06 (S2/S3/S4).

بتستخدم عميل OpenHands وهمي وقاعدة بيانات وهمية بسيطة، لكن الكود الحقيقي
(التطبيق + الخدمة + المحدّد + فحص الأصل) هو اللي بيتنفّذ.
"""
from __future__ import annotations

from starlette.testclient import TestClient

from bot.config import Config
from bot.web import build_web_app
from bot.web.app import COOKIE_NAME, MiniApp
from bot.web.clientip import UNKNOWN, resolve_client_ip
from tests._miniapp_helpers import BOT_TOKEN, make_init_data

OWNER = 555
OTHER = 999
ORIGIN = "https://app.test"


# ------------------------------------------------------------------- fakes
class FakeClient:
    def __init__(self, items=None, convs=None, repos=None, exchange=(None, None)) -> None:
        self.items = items if items is not None else []
        self.convs = convs if convs is not None else {}
        self.repos = repos if repos is not None else []
        self.exchange = exchange
        self.sent = []

    async def search_conversations(self, limit=100, page_id=None):
        return {"items": list(self.items), "next_page_id": None}

    async def get_conversations(self, ids):
        return [self.convs[i] for i in ids if i in self.convs]

    async def get_last_exchange(self, conversation_id):
        return self.exchange

    async def search_repositories(self, query="", limit=100):
        return list(self.repos)


class FakeWorker:
    def __init__(self) -> None:
        self.woken = 0

    def wake(self) -> None:
        self.woken += 1


class FakeDb:
    def __init__(self) -> None:
        self.notifications = True
        self.watched: dict[str, dict] = {}
        self.outbox: list = []
        self.creation: list = []
        self.removed: list = []

    def get_notifications_enabled(self):
        return self.notifications

    def set_notifications_enabled(self, enabled):
        self.notifications = bool(enabled)

    def list_watched(self):
        class W:
            def __init__(self, d):
                self.conversation_id = d["id"]
                self.title = d.get("title", "")
                self.last_state = d.get("last_state")
                self.added_at = d.get("added_at")

        return [W(d) for d in self.watched.values()]

    def add_watched(self, cid, title, chat_id, new_lifecycle=True):
        self.watched[cid] = {"id": cid, "title": title}

    def set_last_state(self, cid, state):
        if cid in self.watched:
            self.watched[cid]["last_state"] = state

    def remove_watched(self, cid):
        self.removed.append(cid)
        self.watched.pop(cid, None)

    def add_or_group_outbox(self, cid, chat_id, text, now, window=None, client_ref=None):
        # idempotency: نفس (cid, chat_id, client_ref) ⇒ نفس السجل، مفيش برومت مكرّر.
        if client_ref:
            for item in self.outbox:
                if item["cid"] == cid and item["chat_id"] == chat_id and item["ref"] == client_ref:
                    return item["id"]
        item = {
            "id": len(self.outbox) + 1,
            "cid": cid,
            "chat_id": chat_id,
            "text": text,
            "ref": client_ref,
            "status": "pending",
        }
        self.outbox.append(item)
        return item["id"]

    def get_outbox(self, outbox_id):
        for item in self.outbox:
            if item["id"] == outbox_id:
                return _Row(
                    id=item["id"], conversation_id=item["cid"], status=item["status"],
                    created_at="t", updated_at="t",
                )
        return None

    def find_outbox_by_ref(self, cid, chat_id, client_ref):
        for item in self.outbox:
            if item["cid"] == cid and item["chat_id"] == chat_id and item["ref"] == client_ref:
                return _Row(
                    id=item["id"], conversation_id=item["cid"], status=item["status"],
                    created_at="t", updated_at="t",
                )
        return None

    def add_creation_job(self, chat_id, repo, text, now, client_ref=None):
        if client_ref:
            for job in self.creation:
                if job["chat_id"] == chat_id and job["ref"] == client_ref:
                    return job["id"]
        job = {
            "id": len(self.creation) + 1,
            "chat_id": chat_id,
            "repo": repo,
            "text": text,
            "ref": client_ref,
            "status": "pending",
            "conversation_id": None,
        }
        self.creation.append(job)
        return job["id"]

    def get_creation_job(self, job_id):
        for job in self.creation:
            if job["id"] == job_id:
                return _Row(
                    id=job["id"], repo=job["repo"], status=job["status"],
                    conversation_id=job["conversation_id"], created_at="t", updated_at="t",
                )
        return None

    def find_creation_job_by_ref(self, chat_id, client_ref):
        for job in self.creation:
            if job["chat_id"] == chat_id and job["ref"] == client_ref:
                return _Row(
                    id=job["id"], repo=job["repo"], status=job["status"],
                    conversation_id=job["conversation_id"], created_at="t", updated_at="t",
                )
        return None


class _Row:
    """صف وهمي بأقل الحقول اللي الـ DTO بيقراها."""

    def __init__(self, **kw) -> None:
        self.__dict__.update(kw)


class FakeApplication:
    def __init__(self, **workers) -> None:
        self.bot_data = dict(workers)


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


def authed_client(**over) -> TestClient:
    kwargs = over.pop("_kwargs", {})
    c = TestClient(build_web_app(make_config(**over), **kwargs), raise_server_exceptions=False)
    r = c.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    assert r.status_code == 200
    return c


def build(**over):
    kwargs = over.pop("_kwargs", {})
    cfg = make_config(**over)
    return TestClient(build_web_app(cfg, **kwargs), raise_server_exceptions=False)


# ------------------------------------------------------- S3 client IP
class _Req:
    def __init__(self, host):
        self.client = type("C", (), {"host": host})() if host is not None else None


def test_clientip_public_ip_used_directly():
    assert resolve_client_ip(_Req("8.8.8.8")) == "8.8.8.8"
    assert resolve_client_ip(_Req("1.1.1.1")) == "1.1.1.1"


def test_clientip_private_ip_collapses_to_unknown():
    assert resolve_client_ip(_Req("10.1.1.62")) == UNKNOWN
    assert resolve_client_ip(_Req("127.0.0.1")) == UNKNOWN
    assert resolve_client_ip(_Req("192.168.1.5")) == UNKNOWN


def test_clientip_missing_or_garbage_is_unknown():
    assert resolve_client_ip(_Req(None)) == UNKNOWN
    assert resolve_client_ip(_Req("not-an-ip")) == UNKNOWN


def test_clientip_ignores_forged_forwarded_headers():
    """هيدرز X-Forwarded-For المزوّرة ما بتأثرش — بنقرأ IP الاتصال الفعلي بس."""

    class Req:
        client = type("C", (), {"host": "10.1.1.62"})()
        headers = {"x-forwarded-for": "203.0.113.7", "x-real-ip": "203.0.113.7"}

    assert resolve_client_ip(Req()) == UNKNOWN


# ------------------------------------------------------- S2 rate limiting
def test_auth_rate_limited_with_retry_after():
    cfg = make_config(mini_app_auth_rate_per_minute=2, mini_app_auth_rate_per_hour=100)
    c = TestClient(build_web_app(cfg, None), raise_server_exceptions=False)
    body = {"initData": make_init_data(OWNER)}
    assert c.post("/api/v1/auth", json=body).status_code == 200
    assert c.post("/api/v1/auth", json=body).status_code == 200
    r = c.post("/api/v1/auth", json=body)
    assert r.status_code == 429
    assert r.json()["error"] == "rate_limited"
    assert int(r.headers["retry-after"]) >= 1
    # الرد 429 بيعمل الأمن برضه.
    assert r.headers["x-content-type-options"] == "nosniff"


def test_authenticated_api_rate_limited_per_session():
    cfg = make_config(mini_app_api_rate_per_minute=2)
    c = TestClient(build_web_app(cfg, None), raise_server_exceptions=False)
    c.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    assert c.get("/api/v1/app/bootstrap").status_code == 200
    assert c.get("/api/v1/app/bootstrap").status_code == 200
    r = c.get("/api/v1/app/bootstrap")
    assert r.status_code == 429
    assert "retry-after" in {k.lower() for k in r.headers}


def test_health_and_static_not_rate_limited():
    cfg = make_config(mini_app_api_rate_per_minute=1)
    c = TestClient(build_web_app(cfg, None), raise_server_exceptions=False)
    for _ in range(5):
        assert c.get("/health").status_code == 200
        assert c.get("/mini/").status_code == 200


# ------------------------------------------------------- S4 origin guard
def test_state_changing_requires_valid_origin():
    c = authed_client(_kwargs={"db": FakeDb()})
    # من غير Origin ⇒ مرفوض.
    assert c.post("/api/v1/app/notifications", json={"enabled": False}).status_code == 403
    # Origin مضاد ⇒ مرفوض.
    r = c.post(
        "/api/v1/app/notifications",
        json={"enabled": False},
        headers={"origin": "https://evil.test"},
    )
    assert r.status_code == 403 and r.json()["error"] == "bad_origin"
    # Origin مطابق ⇒ مقبول.
    r = c.post(
        "/api/v1/app/notifications",
        json={"enabled": False},
        headers={"origin": ORIGIN},
    )
    assert r.status_code == 200 and r.json()["notifications_enabled"] is False


def test_cross_site_sec_fetch_site_rejected():
    c = authed_client(_kwargs={"db": FakeDb()})
    r = c.post(
        "/api/v1/app/notifications",
        json={"enabled": True},
        headers={"origin": ORIGIN, "sec-fetch-site": "cross-site"},
    )
    assert r.status_code == 403


def test_read_only_endpoints_do_not_require_origin():
    # GET (قراءة) مش محتاج Origin.
    c = authed_client()
    assert c.get("/api/v1/app/bootstrap").status_code == 200


def test_dev_same_host_origin_allowed():
    c = authed_client(_kwargs={"db": FakeDb()})
    r = c.post(
        "/api/v1/app/notifications",
        json={"enabled": True},
        headers={"origin": "http://testserver"},
    )
    assert r.status_code == 200


# ------------------------------------------------------- feature endpoints
def test_list_conversations_maps_status_and_watch():
    client = FakeClient(
        items=[
            {"id": "c1", "title": "T1", "selected_repository": "o/r", "execution_status": "running"},
            {"id": "c2", "title": "T2", "execution_status": "finished"},
        ]
    )
    c = TestClient(
        build_web_app(make_config(), None, client=client), raise_server_exceptions=False
    )
    c.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    r = c.get("/api/v1/conversations")
    assert r.status_code == 200
    body = r.json()
    assert body["items"][0]["id"] == "c1"
    assert body["items"][0]["status"] == "running"
    assert body["items"][1]["state_label"] == "منتهي"
    assert BOT_TOKEN not in r.text


def test_conversation_detail_returns_exchange():
    client = FakeClient(
        convs={"c1": {"id": "c1", "title": "T", "execution_status": "running"}},
        exchange=("مرحبا", "أهلاً"),
    )
    c = TestClient(build_web_app(make_config(), None, client=client), raise_server_exceptions=False)
    c.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    r = c.get("/api/v1/conversations/c1")
    assert r.status_code == 200
    assert r.json()["last_prompt"] == "مرحبا"
    assert r.json()["last_reply"] == "أهلاً"


def test_conversation_not_found_404():
    client = FakeClient(convs={})
    c = TestClient(build_web_app(make_config(), None, client=client), raise_server_exceptions=False)
    c.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    assert c.get("/api/v1/conversations/missing").status_code == 404


def test_send_prompt_queues_and_wakes_worker():
    db = FakeDb()
    worker = FakeWorker()
    app = FakeApplication(outbox_worker=worker)
    c = TestClient(
        build_web_app(make_config(), db, client=FakeClient(), application=app),
        raise_server_exceptions=False,
    )
    c.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    r = c.post(
        "/api/v1/conversations/c1/prompt",
        json={"text": "اعمل حاجة"},
        headers={"origin": ORIGIN},
    )
    assert r.status_code == 200 and r.json()["queued"] is True
    assert [(i["cid"], i["chat_id"], i["text"]) for i in db.outbox] == [("c1", OWNER, "اعمل حاجة")]
    assert worker.woken == 1


def test_send_prompt_rejects_empty_text():
    c = TestClient(build_web_app(make_config(), FakeDb(), client=FakeClient()),
                   raise_server_exceptions=False)
    c.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    r = c.post("/api/v1/conversations/c1/prompt", json={"text": "   "}, headers={"origin": ORIGIN})
    assert r.status_code == 400


def test_watch_and_unwatch(monkeypatch):
    # نرجّع الميزة مؤقتًا لاختبار المسار الحقيقي (القرار 4 بيخفيها افتراضيًا).
    monkeypatch.setattr("bot.features.DEFERRED_FEATURES_HIDDEN", False)
    db = FakeDb()
    client = FakeClient(convs={"c1": {"id": "c1", "title": "T", "execution_status": "running"}})
    c = TestClient(build_web_app(make_config(), db, client=client), raise_server_exceptions=False)
    c.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    r = c.post("/api/v1/conversations/c1/watch", headers={"origin": ORIGIN})
    assert r.status_code == 200 and "c1" in db.watched
    r = c.delete("/api/v1/conversations/c1/watch", headers={"origin": ORIGIN})
    assert r.status_code == 200 and "c1" not in db.watched


def test_watches_hidden_by_default():
    """القرار 4: المتابعات مخفية ⇒ endpoints المتابعة ترجّع 404 في الـ Mini App كمان."""
    db = FakeDb()
    client = FakeClient(convs={"c1": {"id": "c1", "title": "T", "execution_status": "running"}})
    c = TestClient(build_web_app(make_config(), db, client=client), raise_server_exceptions=False)
    c.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    assert c.get("/api/v1/watches").status_code == 404
    assert c.post("/api/v1/conversations/c1/watch", headers={"origin": ORIGIN}).status_code == 404
    assert c.delete("/api/v1/conversations/c1/watch", headers={"origin": ORIGIN}).status_code == 404


def test_create_chat_queues_and_wakes_worker():
    db = FakeDb()
    worker = FakeWorker()
    app = FakeApplication(creation_worker=worker)
    c = TestClient(
        build_web_app(make_config(), db, client=FakeClient(), application=app),
        raise_server_exceptions=False,
    )
    c.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    r = c.post(
        "/api/v1/chats",
        json={"repository": "owner/repo", "text": "ابدأ"},
        headers={"origin": ORIGIN},
    )
    assert r.status_code == 200 and r.json()["queued"] is True
    assert [(j["chat_id"], j["repo"], j["text"]) for j in db.creation] == [(OWNER, "owner/repo", "ابدأ")]
    assert worker.woken == 1


def test_create_chat_rejects_bad_repository():
    c = TestClient(build_web_app(make_config(), FakeDb(), client=FakeClient()),
                   raise_server_exceptions=False)
    c.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    for bad in ("justname", "a/b/c", "", "a b/c"):
        r = c.post("/api/v1/chats", json={"repository": bad, "text": "x"}, headers={"origin": ORIGIN})
        assert r.status_code == 400


def test_repositories_listed():
    client = FakeClient(repos=[{"full_name": "o/r", "private": True}])
    c = TestClient(build_web_app(make_config(), None, client=client), raise_server_exceptions=False)
    c.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    r = c.get("/api/v1/repositories")
    assert r.status_code == 200
    assert r.json()["items"][0]["full_name"] == "o/r"


def test_watches_listed_from_db(monkeypatch):
    monkeypatch.setattr("bot.features.DEFERRED_FEATURES_HIDDEN", False)
    db = FakeDb()
    db.watched["c1"] = {"id": "c1", "title": "T", "last_state": "running", "added_at": "2026"}
    c = TestClient(build_web_app(make_config(), db, client=FakeClient()), raise_server_exceptions=False)
    c.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    r = c.get("/api/v1/watches")
    assert r.status_code == 200 and r.json()["items"][0]["id"] == "c1"


def test_unauthenticated_feature_endpoints_401():
    c = TestClient(build_web_app(make_config(), FakeDb(), client=FakeClient()),
                   raise_server_exceptions=False)
    for path in ("/api/v1/conversations", "/api/v1/watches", "/api/v1/repositories"):
        assert c.get(path).status_code == 401


def test_forbidden_user_session_cannot_reach_features():
    """مستخدم غير مسموح ما بياخدش جلسة أصلاً (auth بيفشل 403 بدون كوكي)."""
    c = TestClient(build_web_app(make_config(), FakeDb(), client=FakeClient()),
                   raise_server_exceptions=False)
    r = c.post("/api/v1/auth", json={"initData": make_init_data(OTHER)})
    assert r.status_code == 403
    assert COOKIE_NAME not in r.headers.get("set-cookie", "")


def test_stale_forbidden_session_is_revoked_and_blocked():
    """لو جلسة موجودة لمستخدم مش مسموح (مثلاً اتشال من القايمة)، الخدمة ترفضها وتبطلها."""
    cfg = make_config()
    app = MiniApp(cfg, FakeDb(), client=FakeClient())
    session = app.sessions.create(OTHER)
    client = TestClient(app.router, raise_server_exceptions=False)
    client.cookies.set(COOKIE_NAME, session.token)
    r = client.get("/api/v1/app/bootstrap")
    assert r.status_code == 403
    assert app.sessions.get(session.token) is None  # الجلسة اتبطلت
