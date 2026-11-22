# OHB2-WP01 — Stage 2 Cleanup Policy and Owner Decision Package

- **Task ID:** `OHB2-WP01-STAGE2-CLEANUP-POLICY-AND-OWNER-DECISION`
- **Date:** 2026-11-21
- **Repository:** `/workspace/project/OpenHandBot`
- **Status:** `DESIGN ONLY — NO IMPLEMENTATION AUTHORIZED`
- **Completion classification:** `COMPLETE_WITH_NOTES`
- **Baseline:** branch `main`, HEAD `0774c9cff923a2ed02da36a1111a283a61600ea5`, tree `faa7a3f03aa361698c6854281c162358bf38b84f`
- **Owner approval:** **NONE RECORDED.** No field in §19 is filled.
- **WP-01 status:** **NOT CLOSED.** This document does not change or close WP-01.

> **Read-only design evidence.** This package was prepared from the actual working tree. The Stage 1
> implementation is present in the tree but is **not committed**; the historical HEAD does not contain
> the `cancelled` state. No application code, test, database row, attachment file, or runtime state was
> modified. No commit, push, PR, merge, deployment, or Autopush activation was performed.

---

## 1. Executive recommendation

### 1.1 Recommended policy

**Recommend Option A — permanent retention — for the current policy decision.**

Keep `cancelled` batches, their `attachment_items` rows, their `attachment_message_identity` evidence,
and their staging files indefinitely. Do **not** add automatic cleanup, a retention timer, a new
worker, a new command, or any file/row deletion path in this stage.

The reason is not that cleanup is technically impossible. It is that the current evidence does not
support a safe automatic or destructive decision:

- `cancelled` is intentionally **non-terminal and non-reapable** in the actual code
  (`bot/attachments.py:1312-1323`; `bot/db.py:129-132`).
- There is **no durable `cancelled_at` timestamp**, no immutable cleanup marker, and no per-batch
  cleanup audit record. `attachment_batches.updated_at` is a general mutation timestamp, not a
  trustworthy retention clock (`bot/db.py:795-804`; cancellation writes it at
  `bot/db.py:1400-1405`).
- File deletion is **not atomic** with SQLite. The existing safe pattern is DB-first (`reaped` CAS,
  then unlink) and even that pattern deliberately refuses a `cancelled` parent
  (`bot/db.py:1705-1732`).
- The existing orphan-item path can delete bytes when a batch row is missing
  (`bot/attachments.py:1678-1734`). Deleting batch rows first would turn cancelled items into
  orphans and bypass the Stage 1 protection.
- `attachment_message_identity.batch_id` uses `ON DELETE RESTRICT`
  (`bot/db.py:822-839`), and message-identity evidence is protected by D-35. Batch-row deletion is
  therefore not a free operation.
- Deleting an `expired`/`rejected`/`delivered`/`failed` batch row would remove or alter a terminal
  routing blocker. OD-01 permits only an explicit clearance marker for `expired`/`rejected`; it does
  not permit file or row deletion (`docs/decisions/OHB2-WP01-OD01-OD03-OWNER-DECISION-RECORD.md`
  rules 1-12).

### 1.2 Conditional future direction (not approved now)

If the owner later decides that retained cancelled bytes are operationally unacceptable, the only
conservative next design is **Option C, a separate owner-confirmed, exact-batch, file-bytes-only
cleanup**, optionally with the retained-row properties of Option D. It must:

1. require an exact `batch_id` and explicit confirmation;
2. be owner-scoped under the existing single-owner architecture;
3. show a metadata-only preview before deletion;
4. revalidate ownership, state, retention condition, and references in a durable transaction;
5. delete only regular files inside the validated staging root;
6. retain batch rows, item rows, message-identity evidence, and clearance markers;
7. use a durable cleanup-intent marker and idempotent retry; and
8. never become automatic merely because a batch is old.

That future design is **not implemented or authorized** here. It requires a separate owner decision,
new tests, and likely new metadata or an audit table.

### 1.3 Explicit non-recommendations

- **Do not choose Option B now.** There is no trustworthy retention clock, no safe automatic
  selection rule, and no approved row-deletion policy.
- **Do not add `cancelled` to `AttachmentReaper._TERMINAL`.** It would contradict the Stage 1
  invariant, the explicit `_NON_REAPABLE` guard, and existing regression tests.
- **Do not delete `attachment_batches` or `attachment_message_identity` rows** as part of Stage 2.
  That changes routing/blocking and destroys evidence; it needs a separate decision.
- **Do not reuse `/attachments_clear` for cleanup.** It is a blocker-clearance operation, not a file
  deletion operation, and OD-01 rule 10 explicitly forbids attachment deletion through clearance.

---

## 2. Actual repository baseline

Observed on 2026-11-21 from `/workspace/project/OpenHandBot`:

| Item | Observed value |
|---|---|
| Branch | `main` |
| HEAD | `0774c9cff923a2ed02da36a1111a283a61600ea5` |
| HEAD tree | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| Index tree | `faa7a3f03aa361698c6854281c162358bf38b84f` (no staged changes) |
| Tracked modifications | **20** |
| Untracked files | **23** (before this package and its report) |
| Ignored state | `.openhands/`, `.pytest_cache/`, `__pycache__/` and similar caches |
| Stage 1 code | Present in the **working tree**, **not committed** |
| Stage 1 tests | `tests/test_wp01_stage1_cancellation.py` is untracked |
| Runtime data | No `attachment_staging` directory or `*.sqlite3` file was present in the repository tree |
| Git operations | No fetch, pull, branch switch, reset, clean, restore, stage, commit, or push was performed |

The pre-existing changes include Stage 1, poller/WP-08 work, docs, and tests. They were preserved
exactly. The actual `git status --short` is recorded in the accompanying report.

### 2.1 Stage 1 is not committed

`git grep HEAD -- bot tests docs` found **no** `ATTACHMENT_BATCH_CANCELLED` and **no**
`attachments_cancel`. The Stage 1 implementation is therefore an uncommitted working-tree change.
The supplied historical baseline is accurate as a Git baseline, but it is not the code that is
currently being audited.

### 2.2 Reported verification is not independently confirmed here

The supplied report says 3584 Python tests, 39 Stage 1 cases, 518 related cases, 280 Node tests,
pyflakes exit 0, Bandit High 0, and pip-audit clean. This design-only task did **not** rerun those
suites. They remain **reported, not independently verified** for this audit. The code inspection below
does independently confirm the relevant implementation shape and guards.

---

## 3. Stage 1 implementation status as observed in the current tree

### 3.1 Implemented behavior observed

| Behavior | Evidence in current tree |
|---|---|
| Durable `cancelled` batch status | `ATTACHMENT_BATCH_CANCELLED` at `bot/db.py:129-132`, included in `ATTACHMENT_BATCH_STATUSES` at `bot/db.py:133-143` |
| Only owned `pending` batches can be cancelled | `Database.cancel_pending_attachment_batch` selects by `batch_id` + `telegram_id`, checks `pending`, CAS-updates with both conditions (`bot/db.py:1358-1431`) |
| Explicit command with exact ID and `confirm` | `handlers.attachments_cancel` (`bot/handlers.py:3090-3133`); registered in `bot/app.py:118-120` and `BOT_COMMANDS` (`bot/app.py:56-58`) |
| Cancellation preserves files, batch rows, item rows, identity | No file/row deletion in `cancel_pending_attachment_batch`; tests assert counts and file existence (`tests/test_wp01_stage1_cancellation.py:133-160`) |
| Cancelled batches excluded from the reaper | `_NON_REAPABLE = {"cancelled"}` and early `_plan_batch` skip (`bot/attachments.py:1322-1323`, `1583-1593`); sweep explicitly counts them as skipped (`bot/attachments.py:1433-1441`) |
| Storage paths guarded against cancellation races | `StagingStore.cancellation_guard` waits for `_accept_lock` and `_sync_lock` (`bot/attachments.py:539-554`); `_store_prepare` rejects cancelled (`bot/attachments.py:709-714`); `try_mark_attachment_item_stored` requires parent `pending` (`bot/db.py:1249-1306`) |
| `_mark_expired` cannot overwrite cancelled | CAS `pending -> expired` (`bot/attachments.py:1543-1581`; `bot/db.py:1337-1356`) |
| `mark_attachment_item_reaped` protects cancelled parent | `NOT EXISTS (... b.status='cancelled')` (`bot/db.py:1705-1732`) |
| Stage 2 cleanup absent | No cleanup command, no retention timer, no `cancelled` reaper path, no attachment `DELETE` SQL |

