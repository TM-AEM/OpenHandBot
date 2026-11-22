# OHB2-WP01 — Stage 1 Cancellation Owner Decision Package

- **Task ID:** `OHB2-WP01-STAGE1-CANCELLATION-OWNER-DECISION-PACKAGE`
- **Date:** 2026-11-22
- **Status:** `PROPOSED — OWNER DECISION REQUIRED`
- **Implementation:** **NOT AUTHORIZED. NOT IMPLEMENTED.**
- **WP-01:** **NOT CLOSED.**
- **Recommendation:** **Approve the Stage 1 design only if the two mandatory code-safety corrections
  in §8.2 are accepted; authorize implementation separately; defer Stage 2 cleanup.**
- **Approval fields:** **NONE FILLED.** See §15.

> **Read-only decision package.** This document verifies the current working tree and prepares owner
> choices. It does not create a `cancelled` state, change code, alter SQLite data, modify the reaper,
> or authorize any cleanup.

---

## 1. Executive recommendation

### 1.1 Recommended decision set

| Decision | Recommendation |
|---|---|
| **A — Eligible state** | **A1: `pending` only** |
| **B — User command** | **`/attachments_cancel <batch_id> confirm`** |
| **C — Ownership/selection** | **Exact batch ID + owner verification; never cancel all batches implicitly** |
| **D — Reaper behavior** | **Explicit `cancelled` exclusion + conditional expiry + item-level batch guard** |
| **E — Retention** | **Retain all files, rows, and identity evidence; Stage 2 cleanup deferred** |
| **F — Mini App** | **Keep frozen and unchanged; no `cancelled` UI required for Stage 1** |
| **G — Schema** | **No migration needed for the status value, but several code paths must be updated** |
| **H — Authorization** | **Design approval, implementation authorization, and Stage 2 cleanup are separate** |

### 1.2 Why Stage 1 is worth approving

The current `/cancel` clears only the route. It leaves the attachment batch `pending`; the owner’s
next text is rejected as `route_mismatch`, and the existing reaper may later delete the bytes at TTL.
The Stage 1 proposal gives the owner a precise, durable way to stop processing **without deleting
anything**, while preserving the existing fail-closed terminal policy.

### 1.3 What is not being approved

This package does **not** authorize:

- implementation of `cancelled`;
- deletion, reaping, retention expiry, or cleanup of cancelled batches;
- any change to OD-01 or OD-03;
- any change to the Mini App, outbox, dependencies, CI, or concurrency policy;
- Stage 2 in any form.

### 1.4 Explicit decision table

| Decision | Recommended | Alternatives considered | Why |
|---|---|---|---|
| **A — Eligible state** | **A1: `pending` only** | **A2:** `pending` + `intent_recorded`; **A3:** add `dispatching`/`uncertain` or other states | A2 needs a new identity-aware rule and a decision about discarding durable intent; A3 is unsafe while remote outcome is ambiguous. A1 has no identity evidence and is locally reversible |
| **B — Command** | **`/attachments_cancel <batch_id> confirm`** | Reuse `/cancel`; use a callback button; add an implicit “cancel latest” command | Reusing `/cancel` conflates route cancellation with batch selection; callbacks lack a reliable batch-ID input; implicit selection violates exact-ID requirement. The existing `attachments_clear` parser pattern supports the recommended command |
| **C — Selection/ownership** | **Exact ID + owner check; never guess** | Owner-wide “cancel all”; latest pending; conversation-wide | Exact ID is the only way to avoid ambiguity with multiple pending batches; ownership check prevents cross-owner changes |
| **D — Reaper** | **Explicit exclusion + CAS expiry + item batch guard** | Rely on `cancelled` not being in `_TERMINAL`; rely only on item CAS | Not adding to `_TERMINAL` is necessary but insufficient without explicit skip/report; unconditional expiry can overwrite `cancelled`; item CAS has no parent-batch guard |
| **E — Retention** | **Retain all files/rows/identity; Stage 2 deferred** | Auto-delete after a timeout; reuse existing reaper; delete on cancel | Any deletion is irreversible and unauthorized; Stage 2 requires a separate owner decision |
| **F — Mini App** | **Freeze; no UI change** | Add cancelled list/download support | Frozen boundary; Stage 1 does not require Mini App visibility; adding it would broaden scope |
| **G — Schema** | **No migration; update all code paths** | Assume no CHECK means no code change; add a column/table | The status column accepts a new text value, but status lists, routing, reaper, and item guard must be updated; no schema migration is needed |
| **H — Authorization** | **Separate design approval, implementation authorization, Stage 2 authorization** | Treat one approval as covering all three | Prevents accidental destructive cleanup and preserves the owner’s decision boundary |

