"""SW-01 regression: فشل قراءة شاهد الحذف في `_send_prompt` ما يتحوّلش لـ «متشاهد».

العيب الأصلي: `_send_prompt` كان بيلتقط **أي** استثناء من `db.is_deleted`، يحوّله لـ
`deleted=True`، يبعت رسالة «الشات اتحذف» (كاذبة)، ويرجع عاديًّا — فالفشل يتخفي، والتحديث
يتعامل كإنه اتعالج من غير ما البرومت يتحفظ بثبات.

السلوك الصحيح:
- `is_deleted` نجحت وTrue ⇒ رفض الحذف المشروع (F-1) زي ما هو.
- `is_deleted` نجحت وFalse ⇒ مسار الحفظ العادي.
- `is_deleted` فشلت ⇒ الاستثناء **بيطلع** (فشل عابر يُعاد محدودًا، دائم يُرفع فورًا)، مفيش
  رسالة حذف كاذبة، مفيش رجوع عادي، مفيش استهلاك لحالة الانتظار.

كل الاختبارات معزولة (قاعدة SQLite مؤقتة + fakes)، بدون أي شبكة/تيليجرام إنتاجي.
"""
from __future__ import annotations

import asyncio
import sqlite3
from types import SimpleNamespace

import pytest

import bot.handlers as h
from bot import outbox
from tests.test_f1_tombstone_enforcement import CID, CountingClient, _ctx_with
from tests.test_handlers import FakeMessage

DELAYS = h._DEDUPE_RETRY_DELAYS
# أكواد SQLite الرقمية (ثابتة في كل الإصدارات) بدل الاعتماد على ثوابت الوحدة.
_SQLITE_BUSY = getattr(sqlite3, "SQLITE_BUSY", 5)
_SQLITE_LOCKED = getattr(sqlite3, "SQLITE_LOCKED", 6)


# ------------------------------------------------------------------ helpers
def _text_update(user_id: int, text: str, update_id: int | None = None):
    msg = FakeMessage()
    msg.text = text
    up = SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_chat=SimpleNamespace(id=99, type="private"),
        message=msg,
    )
    if update_id is not None:
        up.update_id = update_id
    return up


def _busy() -> sqlite3.OperationalError:
    exc = sqlite3.OperationalError("database is locked")
    exc.sqlite_errorcode = _SQLITE_BUSY
    return exc


def _locked() -> sqlite3.OperationalError:
    exc = sqlite3.OperationalError("database table is locked")
    exc.sqlite_errorcode = _SQLITE_LOCKED
    return exc


def _permanent() -> sqlite3.ProgrammingError:
    return sqlite3.ProgrammingError("Cannot operate on a closed database.")


def _patch_sleep(monkeypatch) -> list[float]:
    """يعترض `asyncio.sleep` في وحدات handlers ويسجّل المُدد (بدون انتظار حقيقي)."""
    recorded: list[float] = []

    async def _fake_sleep(delay):
        recorded.append(delay)

    monkeypatch.setattr(h.asyncio, "sleep", _fake_sleep)
    return recorded


class _FakeDB:
    """قاعدة وهمية: `is_deleted` بيفشل `fail_times` مرة ثم يرجّع `result`."""

    def __init__(self, exc: Exception, fail_times: int, result: bool = False) -> None:
        self.exc = exc
        self.fail_times = fail_times
        self.result = result
        self.calls = 0

    def is_deleted(self, conversation_id: str) -> bool:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise self.exc
        return self.result


# ============================================================ retry unit behavior
def test_transient_busy_retries_then_succeeds(monkeypatch):
    """BUSY عابر: يُعاد محدودًا ثم ينجح ⇒ النتيجة من القراءة الناجحة، مفيش رفع."""
    delays = _patch_sleep(monkeypatch)
    db = _FakeDB(_busy(), fail_times=2, result=False)
    out = asyncio.run(h._is_deleted_with_retry(db, CID))
    assert out is False
    assert db.calls == 3  # محاولة أصلية + إعادتان
    assert delays == list(DELAYS[:2])  # المُدد المستخدمة بالظبط (محدودة)


