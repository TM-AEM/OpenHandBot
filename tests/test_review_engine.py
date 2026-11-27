"""R4: isolated two-stage review cycle and deterministic verdict integration."""

from __future__ import annotations

import asyncio
import json

from bot.review.engine import _combine_blind, run_review_cycle
from bot.review.evidence import ReviewEvidence
from bot.review.github import (
    WorkflowJob,
    WorkflowJobsEvidence,
    WorkflowRun,
    WorkflowRunsEvidence,
)
from bot.review.llm import ModelResponse
from bot.review.llm import StageExecution
from bot.review.schema import SCHEMA_VERSION, BlindReviewOutput, parse_blind_review

A = "a" * 40
B = "b" * 40
REPORT = "OPENHANDS_REPORT_SENTINEL"


def diff():
    return (
        "diff --git a/src/x.py b/src/x.py\n"
        "--- a/src/x.py\n"
        "+++ b/src/x.py\n"
        "@@ -1 +1 @@\n"
        "-old\n+new\n"
    )


def runs(*, ci_state="success", conclusion="success"):
    return WorkflowRunsEvidence(
        repository="owner/repo",
        head_sha=B,
        runs=(
            WorkflowRun(
                run_id=1,
                name="verify",
                head_sha=B,
                head_branch="agent/x",
                status="completed",
                conclusion=conclusion,
                event="push",
                run_attempt=1,
                created_at=None,
                updated_at=None,
            ),
        ),
        status="verified",
        observed_head_shas=(B,),
        ci_state=ci_state,
    )


def jobs():
    return WorkflowJobsEvidence(
        repository="owner/repo",
        run_id=1,
        head_sha=B,
        jobs=(
            WorkflowJob(
                job_id=10,
                run_id=1,
                name="test",
                head_sha=B,
                status="completed",
                conclusion="success",
                started_at=None,
                completed_at=None,
            ),
        ),
        status="verified",
        observed_head_shas=(B,),
    )


def evidence(*, ci_state="success"):
    return ReviewEvidence.from_raw_diff(
        repository="owner/repo",
        pr_number=1,
        branch="agent/x",
        base_sha=A,
        head_sha=B,
        diff_text=diff(),
        max_input_chars=20_000,
        ci_runs=runs(ci_state=ci_state),
        ci_jobs=(jobs(),),
        sha_status="verified",
        ci_jobs_complete=True,
    )


def blind_json():
    return json.dumps(
        {
            "schema_version": "r4.v1",
            "stage": "blind",
            "assessment": "clean",
            "summary": "clean",
            "findings": [],
            "reviewed_files": ["src/x.py"],
            "evidence_gaps": [],
        }
    )


def adversarial_json(blind_sha):
    return json.dumps(
        {
            "schema_version": "r4.v1",
            "stage": "adversarial",
            "blind_review_sha256": blind_sha,
            "assessment": "concur",
            "summary": "concur",
            "findings": [],
            "challenges": [],
            "reviewed_files": ["src/x.py"],
            "evidence_gaps": [],
        }
    )


class FakeAdapter:
    def __init__(self, blind_response, adversarial_response):
        self.blind_response = blind_response
        self.adversarial_response = adversarial_response
        self.calls = []

    async def complete(self, request):
        self.calls.append(request)
        if request.stage == "blind":
            return ModelResponse(self.blind_response, 200, "testprovider", "m")
        return ModelResponse(self.adversarial_response, 200, "testprovider", "m")


def test_two_stage_cycle_isolates_blind_and_passes_deterministically():
    blind = parse_blind_review(blind_json())
    adapter = FakeAdapter(blind_json(), adversarial_json(blind.fingerprint))
    result = asyncio.run(
        run_review_cycle(
            adapter,
            evidence=evidence(),
            implementation_report=REPORT,
            max_input_chars=10_000,
        )
    )
    assert result.verdict.verdict == "PASS"
    assert result.verdict.rule == "R4-PASS-01"
    assert len(adapter.calls) == 2
    assert adapter.calls[0].stage == "blind"
    assert REPORT not in adapter.calls[0].user
    assert adapter.calls[1].stage == "adversarial"
    assert REPORT in adapter.calls[1].user
    assert blind.fingerprint in adapter.calls[1].user


def test_combined_summary_overflow_fails_closed():
    output = BlindReviewOutput(
        SCHEMA_VERSION, "blind", "clean", "x" * 3_000, (), ("src/x.py",), ()
    )
    run = StageExecution("blind", "ok", output, None, False, "f" * 64)
    assert _combine_blind([run, run]) is None


def test_blind_failure_stops_before_adversarial_and_blocks():
    adapter = FakeAdapter("not-json", adversarial_json("0" * 64))
    result = asyncio.run(
        run_review_cycle(
            adapter,
            evidence=evidence(),
            implementation_report=REPORT,
            max_input_chars=10_000,
        )
    )
    assert result.verdict.verdict == "BLOCKED"
    assert len(adapter.calls) == 2  # one blind call + one bounded correction
    assert result.adversarial_execution is None


def test_ci_failure_cannot_be_overridden_by_successful_review():
    blind = parse_blind_review(blind_json())
    adapter = FakeAdapter(blind_json(), adversarial_json(blind.fingerprint))
    result = asyncio.run(
        run_review_cycle(
            adapter,
            evidence=evidence(ci_state="failure"),
            implementation_report=REPORT,
            max_input_chars=10_000,
        )
    )
    assert result.verdict.verdict == "FAIL"
    assert result.verdict.rule == "R4-CI-01"


def test_forged_adversarial_blind_binding_is_blocked():
    adapter = FakeAdapter(blind_json(), adversarial_json("0" * 64))
    result = asyncio.run(
        run_review_cycle(
            adapter,
            evidence=evidence(),
            implementation_report=REPORT,
            max_input_chars=10_000,
        )
    )
    assert result.verdict.verdict == "BLOCKED"
    assert result.adversarial_validation.stage_valid is False
