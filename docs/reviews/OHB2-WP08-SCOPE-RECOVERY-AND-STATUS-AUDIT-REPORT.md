# OHB2 — WP-08 Scope Recovery and Status Audit Report

**Task ID:** `OHB2-WP08-SCOPE-RECOVERY-AND-STATUS-AUDIT`
**Date:** 2026-11-22
**Mode:** audit and documentation only; no application, test, dependency, lockfile, CI, Docker, runtime, or Mini App changes.
**Repository:** `/workspace/project/OpenHandBot`
**Branch:** `main`
**HEAD:** `0774c9cff923a2ed02da36a1111a283a61600ea5`
**Overall verdict:** **`INCOMPLETE`**

---

## 1. Executive verdict

**WP-08 is `INCOMPLETE`, not `COMPLETE` and not `BLOCKED`.**

The original WP-08 scope was reliably recovered. The committed implementation at `HEAD` already covers the main documentation synchronization, `start.sh` `anyio` probe, and a dedicated documentation/env/schema parity test file. However, WP-08 cannot be marked complete because:

1. `docs/ZERO_TOUCH_STARTUP.md` still omits `MINI_APP_TRUSTED_PROXIES` and `ATTACHMENT_DOCUMENT_INTAKE_ENABLED`, both explicitly required by the original WP-08 target list.
2. `start.sh` contains `anyio`, but `tests/test_start_script.py` has **no explicit anyio assertion**. Mutation removing `anyio` from `start.sh` leaves all 13 start-script tests green.
3. `tests/test_doc_code_parity.py` checks table/env names anywhere in `OPERATIONS_RUNBOOK.md`, not specifically in §4/§3. Removing `notification_inbox` from the §4 table list leaves the table test green because the name still appears in §9.
4. The originally named regression-test files `tests/test_deploy_manifest.py` and `tests/test_zero_touch_contract.py` contain no env/schema parity assertions; parity was placed in a new file instead.
5. `README.md` still describes the feature flag as `DEFERRED_FEATURES_HIDDEN=True`, while `bot/features.py` currently sets `False`. The text is ambiguous rather than a proven runtime contradiction, but it is not a clean current statement.
6. The final owner-gated parts of WP-08 remain open: `/updates_*` command docs (`OD-02` / WP-04 Part 2), the `callback_refs` 17→18 table change (WP-06 Part 2 / O-5/O-6/O-7), the final attachment-intake default (WP-01 / `OD-03`), and final poller concurrency wording (WP-07 / `OD-04`).
7. There is no dedicated WP-08 owner-acceptance record. Owner approval is not required for the non-Mini-App documentation and `start.sh` changes, but formal acceptance was not recorded.

The verdict is **not `BLOCKED`** because several unblocked, actionable items remain. It is **not `COMPLETE_WITH_NOTES`** because the acceptance criterion of zero contradictions and fully enforced parity is not met.

---

## 2. Recovered original WP-08 scope

### 2.1 Source hierarchy

The authoritative recovery sources are:

1. `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md` §E `WP-08` (lines 698–720), which supersedes earlier count errors.
2. `docs/audits/OHB2-REMEDIATION-MASTER-PLAN.md` WP-08 (lines 196–210), the original plan; its “19 tables” count is superseded by the corrected baseline’s 17 (or 18 only if `callback_refs` is approved and implemented).
3. `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md` defect entries:
   - `DEF-017` (lines 320–333)
   - `DEF-018` (lines 335–347)
   - `NEW-DEF-07` (lines 463–477)
   - `NEW-DEF-08` (lines 480–490)
4. `docs/reviews/OHB2-REMAINING-REMEDIATION-EXECUTION-REPORT.md` — implementation report and explicit “WP-08 PARTIAL” statement.
5. `docs/reviews/OHB2-POST-REMEDIATION-CUMULATIVE-INDEPENDENT-REVIEW.md` §5.7 — historical cumulative review of the partial WP-08 implementation.
6. `docs/audits/OHB2-WP06-PART2-OWNER-DECISION-REGISTER-OD-WP06-PART2-02.md` — O-5 direction approval, O-7 deferral, O-6 pending.
7. `docs/audits/OHB2-OWNER-DECISIONS-BRIEFING.md` — `OD-01`…`OD-05` remain pending and WP-08 is marked partially blocked.

