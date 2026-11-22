# OHB2-WP01 — Active Attachment-Batch Cancellation Safety Design

- **Task ID:** `OHB2-WP01-ACTIVE-BATCH-CANCELLATION-SAFETY-DESIGN`
- **Date:** 2026-11-22
- **Repository:** `/workspace/project/OpenHandBot`
- **Status:** `DESIGN ONLY — NO IMPLEMENTATION AUTHORIZED`
- **Recommendation:** **Option C — two-stage cancellation**, implemented in Stage 1 as a durable,
  non-reapable `cancelled` state, with cleanup deliberately deferred to a separate owner decision.
- **Owner approval:** **NONE RECORDED.** This document proposes a lifecycle change; it does not
  approve it and does not close WP-01.

> **Read-only design evidence.** The current working tree contains the uncommitted WP-01
> implementation described in `docs/audits/OHB2-WP01-ATTACHMENT-LIFECYCLE-IMPLEMENTATION-REPORT.md`.
> The committed baseline is `main` / `0774c9cff923a2ed02da36a1111a283a61600ea5` / tree
> `faa7a3f03aa361698c6854281c162358bf38b84f`; the attachment cancellation design below is evaluated
> against the **actual working tree**, not only the historical baseline.

---

## 1. Executive recommendation

**Recommend Option C.** Cancellation and cleanup are different lifecycle decisions:

1. **Stage 1 — stop processing without deleting anything.** `/cancel` may transition exactly one
   verified active `pending` batch, owned by the caller and associated with the current `route`
   conversation, to a new durable `cancelled` status. Items, `staging_token`s, bytes, identity
   evidence, and all rows remain intact.
2. **Stage 2 — cleanup eligibility is separate and not implemented here.** A `cancelled` batch must
   **never** become eligible for the existing reaper merely because it is cancelled. Any later
   cleanup requires a separate, explicit owner authorization for a specific batch, with its own
   retention and confirmation policy.

This is preferred over Option A because Option A does not actually cancel the batch and leaves the
owner blocked after `/cancel`. It is preferred over Option B as a single combined decision because
Option B risks conflating “stop processing” with “become eligible for deletion”; Option C makes the
separation an explicit invariant.

**No schema migration is required for Stage 1.** `attachment_batches.status` is an unconstrained
`TEXT` column (`bot/db.py:779-787`), and existing status validation is application-level
(`ATTACHMENT_BATCH_STATUSES`, `bot/db.py:115-138`). Stage 1 adds an application status value, not a
column or table.

**Reaper changes are required.** The current reaper treats `expired`/`rejected`/`delivered`/`failed`
as deletable terminal states (`bot/attachments.py:1242-1250`) and its expiry transition is an
unconditional status update (`bot/db.py:1309-1318`; called by
`AttachmentReaper._mark_expired`, `bot/attachments.py:1460-1474`). Stage 1 must add an explicit
`cancelled` exclusion and a compare-and-swap (CAS) `pending → expired` transition.

**Outbox changes are not required for Stage 1.** The current attachment lifecycle is local only:
`AttachmentService.accept` (`bot/attachments.py:1039-1148`) and
`Database.record_attachment_intent` (`bot/db.py:1700-1790`) do not create an `outbox` row. The only
outbox path is ordinary prompt dispatch after `_handle_accompanying_text` returns `False`
(`bot/handlers.py:2932-2971`).

---

## 2. Verified current behavior

### 2.1 Git and workspace baseline

| Item | Verified value |
|---|---|
| Branch | `main` |
| HEAD | `0774c9cff923a2ed02da36a1111a283a61600ea5` |
| HEAD tree | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| Index | Empty (`git diff --cached` produced no entries) |
| WP-01 implementation | **Uncommitted working-tree changes** in `bot/`, tests, docs, `.env.example`, `README.md`, `.agent/PROGRESS.md` |
| WP-01 report | Actual path is `docs/audits/OHB2-WP01-ATTACHMENT-LIFECYCLE-IMPLEMENTATION-REPORT.md` (untracked), not `docs/reviews/` |
| Historical master backlog | `docs/reviews/OHB2-MASTER-BACKLOG-RECONCILIATION-AND-NEXT-TASK-REPORT.md` still describes WP-01 as not started; that is stale relative to the current working tree |

No fetch, pull, branch switch, reset, restore, clean, stage, commit, or push was performed during this
design task.

### 2.2 Current `/cancel` behavior

`cancel_route` (`bot/handlers.py:3076-3086`) and `cancel_route_button`
(`bot/handlers.py:3089-3101`) call:

```python
db.clear_awaiting_and_record_outcome(
    telegram_id, update_id, outbox.now_iso(), update_outcomes.DURABLE_COMPLETED
)
```

`clear_awaiting_and_record_outcome` (`bot/db.py:3039-3069`) clears only `user_state.awaiting_*` and
records the update outcome in one `BEGIN IMMEDIATE` transaction. It does **not** read or write
`attachment_batches`, `attachment_items`, or `attachment_message_identity`.

