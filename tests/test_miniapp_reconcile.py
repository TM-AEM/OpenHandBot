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
    assert r.status_code == 200 and r.json()["state"] == "discarded"
    assert r.json()["cancellation"] == "discarded"
    assert db.get_outbox(oid).status == "discarded"


def test_discard_after_send_may_have_started_not_confirmed(tmp_path):
    # OHB2-N10-28C: لو الـ POST ممكن يكون بدأ (sending/unknown)، ما بندّعيش إلغاء —
    # بنرجّع الحالة الحالية + علامة not_confirmed، والقاعدة ماتتغيّرش.
    db = Database(str(tmp_path / "d.sqlite3"))
    oid = db.add_or_group_outbox("c1", OWNER, "x", "t", client_ref="r1")
    db.set_outbox_status(oid, "unknown", "t2")
    c = _authed(tmp_path, db)
    r = _post(c, {"id": oid, "action": "discard"})
    assert r.status_code == 200 and r.json()["state"] == "ambiguous"
    assert r.json()["cancellation"] == "not_confirmed"
    assert db.get_outbox(oid).status == "unknown"  # مفيش تغيير


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
    """سباق discard/mark_sent على سجل غامض (unknown): اللي ممكن يكون اتبعت مايتلغيش.

    OHB2-N10-28C: discard على سجل ممكن يكون بدأ الإرسال (unknown) **مش** بيلغيه.
    التزامن حقيقي (اتصال SQLite مستقل لكل ثريد)، فترتيب الوصول مش مضمون؛ والنتيجتين
    المشروعتين الاتنين مقبولتين:
    - mark_sent يسبق ⇒ unknown→sent؛ الشطب بعده على سجل نهائي ⇒ 409 already_terminal.
    - discard يسبق ⇒ لسه unknown ⇒ 200 not_confirmed (مفيش تغيير)؛ وبعدها mark_sent
      يحسمه sent.
    في الحالتين الحالة النهائية 'sent'، ومستحيل ترجع 'discarded' (سجل غامض مايتلغيش).
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
    results = {}

    def worker(c, action):
        barrier.wait()
        results[action] = _post(c, {"id": oid, "action": action})

    ts = [
        threading.Thread(target=worker, args=(c1, "discard")),
        threading.Thread(target=worker, args=(c2, "mark_sent")),
    ]
    for t in ts:
        t.start()
    for t in ts:
        t.join()

    # في كل الترتيبات المشروعة، mark_sent بيكسب في الآخر ⇒ الحالة النهائية 'sent'
    # ومستحيل تبقى 'discarded' (discard على سجل غامض مايغيّرش الحالة).
    assert db.get_outbox(oid).status == "sent"
    assert results["mark_sent"].status_code == 200
    assert results["mark_sent"].json()["state"] == "accepted"

    # النتيجة المشروعة الوحيدة للشطب على سجل غامض: 200 (not_confirmed، الشطب سبق
    # mark_sent) أو 409 (already_terminal، mark_sent سبق). أي حالة تانية = فشل.
    discard = results["discard"]
    if discard.status_code == 200:
        # الشطب سبق mark_sent: مفيش تغيير، ومفيش ادّعاء إلغاء وهمي.
        assert discard.json().get("cancellation") == "not_confirmed"
        assert discard.json()["state"] == "ambiguous"
    else:
        assert discard.status_code == 409
        assert discard.json()["error"] == "already_terminal"


# =============================== OHB2-PLAN-02: pending remote deletion list & reconcile
class _DelClient:
    def __init__(self, *, owner_uuid="owner-1", conv_owner="owner-1", exists=False, get_status=200):
        self.owner_uuid = owner_uuid
        self.conv_owner = conv_owner
        self.exists = exists
        self.get_status = get_status
        self.delete_calls = 0
        self.get_calls = 0

    async def get_current_user(self):
        return {"id": self.owner_uuid}

    async def get_conversations(self, ids):
        from bot.errors import ApiError

        self.get_calls += 1
        if self.get_status != 200:
            raise ApiError("upstream", self.get_status)
        if not self.exists:
            return []
        return [{"id": cid, "title": "t", "created_by_user_id": self.conv_owner} for cid in ids]

    async def conversation_exists(self, cid):
        from bot.errors import ApiError

        self.get_calls += 1
        if self.get_status != 200:
            raise ApiError("upstream", self.get_status)
        return self.exists

    async def delete_conversation(self, cid):
        self.delete_calls += 1
        return True


def _del_authed(tmp_path, db, client):
    c = TestClient(build_web_app(make_config(tmp_path), db=db, client=client), raise_server_exceptions=False)
    c.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    return c


def test_pending_deletions_list_auth_and_filtering(tmp_path):
    db = Database(str(tmp_path / "del_list.sqlite3"))
    unauthed = TestClient(build_web_app(make_config(tmp_path), db=db, client=_DelClient()))
    assert unauthed.get("/api/v1/operations/deletions/list").status_code == 401

    db.begin_remote_deletion("c_del", "2026-01-01T00:00:00Z")
    db.begin_remote_deletion("c_unc", "2026-01-02T00:00:00Z")
    db.set_remote_deletion_state("c_unc", db.REMOTE_UNCERTAIN, "2026-01-02T00:00:00Z")
    db.delete_conversation("c_done", "2026-01-03T00:00:00Z", remote_confirmed=True)
    db.delete_conversation("c_legacy", "2026-01-04T00:00:00Z", remote_confirmed=False)

    c = _del_authed(tmp_path, db, _DelClient())
    r = c.get("/api/v1/operations/deletions/list")
    assert r.status_code == 200
    items = r.json()["items"]
    assert [it["conversation_id"] for it in items] == ["c_unc", "c_del"]
    assert [it["state"] for it in items] == ["uncertain", "deleting"]


def test_deletion_reconcile_guards_and_validation(tmp_path):
    db = Database(str(tmp_path / "del_guard.sqlite3"))
    c = _del_authed(tmp_path, db, _DelClient())
    assert c.post("/api/v1/operations/deletions/reconcile", json={"conversation_id": "c1"}).status_code == 403
    assert c.post(
        "/api/v1/operations/deletions/reconcile",
        json={"conversation_id": "bad id!"},
        headers={"origin": ORIGIN},
    ).status_code == 400
    r409 = c.post(
        "/api/v1/operations/deletions/reconcile",
        json={"conversation_id": "c1"},
        headers={"origin": ORIGIN},
    )
    assert r409.status_code == 409 and r409.json()["error"] == "not_pending"


def test_deletion_reconcile_never_bypasses_owner_mismatch(tmp_path):
    db = Database(str(tmp_path / "del_owner.sqlite3"))
    db.begin_remote_deletion("c1", "2026-01-01T00:00:00Z")
    client = _DelClient(owner_uuid="owner-1", conv_owner="other-owner", exists=True)
    c = _del_authed(tmp_path, db, client)
    r = c.post(
        "/api/v1/operations/deletions/reconcile",
        json={"conversation_id": "c1"},
        headers={"origin": ORIGIN},
    )
    assert r.status_code == 403 and r.json()["error"] == "unauthorized"
    assert client.delete_calls == 0


def test_deletion_reconcile_absent_confirms_without_delete_call(tmp_path):
    db = Database(str(tmp_path / "del_absent.sqlite3"))
    db.add_watched("c1", "شات", chat_id=OWNER)
    db.begin_remote_deletion("c1", "2026-01-01T00:00:00Z")
    db.set_remote_deletion_state("c1", db.REMOTE_UNCERTAIN, "2026-01-01T00:00:00Z")
    client = _DelClient(exists=False)
    c = _del_authed(tmp_path, db, client)
    r = c.post(
        "/api/v1/operations/deletions/reconcile",
        json={"conversation_id": "c1"},
        headers={"origin": ORIGIN},
    )
    assert r.status_code == 200
    assert r.json()["deleted"] is True and r.json()["status"] == "deleted"
    assert client.delete_calls == 0
    assert db.remote_deletion_state("c1") == db.REMOTE_CONFIRMED
    assert c.get("/api/v1/operations/deletions/list").json()["items"] == []


def test_deletion_reconcile_present_restores_local_and_returns_502(tmp_path):
    db = Database(str(tmp_path / "del_present.sqlite3"))
    db.begin_remote_deletion("c1", "2026-01-01T00:00:00Z")
    client = _DelClient(exists=True)
    c = _del_authed(tmp_path, db, client)
    r = c.post(
        "/api/v1/operations/deletions/reconcile",
        json={"conversation_id": "c1"},
        headers={"origin": ORIGIN},
    )
    assert r.status_code == 502 and r.json()["error"] == "remote_delete_failed"
    assert client.delete_calls == 0
    assert db.is_deleted("c1") is False
    assert db.remote_deletion_state("c1") is None


def test_deletion_reconcile_upstream_error_returns_503_and_stays_uncertain(tmp_path):
    db = Database(str(tmp_path / "del_err.sqlite3"))
    db.begin_remote_deletion("c1", "2026-01-01T00:00:00Z")
    client = _DelClient(get_status=503)
    c = _del_authed(tmp_path, db, client)
    r = c.post(
        "/api/v1/operations/deletions/reconcile",
        json={"conversation_id": "c1"},
        headers={"origin": ORIGIN},
    )
    assert r.status_code == 503 and r.json()["error"] == "remote_delete_pending"
    assert client.delete_calls == 0
    assert db.remote_deletion_state("c1") == db.REMOTE_UNCERTAIN
    assert len(c.get("/api/v1/operations/deletions/list").json()["items"]) == 1


def test_delete_endpoint_retry_on_uncertain_when_upstream_gone_reconciles_no_delete(tmp_path):
    db = Database(str(tmp_path / "del_retry.sqlite3"))
    db.begin_remote_deletion("c1", "2026-01-01T00:00:00Z")
    db.set_remote_deletion_state("c1", db.REMOTE_UNCERTAIN, "2026-01-01T00:00:00Z")
    client = _DelClient(exists=False)
    c = _del_authed(tmp_path, db, client)
    r = c.delete("/api/v1/conversations/c1", headers={"origin": ORIGIN})
    assert r.status_code == 200 and r.json()["deleted"] is True
    assert client.delete_calls == 0
    assert db.remote_deletion_state("c1") == db.REMOTE_CONFIRMED
