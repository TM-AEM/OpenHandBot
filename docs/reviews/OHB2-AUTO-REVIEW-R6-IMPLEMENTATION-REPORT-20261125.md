# OHB2-AUTO-REVIEW-R6 — Implementation Report (2026-11-25)

## Status

**DONE (local implementation and local verification only).**

R6 implements Telegram delivery of the persisted R5 review result: a concise Arabic summary,
the complete immutable Markdown report as a document, a Details action, and owner-only
Accept/Reject actions. No review worker is started by this change, no real Telegram/GitHub/provider
traffic was used, and no independent review is claimed.

## Acceptance criteria

1. **Deterministic report from persisted data — MET.**
   `bot/review/report.py::build_review_report` reads `auto_reviews`, `auto_review_memberships`,
   `auto_review_stages`, and `auto_review_evidence`; it re-parses persisted blind/adversarial
   output and never calls a reviewer or reads a raw diff. The report includes verdict, scope,
   membership SHAs, per-stage assessments, findings grouped by severity, CI/evidence metadata,
   limitations, and the owner-decision separation. Single-PR filename is `review-<head7>.md`;
   multi-PR filename is `review-<sha256(snapshot)7>.md`. Evidence is recorded in
   `tests/test_review_report.py`.
2. **Summary + full document through the existing outbox — MET.**
   `ReviewReportService.prepare` persists one report per `(review_id, version)` and schedules
   one outbox intent. `bot/outbox.py::_post_claimed_review` sends a document with an escaped
   summary caption and Details/Accept/Reject buttons, with a `claimed⇒sending` CAS before the
   Telegram call. A confirmed send is the only path to `sent`; ambiguous failures are `unknown`.
   Evidence: `tests/test_review_delivery.py`, `tests/test_review_worker_integration.py`.
3. **Narrow callback contract — MET.**
   `bot/app.py` registers only `^review:`; payloads are
   `review:{d|a|r}:{review_id}:{version}`, validated by a full-match regex and measured in UTF-8
   bytes (≤64). Payloads contain no token, SHA, report text, or owner id. Evidence:
   `tests/test_review_callback.py::test_callback_format_parsing_and_utf8_limit` and
   `test_review_callback_is_registered_narrowly`.
4. **Owner/authorization re-checks — MET.**
   `bot/handlers.py::review_action` checks `_allowed`, configured `owner_id`, private chat,
   `effective_chat.id == cycle.chat_id`, and `callback_query.message.chat_id == cycle.chat_id`.
   Forged, cross-conversation, non-owner, missing-report, and malformed callbacks mutate nothing
   and expose no report content. Evidence: callback tests listed above.
5. **Durable owner acceptance — MET.**
   `auto_review_owner_acceptance` stores `event_type=OWNER_ACCEPTANCE`, action, owner user id,
   report version, and a unique idempotency key. Duplicate decisions return the original record;
   a different action returns a conflict and is not written. The technical verdict, stage output,
   findings, and SHAs are not updated. Evidence: callback tests and
   `test_owner_acceptance_does_not_change_report_content`.
6. **Details fails closed — MET.**
   Details loads the exact persisted report row; it never regenerates or uses the latest report
   when a requested version is missing. Missing report/version answers without content and sends
   no document. Evidence: callback/delivery tests.

## Changes

- `bot/db.py`: R6 constants/dataclasses; `auto_review_reports` and
  `auto_review_owner_acceptance` tables with immutability triggers; outbox
  `review_kind/review_version/review_report_id`; report/acceptance/read/recovery APIs.
- `bot/review/report.py`: deterministic report builder, filename rule, Markdown/HTML escaping,
  secret and size checks, callback builder/parser/keyboard, report service, Details sender.
- `bot/review/worker.py`: optional `report_service`; prepares the R6 report on completion and
  terminal failure, and uses R6 recovery instead of the R5 text-only fallback when wired.
- `bot/outbox.py`: existing outbox worker branch for R6 summary+document delivery; legacy R5
  rows without R6 fields retain their old text path.
- `bot/handlers.py`: owner-only `review_action` callback handler.
- `bot/app.py`: constructs `ReviewReportService` in `bot_data` and registers `^review:`.
- `tests/_review_r6_helpers.py`, `tests/test_review_report.py`, `tests/test_review_delivery.py`,
  `tests/test_review_callback.py`, `tests/test_review_worker_integration.py`: deterministic
  fixtures, positive paths, and negative controls.
- `tests/test_def011_a_option_b_limits.py`, `tests/test_def011_fs_offload.py`,
  `tests/test_doc_code_parity.py`: schema count/contract updates for the two R6 tables.
- `README.md`, `docs/OPERATIONS_RUNBOOK.md`, `.agent/PROGRESS.md`: R6 behavior/limits.

## Verification (real local commands)

- `python -m pytest -q` — **4182 passed**, 0 failed (74 warnings; pre-existing PTB/Starlette
  deprecation warnings).
- Focused R6/R5 run — **61 passed** across report, delivery, callback, worker integration, and
  lifecycle tests.
- `python -m pyflakes bot/ automation/ tools/ main.py tests/` — 0 findings.
- `python -m py_compile ...` — 0 errors.
- `node --test tests/frontend/*.test.js` — 280 passed, 0 failed.
- `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` — 0 High.
- `python -m pip_audit -r requirements-dev.txt` — no known vulnerabilities.

## Not verified / not implemented

- No independent review was performed in this session; this is the author's implementation report.
- No real Telegram delivery, GitHub API call, provider call, deployment, or production DB
  migration was executed.
- The R5 review worker is intentionally not started by `bot/app.py`; R6 does not activate it.
- Real Telegram file/caption limits and live callback behavior remain unverified outside fakes.
- No commit, push, PR, merge, or deploy was made.

## Assumptions and decisions

- Summary is the Telegram document caption (one message) rather than a second separate message.
- Report content excludes mutable delivery/lifecycle timestamps so the same immutable review
  result produces the same bytes; report version 1 is the default.
- R5 outbox rows without `review_kind`/`review_report_id` retain the legacy text delivery path;
  R6 rows fail closed if their report is missing.
- Owner identity is the configured `owner_id`; the review's `chat_id` must equal it in this
  private-chat deployment.
- Report filename for multi-PR cycles uses a canonical membership snapshot hash because no single
  PR head represents the cycle.

## Branch and commits

- Branch: `agent/r6-review-delivery`.
- Commits: none made in this session (working tree changes remain uncommitted).
- Baseline: `01079676351aac869d09d4d1747661cd6f07d82b`.

## Suggested next step

R7: independent review of this R6 diff, followed by a separately approved runtime activation plan
for the R5 worker and real Telegram delivery.
