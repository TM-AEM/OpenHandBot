# OHB2-WP01 — Stage 2 Cleanup Policy and Owner Decision Report

- **Task ID:** `OHB2-WP01-STAGE2-CLEANUP-POLICY-AND-OWNER-DECISION`
- **Date:** 2026-11-21
- **Repository:** `/workspace/project/OpenHandBot`
- **Status:** `DESIGN ONLY — COMPLETE_WITH_NOTES`
- **Owner approval:** **NONE RECORDED**
- **WP-01:** **NOT CLOSED**

---

## 1. Overall verdict

**COMPLETE_WITH_NOTES.**

The read-only audit and the owner decision package are complete. The package identifies the actual
attachment data, every production file and database deletion/mutation path found, the state
eligibility boundaries, the four cleanup alternatives, the safety/recovery requirements, and the
owner decisions that remain unfilled.

The notes are material:

- Stage 1 is present only as uncommitted working-tree code; the historical HEAD does not contain it.
- The reported Stage 1 test results were **not rerun** in this design-only task.
- `delivered`, `dispatching`, `uncertain`, `rejected`, and `failed` have no production transition
  found in the current tree; their cleanup behavior is defined only by constants/reaper/test setup.
- There is no dedicated `cancelled_at` timestamp, no cleanup audit record, and no unique constraint on
  `staging_token`.
- All owner decisions remain unfilled.

No application code, test, database, attachment file, or runtime behavior was modified.

---

## 2. Actual Git state

Observed before creating the two deliverables:

| Item | Value |
|---|---|
| Branch | `main` |
| HEAD | `0774c9cff923a2ed02da36a1111a283a61600ea5` |
| HEAD tree | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| Index tree | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| Tracked modifications | 20 |
| Untracked files | 23 |
| Staged changes | None |
| Git operations | No fetch, pull, switch, reset, clean, restore, stage, commit, or push |

The complete baseline status snapshot was:

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

After creating this report and the decision package, the only additions are the two deliverables
listed in §9. All other status lines were verified unchanged by comparing a saved baseline snapshot
with the final status.

**Stage 1 is uncommitted:** `git grep HEAD -- bot tests docs` found no `ATTACHMENT_BATCH_CANCELLED`
and no `attachments_cancel`. The code exists only in the working tree.

---

## 3. Inspected source files and functions

Read-only inspection covered:

| Area | Files / functions |
|---|---|
| Instructions | `AGENTS.md` |
| Database/schema | `bot/db.py`: `_init_schema`, `_migrate`, `AttachmentBatch`, `AttachmentItem`, `ATTACHMENT_BATCH_*`, `ATTACHMENT_ITEM_*`, `create_attachment_batch`, `add_attachment_item`, `set_attachment_item_status`, `try_mark_attachment_item_stored`, `mark_attachment_batch_status`, `try_transition_attachment_batch_status`, `cancel_pending_attachment_batch`, `list_*attachment*`, `clear_attachment_terminal_batch`, `mark_attachment_item_reaped`, `classify_attachment_routing`, `record_attachment_intent`, `accept_attachment_item`, `accept_attachment_item_into_new_batch` |
| Storage/service | `bot/attachments.py`: `staging_root_for`, `ensure_staging_root`, `_safe_unlink`, `_is_within`, `staging_total_bytes`, `StagingStore._write_to_path`, `_store_prepare`, `_store_finalize`, `_store_write`, `store`, `store_async`, `cancellation_guard`, `AttachmentService.accept`, `cancel_pending_batch` |
| Reaper | `bot/attachments.py`: `AttachmentReaper._TERMINAL`, `_NON_REAPABLE`, `sweep`, `sweep_async`, `_sweep_db_phase`, `_sweep_fs_tail`, `_apply_cleanups`, `_finalize`, `_mark_expired`, `_plan_batch`, `_finish_batch`, `_plan_orphan_items`, `_scan_root_untracked`, `_count_unsafe_entries`, `_validated_root`, `_is_unsafe_entry`, `_remove_file`, `_log_report`, `OpportunisticSweeper` |
| Handlers/routing | `bot/handlers.py`: `_attachment_service`, `handle_attachment`, `handle_unsupported_attachment`, `_handle_accompanying_text`, `attachments_list`, `attachments_clear`, `attachments_cancel`, `cancel_route` |
| App/watcher | `bot/app.py`: `BOT_COMMANDS`, handler registration, `_post_init` reaper wiring, Mini App wiring; `bot/watcher.py`: `tick` |
| Mini App/read path | `bot/web/services.py`: `download_attachment`, `list_staged_attachments`; `bot/web/download.py`: `resolve_staged_path`, `open_staged_file`, `iter_file_chunks` |
| Config/limits | `bot/config.py`: `db_path`, `attachment_document_intake_enabled`; `bot/attachments.py`: `MAX_ATTACHMENT_BYTES`, `MAX_ITEMS_PER_BATCH`, `MAX_STAGING_TOTAL_BYTES`, `ATTACHMENT_BATCH_TTL`; `bot/files.py`: `is_safe_workspace_path`, `is_valid_conversation_id` |
| Decisions/docs | `docs/decisions/OHB2-WP01-OD01-OD03-OWNER-DECISION-RECORD.md`; `docs/reviews/OHB2-WP01-ACTIVE-BATCH-CANCELLATION-SAFETY-DESIGN.md`; `docs/OPERATIONS_RUNBOOK.md` |
| Tests read | `tests/test_wp01_stage1_cancellation.py`; `tests/test_attachment_cleanup_expiration_a4.py`; `tests/test_repair_plan_02_life02_crash_recovery.py`; `tests/test_repair_plan_02_life01_f2_race.py`; `tests/test_repair_plan_01_review_findings.py`; `tests/test_attachment_batch_schema.py`; `tests/test_doc_code_parity.py` |

