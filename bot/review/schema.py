"""Strict, versioned review output schemas (R4).

Model output is untrusted data. This module never parses free text into a verdict
and never treats missing fields as success. All failures are safe, typed errors.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

SCHEMA_VERSION = "r4.v1"
STAGE_BLIND = "blind"
STAGE_ADVERSARIAL = "adversarial"
STAGES = (STAGE_BLIND, STAGE_ADVERSARIAL)

SEVERITIES = ("critical", "high", "medium", "low")
CONFIDENCES = ("high", "medium", "low")
CATEGORIES = ("security", "correctness", "tests", "performance", "maintainability", "other")
BLIND_ASSESSMENTS = ("clean", "findings", "insufficient_evidence")
ADVERSARIAL_ASSESSMENTS = ("concur", "dissent", "insufficient_evidence")
CHALLENGE_STATUSES = ("supported", "unsupported", "unverifiable")
CI_STATUSES = ("success", "failure", "pending", "cancelled", "skipped", "unknown")

MAX_OUTPUT_CHARS = 200_000
MAX_FINDINGS = 100
MAX_REVIEWED_FILES = 2_000
MAX_EVIDENCE_GAPS = 100
MAX_CHALLENGES = 100
MAX_TITLE_CHARS = 300
MAX_DESCRIPTION_CHARS = 4_000
MAX_QUOTE_CHARS = 500
MAX_PATH_CHARS = 512
MAX_LINE = 1_000_000

_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class SchemaError(ValueError):
    """Safe schema error. It never includes raw model output."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


@dataclass(frozen=True)
class Finding:
    id: str
    severity: str
    category: str
    claim: str
    description: str
    file: str
    line_start: int
    line_end: int
    confidence: str
    evidence_quote: str | None = None
    ci_run_id: int | None = None
    ci_job_id: int | None = None
    ci_status: str | None = None
    commit_sha: str | None = None
    recommendation: str | None = None


@dataclass(frozen=True)
class Challenge:
    finding_id: str
    status: str
    reason: str


@dataclass(frozen=True)
class BlindReviewOutput:
    schema_version: str
    stage: str
    assessment: str
    summary: str
    findings: tuple[Finding, ...]
    reviewed_files: tuple[str, ...]
    evidence_gaps: tuple[str, ...]

    @property
    def fingerprint(self) -> str:
        return _fingerprint(_blind_dict(self))


@dataclass(frozen=True)
class AdversarialReviewOutput:
    schema_version: str
    stage: str
    blind_review_sha256: str
    assessment: str
    summary: str
    findings: tuple[Finding, ...]
    challenges: tuple[Challenge, ...]
    reviewed_files: tuple[str, ...]
    evidence_gaps: tuple[str, ...]

    @property
    def fingerprint(self) -> str:
        return _fingerprint(_adversarial_dict(self))


def _fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def output_json(output: BlindReviewOutput | AdversarialReviewOutput) -> str:
    """Canonical persisted representation; parse_stage_output validates it again."""
    if isinstance(output, BlindReviewOutput):
        payload = _blind_dict(output)
    elif isinstance(output, AdversarialReviewOutput):
        payload = _adversarial_dict(output)
    else:
        raise SchemaError("unsupported_output")
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _blind_dict(output: BlindReviewOutput) -> dict[str, Any]:
    return {
        "schema_version": output.schema_version,
        "stage": output.stage,
        "assessment": output.assessment,
        "summary": output.summary,
        "findings": [_finding_dict(item) for item in output.findings],
        "reviewed_files": list(output.reviewed_files),
        "evidence_gaps": list(output.evidence_gaps),
    }


def _adversarial_dict(output: AdversarialReviewOutput) -> dict[str, Any]:
    return {
        "schema_version": output.schema_version,
        "stage": output.stage,
        "blind_review_sha256": output.blind_review_sha256,
        "assessment": output.assessment,
        "summary": output.summary,
        "findings": [_finding_dict(item) for item in output.findings],
        "challenges": [
            {"finding_id": item.finding_id, "status": item.status, "reason": item.reason}
            for item in output.challenges
        ],
        "reviewed_files": list(output.reviewed_files),
        "evidence_gaps": list(output.evidence_gaps),
    }


