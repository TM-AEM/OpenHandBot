# OHB2 — WP-08 Remaining Scope Reconciliation Report

**Task ID:** `OHB2-WP08-REMAINING-SCOPE-RECONCILIATION`
**Date:** 2026-11-22
**Mode:** planning and audit only; no implementation, test, runtime, dependency, or protected-path changes.
**Repository:** `/workspace/project/OpenHandBot`

---

## 1. Executive verdict

**`RECONCILED_WITH_NOTES`**

The original WP-08 scope is recoverable and has been reconciled against the current working tree,
committed `HEAD`, tests, documentation, owner acceptance, and dependency records.

**WP-08 overall remains `INCOMPLETE`.** The five owner-accepted parity-hardening items are complete
in the current working tree, but they are not committed at `HEAD`, and several owner-gated/deferred
requirements remain open. No additional unblocked WP-08 implementation task is currently eligible.

---

## 2. Baseline branch, HEAD, and working-tree state

### 2.1 Git identity

| Item | Value |
|---|---|
| Branch | `main` |
| HEAD | `0774c9cff923a2ed02da36a1111a283a61600ea5` |
| HEAD tree | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| Upstream | `origin/main` at `0774c9cff923a2ed02da36a1111a283a61600ea5` (local ref; no fetch/pull) |

### 2.2 Pre-existing tracked modifications

The following were present before this audit and were preserved:

- `.agent/PROGRESS.md`
- `README.md`
- `bot/app.py`
- `docs/ZERO_TOUCH_STARTUP.md`
- `docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md`
- `docs/audits/OHB2-WP07-FINAL-STABILIZATION-AUDIT.md`
- `docs/audits/OHB2-WP07-NEW-DEF03-S3-DELIVERY-AND-ACCEPTANCE-RECONCILIATION.md`
- `tests/test_doc_code_parity.py`
- `tests/test_start_script.py`
- `tests/test_u04_concurrency.py`

### 2.3 Pre-existing untracked files

- `docs/audits/OHB2-POLLER-CONCURRENCY-OPTION-A-IMPLEMENTATION-REPORT.md`
- `docs/audits/OHB2-POLLER-CONCURRENCY-OPTION-A-INDEPENDENT-REVIEW-HANDOFF.md`
- `docs/audits/OHB2-POLLER-CONCURRENCY-STRUCTURAL-SAFETY-AUDIT-REPORT.md`
- `docs/audits/OHB2-WP08-OWNER-ACCEPTANCE-RECORD.md`
- `docs/reviews/OHB2-WP07-NAV-OWNER-DECISION-PACKAGE.md`
- `docs/reviews/OHB2-WP08-SCOPE-RECOVERY-AND-STATUS-AUDIT-REPORT.md`
- `docs/reviews/OHB2-WP08-UNBLOCKED-PARITY-HARDENING-IMPLEMENTATION-REPORT.md`
- `docs/reviews/OHB2-WP09-COMPATIBILITY-AND-ENVIRONMENT-VERIFICATION-REPORT.md`
- `docs/reviews/REV-IND-01-WP-07-INDEPENDENT-REVIEW-REPORT.md`

### 2.4 Relevant ignored paths

`.openhands/`, `.pytest_cache/`, `__pycache__/`, and Python cache directories under `bot/`, `tests/`,
and `automation/autopush/` are present and preserved.

### 2.5 Committed vs working-tree distinction

The five accepted parity-hardening changes are **working-tree-only**:

| File | `HEAD` state | Current working tree |
|---|---|---|
| `docs/ZERO_TOUCH_STARTUP.md` | Lacks the two accepted env rows | Contains both accepted rows |
| `tests/test_start_script.py` | Lacks the explicit `anyio` test | Contains the accepted test |
| `tests/test_doc_code_parity.py` | Older whole-document checks | Contains section-scoped checks and canonical ownership |
| `README.md` | Ambiguous `DEFERRED_FEATURES_HIDDEN=True` wording | Current `False` wording |

