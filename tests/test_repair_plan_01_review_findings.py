"""OHB2-REPAIR-PLAN-01-REVIEW-FINDINGS — إصلاح نتائج المراجعة المستقلّة.

يغطّي FIX-R01 … FIX-R05 بلا تغيير المعمارية أو سياسة المرفقات المعتمدة (A0–A4):

- **FIX-R01 / Option A**: حصص D-12 (عدد/بايت) **معطّلة افتراضيًّا** (مفيش فرض) لحد موافقة
  المالك الصريحة؛ آلية الحصص محفوظة وقابلة للتفعيل صريحًا؛ سقف الملف الواحد (3 MiB) يفضل
  مفعّل؛ D-12 يفضل غير محسوم.
- **FIX-R02**: محاسبة الحصص على **الموارد الفعلية** (الملفات) مش الصفوف التاريخية ⇒ الرفض/
  الانتهاء/الكنس ما بيستهلكش سعة دائمة.
- **FIX-R04 (R-1/R-2)**: المسار البديل غير المحدود (`File.download_to_memory`) **مرفوض**
  صراحةً؛ المسارات المقبولة (بثّ HTTPX، قراءة ملف محلي مقيّدة) بحدّ فعلي. الاختبارات
  بتستخدم PTB 22.8 الحقيقي (أو بديل أمين ينادي `write()` **مرّة واحدة** بالرد الكامل).
- **FIX-R05**: جدول الحدود موثَّق (مفعّل/معطّل/بانتظار الموافقة).

**R-3 (بوابة معمارية):** نقطة الكنس عند الإدخال اتشالت (نقطة استدعاء غير معتمَدة في A4)؛
كنس الإقلاع (A4) محفوظ.
**R-4:** `AttachmentReaper` بيمنع البناء الغامض (بلا `store`/`db_path`) بدل جذر نسبي صامت.

معزولة (tmp_path + sqlite مؤقّت + سوكيت TCP حقيقي للبثّ)، بلا شبكة خارجية.
"""
from __future__ import annotations

import asyncio
import os
import pathlib
from datetime import datetime, timezone, timedelta

import httpx
import pytest

from bot import attachments as attachments_mod
from bot import handlers
from bot.attachments import (
    MAX_ATTACHMENT_BYTES,
    AttachmentReaper,
    AttachmentService,
    AttachmentTooLargeError,
    StageStatus,
    StagingError,
    StagingStore,
    staging_total_bytes,
)
from bot.config import Config
from bot.db import (
    ATTACHMENT_ITEM_STORED,
    Database,
)
from bot.files import IdentityCache

from tests._real_http import RealHTTPServer, http_response
from tests.test_repair_plan_01_resource_staging import (
    CID,
    OWNER_ID,
    FakeClient,
    _FakeBot,
    _FakeCtx,
    _run,
    _tg_file,
    add_batch,
    make_store,
)

T0_DT = datetime(2026, 11, 11, tzinfo=timezone.utc)


# ------------------------------------------------------------------ مساعدات
def _service(db, store):
    client = FakeClient()
    return AttachmentService(db, store, client, IdentityCache(client))


async def _accept(service, name, payload=b"x", *, now=T0_DT, update_id=None):
    async def factory():
        return iter([payload])

    return await service.accept(
        telegram_id=OWNER_ID, conversation_id=CID, display_name=name,
        declared_size=None, update_id=update_id, now=now, chunks_factory=factory,
    )


def _batch_id(db):
    return db._conn.execute("SELECT batch_id FROM attachment_batches").fetchone()["batch_id"]


# ============================================================================
# 1) FIX-R01 — سياسة الحصص (Option A)
# ============================================================================
def test_default_config_does_not_enforce_item_count(tmp_path):
    """الافتراضي: مفيش سقف عدد ⇒ 25 ملف كلهم يتخزّنوا (بلا `REJECTED_QUOTA`)."""
    db, store = make_store(tmp_path)
    add_batch(db)
    svc = _service(db, store)

    async def run():
        for i in range(25):
            r = await _accept(svc, f"f{i}.txt", b"x")
            assert r.stage is not StageStatus.REJECTED_QUOTA

    _run(run())
    items = db.list_attachment_items("b1")
    assert len(items) == 25
    assert all(it.status == ATTACHMENT_ITEM_STORED for it in items)
    assert len(list(store.root.iterdir())) == 25


