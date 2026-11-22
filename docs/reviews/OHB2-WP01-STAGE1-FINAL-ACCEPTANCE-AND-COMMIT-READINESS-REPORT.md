# OHB2-WP01 Stage 1 — Final Acceptance and Commit-Readiness Audit

- **Task:** `OHB2-WP01-STAGE1-FINAL-ACCEPTANCE-AND-COMMIT-READINESS-AUDIT`
- **Date:** 2026-11-21
- **Repository:** `/workspace/project/OpenHandBot`
- **Mode:** read-only audit; one new report only
- **Overall verdict:** **NOT_READY**
- **Technical Stage 1 acceptance:** **PASS_WITH_NOTES**
- **Scope isolation:** **NOT_ESTABLISHED**
- **Publication readiness:** **NOT_READY**
- **Independent review:** **NOT PERFORMED — this is not an independent review**
- **Owner approval:** **NO EXPLICIT STAGE 1 APPROVAL RECORDED**
- **WP-01:** **NOT CLOSED**

> This audit does not claim independent review or independent approval. It inspected the actual
> working tree, reports, source, tests, and Git metadata. It did not modify application code, tests,
> configuration, schema, Stage 2 fields, Mini App files, or any existing report. No fetch, pull,
> branch switch, reset, clean, restore, stage, commit, push, PR, merge, deployment, or Autopush
> action occurred.

## 1. Executive decision

The **Stage 1 behavior is technically acceptable with documented notes**, but the working tree is
**not safe to publish as an isolated Stage 1 commit** in its current state.

The blockers are scope and authorization, not an observed Stage 1 safety failure:

1. Stage 1 code is intermingled with unrelated uncommitted work in the same files:
   `bot/db.py`, `bot/handlers.py`, `bot/app.py`, `docs/OPERATIONS_RUNBOOK.md`,
   `tests/test_doc_code_parity.py`, and WP-07 documents.
2. Stage 1 also depends on prior WP-01 lifecycle/OD-01/OD-03 changes in those same mixed files
   (`/attachments`, `/attachments_clear`, clearance/routing helpers, and their registrations).
   A Stage 1-only patch cannot be applied to `HEAD` without either including those prerequisites or
   creating a separate prerequisite commit.
3. Exact Stage 1 hunk boundaries are **not provable from Git alone** in this dirty tree. The
   implementation report gives a file/function list and hashes, but there is no Stage 1 commit and no
   isolated Stage 1 patch.
4. No explicit Stage 1 owner approval is recorded. The Stage 1 decision package still says
   `PROPOSED — OWNER DECISION REQUIRED` and `NONE FILLED`; the separate WP-01 owner decision record
   authorizes broader WP-01 work including “safe active-batch abandonment”, but does not explicitly
   name this Stage 1 command/design package.
5. The current environment has no `pytest` or project virtualenv, so the focused/current test rerun
   could not be executed. Documented test evidence exists for the exact source hashes recorded by
   the implementation and N1/N2 reports; static compilation and whitespace checks pass.

The safe next step is **not** to stage the whole dirty tree. It is to produce a separate,
non-destructive Stage 1 patch in a fresh branch/worktree (including the prerequisite WP-01 hunks
explicitly), run the full suite against that isolated patch, and obtain owner approval before any
publication.

## 2. Baseline and final Git state

### 2.1 Recorded baseline from the N1/N2 report

The N1/N2 report records the state before that remediation task:

| Item | Value |
|---|---|
| Branch | `main` |
| HEAD | `0774c9cff923a2ed02da36a1111a283a61600ea5` |
| HEAD tree | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| Index tree | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| Staged entries | 0 |
| Tracked modifications | 20 |
| Untracked files | 26 |
| Full working-tree diff SHA-256 | `a57bfbe453adcf2d9a08e78f81c9c7fd2efb6fc16f526e27ebfdc8754cf33f3d` |

### 2.2 Actual state at this audit

| Item | Value |
|---|---|
| Branch | `main` |
| HEAD | `0774c9cff923a2ed02da36a1111a283a61600ea5` |
| HEAD tree | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| Index tree | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| Staged entries | 0 |
| Tracked modifications | 23 |
| Untracked files before this report | 29 |
| Untracked files after this report | 30 (this report added) |
| Full working-tree diff SHA-256 | `25a53aaad27eeaaffcaa47e95b1c650be2c457f67bb12a92906d395e3e1a648f` |
| Ignored entries observed | `.openhands/`, `.pytest_cache/`, `__pycache__/` trees |