The committed `HEAD` already contains the earlier WP-08 documentation synchronization, `start.sh`
`anyio` probe, and the original `test_doc_code_parity.py`. The accepted parity-hardening changes are
not in `HEAD`.

The working tree also contains unrelated pre-existing WP-07 changes, including `bot/app.py` using
`concurrent_updates(False)` while committed `HEAD` and `OPERATIONS_RUNBOOK.md` still say `True`.
This audit did not modify that work.

---

## 3. Authoritative scope sources and supersession decisions

### 3.1 Authoritative sources

1. `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md` §E `WP-08` (the corrected authoritative scope).
2. `docs/audits/OHB2-REMEDIATION-MASTER-PLAN.md` WP-08 (original plan; superseded count corrected below).
3. `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md`:
   - `DEF-017` — documentation/runbook drift.
   - `DEF-018` — AI Studio scaffold and missing `anyio` probe.
   - `NEW-DEF-07` — prior-audit factual corrections.
   - `NEW-DEF-08` — missing env/schema parity tests.
4. `docs/reviews/OHB2-REMAINING-REMEDIATION-EXECUTION-REPORT.md` — historical partial implementation.
5. `docs/reviews/OHB2-POST-REMEDIATION-CUMULATIVE-INDEPENDENT-REVIEW.md` §5.7 — historical cumulative review.
6. `docs/reviews/OHB2-WP08-SCOPE-RECOVERY-AND-STATUS-AUDIT-REPORT.md` — historical `INCOMPLETE` audit.
7. `docs/reviews/OHB2-WP08-UNBLOCKED-PARITY-HARDENING-IMPLEMENTATION-REPORT.md` — implementation of the five unblocked items, verdict `DONE_WITH_NOTES`.
8. `docs/audits/OHB2-WP08-OWNER-ACCEPTANCE-RECORD.md` — `OD-WP08-ACCEPT-01`, dated `2026-11-22`.
9. `.agent/PROGRESS.md` — append-only project progress and acceptance record.

### 3.2 Supersession decisions

| Historical statement | Authoritative resolution |
|---|---|
| Master plan says “19 SQLite tables” | **Superseded**: corrected baseline and current schema use **17** tables. |
| `callback_refs` / 18th table as a WP-08 requirement | **Not assumed**: conditional on WP-06 Part 2 and O-5/O-6/O-7. Current schema and Runbook remain 17. |
| Original WP-08 named `test_deploy_manifest.py` / `test_zero_touch_contract.py` as parity locations | **Superseded by accepted item 4**: `tests/test_doc_code_parity.py` is the canonical documentation-parity location. |
| `DEFERRED_FEATURES_HIDDEN=True` README wording | **Superseded by accepted item 5**: current value is `False`; `True` is the optional hiding mode. |
| AI Studio scaffold removal | **Deferred/preserved** by approved frontend-authority decision; no deletion authorized. |
| Mini App changes | **Frozen**; `docs/MINI_APP.md`, `bot/web/*`, and `Config.mini_app_*` remain excluded. |

---

## 4. Requirement-level reconciliation matrix

Status values: `COMPLETE_ACCEPTED`, `COMPLETE_NOT_ACCEPTED`, `PARTIAL`, `OPEN_UNBLOCKED`, `BLOCKED`,
`DEFERRED`, `SUPERSEDED`.

