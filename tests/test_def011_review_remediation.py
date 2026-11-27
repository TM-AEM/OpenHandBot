"""Focused regressions for the DEF-011 review findings F-01/F-06/F-07/F-08.

Deterministic fakes and temp SQLite only; no network and no real sleeps.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from types import SimpleNamespace

import bot.handlers as h
from bot import outbox
from bot.db import Database
from tests.test_handlers import make_context, make_update

OWNER = 1

CID = "conv-remediation"


def _aged(minutes: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(minutes=minutes)


def test_routing_target_cas_rejects_prompt_after_selection_changes(tmp_path):
    db = Database(str(tmp_path / "cas.sqlite3"))
    db.set_last_accessed_conversation(OWNER, "A")
    db.set_last_accessed_conversation(OWNER, "B")

    out_id = db.add_or_group_outbox(
        "A", OWNER, "برومت", outbox.now_iso(),
        update_id=9001, expected_routing=(OWNER, "A"),
    )

    assert out_id == 0
    assert db.count_outbox() == 0


def test_routing_target_cas_allows_unchanged_target(tmp_path):
    db = Database(str(tmp_path / "cas-ok.sqlite3"))
    db.set_last_accessed_conversation(OWNER, "A")

    out_id = db.add_or_group_outbox(
        "A", OWNER, "برومت", outbox.now_iso(),
        update_id=9002, expected_routing=(OWNER, "A"),
    )

    assert out_id > 0
    assert db.get_outbox(out_id).conversation_id == "A"


def test_handler_rejects_prompt_when_selection_changes_during_preparation(
    tmp_path, monkeypatch
):
    async def _run():
        ctx = make_context(OWNER, tmp_path)
        db = ctx.bot_data["db"]
        db.set_last_accessed_conversation(OWNER, "A")
        started = asyncio.Event()
        release = asyncio.Event()

        async def blocked_deleted_check(_db, _conversation_id):
            started.set()
            await release.wait()
            return False

        monkeypatch.setattr(h, "_is_deleted_with_retry", blocked_deleted_check)
        update = make_update(OWNER, "برومت أثناء التغيير")
        update.update_id = 9003
        task = asyncio.create_task(h.handle_text(update, ctx))
        await started.wait()
        db.set_last_accessed_conversation(OWNER, "B")
        release.set()
        await task

        assert db.count_outbox() == 0
        assert any("تغيّر الشات المختار" in text for text in update.message.replies)

    asyncio.run(_run())


def test_expired_reply_consumes_stale_state_when_routing_allowed(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    db = ctx.bot_data["db"]
    db.set_last_accessed_conversation(OWNER, "A")
    db.set_awaiting(OWNER, "A", "reply", now=_aged(30))
    update = make_update(OWNER, "رد متأخر")

    asyncio.run(h.handle_text(update, ctx))

    assert [item.conversation_id for item in db.list_outbox_by_status("pending")] == ["A"]
    assert db.get_awaiting(OWNER) == (None, None)


def test_prompt_ack_is_explicitly_queued_and_ack_id_is_persisted(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER, "A", "reply")
    update = make_update(OWNER, "برومت")
    update.update_id = 9010
    replies = []

    async def reply_text(text, **kw):
        replies.append(text)
        return SimpleNamespace(message_id=700)

    update.message.reply_text = reply_text

    asyncio.run(h.handle_text(update, ctx))

    assert replies == ["وصل ✅ — تم حفظ طلبك، ولسه هيتبعت."]
    item = db.list_outbox_by_status("pending")[0]
    assert item.ack_message_ids == (700,)
    assert item.telegram_message_ids == ()


def test_missing_ack_message_id_is_not_guessed_or_tracked(tmp_path):
    ctx = make_context(OWNER, tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER, "A", "reply")
    update = make_update(OWNER, "برومت")
    update.update_id = 9011
    replies = []

    async def reply_text(text, **kw):
        replies.append(text)
        return None

    update.message.reply_text = reply_text

    asyncio.run(h.handle_text(update, ctx))

    item = db.list_outbox_by_status("pending")[0]
    assert item.ack_message_ids == ()
    assert item.telegram_message_ids == ()
