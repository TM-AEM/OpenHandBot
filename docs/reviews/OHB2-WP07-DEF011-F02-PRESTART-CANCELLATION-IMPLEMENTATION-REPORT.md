# OHB2 — WP-07 / DEF-011 / F-02 — Pre-Start Cancellation — Implementation Report

**Task:** `OHB2-WP07-DEF011-F02-PRESTART-CANCELLATION-FINAL-IMPLEMENTATION`
**Date:** 2026-11-18
**Authorization:** owner granted D1–D5 in the current conversation; **D6 = DEFER** (no double-cancellation fix).
**Verdict:** **`F02_IMPLEMENTED_AND_VERIFIED_WITH_NOTES`**

> **Not independently reviewed, not owner-accepted, not closed.**
> WP-07 and DEF-011 remain **incomplete**. This report claims only what the commands below show.

---

## 1. Original defect and root cause

**Symptom.** A single raw `asyncio.Task.cancel()` delivered during `store_async` could permanently
wedge `_accept_lock`, blocking **every** future attachment acceptance for the process lifetime.

**Root cause.** `anyio.to_thread.run_sync` performs `await checkpoint()` **before** it enters its
internal `CancelScope(shield=...)`. If the raw cancellation lands in that window:

1. the `CancelledError` is raised before the worker is submitted, so `_worker` is **never called**;
2. the previous code entered `except anyio.get_cancelled_exc_class():` and did
   `await to_thread.run_sync(_done.wait)` — waiting for a signal that **can never be set**;
3. `_accept_lock` is held by the `async with` and is never released.

**Second, subtler window.** Even when the future *is* submitted, anyio's `WorkerThread.run` does
`if not future.cancelled(): result = context.run(func, ...)`. A future cancelled at that point also
skips `func` entirely — same wedge, different code path.

**Reproduced before the fix** (see §6): ticks ≥ 2 → `outcome=HANG`, `lock_held=True`, `writes=0`
deterministically. `writes=0` proves the worker never ran, i.e. the pre-start window.

---

## 2. Exact implementation and state transitions

Changed region: **`StagingStore.store_async` only**, lines ~899–972 of `bot/attachments.py`.
Isolated diff: **74 lines** (see §4). Nothing else in the file was touched.

### 2.1 Shared state (all created per call, inside the acceptance-lock scope)

```python
_gate = threading.Lock()                        # the atomic gate
_state = {"started": False, "abandoned": False} # lifecycle state
_done = threading.Event()                       # completion signal
_box: dict = {}                                 # worker result / error
```

### 2.2 Worker transition (worker thread)

```python
def _worker() -> None:
    try:
        with _gate:                     # synchronous; no await inside
            if _state["abandoned"]:
                return                  # caller won the race -> never write
            _state["started"] = True
        _box["wrote"] = self._store_write(...)   # filesystem work OUTSIDE the gate
    except BaseException as exc:
        _box["error"] = exc
    finally:
        _done.set()                     # unconditional for every invocation
```

The **entire body, including the early-abandonment return, is inside `try/finally`**, so
`_done.set()` runs for every real invocation — including on `BaseException`.

### 2.3 Caller transition (event-loop thread, on cancellation)

```python
except anyio.get_cancelled_exc_class():
    with _gate:                         # synchronous; no await inside
        if _state["started"]:
            _needs_drain = True
        else:
            _state["abandoned"] = True
            _needs_drain = False
    if _needs_drain:
        with anyio.CancelScope(shield=True):
            await to_thread.run_sync(_done.wait)
    raise
```

**The gate is never held across an `await`, a filesystem operation, or a database operation.**
Both `with _gate:` blocks contain only in-memory flag reads/writes. This is enforced by a static
test (`case18`) and by construction.

### 2.4 Preserved contracts

| Contract | Status |
|---|---|
| `_store_prepare` / `_store_finalize` on the event loop (SQLite owner path) | unchanged |
| `_write_to_path` filesystem work on the worker thread | unchanged |
| `_store_write` maps `OSError` → `WRITE_FAILED` (does not raise) | unchanged |
| `_store_finalize` not called after a failed write | preserved (error check precedes it) |
| Fail-closed: cancellation never yields `stored` | preserved (item stays `pending`) |
| Worker error re-raised to the caller | preserved (`_box["error"]`) |