The counts and diff hash **exactly match the N1/N2 report's final state**. The difference from the
recorded pre-N1/N2 baseline is explained by the N1/N2 task's six additions/changes:

- modified: `tests/test_repair_plan_02_life01_f2_race.py`
- modified: `tests/test_repair_plan_01_review_findings.py`
- modified: `tests/test_miniapp_attachment_download_mt2.py`
- untracked: `tests/test_wp01_stage1_n1_n2_remediation.py`
- untracked: `docs/reviews/OHB2-WP01-STAGE1-CANCELLATION-IMPLEMENTATION-REPORT-ADDENDUM-N1-N2.md`
- untracked: `docs/reviews/OHB2-WP01-STAGE1-CANCELLATION-N1-N2-REMEDIATION-REPORT.md`

No baseline entry disappeared; a set comparison of the recorded baseline status and the current
status produced no missing baseline paths. The working tree is not clean and is not the same as
`HEAD`; the report's statement that it is unchanged is therefore confirmed only for this exact
recorded state, not for committed code.

### 2.3 Current source-hash provenance

The current Stage 1/remediation source hashes match the N1/N2 report exactly:

| File | Current SHA-256 | Matches N1/N2 report |
|---|---|---|
| `bot/db.py` | `c7c44ea4592f98eac40de63344a57c9b62e16d365ab7da62fac71b46b093f359` | Yes |
| `bot/attachments.py` | `0c52d04bfc7a461a0d8ca0a92476faa91a00ef9ebe7becb1e00fb12a76126d9b` | Yes |
| `tests/test_wp01_stage1_n1_n2_remediation.py` | `14adb057224153377d364e1fd467e9b4e6b1842295d10739347d1cb7eb3f92fa` | Yes |
| `tests/test_repair_plan_02_life01_f2_race.py` | `5765530e5a88651733a2c0e9c6122dd8f242765b68cb0092e5edcff6a1da7d8b` | Yes |
| `tests/test_repair_plan_01_review_findings.py` | `c8029a87f340842662fc0ed1280f911885170460545d1536428c391a5176cd3b` | Yes |
| `tests/test_miniapp_attachment_download_mt2.py` | `4c8384409411316e27fde74f56054fbb473a002f659137ebd343cc1789d2ed4f` | Yes |

The Stage 1 implementation hashes in `bot/handlers.py`, `bot/app.py`,
`tests/test_wp01_stage1_cancellation.py`, `docs/OPERATIONS_RUNBOOK.md`,
`tests/test_attachment_batch_schema.py`, and `tests/test_doc_code_parity.py` match the Stage 1
implementation report. This gives the documented test evidence a verifiable source provenance.

## 3. Reconstructed Stage 1 scope

### 3.1 Durable `pending -> cancelled`

- **Implementation:** `bot/db.py:132` (`ATTACHMENT_BATCH_CANCELLED`), `bot/db.py:133-143`
  (status set), `bot/db.py:1370-1443` (`cancel_pending_attachment_batch`).
- **Behavior:** `BEGIN IMMEDIATE`; owner+batch lookup; duplicate-update handling; `pending`-only
  conditional `UPDATE`; commit before returning `cancelled`; rollback on exception.
- **Tests:** `tests/test_wp01_stage1_cancellation.py:133-262` (success/preservation, ownership,
  ineligible states, idempotency, duplicate, DB rollback, reopen, concurrent cancels).

### 3.2 Explicit batch-ID command and confirmation

- **Implementation:** `bot/handlers.py:3090-3133` (`attachments_cancel`), exact two arguments and
  case-insensitive `confirm`; `bot/app.py:58` and `bot/app.py:120` registration; `bot/handlers.py:911`
  help text; `bot/handlers.py:3039` list hint.
- **Tests:** `tests/test_wp01_stage1_cancellation.py:578-680` (registration, exact args, ownership,
  ineligible states, duplicate, DB failure no success reply).

### 3.3 Separation from `/cancel`

