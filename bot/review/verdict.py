"""Deterministic verdict rules (R4).

The model never supplies the verdict. Only validated findings, verified CI state,
verified SHA/evidence coverage, and fixed precedence determine the result.
Owner acceptance is deliberately separate and is not implemented here.
"""
from __future__ import annotations

from dataclasses import dataclass

from bot.review.evidence import ReviewEvidence, StageEvidenceValidation
from bot.review.schema import Finding

VERDICT_PASS = "PASS"
VERDICT_PASS_WITH_NOTES = "PASS_WITH_NOTES"
VERDICT_FAIL = "FAIL"
VERDICT_BLOCKED = "BLOCKED"
VERDICTS = (VERDICT_PASS, VERDICT_PASS_WITH_NOTES, VERDICT_FAIL, VERDICT_BLOCKED)

RULES_VERSION = "r4-verdict.v1"


@dataclass(frozen=True)
class VerdictResult:
    verdict: str
    reason: str
    rule: str
    valid_findings: tuple[Finding, ...]
    invalid_findings: int
    ci_state: str
    sha_status: str
    notes: tuple[str, ...] = ()


def evaluate_verdict(
    *,
    evidence: ReviewEvidence,
    blind_validation: StageEvidenceValidation,
    adversarial_validation: StageEvidenceValidation,
    blind_stage_ok: bool,
    adversarial_stage_ok: bool,
    blind_assessment: str | None,
    adversarial_assessment: str | None,
    notes: tuple[str, ...] = (),
) -> VerdictResult:
    valid_findings = _dedupe(blind_validation.accepted + adversarial_validation.accepted)
    invalid_findings = blind_validation.invalid_findings + adversarial_validation.invalid_findings
    stage_failure = (
        not blind_stage_ok
        or not adversarial_stage_ok
        or not blind_validation.stage_valid
        or not adversarial_validation.stage_valid
    )
    evidence_gaps = bool(blind_validation.evidence_gaps or adversarial_validation.evidence_gaps)
    sha_ok = (
        evidence.sha_status == "verified"
        and blind_validation.sha_status == "verified"
        and adversarial_validation.sha_status == "verified"
        and evidence.coverage_complete
    )
    ci_state = evidence.ci_state

    if not sha_ok:
        return _result(
            VERDICT_BLOCKED,
            "sha_or_diff_evidence_not_verified",
            "R4-SHA-01",
            valid_findings,
            invalid_findings,
            ci_state,
            evidence.sha_status,
            notes,
        )
    if ci_state == "failure":
        return _result(
            VERDICT_FAIL,
            "ci_failure",
            "R4-CI-01",
            valid_findings,
            invalid_findings,
            ci_state,
            evidence.sha_status,
            notes,
        )
    if evidence.secret_detected:
        return _result(
            VERDICT_FAIL,
            "secret_detected_in_diff",
            "R4-SEC-01",
            valid_findings,
            invalid_findings,
            ci_state,
            evidence.sha_status,
            notes,
        )
    if any(item.severity in ("critical", "high") for item in valid_findings):
        return _result(
            VERDICT_FAIL,
            "valid_critical_or_high_finding",
            "R4-FINDING-01",
            valid_findings,
            invalid_findings,
            ci_state,
            evidence.sha_status,
            notes,
        )
    if stage_failure or invalid_findings or evidence_gaps:
        return _result(
            VERDICT_BLOCKED,
            "stage_or_evidence_failure",
            "R4-BLOCK-01",
            valid_findings,
            invalid_findings,
            ci_state,
            evidence.sha_status,
            notes,
        )
    if blind_assessment in ("insufficient_evidence",) or adversarial_assessment in (
        "insufficient_evidence",
        "dissent",
    ):
        return _result(
            VERDICT_BLOCKED,
            "reviewer_insufficient_evidence_or_dissent",
            "R4-BLOCK-02",
            valid_findings,
            invalid_findings,
            ci_state,
            evidence.sha_status,
            notes,
        )
    if ci_state != "success":
        return _result(
            VERDICT_BLOCKED,
            "ci_unavailable_or_not_successful",
            "R4-CI-02",
            valid_findings,
            invalid_findings,
            ci_state,
            evidence.sha_status,
            notes,
        )
    if not evidence.ci_jobs_complete:
        return _result(
            VERDICT_BLOCKED,
            "ci_jobs_incomplete_or_unverified",
            "R4-CI-03",
            valid_findings,
            invalid_findings,
            ci_state,
            evidence.sha_status,
            notes,
        )
    if not valid_findings:
        return _result(
            VERDICT_PASS,
            "ci_success_and_no_valid_findings",
            "R4-PASS-01",
            valid_findings,
            invalid_findings,
            ci_state,
            evidence.sha_status,
            notes,
        )
    if all(item.severity in ("medium", "low") for item in valid_findings):
        return _result(
            VERDICT_PASS_WITH_NOTES,
            "only_medium_or_low_valid_findings",
            "R4-NOTES-01",
            valid_findings,
            invalid_findings,
            ci_state,
            evidence.sha_status,
            notes,
        )
    return _result(
        VERDICT_BLOCKED,
        "unhandled_finding_combination",
        "R4-BLOCK-03",
        valid_findings,
        invalid_findings,
        ci_state,
        evidence.sha_status,
        notes,
    )


def _result(
    verdict: str,
    reason: str,
    rule: str,
    valid_findings: tuple[Finding, ...],
    invalid_findings: int,
    ci_state: str,
    sha_status: str,
    notes: tuple[str, ...],
) -> VerdictResult:
    return VerdictResult(
        verdict=verdict,
        reason=reason,
        rule=rule,
        valid_findings=valid_findings,
        invalid_findings=invalid_findings,
        ci_state=ci_state,
        sha_status=sha_status,
        notes=notes,
    )


def _dedupe(findings: tuple[Finding, ...]) -> tuple[Finding, ...]:
    rank = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    by_key: dict[tuple[str, str], Finding] = {}
    for finding in findings:
        key = (finding.file, finding.id)
        current = by_key.get(key)
        if current is None or rank.get(finding.severity, 5) > rank.get(
            current.severity, 5
        ):
            by_key[key] = finding
    return tuple(by_key.values())