| ID | Requirement and source | Current evidence | Tests / assertions | Historical status | Owner acceptance | Independent review | Classification | Remaining action |
|---|---|---|---|---|---|---|---|---|
| `WP08-R01` | Runbook §3 covers all 20 env vars (baseline WP-08; `DEF-017`) | `docs/OPERATIONS_RUNBOOK.md:41-67`; current parse: 20 documented = 20 config vars. | `test_doc_code_parity.py::test_runbook_documents_every_config_variable` parses §3 and checks exact set, including unexpected entries. 44 focused tests pass. | Historical report called WP-08 partial; this requirement was implemented. | Not among the five accepted items. | Not independently reviewed. | **COMPLETE_NOT_ACCEPTED** | No implementation action. Optional owner acceptance only. |
| `WP08-R02` | Runbook §4 covers all SQLite tables and count (baseline WP-08; corrected 17-table baseline) | `docs/OPERATIONS_RUNBOOK.md:86-92`; current parse: 17 documented = 17 schema tables. | `test_runbook_documents_every_schema_table` checks §4 set/duplicates; `test_runbook_table_count_matches_schema` checks count and list together. | Historical report called WP-08 partial; current baseline implemented. | Not among the five accepted items. | Not independently reviewed. | **COMPLETE_NOT_ACCEPTED** | No implementation action. `callback_refs`/18 remains separate and blocked. |
| `WP08-R03` | Runbook §9 documents `notification_inbox` recovery (baseline WP-08; `DEF-017`) | `docs/OPERATIONS_RUNBOOK.md:392-398` documents persistence, recovery, pending rows, and read-only inspection. | No dedicated assertion; verified by document inspection. | Historical report says added. | Not among the five accepted items. | Not independently reviewed. | **COMPLETE_NOT_ACCEPTED** | No implementation action. |
| `WP08-R04` | Zero-Touch documents remote `DELETE` plus local tombstone (baseline WP-08; `DEF-017`) | `docs/ZERO_TOUCH_STARTUP.md:242-248` explicitly says deletion is remote and local, with irreversible remote delete. | No dedicated assertion; verified by document inspection. | Historical report says corrected. | Not among the five accepted items. | Not independently reviewed. | **COMPLETE_NOT_ACCEPTED** | No implementation action. |
| `WP08-R05` | Zero-Touch `/health`, `/ready`, `/status` accuracy (baseline WP-08; `DEF-017`) | `docs/ZERO_TOUCH_STARTUP.md:52-53` matches the runbook’s liveness/readiness/status semantics. | `test_zero_touch_contract.py` covers startup/DB lifecycle, not route wording. | Historical report says aligned. | Not among the five accepted items. | Not independently reviewed. | **COMPLETE_NOT_ACCEPTED** | No implementation action. |
| `WP08-R06` | Zero-Touch documents `MINI_APP_TRUSTED_PROXIES` (master plan WP-08; `DEF-017`) | `docs/ZERO_TOUCH_STARTUP.md:93`; current config default empty; empty trusts no forwarded header; invalid value raises `ConfigError`. | No dedicated ZERO_TOUCH test; accepted item 1 covers the row. | Historical report noted omission; implementation report added it. | **Accepted item 1**, working-tree only. | Not independently reviewed. | **COMPLETE_ACCEPTED** | Publication/commit not authorized; no implementation action. |
| `WP08-R07` | Zero-Touch documents `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` (master plan WP-08; `DEF-017`) | `docs/ZERO_TOUCH_STARTUP.md:94`; current default `1`/`True`; `0` disables document intake only; text/buttons/Mini App/unsupported-media rejection remain. | No dedicated ZERO_TOUCH test; accepted item 1 covers the row. | Historical report noted omission; implementation report added it. | **Accepted item 1**, working-tree only. | Not independently reviewed. | **COMPLETE_ACCEPTED** | Publication/commit not authorized; final default remains owner-gated. |
| `WP08-R08` | README documents all env vars (baseline WP-08; `DEF-017`) | `README.md:70-92` contains all 20 vars, including both accepted rows. | `test_readme_documents_every_config_variable` parses the README env table and checks exact set. | Historical report says added. | Not among the five accepted items. | Not independently reviewed. | **COMPLETE_NOT_ACCEPTED** | No implementation action. |
| `WP08-R09` | README explains `DEFERRED_FEATURES_HIDDEN=False` and `is_hidden()` behavior (accepted item 5; `NEW-DEF-07`) | `README.md:33-36` says current value `False`; `True` is the optional hiding mode; `bot/features.py:15,20-22` confirms. | No dedicated README flag test; accepted item 5 covers the wording. | Historical report noted ambiguity; implementation report corrected it. | **Accepted item 5**, working-tree only. | Not independently reviewed. | **COMPLETE_ACCEPTED** | Publication/commit not authorized; no implementation action. |
| `WP08-R10` | API_NOTES reconciles OpenAPI versions (baseline WP-08; `DEF-017`) | `docs/API_NOTES.md:81-84` records historical `v1.68.1`, ADR `v1.87.1`, P0 `v1.91.0`, and warns not to treat version as fixed. | Document inspection. | Historical report says reconciled. | Not among the five accepted items. | Not independently reviewed. | **COMPLETE_NOT_ACCEPTED** | No implementation action. |
| `WP08-R11` | `start.sh` makes `anyio` part of the runtime dependency probe (baseline WP-08; `DEF-018`) | `start.sh:56` includes `"anyio"`; `requirements.txt:9` pins `anyio==4.16.0`. | Accepted item 2’s test checks the declaration and install path; `start.sh` itself was committed before the acceptance task. | Historical report says added. | Not explicitly among the five accepted items; accepted item 2 is the test protection. | Not independently reviewed. | **COMPLETE_NOT_ACCEPTED** | No implementation action. Do not overstate acceptance of `start.sh` itself. |
| `WP08-R12` | `tests/test_start_script.py` protects `anyio` contract (accepted item 2; `DEF-018`) | `tests/test_start_script.py:113-127` parses `mods`, checks `anyio`, checks `requirements.txt`, and checks `pip install -r requirements.txt`. | Focused suite: 44 passed; prior mutation M4 removed `anyio` from `start.sh` and this test failed. | Implementation report says added. | **Accepted item 2**, working-tree only. | Not independently reviewed. | **COMPLETE_ACCEPTED** | Publication/commit not authorized. Test is contractual, not live install. |
| `WP08-R13` | NEW-DEF-08 env parity (baseline `NEW-DEF-08`; accepted item 3) | `tests/test_doc_code_parity.py:63-70,96-115` scopes Runbook to §3 and README to its env table; exact set checks include missing and unexpected. | Focused suite: 44 passed. | Historical report says parity added; later audit found whole-document weakness; implementation hardened it. | **Accepted item 3**, working-tree only. | Not independently reviewed. | **COMPLETE_ACCEPTED** | Publication/commit not authorized. |
| `WP08-R14` | NEW-DEF-08 SQLite schema parity (baseline `NEW-DEF-08`; accepted item 3) | `tests/test_doc_code_parity.py:73-78,118-139` extracts §4 count/list, checks set, duplicates, and count/list consistency. | Focused suite: 44 passed. | Historical report says parity added; later audit found whole-document weakness; implementation hardened it. | **Accepted item 3**, working-tree only. | Not independently reviewed. | **COMPLETE_ACCEPTED** | Publication/commit not authorized. 17-table baseline preserved. |
| `WP08-R15` | Canonical parity-test ownership (accepted item 4) | `tests/test_doc_code_parity.py:8-10` states it is the canonical documentation/env/schema parity guard. | Focused suite: 44 passed. | Implementation report records the decision; audit recommended it. | **Accepted item 4**, working-tree only. | Not independently reviewed. | **COMPLETE_ACCEPTED** | Publication/commit not authorized. |
| `WP08-R16` | Original exact parity locations `test_deploy_manifest.py` / `test_zero_touch_contract.py` (master plan WP-08) | Neither file contains env/schema parity assertions; they remain runtime/deploy contract tests. | Inspected: no doc/env/schema parity assertions. | Original plan named these files; later implementation chose a dedicated module. | **Accepted item 4** supersedes the exact location. | Not independently reviewed. | **SUPERSEDED** | No action; do not duplicate assertions. |
| `WP08-R17` | NEW-DEF-07 live-document factual propagation (baseline WP-08 included `NEW-DEF-07`) | Live docs use 17 tables, 20 env vars, remote deletion, readiness, and current API versions; README flag is accepted item 5. | Parity tests and document inspection; no dedicated test for every narrative statement. | Historical audit found stale facts; implementation corrected the operational docs. | Only README flag wording is explicitly accepted (item 5); other live-doc corrections are not individually accepted. | Not independently reviewed. | **COMPLETE_NOT_ACCEPTED** | No implementation action. |
| `WP08-R18` | Preserve AI Studio scaffold (`DEF-018`; WP-08 exclusion) | Root scaffold files remain present; no diff vs `HEAD`. | File inventory. | Historical decision: preserve unless explicitly approved. | Not part of the five accepted items. | Not applicable. | **DEFERRED** | No action without explicit owner authorization. |
| `WP08-R19` | Preserve Mini App freeze (WP-08 exclusion) | `git diff HEAD -- docs/MINI_APP.md bot/web bot/config.py` is empty. | Protected-path check. | Approved project boundary. | Not part of the five accepted items. | Not applicable. | **DEFERRED** | No action. |
| `WP08-R20` | Document `/updates_status` and `/updates_skip` if approved (baseline WP-08 dependency) | No commands exist in source or docs. | Source grep finds no implementation. | Historical report says blocked. | Not accepted. | Not reviewed. | **BLOCKED** | Requires `OD-02` / WP-04 Part 2. |
| `WP08-R21` | Update Runbook if WP-06 adds `callback_refs` (17→18) | `callback_refs` absent; schema and Runbook are 17. | `grep` finds no `callback_refs`; schema parse 17. | Historical report says blocked. | Not accepted. | Not reviewed. | **BLOCKED** | Requires WP-06 Part 2 and O-5/O-6/O-7. Do not assume an 18th table. |
| `WP08-R22` | Document final `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` default after WP-01/`OD-03` | Current code default `True`; docs match current code. | Current parity tests pass. | Historical report says blocked for finalization. | Not accepted beyond current-value docs. | Not reviewed. | **BLOCKED** | Requires WP-01 / `OD-03`; current docs are accurate for current code. |
| `WP08-R23` | Final poller-concurrency documentation (WP-07 / `OD-04`) | Committed `HEAD` and Runbook say `True`; working-tree `bot/app.py` says `False`; mismatch is pre-existing. | No new test run for this; inspect `bot/app.py` and Runbook. | Historical report says blocked. | Not accepted. | Not reviewed. | **BLOCKED** | Requires `OD-04` / WP-07; do not edit uncommitted work. |