- **Implementation:** `bot/handlers.py:3136-3147` (`cancel_route`) and
  `bot/handlers.py:3149-3160` (`cancel_route_button`) remain route-only; cancellation command does
  not call `clear_awaiting_and_record_outcome`.
- **Test:** `tests/test_wp01_stage1_cancellation.py:683-691` proves `/cancel` leaves the attachment
  batch `pending`.

### 3.4 Synchronization across asynchronous and synchronous storage

- **Implementation:** `bot/attachments.py:531-555` (`_sync_lock` and `cancellation_guard`),
  `bot/attachments.py:894-911` (synchronous `store()` holds `_sync_lock`),
  `bot/attachments.py:955-1015` (`store_async` holds `_accept_lock`),
  `bot/attachments.py:1201-1218` (`AttachmentService.cancel_pending_batch` waits on the guard).
- **Tests:** `tests/test_wp01_stage1_cancellation.py:292-500` (rejection, cancel-first, store-wins,
  sync and async paths); `tests/test_wp01_stage1_n1_n2_remediation.py:391-465` (real accept/cancel
  interleaving).
- **Note:** direct synchronous `store()` on the event-loop thread is not the production path; a hung
  sync store can delay cancellation. This is a liveness limitation, not a state-corruption path.

### 3.5 Parent-state checks before storage

- **Implementation:** `bot/attachments.py:702-714` (`_store_prepare` requires a `pending` parent
  before item insertion/bytes); `bot/db.py:2051-2085` (`accept_attachment_item` conditional INSERT
  with owner/conversation/`pending`); `bot/db.py:1261-1318`
  (`try_mark_attachment_item_stored` requires item and parent `pending`).
- **Tests:** N1 cases `tests/test_wp01_stage1_n1_n2_remediation.py:135-168` cover every non-pending
  state, sync and async, plus `row_created=True`; Stage 1 tests `292-500` cover cancelled races.

### 3.6 CAS protection for cancellation and expiration

- **Implementation:** `bot/db.py:1349-1368` (`try_transition_attachment_batch_status`),
  `bot/db.py:1412-1417` (cancellation CAS), `bot/attachments.py:1548-1570` (reaper expiry CAS),
  `bot/attachments.py:1116-1149` (accept-path expiry CAS).
- **Tests:** `tests/test_wp01_stage1_cancellation.py:541-552` and
  `tests/test_wp01_stage1_n1_n2_remediation.py:224-315` (actual two-connection cancel/expiry race;
  exactly one winner; reaper follows the winner).

### 3.7 Parent-state eligibility for item reaping

- **Implementation:** `bot/db.py:148-155` (`ATTACHMENT_BATCH_REAPABLE_STATUSES`),
  `bot/db.py:1717-1750` (`mark_attachment_item_reaped` conditional UPDATE),
  `bot/attachments.py:1316` (`_TERMINAL` uses the same set).
- **Tests:** `tests/test_wp01_stage1_n1_n2_remediation.py:191-222` (ineligible parents, all
  approved terminal parents, orphan policy); `tests/test_wp01_stage1_cancellation.py:554-576`.

### 3.8 Exclusion of cancelled batches from automatic reaping

- **Implementation:** `bot/attachments.py:1316-1318` (`_TERMINAL` excludes cancelled;
  `_NON_REAPABLE`), `bot/attachments.py:1428-1436` (explicit skipped count),
  `bot/attachments.py:1582-1594` (`_plan_batch` early skip).
- **Tests:** `tests/test_wp01_stage1_cancellation.py:504-533` (sweep leaves files/rows; explicit
  plan skip).

### 3.9 Preservation of files, rows, and identity

- **Implementation:** `bot/db.py:1370-1443` has no file/row/identity deletion; cancellation only
  updates the batch status. `AttachmentService.cancel_pending_batch` only calls the DB method.
  No `DELETE FROM attachment_*` path was added.
- **Tests:** `tests/test_wp01_stage1_cancellation.py:133-160` (file exists, item remains, counts
  unchanged); T3/T4 and N1/N2 preservation assertions.

### 3.10 Truthful user-facing results

- **Implementation:** `bot/handlers.py:2301-2305` (`ATTACHMENT_BATCH_CANCELLED_TEXT`),
  `bot/handlers.py:2653-2670` (rejected/duplicate mapping),
  `bot/handlers.py:3124-3133` (cancelled/already/not found/not eligible/duplicate messages).
