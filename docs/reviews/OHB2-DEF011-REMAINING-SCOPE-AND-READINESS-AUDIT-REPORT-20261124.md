# OHB2 — DEF-011 Remaining Scope and Readiness Audit

**Task ID:** `OHB2-DEF011-REMAINING-SCOPE-AND-READINESS-AUDIT`
**Date:** 2026-11-24
**Mode:** audit only; no source, test, documentation, configuration, dependency, CI, Mini App, or Git-history changes.
**Repository:** `/workspace/project/OpenHandBot`
**Final verdict:** **`READY — NEXT IMPLEMENTATION TASK IDENTIFIED`**

> The reported “F-03 Independent Review and Closure” does **not** establish closure of F-03 or DEF-011.
> F-03’s current documentation remediation is present, but it has **no independent review of the
> current snapshot**, and one current correction notice still makes a false `DEF-011-C` claim.
> `DEF-011-A` remains unimplemented and blocked by owner decisions.

---

## 1. Actual baseline and working-tree state

### 1.1 Git identity

| Item | Value |
|---|---|
| Branch | `main` |
| `HEAD` | `2d528633a86472a6a502d7dca5b69ae9f10359ab` |
| `HEAD` tree | `90b62951e53156ac55cffca2f471a0690f21b3d0` |
| Local `origin/main` | `2d528633a86472a6a502d7dca5b69ae9f10359ab` |
| Staged | none |
| Fetch/pull/switch/reset/clean/rebase | **none** |
| Worktree | dirty with pre-existing WP-03/WP-08/WP-09/A4-F5 work; preserved |

The historical reference in the task matches the actual checkout exactly.

### 1.2 Pre-existing changes preserved

Tracked modifications present before this audit:

- `.agent/PROGRESS.md`
- `.github/workflows/ci.yml`
- `bot/attachments.py`
- `bot/db.py`
- `bot/handlers.py`
- `bun.lock` — deleted by the earlier owner-approved WP-09 npm task
- `docs/OPERATIONS_RUNBOOK.md` — prior WP-08 poller documentation repair
- `docs/audits/OHB2-REMEDIATION-MASTER-PLAN.md`
- `package-lock.json`, `package.json`
- `tests/test_attachment_batch_lifecycle_a2.py`
- `tests/test_attachment_staging_a1.py`
- `tests/test_def011_a_option_b_limits.py`
- `tests/test_def011_fs_offload.py`
- `tests/test_doc_code_parity.py`
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
- `docs/reviews/OHB2-WP08-POLLER-CONCURRENCY-DOC-ALIGNMENT-REPORT-20261124.md`
- `docs/reviews/OHB2-WP08-REMAINING-SCOPE-AND-READINESS-AUDIT-REPORT-20261124.md`
- `docs/reviews/OHB2-WP09-COMPATIBILITY-AND-ENVIRONMENT-VERIFICATION-REPORT-20261123.md`
- `docs/reviews/OHB2-WP09-NPM-CANONICAL-LOCKFILE-AND-CI-REPAIR-REPORT-20261123.md`
- `tests/test_a4_f5_expiration_boundary.py`

Ignored `.openhands/`, `.agent/`, Python caches, and `.pytest_cache/` were preserved. No pre-existing
file was reset, cleaned, staged, overwritten, or deleted.

---

## 2. Authoritative DEF-011 scope

The authoritative split is in `docs/audits/OHB2-WP07-DEF011-REMEDIATION-AUDIT.md:43-74`:

| Sub-defect | Original requirement | Original owner |
|---|---|---|
| **DEF-011-A** | Cross-download **quota reservation ledger**; quota checks read actual disk state but never reserve in-flight bytes across concurrent streams | WP-07 |
| **DEF-011-B** | Move blocking filesystem I/O off the asyncio event loop (`_write_to_path`/`fsync`, `_read_head`, reaper sweep, local Bot-API read) | WP-07 |
| **DEF-011-C** | Correct misleading attachment acceptance UX so it says the file is staged locally and not uploaded to OpenHands | WP-01 |

`DEF-011` as a whole is the union of A, B, and C. `D6` (repeated raw cancellation during drain) is a
separate deferred limitation, not an original A/B/C sub-defect.