---

## 3. Mutual-exclusion proof

**Claim.** It is impossible to reach *(caller does not wait)* ∧ *(worker subsequently writes)*
∧ *(acceptance lock released before that write finishes)*.

**Proof by contradiction.** Suppose the caller set `_needs_drain = False`. While holding `_gate` it
therefore observed `started == False` and then set `abandoned = True`.

- **Case (a) — the worker acquired `_gate` first.** It would have set `started = True` and released
  the gate before the caller could acquire it. The caller would then read `started == True` and set
  `_needs_drain = True`. **Contradiction.**
- **Case (b) — the caller acquired `_gate` first.** It set `abandoned = True`. When the worker
  later acquires the gate it reads `abandoned == True` and returns without writing. **Contradiction.**

Both cases are excluded ⇒ no interleaving satisfies the premise. **∎**

**Why both transitions cannot win.** They are serialized by the same `_gate`, and the second actor
always *observes* the first actor's committed state. There is no gap between "read the flag" and
"act on it" because both happen under the same lock. The gate is the linearization point. No
reliance on thread-start timing, sleeps, or polling.

**Complementary property (worker wins).** If `started == True`, the caller drains inside the
`async with self._accept_lock` scope, so the lock cannot be released while the writer is active.
Verified empirically: `held_while_writing=True`, `max_concurrent_writers=1` (§6).

---

## 4. Exact two-file diff

| File | Change |
|---|---|
| `bot/attachments.py` | **74 lines** isolated (44 added / 12 removed in `store_async` + docstring) |
| `tests/test_def011_fs_offload.py` | **+674 lines**, 20 new tests appended (§5) |

### 4.1 `bot/attachments.py` — isolated diff

The repository already contained **705 lines of unrelated pre-existing modifications** to this file
(DEF-011-B work, uncommitted). To separate my change I reconstructed the exact pre-existing state:

```
git show HEAD:bot/attachments.py > pre.py && patch -p1 < PRE_attachments.diff
sha256(pre.py) = 58dbfb3a3ba9c5f23d1f6d34a06757f1a575ee9c956f54504fe4340d3e3ac93f   ← matches baseline
```

Diffing that against the current file yields **only** my F-02 hunk. It contains exactly three
changes: the docstring paragraph, the gate/state/worker block, and the cancellation handler.

**Verified unchanged by my diff:** `_store_prepare`, `_store_finalize`, `_write_to_path`,
`_safe_unlink` — zero changed `def` lines each.

### 4.2 Hashes

| File | Baseline | Final |
|---|---|---|
| `bot/attachments.py` | `58dbfb3a3ba9c5f23d1f6d34a06757f1a575ee9c956f54504fe4340d3e3ac93f` | `b98d561f0ba0ab27dea4e6bedee7955f68f1f6fa85a39fa81afe8aeb4d818356` |
| `tests/test_def011_fs_offload.py` | `d0148a4d49b24cd973090ab74e59b901e7ef2bc3d109cc2210f8dec536360df9` | `61babf0d77ff283e40f50b0d67448906c1ed6165849490b33bcb3ad579a160e4` |

---

## 5. Test matrix and results

**20 new tests** appended to `tests/test_def011_fs_offload.py` (module: 24 → 44 tests).

Every test asserts, where applicable: whether the worker started (via a write counter or
`entered` event), whether filesystem writing occurred, whether the acceptance lock stayed held
while required, whether a second acceptance could overlap (`max` concurrency), final DB status,
and completes within a **bounded watchdog** (`asyncio.wait_for(..., 2.0)`), with `release.set()`
in `finally` so a failed assertion cannot leave a hung thread.

