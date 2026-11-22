# OHB2-WP01 Stage 1 — Post-Implementation Verification Report

- **Task ID:** `OHB2-WP01-STAGE1-CANCELLATION-POST-IMPLEMENTATION-VERIFICATION`
- **Date:** 2026-11-21
- **Repository:** `/workspace/project/OpenHandBot`
- **Mode:** read-only verification plus creation of this report
- **Overall verdict:** **PASS_WITH_NOTES**
- **Completion classification:** **COMPLETE_WITH_NOTES**
- **Independent review:** **NOT CLAIMED**
- **Owner approval:** **NOT RECORDED**
- **WP-01:** **NOT CLOSED**

---

## 1. Overall verdict and scope

**PASS_WITH_NOTES.**

The Stage 1 cancellation implementation matches all twelve requested safety requirements in the
actual working tree, and the focused, related, and full test suites pass. The implementation does not
delete attachment files, rows, or identity records, does not add a worker/queue/database/process, does
not modify the Mini App, and does not activate Stage 2 cleanup or Autopush.

The notes are material and are not silently dismissed:

1. The approved design's broader correction "`_store_prepare` must reject **any** non-`pending`
   batch before any write" is only partially implemented: the code rejects `cancelled` explicitly,
   while `expired`/`intent_recorded`/other non-pending states still write a new file and then fail at
   finalization, leaving a `pending` item row. This is pre-existing behavior, not a cancellation
   bypass, but it is a design-to-code deviation.
2. The approved design's stronger suggestion that `mark_attachment_item_reaped` require a terminal
   parent is not implemented; it only refuses a `cancelled` parent. A temporary, non-production
   check confirmed that an item under a `pending` parent can still be marked `reaped` if the method
   is called directly. No production caller does this, but it is a future misuse hazard.
3. Several important interleavings are proven by code/CAS reasoning but are not directly exercised:
   cancellation vs. reaper expiry interleaving, cancellation vs. direct `store()` while the sync
   lock is contended, `/attachments_cancel` route preservation, `cancelled` rejection by
   `/attachments_clear`, and SQLite `BUSY`/`LOCKED` behavior.
4. The implementation report says the synchronous lock is acquired through "asyncio's executor";
   the code actually uses `anyio.to_thread.run_sync`. This is a documentation inaccuracy, not a code
   defect.
5. Exact Stage 1 hunk attribution is not provable from Git alone because the working tree also
   contains unrelated uncommitted changes in the same files. The Stage 1 file hashes match the
   implementation report exactly; see §3.

This report is a verification, not an independent review and not an approval. It does not establish
independent approval or close WP-01.

---

## 2. Exact baseline and final Git state

### 2.1 Baseline (before this report)

| Item | Value |
|---|---|
| Working directory | `/workspace/project/OpenHandBot` |
| Branch | `main` |
| HEAD | `0774c9cff923a2ed02da36a1111a283a61600ea5` |
| HEAD tree | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| Index tree | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| Staged entries | None |
| Tracked modifications | 20 |
| Untracked files | 25 (including prior Stage 2 docs and prior reports) |
| Ignored entries relevant | `.openhands/`, `.pytest_cache/`, `__pycache__/` trees |
| Runtime data | No `attachment_staging` directory or `*.sqlite3` files were present |

Baseline `git status --porcelain`:

