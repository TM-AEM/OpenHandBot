# OHB2-WP01-ACTIVE-BATCH-CANCELLATION-SAFETY-DESIGN — Task Report

- **Task ID:** `OHB2-WP01-ACTIVE-BATCH-CANCELLATION-SAFETY-DESIGN`
- **Date:** 2026-11-22
- **Status:** `COMPLETE_WITH_NOTES`
- **Mode:** read-only inspection plus creation of the two required design documents. No implementation.
- **Recommendation:** **Option C — two-stage cancellation**; Stage 1 adds a durable, non-reapable
  `cancelled` state and Stage 2 cleanup is deferred to a separate owner decision.
- **Owner approval:** **NONE RECORDED. WP-01 IS NOT CLOSED.**

---

## 1. Actual baseline and Git state

| Item | Verified value |
|---|---|
| Working directory | `/workspace/project/OpenHandBot` |
| Branch | `main` |
| HEAD | `0774c9cff923a2ed02da36a1111a283a61600ea5` |
| HEAD tree | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| Last commit | `0774c9c fix(rev-01): drop stale browser cache snapshots and add review handoff package` |
| Index | Empty; `git diff --cached --name-status` produced no entries |
| Staged changes | None |
| Working-tree state | Pre-existing WP-01/poller/WP-08 changes were already present and were preserved |
| Untracked state | Pre-existing reports/decision records and `tests/test_wp01_attachment_lifecycle.py` were preserved |
| Ignored state | `.pytest_cache`, `__pycache__`, `.openhands/memory` were preserved |

The supplied baseline matches the actual committed baseline exactly. It does **not** describe the
working tree: the WP-01 implementation is uncommitted. The design therefore cites the working-tree
implementation and clearly labels it as such.

No fetch, pull, branch switch, reset, restore, clean, stage, commit, or push was performed.

---

## 2. Evidence inspected

### 2.1 Instructions and records

- `AGENTS.md` (full).
- `docs/audits/OHB2-WP01-ATTACHMENT-LIFECYCLE-IMPLEMENTATION-REPORT.md` — actual WP-01 report
  (untracked; there is no `docs/reviews/` copy).
- `docs/decisions/OHB2-WP01-OD01-OD03-OWNER-DECISION-RECORD.md`.
- `docs/reviews/OHB2-OD01-OD03-OWNER-DECISION-PACKAGE.md`.
- `docs/reviews/OHB2-MASTER-BACKLOG-RECONCILIATION-AND-NEXT-TASK-REPORT.md` (historical status;
  stale for WP-01 implementation).
- `.agent/PROGRESS.md` (read-only; not modified).
- Current `docs/OPERATIONS_RUNBOOK.md`, `docs/ZERO_TOUCH_STARTUP.md`, and `README.md` attachment
  documentation.

### 2.2 Source paths and functions examined

| Area | Paths / functions |
|---|---|
| `/cancel` | `bot/handlers.py::cancel_route` (3076-3086), `cancel_route_button` (3089-3101) |
| User state | `bot/db.py::clear_awaiting_and_record_outcome` (3039-3069), `_clear_awaiting_nocommit` (3031-3037) |
| Attachment intake | `bot/handlers.py::handle_attachment` (2553-2675), `_attachment_service` (2357-2380) |
| Attachment routing | `bot/db.py::classify_attachment_routing` (1610-1698), `AttachmentRoutingState` (517-538), `has_unknown_attachment_batch_status` (1517-1527) |
| Batch states | `bot/db.py:115-166` (`ATTACHMENT_BATCH_STATUSES`, unresolved/clearable sets), `AttachmentBatch` (499-514) |
| Batch creation/transition | `create_attachment_batch` (1097-1117), `mark_attachment_batch_status` (1309-1318), `try_mark_attachment_item_stored` (1233-1283), `record_attachment_intent` (1700-1790), `accept_attachment_item` (1862-1908), `accept_attachment_item_into_new_batch` (1910-1985) |
| Terminal queries | `list_live_pending_attachment_batches` (1322-1345), `has_expired_pending_attachment_batch` (1347-1371), `list_unresolved_attachment_batches` (1373-1386), `has_terminal_attachment_batch` (1388-1405), `list_terminal_attachment_batches` (1407-1420), `is_attachment_terminal_cleared` (1430-1445), `clear_attachment_terminal_batch` (1447-1515) |
| Staging/persistence | `bot/attachments.py::AttachmentService.accept` (1039-1148), `StagingStore._accept_lock` (521-526), `_store_prepare` (662-761), `_write_to_path` (628-660), `_store_finalize` (763-799), `store_async` (881-980) |
| Reaper | `AttachmentReaper` (1227-1745), `_TERMINAL` (1242-1250), `sweep`/`sweep_async` (1272-1305), `_sweep_db_phase` (1313-1388), `_mark_expired` (1460-1474), `_plan_batch` (1476-1538), `_plan_orphan_items` (1564-1620), `_remove_file` (1689-1735), `OpportunisticSweeper` (1749-1858) |
| Startup/worker | `bot/app.py` startup hook (245-259), `bot/watcher.py::tick` (177-183), `bot/outbox.py::OutboxWorker` (672-695), `outbox_recover` (529-555) |
| Concurrency/duplicate | `bot/app.py:77-93`, `bot/polling.py:155-178`, `bot/handlers.py::dedupe_update` (490-570), `Database.mark_update_outcome` (3196-3236), `add_or_group_outbox` (3463-3560) |
| Schema | `attachment_batches`/`attachment_items`/`attachment_message_identity` (779-825); `settings`; `Database.__init__` WAL/busy_timeout (558-590) |
| Mini App read path | `bot/web/services.py:790-870` (`latest_pending` + list; no deletion) |
| Tests | `tests/test_wp01_attachment_lifecycle.py` (especially `test_cancel_does_not_delete_active_batch_data`), `tests/test_repair_plan_02_life01_f2_race.py`, `tests/test_repair_plan_02_life02_crash_recovery.py`, `tests/test_attachment_cleanup_expiration_a4.py` |

