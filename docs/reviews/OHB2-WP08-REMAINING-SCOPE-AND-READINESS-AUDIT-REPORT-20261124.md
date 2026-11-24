# OHB2 — WP-08 Remaining Scope and Readiness Audit

**Task ID:** `OHB2-WP08-REMAINING-SCOPE-AND-READINESS-AUDIT`
**Date:** 2026-11-24
**Mode:** audit only; no source, test, configuration, dependency, CI, documentation, Mini App, or Git history changes.
**Repository:** `/workspace/project/OpenHandBot`
**Overall verdict:** **`READY — NEXT IMPLEMENTATION TASK IDENTIFIED`**

> WP-08 is **not complete**. Five items are owner-accepted and published. The remaining scope is
> reconstructed below. One newly confirmed, unblocked documentation defect remains: the Runbook
> still says `concurrent_updates(True)` while the current code and tests use
> `concurrent_updates(False)`. Other remaining items are owner-gated or blocked by WP-06 Part 2.

---

## 1. Actual baseline and working-tree state

### 1.1 Git identity

| Item | Value |
|---|---|
| Branch | `main` |
| `HEAD` | `2d528633a86472a6a502d7dca5b69ae9f10359ab` |
| `HEAD` tree | `90b62951e53156ac55cffca2f471a0690f21b3d0` |
| Local `origin/main` | `2d528633a86472a6a502d7dca5b69ae9f10359ab` |
| Fetch/pull/rebase/switch | **not performed** |
| Staged changes | none |
| Index | no staged entries |
| Worktree | dirty; pre-existing changes preserved |

The Notion historical identifiers match the actual current checkout exactly: branch `main`,
HEAD `2d528633...`, tree `90b62951...`.

### 1.2 Pre-existing changes preserved

Tracked modifications present before this audit:

- `.agent/PROGRESS.md`
- `.github/workflows/ci.yml`
- `bot/attachments.py`
- `bot/db.py`
- `bot/handlers.py`
- `bun.lock` — **deleted** by the prior owner-approved WP-09 npm canonicalization task
- `docs/audits/OHB2-REMEDIATION-MASTER-PLAN.md`
- `package-lock.json`
- `package.json`
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

Untracked files present before this audit:

- `docs/reviews/OHB2-WP03-AUD01-DISPLAY-FAILURE-REPAIR-REPORT.md`
- `docs/reviews/OHB2-WP03-REFRESHED-READINESS-AUDIT-REPORT.md`
- `docs/reviews/OHB2-WP03-REVIEW-READINESS-AND-EVIDENCE-AUDIT-REPORT.md`
- `docs/reviews/OHB2-WP09-COMPATIBILITY-AND-ENVIRONMENT-VERIFICATION-REPORT-20261123.md`
- `docs/reviews/OHB2-WP09-NPM-CANONICAL-LOCKFILE-AND-CI-REPAIR-REPORT-20261123.md`
- `tests/test_a4_f5_expiration_boundary.py`

Ignored `.openhands/`, `.pytest_cache/`, `__pycache__/`, and Python caches were preserved.
No pre-existing file was reset, cleaned, stashed, staged, or overwritten.

### 1.3 Committed versus working tree

The accepted WP-08 items are present in **committed `HEAD`**. The uncommitted changes above are
WP-03/WP-09 work plus this audit report; they are not WP-08 changes and are not attributed to WP-08.

---

## 2. Historical baseline reconciliation

| Historical claim | Actual evidence | Reconciliation |
|---|---|---|
| Notion baseline: `main`, HEAD `2d528633...`, tree `90b62951...` | `git rev-parse` returns exactly those values | **MATCH** |
| Five WP-08 items accepted and published via commit `9d1e13d` | `git merge-base --is-ancestor 9d1e13d HEAD` exits `0`; `git branch --contains 9d1e13d` includes `main` | **CONFIRMED** |
| Acceptance record baseline `0774c9c` | `9d1e13d^` is `0774c9cff923a2ed02da36a1111a283a61600ea5` | **CONFIRMED** |
| WP-08 remains incomplete | Five accepted items are limited; R20/R21/R23 remain open/blocked; R23 has a live mismatch | **CONFIRMED** |
| WP-08 before WP-09 | Historical sequence only; current WP-09 work is uncommitted and not part of this audit | **HISTORICAL CONTEXT** |

