# OHB2-R7 WP-01 / D-03 Authorization Revalidation — Implementation Report

**Date:** 2026-11-26
**Status:** `WP01_LOCAL_IMPLEMENTATION_AND_VERIFICATION_COMPLETE`
**Scope:** Local implementation and verification of WP-01 only. No live operation,
provider call, GitHub call, Telegram send, worker activation, production deployment,
schema work, or Git publication.

## Owner-approved policy

D-03 is implemented as `current-owner-revalidation`: the current authoritative
`Config.owner_id` is checked at each protected execution and delivery boundary. Cached
authorization is not accepted, and every check reads the persisted cycle/watched/
deletion state again.

## What changed

| File | Reason |
| --- | --- |
| `bot/review/authorization.py` | New read-only helper and safe error type. Checks owner config, cycle state, owner/chat relationship, deletion witness, and watched conversation. |
| `bot/review/worker.py` | Binds the configured owner and revalidates before execution, each evidence collection, Blind, Adversarial, each provider request, and completion. |
| `bot/review/report.py` | Revalidates before generating or scheduling a report. |
| `bot/outbox.py` | Revalidates before report claim, before the send CAS, after the CAS and before `send_document`, and after send before `sent`. Retryable DB-read failures return to `pending`; explicit denial fails closed. |
| `bot/app.py` | Passes `config.owner_id` to the report service and outbox worker. |
| `tests/test_review_authorization_revalidation.py` | 39 focused negative/positive tests covering owner, chat, deletion, watched, DB-read, resume, delivery, recovery, lease, and R6 acceptance cases. |
| Existing review tests/helpers | Added the required watched-conversation setup and owner injection so existing tests exercise the real authorization boundary. |

## Behavior

- Owner change, missing/malformed owner config, deleted conversation, missing watched
  conversation, wrong private chat, group/channel target, and actual delivery target
  mismatch are denied before content is sent.
- Database read failures during deletion or ownership lookup produce a retryable safe
  outcome; they never authorize success or imply deletion.
- Delivery denial preserves the report and evidence, and does not mark the report sent.
- Retryable delivery authorization read failures leave the outbox row recoverable.
- Lease/epoch fencing and R6 owner acceptance behavior remain intact.

## Verification

- Full Python suite: `4335 passed, 0 failed` (`pytest -q`, 328.54s).
- Focused WP-01 tests: `39 passed`.
- Frontend: `280 pass, 0 fail`.
- `pyflakes`: clean.
- `compileall`: clean.
- `bandit -lll -s B613`: 0 High.
- `pip-audit`: no known vulnerabilities.
- `git diff --check`: clean.

## Not implemented / not verified

- No live Telegram delivery, provider call, GitHub call, or production database.
- No WP-02..WP-06, D-04b, worker activation, or deployment.
- Group/channel coverage is represented by non-owner negative chat IDs; no Telegram
  chat-type metadata is persisted in the outbox schema.
