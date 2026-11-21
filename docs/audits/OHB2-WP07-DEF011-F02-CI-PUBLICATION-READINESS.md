# OHB2 — WP-07 / DEF-011 / F-02 — CI Publication Readiness

**Task:** `OHB2-WP07-DEF011-F02-CI-PUBLICATION-READINESS-AND-INDEPENDENT-REVIEW-HANDOFF`
**Date:** 2026-11-18
**Status:** `F02_PUBLICATION_HANDOFF_READY` — **with a material correction to the assumed publication set**
**F-02 remains OPEN.** No CI run, no independent review, no commit/push/PR occurred.

---

## 0. Headline finding — the "two-file patch" premise is not viable

The task premise is that F-02 can be published as a **two-file** patch
(`bot/attachments.py` + `tests/test_def011_fs_offload.py`). **This was tested and is false.**

| Attempt | Set published on a clean `HEAD` base | Result |
|---|---|---|
| A | 2 files (as assumed) | **1 failed**, 3329 passed — `test_T8b_local_capped_read_runs_off_event_loop_thread` |
| B | 3 files (+ `bot/handlers.py`) | **94 failed** |
| C | 4 files (+ `tests/test_handlers.py`) | **92 failed** |
| D | 5 files (+ `bot/db.py`) | **9 failed** |
| E | 6 files (+ `tests/test_sw06_unwatch_db_failure_propagation.py`) | **3330 passed, 0 failed** ✅ |

**Root cause:** F-02 is not an isolated change. The DEF-011 regression suite asserts that
`_read_local_capped` runs **off** the event-loop thread, which is implemented by an
**uncommitted** `anyio.to_thread.run_sync` change in `bot/handlers.py`. That change in turn depends on
new `bot/db.py` helpers. None of this exists at `HEAD 52e7789`.

**Consequence:** the minimal self-consistent publication set is **6 files**, not 2. Publishing only
two files would push a **red CI** run. This is recorded as the corrected publication unit; the
two-file set is documented as rejected with evidence.

---

## 1. Fresh Git baseline

| Property | Value |
|---|---|
| Repository root | `/workspace/project/OpenHandBot` |
| Branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` |
| HEAD | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| `origin/main` | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| Divergence | `0 0` |
| Staged | 0 |
| Modified | 8 |
| Untracked | 68 |
| Ignored | 8 |

Remotes: `origin` → `https://github.com/TM-AEM/OpenHandBot.git` (fetch + push).

### 1.1 The 8 pre-existing modified files

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

`.agent/PROGRESS.md` is agent working notes and is **excluded** from publication.

### 1.2 Candidate hash verification

| File | Recomputed SHA-256 | Expected | Match |
|---|---|---|---|
| `bot/attachments.py` | `b98d561f0ba0ab27dea4e6bedee7955f68f1f6fa85a39fa81afe8aeb4d818356` | `b98d561f…` | **yes** |
| `tests/test_def011_fs_offload.py` | `3d3b3a2ac399fec0420e2d769f98c7c2841c69c05f341734aecef68df4f503ea` | `3d3b3a2a…` | **yes** |

Both match the recorded candidate exactly — **no discrepancy**, so the earlier local evidence
remains valid for these two files.

### 1.3 What `HEAD` actually contains

| Check | Value |
|---|---|
| `git show HEAD:bot/attachments.py` → `store_async` | **0 occurrences** |
| `git show HEAD:bot/attachments.py` → `_accept_lock` | **0 occurrences** |
| `git show HEAD:bot/handlers.py` → `to_thread` | **0 occurrences** |
| `tests/test_def011_fs_offload.py` at HEAD | **UNTRACKED** |

The entire F-02 / DEF-011 offload work is uncommitted.

---

## 2. Publication patch

### 2.1 Set (6 files — the minimum that passes CI)

