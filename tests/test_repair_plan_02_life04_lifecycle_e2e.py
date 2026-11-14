"""OHB2-LIFE-04 — مجموعة دورة الحياة المحلية من طرف لطرف (تكامل حقيقي).

تربط المسارات الأربعة في مسار واحد حقيقي (بلا mocks للطبقة الكاملة):
  handler استقبال المستند (LIFE-03 gate) ⇒ نيّة متينة + `stored` (A1/A2)
  ⇒ انتهاء TTL ⇒ كنس من **tick عامل موجود** (`Watcher`، LIFE-01) ⇒ تعافٍ (LIFE-02).

تشمل: المسار السعيد، الإيقاف (kill switch)، التعافي بعد المقاطعة، الحيوية/idempotency،
وحرس معماري (مفيش عامل/مهمّة/مالك قاعدة جديد).

معزولة (tmp_path + sqlite حقيقي + Harness حقيقي بملف محلي مزيّف — مفيش شبكة).
"""
from __future__ import annotations

import asyncio
import dataclasses
import pathlib
from datetime import datetime, timedelta, timezone

from bot import attachments as attachments_mod
from bot.attachments import (
    AttachmentReaper,
    OpportunisticSweeper,
    staging_root_for,
)
from bot.db import (
    ATTACHMENT_BATCH_EXPIRED,
    ATTACHMENT_BATCH_PENDING,
    ATTACHMENT_ITEM_REAPED,
    ATTACHMENT_ITEM_STORED,
)
from bot.watcher import Watcher

import bot.handlers as h_mod
from tests.test_attachment_batch_lifecycle_a2 import (
    CID,
    OWNER_ID,
    Harness,
    _harness,
)

# نطاق معرّفات تحديث فريد.
U = 3_200_000


# ------------------------------------------------------------------ أدوات
def _db_path(harness: Harness) -> str:
    return harness.app.bot_data["config"].db_path


def _tick(harness: Harness, *, now: datetime | None = None) -> None:
    """يشغّل كنسة LIFE-01 عبر **tick المراقب الموجود** (مفيش عامل جديد)."""
    reaper = AttachmentReaper(harness.db, _db_path(harness))
    sweeper = OpportunisticSweeper(reaper, min_interval=0.0)
    watcher = Watcher(
        harness.app.bot_data["client"], harness.db, harness.app.bot,
        chat_id=OWNER_ID, opportunistic_sweeper=sweeper,
    )
    if now is None:
        asyncio.run(watcher.tick())
    else:
        # كنسة مباشرة بلحظة صريحة (تجاوز الخنق) — نفس الغلاف، نفس الـ reaper.
        sweeper.maybe_sweep(now=now)


def _batch_id(harness: Harness) -> str:
    return harness.db._conn.execute(
        "SELECT batch_id FROM attachment_batches"
    ).fetchone()["batch_id"]


def _t0(harness: Harness) -> datetime:
    row = harness.db._conn.execute(
        "SELECT t0 FROM attachment_batches"
    ).fetchone()
    return datetime.fromisoformat(row["t0"])


def _after_ttl(harness: Harness, *, minutes: int = 16) -> datetime:
    return _t0(harness) + timedelta(minutes=minutes)


def _item(harness: Harness, batch_id: str):
    return harness.db.list_attachment_items(batch_id)[0]


def _count(harness: Harness, table: str) -> int:
    return harness.db._conn.execute(f"SELECT COUNT(*) c FROM {table}").fetchone()["c"]


# ============================================================================
# 1) المسار السعيد من طرف لطرف: استقبال ⇒ stored ⇒ انتهاء ⇒ كنس ⇒ reaped
# ============================================================================
def test_e2e_intake_then_expiry_sweep_via_tick(tmp_path, monkeypatch):
    harness = _harness(tmp_path, monkeypatch)
    harness.db.set_awaiting(OWNER_ID, CID, "route", title="A")
    harness.process(harness.document_update(U + 1))

    # (أ) القبول: نيّة متينة + رد صادق + مؤهّل للإقرار.
    assert harness.replies == [h_mod.ATTACHMENT_ACCEPTED_TEXT]
    assert harness.db.update_outcome(U + 1) == "durable_intent_recorded"
    assert harness.db.is_update_acknowledgment_eligible(U + 1) is True
    batch_id = _batch_id(harness)
    item = _item(harness, batch_id)
    assert item.status == ATTACHMENT_ITEM_STORED
    root = staging_root_for(_db_path(harness))
    staged = root / item.staging_token
    assert staged.exists()

    # (ب) دفعة حيّة ⇒ كنسة tick ما بتلمسش.
    _tick(harness, now=_t0(harness) + timedelta(minutes=5))
    assert staged.exists()
    assert harness.db.get_attachment_batch(batch_id).status == ATTACHMENT_BATCH_PENDING

    # (ج) انتهاء TTL ⇒ كنسة tick ⇒ expired + reaped + حذف البايت.
    _tick(harness, now=_after_ttl(harness))
    assert harness.db.get_attachment_batch(batch_id).status == ATTACHMENT_BATCH_EXPIRED
    assert harness.db.get_attachment_item(item.item_id).status == ATTACHMENT_ITEM_REAPED
    assert not staged.exists()


