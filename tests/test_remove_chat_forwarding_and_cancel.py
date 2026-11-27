"""Removal regressions for chat-forwarding UX, route state, and cancellation controls.

Deterministic fakes and temp SQLite only; no Telegram/OpenHands network calls.
"""
from __future__ import annotations

import asyncio

from telegram.ext import CallbackQueryHandler, CommandHandler

import bot.handlers as h
from bot import outbox
from bot.app import BOT_COMMANDS, build_application
from bot.db import Database
from bot import keyboards as kb
from tests.test_4b import OpenClient, Q, cb_update
from tests.test_app import make_config
from tests.test_handlers import make_context, make_update

OWNER = 1


def _open(ctx, conversation_id: str, *, title: str = "شات") -> None:
    ctx.bot_data["client"] = OpenClient(
        {"id": conversation_id, "title": title, "execution_status": "finished"}
    )
    asyncio.run(h.open_conversation(cb_update(Q(f"open:{conversation_id}")), ctx))


def _send(ctx, text: str, *, user_id: int = OWNER):
    update = make_update(user_id, text)
    asyncio.run(h.handle_text(update, ctx))
    return update


def _pending(ctx):
    return ctx.bot_data["db"].list_outbox_by_status("pending")


def test_open_has_no_forwarding_instruction_and_no_route(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    q = Q("open:A")
    ctx.bot_data["client"] = OpenClient(
        {"id": "A", "title": "A", "execution_status": "finished"}
    )
    asyncio.run(h.open_conversation(cb_update(q), ctx))

    shown = "".join(q.edits)
    assert "رسايلك الجاية" not in shown
    assert "إلغاء التوجيه" not in shown
    assert "/cancel" not in shown
    assert ctx.bot_data["db"].get_awaiting(OWNER) == (None, None)
    assert ctx.bot_data["db"].get_last_accessed_conversation(OWNER) == "A"


def test_legacy_route_without_last_target_does_not_redirect(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER, "A", "route", title="A")

    update = _send(ctx, "لا يجب أن يذهب إلى route قديم")

    assert _pending(ctx) == []
    assert db.count_creation_jobs() == 0
    assert "مفيش شات محدد" in update.message.replies[0]


def test_legacy_route_does_not_override_last_accessed(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    db = ctx.bot_data["db"]
    db.set_last_accessed_conversation(OWNER, "B")
    db.set_awaiting(OWNER, "A", "route", title="A")

    _send(ctx, "يذهب إلى B فقط")

    assert [item.conversation_id for item in _pending(ctx)] == ["B"]


def test_legacy_pause_setting_does_not_block_ordinary_text(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    db = ctx.bot_data["db"]
    db.set_last_accessed_conversation(OWNER, "A")
    db.set_setting(f"routing_paused:{OWNER}", "1")

    _send(ctx, "رسالة عادية")

    assert [item.conversation_id for item in _pending(ctx)] == ["A"]


def test_cancel_command_callback_button_and_help_are_removed(tmp_path):
    app = build_application(make_config(tmp_path))
    commands = {
        command
        for group in app.handlers.values()
        for handler in group
        if isinstance(handler, CommandHandler)
        for command in handler.commands
    }
    patterns = {
        getattr(handler.pattern, "pattern", str(handler.pattern))
        for group in app.handlers.values()
        for handler in group
        if isinstance(handler, CallbackQueryHandler)
    }
    callbacks = [
        button.callback_data
        for row in kb.conversation_actions("c1").inline_keyboard
        for button in row
    ]

    assert "cancel" not in commands
    assert "cancelroute" not in patterns
    assert "cancelroute" not in callbacks
    assert "cancel" not in [name for name, _ in BOT_COMMANDS]
    assert not hasattr(h, "cancel_route")
    assert not hasattr(h, "cancel_route_button")
    assert "/cancel" not in h.HELP_TEXT
    assert "إلغاء التوجيه" not in h.HELP_TEXT


def test_manual_copy_buttons_remain(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    _open(ctx, "A")
    markup = kb.conversation_actions(
        "A", has_reply=True, reply_cut=False, mini_app_url="https://example.test/app"
    )
    callbacks = [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    ]
    assert "copy:A" in callbacks
    assert "txt:A" in callbacks
    assert "reply:A" in callbacks
    assert "open:A" in callbacks
    assert "cancelroute" not in callbacks


def test_ordinary_prompt_submission_and_selection_still_work(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    _open(ctx, "A")
    _send(ctx, "إلى A")
    _open(ctx, "B")
    _send(ctx, "إلى B")

    assert [item.conversation_id for item in _pending(ctx)] == ["A", "B"]
    assert ctx.bot_data["db"].get_awaiting(OWNER) == (None, None)
    assert ctx.bot_data["db"].get_last_accessed_conversation(OWNER) == "B"


def test_queued_ack_is_not_a_delivery_claim(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    _open(ctx, "A")
    update = _send(ctx, "برومت")

    assert update.message.replies
    assert "تم حفظ طلبك" in update.message.replies[0]
    assert "اتبعت" not in update.message.replies[0]
    assert len(_pending(ctx)) == 1


def test_deleted_target_is_not_used_after_restart(tmp_path):
    db_path = str(tmp_path / "deleted.sqlite3")
    ctx = make_context(OWNER, tmp_path)
    ctx.bot_data["db"] = Database(db_path)
    try:
        _open(ctx, "A")
        ctx.bot_data["db"].delete_conversation(
            "A", outbox.now_iso(), remote_confirmed=True
        )
        update = _send(ctx, "بعد الحذف")
        assert _pending(ctx) == []
        assert ctx.bot_data["db"].get_last_accessed_conversation(OWNER) is None
        assert "اتحذف" in update.message.replies[0]
        ctx.bot_data["db"].close()

        reopened = Database(db_path)
        ctx.bot_data["db"] = reopened
        later = _send(ctx, "بعد إعادة التشغيل")
        assert reopened.count_outbox() == 0
        assert reopened.get_last_accessed_conversation(OWNER) is None
        assert "مفيش شات محدد" in later.message.replies[0]
    finally:
        ctx.bot_data["db"].close()


def test_chat_reopens_last_accessed_without_creating_route_or_prompt(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    _open(ctx, "A")
    before = ctx.bot_data["db"].count_outbox()
    update = make_update(OWNER, "/chat")

    asyncio.run(h.chat(update, ctx))

    assert ctx.bot_data["db"].count_outbox() == before
    assert ctx.bot_data["db"].count_creation_jobs() == 0
    assert ctx.bot_data["db"].get_awaiting(OWNER) == (None, None)
    assert ctx.bot_data["db"].get_last_accessed_conversation(OWNER) == "A"


def test_start_does_not_reactivate_legacy_pause(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    db = ctx.bot_data["db"]
    _open(ctx, "A")
    db.set_setting(f"routing_paused:{OWNER}", "1")
    asyncio.run(h.start(make_update(OWNER, "/start"), ctx))

    _send(ctx, "بعد /start")

    assert [item.conversation_id for item in _pending(ctx)] == ["A"]


def test_selection_change_during_preparation_rejects_prompt(tmp_path, monkeypatch):
    async def run():
        ctx = make_context(OWNER, tmp_path)
        db = ctx.bot_data["db"]
        ctx.bot_data["client"] = OpenClient(
            {"id": "A", "title": "A", "execution_status": "finished"}
        )
        await h.open_conversation(cb_update(Q("open:A")), ctx)
        started = asyncio.Event()
        release = asyncio.Event()

        async def blocked(_db, _cid):
            started.set()
            await release.wait()
            return False

        monkeypatch.setattr(h, "_is_deleted_with_retry", blocked)
        update = make_update(OWNER, "برومت أثناء تغيير الاختيار")
        update.update_id = 9901
        task = asyncio.create_task(h.handle_text(update, ctx))
        await started.wait()
        db.set_last_accessed_conversation(OWNER, "B")
        release.set()
        await task

        assert db.count_outbox() == 0
        assert any("تغيّر الشات المختار" in text for text in update.message.replies)

    asyncio.run(run())


def test_unavailable_target_has_no_fallback_or_creation(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    _open(ctx, "A")
    ctx.bot_data["db"].delete_conversation(
        "A", outbox.now_iso(), remote_confirmed=True
    )

    update = _send(ctx, "هدف غير متاح")

    assert _pending(ctx) == []
    assert ctx.bot_data["db"].count_creation_jobs() == 0
    assert any("اتحذف" in text for text in update.message.replies)
    assert ctx.bot_data["db"].get_last_accessed_conversation(OWNER) is None
