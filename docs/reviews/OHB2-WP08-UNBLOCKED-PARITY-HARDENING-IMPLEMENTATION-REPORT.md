# OHB2 — WP-08 Unblocked Parity Hardening — Implementation Report

**Task ID:** `OHB2-WP08-UNBLOCKED-PARITY-HARDENING`
**Date:** 2026-11-22
**Mode:** documentation and test hardening only; no application behavior, architecture, schema, dependency, lockfile, CI, Docker, runtime, or Mini App changes.
**Repository:** `/workspace/project/OpenHandBot`
**Final verdict:** **`DONE_WITH_NOTES`**

---

## 1. Baseline branch, HEAD, and working-tree state

| Item | Baseline value |
|---|---|
| Branch | `main` |
| HEAD | `0774c9cff923a2ed02da36a1111a283a61600ea5` |
| HEAD tree | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| Upstream | `origin/main` at `0774c9cff923a2ed02da36a1111a283a61600ea5` (no fetch/pull) |
| Tracked pre-existing modifications | `.agent/PROGRESS.md`, `bot/app.py`, `docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md`, `docs/audits/OHB2-WP07-FINAL-STABILIZATION-AUDIT.md`, `docs/audits/OHB2-WP07-NEW-DEF03-S3-DELIVERY-AND-ACCEPTANCE-RECONCILIATION.md`, `tests/test_u04_concurrency.py` |
| Untracked pre-existing files | Three poller-concurrency audit reports, `OHB2-WP07-NAV-OWNER-DECISION-PACKAGE.md`, `OHB2-WP08-SCOPE-RECOVERY-AND-STATUS-AUDIT-REPORT.md`, `OHB2-WP09-COMPATIBILITY-AND-ENVIRONMENT-VERIFICATION-REPORT.md`, `REV-IND-01-WP-07-INDEPENDENT-REVIEW-REPORT.md` |
| Ignored | `.openhands/`, `.pytest_cache/`, `__pycache__/`, and related Python caches |

All pre-existing changes were preserved. None were staged, reverted, overwritten, or included in a commit.

### Source-of-truth verification

| Item | Verified source | Actual semantics |
|---|---|---|
| `MINI_APP_TRUSTED_PROXIES` | `bot/config.py:38,120-134,312`; `bot/web/clientip.py` | Optional comma-separated IPs/CIDRs; default empty; empty means no forwarded header is trusted; invalid value raises `ConfigError`. |
| `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` | `bot/config.py:43,315-317`; `bot/handlers.py:2556` | Default `True` (`1`); `0` disables Telegram document intake only: no `get_file`, download, staging row, or OpenHands call; text/buttons, Mini App behavior, and unsupported-media rejection remain unchanged. |
| `DEFERRED_FEATURES_HIDDEN` | `bot/features.py:15,20-22` | Current value `False`; `is_hidden()` hides only when the flag is `True` and the feature is in `HIDDEN_FEATURES`. |
| `start.sh` dependency mechanism | `start.sh:48-97`; `requirements.txt` | Runtime probe tuple `mods`; missing dependencies trigger optional `pip install -r requirements.txt`; `anyio` is pinned in `requirements.txt`. |

---

## 2. Five task items and implementation status

| Item | Implementation | Status |
|---|---|---|
| 1. ZERO_TOUCH §2.3 env documentation | Added `MINI_APP_TRUSTED_PROXIES` and `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` rows with source-accurate defaults/semantics. | **DONE** |
| 2. Protect `anyio` in start-script tests | Added `test_anyio_is_in_startup_probe_and_install_requirements` in `tests/test_start_script.py`; it parses the actual `start.sh` dependency tuple, checks `requirements.txt` pins `anyio`, and verifies `start.sh` uses `pip install -r requirements.txt`. | **DONE** |
| 3. Harden documentation parity tests | Added section-scoped parsers for Runbook §3/§4 and README env table; exact set comparison for env vars; exact table set, duplicate, and count checks for §4. | **DONE** |
| 4. Test ownership and parity coverage | Kept `tests/test_doc_code_parity.py` as the canonical parity module and documented that ownership in its module docstring. `tests/test_deploy_manifest.py` and `tests/test_zero_touch_contract.py` remain runtime/deploy contract tests; no duplicate parity assertions were added. | **DONE** |
| 5. README `DEFERRED_FEATURES_HIDDEN` accuracy | Replaced `DEFERRED_FEATURES_HIDDEN=True` phrasing with current `False` value and conditional `True` hiding behavior. | **DONE** |

---

## 3. Exact files changed by this task

| File | Change |
|---|---|
| `docs/ZERO_TOUCH_STARTUP.md` | Added the two missing env rows to §2.3. |
| `tests/test_start_script.py` | Added explicit `anyio` probe/requirements regression test. |
| `tests/test_doc_code_parity.py` | Added section-scoped env/schema helpers; hardened README/Runbook tests; documented canonical ownership. |
| `README.md` | Corrected current `DEFERRED_FEATURES_HIDDEN` wording. |
| `docs/reviews/OHB2-WP08-UNBLOCKED-PARITY-HARDENING-IMPLEMENTATION-REPORT.md` | This report. |

No changes were made to `bot/web/`, `docs/MINI_APP.md`, `Config.mini_app_*`, `bot/app.py`, `tests/test_u04_concurrency.py`, SQLite schema, `/updates_*`, dependencies, lockfiles, CI, Docker, or runtime behavior.

---

## 4. Test commands, counts, and exit codes

### 4.1 Focused WP-08 group

```sh
/tmp/rev-ind-01-wp07-venv/bin/python -m pytest -q \
  tests/test_doc_code_parity.py \
  tests/test_start_script.py \
  tests/test_deploy_manifest.py \
  tests/test_zero_touch_contract.py
```

