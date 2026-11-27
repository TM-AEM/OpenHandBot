"""OHB2-AUTO-REVIEW-R2: SQLite auto_reviews schema, snapshots, and atomic reservation."""

from __future__ import annotations

import sqlite3
import threading

import pytest

from bot.config import load_config
from bot.db import (
    AUTO_REVIEW_RESERVATION_ALREADY,
    AUTO_REVIEW_RESERVATION_CONFLICT,
    AUTO_REVIEW_RESERVATION_INVALID,
    AUTO_REVIEW_RESERVATION_NEW,
    AUTO_REVIEW_SCOPE_CONVERSATION,
    AUTO_REVIEW_SCOPE_PER_PR,
    Database,
    build_auto_review_reservation_key,
)

SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40
REVIEWER_KEY = "sk-reviewer-test-SENTINEL-123456"
GITHUB_TOKEN = "ghp_review_SENTINEL_123456"


def make_db(tmp_path):
    return Database(str(tmp_path / "auto.sqlite3"))


def make_snapshot(db, model="model-a", config=None):
    return db.get_or_create_auto_review_provider_snapshot(
        provider="testprovider",
        api_base="https://reviewer.invalid/v1",
        model=model,
        config=config if config is not None else {"max_input_chars": 1000},
        now="2026-11-24T00:00:00+00:00",
    )


def reserve(
    db,
    *,
    key,
    snapshot_id,
    conversation_id="conv-1",
    repository_id=123,
    repository_full_name="Owner/Repo",
    head_sha=SHA_A,
    scope=AUTO_REVIEW_SCOPE_CONVERSATION,
    pr_number=None,
    branch="agent/x",
    base_sha=SHA_B,
    rounds=0,
    reserved_by="test",
):
    return db.reserve_auto_review(
        reservation_key=key,
        conversation_id=conversation_id,
        repository_id=repository_id,
        repository_full_name=repository_full_name,
        head_sha=head_sha,
        scope=scope,
        pr_number=pr_number,
        branch=branch,
        base_sha=base_sha,
        provider_snapshot_id=snapshot_id,
        reserved_by=reserved_by,
        rounds=rounds,
        now="2026-11-24T00:00:00+00:00",
    )


def conversation_key(conversation_id="conv-1", head_sha=SHA_A):
    return build_auto_review_reservation_key(
        scope=AUTO_REVIEW_SCOPE_CONVERSATION,
        conversation_id=conversation_id,
        repository_id=123,
        head_sha=head_sha,
    )


def per_pr_key(pr_number=1, head_sha=SHA_A, conversation_id="conv-1"):
    return build_auto_review_reservation_key(
        scope=AUTO_REVIEW_SCOPE_PER_PR,
        conversation_id=conversation_id,
        repository_id=123,
        pr_number=pr_number,
        head_sha=head_sha,
    )


def test_schema_created_and_initialization_is_idempotent(tmp_path):
    path = tmp_path / "auto.sqlite3"
    db = Database(str(path))
    tables = {
        row[0]
        for row in db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'auto_review%'"
        )
    }
    assert {"auto_reviews", "auto_review_provider_snapshots"} <= tables
    snap = make_snapshot(db)
    result = reserve(db, key=conversation_key(), snapshot_id=snap.id)
    assert result.outcome == AUTO_REVIEW_RESERVATION_NEW
    before = db._conn.execute(
        "SELECT count(*) FROM sqlite_master WHERE name LIKE 'auto_review%' "
        "OR name LIKE 'ux_auto_reviews%' OR name LIKE 'trg_auto_review%'"
    ).fetchone()[0]
    db._conn.close()

    db2 = Database(str(path))
    after = db2._conn.execute(
        "SELECT count(*) FROM sqlite_master WHERE name LIKE 'auto_review%' "
        "OR name LIKE 'ux_auto_reviews%' OR name LIKE 'trg_auto_review%'"
    ).fetchone()[0]
    assert before == after
    assert db2._conn.execute("SELECT count(*) FROM auto_reviews").fetchone()[0] == 1
    assert db2.get_auto_review(result.review_id).head_sha == SHA_A


