"""OHB2-PLAN-15-OPERATIONAL-FAILURE-VISIBILITY — اختبارات انحدار لمساري `show_status`/`show_cost`.

تغطّي العيوب المؤكّدة المصلَحة في Plan 05 وثوابت الفشل المغلق القائمة:
1. `OPS01-D1`: فشل `q.answer()` (استعلام منتهي الصلاحية `BadRequest` عند إعادة التسليم أو `TimedOut`)
   لا يوقف معالجة `show_status`/`show_cost` ولا يحوّل التعافي لـ `FAILED_PERMANENT`؛ يُسجَّل نوع الخطأ
   فقط (بدون نصه/أسرار)، بينما `asyncio.CancelledError` لا يُبتلَع.
2. `OPS01-D2`: الحمولات المشوّهة من OpenHands (`metrics` أو `accumulated_token_usage` ليست `dict`
   في `show_cost`، أو `execution_status` غير قابل للتجزئة في `show_status`) لا تسبّب انهيارًا
   صامتًا بعد `q.answer()` ولا حجبًا دائمًا (`FAILED_PERMANENT`).
3. الحفاظ على عقود `Stage 4 F1` و`SW-05` القائمة (5xx/429/timeout ⇒ `FAILED_TRANSIENT`،
   فشل التعديل بعد نجاح التفويض ⇒ `FAILED_TRANSIENT`، ورفض 404/403 ⇒ `EXPLICITLY_IGNORED`).
"""
from __future__ import annotations

import asyncio
import logging

import pytest
from telegram.error import BadRequest, TimedOut

import bot.handlers as h
from bot import update_outcomes as uo
from bot.errors import ApiError
from bot.messages import format_cost, state_label
from bot.polling import TelegramPoller
from tests.test_duplicate_update_dispatch import OWNER_ID
from tests.test_handlers import DetailClient, FakeQuery, _cb_update, _ctx_with
from tests.test_stage2_custom_polling import _callback, _with_started_app


class _AnswerFailQuery(FakeQuery):
    def __init__(self, data: str, exc: BaseException):
        super().__init__()
        self.data = data
        self._exc = exc
        self.answer_calls = 0

    async def answer(self):
        self.answer_calls += 1
        raise self._exc


def _cb_with_answer_error(data: str, exc: BaseException, update_id: int = 7001):
    update = _cb_update(OWNER_ID, data)
    update.update_id = update_id
    update.callback_query = _AnswerFailQuery(data, exc)
    return update


# --------------------------------------------------------------------------- #
# 1) OPS01-D1: فشل q.answer() لا يمنع العرض/التعافي ولا يسجّل أسرارًا
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "exc_factory",
    [
        lambda: BadRequest("Query is too old and response timeout expired super-secret-token"),
        lambda: TimedOut("timed out super-secret-token"),
    ],
    ids=["stale_bad_request", "timed_out"],
)
@pytest.mark.parametrize(
    "handler,data,expected_fragment",
    [
        (h.show_status, "status:c1", "شغال"),
        (h.show_cost, "cost:c1", "1.5000"),
    ],
    ids=["status", "cost"],
)
def test_show_status_cost_answer_failure_continues_and_logs_type_only(
    tmp_path, caplog, handler, data, expected_fragment, exc_factory
):
    conv = {
        "id": "c1",
        "title": "شات",
        "execution_status": "running",
        "metrics": {"accumulated_cost": 1.5},
    }
    ctx = _ctx_with(tmp_path, DetailClient(conv))
    exc = exc_factory()
    update = _cb_with_answer_error(data, exc, update_id=7101)

    with caplog.at_level(logging.WARNING, logger="bot.handlers"):
        asyncio.run(handler(update, ctx))

    assert update.callback_query.answer_calls == 1
    assert update.callback_query.edits
    assert expected_fragment in update.callback_query.edits[-1]
    assert ctx.bot_data["db"].update_outcome(7101) == uo.EXPLICITLY_IGNORED
    assert ctx.bot_data["db"].is_update_acknowledgment_eligible(7101) is True
    assert type(exc).__name__ in caplog.text
    assert "super-secret-token" not in caplog.text


