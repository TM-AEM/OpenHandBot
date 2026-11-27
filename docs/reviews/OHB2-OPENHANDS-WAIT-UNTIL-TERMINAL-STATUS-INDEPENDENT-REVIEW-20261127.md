# OHB2-OPENHANDS-WAIT-UNTIL-TERMINAL-STATUS — Independent Review

**Task ID:** `OHB2-OPENHANDS-WAIT-UNTIL-TERMINAL-STATUS-INDEPENDENT-REVIEW`
**Review date:** 2026-11-27
**Mode:** strict independent review, read-only
**Verdict:** `PASS_WITH_NOTES`

## 1. Review objective and independence

This review independently verifies whether the implementation removes the premature
10-minute watcher termination and safely tracks submitted OpenHands tasks until a
provider-confirmed terminal state and report retrieval.

The implementation report was used only as a map of claimed scope. Source code,
migrations, callers, tests, and test results were inspected and executed independently.
No production OpenHands, Telegram, Mini App, or paid provider call was made. No live
integration check was performed.

## 2. Actual baseline and workspace state

| Item | Actual value |
|---|---|
| Branch | `agent/r6-review-delivery` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` |
| HEAD tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| Staged | 0 files |
| Modified tracked | 15 files |
| Untracked, `git status` entries | 94 entries |
| Untracked, file-level (`git ls-files --others --exclude-standard`) | 110 files |
| Relevant ignored | `.venv/`, `node_modules/`, `__pycache__/`, `.pytest_cache/` |
| `git diff --check` | exit 0 |
| HEAD after review | unchanged |

The reported HEAD and tree match the actual workspace. The reported
`15 modified / 94 untracked / 0 staged` matches `git status` entry counts. The
file-level untracked count is 110, because Git status collapses untracked directories
while `git ls-files` enumerates files. This is a reporting-definition difference, not
an implementation discrepancy. After this review report was created, the status-level
untracked count is 95; the implementation files are unchanged.

`git diff --stat` shows 15 modified tracked files with 5,178 insertions. The report
identifies 12 as pre-existing and 3 as implementation/test files. The workspace has
many pre-existing R7/review artifacts; without a pre-task snapshot, the exact
attribution of every pre-existing line cannot be proven from the current tree alone.
The task-relevant tracked files are:

- `bot/watcher.py`
- `bot/messages.py`
- `bot/db.py` (the new watched-tracking portion)
- `tests/test_u01_watcher.py`

The task-relevant untracked files are:

- `tests/test_openhands_wait_until_terminal.py`
- `docs/reviews/OHB2-OPENHANDS-WAIT-UNTIL-TERMINAL-STATUS-IMPLEMENTATION-REPORT-20261127.md`

## 3. Files and code paths reviewed

Source and lifecycle:

- `bot/watcher.py` — `_run`, `_wait_for_initial_check`, `_backoff_delay`, `tick`,
  `_process_submitted`, `_process_legacy`, timeout paths, `_notify`, pending-delivery
  recovery, missing-conversation path.
- `bot/db.py` — `Watched` model, schema creation, `_migrate`, `add_watched`,
  `mark_submitted`, `list_watched`, `get_watched`, `advance_watched_state`,
  `mark_watched_verified`, `mark_poll_failure`, `set_poll_next_check`,
  `set_report_state`, `remove_watched_if_seq`.
- `bot/messages.py` — `get_status`, `is_terminal`, `task_state`, labels and terminal
  sets.
- `bot/openhands_client.py` — `parse_timestamp`, `get_reply_since`, agent report
  extraction and timestamp filtering.
- `bot/app.py` — watcher startup.
- `bot/outbox.py` — submitted-at persistence and watch completion.
- `bot/handlers.py`, `bot/web/services.py` — manual watch and display paths.
- `bot/notifier.py` — watched-row coordination and terminal notification ownership.
- `bot/config.py` — `WATCHER_INTERVAL` bounds.

Tests:

- `tests/test_openhands_wait_until_terminal.py` — all 18 tests.
- `tests/test_u01_watcher.py` — updated and existing U01 tests.
- `tests/test_watcher.py`, `tests/test_messages.py`, `tests/test_notifier.py`.
- Migration and status probes in temporary directories outside the repository.

## 4. Findings ranked by severity

### P2-1 — Terminal state changes after a pending report are not notified

**Location:** `bot/watcher.py:460-470` and `bot/watcher.py:484-491`.

`transition` is computed from `w.last_state`. After a terminal `finished` response with
no report, the implementation deliberately advances `last_state` to `finished` and sets
`report_state=pending`. If a later provider response is `error`, `stuck`, `sandbox_error`,
or `cancelled` with still no report, `transition` is false because the previous recorded
state is already terminal. The condition at line 470 therefore does not send a failure or
cancellation notification. The task remains watched and eventually reaches the 24-hour
`TIMED_OUT` notice, but the user is not told that the provider reported failure or
cancellation.

Independent probe:

```text
tick 1: finished, no report -> sent=0, last_state=finished, report_state=pending
tick 2: error, no report    -> sent=0, last_state=error, report_state=pending
tick 3: cancelled, no report-> sent=0, last_state=cancelled, report_state=pending
```

Impact: delayed/missing failure and cancellation notices. This is not a false-success
path and does not lose the watch, but it is a real status-notification gap. The new tests
only cover `error` and `cancelled` directly from a non-terminal `running` state.

Required correction: notify on a new terminal state when `report_state` is pending or
when `w.last_state != state`, not only on a non-terminal-to-terminal transition. Add
regression tests for `finished→error`, `finished→cancelled`, and
`finished→sandbox_error` with no report.

### P2-2 — Duplicate terminal report delivery after a `set_report_state` database failure

**Location:** `bot/watcher.py:472-482`; `_notify` clears pending delivery at
`bot/watcher.py:788` before the caller writes `report_state`.

Normal path:

1. `_notify` sends the report and clears `pending_delivery_state`.
2. `_process_submitted` then calls `set_report_state(REPORT_STATE_DELIVERED)`.
3. `remove_watched_if_seq` removes the watch.

If step 2 raises a database error, the outer per-chat handler leaves the row watched.
The next tick has no `report_state=delivered` marker, no pending-delivery marker, and the
same report is still returned by `get_reply_since`; `_notify` sends the report again.

Independent probe with `db.set_report_state` forced to raise after a successful send:

```text
first tick:  sent=1, watched=True, report_state=None
second tick: sent=2, watched=True
```

Impact: duplicate terminal messages under a database write failure. The implementation
does not claim exactly-once Telegram delivery, so this is not a new exactly-once
violation, but the implementation report's statement that the delivered guard prevents
duplicate report delivery is too broad. The guard works only when the delivered-state
write succeeds.

Required correction: make report delivery state and watch removal durable in the same
transaction or a write-ahead marker that `_notify`/recovery honors before sending again.
Add a regression test that injects a failure in `set_report_state` after successful
Telegram delivery.

### P2-3 — Semantic task outcomes are not wired into runtime and cannot represent pending report state

**Location:** `bot/messages.py:39-70`; runtime watcher uses raw statuses, not
`task_state()`.

`task_state("finished")` returns `TASK_COMPLETED` regardless of
`watched.report_state=pending`. `TASK_TIMED_OUT` is defined but is not used outside the
new tests. `grep` finds no runtime use of `task_state` or `TASK_TIMED_OUT` in
`bot/`, `automation/`, `tools/`, or `main.py`.

Impact: the implementation has a semantic-status API, but the actual watcher, Mini App
service, and notifier still use raw provider status. If future UI or reporting code calls
`task_state(last_state)`, it can show COMPLETED while the final report is still missing.
This is a design/contract gap rather than a current runtime false-success path.

Required correction: either persist/derive a semantic outcome that includes
`report_state` (for example, `finished + pending` must not be `completed`), or remove
the unused public semantic API until it is integrated. Add a test that asserts the
pending-report case is not COMPLETED.

### P3-1 — `canceled` and `cancelled` are not fully consistent at the helper level

**Location:** `bot/messages.py:46-48`, `bot/messages.py:90-92`.

`get_status()` and `task_state()` normalize `canceled` to `cancelled`, but
`DONE_STATES`/`TERMINAL_STATES` contain only `cancelled`. Direct calls show:

```text
is_terminal("canceled") -> False
task_state("canceled")  -> "cancelled"
get_status({"execution_status": "canceled"}) -> "cancelled"
```

Current watcher paths call `get_status()` first, so the actual watcher behavior is
normalized. The inconsistency remains for direct helper callers and future code.

Required correction: normalize in `is_terminal()` or include both spellings in the
terminal sets; add a direct helper test.

### P3-2 — Backoff can be shorter than a configured base interval above 900 seconds

**Location:** `bot/watcher.py:207-210`, `bot/watcher.py:189-205`; configuration allows
`WATCHER_INTERVAL` up to 3,600 seconds (`bot/config.py:355-365`).

Independent probe:

```text
interval 25   -> failure 1: 25 s
interval 900  -> failure 1: 900 s
interval 3600 -> failure 1: 900 s
initial wait for next_check_at = +30 min -> 900 s
```

The cap is correctly bounded at 15 minutes for the default 25-second interval. For a
configured interval above 15 minutes, however, the first failure makes the watcher poll
more often than the configured base interval. This is an edge-case operational risk,
not a default-configuration regression.

Required correction: use a floor of `max(self._interval, min(...))` or document that
intervals above the backoff cap are intentionally shortened. Add a high-interval test.

### P3-3 — Missing-conversation path still stops tracking after three absences

**Location:** `bot/watcher.py:425-434`.

`_handle_missing()` sends an explicit "no longer exists / tracking stopped" message and
removes the watch after `MISSING_LIMIT` (3) cycles. It does not report COMPLETED, so it is
not a false-success path. If the provider absence is transient rather than a confirmed
deletion, however, a task can lose tracking before its actual terminal state. The
implementation report labels this as an existing separate path and the independent
review confirms the behavior.

Classification: operational risk, not a blocker for the core 10-minute fix. It should
be either accepted as a deletion policy or redesigned to distinguish confirmed deletion
from transient unavailability.

### P3-4 — `waiting_for_confirmation` is UNKNOWN semantically but still uses the terminal wording

**Location:** `bot/watcher.py:718-720`; `bot/messages.py:68-70`.

`task_state("waiting_for_confirmation")` is `TASK_UNKNOWN`, and the existing U01 test
requires a notification. The notification header is still `"انتهى الشات"` ("chat
finished") and the watch is removed. It is not a COMPLETED report and the body adds
"waiting for your confirmation", but the wording can be read as completion.

Classification: acceptable existing behavior with a wording risk, not a false-success
path.

### P3-5 — Test gaps around the actual restart and duplicate boundaries

The 18 tests are real `Watcher`/SQLite tests and are useful, but they do not cover:

- `finished`/terminal state changing to a different terminal state with no report
  (P2-1);
- a database failure after successful report delivery (P2-2);
- migration of an old `watched` table (tested independently here, not in the repo);
- the actual `_run()` sleep path and `next_check_at` initial wait (only
  `_backoff_delay()` is tested);
- `report_state=delivered` when watch removal fails;
- `mark_submitted()` reset behavior (independently probed here, not in the repo);
- `canceled` through the watcher rather than only `task_state`;
- a transient missing-conversation sequence after a pending report.

## 5. Lifecycle and status assessment

### 10-minute termination

The original failure is removed from the watcher lifecycle. `grep -R START_TIMEOUT bot
tests` finds only `bot/web/runner.py` (`_START_TIMEOUT = 10.0`), which is unrelated to
the watcher. `Watcher` no longer imports or branches on a 10-minute completion constant.

The running-task test passes:

```text
test_running_after_ten_minutes_remains_tracked PASSED
```

The task remains watched and `last_state` remains `running` after the old threshold.

### Terminal state without a report

For a submitted task, `_process_submitted()`:

1. reads the report with `get_reply_since(submitted_at)`;
2. if a report exists, delivers it;
3. if no report exists for `finished`, sets `report_state=pending`, persists
   `last_state=finished`, and returns without removing the watch;
4. for failure-like states, sends the failure notification without requiring a report
   on a real transition;
5. retries report retrieval on later ticks.

The focused tests confirm no premature removal for `finished` without a report and
delayed delivery when the report arrives later.

The P2-1 gap is the later terminal-state change case described above.

### Status mapping

| Provider/local condition | Observed implementation behavior | Assessment |
|---|---|---|
| `running`, `idle`, `paused` | `task_state` RUNNING; watcher keeps watching | correct |
| `finished` with fresh report | report delivered, delivered state, watch removed | correct |
| `finished` without report | `report_state=pending`, watch retained | correct |
| `error`, `stuck`, `sandbox_error` | FAILED notification on real transition | correct for direct transition; P2-1 for later transition |
| `cancelled` | CANCELLED notification; `canceled` normalized by `get_status` | runtime path correct; P3-1 helper inconsistency |
| `waiting_for_confirmation` | UNKNOWN semantic; notification and removal | not COMPLETED, but wording risk P3-4 |
| unknown/missing status | UNKNOWN, watch retained | correct |
| local 24-hour deadline | `report_state=timed_out`, TIMEOUT notice, no COMPLETED | core correct; semantic state not persisted as a task outcome |

`task_state()` is not used by runtime code. This makes the status mapping test useful as
a unit contract but not evidence that the lifecycle emits those outcomes. P2-3 records
this gap.

### Transient and permanent errors

- `get_conversations` `ApiError`: `mark_poll_failure()` increments `poll_failures`,
  writes `next_check_at`, leaves `last_state` and `report_state` unchanged, and returns
  without notification. The test verifies this.
- `get_reply_since` `ApiError`: leaves the watch and recorded state unchanged; the U01
  test verifies this.
- `note_transition` database failure: `_notify` does not send and the outer per-chat
  handler leaves the watch. The new test verifies this narrow case.
- `set_report_state` database failure after a successful send: duplicate-delivery risk
  (P2-2), not a false-success path.

### Backoff and polling

`_backoff_delay()` is bounded for the default interval and the new tests verify the
default 25/50/900 sequence. The actual `_run()` timing path is not directly tested. The
high-interval edge is P3-2. No unbounded loop or unbounded memory growth was found.

## 6. Database migration and restart recovery

### Migration

Independent probe created a pre-change `watched` table without the four new columns,
inserted an existing row, and opened it with the current `Database`:

```text
columns = conversation_id, title, last_state, chat_id, submitted_at, added_at,
          retry_count, pending_delivery_state, watch_seq,
          last_verified_at, report_state, poll_failures, next_check_at
