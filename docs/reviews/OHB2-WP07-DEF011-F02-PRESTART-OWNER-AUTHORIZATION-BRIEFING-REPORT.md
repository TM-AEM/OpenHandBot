# OHB2 — WP-07 / DEF-011 / F-02 — Pre-Start Owner Authorization Briefing — Report

**Task:** `OHB2-WP07-DEF011-F02-PRESTART-OWNER-AUTHORIZATION-BRIEFING`
**Date:** 2026-11-18
**Type:** documentation only — no source, test, or decision-record change
**Verdict:** **`F02_OWNER_BRIEFING_READY`**

> **This report, and the briefing it describes, grant no permission.** No owner decision was made,
> signed, ticked, or preselected. F-02 is not implemented, not accepted, not independently reviewed,
> and not closed. WP-07 and DEF-011 remain incomplete.

---

## 1. Evidence inspected

Read in full or in the cited sections:

| Source | What was taken from it |
|---|---|
| `docs/reviews/OHB2-WP07-DEF011-F02-OPTION-A-IMPLEMENTATION-REPORT.md` (13,699 B) | the F-02 implementation as delivered, and its disclosed double-cancel limitation |
| `docs/reviews/OHB2-WP07-DEF011-F02-INDEPENDENT-TECHNICAL-REVIEW-REPORT.md` (25,267 B) | discovery of the pre-start regression; 48/48 determinism; the pre-fix vs post-fix comparison; mutation survivors M2/M4; §8 double-cancel analysis and reachability |
| `docs/reviews/OHB2-WP07-DEF011-F02-PRESTART-CANCELLATION-REMEDIATION-REPORT.md` (13,890 B) | live re-confirmation on the current hashes; `BLOCKED_OWNER_AUTHORIZATION_REQUIRED` status; the guard inventory |
| `docs/audits/OHB2-WP07-SCOPE-A-C-GRANT-AUTHORIZATION-AND-SCOPE-REPORT.md` | closest prior F-02 grant: verdict `BLOCKED`, `C-GRANT-SCOPE-A` = `- [ ]` unticked |
| `docs/audits/OHB2-WP07-BATCH04-REV2-OWNER-DECISIONS.md` | "⚠️ NOTHING IS GRANTED" precedent; the GRANT/DENY/DEFER + signature-block convention reused in §B/§F |
| `tests/test_repair_plan_01_review_findings.py` (lines 364-365, 393-396) | exact guard assertions |
| `tests/test_attachment_cleanup_expiration_a4.py` (lines 637-638) | exact guard assertions |
| `bot/attachments.py`, `bot/handlers.py`, `bot/polling.py` | `store_async` drain shape; the two competing `to_thread` call sites; the signal-handler `Event` |

### 1.1 Verified facts

| Check | Verified value |
|---|---|
| The two authorized candidate files | `bot/attachments.py`, `tests/test_def011_fs_offload.py` — and nothing else |
| `bot/attachments.py` SHA-256 | `58dbfb3a3ba9c5f23d1f6d34a06757f1a575ee9c956f54504fe4340d3e3ac93f` |
| `tests/test_def011_fs_offload.py` SHA-256 | `d0148a4d49b24cd973090ab74e59b901e7ef2bc3d109cc2210f8dec536360df9` |
| Pre-start reproduction | cancel @1 tick → cancelled, lock free; @2/3 ticks → HANG, `accept_lock_still_held=True`; watchdog fired at 12 s |
| Determinism | 48/48 hangs at ≥2 ticks (2/3/4/6 ticks × 12) |
| Pre-fix comparison | `lock_held_after_hang=False`, `new_acceptance: ACQUIRED`, `process exited cleanly` |
| 12 required regression cases | reproduced verbatim from the prior task's Phase 6 specification into briefing §B.1 |
| Guard constraints | `"asyncio" not in src`, `"create_task" not in src`, `not hasattr(StagingStore,"start"/"stop")`, `not hasattr(AttachmentReaper,"stop")`, `"opportunistic_cleanup" not in src` |
| Double-cancellation limitation | `max_concurrent_writers=2`, latent (PTB `stop()` gathers; `asyncio.run` = 1 cancel; signal handlers only set an `Event`; 3 production `.cancel()`s hit their own tasks) |
| Git state | HEAD `52e7789cc8cc97a7f7c09c9592226ab117db99a2`, branch `openhands-workspace-40xxn2SbOi0tRICb3y8TE`, divergence `0 0` |

