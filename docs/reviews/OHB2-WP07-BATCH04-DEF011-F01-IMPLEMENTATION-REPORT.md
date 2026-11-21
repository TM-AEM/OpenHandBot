# OHB2 — WP-07 / DEF-011 / F-01 — Implementation Report

**Task ID:** `OHB2-WP07-BATCH04-DEF011-F01-REAPER-FILESYSTEM-OFFLOAD`
**Date:** 2026-11-19
**Final status:** **DONE (implementation + local verification)** — independent review and owner acceptance are **NOT** claimed.

| Dimension | Status |
|---|---|
| Implementation of F-01 | **DONE** |
| Local verification (tests + static analysis) | **DONE** — all gates green |
| Independent external review | **NOT PERFORMED** — no reviewer-session/environment independence established |
| Owner acceptance | **NOT CLAIMED** |
| WP-09 Python 3.11 matrix | **UNVERIFIED** — only Python 3.13.15 available, no push ⇒ no CI |

---

## 1. Initial Git baseline and final Git state

### 1.1 Baseline (recorded before any edit)

| Item | Value |
|---|---|
| Repository root | `/workspace/project/OpenHandBot` |
| Branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` |
| HEAD | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` (== `origin/main`) |
| Staged | 0 |
| Modified (tracked) | 8 |
| Untracked | 37 |
| Python | 3.13.15 (`.venv`), no 3.11 / 3.12 interpreter present |
| Node | v24.22.2 |

Tracked modifications present at start (**pre-existing user work, not mine**):
`.agent/PROGRESS.md`, `bot/app.py`, `bot/attachments.py`, `bot/db.py`,
`bot/handlers.py`, `bot/watcher.py`, `tests/test_handlers.py`,
`tests/test_sw06_unwatch_db_failure_propagation.py`.

### 1.2 Final state

| Item | Value |
|---|---|
| Branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` (unchanged) |
| HEAD | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` (unchanged) |
| Staged | **0** (nothing staged) |
| Modified (tracked) | **8** (unchanged — no new tracked file modified) |
| Untracked | **40** (37 → 40: my 3 new files — `tests/test_f01_reaper_fs_offload.py`, the implementation report, and the review-package README). `tests/test_def011_fs_offload.py` was already untracked before this task. |
| Commits / push / PR | **none** |

No `git reset`, `git clean`, force operation, broad deletion, `git add .`, or
`git add -A` was executed at any point.

---

## 2. F-01 root cause and exact fix

### 2.1 Root cause (before)

`sweep_async()` offloaded only `_sweep_fs_tail` (root scan) to a worker thread.
The **actual byte deletion** — `_remove_file()` (`os.lstat` + `os.unlink`) — was
invoked from inside `_sweep_db_phase()`, which runs on the event-loop thread:

```
sweep_async()                      [event loop]
  └─ _sweep_db_phase()             [event loop]   ← DEFECT
       ├─ _sweep_batch()           → _remove_file()  ×2   (lstat + unlink on loop)
       └─ _sweep_orphan_items()    → _remove_file()  ×2   (lstat + unlink on loop)
  └─ to_thread.run_sync(_sweep_fs_tail)   [worker]  ← only iterdir/lstat of root
```

Measured before the fix (400 staged files): DB phase **241.5 ms on the loop** vs
FS tail **0.1 ms off-loop**; event-loop heartbeat gap **244.7 ms**.
Reachable in production from `bot/app.py:241` (startup) and `bot/watcher.py:183`
(every watcher tick).

### 2.2 Fix (after)

The DB phase now produces **decisions only** and appends them to a `SweepPlan`;
the actual filesystem deletion is executed by `_apply_cleanups()` inside
`_sweep_fs_tail()`, i.e. on the worker thread. Aggregation happens afterwards on
the loop thread with **no DB and no disk access**.

