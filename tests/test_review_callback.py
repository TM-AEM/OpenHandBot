"""R6 callback parsing, registration, authorization, Details, and OWNER_ACCEPTANCE."""
from __future__ import annotations

import asyncio
import re
import sqlite3
from types import SimpleNamespace

import pytest

from bot.app import build_application
from bot.config import Config
from bot.db import AutoReviewConflict
from bot.handlers import review_action
from bot.review.report import (
    ACTION_ACCEPT,
    ACTION_DETAILS,
    ACTION_REJECT,
    ReviewCallbackError,
    ReviewReportService,
    build_review_callback,
    parse_review_callback,
)
from tests._review_r6_helpers import (
    SHA2,
    T2,
    finding,
    make_db,
    member,
    seed_completed_cycle,
)


class FakeQuery:
    def __init__(self, data, chat_id=7):
        self.data = data
        self.message = SimpleNamespace(chat_id=chat_id)
        self.answers = []

    async def answer(self, text=None, show_alert=False):
        self.answers.append(text)


class FakeBot:
    def __init__(self):
        self.documents = []

    async def send_document(self, **kwargs):
        self.documents.append(kwargs)
        return object()


def make_context(db, *, allowed=(7,), owner=7):
    config = Config(
        telegram_bot_token="123456:ABCDEFGH",
        openhands_api_key="k",
        allowed_telegram_ids=frozenset(allowed),
        owner_id=owner,
        db_path="unused",
    )
    return SimpleNamespace(
        bot=FakeBot(),
        bot_data={
            "config": config,
            "db": db,
            "review_report_service": ReviewReportService(db, owner_id=7),
        },
    )


def make_update(data, *, user=7, chat=7, update_id=1):
    return SimpleNamespace(
        callback_query=FakeQuery(data, chat_id=chat),
        effective_user=SimpleNamespace(id=user),
        effective_chat=SimpleNamespace(id=chat, type="private"),
        update_id=update_id,
    )


def _seed(tmp_path):
    db = make_db(tmp_path)
    review_id = seed_completed_cycle(
        db,
        (member(1, SHA2),),
        blind_findings=[finding("F-1", "high")],
        adversarial_findings=[finding("F-1", "high")],
    )
    ReviewReportService(db, owner_id=7).prepare(review_id, now=T2)
    return db, review_id


def _call(handler, update, context):
    asyncio.run(handler(update, context))


def test_callback_format_parsing_and_utf8_limit():
    for action in (ACTION_DETAILS, ACTION_ACCEPT, ACTION_REJECT):
        data = build_review_callback(action, 123, 1)
        assert len(data.encode("utf-8")) <= 64
        assert data.startswith("review:")
        assert parse_review_callback(data) == (action, 123, 1)
        assert "sk-" not in data
        assert not re.search(r"[0-9a-f]{40}", data)
    with pytest.raises(ReviewCallbackError):
        parse_review_callback("review:x:1:1")
    with pytest.raises(ReviewCallbackError):
        parse_review_callback("review:a:0:1")
    with pytest.raises(ReviewCallbackError):
        parse_review_callback("review:a:1:1:extra")
    with pytest.raises(ReviewCallbackError):
        parse_review_callback("review:a:" + "9" * 60 + ":1")
    with pytest.raises(ReviewCallbackError):
        build_review_callback("bogus", 1, 1)
    # A 60-byte numeric id plus framing is over the Telegram limit.
    with pytest.raises(ReviewCallbackError):
        build_review_callback(ACTION_ACCEPT, int("9" * 60), 1)


def test_review_callback_is_registered_narrowly(tmp_path):
    config = Config(
        telegram_bot_token="123456:ABCDEFGH",
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({1}),
        owner_id=1,
        db_path=str(tmp_path / "app.sqlite3"),
    )
    app = build_application(config)
    patterns = [
        h.pattern.pattern
        for group in app.handlers.values()
        for h in group
        if hasattr(h, "pattern") and h.pattern is not None
    ]
    assert "^review:" in patterns
    review_patterns = [p for p in patterns if p.startswith("^review")]
    assert review_patterns == ["^review:"]
    assert re.match("^review:", "review:d:1:1")
    assert not re.match("^review:", "reviewx:d:1:1")


@pytest.mark.parametrize(
    "action,answer,expected",
    [
        (ACTION_ACCEPT, "تم تسجيل القبول.", "ACCEPT"),
        (ACTION_REJECT, "تم تسجيل الرفض.", "REJECT"),
    ],
)
def test_owner_accept_reject_persists_separate_record_and_keeps_verdict(
    tmp_path, action, answer, expected
):
    db, review_id = _seed(tmp_path)
    before_cycle = db.get_auto_review(review_id)
    before_stages = tuple(
        row["output_json"]
        for row in db._conn.execute(
            "SELECT output_json FROM auto_review_stages WHERE review_id=? ORDER BY stage",
            (review_id,),
        )
    )
    context = make_context(db)
    update = make_update(build_review_callback(action, review_id, 1))
    _call(review_action, update, context)
    assert update.callback_query.answers[-1] == answer
    decisions = db.list_auto_review_owner_decisions(review_id)
    assert len(decisions) == 1
    assert decisions[0].action == expected
    assert decisions[0].event_type == "OWNER_ACCEPTANCE"
    after_cycle = db.get_auto_review(review_id)
    assert after_cycle.verdict == before_cycle.verdict == "PASS"
    after_stages = tuple(
        row["output_json"]
        for row in db._conn.execute(
            "SELECT output_json FROM auto_review_stages WHERE review_id=? ORDER BY stage",
            (review_id,),
        )
    )
    assert after_stages == before_stages