def _finding_dict(item: Finding) -> dict[str, Any]:
    return {
        "id": item.id,
        "severity": item.severity,
        "category": item.category,
        "claim": item.claim,
        "description": item.description,
        "file": item.file,
        "line_start": item.line_start,
        "line_end": item.line_end,
        "confidence": item.confidence,
        "evidence_quote": item.evidence_quote,
        "ci_run_id": item.ci_run_id,
        "ci_job_id": item.ci_job_id,
        "ci_status": item.ci_status,
        "commit_sha": item.commit_sha,
        "recommendation": item.recommendation,
    }


def schema_instructions(stage: str) -> str:
    """Return the exact JSON contract shown to the model for a stage."""
    common: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "stage": stage,
        "assessment": (
            "clean|findings|insufficient_evidence"
            if stage == STAGE_BLIND
            else "concur|dissent|insufficient_evidence"
        ),
        "summary": "bounded text",
        "findings": [
            {
                "id": "F-1",
                "severity": "critical|high|medium|low",
                "category": "security|correctness|tests|performance|maintainability|other",
                "claim": "bounded text",
                "description": "bounded text",
                "file": "path/from/diff",
                "line_start": 1,
                "line_end": 1,
                "confidence": "high|medium|low",
                "evidence_quote": "optional exact diff text",
                "ci_run_id": None,
                "ci_job_id": None,
                "ci_status": "success|failure|pending|cancelled|skipped|unknown",
                "commit_sha": None,
                "recommendation": None,
            }
        ],
        "reviewed_files": ["path/from/diff"],
        "evidence_gaps": ["bounded text"],
    }
    if stage == STAGE_ADVERSARIAL:
        common["blind_review_sha256"] = "64 lowercase hex"
        common["challenges"] = [
            {"finding_id": "F-1", "status": "supported|unsupported|unverifiable", "reason": "text"}
        ]
    return json.dumps(common, indent=2, ensure_ascii=False)


def parse_stage_output(
    text: str,
    stage: str,
    *,
    max_chars: int = MAX_OUTPUT_CHARS,
) -> BlindReviewOutput | AdversarialReviewOutput:
    if stage not in STAGES:
        raise SchemaError("unsupported_stage")
    if not isinstance(text, str):
        raise SchemaError("output_not_text")
    if not isinstance(max_chars, int) or isinstance(max_chars, bool):
        raise SchemaError("invalid_output_limit")
    if not 1 <= max_chars <= MAX_OUTPUT_CHARS:
        raise SchemaError("invalid_output_limit")
    if len(text) > max_chars:
        raise SchemaError("output_too_large")
    try:
        raw = json.loads(text, object_pairs_hook=_unique_object)
    except SchemaError:
        raise
    except (TypeError, ValueError) as exc:
        raise SchemaError("invalid_json") from exc
    if not isinstance(raw, dict):
        raise SchemaError("output_not_object")
    if stage == STAGE_BLIND:
        return _parse_blind(raw)
    return _parse_adversarial(raw)


def parse_blind_review(
    text: str, *, max_chars: int = MAX_OUTPUT_CHARS
) -> BlindReviewOutput:
    output = parse_stage_output(text, STAGE_BLIND, max_chars=max_chars)
    if not isinstance(output, BlindReviewOutput):
        raise SchemaError("stage_mismatch")
    return output


def parse_adversarial_review(
    text: str, *, max_chars: int = MAX_OUTPUT_CHARS
) -> AdversarialReviewOutput:
    output = parse_stage_output(text, STAGE_ADVERSARIAL, max_chars=max_chars)
    if not isinstance(output, AdversarialReviewOutput):
        raise SchemaError("stage_mismatch")
    return output


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SchemaError("duplicate_json_key")
        result[key] = value
    return result


