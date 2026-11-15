"""OHB2-REPAIR-PLAN-02/LIFE-01/F2 — منع إحياء مرفق منتهي/مكنوس بالكتابة المتأخّرة.

المرجع: مراجعة LIFE-01 المستقلة — F2: نافذة تنزيل غير متزامنة (`concurrent_updates(True)`)
بتخلّي الكنس (LIFE-01 من tick المراقب) يوسم الدفعة `expired` والعنصر `reaped`، وبعدها
الكتابة المتأخّرة كانت بتغيّر العنصر لـ `stored` **بلا شرط** ⇒ عنصر `stored` جوّه دفعة
منتهية (إحياء).

الإصلاح: الانتقال النهائي `pending ⇒ stored` بقى **ذرّيًّا مشروطًا**
(`Database.try_mark_attachment_item_stored`): العنصر `pending` **و** الدفعة الأب `pending`،
كله في نفس الـ`UPDATE` (تقييم لحظة الكتابة) ⇒ أي كتابة متأخّرة تُرفض (fail closed)، والملف
المُملوك الجديد بيتشال، ومفيش ادّعاء نجاح.

قاعدة SQLite حقيقية + مجلد staging حقيقي + أدوات تنزيل/ساعة متحكَّم فيها + حواجز حتمية.
"""
from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timezone

import pytest

from bot.attachments import (
    AcceptOutcome,
    AttachmentReaper,
    AttachmentService,
    OpportunisticSweeper,
    StageStatus,
    StagingStore,
    staging_root_for,
)
from bot.db import (
    ATTACHMENT_BATCH_DELIVERED,
    ATTACHMENT_BATCH_EXPIRED,
    ATTACHMENT_BATCH_PENDING,
    ATTACHMENT_ITEM_REAPED,
    ATTACHMENT_ITEM_STORED,
    Database,
)
from bot.files import IdentityCache
from bot.watcher import Watcher

OWNER_ID = 111
OWNER_UUID = "11111111-2222-3333-4444-555555555555"
CID = "11111111222233334444555566667777"
# `T0` حيّ (قبل انتهاء المهلة بكتير) للاختبارات المتزامنة.
T0 = datetime(2026, 11, 14, 10, 0, 0, tzinfo=timezone.utc)
NOW_LIVE = datetime(2026, 11, 14, 10, 5, tzinfo=timezone.utc)     # داخل المهلة
NOW_AFTER = datetime(2026, 11, 14, 10, 16, tzinfo=timezone.utc)   # بعد الحدّ
# `T0` «قبل الانتهاء مباشرةً» لسباق A: القبول حيّ، والكنسة بعده فورًا منتهية.
T0_RIGHT_BEFORE_EXPIRY = datetime(2026, 11, 14, 10, 0, 0, 1, tzinfo=timezone.utc)


class FakeClient:
    def __init__(self, owner=OWNER_UUID):
        self.owner = owner

    async def get_current_user(self):
        return {"id": self.owner}

    async def get_conversations(self, ids):
        return [{"id": CID, "created_by_user_id": self.owner, "title": "A"} for _ in ids]


def make_env(tmp_path):
    db_path = str(tmp_path / "state.sqlite3")
    db = Database(db_path)
    store = StagingStore(db, db_path)
    client = FakeClient()
    service = AttachmentService(db, store, client, IdentityCache(client))
    return db, store, service, db_path


def reaper(db, db_path):
    return AttachmentReaper(db, db_path)


def _run(coro):
    return asyncio.run(coro)


async def accept(service, *, now=T0, name="a.txt", chunks=(b"data",), declared=None,
                 update_id=None, factory=None):
    async def default_factory():
        return iter(chunks)

    return await service.accept(
        telegram_id=OWNER_ID,
        conversation_id=CID,
        display_name=name,
        declared_size=declared,
        update_id=update_id,
        now=now,
        chunks_factory=factory if factory is not None else default_factory,
    )


def only_batch(db):
    batches = db.list_all_attachment_batches()
    assert len(batches) == 1
    return batches[0]


def item_of(db, batch_id):
    items = db.list_attachment_items(batch_id)
    assert len(items) == 1
    return items[0]


def staged_names(db_path):
    root = staging_root_for(db_path)
    if not root.exists():
        return []
    return sorted(p.name for p in root.iterdir())


