# OHB2 — WP-09 Compatibility and Environment Verification (Fresh Run)

**Task ID:** `OHB2-WP09-COMPATIBILITY-AND-ENVIRONMENT-VERIFICATION`
**Date:** 2026-11-23
**Mode:** read-only verification; no application, test, dependency, lockfile, Docker, CI, or Mini App changes.
**Overall verdict:** **`FAILED — CONFIRMED COMPATIBILITY DEFECT`**

> The confirmed defect is the frontend reproducible-install path: `npm ci` fails against the current
> committed `package-lock.json`. Python 3.11/3.13 and the frontend unit tests pass; the frontend build
> succeeds only after a non-reproducible `npm install`. This report does not claim independent review,
> owner acceptance, or WP-09 closure.

---

## 1. Exact baseline and worktree state

### 1.1 Repository identity

| Item | Value |
|---|---|
| Repository | `/workspace/project/OpenHandBot` |
| Branch | `main` |
| `HEAD` | `2d528633a86472a6a502d7dca5b69ae9f10359ab` |
| `HEAD` tree | `90b62951e53156ac55cffca2f471a0690f21b3d0` |
| `HEAD` subject | `docs: record NEW-03 acceptance audit in progress` |
| Local `origin/main` | `2d528633a86472a6a502d7dca5b69ae9f10359ab` |
| Remote fetch/pull | **not performed** |
| Staged changes | none |
| Worktree | dirty; pre-existing uncommitted work preserved |

The current `HEAD` and tree match the recorded baseline. The current worktree contains uncommitted
WP-03/A4-F5 work that predates this task; it was not modified.

### 1.2 Pre-existing changes preserved

Tracked modifications present at baseline:

- `.agent/PROGRESS.md`
- `bot/attachments.py`
- `bot/db.py`
- `bot/handlers.py`
- `tests/test_attachment_batch_lifecycle_a2.py`
- `tests/test_attachment_staging_a1.py`
- `tests/test_def011_a_option_b_limits.py`
- `tests/test_def011_fs_offload.py`
- `tests/test_f01_reaper_fs_offload.py`
- `tests/test_miniapp_attachment_download_mt2.py`
- `tests/test_repair_plan_01_resource_staging.py`
- `tests/test_repair_plan_02_life01_f2_race.py`
- `tests/test_repair_plan_02_life02_crash_recovery.py`
- `tests/test_wp03_handler_outcome_and_send_guards.py`

Untracked files present at baseline:

- `docs/reviews/OHB2-WP03-AUD01-DISPLAY-FAILURE-REPAIR-REPORT.md`
- `docs/reviews/OHB2-WP03-REFRESHED-READINESS-AUDIT-REPORT.md`
- `docs/reviews/OHB2-WP03-REVIEW-READINESS-AND-EVIDENCE-AUDIT-REPORT.md`
- `tests/test_a4_f5_expiration_boundary.py`

Ignored state (`.openhands/`, `.pytest_cache/`, `__pycache__/`, etc.) was preserved.

### 1.3 Report-path collision

The requested report path:

`docs/reviews/OHB2-WP09-COMPATIBILITY-AND-ENVIRONMENT-VERIFICATION-REPORT.md`

already exists as a **tracked historical report**:

- SHA-256: `498475d8876854eb64039bf92224a9dee8353b46d95cebfb50edf2d39dd062c7`
- Historical `HEAD`: `0774c9cff923a2ed02da36a1111a283a61600ea5`
- Historical verdict: `COMPLETE_WITH_NOTES`

It was **not overwritten or modified**. This fresh report is therefore at the suffixed path in §12.

---

## 2. Project metadata inspected

| Item | Finding |
|---|---|
| Python metadata | No `pyproject.toml`, `setup.cfg`, or `tox.ini`; `requirements.txt` and `requirements-dev.txt` are authoritative |
| Python minimum | `bot/bootstrap.py` sets `MIN_PYTHON = (3, 11)`; `start.sh` enforces `>= 3.11` |
| Python CI matrix | `.github/workflows/ci.yml`: `["3.11", "3.13"]` |
| Node metadata | `package.json` has **no** `engines` or `packageManager` field |
| Node CI target | `.github/workflows/ci.yml`: `node-version: "24"` |
| Node documentation | `docs/MINI_APP.md` says Node 24; old master-plan/audit text still says Node 22 |
| Lockfiles | Both `package-lock.json` (lockfileVersion 3) and `bun.lock` (Bun lockfile v2) exist |
| Package manager | `npm 12.2.2`; `bun` is not installed |
| Docker assets | No Dockerfile, Compose file, or Docker build configuration exists |
| CI workflow | Python matrix, install, pyflakes, pip-audit, Bandit, pytest; frontend job runs only `node --test` |