def test_default_config_does_not_enforce_global_bytes(tmp_path):
    """الافتراضي: مفيش سقف بايت كلي ⇒ ملفات كتير تتخزّن بلا رفض حصّة."""
    db, store = make_store(tmp_path)
    add_batch(db)
    svc = _service(db, store)
    payload = b"z" * 200_000

    async def run():
        for i in range(6):
            r = await _accept(svc, f"g{i}.dat", payload)
            assert r.outcome.value == "stored"

    _run(run())
    assert staging_total_bytes(store.root) == 6 * len(payload)


def test_store_defaults_are_all_disabled(tmp_path):
    """`StagingStore` الافتراضي: كل حصص D-12 `None` و`quota_enabled` False."""
    db, store = make_store(tmp_path)
    assert store.max_items_per_batch is None
    assert store.max_total_bytes is None
    assert store.max_bytes_per_batch is None
    assert store.quota_enabled is False
    assert store.max_bytes == MAX_ATTACHMENT_BYTES  # سقف الملف مفعّل دائمًا


def test_per_file_3mib_limit_remains_enforced(tmp_path):
    """سقف الملف الواحد (3 MiB) يفضل مفعّلًا (مستقلّ عن حصص D-12)."""
    db, store = make_store(tmp_path)
    add_batch(db)
    svc = _service(db, store)

    async def run():
        over = await _accept(svc, "big.dat", b"x" * (MAX_ATTACHMENT_BYTES + 1))
        assert over.stage is StageStatus.REJECTED_SIZE
        exact = await _accept(svc, "exact.dat", b"x" * MAX_ATTACHMENT_BYTES)
        assert exact.stage is StageStatus.STORED

    _run(run())


def test_extension_and_magic_validation_remain_enforced(tmp_path):
    """فحص الامتداد والمحتوى (magic bytes) يفضل مفعّلًا."""
    db, store = make_store(tmp_path)
    add_batch(db)
    svc = _service(db, store)

    async def run():
        ext = await _accept(svc, "evil.sh", b"harmless")
        assert ext.stage is StageStatus.REJECTED_TYPE
        magic = await _accept(svc, "report.txt", b"\x7fELF\x02\x01\x01\x00rest")
        assert magic.stage is StageStatus.REJECTED_TYPE

    _run(run())


def test_ownership_checks_remain_enforced(tmp_path):
    """حراسة الملكية: دفعة مستخدم تاني ⇒ رفض مغلق (`REJECTED_BATCH`)."""
    db, store = make_store(tmp_path)
    add_batch(db, telegram_id=999999)
    res = store.store(telegram_id=OWNER_ID, batch_id="b1", item_id="i1",
                      display_name="a.txt", chunks=[b"x"])
    assert res.status is StageStatus.REJECTED_BATCH


def test_no_config_path_enables_unapproved_policy(tmp_path):
    """مفيش مفتاح config/env يُفعّل الحصص ضمنيًّا (المفتاح غير موجود في `Config`)."""
    fields = set(getattr(Config, "__dataclass_fields__", {}))
    assert not any("quota" in f or "max_items" in f or "max_total" in f for f in fields)
    # والافتراضي في المخزن معطّل حتى لو الإعداد الافتراضي بالكامل.
    cfg = Config(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({OWNER_ID}),
        owner_id=OWNER_ID,
        db_path=str(tmp_path / "t.sqlite3"),
    )
    db = Database(cfg.db_path)
    store = StagingStore(db, cfg.db_path)
    assert store.quota_enabled is False


def test_quota_mechanism_remains_testable_when_explicitly_enabled(tmp_path):
    """التفعيل الصريح (تمرير حدّ) يشغّل الآلية ⇒ الرفض يعمل (جاهزة للموافقة المستقبلية)."""
    db, store = make_store(tmp_path, max_items_per_batch=2)
    add_batch(db)
    svc = _service(db, store)

    async def run():
        assert (await _accept(svc, "a.txt", b"1")).stage is StageStatus.STORED
        assert (await _accept(svc, "b.txt", b"2")).stage is StageStatus.STORED
        third = await _accept(svc, "c.txt", b"3")
        assert third.stage is StageStatus.REJECTED_QUOTA

    _run(run())
    assert len(list(store.root.iterdir())) == 2