---

## 2. Verified current behavior

### 2.1 Git baseline

| Item | Verified value |
|---|---|
| Branch | `main` |
| HEAD | `0774c9cff923a2ed02da36a1111a283a61600ea5` |
| HEAD tree | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| Index | Empty (`git diff --cached --name-status` produced no entries) |
| Working tree | Pre-existing uncommitted WP-01/poller/WP-08 changes preserved |
| Design artifact | `docs/reviews/OHB2-WP01-ACTIVE-BATCH-CANCELLATION-SAFETY-DESIGN.md` |
| Design SHA-256 | `5436c2b1539eee7843b03c21137cc4926eac7a92c39a32bb98ea2f2bd66e4545` (matches supplied value) |
| Design report | `docs/reviews/OHB2-WP01-ACTIVE-BATCH-CANCELLATION-SAFETY-DESIGN-REPORT.md` |
| Design report actual SHA-256 | `1607b942941bb05140196c499230d682648ddc206a67f3afc1bbd7805db6108e` (matches supplied value) |
| Actual WP-01 report | `docs/audits/OHB2-WP01-ATTACHMENT-LIFECYCLE-IMPLEMENTATION-REPORT.md` (untracked) |

The historical master reconciliation still says WP-01 was not started; that is stale relative to the
working tree. The implementation is uncommitted and was preserved.

### 2.2 `/cancel` and button behavior

`cancel_route` (`bot/handlers.py:3076-3086`) and `cancel_route_button`
(`bot/handlers.py:3089-3101`) call only:

```python
db.clear_awaiting_and_record_outcome(
    telegram_id, update_id, outbox.now_iso(), update_outcomes.DURABLE_COMPLETED
)
```

`clear_awaiting_and_record_outcome` (`bot/db.py:3039-3069`) clears `user_state.awaiting_*` and
records the update outcome in one `BEGIN IMMEDIATE` transaction. It does not touch
`attachment_batches`, `attachment_items`, or `attachment_message_identity`.

Verified consequences:

- an active batch remains `pending`;
- the `/cancel` reply says the route was cancelled, not that the batch was cancelled;
- after the route is cleared, `_handle_accompanying_text` (`bot/handlers.py:2747-2898`) sees
  `LIVE` plus a missing/mismatched route and rejects the text with `route_mismatch`;
- at `T0 + 15 minutes` (`ATTACHMENT_BATCH_TTL`, `bot/db.py:264-270`) the reaper can transition the
  batch to `expired` and delete its bytes.

Existing focused tests confirm the current state:

```text
pytest -q tests/test_wp01_attachment_lifecycle.py -k 'cancel or clear'
24 passed, 4 deselected
```

`tests/test_wp01_attachment_lifecycle.py::test_cancel_does_not_delete_active_batch_data` currently
asserts that `/cancel` leaves the batch `pending` and its item row intact.

### 2.3 Command conventions

The existing `attachments_clear` handler (`bot/handlers.py:3030-3073`) already demonstrates the
project convention for a one-batch, explicit command:

- `_guard` checks owner/chat authorization;
- `context.args` must contain exactly the batch ID and `confirm`;
- missing/invalid arguments return usage and mark the update explicitly ignored;
- the DB method returns a result string;
- the handler replies only after the DB call returns;
- database exceptions are re-raised, with no success reply.

`BOT_COMMANDS` (`bot/app.py:48-62`) and `CommandHandler` registration
(`bot/app.py:114-125`) require every listed command to have a handler, enforced by
`tests/test_app.py::test_bot_commands_match_registered_command_handlers`. A new command must be
added to both, plus `HELP_TEXT` (`bot/handlers.py:902-917`).

