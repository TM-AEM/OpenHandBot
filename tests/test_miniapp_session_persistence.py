"""OHB2-PHASE1A: اختبارات ثبات جلسات الـ Mini App في SQLite.

بتثبّت: التخزين الدائم، هاش التوكن (مفيش توكن خام)، النجاة من إعادة التشغيل،
الانتهاء، الإلغاء، ملكية المستخدم، الفشل المغلق، أمان الكوكي، والترحيل.
كل الاختبارات بقاعدة مؤقتة معزولة وتبعيات وهمية (مفيش شبكة/تيليجرام/OpenHands حقيقي).
"""
from __future__ import annotations

import logging
import sqlite3

import pytest
from starlette.testclient import TestClient

from bot.config import Config
from bot.db import Database
from bot.web import build_web_app
from bot.web.app import COOKIE_NAME, MiniApp
from bot.web.sessions import SessionStore, hash_token
from tests._miniapp_helpers import BOT_TOKEN, make_init_data

OWNER = 555
OTHER = 999
ORIGIN = "http://testserver"


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


def make_db(tmp_path) -> Database:
    return Database(str(tmp_path / "sessions.sqlite3"))


# --------------------------------------------------------- durable basics
def test_new_session_authenticates(tmp_path):
    db = make_db(tmp_path)
    store = SessionStore(ttl=100, db=db)
    s = store.create(OWNER, {"display_name": "أحمد"})
    got = store.get(s.token)
    assert got is not None
    assert got.user_id == OWNER
    assert got.profile["display_name"] == "أحمد"


def test_raw_token_never_stored_only_hash(tmp_path):
    db = make_db(tmp_path)
    store = SessionStore(ttl=100, db=db)
    s = store.create(OWNER)
    # العمود بيحمل هاش SHA-256، **مش** التوكن الخام.
    rows = db._conn.execute("SELECT token_hash, user_id FROM web_sessions").fetchall()
    assert len(rows) == 1
    assert rows[0]["token_hash"] == hash_token(s.token)
    assert rows[0]["token_hash"] != s.token
    # التوكن الخام ما ظهرش في أي مكان في القاعدة (كل الأعمدة/النص).
    dump = "\n".join(
        str(v) for row in db._conn.execute("SELECT * FROM web_sessions").fetchall() for v in row
    )
    assert s.token not in dump
    assert len(rows[0]["token_hash"]) == 64


def test_session_survives_service_reconstruction(tmp_path):
    path = str(tmp_path / "sessions.sqlite3")
    db1 = Database(path)
    token = SessionStore(ttl=100, db=db1).create(OWNER).token
    # إعادة بناء الخدمة/العملية: اتصال ومخزن جديدان على نفس الملف.
    db2 = Database(path)
    got = SessionStore(ttl=100, db=db2).get(token)
    assert got is not None and got.user_id == OWNER


def test_session_survives_sqlite_close_and_reopen(tmp_path):
    path = str(tmp_path / "sessions.sqlite3")
    db1 = Database(path)
    token = SessionStore(ttl=100, db=db1).create(OWNER).token
    db1._conn.close()
    db2 = Database(path)
    assert SessionStore(ttl=100, db=db2).get(token) is not None


# ----------------------------------------------------- expiry / revocation
def test_expired_session_rejected(tmp_path):
    db = make_db(tmp_path)
    store = SessionStore(ttl=10, db=db)
    s = store.create(OWNER, now=1000.0)
    assert store.get(s.token, now=1005.0) is not None
    assert store.get(s.token, now=1011.0) is None


def test_expired_session_rejected_after_restart(tmp_path):
    path = str(tmp_path / "sessions.sqlite3")
    db1 = Database(path)
    token = SessionStore(ttl=10, db=db1).create(OWNER, now=1000.0).token
    db2 = Database(path)
    # حتى لو العميل فضل يبعت الكوكي، الانتهاء من السيرفر يمنع المصادقة.
    assert SessionStore(ttl=10, db=db2).get(token, now=1011.0) is None


def test_revoked_session_rejected(tmp_path):
    db = make_db(tmp_path)
    store = SessionStore(ttl=100, db=db)
    s = store.create(OWNER)
    store.revoke(s.token)
    assert store.get(s.token) is None


