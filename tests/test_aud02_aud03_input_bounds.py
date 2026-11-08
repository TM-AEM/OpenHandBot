"""AUD-02/AUD-03: حدود الأعداد الصحيحة + حقول JSON غير النصية ⇒ خطأ منظّم (400) مش 500.

AUD-02: أي رقم يتحوّل لـ SQLite INTEGER (معرّف/صفحة) لازم يتفحص قبل الـ binding،
وإلا OverflowError ⇒ 500. نرفضه بـ 400.
AUD-03: أي حقل JSON (نص/إجراء/مستودع/معرّف) ممكن يكون رقم/منطقي/قائمة/كائن/null،
مش نص دايمًا. `(value or "").strip()` على قيمة غير نصية يضرب AttributeError ⇒ 500.

كل الاختبارات بقاعدة SQLite حقيقية + تطبيق API حقيقي + عميل وهمي (مفيش شبكة).
"""
from __future__ import annotations

from starlette.testclient import TestClient

from bot.config import Config
from bot.db import MAX_SQLITE_INT, Database
from bot.web import build_web_app
from tests._miniapp_helpers import BOT_TOKEN, make_init_data

OWNER = 555
ORIGIN = "https://app.test"
OWNER_UUID = "owner-uuid-123"
HUGE = 10**25  # أكبر من 64-bit ⇒ OverflowError قبل الإصلاح


class FakeClient:
    def __init__(self, convs=None) -> None:
        self.convs = convs or {}

    async def get_conversations(self, ids):
        return [
            {**self.convs[i], "created_by_user_id": self.convs[i].get("created_by_user_id", OWNER_UUID)}
            for i in ids
            if i in self.convs
        ]

    async def get_current_user(self):
        return {"id": OWNER_UUID}

    async def get_last_exchange(self, conversation_id):
        return (None, None)

    async def search_repositories(self, query="", limit=100):
        return []


def make_config(tmp_path, **over) -> Config:
    base = dict(
        telegram_bot_token=BOT_TOKEN,
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({OWNER}),
        owner_id=OWNER,
        db_path=str(tmp_path / "t.sqlite3"),
        mini_app_cookie_secure=False,
        mini_app_allowed_origins=frozenset({ORIGIN}),
    )
    base.update(over)
    return Config(**base)


def authed(tmp_path, db):
    client = TestClient(
        build_web_app(make_config(tmp_path), db, client=FakeClient(convs={"c1": {"id": "c1"}})),
        raise_server_exceptions=False,
    )
    assert client.post("/api/v1/auth", json={"initData": make_init_data(OWNER)}).status_code == 200
    return client


def _db(tmp_path):
    return Database(str(tmp_path / "ops.sqlite3"))


# --------------------------------------------------------- AUD-02: معرّفات ضخمة
def test_outbox_huge_id_is_400(tmp_path):
    db = _db(tmp_path)
    c = authed(tmp_path, db)
    for bad in (HUGE, MAX_SQLITE_INT + 1):
        assert c.get(f"/api/v1/operations/outbox?id={bad}").status_code == 400, bad


def test_outbox_negative_id_is_400(tmp_path):
    db = _db(tmp_path)
    c = authed(tmp_path, db)
    assert c.get("/api/v1/operations/outbox?id=-5").status_code == 400


def test_creation_huge_and_negative_id_is_400(tmp_path):
    db = _db(tmp_path)
    c = authed(tmp_path, db)
    assert c.get(f"/api/v1/operations/creation?id={HUGE}").status_code == 400
    assert c.get("/api/v1/operations/creation?id=-5").status_code == 400


def test_outbox_reconcile_huge_id_is_400(tmp_path):
    db = _db(tmp_path)
    c = authed(tmp_path, db)
    r = c.post(
        "/api/v1/operations/outbox/reconcile",
        json={"id": HUGE, "action": "discard"},
        headers={"origin": ORIGIN},
    )
    assert r.status_code == 400


def test_creation_reconcile_huge_id_is_400(tmp_path):
    db = _db(tmp_path)
    c = authed(tmp_path, db)
    r = c.post(
        "/api/v1/operations/creation/reconcile",
        json={"id": HUGE, "action": "cancel"},
        headers={"origin": ORIGIN},
    )
    assert r.status_code == 400


def test_notification_huge_id_is_400_on_all_mutations(tmp_path):
    db = _db(tmp_path)
    db.add_inbox_item("c1", "t", "terminal", "m", "t0")
    c = authed(tmp_path, db)
    for bad in (HUGE, MAX_SQLITE_INT + 1):
        assert c.post(f"/api/v1/notifications/{bad}/read", headers={"origin": ORIGIN}).status_code == 400
        assert c.post(f"/api/v1/notifications/{bad}/archive", json={}, headers={"origin": ORIGIN}).status_code == 400
        assert c.post(f"/api/v1/notifications/{bad}/unarchive", json={}, headers={"origin": ORIGIN}).status_code == 400
        assert c.delete(f"/api/v1/notifications/{bad}", headers={"origin": ORIGIN}).status_code == 400
    assert db.count_inbox() == 1  # مفيش صف اتأثّر