### 3.2 What is not present

- No `cancelled_at`, `cleanup_at`, `cleaned_at`, or deletion-intent column.
- No cleanup audit table or per-batch cleanup marker.
- No owner-confirmed cleanup command.
- No automatic retention check for `cancelled`.
- No deletion of `attachment_batches`, `attachment_items`, or `attachment_message_identity` rows by
  any attachment code path.
- No production transition to `delivered`, `dispatching`, `uncertain`, `rejected`, or `failed` was
  found. Those constants exist, and the reaper treats some as terminal, but current production code
  only writes `pending`, `intent_recorded`, `expired`, and `cancelled`.

---

## 4. Complete attachment-data inventory

### 4.1 SQLite tables

Schema: `bot/db.py:788-841`; foreign-key enforcement: `bot/db.py:582-590`.

#### `attachment_batches`

| Column | Type / meaning |
|---|---|
| `batch_id` | TEXT PRIMARY KEY; opaque random ID (`new_batch_id`, `bot/attachments.py:388-390`) |
| `telegram_id` | INTEGER NOT NULL; owner |
| `conversation_id` | TEXT NOT NULL; explicit OpenHands conversation |
| `t0` | TEXT NOT NULL; absolute UTC timestamp of first file; never extended |
| `status` | TEXT NOT NULL DEFAULT `pending`; application-level status set |
| `created_at` | TEXT; creation timestamp |
| `updated_at` | TEXT; last mutation timestamp (not a dedicated cancellation/cleanup time) |
| `intent_text` | TEXT; accompanying prompt text when intent is recorded; normally NULL for a cancelled batch |

Index: `idx_attachment_batches_owner(telegram_id, conversation_id)`.

#### `attachment_items`

| Column | Type / meaning |
|---|---|
| `item_id` | TEXT PRIMARY KEY; opaque random ID |
| `batch_id` | TEXT NOT NULL; parent batch ID; **no foreign key** |
| `staging_token` | TEXT; opaque filename token; no unique constraint |
| `display_name` | TEXT; sanitized display metadata only |
| `size_bytes` | INTEGER; stored size |
| `status` | TEXT NOT NULL DEFAULT `pending`; `pending` / `stored` / `reaped` are used |
| `created_at` | TEXT |
| `updated_at` | TEXT |

Index: `idx_attachment_items_batch(batch_id)`.

#### `attachment_message_identity`

| Column | Type / meaning |
|---|---|
| `telegram_id`, `chat_id`, `message_id` | composite PRIMARY KEY; legal message identity |
| `batch_id` | TEXT NOT NULL; `FOREIGN KEY ... ON DELETE RESTRICT` |
| `conversation_id` | TEXT NOT NULL |
| `created_at` | TEXT NOT NULL |

Index: `idx_attachment_message_identity_batch(batch_id)`.

#### `settings`

Key/value table (`bot/db.py:685-688`). The only attachment-related key is
`attachment_terminal_clearance:<batch_id>`, whose value is the owner `telegram_id`
(`bot/db.py:162-169`, `1555-1636`). This is a **blocker-clearance marker**, not a file-cleanup
marker.

### 4.2 Files and directories

| Item | Location / rule |
|---|---|
| Staging root | Sibling directory of the SQLite database: `<db_parent>/attachment_staging` (`bot/attachments.py:213-218`, `STAGING_DIRNAME` at `117`) |
| Root creation | `ensure_staging_root` creates `0700`, rejects symlink/non-directory, enforces `0700` (`bot/attachments.py:251-287`) |
| File names | Opaque 32-hex tokens (`new_staging_token`, `bot/attachments.py:208-210`); no user filename is used as a path |
| File mode | `0600` (`bot/attachments.py:119`, `652-658`) |
| File contents | Downloaded attachment bytes only |
| Partial files | Removed on write failure via `_safe_unlink` (`bot/attachments.py:290-295`, `681-683`, `800-825`, `862`) |
| Orphan files | Files in the root with no matching item token are counted, not deleted (`bot/attachments.py:1736-1760`) |
| Untracked unsafe entries | Symlinks/non-regular entries are counted and left (`bot/attachments.py:1762-1801`) |

**Ignore-policy observation:** `.gitignore` ignores `.attachment_staging/` (with a leading dot), while
the code uses `attachment_staging` (no dot). `git check-ignore` confirmed `attachment_staging/...` is
**not ignored**. This is a pre-existing operational hazard if the database lives inside the repository:
runtime bytes could appear as untracked files. This package does not change `.gitignore`.

### 4.3 Related durable records

| Record | Attachment relation |
|---|---|
| `processed_updates` | Records update outcomes, including `durable_completed`, `explicitly_ignored`, `duplicate_completed`; retention is bounded (50,000 rows) and separate from attachment data (`docs/OPERATIONS_RUNBOOK.md:232-304`) |
| `update_failures` | Technical failure records; not attachment data |
| `outbox` | **No attachment rows are created.** Attachment intent is local only; tests assert this (`tests/test_repair_plan_02_life01_f2_race.py:371`) |
| `settings` clearance markers | Per-batch terminal blocker clearance; no file deletion |
| Mini App sessions / watched / notification tables | Not attachment storage; Mini App attachment endpoints are read-only |

---

## 5. Every identified file and database deletion path

### 5.1 File deletion paths

