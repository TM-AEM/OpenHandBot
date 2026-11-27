"""OHB2-REPAIR-PLAN-01 — حدود الموارد والـ staging (FIX-01 … FIX-04).

تغطّي الإصلاحات الأربعة بلا تغيير المعمارية أو سياسة المرفقات:
- **FIX-01**: تنزيل تيليجرام متدفّق بسقف بايت صلب (يوقف التنزيل فورًا عند التجاوز).
- **FIX-02**: حصر التنزيلات المتزامنة (semaphore) — لا يتجاوز `MAX_CONCURRENT_DOWNLOADS`.
- **FIX-03**: سقف لكل دفعة (عدد) وسقف كلي للبايتات ⇒ رفض مغلق (`REJECTED_QUOTA`).
- **FIX-04**: فرض صلاحية جذر الـ staging (0700) يفشل مقفولًا.

معزولة (tmp_path + sqlite مؤقّت) وبنفس أدوات HTTP الحقيقية المستخدمة في اختبارات
`test_real_http_file_download.py` (سوكيت TCP حقيقي) لمسار البثّ.
"""

import asyncio
import os
from datetime import datetime, timezone

import httpx
import pytest
from telegram import File

from bot import handlers
from bot.attachments import (
    AttachmentService,
    AttachmentTooLargeError,
    StageStatus,
    StagingError,
    StagingStore,
    ensure_staging_root,
)
from bot.db import ATTACHMENT_ITEM_STORED, Database
from bot.files import IdentityCache

from tests._real_http import RealHTTPServer, chunked_response, http_response

OWNER_ID = 111
OWNER_UUID = "11111111-2222-3333-4444-555555555555"
CID = "11111111222233334444555566667777"
T0 = "2026-11-11T00:00:00+00:00"
_TEST_NOW = datetime(2026, 11, 11, 0, 5, tzinfo=timezone.utc)


class FakeClient:
    """عميل OpenHands مزيّف: هوية مالك + محادثة مملوكة (مفيش شبكة)."""

    def __init__(self, owner=OWNER_UUID):
        self.owner = owner

    async def get_current_user(self):
        return {"id": self.owner}

    async def get_conversations(self, ids):
        return [{"id": CID, "created_by_user_id": self.owner, "title": "A"} for _ in ids]


# ------------------------------------------------------------------ مساعدات
def make_store(tmp_path, **kw):
    db_path = str(tmp_path / "state.sqlite3")
    db = Database(db_path)
    kw.setdefault("clock", lambda: _TEST_NOW)
    store = StagingStore(db, db_path, **kw)
    return db, store


def add_batch(db, batch_id="b1", telegram_id=OWNER_ID, conversation_id=CID):
    db.create_attachment_batch(batch_id, telegram_id, conversation_id, T0)


class _FakeRequest:
    def __init__(self, client):
        self._client = client


class _FakeBot:
    """بوت مزيّف بحدّ أدنى: عميل httpx حقيقي + عدّاد تنزيلات متزامنة."""

    def __init__(self, client, tg_file, *, delay=0.0):
        self.request = _FakeRequest(client)
        self._file = tg_file
        self._delay = delay
        self.entered = 0
        self.max_entered = 0
        self.get_file_calls = 0

    async def get_file(self, file_id=None, **kw):
        self.get_file_calls += 1
        self.entered += 1
        self.max_entered = max(self.max_entered, self.entered)
        try:
            if self._delay:
                await asyncio.sleep(self._delay)
            return self._file
        finally:
            self.entered -= 1


class _FakeCtx:
    def __init__(self, bot):
        self.bot = bot


def _run(coro):
    return asyncio.run(coro)


# =============================================================== FIX-04 (fail closed)
def test_ensure_root_fixes_wrong_mode(tmp_path):
    """جذر بصلاحية غلط ⇒ تُفرض 0700 (المسار السعيد)."""
    root = tmp_path / "attachment_staging"
    root.mkdir(mode=0o755)
    os.chmod(str(root), 0o755)
    assert ensure_staging_root(root) == root
    assert (os.stat(str(root)).st_mode & 0o777) == 0o700


def test_ensure_root_fails_closed_when_chmod_fails(tmp_path, monkeypatch):
    """فشل فرض الصلاحية ⇒ `StagingError` (مفيش ابتلاع صامت)."""
    root = tmp_path / "attachment_staging"
    root.mkdir(mode=0o755)
    os.chmod(str(root), 0o755)

    def boom(path, mode):
        raise OSError("chmod not permitted")

    monkeypatch.setattr(os, "chmod", boom)
    with pytest.raises(StagingError):
        ensure_staging_root(root)