```text
 M .agent/PROGRESS.md
 M .env.example
 M README.md
 M bot/app.py
 M bot/attachments.py
 M bot/config.py
 M bot/db.py
 M bot/handlers.py
 M docs/OPERATIONS_RUNBOOK.md
 M docs/ZERO_TOUCH_STARTUP.md
 M docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md
 M docs/audits/OHB2-WP07-FINAL-STABILIZATION-AUDIT.md
 M docs/audits/OHB2-WP07-NEW-DEF03-S3-DELIVERY-AND-ACCEPTANCE-RECONCILIATION.md
 M docs/reviews/OHB2-WP07-FINAL-STABILIZATION-BATCH-REPORT.md
 M tests/test_attachment_batch_lifecycle_a2.py
 M tests/test_attachment_batch_schema.py
 M tests/test_doc_code_parity.py
 M tests/test_repair_plan_02_life03_intake_kill_switch.py
 M tests/test_start_script.py
 M tests/test_u04_concurrency.py
?? docs/audits/OHB2-POLLER-CONCURRENCY-OPTION-A-IMPLEMENTATION-REPORT.md
?? docs/audits/OHB2-POLLER-CONCURRENCY-OPTION-A-INDEPENDENT-REVIEW-HANDOFF.md
?? docs/audits/OHB2-POLLER-CONCURRENCY-STRUCTURAL-SAFETY-AUDIT-REPORT.md
?? docs/audits/OHB2-WP01-ATTACHMENT-LIFECYCLE-IMPLEMENTATION-REPORT.md
?? docs/audits/OHB2-WP08-OWNER-ACCEPTANCE-RECORD.md
?? docs/decisions/OHB2-WP01-OD01-OD03-OWNER-DECISION-RECORD.md
?? docs/reviews/OHB2-MASTER-BACKLOG-RECONCILIATION-AND-NEXT-TASK-REPORT.md
?? docs/reviews/OHB2-OD01-OD03-OWNER-DECISION-ANALYSIS-REPORT.md
?? docs/reviews/OHB2-OD01-OD03-OWNER-DECISION-PACKAGE.md
?? docs/reviews/OHB2-WP01-ACTIVE-BATCH-CANCELLATION-SAFETY-DESIGN-REPORT.md
?? docs/reviews/OHB2-WP01-ACTIVE-BATCH-CANCELLATION-SAFETY-DESIGN.md
?? docs/reviews/OHB2-WP01-STAGE1-CANCELLATION-IMPLEMENTATION-REPORT.md
?? docs/reviews/OHB2-WP01-STAGE1-CANCELLATION-OWNER-DECISION-PACKAGE.md
?? docs/reviews/OHB2-WP01-STAGE1-CANCELLATION-OWNER-DECISION-REPORT.md
?? docs/reviews/OHB2-WP01-STAGE2-CLEANUP-POLICY-AND-OWNER-DECISION-PACKAGE.md
?? docs/reviews/OHB2-WP01-STAGE2-CLEANUP-POLICY-AND-OWNER-DECISION-REPORT.md
?? docs/reviews/OHB2-WP07-NAV-OWNER-DECISION-PACKAGE.md
?? docs/reviews/OHB2-WP08-OWNER-ACCEPTANCE-RECORD-REPORT.md
?? docs/reviews/OHB2-WP08-REMAINING-SCOPE-RECONCILIATION-REPORT.md
?? docs/reviews/OHB2-WP08-SCOPE-RECOVERY-AND-STATUS-AUDIT-REPORT.md
?? docs/reviews/OHB2-WP08-UNBLOCKED-PARITY-HARDENING-IMPLEMENTATION-REPORT.md
?? docs/reviews/OHB2-WP09-COMPATIBILITY-AND-ENVIRONMENT-VERIFICATION-REPORT.md
?? docs/reviews/REV-IND-01-WP-07-INDEPENDENT-REVIEW-REPORT.md
?? tests/test_wp01_attachment_lifecycle.py
?? tests/test_wp01_stage1_cancellation.py
```

### 2.2 Final state

After creating only this report, the expected final state is the same 20 tracked modifications plus
**26** untracked files (the 25 pre-existing plus this report). The final status is rechecked after
report creation; see the final response for the exact command output. The working-tree diff hash is
unchanged from baseline.

| Item | Final value |
|---|---|
| Branch | `main` |
| HEAD | `0774c9cff923a2ed02da36a1111a283a61600ea5` |
| HEAD tree | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| Index tree | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| Tracked modifications | 20 |
| Untracked files | 26 |
| Staged entries | None |
| Working-tree diff SHA-256 | `a57bfbe453adcf2d9a08e78f81c9c7fd2efb6fc16f526e27ebfdc8754cf33f3d` |

No fetch, pull, switch, reset, clean, restore, stage, commit, push, PR, merge, deployment, or
Autopush action was performed.

---

## 3. Stage 1 implementation attribution and file hashes

The implementation report lists the Stage 1 files. Their actual SHA-256 values **match the report
exactly**:

| File | SHA-256 | Matches report |
|---|---|---|
| `bot/db.py` | `b20801a3e7d4abb07295d4867cb74b904d5bd5c95c3732f25f4b61017efc1ff3` | Yes |
| `bot/attachments.py` | `a756102fe2dd7e194f140d4caaaf11310e8a4d77fcc13289b45a2215f22aa0de` | Yes |
| `bot/handlers.py` | `84a12aa63b32f54b6390196444ddd2d3226ac8207ba99dd862f7ffeeb0d2bb33` | Yes |
| `bot/app.py` | `36ff922fd6116ef5414db2ef99aa09a0827cb6bcfa737ba8b03ab8b4d25509da` | Yes |
| `tests/test_wp01_stage1_cancellation.py` | `ce5dfcb77e2d9f76a5bd5e615b7c52b7e994c27b90fa22011607ef4f70ba2492` | Yes |
| `docs/OPERATIONS_RUNBOOK.md` | `709c4d44c6de6ee5930d234593a78fea24cb62b4a0a62ebc236602d4a97a4f7b` | Yes |
| `tests/test_attachment_batch_schema.py` | `3d4a2c1fe572988fe5df4665cc44d97a7db5777701c1975c6f11639aa2b1f0eb` | Yes |
| `tests/test_doc_code_parity.py` | `20465bffaa58496a1c39412c745b51dadc2205f96b615643d08909aa770499d6` | Yes |

**Attribution limitation:** `bot/app.py`, `bot/db.py`, `bot/attachments.py`, and `bot/handlers.py`
also contain unrelated uncommitted work (for example, poller/`concurrent_updates` changes in
`bot/app.py`). A commit-level or hunk-level Stage 1-only diff is therefore **not calculable from Git
alone**. The full working-tree diff hash is `a57bfbe...`; it includes unrelated changes. The Stage 1
attribution above relies on the implementation report's file list, matching file hashes, and named
functions/hunks, not on a clean commit.

---

## 4. Design-to-code traceability matrix

Legend: **PASS** = requested requirement is implemented and evidenced; **PASS\*** = implemented with
a documented note; **FAIL** = requested requirement not met; **NOT VERIFIED** = evidence unavailable.

