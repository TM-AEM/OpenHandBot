"""OHB2-D1: تصنيف أكواد SQLite **الممتدة** لأخطاء BUSY/LOCKED كعابرة.

العيب السابق: `is_transient_sqlite_error` كان بيطابق الكود **الكامل** مقابل {BUSY=5,
LOCKED=6}، فالأكواد الممتدة اللي أصلها BUSY/LOCKED (BUSY_RECOVERY 261،
LOCKED_SHAREDCACHE 262، BUSY_SNAPSHOT 517، BUSY_TIMEOUT 773) كانت تُصنّف **دائمة** ⇒
فشل مقفول بلا إعادة محاولة. الإصلاح: مطابقة الكود **الأساسي** (`sqlite_errorcode & 0xFF`).

الاختبارات دي بتغطّي:
- الأكواد الأساسية والممتدة العابرة ⇒ عابرة.
- أكواد دائمة (IOERR/READONLY/FULL/CANTOPEN/CORRUPT/NOTADB) وامتداداتها ⇒ دائمة.
- الأخطاء بلا `sqlite_errorcode` ⇒ الاحتياطي النصي زي ما هو.
- إعادة المحاولة الفعلية للأكواد الممتدة عبر المُغلّفات الحقيقية + استنفاد الميزانية.
- ثبات المُدد (0.25/0.5/1.0) — مفيش تغيير في سياسة إعادة المحاولة.

كل الأخطاء **مُصنَّعة** (`sqlite_errorcode` يُضاف يدويًّا) عشان التصنيف يكون حتمي وغير
معتمد على سلوك SQLite الخاص بالمنصّة. مفيش قاعدة حيّة ولا ملفات WAL/SHM.
"""
from __future__ import annotations

import asyncio
import os
import sqlite3

import pytest

import bot.db as db_module
import bot.handlers as h
from bot.db import Database

# الأكواد الأساسية (ثابتة في SQLite) — بنستخدم getattr كاحتياطي للتوافق.
_BUSY = getattr(sqlite3, "SQLITE_BUSY", 5)
_LOCKED = getattr(sqlite3, "SQLITE_LOCKED", 6)
_IOERR = getattr(sqlite3, "SQLITE_IOERR", 10)
_READONLY = getattr(sqlite3, "SQLITE_READONLY", 8)
_FULL = getattr(sqlite3, "SQLITE_FULL", 13)
_CANTOPEN = getattr(sqlite3, "SQLITE_CANTOPEN", 14)
_CORRUPT = getattr(sqlite3, "SQLITE_CORRUPT", 11)
_NOTADB = getattr(sqlite3, "SQLITE_NOTADB", 26)

# الأكواد الممتدة: الكود الأساسي = code & 0xFF (بتتفق مع ثوابت SQLite الممتدة).
_BUSY_RECOVERY = 261        # 0x105 -> BUSY
_LOCKED_SHAREDCACHE = 262   # 0x106 -> LOCKED
_BUSY_SNAPSHOT = 517        # 0x205 -> BUSY
_BUSY_TIMEOUT = 773         # 0x305 -> BUSY
_IOERR_READ = 266           # 0x10A -> IOERR (دائم)

_TRANSIENT_CODES = {
    "SQLITE_BUSY": _BUSY,
    "SQLITE_LOCKED": _LOCKED,
    "SQLITE_BUSY_RECOVERY": _BUSY_RECOVERY,
    "SQLITE_LOCKED_SHAREDCACHE": _LOCKED_SHAREDCACHE,
    "SQLITE_BUSY_SNAPSHOT": _BUSY_SNAPSHOT,
    "SQLITE_BUSY_TIMEOUT": _BUSY_TIMEOUT,
}

_PERMANENT_CODES = {
    "SQLITE_IOERR": _IOERR,
    "SQLITE_READONLY": _READONLY,
    "SQLITE_FULL": _FULL,
    "SQLITE_CANTOPEN": _CANTOPEN,
    "SQLITE_CORRUPT": _CORRUPT,
    "SQLITE_NOTADB": _NOTADB,
    "SQLITE_IOERR_READ (extended)": _IOERR_READ,
}