---

## 3. Python 3.11 verification

### 3.1 Availability and environment

- Native `python3.11`: **not installed**.
- `uv 0.13.7` was available. It installed official CPython **3.11.18** into its user cache, outside the
  repository.
- Fresh isolated venv: `/tmp/ohb2-wp09-py311`
- Interpreter: `Python 3.11.18`
- `pip`: `26.3`
- Dependency install from `requirements-dev.txt`: **exit 0**; no tracked files changed.

This is a genuine Python 3.11 execution, not a historical CI claim. It is **uv-managed**, not the
system-native interpreter.

### 3.2 Results

| Check | Result | Exit |
|---|---|---|
| `pytest -q` full suite | **3823 passed, 0 failed, 74 warnings** | 0 |
| `pyflakes bot/ automation/ tools/ main.py tests/` | no diagnostics | 0 |
| `bandit -r ... -lll -s B613` | **High 0**; Low 5 / Medium 19 | 0 |
| `pip-audit -r requirements-dev.txt` | **No known vulnerabilities found** | 0 |
| `compileall -q ...` | no errors | 0 |

No Python 3.11 incompatibility was found. The full suite is the current worktree suite, including the
pre-existing A4-F5 changes and WP-03 repair tests.

---

## 4. Python 3.13 verification

### 4.1 Availability and environment

- Fresh isolated venv: `/tmp/ohb2-wp09-py313`
- Interpreter: `Python 3.13.15`
- `pip`: `26.3`
- Dependency install from `requirements-dev.txt`: **exit 0**; no tracked files changed.

### 4.2 Results

| Check | Result | Exit |
|---|---|---|
| `pytest -q` full suite | **3823 passed, 0 failed, 74 warnings** | 0 |
| `pyflakes bot/ automation/ tools/ main.py tests/` | no diagnostics | 0 |
| `bandit -r ... -lll -s B613` | **High 0**; Low 5 / Medium 19 | 0 |
| `pip-audit -r requirements-dev.txt` | **No known vulnerabilities found** | 0 |
| `compileall -q ...` | no errors | 0 |

No Python 3.13 incompatibility was found.

---

## 5. Node and frontend verification

### 5.1 Environment

- Node.js: `v24.22.2`
- npm: `12.2.2`
- Bun: **not installed**
- `package.json`: no `engines`, no `packageManager`
- `package-lock.json`: lockfileVersion 3
- `bun.lock`: present; Bun lockfile v2 (not strict JSON)

### 5.2 Node unit tests

```sh
node --test tests/frontend/*.test.js
```

Result: **280 tests, 280 passed, 0 failed, 0 skipped**, exit `0`.

This verifies the existing JavaScript unit invariants only. It does not verify npm installation or a
production build.

### 5.3 `npm ci` against the committed lockfile

Run in an isolated `git archive HEAD` copy at `/tmp/ohb2-wp09-frontend`:

```sh
npm ci
```

Result: **exit 1**, `EUSAGE`:

```text
`npm ci` can only install packages when your package.json and package-lock.json are in sync.
Missing: @tailwindcss/oxide-* ...
Missing: lightningcss-* ...
Missing: @rolldown/binding-* ...
Missing: @typescript/typescript-* ...
```

The lockfile is missing optional platform packages required by the current dependency graph. This is a
reproducible lockfile/dependency-install defect, not a Node runtime failure.

### 5.4 `npm install` and build

In the same isolated copy, after `npm ci` failed:

```sh
npm install
npm run build
npm run lint
```

Results:

- `npm install`: **exit 0**, 178 packages added; `found 0 vulnerabilities`; npm reported 3 blocked
  install scripts (`@google/genai`, `esbuild`, `protobufjs`).