def test_revoked_stays_rejected_after_restart(tmp_path):
    path = str(tmp_path / "sessions.sqlite3")
    db1 = Database(path)
    store1 = SessionStore(ttl=100, db=db1)
    token = store1.create(OWNER).token
    store1.revoke(token)
    db2 = Database(path)
    assert SessionStore(ttl=100, db=db2).get(token) is None


def test_unknown_and_malformed_token_rejected(tmp_path):
    db = make_db(tmp_path)
    store = SessionStore(ttl=100, db=db)
    store.create(OWNER)
    assert store.get("not-a-real-token") is None
    assert store.get("") is None
    assert store.get(None) is None
    assert store.get("x" * 4096) is None
    assert store.get("../../etc/passwd") is None


def test_tampered_token_rejected(tmp_path):
    db = make_db(tmp_path)
    store = SessionStore(ttl=100, db=db)
    s = store.create(OWNER)
    tampered = s.token[:-1] + ("A" if s.token[-1] != "A" else "B")
    assert store.get(tampered) is None


# -------------------------------------------------------- user ownership
def test_session_binds_to_its_own_user(tmp_path):
    db = make_db(tmp_path)
    store = SessionStore(ttl=100, db=db)
    a = store.create(111)
    b = store.create(222)
    assert store.get(a.token).user_id == 111
    assert store.get(b.token).user_id == 222
    # إلغاء جلسة مستخدم ما يأثرش على جلسة غيره.
    store.revoke(a.token)
    assert store.get(a.token) is None
    assert store.get(b.token).user_id == 222


def test_other_user_session_cannot_authorize(tmp_path):
    # جلسة لمستخدم غير مسموح ⇒ تُرفض وتُلغى (فشل مغلق)، وجلسة المالك تفضل شغالة.
    db = make_db(tmp_path)
    app = build_web_app(make_config(), db)
    tc = TestClient(app, raise_server_exceptions=False)
    assert tc.post("/api/v1/auth", json={"initData": make_init_data(OTHER)}).status_code == 403
    assert tc.post("/api/v1/auth", json={"initData": make_init_data(OWNER)}).status_code == 200
    assert tc.get("/api/v1/app/bootstrap").status_code == 200


# ------------------------------------------------------------- fail closed
def test_database_error_fails_closed(tmp_path):
    db = make_db(tmp_path)
    store = SessionStore(ttl=100, db=db)
    s = store.create(OWNER)

    def boom(*_a, **_k):
        raise sqlite3.OperationalError("database is locked")

    db.get_web_session = boom  # type: ignore[assignment]
    assert store.get(s.token) is None  # خطأ القاعدة ما ينفعش يمنح مصادقة


def test_create_failure_does_not_return_unstored_session(tmp_path):
    db = make_db(tmp_path)
    store = SessionStore(ttl=100, db=db)

    def boom(*_a, **_k):
        raise sqlite3.OperationalError("disk I/O error")

    db.add_web_session = boom  # type: ignore[assignment]
    with pytest.raises(sqlite3.OperationalError):
        store.create(OWNER)


# -------------------------------------------------------------- cookies
def test_cookie_security_properties_preserved(tmp_path):
    db = make_db(tmp_path)
    tc = TestClient(build_web_app(make_config(), db), raise_server_exceptions=False)
    r = tc.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    assert r.status_code == 200
    raw = r.headers.get("set-cookie", "")
    assert COOKIE_NAME in raw
    assert "HttpOnly" in raw
    assert "samesite=strict" in raw.lower()
    assert "Path=/" in raw


def test_secure_cookie_flag_respected(tmp_path):
    db = make_db(tmp_path)
    tc = TestClient(
        build_web_app(make_config(mini_app_cookie_secure=True), db), raise_server_exceptions=False
    )
    r = tc.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    assert "secure" in r.headers.get("set-cookie", "").lower()


# ------------------------------------------------------- app-level restart
def test_app_session_survives_restart(tmp_path):
    path = str(tmp_path / "sessions.sqlite3")
    cfg = make_config()
    db1 = Database(path)
    tc1 = TestClient(build_web_app(cfg, db1), raise_server_exceptions=False)
    assert tc1.post("/api/v1/auth", json={"initData": make_init_data(OWNER)}).status_code == 200
    token = tc1.cookies.get(COOKIE_NAME)
    assert token

    # "restart": قاعدة وتطبيق جديدان على نفس الملف + نفس الكوكي.
    db2 = Database(path)
    tc2 = TestClient(build_web_app(cfg, db2), raise_server_exceptions=False)
    tc2.cookies.set(COOKIE_NAME, token)
    assert tc2.get("/api/v1/app/bootstrap").status_code == 200


