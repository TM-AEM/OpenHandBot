# OHB2 — WP-07 — DEF-011 — F-02 Cancellation / `_accept_lock` Race Investigation

**Task:** `OHB2-WP07-DEF011-F02-CANCELLATION-LOCK-RACE-INVESTIGATION`
**Date:** 2026-11-19
**Type:** investigation + test design only — **no source or test file was modified**
**Verdict:** **`F02_REPRODUCED_REMEDIATION_DESIGN_READY`**

> F-02 is **confirmed reproducible, deterministically**, and its impact is **narrower than the
> finding text implies** but real. A minimal, architecture-preserving fix is designed and
> **empirically validated in a throwaway harness**. No production or test file was changed; no
> owner decision record was touched.

---

## 1. Baseline

| Field | Value |
|---|---|
| HEAD | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| `origin/main` | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| Branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` |
| Divergence | `0 0` |
| Staged / Modified / Untracked / Ignored | **0 / 8 / 56 / 8** |
| `bot/attachments.py` | **modified in working tree** (DEF-011-B work), sha256 `d27fb79870d900f5…`, 1826 lines |
| Tracked in `origin/main`? | **YES** (baseline version differs) |

**Environment:** Python **3.13.15**, **anyio 4.16.0** (`requirements.txt` pins `anyio==4.16.0`),
pytest **9.0.3**, python-telegram-bot **22.8**.

**Existing tests in scope** (all passing, 118 tests across 4 files):
`tests/test_def011_fs_offload.py` (incl. `test_T7_cancel_during_write_never_claims_stored`),
`tests/test_attachment_staging_a1.py`, `tests/test_attachment_batch_lifecycle_a2.py`,
`tests/test_f01_reaper_fs_offload.py`.

Every pre-existing working-tree modification was preserved; `bot/attachments.py` hash is unchanged
by this task.

---

## 2. Code-path analysis

### 2.1 The critical section

`bot/attachments.py:898` — inside `StagingStore.store_async`:

```python
async with self._accept_lock:                       # line 898  (anyio.Lock, line 525)
    prep = self._store_prepare(...)                 # DB phase, event-loop thread
    if isinstance(prep, StageResult):
        return prep
    path, token, cap = prep
    wrote = await to_thread.run_sync(               # line 909  ← the await point
        functools.partial(self._store_write, path=path, chunks=chunks,
                          cap=cap, item_id=item_id, token=token)
    )                                               # abandon_on_cancel defaults to False
    if isinstance(wrote, StageResult):
        return wrote
    written, head = wrote
    return self._store_finalize(...)                # DB phase, event-loop thread
