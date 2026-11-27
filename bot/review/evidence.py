"""Evidence validation against the pinned diff and CI evidence (R4).

Model findings are untrusted. A finding is accepted only when its path, line range,
quote, commit SHA, and CI references can be verified against the supplied evidence.
R3's compare limitations are preserved: an incomplete diff never claims full coverage.
"""
from __future__ import annotations

import hashlib
import json
import re
import shlex
from dataclasses import dataclass
from urllib.parse import unquote

from bot.review.github import CompareResult, WorkflowJobsEvidence, WorkflowRunsEvidence
from bot.review.redact import redact_diff
from bot.review.schema import (
    STAGE_ADVERSARIAL,
    STAGE_BLIND,
    AdversarialReviewOutput,
    BlindReviewOutput,
    Finding,
)

MAX_PATH_CHARS = 512
_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class EvidenceError(ValueError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


@dataclass(frozen=True)
class DiffFileEvidence:
    path: str
    patch: str
    new_lines: frozenset[int]
    old_lines: frozenset[int]
    added_lines: frozenset[int]
    status: str = "included"

    def covers(self, line_start: int, line_end: int) -> bool:
        return all(line in self.new_lines for line in range(line_start, line_end + 1))


@dataclass(frozen=True)
class EvidenceProvenance:
    path: str
    line_start: int
    line_end: int
    commit_sha: str
    source: str = "diff"


@dataclass(frozen=True)
class ReviewEvidence:
    repository: str
    pr_number: int | None
    branch: str
    base_sha: str
    head_sha: str
    diff_text: str
    files: tuple[DiffFileEvidence, ...]
    excluded_paths: tuple[str, ...]
    secret_redactions: tuple[tuple[str, int], ...]
    ci_runs: WorkflowRunsEvidence | None
    ci_jobs: tuple[WorkflowJobsEvidence, ...]
    architecture_decisions: tuple[str, ...]
    sha_status: str  # verified | unverified
    coverage_complete: bool
    ci_jobs_complete: bool

    @property
    def files_by_path(self) -> dict[str, DiffFileEvidence]:
        return {item.path: item for item in self.files}

    @property
    def ci_state(self) -> str:
        if self.ci_runs is None or self.ci_runs.status != "verified":
            return "missing"
        return self.ci_runs.ci_state

    @property
    def secret_detected(self) -> bool:
        return bool(self.secret_redactions)

    @property
    def fingerprint(self) -> str:
        """Stable binding of the exact evidence set used for a review stage."""
        payload = {
            "repository": self.repository,
            "pr_number": self.pr_number,
            "branch": self.branch,
            "base_sha": self.base_sha,
            "head_sha": self.head_sha,
            "diff_sha256": hashlib.sha256(self.diff_text.encode("utf-8")).hexdigest(),
            "files": [
                [item.path, item.status, sorted(item.new_lines), sorted(item.old_lines)]
                for item in self.files
            ],
            "excluded_paths": list(self.excluded_paths),
            "secret_redactions": [list(item) for item in self.secret_redactions],
            "ci_runs": _ci_runs_fingerprint(self.ci_runs),
            "ci_jobs": [_ci_jobs_fingerprint(item) for item in self.ci_jobs],
            "architecture_decisions": list(self.architecture_decisions),
            "sha_status": self.sha_status,
            "coverage_complete": self.coverage_complete,
            "ci_jobs_complete": self.ci_jobs_complete,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def from_raw_diff(
        cls,
        *,
        repository: str,
        pr_number: int | None,
        branch: str,
        base_sha: str,
        head_sha: str,
        diff_text: str,
        max_input_chars: int,
        ci_runs: WorkflowRunsEvidence | None = None,
        ci_jobs: tuple[WorkflowJobsEvidence, ...] = (),
        architecture_decisions: tuple[str, ...] = (),
        sha_status: str = "unverified",
        ci_jobs_complete: bool | None = None,
    ) -> "ReviewEvidence":
        if not _valid_repo(repository):
            raise EvidenceError("invalid_repository")
        if not _sha(base_sha) or not _sha(head_sha):
            raise EvidenceError("invalid_sha")
        if sha_status not in ("verified", "unverified"):
            raise EvidenceError("invalid_sha_status")
        if not isinstance(diff_text, str):
            raise EvidenceError("invalid_diff")
        if (
            not isinstance(max_input_chars, int)
            or isinstance(max_input_chars, bool)
            or not 1 <= max_input_chars <= 1_000_000
        ):
            raise EvidenceError("invalid_input_limit")
        if ci_runs is not None and not isinstance(ci_runs, WorkflowRunsEvidence):
            raise EvidenceError("invalid_ci_evidence")
        if not isinstance(ci_jobs, tuple) or any(
            not isinstance(item, WorkflowJobsEvidence) for item in ci_jobs
        ):
            raise EvidenceError("invalid_ci_jobs")
        if not isinstance(architecture_decisions, tuple) or any(
            not isinstance(item, str) for item in architecture_decisions
        ):
            raise EvidenceError("invalid_architecture_decisions")
        try:
            redacted = redact_diff(
                diff_text,
                max_input_chars=max_input_chars,
                max_output_chars=max_input_chars,
            )
        except ValueError as exc:
            raise EvidenceError("diff_redaction_failed") from exc
        if redacted.status == "blocked":
            raise EvidenceError("diff_redaction_blocked")
        if redacted.status == "oversized":
            raise EvidenceError("diff_too_large")
        if redacted.status == "truncated":
            raise EvidenceError("diff_truncated")
        files = _parse_diff(redacted.text)
        _validate_ci(ci_runs, ci_jobs, head_sha)
        coverage_complete = not redacted.excluded_paths and (
            not diff_text or bool(files)
        )
        # Completeness requires a documented workflow contract. A caller that
        # cannot establish it must leave this false rather than infer success
        # from an arbitrary run/job shape.
        if ci_jobs_complete is None:
            ci_jobs_complete = False
        if not isinstance(ci_jobs_complete, bool):
            raise EvidenceError("invalid_ci_jobs_complete")
        return cls(
            repository=repository,
            pr_number=pr_number,
            branch=branch,
            base_sha=base_sha,
            head_sha=head_sha,
            diff_text=redacted.text,
            files=files,
            excluded_paths=tuple(redacted.excluded_paths),
            secret_redactions=tuple(redacted.redactions),
            ci_runs=ci_runs,
            ci_jobs=tuple(ci_jobs),
            architecture_decisions=tuple(architecture_decisions),
            sha_status=sha_status,
            coverage_complete=coverage_complete,
            ci_jobs_complete=ci_jobs_complete,
        )

    @classmethod
    def from_compare(
        cls,
        compare: CompareResult,
        *,
        diff_text: str,
        max_input_chars: int,
        branch: str,
        pr_number: int | None,
        ci_runs: WorkflowRunsEvidence | None = None,
        ci_jobs: tuple[WorkflowJobsEvidence, ...] = (),
        architecture_decisions: tuple[str, ...] = (),
        ci_jobs_complete: bool | None = None,
    ) -> "ReviewEvidence":
        if not isinstance(compare, CompareResult):
            raise EvidenceError("invalid_compare")
        if compare.status != "verified":
            raise EvidenceError("compare_not_verified")
        evidence = cls.from_raw_diff(
            repository=compare.repository,
            pr_number=pr_number,
            branch=branch,
            base_sha=compare.base_sha,
            head_sha=compare.head_sha,
            diff_text=diff_text,
            max_input_chars=max_input_chars,
            ci_runs=ci_runs,
            ci_jobs=ci_jobs,
            architecture_decisions=architecture_decisions,
            sha_status="verified",
            ci_jobs_complete=ci_jobs_complete,
        )
        compare_paths = {item.filename for item in compare.files if item.patch is not None}
        diff_paths = {item.path for item in evidence.files}
        if compare_paths != diff_paths:
            raise EvidenceError("diff_coverage_mismatch")
        return evidence


@dataclass(frozen=True)
class FindingValidation:
    finding: Finding
    accepted: bool
    reason: str | None = None
    provenance: EvidenceProvenance | None = None


@dataclass(frozen=True)
class StageEvidenceValidation:
    stage: str
    accepted: tuple[Finding, ...]
    rejected: tuple[FindingValidation, ...]
    reviewed_files: tuple[str, ...]
    evidence_gaps: tuple[str, ...]
    sha_status: str
    coverage_complete: bool
    stage_valid: bool
    invalid_reason: str | None = None

    @property
    def invalid_findings(self) -> int:
        return len(self.rejected)


def validate_stage_output(
    output: BlindReviewOutput | AdversarialReviewOutput,
    evidence: ReviewEvidence,
    *,
    expected_files: tuple[str, ...] | None = None,
) -> StageEvidenceValidation:
    stage = getattr(output, "stage", "")
    if stage not in (STAGE_BLIND, STAGE_ADVERSARIAL):
        return StageEvidenceValidation(
            stage, (), (), (), (), evidence.sha_status, False, False, "unsupported_stage"
        )
    if evidence.sha_status != "verified":
        return StageEvidenceValidation(
            stage,
            (),
            (),
            tuple(output.reviewed_files),
            tuple(output.evidence_gaps),
            evidence.sha_status,
            evidence.coverage_complete,
            False,
            "sha_unverified",
        )
    if not evidence.coverage_complete:
        return StageEvidenceValidation(
            stage,
            (),
            (),
            tuple(output.reviewed_files),
            tuple(output.evidence_gaps),
            evidence.sha_status,
            False,
            False,
            "diff_coverage_incomplete",
        )
    if output.evidence_gaps:
        return StageEvidenceValidation(
            stage,
            (),
            (),
            tuple(output.reviewed_files),
            tuple(output.evidence_gaps),
            evidence.sha_status,
            True,
            False,
            "model_evidence_gaps",
        )
    available = evidence.files_by_path
    expected = set(expected_files) if expected_files is not None else set(available)
    reviewed = set(output.reviewed_files)
    if reviewed != expected or not reviewed <= set(available) or (expected and not reviewed):
        return StageEvidenceValidation(
            stage,
            (),
            (),
            tuple(output.reviewed_files),
            tuple(output.evidence_gaps),
            evidence.sha_status,
            True,
            False,
            "reviewed_files_mismatch",
        )
    accepted: list[Finding] = []
    rejected: list[FindingValidation] = []
    for finding in output.findings:
        validation = _validate_finding(finding, evidence)
        if validation.accepted:
            accepted.append(finding)
        else:
            rejected.append(validation)
    stage_valid = not rejected
    return StageEvidenceValidation(
        stage=stage,
        accepted=tuple(accepted),
        rejected=tuple(rejected),
        reviewed_files=tuple(output.reviewed_files),
        evidence_gaps=tuple(output.evidence_gaps),
        sha_status=evidence.sha_status,
        coverage_complete=evidence.coverage_complete,
        stage_valid=stage_valid,
        invalid_reason=None if stage_valid else "invalid_findings",
    )


def validate_adversarial_binding(
    output: AdversarialReviewOutput,
    blind: BlindReviewOutput,
    evidence: ReviewEvidence,
    *,
    expected_files: tuple[str, ...] | None = None,
) -> StageEvidenceValidation:
    if output.blind_review_sha256 != blind.fingerprint:
        return StageEvidenceValidation(
            STAGE_ADVERSARIAL,
            (),
            (),
            tuple(output.reviewed_files),
            tuple(output.evidence_gaps),
            evidence.sha_status,
            evidence.coverage_complete,
            False,
            "blind_fingerprint_mismatch",
        )
    blind_ids = {item.id for item in blind.findings}
    for challenge in output.challenges:
        if challenge.finding_id not in blind_ids:
            return StageEvidenceValidation(
                STAGE_ADVERSARIAL,
                (),
                (),
                tuple(output.reviewed_files),
                tuple(output.evidence_gaps),
                evidence.sha_status,
                evidence.coverage_complete,
                False,
                "unknown_blind_finding_reference",
            )
    return validate_stage_output(output, evidence, expected_files=expected_files)


def diff_text_from_compare(compare: CompareResult) -> str:
    """Build a unified diff from a verified R3 compare result without network access."""
    if not isinstance(compare, CompareResult):
        raise EvidenceError("invalid_compare")
    if compare.status != "verified":
        raise EvidenceError("compare_not_verified")
    parts: list[str] = []
    for item in compare.files:
        if item.patch is None:
            continue
        old = "/dev/null" if item.status == "added" else f"a/{item.filename}"
        new = "/dev/null" if item.status == "removed" else f"b/{item.filename}"
        parts.append(
            f"diff --git a/{item.filename} b/{item.filename}\n"
            f"--- {old}\n+++ {new}\n{item.patch}\n"
        )
    return "".join(parts)


def _ci_runs_fingerprint(runs: WorkflowRunsEvidence | None) -> object:
    if runs is None:
        return None
    return {
        "repository": runs.repository,
        "head_sha": runs.head_sha,
        "status": runs.status,
        "ci_state": runs.ci_state,
        "observed_head_shas": list(runs.observed_head_shas),
        "runs": [
            [
                item.run_id,
                item.name,
                item.head_sha,
                item.head_branch,
                item.status,
                item.conclusion,
                item.event,
                item.run_attempt,
                item.created_at,
                item.updated_at,
            ]
            for item in runs.runs
        ],
    }


def _ci_jobs_fingerprint(group: WorkflowJobsEvidence) -> object:
    return {
        "repository": group.repository,
        "run_id": group.run_id,
        "head_sha": group.head_sha,
        "status": group.status,
        "observed_head_shas": list(group.observed_head_shas),
        "jobs": [
            [
                item.job_id,
                item.run_id,
                item.name,
                item.head_sha,
                item.status,
                item.conclusion,
                item.started_at,
                item.completed_at,
            ]
            for item in group.jobs
        ],
    }


def _validate_finding(finding: Finding, evidence: ReviewEvidence) -> FindingValidation:
    try:
        path = _normalize_path(finding.file)
    except EvidenceError:
        return FindingValidation(finding, False, "invalid_path")
    file_evidence = evidence.files_by_path.get(path)
    if file_evidence is None:
        return FindingValidation(finding, False, "file_not_in_diff")
    if file_evidence.status != "included":
        return FindingValidation(finding, False, "file_not_reviewable")
    if (
        not isinstance(finding.line_start, int)
        or isinstance(finding.line_start, bool)
        or not isinstance(finding.line_end, int)
        or isinstance(finding.line_end, bool)
        or finding.line_start < 1
        or finding.line_end < finding.line_start
    ):
        return FindingValidation(finding, False, "invalid_line_range")
    if not file_evidence.covers(finding.line_start, finding.line_end):
        return FindingValidation(finding, False, "line_not_in_diff")
    if finding.evidence_quote is not None and finding.evidence_quote not in file_evidence.patch:
        return FindingValidation(finding, False, "evidence_quote_not_found")
    if finding.commit_sha is not None and finding.commit_sha not in {
        evidence.base_sha,
        evidence.head_sha,
    }:
        return FindingValidation(finding, False, "commit_sha_mismatch")
    ci_reason = _validate_ci_claim(finding, evidence)
    if ci_reason is not None:
        return FindingValidation(finding, False, ci_reason)
    return FindingValidation(
        finding,
        True,
        provenance=EvidenceProvenance(
            path=path,
            line_start=finding.line_start,
            line_end=finding.line_end,
            commit_sha=finding.commit_sha or evidence.head_sha,
        ),
    )


def _validate_ci_claim(finding: Finding, evidence: ReviewEvidence) -> str | None:
    if finding.ci_run_id is None and finding.ci_job_id is None and finding.ci_status is None:
        return None
    if evidence.ci_runs is None or evidence.ci_runs.status != "verified":
        return "ci_evidence_missing"
    run = None
    if finding.ci_run_id is not None:
        run = next(
            (item for item in evidence.ci_runs.runs if item.run_id == finding.ci_run_id),
            None,
        )
        if run is None:
            return "ci_run_not_found"
    job = None
    if finding.ci_job_id is not None:
        job = next(
            (
                item
                for group in evidence.ci_jobs
                for item in group.jobs
                if item.job_id == finding.ci_job_id
            ),
            None,
        )
        if job is None:
            return "ci_job_not_found"
        if finding.ci_run_id is not None and job.run_id != finding.ci_run_id:
            return "ci_job_run_mismatch"
    if finding.ci_status is not None:
        if job is not None:
            actual = _conclusion(job.status, job.conclusion)
        elif run is not None:
            actual = _conclusion(run.status, run.conclusion)
        else:
            return "ci_claim_without_reference"
        if actual != finding.ci_status:
            return "ci_status_mismatch"
    return None


def _conclusion(status: str, conclusion: str | None) -> str:
    if status.lower() != "completed":
        return "pending"
    value = (conclusion or "").lower()
    if value in ("success", "failure", "cancelled", "skipped"):
        return value
    return "unknown"


def _validate_ci(
    runs: WorkflowRunsEvidence | None,
    jobs: tuple[WorkflowJobsEvidence, ...],
    head_sha: str,
) -> None:
    if runs is not None:
        if runs.status != "verified":
            raise EvidenceError("ci_not_verified")
        if runs.head_sha != head_sha or any(item.head_sha != head_sha for item in runs.runs):
            raise EvidenceError("ci_sha_mismatch")
    run_ids = {item.run_id for item in runs.runs} if runs is not None else set()
    for group in jobs:
        if group.status != "verified" or group.head_sha != head_sha:
            raise EvidenceError("ci_jobs_not_verified")
        for job in group.jobs:
            if job.head_sha != head_sha or job.run_id not in run_ids:
                raise EvidenceError("ci_job_mismatch")


def _parse_diff(diff_text: str) -> tuple[DiffFileEvidence, ...]:
    if not diff_text:
        return ()
    sections = _split_sections(diff_text)
    files: list[DiffFileEvidence] = []
    seen: set[str] = set()
    for section in sections:
        parsed = _parse_section(section)
        if parsed is None:
            continue
        if parsed.path in seen:
            raise EvidenceError("duplicate_diff_path")
        seen.add(parsed.path)
        files.append(parsed)
    if diff_text and not files:
        raise EvidenceError("diff_unparseable")
    return tuple(files)


def _split_sections(diff_text: str) -> list[str]:
    lines = diff_text.splitlines(keepends=True)
    sections: list[str] = []
    current: list[str] = []
    for line in lines:
        if line.startswith("diff --git "):
            if current:
                sections.append("".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("".join(current))
    return sections


def _parse_section(section: str) -> DiffFileEvidence | None:
    old_path: str | None = None
    new_path: str | None = None
    binary = False
    hunk_seen = False
    for line in section.splitlines():
        if _HUNK_RE.match(line):
            hunk_seen = True
            continue
        if hunk_seen:
            continue
        if line.startswith("diff --git "):
            paths = _header_paths(line[len("diff --git ") :])
            if paths is not None:
                old_path, new_path = paths
        elif line.startswith("--- "):
            old_path = _header_path(line[4:])
        elif line.startswith("+++ "):
            new_path = _header_path(line[4:])
        elif line.startswith("Binary files ") or line.startswith("GIT binary patch"):
            binary = True
    path = new_path or old_path
    if path is None:
        return None
    path = _normalize_path(path)
    new_lines: set[int] = set()
    old_lines: set[int] = set()
    added_lines: set[int] = set()
    old_no = new_no = 0
    old_remaining = new_remaining = 0
    in_hunk = False
    for line in section.splitlines():
        match = _HUNK_RE.match(line)
        if match:
            if in_hunk and (old_remaining or new_remaining):
                raise EvidenceError("diff_hunk_count_mismatch")
            old_no = int(match.group(1))
            new_no = int(match.group(3))
            old_remaining = int(match.group(2)) if match.group(2) is not None else 1
            new_remaining = int(match.group(4)) if match.group(4) is not None else 1
            in_hunk = True
            continue
        if not in_hunk:
            continue
        if line.startswith("+"):
            if new_remaining <= 0:
                raise EvidenceError("diff_hunk_count_mismatch")
            new_lines.add(new_no)
            added_lines.add(new_no)
            new_no += 1
            new_remaining -= 1
        elif line.startswith("-"):
            if old_remaining <= 0:
                raise EvidenceError("diff_hunk_count_mismatch")
            old_lines.add(old_no)
            old_no += 1
            old_remaining -= 1
        elif line.startswith(" "):
            if old_remaining <= 0 or new_remaining <= 0:
                raise EvidenceError("diff_hunk_count_mismatch")
            old_lines.add(old_no)
            new_lines.add(new_no)
            old_no += 1
            new_no += 1
            old_remaining -= 1
            new_remaining -= 1
        elif line.startswith("\\"):
            continue
    if in_hunk and (old_remaining or new_remaining):
        raise EvidenceError("diff_hunk_count_mismatch")
    return DiffFileEvidence(
        path=path,
        patch=section,
        new_lines=frozenset(new_lines),
        old_lines=frozenset(old_lines),
        added_lines=frozenset(added_lines),
        status="binary" if binary else "included",
    )


def _header_paths(raw: str) -> tuple[str, str] | None:
    try:
        parts = shlex.split(raw)
    except ValueError:
        return None
    if len(parts) != 2:
        return None
    return _strip_prefix(parts[0]), _strip_prefix(parts[1])


def _header_path(raw: str) -> str | None:
    value = raw.split("\t", 1)[0].strip()
    if value == "/dev/null":
        return None
    return _strip_prefix(_strip_quotes(value))


def _strip_prefix(value: str) -> str:
    if value.startswith(("a/", "b/")):
        return value[2:]
    return value


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def _normalize_path(raw: str | None) -> str:
    if not isinstance(raw, str):
        raise EvidenceError("missing_path")
    value = unquote(unquote(raw)).replace("\\", "/")
    if not value or value.startswith("/") or re.match(r"^[A-Za-z]:/", value):
        raise EvidenceError("invalid_path")
    if value.startswith(("a/", "b/")):
        value = value[2:]
    parts: list[str] = []
    for part in value.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            raise EvidenceError("invalid_path")
        parts.append(part)
    normalized = "/".join(parts)
    if (
        not normalized
        or len(normalized) > MAX_PATH_CHARS
        or any(ord(ch) < 32 for ch in normalized)
    ):
        raise EvidenceError("invalid_path")
    return normalized


def _valid_repo(value: str) -> bool:
    if not isinstance(value, str):
        return False
    parts = value.split("/")
    return len(parts) == 2 and all(
        part and part not in (".", "..") and all(ch.isalnum() or ch in "_.-" for ch in part)
        for part in parts
    )


def _sha(value: str) -> bool:
    return isinstance(value, str) and len(value) == 40 and all(
        ch in "0123456789abcdef" for ch in value
    )
