# OHB2 — WP-07 / DEF-011 / F-02 — Independent Technical Review

**Review date:** 2026-11-18
**Artifacts under review:** `bot/attachments.py`, `tests/test_def011_fs_offload.py`
**Implementation report reviewed:** `docs/reviews/OHB2-WP07-DEF011-F02-OPTION-A-IMPLEMENTATION-REPORT.md`

**Review verdict:** `INDEPENDENCE_NOT_ESTABLISHED`
**Technical verdict (separate, clearly labelled):** `FAIL`

> These two verdicts answer different questions and must not be merged.
> * `INDEPENDENCE_NOT_ESTABLISHED` answers *"was this review performed by an independent
>   reviewer?"* — **No** (see §1).
> * `FAIL` answers *"is the reviewed implementation technically acceptable?"* — **No**, because a
>   reproducible, previously-undisclosed defect was found that is **worse** than the one disclosed
>   in the implementation report (§7, §9).

---

## 1. Independence verification

**Result: `INDEPENDENCE_NOT_ESTABLISHED`.**

| Property | Value |
|---|---|
| Hostname | `runtime-hjffxzvtsqfkfugy-56cd5f89b-4649q` |
| Kernel / OS | `Linux 6.8.0-1055-gke x86_64` |
| User / uid | `openhands` / `10001` |
| Working directory | `/workspace/project/OpenHandBot` |
| Python | 3.13.15 (repo `.venv`), pytest 9.0.3 |
| Repository identity | `TM-AEM/OpenHandBot`, branch `openhands-workspace-40xxn2SbOi0tRICb3y8TE`, HEAD `52e7789cc8cc97a7f7c09c9592226ab117db99a2`, divergence vs `origin/main` = `0 0` |
| Filesystem | **Shared, writable** with the implementation workspace — same inode tree, same `.git`, same `.venv` |

Evidence that genuine separation does **not** exist:

1. **Same host, same user, same session.** The implementation edits and the implementation report
   were produced in the immediately preceding turn of the *same* conversation, on this *same* host,
   by this *same* agent identity. There is no second reviewer identity.
2. **Same filesystem, not an independently materialized copy.** I did not review a
   separately-provisioned checkout; I reviewed the live working tree. I mitigated this by freezing a
   read-only snapshot (§2), but a snapshot taken by the implementer from the implementer's own tree is
   **not** reviewer independence.
3. **No isolation primitive available.** `docker` is installed but the daemon socket
   (`/var/run/docker.sock`) does not exist — `failed to connect to the docker API`. No container,
   namespace, VM or separate agent-server is reachable (`ss -ltn` returns no listener on `:60000`).
   Prior directories under `/workspace/review-*` are same-host, same-user artifacts, not separate
   reviewer environments.
4. **No separate reviewer session can be provisioned.** No LLM profiles or provider connections are
   configured for a distinct reviewer agent, and spawning one would spend credentials I am not
   authorized to spend.

**Consequence:** every result below is a **same-agent technical review**, not an independent review.
The §7 defect was found *despite* this limitation, and its reproduction is fully scripted, so it is
reproducible by a genuinely independent party.

---

## 2. Reviewed baseline and diff identity

A read-only snapshot was frozen **before** any analysis, outside the repository:

`/workspace/reviewer-workspace/OHB2-WP07-DEF011-F02-INDEPENDENT-TECHNICAL-REVIEW-20261118/`
(`chmod -w` applied; `MANIFEST.txt` records hashes)

| Artifact | SHA-256 |
|---|---|
| `attachments.py.frozen` | `58dbfb3a3ba9c5f23d1f6d34a06757f1a575ee9c956f54504fe4340d3e3ac93f` |
| `test_def011_fs_offload.py.frozen` | `d0148a4d49b24cd973090ab74e59b901e7ef2bc3d109cc2210f8dec536360df9` |
| `impl-report.md.frozen` | `68ded7a6a89e39caf4013d80dc01b4f3dd7d76a4ab12fe2eae6666431acc811f` |
| `investigation.md.frozen` | `25172156d6fc8a1b43de8e81e0fd3ba0edbce8ba2095078e77f39088d50b57f1` |
| `attachments.vs-origin-main.diff` | `64f604de587612e7966931ee44da90c67a3cc821a449460078d57d1ec450134f` |