### 4.1 Additional authoritative requirements checked

- **`DEF-017`**: all listed Runbook/ZERO_TOUCH/README/API items are represented above.
- **`DEF-018`**: `anyio` probe is present; AI Studio scaffold is preserved; test protection is accepted.
- **`NEW-DEF-07`**: live docs were checked for the superseded 19-table, local-only deletion, old endpoint,
  and feature-flag claims. The only accepted narrative correction is the README flag wording.
- **`NEW-DEF-08`**: env/schema parity is implemented in the canonical module; exact-section checks are
  accepted.
- **Master-plan exact test locations**: superseded by the accepted canonical module decision.

---

## 5. Verification of the five accepted parity-hardening items

| Accepted item | Current verification | Acceptance status |
|---|---|---|
| 1. ZERO_TOUCH §2.3 env rows | Both rows exist at `docs/ZERO_TOUCH_STARTUP.md:93-94`; values match `bot/config.py`. | **Accepted, working-tree only** |
| 2. `anyio` test protection | `tests/test_start_script.py:113-127` checks actual `start.sh` declaration, `requirements.txt`, and `pip install -r requirements.txt`. | **Accepted, working-tree only** |
| 3. Section-scoped env/schema parity | `tests/test_doc_code_parity.py` parses §3/§4; exact set, duplicate, count/list checks. | **Accepted, working-tree only** |
| 4. Canonical ownership | Module docstring at `tests/test_doc_code_parity.py:8-10`. | **Accepted, working-tree only** |
| 5. README flag semantics | `README.md:33-36`; `bot/features.py:15,20-22` confirms `False` and `is_hidden()`. | **Accepted, working-tree only** |

