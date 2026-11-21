# OHB2 — WP-07 — Batch 04 — REV2 — S3 Baseline Manifest

**Task:** `OHB2-WP07-BATCH04-REV2-S3-EXECUTION`
**Date:** 2026-11-19
**Status:** **BASELINE IDENTIFIED — NOT YET COMMITTED**

> **No commit exists for the NEW-DEF-03 delivery.** This manifest records the *identifiable*
> baseline (base commit + exact file content hashes). It does **not** invent a delivery commit.

---

## 1. Base commit

| Field | Value |
|---|---|
| **Base commit** | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| `origin/main` | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| Divergence | `0 0` |
| Branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` |

## 2. NEW-DEF-03 delivery commit

**NONE.** No commit, push, branch, or PR was created in this task (no authorization for C).

The delivery exists only as **selected hunks inside the working tree**. Its identity is defined by
the file content hashes below, not by a commit SHA.

## 3. Exact changed paths (Scope A only)

### 3.1 Production

| Path | Working-tree SHA-256 | `origin/main` SHA-256 | Δ |
|---|---|---|---|
| `bot/db.py` | `205f1363aaf0b1f8173b74285e263891d333928ba480d478b6b525d4369c694b` | `472fa573142ee4265cdb2a26ec882906d743d798300e73ad16a9583ef5343314` | +269 / −66 |
| `bot/handlers.py` | `40dd8902595c1a63875f8c9d37d4fed4a454be15e1390e5386dcfa9bce058014` | `96325cf2d8f24d291f0bf2f664188678ff03e6f27e914410803f4216affb4f6a` | 24/44 hunks |
| `bot/watcher.py` | `06f3dd4c23e3e154a311bc26b749240a92abe825b8a14b29ac9dbaee41aa6fcb` | `43a6d9446ac6d75acf9763f09f7a4d5890b7a567250e27ee330c538a95cf7370` | 2/3 hunks |

### 3.2 Tests (compatibility only)

| Path | Working-tree SHA-256 | `origin/main` SHA-256 | Δ |
|---|---|---|---|
| `tests/test_handlers.py` | `2b1f978091f45c695803a73845065073690f58f1b1c8d2f41fa38d04c1fa8ea8` | `8a2b080ed10e5379cdf46a4c2194b3572b6683381ff430fd5c140528faa6c904` | +2 / −2 |
| `tests/test_sw06_unwatch_db_failure_propagation.py` | `ba2633113424432467edeff6cb74f656bb4b5fe9b762dbcc8a251799b33e07ef` | `79a8a5a332e182456f300b16823cb353ce34f9713746223e298a6c9fcbde8059` | +11 / −11 |

### 3.3 Explicitly EXCLUDED from this baseline

| Path | Reason |
|---|---|
| `bot/attachments.py` | DEF-011-B / F-01 — separate delivery |
| `bot/app.py` | DEF-011-B — separate delivery |
| 1 `handlers.py` hunk (`_download_attachment_chunks` + imports) | DEF-011-B |
| 1 `watcher.py` hunk (`maybe_sweep_async`) | DEF-011-B |
| 17 NAV hunks in `handlers.py` | **unaccepted** (Scope A′) |
| 7 untracked WP-07 test files | not part of Scope A delivery |
| `.agent/PROGRESS.md` | work log — never published |

## 4. Test evidence

Measured on a throwaway reconstruction from `git archive origin/main` (not on the working tree):

| Command | Result | Exit |
|---|---|---|
| `python -m pytest -q` (full suite) | **3285 passed**, 0 failed | 0 |
| `python -m pytest -q` + 3 WP-07 regression files | **3334 passed**, 0 failed | 0 |
| `python -m pytest -q tests/test_wp07_watch_unwatch_atomicity.py tests/test_wp07_atomic_state_outcome.py tests/test_wp07_f1_notification_failure.py` | **47 passed** | 0 |
| `python -m pyflakes bot/ automation/ tools/ main.py tests/` | **clean** | 0 |
| `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | **No issues identified** | 0 |
| NAV non-vacuity proof (NAV tests on NAV-excluded build) | **16 failed / 35 passed** | 1 |

**Purity checks:**

| Check | Result |
|---|---|
| `NAV-0` markers in `bot/handlers.py` | **0** |
| `to_thread` in `bot/handlers.py` | **0** |
| `bot/attachments.py` vs `origin/main` | **identical** |
| `bot/db.py` DEF-011 / NAV markers | **0** |

## 5. Acceptance record reference

| Field | Value |
|---|---|
| Record | `.agent/PROGRESS.md:4272-4277` |
| Marker | `NEW-DEF-03_NON_CONCURRENCY_OWNER_ACCEPTED` |
| Scope accepted | exactly A-1..A-5 |
| Baseline statement | `OHB2-CORRECTED-REMEDIATION-BASELINE.md` §NEW-DEF-03 → **Owner Approval Requirements: `NONE`** |
| What it does **NOT** mean | not `WP-07_COMPLETE`, not `NEW-DEF-03_COMPLETE`, not NAV acceptance |

**Scope A′ (NAV-01..06):** `REQUIRES_SEPARATE_OWNER_DECISION` — **not accepted**, **not** in this baseline.

## 6. Verdicts applicable to this manifest

| Dimension | Status |
|---|---|
| Implementation completion | **DONE** (already in working tree) |
| Test validation | **VERIFIED** (3285 / 3334 / 47; pyflakes, bandit clean) |
| Git stabilization | **IDENTIFIED, NOT COMMITTED** — base `52e7789`, no delivery commit |
| Owner acceptance | **ACCEPTED for Scope A** (A-1..A-5 only); **NOT** for NAV |
| Package integrity | n/a (no package built for NEW-DEF-03) |
| Independent review | **NOT ESTABLISHED** |
| Technical correctness | **NOT ESTABLISHED** (no independent review) |
| Formal finding closure | **NOT DONE** |

## 7. Preservation

| Item | State |
|---|---|
| `HEAD` | `52e7789` — **unchanged** |
| Staged | **0** |
| Modified | **8** — **unchanged** |
| Untracked | **49 → 52** (3 new reports) |
| Ignored | **8** — **unchanged** |
| `.openhands/` | preserved |
| `.agent/` | preserved |
| Batch04 archive `47b9923…` | **intact** |
| REV2 archive `de8e4fc9…` | **intact** |
| Workflow files | **unmodified** |

No reset, clean, force, broad deletion, `git add .`, or `git add -A` was used.