- **Tests:** `tests/test_wp01_stage1_cancellation.py:585-680`; T2
  `tests/test_wp01_stage1_n1_n2_remediation.py:316-340`; T3/T4 handler tests.

### 3.11 T1-T7 and N1/N2 regression coverage

- `tests/test_wp01_stage1_n1_n2_remediation.py:135-168` — N1 (10 non-pending states, sync/async,
  row-created, NULL schema).
- `:191-222` — N2 (ineligible/approved parents, orphan).
- `:224-315` — T1 (two-connection cancel/expiry race + reaper).
- `:316-340` — T2 (handler `REJECTED_BATCH` response).
- `:342-367` — T3 (route/user_state preservation).
- `:369-389` — T4 (`/attachments_clear` rejects cancelled).
- `:391-465` — T5 (accept/cancel interleaving).
- `:467-539` — T6 (real SQLite write lock; permanent DB error).
- `:541-568` — T7 (commit-boundary fault injection/reopen).
- Stage 1 test suite: `tests/test_wp01_stage1_cancellation.py:133-702` (39 tests in the
  implementation report; 44 tests in the N1/N2 file).

### 3.12 Operational documentation

- **Implementation:** `docs/OPERATIONS_RUNBOOK.md:320` documents `/attachments_cancel
  <batch_id> confirm`, `pending` only, no file/row/identity deletion, no route clear, and
  non-reapable cancelled batches.
- **Help/registration:** `bot/handlers.py:911`, `bot/app.py:58`, `bot/app.py:120`.
- **Parity:** `tests/test_doc_code_parity.py:249-253` and `:346-348` expect six `to_thread`
  occurrences; the addendum corrects the implementation report's “asyncio's executor” wording to
  `anyio.to_thread.run_sync`.

## 4. Safety acceptance matrix

Legend: **PASS** = requirement implemented and evidenced; **FAIL** = requirement not met;
**NOT VERIFIED** = evidence unavailable. “PASS + note” means the requirement is met with a
documented residual limitation, not a hidden failure.

| Requirement | Verdict | Evidence |
|---|---|---|
| Durable `pending -> cancelled` transition | **PASS** | `bot/db.py:1370-1443`; Stage 1 tests `133-262` |
| Explicit batch-ID command + confirmation | **PASS** | `bot/handlers.py:3090-3133`; `bot/app.py:58,120`; tests `578-680` |
| Separation from `/cancel` | **PASS** | `bot/handlers.py:3136-3160`; test `683-691` |
| Sync/async cancellation synchronization | **PASS + note** | `bot/attachments.py:531-555,894-911,955-1015,1201-1218`; tests `292-500`; direct sync store liveness note |
| Parent-state check before storage | **PASS + note** | `bot/attachments.py:710-714`; `bot/db.py:2051-2085,1261-1318`; N1 tests `135-168`; `row_created=True` residual below |
| CAS cancellation/expiration | **PASS** | `bot/db.py:1349-1368,1412-1417`; `bot/attachments.py:1548-1570`; T1 `224-315` |
| Parent eligibility for item reaping | **PASS** | `bot/db.py:148-155,1717-1750`; N2 tests `191-222` |
| Cancelled excluded from automatic reaping | **PASS** | `bot/attachments.py:1316-1318,1428-1436,1582-1594`; tests `504-533` |
| Files/rows/identity preserved | **PASS** | No deletion in cancellation; tests `133-160`, T3/T4 |
| Truthful results/no false success | **PASS** | `bot/handlers.py:2301-2305,2653-2670,3124-3133`; tests `585-680`, T2 |
| T1-T7 and N1/N2 coverage exists | **PASS** | `tests/test_wp01_stage1_n1_n2_remediation.py:135-568`; Stage 1 suite `133-702` |
| Operational documentation | **PASS** | `docs/OPERATIONS_RUNBOOK.md:320`; help/registration/parity |

### 4.1 `row_created=True` residual

`AttachmentService.accept` performs row-first insertion before `store_async`. If the batch becomes
non-pending after that insertion but before storage, `_store_prepare` returns `REJECTED_BATCH` and
writes no bytes; the already-created item row remains `pending` (it is not deleted, because deletion
is out of scope). This is **not** mistaken for successful storage:

