# OHB2 — WP-07 / DEF-011 Implementation Plan

**Task ID:** `OHB2-WP07-DEF011-REMEDIATION-AUDIT-AND-IMPLEMENTATION-PLAN`
**Date:** 2026-11-19
**Status:** **PLAN ONLY — NOT AUTHORIZED, NOT IMPLEMENTED**
**Recorded by:** AI agent (OpenHands) on behalf of the repository owner.

> ## ⚠ No implementation is authorized by this document
>
> Nothing here has been executed. No production code, test, or schema change exists.
> **Stop and wait for explicit owner authorization before implementing any phase.**

---

## 1. Scope definition

### 1.1 In scope (this plan)

**Sub-defect B only** — move blocking filesystem I/O off the asyncio event loop in:

| # | Location | Operation |
|---|---|---|
| B-1 | `StagingStore._write_to_path` (`bot/attachments.py:612-644`) | `os.open` / `write` / `flush` / `os.fsync` |
| B-2 | `StagingStore._read_head` (`:352-355`, called `:757`) | content head re-read for magic-byte validation |
| B-3 | `AttachmentReaper.sweep` (`:1062-1148`) | `lstat` / `unlink` / `iterdir` filesystem walk |
| B-4 | `_read_local_capped` (`bot/handlers.py:1999-2012`) | local Bot-API file read (optional, lower priority) |

### 1.2 Explicitly OUT of scope

| Excluded | Reason |
|---|---|
| **Sub-defect A** (reservation ledger) | Dormant while dispatch is sequential; requires OD-04 Option B to be meaningful; must be inert by default under D-12. **Separate owner decision.** |
| **Sub-defect C** (UX copy) | Owned by **WP-01**, which is fully blocked on OD-01 + OD-03 + pre-change inventory. |
| Any schema/migration change | Not required — the ledger is in-process; 17 tables preserved. |
| `bot/app.py` / `bot/polling.py` | Not touched (DEF-006 / OD-04 boundary). |
| Mini App (`bot/web/*`) | Prohibited. |
| New dependencies | Not needed — `anyio==4.16.0` and `starlette==1.3.1` are already pinned in `requirements.txt`. |
| NAV-01..06 / WP-05 / WP-06 Part 2 | Unrelated, no dependency. |

---

## 2. Remediation options (Phase 6)

### Option 1 — Offload only the pure-I/O region with `anyio.to_thread.run_sync` ⭐ RECOMMENDED

**Approach.** Split each blocking function into a *pure file-operation* inner function and keep all
SQLite access on the loop thread.

**Files and functions:**

| File | Change |
|---|---|
| `bot/attachments.py` | Extract `_write_to_path_sync(path, chunks, cap)` (existing body, unchanged) and make `_write_to_path` an `async def` wrapper: `await anyio.to_thread.run_sync(functools.partial(_write_to_path_sync, path, chunks, cap))`. `store()` becomes `async def` and `await`s it. |
| `bot/attachments.py` | Same treatment for `_read_head` → `async def _read_head_async`. |
| `bot/attachments.py` | `AttachmentReaper.sweep` — split into DB phase (on loop) + FS phase (offloaded). `maybe_sweep` becomes `async def`; `watcher.tick` `await`s it. |
| `bot/handlers.py` | `AttachmentService.accept` already `async`; change `self._store.store(...)` → `await self._store.store(...)`. |
| `bot/handlers.py` | `_read_local_capped` → offload via `run_in_threadpool` inside the existing async generator. |
| `bot/app.py` | Boot sweep call `reaper.sweep(...)` → `await reaper.sweep(...)` (inside the existing async `_post_init`). |

**Proposed behaviour.** Byte-identical results and identical exception/status contract. Only the
*execution thread* changes for file operations.

**Concurrency implications.** No new concurrency. `to_thread` uses the existing default executor.
Does **not** enable intra-batch parallelism and does **not** touch OD-04.

**SQLite implications.** **None** — every `self._db.*` call remains on the loop thread. This is the
central safety constraint (see audit §3.5).

