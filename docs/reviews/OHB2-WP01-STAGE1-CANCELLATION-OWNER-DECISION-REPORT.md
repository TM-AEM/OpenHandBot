# OHB2-WP01-STAGE1-CANCELLATION-OWNER-DECISION-REPORT

- **Task ID:** `OHB2-WP01-STAGE1-CANCELLATION-OWNER-DECISION-PACKAGE`
- **Date:** 2026-11-22
- **Status:** `COMPLETE_WITH_NOTES`
- **Mode:** read-only inspection plus creation of the decision package and this report.
- **Implementation:** **NOT AUTHORIZED. NOT IMPLEMENTED.**
- **Recommendation:** Stage 1 design is sound **with two mandatory code-safety corrections**; approve
  design only if those corrections are accepted, authorize implementation separately, defer Stage 2.
- **Owner approval:** **NONE RECORDED. WP-01 IS NOT CLOSED.**

---

## 1. Actual baseline and Git state

| Item | Verified value |
|---|---|
| Working directory | `/workspace/project/OpenHandBot` |
| Branch | `main` |
| HEAD | `0774c9cff923a2ed02da36a1111a283a61600ea5` |
| HEAD tree | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| Index | Empty; no staged entries |
| Working tree | Pre-existing WP-01/poller/WP-08 changes preserved |
| Untracked | Pre-existing reports, decision records, design docs, and `tests/test_wp01_attachment_lifecycle.py` preserved |
| Ignored | `.pytest_cache`, `__pycache__`, `.openhands/memory` preserved |
| Design SHA-256 | `5436c2b1539eee7843b03c21137cc4926eac7a92c39a32bb98ea2f2bd66e4545` (matches supplied) |
| Design report actual SHA-256 | `1607b942941bb05140196c499230d682648ddc206a67f3afc1bbd7805db6108e` (matches supplied) |
| WP-01 report actual SHA-256 | `08c09c3a257b56e82e835e845e360106004ea20a33da6f0e18ae38e44eabe33d` |

No fetch, pull, branch switch, reset, restore, clean, stage, commit, or push was performed.

---

## 2. Sources and code paths inspected

### 2.1 Records

- `AGENTS.md`.
- `docs/audits/OHB2-WP01-ATTACHMENT-LIFECYCLE-IMPLEMENTATION-REPORT.md` (actual WP-01 report; untracked).
- `docs/decisions/OHB2-WP01-OD01-OD03-OWNER-DECISION-RECORD.md`.
- `docs/reviews/OHB2-OD01-OD03-OWNER-DECISION-PACKAGE.md`.
- `docs/reviews/OHB2-MASTER-BACKLOG-RECONCILIATION-AND-NEXT-TASK-REPORT.md` (historical; stale for WP-01).
- `docs/reviews/OHB2-WP01-ACTIVE-BATCH-CANCELLATION-SAFETY-DESIGN.md` and its report.
- `.agent/PROGRESS.md` (read-only; not modified).

### 2.2 Code

| Area | Verified paths/functions |
|---|---|
| `/cancel` | `bot/handlers.py::cancel_route` (3076-3086), `cancel_route_button` (3089-3101) |
| Awaiting state | `bot/db.py::clear_awaiting_and_record_outcome` (3039-3069) |
| Commands | `bot/app.py::BOT_COMMANDS` (48-62), handler registration (114-125), `bot/handlers.py::attachments_clear` (3030-3073), `HELP_TEXT` (902-917), `tests/test_app.py:304-317` |
| Statuses | `bot/db.py:115-161` |
| Routing | `bot/db.py::classify_attachment_routing` (1610-1698), `AttachmentRoutingState` (517-538) |
| Batch CAS/transactions | `try_mark_attachment_item_stored` (1233-1290), `mark_attachment_batch_status` (1309-1319), `clear_attachment_terminal_batch` (1447-1511), `record_attachment_intent` (1700-1790), `mark_attachment_item_reaped` (1580-1600) |
| Persistence | `bot/attachments.py::AttachmentService.accept` (1039-1148), `_accept_lock` (521-526), `store_async` (881-983), `_store_prepare` (662-761), `_store_finalize` (763-799) |
| Reaper | `_TERMINAL` (1242-1250), `_sweep_db_phase` (1313-1388), `_mark_expired` (1460-1474), `_plan_batch` (1476-1538), `_plan_orphan_items` (1564-1620), `_remove_file` (1689-1735) |
| Startup/watcher | `bot/app.py:245-259`, `bot/watcher.py:177-183` |
| Outbox | `bot/outbox.py::outbox_recover` (529-555), `OutboxWorker` (672-695); attachment paths create no outbox row |
| Mini App | `bot/web/services.py:790-870` (`latest_pending` only; no deletion) |
| Schema | `bot/db.py:779-825`; `Database.__init__` WAL/busy_timeout (558-590) |

