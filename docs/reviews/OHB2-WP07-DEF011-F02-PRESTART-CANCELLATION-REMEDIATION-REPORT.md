# OHB2 — WP-07 / DEF-011 / F-02 — Pre-Start Cancellation Regression Remediation

**Task:** `OHB2-WP07-DEF011-F02-PRESTART-CANCELLATION-REGRESSION-REMEDIATION`
**Date:** 2026-11-18
**Verdict:** **`F02_BLOCKED_OWNER_AUTHORIZATION_REQUIRED`**

> **No source or test file was modified.** The Phase 0 authorization gate failed: there is no
> explicit, signed owner authorization for this remediation anywhere in the repository. Per the
> task's own Phase 0 rule, work stopped before any change to `bot/attachments.py` or
> `tests/test_def011_fs_offload.py`.
>
> The regression itself **is real and is still live** — I re-confirmed it read-only against the
> current file hashes (§3). This report exists so the owner can authorize the fix with full evidence
> in hand. Nothing here claims F-02 is fixed, closed, reviewed, or accepted.

---

## 1. Authorization evidence — GATE FAILED

### 1.1 What was searched

| Source | Result |
|---|---|
| `docs/decisions/` (owner decision records) | no F-02 remediation grant |
| `docs/audits/` (authorization briefings, grants, decisions) | no signed grant |
| `docs/reviews/` (implementation + review reports) | recommendation only, explicitly **not** authorization |
| `.agent/PROGRESS.md` (413 KB, full history) | no grant marker for this task |
| `.openhands/` (agent memory) | no grant |
| `git log` | no owner commit after `52e7789` |
| Task name string in any doc | **not found** |

### 1.2 Signed-authorization checks

| Check | Result |
|---|---|
| Ticked decision checkboxes (`- [x]`) in `docs/audits/`, `docs/decisions/` | **0** — nothing is ticked |
| Owner signature / date fields | **13 blank `______________________` placeholders, none filled** |
| `GRANTED` / `SIGNED` / `APPROVED` markers attributable to this scope | **none** |
| `C-GRANT-SCOPE-A` checkbox (the closest prior F-02 grant) | **`- [ ]` unticked** |

### 1.3 The closest existing documents, and why neither authorizes this work

1. **`docs/audits/OHB2-WP07-SCOPE-A-C-GRANT-AUTHORIZATION-AND-SCOPE-REPORT.md`** — verdict
   `BLOCKED_OWNER_AUTHORIZATION_REQUIRED`. It states plainly that `C-GRANT-SCOPE-A` is **NOT
   signed**: 0 ticked boxes, blank signature/date, and all five requested permissions
   (branch / commit / push / PR / CI) **NOT GRANTED**. It even records that the report's own
   mtime is an agent write, not an owner edit.
2. **`docs/audits/OHB2-WP07-BATCH04-REV2-OWNER-DECISIONS.md`** — carries the banner
   *"⚠️ NOTHING IS GRANTED — Every checkbox in §10 is empty on purpose. This document asks; it does
   not authorize."* Its four signature blocks are blank.

### 1.4 Explicitly rejected as authorization

Per the task's instruction, I did **not** treat any of the following as authorization:

* this prompt itself;
* the earlier F-02 implementation authorization (a different, completed task);
* the technical review's recommendation **C** — §11 of
  `OHB2-WP07-DEF011-F02-INDEPENDENT-TECHNICAL-REVIEW-REPORT.md` says *"I have not implemented any of
  this"* and its §356/§400 only *recommends* a corrective change;
* any agent-authored document, `PROGRESS.md` entry, or prior `PARTIAL` verdict.

**Conclusion: the gate fails. Required authorization is absent.**

---

## 2. Baseline and preservation evidence (Phase 1, read-only)