def test_d12_remains_unresolved_and_values_provisional():
    """D-12 يفضل غير محسوم في سجل القرارات، والقيم موسومة مؤقّتة في الكود."""
    register = pathlib.Path("docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md").read_text(
        encoding="utf-8"
    )
    idx = register.index("### D-12")
    section = register[idx : idx + 400]
    assert "غير محسوم" in section
    src = pathlib.Path(attachments_mod.__file__).read_text(encoding="utf-8")
    assert "مؤقّت" in src  # القيم موسومة مؤقّتة/PROVISIONAL


# ============================================================================
# 2) FIX-R02 — محاسبة العناصر (الموارد الفعلية vs السجل التاريخي)
# ============================================================================
def test_rejected_items_do_not_consume_count_quota(tmp_path):
    """رفضات الحجم ما بتستهلكش سقف العدد ⇒ الملف الصالح يتقبل بعدها."""
    db, store = make_store(tmp_path, max_items_per_batch=2, max_bytes=4)
    add_batch(db)
    svc = _service(db, store)

    async def run():
        for i in range(3):
            assert (await _accept(svc, f"big{i}.txt", b"1234567890")).stage is (
                StageStatus.REJECTED_SIZE
            )
        assert (await _accept(svc, "ok1.txt", b"aa")).stage is StageStatus.STORED
        assert (await _accept(svc, "ok2.txt", b"bb")).stage is StageStatus.STORED
        # دلوقتي 2 ملفات فعلية عند السقف ⇒ الرفض هنا صح.
        assert (await _accept(svc, "ok3.txt", b"cc")).stage is StageStatus.REJECTED_QUOTA

    _run(run())
    assert len(list(store.root.iterdir())) == 2


def test_failed_transfer_then_valid_item_accepted(tmp_path):
    """فشل نقل (مش حجم) ما بيستهلكش سعة ⇒ الملف الصالح التالي يتخزّن."""
    db, store = make_store(tmp_path, max_items_per_batch=1)
    add_batch(db)
    svc = _service(db, store)

    async def failing():
        raise StagingError("transport")

    async def run():
        with pytest.raises(StagingError):
            await svc.accept(
                telegram_id=OWNER_ID, conversation_id=CID, display_name="bad.txt",
                declared_size=None, update_id=None, now=T0_DT, chunks_factory=failing,
            )
        assert (await _accept(svc, "ok.txt", b"x")).stage is StageStatus.STORED

    _run(run())
    assert len(list(store.root.iterdir())) == 1


def test_reaped_item_releases_capacity(tmp_path):
    """عنصر `reaped` (بايتاته اتحذفت) ما بيحجبش السعة ⇒ عنصر جديد يتخزّن."""
    db, store = make_store(tmp_path, max_items_per_batch=1)
    add_batch(db)
    svc = _service(db, store)

    async def run():
        r1 = await _accept(svc, "a.txt", b"1")
        assert r1.stage is StageStatus.STORED
        assert (await _accept(svc, "b.txt", b"2")).stage is StageStatus.REJECTED_QUOTA

    _run(run())
    # كنس العنصر **المخزَّن** (DB-أولًا ثم حذف الملف) — نفس تسلسل A4.
    stored = [it for it in db.list_attachment_items("b1") if it.status == ATTACHMENT_ITEM_STORED]
    assert len(stored) == 1
    item = stored[0]
    assert db.mark_attachment_item_reaped(item.item_id) is True
    os.unlink(str(store.root / item.staging_token))

    async def run2():
        assert (await _accept(svc, "c.txt", b"3")).stage is StageStatus.STORED

    _run(run2())
    assert len(list(store.root.iterdir())) == 1


def test_stored_items_accounted_while_files_exist(tmp_path):
    """عنصر `stored` بيتحسب طول ما ملفه موجود؛ بحذف الملف تتحرّر السعة."""
    db, store = make_store(tmp_path, max_items_per_batch=2)
    add_batch(db)
    svc = _service(db, store)

    async def run():
        await _accept(svc, "a.txt", b"1")
        await _accept(svc, "b.txt", b"2")
        assert (await _accept(svc, "c.txt", b"3")).stage is StageStatus.REJECTED_QUOTA

    _run(run())
    stored = [it for it in db.list_attachment_items("b1") if it.status == ATTACHMENT_ITEM_STORED]
    os.unlink(str(store.root / stored[0].staging_token))  # ملف اتشال خارجيًّا

    async def run2():
        assert (await _accept(svc, "d.txt", b"4")).stage is StageStatus.STORED

    _run(run2())