### 2.3 Read-only checks

```text
pytest -q tests/test_wp01_attachment_lifecycle.py -k 'cancel or clear'
24 passed, 4 deselected in 1.72s
```

No dependency installation or environment modification was performed. The existing temporary venv
was reused for this focused test only.

---

## 3. Verification of each Stage 1 assumption

| # | Assumption | Result | Evidence and correction |
|---:|---|---|---|
| 1 | Only `pending` may be cancelled | **PASS (proposed)** | `pending` is the only active local batch state; `intent_recorded`/`dispatching`/`uncertain` are unresolved and terminal states are protected (`bot/db.py:115-161`). |
| 2 | `intent_recorded`, `dispatching`, `uncertain`, terminal are not cancellable | **PASS (proposed)** | Same evidence; `intent_recorded` carries durable intent/identity and remote states are ambiguous; terminal policy is OD-01. |
| 3 | Cancellation identifies exactly one batch by explicit Batch ID | **PASS (convention)** | Existing `attachments_clear` uses exact `context.args` (`bot/handlers.py:3038-3052`); recommended command follows it. |
| 4 | Ownership is verified | **PASS (pattern)** | Existing DB methods use `batch_id` + `telegram_id` (`bot/db.py:1447-1511`); new method must do the same. |
| 5 | `pending → cancelled` is atomic and conditional | **PARTIAL** | The project has CAS patterns (`try_mark_attachment_item_stored`, `clear_attachment_terminal_batch`), but no batch CAS exists; `mark_attachment_batch_status` is unconditional (`bot/db.py:1309-1319`). **Correction:** add a batch CAS inside `BEGIN IMMEDIATE`. |
| 6 | `_accept_lock` protects the relevant operation | **PARTIAL** | It is a per-`StagingStore` `anyio.Lock` used only by `store_async` (`bot/attachments.py:521-526`, `923`). It does not cover download/classification/row creation or sync `store()`, and `_store_prepare` does not check batch status (`662-761`). **Correction:** use the same lock for the write window and add a `pending` status check in `_store_prepare`; keep production on `store_async`. |
| 7 | DB transaction uses existing SQLite ownership/semantics | **PASS (pattern)** | One `Database` connection, WAL, `busy_timeout=5000`; `BEGIN IMMEDIATE` used by lifecycle methods (`bot/db.py:558-590`, 1233-1290, 1447-1511). |
| 8 | Duplicate cancellation is idempotent and cannot affect another batch | **PARTIAL** | Existing `clear_attachment_terminal_batch` checks `update_id` and exact batch; `clear_awaiting_and_record_outcome` does not check duplicates (`3039-3069`). **Correction:** new DB method must check `update_is_processed` inside the transaction and use exact batch ID. |
| 9 | Success response only after durable transition | **PASS (pattern)** | `attachments_clear` replies only after the DB method returns; DB commits before return (`bot/handlers.py:3053-3071`). |
| 10 | DB failure does not produce false success | **PASS (pattern)** | `attachments_clear` re-raises DB exceptions and does not reply (`bot/handlers.py:3061-3063`). New handler must do the same. |
| 11 | No file/row/identity is deleted or moved | **PARTIAL** | Cancellation itself performs no FS/DB deletion, but an in-flight `store_async` failure can `_safe_unlink` a newly written file (`bot/attachments.py:770-795`) if cancellation wins mid-write and `_store_prepare` lacks a status check. **Correction:** status check + shared lock; cancellation must never delete persisted bytes. |
| 12 | Reaper explicitly excludes `cancelled` | **NOT CURRENT** | `_TERMINAL` is exactly `delivered/expired/rejected/failed` (`bot/attachments.py:1242-1250`); no `cancelled` exists. **Correction:** add explicit non-reapable skip/report and tests. |
| 13 | `_mark_expired` cannot overwrite `cancelled` | **NOT CURRENT** | `_mark_expired` calls unconditional `mark_attachment_batch_status` (`bot/attachments.py:1460-1474`; `bot/db.py:1309-1319`). **Correction:** CAS `pending → expired`; do not plan if CAS fails. |
| 14 | `mark_attachment_item_reaped` cannot mark cancelled items | **NOT CURRENT** | It checks only item status `pending/stored`; no parent-batch guard (`bot/db.py:1580-1600`). **Correction:** batch-aware guard for the batch path; orphan path remains separate. |
| 15 | OD-01 clearance for `expired`/`rejected` remains unchanged | **PASS** | `ATTACHMENT_BATCH_CLEARABLE_STATUSES` is exactly `{expired, rejected}` (`bot/db.py:157-161`); `cancelled` must not be added. |