`/attachments_cancel <batch_id> confirm` is therefore supported by the existing parser and handler
conventions without a new interaction model, callback scheme, or worker.

---

## 3. Verified state-machine behavior

### 3.1 Current statuses

`bot/db.py:115-138` defines:

`pending`, `intent_recorded`, `dispatching`, `uncertain`, `delivered`, `expired`, `rejected`,
`failed`.

- `pending` is the only state eligible for a new file or accompanying intent.
- `intent_recorded`, `dispatching`, `uncertain` are `UNRESOLVED` and block normal text.
- `delivered`, `expired`, `rejected`, `failed` are terminal and block normal text, except explicit
  clearance for `expired`/`rejected`.
- `dispatching`/`uncertain` have no current production transition; they are future Stage B states.

### 3.2 Current routing

`classify_attachment_routing` (`bot/db.py:1610-1698`) order:

1. unknown status → `AttachmentBatchIntegrityError` (fail closed);
2. unresolved statuses → `UNRESOLVED`;
3. multiple live pending → `MULTI_LIVE`;
4. one live pending → `LIVE`;
5. expired pending → `EXPIRED_PENDING`;
6. terminal batches → `TERMINAL_ASSOCIATED` (identity proven) or `TERMINAL_UNPROVEN`; explicit
   clearance can make only cleared `expired`/`rejected` fall through;
7. otherwise `NONE`.

`TERMINAL_ASSOCIATED`/`TERMINAL_UNPROVEN` are rejected by
`_handle_accompanying_text` (`bot/handlers.py:2798-2808`). `delivered` and `failed` are never
clearable; `ATTACHMENT_BATCH_CLEARABLE_STATUSES` is exactly `{expired, rejected}`
(`bot/db.py:157-161`).

### 3.3 Current batch transactions and CAS

- `try_mark_attachment_item_stored` (`bot/db.py:1233-1290`) is an atomic conditional transition:
  item `pending` and parent batch `pending`, both in one `UPDATE`, under `BEGIN IMMEDIATE`.
- `clear_attachment_terminal_batch` (`bot/db.py:1447-1511`) is a `BEGIN IMMEDIATE` transaction that
  checks `update_id`, owner, status, and clearance marker; it does not delete files or rows.
- `record_attachment_intent` (`bot/db.py:1700-1790`) is a `BEGIN IMMEDIATE` transaction that
  CAS-transitions `pending → intent_recorded`, writes identity evidence, and records a durable
  outcome.
- `mark_attachment_batch_status` (`bot/db.py:1309-1319`) is **unconditional**: it updates by
  `batch_id` only. It is currently used by `_mark_expired` and the accept path for an old pending
  batch.
- There is **no** existing batch-level CAS helper and **no** `cancelled` status.

---

## 4. Actual reaper deletion conditions

`AttachmentReaper._TERMINAL` (`bot/attachments.py:1242-1250`) is exactly:

```text
delivered, expired, rejected, failed
```

For a terminal batch with parseable `t0`, `_plan_batch` (`bot/attachments.py:1476-1538`):

1. lists items;
2. for each `pending`/`stored` item, calls `mark_attachment_item_reaped` before any unlink;
3. for an already-`reaped` item, schedules a retry unlink;
4. appends `FileCleanup` entries;
5. `_apply_cleanups` calls `_remove_file` (`bot/attachments.py:1689-1735`), which only unlinks a
   single regular file inside the validated staging root; symlinks, foreign paths, and non-regular
   entries are refused.

`_mark_expired` (`bot/attachments.py:1460-1474`) calls the unconditional
`mark_attachment_batch_status` for `pending → expired`. That is a **mandatory correction point**:
it can overwrite a future `cancelled` status unless changed to CAS.

`mark_attachment_item_reaped` (`bot/db.py:1580-1600`) checks only the **item** status
(`pending`/`stored`). It does **not** check the parent batch status. If called for an item whose
batch is `cancelled`, it would mark that item `reaped`. The reaper must not call it in that case,
and a batch-status guard is recommended as defense in depth.