def test_historical_rows_are_preserved(tmp_path):
    """الصفوف التاريخية (المرفوضة) بتفضل محفوظة — مفيش حذف لتمرير الحصّة."""
    db, store = make_store(tmp_path, max_items_per_batch=2)
    add_batch(db)
    svc = _service(db, store)

    async def run():
        for i in range(5):
            await _accept(svc, f"f{i}.txt", b"1")

    _run(run())
    assert db.count_attachment_items() == 5  # كل الصفوف محفوظة (2 stored + 3 pending مرفوضة)


def test_repeated_rejections_do_not_corrupt_accounting(tmp_path):
    """رفضات متكرّرة ما بتفسدش المحاسبة ⇒ العنصر الصالح اللاحق يتخزّن."""
    db, store = make_store(tmp_path, max_items_per_batch=1)
    add_batch(db)
    svc = _service(db, store)

    async def run():
        await _accept(svc, "ok.txt", b"1")  # يشغل السعة (ملف واحد)
        for i in range(10):
            assert (await _accept(svc, f"r{i}.txt", b"2")).stage is StageStatus.REJECTED_QUOTA

    _run(run())
    assert len(list(store.root.iterdir())) == 1
    assert db.count_attachment_items() == 11  # السجل التاريخي محفوظ بالكامل


def test_concurrent_admission_against_real_sqlite(tmp_path):
    """قبول متزامن (نفس اتصال SQLite الحقيقي) لا يتجاوز السقف الفعلي."""
    db, store = make_store(tmp_path, max_items_per_batch=3)
    add_batch(db)
    svc = _service(db, store)

    async def run():
        tasks = [_accept(svc, f"c{i}.txt", b"x") for i in range(12)]
        results = await asyncio.gather(*tasks)
        return results

    results = _run(run())
    stored = sum(1 for r in results if r.stage is StageStatus.STORED)
    rejected = sum(1 for r in results if r.stage is StageStatus.REJECTED_QUOTA)
    assert stored == 3
    assert rejected == 9
    assert len(list(store.root.iterdir())) == 3


# ============================================================================
# 3) R-3 — بوابة معمارية: نقطة الكنس عند الإدخال اتشالت (غير معتمَدة في A4)
# ============================================================================
def test_intake_does_not_invoke_cleanup():
    """R-3: الإدخال (`accept`) **ما بيناديش** أي كنس — نقطة استدعاء إضافية غير معتمَدة
    في A4 (المعتمَد: hook الإقلاع فقط). الكنس عند الإدخال اتشال بالكامل."""
    src = pathlib.Path(attachments_mod.__file__).read_text(encoding="utf-8")
    assert "opportunistic_cleanup" not in src
    assert not hasattr(StagingStore, "opportunistic_cleanup")
    # `accept` ما بيستدعيش أي كنس في مساره.
    idx = src.index("async def accept(")
    accept_body = src[idx : src.index("\nclass ", idx)]
    assert "sweep(" not in accept_body
    assert "AttachmentReaper" not in accept_body


def test_startup_reaper_still_cleans_expired(tmp_path):
    """كنس الإقلاع (A4) لسه شغّال (الوحيد المعتمَد)."""
    db, store = make_store(tmp_path)
    add_batch(db)
    svc = _service(db, store)

    async def run():
        await _accept(svc, "a.txt", b"1")

    _run(run())
    report = AttachmentReaper(db, tmp_path / "state.sqlite3").sweep(
        now=T0_DT + timedelta(minutes=20)
    )
    assert report.cleaned >= 1
    assert list(store.root.iterdir()) == []


def test_cleanup_adds_no_worker_or_scheduler():
    """الكنس (A4) متزامن ومربوط بالـ hook — مفيش عامل/مجدول/عملية جديدة."""
    src = pathlib.Path(attachments_mod.__file__).read_text(encoding="utf-8")
    assert "asyncio" not in src
    assert "create_task" not in src
    assert not hasattr(StagingStore, "start")
    assert not hasattr(StagingStore, "stop")
    assert not hasattr(AttachmentReaper, "start")
    assert not hasattr(AttachmentReaper, "stop")


# ============================================================================
# 3b) R-4 — بناء `AttachmentReaper` الآمن (جذر صريح)
# ============================================================================
def test_reaper_rejects_ambiguous_construction(tmp_path):
    """R-4: بناء بلا `store`/`db_path` ⇒ `StagingError` (مفيش جذر نسبي صامت)."""
    db, _store = make_store(tmp_path)
    with pytest.raises(StagingError):
        AttachmentReaper(db)