`9d1e13d` is a published ancestor of `HEAD`, not a dangling or unmerged commit.

---

## 3. Evidence for commit `9d1e13d`

Commit:

- SHA: `9d1e13d72ed7dca8ffd2c6eebff1c6a36400ab17`
- Parent: `0774c9cff923a2ed02da36a1111a283a61600ea5`
- Tree: `cd8884be580cb3e84b9602d8d356201f9579b748`
- Subject: `chore: sync complete local OHB2 remediation, docs, and tests`

WP-08-relevant files changed in that commit:

| File | Change |
|---|---|
| `docs/ZERO_TOUCH_STARTUP.md` | Added accepted §2.3 env rows |
| `README.md` | Corrected accepted feature-flag wording |
| `tests/test_start_script.py` | Added accepted `anyio` contract test |
| `tests/test_doc_code_parity.py` | Added accepted section-scoped parity checks and canonical ownership |
| `docs/audits/OHB2-WP08-OWNER-ACCEPTANCE-RECORD.md` | Published acceptance record |
| `docs/reviews/OHB2-WP08-UNBLOCKED-PARITY-HARDENING-IMPLEMENTATION-REPORT.md` | Published implementation report |

The commit is the publication point for the five accepted items. Its parent is exactly the
acceptance-record baseline, which is strong evidence that the published commit contains the accepted
working-tree implementation rather than an unrelated later state.

---

## 4. Complete WP-08 requirement inventory

Stable IDs from the prior WP-08 reconciliation are reused; no new project IDs were introduced.

