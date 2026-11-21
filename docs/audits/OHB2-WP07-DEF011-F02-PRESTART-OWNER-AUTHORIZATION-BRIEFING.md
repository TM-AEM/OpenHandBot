# OHB2 — WP-07 / DEF-011 / F-02 — Pre-Start Cancellation Regression
# Owner Authorization Briefing

**Document type:** owner decision request — **this document grants nothing**
**Date:** 2026-11-18
**Status:** `AWAITING_OWNER_DECISION` — every checkbox and signature field below is **empty on purpose**

> ## ⚠️ NOTHING IS AUTHORIZED BY THIS DOCUMENT
> This briefing **asks** for a decision. Reading it, or the task that produced it, does not
> constitute authorization. No source file, test file, owner decision record, or Git state was
> changed while preparing it. Every GRANT/DENY/DEFER option is left blank and unselected.
>
> F-02 is **not** implemented, **not** accepted, **not** independently reviewed, and **not** closed.
> WP-07 and DEF-011 remain incomplete.

---

## 0. Why this decision is needed now

The F-02 cancellation fix currently in the working tree (uncommitted) closes one hazard and
introduces another. A technical review found, and a follow-up session re-confirmed on the current
bytes, that a **single** raw cancellation delivered before the filesystem worker starts can leave
`_accept_lock` held **forever**. That permanently blocks attachment acceptance and can prevent the
process from shutting down.

The fix cannot be written without owner authorization, because:

* the prior F-02 implementation authorization covered a **different, already-completed** task;
* the technical review only **recommended** a corrective change — it explicitly did not implement it;
* no owner-signed authorization for this remediation exists anywhere in the repository (§7).

So this briefing exists to let the owner decide with the evidence in hand.

---

## A. Problem statement

### A.1 What the regression is

`StagingStore.store_async` (`bot/attachments.py`) holds an acceptance lock (`_accept_lock`) while a
filesystem write is offloaded to a worker thread, so that only one writer can ever be inside
`_write_to_path`. To keep the lock held until the worker truly finishes, the current code catches
cancellation and **drains** on a `threading.Event`:

```python
try:
    await to_thread.run_sync(_worker)
except anyio.get_cancelled_exc_class():
    await to_thread.run_sync(_done.wait)   # wait for the worker to signal completion
    raise
```

The completion signal (`_done.set()`) is set inside `_worker`'s `finally` block. That is correct
**only if `_worker` actually runs.**

`anyio`'s `run_sync_in_worker_thread` performs `await cls.checkpoint()` at
`anyio/_backends/_asyncio.py:2730` **before** it acquires the capacity limiter and **before** the
worker thread is created. If the task is cancelled in that window:

1. `_worker` is **never invoked**, so `_done.set()` **never executes**;
2. the `except` branch therefore waits on `_done.wait()` for an event **nobody will ever set**;
3. that wait is itself a `to_thread.run_sync` call, so it blocks indefinitely;
4. `_accept_lock` is held for the whole time, because the `async with` block cannot exit.

**The failure is a wait for a completion signal from a worker that never started.**

### A.2 Measured consequences

All figures below are **measured**, not estimated. They come from
`OHB2-WP07-DEF011-F02-INDEPENDENT-TECHNICAL-REVIEW-REPORT.md` (§9) and were re-confirmed read-only
against the current file hashes in
`OHB2-WP07-DEF011-F02-PRESTART-CANCELLATION-REMEDIATION-REPORT.md` (§3).

**Live re-confirmation on the current bytes (deterministic event-loop tick control + watchdog):**

```
=== live re-confirmation (read-only) ===
  cancel after 1 tick(s): outcome=cancelled  accept_lock_still_held=False
  cancel after 2 tick(s): outcome=HANG       accept_lock_still_held=True
  cancel after 3 tick(s): outcome=HANG       accept_lock_still_held=True
  WATCHDOG: probe exceeded 12s -> something is blocked
```

**Determinism:** 48/48 trials hung for every cancel point at ≥2 ticks (`2, 3, 4, 6` ticks × 12
trials each). This is a deterministic failure, not a flaky race.