def test_reaper_accepts_explicit_db_path(tmp_path):
    """R-4: `db_path` صريح مسار مشروع (يُستخدم في hook الإقلاع)."""
    db, _store = make_store(tmp_path)
    r = AttachmentReaper(db, tmp_path / "state.sqlite3")
    assert r.root == _store.root


def test_reaper_accepts_existing_store(tmp_path):
    """R-4: تمرير `store` موجود يفضّل نفس الجذر (بلا اتصال قاعدة تاني)."""
    db, store = make_store(tmp_path)
    before = db._conn
    r = AttachmentReaper(db, store=store)
    assert r.root == store.root
    assert db._conn is before



# ============================================================================
# 4) FIX-R04 (R-1/R-2) — مسار بديل محدود فقط؛ اللامحدود مرفوض
# ============================================================================
class _FakeFallbackFile:
    """`File` مزيّف بلا URL/مسار (يستخدمه اختبار أن التطبيق **ما بيناديش**
    `download_to_memory`). يسجّل أي نداء فعلًا لـ `download_to_memory` عشان نثبت الرفض."""

    file_id = "f1"
    file_unique_id = "u1"
    file_size = None
    file_path = None

    def __init__(self) -> None:
        self.download_calls = 0

    async def download_to_memory(self, out, **kw):  # pragma: no cover — ممنوع يُنادى
        self.download_calls += 1
        raise AssertionError("ممنوع نداء download_to_memory (مسار غير محدود)")


class _FallbackBot:
    """بوت مزيّف: `get_file` يرجّع ملف بلا URL/مسار، و`request` بلا عميل httpx."""

    class _Request:
        _client = None

    def __init__(self, tg_file):
        self.request = _FallbackBot._Request()
        self._file = tg_file

    async def get_file(self, file_id=None, **kw):
        return self._file


def test_remote_fallback_rejected_without_invoking_unbounded_ptb(tmp_path):
    """R-1 (حاجب): URL بلا عميل بثّ ⇒ `StagingError` **قبل** أي نداء لـ
    `download_to_memory` (مفيش تبديل صامت لمسار غير محدود)."""
    f = _FakeFallbackFile()
    f.file_path = "https://api.telegram.org/file/botX/p"  # URL لكن البوت بلا عميل httpx
    bot = _FallbackBot(f)
    with pytest.raises(StagingError):
        _run(handlers._download_attachment_chunks(_FakeCtx(bot), "f1", 3 * 1024 * 1024))
    assert f.download_calls == 0  # المسار اللامحدود ما اتناداش خالص


def test_no_path_fallback_rejected_without_invoking_unbounded_ptb():
    """بلا URL وبلا ملف محلي ⇒ `StagingError` (مفيش مسار استلام محدود)."""
    f = _FakeFallbackFile()  # file_path=None
    bot = _FallbackBot(f)
    with pytest.raises(StagingError):
        _run(handlers._download_attachment_chunks(_FakeCtx(bot), "f1", 1000))
    assert f.download_calls == 0


def test_handlers_module_does_not_call_download_to_memory():
    """R-1: الوحدة ما بتناديش `download_to_memory` خالص (المسار اللامحدود اتشال)."""
    src = pathlib.Path(handlers.__file__).read_text(encoding="utf-8")
    assert "download_to_memory(" not in src  # مفيش نداء (الذكر في التوثيق بلا قوسين)
    assert "_CappedByteSink" not in src


def test_rejected_remote_fallback_yields_no_stored_state(tmp_path):
    """R-2.4: رفض المسار البديل (مفيش بثّ) ⇒ مفيش حالة `stored` (العنصر يفضل pending)."""
    db, store = make_store(tmp_path)
    add_batch(db)
    svc = _service(db, store)
    f = _FakeFallbackFile()
    f.file_path = "https://api.telegram.org/file/botX/p"
    ctx = _FakeCtx(_FallbackBot(f))

    async def factory():
        return await handlers._download_attachment_chunks(ctx, "f1", MAX_ATTACHMENT_BYTES)

    with pytest.raises(StagingError):
        _run(svc.accept(
            telegram_id=OWNER_ID, conversation_id=CID, display_name="x.dat",
            declared_size=None, update_id=None, now=T0_DT, chunks_factory=factory,
        ))
    items = db.list_attachment_items(_batch_id(db))
    assert len(items) == 1 and items[0].status != ATTACHMENT_ITEM_STORED
    # مفيش ملف staging جزئي (الجذر ممكن ميتعملش أصلًا).
    assert not store.root.exists() or list(store.root.iterdir()) == []


