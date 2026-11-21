# OHB2 — WP-07 / DEF-011 / F-02 — Independent Review and Closure Assessment

**Task:** `OHB2-WP07-DEF011-F02-INDEPENDENT-REVIEW-AND-CLOSURE`
**Date:** 2026-11-18
**Subject:** `OHB2-WP07-DEF011-F02-PRESTART-CANCELLATION-FINAL-IMPLEMENTATION`
**Review type:** **LOCAL TECHNICAL AUDIT — NOT an independent review** (see §1)

## FINAL VERDICT

```
INDEPENDENCE_NOT_ESTABLISHED
```

**F-02 is NOT closed. WP-07 and DEF-011 are NOT complete.**
A local technical audit was performed and is reported separately in §3–§12. It does not
substitute for an independent review, and it does not authorise closure.

---

## 1. Independence assessment

### 1.1 Verdict

```
INDEPENDENCE_NOT_ESTABLISHED
```

The task requires a genuinely separate review environment: separate host or isolated execution
environment, separate filesystem, separate process/session, read-only access to the exact
snapshot, and its own ability to execute tests. **None of these is available here.**

### 1.2 Environment identity (measured, not assumed)

| Property | Value | Independent? |
|---|---|---|
| Hostname | `runtime-hjffxzvtsqfkfugy-fdb7c5747-mrgdg` | single host |
| Docker daemon | **absent** (`/var/run/docker.sock` does not exist) | no container isolation |
| Podman / bwrap / firejail / lxc / systemd-nspawn | **all absent** | no sandbox isolation |
| `unshare --mount --pid --user` | **`Operation not permitted`** (cannot change root fs propagation) | no namespace isolation |
| `chroot` | present but requires root and shares the same kernel/host | not isolation |
| Agent servers | only `:60000`, which hosts **this** session | no second session |
| `/workspace/project/OpenHandBot` | device `66309` | — |
| `/workspace/review-packages` | device `66309` | **same filesystem** |
| `/workspace/reviewer-workspace` | device `66309` | **same filesystem** |
| `/workspace/review-20261119-isolated` | device `66309` | **same filesystem** |
| Ownership of all review dirs | `openhands` (same uid as this session) | **same identity** |

The directories named `review-*` are **not** independent environments. They are same-host,
same-filesystem, same-uid artifacts produced by earlier sessions of this same agent. Their names
are not evidence of isolation.

### 1.3 Why a same-host second agent would not qualify

The task states explicitly that a second agent on the same host, container, filesystem, or shared
writable workspace is **not** independent. Every available execution context here shares the
kernel, the device, the uid, and the Python environment. A different prompt in the same sandbox is
not a different environment.

### 1.4 What was not done (and why)

- No code was published, no PR opened, no repository visibility changed, no GitHub Actions
  triggered to manufacture an environment. The task forbids this, and it would also be a
  data-exfiltration risk (HIGH).
- No cloud delegation: that requires spending money and external credentials, which is outside the
  authorised scope.

### 1.5 Consequence

Per the task's own rules: independence is recorded as not established, no independent-review claim
is made, the local audit below is **clearly separated** from the independent-review verdict, and
**F-02 is not closed**.

---

## 2. Reviewed snapshot

### 2.1 Identity — recomputed, not taken from the hints