| File | Change | SHA-256 | Required because |
|---|---|---|---|
| `bot/attachments.py` | +444 / −104 | `b98d561f…` | **The F-02 implementation** (gate, `started`/`abandoned`, drain, worker) |
| `bot/handlers.py` | +144 / −41 | `40dd8902…` | Off-loop `to_thread` read — asserted by T-8b |
| `bot/db.py` | +269 / −66 | `205f1363…` | Atomic watch/unwatch helpers the handlers use |
| `tests/test_def011_fs_offload.py` | **new**, 1575 lines | `3d3b3a2a…` | DEF-011 matrix (45 tests) incl. **REV-01** |
| `tests/test_handlers.py` | +2 / −2 | `2b1f9780…` | Updated expectations for the new outcome API |
| `tests/test_sw06_unwatch_db_failure_propagation.py` | +11 / −11 | `ba263311…` | Updated for the new cancellation/outcome semantics |

Combined diffstat: **6 files changed, 2445 insertions(+), 224 deletions(-)**.

**Excluded deliberately:** `.agent/PROGRESS.md` (agent notes), `bot/app.py` and `bot/watcher.py`
(**not** required — the 6-file set passes with both at `HEAD`), all other untracked files (8 other
work-package test files, `docs/`), `.openhands/`, `.agent/`.

### 2.2 Patch artifact

| Property | Value |
|---|---|
| Path | `/tmp/f02handoff/f02-publication.patch` |
| SHA-256 | `59b701369a3b6d2bf70f8028d3ffc8d22831b2f3eedba8cc4de16997246ebe94` |
| Base commit | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| Files in patch | 6 (list verified by `grep '^+++ b/'`) |
| `git apply --check` on pristine HEAD | **OK** |
| Applied → reproduces candidate hashes | **yes** (`b98d561f…`, `3d3b3a2a…`) |

The patch is stored **outside** the repository so it cannot be accidentally staged or committed.

### 2.3 Reproducible commands

```bash
# 1. Verify base
git -C /workspace/project/OpenHandBot rev-parse HEAD   # -> 52e7789cc8cc97a7f7c09c9592226ab117db99a2

# 2. Apply to a pristine tree
mkdir /tmp/verify && cd /tmp/verify
git -C /workspace/project/OpenHandBot archive HEAD | tar x
git apply --check /tmp/f02handoff/f02-publication.patch
git apply         /tmp/f02handoff/f02-publication.patch

# 3. Verify candidate hashes
sha256sum bot/attachments.py tests/test_def011_fs_offload.py
#   b98d561f0ba0ab27dea4e6bedee7955f68f1f6fa85a39fa81afe8aeb4d818356  bot/attachments.py
#   3d3b3a2ac399fec0420e2d769f98c7c2841c69c05f341734aecef68df4f503ea  tests/test_def011_fs_offload.py

# 4. Verify the patch itself
sha256sum /tmp/f02handoff/f02-publication.patch
#   59b701369a3b6d2bf70f8028d3ffc8d22831b2f3eedba8cc4de16997246ebe94
```

### 2.4 Secret and scope scan

| Check | Result |
|---|---|
| Hardcoded credentials / private keys / tokens | **none** (only a fake test fixture CID `111111112222…` and `import secrets`) |
| `.openhands/` content | **0** |
| `.agent/` content | **0** |
| `.env` | **0** |
| `docs/audits/`, `docs/reviews/` files included | **0** (one docstring *reference* inside the test file, not a file addition) |
| Mini App changed lines | **0** (`mini_app` appears only in unchanged context lines) |
| Schema DDL added/changed | **0** (the only `CREATE TABLE` is inside a test assertion that counts tables) |
| New dependency | **none** (`requirements*.txt`, `pyproject.toml`, `package.json` untouched) |

---

## 3. Local verification evidence — LOCAL, not CI

Both interpreters, on the exact 6-file set applied to a pristine `HEAD` base:

| Check | Python 3.11.18 | Python 3.13.15 |
|---|---|---|
| `pyflakes bot/ automation/ tools/ main.py tests/` | **clean (exit 0)** | **clean (exit 0)** |
| `pytest -q` | **3330 passed, 0 failed** (198.75 s) | **3330 passed, 0 failed** (180.51 s) |
| REV-01 on correct impl | pass | **pass** |
| REV-01 on M4′ mutant | — | **fail** (`assert 1 == 0`) |
| M4′ scope check (`with _gate:` blocks) | — | **2** (gate intact) |

### 3.1 Why 3330 and not 3443

The working tree reports **3443** because it contains **8 other untracked test files** belonging to
separate work packages (`test_f01_reaper_fs_offload.py`, `test_wp07_*`, `test_f03_*`, …). Those are
**not** part of the F-02 publication set and are correctly excluded. The 6-file set yields **3330** on
both versions — consistent, and 113 fewer because those unrelated test files are absent.

**This is local evidence only. It is not CI evidence.**

---

## 4. CI route and blockers

### 4.1 Workflow facts (`.github/workflows/ci.yml`)

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
```

Matrix: `python-version: ["3.11", "3.13"]` on `ubuntu-latest`.
Steps: pyflakes → pip-audit → bandit `-lll -s B613` → `pytest -q`; plus a separate
`frontend` job running `node --test tests/frontend/*.test.js`.

### 4.2 Route assessment

| Route | Available without forbidden action? |
|---|---|
| `workflow_dispatch` | **No** — not present; adding it = editing a workflow file |
| `push` to `main` | **No** — requires commit + push |
| `pull_request` | **No** — requires branch + commit + PR |
| `act` local runner | **No** — absent, and needs Docker (absent) |
| Reuse run `44371404130` | **No** — see §4.3 |

### 4.3 The existing green run is NOT F-02 evidence

Run `44371404130` has `headSha = 52e7789` — the current `HEAD`, which contains **zero** occurrences
of `store_async`. It tested code **without F-02**. Citing it as F-02 CI evidence would be false.

### 4.4 Required owner authorization

**Exactly this action requires explicit owner authorization:**

> Commit the 6-file set to a branch (or to `main`) and push it so that the existing `CI` workflow runs
> on Python 3.11 and 3.13. A pull request would additionally require branch creation and PR opening.

Nothing less will produce CI evidence. No commit, push, branch, PR, workflow edit, or settings change
was performed by this task.

---

## 5. Outstanding owner authorization (summary)

| Action | Needed for | Performed? |
|---|---|---|
| Commit the 6 files | Publication | **No** |
| Create branch / push | Triggering `CI` | **No** |
| Open PR (optional) | Reviewable CI + review trail | **No** |
| Provision an isolated reviewer host | Genuine independent review | **No** |

---

## 6. Limitations

1. **CI not run** — the candidate is uncommitted; Actions checks out commits.
2. **Independent review not performed** — no isolated environment exists here.
3. **Python 3.11/3.13 verified locally only** — not on a GitHub runner.
4. **Publication set is 6 files, not 2** — the two-file premise fails CI (evidence in §0).
5. **D6 remains deferred and open** — repeated raw cancellation is unsafe; see the handoff doc.
6. **F-02 remains OPEN.**

---

## 7. Verification artifacts

| Path | Contents |
|---|---|
| `/tmp/f02handoff/f02-publication.patch` | The 6-file patch (`59b70136…`) |
| `/tmp/final8/` | 6-file set, 3.13 venv — 3330 passed |
| `/tmp/v311/` | 6-file set, 3.11 venv — 3330 passed |
| `/tmp/mut8/` | M4′ mutant — REV-01 fails |
| `/tmp/applytest/` | Pristine HEAD + patch → hash reproduction |
| `/tmp/pubtest/`, `/tmp/mintest/`, `/tmp/minimal/`, `/tmp/set5/`, `/tmp/set5c/`, `/tmp/why6/` | The rejected smaller sets (evidence for §0) |

All artifacts live **outside** the repository. Nothing was staged or committed.