```
sweep_async()                          [event loop]
  └─ _sweep_db_phase(plan)             [event loop]  ← DB ONLY, no disk
       ├─ _plan_batch()        → marks item `reaped` (CAS) + plan.cleanups.append(...)
       └─ _plan_orphan_items() → marks item `reaped` (CAS) + plan.cleanups.append(...)
  └─ to_thread.run_sync(_sweep_fs_tail(plan))   [worker]
       ├─ _apply_cleanups(plan)  → _remove_file()  (lstat + unlink)   ← moved here
       ├─ _scan_root_untracked()
       └─ _count_unsafe_entries()
  └─ _finalize(plan)                   [event loop]  ← pure arithmetic, no DB/disk
```

New/changed structures in `bot/attachments.py`:

| Symbol | Kind | Purpose |
|---|---|---|
| `FileCleanup` | new dataclass | one DB-decided, not-yet-executed byte deletion (`token`, `batch_id`, `item_id`, `result`) |
| `BatchPlan` | new dataclass | per-batch DB decision; outcome computed after deletion |
| `SweepPlan` | new dataclass | `cleanups` + `batches` + `immediate` + `orphans_left` |
| `_sweep_db_phase(..., plan)` | signature | now DB-only; appends decisions to `plan` |
| `_plan_batch()` | new (was `_sweep_batch`) | DB decisions only; no `_remove_file` |
| `_finish_batch()` | new | converts decision + deletion results into `BatchSweepResult` |
| `_plan_orphan_items()` | new (was `_sweep_orphan_items`) | DB decisions only; no `_remove_file` |
| `_apply_cleanups()` | new | executes `_remove_file` — worker thread only, no DB |
| `_finalize()` | new | aggregates results — loop thread, no DB, no disk |

### 2.3 Ordering preserved (requirement 3)

The DB decision (`mark_attachment_item_reaped`, a CAS) still happens **before**
any byte deletion. `_plan_batch`/`_plan_orphan_items` mark `reaped` and append
to `plan.cleanups`; `_apply_cleanups` runs strictly later. A file is never
deleted before the DB has safely recorded the cleanup intent.

### 2.4 Behaviour preserved (requirement 4)

| Case | Behaviour | Evidence |
|---|---|---|
| Missing file | `absent` → counted `reconciled` → `CLEANED` (pre-existing semantics, unchanged) | `test_F01_missing_file_is_absent_and_idempotent` |
| Successful deletion | `deleted` → `files_deleted` incremented | `test_F01_remove_file_runs_on_worker_thread` |
| Filesystem error (`OSError`) | `retry` → `PARTIAL`/`RETRY`, file left in place | `test_F01_filesystem_error_maps_to_retry` |
| Database error on mark | `retry`, **no** byte deletion (fail-closed) | `test_F01_database_error_maps_to_retry_and_no_deletion` |
| Repeated cleanup / recovery | idempotent, no errors, re-reaps leftovers | `test_F01_missing_file_is_absent_and_idempotent` |
| Orphan cleanup (no parent batch) | deleted off-loop; `retry` counts toward `orphans_left` | `test_F01_orphan_cleanup_also_off_loop` |

### 2.5 SQLite ownership preserved (requirement 5)

The `Database` connection is never passed to the worker. `_sweep_fs_tail` /
`_apply_cleanups` touch no `self._db`. All SQL runs in `_sweep_db_phase` on the
owner (event-loop) thread. Verified by
`test_F01_sqlite_never_called_from_worker_thread` (0 off-loop DB calls).

### 2.6 Synchronous API contract (requirement 6)

`sweep()` (synchronous) is preserved unchanged in behaviour: it still performs
DB work and filesystem deletion on the **caller's** thread. Its docstring now
states this honestly (it does **not** claim to be non-blocking) and points
callers to `sweep_async()`.

---

## 3. Thread-identity evidence

Measured on the live tree after the fix (`/tmp/p11.py`, 300 staged files):

```
deleted: 300
filesystem calls ON the loop thread: {'lstat': 0, 'unlink': 0, 'open': 0, 'iterdir': 0}
VERDICT: no FS on loop
```

`_remove_file` thread identity (`/tmp/p9.py`, 400 files):

