# OHB2 — DEF-011 Remaining Scope and Next-Task Audit

**Task ID:** `OHB2-DEF011-REMAINING-SCOPE-NEXT-TASK-AUDIT`
**Date:** 2026-11-24
**Mode:** audit and planning only; no implementation, no repository modification except this report.
**Repository:** `/workspace/project/OpenHandBot`
**Final verdict:** **`READY — REVIEW IS THE NEXT REQUIRED ACTION`**

> There is no eligible implementation task at this time. `DEF-011-A` is blocked by owner decisions
> `D-12` and `OD-04`. `DEF-011-B` and `DEF-011-C` are implemented with local evidence but lack
> independent review and owner acceptance. The current F-03 documentation snapshot, including the
> stale-C correction, is ready for independent review; it is not owner-accepted and does not close
> `DEF-011`.

---

## 1. Exact repository baseline

| Item | Value |
|---|---|
| Branch | `main` |
| `HEAD` | `2d528633a86472a6a502d7dca5b69ae9f10359ab` |
| `HEAD` tree | `90b62951e53156ac55cffca2f471a0690f21b3d0` |
| Upstream | `origin/main` |
| Local `origin/main` | `2d528633a86472a6a502d7dca5b69ae9f10359ab` |
| Remote state verified? | **NO** — no fetch/pull/network; the local `origin/main` ref is recorded, not a live remote query |
| Staged | none |
| Worktree | dirty with pre-existing WP-03/WP-08/WP-09/A4-F5 work |
| Fetch/pull/switch/reset/clean/stash/rebase | **none** |
| Destructive Git operations | **none** |

The historical baseline supplied in the task still matches the actual checkout: branch `main`,
HEAD `2d528633…`, tree `90b62951…`.

### 1.1 Pre-existing changes preserved

Tracked modifications present before this audit:

- `.agent/PROGRESS.md`
- `.github/workflows/ci.yml`
- `bot/attachments.py`
- `bot/db.py`
- `bot/handlers.py`
- `bun.lock` — deleted by the earlier WP-09 npm task
- `docs/OPERATIONS_RUNBOOK.md` — prior WP-08 poller documentation repair
- `docs/audits/OHB2-REMEDIATION-MASTER-PLAN.md`
- `docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md` — prior F-03 stale-C correction
- `package-lock.json`, `package.json`
- `tests/test_attachment_batch_lifecycle_a2.py`
- `tests/test_attachment_staging_a1.py`
- `tests/test_def011_a_option_b_limits.py`
- `tests/test_def011_fs_offload.py`
- `tests/test_doc_code_parity.py` — prior WP-08 and F-03 parity additions
- `tests/test_f01_reaper_fs_offload.py`
- `tests/test_miniapp_attachment_download_mt2.py`
- `tests/test_repair_plan_01_resource_staging.py`
- `tests/test_repair_plan_02_life01_f2_race.py`
- `tests/test_repair_plan_02_life02_crash_recovery.py`
- `tests/test_wp03_handler_outcome_and_send_guards.py`

Untracked files present before this audit:

- `docs/reviews/OHB2-DEF011-F03-STALE-C-CORRECTION-REPORT-20261124.md`
- `docs/reviews/OHB2-DEF011-REMAINING-SCOPE-AND-READINESS-AUDIT-REPORT-20261124.md`
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

Source: `docs/audits/OHB2-WP07-DEF011-REMEDIATION-AUDIT.md:43-74`.

| Sub-defect | Original requirement | Owner |
|---|---|---|
| **DEF-011-A** | Cross-download quota **reservation ledger**; reserve in-flight bytes/items before writes so concurrent streams cannot overshoot | WP-07 |
| **DEF-011-B** | Move blocking filesystem I/O off the asyncio event loop (`fsync`, `_read_head`, reaper sweep, local Bot-API read) | WP-07 |
| **DEF-011-C** | Truthful attachment acceptance UX: local staging only, not uploaded to OpenHands | WP-01 |

`D6` (repeated raw cancellation during drain) is a separate deferred limitation, not an original
A/B/C sub-defect. `DEF-011` as a whole is the union of A, B, and C.

---

## 3. Status table: A, B, C, and related findings

