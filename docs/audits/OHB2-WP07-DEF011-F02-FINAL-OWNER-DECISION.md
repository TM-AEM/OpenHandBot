# OHB2 — WP-07 / DEF-011 / F-02
# FINAL OWNER DECISION — Pre-Start Cancellation Remediation

**Document type:** owner authorization decision — **this document grants nothing**
**Date:** 2026-11-18
**Status:** `AWAITING_OWNER_DECISION` — every selection, signature, and date field below is **blank on purpose**

> ## ⚠️ THIS DOCUMENT AUTHORIZES NOTHING
> It **asks** for a decision. Reading it, or the task that produced it, is not authorization.
> No source file, test file, guard, schema, Mini App file, configuration, dependency, or owner
> decision record was changed while preparing it. Every GRANT/DENY/DEFER option and both D6 choices
> are left unselected and unsigned.
>
> **F-02 is not implemented, not independently reviewed, not owner-accepted, and not closed.**
> WP-07 and DEF-011 remain incomplete.

---

## 0. Purpose and authority

This is the single authoritative owner decision document for the F-02 pre-start cancellation
remediation. It supersedes the earlier *request* framing in
`OHB2-WP07-DEF011-F02-PRESTART-OWNER-AUTHORIZATION-BRIEFING.md` by adding the exact implementation
specification, the exact test matrix, the AnyIO cancellation limitation, and the D6 separation.

It replaces no signed record — there are none. It creates no authorization.

**Provenance of the findings in this document is stated in §8.** Some findings were independently
verified against the repository in this session; others were supplied by the owner as conversation
evidence from prior investigation sessions and are **not** backed by a report file in the
repository. They are labelled accordingly throughout.

---

## A. Atomic worker-start gate (proposed behavior)

### A.1 Mechanism

Inside `StagingStore.store_async` only, using the **already-imported** `threading` module
(`bot/attachments.py:75`):

- one `threading.Lock` gate (`_gate`);
- two explicit boolean states: `started`, `abandoned`;
- the existing `threading.Event` (`_done`) is retained for the drain.

### A.2 The two competing transitions

**Worker, at entry, before any filesystem work:**

```
with _gate:                 # synchronous; no await inside
    if _state["abandoned"]:
        return              # exit WITHOUT writing
    _state["started"] = True
# ... filesystem work, outside the gate ...
```

**Cancelling caller, inside the cancellation handler:**

```
with _gate:                 # synchronous; no await inside
    if _state["started"]:
        need_wait = True
    else:
        _state["abandoned"] = True
        need_wait = False
if need_wait:
    <drain>                 # see §C
raise
```

### A.3 Hard structural rules

1. **The gate must never be held across an `await`, a filesystem operation, or a database
   operation.** Both `with _gate:` blocks are pure in-memory flag checks. This is a correctness
   requirement, not a style preference: holding the gate across an await would deadlock the caller
   against the worker thread.
2. **If the caller marks the operation abandoned before the worker starts, the worker must exit
   without writing** — no bytes, no partial file, no database mutation.
3. **If the worker marks itself started first, the caller must drain it before releasing the
   acceptance lock** — the lock may not be released while a writer is active.

### A.4 Mutual-exclusion proof

Claim: it is **impossible** to reach the state *(caller does not wait)* ∧ *(worker subsequently
writes)* ∧ *(lock released before that write finishes)*.

Proof by contradiction. Suppose the caller set `need_wait = False`. That means, while holding
`_gate`, it observed `started == False` and then set `abandoned = True`.

- **Case (a) — the worker acquired `_gate` first.** It would have set `started = True` and released
  the gate before the caller could acquire it. The caller would then read `started == True` and set
  `need_wait = True`. Contradiction.
- **Case (b) — the caller acquired `_gate` first.** It set `abandoned = True`. When the worker later
  acquires the gate it reads `abandoned == True` and returns without writing. Contradiction.

Both cases are excluded, so no interleaving satisfies the premise. **∎**

**Why the two transitions cannot both win:** they are serialized by the same `_gate`, and the second
actor always *observes* the first actor's committed state. There is no timing window between
"observe the flag" and "act on it", because both happen under the same lock. The gate is the
linearization point.

**Deliberately absent:** no reliance on thread-start timing, no sleep, no polling, no heuristic. This
is why the design is deterministic rather than probabilistic.