Verified consequences:

- `/cancel` replies `"اتلغى التوجيه. ابعت /start للقائمة."` even when an active attachment batch
  exists (`bot/handlers.py:3086`). The reply can therefore imply the attachment context was
  cancelled when only the route was cleared.
- The active batch remains `pending`; the existing test
  `tests/test_wp01_attachment_lifecycle.py::test_cancel_does_not_delete_active_batch_data` asserts
  this current behavior.
- After `/cancel`, `_handle_accompanying_text` (`bot/handlers.py:2747-2898`) still classifies the
  pending batch as `LIVE`, sees that `route` is now absent/mismatched, and rejects the text with
  `ATTACHMENT_TEXT_AMBIGUOUS_TEXT` (`reason="route_mismatch"`). The owner cannot send a normal prompt
  until the batch expires.
- At `T0 + 15 minutes` (`ATTACHMENT_BATCH_TTL`, `bot/db.py:264-270`), the reaper may mark the batch
  `expired` and delete its bytes (`bot/attachments.py:1313-1388`, `1460-1538`, `1689-1735`).
  `/attachments_clear` can later clear the *routing block* only for `expired`/`rejected`, but it
  cannot restore bytes the reaper already deleted.

The existing `/cancel` behavior is therefore **data-preserving only until expiry**; it is not a
safe cancellation of an active batch and its user-facing message is misleading.

### 2.3 Current batch states and routing

Statuses are defined in `bot/db.py:115-138`:

`pending`, `intent_recorded`, `dispatching`, `uncertain`, `delivered`, `expired`, `rejected`,
`failed`.

Routing (`Database.classify_attachment_routing`, `bot/db.py:1610-1698`) is ordered:

1. unknown status → `AttachmentBatchIntegrityError` (fail closed);
2. `intent_recorded`/`dispatching`/`uncertain` → `UNRESOLVED`;
3. more than one live `pending` → `MULTI_LIVE`;
4. one live `pending` → `LIVE`;
5. expired `pending` → `EXPIRED_PENDING`;
6. terminal batches → `TERMINAL_ASSOCIATED` when the current message identity is proven, otherwise
   `TERMINAL_UNPROVEN`; explicit clearance for `expired`/`rejected` can make the terminal branch
   fall through;
7. otherwise `NONE`.

`TERMINAL_ASSOCIATED`/`TERMINAL_UNPROVEN` are fail-closed (`bot/db.py:1668-1694`), and
`_handle_accompanying_text` rejects both (`bot/handlers.py:2798-2808`). `delivered` and `failed` are
never clearable. Only `expired` and `rejected` are in
`ATTACHMENT_BATCH_CLEARABLE_STATUSES` (`bot/db.py:157-161`).

### 2.4 Current persistence and transaction boundaries

- `AttachmentService.accept` (`bot/attachments.py:1039-1148`) performs authorization, size/type
  checks, batch classification, then **row-first** creation of the batch/item and update outcome
  (`bot/db.py:1862-1985`), then downloads and stores bytes.
- `StagingStore._store_prepare` (`bot/attachments.py:662-761`) checks batch ownership and
  conversation validity but **does not check `batch.status`**. It returns `(path, token, cap)` for
  a batch that may have changed state since classification.
- `StagingStore.store_async` (`bot/attachments.py:881-980`) serializes acceptance with
  `StagingStore._accept_lock` (`bot/attachments.py:521-526`). The lock covers `_store_prepare`,
  the worker-thread write, and `_store_finalize`.
- `_store_finalize` (`bot/attachments.py:763-799`) calls
  `try_mark_attachment_item_stored` (`bot/db.py:1233-1283`), whose `UPDATE` requires both the item
  and its parent batch to be `pending`. If that fails, it calls `_safe_unlink(path)`
  (`bot/attachments.py:771-795`; `_safe_unlink` at `bot/attachments.py:287-292`).
- `record_attachment_intent` (`bot/db.py:1700-1790`) atomically changes `pending → intent_recorded`,
  stores `intent_text`, writes identity evidence, and records a durable outcome. It does **not**
  create outbox work.
- `Database.__init__` uses one SQLite connection, WAL, and `busy_timeout=5000`
  (`bot/db.py:558-590`). There is no second DB owner and no cross-file transaction.

**No atomicity across SQLite and the filesystem is claimed.** The module contract explicitly says
SQLite and files are separate stores and the lifecycle is at-most-once, not exactly-once
(`bot/attachments.py:1-70`).

### 2.5 Current reaper deletion conditions

`AttachmentReaper._TERMINAL` is exactly:

```python
{"delivered", "expired", "rejected", "failed"}
```

(`bot/attachments.py:1242-1250`).

For a batch in that set with a parseable `t0`, `_plan_batch` (`bot/attachments.py:1476-1538`):