The two hashes are byte-identical to the snapshot the technical review used, so every cited
measurement applies to exactly these bytes.

**Note on the 12 cases.** They were specified in the prior remediation task's Phase 6 and were not
enumerated inside any of the three reports. I carried them over verbatim rather than inventing a
different list; briefing §B.1 is the authoritative enumeration for the owner to decide on.

---

## 2. Exact proposed scope

Five independent permissions, each with GRANT / DENY / DEFER and **no option preselected**:

| Decision | Subject |
|---|---|
| **D1** | Modify `bot/attachments.py` to fix the pre-start cancellation regression |
| **D2** | Modify `tests/test_def011_fs_offload.py` for the 12 regression cases (+ strengthen T7) |
| **D3** | Run focused, module, attachment, and full Python suites locally |
| **D4** | Run mutation checks and applicable static/security checks |
| **D5** | Prepare the implementation report and independent-review handoff |

Plus **one separate** decision, kept out of §B on purpose:

| Decision | Subject |
|---|---|
| **D6** | Double-cancellation: `ACCEPT-AND-DOCUMENT` **or** `DEFER-TO-SEPARATE-INVESTIGATION` |

**File scope is exactly two files**, plus the decision-5 report/handoff document. §C of the briefing
lists 16 mandatory constraints (guards preserved, DEF-011-B preserved, SQLite on the loop thread, FS
off the loop thread, pending/reaper preserved, no schema/deps/workers/queues/outboxes, no Mini App
changes, no changes outside the two files, no Git staging/commit/branch/push/PR/merge/deploy/CI, no
Autopush, no false cancellation-safety claims, no test weakening, no unverified 3.11 claim).

The briefing also separates **measured** evidence (the wedge, its determinism, the pre-fix
comparison) from **inferred** risk (production frequency, real-world shutdown hang, blast radius),
and states plainly that no production occurrence was observed.

---

## 3. Authorization status

### Before this task

| Item | State |
|---|---|
| Owner authorization for the pre-start remediation | **ABSENT** |
| `C-GRANT-SCOPE-A` | **`- [ ]` unticked** |
| Ticked boxes in `docs/audits/`, `docs/decisions/` | **0** |
| Owner signature/date fields | **13 blank** |
| Owner commit after `52e7789` | **none** |

### After this task

**Unchanged — still ABSENT.** A briefing is a request, not a grant. Writing it cannot and does not
create authorization.

| Item | State |
|---|---|
| Owner authorization for the pre-start remediation | **STILL ABSENT** |
| Ticked boxes in the new briefing | **0 of 17** |
| Signature/date fields in the new briefing | **6, all blank** |
| D6 double-cancellation choice | **blank** |
| Existing decision records modified | **none** |

---

## 4. Files created

| File | Purpose |
|---|---|
| `docs/audits/OHB2-WP07-DEF011-F02-PRESTART-OWNER-AUTHORIZATION-BRIEFING.md` | the owner decision request (§A problem, §B five permissions, §C constraints, §D double-cancel, §E review/acceptance, §F blank signature block, §G status, §H evidence sources) |
| `docs/reviews/OHB2-WP07-DEF011-F02-PRESTART-OWNER-AUTHORIZATION-BRIEFING-REPORT.md` | this report |

No other file was created, modified, or deleted.

---

## 5. Phase 3 verification