| ID | Current status | Evidence | Review / acceptance | Remaining action |
|---|---|---|---|---|
| **DEF-011-A** | **NOT IMPLEMENTED — BLOCKED** | No `reserv`/`in_flight`/`_ledger`/`reserved_bytes` accounting in `bot/attachments.py`, `bot/handlers.py`, or `bot/db.py`. Option B limits exist but are not a ledger. | A implementation report `OHB2-WP07-DEF011-A-IMPLEMENTATION-REPORT.md` closes only Option B, subject to review; independent-review attempts returned `INDEPENDENCE_NOT_ESTABLISHED`; no owner acceptance. | Owner decisions `D-12` (aggregate quota policy) and `OD-04` (concurrency policy). |
| **DEF-011-B** | **IMPLEMENTED — EVIDENCE VERIFIED** | `bot/attachments.py:90,557,1007,1022,1385`; `bot/handlers.py:17,2638`; `bot/watcher.py:183`; `bot/app.py:270`; `bot/web/download.py:28,211`. `tests/test_def011_fs_offload.py`: 45 passed. | No standalone B independent review or owner acceptance found. F-03 review at `9d1e13d` verified B code evidence only. | Review/acceptance, not implementation. |
| **DEF-011-C** | **IMPLEMENTED — local-only copy** | `bot/handlers.py:2400-2406`; emitted only at `bot/handlers.py:2775-2776` when `result.outcome is AcceptOutcome.STORED`; `tests/test_wp01_attachment_lifecycle.py` and `test_attachment_batch_lifecycle_a2.py` cover message behavior. | Current F-03 correction notice records C implemented; no independent review or owner acceptance. | Review/acceptance, not implementation. |
| **F-03** | **IMPLEMENTATION PRESENT; CURRENT REVIEW NOT ESTABLISHED** | Current proposal/batch notices record B implemented, A not, C implemented; F-01 report has the 2026-11-24 stale-C correction; parity T-5 passes. | Latest independent review of `9d1e13d` = `FAIL`; earlier `F03_REVIEW_PASS` only for `30dfa0d`; no review of `2217a25`/current snapshot. No owner acceptance. | Independent review of the exact current F-03 snapshot. |
| **DEF-011-F03-FOLLOW-01** | **CORRECTED — AWAITING REVIEW** | `docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md:317-329`; T-5 assertions at `tests/test_doc_code_parity.py:389-424`. | Documentation/test-only correction report exists; no independent review. | Batch review with F-03. |
| **F-01/F-02/F-04–F-08** (review findings) | **IMPLEMENTED — NOT INDEPENDENTLY REVIEWED** | `2217a25`; `tests/test_def011_review_remediation.py`: 8 passed; `.agent/PROGRESS.md:4796-4807`. | No independent review of `2217a25`/current snapshot; no owner acceptance. | Review/acceptance, not a new implementation defect. |
| **F-09** | **RESOLVED — documentation correction** | F-03 implementation report later correction records six `to_thread` occurrences; current code has 6. | Documentation only. | None for implementation. |
| **F-10** | **OPEN — documentation follow-up** | F-03 review §12.4 / `OHB2-DEF011-F03-INDEPENDENT-REVIEW-REPORT.md:376-377`: proposal diagnosis-hash drift due later post-decision update. | Not independently reviewed as a separate item. | Separate documentation follow-up; do not expand this task. |
| **F-11** | **RESOLVED for the F-03 row** | Dated correction and T-5 in BATCH04-F01 report. | Documentation only. | None. |
| **F-12** | **HISTORICAL — not a current claim** | Earlier `GENUINELY` report applies to `30dfa0d`; its own §12 says so. | Historical. | None. |

### 3.1 Why A is blocked, not actionable

`OHB2-WP07-DEF011-REMEDIATION-AUDIT.md:109-116,385-389` records:

- `D-12` has no owner decision authorizing aggregate quota enablement.
- `OD-04` is unresolved; a ledger is only meaningful under concurrency, and the project must not
  introduce concurrency without a decision.
- An always-on ledger would alter `D-12` behavior without owner approval.

Option B (`10` files/`64 MiB`) is already owner-approved as a separate capacity-limit change, but it
explicitly does **not** implement the reservation ledger. A remains a separate blocked item.

### 3.2 If A is later authorized

Exact boundary to use in a future task, not implemented here:

- **Allowed files:** `bot/attachments.py` and focused tests only.
- **Mechanism:** in-process reservation accounting inside the existing `_accept_lock` critical
  section: reserve item/byte budget before the write; release on rejection, write failure,
  cancellation, or finalization.