- `_store_prepare` rejects before item insertion/bytes (`bot/attachments.py:710-714`);
- `_store_finalize` is never reached;
- `try_mark_attachment_item_stored` requires both item and parent `pending`
  (`bot/db.py:1261-1318`);
- the handler returns `ATTACHMENT_BATCH_CANCELLED_TEXT`, not `ATTACHMENT_ACCEPTED_TEXT`
  (`bot/handlers.py:2653-2670`);
- no staging file is written.

The residual is a pre-existing row, not a false success. It remains a documented non-blocking
limitation and should be accepted explicitly by the owner or addressed in a future task.

### 4.2 Stage 2 policy compatibility

**PASS.** No Stage 2 cleanup command, timer, retention expiry, cancelled reaper path, or attachment
`DELETE` SQL was introduced. `cancelled` is non-terminal and non-reapable; Stage 2 Option A
(permanent retention) is preserved in behavior. The Stage 2 decision package remains
`DESIGN ONLY — NO IMPLEMENTATION AUTHORIZED` and its owner fields are unfilled.

### 4.3 Architecture and lifecycle

**PASS.** No new worker, queue, database, process, dependency, schema migration, Mini App source,
or Autopush behavior was added by Stage 1. The only `to_thread` occurrence added is the guarded
sync-lock acquisition already documented; existing path-containment/symlink/regular-file protections
are unchanged.

## 5. Exact scope attribution

### 5.1 Pure Stage 1/N1/N2 additions

These files are untracked and contain Stage 1/N1/N2 artifacts without a pre-existing tracked
baseline:

- `tests/test_wp01_stage1_cancellation.py` — Stage 1 tests.
- `tests/test_wp01_stage1_n1_n2_remediation.py` — N1/N2 and T1-T7 tests.
- `docs/reviews/OHB2-WP01-ACTIVE-BATCH-CANCELLATION-SAFETY-DESIGN.md` — approved design input.
- `docs/reviews/OHB2-WP01-ACTIVE-BATCH-CANCELLATION-SAFETY-DESIGN-REPORT.md` — design report.
- `docs/reviews/OHB2-WP01-STAGE1-CANCELLATION-OWNER-DECISION-PACKAGE.md` — pre-decision package.
- `docs/reviews/OHB2-WP01-STAGE1-CANCELLATION-OWNER-DECISION-REPORT.md` — decision report.
- `docs/reviews/OHB2-WP01-STAGE1-CANCELLATION-IMPLEMENTATION-REPORT.md` — implementation report.
- `docs/reviews/OHB2-WP01-STAGE1-CANCELLATION-IMPLEMENTATION-REPORT-ADDENDUM-N1-N2.md` — correction.
- `docs/reviews/OHB2-WP01-STAGE1-CANCELLATION-POST-IMPLEMENTATION-VERIFICATION-REPORT.md` — verification.
- `docs/reviews/OHB2-WP01-STAGE1-CANCELLATION-N1-N2-REMEDIATION-REPORT.md` — N1/N2 report.

These are documentation/test additions, not proof that the mixed source files are isolated.

### 5.2 Mixed files — Stage 1 plus unrelated work

| File | Stage 1/N1/N2 content | Unrelated/pre-existing content |
|---|---|---|
| `bot/db.py` | constants `132-155`; `AttachmentBatchStateChanged` `195-200`; routing `CANCELLED` `554-556`; CAS/cancel `1349-1443`; `list_cancelled` `1512-1523`; N2 guard `1717-1750`; routing cancelled branches `1847-1851`; conditional item insert `2051-2085` | prior WP-01 clearance/routing: `174-183`, `1544-1645`, `1779-1836`; other prior lifecycle work |
| `bot/handlers.py` | `ATTACHMENT_BATCH_CANCELLED_TEXT` `2301-2305`; rejected-batch reply `2653-2670`; `CANCELLED` routing `2839-2842`; `attachments_cancel` `3090-3133`; hint `3039`; help line `911` | prior WP-01 `/attachments`, `/attachments_clear` and OD-03 messages at `2253-2305`, `2698-2720`, `3019-3088` |
| `bot/app.py` | `attachments_cancel` command `58`, registration `120` | prior WP-01 `attachments`/`attachments_clear` `56-57,118-119`; unrelated WP-07 `concurrent_updates(False)` `78-94` |
| `docs/OPERATIONS_RUNBOOK.md` | `/attachments_cancel` row `320` | OD-03 intake default row `64`; prior WP-01 `/attachments`/clear rows `318-319` |
| `tests/test_doc_code_parity.py` | `to_thread` count hunks `249-253`, `346-348` | WP-08 env/schema parity changes at `5-?`, `55-?`, and related functions |
| `docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md` | `six` count hunk around `37` | WP-07 post-decision update around `14-17` and unrelated content |
| `docs/reviews/OHB2-WP07-FINAL-STABILIZATION-BATCH-REPORT.md` | `six` count hunk around `217` | WP-07 report content; only the count hunk is Stage 1-related |

