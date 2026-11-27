"""Isolated two-stage review cycle orchestration (R4).

This is a pure in-process pipeline: explicit evidence in, structured stage results
and a deterministic verdict out. It is not a worker, does not select scope, does
not reserve reviews, and does not activate runtime behavior.
"""
from __future__ import annotations

from dataclasses import dataclass

from bot.review.evidence import (
    ReviewEvidence,
    StageEvidenceValidation,
    validate_adversarial_binding,
    validate_stage_output,
)
from bot.review.llm import ReviewProvider, StageExecution, execute_stage
from bot.review.prompts import (
    AdversarialReviewInput,
    BlindReviewInput,
    PromptBuildError,
    build_adversarial_requests,
    build_blind_requests,
)
from bot.review.schema import (
    STAGE_ADVERSARIAL,
    STAGE_BLIND,
    AdversarialReviewOutput,
    BlindReviewOutput,
    SCHEMA_VERSION,
    Challenge,
    Finding,
)
from bot.review.verdict import VerdictResult, evaluate_verdict


@dataclass(frozen=True)
class ReviewCycleResult:
    verdict: VerdictResult
    blind_execution: StageExecution | None
    adversarial_execution: StageExecution | None
    blind_output: BlindReviewOutput | None
    adversarial_output: AdversarialReviewOutput | None
    blind_validation: StageEvidenceValidation
    adversarial_validation: StageEvidenceValidation
    request_fingerprints: tuple[str, ...]
    error_code: str | None = None


async def run_review_cycle(
    adapter: ReviewProvider,
    *,
    evidence: ReviewEvidence,
    implementation_report: str,
    max_input_chars: int,
    review_instructions: tuple[str, ...] = (),
) -> ReviewCycleResult:
    if not isinstance(implementation_report, str):
        return _blocked(evidence, "invalid_implementation_report", ())
    blind_input = BlindReviewInput(
        repository=evidence.repository,
        pr_number=evidence.pr_number,
        branch=evidence.branch,
        base_sha=evidence.base_sha,
        head_sha=evidence.head_sha,
        diff_text=evidence.diff_text,
        ci_runs=evidence.ci_runs,
        ci_jobs=evidence.ci_jobs,
        architecture_decisions=evidence.architecture_decisions,
        review_instructions=review_instructions,
    )
    try:
        blind_requests = build_blind_requests(
            blind_input, max_input_chars=max_input_chars
        )
    except PromptBuildError:
        return _blocked(evidence, "blind_prompt_build_failed", ())
    blind_runs: list[StageExecution] = []
    for request in blind_requests:
        execution = await execute_stage(adapter, request)
        blind_runs.append(execution)
        if not execution.ok:
            return _stage_failure(evidence, execution, None, "blind_stage_failed")
    blind_output = _combine_blind(blind_runs)
    if blind_output is None:
        return _blocked(evidence, "blind_output_combine_failed", tuple(
            item.request_fingerprint for item in blind_runs
        ))
    blind_validation = validate_stage_output(blind_output, evidence)
    if not blind_validation.stage_valid:
        return _validation_failure(
            evidence,
            blind_runs,
            None,
            blind_output,
            None,
            blind_validation,
            _empty_validation(STAGE_ADVERSARIAL, evidence, "adversarial_not_run"),
            "blind_evidence_failed",
        )

    adversarial_input = AdversarialReviewInput(
        repository=evidence.repository,
        pr_number=evidence.pr_number,
        branch=evidence.branch,
        base_sha=evidence.base_sha,
        head_sha=evidence.head_sha,
        diff_text=evidence.diff_text,
        ci_runs=evidence.ci_runs,
        ci_jobs=evidence.ci_jobs,
        architecture_decisions=evidence.architecture_decisions,
        review_instructions=review_instructions,
        implementation_report=implementation_report,
        blind_result=blind_output,
        blind_fingerprint=blind_output.fingerprint,
    )
    try:
        adversarial_requests = build_adversarial_requests(
            adversarial_input, max_input_chars=max_input_chars
        )
    except PromptBuildError:
        return _validation_failure(
            evidence,
            blind_runs,
            None,
            blind_output,
            None,
            blind_validation,
            _empty_validation(STAGE_ADVERSARIAL, evidence, "adversarial_prompt_build_failed"),
            "adversarial_prompt_build_failed",
        )
    adversarial_runs: list[StageExecution] = []
    for request in adversarial_requests:
        execution = await execute_stage(adapter, request)
        adversarial_runs.append(execution)
        if not execution.ok:
            return _stage_failure(
                evidence,
                None,
                execution,
                "adversarial_stage_failed",
                blind_output,
                blind_validation,
            )
    adversarial_output = _combine_adversarial(adversarial_runs, blind_output)
    if adversarial_output is None:
        return _validation_failure(
            evidence,
            blind_runs,
            adversarial_runs,
            blind_output,
            None,
            blind_validation,
            _empty_validation(STAGE_ADVERSARIAL, evidence, "adversarial_output_combine_failed"),
            "adversarial_output_combine_failed",
        )
    adversarial_validation = validate_adversarial_binding(
        adversarial_output, blind_output, evidence
    )
    verdict = evaluate_verdict(
        evidence=evidence,
        blind_validation=blind_validation,
        adversarial_validation=adversarial_validation,
        blind_stage_ok=True,
        adversarial_stage_ok=True,
        blind_assessment=blind_output.assessment,
        adversarial_assessment=adversarial_output.assessment,
    )
    return ReviewCycleResult(
        verdict=verdict,
        blind_execution=blind_runs[-1] if blind_runs else None,
        adversarial_execution=adversarial_runs[-1] if adversarial_runs else None,
        blind_output=blind_output,
        adversarial_output=adversarial_output,
        blind_validation=blind_validation,
        adversarial_validation=adversarial_validation,
        request_fingerprints=tuple(
            item.request_fingerprint for item in (*blind_runs, *adversarial_runs)
        ),
    )


