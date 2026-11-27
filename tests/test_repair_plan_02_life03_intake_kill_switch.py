"""OHB2-LIFE-03 — مفتاح إيقاف استقبال المستندات المحلي (محلي فقط، قابل للعكس).

مفتاح **مستقلّ** `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` (افتراضيًا **معطّل** = opt-in صريح):
- **معطّل** ⇒ `handle_attachment` يرفض **قبل** أي `get_file`/تنزيل/صف/ملف/نداء OpenHands/
  سجل outbox، مع رسالة صادقة (`ATTACHMENT_INTAKE_DISABLED_TEXT`)، والتحديث يُسجَّل
  `explicitly_ignored` (مؤهّل للإقرار، بلا حجب الحدّ).
- **لا يعطّل** مسارات النص/الأزرار/Mini App، ولا مسار رفض الوسائط غير المدعومة
  (`handle_unsupported_attachment`) اللي يفضل شغّالًا.
- عكوس بلا فقدان بيانات: إعادة التفعيل ترجّع السلوك بالظبط.

الساعات/الشبكة معزولة (نفس Harness اختبارات A2 الحقيقي — ملف محلي مزيّف، مفيش شبكة).
"""
from __future__ import annotations

import dataclasses

import pytest

import bot.handlers as h_mod
from bot.db import Database

from tests.test_attachment_batch_lifecycle_a2 import (
    CID,
    OWNER_ID,
    Harness,
    _harness,
)

# نطاق معرّفات تحديث فريد (لا يتقاطع مع الملفات الأخرى).
U = 3_100_000


# ------------------------------------------------------------------ أدوات
def _disable_intake(harness: Harness) -> None:
    cfg = harness.app.bot_data["config"]
    harness.app.bot_data["config"] = dataclasses.replace(
        cfg, attachment_document_intake_enabled=False
    )


def _count(db: Database, table: str) -> int:
    return db._conn.execute(f"SELECT COUNT(*) c FROM {table}").fetchone()["c"]


def _batch_rows(db: Database) -> int:
    return _count(db, "attachment_batches")


# ============================================================================
# 1) المعطّل ⇒ رفض صادق قبل أي أثر جانبي
# ============================================================================
def test_disabled_intake_rejects_with_truthful_message(tmp_path, monkeypatch):
    harness = _harness(tmp_path, monkeypatch)
    _disable_intake(harness)
    harness.db.set_last_accessed_conversation(OWNER_ID, CID)
    harness.process(harness.document_update(U + 1))
    assert harness.replies == [h_mod.ATTACHMENT_INTAKE_DISABLED_TEXT]


def test_disabled_intake_does_not_call_get_file(tmp_path, monkeypatch):
    harness = _harness(tmp_path, monkeypatch)
    _disable_intake(harness)
    harness.db.set_last_accessed_conversation(OWNER_ID, CID)
    harness.process(harness.document_update(U + 2))
    assert harness.get_file_calls == []  # مفيش get_file خالص


def test_disabled_intake_creates_no_rows_or_files(tmp_path, monkeypatch):
    harness = _harness(tmp_path, monkeypatch)
    _disable_intake(harness)
    harness.db.set_last_accessed_conversation(OWNER_ID, CID)
    harness.process(harness.document_update(U + 3))
    assert _batch_rows(harness.db) == 0            # مفيش دفعة
    assert _count(harness.db, "attachment_items") == 0
    assert _count(harness.db, "attachment_message_identity") == 0
    # مفيش ملف في جذر الـ staging.
    from bot.attachments import staging_root_for

    root = staging_root_for(harness.app.bot_data["config"].db_path)
    assert (not root.exists()) or (list(root.iterdir()) == [])


def test_disabled_intake_makes_no_openhands_call(tmp_path, monkeypatch):
    harness = _harness(tmp_path, monkeypatch)
    _disable_intake(harness)
    harness.db.set_last_accessed_conversation(OWNER_ID, CID)
    harness.app.bot_data["client"].calls.clear()
    harness.process(harness.document_update(U + 4))
    assert harness.app.bot_data["client"].calls == []  # مفيش نداء OpenHands


def test_disabled_intake_writes_no_outbox_row(tmp_path, monkeypatch):
    harness = _harness(tmp_path, monkeypatch)
    _disable_intake(harness)
    harness.db.set_last_accessed_conversation(OWNER_ID, CID)
    harness.process(harness.document_update(U + 5))
    assert _count(harness.db, "outbox") == 0


def test_disabled_intake_records_explicitly_ignored(tmp_path, monkeypatch):
    harness = _harness(tmp_path, monkeypatch)
    _disable_intake(harness)
    harness.db.set_last_accessed_conversation(OWNER_ID, CID)
    harness.process(harness.document_update(U + 6))
    assert harness.db.update_outcome(U + 6) == "explicitly_ignored"
    assert harness.db.is_update_acknowledgment_eligible(U + 6) is True


