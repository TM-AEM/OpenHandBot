# OHB2 — WP-07 / DEF-011 / F-02 — Six-File Publication & CI Report

**Task:** `OHB2-WP07-DEF011-F02-SIX-FILE-PUBLICATION-CI-EXECUTION`
**Date:** 2026-11-20
**Verdict:** **`F02_PUBLISHED_CI_PASS_REVIEW_PENDING`**

---

## 0. Verdict rationale

| Acceptance criterion | Met |
|---|---|
| 1. Exactly six authorized files published; no unrelated file | **YES** |
| 2. Published commit traceable to the verified six-file patch | **YES** |
| 3. PR targets `main` and remains unmerged | **YES** |
| 4. Actual GitHub Actions CI passes on 3.11 **and** 3.13 against the exact publication commit | **YES** |
| 5. CI evidence distinguished from local test evidence | **YES** (§4 vs §3) |
| 6. Review package identifies the exact immutable commit | **YES** |
| 7. No independent-review success claimed before a separate review | **YES** — review still pending |
| 8. D6 explicitly deferred and open | **YES** |
| 9. No deployment, merge, Autopush, or unrelated repo change | **YES** |

Criterion 4 is met and criterion 7 is honoured, so the correct verdict is
`F02_PUBLISHED_CI_PASS_REVIEW_PENDING` — **not** `F02_REVIEW_HANDOFF_READY` (that would imply the
handoff is the endpoint) and **not** any failure verdict.

---

## 1. Fresh base and branch

| Property | Value |
|---|---|
| Repository root | `/workspace/project/OpenHandBot` |
| Base `HEAD` | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| `origin/main` at start | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| Divergence at start | `0 0` |
| Authoring branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` |
| **Publication branch** | `review/ohb2-wp07-def011-f02-six-file-ci` |
| Pre-publication status | `staged=0 modified=8 untracked=71 ignored=8` |
| Post-publication status | `staged=0 modified=8 untracked=71 ignored=8` — **unchanged** |

### 1.1 Patch provenance verified before publication

| Check | Result |
|---|---|
| Patch SHA-256 | `59b701369a3b6d2bf70f8028d3ffc8d22831b2f3eedba8cc4de16997246ebe94` — **matches expected exactly** |
| Patch file list | exactly the 6 expected paths — **no seventh file** |
| `git apply --check` on pristine `HEAD` | **clean** |
| Applying reproduces all six candidate hashes | **yes**, byte-identical |
| `.openhands/`, `.agent/`, unrelated content | **untouched** |

No discrepancy was found, so publication proceeded.

---

## 2. Exact six-file list

| # | Path | SHA-256 at `31dec52` | Δ |
|---|---|---|---|
| 1 | `bot/attachments.py` | `b98d561f0ba0ab27dea4e6bedee7955f68f1f6fa85a39fa81afe8aeb4d818356` | +444 / −104 |
| 2 | `bot/db.py` | `205f1363aaf0b1f8173b74285e263891d333928ba480d478b6b525d4369c694b` | +269 / −66 |
| 3 | `bot/handlers.py` | `40dd8902595c1a63875f8c9d37d4fed4a454be15e1390e5386dcfa9bce058014` | +144 / −41 |
| 4 | `tests/test_def011_fs_offload.py` | `3d3b3a2ac399fec0420e2d769f98c7c2841c69c05f341734aecef68df4f503ea` | +1575 / −0 (new) |
| 5 | `tests/test_handlers.py` | `2b1f978091f45c695803a73845065073690f58f1b1c8d2f41fa38d04c1fa8ea8` | +2 / −2 |
| 6 | `tests/test_sw06_unwatch_db_failure_propagation.py` | `ba2633113424432467edeff6cb74f656bb4b5fe9b762dbcc8a251799b33e07ef` | +11 / −11 |

Commit diffstat: **6 files changed, 2445 insertions(+), 224 deletions(-)**.

**Excluded and confirmed absent from the commit:** `.agent/PROGRESS.md`, `bot/app.py`,
`bot/watcher.py`, the 8 other untracked work-package test files, `.openhands/`, `.agent/`, all `docs/`.

### 2.1 Staging was explicit — never `git add .`

```
git add -- bot/attachments.py bot/db.py bot/handlers.py \
           tests/test_def011_fs_offload.py tests/test_handlers.py \
           tests/test_sw06_unwatch_db_failure_propagation.py