def _parse_blind(raw: dict[str, Any]) -> BlindReviewOutput:
    _require_keys(
        raw,
        {
            "schema_version",
            "stage",
            "assessment",
            "summary",
            "findings",
            "reviewed_files",
            "evidence_gaps",
        },
        "blind",
    )
    _require_version_and_stage(raw, STAGE_BLIND)
    assessment = _enum(raw.get("assessment"), BLIND_ASSESSMENTS, "assessment")
    summary = _bounded_text(raw.get("summary"), "summary", 4_000)
    findings = _parse_findings(raw.get("findings"))
    reviewed_files = _parse_reviewed_files(raw.get("reviewed_files"))
    gaps = _parse_gaps(raw.get("evidence_gaps"))
    if assessment == "clean" and findings:
        raise SchemaError("contradictory_assessment")
    if assessment == "findings" and not findings:
        raise SchemaError("contradictory_assessment")
    if assessment == "insufficient_evidence" and not gaps:
        raise SchemaError("contradictory_assessment")
    return BlindReviewOutput(
        schema_version=SCHEMA_VERSION,
        stage=STAGE_BLIND,
        assessment=assessment,
        summary=summary,
        findings=findings,
        reviewed_files=reviewed_files,
        evidence_gaps=gaps,
    )


def _parse_adversarial(raw: dict[str, Any]) -> AdversarialReviewOutput:
    _require_keys(
        raw,
        {
            "schema_version",
            "stage",
            "blind_review_sha256",
            "assessment",
            "summary",
            "findings",
            "challenges",
            "reviewed_files",
            "evidence_gaps",
        },
        "adversarial",
    )
    _require_version_and_stage(raw, STAGE_ADVERSARIAL)
    blind_sha = raw.get("blind_review_sha256")
    if not isinstance(blind_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", blind_sha):
        raise SchemaError("invalid_blind_review_sha256")
    assessment = _enum(raw.get("assessment"), ADVERSARIAL_ASSESSMENTS, "assessment")
    summary = _bounded_text(raw.get("summary"), "summary", 4_000)
    findings = _parse_findings(raw.get("findings"))
    challenges = _parse_challenges(raw.get("challenges"))
    reviewed_files = _parse_reviewed_files(raw.get("reviewed_files"))
    gaps = _parse_gaps(raw.get("evidence_gaps"))
    if assessment == "dissent" and not challenges:
        raise SchemaError("contradictory_assessment")
    if assessment == "insufficient_evidence" and not gaps:
        raise SchemaError("contradictory_assessment")
    return AdversarialReviewOutput(
        schema_version=SCHEMA_VERSION,
        stage=STAGE_ADVERSARIAL,
        blind_review_sha256=blind_sha,
        assessment=assessment,
        summary=summary,
        findings=findings,
        challenges=challenges,
        reviewed_files=reviewed_files,
        evidence_gaps=gaps,
    )


def _require_version_and_stage(raw: dict[str, Any], stage: str) -> None:
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise SchemaError("unsupported_schema_version")
    if raw.get("stage") != stage:
        raise SchemaError("stage_mismatch")


def _require_keys(raw: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = set(raw) - allowed
    if unknown:
        raise SchemaError("unknown_field", f"{label}: unknown fields")
    missing = allowed - set(raw)
    if missing:
        raise SchemaError("missing_field", f"{label}: missing fields")


def _enum(value: Any, allowed: tuple[str, ...], name: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise SchemaError(f"invalid_{name}")
    return value


def _bounded_text(value: Any, name: str, limit: int, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise SchemaError(f"invalid_{name}")
    if (not value and not allow_empty) or len(value) > limit or "\x00" in value:
        raise SchemaError(f"invalid_{name}")
    return value


def _parse_findings(value: Any) -> tuple[Finding, ...]:
    if not isinstance(value, list):
        raise SchemaError("invalid_findings")
    if len(value) > MAX_FINDINGS:
        raise SchemaError("too_many_findings")
    findings: list[Finding] = []
    ids: set[str] = set()
    for item in value:
        finding = _parse_finding(item)
        if finding.id in ids:
            raise SchemaError("duplicate_finding_id")
        ids.add(finding.id)
        findings.append(finding)
    return tuple(findings)


def _parse_finding(value: Any) -> Finding:
    if not isinstance(value, dict):
        raise SchemaError("invalid_finding")
    _require_keys(
        value,
        {
            "id",
            "severity",
            "category",
            "claim",
            "description",
            "file",
            "line_start",
            "line_end",
            "confidence",
            "evidence_quote",
            "ci_run_id",
            "ci_job_id",
            "ci_status",
            "commit_sha",
            "recommendation",
        },
        "finding",
    )
    finding_id = value.get("id")
    if not isinstance(finding_id, str) or not _ID_RE.fullmatch(finding_id):
        raise SchemaError("invalid_finding_id")
    severity = _enum(value.get("severity"), SEVERITIES, "severity")
    category = _enum(value.get("category"), CATEGORIES, "category")
    confidence = _enum(value.get("confidence"), CONFIDENCES, "confidence")
    claim = _bounded_text(value.get("claim"), "claim", MAX_TITLE_CHARS)
    description = _bounded_text(value.get("description"), "description", MAX_DESCRIPTION_CHARS)
    file_path = _valid_path(value.get("file"))
    line_start = _line(value.get("line_start"), "line_start")
    line_end = _line(value.get("line_end"), "line_end")
    if line_end < line_start:
        raise SchemaError("invalid_line_range")
    quote = value.get("evidence_quote")
    if quote is not None:
        quote = _bounded_text(quote, "evidence_quote", MAX_QUOTE_CHARS)
    ci_run_id = _optional_positive_int(value.get("ci_run_id"), "ci_run_id")
    ci_job_id = _optional_positive_int(value.get("ci_job_id"), "ci_job_id")
    ci_status = value.get("ci_status")
    if ci_status is not None:
        ci_status = _enum(ci_status, CI_STATUSES, "ci_status")
    commit_sha = value.get("commit_sha")
    if commit_sha is not None:
        if not isinstance(commit_sha, str) or not _SHA_RE.fullmatch(commit_sha):
            raise SchemaError("invalid_commit_sha")
    recommendation = value.get("recommendation")
    if recommendation is not None:
        recommendation = _bounded_text(recommendation, "recommendation", 1_000)
    return Finding(
        id=finding_id,
        severity=severity,
        category=category,
        claim=claim,
        description=description,
        file=file_path,
        line_start=line_start,
        line_end=line_end,
        confidence=confidence,
        evidence_quote=quote,
        ci_run_id=ci_run_id,
        ci_job_id=ci_job_id,
        ci_status=ci_status,
        commit_sha=commit_sha,
        recommendation=recommendation,
    )


def _parse_challenges(value: Any) -> tuple[Challenge, ...]:
    if not isinstance(value, list):
        raise SchemaError("invalid_challenges")
    if len(value) > MAX_CHALLENGES:
        raise SchemaError("too_many_challenges")
    challenges: list[Challenge] = []
    ids: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            raise SchemaError("invalid_challenge")
        _require_keys(item, {"finding_id", "status", "reason"}, "challenge")
        finding_id = item.get("finding_id")
        if not isinstance(finding_id, str) or not _ID_RE.fullmatch(finding_id):
            raise SchemaError("invalid_challenge_finding_id")
        if finding_id in ids:
            raise SchemaError("duplicate_challenge_id")
        ids.add(finding_id)
        status = _enum(item.get("status"), CHALLENGE_STATUSES, "challenge_status")
        reason = _bounded_text(item.get("reason"), "challenge_reason", 1_000)
        challenges.append(Challenge(finding_id, status, reason))
    return tuple(challenges)


def _parse_reviewed_files(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise SchemaError("invalid_reviewed_files")
    if len(value) > MAX_REVIEWED_FILES:
        raise SchemaError("too_many_reviewed_files")
    files: list[str] = []
    seen: set[str] = set()
    for item in value:
        path = _valid_path(item)
        if path in seen:
            raise SchemaError("duplicate_reviewed_file")
        seen.add(path)
        files.append(path)
    return tuple(files)


def _parse_gaps(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise SchemaError("invalid_evidence_gaps")
    if len(value) > MAX_EVIDENCE_GAPS:
        raise SchemaError("too_many_evidence_gaps")
    return tuple(_bounded_text(item, "evidence_gap", 1_000) for item in value)


def _valid_path(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > MAX_PATH_CHARS:
        raise SchemaError("invalid_path")
    if value.startswith("/") or "\\" in value or "\x00" in value:
        raise SchemaError("invalid_path")
    if re.match(r"^[A-Za-z]:/", value):
        raise SchemaError("invalid_path")
    if any(part in ("", ".", "..") for part in value.split("/")):
        raise SchemaError("invalid_path")
    if any(ord(ch) < 32 for ch in value):
        raise SchemaError("invalid_path")
    return value


def _line(value: Any, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= MAX_LINE:
        raise SchemaError(f"invalid_{name}")
    return value


def _optional_positive_int(value: Any, name: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise SchemaError(f"invalid_{name}")
    return value