### 2.1 Current source evidence

| Fact | Current evidence |
|---|---|
| B offload exists | `bot/attachments.py:90` imports `to_thread`; `bot/attachments.py:557,1007,1022,1385` use it; `bot/handlers.py:17,2638` offload the local read. `grep -c to_thread bot/attachments.py` = **6**. |
| A ledger absent | No `reserv`, `in_flight`, `_ledger`, or `reserved_bytes` tokens in `bot/attachments.py`, `bot/handlers.py`, or `bot/db.py` (grep returned only unrelated `preserve` text). |
| C local-only copy exists | `bot/handlers.py:2403-2406` says the file is saved locally and **not uploaded to OpenHands**; it is selected only on `AcceptOutcome.STORED` (`bot/handlers.py:2775-2776`). |
| Option B limits exist | `bot/handlers.py:2507-2518` passes `max_items_per_batch=10` and `max_total_bytes=64 MiB` to the single production `StagingStore`; `max_bytes_per_batch` remains `None`. |
| Schema unchanged | Current schema has **17** tables; no quota/reservation table. |

The presence of Option B limits does **not** implement A. Option B is a separate capacity-limit
implementation; the reservation ledger is still absent.

---

## 3. Full DEF-011 sub-finding disposition

| ID | Exact requirement | Implementation status | Code/test evidence | Publication / review | Owner acceptance | Remaining gap / blocker | Batch-review eligible? |
|---|---|---|---|---|---|---|---|
| **DEF-011-A** | Cross-download quota reservation ledger | **NOT IMPLEMENTED** | No reservation/in-flight accounting; `bot/attachments.py` has no ledger tokens. Option B limits exist but are not a ledger. | Option B implementation report `OHB2-WP07-DEF011-A-IMPLEMENTATION-REPORT.md`; its independent-review attempts returned `INDEPENDENCE_NOT_ESTABLISHED` (`...A-INDEPENDENT-REVIEW-REPORT.md`, `...RETRY...`). | **NOT GRANTED** for A. `D-12` and `OD-04` remain unresolved; Option B is not owner acceptance of A. | **BLOCKED — OWNER DECISION REQUIRED** (`D-12` aggregate-quota policy and `OD-04` concurrency policy). | No |
| **DEF-011-B** | Filesystem I/O off the event loop | **IMPLEMENTED** | `to_thread` ×6 in `bot/attachments.py`; handlers offload; `tests/test_def011_fs_offload.py`: **45 passed**. | Implemented in the current tree; F-03 review at `9d1e13d` verified B evidence, but no standalone B independent review/closure was found. | **NOT GRANTED** for B as a closed item. | No known implementation defect; independent review/owner acceptance still absent. | No — not a standalone reviewed package |
| **DEF-011-C** | Truthful local-only attachment acceptance copy | **IMPLEMENTED — local-only copy** | `bot/handlers.py:2403-2406`, emitted only after `AcceptOutcome.STORED` at `:2775-2776`; `tests/test_wp01_attachment_lifecycle.py` and routing suite pass. | F-03 review at `9d1e13d` found C implemented in code but the F-03 notices were stale; later `2217a25` corrected the proposal/batch notices. | **NOT GRANTED** for DEF-011 as a whole; `OD-01`/`OD-03` remain WP-01-level policy matters. | No code defect found; current F-01 correction notice still falsely says C is NOT IMPLEMENTED (see §5). | No |
| **DEF-011 overall** | A + B + C | **PARTIAL / OPEN** | B and C present; A absent | No independent review of the current snapshot; no owner acceptance | **NOT GRANTED** | A blocked; F-03 current evidence incomplete | No |

### 3.1 DEF-011-A explicit status

`DEF-011-A` was **not** superseded and was **not** implemented by Option B:

- `OHB2-WP07-DEF011-A-IMPLEMENTATION-REPORT.md:272-281` says the task closes **only** the Option B
  implementation work, subject to review; `DEF-011` is not closed.
- The implementation report's §8 explicitly records: **“No reservation ledger / new table”**.
- The current tree contains no ledger tokens.
- The A review attempts explicitly returned `INDEPENDENCE_NOT_ESTABLISHED`; no owner acceptance was
  recorded.

### 3.2 If A later becomes actionable