Observed focused test result: **44 passed in 1.69s**, exit **0**.

The acceptance record is limited to these five items. It does not accept the Runbook content itself,
the `start.sh` probe itself, or any owner-gated WP-08 item.

---

## 6. Owner-acceptance scope and qualifications

- **Decision:** `OD-WP08-ACCEPT-01`, `ACCEPT_WITH_NOTES`, dated **2026-11-22**.
- **Accepted scope:** exactly the five items in §5.
- **Implementation verdict:** `DONE_WITH_NOTES`.
- **Full test suite:** not run for the parity-hardening task.
- **`anyio`:** contractual/static check, not a live network installation test.
- **Independent review:** not performed and not claimed.
- **WP-08 overall:** remains `INCOMPLETE`.
- **Other completed WP-08 requirements:** not owner-accepted merely because they exist or have tests.

The acceptance record and `.agent/PROGRESS.md` both preserve these qualifications.

---

## 7. Dependency and blocker matrix

| Dependency | What it blocks | Why blocked | Unblock condition | Part of WP-08 or external? | Safe documentation-only work now? |
|---|---|---|---|---|---|
| `OD-01` + `OD-03` / WP-01 | Final attachment routing/intake default and final ZERO_TOUCH/attachment docs | Owner policy on terminal attachment behavior and intake default is unresolved. | Explicit owner decision, then WP-01 execution. | External owner/WP-01 dependency affecting WP-08 docs. | No: would risk documenting an unapproved default. Current default is documented accurately. |
| `OD-02` / WP-04 Part 2 | `/updates_status` and `/updates_skip` docs | Commands are not implemented; ADR §28.4 policy is unselected. | Owner selects OD-02 option; WP-04 Part 2 implements. | External owner/WP-04 dependency. | No: no commands exist to document as implemented. |
| WP-06 Part 2 / `callback_refs` | 17→18 table parity and Runbook update | `callback_refs` table and design gates are not authorized/implemented; O-5 direction only, O-6 pending, O-7 deferred. | Separate migration authorization plus O-5/O-6/O-7 resolution. | Conditional WP-06 dependency; not a current 17-table WP-08 requirement. | No: adding 18 would invent scope and break the 17-table baseline. |
| `OD-04` / WP-07 | Final poller-concurrency docs | Working-tree `bot/app.py` says `False`; committed Runbook/HEAD says `True`; owner policy unresolved. | Explicit OD-04 decision and WP-07 stabilization. | External owner/WP-07 dependency. | No: a doc-only change would choose a policy without authorization. |
| Mini App freeze | Any Mini App doc/code change | Approved project boundary. | No change authorized by this task; separate owner approval required. | Hard exclusion. | No. |
| AI Studio scaffold preservation | Root scaffold deletion/cleanup | Approved frontend-authority decision; no deletion authorization. | Explicit owner authorization if ever needed. | Hard exclusion. | No. |
| WP-10 / `OD-05` | External infrastructure qualification | External credentials/infrastructure and owner decision unavailable. | OD-05 and external prerequisites. | External; not a local WP-08 requirement. | Not applicable. |

