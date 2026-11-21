# OHB2 — WP-07 / Batch 04 — Package Remediation Plan Report (C1 / C2)

**Task:** `OHB2-WP07-BATCH04-REVIEW-PACKAGE-REMEDIATION-PLAN`
**Date:** 2026-11-19
**Mode:** **PLAN ONLY** — no implementation, no rebuild, no transfer, no disclosure.
**Companion plan:** `docs/audits/OHB2-WP07-BATCH04-REVIEW-PACKAGE-REMEDIATION-PLAN.md`

> **F-01 and DEF-011 are NOT independently reviewed, NOT accepted, NOT closed.**
> **C1 and C2 were NOT implemented.**

---

## 0. Verdict

# `PACKAGE_REMEDIATION_PLAN_READY`

The deficiency is **reproduced exactly**, the root cause is **proven**, the minimal required file
set is **empirically established** (a reconstruction from `origin/main` + the proposed files
reaches **3419 passed — identical to the worktree**), and C1/C2 are specified as exact, verifiable
steps. One owner decision (package scope, **D-1**) must be made before execution.

---

## 1. Is the package deficiency reproduced?

**YES — exactly.**

| Reproduction | Command (in a temp dir) | Result |
|---|---|---|
| A. Package's own 2 test files on `origin/main` + snapshot | `pytest -q tests/test_f01_reaper_fs_offload.py tests/test_def011_fs_offload.py` | **`1 failed, 33 passed` in 2.20s** |
| B. F-01 subset alone | `pytest -q tests/test_f01_reaper_fs_offload.py` | **`13 passed` in 0.89s** |
| C. DEF-011-B subset alone | `pytest -q tests/test_def011_fs_offload.py` | **`1 failed, 20 passed` in 1.22s** |
| D. Add **only** `bot/handlers.py` | both files | **`34 passed` in 2.13s** |

Failing test in A and C: `tests/test_def011_fs_offload.py::test_T8b_local_capped_read_runs_off_event_loop_thread`.

**The previous `1 failed / 33 passed` result is reproduced with no change.** The environment and
source state are unchanged (`HEAD == origin/main == 52e7789…`, archive digest `47b9923…`).

The package is **internally intact** — `sha256sum -c MANIFEST.sha256` → all OK. The defect is
**incompleteness**, not corruption.

---

## 2. Exact missing files and dependencies

### 2.1 Proven root cause

`bot/handlers.py` is **not** in the package, yet it contains a reviewed DEF-011-B change:

```diff
+import functools
+from anyio import to_thread
-                    return iter([_read_local_capped(file_path, max_bytes)])
+                    data = await to_thread.run_sync(
+                        functools.partial(_read_local_capped, file_path, max_bytes)
```

`test_T8b` asserts that `_read_local_capped` runs on a **non-loop** thread. Without the package
carrying `bot/handlers.py`, the reconstruction uses `origin/main`'s synchronous version → the
assertion fails.

### 2.2 Missing from the current package

| Missing | Why it matters |
|---|---|
| `bot/handlers.py` | **Causes the failure** (holds the `_read_local_capped` offload) |
| `bot/db.py` | Full-suite gate: **100 failures** without it (WP-07 atomicity work) |
| `bot/watcher.py`, `bot/app.py` | DEF-011-B call sites (`maybe_sweep_async`, `sweep_async`) |
| `tests/test_handlers.py`, `tests/test_sw06_unwatch_db_failure_propagation.py` | `**_kw` signature compatibility |
| 7 untracked WP-07 test files | exactly the remaining **100** tests to reach 3419 |
| `pytest.ini` | `asyncio_mode=auto`, `pythonpath=.` — required to collect at all |
| `requirements*.txt` | dependency pinning for a clean environment |
| `WORKTREE-VS-HEAD.diff` | **absent entirely** (Batch 03 had one) — reviewer cannot see the delta |
| `BASE.txt` / `SCOPE.md` | no explicit base commit, no DEF-011-B vs F-01 split |

### 2.3 Dependency completeness proof (the decisive evidence)

| Reconstruction contents | Full-suite result |
|---|---|
| `attachments` + `handlers` + `watcher` + `app` (no `db.py`) | **100 failed, 3219 passed** |
| + `db.py` + 2 modified tests | **3319 passed** |
| + 7 untracked WP-07 test files | **3419 passed** |
| *worktree control* | **3419 passed** |

Gap arithmetic: 134 untracked tests − 34 already present = **100**, matching the failure count
exactly. Reaching **3419 = worktree** proves the set is **complete and sufficient**.

---

## 3. Can the proposed package independently reproduce the relevant tests?

**YES — demonstrated, not asserted.**

The reconstruction used **only** `git archive origin/main` plus the proposed payload files, in a
temporary directory, with **no access** to the original worktree:

| Gate | Result |
|---|---|
| DEF-011-B subset | **21 passed** |
| F-01 subset | **13 passed** |
| Combined focused | **34 passed** |
| Full suite | **3419 passed, 0 failed** |
| Worktree control | **3419 passed** |

