# OHB2-AUTO-REVIEW-R6 — Author Self-Review (2026-11-25)

## Scope of this review

This is an **author self-review**, not an independent review. It covers the R6 diff in the local
working tree only. No reviewer was simulated, no PASS was fabricated, and no live service was used.

## What was checked

1. **Data provenance.** The report builder accepts only a persisted review cycle with a technical
   verdict, the exact persisted membership snapshot, persisted stage rows, and persisted evidence
   rows. It does not call a model, collector, GitHub, or Telegram to create content.
2. **No false PASS.** `BLOCKED` remains `BLOCKED`; missing/invalid stages, missing evidence, and
   incomplete coverage are surfaced as limitations and prevent the report from claiming
   completion. No code path upgrades a technical verdict.
3. **Owner decisions are separate.** ACCEPT/REJECT writes only to
   `auto_review_owner_acceptance`; it does not update `auto_reviews`, stage output, findings, or
   SHAs. The report explicitly labels owner acceptance as a separate event.
4. **Authorization.** The callback handler rechecks the configured allowed user, configured owner,
   private-chat status, cycle chat, and callback message chat. Callback data carries no owner id.
5. **Delivery safety.** The existing outbox remains the only sender. A report document is sent
   only after a report row is loaded and the row is CASed from `claimed` to `sending`; only a
   confirmed `send_document` result writes `sent`. Telegram ambiguity writes `unknown`, not `sent`.
6. **Idempotency.** Report rows are unique by `(review_id, version)` and immutable by trigger.
   Owner decisions are unique by `(review_id, report_version, owner_user_id)` and immutable.
   Outbox intents are unique by `(review_id, report_version)` through `review_delivery_key`.
7. **Input safety.** Callback data is strict, ASCII-only by construction, and bounded to 64 UTF-8
   bytes. Report text escapes Markdown metacharacters and HTML; filenames are validated by a strict
   regex and are not accepted from callbacks. Report content is secret-scanned and size-bounded.
8. **Compatibility.** Legacy R5 outbox rows without R6 fields still use the old text path. R6 rows
   with a missing/unknown report or version fail closed rather than sending a latest report.

## Findings and fixes during self-review

- Removed mutable lifecycle/updated-at fields from report content so repeated builds of the same
  immutable result are byte-identical.
- Added report SHA verification in `save_auto_review_report`.
- Added report-id/version/filename consistency checks before scheduling delivery.
- Added a fail-closed check for a missing outbox report version.
- Changed R6 recovery to avoid silently creating the R5 text-only outbox intent when the R6
  service is wired.
- Added negative controls for active-cycle reports, report immutability, hash mismatch, missing
  report/version, owner mismatch, non-owner, forged ids, and cross-conversation callbacks.

## Residual risks / not verified

- Live Telegram caption/document limits and callback behavior are not verified.
- No real report has been delivered, no real review cycle has been run, and no provider/GitHub
  traffic occurred.
- The SQLite migration was exercised on fresh test databases; a production copy was not migrated.
- Independent review is still required before claiming production readiness.
- The R5 worker remains intentionally unwired in `bot/app.py`; this is not a runtime activation.

## Verdict

`R6_LOCAL_IMPLEMENTATION_REVIEWED_BY_AUTHOR` — ready for independent review, not for production
activation.
