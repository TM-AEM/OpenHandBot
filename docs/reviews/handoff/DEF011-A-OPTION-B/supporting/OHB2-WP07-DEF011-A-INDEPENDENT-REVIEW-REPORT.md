# OHB2 — WP-07 / DEF-011-A — Independent Review Report (Option B)

**Review task ID:** `OHB2-WP07-DEF011-A-INDEPENDENT-REVIEW-AND-CLOSURE`
**Timestamp:** 2026-11-21 (review performed after the implementation turn)
**Review type:** review-only. No implementation file, test, configuration, or existing report was modified.
The only artifact created is this report.

**Final verdict:** `INDEPENDENCE_NOT_ESTABLISHED` (see §12). A technical replay was still performed and is
reported in §9–§10 as **non-independent** evidence; it must not be read as an independent PASS.

---

## 1. Reviewer session identity and independence evidence

| Item | Value |
|---|---|
| Agent-server conversations directory | `/var/openhands/conversations/` |
| Conversations present | **exactly one**: `de819568659047d2906ae4b94a4ddc7c` |
| This conversation ID | `de819568-6590-47d2-906a-e4b94a4ddc7c` |
| `parent_conversation_id` | `null` |
| `forked_from_conversation_id` | `null` |
| Initial message of this conversation | the **F-03 review** task (first user turn) |
| Implementation of DEF-011-A Option B | performed in **this same conversation** (the immediately preceding user turn) |
| Working tree | the implementation agent's uncommitted workspace (the candidate lives here) |

**Conclusion:** the reviewer **is** the implementation agent. The same conversation
(`de819568-…`) diagnosed, implemented, and is now asked to review DEF-011-A Option B. There is no second
conversation/session on this agent-server to act as a genuinely separate reviewer, and the candidate is the
implementation agent's own uncommitted working tree.

A fresh clone from `origin` and isolated copies were used for the technical replay (§4, §9), but that does
**not** cure the session-identity problem: the task explicitly forbids reusing the implementation agent's
session and workspace, and explicitly states that a different container alone is not sufficient.

Therefore **independence is NOT established** and no independent PASS can be claimed, regardless of the
technical results below.

---

## 2. Base and candidate revisions

| Item | Value |
|---|---|
| Base revision | `30dfa0d6432cdb8f7787edde38f48fb482b6ced6` (`origin/main`, `main`) |
| Candidate | **uncommitted working-tree changes** on branch `openhands-workspace-11yyMvqKPjTrIZt1RRpWq9` |
| Candidate on `origin/main`? | **No** — `git diff origin/main -- bot/handlers.py bot/attachments.py` is non-empty |
| Candidate code diff | `bot/handlers.py` +17/−2; `bot/attachments.py` +10/−5 (docstrings only) |

The candidate is **not** committed or pushed. It exists only as workspace artifacts.

---

## 3. Candidate provenance and changed-file list

Candidate hashes (working tree at review time):

| File | SHA-256 |
|---|---|
| `bot/handlers.py` | `a2e3f16556fda6ec4e14badda2a3908dcdda56779882d344d2906d035563bd0c` |
| `bot/attachments.py` | `d31320afb4e39dd8cbbd09df45e6a755b24eeca149a115c7ff516a2ec4eb61d4` |
| `tests/test_def011_a_option_b_limits.py` | `63a0033a4e5440ac0e762b77cc58f50da9aa09afa849e97c0d745c4cb795fb13` |
| `docs/audits/OHB2-WP07-DEF011-A-IMPLEMENTATION-REPORT.md` | `682527029c3d6762d6ac0ae7227ca4fcd90e98520d23f1ddd4e7731b76952e22` |

**Actual candidate changed-file list (verified):**

- `bot/handlers.py` (modified — production wiring)
- `bot/attachments.py` (modified — docstrings/comments only)
- `tests/test_def011_a_option_b_limits.py` (new — 16 tests)
- `docs/audits/OHB2-WP07-DEF011-A-IMPLEMENTATION-REPORT.md` (new — implementation report)

This matches the expected list. The workspace also contains **pre-existing, unrelated** changes that are
**not** part of this candidate and were preserved:

- `docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md` (+14/0, F-03 stale-reference correction)
- `tests/test_doc_code_parity.py` (+32/0, pre-existing T-5 test)
- untracked F-03 reports and the DEF-011-A diagnosis brief

No unrelated DEF-011 finding (DEF-011-B/C, DEF-006, D6) was bundled into the candidate. `bot/db.py`,
`bot/config.py`, `.env.example`, `bot/app.py`, and `bot/polling.py` are untouched by the candidate
(verified with `git status --porcelain`).

---

## 4. Production wiring findings

`bot/handlers.py::_attachment_service` (lines 1960–1983) is the **single** production construction site:

```python
from .attachments import (
    MAX_ITEMS_PER_BATCH, MAX_STAGING_TOTAL_BYTES, AttachmentService, StagingStore,
)
...
store = StagingStore(
    db,
    context.bot_data["config"].db_path,
    max_items_per_batch=MAX_ITEMS_PER_BATCH,   # 10
    max_total_bytes=MAX_STAGING_TOTAL_BYTES,   # 64 MiB
)
context.bot_data["attachment_store"] = store
```

Verified:

| Requirement | Result |
|---|---|
| Actual constructor parameters are `max_items_per_batch` / `max_total_bytes` | **Yes** (`StagingStore.__init__`, `bot/attachments.py:497`) |
| Values reach the active production intake path | **Yes** — `handle_attachment` → `_attachment_service` → `AttachmentService.accept` → `store_async` |
| Production service cannot be replaced by an unconfigured instance | **Yes** — `attachment_store` is read/written only in `_attachment_service` (grep: only `:1969`/`:1982`); it is cached and reused |
| Other callers retain `None` defaults | **Yes** — `StagingStore.__init__` defaults `None`; the reaper's internal store is default but only deletes |
| 3 MiB per-file limit active | **Yes** — `max_bytes` default `MAX_ATTACHMENT_BYTES`; `_effective_cap` includes it |
| 15-minute TTL unchanged | **Yes** — `bot/db.py:261` untouched |

The task's descriptive term `max_files_per_batch` correctly maps to the existing parameter
`max_items_per_batch`; no new parameter or config surface was introduced.

---

## 5. Capacity-accounting and concurrency analysis

Traced functions (live candidate):

| Function | Location | Behavior |
|---|---|---|
| `_batch_active_files` | `attachments.py:560` | Counts **actual regular files** on disk for the batch (any item status; missing file ⇒ 0) |
| `staging_total_bytes` | `attachments.py:301` | Sums **all regular files** in the staging root (global; `lstat`, no symlink following; missing root ⇒ 0; read failure propagates) |
| `quota_block` | `attachments.py:583` | `count + extra_items > max_items_per_batch` ⇒ `batch_items` |
| `byte_quota_block` | `attachments.py:598` | per-batch byte cap (unused by Option B) |
| `_effective_cap` | `attachments.py:609` | `min(3 MiB, 64 MiB − staging_total_bytes(root), …)`; `cap <= 0` ⇒ `REJECTED_QUOTA` |
| `_write_to_path` | `attachments.py:623` | Enforces cap during streaming; overflow ⇒ unlink + `_TooLargeError` ⇒ `REJECTED_QUOTA` |
| `store_async` / `_accept_lock` | `attachments.py:876` / `:526`, `:918` | prepare (quota) → write → finalize under one lock |
| `try_mark_attachment_item_stored` | `db.py:1224` | CAS `pending→stored` requiring item `pending` **and** batch `pending` |
| `_remove_file` | `attachments.py:1689` | Deletes only a safe known token; `absent` = idempotent success; symlink/unsafe ⇒ refused |
| `_scan_root_untracked` | `attachments.py:1622` | Counts untracked entries; **does not delete** |

Verified properties:

- **10-file cap:** 10 actual files accepted, 11th `REJECTED_QUOTA` (test).
- **3 MiB cap:** 3 MiB exact accepted, 3 MiB + 1 `REJECTED_SIZE` (test).
- **64 MiB global cap:** shared across batches (`staging_total_bytes(root)` is global); below/at/above
  boundary correct (test).
- **Exact boundaries:** at 64 MiB the next store is rejected before any write; at 64 MiB − 1 a 1-byte file
  is accepted to reach exactly 64 MiB.
- **Concurrency:** `_accept_lock` covers quota-check → write → mark; sequential production polling
  (`bot/polling.py:175-178`) means real concurrency is 1. Concurrent tests: 15 accepts with cap 10 ⇒
  exactly 10 stored; 10 × 30 B with cap 100 ⇒ exactly 3 stored (90 B).
- **Failed/interrupted writes:** `fsync` failure ⇒ `WRITE_FAILED`, no file, 0 bytes, row `pending`;
  partial file after interruption is counted by a fresh store and reclaimed by expiry.
- **Idempotent release:** second sweep deletes 0 and capacity stays 0; `_remove_file` returns `absent` for
  missing files.
- **Restart/reconstruction:** a fresh `StagingStore` accounts from actual files + DB state.
- **No false success:** finalization is a CAS; failures fail closed.

No over-commit path was found under the supported single-process, sequential-dispatch model.

---

## 6. Orphan-file behavior

`staging_total_bytes` counts **all regular files** in the staging root, including untracked/orphan files.
`_scan_root_untracked` reports them and `_remove_file` only deletes files referenced by a known safe token,
so orphans are **never deleted** by this change. This matches the diagnosis and the implementation report.