1. lists items;
2. for each `pending`/`stored` item, marks it `reaped` via
   `Database.mark_attachment_item_reaped` (`bot/db.py:1580-1601`) **before** any unlink;
3. for an already-`reaped` item, schedules the unlink again (idempotent retry);
4. `_apply_cleanups` runs `_remove_file` (`bot/attachments.py:1689-1735`), which only unlinks a
   single regular file whose opaque token is inside the validated staging root; symlinks, foreign
   paths, and non-regular entries are refused.

`_mark_expired` (`bot/attachments.py:1460-1474`) calls the unconditional
`Database.mark_attachment_batch_status` (`bot/db.py:1309-1318`) to change `pending → expired`.
That unconditional update is a key design hazard: if a cancellation transition is added later, an
expiry path that already selected the batch must not overwrite `cancelled` with `expired`.

The reaper is invoked from the existing startup hook (`bot/app.py:245-259`) and the existing
`Watcher.tick` through `OpportunisticSweeper` (`bot/watcher.py:177-183`;
`bot/attachments.py:1749-1858`). There is no new reaper worker or scheduler.

### 2.6 Concurrency and duplicate handling

- Telegram updates are dispatched sequentially: `Application` is built with
  `concurrent_updates(False)` (`bot/app.py:77-93`) and `TelegramPoller.process_updates` awaits each
  `dispatch_and_wait` before the next (`bot/polling.py:155-178`).
- `dedupe_update` (`bot/handlers.py:490-570`) checks `processed_updates` before handlers run; the
  actual “processed” row is written atomically with durable work (or with the update outcome).
- Outbox work is separate (`OutboxWorker`, `bot/outbox.py:672-695`; recovery at
  `bot/outbox.py:529-555`). Attachment intake does not enqueue outbox work.
- The reaper’s DB phase runs on the event loop; its filesystem tail runs on a worker thread
  (`AttachmentReaper.sweep_async`, `bot/attachments.py:1288-1305`). A cancellation handler can run
  while the reaper is in its filesystem tail, but by then the batch is already terminal; it is no
  longer an active batch.

---

## 3. Lifecycle and deletion-path analysis

### 3.1 State transitions (current)

| From | To | Trigger | Current code |
|---|---|---|---|
| (none) | `pending` | first accepted file | `accept_attachment_item_into_new_batch`, `bot/db.py:1910-1985` |
| `pending` | `pending` | additional file | `accept_attachment_item`, `bot/db.py:1862-1908` |
| `pending` | `intent_recorded` | eligible accompanying text | `record_attachment_intent`, `bot/db.py:1700-1790` |
| `pending` | `expired` | reaper TTL | `_mark_expired` → `mark_attachment_batch_status` |
| `pending` | `expired` | new file after old pending expired | `AttachmentService.accept`, `bot/attachments.py:1083-1089` |
| `intent_recorded` | (remote states) | future Stage B; no current production transition | — |
| `delivered`/`expired`/`rejected`/`failed` | no status change | terminal result | reaper/clearance |
| `expired`/`rejected` | no status change | explicit clearance marker in `settings` | `clear_attachment_terminal_batch`, `bot/db.py:1447-1515` |

`dispatching` and `uncertain` are accepted statuses but have no current production transition;
they are treated as unresolved and skipped by the reaper (`bot/db.py:148-155`;
`bot/attachments.py:1349-1358`).

### 3.2 Every path that can delete attachment bytes

| Path | What it can delete | Protection / relevance |
|---|---|---|
| `AttachmentReaper._sweep_db_phase` + `_plan_batch` + `_apply_cleanups` | bytes of terminal (`delivered`/`expired`/`rejected`/`failed`) batches | DB-first `reaped` CAS, then `_remove_file`; no cancelled concept today |
| `AttachmentReaper._mark_expired` | no bytes directly; makes a batch terminal so step 2 can delete | unconditional status update is a race hazard |
| `AttachmentReaper._plan_orphan_items` | bytes of items whose batch row is missing | orphan cleanup only; cancellation must not delete the batch row |
| `StagingStore._store_write` / `_store_finalize` | partial/rejected **newly written** file | existing fail-closed cleanup; not a persisted batch deletion, but relevant to an in-flight cancel |
| `StagingStore._write_to_path` exception path | partial new file | `_safe_unlink` on write failure |
| `_safe_unlink` on `_store_finalize` failure | new file when item cannot transition to `stored` | if cancellation wins mid-write, this would delete the new file unless cancellation serializes with the store |
| `AttachmentReaper._scan_root_untracked` | **nothing** | leaves untracked files and reports them |
| Mini App download (`bot/web/services.py:790-870`) | **nothing** | read-only; requires `pending` batch |
| `/attachments_clear` | **nothing** | only writes a settings marker; no file/row deletion |

### 3.3 Direct and indirect eligibility