**The working tree still matches the implementation report.** Live hashes re-checked *after* the
review are byte-identical to the frozen snapshot (`58dbfb3a…`, `d0148a4d…`), so the artifacts I
reviewed are exactly the artifacts the implementer produced. `bot/attachments.py` is 1849 lines.

**Separating pre-existing work from F-02 work.** `bot/attachments.py` carries a large body of
*pre-existing, uncommitted* DEF-011 work (the whole `store_async` / reaper / offload refactor).
`git diff origin/main -- bot/attachments.py` reports `410 insertions / 104 deletions` across 7
hunks — that is **not** F-02's diff. F-02 is a small subset:

| Hunk | Content |
|---|---|
| `@@ -72,16 +72,21 @@` | `+import threading` |
| `@@ -807,6 +793,156 @@` | `store_async` docstring + the `_done` / `_box` / `_worker` drain block |

The other 5 hunks (`@@ -513`, `@@ -643`, `@@ -748`, `@@ -953`, and the reaper body) belong to the
pre-existing DEF-011 work, not to F-02. **This distinction matters:** the implementation report's
"+30/−6 across 3 hunks" describes only F-02's own edits, which I confirmed by reconstructing the
pre-F-02 variant (§9). No pre-existing user work was absorbed, rewritten or reverted by F-02.

**Guard files were not modified.** `tests/test_attachment_cleanup_expiration_a4.py`,
`test_repair_plan_01_review_findings.py`, `test_repair_plan_02_life01_opportunistic_cleanup.py`,
`test_repair_plan_02_life04_lifecycle_e2e.py` are untouched by this task and still pass (§6).

---

## 3. Implementation control-flow analysis

The reviewed code (`store_async`, lines ~905–948):

```python
async with self._accept_lock:
    prep = self._store_prepare(...)          # DB — event-loop thread
    if isinstance(prep, StageResult): return prep
    path, token, cap = prep
    _done = threading.Event()
    _box: dict = {}

    def _worker() -> None:
        try:
            _box["wrote"] = self._store_write(...)   # FS — worker thread
        except BaseException as exc:
            _box["error"] = exc
        finally:
            _done.set()

    try:
        await to_thread.run_sync(_worker)
    except anyio.get_cancelled_exc_class():
        await to_thread.run_sync(_done.wait)
        raise
    if "error" in _box: raise _box["error"]
    wrote = _box["wrote"]
    if isinstance(wrote, StageResult): return wrote
    written, head = wrote
    return self._store_finalize(...)         # DB — event-loop thread
```

**Verified against the ten Phase-3 questions:**

| # | Property | Result | Evidence |
|---|---|---|---|
| 1 | Worker signals completion on success | **Yes** | `finally: _done.set()` |
| 2 | Worker signals completion on exception | **Yes** | `finally` covers `except BaseException` |
| 3 | Lock released only after worker stopped | **Yes, on the reachable path** — `async with` exits only after the drain returns. **No, in the pre-start window** (§9) |
| 4 | Completion signal missed / observed prematurely | **Missed if the worker never starts** — `_done` is then never set and the drain blocks forever (§9) |
| 5 | Worker exceptions propagated | **Yes** — `_box["error"]` re-raised on the caller thread. Verified for `RuntimeError`, `SystemExit`, `KeyboardInterrupt`; no *"never retrieved"* warnings |
| 6 | Cancellation semantics preserved | **Yes** — `raise` re-raises the original cancel after draining |
| 7 | SQLite on the event-loop thread | **Yes** — `_store_prepare` / `_store_finalize` are sync methods called only on the loop thread; the worker receives only `path/chunks/cap/token` |
| 8 | Filesystem off the event-loop thread | **Yes** — measured: loop thread `MainThread`, writer thread `AnyIO worker thread` |
| 9 | Temp files / partial writes safe | **Yes** — `_write_to_path` uses `O_EXCL|O_NOFOLLOW`, and `_safe_unlink(path)` on any `BaseException`; no partial file survives |
| 10 | Pending / reaper recovery still valid | **Yes** — after a cancelled write the item stays `pending`, and a later sweep reaps it and deletes the orphan file (verified end to end) |

