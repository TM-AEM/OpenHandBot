# OHB2 — WP-07 / Batch 04 — Authorization Readiness Report

**Task:** `OHB2-WP07-BATCH04-OWNER-AUTHORIZATION-READINESS`
**Date:** 2026-11-19
**Mode:** read-only inspection + two documentation deliverables. **No publication, transfer,
Git mutation, CI trigger, or external disclosure occurred.**
**Companion:** `docs/audits/OHB2-WP07-BATCH04-OWNER-AUTHORIZATION-BRIEFING.md`

> **F-01 is NOT independently reviewed, NOT accepted, and NOT closed.**
> **DEF-011 is NOT closed.** Nothing in this report changes that.

---

## 0. Verdict

# `OWNER_AUTHORIZATION_BRIEFING_READY_WITH_NOTES`

The evidence is **sufficient for an owner decision** on *which route*, but two material
findings must be recorded as notes before any handoff:

- **NOTE-1 (scope):** "publish only the F-01 scope" is **not achievable** — `bot/attachments.py`
  carries unreviewed Batch-03 DEF-011-B work in the same file. Measured: **DEF-011-B +245/−59**
  (`origin/main` → Batch-03 snapshot) plus **F-01 +162/−65** (Batch-03 snapshot → worktree),
  totalling **+386/−103** vs `origin/main`. Any Route A disclosure is **broader** than F-01.
- **NOTE-2 (packaging):** the Batch-04 package is **not self-sufficient** — omitting
  `bot/handlers.py` (and the diff) makes the package's own test suite fail **1/34** from a clean
  `origin/main` tree, while the real working tree passes **34/34**.

Neither note blocks a decision; both change what must be authorized.

---

## 1. Baseline documents — presence reconciliation

All mandatory inputs were present. **None was missing; none was reconstructed.**

| Document | Status | Size |
|---|---|---|
| `docs/audits/OHB2-WP07-DEF011-REMEDIATION-AUDIT.md` | PRESENT | 22 635 B |
| `docs/audits/OHB2-WP07-DEF011-IMPLEMENTATION-PLAN.md` | PRESENT | 15 516 B |
| `docs/reviews/OHB2-WP07-BATCH03-EXTERNAL-REVIEW-HANDOFF-REPORT.md` | PRESENT | 18 101 B |
| `docs/reviews/OHB2-WP07-BATCH03-EXTERNAL-REVIEW-CHECKLIST.md` | PRESENT | 7 661 B |
| `docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md` | PRESENT | 16 778 B |
| `/workspace/review-packages/OHB2-WP07-BATCH04-EXTERNAL-REVIEW-ENVIRONMENT-REPORT.md` | PRESENT | 18 130 B |
| Batch-04 archive | PRESENT | 107 643 B |
| Batch-04 sidecar | PRESENT | 111 B |

### 1.1 What the baseline documents establish (reconciled, not assumed)

- **DEF-011 has three sub-defects** (audit §2.2): **A** quota/reservation ledger (WP-07,
  inert by default under D-12; unreachable while dispatch is sequential per OD-04), **B**
  synchronous filesystem I/O on the event loop (WP-07), **C** misleading acceptance UX copy
  (**WP-01**, blocked on OD-01/OD-03).
- **Batch 03** implemented **B** and flagged **N-1** (A not implemented), **N-2** (C is WP-01),
  **N-3** (OD-04 unratified), **N-4** (WP-09 unverified).
- **Batch 04** fixed **F-01** — the reaper's `_remove_file` (`os.lstat`/`os.unlink`) running on
  the event loop — by making `_sweep_db_phase` return a plan and moving deletion into
  `_sweep_fs_tail` on a worker thread.
- **F-02** (lock released while worker writes on cancellation) and **F-03** (stale acceptance
  doc) are **open**, explicitly out of Batch-04 scope.

**No contradiction found** between the audit, the plan and the Batch-03/04 reports on scope.
The Batch-03 checklist's `DEF-011` decomposition matches the audit §2.2 exactly.

---

## 2. Phase 1 — Revalidated current state (re-derived, not copied)

### 2.1 Git