The reaper is invoked from the existing startup hook (`bot/app.py:245-259`) and the existing
`Watcher.tick` via `OpportunisticSweeper` (`bot/watcher.py:177-183`;
`bot/attachments.py:1749-1858`). No new reaper worker exists or is proposed.

---

## 5. Stage 1 proposed state transition

### 5.1 Transition

| From | To | Preconditions | Side effects |
|---|---|---|---|
| `pending` | `cancelled` | exact `batch_id`; `telegram_id` matches; `update_id` not already processed; current status is `pending`; CAS succeeds | set `status='cancelled'`, `updated_at`; record `durable_completed` in the same SQLite transaction; **no** route clear, file, item, or identity change |

### 5.2 Explicitly not transitionable

- `intent_recorded` → anything (Stage 1): remains unresolved.
- `dispatching` / `uncertain` → anything (Stage 1): remains unresolved; remote ambiguity.
- `delivered` / `expired` / `rejected` / `failed` → anything (Stage 1): terminal; use existing
  OD-01 clearance only for `expired`/`rejected`.
- unknown / corrupt → anything: fail closed.
- `cancelled` → any other status: not part of Stage 1; no resume/undo.

### 5.3 Routing treatment

Add an explicit `AttachmentRoutingState.CANCELLED` (or equivalent) that is **non-blocking** for
ordinary prompts. Because Stage 1 permits only `pending` cancellation, there is no message identity
evidence attached to a cancelled batch. If a later owner decision permits cancelling
`intent_recorded`, a separate identity-aware rule must be designed before implementation; do not
silently turn a message with existing identity evidence into a new prompt.

The existing `TERMINAL_*`, `UNRESOLVED`, `MULTI_LIVE`, `EXPIRED_PENDING`, and unknown behavior must
remain unchanged.

---

## 6. Eligible and ineligible states

| State | Cancellable in Stage 1? | Reason |
|---|---|---|
| `pending` | **YES** | Active local batch; no durable intent/identity; safe to stop without deletion |
| `intent_recorded` | **NO** | Durable local intent and identity exist; needs separate policy |
| `dispatching` | **NO** | Remote dispatch may be underway; ambiguity |
| `uncertain` | **NO** | Remote outcome unknown; must reconcile |
| `delivered` | **NO** | Terminal success; protected |
| `expired` | **NO** | Terminal; only existing explicit clearance, not cancellation |
| `rejected` | **NO** | Terminal; only existing explicit clearance, not cancellation |
| `failed` | **NO** | Terminal failure; protected |
| unknown/corrupt | **NO** | Fail closed |
| `cancelled` | **NO-OP** | Already cancelled; idempotent response only |

“Pending” includes a batch whose `t0` deadline has passed but which has not yet been transitioned by
the reaper. Cancellation may win the CAS before the reaper; if the reaper commits `expired` first,
cancellation returns `not_eligible`/`too_late` and must not claim success.

---

## 7. Exact command contract

### 7.1 Command

```text
/attachments_cancel <batch_id> confirm
```

### 7.2 Parser and validation

- Exactly two arguments after the command: non-empty batch ID and case-insensitive `confirm`.
- Missing/extra arguments or missing `confirm` → usage response; no DB write; mark update
  `explicitly_ignored`.
- Batch ID is used as a parameterized SQL value; no path/command construction.
- No “cancel all”, no “latest batch”, no conversation-wide fallback.
- Multiple pending batches are irrelevant to selection because the ID is explicit; the command
  never guesses.

### 7.3 Ownership and selection

- The DB method requires both `batch_id` and `telegram_id`.
- Wrong owner and nonexistent ID both return `not_found`; do not reveal another owner’s batch.
- A valid ID belonging to another user must leave that batch unchanged.

### 7.4 Result messages and outcomes

