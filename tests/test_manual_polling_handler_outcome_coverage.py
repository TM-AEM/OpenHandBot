"""OHB2-MANUAL-POLLING-HANDLER-OUTCOME-COVERAGE — اختبارات تغطية نتائج المعالجات.

بتغطّي الفجوات اللي حدّدها OHB2-MANUAL-POLLING-ACK-INTEGRATION-DESIGN: كل مسار معالج
ذي صلة لازم يسجّل **نتيجة صريحة مصنّفة صح** قبل ما يرجع، وأهمها:

- **مسار الديدَب الفاشل**: فشل قاعدة في `dedupe_update` **مايتحوّلش** لتجاهل/نجاح صامت؛
  بيتسجّل فشل (غير مؤهّل) والاستثناء `ApplicationHandlerStop` بيتوقف، وما بيتكتبش في جدول
  الديدَب ⇒ إعادة التسليم لسه تنفّذ.
- العمليات الدائمة المحلية ⇒ `durable_completed`.
- القراءة/الرفض المقصود ⇒ `explicitly_ignored`.
- الفشل الخارجي المُبتلَع ⇒ `partial_or_unknown`/`failed_*` (غير مؤهّل).

مفيش شبكة: قاعدة SQLite معزولة وعملاء وهميين، والنداء مباشر للـ handler.
"""
from __future__ import annotations

import asyncio
import sqlite3
from types import SimpleNamespace

import pytest
from telegram.ext import ApplicationHandlerStop

import bot.handlers as h
from bot import update_outcomes as uo
from bot.db import Database
from bot.errors import ApiError

from tests.test_duplicate_update_dispatch import OWNER_ID
from tests.test_handlers import (
    DetailClient,
    ExchangeClient,
    FakeQuery,
    _cb_update,
    _ctx_with,
    make_update,
)


def _cb(tmp_path, client, data, update_id):
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(OWNER_ID, data)
    update.update_id = update_id
    return update, ctx


# ============================================================================
# 0) مسار الديدَب الفاشل — الحاسم: فشل قاعدة **مش** تجاهل/نجاح صامت
# ============================================================================
def test_dedupe_db_failure_records_failure_and_stops(tmp_path, monkeypatch):
    """فشل فحص الديدَب ⇒ فشل مسجّل (غير مؤهّل) + إيقاف المعالجة، مش «تحديث مُتجاهَل ناجح».

    الفشل بيتكتب في `update_failures` بس (مش جدول الديدَب) ⇒ إعادة التسليم لسه تنفّذ
    (مفيش «ترخيص» مزدوج صامت).
    """
    db = Database(str(tmp_path / "dedupe.sqlite3"))

    def permanent(_uid):
        raise sqlite3.OperationalError("no such table: processed_updates")

    monkeypatch.setattr(db, "update_is_processed", permanent)
    ctx = SimpleNamespace(bot_data={"db": db})
    update = SimpleNamespace(update_id=9001)

    with pytest.raises(ApplicationHandlerStop):
        asyncio.run(h.dedupe_update(update, ctx))

    # مش نتيجة تجاهل/نجاح — فشل صريح غير مؤهّل.
    assert db.update_outcome(9001) != uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(9001) is False
    assert db.update_failure(9001) == uo.FAILED_PERMANENT
    # الفشل **مش** في جدول الديدَب ⇒ إعادة التسليم تنفّذ.
    assert db.count_processed_updates() == 0
    db.close()


def test_dedupe_duplicate_stops_without_new_outcome(tmp_path):
    """تحديث مكرّر ⇒ إيقاف بلا كتابة نتيجة جديدة (مفيش فشل كاذب)."""
    db = Database(str(tmp_path / "dedupe2.sqlite3"))
    db.mark_update_outcome(9101, "2026-01-01T00:00:00+00:00", uo.DURABLE_COMPLETED)
    ctx = SimpleNamespace(bot_data={"db": db})
    with pytest.raises(ApplicationHandlerStop):
        asyncio.run(h.dedupe_update(SimpleNamespace(update_id=9101), ctx))
    assert db.update_failure(9101) is None
    db.close()