### 2.2 Original requirements

| Requirement | Original description | Source |
|---|---|---|
| `DEF-017` documentation sync | Fix operational documentation contradictions and omissions across `ZERO_TOUCH_STARTUP.md`, `OPERATIONS_RUNBOOK.md`, `README.md`, and `API_NOTES.md`. | Baseline `DEF-017`; master plan WP-08 |
| Runbook schema inventory | Document the exact SQLite tables in `OPERATIONS_RUNBOOK.md` §4; corrected count is **17** (18 only if `callback_refs` is approved and implemented); derive dynamically from `bot/db.py::_init_schema`. | Baseline WP-08 constraint 1 |
| Runbook env inventory | Document all **20** env vars in `OPERATIONS_RUNBOOK.md` §3 and `README.md`, including `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` and `MINI_APP_TRUSTED_PROXIES`. | Baseline WP-08 constraint 2 |
| Runbook recovery guidance | Add `notification_inbox` persistence/recovery guidance to `OPERATIONS_RUNBOOK.md` §9. | Baseline WP-08 constraint 3 |
| Zero-Touch deletion truth | Fix `ZERO_TOUCH_STARTUP.md` to state that deletion is both remote `DELETE` and local tombstone, not local-only. | Baseline WP-08 constraint 4; `DEF-017` |
| Zero-Touch readiness truth | Align `/health`, `/ready`, and `/status` wording with the runbook and actual routes. | Baseline WP-08 constraint 4; `DEF-017` |
| Zero-Touch env list | Add `MINI_APP_TRUSTED_PROXIES` and `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` to `ZERO_TOUCH_STARTUP.md`. | Master plan WP-08 exact target list; `DEF-017` root cause |
| API version reconciliation | Reconcile OpenAPI versions in `API_NOTES.md` (`v1.68.1` historical vs `v1.79.0` client vs `v1.87.1` ADR vs `v1.91.0` P0). | Baseline WP-08 constraint 5; `DEF-017` |
| `start.sh` anyio probe | Add `"anyio"` to the runtime dependency probe at `start.sh:56`. | Baseline WP-08 constraint 6; `DEF-018` |
| `NEW-DEF-08` parity tests | Automated env-var and schema-table parity between `.env.example`/`bot/config.py`/`bot/db.py` and `README.md`/`OPERATIONS_RUNBOOK.md`; originally named in `tests/test_deploy_manifest.py` and `tests/test_zero_touch_contract.py`. | Baseline `NEW-DEF-08`; WP-08 regression tests |
| `test_start_script.py` anyio coverage | Update `tests/test_start_script.py` to cover `anyio`. | `DEF-018` required regression tests |
| AI Studio scaffold preservation | Do not delete root AI Studio scaffold files without explicit approval. | Baseline WP-08 explicit exclusions; `DEF-018` |
| Mini App freeze | Do not modify `docs/MINI_APP.md`, `bot/web/*`, or `Config.mini_app_*`. | Baseline WP-08 explicit exclusions |
| `NEW-DEF-07` propagation | Ensure live operational docs do not repeat the superseded audit facts. | Baseline WP-08 included defect IDs; `NEW-DEF-07` |

### 2.3 Superseded, conditional, and later items

| Item | Classification |
|---|---|
| Master-plan “19 SQLite tables” | **Superseded** by corrected baseline: 17 tables; 18 only if `callback_refs` is approved and implemented. Current schema has 17. |
| `callback_refs` / 18-table parity | **Conditional**, not current: WP-06 Part 2 design/O-5/O-6/O-7 are not authorized for migration. |
| `/updates_status` / `/updates_skip` docs | **Owner-gated**, not current: blocked on `OD-02` / WP-04 Part 2. |
| Final `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` default | **Owner-gated**, not current: blocked on WP-01 / `OD-03`; current code default is `True` and docs currently match it. |
| Final poller concurrency wording | **Owner-gated/conditional**: WP-07 / `OD-04`; current working tree has an uncommitted `concurrent_updates(False)` change while committed `HEAD` and runbook still say `True`. |
| AI Studio scaffold removal | **Deferred by design**: preserve unless the owner explicitly authorizes deletion. |
| Dedicated `tests/test_doc_code_parity.py` | **Later implementation choice**, not the originally named test-file location. It is functionally useful, but the original named files were not updated. |

