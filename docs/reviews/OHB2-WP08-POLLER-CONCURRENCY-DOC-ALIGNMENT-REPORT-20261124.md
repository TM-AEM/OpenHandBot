# OHB2 — WP-08 Poller Concurrency Documentation Alignment

**Task ID:** `OHB2-WP08-POLLER-CONCURRENCY-DOC-ALIGNMENT`
**Date:** 2026-11-24
**Mode:** documentation and focused test repair only; no runtime behavior change.
**Repository:** `/workspace/project/OpenHandBot`
**Final verdict:** **`READY — AWAITING BATCH INDEPENDENT REVIEW`**

> This is implementation and local verification evidence only. It is not an independent review, owner
> acceptance, or WP-08 closure.

---

## 1. Actual baseline

| Item | Value |
|---|---|
| Branch | `main` |
| `HEAD` | `2d528633a86472a6a502d7dca5b69ae9f10359ab` |
| `HEAD` tree | `90b62951e53156ac55cffca2f471a0690f21b3d0` |
| Local `origin/main` | `2d528633a86472a6a502d7dca5b69ae9f10359ab` |
| Staged changes | none |
| Worktree | dirty with pre-existing WP-03/WP-09/A4-F5 work |
| `bot/app.py` SHA-256 | `70870c649b0fa1b9ba3f27bea227b521902ee7395ad6d29011249b4bf465b031` |
| `tests/test_u04_concurrency.py` SHA-256 | `e78de07e026f30f53b4958d20368097a85268cd2239a2e220944e023fa7c6404` |
| `docs/OPERATIONS_RUNBOOK.md` baseline SHA-256 | `709c4d44c6de6ee5930d234593a78fea24cb62b4a0a62ebc236602d4a97a4f7b` |
| `tests/test_doc_code_parity.py` baseline SHA-256 | `12caa03d08ffd85551b77caa2ceccb01b7bb3a814fe77a38f4499aa7f565e000` |

Pre-existing tracked and untracked changes were preserved. In particular, the WP-09 package/CI
changes, WP-03/A4-F5 changes, and all untracked reports were not modified by this task.

### 1.1 Confirmed starting behavior

`bot/app.py:101` contains:

```python
.concurrent_updates(False)
```

`tests/test_u04_concurrency.py:113-116` asserts:

```python
assert app.concurrent_updates == 1
assert app._update_processor.max_concurrent_updates == 1
```

The Runbook previously said `concurrent_updates(True)` at line 141, which was the confirmed
`WP08-FIND-01` documentation mismatch.

---

## 2. Changes made

### 2.1 `docs/OPERATIONS_RUNBOOK.md`

Corrected the polling section to document the current serial configuration:

- Changed `concurrent_updates(True)` to `concurrent_updates(False)`.
- Documented `max_concurrent_updates == 1`.
- Documented that `Application.update_queue` processing is serial.
- Preserved the existing `TelegramPoller.dispatch_and_wait` / `update_queue.join()` explanation and
  the operational implication that a slow or unresolved update delays the next update in the batch.
- Added only the existing limitation that the setting does not add an acknowledgment or exactly-once
  guarantee. No new delivery or ordering guarantee was invented.

### 2.2 `tests/test_doc_code_parity.py`

Added a focused parity guard:

- Reads `bot/app.py` into `APP_SRC`.
- Extracts only the Runbook section from `- **الاستقبال:**` to `- **الحالة المستقرة:**`.
- Asserts `bot/app.py` contains `.concurrent_updates(False)`.
- Asserts the Runbook section contains `concurrent_updates(False)`.
- Asserts the Runbook section does **not** contain `concurrent_updates(True)`.

The test follows the existing `_doc_section` convention and does not parse unrelated Runbook text.

### 2.3 Report

- Created this report only.

No runtime poller code, `OD-04` policy, Mini App, `bot/config.py`, dependencies, lockfiles, CI, or
deployment configuration was changed.

---

## 3. Finding disposition

| Finding | Disposition | Evidence |
|---|---|---|
| `WP08-FIND-01` — Runbook poller concurrency text contradicted `bot/app.py` | **RESOLVED** | Runbook now says `concurrent_updates(False)`; new parity test passes; stale negative control fails |

---

## 4. Verification

### 4.1 New parity test

```sh
/tmp/ohb2-wp08-audit-venv/bin/python -m pytest -q \
  tests/test_doc_code_parity.py::test_runbook_poller_concurrency_matches_application
```

Result: **1 passed**, exit `0`.

### 4.2 Focused WP-08 tests