def test_transient_busy_exhaustion_propagates(monkeypatch):
    """BUSY عابر بعد استنفاد الميزانية ⇒ يرفع الاستثناء الأصلي (مفيش تحويل لنتيجة)."""
    delays = _patch_sleep(monkeypatch)
    db = _FakeDB(_busy(), fail_times=10**9)
    with pytest.raises(sqlite3.OperationalError) as ei:
        asyncio.run(h._is_deleted_with_retry(db, CID))
    assert getattr(ei.value, "sqlite_errorcode", None) == _SQLITE_BUSY
    assert db.calls == len(DELAYS) + 1  # محاولة أصلية + عدد الإعادات المسموح بالظبط
    assert delays == list(DELAYS)  # الميزانية كاملة وبس، مفيش زيادة


def test_transient_locked_exhaustion_propagates(monkeypatch):
    """LOCKED: نفس ضمانات BUSY (يُعاد محدودًا ثم يرفع)."""
    delays = _patch_sleep(monkeypatch)
    db = _FakeDB(_locked(), fail_times=10**9)
    with pytest.raises(sqlite3.OperationalError) as ei:
        asyncio.run(h._is_deleted_with_retry(db, CID))
    assert getattr(ei.value, "sqlite_errorcode", None) == _SQLITE_LOCKED
    assert db.calls == len(DELAYS) + 1
    assert delays == list(DELAYS)


def test_permanent_error_is_not_retried(monkeypatch):
    """خطأ دائم ⇒ مفيش إعادة محاولة (نداء واحد) والاستثناء الأصلي بيطلع."""
    delays = _patch_sleep(monkeypatch)
    db = _FakeDB(_permanent(), fail_times=10**9)
    with pytest.raises(sqlite3.ProgrammingError):
        asyncio.run(h._is_deleted_with_retry(db, CID))
    assert db.calls == 1
    assert delays == []  # مفيش إعادة محاولة لأخطاء دائمة


# ============================================================ handler-level behavior
def test_handler_busy_retries_bounded_then_propagates(tmp_path, monkeypatch):
    """BUSY على مستوى `handle_text`: يُعاد محدودًا، يرفع، مفيش رسالة كاذبة، مفيش فقد."""
    client = CountingClient()
    ctx = _ctx_with(tmp_path, client)
    db = ctx.bot_data["db"]
    db.set_awaiting(1, CID, "reply")
    delays = _patch_sleep(monkeypatch)

    calls = {"n": 0}

    def boom(*_a, **_k):
        calls["n"] += 1
        raise _busy()

    monkeypatch.setattr(db, "is_deleted", boom)
    update = _text_update(1, "برومت")
    with pytest.raises(sqlite3.OperationalError):
        asyncio.run(h.handle_text(update, ctx))
    assert calls["n"] == len(DELAYS) + 1  # إعادات محدودة
    assert delays == list(DELAYS)
    assert db.count_outbox() == 0  # مفيش برومت اتسجّل
    assert client.calls == []  # مفيش نداء بعيد
    assert not any("اتحذف" in r for r in update.message.replies)  # مفيش رسالة حذف كاذبة
    assert db.get_awaiting(1) == (CID, "reply")  # التوجيه ما اتستهلكش