def test_disabled_intake_no_download_helper_invoked(tmp_path, monkeypatch):
    """لا نداء لمسار التنزيل المقيّد (`_download_attachment_chunks`) ولا `get_file`."""
    harness = _harness(tmp_path, monkeypatch)
    _disable_intake(harness)
    harness.db.set_last_accessed_conversation(OWNER_ID, CID)
    called = []
    real = h_mod._download_attachment_chunks

    async def spy(*a, **k):
        called.append(True)
        return await real(*a, **k)

    monkeypatch.setattr(h_mod, "_download_attachment_chunks", spy)
    harness.process(harness.document_update(U + 7))
    assert called == []


# ============================================================================
# 2) التفعيل الصريح (opt-in) ⇒ السلوك السابق محفوظ
# ============================================================================
def test_explicit_enable_stores_document(tmp_path, monkeypatch):
    harness = _harness(tmp_path, monkeypatch)
    assert harness.app.bot_data["config"].attachment_document_intake_enabled is True
    harness.db.set_last_accessed_conversation(OWNER_ID, CID)
    harness.process(harness.document_update(U + 8))
    assert harness.replies == [h_mod.ATTACHMENT_ACCEPTED_TEXT]
    assert _batch_rows(harness.db) == 1


def test_re_enabling_restores_behavior(tmp_path, monkeypatch):
    """عكوس بلا فقدان: تعطيل ثم تفعيل ⇒ نفس السلوك الأصلي."""
    harness = _harness(tmp_path, monkeypatch)
    harness.db.set_last_accessed_conversation(OWNER_ID, CID)
    _disable_intake(harness)
    harness.process(harness.document_update(U + 9))
    assert harness.replies == [h_mod.ATTACHMENT_INTAKE_DISABLED_TEXT]
    assert _batch_rows(harness.db) == 0
    # إعادة التفعيل.
    cfg = harness.app.bot_data["config"]
    harness.app.bot_data["config"] = dataclasses.replace(
        cfg, attachment_document_intake_enabled=True
    )
    harness.process(harness.document_update(U + 10))
    assert harness.replies[-1] == h_mod.ATTACHMENT_ACCEPTED_TEXT
    assert _batch_rows(harness.db) == 1


# ============================================================================
# 3) ما بيعطّلش مسار رفض الوسائط غير المدعومة
# ============================================================================
def test_disabled_intake_keeps_unsupported_media_rejection(tmp_path, monkeypatch):
    harness = _harness(tmp_path, monkeypatch)
    _disable_intake(harness)
    harness.process(harness.photo_update(U + 11))
    # مسار رفض الوسائط غير المدعومة يفضل شغّالًا (رسالته الخاصة، مش رسالة الإيقاف).
    assert harness.replies == [h_mod.UNSUPPORTED_ATTACHMENT_TEXT]


# ============================================================================
# 4) ما بيعطّلش مسار النص
# ============================================================================
def test_disabled_intake_does_not_block_text_path(tmp_path, monkeypatch):
    harness = _harness(tmp_path, monkeypatch)
    _disable_intake(harness)
    # مسار النص لا يمرّ بـ handle_attachment إطلاقًا (تأكيد مصدري: المفتاح محصور هناك).
    import inspect

    src = inspect.getsource(h_mod.handle_attachment)
    assert "attachment_document_intake_enabled" in src
    for name in ("handle_text", "handle_reply", "send_reply_txt"):
        fn = getattr(h_mod, name, None)
        if fn is not None:
            assert "attachment_document_intake_enabled" not in inspect.getsource(fn)


# ============================================================================
# 5) تحقّق الإعداد (افتراضي/قيم صريحة/قيمة غلط)
# ============================================================================
def _env(**kw):
    base = {
        "TELEGRAM_BOT_TOKEN": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        "OPENHANDS_API_KEY": "sk-oh-test-key-123456",
        "ALLOWED_TELEGRAM_ID": "1",
        "DB_PATH": "/tmp/x.sqlite3",
    }
    base.update(kw)
    return base


def test_config_default_disabled():
    from bot.config import load_config

    cfg = load_config(_env())
    assert cfg.attachment_document_intake_enabled is False


@pytest.mark.parametrize("raw,expected", [
    ("0", False), ("false", False), ("no", False), ("off", False),
    ("1", True), ("true", True), ("yes", True), ("on", True),
])
def test_config_explicit_values(raw, expected):
    from bot.config import load_config

    cfg = load_config(_env(ATTACHMENT_DOCUMENT_INTAKE_ENABLED=raw))
    assert cfg.attachment_document_intake_enabled is expected


def test_config_invalid_value_rejected():
    from bot.config import ConfigError, load_config

    with pytest.raises(ConfigError):
        load_config(_env(ATTACHMENT_DOCUMENT_INTAKE_ENABLED="maybe"))


def test_config_error_message_does_not_leak_value():
    from bot.config import ConfigError, load_config

    with pytest.raises(ConfigError) as ei:
        load_config(_env(ATTACHMENT_DOCUMENT_INTAKE_ENABLED="super-secret-xyz"))
    assert "super-secret-xyz" not in str(ei.value)


# ============================================================================
# 6) المفتاح يظهر في .env.example (موثّق)
# ============================================================================
def test_env_example_documents_flag():
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1]
    text = (root / ".env.example").read_text(encoding="utf-8")
    assert "ATTACHMENT_DOCUMENT_INTAKE_ENABLED=0" in text