| # | Test | Sync | Inject | Lock | Write? | DB | Result |
|---|---|---|---|---|---|---|---|
| 1 | `case01_cancel_before_submission` | tick control | before submission | released | no | pending | **PASS** |
| 2 | `case02_cancel_at_initial_checkpoint` | tick control | at `checkpoint()` | released | no | pending | **PASS** |
| 3 | `case03_cancel_while_waiting_for_limiter` | limiter `total_tokens=1` + hog thread | during limiter acquire | released | no | pending | **PASS** |
| 4 | `case04_cancel_after_submission_before_worker` | ticks 2,3,4,6,8 | after submit, before `func` | released | no | no `stored` | **PASS** |
| 5 | `case05_cancel_after_worker_start` | `entered` event | after started | held → released | yes | pending | **PASS** |
| 6 | `case06_cancel_during_filesystem_write` | `entered`/`release` | mid-write | held | yes | pending | **PASS** |
| 7 | `case07_worker_success_after_cancellation` | `entered`/`release` | mid-write | released | yes (ok) | pending | **PASS** |
| 8 | `case08_oserror_during_cancellation_path` | `entered`/`release` | mid-write + raise | released | fails | pending | **PASS** |
| 9 | `case09_unexpected_worker_exception` | direct | `RuntimeError` | released | fails | pending | **PASS** |
| 10 | `case10_unconditional_completion_signaling` | direct | `BaseException` | released | fails | — | **PASS** |
| 11 | `case11_early_abandonment_without_waiting` | ticks + reuse | before start | released, reusable | no | pending | **PASS** |
| 12 | `case12_no_overlapping_acceptance` | `entered`/`release` | none | serialized | sequential | — | **PASS** |
| 13 | `case13_anyio_scope_already_cancelled_at_drain` | scope + raw cancel | drain entry | **held** → released | yes | pending | **PASS** |
| 14 | `M1_anyio_fail_after_during_write` | `fail_after(0.05)` | during write | released | yes | no `stored` | **PASS** |
| 15 | `case15_lock_released_on_every_exit_path` | table-driven | success/reject/error/cancel | released each | per path | per path | **PASS** |
| 16 | `case16_shutdown_completion_with_pending_cancellation` | `asyncio.run` teardown | pre-start | released | no | pending | **PASS** |
| 17 | `case17_T7_strengthened_pre_start` | ticks + `entered` | **pre-start AND mid-write** | both asserted | both | — | **PASS** |
| 18 | `case18_no_await_while_holding_gate` | source inspection | — | — | — | — | **PASS** |
| M3 | `M3_double_cancel_before_gate` | double cancel | pre-gate | released | no | pending | **PASS** |
| M4 | `M4_worker_exception_not_masked_as_stored` | `entered`/`release` | drain + raise | released | fails | pending | **PASS** |

**M5** is covered by `case11`; **M6** by `case18`; **M7** by `case15`; **M8** by `case16`;
**M2** by `case13`; **M1** by its own test.

### 5.1 T7 strengthening (required item 17)

The original T7 sets its `started` event **inside** the write function and spins
`while not started.is_set()`. That guarantees the worker is already executing before the cancel is
delivered, so **T7 alone cannot detect any pre-start window** and would have passed on the broken
code. `case17` adds an explicit pre-start branch that asserts `writes == []` and the lock is
released — the exact behaviour T7 missed.

### 5.2 Static gate check (required item 18)

`case18` parses `store_async` source, walks every `with _gate:` block by indentation, and asserts no
`await` appears inside. It also requires ≥ 2 gate blocks (worker + caller) so the check cannot pass
vacuously on an empty file.

---

## 6. Before-fix and after-fix reproduction evidence

Same probe, unchanged, before and after (`/tmp/f02/repro_before.py` vs `repro_after.py`), bounded by
a 20 s watchdog.

**BEFORE** (`attachments.py` = `58dbfb3a…`):

```
ticks=0: outcome=cancelled  lock_held=False writes=0
ticks=1: outcome=cancelled  lock_held=False writes=0
ticks=2: outcome=HANG       lock_held=True  writes=0  <-- LOCK WEDGED
ticks=3: outcome=HANG       lock_held=True  writes=0  <-- LOCK WEDGED
ticks=4: outcome=HANG       lock_held=True  writes=0  <-- LOCK WEDGED
ticks=6: outcome=HANG       lock_held=True  writes=0  <-- LOCK WEDGED
WATCHDOG: probe exceeded 20.0s -> HANG CONFIRMED
```