| ID | Requirement and source | Current evidence | Verification | Status |
|---|---|---|---|---|
| `WP08-R01` | Runbook §3 documents all 20 env vars (`DEF-017`) | `docs/OPERATIONS_RUNBOOK.md:41-67`; current extraction: 20 documented = 20 config vars | `test_runbook_documents_every_config_variable`; read-only extraction | **IMPLEMENTED — EVIDENCE VERIFIED** |
| `WP08-R02` | Runbook §4 documents all SQLite tables and the 17-table count (`DEF-017`, corrected baseline) | `docs/OPERATIONS_RUNBOOK.md:86-92`; current extraction: 17 list = 17 schema = count 17 | `test_runbook_documents_every_schema_table`; `test_runbook_table_count_matches_schema` | **IMPLEMENTED — EVIDENCE VERIFIED** |
| `WP08-R03` | Runbook §9 documents `notification_inbox` recovery (`DEF-017`) | `docs/OPERATIONS_RUNBOOK.md:395-400`; table exists in `bot/db.py` | Document + schema inspection | **IMPLEMENTED — EVIDENCE VERIFIED** |
| `WP08-R04` | Zero-Touch documents remote deletion plus local tombstone (`DEF-017`) | `docs/ZERO_TOUCH_STARTUP.md:243-251`; remote `DELETE` and tombstone are described | `tests/test_remote_deletion.py`: 68 passed | **IMPLEMENTED — EVIDENCE VERIFIED** |
| `WP08-R05` | Zero-Touch `/health`, `/ready`, `/status` accuracy (`DEF-017`) | `docs/ZERO_TOUCH_STARTUP.md:52-54`; routes documented as liveness/readiness/status | `tests/test_stabilization_f02_f06.py`: 28 passed | **IMPLEMENTED — EVIDENCE VERIFIED** |
| `WP08-R06` | Zero-Touch documents `MINI_APP_TRUSTED_PROXIES` (`DEF-017`) | `docs/ZERO_TOUCH_STARTUP.md:93`; `bot/config.py:38,129-135` default empty, invalid value `ConfigError` | Accepted item 1; source/doc inspection | **OWNER-ACCEPTED — PUBLISHED** |
| `WP08-R07` | Zero-Touch documents `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` (`DEF-017`) | `docs/ZERO_TOUCH_STARTUP.md:94`; `bot/config.py:44,317` default `False`; docs default `0` | Accepted item 1; source/doc inspection | **OWNER-ACCEPTED — PUBLISHED** |
| `WP08-R08` | README documents all env vars (`DEF-017`) | `README.md:70-92`; current README env table has all 20 vars | `test_readme_documents_every_config_variable` | **IMPLEMENTED — EVIDENCE VERIFIED** |
| `WP08-R09` | README explains `DEFERRED_FEATURES_HIDDEN=False` (`NEW-DEF-07`) | `README.md:33-36`; `bot/features.py:15,20-22` confirms `False` and `is_hidden()` behavior | Accepted item 5; source/doc inspection | **OWNER-ACCEPTED — PUBLISHED** |
| `WP08-R10` | `docs/API_NOTES.md` reconciles OpenAPI versions (`DEF-017`) | `docs/API_NOTES.md:81-84` records historical `v1.68.1`, ADR `v1.87.1`, P0 `v1.91.0`, and warns against treating it as fixed | Document inspection | **IMPLEMENTED — EVIDENCE VERIFIED** |
| `WP08-R11` | `start.sh` includes `anyio` in the runtime dependency probe (`DEF-018`) | `start.sh:56` includes `"anyio"`; `requirements.txt:9` pins `anyio==4.16.0` | Accepted item 2 test; source inspection | **IMPLEMENTED — EVIDENCE VERIFIED** |
| `WP08-R12` | `tests/test_start_script.py` protects the `anyio` contract (accepted item 2) | `tests/test_start_script.py:113-127` parses the actual `mods` tuple, checks `requirements.txt`, and checks `pip install -r requirements.txt` | 14 start-script tests pass; accepted item 2 | **OWNER-ACCEPTED — PUBLISHED** |
| `WP08-R13` | Section-scoped env parity (accepted item 3) | `tests/test_doc_code_parity.py:63-70,96-115`; exact missing/unexpected sets | 15 parity tests pass; accepted item 3 | **OWNER-ACCEPTED — PUBLISHED** |
| `WP08-R14` | Section-scoped SQLite schema parity (accepted item 3) | `tests/test_doc_code_parity.py:73-78,118-139`; exact set, duplicates, and count/list consistency | 15 parity tests pass; accepted item 3 | **OWNER-ACCEPTED — PUBLISHED** |
| `WP08-R15` | Canonical parity-test ownership (accepted item 4) | `tests/test_doc_code_parity.py:8-10` states canonical ownership | Accepted item 4; source inspection | **OWNER-ACCEPTED — PUBLISHED** |
| `WP08-R16` | Original exact parity locations `test_deploy_manifest.py` / `test_zero_touch_contract.py` (master plan) | Neither file contains env/schema parity assertions; they remain runtime/deploy tests | Accepted item 4 supersedes the location; both files pass | **NOT APPLICABLE — WITH EVIDENCE** |
| `WP08-R17` | `NEW-DEF-07` live-document factual propagation | Current live docs show 17 tables, 20 env vars, remote deletion, readiness, and current API versions | Doc inspection; parity tests; R23 is the remaining concurrency wording exception | **IMPLEMENTED — EVIDENCE VERIFIED** (except R23) |
| `WP08-R18` | Preserve AI Studio scaffold (`DEF-018` exclusion) | Other scaffold files remain; `bun.lock` was deleted by the later owner-approved WP-09 npm canonicalization task | Current worktree + WP-09 report | **NOT APPLICABLE — WITH EVIDENCE** (superseded by later approved change) |
| `WP08-R19` | Preserve Mini App freeze | `git diff HEAD -- docs/MINI_APP.md bot/web bot/config.py` is empty | Protected-path check | **IMPLEMENTED — EVIDENCE VERIFIED** |
| `WP08-R20` | Document `/updates_status` / `/updates_skip` if approved | No implementation in `bot/`; no live command docs; only historical/design documents mention them | Source/doc grep | **BLOCKED — OWNER DECISION REQUIRED** (`OD-02` / WP-04 Part 2) |
| `WP08-R21` | Update Runbook if WP-06 adds `callback_refs` (17→18) | `callback_refs` absent from `bot/` and `tests/`; schema and Runbook remain 17 | `grep` + schema extraction | **BLOCKED — OWNER DECISION REQUIRED** (WP-06 Part 2 / O-5/O-6/O-7) |
| `WP08-R22` | Final `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` default docs | Code default `False`; `.env.example=0`; README/Runbook/ZERO docs all say `0`/disabled | Source/doc inspection; `OD-WP01-OD01-OD03-01` Option A | **IMPLEMENTED — EVIDENCE VERIFIED** |
| `WP08-R23` | Final poller-concurrency documentation (WP-07 / `OD-04`) | `bot/app.py:101` uses `.concurrent_updates(False)`; `tests/test_u04_concurrency.py` asserts `== 1`; `docs/OPERATIONS_RUNBOOK.md:141` still says `concurrent_updates(True)` | 11 concurrency tests pass; direct source/doc extraction | **INCOMPLETE — CONFIRMED DOCUMENTATION GAP** |