def _combine_blind(runs: list[StageExecution]) -> BlindReviewOutput | None:
    findings: list[Finding] = []
    files: list[str] = []
    gaps: list[str] = []
    summaries: list[str] = []
    ids: set[str] = set()
    assessments: list[str] = []
    for run in runs:
        output = run.output
        if not isinstance(output, BlindReviewOutput):
            return None
        for finding in output.findings:
            if finding.id in ids:
                return None
            ids.add(finding.id)
            findings.append(finding)
        for path in output.reviewed_files:
            if path not in files:
                files.append(path)
        gaps.extend(output.evidence_gaps)
        summaries.append(output.summary)
        assessments.append(output.assessment)
    if "insufficient_evidence" in assessments:
        assessment = "insufficient_evidence"
    elif findings:
        assessment = "findings"
    else:
        assessment = "clean"
    summary = " | ".join(summaries)
    if len(summary) > 4_000:
        return None
    return BlindReviewOutput(
        schema_version=SCHEMA_VERSION,
        stage=STAGE_BLIND,
        assessment=assessment,
        summary=summary,
        findings=tuple(findings),
        reviewed_files=tuple(files),
        evidence_gaps=tuple(gaps),
    )


def _combine_adversarial(
    runs: list[StageExecution], blind: BlindReviewOutput
) -> AdversarialReviewOutput | None:
    findings: list[Finding] = []
    files: list[str] = []
    gaps: list[str] = []
    summaries: list[str] = []
    challenges: list[Challenge] = []
    ids: set[str] = set()
    challenge_ids: set[str] = set()
    assessments: list[str] = []
    for run in runs:
        output = run.output
        if not isinstance(output, AdversarialReviewOutput):
            return None
        if output.blind_review_sha256 != blind.fingerprint:
            return None
        for finding in output.findings:
            if finding.id in ids:
                return None
            ids.add(finding.id)
            findings.append(finding)
        for challenge in output.challenges:
            if challenge.finding_id in challenge_ids:
                return None
            challenge_ids.add(challenge.finding_id)
            challenges.append(challenge)
        for path in output.reviewed_files:
            if path not in files:
                files.append(path)
        gaps.extend(output.evidence_gaps)
        summaries.append(output.summary)
        assessments.append(output.assessment)
    if "insufficient_evidence" in assessments:
        assessment = "insufficient_evidence"
    elif "dissent" in assessments:
        assessment = "dissent"
    else:
        assessment = "concur"
    summary = " | ".join(summaries)
    if len(summary) > 4_000:
        return None
    return AdversarialReviewOutput(
        schema_version=SCHEMA_VERSION,
        stage=STAGE_ADVERSARIAL,
        blind_review_sha256=blind.fingerprint,
        assessment=assessment,
        summary=summary,
        findings=tuple(findings),
        challenges=tuple(challenges),
        reviewed_files=tuple(files),
        evidence_gaps=tuple(gaps),
    )