**AFTER** (`attachments.py` = `b98d561f…`):

```
ticks=0: outcome=cancelled  lock_held=False writes=0
ticks=1: outcome=cancelled  lock_held=False writes=0
ticks=2: outcome=cancelled  lock_held=False writes=0
ticks=3: outcome=cancelled  lock_held=False writes=0
ticks=4: outcome=cancelled  lock_held=False writes=0
ticks=6: outcome=cancelled  lock_held=False writes=0
```

**Both halves of the invariant** (`/tmp/f02/verify_both.py`):

```
=== HALF 1: pre-start cancel (lock must be RELEASED) ===
  ticks=0: cancelled  lock_held=False writes=0  OK
  ticks=2: cancelled  lock_held=False writes=0  OK
  ticks=3: cancelled  lock_held=False writes=0  OK
  ticks=6: cancelled  lock_held=False writes=0  OK
=== HALF 2: cancel while worker WRITES (lock must stay HELD) ===
  lock_held_at_cancel=True  second_accept_blocked=True  max_concurrent_writers=1  lock_after=False
  OK
```

---

## 7. Mutation results

Seven mutants injected into `bot/attachments.py`, each run against the F-02 tests, then restored
(verified byte-identical afterwards).

| # | Mutant | Result | Killed by |
|---|---|---|---|
| 1 | Remove the drain (`if _needs_drain` → `if False`) | **KILLED** | case05, case17 + 3 pre-existing F-02 tests |
| 2 | `_done.set()` moved out of `finally` (error path only) | **KILLED (HANG)** | the defect itself |
| 3 | Swallow worker exceptions (`if False: raise`) | **KILLED** | case04, case09, case10 |
| 4 | Remove the gate's `abandoned` check in the worker | **KILLED** | case18 (gate-block count) |
| 5 | Always drain (`if True`) even if never started | **KILLED (HANG)** | the defect itself |
| 6 | Remove the `anyio.CancelScope(shield=True)` around the drain | **KILLED** | **case13** |
| 7 | `started` never set (`= False`) | **KILLED** | case05, case13, case17 + 3 pre-existing |

**All 7 killed.** Mutant 6 is the notable one: it survived the *first* mutation run. I then
constructed a discriminating probe and found that the shield only matters when an **anyio scope is
already cancelled** *and* a raw cancel drives the caller into the drain. Measured empirically:

| Variant | `held_while_writing` |
|---|---|
| shield present | **True** |
| shield removed | **False** ← lock released under an active writer |

`case13` was rewritten to assert exactly that, after which mutant 6 was killed. This is the reason
the shield is a real, tested requirement rather than a defensive decoration.

---

## 8. Static and security results