def test_ensure_root_fails_closed_when_mode_still_wrong(tmp_path, monkeypatch):
    """الـ chmod مايحقّقش 0700 (يفشل بصمت) ⇒ رفض مغلق بعد الفحص."""
    root = tmp_path / "attachment_staging"
    root.mkdir(mode=0o755)
    os.chmod(str(root), 0o755)
    monkeypatch.setattr(os, "chmod", lambda path, mode: None)  # لا يغيّر شيئًا
    with pytest.raises(StagingError):
        ensure_staging_root(root)


def test_store_write_failed_when_root_mode_unenforceable(tmp_path, monkeypatch):
    """تخزين على جذر لا يمكن فرض 0700 عليه ⇒ `WRITE_FAILED` (فشل مغلق، بلا `stored`)."""
    db, store = make_store(tmp_path)
    add_batch(db)
    root = store.ensure_root()
    os.chmod(str(root), 0o755)

    def boom(path, mode):
        raise OSError("chmod not permitted")

    monkeypatch.setattr(os, "chmod", boom)
    res = store.store(telegram_id=OWNER_ID, batch_id="b1", item_id="i1",
                      display_name="a.txt", chunks=[b"data"])
    assert res.status is StageStatus.WRITE_FAILED
    assert list(root.iterdir()) == []
    assert db.list_attachment_items("b1") == []


# =============================================================== FIX-03 (quotas)
def test_batch_item_quota_rejects_extra_item(tmp_path):
    """تجاوز سقف عدد عناصر الدفعة ⇒ `REJECTED_QUOTA` (بلا كتابة ملف ثالث)."""
    db, store = make_store(tmp_path, max_items_per_batch=2)
    add_batch(db)
    r1 = store.store(telegram_id=OWNER_ID, batch_id="b1", item_id="i1",
                     display_name="a.txt", chunks=[b"1"])
    r2 = store.store(telegram_id=OWNER_ID, batch_id="b1", item_id="i2",
                     display_name="b.txt", chunks=[b"2"])
    assert r1.status is StageStatus.STORED and r2.status is StageStatus.STORED
    r3 = store.store(telegram_id=OWNER_ID, batch_id="b1", item_id="i3",
                     display_name="c.txt", chunks=[b"3"])
    assert r3.status is StageStatus.REJECTED_QUOTA
    assert len(db.list_attachment_items("b1")) == 2
    assert sorted(p.name for p in store.root.iterdir()) == sorted(
        [r1.staging_token, r2.staging_token]
    )


def test_batch_item_quota_applies_with_row_created(tmp_path):
    """مسار A2 (`row_created=True`): العدّ على **الملفات الفعلية**؛ الصف مُدرج (بالتوكن)
    لكن الملف الجديد لسه مش موجود ⇒ يتخطّى السقف ⇒ رفض مغلق (بلا كتابة ملف ثالث)."""
    db, store = make_store(tmp_path, max_items_per_batch=2)
    add_batch(db)
    for i, tok in (("i1", "a" * 32), ("i2", "b" * 32)):
        db.add_attachment_item(i, "b1", staging_token=tok, display_name="a.txt", status="pending")
        res = store.store(telegram_id=OWNER_ID, batch_id="b1", item_id=i, staging_token=tok,
                          display_name="a.txt", chunks=[b"x"], row_created=True)
        assert res.status is StageStatus.STORED
    # الصف الثالث مُدرج (row-first) لكن ملفات الدفعة الفعلية (2) عند السقف ⇒ رفض مغلق.
    db.add_attachment_item("i3", "b1", staging_token="c" * 32, display_name="a.txt", status="pending")
    res = store.store(telegram_id=OWNER_ID, batch_id="b1", item_id="i3", staging_token="c" * 32,
                      display_name="a.txt", chunks=[b"x"], row_created=True)
    assert res.status is StageStatus.REJECTED_QUOTA
    assert len(list(store.root.iterdir())) == 2


def test_total_staging_bytes_quota_rejects_overflow(tmp_path):
    """تجاوز السقف الكلي لبايتات الـ staging ⇒ `REJECTED_QUOTA` (الملف التاني مش بيتكتب)."""
    db, store = make_store(tmp_path, max_total_bytes=10)
    add_batch(db)
    r1 = store.store(telegram_id=OWNER_ID, batch_id="b1", item_id="i1",
                     display_name="a.txt", chunks=[b"12345678"])  # 8 ≤ 10
    assert r1.status is StageStatus.STORED
    r2 = store.store(telegram_id=OWNER_ID, batch_id="b1", item_id="i2",
                     display_name="b.txt", chunks=[b"123456"])  # 8+6 > 10 ⇒ رفض
    assert r2.status is StageStatus.REJECTED_QUOTA
    assert len(list(store.root.iterdir())) == 1