**Operational consequence (verified, expected):** a pre-existing orphan consumes part of the 64 MiB global
budget and reduces capacity for new attachments. This is an approved-preserved behavior, not a defect; no
cleanup policy was added.

---

## 7. Architecture and lifecycle regression analysis

| Constraint | Result |
|---|---|
| No reservation ledger / new table | **Yes** — no `reserve`/`reservation`/`reserved_bytes` tokens; T11b passes |
| No schema migration / version change | **Yes** — `bot/db.py` untouched; 17 tables (T12 passes) |
| No new worker/queue/process/SQLite owner | **Yes** — no changes to `app.py`/workers |
| No new env/config surface | **Yes** — `bot/config.py` and `.env.example` untouched |
| One-bot + ASGI architecture unchanged | **Yes** |
| D-15/C2 lifecycle unchanged | **Yes** — expiry reclaims staging only; a sentinel file outside the root survives the sweep; batch/item metadata is retained (`expired`/`reaped`) |
| Telegram delivery / exactly-once unchanged | **Yes** — outbox and batch lifecycle untouched |
| F-02 / D6 unchanged | **Yes** — `bot/attachments.py` diff is docstrings only; `store_async` F-02 logic unchanged |

---

## 8. Test review

`tests/test_def011_a_option_b_limits.py` (16 tests) is behavior-driven: it asserts statuses, file counts,
byte totals, and preserved data, not private internals. Coverage:

| Requirement | Test |
|---|---|
| Production wiring (10 / 64 MiB / 3 MiB, cached store) | `test_production_wiring_enables_option_b_limits` |
| Defaults stay `None` | `test_default_store_stays_unenforced` |
| 3 MiB boundary | `test_per_file_3mib_limit_still_enforced` |
| 10 / 11 file boundary | `test_ten_files_accepted_eleventh_rejected` |
| 64 MiB below/at/above | `test_aggregate_64mib_boundary_below_exact_above` |
| Aggregate rejection without partial file | `test_aggregate_rejection_via_accept_leaves_no_file` |
| Cross-batch sharing | `test_aggregate_capacity_is_shared_across_batches` |
| Concurrency | `test_concurrent_intake_cannot_bypass_item_limit`, `…global_byte_limit` |
| Failed write | `test_failed_write_does_not_consume_capacity` |
| Interrupted / restart | `test_interrupted_partial_file_is_accounted_and_reclaimed` |
| Idempotent cleanup | `test_repeated_sweep_is_idempotent_and_releases_once` |
| Repeated intake after release | `test_repeated_intake_after_release` |
| Expiry + C2 | `test_expiry_releases_staging_and_preserves_outside_data` |
| Orphans counted / preserved | `test_orphan_file_counts_toward_limit_and_is_never_deleted` |
| No schema/ledger | `test_no_schema_migration_or_reservation_ledger` |

The tests are deterministic, use `tmp_path` + temporary SQLite, and make no network/Telegram/OpenHands
calls. No existing test was weakened or deleted.

---

## 9. Independent execution results (same-agent isolated replay — NOT independent)

> These runs were executed by the **same agent** that implemented the change, in fresh clones/copies. They
> are recorded for technical completeness only and do **not** satisfy the independence requirement.

Environment: Python **3.13.15**, pytest 9.0.3, on the review container. The base clone was
`git clone https://github.com/TM-AEM/OpenHandBot.git` at `30dfa0d` (verified).