---

## 3. Finding-by-finding status table

Status values: `COMPLETED`, `PARTIALLY_IMPLEMENTED`, `OPEN`, `BLOCKED`, `DEFERRED`, `SUPERSEDED`.

| ID / item | Original requirement | Current implementation evidence | Tests and execution evidence | Review / acceptance | Dependencies / blockers | Status |
|---|---|---|---|---|---|---|
| `DEF-017` / R1 | Runbook §4 documents all SQLite tables; dynamic count | `docs/OPERATIONS_RUNBOOK.md:86-92` lists **17** tables and names `bot/db.py::_init_schema`; actual schema count is 17. | `test_doc_code_parity.py::test_runbook_documents_every_schema_table` and `::test_runbook_table_count_matches_schema` pass; 14 parity/F-03 tests pass. Mutation M3 shows the table-name test is not §4-scoped. | Historical cumulative review says verified; no current independent review. No dedicated owner acceptance. | Final 18-table variant blocked by WP-06 Part 2/O-5/O-6/O-7. | **COMPLETED for current 17-table baseline; test hardening OPEN** |
| `DEF-017` / R2 | Runbook §3 documents all 20 env vars | `docs/OPERATIONS_RUNBOOK.md:41-67` has 20 env rows; actual `bot/config.py` set is 20. | `test_runbook_documents_every_config_variable` passes; test checks whole document, not §3. | Same as above. | Final defaults blocked by WP-01/`OD-03`; `/updates_*` docs blocked by `OD-02`. | **COMPLETED for current env set; finalization BLOCKED** |
| `DEF-017` / R3 | Runbook §9 `notification_inbox` recovery | `docs/OPERATIONS_RUNBOOK.md:392-398` documents persistence/recovery and read-only inspection. | Covered by document inspection; no dedicated assertion. | Historical review says present. | None. | **COMPLETED** |
| `DEF-017` / R4 | Zero-Touch remote deletion truth | `docs/ZERO_TOUCH_STARTUP.md:242-248` explicitly documents remote `DELETE` plus local tombstone and non-reversibility. | Document inspection. | Historical review says corrected. | None. | **COMPLETED** |
| `DEF-017` / R5 | Zero-Touch `/health`, `/ready`, `/status` alignment | `docs/ZERO_TOUCH_STARTUP.md:52-53` matches runbook §5 routes and semantics. | Document inspection; `tests/test_zero_touch_contract.py` exercises startup/DB lifecycle, not route wording. | Historical review says aligned. | None. | **COMPLETED** |
| `DEF-017` / R6 | Add `MINI_APP_TRUSTED_PROXIES` and `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` to `ZERO_TOUCH_STARTUP.md` | `docs/ZERO_TOUCH_STARTUP.md:85-92` lists Mini App settings but **omits both** required variables. | No test asserts this. | Not recorded. | None; unblocked. | **OPEN** |
| `DEF-017` / R7 | README documents all env vars | `README.md:70-91` contains all 20 config vars, including both missing runbook variables. | `test_readme_documents_every_config_variable` passes; mutation M2 removing `MINI_APP_TRUSTED_PROXIES` from README makes the test fail, proving it is load-bearing. | Historical review says added. | None. | **COMPLETED** |
| `DEF-017` / R8 | API_NOTES version reconciliation | `docs/API_NOTES.md:81-84` records `v1.68.1` as historical, `v1.87.1` ADR, `v1.91.0` P0, and warns not to treat it as fixed. | Document inspection. | Historical review says reconciled. | None. | **COMPLETED** |
| `DEF-017` / R9 (`NEW-DEF-07`) | Live docs must not repeat superseded audit facts | Most live docs are corrected (17 tables, 20 env vars, remote deletion, readiness). `README.md:33` still writes `DEFERRED_FEATURES_HIDDEN=True` while `bot/features.py:15` is `False`. | No test covers this README flag wording. | Not recorded. | None; unblocked clarification. | **PARTIALLY_IMPLEMENTED / AMBIGUOUS** |
| `DEF-018` / R1 | `start.sh:56` includes `anyio` | `start.sh:56` has `mods = ("telegram", "httpx", "dotenv", "starlette", "uvicorn", "anyio")`. | `tests/test_start_script.py` 13 tests pass, but no test mentions `anyio`. | Historical review says present. | None. | **COMPLETED (code)** |
| `DEF-018` / R2 | `tests/test_start_script.py` covers `anyio` | No `anyio` string or assertion in `tests/test_start_script.py`. | Mutation M1 removed `, "anyio"` from `start.sh`; all **13** start-script tests still passed. | Not recorded. | None; unblocked. | **OPEN** |
| `DEF-018` / R3 | Preserve AI Studio scaffold unless approved | `package.json`, `package-lock.json`, `bun.lock`, `index.html`, `metadata.json`, `vite.config.ts`, `tsconfig.json`, and `src/*` remain present; no diff vs `HEAD`. | File inventory and `git diff` inspection. | Approved preservation decision in `OHB2-PLAN04-UI01-FRONTEND-AUTHORITY.md`. | Deletion requires explicit owner approval. | **DEFERRED / PRESERVED** |
| `NEW-DEF-08` / R1 | Env parity between config/.env and README/Runbook | `tests/test_doc_code_parity.py:55-78` checks `.env.example` and README/Runbook; 14 tests pass. | Current focused run: **14 passed**; README mutation M2 fails correctly. Runbook check is whole-document, not §3-scoped. | Historical review says parity present; no current independent review. | None for current set; final set depends on owner-gated changes. | **PARTIALLY_IMPLEMENTED (test hardening OPEN)** |
| `NEW-DEF-08` / R2 | Schema parity between `bot/db.py` and Runbook | `tests/test_doc_code_parity.py:81-91` checks table names anywhere in Runbook and the literal count. | Mutation M3 removed `notification_inbox` from the §4 list but left it in §9; the table test still passed. Count test is count-only. | Historical review says mutation-verified; this audit found a section-scope gap. | Final 18-table variant blocked by WP-06 Part 2. | **PARTIALLY_IMPLEMENTED** |
| `NEW-DEF-08` / R3 | Parity assertions in originally named `test_deploy_manifest.py` / `test_zero_touch_contract.py` | Neither file contains env/schema parity assertions; parity lives in the new `test_doc_code_parity.py`. | Focused tests: `test_deploy_manifest.py` 6 passed, `test_zero_touch_contract.py` 10 passed; neither is a parity guard. | Implementation report documents the new file; no owner acceptance. | None; documentation/test-location decision. | **PARTIALLY_IMPLEMENTED / DEVIATED** |
| `WP-08` final / `/updates_*` docs | Document `/updates_status` and `/updates_skip` if approved | No commands exist in source; no docs. | Source grep finds no `/updates_status` or `/updates_skip` implementation. | Historical report says blocked. | `OD-02` / WP-04 Part 2. | **BLOCKED** |
| `WP-08` final / `callback_refs` 18-table parity | Update Runbook if WP-06 adds `callback_refs` | `callback_refs` absent; schema 17; runbook 17. | `grep` for `callback_refs` in `bot/db.py`/tests returns none. | O-5 direction only; O-6 pending; O-7 deferred. | WP-06 Part 2 design + explicit migration authorization. | **BLOCKED** |
| `WP-08` final / attachment default | Document final `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` default after WP-01/`OD-03` | Code default is `True`; README/Runbook currently document `1`/`True`; `.env.example` has the name. | No owner decision; docs match current code. | `OD-03` pending. | WP-01 / `OD-03`. | **BLOCKED for finalization; current docs accurate** |
| `WP-08` final / poller concurrency wording | Align runbook with final WP-07 polling policy | Committed `HEAD` has `concurrent_updates(True)` and runbook says `True`; working tree has uncommitted `concurrent_updates(False)` while runbook still says `True`. | Working-tree diff only; no full-suite run in this audit. | `OD-04` pending. | WP-07 / `OD-04`; do not edit uncommitted work. | **BLOCKED / WORKING-TREE MISMATCH** |
| `WP-08` acceptance | Owner acceptance of WP-08 | No dedicated WP-08 owner acceptance record in `.agent/PROGRESS.md` or owner-decision documents. | N/A. | Required owner approvals for docs/start.sh are `NONE`; formal acceptance not recorded. | None for docs; owner-gated subitems remain. | **ACCEPTANCE_NOT_RECORDED** |