`bot/attachments.py` appears to contain Stage 1/N1/N2 changes only in the working diff; its
current hash matches the N1/N2 report. This is an observation from the diff, not a clean-commit
proof.

### 5.3 Stage 1 dependencies on prior WP-01 work

Stage 1 cannot be applied as a standalone patch to `HEAD` because it references prior WP-01
lifecycle/OD-01/OD-03 work in the same files:

- `bot/db.py` Stage 1 routing references `list_terminal_attachment_batches`,
  `is_attachment_terminal_cleared`, and `ATTACHMENT_BATCH_CLEARABLE_STATUSES` (prior WP-01).
- `bot/handlers.py` Stage 1 `/attachments_cancel` sits alongside prior `/attachments` and
  `/attachments_clear`; T4 explicitly calls `clear_attachment_terminal_batch`.
- `bot/app.py` registers `attachments_cancel` next to prior `attachments`/`attachments_clear`.
- `tests/test_wp01_stage1_n1_n2_remediation.py:383-384` depends on the prior clearance API.
- `docs/OPERATIONS_RUNBOOK.md` has both the prior WP-01 rows and the Stage 1 row.

Therefore the publication scope is either (a) a combined WP-01 lifecycle + Stage 1 commit, or
(b) a prerequisite WP-01 lifecycle/OD-01/OD-03 commit followed by a hunk-level Stage 1 commit.

### 5.4 Proposed file-by-file publication scope (not staged)

**Include in a Stage 1-only patch only after hunk extraction:**

- `bot/db.py` — only the Stage 1/N1/N2 hunks listed in §5.2; exclude prior clearance/routing hunks.
- `bot/attachments.py` — Stage 1/N1/N2 diff (verify hunk-by-hunk before applying).
- `bot/handlers.py` — only the Stage 1 hunks listed in §5.2.
- `bot/app.py` — only `attachments_cancel` command/registration lines.
- `docs/OPERATIONS_RUNBOOK.md` — only line `320` (and any Stage 1-specific text), not the OD-03 row.
- `tests/test_attachment_batch_schema.py` — `cancelled` status line only.
- `tests/test_doc_code_parity.py` — only the `to_thread` count hunks; exclude WP-08 changes.
- `docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md` — only the `six` count hunk.
- `docs/reviews/OHB2-WP07-FINAL-STABILIZATION-BATCH-REPORT.md` — only the `six` count hunk.
- `tests/test_repair_plan_02_life01_f2_race.py` — N1-only changes.
- `tests/test_repair_plan_01_review_findings.py` — N2-only changes.
- `tests/test_miniapp_attachment_download_mt2.py` — N2-only test setup change.
- `tests/test_wp01_stage1_cancellation.py` — whole new file.
- `tests/test_wp01_stage1_n1_n2_remediation.py` — whole new file.
- Stage 1 design/implementation/verification/N1/N2 docs listed in §5.1.

**Prerequisite, separate from Stage 1 (owner decision required):**

- `bot/config.py`, `.env.example`, `README.md`, `docs/ZERO_TOUCH_STARTUP.md` — OD-03 default-off.
- Prior WP-01 clearance/routing hunks in `bot/db.py`, `/attachments`/`/attachments_clear` hunks in
  `bot/handlers.py`, and their `bot/app.py` registrations.
- `tests/test_wp01_attachment_lifecycle.py`, `tests/test_repair_plan_02_life03_intake_kill_switch.py`,
  `tests/test_attachment_batch_lifecycle_a2.py`, related OD-03 test changes.