| # | Exact source and function | States it can process | Files/records affected | Trigger | Reversible? | Ownership/path checks | Race exposure |
|---|---|---|---|---|---|---|---|
| F1 | `StagingStore._write_to_path` exception path + `_safe_unlink` (`bot/attachments.py:652-684`, `290-295`) | New item being written; parent normally `pending` | Only the newly created partial file at `root/token`; no DB row deletion | Automatic on write failure | No | `_store_prepare` checked owner/batch; token validated; path was built from validated root; `O_EXCL`/`O_NOFOLLOW` | A concurrent reaper/cancel may also act on the same item; item remains `pending` if write fails |
| F2 | `StagingStore._store_finalize` `_safe_unlink` (`bot/attachments.py:793-829`) | Item cannot become `stored` (empty, denied magic, DB failure, CAS false) | Newly written file; item row remains | Automatic on rejection/race | No | Owner checked in prepare; path containment checked; finalize CAS requires parent `pending` | If reaper marks item `reaped` first, CAS fails and unlink is idempotent |
| F3 | `StagingStore._store_write` `_safe_unlink` on head-read failure (`bot/attachments.py:831-867`) | Item being written | Newly written file | Automatic on I/O failure | No | Same as F1/F2 | Same as F1/F2 |
| F4 | `AttachmentReaper._apply_cleanups` -> `_remove_file` (`bot/attachments.py:1498-1505`, `1803-1849`) | `delivered` / `expired` / `rejected` / `failed` batches with parseable `t0`; orphan items | Regular file at validated root/token; item status may be `reaped`; no batch/identity deletion | Automatic at startup and on existing Watcher tick via `OpportunisticSweeper` | No | Root `lstat`, symlink rejection, `_is_within`, regular-file check; **no owner check**; token only | Late storage writes; concurrent cancellation/expiry; duplicate sweeps; file replacement between checks |
| F5 | `AttachmentReaper._plan_orphan_items` + F4 (`bot/attachments.py:1678-1734`) | Items whose `batch_id` has no matching batch row; item status `pending`/`stored`/`reaped` | File and item status (`reaped`); no batch/identity deletion | Automatic at startup/tick | No | Token/path checks in F4; **no owner check**; **bypasses `cancelled` parent guard because parent is missing** | If a cancelled batch row is deleted, its items become orphans and can be deleted by this path |
| F6 | `AttachmentReaper._scan_root_untracked` (`bot/attachments.py:1736-1760`) | Any root entry | **Deletes nothing**; counts untracked | Automatic observation | N/A | Validated root; skips known tokens and unsafe entries | None (read-only) |
| F7 | `AttachmentReaper._count_unsafe_entries` (`bot/attachments.py:1762-1801`) | Any root entry | **Deletes nothing**; counts symlinks/non-regular | Automatic observation | N/A | `lstat` only | None (read-only) |
| F8 | Mini App download `resolve_staged_path` / `open_staged_file` (`bot/web/download.py:69-106`, `125-163`) | Only a `pending` batch's `stored` item, live TTL, owner/conversation authorized | **Deletes nothing**; opens read-only fd | Explicit HTTP request | N/A | Owner/conversation authorization; 32-hex token; root realpath; `lstat` regular-file; `O_NOFOLLOW`; size match | A cleanup unlink while a download fd is open is safe on POSIX (fd remains valid) but must not be claimed as cross-platform safe |
| F9 | `/attachments_clear` (`bot/handlers.py:3044-3087`; `bot/db.py:1572-1636`) | `expired` / `rejected` only | **Deletes no files or rows**; writes a `settings` marker | Explicit owner command | Marker is durable; can be ignored but not deleted by current code | Owner + exact batch + status | No file race; only routing blocker changes |

**No other production file deletion path was found.** Repository-wide search found only
`os.unlink` in `bot/attachments.py` (`_safe_unlink` and `_remove_file`) and `os.open` in
`bot/web/download.py` (read-only). There is no `shutil.rmtree`, no directory deletion, and no
attachment cleanup in the Mini App or `bot/files.py`.

### 5.2 Database deletion and mutation paths

| # | Exact source and function | Operation | Affected records | Trigger | Notes |
|---|---|---|---|---|---|
| D1 | `Database._init_schema` / `_migrate` (`bot/db.py:612-845`, `847-1110`) | `CREATE` / additive `ALTER` | No deletion | Startup | No attachment row deletion; `intent_text` is added non-destructively |
| D2 | `create_attachment_batch` (`bot/db.py:1113-1135`) | INSERT batch | Batch | Test/helper or new-batch path | Production new-batch path is D8 |
| D3 | `add_attachment_item` / `_insert_attachment_item_nocommit` (`bot/db.py:1156-1202`) | INSERT item | Item | Store prepare / new batch | No deletion |
| D4 | `set_attachment_item_status` (`bot/db.py:1212-1247`) | UPDATE item status | Item | **No production call found** (generic helper) | No batch guard; not a cleanup path, but a future hazard |
| D5 | `try_mark_attachment_item_stored` (`bot/db.py:1249-1306`) | CAS item `pending -> stored` | Item | Storage finalize | Requires parent `pending`; no deletion |
| D6 | `mark_attachment_batch_status` (`bot/db.py:1325-1335`) | Unconditional UPDATE batch status | Batch | Tests/future helper; not the current cancellation/expiry CAS path | No owner/status guard; must not be used for cleanup |
| D7 | `try_transition_attachment_batch_status` (`bot/db.py:1337-1356`) | CAS batch status | Batch | Expiry and cancellation | Used by `_mark_expired` and accept expiry |
| D8 | `cancel_pending_attachment_batch` (`bot/db.py:1358-1431`) | CAS `pending -> cancelled` + outcome | Batch + `processed_updates` | `/attachments_cancel` | No files/items/identity; preserves all |
| D9 | `clear_attachment_terminal_batch` (`bot/db.py:1572-1636`) | INSERT/UPDATE settings marker + outcome | `settings` + `processed_updates` | `/attachments_clear` | No attachment row/file deletion |
| D10 | `mark_attachment_item_reaped` (`bot/db.py:1705-1732`) | CAS item `pending`/`stored -> reaped` | Item | Reaper | Refuses a `cancelled` parent; no identity/batch deletion |
| D11 | `record_attachment_intent` (`bot/db.py:1836-1927`) | CAS `pending -> intent_recorded`, writes `intent_text`, INSERT identity, outcome | Batch + identity + `processed_updates` | Accompanying text | No deletion; identity INSERT is atomic with intent |
| D12 | `accept_attachment_item` (`bot/db.py:1998-2071`) | Conditional INSERT item + outcome | Item + `processed_updates` | Append file | Requires parent `pending` in the INSERT |
| D13 | `accept_attachment_item_into_new_batch` (`bot/db.py:2073-2123`) | INSERT batch + item + outcome | Batch + item + `processed_updates` | First file | No deletion |
| D14 | `prune_processed_updates` (`bot/db.py`, called from `bot/app.py:230-239`) | DELETE from `processed_updates` | Update log only | Startup | Not attachment data; bounded retention documented in the runbook |
| D15 | `run_startup_maintenance` (`bot/db.py`, called from `main.py:46-61`) | PRAGMA optimize / incremental vacuum / checkpoint | SQLite housekeeping | Startup | No attachment rows deleted; may reclaim free pages globally if enabled |

**No production `DELETE FROM attachment_batches`, `DELETE FROM attachment_items`, or
`DELETE FROM attachment_message_identity` exists.** A repository-wide search returned zero attachment
`DELETE` statements in `bot/`. The `attachment_message_identity` FK is `ON DELETE RESTRICT`, so a
batch row with identity evidence cannot be deleted without first deleting identity evidence.

### 5.3 Important indirect deletion risk

`_plan_orphan_items` deletes bytes for an item whose `batch_id` has no parent row. If any future
cleanup deletes a `cancelled` batch row before its items/files, the existing reaper would see those
items as orphans and could delete their files. That would silently bypass the Stage 1
`cancelled` protection. Any future design must either:

- never delete batch rows, or
- make the orphan path aware of durable cleanup intent and explicitly forbid deleting items that
  belonged to a retained `cancelled` batch.

The current code has no such marker.

---

## 6. Attachment state lifecycle

### 6.1 Batch transitions observed in production code

| From | To | Trigger | Code |
|---|---|---|---|
| none | `pending` | First accepted file | `accept_attachment_item_into_new_batch` (`bot/db.py:2073-2123`) |
| `pending` | `pending` | Additional file in the same batch | `accept_attachment_item` (`bot/db.py:1998-2071`) |
| `pending` | `intent_recorded` | Eligible accompanying text | `record_attachment_intent` (`bot/db.py:1836-1927`) |
| `pending` | `expired` | New file after an old pending batch expired | `AttachmentService.accept` (`bot/attachments.py:1115-1135`) |
| `pending` | `expired` | Reaper TTL check | `_mark_expired` (`bot/attachments.py:1543-1581`) |
| `pending` | `cancelled` | Explicit owner cancellation | `cancel_pending_attachment_batch` (`bot/db.py:1358-1431`) |
| `expired` / `rejected` | unchanged | Explicit terminal clearance marker | `clear_attachment_terminal_batch` (`bot/db.py:1572-1636`) |
| `delivered` / `dispatching` / `uncertain` / `rejected` / `failed` | no production transition found | Defined states / future Stage B | Constants `bot/db.py:121-143`; comments say Stage B not implemented (`bot/db.py:120`, `149-150`) |

