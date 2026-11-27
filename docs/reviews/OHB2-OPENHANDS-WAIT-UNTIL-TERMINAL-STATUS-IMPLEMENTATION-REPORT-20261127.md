# OHB2-OPENHANDS-WAIT-UNTIL-TERMINAL-STATUS — Implementation Report

**Task ID:** `OHB2-OPENHANDS-WAIT-UNTIL-TERMINAL-STATUS`
**Date:** 2026-11-27
**Verdict:** `PASS_WITH_NOTES`

## 1. Baseline

### 1.1 Git baseline

| Item | Value |
|---|---|
| Branch | `agent/r6-review-delivery` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` |
| HEAD tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| `main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `origin/main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| Modified tracked before task | 12 pre-existing |
| Staged before/after task | 0 |
| Untracked before task | 92 pre-existing |
| Ignored relevant files | `.venv/`, `node_modules/`, `__pycache__/` pre-existing ignored artifacts |
| Modified tracked after implementation | 15 (12 pre-existing + 3 implementation/test files) |
| Untracked after implementation | 93 before this report; 94 including this report |
| `bot/review` tracked files | 0 |
| D-05/R7 files | untouched |

Pre-existing modified files include `.agent/PROGRESS.md`, `.env.example`, `README.md`,
`bot/app.py`, `bot/config.py`, `bot/db.py`, `bot/handlers.py`, `bot/outbox.py`,
`docs/OPERATIONS_RUNBOOK.md`, and three existing test files. Those changes were preserved.
`bot/db.py` already had unrelated R7 modifications; this task only added the watched
tracking columns and methods described below.

### 1.2 Baseline checks

```text
python -m pytest -q tests/test_watcher.py tests/test_u01_watcher.py
98 passed, 28 warnings in 9.90s