---

## 4. Implementation, test, review, and acceptance evidence

### 4.1 Committed versus working-tree state

- `tests/test_doc_code_parity.py`, `start.sh`, `docs/OPERATIONS_RUNBOOK.md`, `docs/ZERO_TOUCH_STARTUP.md`, `docs/API_NOTES.md`, `README.md`, `tests/test_deploy_manifest.py`, `tests/test_zero_touch_contract.py`, and `tests/test_start_script.py` are tracked and **unchanged versus `HEAD`**.
- Commit `52e7789` (`chore: sync local remediation work to main`) contains the WP-08 documentation edits, `start.sh` `anyio` change, and the new `tests/test_doc_code_parity.py`.
- Commit `30dfa0d` later changed only `tests/test_doc_code_parity.py` (F-03 additions) among WP-08-related files.
- Current working tree has pre-existing uncommitted concurrency work: `M bot/app.py` and `M tests/test_u04_concurrency.py`; it was not modified by this audit.
- The working-tree `bot/app.py` change from `concurrent_updates(True)` to `False` creates a **working-tree-only** documentation mismatch with `OPERATIONS_RUNBOOK.md:141`, which still says `True`. This is not a committed WP-08 regression, but it is a WP-08 dependency if WP-07 work lands.

### 4.2 Actual focused test execution

