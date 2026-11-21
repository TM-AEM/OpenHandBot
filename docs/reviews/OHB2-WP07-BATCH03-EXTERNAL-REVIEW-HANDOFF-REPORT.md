# OHB2 — WP-07 Batch-03 External Review Handoff Report

**Task ID:** `OHB2-WP07-BATCH03-EXTERNAL-INDEPENDENT-REVIEW-HANDOFF`
**Date:** 2026-11-19
**Recorded by:** AI agent (OpenHands) on behalf of the repository owner.

> **This document does NOT contain a technical review.** It prepares and verifies a read-only
> handoff package for a **genuinely independent external reviewer**. No technical PASS is claimed
> anywhere in this report. Package creation does **not** establish review independence.

---

## 0. Verdict

# `WP07_EXTERNAL_REVIEW_PACKAGE_READY_WITH_NOTES`

**Why `_WITH_NOTES` and not plain `_READY`:** the package is complete, verified and reproducible,
but it carries four substantive scope notes the reviewer must confront, none of which are packaging
defects:

| # | Note | Where |
|---|---|---|
| N-1 | `DEF-011` sub-defect **A** (in-process quota reservation ledger) is **NOT implemented**, although baseline §WP-07 constraint 2 requires it. | §4.3 |
| N-2 | `DEF-011` sub-defect **C** (acceptance UX copy) belongs to **WP-01** and is blocked on `OD-01`/`OD-03`. | §4.3 |
| N-3 | `DEF-006` / `OD-04` concurrency is **unratified**; only the comments-only path exists. | §4.2 |
| N-4 | `WP-09` Python 3.11 compatibility is **UNVERIFIED** (only 3.13 available here). | §7 |

**The technical review itself remains PENDING** until a genuinely separate reviewer inspects the
package. Independence is **not** established by this agent, this host, this process, or this
package.

---

## 1. Phase 1 — Repository inventory (read-only, verified)

Repository root: `/workspace/project/OpenHandBot` (real Git working tree; `git rev-parse --show-toplevel` = root).

| Item | Value |
|---|---|
| Branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` |
| HEAD | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` — **matches the recorded HEAD exactly** |
| `origin/main` | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` (identical to HEAD) |
| Staged changes | **none** (`git diff --cached` empty) |
| Modified tracked files | **8** (listed below) |
| Untracked files | **34** (listed below) |
| Ignored files | `.venv/`, `.openhands/`, `__pycache__/`, `*.pyc` (git-ignored; **preserved, not packaged**) |
| SQLite tables | **17** (`CREATE TABLE IF NOT EXISTS` in `bot/db.py`; no schema change in the diff) |
| Python | 3.13.15 (project `.venv`) |
| Node | v24.22.2 |

### 1.1 Modified tracked files (8)

```
 M .agent/PROGRESS.md
 M bot/app.py
 M bot/attachments.py
 M bot/db.py
 M bot/handlers.py
 M bot/watcher.py
 M tests/test_handlers.py
 M tests/test_sw06_unwatch_db_failure_propagation.py