- **Inertness:** no behavior change when `quota_enabled is False`; preserve `D-12` defaults.
- **SQLite safety:** all `Database` calls remain on the loop thread; no SQLite from worker threads.
- **Preserved limits:** 3 MiB per-file, 10-item and 64 MiB Option B caps, 17 tables, sequential
  polling, and `OD-04`.
- **Acceptance:** no concurrent overshoot; every failure/cancellation path releases its reservation;
  no partial file or false `stored`; default-disabled behavior unchanged; focused/full tests green;
  no schema/dependency/CI/Mini App change.

This boundary is a plan only; it is not authorized or implemented.

---

## 4. B — offload verification

### 4.1 Claimed paths and current code

| Path | Current implementation | Evidence |
|---|---|---|
| Attachment write | `store_async` runs the write in `to_thread.run_sync(_worker)` | `bot/attachments.py:930-1023` |
| Cancellation drain | waits for worker completion via `to_thread.run_sync(_done.wait)` | `bot/attachments.py:1022` |
| Reaper sweep | `sweep_async` offloads `_sweep_fs_tail` | `bot/attachments.py:1373-1390` |
| Opportunistic sweeper | `maybe_sweep_async` awaits `sweep_async` | `bot/attachments.py:1964-1975` |
| Watcher | `await ...maybe_sweep_async()` | `bot/watcher.py:183` |
| Startup reaper | `await reaper.sweep_async(...)` | `bot/app.py:270` |
| Local Bot-API read | `to_thread.run_sync(functools.partial(_read_local_capped, ...))` | `bot/handlers.py:2638` |
| Mini App download | `run_in_threadpool(_read_chunk, ...)` | `bot/web/download.py:211` |

### 4.2 Test evidence

`tests/test_def011_fs_offload.py`: **45 passed** in this audit.

The test module covers loop responsiveness, worker-thread execution, cancellation/partial-file
semantics, reaper offload, SQLite thread affinity, local-read offload, and the absence of a
reservation ledger. It is local test evidence, not independent review.

### 4.3 Remaining B status

No confirmed implementation defect or uncovered offload path was found. B is implemented and
covered by local tests; it is **not** independently reviewed or owner-accepted as a closed item.

---

## 5. C — local-only acceptance copy

### 5.1 Constant and call site

`bot/handlers.py:2403-2406`:

```python
ATTACHMENT_ACCEPTED_TEXT = (
    "تم استلام الملف وحفظه محليًا بشكل مؤقت ✅ — "
    "مش مرفوع لـ OpenHands. ابعت أوامرك (النص المصاحب) خلال 15 دقيقة من أول ملف."
)
```

`bot/handlers.py:2775-2776` selects it only when `result.outcome is AcceptOutcome.STORED`.
`grep` found no other production assignment to this constant.

The message does not claim upload, remote availability, or Mini App delivery. It explicitly says
the file is **not uploaded to OpenHands**.

### 5.2 Tests and correction

- `tests/test_wp01_attachment_lifecycle.py:441-445` asserts the accepted/duplicate messages are
  distinct, includes local-storage wording, includes “not uploaded,” and excludes Mini App wording.
- `tests/test_attachment_batch_lifecycle_a2.py` asserts the accepted text is emitted for `STORED`
  and not for the rejected path.
- The 2026-11-24 append-only correction in
  `docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md:317-329` records C as
  implemented and keeps A not implemented.
- `tests/test_doc_code_parity.py::test_t5_batch04_f01_report_correction_notice` protects the latest
  notice and the historical row; **16 parity tests passed**.

C is implemented; independent review and owner acceptance are still absent.

---

## 6. F-03 and related review findings

### 6.1 F-03 evidence chain