**`to_thread.run_sync` is not shielded against a raw cancel** — I verified this directly rather than
assuming it: a raw `Task.cancel()` during `run_sync` is observed immediately
(`cancel_observed_after_s: 0.0`) while the worker thread is still running. So the drain block is
genuinely necessary and is not dead code on the single-cancel path.

---

## 4. Worker and lock lifetime analysis

**Single raw cancel (the reachable case): correct.**
Sequence: worker starts → `_done` not yet set → raw cancel → `CancelledError` caught → drain awaits
`_done.wait()` in a *second* `to_thread` call → worker finishes and sets `_done` → drain returns →
`raise` propagates the cancel → `async with` releases `_accept_lock`. The lock is therefore held
across the entire worker lifetime. Measured: `held_after_c1 = True`.

**Thread-limiter safety.** The drain consumes a *second* thread slot while the worker still holds
one. I tested this at `total_tokens` = 40, 2 and 1 and found **no deadlock** (`elapsed ≈ 0.25 s`,
equal to the worker duration), because the worker releases its slot before the drain needs it. Not a
defect — but it is the reason the pre-start window in §9 is reachable when the pool is saturated.

**Normal serialization is preserved.** Six concurrent acceptances with **no** cancellation produced
`max_concurrent_writers = 1`. F-02 did not weaken the single-writer guarantee on the normal path.

---

## 5. Cancellation test matrix (independently executed)

All rows driven against the **real** `StagingStore.store_async`, not a reimplementation.

| Case | Expected | Observed | Verdict |
|---|---|---|---|
| Normal completion | worker completes, lock released | completed, `lock_free=True` | **PASS** |
| Worker raises before completion | lock released after worker terminates | `RuntimeError` propagated, lock free | **PASS** |
| One raw `cancel()` during write | lock held until worker terminates | `held_after_c1=True` | **PASS** |
| Second acceptance during first worker | no overlap | `max_concurrent_writers=1` | **PASS** |
| Cancel then successful worker completion | cancel propagates after completion | `CancelledError` after drain | **PASS** |
| Cancel then worker failure | no false `stored`, no premature release | item `pending`, lock free, no partial file | **PASS** |
| Repeated cancellation during drain | no writer outliving lock ownership | **FAILS** — `max_concurrent_writers=2` (§8) | **FAIL** |
| Cancel at completion boundary (×50) | no race | `lock_leaks=0`, no errors | **PASS** |
| Reaper during pending write | no unsafe deletion | sweep ran, item `reaped`, orphan deleted by later sweep | **PASS** |
| Repeated stress (×60, single cancel) | no overlap / no inconsistency | `failures=0` | **PASS** |
| **Cancel before the worker starts** (not in the required matrix — found by review) | lock released, no wedge | **permanent wedge** (§9) | **FAIL** |

---

## 6. Architectural guard assessment

**What the guards protect.** All four guards encode one architectural property: *the attachments
module must not introduce a worker system, scheduler, or new concurrency primitive.* Concretely they
assert `"asyncio" not in src`, `"create_task" not in src`, no new worker class
(`class OutboxWorker` / `class Watcher` / `class Scheduler` / `Thread(`), and no
`StagingStore.start/stop` / `AttachmentReaper.start/stop`.

**The alternative preserves the protected property.** Measured on the reviewed file:
`asyncio`→0, `create_task`→0, `class OutboxWorker`→0, `class Watcher`→0, `class Scheduler`→0,
`Thread(`→0 occurrences; `hasattr(StagingStore,'start')`→`False`. F-02 adds no worker, no queue, no
task, and no scheduler — it uses one `threading.Event` and re-uses the existing single
`to_thread.run_sync` call site. The protected property holds.

**No equivalent prohibited mechanism was introduced indirectly.** `anyio.create_task_group` would have
matched the `"create_task"` guard, and it is **not** used. No `run_in_executor`, no new
`ThreadPoolExecutor`, no `asyncio` import. The only new import is `import threading` (stdlib).