### 2.3 Read-only verification performed

- Existing `/cancel` tests:

```text
/tmp/ohb2-venv/bin/python -m pytest -q tests/test_wp01_attachment_lifecycle.py -k 'cancel'
2 passed, 26 deselected in 0.44s
```

This confirms the current behavior asserted by the existing tests: `/cancel` leaves the active
batch `pending` and does not delete its item rows.

- `git diff --check` was run after document creation (see §5).
- No dependency installation or environment modification was performed in this task. The existing
  `/tmp/ohb2-venv` from the prior implementation task was reused only for the two read-only tests.

---

## 3. Findings

1. **`/cancel` is not a batch cancellation.** It clears only `user_state` and records an outcome;
   the batch stays `pending`. After the route is cleared, accompanying text is rejected as
   `route_mismatch` until the batch expires.
2. **The current reply is misleading.** It says the route was cancelled but does not disclose that
   the attachment batch remains active and will be subject to TTL/reaper behavior.
3. **The existing reaper can delete bytes for `delivered`/`expired`/`rejected`/`failed`.**
   `_TERMINAL` excludes all other statuses. Adding `cancelled` without an explicit exclusion would
   be unsafe.
4. **Expiry is an unconditional status update.** `mark_attachment_batch_status` has no expected
   status. A new cancellation state must use a CAS `pending → expired` transition so an expiry path
   cannot overwrite `cancelled` and make it terminal/deletable.
5. **`_store_prepare` does not check batch status.** It verifies ownership and conversation but not
   `pending`. A cancellation that wins before a write would not prevent the write unless this check
   is added and cancellation shares the existing `_accept_lock`.
6. **The attachment lifecycle does not use outbox.** `accept` and `record_attachment_intent` are
   local-only; no attachment outbox row exists. Outbox changes are not required for Stage 1.
7. **No schema migration is required for a `cancelled` status.** `status` is unconstrained `TEXT`;
   the status set is application-level. No new table/column is needed.
8. **No new worker/ownership model is required.** Cancellation can use the existing DB connection
   and the existing store lock; reaper exclusion is a guard in existing code.

---

## 4. Recommendation

**Adopt Option C: two-stage cancellation.**

### Stage 1 (proposed, not implemented)

- Add a durable `cancelled` batch status.
- Allow only `pending → cancelled`, for exactly one owner-owned batch matching the current `route`
  conversation, with CAS and an atomic route clear/outcome record.
- Use the existing `StagingStore._accept_lock` in the cancellation path; add a `pending` status
  check in `_store_prepare`.
- Explicitly exclude `cancelled` from the reaper and use CAS for `pending → expired`.
- Do not touch items, bytes, identity evidence, or any row.
- Treat `cancelled` as a non-blocking routing state for ordinary prompts; only `pending` is
  cancellable in Stage 1, so no message identity is involved.
- Keep `intent_recorded`/`dispatching`/`uncertain` non-cancellable and fail-closed.