def _exc(code: int, msg: str = "synthetic sqlite error") -> sqlite3.OperationalError:
    """خطأ SQLite مُصنَّع بكود محدّد (زي ما Python 3.11+ بيضيف `sqlite_errorcode`)."""
    exc = sqlite3.OperationalError(msg)
    exc.sqlite_errorcode = code
    return exc


def _busy() -> sqlite3.OperationalError:
    return _exc(_BUSY, "database is locked")


# ============================================================================
# 1) التصنيف: الأساسي + الممتد العابر
# ============================================================================
@pytest.mark.parametrize("name,code", sorted(_TRANSIENT_CODES.items()))
def test_primary_and_extended_transient_codes_are_transient(name, code):
    assert db_module.is_transient_sqlite_error(_exc(code)) is True, name


@pytest.mark.parametrize("name,code", sorted(_PERMANENT_CODES.items()))
def test_permanent_codes_are_not_transient(name, code):
    assert db_module.is_transient_sqlite_error(_exc(code)) is False, name


def test_extended_busy_locked_share_primary_code_with_base():
    """نتأكّد إن الأكواد الممتدة فعلاً أساسها BUSY/LOCKED (بيتحقّق من منطق القناع)."""
    for code in (_BUSY_RECOVERY, _LOCKED_SHAREDCACHE, _BUSY_SNAPSHOT, _BUSY_TIMEOUT):
        assert (code & 0xFF) in (_BUSY, _LOCKED)
    assert (_IOERR_READ & 0xFF) == _IOERR  # امتداد IOERR لازم يفضل دائم


# ============================================================================
# 2) الاحتياطي النصي (بدون `sqlite_errorcode`)
# ============================================================================
def test_text_fallback_preserved_without_code():
    assert db_module.is_transient_sqlite_error(
        sqlite3.OperationalError("database is locked")
    ) is True
    assert db_module.is_transient_sqlite_error(
        sqlite3.OperationalError("database is busy")
    ) is True
    assert db_module.is_transient_sqlite_error(
        sqlite3.OperationalError("database table is locked")
    ) is True


def test_text_fallback_permanent_without_code():
    assert db_module.is_transient_sqlite_error(
        sqlite3.OperationalError("disk I/O error")
    ) is False
    assert db_module.is_transient_sqlite_error(
        sqlite3.OperationalError("no such table: processed_updates")
    ) is False
    assert db_module.is_transient_sqlite_error(
        sqlite3.OperationalError("database or disk is full")
    ) is False


def test_missing_sqlite_errorcode_attribute_uses_text_fallback():
    """خطأ بلا السمة خالص ⇒ الاحتياطي النصي (مش استثناء)."""
    exc = sqlite3.OperationalError("database is locked")
    assert not hasattr(exc, "sqlite_errorcode")
    assert db_module.is_transient_sqlite_error(exc) is True


def test_none_code_uses_text_fallback():
    """`sqlite_errorcode = None` (سمة موجودة لكن فاضية) ⇒ الاحتياطي النصي."""
    locked = sqlite3.OperationalError("database is locked")
    locked.sqlite_errorcode = None
    assert db_module.is_transient_sqlite_error(locked) is True
    perm = sqlite3.OperationalError("disk I/O error")
    perm.sqlite_errorcode = None
    assert db_module.is_transient_sqlite_error(perm) is False


def test_non_sqlite_error_is_never_transient():
    assert db_module.is_transient_sqlite_error(RuntimeError("x")) is False
    assert db_module.is_transient_sqlite_error(ValueError("x")) is False


def test_non_int_code_is_not_transient_and_never_raises():
    """كود بنوع غير متوقّع ⇒ مش عابر (نفس سلوك الأصل) ومفيش استثناء جديد."""
    exc = sqlite3.OperationalError("weird")
    exc.sqlite_errorcode = "not-an-int"
    assert db_module.is_transient_sqlite_error(exc) is False


