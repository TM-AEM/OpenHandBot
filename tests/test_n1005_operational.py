"""OHB2-N10-05 — تحقّق تشغيلي شامل (end-to-end / شبكة ضعيفة / فشل عابر / تعافي / تزامن /
موارد منخفضة) على الإصدار المدمج.

التركيز: سدّ فجوات التحقّق القابلة لإعادة الإنتاج عبر **مسارات الكود الحقيقية**
(العميل الحقيقي `OpenHandsClient` + `httpx.MockTransport`، والـ workers الحقيقيون)،
بدل محاكاة النتائج. مفيش شبكة حقيقية ومفيش خدمات خارجية.

بند الأثر OHB2-N10-05: تصنيف 429 كـ "رفض دائم" كان بيحوّل البرومت/الشات لـ 'failed'
(نهائي) عند rate limit عابر — مخالفًا لـ `errors.describe_status` والـ Runbook. الاختبارات
هنا بتثبّت التصنيف الصحيح + at-most-once.
"""
import asyncio
import os
import tempfile

import httpx
import pytest

from bot.db import Database
from bot.errors import ApiError
from bot.openhands_client import OpenHandsClient
from bot.outbox import (
    CreationWorker,
    OutboxWorker,
    is_permanent,
    safe_send,
)
from telegram.error import TelegramError


# =====================================================================
# أدوات مشتركة: قاعدة مؤقتة، بوت fake، وعميل حقيقي فوق MockTransport
# =====================================================================
def _db():
    path = os.path.join(tempfile.mkdtemp(), "t.sqlite3")
    return Database(path)


class _Bot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id=None, text=None, **kw):
        self.sent.append(text)


def _client(handler, timeout: float = 30.0):
    return OpenHandsClient("https://example.test", "key", timeout=timeout,
                           transport=httpx.MockTransport(handler))


def _running_conv(cid="c1"):
    return {"id": cid, "title": "شات", "execution_status": "running", "sandbox_status": "RUNNING"}


def _add_outbox(db, cid="c1", chat_id=99, text="برومت"):
    return db.add_outbox(cid, chat_id, text, "2026-01-01T00:00:00+00:00")


def _drive_outbox(db, handler, bot=None, timeout=30.0):
    """يشغّل دورة OutboxWorker حقيقية فوق عميل حقيقي (MockTransport)."""

    async def go():
        client = _client(handler, timeout=timeout)
        worker = OutboxWorker(client, db, bot or _Bot())
        try:
            await worker._tick()
        finally:
            await client.aclose()

    asyncio.run(go())
    return db.get_outbox(1)


def _mature(monkeypatch):
    """يعطّل نافذة التجميع (القرار 2) عشان الحجز يحصل فورًا."""
    monkeypatch.setattr("bot.outbox.grouping_mature_before", lambda *a, **k: "9999-12-31T23:59:59+00:00")


# =====================================================================
# A. تكامل تيليجرام: فشل الإرسال العابر + الإصلاح المؤكّد
# =====================================================================
def test_safe_send_swallows_telegram_error():
    """`safe_send` ما بترميش على أي `TelegramError` (فشل الإشعار ما يكسرش حالة الصندوق)."""
    class Bot:
        async def send_message(self, **kw):
            raise TelegramError("boom")

    asyncio.run(safe_send(Bot(), 1, "نص"))  # ما يرميش


def test_outbox_post_network_timeout_is_unknown_not_resent(tmp_path, monkeypatch):
    """مهلة شبكة أثناء POST: غامض ⇒ unknown، ومستحيل يتعاود تلقائيًا (at-most-once)."""
    _mature(monkeypatch)
    db = _db()
    _add_outbox(db)

    def handler(request):
        if request.url.path.endswith("/send-message"):
            raise httpx.ReadTimeout("timeout")
        if request.url.path.endswith("/app-conversations"):
            return httpx.Response(200, json=[_running_conv()])
        return httpx.Response(200, json={})

    item = _drive_outbox(db, handler)
    assert item.status == "unknown"
    # دورة تانية: مش هيتاخد تاني (unknown مش مؤهّل).
    _drive_outbox(db, handler)
    assert db.get_outbox(1).status == "unknown"


def test_outbox_post_connect_error_is_unknown(tmp_path, monkeypatch):
    """انقطاع اتصال أثناء POST ⇒ unknown (غامض)، مش إعادة تلقائية."""
    _mature(monkeypatch)
    db = _db()
    _add_outbox(db)

    def handler(request):
        if request.url.path.endswith("/send-message"):
            raise httpx.ConnectError("down")
        if request.url.path.endswith("/app-conversations"):
            return httpx.Response(200, json=[_running_conv()])
        return httpx.Response(200, json={})

    item = _drive_outbox(db, handler)
    assert item.status == "unknown"