Command:

```sh
/tmp/rev-ind-01-wp07-venv/bin/python -m pytest -q \
  tests/test_doc_code_parity.py \
  tests/test_start_script.py \
  tests/test_deploy_manifest.py \
  tests/test_zero_touch_contract.py
```

Result: **43 passed in 1.69 s**, exit `0`.

Per-file collection:

| File | Tests |
|---|---:|
| `tests/test_doc_code_parity.py` | 14 |
| `tests/test_start_script.py` | 13 |
| `tests/test_deploy_manifest.py` | 6 |
| `tests/test_zero_touch_contract.py` | 10 |

The full repository suite was **not rerun** in this audit. Historical WP-09/WP-08 counts are not treated as current evidence. The focused tests above are the actual current execution evidence for WP-08.

### 4.3 Mutation checks in disposable copies

All mutations were applied only to temp copies outside the project working tree.

| Mutation | Command | Result | Interpretation |
|---|---|---|---|
| M1 — remove `, "anyio"` from `start.sh` probe | `pytest -q tests/test_start_script.py` | **13 passed** | The required anyio behavior is **not pinned** by tests. |
| M2 — remove `MINI_APP_TRUSTED_PROXIES` from temp `README.md` | `pytest -q tests/test_doc_code_parity.py::test_readme_documents_every_config_variable` | **1 failed** | README env parity test is load-bearing. |
| M3 — remove `` `notification_inbox`, `` from the Runbook §4 table list, leaving §9 mention | `pytest -q tests/test_doc_code_parity.py::test_runbook_documents_every_schema_table` | **1 passed** | Table parity is whole-document, not §4-scoped; the test can miss a §4 omission. |

### 4.4 Review and acceptance status

