# OHB2 — WP-07 / Batch 04 — C1/C2 Package Implementation Report

**Task:** `OHB2-WP07-BATCH04-REVIEW-PACKAGE-REMEDIATION-C1-C2`
**Date:** 2026-11-19
**Scope authorized:** **FOCUSED_34_TESTS** (owner decision D-1) — DEF-011-B 21 + F-01 13
**Verdict:** **`C1_C2_PACKAGE_READY_WITH_NOTES`**

> **C1 and C2 were executed** under the owner authorization carried by this task.
> **F-01 and DEF-011 remain NOT independently reviewed, NOT accepted, NOT closed.**
> No publication, transfer, visibility change, CI run or external disclosure occurred.

---

## 0. Authorization basis

The task text carried, explicitly and unambiguously:

- `D-1 package scope: FOCUSED_34_TESTS`
- `C1 and C2 implementation must proceed only if this task is accompanied by explicit owner
  authorization for both C1 and C2 and the D-1 focused-34 scope.`

Both conditions were satisfied, so work proceeded. Had either been absent, the correct verdict
would have been `BLOCKED_OWNER_AUTHORIZATION_REQUIRED`.

**Explicitly NOT authorized (and not done):** repository visibility change, GitHub publication,
external transfer, CI execution, independent review, merge, deploy, release.

---

## 1. Before/after state

### 1.1 Git — unchanged by this task