# =====================================================================
# B. OpenHands API: 429/5xx — التصنيف الصحيح + عدم الإرسال المزدوج
# =====================================================================
@pytest.mark.parametrize("status", [500, 502, 503])
def test_outbox_post_5xx_is_unknown_not_failed(tmp_path, monkeypatch, status):
    """5xx عابر أثناء POST ⇒ unknown (مش failed)، مايتعادش تلقائيًا."""
    _mature(monkeypatch)
    db = _db()
    _add_outbox(db)

    def handler(request):
        if request.url.path.endswith("/send-message"):
            return httpx.Response(status, json={"detail": "boom"})
        if request.url.path.endswith("/app-conversations"):
            return httpx.Response(200, json=[_running_conv()])
        return httpx.Response(200, json={})

    item = _drive_outbox(db, handler)
    assert item.status == "unknown"
    assert item.attempts == 0  # الـ POST بدأ ⇒ مفيش استهلاك عدّاد المحاولات الآمنة


def test_outbox_post_429_is_unknown_not_failed(tmp_path, monkeypatch):
    """OHB2-N10-05: 429 على POST **مش** رفض دائم ⇒ unknown (مش failed).

    الغموض بعد بدء الـ POST هو اللي بيحمي at-most-once (مايتعادش تلقائيًا)، مش تصنيف الفشل.
    """
    _mature(monkeypatch)
    db = _db()
    _add_outbox(db)

    def handler(request):
        if request.url.path.endswith("/send-message"):
            return httpx.Response(429, json={"detail": "rate limited"})
        if request.url.path.endswith("/app-conversations"):
            return httpx.Response(200, json=[_running_conv()])
        return httpx.Response(200, json={})

    item = _drive_outbox(db, handler)
    assert item.status == "unknown"          # كان 'failed' قبل الإصلاح
    assert item.status != "failed"
    # مش هيتاخد تاني، فمفيش إرسال مزدوج.
    _drive_outbox(db, handler)
    assert db.get_outbox(1).status == "unknown"


def test_outbox_pre_post_429_is_retryable_pending(tmp_path, monkeypatch):
    """429 قبل بدء الـ POST (قراءة الشات): الإرسال مابدأش ⇒ آمن ⇒ يفضل pending ويتعاود."""
    _mature(monkeypatch)
    db = _db()
    _add_outbox(db)

    def handler(request):
        # أي نداء لقراءة الشات يفشل بـ 429 قبل أي POST.
        if request.url.path.endswith("/app-conversations"):
            return httpx.Response(429, json={"detail": "rate limited"})
        return httpx.Response(200, json={})

    item = _drive_outbox(db, handler)
    assert item.status == "pending"          # آمن يتعاود
    assert item.attempts == 1                # استُهلك عدّاد المحاولة الآمنة


def test_outbox_post_422_is_failed(tmp_path, monkeypatch):
    """422 (طلب غير صحيح) رفض دائم مؤكّد ⇒ failed (مفيش إعادة)."""
    _mature(monkeypatch)
    db = _db()
    _add_outbox(db)

    def handler(request):
        if request.url.path.endswith("/send-message"):
            return httpx.Response(422, json={"detail": "bad"})
        if request.url.path.endswith("/app-conversations"):
            return httpx.Response(200, json=[_running_conv()])
        return httpx.Response(200, json={})

    item = _drive_outbox(db, handler)
    assert item.status == "failed"


def test_is_permanent_excludes_429():
    """تصنيف الفشل: 429 مؤقت (مش دائم)، وباقي 4xx دائم، و5xx/الشبكة غامض."""
    assert is_permanent(ApiError("rl", 429)) is False
    assert is_permanent(ApiError("bad", 400)) is True
    assert is_permanent(ApiError("unprocessable", 422)) is True
    assert is_permanent(ApiError("forbidden", 403)) is True
    assert is_permanent(ApiError("server", 500)) is False
    assert is_permanent(ApiError("gateway", 503)) is False
    assert is_permanent(ApiError("net")) is False  # بلا status ⇒ غامض


def test_outbox_timeout_is_bounded_not_hung(tmp_path, monkeypatch):
    """مهلة قراءة الشات (ReadTimeout) بتتحوّل لخطأ API آمن سريعًا، مش تعليق."""
    _mature(monkeypatch)
    db = _db()
    _add_outbox(db)

    def handler(request):
        raise httpx.ReadTimeout("timeout")

    item = _drive_outbox(db, handler, timeout=0.5)
    # فشل قبل الـ POST ⇒ آمن ⇒ pending (ومافيش تعليق).
    assert item.status == "pending"


