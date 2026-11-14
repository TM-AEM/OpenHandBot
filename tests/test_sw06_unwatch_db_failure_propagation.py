"""OHB2-SW-06: انحدار فشل إلغاء المتابعة (`unwatch_conversation`).

العيب الأصلي (مُثبَت من الكود): المعالج كان بيلتقط `sqlite3.Error` من إزالة المتابعة،
يعرض رسالة خطأ، ثم `return` عاديًّا. يعني فشل قاعدة بيانات حقيقي (كتابة فاشلة/`commit`
فاشل/قاعدة مقفولة استُنفدت محاولاتها) كان **بيُبلَع** ويتحوّل لـ «إتمام معالجة ناجح»:
المتصل/الإطار مايشوفش الفشل، ومفيش فرصة إعادة محاولة حقيقية.

السلوك الصحيح بعد الإصلاح:
- النجاح: الصف يتشال في معاملة ذرّية **متعمّلة** (commit) قبل ما نعلن النجاح.
- الفشل العابر (SQLite BUSY/LOCKED) بيتغطّى بإعادات **محدودة** (`DEDUPE_RETRY_DELAYS`)
  بنفس سياسة `_is_deleted_with_retry`/`_check_update_processed_with_retry`.
- بعد استنفاد الميزانية أو عند فشل دائم: نعرض رسالة متنقّحة + زر محاولة، ثم **نرفع
  الاستثناء الأصلي** (مفيش نجاح كاذب، مفيش ابتلاع).
- `asyncio.CancelledError` ينتشر (مفيش كتم إلغاء).
- فشل تيليجرام **بعد** نجاح الـ commit ما بيعملش إعادة محاولة قاعدة بيانات (الحذف ثابت).

كل الاختبارات معزولة (قاعدة SQLite مؤقتة + تيليجرام fake)، بلا أي شبكة/إنتاج.
"""
from __future__ import annotations

import asyncio
import sqlite3
import threading

import pytest

import bot.handlers as h
from bot import outbox
from bot.db import Database

from tests.test_handlers import DetailClient, _cb_update, _ctx_with

DELAYS = h._DEDUPE_RETRY_DELAYS
_SQLITE_BUSY = getattr(sqlite3, "SQLITE_BUSY", 5)
_SQLITE_LOCKED = getattr(sqlite3, "SQLITE_LOCKED", 6)
SUCCESS = "تمام، اتشال من المتابعة."


# ------------------------------------------------------------------ helpers
def _busy() -> sqlite3.OperationalError:
    exc = sqlite3.OperationalError("database is locked")
    exc.sqlite_errorcode = _SQLITE_BUSY
    return exc


def _locked() -> sqlite3.OperationalError:
    exc = sqlite3.OperationalError("database table is locked")
    exc.sqlite_errorcode = _SQLITE_LOCKED
    return exc


def _permanent_io() -> sqlite3.OperationalError:
    """خطأ I/O دائم (نص مفيش فيه locked/busy) ⇒ مفيش إعادة محاولة."""
    return sqlite3.OperationalError("disk I/O error")


def _permanent_closed() -> sqlite3.ProgrammingError:
    return sqlite3.ProgrammingError("Cannot operate on a closed database.")


def _patch_sleep(monkeypatch) -> list[float]:
    """يعترض `asyncio.sleep` ويسجّل المُدد (بلا انتظار حقيقي)."""
    recorded: list[float] = []

    async def _fake_sleep(delay):
        recorded.append(delay)

    monkeypatch.setattr(h.asyncio, "sleep", _fake_sleep)
    return recorded


def _ctx(tmp_path):
    return _ctx_with(tmp_path, DetailClient(None))


class _CommitFailsConn:
    """بروكسي اتصال: كل حاجة تفوّض للاتصال الحقيقي، لكن `commit` بيفشل (فشل دائم)."""

    def __init__(self, conn):
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def commit(self):
        raise _permanent_io()


# ======================================================= النجاح والثبات
def test_success_commits_durably_and_reports_removal(tmp_path):
    """نجاح: الصف يتشال فعليًا (commit ثابت) والرسالة تتعرض."""
    ctx = _ctx(tmp_path)
    db = ctx.bot_data["db"]
    db.add_watched("c1")
    update = _cb_update(1, "unwatch:c1")
    asyncio.run(h.unwatch_conversation(update, ctx))
    assert update.callback_query.edits == [SUCCESS]
    assert not db.is_watched("c1")
    # إثبات الثبات: اتصال تاني على نفس الملف مايشوفش الصف.
    assert not Database(str(tmp_path / "t.sqlite3")).is_watched("c1")