| # | Requirement | Exact code / evidence | Observed behavior | Verdict |
|---:|---|---|---|---|
| 1 | Only `pending` batches are cancellable | `bot/db.py::cancel_pending_attachment_batch` (1358-1431): selects exact owner/batch, returns `already_cancelled` for cancelled, `not_eligible` for any status other than `pending`; tests `test_ineligible_states` / `test_command_rejects_ineligible_states` | Non-`pending` statuses are rejected without state change; `cancelled` is idempotent | **PASS** |
| 2 | Cancellation uses a conditional transition (CAS) | `bot/db.py::cancel_pending_attachment_batch` uses `BEGIN IMMEDIATE` and `UPDATE ... WHERE batch_id=? AND telegram_id=? AND status='pending'` (1400-1405); `try_transition_attachment_batch_status` (1337-1356) | Only one winner can commit; duplicate/new cancellation is safe; concurrent cancellation test yields `cancelled` + `already_cancelled` | **PASS** |
| 3 | Cancellation deletes no files, rows, or identity | `cancel_pending_attachment_batch` contains no file/row deletion; `AttachmentService.cancel_pending_batch` (1201-1218) only calls DB; tests assert file exists, item remains `stored`, counts unchanged (`tests/test_wp01_stage1_cancellation.py:133-160`) | Files, batch/item rows, and identity are preserved | **PASS** |
| 4 | `/cancel` remains separate and does not cancel an attachment batch | `bot/handlers.py::cancel_route` body unchanged (3136+); it calls `clear_awaiting_and_record_outcome` only; test `test_cancel_route_still_does_not_cancel_batch` (683-691) | `/cancel` leaves the batch `pending`; only `/attachments_cancel` changes it | **PASS** |
| 5 | Explicit command requires exact batch identifier | `bot/handlers.py::attachments_cancel` (3090-3133) requires exactly two args, second `confirm`, non-empty batch ID; `bot/app.py` registration; tests `test_command_requires_exact_arguments`, `test_command_is_owner_scoped...` | Missing/extra args rejected; wrong owner gets no batch disclosure | **PASS** |
| 6 | `cancellation_guard` protects all relevant storage paths, including synchronous `store()` | `bot/attachments.py::cancellation_guard` (539-554) acquires `_sync_lock` via `anyio.to_thread.run_sync`, then `_accept_lock`; `store()` acquires `_sync_lock` (894); `store_async` holds `_accept_lock` (955); tests `test_store_async_wins...`, `test_sync_store_wins...` | Cancellation waits for both paths; storage wins or cancellation wins atomically at the status CAS | **PASS\*** — direct `store()` on the event-loop thread is not a supported production path; no timeout if a sync store hangs |
| 7 | `_store_prepare` rejects a cancelled parent batch | `bot/attachments.py::_store_prepare` (686-714) returns `REJECTED_BATCH` for `ATTACHMENT_BATCH_CANCELLED`; tests `test_store_prepare_rejects_cancelled_batch`, `test_store_async_cannot_persist...`, `test_sync_store_cannot_persist...` | Cancelled batch gets no new item/byte write | **PASS** — see design gap N1 for the broader non-pending requirement |
| 8 | Cancellation and expiration races are handled safely | `AttachmentReaper._mark_expired` uses `try_transition_attachment_batch_status` CAS (1543-1581); cancellation CAS (1400-1405); `_plan_batch` skips cancelled; test `test_mark_expired_cas_does_not_overwrite_non_pending` | One status transition wins; stale expiry cannot overwrite cancelled; cancelled bytes are not planned | **PASS\*** — no direct concurrent cancel-vs-sweep interleaving test (T1) |
| 9 | `mark_attachment_item_reaped` checks the parent batch state | `bot/db.py::mark_attachment_item_reaped` (1705-1732) uses `NOT EXISTS (... b.status='cancelled')`; test `test_item_reaping_rejects_cancelled_parent` | Cancelled parent refuses `reaped`; orphan items remain eligible | **PASS\*** — does not require a terminal parent (design gap N2) |
| 10 | Cancelled batches are excluded from automatic reaping | `AttachmentReaper._NON_REAPABLE` (1322-1323); `_sweep_db_phase` explicit cancelled count/skip (1433-1441); `_plan_batch` early `cancelled_non_reapable` (1583-1593); tests `test_cancelled_batch_is_excluded...`, `test_plan_batch_explicitly_skips_cancelled` | Repeated sweeps leave cancelled rows/files intact | **PASS** |
| 11 | No weakening of path-containment, symlink, ownership, or regular-file protections | No changes to `_remove_file` (1803-1849), `resolve_staged_path`/`open_staged_file` (`bot/web/download.py`), `ensure_staging_root`, `_is_within`, or `is_safe_workspace_path`; full tests pass; no new path deletion | Existing protections remain; cancellation adds no path operation | **PASS** |
| 12 | User-facing responses distinguish success from ineligible/failed attempts | `attachments_cancel` message map (3124-3131); success/`already_cancelled`/`not_found`/`not_eligible`/`duplicate`; tests success, wrong owner, ineligible, duplicate, DB failure no reply (585-680); storage race uses `ATTACHMENT_BATCH_CANCELLED_TEXT` (2658-2659) | No success reply on DB failure; ineligible and wrong-owner replies are truthful; cancelled storage race does not claim acceptance | **PASS\*** — no direct handler test for the `rejected_batch` storage-race reply (T2) |

### 4.1 Additional approved-design checks

| Design point | Result | Evidence |
|---|---|---|
| No route/user-state clear in cancellation | **PASS** | `cancel_pending_attachment_batch` never touches `user_state`; handler does not call `clear_awaiting...`; no test explicitly asserts route preservation (T3) |
| No `cancelled` in `ATTACHMENT_BATCH_CLEARABLE_STATUSES` | **PASS** | `bot/db.py:162-166` contains only `expired`/`rejected`; no test directly calls `/attachments_clear` with cancelled (T4) |
| `cancelled` routing is non-blocking | **PASS** | `AttachmentRoutingState.CANCELLED`; `_handle_accompanying_text` returns `False` (2839-2842); test `test_cancelled_routing_is_non_blocking_for_text` |
| Mini App stays frozen | **PASS** | No `bot/web` or `docs/MINI_APP.md` diff; `git diff --stat -- bot/web docs/MINI_APP.md` empty |
| No schema migration | **PASS** | `cancelled` is an application status value; no new table/column; schema test updated only |
| Stage 2 cleanup not implemented | **PASS** | No cleanup command, retention timer, cancelled reaper path, or attachment `DELETE` SQL |
| No new worker/queue/database/process | **PASS** | No `Thread`/`Queue`/`Process`/`subprocess`/new DB in Stage 1 diff; only `to_thread` in the guard; existing process model |
| No Autopush activation | **PASS** | No `automation/autopush` changes; no deployment action |

