# OHB2 — WP-07 / Batch 04 — Review Package Remediation Plan (C1 / C2)

**Task:** `OHB2-WP07-BATCH04-REVIEW-PACKAGE-REMEDIATION-PLAN`
**Date:** 2026-11-19
**Mode:** **PLAN ONLY** — no repair, no rebuild, no transfer, no disclosure performed.
**Companion report:** `docs/reviews/OHB2-WP07-BATCH04-PACKAGE-REMEDIATION-PLAN-REPORT.md`

> ## ⚠️ IMPLEMENTATION IS NOT AUTHORIZED
> This document specifies **how** to perform C1 (make the package self-contained) and
> C2 (rebuild reproducibly + verify integrity). **Neither has been executed.** No archive
> was edited, rebuilt or replaced; no sidecar was created; no source file was changed.
>
> **F-01 and DEF-011 are NOT independently reviewed, accepted or closed.**

---

## 0. Summary

| Item | Finding |
|---|---|
| Package deficiency reproduced? | **YES** — exactly `1 failed / 33 passed` |
| Root cause | `bot/handlers.py` is absent from the package; it holds the `_read_local_capped` → `anyio.to_thread.run_sync` offload that `test_T8b` asserts |
| F-01-only scope | **Self-sufficient already** — `13 passed` from `origin/main` + snapshot |
| DEF-011-B-only scope | **Broken** — `1 failed / 20 passed` without `handlers.py` |
| Adding only `handlers.py` | **Fixes it** — `34 passed` |
| Minimal set for the focused 34 | `attachments.py` + `handlers.py` + `watcher.py` + `app.py` (no `db.py`) |
| Minimal set for the full 3419 | the above + `db.py` + 2 modified tests + 7 untracked WP-07 test files |
| `.agent/PROGRESS.md` needed? | **NO** — excluded (reduces disclosure) |
| Secrets in proposed files | **NONE found** |

---

## 1. Phase 1 — Scope and dependency inventory

### 1.1 Base identity (verified this task, not copied)

