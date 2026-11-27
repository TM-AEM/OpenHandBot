"""R7 F-02: ReviewRunner must enforce the immutable cycle provider binding."""

from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace

import pytest

from bot.review.llm import ProviderBinding, ProviderSnapshot
from bot.review.worker import ReviewPipelineError, ReviewRunner
from tests.test_auto_review_lifecycle import (
    T0,
    T2,
    FakeCollector,
    FakeProvider,
    make_db,
    member,
    reserve,
    snapshot,
)

KEY = "sk-reviewer-BINDING-SENTINEL-123456"
SHA2 = "b" * 40


def valid_binding(db):
    snap = snapshot(db)
    config = SimpleNamespace(
        reviewer_provider=snap.provider,
        reviewer_api_base=snap.api_base,
        reviewer_model=snap.model,
        reviewer_api_key=KEY,
    )
    return ProviderBinding.from_config(config, snap)


def runner(db, binding, provider=None, collector=None):
    return ReviewRunner(
        db,
        provider or FakeProvider(),
        collector or FakeCollector(),
        max_input_chars=20_000,
        clock=lambda: datetime.fromisoformat(T2),
        provider_binding=binding,
        owner_id=7,
    )


def claimed(db):
    result = reserve(db, (member(1, SHA2),))
    claim = db.claim_auto_review(owner="worker", now=T0)
    assert claim is not None
    return result, claim


def test_valid_binding_runs_and_provider_is_called(tmp_path):
    db = make_db(tmp_path)
    result, claim = claimed(db)
    provider = FakeProvider()
    collector = FakeCollector()
    asyncio.run(runner(db, valid_binding(db), provider, collector).run(claim))
    assert provider.calls == ["blind", "adversarial"]
    assert collector.calls == [1]
    assert db.get_auto_review(result.review_id).verdict == "PASS"


def test_missing_binding_fails_before_provider_or_collector(tmp_path):
    db = make_db(tmp_path)
    _result, claim = claimed(db)
    provider = FakeProvider()
    collector = FakeCollector()
    with pytest.raises(ReviewPipelineError) as info:
        asyncio.run(runner(db, None, provider, collector).run(claim))
    assert info.value.code == "provider_binding_required"
    assert provider.calls == []
    assert collector.calls == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("provider", "other-provider"),
        ("api_base", "https://other.invalid/v1"),
        ("model", "other-model"),
        ("config_fingerprint", "0" * 64),
    ],
)
def test_changed_snapshot_fields_are_rejected_without_provider_calls(tmp_path, field, value):
    db = make_db(tmp_path)
    _result, claim = claimed(db)
    base = valid_binding(db).snapshot
    bad = ProviderSnapshot(
        provider=value if field == "provider" else base.provider,
        api_base=value if field == "api_base" else base.api_base,
        model=value if field == "model" else base.model,
        config_fingerprint=value if field == "config_fingerprint" else base.config_fingerprint,
        settings=base.settings,
        snapshot_id=base.snapshot_id,
    )
    provider = FakeProvider()
    collector = FakeCollector()
    with pytest.raises(ReviewPipelineError) as info:
        asyncio.run(
            runner(db, ProviderBinding(bad, KEY), provider, collector).run(claim)
        )
    assert info.value.code == "provider_binding_mismatch"
    assert provider.calls == []
    assert collector.calls == []
    assert KEY not in str(info.value)