def test_success_removes_from_watched_list(tmp_path):
    ctx = _ctx(tmp_path)
    db = ctx.bot_data["db"]
    db.add_watched("c1")
    db.add_watched("c2")
    update = _cb_update(1, "unwatch:c1")
    asyncio.run(h.unwatch_conversation(update, ctx))
    assert [w.conversation_id for w in db.list_watched()] == ["c2"]


# ======================================================= إعادة محاولة محدودة
def test_transient_busy_retries_then_succeeds(tmp_path, monkeypatch):
    """BUSY عابر: إعادات محدودة ثم نجاح (الصف يتشال، رسالة نجاح)."""
    ctx = _ctx(tmp_path)
    db = ctx.bot_data["db"]
    db.add_watched("c1")
    delays = _patch_sleep(monkeypatch)
    real = db.remove_watched
    calls = {"n": 0}

    def wrapper(cid):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise _busy()
        return real(cid)

    monkeypatch.setattr(db, "remove_watched", wrapper)
    update = _cb_update(1, "unwatch:c1")
    asyncio.run(h.unwatch_conversation(update, ctx))
    assert update.callback_query.edits == [SUCCESS]
    assert not db.is_watched("c1")
    assert calls["n"] == 3  # محاولة أصلية + إعادتان
    assert delays == list(DELAYS[:2])  # المُدد محدودة وبالظبط


def test_transient_locked_retries_then_succeeds(tmp_path, monkeypatch):
    """LOCKED عابر: نفس ضمانات BUSY."""
    ctx = _ctx(tmp_path)
    db = ctx.bot_data["db"]
    db.add_watched("c1")
    delays = _patch_sleep(monkeypatch)
    real = db.remove_watched
    calls = {"n": 0}

    def wrapper(cid):
        calls["n"] += 1
        if calls["n"] <= 1:
            raise _locked()
        return real(cid)

    monkeypatch.setattr(db, "remove_watched", wrapper)
    update = _cb_update(1, "unwatch:c1")
    asyncio.run(h.unwatch_conversation(update, ctx))
    assert update.callback_query.edits == [SUCCESS]
    assert not db.is_watched("c1")
    assert calls["n"] == 2
    assert delays == list(DELAYS[:1])


def test_transient_busy_exhaustion_propagates_no_false_success(tmp_path, monkeypatch):
    """استنفاد الميزانية: يرفع الاستثناء الأصلي، مفيش نجاح، الصف يفضل."""
    ctx = _ctx(tmp_path)
    db = ctx.bot_data["db"]
    db.add_watched("c1")
    delays = _patch_sleep(monkeypatch)
    calls = {"n": 0}

    def boom(cid):
        calls["n"] += 1
        raise _busy()

    monkeypatch.setattr(db, "remove_watched", boom)
    update = _cb_update(1, "unwatch:c1")
    with pytest.raises(sqlite3.OperationalError) as ei:
        asyncio.run(h.unwatch_conversation(update, ctx))
    assert getattr(ei.value, "sqlite_errorcode", None) == _SQLITE_BUSY  # الأصلي محفوظ
    assert calls["n"] == len(DELAYS) + 1
    assert delays == list(DELAYS)
    assert db.is_watched("c1")  # لسه متابَع (مفيش حذف جزئي)
    assert SUCCESS not in update.callback_query.edits
    assert any("تعذّر" in e for e in update.callback_query.edits)


def test_permanent_failure_not_retried(tmp_path, monkeypatch):
    """خطأ دائم (قاعدة مقفولة نهائيًا): مفيش إعادة محاولة، يرفع فورًا."""
    ctx = _ctx(tmp_path)
    db = ctx.bot_data["db"]
    db.add_watched("c1")
    delays = _patch_sleep(monkeypatch)
    calls = {"n": 0}

    def boom(cid):
        calls["n"] += 1
        raise _permanent_closed()

    monkeypatch.setattr(db, "remove_watched", boom)
    update = _cb_update(1, "unwatch:c1")
    with pytest.raises(sqlite3.ProgrammingError):
        asyncio.run(h.unwatch_conversation(update, ctx))
    assert calls["n"] == 1  # نداء واحد، مفيش إعادة
    assert delays == []
    assert db.is_watched("c1")
    assert SUCCESS not in update.callback_query.edits


def test_permanent_io_error_not_retried(tmp_path, monkeypatch):
    """`OperationalError` دائم بنص I/O (مفيش locked/busy) ⇒ مفيش إعادة محاولة."""
    ctx = _ctx(tmp_path)
    db = ctx.bot_data["db"]
    db.add_watched("c1")
    delays = _patch_sleep(monkeypatch)
    calls = {"n": 0}

    def boom(cid):
        calls["n"] += 1
        raise _permanent_io()

    monkeypatch.setattr(db, "remove_watched", boom)
    update = _cb_update(1, "unwatch:c1")
    with pytest.raises(sqlite3.OperationalError):
        asyncio.run(h.unwatch_conversation(update, ctx))
    assert calls["n"] == 1
    assert delays == []


