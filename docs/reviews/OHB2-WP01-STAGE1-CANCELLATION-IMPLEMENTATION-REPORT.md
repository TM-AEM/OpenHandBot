# OHB2-WP01 Stage 1 — Safe Active Attachment-Batch Cancellation

**Status:** `DONE` (implementation + tests + docs, uncommitted)
**Date:** 2026-11-21
**Branch:** `main` (no commit/push/PR/merge/deploy/Autopush)

## Scope delivered

Stage 1, exactly as approved: cancel **one owned `pending` attachment batch** by explicit
`batch_id`, persist a durable `cancelled` state, preserve every file/row/identity record, and
protect storage/reaper paths from cancellation races. Stage 2, Mini App/outbox, CI/concurrency
policy, DEF-011-A/C, and D6 were **not** touched.

## Changes

| File | Change |
|---|---|
| `bot/db.py` | Added `ATTACHMENT_BATCH_CANCELLED` to the known status set; `AttachmentRoutingState.CANCELLED`; atomic `pending → cancelled` with owner + duplicate-update handling (`cancel_pending_attachment_batch`); CAS helper (`try_transition_attachment_batch_status`); append-item insert conditioned on owner/conversation/`pending`; `mark_attachment_item_reaped` refuses items whose parent is `cancelled`; owner-scoped cancelled query; routing classifies cancelled batches as non-blocking. |
| `bot/attachments.py` | `StagingStore.cancellation_guard` serializes cancellation with both `store_async` (`_accept_lock`) and synchronous `store()` (`_sync_lock`); the sync lock is acquired through `asyncio`'s executor so the event loop is never blocked; `_store_prepare` rejects cancelled parents; expiry uses CAS; accept refuses a file when cancellation/another transition wins; reaper excludes `cancelled` and double-guards `_plan_batch`. |
| `bot/handlers.py` | `/attachments_cancel <batch_id> confirm` handler (owner-scoped, explicit confirm, truthful replies); cancelled routing is non-blocking for normal text; truthful `rejected_batch` storage-race reply; help/list hint. |
| `bot/app.py` | Registered `attachments_cancel` and kept `BOT_COMMANDS` ↔ handler parity. |
| `tests/test_wp01_stage1_cancellation.py` | 39 deterministic tests: ownership, eligible/ineligible states, idempotency, duplicate updates, DB rollback, reopen durability, concurrent cancels, append-item race, `store_async`/sync `store` rejection and races, reaper exclusion/CAS/item guard, command behavior, routing. |
| `tests/test_attachment_batch_schema.py` | Documented `cancelled` in the status-set assertion. |
| `docs/OPERATIONS_RUNBOOK.md` | Documented the new command. |
| `docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md` | Updated the current-state `to_thread` count from five to six (the guarded sync-lock acquisition adds one legitimate `to_thread` occurrence); historical §2.2/§7 text untouched. |
| `docs/reviews/OHB2-WP07-FINAL-STABILIZATION-BATCH-REPORT.md` | Same truthful `to_thread` count update in its current-state correction notice. |
| `tests/test_doc_code_parity.py` | Updated the parity guard to the new truthful count (6); protected §2.2/§7 assertions remain unchanged. |
| `.agent/PROGRESS.md` | Added current task goal, acceptance criteria, implementation, and verification notes. |

## Safety properties

- Cancellation is `BEGIN IMMEDIATE` + conditional `UPDATE ... WHERE status='pending' AND telegram_id=?`.
- Wrong owner / unknown ID ⇒ `not_found`; non-`pending` ⇒ `not_eligible`; repeated cancellation ⇒
  `already_cancelled`; duplicate Telegram update ⇒ `duplicate` with no state change.
- No route/user-state clearing, no file/row/identity deletion, no movement.
- `cancelled` is excluded from `AttachmentReaper._TERMINAL`; it is not clearable and not a live batch.
- Storage paths fail closed for cancelled batches; if storage already started, cancellation waits for
  the guarded write/finalize (storage wins) and then marks the batch cancelled, preserving the file.
- Reaper expiry is CAS; a stale reaper cannot overwrite `cancelled`/`intent_recorded`/terminal.
- `mark_attachment_item_reaped` atomically refuses items under a `cancelled` parent.

## Verification (real command output)

| Command | Result |
|---|---|
| `/tmp/ohb2-venv/bin/python -m pytest -q` | **3584 passed**, 74 warnings, exit 0 |
| `/tmp/ohb2-venv/bin/python -m pytest -q tests/test_wp01_stage1_cancellation.py` | **39 passed**, exit 0 |
| Related attachment/reaper/app/handlers/Mini App + parity subset | **518 passed**, exit 0 |
| `node --test tests/frontend/*.test.js` | **280 pass / 0 fail**, exit 0 |
| `python -m pyflakes bot/ automation/ tools/ main.py tests/` | exit 0 |
| `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | **High 0**, exit 0 (Medium 19, Low 5 reported in the current dirty tree; no per-finding baseline comparison) |
| `python -m pip_audit -r requirements-dev.txt` | **No known vulnerabilities found**, exit 0 |
| `git diff --check` | exit 0 |

The first full-suite run exposed two expected parity guards after the new status/worker-thread
occurrence: `test_attachment_batch_schema.py` (documented status set) and
`test_doc_code_parity.py` (truthful `to_thread` count). Both were updated to the new documented
truth; the final full suite is green.

## Not implemented / out of scope

- Stage 2 (deletion/cleanup policy after cancellation), Mini App/outbox changes, CI/concurrency
  policy changes, DEF-011-A, DEF-011-C, D6, reservation ledger.
- No commit, push, PR, merge, deployment, or Autopush activation.
- Pre-existing uncommitted workspace changes (including other docs/tests/config) were preserved;
  this task only edited the files listed above.

## Assumptions / decisions

- A cancelled batch remains a durable, non-terminal, non-reapable local record; it is not deleted.
- `cancelled` routing is non-blocking for normal text because Stage 1 only cancels `pending`
  batches with no message-identity association.
- Cancellation waits for an already-authorized storage write to finish (storage wins), rather than
  aborting it; this preserves bytes and avoids deleting pre-existing data.
- The `to_thread` count in the F-03 correction notices was updated because the new guarded sync-lock
  acquisition adds one legitimate `to_thread` occurrence; historical §2.2/§7 text is unchanged.

## File hashes (SHA-256)

```text
b20801a3e7d4abb07295d4867cb74b904d5bd5c95c3732f25f4b61017efc1ff3  bot/db.py
a756102fe2dd7e194f140d4caaaf11310e8a4d77fcc13289b45a2215f22aa0de  bot/attachments.py
84a12aa63b32f54b6390196444ddd2d3226ac8207ba99dd862f7ffeeb0d2bb33  bot/handlers.py
36ff922fd6116ef5414db2ef99aa09a0827cb6bcfa737ba8b03ab8b4d25509da  bot/app.py
ce5dfcb77e2d9f76a5bd5e615b7c52b7e994c27b90fa22011607ef4f70ba2492  tests/test_wp01_stage1_cancellation.py
709c4d44c6de6ee5930d234593a78fea24cb62b4a0a62ebc236602d4a97a4f7b  docs/OPERATIONS_RUNBOOK.md
3d4a2c1fe572988fe5df4665cc44d97a7db5777701c1975c6f11639aa2b1f0eb  tests/test_attachment_batch_schema.py
20465bffaa58496a1c39412c745b51dadc2205f96b615643d08909aa770499d6  tests/test_doc_code_parity.py
```
