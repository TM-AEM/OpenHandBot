"""R4: strict blind/adversarial output schemas."""

from __future__ import annotations

import json

import pytest

from bot.review.schema import (
    AdversarialReviewOutput,
    BlindReviewOutput,
    SchemaError,
    parse_adversarial_review,
    parse_blind_review,
    parse_stage_output,
)

A = "a" * 40
B = "b" * 40
BLIND_SHA = "a" * 64


def finding(**over):
    value = {
        "id": "F-1",
        "severity": "medium",
        "category": "correctness",
        "claim": "claim",
        "description": "description",
        "file": "src/x.py",
        "line_start": 2,
        "line_end": 2,
        "confidence": "high",
        "evidence_quote": "+new",
        "ci_run_id": None,
        "ci_job_id": None,
        "ci_status": None,
        "commit_sha": None,
        "recommendation": None,
    }
    value.update(over)
    return value


def blind(**over):
    value = {
        "schema_version": "r4.v1",
        "stage": "blind",
        "assessment": "findings",
        "summary": "summary",
        "findings": [finding()],
        "reviewed_files": ["src/x.py"],
        "evidence_gaps": [],
    }
    value.update(over)
    return value


def adversarial(**over):
    value = {
        "schema_version": "r4.v1",
        "stage": "adversarial",
        "blind_review_sha256": BLIND_SHA,
        "assessment": "concur",
        "summary": "summary",
        "findings": [finding(id="F-2")],
        "challenges": [{"finding_id": "F-1", "status": "supported", "reason": "checked"}],
        "reviewed_files": ["src/x.py"],
        "evidence_gaps": [],
    }
    value.update(over)
    return value


def text(value):
    return json.dumps(value, sort_keys=True)


def test_valid_blind_and_fingerprint_are_deterministic():
    first = parse_blind_review(text(blind()))
    second = parse_blind_review(text(blind()))
    assert isinstance(first, BlindReviewOutput)
    assert first.stage == "blind"
    assert first.fingerprint == second.fingerprint
    assert len(first.fingerprint) == 64
    changed = parse_blind_review(text(blind(summary="different")))
    assert changed.fingerprint != first.fingerprint


def test_valid_adversarial_and_fingerprint():
    output = parse_adversarial_review(text(adversarial()))
    assert isinstance(output, AdversarialReviewOutput)
    assert output.stage == "adversarial"
    assert output.challenges[0].status == "supported"
    assert len(output.fingerprint) == 64


@pytest.mark.parametrize(
    "payload",
    [
        blind(extra="x"),
        blind(verdict="PASS"),
        blind(schema_version="r4.v2"),
        blind(stage="adversarial"),
        blind(assessment="pass"),
        blind(findings=[]),
        blind(findings=[finding(severity="info")]),
        blind(findings=[finding(category="style")]),
        blind(findings=[finding(confidence="certain")]),
        blind(findings=[finding(id="bad id")]),
        blind(findings=[finding(file="/etc/passwd")]),
        blind(findings=[finding(file="../secret")]),
        blind(findings=[finding(file="src\\x.py")]),
        blind(findings=[finding(line_start=0)]),
        blind(findings=[finding(line_start=3, line_end=2)]),
        blind(findings=[finding(), finding()]),
        blind(reviewed_files=["src/x.py", "src/x.py"]),
        blind(assessment="clean"),
        blind(assessment="insufficient_evidence"),
    ],
)

def test_invalid_blind_outputs_fail_closed(payload):
    with pytest.raises(SchemaError):
        parse_blind_review(text(payload))


@pytest.mark.parametrize(
    "payload",
    [
        adversarial(extra="x"),
        adversarial(verdict="FAIL"),
        adversarial(blind_review_sha256="not-a-sha"),
        adversarial(assessment="dissent", challenges=[]),
        adversarial(assessment="pass"),
        adversarial(
            challenges=[
                {"finding_id": "F-1", "status": "supported", "reason": "x"},
                {"finding_id": "F-1", "status": "supported", "reason": "y"},
            ]
        ),
        adversarial(challenges=[{"finding_id": "F-1", "status": "maybe", "reason": "x"}]),
        adversarial(findings=[finding(id="F-2"), finding(id="F-2")]),
    ],
)

def test_invalid_adversarial_outputs_fail_closed(payload):
    with pytest.raises(SchemaError):
        parse_adversarial_review(text(payload))


def test_malformed_json_duplicate_keys_and_non_object_are_rejected():
    with pytest.raises(SchemaError) as info:
        parse_blind_review('{"schema_version":"r4.v1",')
    assert info.value.code == "invalid_json"
    with pytest.raises(SchemaError) as info:
        parse_blind_review('{"schema_version":"r4.v1","schema_version":"r4.v1"}')
    assert info.value.code == "duplicate_json_key"
    with pytest.raises(SchemaError) as info:
        parse_blind_review("[]")
    assert info.value.code == "output_not_object"


def test_oversized_output_and_bad_limits_are_rejected_without_raw_output():
    payload = text(blind(summary="x" * 500))
    with pytest.raises(SchemaError) as info:
        parse_blind_review(payload, max_chars=50)
    assert info.value.code == "output_too_large"
    assert "x" * 20 not in str(info.value)
    with pytest.raises(SchemaError) as info:
        parse_blind_review(text(blind()), max_chars=True)
    assert info.value.code == "invalid_output_limit"


def test_missing_fields_are_not_success():
    payload = blind()
    payload.pop("findings")
    with pytest.raises(SchemaError) as info:
        parse_blind_review(text(payload))
    assert info.value.code == "missing_field"


def test_parse_stage_output_rejects_unknown_stage():
    with pytest.raises(SchemaError) as info:
        parse_stage_output(text(blind()), "unknown")
    assert info.value.code == "unsupported_stage"