---

## 8. Remaining open and deferred items

### 8.1 Open unblocked

**None.**

All WP-08 requirements that could be implemented without a new owner decision or external prerequisite
are either complete in the working tree or already complete in committed `HEAD`.

### 8.2 Complete but not owner-accepted

These are implemented but outside the five-item acceptance scope:

- Runbook §3 env coverage (`WP08-R01`).
- Runbook §4 schema coverage (`WP08-R02`).
- Runbook §9 `notification_inbox` recovery (`WP08-R03`).
- Zero-Touch remote deletion semantics (`WP08-R04`).
- Zero-Touch `/health`/`/ready`/`/status` (`WP08-R05`).
- README env coverage (`WP08-R08`).
- API_NOTES version reconciliation (`WP08-R10`).
- `start.sh` `anyio` probe (`WP08-R11`).
- General `NEW-DEF-07` live-doc propagation (`WP08-R17`).

They are not “open implementation” items. Optional owner acceptance of them would be a separate
governance decision.

### 8.3 Blocked

- `/updates_*` docs (`WP08-R20`; `OD-02` / WP-04 Part 2).
- `callback_refs`/18-table parity (`WP08-R21`; WP-06 Part 2 / O-5/O-6/O-7).
- Final attachment-intake default docs (`WP08-R22`; WP-01 / `OD-03`).
- Final poller-concurrency docs (`WP08-R23`; WP-07 / `OD-04`).