**Resource/quota guarantees.** Unchanged. Quotas stay disabled by default (D-12).

**Failure/cancellation semantics.**
- `_safe_unlink` stays **inside** the thread function ⇒ a failed write still cleans up its partial
  file (audit §3.7).
- **[FACT — verified]** `anyio.to_thread.run_sync` defaults to `abandon_on_cancel=False`
  (signature checked on the installed `anyio==4.16.0`; `cancellable` is a deprecated alias with
  default `None`, falling back to `abandon_on_cancel=False`). This is the **desired** behaviour: the
  call waits for the thread to finish rather than abandoning it mid-write.
- **Do NOT pass `abandon_on_cancel=True`** — that would let cancellation abandon a half-written file
  while the thread continues, defeating the `except BaseException: _safe_unlink(path)` guard.
- Note the difference from raw `asyncio.to_thread`: on cancellation the underlying thread keeps
  running regardless, but `abandon_on_cancel=False` makes the awaiting task wait for completion, so
  state stays consistent.
- Exceptions propagate unchanged ⇒ `store()`'s existing `except OSError` / `_TooLargeError` /
  `_CollisionError` handling is preserved.

**Required tests.** See §4 (T-1 … T-8).

**Architectural risks.**
- **MEDIUM:** `store()` and `sweep()` change from sync to `async`. All call sites must be updated.
  Missing one ⇒ `RuntimeWarning: coroutine was never awaited` and a silent no-op. **Mitigation:**
  grep every call site; the audit already enumerated them (`attachments.py:956`,
  `attachments.py:1523`, `app.py:241`, `watcher.py:183`).
- **LOW:** thread-pool saturation if many attachments are processed at once — bounded in practice by
  the sequential poller.

**Migration requirements.** None.

**Dependencies / approvals.** Owner authorization to modify `bot/attachments.py`,
`bot/handlers.py`, `bot/app.py`, `bot/watcher.py`. **No OD-04, no D-12, no schema approval needed.**

**Complexity.** **MODERATE** — ~4 files, ~120-180 changed lines, mostly mechanical `async`/`await`
propagation plus one careful split per function.

---

### Option 2 — Keep `store()` synchronous; offload at the handler boundary

**Approach.** Wrap the whole `service.accept(...)` call in `to_thread` at `handlers.py:2201`.

**Why this is WRONG.** `accept()` calls `self._db.*` (authorization, batch classification, item
insertion, `try_mark_attachment_item_stored`). Wrapping it would execute **SQLite on a worker
thread** against a single shared `check_same_thread=False` connection with no lock — exactly what
baseline `:336` and `:687` forbid.

**Verdict: REJECTED.** Unsafe by construction.

---

### Option 3 — Offload the entire `store()` function, moving DB work inside a lock

**Approach.** Add a `threading.RLock` around `_conn` and run all of `store()` in a thread.

**Why this is wrong.**
- Introduces a **global lock across every DB operation** — a major architectural change to the
  single-owner model.
- Serializes the loop thread against worker threads ⇒ worse latency than today.
- `BEGIN IMMEDIATE` transaction state would be held across thread boundaries — fragile.
- Directly violates "preserve the architecture: one authoritative SQLite owner".

**Verdict: REJECTED.**

---

### Option 4 — Add the reservation ledger (sub-defect A) now

**Approach.** Implement an in-process async reservation ledger alongside Option 1.

**Why deferred.**
- **Unreachable:** with sequential dispatch, only one attachment runs at a time ⇒ no race to fix.
- **D-12 boundary:** an always-on ledger changes admission behaviour ⇒ implicit D-12 change without
  owner approval.
- **OD-04 dependency:** the ledger's value appears only under Option B concurrency, whose safety
  proof does not yet exist.

**Verdict: DEFERRED to OD-04.** Not rejected — correctly sequenced.

---

### Option 5 — Do nothing (accept the stall)

**Approach.** Document the ≤3 MiB stall as accepted.

**Why not.** The stall is real and affects the shared loop (polling + ASGI requests). `bot/web/download.py`
already establishes that this codebase considers loop-blocking file I/O unacceptable. Consistency
argues for fixing it.

