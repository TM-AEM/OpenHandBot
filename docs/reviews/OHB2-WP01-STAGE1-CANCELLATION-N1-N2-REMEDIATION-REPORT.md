# OHB2-WP01 Stage 1 — N1/N2 Remediation and T1-T7 Regression Report

- **Task:** `OHB2-WP01-STAGE1-CANCELLATION-N1-N2-REMEDIATION-AND-REGRESSION-TESTS`
- **Date:** 2026-11-21
- **Repository:** `/workspace/project/OpenHandBot`
- **Mode:** narrow implementation, tests, docs; no publication
- **Completion classification:** **DONE_WITH_NOTES**
- **Independent review:** **NOT CLAIMED**
- **Owner approval:** **NOT RECORDED**
- **WP-01:** **NOT CLOSED**

## 1. Summary

N1 and N2 are remediated in the authoritative storage and database paths. Focused regression
coverage now includes all non-pending storage states, all ineligible/eligible reaping parents, and
T1-T7. The focused, related, and full test suites pass, as do Node tests, pyflakes, Bandit, pip-audit,
and `git diff --check`.

The notes are non-blocking but material:

- A caller that already created an item row (`row_created=True`) before storage cannot have that
  row deleted by this task. Storage now rejects non-pending parents before any byte write, but the
  pre-existing row remains `pending`; deletion of rows/files is explicitly out of scope.
- T2 verifies the handler mapping with a deterministic `REJECTED_BATCH` result at the service
  boundary; N1 separately proves the real storage layer returns `REJECTED_BATCH`. The full
  cancellation race cannot produce that stage through the same accept call because cancellation
  waits on `_accept_lock`.
- T7 uses controlled commit-proxy fault injection, not a real process kill; it proves durable
  state after reopen for the modeled pre/post-commit failures without claiming SQLite/filesystem
  atomicity.
- No independent review or independent approval was performed.

## 2. Baseline and final Git state

### 2.1 Baseline before this task

The task started from the post-verification state recorded by
`docs/reviews/OHB2-WP01-STAGE1-CANCELLATION-POST-IMPLEMENTATION-VERIFICATION-REPORT.md`:

| Item | Baseline |
|---|---|
| Branch | `main` |
| HEAD | `0774c9cff923a2ed02da36a1111a283a61600ea5` |
| HEAD tree | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| Index tree | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| Staged entries | 0 |
| Tracked modifications | 20 |
| Untracked files | 26 |
| Full working-tree diff SHA-256 | `a57bfbe453adcf2d9a08e78f81c9c7fd2efb6fc16f526e27ebfdc8754cf33f3d` |

The baseline was a mixed uncommitted tree: Stage 1, unrelated poller/WP changes, Stage 2 design
documents, and prior reports. None of those pre-existing changes was reverted, cleaned, staged, or
overwritten.

### 2.2 Final state

After adding the task code, tests, addendum, and this report:

| Item | Final |
|---|---|
| Branch | `main` |
| HEAD | `0774c9cff923a2ed02da36a1111a283a61600ea5` |
| HEAD tree | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| Index tree | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| Staged entries | 0 |
| Tracked modifications | 23 |
| Untracked files | 29 |
| Full working-tree diff SHA-256 | `25a53aaad27eeaaffcaa47e95b1c650be2c457f67bb12a92906d395e3e1a648f` |

The 23 modified files are the 20 baseline modifications plus:

- `tests/test_repair_plan_02_life01_f2_race.py`
- `tests/test_repair_plan_01_review_findings.py`
- `tests/test_miniapp_attachment_download_mt2.py`

The 29 untracked files are the 26 baseline untracked files plus:

- `tests/test_wp01_stage1_n1_n2_remediation.py`
- `docs/reviews/OHB2-WP01-STAGE1-CANCELLATION-IMPLEMENTATION-REPORT-ADDENDUM-N1-N2.md`
- `docs/reviews/OHB2-WP01-STAGE1-CANCELLATION-N1-N2-REMEDIATION-REPORT.md`

No fetch, pull, branch switch, reset, clean, restore, stage, commit, push, PR, merge, deployment, or
Autopush action was performed.

## 3. N1 remediation — reject non-pending before storage

### 3.1 Root cause

`StagingStore._store_prepare` rejected only `cancelled`; other non-pending parents
(`expired`, `rejected`, `delivered`, `failed`, `intent_recorded`, `dispatching`, `uncertain`,
unknown/malformed) proceeded through item insertion and byte writing, then failed at finalization.
That could leave a pending item row and perform unnecessary storage work.