| Result | Meaning | Outcome handling |
|---|---|---|
| `cancelled` | transition committed | reply success only after commit; `durable_completed` written atomically |
| `already_cancelled` | idempotent no-op | no second transition; `explicitly_ignored` (or documented equivalent) |
| `not_found` | no owned batch with that ID | no state change; `explicitly_ignored`; no existence leak |
| `not_eligible` | state not `pending` | no state change; `explicitly_ignored`; explain allowed state |
| `duplicate` | `update_id` already processed | no state change; no outcome overwrite |
| DB exception | failure | no success reply; re-raise/record failure |

Suggested Arabic response meanings (final wording chosen at implementation):

- success: “اتلغت معالجة الدفعة. الملفات والبيانات محفوظة محليًا ومش هتتحذف تلقائيًا.”
- already cancelled: “الدفعة دي ملغاة بالفعل؛ مفيش تغيير.”
- not found: “مفيش دفعة بالمعرّف ده لهذا المالك.”
- not eligible: “الإلغاء مسموح فقط لدفعة pending.”
- duplicate: “التحديث ده اتعالج قبل كده؛ مفيش تغيير.”
- usage: “/attachments_cancel <batch_id> confirm”

`/attachments_cancel` must **not** clear `user_state` or the route; it is a batch command, not
`/cancel`. The owner can still use `/cancel` for route cancellation.

### 7.5 Registration

Future implementation must add:

- `BOT_COMMANDS` entry (`bot/app.py:48-62`);
- `CommandHandler("attachments_cancel", handlers.attachments_cancel)` (`bot/app.py:114-125`);
- `HELP_TEXT` line (`bot/handlers.py:902-917`);
- `attachments_list` hint (`bot/handlers.py:3020-3025`), without exposing tokens/paths.

The existing command-list parity test must pass.

---

## 8. Atomicity, ownership, idempotency, and concurrency analysis

### 8.1 Database transaction

Recommended DB method, in the existing `Database` class:

```text
BEGIN IMMEDIATE
  if update_id is not None and update_is_processed(update_id):
      rollback; return "duplicate"
  SELECT status FROM attachment_batches WHERE batch_id=? AND telegram_id=?
  if missing: rollback; return "not_found"
  if status == "cancelled": rollback/commit; return "already_cancelled"
  if status != "pending": rollback; return "not_eligible"
  UPDATE attachment_batches SET status='cancelled', updated_at=?
    WHERE batch_id=? AND telegram_id=? AND status='pending'
  if rowcount != 1: rollback; return "not_eligible"   # CAS race
  mark_update_outcome(update_id, DURABLE_COMPLETED, commit=False)
COMMIT
```

- One SQLite connection, WAL, `busy_timeout=5000` (`bot/db.py:558-590`).
- No filesystem operation in the transaction.
- No item/identity/batch-row deletion.
- No route clear in this command.
- A failure rolls back; the handler must not reply success.

### 8.2 Mandatory corrections to current code assumptions

The proposed Stage 1 is implementable, but **two current-code assumptions are incomplete**:

1. **`_accept_lock` alone is not sufficient.** It is a per-`StagingStore` `anyio.Lock`
   (`bot/attachments.py:521-526`) acquired only by `store_async` (`bot/attachments.py:923`). It does
   not cover `AttachmentService.accept` before `store_async` (authorization, classification, row
   creation) and does not cover the synchronous `store()` path. `_store_prepare`
   (`bot/attachments.py:662-761`) checks ownership and conversation but **not** `batch.status`.
   Correction: cancellation must use the same store lock for the file-write/finalize window **and**
   `_store_prepare` must reject a non-`pending` batch before any write. Production must remain on
   `store_async`; document the sync path as lower-level.
2. **`mark_attachment_item_reaped` has no parent-batch guard.** It only checks item
   `pending`/`stored` (`bot/db.py:1580-1600`). Correction: the reaper must not call it for a
   cancelled batch, and the method (or a new batch-aware variant) should require a terminal parent
   batch for the batch path. Orphan-item cleanup needs a separate path that does not require a
   parent row.

These corrections are part of the Stage 1 implementation authorization, not part of this
read-only task.

### 8.3 `_accept_lock` ownership and scope