A batch becomes reaper-eligible only if its status is one of `_TERMINAL` **and** its `t0` parses.
Indirectly, an active `pending` batch can become eligible by:

1. the reaper’s TTL path;
2. the accept path marking a previous expired pending batch `expired` before creating a new batch;
3. any future code that calls `mark_attachment_batch_status` with a terminal value;
4. any future status list/`_TERMINAL` change that accidentally includes `cancelled`.

A cancellation design must address all four. It must not rely on “the reaper currently doesn’t know
about `cancelled`” as an invariant; that must be explicit and tested.

---

## 4. Option comparison

### Option A — keep current `/cancel` behavior

**What it does:** clears `user_state` and records `durable_completed`; does not touch attachment
state.

**Safety:** no attachment deletion is caused by `/cancel` itself. However, the batch remains
`pending`; after the route is cleared, the owner’s next text is rejected as `route_mismatch`, and at
TTL the existing reaper may delete the bytes.

**Verdict:** **safe against immediate `/cancel` deletion, but not sufficient as a cancellation
mechanism.** It preserves data only for the remainder of the 15-minute TTL, leaves the owner blocked,
and gives a misleading success message. It should remain only as a fallback if the owner explicitly
declines a new lifecycle state.

### Option B — explicit durable `cancelled` state

**What it does:** adds `cancelled` as a durable batch status, stops routing/processing, excludes it
from the reaper, and defines eventual cleanup in the same decision.

**Strengths:** explicit state, idempotent transition, no file deletion, works with one SQLite owner,
no new worker.

**Risks:** if “cancelled” is added to `ATTACHMENT_BATCH_STATUSES` but not explicitly excluded from
the reaper/terminal logic, it can fail open or become deletable. If cleanup is bundled into the same
state, “stop processing” and “delete data” become one decision; that is exactly the conflation this
task is meant to avoid. It also leaves retention/cleanup semantics undefined unless separately
specified.

**Verdict:** technically viable, but **less safe as a single decision** than Option C because it
does not force the cleanup boundary to be explicit.

### Option C — two-stage cancellation (recommended)

**Stage 1:** `pending → cancelled` only, durable, owner-scoped, idempotent, no deletion. `cancelled`
is a protected/non-reapable state. The owner can continue with ordinary prompts; `/attachments`
shows the preserved cancelled batch. No cleanup occurs.

**Stage 2:** a later, separately authorized owner decision defines whether/how a `cancelled` batch
may ever be cleaned up. Stage 2 is **not implemented or authorized by this document**. It requires
its own confirmation, retention rule, and DB-first/idempotent implementation. Until then, cancelled
bytes are preserved indefinitely.

**Strengths:** prevents accidental deletion; separates stopping work from cleanup; preserves bytes,
items, identity evidence, and rows; uses the existing SQLite owner and existing `/cancel` command;
no new worker, scheduler, or table; no schema migration; deterministic tests are possible.

**Verdict:** **recommended.**

### Why not a fourth alternative?

A filesystem-only quarantine (rename/move files) or a separate cancellation worker was considered
and rejected on code evidence: the existing architecture has one SQLite owner
(`bot/db.py:558-590`), the reaper deliberately does not touch the DB from its worker thread
(`bot/attachments.py:1390-1423`), and the project forbids introducing a new worker/ownership model.
A quarantine would also require a new durable mapping and would not remove the need for a DB state
and reaper exclusion.

---

## 5. Recommended state-transition model

### 5.1 Stage 1 states

Add application status:

```text
cancelled
```

Add it to `ATTACHMENT_BATCH_STATUSES` so `has_unknown_attachment_batch_status` accepts it. Add a
separate protected set, for example:

```text
ATTACHMENT_BATCH_NON_REAPABLE_STATUSES = frozenset({"cancelled"})
```

Do **not** add `cancelled` to `_TERMINAL`, `ATTACHMENT_BATCH_CLEARABLE_STATUSES`, or
`ATTACHMENT_BATCH_UNRESOLVED_STATUSES`.

### 5.2 Allowed transition

| From | To | Condition | Side effects |
|---|---|---|---|
| `pending` | `cancelled` | owner matches; exactly one active `pending` batch matches the current `route` conversation; `update_id` not already processed; CAS on `status='pending'` succeeds | set status/updated_at; clear route; record `durable_completed` in the same transaction; **no** item/file/identity change |

All other source statuses are **not cancellable in Stage 1**:

- `intent_recorded` — durable local intent already exists; cancellation would require a separate
  owner decision about discarding intent and identity. Keep `UNRESOLVED`.
- `dispatching` / `uncertain` — remote outcome is unresolved; cancellation could hide an ambiguous
  operation. Keep `UNRESOLVED`.
- `delivered` / `expired` / `rejected` / `failed` — terminal; use the existing OD-01 policy only for
  `expired`/`rejected`; `delivered`/`failed` remain protected.
