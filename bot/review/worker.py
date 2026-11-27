"""R5 durable review orchestration and worker.

The worker is intentionally not started by ``bot.app``. A caller must explicitly
construct and start it; this keeps R5 local verification free of real provider,
GitHub, or Telegram traffic. Delivery is always delegated to the existing outbox.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone

from bot.db import (
    AUTO_REVIEW_LIFECYCLE_ACTIVE,
    AUTO_REVIEW_LIFECYCLE_DELIVERY_PENDING,
    AUTO_REVIEW_LIFECYCLE_RETRY_WAIT,
    AUTO_REVIEW_STAGE_ADVERSARIAL,
    AUTO_REVIEW_STAGE_ADVERSARIAL_VALIDATED,
    AUTO_REVIEW_STAGE_BLIND,
    AUTO_REVIEW_STAGE_BLIND_VALIDATED,
    AutoReviewClaim,
    AutoReviewConflict,
    AutoReviewLeaseLost,
    AutoReviewMembership,
    Database,
)
from bot.outbox import _BaseWorker
from bot.review.authorization import (
    AUTHORIZATION_DATABASE_UNAVAILABLE,
    ReviewAuthorizationError,
    revalidate_review_authorization,
)
from bot.review.collector import EvidenceCollectionError, ReviewEvidenceCollector
from bot.review.engine import _combine_adversarial, _combine_blind
from bot.review.evidence import (
    EvidenceError,
    ReviewEvidence,
    StageEvidenceValidation,
    validate_adversarial_binding,
    validate_stage_output,
)
from bot.review.llm import (
    ProviderBinding,
    ReviewProvider,
    StageExecution,
    execute_stage,
)
from bot.review.prompts import (
    AdversarialReviewInput,
    BlindReviewInput,
    PromptBuildError,
    build_adversarial_requests,
    build_blind_requests,
)
from bot.review.redact import redact_text
from bot.review.schema import (
    AdversarialReviewOutput,
    BlindReviewOutput,
    SchemaError,
    output_json,
    parse_adversarial_review,
    parse_blind_review,
)
from bot.review.verdict import (
    VERDICT_BLOCKED,
    VERDICT_FAIL,
    VERDICT_PASS,
    VERDICT_PASS_WITH_NOTES,
    VerdictResult,
    evaluate_verdict,
)

log = logging.getLogger(__name__)

MAX_DELIVERY_TEXT = 10_000
MAX_STAGE_JSON = 400_000


class ReviewPipelineError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


class ReviewRunner:
    """Run one claimed cycle through R3 evidence and the R4 stage primitives."""

    def __init__(
        self,
        db: Database,
        provider: ReviewProvider,
        collector: ReviewEvidenceCollector,
        *,
        max_input_chars: int,
        architecture_decisions: tuple[str, ...] = (),
        review_instructions: tuple[str, ...] = (),
        lease_seconds: int = 300,
        clock=None,
        report_service=None,
        provider_binding: ProviderBinding | None = None,
        owner_id: int | None = None,
    ) -> None:
        self._db = db
        self._provider = provider
        self._collector = collector
        self._report_service = report_service
        self._provider_binding = provider_binding
        self._max_input_chars = max_input_chars
        self._architecture_decisions = tuple(architecture_decisions)
        self._review_instructions = tuple(review_instructions)
        self._lease_seconds = lease_seconds
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._owner_id = owner_id

    def _now(self) -> str:
        return self._clock().isoformat()

    def _renew(self, claim: AutoReviewClaim) -> None:
        if not self._db.renew_auto_review_lease(
            claim.review_id,
            claim.lease_token,
            now=self._now(),
            lease_seconds=self._lease_seconds,
        ):
            raise AutoReviewLeaseLost("lease lost")

    def _authorize(self, claim: AutoReviewClaim) -> None:
        """Re-read the current owner/cycle relationships at this boundary.

        Never reuse a cycle object read earlier in the run: owner or watched state
        may have changed while evidence collection or a provider call was in flight.
        """
        try:
            cycle = self._db.get_auto_review(claim.review_id)
        except Exception as exc:  # noqa: BLE001 - never authorize from a failed read
            raise ReviewPipelineError(
                AUTHORIZATION_DATABASE_UNAVAILABLE, retryable=True
            ) from exc
        try:
            revalidate_review_authorization(
                self._db,
                owner_id=self._owner_id,
                cycle=cycle,
                phase="execution",
            )
        except ReviewAuthorizationError as exc:
            raise ReviewPipelineError(exc.code, retryable=exc.retryable) from exc

    async def run(self, claim: AutoReviewClaim) -> VerdictResult:
        cycle = self._db.get_auto_review(claim.review_id)
        if cycle is None or not cycle.conversation_wide:
            raise ReviewPipelineError("invalid_conversation_wide_cycle", retryable=False)
        self._authorize(claim)
        self._verify_provider_binding(cycle)
        memberships = self._db.get_auto_review_memberships(cycle.id)
        if not memberships or len(memberships) != cycle.membership_count:
            raise ReviewPipelineError("membership_snapshot_invalid", retryable=False)
        outcomes: list[VerdictResult] = []
        for membership in memberships:
            self._renew(claim)
            self._authorize(claim)
            evidence = await self._collect(membership)
            self._verify_membership_evidence(membership, evidence)
            self._persist_evidence(claim, membership, evidence)
            outcomes.append(await self._run_membership(claim, cycle, membership, evidence))
        aggregate = _aggregate(outcomes)
        text = _delivery_text(cycle, memberships, outcomes, aggregate)
        self._renew(claim)
        self._authorize(claim)
        self._db.complete_auto_review(
            claim.review_id,
            lease_token=claim.lease_token,
            lease_epoch=claim.lease_epoch,
            verdict=aggregate.verdict,
            report_ref=f"review:{claim.review_id}:{aggregate.verdict}",
            delivery_text=text,
            now=self._now(),
        )
        try:
            if self._report_service is not None:
                self._report_service.prepare(claim.review_id, now=self._now())
            else:
                self._db.schedule_auto_review_delivery(claim.review_id, now=self._now())
        except Exception:
            # The verdict is durable; the cycle remains delivery_pending and is
            # recovered by ReviewWorker._claim on the next tick.
            log.exception("failed to prepare review delivery for %s", claim.review_id)
            raise
        return aggregate

    def _verify_provider_binding(self, cycle) -> None:
        binding = self._provider_binding
        if binding is None:
            raise ReviewPipelineError("provider_binding_required", retryable=False)
        snapshot = self._db.get_auto_review_provider_snapshot(cycle.provider_snapshot_id)
        if snapshot is None:
            raise ReviewPipelineError("provider_snapshot_missing", retryable=False)
        bound = binding.snapshot
        if (
            bound.provider != snapshot.provider
            or bound.api_base != snapshot.api_base
            or bound.model != snapshot.model
            or bound.config_fingerprint != snapshot.config_fingerprint
        ):
            raise ReviewPipelineError("provider_binding_mismatch", retryable=False)
        if bound.snapshot_id != snapshot.id:
            raise ReviewPipelineError("provider_binding_cycle_mismatch", retryable=False)
        adapter_binding = getattr(self._provider, "binding", None)
        if adapter_binding is not None and adapter_binding != binding:
            raise ReviewPipelineError("provider_adapter_binding_mismatch", retryable=False)

    async def _collect(self, membership: AutoReviewMembership) -> ReviewEvidence:
        try:
            evidence = await self._collector.collect(
                membership,
                architecture_decisions=self._architecture_decisions,
                max_input_chars=self._max_input_chars,
            )
        except EvidenceCollectionError as exc:
            retryable = not exc.code.startswith(
                ("compare_", "diff_", "evidence_", "ci_", "invalid_")
            )
            raise ReviewPipelineError(exc.code, retryable=retryable) from exc
        except EvidenceError as exc:
            raise ReviewPipelineError(exc.code, retryable=False) from exc
        except Exception as exc:  # collector must not leak details
            raise ReviewPipelineError(
                f"collector_{type(exc).__name__}", retryable=True
            ) from exc
        if not isinstance(evidence, ReviewEvidence):
            raise ReviewPipelineError("invalid_collected_evidence", retryable=False)
        return evidence

    @staticmethod
    def _verify_membership_evidence(
        membership: AutoReviewMembership, evidence: ReviewEvidence
    ) -> None:
        if (
            evidence.repository.casefold() != membership.repository_full_name.casefold()
            or evidence.pr_number != membership.pr_number
            or evidence.base_sha != membership.base_sha
            or evidence.head_sha != membership.head_sha
            or evidence.branch != membership.branch
        ):
            raise ReviewPipelineError("evidence_membership_mismatch", retryable=False)

    def _persist_evidence(
        self,
        claim: AutoReviewClaim,
        membership: AutoReviewMembership,
        evidence: ReviewEvidence,
    ) -> None:
        payload = {
            "repository": evidence.repository,
            "pr_number": evidence.pr_number,
            "branch": evidence.branch,
            "base_sha": evidence.base_sha,
            "head_sha": evidence.head_sha,
            "sha_status": evidence.sha_status,
            "coverage_complete": evidence.coverage_complete,
            "excluded_paths": list(evidence.excluded_paths),
            "secret_redactions": [list(item) for item in evidence.secret_redactions],
            "ci_state": evidence.ci_state,
            "ci_jobs_complete": evidence.ci_jobs_complete,
            "files": [
                [item.path, item.status, len(item.new_lines), len(item.old_lines)]
                for item in evidence.files
            ],
            "ci_runs": [
                [item.run_id, item.name, item.status, item.conclusion]
                for item in (evidence.ci_runs.runs if evidence.ci_runs else ())
            ],
        }
        text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        scan = redact_text(text, max_input_chars=100_000)
        if scan.status != "ok" or scan.redactions:
            raise ReviewPipelineError("secret_in_evidence", retryable=False)
        try:
            self._db.save_auto_review_evidence(
                claim.review_id,
                membership,
                lease_token=claim.lease_token,
                lease_epoch=claim.lease_epoch,
                evidence_sha256=evidence.fingerprint,
                diff_sha256=hashlib.sha256(
                    evidence.diff_text.encode("utf-8")
                ).hexdigest(),
                coverage_complete=evidence.coverage_complete,
                ci_state=evidence.ci_state,
                evidence_json=text,
                now=self._now(),
            )
        except AutoReviewConflict as exc:
            raise ReviewPipelineError("evidence_conflict", retryable=False) from exc

    async def _run_membership(
        self,
        claim: AutoReviewClaim,
        cycle,
        membership: AutoReviewMembership,
        evidence: ReviewEvidence,
    ) -> VerdictResult:
        blind_output, blind_validation = await self._blind(
            claim, cycle, membership, evidence
        )
        adversarial_output, adversarial_validation = await self._adversarial(
            claim, cycle, membership, evidence, blind_output, blind_validation
        )
        return evaluate_verdict(
            evidence=evidence,
            blind_validation=blind_validation,
            adversarial_validation=adversarial_validation,
            blind_stage_ok=True,
            adversarial_stage_ok=True,
            blind_assessment=blind_output.assessment,
            adversarial_assessment=adversarial_output.assessment,
        )

    async def _blind(
        self,
        claim: AutoReviewClaim,
        cycle,
        membership: AutoReviewMembership,
        evidence: ReviewEvidence,
    ) -> tuple[BlindReviewOutput, StageEvidenceValidation]:
        self._renew(claim)
        self._authorize(claim)
        stored = self._db.get_auto_review_stage(
            claim.review_id, membership.repository_id, membership.pr_number, "blind"
        )
        if stored is not None and stored.status == "validated":
            if stored.evidence_sha256 != evidence.fingerprint:
                raise ReviewPipelineError("stale_blind_evidence", retryable=False)
            try:
                output = parse_blind_review(stored.output_json or "")
            except SchemaError as exc:
                raise ReviewPipelineError("stored_blind_invalid", retryable=False) from exc
            validation = validate_stage_output(output, evidence)
            if not validation.stage_valid:
                raise ReviewPipelineError("stored_blind_evidence_invalid", retryable=False)
            self._advance(claim, AUTO_REVIEW_STAGE_BLIND_VALIDATED)
            return output, validation
        self._begin(claim, AUTO_REVIEW_STAGE_BLIND)
        review_input = BlindReviewInput(
            repository=evidence.repository,
            pr_number=membership.pr_number,
            branch=membership.branch,
            base_sha=membership.base_sha,
            head_sha=membership.head_sha,
            diff_text=evidence.diff_text,
            ci_runs=evidence.ci_runs,
            ci_jobs=evidence.ci_jobs,
            architecture_decisions=self._architecture_decisions,
            review_instructions=self._review_instructions,
        )
        try:
            requests = build_blind_requests(
                review_input, max_input_chars=self._max_input_chars
            )
        except PromptBuildError as exc:
            raise ReviewPipelineError("blind_prompt_build_failed", retryable=False) from exc
        executions = await self._execute_requests(claim, requests, "blind")
        output = _combine_blind(executions)
        if output is None:
            raise ReviewPipelineError("blind_combine_failed", retryable=False)
        validation = validate_stage_output(output, evidence)
        if not validation.stage_valid:
            self._save_stage(
                claim,
                membership,
                "blind",
                "invalid",
                evidence.fingerprint,
                output_json(output),
                validation,
            )
            raise ReviewPipelineError("blind_evidence_failed", retryable=False)
        self._save_stage(
            claim,
            membership,
            "blind",
            "validated",
            evidence.fingerprint,
            output_json(output),
            validation,
        )
        self._advance(claim, AUTO_REVIEW_STAGE_BLIND_VALIDATED)
        return output, validation

    async def _adversarial(
        self,
        claim: AutoReviewClaim,
        cycle,
        membership: AutoReviewMembership,
        evidence: ReviewEvidence,
        blind_output: BlindReviewOutput,
        blind_validation: StageEvidenceValidation,
    ) -> tuple[AdversarialReviewOutput, StageEvidenceValidation]:
        self._renew(claim)
        self._authorize(claim)
        stored = self._db.get_auto_review_stage(
            claim.review_id, membership.repository_id, membership.pr_number, "adversarial"
        )
        if stored is not None and stored.status == "validated":
            if stored.evidence_sha256 != evidence.fingerprint:
                raise ReviewPipelineError("stale_adversarial_evidence", retryable=False)
            try:
                output = parse_adversarial_review(stored.output_json or "")
            except SchemaError as exc:
                raise ReviewPipelineError("stored_adversarial_invalid", retryable=False) from exc
            validation = validate_adversarial_binding(output, blind_output, evidence)
            if not validation.stage_valid:
                raise ReviewPipelineError(
                    "stored_adversarial_evidence_invalid", retryable=False
                )
            self._advance(claim, AUTO_REVIEW_STAGE_ADVERSARIAL_VALIDATED)
            return output, validation
        self._begin(claim, AUTO_REVIEW_STAGE_ADVERSARIAL)
        review_input = AdversarialReviewInput(
            repository=evidence.repository,
            pr_number=membership.pr_number,
            branch=membership.branch,
            base_sha=membership.base_sha,
            head_sha=membership.head_sha,
            diff_text=evidence.diff_text,
            ci_runs=evidence.ci_runs,
            ci_jobs=evidence.ci_jobs,
            architecture_decisions=self._architecture_decisions,
            review_instructions=self._review_instructions,
            implementation_report=cycle.implementation_report,
            blind_result=blind_output,
            blind_fingerprint=blind_output.fingerprint,
        )
        try:
            requests = build_adversarial_requests(
                review_input, max_input_chars=self._max_input_chars
            )
        except PromptBuildError as exc:
            raise ReviewPipelineError("adversarial_prompt_build_failed", retryable=False) from exc
        executions = await self._execute_requests(claim, requests, "adversarial")
        output = _combine_adversarial(executions, blind_output)
        if output is None:
            raise ReviewPipelineError("adversarial_combine_failed", retryable=False)
        validation = validate_adversarial_binding(output, blind_output, evidence)
        if not validation.stage_valid:
            self._save_stage(
                claim,
                membership,
                "adversarial",
                "invalid",
                evidence.fingerprint,
                output_json(output),
                validation,
            )
            raise ReviewPipelineError("adversarial_evidence_failed", retryable=False)
        self._save_stage(
            claim,
            membership,
            "adversarial",
            "validated",
            evidence.fingerprint,
            output_json(output),
            validation,
        )
        self._advance(claim, AUTO_REVIEW_STAGE_ADVERSARIAL_VALIDATED)
        return output, validation

    async def _execute_requests(
        self, claim: AutoReviewClaim, requests, stage: str
    ) -> list[StageExecution]:
        executions: list[StageExecution] = []
        for request in requests:
            self._renew(claim)
            self._authorize(claim)
            execution = await execute_stage(self._provider, request)
            if not execution.ok:
                raise ReviewPipelineError(
                    f"{stage}_{execution.error_code or 'failed'}", retryable=True
                )
            executions.append(execution)
        return executions

    def _begin(self, claim: AutoReviewClaim, stage: str) -> None:
        try:
            self._db.begin_auto_review_stage(
                claim.review_id,
                stage,
                claim.lease_token,
                claim.lease_epoch,
                now=self._now(),
            )
        except AutoReviewLeaseLost:
            raise
        except AutoReviewConflict as exc:
            raise ReviewPipelineError("illegal_stage_transition", retryable=False) from exc

    def _advance(self, claim: AutoReviewClaim, stage: str) -> None:
        self._begin(claim, stage)

    def _save_stage(
        self,
        claim: AutoReviewClaim,
        membership: AutoReviewMembership,
        stage: str,
        status: str,
        evidence_sha256: str,
        payload: str,
        validation: StageEvidenceValidation,
    ) -> None:
        scan = redact_text(payload, max_input_chars=MAX_STAGE_JSON)
        if scan.status != "ok" or scan.redactions:
            raise ReviewPipelineError("secret_in_stage_output", retryable=False)
        validation_payload = json.dumps(
            {
                "stage_valid": validation.stage_valid,
                "accepted": len(validation.accepted),
                "rejected": [item.reason for item in validation.rejected],
                "reason": validation.invalid_reason,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        try:
            self._db.save_auto_review_stage(
                claim.review_id,
                membership.repository_id,
                membership.pr_number,
                stage,
                status,
                lease_token=claim.lease_token,
                lease_epoch=claim.lease_epoch,
                evidence_sha256=evidence_sha256,
                output_json=payload,
                validation_json=validation_payload,
                now=self._now(),
            )
        except AutoReviewLeaseLost:
            raise
        except AutoReviewConflict as exc:
            raise ReviewPipelineError("stage_persist_conflict", retryable=False) from exc


def _aggregate(outcomes: list[VerdictResult]) -> VerdictResult:
    if not outcomes:
        return VerdictResult(
            VERDICT_BLOCKED,
            "no_pr_outcomes",
            "R5-AGG-01",
            (),
            0,
            "missing",
            "unverified",
        )
    verdicts = {item.verdict for item in outcomes}
    if VERDICT_FAIL in verdicts:
        verdict = VERDICT_FAIL
        reason = "one_or_more_pr_failed"
    elif VERDICT_BLOCKED in verdicts:
        verdict = VERDICT_BLOCKED
        reason = "one_or_more_pr_blocked"
    elif VERDICT_PASS_WITH_NOTES in verdicts:
        verdict = VERDICT_PASS_WITH_NOTES
        reason = "one_or_more_pr_has_notes"
    else:
        verdict = VERDICT_PASS
        reason = "all_prs_passed"
    findings = tuple(
        finding for item in outcomes for finding in item.valid_findings
    )
    return VerdictResult(
        verdict=verdict,
        reason=reason,
        rule="R5-AGG-01",
        valid_findings=findings,
        invalid_findings=sum(item.invalid_findings for item in outcomes),
        ci_state=(
            "success"
            if all(item.ci_state == "success" for item in outcomes)
            else "mixed"
        ),
        sha_status=(
            "verified"
            if all(item.sha_status == "verified" for item in outcomes)
            else "unverified"
        ),
        notes=tuple(note for item in outcomes for note in item.notes),
    )


def _delivery_text(
    cycle,
    memberships: tuple[AutoReviewMembership, ...],
    outcomes: list[VerdictResult],
    aggregate: VerdictResult,
) -> str:
    lines = [
        f"نتيجة المراجعة المستقلة — دورة {cycle.id}",
        f"القرار: {aggregate.verdict}",
        f"السبب: {aggregate.reason}",
        "الـ PRs:",
    ]
    for outcome, membership in zip(outcomes, memberships):
        lines.append(
            f"- {membership.repository_full_name}#{membership.pr_number} "
            f"@ {membership.head_sha[:12]}: {outcome.verdict} ({outcome.reason})"
        )
    text = "\n".join(lines)
    scan = redact_text(text, max_input_chars=MAX_DELIVERY_TEXT)
    if scan.status != "ok":
        raise ReviewPipelineError("delivery_text_too_large", retryable=False)
    return scan.text


class ReviewWorker(_BaseWorker):
    """Existing worker loop; claims durable review work and delegates to ReviewRunner."""

    def __init__(
        self,
        db: Database,
        runner: ReviewRunner,
        *,
        owner: str,
        poll_interval: float = 2.0,
        max_idle: float = 30.0,
        lease_seconds: int = 300,
        clock=None,
        report_service=None,
    ) -> None:
        super().__init__(None, db, None, poll_interval=poll_interval, max_idle=max_idle)
        self._runner = runner
        self._owner = owner
        self._lease_seconds = lease_seconds
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._report_service = report_service

    def _now(self) -> str:
        return self._clock().isoformat()

    def _claim(self):
        if self._report_service is not None:
            # R6 owns recovery: prepare the report and its outbox intent together.
            # Falling back to the R5 text-only intent would silently omit the report.
            self._report_service.ensure_pending(now=self._now())
        else:
            try:
                self._db.ensure_pending_auto_review_deliveries(now=self._now())
            except Exception:
                log.exception("failed to recover pending review deliveries")
                raise
        claim = self._db.claim_auto_review(
            owner=self._owner, now=self._now(), lease_seconds=self._lease_seconds
        )
        # claim may have terminalized an attempts-exhausted cycle.
        if self._report_service is not None:
            self._report_service.ensure_pending(now=self._now())
        else:
            self._db.ensure_pending_auto_review_deliveries(now=self._now())
        return claim

    async def _process(self, claim: AutoReviewClaim) -> None:
        try:
            await self._runner.run(claim)
        except AutoReviewLeaseLost:
            return
        except ReviewPipelineError as exc:
            try:
                result = self._db.fail_auto_review(
                    claim.review_id,
                    lease_token=claim.lease_token,
                    lease_epoch=claim.lease_epoch,
                    error_class=exc.code,
                    retryable=exc.retryable,
                    now=self._now(),
                )
            except AutoReviewLeaseLost:
                return
            if result == "terminal_failed":
                self._prepare_delivery(claim.review_id)
        except Exception as exc:
            cycle = self._db.get_auto_review(claim.review_id)
            if cycle is not None and cycle.lifecycle_state == AUTO_REVIEW_LIFECYCLE_DELIVERY_PENDING:
                log.warning(
                    "review %s is delivery_pending; delivery recovery will retry (%s)",
                    claim.review_id,
                    type(exc).__name__,
                )
                return
            try:
                self._db.fail_auto_review(
                    claim.review_id,
                    lease_token=claim.lease_token,
                    lease_epoch=claim.lease_epoch,
                    error_class=type(exc).__name__,
                    retryable=True,
                    now=self._now(),
                )
            except AutoReviewLeaseLost:
                return

    def _prepare_delivery(self, review_id: int) -> None:
        try:
            if self._report_service is not None:
                self._report_service.prepare(review_id, now=self._now())
            else:
                self._db.schedule_auto_review_delivery(review_id, now=self._now())
        except Exception:
            log.exception("failed to prepare terminal review delivery")
            raise

    def _is_retry_pending(self, claim: AutoReviewClaim) -> bool:
        cycle = self._db.get_auto_review(claim.review_id)
        return cycle is not None and cycle.lifecycle_state in (
            AUTO_REVIEW_LIFECYCLE_RETRY_WAIT,
            AUTO_REVIEW_LIFECYCLE_ACTIVE,
        )