### 3.2 Exact change

`bot/attachments.py::StagingStore._store_prepare` now enforces:

```python
if batch.status != ATTACHMENT_BATCH_PENDING:
    return StageResult(StageStatus.REJECTED_BATCH, item_id=item_id)
```

This check is after ownership/conversation validation and before:

- item insertion;
- staging-root creation;
- any byte write;
- finalization.

`store()` and `store_async()` both call this same `_store_prepare`, so the rule applies to both
paths. The existing `_sync_lock`/`_accept_lock` and cancellation guard are unchanged.

The result contract remains `StageStatus.REJECTED_BATCH`; affected tests were updated because
they previously expected `DB_FAILED` after the historical write-then-finalize path.

### 3.3 Guarantees verified

For every tested non-pending state, with `row_created=False`:

- no item row is inserted;
- no staging file is written;
- batch status is unchanged;
- result is `REJECTED_BATCH`.

States covered by parametrized tests:

`intent_recorded`, `dispatching`, `uncertain`, `delivered`, `expired`, `rejected`, `failed`,
`cancelled`, `future_status` (unknown), and `""` (malformed).

NULL status is rejected by the schema (`status TEXT NOT NULL`); the test proves
`sqlite3.IntegrityError` and no row.

### 3.4 Residual note (non-blocking)

If a caller already inserted an item row (`row_created=True`), storage rejects the non-pending
parent and writes no bytes, but it does not delete the pre-existing row. Row/file deletion is
forbidden by the task and architecture. The production `AttachmentService.accept` row-first path
still has this historical contract; it is not a new storage bypass.

## 4. N2 remediation — parent-state-aware item reaping

### 4.1 Root cause

`mark_attachment_item_reaped` only refused a `cancelled` parent. A direct call against an item
whose parent was `pending` could mark the item `reaped`, even though the approved reaper only
permits terminal parents.

### 4.2 Exact change

`bot/db.py` now defines one approved set:

```python
ATTACHMENT_BATCH_REAPABLE_STATUSES = frozenset({
    ATTACHMENT_BATCH_DELIVERED,
    ATTACHMENT_BATCH_EXPIRED,
    ATTACHMENT_BATCH_REJECTED,
    ATTACHMENT_BATCH_FAILED,
})
```

`bot/attachments.py::AttachmentReaper._TERMINAL` imports/uses the same set, so caller and DB cannot
drift. `bot/db.py::mark_attachment_item_reaped` now updates an item only when:

- the item is `pending` or `stored`; and
- the parent batch exists and is in `ATTACHMENT_BATCH_REAPABLE_STATUSES`; or
- the item is an orphan with no parent row (existing orphan policy preserved).

The parent check is inside the same conditional `UPDATE`; no read-then-write window exists between
the parent check and item transition. Unknown, empty, `NULL`, `pending`, `intent_recorded`,
`dispatching`, `uncertain`, and `cancelled` parent states fail closed.

### 4.3 Guarantees verified

Direct DB tests prove:

- every ineligible parent state returns `False` and leaves the item `stored`;
- `delivered`, `expired`, `rejected`, and `failed` allow the item transition;
- orphan items still follow the existing orphan cleanup policy;
- the existing terminal reaper path still works (full related suite).

## 5. T1-T7 coverage and outcomes

| ID | Test | Outcome |
|---|---|---|
| T1 | `test_t1_cancel_and_expiry_race_has_one_winner_and_reaper_respects_it` uses two SQLite connections and a barrier; cancel and expiry race on `pending`; exactly one CAS wins; if cancelled, reaper leaves file/item intact; if expired, reaper deletes only that item's bytes. | PASS |
| T2 | Parametrized `test_t2_handler_rejected_batch_does_not_report_success` drives real `handle_attachment` with a deterministic service result (`REJECTED_BATCH`) and asserts the cancelled/error text, never `ATTACHMENT_ACCEPTED_TEXT`. | PASS |
| T3 | `test_t3_attachments_cancel_does_not_mutate_route_or_user_state` sets a route/user_state, calls `/attachments_cancel`, and asserts exact `awaiting_state` preservation plus batch cancellation and file/item preservation. | PASS |
| T4 | `test_t4_attachments_clear_rejects_cancelled_batch` calls `/attachments_clear` on a cancelled batch; asserts `not_eligible`, no clearance marker, status unchanged, and direct DB result `not_eligible`. | PASS |
| T5 | `test_t5_accept_and_cancel_interleaving_storage_wins_without_mixed_state` blocks the accept chunks factory, starts cancellation, proves cancellation is still waiting, releases storage, then verifies `STORED` + `cancelled` + preserved file/item. | PASS |
| T6 | `test_t6_cancellation_waits_for_configured_write_lock_then_commits` holds a real SQLite write lock from a second connection, observes entry into `BEGIN IMMEDIATE` through a test proxy, proves the cancellation thread is blocked, releases, and verifies commit. `test_t6_permanent_db_error_does_not_report_success` verifies permanent error propagation and `pending` state. | PASS |
| T7 | `test_t7_failure_before_commit_leaves_pending_after_reopen` and `test_t7_failure_after_commit_is_durable_but_raises` use a controlled commit proxy; verify pre-commit failure reopens `pending`, post-commit failure reopens `cancelled`, and no success is returned. | PASS |

