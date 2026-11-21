# OHB2 — WP-07 / DEF-011-A — Enable Attachment Capacity Limits (Option B) — Implementation Report

**Task ID:** `OHB2-WP07-DEF011-A-ENABLE-ATTACHMENT-CAPACITY-LIMITS`
**Date:** 2026-11-21
**Approved policy:** **Option B** (explicit owner authorization in this task)
**Status:** `A_IMPLEMENTATION_DONE` (see §13).

---

## 1. Approved values

| Task name | Effective production value | Existing mechanism used |
|---|---|---|
| `max_files_per_batch` | **10 files per attachment batch** | `StagingStore(max_items_per_batch=10)` → `quota_block()` |
| `max_total_bytes` | **64 MiB = 67 108 864 bytes** (global staged storage) | `StagingStore(max_total_bytes=64*1024*1024)` → `_effective_cap()` / `staging_total_bytes()` |
| per-file (unchanged) | **3 MiB = 3 145 728 bytes** | `MAX_ATTACHMENT_BYTES` (always on) |
| staging TTL (unchanged) | **15 minutes, fixed** | `ATTACHMENT_BATCH_TTL` |

The task's name `max_files_per_batch` maps to the existing parameter **`max_items_per_batch`** (the
existing API and tests use "items"); no new parameter or config surface was introduced. The values are
reused from the existing module constants `MAX_ITEMS_PER_BATCH` (10) and `MAX_STAGING_TOTAL_BYTES`
(64 MiB) — a single source of truth.

---

## 2. Baseline (recorded before editing)

| Item | Value |
|---|---|
| Branch | `openhands-workspace-11yyMvqKPjTrIZt1RRpWq9` |
| `HEAD` | `30dfa0d6432cdb8f7787edde38f48fb482b6ced6` |
| `origin/main` | `30dfa0d…` (in sync) |
| Pre-existing tracked modifications | `docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md` (+14/0), `tests/test_doc_code_parity.py` (+32/0) |
| Pre-existing untracked | `docs/audits/OHB2-WP07-DEF011-A-DIAGNOSIS-AND-DECISION-BRIEF.md`, `docs/audits/OHB2-WP07-DEF011-F03-STALE-REFERENCE-CORRECTION-REPORT.md`, `docs/reviews/OHB2-WP07-DEF011-F03-GENUINELY-INDEPENDENT-REVIEW-REPORT.md` |
| Pre-existing ignored | `.openhands/`, `.agent/` (preserved) |
| `bot/attachments.py` SHA-256 | `b98d561f0ba0ab27dea4e6bedee7955f68f1f6fa85a39fa81afe8aeb4d818356` |
| `bot/handlers.py` SHA-256 | `40dd8902595c1a63875f8c9d37d4fed4a454be15e1390e5386dcfa9bce058014` |
| `bot/db.py` SHA-256 | `205f1363aaf0b1f8173b74285e263891d333928ba480d478b6b525d4369c694b` |

All pre-existing changes and artifacts were preserved. Nothing was reset, cleaned, stashed, or discarded.

### 2.1 Call chain reconfirmed before editing

| Element | Location (live) |
|---|---|
| Production `StagingStore` construction | `bot/handlers.py:1960` `_attachment_service()` → `StagingStore(db, config.db_path)` (`:1966`), cached in `bot_data["attachment_store"]` |
| `MAX_ATTACHMENT_BYTES` (3 MiB) | `bot/attachments.py:105` |
| `MAX_ITEMS_PER_BATCH` (10, reference) | `bot/attachments.py:111` |
| `MAX_STAGING_TOTAL_BYTES` (64 MiB, reference) | `bot/attachments.py:112` |
| `_batch_active_files` (per-batch actual-file count/bytes) | `bot/attachments.py:560` |
| `staging_total_bytes` (global actual bytes) | `bot/attachments.py:301` |
| `_accept_lock` (serializes check→write→mark) | `bot/attachments.py:526`, used at `:918` |
| `dispatch_and_wait` (sequential polling) | `bot/polling.py:175-178` |
| Staging expiry / deletion | `bot/db.py:261` (`ATTACHMENT_BATCH_TTL`), `bot/attachments.py:1222` (`AttachmentReaper`) |
| Orphan discovery/accounting | `bot/attachments.py:1617` `_scan_root_untracked` (reports, does not delete); `staging_total_bytes` counts all regular files |
| Production wiring | `bot/handlers.py:1960-1983` |

---

## 3. Implementation

### 3.1 `bot/handlers.py` — production wiring (the only behavioral change)

`_attachment_service()` now passes the approved limits to the single production store:

```python
from .attachments import (
    MAX_ITEMS_PER_BATCH,
    MAX_STAGING_TOTAL_BYTES,
    AttachmentService,
    StagingStore,
)
...
store = StagingStore(
    db,
    context.bot_data["config"].db_path,
    max_items_per_batch=MAX_ITEMS_PER_BATCH,      # 10
    max_total_bytes=MAX_STAGING_TOTAL_BYTES,      # 64 MiB
)
```

`StagingStore.__init__` defaults remain `None`, so **no other caller** (tests, reaper, Mini App read path)
gets implicit enforcement. The store is still cached in `context.bot_data["attachment_store"]`, so there is
exactly one production store and one `_accept_lock`.

### 3.2 `bot/attachments.py` — documentation only (no logic change)

- Limits table (module docstring) updated: `MAX_ITEMS_PER_BATCH` and `MAX_STAGING_TOTAL_BYTES` are now
  marked **enforced in production (Option B, 2026-11-21)**; `StagingStore` defaults stay `None`;
  `max_bytes_per_batch` remains unused.
- `_effective_cap()` docstring now states explicitly that **preserved orphan files** (untracked regular
  files with no DB row) are counted by `staging_total_bytes`, so they reduce the capacity available for
  new staging and are **not deleted** here.

**No executable line in `bot/attachments.py` changed** (diff is docstring/comment-only; see §10).

### 3.3 Where the limits are enforced

Both limits are enforced in `StagingStore.store_async` **inside `_accept_lock`** (`:918`), before any byte
is written:

1. `_store_prepare` (`:657`) → `quota_block(batch_id, extra_items=1)` (`:583`): counts **actual files** in
   the batch; `count + 1 > 10` ⇒ `REJECTED_QUOTA`.
2. `_store_prepare` → `_effective_cap(batch_id)` (`:609`):
   `min(3 MiB, 64 MiB − staging_total_bytes(root), …)`. `cap <= 0` ⇒ `REJECTED_QUOTA`.
3. `_write_to_path` (`:623`) enforces the cap **during** the streaming write; overflow ⇒ `_TooLargeError`
   ⇒ `REJECTED_QUOTA` (when the binding cap is the aggregate) and the partial file is unlinked.

Because the check, the write and the `pending→stored` CAS all happen under `_accept_lock`, and production
polling is sequential (`bot/polling.py:175-178`), concurrent or repeated intake cannot bypass either limit.
The reaper only deletes (frees capacity), never adds, so it cannot cause an over-commit.

### 3.4 Preserved invariants

| Invariant | Evidence |
|---|---|
| 3 MiB per-file cap | `MAX_ATTACHMENT_BYTES` unchanged; `_effective_cap` still includes `self._max_bytes`; test `test_per_file_3mib_limit_still_enforced` |
| 15-minute TTL | `bot/db.py:261` unchanged (`ATTACHMENT_BATCH_TTL = timedelta(minutes=15)`); no TTL edit |
| Authoritative SQLite owner | `bot/db.py` SHA-256 unchanged; no new connection |
| `_accept_lock` + serialized dispatch | `bot/attachments.py:526/918` unchanged; `bot/polling.py:175-178` unchanged |
| Idempotent deletion/release | `_remove_file` unchanged; `test_repeated_sweep_is_idempotent_and_releases_once` |
| CAS anti-resurrection | `try_mark_attachment_item_stored` unchanged (`bot/db.py:1224`); existing race tests green |
| C2 / D-15 | No lifecycle change; expiry reclaims staging only; `test_expiry_releases_staging_and_preserves_outside_data` |
| One bot + ASGI process, existing workers | No new worker/queue/process/owner |

---

## 4. Orphan-file accounting behavior (explicit)

`staging_total_bytes(root)` counts **all regular files** in `<db_dir>/attachment_staging`, including
untracked/orphan files. `_scan_root_untracked` **reports but never deletes** them (existing retention
policy preserved). Therefore:

> **A preserved orphan file consumes part of the 64 MiB aggregate capacity and reduces the capacity
> available for new staging.** It is never deleted, relocated, or ignored by this change.

This is documented in the `_effective_cap` docstring and covered by
`test_orphan_file_counts_toward_limit_and_is_never_deleted`. No cleanup policy was invented.

Practical implication: if an orphan exists, the effective global budget is `64 MiB − orphan_bytes`. In the
normal row-first lifecycle, row-less orphans are rare (a crash mid-write leaves a `pending` row that expiry
reclaims), so this is a bounded, documented edge case rather than a routine capacity loss.

---

## 5. Tests added

New file: `tests/test_def011_a_option_b_limits.py` (16 tests). All deterministic, isolated in `tmp_path`
with temporary SQLite; no Telegram/OpenHands/network calls.