- `npm run build`: **exit 0**, Vite 8.3.8, 16 modules transformed, `dist/index.html` + CSS + JS,
  built in 264 ms.
- `npm run lint` (`tsc --noEmit`): **exit 0**.

The build is viable, but it depends on a non-reproducible `npm install` that mutates the temp copy's
lockfile. The repository lockfile was not modified.

---

## 6. Docker verification

| Check | Result |
|---|---|
| Docker client | **installed**, `29.10.0` build `fdd4b8e` |
| Docker Compose | **installed**, `v5.8.0` |
| Docker daemon | **not available**; `/var/run/docker.sock` absent; `docker info` exit 1 |
| Dockerfile / Compose assets | **none found** |
| `docker compose config` | exit 1: `no configuration file provided: not found` |
| Project Docker requirement | **NOT APPLICABLE** — no Docker workflow/assets documented as a repository build requirement |

Docker is not part of the documented project build workflow. No Docker daemon was started, no image was
pulled, and no container was run.

---

## 7. CI workflow coverage and evidence

### 7.1 Workflow structure

`.github/workflows/ci.yml` (current `HEAD`) parses successfully as YAML.

`test` job:

- Matrix: Python `3.11`, `3.13`
- `pip install -r requirements-dev.txt`
- `pyflakes bot/ automation/ tools/ main.py tests/`
- `pip_audit -r requirements-dev.txt`
- `bandit -r bot/ automation/ tools/ main.py -lll -s B613`
- `pytest -q`

`frontend` job:

- Node `24`
- `node --test tests/frontend/*.test.js`

**Coverage gap:** the frontend job does **not** run `npm ci`, `npm install`, `npm run build`, or
`npm run lint`. It verifies only the existing Node unit tests.

No Docker job exists.

### 7.2 Current CI evidence

- `gh` is installed (`2.105.0`) but **not authenticated**: `gh auth status` reports no logged-in host.
- No CI run was queried and no fetch/pull was performed.
- Historical run #99 and its success are **NOT VERIFIED** by this audit. The workflow structure is
  verified; the actual current run is not.

---

## 8. `npm ci` lockfile drift analysis

**Confirmed:** the current committed `package-lock.json` cannot satisfy `npm ci` for the current
`package.json` dependency graph.

Evidence:

- `npm ci` exit `1`, `EUSAGE`.
- Missing optional platform packages include `@tailwindcss/oxide-*`, `lightningcss-*`,
  `@rolldown/binding-*`, and `@typescript/typescript-*`.
- `npm install` succeeds and adds 178 packages in a temp copy, but that is not reproducible from the
  committed lockfile.
- `npm run build` succeeds only after that temp `npm install`.
- No repository lockfile was regenerated, edited, or staged.

This is a confirmed frontend reproducibility defect. It is not a Node 24 runtime failure: the existing
Node tests and the built output work after installation.

---

## 9. Historical WP-09 reconciliation

| Record | Historical statement | Current evidence | Reconciliation |
|---|---|---|---|
| `docs/reviews/OHB2-WP09-COMPATIBILITY-AND-ENVIRONMENT-VERIFICATION-REPORT.md` | `COMPLETE_WITH_NOTES`; Python 3.11/3.13 pass; Node 24 tests pass; `npm ci` fails; CI not run; Docker not applicable | Fresh Python 3.11/3.13 full suites pass; Node 24 tests pass; `npm ci` still fails; CI still not verified; no Docker assets | Historical report preserved. Its `COMPLETE_WITH_NOTES` was a five-command local-gate verdict at old `HEAD 0774c9c`; it does **not** establish current reproducible frontend installation or current CI. |
| Master plan | Node 22 in WP-09 text | Current CI and Mini App docs use Node 24; Node 22 text is stale | Documentation inconsistency remains; Node 24 is the current CI target. |
| `OHB2-MASTER-BACKLOG-RECONCILIATION...` | WP-09 `COMPLETE_WITH_NOTES`; `npm ci` failure noted; CI not run | Fresh evidence confirms the same `npm ci` failure and CI gap | Backlog status remains implementation/verification-only; it is not a current PASS. |
| Current CI #99 claim | Successful run on current commit | No authenticated CI access; no run evidence inspected | **NOT VERIFIED**, not confirmed and not converted into a failure. |