def test_valid_max_sqlite_int_id_is_not_500(tmp_path):
    """معرّف صالح (MAX_SQLITE_INT) ما يضربش 500 — بس 404 (مفيش صف بالمعرّف ده)."""
    db = _db(tmp_path)
    c = authed(tmp_path, db)
    r = c.get(f"/api/v1/operations/outbox?id={MAX_SQLITE_INT}")
    assert r.status_code == 404, r.text


# --------------------------------------------------------- AUD-03: حقول JSON غير نصية
def test_create_chat_non_string_text_is_400(tmp_path):
    db = _db(tmp_path)
    c = authed(tmp_path, db)
    for bad in (5, 1.5, True, [1, 2], {"a": 1}):
        r = c.post("/api/v1/chats", json={"text": bad}, headers={"origin": ORIGIN})
        assert r.status_code == 400, f"text={bad!r} ⇒ {r.status_code}"


def test_create_chat_non_string_repository_is_400(tmp_path):
    db = _db(tmp_path)
    c = authed(tmp_path, db)
    for bad in (5, [1], {"a": 1}, True):
        r = c.post(
            "/api/v1/chats", json={"repository": bad, "text": "hi"}, headers={"origin": ORIGIN}
        )
        assert r.status_code == 400, f"repository={bad!r} ⇒ {r.status_code}"


def test_create_chat_non_string_client_ref_is_400(tmp_path):
    db = _db(tmp_path)
    c = authed(tmp_path, db)
    r = c.post(
        "/api/v1/chats", json={"text": "hi", "client_ref": 42}, headers={"origin": ORIGIN}
    )
    assert r.status_code == 400


def test_create_chat_null_repository_is_allowed(tmp_path):
    """null مستودع = شات بدون مستودع (سلوك قائم) ⇒ مش 500."""
    db = _db(tmp_path)
    c = authed(tmp_path, db)
    r = c.post(
        "/api/v1/chats", json={"repository": None, "text": "hi"}, headers={"origin": ORIGIN}
    )
    assert r.status_code == 200, r.text


def test_prompt_non_string_text_is_400(tmp_path):
    db = _db(tmp_path)
    c = authed(tmp_path, db)
    for bad in (5, [1], {"x": 1}, True):
        r = c.post(
            "/api/v1/conversations/c1/prompt", json={"text": bad}, headers={"origin": ORIGIN}
        )
        assert r.status_code == 400, f"text={bad!r} ⇒ {r.status_code}"


def test_associate_repository_non_string_is_400(tmp_path):
    db = _db(tmp_path)
    c = authed(tmp_path, db)
    for bad in (5, [1], {"x": 1}, True):
        r = c.patch(
            "/api/v1/conversations/c1/repository",
            json={"repository": bad},
            headers={"origin": ORIGIN},
        )
        assert r.status_code == 400, f"repository={bad!r} ⇒ {r.status_code}"


def test_outbox_reconcile_non_string_action_is_400(tmp_path):
    db = _db(tmp_path)
    oid = db.add_outbox("c1", 1, "x", "t0")
    c = authed(tmp_path, db)
    for bad in (5, 1.5, True, [1], {"a": 1}, None):
        r = c.post(
            "/api/v1/operations/outbox/reconcile",
            json={"id": oid, "action": bad},
            headers={"origin": ORIGIN},
        )
        assert r.status_code == 400, f"action={bad!r} ⇒ {r.status_code}"


def test_creation_reconcile_non_string_action_is_400(tmp_path):
    db = _db(tmp_path)
    jid = db.add_creation_job(OWNER, "repo", "hi", "2026-01-01T00:00:00+00:00")
    c = authed(tmp_path, db)
    for bad in (5, [1], {"a": 1}, None, True):
        r = c.post(
            "/api/v1/operations/creation/reconcile",
            json={"id": jid, "action": bad},
            headers={"origin": ORIGIN},
        )
        assert r.status_code == 400, f"action={bad!r} ⇒ {r.status_code}"


def test_malformed_json_body_is_400(tmp_path):
    db = _db(tmp_path)
    c = authed(tmp_path, db)
    for path in ("/api/v1/chats", "/api/v1/conversations/c1/prompt"):
        r = c.post(path, content=b"{not json", headers={"origin": ORIGIN, "content-type": "application/json"})
        assert r.status_code == 400, f"{path} ⇒ {r.status_code}"


def test_json_array_body_is_400(tmp_path):
    """جسم JSON من نوع مصفوفة (مش كائن) ⇒ 400 منظّم، مش 500."""
    db = _db(tmp_path)
    c = authed(tmp_path, db)
    r = c.post("/api/v1/chats", json=[1, 2, 3], headers={"origin": ORIGIN})
    assert r.status_code == 400