```

The lock is a **plain `async with`**. It is released when the coroutine exits the block — by
return, by exception, **or by cancellation**.

### 2.2 Answers to the required questions

| # | Question | Answer | Evidence |
|---|---|---|---|
| 1 | Does cancelling the awaiting coroutine terminate the worker operation? | **NO** | The thread is already running in the pool; `to_thread` cannot interrupt it. Only the *await* is abandoned. |
| 2 | Can the worker continue writing after the coroutine is cancelled? | **YES — proven** | Probe observed `worker still inside write = 1` immediately after `CancelledError`. |
| 3 | Can `_accept_lock` be released before the worker finishes? | **YES — proven** | `lock held = False` while `active writer = 1`. |
| 4 | Can a second acceptance overlap the first filesystem write? | **YES — proven** | `max_concurrent writers = 2`. |
| 5 | Can this produce duplicate files / inconsistent DB / quota violation / cleanup races? | **Partly** — see §3.3 | Duplicate files: **no** (distinct tokens). DB inconsistency: **no** (CAS guard). Quota bypass: **yes (only if quotas enabled)**. Orphan file after reap: **yes (transient)**. |
| 6 | Does the pending/reaper mechanism prevent or merely recover? | **Merely recovers**, and recovery is **deferred by one sweep** | §3.3 scenario B and §3.4. |

### 2.3 Root cause — precise

`anyio.to_thread.run_sync(..., abandon_on_cancel=False)` wraps the await in
`CancelScope(shield=True)` (`anyio/_backends/_asyncio.py`, `run_sync_in_worker_thread`). That shield
protects against **anyio cancel scopes** (`move_on_after`, `fail_after`, anyio task-group
cancellation) — it does **not** protect against a **raw `asyncio.Task.cancel()`**.

Measured directly, isolated from the project (3 runs each):

| Cancellation mechanism | Outcome | Elapsed | Shield |
|---|---|---|---|
| raw `asyncio.Task.cancel()` | `CancelledError` raised **immediately** | **0.00–0.02 s** | **BROKEN** |
| `anyio.move_on_after(0.05)` | returned normally | **10.00 s** (waited for the worker) | **HELD** |

**So:**
- Under **anyio-scope** cancellation, the shield already prevents F-02 — the lock is held until the
  worker returns.
- Under **raw asyncio task cancellation**, the shield is bypassed, the `async with` exits
  immediately, the lock is released, and the worker keeps writing.

**This distinction is the whole finding.** F-02 is a *raw-asyncio-cancellation* race, not a general
one.

### 2.4 Production reachability — honest assessment

| Question | Finding |
|---|---|
| Does PTB cancel handler tasks? | **No** — `telegram.ext._application` contains **0** `.cancel()` calls. |
| Does the poller dispatch concurrently? | **No** — `bot/polling.py:175` `dispatch_and_wait` is **sequential** (`update_queue.join()`), and `bot/app.py:74-82` documents this explicitly (OD-04 blocks intra-batch concurrency). |
| Any `wait_for`/`timeout` around `accept`? | **None** in `bot/handlers.py`. |
| Are quotas enabled in production? | **No** — `StagingStore` is built as `StagingStore(db, config.db_path)` with **no** quota kwargs ⇒ all `None` (disabled, D-12). |

**Therefore in the current production wiring, no code path performs a raw `Task.cancel()` on an
acceptance coroutine.** F-02 is **latent**: it is reachable by *any future* raw cancellation
(timeouts, `asyncio.wait_for`, task-group teardown, shutdown paths, a future concurrency change) but
is **not currently triggered** by the shipped sequential poller.

This is why F-02 was classified as a **coverage/robustness gap**, not an active defect — and it is
also why it must still be fixed before any concurrency change (OD-04) or timeout is introduced.

---

## 3. Reproduction evidence

### 3.1 Method

Throwaway harness in `/tmp` (since deleted), importing the project's own
`tests.test_def011_fs_offload.make_store` / `add_batch` helpers. The writer was replaced with an
instrumented callable gated on `threading.Event` — **synchronisation primitives only, no sleeps as
the ordering mechanism**.

### 3.2 Core reproduction (deterministic)

```
worker1 entered write; lock held = True
t1.cancel(); t1 raised CancelledError
AFTER cancel: lock held = False, worker still inside write = 1
t2 pending = False; lock held = False; max concurrent writers = 2
>>> OVERLAP (2 writers simultaneously) = True
DB items: [('i1','pending'), ('i2','stored')]
files on disk: 2
```

**Observed state transitions (F-02, unfixed):**

| Step | Lock | Worker 1 | Item i1 (DB) | Files |
|---|---|---|---|---|
| 1. `i1` enters critical section | **held** | — | `pending` | 0 |
| 2. `_store_prepare` returns; `to_thread` dispatched | held | **running** | `pending` | 0 |
| 3. raw `task.cancel()` | **RELEASED** | **still running** | `pending` | 0 |
| 4. `i2` enters critical section | re-acquired by i2 | **still running** | — | 0 |
| 5. i2 writes + finalizes | — | **still running** | `pending` | 1 |
| 6. worker 1 finally writes | — | done | `pending` (never finalized) | **2** |

### 3.3 Impact scenarios (each run 3× — 3/3 deterministic)

**Scenario A — quota bypass (only when quotas are explicitly enabled):**

```
max_items_per_batch=1
i2 result: StageStatus.STORED
items: [('i1','pending'), ('i2','stored')]
files on disk: 2  (quota was 1)
>>> QUOTA EXCEEDED = True
```
The quota counts **real files**. At step 4, i1's row exists but its file does not yet, so the count
is 0 and i2 is admitted. **This is the only admission-control violation found.** It is **not
reachable in production today** because all quotas default to `None` (D-12).

**Scenario B — orphan file after reaping (cleanup race):**

```
after cancel: item status = pending
sweep: cleaned=1, status now = reaped
files right after sweep: 0
AFTER worker1 completes: status = reaped, files = 1
>>> ORPHAN AFTER REAP = True
```
The reaper deletes the row while the worker is still mid-write; the worker then creates the file
**after** the sweep. The DB row is `reaped` yet a file exists. **The DB is never corrupted** — the
`try_mark_attachment_item_stored` CAS (item `pending` AND parent batch `pending`) refuses to
resurrect a reaped item, so the item correctly stays `reaped` and the result is a **fail-closed**
`DB_FAILED`, never a false `stored`.

**Scenario C — duplicate files / token collision:** **NOT reproduced.** `i1` and `i2` receive
**distinct** staging tokens (`f4bd2e71…` vs `a2331388…`), and `_write_to_path` uses
`O_CREAT|O_EXCL|O_NOFOLLOW`, so a collision would fail closed rather than overwrite. **No duplicate
content, no overwrite.**

### 3.4 Recovery behaviour

The orphan is **transient**, not permanent — a **second** sweep reclaims it:

```
after worker done: status= reaped files= 1
second sweep cleaned= 1 files= 0
```

So the reaper **does** eventually recover, but the orphan survives **one extra sweep cycle**
(worst case: one sweep interval of extra disk usage). It is a **delayed-recovery** defect, not a
leak.

### 3.5 Determinism and limitations

| Item | Result |
|---|---|
| Determinism | **3/3** for the core overlap, **3/3** for quota, **3/3** for orphan, **5/5** for the fixed variant |
| Synchronisation | `threading.Event` gates; no ordering by sleep |
| Limitations | (a) Writer replaced by an instrumented callable — ordering is exact, but real fsync latency is not modelled. (b) Quotas are off by default, so Scenario A needed explicit enablement. (c) No live Telegram/OpenHands/storage used. (d) Python 3.13 only; **3.11 not exercised**. |

---

## 4. Root cause summary

**The `_accept_lock` critical section is not cancellation-safe.** `async with self._accept_lock`
releases on *any* exit, including raw `asyncio.Task.cancel()`, while the delegated worker thread
continues running unowned. `to_thread`'s built-in shield covers only anyio cancel scopes.

Consequences, ranked by real impact:

| # | Impact | Severity | Currently reachable? |
|---|---|---|---|
| 1 | Orphan file surviving one extra sweep cycle | **LOW** | Yes (needs a raw cancel) |
| 2 | Quota/admission bypass | **MEDIUM** | **No** (quotas disabled) — would become reachable if quotas are enabled |
| 3 | Concurrent writers (2 at once) | **LOW** | Yes (needs a raw cancel) |
| 4 | DB inconsistency / false `stored` | **NONE** — prevented by the CAS guard | — |
| 5 | Duplicate/overwritten files | **NONE** — distinct tokens + `O_EXCL` | — |

---

## 5. Remediation alternatives

### Option A — **Drain the worker before releasing the lock** (RECOMMENDED)

Run the worker in its own task, `await asyncio.shield(...)` it, and on `CancelledError` **wait for
the worker to actually finish** before re-raising (which releases the lock only afterwards).

| Criterion | Assessment |
|---|---|
| Cancellation semantics | Cancellation is still delivered to the caller (task ends `CancelledError`) — contract preserved. |
| Worker lifetime / ownership | Worker stays owned until it completes; no unowned writer. |
| Lock lifetime | Held until the worker is genuinely done. **Fixes the root cause.** |
| DB consistency | Unchanged (CAS still governs). |
| FS cleanup safety | Orphan impossible from cancellation; reaper race removed. |
| Pending/reaper compatibility | Unchanged; reaper keeps working as before. |
| Deadlock risk | **Bounded**: waits at most the worker's remaining runtime (already bounded by `cap` and `fsync`). No lock-order inversion — the same single lock. |
| Resource leak | None. |
| Testability | **Excellent** — the same `threading.Event` gate proves it. |
| Architecture change | **None.** No new worker/queue/table/schema/dependency. |

**Empirically validated** in the throwaway harness, 5/5 runs: `max_concurrent=1`, `overlap=False`,
lock still held after cancel.

### Option B — **Ownership flag / reaper grace**

Record an "in-flight" marker so the reaper skips items whose worker may still be running.

| Criterion | Assessment |
|---|---|
| Cancellation semantics | Unchanged. |
| Lock lifetime | **Still released early — root cause NOT fixed.** |
| DB consistency | Needs a new column/table ⇒ **violates the "no schema change / no new table" constraint.** |
| Complexity | Higher; touches reaper + schema + migrations. |
| Verdict | **Rejected** — violates explicit constraints and does not fix the cause. |

### Option C — **Shield the whole critical section with `anyio.CancelScope(shield=True)`**

| Criterion | Assessment |
|---|---|
| Effect on raw asyncio cancel | **None — measured failure.** The harness showed `max_concurrent=2`, `overlap=True` with this option. |
| Verdict | **Rejected — does not work**, because the shield only covers anyio scopes. |

### Option D — **Make the writer cancellable mid-write**

Not possible/desirable: a thread cannot be safely interrupted mid-`write`; would risk partial files.

---

## 6. Recommended minimal approach

**Option A.** It is the smallest change that fixes the root cause, adds no architecture, and is
provably testable.

**Sketch (for a future, separately authorized implementation):**

```python
async with self._accept_lock:
    prep = self._store_prepare(...)
    if isinstance(prep, StageResult):
        return prep
    path, token, cap = prep
    worker = asyncio.ensure_future(
        to_thread.run_sync(functools.partial(
            self._store_write, path=path, chunks=chunks, cap=cap,
            item_id=item_id, token=token,
        ))
    )
    try:
        wrote = await asyncio.shield(worker)
    except asyncio.CancelledError:
        # Let the worker finish so the lock is not released under an active writer.
        await asyncio.wait({worker})
        raise
    ...