- Created once per `StagingStore` instance (`bot/attachments.py:521-526`).
- Production `_attachment_service` reuses `context.bot_data["attachment_store"]`
  (`bot/handlers.py:2357-2380`), so `/attachments_cancel` and `handle_attachment` can share the same
  lock only if the command uses that same service/store.
- `store_async` holds the lock across `_store_prepare`, worker write, and `_store_finalize`
  (`bot/attachments.py:923-983`).
- `AttachmentService.accept` downloads bytes **before** `store_async` (`bot/attachments.py:1124-1141`),
  so cancellation can run during download; the later `_store_prepare` status check is required.
- The lock is `anyio.Lock`; it is not a cross-loop or cross-process lock. Production has one event
  loop and one DB owner; no new lock/worker is needed.

### 8.4 Race matrix

| Race | Result with proposed design |
|---|---|
| Cancel before store prepare | Batch `cancelled`; prepare rejects; no file written; item row remains pending in cancelled batch |
| Cancel during download | Same; later prepare rejects; no file |
| Store wins, then cancel | Store writes and marks item stored; cancel then marks batch cancelled; file and item preserved |
| Reaper expires before cancel | Cancel sees `expired`; returns `not_eligible`; no false success; reaper may proceed |
| Cancel before reaper expiry | Reaper CAS `pending → expired` fails; no terminal planning; bytes preserved |
| Reaper selected but not committed | CAS resolves winner; only one status transition commits |
| Duplicate update | `update_is_processed` inside transaction → `duplicate`; no second effect |
| Duplicate new `/attachments_cancel` | `already_cancelled`; no second effect |
| DB BUSY/LOCKED | No success reply; transaction rolls back; update can be retried |
| Permanent DB error | Fail closed; no state change; no file deletion |
| Telegram ack fails after commit | State and outcome durable; no success claim; `/attachments` is source of truth |
| Crash after commit | Restart sees `cancelled`; reaper skips; no deletion |
| Crash before commit | Batch remains `pending`; command can be retried; TTL path may later expire |
| File exists, DB row missing | Untracked file is left/reported; cancellation does not delete |
| DB row exists, file missing | Cancellation preserves row; cancelled is excluded from reaper |

---

## 9. Reaper safeguards

1. Add `ATTACHMENT_BATCH_CANCELLED` to `ATTACHMENT_BATCH_STATUSES` but **never** to
   `AttachmentReaper._TERMINAL`.
2. Add an explicit non-reapable set and skip/report `cancelled` in `_sweep_db_phase`
   (`bot/attachments.py:1313-1388`) and `_plan_batch` (`bot/attachments.py:1476-1538`).
3. Change `_mark_expired` (`bot/attachments.py:1460-1474`) to a CAS `pending → expired`; if the
   batch is `cancelled`, do not transition and do not plan deletion.
4. Change the accept path’s old-batch expiry (`bot/attachments.py:1083-1089`) to the same CAS.
5. Prevent `mark_attachment_item_reaped` from marking items whose parent batch is `cancelled`;
   add a batch-aware guard for the batch path.
6. Do not delete batch rows, item rows, or identity evidence.
7. Keep `_remove_file` path/symlink/regular-file protections unchanged.
8. Keep orphan cleanup limited to items whose batch row is actually missing; cancellation must not
   delete the batch row.
9. Leave untracked files in place and report them.

---

## 10. Retention guarantees

- Stage 1 retains every attachment file, `staging_token`, item row, batch row, `intent_text` (if
  present, though Stage 1 only cancels `pending`), and `attachment_message_identity` row.
- No move, rename, quarantine, unlink, or database row deletion.
- No automatic cleanup, TTL expiry of cancelled batches, or reaper eligibility.
- Cancelled batches remain visible through `/attachments` (status display only; no path/token).
- The Mini App remains frozen and continues to list only `pending` batches; cancelled batches are
  not downloadable there. This is not required for Stage 1.
- Cancelled files count toward the staging byte cap; indefinite retention may reduce capacity and
  requires an owner decision. No automatic eviction is authorized.

---

## 11. Schema compatibility

### 11.1 What the schema allows