@pytest.mark.parametrize(
    "handler,data",
    [(h.show_status, "status:c1"), (h.show_cost, "cost:c1")],
    ids=["status", "cost"],
)
def test_show_status_cost_answer_cancelled_error_not_swallowed(tmp_path, handler, data):
    ctx = _ctx_with(tmp_path, DetailClient({"id": "c1"}))
    update = _cb_with_answer_error(data, asyncio.CancelledError(), update_id=7102)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(handler(update, ctx))


@pytest.mark.parametrize("data", ["status:c1", "cost:c1"], ids=["status", "cost"])
def test_e2e_redelivery_recovery_when_callback_query_expired(tmp_path, monkeypatch, data):
    """التعافي بعد 503 ثم انتهاء صلاحية الكولباك عند إعادة التسليم لا يتعطّل إلى FAILED_PERMANENT."""
    async def run(app, _install_bot):
        class _RecoveringClient(DetailClient):
            def __init__(self):
                super().__init__(
                    {
                        "id": "c1",
                        "title": "شات",
                        "execution_status": "running",
                        "metrics": {"accumulated_cost": 2.25},
                    }
                )
                self.calls = 0

            async def get_conversations(self, ids):
                self.calls += 1
                if self.calls == 1:
                    raise ApiError("service unavailable", 503)
                return await super().get_conversations(ids)

        app.bot_data["client"] = _RecoveringClient()
        db = app.bot_data["db"]
        poller = TelegramPoller(app, db)

        # الدورة 1: فشل تشغيلي ⇒ FAILED_TRANSIENT والحدّ يتوقف.
        assert await poller.process_updates([_callback(app, 7201, data)]) is None
        assert poller._next_offset is None
        assert db.update_outcome(7201) == uo.FAILED_TRANSIENT

        # الدورة 2: OpenHands تعافى لكن تيليجرام يرفض answerCallbackQuery لأن الاستعلام قديم.
        async def _expired_answer(self, *a, **k):
            raise BadRequest("Query is too old and response timeout expired")

        monkeypatch.setattr("telegram.Bot.answer_callback_query", _expired_answer)
        boundary = await poller.process_updates([_callback(app, 7201, data)])
        assert boundary == 7201
        assert poller._next_offset == 7202
        assert db.update_outcome(7201) == uo.EXPLICITLY_IGNORED
        assert db.is_update_acknowledgment_eligible(7201) is True

    asyncio.run(_with_started_app(tmp_path, monkeypatch, run))


# --------------------------------------------------------------------------- #
# 2) OPS01-D2: صمود التنسيق أمام بيانات OpenHands المشوّهة
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bad_metrics", ["invalid", ["x"], 42, True])
def test_format_cost_malformed_metrics_does_not_crash(bad_metrics):
    assert format_cost(bad_metrics) == "مفيش بيانات تكلفة."


def test_format_cost_malformed_token_usage_does_not_crash():
    out = format_cost({"model_name": "m", "accumulated_cost": 1.0, "accumulated_token_usage": "bad"})
    assert "m" in out
    assert "1.0000" in out


@pytest.mark.parametrize("bad_state", [{"nested": 1}, ["running"], 123, True])
def test_state_label_non_string_unhashable_safe(bad_state):
    assert state_label(bad_state) == "غير معروف"


def test_show_cost_malformed_metrics_displays_safely_and_is_eligible(tmp_path):
    ctx = _ctx_with(tmp_path, DetailClient({"id": "c1", "metrics": "not-a-dict"}))
    update = _cb_update(OWNER_ID, "cost:c1")
    update.update_id = 7301
    asyncio.run(h.show_cost(update, ctx))
    assert update.callback_query.edits
    assert "مفيش بيانات تكلفة" in update.callback_query.edits[-1]
    assert ctx.bot_data["db"].update_outcome(7301) == uo.EXPLICITLY_IGNORED


def test_show_status_unhashable_execution_status_displays_safely(tmp_path):
    ctx = _ctx_with(
        tmp_path,
        DetailClient({"id": "c1", "title": "شات", "execution_status": {"bad": 1}}),
    )
    update = _cb_update(OWNER_ID, "status:c1")
    update.update_id = 7302
    asyncio.run(h.show_status(update, ctx))
    assert update.callback_query.edits
    assert "غير معروف" in update.callback_query.edits[-1]
    assert ctx.bot_data["db"].update_outcome(7302) == uo.EXPLICITLY_IGNORED