| Property | Value |
|---|---|
| Repository root | `/workspace/project/OpenHandBot` |
| Branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` |
| HEAD | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| `origin/main` | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| Divergence | `0 0` |
| Staged | 0 |
| Modified | 8 |
| Untracked | 65 |
| Ignored | 8 |

### 2.2 File hashes (recomputed independently)

| File | Full SHA-256 | Matches hint? |
|---|---|---|
| `bot/attachments.py` | `b98d561f0ba0ab27dea4e6bedee7955f68f1f6fa85a39fa81afe8aeb4d818356` | **yes** (`b98d561f…`) |
| `tests/test_def011_fs_offload.py` | `61babf0d77ff283e40f50b0d67448906c1ed6165849490b33bcb3ad579a160e4` | **yes** (`61babf0d…`) |

### 2.3 Snapshot is the working tree, not an older commit — proven

- `git show HEAD:bot/attachments.py` → `7e448b52ac3b5f470cb23e5de073161539e61b47a7c89c8fe5c4e65ec0c2276c`
  (**different** from the working tree, and it contains **no** `store_async` at all — the entire
  thread-offload is uncommitted pre-existing work).
- `tests/test_def011_fs_offload.py` is **not tracked at HEAD** (`git cat-file -e HEAD:…` fails).

So the reviewed artifact is unambiguously the working tree, not a commit. Confirmed.

### 2.4 Pre-fix reference — reconstructed and verified

To review a *diff* I must know the pre-change state. HEAD is useless for that (it predates
`store_async` entirely). I therefore reconstructed the pre-fix file by reverting **only** my F-02
hunk from the current file, and then checked the result against the baseline hash reported by the
implementation task:

```
reconstructed pre-fix sha256 = 58dbfb3a3ba9c5f23d1f6d34a06757f1a575ee9c956f54504fe4340d3e3ac93f
reported baseline            = 58dbfb3a3ba9c5f23d1f6d34a06757f1a575ee9c956f54504fe4340d3e3ac93f
```

**Exact match.** This is a genuine independent check with real evidential value: it proves the F-02
change is exactly the hunk claimed and that no other code was altered under the guise of this task.

### 2.5 Diff scope

Isolated diff of the authorised implementation change: **74 lines**, all inside
`StagingStore.store_async` (`bot/attachments.py` lines ~899–972). Composition: 1 docstring
paragraph, 1 gate/state/worker block, 1 cancellation handler.

**Zero changed `def` lines** for `_store_prepare`, `_store_finalize`, `_write_to_path`,
`_safe_unlink`. No import lines added. `import threading` is pre-existing at line 75.

### 2.6 Snapshot integrity after review

| File | Before review | After review |
|---|---|---|
| `bot/attachments.py` | `b98d561f…` | `b98d561f…` **(unchanged)** |
| `tests/test_def011_fs_offload.py` | `61babf0d…` | `61babf0d…` **(unchanged)** |

`HEAD` unchanged, `staged=0`, `modified=8`, `untracked=65`, `ignored=8`. `.openhands/` preserved.
All mutation and reproduction work was performed on **copies** under `/tmp/f02audit/`; the
authorised files were never modified by this review.

---

## 3. Atomic gate correctness

### 3.1 The code under review (verbatim, lines 931–969)

```python
_gate = threading.Lock()
_state = {"started": False, "abandoned": False}
_done = threading.Event()
_box: dict = {}

def _worker() -> None:
    try:
        with _gate:
            if _state["abandoned"]:
                return
            _state["started"] = True
        _box["wrote"] = self._store_write(...)
    except BaseException as exc:
        _box["error"] = exc
    finally:
        _done.set()

try:
    await to_thread.run_sync(_worker)
except anyio.get_cancelled_exc_class():
    with _gate:
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

### 3.2 Checklist

| Requirement | Verdict | Evidence |
|---|---|---|
| Worker and caller use the **same** gate | **PASS** | single `_gate` created at :931, captured by the closure `_worker` and used at :957 |
| `started` / `abandoned` mutually exclusive | **PASS** | both transitions occur only while holding `_gate`; second actor observes first actor's committed state |
| Gate never held across `await` / FS / DB | **PASS** | both `with _gate:` blocks contain only dict reads/writes; `_store_write` is at :944, **outside** the gate; `case18` enforces structurally |
| Worker wins ⇒ caller drains before releasing `_accept_lock` | **PASS** | drain at :963–968 executes inside the `async with self._accept_lock` scope opened at :918 |
| Caller wins ⇒ worker exits without writing | **PASS** | `if _state["abandoned"]: return` at :941–942 |
| Second acceptance cannot overlap an active write | **PASS** | measured `max_concurrent_writers=1` (§5.2, §6.2) |

### 3.3 Mutual-exclusion proof — reconstructed independently

**Claim.** It is impossible that *(caller does not drain)* ∧ *(worker writes)* ∧ *(lock released
before that write completes)*.

**Proof.** Suppose the caller set `_needs_drain = False`. While holding `_gate` it must have
observed `_state["started"] == False`, then set `_state["abandoned"] = True`.

- If the worker had acquired `_gate` first, it would have set `started = True` and released the
  gate before the caller could acquire it. The caller would then have read `started == True` and set
  `_needs_drain = True`. Contradiction.
