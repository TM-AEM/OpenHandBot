"""OHB2-WP-07 (NEW-DEF-03) — اختبارات انحدار على **ذرّية مسح حالة الانتظار مع كتابة نتيجة
التحديث** في معالجَي التنقّل:

- NAV-02 `handlers.show_menu`
- NAV-05 `handlers.start_new_chat`

العيب: كلاهما كان بيعمل `clear_awaiting` (commit مستقل) ثم `mark_explicitly_ignored`
(commit تانٍ). عطل بينهم كان يسيب حالة ممسوحة **بلا** نتيجة دائمة.

الإصلاح: `Database.clear_awaiting_and_record_outcome` — `BEGIN IMMEDIATE` واحدة.

**الترتيب مقصود ومختلف بين المعالجين:**

- `show_menu`: المسح+النتيجة **بعد** العرض (العرض `_safe_edit_noop` ما بيرفعش، فالترتيب
  ما بيفرقش سلوكيًا لكن بيضمن إن أي استثناء غير متوقّع ما يسبش مسحًا بلا نتيجة).
- `start_new_chat`: المسح+النتيجة **بعد** `_show_repos` عمدًا — هي بترفع
  `OperationalApiFailure` على فشل تشغيلي. لو حصل المسح قبلها كان الفشل يتحوّل لنجاح
  مؤهّل للإقرار (fail-open) — وده اللي `test_operational_failure_does_not_record_ack_eligible`
  بيحرسه.
"""
from __future__ import annotations

import asyncio

import pytest

import bot.handlers as h
from bot import update_outcomes as uo
from bot.db import Database
from bot.errors import ApiError
from telegram.error import BadRequest

from tests.test_4b import Q, cb_update
from tests.test_handlers import make_context

OWNER_ID = 1


def _cb_with_id(data, update_id, user_id=OWNER_ID):
    update = cb_update(Q(data), user_id=user_id)
    update.update_id = update_id
    return update


class _ReposClient:
    """عميل بيرجّع مستودعات أو يرفع خطأ تشغيلي حسب الإعداد."""

    OWNER_UUID = "owner-uuid-123"

    def __init__(self, repos=None, raise_exc=None):
        self._repos = repos if repos is not None else []
        self._raise = raise_exc

    async def get_current_user(self):
        return {"id": self.OWNER_UUID}

    async def search_repositories(self, query="", page_id=None, limit=100):
        if self._raise is not None:
            raise self._raise
        return self._repos