# ============================================================================
# 3) المُغلّفات الحقيقية بتعيد المحاولة للأكواد الممتدة
# ============================================================================
class _ScriptedDB(Database):
    """قاعدة حقيقية مع `is_deleted` مُبرمَج (نمط SW03) — آخر عنصر بيتكرّر."""

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


def test_db_wrapper_retries_extended_busy_recovery(sleep_recorder):
    """`is_deleted_with_retry` (طبقة القاعدة) بتعيد المحاولة لـ BUSY_RECOVERY (261)."""
    db = _ScriptedDB([_exc(_BUSY_RECOVERY, "database is locked"), True])
    assert db.is_deleted_with_retry("c1") is True
    assert db.calls == 2
    assert sleep_recorder == [0.25]


def test_db_wrapper_retries_extended_busy_snapshot(sleep_recorder):
    db = _ScriptedDB([_exc(_BUSY_SNAPSHOT, "database is locked"), _exc(_LOCKED_SHAREDCACHE), False])
    assert db.is_deleted_with_retry("c1") is False
    assert db.calls == 3
    assert sleep_recorder == [0.25, 0.5]


def test_db_wrapper_extended_permanent_not_retried(sleep_recorder):
    """امتداد IOERR (266) دائم ⇒ مفيش إعادة."""
    db = _ScriptedDB([_exc(_IOERR_READ, "disk I/O error")])
    with pytest.raises(sqlite3.OperationalError, match="I/O"):
        db.is_deleted_with_retry("c1")
    assert db.calls == 1
    assert sleep_recorder == []


def test_db_wrapper_extended_transient_exhaustion_propagates_original(sleep_recorder):
    """استنفاد الميزانية لكود ممتد ⇒ **الاستثناء الأصلي** يُرفع (مش مغلّف)."""
    original = _exc(_BUSY_TIMEOUT, "database is locked")
    db = _ScriptedDB([original])
    with pytest.raises(sqlite3.OperationalError) as ei:
        db.is_deleted_with_retry("c1")
    assert db.calls == 4  # 1 أصلية + 3 إعادات
    assert sleep_recorder == [0.25, 0.5, 1.0]
    assert ei.value is original


@pytest.fixture
def async_sleep_recorder(monkeypatch):
    delays: list[float] = []

    async def _fake_sleep(d):
        delays.append(d)

    monkeypatch.setattr(h.asyncio, "sleep", _fake_sleep)
    return delays


def test_handler_dedupe_wrapper_retries_extended_busy(async_sleep_recorder):
    """`_check_update_processed_with_retry` بتعيد المحاولة لـ BUSY_SNAPSHOT (517)."""
    calls = {"n": 0}
    original = _exc(_BUSY_SNAPSHOT, "database is locked")

    class _DB:
        def update_is_processed(self, _uid):
            calls["n"] += 1
            if calls["n"] == 1:
                raise original
            return False

    assert asyncio.run(h._check_update_processed_with_retry(_DB(), 1)) is False
    assert calls["n"] == 2
    assert async_sleep_recorder == [0.25]


def test_handler_is_deleted_wrapper_retries_extended_locked(async_sleep_recorder):
    """`_is_deleted_with_retry` بتعيد المحاولة لـ LOCKED_SHAREDCACHE (262)."""
    calls = {"n": 0}

    class _DB:
        def is_deleted(self, _cid):
            calls["n"] += 1
            if calls["n"] == 1:
                raise _exc(_LOCKED_SHAREDCACHE, "database table is locked")
            return True

    assert asyncio.run(h._is_deleted_with_retry(_DB(), "c1")) is True
    assert calls["n"] == 2
    assert async_sleep_recorder == [0.25]


def test_handler_remove_watched_wrapper_retries_extended_busy(async_sleep_recorder):
    """`_remove_watched_with_retry` بتعيد المحاولة لـ BUSY_RECOVERY (261)."""
    calls = {"n": 0}

    def remover(_cid):
        calls["n"] += 1
        if calls["n"] == 1:
            raise _exc(_BUSY_RECOVERY, "database is locked")

    asyncio.run(h._remove_watched_with_retry(remover, "c1"))
    assert calls["n"] == 2
    assert async_sleep_recorder == [0.25]