| Property | Value |
|---|---|
| Repository root | `/workspace/project/OpenHandBot` |
| Branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` |
| HEAD | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| Divergence vs `origin/main` | `0  0` |
| Staged | `0` |
| Modified | `8` |
| Untracked | `59` |
| Ignored | `8` |
| `bot/attachments.py` SHA-256 | `58dbfb3a3ba9c5f23d1f6d34a06757f1a575ee9c956f54504fe4340d3e3ac93f` |
| `tests/test_def011_fs_offload.py` SHA-256 | `d0148a4d49b24cd973090ab74e59b901e7ef2bc3d109cc2210f8dec536360df9` |

Both hashes are **identical** to the frozen snapshot the independent technical review used, so the
regression evidence in §3 applies to exactly these bytes.

**Ownership of existing diffs.** `git diff origin/main -- bot/attachments.py` is `410 insertions /
104 deletions` across 7 hunks — a large body of **pre-existing, uncommitted DEF-011-B work**
(`store_async`, reaper, offload refactor). Only two hunks belong to F-02:
`@@ -72,16 +72,21 @@` (`+import threading`) and `@@ -807,6 +793,156 @@` (the `_done` / `_box` / `_worker`
drain block). The other five hunks are unrelated DEF-011-B changes that must be preserved.

**Architectural guard tests — unmodified, and here is what they enforce:**

| File | Assertion |
|---|---|
| `tests/test_repair_plan_01_review_findings.py:393` | `assert "asyncio" not in src` |
| `tests/test_repair_plan_01_review_findings.py:394` | `assert "create_task" not in src` |
| `tests/test_repair_plan_01_review_findings.py:395` | `assert not hasattr(StagingStore, "start")` |
| `tests/test_repair_plan_01_review_findings.py:364-365` | `assert "opportunistic_cleanup" not in src`; `assert not hasattr(StagingStore, "opportunistic_cleanup")` |
| `tests/test_attachment_cleanup_expiration_a4.py:637-638` | `assert "asyncio" not in src`; `assert "create_task" not in src` |

`git status` on all four guard files is **empty** — untouched.

---

## 3. Reproduction of the original regression (Phase 2, read-only)

Re-confirmed live against the current hashes, using deterministic event-loop tick control (no
arbitrary sleeps as the proof mechanism), bounded by a watchdog:

```
=== live re-confirmation (read-only) ===
  cancel after 1 tick(s): outcome=cancelled  accept_lock_still_held=False
  cancel after 2 tick(s): outcome=HANG       accept_lock_still_held=True
  cancel after 3 tick(s): outcome=HANG       accept_lock_still_held=True
  WATCHDOG: probe exceeded 12s -> something is blocked