```

**Behavioural change:** none on the success path; on cancellation, the caller's `CancelledError` is
delayed by the worker's remaining runtime instead of being immediate.

**Invariants to preserve:**
1. `_accept_lock` is never released while `_store_write` is executing.
2. No more than one writer is ever inside `_write_to_path` at a time.
3. A cancelled acceptance still never marks the item `stored` (T-7 must stay green).
4. DB work remains on the event-loop thread only.
5. `StageStatus` vocabulary and `AcceptOutcome` mapping unchanged.

**Known limitations of Option A:**
- A cancelled caller now waits for the in-flight write (bounded by `cap` ≈ 3 MiB + `fsync`). This is
  the intended trade-off: correctness over prompt cancellation.
- If the worker hangs indefinitely (pathological disk), the caller waits indefinitely. A timeout
  policy is out of scope (new behaviour, requires owner decision).

---

## 7. Regression-test matrix

| # | Case | Exists? | Action |
|---|---|---|---|
| 1 | Normal successful acceptance | **YES** (`test_T2`, `test_T3`, A1/A2 suites) | keep |
| 2 | Cancellation before worker execution | **NO** | **ADD** |
| 3 | **Cancellation while the worker is writing** | **PARTIAL** (`test_T7` — asserts no `stored`, but **does not assert lock/overlap**) | **EXTEND** |
| 4 | **Worker completes after coroutine cancellation** | **NO** | **ADD** |
| 5 | **Second acceptance while the first worker is active** | **NO** | **ADD** (the core F-02 test) |
| 6 | Worker failure after cancellation | **NO** | **ADD** |
| 7 | DB finalization failure | **YES** (DB-failure suites) | keep |
| 8 | Reaper recovery of pending records | **YES** (`test_T7` tail, F-01 suite) | keep |
| 9 | Repeated cancellation | **NO** | **ADD** |
| 10 | Lock released after all operations settle | **NO** | **ADD** |

**Proposed F-02 regression test (design):**

```python
def test_F02_lock_not_released_while_worker_writes(tmp_path):
    """raw asyncio cancel during write must NOT let a second accept overlap."""
    # gate the writer on threading.Event; record max concurrency
    # 1) start accept(i1); wait started
    # 2) t1.cancel(); expect CancelledError
    # 3) assert store._accept_lock.locked() is True  <-- fails today
    # 4) start accept(i2); assert it does NOT enter (max_concurrent == 1)
    # 5) release; await settle; assert i1 never 'stored'; assert 1 file