def test_real_ptb_download_to_memory_buffers_complete_body():
    """R-2.2: بديل أمين لـ PTB 22.8 — `download_to_memory` بينادي `write()` **مرّة واحدة**
    بالرد الكامل (يفشل لو التطبيق اعتمد على حوض متدفّق)."""
    from telegram import File

    body = b"x" * (1024 * 1024)

    class _Req:
        async def retrieve(self, url, **kw):
            return body

    class _Bot:
        request = _Req()

    f = File(file_id="f", file_unique_id="u", file_size=len(body),
             file_path="https://api.telegram.org/file/botX/p")
    f.set_bot(_Bot())

    class _Sink:
        def __init__(self):
            self.calls = 0
            self.total = 0

        def write(self, data):
            self.calls += 1
            self.total += len(data)
            return len(data)

    sink = _Sink()
    _run(f.download_to_memory(sink))
    assert sink.calls == 1  # PTB 22.8: نداء واحد بالرد الكامل (بلا بثّ)
    assert sink.total == len(body)


def test_primary_stream_exact_limit_and_one_over(tmp_path):
    """المسار الأساسي (بثّ HTTPX حقيقي): المطابق يمرّ، والزيادة تُرفض."""
    payload = b"p" * 4096
    srv = RealHTTPServer(lambda _r: http_response(200, body=payload))
    try:
        client = httpx.AsyncClient()
        bot = _FakeBot(client, _tg_file(f"{srv.url}/file"))
        ctx = _FakeCtx(bot)
        ok = _run(handlers._download_attachment_chunks(ctx, "f1", 4096))
        assert b"".join(ok) == payload
        with pytest.raises(AttachmentTooLargeError):
            _run(handlers._download_attachment_chunks(ctx, "f1", 4095))
        _run(client.aclose())
    finally:
        srv.shutdown()


def test_primary_stream_exact_3mib_and_one_over(tmp_path):
    """السقف الفعلي 3 MiB على المسار الأساسي: 3 MiB يمرّ، 3 MiB+1 يرفض."""
    payload = b"p" * MAX_ATTACHMENT_BYTES
    srv = RealHTTPServer(lambda _r: http_response(200, body=payload))
    try:
        client = httpx.AsyncClient()
        bot = _FakeBot(client, _tg_file(f"{srv.url}/file"))
        ctx = _FakeCtx(bot)
        ok = _run(handlers._download_attachment_chunks(ctx, "f1", MAX_ATTACHMENT_BYTES))
        assert sum(len(c) for c in ok) == MAX_ATTACHMENT_BYTES
        with pytest.raises(AttachmentTooLargeError):
            _run(handlers._download_attachment_chunks(ctx, "f1", MAX_ATTACHMENT_BYTES - 1))
        _run(client.aclose())
    finally:
        srv.shutdown()


def test_primary_stream_mid_transfer_failure_propagates():
    """فشل منتصف النقل في المسار الأساسي ⇒ `StagingError` (مش نجاح كاذب)."""
    srv = RealHTTPServer(lambda _r: http_response(
        200, headers={"Content-Length": "1000000"}, body=b"short"
    ))
    try:
        client = httpx.AsyncClient()
        bot = _FakeBot(client, _tg_file(f"{srv.url}/file"))
        ctx = _FakeCtx(bot)
        with pytest.raises(StagingError):
            _run(handlers._download_attachment_chunks(ctx, "f1", 2_000_000))
        _run(client.aclose())
    finally:
        srv.shutdown()


def test_primary_stream_cancellation_propagates(tmp_path):
    """إلغاء أثناء البثّ ⇒ `CancelledError` ينتشر (مايتحوّلش لنجاح/`StagingError`)."""
    srv = RealHTTPServer(lambda _r: http_response(200, body=b"z" * (256 * 1024)))
    try:
        client = httpx.AsyncClient()
        bot = _FakeBot(client, _tg_file(f"{srv.url}/file"))
        ctx = _FakeCtx(bot)

        async def main():
            task = asyncio.ensure_future(
                handlers._download_attachment_chunks(ctx, "f1", 10 * 1024 * 1024)
            )
            await asyncio.sleep(0)  # نبدأ التنفيذ
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        _run(main())
        _run(client.aclose())
    finally:
        srv.shutdown()


