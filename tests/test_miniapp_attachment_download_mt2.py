"""OHB2-MT-2 — اختبارات تنزيل المرفق المصادَق من الـ Mini App.

تغطّي مسار الـ backend الحقيقي عبر `TestClient` (تطبيق ASGI فعلي + قاعدة SQLite فعلية +
جذر staging فعلي)، مع `httpx.MockTransport` للـ upstream (تفويض الشات) فقط. المصادقة
حقيقية (`initData` موقَّع محليًّا). مفيش شبكة خارجية ومفيش جهاز حقيقي.

النطاق: مصادقة/تفويض/IDOR، فحص الملف (symlink/نوع/حجم/تطابق)، البثّ المحدود غير الحاجب،
الإغلاق الحتمي للوصفة، وفشل القاعدة المغلق. **مفيش** ادّعاء سلامة محتوى أو توافق جهاز.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import re
import sqlite3
from datetime import datetime, timezone

import httpx
import pytest
from starlette.testclient import TestClient

from bot.attachments import (
    MAX_ATTACHMENT_BYTES,
    StagingStore,
    batch_deadline,
    staging_root_for,
)
from bot.config import Config
from bot.db import Database
from bot.openhands_client import OpenHandsClient
from bot.web import build_web_app
from bot.web.download import (
    DEFAULT_DOWNLOAD_NAME,
    AttachmentDownloadError,
    iter_file_chunks,
    open_staged_file,
    resolve_staged_path,
    safe_download_filename,
)

from tests._miniapp_helpers import BOT_TOKEN, make_init_data

OWNER = 555
OTHER = 999
OWNER_UUID = "owner-uuid-123"
OTHER_UUID = "other-uuid-456"
CID = "c1"
CID2 = "c2"
_TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")
PAYLOAD = b"hello mt-2 attachment payload \xd8\xa7\xd9\x84\xd8\xb9\xd8\xb1\xd8\xa8\xd9\x8a\xd8\xa9"


class MockAPI:
    """upstream مزيّف لتفويض الشات فقط (`/users/me` + `/app-conversations`)."""

    def __init__(self):
        self.conv_owner = OWNER_UUID
        self.convs_present = True

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v1/users/me":
            return httpx.Response(200, json={"id": OWNER_UUID, "role": "owner"})
        if path == "/api/v1/app-conversations":
            if not self.convs_present:
                return httpx.Response(200, json=[])
            convs = []
            for cid in (CID, CID2):
                conv = {"id": cid, "title": "شات " + cid}
                if self.conv_owner is not None:
                    conv["created_by_user_id"] = self.conv_owner
                convs.append(conv)
            return httpx.Response(200, json=convs)
        return httpx.Response(404, json={"detail": "no"})


def make_config(db_path: str, **over) -> Config:
    base = dict(
        telegram_bot_token=BOT_TOKEN,
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({OWNER, OTHER}),
        owner_id=OWNER,
        mini_app_cookie_secure=False,
        db_path=db_path,
    )
    base.update(over)
    return Config(**base)


def build(tmp_path, *, api=None, t0=None, telegram_id=OWNER, conversation_id=CID):
    """ينشئ db + staging + عميل مصادَق، ويخزّن مرفقًا واحدًا `stored` فعليًّا.

    بترجّع (client, db, store, res, tc). `t0` بيسمح بتوليد دفعة منتهية (الافتراضي: الآن).
    """
    db_path = str(tmp_path / "state.sqlite3")
    db = Database(db_path)
    store = StagingStore(db, db_path, max_bytes=MAX_ATTACHMENT_BYTES)
    stamp = t0 or datetime.now(timezone.utc).isoformat()
    db.create_attachment_batch("b1", telegram_id, conversation_id, stamp)
    res = store.store(
        telegram_id=telegram_id,
        batch_id="b1",
        item_id="i1",
        display_name="note.txt",
        chunks=[PAYLOAD],
    )
    assert res.status.value == "stored"
    api = api or MockAPI()
    client = OpenHandsClient(
        "https://example.test", "key", transport=httpx.MockTransport(api.handler)
    )
    tc = TestClient(
        build_web_app(make_config(db_path), db, client=client),
        raise_server_exceptions=False,
    )
    return tc, db, store, res, db_path


def login(tc: TestClient, user_id: int = OWNER) -> None:
    resp = tc.post("/api/v1/auth", json={"initData": make_init_data(user_id)})
    assert resp.status_code == 200


def dl_url(cid=CID, item_id="i1") -> str:
    return f"/api/v1/conversations/{cid}/attachments/{item_id}/download"


# ------------------------------------------------------------------ المصادقة
def test_download_requires_auth(tmp_path):
    tc, *_ = build(tmp_path)
    r = tc.get(dl_url())
    assert r.status_code == 401 and r.json()["error"] == "unauthenticated"


def test_attachments_list_requires_auth(tmp_path):
    tc, *_ = build(tmp_path)
    r = tc.get(f"/api/v1/conversations/{CID}/attachments")
    assert r.status_code == 401 and r.json()["error"] == "unauthenticated"


def test_download_success_returns_exact_bytes(tmp_path):
    tc, _db, _store, res, _ = build(tmp_path)
    login(tc)
    r = tc.get(dl_url())
    assert r.status_code == 200
    assert r.content == PAYLOAD
    assert r.headers["content-type"] == "application/octet-stream"
    assert r.headers["content-disposition"] == 'attachment; filename="note.txt"'
    assert r.headers["content-length"] == str(len(PAYLOAD))
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "no-store"
    # مفيش تسريب مسار/رمز staging في الرد (الرمز مُعتِم ومش من المفروض يظهر).
    assert res.staging_token not in r.content.decode("latin1")
    assert "attachment_staging" not in r.content.decode("latin1")


def test_attachments_list_returns_safe_metadata_only(tmp_path):
    tc, _db, _store, res, _ = build(tmp_path)
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/attachments")
    assert r.status_code == 200
    body = r.json()
    assert body["items"][0]["item_id"] == "i1"
    assert body["items"][0]["display_name"] == "note.txt"
    assert body["items"][0]["size_bytes"] == len(PAYLOAD)
    # مفيش رمز staging ولا مسار ولا محتوى في القايمة.
    assert res.staging_token not in r.text
    assert "attachment_staging" not in r.text


# ------------------------------------------------------------------ التفويض/IDOR
def test_download_unknown_conversation_is_not_found(tmp_path):
    tc, *_ = build(tmp_path)
    login(tc)
    r = tc.get(dl_url(cid="missing"))
    assert r.status_code == 404 and r.json()["error"] == "not_found"


def test_download_other_user_conversation_is_forbidden(tmp_path):
    """شات مملوك لمستخدم تاني (upstream) ⇒ 404 منظّم (مفيش كشف ملكية)."""
    api = MockAPI()
    api.conv_owner = OTHER_UUID
    tc, *_ = build(tmp_path, api=api)
    login(tc)
    r = tc.get(dl_url())
    assert r.status_code in (403, 404)


def test_cross_user_attachment_idor_is_denied(tmp_path):
    """المستخدم OTHER يسجّل دخول ويطلب عنصر دفعة OWNER ⇒ 404 (عزل بالمالك)."""
    tc, *_ = build(tmp_path)
    login(tc, user_id=OTHER)
    r = tc.get(dl_url())
    assert r.status_code == 404 and r.json()["error"] == "not_found"


def test_cross_conversation_attachment_idor_is_denied(tmp_path):
    """العنصر تبع دفعة شات تاني ⇒ 404 (ربط العنصر بالمحادثة)."""
    tc, *_ = build(tmp_path, conversation_id=CID2)
    login(tc)
    # نطلب العنصر عبر CID (مش شات الدفعة CID2) ⇒ رفض.
    r = tc.get(dl_url(cid=CID))
    assert r.status_code == 404 and r.json()["error"] == "not_found"


def test_unknown_item_id_is_not_found(tmp_path):
    tc, *_ = build(tmp_path)
    login(tc)
    r = tc.get(dl_url(item_id="does-not-exist"))
    assert r.status_code == 404 and r.json()["error"] == "not_found"


# ------------------------------------------------------------------ الحالة/المهلة
def test_expired_attachment_is_gone(tmp_path):
    # دفعة انتهت منذ وقت طويل (T0 في الماضي البعيد) ⇒ 410 بلا تمديد (D-15).
    tc, *_ = build(tmp_path, t0="2000-01-01T00:00:00+00:00")
    login(tc)
    r = tc.get(dl_url())
    assert r.status_code == 410 and r.json()["error"] == "expired"


def test_expired_attachment_absent_from_list(tmp_path):
    tc, *_ = build(tmp_path, t0="2000-01-01T00:00:00+00:00")
    login(tc)
    r = tc.get(f"/api/v1/conversations/{CID}/attachments")
    assert r.status_code == 200 and r.json()["items"] == []


def test_reaped_item_is_not_downloadable(tmp_path):
    tc, db, *_ = build(tmp_path)
    assert db.mark_attachment_item_reaped("i1") is True
    login(tc)
    r = tc.get(dl_url())
    assert r.status_code == 404 and r.json()["error"] == "not_found"


def test_batch_not_pending_is_not_downloadable(tmp_path):
    tc, db, *_ = build(tmp_path)
    db.mark_attachment_batch_status("b1", "expired", now="2026-11-15T00:00:00+00:00")
    login(tc)
    r = tc.get(dl_url())
    assert r.status_code == 404 and r.json()["error"] == "not_found"


def test_missing_staged_file_is_not_found(tmp_path):
    tc, _db, store, res, _ = build(tmp_path)
    os.unlink(str(store.root / res.staging_token))
    login(tc)
    r = tc.get(dl_url())
    assert r.status_code == 404 and r.json()["error"] == "not_found"


# ------------------------------------------------------------------ سلامة الملف
def test_symlink_is_rejected(tmp_path):
    """symlink في مكان الملف ⇒ رفض (O_NOFOLLOW / lstat)."""
    tc, _db, store, res, _ = build(tmp_path)
    target = store.root / res.staging_token
    outside = tmp_path / "outside.bin"
    outside.write_bytes(PAYLOAD)
    os.unlink(str(target))
    os.symlink(str(outside), str(target))
    login(tc)
    r = tc.get(dl_url())
    assert r.status_code == 404
    assert r.json()["error"] in ("not_found", "unavailable")


def test_non_regular_file_is_rejected(tmp_path):
    """مجلد في مكان الملف ⇒ رفض (مش ملف عادي)."""
    tc, _db, store, res, _ = build(tmp_path)
    target = store.root / res.staging_token
    os.unlink(str(target))
    os.mkdir(str(target))
    login(tc)
    r = tc.get(dl_url())
    assert r.status_code == 404


def test_size_mismatch_fails_closed(tmp_path):
    """الملف على القرص اتغيّر عن الحجم المخزَّن ⇒ 500 (فشل مغلق، مفيش بثّ)."""
    tc, _db, store, res, _ = build(tmp_path)
    (store.root / res.staging_token).write_bytes(PAYLOAD + b"EXTRA")
    login(tc)
    r = tc.get(dl_url())
    assert r.status_code == 500


def test_oversized_file_is_rejected(tmp_path):
    """ملف أكبر من السقف ⇒ رفض (سقف 3 MiB)."""
    tc, _db, store, res, _ = build(tmp_path)
    (store.root / res.staging_token).write_bytes(b"x" * (MAX_ATTACHMENT_BYTES + 1))
    login(tc)
    r = tc.get(dl_url())
    assert r.status_code == 404


def test_safe_filename_sanitizes_and_defaults():
    assert safe_download_filename("note.txt") == "note.txt"
    assert safe_download_filename("../../etc/passwd") == "passwd"
    assert safe_download_filename("a\r\nb.txt") == "ab.txt"
    assert safe_download_filename("...") == DEFAULT_DOWNLOAD_NAME
    assert safe_download_filename(None) == DEFAULT_DOWNLOAD_NAME
    assert safe_download_filename("ملف.txt") == "txt"  # محارف غير ASCII بتتشال (سلوك آمن)


# ------------------------------------------------------------------ طبقة الوحدة
def test_resolve_staged_path_rejects_bad_token(tmp_path):
    root = tmp_path / "attachment_staging"
    root.mkdir()
    for bad in (None, "", "short", "Z" * 32, "../evil", "a" * 31 + "/"):
        with pytest.raises(AttachmentDownloadError):
            resolve_staged_path(root, bad, expected_size=1, max_bytes=MAX_ATTACHMENT_BYTES)


def test_resolve_staged_path_happy_and_size_mismatch(tmp_path):
    root = tmp_path / "attachment_staging"
    root.mkdir()
    token = "a" * 32
    (root / token).write_bytes(b"12345")
    path, size = resolve_staged_path(
        root, token, expected_size=5, max_bytes=MAX_ATTACHMENT_BYTES
    )
    assert size == 5 and path.endswith(token)
    with pytest.raises(AttachmentDownloadError):
        resolve_staged_path(root, token, expected_size=4, max_bytes=MAX_ATTACHMENT_BYTES)


def test_open_staged_file_rejects_symlink(tmp_path):
    root = tmp_path / "attachment_staging"
    root.mkdir()
    token = "b" * 32
    outside = tmp_path / "outside"
    outside.write_bytes(b"data")
    os.symlink(str(outside), str(root / token))
    with pytest.raises(AttachmentDownloadError):
        open_staged_file(str(root / token), 4, max_bytes=MAX_ATTACHMENT_BYTES)


def test_iter_file_chunks_reads_all_and_closes_fd(tmp_path):
    path = tmp_path / "f.bin"
    path.write_bytes(b"x" * 200000)  # > 2 chunks (64 KiB)
    fd = os.open(str(path), os.O_RDONLY)

    async def run():
        chunks = []
        async for c in iter_file_chunks(fd, 200000):
            chunks.append(c)
        return chunks

    chunks = asyncio.run(run())
    assert b"".join(chunks) == b"x" * 200000
    assert len(chunks) == 4  # 64K,64K,64K,~8K ⇒ bounded chunks
    # الوصفة اتقفلت (أي محاولة قراءة ⇒ OSError).
    with pytest.raises(OSError):
        os.read(fd, 1)


def test_iter_file_chunks_closes_fd_on_cancellation(tmp_path):
    path = tmp_path / "f.bin"
    path.write_bytes(b"y" * 200000)
    fd = os.open(str(path), os.O_RDONLY)

    async def run():
        agen = iter_file_chunks(fd, 200000)
        first = await agen.__anext__()  # قطعة واحدة
        assert first
        await agen.aclose()  # إلغاء/إغلاق مبكر ⇒ finally
        return True

    assert asyncio.run(run())
    with pytest.raises(OSError):
        os.read(fd, 1)


def test_iter_file_chunks_does_not_block_event_loop(tmp_path):
    """F-01: القراءة بتتنفّذ في خيط عامل ⇒ حلقة الأحداث تفضل متجاوبة.

    بنشغّل مُكرِّر يقرأ ملفًا كبيرًا نسبيًّا، وفي نفس الوقت مهمة عدّاد على نفس الحلقة.
    لو القراءة كانت حاجبة، العدّاد ما كانش هيتقدّم بين القطع.
    """
    path = tmp_path / "big.bin"
    path.write_bytes(b"q" * (1024 * 1024))  # 1 MiB ⇒ 16 قطعة
    fd = os.open(str(path), os.O_RDONLY)

    async def run():
        ticks = {"n": 0}
        stop = {"v": False}

        async def ticker():
            while not stop["v"]:
                ticks["n"] += 1
                await asyncio.sleep(0)

        t = asyncio.create_task(ticker())
        got = 0
        async for chunk in iter_file_chunks(fd, 1024 * 1024):
            got += len(chunk)
        stop["v"] = True
        await t
        return got, ticks["n"]

    got, ticks = asyncio.run(run())
    assert got == 1024 * 1024
    # العدّاد لازم يكون اشتغل عدة مرات أثناء البثّ (مفيش حجب كامل).
    assert ticks > 5


def test_iter_file_chunks_detects_truncation(tmp_path):
    path = tmp_path / "f.bin"
    path.write_bytes(b"z" * 100)
    fd = os.open(str(path), os.O_RDONLY)

    async def run():
        # المتوقّع 200 بس الملف 100 ⇒ المفروض يرمي بدل ما يكمّل.
        async for _ in iter_file_chunks(fd, 200):
            pass

    with pytest.raises(AttachmentDownloadError):
        asyncio.run(run())
    with pytest.raises(OSError):
        os.read(fd, 1)  # اتقفلت رغم الاستثناء


def test_resolve_staged_path_uses_real_staging_root(tmp_path):
    """يتأكّد إن `staging_root_for` هو نفس الجذر اللي بيكتب فيه المخزن."""
    db_path = str(tmp_path / "state.sqlite3")
    db = Database(db_path)
    store = StagingStore(db, db_path, max_bytes=MAX_ATTACHMENT_BYTES)
    assert store.root == staging_root_for(db_path)


def test_midstream_unlink_does_not_truncate_or_leak(tmp_path):
    """سباق الحذف: كنس الملف **بعد** الفتح لا يقطع البثّ (الوصفة مفتوحة) ولا يسرّب.

    البايتات بتتقرأ من الوصفة المفتوحة (`fd`)؛ إلغاء الرابط (unlink) مش بيأثّر عليها على
    POSIX، فالرد يكتمل بالحجم الكامل المخزَّن، والوصفة تتقفل في النهاية.
    """
    path = tmp_path / "f.bin"
    payload = b"race" * 20000  # 80 KB
    path.write_bytes(payload)
    fd = os.open(str(path), os.O_RDONLY)

    async def run():
        chunks = []
        agen = iter_file_chunks(fd, len(payload))
        async for c in agen:
            chunks.append(c)
            if len(chunks) == 1:
                os.unlink(str(path))  # حذف وسط البثّ
        return b"".join(chunks)

    got = asyncio.run(run())
    assert got == payload  # اكتمل بالكامل رغم الحذف
    with pytest.raises(OSError):
        os.read(fd, 1)  # الوصفة اتقفلت


# ------------------------------------------------------------------ فشل القاعدة
def test_database_error_fails_closed(tmp_path, monkeypatch):
    tc, db, *_ = build(tmp_path)
    login(tc)

    def boom(*a, **k):
        raise sqlite3.OperationalError("db down")

    monkeypatch.setattr(db, "get_attachment_item", boom)
    r = tc.get(dl_url())
    assert r.status_code == 503


def test_list_database_error_fails_closed_empty(tmp_path, monkeypatch):
    tc, db, *_ = build(tmp_path)
    login(tc)

    def boom(*a, **k):
        raise sqlite3.OperationalError("db down")

    monkeypatch.setattr(db, "latest_pending_attachment_batch", boom)
    r = tc.get(f"/api/v1/conversations/{CID}/attachments")
    assert r.status_code == 200 and r.json()["items"] == []


# ------------------------------------------------------------------ محتوى/سلامة
def test_download_content_matches_staged_file(tmp_path):
    """تحقّق تكاملي: البايتات المنزَّلة تطابق الملف المخزَّن (بلا ادّعاء بصمة)."""
    tc, _db, store, res, _ = build(tmp_path)
    on_disk = (store.root / res.staging_token).read_bytes()
    login(tc)
    r = tc.get(dl_url())
    assert hashlib.sha256(r.content).digest() == hashlib.sha256(on_disk).digest()


def test_batch_deadline_never_extends(tmp_path):
    """D-15: المهلة ثابتة = T0 + 15د (لا تُمدَّد)."""
    t0 = "2026-11-15T00:00:00+00:00"
    d1 = batch_deadline(t0)
    d2 = batch_deadline(t0)
    assert d1 == d2
    assert (d1.isoformat()) == "2026-11-15T00:15:00+00:00"


# ---------------------------------------------------- إغلاق الوصفة عند الانقطاع (ASGI ≥ 2.4)
def _run_stream_scope(response, fd, *, disconnect_after, spec="2.4"):
    """يشغّل استجابة ASGI فعليًّا على حلقة أحداث **واحدة**، ويقطع الاتصال بعد N رسالة.

    الفحص بيحصل **جوه** نفس الحلقة وقبل أي `gc` (عشان إغلاق الحلقة/الـ GC ما يخفيش
    العطل). يرجّع `closed_before_gc` (هل الوصفة اتقفلت حتميًّا أثناء الطلب).
    """

    async def main():
        sent = {"n": 0}

        async def receive():
            await asyncio.sleep(3600)

        async def send(_msg):
            sent["n"] += 1
            if sent["n"] >= disconnect_after:
                raise OSError("broken pipe")

        scope = {
            "type": "http",
            "asgi": {"spec_version": spec},
            "method": "GET",
            "path": "/x",
            "headers": [],
            "query_string": b"",
            "http_version": "1.1",
            "scheme": "http",
            "server": ("t", 80),
            "client": ("c", 1),
        }
        try:
            await response(scope, receive, send)
        except BaseException:  # noqa: BLE001 — ClientDisconnect متوقّع على ASGI ≥ 2.4
            pass
        # فحص الإغلاق **قبل** أي GC وقبل إغلاق الحلقة.
        try:
            os.read(fd, 1)
            return False  # لسه مفتوحة ⇒ تسريب
        except OSError:
            return True  # اتقفلت

    return asyncio.run(main())


def test_owned_streaming_response_closes_fd_on_disconnect(tmp_path):
    """انقطاع العميل على ASGI 2.4 ⇒ الوصفة تتقفل حتميًّا (مش بالـ GC)."""
    from bot.web.download import OwnedStreamingResponse

    path = tmp_path / "big.bin"
    path.write_bytes(b"k" * (1024 * 1024))
    fd = os.open(str(path), os.O_RDONLY)

    resp = OwnedStreamingResponse(iter_file_chunks(fd, 1024 * 1024))
    assert _run_stream_scope(resp, fd, disconnect_after=5) is True


def test_plain_streaming_response_leaks_until_gc(tmp_path):
    """إثبات العطل (توثيقي): `StreamingResponse` العادي **ما بيقفلش** أثناء الطلب.

    الاختبار ده بيثبّت **سبب** الإصلاح: على ASGI 2.4، Starlette ما بتقفلش المُكرِّر غير
    المتزامن عند الانقطاع ⇒ الوصفة تفضل مفتوحة لحد الـ GC. لو Starlette غيّر سلوكه
    مستقبلًا، الاختبار هيفشل ويبان إن `OwnedStreamingResponse` ممكن يتبسّط.
    """
    import gc

    from starlette.responses import StreamingResponse

    path = tmp_path / "big.bin"
    path.write_bytes(b"k" * (1024 * 1024))
    fd = os.open(str(path), os.O_RDONLY)

    resp = StreamingResponse(iter_file_chunks(fd, 1024 * 1024))
    assert _run_stream_scope(resp, fd, disconnect_after=5) is False
    gc.collect()  # ننضّف الوصفة المتسربة