### A.5 Consequences for the previously-identified windows

| Window | Old outcome | New outcome |
|---|---|---|
| Cancel before submission | lock held forever | caller sees `started=False` ⇒ no drain ⇒ lock released |
| Cancel at AnyIO's `checkpoint()` | lock held forever | same as above |
| Cancel while queued for the thread limiter | lock held forever | same as above |
| Submitted, but worker skipped `func` | lock held forever | same as above (`started` stays `False`) |
| Cancel after worker start | drains (correct) | unchanged: drains before releasing |

---

## B. Worker completion

1. **The complete worker body — including the early-abandonment path — must sit inside
   `try/finally`,** so that `_done.set()` is **unconditional for every worker invocation**.
   Placing `_done.set()` only on the success/error paths would reintroduce the original defect.
2. **Do not wait for `_done` if the worker was never started.** The wait is conditional on
   `started == True` (§A.2).
3. **Preserve worker error information.** Errors are carried in `_box["error"]` and re-raised.
4. **Do not call `_store_finalize` after a failed write.** The error check precedes finalization.
5. **Preserve fail-closed behavior when cancellation occurs while the worker is completing.** The
   item stays `pending`; the reaper recovers it. No `stored` claim is made.

**Known, disclosed asymmetry:** on the cancellation path the caller re-raises `CancelledError`
rather than the worker's error, so a worker exception that occurs *after* the caller was cancelled
is not propagated to that caller. This is **accepted and documented**, not fixed: the item remains
`pending`, which is the correct fail-closed outcome, and the caller has already been cancelled so it
cannot act on the error anyway. This must be stated in the implementation report rather than
presented as error propagation on the cancellation path.

---

## C. AnyIO cancellation limitation

### C.1 The limitation

AnyIO's `to_thread.run_sync` performs `await checkpoint()` **before** it enters its internal
`CancelScope(shield=...)`. Consequently, if an AnyIO cancel scope is **already cancelled** when the
drain begins, the drain can be aborted at that checkpoint — before the shield exists — releasing the
acceptance lock while the worker is still writing.

### C.2 The required structure

```
with anyio.CancelScope(shield=True):
    await to_thread.run_sync(_done.wait)
```

This places a shield **outside** the `run_sync` call, so the pre-entry checkpoint is itself shielded.

### C.3 What it does and does not do

- **It addresses:** an already-cancelled AnyIO scope during the drain.
- **It does not make raw repeated `Task.cancel()` safe.** A shield blocks AnyIO's *scope-driven*
  cancellation delivery only; a raw `asyncio.Task.cancel()` never consults a shield. Therefore
  **repeated raw cancellation remains unsafe** and is out of scope (see §D).

### C.4 Guard compatibility

`anyio.CancelScope(shield=True)` contains neither `"asyncio"` nor `"create_task"`, so it does not
trip the architectural guards. `anyio` is already imported (`bot/attachments.py:87`).

### C.5 Bounded wait

The drain waits for the worker, and the worker waits for the filesystem write. The write is bounded
in *size* (`cap` bytes) but the design adds **no timeout** on the filesystem operation. This is
pre-existing behaviour, not introduced here, and is recorded as a remaining limitation.

---

## D. D6 — Repeated raw cancellation (separate decision)

**Kept strictly separate from D1–D5. Neither option authorizes implementation.**

### D.1 What it is

A **second** raw cancellation delivered while the drain is in progress cancels the drain wait itself,
releasing the lock while the worker still writes, allowing a second acceptance to enter
concurrently. The DEF-011 single-writer invariant is violated (previously measured
`max_concurrent_writers = 2`).

### D.2 Current reachability

Latent under the current architecture: PTB's `Application.stop()` **gathers** tracked tasks rather
than cancelling them; the app entry point is `asyncio.run(...)` (`main.py:69`); and the three
production `.cancel()` sites (`bot/outbox.py:588`, `bot/watcher.py:161`, `bot/notifier.py:209`)
target their own components' worker tasks, never an acceptance caller.

It becomes reachable the moment any future code wraps an acceptance in a timeout helper or adds a
second cancel-on-shutdown layer.

### D.3 The two permitted choices

- [ ] **D6-ACCEPT_AND_DOCUMENT_LIMITATION** — "Accept the repeated raw-cancellation limitation for
      now and document it, with its reachability, as a known latent limitation. Do not remediate it."