- If the caller acquired `_gate` first, it set `abandoned = True`. When the worker subsequently
  acquires the gate it reads `abandoned == True` and returns without writing. Contradiction.

Both orderings are excluded. Since the gate serialises the two actors and each observes the
other's committed state, no interleaving satisfies the premise. **∎**

This matches the implementation report's proof. It is sound. The gate is the linearisation point;
no timing assumption is involved.

### 3.4 Residual observation — the `abandoned` check is load-bearing but behaviourally untested

This is a genuine finding and is recorded as **F-02-REV-01 (Medium)** in §11. The proof above
depends on line :941–942. I verified empirically that removing *only* that check — while keeping
the `with _gate:` block intact — produces **real overlapping writers**
(`max_concurrent_writers=2`), and that **no test in the suite detects it**. The implementation
report's mutation M4 was killed only because it deleted the *entire* gate block, which trips
`case18`'s structural `checked >= 2` assertion. That is a weaker guarantee than "the property is
behaviourally tested".

---

## 4. Worker lifecycle and error propagation

| Requirement | Verdict | Evidence |
|---|---|---|
| Complete worker body inside `try/finally` | **PASS** | `try:` at :939 encloses the gate block, the write, and the early `return` |
| `_done.set()` unconditional for every invocation | **PASS** | `finally: _done.set()` at :949–950 covers normal, early-return, and `BaseException` paths |
| Caller never waits for a worker that never started | **PASS** | `_needs_drain` is `False` whenever `started` is `False` (:960–962) |
| Worker errors not converted into successful storage | **PASS** | `_box["error"]` re-raised at :970–971; `_store_write` maps `OSError` → `WRITE_FAILED` and never yields `stored` |
| `_store_finalize` not called after failed writing | **PASS** | error check precedes `_store_finalize`; `wrote` is only unpacked after the error guard |
| Cancellation preserves fail-closed behaviour | **PASS** | measured: item remains `pending`, never `stored` (§6) |

### 4.1 Measured error behaviour on the cancellation path

```
caller got: CancelledError (worker OSError NOT propagated)
statuses: ['pending']
lock_held: False
```

A worker `OSError` after cancellation is **not** propagated — the caller re-raises
`CancelledError`. The item stays `pending` and the lock is released. This is the documented
limitation from the implementation report (§13.4) and I confirm it is accurate. It is fail-closed
and therefore acceptable; it is **not** a regression introduced by F-02.

---

## 5. AnyIO cancellation analysis

I verified the three load-bearing claims against the **installed** anyio 4.16.0 source rather than
trusting the report.

### 5.1 Claim: the checkpoint precedes the internal shield

`anyio/_backends/_asyncio.py`, `run_sync_in_worker_thread`:

```
2723  async def run_sync_in_worker_thread(
...
2730      await cls.checkpoint()          <-- checkpoint FIRST
...
2743      async with limiter or cls.current_default_thread_limiter():
2744          with CancelScope(shield=not abandon_on_cancel) as scope:   <-- shield SECOND
```

**Confirmed.** A raw cancellation delivered at line 2730 raises before any shield exists. The
pre-start window is real.

### 5.2 Claim: a cancelled future causes the worker to skip `func`

`anyio/_backends/_asyncio.py`, `WorkerThread.run`:

```
1118      context, func, args, future, cancel_scope = item
1121      if not future.cancelled():
1122          threadlocals.current_cancel_scope = cancel_scope
1124              result = context.run(func, *args)
```

**Confirmed.** If the future is cancelled between dispatch and execution, `func` never runs. This
is the second, independent wedge path — and it is exactly why the gate must handle "worker never
invoked", not merely "worker invoked and cancelled".

### 5.3 Claim: the shield covers anyio-scope cancellation only

`anyio/_backends/_asyncio.py`, cancellation delivery:

```
636      for scope in self._child_scopes:
637          if not scope._shield and not scope.cancel_called:
638              should_retry = scope._deliver_cancellation(origin) or should_retry
```

**Confirmed.** `_shield` suppresses delivery to *anyio scopes*. A raw `Task.cancel()` is delivered
by the asyncio event loop directly to the task and never consults `_shield`. Therefore the code
comment at :964–966 ("the shield does not stop `Task.cancel()`") is **accurate**, and the
implementation does **not** over-claim protection against repeated raw cancellation.