T7 is controlled fault injection, not a real process kill. No SQLite/filesystem atomicity is
claimed. Tests use temporary SQLite/staging paths and no production services.

## 6. Files changed by this task

### Source

| File | Change |
|---|---|
| `bot/attachments.py` | N1 pending-only storage guard in `_store_prepare`; reaper `_TERMINAL` uses the shared DB terminal set. |
| `bot/db.py` | Added `ATTACHMENT_BATCH_REAPABLE_STATUSES`; N2 parent-state guard in `mark_attachment_item_reaped`. |

### Tests

| File | Change |
|---|---|
| `tests/test_wp01_stage1_n1_n2_remediation.py` | New 44-test focused suite for N1, N2, T1-T7. |
| `tests/test_repair_plan_02_life01_f2_race.py` | Updated three existing expectations from `DB_FAILED` to `REJECTED_BATCH` for non-pending storage; expired-start case now asserts no item row. |
| `tests/test_repair_plan_01_review_findings.py` | Quota setup now simulates an already-reaped row directly, because N2 correctly refuses reaping under a pending parent. |
| `tests/test_miniapp_attachment_download_mt2.py` | Endpoint setup simulates a legacy reaped row directly, preserving the 404 test without bypassing the new authoritative guard. |

### Documentation

| File | Change |
|---|---|
| `docs/reviews/OHB2-WP01-STAGE1-CANCELLATION-IMPLEMENTATION-REPORT-ADDENDUM-N1-N2.md` | Corrects the original report's “asyncio's executor” wording to `anyio.to_thread.run_sync`; records N1/N2 scope. Historical report unchanged. |
| `docs/reviews/OHB2-WP01-STAGE1-CANCELLATION-N1-N2-REMEDIATION-REPORT.md` | This report. |

No operational documentation change was required: the runbook already says cancellation is
`pending` only, and N2 is an internal authoritative guard.

## 7. Verification commands and actual results

All commands ran from `/workspace/project/OpenHandBot` with the existing
`/tmp/ohb2-venv/bin/python`. No dependency was installed or upgraded.