### Gate distinction

- **Implementation/configuration inspected:** yes.
- **Local Python/Node tests:** pass.
- **Frontend reproducible installation:** **FAILED — CONFIRMED COMPATIBILITY DEFECT**.
- **Frontend build after non-reproducible install:** pass with note.
- **Current GitHub CI execution:** **NOT VERIFIED**.
- **Docker build:** **NOT APPLICABLE** (no assets).
- **Independent review / owner acceptance / WP-09 closure:** not performed and not claimed.

---

## 10. Findings register

| ID | Severity | File / symbol | Evidence | Impact | Required action | Owner approval |
|---|---|---|---|---|---|---|
| `WP09-F01` | **MEDIUM** | `package-lock.json` / `package.json` | `npm ci` exit 1, `EUSAGE`; missing optional platform packages | Frontend install is not reproducible from the committed lockfile; release/CI install cannot use `npm ci` | Regenerate/align `package-lock.json` with the canonical Node 24/npm version, then verify `npm ci` and build; do not hand-edit | No for lockfile repair, but package-manager policy may need owner decision |
| `WP09-F02` | **MEDIUM** | `.github/workflows/ci.yml` frontend job | Job runs only `node --test`; no `npm ci`, `npm install`, build, or lint | CI does not detect the lockfile defect or prove the frontend build | Add reproducible install/build/lint steps if frontend build is a release gate; otherwise document the gate decision | Yes, CI/coverage decision |
| `WP09-F03` | **LOW** | `docs/audits/OHB2-REMEDIATION-MASTER-PLAN.md` etc. | Node 22 text vs current Node 24 CI/docs | Documentation inconsistency; reviewers may test the wrong Node version | Update stale Node 22 references or mark them historical | No for docs; owner approval if changing approved docs |
| `WP09-F04` | **MEDIUM** | `package.json`, `package-lock.json`, `bun.lock` | Two lockfiles; no `packageManager`; `bun` unavailable | Ambiguous canonical install path and reproducibility | Choose one canonical package manager/lockfile and declare it | Yes, package-manager decision |

No security or data-loss finding was confirmed.

---

## 11. Exact commands, versions, counts, and warnings

### 11.1 Versions

| Tool | Version |
|---|---|
| Python 3.11 | `3.11.18` (`/tmp/ohb2-wp09-py311`) |
| Python 3.13 | `3.13.15` (`/tmp/ohb2-wp09-py313`) |
| pip | `26.3` in both venvs |
| uv | `0.13.7` |
| Node.js | `v24.22.2` |
| npm | `12.2.2` |
| Docker | `29.10.0` build `fdd4b8e` |
| Docker Compose | `v5.8.0` |
| pytest | `9.0.3` |
| python-telegram-bot | `22.8` |

### 11.2 Commands

```sh
# Python 3.11
/tmp/ohb2-wp09-py311/bin/python -m pytest -q -p no:cacheprovider
/tmp/ohb2-wp09-py311/bin/python -m pyflakes bot/ automation/ tools/ main.py tests/
/tmp/ohb2-wp09-py311/bin/python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613
/tmp/ohb2-wp09-py311/bin/python -m pip_audit -r requirements-dev.txt
/tmp/ohb2-wp09-py311/bin/python -m compileall -q bot automation tools main.py tests

# Python 3.13
/tmp/ohb2-wp09-py313/bin/python -m pytest -q -p no:cacheprovider
/tmp/ohb2-wp09-py313/bin/python -m pyflakes bot/ automation/ tools/ main.py tests/
/tmp/ohb2-wp09-py313/bin/python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613
/tmp/ohb2-wp09-py313/bin/python -m pip_audit -r requirements-dev.txt
/tmp/ohb2-wp09-py313/bin/python -m compileall -q bot automation tools main.py tests

# Frontend
node --test tests/frontend/*.test.js

# Isolated frontend copy from committed HEAD
git archive HEAD | tar -x -C /tmp/ohb2-wp09-frontend
cd /tmp/ohb2-wp09-frontend
npm ci
npm install
npm run build
npm run lint

# Docker / CI
docker --version
docker compose version
docker info
docker compose config
gh auth status
git diff --check
```