**Verdict: NOT RECOMMENDED.**

---

## 3. Recommended option and ordered plan

# RECOMMENDATION: **Option 1**

Rationale (evidence-based):

1. It fixes the only *currently reachable* part of DEF-011 (audit §4.4).
2. It requires **no** owner decision that is not already satisfied — no OD-04, no D-12, no schema.
3. It mirrors an **existing, shipped pattern** in `bot/web/download.py` (`run_in_threadpool` for file
   I/O only).
4. It respects every architecture constraint (audit §5).
5. It adds **no dependency** (`anyio`/`starlette` already pinned).

### Ordered phases

| Phase | Work | Verification gate |
|---|---|---|
| **P0** | Record baseline: `pytest -q`, hashes of the 4 target files, `git status --short` | Baseline numbers captured |
| **P1** | Offload `_write_to_path` (B-1). Split into `_write_to_path_sync`; make `_write_to_path` async; make `store()` async; update `accept()` to `await`. | Full suite green; T-1/T-2/T-5/T-7 pass |
| **P2** | Offload `_read_head` (B-2) inside `store()` | Suite green; T-3 passes |
| **P3** | Offload the FS phase of `AttachmentReaper.sweep` (B-3); make `maybe_sweep` async; update `watcher.tick` and `app.py` boot call | Suite green; T-4/T-6 pass |
| **P4** | Offload `_read_local_capped` (B-4) | Suite green; T-8 passes |
| **P5** | Full gate + self-review of complete diff | All gates ≥ baseline |

**Each phase must be independently green.** If a phase regresses, revert only that phase's changes.

### Acceptance criteria

| # | Criterion | Evidence required |
|---|---|---|
| AC-1 | No blocking filesystem call executes on the event loop during `store()` or `sweep()` | Test measures loop latency during a 3 MiB write; assert no stall > threshold |
| AC-2 | The write genuinely executes on a non-loop thread | Test captures `threading.current_thread()` inside the write |
| AC-3 | **No SQLite call is made from a worker thread** | Test asserts `db._conn` accessed only from the loop thread (instrument or thread-name assertion in a DB method) |
| AC-4 | Behaviour, statuses, and exception contract unchanged | All existing attachment tests pass unchanged |
| AC-5 | Cancellation leaves no partial file | Test cancels mid-write; asserts file absent and status not `STORED` |
| AC-6 | No new dependency | `requirements.txt` diff empty |
| AC-7 | No schema change | 17 tables before and after; `db.py` schema block untouched |
| AC-8 | Quotas remain disabled by default | `StagingStore(db, path).quota_enabled is False` |
| AC-9 | Full suite ≥ baseline | `pytest -q` count not lower; pyflakes 0; bandit High 0; node 280/0 |

---

## 4. Test matrix (Phase 7)

> **These tests are NOT written in this task.** They are specified for the implementation phase.

| ID | Test | Behaviour it must prove |
|---|---|---|
| **T-1** | `test_store_write_offloads_from_event_loop` | A concurrent ticker task records timestamps while a 3 MiB write runs; max gap < a bounded threshold (e.g. 50 ms) ⇒ the loop was not blocked. |
| **T-2** | `test_write_executes_on_worker_thread` | The write function records `threading.current_thread().ident`; assert it differs from the loop thread ident. |
| **T-3** | `test_read_head_offloaded` | `_read_head` runs on a worker thread; magic-byte rejection still returns `REJECTED_TYPE`. |
| **T-4** | `test_sweep_offloads_filesystem_phase` | A sweep over N files does not block a concurrent ticker; expired items still become `expired` → `reaped` → unlinked. |
| **T-5** | `test_db_never_called_from_worker_thread` | A `Database` wrapper records the calling thread for every method; assert all calls come from the loop thread during `store()`. |
| **T-6** | `test_sweep_db_phase_stays_on_loop` | Same instrumentation applied to `sweep()`. |
| **T-7** | `test_cancel_during_write_leaves_no_partial_file` | Cancel the accept task mid-write; assert no file under the staging token, and status is not `STORED`. |
| **T-8** | `test_local_capped_read_offloaded` | The local Bot-API read path does not block the loop; `AttachmentTooLargeError` still raised past the cap. |
| **T-9** | `test_write_failure_maps_to_write_failed` | An `OSError` inside the thread still yields `StageStatus.WRITE_FAILED` (contract preserved). |
| **T-10** | `test_collision_still_rejected` | `O_EXCL` collision still yields `WRITE_FAILED` with `error="collision"`. |
| **T-11** | `test_quota_defaults_unchanged` | `quota_enabled is False` after the change (D-12 preserved). |
| **T-12** | `test_schema_table_count_unchanged` | Exactly 17 unique tables. |
| **T-13** | `test_duplicate_update_still_short_circuits` | A duplicate `update_id` returns `DUPLICATE` before any write (no regression). |
| **T-14** | `test_ack_semantics_unchanged` | Acceptance/acknowledgement outcomes are identical to baseline for the same inputs. |