| # | Test | Covers |
|---|---|---|
| 1 | `test_production_wiring_enables_option_b_limits` | production store has `max_items_per_batch=10`, `max_total_bytes=64 MiB`, `max_bytes=3 MiB`, `quota_enabled=True`, single cached store |
| 2 | `test_default_store_stays_unenforced` | `StagingStore` defaults stay `None` (no implicit enforcement) |
| 3 | `test_per_file_3mib_limit_still_enforced` | 3 MiB exact accepted; 3 MiB + 1 rejected (`REJECTED_SIZE`) |
| 4 | `test_ten_files_accepted_eleventh_rejected` | 10 stored, 11th `REJECTED_QUOTA`, 10 files |
| 5 | `test_aggregate_64mib_boundary_below_exact_above` | 64 MiB − 1 (1-byte file accepted → exactly 64 MiB), at 64 MiB rejected, above 64 MiB rejected; no extra files; orphan untouched |
| 6 | `test_aggregate_rejection_via_accept_leaves_no_file` | `accept()` path rejects on aggregate capacity with no file; row-first metadata retained (pending, no file) |
| 7 | `test_aggregate_capacity_is_shared_across_batches` | global cap shared across `b1`/`b2` |
| 8 | `test_concurrent_intake_cannot_bypass_item_limit` | 15 concurrent `store_async` ⇒ exactly 10 stored, 5 rejected |
| 9 | `test_concurrent_intake_cannot_bypass_global_byte_limit` | 10 concurrent × 30 B with cap 100 ⇒ exactly 3 stored, 90 B on disk |
| 10 | `test_failed_write_does_not_consume_capacity` | `fsync` failure ⇒ `WRITE_FAILED`, no file, 0 bytes, row pending |
| 11 | `test_interrupted_partial_file_is_accounted_and_reclaimed` | partial file + pending row counted by a **fresh** store; expiry sweep deletes ≥2 files and restores 0 bytes |
| 12 | `test_repeated_sweep_is_idempotent_and_releases_once` | first sweep deletes; second sweep deletes 0; capacity stays 0 |
| 13 | `test_repeated_intake_after_release` | after expiry release, a new batch accepts again |
| 14 | `test_expiry_releases_staging_and_preserves_outside_data` | staging bytes → 0; outside (C2-like) file untouched; batch/item metadata retained (`expired`/`reaped`) |
| 15 | `test_orphan_file_counts_toward_limit_and_is_never_deleted` | orphan consumes the cap; rejection; orphan survives sweep |
| 16 | `test_no_schema_migration_or_reservation_ledger` | 17 tables; no `reserve`/`reservation`/`reserved_bytes` in `attachments.py` |

### 5.1 Mutation proof (non-vacuity)

On a scratch copy (live tree untouched):
- Revert the production wiring to `StagingStore(db, db_path)` ⇒ `test_production_wiring_enables_option_b_limits` **FAILED**.
- Set `max_items_per_batch=None` ⇒ same test **FAILED**.
- Restore ⇒ **PASSED**.

---

## 6. Validation results (actual commands, exit codes, counts)

