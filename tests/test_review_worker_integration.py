"""R6 integration: a completed R5 cycle prepares and delivers its report."""
from __future__ import annotations

import asyncio
from datetime import datetime

from bot.outbox import _post_claimed
from bot.review.report import ReviewReportService
from bot.review.worker import ReviewRunner, ReviewWorker
from tests.test_auto_review_lifecycle import (
    SHA2,
    T2,
    FakeCollector,
    FakeProvider,
    make_db,
    member,
    provider_binding,
    reserve,
)


class FakeBot:
    def __init__(self):
        self.documents = []

    async def send_document(self, **kwargs):
        self.documents.append(kwargs)
        return object()


def test_r5_runner_with_r6_service_persists_report_before_delivery(tmp_path):
    db = make_db(tmp_path)
    result = reserve(db, (member(1, SHA2),))
    service = ReviewReportService(db, owner_id=7)
    runner = ReviewRunner(
        db,
        FakeProvider(),
        FakeCollector(),
        max_input_chars=20_000,
        clock=lambda: datetime.fromisoformat(T2),
        report_service=service,
        provider_binding=provider_binding(db),
        owner_id=7,
    )
    worker = ReviewWorker(
        db,
        runner,
        owner="worker-1",
        clock=lambda: datetime.fromisoformat(T2),
        report_service=service,
    )
    claim = worker._claim()
    assert claim is not None
    asyncio.run(worker._process(claim))
    cycle = db.get_auto_review(result.review_id)
    assert cycle.lifecycle_state == "delivery_pending"
    report = db.get_auto_review_report(result.review_id, 1)
    assert report is not None
    assert report.verdict == cycle.verdict
    rows = db.get_auto_review_outbox(result.review_id)
    assert len(rows) == 1
    assert rows[0].review_kind == "summary_document"
    assert rows[0].review_version == 1
    assert rows[0].review_report_id == report.id
    item = db.claim_outbox_by_id(rows[0].id, T2)
    bot = FakeBot()
    asyncio.run(_post_claimed(None, db, bot, item, review_owner_id=7))
    assert len(bot.documents) == 1
    assert db.get_outbox(item.id).status == "sent"
    assert db.get_auto_review(result.review_id).delivery_state == "sent"