- unknown / corrupt — fail closed.

### 5.3 Idempotency and duplicate updates

- A repeated `/cancel` for an already-`cancelled` batch is a no-op success: do not change status,
  do not touch files, record the current update outcome only if it is new.
- A duplicate `update_id` already in `processed_updates` returns `duplicate`/no-op; the handler must
  not perform a second transition or overwrite an outcome.
- A second `/cancel` from a new update while the batch is `cancelled` may clear the route again and
  return “already cancelled”; it must not create a new state or delete anything.

### 5.4 Routing treatment

Recommended explicit routing state:

```text
AttachmentRoutingState.CANCELLED = "cancelled"
```

After unresolved/live/expired/terminal checks, if the owner has only cancelled batches, return
`CANCELLED`. `_handle_accompanying_text` must treat `CANCELLED` as **non-blocking** (`return False`)
so ordinary prompts are not permanently blocked by a batch the owner explicitly cancelled. This is
safe in Stage 1 because only `pending` batches (no identity evidence) are cancellable.

If the owner later authorizes cancellation of `intent_recorded`, the design must add a separate
`CANCELLED_ASSOCIATED`/identity-aware rule before that implementation; do not silently allow a
message with existing identity evidence to become a new prompt.

`TERMINAL_ASSOCIATED`, `TERMINAL_UNPROVEN`, `UNRESOLVED`, `MULTI_LIVE`, `EXPIRED_PENDING`, and
unknown states keep their current fail-closed behavior.

### 5.5 Stage 2 (not implemented)

A future Stage 2 must be a separate owner decision. A safe shape would be:

1. an explicit owner command naming one `cancelled` batch plus `confirm`;
2. owner and status re-checked inside `BEGIN IMMEDIATE`;
3. a durable cleanup-eligibility marker (for example a `settings` key) written atomically;
4. DB-first item `reaped` transition, then idempotent file unlink, with `absent` treated as success;
5. no automatic reaper selection of `cancelled` merely because it is old.

No Stage 2 command, marker, retention period, or deletion is authorized by this document.

---

## 6. Race-condition and failure analysis

### 6.1 Scenario matrix

| Scenario | Required behavior | Residual limitation |
|---|---|---|
| `/cancel` arrives while attachment is being persisted | Cancellation and `store_async` share `StagingStore._accept_lock`. If cancel wins, `_store_prepare` must reject a non-`pending` batch before any write; no file is created. If store wins, it completes and stores bytes, then cancel marks `cancelled`; bytes remain. | A sync `StagingStore.store` caller that bypasses the production async path is not covered by the lock; `_store_prepare` status check is the fail-closed defense. |
| `/cancel` arrives after persistence but before outbox insertion | Attachment path never inserts outbox; cancel marks `cancelled`; no outbox row exists; no bytes deleted. | If a future Stage B introduces outbox work, cancellation must be disallowed once dispatch starts. |
| `/cancel` arrives while an outbox item is pending | Attachment lifecycle has no outbox item; unrelated outbox is untouched. | Future Stage B not covered. |
| `/cancel` arrives while outbox worker is processing | Same: no attachment outbox item; no interaction. If future remote dispatch is in progress, batch is `dispatching`/`uncertain` and not cancellable. | Future Stage B requires its own ambiguity policy. |
| Reaper selects a batch immediately before cancellation | Reaper’s `pending → expired` must be CAS. If reaper commits `expired` first, cancellation returns `not_eligible`/`too_late` and must not claim cancellation. If cancellation commits `cancelled` first, reaper’s CAS fails; the batch is not terminal and no items are planned for unlink. | A cancellation arriving after terminal commit cannot undo an already-authorized reaper decision; report “too late” honestly. |
| Cancellation commits but Telegram acknowledgement fails | DB state and update outcome are already durable. Reply failure is recorded as a handler failure/best-effort; no success claim; `/attachments` can show `cancelled`; redelivery is deduped. | No exactly-once delivery of the acknowledgement. |
| Cancellation acknowledgement succeeds but process crashes immediately afterward | State is `cancelled`; route is cleared; update outcome is durable; restart reaper skips it. | The user may not know until `/attachments`; no data loss. |
| Duplicate `/cancel` updates | `dedupe_update`/`processed_updates` prevents re-entry; the DB cancel method also checks `update_id` inside its transaction and is CAS/idempotent. | A duplicate handler call without the barrier is still a no-op. |
| SQLite returns BUSY/LOCKED | `BEGIN IMMEDIATE` waits up to `busy_timeout=5000`; on failure it raises, no success reply, no partial state. The update can be redelivered. | A transient failure may delay cancellation; no data deletion. |
| SQLite returns a permanent error | Fail closed: no success, no status change, no file deletion; record failure; manual inspection. | Cancellation unavailable until DB is repaired. |
| File exists but its DB record is missing | `_scan_root_untracked` leaves it and reports `untracked_left`; cancellation does not delete it. | Manual reconciliation. |
| DB record exists but its file is missing | Cancellation preserves the row; `cancelled` is excluded from the reaper. | Future Stage 2 must treat missing file as idempotent success. |
| Restart with a cancellation request in progress | If the transaction committed, `cancelled` persists and reaper skips it. If it did not commit, the batch remains `pending` and can be cancelled again or expire. | No separate “in-progress” durable state; the transaction is the boundary. |

