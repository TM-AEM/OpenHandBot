"""R6 deterministic review report and Telegram delivery helpers.

The report is built only from persisted R5 cycle, stage, and evidence rows. It never
re-runs a reviewer, reads a raw diff, or turns an incomplete cycle into a complete
report. Owner decisions are stored elsewhere and never alter the technical verdict.
"""
from __future__ import annotations

import asyncio
import hashlib
import html
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.constants import ParseMode
from telegram.error import TelegramError

from bot.db import (
    AUTO_REVIEW_REPORT_VERSION,
    AutoReviewReport,
    Database,
)
from bot.messages import escape_html
from bot.review.authorization import (
    AUTHORIZATION_DATABASE_UNAVAILABLE,
    ReviewAuthorizationError,
    revalidate_review_authorization,
)
from bot.review.redact import redact_text
from bot.review.schema import (
    AdversarialReviewOutput,
    BlindReviewOutput,
    SchemaError,
    parse_adversarial_review,
    parse_blind_review,
)
from bot.review.verdict import VERDICTS

log = logging.getLogger(__name__)

MAX_REPORT_CHARS = 180_000
MAX_REPORT_BYTES = 300_000
MAX_SUMMARY_CHARS = 1024
FILENAME_RE = re.compile(r"^review-[0-9a-f]{7}\.md$")
CALLBACK_RE = re.compile(r"^review:([dar]):([1-9][0-9]{0,17}):([1-9][0-9]{0,5})$")
CALLBACK_LIMIT = 64

ACTION_DETAILS = "details"
ACTION_ACCEPT = "accept"
ACTION_REJECT = "reject"
ACTION_CODES = {
    ACTION_DETAILS: "d",
    ACTION_ACCEPT: "a",
    ACTION_REJECT: "r",
}
CODE_ACTIONS = {value: key for key, value in ACTION_CODES.items()}

SEVERITY_ORDER = ("critical", "high", "medium", "low")
SEVERITY_RANK = {name: index for index, name in enumerate(SEVERITY_ORDER)}
VALIDATION_OK = "ok"


class ReviewReportError(RuntimeError):
    """Safe report error; never includes repository or model text."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ReviewCallbackError(ValueError):
    """Malformed or oversized review callback payload."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class GeneratedReviewReport:
    review_id: int
    version: int
    filename: str
    content: str
    summary: str
    report_sha256: str
    verdict: str


@dataclass(frozen=True)
class _StageView:
    stage: str
    status: str
    assessment: str = "unavailable"
    summary: str = "unavailable"
    findings: tuple[Any, ...] = ()
    challenges: tuple[Any, ...] = ()
    evidence_gaps: tuple[str, ...] = ()
    reviewed_files: tuple[str, ...] = ()
    validation_rejected: tuple[str, ...] = ()
    updated_at: str | None = None
    problem: str | None = None


def build_review_callback(action: str, review_id: int, version: int) -> str:
    """Build a strict, secret-free callback payload within Telegram's 64-byte limit."""
    if action not in ACTION_CODES:
        raise ReviewCallbackError("unknown_action")
    if isinstance(review_id, bool) or not isinstance(review_id, int) or review_id <= 0:
        raise ReviewCallbackError("invalid_review_id")
    if isinstance(version, bool) or not isinstance(version, int) or version <= 0:
        raise ReviewCallbackError("invalid_version")
    data = f"review:{ACTION_CODES[action]}:{review_id}:{version}"
    if len(data.encode("utf-8")) > CALLBACK_LIMIT:
        raise ReviewCallbackError("callback_too_long")
    return data


def parse_review_callback(data: object) -> tuple[str, int, int]:
    """Parse only `review:{d|a|r}:{review_id}:{version}`; reject everything else."""
    if not isinstance(data, str) or not data:
        raise ReviewCallbackError("invalid_callback")
    if len(data.encode("utf-8")) > CALLBACK_LIMIT:
        raise ReviewCallbackError("callback_too_long")
    match = CALLBACK_RE.fullmatch(data)
    if match is None:
        raise ReviewCallbackError("invalid_callback")
    code, review_raw, version_raw = match.groups()
    action = CODE_ACTIONS.get(code)
    if action is None:
        raise ReviewCallbackError("unknown_action")
    review_id = int(review_raw)
    version = int(version_raw)
    if review_id <= 0 or version <= 0:
        raise ReviewCallbackError("invalid_identifier")
    return action, review_id, version