| Field | Value |
|---|---|
| Branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` |
| HEAD | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| `origin/main` | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| Staged / Modified / Untracked / Ignored | **0 / 8 / 40 / 8** |
| New changes since env-discovery report? | **NO** (report recorded 8 / 40) |

### 2.2 F-01 files (exact SHA-256)

| File | State | SHA-256 |
|---|---|---|
| `bot/attachments.py` | modified | `d27fb79870d900f584aebfea861619f6e4000ba1b9cb026d359189ae1e914ed5` |
| `tests/test_f01_reaper_fs_offload.py` | untracked | `0caa88c6e8c3cae176d90464d2f46e1495e6512fa282c33bdc795daf01fdae2e` |
| `tests/test_def011_fs_offload.py` | untracked | `db0f5b6177a7a51652a19be71c27dca56ce97182b1b09966f1dd2e97d3a7e99f` |

### 2.3 Package

| Check | Result |
|---|---|
| Archive size / SHA-256 | `107643` B / `47b992300ec1bd5efec8c6c95afff4a63815a58ccd25f254975939f53f0bf71d` |
| Sidecar `sha256sum -c` | **OK** |
| `MANIFEST.sha256` from fresh extraction | **8/8 OK** |
| Unchanged since previous report | **YES** (same size, digest, mtime) |
| Snapshot == current worktree (3 code files + report) | **YES** (all 4 hashes match) |
| Archive hygiene | 17 entries, relative only, no traversal, no symlinks |

### 2.4 Public repo / CI unchanged

- Visibility **public** (read-only API, unchanged).
- `.github/workflows/ci.yml` identical to `origin/main` (`e2edadf0…`).
- Triggers `push:[main]`, `pull_request:[main]` — **no `workflow_dispatch`**.
- `pushed_at 2026-11-18T18:35:36Z` — no push since Batch 03.

---

## 3. Checks performed (with real results)

| # | Check | Command (abbreviated) | Result |
|---|---|---|---|
| 1 | Archive digest | `sha256sum <archive>` | `47b9923…0bf71d` |
| 2 | Sidecar verify | `sha256sum -c <sidecar>` | OK |
| 3 | Manifest verify | `sha256sum -c MANIFEST.sha256` | **8/8 OK** |
| 4 | Archive↔worktree equality | hash compare, 4 files | **all MATCH** |
| 5 | Archive hygiene | `tar tzf` | 17 entries, no traversal, no symlinks |
| 6 | Repo visibility | read-only API | `public` |
| 7 | CI config vs `origin/main` | `git diff --quiet` | identical |
| 8 | F-01 delta isolation | `git diff --shortstat origin/main -- bot/attachments.py` | **+386/−103** total; split measured below |
| 8b | Delta split (measured) | `diff -u` between `origin/main`, Batch-03 snapshot, worktree | DEF-011-B **+245/−59**; F-01 **+162/−65** |
| 9 | DEF-011-B presence on `origin/main` | `git show origin/main:bot/attachments.py \| grep -c "async def store_async"` | **0** ⇒ Batch-03 work is local-only |
| 10 | Package self-sufficiency | `git archive origin/main` + snapshot files → pytest | **1 failed / 33 passed** |
| 11 | Working-tree control | same 2 test files in real tree | **34 passed** |
| 12 | F-01 file standalone | snapshot `attachments.py` + `test_f01_*.py` from `origin/main` | **13 passed** |
| 13 | Failure diagnosis | read `test_T8b…` + `bot/handlers.py` | needs `_read_local_capped` offload in **handlers.py** (not packaged) |
| 14 | Secrets surface | `ls -a`, `git status --ignored` | no `.env`; `.openhands/`, `.venv/`, `__pycache__/` ignored |

**Note on check 10/12:** these executed in a **temporary directory** built with
`git archive origin/main`. The repository itself was **not** modified; the temp dir was
deleted (`rm -rf /tmp/tmp.fCoMcR6T4q`). This is verification of the *package*, not an F-01
technical review.

---

## 4. Missing information

| # | Missing | Impact |
|---|---|---|
| M-1 | `WORKTREE-VS-HEAD.diff` absent from the Batch-04 package (Batch 03 had one) | Reviewer cannot see the delta without reconstructing it |
| M-2 | `snapshot/bot/handlers.py`, `db.py`, `watcher.py`, `app.py`, `requirements*.txt`, `pytest.ini` absent | Package cannot reproduce a green suite (NOTE-2) |
| M-3 | No `PACKAGE.sha256` inside the package (Batch-03 checklist expects one) | Minor; external sidecar covers it |
| M-4 | No owner decision record for **OD-04** | Blocks DEF-011 A and any concurrency statement |
| M-5 | No owner decisions for **OD-01 / OD-03** | Blocks DEF-011 C (WP-01) |
| M-6 | No Python 3.11 interpreter available here | WP-09 stays **UNVERIFIED** |
| M-7 | Self-hosted runner inventory unknown (`gh api …/actions/runners` → 403) | Cannot confirm whether a private runner exists |
| M-8 | The 40 untracked files were **not** individually secret-scanned | Required gate before any push (§4 A4 of the briefing) |

---

## 5. Blockers

| # | Blocker | Type | Resolvable here? |
|---|---|---|---|
| BL-1 | Independence cannot be established on this host (same machine-id, same `/workspace` device, writable worktree) | Environmental | **No** |
| BL-2 | Route A publishes **more than F-01** (DEF-011 B in the same file) | Scope | No — inherent |
| BL-3 | Route A/B both require **owner authorization** | Authorization | No — owner only |
| BL-4 | Route B incurs **Actions minutes cost** | Cost | No — owner only |
| BL-5 | Package incomplete (M-1, M-2) | Packaging | Yes — but **not** authorized in this task |
| BL-6 | DEF-011 A / C, F-02, F-03, WP-09 remain open | Scope | No — out of Batch-04 scope |

---

## 6. Route feasibility

| Route | Technically feasible? | Blocked on |
|---|---|---|
| **A — Public PR** | **YES** — CI triggers natively on `pull_request`; hosted runners are genuinely separate (evidenced: `GitHub Actions 1000000325/26/27`) | Owner authorization for public disclosure + secret scan (A4) |
| **B — Private first** | **YES** — same mechanics after a visibility change | Owner authorization + acceptance of Actions cost + collaborator/token re-verification |
| Neither | Always available | — |

**Both routes are technically feasible. Neither is authorized.**

---

## 7. Exact permissions still required

Every item is listed separately in the briefing §4 (A1–A9, B1–B10, C1–C2). Summary:

- **Route A:** public disclosure (A1), token use (A2), branch push (A3), secret scan (A4), PR
  (A5), CI run (A6), artifact retrieval (A7), review execution (A8).
- **Route B:** visibility change/mirror (B1), privacy verification (B2), **Actions cost
  acceptance** (B3), access re-verification (B4), token/push/PR/CI (B5–B7), review (B8).
- **Either:** package fix (C1) + archive re-hash (C2).

**Not required / not requested:** merge, deploy, release, Autopush, Mini App changes, schema
changes, architecture changes.

---

## 8. Newly discovered risks

1. **Scope inflation (highest).** The reviewed unit is not F-01 alone. Approving "publish the
   F-01 scope" would in fact publish unreviewed Batch-03 DEF-011-B code. The owner must
   authorize the **actual** diff, not the nominal one.
2. **False-negative review risk.** With the current package a reviewer on a clean `origin/main`
   tree sees **1 failing test** caused by a **packaging omission**, not a code defect. If this
   is not fixed (C1/C2), the review would produce a misleading FAIL.
3. **Irreversibility of Route A.** Public history is mirrored; reverting visibility does not
   retract it. Existing forks remain public even under Route B.
4. **Cost shift under Route B.** Private-repo Actions are metered; public-repo Actions are free.
   Route B therefore trades disclosure risk for a spend decision.
5. **Untracked-file secret exposure.** 40 untracked files would be published under Route A and
   have not been individually scanned (M-8).

---

## 9. Files created by this task

| File | Purpose |
|---|---|
| `docs/audits/OHB2-WP07-BATCH04-OWNER-AUTHORIZATION-BRIEFING.md` | Owner decision document (routes, permissions, decision fields) |
| `docs/reviews/OHB2-WP07-BATCH04-AUTHORIZATION-READINESS-REPORT.md` | This report |

**Both are untracked and unstaged.** No other file was created or modified.

---

## 10. Git state before and after

| Metric | Before | After |
|---|---|---|
| HEAD | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| Staged | 0 | **0** |
| Modified | 8 | **8** |
| Untracked | 40 | **42** (the two deliverables) |
| Ignored | 8 | **8** |

The **only** delta is the two authorized documentation files. No existing tracked, untracked
or ignored file was altered, moved or deleted — including `.openhands/` and `.agent/`.

---

## 11. Confirmation of non-disclosure and non-modification

- **No** `git push`, `commit`, `add`, `stage`, `branch`, `checkout`, `reset`, `clean`, or
  `restore` was run. (`git archive`, `git diff`, `git show`, `git status`, `git rev-parse`
  are read-only.)
- **No** PR was opened; **no** repository visibility was changed.
- **No** GitHub API call that modifies state was made. Only read-only `GET`s:
  `GET /repos/TM-AEM/OpenHandBot`.
- **No** CI run was triggered; **no** workflow was dispatched.
- **No** source code, artifact, or package was uploaded anywhere.
- **No** token value was printed, echoed, or transmitted. Only *presence* of env-var names was
  checked; values were never read out.
- **No** account, subscription, or payment action; **no** paid infrastructure used.
- **No** production code, test, implementation report, or the Batch-04 archive was modified.
  The archive was only read (`sha256sum`, `tar tzf`, extraction into a **temporary** directory
  that was deleted).
- **No** Mini App, schema, or architectural decision was touched.
- **F-01 is not claimed independently reviewed, accepted, or closed.**
- **F-02 and F-03 were not fixed.**

---

## 12. Recommended next action (single)

**The owner completes the decision block in the briefing (§7), choosing Route A, Route B, or
Neither, and — whichever is chosen — also authorizes C1/C2 (package completeness fix).**

Everything else is already prepared: package integrity, hashes, runner availability and the
permission manifest.