### 6.2 In-flight persistence detail

Current `_store_prepare` (`bot/attachments.py:662-761`) checks ownership and conversation validity,
but not batch status. This is safe today only because no cancellation state exists. Stage 1 must add:

```text
if batch.status != ATTACHMENT_BATCH_PENDING:
    return StageResult(StageStatus.REJECTED_BATCH, ...)
```

before any file write. The `store_async` lock (`bot/attachments.py:881-923`) and the cancellation
path must use the **same** lock. That yields two safe orders:

- **Cancel first:** batch becomes `cancelled`; the later `store_async` sees non-`pending` and
  rejects before `_write_to_path`; no bytes are created.
- **Store first:** the write and `pending → stored` transition complete under the lock; cancellation
  then marks the batch `cancelled`; the stored file and item remain.

If the task runs the synchronous `store()` API, there is no async lock coverage; the new status check
in `_store_prepare` remains fail-closed, but a cancel that commits between `_store_prepare` and
`_store_finalize` could still cause `_store_finalize` to unlink the newly written file. The
implementation must either (a) keep production on `store_async`, as it is today, and document the
sync API as lower-level, or (b) add a shared lock/guard to the sync path. This design recommends
(a) plus a regression test that production wiring uses `store_async`.

### 6.3 Reaper CAS detail

Replace the production expiry transitions with a CAS:

```text
UPDATE attachment_batches
SET status = 'expired', updated_at = ?
WHERE batch_id = ? AND status = 'pending'
```

If `rowcount != 1`, the reaper must not plan items for deletion. The same CAS must be used by the
accept path when it retires an old pending batch (`bot/attachments.py:1083-1089`). The unconditional
`mark_attachment_batch_status` may remain for explicit tests/administrative code, but it must not be
used by the reaper or cancellation-adjacent lifecycle paths.

### 6.4 Database/filesystem boundary

Cancellation Stage 1 performs **no filesystem operation** and no row deletion. Therefore its SQLite
transaction is atomic on its own; no claim is made that SQLite and the filesystem are atomic. The
only filesystem effects in the whole lifecycle remain the existing store rejection unlinks and the
reaper unlinks. Stage 1 deliberately does not add a new unlink path.

---

## 7. Recommended design

### 7.1 `/cancel` behavior

When `/cancel` is invoked:

1. Read the current `awaiting_state`.
2. If `kind == "route"` and exactly one owner-owned `pending` batch exists for that
   `conversation_id`, attempt Stage 1 cancellation under the store’s acceptance lock.
3. If no matching batch exists, perform the current route clear/outcome transaction only.
4. If the batch is non-cancellable (`intent_recorded`, `dispatching`, `uncertain`, terminal,
   unknown), do **not** change its status; clear the route (current command semantics) and return a
   truthful message that the batch was not cancelled and where to inspect it.
5. If multiple matching `pending` batches exist, do not guess; cancel none and report ambiguity.
6. Reply only after the transaction returns; never claim success before commit.

Suggested Arabic response meanings (final wording can be chosen during implementation):

- cancelled: “اتلغى التوجيه، والدفعة اتلغت معالجة. الملفات محفوظة محليًا ومش هتتحذف تلقائيًا.”
- no batch: current “اتلغى التوجيه. ابعت /start للقائمة.”
- non-cancellable: “اتلغى التوجيه، لكن الدفعة مش قابلة للإلغاء دلوقتي (بدأت/انتهت). راجع /attachments.”
- ambiguous: “اتلغى التوجيه. فيه أكثر من دفعة نشطة؛ راجع /attachments.”
- DB failure: no success text; propagate/record failure.

The callback-button path must use the same service method and messages.

### 7.2 `/attachments` visibility

`attachments_list` (`bot/handlers.py:3006-3028`) already lists all owner batches. Stage 1 should
display `cancelled` explicitly and explain that it is preserved and not auto-deleted. Do not expose
`staging_token` or paths.

### 7.3 Reaper behavior

- `cancelled` is never in `_TERMINAL`.
- `_sweep_db_phase` explicitly enumerates cancelled batches and increments `skipped` (observability)
  without calling `_plan_batch`.
- `_plan_batch` has a defense-in-depth guard: a non-reapable status returns `SKIPPED` with reason
  `non_reapable`.