def test_dedupe_missing_update_id_is_noop(tmp_path):
    """تحديث بلا `update_id` صالح ⇒ ما بنمنعش أي حاجة (مفيش نتيجة)."""
    db = Database(str(tmp_path / "dedupe3.sqlite3"))
    ctx = SimpleNamespace(bot_data={"db": db})
    asyncio.run(h.dedupe_update(SimpleNamespace(update_id="x"), ctx))
    assert db.count_processed_updates() == 0
    db.close()


# ============================================================================
# 1) عمليات دائمة محلية ⇒ durable_completed
# ============================================================================
def test_watch_conversation_records_durable_completed(tmp_path):
    ctx_client = DetailClient({"id": "c1", "title": "شات", "execution_status": "running"})
    update, ctx = _cb(tmp_path, ctx_client, "watch:c1", 9201)
    asyncio.run(h.watch_conversation(update, ctx))
    assert ctx.bot_data["db"].is_watched("c1")
    assert ctx.bot_data["db"].update_outcome(9201) == uo.DURABLE_COMPLETED
    assert ctx.bot_data["db"].is_update_acknowledgment_eligible(9201) is True


def test_unwatch_conversation_records_durable_completed(tmp_path):
    update, ctx = _cb(tmp_path, DetailClient(None), "unwatch:c1", 9202)
    ctx.bot_data["db"].add_watched("c1")
    asyncio.run(h.unwatch_conversation(update, ctx))
    assert not ctx.bot_data["db"].is_watched("c1")
    assert ctx.bot_data["db"].update_outcome(9202) == uo.DURABLE_COMPLETED


def test_reply_prompt_records_durable_completed(tmp_path):
    update, ctx = _cb(tmp_path, DetailClient({"id": "c1", "title": "شات"}), "reply:c1", 9203)
    asyncio.run(h.reply_prompt(update, ctx))
    assert ctx.bot_data["db"].update_outcome(9203) == uo.DURABLE_COMPLETED


def test_pick_repo_records_durable_completed(tmp_path):
    update, ctx = _cb(tmp_path, DetailClient(None), "pickrepo:7:0", 9204)
    ctx.bot_data["repo_nav"] = {OWNER_ID: {"gen": 7, "names": ["owner/repo"], "query": ""}}
    asyncio.run(h.pick_repo(update, ctx))
    assert ctx.bot_data["db"].update_outcome(9204) == uo.DURABLE_COMPLETED


def test_cancel_route_button_records_durable_completed(tmp_path):
    update, ctx = _cb(tmp_path, DetailClient(None), "cancelroute", 9205)
    asyncio.run(h.cancel_route_button(update, ctx))
    assert ctx.bot_data["db"].update_outcome(9205) == uo.DURABLE_COMPLETED


def test_cancel_route_message_records_durable_completed(tmp_path):
    ctx = _ctx_with(tmp_path, DetailClient(None))
    update = make_update(OWNER_ID, "/cancel")
    update.update_id = 9206
    asyncio.run(h.cancel_route(update, ctx))
    assert ctx.bot_data["db"].update_outcome(9206) == uo.DURABLE_COMPLETED


# ============================================================================
# 2) قراءة/رفض مقصود ⇒ explicitly_ignored
# ============================================================================
def test_list_watches_empty_records_ignored(tmp_path):
    update, ctx = _cb(tmp_path, DetailClient(None), "watched:0", 9301)
    asyncio.run(h.list_watches(update, ctx))
    assert ctx.bot_data["db"].update_outcome(9301) == uo.EXPLICITLY_IGNORED


def test_start_records_ignored(tmp_path):
    ctx = _ctx_with(tmp_path, DetailClient(None))
    update = make_update(OWNER_ID, "/start")
    update.update_id = 9302
    asyncio.run(h.start(update, ctx))
    assert ctx.bot_data["db"].update_outcome(9302) == uo.EXPLICITLY_IGNORED