| Consequence | Measured evidence |
|---|---|
| **Permanent lock retention** | `lock_held_after_hang=True` — the lock is never released |
| **Blocked subsequent acceptance** | `new_acceptance: BLOCKED FOREVER -> intake permanently wedged` |
| **Potential shutdown hang** | `WATCHDOG: process did NOT exit within 6s -> SHUTDOWN HANG` |
| **Event loop appears healthy** | `event_loop_still_responsive=True` — the process looks alive while intake is dead |

That last row matters operationally: the bot does not crash or log an obvious error. It keeps
serving, and every attachment upload silently blocks forever.

### A.3 Cancellation before worker start vs. after worker start

The distinction is the whole defect:

| | **Before worker start** (≥2 ticks) | **After worker start** (1 tick) |
|---|---|---|
| Worker ran | **No** | Yes |
| Completion signal set | **No** | Yes |
| Accepting coroutine terminated | **No** | Yes |
| `_accept_lock` released | **No** | Yes |
| Second acceptance proceeds | **No** | Yes |
| Process shuts down | **No** | Yes |
| Correct today | **No — defect** | Yes |

The drain logic is only sound in the right-hand column. In the left-hand column it waits for a
worker that was never created.

### A.4 This is a regression, not a pre-existing bug

The same probe run against the **pre-F-02** variant (reconstructed by removing only the drain block)
behaves correctly:

```
lock_held_after_hang=False
new_acceptance: ACQUIRED (no permanent block)
process exited cleanly
```

So the pre-fix code had the *opposite* problem — it released the lock too early and allowed two
concurrent writers — but it **never wedged**. F-02 traded a concurrency hazard for a
permanent-availability hazard triggerable by a **single** cancellation. Both are real; the new one is
worse for availability.

### A.5 Measured evidence vs. inferred risk

Kept deliberately separate, because they carry different weight in the decision.

**Measured (reproduced on the current bytes):**

* The wedge itself, its determinism (48/48), the held lock, the blocked second acceptance, and the
  shutdown hang — all observed directly.
* The pre-fix variant does not wedge — observed directly.
* The single-cancel path **after** the worker starts behaves correctly — observed directly.

**Inferred (reasoned, not observed in production):**

* **How often the pre-start window is hit in production.** The window is "cancelled after
  `store_async` reached `run_sync` but before the worker thread began executing". It is narrow, but
  it widens under load: the app offloads downloads (`bot/handlers.py:2086`) and sweep tails
  (`bot/attachments.py:1261`) onto the same 40-thread default limiter, so pool saturation is
  plausible exactly when many attachments are in flight. **I have not measured a production
  occurrence.** No production log, crash, or user report was examined.
* **Whether shutdown actually hangs in the deployed bot.** The shutdown hang was reproduced in a
  controlled harness, not observed in a live deployment. The app's SIGINT/SIGTERM handlers only set
  an `Event`, and PTB's `stop()` gathers rather than cancels — so the single cancel that triggers
  this most plausibly arrives from loop teardown. Whether a real shutdown reaches the window is
  **inferred**, not demonstrated.
* **Blast radius.** Attachment intake is permanently blocked, but the rest of the bot keeps running
  (measured: the loop stays responsive). So the expected production symptom is "attachments stop
  working silently", not a total outage — inferred.

**Nothing in A.5's inferred list should be presented as established fact.**

---

## B. Exact proposed authorization scope

Five **separate** decisions. Each must be answered independently; **no option is preselected**, and
granting one does not imply any other.

> Note on scope: the two candidate files are exactly `bot/attachments.py` and
> `tests/test_def011_fs_offload.py`. Nothing else in source or tests is in scope. The one additional
> file permitted is the implementation report / review-handoff document (decision 5).

### Decision 1 — Modify `bot/attachments.py`

> Scope: remediate **only** the pre-start cancellation regression described in §A, inside
> `StagingStore.store_async`. The invariant to preserve: the lock must never be released while a
> worker is active, and must never be held waiting on a worker that never started.

- [ ] **D1-GRANT** — "I authorize modifying `bot/attachments.py` to fix the pre-start cancellation
      regression described in §A, within the constraints in §C."
- [ ] **D1-DENY** — "Do not modify `bot/attachments.py`."
- [ ] **D1-DEFER** — "Decide later; do not modify it now."