- `docs/decisions/OHB2-WP01-OD01-OD03-OWNER-DECISION-RECORD.md` and the prior WP-01 report.

**Exclude from Stage 1 publication:**

- `.agent/PROGRESS.md` (internal task state; mixed).
- Poller concurrency implementation/audit/handoff docs and `tests/test_u04_concurrency.py`,
  `tests/test_start_script.py` and their code.
- WP-07/WP-08/WP-09 owner/acceptance/reconciliation reports.
- `docs/reviews/OHB2-WP01-STAGE2-CLEANUP-POLICY-AND-OWNER-DECISION-*.md` (Stage 2; no code).
- `docs/audits/OHB2-WP01-ATTACHMENT-LIFECYCLE-IMPLEMENTATION-REPORT.md` and
  `tests/test_wp01_attachment_lifecycle.py` (prior WP-01 context, not Stage 1).
- `.env.example`, `README.md`, `bot/config.py`, `docs/ZERO_TOUCH_STARTUP.md` (OD-03 prerequisite,
  not Stage 1).
- Any ignored cache/agent state.

**Do not stage any of the above in this audit.** The proposed scope is a plan only.

## 6. Test evidence and provenance

### 6.1 Current audit checks actually run

| Command | Exit | Actual result |
|---|---:|---|
| `python3 -m py_compile` on the Stage 1/remediation source and test files | 0 | syntax OK |
| `git diff --check` | 0 | no whitespace errors |

### 6.2 Test rerun unavailable

An attempted focused rerun:

```text
/tmp/ohb2-venv/bin/python -m pytest -q \
  tests/test_wp01_stage1_cancellation.py \
  tests/test_wp01_stage1_n1_n2_remediation.py
```

failed with exit `127`: `/tmp/ohb2-venv/bin/python: No such file or directory`. The system Python
also has no `pytest` (`ModuleNotFoundError`), and no Docker daemon is available. Therefore the full
or focused Python suite was **NOT RERUN** in this audit. This is an environment limitation, not a
test failure.

### 6.3 Documented evidence (provenance)

The implementation and N1/N2 reports record, for the exact source hashes above:

- Stage 1 focused suite: **39 passed**.
- N1/N2/T1-T7 suite: **44 passed**.
- Related subset: **539 passed** at verification, **148 passed** in the N1/N2 focused rerun.
- Full Python suite: **3584 passed** after Stage 1; **3628 passed** after N1/N2.
- Node: **280 pass / 0 fail**.
- pyflakes: exit 0.
- Bandit: High 0 (Medium 19, Low 5).
- pip-audit: no known vulnerabilities.
- `git diff --check`: exit 0.

Because current source hashes match the reports and no source changed in this audit, these results
have verifiable provenance for the current working-tree source. They are **not** an independent
rerun and are **not** independent review.

## 7. Verdicts

### 7.1 Technical Stage 1 acceptance

**PASS_WITH_NOTES.**

All twelve requested Stage 1 safety behaviors are implemented and have code/test evidence. N1 and
N2 are remediated; T1-T7 are covered by deterministic tests. The notes are:

- `row_created=True` can leave a pre-existing `pending` item row after a batch becomes non-pending;
  no bytes are written, no `stored` transition occurs, and no success is reported.
- T2 is a handler-boundary test with a deterministic service result; N1 separately proves the
  storage rejection.
- T7 is controlled commit-fault injection, not a real process crash.
- Direct synchronous `store()` on the event loop can delay cancellation; production uses
  `store_async`.

### 7.2 Scope isolation

**NOT_ESTABLISHED.**

The exact Stage 1 hunk set is not available as a commit or isolated patch. Four core source files
and two tests/docs contain both Stage 1 and unrelated or prerequisite WP-01/WP-07/WP-08 changes.
Stage 1 also depends on prior WP-01 clearance/routing code. A file-level commit of the dirty tree
would publish unrelated work; a clean Stage 1-only commit is not yet proven.

### 7.3 Publication readiness

**NOT_READY.**

A publication is blocked by the scope-isolation gap and by the absence of explicit Stage 1 owner
approval. No commit/push/PR is authorized or performed. A successful test suite is not proof of
independent review or owner approval.

### 7.4 Remaining owner decisions