| Artifact | Snapshot | Verdict / use |
|---|---|---|
| `OHB2-WP07-DEF011-F03-IMPLEMENTATION-REPORT.md` | original `52e7789`; later correction | Historical `F03_REMEDIATED`; later correction records six `to_thread`, C implemented |
| `OHB2-WP07-DEF011-F03-GENUINELY-INDEPENDENT-REVIEW-REPORT.md` | `30dfa0d` | `F03_REVIEW_PASS` for that snapshot only |
| Same report, appended §12 | current tree at `9d1e13d` | `INDEPENDENCE_NOT_ESTABLISHED` for current tree; explicitly not a current pass |
| `OHB2-DEF011-F03-INDEPENDENT-REVIEW-REPORT.md` | `9d1e13d` / tree `cd8884be…` | **`FAIL`**; F-01/F-02/F-03 and other material findings |
| `2217a25` | parent `9d1e13d` | Implementation fixes for F-01/F-02/F-03 and related findings; no independent review |
| `OHB2-DEF011-F03-STALE-C-CORRECTION-REPORT-20261124.md` | current worktree | Documentation/test correction; **READY — AWAITING BATCH INDEPENDENT REVIEW** |
| `.agent/PROGRESS.md:4909-4915` | project record | “F-03 is considered closed” — bookkeeping, not independent review or owner acceptance |

**Conclusion:** F-03’s documentation remediation is present and the stale-C correction is guarded,
but the current snapshot has **no passing independent review** and **no owner acceptance**. It is not
valid to treat the project progress note as closure evidence.

### 6.2 Related findings

- F-01/F-02/F-04–F-08 were implemented in `2217a25` and covered by
  `tests/test_def011_review_remediation.py` (8 passed), but not independently reviewed.
- F-09 is a corrected implementation-report count.
- F-10 is a separate proposal-hash documentation follow-up; it is not a DEF-011-A/B/C
  implementation defect and is not expanded here.
- F-11 is resolved for the F-03 row; F-12 is a stale historical report for `30dfa0d`.

---

## 7. Actionability and dependency analysis

| Item | Classification | Why |
|---|---|---|
| `DEF-011-A` | **BLOCKED — OWNER DECISION REQUIRED** | `D-12` and `OD-04` unresolved; no ledger authorized. |
| `DEF-011-B` | **AWAITING INDEPENDENT REVIEW / OWNER ACCEPTANCE** | Implementation and local tests exist; no complete independent review or owner record. |
| `DEF-011-C` | **AWAITING INDEPENDENT REVIEW / OWNER ACCEPTANCE** | Implementation and local tests exist; no complete independent review or owner record. |
| F-03 / FOLLOW-01 | **AWAITING BATCH INDEPENDENT REVIEW** | Correction and parity test complete; latest independent review is `FAIL` at an earlier snapshot and no current review exists. |
| F-10 | **SEPARATE DOCUMENTATION FOLLOW-UP** | Proposal hash drift; not an implementation task for A/B/C. |
| `D6` | **DEFERRED** | Separate limitation; not part of A/B/C. |

There is **no eligible implementation task**:

- A is blocked by owner decisions.
- B and C have no confirmed implementation defect; their missing evidence is review/acceptance.
- F-03 is documentation/test work already complete and awaiting review.
- F-10 is a separate documentation follow-up and is outside this task’s scope.

---

## 8. Next required action

**`OHB2-DEF011-F03-CURRENT-SNAPSHOT-INDEPENDENT-REVIEW`** (proposed review task ID; review-only).

This is **not** an implementation task and must not be disguised as one.

**Exact snapshot to review:** current `HEAD` `2d528633…` / tree `90b62951…`, plus the documented
working-tree F-03 correction files:

- `docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md` (SHA-256
  `cbeb85fd8602d2296e84ce2cdce59622a59b1d15a5334868dbc95cd76444da81`)
- `tests/test_doc_code_parity.py` (SHA-256
  `2f65ea835b87470658edb7296e51b661bab096946eb98035680e414ee5130cef`)
- `docs/reviews/OHB2-DEF011-F03-STALE-C-CORRECTION-REPORT-20261124.md` (SHA-256
  `a9134ec7430fbd5d540c9d11cadc5e9acfd83c3cfde5bd1e691a083c29f1ffd3`)

The reviewer must be genuinely separate from the implementation session and must independently
verify the F-03 notices, the current C status, the historical-row preservation, and the parity test.
The review should not modify runtime code, `OD-04`, `D-12`, A, Mini App, or historical reports.

**Prerequisites:** exact snapshot package/hashes; independent reviewer access; no implementation
changes during review. **Owner approval:** not required to conduct the review; owner acceptance is a
separate later gate.

---

## 9. Tests actually run