### 8.4 Deferred/preserved

- AI Studio scaffold (`WP08-R18`).
- Mini App freeze (`WP08-R19`).

### 8.5 Publication status

The five accepted changes are **not committed**. The acceptance record and implementation report are
working-tree artifacts. Commit/push/PR/publication is not authorized by this task and is not an
implementation item; it requires separate explicit owner authorization.

---

## 9. Next executable task recommendation

**None is currently eligible.**

No remaining WP-08 item satisfies all eligibility conditions:

- no authoritative requirement left unimplemented,
- no new owner decision,
- no independent reviewer,
- no protected-path violation,
- isolated from pre-existing work.

The remaining items are either complete-but-not-accepted, blocked by owner decisions/dependencies, or
deferred by approved exclusions. Manufacturing a new documentation/test task would exceed the
authoritative WP-08 scope. A future task may be planned only after an owner resolves `OD-02`, `OD-03`,
`OD-04`, or the WP-06 Part 2 prerequisites, or after separate authorization to publish the accepted
working-tree changes.

---

## 10. Tests and evidence collected

### 10.1 Observed in this audit

Command:

```sh
/tmp/rev-ind-01-wp07-venv/bin/python -m pytest -q \
  tests/test_doc_code_parity.py \
  tests/test_start_script.py \
  tests/test_deploy_manifest.py \
  tests/test_zero_touch_contract.py
```

Result: **44 passed in 1.69s**, exit **0**.

Additional observed checks:

- Current Runbook §3: **20** documented env vars; config: **20**; exact equality.
- Current Runbook §4: documented count **17**, list **17**, schema **17**; exact equality.
- `tests/test_deploy_manifest.py` and `tests/test_zero_touch_contract.py`: no env/schema documentation
  parity assertions; they remain runtime/deploy tests.
- `tests/test_start_script.py`: explicit `anyio` test asserts the `start.sh` tuple, `requirements.txt`
  pin, and `pip install -r requirements.txt`.
- `tests/test_doc_code_parity.py`: exact §3/§4 parsers and list/count checks are present.
- `git diff --check`: exit **0**.

### 10.2 Historical claims not re-run

The implementation report records **44 focused**, **31 additional**, and **62 trusted-proxy tests**,
plus six mutation checks. This audit only re-ran the 44 focused tests. The 31/62 results and mutation
results are historical claims from the implementation report, not re-executed here.

### 10.3 Not run

- Full Python suite: **NOT RUN** (not necessary for this audit; no full-suite claim).
- Node/frontend tests: **NOT RUN**.
- Bandit/pip-audit: **NOT RUN**.
- Production/API calls: **NONE**.

---

## 11. Scope limitations and unresolved ambiguities