A is not actionable now because it is blocked by `D-12` (aggregate quota policy) and `OD-04`
(concurrency policy). If the owner authorizes it, the exact boundary should be:

- **File scope:** `bot/attachments.py` and focused tests only; no schema, no `bot/config.py`, no
  `.env.example`, no new dependency, no Mini App, no poller/concurrency change.
- **Mechanism:** an in-process reservation ledger around the existing `store_async` critical section
  (`_accept_lock`), reserving item/byte budget **before** the write and releasing it on rejection,
  failure, cancellation, or finalization.
- **Inertness:** no behavior change when `quota_enabled` is `False`; preserve `D-12` defaults.
- **SQLite safety:** all `Database` access remains on the loop thread; no SQLite from worker threads.
- **Preserved limits:** 3 MiB per-file, Option B 10-item and 64 MiB caps, 17 tables, sequential
  polling and `OD-04`.
- **Acceptance:** concurrent intake cannot exceed the configured cap; every failure/cancellation path
  releases the reservation; no partial file or false `stored`; defaults remain disabled; focused and
  full suites green; no schema/dependency/CI change.

No part of this boundary was implemented in this audit.

---

## 4. F-03 status and closure evidence

### 4.1 What F-03 is

F-03 is the **documentation defect** where historical acceptance/stabilization documents claimed
`DEF-011` was entirely unimplemented, with “0 `to_thread`” and “0 quota ledger”. It is not a code
sub-defect and does not close A/B/C.

### 4.2 Evidence chain

| Artifact | Snapshot | Verdict / status | What it establishes |
|---|---|---|---|
| `docs/audits/OHB2-WP07-DEF011-F03-IMPLEMENTATION-REPORT.md` | Original `52e7789`; later correction appended | Historical `F03_REMEDIATED`; later correction says current `to_thread` count is six and C is implemented | Implementation report, not an independent review |
| `docs/reviews/OHB2-WP07-DEF011-F03-GENUINELY-INDEPENDENT-REVIEW-REPORT.md` | `30dfa0d` | **`F03_REVIEW_PASS`** | A valid historical pass for `30dfa0d` only |
| Same report, appended §12 | Current tree at `9d1e13d` | **`INDEPENDENCE_NOT_ESTABLISHED`** for the current tree | Explicitly says the top pass must not be read as a pass for the current tree |
| `docs/reviews/OHB2-DEF011-F03-INDEPENDENT-REVIEW-REPORT.md` | `9d1e13d` / tree `cd8884be…` | **`FAIL`** | Independence established; material F-01/F-02/F-03 findings remained, including stale `DEF-011-C` notices |
| Commit `2217a25` | Parent `9d1e13d` | **Implementation fixes only** | Corrected F-03 notices, added F-01/F-02/F-03 tests and the current F-03 report |
| `.agent/PROGRESS.md:4909-4915` | Project record | “F-03 is considered closed under the documented interpretation” | A project bookkeeping statement, **not** an independent review or owner acceptance |

### 4.3 Current conclusion for F-03

- **Implementation:** mostly present. The proposal and batch-report notices now mark B implemented, A
  not implemented, C implemented, and DEF-011 open (`OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md:33-49`;
  `OHB2-WP07-FINAL-STABILIZATION-BATCH-REPORT.md:214-221`).
- **Independent review:** **NOT PASSED for the current snapshot.** The only review of `9d1e13d` is
  `FAIL`; the only `F03_REVIEW_PASS` is for `30dfa0d`; no review of `2217a25`/current `HEAD` exists.
- **Owner acceptance:** **none**.
- **Closure:** **NOT ESTABLISHED.** The “reported completion” is not a valid current closure.

---

## 5. Newly confirmed open finding: stale C status in the F-01 correction notice

### `DEF-011-F03-FOLLOW-01` — current correction notice still says C is NOT IMPLEMENTED

- **Severity:** MEDIUM (current documentation contradicting current code)
- **File:** `docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md:312-313`
- **Current text:** the dated correction notice says `DEF-011-A` and `DEF-011-C` remain
  **NOT IMPLEMENTED**.