```

`git diff --cached --name-only` returned exactly 6 paths. Staged blobs were verified byte-identical to
the patch-applied reference tree for all six files.

### 2.2 A note on applying the patch

`git apply` was **not** used on the working tree: the working tree already contained the candidate
content, so the patch (built against a clean `HEAD`) reported conflicts and "already exists". Instead
the six files were verified byte-identical to the patch-applied reference (`cmp` → IDENTICAL for all
six) and then staged explicitly. The resulting commit blobs match the reference hashes exactly, so the
commit is provably the same content the patch produces.

---

## 3. Original patch hash

`59b701369a3b6d2bf70f8028d3ffc8d22831b2f3eedba8cc4de16997246ebe94`

Retained as provenance. The published commit — not the patch — is now authoritative.

---

## 4. Publication commit

| Property | Value |
|---|---|
| **Commit SHA** | `31dec52289142d0d0dc2bd16604d88644ba3baba` |
| Parent | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| Author / committer | `openhands <openhands@all-hands.dev>` |
| Files changed | **6** |
| Diffstat | +2445 / −224 |
| Contains `store_async` | **3 occurrences** (absent at parent) |
| Pushed to | `origin/review/ohb2-wp07-def011-f02-six-file-ci` |

Commit-message trailer: `Co-authored-by: openhands <openhands@all-hands.dev>`.

---

## 5. Pull request

| Property | Value |
|---|---|
| **PR** | https://github.com/TM-AEM/OpenHandBot/pull/7 |
| Number | 7 |
| Title | `fix(def011): F-02 abandoned-worker guard with behavioural regression coverage` |
| Base | `main` |
| Head | `review/ohb2-wp07-def011-f02-six-file-ci` |
| Head SHA | `31dec52289142d0d0dc2bd16604d88644ba3baba` |
| State | **OPEN** |
| Merged | **NO** (`mergedAt: null`) |
| Changed files | **6** |
| Additions / deletions | 2445 / 224 |

The PR body documents F-02 scope, why all six files are required, why the two-file candidate was
rejected, the local 3.11/3.13 evidence, the outstanding D6 limitation, and that independent review is
pending.

**The PR was not merged, and merging is out of scope for this task.**

---

## 6. Actual GitHub Actions CI — authoritative evidence

| Property | Value |
|---|---|
| **Run ID** | `44767282994` |
| **Run URL** | https://github.com/TM-AEM/OpenHandBot/actions/runs/44767282994 |
| Workflow | `CI` (existing, **unmodified**) |
| Event | `pull_request` |
| **Run `headSha`** | `31dec52289142d0d0dc2bd16604d88644ba3baba` — **equals the publication commit** |
| Conclusion | **success** |

### 6.1 Job results

| Job | ID | Python | Conclusion | Test count |
|---|---|---|---|---|
| `Tests & lint (3.11)` | `136395179840` | 3.11.18 | **success** | **3330 passed, 0 failed** (92.15 s) |
| `Tests & lint (3.13)` | `136395179562` | 3.13.18 | **success** | **3330 passed, 0 failed** (97.84 s) |
| `Frontend tests (Node)` | `136395178955` | Node | **success** | **280 pass, 0 fail** |

Steps inside each Python job, all successful: checkout → setup-python → install dependencies →
`pyflakes` (clean) → `pip-audit` (*No known vulnerabilities found*) → `bandit -lll -s B613`
(**High: 0**; 5 Low / 19 Medium, unchanged from baseline) → `pytest`.

### 6.2 Proof the run tested the candidate, not `52e7789`

| Evidence | Value |
|---|---|
| Run `headSha` | `31dec52…` ≠ `52e7789…` |
| `tests/test_def011_fs_offload.py` at that ref | exists, **64237 bytes** (identical to local) |
| Tests in that file | **45**, including `test_f02_REV01_abandoned_worker_must_not_write_and_must_not_overlap` |
| CI test count | **3330** — matches the local six-file-set count exactly |
| `store_async` at parent `52e7789` | **0** — so 3330 could not come from the base |

### 6.3 Python versions actually exercised

`3.11.18` and `3.13.18` (the matrix covers 3.11 and 3.13 as required). Both passed.

### 6.4 Local evidence, kept distinct from CI

Before publication the six-file candidate was validated locally on a clean `HEAD` base:

| Check | Local 3.11.18 | Local 3.13.15 |
|---|---|---|
| pyflakes | clean | clean |
| `pytest -q` | **3330 passed, 0 failed** | **3330 passed, 0 failed** |

These are **local runs, not CI**. The CI evidence in §6 is independent of and additional to them, and
the two agree (3330 on both versions).

---

## 7. Independent-review handoff

**Location:** `docs/reviews/OHB2-WP07-DEF011-F02-INDEPENDENT-REVIEW-HANDOFF.md` (updated for publication)

Now contains:

- publication commit SHA `31dec52289142d0d0dc2bd16604d88644ba3baba`;
- PR URL and CI run URL/ID;
- the six exact blob hashes at the published commit;
- CI results for 3.11 and 3.13;
- the original patch SHA-256 as provenance;
- the full **20-item review checklist**;
- the explicit **D6** limitation;
- instructions to check out and reproduce against the **published commit**, not a snapshot.

**Independent review status: `NOT PERFORMED`.** This environment cannot supply a genuinely separate
host, so no review is claimed. Same-host directories, worktrees, processes or sessions do not satisfy
independence.

---

## 8. D6 status

**DEFERRED AND OPEN.** Repeated raw `Task.cancel()` during the drain remains unsafe: a second raw
cancel interrupts the drain, `_accept_lock` is released under an active writer, and
`max_concurrent_writers` reaches 2. `anyio.CancelScope(shield=True)` does not prevent this. F-02
addresses **single** cancellation only. Nothing in this publication changes D6's status, and D6 must
not be described as safe.

---

## 9. Remaining blockers

| Blocker | Owner action needed |
|---|---|
| **Independent review not performed** | A reviewer on a genuinely separate host must review commit `31dec52` and reproduce the suite. |
| **D6 unresolved** | Separate defect; needs its own owner decision and design. |
| **PR unmerged** | Deliberately left open. Merging requires owner authorization and is out of scope. |
| **Owner acceptance** | Not granted. |

No technical or permission blocker prevented publication — GitHub auth as `TM-AEM` with push rights was
sufficient and no broader permission was sought.

---

## 10. Actions taken and not taken

**Taken:** created branch → staged exactly 6 paths → committed → pushed → opened 1 PR → read CI results.

**Not taken:** push to `main`; merge; deploy; release; Autopush; workflow or CI configuration change;
repository visibility/collaborator/permission/webhook/secret/Actions-settings change; `git add .`;
`git add -A`; reset; clean; force-push; any seventh file.

### 10.1 Working-tree preservation

After the push, returning to the authoring branch reverted the six files in the working tree. They were
**restored from commit `31dec52`** (the same content), returning the workspace to its exact
pre-publication state: `staged=0 modified=8 untracked=71 ignored=8`, with all six candidate hashes
intact. No user work was discarded; the untracked `docs/` reports and `.openhands/` were never touched.

---

## 11. Honest limitations

1. **Independent review has not happened.** Publication and CI do not substitute for it.
2. **D6 is still open** and unsafe under repeated raw cancellation.
3. **PR #7 is unmerged** by design.
4. The local and CI counts (3330) exclude 8 untracked test files from other work packages that are not
   part of this publication set; the authoring worktree therefore reports 3443.
5. This report describes one commit (`31dec52`) and one CI run (`44767282994`); it makes no claim about
   any later revision.