def test_total_staging_bytes_quota_rejects_when_full(tmp_path):
    """الجذر مليان بالكامل ⇒ رفض مباشر (بلا محاولة كتابة)."""
    db, store = make_store(tmp_path, max_total_bytes=4)
    add_batch(db)
    r1 = store.store(telegram_id=OWNER_ID, batch_id="b1", item_id="i1",
                     display_name="a.txt", chunks=[b"1234"])
    assert r1.status is StageStatus.STORED
    r2 = store.store(telegram_id=OWNER_ID, batch_id="b1", item_id="i2",
                     display_name="b.txt", chunks=[b"5"])
    assert r2.status is StageStatus.REJECTED_QUOTA


def test_quota_defaults_are_disabled(tmp_path):
    """FIX-R01/Option A: افتراضيًّا الحصص **معطّلة** (`None`) ومفيش فرض؛ التخزين العادي شغّال."""
    db, store = make_store(tmp_path)
    add_batch(db)
    assert store.max_items_per_batch is None
    assert store.max_total_bytes is None
    assert store.max_bytes_per_batch is None
    assert store.quota_enabled is False
    res = store.store(telegram_id=OWNER_ID, batch_id="b1", item_id="i1",
                      display_name="a.txt", chunks=[b"hello"])
    assert res.status is StageStatus.STORED


# =============================================================== FIX-01 (streaming)
def _tg_file(url):
    return File(file_id="f1", file_unique_id="u1", file_size=None, file_path=url)


def test_stream_download_exact_bytes_under_cap(tmp_path):
    """تنزيل متدفّق داخل السقف ⇒ البايتات مطابقة حرفيًا."""
    payload = b"hello world" * 100
    srv = RealHTTPServer(lambda _r: http_response(200, body=payload))
    try:
        client = httpx.AsyncClient()
        bot = _FakeBot(client, _tg_file(f"{srv.url}/file"))
        ctx = _FakeCtx(bot)
        chunks = _run(handlers._download_attachment_chunks(ctx, "f1", 1_000_000))
        assert b"".join(chunks) == payload
        _run(client.aclose())
    finally:
        srv.shutdown()


def test_stream_download_stops_at_hard_cap(tmp_path):
    """ملف أكبر من السقف ⇒ `AttachmentTooLargeError` والتنزيل يوقف بدري."""
    payload = b"x" * (64 * 1024 * 4)
    srv = RealHTTPServer(lambda _r: http_response(200, body=payload))
    try:
        client = httpx.AsyncClient()
        bot = _FakeBot(client, _tg_file(f"{srv.url}/file"))
        ctx = _FakeCtx(bot)
        with pytest.raises(AttachmentTooLargeError):
            _run(handlers._download_attachment_chunks(ctx, "f1", 1000))
        _run(client.aclose())
    finally:
        srv.shutdown()


def test_stream_download_oversize_chunked(tmp_path):
    """رد chunked يتجاوز السقف ⇒ رفض (العدّ التراكمي على البايتات الخام)."""
    srv = RealHTTPServer(lambda _r: chunked_response([b"y" * 500, b"z" * 500]))
    try:
        client = httpx.AsyncClient()
        bot = _FakeBot(client, _tg_file(f"{srv.url}/file"))
        ctx = _FakeCtx(bot)
        with pytest.raises(AttachmentTooLargeError):
            _run(handlers._download_attachment_chunks(ctx, "f1", 700))
        _run(client.aclose())
    finally:
        srv.shutdown()


def test_stream_download_rejects_redirect():
    """3xx إعادة توجيه ⇒ رفض آمن (`StagingError`) بدل تفسير جسم الـ redirect كمحتوى."""
    srv = RealHTTPServer(lambda _r: http_response(
        302, headers={"Location": "http://example.invalid/elsewhere"}, body=b""
    ))
    try:
        client = httpx.AsyncClient()
        bot = _FakeBot(client, _tg_file(f"{srv.url}/file"))
        ctx = _FakeCtx(bot)
        with pytest.raises(StagingError):
            _run(handlers._download_attachment_chunks(ctx, "f1", 1_000_000))
        _run(client.aclose())
    finally:
        srv.shutdown()


def test_stream_download_rejects_unexpected_content_encoding():
    """`Content-Encoding` غير `identity` ⇒ رفض آمن (مفيش تخزين بايتات مضغوطة)."""
    srv = RealHTTPServer(lambda _r: http_response(
        200, headers={"Content-Encoding": "gzip"}, body=b"not-really-gzip"
    ))
    try:
        client = httpx.AsyncClient()
        bot = _FakeBot(client, _tg_file(f"{srv.url}/file"))
        ctx = _FakeCtx(bot)
        with pytest.raises(StagingError):
            _run(handlers._download_attachment_chunks(ctx, "f1", 1_000_000))
        _run(client.aclose())
    finally:
        srv.shutdown()