# ======================================================= فشل الكتابة/الـ commit
def test_write_failure_never_reports_success(tmp_path, monkeypatch):
    """فشل كتابة: مفيش رسالة نجاح أبدًا، والصف يفضل."""
    ctx = _ctx(tmp_path)
    db = ctx.bot_data["db"]
    db.add_watched("c1")
    monkeypatch.setattr(db, "remove_watched", lambda cid: (_ for _ in ()).throw(_permanent_io()))
    update = _cb_update(1, "unwatch:c1")
    with pytest.raises(sqlite3.OperationalError):
        asyncio.run(h.unwatch_conversation(update, ctx))
    assert SUCCESS not in update.callback_query.edits
    assert db.is_watched("c1")


def test_commit_failure_rolls_back_and_propagates(tmp_path):
    """فشل `commit` مايتفسّرش كنجاح: الـ rollback يحفظ الصف، والهاندلر يرفع."""
    ctx = _ctx(tmp_path)
    db = ctx.bot_data["db"]
    db.add_watched("c1")
    real_conn = db._conn
    db._conn = _CommitFailsConn(real_conn)

    # طبقة القاعدة: فشل الـ commit ⇒ rollback ⇒ الصف يفضل (مفيش «متعمّل» كاذب).
    with pytest.raises(sqlite3.OperationalError):
        db.remove_watched("c1")
    assert real_conn.execute(
        "SELECT 1 FROM watched WHERE conversation_id='c1'"
    ).fetchone() is not None

    # الهاندلر: ينتشر كذلك، مفيش رسالة نجاح.
    update = _cb_update(1, "unwatch:c1")
    with pytest.raises(sqlite3.OperationalError):
        asyncio.run(h.unwatch_conversation(update, ctx))
    assert SUCCESS not in update.callback_query.edits
    assert real_conn.execute(
        "SELECT 1 FROM watched WHERE conversation_id='c1'"
    ).fetchone() is not None


# ======================================================= الملكية و F-1
def test_non_owner_ignored(tmp_path):
    """مستخدم غير مسموح ⇒ تجاهل تام (مفيش تعديل، الصف يفضل)."""
    ctx = _ctx(tmp_path)
    db = ctx.bot_data["db"]
    db.add_watched("c1")
    update = _cb_update(999, "unwatch:c1")
    asyncio.run(h.unwatch_conversation(update, ctx))
    assert update.callback_query.edits == []
    assert db.is_watched("c1")


def test_tombstone_intact_after_unwatch(tmp_path):
    """F-1: إلغاء المتابعة ما بيلمسش شاهد الحذف (الشاهد يفضل بعد الإزالة)."""
    ctx = _ctx(tmp_path)
    db = ctx.bot_data["db"]
    db.add_watched("c1")
    db.begin_remote_deletion("c1", outbox.now_iso())
    assert db.is_deleted("c1") is True
    update = _cb_update(1, "unwatch:c1")
    asyncio.run(h.unwatch_conversation(update, ctx))
    assert update.callback_query.edits == [SUCCESS]
    assert db.is_deleted("c1") is True  # الشاهد ما اتغيّرش
    assert not db.is_watched("c1")


# ======================================================= التكرار والتزامن
def test_repeated_unwatch_callbacks_consistent(tmp_path):
    """ضغطتان مكرّرتان: الاتنين يرجعوا بنجاح (التانية no-op)، حالة متسقة."""
    ctx = _ctx(tmp_path)
    db = ctx.bot_data["db"]
    db.add_watched("c1")
    u1 = _cb_update(1, "unwatch:c1")
    asyncio.run(h.unwatch_conversation(u1, ctx))
    u2 = _cb_update(1, "unwatch:c1")
    asyncio.run(h.unwatch_conversation(u2, ctx))  # مايرميش (idempotent)
    assert u1.callback_query.edits == [SUCCESS]
    assert u2.callback_query.edits == [SUCCESS]
    assert not db.is_watched("c1")
    assert db.list_watched() == []