---

## 5. Concurrency and failure-path findings

### 5.1 Asynchronous acceptance vs. cancellation

- `store_async` holds `_accept_lock` across `_store_prepare`, worker write, and `_store_finalize`
  (`bot/attachments.py:955`).
- `cancellation_guard` waits for `_accept_lock` before `cancel_pending_attachment_batch`
  (`bot/attachments.py:548-554`).
- Therefore cancellation cannot change `pending -> cancelled` inside the prepare/write/finalize
  window of the same store.
- Tests `test_store_async_wins_and_cancellation_preserves_stored_file` and
  `test_store_async_cannot_persist_into_cancelled_batch` exercise both outcomes.

**Verdict: PASS** for the production async path, subject to the single-store assumption.

### 5.2 Synchronous `store()` vs. cancellation

- `store()` acquires `_sync_lock` for the whole prepare/write/finalize window
  (`bot/attachments.py:894`).
- `cancellation_guard` acquires `_sync_lock` through `anyio.to_thread.run_sync` before entering the
  DB cancellation (`bot/attachments.py:548-554`).
- Tests `test_sync_store_wins_and_cancellation_preserves_stored_file` and
  `test_sync_store_cannot_persist_into_cancelled_batch` cover store-wins and cancel-first.

**Verdict: PASS.** Limitation: a synchronous `store()` invoked directly on the event-loop thread
would block the loop by design; production uses `store_async`. If a sync store hangs while holding
`_sync_lock`, cancellation waits without a timeout. This is a liveness limitation, not a state
corruption path.

### 5.3 Cancellation vs. `_store_prepare`

- `_store_prepare` reads the batch and rejects `cancelled` before item insertion/write
  (`bot/attachments.py:704-714`).
- Under the same store lock, cancellation cannot interleave between this read and the write.
- If cancellation wins before the lock is acquired, `_store_prepare` sees `cancelled` and returns
  `REJECTED_BATCH`.

**Verdict: PASS** for cancelled. **N1:** the code does not reject other non-pending states before
write; `test_store_into_already_expired_batch_is_rejected` passes while leaving a `pending` item row
and no file, showing the broader design correction is not implemented.

### 5.4 Cancellation vs. expiration/reaper

- Cancellation uses `BEGIN IMMEDIATE` + CAS on `status='pending'`.
- `_mark_expired` uses `try_transition_attachment_batch_status(expected='pending',
  new='expired')`.
- If reaper commits `expired` first, cancellation returns `not_eligible`; if cancellation commits
  first, the reaper CAS fails and `_plan_batch` never plans the cancelled batch.
- `_NON_REAPABLE` and `_plan_batch` provide a second guard even if a future selector includes
  cancelled.

**Verdict: PASS by code/CAS reasoning and unit tests.** No direct simultaneous cancel-vs-sweep test
was found (T1). SQLite serializes the two writers; no filesystem/SQLite atomicity is claimed.

### 5.5 Item insertion vs. cancellation

- `accept_attachment_item` uses a conditional INSERT requiring parent `pending`, owner, and
  conversation (`bot/db.py:1998-2071`).
- If cancellation commits first, the INSERT fails and `AttachmentService.accept` catches
  `AttachmentBatchStateChanged` and returns `REJECTED_BATCH` without downloading bytes
  (`bot/attachments.py:1163-1166`).
- If insertion commits first, cancellation can then cancel; the item remains, which is intended.
- Test `test_append_item_cannot_land_in_cancelled_batch` covers the DB-level rejection; no direct
  accept-vs-cancel interleaving test was found (T5).

