"""OHB2-SW03: إعادة محاولة **محدودة** مشتركة لقراءة شاهد الحذف (طبقة القاعدة).

بتغطّي: التصنيف العابر (BUSY/LOCKED) مقابل الدائم، عدّ المحاولات بالظبط، ترتيب المُدد،
الحفاظ على الاستثناء الأصلي، وسياسة مشتركة واحدة بين البوت والـ Mini App.
كل التأخيرات مُرقّعة (`time.sleep`) ⇒ مفيش انتظار حقيقي.
"""
from __future__ import annotations

import os
import sqlite3

import pytest

import bot.db as db_module
import bot.handlers as h
from bot import outbox
from bot.db import Database

_SQLITE_BUSY = getattr(sqlite3, "SQLITE_BUSY", 5)
_SQLITE_LOCKED = getattr(sqlite3, "SQLITE_LOCKED", 6)


def _busy() -> sqlite3.OperationalError:
    exc = sqlite3.OperationalError("database is locked")
    exc.sqlite_errorcode = _SQLITE_BUSY
    return exc


def _locked() -> sqlite3.OperationalError:
    exc = sqlite3.OperationalError("database table is locked")
    exc.sqlite_errorcode = _SQLITE_LOCKED
    return exc


def _permanent() -> sqlite3.OperationalError:
    exc = sqlite3.OperationalError("no such table: deleted_conversations")
    exc.sqlite_errorcode = getattr(sqlite3, "SQLITE_ERROR", 1)
    return exc


class _ScriptedDB(Database):
    """قاعدة حقيقية مع `is_deleted` مُبرمَج: كل نداء ياخد النتيجة/الاستثناء التالي.

    آخر عنصر بيتكرّر بعد ما القايمة تخلص (عشان «فشل مستمر»).
    """

    def __init__(self, outcomes):
        super().__init__(":memory:")
        self._outcomes = list(outcomes)
        self.calls = 0

    def is_deleted(self, conversation_id: str) -> bool:
        self.calls += 1
        idx = min(self.calls - 1, len(self._outcomes) - 1)
        outcome = self._outcomes[idx]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def sleep_recorder(monkeypatch):
    delays: list[float] = []
    monkeypatch.setattr(db_module.time, "sleep", delays.append)
    return delays


def _real_db(tmp_path) -> Database:
    return Database(os.path.join(tmp_path, "sw03.sqlite3"))


# ---------------------------------------------------------------- real reads
def test_successful_tombstone_read_returns_true(tmp_path):
    db = _real_db(tmp_path)
    db.delete_conversation("c1", outbox.now_iso(), remote_confirmed=True)
    assert db.is_deleted_with_retry("c1") is True


def test_successful_non_tombstone_read_returns_false(tmp_path):
    db = _real_db(tmp_path)
    assert db.is_deleted_with_retry("c1") is False


# ------------------------------------------------------------ transient recovery
def test_busy_then_success_recovers(sleep_recorder):
    db = _ScriptedDB([_busy(), True])
    assert db.is_deleted_with_retry("c1") is True
    assert db.calls == 2  # محاولة + إعادة واحدة
    assert sleep_recorder == [0.25]


def test_locked_then_success_recovers(sleep_recorder):
    db = _ScriptedDB([_locked(), _locked(), False])
    assert db.is_deleted_with_retry("c1") is False
    assert db.calls == 3
    assert sleep_recorder == [0.25, 0.5]


# --------------------------------------------------------- exhaustion / propagate
def test_repeated_busy_exhausts_four_attempts_and_propagates(sleep_recorder):
    original = _busy()
    db = _ScriptedDB([original])
    with pytest.raises(sqlite3.OperationalError) as ei:
        db.is_deleted_with_retry("c1")
    assert db.calls == 4  # 1 أصلية + 3 إعادات
    assert sleep_recorder == [0.25, 0.5, 1.0]
    assert ei.value is original  # الاستثناء الأصلي نفسه (مش مغلّف)


def test_repeated_locked_exhausts_four_attempts_and_propagates(sleep_recorder):
    original = _locked()
    db = _ScriptedDB([original])
    with pytest.raises(sqlite3.OperationalError) as ei:
        db.is_deleted_with_retry("c1")
    assert db.calls == 4
    assert sleep_recorder == [0.25, 0.5, 1.0]
    assert ei.value is original


# ------------------------------------------------------------- permanent / other
def test_permanent_sqlite_error_not_retried(sleep_recorder):
    db = _ScriptedDB([_permanent()])
    with pytest.raises(sqlite3.OperationalError, match="no such table"):
        db.is_deleted_with_retry("c1")
    assert db.calls == 1  # مفيش إعادة
    assert sleep_recorder == []


def test_non_sqlite_error_not_retried(sleep_recorder):
    db = _ScriptedDB([RuntimeError("bug")])
    with pytest.raises(RuntimeError, match="bug"):
        db.is_deleted_with_retry("c1")
    assert db.calls == 1
    assert sleep_recorder == []


# ------------------------------------------------------------- delay policy
def test_retry_delays_exact():
    assert db_module.DEDUPE_RETRY_DELAYS == (0.25, 0.5, 1.0)


def test_shared_policy_between_db_and_handlers():
    """سياسة واحدة: البوت بيعيد تصدير نفس الأسماء من طبقة القاعدة (مفيش تكرار سياسة)."""
    assert h._DEDUPE_RETRY_DELAYS is db_module.DEDUPE_RETRY_DELAYS
    assert h._is_transient_sqlite_error is db_module.is_transient_sqlite_error


# ------------------------------------------------------------- classifier
def test_classifier_busy_locked_by_code():
    assert db_module.is_transient_sqlite_error(_busy()) is True
    assert db_module.is_transient_sqlite_error(_locked()) is True


def test_classifier_permanent_and_non_sqlite_false():
    assert db_module.is_transient_sqlite_error(_permanent()) is False
    assert db_module.is_transient_sqlite_error(RuntimeError("x")) is False


def test_classifier_text_fallback_without_code():
    assert db_module.is_transient_sqlite_error(
        sqlite3.OperationalError("database is busy")
    ) is True
    assert db_module.is_transient_sqlite_error(
        sqlite3.OperationalError("database table is locked")
    ) is True