### 11.3 Results

| Command / check | Result | Exit |
|---|---|---|
| Python 3.11 full pytest | **3823 passed, 0 failed, 74 warnings** | 0 |
| Python 3.11 pyflakes | clean | 0 |
| Python 3.11 Bandit | High 0; Low 5 / Medium 19 | 0 |
| Python 3.11 pip-audit | No known vulnerabilities found | 0 |
| Python 3.11 compileall | clean | 0 |
| Python 3.13 full pytest | **3823 passed, 0 failed, 74 warnings** | 0 |
| Python 3.13 pyflakes | clean | 0 |
| Python 3.13 Bandit | High 0; Low 5 / Medium 19 | 0 |
| Python 3.13 pip-audit | No known vulnerabilities found | 0 |
| Python 3.13 compileall | clean | 0 |
| Node unit tests | **280 passed, 0 failed** | 0 |
| `npm ci` | **FAILED — EUSAGE lockfile drift** | 1 |
| `npm install` (temp) | 178 packages; 0 vulnerabilities | 0 |
| `npm run build` (temp) | Vite 8.3.8; dist built in 264 ms | 0 |
| `npm run lint` (temp) | `tsc --noEmit` clean | 0 |
| `docker info` | daemon/socket unavailable | 1 |
| `docker compose config` | no configuration file | 1 |
| `gh auth status` | not authenticated | 1 |
| `git diff --check` | clean | 0 |

Warnings: 74 pytest warnings are the existing PTB/Starlette deprecation warnings; no warning was
promoted to a failure. npm reported blocked install scripts in the temp copy; this is an npm policy
warning, not a build failure.

---

## 12. Changed files — this report only

Created:

- `docs/reviews/OHB2-WP09-COMPATIBILITY-AND-ENVIRONMENT-VERIFICATION-REPORT-20261123.md`

No existing report was modified. The requested exact path was already occupied by the tracked
historical report described in §1.3 and was preserved.

No application source, tests, dependencies, lockfiles, Docker configuration, CI workflows, Mini App
files, or `.openhands/` state were modified. Temporary venvs, archives, and frontend installs were
kept outside the repository.

---

## 13. Final repository state

| Item | Value |
|---|---|
| Branch | `main` |
| `HEAD` | `2d528633a86472a6a502d7dca5b69ae9f10359ab` |
| Tree | `90b62951e53156ac55cffca2f471a0690f21b3d0` |
| Local `origin/main` | `2d528633a86472a6a502d7dca5b69ae9f10359ab` |
| Staged | none |
| Worktree | unchanged pre-existing modifications plus this report only |
| `package.json` / lockfiles | unchanged (no diff) |
| Git publication | none |
| Destructive Git operation | none |

---

## 14. Final verdict and required follow-up

**`FAILED — CONFIRMED COMPATIBILITY DEFECT`**

The supported Python runtimes (3.11.18 and 3.13.15) pass the full suite and static/security checks.
Node 24 passes the existing frontend tests. The frontend build succeeds after a temp `npm install`.

However, the committed frontend dependency state is **not reproducibly installable**:

1. `npm ci` fails with `EUSAGE` because `package.json` and `package-lock.json` are out of sync.
2. CI does not run `npm ci`, `npm install`, build, or lint, so it cannot detect this defect.
3. Two lockfiles exist (`package-lock.json`, `bun.lock`) with no canonical `packageManager`.

WP-09 therefore needs a narrowly scoped follow-up:

- Align/regenerate `package-lock.json` with the canonical Node 24/npm version and verify `npm ci`.
- Decide the canonical frontend package manager/lockfile.
- Add frontend install/build/lint to CI if they are release-gate requirements.
- Re-run current CI and record the actual run/commit evidence.

Docker is **NOT APPLICABLE** for the current repository because there are no Docker assets or
documented Docker build workflow. The Docker daemon is unavailable; no Docker verification was
attempted beyond client/version/config checks. Current GitHub CI execution remains **NOT VERIFIED**.

This report does not claim independent review, owner acceptance, or WP-09 closure.

---

## 15. Report integrity

**Report body SHA-256 (excluding this footer):** `a7c08e3ce994891e5d6d9cb305b2d435d11657ac67359930cc737f4637c3f9e2`