### 6.2 Item transitions

| From | To | Trigger | Code |
|---|---|---|---|
| none | `pending` | Row-first acceptance | `_insert_attachment_item_nocommit` (`bot/db.py:1177-1202`); `accept_attachment_item*` |
| `pending` | `stored` | Complete write + CAS | `try_mark_attachment_item_stored` (`bot/db.py:1249-1306`) |
| `pending` / `stored` | `reaped` | Reaper decision after terminal/expiry | `mark_attachment_item_reaped` (`bot/db.py:1705-1732`) |
| any | any | Generic helper | `set_attachment_item_status` (`bot/db.py:1212-1247`); **no production call found** |

### 6.3 Routing effects

`classify_attachment_routing` (`bot/db.py:1742-1834`) order:

1. unknown/NULL status -> `AttachmentBatchIntegrityError` (fail closed);
2. `intent_recorded` / `dispatching` / `uncertain` -> `UNRESOLVED` (blocking);
3. multiple live `pending` -> `MULTI_LIVE`;
4. one live `pending` -> `LIVE`;
5. expired `pending` -> `EXPIRED_PENDING`;
6. terminal (`delivered` / `expired` / `rejected` / `failed`) -> `TERMINAL_ASSOCIATED` if identity
   proves the message, otherwise `TERMINAL_UNPROVEN`; only explicitly cleared `expired`/`rejected`
   may fall through;
7. otherwise, `cancelled` -> `CANCELLED`; else `NONE`.

`_handle_accompanying_text` treats `CANCELLED` as non-blocking (`bot/handlers.py:2839-2842`).
Therefore deleting a `cancelled` batch row does not usually change routing from `CANCELLED` to
`NONE`; however it removes the visible audit record. Deleting a terminal batch row **does** change
routing and can remove a blocker.

---

## 7. Cleanup alternatives A–D

### Option A — Permanent retention (recommended for this decision)

**Design:** keep every cancelled batch row, item row, identity record, and file indefinitely. No
automatic cleanup; no additional deletion path.

| Dimension | Assessment |
|---|---|
| Data-loss risk | **Lowest.** No attachment bytes or rows are deleted. |
| Recovery | **Best.** Full local copy remains available for inspection or a future explicit decision. |
| Operational complexity | Low code complexity; **high storage/ops risk** over time. |
| Required code/schema | **None.** |
| Test requirements | Keep existing Stage 1 invariants: cancelled excluded from reaper; files/rows/identity remain; no cleanup path. |
| Interaction with clearance | None; OD-01 clearance remains separate and unchanged. |
| New worker/reaper | No. |
| Architecture change | No. |
| Main disadvantage | Unbounded disk/database growth; cancelled files count toward the 64 MiB staging cap (`bot/attachments.py:633-649`, `304-326`), so enough cancelled batches can cause new acceptance to be rejected as quota. |

**Recommendation:** choose this now unless the owner explicitly accepts a destructive cleanup policy.

### Option B — Time-based automatic cleanup

**Design:** automatically delete cancelled files after a retention period.

Analysis:

- **Clock start:** there is no dedicated `cancelled_at`. The closest values are `t0` (first file,
  immutable but potentially much earlier than cancellation), `created_at`, and `updated_at` (last
  mutation). `updated_at` is written by cancellation (`bot/db.py:1400-1405`) but is not immutable and
  is not a dedicated cleanup clock. A correct design needs a new durable timestamp or marker.
- **Clock trust:** timestamps are wall-clock UTC strings; system clock changes can delay or accelerate
  eligibility. No monotonic durable clock exists.
- **Eligibility while referenced:** `staging_token` has no unique constraint, `attachment_items` has no
  FK to batches, and identity rows may reference the batch. Cleanup must verify that the token is not
  used by any non-eligible item and that identity evidence remains. No such check exists today.
- **Delayed workers/stale processes:** `store_async` can still be writing when a timer fires. Stage 1
  uses `cancellation_guard`; an automatic cleaner must use the same locks or a stronger serialization
  rule.
- **Partial deletion:** SQLite and filesystem are separate stores. A crash between unlink and status
  update can leave a `stored`/`pending` item with no file. The existing DB-first `reaped` pattern is
  the right shape, but `mark_attachment_item_reaped` explicitly refuses a `cancelled` parent.
- **Idempotence/recovery:** possible with a durable per-item cleanup state and retry; not possible
  safely with only a timer and no marker.
- **Row deletion:** automatic deletion of batch rows would remove routing blockers and break identity
  FK rules; not acceptable without a separate policy.
- **Architecture:** can run on the existing startup/tick hooks without a new worker, but changes the
  reaper’s policy and the Stage 1 non-reapable invariant. That is a material behavior change.

**Verdict:** **not recommended now.** It has no trustworthy retention clock and would require new
metadata, new eligibility rules, and explicit owner authorization.

### Option C — Explicit owner-confirmed cleanup

**Design:** a separate command or operator action names exactly one batch, shows a preview, requires
`confirm`, and deletes only approved files. Batch/items/identity remain unless separately approved.

| Dimension | Assessment |
|---|---|
| Data-loss risk | Controlled but irreversible for deleted bytes; preview and exact ID reduce mistakes. |
| Recovery | Rows/identity remain; deleted bytes are not recoverable. Partial deletion is recoverable by retry; missing files are idempotent success. |
| Operational complexity | Medium: new command/handler, DB validation, durable cleanup marker, file worker, audit, tests. |
| Required code/schema | Code changes; likely a durable cleanup marker (new column/table or settings key) and possibly an audit table. |
| Test requirements | Ownership, exact ID, eligibility, preview, confirm, duplicate requests, symlink/path traversal, missing files, partial failure, crash/restart, no race with storage, identity retained. |
| Interaction with clearance | Must remain separate from `/attachments_clear`; cleanup must not clear a terminal blocker. |
| New worker/reaper | No new worker; file I/O can use the existing `to_thread` pattern. Do not add `cancelled` to the automatic reaper. |
| Architecture change | Compatible with one bot + ASGI + one SQLite owner if implemented as an owner-scoped command; new command is a product/interface change, not a new process. |

**Verdict:** the only acceptable future destructive path, and only after explicit owner approval and
metadata/audit design.

### Option D — Hybrid retention

**Design:** retain all batch/item/identity rows and audit metadata, but delete eligible file bytes
after a defined condition.

| Dimension | Assessment |
|---|---|
| Data-loss risk | Bytes lost; metadata/audit retained. |
| Recovery | Rows and identity remain; files not recoverable; missing-file handling must be truthful. |
| Operational complexity | Medium-high: item cleanup state, batch cleanup marker, audit, retention rule. |
| Required code/schema | New item state (`cleaned`/`cancelled_reaped`) or a durable cleanup marker/audit table; cannot safely reuse `reaped` without changing its Stage 1 parent guard and tests. |
| Test requirements | Same as C plus row-retention and audit tests. |
| Interaction with clearance | Keep separate; no implicit clearance. |
| New worker/reaper | No new worker; could be explicit or tick-driven. Automatic tick-driven eligibility is still an automatic cleanup and needs explicit approval. |
| Architecture change | Compatible in process shape; schema/status semantics change is material and needs approval. |