# =====================================================================
# C. إنشاء الشات الجديد: نفس تصنيف 429 (مسار مشترك عبر is_permanent)
# =====================================================================
def test_creation_429_is_unknown_not_failed(tmp_path):
    """429 على POST بدء الشات ⇒ unknown (مش failed)."""
    db = _db()
    db.add_creation_job(99, "o/r", "برومت", "2026-01-01T00:00:00+00:00")

    class Client:
        async def start_conversation(self, text, repo, branch=None):
            raise ApiError("rate limited", 429)

    worker = CreationWorker(Client(), db, _Bot(), "https://app.all-hands.dev")
    asyncio.run(worker._tick())
    assert db.get_creation_job(1).status == "unknown"


def test_creation_422_is_failed(tmp_path):
    """422 على POST بدء الشات ⇒ failed (رفض دائم مؤكّد)."""
    db = _db()
    db.add_creation_job(99, "o/r", "برومت", "2026-01-01T00:00:00+00:00")

    class Client:
        async def start_conversation(self, text, repo, branch=None):
            raise ApiError("bad", 422)

    worker = CreationWorker(Client(), db, _Bot(), "https://app.all-hands.dev")
    asyncio.run(worker._tick())
    assert db.get_creation_job(1).status == "failed"


# =====================================================================
# D. تزامن SQLite: كاتب متزامن (قاعدة منفصلة) ما بيكسرش التسجيل
# =====================================================================
def test_concurrent_writer_does_not_break_outbox_recording(tmp_path):
    """كاتب تاني على نفس ملف القاعدة (WAL + busy_timeout) ما يمنعش تسجيل 'pending'."""
    path = str(tmp_path / "t.sqlite3")
    db = Database(path)
    other = Database(path)  # اتصال تاني لنفس الملف (كاتب متزامن)
    other.add_outbox("cX", 1, "من الكاتب التاني", "2026-01-01T00:00:00+00:00")
    oid = db.add_outbox("c1", 99, "برومت", "2026-01-01T00:00:00+00:00")
    assert db.get_outbox(oid).status == "pending"
    other.close()
    db.close()


# =====================================================================
# E. موارد منخفضة: حدود ثابتة (بلا شبكة) — تُثبت عدم النمو غير المحدود
# =====================================================================
def test_exchange_and_file_bounds_are_finite():
    """حدود الذاكرة ثابتة وموجودة (مراجعة موارد منخفضة بلا تشغيل)."""
    from bot import file_cache, openhands_client
    from bot.handlers import EXCHANGE_CACHE_MAX
    from bot.web.ratelimit import Limit, SlidingWindowLimiter

    assert file_cache.MAX_ENTRIES > 0
    assert file_cache.MAX_TOTAL_CHARS > 0
    assert EXCHANGE_CACHE_MAX > 0
    assert openhands_client.MAX_FILE_RESPONSE_BYTES > 0
    assert openhands_client.MAX_EXPORT_BYTES > 0
    limiter = SlidingWindowLimiter([Limit(max_events=2, window_seconds=60)], max_keys=3)
    for i in range(50):
        limiter.allow(f"key-{i}", now=float(i))
    assert len(limiter._events) <= 3  # المفاتيح محدودة (طرد LRU)


def test_file_cache_stays_bounded_under_churn():
    """ذاكرة ملفات الشاتات ما تتعدّاش الحد حتى مع إدخال/إخراج متكرر."""
    from bot.file_cache import FileCache

    cache = FileCache(max_entries=4, max_total_chars=10_000)
    for i in range(50):
        cache.put(f"c{i}", ["a.txt", "b.txt"])
    assert len(cache) <= 4


# =====================================================================
# F. تعافي إعادة التشغيل: حالة 'sending' متروكة ⇒ unknown (بلا إرسال مزدوج)
# =====================================================================
def test_outbox_recovery_leaves_no_resend_after_restart(tmp_path):
    """سجل 'sending' من إعادة تشغيل ⇒ 'unknown' + إشعار، ومستحيل يتبعت تاني."""
    from types import SimpleNamespace

    from bot.outbox import outbox_recover

    db = _db()
    oid = _add_outbox(db)
    db.set_outbox_status(oid, "sending", "2026-01-01T00:00:00+00:00")
    bot = _Bot()
    app = SimpleNamespace(bot_data={"db": db}, bot=bot)
    asyncio.run(outbox_recover(app))
    assert db.get_outbox(oid).status == "unknown"
    assert bot.sent  # المستخدم اتنبّه إن فيه برومت ممكن يكون اتبعت
    # بعد التعافي، الحجز مش هيرجع السجل ده (unknown مش مؤهّل).
    assert db.claim_outbox("2026-01-01T00:00:01+00:00") is None