- [ ] **D6-DEFER_TO_SEPARATE_INVESTIGATION** — "Defer repeated-cancellation remediation to a
      separate investigation and a separate authorization."

Owner signature / date: ______________________

**Repeated raw cancellation is NOT fixed, NOT safe, and NOT made safe by this specification.**

---

## E. Exact source scope

### E.1 Permitted

| File | Permitted change |
|---|---|
| `bot/attachments.py` | `store_async` implementation only |
| `tests/test_def011_fs_offload.py` | the regression tests in §F |

### E.2 Explicitly prohibited

- `_store_prepare`, `_store_finalize`, `_write_to_path`, `_safe_unlink` — **no changes**.
- Schema, migrations, database access patterns — **no changes**.
- Mini App (source, UI, assets, configuration, tests, documentation) — **no changes**.
- Any file outside the two listed above, except the implementation report permitted by D5.
- Guard tests — **may not be edited, weakened, skipped, or deleted**.

---

## F. Exact test specification (`tests/test_def011_fs_offload.py`)

All tests must use **deterministic synchronization** (events, gates, explicit tick control) rather
than arbitrary sleeps, and every test must carry a **bounded watchdog** with a stated failure
condition. Cleanup must not itself be able to hang.

Columns: **Sync** = synchronization mechanism; **Inject** = cancellation injection point;
**Lock** = expected acceptance-lock state; **Write?** = may the worker write;
**DB** = expected database status; **WD** = watchdog.

### F.1 Core cases (1–18)

| # | Case | Sync | Inject | Lock | Write? | DB | WD |
|---|---|---|---|---|---|---|---|
| 1 | Cancellation before submission | tick control | before `store_async` reaches `run_sync` | released | no | `pending` | 2 s |
| 2 | Cancellation at the initial AnyIO checkpoint | tick control | at `checkpoint()` | released | no | `pending` | 2 s |
| 3 | Cancellation while waiting for the thread limiter | `limiter.total_tokens=1` + a hog task | during limiter acquire | released | no | `pending` | 2 s |
| 4 | Cancellation after submission, before worker execution | `started` event held by worker | after `put_nowait`, before `func` | released | no | `pending` | 2 s |
| 5 | Cancellation after worker start | `started` event | after worker marked started | held, then released | yes (completes) | `pending` | 2 s |
| 6 | Cancellation during filesystem writing | `release` event | while writing | **held** | yes | `pending` | 2 s |
| 7 | Worker success after caller cancellation | `release` event | during write, then release | released | yes, succeeds | `pending` (no `stored` claim) | 2 s |
| 8 | `OSError` during the cancellation path | `release` + raise | during write | released | yes, fails | `pending` | 2 s |
| 9 | Unexpected worker exception | raise `RuntimeError` (not `OSError`) | during write | released | fails | `pending` | 2 s |
| 10 | Unconditional completion signaling | direct invocation | abandonment path | released | no | `pending` | 2 s |
| 11 | Early abandonment without waiting | gate instrumentation | before start | released | no | `pending` | 2 s |
| 12 | No overlapping acceptance while a worker is active | concurrent acceptances | none | serialized | sequential | `stored` for the successful one | 5 s |
| 13 | AnyIO scope already cancelled when the drain begins | pre-cancelled `CancelScope` | at drain entry | held → released | yes, completes | `pending` | 2 s |
| 14 | AnyIO cancellation during the drain | `fail_after` during drain | mid-drain | held → released | yes, completes | `pending` | 2 s |
| 15 | Lock release after every permitted exit path | table-driven over exit paths | each path | released at return | per path | per path | 2 s |
| 16 | Shutdown completion with a pending single cancellation | `asyncio.run` teardown | pre-start | released | no | `pending` | 5 s |
| 17 | **T7 strengthened** so it does not assume the worker already started | `started` event + explicit pre-start variant | pre-start **and** mid-write | per variant | per variant | `pending` | 2 s |
| 18 | Static proof that no `await` occurs while holding the gate | source inspection | — | — | — | — | n/a |

### F.2 M-series (M1–M8)