| Field | Value |
|---|---|
| HEAD | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| `origin/main` | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` (identical) |
| Worktree state | 0 staged / 8 modified / 40 pre-existing untracked / 8 ignored |
| Archive | `107643` B, SHA-256 `47b9923…0bf71d` (unchanged) |

### 1.2 Inventory table

Legend — **In pkg?**: whether it must be in the review package. **Risk**: disclosure sensitivity.

| # | File | Git state | On `origin/main`? | Needed for | In pkg? | Risk |
|---|---|---|---|---|---|---|
| 1 | `bot/attachments.py` | modified | yes | **DEF-011-B + F-01** | **YES** (snapshot) | LOW — runtime code, no secrets |
| 2 | `bot/handlers.py` | modified | yes | **DEF-011-B** (`_read_local_capped` offload) | **YES** (snapshot) | LOW — runtime code |
| 3 | `bot/watcher.py` | modified | yes | DEF-011-B call site (`maybe_sweep_async`) | **YES** | LOW |
| 4 | `bot/app.py` | modified | yes | DEF-011-B startup call site (`sweep_async`) | **YES** | LOW |
| 5 | `bot/db.py` | modified | yes | **Full-suite gate only** (WP-07 atomicity work) | **YES** (if full gate) | MEDIUM — 269 lines of unrelated WP-07 work; contains SQL, no secrets |
| 6 | `tests/test_f01_reaper_fs_offload.py` | untracked | **no** | **F-01** (13 tests) | **YES** | LOW |
| 7 | `tests/test_def011_fs_offload.py` | untracked | **no** | **DEF-011-B** (21 tests) | **YES** | LOW |
| 8 | `tests/test_handlers.py` | modified | yes | full suite (`**_kw` compat) | **YES** (if full gate) | LOW — 2 lines |
| 9 | `tests/test_sw06_unwatch_db_failure_propagation.py` | modified | yes | full suite (`**_kw` compat) | **YES** (if full gate) | LOW — 11 lines |
| 10 | `tests/test_f03_watch_conversation_status_normalization.py` | untracked | **no** | full suite (2 tests) | **YES** (if full gate) | LOW — but **DEF-013 scope, not DEF-011** |
| 11 | `tests/test_wp07_atomic_state_outcome.py` | untracked | **no** | full suite (9 tests) | **YES** (if full gate) | LOW — **NEW-DEF-03 scope** |
| 12 | `tests/test_wp07_f1_notification_failure.py` | untracked | **no** | full suite (14 tests) | **YES** (if full gate) | LOW — **F-1 Option C scope** |
| 13 | `tests/test_wp07_nav01_nav03_nav04_atomic.py` | untracked | **no** | full suite (25 tests) | **YES** (if full gate) | LOW — **NAV scope** |
| 14 | `tests/test_wp07_nav02_nav05_simple_clear_atomic.py` | untracked | **no** | full suite (14 tests) | **YES** (if full gate) | LOW — **NAV scope** |
| 15 | `tests/test_wp07_nav06_open_conversation_atomic.py` | untracked | **no** | full suite (12 tests) | **YES** (if full gate) | LOW — **NAV scope** |
| 16 | `tests/test_wp07_watch_unwatch_atomicity.py` | untracked | **no** | full suite (24 tests) | **YES** (if full gate) | LOW — **NEW-DEF-03 scope** |
| 17 | `pytest.ini` | unmodified | yes | test config (`asyncio_mode=auto`, `pythonpath=.`) | **YES** (self-containment) | LOW |
| 18 | `requirements.txt` | unmodified | yes | dependency pinning | **YES** | LOW |
| 19 | `requirements-dev.txt` | unmodified | yes | test tooling | **YES** | LOW |
| 20 | `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md` | tracked | yes | scope authority | **YES** | LOW |
| 21 | `docs/audits/OHB2-WP07-DEF011-REMEDIATION-AUDIT.md` | untracked | **no** | scope authority (A/B/C split) | **YES** | LOW |
| 22 | `docs/audits/OHB2-WP07-DEF011-IMPLEMENTATION-PLAN.md` | untracked | **no** | AC-1..AC-9, T-1..T-14 | **YES** | LOW |
| 23 | `docs/reviews/OHB2-WP07-BATCH03-EXTERNAL-REVIEW-HANDOFF-REPORT.md` | untracked | **no** | DEF-011-B context | **YES** | LOW |
| 24 | `docs/reviews/OHB2-WP07-BATCH03-EXTERNAL-REVIEW-CHECKLIST.md` | untracked | **no** | review procedure | **YES** | LOW |
| 25 | `docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md` | untracked | **no** | F-01 record | **YES** | LOW |

### 1.3 Files deliberately **excluded** (and why)

| File | Reason for exclusion |
|---|---|
| `.agent/PROGRESS.md` | **Not test-required** (absent from the reconstruction that produced 3419/0). It is a running work log with 236 added lines, 35 keyword hits for token/secret/password (all mentions, no values) and long unrelated history. **Excluding it reduces disclosure surface.** |
| `.openhands/**` | Agent memory; git-ignored; private working notes. |
| `.venv/**` | Virtual environment; not portable, not needed (dependencies come from `requirements*.txt`). |
| `__pycache__/**`, `.pytest_cache/**` | Build caches; non-deterministic; the Batch-03 package had a `__pycache__` hygiene defect (PACK-02). |
| `.env`, any credential file | **Never packaged.** (`.env` does not exist in the tree; only `.env.example`, already public.) |
| `docs/design/**`, other WP-05/WP-06 reports | Unrelated scope; would inflate disclosure. |
| `bot/web/**`, `tests/frontend/**`, `docs/MINI_APP.md` | **Mini App — explicitly out of scope and untouched.** |
| Any `*.sqlite`, `*.db`, `*.wal`, `*.shm` | Runtime data; may contain user content. |

### 1.4 Scope decomposition (the central fact)

`bot/attachments.py` carries **two** unreviewed batches (measured in the previous task and re-verified here):

| Segment | Base → Target | Δ |
|---|---|---|
| Batch-03 DEF-011-B | `origin/main` → Batch-03 snapshot | +245 / −59 |
| Batch-04 F-01 | Batch-03 snapshot → worktree | +162 / −65 |
| **Total vs `origin/main`** | | **+386 / −103** |

`store_async` and `sweep_async` do **not** exist on `origin/main` (`grep -c` = 0), which proves
DEF-011-B is local-only. The package must therefore present **both** deltas separately (§3.3).

---

## 2. Phase 2 — Reproduced failure evidence

All work was done in **temporary directories** (`/tmp/pkgrepro.*`, `/tmp/minimal.*`), built with
`git archive origin/main`. The repository, the archive and the sidecar were never modified. All
temp directories were deleted afterwards.

### 2.1 Reproduction A — package's own two test files (the reported failure)

```sh
T=$(mktemp -d /tmp/pkgrepro.XXXXXX)
cd /workspace/project/OpenHandBot
git archive origin/main | tar -x -C "$T"
mkdir -p "$T/.pkg" && tar xzf <archive> -C "$T/.pkg"
P="$T/.pkg/OHB2-WP07-BATCH04-DEF011-F01-20261119"
cp "$P/snapshot/bot/attachments.py"        "$T/bot/attachments.py"
cp "$P/snapshot/tests/test_f01_reaper_fs_offload.py" \
   "$P/snapshot/tests/test_def011_fs_offload.py"     "$T/tests/"
cd "$T" && python -m pytest -q tests/test_f01_reaper_fs_offload.py tests/test_def011_fs_offload.py
```

| Result | Value |
|---|---|
| Outcome | **`1 failed, 33 passed` in 2.20s** |
| Failing test | `tests/test_def011_fs_offload.py::test_T8b_local_capped_read_runs_off_event_loop_thread` |
| Assertion | `assert seen and all(t != loop_thread for t in seen), "القراءة حصلت على خيط الحلقة"` |
| Manifest check | `sha256sum -c MANIFEST.sha256` → all OK (the package is **internally** intact) |

**⇒ The previously reported `1 failed / 33 passed` is exactly reproducible. Nothing changed.**

### 2.2 Reproduction B — F-01 subset alone

| Command | Result |
|---|---|
| `pytest -q tests/test_f01_reaper_fs_offload.py` | **`13 passed` in 0.89s** |

**⇒ F-01 is self-sufficient in the current package.**

### 2.3 Reproduction C — DEF-011-B subset alone

| Command | Result |
|---|---|
| `pytest -q tests/test_def011_fs_offload.py` | **`1 failed, 20 passed` in 1.22s** |

**⇒ The single failure is DEF-011-B-only, not F-01.**

### 2.4 Root-cause confirmation

Adding **only** `bot/handlers.py` to the reconstruction:

| Command | Result |
|---|---|
| `cp bot/handlers.py "$T/bot/"` then both files | **`34 passed` in 2.13s** |

The missing hunk in `bot/handlers.py`:

```diff
+import functools
+from anyio import to_thread
-                    return iter([_read_local_capped(file_path, max_bytes)])
+                    data = await to_thread.run_sync(
+                        functools.partial(_read_local_capped, file_path, max_bytes)
```

**⇒ Root cause proven: the package omits the file that contains a reviewed DEF-011-B change.**

### 2.5 Full-suite reconstruction ladder

| Step | Files in reconstruction | Result |
|---|---|---|
| a | `attachments` + `handlers` + `watcher` + `app` + 2 tests | **34 passed** (focused) |
| b | same, **no `db.py`**, full suite | **100 failed, 3219 passed** |
| c | + `db.py` + 2 modified tests | **3319 passed** |
| d | + 7 untracked WP-07 test files | **3419 passed** |
| — | *worktree control* | **3419 passed** |

**Arithmetic of the 100-test gap:** 134 untracked tests total − 34 already present = **100** =
exactly the 7 other untracked WP-07 test files. Step (d) reaching **3419 — identical to the
worktree** — confirms the required set is **complete and sufficient**.

---

## 3. Phase 3 — Proposed corrected package design

### 3.1 Design goals

The package must let a **separate reviewer** (a) reconstruct the exact reviewed state, (b) see the
`origin/main` baseline, (c) separate DEF-011-B from F-01, (d) run the tests **without the original
worktree**, (e) verify every file, (f) detect missing/extra/altered files, (g) distinguish
implementation evidence from review evidence.

### 3.2 Proposed layout

```
OHB2-WP07-BATCH04-DEF011-F01-REV2-<YYYYMMDD>/
├── README.md                       # what this is, how to verify, what is out of scope
├── PACKAGE.sha256                  # archive's own digest, published alongside (not inside)
├── MANIFEST.sha256                 # every payload file, one line each, sorted
├── BASE.txt                        # base commit + worktree HEAD + branch + counts
├── WORKTREE-VS-HEAD.diff           # complete patch: all 5 tracked mods (unified, git format)
├── UNTRACKED-FILES.diff            # new files as /dev/null diffs (or list + copies)
├── SCOPE.md                        # DEF-011-B vs F-01 split with the measured deltas
├── snapshot/                       # exact implementation state (5 files)
│   ├── bot/attachments.py
│   ├── bot/handlers.py
│   ├── bot/db.py
│   ├── bot/watcher.py
│   └── bot/app.py
├── tests/                          # all 9 test files (2 scope + 7 regression)
│   ├── test_def011_fs_offload.py
│   ├── test_f01_reaper_fs_offload.py
│   ├── test_handlers.py
│   ├── test_sw06_unwatch_db_failure_propagation.py
│   ├── test_f03_watch_conversation_status_normalization.py
│   ├── test_wp07_atomic_state_outcome.py
│   ├── test_wp07_f1_notification_failure.py
│   ├── test_wp07_nav01_nav03_nav04_atomic.py
│   ├── test_wp07_nav02_nav05_simple_clear_atomic.py
│   ├── test_wp07_nav06_open_conversation_atomic.py
│   └── test_wp07_watch_unwatch_atomicity.py
├── config/
│   ├── pytest.ini
│   ├── requirements.txt
│   └── requirements-dev.txt
└── docs/
    ├── OHB2-CORRECTED-REMEDIATION-BASELINE.md
    ├── OHB2-WP07-DEF011-REMEDIATION-AUDIT.md
    ├── OHB2-WP07-DEF011-IMPLEMENTATION-PLAN.md
    ├── OHB2-WP07-BATCH03-EXTERNAL-REVIEW-HANDOFF-REPORT.md
    ├── OHB2-WP07-BATCH03-EXTERNAL-REVIEW-CHECKLIST.md
    └── OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md
```

### 3.3 Patch representation (explicit requirement)

`WORKTREE-VS-HEAD.diff` alone is **insufficient**: `git diff HEAD` **does not include untracked
files**. Verified: a temp-index run showed 10 files / 1960 insertions once the 3 new tests were
added via `git add -N`.

Two acceptable, unambiguous representations:

**Option 1 — single complete patch (preferred).** Build with a **throwaway index** so the real
index is untouched:

```sh
TMPIDX=$(mktemp -u /tmp/tmpidx.XXXXXX)
GIT_INDEX_FILE=$TMPIDX git read-tree origin/main
GIT_INDEX_FILE=$TMPIDX git add -N <all 16 code/test paths>
GIT_INDEX_FILE=$TMPIDX git diff > WORKTREE-VS-HEAD.diff
rm -f "$TMPIDX"
```

Verified working: produced 10 files / +1960 / −228, and `git status` still showed **staged=0**.

**Option 2 — split representation.** `WORKTREE-VS-HEAD.diff` (tracked mods only) **plus**
`UNTRACKED-FILES.diff` (`git diff --no-index /dev/null <file>` per new file). Equally
unambiguous, and makes "new file" explicit.

Either way the package must state: **base commit `52e7789cc8cc97a7f7c09c9592226ab117db99a2`**,
and that `snapshot/` is the authoritative content (the diff is for **inspection**, not application).

### 3.4 Separating DEF-011-B from F-01

`SCOPE.md` must contain the measured split and the pre-fix reference hash:

| Item | Value |
|---|---|
| `origin/main` → Batch-03 snapshot (DEF-011-B) | +245 / −59 |
| Batch-03 snapshot → worktree (F-01) | +162 / −65 |
| Total vs `origin/main` | +386 / −103 |
| Pre-F-01 file (Batch-03 snapshot) SHA-256 | `e72745eb9d628c20daec3caddd4c6e95fd3365ece6655ec2adb2d03138b99d2e` |
| Post-F-01 file SHA-256 | `d27fb79870d900f584aebfea861619f6e4000ba1b9cb026d359189ae1e914ed5` |

Providing the pre-F-01 file (or its hash + a `DEF011B-VS-F01.diff`) lets the reviewer **reproduce
the F-01 mutation check** (revert → tests must fail) without guessing.

### 3.5 Manifest format

`MANIFEST.sha256` — `sha256sum`-compatible, sorted, one line per payload file, **relative to the
package root**, covering `snapshot/`, `tests/`, `config/`, `docs/`, `BASE.txt`, `SCOPE.md`,
`README.md`, and both diffs:

```
<64-hex>  snapshot/bot/attachments.py
<64-hex>  tests/test_f01_reaper_fs_offload.py
...
```

Rules: exactly one line per file; no duplicates; no absolute paths; no `..`; no symlinks; the
manifest **must not** list itself or `PACKAGE.sha256` (self-reference is impossible).

### 3.6 Reproducible build procedure

```sh
# 0. Deterministic inputs only; build in a clean staging dir
STAGE=$(mktemp -d) && PKG="$STAGE/OHB2-WP07-BATCH04-DEF011-F01-REV2-20261119"
mkdir -p "$PKG"/{snapshot/bot,tests,config,docs}

# 1. Copy payload (explicit list — never `cp -r .`)
cd /workspace/project/OpenHandBot
cp bot/attachments.py bot/handlers.py bot/db.py bot/watcher.py bot/app.py "$PKG/snapshot/bot/"
cp tests/test_def011_fs_offload.py tests/test_f01_reaper_fs_offload.py \
   tests/test_handlers.py tests/test_sw06_unwatch_db_failure_propagation.py \
   tests/test_f03_watch_conversation_status_normalization.py \
   tests/test_wp07_atomic_state_outcome.py tests/test_wp07_f1_notification_failure.py \
   tests/test_wp07_nav01_nav03_nav04_atomic.py tests/test_wp07_nav02_nav05_simple_clear_atomic.py \
   tests/test_wp07_nav06_open_conversation_atomic.py tests/test_wp07_watch_unwatch_atomicity.py "$PKG/tests/"
cp pytest.ini requirements.txt requirements-dev.txt "$PKG/config/"
cp docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md \
   docs/audits/OHB2-WP07-DEF011-REMEDIATION-AUDIT.md \
   docs/audits/OHB2-WP07-DEF011-IMPLEMENTATION-PLAN.md \
   docs/reviews/OHB2-WP07-BATCH03-EXTERNAL-REVIEW-HANDOFF-REPORT.md \
   docs/reviews/OHB2-WP07-BATCH03-EXTERNAL-REVIEW-CHECKLIST.md \
   docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md "$PKG/docs/"

# 2. BASE.txt + SCOPE.md + README.md written from verified values (not from memory)

# 3. Diffs (§3.3), then manifest
cd "$PKG" && find . -type f ! -name MANIFEST.sha256 | LC_ALL=C sort | xargs sha256sum > MANIFEST.sha256

# 4. Deterministic archive (verified reproducible)
tar --sort=name --mtime='UTC 2026-11-19' --owner=0 --group=0 --numeric-owner \
    -czf "$STAGE/OHB2-WP07-BATCH04-DEF011-F01-REV2-20261119.tar.gz" -C "$STAGE" "$(basename "$PKG")"

# 5. Sidecar
cd "$STAGE" && sha256sum OHB2-WP07-BATCH04-DEF011-F01-REV2-20261119.tar.gz \
    > OHB2-WP07-BATCH04-DEF011-F01-REV2-20261119.tar.gz.sha256
```

**Reproducibility verified:** two consecutive `tar` runs with these flags produced the **same**
SHA-256. (A naive `tar czf` also matched here only because mtimes happened to agree — the explicit
`--mtime/--owner/--sort` flags are what make it *guaranteed* reproducible across machines.)

---

## 4. Phase 4 — Package acceptance criteria

### 4.1 Package-integrity gates (must all pass)

| # | Check | Pass condition |
|---|---|---|
| G1 | Clean extraction into a new empty directory | `tar xzf` exits 0; no pre-existing files required |
| G2 | No dependency on the original worktree | extraction + tests succeed with the repo absent/unmounted |
| G3 | No missing imports / test config | `pytest` collects with no `ImportError`/`ModuleNotFoundError` |
| G4 | DEF-011-B subset passes in the snapshot | `pytest tests/test_def011_fs_offload.py` → **21 passed** |
| G5 | F-01 regression subset passes | `pytest tests/test_f01_reaper_fs_offload.py` → **13 passed** |
| G6 | Combined relevant suite passes | both files → **34 passed**; full suite → **3419 passed, 0 failed** |
| G7 | Manifest completeness | every required file appears **exactly once** |
| G8 | No unmanifested files | `find . -type f` minus manifest set = **∅** |
| G9 | No traversal / symlinks | no absolute paths, no `..`, no symlinks in `tar tzf`/`tar tvzf` |
| G10 | Archive digest matches sidecar | `sha256sum -c <sidecar>` → OK |
| G11 | Rebuild reproducibility | two independent builds from identical inputs → **identical** SHA-256 |
| G12 | No secrets / no unrelated private files | secret scan clean; no `.env`, no `.openhands/`, no `.venv/`, no caches, no DB files |

### 4.2 Three separate verdicts (must not be conflated)

| Dimension | Who decides | Meaning |
|---|---|---|
| **Package integrity** | package builder + reviewer | G1–G12 pass. Says **nothing** about whether the code is correct. |
| **Technical correctness** | independent reviewer | Does the offload actually work? Does `_remove_file`/`os.lstat`/`os.unlink` run off the loop thread? Is SQLite kept on the owner thread? |
| **Independent-review acceptance** | owner | Only after the reviewer's independence is established (§5) and the owner accepts. |

**A green G1–G12 run is not acceptance.** Conversely, a technical PASS from a non-independent
reviewer is not acceptance either.

---

## 5. Security and disclosure requirements

1. **Secret scan before packaging** — the 25 payload files were scanned this task:
   **no credential patterns** (`ghp_`/`ghu_`/`sk-…`/`AKIA…`/`PRIVATE KEY`/inline passwords).
   Must be re-run at build time, and **also** on the diff files.
2. **`.agent/PROGRESS.md` is excluded** — it is not test-required and carries long unrelated
   history plus 35 keyword mentions. Excluding it lowers disclosure.
3. **`bot/db.py` is MEDIUM risk** — it carries 269 lines of **WP-07 atomicity** work that is
   **not DEF-011**. It is needed only for the full-suite gate. Owner should decide whether the
   package ships the full gate (with `db.py` + 7 unrelated test files) or only the focused
   34-test scope (no `db.py`). **This is an open decision (§7).**
4. **Seven of the nine test files are unrelated scope** — they belong to DEF-013, NEW-DEF-03,
   NAV-01..06 and F-1 Option C. They are needed only for the full-suite count. Their presence
   must be **labelled** in `SCOPE.md` so a reviewer does not treat them as DEF-011 evidence.
5. **Never package** `.env`, credentials, tokens, `.openhands/`, `.venv/`, `__pycache__/`,
   `.pytest_cache/`, `*.sqlite*`, or any Mini App file.
6. **Transfer is a separate authorization** — packaging ≠ publishing. Nothing here authorizes
   upload, push, PR, visibility change or CI.
7. **Sidecar provenance** — a sidecar produced on the implementation host is **internal
   consistency only**. Independent authentication requires the reviewer to recompute the digest
   from the **received bytes**.

---

## 6. Exact C1 / C2 execution steps (for when authorized)

### C1 — Make the package self-contained

| Step | Action | Verification |
|---|---|---|
| C1.1 | Confirm base is unchanged (`HEAD == origin/main == 52e7789…`; 0 staged) | `git rev-parse` both |
| C1.2 | Re-verify the 25 payload files exist and hash them | record SHA-256 for each |
| C1.3 | Create staging dir + `snapshot/`, `tests/`, `config/`, `docs/` | `mkdir -p` |
| C1.4 | Copy the 5 snapshot files (explicit list) | 5 files present |
| C1.5 | Copy the 11 test files (2 scope + 2 modified + 7 regression) | 11 files present |
| C1.6 | Copy `pytest.ini`, `requirements.txt`, `requirements-dev.txt` | 3 files |
| C1.7 | Copy the 6 scope documents | 6 files |
| C1.8 | Write `BASE.txt` (commit, branch, counts, date) | matches §1.1 |
| C1.9 | Write `SCOPE.md` with the measured split + pre-fix hash (§3.4) | deltas match +245/−59 and +162/−65 |
| C1.10 | Generate `WORKTREE-VS-HEAD.diff` via temp index (§3.3) | contains `diff --git`, 10 files |
| C1.11 | Write `README.md` (verify steps, out-of-scope list, "not a review") | — |
| C1.12 | **Secret-scan the staging dir** | zero findings, else stop |

### C2 — Rebuild reproducibly + verify integrity

| Step | Action | Verification |
|---|---|---|
| C2.1 | Generate `MANIFEST.sha256` (sorted, relative, no self-entry) | one line per file |
| C2.2 | Verify manifest in place | `sha256sum -c MANIFEST.sha256` → all OK |
| C2.3 | Build archive with deterministic flags (§3.6) | exit 0 |
| C2.4 | Generate sidecar | sidecar contains the new digest |
| C2.5 | **Build twice**, compare | identical SHA-256 (G11) |
| C2.6 | Fresh-extract into an empty dir | `tar tzf`/`tvzf`: no traversal, no symlinks (G9) |
| C2.7 | Manifest check in the extraction | all OK (G7) |
| C2.8 | Unmanifested-file check | `comm` of `find` vs manifest = ∅ (G8) |
| C2.9 | **Reconstruct from `origin/main` + snapshot only** | focused 34 passed; full 3419 passed (G2, G4–G6) |
| C2.10 | Record the result table in the report | evidence, not claims |

**C2.9 is the decisive gate** — it is the only step that proves the package is independent of the
original worktree.

---

## 7. Risks, dependencies and unresolved decisions

### 7.1 Risks

| # | Risk | Mitigation |
|---|---|---|
| R1 | Shipping `db.py` + 7 unrelated test files discloses WP-07/NAV/F-1-C scope | Label in `SCOPE.md`; or ship the focused 34-test package |
| R2 | A reviewer might treat a green full suite as DEF-011 acceptance | §4.2 three-verdict rule; state it in `README.md` |
| R3 | Non-deterministic archive | deterministic tar flags (verified) |
| R4 | A future commit changes HEAD mid-build | assert `HEAD == 52e7789` at C1.1 and C2.10 |
| R5 | Package size growth from 8 → ~25 files | acceptable; still tiny |
| R6 | Reviewer cannot reproduce the F-01 mutation check without the pre-fix file | include pre-fix hash + `DEF011B-VS-F01.diff` (§3.4) |
| R7 | Sidecar is not independent authentication | §5.7 |

### 7.2 Dependencies

- Owner decision on **package scope** (§7.3, D-1).
- Owner authorization to **build** C1/C2 (not granted).
- A later, **separate** authorization for transfer/publication.
- Independence route (Route A/B) remains **undecided** — see the briefing.

### 7.3 Unresolved decisions (owner)

| # | Decision | Options |
|---|---|---|
| **D-1** | Package scope | **(a)** Focused: 4 bot files + 2 tests → 34 tests, no `db.py`, minimum disclosure. **(b)** Full: + `db.py` + 2 modified tests + 7 unrelated tests → 3419 tests, more disclosure. **Recommendation: (b)**, because a reviewer needs the full regression to judge "nothing else broke" — but the owner must accept the wider scope. |
| **D-2** | Include the pre-F-01 file for the mutation check | yes (recommended) / hash only |
| **D-3** | Replace the existing archive or publish REV2 alongside | **Recommendation: REV2 alongside**, preserving the original as evidence |
| **D-4** | Transfer route (A public / B private / neither) | see the owner briefing |

---

## 8. Statement of non-implementation

**C1 and C2 have NOT been executed.** As of this document:

- The existing archive (`47b9923…0bf71d`, `107643` B) and its sidecar are **untouched**.
- **No** replacement archive or sidecar was created.
- **No** source code, test, implementation report or package README was modified.
- **No** staging, commit, push, branch, PR or CI trigger occurred; visibility unchanged.
- **No** source or artifact was uploaded, transferred or disclosed.
- **No** token or credential was used, printed or exposed.
- The repository is at `HEAD 52e7789`, **0 staged, 8 modified, 40 pre-existing untracked**,
  8 ignored — unchanged apart from the two authorized deliverables.
- **F-01 and DEF-011 remain NOT independently reviewed, NOT accepted, NOT closed.**
  F-02, F-03 remain open; WP-09 remains unverified.

Execution of C1/C2 requires **separate explicit owner authorization**, including a decision on
**D-1** (package scope).