def test_help_records_ignored(tmp_path):
    ctx = _ctx_with(tmp_path, DetailClient(None))
    update = make_update(OWNER_ID, "/help")
    update.update_id = 9303
    asyncio.run(h.help_command(update, ctx))
    assert ctx.bot_data["db"].update_outcome(9303) == uo.EXPLICITLY_IGNORED


def test_outbox_list_records_ignored(tmp_path):
    ctx = _ctx_with(tmp_path, DetailClient(None))
    update = make_update(OWNER_ID, "/outbox")
    update.update_id = 9304
    asyncio.run(h.outbox_list(update, ctx))
    assert ctx.bot_data["db"].update_outcome(9304) == uo.EXPLICITLY_IGNORED


def test_show_status_conversation_not_found_records_ignored(tmp_path):
    update, ctx = _cb(tmp_path, DetailClient(None), "status:c1", 9305)
    asyncio.run(h.show_status(update, ctx))
    assert ctx.bot_data["db"].update_outcome(9305) == uo.EXPLICITLY_IGNORED


def test_authorization_rejection_records_ignored_and_sends_nothing(tmp_path):
    """رفض التفويض: نتيجة صريحة + **مفيش** أي كشف/إرسال (سلوك التفويض ما اتغيّرش)."""
    ctx = _ctx_with(tmp_path, DetailClient(None))
    update = make_update(999, "/start")  # مستخدم غير مسموح
    update.update_id = 9306
    asyncio.run(h.start(update, ctx))
    assert update.message.replies == []  # مفيش رسالة
    assert ctx.bot_data["db"].update_outcome(9306) == uo.EXPLICITLY_IGNORED


# ============================================================================
# 3) فشل خارجي مُبتلَع ⇒ partial_or_unknown / failed_* (غير مؤهّل)
# ============================================================================
def test_list_files_upstream_error_records_ambiguous(tmp_path):
    class _UpstreamFilesClient(DetailClient):
        async def list_files(self, conversation_id, path=""):
            raise ApiError("upstream down")

    update, ctx = _cb(tmp_path, _UpstreamFilesClient({"id": "c1"}), "files:c1:0", 9401)
    asyncio.run(h.list_files(update, ctx))
    db = ctx.bot_data["db"]
    assert db.update_outcome(9401) == uo.PARTIAL_OR_UNKNOWN
    assert db.is_update_acknowledgment_eligible(9401) is False


def test_send_reply_txt_transient_upstream_records_ambiguous(tmp_path):
    client = ExchangeClient({"id": "c1", "title": "شات"}, exchange_error=ApiError("timeout"))
    update, ctx = _cb(tmp_path, client, "txt:c1", 9402)
    asyncio.run(h.send_reply_txt(update, ctx))
    db = ctx.bot_data["db"]
    assert db.update_outcome(9402) == uo.PARTIAL_OR_UNKNOWN
    assert db.is_update_acknowledgment_eligible(9402) is False


def test_send_reply_txt_permanent_rejection_records_ignored(tmp_path):
    client = ExchangeClient({"id": "c1", "title": "شات"}, exchange_error=ApiError("gone", 404))
    update, ctx = _cb(tmp_path, client, "txt:c1", 9403)
    asyncio.run(h.send_reply_txt(update, ctx))
    assert ctx.bot_data["db"].update_outcome(9403) == uo.EXPLICITLY_IGNORED


def test_show_status_display_failure_records_transient(tmp_path):
    """فشل عرض تيليجرام (تسليم المحتوى الوحيد المطلوب) ⇒ failed_transient (مش تجاهل)."""
    class _FailingEditQuery(FakeQuery):
        async def edit_message_text(self, text, **kw):
            raise RuntimeError("telegram down")

    ctx = _ctx_with(tmp_path, DetailClient({"id": "c1", "title": "شات", "execution_status": "running"}))
    update = _cb_update(OWNER_ID, "status:c1")
    update.update_id = 9404
    update.callback_query = _FailingEditQuery()
    update.callback_query.data = "status:c1"
    asyncio.run(h.show_status(update, ctx))
    db = ctx.bot_data["db"]
    assert db.update_outcome(9404) == uo.FAILED_TRANSIENT
    assert db.is_update_acknowledgment_eligible(9404) is False