| # | Case | Sync | Inject | Lock | Write? | DB | WD |
|---|---|---|---|---|---|---|---|
| M1 | AnyIO scope cancellation (not raw) | `fail_after(0)` | pre-start / mid-write | per case | per case | `pending` | 2 s |
| M2 | Scope already cancelled at drain | pre-cancelled scope | drain entry | released | yes | `pending` | 2 s |
| M3 | Cancellation while entering the `except` handler | double cancel | between handler entry and gate | released | no | `pending` | 2 s |
| M4 | Worker exception on the cancellation path | `release` + raise | during drain | released | fails | **`pending`, never `stored`** | 2 s |
| M5 | `_done` on the early-exit path | gate instrumentation | abandonment | released | no | `pending` | 2 s |
| M6 | Gate never held across `await` | static scan | — | — | — | — | n/a |
| M7 | Lock release is atomic on all paths | table-driven | all paths | `locked() is False` after return | — | — | 2 s |
| M8 | Shutdown with a pending pre-start cancellation | `asyncio.run` teardown | tick 0–1 | released | no | — | 5 s |

### F.3 Mandatory weakness disclosure

The current T7 (`tests/test_def011_fs_offload.py:284`) sets its `started` event **inside** the write
function and waits `while not started.is_set(): await anyio.sleep(0)`. That guarantees the worker is
already executing before the cancel is delivered, so **T7 cannot detect any pre-start window** and
would give a false assurance if relied upon alone. Test 17 must add the pre-start variants; T7 alone
is insufficient evidence.

---

## G. Owner authorization matrix

Each decision is independent. **No option is preselected.**

### D1 — Modify `bot/attachments.py` (within §E)

- [ ] **D1-GRANT** — authorize implementing §A–§C in `store_async` only.
- [ ] **D1-DENY** — do not modify `bot/attachments.py`.
- [ ] **D1-DEFER** — decide later.

Owner signature / date: ______________________

### D2 — Modify `tests/test_def011_fs_offload.py` (within §F)

- [ ] **D2-GRANT** — authorize adding the §F matrix and strengthening T7.
- [ ] **D2-DENY** — do not modify the test file.
- [ ] **D2-DEFER** — decide later.

Owner signature / date: ______________________

### D3 — Run the test groups

- [ ] **D3-GRANT** — authorize running: the focused F-02 tests, the full
      `tests/test_def011_fs_offload.py` module, attachment-related tests, and the full Python suite.
- [ ] **D3-DENY** — do not run them.
- [ ] **D3-DEFER** — decide later.

Owner signature / date: ______________________

### D4 — Run mutation, static, and security checks

- [ ] **D4-GRANT** — authorize mutation checks plus pyflakes, bandit, and the available
      dependency/security checks.
- [ ] **D4-DENY** — do not run them.
- [ ] **D4-DEFER** — decide later.

Owner signature / date: ______________________

### D5 — Prepare the implementation report and independent-review handoff

- [ ] **D5-GRANT** — authorize preparing the implementation report and the review handoff package.
- [ ] **D5-DENY** — do not prepare them.
- [ ] **D5-DEFER** — decide later.

Owner signature / date: ______________________

### D6 — Repeated-cancellation policy

See §D.3. **Separate from D1–D5.**

---

## H. What is explicitly NOT authorized

- **Previous Option A authorization does not automatically authorize this new remediation.** It
  covered a different, completed task; this is a newly discovered regression.
- **A technical recommendation is not implementation authorization.** The technical review only
  recommended a corrective direction and stated it implemented nothing.
- **A draft is not a signed owner decision.** This document, and every other agent-authored
  document, is a request.
- **No implementation may start until the relevant permissions are explicitly granted** with the
  owner's signature and date.

---

## I. Independent review requirements

Technical review must:

1. Inspect the final two-file diff.
2. Independently reproduce the relevant cancellation scenarios.
3. Run the authorized tests independently.
4. Inspect the architectural guards and error propagation.
5. Test the pre-start cancellation windows specifically.
6. Report double-cancellation behaviour separately.
7. Use a **genuinely separate host, session, and filesystem**.

If genuine independence is unavailable, the verdict **must** be `INDEPENDENCE_NOT_ESTABLISHED`.
A same-host review by another agent in the same session is **not** independent and must not be
presented as such.

**Owner acceptance remains a separate post-review decision.** Passing tests and passing review do
not constitute acceptance.

---

## J. Signature block

**All fields blank until the owner completes them.**