`attachment_batches.status` is `TEXT NOT NULL DEFAULT 'pending'` with no SQL CHECK constraint
(`bot/db.py:779-787`). Adding a new status value does not require a table/column migration.

### 11.2 What still must change

The absence of a CHECK constraint does **not** make every code path accept `cancelled`. Future
implementation must update:

- `ATTACHMENT_BATCH_STATUSES` (`bot/db.py:129-138`) so `has_unknown_attachment_batch_status`
  (`bot/db.py:1513-1527`) does not reject the new status.
- `classify_attachment_routing` (`bot/db.py:1610-1698`) with an explicit non-blocking
  `CANCELLED` branch; otherwise the new status could fall through incorrectly.
- `AttachmentReaper._TERMINAL`/`_sweep_db_phase`/`_plan_batch` to exclude it explicitly.
- `_mark_expired`/accept-path expiry to use CAS.
- `mark_attachment_item_reaped`/batch path to guard against cancelled parents.
- `/attachments` display and command help.

No migration is required, but **code-path compatibility is required**. Older code that does not
know `cancelled` will fail closed (unknown status) rather than delete; this is acceptable but means
downgrade is not a supported feature.

---

## 12. Required regression tests

### 12.1 DB and state

1. Owned `pending` + exact ID → `cancelled`; item/file/identity counts unchanged.
2. Wrong-owner ID → `not_found`; target batch unchanged.
3. `intent_recorded`, `dispatching`, `uncertain`, `delivered`, `expired`, `rejected`, `failed` →
   `not_eligible`; unchanged.
4. Duplicate `update_id` → `duplicate`; no second transition/outcome overwrite.
5. Repeated `/attachments_cancel` → `already_cancelled`; no second transition.
6. DB `BUSY`/`LOCKED` and permanent error → no success, no state change, no file deletion.
7. Success outcome is written in the same transaction; ack occurs after commit.

### 12.2 Persistence/concurrency

8. Cancel before `store_async` prepare → no file; item row remains.
9. Store wins, then cancel → file and `stored` item remain.
10. Cancel during download → later prepare rejects; no file.
11. `_store_prepare` rejects non-`pending` batch before writing.
12. The production path uses `store_async`; a source/behavior test proves the lock is shared.

### 12.3 Reaper

13. `cancelled` not in `_TERMINAL`; repeated sweep leaves bytes/rows.
14. `_mark_expired` CAS cannot overwrite `cancelled`.
15. `mark_attachment_item_reaped` cannot mark an item of a cancelled batch.
16. Restart/reopen: cancelled batch and file survive; reaper skips.
17. Untracked file remains; orphan item of a cancelled batch is not treated as orphan.
18. Existing terminal deletion tests for `expired`/`rejected`/`delivered`/`failed` remain green.

### 12.4 Clearance/UI/command

19. `/attachments_clear` still accepts only `expired`/`rejected`; `cancelled` is not clearable.
20. `/attachments_cancel` requires exact ID + `confirm`; missing/extra args/confirm are rejected;
    no implicit all.
21. `/attachments` displays cancelled status; no token/path.
22. `BOT_COMMANDS`/handler parity and `HELP_TEXT` include the new command.
23. No outbox row is created; no Mini App/`bot/web` change.
24. No attachment file/row/identity deletion or move.

---

## 13. Files expected to change in a future implementation

| File | Expected change |
|---|---|
| `bot/db.py` | `ATTACHMENT_BATCH_CANCELLED`; status tuple; non-reapable set; `cancel_pending_attachment_batch`; batch CAS helper; owner-scoped cancelled query; `AttachmentRoutingState.CANCELLED`; classification; batch-aware item guard |
| `bot/attachments.py` | `_store_prepare` status check; `AttachmentService.cancel_pending` using the existing lock; reaper skip/report; `_mark_expired` CAS; item guard |
| `bot/handlers.py` | `attachments_cancel` handler; `/attachments` status hint; `HELP_TEXT`; no `/cancel` change required for Stage 1 |
| `bot/app.py` | `BOT_COMMANDS` entry; `CommandHandler("attachments_cancel", ...)` |
| `tests/test_wp01_active_batch_cancellation.py` (new) | Full Stage 1 regression matrix |
| `tests/test_wp01_attachment_lifecycle.py` | Existing `/cancel` assertion remains as the old behavior; add explicit command tests or leave separate |
| `tests/test_attachment_cleanup_expiration_a4.py` | Cancelled exclusion/CAS/item-guard tests |
| `tests/test_app.py` | Command-list parity automatically covers new command if registered |
| `docs/OPERATIONS_RUNBOOK.md` | Document command, retention, no auto deletion |
| `README.md` / help | Command/user-facing behavior only if needed |