| # | Command | Result | Exit |
|---|---|---|---|
| 1 | `python3 -m pytest tests/test_def011_a_option_b_limits.py -v` | **16 passed** | 0 |
| 1b | Focused attachment/staging suite (14 files incl. the new one: `test_def011_fs_offload`, `test_repair_plan_01_resource_staging`, `test_repair_plan_01_review_findings`, `test_attachment_staging_a1`, `test_attachment_batch_lifecycle_a2`, `test_attachment_cleanup_expiration_a4`, `test_attachment_intent_a3`, `test_repair_plan_02_life01_f2_race`, `test_repair_plan_02_life02_crash_recovery`, `test_repair_plan_02_life04_lifecycle_e2e`, `test_f01_reaper_fs_offload`, `test_repair_plan_02_life01_app_wiring`, `test_miniapp_attachment_download_mt2`) | **387 passed** | 0 |
| 2 | `python3 -m pytest -q` | **3467 passed, 0 failed**, 74 warnings | 0 |
| 3 | `node --test tests/frontend/*.test.js` | **280 pass, 0 fail** (not required — Python-only change; run for completeness) | 0 |
| 4 | `python3 -m pyflakes bot/ automation/ tools/ main.py tests/` | no output | 0 |
| 5 | `python3 -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | **High: 0** (Low 5, Medium 19) | 0 |
| 6 | `pytest tests/test_def011_fs_offload.py::test_T12_schema_table_count_unchanged ::test_T11b_no_reservation_ledger_introduced ::test_T11_aggregate_quotas_remain_disabled_by_default` | **3 passed** (17 tables; no ledger; defaults still `None`) | 0 |

**Baseline comparison:** full suite was **3451 passed** before this task; now **3467 passed** = **+16**
exactly the new tests. No existing test was weakened or deleted; all pre-existing attachment/staging tests
still pass.

**Unrun checks:** none applicable were skipped. No 3.11 interpreter is available in this environment
(verification used Python 3.13.15); the change is version-neutral (no new syntax/dependency).

---

## 7. Changed-file list and diff summary

| File | Change | Lines |
|---|---|---|
| `bot/handlers.py` | Pass `max_items_per_batch=10`, `max_total_bytes=64 MiB` to the single production `StagingStore` | **+17 / −2** |
| `bot/attachments.py` | Docstring/comment only (limits table + orphan-accounting note) — **no executable change** | **+10 / −5** |
| `tests/test_def011_a_option_b_limits.py` | New focused regression tests | new (16 tests) |
| `docs/audits/OHB2-WP07-DEF011-A-IMPLEMENTATION-REPORT.md` | This report | new |

Pre-existing modified/untracked files (`docs/reviews/…F01-IMPLEMENTATION-REPORT.md`,
`tests/test_doc_code_parity.py`, the F-03 reports, the diagnosis brief, `.openhands/`, `.agent/`) were
**preserved unchanged by this task**.

---

## 8. Explicit confirmation: no architecture change

- **No schema migration / schema-version change:** `bot/db.py` SHA-256 unchanged
  (`205f1363…c694b`); still **17** tables (`test_T12`).
- **No reservation ledger / new table:** no `reserve`/`reservation`/`reserved_bytes` tokens in
  `attachments.py` (`test_T11b`); accounting remains actual-file based.
- **No new worker/queue/SQLite owner/background process:** no change to `app.py`/workers; the reaper and
  watcher are untouched.
- **No new environment variables or config surface:** `bot/config.py` and `.env.example` unchanged.
- **No change to Telegram delivery guarantees / exactly-once:** outbox and batch lifecycle untouched.
- **No change to DEF-011-B/C, F-02, D6, media policy, or navigation:** untouched.
- **No broad formatting/refactoring:** diffs are minimal and scoped.

---

## 9. Limitations and remaining risks

1. **Preserved orphan files** consume part of the 64 MiB global budget (§4). This is intentional
   (existing retention policy) and is the only "capacity loss" edge case.
2. **Sweep latency:** the 15-minute TTL is logical; physical deletion happens at startup or on a throttled
   watcher tick (≥60 s). Under a stopped watcher, expired files linger until the next startup, so the
   64 MiB cap may stay occupied longer than 15 minutes.
3. **Global scope:** the 64 MiB cap is shared across all batches/conversations (single-user deployment),
   so one busy conversation can consume budget for another.
4. **Download-before-check:** quota rejection occurs after the ≤3 MiB download (the download is the input);
   a rejected file consumes transient bandwidth/memory but no disk. Not a safety gap.
5. **Single-process assumption:** `_accept_lock` serializes within one bot process (the supported model).
   Running two processes against the same staging root is unsupported and would bypass the in-process lock.
6. **Python 3.11 not run here** (no interpreter); the change is version-neutral.

---

## 10. Diff/scope audit

- `git status` shows only: `bot/attachments.py` (M, docstrings), `bot/handlers.py` (M, wiring), the new test
  file, the new report, plus the pre-existing modifications/untracked files from earlier tasks.
- `bot/db.py`, `bot/config.py`, `.env.example`, `bot/app.py`, `bot/polling.py` — **unchanged**.
- No `git add .`/`git add -A`; no reset/clean/stash/force.
- **No commit, push, PR, merge, deployment, or Autopush activation** was performed.

---

## 11. Final report (AGENTS.md format)

- **Status:** **DONE** — `A_IMPLEMENTATION_DONE`.
- **Acceptance criteria:** all met (§3–§8); 16 new tests pass; full suite 3467/0; all gates green.
- **Changes:** `bot/handlers.py` (wiring), `bot/attachments.py` (docs only), new test file, this report.
- **Verification:** see §6 (actual commands/exit codes).
- **Not verified / not implemented:** DEF-011-C, DEF-006, D6, media policy — out of scope. 3.11 not run.
- **Assumptions:** single-process deployment; production intake is sequential; `max_files_per_batch`
  maps to the existing `max_items_per_batch`.
- **Branch and commits:** `openhands-workspace-11yyMvqKPjTrIZt1RRpWq9` at `30dfa0d`; **no commit**.
- **Suggested next step:** independent review of this diff, then owner sign-off on the global-scope and
  orphan-accounting trade-offs.

---

## 12. DEF-011 status

**`DEF-011` is NOT closed.** This task closes **only the DEF-011-A implementation work** (Option B),
subject to subsequent review. `DEF-011-B` is implemented; `DEF-011-C` is not; `D6` remains deferred.

---

## 13. Explicit status

# `A_IMPLEMENTATION_DONE`