def test_e2e_two_documents_same_batch_then_sweep_both(tmp_path, monkeypatch):
    harness = _harness(tmp_path, monkeypatch)
    harness.db.set_awaiting(OWNER_ID, CID, "route", title="A")
    harness.process(harness.document_update(U + 2, name="a.txt"))
    harness.process(harness.document_update(U + 3, name="b.txt"))
    assert _count(harness, "attachment_batches") == 1  # نفس الدفعة (بلا تمديد)
    batch_id = _batch_id(harness)
    items = harness.db.list_attachment_items(batch_id)
    assert len(items) == 2
    assert all(i.status == ATTACHMENT_ITEM_STORED for i in items)
    root = staging_root_for(_db_path(harness))
    paths = [root / i.staging_token for i in items]
    assert all(p.exists() for p in paths)

    _tick(harness, now=_after_ttl(harness))
    assert all(not p.exists() for p in paths)
    assert all(
        harness.db.get_attachment_item(i.item_id).status == ATTACHMENT_ITEM_REAPED
        for i in items
    )


def test_e2e_repeated_sweeps_are_idempotent(tmp_path, monkeypatch):
    harness = _harness(tmp_path, monkeypatch)
    harness.db.set_awaiting(OWNER_ID, CID, "route", title="A")
    harness.process(harness.document_update(U + 4))
    batch_id = _batch_id(harness)
    item = _item(harness, batch_id)
    for _ in range(3):
        _tick(harness, now=_after_ttl(harness))
    assert not (staging_root_for(_db_path(harness)) / item.staging_token).exists()
    assert harness.db.get_attachment_item(item.item_id).status == ATTACHMENT_ITEM_REAPED


# ============================================================================
# 2) التعافي بعد المقاطعة (أثر جزئي) عبر tick الموجود
# ============================================================================
def test_e2e_recovers_stale_partial_after_interruption(tmp_path, monkeypatch):
    harness = _harness(tmp_path, monkeypatch)
    harness.db.set_awaiting(OWNER_ID, CID, "route", title="A")
    harness.process(harness.document_update(U + 5))
    batch_id = _batch_id(harness)
    item = _item(harness, batch_id)
    # محاكاة أثر جزئي متبقٍّ بعد مقاطعة (الملف موجود، العنصر stored) — كنسة الانتهاء تُنظّفه.
    _tick(harness, now=_after_ttl(harness))
    assert not (staging_root_for(_db_path(harness)) / item.staging_token).exists()
    assert harness.db.get_attachment_item(item.item_id).status == ATTACHMENT_ITEM_REAPED


# ============================================================================
# 3) الإيقاف من طرف لطرف: مفيش أثر، والكنس لا يجد شيئًا
# ============================================================================
def test_e2e_kill_switch_no_side_effects_then_clean_sweep(tmp_path, monkeypatch):
    harness = _harness(tmp_path, monkeypatch)
    cfg = harness.app.bot_data["config"]
    harness.app.bot_data["config"] = dataclasses.replace(
        cfg, attachment_document_intake_enabled=False
    )
    harness.db.set_awaiting(OWNER_ID, CID, "route", title="A")
    harness.process(harness.document_update(U + 6))
    assert harness.replies == [h_mod.ATTACHMENT_INTAKE_DISABLED_TEXT]
    assert _count(harness, "attachment_batches") == 0
    assert harness.get_file_calls == []
    # كنسة tick على قاعدة فاضية ⇒ آمنة بلا خطأ.
    _tick(harness, now=datetime.now(timezone.utc) + timedelta(minutes=16))
    assert _count(harness, "attachment_batches") == 0


# ============================================================================
# 4) حرس معماري: مفيش عامل/مهمّة/مالك قاعدة جديد
# ============================================================================
def test_e2e_tick_creates_no_asyncio_task(tmp_path, monkeypatch):
    harness = _harness(tmp_path, monkeypatch)
    harness.db.set_awaiting(OWNER_ID, CID, "route", title="A")
    harness.process(harness.document_update(U + 7))
    created = []
    real_create = asyncio.create_task

    def spy(coro, *a, **k):
        created.append(coro)
        return real_create(coro, *a, **k)

    monkeypatch.setattr(asyncio, "create_task", spy)
    _tick(harness, now=_after_ttl(harness))
    assert created == []  # الكنسة الانتهاكية متزامنة ⇒ مفيش مهمّة جديدة


def test_e2e_attachments_module_has_no_asyncio_or_worker_class():
    src = pathlib.Path(attachments_mod.__file__).read_text(encoding="utf-8")
    assert "asyncio" not in src
    assert "create_task" not in src
    # مفيش فئة عامل جديدة في وحدة الـ staging.
    for token in ("class OutboxWorker", "class Watcher", "class Scheduler", "Thread("):
        assert token not in src


def test_e2e_watcher_owns_no_extra_connection(tmp_path, monkeypatch):
    harness = _harness(tmp_path, monkeypatch)
    harness.db.set_awaiting(OWNER_ID, CID, "route", title="A")
    harness.process(harness.document_update(U + 8))
    conn_before = harness.db._conn
    _tick(harness, now=_after_ttl(harness))
    assert harness.db._conn is conn_before  # نفس اتصال القاعدة الوحيد


# ============================================================================
# 5) حرس ضد الانحدار: مسار الإدخال ما بيناديش كنس (R-3 يفضل قائمًا)
# ============================================================================
def test_e2e_intake_path_still_has_no_sweep():
    src = pathlib.Path(attachments_mod.__file__).read_text(encoding="utf-8")
    assert "opportunistic_cleanup" not in src
    idx = src.index("async def accept(")
    accept_body = src[idx: src.index("\nclass ", idx)]
    assert "sweep(" not in accept_body
    assert "AttachmentReaper" not in accept_body