def test_handler_wrapper_extended_permanent_not_retried(async_sleep_recorder):
    """كود دائم ممتد عبر مُغلّف الـ handler ⇒ مفيش إعادة، الاستثناء يطلع."""
    calls = {"n": 0}

    class _DB:
        def is_deleted(self, _cid):
            calls["n"] += 1
            raise _exc(_FULL, "database or disk is full")

    with pytest.raises(sqlite3.OperationalError, match="full"):
        asyncio.run(h._is_deleted_with_retry(_DB(), "c1"))
    assert calls["n"] == 1
    assert async_sleep_recorder == []


def test_handler_wrapper_extended_transient_exhaustion_propagates(async_sleep_recorder):
    """استنفاد الميزانية عبر مُغلّف الـ handler ⇒ الاستثناء الأصلي يطلع."""
    original = _exc(_BUSY_TIMEOUT, "database is locked")

    class _DB:
        def update_is_processed(self, _uid):
            raise original

    with pytest.raises(sqlite3.OperationalError) as ei:
        asyncio.run(h._check_update_processed_with_retry(_DB(), 1))
    assert ei.value is original
    assert async_sleep_recorder == [0.25, 0.5, 1.0]


# ============================================================================
# 4) ثبات سياسة إعادة المحاولة (مفيش تغيير في المُدد/الحدود)
# ============================================================================
def test_retry_delays_unchanged_exact():
    assert db_module.DEDUPE_RETRY_DELAYS == (0.25, 0.5, 1.0)


def test_shared_policy_unchanged_between_db_and_handlers():
    assert h._DEDUPE_RETRY_DELAYS is db_module.DEDUPE_RETRY_DELAYS
    assert h._is_transient_sqlite_error is db_module.is_transient_sqlite_error


def test_transient_base_code_set_unchanged():
    """الأكواد الأساسية العابرة تفضل {BUSY, LOCKED} بالظبط (مفيش توسيع غير مقصود)."""
    assert set(db_module._TRANSIENT_SQLITE_CODES) == {_BUSY, _LOCKED}


# ============================================================================
# 5) إعادة إنتاج الفشل الحقيقي (SQLITE_BUSY_SNAPSHOT) — قاعدة مؤقتة فقط
# ============================================================================
def test_real_wal_busy_snapshot_classified_transient(tmp_path):
    """إعادة إنتاج حقيقية لـ SQLITE_BUSY_SNAPSHOT (517) على قاعدة WAL مؤقتة.

    لو المنصّة/النسخة ما أنتجتش الكود 517، الاختبار يتخطّى (مفيش اعتماد على سلوك منصّة).
    """
    path = os.path.join(tmp_path, "d1_busy_snapshot.sqlite3")
    a = sqlite3.connect(path)
    a.execute("PRAGMA journal_mode=WAL")
    a.execute("CREATE TABLE t(x)")
    a.commit()
    b = sqlite3.connect(path)
    b.execute("PRAGMA journal_mode=WAL")
    try:
        a.execute("BEGIN")
        a.execute("SELECT * FROM t").fetchall()  # لقطة قراءة على A
        b.execute("INSERT INTO t VALUES (1)")
        b.commit()  # B تقدّم الـ WAL
        with pytest.raises(sqlite3.OperationalError) as ei:
            a.execute("INSERT INTO t VALUES (2)")
            a.commit()
    finally:
        a.close()
        b.close()
    code = getattr(ei.value, "sqlite_errorcode", None)
    if code is None:
        pytest.skip("النسخة لا تُرفق sqlite_errorcode — مش ممكن التحقق الحقيقي")
    assert (code & 0xFF) == _BUSY, f"expected BUSY-family, got code={code}"
    assert db_module.is_transient_sqlite_error(ei.value) is True
