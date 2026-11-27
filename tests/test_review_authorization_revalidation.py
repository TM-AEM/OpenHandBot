"""WP-01 D-03 current-owner revalidation tests (local, fake transport only)."""
from __future__ import annotations

import asyncio
import dataclasses
import sqlite3
from datetime import datetime

import pytest

from bot.db import (
    AUTO_REVIEW_LIFECYCLE_DELIVERY_PENDING,
    AUTO_REVIEW_LIFECYCLE_RETRY_WAIT,
    AutoReviewLeaseLost,
)
from bot.outbox import _post_claimed
from bot.review.report import ReviewReportError, ReviewReportService
from bot.review.worker import ReviewPipelineError, ReviewRunner, ReviewWorker
from tests._review_r6_helpers import (
    SHA2,
    T2 as R6_T2,
    make_db as r6_make_db,
    member as r6_member,
    seed_completed_cycle,
)
from tests.test_auto_review_lifecycle import (
    FakeCollector,
    FakeProvider,
    T1,
    T2,
    evid,
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


def _cycle(db, *, conv="conv-1", chat=7):
    result = reserve(db, (member(1, SHA2),), conv=conv, chat=chat)
    assert result.review_id is not None
    return result.review_id


def _claim(db, review_id, *, now=T1):
    claim = db.claim_auto_review(owner="worker", now=now)
    assert claim is not None
    assert claim.review_id == review_id
    return claim


def _runner(db, *, owner=7, provider=None, collector=None):
    return ReviewRunner(
        db,
        provider or FakeProvider(),
        collector or FakeCollector(),
        max_input_chars=20_000,
        clock=lambda: datetime.fromisoformat(T2),
        provider_binding=provider_binding(db),
        owner_id=owner,
    )


def _run(db, claim, *, owner=7, provider=None, collector=None):
    provider = provider or FakeProvider()
    collector = collector or FakeCollector()
    runner = _runner(db, owner=owner, provider=provider, collector=collector)
    worker = ReviewWorker(db, runner, owner="worker", clock=lambda: datetime.fromisoformat(T2))
    asyncio.run(worker._process(claim))
    return provider, collector


def _set_watched(db, conv="conv-1", chat=7):
    db._conn.execute("UPDATE watched SET chat_id=? WHERE conversation_id=?", (chat, conv))
    db._conn.commit()


def _delete_watched(db, conv="conv-1"):
    db._conn.execute("DELETE FROM watched WHERE conversation_id=?", (conv,))
    db._conn.commit()


def _delete_conversation(db, conv="conv-1"):
    db._conn.execute(
        "INSERT OR REPLACE INTO deleted_conversations(conversation_id, deleted_at) "
        "VALUES(?, ?)",
        (conv, T2),
    )
    db._conn.commit()


def _delivery_cycle(tmp_path, *, chat=7):
    db = r6_make_db(tmp_path)
    review_id = seed_completed_cycle(db, (r6_member(1, SHA2),), chat=chat)
    service = ReviewReportService(db, owner_id=chat)
    report = service.prepare(review_id, now=R6_T2)
    return db, review_id, report


def _claim_outbox(db, review_id):
    rows = db.get_auto_review_outbox(review_id)
    assert len(rows) == 1
    item = db.claim_outbox_by_id(rows[0].id, R6_T2)
    assert item is not None
    return item


# Owner identity -----------------------------------------------------------


def test_current_configured_owner_is_accepted(tmp_path):
    db = make_db(tmp_path)
    review_id = _cycle(db)
    claim = _claim(db, review_id)
    provider, collector = _run(db, claim, owner=7)
    assert provider.calls == ["blind", "adversarial"]
    assert collector.calls == [1]
    assert db.get_auto_review(review_id).verdict == "PASS"


def test_owner_change_after_cycle_creation_blocks_execution(tmp_path):
    db = make_db(tmp_path)
    review_id = _cycle(db)
    claim = _claim(db, review_id)
    provider, _ = _run(db, claim, owner=8)
    cycle = db.get_auto_review(review_id)
    assert provider.calls == []
    assert cycle.error_class == "review_owner_chat_mismatch"
    assert cycle.lifecycle_state == AUTO_REVIEW_LIFECYCLE_DELIVERY_PENDING


def test_missing_owner_configuration_fails_closed(tmp_path):
    db = make_db(tmp_path)
    review_id = _cycle(db)
    claim = _claim(db, review_id)
    provider, _ = _run(db, claim, owner=None)
    cycle = db.get_auto_review(review_id)
    assert provider.calls == []
    assert cycle.error_class == "owner_config_missing"


def test_malformed_owner_configuration_fails_closed(tmp_path):
    db = make_db(tmp_path)
    review_id = _cycle(db)
    claim = _claim(db, review_id)
    provider, _ = _run(db, claim, owner="7")
    cycle = db.get_auto_review(review_id)
    assert provider.calls == []
    assert cycle.error_class == "owner_config_malformed"


def test_stored_cycle_owner_differs_from_current_owner(tmp_path):
    db = make_db(tmp_path)
    review_id = _cycle(db, chat=8)
    claim = _claim(db, review_id)
    provider, _ = _run(db, claim, owner=7)
    cycle = db.get_auto_review(review_id)
    assert provider.calls == []
    assert cycle.error_class == "review_owner_chat_mismatch"


def test_stale_authorization_cannot_bypass_revalidation(tmp_path):
    db = make_db(tmp_path)
    review_id = _cycle(db)
    claim = _claim(db, review_id)
    runner = _runner(db)
    runner._authorize(claim)  # stale success must not be cached
    _set_watched(db, chat=8)
    with pytest.raises(ReviewPipelineError) as info:
        runner._authorize(claim)
    assert info.value.code == "review_watched_owner_mismatch"
    assert db.get_auto_review(review_id).verdict is None


# Telegram chat ------------------------------------------------------------


def test_authorized_private_owner_chat_delivers(tmp_path):
    db, review_id, _report = _delivery_cycle(tmp_path)
    item = _claim_outbox(db, review_id)
    bot = FakeBot()
    asyncio.run(_post_claimed(None, db, bot, item, review_owner_id=7))
    assert len(bot.documents) == 1
    assert db.get_outbox(item.id).status == "sent"


@pytest.mark.parametrize("target", [-1001234567890, -1009876543210])
def test_group_and_channel_targets_are_rejected(tmp_path, target):
    db, review_id, _report = _delivery_cycle(tmp_path)
    item = _claim_outbox(db, review_id)
    db._conn.execute("UPDATE outbox SET chat_id=? WHERE id=?", (target, item.id))
    db._conn.commit()
    item = db.get_outbox(item.id)
    bot = FakeBot()
    asyncio.run(_post_claimed(None, db, bot, item, review_owner_id=7))
    assert bot.documents == []
    assert db.get_outbox(item.id).status == "failed"
    assert db.get_auto_review(review_id).delivery_state == "failed"


def test_wrong_private_chat_target_is_rejected(tmp_path):
    db, review_id, _report = _delivery_cycle(tmp_path)
    item = _claim_outbox(db, review_id)
    db._conn.execute("UPDATE outbox SET chat_id=8 WHERE id=?", (item.id,))
    db._conn.commit()
    item = db.get_outbox(item.id)
    bot = FakeBot()
    asyncio.run(_post_claimed(None, db, bot, item, review_owner_id=7))
    assert bot.documents == []
    assert db.get_outbox(item.id).status == "failed"


def test_watched_chat_mismatch_is_rejected(tmp_path):
    db, review_id, _report = _delivery_cycle(tmp_path)
    _set_watched(db, chat=8)
    item = _claim_outbox(db, review_id)
    bot = FakeBot()
    asyncio.run(_post_claimed(None, db, bot, item, review_owner_id=7))
    assert bot.documents == []
    assert db.get_outbox(item.id).status == "failed"
    assert db.get_auto_review(review_id).error_class is None


def test_cycle_chat_mismatch_is_rejected(tmp_path):
    db, review_id, _report = _delivery_cycle(tmp_path)
    db._conn.execute("UPDATE auto_reviews SET chat_id=8 WHERE id=?", (review_id,))
    db._conn.commit()
    item = _claim_outbox(db, review_id)
    bot = FakeBot()
    asyncio.run(_post_claimed(None, db, bot, item, review_owner_id=7))
    assert bot.documents == []
    assert db.get_outbox(item.id).status == "failed"


def test_outbox_conversation_mismatch_is_rejected(tmp_path):
    db, review_id, _report = _delivery_cycle(tmp_path)
    item = _claim_outbox(db, review_id)
    db._conn.execute(
        "UPDATE outbox SET conversation_id='conv-other' WHERE id=?", (item.id,)
    )
    db._conn.commit()
    item = db.get_outbox(item.id)
    bot = FakeBot()
    asyncio.run(_post_claimed(None, db, bot, item, review_owner_id=7))
    assert bot.documents == []
    assert db.get_outbox(item.id).status == "failed"


def test_actual_delivery_target_mismatch_is_rejected(tmp_path):
    db, review_id, _report = _delivery_cycle(tmp_path)
    item = _claim_outbox(db, review_id)
    db._conn.execute("UPDATE outbox SET chat_id=9 WHERE id=?", (item.id,))
    db._conn.commit()
    item = db.get_outbox(item.id)
    bot = FakeBot()
    asyncio.run(_post_claimed(None, db, bot, item, review_owner_id=7))
    assert bot.documents == []
    assert db.get_outbox(item.id).status == "failed"


# Conversation state -------------------------------------------------------


def test_deleted_conversation_before_blind_blocks_execution(tmp_path):
    db = make_db(tmp_path)
    review_id = _cycle(db)
    claim = _claim(db, review_id)
    _delete_conversation(db)
    provider, collector = _run(db, claim)
    assert provider.calls == []
    assert collector.calls == []
    assert db.get_auto_review(review_id).error_class == "review_conversation_deleted"


def test_deleted_conversation_between_blind_and_adversarial_blocks_stage(tmp_path):
    db = make_db(tmp_path)
    review_id = _cycle(db)
    claim = _claim(db, review_id)
    runner = _runner(db)
    cycle = db.get_auto_review(review_id)
    membership = db.get_auto_review_memberships(review_id)[0]
    evidence = evid(membership)
    blind, blind_validation = asyncio.run(runner._blind(claim, cycle, membership, evidence))
    _delete_conversation(db)
    with pytest.raises(ReviewPipelineError) as info:
        asyncio.run(
            runner._adversarial(claim, cycle, membership, evidence, blind, blind_validation)
        )
    assert info.value.code == "review_conversation_deleted"
    assert runner._provider.calls == ["blind"]


def test_conversation_ownership_change_before_stage_blocks_stage(tmp_path):
    db = make_db(tmp_path)
    review_id = _cycle(db)
    claim = _claim(db, review_id)
    _set_watched(db, chat=8)
    runner = _runner(db)
    cycle = db.get_auto_review(review_id)
    membership = db.get_auto_review_memberships(review_id)[0]
    with pytest.raises(ReviewPipelineError) as info:
        asyncio.run(runner._blind(claim, cycle, membership, evid(membership)))
    assert info.value.code == "review_watched_owner_mismatch"
    assert runner._provider.calls == []


def test_missing_conversation_record_blocks_execution(tmp_path):
    db = make_db(tmp_path)
    review_id = _cycle(db)
    claim = _claim(db, review_id)
    _delete_watched(db)
    provider, _ = _run(db, claim)
    assert provider.calls == []
    assert db.get_auto_review(review_id).error_class == "review_conversation_not_watched"


def test_database_error_during_ownership_lookup_retries_safely(tmp_path, monkeypatch):
    db = make_db(tmp_path)
    review_id = _cycle(db)
    claim = _claim(db, review_id)

    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("forced ownership read failure")

    monkeypatch.setattr(db, "get_watched", fail)
    provider, _ = _run(db, claim)
    cycle = db.get_auto_review(review_id)
    assert provider.calls == []
    assert cycle.error_class == "review_authorization_database_unavailable"
    assert cycle.lifecycle_state == AUTO_REVIEW_LIFECYCLE_RETRY_WAIT


def test_database_error_during_deletion_lookup_retries_safely(tmp_path, monkeypatch):
    db = make_db(tmp_path)
    review_id = _cycle(db)
    claim = _claim(db, review_id)

    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("forced deletion read failure")

    monkeypatch.setattr(db, "is_deleted_with_retry", fail)
    provider, _ = _run(db, claim)
    cycle = db.get_auto_review(review_id)
    assert provider.calls == []
    assert cycle.error_class == "review_authorization_database_unavailable"
    assert cycle.lifecycle_state == AUTO_REVIEW_LIFECYCLE_RETRY_WAIT


# Resume and delayed execution --------------------------------------------


def test_revocation_before_stage_resume_blocks_provider(tmp_path):
    db = make_db(tmp_path)
    review_id = _cycle(db)
    claim = _claim(db, review_id)
    runner = _runner(db)
    cycle = db.get_auto_review(review_id)
    membership = db.get_auto_review_memberships(review_id)[0]
    evidence = evid(membership)
    asyncio.run(runner._blind(claim, cycle, membership, evidence))
    _set_watched(db, chat=8)
    with pytest.raises(ReviewPipelineError) as info:
        asyncio.run(runner._blind(claim, cycle, membership, evidence))
    assert info.value.code == "review_watched_owner_mismatch"
    assert runner._provider.calls == ["blind"]


def test_owner_change_before_delayed_execution_blocks_provider(tmp_path):
    db = make_db(tmp_path)
    review_id = _cycle(db)
    claim = _claim(db, review_id)
    _set_watched(db, chat=8)
    provider, _ = _run(db, claim)
    assert provider.calls == []
    assert db.get_auto_review(review_id).error_class == "review_watched_owner_mismatch"


def test_stale_claim_cannot_bypass_current_authorization(tmp_path):
    db = make_db(tmp_path)
    review_id = _cycle(db)
    claim = _claim(db, review_id)
    _set_watched(db, chat=8)
    runner = _runner(db)
    with pytest.raises(ReviewPipelineError) as info:
        runner._authorize(claim)
    assert info.value.code == "review_watched_owner_mismatch"


def test_duplicate_or_delayed_stage_attempt_requires_current_authorization(tmp_path):
    db = make_db(tmp_path)
    review_id = _cycle(db)
    claim = _claim(db, review_id)
    runner = _runner(db)
    cycle = db.get_auto_review(review_id)
    membership = db.get_auto_review_memberships(review_id)[0]
    evidence = evid(membership)
    asyncio.run(runner._blind(claim, cycle, membership, evidence))
    _set_watched(db, chat=8)
    with pytest.raises(ReviewPipelineError):
        asyncio.run(runner._blind(claim, cycle, membership, evidence))
    assert runner._provider.calls == ["blind"]


# Delivery -----------------------------------------------------------------


def test_revocation_before_report_claim_blocks_delivery(tmp_path):
    db, review_id, _report = _delivery_cycle(tmp_path)
    _set_watched(db, chat=8)
    item = _claim_outbox(db, review_id)
    bot = FakeBot()
    asyncio.run(_post_claimed(None, db, bot, item, review_owner_id=7))
    assert bot.documents == []
    assert db.get_outbox(item.id).status == "failed"
    assert db.get_outbox(item.id).error == "review_watched_owner_mismatch"
    assert db.get_auto_review(review_id).delivery_state == "failed"
    assert db.get_auto_review(review_id).terminal_reason == "delivery_failed"


def test_revocation_after_claim_before_send_blocks_delivery(tmp_path, monkeypatch):
    db, review_id, _report = _delivery_cycle(tmp_path)
    item = _claim_outbox(db, review_id)
    original = db.get_auto_review_report

    def change_owner(*args, **kwargs):
        result = original(*args, **kwargs)
        _set_watched(db, chat=8)
        return result

    monkeypatch.setattr(db, "get_auto_review_report", change_owner)
    bot = FakeBot()
    asyncio.run(_post_claimed(None, db, bot, item, review_owner_id=7))
    assert bot.documents == []
    assert db.get_outbox(item.id).status == "failed"


def test_revocation_during_delayed_delivery_blocks_delivery(tmp_path):
    db, review_id, _report = _delivery_cycle(tmp_path)
    _set_watched(db, chat=8)
    item = _claim_outbox(db, review_id)
    bot = FakeBot()
    asyncio.run(_post_claimed(None, db, bot, item, review_owner_id=7))
    assert bot.documents == []
    assert db.get_outbox(item.id).status == "failed"


def test_unauthorized_target_never_receives_a_report(tmp_path):
    db, review_id, _report = _delivery_cycle(tmp_path)
    item = _claim_outbox(db, review_id)
    db._conn.execute("UPDATE outbox SET chat_id=8 WHERE id=?", (item.id,))
    db._conn.commit()
    item = db.get_outbox(item.id)
    bot = FakeBot()
    asyncio.run(_post_claimed(None, db, bot, item, review_owner_id=7))
    assert bot.documents == []
    assert db.get_outbox(item.id).status != "sent"


def test_unauthorized_delivery_is_never_marked_sent(tmp_path):
    db, review_id, _report = _delivery_cycle(tmp_path)
    _set_watched(db, chat=8)
    item = _claim_outbox(db, review_id)
    bot = FakeBot()
    asyncio.run(_post_claimed(None, db, bot, item, review_owner_id=7))
    assert db.get_outbox(item.id).status != "sent"
    assert db.get_auto_review(review_id).delivery_state != "sent"
    assert db.get_auto_review(review_id).terminal_reason != "delivered"


def test_authorization_read_failure_does_not_consume_delivery(tmp_path, monkeypatch):
    db, review_id, _report = _delivery_cycle(tmp_path)
    item = _claim_outbox(db, review_id)
    original = db.get_watched

    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("forced read failure")

    monkeypatch.setattr(db, "get_watched", fail)
    bot = FakeBot()
    asyncio.run(_post_claimed(None, db, bot, item, review_owner_id=7))
    assert bot.documents == []
    assert db.get_outbox(item.id).status == "pending"
    assert db.get_auto_review_report(review_id, 1) is not None
    monkeypatch.setattr(db, "get_watched", original)
    reclaimed = db.claim_outbox_by_id(item.id, R6_T2)
    assert reclaimed is not None
    asyncio.run(_post_claimed(None, db, bot, reclaimed, review_owner_id=7))
    assert len(bot.documents) == 1
    assert db.get_outbox(item.id).status == "sent"


def test_revocation_after_send_is_not_marked_sent(tmp_path):
    db, review_id, _report = _delivery_cycle(tmp_path)
    item = _claim_outbox(db, review_id)

    class MutatingBot(FakeBot):
        async def send_document(self, **kwargs):
            self.documents.append(kwargs)
            _set_watched(db, chat=8)
            return object()

    bot = MutatingBot()
    asyncio.run(_post_claimed(None, db, bot, item, review_owner_id=7))
    assert len(bot.documents) == 1
    assert db.get_outbox(item.id).status == "unknown"
    assert db.get_auto_review(review_id).delivery_state == "unknown"


def test_report_generation_requires_current_authorization(tmp_path):
    db = r6_make_db(tmp_path)
    review_id = seed_completed_cycle(db, (r6_member(1, SHA2),), chat=7)
    _set_watched(db, chat=8)
    service = ReviewReportService(db, owner_id=7)
    with pytest.raises(ReviewReportError) as info:
        service.prepare(review_id, now=R6_T2)
    assert info.value.code == "review_watched_owner_mismatch"
    assert db.get_auto_review_report(review_id, 1) is None
    assert db.get_auto_review_outbox(review_id) == ()


def test_authorized_delivery_continues_to_work(tmp_path):
    db, review_id, _report = _delivery_cycle(tmp_path)
    item = _claim_outbox(db, review_id)
    bot = FakeBot()
    asyncio.run(_post_claimed(None, db, bot, item, review_owner_id=7))
    assert len(bot.documents) == 1
    assert db.get_outbox(item.id).status == "sent"
    assert db.get_auto_review(review_id).delivery_state == "sent"


# State and recovery -------------------------------------------------------


def test_authorization_denial_preserves_evidence_and_report(tmp_path):
    db, review_id, _report = _delivery_cycle(tmp_path)
    _set_watched(db, chat=8)
    item = _claim_outbox(db, review_id)
    bot = FakeBot()
    asyncio.run(_post_claimed(None, db, bot, item, review_owner_id=7))
    assert db.get_auto_review_report(review_id, 1) is not None
    assert db._conn.execute(
        "SELECT COUNT(*) FROM auto_review_evidence WHERE review_id=?", (review_id,)
    ).fetchone()[0] == 1
    assert db.get_auto_review(review_id).verdict == "PASS"


def test_retryable_database_failure_preserves_recoverable_work(tmp_path, monkeypatch):
    db, review_id, _report = _delivery_cycle(tmp_path)
    item = _claim_outbox(db, review_id)
    original = db.is_deleted_with_retry

    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("forced deletion read failure")

    monkeypatch.setattr(db, "is_deleted_with_retry", fail)
    bot = FakeBot()
    asyncio.run(_post_claimed(None, db, bot, item, review_owner_id=7))
    assert db.get_outbox(item.id).status == "pending"
    assert db.get_auto_review(review_id).lifecycle_state == AUTO_REVIEW_LIFECYCLE_DELIVERY_PENDING
    monkeypatch.setattr(db, "is_deleted_with_retry", original)
    reclaimed = db.claim_outbox_by_id(item.id, R6_T2)
    assert reclaimed is not None
    asyncio.run(_post_claimed(None, db, bot, reclaimed, review_owner_id=7))
    assert len(bot.documents) == 1


def test_process_restart_does_not_restore_stale_authorization(tmp_path):
    db = make_db(tmp_path)
    review_id = _cycle(db)
    claim = _claim(db, review_id)
    _set_watched(db, chat=8)
    restarted_runner = _runner(db)
    with pytest.raises(ReviewPipelineError) as info:
        restarted_runner._authorize(claim)
    assert info.value.code == "review_watched_owner_mismatch"
    assert restarted_runner._provider.calls == []


def test_lease_fencing_remains_enforced(tmp_path):
    db = make_db(tmp_path)
    review_id = _cycle(db)
    claim = _claim(db, review_id)
    forged = dataclasses.replace(claim, lease_token="forged-token")
    runner = _runner(db)
    cycle = db.get_auto_review(review_id)
    membership = db.get_auto_review_memberships(review_id)[0]
    with pytest.raises(AutoReviewLeaseLost):
        asyncio.run(runner._blind(forged, cycle, membership, evid(membership)))
    assert runner._provider.calls == []


def test_existing_r6_owner_acceptance_still_works(tmp_path):
    db, review_id, report = _delivery_cycle(tmp_path)
    result = db.record_auto_review_owner_decision(review_id, report.version, 7, "ACCEPT")
    assert result.outcome == "recorded"
    assert db.get_auto_review_owner_decision(review_id, report.version, 7) is not None


def test_authorization_failure_is_reported_with_safe_reason(tmp_path):
    db = make_db(tmp_path)
    review_id = _cycle(db)
    claim = _claim(db, review_id)
    provider, _ = _run(db, claim, owner=8)
    cycle = db.get_auto_review(review_id)
    assert provider.calls == []
    assert cycle.error_class == "review_owner_chat_mismatch"
    assert "owner/repo" not in (cycle.error_detail or "")
    assert cycle.error_detail == "review_owner_chat_mismatch"