| Field | Before | After |
|---|---|---|
| Repo root | `/workspace/project/OpenHandBot` | same |
| Remote | `https://github.com/TM-AEM/OpenHandBot.git` | same |
| Branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` | same |
| HEAD | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` | **same** |
| `origin/main` | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` | same |
| Divergence | `0 0` | `0 0` |
| Staged | 0 | **0** |
| Modified | 8 | **8** |
| Untracked | 44 | **45** (+ the report only) |
| Ignored | 8 | **8** |

**No production source or test file was modified.** All package assembly happened in
`/tmp/c1c2-build/…` and `/workspace/review-packages/`.

### 1.2 Original Batch-04 package — preserved byte-for-byte

| Artifact | Before | After |
|---|---|---|
| `OHB2-WP07-BATCH04-DEF011-F01-20261119.tar.gz` | `47b9923…0bf71d`, 107643 B, mtime `2026-11-19 16:06:26` | **identical** |
| `…tar.gz.sha256` | `84460e5…ab63ab` | **identical** |
| Package dir `MANIFEST.sha256` | `9558eb5f…8c5b35` | **identical** |

The original was **never** edited, rebuilt, replaced or deleted.

---

## 2. Phase 1 — Frozen inputs

### 2.1 Test inventory (verified, not assumed)

| Subset | Collected | Expected | Match |
|---|---|---|---|
| `tests/test_def011_fs_offload.py` | **21** | 21 | ✅ |
| `tests/test_f01_reaper_fs_offload.py` | **13** | 13 | ✅ |
| Combined | **34** | 34 | ✅ |

Source state matched the approved plan exactly (HEAD `52e7789`, 0 staged, 8 modified). **No
discrepancy** was found, so no stop condition triggered.

### 2.2 Source hashes (frozen)

| File | SHA-256 |
|---|---|
| `bot/attachments.py` | `d27fb79870d900f584aebfea861619f6e4000ba1b9cb026d359189ae1e914ed5` |
| `bot/handlers.py` | `40dd8902595c1a63875f8c9d37d4fed4a454be15e1390e5386dcfa9bce058014` |
| `bot/watcher.py` | `06f3dd4c23e3e154a311bc26b749240a92abe825b8a14b29ac9dbaee41aa6fcb` |
| `bot/app.py` | `fb3d5038fbe220ec736feb14b7ec7d1b1f396f31472ddcbc789f182695143e24` |
| `tests/test_def011_fs_offload.py` | `db0f5b6177a7a51652a19be71c27dca56ce97182b1b09966f1dd2e97d3a7e99f` |
| `tests/test_f01_reaper_fs_offload.py` | `0caa88c6e8c3cae176d90464d2f46e1495e6512fa282c33bdc795daf01fdae2e` |

### 2.3 Key Phase-1 discovery: `db.py` is not needed

The approved plan assumed the focused package might need `bot/db.py`. **Measured otherwise:**

| Variant | Result |
|---|---|
| `attachments` + `handlers` only, `db.py` from `origin/main` | **34 passed** |
| + `watcher` + `app` | **34 passed** |
| `watcher`/`app` reverted to `origin/main` | **34 passed** |

⇒ The 34 focused tests need **only** `attachments.py` + `handlers.py`. `watcher.py` and `app.py`
are included because they are DEF-011-B **call sites** the reviewer must inspect, and
`bot/db.py` (269 lines of unrelated WP-07 atomicity work) is **excluded** — eliminating the
plan's MEDIUM-risk disclosure item.

### 2.4 Disclosure delta vs the already-handed-off Batch-03 package

| File | vs Batch-03 snapshot | New disclosure? |
|---|---|---|
| `bot/attachments.py` | differs (+162 / −65) | **Yes** — the F-01 delta, which is this review's subject |
| `bot/handlers.py` | **byte-identical** (`40dd8902…`) | **No** |
| `bot/watcher.py` | **byte-identical** (`06f3dd4c…`) | **No** |
| `bot/app.py` | **byte-identical** (`fb3d5038…`) | **No** |

`bot/handlers.py` carries 44 hunks, most of them **NEW-DEF-03** (not DEF-011-B). It was
included **whole and unmodified** rather than synthetically reduced, because (a) it is already
disclosed in Batch-03, and (b) a fabricated partial file would not exist in the repository and
would be unverifiable. Full rationale in `SCOPE.md` §2.1.

---

## 3. Phase 2 (C1) — Package built

### 3.1 Exact file inventory (20 payload files + manifest)

| # | Path | Size (B) | SHA-256 |
|---|---|---|---|
| 1 | `BASE.txt` | 231 | `a1cf656392334121a16bab0a04bb9ddc0b566338b414c56d94a0b20e49e6c184` |
| 2 | `DEF011B-VS-F01.diff` | 20288 | `98e3e9c2f28af64c40c83defcfacc320ac5d4795895074289e5f8c8bd89e3707` |
| 3 | `README.md` | 6490 | `e36cf44772b3ee49d5f6d1c2ebc28221fd1a1ea1d3323c9d3536295eab7c826b` |
| 4 | `SCOPE.md` | 6769 | `6366d648a3f71a597c31ccd756d54e8d26e51d7c31fbf354f77db022bb252c5a` |
| 5 | `WORKTREE-VS-HEAD.diff` | 102252 | `3780ebd67d36e84e8fbf69cecc44d538c52ea926a8a0e391a486fda367af5b1d` |
| 6 | `config/pytest.ini` | 62 | `4950b359cb81cc6fe0ba246724c53716a0f27753df7d41493298600fbe82ac8a` |
| 7 | `config/requirements-dev.txt` | 459 | `a4590b70c77e5958da7afda7131eb5990d9e1fe2151d54a76af08c662a799b8c` |
| 8 | `config/requirements.txt` | 479 | `ce1f42b5069fb8972c07d85700471880a573a3def220b989a05732ad9d7b9b0a` |
| 9 | `docs/OHB2-CORRECTED-REMEDIATION-BASELINE.md` | 141146 | `dccc28fd68a6b505f59a2f3f7ec04ee5390a32a5ffed97e85abda8d0d5a2656f` |
| 10 | `docs/OHB2-WP07-BATCH03-EXTERNAL-REVIEW-HANDOFF-REPORT.md` | 18101 | `9c33d20e4e2851c76479c589bc1a9ea82db18e8adfcc572578a3bf776df60223` |
| 11 | `docs/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md` | 16778 | `141c7f074576088a70d1c4e6fa2ba01f8d6edc5cc137b3f297df4639ddde15d5` |
| 12 | `docs/OHB2-WP07-DEF011-IMPLEMENTATION-PLAN.md` | 15516 | `a564f43204bac139e332ede95112c7b7a2a4211ec48011bae89ba6cf50b1d17b` |
| 13 | `docs/OHB2-WP07-DEF011-REMEDIATION-AUDIT.md` | 22635 | `45e3ed21301d819419e5f3e685f8e5d43981a0d75e36459b509888e182e8b1d5` |
| 14 | `mutation/attachments.py.pre-F01` | 90173 | `e72745eb9d628c20daec3caddd4c6e95fd3365ece6655ec2adb2d03138b99d2e` |
| 15 | `snapshot/bot/app.py` | 25081 | `fb3d5038fbe220ec736feb14b7ec7d1b1f396f31472ddcbc789f182695143e24` |
| 16 | `snapshot/bot/attachments.py` | 94981 | `d27fb79870d900f584aebfea861619f6e4000ba1b9cb026d359189ae1e914ed5` |
| 17 | `snapshot/bot/handlers.py` | 182968 | `40dd8902595c1a63875f8c9d37d4fed4a454be15e1390e5386dcfa9bce058014` |
| 18 | `snapshot/bot/watcher.py` | 52142 | `06f3dd4c23e3e154a311bc26b749240a92abe825b8a14b29ac9dbaee41aa6fcb` |
| 19 | `tests/test_def011_fs_offload.py` | 20570 | `db0f5b6177a7a51652a19be71c27dca56ce97182b1b09966f1dd2e97d3a7e99f` |
| 20 | `tests/test_f01_reaper_fs_offload.py` | 13516 | `0caa88c6e8c3cae176d90464d2f46e1495e6512fa282c33bdc795daf01fdae2e` |

Snapshot hashes 15–18 and test hashes 19–20 are **identical to the frozen Phase-1 source
hashes** (§2.2) — the package carries exactly the reviewed state.

### 3.2 Delta representation

| Artifact | Contents |
|---|---|
| `WORKTREE-VS-HEAD.diff` | Complete `git diff` vs `origin/main` for **exactly the 6 packaged code/test files** — 6 `diff --git` headers, 2 `new file mode` entries (the untracked tests) |
| `DEF011B-VS-F01.diff` | `attachments.py` only: pre-F-01 → post-F-01 = **+162 / −65** |

`WORKTREE-VS-HEAD.diff` was generated with a **throwaway index** (`GIT_INDEX_FILE` in `/tmp`) so
the repository index was never touched (`staged=0` re-verified). An earlier draft accidentally
included 4 out-of-scope files (`.agent/PROGRESS.md`, `db.py`, 2 test files); it was **caught and
restricted** before publishing — the shipped diff contains only packaged paths.

---

## 4. Phase 4 (C2) — Reproducible build

### 4.1 Two independent builds

| Build | Directory | Manifest lines |
|---|---|---|
| 1 | `/tmp/c1c2-build/build1/…` | 20 |
| 2 | `/tmp/c1c2-build/build2/…` | 20 |

`diff build1/MANIFEST.sha256 build2/MANIFEST.sha256` → **identical** ⇒ payloads byte-identical.

### 4.2 Deterministic archive

```
tar --sort=name --mtime='UTC 2026-11-19 00:00:00' --owner=0 --group=0 \
    --numeric-owner --format=gnu -czf <pkg>.tar.gz <pkg>