Owner signature / date: ______________________

### Decision 2 — Modify `tests/test_def011_fs_offload.py` for the 12 regression cases

> Scope: add the 12 deterministic regression tests listed in §B.1, and strengthen the existing T7
> assertions if needed. No other test file may be touched.

- [ ] **D2-GRANT** — "I authorize modifying `tests/test_def011_fs_offload.py` to add the 12
      regression cases in §B.1 and strengthen T7."
- [ ] **D2-DENY** — "Do not modify the test file."
- [ ] **D2-DEFER** — "Decide later."

Owner signature / date: ______________________

#### B.1 The 12 required regression cases

All must use bounded waits and deterministic synchronization, and their cleanup must not itself be
able to hang.

| # | Case |
|---|---|
| 1 | Cancellation **before** worker submission |
| 2 | Cancellation **after submission but before** worker execution |
| 3 | Cancellation **after** worker start |
| 4 | Cancellation **during** worker completion |
| 5 | Worker **success** after cancellation |
| 6 | Worker **exception** after cancellation |
| 7 | **Unexpected** worker exception still signals completion |
| 8 | Worker error is **not silently swallowed** |
| 9 | Lock is **released if the worker never starts** |
| 10 | Lock **remains held** while an active worker is writing |
| 11 | A **second acceptance cannot overlap** the first writer |
| 12 | **Process shutdown does not hang** after pre-start cancellation |

### Decision 3 — Run the test suites

> Scope: run focused pre-start tests, all F-02 tests, the whole
> `tests/test_def011_fs_offload.py` module, attachment-related tests, and the full Python suite
> where feasible. Local execution only.

- [ ] **D3-GRANT** — "I authorize running the focused, module, attachment, and full Python test
      suites locally."
- [ ] **D3-DENY** — "Do not run the suites."
- [ ] **D3-DEFER** — "Decide later."

Owner signature / date: ______________________

### Decision 4 — Run mutation checks and static/security checks

> Scope: mutation checks proving the new tests detect (a) missing completion signalling,
> (b) premature lock release, (c) waiting forever for a worker that never starts, and (d) swallowed
> worker exceptions; plus pyflakes, bandit, and any available dependency/security checks.

- [ ] **D4-GRANT** — "I authorize running the mutation checks and the applicable static and security
      checks locally."
- [ ] **D4-DENY** — "Do not run them."
- [ ] **D4-DEFER** — "Decide later."

Owner signature / date: ______________________

### Decision 5 — Prepare the implementation report and independent-review handoff

> Scope: write the implementation report and prepare a handoff package for an independent reviewer.
> This is documentation only; it does not create a reviewer and does not assert independence.

- [ ] **D5-GRANT** — "I authorize preparing the implementation report and the independent-review
      handoff package."
- [ ] **D5-DENY** — "Do not prepare them."
- [ ] **D5-DEFER** — "Decide later."

Owner signature / date: ______________________

---

## C. Mandatory constraints

If any permission in §B is granted, the work **must** stay inside all of the following. These are not
negotiable defaults; they are the conditions of the grant.

### C.1 Preserved behaviour and structure

1. **Existing architectural guard tests remain in force and unmodified.** Specifically, the module
   must continue to satisfy:
   * `assert "asyncio" not in src`
   * `assert "create_task" not in src`
   * `assert not hasattr(StagingStore, "start")`, `"stop"`, and `not hasattr(AttachmentReaper, "stop")`
   * `assert "opportunistic_cleanup" not in src` and `not hasattr(StagingStore, "opportunistic_cleanup")`

   No guard file may be edited, weakened, skipped, or deleted. No prohibited construct may be
   introduced **indirectly** (e.g. `anyio.create_task_group` would match the `"create_task"` guard
   and is therefore excluded).
2. **Existing DEF-011-B working-tree changes are preserved.** `bot/attachments.py` currently carries
   a large uncommitted DEF-011-B body (the `store_async` / reaper / offload refactor, 410+/104−
   across 7 hunks). Only the two F-02 hunks are in scope. Nothing unrelated may be reverted,
   reformatted, or absorbed.
