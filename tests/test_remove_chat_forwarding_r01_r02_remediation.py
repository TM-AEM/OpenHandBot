"""R-01/R-02 remediation regressions for forwarding removal.

R-01: pending newchat/reposearch selection must never route attachments or accompanying
text to a stale last_accessed conversation. R-02: a concurrent clear-to-None must produce
an explicit user response instead of a silent explicitly_ignored outcome.

Deterministic fakes, temp SQLite, and asyncio events only; no sleeps or network calls.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from telegram import Chat, Message, Update, User

import bot.handlers as h
from bot import update_outcomes as uo
from bot.attachments import AcceptOutcome, StageStatus
from tests.test_attachment_batch_lifecycle_a2 import (
    CID,
    Harness,
    OWNER_ID,
    _patch_telegram,
    accept,
    make_service,
)
from tests.test_handlers import make_context, make_update


def _harness(tmp_path, monkeypatch) -> Harness:
    harness = Harness(tmp_path)
    _patch_telegram(monkeypatch, harness)
    return harness


def _text_update(harness: Harness, text: str, update_id: int) -> Update:
    chat = Chat(id=99, type="private")
    user = User(id=OWNER_ID, first_name="o", is_bot=False)
    message = Message(
        message_id=77,
        date=None,
        chat=chat,
        from_user=user,
        text=text,
    )
    message.set_bot(harness.app.bot)
    update = Update(update_id=update_id, message=message)
    update.set_bot(harness.app.bot)
    return update


def _batch_id(harness: Harness) -> str:
    row = harness.db._conn.execute(
        "SELECT batch_id FROM attachment_batches ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    assert row is not None
    return row["batch_id"]


# ---------------------------------------------------------------- R-01 documents
@pytest.mark.parametrize(
    ("kind", "conversation_id"),
    [("newchat", None), ("reposearch", "")],
)
def test_pending_selection_document_does_not_bind_previous_conversation(
    tmp_path, monkeypatch, kind, conversation_id
):
    harness = _harness(tmp_path, monkeypatch)
    db = harness.db
    db.set_last_accessed_conversation(OWNER_ID, CID)
    db.set_awaiting(OWNER_ID, conversation_id, kind)

    harness.process(harness.document_update(99001))

    assert db.count_attachment_batches() == 0
    assert db.count_attachment_items() == 0
    assert "اختار شات" in harness.replies[0]
    assert db.update_outcome(99001) == uo.EXPLICITLY_IGNORED
    assert db.get_last_accessed_conversation(OWNER_ID) == CID
    assert db.get_awaiting(OWNER_ID) == (conversation_id, kind)


def test_pending_selection_without_last_accessed_has_explicit_response(
    tmp_path, monkeypatch
):
    harness = _harness(tmp_path, monkeypatch)
    db = harness.db
    db.set_awaiting(OWNER_ID, None, "newchat")

    harness.process(harness.document_update(99002))

    assert db.count_attachment_batches() == 0
    assert db.count_attachment_items() == 0
    assert "اختار شات" in harness.replies[0]
    assert db.update_outcome(99002) == uo.EXPLICITLY_IGNORED


def test_expired_pending_selection_is_cleared_and_not_used(tmp_path, monkeypatch):
    harness = _harness(tmp_path, monkeypatch)
    db = harness.db
    db.set_last_accessed_conversation(OWNER_ID, CID)
    db.set_awaiting(
        OWNER_ID,
        None,
        "newchat",
        now=datetime.now(timezone.utc) - timedelta(minutes=11),
    )

    harness.process(harness.document_update(99003))

    assert db.count_attachment_batches() == 0
    assert "انتهت مهلة اختيار الشات" in harness.replies[0]
    assert db.get_awaiting(OWNER_ID) == (None, None)
    assert db.update_outcome(99003) == uo.EXPLICITLY_IGNORED


def test_no_pending_selection_keeps_normal_attachment_behavior(tmp_path, monkeypatch):
    harness = _harness(tmp_path, monkeypatch)
    db = harness.db
    db.set_last_accessed_conversation(OWNER_ID, CID)

    harness.process(harness.document_update(99004))

    assert db.count_attachment_batches() == 1
    assert db.get_attachment_batch(_batch_id(harness)).conversation_id == CID
    assert harness.replies[-1] == h.ATTACHMENT_ACCEPTED_TEXT
    assert db.update_outcome(99004) == uo.DURABLE_INTENT_RECORDED


def test_pending_selection_created_during_upload_is_rejected_atomically(
    tmp_path, monkeypatch
):
    harness = _harness(tmp_path, monkeypatch)
    db = harness.db
    db.set_last_accessed_conversation(OWNER_ID, CID)
    ctx = SimpleNamespace(bot_data=harness.app.bot_data)
    real_service = h._attachment_service(ctx)

    class _RaceService:
        store = real_service.store

        async def accept(self, **kwargs):
            # Simulate new_chat_no_repo/pick_repo landing after the handler precheck.
            db.set_awaiting(OWNER_ID, None, "newchat")
            return await real_service.accept(**kwargs)

    monkeypatch.setattr(h, "_attachment_service", lambda _ctx: _RaceService())

    harness.process(harness.document_update(99005))

    assert db.count_attachment_batches() == 0
    assert db.count_attachment_items() == 0
    assert "اختار شات" in harness.replies[0]
    assert db.update_outcome(99005) == uo.EXPLICITLY_IGNORED


def test_service_rejects_pending_selection_before_any_batch_write(tmp_path):
    db, _store, _client, service = make_service(tmp_path)
    db.set_awaiting(OWNER_ID, None, "newchat")

    result = asyncio.run(accept(service, cid=CID))

    assert result.outcome is AcceptOutcome.REJECTED
    assert result.stage is StageStatus.REJECTED_SELECTION
    assert db.count_attachment_batches() == 0
    assert db.count_attachment_items() == 0
    db.close()


# ------------------------------------------------------- R-01 accompanying text
@pytest.mark.parametrize(
    ("kind", "conversation_id"),
    [("newchat", None), ("reposearch", "")],
)
def test_pending_selection_accompanying_text_does_not_use_old_batch(
    tmp_path, monkeypatch, kind, conversation_id
):
    harness = _harness(tmp_path, monkeypatch)
    db = harness.db
    db.set_last_accessed_conversation(OWNER_ID, CID)
    harness.process(harness.document_update(99006))
    batch_id = _batch_id(harness)
    db.set_awaiting(OWNER_ID, conversation_id, kind)

    harness.process(_text_update(harness, "نص للشات القديم", 99007))

    assert db.get_attachment_batch(batch_id).intent_text is None
    assert "اختار شات" in harness.replies[-1]
    assert db.update_outcome(99007) == uo.EXPLICITLY_IGNORED


# ---------------------------------------------------------------- R-02 races
def _start_blocked_prompt(tmp_path, monkeypatch):
    ctx = make_context(OWNER_ID, tmp_path)
    db = ctx.bot_data["db"]
    db.set_last_accessed_conversation(OWNER_ID, "A")
    started = asyncio.Event()
    release = asyncio.Event()
    original = h._is_deleted_with_retry

    async def blocked(_db, _cid):
        started.set()
        await release.wait()
        return False

    monkeypatch.setattr(h, "_is_deleted_with_retry", blocked)
    update = make_update(OWNER_ID, "برومت")
    update.update_id = 99101
    task = asyncio.create_task(h.handle_text(update, ctx))
    return ctx, db, update, task, started, release, original


def test_clear_to_none_before_cas_replies_and_does_not_silently_ignore(
    tmp_path, monkeypatch
):
    async def run():
        ctx, db, update, task, started, release, original = _start_blocked_prompt(
            tmp_path, monkeypatch
        )
        await started.wait()
        db.clear_last_accessed_conversation(OWNER_ID)
        release.set()
        await task

        assert db.count_outbox() == 0
        assert update.message.replies
        assert "اتغيّر أو اتشال" in update.message.replies[0]
        assert "تم حفظ" not in update.message.replies[0]
        assert db.update_outcome(99101) == uo.EXPLICITLY_IGNORED
        monkeypatch.setattr(h, "_is_deleted_with_retry", original)
        db.close()

    asyncio.run(run())


def test_changed_to_another_conversation_before_cas_replies(tmp_path, monkeypatch):
    async def run():
        ctx, db, update, task, started, release, original = _start_blocked_prompt(
            tmp_path, monkeypatch
        )
        await started.wait()
        db.set_last_accessed_conversation(OWNER_ID, "B")
        release.set()
        await task

        assert db.count_outbox() == 0
        assert update.message.replies
        assert "تغيّر الشات المختار" in update.message.replies[0]
        assert "تم حفظ" not in update.message.replies[0]
        monkeypatch.setattr(h, "_is_deleted_with_retry", original)
        db.close()

    asyncio.run(run())


def test_cas_database_failure_is_not_acknowledged(tmp_path, monkeypatch):
    ctx = make_context(OWNER_ID, tmp_path)
    db = ctx.bot_data["db"]
    db.set_last_accessed_conversation(OWNER_ID, "A")
    update = make_update(OWNER_ID, "برومت")
    update.update_id = 99102

    def _fail(*_args, **_kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(db, "add_or_group_outbox", _fail)
    with pytest.raises(RuntimeError):
        asyncio.run(h.handle_text(update, ctx))

    assert db.count_outbox() == 0
    assert update.message.replies == []
    db.close()


def test_cas_success_still_queues_prompt_and_ack(tmp_path):
    ctx = make_context(OWNER_ID, tmp_path)
    db = ctx.bot_data["db"]
    db.set_last_accessed_conversation(OWNER_ID, "A")
    update = make_update(OWNER_ID, "برومت")
    update.update_id = 99103

    asyncio.run(h.handle_text(update, ctx))

    assert [item.conversation_id for item in db.list_outbox_by_status("pending")] == ["A"]
    assert update.message.replies
    assert "تم حفظ طلبك" in update.message.replies[0]
    assert db.update_outcome(99103) == uo.DURABLE_INTENT_RECORDED
    db.close()
