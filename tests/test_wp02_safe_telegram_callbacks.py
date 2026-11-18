"""OHB2-WP-02: تقوية كولباك تيليجرام — `_safe_answer` + `_safe_edit_noop`.

يغطّي قرار المالك A/B (docs/decisions/OHB2-OWNER-DECISION-WP-02-CALLBACK-HARDENING.md):

- `_safe_answer(q, text=None, *, show_alert=False)`: التقاط `(TelegramError, asyncio.TimeoutError)`
  **فقط**، تمرير **موضعي** للنص، `show_alert` عند الحاجة، تسجيل نوع الخطأ فقط، وانتشار
  `asyncio.CancelledError`؛ وفشل الرد مايمنعش معالجة الكولباك.
- `_safe_edit_noop`: no-op حميد لفشل التعديل العابر/«not modified» في المواقع الخمسة، بلا
  `FAILED_PERMANENT`/`FAILED_TRANSIENT`، مع صون `EXPLICITLY_IGNORED` و`DURABLE_COMPLETED`
  وعدم إخفاء أخطاء البرمجة/القاعدة، وانتشار `CancelledError`.
- `_safe_edit` القائم **لم يتغيّر** (يعيد رفع ما عدا «not modified»).

كل النداءات مموّهة (مفيش تيليجرام/شبكة حقيقية).
"""
from __future__ import annotations

import asyncio
import inspect
import logging
import sqlite3
from types import SimpleNamespace

import pytest
from telegram.error import BadRequest, TimedOut

import bot.handlers as h
from bot import update_outcomes as uo

from tests.test_handlers import make_context


# ------------------------------------------------------------------ دوبلز
class _Recorder:
    """كولباك قابل للتحكّم: يسجّل نداءات answer/edit ويرمي خطأً مُعدًّا عند الطلب."""

    def __init__(self, *, answer_exc=None, edit_exc=None):
        self.data = "menu"
        self.message = SimpleNamespace(chat_id=99)
        self.answer_calls = []  # list[(args_tuple, kwargs_dict)]
        self.edit_calls = []  # list[(text, kwargs_dict)]
        self._answer_exc = answer_exc
        self._edit_exc = edit_exc

    async def answer(self, *args, **kwargs):
        self.answer_calls.append((args, kwargs))
        if self._answer_exc is not None:
            raise self._answer_exc

    async def edit_message_text(self, text, **kwargs):
        self.edit_calls.append((text, kwargs))
        if self._edit_exc is not None:
            raise self._edit_exc
        return True


def _cb(update_id, q, user_id=1, chat_type="private"):
    return SimpleNamespace(
        update_id=update_id,
        effective_user=SimpleNamespace(id=user_id),
        effective_chat=SimpleNamespace(id=99, type=chat_type),
        message=SimpleNamespace(),
        callback_query=q,
    )


# ================================================================== A: _safe_answer
def test_safe_answer_signature_matches_decision():
    sig = inspect.signature(h._safe_answer)
    params = list(sig.parameters.values())
    assert [p.name for p in params] == ["q", "text", "show_alert"]
    assert params[1].default is None
    assert params[2].kind is inspect.Parameter.KEYWORD_ONLY
    assert params[2].default is False


def test_safe_answer_bare_calls_without_args():
    q = _Recorder()
    asyncio.run(h._safe_answer(q))
    assert q.answer_calls == [((), {})]


def test_safe_answer_text_forwarded_positionally_no_kwargs():
    q = _Recorder()
    asyncio.run(h._safe_answer(q, "نص الرد"))
    assert q.answer_calls == [(("نص الرد",), {})]


def test_safe_answer_show_alert_forwarded_when_required():
    q = _Recorder()
    asyncio.run(h._safe_answer(q, "تنبيه", show_alert=True))
    assert q.answer_calls == [(("تنبيه",), {"show_alert": True})]