def review_actions_markup(review_id: int, version: int) -> InlineKeyboardMarkup:
    """Details/Accept/Reject buttons; all payloads are measured in UTF-8 bytes."""
    buttons = [
        InlineKeyboardButton(
            "تفاصيل", callback_data=build_review_callback(ACTION_DETAILS, review_id, version)
        ),
        InlineKeyboardButton(
            "قبول", callback_data=build_review_callback(ACTION_ACCEPT, review_id, version)
        ),
        InlineKeyboardButton(
            "رفض", callback_data=build_review_callback(ACTION_REJECT, review_id, version)
        ),
    ]
    return InlineKeyboardMarkup([buttons])


def _safe_md(value: object) -> str:
    """Escape untrusted text for a plain Markdown document."""
    text = str(value).replace("\r", " ").replace("\n", " ")
    text = html.escape(text, quote=False)
    return re.sub(r"([\\`*_{}\[\]()#+.!|>])", r"\\\1", text)


def _short_sha(value: str) -> str:
    return value[:7]


def report_filename(memberships) -> str:
    """Documented filename rule.

    One PR: the first 7 characters of its exact reviewed head SHA.
    Multiple PRs: first 7 hex characters of SHA-256 over the canonical immutable
    membership snapshot, because no single PR SHA represents the whole cycle.
    """
    ordered = sorted(memberships, key=lambda item: (item.repository_id, item.pr_number))
    if not ordered:
        raise ReviewReportError("no_memberships")
    for item in ordered:
        if not isinstance(item.head_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", item.head_sha):
            raise ReviewReportError("invalid_head_sha")
        if not isinstance(item.base_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", item.base_sha):
            raise ReviewReportError("invalid_base_sha")
    if len(ordered) == 1:
        short = _short_sha(ordered[0].head_sha)
    else:
        payload = [
            [
                item.repository_id,
                item.pr_number,
                item.branch,
                item.base_sha,
                item.head_sha,
            ]
            for item in ordered
        ]
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        short = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:7]
    filename = f"review-{short}.md"
    if not FILENAME_RE.fullmatch(filename):
        raise ReviewReportError("invalid_filename")
    return filename


def _evidence_json(evidence) -> dict[str, Any] | None:
    if evidence is None:
        return None
    try:
        payload = json.loads(evidence.evidence_json)
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _validation_rejected(stage) -> tuple[str, ...]:
    if stage is None or not stage.validation_json:
        return ()
    try:
        payload = json.loads(stage.validation_json)
    except (TypeError, ValueError):
        return ("validation_json_invalid",)
    if not isinstance(payload, dict):
        return ("validation_json_invalid",)
    rejected = payload.get("rejected")
    if not isinstance(rejected, list):
        return ()
    return tuple(_safe_md(item) for item in rejected[:100] if isinstance(item, str))


def _stage_view(db: Database, review_id: int, membership, stage_name: str) -> _StageView:
    stage = db.get_auto_review_stage(
        review_id, membership.repository_id, membership.pr_number, stage_name
    )
    if stage is None:
        return _StageView(stage=stage_name, status="missing", problem="stage_missing")
    rejected = _validation_rejected(stage)
    if stage.status != "validated":
        return _StageView(
            stage=stage_name,
            status=stage.status,
            validation_rejected=rejected,
            updated_at=stage.updated_at,
            problem="stage_not_validated",
        )
    try:
        if stage_name == "blind":
            output: BlindReviewOutput | AdversarialReviewOutput = parse_blind_review(
                stage.output_json or ""
            )
        else:
            output = parse_adversarial_review(stage.output_json or "")
    except SchemaError:
        return _StageView(
            stage=stage_name,
            status=stage.status,
            validation_rejected=rejected,
            updated_at=stage.updated_at,
            problem="persisted_output_invalid",
        )
    return _StageView(
        stage=stage_name,
        status=stage.status,
        assessment=output.assessment,
        summary=output.summary,
        findings=tuple(output.findings),
        challenges=tuple(getattr(output, "challenges", ())),
        evidence_gaps=tuple(output.evidence_gaps),
        reviewed_files=tuple(output.reviewed_files),
        validation_rejected=rejected,
        updated_at=stage.updated_at,
    )


def _finding_sources(views: list[_StageView]) -> list[tuple[Any, tuple[str, ...]]]:
    found: dict[str, tuple[Any, set[str]]] = {}
    for view in views:
        if view.status != "validated":
            continue
        for finding in view.findings:
            current = found.get(finding.id)
            if current is None:
                found[finding.id] = (finding, {view.stage})
                continue
            old_finding, sources = current
            sources.add(view.stage)
            if SEVERITY_RANK.get(finding.severity, 99) < SEVERITY_RANK.get(
                old_finding.severity, 99
            ):
                found[finding.id] = (finding, sources)
    ordered = sorted(
        found.values(),
        key=lambda item: (SEVERITY_RANK.get(item[0].severity, 99), item[0].id),
    )
    return [(finding, tuple(sorted(sources))) for finding, sources in ordered]


def _severity_counts(findings: list[tuple[Any, tuple[str, ...]]]) -> dict[str, int]:
    counts = {name: 0 for name in SEVERITY_ORDER}
    for finding, _sources in findings:
        if finding.severity in counts:
            counts[finding.severity] += 1
    return counts


def _ci_lines(evidence) -> list[str]:
    payload = _evidence_json(evidence)
    if payload is None:
        return ["- بيانات CI: غير متاحة (لا يوجد دليل محفوظ)."]
    lines = [
        f"- حالة CI: {_safe_md(payload.get('ci_state', 'unknown'))}",
        f"- SHA: {_safe_md(payload.get('sha_status', 'unverified'))}",
        f"- التغطية مكتملة: {'نعم' if payload.get('coverage_complete') else 'لا'}",
    ]
    runs = payload.get("ci_runs")
    if isinstance(runs, list) and runs:
        lines.append("- تشغيلات CI:")
        normalized = []
        for run in runs:
            if isinstance(run, (list, tuple)) and len(run) >= 4:
                normalized.append(tuple(str(part) for part in run[:4]))
            elif isinstance(run, dict):
                normalized.append(
                    (
                        str(run.get("run_id", "")),
                        str(run.get("name", "")),
                        str(run.get("status", "")),
                        str(run.get("conclusion", "")),
                    )
                )
        for run_id, name, status, conclusion in sorted(normalized):
            lines.append(
                f"  - {_safe_md(run_id)}: {_safe_md(name)} — "
                f"{_safe_md(status)}/{_safe_md(conclusion)}"
            )
    else:
        lines.append("- تشغيلات CI: غير محفوظة.")
    jobs = payload.get("ci_jobs")
    if isinstance(jobs, list) and jobs:
        lines.append("- وظائف CI:")
        for job in jobs[:100]:
            if isinstance(job, dict):
                lines.append(
                    f"  - {_safe_md(job.get('job_id', ''))}: "
                    f"{_safe_md(job.get('name', ''))} — "
                    f"{_safe_md(job.get('conclusion', 'unknown'))}"
                )
    else:
        lines.append("- وظائف CI: غير محفوظة في الدليل.")
    return lines


def build_review_report(
    db: Database, review_id: int, *, version: int = AUTO_REVIEW_REPORT_VERSION
) -> GeneratedReviewReport:
    """Build a deterministic report from persisted, already-validated data."""
    cycle = db.get_auto_review(review_id)
    if cycle is None:
        raise ReviewReportError("review_not_found")
    if cycle.lifecycle_state not in ("delivery_pending", "terminal"):
        raise ReviewReportError("review_not_terminal")
    if cycle.verdict not in VERDICTS:
        raise ReviewReportError("missing_verdict")
    memberships = db.get_auto_review_memberships(review_id)
    if not memberships or len(memberships) != cycle.membership_count:
        raise ReviewReportError("membership_snapshot_invalid")
    filename = report_filename(memberships)
    views_by_membership = []
    limitations: list[str] = []
    evidence_rows = []
    for membership in memberships:
        evidence = db.get_auto_review_evidence(
            review_id, membership.repository_id, membership.pr_number
        )
        evidence_rows.append(evidence)
        blind = _stage_view(db, review_id, membership, "blind")
        adversarial = _stage_view(db, review_id, membership, "adversarial")
        views_by_membership.append((membership, evidence, blind, adversarial))
        for view in (blind, adversarial):
            if view.problem:
                limitations.append(
                    f"{membership.repository_full_name}#{membership.pr_number}: "
                    f"{view.stage}={view.problem}"
                )
        if evidence is None:
            limitations.append(
                f"{membership.repository_full_name}#{membership.pr_number}: evidence_missing"
            )
        else:
            if not evidence.coverage_complete:
                limitations.append(
                    f"{membership.repository_full_name}#{membership.pr_number}: "
                    "coverage_incomplete"
                )
            payload = _evidence_json(evidence)
            if payload is None:
                limitations.append(
                    f"{membership.repository_full_name}#{membership.pr_number}: "
                    "evidence_json_invalid"
                )
            elif payload.get("ci_jobs_complete") is False:
                limitations.append(
                    f"{membership.repository_full_name}#{membership.pr_number}: "
                    "ci_jobs_incomplete"
                )
    all_findings = _finding_sources(
        [view for _membership, _evidence, blind, adversarial in views_by_membership
         for view in (blind, adversarial)]
    )
    counts = _severity_counts(all_findings)
    complete = (
        cycle.verdict != "BLOCKED"
        and all(
            blind.status == "validated" and adversarial.status == "validated"
            for _membership, _evidence, blind, adversarial in views_by_membership
        )
        and all(evidence is not None and evidence.coverage_complete for evidence in evidence_rows)
        and not limitations
    )
    lines = [
        f"# تقرير المراجعة المستقلة — دورة {_safe_md(cycle.id)}",
        "",
        f"- نسخة التقرير: {_safe_md(version)}",
        f"- اسم الملف: `{filename}`",
        "- قاعدة اسم الملف: PR واحد = أول 7 hex من reviewed head SHA؛ عدة PRs = أول 7 hex "
        "من SHA-256 للقطة العضوية الثابتة.",
        "- بصمة التقرير: SHA-256 فوق المحتوى النهائي، محفوظة في `auto_review_reports`.",
        f"- القرار التقني: **{_safe_md(cycle.verdict)}**",
        f"- النطاق: {_safe_md(cycle.scope_policy or cycle.scope)}",
        f"- المحادثة: `{_safe_md(cycle.conversation_id)}`",
        f"- الحالة: {'مكتملة' if complete else 'غير مكتملة أو متوقفة'}",
        "",
        "## ملخص",
        f"- عدد PRs: {_safe_md(len(memberships))}",
        f"- الملاحظات: critical={counts['critical']}, high={counts['high']}, "
        f"medium={counts['medium']}, low={counts['low']}",
        "- قرار المالك: سجل منفصل (OWNER_ACCEPTANCE) ولا يغيّر هذا القرار التقني.",
        "",
        "## نطاق المراجعة وPRs",
    ]
    for membership in memberships:
        lines.extend(
            [
                f"### {_safe_md(membership.repository_full_name)}#{_safe_md(membership.pr_number)}",
                f"- الفرع: {_safe_md(membership.branch)}",
                f"- base SHA: `{_safe_md(membership.base_sha)}`",
                f"- reviewed head SHA: `{_safe_md(membership.head_sha)}`",
            ]
        )
    lines.extend(["", "## نتائج المراحل"])
    for membership, _evidence, blind, adversarial in views_by_membership:
        lines.extend(
            [
                f"### {_safe_md(membership.repository_full_name)}#{_safe_md(membership.pr_number)}",
                f"- Blind: {_safe_md(blind.status)} / {_safe_md(blind.assessment)}",
                f"- Blind summary: {_safe_md(blind.summary)}",
                f"- Adversarial: {_safe_md(adversarial.status)} / "
                f"{_safe_md(adversarial.assessment)}",
                f"- Adversarial summary: {_safe_md(adversarial.summary)}",
            ]
        )
        for challenge in adversarial.challenges:
            lines.append(
                f"  - تحدي {_safe_md(challenge.finding_id)}: "
                f"{_safe_md(challenge.status)} — {_safe_md(challenge.reason)}"
            )
        gaps = tuple(blind.evidence_gaps) + tuple(adversarial.evidence_gaps)
        if gaps:
            lines.append("  - فجوات الدليل:")
            for gap in gaps[:100]:
                lines.append(f"    - {_safe_md(gap)}")
    lines.extend(["", "## النتائج حسب الخطورة"])
    if not all_findings:
        lines.append("- لا توجد نتائج مُتحقَّق منها.")
    else:
        for severity in SEVERITY_ORDER:
            group = [item for item in all_findings if item[0].severity == severity]
            if not group:
                continue
            lines.append(f"### {severity} ({len(group)})")
            for finding, sources in group:
                lines.extend(
                    [
                        f"- **{_safe_md(finding.id)}** — {_safe_md(finding.claim)}",
                        f"  - الملف: `{_safe_md(finding.file)}` "
                        f"({_safe_md(finding.line_start)}-{_safe_md(finding.line_end)})",
                        f"  - الوصف: {_safe_md(finding.description)}",
                        f"  - الثقة: {_safe_md(finding.confidence)}",
                        f"  - المصدر: {_safe_md(', '.join(sources))}",
                    ]
                )
                if finding.evidence_quote:
                    lines.append(f"  - اقتباس الدليل: `{_safe_md(finding.evidence_quote)}`")
                refs = []
                if finding.ci_run_id is not None:
                    refs.append(f"run={finding.ci_run_id}")
                if finding.ci_job_id is not None:
                    refs.append(f"job={finding.ci_job_id}")
                if finding.ci_status:
                    refs.append(f"ci={finding.ci_status}")
                if finding.commit_sha:
                    refs.append(f"sha={finding.commit_sha}")
                if refs:
                    lines.append(f"  - مراجع: {_safe_md(', '.join(refs))}")
                if finding.recommendation:
                    lines.append(f"  - توصية: {_safe_md(finding.recommendation)}")
    lines.extend(["", "## الأدلة وCI"])
    for membership, evidence, _blind, _adversarial in views_by_membership:
        lines.append(
            f"### {_safe_md(membership.repository_full_name)}#{_safe_md(membership.pr_number)}"
        )
        lines.extend(_ci_lines(evidence))
        if evidence is not None:
            lines.append(f"- evidence SHA-256: `{_safe_md(evidence.evidence_sha256)}`")
            lines.append(f"- diff SHA-256: `{_safe_md(evidence.diff_sha256)}`")
            payload = _evidence_json(evidence)
            if payload is not None:
                files = payload.get("files")
                if isinstance(files, list):
                    lines.append(f"- ملفات التغطية: {_safe_md(len(files))}")
                excluded = payload.get("excluded_paths")
                if isinstance(excluded, list) and excluded:
                    lines.append("- مسارات مستثناة:")
                    for path in excluded[:100]:
                        lines.append(f"  - `{_safe_md(path)}`")
    lines.extend(["", "## القيود والتغطية غير المكتملة"])
    if limitations:
        for item in sorted(set(limitations)):
            lines.append(f"- {_safe_md(item)}")
    else:
        lines.append("- لا توجد قيود مسجلة.")
    lines.extend(
        [
            "- لا يحتوي هذا التقرير على diff خام أو payload مزوّد حساس.",
            "- التقرير لا يثبت اكتمال تغطية لم تُسجَّل في الأدلة المحفوظة.",
            "",
            "## الطوابع الزمنية ودورة الحياة",
            f"- created_at: {_safe_md(cycle.created_at)}",
            f"- reserved_at: {_safe_md(cycle.reserved_at)}",
            f"- error_class: {_safe_md(cycle.error_class or 'none')}",
        ]
    )
    for membership, evidence, blind, adversarial in views_by_membership:
        lines.append(
            f"- {_safe_md(membership.repository_full_name)}#{_safe_md(membership.pr_number)}: "
            f"evidence={_safe_md(evidence.created_at if evidence else 'unavailable')}, "
            f"blind={_safe_md(blind.updated_at or 'unavailable')}, "
            f"adversarial={_safe_md(adversarial.updated_at or 'unavailable')}"
        )
    lines.extend(
        [
            "",
            "## قرار المالك",
            "- قرار المالك (ACCEPT/REJECT) يُسجَّل كحدث OWNER_ACCEPTANCE منفصل.",
            "- لا يغيّر القرار التقني أو النتائج أو الـ SHAs أو مراحل R5.",
        ]
    )
    content = "\n".join(lines) + "\n"
    if len(content) > MAX_REPORT_CHARS or len(content.encode("utf-8")) > MAX_REPORT_BYTES:
        raise ReviewReportError("report_too_large")
    scan = redact_text(content, max_input_chars=MAX_REPORT_CHARS)
    if scan.status != VALIDATION_OK or scan.redactions:
        raise ReviewReportError("secret_in_report")
    summary = (
        f"مراجعة مستقلة — دورة {cycle.id}\n"
        f"القرار التقني: {cycle.verdict}\n"
        f"PRs: {len(memberships)} | "
        f"critical={counts['critical']}, high={counts['high']}, "
        f"medium={counts['medium']}, low={counts['low']}\n"
        f"الحالة: {'مكتملة' if complete else 'غير مكتملة أو متوقفة'}\n"
        f"الملف: {filename}"
    )
    if len(summary) > MAX_SUMMARY_CHARS:
        raise ReviewReportError("summary_too_large")
    summary_scan = redact_text(summary, max_input_chars=MAX_SUMMARY_CHARS)
    if summary_scan.status != VALIDATION_OK or summary_scan.redactions:
        raise ReviewReportError("secret_in_summary")
    return GeneratedReviewReport(
        review_id=review_id,
        version=version,
        filename=filename,
        content=content,
        summary=summary,
        report_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        verdict=cycle.verdict,
    )


class ReviewReportService:
    """Persist reports and attach them to the existing R5 outbox delivery intent."""

    def __init__(self, db: Database, *, clock=None, owner_id: int | None = None) -> None:
        self._db = db
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._owner_id = owner_id

    def _now(self) -> str:
        return self._clock().isoformat()

    def build(self, review_id: int, *, version: int = AUTO_REVIEW_REPORT_VERSION):
        return build_review_report(self._db, review_id, version=version)

    def prepare(
        self,
        review_id: int,
        *,
        version: int = AUTO_REVIEW_REPORT_VERSION,
        now: str | None = None,
    ) -> AutoReviewReport:
        try:
            cycle = self._db.get_auto_review(review_id)
        except Exception as exc:  # noqa: BLE001 - never authorize from a failed read
            raise ReviewReportError(AUTHORIZATION_DATABASE_UNAVAILABLE) from exc
        try:
            revalidate_review_authorization(
                self._db,
                owner_id=self._owner_id,
                cycle=cycle,
                target_chat_id=getattr(cycle, "chat_id", None),
                phase="delivery",
            )
        except ReviewAuthorizationError as exc:
            raise ReviewReportError(exc.code) from exc
        report = self._db.get_auto_review_report(review_id, version)
        if report is None:
            generated = self.build(review_id, version=version)
            report = self._db.save_auto_review_report(
                review_id,
                version=version,
                filename=generated.filename,
                content=generated.content,
                summary=generated.summary,
                report_sha256=generated.report_sha256,
                verdict=generated.verdict,
                now=now or self._now(),
            )
        self._db.schedule_auto_review_report_delivery(
            review_id,
            report_id=report.id,
            version=report.version,
            filename=report.filename,
            summary=report.summary,
            now=now or self._now(),
        )
        return report

    def ensure_pending(self, *, now: str | None = None) -> int:
        count = 0
        for cycle in self._db.list_auto_reviews_by_lifecycle("delivery_pending"):
            try:
                self.prepare(cycle.id, now=now or self._now())
                count += 1
            except Exception as exc:  # noqa: BLE001 - one bad cycle must not stop others
                log.warning(
                    "تعذّر تجهيز تقرير المراجعة %s (%s)", cycle.id, type(exc).__name__
                )
        return count

    def get(self, review_id: int, version: int) -> AutoReviewReport | None:
        return self._db.get_auto_review_report(review_id, version)

    async def send_details(self, bot, chat_id: int, report: AutoReviewReport) -> bool:
        """Send the exact persisted report version; never regenerate it here."""
        try:
            await bot.send_document(
                chat_id=chat_id,
                document=InputFile(report.content.encode("utf-8"), filename=report.filename),
                caption=escape_html(report.summary),
                parse_mode=ParseMode.HTML,
                reply_markup=review_actions_markup(report.review_id, report.version),
            )
            return True
        except (TelegramError, asyncio.TimeoutError) as exc:
            log.warning("تعذّر إرسال تقرير المراجعة (%s)", type(exc).__name__)
            return False