**Verdict: PASS by code and DB-level test.**

### 5.6 Item reaping vs. cancellation

- `mark_attachment_item_reaped` refuses a `cancelled` parent (`bot/db.py:1717-1729`).
- The reaper only plans terminal batches; cancellation only targets `pending`; the two paths do not
  normally overlap.
- **N2:** the method does not require a terminal parent. A temporary verification on a temp database
  (not repository data) showed:
  `pending_parent_mark_reaped=True`, `pending_parent_item_status=reaped`.
  No production caller does this, but a future caller could bypass the intended terminal-parent
  invariant.

**Verdict: PASS for the requested cancelled guard; design gap N2 remains.**

### 5.7 SQLite BUSY/LOCKED and permanent DB errors

- `Database` uses one connection, WAL, `busy_timeout=5000` (`bot/db.py:574-590`).
- Cancellation wraps its state change in `BEGIN IMMEDIATE`; an exception triggers `rollback` and
  propagates (`bot/db.py:1375-1431`).
- `attachments_cancel` re-raises DB exceptions and emits no success reply (`bot/handlers.py:3121-3123`).
- Test `test_database_failure_rolls_back_cancellation` and
  `test_command_database_failure_has_no_success_reply` cover permanent failures.
- No cancellation-specific test was found for actual SQLite `BUSY`/`LOCKED` contention. General
  transient-error classification tests and a `PRAGMA busy_timeout == 5000` test exist elsewhere, but
  they do not exercise this cancellation transaction under contention (T6).

**Verdict: PASS for fail-closed behavior; cancellation-specific BUSY/LOCKED timing NOT VERIFIED.**

### 5.8 Filesystem errors and partial writes

- Cancellation itself performs no filesystem operation.
- Existing storage cleanup uses `_safe_unlink` for partial/new files; reaper uses `_remove_file`
  with `lstat`/regular-file/path checks and retry.
- The tests for these paths pass in the full suite; Stage 1 does not add a new deletion primitive.
- No new Stage 1 filesystem error injection was added; existing coverage remains.

**Verdict: PASS for cancellation (no FS operation); FS behavior is inherited and tested elsewhere.**

### 5.9 Process interruption and retry/idempotency

- Cancellation commit is a single SQLite transaction; a crash before commit leaves `pending`, after
  commit leaves `cancelled` with no file/row deletion.
- Duplicate update handling checks `update_is_processed` inside the transaction; repeated new
  command returns `already_cancelled`.
- Tests cover reopen durability, duplicate update, duplicate cancellation, and DB rollback.
- No crash-injection test at the exact commit boundary was found (T7).

**Verdict: PASS for durable/idempotent behavior; crash-boundary coverage is partial.**

### 5.10 No atomicity claim

No report or code claims SQLite/filesystem atomicity. Cancellation does not touch the filesystem;
storage remains DB-first with `_safe_unlink` on failure; reaper remains DB-first `reaped` then unlink.

---

## 6. Test commands and actual results

All commands were run from `/workspace/project/OpenHandBot` with the existing
`/tmp/ohb2-venv/bin/python`; no dependency installation or upgrade was performed.