| Check | Command | Result |
|---|---|---|
| pyflakes | `python -m pyflakes bot/ automation/ tools/ main.py tests/` | **clean, exit 0** |
| bandit | `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | **High severity: 0** |
| pip-audit | `python -m pip_audit -r requirements-dev.txt` | **No known vulnerabilities** |

### 8.1 Full validation sequence (in the order required)

| # | Step | Command | Result |
|---|---|---|---|
| 1 | F-02 focused | `pytest tests/test_def011_fs_offload.py -k f02` | **23 passed** |
| 2 | Full module | `pytest tests/test_def011_fs_offload.py` | **44 passed** |
| 3 | Guard tests | `pytest tests/test_repair_plan_01_review_findings.py tests/test_attachment_cleanup_expiration_a4.py` | **101 passed** |
| 4 | Full Python suite | `pytest -q` | **3442 passed, 0 failed** (176 s) |
| 5 | Frontend | `node --test tests/frontend/*.test.js` | **280 pass, 0 fail** |
| 6 | pyflakes | see above | clean |
| 7 | bandit | see above | High 0 |
| 8 | pip-audit | see above | clean |
| 9 | Mutations | see §7 | 7/7 killed |

Baseline before my change: full suite **3422 passed / 0 failed**. After: **3442 passed / 0 failed**
(3422 + 20 new). Frontend unchanged at 280. **Zero regressions.**

---

## 9. Python version and compatibility limitations

| Version | Status |
|---|---|
| 3.13.15 | **VERIFIED** — all tests and checks above ran here |
| 3.11 | **UNVERIFIED** — interpreter not installed in this environment (`python3.11` / `python3.12` not found) |
| 3.12 | **UNVERIFIED** — same |

The implementation uses only `threading.Lock`, `threading.Event`, and `anyio.CancelScope` — all
available and semantically identical on 3.11. **But I did not execute anything on 3.11 and do not
infer compatibility from 3.13.** CI (`CI` workflow, Python 3.11 & 3.13) must confirm it; that run
was **not** performed because Git publication is outside this authorization.

---

## 10. D6 — repeated raw cancellation status

**DEFERRED. Not implemented. Not fixed. Not safe.**

Measured behaviour (`/tmp/f02/probe_d6.py`), two raw cancels:

```
lock_held_after_1st_cancel=True
lock_held_after_2nd_cancel=False   <-- limitation live
second_acceptance_overlapped=True
max_concurrent_writers=2           <-- single-writer invariant violated
```

A **second** raw `Task.cancel()` interrupts the drain wait itself, releasing `_accept_lock` while
the worker still writes; a concurrent acceptance then enters, giving **two simultaneous writers**.
`anyio.CancelScope(shield=True)` does **not** prevent this — a shield blocks anyio *scope*
cancellation delivery, and a raw `Task.cancel()` never consults a shield.

**Reachability today:** latent. `main.py:69` uses `asyncio.run(...)`; PTB 22.8 `Application.stop()`
**gathers** tasks rather than cancelling them; the three production `.cancel()` sites
(`bot/outbox.py:588`, `bot/watcher.py:161`, `bot/notifier.py:209`) target their own components'
tasks, never an acceptance caller. It becomes reachable if future code wraps acceptance in a
timeout helper or adds a second cancel-on-shutdown layer.

`M3_double_cancel_before_gate` covers a double cancel **before** the gate (passes, no hang). That
is a different scenario from interrupting the drain and must not be read as a D6 fix.

---

## 11. Existing unrelated working-tree changes (preserved)

Eight files were already modified **before** this task and were left untouched:

```
 M .agent/PROGRESS.md
 M bot/app.py
 M bot/attachments.py        ← carries 705 lines of pre-existing DEF-011-B work
 M bot/db.py
 M bot/handlers.py
 M bot/watcher.py
 M tests/test_handlers.py
 M tests/test_sw06_unwatch_db_failure_propagation.py
```

62 pre-existing untracked files were also preserved (`.openhands/`, `.agent/`, prior audit/review
docs, and `tests/test_def011_fs_offload.py` itself, which was already untracked).

No reset, clean, stash, checkout, or restore was run against any of them. The 705-line pre-existing
diff in `bot/attachments.py` is intact — my isolated change is 74 lines layered on top (§4.1).

---

## 12. Git baseline and final status

| Property | Before | After |
|---|---|---|
| HEAD | `52e7789` | `52e7789` |
| Branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` | unchanged |
| Divergence vs `origin/main` | `0 0` | `0 0` |
| Staged | 0 | **0** |
| Modified | 8 | **8** (same files) |
| Untracked | 64 | **64** (same count) |
| Ignored | 8 | 8 |

**No stage, commit, branch, push, PR, CI, merge, deploy, release, visibility change, or Autopush.**
The two authorized files are the only ones this task changed.

---

## 13. Remaining risks and follow-up requirements

1. **Not independently reviewed.** See §14. A passing test suite is not a review — the previous
   F-02 fix passed 3422 tests and still shipped a Critical regression.
2. **Not owner-accepted.** Acceptance is a separate post-review decision.
3. **D6 is live** (§10): repeated raw cancellation breaks the single-writer invariant. Deferred by
   owner decision, documented here, **not fixed**.
4. **Worker exceptions are not propagated on the cancellation path.** The caller re-raises
   `CancelledError`, so a worker error after cancellation is dropped. Accepted: the item stays
   `pending`, which is the correct fail-closed outcome, and the caller is cancelled so it cannot
   act on the error anyway. Documented, not fixed.
5. **No timeout on the filesystem write.** The drain waits for the worker, and the worker waits for
   the write. Size is bounded by `cap`, but a hung filesystem could hold the acceptance lock
   indefinitely. Pre-existing behaviour; **not** introduced here.
6. **Python 3.11 unverified** (§9).
7. **Anyio-scope scenarios are not production-reachable** — no `fail_after` / `move_on_after` /
   `CancelScope` / `create_task_group` exists in `bot/`, `main.py`, `automation/`, or `tools/`, and
   PTB 22.8 does not use anyio. `case13`/`M1` are defensive coverage for the structure the design
   requires, not reproductions of a live production path.

---

## 14. Review handoff

### 14.1 Independence status

```
INDEPENDENCE_NOT_ESTABLISHED
```

This review **cannot** be performed here as an independent one. The implementation, the tests, the
mutation harness, and this report were all produced by the same agent in the same session on the
same host and filesystem. No separate reviewer session, host, or filesystem is available in this
environment. **A same-host review must not be presented as independent.**

### 14.2 What the reviewer must do (in a genuinely separate environment)

1. Inspect the final two-file diff — reconstruct the pre-existing state with
   `git show HEAD:bot/attachments.py` + the pre-existing diff, then diff (procedure in §4.1).
2. Independently reproduce the cancellation windows — the pre-start wedge is at ticks ≥ 2; assert
   `lock_held` and `writes`.
3. Run the authorized regression tests: `pytest tests/test_def011_fs_offload.py -k f02`.
4. Inspect exception propagation and completion signaling — verify `_done.set()` is inside
   `finally`, and that a failed write never reaches `_store_finalize`.
5. Verify the architectural guards: `asyncio` 0, `create_task` 0, `Thread(` 0 in
   `bot/attachments.py`, and `StagingStore.start`/`stop` / `AttachmentReaper.start`/`stop` absent.
6. Assess the D6 limitation separately (§10) — do not merge it into the single-cancellation verdict.

### 14.3 Reproduction instructions

```bash
cd /workspace/project/OpenHandBot

# hashes must match §4.2
sha256sum bot/attachments.py tests/test_def011_fs_offload.py

# focused
.venv/bin/python -m pytest tests/test_def011_fs_offload.py -k f02 -q
# module + guards + full suite
.venv/bin/python -m pytest tests/test_def011_fs_offload.py -q
.venv/bin/python -m pytest tests/test_repair_plan_01_review_findings.py \
    tests/test_attachment_cleanup_expiration_a4.py -q
.venv/bin/python -m pytest -q
# static / security
.venv/bin/python -m pyflakes bot/ automation/ tools/ main.py tests/
.venv/bin/python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613
.venv/bin/python -m pip_audit -r requirements-dev.txt
# frontend
node --test tests/frontend/*.test.js
```

Expected: 23 / 44 / 101 / 3442 passed; pyflakes clean; bandit High 0; pip-audit clean; node 280.

---

## 15. Verdict

```
F02_IMPLEMENTED_AND_VERIFIED_WITH_NOTES
```

**Implemented and verified:** the pre-start regression is reproduced before the fix
(`HANG`, `lock_held=True`, `writes=0` at ticks ≥ 2) and prevented after it (all windows cancel
cleanly, lock released), while the started-worker case still drains correctly
(`held_while_writing=True`, `max_concurrent_writers=1`). Full suite 3422 → 3442 passed, zero
failures, zero regressions; all 7 mutants killed; guards intact; exactly two files changed.

**`_WITH_NOTES` because:** the D6 limitation is live and unfixed (§10), Python 3.11 is unverified
(§9), worker errors are not propagated on the cancellation path (§13.4), the review is not
independent (§14.1), and owner acceptance has not occurred.

**F-02 is not closed. WP-07 and DEF-011 are not complete.**