def test_safe_answer_bad_request_query_too_old_swallowed():
    q = _Recorder(answer_exc=BadRequest("Query is too old and response timeout expired"))
    asyncio.run(h._safe_answer(q, "x"))  # مايرميش


def test_safe_answer_timed_out_swallowed():
    q = _Recorder(answer_exc=TimedOut("timed out"))
    asyncio.run(h._safe_answer(q))  # مايرميش


def test_safe_answer_asyncio_timeout_error_swallowed():
    q = _Recorder(answer_exc=asyncio.TimeoutError())
    asyncio.run(h._safe_answer(q, "x"))  # مايرميش


def test_safe_answer_logs_type_only_not_payload(caplog):
    secret = "super-secret-token-should-not-be-logged"
    q = _Recorder(answer_exc=BadRequest(f"Query is too old {secret}"))
    with caplog.at_level(logging.WARNING, logger="bot.handlers"):
        asyncio.run(h._safe_answer(q))
    assert "BadRequest" in caplog.text
    assert secret not in caplog.text


def test_safe_answer_cancelled_error_propagates():
    q = _Recorder(answer_exc=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(h._safe_answer(q))


def test_safe_answer_unrelated_error_not_swallowed():
    """except ضيّق: أخطاء البرمجة (مش Telegram/Timeout) بتنتشر، ما بتتخفاش."""
    q = _Recorder(answer_exc=RuntimeError("programming bug"))
    with pytest.raises(RuntimeError):
        asyncio.run(h._safe_answer(q))


def test_safe_answer_failure_does_not_block_callback_processing(tmp_path):
    """فشل الرد على الكولباك مايمنعش تنفيذ المعالج ولا تسجيل نتيجته."""
    ctx = make_context(1, tmp_path)
    q = _Recorder(answer_exc=BadRequest("Query is too old"))
    upd = _cb(5001, q)
    asyncio.run(h.show_menu(upd, ctx))
    assert len(q.edit_calls) == 1  # العرض اتنفّذ رغم فشل الرد
    assert ctx.bot_data["db"].update_outcome(5001) == uo.EXPLICITLY_IGNORED
    assert ctx.bot_data["db"].is_update_acknowledgment_eligible(5001) is True


# ================================================================== B: الترتيب/التفويض
def test_unauthorized_show_menu_no_side_effects(tmp_path):
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(999, "conv-x", "reply")  # حالة محمية موجودة
    q = _Recorder()
    upd = _cb(5100, q, user_id=999)  # مش مصرّح
    asyncio.run(h.show_menu(upd, ctx))
    assert q.edit_calls == []  # مفيش تعديل قبل التفويض
    assert db.get_awaiting(999) == ("conv-x", "reply")  # clear_awaiting مااتنفّذش
    assert db.update_outcome(5100) == uo.EXPLICITLY_IGNORED


def test_unauthorized_notifications_toggle_no_toggle(tmp_path):
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    before = db.get_notifications_enabled()
    q = _Recorder()
    upd = _cb(5101, q, user_id=999)
    asyncio.run(h.notifications_toggle(upd, ctx))
    assert db.get_notifications_enabled() == before  # التبديل مااتنفّذش
    assert db.update_outcome(5101) == uo.EXPLICITLY_IGNORED


def test_authorized_show_menu_edits_after_auth(tmp_path):
    ctx = make_context(1, tmp_path)
    q = _Recorder()
    upd = _cb(5102, q, user_id=1)
    asyncio.run(h.show_menu(upd, ctx))
    assert len(q.edit_calls) == 1
    assert ctx.bot_data["db"].update_outcome(5102) == uo.EXPLICITLY_IGNORED


# ================================================================== C: _safe_edit_noop
def test_safe_edit_noop_not_modified_is_benign_noop():
    q = _Recorder(edit_exc=BadRequest("Message is not modified"))
    assert asyncio.run(h._safe_edit_noop(q, "x")) is False  # مايرميش


def test_safe_edit_noop_deleted_message_bad_request_benign():
    q = _Recorder(edit_exc=BadRequest("message to edit not found"))
    assert asyncio.run(h._safe_edit_noop(q, "x")) is False


def test_safe_edit_noop_timed_out_benign():
    q = _Recorder(edit_exc=TimedOut("timed out"))
    assert asyncio.run(h._safe_edit_noop(q, "x")) is False


def test_safe_edit_noop_asyncio_timeout_benign():
    q = _Recorder(edit_exc=asyncio.TimeoutError())
    assert asyncio.run(h._safe_edit_noop(q, "x")) is False


def test_safe_edit_noop_success_returns_true():
    q = _Recorder()
    assert asyncio.run(h._safe_edit_noop(q, "x")) is True
    assert q.edit_calls and q.edit_calls[0][0] == "x"


def test_safe_edit_noop_logs_type_only(caplog):
    secret = "super-secret-token-should-not-be-logged"
    q = _Recorder(edit_exc=BadRequest(f"message to edit not found {secret}"))
    with caplog.at_level(logging.WARNING, logger="bot.handlers"):
        asyncio.run(h._safe_edit_noop(q, "x"))
    assert "BadRequest" in caplog.text
    assert secret not in caplog.text


def test_safe_edit_noop_cancelled_error_propagates():
    q = _Recorder(edit_exc=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(h._safe_edit_noop(q, "x"))


def test_safe_edit_noop_does_not_swallow_programming_error():
    q = _Recorder(edit_exc=RuntimeError("bug"))
    with pytest.raises(RuntimeError):
        asyncio.run(h._safe_edit_noop(q, "x"))


def test_safe_edit_noop_does_not_swallow_db_error():
    q = _Recorder(edit_exc=sqlite3.OperationalError("database is locked"))
    with pytest.raises(sqlite3.OperationalError):
        asyncio.run(h._safe_edit_noop(q, "x"))


# ================================================================== D: عقد _safe_edit القائم
def test_safe_edit_still_reraises_non_not_modified():
    q = _Recorder(edit_exc=BadRequest("message to edit not found"))
    with pytest.raises(BadRequest):
        asyncio.run(h._safe_edit(q, "x"))


def test_safe_edit_not_modified_returns_false():
    q = _Recorder(edit_exc=BadRequest("Message is not modified"))
    assert asyncio.run(h._safe_edit(q, "x")) is False


def test_safe_edit_success_returns_true():
    q = _Recorder()
    assert asyncio.run(h._safe_edit(q, "x")) is True


# ================================================================== E: المواقع الخمسة
def test_app_open_edit_not_modified_keeps_ignored(tmp_path):
    ctx = make_context(1, tmp_path)
    q = _Recorder(edit_exc=BadRequest("Message is not modified"))
    upd = _cb(6001, q)  # mini_app معطّل افتراضيًا ⇒ فرع «مش متاح»
    asyncio.run(h.app_open(upd, ctx))
    assert ctx.bot_data["db"].update_outcome(6001) == uo.EXPLICITLY_IGNORED
    assert ctx.bot_data["db"].is_update_acknowledgment_eligible(6001) is True


def test_app_open_edit_timed_out_not_permanent(tmp_path):
    ctx = make_context(1, tmp_path)
    q = _Recorder(edit_exc=TimedOut("timed out"))
    upd = _cb(6002, q)
    asyncio.run(h.app_open(upd, ctx))  # مايرميش
    out = ctx.bot_data["db"].update_outcome(6002)
    assert out == uo.EXPLICITLY_IGNORED
    assert out != uo.FAILED_PERMANENT and out != uo.FAILED_TRANSIENT


def test_app_open_available_branch_edit_failure(tmp_path):
    ctx = make_context(1, tmp_path)
    ctx.bot_data["config"].mini_app_enabled = True
    ctx.bot_data["config"].mini_app_url = "https://app.example.com/mini"
    q = _Recorder(edit_exc=BadRequest("message to edit not found"))
    upd = _cb(6003, q)
    asyncio.run(h.app_open(upd, ctx))
    assert ctx.bot_data["db"].update_outcome(6003) == uo.EXPLICITLY_IGNORED


def test_show_menu_edit_failure_keeps_ignored(tmp_path):
    ctx = make_context(1, tmp_path)
    q = _Recorder(edit_exc=BadRequest("message to edit not found"))
    upd = _cb(6004, q)
    asyncio.run(h.show_menu(upd, ctx))
    assert ctx.bot_data["db"].update_outcome(6004) == uo.EXPLICITLY_IGNORED


def test_notifications_menu_edit_timed_out_not_permanent(tmp_path):
    ctx = make_context(1, tmp_path)
    q = _Recorder(edit_exc=TimedOut("timed out"))
    upd = _cb(6005, q)
    asyncio.run(h.notifications_menu(upd, ctx))
    out = ctx.bot_data["db"].update_outcome(6005)
    assert out == uo.EXPLICITLY_IGNORED
    assert out != uo.FAILED_PERMANENT and out != uo.FAILED_TRANSIENT


def test_notifications_toggle_edit_failure_keeps_durable_completed(tmp_path):
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    q = _Recorder(edit_exc=BadRequest("message to edit not found"))
    upd = _cb(6006, q)
    asyncio.run(h.notifications_toggle(upd, ctx))  # مايرميش
    assert db.update_outcome(6006) == uo.DURABLE_COMPLETED  # الـ commit محفوظ
    assert db.is_update_acknowledgment_eligible(6006) is True
    assert db.update_failure(6006) is None  # مفيش تلويث لـ update_failures
    assert db.acknowledgment_boundary([6006]) == 6006  # الحدّ مااتحجبش
    assert db.get_notifications_enabled() is False  # التبديل اتعمّل فعلًا


def test_notifications_toggle_not_modified_keeps_durable_completed(tmp_path):
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    q = _Recorder(edit_exc=BadRequest("Message is not modified"))
    upd = _cb(6007, q)
    asyncio.run(h.notifications_toggle(upd, ctx))
    assert db.update_outcome(6007) == uo.DURABLE_COMPLETED
    assert db.update_failure(6007) is None


def test_notifications_toggle_answer_and_edit_failures_keep_durable(tmp_path):
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    q = _Recorder(answer_exc=TimedOut("timed out"), edit_exc=TimedOut("timed out"))
    upd = _cb(6008, q)
    asyncio.run(h.notifications_toggle(upd, ctx))
    assert db.update_outcome(6008) == uo.DURABLE_COMPLETED
    assert db.acknowledgment_boundary([6008]) == 6008


def test_notifications_toggle_duplicate_no_second_toggle(tmp_path):
    """تحديث مكرّر (نفس update_id) ما بيعملش تبديل تاني، والنتيجة تفضل متينة."""
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    q1 = _Recorder()
    asyncio.run(h.notifications_toggle(_cb(6009, q1), ctx))
    first = db.get_notifications_enabled()
    q2 = _Recorder()
    asyncio.run(h.notifications_toggle(_cb(6009, q2), ctx))
    assert db.get_notifications_enabled() == first  # مفيش تبديل تاني
    assert db.update_outcome(6009) == uo.DURABLE_COMPLETED


def test_cancelled_error_propagates_through_real_handler(tmp_path):
    """الإلغاء ينتشر عبر معالج حقيقي (مايتحوّلش لنجاح/تجاهل)."""
    ctx = make_context(1, tmp_path)
    q = _Recorder(answer_exc=asyncio.CancelledError())
    upd = _cb(6010, q)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(h.show_menu(upd, ctx))
    assert ctx.bot_data["db"].update_outcome(6010) is None  # مفيش نتيجة كاذبة