### 4.1 Source counts used by the inventory

Read-only extraction on the current worktree:

```text
config_env 20 runbook_env 20 env_missing [] env_extra []
schema_tables 17 runbook_count 17 runbook_list 17 schema_missing [] doc_extra []
poller_code_false True
poller_runbook_true True
```

This independently confirms the env/schema parity and the poller mismatch.

---

## 5. Verification of the five owner-accepted items

| Accepted item | Current evidence in committed `HEAD` | Later change? | Status |
|---|---|---|---|
| 1. ZERO_TOUCH §2.3 env rows | Rows at `docs/ZERO_TOUCH_STARTUP.md:93-94`; current file hash equals `HEAD`; values match `bot/config.py` (`empty` and `False`) | None in this file since `9d1e13d` | **OWNER-ACCEPTED — PUBLISHED** |
| 2. `anyio` test protection | `tests/test_start_script.py:113-127`; current file hash equals `HEAD`; test passes | None in this file since `9d1e13d` | **OWNER-ACCEPTED — PUBLISHED** |
| 3. Section-scoped env/schema parity | `tests/test_doc_code_parity.py`; §3/§4 exact parsers and count/list checks; 15 tests pass | Later additive WP-07 F-03 tests; accepted §3/§4 checks unchanged | **OWNER-ACCEPTED — PUBLISHED** |
| 4. Canonical parity ownership | Module docstring at `tests/test_doc_code_parity.py:8-10` | Later additive tests do not remove ownership | **OWNER-ACCEPTED — PUBLISHED** |
| 5. README feature-flag accuracy | `README.md:33-36`; `bot/features.py` confirms `False` | None in this file since `9d1e13d` | **OWNER-ACCEPTED — PUBLISHED** |

### 5.1 Acceptance applicability

`OD-WP08-ACCEPT-01` (2026-11-22) applies to exactly these five items, not to all of WP-08. The
acceptance record is in `docs/audits/OHB2-WP08-OWNER-ACCEPTANCE-RECORD.md` and was published in
`9d1e13d`. The current committed files still contain the accepted behavior. The later parity-test
additions are outside the five-item acceptance scope but do not modify the accepted contracts.

No accepted item is reopened merely because no independent review exists.

---

## 6. Remaining incomplete and blocked items

### 6.1 `WP08-R23` — confirmed documentation gap