- `_mark_expired` uses CAS and reports a race rather than overwriting.
- No `mark_attachment_item_reaped` call for a cancelled batch.
- No deletion of batch rows, item rows, or identity evidence.
- Repeated sweeps/restart are idempotent and leave cancelled bytes intact.

### 7.4 Outbox behavior

No Stage 1 change. Attachment cancellation never creates, edits, or discards outbox rows. If a
future Stage B makes attachments outbox-driven, the cancellation state must be resolved before
enqueueing, or the batch must be `dispatching`/`uncertain` and non-cancellable.

### 7.5 Migration and compatibility

- **No schema migration** for Stage 1. `status` is `TEXT` with no CHECK constraint; adding a value is
  an application-level change.
- Existing rows remain valid.
- Older code that does not know `cancelled` sees an unknown status and fails closed (classification
  raises `AttachmentBatchIntegrityError`; reaper reports unknown and leaves it). This is preferable
  to silent deletion.
- If a cancellation timestamp/reason is later required, prefer a `settings` key over a new column;
  no such key is authorized now.

---

## 8. Reaper safety rules

1. `ATTACHMENT_BATCH_CANCELLED` must **not** be added to `AttachmentReaper._TERMINAL`.
2. Add an explicit non-reapable set and skip it in both `_sweep_db_phase` and `_plan_batch`.
3. Expiry must be `pending → expired` via CAS; never overwrite a non-`pending` status.
4. Never call `mark_attachment_item_reaped` for an item whose batch is `cancelled`.
5. Never delete `attachment_batches`, `attachment_items`, or `attachment_message_identity` rows
   during cancellation or cancelled cleanup design Stage 1.
6. Orphan cleanup may only operate when the batch row is actually absent; cancellation must not
   delete the row.
7. Leave untracked files in place and report them; do not infer ownership.
8. Keep `_remove_file`’s path/symlink/regular-file protections unchanged.
9. Tests must prove repeated sweeps and restart leave cancelled bytes/rows intact.

---

## 9. Recovery and retention policy

### 9.1 Recovery

- Cancellation is a single SQLite transaction; there is no partial “cancellation in progress” row.
- After restart, `cancelled` is a normal durable status; the startup reaper skips it.
- If the process dies before commit, the batch remains `pending`; `/cancel` can be retried, or the
  normal TTL path may expire it.
- If the process dies after commit but before the Telegram reply, the state is durable and
  `/attachments` is the source of truth; redelivery is deduped.
- If a file was never written, the item row remains `pending` in a `cancelled` batch; it is preserved
  for audit/Stage 2, not deleted.

### 9.2 Retention

Stage 1 retains cancelled batches, items, identity evidence, and files **indefinitely** until a
separate owner-authorized cleanup decision. This is intentional:

- no automatic deletion;
- no use of the existing destructive reaper;
- no extension of OD-01 clearance to `cancelled`;
- no new retention worker.

Operational consequence: cancelled files count toward the staging byte cap, so a long-lived
cancelled batch can reduce capacity. `/attachments` visibility and an owner decision for Stage 2 are
required; automatic eviction is not authorized.

---

## 10. Implementation scope for a later task

### 10.1 Likely files and functions

| File | Likely change |
|---|---|
| `bot/db.py` | Add `ATTACHMENT_BATCH_CANCELLED`; add to `ATTACHMENT_BATCH_STATUSES`; add non-reapable set; add `cancel_pending_attachment_batch`; add CAS helper for batch status; add owner-scoped cancelled query; add `AttachmentRoutingState.CANCELLED`; update `classify_attachment_routing`; keep OD-01 clearance unchanged |
| `bot/attachments.py` | Add `AttachmentService.cancel_pending_batch` using the existing `_accept_lock`; add status check in `_store_prepare`; add reaper `cancelled` skip/report; add CAS in `_mark_expired`; keep `_TERMINAL` unchanged |
| `bot/handlers.py` | Update `cancel_route` and `cancel_route_button` to call the service; update `/attachments` label; keep `/attachments_clear` policy unchanged |
| `tests/test_wp01_attachment_lifecycle.py` | Replace the current “cancel leaves pending” assertion with the authorized cancellation behavior; keep no-deletion/identity tests |
| `tests/test_wp01_active_batch_cancellation.py` (new) | Cancellation, CAS, reaper exclusion, in-flight persistence, restart, duplicate, DB failure, no-outbox tests |
| `tests/test_attachment_cleanup_expiration_a4.py` | Add cancelled-batch survival and CAS race tests |
| `docs/OPERATIONS_RUNBOOK.md` | Document `/cancel` cancellation, preserved data, no auto deletion, Stage 2 not implemented |

`bot/app.py`, `bot/web/*`, `docs/MINI_APP.md`, dependency files, lockfiles, and CI are **not**
expected to change for Stage 1.

### 10.2 Migration

**No schema migration.** Add a status constant only. Do not add a column or table for Stage 1.

### 10.3 Reaper and outbox changes

