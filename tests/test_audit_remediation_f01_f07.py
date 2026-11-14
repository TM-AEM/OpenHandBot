"""OHB2-POST-PUBLICATION-AUDIT-REMEDIATION: اختبارات مركّزة للإصلاحات F01–F07.

كل قسم بيغطّي finding واحد على الكود الحقيقي (بدون mocks غير ضرورية):
- F01: القراءة المحدودة المتدفّقة لجسم طلب الـ Mini App.
- F02: الإكمال المحلي القابل للتعافي (إشعار/متابعة) بعد نجاح العملية الخارجية.
- F03: رفض إعادة التوجيه 3xx في مسارات التنزيل/التصدير المتدفّقة.
- F05: رفض قيم الإعداد المنطقية غير الصالحة.
- F06: تكامل SQLite عند الإقلاع + جاهزية صادقة.
- F07: تحديد IP العميل بأمان خلف البروكسيات.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3

import httpx
import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from bot.config import Config, ConfigError, load_config
from bot.db import Database
from bot.errors import ApiError
from bot.openhands_client import OpenHandsClient
from bot.outbox import (
    COMPLETION_KIND_CREATION,
    COMPLETION_KIND_OUTBOX,
    COMPLETION_MAX_ATTEMPTS,
    CompletionWorker,
    deliver_outbox,
    now_iso,
)
from bot.web.app import MAX_BODY_BYTES, MiniApp
from bot.web.clientip import UNKNOWN, parse_trusted_proxies, resolve_client_ip
from tests._miniapp_helpers import BOT_TOKEN

OWNER = 555


def _cfg(**over) -> Config:
    base = dict(
        telegram_bot_token=BOT_TOKEN,
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({OWNER}),
        owner_id=OWNER,
        mini_app_cookie_secure=False,
    )
    base.update(over)
    return Config(**base)


# ===================================================================== F01
def _raw_echo_app():
    """تطبيق Starlette حقيقي بيستخدم MiniApp._read_body عشان نختبر القراءة المحدودة."""

    captured: dict = {}

    async def echo(request):
        try:
            data = await request.app.state.mini._read_body(request)
        except Exception as exc:  # noqa: BLE001
            captured["error"] = type(exc).__name__
            return JSONResponse({"error": type(exc).__name__}, status_code=400)
        captured["data"] = data
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/echo", echo, methods=["POST"])])
    app.state.mini = MiniApp(_cfg(), None)
    return app, captured


class _FakeRequest:
    """طلب وهمي لاختبار `_read_body` مباشرة (يستهلك قطع ASGI المزوّدة)."""

    def __init__(self, chunks, headers=None):
        self._chunks = list(chunks)
        self.headers = headers or {}
        self.consumed = 0

    async def stream(self):
        for chunk in self._chunks:
            self.consumed += 1
            yield chunk


def test_f01_normal_small_request():
    app, captured = _raw_echo_app()
    client = TestClient(app)
    r = client.post("/echo", json={"a": 1, "b": "x"})
    assert r.status_code == 200
    assert captured["data"] == {"a": 1, "b": "x"}


def test_f01_exact_max_size_accepted():
    app, captured = _raw_echo_app()
    client = TestClient(app)
    base = '{"a":"' + ("x" * (MAX_BODY_BYTES - 8)) + '"}'
    body = base.encode()
    assert len(body) == MAX_BODY_BYTES
    r = client.post("/echo", content=body, headers={"content-type": "application/json"})
    assert r.status_code == 200
    assert captured["data"]["a"].startswith("x")


def test_f01_max_plus_one_rejected():
    app, captured = _raw_echo_app()
    client = TestClient(app)
    body = b'{"a":"' + b"x" * MAX_BODY_BYTES + b'"}'
    r = client.post("/echo", content=body, headers={"content-type": "application/json"})
    assert r.status_code == 400
    assert captured["error"] == "_BodyTooLarge"


def test_f01_chunked_no_content_length_still_bounded():
    """قطع بدون Content-Length واكبر من الحد ⇒ يُرفض بالعدّ التراكمي."""

    def gen():
        for _ in range(20):
            yield b"x" * 4096  # 81920 > 16384

    app, captured = _raw_echo_app()
    client = TestClient(app)
    r = client.post("/echo", content=gen())
    assert r.status_code == 400
    assert captured["error"] == "_BodyTooLarge"


def test_f01_multiple_asgi_chunks_accumulate():
    payload = {"k": "v" * 100}

    def gen():
        raw = json.dumps(payload).encode()
        for i in range(0, len(raw), 7):
            yield raw[i:i + 7]

    app, captured = _raw_echo_app()
    client = TestClient(app)
    r = client.post("/echo", content=gen(), headers={"content-type": "application/json"})
    assert r.status_code == 200
    assert captured["data"] == payload


def test_f01_oversized_content_length_rejected_before_read():
    mini = MiniApp(_cfg(), None)
    req = _FakeRequest([b"{}"], headers={"content-length": str(MAX_BODY_BYTES + 1)})
    with pytest.raises(Exception) as ei:
        asyncio.run(mini._read_body(req))
    assert type(ei.value).__name__ == "_BodyTooLarge"
    assert req.consumed == 0  # مفيش استهلاك خالص


def test_f01_malformed_content_length_rejected():
    mini = MiniApp(_cfg(), None)
    req = _FakeRequest([b"{}"], headers={"content-length": "abc"})
    with pytest.raises(Exception) as ei:
        asyncio.run(mini._read_body(req))
    assert type(ei.value).__name__ == "_BadJson"


def test_f01_invalid_json_rejected():
    app, captured = _raw_echo_app()
    client = TestClient(app)
    r = client.post("/echo", content=b"{not json")
    assert r.status_code == 400
    assert captured["error"] == "_BadJson"


def test_f01_stops_consuming_after_limit():
    """بعد تجاوز الحد، التطبيق يتوقّف عن استهلاك القطع (مفيش تجميع كامل)."""
    mini = MiniApp(_cfg(), None)
    req = _FakeRequest([b"x" * 4096 for _ in range(100)])
    with pytest.raises(Exception) as ei:
        asyncio.run(mini._read_body(req))
    assert type(ei.value).__name__ == "_BodyTooLarge"
    assert req.consumed < 100  # وقفنا بدري


# ===================================================================== F02
def _mkdb(tmp_path) -> Database:
    return Database(str(tmp_path / "t.sqlite3"))


class _Bot:
    def __init__(self, fail=False):
        self.sent: list[str] = []
        self.fail = fail

    async def send_message(self, chat_id, text):
        if self.fail:
            from telegram.error import TelegramError

            raise TelegramError("boom")
        self.sent.append(text)


def test_f02_completion_table_roundtrip(tmp_path):
    db = _mkdb(tmp_path)
    db.add_completion_pending(
        COMPLETION_KIND_OUTBOX, 7, 99, "c1", now_iso(),
        title="T", last_state="running", submitted_at="t0", notice_text="نص",
    )
    row = db.get_completion_pending(COMPLETION_KIND_OUTBOX, 7)
    assert row is not None
    assert row.notice_text == "نص"
    assert row.conversation_id == "c1"
    assert row.attempts == 0
    assert db.count_completion_pending() == 1
    # idempotent: تسجيل تاني مايعملش صف تاني (بس يحدّث البيانات).
    db.add_completion_pending(COMPLETION_KIND_OUTBOX, 7, 99, "c1", now_iso(), notice_text="نص2")
    assert db.count_completion_pending() == 1
    assert db.get_completion_pending(COMPLETION_KIND_OUTBOX, 7).notice_text == "نص2"
    db.clear_completion_pending(COMPLETION_KIND_OUTBOX, 7)
    assert db.count_completion_pending() == 0


def test_f02_outbox_success_registers_completion_and_completes(tmp_path):
    """نجاح POST: 'sent' + صف إكمال write-ahead + إشعار + متابعة، والصف يتشال بعد النجاح."""
    db = _mkdb(tmp_path)
    oid = db.add_outbox("c1", 99, "برومت", now_iso())

    class Client:
        async def get_conversations(self, ids):
            return [{"id": "c1", "title": "شات", "execution_status": "running",
                     "sandbox_status": "RUNNING"}]

        async def send_message(self, cid, text):
            pass

    bot = _Bot()
    asyncio.run(deliver_outbox(Client(), db, bot, oid))
    assert db.get_outbox(oid).status == "sent"
    assert db.is_watched("c1")
    assert db.count_completion_pending() == 0  # الإشعار نجح ⇒ اتشال
    assert any("اتبعت" in s for s in bot.sent)


def test_f02_outbox_notification_failure_keeps_completion_and_recovers(tmp_path):
    """فشل الإشعار: 'sent' + المتابعة مسجّلة + صف إكمال **لسه معلّق** للتعافي."""
    db = _mkdb(tmp_path)
    oid = db.add_outbox("c1", 99, "برومت", now_iso())

    class Client:
        async def get_conversations(self, ids):
            return [{"id": "c1", "title": "شات", "execution_status": "running",
                     "sandbox_status": "RUNNING"}]

        async def send_message(self, cid, text):
            pass

    bot = _Bot(fail=True)
    asyncio.run(deliver_outbox(Client(), db, bot, oid))
    assert db.get_outbox(oid).status == "sent"
    assert db.is_watched("c1")  # المتابعة اتسجّلت قبل الإشعار
    pending = db.get_completion_pending(COMPLETION_KIND_OUTBOX, oid)
    assert pending is not None  # لسه معلّق ⇒ هيتعافى

    # التعافي: worker الإكمال يبعت الإشعار (من غير أي POST خارجي) ويشيل الصف.
    ok_bot = _Bot()
    worker = CompletionWorker(None, db, ok_bot)
    asyncio.run(worker._tick())
    assert db.get_completion_pending(COMPLETION_KIND_OUTBOX, oid) is None
    assert any("اتبعت" in s for s in ok_bot.sent)
    assert db.get_outbox(oid).status == "sent"  # مفيش POST خارجي مكرّر


def test_f02_completion_worker_never_touches_external(tmp_path):
    """worker الإكمال مايناديش أي عميل خارجي إطلاقًا (at-most-once محفوظ)."""
    db = _mkdb(tmp_path)
    db.add_completion_pending(
        COMPLETION_KIND_OUTBOX, 1, 99, "c1", now_iso(), title="T", notice_text="نص",
    )

    class ExplodeClient:
        async def get_conversations(self, ids):
            raise AssertionError("الإكمال المحلي مايعملش أي استدعاء خارجي")

        async def send_message(self, *a, **k):
            raise AssertionError("الإكمال المحلي مايعملش أي استدعاء خارجي")

    worker = CompletionWorker(ExplodeClient(), db, _Bot())
    asyncio.run(worker._tick())
    assert db.count_completion_pending() == 0


def test_f02_creation_done_registers_completion_no_duplicate_conversation(tmp_path):
    """إنشاء شات: 'done' + صف إكمال يحمل الرابط/المعرّف؛ الفشل مايعيدش إنشاء شات."""
    from bot import outbox as ob

    db = _mkdb(tmp_path)
    jid = db.add_creation_job(99, "o/r", "text", now_iso())
    db.set_creation_status(jid, "claimed", now_iso())

    class Client:
        async def get_conversations(self, ids):
            return []

    bot = _Bot(fail=True)
    asyncio.run(ob._finish_creation(Client(), db, bot, jid, 99, "o/r", "conv-1", "https://x"))
    assert db.get_creation_job(jid).status == "done"
    pending = db.get_completion_pending(COMPLETION_KIND_CREATION, jid)
    assert pending is not None
    assert pending.conversation_id == "conv-1"
    assert "conv-1" in pending.notice_text

    # التعافي يبعت الرابط من غير أي POST (الـ client مايتنادىش).
    class ExplodeClient:
        async def get_conversations(self, ids):
            raise AssertionError("ماينفعش نعمل POST/GET خارجي في الإكمال")

    ok_bot = _Bot()
    worker = CompletionWorker(ExplodeClient(), db, ok_bot)
    asyncio.run(worker._tick())
    assert db.get_completion_pending(COMPLETION_KIND_CREATION, jid) is None
    assert any("conv-1" in s for s in ok_bot.sent)
    assert db.get_creation_job(jid).status == "done"  # مفيش إعادة إنشاء


def test_f02_completion_attempts_bounded(tmp_path):
    """فشل الإشعار المتكرّر مايعملش حلقة لا نهائية: العدّاد يزيد ومحدود.

    OHB2-STABILIZATION-F02: بقى فيه backoff دائم (next_attempt_at)، فالمحاولات المتلاحقة
    لازم تكون بعد ما موعد المحاولة يحين. بنحاكي مرور الوقت بتصفير next_attempt_at بين الدورات.
    """
    db = _mkdb(tmp_path)
    db.add_completion_pending(
        COMPLETION_KIND_OUTBOX, 1, 99, "c1", now_iso(), title="T", notice_text="نص",
    )
    bot = _Bot(fail=True)
    worker = CompletionWorker(None, db, bot)
    for _ in range(COMPLETION_MAX_ATTEMPTS + 3):
        # نخلّي العنصر مؤهّل من جديد (نحاكي مرور وقت الـ backoff).
        db._conn.execute("UPDATE completion_pending SET next_attempt_at=NULL")
        db._conn.commit()
        asyncio.run(worker._tick())
    row = db.get_completion_pending(COMPLETION_KIND_OUTBOX, 1)
    assert row is not None  # لسه معلّق (ظاهر في الحالة) مش مفقود
    assert row.exhausted == 1  # مستنفد/مطلوب تدخّل، ومستبعد من المؤهّل
    assert row.attempts >= COMPLETION_MAX_ATTEMPTS


def test_f02_recovery_across_restart_completes(tmp_path):
    """محاكاة crash بعد 'sent' وقبل الإشعار: صف الإكمال ينجو ويُكمل بعد restart."""
    db = _mkdb(tmp_path)
    oid = db.add_outbox("c1", 99, "برومت", now_iso())
    db.set_outbox_status(oid, "sent", now_iso())
    db.add_completion_pending(
        COMPLETION_KIND_OUTBOX, oid, 99, "c1", now_iso(), title="شات",
        last_state="running", notice_text="اتبعت ✅ الشات اتضاف للمتابعة.",
    )
    # "إعادة تشغيل": نفس القاعدة، اتصال جديد.
    db2 = Database(str(tmp_path / "t.sqlite3"))
    assert db2.count_completion_pending() == 1
    bot = _Bot()
    worker = CompletionWorker(None, db2, bot)
    asyncio.run(worker._tick())
    assert db2.count_completion_pending() == 0
    assert db2.is_watched("c1")
    assert any("اتبعت" in s for s in bot.sent)


# ===================================================================== F03
class _ChunkedStream(httpx.AsyncByteStream):
    def __init__(self, chunks):
        self._chunks = list(chunks)

    async def __aiter__(self):
        for chunk in self._chunks:
            yield chunk

    async def aclose(self):
        pass


def _client(handler, key="key"):
    return OpenHandsClient("https://example.test", key, transport=httpx.MockTransport(handler))


@pytest.mark.parametrize("code", [301, 302, 307, 308])
def test_f03_read_file_rejects_redirects(code):
    seen = {"n": 0}

    def handler(request):
        seen["n"] += 1
        return httpx.Response(
            code, headers={"location": "https://evil.test/x"},
            stream=_ChunkedStream([b"x"]),
        )

    client = _client(handler)
    with pytest.raises(ApiError) as ei:
        asyncio.run(client.read_file_text_bounded("c1", "f.txt"))
    assert ei.value.status_code == code
    assert seen["n"] == 1  # مفيش متابعة


@pytest.mark.parametrize("code", [301, 302, 307, 308])
def test_f03_export_rejects_redirects(code):
    seen = {"n": 0}

    def handler(request):
        seen["n"] += 1
        return httpx.Response(
            code, headers={"location": "https://evil.test/x"},
            stream=_ChunkedStream([b"x"]),
        )

    client = _client(handler)
    with pytest.raises(ApiError) as ei:
        asyncio.run(client.export_conversation("c1"))
    assert ei.value.status_code == code
    assert seen["n"] == 1


def test_f03_redirect_body_not_returned_as_content():
    def handler(request):
        return httpx.Response(
            302, headers={"location": "https://evil.test/x"},
            stream=_ChunkedStream([b"SECRET-REDIRECT-BODY"]),
        )

    client = _client(handler)
    with pytest.raises(ApiError):
        asyncio.run(client.read_file_text_bounded("c1", "f.txt"))


def test_f03_non_redirect_still_works():
    body = json.dumps("hello").encode()

    def handler(request):
        return httpx.Response(200, stream=_ChunkedStream([body]))

    client = _client(handler)
    assert asyncio.run(client.read_file_text_bounded("c1", "f.txt")) == "hello"


# ===================================================================== F05
_BASE_ENV = {
    "TELEGRAM_BOT_TOKEN": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
    "OPENHANDS_API_KEY": "secret-key-123456",
    "ALLOWED_TELEGRAM_ID": "555",
}
_MINI_URL = "https://example.test/mini/"


def _env(**over):
    return {**_BASE_ENV, **over}


def test_f05_missing_retains_default():
    assert load_config(_env()).mini_app_enabled is False


def test_f05_empty_retains_default():
    assert load_config(_env(MINI_APP_ENABLED="")).mini_app_enabled is False
    assert load_config(_env(MINI_APP_ENABLED="   ")).mini_app_enabled is False


@pytest.mark.parametrize("val", ["1", "true", "TRUE", "Yes", "on", "y", " true "])
def test_f05_truthy_accepted(val):
    cfg = load_config(_env(MINI_APP_ENABLED=val, MINI_APP_URL=_MINI_URL))
    assert cfg.mini_app_enabled is True


@pytest.mark.parametrize("val", ["0", "false", "FALSE", "No", "off", "n", " 0 "])
def test_f05_falsy_accepted(val):
    assert load_config(_env(MINI_APP_ENABLED=val)).mini_app_enabled is False


@pytest.mark.parametrize("val", ["garbage", "2", "enabled", "nope", "yesss"])
def test_f05_invalid_rejected(val):
    with pytest.raises(ConfigError) as ei:
        load_config(_env(MINI_APP_ENABLED=val))
    # الرسالة بتذكر اسم المتغيّر بس، مش القيمة.
    assert "MINI_APP_ENABLED" in str(ei.value)
    assert val not in str(ei.value)


# ===================================================================== F06
def test_f06_healthy_quick_check(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    assert db.run_startup_maintenance() is True
    assert db.is_healthy() is True


def test_f06_unhealthy_quick_check(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "t.sqlite3"))
    monkeypatch.setattr(db, "quick_check", lambda: False)
    assert db.run_startup_maintenance() is False
    assert db.is_healthy() is False


def test_f06_raising_quick_check(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "t.sqlite3"))

    def boom():
        raise sqlite3.DatabaseError("corrupt")

    monkeypatch.setattr(db, "quick_check", boom)
    assert db.run_startup_maintenance() is False
    assert db.is_healthy() is False


def test_f06_workers_not_started_after_integrity_failure(tmp_path, monkeypatch):
    """فشل التكامل ⇒ مفيش workers/مراقب/مُبلّغ ولا polling."""
    from bot.app import build_application

    cfg = _cfg(db_path=str(tmp_path / "t.sqlite3"))
    app = build_application(cfg)
    db = app.bot_data["db"]
    monkeypatch.setattr(db, "run_startup_maintenance", lambda: False)
    asyncio.run(app.post_init(app))
    assert app.bot_data.get("startup_failed") == "database_integrity"
    for key in ("outbox_worker", "creation_worker", "completion_worker", "watcher", "notifier"):
        assert app.bot_data.get(key) is None


def test_f06_readiness_not_ready_before_check(tmp_path):
    db = Database(str(tmp_path / "t.sqlite3"))
    assert db.integrity_ok is None
    assert db.is_healthy() is False  # مفيش ادّعاء READY قبل الفحص


# ===================================================================== F07
class _Req:
    def __init__(self, host, headers=None):
        self.client = type("C", (), {"host": host})() if host is not None else None
        self.headers = headers or {}


def test_f07_direct_client_uses_peer_ip():
    assert resolve_client_ip(_Req("8.8.8.8")) == "8.8.8.8"


def test_f07_no_trusted_proxies_ignores_forwarded():
    req = _Req("8.8.8.8", {"x-forwarded-for": "1.2.3.4"})
    assert resolve_client_ip(req) == "8.8.8.8"  # الهيدر بيتجاهَل تمامًا


def test_f07_private_peer_collapses_to_unknown():
    assert resolve_client_ip(_Req("10.0.0.5")) == UNKNOWN


def test_f07_trusted_proxy_uses_forwarded_client():
    trusted = parse_trusted_proxies("10.0.0.0/8")
    req = _Req("10.0.0.9", {"x-forwarded-for": "8.8.8.8"})
    assert resolve_client_ip(req, trusted) == "8.8.8.8"


def test_f07_trusted_proxy_skips_trusted_hops():
    trusted = parse_trusted_proxies("10.0.0.0/8")
    req = _Req("10.0.0.9", {"x-forwarded-for": "8.8.8.8, 10.0.0.8"})
    assert resolve_client_ip(req, trusted) == "8.8.8.8"


def test_f07_untrusted_peer_ignores_forwarded():
    trusted = parse_trusted_proxies("10.0.0.0/8")
    req = _Req("9.9.9.9", {"x-forwarded-for": "1.2.3.4"})
    assert resolve_client_ip(req, trusted) == "9.9.9.9"


def test_f07_spoofed_forwarded_from_untrusted_peer():
    """عميل مباشر (مش بروكسي موثوق) يحاول يزوّر XFF ⇒ IP الاتصال الفعلي."""
    trusted = parse_trusted_proxies("10.0.0.0/8")
    req = _Req("9.9.9.9", {"x-forwarded-for": "1.2.3.4"})
    assert resolve_client_ip(req, trusted) == "9.9.9.9"


def test_f07_malformed_forwarded_is_unknown():
    trusted = parse_trusted_proxies("10.0.0.0/8")
    req = _Req("10.0.0.9", {"x-forwarded-for": "not-an-ip"})
    assert resolve_client_ip(req, trusted) == UNKNOWN


def test_f07_parse_trusted_proxies_rejects_invalid():
    with pytest.raises(ValueError):
        parse_trusted_proxies("10.0.0.0/8, garbage")
    assert parse_trusted_proxies("") == ()
    assert len(parse_trusted_proxies("10.0.0.1, 192.168.0.0/16")) == 2


def test_f07_config_trusted_proxies_parsed_and_validated():
    cfg = load_config(_env(MINI_APP_TRUSTED_PROXIES="10.0.0.0/8, 192.168.1.1"))
    assert "10.0.0.0/8" in cfg.mini_app_trusted_proxies
    with pytest.raises(ConfigError):
        load_config(_env(MINI_APP_TRUSTED_PROXIES="not-a-cidr"))