| Check | Command | Result | Exit |
|---|---|---|---|
| Targeted F-01 correction test | `pytest tests/test_doc_code_parity.py::test_t5_batch04_f01_report_correction_notice` | **1 passed** | 0 |
| Full parity file | `pytest tests/test_doc_code_parity.py` | **16 passed** | 0 |
| F-01/DEF-011 focused | `pytest tests/test_def011_fs_offload.py tests/test_def011_a_option_b_limits.py tests/test_def011_review_remediation.py tests/test_f03_status_label_end_to_end.py tests/test_f03_watch_conversation_status_normalization.py` | **74 passed** | 0 |
| C/routing/cleanup | `pytest tests/test_wp01_attachment_lifecycle.py tests/test_persistent_ready_sticky_routing.py tests/test_telegram_prompt_cleanup_durable.py` | **71 passed** | 0 |
| Full Python suite | `pytest -q` | **3824 passed, 0 failed**, 74 warnings | 0 |
| Static | `pyflakes tests/test_doc_code_parity.py` | no diagnostics | 0 |
| Compile | `compileall -q tests/test_doc_code_parity.py` | clean | 0 |
| Diff hygiene | `git diff --check` | clean | 0 |

Not run: GitHub Actions/CI, Node/frontend tests, live Telegram/OpenHands/Enzonic calls, independent
review, and owner acceptance. The full suite includes pre-existing uncommitted work; it is not
evidence of CI or independent review.

---

## 10. Git safety and changed files

| Item | Value |
|---|---|
| Branch | `main` (unchanged) |
| `HEAD` | `2d528633a86472a6a502d7dca5b69ae9f10359ab` (unchanged) |
| Tree | `90b62951e53156ac55cffca2f471a0690f21b3d0` (unchanged) |
| Staged | none |
| Commit/push/PR/merge/deploy/release/Autopush | none |
| Reset/clean/force/rebase/switch | none |
| New file | this audit report only |
| Pre-existing changes | preserved |

Relevant hashes:

| Artifact | SHA-256 |
|---|---|
| `bot/attachments.py` | `c1c7b2f43ce1364f11fb7ea8c33ee8cd86d8d6166773f4941adf1882f967eb5f` |
| `bot/handlers.py` | `966d1d5ecac3b67eb02a516b153df87a5fa4fba79e5a51ae978cd27db402e568` |
| `bot/db.py` | `18c350ecb6b138d324820a068b60b6686bb999b3aa8a580746fe3e643720141d` |
| `bot/app.py` | `70870c649b0fa1b9ba3f27bea227b521902ee7395ad6d29011249b4bf465b031` |
| `docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md` | `cbeb85fd8602d2296e84ce2cdce59622a59b1d15a5334868dbc95cd76444da81` |
| `tests/test_doc_code_parity.py` | `2f65ea835b87470658edb7296e51b661bab096946eb98035680e414ee5130cef` |
| `docs/reviews/OHB2-DEF011-F03-STALE-C-CORRECTION-REPORT-20261124.md` | `a9134ec7430fbd5d540c9d11cadc5e9acfd83c3cfde5bd1e691a083c29f1ffd3` |
| `docs/reviews/OHB2-DEF011-F03-INDEPENDENT-REVIEW-REPORT.md` | `1a4663187873e13b7562feb754541889967cae5ade51e5dc18684af4bfa6a062` |
| `docs/reviews/OHB2-WP07-DEF011-F03-GENUINELY-INDEPENDENT-REVIEW-REPORT.md` | `446c7f0215ebadfded2aebc7805c6e537bd7e37e757c6dfb792dcff19f55b4e6` |
| `docs/audits/OHB2-WP07-DEF011-F03-IMPLEMENTATION-REPORT.md` | `3936498e9cfd04b8e3c9833e951d4fbdcd2afac1a12669ac350844ccfd30e3ac` |
| This report body | see §11 |

---

## 11. Report integrity and limitations

- This audit did not modify runtime code, tests, configuration, documentation, or project records
  other than creating this report.
- It did not independently review or accept any DEF-011 item.
- It did not verify GitHub Actions or remote CI.
- It did not fetch or verify live remote state; local `origin/main` is recorded only.
- F-03 and FOLLOW-01 remain unclosed until a genuinely independent review and separate owner
  acceptance.
- `DEF-011` remains **OPEN**; no closure is claimed.

**Report body SHA-256 (excluding this footer):** `1aee21cce3cc7b63d479e485730b1b144060647840f087a1a412555a092ceed9`