def test_primary_stream_local_file_success_and_missing(tmp_path):
    """مسار محلي: النجاح عبر القراءة المقيّدة، والملف المفقود ⇒ رفض مغلق."""
    local = tmp_path / "local.bin"
    local.write_bytes(b"abcdef")
    bot = _FakeBot(None, _tg_file(str(local)))
    ctx = _FakeCtx(bot)
    chunks = _run(handlers._download_attachment_chunks(ctx, "f1", 100))
    assert b"".join(chunks) == b"abcdef"
    with pytest.raises(AttachmentTooLargeError):
        _run(handlers._download_attachment_chunks(ctx, "f1", 3))

    missing = _FakeBot(None, _tg_file(str(tmp_path / "nope.bin")))
    with pytest.raises(StagingError):
        _run(handlers._download_attachment_chunks(_FakeCtx(missing), "f1", 100))


def test_local_read_oserror_rejected(tmp_path, monkeypatch):
    """خطأ قراءة محلي (OSError) ⇒ `StagingError` (مش فشل صامت)."""
    local = tmp_path / "local.bin"
    local.write_bytes(b"abcdef")

    def boom(*a, **k):
        raise OSError("read denied")

    monkeypatch.setattr(handlers, "open", boom, raising=False)
    bot = _FakeBot(None, _tg_file(str(local)))
    with pytest.raises(StagingError):
        _run(handlers._download_attachment_chunks(_FakeCtx(bot), "f1", 100))


def test_staging_write_failure_no_partial_file_no_stored(tmp_path, monkeypatch):
    """فشل كتابة الـ staging ⇒ `WRITE_FAILED`، بلا ملف جزئي وبلا `stored` (الصف يفضل
    `pending` حسب row-first، عشان كنس A4 يلاقيه)."""
    db, store = make_store(tmp_path)
    add_batch(db)

    def boom(*a, **k):
        raise OSError("write denied")

    monkeypatch.setattr(os, "fdopen", boom)
    res = store.store(telegram_id=OWNER_ID, batch_id="b1", item_id="i1",
                      display_name="a.txt", chunks=[b"data"])
    assert res.status is StageStatus.WRITE_FAILED
    assert list(store.root.iterdir()) == []  # مفيش ملف جزئي
    items = db.list_attachment_items("b1")
    assert len(items) == 1 and items[0].status != ATTACHMENT_ITEM_STORED  # يفضل pending



# ============================================================================
# 5) FIX-R05 — سقف بايتات الدفعة (تصميم مُهيّأ، معطّل افتراضيًّا)
# ============================================================================
def test_per_batch_byte_quota_disabled_by_default(tmp_path):
    """افتراضيًّا: سقف بايتات الدفعة معطّل ⇒ مفيش رفض حصّة."""
    db, store = make_store(tmp_path)
    assert store.max_bytes_per_batch is None
    add_batch(db)
    svc = _service(db, store)

    async def run():
        await _accept(svc, "a.dat", b"x" * 1000)
        await _accept(svc, "b.dat", b"y" * 1000)

    _run(run())
    assert len(list(store.root.iterdir())) == 2


def test_per_batch_byte_quota_enforced_when_explicitly_enabled(tmp_path):
    """عند التفعيل الصريح: تجاوز سقف بايتات الدفعة ⇒ `REJECTED_QUOTA`."""
    db, store = make_store(tmp_path, max_bytes_per_batch=1500, max_bytes=1000)
    add_batch(db)
    svc = _service(db, store)

    async def run():
        assert (await _accept(svc, "a.dat", b"x" * 1000)).stage is StageStatus.STORED
        second = await _accept(svc, "b.dat", b"y" * 1000)  # 1000+1000 > 1500
        assert second.stage is StageStatus.REJECTED_QUOTA

    _run(run())
    assert len(list(store.root.iterdir())) == 1


def test_documented_limits_table_exists():
    """جدول الحدود (FIX-R05) موجود في توثيق الوحدة ويوضّح المفعّل/المعطّل."""
    src = pathlib.Path(attachments_mod.__file__).read_text(encoding="utf-8")
    assert "جدول الحدود" in src
    assert "معطّل" in src and "مفعّل" in src