```sh
/tmp/ohb2-wp08-audit-venv/bin/python -m pytest -q \
  tests/test_doc_code_parity.py \
  tests/test_start_script.py \
  tests/test_deploy_manifest.py \
  tests/test_zero_touch_contract.py
```

Result: **46 passed**, exit `0`.

### 4.3 Poller/readiness focused tests

```sh
/tmp/ohb2-wp08-audit-venv/bin/python -m pytest -q \
  tests/test_u04_concurrency.py \
  tests/test_wp07_route_renewal_and_policy.py \
  tests/test_stabilization_f02_f06.py
```

Result: **41 passed**, 2 warnings, exit `0`.

### 4.4 Full Python suite

```sh
/tmp/ohb2-wp08-audit-venv/bin/python -m pytest -q
```

Result: **3824 passed, 0 failed, 74 warnings**, exit `0`.

The suite includes pre-existing uncommitted WP-03/A4-F5/WP-09 changes; those changes are not part of
this task.

### 4.5 Negative control

A disposable copy was made under `/tmp/ohb2-wp08-poller-negative` from `git archive HEAD`, then the
current Runbook and parity test were copied in. Only the temp Runbook was changed back to
`concurrent_updates(True)`.

```sh
cd /tmp/ohb2-wp08-poller-negative
python -m pytest -q \
  tests/test_doc_code_parity.py::test_runbook_poller_concurrency_matches_application
```

Result: **1 failed**, exit `1`:

```text
AssertionError: Runbook لا يذكر concurrent_updates(False) في قسم الاستقبال
```

This proves the new assertion is non-vacuous. The real repository was not modified by the negative
control.

### 4.6 Static and diff checks

| Check | Result | Exit |
|---|---|---|
| `pyflakes tests/test_doc_code_parity.py` | no diagnostics | 0 |
| `compileall -q tests/test_doc_code_parity.py` | clean | 0 |
| `git diff --check` | clean | 0 |
| `git diff --stat -- docs/OPERATIONS_RUNBOOK.md tests/test_doc_code_parity.py` | 2 files, 26 insertions, 5 deletions | 0 |

### 4.7 Not run

- GitHub Actions/CI: **NOT RUN / NOT VERIFIED**.
- Node/frontend tests: not relevant to this documentation-only repair; not run.
- Independent review: **NOT PERFORMED**.
- Production API/Telegram/OpenHands/Enzonic calls: **NONE**.

---

## 5. Runtime and protected-path confirmation

| Item | Confirmation |
|---|---|
| `bot/app.py` | SHA-256 unchanged: `70870c649b0fa1b9ba3f27bea227b521902ee7395ad6d29011249b4bf465b031` |
| `tests/test_u04_concurrency.py` | SHA-256 unchanged: `e78de07e026f30f53b4958d20368097a85268cd2239a2e220944e023fa7c6404` |
| `OD-04` policy | untouched; no concurrency policy change |
| `docs/MINI_APP.md` | no diff vs `HEAD` |
| `bot/web/` | no diff vs `HEAD` |
| `bot/config.py` | no diff vs `HEAD` |
| Mini App files | untouched |
| Pre-existing unrelated changes | preserved; no reset, clean, stash, stage, commit, push, PR, merge, deploy, release, or Autopush |

The pre-existing `.github/workflows/ci.yml`, `package.json`, `package-lock.json`, and `bun.lock`
worktree changes belong to the earlier WP-09 task; they were not touched here.

---

## 6. Changed files

| File | Change | Final SHA-256 |
|---|---|---|
| `docs/OPERATIONS_RUNBOOK.md` | Poller section corrected to `concurrent_updates(False)` and serial behavior | `d9894196acc0fcc509761f6d2dbe3d730802994d5a044a938d449ec75ad74635` |
| `tests/test_doc_code_parity.py` | Added focused Runbook/application poller parity test | `9324d9b2b1b8744682e21b134e09959a59f327005876d95242285741d55305fb` |
| `docs/reviews/OHB2-WP08-POLLER-CONCURRENCY-DOC-ALIGNMENT-REPORT-20261124.md` | This report | see §8 |

---

## 7. Final Git state

| Item | Value |
|---|---|
| Branch | `main` |
| `HEAD` | `2d528633a86472a6a502d7dca5b69ae9f10359ab` (unchanged) |
| Tree | `90b62951e53156ac55cffca2f471a0690f21b3d0` (unchanged) |
| Staged | none |
| Commits/push/PR/merge/deploy/release | none |
| Branch switch/reset/clean/force | none |

---

## 8. Report integrity

**Report body SHA-256 (excluding this footer):** `b777e5ce7fe95fac728678d18fd2e08f4f9a2b9eaffcc1d1c1eda15a6179bc4e`