row = existing values preserved
PRAGMA integrity_check = ok
```

The migration is additive and nullable/defaulted; no existing row was discarded. The
new `poll_failures` column has `NOT NULL DEFAULT 0`. No destructive migration or broad
rewrite was found.

### Restart recovery

`list_watched()` reads the new fields; `Watched` carries them; `mark_submitted()` resets
`last_verified_at`, `report_state`, `poll_failures`, and `next_check_at` for a new
tracking cycle (independently probed and verified).

The restart test closes and reopens the database and confirms the same
`conversation_id` association. `watch_seq` preservation is visible in the persisted row,
but the new test does not explicitly assert it. `_wait_for_initial_check()` reads
`next_check_at` and sleeps for the future minimum, capped at 900 seconds. The actual
`_run()` timing path is not covered by a timing test.

## 7. Duplicate notification and report retrieval

Report retrieval uses `get_reply_since()` and only returns an agent message or
FinishAction with a timestamp strictly greater than `submitted_at`; missing or
unparseable timestamps are ignored. This is the correct anti-stale-report boundary and
is covered by U01 tests.

The normal duplicate path is protected by:
- `report_state=delivered` early removal;
- `pending_delivery_state` recovery;
- inbox `event_key`/`transition_seq` identity.

The normal tests pass, but the guard is not a complete exactly-once mechanism:

- P2-2 shows a duplicate after a `set_report_state` failure.
- `_notify` can send before the delivered marker is durable.
- Timeout/missing `_deliver()` uses event-first recording but does not check whether the
  event was already delivered before sending again.
- No exactly-once Telegram guarantee is claimed by the project, and this review does not
  claim one.

## 8. Independent test and verification results

The system interpreter `/usr/local/bin/python` does not have pytest:

```text
/usr/local/bin/python -m pytest -q tests/test_openhands_wait_until_terminal.py
/usr/local/bin/python: No module named pytest
exit 1
```

The repository virtual environment was used for the requested Python commands:

```text
export PATH="$PWD/.venv/bin:$PATH"

