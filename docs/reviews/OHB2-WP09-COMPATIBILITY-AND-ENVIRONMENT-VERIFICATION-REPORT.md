# OHB2 — WP-09 Compatibility and Environment Verification Report

**Task ID:** `OHB2-WP09-COMPATIBILITY-AND-ENVIRONMENT-VERIFICATION`
**Date:** 2026-11-22
**Mode:** audit and verification only; no application, test, dependency, lockfile, CI, Docker, or runtime-configuration changes.
**Repository:** `/workspace/project/OpenHandBot`
**Overall verdict:** **`COMPLETE_WITH_NOTES`** for the WP-09 local release gate (Categories 1–6). See §14 for the exact boundary and the separate frontend packaging failure.

---

## 1. Executive summary

- **Python 3.11 was actually tested.** The native host has no Python 3.11 interpreter, so a disposable official `python:3.11-slim` container (`Python 3.11.18`, image digest `sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535`) was used against a clean `HEAD` archive.
- **Python 3.11 full suite passed:** **3513 passed, 1 skipped, 0 failed**, 74 warnings, **169.99 s**, exit `0`, after installing `git` in the disposable container. The one skip is `tests/test_frontend_ops.py::test_frontend_operation_logic` because Node is absent inside the Python container; Node tests were run separately on the host and passed **280/280**.
- **Python 3.13.15 full suite passed:** **3514 passed, 0 failed**, 74 warnings, **174.28 s**, exit `0`, using the existing isolated `/tmp/rev-ind-01-wp07-venv`.
- **Static/security checks passed on both Python versions:** `pyflakes` exit `0` with no diagnostics; `pip-audit` reported **No known vulnerabilities found**; `bandit` reported **High 0**, Low 5, Medium 19, exit `0`.
- **Node.js v24.22.2 / npm 12.2.2:** `node --test tests/frontend/*.test.js` passed **280/280**, exit `0`, 1.035 s. Node 24 is the current CI target.
- **Frontend reproducible install has a real failure:** `npm ci` exits `1` (`EUSAGE`) because `package.json` and `package-lock.json` are out of sync (missing optional platform packages). A temporary `npm install` succeeded and `npm run build` succeeded (Vite 8.3.8, exit `0`, 235 ms). This is a lockfile/reproducibility gap, not a Node 24 runtime failure.
- **Docker is not a repository/WP-09 build requirement:** there are no Dockerfiles or Compose files. Docker 29.10.0 and Compose v5.8.0 are installed; the daemon was started temporarily only to provide Python 3.11, then stopped. Docker build validation is `NOT APPLICABLE`.
- **CI is configured but was not executed on GitHub:** `.github/workflows/ci.yml` has Python `3.11`/`3.13` plus Node `24`; no push/PR was permitted. Local equivalents were executed.
- **Documentation conflict:** the WP-09 master plan still says Node 22, while the current CI, the corrected remediation baseline, and Mini App documentation say Node 24. Node 24 is treated as the current authoritative target; Node 22 references are stale.
- **No project implementation/configuration files were modified.** Only this report was created. The pre-existing working-tree changes were preserved.

---

## 2. Repository baseline

Recorded before verification:

| Item | Value |
|---|---|
| Repository path | `/workspace/project/OpenHandBot` |
| Remote | `https://github.com/TM-AEM/OpenHandBot.git` (fetch/push) |
| Current branch | `main` |
| HEAD commit | `0774c9cff923a2ed02da36a1111a283a61600ea5` |
| HEAD tree | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| `origin/main` local ref | `0774c9cff923a2ed02da36a1111a283a61600ea5` |
| Tracked modifications | `.agent/PROGRESS.md`, `bot/app.py`, `docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md`, `docs/audits/OHB2-WP07-FINAL-STABILIZATION-AUDIT.md`, `docs/audits/OHB2-WP07-NEW-DEF03-S3-DELIVERY-AND-ACCEPTANCE-RECONCILIATION.md`, `tests/test_u04_concurrency.py` |
| Untracked files | three poller-concurrency reports under `docs/audits/`, plus `docs/reviews/OHB2-WP07-NAV-OWNER-DECISION-PACKAGE.md` and `docs/reviews/REV-IND-01-WP-07-INDEPENDENT-REVIEW-REPORT.md` |
| Ignored files | `.openhands/`, `.pytest_cache/`, `__pycache__/`, `automation/autopush/__pycache__/`, `bot/__pycache__/`, `bot/web/__pycache__/`, `tests/__pycache__/` |
| Test source | Clean `git archive HEAD` copies outside the project working tree; uncommitted concurrency changes excluded |