**Verdict:** a reasonable future variant of C if the owner wants auditability, but it requires a
separate schema/metadata decision. Not recommended as the immediate action.

### Option comparison summary

| Criterion | A permanent | B time-based auto | C explicit | D hybrid |
|---|---|---|---|---|
| Deletes files | No | Yes | Yes, explicit only | Yes, explicit or policy |
| Deletes rows | No | Maybe (unsafe) | No by default | No (retain) |
| Deletes identity | No | No | No | No |
| New schema | No | Likely yes | Likely yes (marker/audit) | Yes (state/audit) |
| New worker | No | No (existing tick) | No | No |
| Architecture change | No | Reaper policy change | New command only | Schema/status change |
| Data-loss risk | Lowest | High if unproven | Controlled | Controlled but irreversible |
| Recommended now | **Yes** | **No** | **Future only** | **Future only** |

---

## 8. State eligibility matrix

Legend: **Protected** = no cleanup under this policy; **Existing** = existing reaper behavior;
**Future explicit** = only after a new owner decision; **N/A** = no production transition observed.

| State | Current production writer? | Existing reaper behavior | Routing effect | Stage 2 file bytes | Item rows | Batch row | Identity | Clearance |
|---|---|---|---|---|---|---|---|---|
| `pending` | Yes (new/append) | Live pending untouched; expired pending marked `expired` then cleaned | `LIVE`/`MULTI_LIVE`/`EXPIRED_PENDING` | **Protected while live**; existing expiry path after TTL | Protected | Protected | Protected | Not applicable |
| `cancelled` | Yes (`/attachments_cancel`) | Explicitly skipped; `_NON_REAPABLE`; item CAS refuses parent | `CANCELLED` (non-blocking) | **Protected now**; future explicit C only | **Protected** | **Protected** | **Protected** | **Not eligible** for OD-01 clearance |
| `expired` | Yes (TTL/accept) | Terminal; files eligible for existing reaper | `TERMINAL_*` / `EXPIRED_PENDING` until transition | **Existing** reaper (not Stage 2) | `reaped` by existing reaper | **Retain** | **Retain** | Explicit clearance allowed |
| `rejected` | No production writer found | Terminal; files eligible if state is written | `TERMINAL_*` | **Existing** reaper if present | `reaped` by existing reaper | **Retain** | **Retain** | Explicit clearance allowed |
| `delivered` | No production writer found | Terminal; files eligible | `TERMINAL_ASSOCIATED`/`TERMINAL_UNPROVEN` | **Existing** reaper if present | `reaped` by existing reaper | **Retain** | **Retain** | **Never clearable** |
| `failed` | No production writer found | Terminal; files eligible | `TERMINAL_*` | **Existing** reaper if present | `reaped` by existing reaper | **Retain** | **Retain** | **Never clearable** |
| `intent_recorded` | Yes (accompanying text) | Unresolved; skipped; no cleanup | `UNRESOLVED` (blocking) | **Protected** | Protected | Protected | Protected | Not applicable |
| `dispatching` | No production writer found (future Stage B) | Unresolved; skipped | `UNRESOLVED` | **Protected** | Protected | Protected | Protected | Not applicable |
| `uncertain` | No production writer found (future Stage B) | Unresolved; skipped | `UNRESOLVED` | **Protected** | Protected | Protected | Protected | Not applicable |
| Unknown / NULL / malformed | Corruption/future value | Reported; no cleanup | `AttachmentBatchIntegrityError` | **Protected** | Protected | Protected | Protected | Not applicable |
| Orphan item (no parent batch) | Corruption/manual/batch deletion | Existing orphan path marks `reaped` and deletes | No batch routing | **Existing orphan path**; do not create this state | `reaped` | Missing | If identity exists, FK would have prevented batch deletion | Not applicable |

### 8.1 Separate permissions (must not be conflated)

| Operation | Current permission | Recommendation |
|---|---|---|
| 1. Clear a terminal routing blocker | Explicit `/attachments_clear` for `expired`/`rejected` only (`bot/db.py:162-166`, `1572-1636`) | Keep unchanged; do not extend to `cancelled` |
| 2. Delete attachment file bytes | Existing reaper for terminal/expired; store failure cleanup for new partial files | Do not extend to `cancelled` without a separate decision |
| 3. Delete `attachment_items` rows | **No permission; no code path** | Keep protected; do not delete in Stage 2 |
| 4. Delete `attachment_batches` rows | **No permission; no code path** | Keep protected; row deletion would alter routing/blocking and audit |
| 5. Delete `attachment_message_identity` rows | **No permission; no code path; FK RESTRICT; D-35** | Keep protected permanently unless a separate explicit decision says otherwise |
| 6. Remove metadata/audit evidence | **No permission** | Keep protected; a future cleanup must add audit, not remove it |

### 8.2 Conservative eligibility conclusion

Only **file bytes** of a `cancelled` batch could ever become eligible under a future explicit policy.
Even then, the safest rule is:

- batch status exactly `cancelled`;
- exact owner and exact batch ID;
- explicit confirmation and a preview;
- retention condition satisfied by a dedicated durable timestamp/marker;
- no identity evidence, no live item, no shared token reference, no active storage;
- delete only regular files inside the validated staging root;
- retain batch/item/identity/clearance rows.

`pending`, `intent_recorded`, `dispatching`, `uncertain`, unknown, and malformed states must remain
permanently protected. `expired`/`rejected`/`delivered`/`failed` already have existing reaper and
clearance semantics; Stage 2 must not broaden them or delete their rows.

---

## 9. File deletion safety analysis