- Historical implementation report `OHB2-REMAINING-REMEDIATION-EXECUTION-REPORT.md` records WP-08 as **PARTIAL** and lists the owner-gated gaps.
- Historical cumulative review `OHB2-POST-REMEDIATION-CUMULATIVE-INDEPENDENT-REVIEW.md` §5.7 records the docs/parity items as verified against source, but also records the final owner-gated items as not implemented.
- This audit did **not** perform or claim an independent review. The historical review is not treated as current independent evidence.
- No dedicated WP-08 owner acceptance record exists. `Required Owner Approvals: NONE` applies to the non-Mini-App documentation and `start.sh` changes, but the owner-gated finalization remains unresolved.

---

## 5. Dependencies and blockers

| Dependency / decision | Effect on WP-08 | Current status |
|---|---|---|
| `OD-01` + WP-01 | Final attachment routing and `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` behavior may change operator docs. | Pending; WP-01 not started. |
| `OD-03` + WP-01 | Final attachment-intake default; current docs match current `True` default, but not a frozen final policy. | Pending. |
| `OD-02` + WP-04 Part 2 | `/updates_status` and `/updates_skip` documentation; commands not implemented. | Pending; Part 2 blocked. |
| WP-06 Part 2 `callback_refs` + O-5/O-6/O-7 | Runbook table count may become 18; O-6 requires atomic runbook update. | O-5 direction only; migration not authorized; O-6 pending; O-7 deferred. |
| `OD-04` + WP-07 | Poller concurrency wording and runbook/code alignment. | Pending; working-tree `concurrent_updates(False)` vs runbook `True` is a live mismatch if that work lands. |
| WP-09 | Verification of parity tests on supported runtimes; not a documentation blocker. | WP-09 is separately audited; not re-run here. |
| WP-10 | External hosting qualification; no direct WP-08 implementation dependency. | Out of scope; `OD-05` pending. |
| Mini App freeze | `docs/MINI_APP.md`, `bot/web/*`, `Config.mini_app_*` must remain untouched. | Preserved; no diff vs `HEAD`. |
| AI Studio scaffold | Root scaffold files must remain unless explicitly approved for deletion. | Preserved; no diff vs `HEAD`. |

### 5.1 Overlap analysis

- **WP-05:** no direct overlap with WP-08 documentation scope; WP-08 documents final worker/schema behavior only.
- **WP-06:** direct overlap through `callback_refs` and the 17→18 table count; O-6 requires the runbook update in the same change set.
- **WP-07:** direct overlap through poller concurrency documentation and `bot/app.py`; final wording depends on `OD-04`.
- **WP-09:** verification dependency only; WP-08 parity tests are part of the Python suite.
- **WP-10:** no implementation overlap; external hosting documentation is out of WP-08's local scope.

---

## 6. Explicitly unresolved or unverifiable items

1. **ZERO_TOUCH env rows:** `MINI_APP_TRUSTED_PROXIES` and `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` are absent from `docs/ZERO_TOUCH_STARTUP.md`.
2. **Anyio test:** no explicit assertion in `tests/test_start_script.py`; M1 confirms the gap.
3. **Runbook table parity:** the test checks whole-document occurrence, not §4; M3 confirms the gap.
4. **Runbook env parity:** the test checks whole-document occurrence, not §3; not mutated, but structurally weak.
5. **Originally named test files:** `tests/test_deploy_manifest.py` and `tests/test_zero_touch_contract.py` do not contain env/schema parity assertions.
6. **README feature-flag wording:** `README.md:33` uses `DEFERRED_FEATURES_HIDDEN=True`; current code is `False`; clarification is needed.
7. **Owner-gated docs:** `/updates_*`, `callback_refs` 18-table variant, final attachment default, and final poller policy remain unresolved.
8. **Working-tree poller mismatch:** uncommitted `bot/app.py` uses `concurrent_updates(False)` while committed runbook says `True`; this is working-tree evidence, not a committed WP-08 state.
9. **Owner acceptance:** no dedicated WP-08 acceptance record.
10. **Full current suite:** not rerun in this audit; only the 43 focused tests were executed. Historical counts are not used as proof.

---

## 7. Recommended next actionable task

### Task ID

`OHB2-WP08-UNBLOCKED-PARITY-HARDENING`

