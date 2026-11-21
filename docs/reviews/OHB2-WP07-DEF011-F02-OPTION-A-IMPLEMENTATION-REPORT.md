# OHB2 — WP-07 / DEF-011 / F-02 — Option A Implementation Report

**Task:** `OHB2-WP07-DEF011-F02-OPTION-A-IMPLEMENTATION`
**Date:** 2026-11-18
**Verdict:** `F02_IMPLEMENTED_WITH_NOTES`

---

## 1. Authorization scope

Owner authorized F-02 remediation using Option A, **limited to two files**:

1. `bot/attachments.py`
2. `tests/test_def011_fs_offload.py`

Authorized: source + test edits in those two files only; local tests and static checks; this report.
**Not** authorized (and **not** performed): any other file, git staging/commit/branch/push/PR/merge,
CI publication, deployment, production calls, dependency installation, autopush activation.

---

## 2. Baseline and preservation evidence

| Item | Value |
|---|---|
| Repository root | `/workspace/project/OpenHandBot` |
| Branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` |
| HEAD | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| Divergence from `origin/main` | `0  0` |
| Staged / modified / untracked / ignored | `0 / 8 / 57 / 8` |
| `bot/attachments.py` pre-task SHA-256 | `d27fb79870d900f584aebfea861619f6e4000ba1b9cb026d359189ae1e914ed5` (1826 lines) |
| `tests/test_def011_fs_offload.py` | untracked; **21 tests** pre-task (per session baseline); now **24 tests**, 752 lines, SHA-256 `d0148a4d…`. Pre-task byte hash not recorded this session. |
| Python | 3.13.15 (`.venv`) |
| anyio | 4.16.0 |

`bot/attachments.py` already carried **pre-existing DEF-011-B working-tree changes** (386 insertions /
103 deletions vs `origin/main`). Those hunks are **untouched**: the `sweep_async` / `_sweep_fs_tail` /
`maybe_sweep_async` marker count is unchanged at **9** before and after this task.

**Isolation proof.** Removing only this task's edits from the current file and diffing against it yields
**exactly 3 hunks** (`import threading`, the docstring note, the worker block) — `git diff --no-index
--numstat` reports **+30 / −6** — with **no other changed lines**. The byte-identical pre-task SHA-256
could not be re-derived by the reconstruction script (a line-counting off-by-one in the script itself,
not a content difference), so the `diff` hunk evidence is the authoritative isolation proof.
Corroborating: the DEF-011-B marker count is unchanged at **9**, and the working-tree counters after the
task are unchanged (`0 / 8 / 57 / 8`), i.e. **no file outside the two authorized ones was added,
modified or removed.**

---

## 3. Root cause (confirmed by the prior investigation)

`anyio.to_thread.run_sync(abandon_on_cancel=False)` shields the await with an anyio
`CancelScope(shield=True)`. That shield covers **anyio cancel scopes only**; it does **not** protect
against a raw `asyncio.Task.cancel()`. Under a raw cancel the `async with self._accept_lock` block exits
immediately while the delegated worker thread keeps writing, so `_accept_lock` is released under an
active writer and a second acceptance can enter the filesystem critical section. Measured before the
fix: `max_concurrent writers = 2`.

---

## 4. Implementation details

### 4.1 The approved mechanism

Option A as validated: the worker runs in an independently-owned task, the caller awaits it through a
shield, and on cancellation it **waits for the worker to settle before re-raising** the cancellation,
so `_accept_lock` is never released while `_store_write` is executing.

### 4.2 Deviation required by a conflicting architectural guard

Four **pre-existing, previously-passing** tests forbid the literal strings `"asyncio"` and
`"create_task"` anywhere in `bot/attachments.py`:

- `tests/test_attachment_cleanup_expiration_a4.py::test_reaper_introduces_no_worker_or_task`
- `tests/test_repair_plan_01_review_findings.py::test_cleanup_adds_no_worker_or_scheduler`
- `tests/test_repair_plan_02_life01_opportunistic_cleanup.py::test_attachments_module_has_no_asyncio_or_task`
- `tests/test_repair_plan_02_life04_lifecycle_e2e.py::test_e2e_attachments_module_has_no_asyncio_or_worker_class`

These encode the **approved architecture** ("one bot + ASGI process, no new worker systems"). The
mandated literal implementation (`asyncio.ensure_future` + `asyncio.shield` + `asyncio.wait`) makes
`"asyncio"` appear in the module and therefore **breaks all four guards** (measured: 4 failed). Those
guard files are **outside** the authorized edit set, so they cannot be relaxed here, and AGENTS.md
forbids breaking working checks or weakening assertions to obtain green.

Measured mechanism comparison under a raw `asyncio.Task.cancel()`:

| Mechanism | Lock held after cancel | Lock released after worker end | Verdict |
|---|---|---|---|
| plain `await to_thread.run_sync` (vulnerable) | **no** | no | broken |
| bare `anyio.CancelScope(shield=True)` | **no** | no | broken (as the investigation found) |
| `anyio.create_task_group()` | yes | yes | works, but contains `"create_task"` → breaks guards |
| `asyncio.ensure_future` + `asyncio.shield` + `asyncio.wait` (mandated) | yes | yes | works, but contains `"asyncio"` → breaks guards |
| **`threading.Event` completion barrier + drain (implemented)** | **yes** | **yes** | **works, guard-compliant** |

The implemented form keeps Option A's semantics — *drain the worker before releasing the lock* — while
using no forbidden literal. It adds **no** new worker, queue, task or thread pool; it runs the same
single `to_thread` call and adds one `threading.Event` plus a one-shot drain wait.

### 4.3 The change

```python
_done = threading.Event()
_box: dict = {}