def test_concurrent_unwatch_two_connections_consistent(tmp_path):
    """اتصالان على نفس الملف يعملوا إزالة متزامنة ⇒ مفيش فساد، الحالة نهائية متسقة."""
    path = str(tmp_path / "t.sqlite3")
    db1 = Database(path)
    db1.add_watched("c1")
    db2 = Database(path)
    errors: list[Exception] = []

    def worker(db):
        try:
            db.remove_watched("c1")
        except Exception as exc:  # noqa: BLE001 — نلتقط للتحقق
            errors.append(exc)

    t1 = threading.Thread(target=worker, args=(db1,))
    t2 = threading.Thread(target=worker, args=(db2,))
    t1.start()
    t2.start()
    t1.join(timeout=30)
    t2.join(timeout=30)
    assert errors == []
    assert not db1.is_watched("c1")
    assert db1.list_watched() == []


# ======================================================= الإلغاء
def test_cancelled_error_not_swallowed(tmp_path, monkeypatch):
    """`CancelledError` من الإزالة ينتشر (مفيش كتم)، والصف يفضل."""
    ctx = _ctx(tmp_path)
    db = ctx.bot_data["db"]
    db.add_watched("c1")

    def boom(cid):
        raise asyncio.CancelledError()

    monkeypatch.setattr(db, "remove_watched", boom)
    update = _cb_update(1, "unwatch:c1")
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(h.unwatch_conversation(update, ctx))
    assert db.is_watched("c1")
    assert SUCCESS not in update.callback_query.edits


def test_cancellation_during_retry_sleep_propagates(tmp_path, monkeypatch):
    """إلغاء أثناء انتظار إعادة المحاولة ينتشر (مش يتحوّل لنجاح)."""
    ctx = _ctx(tmp_path)
    db = ctx.bot_data["db"]
    db.add_watched("c1")
    calls = {"n": 0}

    def boom(cid):
        calls["n"] += 1
        raise _busy()

    monkeypatch.setattr(db, "remove_watched", boom)

    async def cancel_sleep(delay):
        raise asyncio.CancelledError()

    monkeypatch.setattr(h.asyncio, "sleep", cancel_sleep)
    update = _cb_update(1, "unwatch:c1")
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(h.unwatch_conversation(update, ctx))
    assert calls["n"] == 1  # اتوقف عند أول إعادة محاولة
    assert db.is_watched("c1")


# ======================================================= فشل تيليجرام بعد الـ commit
def test_telegram_failure_after_commit_no_db_retry(tmp_path, monkeypatch):
    """فشل تعديل تيليجرام **بعد** نجاح الحذف: مفيش إعادة محاولة قاعدة بيانات."""
    ctx = _ctx(tmp_path)
    db = ctx.bot_data["db"]
    db.add_watched("c1")
    real = db.remove_watched
    calls = {"n": 0}

    def counting(cid):
        calls["n"] += 1
        return real(cid)

    monkeypatch.setattr(db, "remove_watched", counting)
    update = _cb_update(1, "unwatch:c1")

    async def boom_edit(text, **kw):
        raise RuntimeError("telegram down")

    update.callback_query.edit_message_text = boom_edit
    with pytest.raises(RuntimeError):
        asyncio.run(h.unwatch_conversation(update, ctx))
    assert calls["n"] == 1  # مفيش إعادة محاولة للحذف
    assert not db.is_watched("c1")  # الحذف ثابت ومتعمّل قبل فشل العرض


def test_telegram_not_modified_after_commit_is_ok(tmp_path, monkeypatch):
    """«not modified» بعد الحذف الناجح: مش خطأ، الصف اتشال (سلوك متوافق)."""
    ctx = _ctx(tmp_path)
    db = ctx.bot_data["db"]
    db.add_watched("c1")
    update = _cb_update(1, "unwatch:c1")

    async def not_modified(text, **kw):
        raise RuntimeError("Bad Request: message is not modified")

    update.callback_query.edit_message_text = not_modified
    asyncio.run(h.unwatch_conversation(update, ctx))  # مايرميش
    assert not db.is_watched("c1")


# ======================================================= وحدة مساعد الإعادة
def test_retry_helper_bounded_attempts(monkeypatch):
    """المساعد: إعادات محدودة بالظبط (1 + len(DELAYS)) ثم يرفع الأصلي."""
    delays = _patch_sleep(monkeypatch)
    calls = {"n": 0}

    def boom(cid):
        calls["n"] += 1
        raise _busy()

    with pytest.raises(sqlite3.OperationalError):
        asyncio.run(h._remove_watched_with_retry(boom, "c1"))
    assert calls["n"] == len(DELAYS) + 1
    assert delays == list(DELAYS)


def test_retry_helper_passes_through_success(monkeypatch):
    delays = _patch_sleep(monkeypatch)
    seen = []

    def ok(cid):
        seen.append(cid)

    asyncio.run(h._remove_watched_with_retry(ok, "c1"))
    assert seen == ["c1"]
    assert delays == []