**No guard was bypassed, weakened, or made ineffective.** I ran the four guard modules plus the
lifecycle E2E module: **126 passed**. The guard assertions are unmodified. I did **not** weaken any
guard, and I do **not** recommend removing one to make a preferred implementation compile.

> Judgement: the implementer's decision to deviate from the literal `asyncio.*` form was **correct**.
> The literal form would have broken four previously-passing architectural guards, which AGENTS.md
> forbids. The deviation is legitimate and is the right call.

---

## 7. Independently executed test results

Executed in the shared workspace with the repo's own `.venv`. **Because independence is not
established (§1), these are same-agent results, not independent verification.**

| Command | Result |
|---|---|
| `pytest tests/test_def011_fs_offload.py -k "F02 or T7"` | **4 passed**, 20 deselected |
| `pytest tests/test_def011_fs_offload.py` | **24 passed** |
| `pytest tests/ -k "attachment or def011 or staging or reaper"` | **420 passed**, 3002 deselected |
| `pytest` (full suite) | **3422 passed, 0 failed** (170.18 s) |
| `node --test tests/frontend/*.test.js` | **280 pass, 0 fail** |
| `pyflakes bot/attachments.py tests/test_def011_fs_offload.py` | clean (exit 0) |
| `bandit -lll -s B613 bot/attachments.py` | clean (exit 0) |
| Guard modules (4 files) | **126 passed** |

The implementer's headline numbers **reproduce exactly** (3422 / 280 / 0 lint). That is genuine
evidence the reported suite results are accurate — but the suite does not cover the defect in §9.