| Command | Exit | Actual result |
|---|---:|---|
| `pytest -q tests/test_wp01_stage1_n1_n2_remediation.py` | 0 | **44 passed** in 2.28s |
| Same new suite, repeated 3 times | 0 | **44 passed** each (2.27s / 2.30s / 2.34s) |
| `pytest -q tests/test_wp01_stage1_n1_n2_remediation.py tests/test_repair_plan_02_life01_f2_race.py tests/test_repair_plan_01_review_findings.py tests/test_miniapp_attachment_download_mt2.py` | 0 | **148 passed**, 2 warnings, 7.66s |
| Affected existing suites including `tests/test_wp01_stage1_cancellation.py` | 0 | **143 passed**, 2 warnings, 7.93s |
| `pytest -q` (full Python suite) | 0 | **3628 passed**, 74 warnings, 176.35s |
| `pytest --collect-only -q tests/test_wp01_stage1_n1_n2_remediation.py` | 0 | **44 tests collected** |
| `node --test tests/frontend/*.test.js` | 0 | **280 pass, 0 fail** |
| `python -m pyflakes bot/ automation/ tools/ main.py tests/` | 0 | no output |
| `git diff --check` | 0 | no output |
| `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | 0 | **High 0**, Medium 19, Low 5 |
| `python -m pip_audit -r requirements-dev.txt` | 0 | **No known vulnerabilities found** |

## 8. Residual risks and limitations

1. **Row-first pre-existing item:** `row_created=True` callers own the item row; N1 prevents new
   insertion/bytes but cannot delete an already-created row without violating the no-deletion rule.
   This is documented, non-blocking, and does not affect the direct storage path tested by N1.
2. **T2 boundary:** the handler test uses a deterministic service result. N1 separately proves the
   real storage layer returns `REJECTED_BATCH`; a same-accept cancellation cannot produce that stage
   because cancellation waits for `_accept_lock`.
3. **T7:** controlled commit-boundary fault injection, not a real crash. Durable reopen state is
   verified for the modeled failures; no atomicity across SQLite and filesystem is claimed.
4. **T6:** the actual write-lock test uses a second SQLite connection and a test proxy to observe
   `BEGIN IMMEDIATE`. It verifies the configured `busy_timeout=5000` wait and commit behavior, not
   every SQLite busy-handler edge case.
5. **Independent review:** not performed; this report is not approval.
6. **Unrelated pre-existing work:** remains uncommitted and was preserved; task-only hunk hashes are
   not separable from the mixed working tree via Git alone.

## 9. SHA-256 values

### 9.1 This report

- **Report self-hash (reproducible):** `bb05b465f8ed0e669a16003dfd29151933ec4575cdf7379f845b9aed5db0e6ef`

Definition: SHA-256 of this file after replacing the 64-hex value on the self-hash line with an
empty string. The actual final `sha256sum` is reported in the task response because a literal
full-file hash cannot be embedded without changing the file.

### 9.2 Task files

| File | SHA-256 |
|---|---|
| `bot/db.py` | `c7c44ea4592f98eac40de63344a57c9b62e16d365ab7da62fac71b46b093f359` |
| `bot/attachments.py` | `0c52d04bfc7a461a0d8ca0a92476faa91a00ef9ebe7becb1e00fb12a76126d9b` |
| `tests/test_wp01_stage1_n1_n2_remediation.py` | `14adb057224153377d364e1fd467e9b4e6b1842295d10739347d1cb7eb3f92fa` |
| `tests/test_repair_plan_02_life01_f2_race.py` | `5765530e5a88651733a2c0e9c6122dd8f242765b68cb0092e5edcff6a1da7d8b` |
| `tests/test_repair_plan_01_review_findings.py` | `c8029a87f340842662fc0ed1280f911885170460545d1536428c391a5176cd3b` |
| `tests/test_miniapp_attachment_download_mt2.py` | `4c8384409411316e27fde74f56054fbb473a002f659137ebd343cc1789d2ed4f` |
| `docs/reviews/OHB2-WP01-STAGE1-CANCELLATION-IMPLEMENTATION-REPORT-ADDENDUM-N1-N2.md` | `2448909017c3ef0346837dff7bbcf20b080ebe3999762219a45006686593894b` |

### 9.3 Diff

- **Full working-tree diff SHA-256:** `25a53aaad27eeaaffcaa47e95b1c650be2c457f67bb12a92906d395e3e1a648f`
  (includes all pre-existing uncommitted changes; not a task-only patch).
- **Task-only hunk hash:** not calculable from Git alone because the task changes share files with
  unrelated pre-existing uncommitted work.

## 10. Working tree vs committed/published code

| Aspect | Working tree | Committed / published |
|---|---|---|
| N1/N2 remediation | Present, uncommitted | Absent at HEAD `0774c9c...` |
| New regression suite | Untracked | Not in HEAD |
| Existing test updates | Modified, uncommitted | Absent at HEAD |
| Addendum/report | Untracked | Not in HEAD |
| Remote/PR/deployment | Not touched | Not published |

No commit, push, PR, merge, deployment, or Autopush occurred. The verified code is not published.

## 11. Preservation confirmation

- All 20 baseline tracked modifications and all 26 baseline untracked files were preserved.
- No pre-existing report was overwritten; the historical implementation report is unchanged and
  the correction is a separate addendum.
- No attachment file, row, batch, or identity record was deleted.
- No Stage 2 retention field, recommendation, cleanup command, or automatic cleanup was changed.
- No Mini App source, worker, queue, database, process, dependency, or architecture change was made.
- Final state: **23 modified + 29 untracked**, 0 staged; full working-tree diff hash
  `25a53aa...`.

**Completion: DONE_WITH_NOTES. N1/N2 are remediated and T1-T7 are covered by deterministic tests.
No independent review or owner approval is claimed.**
