"""OHB2-N10-28C+28D: دمج عابر للطبقات (صندوق ↔ عميل OpenHands الحقيقي ↔ قاعدة البيانات).

بنستخدم `OpenHandsClient` الحقيقي مع `httpx.MockTransport` (مفيش شبكة) لتغطية المسار
الكامل: شطب/إرسال ← عميل HTTP ← حالة القاعدة، والتأكد إن ردود OpenHands المشوّهة أو
الغامضة ما بتعملش نجاح وهمي ولا إعادة إرسال تلقائية.
"""
import asyncio

import httpx

from bot.db import Database
from bot.openhands_client import OpenHandsClient
from bot.outbox import CreationWorker, OutboxWorker

from tests.test_outbox import Bot, add_pending


def _client(handler):
    return OpenHandsClient("https://example.test", "key", transport=httpx.MockTransport(handler))


# ================================ صندوق: رد غامض ⇒ unknown ومفيش إعادة تلقائية
def test_ambiguous_send_outcome_is_unknown_and_never_auto_resent(tmp_path):
    calls = {"send": 0}

    def handler(request):
        if request.url.path.endswith("/send-message"):
            calls["send"] += 1
            raise httpx.ReadTimeout("timed out")  # النتيجة غامضة (مش رفض)
        # جلب الشات: sandbox جاهز ⇒ نعدّي لمرحلة الـ POST.
        return httpx.Response(200, json=[{"id": "c1", "title": "شات", "sandbox_status": "RUNNING"}])

    db = Database(str(tmp_path / "d.sqlite3"))
    oid = add_pending(db)
    client = _client(handler)
    worker = OutboxWorker(client, db, Bot())

    asyncio.run(worker._tick())
    assert db.get_outbox(oid).status == "unknown"  # غامض، مش sent/failed
    # إعادة الدورة: 'unknown' مش مؤهّل ⇒ مفيش POST تاني.
    asyncio.run(worker._tick())
    assert calls["send"] == 1  # مفيش إعادة إرسال تلقائية


def test_definite_rejection_is_failed_and_not_resent(tmp_path):
    calls = {"send": 0}

    def handler(request):
        if request.url.path.endswith("/send-message"):
            calls["send"] += 1
            return httpx.Response(422, json={"detail": "bad"})
        return httpx.Response(200, json=[{"id": "c1", "title": "شات", "sandbox_status": "RUNNING"}])

    db = Database(str(tmp_path / "d.sqlite3"))
    oid = add_pending(db)
    worker = OutboxWorker(_client(handler), db, Bot())
    asyncio.run(worker._tick())
    assert db.get_outbox(oid).status == "failed"
    asyncio.run(worker._tick())
    assert calls["send"] == 1


def test_redirect_on_send_is_not_success(tmp_path):
    calls = {"send": 0}

    def handler(request):
        if request.url.path.endswith("/send-message"):
            calls["send"] += 1
            return httpx.Response(307, headers={"location": "https://evil.test"})
        return httpx.Response(200, json=[{"id": "c1", "title": "شات", "sandbox_status": "RUNNING"}])

    db = Database(str(tmp_path / "d.sqlite3"))
    oid = add_pending(db)
    worker = OutboxWorker(_client(handler), db, Bot())
    asyncio.run(worker._tick())
    # 307 (غير دائم) ⇒ مش 4xx مؤكد ⇒ غامض 'unknown' (مش 'sent').
    assert db.get_outbox(oid).status == "unknown"
    assert calls["send"] == 1  # مفيش متابعة لإعادة التوجيه (طلب واحد بس)


def test_successful_send_via_real_client_is_sent(tmp_path):
    def handler(request):
        if request.url.path.endswith("/send-message"):
            return httpx.Response(200, json={})
        return httpx.Response(200, json=[{"id": "c1", "title": "شات",
                                          "execution_status": "running",
                                          "sandbox_status": "RUNNING"}])

    db = Database(str(tmp_path / "d.sqlite3"))
    oid = add_pending(db)
    worker = OutboxWorker(_client(handler), db, Bot())
    asyncio.run(worker._tick())
    assert db.get_outbox(oid).status == "sent"


# ======================= إنشاء الشات: رد مشوّه ما بيعملش شات مكرّر عند الاستعادة
def test_malformed_start_response_then_restart_does_not_duplicate(tmp_path):
    posts = {"n": 0}

    def handler(request):
        if request.method == "POST" and request.url.path == "/api/v1/app-conversations":
            posts["n"] += 1
            return httpx.Response(200, content=b"<html>proxy</html>")
        return httpx.Response(200, json={})

    db = Database(str(tmp_path / "d.sqlite3"))
    jid = db.add_creation_job(99, "o/r", "برومت", "t")
    worker = CreationWorker(_client(handler), db, Bot(), "https://app.all-hands.dev")
    asyncio.run(worker._tick())
    assert db.get_creation_job(jid).status == "unknown"
    assert posts["n"] == 1
    # إعادة تشغيل: 'unknown' مش مؤهّل ⇒ مفيش POST تاني (مفيش شات مكرّر).
    worker2 = CreationWorker(_client(handler), db, Bot(), "https://app.all-hands.dev")
    asyncio.run(worker2._tick())
    assert posts["n"] == 1


# ================================ تسوية ما بتكرّرش العملية وما بتعملش شطب وهمي
def test_reconcile_does_not_duplicate_or_false_cancel(tmp_path):
    from bot.db import Database
    from tests.test_batch_c_integration import ORIGIN, MockAPI, login, make_app

    api = MockAPI()
    db = Database(str(tmp_path / "d.sqlite3"))
    tc = make_app(api, db=db)
    login(tc)

    # سجل صندوق غامض (ممكن يكون اتبعت).
    oid = db.add_outbox("c1", 555, "x", "2026-01-01T00:00:00+00:00")
    db.set_outbox_status(oid, "unknown", "2026-01-01T00:00:01+00:00")

    r = tc.post("/api/v1/operations/outbox/reconcile", json={"id": oid, "action": "discard"},
                headers={"origin": ORIGIN})
    # الشطب على سجل ممكن يكون بدأ ⇒ not_confirmed (مفيش شطب وهمي، مفيش تكرار).
    assert r.status_code == 200 and r.json().get("cancellation") == "not_confirmed"
    assert db.get_outbox(oid).status == "unknown"  # الحالة محفوظة
    assert db.count_outbox() == 1  # مفيش سجل جديد