3. **SQLite ownership stays on the authoritative event-loop thread.** `_store_prepare` and
   `_store_finalize` must remain synchronous calls on the loop thread; the worker thread must never
   touch the database.
4. **Filesystem operations stay off the event-loop thread.** All `open`/`write`/`unlink`/`lstat` work
   continues in the worker thread.
5. **Existing pending/reaper behaviour is preserved.** A cancelled or failed write must leave the
   item `pending` (fail closed), must not create a false "stored" state, and must leave no partial
   file behind; the reaper must still be able to recover orphans.

### C.2 Prohibited additions

6. **No schema changes.**
7. **No new dependencies.** Nothing installed.
8. **No new workers, queues, outboxes, schedulers, or background services**, and no new concurrency
   architecture.
9. **No Mini App changes** — no source, UI, assets, configuration, tests, or documentation.
10. **No changes outside the two authorized files**, except the separately identified
    implementation-report / handoff document from decision 5.

### C.3 Git and publication

11. **No Git staging, commit, branch creation, push, PR, merge, deployment, or CI publication.**
12. **No Autopush activation.**
13. **No changes to repository settings or visibility.**

### C.4 Evidence integrity

14. **No false claims about cancellation safety.** If the double-cancellation limitation (§D) is not
    resolved by the chosen design, it must be reported as an explicit remaining limitation, not
    silently dropped.
15. **Test success must not be obtained by weakening tests.** No assertion may be relaxed to make a
    run green.
16. **Python 3.11 compatibility must not be claimed unless actually executed on Python 3.11.** Only
    3.13.15 is available locally.

---

## D. Double-cancellation decision

**This is deliberately separate from §B.** It is a *different* defect and must not be folded into the
pre-start authorization.

### D.1 What it is

A **second** raw cancellation delivered while the drain is in progress cancels the drain wait
itself, so the lock is released while the worker is **still writing**, and a second acceptance can
enter `_write_to_path` concurrently. The DEF-011 single-writer invariant is violated.

**Measured:** `max_concurrent_writers=2` with a real overlap proven.

### D.2 Why it is currently latent

A second cancel cannot arise from the supported execution path today:

* PTB `Application.stop()` **awaits** tracked tasks via `asyncio.gather(...)` — it does not cancel
  them (measured: 0 cancels).
* `asyncio.run()` loop teardown delivers **one** cancel (measured: 1).
* The app's SIGINT/SIGTERM handlers only set an `asyncio.Event`; they never cancel a handler task.
* The 3 `.cancel()` calls in production (`bot/outbox.py:588`, `bot/watcher.py:161`,
  `bot/notifier.py:209`) target **their own components'** worker tasks, never an acceptance caller.

It becomes reachable the moment any future code wraps an acceptance in `asyncio.wait_for(...)` or
adds a second cancel-on-shutdown layer — both demonstrated to deliver two cancels.

**Note:** the §A regression needs only **one** cancel, so this reachability argument does **not**
protect it. They are genuinely separate.

### D.3 The choice

- [ ] **D6-ACCEPT-AND-DOCUMENT** — "Accept the remaining double-cancellation limitation for now and
      document it as a known, latent limitation with its reachability. Do not remediate it in this
      task."
- [ ] **D6-DEFER-TO-SEPARATE-INVESTIGATION** — "Defer double-cancellation remediation to a separate
      investigation and a separate authorization. Do not address it in this task."

Owner signature / date: ______________________

> Neither option authorizes a broader implementation. Choosing either does **not** grant the
> pre-start fix, and granting the pre-start fix does **not** authorize double-cancellation work.
> Adding any new worker or architectural mechanism to address double-cancellation would require its
> own separate authorization.

---

## E. Review and acceptance requirements

Three separate gates remain after implementation. Passing one does not satisfy the others.

### E.1 Implementation test success is not independent review

A green suite proves the tests the implementer wrote pass. It does **not** prove the fix is correct,
complete, or safe. The prior round is the concrete example: the F-02 implementation had
**3422 passing tests, 0 failures**, and still shipped a Critical regression that the suite did not
detect. Test success and review are different things.

### E.2 Genuine independent review requires a separate environment

Independence requires a **separate environment** — different host, different session, different
filesystem, a reviewer who did not author the change. **Another agent in the same host, same session,
or the same shared filesystem is not independent.**