```

---

## 8. Exact implementation scope (for a future authorized task)

| File | Change | Lines (est.) |
|---|---|---|
| `bot/attachments.py` | `store_async`: replace `await to_thread.run_sync(...)` with worker-task + `asyncio.shield` + drain-on-cancel | ~10–14 |
| `tests/test_def011_fs_offload.py` | Extend `test_T7` with lock/overlap assertions | ~10 |
| `tests/test_def011_fs_offload.py` | Add F-02 regression test (§7) | ~40 |

**Not required:** schema, migration, new table, new worker, new queue/outbox, new dependency,
Mini App, `AttachmentService.accept`, reaper, `bot/app.py`, `bot/handlers.py`.

---

## 9. Independent review readiness

A review package would contain: the §8 diff, the F-02 regression test, the §7 matrix, the §6
invariants, the §3 before/after transition tables, and the §3.5 limitations. The reviewer must
reproduce the overlap on the **unfixed** code and its absence on the **fixed** code.

**No independent review has occurred.** `INDEPENDENCE_NOT_ESTABLISHED`.

---

## 10. Required owner decisions / authorizations

| # | Needed |
|---|---|
| 1 | **Authorization to modify `bot/attachments.py` + `tests/test_def011_fs_offload.py`** (implementation is out of scope for this task). |
| 2 | Decision on the **cancellation-latency trade-off** in §6 (caller waits for the in-flight write). Conservative default: accept it. |
| 3 | Acknowledgment that F-02 is **latent** today (no raw cancel in the shipped poller) and should be fixed **before** any OD-04 concurrency change or timeout is introduced. |
| 4 | If a worker-timeout policy is ever wanted, that is a **separate** decision (new behaviour). |

---

## 11. Explicit non-claims

- **F-02 is NOT fixed and NOT closed.** This task produced no code change.
- **No source or test file was modified**; `bot/attachments.py` hash is byte-identical to before.
- **No independent review** occurred.
- **WP-07 is NOT complete. DEF-011 is NOT complete.** DEF-011-A, DEF-011-C, F-03, WP-09 and the
  NAV/DEF-006 items remain open.
- **Python 3.11 was not exercised**; all evidence is Python 3.13.
- The `_accept_lock` guarantee is **not** an exactly-once delivery guarantee, and nothing here
  implies SQLite/Telegram atomicity.