def test_app_logout_survives_restart(tmp_path):
    path = str(tmp_path / "sessions.sqlite3")
    cfg = make_config()
    db1 = Database(path)
    tc1 = TestClient(build_web_app(cfg, db1), raise_server_exceptions=False)
    tc1.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    token = tc1.cookies.get(COOKIE_NAME)
    r = tc1.post("/api/v1/auth/logout", headers={"origin": ORIGIN})
    assert r.status_code == 200

    db2 = Database(path)
    tc2 = TestClient(build_web_app(cfg, db2), raise_server_exceptions=False)
    tc2.cookies.set(COOKIE_NAME, token)
    assert tc2.get("/api/v1/app/bootstrap").status_code == 401


# ------------------------------------------------------------- migration
def test_web_sessions_table_on_fresh_db(tmp_path):
    db = make_db(tmp_path)
    cols = {r["name"] for r in db._conn.execute("PRAGMA table_info(web_sessions)")}
    assert {"token_hash", "user_id", "created_at", "expires_at", "profile"} <= cols


def test_migration_adds_web_sessions_to_old_db(tmp_path):
    path = str(tmp_path / "old.sqlite3")
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE watched (conversation_id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '',"
        " last_state TEXT);"
        "CREATE TABLE user_state (telegram_id INTEGER PRIMARY KEY, awaiting_conversation_id TEXT,"
        " awaiting_kind TEXT, pending_repo TEXT);"
    )
    conn.execute("INSERT INTO watched(conversation_id, title) VALUES('c1', 'قديم')")
    conn.commit()
    conn.close()

    db = Database(path)
    # الجدول الجديد اتضاف، والبيانات القديمة محفوظة، والجلسات بتشتغل.
    assert db.list_watched()[0].conversation_id == "c1"
    store = SessionStore(ttl=100, db=db)
    assert store.get(store.create(OWNER).token) is not None


def test_migration_is_idempotent(tmp_path):
    path = str(tmp_path / "sessions.sqlite3")
    db1 = Database(path)
    token = SessionStore(ttl=100, db=db1).create(OWNER).token
    db1._conn.close()
    # إعادة الفتح تشغّل `_migrate` تاني ⇒ ما تكسرش ولا تفقد الجلسات.
    db2 = Database(path)
    assert SessionStore(ttl=100, db=db2).get(token) is not None


# ---------------------------------------------------- transactions / prune
def test_prune_removes_only_expired(tmp_path):
    db = make_db(tmp_path)
    store = SessionStore(ttl=100, db=db)
    live = store.create(OWNER, now=1000.0)
    dead = store.create(OWNER, now=1000.0)
    db._conn.execute("UPDATE web_sessions SET expires_at=1005 WHERE token_hash=?", (hash_token(dead.token),))
    db._conn.commit()
    removed = db.prune_web_sessions(1010.0)
    assert removed == 1
    assert store.get(live.token, now=1010.0) is not None
    assert store.get(dead.token, now=1010.0) is None


def test_interleaved_operations_stay_consistent(tmp_path):
    db = make_db(tmp_path)
    store = SessionStore(ttl=10_000, db=db)
    tokens = [store.create(OWNER).token for _ in range(50)]
    for i, t in enumerate(tokens):
        if i % 5 == 0:
            store.revoke(t)
    for i, t in enumerate(tokens):
        got = store.get(t)
        if i % 5 == 0:
            assert got is None
        else:
            assert got is not None
    assert db.count_web_sessions() == len(tokens) - 10


def test_single_connection_owner_preserved(tmp_path):
    # مفيش مالك اتصال تاني: نفس الاتصال، ونفس إعدادات WAL/busy_timeout.
    db = make_db(tmp_path)
    store = SessionStore(ttl=100, db=db)
    store.create(OWNER)
    assert db._conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert db._conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


def test_expired_pruned_on_create_and_lookup(tmp_path):
    # التنظيف (prune) بيحصل كجزء من دورة الحياة: عند الإنشاء (best-effort) والفحص.
    db = make_db(tmp_path)
    store = SessionStore(ttl=10, db=db)
    old = store.create(OWNER, now=1000.0)  # بينتهي عند 1010
    # إنشاء جديد "لاحق" يشيل المنتهي من نفس الجدول.
    store.create(OWNER, now=5000.0)
    assert store.get(old.token, now=5000.0) is None
    assert db.count_web_sessions() == 1


