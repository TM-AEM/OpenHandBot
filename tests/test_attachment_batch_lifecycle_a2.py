"""OHB2-P0-A2 — دورة حياة الدفعة: هوية + ملكية + مهلة 15 دقيقة (محلي فقط).

يغطّي المتطلبات الدقيقة لـ R4 Stage A2:
- أول ملف يثبّت `T0` (مرة واحدة)؛ الملفات التانية بتضيف بلا تمديد للمهلة.
- المهلة = `T0 + 15 دقيقة` بالظبط؛ دفعة منتهية ⇒ الملف **يرفض الانضمام** ويبدأ دفعة جديدة.
- تفويض ملكية المحادثة + شاهد الحذف **قبل** أي قبول دائم (فشل مغلق).
- عزل الملكية (معرّف الدفعة لوحده مش تفويض).
- تطبيع الحجم المُعلَن (A1-REV-F4) + سقف A1 المُتدفّق.
- النتيجة الدائمة `durable_intent_recorded` ذرّيًّا مع القبول (row-first).

الساعات **محقونة** (بنمرّر `now` صريح للخدمة) ⇒ مفيش sleeps ومفيش اختبارات زمنية هشّة.
مفيش شبكة ومفيش حالة إنتاج: قاعدة مؤقتة + مجلد مؤقت + عميل مزيّف.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone

import pytest
from telegram import Chat, Document, Message, PhotoSize, Update, User

import bot.handlers as h_mod
from bot import app as app_mod
from bot import outbox
from bot.attachments import (
    AcceptOutcome,
    AttachmentService,
    BatchDecision,
    StagingStore,
    batch_deadline,
    batch_is_expired,
    classify_incoming_file,
    normalize_declared_size,
    sanitize_display_name,
)
from bot.config import Config
from bot.db import (
    ATTACHMENT_BATCH_EXPIRED,
    ATTACHMENT_BATCH_PENDING,
    ATTACHMENT_BATCH_TTL,
    ATTACHMENT_ITEM_STORED,
    Database,
)
from bot.files import IdentityCache

OWNER_ID = 1
OWNER_UUID = "11111111-2222-3333-4444-555555555555"
OTHER_UUID = "99999999-8888-7777-6666-555555555555"
CHAT_ID = 99
CID = "11111111222233334444555566667777"   # معرّف محادثة صالح (32 محرفًا)


# ------------------------------------------------------------------ عميل مزيّف
class FakeClient:
    """عميل OpenHands مزيّف: هوية مالك + محادثات مملوكة. مفيش شبكة."""

    def __init__(self, *, owner=OWNER_UUID, conversations=None, deleted_check=None):
        self.owner = owner
        self.conversations = conversations if conversations is not None else {}
        self.calls: list[tuple] = []
        self._deleted_check = deleted_check

    async def get_current_user(self):
        self.calls.append(("get_current_user",))
        return {"id": self.owner}

    async def get_conversations(self, ids):
        self.calls.append(("get_conversations", tuple(ids)))
        return [self.conversations[i] for i in ids if i in self.conversations]


def _conv(cid=CID, *, created_by=OWNER_UUID):
    return {"id": cid, "created_by_user_id": created_by, "title": "A"}


def make_db(tmp_path) -> Database:
    return Database(str(tmp_path / "t.sqlite3"))


def make_service(tmp_path, *, client=None, db=None, max_bytes=None):
    db = db if db is not None else make_db(tmp_path)
    store = (
        StagingStore(db, str(tmp_path / "t.sqlite3"), max_bytes=max_bytes)
        if max_bytes is not None
        else StagingStore(db, str(tmp_path / "t.sqlite3"))
    )
    client = client if client is not None else FakeClient(conversations={CID: _conv()})
    service = AttachmentService(
        db, store, client, IdentityCache(client), max_bytes=max_bytes
    )
    return db, store, client, service


T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


async def accept(service, *, now=T0, cid=CID, name="a.txt", size=None, chunks=(b"data",),
                 telegram_id=OWNER_ID, update_id=None):
    async def factory():
        return iter(chunks)

    return await service.accept(
        telegram_id=telegram_id,
        conversation_id=cid,
        display_name=name,
        declared_size=size,
        update_id=update_id,
        now=now,
        chunks_factory=factory,
    )


def tombstone(db, cid):
    db._conn.execute(
        "INSERT OR IGNORE INTO deleted_conversations(conversation_id, deleted_at) VALUES(?, ?)",
        (cid, outbox.now_iso()),
    )
    db._conn.commit()


# ================================================================ 1) أول ملف / T0
def test_first_file_creates_batch_and_sets_t0(tmp_path):
    db, store, client, service = make_service(tmp_path)
    res = asyncio.run(accept(service, now=T0))
    assert res.outcome is AcceptOutcome.STORED
    batches = db._conn.execute("SELECT * FROM attachment_batches").fetchall()
    assert len(batches) == 1
    assert batches[0]["t0"] == T0.isoformat()
    assert batches[0]["status"] == ATTACHMENT_BATCH_PENDING
    assert batches[0]["conversation_id"] == CID
    assert batches[0]["telegram_id"] == OWNER_ID


def test_first_file_row_first_and_stored(tmp_path):
    db, store, client, service = make_service(tmp_path)
    res = asyncio.run(accept(service, now=T0, chunks=(b"hello",)))
    items = db.list_attachment_items(res.batch_id)
    assert len(items) == 1
    assert items[0].status == ATTACHMENT_ITEM_STORED
    assert items[0].size_bytes == 5
    # ملف staging موجود فعلاً باسم مُعتِم.
    staged = list(store.ensure_root().iterdir())
    assert len(staged) == 1


def test_stored_item_references_its_staging_file(tmp_path):
    # F-1: الصف الدائم لازم يشير لتوكن ملفه (A4 يقدر يكنس البايتات).
    db, store, client, service = make_service(tmp_path)
    res = asyncio.run(accept(service, now=T0, chunks=(b"hello",)))
    item = db.get_attachment_item(res.item_id)
    assert item.staging_token  # توكن غير فاضي (مش None)
    staged = {p.name for p in store.ensure_root().iterdir()}
    assert item.staging_token in staged  # الصف يشير لملف موجود بالفعل


def test_display_name_is_sanitized_before_persisting(tmp_path):
    # F-2: اسم العرض يُخزَّن آمنًا (بلا مسار/محارف تحكّم، ومقصوص الطول) — بيانات وصفية فقط.
    db, store, client, service = make_service(tmp_path)
    hostile = "../../etc/passwd\x07" + "A" * 5000
    res = asyncio.run(accept(service, now=T0, name=hostile, chunks=(b"x",)))
    stored = db.get_attachment_item(res.item_id).display_name
    assert stored == sanitize_display_name(hostile)
    assert stored is not None and "/" not in stored and "\\" not in stored
    assert "\x07" not in stored and len(stored) <= 200


def test_appended_item_also_references_its_staging_file(tmp_path):
    # F-1 (مسار APPEND): كل عنصر مضموم لازم يشير لملفه الخاص (توكنات مستقلة).
    db, store, client, service = make_service(tmp_path)
    first = asyncio.run(accept(service, now=T0, name="a.txt", chunks=(b"aaa",)))
    second = asyncio.run(accept(service, now=T0 + timedelta(minutes=1), name="b.txt", chunks=(b"bb",)))
    tokens = [db.get_attachment_item(i.item_id).staging_token for i in (first, second)]
    assert all(tokens) and tokens[0] != tokens[1]
    staged = {p.name for p in store.ensure_root().iterdir()}
    assert set(tokens) <= staged


def test_batch_id_and_item_id_are_opaque(tmp_path):
    db, store, client, service = make_service(tmp_path)
    res = asyncio.run(accept(service, now=T0, name="secret-report.txt"))
    assert res.batch_id and "secret" not in res.batch_id
    assert res.item_id and "secret" not in res.item_id
    assert res.batch_id != res.item_id


# ============================================================ 2) الإضافة بلا تمديد
def test_second_file_appends_and_does_not_change_t0(tmp_path):
    db, store, client, service = make_service(tmp_path)
    first = asyncio.run(accept(service, now=T0, name="a.txt"))
    second = asyncio.run(accept(service, now=T0 + timedelta(minutes=5), name="b.txt"))
    assert first.batch_id == second.batch_id  # نفس الدفعة
    batch = db.get_attachment_batch(first.batch_id)
    assert batch.t0 == T0.isoformat()  # T0 ما اتغيّرش
    assert len(db.list_attachment_items(first.batch_id)) == 2


def test_append_does_not_extend_deadline(tmp_path):
    db, store, client, service = make_service(tmp_path)
    first = asyncio.run(accept(service, now=T0))
    deadline_before = batch_deadline(db.get_attachment_batch(first.batch_id).t0)
    asyncio.run(accept(service, now=T0 + timedelta(minutes=14), name="b.txt"))
    deadline_after = batch_deadline(db.get_attachment_batch(first.batch_id).t0)
    assert deadline_before == deadline_after == T0 + timedelta(minutes=15)


def test_batch_stays_pending_after_append(tmp_path):
    db, store, client, service = make_service(tmp_path)
    first = asyncio.run(accept(service, now=T0))
    asyncio.run(accept(service, now=T0 + timedelta(minutes=1), name="b.txt"))
    assert db.get_attachment_batch(first.batch_id).status == ATTACHMENT_BATCH_PENDING


# ================================================================= 3) المهلة
def test_deadline_is_exactly_15_minutes(tmp_path):
    assert ATTACHMENT_BATCH_TTL == timedelta(minutes=15)
    assert batch_deadline(T0.isoformat()) == T0 + timedelta(minutes=15)


def test_batch_is_expired_boundaries(tmp_path):
    t0 = T0.isoformat()
    assert batch_is_expired(t0, T0 + timedelta(minutes=15)) is False  # على الحد بالظبط
    assert batch_is_expired(t0, T0 + timedelta(minutes=15, microseconds=1)) is True
    assert batch_is_expired("not-a-timestamp", T0) is True  # fail closed


def test_append_just_before_expiry_ok(tmp_path):
    db, store, client, service = make_service(tmp_path)
    first = asyncio.run(accept(service, now=T0))
    res = asyncio.run(
        accept(service, now=T0 + timedelta(minutes=14, seconds=59), name="b.txt")
    )
    assert res.batch_id == first.batch_id
    assert res.outcome is AcceptOutcome.STORED


def test_append_after_expiry_starts_new_batch(tmp_path):
    db, store, client, service = make_service(tmp_path)
    first = asyncio.run(accept(service, now=T0))
    res = asyncio.run(accept(service, now=T0 + timedelta(minutes=16), name="b.txt"))
    # ملف جديد ⇒ دفعة جديدة (R4: المنتهية ترفض الملف ⇒ دفعة جديدة)، بلا انضمام.
    assert res.batch_id != first.batch_id
    assert res.outcome is AcceptOutcome.STORED
    assert len(db.list_attachment_items(first.batch_id)) == 1  # القديمة ما اتضمّتش
    assert db.get_attachment_batch(first.batch_id).status == ATTACHMENT_BATCH_EXPIRED


def test_expired_batch_cannot_be_revived(tmp_path):
    db, store, client, service = make_service(tmp_path)
    first = asyncio.run(accept(service, now=T0))
    asyncio.run(accept(service, now=T0 + timedelta(minutes=20), name="b.txt"))
    # محاولة إضافية بعيدة: القديمة تفضل expired، والعنصر الأصلي ما اتغيّرش.
    asyncio.run(accept(service, now=T0 + timedelta(minutes=40), name="c.txt"))
    old = db.get_attachment_batch(first.batch_id)
    assert old.status == ATTACHMENT_BATCH_EXPIRED
    assert old.t0 == T0.isoformat()  # T0 ثابت
    assert len(db.list_attachment_items(first.batch_id)) == 1


# ============================================ 4) التفويض/العزل/الشاهد (fail closed)
def test_cross_user_does_not_append_to_other_user_batch(tmp_path):
    db, store, client, service = make_service(tmp_path)
    asyncio.run(accept(service, now=T0, telegram_id=OWNER_ID))
    # مستخدم تاني: مايشوفش دفعة الأول ⇒ دفعة جديدة مستقلة.
    res2 = asyncio.run(accept(service, now=T0 + timedelta(minutes=1), telegram_id=222))
    assert res2.outcome is AcceptOutcome.STORED
    batches = db._conn.execute(
        "SELECT telegram_id, COUNT(*) c FROM attachment_batches GROUP BY telegram_id"
    ).fetchall()
    assert {r["telegram_id"]: r["c"] for r in batches} == {OWNER_ID: 1, 222: 1}


def test_unknown_conversation_rejected(tmp_path):
    db, store, client, service = make_service(
        tmp_path, client=FakeClient(conversations={})  # مفيش محادثات
    )
    res = asyncio.run(accept(service, now=T0))
    assert res.outcome is AcceptOutcome.AUTH_FAILED
    assert db._conn.execute("SELECT COUNT(*) c FROM attachment_batches").fetchone()["c"] == 0


def test_syntactically_valid_but_unauthorized_conversation_rejected(tmp_path):
    # معرّف صالح نحويًّا لكن مملوك لهوية تانية ⇒ UNAUTHORIZED (fail closed).
    client = FakeClient(conversations={CID: _conv(created_by=OTHER_UUID)})
    db, store, client, service = make_service(tmp_path, client=client)
    res = asyncio.run(accept(service, now=T0))
    assert res.outcome is AcceptOutcome.AUTH_FAILED
    assert db._conn.execute("SELECT COUNT(*) c FROM attachment_batches").fetchone()["c"] == 0


def test_tombstoned_conversation_rejected(tmp_path):
    db, store, client, service = make_service(tmp_path)
    tombstone(db, CID)
    res = asyncio.run(accept(service, now=T0))
    assert res.outcome is AcceptOutcome.AUTH_FAILED
    assert db._conn.execute("SELECT COUNT(*) c FROM attachment_batches").fetchone()["c"] == 0
    # ومفيش نداء بعيد للمحادثة المتشاهدة (الفشل قبل أي جلب).
    assert ("get_conversations", (CID,)) not in client.calls


def test_authz_db_error_fails_closed(tmp_path):
    db, store, client, service = make_service(tmp_path)

    def boom(_cid):
        raise RuntimeError("db down")

    db.is_deleted = boom  # فشل قراءة الشاهد ⇒ fail closed (DELETED، مفيش جلب)
    res = asyncio.run(accept(service, now=T0))
    assert res.outcome is AcceptOutcome.AUTH_FAILED
    assert db._conn.execute("SELECT COUNT(*) c FROM attachment_batches").fetchone()["c"] == 0


def test_no_silent_conversation_substitution(tmp_path):
    # الدفعة مربوطة بمحادثة واحدة؛ ملف في محادثة تانية بيعمل دفعة مستقلة (مفيش تبديل صامت).
    cid2 = "aaaaaaaabbbbbbbbccccccccdddddddd"
    client = FakeClient(conversations={CID: _conv(), cid2: _conv(cid2)})
    db, store, client, service = make_service(tmp_path, client=client)
    first = asyncio.run(accept(service, now=T0, cid=CID))
    other = asyncio.run(accept(service, now=T0 + timedelta(minutes=1), cid=cid2))
    assert other.batch_id != first.batch_id
    assert db.get_attachment_batch(first.batch_id).conversation_id == CID
    assert db.get_attachment_batch(other.batch_id).conversation_id == cid2


# ==================================================== 5) المدخلات + التكامل مع A1
def test_normalize_declared_size_unit():
    assert normalize_declared_size(None) is None
    assert normalize_declared_size(0) == 0
    assert normalize_declared_size(10) == 10
    assert normalize_declared_size(-5) is None
    assert normalize_declared_size(True) is None
    with pytest.raises(ValueError):
        normalize_declared_size("10")
    with pytest.raises(ValueError):
        normalize_declared_size(3.5)


def test_invalid_declared_size_type_rejected(tmp_path):
    db, store, client, service = make_service(tmp_path)
    res = asyncio.run(accept(service, now=T0, size="not-a-number"))
    assert res.outcome is AcceptOutcome.REJECTED
    assert db._conn.execute("SELECT COUNT(*) c FROM attachment_batches").fetchone()["c"] == 0


def test_negative_declared_size_is_ignored_and_actual_governs(tmp_path):
    db, store, client, service = make_service(tmp_path)
    res = asyncio.run(accept(service, now=T0, size=-1, chunks=(b"ok",)))
    assert res.outcome is AcceptOutcome.STORED  # الحجم الفعلي صغير
    assert db.list_attachment_items(res.batch_id)[0].size_bytes == 2


def test_oversize_declared_size_rejected_before_any_row(tmp_path):
    db, store, client, service = make_service(tmp_path)
    res = asyncio.run(accept(service, now=T0, size=10 * 1024 * 1024))
    assert res.outcome is AcceptOutcome.REJECTED
    assert db._conn.execute("SELECT COUNT(*) c FROM attachment_batches").fetchone()["c"] == 0


def test_streamed_size_limit_enforced(tmp_path):
    db, store, client, service = make_service(tmp_path, max_bytes=10)
    res = asyncio.run(accept(service, now=T0, size=None, chunks=(b"x" * 50,)))
    # اتقبل (نية دائمة) بس التخزين فشل ⇒ العنصر pending (مش stored ⇒ مش قابل للإرسال).
    assert res.outcome is AcceptOutcome.ACCEPTED
    item = db.get_attachment_item(res.item_id)
    assert item.status == ATTACHMENT_BATCH_PENDING
    assert list(store.ensure_root().iterdir()) == []  # مفيش بقايا جزئية


def test_failed_storage_leaves_no_stored_item(tmp_path):
    db, store, client, service = make_service(tmp_path, max_bytes=4)
    res = asyncio.run(accept(service, now=T0, chunks=(b"12345",)))
    items = db.list_attachment_items(res.batch_id)
    assert all(i.status != ATTACHMENT_ITEM_STORED for i in items)


def test_partial_write_failure_keeps_item_pending(tmp_path):
    db, store, client, service = make_service(tmp_path)

    def gen():
        yield b"partial"
        raise OSError("connection reset")

    async def factory():
        return gen()

    res = asyncio.run(
        service.accept(
            telegram_id=OWNER_ID, conversation_id=CID, display_name="a.txt",
            declared_size=None, update_id=None, now=T0, chunks_factory=factory,
        )
    )
    assert res.outcome is AcceptOutcome.ACCEPTED
    assert db.get_attachment_item(res.item_id).status == ATTACHMENT_BATCH_PENDING
    assert list(store.ensure_root().iterdir()) == []


def test_db_failure_on_accept_propagates(tmp_path):
    db, store, client, service = make_service(tmp_path)

    def boom(*a, **k):
        raise RuntimeError("db down")

    db.accept_attachment_item_into_new_batch = boom
    with pytest.raises(RuntimeError):
        asyncio.run(accept(service, now=T0))
    # مفيش قبول دائم (مافيش صفوف).
    assert db._conn.execute("SELECT COUNT(*) c FROM attachment_batches").fetchone()["c"] == 0


def test_writer_exception_inside_transaction_is_not_a_duplicate(tmp_path):
    """M6: فشل **داخل معاملة الكاتب الحقيقية** (بعد إدراج صف العنصر) لازم ينتشر.

    الحقن جوه `_mark_processed_nocommit` (يُنادى بعد إدراج العنصر وقبل `commit`) ⇒ بنمارس
    المعاملة الحقيقية، مش غلاف مزيّف. لو الكاتب ابتلع الاستثناء وأرجع `None` (طفرة M6)،
    الخدمة هترجّع `DUPLICATE` بدل ما ترفع ⇒ `pytest.raises` يفشل. ولو اتشال الـ `rollback`
    (طفرة M9)، صف العنصر يفضل ⇒ تأكيدات «مفيش صفوف» تفشل.
    """
    db, store, client, service = make_service(tmp_path)
    original = db._mark_processed_nocommit

    def boom(update_id, now, outcome=None):
        raise RuntimeError("writer mark failed")

    db._mark_processed_nocommit = boom
    with pytest.raises(RuntimeError, match="writer mark failed"):
        asyncio.run(accept(service, now=T0, update_id=7201))

    # (2) مش متحوّل لـ None/DUPLICATE/ACCEPTED: الاستثناء الأصلي انتشر فوق.
    # (3) مفيش علامة تكرار كاذبة ولا أي نتيجة مؤهّلة للإقرار.
    assert db.update_outcome(7201) is None
    assert db.update_is_processed(7201) is False
    assert db.is_update_acknowledgment_eligible(7201) is False
    # (4) مفيش صف عنصر/دفعة جزئي (rollback كامل).
    assert db._conn.execute("SELECT COUNT(*) c FROM attachment_items").fetchone()["c"] == 0
    assert db._conn.execute("SELECT COUNT(*) c FROM attachment_batches").fetchone()["c"] == 0
    assert db._conn.execute("SELECT COUNT(*) c FROM processed_updates").fetchone()["c"] == 0

    # (5) القاعدة صالحة: إعادة المحاولة بنفس `update_id` تنجح (عقد الديدَب: مفيش تسجيل ⇒ تنفيذ).
    db._mark_processed_nocommit = original
    retry = asyncio.run(accept(service, now=T0, update_id=7201))
    assert retry.outcome is AcceptOutcome.STORED
    assert db.update_outcome(7201) == "durable_intent_recorded"
    assert db._conn.execute("SELECT COUNT(*) c FROM attachment_batches").fetchone()["c"] == 1


def test_writer_rollback_leaves_no_partial_state_on_append(tmp_path):
    """M9: فشل بعد إدراج عنصر في دفعة قائمة ⇒ `rollback` كامل (مفيش عنصر/علامة جزئية).

    الحقن بيكتب العلامة (`_mark_processed_nocommit`) **ثم** يرفع، فبيحدث تعديل دلالي واحد
    على الأقل قبل الفشل. لو اتشال الـ `rollback` (طفرة M9)، العنصر المُلحَق والعلامة يفضلوا
    ⇒ تأكيدات «مفيش عنصر ثاني / مفيش علامة» تفشل. ولو الكاتب ابتلع الاستثناء (طفرة M6)،
    الخدمة ترجّع `DUPLICATE` بدل ما ترفع ⇒ `pytest.raises` يفشل.
    """
    db, store, client, service = make_service(tmp_path)
    first = asyncio.run(accept(service, now=T0, update_id=7301))
    assert first.outcome is AcceptOutcome.STORED
    assert len(db.list_attachment_items(first.batch_id)) == 1

    original = db._mark_processed_nocommit

    def boom(update_id, now, outcome=None):
        original(update_id, now, outcome)  # تعديل دلالي حقيقي قبل الفشل
        raise RuntimeError("writer mark failed after write")

    db._mark_processed_nocommit = boom
    with pytest.raises(RuntimeError, match="writer mark failed after write"):
        asyncio.run(accept(service, now=T0, update_id=7302))  # APPEND على الدفعة القائمة

    # (2) الـ APPEND اتراجع: العنصر الثاني مش موجود، والدفعة الأصلية سليمة.
    assert len(db.list_attachment_items(first.batch_id)) == 1
    # (3) مفيش علامة تكرار كاذبة ولا نتيجة للتحديث الفاشل.
    assert db.update_outcome(7302) is None
    assert db.update_is_processed(7302) is False
    assert db.is_update_acknowledgment_eligible(7302) is False
    assert db.update_outcome(7301) == "durable_intent_recorded"  # الأصلية ما اتلمستش
    # (5) القاعدة صالحة: إعادة المحاولة بنفس `update_id` تضيف عنصرًا واحدًا بس.
    db._mark_processed_nocommit = original
    retry = asyncio.run(accept(service, now=T0, update_id=7302))
    assert retry.outcome is AcceptOutcome.STORED
    assert len(db.list_attachment_items(first.batch_id)) == 2


def test_rejected_extension_before_any_write(tmp_path):
    db, store, client, service = make_service(tmp_path)
    res = asyncio.run(accept(service, now=T0, name="evil.exe"))
    assert res.outcome is AcceptOutcome.REJECTED
    assert db._conn.execute("SELECT COUNT(*) c FROM attachment_batches").fetchone()["c"] == 0


# ============================================================ 6) النتيجة الدائمة/التكرار
def test_accept_writes_durable_intent_outcome(tmp_path):
    db, store, client, service = make_service(tmp_path)
    asyncio.run(accept(service, now=T0, update_id=500))
    assert db.update_outcome(500) == "durable_intent_recorded"
    assert db.is_update_acknowledgment_eligible(500) is True


def test_duplicate_update_does_not_create_second_item(tmp_path):
    db, store, client, service = make_service(tmp_path)
    first = asyncio.run(accept(service, now=T0, update_id=501))
    second = asyncio.run(accept(service, now=T0 + timedelta(minutes=1), name="b.txt", update_id=501))
    # نفس الـ update_id ⇒ ما بيتكرّرش عنصر تاني (at-most-once، بلا ادّعاء exactly-once).
    assert len(db.list_attachment_items(first.batch_id)) == 1
    assert db.update_outcome(501) == "duplicate_completed"
    # F-4: مفيش قبول جديد ولا معرّف عنصر مُفبرَك — نتيجة صريحة `duplicate` بلا item_id.
    assert second.outcome is AcceptOutcome.DUPLICATE
    assert second.item_id is None
    assert second.batch_id is None


def test_duplicate_result_has_no_fabricated_item_id(tmp_path):
    # F-4: كل معرّف عنصر مُرجَع من قبول ناجح لازم يطابق صفًا حقيقيًا في القاعدة.
    db, store, client, service = make_service(tmp_path)
    first = asyncio.run(accept(service, now=T0, update_id=511))
    assert first.item_id is not None and db.get_attachment_item(first.item_id) is not None
    dup = asyncio.run(accept(service, now=T0, name="dup.txt", update_id=511))
    assert dup.outcome is AcceptOutcome.DUPLICATE
    assert dup.item_id is None  # مش مُفبرَك ولا مُعاد استخدام معرّف عنصر تاني
    assert len(db.list_attachment_items(first.batch_id)) == 1


def test_duplicate_result_matches_regardless_of_batch_decision(tmp_path):
    # F-4: التكرار يرجّع DUPLICATE قبل أي كتابة عنصر، حتى لو الدفعة السابقة انتهت وقتها
    # (الدفعة المنتهية تُوسَم `expired` في خطوة منفصلة، لكن **مايتعملش** عنصر/دفعة جديدة).
    db, store, client, service = make_service(tmp_path)
    first = asyncio.run(accept(service, now=T0, update_id=521))
    dup = asyncio.run(accept(service, now=T0 + timedelta(minutes=16), name="late.txt", update_id=521))
    assert dup.outcome is AcceptOutcome.DUPLICATE
    assert dup.item_id is None
    assert len(db.list_attachment_items(first.batch_id)) == 1  # مفيش عنصر جديد
    assert db.get_attachment_batch(first.batch_id).t0 == T0.isoformat()  # T0 ما اتمدّدش


def test_duplicate_does_not_download_or_stage(tmp_path):
    # F-4: مسار التكرار يرجّع قبل أي تنزيل/كتابة بايتات (مفيش ملفات staging جديدة).
    db, store, client, service = make_service(tmp_path)
    asyncio.run(accept(service, now=T0, update_id=531, chunks=(b"first",)))
    staged_before = {p.name for p in store.ensure_root().iterdir()}
    called = {"n": 0}

    async def factory():
        called["n"] += 1
        return iter([b"dup"])

    dup = asyncio.run(
        service.accept(
            telegram_id=OWNER_ID, conversation_id=CID, display_name="dup.txt",
            declared_size=None, update_id=531, now=T0, chunks_factory=factory,
        )
    )
    assert dup.outcome is AcceptOutcome.DUPLICATE
    assert called["n"] == 0  # ما اتنزّلش أي بايت
    assert {p.name for p in store.ensure_root().iterdir()} == staged_before


def test_repeated_duplicate_does_not_extend_t0(tmp_path):
    db, store, client, service = make_service(tmp_path)
    first = asyncio.run(accept(service, now=T0, update_id=502))
    for _ in range(3):
        asyncio.run(accept(service, now=T0 + timedelta(minutes=3), name="b.txt", update_id=502))
    assert db.get_attachment_batch(first.batch_id).t0 == T0.isoformat()


def test_classify_incoming_file_decisions(tmp_path):
    db, store, client, service = make_service(tmp_path)
    assert classify_incoming_file(
        db, telegram_id=OWNER_ID, conversation_id=CID, now=T0
    ).decision is BatchDecision.NEW
    asyncio.run(accept(service, now=T0))
    assert classify_incoming_file(
        db, telegram_id=OWNER_ID, conversation_id=CID, now=T0 + timedelta(minutes=1)
    ).decision is BatchDecision.APPEND
    assert classify_incoming_file(
        db, telegram_id=OWNER_ID, conversation_id=CID, now=T0 + timedelta(minutes=20)
    ).decision is BatchDecision.EXPIRED


# ============================================== 7) تكامل الـ handler الحقيقي (app)
class FakeTgFile:
    def __init__(self, data: bytes):
        self._data = data

    async def download_to_memory(self, buf, **kw):
        buf.write(self._data)


class Harness:
    def __init__(self, tmp_path, *, file_bytes=b"hello", conversations=None) -> None:
        self.file_bytes = file_bytes
        self.app = app_mod.build_application(make_config(tmp_path))
        self.app._initialized = True  # نتخطّى initialize() (بيفتح جلسة شبكة حقيقية)
        self.app.bot_data["client"] = FakeClient(
            conversations=conversations if conversations is not None else {CID: _conv()}
        )
        self.replies: list[str] = []
        self.get_file_calls: list[str] = []

    @property
    def db(self) -> Database:
        return self.app.bot_data["db"]

    def _user(self, uid=OWNER_ID) -> User:
        return User(id=uid, first_name="o", is_bot=False)

    def document_update(self, update_id, *, name="report.pdf", size=None, uid=OWNER_ID) -> Update:
        chat = Chat(id=CHAT_ID, type="private")
        doc = Document(file_id="doc-1", file_unique_id="u1", file_name=name, file_size=size)
        msg = Message(message_id=5, date=None, chat=chat, from_user=self._user(uid), document=doc)
        msg.set_bot(self.app.bot)
        up = Update(update_id=update_id, message=msg)
        up.set_bot(self.app.bot)
        return up

    def photo_update(self, update_id) -> Update:
        chat = Chat(id=CHAT_ID, type="private")
        msg = Message(
            message_id=5, date=None, chat=chat, from_user=self._user(),
            photo=[PhotoSize(file_id="ph-1", file_unique_id="u2", width=10, height=10)],
        )
        msg.set_bot(self.app.bot)
        up = Update(update_id=update_id, message=msg)
        up.set_bot(self.app.bot)
        return up

    def process(self, update: Update) -> None:
        asyncio.run(self.app.process_update(update))

    def process_attachment_direct(self, update: Update) -> None:
        """يشغّل `handle_attachment` مباشرةً (يتخطّى حاجز group=-1).

        لمحاكاة **سباق التكرار**: إعادة تسليم توصل للـ handler قبل ما الحاجز يسجّل
        «معالَج». كده نتحقّق من سلوك مسار التكرار الحقيقي (F-4).
        """
        from types import SimpleNamespace

        ctx = SimpleNamespace()
        ctx.bot_data = self.app.bot_data
        ctx.bot = self.app.bot
        asyncio.run(h_mod.handle_attachment(update, ctx))


def make_config(tmp_path) -> Config:
    return Config(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({OWNER_ID}),
        owner_id=OWNER_ID,
        db_path=str(tmp_path / "t.sqlite3"),
    )


def _patch_telegram(monkeypatch, harness: Harness) -> None:
    async def _send_message(self, chat_id=None, text=None, **kw):
        harness.replies.append(text)
        return Message(message_id=1, date=None, chat=Chat(id=chat_id, type="private"))

    async def _get_file(self, file_id=None, **kw):
        harness.get_file_calls.append(file_id)
        return FakeTgFile(harness.file_bytes)

    async def _noop(self, *a, **k):
        return True

    monkeypatch.setattr("telegram.Bot.send_message", _send_message)
    monkeypatch.setattr("telegram.Bot.get_file", _get_file)
    monkeypatch.setattr("telegram.Bot.set_my_commands", _noop)
    monkeypatch.setattr("telegram.Bot.set_chat_menu_button", _noop)


def _harness(tmp_path, monkeypatch, **kw) -> Harness:
    harness = Harness(tmp_path, **kw)
    _patch_telegram(monkeypatch, harness)
    return harness


def test_handler_document_accepted_records_durable_intent(tmp_path, monkeypatch):
    harness = _harness(tmp_path, monkeypatch)
    harness.db.set_awaiting(OWNER_ID, CID, "route", title="A")
    harness.process(harness.document_update(900))
    assert harness.replies == [h_mod.ATTACHMENT_ACCEPTED_TEXT]
    batch = harness.db.get_attachment_batch(
        harness.db._conn.execute("SELECT batch_id FROM attachment_batches").fetchone()["batch_id"]
    )
    assert batch is not None and batch.conversation_id == CID
    assert harness.db.update_outcome(900) == "durable_intent_recorded"
    assert harness.db.is_update_acknowledgment_eligible(900) is True


def test_handler_document_without_route_rejected(tmp_path, monkeypatch):
    harness = _harness(tmp_path, monkeypatch)
    # مفيش توجيه ⇒ مفيش محادثة مختارة ⇒ رفض، ومفيش دفعة، ومفيش تنزيل.
    harness.process(harness.document_update(901))
    assert harness.replies and harness.replies[0] != h_mod.ATTACHMENT_ACCEPTED_TEXT
    assert harness.db._conn.execute("SELECT COUNT(*) c FROM attachment_batches").fetchone()["c"] == 0
    assert harness.get_file_calls == []
    assert harness.db.update_outcome(901) == "explicitly_ignored"


def test_handler_non_owner_document_ignored(tmp_path, monkeypatch):
    harness = _harness(tmp_path, monkeypatch)
    harness.db.set_awaiting(OWNER_ID, CID, "route", title="A")
    harness.process(harness.document_update(902, uid=999))
    assert harness.replies == []
    assert harness.db._conn.execute("SELECT COUNT(*) c FROM attachment_batches").fetchone()["c"] == 0


def test_handler_duplicate_document_single_batch(tmp_path, monkeypatch):
    harness = _harness(tmp_path, monkeypatch)
    harness.db.set_awaiting(OWNER_ID, CID, "route", title="A")
    harness.process(harness.document_update(903))
    harness.process(harness.document_update(903))  # نفس التحديث (إعادة تسليم)
    assert harness.db._conn.execute("SELECT COUNT(*) c FROM attachment_batches").fetchone()["c"] == 1
    batch_id = harness.db._conn.execute("SELECT batch_id FROM attachment_batches").fetchone()["batch_id"]
    assert len(harness.db.list_attachment_items(batch_id)) == 1


def test_handler_duplicate_race_replies_accepted_without_new_item(tmp_path, monkeypatch):
    # F-4: لو إعادة التسليم عدّت الحاجز ووصلت الـ handler (سباق)، لازم:
    #   - ما تنشئش عنصر/دفعة جديدة،
    #   - تردّ بنص القبول نفسه (بلا رد خطأ كاذب)،
    #   - تسيب النتيجة الدائمة `duplicate_completed` (ما تتكتبش فوقها durable_completed).
    harness = _harness(tmp_path, monkeypatch)
    harness.db.set_awaiting(OWNER_ID, CID, "route", title="A")
    first = harness.document_update(914)
    harness.process_attachment_direct(first)
    batch_id = harness.db._conn.execute("SELECT batch_id FROM attachment_batches").fetchone()["batch_id"]
    assert len(harness.db.list_attachment_items(batch_id)) == 1
    replies_before = list(harness.replies)

    dup = harness.document_update(914)  # نفس التحديث، بنفس الملف
    harness.process_attachment_direct(dup)

    assert harness.db._conn.execute("SELECT COUNT(*) c FROM attachment_batches").fetchone()["c"] == 1
    assert len(harness.db.list_attachment_items(batch_id)) == 1
    assert len(harness.replies) == len(replies_before) + 1
    assert harness.replies[-1] == replies_before[-1]  # نفس رد القبول (idempotent، مش خطأ)
    assert harness.db.update_outcome(914) == "duplicate_completed"


def test_handler_rejected_type_is_ignored(tmp_path, monkeypatch):
    harness = _harness(tmp_path, monkeypatch)
    harness.db.set_awaiting(OWNER_ID, CID, "route", title="A")
    harness.process(harness.document_update(904, name="evil.exe"))
    assert harness.replies == [h_mod.ATTACHMENT_UNSUPPORTED_TYPE_TEXT]
    assert harness.db._conn.execute("SELECT COUNT(*) c FROM attachment_batches").fetchone()["c"] == 0
    assert harness.db.update_outcome(904) == "explicitly_ignored"


def test_handler_photo_still_uses_legacy_rejection(tmp_path, monkeypatch):
    harness = _harness(tmp_path, monkeypatch)
    harness.db.set_awaiting(OWNER_ID, CID, "route", title="A")
    harness.process(harness.photo_update(905))
    assert harness.replies == [h_mod.UNSUPPORTED_ATTACHMENT_TEXT]
    assert harness.db._conn.execute("SELECT COUNT(*) c FROM attachment_batches").fetchone()["c"] == 0


def test_handler_reply_failure_is_recorded(tmp_path, monkeypatch):
    harness = _harness(tmp_path, monkeypatch)
    harness.db.set_awaiting(OWNER_ID, CID, "route", title="A")

    async def _boom(self, chat_id=None, text=None, **kw):
        raise RuntimeError("telegram down")

    monkeypatch.setattr("telegram.Bot.send_message", _boom)
    harness.process(harness.document_update(906))
    # الرد فشل ⇒ فشل مُسجّل (مش تجاهل صامت). النية الدائمة (صف العنصر) اتكتبت قبله.
    assert harness.db.update_failure(906) is not None
    assert harness.db._conn.execute("SELECT COUNT(*) c FROM attachment_batches").fetchone()["c"] == 1


def test_handler_stored_item_is_not_dispatched(tmp_path, monkeypatch):
    # A2 ما بترسلش أي حاجة (مفيش صندوق/إنشاء) — التسليم مرحلة A3/B.
    harness = _harness(tmp_path, monkeypatch)
    harness.db.set_awaiting(OWNER_ID, CID, "route", title="A")
    harness.process(harness.document_update(907))
    assert harness.db.count_outbox() == 0
    assert harness.db.list_open_creation_jobs() == []


def test_handler_streamed_oversize_replies_too_large(tmp_path, monkeypatch):
    # البايتات الفعلية أكبر من سقف A1 (3 MiB) ⇒ رد «كبير أوي»، والعنصر يفضل pending.
    harness = _harness(tmp_path, monkeypatch, file_bytes=b"x" * (3 * 1024 * 1024 + 1))
    harness.db.set_awaiting(OWNER_ID, CID, "route", title="A")
    harness.process(harness.document_update(908))
    assert harness.replies == [h_mod.ATTACHMENT_TOO_LARGE_TEXT]
    batch_id = harness.db._conn.execute("SELECT batch_id FROM attachment_batches").fetchone()["batch_id"]
    items = harness.db.list_attachment_items(batch_id)
    assert len(items) == 1 and items[0].status == ATTACHMENT_BATCH_PENDING
    assert harness.db.update_outcome(908) == "durable_intent_recorded"


def test_handler_second_document_appends_same_batch(tmp_path, monkeypatch):
    harness = _harness(tmp_path, monkeypatch)
    harness.db.set_awaiting(OWNER_ID, CID, "route", title="A")
    harness.process(harness.document_update(909))
    harness.process(harness.document_update(910))
    assert harness.db._conn.execute("SELECT COUNT(*) c FROM attachment_batches").fetchone()["c"] == 1
    batch_id = harness.db._conn.execute("SELECT batch_id FROM attachment_batches").fetchone()["batch_id"]
    assert len(harness.db.list_attachment_items(batch_id)) == 2


def test_handle_attachment_registered_for_documents():
    app = app_mod.build_application(make_config_only())
    callbacks = {h.callback for group in app.handlers.values() for h in group}
    assert h_mod.handle_attachment in callbacks


def make_config_only() -> Config:
    import tempfile

    return Config(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({OWNER_ID}),
        owner_id=OWNER_ID,
        db_path=os.path.join(tempfile.mkdtemp(), "t.sqlite3"),
    )
