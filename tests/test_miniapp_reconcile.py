"""اختبارات OHB2-09-05: تسوية الصندوق يدويًا (parity مع أوامر البوت).

بتستخدم قاعدة البيانات الحقيقية وتطبيق الـ API الحقيقي. الهدف: إثبات إن
`discard`/`mark_sent` بيعملوا **نفس** اللي أوامر البوت بتعمله، وإن التحويلات
نهائية (at-most-once محفوظ)، وإن الردود منظّمة وآمنة.
"""
from __future__ import annotations

from starlette.testclient import TestClient

from bot.config import Config
from bot.db import Database
from bot.web import build_web_app
from tests._miniapp_helpers import BOT_TOKEN, make_init_data

OWNER = 555
ORIGIN = "https://app.test"
RECONCILE = "/api/v1/operations/outbox/reconcile"


class FakeClient:
    async def get_conversations(self, ids):
        return []

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


def _authed(tmp_path, db):
    c = TestClient(
        build_web_app(make_config(tmp_path), db=db, client=FakeClient()),
        raise_server_exceptions=False,
    )
    c.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    return c


def _post(c, body):
    return c.post(RECONCILE, json=body, headers={"origin": ORIGIN})


def test_reconcile_requires_auth(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    c = TestClient(
        build_web_app(make_config(tmp_path), db=db, client=FakeClient()),
        raise_server_exceptions=False,
    )
    assert _post(c, {"id": 1, "action": "discard"}).status_code == 401


def test_discard_pending_marks_discarded_terminal(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    oid = db.add_or_group_outbox("c1", OWNER, "x", "t", client_ref="r1")
    c = _authed(tmp_path, db)
    r = _post(c, {"id": oid, "action": "discard"})
    assert r.status_code == 200 and r.json()["state"] == "failed"
    assert db.get_outbox(oid).status == "discarded"


def test_discard_already_terminal_conflicts(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    oid = db.add_or_group_outbox("c1", OWNER, "x", "t", client_ref="r1")
    db.set_outbox_status(oid, "sent", "t2")
    c = _authed(tmp_path, db)
    r = _post(c, {"id": oid, "action": "discard"})
    assert r.status_code == 409 and r.json()["error"] == "already_terminal"
    assert db.get_outbox(oid).status == "sent"  # مفيش تغيير


def test_mark_sent_only_from_unknown(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    oid = db.add_or_group_outbox("c1", OWNER, "x", "t", client_ref="r1")
    db.set_outbox_status(oid, "unknown", "t2")
    c = _authed(tmp_path, db)
    r = _post(c, {"id": oid, "action": "mark_sent"})
    assert r.status_code == 200 and r.json()["state"] == "accepted"
    assert db.get_outbox(oid).status == "sent"


def test_mark_sent_pending_conflicts(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    oid = db.add_or_group_outbox("c1", OWNER, "x", "t", client_ref="r1")
    c = _authed(tmp_path, db)
    r = _post(c, {"id": oid, "action": "mark_sent"})
    assert r.status_code == 409 and r.json()["error"] == "invalid_state"
    assert db.get_outbox(oid).status == "pending"  # ما اتغيّرش


def test_mark_sent_when_already_sent_is_idempotent(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    oid = db.add_or_group_outbox("c1", OWNER, "x", "t", client_ref="r1")
    db.set_outbox_status(oid, "sent", "t2")
    c = _authed(tmp_path, db)
    r = _post(c, {"id": oid, "action": "mark_sent"})
    assert r.status_code == 200 and r.json()["state"] == "accepted"


def test_discard_is_terminal_and_cannot_go_pending(tmp_path):
    """at-most-once: بعد الشطب مستحيل يرجع pending ⇒ مفيش إرسال تلقائي."""
    db = Database(str(tmp_path / "d.sqlite3"))
    oid = db.add_or_group_outbox("c1", OWNER, "x", "t", client_ref="r1")
    c = _authed(tmp_path, db)
    assert _post(c, {"id": oid, "action": "discard"}).status_code == 200
    assert db.count_outbox("pending") == 0
    # محاولة تانية ⇒ 409، والحالة تفضل نهائية.
    assert _post(c, {"id": oid, "action": "discard"}).status_code == 409


def test_unknown_action_rejected(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    oid = db.add_or_group_outbox("c1", OWNER, "x", "t", client_ref="r1")
    c = _authed(tmp_path, db)
    r = _post(c, {"id": oid, "action": "delete"})
    assert r.status_code == 400 and r.json()["error"] == "bad_request"


def test_missing_or_bad_id_rejected(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    c = _authed(tmp_path, db)
    assert _post(c, {"action": "discard"}).status_code == 400
    assert _post(c, {"id": "abc", "action": "discard"}).status_code == 400


def test_missing_operation_404(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    c = _authed(tmp_path, db)
    assert _post(c, {"id": 999, "action": "discard"}).status_code == 404


def test_reconcile_requires_origin(tmp_path):
    """POST بيغيّر حالة ⇒ لازم same-origin (حماية CSRF)."""
    db = Database(str(tmp_path / "d.sqlite3"))
    oid = db.add_or_group_outbox("c1", OWNER, "x", "t", client_ref="r1")
    c = _authed(tmp_path, db)
    r = c.post(RECONCILE, json={"id": oid, "action": "discard"})  # بدون origin
    assert r.status_code == 403 and r.json()["error"] == "bad_origin"


def test_reconcile_dto_has_no_prompt_text(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    oid = db.add_or_group_outbox("c1", OWNER, "سر خطير", "t", client_ref="r1")
    db.set_outbox_status(oid, "unknown", "t2")
    c = _authed(tmp_path, db)
    r = _post(c, {"id": oid, "action": "mark_sent"})
    assert "سر خطير" not in r.text and BOT_TOKEN not in r.text


# =============================== OHB2-09-05-R1: atomic (race-free) state transitions
def test_set_outbox_status_if_in_is_compare_and_set(tmp_path):
    """CAS ذرّي: الشرط جوّه الـ UPDATE ⇒ حالة مش مسموحة ⇒ مفيش تغيير (rowcount=0)."""
    db = Database(str(tmp_path / "d.sqlite3"))
    oid = db.add_or_group_outbox("c1", OWNER, "x", "t", client_ref="r1")
    db.set_outbox_status(oid, "unknown", "t1")
    assert db.set_outbox_status_if_in(oid, "sent", "t2", {"unknown"}, "ok") is True
    assert db.get_outbox(oid).status == "sent"
    assert db.set_outbox_status_if_in(oid, "discarded", "t3", {"unknown"}, "no") is False
    assert db.get_outbox(oid).status == "sent"


def test_reconcile_discard_uses_atomic_cas_under_concurrency(tmp_path):
    """شطبان متزامنان على 'pending' ⇒ تغيير واحد فعلي، والتاني 409 (مفيش كتابة مزدوجة).

    بنستخدم **اتصال SQLite منفصل لكل ثريد** على نفس الملف (الاتصالات بتتبني في المين
    ثريد قبل ما الثريدات تبدأ). ده أقوى إثبات للـ CAS: القرار والكتابة في جملة SQL واحدة
    على مستوى القاعدة. اتصال واحد مشترك بين ثريدات مش آمن في sqlite3 (InterfaceError:
    bad parameter or other API misuse)، والإنتاج نفسه بيشتغل على event loop واحد.
    """
    import threading

    path = str(tmp_path / "d.sqlite3")
    db = Database(path)
    oid = db.add_or_group_outbox("c1", OWNER, "x", "t", client_ref="r1")
    db2 = Database(path)  # اتصال تاني مستقل على نفس الملف
    c1 = _authed(tmp_path, db)
    c2 = _authed(tmp_path, db2)
    barrier = threading.Barrier(2)
    results = []

    def worker(c):
        barrier.wait()
        results.append(_post(c, {"id": oid, "action": "discard"}).status_code)

    ts = [threading.Thread(target=worker, args=(c1,)), threading.Thread(target=worker, args=(c2,))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert sorted(results) == [200, 409]
    assert db.get_outbox(oid).status == "discarded"


def test_reconcile_mark_sent_never_clobbers_a_discard(tmp_path):
    """سباق discard/mark_sent: اللي يخسر مايقدرش يقلب النتيجة (مفيش read-then-write).

    زي فوق: اتصال SQLite مستقل لكل ثريد عشان نختبر الـ CAS عبر اتصالين حقيقيين.
    """
    import threading

    path = str(tmp_path / "d.sqlite3")
    db = Database(path)
    oid = db.add_or_group_outbox("c1", OWNER, "x", "t", client_ref="r1")
    db.set_outbox_status(oid, "unknown", "t1")
    db2 = Database(path)  # اتصال تاني مستقل
    c1 = _authed(tmp_path, db)
    c2 = _authed(tmp_path, db2)
    barrier = threading.Barrier(2)
    codes = {}

    def worker(c, action):
        barrier.wait()
        codes[action] = _post(c, {"id": oid, "action": action}).status_code

    ts = [
        threading.Thread(target=worker, args=(c1, "discard")),
        threading.Thread(target=worker, args=(c2, "mark_sent")),
    ]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    final = db.get_outbox(oid).status
    assert final in ("discarded", "sent")
    assert 200 in codes.values()
    if final == "discarded":
        assert codes.get("mark_sent") == 409
    else:
        assert codes.get("discard") == 409