No function was modified.

---

## 4. Attachment-data inventory summary

### 4.1 SQLite

- `attachment_batches`: batch ID, owner, conversation, `t0`, status, timestamps, `intent_text`.
- `attachment_items`: item ID, batch ID (no FK), staging token (no unique constraint), display name,
  size, status, timestamps.
- `attachment_message_identity`: composite message identity, batch ID with `ON DELETE RESTRICT`,
  conversation, timestamp.
- `settings`: `attachment_terminal_clearance:<batch_id>` owner marker; blocker clearance only.
- `processed_updates` / `update_failures`: outcome/failure logs; not attachment content.
- `outbox`: **no attachment rows**; attachment intent is local only.

### 4.2 Filesystem

- Root: `<db_parent>/attachment_staging`, mode `0700`; root symlink/non-directory rejected.
- File names: opaque 32-hex tokens; mode `0600`; no user filename used as a path.
- Partial files: deleted by store failure cleanup.
- Orphan files: counted, not deleted.
- Unsafe entries: counted, not followed/deleted.
- `.gitignore` uses `.attachment_staging/` (leading dot), while code uses `attachment_staging`; this
  is a pre-existing ignore mismatch, not changed here.

---

## 5. Identified deletion paths

### 5.1 File deletion

1. `StagingStore._write_to_path` / `_safe_unlink` (`bot/attachments.py:652-684`, `290-295`):
   automatic cleanup of a newly written partial file after a write failure.
2. `StagingStore._store_finalize` / `_safe_unlink` (`bot/attachments.py:793-829`): automatic cleanup
   when an item cannot become `stored`.
3. `StagingStore._store_write` / `_safe_unlink` (`bot/attachments.py:831-867`): automatic cleanup on
   head-read failure.
4. `AttachmentReaper._apply_cleanups` -> `_remove_file` (`bot/attachments.py:1498-1505`,
   `1803-1849`): automatic deletion of terminal/expired files and orphan-item files.
5. `AttachmentReaper._plan_orphan_items` (`bot/attachments.py:1678-1734`): automatic deletion of
   bytes for items whose parent batch row is missing. **This is the hidden bypass risk if a batch row
   is ever deleted.**
6. `_scan_root_untracked` and `_count_unsafe_entries`: observation only; delete nothing.
7. Mini App download: read-only; deletes nothing.
8. `/attachments_clear`: writes a settings marker; deletes no files/rows.

### 5.2 Database deletion

**No production attachment `DELETE` statement exists.** Repository-wide search found zero
`DELETE FROM attachment_batches`, `DELETE FROM attachment_items`, or
`DELETE FROM attachment_message_identity` statements in `bot/`. The only attachment DB mutations are
INSERT/UPDATE (batch/item/identity/settings) and the separate `processed_updates` pruning.

The important mutation paths are listed in the decision package §5.2. The generic
`mark_attachment_batch_status` (unconditional) and `set_attachment_item_status` (no batch guard) are
not cleanup paths, but are future hazards if reused without CAS/ownership checks.

---

## 6. State eligibility findings

- `cancelled` is non-terminal and non-reapable: `_NON_REAPABLE` and early `_plan_batch` skip; item
  `reaped` CAS refuses a cancelled parent.
- `pending` is active/live; it can become `expired` at TTL; the reaper then uses the existing terminal
  path.
- `expired` and `rejected` already have file cleanup through the existing reaper and explicit
  blocker clearance through `/attachments_clear`.
