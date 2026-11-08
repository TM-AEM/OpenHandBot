"""OHB2-PHASE1D — اختبارات رؤية/إلغاء/تسوية طلبات الشات الجديد في الـ Mini App.

بتستخدم قاعدة البيانات **الحقيقية** وتطبيق الـ API الحقيقي مع عميل OpenHands وهمي.
الهدف: إثبات نطاق المالك، وحدّ الإلغاء قبل الإرسال، وتسوية الغموض، ومنع أي إنشاء مكرّر.
"""
from __future__ import annotations

from starlette.testclient import TestClient

from bot.config import Config
from bot.db import Database
from bot.web import build_web_app
from tests._miniapp_helpers import BOT_TOKEN, make_init_data

OWNER = 555
OTHER = 777
ORIGIN = "https://app.test"
LIST = "/api/v1/operations/creation/list"
DETAIL = "/api/v1/operations/creation"
RECONCILE = "/api/v1/operations/creation/reconcile"


class FakeClient:
    """عميل وهمي — ما بيتنادىش خالص في مسارات القراءة/التسوية (مفيش POST بعيد)."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get_conversations(self, ids):
        self.calls.append("get_conversations")
        return []

    async def get_last_exchange(self, conversation_id):
        self.calls.append("get_last_exchange")
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


def _authed(tmp_path, db, client=None):
    c = TestClient(
        build_web_app(make_config(tmp_path), db=db, client=client or FakeClient()),
        raise_server_exceptions=False,
    )
    c.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    return c


def _post(c, body):
    return c.post(RECONCILE, json=body, headers={"origin": ORIGIN})


# ------------------------------------------------------------ visibility
def test_list_owner_scoped_excludes_other_users(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    mine = db.add_creation_job(OWNER, "o/mine", "a", "2026-01-01T00:00:00+00:00", client_ref="r1")
    db.add_creation_job(OTHER, "o/other", "b", "2026-01-02T00:00:00+00:00", client_ref="r2")
    c = _authed(tmp_path, db)
    body = c.get(LIST).json()
    ids = [it["id"] for it in body["items"]]
    assert ids == [mine]
    assert body["has_more"] is False


def test_list_requires_auth(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    c = TestClient(
        build_web_app(make_config(tmp_path), db=db, client=FakeClient()),
        raise_server_exceptions=False,
    )
    assert c.get(LIST).status_code == 401


def test_list_pagination_cannot_bypass_ownership(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    for i in range(12):
        db.add_creation_job(OWNER, "o/mine", f"t{i}", f"2026-01-{i+1:02d}T00:00:00+00:00", client_ref=f"r{i}")
    other_ids = set()
    for i in range(5):
        other_ids.add(db.add_creation_job(OTHER, "o/other", f"x{i}", "2026-02-01T00:00:00+00:00", client_ref=f"o{i}"))
    c = _authed(tmp_path, db)
    seen = []
    for page in (0, 1, 2):
        body = c.get(f"{LIST}?page={page}").json()
        seen.extend(it["id"] for it in body["items"])
    assert not (set(seen) & other_ids), "الترقيم مايقدّش يسرّب طلبات مستخدم تاني"
    assert len(seen) == 12


def test_detail_owner_scoped_other_user_404(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    jx = db.add_creation_job(OTHER, "o/other", "b", "2026-01-02T00:00:00+00:00", client_ref="r2")
    c = _authed(tmp_path, db)
    assert c.get(f"{DETAIL}?id={jx}").status_code == 404


def test_detail_unknown_job_404(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    c = _authed(tmp_path, db)
    assert c.get(f"{DETAIL}?id=99999").status_code == 404


def test_dto_exposes_no_sensitive_fields(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(OWNER, "o/r", "نص البرومت السري", "2026-01-01T00:00:00+00:00", client_ref="r1")
    c = _authed(tmp_path, db)
    body = c.get(f"{DETAIL}?id={jid}").json()
    assert "text" not in body and "client_ref" not in body
    assert "نص البرومت السري" not in str(body)
    # حقول آمنة مشتقّة على السيرفر موجودة.
    assert body["post_state"] == "not_started"
    assert body["cancellable"] is True and body["terminal"] is False


def test_dto_conversation_id_only_when_evidence(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(OWNER, "o/r", "x", "t", client_ref="r1")
    c = _authed(tmp_path, db)
    assert c.get(f"{DETAIL}?id={jid}").json()["conversation_id"] == ""
    db.set_creation_done(jid, "t2", "conv-9")
    body = c.get(f"{DETAIL}?id={jid}").json()
    assert body["conversation_id"] == "conv-9"
    assert body["state"] == "accepted" and body["terminal"] is True


# ------------------------------------------------------------ cancellation
def test_cancel_pending_succeeds_terminal(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(OWNER, "o/r", "x", "t", client_ref="r1")
    c = _authed(tmp_path, db)
    r = _post(c, {"id": jid, "action": "cancel"})
    assert r.status_code == 200
    assert r.json()["state"] == "discarded"
    assert r.json()["cancellation"] == "discarded"
    assert db.get_creation_job(jid).status == "discarded"


def test_cancel_claimed_succeeds(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(OWNER, "o/r", "x", "t", client_ref="r1")
    db.claim_creation_job("t1")  # pending ⇒ claimed
    c = _authed(tmp_path, db)
    r = _post(c, {"id": jid, "action": "cancel"})
    assert r.status_code == 200 and r.json()["state"] == "discarded"


def test_cancel_starting_not_confirmed_no_change(tmp_path):
    """الـ POST ممكن يكون بدأ ⇒ مفيش ادّعاء إلغاء والقاعدة ماتتغيّرش."""
    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(OWNER, "o/r", "x", "t", client_ref="r1")
    db.set_creation_status(jid, "starting", "t1")
    c = _authed(tmp_path, db)
    r = _post(c, {"id": jid, "action": "cancel"})
    assert r.status_code == 200
    assert r.json()["state"] == "pending" and r.json()["cancellation"] == "not_confirmed"
    assert db.get_creation_job(jid).status == "starting"  # مفيش تغيير


def test_cancel_unknown_not_confirmed_no_change(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(OWNER, "o/r", "x", "t", client_ref="r1")
    db.set_creation_status(jid, "unknown", "t1")
    c = _authed(tmp_path, db)
    r = _post(c, {"id": jid, "action": "cancel"})
    assert r.status_code == 200 and r.json()["cancellation"] == "not_confirmed"
    assert db.get_creation_job(jid).status == "unknown"


def test_cancel_terminal_states_conflict(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    c = _authed(tmp_path, db)
    for terminal in ("done", "failed", "discarded"):
        jid = db.add_creation_job(OWNER, "o/r", terminal, "t", client_ref=f"r-{terminal}")
        db.set_creation_status(jid, terminal, "t1")
        r = _post(c, {"id": jid, "action": "cancel"})
        assert r.status_code == 409 and r.json()["error"] == "already_terminal"
        assert db.get_creation_job(jid).status == terminal  # مفيش تغيير


def test_cancel_repeated_is_safe(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(OWNER, "o/r", "x", "t", client_ref="r1")
    c = _authed(tmp_path, db)
    r1 = _post(c, {"id": jid, "action": "cancel"})
    r2 = _post(c, {"id": jid, "action": "cancel"})
    assert r1.status_code == 200 and r2.status_code == 409
    assert db.get_creation_job(jid).status == "discarded"


def test_cancel_enforces_ownership(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    jx = db.add_creation_job(OTHER, "o/other", "x", "t", client_ref="r1")
    c = _authed(tmp_path, db)
    assert _post(c, {"id": jx, "action": "cancel"}).status_code == 404
    assert db.get_creation_job(jx).status == "pending"  # مفيش تغيير


def test_cancel_unknown_job_404(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    c = _authed(tmp_path, db)
    assert _post(c, {"id": 99999, "action": "cancel"}).status_code == 404


# ------------------------------------------------------------ reconciliation
def test_mark_sent_only_from_unknown(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(OWNER, "o/r", "x", "t", client_ref="r1")
    db.set_creation_status(jid, "unknown", "t1")
    c = _authed(tmp_path, db)
    r = _post(c, {"id": jid, "action": "mark_sent"})
    assert r.status_code == 200 and r.json()["state"] == "accepted"
    assert db.get_creation_job(jid).status == "done"


def test_mark_sent_idempotent_when_done(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(OWNER, "o/r", "x", "t", client_ref="r1")
    db.set_creation_done(jid, "t1", "conv-1")
    c = _authed(tmp_path, db)
    r = _post(c, {"id": jid, "action": "mark_sent"})
    assert r.status_code == 200 and r.json()["state"] == "accepted"


def test_mark_sent_rejects_non_unknown(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    c = _authed(tmp_path, db)
    for state in ("pending", "claimed", "starting", "failed"):
        jid = db.add_creation_job(OWNER, "o/r", state, "t", client_ref=f"r-{state}")
        db.set_creation_status(jid, state, "t1")
        r = _post(c, {"id": jid, "action": "mark_sent"})
        assert r.status_code == 409 and r.json()["error"] == "invalid_state"
        assert db.get_creation_job(jid).status == state  # مفيش تغيير


def test_reconcile_unknown_action_rejected(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(OWNER, "o/r", "x", "t", client_ref="r1")
    c = _authed(tmp_path, db)
    assert _post(c, {"id": jid, "action": "resend"}).status_code == 400
    assert db.get_creation_job(jid).status == "pending"


def test_reconcile_requires_auth(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    c = TestClient(
        build_web_app(make_config(tmp_path), db=db, client=FakeClient()),
        raise_server_exceptions=False,
    )
    assert _post(c, {"id": 1, "action": "cancel"}).status_code == 401


def test_reconcile_requires_origin(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(OWNER, "o/r", "x", "t", client_ref="r1")
    c = _authed(tmp_path, db)
    r = c.post(RECONCILE, json={"id": jid, "action": "cancel"})  # بدون Origin
    assert r.status_code == 403 and r.json()["error"] == "bad_origin"
    assert db.get_creation_job(jid).status == "pending"


def test_reconcile_enforces_ownership(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    jx = db.add_creation_job(OTHER, "o/other", "x", "t", client_ref="r1")
    db.set_creation_status(jx, "unknown", "t1")
    c = _authed(tmp_path, db)
    assert _post(c, {"id": jx, "action": "mark_sent"}).status_code == 404
    assert db.get_creation_job(jx).status == "unknown"


# ------------------------------------------------------------ no duplicate creation
def test_reconcile_never_touches_remote_client(tmp_path):
    """التسوية **مابتعملش** أي نداء شبكة (مفيش POST بعيد ⇒ مفيش إنشاء مكرّر)."""
    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(OWNER, "o/r", "x", "t", client_ref="r1")
    db.set_creation_status(jid, "unknown", "t1")
    client = FakeClient()
    c = _authed(tmp_path, db, client=client)
    _post(c, {"id": jid, "action": "mark_sent"})
    _post(c, {"id": jid, "action": "cancel"})
    assert client.calls == [], "مفيش أي نداء شبكة من مسار التسوية"


def test_unknown_never_becomes_retryable_pending(tmp_path):
    """الغموض مايتحوّلش أبدًا لحالة قابلة لإعادة المحاولة تلقائيًا."""
    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(OWNER, "o/r", "x", "t", client_ref="r1")
    db.set_creation_status(jid, "unknown", "t1")
    c = _authed(tmp_path, db)
    # إلغاء (غير مؤكد) لا يغيّر الحالة، ولا يرجّعها pending.
    _post(c, {"id": jid, "action": "cancel"})
    assert db.get_creation_job(jid).status == "unknown"
    # mark_sent ⇒ done (نهائي، مستحيل يرجع pending).
    _post(c, {"id": jid, "action": "mark_sent"})
    assert db.get_creation_job(jid).status == "done"
    assert db.list_creation_jobs_by_status("pending") == []


def test_done_job_cannot_be_recancelled_or_recreated(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(OWNER, "o/r", "x", "t", client_ref="r1")
    db.set_creation_done(jid, "t1", "conv-1")
    c = _authed(tmp_path, db)
    assert _post(c, {"id": jid, "action": "cancel"}).status_code == 409
    assert _post(c, {"id": jid, "action": "mark_sent"}).status_code == 200  # idempotent
    assert db.get_creation_job(jid).status == "done"
    assert db.get_creation_job(jid).conversation_id == "conv-1"


# ------------------------------------------------------------ concurrency / stale
def test_cancel_loses_worker_start_race_not_confirmed(tmp_path):
    """سباق: الـ worker بدأ (claimed⇒starting) بعد قراءة الخدمة وقبل الـ CAS ⇒ not_confirmed."""
    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(OWNER, "o/r", "x", "t", client_ref="r1")
    c = _authed(tmp_path, db)

    real_discard = db.discard_creation_job
    calls = {"n": 0}

    def racing_discard(job_id, now, reason=None, chat_id=None):
        # قبل الـ CAS بالظبط، الـ worker يبدأ الـ POST (claimed ⇒ starting).
        calls["n"] += 1
        db.set_creation_status(jid, "starting", "t1")
        return real_discard(job_id, now, reason, chat_id=chat_id)

    db.discard_creation_job = racing_discard  # type: ignore[assignment]
    r = _post(c, {"id": jid, "action": "cancel"})
    assert r.status_code == 200 and r.json()["cancellation"] == "not_confirmed"
    assert db.get_creation_job(jid).status == "starting"  # ما اتلغاش (مفيش clobber)


def test_two_simultaneous_cancels_only_one_wins(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(OWNER, "o/r", "x", "t", client_ref="r1")
    c = _authed(tmp_path, db)
    r1 = _post(c, {"id": jid, "action": "cancel"})
    r2 = _post(c, {"id": jid, "action": "cancel"})
    assert sorted([r1.status_code, r2.status_code]) == [200, 409]
    assert db.get_creation_job(jid).status == "discarded"


def test_stale_cancel_after_worker_done_rejected(tmp_path):
    """طلب قديم (stale): الـ worker خلّص ⇒ الحالة نهائية ⇒ 409 من غير أي تغيير."""
    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(OWNER, "o/r", "x", "t", client_ref="r1")
    c = _authed(tmp_path, db)
    db.set_creation_done(jid, "t1", "conv-1")  # الـ worker خلّص قبل الطلب
    r = _post(c, {"id": jid, "action": "cancel"})
    assert r.status_code == 409 and r.json()["error"] == "already_terminal"
    assert db.get_creation_job(jid).conversation_id == "conv-1"  # الدليل محفوظ


def test_concurrent_mark_sent_single_transition(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(OWNER, "o/r", "x", "t", client_ref="r1")
    db.set_creation_status(jid, "unknown", "t1")
    c = _authed(tmp_path, db)
    r1 = _post(c, {"id": jid, "action": "mark_sent"})
    r2 = _post(c, {"id": jid, "action": "mark_sent"})
    assert r1.status_code == 200 and r2.status_code == 200  # idempotent
    assert db.get_creation_job(jid).status == "done"


def test_mark_sent_loses_cas_race_returns_conflict(tmp_path):
    """سباق CAS: حد تاني حسم الطلب بين القراءة والـ CAS ⇒ 409 (مفيش read-then-write)."""
    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(OWNER, "o/r", "x", "t", client_ref="r1")
    db.set_creation_status(jid, "unknown", "t1")
    c = _authed(tmp_path, db)

    real_cas = db.set_creation_status_if_in
    calls = {"n": 0}

    def racing_cas(job_id, new_status, now, allowed, error=None, chat_id=None):
        calls["n"] += 1
        db.set_creation_status(jid, "failed", "t2")  # حد تاني حسم الطلب
        return real_cas(job_id, new_status, now, allowed, error, chat_id=chat_id)

    db.set_creation_status_if_in = racing_cas  # type: ignore[assignment]
    r = _post(c, {"id": jid, "action": "mark_sent"})
    assert r.status_code == 409 and r.json()["error"] == "invalid_state"
    assert db.get_creation_job(jid).status == "failed"  # مفيش clobber


def test_cas_race_to_done_is_idempotent(tmp_path):
    """سباق: حد تاني حسم الطلب لـ done بين القراءة والـ CAS ⇒ no-op idempotent."""
    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(OWNER, "o/r", "x", "t", client_ref="r1")
    db.set_creation_status(jid, "unknown", "t1")
    c = _authed(tmp_path, db)

    real_cas = db.set_creation_status_if_in

    def racing_cas(job_id, new_status, now, allowed, error=None, chat_id=None):
        db.set_creation_done(jid, "t2", "conv-x")
        return real_cas(job_id, new_status, now, allowed, error, chat_id=chat_id)

    db.set_creation_status_if_in = racing_cas  # type: ignore[assignment]
    r = _post(c, {"id": jid, "action": "mark_sent"})
    assert r.status_code == 200 and r.json()["state"] == "accepted"
    assert db.get_creation_job(jid).status == "done"


# -------------------------------------------- outbox by-id lookups are owner-scoped too
def test_outbox_operation_owner_scoped(tmp_path):
    """OHB2-PHASE1D: البحث بـ id على الصندوق مقيّد بالمالك — id مستخدم تاني ⇒ 404."""
    db = Database(str(tmp_path / "d.sqlite3"))
    ox = db.add_or_group_outbox("c1", OTHER, "x", "t", client_ref="r1")
    c = _authed(tmp_path, db)
    assert c.get(f"/api/v1/operations/outbox?id={ox}").status_code == 404


def test_outbox_reconcile_owner_scoped(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    ox = db.add_or_group_outbox("c1", OTHER, "x", "t", client_ref="r1")
    c = _authed(tmp_path, db)
    r = c.post("/api/v1/operations/outbox/reconcile", json={"id": ox, "action": "discard"}, headers={"origin": ORIGIN})
    assert r.status_code == 404
    assert db.get_outbox(ox).status == "pending"  # مفيش تغيير


# ------------------------------- DB-layer mutators are owner-scoped too (defense in depth)
def test_db_discard_owner_scoped_other_user_noop(tmp_path):
    """الدفاع في العمق: `discard_creation_job(chat_id=...)` مستخدم تاني ⇒ مفيش تغيير."""
    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(OTHER, "o/r", "x", "t", client_ref="r1")
    outcome = db.discard_creation_job(jid, "t2", "x", chat_id=OWNER)
    assert outcome == "terminal"  # الصف مش مملوك ⇒ مش موجود في نطاق المالك
    assert db.get_creation_job(jid).status == "pending"  # ما اتلغاش


def test_db_discard_owner_scoped_owner_ok(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(OWNER, "o/r", "x", "t", client_ref="r1")
    assert db.discard_creation_job(jid, "t2", "x", chat_id=OWNER) == "discarded"
    assert db.get_creation_job(jid).status == "discarded"


def test_db_cas_owner_scoped_other_user_noop(tmp_path):
    """الدفاع في العمق: `set_creation_status_if_in(chat_id=...)` مستخدم تاني ⇒ مفيش تغيير."""
    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(OTHER, "o/r", "x", "t", client_ref="r1")
    db.set_creation_status(jid, "unknown", "t1")
    changed = db.set_creation_status_if_in(jid, "done", "t2", {"unknown"}, None, chat_id=OWNER)
    assert changed is False
    assert db.get_creation_job(jid).status == "unknown"  # ما اتغيّرش


def test_db_cas_owner_scoped_owner_ok(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(OWNER, "o/r", "x", "t", client_ref="r1")
    db.set_creation_status(jid, "unknown", "t1")
    changed = db.set_creation_status_if_in(jid, "done", "t2", {"unknown"}, None, chat_id=OWNER)
    assert changed is True
    assert db.get_creation_job(jid).status == "done"


def test_db_discard_without_scope_still_works(tmp_path):
    """المسارات الداخلية (البوت/الـ workers) من غير نطاق لازم تفضل شغّالة كما هي."""
    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(OTHER, "o/r", "x", "t", client_ref="r1")
    assert db.discard_creation_job(jid, "t2") == "discarded"


def test_db_cas_without_scope_still_works(tmp_path):
    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(OTHER, "o/r", "x", "t", client_ref="r1")
    db.set_creation_status(jid, "unknown", "t1")
    assert db.set_creation_status_if_in(jid, "done", "t2", {"unknown"}) is True