def test_delete_confirm_db_failure_records_permanent(tmp_path, monkeypatch):
    from tests.test_handlers import F1ListClient

    update, ctx = _cb(tmp_path, F1ListClient(conv={"id": "c1", "title": "شات"}), "deleteok:c1", 9405)
    ctx.bot_data["db"].add_watched("c1", "شات", chat_id=99)

    def boom(*_a, **_k):
        raise sqlite3.Error("boom")

    monkeypatch.setattr(ctx.bot_data["db"], "delete_conversation", boom)
    asyncio.run(h.delete_conversation_confirm(update, ctx))
    assert ctx.bot_data["db"].update_failure(9405) == uo.FAILED_PERMANENT


# ============================================================================
# 4) معالجات إدارة الصندوق (أوامر المالك) — نتيجة لكل مسار
# ============================================================================
def _msg_update(tmp_path, text, update_id):
    ctx = _ctx_with(tmp_path, DetailClient(None))
    update = make_update(OWNER_ID, text)
    update.update_id = update_id
    return update, ctx


def test_outbox_status_usage_records_ignored(tmp_path):
    update, ctx = _msg_update(tmp_path, "/outbox_status", 9501)
    ctx.args = []
    asyncio.run(h.outbox_status(update, ctx))
    assert ctx.bot_data["db"].update_outcome(9501) == uo.EXPLICITLY_IGNORED


def test_outbox_status_found_records_ignored(tmp_path):
    update, ctx = _msg_update(tmp_path, "/outbox_status prompt:1", 9502)
    oid = ctx.bot_data["db"].add_outbox("c1", 99, "برومت", "2026-01-01T00:00:00+00:00")
    ctx.args = [f"prompt:{oid}"]
    asyncio.run(h.outbox_status(update, ctx))
    assert ctx.bot_data["db"].update_outcome(9502) == uo.EXPLICITLY_IGNORED


def test_outbox_discard_confirmed_records_durable_completed(tmp_path):
    update, ctx = _msg_update(tmp_path, "/outbox_discard prompt:1 confirm", 9503)
    oid = ctx.bot_data["db"].add_outbox("c1", 99, "برومت", "2026-01-01T00:00:00+00:00")
    ctx.args = [f"prompt:{oid}", "confirm"]
    asyncio.run(h.outbox_discard(update, ctx))
    assert ctx.bot_data["db"].update_outcome(9503) == uo.DURABLE_COMPLETED


def test_outbox_discard_not_confirmed_records_ambiguous(tmp_path):
    """الـ POST ممكن يكون بدأ ⇒ نتيجة غامضة (غير مؤهّلة)، مش نجاح."""
    update, ctx = _msg_update(tmp_path, "/outbox_discard prompt:1 confirm", 9504)
    oid = ctx.bot_data["db"].add_outbox("c1", 99, "برومت", "2026-01-01T00:00:00+00:00")
    ctx.bot_data["db"].set_outbox_status(oid, "unknown", "2026-01-01T00:00:01+00:00")
    ctx.args = [f"prompt:{oid}", "confirm"]
    asyncio.run(h.outbox_discard(update, ctx))
    db = ctx.bot_data["db"]
    assert db.update_outcome(9504) == uo.PARTIAL_OR_UNKNOWN
    assert db.is_update_acknowledgment_eligible(9504) is False


def test_outbox_mark_sent_usage_records_ignored(tmp_path):
    update, ctx = _msg_update(tmp_path, "/outbox_mark_sent", 9505)
    ctx.args = []
    asyncio.run(h.outbox_mark_sent(update, ctx))
    assert ctx.bot_data["db"].update_outcome(9505) == uo.EXPLICITLY_IGNORED