### 5.4 Verdict on the AnyIO reasoning

All three claims are factually correct against the installed version. The external
`CancelScope(shield=True)` around the drain is justified: without it, an already-cancelled anyio
scope aborts the drain at `run_sync`'s own checkpoint, releasing the lock under an active writer.
I confirmed this empirically (§5.5).

### 5.5 Empirical confirmation of the shield's necessity

| Variant | `held_while_writing` |
|---|---|
| shield present | **True** |
| shield removed | **False** ← lock released under an active writer |

Reproduced independently with an anyio scope cancelled **and** a raw cancel driving the caller into
the drain. This is the only path that reaches the drain with a cancelled scope, and it is
defensively covered by `case13`.

### 5.6 Reachability note

No production code uses anyio scopes: the only `CancelScope` in `bot/`, `main.py`, `automation/`,
`tools/` is the drain's own at `bot/attachments.py:967`. There is no `fail_after`,
`move_on_after`, or `create_task_group` anywhere in production code, and PTB 22.8 does not use
anyio. The anyio-scope scenarios are **defensive** coverage for the structure the design requires,
not reproductions of a live production path. This matches the implementation report.

---

## 6. Before/after reproduction

All reproduction ran against **hash-asserted** modules. My first attempt was invalid because the
repository path won `sys.path` resolution and silently loaded the fixed file while labelled
"BEFORE" — I detected this, discarded the result, and added a hard assertion on the loaded module's
SHA-256 so the error cannot recur silently.

### 6.1 BEFORE — pre-fix `58dbfb3a…` (verified loaded)

```
=== BEFORE (module sha=58dbfb3a3ba9c5f2…) ===
  ticks=0: cancelled  lock_held=False writes=0 statuses=[]
  ticks=1: cancelled  lock_held=False writes=0 statuses=[]
  ticks=2: HANG       lock_held=True  writes=0 statuses=['pending']   <-- WEDGED
  ticks=3: HANG       lock_held=True  writes=0 statuses=['pending']   <-- WEDGED
  ticks=4: HANG       lock_held=True  writes=0 statuses=['pending']   <-- WEDGED
  ticks=6: HANG       lock_held=True  writes=0 statuses=['pending']   <-- WEDGED
  WATCHDOG[BEFORE]: HANG
```

`writes=0` on every wedged tick proves the worker was never invoked — the pre-start window, exactly
as diagnosed.

### 6.2 AFTER — current `b98d561f…` (verified loaded)

```
=== AFTER (module sha=b98d561f0ba0ab27…) ===
  ticks=0: cancelled  lock_held=False writes=0 statuses=[]
  ticks=1: cancelled  lock_held=False writes=0 statuses=[]
  ticks=2: cancelled  lock_held=False writes=0 statuses=['pending']
  ticks=3: cancelled  lock_held=False writes=0 statuses=['pending']
  ticks=4: cancelled  lock_held=False writes=0 statuses=['pending']
  ticks=6: cancelled  lock_held=False writes=0 statuses=['pending']
```

No hang at any tick. Lock always released. Zero writes. Never `stored`.

### 6.3 Complementary half — started worker keeps the lock

```
lock_held_at_cancel=True          (must be True)
second_acceptance_blocked=True    (must be True)
max_concurrent_writers=1          (must be 1)
lock_after_completion=False       (must be False)
writes=2
HALF-2: OK
```

### 6.4 Expected-behaviour checklist (single raw cancellation)

| Expectation | Result |
|---|---|
| No permanent hang | **PASS** (ticks 0,1,2,3,4,6) |
| No lock held after a safely abandoned pre-start operation | **PASS** (`lock_held=False`) |
| No lock release while a started worker is writing | **PASS** (`lock_held_at_cancel=True`) |
| No overlapping filesystem writers | **PASS** (`max_concurrent_writers=1`) |
| No false `stored` state | **PASS** (status `pending` or absent) |

Synchronisation used events and `asyncio.wait_for` watchdogs, not bare sleeps as sole evidence.

---

## 7. Independent test results

Environment: **Python 3.13.15** (GCC 14.2.0), **pytest 9.0.3**, **anyio 4.16.0**.