The uncommitted `bot/app.py` and `tests/test_u04_concurrency.py` changes are pre-existing poller-concurrency work. They were **not** included in the clean-HEAD verification and were **not** modified by this task.

---

## 3. Authoritative WP-09 requirements

### 3.1 Sources inspected

- `docs/audits/OHB2-REMEDIATION-MASTER-PLAN.md` — WP-09 definition and five-command acceptance.
- `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md` — WP-09 Categories 1–7 and Python 3.11/3.13 + Node 24 target.
- `.github/workflows/ci.yml` — actual CI matrix and steps.
- `bot/bootstrap.py` and `start.sh` — runtime Python gate.
- `requirements.txt`, `requirements-dev.txt`, `pytest.ini`.
- `package.json`, `package-lock.json`, `bun.lock`, `docs/MINI_APP.md`.
- `README.md`, `docs/REGRESSION_GATE.md`, deployment documentation.

### 3.2 Required versions

| Runtime/tool | Authoritative requirement | Evidence |
|---|---|---|
| Python | **3.11 or newer**; CI verifies **3.11 and 3.13** | `bot/bootstrap.py:22-23` (`MIN_PYTHON = (3, 11)`); `start.sh:41-46`; `.github/workflows/ci.yml:21-23` |
| Python 3.11 | **Mandatory verification target** | WP-09 master plan and corrected baseline; CI matrix `["3.11", "3.13"]` |
| Node.js | **24** (current CI target) | `.github/workflows/ci.yml:62-67`; `docs/MINI_APP.md:419`; `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md:720,743` |
| npm | **No pinned version** | No `engines` or `packageManager` in `package.json`; `package-lock.json` is lockfile v3 |
| Docker / Compose | **Not required** | No Dockerfile or Compose file exists; WP-09 plan specifies clean venv/CI, not a container build |

**Documentation conflict:** `docs/audits/OHB2-REMEDIATION-MASTER-PLAN.md:223,232` still says Node 22. Current CI and the corrected baseline say Node 24. This report treats **Node 24 as the current authoritative target** and records Node 22 as stale documentation, not as a verified requirement.

### 3.3 WP-09 evidence categories

The corrected baseline defines seven strictly separated categories:

1. Syntax checks.
2. Unit tests.
3. Integration tests.
4. Static analysis (`pyflakes`).
5. SAST (`bandit`).
6. Dependency vulnerability scanning (`pip-audit`).
7. External infrastructure checks (`WP-10`, `OD-05`).

Categories 1–6 are the local release-gate scope. Category 7 is external hosting/infrastructure and remains outside this local audit.

### 3.4 Five-command WP-09 gate

```sh
python -m pytest -q
node --test tests/frontend/*.test.js
python -m pyflakes bot/ automation/ tools/ main.py tests/
python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613
python -m pip_audit -r requirements-dev.txt
```

The master-plan acceptance text says both Python 3.11 and 3.13 plus Node; the current CI and corrected baseline use Node 24.

---

## 4. Environment inventory

| Tool / runtime | Available? | Exact version / path | Notes |
|---|---|---|---|
| Python (default) | Yes | `3.13.15` at `/usr/local/bin/python3` | `python3.13` also present |
| Python 3.11 (native) | **No** | `python3.11` not found | No pyenv/conda-managed 3.11 |
| Python 3.12 | No | not found | Not a WP-09 target |
| pip | Yes | bundled with Python 3.13 | Host has no project dev packages |
| `uv` | Yes | `/usr/bin/uv` | No managed Python 3.11 directory found; not used for verification |
| pyenv / conda / micromamba | No | — | — |
| Node.js | Yes | `v24.22.2` | Matches CI Node 24 |
| npm | Yes | `12.2.2` | No repository npm pin |
| bun | No | — | `bun.lock` exists, but `bun` is unavailable |
| Docker | Yes | `29.10.0` | Daemon initially not running; started temporarily and stopped |
| Docker Compose | Yes | `v5.8.0` | No Compose file in repository |
| pytest (host) | No | — | Present in `/tmp/rev-ind-01-wp07-venv` |
| pyflakes / bandit / pip-audit (host) | No | — | Present in the 3.13 venv and installed in the 3.11 container |
| Git | Yes | available | Needed by five autopush tests |
| GitHub CLI | Yes | `2.105.0` | Not used for publication |
| Sudo | Yes | `sudo -n true` exit `0` | Used only to start/stop local Docker |