def test_stream_download_local_file_path_capped(tmp_path):
    """مسار محلي (سيرفر Bot API) ⇒ قراءة متدفّقة مقيّدة (نفس سلوك البثّ)."""
    local = tmp_path / "local.bin"
    local.write_bytes(b"abcdef")
    bot = _FakeBot(None, _tg_file(str(local)))  # مفيش عميل httpx ⇒ مسار محلي
    ctx = _FakeCtx(bot)
    chunks = _run(handlers._download_attachment_chunks(ctx, "f1", 100))
    assert b"".join(chunks) == b"abcdef"
    with pytest.raises(AttachmentTooLargeError):
        _run(handlers._download_attachment_chunks(ctx, "f1", 3))


def test_accept_propagates_transport_failure(tmp_path):
    """فشل نقل (مش حجم) ⇒ ينتشر من `accept` (المستدعي يسجّله فشل، مش نجاح كاذب)."""
    db, store = make_store(tmp_path)
    add_batch(db)
    client = FakeClient()
    service = AttachmentService(db, store, client, IdentityCache(client))

    async def chunks_factory():
        raise StagingError("transport")

    with pytest.raises(StagingError):
        _run(service.accept(
            telegram_id=OWNER_ID, conversation_id=CID, display_name="a.txt",
            declared_size=None, update_id=None, now=datetime(2026, 11, 11, tzinfo=timezone.utc),
            chunks_factory=chunks_factory,
        ))


def test_accept_translates_too_large_to_rejected_size(tmp_path):
    """`accept` يترجم `AttachmentTooLargeError` ⇒ `REJECTED_SIZE` (العنصر يفضل pending)."""
    db, store = make_store(tmp_path)
    add_batch(db)
    client = FakeClient()
    service = AttachmentService(db, store, client, IdentityCache(client))

    async def chunks_factory():
        raise AttachmentTooLargeError()

    res = _run(service.accept(
        telegram_id=OWNER_ID, conversation_id=CID, display_name="a.txt",
        declared_size=None, update_id=None, now=datetime(2026, 11, 11, tzinfo=timezone.utc),
        chunks_factory=chunks_factory,
    ))
    assert res.stage is StageStatus.REJECTED_SIZE
    items = db.list_attachment_items(res.batch_id)
    assert len(items) == 1 and items[0].status != ATTACHMENT_ITEM_STORED


# =============================================================== FIX-02 (concurrency)
def test_concurrent_downloads_are_bounded(tmp_path):
    """عدد التنزيلات المتزامنة لا يتجاوز `MAX_CONCURRENT_DOWNLOADS`."""
    srv = RealHTTPServer(lambda _r: http_response(200, body=b"ok"))
    try:
        client = httpx.AsyncClient()
        bot = _FakeBot(client, _tg_file(f"{srv.url}/file"), delay=0.05)
        ctx = _FakeCtx(bot)

        async def main():
            tasks = [handlers._download_attachment_chunks(ctx, "f1", 1000) for _ in range(12)]
            await asyncio.gather(*tasks)

        _run(main())
        assert bot.max_entered <= handlers.MAX_CONCURRENT_DOWNLOADS
        assert bot.max_entered >= 2  # التزامن متاح فعلاً (مش متسلسل تمامًا)
        assert bot.get_file_calls == 12
        _run(client.aclose())
    finally:
        srv.shutdown()


def test_download_semaphore_bound_is_positive():
    assert handlers.MAX_CONCURRENT_DOWNLOADS >= 1


# =============================================================== FIX-03 (handler reply)
def test_handler_quota_reply_on_full_batch(tmp_path, monkeypatch):
    """دفعة وصلت السقف ⇒ الملف التاني ياخد رد السقف، والعنصر مايتخزّنش (fail closed)."""
    from tests.test_attachment_batch_lifecycle_a2 import CID as A2_CID, OWNER_ID as A2_OWNER, _harness

    harness = _harness(tmp_path, monkeypatch)
    db_path = harness.app.bot_data["config"].db_path
    harness.app.bot_data["attachment_store"] = StagingStore(
        harness.db, db_path, max_items_per_batch=1, clock=lambda: _TEST_NOW
    )
    harness.db.set_last_accessed_conversation(A2_OWNER, A2_CID)
    harness.process(harness.document_update(9901))
    harness.process(harness.document_update(9902))
    assert harness.replies[0] == handlers.ATTACHMENT_ACCEPTED_TEXT
    assert harness.replies[1] == handlers.ATTACHMENT_QUOTA_TEXT
    batch_id = harness.db._conn.execute(
        "SELECT batch_id FROM attachment_batches"
    ).fetchone()["batch_id"]
    items = harness.db.list_attachment_items(batch_id)
    assert sum(1 for i in items if i.status == ATTACHMENT_ITEM_STORED) == 1