### Existing coverage gaps this plan closes

| Gap | Closed by |
|---|---|
| No event-loop responsiveness assertion | T-1, T-4 |
| No offload proof | T-2, T-3, T-8 |
| No thread-affinity assertion for SQLite | T-5, T-6 |
| No cancellation-mid-write test | T-7 |

---

## 5. Dependencies and approvals

| Item | Status | Needed for |
|---|---|---|
| **Owner authorization to modify `bot/attachments.py`, `bot/handlers.py`, `bot/watcher.py`, `bot/app.py`** | **NOT GRANTED** | P1–P4 |
| **OD-04** | Unresolved — **NOT required** for Option 1 | Sub-defect A only |
| **D-12** | Defaults must stay `None` — **respected, no decision needed** | — |
| **OD-01 / OD-03** | Block WP-01 — **not required** | Sub-defect C only |
| **Schema approval** | **NOT required** — no schema change | — |
| **New dependencies** | **NOT required** | — |

**Conclusion:** Option 1 needs exactly **one** approval — owner authorization to edit the four files.

---

## 6. Rollback considerations

| Scenario | Rollback |
|---|---|
| A phase regresses the suite | Revert only that phase's edits (the plan is phase-isolated by function) |
| `async` propagation missed a call site | Symptom: `RuntimeWarning: coroutine ... never awaited` + attachment silently not stored. Detect via T-9/T-13 and a full-suite run; revert P1 |
| Thread-pool starvation observed | Revert P3 (largest FS phase) first, keep P1 |
| Unexpected SQLite thread error | Indicates AC-3 violated; revert immediately — this is the highest-severity failure mode |

**Non-destructive snapshot before P1:**

```bash
git stash create           # prints a commit SHA; does NOT modify working tree
sha256sum bot/attachments.py bot/handlers.py bot/watcher.py bot/app.py
```

**Never** use `git reset`, `git checkout --`, or `git clean` on pre-existing WP-07 work.

---

## 7. What this plan deliberately does not do

- It does **not** implement sub-defect A (ledger) — that is OD-04's decision.
- It does **not** implement sub-defect C (UX copy) — that is WP-01's, blocked on OD-01/OD-03.
- It does **not** enable any quota by default (D-12 preserved).
- It does **not** add concurrency or touch `concurrent_updates`/`process_updates` (OD-04 boundary).
- It does **not** change the schema or add dependencies.
- It does **not** claim DEF-011 is fixed — only that this plan would fix sub-defect B.

---

## 8. Definition of done (for the future implementation task)

1. AC-1 … AC-9 all satisfied with recorded evidence.
2. T-1 … T-14 written, passing, and **mutation-proven non-vacuous** (revert the offload ⇒ the test fails).
3. Full suite ≥ baseline; pyflakes 0; bandit High 0; node 280/0; doc parity green.
4. `git diff` reviewed: no schema change, no new dependency, no Mini App change, no WP-07 unrelated change.
5. `.agent/PROGRESS.md` updated with an honest status that names **sub-defect B only**.
6. No commit/push/PR without separate authorization.