**Mutation verification (my own mutations, not the implementer's):**

| Mutation | Expected | Result |
|---|---|---|
| M1 — delete the drain, plain `await` | F-02 tests fail | **4 failed** (T7 + 3 F-02) — correctly detected |
| M2 — move `_done.set()` out of `finally` | suite should fail | **24 passed — SURVIVED** (coverage gap) |
| M3 — drain waits on a never-set event | suite should fail/hang | **hung** (detected only as a timeout, not an assertion) |
| M4 — swallow `_box["error"]` | suite should fail | **24 passed — SURVIVED** (coverage gap) |

M1 confirms the new tests are non-vacuous for the *disclosed* defect. **M2 and M4 surviving is a real
test-coverage gap:** nothing asserts that the completion signal is set on the exception path, and
nothing asserts that an unexpected worker exception type reaches the caller. I verified M2 is not
merely theoretical — with M2 applied, a cancel during an unexpected exception makes the drain block
forever (watchdog: `still blocked after 3s -> drain never unblocked`), and no test fails.

---

## 8. Double-cancellation assessment (the disclosed limitation)

**Independently reproduced. The report's disclosure is accurate.**

Probe: real `store_async`, one worker blocked in `_write_to_path`, then two raw cancels.

```
held_after_c1: True          # drain working
held_after_c2: False         # drain itself was cancelled -> lock released
worker_active_at_c2: 1
max_concurrent_writers: 2    # two REAL writers overlapped
OVERLAP PROVEN: True
```

The second cancel cancels `_done.wait()` itself, so the lock is released while the worker is still
writing, and a second acceptance then enters `_write_to_path` concurrently. The DEF-011 invariant
"no more than one writer is ever inside `_write_to_path`" is violated.

**Classification: a latent robustness limitation under the current architecture.**
Not a reachable defect in the shipped path — I verified reachability rather than accepting the
report's claim:

* PTB `Application.stop()` **awaits** tracked tasks via `asyncio.gather(...)`; it does not cancel them
  (`cancels=0`).
* `asyncio.run()` loop teardown delivers **one** cancel (`cancels=1`, measured).
* The app's SIGINT/SIGTERM handlers only set an `asyncio.Event` (`polling.py:113`); they never cancel
  a handler task (`cancels=1` under real SIGINT).
* The 3 `.cancel()` calls in production (`outbox.py:588`, `watcher.py:161`, `notifier.py:209`) target
  those components' **own** worker tasks in `stop()`, never a `store_async` caller.

So two cancels on one acceptance task cannot arise from the supported execution path today. It
becomes reachable the moment any future code wraps an acceptance in `asyncio.wait_for(...)` or adds a
second cancel-on-shutdown layer — both of which I demonstrated *do* deliver two cancels
(`cancels_delivered=2 -> double=YES`).

**Correction to the implementation report.** §9 of that report states the shipped PTB path performs
**"0 `.cancel()` calls"**. That is **inaccurate**: there are **3** `.cancel()` calls in production
code. The conclusion (none targets an acceptance task) still holds, but the stated justification is
wrong and should not be relied on.

---

## 9. NEW DEFECT — cancel before the worker starts wedges intake permanently

This is **not** the limitation disclosed in the implementation report. It is a distinct defect that
the report does not mention, and it is **worse**: it needs only a **single** raw cancel and it
**permanently** disables attachment intake and **prevents process shutdown**.

**Mechanism.** `anyio`'s `run_sync_in_worker_thread` performs
`await cls.checkpoint()` *before* acquiring the capacity limiter and *before* the worker thread is
created (`anyio/_backends/_asyncio.py:2730`). If the task is cancelled at that point, `_worker` never
runs, so `_done.set()` never executes. The `except` branch then waits on `_done.wait()` — a second
`to_thread` call — **for an event that no one will ever set.** The lock is held for the whole wait.

**Reproduction (deterministic, 48/48).**

```
cancel after 1 tick: {'cancelled': 12}      # worker had started -> fine
cancel after 2 ticks: {'HANG': 12}
cancel after 3 ticks: {'HANG': 12}
cancel after 4 ticks: {'HANG': 12}
cancel after 6 ticks: {'HANG': 12}
```

**Consequences, measured on the real code:**

```
lock_held_after_hang=True
event_loop_still_responsive=True
new_acceptance: BLOCKED FOREVER -> intake permanently wedged
```

The event loop stays healthy, so the process looks alive, but every future attachment acceptance
blocks on `_accept_lock` forever. Under `asyncio.run()` teardown the same wedge prevents the process
from exiting:

```
handler submitted and waiting for a thread slot
WATCHDOG: process did NOT exit within 6s -> SHUTDOWN HANG
```

**This is a regression introduced by the F-02 fix.** The identical probe against the pre-F-02 variant
(reconstructed by removing only the drain block) behaves correctly:

```
lock_held_after_hang=False
new_acceptance: ACQUIRED (no permanent block)
process exited cleanly
```

The pre-fix code had the *opposite* bug (lock released early, concurrent writers) but it never
wedged. F-02 traded a concurrency hazard for a permanent-availability hazard on a *single* cancel.

**Reachability.** The window is "task cancelled after `store_async` reached `run_sync` but before the
worker thread began executing". It is narrow but real, and it widens exactly when it matters most:
when the thread pool is busy. The app already offloads downloads (`handlers.py:2086`) and sweep tails
(`attachments.py:1261`) onto the same 40-thread default limiter, so saturation is plausible under
concurrent load — and shutdown is precisely when cancels arrive. Unlike the §8 limitation, this one
needs **one** cancel, not two, so the reachability argument that protects §8 does **not** protect this.

**Severity: Critical.** It is a permanent denial of the attachment intake path and blocks graceful
shutdown, reachable with a single cancellation, and it is a regression against the pre-fix baseline.

**Narrowly scoped remediation (recommended, NOT implemented by me).** Set a "worker started" flag
before the checkpoint is passed — i.e. mark the worker as pending before `run_sync` can be cancelled
and only drain when a worker is actually in flight — or drain with a bounded wait so the caller can
never block unboundedly on an event that will not be set. Either is a small, local change inside
`store_async`; neither requires touching the guards. A regression test that cancels across a range of
event-loop ticks (including before the worker starts) must be added.

---

## 10. Findings by severity

### Confirmed implementation defects
* **CRITICAL — cancel-before-worker-start wedges intake permanently and blocks shutdown** (§9).
  Deterministic, 48/48, a regression against the pre-fix baseline. *Not disclosed in the
  implementation report.*

### Test coverage gaps
* **HIGH — M2 survives:** no test asserts `_done.set()` happens on the exception path; the mutant
  hangs the drain on an unexpected exception and the suite stays green (§7).
* **MEDIUM — M4 survives:** no test asserts an unexpected worker exception *type* reaches the caller.
* **MEDIUM — no test covers cancel before the worker starts** (the §9 defect is invisible to the
  suite). The matrix in the implementation report covers only the worker-already-started window.

### Latent cancellation limitations
* **MEDIUM — double raw cancel during the drain** releases the lock under an active writer and allows
  two concurrent writers (§8). Confirmed reproducible; not reachable from the current shipped path.

### Incorrect statement in the implementation report
* **LOW — "0 `.cancel()` calls" is false** (there are 3). The conclusion survives; the justification
  does not (§8).

### Architectural decisions requiring owner approval
* The **deviation from the literal `asyncio.*` Option A form** to a `threading.Event` drain, in order
  to keep four architectural guards passing. I judge this deviation **correct and necessary** (§6),
  but it does require owner acknowledgement.

### Environmental verification gaps
* **Python 3.11 not verified** (only 3.13.15 available). CI covers 3.11; I did not.
* **Independence not established** (§1) — no separate reviewer environment exists here.

---

## 11. Recommendation

**C — Reject the current implementation and request a narrowly scoped corrective change.**

This is not a rejection of the *approach*. The guard-compliant `threading.Event` drain is the right
idea, and its behaviour on the reachable single-cancel path is correct (§3–§5). But the
implementation as submitted **introduces a Critical regression** (§9) that did not exist before it,
and it cannot be accepted while a single cancellation can permanently wedge intake and block
shutdown.

Requested corrective scope (small, local, no guard changes):
1. Ensure the drain can only block when a worker is actually in flight — never on a worker that was
   cancelled before it started.
2. Add a regression test that cancels across event-loop ticks, including before the worker starts.
3. Add the two missing assertions from §7 (completion signal on the exception path; unexpected
   exception type propagation).

Option **B** (accept, with a follow-up limited to hardening the *double*-cancel drain) would be
appropriate **only after** the §9 Critical is fixed. Option **A** (accept as-is) is **not**
defensible given §9.

**I have not implemented any of this.** No source file, test, guard, schema, or owner record was
modified by this review.

---

## 12. Remaining owner decisions

1. **§9 Critical regression** — accept the corrective scope above (recommended), or direct a
   different remediation.
2. **§8 double-cancel** — accept as a documented latent limitation, or authorize a follow-up.
3. **Guard-driven deviation** — acknowledge that the literal `asyncio.*` form was replaced by a
   `threading.Event` drain to keep the four architectural guards intact.
4. **Independence** — decide whether a genuinely independent reviewer environment must be provisioned
   before F-02 is closed; this environment cannot supply one (§1).

---

## 13. Review verdict

```
INDEPENDENCE_NOT_ESTABLISHED
```

Reviewer-session and environment independence were **not** established (§1). This review is a
same-agent technical review, clearly labelled as such.

```
TECHNICAL: FAIL
```

The implementation is **not** acceptable as submitted: a Critical, reproducible, previously-undisclosed
regression (§9) allows a single cancellation to permanently wedge attachment intake and block graceful
shutdown. The disclosed double-cancel limitation (§8) is real but correctly classified as latent.

**A technical PASS would not have implied owner acceptance. This is not a PASS.** F-02 is **not**
closed, WP-07 is **not** complete, and DEF-011 is **not** complete.

---

## Appendix — review boundary attestation

* Files modified by this review: **only this report** (plus the read-only snapshot outside the repo).
* `bot/attachments.py` — SHA-256 unchanged before/after: `58dbfb3a…`.
* `tests/test_def011_fs_offload.py` — SHA-256 unchanged before/after: `d0148a4d…`.
* Git state unchanged: HEAD `52e7789`, divergence `0 0`, `staged=0 modified=8 untracked=58 ignored=8`.
* No staging, commit, push, PR, merge, deploy, release or visibility change was performed.
* No dependency installed; no schema change; no new worker/queue; no guard weakened.
* All mutation and reproduction work was done in throwaway copies under `/tmp` (`rv_tree`, `rv_pre`,
  `rv_mut`), never in the repository.