python -m pyflakes bot/watcher.py bot/openhands_client.py bot/messages.py bot/db.py bot/outbox.py tests/test_watcher.py tests/test_u01_watcher.py
exit 0
```

No commit, push, PR, merge, deployment, release, branch switch, reset, clean, or autopush
was performed.

## 2. Root cause of the 10-minute behavior

The 10-minute limit was local, not an OpenHands provider timeout.

Baseline evidence:

- `bot/watcher.py:46` in HEAD: `START_TIMEOUT = timedelta(minutes=10)`.
- `bot/watcher.py:390-423` in HEAD: `_process_submitted()`.
- When OpenHands reported a terminal state but `get_reply_since()` returned no report
  newer than the prompt, the watcher:
  1. waited until `START_TIMEOUT` (10 minutes);
  2. sent a `stale_report` notification saying no new report appeared;
  3. called `remove_watched_if_seq()` and stopped tracking.

That path did not literally set `notified_status` to `finished`; it did, however, end
tracking at a local 10-minute deadline and presented the task as no longer worth
following. It could therefore be perceived as a completed/stale task even though the
final report had not been retrieved. The 10-minute value was unrelated to:

- `OpenHandsClient` HTTP timeout (`30s`);
- `WATCHER_INTERVAL` (`25s` default, configurable);
- `AWAITING_TTL` (`10m`) which is the Telegram routing window, not task lifecycle;
- `bot/web/runner.py::_START_TIMEOUT` (`10s`) which is ASGI server startup.

The root cause was the local `START_TIMEOUT` branch in `_process_submitted`.

## 3. Existing lifecycle and polling flow

1. The user sends a prompt through the existing outbox path.
2. `bot/outbox.py::_complete_outbox` (baseline lines 437-439) adds the conversation to
   `watched`, stores its baseline state, and stores `submitted_at`.
3. `bot/app.py::_post_init` (lines 306-317) starts one `Watcher` in the existing
   one-process architecture.
4. `Watcher._run()` calls `Watcher.tick()` and sleeps the bounded current delay
   (`WATCHER_INTERVAL`, or persisted/in-memory backoff after a failed batch).
5. `tick()`:
   - lists durable `watched` rows;
   - calls `OpenHandsClient.get_conversations(ids)` once for the batch;
   - maps each row through `bot.messages.get_status()`;
   - routes submitted rows to `_process_submitted()` and manual/legacy rows to
     `_process_legacy()`.
6. `_process_submitted()` calls `get_reply_since(submitted)` and only delivers a
   terminal notification when a fresh report exists, except for terminal failure-like
   states where a fresh report may not exist.
7. `Watcher._notify()` writes an event-first inbox row, sends through Telegram, records
   delivery state, and then removes the watch. Existing inbox `event_key` and
   `transition_seq` prevent duplicate transition delivery.
8. The Mini App reads the live OpenHands conversation through
   `bot/web/services.py::_conversation_dto()` / `get_status()`. No new Mini App
   mechanism was introduced.
9. Restart recovery is the existing `Watcher` start path: `list_watched()` reloads the
   durable rows, `_wait_for_initial_check()` honors persisted `next_check_at`, and the
   next tick resumes polling.

Durable identifiers/state already present: `conversation_id` (primary key),
`submitted_at`, `last_state`, `watch_seq`, `pending_delivery_state`, and the inbox
event key/transition identity.

### 3.1 Before/after lifecycle behavior

| Situation | Before | After |
|---|---|---|
| Non-terminal after 10 minutes | `START_TIMEOUT` branch could terminate a terminal/no-report watch | Continue polling until provider terminal state |
| Terminal, no fresh report | After 10 minutes sent stale notice and removed watch | Persist terminal + `report_state=pending`; keep polling for report |
| Terminal, report arrives later | Could already be removed | Deliver once, then remove |
| Polling/network failure | Retry next fixed tick; no false completion | Keep state; persist `poll_failures`/`next_check_at`; bounded backoff in `_run()` |
| Restart | Existing watched rows reloaded | Reload and honor persisted next-check/report state |
| Local 24-hour deadline | Could end with no explicit semantic outcome | `TIMED_OUT` notice, never `COMPLETED` |
| Duplicate terminal response | Existing inbox/transition identity | Same mechanism plus delivered-report guard |

## 4. Implementation changes and rationale

### 4.1 `bot/watcher.py`

- Removed the `START_TIMEOUT = timedelta(minutes=10)` terminal/no-report branch.
- A confirmed terminal state with no fresh report now:
  - persists the terminal state with `advance_watched_state()`;
  - keeps the watch row;
  - continues trying to retrieve the report;
  - sends no success notification and does not remove the watch.
- Added `_notify_terminal_timeout()` for the local 24-hour report-wait deadline. Its
  message explicitly says the task was **not** considered complete and records a
  `timeout` inbox event before stopping tracking.
- Added durable `last_verified_at`, `report_state`, `poll_failures`, and `next_check_at`
  updates after successful/failed provider polls.
- Added bounded polling backoff in `Watcher._run()`: the next loop delay doubles from
  `WATCHER_INTERVAL` per consecutive batch failure, capped at 15 minutes. `tick()` remains
  immediate for existing callers/tests; `_run()` owns the production delay.
- Added `_wait_for_initial_check()` so a restarted process honors persisted
  `next_check_at` instead of making an immediate duplicate request.
- Persisted report-retrieval state: `pending` after a terminal state without a report,
  `delivered` after report delivery, `not_required` for failure-like terminal states,
  and `timed_out` for the local 24-hour deadline.
- Preserved the existing transient `ApiError` behavior: no state change and no watch
  removal; the failed batch is persisted with an incremented failure count and next
  check time.
- Added a delivered-report guard so a failed watch deletion cannot resend a terminal
  report after restart.

### 4.2 `bot/db.py`

- Added nullable `watched.last_verified_at`, `report_state`, `poll_failures`, and
  `next_check_at` columns to the schema and a non-destructive `ALTER TABLE` migration
  for existing databases.
- Added those fields to `Watched`, `list_watched()`, and `get_watched()`.
- Added `mark_watched_verified()` (also resets failure count and records next check),
  `mark_poll_failure()`, `set_poll_next_check()`, and `set_report_state()`.
- `mark_submitted()` clears `last_verified_at`, `report_state`, `poll_failures`, and
  `next_check_at`, because a previous cycle's success does not verify a new prompt.
- New watch lifecycles clear the same per-cycle fields.

### 4.3 `bot/messages.py`

- Added explicit local semantic states:
  `TASK_RUNNING`, `TASK_COMPLETED`, `TASK_FAILED`, `TASK_CANCELLED`,
  `TASK_UNKNOWN`, and `TASK_TIMED_OUT`.
- Added `task_state()` mapping. Only `finished` maps to COMPLETED; `error`, `stuck`, and
  `sandbox_error` map to FAILED; `cancelled` (and normalized `canceled`) maps to CANCELLED;
  unknown values map to UNKNOWN. The mapper lowercases its input.
- Added the `cancelled` provider value/label and normalized the US spelling `canceled`.
- Preserved the existing `waiting_for_confirmation` notification behavior; it is not
  mapped to COMPLETED.

### 4.4 Tests

- Updated the old U01 test that expected removal at 10 minutes.
- Added `tests/test_openhands_wait_until_terminal.py` with 18 focused tests covering the
  required scenarios, including repeated transient failures, persisted backoff, restart
  association, and restart duplicate prevention.

## 5. Database/persistence changes

Only non-destructive columns were added to the existing `watched` table:

```text
watched.last_verified_at TEXT
watched.report_state    TEXT
watched.poll_failures   INTEGER NOT NULL DEFAULT 0
watched.next_check_at   TEXT
```

No new database, owner, worker, queue, external service, or table was introduced.
`last_verified_at` and `next_check_at` are diagnostic/recovery metadata; neither is used
as proof of completion. `report_state` is independent of provider state.

Existing `last_state` remains the last observed provider state. On terminal-without-
report it is allowed to be terminal while the row remains watched for report retrieval.

Recovery design:

- `conversation_id` remains the primary key and existing association to the chat/task.
- `last_state` preserves the last known provider state across restart.
- `last_verified_at` records the last successful status check.
- `poll_failures` and `next_check_at` preserve failure count and the next scheduled
  check; `_wait_for_initial_check()` honors them after restart.
- `report_state` preserves whether the final report is pending, delivered, not required,
  or timed out.
- Existing `submitted_at`, `watch_seq`, `pending_delivery_state`, and inbox identity remain
  the durable mechanisms for report freshness and duplicate delivery prevention.

## 6. Status transition rules

| Observed condition | Local semantic state | Action |
|---|---|---|
| `running`, `idle`, `paused` | `RUNNING` | Continue polling |
| `finished` with fresh report | `COMPLETED` | Deliver report once, set `report_state=delivered`, then remove watch |
| `finished` without fresh report | `COMPLETED` provider state, report pending | Keep watch; set `report_state=pending`; retry report; no success delivery |
| `error`, `stuck`, `sandbox_error` | `FAILED` | Notify failure, set `report_state=not_required`, then remove watch |
| `cancelled` / `canceled` | `CANCELLED` | Notify cancellation, set `report_state=not_required`, then remove watch |
| `waiting_for_confirmation` | `UNKNOWN` semantic state | Preserve existing waiting notification behavior; never COMPLETED |
| Unknown/missing provider state | `UNKNOWN` | Keep watch; never COMPLETED |
| Provider/network `ApiError` | No transition | Persist failure count + next check; keep watch; bounded backoff |
| 24-hour local wait deadline | `TIMED_OUT` | Set `report_state=timed_out`; explicit timeout notice; remove watch; never COMPLETED |
| Database error during transition | No transition | Keep watch; fail safely |

## 7. Tests added and exact results

### 7.1 Focused lifecycle tests

```text
python -m pytest -q \
  tests/test_openhands_wait_until_terminal.py \
  tests/test_u01_watcher.py \
  tests/test_watcher.py