| Requirement | Result | Evidence |
|---|---|---|
| Does not claim authorization | **Pass** | Banner "⚠️ NOTHING IS AUTHORIZED BY THIS DOCUMENT"; §G table records authorization ABSENT; closing line "This document requests a decision. It does not make one." |
| Does not grant permissions by default | **Pass** | `grep -c '^- \[x\]'` = **0**; `grep -c '^- \[ \]'` = **17** (5×3 + 2) |
| Does not modify existing decision records | **Pass** | `git status --porcelain docs/audits/ docs/decisions/` shows only `??` (pre-existing untracked); **zero ` M`** |
| Does not alter source or test files | **Pass** | `bot/attachments.py` = `58dbfb3a…`, `tests/test_def011_fs_offload.py` = `d0148a4d…` — identical before and after |
| Does not expand scope to unrelated WP-07 findings | **Pass** | `grep -cE "DEF-006|NAV-0|NEW-DEF-03|WP-09|DEF-013"` = **0** |
| Signature fields left blank | **Pass** | 6 `Owner signature / date: ______________________` lines; 0 filled dates; 0 signatures; D6 line blank |
| Guard files untouched | **Pass** | `git status --porcelain` on all four guard files is empty |
| `.openhands/` and `.agent/` preserved | **Pass** | both present and untouched (`.agent/PROGRESS.md` retains its pre-existing ` M` from an earlier task, not from this one) |

---

## 6. Git state

| Property | Before | After |
|---|---|---|
| HEAD | `52e7789` | `52e7789` (unchanged) |
| Branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` | unchanged |
| Divergence vs `origin/main` | `0 0` | `0 0` |
| Staged | 0 | **0** |
| Modified | 8 | **8** (all pre-existing, none touched by me) |
| Untracked | 60 | **61** (+1 = the briefing) |
| Ignored | 8 | 8 |

The 8 modified files are pre-existing work from earlier tasks: `.agent/PROGRESS.md`, `bot/app.py`,
`bot/attachments.py`, `bot/db.py`, `bot/handlers.py`, `bot/watcher.py`, `tests/test_handlers.py`,
`tests/test_sw06_unwatch_db_failure_propagation.py`. `bot/attachments.py`'s hash is unchanged, so its
` M` status is the pre-existing DEF-011-B work, not an edit by this task.

No stage, commit, branch, push, PR, merge, deploy, release, CI change, or visibility change. Autopush
not activated.

---

## 7. Explicit statement

**The briefing grants no permission.** It presents five separate decisions (D1–D5) and one separate
double-cancellation decision (D6), each with GRANT / DENY / DEFER left unselected and unsigned. It
does not infer authorization from the prior F-02 implementation approval, from the technical review's
recommendation, or from the task that produced it.

**What the owner still must decide:**

1. D1 — modify `bot/attachments.py` (GRANT/DENY/DEFER)
2. D2 — modify `tests/test_def011_fs_offload.py` for the 12 cases (GRANT/DENY/DEFER)
3. D3 — run the test suites (GRANT/DENY/DEFER)
4. D4 — run mutation and static/security checks (GRANT/DENY/DEFER)
5. D5 — prepare the implementation report and handoff (GRANT/DENY/DEFER)
6. D6 — double-cancellation: accept-and-document **or** defer to a separate investigation
7. Signature and date

---

## 8. Remaining limitations

1. **The Critical pre-start regression is still live in the working tree.** Nothing was fixed.
2. **No independent review** of the briefing or of anything else. Independence is not established in
   this environment (same host, user, filesystem; no Docker socket; no second agent-server; no
   reviewer LLM profile).
3. **Production frequency and real shutdown impact are inferred, not measured** — stated as such in
   briefing §A.5.
4. **Test coverage gaps remain** (M2/M4 mutants survive; no test covers cancel-before-start).
5. **Python 3.11 not verified** — only 3.13.15 available. No 3.11 claim is made.

---

## 9. Final verdict

```
F02_OWNER_BRIEFING_READY
```

The briefing is complete, evidence-backed, scope-tight, and grants nothing. The owner now has the
precise decision set needed to unblock the remediation.

This verdict means **only** that the briefing is ready. It does **not** mean F-02 is implemented,
accepted, independently reviewed, or closed, and it does not mean WP-07 or DEF-011 is complete.