- `delivered` and `failed` are terminal and never clearable; file cleanup is handled by the existing
  reaper if those states exist.
- `intent_recorded`, `dispatching`, `uncertain`, unknown/NULL/malformed states are protected:
  unresolved or fail-closed; no cleanup.
- No production writer was found for `delivered`, `dispatching`, `uncertain`, `rejected`, or `failed`;
  their current behavior is theoretical/state-fixture behavior until a later stage.

Separate permissions are documented in the package §8.1: blocker clearance, file deletion, item-row
deletion, batch-row deletion, identity deletion, and audit removal are distinct and must not be
conflated.

---

## 7. Option comparison and recommendation

| Option | Summary | Verdict |
|---|---|---|
| A — permanent retention | Keep all rows/identity/files; no cleanup | **Recommended now** |
| B — time-based automatic | Delete after a retention period | **Not recommended**; no trustworthy clock/marker, reaper policy change, high risk |
| C — explicit owner-confirmed | Exact batch, preview, confirm, file-only deletion | **Only acceptable future destructive path**, after separate approval |
| D — hybrid | Retain rows/identity/audit; delete bytes | Future variant of C; requires schema/status/audit decision |

**Recommendation:** adopt Option A for this decision. If cleanup becomes necessary, design Option C
(optionally with D's retained-row audit properties) in a separate owner-authorized task. Do not add
`cancelled` to `_TERMINAL`, do not delete batch/identity rows, and do not reuse
`/attachments_clear`.

---

## 8. Unresolved risks and owner decisions

Material unresolved risks are documented in package §17, including:

- shared/duplicate `staging_token` and no unique constraint;
- orphan-item path bypassing cancelled protection if a batch row is deleted;
- no dedicated `cancelled_at` or cleanup audit;
- no file identity/hash and no owner check in `_remove_file`;
- cancelled files count toward the 64 MiB staging cap;
- `.gitignore` staging-name mismatch;
- Stage 1 uncommitted and its reported tests not rerun;
- terminal states with no production writer;
- batch-row deletion changing routing/blocking and identity FK restrictions;
- wall-clock trust, partial deletion, disk/permission errors, and no exactly-once claim.

All owner decisions in package §19 remain **NOT FILLED**. No approval is recorded on the owner's
behalf.

---

## 9. Exact files created

1. `docs/reviews/OHB2-WP01-STAGE2-CLEANUP-POLICY-AND-OWNER-DECISION-PACKAGE.md`
2. `docs/reviews/OHB2-WP01-STAGE2-CLEANUP-POLICY-AND-OWNER-DECISION-REPORT.md`

No other file was created, modified, deleted, moved, renamed, or truncated.

---

## 10. Verification

### 10.1 Commands and results

| Command | Result |
|---|---|
| `git branch --show-current` | `main` |
| `git rev-parse HEAD` | `0774c9cff923a2ed02da36a1111a283a61600ea5` |
| `git rev-parse HEAD^{tree}` | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| `git write-tree` | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| `git status --porcelain` (baseline) | 20 modified + 23 untracked; no staged changes |
| `git diff --check` | exit **0** |
| `sha256sum` package | `7769b65c32c820104d6bf09e25d27f4d610a4e182ff3ebdfe87338cbe92be654` |
| `sha256sum` report | See §10.2 self-hash and final detached value |
| Full Python/Node/lint suites | **Not run** in this design-only task |

`git diff --check` was run after both deliverables were created; it returned exit 0 (no whitespace
errors).

### 10.2 SHA-256 of both deliverables

- **Decision package:** `7769b65c32c820104d6bf09e25d27f4d610a4e182ff3ebdfe87338cbe92be654`
- **Report self-hash:** `f60f99aa0cfd178a93a1e018c9597a5e573a264c3a1770e5c152a5454c598d00`

The report hash is a reproducible self-hash: SHA-256 of this file after replacing the 64-hex value on
the self-hash line with an empty string. A literal SHA-256 of the final file cannot be embedded in
its own content without changing that content; the actual final file hash is also reported in the
task's final response and can be checked with `sha256sum`.

### 10.3 Preservation confirmation

- Baseline `git diff` hash and status snapshot were saved outside the repository before writing.
- After writing, the only status additions are the two deliverables above; all pre-existing modified
  and untracked files remain unchanged.
- No staging, commit, push, PR, merge, deployment, or Autopush activation occurred.
- No database row, attachment file, test, application source, Mini App file, or runtime process was
  modified or deleted.

### 10.4 Explicit confirmation

**No cleanup, deletion, reaping, retention change, state transition, or database mutation was
performed.** This task was read-only except for creating the two Markdown deliverables.