def test_handler_locked_retries_bounded_then_propagates(tmp_path, monkeypatch):
    """LOCKED على مستوى `handle_text`: نفس ضمانات BUSY."""
    client = CountingClient()
    ctx = _ctx_with(tmp_path, client)
    db = ctx.bot_data["db"]
    db.set_awaiting(1, CID, "reply")
    delays = _patch_sleep(monkeypatch)

    calls = {"n": 0}

    def boom(*_a, **_k):
        calls["n"] += 1
        raise _locked()

    monkeypatch.setattr(db, "is_deleted", boom)
    update = _text_update(1, "برومت")
    with pytest.raises(sqlite3.OperationalError):
        asyncio.run(h.handle_text(update, ctx))
    assert calls["n"] == len(DELAYS) + 1
    assert delays == list(DELAYS)
    assert db.count_outbox() == 0
    assert not any("اتحذف" in r for r in update.message.replies)
    assert db.get_awaiting(1) == (CID, "reply")


def test_handler_permanent_failure_propagates_no_retry(tmp_path, monkeypatch):
    """خطأ دائم على مستوى `handle_text`: يرفع فورًا (بدون إعادة)، مفيش رسالة كاذبة."""
    client = CountingClient()
    ctx = _ctx_with(tmp_path, client)
    db = ctx.bot_data["db"]
    db.set_awaiting(1, CID, "reply")
    delays = _patch_sleep(monkeypatch)

    calls = {"n": 0}

    def boom(*_a, **_k):
        calls["n"] += 1
        raise _permanent()

    monkeypatch.setattr(db, "is_deleted", boom)
    update = _text_update(1, "برومت")
    with pytest.raises(sqlite3.ProgrammingError):
        asyncio.run(h.handle_text(update, ctx))
    assert calls["n"] == 1  # مفيش إعادة محاولة لخطأ دائم
    assert delays == []
    assert db.count_outbox() == 0
    assert not any("اتحذف" in r for r in update.message.replies)
    assert db.get_awaiting(1) == (CID, "reply")


def test_genuine_tombstone_still_rejected(tmp_path):
    """شات متشاهد فعلًا (قراءة ناجحة = True) ⇒ رفض الحذف المشروع (F-1 محفوظ)."""
    client = CountingClient()
    ctx = _ctx_with(tmp_path, client)
    db = ctx.bot_data["db"]
    db.set_awaiting(1, CID, "reply")
    db.begin_remote_deletion(CID, outbox.now_iso())
    assert db.is_deleted(CID) is True  # شاهد 'deleting' (قراءة ناجحة)

    update = _text_update(1, "برومت متأخّر")
    asyncio.run(h.handle_text(update, ctx))
    assert db.count_outbox() == 0  # مفيش برومت
    assert db.is_deleted(CID) is True  # الشاهد ما اتشالش (مفيش إحياء)
    assert client.calls == []  # مفيش نداء بعيد
    assert any("اتحذف" in r for r in update.message.replies)  # رسالة الحذف المشروعة
    assert db.get_awaiting(1) == (CID, "reply")  # التوجيه لسه قائم


def test_non_deleted_conversation_persists_prompt(tmp_path):
    """قراءة ناجحة = False ⇒ مسار الحفظ العادي يكمّل (صف صندوق + تأكيد)."""
    client = CountingClient()
    ctx = _ctx_with(tmp_path, client)
    db = ctx.bot_data["db"]
    db.set_awaiting(1, CID, "reply")

    update = _text_update(1, "برومت عادي")
    asyncio.run(h.handle_text(update, ctx))
    assert db.count_outbox() == 1  # البرومت اتحفظ بثبات
    assert any("وصل" in r for r in update.message.replies)  # تأكيد الحفظ
    assert db.get_awaiting(1) == (None, None)  # حالة الانتظار اتستهلكت (reply)


def test_outbox_write_failure_rolls_back_and_keeps_awaiting(tmp_path, monkeypatch):
    """فشل كتابة الصندوق ⇒ rollback كامل، مفيش استهلاك للحالة، الاستثناء بيطلع."""
    client = CountingClient()
    ctx = _ctx_with(tmp_path, client)
    db = ctx.bot_data["db"]
    db.set_awaiting(1, CID, "reply")

    def boom(*_a, **_k):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(db, "add_or_group_outbox", boom)
    update = _text_update(1, "برومت")
    with pytest.raises(sqlite3.OperationalError):
        asyncio.run(h.handle_text(update, ctx))
    assert db.count_outbox() == 0  # مفيش برومت
    assert db.get_awaiting(1) == (CID, "reply")  # الحالة ما اتستهلكتش