| # | Check | Command | Result | Exit |
|---|---|---|---|---|
| 1 | Candidate-only focused (clean main + 4 candidate files) | `python3 -m pytest tests/test_def011_a_option_b_limits.py -q` | **16 passed** in 1.22s | 0 |
| 2 | Exact workspace snapshot (pre-existing + candidate) | `python3 -m pytest -q` | **3467 passed, 0 failed**, 74 warnings, 173.23s | 0 |
| 3 | Baseline (pre-existing changes, candidate removed) | `python3 -m pytest -q` | **3451 passed, 0 failed**, 74 warnings, 170.99s | 0 |
| 4 | Collection counts | `pytest --collect-only -q` | clean main **3450**; candidate-only **3466** | 0 |
| 5 | Pyflakes | `python3 -m pyflakes bot/ automation/ tools/ main.py tests/` | no output | 0 |
| 6 | Bandit | `python3 -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | **High: 0** | 0 |
| 7 | Frontend | `node --test tests/frontend/*.test.js` | **280 pass, 0 fail** | 0 |
| 8 | Schema/ledger/defaults | `pytest test_T12 test_T11b test_T11` | **3 passed** | 0 |

**Reconciliation of the claimed 3451 → 3467:**

- 3451 = baseline with the pre-existing workspace changes (including the pre-existing T-5 test in
  `tests/test_doc_code_parity.py`).
- 3467 = 3451 + **16** new tests (the candidate). This matches the implementation report exactly.
- The candidate **alone** on clean `main` is 3450 + 16 = **3466**; the +1 difference from 3467 is the
  pre-existing T-5 test, which is **not** part of this candidate. No discrepancy in the claim.

---

## 10. Mutation / negative-control results

Performed in a disposable copy (`/tmp/def011a_review/mut`); the candidate checkout was not altered.

| Mutation | Expected | Observed |
|---|---|---|
| M1 — production wiring omitted | detected | **FAIL** (`test_production_wiring_enables_option_b_limits`) |
| M2 — `max_items_per_batch=None` | detected | **FAIL** (wiring test) |
| M3 — `max_total_bytes=None` | detected | **FAIL** (wiring test) |
| M4 — item limit 10 → 11 | detected | behavior test **passes** (it uses local `OPTION_B_ITEMS`), **wiring test FAILS** ⇒ detected by the suite |
| M5 — total cap 64 MiB → 128 MiB | detected | behavior test **passes** (local `OPTION_B_TOTAL`), **wiring test FAILS** ⇒ detected by the suite |
| M6 — orphans excluded from `_effective_cap` | detected | **FAIL** (`test_orphan_file_counts…`) |
| M7 — capacity release regression (no `unlink`) | detected | **FAIL** (`test_repeated_sweep…`) |
| Control (unmutated) | pass | **PASS** |

All seven mutations are detected by the test suite as a whole. Note (Informational): M4/M5 are detected only
by the production wiring test, because the two behavior tests intentionally use local approved-value
constants; this is a reasonable mechanism-vs-wiring separation, but it means the wiring test is the sole
guard pinning the module constants.

---

## 11. Findings

### Critical
- **F-01 — Independence not established (review-process blocker, not a code defect).**
  The reviewer is the implementation agent: same conversation `de819568-…`, same workspace, same uncommitted
  candidate; no second conversation exists on the agent-server. Per the task, this forbids an independent
  PASS. **Required correction:** run this review from a genuinely separate conversation/session (new
  conversation, `parent=null`, fresh clone) that did not implement the change.

### High
- None found in the technical replay.

### Medium
- None found in the technical replay.

### Low
- **F-02 — Stale "until owner approval" phrasing in `StagingStore.__init__` docstring.**
  `bot/attachments.py:505-508` still says the remaining quotas are disabled "until explicit owner approval
  (D-12 / Option A)". The defaults are still `None`, so behavior is correct, but Option B is now approved
  and activated in production. **Impact:** documentation only; could mislead a future maintainer.
  **Classification:** pre-existing wording, not a regression; optional correction (mention the approved
  production activation). Not blocking.

### Informational
- **F-03 — Behavior tests use local constants.** `test_ten_files_accepted_eleventh_rejected` and
  `test_aggregate_64mib_boundary_below_exact_above` use local `OPTION_B_ITEMS`/`OPTION_B_TOTAL` rather than
  the module constants; the wiring test is the only test that pins the module constants. Acceptable design;
  recorded for completeness.
- **F-04 — Orphan budget consumption** is the approved-preserved behavior; documented in the code and
  report. Not a defect.
- **F-05 — Test helper `_store(db, store, …)` has an unused `db` parameter.** Cosmetic only; pyflakes does
  not flag unused arguments.

No stylistic-only findings were promoted to defects.

---

## 12. Explicit review verdict

# `INDEPENDENCE_NOT_ESTABLISHED`

**Reason:** the review was performed in the same conversation (`de819568-…`) and workspace that implemented
DEF-011-A Option B. No genuinely separate reviewer session is available on this agent-server. The technical
replay is green, but it is **not** an independent review and must not be treated as an independent PASS.

---

## 13. Remaining limitations and recommended next action

- **Technical status (non-independent):** the candidate appears correct. Production wiring passes 10 and
  64 MiB; the 3 MiB per-file cap and 15-minute TTL are preserved; accounting is actual-file based; the lock
  covers the critical section; failures and restarts do not leak capacity; orphans are counted and
  preserved; no schema/ledger/worker/config change. The claimed 3451 → 3467 counts were reproduced exactly.
- **Blocking gap:** independent session identity. The smallest actionable correction is to re-run this
  review from a genuinely separate conversation/session (new conversation, `parent=null`, fresh clone of
  `TM-AEM/OpenHandBot` at `30dfa0d`) that did not implement the change. No code change is needed for that.
- **Closure:** because the verdict is not a PASS, **DEF-011-A is not marked as having passed independent
  technical review**, and the broader **DEF-011 remains open**. No owner decision record was changed.

---

*End of report. The only artifact created by this review is this file.*