# ============================================================================
# Race A — الكنس بيكسب قبل الكتابة المتأخّرة (الكنس عبر tick المراقب الحقيقي)
# ============================================================================
def test_race_a_reaper_wins_before_late_store(tmp_path):
    db, store, service, db_path = make_env(tmp_path)
    reaper_obj = reaper(db, db_path)
    real_sweep = reaper_obj.sweep
    # نخلي كنسة المراقب تستخدم `NOW_AFTER` حتميًّا (بدل ساعة الحائط).
    reaper_obj.sweep = lambda *, now: real_sweep(now=NOW_AFTER)
    sweeper = OpportunisticSweeper(reaper_obj)

    class _NoClient:
        async def get_conversations(self, ids):  # pragma: no cover
            return []

    watcher = Watcher(_NoClient(), db, bot=None, chat_id=OWNER_ID,
                      opportunistic_sweeper=sweeper)

    async def scenario():
        reached = asyncio.Event()
        gate = asyncio.Event()

        async def factory():
            reached.set()
            await gate.wait()  # نتوقّف جوه نافذة التنزيل غير المتزامنة
            return iter([b"data"])

        task = asyncio.ensure_future(accept(service, now=T0_RIGHT_BEFORE_EXPIRY,
                                            factory=factory))
        await asyncio.wait_for(reached.wait(), timeout=5)
        # دلوقتي: العنصر `pending` والدفعة `pending` (بايتات لسه ما اتنزّلتش).
        batch = only_batch(db)
        assert batch.status == ATTACHMENT_BATCH_PENDING
        assert item_of(db, batch.batch_id).status == ATTACHMENT_BATCH_PENDING
        # مسار الكنس الحقيقي من tick المراقب (الدفعة فاتت المهلة الآن).
        await asyncio.wait_for(watcher.tick(), timeout=5)
        assert db.get_attachment_batch(batch.batch_id).status == ATTACHMENT_BATCH_EXPIRED
        assert db.get_attachment_item(item_of(db, batch.batch_id).item_id).status == \
            ATTACHMENT_ITEM_REAPED
        # نكمل التنزيل/الكتابة المتأخّرة.
        gate.set()
        return batch.batch_id, await asyncio.wait_for(task, timeout=5)

    batch_id, result = _run(scenario())
    # الكتابة المتأخّرة **ما تقدرش** تحيي العنصر/الدفعة.
    assert result.outcome is not AcceptOutcome.STORED
    assert db.get_attachment_item(item_of(db, batch_id).item_id).status == ATTACHMENT_ITEM_REAPED
    assert db.get_attachment_batch(batch_id).status == ATTACHMENT_BATCH_EXPIRED
    assert staged_names(db_path) == []  # مفيش ملف يتيم
    assert db.count_outbox() == 0  # مفيش مسار برومت/إرسال


# ============================================================================
# Race B — الكتابة بتكسب قبل الكنس، والكنس بعدها آمن
# ============================================================================
def test_race_b_store_wins_then_reaper_expires_safely(tmp_path):
    db, store, service, db_path = make_env(tmp_path)
    res = _run(accept(service, now=T0))
    assert res.outcome is AcceptOutcome.STORED
    batch_id = res.batch_id
    item = item_of(db, batch_id)
    assert item.status == ATTACHMENT_ITEM_STORED
    token = item.staging_token
    assert (staging_root_for(db_path) / token).exists()

    # بعد انتهاء المهلة ⇒ الكنس يوسم الدفعة expired والعنصر reaped ويشيل البايتات بأمان.
    rep = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert rep.files_deleted == 1
    assert db.get_attachment_batch(batch_id).status == ATTACHMENT_BATCH_EXPIRED
    assert db.get_attachment_item(item.item_id).status == ATTACHMENT_ITEM_REAPED
    assert not (staging_root_for(db_path) / token).exists()


# ============================================================================
# Race C1 — حاجز بين الكتابة والانتقال: الكنس الكامل (expire+reap+حذف الملف)
# ============================================================================
def test_race_c1_full_reaper_between_write_and_transition(tmp_path, monkeypatch):
    db, store, service, db_path = make_env(tmp_path)
    db.create_attachment_batch("b1", OWNER_ID, CID, T0_RIGHT_BEFORE_EXPIRY.isoformat())

    real_write = store._write_to_path

    def hooked(path, chunks, cap):
        written = real_write(path, chunks, cap)  # الكتابة خلصت
        # حاجز: الكنس الكامل (expire batch + reap item + حذف البايتات) قبل الانتقال.
        reaper(db, db_path).sweep(now=NOW_AFTER)
        return written

    monkeypatch.setattr(store, "_write_to_path", hooked)
    res = store.store(telegram_id=OWNER_ID, batch_id="b1", item_id="i1",
                      display_name="a.txt", chunks=[b"data"])
    assert res.status is not StageStatus.STORED  # مفيش إحياء
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_EXPIRED
    assert db.get_attachment_item("i1").status == ATTACHMENT_ITEM_REAPED
    assert staged_names(db_path) == []