def test_existing_database_and_unrelated_rows_are_preserved(tmp_path):
    path = tmp_path / "existing.sqlite3"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE unrelated (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute("INSERT INTO unrelated(value) VALUES ('keep')")
    conn.commit()
    conn.close()

    db = Database(str(path))
    snap = make_snapshot(db)
    result = reserve(db, key=conversation_key(), snapshot_id=snap.id)
    assert result.outcome == AUTO_REVIEW_RESERVATION_NEW
    assert db._conn.execute("SELECT value FROM unrelated").fetchone()[0] == "keep"
    assert db.get_auto_review(result.review_id) is not None


def test_snapshot_is_idempotent_and_immutable(tmp_path):
    db = make_db(tmp_path)
    first = make_snapshot(db, model="model-a")
    second = make_snapshot(db, model="model-a")
    assert first.id == second.id
    assert first.config_fingerprint == second.config_fingerprint

    with pytest.raises(sqlite3.IntegrityError):
        db._conn.execute(
            "UPDATE auto_review_provider_snapshots SET model='model-b' WHERE id=?",
            (first.id,),
        )
    db._conn.rollback()
    with pytest.raises(sqlite3.IntegrityError):
        db._conn.execute("DELETE FROM auto_review_provider_snapshots WHERE id=?", (first.id,))
    db._conn.rollback()
    assert db.get_auto_review_provider_snapshot(first.id).model == "model-a"


def test_provider_model_changes_affect_new_cycles_only(tmp_path):
    path = tmp_path / "auto.sqlite3"
    db = Database(str(path))
    snap_a = make_snapshot(db, model="model-a")
    r1 = reserve(
        db,
        key=conversation_key("conv-a"),
        snapshot_id=snap_a.id,
        conversation_id="conv-a",
    )
    snap_b = make_snapshot(db, model="model-b")
    r2 = reserve(
        db,
        key=conversation_key("conv-b"),
        snapshot_id=snap_b.id,
        conversation_id="conv-b",
    )

    assert r1.outcome == AUTO_REVIEW_RESERVATION_NEW
    assert r2.outcome == AUTO_REVIEW_RESERVATION_NEW
    assert snap_a.id != snap_b.id
    assert db.get_auto_review(r1.review_id).provider_snapshot_id == snap_a.id
    assert db.get_auto_review(r2.review_id).provider_snapshot_id == snap_b.id
    assert db.get_auto_review_provider_snapshot(snap_a.id).model == "model-a"
    db._conn.close()

    reopened = Database(str(path))
    assert reopened.get_auto_review(r1.review_id).provider_snapshot_id == snap_a.id
    assert reopened.get_auto_review_provider_snapshot(snap_a.id).model == "model-a"


def test_duplicate_event_is_idempotent_and_identity_conflict_is_rejected(tmp_path):
    db = make_db(tmp_path)
    snap = make_snapshot(db)
    key = conversation_key()
    first = reserve(db, key=key, snapshot_id=snap.id)
    duplicate = reserve(db, key=key, snapshot_id=snap.id)
    conflict = reserve(db, key=key, snapshot_id=snap.id, head_sha=SHA_C)

    assert first.outcome == AUTO_REVIEW_RESERVATION_NEW
    assert duplicate.outcome == AUTO_REVIEW_RESERVATION_ALREADY
    assert duplicate.existing_id == first.review_id
    assert conflict.outcome == AUTO_REVIEW_RESERVATION_CONFLICT
    assert conflict.existing_id == first.review_id
    assert db._conn.execute("SELECT count(*) FROM auto_reviews").fetchone()[0] == 1


def test_repository_name_snapshot_does_not_break_idempotency(tmp_path):
    db = make_db(tmp_path)
    snap = make_snapshot(db)
    first = reserve(
        db,
        key=conversation_key(),
        snapshot_id=snap.id,
        repository_full_name="Owner/Old",
    )
    renamed = reserve(
        db,
        key=conversation_key(),
        snapshot_id=snap.id,
        repository_full_name="Owner/New",
    )
    assert first.outcome == AUTO_REVIEW_RESERVATION_NEW
    assert renamed.outcome == AUTO_REVIEW_RESERVATION_ALREADY
    assert renamed.existing_id == first.review_id
    assert db.get_auto_review(first.review_id).repository_full_name == "Owner/Old"


def test_conversation_scope_blocks_second_active_cycle_and_terminal_releases(tmp_path):
    db = make_db(tmp_path)
    snap = make_snapshot(db)
    first = reserve(db, key=conversation_key(head_sha=SHA_A), snapshot_id=snap.id)
    second = reserve(db, key=conversation_key(head_sha=SHA_C), snapshot_id=snap.id)

    assert first.outcome == AUTO_REVIEW_RESERVATION_NEW
    assert second.outcome == AUTO_REVIEW_RESERVATION_CONFLICT
    assert db._conn.execute("SELECT count(*) FROM auto_reviews").fetchone()[0] == 1

    db._conn.execute(
        "UPDATE auto_reviews SET status='terminal', terminal_reason='test' WHERE id=?",
        (first.review_id,),
    )
    db._conn.commit()
    third = reserve(db, key=conversation_key(head_sha=SHA_C), snapshot_id=snap.id)
    assert third.outcome == AUTO_REVIEW_RESERVATION_NEW
    assert db._conn.execute("SELECT count(*) FROM auto_reviews").fetchone()[0] == 2


def test_mixed_scopes_are_rejected_for_same_conversation(tmp_path):
    db = make_db(tmp_path)
    snap = make_snapshot(db)
    conversation = reserve(
        db,
        key=conversation_key(),
        snapshot_id=snap.id,
        scope=AUTO_REVIEW_SCOPE_CONVERSATION,
    )
    mixed = reserve(
        db,
        key=per_pr_key(pr_number=1),
        snapshot_id=snap.id,
        scope=AUTO_REVIEW_SCOPE_PER_PR,
        pr_number=1,
    )
    assert conversation.outcome == AUTO_REVIEW_RESERVATION_NEW
    assert mixed.outcome == AUTO_REVIEW_RESERVATION_CONFLICT
    assert mixed.existing_id == conversation.review_id

    db._conn.execute(
        "UPDATE auto_reviews SET status='terminal', terminal_reason='test' WHERE id=?",
        (conversation.review_id,),
    )
    db._conn.commit()
    allowed = reserve(
        db,
        key=per_pr_key(pr_number=1),
        snapshot_id=snap.id,
        scope=AUTO_REVIEW_SCOPE_PER_PR,
        pr_number=1,
    )
    assert allowed.outcome == AUTO_REVIEW_RESERVATION_NEW


def test_per_pr_scope_allows_distinct_prs_but_blocks_same_pr(tmp_path):
    db = make_db(tmp_path)
    snap = make_snapshot(db)
    first = reserve(
        db,
        key=per_pr_key(pr_number=1, head_sha=SHA_A),
        snapshot_id=snap.id,
        scope=AUTO_REVIEW_SCOPE_PER_PR,
        pr_number=1,
    )
    second = reserve(
        db,
        key=per_pr_key(pr_number=2, head_sha=SHA_A),
        snapshot_id=snap.id,
        scope=AUTO_REVIEW_SCOPE_PER_PR,
        pr_number=2,
    )
    conflict = reserve(
        db,
        key=per_pr_key(pr_number=1, head_sha=SHA_C),
        snapshot_id=snap.id,
        scope=AUTO_REVIEW_SCOPE_PER_PR,
        pr_number=1,
    )

    assert first.outcome == AUTO_REVIEW_RESERVATION_NEW
    assert second.outcome == AUTO_REVIEW_RESERVATION_NEW
    assert conflict.outcome == AUTO_REVIEW_RESERVATION_CONFLICT
    assert db._conn.execute("SELECT count(*) FROM auto_reviews").fetchone()[0] == 2


@pytest.mark.parametrize(
    "over",
    [
        {"head_sha": "bad"},
        {"repository_id": 0},
        {"conversation_id": ""},
        {"scope": AUTO_REVIEW_SCOPE_PER_PR, "pr_number": None},
        {"repository_full_name": "bad"},
        {"key": ""},
        {"rounds": -1},
        {"scope": "unknown"},
    ],
)
def test_invalid_inputs_are_rejected_without_writes(tmp_path, over):
    db = make_db(tmp_path)
    snap = make_snapshot(db)
    params = {
        "key": conversation_key(),
        "snapshot_id": snap.id,
        "conversation_id": "conv-1",
        "repository_id": 123,
        "repository_full_name": "Owner/Repo",
        "head_sha": SHA_A,
        "scope": AUTO_REVIEW_SCOPE_CONVERSATION,
        "pr_number": None,
        "rounds": 0,
    }
    params.update(over)
    result = reserve(db, **params)
    assert result.outcome == AUTO_REVIEW_RESERVATION_INVALID
    assert db._conn.execute("SELECT count(*) FROM auto_reviews").fetchone()[0] == 0


def test_missing_provider_snapshot_is_invalid(tmp_path):
    db = make_db(tmp_path)
    result = reserve(db, key=conversation_key(), snapshot_id=999)
    assert result.outcome == AUTO_REVIEW_RESERVATION_INVALID
    assert db._conn.execute("SELECT count(*) FROM auto_reviews").fetchone()[0] == 0


def test_transaction_rollback_leaves_no_partial_review(tmp_path):
    db = make_db(tmp_path)
    snap = make_snapshot(db)
    db._conn.execute(
        "CREATE TRIGGER fail_auto_review_insert BEFORE INSERT ON auto_reviews "
        "BEGIN SELECT RAISE(ABORT, 'forced failure'); END;"
    )
    db._conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        reserve(db, key=conversation_key(), snapshot_id=snap.id)
    assert db._conn.execute("SELECT count(*) FROM auto_reviews").fetchone()[0] == 0

    db._conn.execute("DROP TRIGGER fail_auto_review_insert")
    db._conn.commit()
    result = reserve(db, key=conversation_key(), snapshot_id=snap.id)
    assert result.outcome == AUTO_REVIEW_RESERVATION_NEW


def _run_concurrently(first, second):
    barrier = threading.Barrier(2)
    results = []
    errors = []

    def run(fn):
        try:
            barrier.wait(timeout=10)
            results.append(fn())
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [
        threading.Thread(target=run, args=(first,)),
        threading.Thread(target=run, args=(second,)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert all(not thread.is_alive() for thread in threads)
    assert not errors, errors
    return results


def test_concurrent_same_key_one_new_one_already(tmp_path):
    path = str(tmp_path / "auto.sqlite3")
    db1 = Database(path)
    db2 = Database(path)
    snap = make_snapshot(db1)
    key = conversation_key()
    results = _run_concurrently(
        lambda: reserve(db1, key=key, snapshot_id=snap.id),
        lambda: reserve(db2, key=key, snapshot_id=snap.id),
    )
    assert sorted(result.outcome for result in results) == [
        AUTO_REVIEW_RESERVATION_ALREADY,
        AUTO_REVIEW_RESERVATION_NEW,
    ]
    assert db1._conn.execute("SELECT count(*) FROM auto_reviews").fetchone()[0] == 1


def test_concurrent_different_keys_conversation_scope_one_new_one_conflict(tmp_path):
    path = str(tmp_path / "auto.sqlite3")
    db1 = Database(path)
    db2 = Database(path)
    snap = make_snapshot(db1)
    results = _run_concurrently(
        lambda: reserve(db1, key=conversation_key(head_sha=SHA_A), snapshot_id=snap.id),
        lambda: reserve(db2, key=conversation_key(head_sha=SHA_C), snapshot_id=snap.id),
    )
    assert sorted(result.outcome for result in results) == [
        AUTO_REVIEW_RESERVATION_CONFLICT,
        AUTO_REVIEW_RESERVATION_NEW,
    ]
    assert db1._conn.execute("SELECT count(*) FROM auto_reviews").fetchone()[0] == 1


def test_no_plaintext_credentials_persisted(tmp_path):
    env = {
        "TELEGRAM_BOT_TOKEN": "123456:ABCdef-ghiJKL_mnoPQR",
        "OPENHANDS_API_KEY": "sk-oh-test-key-123456",
        "ALLOWED_TELEGRAM_ID": "1",
        "REVIEW_ENABLED": "1",
        "REVIEW_REPOS": "Owner/Repo",
        "REVIEWER_PROVIDER": "testprovider",
        "REVIEWER_API_BASE": "https://reviewer.invalid/v1",
        "REVIEWER_API_KEY": REVIEWER_KEY,
        "REVIEWER_MODEL": "reviewer-model-v1",
        "REVIEW_GITHUB_TOKEN": GITHUB_TOKEN,
    }
    cfg = load_config(env)
    path = tmp_path / "auto.sqlite3"
    db = Database(str(path))
    snap = db.get_or_create_auto_review_provider_snapshot(
        provider=cfg.reviewer_provider,
        api_base=cfg.reviewer_api_base,
        model=cfg.reviewer_model,
        config={
            "max_input_chars": cfg.review_max_input_chars,
            "ci_timeout_min": cfg.review_ci_timeout_min,
            "autofix_rounds": cfg.review_autofix_rounds,
        },
    )
    result = reserve(db, key=conversation_key(), snapshot_id=snap.id)
    assert result.outcome == AUTO_REVIEW_RESERVATION_NEW

    rows = [dict(row) for row in db._conn.execute("SELECT * FROM auto_reviews")]
    rows += [
        dict(row)
        for row in db._conn.execute("SELECT * FROM auto_review_provider_snapshots")
    ]
    db._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    blob = path.read_bytes()
    for secret in (REVIEWER_KEY, GITHUB_TOKEN):
        assert secret not in str(rows)
        assert secret.encode() not in blob


def test_snapshot_rejects_secretish_config(tmp_path):
    db = make_db(tmp_path)
    with pytest.raises(ValueError):
        make_snapshot(db, config={"api_key": REVIEWER_KEY})
    assert db._conn.execute(
        "SELECT count(*) FROM auto_review_provider_snapshots"
    ).fetchone()[0] == 0
