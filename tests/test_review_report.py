"""R6 deterministic report generation tests (no network, no Telegram)."""
from __future__ import annotations

import sqlite3

import pytest

from bot.db import AutoReviewConflict
from bot.review.report import (
    ReviewReportError,
    ReviewReportService,
    build_review_report,
    report_filename,
)
from tests._review_r6_helpers import (
    SHA2,
    SHA3,
    SHA4,
    T2,
    finding,
    make_db,
    member,
    reserve,
    seed_completed_cycle,
)


def test_single_pr_filename_and_deterministic_content(tmp_path):
    db = make_db(tmp_path)
    review_id = seed_completed_cycle(
        db,
        (member(1, SHA2),),
        blind_findings=[finding("F-1", "high")],
        adversarial_findings=[finding("F-1", "high")],
    )
    first = build_review_report(db, review_id)
    second = build_review_report(db, review_id)
    assert first.filename == "review-bbbbbbb.md"
    assert first.filename == second.filename
    assert first.content == second.content
    assert first.report_sha256 == second.report_sha256
    assert first.summary == second.summary
    assert "review-bbbbbbb.md" in first.content
    assert SHA2 in first.content
    assert "PASS" in first.content
    assert "OWNER_ACCEPTANCE" in first.content


def test_multi_pr_filename_uses_aggregate_snapshot_not_one_pr(tmp_path):
    db = make_db(tmp_path)
    members = (member(1, SHA2), member(2, SHA4, base=SHA3))
    review_id = seed_completed_cycle(db, members)
    report = build_review_report(db, review_id)
    expected = report_filename(members)
    assert report.filename == expected
    assert report.filename != f"review-{SHA2[:7]}.md"
    assert "owner/repo#1" in report.content
    assert "owner/repo#2" in report.content
    assert SHA2 in report.content and SHA4 in report.content


def test_findings_are_grouped_ordered_and_deduplicated(tmp_path):
    db = make_db(tmp_path)
    blind = [
        finding("F-2", "low", claim="low claim"),
        finding("F-1", "critical", claim="critical claim"),
        finding("F-3", "high", claim="high claim"),
    ]
    adversarial = [finding("F-3", "high", claim="high claim")]
    review_id = seed_completed_cycle(
        db, (member(1, SHA2),), blind_findings=blind, adversarial_findings=adversarial
    )
    content = build_review_report(db, review_id).content
    assert content.index("### critical") < content.index("### high") < content.index("### low")
    assert content.count("**F-3**") == 1
    assert "المصدر: adversarial, blind" in content


def test_blocked_and_incomplete_evidence_are_not_reported_as_pass(tmp_path):
    db = make_db(tmp_path)
    review_id = seed_completed_cycle(
        db,
        (member(1, SHA2),),
        verdict="BLOCKED",
        coverage=False,
        ci_state="failure",
        stage_status="invalid",
    )
    report = build_review_report(db, review_id)
    assert "**BLOCKED**" in report.content
    assert "غير مكتملة" in report.content
    assert "stage\\_not\\_validated" in report.content
    assert "coverage\\_incomplete" in report.content
    assert "**PASS**" not in report.content
    assert "الحالة: مكتملة" not in report.summary


def test_report_escapes_untrusted_markdown_and_html(tmp_path):
    db = make_db(tmp_path)
    payload = "<script>alert(1)</script> [click](https://evil.invalid)"
    review_id = seed_completed_cycle(
        db,
        (member(1, SHA2),),
        blind_findings=[finding("F-1", "medium", description=payload)],
    )
    content = build_review_report(db, review_id).content
    assert "<script>" not in content
    assert "&lt;script&gt;" in content
    assert "[click](https://evil.invalid)" not in content
    assert "\\[click\\]" in content


def test_report_rejects_secret_in_persisted_output(tmp_path):
    db = make_db(tmp_path)
    secret = "sk-" + "A" * 24
    review_id = seed_completed_cycle(
        db,
        (member(1, SHA2),),
        blind_findings=[finding("F-1", "high", description=secret)],
    )
    with pytest.raises(ReviewReportError) as exc:
        build_review_report(db, review_id)
    assert exc.value.code == "secret_in_report"


def test_report_size_is_bounded(tmp_path, monkeypatch):
    db = make_db(tmp_path)
    review_id = seed_completed_cycle(db, (member(1, SHA2),))
    monkeypatch.setattr("bot.review.report.MAX_REPORT_CHARS", 100)
    with pytest.raises(ReviewReportError) as exc:
        build_review_report(db, review_id)
    assert exc.value.code == "report_too_large"


def test_filename_rejects_invalid_sha():
    bad = member(1, "not-a-sha")
    with pytest.raises(ReviewReportError) as exc:
        report_filename((bad,))
    assert exc.value.code == "invalid_head_sha"


def test_owner_acceptance_does_not_change_report_content(tmp_path):
    db = make_db(tmp_path)
    review_id = seed_completed_cycle(
        db,
        (member(1, SHA2),),
        blind_findings=[finding("F-1", "medium")],
    )
    before = build_review_report(db, review_id)
    ReviewReportService(db, owner_id=7).prepare(review_id, now=T2)
    db.record_auto_review_owner_decision(review_id, 1, 7, "ACCEPT", now=T2)
    after = build_review_report(db, review_id)
    assert before.content == after.content
    assert before.report_sha256 == after.report_sha256
    cycle = db.get_auto_review(review_id)
    assert cycle.verdict == "PASS"
    assert db.list_auto_review_owner_decisions(review_id)[0].action == "ACCEPT"


def test_report_cannot_be_built_for_active_cycle(tmp_path):
    db = make_db(tmp_path)
    result = reserve(db, (member(1, SHA2),))
    with pytest.raises(ReviewReportError) as exc:
        build_review_report(db, result.review_id)
    assert exc.value.code == "review_not_terminal"


def test_report_version_is_immutable_and_hash_checked(tmp_path):
    db = make_db(tmp_path)
    review_id = seed_completed_cycle(db, (member(1, SHA2),))
    service = ReviewReportService(db, owner_id=7)
    report = service.prepare(review_id, now=T2)
    with pytest.raises(AutoReviewConflict):
        db.save_auto_review_report(
            review_id,
            version=1,
            filename=report.filename,
            content=report.content + "changed",
            summary=report.summary,
            report_sha256="0" * 64,
            verdict=report.verdict,
            now=T2,
        )
    with pytest.raises(sqlite3.IntegrityError):
        db._conn.execute(
            "UPDATE auto_review_reports SET summary='tampered' WHERE id=?",
            (report.id,),
        )
    assert db.get_auto_review_report(review_id, 1).summary == report.summary