- **Contradiction:** `bot/handlers.py:2403-2406` contains the local-only acceptance copy and
  `bot/handlers.py:2775-2776` emits it only after `AcceptOutcome.STORED`; the current F-03
  implementation-report correction and proposal/batch notices mark C **IMPLEMENTED**.
- **Why tests miss it:** `tests/test_doc_code_parity.py::test_t5_batch04_f01_report_correction_notice`
  checks the dated notice and preserved historical F-03 row, but does not assert the notice’s C
  status.
- **Historical row:** line 298 (`DEF-011 C — OPEN / NOT IMPLEMENTED`) is a historical row and must
  remain unchanged; only the **current correction notice** is wrong.
- **Disposition:** **OPEN — confirmed documentation defect**, directly related to F-03; not fixed by
  this audit.

---

## 6. Review findings from the F-03 independent review

These are separate review findings, not original A/B/C sub-defects; they are listed to prevent
duplicate identifiers and to record current disposition.

| Review finding | Status / evidence | Current disposition |
|---|---|---|
| **F-01** — `/chat` leaves stale route after confirmed-missing target | `2217a25` changes routing; `tests/test_def011_review_remediation.py` 8 passed; `.agent/PROGRESS.md:4796-4797` | **IMPLEMENTED — NOT INDEPENDENTLY REVIEWED** |
| **F-02** — success-looking acknowledgement before delivery | `2217a25`; same 8 tests; `.agent/PROGRESS.md:4798-4799` | **IMPLEMENTED — NOT INDEPENDENTLY REVIEWED** |
| **F-03** — F-03 notices’ C status wrong | Proposal/batch notices corrected at `2217a25`; F-01 report notice still stale (FOLLOW-01) | **PARTIAL — FOLLOW-01 OPEN** |
| **F-04/F-05** — over-broad target clearing / ambiguous empty result | `2217a25`; `.agent/PROGRESS.md:4802-4803` | **IMPLEMENTED — NOT INDEPENDENTLY REVIEWED** |
| **F-06** — `/cancel` transaction gap | `2217a25`; `test_def011_review_remediation.py::test_cancel_pause_failure_rolls_back_route_and_awaiting` | **IMPLEMENTED — NOT INDEPENDENTLY REVIEWED** |
| **F-07** — selection/submission race | `2217a25`; CAS tests in `test_def011_review_remediation.py` | **IMPLEMENTED — NOT INDEPENDENTLY REVIEWED** |
| **F-08** — expired reply fallback | `2217a25`; two tests in `test_def011_review_remediation.py` | **IMPLEMENTED — NOT INDEPENDENTLY REVIEWED** |
| **F-09** — implementation report stale `to_thread` count | Current F-03 report later correction: six occurrences | **RESOLVED — DOCUMENTATION CORRECTION** |
| **F-10** — proposal diagnosis-hash drift | `OHB2-DEF011-F03-INDEPENDENT-REVIEW-REPORT.md:376-377`; later proposal update is outside F-03 notice | **OPEN — DOCUMENTATION FOLLOW-UP**, not fixed |
| **F-11** — BATCH04 F-03 row stale | Dated correction + T-5 present | **RESOLVED for the F-03 row**, but FOLLOW-01 remains |
| **F-12** — earlier `GENUINELY` report stale for current tree | Earlier report itself says it applies to `30dfa0d` only | **HISTORICAL — NOT A CURRENT CLAIM** |

The F-01/F-02/F-04–F-08 fixes were committed in `2217a25`; they are **not** an independent review and
do not close DEF-011.

---

## 7. Duplicate and superseded findings