def test_revoke_is_idempotent(tmp_path):
    db = make_db(tmp_path)
    store = SessionStore(ttl=100, db=db)
    s = store.create(OWNER)
    store.revoke(s.token)
    store.revoke(s.token)  # تاني ⇒ لا شيء (مفيش خطأ)
    assert store.get(s.token) is None


def test_lookup_uses_serialized_connection_owner(tmp_path):
    # التأكيد إن العمليات كلها على **نفس** الاتصال الواحد (مفيش مالك تاني/اتصال جديد).
    db = make_db(tmp_path)
    store = SessionStore(ttl=100, db=db)
    before = id(db._conn)
    store.create(OWNER)
    store.get("x")
    store.revoke("x")
    assert id(db._conn) == before


def test_ttl_defaults_and_minimum(tmp_path):
    db = make_db(tmp_path)
    # TTL أقل من 1 بيتصحّح لـ 1 (زي السلوك القديم).
    store = SessionStore(ttl=0, db=db)
    s = store.create(OWNER, now=1000.0)
    assert s.expires_at == 1001.0


def test_revoke_failure_is_logged_not_swallowed_silently(tmp_path, caplog):
    db = make_db(tmp_path)
    store = SessionStore(ttl=100, db=db)
    s = store.create(OWNER)

    def boom(*_a, **_k):
        raise sqlite3.OperationalError("database is locked")

    db.delete_web_session = boom  # type: ignore[assignment]
    with caplog.at_level(logging.WARNING):
        store.revoke(s.token)  # ما يرميش، لكن يسجّل تحذير بلا أي سر
    assert any("إلغاء جلسة" in r.getMessage() for r in caplog.records)
    assert s.token not in "\n".join(r.getMessage() for r in caplog.records)


def test_tokens_not_logged(tmp_path, caplog):
    db = make_db(tmp_path)
    store = SessionStore(ttl=100, db=db)
    with caplog.at_level(logging.DEBUG):
        s = store.create(OWNER)
        store.get(s.token)
        store.get("garbage-token")
        store.revoke(s.token)
    joined = "\n".join(r.getMessage() for r in caplog.records)
    assert s.token not in joined


# ================================ OHB2-PHASE1E-F4: limiter key is not the raw token
def test_rate_limiter_key_is_hashed_not_raw_token(tmp_path):
    """F4: التوثيق بيقول المفاتيح معرّفات مستعارة مش توكنات، لكن كان التوكن الخام نفسه
    بيتخزّن كمفتاح الحد. دلوقتي لازم يكون هاش التوكن (مفيش توكن خام في المخزن).
    """
    db = make_db(tmp_path)
    app = build_web_app(make_config(), db)
    tc = TestClient(app, raise_server_exceptions=False)
    assert tc.post("/api/v1/auth", json={"initData": make_init_data(OWNER)}).status_code == 200
    raw = tc.cookies.get(COOKIE_NAME)
    assert raw  # عندنا توكن جلسة فعلي

    # نبني MiniApp جديد على **نفس** القاعدة (الجلسة دائمة) عشان نفحص المحدّد مباشرة.
    from bot.web.app import MiniApp

    m = MiniApp(make_config(), db)
    tc2 = TestClient(m.router, raise_server_exceptions=False)
    tc2.cookies.set(COOKIE_NAME, raw)
    assert tc2.get("/api/v1/app/bootstrap").status_code == 200  # يعدّي على المحدّد

    keys = list(m.api_limiter._events.keys())
    assert raw not in keys, "التوكن الخام مستحيل يكون مفتاح الحد"
    assert hash_token(raw) in keys, "المفتاح لازم يكون هاش التوكن"


def test_rate_limiter_key_is_deterministic_and_not_reversible(tmp_path):
    """AUD-05: نفس التوكن ⇒ نفس المفتاح دايمًا؛ والمفتاح هاش 64-hex مش التوكن الخام."""
    import hashlib

    token = "raw-session-token-abc123"
    assert hash_token(token) == hash_token(token)  # حتمي
    key = hash_token(token)
    assert key != token and token not in key
    assert key == hashlib.sha256(token.encode("utf-8")).hexdigest()
    assert len(key) == 64 and all(c in "0123456789abcdef" for c in key)