# ============================================================================
# Race C2 — حاجز: الدفعة بقت expired فقط (العنصر لسه pending والملف موجود)
#           ⇒ الانتقال الذرّي **لازم** يرفض (فحص الدفعة الأب وحده كافي)
# ============================================================================
def test_race_c2_expired_batch_between_write_and_transition(tmp_path, monkeypatch):
    db, store, service, db_path = make_env(tmp_path)
    db.create_attachment_batch("b1", OWNER_ID, CID, T0_RIGHT_BEFORE_EXPIRY.isoformat())

    real_write = store._write_to_path

    def hooked(path, chunks, cap):
        written = real_write(path, chunks, cap)
        # حاجز: نافذة «الكنس وسم الدفعة expired لكن لسه ما وسمش العنصر reaped».
        db.mark_attachment_batch_status("b1", ATTACHMENT_BATCH_EXPIRED,
                                        now=NOW_AFTER.isoformat())
        return written

    monkeypatch.setattr(store, "_write_to_path", hooked)
    res = store.store(telegram_id=OWNER_ID, batch_id="b1", item_id="i1",
                      display_name="a.txt", chunks=[b"data"])
    # الانتقال اتّرفض بسبب حالة الدفعة الأب (مش لغياب الملف) ⇒ fail closed.
    assert res.status is StageStatus.DB_FAILED
    assert db.get_attachment_item("i1").status == ATTACHMENT_BATCH_PENDING  # ما اتحوّلش stored
    assert db.get_attachment_batch("b1").status == ATTACHMENT_BATCH_EXPIRED
    assert staged_names(db_path) == []  # الملف المُملوك اتشال، مفيش يتيم


# ============================================================================
# انتقال مباشر: reaped ⇒ stored مرفوض
# ============================================================================
def test_direct_reaped_to_stored_is_rejected(tmp_path):
    db, store, service, db_path = make_env(tmp_path)
    db.create_attachment_batch("b1", OWNER_ID, CID, T0.isoformat())
    db.add_attachment_item("i1", "b1", staging_token="a" * 32, display_name="n",
                           size_bytes=3, status=ATTACHMENT_ITEM_REAPED)
    ok = db.try_mark_attachment_item_stored("i1", size_bytes=3, staging_token="a" * 32)
    assert ok is False
    assert db.get_attachment_item("i1").status == ATTACHMENT_ITEM_REAPED


# ============================================================================
# تخزين داخل دفعة منتهية أصلًا مرفوض
# ============================================================================
def test_store_into_already_expired_batch_is_rejected(tmp_path):
    db, store, service, db_path = make_env(tmp_path)
    db.create_attachment_batch("b1", OWNER_ID, CID, T0.isoformat(),
                               status=ATTACHMENT_BATCH_EXPIRED)
    res = store.store(telegram_id=OWNER_ID, batch_id="b1", item_id="i1",
                      display_name="a.txt", chunks=[b"data"])
    assert res.status is StageStatus.DB_FAILED
    assert db.get_attachment_item("i1").status == ATTACHMENT_BATCH_PENDING
    assert staged_names(db_path) == []


# ============================================================================
# مسار نشط صحيح: عنصر pending ⇒ stored عادي
# ============================================================================
def test_active_pending_item_stores_normally(tmp_path):
    db, store, service, db_path = make_env(tmp_path)
    res = _run(accept(service, now=NOW_LIVE))
    assert res.outcome is AcceptOutcome.STORED
    item = item_of(db, res.batch_id)
    assert item.status == ATTACHMENT_ITEM_STORED
    assert (staging_root_for(db_path) / item.staging_token).exists()


# ============================================================================
# عنصر stored قديم: انتهاء/كنس يفضل صحيح
# ============================================================================
def test_stored_item_expiration_and_reaping_still_correct(tmp_path):
    db, store, service, db_path = make_env(tmp_path)
    res = _run(accept(service, now=NOW_LIVE))
    item = item_of(db, res.batch_id)
    db.mark_attachment_batch_status(res.batch_id, ATTACHMENT_BATCH_DELIVERED,
                                    now=NOW_LIVE.isoformat())
    rep = reaper(db, db_path).sweep(now=NOW_AFTER)
    assert rep.files_deleted == 1
    assert db.get_attachment_item(item.item_id).status == ATTACHMENT_ITEM_REAPED
    assert not (staging_root_for(db_path) / item.staging_token).exists()