| Command | Exit | Actual result |
|---|---:|---|
| `/tmp/ohb2-venv/bin/python -m pytest -q tests/test_wp01_stage1_cancellation.py` | 0 | **39 passed** in 2.51s |
| Same focused test, three repeated runs | 0 | **39 passed** each (2.57s / 2.47s / 2.47s) |
| `/tmp/ohb2-venv/bin/python -m pytest -q tests/test_wp01_stage1_cancellation.py tests/test_wp01_attachment_lifecycle.py tests/test_attachment_cleanup_expiration_a4.py tests/test_attachment_batch_lifecycle_a2.py tests/test_attachment_staging_a1.py tests/test_def011_fs_offload.py tests/test_f01_reaper_fs_offload.py tests/test_repair_plan_02_life01_f2_race.py tests/test_repair_plan_02_life01_opportunistic_cleanup.py tests/test_repair_plan_02_life02_crash_recovery.py tests/test_app.py tests/test_handlers.py tests/test_attachment_batch_state_routing_f1_1a.py tests/test_attachment_message_identity_a3.py tests/test_miniapp_attachment_download_mt2.py tests/test_doc_code_parity.py tests/test_attachment_batch_schema.py` | 0 | **539 passed**, 2 warnings, 26.59s |
| `/tmp/ohb2-venv/bin/python -m pytest -q` | 0 | **3584 passed**, 74 warnings, 173.04s |
| `/tmp/ohb2-venv/bin/python -m pytest --collect-only -q tests/test_wp01_stage1_cancellation.py` | 0 | **39 tests collected** |
| `/tmp/ohb2-venv/bin/python -m pytest -q tests/test_repair_plan_02_life01_f2_race.py::test_store_into_already_expired_batch_is_rejected` | 0 | **1 passed** (evidence for N1) |
| `node --test tests/frontend/*.test.js` | 0 | **280 tests, 280 pass, 0 fail** |
| `/tmp/ohb2-venv/bin/python -m pyflakes bot/ automation/ tools/ main.py tests/` | 0 | no output |
| `git diff --check` | 0 | no output |
| `/tmp/ohb2-venv/bin/python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | 0 | **High 0**, Medium 19, Low 5 |
| `/tmp/ohb2-venv/bin/python -m pip_audit -r requirements-dev.txt` | 0 | **No known vulnerabilities found** |

### 6.1 Additional read-only check

A temporary Python process (outside the repository, temp directory, no repository data) checked the
parent-batch guard:

```text
pending_parent_mark_reaped= True
pending_parent_item_status= reaped
```

This is evidence for N2; it did not modify repository data or code.

### 6.2 Not run / not verified

- Actual SQLite `BUSY`/`LOCKED` contention and timeout behavior.
- Direct concurrent cancel-vs-sweep interleaving.
- Direct cancellation of a batch while a synchronous `store()` is in progress on the same event-loop
  thread (production uses `store_async`).
- Crash injection at the exact SQLite commit boundary.
- Independent review by a separate reviewer/session; **not claimed**.

---

## 7. Scope, regression, and documentation audit

### 7.1 Scope checks

| Check | Result | Evidence |
|---|---|---|
| New worker/queue/database/process | **PASS — none** | No new thread/queue/process/DB in Stage 1 diff; guard uses existing `to_thread` |
| Bot + ASGI / SQLite ownership model | **PASS — unchanged** | One bot+ASGI process; one `Database` connection; no Mini App changes |
| Mini App files/behavior | **PASS — unchanged** | No `bot/web`/`docs/MINI_APP.md` diff |
| Stage 2 cleanup policy | **PASS — unchanged** | No cleanup command/timer/reaper path for cancelled; Stage 2 docs untouched |
| Automatic cleanup for cancelled | **PASS — none** | `_NON_REAPABLE`; no cancelled reaper selection |
| Attachment files/rows/identity deletion | **PASS — none** | No attachment `DELETE` SQL; cancellation code has no file/row deletion |
| Autopush | **PASS — not activated** | No automation/autopush changes; no deployment |
| Production Telegram/OpenHands calls in Stage 1 tests | **PASS — none** | Stage 1 tests use fake Telegram objects and `None` clients; no `httpx`/network calls |

### 7.2 Documentation consistency

- `docs/OPERATIONS_RUNBOOK.md:320` accurately documents `/attachments_cancel <batch_id> confirm`,
  `pending` only, no file/row/identity deletion, no route clear, and non-reapable cancelled batches.
- `HELP_TEXT` and `BOT_COMMANDS` both include `attachments_cancel`; `tests/test_app.py` parity passes.
- `/attachments` lists cancelled status and the command hint (`bot/handlers.py:3038-3039`).
- **N3:** `docs/reviews/OHB2-WP01-STAGE1-CANCELLATION-IMPLEMENTATION-REPORT.md` says the sync lock
  is acquired through "asyncio's executor"; the actual implementation uses
  `anyio.to_thread.run_sync` (`bot/attachments.py:548-549`). This is a wording inaccuracy only.
- No stale command text was found in the runbook for `/attachments_cancel`.

### 7.3 Missing tests / coverage gaps

| ID | Gap | Impact |
|---|---|---|
| T1 | No direct concurrent cancellation-vs-reaper sweep test | CAS proof exists; unit test covers non-pending CAS; race not directly exercised |
| T2 | No handler test for `rejected_batch` storage-race reply | Message code is straightforward; response text not directly asserted |
| T3 | No explicit assertion that `/attachments_cancel` preserves `user_state`/route | Code has no route clear; design requirement not directly tested |
| T4 | No test that `/attachments_clear` rejects `cancelled` | Clearable set excludes it; direct test absent |
| T5 | No direct accept-vs-cancel interleaving test | DB conditional insert and `AttachmentBatchStateChanged` path exist; unit test covers DB rejection |
| T6 | No cancellation-specific SQLite `BUSY`/`LOCKED` contention test | Fail-closed behavior exists; general classification/PRAGMA tests exist; this transaction's contention timing unverified |
| T7 | No crash injection at the exact cancellation commit boundary | Reopen/durability tests exist; crash boundary not directly exercised |

---

## 8. Is the implementation safe to proceed to a future independent review?

**Yes — with the notes above.**

The requested twelve Stage 1 safety requirements are satisfied in the actual working tree, and the
focused/related/full suites pass. The implementation is safe to hand to a genuinely independent
reviewer, provided that reviewer explicitly evaluates:

1. the `_store_prepare` non-pending design gap (N1);
2. the terminal-parent design gap in `mark_attachment_item_reaped` (N2);
3. the missing race/BUSY/crash tests (T1-T7);
4. exact Stage 1 hunk attribution, which is not possible from Git alone in this dirty tree.

This verification does **not** grant independent approval. A future independent review should be a
separate session with independent repository access, and should not rely on this report alone.

---

## 9. Exact SHA-256 values

### 9.1 This report

- **Report self-hash (reproducible):** `18ce87dcbbda9c6a437ff119cf7f8c6dc6dad0f5d7b8f179a216cf671779bfca`

Definition: SHA-256 of this file after replacing the 64-hex value on the self-hash line with an empty
string. A literal full-file hash cannot be embedded in the file without changing that file; the actual
final `sha256sum` is reported in the task's final response.

### 9.2 Implementation / working-tree diff

- **Full working-tree diff SHA-256:** `a57bfbe453adcf2d9a08e78f81c9c7fd2efb6fc16f526e27ebfdc8754cf33f3d`
  (includes unrelated uncommitted changes; not a Stage 1-only patch).
- **Stage 1 test file SHA-256:** `ce5dfcb77e2d9f76a5bd5e615b7c52b7e994c27b90fa22011607ef4f70ba2492`
- **Stage 1 source file hashes:** see §3; all match the implementation report.

**Exact Stage 1 hunk hash is not calculable** because Stage 1 changes are intermingled with unrelated
uncommitted changes in the same files and there is no Stage 1 commit.

---

## 10. Working tree vs. committed/published code

| Aspect | Working tree | Committed / published |
|---|---|---|
| Stage 1 implementation | **Present** (uncommitted) | **Absent** at HEAD `0774c9c...` |
| `ATTACHMENT_BATCH_CANCELLED` | Present in working tree | Not found by `git grep HEAD` |
| `/attachments_cancel` | Present in working tree | Not found by `git grep HEAD` |
| Stage 1 test file | Untracked in working tree | Not in HEAD |
| Stage 2 docs | Untracked prior artifacts | Not in HEAD |
| Remote/PR/deployment | Not touched | Not published |

No commit, push, PR, merge, deployment, or Autopush occurred. The verified code is **not** published
and is not a release artifact.

---

## 11. Limitations and preservation confirmation

- This task is **not** an independent review and does **not** establish independent approval.
- The full Python suite, related tests, focused tests, Node tests, pyflakes, Bandit, pip-audit, and
  `git diff --check` were run; see §6.
- No application code, tests, configuration, schema, Mini App, runtime data, or existing report was
  modified.
- The only new file is this report.
- No fetch, pull, branch switch, reset, clean, restore, stage, commit, push, PR, merge, deployment, or
  Autopush occurred.
- All pre-existing tracked, untracked, and ignored files were preserved. The final status is the
  baseline plus this one report.

**WP-01 remains open. Stage 1 is verified in the working tree only; independent review and owner
approval remain outstanding.**