1. The accepted parity-hardening changes are **working-tree-only**, not committed at `HEAD`.
2. The owner acceptance is limited to five items; other completed WP-08 requirements are not accepted.
3. The working tree has pre-existing WP-07 changes, including the `concurrent_updates(False)` vs
   committed Runbook `True` mismatch; this is outside this audit's authority.
4. No independent review exists for WP-08.
5. No full-suite verification was performed for the parity-hardening task or this audit.
6. `test_deploy_manifest.py` and `test_zero_touch_contract.py` intentionally do not duplicate the
   canonical parity assertions; the accepted ownership decision makes that a documented choice, not
   an omission.

---

## 12. Exact files changed

- **Created:** `docs/reviews/OHB2-WP08-REMAINING-SCOPE-RECONCILIATION-REPORT.md` (this report only).

No application, test, dependency, lockfile, CI, Docker, runtime, Mini App, or historical report was
modified by this audit.

---

## 13. Protected-path and behavior confirmation

- `git diff --name-status HEAD -- docs/MINI_APP.md bot/web bot/config.py package.json index.html metadata.json src` produced no output.
- No application or test behavior was changed.
- No dependency, lockfile, CI, Docker, runtime, or Mini App change was made.
- No staging, commit, push, PR, merge, deployment, release, or Autopush activation occurred.
- No reset, clean, force operation, broad deletion, or `git add .` / `git add -A` was used.
- No fetch, pull, or branch switch occurred.
- No production calls or credentials were used.

---

## 14. Final Git status

`HEAD` remains `0774c9cff923a2ed02da36a1111a283a61600ea5`; nothing is staged or committed.
The exact final `git status --short --branch` is:

```text
## main...origin/main
 M .agent/PROGRESS.md
 M README.md
 M bot/app.py
 M docs/ZERO_TOUCH_STARTUP.md
 M docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md
 M docs/audits/OHB2-WP07-FINAL-STABILIZATION-AUDIT.md
 M docs/audits/OHB2-WP07-NEW-DEF03-S3-DELIVERY-AND-ACCEPTANCE-RECONCILIATION.md
 M tests/test_doc_code_parity.py
 M tests/test_start_script.py
 M tests/test_u04_concurrency.py
?? docs/audits/OHB2-POLLER-CONCURRENCY-OPTION-A-IMPLEMENTATION-REPORT.md
?? docs/audits/OHB2-POLLER-CONCURRENCY-OPTION-A-INDEPENDENT-REVIEW-HANDOFF.md
?? docs/audits/OHB2-POLLER-CONCURRENCY-STRUCTURAL-SAFETY-AUDIT-REPORT.md
?? docs/audits/OHB2-WP08-OWNER-ACCEPTANCE-RECORD.md
?? docs/reviews/OHB2-WP07-NAV-OWNER-DECISION-PACKAGE.md
?? docs/reviews/OHB2-WP08-OWNER-ACCEPTANCE-RECORD-REPORT.md
?? docs/reviews/OHB2-WP08-REMAINING-SCOPE-RECONCILIATION-REPORT.md
?? docs/reviews/OHB2-WP08-SCOPE-RECOVERY-AND-STATUS-AUDIT-REPORT.md
?? docs/reviews/OHB2-WP08-UNBLOCKED-PARITY-HARDENING-IMPLEMENTATION-REPORT.md
?? docs/reviews/OHB2-WP09-COMPATIBILITY-AND-ENVIRONMENT-VERIFICATION-REPORT.md
?? docs/reviews/REV-IND-01-WP-07-INDEPENDENT-REVIEW-REPORT.md
```

---

## 15. Report SHA-256

SHA-256 of this report's content above this section, before this section was appended:

`2869af903ebabbb87001f840402b08f2e3392676e9fd7e42dae88b638c5fcdaa`

The final file SHA-256, including this section, is reported in the task final response and can be
recomputed with `sha256sum` on this path.