### 4.1 Python 3.11 route

Python 3.11 is not installed natively. The safe existing alternative used was Docker:

- Image: `python:3.11-slim`
- Python: `3.11.18`
- Digest: `sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535`
- Container filesystem only; the project working tree was not mounted read-write. A clean `HEAD` archive was mounted into `/work`.
- `git` was installed inside the disposable container because five autopush tests invoke it. The host environment was not changed.

The Docker daemon was stopped after verification. No production service, Telegram call, OpenHands call, or deployment was made.

---

## 5. Python 3.11 installation and test results

### 5.1 Source and installation

```sh
tmp=$(mktemp -d /tmp/ohb2-wp09-head.XXXXXX)
git archive HEAD | tar -x -C "$tmp"
```

Inside `python:3.11-slim`:

```sh
python -V
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -c "import bot.bootstrap, bot.app, main; print('IMPORT_OK', bot.bootstrap.MIN_PYTHON)"
```

| Command | Exit | Result |
|---|---:|---|
| `python -V` | 0 | `Python 3.11.18` |
| `python -m pip install --upgrade pip` | 0 | pip upgraded inside container |
| `python -m pip install -r requirements-dev.txt` | 0 | all pinned runtime/dev packages installed |
| `python -c "import bot.bootstrap, bot.app, main; ..."` | 0 | `IMPORT_OK (3, 11)`; no production calls |

### 5.2 First full-suite attempt (environment artifact)

The first `python:3.11-slim` run did not include `git`:

```sh
python -m pytest -q
```

Result: **exit 1**, **3508 passed, 1 skipped, 5 failed**, 74 warnings, **170.83 s**.

The five failures were:

- `tests/test_autopush_automation.py::test_autopush_commits_and_pushes_changes`
- `tests/test_autopush_automation.py::test_autopush_no_changes_makes_no_push`
- `tests/test_autopush_automation.py::test_autopush_fails_closed_on_unapproved_path`
- `tests/test_autopush_automation.py::test_autopush_default_allowlist_stages_nothing`
- `tests/test_autopush_security.py::test_credential_not_written_to_git_config`

Root cause in the log: `FileNotFoundError: [Errno 2] No such file or directory: 'git'`. This is a **container-image limitation**, not a Python 3.11 incompatibility. The final valid run installed `git` in the disposable container.

### 5.3 Final Python 3.11 run with `git` available

```sh
apt-get update
apt-get install -y --no-install-recommends git
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

| Command | Exit | Result |
|---|---:|---|
| `python -V` | 0 | `Python 3.11.18` |
| `git --version` | 0 | git installed in container |
| `python -m pip install --upgrade pip` | 0 | success |
| `python -m pip install -r requirements-dev.txt` | 0 | success |
| `python -m pytest -q` | **0** | **3513 passed, 1 skipped, 0 failed**, 74 warnings, **169.99 s** |

The one skip is `tests/test_frontend_ops.py::test_frontend_operation_logic`, skipped because `node` is not installed in the Python container. Node was tested separately on the host: **280/280 passed**.

Warnings (74 total) are deprecation warnings, not failures:

- Starlette `TestClient` with `httpx` deprecation.
- `anyio.abc.BlockingPortal` deprecation.
- `python-telegram-bot` `retry_after` deprecation in `tests/test_batch3r_fix.py`, `test_batch3r_fix2_f1.py`, `test_notifier.py`, `test_watcher.py`.

### 5.4 Python 3.11 static/security checks

| Command | Exit | Result |
|---|---:|---|
| `python -m pyflakes bot/ automation/ tools/ main.py tests/` | 0 | no diagnostics |
| `python -m pip_audit -r requirements-dev.txt` | 0 | `No known vulnerabilities found` |
| `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | 0 | `No issues identified`; High **0**, Low 5, Medium 19 |