def test_binding_from_another_cycle_is_rejected(tmp_path):
    db = make_db(tmp_path)
    first = reserve(db, (member(1, SHA2),))
    first_claim = db.claim_auto_review(owner="worker", now=T0)
    assert first_claim is not None
    other_snap = db.get_or_create_auto_review_provider_snapshot(
        provider="testprovider",
        api_base="https://reviewer.invalid/v1",
        model="model-b",
        config={"max_input_chars": 20000},
        now=T0,
    )
    db.add_watched("conv-2", "test conversation", 7)
    second = db.reserve_conversation_review(
        conversation_id="conv-2",
        chat_id=7,
        memberships=(member(2, SHA2),),
        provider_snapshot_id=other_snap.id,
        reserved_by="test",
        implementation_report="implementation report",
        now=T0,
    )
    second_claim = db.claim_auto_review(owner="worker", now=T0)
    assert second_claim is not None
    provider = FakeProvider()
    collector = FakeCollector()
    with pytest.raises(ReviewPipelineError) as info:
        asyncio.run(
            runner(db, valid_binding(db), provider, collector).run(second_claim)
        )
    assert info.value.code == "provider_binding_mismatch"
    assert provider.calls == []
    assert collector.calls == []
    assert db.get_auto_review(first.review_id) is not None
    assert db.get_auto_review(second.review_id) is not None


def test_binding_with_same_content_but_another_snapshot_id_is_rejected(tmp_path):
    db = make_db(tmp_path)
    _result, claim = claimed(db)
    base = valid_binding(db).snapshot
    other_id = ProviderBinding(
        ProviderSnapshot(
            provider=base.provider,
            api_base=base.api_base,
            model=base.model,
            config_fingerprint=base.config_fingerprint,
            settings=base.settings,
            snapshot_id=(base.snapshot_id or 0) + 999,
        ),
        KEY,
    )
    provider = FakeProvider()
    collector = FakeCollector()
    with pytest.raises(ReviewPipelineError) as info:
        asyncio.run(runner(db, other_id, provider, collector).run(claim))
    assert info.value.code == "provider_binding_cycle_mismatch"
    assert provider.calls == []
    assert collector.calls == []


def test_binding_without_snapshot_id_cannot_prove_cycle_association(tmp_path):
    db = make_db(tmp_path)
    _result, claim = claimed(db)
    base = valid_binding(db).snapshot
    unassociated = ProviderBinding(
        ProviderSnapshot(
            provider=base.provider,
            api_base=base.api_base,
            model=base.model,
            config_fingerprint=base.config_fingerprint,
            settings=base.settings,
            snapshot_id=None,
        ),
        KEY,
    )
    provider = FakeProvider()
    with pytest.raises(ReviewPipelineError) as info:
        asyncio.run(runner(db, unassociated, provider, FakeCollector()).run(claim))
    assert info.value.code == "provider_binding_cycle_mismatch"
    assert provider.calls == []


def test_adapter_binding_mismatch_is_rejected(tmp_path):
    db = make_db(tmp_path)
    _result, claim = claimed(db)
    valid = valid_binding(db)
    base = valid.snapshot
    other = ProviderBinding(
        ProviderSnapshot(
            provider=base.provider,
            api_base=base.api_base,
            model=base.model,
            config_fingerprint="f" * 64,
            settings=base.settings,
            snapshot_id=base.snapshot_id,
        ),
        KEY,
    )
    provider = FakeProvider()
    provider.binding = other
    with pytest.raises(ReviewPipelineError) as info:
        asyncio.run(runner(db, valid, provider, FakeCollector()).run(claim))
    assert info.value.code == "provider_adapter_binding_mismatch"
    assert provider.calls == []


def test_mismatch_does_not_mutate_the_immutable_snapshot(tmp_path):
    db = make_db(tmp_path)
    _result, claim = claimed(db)
    snap = snapshot(db)
    before = db.get_auto_review_provider_snapshot(snap.id)
    base = valid_binding(db).snapshot
    bad = ProviderBinding(
        ProviderSnapshot(
            provider=base.provider,
            api_base=base.api_base,
            model="other-model",
            config_fingerprint=base.config_fingerprint,
            settings=base.settings,
            snapshot_id=base.snapshot_id,
        ),
        KEY,
    )
    with pytest.raises(ReviewPipelineError):
        asyncio.run(runner(db, bad, FakeProvider(), FakeCollector()).run(claim))
    after = db.get_auto_review_provider_snapshot(snap.id)
    assert before == after