Result: **44 passed in 1.70 s**, exit **0**.

Per-file collection after the change:

| File | Tests |
|---|---:|
| `tests/test_doc_code_parity.py` | 14 |
| `tests/test_start_script.py` | 14 |
| `tests/test_deploy_manifest.py` | 6 |
| `tests/test_zero_touch_contract.py` | 10 |

The previous WP-08 focused total was 43; the new `anyio` test accounts for the increase to 44.

### 4.2 Additional directly affected tests

```sh
/tmp/rev-ind-01-wp07-venv/bin/python -m pytest -q \
  tests/test_repair_plan_02_life03_intake_kill_switch.py \
  tests/test_features_hidden.py \
  tests/test_n1002_feature_flag_reachability.py
```

Result: **31 passed, 2 warnings**, exit **0**.

```sh
/tmp/rev-ind-01-wp07-venv/bin/python -m pytest -q \
  tests/test_audit_remediation_f01_f07.py -k f07
```

Result: **62 passed, 2 warnings**, exit **0**.

### 4.3 Static check

```sh
/tmp/rev-ind-01-wp07-venv/bin/python -m pyflakes bot/ automation/ tools/ main.py tests/
```

Result: exit **0**, no diagnostics.

### 4.4 Diff check

```sh
git diff --check
```

Result: exit **0**, no whitespace errors.

### 4.5 Full suite

The full repository test suite was **not executed** in this task. No claim is made that the full suite passed. The focused and directly affected tests above are the actual execution evidence.

---

## 5. Mutation-test results and limitations

All mutations were performed in disposable copies under `/tmp`; the real working tree was not mutated.

| ID | Mutation | Test | Result | Expected |
|---|---|---|---|---|
| M1 | Remove `MINI_APP_TRUSTED_PROXIES` from Runbook §3 | `test_runbook_documents_every_config_variable` | **1 failed**, exit 1 | Fail |
| M2 | Remove `notification_inbox` from Runbook §4 list while leaving it in §9 | `test_runbook_documents_every_schema_table` | **1 failed**, exit 1 | Fail |
| M3 | Change `**17** جدول` to `**18** جدول` without changing the list | `test_runbook_table_count_matches_schema` | **1 failed**, exit 1 | Fail |
| M4 | Remove `, "anyio"` from `start.sh` dependency tuple | `test_anyio_is_in_startup_probe_and_install_requirements` | **1 failed**, exit 1 | Fail |
| M5 | Add unexpected `EXTRA_ENV` row to Runbook §3 | `test_runbook_documents_every_config_variable` | **1 failed**, exit 1 | Fail |
| M6 | Add unexpected `extra_table` to Runbook §4 list | `test_runbook_documents_every_schema_table` | **1 failed**, exit 1 | Fail |

### Mutation limitations

- The first M2 harness attempt did not apply because the target row ends with a comma but no trailing space. The harness was corrected in the temp copy; the final M2 run failed as intended. This was a harness issue, not a project-code issue.
- The `anyio` test is a static contract test: it verifies the actual `start.sh` dependency declaration, the `requirements.txt` pin, and the intended `pip install -r requirements.txt` mechanism. It does not perform a live network install.
- Mutations M1–M6 are isolated temporary-copy checks; they do not prove every possible documentation drift, only the specific contracts exercised.

---

## 6. `git diff --check` result

`git diff --check` exited **0** with no output. This check includes the task's four modified tracked files plus pre-existing working-tree changes; no whitespace errors were introduced.

---

## 7. Explicitly deferred and excluded WP-08 items

The following remain intentionally untouched:

- `/updates_status` and `/updates_skip` documentation and implementation (`OD-02` / WP-04 Part 2).
- `callback_refs` and the 17→18 SQLite table change (WP-06 Part 2 / O-5/O-6/O-7).
- Final `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` default policy (`OD-01` / `OD-03`).
- Final poller concurrency documentation (`OD-04` / WP-07).
- `bot/app.py` and `tests/test_u04_concurrency.py` pre-existing changes.
- Mini App files, `docs/MINI_APP.md`, `Config.mini_app_*`, and Mini App behavior.
- Dependencies, lockfiles, CI workflows, Docker configuration, and runtime behavior.
- Owner-gated or deferred WP-08 items generally.

---

## 8. Remaining issues or deviations

1. **No full-suite execution:** only focused and directly affected tests were run.
2. **Static `anyio` test:** it proves declaration/requirements/install-path wiring, not a live pip install.
3. **Canonical parity ownership:** `tests/test_doc_code_parity.py` is now explicitly documented as the canonical env/schema documentation parity guard. `tests/test_deploy_manifest.py` and `tests/test_zero_touch_contract.py` were intentionally not duplicated with the same contract.
4. **No independent review:** this task required ordinary implementation verification only; no independent review is claimed.
5. **No owner acceptance:** owner-gated WP-08 items remain outside this task.

---

## 9. Final verdict

**`DONE_WITH_NOTES`**

All five unblocked WP-08 items were implemented. Focused tests pass, additional affected tests pass, static checks pass, `git diff --check` passes, and all six mutation checks fail in the intended direction. The notes are the absence of a full-suite run, the static nature of the `anyio` test, and the deliberate canonical-test-location decision.

---

## 10. Report SHA-256

SHA-256 of this report's content above this section, before this section was appended:

`4a6358f59c062136c085bbba1b9eee781cbb65f2753026464951c87809d2d4b9`

The final file SHA-256, including this section, is reported in the task final response and can be recomputed with `sha256sum` on this path.