**Exact requirement:** final poller-concurrency documentation must match actual startup/polling
behavior.

**Evidence:**

- `bot/app.py:101` contains `.concurrent_updates(False)`.
- `tests/test_u04_concurrency.py:113-116` asserts `app.concurrent_updates == 1` and
  `app._update_processor.max_concurrent_updates == 1`.
- `docs/OPERATIONS_RUNBOOK.md:141` still says **`concurrent_updates(True)`**.
- The poller implementation report itself records this as a known stale line:
  `docs/audits/OHB2-POLLER-CONCURRENCY-OPTION-A-IMPLEMENTATION-REPORT.md:390-392`.

**What remains:** update the live Runbook wording to describe the current `False`/sequential
behavior, and preferably add a narrow documentation-parity assertion that prevents the literal
`concurrent_updates(True)` from returning to that section without a code change.

**Authorization:** this is a documentation-only correction to match existing code and tests. It does
not require selecting a new concurrency policy. Changing the code or enabling intra-batch concurrency
remains blocked by `OD-04`.

**Can proceed without owner clarification:** **yes**, for the documentation correction only.

### 6.2 `WP08-R20` — `/updates_status` and `/updates_skip`

- No implementation exists in `bot/`.
- Only historical/design documents mention the commands.
- Blocked by `OD-02` / WP-04 Part 2.
- Not actionable without an owner decision and subsequent WP-04 Part 2 implementation.

### 6.3 `WP08-R21` — `callback_refs` / 18-table variant

- `callback_refs` is absent from `bot/` and `tests/`.
- Current schema and Runbook are 17 tables.
- Blocked by WP-06 Part 2 and the O-5/O-6/O-7 design gates.
- Do not add an 18th table or document one as current.

### 6.4 `WP08-R22` — final attachment default

- `bot/config.py` defaults to `False`.
- `.env.example` and all three operator docs document `0`/disabled.
- `OD-WP01-OD01-OD03-01` records Option A (`False`).
- This is implemented and verified for the current baseline; WP-01 Stage 1 remains in its own batch
  review queue and was not reopened here.

### 6.5 `WP08-R18` and `WP08-R19` — preservation constraints

- Mini App freeze is intact: no diff for `docs/MINI_APP.md`, `bot/web/`, or `bot/config.py`.
- AI Studio scaffold is not fully unchanged: `bun.lock` was removed by the later owner-approved WP-09
  npm task. Other scaffold files remain. This audit does not reopen WP-09 or treat its approved
  removal as a WP-08 regression.

---

## 7. Newly confirmed findings

### `WP08-FIND-01` — Runbook poller concurrency text contradicts current code

- **Severity:** MEDIUM (operational documentation; can mislead operators and reviewers)
- **File:** `docs/OPERATIONS_RUNBOOK.md:141`
- **Actual code:** `bot/app.py:101` `.concurrent_updates(False)`
- **Actual test:** `tests/test_u04_concurrency.py:113-116`
- **Historical note:** `docs/audits/OHB2-POLLER-CONCURRENCY-OPTION-A-IMPLEMENTATION-REPORT.md:390-392`
  explicitly records the stale line.
- **Impact:** an operator reading the Runbook would believe concurrency is enabled when the
  Application builder enforces one update at a time. No data-loss or security impact was found.
- **Fix status:** not implemented in this audit (audit-only).

No other confirmed documentation/code mismatch was found in the checked WP-08 surface.

---

## 8. Commands executed and results

### 8.1 Environment

- Python: `3.13.15` in `/tmp/ohb2-wp08-audit-venv`
- Dependencies: `requirements-dev.txt`, install exit `0`
- Node: not required for this WP-08 audit; no Node command was run

### 8.2 Tests

```sh
python -m pytest -q tests/test_doc_code_parity.py \
  tests/test_start_script.py tests/test_deploy_manifest.py \
  tests/test_zero_touch_contract.py
```