def test_rate_limiter_keys_are_isolated_per_session(tmp_path):
    """AUD-05: جلسات مختلفة ⇒ مفاتيح مختلفة (العزل محفوظ)؛ وجلسة واحدة ما تستهلكش
    ميزانية جلسة تانية."""
    db = make_db(tmp_path)
    m = MiniApp(make_config(), db)
    t1 = m.sessions.create(OWNER).token
    t2 = m.sessions.create(OWNER).token
    k1, k2 = hash_token(t1), hash_token(t2)
    assert k1 != k2 and t1 != t2
    # استهلك ميزانية t1؛ لازم t2 تفضل مسموحة.
    for _ in range(m._config.mini_app_api_rate_per_minute):
        assert m.api_limiter.allow(k1)[0] is True
    assert m.api_limiter.allow(k1)[0] is False  # t1 اتحدّت
    assert m.api_limiter.allow(k2)[0] is True   # t2 ما اتأثّرش


def test_rate_limiter_key_has_no_raw_token_after_expiry_cleanup(tmp_path):
    """AUD-05: حتى بعد الانتهاء/التنظيف، ما يتخزّنش أي توكن خام كمفتاح."""
    db = make_db(tmp_path)
    m = MiniApp(make_config(), db)
    raw = m.sessions.create(OWNER).token
    # ننادي المحدّد مباشرة بالمفتاح المشتق (نفس ما بيعمل `_guarded`).
    m.api_limiter.allow(hash_token(raw))
    m.sessions.revoke(raw)  # إلغاء + تنظيف
    keys = list(m.api_limiter._events.keys())
    assert all(raw != k for k in keys)
    assert all(len(k) == 64 for k in keys)  # كلها هاشات SHA-256


# ================================ OHB2-PLAN-02-B: تسجيل خروج صادق (fail-closed)
# العيب المؤكَّد: `SessionStore.revoke` كان بيبلع فشل القاعدة، و`/auth/logout` كان
# بيرجّع 200 {"ok": true} ويمسح الكوكي حتى لما الحذف يفشل ⇒ العميل يفتكر إنه خرج
# والجلسة تفضل سارية لحد الـ TTL. الإصلاح: `revoke` بترجّع bool، وlogout بيرجّع
# فشل خادمي صريح وما يمسحش الكوكي لو الإلغاء ما اتأكّدش.

def _revocation_db_failure():
    def boom(*_a, **_k):
        raise sqlite3.OperationalError("database is locked")
    return boom


def test_revoke_returns_false_and_logs_on_db_failure(tmp_path, caplog):
    """Test A: فشل القاعدة في `revoke` يترجّع False (مش نجاح)، ويتسجّل بلا أي سر."""
    db = make_db(tmp_path)
    store = SessionStore(ttl=100, db=db)
    s = store.create(OWNER)
    db.delete_web_session = _revocation_db_failure()  # type: ignore[assignment]
    with caplog.at_level(logging.WARNING):
        assert store.revoke(s.token) is False
    # الصف لسه موجود (الحذف فشل) — الجلسة سارية فعليًا ⇒ لازم نبلّغ بالفشل.
    assert db.count_web_sessions() == 1
    joined = "\n".join(r.getMessage() for r in caplog.records)
    assert "إلغاء جلسة" in joined
    assert s.token not in joined  # مفيش توكن خام في اللوج


def test_revoke_returns_true_on_confirmed_success(tmp_path):
    """Test A (مكمّل): الإلغاء المؤكّد يرجّع True والصف يختفي."""
    db = make_db(tmp_path)
    store = SessionStore(ttl=100, db=db)
    s = store.create(OWNER)
    assert store.revoke(s.token) is True
    assert db.count_web_sessions() == 0


def test_logout_does_not_claim_success_on_revocation_failure(tmp_path):
    """Test B: فشل الإلغاء ⇒ رد غير ناجح (503) بلا {"ok": true}، والكوكي ما يتمسحش،

    والجلسة ما تتعاملش كأنها مُلغاة (تفضل سارية ⇒ العميل يقدر يعيد المحاولة)."""
    db = make_db(tmp_path)
    tc = TestClient(build_web_app(make_config(), db), raise_server_exceptions=False)
    tc.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    token = tc.cookies.get(COOKIE_NAME)
    assert token

    db.delete_web_session = _revocation_db_failure()  # type: ignore[assignment]
    r = tc.post("/api/v1/auth/logout", headers={"origin": ORIGIN})
    assert r.status_code == 503
    assert "ok" not in r.json()
    assert r.json()["error"] == "logout_failed"
    # الكوكي ما اتمسحش ⇒ العميل لسه معاه جلسة يعيد المحاولة بها.
    assert "ohb_session=" not in (r.headers.get("set-cookie") or "")
    # والجلسة لسه سارية من جهة السيرفر (مفيش ادّعاء كاذب بالإلغاء): نفس الكوكي لسه
    # بيصادق على مسار محمي.
    assert tc.get("/api/v1/app/bootstrap").status_code == 200