116 passed, 28 warnings in 11.93s
```

The new file covers:

1. Running after 10 minutes remains tracked.
2. Temporary polling timeout does not complete.
3. Missing final report does not imply success.
4. Completion after multiple polling cycles is delivered.
5. Provider failure is FAILED.
6. Confirmed cancellation is CANCELLED.
7. Unknown provider state is not success.
8. Missing status field is UNKNOWN, not success.
9. Transient provider errors are retried safely.
10. Repeated transient failures do not complete and persist failure/backoff state.
11. Restart recovery resumes a running task and preserves its association.
12. Duplicate terminal responses do not duplicate delivery.
13. Restart after delivery does not resend.
14. Delayed report is still delivered after the old 10-minute point.
15. Terminal report timeout is TIMED_OUT, not COMPLETED.
16. Permanent database error does not complete.
17. Semantic status mapping never maps unknown to COMPLETED.
18. Poll backoff is bounded by the 15-minute cap.

The fake client/bot exercise the real `Watcher`, real SQLite `Database`, real inbox and
notification persistence paths. No network or production task was used.

No tests were skipped. The focused suite and full Python suite were both run after the
final code changes.

### 7.2 Broader Python regression

```text
python -m pytest -q
4401 passed, 74 warnings in 335.47s (0:05:35)
```

### 7.3 Frontend regression

```text
node --test tests/frontend/*.test.js
280 passed, 0 failed
```

### 7.4 Static/security checks

```text
python -m pyflakes bot/ automation/ tools/ main.py tests/
exit 0

python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613
No issues identified; High severity 0

python -m pip_audit -r requirements-dev.txt
No known vulnerabilities found

git diff --check
exit 0
```

## 8. Remaining limitations and unresolved risks

- **Live provider verification is UNVERIFIED.** No real OpenHands task, Telegram
  message, Mini App deployment, or production service was used. Tests use fakes.
- **`cancelled` provider value:** it is recognized and normalized if OpenHands returns
  it, but it was not independently observed in the repository's documented provider
  sample. It is not treated as success.
- **`waiting_for_confirmation`:** existing behavior is preserved; it remains a terminal
  notification state in the current architecture even though `task_state()` maps it to
  UNKNOWN. Changing that broader semantic was outside this task's minimal fix.
- **Missing conversation:** the existing `missing` path still stops a watch after
  `MISSING_LIMIT` repeated absent responses. It never reports COMPLETED, but it is a
  separate provider-absence path and was not redesigned here.
- **Polling cadence:** `WATCHER_INTERVAL` remains the base cadence. `_run()` applies
  bounded exponential backoff on batch fetch failures, capped at 15 minutes; `tick()`
  itself remains immediate so existing direct callers and tests keep their semantics.
  No provider-specific rate-limit policy was added beyond existing `RetryAfter` handling
  in notification paths.
- **Backoff execution path:** the backoff delay is applied by `Watcher._run()`; a direct
  caller of `tick()` (including tests) does not sleep. The persisted
  `poll_failures`/`next_check_at` fields are still written and honored by `_run()` after
  restart. The actual `_run()` sleep/initial-wait timing was not exercised by a timing
  test; only `_backoff_delay()` and persisted state were directly tested.
- **Mini App:** no Mini App code was changed. It continues to display the live provider
  status through the existing service path; live UI behavior was not exercised.
- **No commit/push:** implementation exists only in the working tree.

## 9. Safety confirmation

- No `git reset`, `git clean`, force operation, broad deletion, or broad `git add`.
- No commit, push, PR, merge, deployment, release, or branch switch.
- Autopush remains inactive/disabled.
- No production OpenHands, Telegram, Canary, or provider API calls.
- No application database opened or migrated in a live environment.
- No unrelated R7/D-05 work or FIND-02 remediation was touched.
- Existing task/conversation associations were preserved; `conversation_id` remains the
  primary key and restart tests assert the same association.
- Pre-existing modified/untracked files were preserved.

## 10. Verdict and next step

**Verdict: `PASS_WITH_NOTES`.**

The local 10-minute false-termination path is removed; running tasks remain tracked,
terminal states are distinguished, delayed reports are retrieved, restart recovery is
covered by tests, and duplicate terminal delivery remains protected by the existing
inbox/transition identity. Poll failures are persisted with bounded backoff, and report
retrieval state is durable and independent of provider state.

This is implementation-review status only. Independent review, owner acceptance, and a
live provider/Telegram/Mini App verification remain separate gates.

**Recommended next step:** run an independent review of this diff, then perform one
controlled non-production integration check against a disposable OpenHands
conversation to verify live status/report timing and Mini App display without submitting
a real user task.