Result: **45 passed**, exit `0`.

```sh
python -m pytest -q tests/test_u04_concurrency.py \
  tests/test_wp07_route_renewal_and_policy.py \
  tests/test_stabilization_f02_f06.py
```

Result: **41 passed**, 2 warnings, exit `0`.

```sh
python -m pytest -q tests/test_remote_deletion.py
```

Result: **68 passed**, exit `0`.

```sh
python -m pytest -q
```

Result: **3823 passed, 0 failed, 74 warnings**, exit `0`.

The full-suite run includes the pre-existing uncommitted WP-03/A4-F5 and WP-09 work; those changes
are not part of this audit.

### 8.3 Read-only documentation checks

- Config env vars: **20**; Runbook §3: **20**; missing/extra: **none**.
- Schema tables: **17**; Runbook §4 list: **17**; count: **17**; missing/extra: **none**.
- `bot/app.py` contains `.concurrent_updates(False)`: **true**.
- `docs/OPERATIONS_RUNBOOK.md` contains `concurrent_updates(True)`: **true** (confirmed mismatch).
- `git diff --check`: exit `0`.
- `git merge-base --is-ancestor 9d1e13d HEAD`: exit `0`.
- `git diff HEAD -- docs/MINI_APP.md bot/web bot/config.py`: empty.

### 8.4 Not run

- Node/frontend tests: not relevant to this WP-08 audit and not run.
- Live Telegram, OpenHands, Enzonic, or production calls: **none**.
- Independent review: **not performed**; this audit is not an independent review.

---

## 9. Verified facts versus historical claims

### Verified in this audit

- Current `HEAD`, tree, and Notion baseline match.
- `9d1e13d` is an ancestor of `HEAD`, is on `main`, and its parent is the acceptance baseline
  `0774c9c`.
- The five accepted items are present in committed `HEAD`; the accepted files are unchanged since
  `9d1e13d` except for later additive parity tests.
- Runbook §3/§4 env/schema parity is exact (20/20 and 17/17).
- `anyio` is in `start.sh` and protected by `test_start_script.py`.
- `README` flag wording matches `bot/features.py`.
- Remote deletion and readiness tests pass.
- `bot/app.py` uses `False`; Runbook says `True`; this is a real documentation gap.
- Mini App and `bot/config.py` have no diff versus `HEAD`.

### Historical claims not independently re-verified

- The original WP-08 implementation report's 31 and 62 additional test counts and six mutation
  results are historical claims; this audit ran its own focused/full tests but did not reproduce
  those exact mutation runs.
- The Notion statement that the five items were published through `9d1e13d` is supported by commit
  ancestry and file contents, not by a live Notion API read.
- No GitHub Actions run was queried; CI status is outside this audit.
- No independent review exists for WP-08; the historical owner acceptance is not a technical review.

---

## 10. Single most appropriate next actionable task

**Proposed task ID:** `OHB2-WP08-POLLER-CONCURRENCY-DOC-ALIGNMENT` (audit proposal only; not a
project-stable ID).

**Scope:**

1. Update `docs/OPERATIONS_RUNBOOK.md:139-146` so the live text says
   `concurrent_updates(False)` and describes the current sequential `Application` behavior.
2. Keep the existing distinction that `TelegramPoller.dispatch_and_wait` is sequential; do not claim
   new intra-batch concurrency.
3. Add a narrow documentation-parity regression assertion, preferably in
   `tests/test_doc_code_parity.py`, so the Runbook section cannot silently revert to
   `concurrent_updates(True)` while `bot/app.py` remains `False`.
4. Do not change `bot/app.py`, `tests/test_u04_concurrency.py`, schema, Mini App, or `OD-04` policy.

**Why it is actionable now:** the code and tests already establish the current behavior; this is a
truthful documentation/test correction, not a new architecture or concurrency-policy decision.