def test_logout_retry_after_503_revokes_and_persists_across_restart(tmp_path):
    """بعد 503، إعادة المحاولة بالكوكي الباقي تنجح بـ 200 وتثبت الإلغاء بعد إعادة التشغيل."""
    path = str(tmp_path / "retry_logout.sqlite3")
    db = Database(path)
    tc = TestClient(build_web_app(make_config(), db), raise_server_exceptions=False)
    tc.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    token = tc.cookies.get(COOKIE_NAME)
    assert token

    orig_delete = db.delete_web_session
    db.delete_web_session = _revocation_db_failure()  # type: ignore[assignment]
    r1 = tc.post("/api/v1/auth/logout", headers={"origin": ORIGIN})
    assert r1.status_code == 503
    assert "ohb_session=" not in (r1.headers.get("set-cookie") or "")

    # استعادة القاعدة وإعادة المحاولة بنفس الجلسة
    db.delete_web_session = orig_delete  # type: ignore[assignment]
    r2 = tc.post("/api/v1/auth/logout", headers={"origin": ORIGIN})
    assert r2.status_code == 200 and r2.json() == {"ok": True}
    assert "Max-Age=0" in (r2.headers.get("set-cookie") or "")
    db.close()

    # إعادة تشغيل القاعدة والتطبيق ⇒ التوكن القديم مرفوض
    db2 = Database(path)
    tc2 = TestClient(build_web_app(make_config(), db2), raise_server_exceptions=False)
    tc2.cookies.set(COOKIE_NAME, token)
    assert tc2.get("/api/v1/app/bootstrap").status_code == 401


def test_logout_success_clears_cookie_and_revokes(tmp_path):
    """Test C: الإلغاء المؤكّد ⇒ 200 {"ok": true} + مسح الكوكي (بنفس الصفات) + إبطال الجلسة."""
    db = make_db(tmp_path)
    tc = TestClient(build_web_app(make_config(), db), raise_server_exceptions=False)
    tc.post("/api/v1/auth", json={"initData": make_init_data(OWNER)})
    token = tc.cookies.get(COOKIE_NAME)
    assert token  # الجلسة اتعملت فعلًا قبل الخروج

    r = tc.post("/api/v1/auth/logout", headers={"origin": ORIGIN})
    assert r.status_code == 200 and r.json() == {"ok": True}
    set_cookie = r.headers.get("set-cookie") or ""
    assert "ohb_session=" in set_cookie and "Max-Age=0" in set_cookie and "Path=/" in set_cookie
    assert db.count_web_sessions() == 0
    # الكوكي اتمسح فعليًا من العميل ⇒ الطلب الجاي غير مصادق.
    tc.cookies.clear()
    assert tc.get("/api/v1/app/bootstrap").status_code == 401


def test_logout_without_session_is_unauthenticated(tmp_path):
    """Test D: إعادة logout (مفيش كوكي) تفضل 401 حسب العقد القائم (مش خطأ خادمي جديد)."""
    db = make_db(tmp_path)
    tc = TestClient(build_web_app(make_config(), db), raise_server_exceptions=False)
    r = tc.post("/api/v1/auth/logout", headers={"origin": ORIGIN})
    assert r.status_code == 401
    assert r.json()["error"] == "unauthenticated"


def test_revoke_absent_or_expired_session_is_idempotent(tmp_path):
    """Test D (مكمّل): إلغاء توكن غائب/منتهي ما يرميش، ويرجّع True (مفيش حاجة تُلغى)."""
    db = make_db(tmp_path)
    store = SessionStore(ttl=100, db=db)
    assert store.revoke("not-a-real-token") is True  # غائب ⇒ لا شيء
    s = store.create(OWNER, now=1000.0)  # ينتهي عند 1100
    assert store.revoke(s.token) is True
    assert store.revoke(s.token) is True  # تكرار ⇒ لا شيء (idempotent)