**Not expected to change:** `bot/outbox.py`, `bot/web/*`, `docs/MINI_APP.md`, dependencies,
lockfiles, CI, schema, or concurrency policy.

---

## 14. Risks and limitations

1. **Terminal race:** if the reaper commits `expired` before cancellation, cancellation cannot undo
   it. The command must return `not_eligible`/`too_late`, not a false success.
2. **Lock scope:** `_accept_lock` alone does not cover download/classification/row creation or the
   sync `store()` path; the mandatory `_store_prepare` status check is required.
3. **Item guard:** `mark_attachment_item_reaped` currently lacks a parent-batch guard; without the
   correction it could mark items of a cancelled batch.
4. **Indefinite retention:** cancelled files/rows remain forever in Stage 1 and count toward the
   staging cap. No automatic eviction is authorized.
5. **Mini App visibility:** the frozen Mini App lists only `pending`; cancelled batches are not
   downloadable there. Stage 1 does not require changing that.
6. **Uncommitted baseline:** the current WP-01 implementation is working-tree only; the package is
   based on that actual state, not only HEAD.
7. **No implementation tests:** this is design/decision only. The future implementation must prove
   the race matrix with deterministic tests.
8. **No independent review:** not claimed.
9. **Owner approval absent:** this package is a proposal, not an authorization.

---

## 15. Explicit owner approval fields

> **OWNER ONLY. Do not fill these fields on the owner’s behalf.**
> Current status: **NONE RECORDED.** No checkbox below is checked.

### 15.1 Decision 1 — Stage 1 design

- [ ] **APPROVE** the Stage 1 design as described in this package.
- [ ] **REJECT** the Stage 1 design.
- [ ] **REQUEST CHANGES** (specify): ______________________________________________

Owner signature / date: __________________________________________________________

### 15.2 Decision 2 — Stage 1 implementation authorization

- [ ] **AUTHORIZE** a separate Stage 1 implementation task, limited to the scope in §13 and the
  acceptance criteria in this package.
- [ ] **WITHHOLD** implementation authorization.
- [ ] **AUTHORIZE WITH CONDITIONS** (specify): ____________________________________

Owner signature / date: __________________________________________________________

### 15.3 Decision 3 — Stage 2 cleanup

- [ ] **DEFER** Stage 2 cleanup; retain all cancelled files/rows indefinitely for now.
- [ ] **AUTHORIZE A SEPARATE STAGE 2 DESIGN** only; no cleanup implementation yet.
- [ ] **AUTHORIZE STAGE 2 CLEANUP** (requires a separate explicit retention/confirmation policy):
  ______________________________________________________________________________

Owner signature / date: __________________________________________________________

### 15.4 Explicit non-conflation

- Approval of the **design** does not authorize implementation.
- Authorization of **Stage 1 implementation** does not authorize Stage 2 cleanup.
- Authorization of **Stage 2 cleanup** is a separate decision and is not requested here.
- No owner approval is recorded by this document.

---

## 16. Conclusion

**Stage 1 is safe and implementable only with the two mandatory corrections in §8.2:**
the `_store_prepare` status check plus shared `_accept_lock` usage, and the parent-batch guard for
`mark_attachment_item_reaped`. With those corrections, the recommended design preserves all
attachment data, uses the existing SQLite owner and command conventions, keeps the reaper from
touching `cancelled`, and leaves Stage 2 cleanup explicitly unapproved.

**Recommended owner action:** approve the design, authorize Stage 1 implementation separately, and
defer Stage 2 cleanup. **WP-01 remains open.**
