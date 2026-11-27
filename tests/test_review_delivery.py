"""R6 outbox-backed Telegram report delivery tests (fake transport only)."""
from __future__ import annotations

import asyncio

import pytest
from telegram.error import BadRequest, TelegramError

from bot.outbox import _post_claimed
from bot.review.report import ReviewReportService
from tests._review_r6_helpers import (
    SHA2,
    T2,
    finding,
    make_db,
    member,
    seed_completed_cycle,
)


class FakeBot:
    def __init__(self, error=None):
        self.error = error
        self.documents = []
        self.messages = []

    async def send_document(self, **kwargs):
        if self.error is not None:
            raise self.error
        self.documents.append(kwargs)
        return object()

    async def send_message(self, *args, **kwargs):
        self.messages.append((args, kwargs))
        return object()


def _prepared_cycle(tmp_path):
    db = make_db(tmp_path)
    review_id = seed_completed_cycle(
        db,
        (member(1, SHA2),),
        blind_findings=[finding("F-1", "high")],
        adversarial_findings=[finding("F-1", "high")],
    )
    service = ReviewReportService(db, owner_id=7)
    report = service.prepare(review_id, now=T2)
    return db, review_id, report


def _claim_first(db, review_id):
    rows = db.get_auto_review_outbox(review_id)
    assert len(rows) == 1
    item = db.claim_outbox_by_id(rows[0].id, T2)
    assert item is not None
    return item


def test_summary_document_delivery_uses_existing_outbox_and_buttons(tmp_path):
    db, review_id, report = _prepared_cycle(tmp_path)
    item = _claim_first(db, review_id)
    assert item.review_kind == "summary_document"
    assert item.review_version == 1
    assert item.review_report_id == report.id
    bot = FakeBot()
    asyncio.run(_post_claimed(None, db, bot, item, review_owner_id=7))
    assert db.get_outbox(item.id).status == "sent"
    assert len(bot.documents) == 1
    assert bot.messages == []
    sent = bot.documents[0]
    assert sent["document"].filename == "review-bbbbbbb.md"
    assert "PASS" in sent["caption"]
    assert "review-bbbbbbb.md" in sent["caption"]
    buttons = sent["reply_markup"].inline_keyboard[0]
    assert [button.text for button in buttons] == ["تفاصيل", "قبول", "رفض"]
    assert all(len(button.callback_data.encode("utf-8")) <= 64 for button in buttons)
    assert all(button.callback_data.startswith("review:") for button in buttons)
    assert "sk-" not in sent["caption"]


def test_duplicate_completion_does_not_send_twice(tmp_path):
    db, review_id, _report = _prepared_cycle(tmp_path)
    item = _claim_first(db, review_id)
    bot = FakeBot()
    asyncio.run(_post_claimed(None, db, bot, item, review_owner_id=7))
    asyncio.run(_post_claimed(None, db, bot, item, review_owner_id=7))
    assert len(bot.documents) == 1
    assert db.get_outbox(item.id).status == "sent"


@pytest.mark.parametrize(
    "error,expected",
    [
        (TelegramError("network"), "unknown"),
        (BadRequest("bad request"), "failed"),
    ],
)
def test_delivery_failure_is_never_marked_sent(tmp_path, error, expected):
    db, review_id, _report = _prepared_cycle(tmp_path)
    item = _claim_first(db, review_id)
    bot = FakeBot(error=error)
    asyncio.run(_post_claimed(None, db, bot, item, review_owner_id=7))
    assert db.get_outbox(item.id).status == expected
    cycle = db.get_auto_review(review_id)
    assert cycle.delivery_state == expected
    assert cycle.terminal_reason != "delivered"


def test_missing_report_fails_closed_without_fabrication(tmp_path):
    db = make_db(tmp_path)
    review_id = seed_completed_cycle(db, (member(1, SHA2),))
    outbox_id = db.schedule_auto_review_delivery(review_id, now=T2)
    db._conn.execute(
        "UPDATE outbox SET review_kind='summary_document' WHERE id=?", (outbox_id,)
    )
    db._conn.commit()
    item = db.claim_outbox_by_id(outbox_id, T2)
    assert item is not None
    bot = FakeBot()
    asyncio.run(_post_claimed(None, db, bot, item, review_owner_id=7))
    assert db.get_outbox(outbox_id).status == "failed"
    assert bot.documents == []
    assert db.get_auto_review(review_id).delivery_state == "failed"


def test_prepare_is_idempotent_and_ensure_pending_recovers(tmp_path):
    db, review_id, report = _prepared_cycle(tmp_path)
    service = ReviewReportService(db, owner_id=7)
    same = service.prepare(review_id, now=T2)
    assert same.id == report.id
    assert len(db.get_auto_review_outbox(review_id)) == 1
    assert db._conn.execute(
        "SELECT count(*) FROM auto_review_reports WHERE review_id=?", (review_id,)
    ).fetchone()[0] == 1
    # Remove the intent only to prove recovery; reports/verdict are untouched.
    db._conn.execute("DELETE FROM outbox WHERE review_id=?", (review_id,))
    db._conn.commit()
    assert service.ensure_pending(now=T2) >= 1
    assert len(db.get_auto_review_outbox(review_id)) == 1


def test_unknown_report_version_does_not_send_latest_report(tmp_path):
    db, review_id, _report = _prepared_cycle(tmp_path)
    item = _claim_first(db, review_id)
    # Simulate an old/forged intent pointing at a version that is not persisted.
    db._conn.execute(
        "UPDATE outbox SET review_version=2 WHERE id=?", (item.id,)
    )
    db._conn.commit()
    item = db.get_outbox(item.id)
    bot = FakeBot()
    asyncio.run(_post_claimed(None, db, bot, item, review_owner_id=7))
    assert db.get_outbox(item.id).status == "failed"
    assert bot.documents == []


def test_missing_review_version_fails_closed(tmp_path):
    db, review_id, _report = _prepared_cycle(tmp_path)
    item = _claim_first(db, review_id)
    db._conn.execute("UPDATE outbox SET review_version=NULL WHERE id=?", (item.id,))
    db._conn.commit()
    item = db.get_outbox(item.id)
    bot = FakeBot()
    asyncio.run(_post_claimed(None, db, bot, item, review_owner_id=7))
    assert db.get_outbox(item.id).status == "failed"
    assert bot.documents == []