This environment **cannot supply that** (documented in the prior review's §1): same host, same user
uid, same filesystem, no Docker socket, no second agent-server, no reviewer LLM profile. Any review
produced here must be labelled `INDEPENDENCE_NOT_ESTABLISHED`, as the previous one was.

### E.3 F-02 cannot be closed on the implementation report alone

Closing F-02 requires all of:

1. an owner-signed authorization (§B);
2. an implementation whose full suite passes **and** whose mutation checks prove the new tests are
   not vacuous;
3. a **genuinely independent** review that confirms the fix — including that the pre-start window is
   actually closed, not merely narrowed;
4. **owner acceptance as a separate, explicit decision** after that review.

Meeting (1)–(3) does not imply (4).

---

## F. Signature block

**All fields must remain blank until the owner fills them.** Preparing this document did not fill,
tick, or preselect any of them.

```
OWNER DECISION
  D1  bot/attachments.py remediation ......... GRANT / DENY / DEFER  ->  __________
  D2  test_def011_fs_offload.py 12 cases ..... GRANT / DENY / DEFER  ->  __________
  D3  run test suites ........................ GRANT / DENY / DEFER  ->  __________
  D4  mutation + static/security checks ...... GRANT / DENY / DEFER  ->  __________
  D5  implementation report + handoff ........ GRANT / DENY / DEFER  ->  __________

GRANTED PERMISSIONS (restate in words)
  ______________________________________________________________
  ______________________________________________________________

DOUBLE-CANCELLATION CHOICE
  D6  ACCEPT-AND-DOCUMENT / DEFER-TO-SEPARATE-INVESTIGATION  ->  __________

OPTIONAL CONDITIONS
  ______________________________________________________________
  ______________________________________________________________
  ______________________________________________________________

OWNER SIGNATURE: ______________________________

DATE: ____________________
```

---

## G. Authorization status

| Item | State |
|---|---|
| Owner authorization for this remediation | **ABSENT** |
| `C-GRANT-SCOPE-A` (closest prior F-02 grant) | **`- [ ]` unticked** |
| Ticked decision boxes in `docs/audits/`, `docs/decisions/` | **0** |
| Owner signature/date fields | **13 blank, none filled** |
| Owner commit after `52e7789` | **none** |
| This briefing document | **grants nothing** |

**The scope is exactly two files** — `bot/attachments.py` and `tests/test_def011_fs_offload.py` —
plus the decision-5 report/handoff document. Nothing else in source or tests is proposed.

---

## H. Evidence sources

| Source | Used for |
|---|---|
| `docs/reviews/OHB2-WP07-DEF011-F02-OPTION-A-IMPLEMENTATION-REPORT.md` | the F-02 implementation and its disclosed limitation |
| `docs/reviews/OHB2-WP07-DEF011-F02-INDEPENDENT-TECHNICAL-REVIEW-REPORT.md` | the regression discovery, 48/48 determinism, pre-fix comparison, mutation survivors (M2/M4), double-cancel analysis (§8) |
| `docs/reviews/OHB2-WP07-DEF011-F02-PRESTART-CANCELLATION-REMEDIATION-REPORT.md` | live re-confirmation on current hashes, blocker status |
| `tests/test_repair_plan_01_review_findings.py`, `tests/test_attachment_cleanup_expiration_a4.py` | the exact guard assertions in §C.1 |
| `docs/audits/OHB2-WP07-SCOPE-A-C-GRANT-AUTHORIZATION-AND-SCOPE-REPORT.md` | prior grant state (`BLOCKED`, unticked) |
| `docs/audits/OHB2-WP07-BATCH04-REV2-OWNER-DECISIONS.md` | "NOTHING IS GRANTED" precedent and signature-block convention |

Current reviewed bytes: `bot/attachments.py` = `58dbfb3a3ba9c5f23d1f6d34a06757f1a575ee9c956f54504fe4340d3e3ac93f`,
`tests/test_def011_fs_offload.py` = `d0148a4d49b24cd973090ab74e59b901e7ef2bc3d109cc2210f8dec536360df9`.

---

**This document requests a decision. It does not make one.**