| # | Check | Command | Result | Exit |
|---|---|---|---|---|
| 1 | Focused F-02 | `pytest tests/test_def011_fs_offload.py -k f02` | **23 passed**, 21 deselected | 0 |
| 2 | Full module | `pytest tests/test_def011_fs_offload.py` | **44 passed** | 0 |
| 3 | Architectural guards | `pytest tests/test_repair_plan_01_review_findings.py tests/test_attachment_cleanup_expiration_a4.py` | **101 passed** | 0 |
| 4 | Full Python suite | `pytest -q` | **3442 passed, 0 failed** (186.77 s) | 0 |
| 5 | Frontend | `node --test tests/frontend/*.test.js` | **280 pass, 0 fail** | 0 |
| 6 | pyflakes | `pyflakes bot/ automation/ tools/ main.py tests/` | **clean** | 0 |
| 7 | bandit | `bandit -r … -lll -s B613` | **Severity High: 0** (Low 5, Medium 19) | 0 |
| 8 | pip-audit | `pip_audit -r requirements-dev.txt` | **No known vulnerabilities** | 0 |

Every reported count reproduces exactly. Note on bandit: the summary also prints
"High: 6" under *confidence*; the authoritative **severity** breakdown is High **0**.

### 7.1 Architectural guard results (independent re-derivation)

| Token in `bot/attachments.py` | Count | Requirement |
|---|---|---|
| `asyncio` | **0** | PASS |
| `create_task` | **0** | PASS |
| `TaskGroup` / `create_task_group` | **0** / **0** | PASS |
| `Thread(` | **0** | PASS |
| `opportunistic_cleanup` | **0** | PASS |
| `queue` / `ThreadPool` / `Process(` | **0** / **0** / **0** | PASS |
| `StagingStore.start` / `.stop` | **absent** | PASS |

No new imports; no new worker, queue, service, dependency, or background process. SQLite ownership
remains on the event-loop path (`_store_prepare` / `_store_finalize`); filesystem work remains in
the existing worker-thread path (`_store_write`, which receives only `path`, `chunks`, `cap`,
`item_id`, `token` — no database handle). No schema, Mini App, or API contract change.

---

## 8. Independent mutation review

Seven mutations, each applied to an **isolated copy** of the repository (`/tmp/f02audit/mutsandbox`),
never to the user's tree. For each I recorded the exact mutation, the meaning, the verdict, and the
killing test.

| # | Exact mutation | Meaningful defect? | Verdict | Detected by |
|---|---|---|---|---|
| M1 | `if _needs_drain:` → `if False:` | Yes — started worker never awaited; lock released under active writer | **KILLED** | `test_F02_lock_held_while_worker_writes_after_raw_cancel`, `test_F02_worker_failure_after_cancel_releases_lock_and_never_stores`, `test_F02_repeated_raw_cancel_keeps_single_writer`, `case05`, `case13` |
| M2 | `_done.set()` moved out of `finally` (error path) | Yes — drain can hang forever on a failing worker | **KILLED (HANG)** | the defect itself (watchdog) |
| M3 | `if "error" in _box:` → `if False:` | Yes — failed write treated as success | **KILLED** | `case09`, `case10` |
| M4 | `with _gate:` + `abandoned` check **removed entirely** | Yes — worker writes after caller abandoned | **KILLED (structurally only)** | `case18` (`checked >= 2`) — **see §8.1** |
| M4′ | **only** `if _state["abandoned"]: return` removed, gate block kept | Yes — real overlap (`max_concurrent_writers=2`) | **SURVIVED** | **no test detects it** — **F-02-REV-01** |
| M5 | `if _needs_drain:` → `if True:` | Yes — pre-start hang (the original defect) | **KILLED (HANG)** | the defect itself (watchdog) |
| M6 | `with anyio.CancelScope(shield=True):` removed | Yes — cancelled scope aborts drain; lock released under writer | **KILLED** | `case13` |
| M7 | `_state["started"] = True` → `= False` | Yes — caller always abandons; no drain when worker runs | **KILLED** | `test_F02_lock_held_…`, `test_F02_worker_failure_…`, `test_F02_repeated_raw_cancel_…`, `case05`, `case13` |

### 8.1 The M4 discrepancy — a real finding

The implementation report claims "7/7 mutants killed". My independent run reproduces 7/7 **only if
M4 is defined as deleting the whole gate block**. That definition is killed by a *structural*
assertion (`case18` counts `with _gate:` blocks and requires ≥ 2), not by any behavioural test.