---

## 6. Python 3.13 results

Python 3.13 used the existing isolated venv `/tmp/rev-ind-01-wp07-venv` (`Python 3.13.15`, `pytest 9.0.3`, `pyflakes 4.0.3`). `pip check` returned `No broken requirements found`, exit `0`.

A fresh clean-HEAD archive was used for the 3.13 run so the pre-existing working-tree concurrency changes were excluded.

| Command | Exit | Result |
|---|---:|---|
| `python -m pip check` | 0 | no broken requirements |
| `python -m pyflakes bot/ automation/ tools/ main.py tests/` | 0 | no diagnostics |
| `python -m pip_audit -r requirements-dev.txt` | 0 | `No known vulnerabilities found` |
| `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | 0 | High **0**, Low 5, Medium 19 |
| `python -m compileall -q bot automation tools tests main.py` | 0 | syntax compilation clean |
| `python -m pytest -q` | **0** | **3514 passed, 0 failed**, 74 warnings, **174.28 s** |

The 3.13 count is one higher than 3.11 because the Node-dependent `test_frontend_operation_logic` test ran on the host instead of being skipped.

An earlier 3.13 attempt was interrupted by the terminal timeout after 2478 passes; it was not used as evidence. The final background run completed with the result above.

---

## 7. Node.js / npm compatibility

### 7.1 Versions and required target

| Item | Value |
|---|---|
| Local Node | `v24.22.2` |
| Local npm | `12.2.2` |
| CI Node | `24` (`.github/workflows/ci.yml:62-67`) |
| npm pin | none; no `engines`, no `packageManager` |
| Lockfiles | `package-lock.json` (v3) and `bun.lock`; `bun` unavailable |

Node 24 is supported for the documented frontend test command.

### 7.2 Frontend tests

```sh
node --test tests/frontend/*.test.js
```

Result: **exit 0**, **280 tests, 280 pass, 0 fail, 0 cancelled, 0 skipped, 0 todo**, duration **1035.12 ms**. This matches the CI frontend job command.

### 7.3 Reproducible install and build

```sh
npm ci
npm run build
```

Result: **`npm ci` exit 1** with `EUSAGE`:

```text
npm error `npm ci` can only install packages when your package.json and
npm error package-lock.json are in sync. Please update your lock file with
npm error `npm install` before continuing.
```

The log lists missing optional/platform packages including `@tailwindcss/oxide-*`, `lightningcss-*`, `@rolldown/binding-*`, and `@typescript/typescript-*`. Therefore the reproducible install path is currently broken.

To separate lockfile drift from a source/build defect, a disposable temp copy was used:

```sh
npm install --no-audit --no-fund
npm run build
```

Result:

- `npm install`: exit `0`, 178 packages added in 5 s.
- `npm run build`: exit `0`, Vite 8.3.8 built `dist/index.html`, CSS, and JS in 235 ms.
- Vite emitted a non-blocking warning about ESM syntax in `vite.config.ts` being loaded as CommonJS.
- npm emitted warnings that three install scripts were blocked by its allow-scripts policy; the build still succeeded.

**Classification:** Node 24 runtime and frontend tests are **PASS**. `npm ci` reproducible install is **FAIL**; build after a non-reproducible `npm install` is **PASS**. The project `package-lock.json` was not modified; the temp copy's lockfile changes are outside the project.

The presence of both `bun.lock` and `package-lock.json`, with no `packageManager` field, is a second reproducibility ambiguity. `bun` is not installed.

---

## 8. Docker verification

- **No Dockerfiles** and **no Compose files** exist in the repository. WP-09 does not require a Docker build; Docker is **NOT APPLICABLE** as a repository build requirement.
- Docker Engine `29.10.0` and Docker Compose `v5.8.0` are installed. The daemon was initially not running (`/var/run/docker.sock` absent).
- A local daemon was started temporarily only to run the official Python 3.11 image. It was stopped after verification; no container remains.
- The Python 3.11 image was `python:3.11-slim`, Python `3.11.18`, digest `sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535`.
- No production service, production credential, external Telegram/OpenHands call, or deployment was used.
- **Docker build/Compose validation: `NOT APPLICABLE`.** If the owner later adds Docker assets, a new verification task is required.

---

## 9. CI compatibility matrix

| Environment | Required version | Configured CI version | Locally available | Verification result |
|---|---|---|---|---|
| Python | `>=3.11`; CI 3.11/3.13 | `3.11`, `3.13` | Native 3.13.15; 3.11 via Docker 3.11.18 | **PASS** for both local equivalents |
| Python 3.11 | Mandatory | `3.11` | Docker 3.11.18 | **PASS** (3513 passed, 1 skip) |
| Python 3.13 | Supported/CI | `3.13` | 3.13.15 | **PASS** (3514 passed) |
| Node.js | 24 (current CI) | `24` | 24.22.2 | **PASS** (280/280) |
| Node.js 22 | Stale master-plan reference | Not configured | Not tested | **NOT APPLICABLE / STALE** |
| npm | No pinned version | Not installed by CI | 12.2.2 | **FAIL** for `npm ci`; build after `npm install` PASS |
| Frontend tests | `node --test` | Yes | Yes | **PASS** |
| Python lint | `pyflakes` | Yes | Yes | **PASS** both versions |
| Python SAST | `bandit -lll -s B613` | Yes | Yes | **PASS** both versions; High 0 |
| Dependency audit | `pip-audit` | Yes | Yes | **PASS** both versions |
| Docker validation | Not required | No | Docker available | **NOT APPLICABLE** |
| CI workflow execution | Push/PR only | `push`/`pull_request` | Not run on GitHub | **NOT RUN**; local equivalents PASS |

### 9.1 CI coverage observations

- `.github/workflows/ci.yml` covers Python 3.11 and 3.13, frontend tests on Node 24, `pyflakes`, `pip-audit`, `bandit`, and `pytest`.
- The frontend job runs only `node --test`; it does **not** run `npm ci`, `npm run build`, or `npm run lint`.
- No Docker validation is present; this is consistent with there being no Docker assets and WP-09 not requiring Docker.
- `f02-review.yml` also uses Python 3.11/3.13, but it is a review/evidence workflow, not the primary CI gate.
- CI has no `workflow_dispatch`; it runs on `push`/`pull_request` to `main`. No push/PR was authorized, so the GitHub runner itself was not executed.
- The master plan's Node 22 text conflicts with current CI/corrected-baseline Node 24. This is a documentation inconsistency, not a local runtime failure.
- CI runs `python -m pip install --upgrade pip` without a pip pin. This is not a project dependency pin and did not cause a failure.

---

## 10. Exact commands and exit codes

### 10.1 Baseline and environment

| Command | Exit | Output summary |
|---|---:|---|
| `git rev-parse HEAD` | 0 | `0774c9cff923a2ed02da36a1111a283a61600ea5` |
| `git rev-parse HEAD^{tree}` | 0 | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| `git status --short --branch` | 0 | `## main...origin/main` plus pre-existing modifications |
| `python3 --version` | 0 | `Python 3.13.15` |
| `node --version` | 0 | `v24.22.2` |
| `npm --version` | 0 | `12.2.2` |
| `docker --version` | 0 | `Docker version 29.10.0, build fdd4b8e` |
| `docker compose version` | 0 | `Docker Compose version v5.8.0` |

### 10.2 Python 3.11 container

| Command | Exit | Output summary |
|---|---:|---|
| `docker pull python:3.11-slim` | 0 | image pulled; digest recorded |
| `docker run --rm python:3.11-slim python -V` | 0 | `Python 3.11.18` |
| `apt-get install -y --no-install-recommends git` | 0 | git available |
| `python -m pip install --upgrade pip` | 0 | success |
| `python -m pip install -r requirements-dev.txt` | 0 | success |
| `python -c "import bot.bootstrap, bot.app, main; ..."` | 0 | `IMPORT_OK (3, 11)` |
| `python -m pyflakes bot/ automation/ tools/ main.py tests/` | 0 | no diagnostics |
| `python -m pip_audit -r requirements-dev.txt` | 0 | no known vulnerabilities |
| `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | 0 | High 0, Low 5, Medium 19 |
| `python -m pytest -q` (without git) | 1 | 3508 passed, 1 skipped, 5 failed (missing `git`) |
| `python -m pytest -q` (with git) | **0** | **3513 passed, 1 skipped**, 74 warnings, 169.99 s |

### 10.3 Python 3.13

| Command | Exit | Output summary |
|---|---:|---|
| `/tmp/rev-ind-01-wp07-venv/bin/python -m pip check` | 0 | no broken requirements |
| `python -m pyflakes ...` | 0 | no diagnostics |
| `python -m pip_audit -r requirements-dev.txt` | 0 | no known vulnerabilities |
| `python -m bandit ... -lll -s B613` | 0 | High 0, Low 5, Medium 19 |
| `python -m compileall -q bot automation tools tests main.py` | 0 | clean |
| `python -m pytest -q` | **0** | **3514 passed**, 74 warnings, 174.28 s |

### 10.4 Node/npm

| Command | Exit | Output summary |
|---|---:|---|
| `node --test tests/frontend/*.test.js` | **0** | **280 pass, 0 fail**, 1035.12 ms |
| `npm ci` | **1** | `EUSAGE`; package.json/package-lock.json out of sync |
| `npm install --no-audit --no-fund` (temp only) | 0 | 178 packages added in 5 s |
| `npm run build` (temp only) | **0** | Vite 8.3.8; dist built in 235 ms |

---

## 11. Test counts and durations

| Run | Passed | Failed | Skipped | Warnings | Duration |
|---|---:|---:|---:|---:|---:|
| Python 3.11 first attempt (no git) | 3508 | 5 | 1 | 74 | 170.83 s |
| Python 3.11 final (git installed) | **3513** | **0** | **1** | 74 | **169.99 s** |
| Python 3.13 final | **3514** | **0** | 0 | 74 | **174.28 s** |
| Node frontend (`node --test`) | **280** | **0** | 0 | — | **1035.12 ms** |
| `npm run build` (after temp install) | — | — | — | — | **235 ms** |

The Python 3.11 skip is the Node-dependent frontend wrapper; Node tests were run separately and passed.

---

## 12. Failures, blockers, and missing evidence

1. **Native Python 3.11 is absent.** It was not available as `python3.11`; Docker `python:3.11-slim` was used as a safe existing alternative. This is a workaround, not a native-host result.
2. **First Python 3.11 full run failed 5 tests due to missing `git` in the minimal container.** This is an environment limitation. Re-running with `git` installed produced 3513 passed / 0 failed.
3. **One Python 3.11 test is skipped because Node is absent in the Python container.** `tests/test_frontend_ops.py::test_frontend_operation_logic` is conditional; the separate Node run passed 280/280. This is not a hidden failure.
4. **`npm ci` fails on lockfile drift.** This is a real reproducibility failure; `npm install` and `vite build` succeed in a temp copy, so the source build itself is viable.
5. **`bun.lock` and `package-lock.json` coexist with no canonical package manager declaration.** `bun` is unavailable. This is a packaging ambiguity.
6. **CI was not executed on GitHub.** No push/PR was authorized. Local clean-HEAD equivalents were executed; the GitHub runner remains `NOT RUN`.
7. **WP-09 Category 7 (external infrastructure) is `NOT RUN`.** It belongs to `WP-10`/`OD-05` and requires live Enzonic/SFTP/HTTPS/persistence checks; no production credentials or calls were used.
8. **Node 22 is stale in the master plan.** Current CI and corrected baseline use Node 24. Node 22 was not tested and is not the current CI target.
9. **Docker build validation is not applicable.** There are no Dockerfiles or Compose files.

---

## 13. Proposed remediation tasks

These are proposals only; none were implemented.

| ID | Proposed remediation | Why |
|---|---|---|
| `R-WP09-01` | Regenerate/align `package-lock.json` with `package.json` using the canonical Node 24/npm version; verify `npm ci` and `npm run build`; do not hand-edit the lockfile. | `npm ci` currently exits `EUSAGE`; reproducible frontend install is broken. |
| `R-WP09-02` | Choose a canonical frontend package manager/lockfile (`package-lock.json` vs `bun.lock`), add a `packageManager` declaration if appropriate, and document the reproducible install command. | Two lockfiles exist; `bun` is unavailable; npm is unpinned. |
| `R-WP09-03` | Update stale Node 22 references in `OHB2-REMEDIATION-MASTER-PLAN.md` and historical audit text to Node 24, or explicitly mark them historical. | Current CI/corrected baseline/Mini App docs use Node 24. |
| `R-WP09-04` | If frontend build is a release gate, add `npm ci` and `npm run build` to the CI frontend job and document them. | CI currently runs only `node --test`; build coverage is absent. |
| `R-WP09-05` | Run the GitHub Actions `CI` workflow on an authorized branch/PR to obtain actual runner evidence. | Local equivalents pass, but the GitHub runner itself is `NOT RUN`; publication requires explicit authorization. |
| `R-WP09-06` | Execute WP-09 Category 7 external infrastructure checks under `WP-10`/`OD-05`. | Enzonic SFTP, SQLite restart persistence, HTTPS ingress, and live OpenHands checks were not run. |

No dependency, lockfile, CI, Docker, application, test, or Mini App change was made while producing these proposals.

---

## 14. Overall WP-09 verdict

**`COMPLETE_WITH_NOTES` — WP-09 local release gate (Categories 1–6) is satisfied; WP-09 is not `COMPLETE`.**

Reasons for `COMPLETE_WITH_NOTES`:

- Python **3.11.18** full suite: **3513 passed, 0 failed, 1 environment skip**.
- Python **3.13.15** full suite: **3514 passed, 0 failed**.
- `pyflakes`, `pip-audit`, and `bandit` pass on both Python versions; `bandit` High 0.
- Node **24.22.2** frontend tests: **280/280 pass**.
- Syntax compilation (`compileall`) and `node --check` pass.

Remaining notes prevent a `COMPLETE` verdict:

- WP-09 Category 7 external infrastructure is **`NOT RUN`** (`WP-10`/`OD-05`).
- The GitHub Actions CI workflow was **not executed**; only local clean-HEAD equivalents were run.
- `npm ci` reproducible frontend install **fails** due lockfile drift; `npm install` + build passes only in a temp copy.
- Node 22 vs Node 24 documentation conflict remains.
- Docker build validation is **`NOT APPLICABLE`** because no Docker assets exist.

If the owner treats the frontend `npm ci`/build path as a mandatory WP-09 acceptance gate, the verdict must be downgraded to **`INCOMPLETE`** until `R-WP09-01` and `R-WP09-02` are resolved. Under the documented five-command WP-09 gate, the correct verdict is `COMPLETE_WITH_NOTES`.

---

## 15. Project file modification confirmation

- **Created:** `docs/reviews/OHB2-WP09-COMPATIBILITY-AND-ENVIRONMENT-VERIFICATION-REPORT.md` (this report only).
- **No application code, tests, dependencies, lockfiles, CI workflows, Dockerfiles, Compose files, runtime configuration, or Mini App files were modified.**
- The pre-existing tracked modifications (`.agent/PROGRESS.md`, `bot/app.py`, the three WP-07 documentation files, `tests/test_u04_concurrency.py`) and pre-existing untracked reports were preserved and not staged.
- Temporary Python 3.11 container, clean-HEAD archives, and frontend/npm temp copies were kept outside the project working tree. The temporary Docker daemon was stopped.
- No production credentials, Telegram calls, OpenHands calls, deployments, or external production services were used.
- **No Git publication action occurred:** no staging, commit, push, PR, merge, deployment, or Autopush activation; no reset, clean, force operation, or broad deletion.

---

## 16. Report SHA-256

SHA-256 of this report's content above this section, before this section was appended:

`082d2db4df085ab67e9e7f4f5e7a89bf4717a6f2747f08db354d8f30b94e45f6`

The final file SHA-256, including this section, is reported in the task final response and can be recomputed with `sha256sum` on this path.