```

### 1.2 Untracked files (34)

WP-07 tests (8), WP-07 audits (7), WP-07/WP-05/WP-06 reports (18), plus `docs/design/`.
The full untracked list is captured verbatim in `MANIFEST.sha256` of the package.

### 1.3 DEF-011 implementation present? **YES — verified against source, not reports**

```
bot/attachments.py:525   self._accept_lock = anyio.Lock()
bot/attachments.py:656   def _store_prepare(
bot/attachments.py:757   def _store_finalize(
bot/attachments.py:795   def _store_write(
bot/attachments.py:875   async def store_async(
bot/attachments.py:1189  async def sweep_async(
bot/attachments.py:1211  def _sweep_db_phase(
bot/attachments.py:1285  def _sweep_fs_tail(
bot/attachments.py:1679  async def maybe_sweep_async(
bot/attachments.py:909   await to_thread.run_sync(   # store write
bot/attachments.py:1199  await to_thread.run_sync(   # sweep fs tail
bot/handlers.py:2086     await to_thread.run_sync(   # _read_local_capped
```

### 1.4 Material discrepancy vs the reported implementation? **NO for code; YES for two documents**

- The **code** state matches the reported DEF-011 implementation exactly (HEAD unchanged, working
  tree carries the work).
- **Discrepancy D-1:** `docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md` states
  "`DEF-011` is entirely unimplemented" and lists it under "Explicit non-authorizations"
  (§7 "No DEF-011 implementation"). That document predates the DEF-011 work and is **now stale**.
  It is packaged **as-is** (it is the authoritative record of what was proposed at that time) and
  flagged here rather than edited, per the read-only constraint.
- **Discrepancy D-2:** the same proposal's reservation **R9** ("DEF-011 entirely unimplemented")
  is superseded by the current tree. Reviewer must re-verify rather than trust R9.

**No repair was attempted.** Both are documented, not fixed.

---

## 2. Phase 2 — Scope reconciliation

### 2.1 Findings implemented in **committed HEAD**

| Finding | What is committed | Evidence |
|---|---|---|
| `DEF-006` (partial) | The comments-only alignment in `bot/app.py:74-89` explaining that `concurrent_updates(True)` does **not** make `TelegramPoller` parallel. | `git show HEAD:bot/app.py` contains the `DEF-006` block; worktree adds nothing here. |
| `DEF-013` (partial) | The `renew_awaiting`-after-whitespace-validation fix in `bot/handlers.py` (HEAD line 2460 marker). | `git grep DEF-013 HEAD -- bot/` → 1 hit. |

Everything else in WP-07 is **uncommitted working-tree work**.

### 2.2 Findings implemented **only in the working tree**

| Finding | Status | Key locations |
|---|---|---|
| `DEF-011` sub-defect **B** — filesystem offload | **IMPLEMENTED** | `attachments.py` (`store_async`/`sweep_async`/`maybe_sweep_async`, `_accept_lock`), `handlers.py:2086`, `watcher.py`, `app.py` |
| `DEF-013` — atomic expired-awaiting clear + outcome | **IMPLEMENTED** | `db.clear_awaiting_and_record_outcome`, `handlers.py` expired branch |
| `NEW-DEF-03` — atomic state+outcome at set/clear/watch sites | **IMPLEMENTED** | `db.py` (`add_watched_and_record_outcome`, `remove_watched*`, `_set_awaiting_nocommit`), `handlers.py`, `watcher.py` |
| `NAV-01..06` — navigation clear atomicity (**part of NEW-DEF-03**, not an independent baseline finding) | **IMPLEMENTED, UNACCEPTED** | see §2.3 |

### 2.3 `NAV-01..06` are **not** independent baseline findings

The authoritative baseline registers `DEF-006`, `DEF-011`, `DEF-013`, `NEW-DEF-03` for `WP-07`.
`NAV-01..06` are an **internal decomposition of the navigation sub-part of `NEW-DEF-03`**, created
by the agent while executing it. They must be reviewed **as `NEW-DEF-03` scope**, not as separate
register entries. Their acceptance status is nevertheless separate (see §2.5).

### 2.4 `DEF-011` is **NOT** closed

`DEF-011` decomposes into three sub-defects (source: `docs/audits/OHB2-WP07-DEF011-REMEDIATION-AUDIT.md` §2.2):

| Sub | Description | Owner | Current state |
|---|---|---|---|
| **A** | Missing cross-download **quota reservation ledger** | `WP-07` | **NOT IMPLEMENTED** — zero `reserv*` matches in `bot/` (excluding unrelated `is_reserved`). |
| **B** | Synchronous disk I/O on the event loop | `WP-07` | **IMPLEMENTED** (3 `to_thread` sites). |
| **C** | Misleading `ATTACHMENT_ACCEPTED_TEXT` acceptance UX | **`WP-01`** | **NOT IMPLEMENTED** — text still reads only "استلمت الملف ✅ …" with no local-only disclosure (`handlers.py:1878`). |

**Sub-defect C is owned by WP-01, which is blocked on `OD-01` + `OD-03`.** It is outside WP-07's
authorized scope and must not be implemented here.

### 2.5 Quota reservation ledger — explicit disclosure

> **The in-process quota reservation ledger (sub-defect A) was NOT implemented and remains
> OUTSIDE the authorized DEF-011 implementation scope of this batch.**

Rationale (documented in `docs/audits/OHB2-WP07-DEF011-REMEDIATION-AUDIT.md` §4.1, §5, §7):
- Baseline §WP-07 constraint 2 does ask for it, **but**
- `D-12` requires aggregate quota defaults to stay `None`; an always-on ledger would change them;
- the ledger is only *meaningful* under concurrency, and concurrency is `OD-04`-blocked;
- therefore a ledger here would be inert dead code at best and a `D-12` violation at worst.

**This is a real deviation from the baseline text and is disclosed, not hidden.** The reviewer must
judge whether the deviation is acceptable or whether sub-defect A must be reopened after `OD-04`.

### 2.6 Owner-acceptance inventory

| Scope | Content | Status |
|---|---|---|
| **A** (accepted, per `.agent/PROGRESS.md:4272`) | `watch`/`unwatch`/awaiting atomicity + back-compat + F-1 Option C | **ACCEPTED (5 items)** — verified intact |
| **A′** | `NAV-01..06` | **UNACCEPTED** — `REQUIRES_SEPARATE_OWNER_DECISION` |
| **B** | `DEF-006` / `OD-04` concurrency | **BLOCKED_PENDING_OD04** |
| **DEF-011 B** | filesystem offload (this batch) | **NO ACCEPTANCE RECORD** — implemented + tested only |

### 2.7 Blocked by owner decisions

| Decision | Blocks |
|---|---|
| `OD-01` + `OD-03` | `WP-01` ⇒ therefore **DEF-011 sub-defect C** |
| `OD-02` | `WP-04` Part 2 |
| `OD-04` | `DEF-006` concurrency; **DEF-011 sub-defect A** (ledger is meaningful only under it) |
| `OD-05` | `WP-10` |

### 2.8 Unresolved verification limitations

| # | Limitation |
|---|---|
| L-1 | **Independent review not established** (this agent/host cannot supply it). |
| L-2 | **WP-09 Python 3.11 not run** — only 3.13 available; CI not triggered (no push). |
| L-3 | Mutation results are **prior self-reports**, not independently reproduced. |
| L-4 | Docker daemon absent in this environment (prior container-based verification path unavailable). |

### 2.9 F-1 and watch/unwatch — re-checked against current source (not assumed)

- **F-1 (Option C)**: mechanism verified in source — the six paths commit state + `durable_completed`
  in one `BEGIN IMMEDIATE`; the Telegram send is outside the transaction; on failure
  `handle_processing_error` (`handlers.py:827`) → `record_update_failure` (`handlers.py:656`) →
  `mark_update_outcome` (`db.py:3068`) writes **only** `update_failures`. Verified that
  `prune_processed_updates` (`db.py:3226`) deletes **only** from `processed_updates`
  (`db.py:3247`, `:3252`) ⇒ the failure evidence survives pruning. **Consistent with Option C.**
- **Watch/unwatch atomicity**: `add_watched_and_record_outcome`, `remove_watched`,
  `_remove_watched_nocommit`, `remove_watched_completing`, `_remove_watched_completing_nocommit`
  are all present in `bot/db.py`; `watcher.unwatch` accepts `update_id`/`now`/`outcome`.
  **Consistent with the accepted A-1/A-2 scope.**

Neither is assumed open or resolved from old reports; both were re-checked in the current source.

---

## 3. Phase 3 — Package location and contents

**Package root:**
```
/workspace/review-packages/OHB2-WP07-BATCH03-EXTERNAL-REVIEW-HANDOFF-20261119
```

| Artifact | Purpose |
|---|---|
| `snapshot/` | Exact source snapshot of the 39 in-scope working-tree files (repo-relative layout). |
| `WORKTREE-VS-HEAD.diff` | Authoritative `git diff HEAD --` (tracked modifications only). |
| `MANIFEST.sha256` | sha256 + size + tracked/untracked class + in-scope flag per file. |
| `PACKAGE.sha256` | Package-level checksum over the archive. |
| `OHB2-WP07-BATCH03-EXTERNAL-REVIEW-HANDOFF-20261119.tar.gz` | Single archive for transport. |
| `README.md` | Extraction + verification instructions. |

The **committed HEAD vs uncommitted working tree** distinction is preserved: the diff is a real
`git diff HEAD`, and the manifest labels every file `tracked-clean` / `modified` / `untracked`.
**No clean commit was manufactured** and no working-tree change is presented as committed.

---

## 4. Phase 4 — Reviewer instructions (binding)

The external reviewer **must**:

1. Inspect the **complete** `WORKTREE-VS-HEAD.diff` and the snapshot sources — not the reports.
2. Verify **every** baseline finding against source.
3. For **DEF-011 B**, confirm all of:
   - filesystem operations actually execute **outside** the event-loop thread;
   - SQLite access remains in its **owning** execution context;
   - mixed DB/FS functions were **not** moved wholesale to worker threads;
   - cancellation, partial-file cleanup and error propagation are safe;
   - `anyio.Lock` preserves the **previously sequential** admission behaviour;
   - **no** quota ledger, schema change, worker, or new dependency was introduced.
4. For **DEF-006**, disclose `OD-04` status **without inventing owner approval**.
5. For **DEF-013** / **NEW-DEF-03**, include the navigation paths and watch/unwatch atomicity,
   treating `NAV-01..06` as `NEW-DEF-03` sub-scope.
6. For **F-1**, verify post-commit send-failure semantics against the actual owner decision.
7. Check that **WP-05** changes remain separated and were not unintentionally altered.
8. **Independently run** the focused and full test suites where the environment permits.
9. **Verify test counts and static-check claims** instead of copying reported numbers.
10. Report **Python 3.11 as UNVERIFIED** if it cannot be run.
11. Report every defect with severity, exact file/function/line evidence, reproduction steps and a
    recommended correction.
12. **Not modify** the supplied snapshot.

Required verdict dimensions: technical correctness, scope compliance, test reproducibility,
architecture compliance, owner-acceptance readiness, independent-review status.

---

## 5. Phase 5 — Independence safeguards (what this agent did NOT do)

- Did **not** claim to be the independent reviewer.
- Did **not** generate a fake second identity.
- Did **not** describe another process/venv on this host as independent.
- Did **not** mark any self-review as PASS.
- Did **not** upload repository contents to any external service.
- Did **not** claim package creation establishes independence.

**Limitation stated explicitly: no approved external reviewer or separate execution environment is
available to this agent. Independence remains UNESTABLISHED.**

---

## 6. Phase 6 — Package verification (performed)

| Check | Result |
|---|---|
| Every included file exists | ✅ 39/39 snapshot files present |
| Manifest sizes/hashes match actual files | ✅ re-verified (`sha256sum -c`) |
| Package checksum reproducible | ✅ `PACKAGE.sha256` re-computed and matched |
| Archive extracts in a temp location without touching the repo | ✅ verified |
| Tracked vs untracked correctly classified | ✅ classes derived from `git status --porcelain` |
| No secrets / tokens / credentials / production data | ✅ scanned — only env-var **names** in prose, no values |
| All required review documents present | ✅ see §3 + `MANIFEST.sha256` |
| Snapshot represents the **current** working tree | ✅ hashes recomputed against live repo at build time |

---

## 7. Verification evidence recorded for the reviewer (not a review verdict)

| Command | Result | Note |
|---|---|---|
| `python -m pytest -q` (full) | **3406 passed, 0 failed** | agent-run, not independent |
| focused WP-07 suites (8 files) | **121 passed** | agent-run |
| `python -m pyflakes bot/ automation/ tools/ main.py tests/` | exit 0 | clean |
| `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | exit 0 | High 0 |
| `node --test tests/frontend/*.test.js` | 280 pass / 0 fail | |
| Python 3.11 | **UNVERIFIED** | only 3.13 available; CI not triggered |

The reviewer must **re-derive** these numbers. They are provided as a baseline to compare against,
not as accepted fact.

---

## 8. Deliverables

| # | Deliverable | Location |
|---|---|---|
| 1 | Handoff report (this file) | `docs/reviews/OHB2-WP07-BATCH03-EXTERNAL-REVIEW-HANDOFF-REPORT.md` |
| 2 | Reviewer checklist | `docs/reviews/OHB2-WP07-BATCH03-EXTERNAL-REVIEW-CHECKLIST.md` |
| 3 | Findings template | `docs/reviews/OHB2-WP07-BATCH03-EXTERNAL-REVIEW-FINDINGS-TEMPLATE.md` |
| 4 | Review archive + manifest + checksum + README | `/workspace/review-packages/OHB2-WP07-BATCH03-EXTERNAL-REVIEW-HANDOFF-20261119/` |

**Package path:** `/workspace/review-packages/OHB2-WP07-BATCH03-EXTERNAL-REVIEW-HANDOFF-20261119`
**Package archive:** `/workspace/review-packages/OHB2-WP07-BATCH03-EXTERNAL-REVIEW-HANDOFF-20261119.tar.gz` (528 KB)
**Package checksum (SHA-256): the authoritative value is in `OHB2-WP07-BATCH03-EXTERNAL-REVIEW-HANDOFF-20261119.tar.gz.sha256`, shipped beside
the archive.** Verify with `sha256sum -c OHB2-WP07-BATCH03-EXTERNAL-REVIEW-HANDOFF-20261119.tar.gz.sha256` from the directory that holds both files.

> This report lives **inside** the archive, so it deliberately does **not** embed the archive's own
> digest — doing so would be circular (writing the digest would change the digest). The sidecar is
> the single source of truth; it is excluded from the tarball for the same reason.

Archive build is **byte-for-byte reproducible**:
`tar --sort=name --owner=0 --group=0 --numeric-owner --mtime='2026-11-19 00:00:00' --exclude=PACKAGE.sha256`.

**Verification performed end-to-end in `/tmp`** (fresh directory, reviewer procedure):
`sha256sum -c <archive>.tar.gz.sha256` → `OK` → `tar -xzf` → `sha256sum -c MANIFEST.sha256` →
**43/43 entries OK, 0 failures** → 45 files (43 manifest-tracked + `MANIFEST.sha256` + `README.md`)
→ 3 deliverables in `handoff-docs/`, 39 files in `snapshot/`. Rebuild of the archive from the
package tree reproduces the **identical** digest ⇒ byte-for-byte reproducible.
**Snapshot fidelity:** **39/39** snapshot files re-hashed and matched the live working tree exactly.
**Packaged code diff:** the `bot/` + SW-06 test hunks in `WORKTREE-VS-HEAD.diff` are **byte-identical**
(sha256 `5b469ba3…`) to a fresh `git diff HEAD` of those paths at handoff time.

---

## 9. Repository safety confirmation

- Read-only operation: **no** production code or test file was modified by this task.
- No database/schema change (17 tables, unchanged).
- No Mini App change. No dependency installed. No live Telegram/OpenHands call.
- No destructive Git command; no staging; no commit/push/PR/merge/deploy/release.
- Autopush untouched. `.openhands/` and `.agent/` preserved.
- The only repository additions are the three documents in §8.

---

## 10. Final verdict

# `WP07_EXTERNAL_REVIEW_PACKAGE_READY_WITH_NOTES`

**The technical review remains PENDING.** It cannot begin until a genuinely separate reviewer,
in a genuinely separate execution environment, inspects the package and issues its own verdict.