# ============================================================================
# NAV-02 — show_menu
# ============================================================================
def test_show_menu_clears_state_and_records_outcome_atomically(tmp_path):
    """مسح الحالة + `explicitly_ignored` معًا، والنتيجة مؤهّلة للإقرار."""
    ctx = make_context(OWNER_ID, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    asyncio.run(h.show_menu(_cb_with_id("menu", 7101), ctx))

    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.update_outcome(7101) == uo.EXPLICITLY_IGNORED
    assert uo.is_ack_eligible(db.update_outcome(7101)) is True
    db.close()


def test_show_menu_rollback_leaves_state_and_outcome_untouched(tmp_path, monkeypatch):
    """فشل كتابة النتيجة ⇒ **مفيش** مسح للحالة (الاتنين يتراجعوا)."""
    ctx = make_context(OWNER_ID, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    def _boom(*_a, **_k):
        raise RuntimeError("outcome write failed")

    monkeypatch.setattr(db, "mark_update_outcome", _boom)
    with pytest.raises(RuntimeError):
        asyncio.run(h.show_menu(_cb_with_id("menu", 7102), ctx))

    assert db.get_awaiting(OWNER_ID) == ("conv-A", "route"), "مسح حالة بلا نتيجة!"
    assert db.update_outcome(7102) is None
    db.close()


def test_show_menu_update_id_none_clears_without_outcome(tmp_path):
    """`update_id=None` ⇒ المسح بس، ومفيش صف نتيجة (سلوك قديم)."""
    ctx = make_context(OWNER_ID, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    asyncio.run(h.show_menu(cb_update(Q("menu")), ctx))

    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.count_processed_updates() == 0
    db.close()


def test_show_menu_display_failure_still_records_ignored(tmp_path):
    """فشل تعديل الرسالة (حميد/عابر) ⇒ النتيجة تفضل `explicitly_ignored` (سلوك WP-02 محفوظ)."""
    ctx = make_context(OWNER_ID, tmp_path)
    db = ctx.bot_data["db"]

    q = Q("menu")

    async def _fail(*_a, **_k):
        raise BadRequest("message to edit not found")

    q.edit_message_text = _fail
    update = cb_update(q)
    update.update_id = 7103

    asyncio.run(h.show_menu(update, ctx))

    assert db.update_outcome(7103) == uo.EXPLICITLY_IGNORED
    db.close()


def test_show_menu_unexpected_exception_leaves_state_untouched(tmp_path):
    """استثناء غير متوقّع في العرض ⇒ **مفيش** مسح ولا نتيجة (fail-closed).

    ده مكسب ترتيب الإصلاح: المسح+النتيجة بقوا بعد العرض، فأي رفع غير متوقّع ما بيسيبش
    حالة ممسوحة بلا نتيجة (المسار القديم كان بيمسح **قبل** العرض).
    """
    ctx = make_context(OWNER_ID, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    q = Q("menu")

    async def _boom(*_a, **_k):
        raise RuntimeError("unexpected bug")

    q.edit_message_text = _boom
    update = cb_update(q)
    update.update_id = 7105

    with pytest.raises(RuntimeError):
        asyncio.run(h.show_menu(update, ctx))

    assert db.get_awaiting(OWNER_ID) == ("conv-A", "route")
    assert db.update_outcome(7105) is None
    db.close()


def test_show_menu_unauthorized_touches_nothing(tmp_path):
    """غير مصرّح ⇒ مفيش مسح ولا تعديل، والنتيجة `explicitly_ignored` من مسار التفويض."""
    ctx = make_context(OWNER_ID, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(999, "conv-x", "reply")

    asyncio.run(h.show_menu(_cb_with_id("menu", 7104, user_id=999), ctx))

    assert db.get_awaiting(999) == ("conv-x", "reply")
    assert db.update_outcome(7104) == uo.EXPLICITLY_IGNORED
    db.close()


# ============================================================================
# NAV-05 — start_new_chat
# ============================================================================
def test_start_new_chat_clears_state_and_records_outcome_atomically(tmp_path):
    """مسح الحالة + `explicitly_ignored` معًا بعد عرض القايمة."""
    ctx = make_context(OWNER_ID, tmp_path, client=_ReposClient(repos=[{"full_name": "o/r"}]))
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    asyncio.run(h.start_new_chat(_cb_with_id("newchat", 7201), ctx))

    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.update_outcome(7201) == uo.EXPLICITLY_IGNORED
    assert uo.is_ack_eligible(db.update_outcome(7201)) is True
    db.close()


def test_start_new_chat_rollback_leaves_state_and_outcome_untouched(tmp_path, monkeypatch):
    """فشل كتابة النتيجة ⇒ **مفيش** مسح للحالة."""
    ctx = make_context(OWNER_ID, tmp_path, client=_ReposClient(repos=[{"full_name": "o/r"}]))
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    def _boom(*_a, **_k):
        raise RuntimeError("outcome write failed")

    monkeypatch.setattr(db, "mark_update_outcome", _boom)
    with pytest.raises(RuntimeError):
        asyncio.run(h.start_new_chat(_cb_with_id("newchat", 7202), ctx))

    assert db.get_awaiting(OWNER_ID) == ("conv-A", "route"), "مسح حالة بلا نتيجة!"
    assert db.update_outcome(7202) is None
    db.close()


def test_start_new_chat_update_id_none_clears_without_outcome(tmp_path):
    """`update_id=None` ⇒ المسح بس، ومفيش صف نتيجة."""
    ctx = make_context(OWNER_ID, tmp_path, client=_ReposClient(repos=[{"full_name": "o/r"}]))
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    asyncio.run(h.start_new_chat(cb_update(Q("newchat")), ctx))

    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.count_processed_updates() == 0
    db.close()


def test_operational_failure_does_not_record_ack_eligible(tmp_path):
    """الحاسم: فشل تشغيلي (5xx) في `_show_repos` ⇒ **مفيش** مسح ولا نتيجة مؤهّلة.

    لو المسح+النتيجة حصلوا قبل `_show_repos`، كان التحديث يتسجّل `explicitly_ignored`
    (مؤهّل) ثم يرفع ⇒ فشل يتحوّل لنجاح ويُحجب الحدّ. الاختبار ده بيحرس الترتيب.
    """
    ctx = make_context(
        OWNER_ID, tmp_path, client=_ReposClient(raise_exc=ApiError("upstream down", 503))
    )
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    with pytest.raises(h.OperationalApiFailure):
        asyncio.run(h.start_new_chat(_cb_with_id("newchat", 7203), ctx))

    assert db.get_awaiting(OWNER_ID) == ("conv-A", "route"), "الحالة اتلمست قبل الفشل!"
    assert db.update_outcome(7203) is None, "فشل تشغيلي اتسجّل كنتيجة مؤهّلة!"
    db.close()


def test_start_new_chat_unauthorized_touches_nothing(tmp_path):
    """غير مصرّح ⇒ مفيش مسح، والنتيجة من مسار التفويض."""
    ctx = make_context(OWNER_ID, tmp_path, client=_ReposClient(repos=[{"full_name": "o/r"}]))
    db = ctx.bot_data["db"]
    db.set_awaiting(999, "conv-x", "reply")

    asyncio.run(h.start_new_chat(_cb_with_id("newchat", 7204, user_id=999), ctx))

    assert db.get_awaiting(999) == ("conv-x", "reply")
    assert db.update_outcome(7204) == uo.EXPLICITLY_IGNORED
    db.close()


# ============================================================================
# إعادة التسليم — المعالجان معًا
# ============================================================================
@pytest.mark.parametrize(
    "handler,callback,uid",
    [
        (h.show_menu, "menu", 7301),
        (h.start_new_chat, "newchat", 7302),
    ],
    ids=["nav02_show_menu", "nav05_start_new_chat"],
)
def test_repeated_delivery_keeps_outcome_stable(tmp_path, handler, callback, uid):
    """إعادة تسليم نفس `update_id` ⇒ النتيجة ثابتة، والحالة ممسوحة."""
    ctx = make_context(OWNER_ID, tmp_path, client=_ReposClient(repos=[{"full_name": "o/r"}]))
    db = ctx.bot_data["db"]

    asyncio.run(handler(_cb_with_id(callback, uid), ctx))
    asyncio.run(handler(_cb_with_id(callback, uid), ctx))

    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.update_outcome(uid) == uo.EXPLICITLY_IGNORED
    db.close()


# ============================================================================
# الوحدة: المساعد الذرّي على مسار المسح
# ============================================================================
def test_helper_rolls_back_clear_when_outcome_write_fails(tmp_path, monkeypatch):
    """`clear_awaiting_and_record_outcome`: فشل النتيجة ⇒ الحالة **مااتمسحتش**."""
    db = Database(str(tmp_path / "unit.sqlite3"))
    db.set_awaiting(OWNER_ID, "conv-A", "route", title="t")

    def _boom(*_a, **_k):
        raise RuntimeError("outcome write failed")

    monkeypatch.setattr(db, "mark_update_outcome", _boom)
    with pytest.raises(RuntimeError):
        db.clear_awaiting_and_record_outcome(
            OWNER_ID, 7401, "2026-01-01T00:00:00+00:00", uo.EXPLICITLY_IGNORED
        )

    assert db.get_awaiting(OWNER_ID) == ("conv-A", "route")
    assert db.update_outcome(7401) is None
    db.close()