def _worker() -> None:
    try:
        _box["wrote"] = self._store_write(
            path=path, chunks=chunks, cap=cap, item_id=item_id, token=token,
        )
    except BaseException as exc:  # propagate, never swallow
        _box["error"] = exc
    finally:
        _done.set()

try:
    await to_thread.run_sync(_worker)
except anyio.get_cancelled_exc_class():
    await to_thread.run_sync(_done.wait)   # drain: hold the lock until the thread finishes
    raise
if "error" in _box:
    raise _box["error"]
wrote = _box["wrote"]
```

Plus `import threading` and a docstring note. Worker exceptions are captured and re-raised on the
caller's thread so the error contract is unchanged and no "exception never retrieved" warning is
produced (verified).

**Preserved:** SQLite ownership and event-loop boundaries (all `_store_prepare` / `_store_finalize`
stay on the loop thread); DB finalization; pending/reaper recovery; `O_EXCL`/`O_NOFOLLOW` exclusive
creation; public interfaces and the synchronous `store()` path.

**Not introduced:** schema/table/migration, new worker/queue/outbox, dependency, concurrency
architecture, Mini App change, exactly-once claim.

---

## 5. Changed files and diff statistics

| File | Change |
|---|---|
| `bot/attachments.py` | `import threading`; docstring note; worker block replaced (drain-on-cancel) |
| `tests/test_def011_fs_offload.py` | `T7` strengthened; 3 new F-02 tests + `_WriterProbe` helper |

`git diff --stat origin/main -- bot/attachments.py` → `1 file changed, 410 insertions(+), 104 deletions(-)`
(386/103 of which is pre-existing DEF-011-B work).

This task's own delta inside that file, measured with `git diff --no-index --numstat` against a
reconstruction with only my edits removed, is **+30 / −6 lines across 3 hunks** (the `import threading`
line, the 6-line docstring note, and the 23-line worker block replacing the 6-line call). The
reconstruction is line-count consistent with the current file (`1825 + 24 = 1849`); a byte-identical
pre-task SHA-256 could not be re-derived by that script, so the `diff` hunk evidence is used as the
isolation proof instead of a hash match.

---

## 6. Regression test results

`tests/test_def011_fs_offload.py` — **24 passed** (was 21; +3 new, T7 strengthened).

New / strengthened coverage (`_WriterProbe` gates every write on a `threading.Event`, so ordering is
synchronisation-based, never sleep-based):

| Test | Proves |
|---|---|
| `test_T7_cancel_during_write_never_claims_stored` (strengthened) | after a delivered raw cancel the lock is **still held**, `max_concurrent == 1`, lock released afterwards, no `stored` claim, reaper recovers |
| `test_F02_lock_held_while_worker_writes_after_raw_cancel` | 10-point contract: worker enters and pauses → raw cancel → worker keeps running → lock held → second accept cannot enter → worker finishes → cancel propagates → second accept proceeds → `max_concurrent == 1` → final DB/filesystem consistent |
| `test_F02_worker_failure_after_cancel_releases_lock_and_never_stores` | worker raises after cancel ⇒ cancellation propagates, lock eventually released, item stays `pending`, no partial file |
| `test_F02_repeated_raw_cancel_keeps_single_writer` | 3 cancel rounds each with a concurrent accept ⇒ `max_concurrent == 1`, victims `pending`, rivals `stored` |

**Non-vacuity (mutation evidence).** Re-installing the pre-fix body at runtime
(`await to_thread.run_sync(...)` only, no repo file changed):

```
FAILED test_T7_cancel_during_write_never_claims_stored
FAILED test_F02_lock_held_while_worker_writes_after_raw_cancel
FAILED test_F02_worker_failure_after_cancel_releases_lock_and_never_stores
FAILED test_F02_repeated_raw_cancel_keeps_single_writer
4 failed
```

Against the fixed code the same 4 pass. **All four tests are non-vacuous.**

**Stress.** 60 independent iterations of the real `store_async` under raw cancel:
`iterations=60 failures=0` (lock held, cancel propagated, lock freed, `max_concurrent == 1` each time).

---

## 7. Full suite and static checks

| Command | Result |
|---|---|
| `python -m pytest -q` | **3422 passed, 74 warnings** (baseline 3419; +3 new tests), exit 0 |
| `node --test tests/frontend/*.test.js` | **280 pass, 0 fail**, exit 0 |
| `python -m pyflakes bot/ automation/ tools/ main.py tests/` | **0 findings**, exit 0 |
| `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | **no High findings**, exit 0 |

Python **3.11 was NOT tested** — only 3.13.15 is present in this environment. No 3.11 claim is made.

---

## 8. Cancellation and lock-lifetime evidence

| Phase | Before fix | After fix |
|---|---|---|
| raw cancel during write | `async with` exits immediately; lock free; worker still writing; second writer overlaps (`max_concurrent = 2`) | cancel caught; drain waits for the thread; lock held; `max_concurrent = 1` |
| lock released | before worker end | **after** worker end |
| cancellation propagated | yes | yes (after drain) |
| `stored` claim on cancel | never | never |
| worker raises after cancel | swallowed into a background thread | captured and re-raised on the caller's thread; lock released |

Measured timelines (harness, worker gated 0.40 s): `worker_start +0.000 → worker_end +0.400 →
caller_cancelled +0.401 → lock_free +0.401`. `LOCK RELEASED AFTER WORKER END = True`.

---

## 9. Remaining limitations

1. **Double raw cancel during the drain.** If a **second** `Task.cancel()` arrives *while* the drain
   wait is running, the drain is itself cancelled and the lock is released under an active writer.
   Measured for **both** the mandated Option A form and the implemented form
   (`held_after_2nd_cancel = False`), and shielding the drain does not help either. This is an
   **inherent limitation of the approved design**, not of the chosen formulation. It requires two raw
   cancels on the same task; the shipped PTB path performs **none** (0 `.cancel()` calls,
   sequential `dispatch_and_wait`), so it is latent. Closing it needs an owner decision (e.g. a
   non-cancellable drain primitive or a timeout policy).
2. **Cancelled callers now wait** for the in-flight write (bounded by `cap` ≈ 3 MiB + `fsync`). This is
   Option A's documented correctness-over-promptness trade-off.
3. **Pathological hang** (disk never returns) ⇒ the caller waits indefinitely; a timeout policy is out
   of scope and is new behaviour requiring an owner decision.
4. The implementation **deviates from the mandated literal form** (no `asyncio.*`) because four
   pre-existing architectural guard tests forbid that literal in this module. Semantics are identical;
   see §4.2. **This deviation needs owner acknowledgement.**

---

## 10. Independent review status

**No independent review has occurred.** `INDEPENDENCE_NOT_ESTABLISHED`. All verification above was
performed by the implementing agent in the same session. No separate reviewer environment inspected the
final diff or re-ran the tests. This report makes **no** independent-review claim.

---

## 11. Git and publication status

- Branch `openhands-workspace-40xxn2SbOi0tRICb3y8TE`, HEAD `52e7789`, divergence `0 0` — unchanged.
- **No** staging, commit, branch creation, push, PR, merge, CI publication or deployment.
- Working tree: `0 staged / 8 modified / 58 untracked / 8 ignored`. The counters differ from the
  baseline only by **+1 untracked**: this report. Of the tracked modifications and untracked files, only
  `bot/attachments.py` and `tests/test_def011_fs_offload.py` differ in content because of this task; all
  other pre-existing user work is untouched.
- No secrets, no debug code, no temp files left in the repo (`/tmp` harnesses only, outside the repo).

---

## 12. Verdict

`F02_IMPLEMENTED_WITH_NOTES`

Implemented and verified within the authorized scope; the fix is non-vacuously regression-tested and the
full suite is green. The notes are: (a) the implementation necessarily deviates from the mandated
literal `asyncio.*` form to satisfy four pre-existing architectural guards, and (b) a double-cancel
residual limitation is inherent to the approved design. **F-02 is not independently reviewed and not
owner-accepted. DEF-011 and WP-07 are not complete.**
