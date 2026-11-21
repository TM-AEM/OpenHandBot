# OHB2 — WP-07 / DEF-011 / F-02 — Final Owner Decision — Report

**Task:** `OHB2-WP07-DEF011-F02-FINAL-OWNER-DECISION-AND-IMPLEMENTATION-SPEC`
**Date:** 2026-11-18
**Type:** documentation only — no source, test, guard, schema, Mini App, config, or dependency change
**Verdict:** **`F02_FINAL_OWNER_DECISION_READY_WITH_NOTES`**

> **Neither this report nor the decision document it describes grants any permission.** No owner
> decision was made, signed, ticked, or preselected. F-02 is not implemented, not independently
> reviewed, not owner-accepted, and not closed. WP-07 and DEF-011 remain incomplete.
>
> The verdict carries `_WITH_NOTES` rather than plain `_READY` because two findings in the
> specification are sourced from conversation only and have **no report file in the repository**
> (§2.2), and one behavioural limitation (worker errors not propagated on the cancellation path) had
> to be disclosed rather than specified away (§5).

---

## 1. Deliverables

| # | File | Size | Purpose |
|---|---|---|---|
| 1 | `docs/audits/OHB2-WP07-DEF011-F02-FINAL-OWNER-DECISION.md` | 18,238 B | the authoritative owner decision document (§A–§L) |
| 2 | `docs/reviews/OHB2-WP07-DEF011-F02-FINAL-OWNER-DECISION-REPORT.md` | this file | provenance, verification, and status report |

No other file was created, modified, or deleted.

---

## 2. Evidence sources and provenance

### 2.1 Read from the repository in this session

| Source | Used for |
|---|---|
| `docs/audits/OHB2-WP07-DEF011-F02-PRESTART-OWNER-AUTHORIZATION-BRIEFING.md` | prior request framing; confirmed still 0/17 ticked |
| `docs/reviews/OHB2-WP07-DEF011-F02-PRESTART-OWNER-AUTHORIZATION-BRIEFING-REPORT.md` | prior report structure and provenance discipline |
| `docs/reviews/OHB2-WP07-DEF011-F02-CANCELLATION-LOCK-RACE-INVESTIGATION.md` | original root-cause analysis and remediation options A–D |
| `docs/reviews/OHB2-WP07-DEF011-F02-INDEPENDENT-TECHNICAL-REVIEW-REPORT.md` | the regression discovery, 48/48 determinism, pre-fix comparison |
| `docs/reviews/OHB2-WP07-DEF011-F02-PRESTART-CANCELLATION-REMEDIATION-REPORT.md` | live re-confirmation, blocker status |
| `docs/reviews/OHB2-WP07-DEF011-F02-OPTION-A-IMPLEMENTATION-REPORT.md` | the F-02 implementation as delivered |
| `bot/attachments.py` | `store_async` anchors, guard tokens, lock/Event/worker structure |
| `tests/test_def011_fs_offload.py` | T7 at `:284` and its synchronization mechanism |
| `tests/test_repair_plan_01_review_findings.py:390-397` | exact guard assertions |
| `tests/test_attachment_cleanup_expiration_a4.py:635-639` | exact guard assertions |

### 2.2 Supplied by the owner as conversation evidence — **no report file exists**

The task's own Phase 1 anticipated this: *"Use the latest investigation findings supplied by the
owner as authoritative conversation evidence where corresponding reports are not present in the
repository."* Confirmed by directory listing — only these F-02 review files exist:

```
CANCELLATION-LOCK-RACE-INVESTIGATION.md
INDEPENDENT-TECHNICAL-REVIEW-REPORT.md
OPTION-A-IMPLEMENTATION-REPORT.md
PRESTART-CANCELLATION-REMEDIATION-REPORT.md
PRESTART-OWNER-AUTHORIZATION-BRIEFING-REPORT.md
```

There is **no** report for the design investigation or for the final design-safety verification.
Therefore the following are recorded in the decision document as **conversation-sourced**, in a
dedicated section (§K.2), explicitly not re-verified:

- the `F02_DESIGN_VALID_WITH_ANYIO_CANCELLATION_LIMITATION` verdict;
- the AnyIO 4.16.0 source findings (`checkpoint()` at `_backends/_asyncio.py:2730` preceding the
  shield at `:2744`; the worker's `if not future.cancelled():` skip at `:1121`);
- the M1–M8 matrix design;
- the mutual-exclusion proof as previously stated.

**This distinction is the main note behind the `_WITH_NOTES` verdict.** I did not re-run those
investigations (forbidden by this task and by the absent D3/D4).

---

## 3. Current source hashes (verified without modifying files)

| File | SHA-256 |
|---|---|
| `bot/attachments.py` | `58dbfb3a3ba9c5f23d1f6d34a06757f1a575ee9c956f54504fe4340d3e3ac93f` |
| `tests/test_def011_fs_offload.py` | `d0148a4d49b24cd973090ab74e59b901e7ef2bc3d109cc2210f8dec536360df9` |

Identical before and after this task.

---

## 4. Exact source/test scope

### 4.1 Permitted by D1/D2

| File | Permitted change |
|---|---|
| `bot/attachments.py` | `store_async` only |
| `tests/test_def011_fs_offload.py` | the §F test matrix |

### 4.2 Prohibited (stated explicitly in the decision document §E.2)

`_store_prepare`, `_store_finalize`, `_write_to_path`, `_safe_unlink`, schema, Mini App, guard
tests, and every file outside the two above (except the D5 report).

---

## 5. Test matrix completeness

### 5.1 Coverage

The decision document §F specifies **18 core cases + M1–M8 = 26 tests**. Mapping to the task's
required list:

| Task requirement | Test # |
|---|---|
| Cancellation before submission | 1 |
| Cancellation at the initial AnyIO checkpoint | 2 |
| Cancellation while waiting for the thread limiter | 3 |
| Cancellation after submission, before worker execution | 4 |
| Cancellation after worker start | 5 |
| Cancellation during filesystem writing | 6 |
| Worker success after caller cancellation | 7 |
| `OSError` on the cancellation path | 8 |
| Unexpected worker exception | 9 |
| Unconditional completion signaling | 10 |
| Early abandonment without waiting | 11 |
| No overlapping acceptance while a worker is active | 12 |
| AnyIO scope already cancelled when drain begins | 13 (M2) |
| AnyIO cancellation during the drain | 14 (M1) |
| Lock release after every permitted exit path | 15 (M7) |
| Shutdown completion with a pending single cancellation | 16 (M8) |
| T7 strengthened so it does not assume worker started | 17 |
| Static proof that no `await` occurs while holding the gate | 18 (M6) |

Every one of the 18 required items is covered. M3, M4, M5 add the remaining investigation cases
(cancellation entering the handler, worker exception during drain, `_done` on early exit).

### 5.2 Per-test specification

Each test in §F.1/§F.2 carries: synchronization mechanism, exact injection point, expected lock
state, whether the worker may write, expected DB status (`pending`/`stored`), and a bounded
watchdog (2 s, or 5 s for shutdown/concurrency cases).

### 5.3 Mandatory weakness disclosure

§F.3 records that the current T7 (`tests/test_def011_fs_offload.py:284`) sets its `started` event
**inside** the write function and spins `while not started.is_set()`, which guarantees the worker is
already executing before the cancel lands. **T7 therefore cannot detect any pre-start window** and
would give false assurance if used alone. Test 17 must add the pre-start variants.

---

## 6. Unresolved ambiguity

| # | Ambiguity | Resolution taken |
|---|---|---|
| 1 | Whether the drain shield (`anyio.CancelScope(shield=True)`) is **mandatory** or optional hardening | Specified as required structure (§C.2), because it closes an identified limitation at zero guard cost |
| 2 | Whether worker errors must propagate on the cancellation path | **Not achievable without changing fail-closed semantics.** Disclosed as a limitation (§B.5) rather than specified as a requirement |
| 3 | Whether the filesystem write should gain a timeout | **Out of scope** — pre-existing behaviour; recorded as limitation (§C.5) |
| 4 | Whether M1/M2 (AnyIO-scope cases) are meaningful when no AnyIO scopes exist in production | Kept as defensive coverage; noted as not production-reachable (§L.5) |

---

## 7. D6 status

**Unresolved and out of scope.** Two choices only:

- `ACCEPT_AND_DOCUMENT_LIMITATION`
- `DEFER_TO_SEPARATE_INVESTIGATION`

Both left blank. Neither authorizes implementation. The document states plainly that repeated raw
cancellation is **not fixed, not safe, and not made safe** by this specification.

---

## 8. Owner authorization status

### Before this task

| Item | State |
|---|---|
| Ticked boxes in the briefing | **0 / 17** |
| Ticked boxes across `docs/audits/` + `docs/decisions/` | **0** |
| Owner signatures / dates | **0 filled** |
| Owner commit after `52e7789` | **none** |

### After this task

**Unchanged — still ABSENT.** A decision document is a request; writing it cannot create
authorization.

| Item | State |
|---|---|
| Ticked boxes in the new decision document | **0 / 17** |
| Signature/date fields in the new document | **6, all blank** |
| D6 choice | **blank** |
| Existing decision records modified | **none** |

---

## 9. Git status

| Property | Before | After |
|---|---|---|
| HEAD | `52e7789` | `52e7789` |
| Branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` | unchanged |
| Divergence vs `origin/main` | `0 0` | `0 0` |
| Staged | 0 | **0** |
| Modified | 8 | **8** (all pre-existing) |
| Untracked | 62 | **64** (+2 = the two documents) |
| Ignored | 8 | 8 |

The 8 pre-existing modified files (`.agent/PROGRESS.md`, `bot/app.py`, `bot/attachments.py`,
`bot/db.py`, `bot/handlers.py`, `bot/watcher.py`, `tests/test_handlers.py`,
`tests/test_sw06_unwatch_db_failure_propagation.py`) are untouched by this task;
`bot/attachments.py`'s hash is unchanged, so its ` M` status is pre-existing DEF-011-B work.

No stage, commit, branch, push, PR, merge, deploy, release, CI, or visibility change. Autopush not
activated. `.openhands/` and `.agent/` preserved.

---

## 10. Confirmation that no source or test file changed

- `bot/attachments.py` — `58dbfb3a…` **before and after**: unchanged.
- `tests/test_def011_fs_offload.py` — `d0148a4d…` **before and after**: unchanged.
- Guard tests — `git status` empty for all four guard files.
- No tests run, no mutation checks run, no reproductions run.
- No dependencies installed, no schema touched, no Mini App touched.

---

## 11. Remaining limitations

1. **The Critical pre-start regression is still live.** Nothing is fixed.
2. **Repeated raw cancellation (D6) remains unsafe.**
3. **Worker exceptions are not propagated on the cancellation path** (§B.5) — disclosed.
4. **No filesystem timeout** on the write (§C.5) — pre-existing.
5. **AnyIO-scope scenarios are not production-reachable** — no AnyIO cancel scopes exist in
   `bot/`, `main.py`, `automation/`, or `tools/`, and PTB 22.8 does not use AnyIO.
6. **Python 3.11 unverified** — only 3.13.15 available.
7. **No independent review** of this document or of the design.

---

## 12. Final verdict

```
F02_FINAL_OWNER_DECISION_READY_WITH_NOTES
```

The decision document is complete, internally consistent, scope-tight, and grants nothing. It is
marked `_WITH_NOTES` because:

- the two most recent investigation findings exist only as conversation evidence, with no repository
  report (provenance is disclosed in §K.2 rather than presented as verified fact);
- the worker-error propagation limitation had to be disclosed rather than specified away.

This verdict means **only** that the owner decision document is ready for the owner. It does **not**
mean F-02 is implemented, independently reviewed, owner-accepted, or closed, and it does not mean
WP-07 or DEF-011 is complete.