| Identifier / report | Disposition | Evidence |
|---|---|---|
| `OHB2-WP07-DEF011-F03-GENUINELY-INDEPENDENT-REVIEW-REPORT.md` | **SUPERSEDED for current snapshot**; valid only for `30dfa0d` | Its own §12 says the pass is not a current-tree pass; `INDEPENDENCE_NOT_ESTABLISHED` for the current tree |
| `OHB2-WP07-DEF011-F03-INDEPENDENT-REVIEW-REPORT.md` | **HISTORICAL FAIL at `9d1e13d`** | Final verdict `FAIL`; F-03 notices C status wrong at that snapshot |
| `OHB2-WP07-DEF011-F03-IMPLEMENTATION-REPORT.md` | Historical `F03_REMEDIATED`, later correction appended | Current correction says six `to_thread`, C implemented, A open |
| `OHB2-WP07-DEF011-F03-STALE-REFERENCE-CORRECTION-REPORT.md` | **Separate stale-reference task**, not F-03 closure | Its own verdict says `DONE` for the stale reference only; DEF-011 remains open |
| `OHB2-F01-F02-F03-DISCRIMINATING-REGRESSION-TESTS-REPORT.md` | **Different `F-03`** (WP-06 / `DEF-009` status-label coverage) | Not this DEF-011 documentation F-03; do not merge |
| `DEF-011-A` Option B report | **Not a ledger implementation** | Explicitly says no reservation ledger; A remains open |
| `.agent/PROGRESS.md:4909` | Project bookkeeping, not review/acceptance | No independent verdict or owner record |

---

## 8. Confirmed open findings and blockers

1. **`DEF-011-A` is open and blocked** by `D-12` and `OD-04`; no ledger exists. Option B is a
   separate implemented capacity-limit change, not A.
2. **F-03 is not closure-eligible**: current snapshot has no passing independent review; the last
   review of `9d1e13d` was `FAIL`; later `2217a25` fixes were not independently reviewed.
3. **`DEF-011-F03-FOLLOW-01`** is a confirmed current documentation defect in the F-01 report’s
   correction notice (`C` still `NOT IMPLEMENTED` while code implements C).
4. **F-10** proposal diagnosis-hash drift remains a separate documentation follow-up; it is not
   expanded here.
5. **DEF-011-B** and **DEF-011-C** are implemented but have no complete independent review or owner
   acceptance for the overall finding.
6. **`D6`** remains deferred; it is not part of A/B/C and is not addressed here.

---

## 9. Batch independent-review eligibility

**No DEF-011 item is currently eligible for the batch independent-review queue.**

- `DEF-011-A` is blocked by owner decisions.
- F-03’s current snapshot has no passing independent review and still has a current stale C notice.
- B/C are implemented but not packaged as an independently reviewable, owner-scoped item.
- The F-01/F-02/F-04–F-08 fixes are committed but not independently reviewed; adding them as a batch
  review would be a new review scope, not a closure of F-03.

No existing queue item is duplicated by this audit.

---

## 10. Recommended next task

**Proposed task ID:** `OHB2-DEF011-F03-STALE-C-CORRECTION` (audit proposal only; not a project-stable
ID).

**Scope (docs/test only):**

1. Add a dated, append-only correction to
   `docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md` after the existing notice,
   stating that `DEF-011-C` is **IMPLEMENTED (local-only copy)** and `DEF-011-A` remains
   **NOT IMPLEMENTED**; preserve the historical rows unchanged.
2. Extend `tests/test_doc_code_parity.py`’s F-01 report check so the current notice cannot claim C
   is not implemented while `bot/handlers.py` contains the local-only acceptance copy and emits it
   only after `STORED`.
3. Do not change runtime code, `bot/app.py`, Mini App, schema, dependencies, CI, `D-12`, or `OD-04`.
4. Do not claim F-03 is closed by this correction; it only removes one confirmed stale claim.

**Acceptance criteria:**

- The F-01 correction notice no longer makes a current `C NOT IMPLEMENTED` claim.
- Historical rows remain byte-for-byte intact.
- The focused parity test fails if the stale C claim returns and passes on the corrected notice.
- Full Python suite remains green; no protected path or unrelated worktree change.
- After this, the next gate is a readiness/independent review of the current F-03 snapshot; that is
  not part of this task.

---

## 11. Commands and tests actually run

Environment: `/tmp/ohb2-wp08-audit-venv`, Python `3.13.15`; dependencies from `requirements-dev.txt`.