**Acceptance criteria:** Runbook no longer says `concurrent_updates(True)` in the live polling
description; a focused test fails if the literal reappears while code remains `False`; focused and
full Python tests pass; no protected-path changes.

---

## 11. Batch independent-review queue

**No new WP-08 item qualifies for the batch independent-review queue in this audit.**

- The five accepted items are already owner-accepted and published; they are not reopened.
- `WP08-R20` and `WP08-R21` are blocked.
- `WP08-R23` is an unimplemented documentation gap; it must be fixed first.
- `WP08-R22` is implemented but overlaps WP-01 Stage 1, which is already in the queue; do not
  duplicate it.
- WP-08 as a whole is not a ready review package because R23 and the blocked items remain.

---

## 12. Final Git state

| Item | Value |
|---|---|
| Branch | `main` |
| `HEAD` | `2d528633a86472a6a502d7dca5b69ae9f10359ab` |
| Tree | `90b62951e53156ac55cffca2f471a0690f21b3d0` |
| Staged | none |
| New file | this audit report only |
| Pre-existing changes | preserved |
| Commit/push/PR/merge/deploy/release/Autopush | **none** |
| Reset/clean/force/branch switch | **none** |

No application, test, configuration, dependency, CI, documentation, Mini App, or `.openhands/` state
was modified by this audit.

---

## 13. Evidence artifact hashes

| Artifact | SHA-256 |
|---|---|
| `docs/ZERO_TOUCH_STARTUP.md` | `00fd5fcf9d01f6f771617efa13233517212f2a04b843060bd2fe3e918c3b1f61` |
| `README.md` | `7bc350640e69f3c1dd7e705e33e888c511ece6b98f881734d4cbbfe2bc718750` |
| `tests/test_start_script.py` | `17ef514f6b0b413d108a5f53f7ba293d07665b1a1dee7a5e923027f6a045353d` |
| `tests/test_doc_code_parity.py` | `12caa03d08ffd85551b77caa2ceccb01b7bb3a814fe77a38f4499aa7f565e000` |
| `docs/audits/OHB2-WP08-OWNER-ACCEPTANCE-RECORD.md` | `a24efc5793465e841ad67c50de5f6b245f504bebab0b3656e0dd113df85dccc1` |
| `docs/reviews/OHB2-WP08-UNBLOCKED-PARITY-HARDENING-IMPLEMENTATION-REPORT.md` | `945c35d66dcd5d1b89f8c579c8ef9ac260183fb5f562f6488635aeba58543e07` |
| `docs/reviews/OHB2-WP08-SCOPE-RECOVERY-AND-STATUS-AUDIT-REPORT.md` | `0a7322e214326b9078fae827b639c32fd7ac204d3ee3d36de1541273747722e3` |
| `docs/reviews/OHB2-WP08-REMAINING-SCOPE-RECONCILIATION-REPORT.md` | `47b467440c51cee4b9b6ef30117265baf36d9ba5ca06603f8aa93563868d6b7f` |
| `bot/app.py` | `70870c649b0fa1b9ba3f27bea227b521902ee7395ad6d29011249b4bf465b031` |
| `bot/config.py` | `30f51b3dc8c1f2de804ac8943c56038674fa6afe36adb531eb778ee5e9958b2d` |
| `docs/OPERATIONS_RUNBOOK.md` | `709c4d44c6de6ee5930d234593a78fea24cb62b4a0a62ebc236602d4a97a4f7b` |
| `tests/test_u04_concurrency.py` | `e78de07e026f30f53b4958d20368097a85268cd2239a2e220944e023fa7c6404` |
| `tests/test_wp07_route_renewal_and_policy.py` | `dea9a91feece46f0952bfe73e674f551c7fee99c9016b7e72a4a1e8db2874bbf` |
| This report body | see §14 (body hash) |

---

## 14. Report integrity

**Report body SHA-256 (excluding this footer):** `45a0e81a38f159297994cfd0d8f7e403ffaa5818664357b512d8359921ff0b1c`