```

| Build | Archive SHA-256 |
|---|---|
| 1 | `de8e4fc9c751f900d8235b5a5fd8302620e1841114b250441bcdaf3a3c8bf8b5` |
| 2 | `de8e4fc9c751f900d8235b5a5fd8302620e1841114b250441bcdaf3a3c8bf8b5` |

**⇒ REPRODUCIBLE.** Size `223474` B in both.

### 4.3 Published artifacts (new names — original untouched)

| Artifact | Path | SHA-256 |
|---|---|---|
| Archive | `/workspace/review-packages/OHB2-WP07-BATCH04-DEF011-F01-REV2-FOCUSED34-20261119.tar.gz` | `de8e4fc9c751f900d8235b5a5fd8302620e1841114b250441bcdaf3a3c8bf8b5` |
| Sidecar | `…-REV2-FOCUSED34-20261119.tar.gz.sha256` | (126 B) |

`sha256sum -c <sidecar>` → **OK**.

### 4.4 Extraction verification (from the *published* archive)

| Check | Result |
|---|---|
| Fresh extraction into empty dir | OK |
| Absolute paths / `../` traversal | **none** |
| Symlinks | **none** |
| Manifest verify in extraction | **20/20 OK** |
| Declared vs actual file count | **20 = 20** |
| Unmanifested (extra) files | **none** |
| Missing files | **none** |

---

## 5. Phase 3 — Independent reconstruction (the decisive gate)

Performed in `/tmp/independent.*` from **`git archive 52e7789` + package files only**, with the
implementation worktree **not** on the path.

**Import-resolution proof (no worktree fallback):**

```
cwd = /tmp/independent.jREQj8
bot.attachments from: /tmp/independent.jREQj8/bot/attachments.py
```

### 5.1 Test results

| Subset | Command | Result | Exit |
|---|---|---|---|
| DEF-011-B | `pytest -q tests/test_def011_fs_offload.py` | **21 passed** (1.21s) | 0 |
| F-01 | `pytest -q tests/test_f01_reaper_fs_offload.py` | **13 passed** (0.84s) | 0 |
| Combined | both files | **34 passed** (1.91s) | 0 |
| Final (published archive) | both files | **34 passed** (2.11s) | **0** |

No test was missing, unexpectedly collected, skipped or failed.

### 5.2 F-01 mutation check (non-vacuity proof)

| Step | Result |
|---|---|
| Restore `mutation/attachments.py.pre-F01` | **8 failed, 5 passed** (0.87s) |
| Restore `snapshot/bot/attachments.py` | **13 passed** (0.87s) |

The tests instrument `_remove_file` and assert:

- `test_F01_remove_file_runs_on_worker_thread` — every `_remove_file` call runs off the loop thread;
- `test_F01_os_lstat_and_unlink_run_off_loop` — `assert on_loop["lstat"] == 0` and
  `assert on_loop["unlink"] == 0` on the loop thread.

⇒ `_remove_file`, `os.lstat` and `os.unlink` are proven to execute **outside the event-loop
thread** in the async reaper path, and the tests **detect the original defect**.

---

## 6. Security review

| Check | Result |
|---|---|
| Credential patterns (`ghp_`/`ghu_`/`sk-…`/`AKIA…`/`BEGIN PRIVATE KEY`/`xox[baprs]-`) across all 20 files | **none** |
| High-entropy strings | only document filenames and git SHAs |
| `.env`, `*.sqlite*`, `__pycache__`, `*.pyc`, `.venv` | **absent** |
| `.agent/PROGRESS.md` | **excluded** (not test-required; unrelated history) |
| `bot/db.py` (269 lines of unrelated WP-07 work) | **excluded** — proven unnecessary (§2.3) |
| 7 untracked WP-07 test files | **excluded** — full-suite scope only |
| Mini App files | **none touched or included** |
| Per-file inclusion rationale | recorded in `SCOPE.md` §2 |

**Disclosure delta:** only `bot/attachments.py` adds new content vs the already-handed-off
Batch-03 package. The other 3 bot files are byte-identical to what the reviewer already received.

---

## 7. Limitations and unresolved issues

| # | Item |
|---|---|
| L1 | **The package is not a review.** Integrity and reproducibility are proven; correctness and acceptance are **not**. |
| L2 | **Independence is still unresolved.** No separate machine has been used. A reviewer must prove separate machine-id/host/filesystem per the Batch-03 checklist §0. |
| L3 | **The sidecar is not independent authentication.** The reviewer must recompute SHA-256 from received bytes and compare through a separate channel. |
| L4 | **`bot/handlers.py` carries NEW-DEF-03 content** (44 hunks, mostly not DEF-011-B). It is included whole because it is byte-identical to the already-disclosed Batch-03 snapshot. A reviewer must **not** treat those hunks as DEF-011-B evidence. |
| L5 | **`bot/db.py` is not in the package**, so the full 3,419-test suite cannot be run from it. This is the owner-approved FOCUSED-34 scope (D-1), not a defect. |
| L6 | **DEF-011 A** (ledger) NOT implemented; **DEF-011 C** (UX copy) WP-01 blocked; **F-02**, **F-03** OPEN; **WP-09** (py3.11) UNVERIFIED. |
| L7 | **DEF-011 is NOT closed.** |
| L8 | The build script lives at `/tmp/build-pkg.sh` (outside the repo, not shipped). Its steps are documented in the README and the remediation plan so the build is re-derivable. |
| L9 | Python 3.13 only. No 3.11 interpreter is available, so the 3.11 matrix stays UNVERIFIED. |

---

## 8. Files created

| File | Where |
|---|---|
| `OHB2-WP07-BATCH04-DEF011-F01-REV2-FOCUSED34-20261119.tar.gz` | `/workspace/review-packages/` |
| `…tar.gz.sha256` | `/workspace/review-packages/` |
| `docs/reviews/OHB2-WP07-BATCH04-C1-C2-PACKAGE-IMPLEMENTATION-REPORT.md` | repo (this file) |

**Untracked and unstaged.** No other repository file was created or modified.

---

## 9. Confirmation of safety constraints

- **No** production source code or test was changed.
- **No** Mini App, schema or architectural decision touched.
- **Nothing staged or committed.**
- **No** push, branch, PR, merge.
- **No** visibility change; **no** modifying GitHub API call.
- **No** CI or GitHub Actions triggered.
- **No** upload or external transfer — the package stayed on this host.
- **No** token or credential used, printed or exposed.
- **No** account created, **no** cost incurred.
- **Original Batch-04 archive and sidecar preserved** (hashes and mtime unchanged).
- All tracked, untracked and ignored files preserved, including `.openhands/` and `.agent/`.
- **No** reset, clean, force or destructive Git operation.
- **F-01 and DEF-011 are NOT claimed independently reviewed, accepted or closed.**

---

## 10. Verdict

# `C1_C2_PACKAGE_READY_WITH_NOTES`

The package is **self-contained, integrity-verified and reproducible**, and it independently
reproduces **21 + 13 = 34 passing tests** from a clean base commit. The notes are L1–L9, above —
most importantly that **the package proves nothing about correctness, independence or
acceptance**.

Publication and independent review require **separate explicit owner authorization**.