def test_outbox_mark_sent_unknown_to_sent_records_durable_completed(tmp_path):
    update, ctx = _msg_update(tmp_path, "/outbox_mark_sent prompt:1 confirm", 9506)
    oid = ctx.bot_data["db"].add_outbox("c1", 99, "برومت", "2026-01-01T00:00:00+00:00")
    ctx.bot_data["db"].set_outbox_status(oid, "unknown", "2026-01-01T00:00:01+00:00")
    ctx.args = [f"prompt:{oid}", "confirm"]
    asyncio.run(h.outbox_mark_sent(update, ctx))
    assert ctx.bot_data["db"].update_outcome(9506) == uo.DURABLE_COMPLETED


# ============================================================================
# 5) نص في حالة انتظار **منتهية** ⇒ تجاهل صريح (البرومت ما اتنفّذش عمدًا)
# ============================================================================
def test_handle_text_expired_state_records_ignored(tmp_path):
    from datetime import datetime, timedelta, timezone

    ctx = _ctx_with(tmp_path, DetailClient(None))
    ctx.bot_data["db"].set_awaiting(
        OWNER_ID, "c1", "reply", now=datetime.now(timezone.utc) - timedelta(hours=1)
    )
    update = make_update(OWNER_ID, "برومت قديم")
    update.update_id = 9601
    asyncio.run(h.handle_text(update, ctx))
    assert ctx.bot_data["db"].update_outcome(9601) == uo.EXPLICITLY_IGNORED


# ============================================================================
# 6) OHB2-PLAN-01-STAGE4: show_status/show_cost — نجاح العرض ⇒ نتيجة صريحة مؤهّلة
# ============================================================================
# العيب المؤكّد: show_status/show_cost كانوا بيسجّلوا نتيجة **بس** على مسارات الفشل/الرفض،
# والمسار الناجح (العرض اتحقق) كان بيرجع **بلا أي نتيجة** ⇒ غير مؤهّل (fail-closed) ⇒ حجب
# الحدّ من غير سبب، على عكس كل مسارات العرض التانية (open_conversation/copy_reply/…).
def test_show_status_success_records_ignored(tmp_path):
    ctx = _ctx_with(
        tmp_path,
        DetailClient({"id": "c1", "title": "شات", "execution_status": "running"}),
    )
    update = _cb_update(OWNER_ID, "status:c1")
    update.update_id = 9701
    asyncio.run(h.show_status(update, ctx))
    db = ctx.bot_data["db"]
    assert db.update_outcome(9701) == uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(9701) is True


def test_show_cost_success_records_ignored(tmp_path):
    ctx = _ctx_with(
        tmp_path,
        DetailClient(
            {"id": "c1", "title": "شات", "metrics": {"accumulated_cost": 1.5}}
        ),
    )
    update = _cb_update(OWNER_ID, "cost:c1")
    update.update_id = 9702
    asyncio.run(h.show_cost(update, ctx))
    db = ctx.bot_data["db"]
    assert db.update_outcome(9702) == uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(9702) is True


def test_show_cost_conversation_not_found_records_ignored(tmp_path):
    update, ctx = _cb(tmp_path, DetailClient(None), "cost:c1", 9703)
    asyncio.run(h.show_cost(update, ctx))
    assert ctx.bot_data["db"].update_outcome(9703) == uo.EXPLICITLY_IGNORED


def test_show_cost_display_failure_records_transient(tmp_path):
    """فشل عرض التكلفة ⇒ failed_transient (غير مؤهّل)، ومفيش نجاح كاذب."""

    class _FailingEditQuery(FakeQuery):
        async def edit_message_text(self, text, **kw):
            raise RuntimeError("telegram down")

    ctx = _ctx_with(
        tmp_path,
        DetailClient(
            {"id": "c1", "title": "شات", "metrics": {"accumulated_cost": 2.0}}
        ),
    )
    update = _cb_update(OWNER_ID, "cost:c1")
    update.update_id = 9704
    update.callback_query = _FailingEditQuery()
    update.callback_query.data = "cost:c1"
    asyncio.run(h.show_cost(update, ctx))
    db = ctx.bot_data["db"]
    assert db.update_outcome(9704) == uo.FAILED_TRANSIENT
    assert db.is_update_acknowledgment_eligible(9704) is False