```
deleted=400
_remove_file: calls=400  on_loop_thread=0
total time inside _remove_file (lstat+unlink): 40.2 ms  (0.100 ms/file)
```

**Before** the fix, the same probes reported `_remove_file` on the loop thread
and a 241–249 ms event-loop stall. **After** the fix, 0 filesystem calls and 0
`_remove_file` calls occur on the loop thread.

> Note: the residual ~200 ms event-loop gap in a 400-file sweep is the
> **synchronous SQLite DB phase** (400 CAS transactions) on its owner thread.
> That is a separate concern (DB batching), not F-01, and is out of scope here.

---

## 4. Startup and watcher call-path evidence

| Path | Code | Path taken | Test |
|---|---|---|---|
| Startup | `bot/app.py:241` — `await reaper.sweep_async(...)` | async → worker | `test_F01_startup_path_uses_safe_async_sweep` |
| Watcher tick | `bot/watcher.py:183` — `await self._opportunistic_sweeper.maybe_sweep_async()` → `sweep_async` (`bot/attachments.py:1787`) | async → worker | `test_F01_watcher_path_uses_safe_async_sweep` |

Both production entry points use the asynchronous path, so both are covered by
the off-loop guarantee.

---

## 5. Regression tests

New file: **`tests/test_f01_reaper_fs_offload.py`** — 13 tests.

| Test | Proves |
|---|---|
| `test_F01_remove_file_runs_on_worker_thread` | every `_remove_file` call runs off the loop thread |
| `test_F01_os_lstat_and_unlink_run_off_loop` | `os.lstat` and `os.unlink` never run on the loop |
| `test_F01_no_filesystem_syscall_on_loop_during_sweep` | `lstat`/`unlink`/`open`/`iterdir` all 0 on the loop |
| `test_F01_mutation_remove_file_back_in_db_phase_is_detected` | **mutation**: moving deletion back into the DB phase makes the test fail |
| `test_F01_db_phase_performs_no_file_deletion` | `_sweep_db_phase` performs zero deletions, still marks `reaped` |
| `test_F01_db_phase_marks_reaped_before_any_deletion` | DB mark strictly precedes any FS delete |
| `test_F01_startup_path_uses_safe_async_sweep` | startup path deletes off-loop |
| `test_F01_watcher_path_uses_safe_async_sweep` | watcher path deletes off-loop |
| `test_F01_sqlite_never_called_from_worker_thread` | no SQLite call from a worker thread |
| `test_F01_missing_file_is_absent_and_idempotent` | missing-file + repeat-sweep semantics preserved |
| `test_F01_filesystem_error_maps_to_retry` | `OSError` → `retry`, file retained |
| `test_F01_database_error_maps_to_retry_and_no_deletion` | DB failure → `retry`, no deletion |
| `test_F01_orphan_cleanup_also_off_loop` | orphan deletions also off-loop |

### 5.1 Discriminating power (mutation proof)

The new tests were executed against the **pre-fix** `attachments.py` (restored
byte-exactly from the Batch-03 snapshot, SHA-256 `e72745eb9d628c20…`) in an
isolated copy at `/tmp/mut1`:

```
8 failed, 5 passed in 1.05s
```

The 8 failures are exactly the F-01 defect detectors (including the mutation
test). The 5 that pass on both versions are the *preserved-semantics* tests
(ordering, SQLite ownership, missing-file, FS-error, DB-error) — which is the
correct, intended result: they guard against regression, not against F-01.

---

## 6. Validation commands, counts and exit codes

All commands run with `/workspace/project/OpenHandBot/.venv/bin/python`.