| Concern | Current evidence | Required future rule |
|---|---|---|
| Symlink rejection | `_remove_file` uses `lstat` on root and path, rejects `S_ISLNK`/non-regular (`bot/attachments.py:1817-1841`); `resolve_staged_path` and `open_staged_file` reject symlinks (`bot/web/download.py:94-105`, `134-163`); `ensure_staging_root` rejects a symlink root (`bot/attachments.py:261-267`) | Keep all three checks; never use `realpath`-following deletion |
| Path traversal | `is_safe_workspace_path` rejects absolute/backslash/control/`.`/`..` (`bot/files.py:75-94`); `_is_within` uses realpath containment (`bot/attachments.py:298-301`); download requires 32-hex token (`bot/web/download.py:31-33`, `90-93`) | Validate token as a single safe component and re-check containment immediately before unlink |
| Staging-root containment | `staging_root_for` is db-parent/attachment_staging (`bot/attachments.py:213-218`); `_validated_root` rejects missing/symlink/non-directory (`bot/attachments.py:1781-1791`) | Never delete the root or a directory; only regular files directly inside it |
| File identity/ownership | Current `_remove_file` deletes by token only; no owner check, no inode/hash, no unique token constraint (`bot/attachments.py:1803-1849`; schema `bot/db.py:810-819`) | Owner-scoped batch lookup plus token reference check; optionally inode/size verification; reject shared tokens |
| Missing file | `_remove_file` returns `absent` as idempotent success (`bot/attachments.py:1832-1835`); `_safe_unlink` ignores `OSError` (`bot/attachments.py:290-295`) | Treat absent as success but record it truthfully |
| Already deleted | Same `absent` path; repeated sweeps are idempotent (`tests/test_attachment_cleanup_expiration_a4.py:190-204`) | Keep idempotent; do not recreate rows/files |
| Permission error | `_remove_file` returns `retry` on `OSError` (`bot/attachments.py:1842-1848`) | Retry with bounded reporting; never claim success |
| Partial deletion | `_finish_batch` returns `PARTIAL`/`RETRY` (`bot/attachments.py:1654-1676`) | Keep per-item results; do not delete batch row after partial failure |
| Disk I/O error | `_write_to_path` cleans partial file and propagates; `_remove_file` retries | Same fail-closed behavior; no success reply |
| SQLite error | Reaper marks errors and retries; `_mark_expired` CAS failure re-reads state (`bot/attachments.py:1543-1581`) | Cleanup must commit durable intent before unlink; DB failure means no deletion |
| Process termination | Existing DB-first `reaped` state allows retry after crash; tests cover crash recovery (`tests/test_repair_plan_02_life02_crash_recovery.py:264-330`) | Cleanup must use a durable per-item intent/marker; never delete first and mark later |
| Concurrent storage | Stage 1 `cancellation_guard` waits for storage locks (`bot/attachments.py:539-554`); reaper CAS prevents revival | Cleanup must acquire the same guard or prove the batch cannot accept writes |
| Concurrent delivery | No production delivery transition found; Mini App download is read-only and only for `pending` | Do not delete a file with an open download fd without defining POSIX-only semantics; cancelled is not downloadable |
| Concurrent cancellation/expiry | Cancellation CAS and expiry CAS are mutually exclusive (`bot/db.py:1337-1356`, `1358-1431`); `_plan_batch` skips cancelled | Cleanup must re-check state in the same transaction and never overwrite `cancelled`/`expired` |
| Duplicate cleanup | Existing `reaped`/absent is idempotent; command dedupe uses `update_id` | Use exact batch + idempotency key; duplicate request must not re-delete or change rows |
| Retry broadening | `_plan_batch` only selects `_TERMINAL`; `_NON_REAPABLE` guard; orphan path only when parent absent | A cleanup retry must not make other batches eligible or delete orphaned cancelled data |
| SQLite/filesystem atomicity | No atomicity is claimed; module contract and reaper use DB-first + retry (`bot/attachments.py:1-70`, `1297-1309`) | Never claim atomic deletion; use durable intent + idempotent retry |
| Recovery after partial completion | Existing reaper retries `reaped` items and treats missing as success | Add a cleanup report/audit and retain batch/identity rows for reconciliation |

---

## 10. Database record retention analysis

### 10.1 Batch rows

- `attachment_batches` holds lifecycle state, owner, conversation, `t0`, timestamps, and
  `intent_text`.
- Deleting a batch row would remove the visible `/attachments` record and can change routing:
  - `cancelled` row deletion usually changes `CANCELLED` to `NONE` (non-blocking), but loses audit;
  - `expired`/`rejected` row deletion could remove a blocker that OD-01 requires to be cleared only
    explicitly;
  - `delivered`/`failed` row deletion would remove a permanent blocker.
- `attachment_message_identity` uses `ON DELETE RESTRICT`, so a batch with identity evidence cannot be
  deleted without deleting identity first.
- Deleting a batch row would orphan its `attachment_items`; the existing orphan reaper would then
  delete their files (`bot/attachments.py:1678-1734`).

**Recommendation:** retain batch rows indefinitely unless a separate owner decision explicitly
authorizes a row-deletion policy and the resulting routing/audit change.

### 10.2 Item rows

- Item rows are the only durable per-file metadata (token, display name, size, status).
- Deleting them would destroy audit evidence and make a retained file untracked.
- `attachment_items` has no FK to `attachment_batches`; deletion does not cascade.
- `staging_token` is not unique, so an item row is also the only reference check available.

**Recommendation:** retain item rows indefinitely; a future cleanup may change item status to a
durable `cleaned`/`reaped` value but must not delete the row.

### 10.3 Message identity

- `attachment_message_identity` is independent evidence (D-35); it is created atomically with intent
  (`bot/db.py:1902-1919`) and is never deleted by attachment code.
- It has `ON DELETE RESTRICT` (`bot/db.py:829-839`), and `PRAGMA foreign_keys=ON` is enforced
  (`bot/db.py:582-590`).
- Deleting identity would change routing from `TERMINAL_ASSOCIATED` to `TERMINAL_UNPROVEN`/fallback
  and would destroy evidence.

**Recommendation:** never delete identity in Stage 2. Retain it permanently unless a separate,
explicit evidence-retention decision says otherwise.

### 10.4 Clearance markers and audit metadata

- `settings` clearance markers are keyed by batch ID. If a batch row is deleted, the marker becomes
  stale and could collide with a reused ID (IDs are random, but no invariant prevents reuse).
- There is no cleanup audit table. `processed_updates` has bounded retention (50,000) and is not a
  durable per-file audit.
- If the owner wants durable cleanup audit, a new table or a durable settings record with structured
  values is required. That is a schema/metadata change and needs separate approval.

---

## 11. Recovery and partial-failure strategy

### 11.1 Recommended shape if cleanup is ever approved

1. **Preview (read-only):** owner and batch ID; batch status; item count; total bytes; missing files;
   unsafe entries; whether identity exists; whether a token is referenced by another item. No paths
   or contents are shown.
2. **Confirm:** exact `batch_id` + explicit confirmation token.
3. **Durable validation:** `BEGIN IMMEDIATE`; re-check owner, status, retention marker, references,
   and no active storage; write a durable cleanup-intent marker (per item or per batch); commit.
4. **Delete:** in a worker thread, unlink only regular files inside the validated root; record
   `deleted`/`absent`/`retry`/`unsafe` per item.
5. **Finalize:** update item statuses/marker only after durable results; never delete batch/identity.
6. **Retry:** a repeated request or restart retries only items with durable cleanup intent; absent
   files are success; unsafe/foreign paths are left and reported.
7. **Audit:** durable outcome with batch ID, item count, bytes, result classes, timestamps, and owner
   (no file paths/content). No success reply before the durable marker/outcome.

### 11.2 Failure matrix

| Failure | Safe behavior |
|---|---|
| DB failure before intent | No deletion; report failure |
| Crash after intent before unlink | Retry unlinks; item remains in cleanup state |
| Crash after unlink before result update | Retry sees absent and records success |
| Partial multi-item deletion | Retry only remaining items; batch remains retained |
| Permission/disk error | Mark retry; no success claim |
| Missing root/file | Treat absent as idempotent success; record it |
| Symlink/foreign path | Leave untouched; report unsafe |
| Concurrent storage | Guard rejects or waits; never delete an active write |
| Concurrent cancellation/expiry | State re-check/CAS; never overwrite the other transition |
| Duplicate request | Idempotent marker/update outcome; no second deletion |
| Clock change | Do not rely on wall clock without a dedicated policy; a changed clock must not silently broaden eligibility |

### 11.3 What must not be claimed

- SQLite transactions do **not** make filesystem deletion atomic.
- A successful `unlink` does not prove the row update succeeded.
- A missing file is not proof that a row is safe to delete.
- A `reaped` item status is not a batch-level cleanup audit.

---

## 12. Reaper integration analysis

### 12.1 Current reaper behavior

- `AttachmentReaper._TERMINAL = {delivered, expired, rejected, failed}` (`bot/attachments.py:1312-1321`).
- `_NON_REAPABLE = {cancelled}` (`bot/attachments.py:1322-1323`).
- `_sweep_db_phase` explicitly counts cancelled as skipped (`bot/attachments.py:1433-1441`).
- `_plan_batch` returns `SKIPPED` with `reason="cancelled_non_reapable"` before any item/t0 logic
  (`bot/attachments.py:1583-1593`).
- `_mark_expired` uses CAS `pending -> expired`, so it cannot overwrite cancelled
  (`bot/attachments.py:1543-1581`).