python -m pytest -q tests/test_openhands_wait_until_terminal.py \
  tests/test_u01_watcher.py tests/test_watcher.py
116 passed, 28 warnings in 11.57s
exit 0

python -m pytest -q
4401 passed, 74 warnings in 333.59s (0:05:33)
exit 0

python -m pytest -q tests/test_openhands_wait_until_terminal.py -vv
18 passed in 1.86s
exit 0

python -m pyflakes bot/ automation/ tools/ main.py tests/
exit 0

node --test tests/frontend/*.test.js
tests 280
pass 280
fail 0
cancelled 0
skipped 0
exit 0

python -m pytest -q tests/test_doc_code_parity.py
16 passed in 0.05s
exit 0

python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613
No issues identified.
High severity: 0
Low: 7
Medium: 22
exit 0

python -m pip_audit -r requirements-dev.txt
No known vulnerabilities found
exit 0

git diff --check
exit 0
```

No tests were skipped. The new 18 tests use the real SQLite `Database`, real `Watcher`,
real inbox/notification persistence, and fake OpenHands/Telegram boundaries. They do
not use a mock database.

## 9. Assessment of reported limitations

| Reported limitation | Classification | Evidence and impact |
|---|---|---|
| Live OpenHands/Telegram/Mini App integration unverified | Operational risk / release gate | No live calls were made by design. Source and unit behavior pass; live timing, provider state names, and UI display remain unverified. |
| `cancelled` not observed directly from production | Acceptable note plus P3-1 | `get_status` normalizes both spellings; direct `is_terminal("canceled")` is false. Actual watcher path uses `get_status`. |
| `waiting_for_confirmation` represented as UNKNOWN | Acceptable note plus P3-4 | `task_state` is UNKNOWN; no COMPLETED. Existing notification says "chat finished" and removes the watch, which is a wording/ownership risk. |
| Missing conversation stops after three missing cycles | Operational risk / P3-3 | Explicit stop, not a false completion. A transient provider absence can lose tracking before terminal state. |
| Actual `_run()` sleep timing untested | Test gap / P3-5 and P3-2 | `_backoff_delay` and initial-wait behavior were independently probed; no timing test exercises `_run()` end to end. High configured intervals shorten the first delay. |
| Mini App code unchanged | Acceptable note / release gate | Backend `get_status` remains the display source. No Mini App live behavior was exercised. |
| No exactly-once Telegram delivery guarantee | Acceptable note plus P2-2 | Existing design limitation. The implementation report's delivered-guard claim is not valid across a `set_report_state` failure. |

No reported limitation is a blocker for the specific 10-minute termination fix. P2-1,
P2-2, and P2-3 require correction before the implementation should be considered fully
acceptance-ready for status/report delivery.

## 10. Discrepancies with the implementation report

1. **Untracked count definition:** the report's `94` matches `git status` entries; the
   actual file-level count is `110`. No source discrepancy.
2. **HEAD/tree/status:** match exactly at status-entry level. HEAD and tree are
   unchanged.
3. **Test counts:** independently reproduced 116 focused, 4,401 full, 18 new, 280
   frontend, and 16 doc-parity tests.
4. **Semantic states:** the report describes semantic task states, but `task_state()`
   and `TASK_TIMED_OUT` are not used by runtime code. The report does not establish
   that the watcher emits those semantic states.
5. **Delivered guard:** the report's claim is overbroad. The guard is absent after a
   `set_report_state` database failure (P2-2).
6. **Backoff:** the report says bounded/not aggressive. It is bounded at 900 seconds
   but can be shorter than a configured base interval above 900 seconds (P3-2).
7. **`bot/db.py` scope:** the report says only watched-tracking fields were added to a
   pre-existing R7-modified file. The current diff contains many pre-existing lines;
   without a pre-task snapshot this review cannot independently attribute every line.
8. **No commit/push:** confirmed; HEAD remains at the reported commit.

## 11. Required corrective actions

Before treating the status/report lifecycle as complete:

1. Fix P2-1: notify on a new terminal failure/cancellation even when the previous state
   was terminal but `report_state` is pending; add transition tests.
2. Fix P2-2: make delivered-report state durable before/with the send-completion path,
   or teach recovery to treat a delivered report as sent; add a database-failure test.
3. Fix P2-3: integrate semantic outcome with `report_state`, or remove the unused
   semantic API; add a `finished + pending` test.
4. Fix P3-1: normalize `canceled` in `is_terminal()` and terminal sets.
5. Fix P3-2: ensure backoff never goes below the configured base interval; add a
   high-interval test and an actual `_run()` timing test.
6. Decide and test P3-3: confirm deletion vs transient missing; if transient, preserve
   the watch and persist the miss count.
7. Add migration coverage for an old `watched` schema and a restart test for
   `report_state=pending`.

## 12. Review safety confirmation

This review was strictly read-only for implementation and existing artifacts:

- No implementation file, test, configuration, migration, or existing report was
  edited, formatted, repaired, or deleted.
- The only file created is this independent review report.
- No file was staged or unstaged.
- No `git reset`, `git clean`, force operation, branch switch, or broad deletion was
  performed.
- No commit, push, pull request, merge, deployment, release, or Autopush activation was
  performed.
- No production credentials, production API, Telegram, OpenHands task, Mini App live
  check, or paid inference was used.
- Test-created `.pytest_cache` is ignored by the repository; pre-existing workspace
  changes were preserved.