### Why this is next

It addresses only unblocked WP-08 gaps and does not depend on `OD-01`…`OD-04`, WP-06 Part 2, or external infrastructure. It avoids the owner-gated finalization work and the working-tree poller change.

### Scope

1. Add `MINI_APP_TRUSTED_PROXIES` and `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` to the feature-specific env table in `docs/ZERO_TOUCH_STARTUP.md` with their actual defaults/behavior, without changing `Config.mini_app_*` or Mini App code.
2. Add an explicit `anyio` assertion to `tests/test_start_script.py` so removing `anyio` from `start.sh` fails the test.
3. Harden `tests/test_doc_code_parity.py`:
   - scope env-var checks to `OPERATIONS_RUNBOOK.md` §3;
   - scope table-name checks to §4;
   - assert the §4 table set and count together, not only a whole-document token or count.
4. Add the env/schema parity assertions to `tests/test_deploy_manifest.py` and/or `tests/test_zero_touch_contract.py`, or explicitly document and test the dedicated `tests/test_doc_code_parity.py` as the canonical guard if the owner accepts that location change.
5. Clarify `README.md` line 33 so it states the current `DEFERRED_FEATURES_HIDDEN=False` value and describes `True` only as the opt-in hiding mode.

### Acceptance criteria

- `docs/ZERO_TOUCH_STARTUP.md` contains both required env vars with accurate defaults and behavior.
- Removing `anyio` from `start.sh` causes at least one `tests/test_start_script.py` test to fail.
- Removing any table from the Runbook §4 list causes a parity test to fail; removing an env var from §3 causes a parity test to fail.
- The table list and count are asserted together and cannot drift independently.
- The README feature-flag wording is accurate for current code.
- All focused WP-08 tests pass; no Mini App, `Config.mini_app_*`, owner-gated, schema, or dependency changes.
- No owner decision is required for this task.

### Independent reviewer requirement

**No.** This is a documentation/test-only hardening task with no owner decision, schema change, architecture change, or Mini App change. A normal maintainer review is sufficient. Do not schedule a separate independent-review session for this immediate task.

---

## 8. Repository state and exact files created or modified

### 8.1 State at audit start

| Item | Value |
|---|---|
| Branch | `main` |
| HEAD | `0774c9cff923a2ed02da36a1111a283a61600ea5` |
| HEAD tree | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| Upstream | `origin/main` at `0774c9cff923a2ed02da36a1111a283a61600ea5` |
| Tracked modifications | `.agent/PROGRESS.md`, `bot/app.py`, three WP-07 audit documents, `tests/test_u04_concurrency.py` |
| Untracked files | three poller-concurrency reports, `OHB2-WP07-NAV-OWNER-DECISION-PACKAGE.md`, `OHB2-WP09-COMPATIBILITY-AND-ENVIRONMENT-VERIFICATION-REPORT.md`, `REV-IND-01-WP-07-INDEPENDENT-REVIEW-REPORT.md` |
| Ignored | `.openhands/`, `.pytest_cache/`, `__pycache__/` and other Python caches |

### 8.2 Files created/modified by this audit

- **Created:** `docs/reviews/OHB2-WP08-SCOPE-RECOVERY-AND-STATUS-AUDIT-REPORT.md` (this report only).
- **Modified:** none of the project implementation, tests, dependencies, lockfiles, CI, Docker, runtime configuration, or Mini App files.
- **Preserved:** all pre-existing tracked/untracked/ignored files, including `.agent/PROGRESS.md`, `bot/app.py`, `tests/test_u04_concurrency.py`, and all poller-concurrency reports.
- **Git publication:** none. No staging, commit, push, PR, merge, deployment, release, or Autopush activation; no reset, clean, force operation, or broad deletion.

---

## 9. Report SHA-256

SHA-256 of this report's content above this section, before this section was appended:

`ba66556eafaf25f76b124fc92390c770eb01c1414b32a8eec6bce50e17bb5162`

The final file SHA-256, including this section, is reported in the task final response and can be recomputed with `sha256sum` on this path.