- Reaper: **required** (exclusion + CAS + tests).
- Outbox: **none** for Stage 1.

### 10.4 User-facing commands

- `/cancel` remains the entry point.
- `/attachments` shows `cancelled`.
- `/attachments_clear` remains restricted to `expired`/`rejected`; do not extend it to `cancelled`
  without a new owner decision.
- No new command is required for Stage 1; an explicit `/attachments_cancel` is an open owner choice.

### 10.5 Acceptance criteria

1. `/cancel` with exactly one matching active `pending` batch transitions it to `cancelled`, clears
   the route, and records a durable outcome atomically; no file/item/identity row is deleted.
2. `/cancel` with no matching batch, multiple matching batches, or a non-cancellable status changes
   no attachment status and returns a truthful response; no false success.
3. In-flight persistence is safe: cancel-first creates no file; store-first preserves the file and
   item; cancellation never unlinks a persisted attachment.
4. Reaper never selects, marks, or deletes a `cancelled` batch; repeated sweeps and restart leave its
   bytes/rows intact; CAS prevents `pending → expired` from overwriting `cancelled`.
5. Duplicate `/cancel`, duplicate `update_id`, BUSY/LOCKED, and permanent DB errors are idempotent or
   fail closed; no success is reported before commit.
6. Existing terminal invariants and OD-01 clearance are unchanged: only `expired`/`rejected` can be
   cleared; `delivered`/`failed`/`TERMINAL_ASSOCIATED`/`TERMINAL_UNPROVEN` remain protected.
7. No outbox row, remote call, Mini App change, new worker, or schema migration is introduced.
8. `/attachments` and the runbook accurately describe preserved cancelled data and the absence of
   automatic cleanup.

### 10.6 Explicitly excluded behavior

- No implementation in this task.
- No deletion of any existing attachment file, row, or identity.
- No automatic cleanup/retention worker.
- No `cancelled` in `_TERMINAL` or OD-01 clearable set.
- No schema migration or new table.
- No outbox change.
- No Stage B remote upload/dispatch.
- No Mini App or `bot/web` change.
- No WP-06, WP-07 concurrency, WP-01 closure, or owner acceptance.
- No commit, push, PR, merge, deployment, or Autopush.

---

## 11. Acceptance criteria for this design task

- Both required documents exist under `docs/reviews/`.
- Every cited path/function/status is verified against the current source.
- The recommendation is explicit and distinguishes Stage 1 from Stage 2.
- The reaper’s actual selection/deletion conditions are accurately described.
- No code, tests, dependencies, schema, database, reaper, outbox, or attachment files are modified.
- `git diff --check` passes.
- Both documents have recorded SHA-256 values.
- No implementation is claimed and WP-01 is not marked closed.

---

## 12. Open owner decisions

**None of these are approved by this document.**

1. **Authorize Stage 1 at all?** A new `cancelled` lifecycle state is a separate lifecycle decision;
   the prior WP-01 authorization (OD-01 Option C + OD-03 Option A) did not approve it.
2. **Cancellation scope:** `pending` only (recommended), or also `intent_recorded`? The latter needs
   an identity-aware routing rule and a decision about discarding durable local intent.
3. **`dispatching`/`uncertain`:** confirm they remain non-cancellable until remote reconciliation.
4. **Entry point:** should `/cancel` cancel a matching pending batch (recommended), or should a new
   explicit `/attachments_cancel <batch_id> confirm` be required? Or both?
5. **Ambiguity:** when multiple pending batches exist, should `/cancel` cancel none and require
   `/attachments`, or cancel the batch matching the current route only?
6. **Stage 2 cleanup:** whether any cleanup will ever be allowed, after what retention period, and
   with what explicit confirmation. No automatic cleanup is authorized.
7. **Visibility:** whether cancelled batches should appear in `/attachments` only, or also in a
   separate operator report. The Mini App currently hides non-`pending` batches
   (`bot/web/services.py:842-870`); changing that would touch the frozen Mini App boundary and needs
   separate approval.
8. **Cancellation metadata:** whether `updated_at` is sufficient or a separate cancellation
   timestamp/reason is required. Stage 1 recommends no schema change.

---

## 13. Explicit non-goals

This document does **not**:

- implement cancellation or any code/test change;
- delete, move, rename, quarantine, or clean any attachment file;
- delete any SQLite row or change schema/data;
- add `cancelled` to the existing destructive reaper;
- extend OD-01 clearance to `cancelled`;
- change OD-01 or OD-03;
- add an outbox, worker, scheduler, or second database owner;
- implement Stage B remote upload;
- change the Mini App or `bot/web`;
- start WP-06 or unrelated WP-01 work;
- record owner approval on the owner’s behalf;
- claim WP-01 closure or independent review.

**Current WP-01 status remains `DONE_WITH_NOTES` for its authorized scope only; active-batch
cancellation remains a separate, unapproved lifecycle decision.**
