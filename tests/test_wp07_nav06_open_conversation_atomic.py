"""OHB2-WP-07 (NAV-06) — atomic display success + last-accessed selection.

Opening a conversation no longer creates a forwarding route window. The durable effect is
`last_accessed_conversation_id`, written together with the update outcome after Telegram
confirms the view was displayed. A failed display changes neither value.
"""
from __future__ import annotations

import asyncio

import pytest

import bot.handlers as h
from bot import update_outcomes as uo
from bot.db import Database

from tests.test_4b import Q, OpenClient, cb_update
from tests.test_handlers import make_context

OWNER_ID = 1


def _open_ctx(tmp_path, title="شات A"):
    client = OpenClient({"id": "A", "title": title, "execution_status": "finished"})
    return make_context(OWNER_ID, tmp_path, client=client)


def _cb_with_id(data, update_id):
    update = cb_update(Q(data))
    update.update_id = update_id
    return update


def test_display_success_commits_last_accessed_and_outcome_together(tmp_path):
    ctx = _open_ctx(tmp_path)
    db = ctx.bot_data["db"]

    asyncio.run(h.open_conversation(_cb_with_id("open:A", 7001), ctx))

    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.get_last_accessed_conversation(OWNER_ID) == "A"
    assert db.update_outcome(7001) == uo.EXPLICITLY_IGNORED
    assert uo.is_ack_eligible(db.update_outcome(7001)) is True
    db.close()


def test_display_success_clears_stale_awaiting(tmp_path):
    ctx = _open_ctx(tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-OLD", "reply", title="قديم")

    asyncio.run(h.open_conversation(_cb_with_id("open:A", 7002), ctx))

    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.get_last_accessed_conversation(OWNER_ID) == "A"
    db.close()


def test_failure_cannot_leave_last_accessed_without_outcome(tmp_path, monkeypatch):
    ctx = _open_ctx(tmp_path)
    db = ctx.bot_data["db"]
    db.set_last_accessed_conversation(OWNER_ID, "conv-OLD")
    original = db._set_awaiting_nocommit

    def _write_then_fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("outcome write failed")

    monkeypatch.setattr(db, "_set_awaiting_nocommit", _write_then_fail)
    with pytest.raises(RuntimeError):
        asyncio.run(h.open_conversation(_cb_with_id("open:A", 7003), ctx))

    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.get_last_accessed_conversation(OWNER_ID) == "conv-OLD"
    assert db.update_outcome(7003) is None
    db.close()


def test_handler_rolls_back_on_outcome_write_failure(tmp_path, monkeypatch):
    ctx = _open_ctx(tmp_path)
    db = ctx.bot_data["db"]
    db.set_last_accessed_conversation(OWNER_ID, "conv-OLD")

    def _boom(*_a, **_k):
        raise RuntimeError("outcome write failed")

    monkeypatch.setattr(db, "mark_update_outcome", _boom)
    with pytest.raises(RuntimeError):
        asyncio.run(h.open_conversation(_cb_with_id("open:A", 7004), ctx))

    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.get_last_accessed_conversation(OWNER_ID) == "conv-OLD"
    assert db.count_processed_updates() == 0
    db.close()


def test_previous_awaiting_survives_failed_transaction(tmp_path, monkeypatch):
    ctx = _open_ctx(tmp_path)
    db = ctx.bot_data["db"]
    db.set_awaiting(OWNER_ID, "conv-OLD", "reply", title="قديم")

    def _boom(*_a, **_k):
        raise RuntimeError("outcome write failed")

    monkeypatch.setattr(db, "mark_update_outcome", _boom)
    with pytest.raises(RuntimeError):
        asyncio.run(h.open_conversation(_cb_with_id("open:A", 7005), ctx))

    assert db.get_awaiting(OWNER_ID) == ("conv-OLD", "reply")
    db.close()


def test_update_id_none_saves_last_without_outcome(tmp_path):
    ctx = _open_ctx(tmp_path)
    db = ctx.bot_data["db"]

    asyncio.run(h.open_conversation(cb_update(Q("open:A")), ctx))

    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.get_last_accessed_conversation(OWNER_ID) == "A"
    assert db.count_processed_updates() == 0
    db.close()


def test_display_failure_saves_nothing_and_records_transient(tmp_path):
    ctx = _open_ctx(tmp_path)
    db = ctx.bot_data["db"]
    db.set_last_accessed_conversation(OWNER_ID, "conv-OLD")
    q = Q("open:A")

    async def _fail(*_a, **_k):
        raise RuntimeError("Message can't be edited")

    q.edit_message_text = _fail
    update = cb_update(q)
    update.update_id = 7007

    asyncio.run(h.open_conversation(update, ctx))

    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.get_last_accessed_conversation(OWNER_ID) == "conv-OLD"
    assert db.update_outcome(7007) == uo.FAILED_TRANSIENT
    assert uo.is_ack_eligible(db.update_outcome(7007)) is False
    db.close()


def test_telegram_display_text_has_no_forwarding_instruction(tmp_path):
    ctx = _open_ctx(tmp_path)
    q = Q("open:A")
    update = cb_update(q)
    update.update_id = 7008

    asyncio.run(h.open_conversation(update, ctx))

    shown = "".join(q.edits)
    assert "رسايلك الجاية" not in shown
    assert "لحد ما تفتح/تختار شات تاني" not in shown
    assert "إلغاء التوجيه" not in shown
    assert q.markups and q.markups[0] is not None
    ctx.bot_data["db"].close()


def test_repeated_delivery_keeps_outcome_and_selection_consistent(tmp_path):
    ctx = _open_ctx(tmp_path)
    db = ctx.bot_data["db"]

    asyncio.run(h.open_conversation(_cb_with_id("open:A", 7009), ctx))
    asyncio.run(h.open_conversation(_cb_with_id("open:A", 7009), ctx))

    assert db.get_last_accessed_conversation(OWNER_ID) == "A"
    assert db.update_outcome(7009) == uo.EXPLICITLY_IGNORED
    db.close()


def test_helper_rolls_back_selection_when_outcome_write_fails(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "unit.sqlite3"))
    db.set_last_accessed_conversation(OWNER_ID, "conv-OLD")

    def _boom(*_a, **_k):
        raise RuntimeError("outcome write failed")

    monkeypatch.setattr(db, "mark_update_outcome", _boom)
    with pytest.raises(RuntimeError):
        db.set_awaiting_and_record_outcome(
            OWNER_ID, None, None, 8001, "2026-01-01T00:00:00+00:00",
            uo.EXPLICITLY_IGNORED, last_accessed_conversation_id="conv-A",
        )

    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.get_last_accessed_conversation(OWNER_ID) == "conv-OLD"
    assert db.update_outcome(8001) is None
    db.close()


def test_helper_without_update_id_saves_selection_only(tmp_path):
    db = Database(str(tmp_path / "unit2.sqlite3"))
    ok = db.set_awaiting_and_record_outcome(
        OWNER_ID, None, None, None, "2026-01-01T00:00:00+00:00",
        uo.EXPLICITLY_IGNORED, last_accessed_conversation_id="conv-A",
    )
    assert ok is False
    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.get_last_accessed_conversation(OWNER_ID) == "conv-A"
    assert db.count_processed_updates() == 0
    db.close()
