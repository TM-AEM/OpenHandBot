"""اختبارات OHB2-07: idempotency + حالات العملية + الاستعلام بعد نتيجة غامضة.

بتستخدم قاعدة البيانات الحقيقية (Database) لمسار الصندوق/الإنشاء، وتطبيق الـ API
الحقيقي مع عميل OpenHands وهمي. الهدف: إثبات إن double-tap/إعادة المحاولة ما بتعملش
برومت مكرّر أو شات مكرّر، وإن الحالة (pending/accepted/failed/ambiguous) بتُعرض بأمان.
"""
from __future__ import annotations

from starlette.testclient import TestClient

from bot.config import Config
from bot.db import Database
from bot.web import build_web_app
from tests._miniapp_helpers import BOT_TOKEN, make_init_data

OWNER = 555
ORIGIN = "https://app.test"


class FakeClient:
    def __init__(self, convs=None) -> None:
        self.convs = convs or {}

    async def get_conversations(self, ids):
        return [self.convs[i] for i in ids if i in self.convs]

    async def get_last_exchange(self, conversation_id):
        return (None, None)


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


# ------------------------------------------------ DB idempotency (real DB)
def test_outbox_same_ref_returns_same_row(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    a = db.add_or_group_outbox("c1", 1, "برومت", "2026-01-01T00:00:00+00:00", client_ref="r1")
    # نافذة كبيرة عن قصد: حتى مع التجميع، نفس المعرّف مايعملش سجل جديد.
    b = db.add_or_group_outbox("c1", 1, "برومت", "2026-01-01T00:00:00+00:00", client_ref="r1")
    assert a == b
    assert db.count_outbox("pending") == 1


def test_outbox_different_ref_creates_new_row(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    a = db.add_or_group_outbox("c1", 1, "أ", "2026-01-01T00:00:00+00:00", client_ref="r1")
    b = db.add_or_group_outbox("c1", 1, "ب", "2026-01-01T00:00:00+00:00", client_ref="r2")
    assert a != b
    assert db.count_outbox("pending") == 2


def test_outbox_no_ref_keeps_grouping_behavior(tmp_path):
    """من غير معرّف عملية، سلوك التجميع الأصلي مايتغيّرش (توافق خلفي)."""
    db = Database(str(tmp_path / "d.sqlite3"))
    a = db.add_or_group_outbox("c1", 1, "أ", "2026-01-01T00:00:00+00:00")
    b = db.add_or_group_outbox("c1", 1, "ب", "2026-01-01T00:00:00+00:00")
    assert a == b  # اتجمّعوا في سجل واحد
    assert db.get_outbox(a).text == "أ\nب"


def test_find_outbox_by_ref(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    oid = db.add_or_group_outbox("c1", 1, "x", "t", client_ref="r1")
    assert db.find_outbox_by_ref("c1", 1, "r1").id == oid
    assert db.find_outbox_by_ref("c1", 1, "nope") is None


def test_creation_same_ref_returns_same_row(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    a = db.add_creation_job(1, "o/r", "ابدأ", "t", client_ref="r1")
    b = db.add_creation_job(1, "o/r", "ابدأ", "t", client_ref="r1")
    assert a == b
    assert db.count_creation_jobs("pending") == 1


def test_creation_different_ref_creates_new_row(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    a = db.add_creation_job(1, "o/r", "أ", "t", client_ref="r1")
    b = db.add_creation_job(1, "o/r", "ب", "t", client_ref="r2")
    assert a != b
    assert db.count_creation_jobs("pending") == 2


def test_find_creation_by_ref(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(1, "o/r", "x", "t", client_ref="r1")
    assert db.find_creation_job_by_ref(1, "r1").id == jid
    assert db.find_creation_job_by_ref(1, "nope") is None


def test_migration_adds_client_ref_to_old_db(tmp_path):
    """قاعدة قديمة من غير عمود client_ref ⇒ يتضاف من غير فقد بيانات."""
    import sqlite3

    path = str(tmp_path / "old.sqlite3")
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE watched (conversation_id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '',"
        " last_state TEXT, chat_id INTEGER);"
        "CREATE TABLE user_state (telegram_id INTEGER PRIMARY KEY, awaiting_conversation_id TEXT,"
        " awaiting_kind TEXT);"
        "CREATE TABLE outbox (id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL,"
        " chat_id INTEGER NOT NULL, text TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',"
        " error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);"
    )
    conn.execute(
        "INSERT INTO outbox(conversation_id, chat_id, text, status, created_at, updated_at)"
        " VALUES('c1', 9, 'قديم', 'pending', 't', 't')"
    )
    conn.commit()
    conn.close()

    db = Database(path)
    item = db.get_outbox(1)
    assert item.text == "قديم"
    assert item.client_ref is None  # العمود الجديد اتضاف بقيمة NULL
    # نقدر نستخدم idempotency بعد الترقية.
    assert db.add_or_group_outbox("c1", 9, "جديد", "t", client_ref="r1") == 2


# ------------------------------------------------- API-level idempotency
def _authed(tmp_path, **over):
    kwargs = over.pop("_kwargs", {})
    client = TestClient(build_web_app(make_config(tmp_path, **over), **kwargs), raise_server_exceptions=False)
    client.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    return client


def test_prompt_duplicate_ref_does_not_duplicate(tmp_path):
    """double-tap: نفس client_ref مرتين ⇒ سجل صندوق واحد بس."""
    db = Database(str(tmp_path / "d.sqlite3"))
    c = _authed(tmp_path, _kwargs={"db": db, "client": FakeClient()})
    body = {"text": "اعمل حاجة", "client_ref": "ref-abc"}
    r1 = c.post("/api/v1/conversations/c1/prompt", json=body, headers={"origin": ORIGIN})
    r2 = c.post("/api/v1/conversations/c1/prompt", json=body, headers={"origin": ORIGIN})
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["outbox_id"] == r2.json()["outbox_id"]
    assert db.count_outbox("pending") == 1
    assert r1.json()["operation"]["state"] == "pending"
    assert "text" not in r1.json()["operation"]  # مفيش نص البرومت في DTO الحالة


def test_create_chat_duplicate_ref_does_not_duplicate(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    c = _authed(tmp_path, _kwargs={"db": db, "client": FakeClient()})
    body = {"repository": "o/r", "text": "ابدأ", "client_ref": "ref-1"}
    r1 = c.post("/api/v1/chats", json=body, headers={"origin": ORIGIN})
    r2 = c.post("/api/v1/chats", json=body, headers={"origin": ORIGIN})
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["job_id"] == r2.json()["job_id"]
    assert db.count_creation_jobs("pending") == 1


# -------------------------------------------- operation status transitions
def test_outbox_operation_states(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    c = _authed(tmp_path, _kwargs={"db": db, "client": FakeClient()})
    oid = db.add_or_group_outbox("c1", OWNER, "x", "t", client_ref="r1")
    # pending
    r = c.get(f"/api/v1/operations/outbox?id={oid}")
    assert r.status_code == 200 and r.json()["state"] == "pending"
    # accepted
    db.set_outbox_status(oid, "sent", "t2")
    assert c.get(f"/api/v1/operations/outbox?id={oid}").json()["state"] == "accepted"
    # ambiguous
    db.set_outbox_status(oid, "unknown", "t3")
    assert c.get(f"/api/v1/operations/outbox?id={oid}").json()["state"] == "ambiguous"
    # failed
    db.set_outbox_status(oid, "failed", "t4")
    assert c.get(f"/api/v1/operations/outbox?id={oid}").json()["state"] == "failed"


def test_creation_operation_states_and_conversation_id(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    c = _authed(tmp_path, _kwargs={"db": db, "client": FakeClient()})
    jid = db.add_creation_job(OWNER, "o/r", "x", "t", client_ref="r1")
    r = c.get(f"/api/v1/operations/creation?id={jid}")
    assert r.status_code == 200 and r.json()["state"] == "pending"
    db.set_creation_done(jid, "t2", "conv-9")
    body = c.get(f"/api/v1/operations/creation?id={jid}").json()
    assert body["state"] == "accepted" and body["conversation_id"] == "conv-9"


def test_operation_lookup_by_client_ref(tmp_path):
    """بعد نتيجة غامضة: نلاقي العملية بمعرّفها من غير ما نعرف الـ id."""
    db = Database(str(tmp_path / "d.sqlite3"))
    c = _authed(tmp_path, _kwargs={"db": db, "client": FakeClient()})
    db.add_or_group_outbox("c1", OWNER, "x", "t", client_ref="ref-7")
    r = c.get("/api/v1/operations/outbox?conversation_id=c1&client_ref=ref-7")
    assert r.status_code == 200 and r.json()["state"] == "pending"
    jid = db.add_creation_job(OWNER, "o/r", "x", "t", client_ref="cref-7")
    r = c.get("/api/v1/operations/creation?client_ref=cref-7")
    assert r.status_code == 200 and r.json()["id"] == jid


def test_operation_lookup_unknown_ref_404(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    c = _authed(tmp_path, _kwargs={"db": db, "client": FakeClient()})
    assert c.get("/api/v1/operations/outbox?conversation_id=c1&client_ref=none").status_code == 404
    assert c.get("/api/v1/operations/creation?client_ref=none").status_code == 404


def test_operation_lookup_requires_id_or_ref(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    c = _authed(tmp_path, _kwargs={"db": db, "client": FakeClient()})
    assert c.get("/api/v1/operations/outbox").status_code == 400
    assert c.get("/api/v1/operations/creation").status_code == 400
    assert c.get("/api/v1/operations/outbox?id=abc").status_code == 400


def test_operation_endpoints_require_auth(tmp_path):
    c = TestClient(
        build_web_app(make_config(tmp_path), db=Database(str(tmp_path / "d.sqlite3"))),
        raise_server_exceptions=False,
    )
    assert c.get("/api/v1/operations/outbox?id=1").status_code == 401
    assert c.get("/api/v1/operations/creation?id=1").status_code == 401


def test_prompt_invalid_client_ref_rejected(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    c = _authed(tmp_path, _kwargs={"db": db, "client": FakeClient()})
    bad = "x" * 100  # أطول من الحد
    r = c.post(
        "/api/v1/conversations/c1/prompt",
        json={"text": "ن", "client_ref": bad},
        headers={"origin": ORIGIN},
    )
    assert r.status_code == 400