### Stage 2 (not authorized)

- Separate owner decision for any eventual cleanup.
- Explicit per-batch confirmation, retention policy, DB-first/idempotent unlink.
- No automatic reaper selection of `cancelled`; no extension of OD-01 to `cancelled`.

### Required reaper rules

- `cancelled` is **not** in `AttachmentReaper._TERMINAL`.
- Add a non-reapable set and skip/report it in `_sweep_db_phase` and `_plan_batch`.
- Use CAS for expiry; never overwrite `cancelled`.
- Never mark items of a cancelled batch `reaped`.
- Never delete batch/item/identity rows.

### Migration / outbox

- **Schema migration:** none for Stage 1.
- **Reaper changes:** required.
- **Outbox changes:** none for Stage 1.
- **Mini App:** no change; it continues to list only `pending` batches, so cancelled batches are not
  downloadable there. Changing that is outside this design.

---

## 5. Files created and SHA-256

| File | Lines | SHA-256 |
|---|---:|---|
| `docs/reviews/OHB2-WP01-ACTIVE-BATCH-CANCELLATION-SAFETY-DESIGN.md` | 690 | `5436c2b1539eee7843b03c21137cc4926eac7a92c39a32bb98ea2f2bd66e4545` |
| `docs/reviews/OHB2-WP01-ACTIVE-BATCH-CANCELLATION-SAFETY-DESIGN-REPORT.md` | 221 | `7a30366779aff613d56c7685d69960c4833decf16152695734c2242f88d08913` — hash computed over this report **excluding this table row** |

The report hash is defined as the SHA-256 of this report **with the table row containing the text
“hash computed over this report **excluding this table row**” excluded** (a self-referential
full-file hash cannot include itself). The final response also records the actual full-file
`sha256sum` after finalization.

No other file was created, modified, renamed, moved, or deleted by this task.

---

## 6. Verification results

| Check | Result |
|---|---|
| `git diff --check` | exit 0; no output (run after document creation) |
| Existing `/cancel` tests | 2 passed, 26 deselected |
| Design citations vs source | verified against working tree; see §2 |
| Schema migration | not required; verified `status TEXT` with no CHECK |
| Reaper conditions | verified `_TERMINAL` and `_sweep_db_phase`/`_plan_batch`/`_remove_file` |
| Outbox interaction | verified attachment accept/intent paths create no outbox row |
| Full Python suite | **NOT RUN**; this is design-only and no implementation is authorized |
| Implementation tests | **NOT CLAIMED** |
| Live Telegram/OpenHands | **NOT RUN**; no production calls or credentials |
| Independent review | **NOT CLAIMED** |

---

## 7. Limitations and honest notes

- The current WP-01 implementation is **uncommitted working-tree state**. The design is evaluated
  against that actual state; the committed baseline alone does not contain the new `/attachments`
  and clearance implementation.
- The historical master backlog says WP-01 was not started; that record is stale relative to the
  working tree. It was not rewritten.
- No stress test of the proposed lock/CAS design was run, because implementation is not authorized.
  The race analysis is based on the actual code paths and SQLite/anyio behavior; it must be proven
  with deterministic tests in a later implementation task.
- A cancellation that arrives after the reaper has already committed `expired` cannot undo that
  decision. The design requires an honest `not_eligible`/`too_late` response, not a false success.
- Cancelled bytes are retained indefinitely in Stage 1. This is intentional because no destructive
  cleanup is authorized; it can consume the staging byte cap and requires an owner decision.
- The Mini App currently hides non-`pending` batches (`bot/web/services.py:842-870`); making
  cancelled batches visible there would touch the frozen Mini App boundary and is not authorized.
- No owner approval was recorded. The recommendation is a proposal only.

---

## 8. Explicit preservation and authorization confirmation

- **No application code or tests were modified.**
- **No dependencies, lockfiles, runtime configuration, or CI were modified.**
- **No Mini App, `bot/web`, or `docs/MINI_APP.md` was modified.**
- **No SQLite schema or data was changed.**
- **No reaper or outbox code was modified.**
- **No attachment file was deleted, moved, renamed, or cleaned.**
- **No database row was deleted.**
- **No OD-01/OD-03 decision was changed.**
- **No historical decision record was modified.**
- **No owner approval was recorded.**
- **No staging, commit, push, PR, merge, deployment, release, or Autopush activation occurred.**
- All pre-existing tracked, untracked, and ignored files were preserved.
- **WP-01 remains `DONE_WITH_NOTES` for its authorized scope only; it is not closed.**