When M4 is narrowed to the semantically precise mutation — removing only the `abandoned`
early-return while keeping the gate — it **SURVIVES the entire F-02 suite (23 passed)** despite
being a genuine defect. I proved it is genuine by forcing the exact race deterministically
(worker dispatched, then blocked at the gate while the caller takes it):

| Variant | `writes_total` | `max_concurrent_writers` | Verdict |
|---|---|---|---|
| Mutant M4′ (no `abandoned` check) | 2 | **2** | **OVERLAP DETECTED** |
| Correct code | 1 | **1** | no overlap |

So the `abandoned` check at :941–942 is **load-bearing**, and no regression test would catch its
removal. This is recorded as **F-02-REV-01 (Medium)** in §11. It is a **test-coverage gap**, not an
implementation defect: the shipped code is correct.

---

## 9. D6 — separate assessment

D6 is explicitly outside this remediation. I did not modify code to address it.

### 9.1 Independently reproduced

```
lock_held_after_1st_cancel=True
lock_held_after_2nd_cancel=False   <-- limitation live
max_concurrent_writers=2           <-- single-writer invariant broken
D6 CONFIRMED LIVE
```

**Confirmed:** a **second** raw `Task.cancel()` delivered while the drain is waiting interrupts the
drain, `_accept_lock` is released while the worker is still writing, and a concurrent acceptance
then enters — producing **two simultaneous writers**.

`anyio.CancelScope(shield=True)` does **not** prevent this, and the implementation does not claim
it does (verified in §5.3).

### 9.2 Reachability in production paths

| Site | Behaviour | Reaches an acceptance caller? |
|---|---|---|
| `bot/outbox.py:588` `task.cancel()` | targets the outbox worker task | no |
| `bot/watcher.py:161` `self._task.cancel()` | targets the watcher task | no |
| `bot/notifier.py:209` `self._task.cancel()` | targets the notifier task | no |
| `main.py:69` | `asyncio.run(run_bot(app))` — single entry | — |
| PTB 22.8 `Application.stop()` | gathers tasks, does not cancel | no |

**D6 is latent, not reachable today.** It becomes reachable if future code wraps acceptance in a
timeout helper (`fail_after`) or adds a second cancel-on-shutdown layer that targets an acceptance
caller.

### 9.3 Status

**D6 remains OPEN as a separate follow-up.** Repeated raw cancellation is **not** safe and this
review does not claim otherwise.

---

## 10. Python 3.11 status

```
UNVERIFIED
```

Only `/usr/local/bin/python3.13` exists. `python3.11`, `python3.12`, `python3.10` are all **absent**;
no pyenv, conda, or alternate interpreter is installed. All results above were produced on
**3.13.15** only.

The implementation uses `threading.Lock`, `threading.Event`, and `anyio.CancelScope`, all
semantically identical on 3.11 — but I did not execute anything on 3.11 and do not infer
compatibility. CI (Python 3.11 & 3.13) must confirm it; that run was **not** performed because
triggering CI is outside this authorisation.

---

## 11. Findings by severity

### F-02-REV-01 — Medium — the `abandoned` early-return is load-bearing but behaviourally untested

- **Location:** `bot/attachments.py:941–942` (worker gate block); test gap in
  `tests/test_def011_fs_offload.py`.
- **Evidence:** Mutation M4′ (removing only `if _state["abandoned"]: return`, keeping the gate)
  survives all 23 F-02 tests. Forced-race measurement: mutant `max_concurrent_writers=2`, correct
  code `1` (§8.1). The report's M4 was killed only by `case18`'s structural block count, which is a
  proxy for the *shape* of the code, not for the *property*.
- **Impact:** The property "a caller that abandoned must prevent the worker from writing" is
  correct in the shipped code but unprotected against regression. A future refactor that keeps two
  `with _gate:` blocks while dropping the `abandoned` check would pass the whole suite and
  reintroduce overlapping writers.
- **Regression or pre-existing?** New — this is a gap in the F-02 test suite delivered by this
  task.
- **Required correction (for the implementation workflow, not applied here):** add one behavioural
  test that forces the caller-wins-then-worker-runs ordering deterministically (e.g. a gate wrapper
  that makes the worker thread yield to the caller, as used in this review) and asserts
  `writes == 0` / `max_concurrent_writers == 1`. This belongs in the authorised
  `tests/test_def011_fs_offload.py`.