| # | Gate | Command | Result | Exit |
|---|---|---|---|---|
| 1 | F-01 focused | `pytest -q tests/test_f01_reaper_fs_offload.py` | **13 passed** | 0 |
| 2 | DEF-011 focused | `pytest -q tests/test_def011_fs_offload.py` | **21 passed** | 0 |
| 3 | WP-07 focused | `pytest -q tests/test_wp07_*.py tests/test_def011_fs_offload.py tests/test_f01_reaper_fs_offload.py` | **134 passed** | 0 |
| 4 | Full suite | `pytest -q -p no:cacheprovider` | **3419 passed, 0 failed** (baseline 3406 + 13) | 0 |
| 5 | pyflakes | `python -m pyflakes bot/ automation/ tools/ main.py tests/` | **0 findings** | 0 |
| 6 | bandit (High) | `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | **High: 0** | 0 |
| 7 | Node/frontend | `node --test tests/frontend/*.test.js` | **280 pass / 0 fail** | 0 |
| 8 | Doc parity | `pytest -q tests/test_doc_code_parity.py` | **6 passed** | 0 |
| 9 | Mutation | F-01 tests vs pre-fix `attachments.py` | **8 failed / 5 passed** (expected) | 1 |

Frontend files were **not** modified (verified: 0 changed paths matching
`frontend` / `miniapp` / `mini_app`).

### 6.1 Pre-existing failures

None. The full suite is **0 failed** before and after this change.

### 6.2 Not verified

- **WP-09 — Python 3.11 matrix: `UNVERIFIED`.** Only Python 3.13.15 is
  installed (`/usr/local/bin/python3.13`); no 3.11 or 3.12 interpreter exists.
  Nothing was pushed, so no CI run exists either. This is **not** a PASS.

---

## 7. Changed-file inventory

### 7.1 Implementation (1 file)

| File | Change |
|---|---|
| `bot/attachments.py` | F-01 fix: DB phase returns decisions (`SweepPlan`), deletion moved into `_apply_cleanups` (worker thread), `_finalize` aggregates on loop. Docstrings corrected for `sweep()` and `maybe_sweep_async()`. |

Delta vs the pre-fix snapshot: **+162 / −65 lines** (`/tmp/f01.diff`).

> The `git diff` figure for this file (386 insertions / 103 deletions) is larger
> because it also contains **pre-existing uncommitted user work** that was
> present before this task began. The F-01 delta alone is the 162/65 above.

### 7.2 Tests (2 files)

| File | Change |
|---|---|
| `tests/test_f01_reaper_fs_offload.py` | **new** — 13 F-01 regression tests |
| `tests/test_def011_fs_offload.py` | **signature compatibility only** — `spy(known, report)` → `spy(known, report, plan)`. Zero assertions added, removed, or weakened. |

### 7.3 Documentation (1 file)

| File | Change |
|---|---|
| `docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md` | this report |

---

## 8. Preservation verification

| Check | Result |
|---|---|
| `bot/app.py`, `bot/db.py`, `bot/handlers.py`, `bot/watcher.py` | byte-identical to the Batch-03 snapshot — **UNCHANGED** |
| `tests/test_handlers.py`, `tests/test_sw06_unwatch_db_failure_propagation.py` | byte-identical to the Batch-03 snapshot — **UNCHANGED** |
| Pre-existing tracked modifications (8) | preserved, count unchanged |
| Pre-existing untracked files (37) | preserved; only **+3** (my new test file + 2 new reports) |
| `.openhands/`, `.agent/` | untouched (`.agent/PROGRESS.md` pre-existing modification left alone) |
| Mini App / frontend | untouched |
| Staged / committed / pushed | nothing |

---

## 9. Explicit outstanding findings

| ID | Status | Notes |
|---|---|---|
| **F-02** | **OPEN / NOT FIXED** | On cancellation, `_accept_lock` is released while the worker thread is still writing (`lock.locked()=False`, worker still active), breaking the "sequential admission" invariant. `store_async`'s `async with self._accept_lock` at `bot/attachments.py:898` is unchanged by this task. Cap remains fail-closed. Out of scope per the task's "do not fix F-02" instruction. |
| **DEF-011 A** (quota / reservation ledger) | **OPEN / NOT IMPLEMENTED** | Blocked by D-12 / OD-04 owner decision. Out of scope. |
| **DEF-011 C** (attachment UX copy) | **OPEN / NOT IMPLEMENTED** | Owned by WP-01 (OD-01 / OD-03). Out of scope. |
| **WP-09 Python 3.11 matrix** | **UNVERIFIED** | No 3.11 interpreter; no CI (nothing pushed). |
| **F-03** (stale acceptance doc claiming "0 `to_thread`") | **OPEN / NOT FIXED** | Batch-03 DOC-01; not part of this task. |
| Residual ~200 ms loop gap in large sweeps | **NOTED, NOT FIXED** | This is the synchronous SQLite DB phase on its owner thread, not F-01. Would require DB batching — a separate decision. |

> **⚠ LATER CORRECTION — 2026-11-21 (append-only; the historical F-03 row above is unchanged).**
> The **F-03** row above ("**OPEN / NOT FIXED**") was accurate when this report was written on
> **2026-11-19**; it is now **SUPERSEDED**. F-03 (the stale acceptance documents claiming
> "0 `to_thread`") was subsequently corrected with dated, additive supersession notices and guarded by
> parity tests, and it then passed a **genuinely independent review** with the verdict
> **`F03_REVIEW_PASS`** — see
> `docs/reviews/OHB2-WP07-DEF011-F03-GENUINELY-INDEPENDENT-REVIEW-REPORT.md`.
>
> This correction closes **only the F-03 documentation remediation**; it does not close `DEF-011`.
> **`DEF-011` as a whole remains OPEN.** `DEF-011-A` (quota reservation ledger) and `DEF-011-C`
> (attachment acceptance UX copy) remain **NOT IMPLEMENTED**, and `D6` (repeated raw cancellation during
> drain) remains **deferred**. The historical F-03 row is preserved unchanged above as a historical
> record.

Unchanged blockers carried forward: DEF-006, DEF-013, NEW-DEF-03, NAV-01..06,
WP-05, WP-06, WP-08 were **not** modified by this task.

---

## 10. Review package

Built outside the repository:

| Item | Value |
|---|---|
| Directory | `/workspace/review-packages/OHB2-WP07-BATCH04-DEF011-F01-20261119/` |
| Archive | `/workspace/review-packages/OHB2-WP07-BATCH04-DEF011-F01-20261119.tar.gz` |
| Archive checksum (authoritative) | `/workspace/review-packages/OHB2-WP07-BATCH04-DEF011-F01-20261119.tar.gz.sha256` |
| Manifest | `MANIFEST.sha256` — **8/8 entries verified OK** (re-checked from a fresh extraction) |
| Contents | post-fix `bot/attachments.py`; `tests/test_f01_reaper_fs_offload.py`; `tests/test_def011_fs_offload.py`; implementation report; Batch-03 handoff report; DEF-011 audit + plan + corrected baseline; package README |

The archive's own hash is deliberately kept **outside** the archive (a
self-referential hash cannot be valid), in the sidecar `.sha256` file next to it.

Reproduce:

```sh
cd /workspace/review-packages
sha256sum -c OHB2-WP07-BATCH04-DEF011-F01-20261119.tar.gz.sha256
tar xzf OHB2-WP07-BATCH04-DEF011-F01-20261119.tar.gz
cd OHB2-WP07-BATCH04-DEF011-F01-20261119 && sha256sum -c MANIFEST.sha256
```

Package README (with the independent-reviewer checklist):
`docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-REVIEW-PACKAGE.md`.

> **No independent review has been performed.** No reviewer session or
> environment independence was established in this task. Building a package is
> a prerequisite for such a review, **not** evidence of one.

---

## 11. Status distinction (explicit)

| Level | State |
|---|---|
| **Implementation complete** | **YES** — F-01 fixed in `bot/attachments.py` |
| **Local verification** | **YES** — 3419 pytest passed / 0 failed, pyflakes 0, bandit High 0, node 280/0, doc parity 6 |
| **Independent review** | **NO** — not established, not claimed |
| **Owner acceptance** | **NO** — not requested, not claimed |
| **Closure of DEF-011** | **NO** — parts A and C remain open; only the F-01 offload defect is fixed |