# ============================================================================
# رفض الانتقال المتأخّر يشيل **بس** الأثر المُملوك؛ الملفات المجهولة تفضل
# ============================================================================
def test_rejected_transition_removes_only_owned_artifact(tmp_path, monkeypatch):
    db, store, service, db_path = make_env(tmp_path)
    db.create_attachment_batch("b1", OWNER_ID, CID, T0.isoformat(),
                               status=ATTACHMENT_BATCH_EXPIRED)
    root = staging_root_for(db_path)
    root.mkdir(parents=True, exist_ok=True)
    unknown = root / ("u" * 32)
    unknown.write_bytes(b"unknown-not-ours")

    res = store.store(telegram_id=OWNER_ID, batch_id="b1", item_id="i1",
                      display_name="a.txt", chunks=[b"data"], staging_token="k" * 32)
    assert res.status is StageStatus.DB_FAILED
    assert not (root / ("k" * 32)).exists()  # الأثر المُملوك اتشال
    assert unknown.exists()  # الملف المجهول ما اتلمسش
    assert unknown.read_bytes() == b"unknown-not-ours"


# ============================================================================
# التكرار: نفس `update_id` ⇒ مفيش عنصر جديد (idempotent)، بلا أثر آمن مكرّر
# ============================================================================
def test_duplicate_delivery_does_not_corrupt_or_duplicate(tmp_path):
    db, store, service, db_path = make_env(tmp_path)
    r1 = _run(accept(service, now=NOW_LIVE, update_id=9001))
    assert r1.outcome is AcceptOutcome.STORED
    r2 = _run(accept(service, now=NOW_LIVE, update_id=9001))
    assert r2.outcome is AcceptOutcome.DUPLICATE
    batch = only_batch(db)
    assert len(db.list_attachment_items(batch.batch_id)) == 1  # مفيش عنصر مكرّر
    assert item_of(db, batch.batch_id).status == ATTACHMENT_ITEM_STORED
    assert len(staged_names(db_path)) == 1  # ملف واحد بس


# ============================================================================
# T0 الثابت ودليل الهوية يفضلوا كما هم بعد كتابة متأخّرة مرفوضة
# ============================================================================
def test_fixed_t0_and_identity_evidence_unchanged_after_rejected_store(tmp_path):
    db, store, service, db_path = make_env(tmp_path)
    res = _run(accept(service, now=NOW_LIVE))
    batch_id = res.batch_id
    t0_before = db.get_attachment_batch(batch_id).t0
    # دليل هوية عبر مسار الإنتاج (record_attachment_intent) — بينقل الدفعة intent_recorded.
    bound = db.record_attachment_intent(
        batch_id, telegram_id=OWNER_ID, conversation_id=CID, intent_text="نصّ مصاحب",
        now=NOW_LIVE.isoformat(), update_id=None, chat_id=OWNER_ID, message_id=555,
    )
    assert bound == batch_id
    assert db.message_identity_batch_id(OWNER_ID, OWNER_ID, 555) == batch_id
    # كتابة متأخّرة لعنصر جديد على نفس الدفعة (مش pending) ⇒ مرفوضة.
    late = store.store(telegram_id=OWNER_ID, batch_id=batch_id, item_id="late1",
                       display_name="a.txt", chunks=[b"x"])
    assert late.status is StageStatus.DB_FAILED
    assert db.get_attachment_batch(batch_id).t0 == t0_before  # T0 ما اتغيّرش
    assert db.message_identity_batch_id(OWNER_ID, OWNER_ID, 555) == batch_id  # الهوية باقية


# ============================================================================
# قيود المفاتيح الأجنبية/الحذف ما اتنكستش
# ============================================================================
def test_foreign_key_delete_restriction_intact(tmp_path):
    db, store, service, db_path = make_env(tmp_path)
    res = _run(accept(service, now=NOW_LIVE))
    db.record_attachment_intent(
        res.batch_id, telegram_id=OWNER_ID, conversation_id=CID, intent_text="t",
        now=NOW_LIVE.isoformat(), update_id=None, chat_id=OWNER_ID, message_id=777,
    )
    with pytest.raises(sqlite3.IntegrityError):
        db._conn.execute("DELETE FROM attachment_batches WHERE batch_id=?", (res.batch_id,))
    db._conn.rollback()


# ============================================================================
# مفيش نية مرفق تدخل مسار البرومت/الصندوق (outbox)
# ============================================================================
def test_no_attachment_intent_enters_outbox(tmp_path):
    db, store, service, db_path = make_env(tmp_path)
    _run(accept(service, now=NOW_LIVE))
    db.create_attachment_batch("b2", OWNER_ID, CID, T0.isoformat(),
                               status=ATTACHMENT_BATCH_EXPIRED)
    store.store(telegram_id=OWNER_ID, batch_id="b2", item_id="i9",
                display_name="a.txt", chunks=[b"data"])
    assert db.count_outbox() == 0