```

**The finding reproduces exactly as the review reported.** One tick lets the worker start (safe);
two or more ticks land in the pre-start window and wedge `_accept_lock` permanently.

Root cause (previously established, unchanged): `anyio`'s `run_sync_in_worker_thread` executes
`await cls.checkpoint()` at `_backends/_asyncio.py:2730` **before** acquiring the capacity limiter
and creating the worker thread. A cancellation in that window means `_worker` never runs, so
`_done.set()` never executes, and the drain's `to_thread.run_sync(_done.wait)` blocks forever while
holding `_accept_lock`.

| Case | Worker started | Completion signal set | Accepting coroutine terminated | Lock released | 2nd acceptance proceeds | Process shuts down |
|---|---|---|---|---|---|---|
| Cancel before worker begins (≥2 ticks) | **No** | **No** | **No** | **No** | **No** | **No** |
| Cancel after worker began (1 tick) | Yes | Yes | Yes | Yes | Yes | Yes |

The "at boundary" / "during completion" cases were **not** re-run in this session because the gate
failed; the prior review already covered them (boundary ×50 clean, stress ×60 clean). I did not
extend testing beyond what the blocker required.

---

## 4. What was NOT done — and why

| Phase | Status | Reason |
|---|---|---|
| 0 — Authorization gate | **FAILED** | No signed owner authorization (§1) |
| 1 — Baseline & preservation | **DONE** (read-only) | §2 |
| 2 — Reproduce regression | **DONE** (read-only, partial matrix) | §3 |
| 3 — Lifecycle protocol design | **NOT STARTED** | Gated on Phase 0 |
| 4 — Architectural guards | **INSPECTED only** (read-only) | §2; no change made |
| 5 — Implementation | **NOT PERFORMED** | Gated on Phase 0 |
| 6 — Regression tests | **NOT ADDED** | Gated on Phase 0 |
| 7 — Double-cancel boundary | **NOT INVESTIGATED** | Gated on Phase 0 |
| 8 — Validation | **NOT RUN** (beyond the read-only probe) | Gated on Phase 0 |
| 9 — Scope audit | **DONE** | §6 |

I deliberately did not "prepare" the fix in the working tree, because an uncommitted partial change
would alter the baseline the owner is being asked to authorize.

---

## 5. Design sketch for the owner to consider (NOT implemented, NOT validated)

Offered only to make the authorization decision concrete. **Nothing here is verified**, and the
task explicitly warns against assuming a `finally`-block `Event` alone solves the problem.

The invariant to preserve is: *the lock must never be released while a worker is active, and must
never be held waiting on a worker that never started.* That requires distinguishing the states the
task lists (§Phase 3 items 1–6), in particular **"submitted but not yet executing"** versus
**"executing"**. A sketch that stays inside the current guards:

1. Record an explicit "worker actually entered" flag as the **first statement inside `_worker`**
   (the worker runs in the thread, so this flag is only set once the thread body really starts).
2. On cancellation, consult that flag: if the worker never entered, **do not drain** — release
   immediately, since there is no in-flight writer to wait for.
3. If the worker did enter, drain as today, but with a **bounded** wait so the caller can never block
   unboundedly.

This uses no `asyncio`, no `create_task`, no task group, no new worker/queue/thread, and adds no
dependency — so it should satisfy the five guard assertions in §2. **Whether it fully closes the
window must be proven by reproduction, not assumed.** I have not written or tested it.

---

## 6. Scope and diff audit (Phase 9)

| Check | Result |
|---|---|
| `bot/attachments.py` modified by this task | **No** — hash unchanged `58dbfb3a…` |
| `tests/test_def011_fs_offload.py` modified by this task | **No** — hash unchanged `d0148a4d…` |
| Any other source/test file modified | **No** |
| Pre-existing DEF-011-B changes intact | **Yes** — untouched |
| Architectural guard files unchanged | **Yes** — `git status` empty |
| Schema changes | **None** |
| Dependency changes | **None** — nothing installed |
| Mini App changes | **None** |
| New workers / queues / services | **None** |
| Owner decision records modified | **None** |
| `.openhands/` preserved | **Yes** — untouched |
| Staged / committed / branched / pushed / PR / merged / deployed | **None** |
| Autopush activated | **No** |

Files added by this task: **this report only.**

---

## 7. Double-cancellation status (Phase 7)

**Unchanged and unfixed.** The second-raw-cancel limitation described in
`OHB2-WP07-DEF011-F02-INDEPENDENT-TECHNICAL-REVIEW-REPORT.md` §8 (a second cancellation cancels the
drain wait itself, releasing the lock while the worker is still writing, allowing two concurrent
writers) remains **exactly as reviewed**.

* Reproduced previously: `max_concurrent_writers=2`, real overlap.
* Reachability unchanged: PTB `stop()` gathers rather than cancels (0 cancels), `asyncio.run`
  teardown delivers 1 cancel, app signal handlers only set an `Event`, and the 3 production
  `.cancel()` calls target their own components' worker tasks.
* It is **latent** under the current production path, and would become reachable with any future
  `wait_for` wrapper or an extra cancel-on-shutdown layer.

I make **no claim** that this is fixed, and no new mechanism was added to address it.

---

## 8. Remaining limitations

1. **The Critical pre-start regression is still live in the working tree** (§3). Attachment intake
   can be permanently wedged and process shutdown blocked by a single cancellation.
2. **Test coverage gaps remain** (from the prior review): mutation M2 (completion signal not set on
   the exception path) and M4 (swallowed worker error) both survive the current suite, and no test
   covers cancellation before the worker starts.
3. **Double-cancel limitation** remains (§7).
4. **Python 3.11 not verified** — only 3.13.15 is available locally. No 3.11 claim is made.
5. **No independent review** of anything in this report.

---

## 9. Independent review status

**None.** This report is agent-authored. Reviewer-session and environment independence remain
**not established** in this environment (same host, same user, same filesystem, no Docker socket, no
second agent-server, no reviewer LLM profile) — the same limitation documented in
`OHB2-WP07-DEF011-F02-INDEPENDENT-TECHNICAL-REVIEW-REPORT.md` §1.

Nothing in this report has been independently verified.

---

## 10. Git and publication status

* HEAD `52e7789cc8cc97a7f7c09c9592226ab117db99a2`, divergence `0 0` — **unchanged**.
* `staged=0`, `modified=8`, `untracked=59` (was 58; the +1 is this report), `ignored=8`.
* **No** commit, stage, branch, push, PR, merge, deploy, release, CI change, or visibility change.
* Autopush **not** activated.

---

## 11. What the owner must provide to unblock

A signed authorization that explicitly permits **all** of the following, for this exact task:

1. Modification of **`bot/attachments.py`**.
2. Modification of **`tests/test_def011_fs_offload.py`**.
3. Remediation of the **pre-start cancellation regression** (the §3 defect).
4. Addition of the **12 required regression tests** and the mutation checks (Phase 6).
5. Confirmation that **no** guard test may be weakened, and that **no** new
   worker/queue/service/dependency/schema change is permitted.

A workable place to record it is a new signed block in
`docs/audits/OHB2-WP07-SCOPE-A-C-GRANT-AUTHORIZATION-AND-SCOPE-REPORT.md` §6 (currently
signature-ready and blank) or a fresh owner-decision record — either is acceptable; I have not
edited or signed anything.

---

## 12. Final verdict

```
F02_BLOCKED_OWNER_AUTHORIZATION_REQUIRED
```

The authorization gate in Phase 0 failed: no signed owner authorization exists for this remediation
(§1). Per the task's own rule, work stopped before any source or test change.

The regression is real, reproducible, and still live (§3) — so this blocker is a genuine
availability risk, not a formality. F-02 is **not** fixed, **not** closed, **not** independently
reviewed, and **not** owner-accepted. WP-07 and DEF-011 remain incomplete.