def _stage_failure(
    evidence: ReviewEvidence,
    blind_execution: StageExecution | None,
    adversarial_execution: StageExecution | None,
    code: str,
    blind_output: BlindReviewOutput | None = None,
    blind_validation: StageEvidenceValidation | None = None,
) -> ReviewCycleResult:
    blind_val = blind_validation or _empty_validation(STAGE_BLIND, evidence, code)
    adv_val = _empty_validation(STAGE_ADVERSARIAL, evidence, "adversarial_not_run")
    verdict = evaluate_verdict(
        evidence=evidence,
        blind_validation=blind_val,
        adversarial_validation=adv_val,
        blind_stage_ok=False,
        adversarial_stage_ok=False,
        blind_assessment=getattr(blind_output, "assessment", None),
        adversarial_assessment=None,
    )
    return ReviewCycleResult(
        verdict=verdict,
        blind_execution=blind_execution,
        adversarial_execution=adversarial_execution,
        blind_output=blind_output,
        adversarial_output=None,
        blind_validation=blind_val,
        adversarial_validation=adv_val,
        request_fingerprints=tuple(
            item.request_fingerprint
            for item in (blind_execution, adversarial_execution)
            if item is not None
        ),
        error_code=code,
    )


def _validation_failure(
    evidence: ReviewEvidence,
    blind_runs: list[StageExecution],
    adversarial_runs: list[StageExecution] | None,
    blind_output: BlindReviewOutput | None,
    adversarial_output: AdversarialReviewOutput | None,
    blind_validation: StageEvidenceValidation,
    adversarial_validation: StageEvidenceValidation,
    code: str,
) -> ReviewCycleResult:
    verdict = evaluate_verdict(
        evidence=evidence,
        blind_validation=blind_validation,
        adversarial_validation=adversarial_validation,
        blind_stage_ok=True,
        adversarial_stage_ok=False,
        blind_assessment=getattr(blind_output, "assessment", None),
        adversarial_assessment=getattr(adversarial_output, "assessment", None),
    )
    return ReviewCycleResult(
        verdict=verdict,
        blind_execution=blind_runs[-1] if blind_runs else None,
        adversarial_execution=(
            adversarial_runs[-1] if adversarial_runs else None
        ),
        blind_output=blind_output,
        adversarial_output=adversarial_output,
        blind_validation=blind_validation,
        adversarial_validation=adversarial_validation,
        request_fingerprints=tuple(
            item.request_fingerprint for item in (*blind_runs, *(adversarial_runs or []))
        ),
        error_code=code,
    )


def _blocked(
    evidence: ReviewEvidence, code: str, fingerprints: tuple[str, ...]
) -> ReviewCycleResult:
    blind_val = _empty_validation(STAGE_BLIND, evidence, code)
    adv_val = _empty_validation(STAGE_ADVERSARIAL, evidence, code)
    verdict = evaluate_verdict(
        evidence=evidence,
        blind_validation=blind_val,
        adversarial_validation=adv_val,
        blind_stage_ok=False,
        adversarial_stage_ok=False,
        blind_assessment=None,
        adversarial_assessment=None,
    )
    return ReviewCycleResult(
        verdict=verdict,
        blind_execution=None,
        adversarial_execution=None,
        blind_output=None,
        adversarial_output=None,
        blind_validation=blind_val,
        adversarial_validation=adv_val,
        request_fingerprints=fingerprints,
        error_code=code,
    )


def _empty_validation(
    stage: str, evidence: ReviewEvidence, reason: str
) -> StageEvidenceValidation:
    return StageEvidenceValidation(
        stage=stage,
        accepted=(),
        rejected=(),
        reviewed_files=(),
        evidence_gaps=(),
        sha_status=evidence.sha_status,
        coverage_complete=evidence.coverage_complete,
        stage_valid=False,
        invalid_reason=reason,
    )