- **Accuracy note:** the implementation report's "7/7 mutants killed" is **not reproducible** as
  literally stated; it holds only for the broader M4 definition. The report should be corrected to
  state which mutation was used and that its detection is structural.

### F-02-REV-02 — Informational — worker errors are not propagated on the cancellation path

- **Location:** `bot/attachments.py:954–969`.
- **Evidence:** measured `caller got: CancelledError`, item `pending`, lock released (§4.1).
- **Impact:** A worker `OSError` concurrent with cancellation is dropped. Fail-closed outcome
  (`pending`, never `stored`) is preserved, and the caller is cancelled so it cannot act on the
  error anyway.
- **Regression or pre-existing?** Introduced with F-02's structure; documented in the
  implementation report §13.4. Acceptable by design.
- **Required correction:** none. Retain the documentation.

### F-02-REV-03 — Informational — no timeout on the filesystem write

- **Location:** `bot/attachments.py:944–946` and the drain at :967–968.
- **Impact:** A hung filesystem could hold `_accept_lock` indefinitely while the drain waits.
  Size is bounded by `cap`, but not time.
- **Regression or pre-existing?** Pre-existing behaviour of the offload design; not introduced by
  F-02.
- **Required correction:** none within this scope. Note for future work.

### F-02-REV-04 — Informational — D6 remains open

See §9. Deferred by owner decision; not fixed; not safe.

### No Critical or High findings within the authorised F-02 scope

The implementation itself is correct for single raw cancellation: the defect is fixed, the
invariants hold under measurement, and the architecture is preserved. The only new finding of
substance is a test-coverage gap (Medium), not a code defect.

---

## 12. Closure recommendation

### 12.1 Recommendation

**Do not close F-02 on the basis of this review.** The reason is procedural and mandatory: this is
**not** an independent review, and the task requires an independent reviewer to provide the closure
recommendation.

### 12.2 Technical readiness (local audit conclusion)

The local technical audit finds F-02 **technically sound** for its stated scope:

- The pre-start defect is **independently reproduced** before the fix (wedged at ticks ≥ 2,
  `writes=0`) and **independently confirmed fixed** after it.
- Both halves of the invariant hold: pre-start cancellation releases the lock; a started worker
  keeps it; `max_concurrent_writers=1`.
- The mutual-exclusion proof is sound and reconstructed independently.
- All three AnyIO claims verified against installed source.
- 3442 Python tests, 280 frontend tests, guards, pyflakes, bandit High 0, pip-audit all pass.
- Architectural guards intact; exactly two authorised files changed; snapshot byte-identical after
  review.

But two conditions for closure are **not** met:

1. **Independence is not established** — no separate host, filesystem, or session exists.
2. **F-02-REV-01 (Medium)** is an unresolved finding within the authorised scope: a load-bearing
   invariant lacks behavioural test coverage.

### 12.3 Conditions to close

- [ ] A genuinely separate review environment performs this review and issues its own verdict.
- [ ] F-02-REV-01 is corrected in `tests/test_def011_fs_offload.py` (one behavioural test), and the
      corrected snapshot is re-reviewed.
- [ ] CI confirms Python 3.11.
- [ ] D6 remains documented as deferred and open.
- [ ] Owner acceptance is granted (separate from any review).

### 12.4 What this review does not claim

- It does not claim an independent review occurred.
- It does not claim F-02 is closed.
- It does not claim WP-07 or DEF-011 are complete.
- It does not claim repeated raw cancellation is safe.
- It does not claim Python 3.11 compatibility.

---

## 13. Report metadata

| Item | Value |
|---|---|
| Verdict | `INDEPENDENCE_NOT_ESTABLISHED` |
| Local audit conclusion | F-02 technically sound; one Medium test-coverage gap |
| Files modified by this review | **none** (report only) |
| Snapshot after review | `b98d561f…` / `61babf0d…` — unchanged |
| Git after review | `HEAD 52e7789`, `staged 0`, `modified 8`, `untracked 65` |
| Reproduction artifacts | `/tmp/f02audit/` (outside the repository) |
| Commits / pushes / PRs / CI | none |