| Check | Command | Result | Exit |
|---|---|---|---|
| Focused DEF-011 suite | `python -m pytest -q tests/test_doc_code_parity.py tests/test_def011_fs_offload.py tests/test_def011_a_option_b_limits.py tests/test_def011_review_remediation.py tests/test_f03_status_label_end_to_end.py tests/test_f03_watch_conversation_status_normalization.py` | **90 passed** | 0 |
| C/routing/cleanup suite | `python -m pytest -q tests/test_wp01_attachment_lifecycle.py tests/test_persistent_ready_sticky_routing.py tests/test_telegram_prompt_cleanup_durable.py` | **71 passed** | 0 |
| Full Python suite | `python -m pytest -q` | **3824 passed, 0 failed**, 74 warnings | 0 |
| Diff hygiene | `git diff --check` | clean | 0 |
| Ledger token scan | `grep -nE 'reserv|in_flight|_ledger|reserved_bytes' bot/attachments.py bot/handlers.py bot/db.py` | no ledger tokens | 0 |
| Schema count | in-memory `executescript` of `_init_schema` | **17 tables** | 0 |
| B offload count | `grep -c to_thread bot/attachments.py` | **6** | 0 |

Not run: GitHub Actions/CI, Node/frontend tests, live Telegram/OpenHands/Enzonic calls, and any
independent review. The full suite includes pre-existing uncommitted WP-03/WP-08/WP-09/A4-F5 work;
those changes are not part of this audit.

---

## 12. Git safety and changed files

| Item | Value |
|---|---|
| Branch | `main` (unchanged) |
| `HEAD` | `2d528633a86472a6a502d7dca5b69ae9f10359ab` (unchanged) |
| Tree | `90b62951e53156ac55cffca2f471a0690f21b3d0` (unchanged) |
| Staged | none |
| Commit/push/PR/merge/deploy/release/Autopush | none |
| Reset/clean/force/rebase/switch | none |
| New file | this report only |
| Pre-existing changes | preserved |

### 12.1 Relevant hashes

| Artifact | SHA-256 |
|---|---|
| `bot/attachments.py` | `c1c7b2f43ce1364f11fb7ea8c33ee8cd86d8d6166773f4941adf1882f967eb5f` |
| `bot/handlers.py` | `966d1d5ecac3b67eb02a516b153df87a5fa4fba79e5a51ae978cd27db402e568` |
| `bot/db.py` | `18c350ecb6b138d324820a068b60b6686bb999b3aa8a580746fe3e643720141d` |
| `bot/app.py` | `70870c649b0fa1b9ba3f27bea227b521902ee7395ad6d29011249b4bf465b031` |
| `docs/reviews/OHB2-DEF011-F03-INDEPENDENT-REVIEW-REPORT.md` | `1a4663187873e13b7562feb754541889967cae5ade51e5dc18684af4bfa6a062` |
| `docs/reviews/OHB2-WP07-DEF011-F03-GENUINELY-INDEPENDENT-REVIEW-REPORT.md` | `446c7f0215ebadfded2aebc7805c6e537bd7e37e757c6dfb792dcff19f55b4e6` |
| `docs/audits/OHB2-WP07-DEF011-F03-IMPLEMENTATION-REPORT.md` | `3936498e9cfd04b8e3c9833e951d4fbdcd2afac1a12669ac350844ccfd30e3ac` |
| `docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md` | `7991b8af9c457eb8a65c743ab68ea743e5f00ba76d7aab050d279f13a9f1779f` |
| `docs/reviews/OHB2-WP07-FINAL-STABILIZATION-BATCH-REPORT.md` | `005e55a23e77c7f27b720dc43af99412fd31e8c54377b336fdc75379799e182b` |
| `docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md` | `81333b5831b63a12dbfd9f0d1b681855ae46bae999901ebd0434616a97827ce3` |
| `tests/test_doc_code_parity.py` | `9324d9b2b1b8744682e21b134e09959a59f327005876d95242285741d55305fb` |
| `tests/test_def011_fs_offload.py` | `1e1658536f07b3bd0d842d61798c477ac0b811e8ba6c9ff5476a6dd7eeea5f2c` |
| `tests/test_def011_a_option_b_limits.py` | `72eb395b26479e8127a3b5f9a088193d383509fcc82dc3825e2223a4c72154ef` |
| `tests/test_def011_review_remediation.py` | `9f3210a1a2021f473d1d3c1723f5ecfccb6d25f284621073ea67eb9aa139934a` |
| This report body | see §13 |

---

## 13. Report integrity

**Report body SHA-256 (excluding this footer):** `f55dbf5b9e3fbad3c110b77762f57822945e44043180be8a8bf10f70ecfaa18c`