So a reviewer given the corrected package can reproduce every relevant test **without** the
implementation worktree — which is exactly the property the current package lacks.

---

## 4. Exact C1 / C2 implementation steps

Full detail is in the plan (§6). Condensed:

### C1 — self-containment

1. Assert `HEAD == origin/main == 52e7789…`, 0 staged.
2. Hash all 25 payload files.
3. Create `snapshot/bot/`, `tests/`, `config/`, `docs/`.
4. Copy **5** bot files, **11** test files, **3** config files, **6** docs (explicit lists).
5. Write `BASE.txt` (commit/branch/counts) and `SCOPE.md` (DEF-011-B +245/−59, F-01 +162/−65,
   pre-fix hash `e72745eb…`).
6. Generate `WORKTREE-VS-HEAD.diff` via a **throwaway index** so the real index is untouched.
7. Write `README.md`; **secret-scan the staging dir**.

### C2 — reproducible rebuild + integrity

8. `find … | sort | xargs sha256sum > MANIFEST.sha256`.
9. `sha256sum -c MANIFEST.sha256` → all OK.
10. Deterministic `tar --sort=name --mtime=… --owner=0 --group=0 --numeric-owner -czf`.
11. `sha256sum … > <archive>.sha256`.
12. **Build twice** → identical digest (reproducibility).
13. Fresh extract → check traversal/symlinks.
14. Manifest check in the extraction; unmanifested-file check (`comm` → ∅).
15. **Reconstruct from `origin/main` + snapshot only** → focused 34 / full 3419.

Step 15 is the decisive gate.

---

## 5. Security and disclosure risks

| # | Risk | Detail | Mitigation |
|---|---|---|---|
| S1 | Secret leakage | 25 payload files scanned this task → **no credential patterns** | re-scan at build, including diffs |
| S2 | `.agent/PROGRESS.md` | **Excluded** — not test-required; 236 added lines of unrelated history, 35 keyword mentions | omit from package |
| S3 | `bot/db.py` scope creep | **269 lines of WP-07 atomicity**, unrelated to DEF-011 | owner decision D-1; label in `SCOPE.md` |
| S4 | 7 unrelated test files | DEF-013 / NEW-DEF-03 / NAV / F-1-C scope | label them; do not present as DEF-011 evidence |
| S5 | Caches / venv / DB files | non-deterministic or user data | explicit exclusion list |
| S6 | Sidecar ≠ independent authentication | produced on the implementation host | reviewer must recompute from received bytes |
| S7 | Packaging ≠ publishing | a built package is not a disclosure | separate owner authorization for transfer |

**No secret value was read, printed or used during this task.**

---

## 6. Files created

| File | Purpose |
|---|---|
| `docs/audits/OHB2-WP07-BATCH04-REVIEW-PACKAGE-REMEDIATION-PLAN.md` | The remediation plan (C1/C2) |
| `docs/reviews/OHB2-WP07-BATCH04-PACKAGE-REMEDIATION-PLAN-REPORT.md` | This report |

Both are **untracked and unstaged**. No other file was created or modified.

---

## 7. Git state before and after

| Metric | Before | After |
|---|---|---|
| HEAD | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| `origin/main` | same | same |
| Staged | 0 | **0** |
| Modified | 8 | **8** |
| Untracked | 42 | **44** (+ the 2 deliverables) |
| Ignored | 8 | **8** |

Archive: `47b992300ec1bd5efec8c6c95afff4a63815a58ccd25f254975939f53f0bf71d`, `107643` B — **unchanged**.

---

## 8. Confirmation of non-implementation / non-disclosure

- **C1 and C2 were not executed.** No package was built or rebuilt.
- The existing archive and sidecar were **read only** (`sha256sum`, `tar tzf`, extraction into
  temp dirs that were deleted). They were **not edited, replaced or regenerated**.
- **No** source code, test, implementation report or package README was modified.
- **No** `git add`/`commit`/`push`/`branch`/`checkout`/`reset`/`clean`/`restore`. The temp-index
  diff test used `GIT_INDEX_FILE` in `/tmp` and left `staged=0` (verified).
- **No** PR, **no** visibility change, **no** CI trigger, **no** modifying GitHub API call.
- **No** upload, transfer or disclosure of source or artifacts.
- **No** token or credential used, printed or exposed.
- **No** account, subscription, payment or paid infrastructure.
- **No** Mini App, schema or architectural decision touched.
- All temporary directories removed (`/tmp/pkgrepro.*`, `/tmp/minimal.*`, `/tmp/reprotest.*`,
  `/tmp/tmpidx.*` → none remain).
- **F-01 and DEF-011 remain NOT independently reviewed, NOT accepted, NOT closed.**
  F-02, F-03 remain open; WP-09 remains unverified.

---

## 9. Recommended next action (single)

**Owner decides D-1 (package scope: focused 34-test vs full 3419-test) and authorizes C1/C2
execution.** No build should start before that decision, because it determines the disclosure
surface (`db.py` + 7 unrelated test files).