def test_duplicate_and_conflicting_decisions_are_stable(tmp_path):
    db, review_id = _seed(tmp_path)
    context = make_context(db)
    data = build_review_callback(ACTION_ACCEPT, review_id, 1)
    first = make_update(data, update_id=1)
    _call(review_action, first, context)
    second = make_update(data, update_id=2)
    _call(review_action, second, context)
    assert second.callback_query.answers[-1] == "تم تسجيل قرارك مسبقًا."
    assert len(db.list_auto_review_owner_decisions(review_id)) == 1
    conflict = make_update(
        build_review_callback(ACTION_REJECT, review_id, 1), update_id=3
    )
    _call(review_action, conflict, context)
    assert conflict.callback_query.answers[-1] == "يوجد قرار سابق ولا يمكن تغييره."
    decisions = db.list_auto_review_owner_decisions(review_id)
    assert len(decisions) == 1
    assert decisions[0].action == "ACCEPT"
    assert db.get_auto_review(review_id).verdict == "PASS"


def test_allowed_non_owner_and_disallowed_users_mutate_nothing(tmp_path):
    db, review_id = _seed(tmp_path)
    for user, allowed in ((8, (7, 8)), (9, (7,))):
        context = make_context(db, allowed=allowed, owner=7)
        update = make_update(
            build_review_callback(ACTION_ACCEPT, review_id, 1), user=user
        )
        _call(review_action, update, context)
        assert update.callback_query.answers == [None]
        assert db.list_auto_review_owner_decisions(review_id) == ()


def test_forged_and_cross_conversation_callbacks_are_rejected(tmp_path):
    db, review_id = _seed(tmp_path)
    context = make_context(db)
    forged = make_update(build_review_callback(ACTION_ACCEPT, 999, 1))
    _call(review_action, forged, context)
    assert db.list_auto_review_owner_decisions(review_id) == ()
    cross = make_update(build_review_callback(ACTION_ACCEPT, review_id, 1), chat=8)
    _call(review_action, cross, context)
    assert db.list_auto_review_owner_decisions(review_id) == ()
    missing_version = make_update(
        build_review_callback(ACTION_ACCEPT, review_id, 2)
    )
    _call(review_action, missing_version, context)
    assert missing_version.callback_query.answers[-1] == "التقرير غير متاح."
    assert db.list_auto_review_owner_decisions(review_id) == ()


def test_details_sends_exact_report_and_repeats_safely(tmp_path):
    db, review_id = _seed(tmp_path)
    context = make_context(db)
    data = build_review_callback(ACTION_DETAILS, review_id, 1)
    first = make_update(data, update_id=1)
    _call(review_action, first, context)
    second = make_update(data, update_id=2)
    _call(review_action, second, context)
    assert len(context.bot.documents) == 2
    assert context.bot.documents[0]["document"].filename == "review-bbbbbbb.md"
    assert "PASS" in context.bot.documents[0]["caption"]
    assert first.callback_query.answers[-1] == "تم إرسال التقرير."
    assert db.list_auto_review_owner_decisions(review_id) == ()


def test_details_requires_owner_and_missing_report_fails_closed(tmp_path):
    db, review_id = _seed(tmp_path)
    context = make_context(db, allowed=(7, 8), owner=7)
    non_owner = make_update(
        build_review_callback(ACTION_DETAILS, review_id, 1), user=8
    )
    _call(review_action, non_owner, context)
    assert context.bot.documents == []
    # A cycle with no persisted report cannot be fabricated.
    missing_dir = tmp_path / "missing"
    missing_dir.mkdir()
    missing_db = make_db(missing_dir)
    missing_id = seed_completed_cycle(missing_db, (member(1, SHA2),))
    missing_context = make_context(missing_db)
    owner = make_update(build_review_callback(ACTION_DETAILS, missing_id, 1))
    _call(review_action, owner, missing_context)
    assert owner.callback_query.answers[-1] == "التقرير غير متاح."
    assert missing_context.bot.documents == []


def test_database_failure_never_reports_acceptance_success(tmp_path, monkeypatch):
    db, review_id = _seed(tmp_path)
    context = make_context(db)

    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("boom")

    monkeypatch.setattr(db, "record_auto_review_owner_decision", fail)
    update = make_update(build_review_callback(ACTION_ACCEPT, review_id, 1))
    _call(review_action, update, context)
    assert update.callback_query.answers[-1] == "تعذّر تسجيل قرارك؛ لم يتم حفظه."
    assert db.list_auto_review_owner_decisions(review_id) == ()
    assert db.get_auto_review(review_id).verdict == "PASS"


def test_db_rejects_owner_mismatch_even_if_called_directly(tmp_path):
    db, review_id = _seed(tmp_path)
    with pytest.raises(AutoReviewConflict):
        db.record_auto_review_owner_decision(review_id, 1, 8, "ACCEPT", now=T2)
    assert db.list_auto_review_owner_decisions(review_id) == ()