```
OWNER DECISION
  D1  bot/attachments.py (store_async) ....... GRANT / DENY / DEFER  ->  __________
  D2  test_def011_fs_offload.py matrix ....... GRANT / DENY / DEFER  ->  __________
  D3  run test groups ........................ GRANT / DENY / DEFER  ->  __________
  D4  mutation + static/security checks ...... GRANT / DENY / DEFER  ->  __________
  D5  implementation report + handoff ........ GRANT / DENY / DEFER  ->  __________

GRANTED PERMISSIONS (restate in words)
  ______________________________________________________________
  ______________________________________________________________

REPEATED-CANCELLATION POLICY (D6)
  ACCEPT_AND_DOCUMENT_LIMITATION / DEFER_TO_SEPARATE_INVESTIGATION  ->  __________

OPTIONAL CONDITIONS
  ______________________________________________________________
  ______________________________________________________________

OWNER SIGNATURE: ______________________________

DATE: ____________________
```

---

## K. Evidence provenance

### K.1 Independently verified in this session against the repository

| Fact | Value |
|---|---|
| `bot/attachments.py` SHA-256 | `58dbfb3a3ba9c5f23d1f6d34a06757f1a575ee9c956f54504fe4340d3e3ac93f` |
| `tests/test_def011_fs_offload.py` SHA-256 | `d0148a4d49b24cd973090ab74e59b901e7ef2bc3d109cc2210f8dec536360df9` |
| Guard assertions | `tests/test_repair_plan_01_review_findings.py:390-397`, `tests/test_attachment_cleanup_expiration_a4.py:635-639` |
| Guard tokens in `attachments.py` | `asyncio` 0, `create_task` 0, `Thread(` 0, `opportunistic_cleanup` 0 |
| `store_async` anchors | lock `:526`, `async with` `:905`, `_done` `:918`, `_worker` `:921`, drain `:934` |
| T7 location | `tests/test_def011_fs_offload.py:284` |
| D6 production `.cancel()` sites | `bot/outbox.py:588`, `bot/watcher.py:161`, `bot/notifier.py:209` |
| PTB `stop()` gathers | `telegram/ext/_application.py:694` |
| App entry point | `main.py:69` → `asyncio.run(...)` |
| Owner authorization state | 0 of 17 boxes ticked; 0 signatures; no owner commit after `52e7789` |

### K.2 Supplied by the owner as conversation evidence — **no report file exists in the repository**

- The `F02_DESIGN_VALID_WITH_ANYIO_CANCELLATION_LIMITATION` verdict.
- The AnyIO 4.16.0 source findings: `checkpoint()` at `_backends/_asyncio.py:2730` preceding the
  shield at `:2744`; the worker's `if not future.cancelled():` skip at `:1121`.
- The M1–M8 matrix as designed in the prior session.
- The mutual-exclusion proof as previously stated.

These are **not independently re-verified in this documentation task** (D3/D4 are ungranted and this
task forbids re-running investigations). They must be re-verified during implementation and by the
independent reviewer.

### K.3 Report files present in the repository

`OHB2-WP07-DEF011-F02-CANCELLATION-LOCK-RACE-INVESTIGATION.md`,
`-OPTION-A-IMPLEMENTATION-REPORT.md`, `-INDEPENDENT-TECHNICAL-REVIEW-REPORT.md`,
`-PRESTART-CANCELLATION-REMEDIATION-REPORT.md`, `-PRESTART-OWNER-AUTHORIZATION-BRIEFING-REPORT.md`.

**Not present:** reports for the design investigation and the final design-safety verification — those
were delivered in conversation only.

---

## L. Remaining limitations and ambiguities

1. **The Critical pre-start regression is still live.** Nothing is fixed.
2. **Repeated raw cancellation (D6) remains unsafe** and is out of scope.
3. **Worker exceptions on the cancellation path are not propagated** to the cancelled caller
   (§B.5). Disclosed, not fixed.
4. **No timeout on the filesystem write** (§C.5). Pre-existing.
5. **AnyIO-scope scenarios (M1, M2, M13) are not reachable in production today** — no AnyIO cancel
   scopes exist in `bot/`, `main.py`, `automation/`, or `tools/`, and PTB 22.8 does not use AnyIO.
   They are defensive coverage, not reproductions of a live path.
6. **Python 3.11 is unverified.** Only 3.13.15 is available locally.
7. **No independent review exists** for any of this. This document is agent-authored.

---

**This document requests a decision. It does not make one.**