### 3.1 Conclusion on assumptions

The design is implementable, but assumptions 5, 6, 8, 11, 12, 13, and 14 require code changes or
explicit implementation rules. The three most important are:

1. `_store_prepare` status check + shared `_accept_lock`;
2. CAS for `pending → expired` (and for `pending → cancelled`);
3. parent-batch guard for `mark_attachment_item_reaped`.

The current absence of `cancelled` from `_TERMINAL` is **not** a sufficient safety proof; it must be
an explicit, tested exclusion.

---

## 4. Recommendation and unresolved questions

### 4.1 Recommendation

Adopt **A1 + B + C + D + E + F + G + H** as presented in the decision package:

- `pending` only;
- `/attachments_cancel <batch_id> confirm`;
- exact ID + owner verification;
- explicit reaper exclusion, CAS expiry, and item batch guard;
- retain all files/rows/identity; Stage 2 deferred;
- keep Mini App frozen;
- no schema migration, but update all code paths;
- separate design approval, implementation authorization, and Stage 2 authorization.

### 4.2 Unresolved owner questions

1. Does the owner approve the Stage 1 design?
2. Does the owner authorize a separate Stage 1 implementation task?
3. Does the owner defer Stage 2 cleanup, or authorize a separate Stage 2 design only?
4. If A2 is desired later, what should happen to `intent_recorded` identity evidence?
5. If Mini App visibility is desired later, that is a separate frozen-boundary decision.

No owner choice is assumed or filled in this report.

---

## 5. Files created

| File | Purpose |
|---|---|
| `docs/reviews/OHB2-WP01-STAGE1-CANCELLATION-OWNER-DECISION-PACKAGE.md` | Owner decision package |
| `docs/reviews/OHB2-WP01-STAGE1-CANCELLATION-OWNER-DECISION-REPORT.md` | This task report |

No other file was created, modified, moved, renamed, or deleted by this task.

---

## 6. Verification and SHA-256

### 6.1 Checks

| Check | Result |
|---|---|
| `git diff --check` | exit 0; no output |
| Focused existing tests | `24 passed, 4 deselected` |
| Design SHA-256 vs supplied | matches |
| Design report SHA-256 vs supplied | matches |
| Source re-inspection | no `cancelled` implementation; no state-machine change invalidating Option C |
| Full Python suite | **NOT RUN** (design/decision-only task) |
| Implementation tests | **NOT CLAIMED** |
| Live Telegram/OpenHands | **NOT RUN** |
| Independent review | **NOT CLAIMED** |

### 6.2 Hashes

| File | Lines | SHA-256 |
|---|---:|---|
| `docs/reviews/OHB2-WP01-STAGE1-CANCELLATION-OWNER-DECISION-PACKAGE.md` | 609 | `8749bd20f4a105afded0db47588abb6290c7a1cedc6d863372ebcdd6dc5a851a` |
| `docs/reviews/OHB2-WP01-STAGE1-CANCELLATION-OWNER-DECISION-REPORT.md` | 203 | `211559540b9e0c098196e67d348713b37a663410d5329baf340521ed7f310175` — hash computed over this report **excluding this table row** |

The report self-hash is defined over this report with the table row containing the text
“hash computed over this report **excluding this table row**” excluded; a self-referential
full-file hash cannot include itself. The final response records the actual full-file `sha256sum`
after finalization.

---

## 7. Limitations

- The current WP-01 implementation is **uncommitted working-tree state**; the package is based on
  that actual state, not only HEAD.
- The design report’s assumptions 5, 6, 8, 11, 12, 13, and 14 are not all satisfied by the current
  code; the package documents the required corrections. Stage 1 must not be implemented as a
  minimal “add a status constant” change.
- No implementation or stress tests were run; the race matrix remains a design requirement for the
  future implementation task.
- Cancelled data retention is indefinite in Stage 1 and can consume the staging cap; no cleanup is
  authorized.
- The Mini App remains frozen and hides cancelled batches.
- No owner approval, no independent review, and no WP-01 closure is claimed.

---

## 8. Preservation and authorization confirmation

- No application code or tests were modified.
- No SQLite schema or data was changed.
- No reaper, outbox, Mini App, `bot/web`, dependency, lockfile, runtime configuration, or CI was
  modified.
- No attachment file or staging directory was deleted, moved, renamed, or cleaned.
- No historical decision record was modified and no owner approval was recorded.
- No stage, commit, push, PR, merge, deployment, release, or Autopush occurred.
- All pre-existing tracked, untracked, and ignored files were preserved.
- **WP-01 remains open; Stage 1 remains unapproved and unimplemented.**