def test_commit_failure_rolls_back_and_keeps_awaiting(tmp_path, monkeypatch):
    """فشل الـ commit داخل معاملة الصندوق ⇒ rollback، مفيش برومت، الحالة تفضل قائمة."""
    client = CountingClient()
    ctx = _ctx_with(tmp_path, client)
    db = ctx.bot_data["db"]
    db.set_awaiting(1, CID, "reply")

    class _CommitFailsConn:
        """يفوّض كل شيء للاتصال الحقيقي، لكن أول `commit` بيفشل."""

        def __init__(self, real):
            self._real = real
            self._fail_once = True

        def execute(self, *a, **k):
            return self._real.execute(*a, **k)

        def commit(self):
            if self._fail_once:
                self._fail_once = False
                raise sqlite3.OperationalError("disk I/O error during commit")
            return self._real.commit()

        def rollback(self):
            return self._real.rollback()

        def __getattr__(self, name):
            return getattr(self._real, name)

    db._conn = _CommitFailsConn(db._conn)
    update = _text_update(1, "برومت")
    with pytest.raises(sqlite3.OperationalError):
        asyncio.run(h.handle_text(update, ctx))
    assert db.count_outbox() == 0  # مفيش برومت (rollback)
    assert db.get_awaiting(1) == (CID, "reply")  # الحالة ما اتستهلكتش


def test_confirmation_failure_after_commit_keeps_prompt_durable(tmp_path, monkeypatch):
    """commit نجح وفشل التأكيد تيليجرام ⇒ البرومت يفضل محفوظ، مفيش برومت تاني للتحديث ده."""
    client = CountingClient()
    ctx = _ctx_with(tmp_path, client)
    db = ctx.bot_data["db"]
    db.set_awaiting(1, CID, "route", title="A")

    update = _text_update(1, "برومت", update_id=7777)
    real_reply = update.message.reply_text
    state = {"fail_ack": True}

    async def flaky_reply(text, **kw):
        if state["fail_ack"] and "وصل" in text:
            state["fail_ack"] = False
            raise RuntimeError("telegram send failed")
        await real_reply(text, **kw)

    update.message.reply_text = flaky_reply
    with pytest.raises(RuntimeError):
        asyncio.run(h.handle_text(update, ctx))
    assert db.count_outbox() == 1  # البرومت اتحفظ بثبات رغم فشل التأكيد
    assert db.get_awaiting(1) == (CID, "route")  # route مستمر (بيتجدد، مش بيتستهلك)

    # إعادة تسليم **نفس** التحديث: علامة «معالَج» بتمنع برومت تاني (idempotency).
    update2 = _text_update(1, "برومت", update_id=7777)
    asyncio.run(h.handle_text(update2, ctx))
    assert db.count_outbox() == 1  # مفيش برومت مكرّر
    assert not any("وصل" in r for r in update2.message.replies)  # مفيش تأكيد كاذب


def test_duplicate_update_creates_single_prompt(tmp_path):
    """نفس `update_id` مرتين ⇒ برومت واحد بس (idempotency قائمة، ما اتكسرتش)."""
    client = CountingClient()
    ctx = _ctx_with(tmp_path, client)
    db = ctx.bot_data["db"]
    db.set_awaiting(1, CID, "route", title="A")

    asyncio.run(h.handle_text(_text_update(1, "برومت", update_id=8888), ctx))
    asyncio.run(h.handle_text(_text_update(1, "برومت", update_id=8888), ctx))
    assert db.count_outbox() == 1  # برومت واحد بالظبط