1. **Explicit Stage 1 approval:** fill/record the Stage 1 design and implementation authorization
   fields in `docs/reviews/OHB2-WP01-STAGE1-CANCELLATION-OWNER-DECISION-PACKAGE.md` §15, or record
   an equivalent explicit decision. The package currently says `PROPOSED` and `NONE FILLED`.
2. **Publication scope:** choose either a combined WP-01 lifecycle + Stage 1 commit or a
   prerequisite WP-01 commit followed by a hunk-level Stage 1 commit. Authorize the exact file/hunk
   list; do not authorize the whole dirty tree.
3. **Stage 2 policy record:** decide whether to record Stage 2 Option A (permanent retention) as
   policy. The Stage 2 package is still `DESIGN ONLY` and its owner fields are unfilled; Stage 1
   behavior already preserves it.
4. **Residual acceptance:** explicitly accept or schedule a future task for the `row_created=True`
   pending-row residual. It is non-blocking for safety but remains a data-hygiene limitation.
5. **Publication authorization:** separately authorize branch, commit, and any later PR/merge; none
   is authorized by this audit.

## 8. Residual safety risks

| Risk | Severity | Status |
|---|---|---|
| Mixed-file/hunk publication could include unrelated poller, WP-07, WP-08, or OD-03 work | High for scope isolation | **Blocking publication** until a hunk-level patch is reviewed |
| Stage 1 depends on prior WP-01 clearance/routing code absent from `HEAD` | High for standalone patch | Must include prerequisite or combined commit |
| `row_created=True` leaves a pre-existing `pending` row in a non-pending batch | Medium, non-blocking | No bytes/stored/success; owner acceptance or future cleanup decision |
| Direct sync `store()` can block cancellation | Medium, liveness only | Production uses async path; documented |
| T2/T7 are boundary/fault-injection tests, not full end-to-end races | Low | N1/T1/T5 provide storage/race evidence; documented |
| No explicit Stage 1 owner approval | High for publication | Owner decision required |
| No independent review | High for governance | Not claimed; remains outstanding |

## 9. Git/preservation confirmation

- Branch `main`; HEAD `0774c9cff923a2ed02da36a1111a283a61600ea5`; HEAD tree and index tree
  `faa7a3f03aa361698c6854281c162358bf38b84f`.
- Staged entries: **0**.
- Tracked modifications: **23**; untracked files: **29** before this report.
- All 20 baseline modifications and 26 baseline untracked files are present; no baseline entry is
  missing.
- `.agent/PROGRESS.md`, `.openhands/`, ignored caches, and unrelated work are preserved.
- No application/test/config/schema/Mini App/Stage 2/report file was modified by this audit.
- The only new file is this report.
- No fetch, pull, branch switch, reset, clean, restore, stage, commit, push, PR, merge, deployment,
  or Autopush action occurred.

## 10. SHA-256

- **This report:** `c55d211cb4f62320cf73cf69320b5c7b76176f1a5a5c3fb28445cca15385adbe`
- **Full working-tree diff:** `25a53aaad27eeaaffcaa47e95b1c650be2c457f67bb12a92906d395e3e1a648f`
  (mixed; not a Stage 1-only patch)
- **Stage 1 source hashes:** see §2.3 and the implementation/N1-N2 reports.
- **Task-only hunk hash:** not calculable from Git alone because Stage 1 shares files with
  unrelated uncommitted work.

## 11. Working tree vs committed vs published

| Aspect | Working tree | Committed / published |
|---|---|---|
| Stage 1 cancellation code | Present, uncommitted | Absent at HEAD `0774c9c...` |
| N1/N2 remediation | Present, uncommitted | Absent at HEAD |
| Stage 1 tests | Untracked | Not in HEAD |
| Stage 1 docs | Untracked | Not in HEAD |
| Prior WP-01 lifecycle/OD-03 work | Present, uncommitted | Absent at HEAD |
| Unrelated poller/WP-07/WP-08/WP-09 work | Present, uncommitted | Absent at HEAD |
| Remote/PR/deployment | Not touched | Not published |

**Overall: NOT_READY for isolated publication. Technical Stage 1 behavior: PASS_WITH_NOTES.
Scope isolation: NOT_ESTABLISHED. No independent review or owner approval is claimed.**