- `mark_attachment_item_reaped` refuses an item whose parent is cancelled
  (`bot/db.py:1705-1732`).
- `_remove_file` is the only actual unlink primitive for persisted batches; it is path-contained and
  symlink-safe but owner-blind (`bot/attachments.py:1803-1849`).
- The reaper is called from the existing startup hook (`bot/app.py:247-261`) and the existing
  `Watcher.tick` via `OpportunisticSweeper` (`bot/watcher.py:177-183`; `bot/attachments.py:1863-2002`).
  There is no new worker or scheduler.

### 12.2 Integration conclusions by option

| Option | Reaper change | New worker | Assessment |
|---|---|---|---|
| A permanent | None | No | Best fit; current code already does this |
| B automatic | Add cancelled eligibility/cleanup phase; change `_NON_REAPABLE`/`mark_attachment_item_reaped` guard; add retention clock | No (existing tick) | Material policy change; not recommended now |
| C explicit | Reuse `_remove_file` as a primitive; do not add cancelled to `_TERMINAL`; add explicit DB marker/command | No | Compatible if implemented separately |
| D hybrid | Add durable item cleanup state/audit; maybe tick/explicit | No | Requires schema/status decision |

### 12.3 Orphan-path warning

The existing orphan path is the main hidden deletion route. A future cleanup that deletes a batch row
must not be allowed to turn retained cancelled items into orphans. The safe rule is to **never delete
batch rows** as part of file cleanup.

---

## 13. Architectural compatibility

| Constraint | Evidence | Option A | Option C | Option B/D |
|---|---|---|---|---|
| One bot + ASGI process | `main.py:23-69`; Mini App task is inside the same process (`bot/app.py:353-394`) | Compatible | Compatible (new command only) | Compatible in process shape |
| One authoritative SQLite owner | `Database.__init__` one connection (`bot/db.py:574-590`); reaper uses same connection (`tests/test_attachment_cleanup_expiration_a4.py:652-660`) | Compatible | Compatible | Compatible if no new DB owner |
| Existing outbox/workers only | Attachment intake does not create outbox rows; reaper uses startup/tick; no attachment worker (`bot/app.py:247-261`, `bot/watcher.py:177-183`) | Compatible | Compatible if no new worker; file I/O via `to_thread` | Compatible if existing tick only |
| No additional database | One SQLite file (`bot/config.py:19`, `241`) | Compatible | Compatible | Compatible |
| No new independent worker/queue | Existing `Watcher` only (`bot/watcher.py:150`, `177-183`) | Compatible | Compatible | Compatible only if existing tick |
| No exactly-once Telegram claim | Runbook documents bounded dedupe, not exactly-once (`docs/OPERATIONS_RUNBOOK.md:228-304`) | Compatible | Compatible; command retry must be idempotent | Compatible |
| Autopush disabled/inactive | No Autopush path in attachment code; task forbids activation | Compatible | Compatible | Compatible |
| No Mini App change | Task forbids `bot/web`/`docs/MINI_APP.md` changes; download is read-only (`bot/web/services.py:758-870`) | Compatible | Compatible | Compatible |

**Any proposal that adds an independent scheduler, a second database, an admin CLI process, or
deletes batch/identity rows is an architectural change and requires separate owner approval.**

---

## 14. Required schema or metadata changes, if any

| Option | Schema/metadata need | Current state |
|---|---|---|
| A permanent | None | Current schema is sufficient |
| B automatic | Dedicated immutable `cancelled_at`/retention marker; durable per-item cleanup state; audit record; possibly unique token constraint | **Not present** |
| C explicit | Durable cleanup-intent marker; ideally an audit table; optional unique-token/reference check | **Not present**; code-only command is not enough for durable audit |
| D hybrid | New item cleanup state or batch cleanup marker plus audit table; cannot reuse `reaped` without changing its Stage 1 semantics/guard | **Not present** |

No schema or metadata change is made by this task. Any future change requires a separate owner
decision, a migration plan, backup/rollback analysis, and tests.

---

## 15. Required regression and fault-injection tests for a future implementation

The following criteria are **not implemented**; they are acceptance criteria for a future authorized
task.

1. Ineligible states (`pending`, `intent_recorded`, `dispatching`, `uncertain`, unknown, malformed,
   `expired`, `rejected`, `delivered`, `failed`) cannot enter cancelled cleanup.
2. Exact batch ID and exact owner are required; another owner's batch is invisible and unchanged.
3. No cleanup occurs before the approved retention condition; clock/backdating cases are covered.
4. Duplicate cleanup requests are idempotent and do not double-delete or change outcomes.
5. Partial deletion is recoverable: DB-first intent, crash before/after unlink, restart retry.
6. Missing/already-deleted files are handled truthfully and idempotently.
7. Symlinks and foreign paths are never deleted.
8. Files outside the staging root are never touched.
9. Batch/item/identity rows remain consistent with the approved retention policy.
10. Message identity records are retained unless an explicit approved deletion rule exists.
11. Cleanup cannot race with active storage or delivery; storage wins or cleanup fails closed.
12. Cancellation and cleanup cannot overwrite each other's durable states (CAS/re-check).
13. Reaper retries cannot broaden eligibility or select `cancelled` accidentally.
14. No hidden/implicit cleanup path exists (source-level guard against `DELETE FROM attachment_*`).
15. Every cleanup action has a durable, auditable outcome with no file paths/content in logs.
16. Quota interaction is tested: cancelled bytes count toward the global cap until explicitly cleaned.
17. Shared `staging_token`/orphan-parent cases are rejected or handled without deleting live data.
18. Process termination at every step leaves a recoverable state; no false success reply.

---

## 16. Operational observability and audit requirements

### 16.1 Current observability

- `SweepReport` exposes `scanned`, `cleaned`, `partial`, `retry`, `skipped`, `errors`,
  `files_deleted`, `orphans_left`, `unsafe_left`, `untracked_left` (`bot/attachments.py:1281-1294`).
- `_log_report` logs counts only, no paths/content (`bot/attachments.py:1851-1860`).
- `_mark_expired` logs batch IDs on CAS failure (`bot/attachments.py:1561-1575`).
- `OpportunisticSweeper` distinguishes success from errors and throttles retries
  (`bot/attachments.py:1919-2002`).
- `/attachments` shows batch ID, status, conversation (`bot/handlers.py:3019-3041`).
- `processed_updates` records update outcomes; bounded retention.
- There is **no** cleanup audit record and **no** per-file deletion outcome table.

### 16.2 Future requirements

- A durable cleanup record per batch: owner, batch ID, approved policy/retention condition, item
  count, bytes, deleted/absent/retry/unsafe counts, start/end timestamps, result, and operator/command
  source.
- No file paths, staging tokens, file contents, prompt text, or secrets in logs or audit.
- Explicit failure reporting; never a success reply before durable commit.
- A way to reconcile batch rows/items against the filesystem after a crash.
- No automatic cleanup log line that implies success when only some items were deleted.

---

## 17. Risks and unresolved technical questions

### 17.1 Material risks

| ID | Risk | Evidence | Severity |
|---|---|---|---|
| R1 | No unique `staging_token`; a token shared by two items could be deleted for one batch while another still references it | Schema `bot/db.py:810-819`; `_remove_file` token-only `bot/attachments.py:1803-1849` | High for future cleanup |
| R2 | Orphan-item path bypasses cancelled parent protection if a batch row is missing/deleted | `bot/attachments.py:1678-1734`; `mark_attachment_item_reaped` only protects existing parent | High |
| R3 | No dedicated `cancelled_at`/retention timestamp; `updated_at` is mutable | `bot/db.py:795-804`; `1400-1405` | High for time-based cleanup |
| R4 | No file identity/hash/inode check; regular-file replacement at the same token is not detected by `_remove_file` | `bot/attachments.py:1803-1849` | Medium/High |
| R5 | Reaper `_remove_file` has no owner check; it trusts the token from the DB | `bot/attachments.py:1803-1849` | Medium |
| R6 | No durable per-file cleanup audit | No cleanup table; `processed_updates` bounded | Medium/High |
| R7 | Cancelled files count toward the 64 MiB global cap; repeated cancellations can exhaust acceptance capacity | `bot/attachments.py:304-326`, `633-649`; production store `bot/handlers.py:2379-2384` | Medium |
| R8 | `.gitignore` ignores `.attachment_staging/` but code uses `attachment_staging`; runtime bytes may be untracked | `.gitignore:17`; `bot/attachments.py:117`; `git check-ignore` | Medium operational |
| R9 | Stage 1 is uncommitted; reported test results were not independently rerun here | `git status`; HEAD grep; no test run in this task | Medium |
| R10 | `delivered`/`dispatching`/`uncertain`/`rejected`/`failed` have no production writer; their cleanup behavior is theoretical until Stage B | `bot/db.py:120`, `149-150`; no transition calls found | Medium |
| R11 | Batch-row deletion would change routing/blocking and can orphan items; identity FK RESTRICT | `bot/db.py:822-839`; routing `1742-1834`; orphan path `1678-1734` | High |
| R12 | Wall-clock changes can accelerate/delay time-based eligibility | ISO timestamps from `datetime.now(timezone.utc)`; no monotonic durable clock | High for Option B |
| R13 | Generic `mark_attachment_batch_status` is unconditional and `set_attachment_item_status` has no batch guard | `bot/db.py:1325-1335`, `1212-1247` | Medium (future misuse) |
| R14 | Mini App download holds an open fd; unlink behavior is POSIX-safe but not a cross-platform guarantee | `bot/web/download.py:125-223` | Low/Medium |
| R15 | `settings` clearance markers become stale if a batch row is ever deleted | `bot/db.py:162-169`, `1555-1636` | Medium for future row deletion |
| R16 | `intent_text` may contain sensitive prompt content; normally NULL for cancelled but schema permits it | `bot/db.py:526-527`, `795-804` | Medium privacy/audit |
| R17 | No `VACUUM`/row reclamation policy; deleting rows would not immediately shrink the DB | SQLite behavior; no attachment deletion code | Low/Medium |
| R18 | No exactly-once semantics for cleanup commands or Telegram replies | Runbook `228-304`; Stage 1 command pattern | Medium |
| R19 | Disk-full/permission errors can leave partial cleanup; existing reaper retries but no cleanup audit | `bot/attachments.py:1654-1676`, `1842-1848` | Medium |
| R20 | Unknown/malformed statuses must fail closed; a future cleanup selector must not treat them as eligible | `bot/db.py:1638-1651`, `1742-1834`; reaper `1407-1420` | Medium |

### 17.2 Unresolved owner questions

1. Is permanent retention acceptable, or is disk growth a blocking operational problem?
2. If cleanup is desired, what exact retention condition and clock source are approved?
3. Should cleanup be explicit only, or automatic after a retention period?
4. May file bytes be deleted while batch/item/identity rows remain?
5. May any database rows ever be deleted? If yes, which and under what routing/audit rules?
6. May message-identity evidence ever be deleted? D-35 currently says no.
7. What audit retention is required, and where should it live?
8. Should cancelled bytes count toward the global staging quota, or should they be excluded?
9. Is the Telegram owner command the correct mechanism, or is an offline operator procedure preferred?
10. What happens on a clock jump, disk-full, or partial cleanup?
11. Should a future cleanup be visible in `/attachments` and the Mini App, or stay bot-only?
12. Should the current `.gitignore` staging-name mismatch be fixed separately?

---

## 18. Recommended policy

### 18.1 Decision recommendation

**Adopt Option A now:**

- retain all `cancelled` batch rows, item rows, identity records, and files indefinitely;
- keep `cancelled` non-terminal and non-reapable;
- keep the existing terminal/expired reaper unchanged;
- do not add automatic cleanup, retention timers, new workers, or cleanup commands;
- document the storage/quota consequence and the need for a future owner decision.

### 18.2 If cleanup later becomes necessary

The only acceptable next design is **Option C** (optionally with D’s retained-row audit properties):

- exact batch ID, exact owner, explicit `confirm`;
- metadata-only preview;
- dedicated durable retention/cleanup marker;
- DB-first, idempotent, retryable file-only deletion;
- retain batch, item, identity, and clearance records;
- no automatic eligibility merely because a batch is old;
- no row or identity deletion without a separate decision.

### 18.3 Explicitly rejected now

- Option B automatic cleanup.
- Adding `cancelled` to `_TERMINAL`.
- Reusing `/attachments_clear` for file deletion.
- Deleting batch rows, item rows, or identity records.
- Adding a new worker, queue, scheduler, database, or admin process.
- Any change to OD-01/OD-03, the Mini App, outbox, dependencies, CI, or concurrency policy.

---

## 19. Explicit owner decision fields

> **NONE OF THESE FIELDS IS FILLED.** They are for the owner only. This package does not record
> approval on the owner's behalf.

| ID | Decision | Options | Owner selection | Owner signature/date |
|---|---|---|---|---|
| OD-S2-01 | Retention policy | A permanent / B time-based / C explicit / D hybrid | **[ ] NOT FILLED** | **[ ] NOT FILLED** |
| OD-S2-02 | Authorize automatic cleanup | YES / NO; if YES, retention condition: ______ | **[ ] NOT FILLED** | **[ ] NOT FILLED** |
| OD-S2-03 | Authorize explicit cleanup | YES / NO; command/operator mechanism: ______ | **[ ] NOT FILLED** | **[ ] NOT FILLED** |
| OD-S2-04 | Authorize deletion of file bytes | YES / NO; eligible states: ______ | **[ ] NOT FILLED** | **[ ] NOT FILLED** |
| OD-S2-05 | Authorize deletion of `attachment_items` rows | YES / NO; if YES, scope: ______ | **[ ] NOT FILLED** | **[ ] NOT FILLED** |
| OD-S2-06 | Authorize deletion of `attachment_batches` rows | YES / NO; if YES, routing/audit impact accepted: ______ | **[ ] NOT FILLED** | **[ ] NOT FILLED** |
| OD-S2-07 | Authorize deletion of `attachment_message_identity` rows | YES / NO; D-35 impact accepted: ______ | **[ ] NOT FILLED** | **[ ] NOT FILLED** |
| OD-S2-08 | Authorize schema/architecture changes | YES / NO; scope: ______ | **[ ] NOT FILLED** | **[ ] NOT FILLED** |
| OD-S2-09 | Retention clock/source | `t0` / `updated_at` / new `cancelled_at` / other: ______ | **[ ] NOT FILLED** | **[ ] NOT FILLED** |
| OD-S2-10 | Audit retention and location | settings / new table / external log / other: ______ | **[ ] NOT FILLED** | **[ ] NOT FILLED** |
| OD-S2-11 | Quota treatment of cancelled bytes | count / exclude / other: ______ | **[ ] NOT FILLED** | **[ ] NOT FILLED** |
| OD-S2-12 | Approval to start a future implementation task | YES / NO; task ID: ______ | **[ ] NOT FILLED** | **[ ] NOT FILLED** |

**No approval is implied by this package. WP-01 remains open.**
