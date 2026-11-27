# OHB2-OPENHANDS-WAIT-UNTIL-TERMINAL-STATUS-P2 — Independent Review

**Task ID:** `OHB2-OPENHANDS-WAIT-UNTIL-TERMINAL-STATUS-P2-INDEPENDENT-REVIEW`
**Date:** 2026-11-27
**Verdict:** `PASS_WITH_NOTES`
**Mode:** independent read-only audit + failure injection + regression verification
**Target report:** `docs/reviews/OHB2-OPENHANDS-WAIT-UNTIL-TERMINAL-STATUS-P2-REMEDIATION-REPORT-20261127.md`

The parent task is **not closed**. Owner acceptance remains a separate decision.

## 1. Reviewer environment and independence

- Repository: `/workspace/project/OpenHandBot`
- Branch: `agent/r6-review-delivery`
- Python: repository `.venv` (Python 3.13.15); Node.js available locally.
- The target implementation report was read but its claimed results were **not trusted**.
  Every result below comes from source inspection, the repository's own tests, or
  independent temporary probes under `/tmp`.
- No production OpenHands/Telegram credentials, APIs, conversations, paid inference,
  deployment, or live infrastructure were used.
- This was a read-only review. No implementation file, existing test, configuration,
  schema, or existing report was modified. The only repository artifact created is this
  report.
- Temporary probe files and SQLite databases were created under `/tmp` and removed after
  use.

## 2. Exact baseline and final Git state

Baseline recorded before running tests or creating this report:

| Item | Value |
|---|---|
| Repository | `/workspace/project/OpenHandBot` |
| Branch | `agent/r6-review-delivery` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` |
| HEAD tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| Staged files | 0 |
| Modified tracked files | 18 |
| Untracked status entries | 96 |
| Untracked files | 112 |
| Ignored | `.openhands/`, `.pytest_cache/`, `.venv/`, `__pycache__/`, `node_modules/`, `dist/` |

Final state after adding this review report is expected to be 18 modified tracked files,
0 staged files, 97 untracked status entries, and 113 untracked files. The only difference
is this report; no source or test was touched by the review.

### Attribution limitation

The working tree contains pre-existing changes from earlier tasks. The review did not
have a clean pre-task snapshot and therefore does **not** attribute every modified line
to P2. Evidence used for attribution:

- `bot/web/services.py`, `bot/web/static/app.js`, and `bot/web/static/styles.css` were
  newly modified relative to the prior baseline and contain the P2-3 Mini App changes.
- `bot/db.py`, `bot/messages.py`, and `bot/watcher.py` contain P2-specific hunks mixed
  with pre-existing changes.
- `tests/test_openhands_wait_until_terminal.py` and the target report are untracked.
- Large pre-existing changes such as auto-review schema/worker code are visible in the
  current diff but are **not** part of this P2 remediation. They were not treated as P2
  evidence.

## 3. Files and code paths inspected

- `bot/watcher.py`
  - `_terminal_transition()`: lines 456-464
  - `_reconcile_report_delivery()`: lines 466-500
  - `_process_submitted()`: lines 502-577
  - timeout paths: lines 579-603
  - `_deliver()` and `_notify()`: lines 605-631 and 788-868
  - inbox event identity: lines 667-688
  - `_recover_pending_events()` / `_deliver_pending_event()`: lines 338-417
- `bot/db.py`
  - report states: lines 482-489
  - `set_report_state()`: lines 4223-4229
  - `get_notification_state()`: lines 6545-6557
  - `note_transition()`: lines 6630-6681
  - `add_inbox_event()`: lines 6850-6882
  - `find_inbox_by_event_key()`: lines 7141-7149
  - `mark_inbox_delivered()`: lines 7322-7336
- `bot/messages.py`
  - semantic states and `task_state()`: lines 37-119
  - `get_status()` / `is_terminal()`: lines 122-141
  - Telegram formatting: lines 189-200
- `bot/web/services.py`
  - `_conversation_dto()`: lines 265-278
  - `_list_item()` / `_watched_states()`: lines 663-681
  - list/detail/status/update-repo call sites: lines 643-707 and 887-888
- `bot/web/static/app.js`: `statusPill()` lines 868-872; detail card line 945
- `bot/web/static/styles.css`: semantic status colors lines 162-169
- `bot/handlers.py`: `/status` rendering line 1883
- `tests/test_openhands_wait_until_terminal.py`: all 30 tests, especially lines 343-577
- Existing watcher/notifier tests relevant to delivery: `tests/test_watcher.py`,
  `tests/test_u01_watcher.py`, `tests/test_notifier.py`

## 4. P2-1 — Terminal transitions

`_terminal_transition()` is:

```python
is_terminal(state) and (
    not is_terminal(w.last_state) or w.last_state != state
)
```

This correctly treats a different terminal state as a new transition while leaving
repeated identical terminal polling idempotent.

Independent probe results (real `Database` and real `Watcher`, fake OpenHands/Telegram
boundaries; temp SQLite outside the repository):

| Scenario | Initial durable state | Operation | Telegram calls / accepted | Final durable state | Result |
|---|---|---|---|---|---|
| `finished` → `error`, no report | `running` | tick at +11m; tick at +12m | 0 / 0; 1 / 1 | watch removed; error message contains `خطأ` | PASS |
| `finished` → `cancelled` | `running` | same | 0 / 0; 1 / 1 | watch removed; message contains `اتلغى` | PASS |
| `finished` → `canceled` | `running` | same | 0 / 0; 1 / 1 | watch removed; message contains `اتلغى` | PASS |
| Repeated identical terminal with two `TelegramError` attempts | `finished`, `report_state=pending` | two failed ticks | 1 / 0; 1 / 0; retry_count=2 | watch still present, no duplicate accepted send | PASS (safe retry) |
| Retry after failed transition, then success | `finished`, pending | fail, fail, success, extra tick | 1/0, 1/0, 1/1, 0/0 | watch removed after success; no fourth send | PASS |
| Restart after failed transition | `finished`, pending | restart; tick success; extra tick | 1/0; 1/1; 0/0 | watch removed; no duplicate | PASS |
| Report remains pending at transition | `finished`, pending | tick at +11m; error tick | 0/0; 1/1 | failure notification, never completion | PASS |
| Latest provider state after failed notification | `finished`, pending | error tick with `TelegramError` | 1 / 0 | `watched.last_state=finished`, `report_state=pending`; `notification_state.status=error` | **GAP (R-P2-02)** |

The failure/cancellation messages do not become completion messages: `task_state("error")`
is `failed`, `task_state("cancelled")` and `task_state("canceled")` are `cancelled`.
No conversion of failure or cancellation into completion was observed.

## 5. P2-2 — Report delivery and uncertainty

### 5.1 Durable model observed in source

- `sending` is written before `_notify()` performs the external send
  (`bot/watcher.py:538`).
- `_notify()` records the event before sending, calls `send_long`, then
  `mark_inbox_delivered()` after a successful send (`bot/watcher.py:814-847`).
- A `TelegramError` resets the report state to `pending` for safe retry
  (`bot/watcher.py:542-551`).
- After a successful send, the durable marker is written; failure leaves `sending`
  (`bot/watcher.py:553-560`).
- `_reconcile_report_delivery()` looks up the event by the durable key
  `conversation_id|terminal|watch_seq|transition_seq`:
  - `delivered` ⇒ record `delivered` and remove the watch;
  - `pending`/`failed`/absent ⇒ record `uncertain` and do not auto-resend
    (`bot/watcher.py:466-500`).
- The event key includes conversation, watch cycle, and transition epoch
  (`bot/watcher.py:686-688`), preventing cross-conversation matching and stale
  transition reuse. `find_inbox_by_event_key()` is keyed by that value.

### 5.2 Failure-injection matrix

All probes used a real SQLite `Database`, real `Watcher.tick()`, a fake OpenHands client,
and a fake Telegram bot that counts send invocations and accepted sends.

| # | Initial durable state | Operation | Telegram calls / accepted | Durable event | Final report state | Automatic resend? | Outcome |
|---|---|---|---|---|---|---|---|
| 1 | running, no report state | fake `TelegramError` on send; then normal retry | 1/0; 1/1 | pending; then delivered | pending; then delivered + removed | No blind resend; safe retry after confirmed pre-acceptance failure | provably not delivered first; delivered after retry |
| 2 | running, no report state | normal send | 1/1 | delivered | delivered, watch removed | No | provably delivered |
| 3 | running, no report state | send accepted; `set_report_state(delivered)` raises | 1/1; 0/0 | delivered | sending; then delivered + removed | No | provably delivered; no duplicate |
| 4 | running, no report state | generic `RuntimeError` from Telegram boundary | 1/0 (acceptance unknown) | pending | sending; then uncertain | No | uncertain |
| 5 | running, `report_state=sending` | restart; tick | 0/0 | none | uncertain | No | uncertain |
| 6 | running, `report_state=uncertain` | restart; tick | 0/0 | none | uncertain | No | uncertain |
| 7 | running, `report_state=sending` | durable event pre-marked delivered; tick | 0/0 | delivered | delivered, watch removed | No | provably delivered |
| 8 | running, `report_state=sending` | durable event pending; tick | 0/0 | pending | uncertain | No | uncertain |
| 9 | running, `report_state=sending` | durable event missing; tick | 0/0 | none | uncertain | No | uncertain |
| 10 | running, `report_state=uncertain` | two ticks | 0/0 | none | uncertain | No | uncertain |
| 11 | running, `report_state=uncertain` + pending event | tick; mark event delivered; tick | 0/0; 0/0 | pending; delivered | uncertain; delivered + removed | No | provably delivered after evidence |
| 12 | running, no report state | `TelegramError`; normal retry | 1/0; 1/1 | pending; delivered | pending; delivered + removed | No blind resend; safe retry | provably delivered after retry |
| 13 | `finished`, `report_state=sending` + delivered event for a different status (`error`) | tick | 0/0 | delivered (mismatched) | uncertain | No | conservative; no false delivered |

Additional safety checks:

- **Sending before external send:** a fake bot callback inspected the row during the send
  call and observed `report_state='sending'`.
- **Delivered without evidence:** missing and pending events produced `uncertain`, never
  `delivered`.
- **No blind duplicate:** every uncertain/missing/pending scenario produced zero
  additional send invocations.
- **Recovery after confirmed pre-acceptance failure:** retry produced exactly one accepted
  send and then removed the watch.
- **No exactly-once claim:** source comments and the target report explicitly disclaim
  exactly-once delivery; the uncertainty window is documented.
- **Cross-conversation / stale key:** the event key includes conversation ID and
  `watch_seq`; a delivered event with a mismatched transition status did not cause a
  resend or false delivered state.

## 6. P2-3 — Provider state versus workflow state

`task_state(status, report_state)` and `task_state_label()` were exercised directly and
through `_conversation_dto()`:

| Provider state | Report state | `task_state` | Label | Provider `status` / `state_label` | Result |
|---|---|---|---|---|---|
| running | None | running | شغال | running / شغال | PASS |
| finished | None | provider_finished | المزود أنهى التنفيذ | finished / منتهي | PASS |
| finished | pending | report_pending | التقرير قيد الانتظار | finished / منتهي | PASS |
| finished | sending | report_available | التقرير جاهز (قيد التسليم) | finished / منتهي | PASS |
| finished | delivered | completed | مكتمل | finished / منتهي | PASS |
| finished | uncertain | report_uncertain | تسليم التقرير غير مؤكد | finished / منتهي | PASS |
| error | any | failed | فشل | error / خطأ | PASS |
| cancelled / canceled | any | cancelled | اتلغى | cancelled / اتلغى | PASS |
| finished | timed_out | timed_out | انتهت المهلة | finished / منتهي | PASS |
| running | timed_out | running | شغال | running / شغال | **GAP (R-P2-01)** |
| unknown | timed_out | unknown | غير معروف | unknown / غير معروف | **GAP (R-P2-01)** |
| waiting_for_confirmation | any | unknown | غير معروف | waiting... / مستني تأكيد | P3-4 observation |

Required assertions:

1. **finished alone not completed while report pending/uncertain:** PASS.
2. **Provider status distinguishable from workflow status:** PASS; `status`/`state_label`
   remain provider facts, `task_state` is additive.
3. **Mini App not treating finished as delivery proof:** PASS for `_conversation_dto`;
   `finished + pending` is `report_pending`, not `completed`.
4. **Telegram/Mini App consistency:** Telegram `/status` still renders provider
   `state_label` only (`bot/handlers.py:1883`), while Mini App renders workflow
   `task_state_label`. It does not claim completion, but labels are not identical; see
   R-P2-03.
5. **timed_out not successful completion:** PASS for `finished + timed_out`; it maps to
   `timed_out`, not `completed`.
6. **Restart/reconciliation does not regress delivered to pending or uncertainty to
   success:** PASS in scenarios 7, 11, and 12; no regression or false success observed.

## 7. Architecture and approved-decision compliance

- One bot process + existing ASGI process; no new process or worker was introduced by P2.
- One authoritative SQLite owner; P2 uses the existing `Database`, watcher, and inbox
  mechanisms.
- No new database owner, worker system, or parallel delivery subsystem.
- No P2 schema migration: only new report-state values (`sending`, `uncertain`) on the
  existing `watched.report_state` column. The larger schema changes visible in the
  working tree are pre-existing auto-review work, not P2.
- Existing conversation/task associations remain untouched.
- No exactly-once delivery claim; the uncertainty policy is explicit and conservative.
- No P2 changes to approved R7 decisions, D-05, or FIND-02.
- No unrelated feature activation or scope expansion was observed in the P2-specific
  hunks.

## 8. Independently executed tests

```text
export PATH="$PWD/.venv/bin:$PATH"

python -m pytest -q tests/test_openhands_wait_until_terminal.py \
  tests/test_u01_watcher.py tests/test_watcher.py
128 passed, 28 warnings in 13.26s
exit 0

python -m pytest -q tests/test_openhands_wait_until_terminal.py -vv
30 passed in 3.20s
exit 0

python -m pytest -q
4413 passed, 74 warnings in 339.51s (0:05:39)
exit 0

python -m pyflakes bot/ automation/ tools/ main.py tests/
exit 0

node --test tests/frontend/*.test.js
tests 280, pass 280, fail 0, cancelled 0, skipped 0
exit 0

python -m pytest -q tests/test_doc_code_parity.py
16 passed in 0.05s
exit 0

git diff --check
exit 0

python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613
High severity: 0; Low: 7; Medium: 22
exit 0

python -m pip_audit -r requirements-dev.txt
No known vulnerabilities found
exit 0
```

No test was skipped. The new regression tests exercise the real `Watcher`/`Database`
path with fake external boundaries; they are not merely mocked helper assertions. The
two gaps below are not covered by the existing new tests.

## 9. P3 observations — status only

| ID | Observation | Status | Evidence |
|---|---|---|---|
| P3-1 | `is_terminal("canceled")` helper inconsistency | Still present | `bot/messages.py:139-141`; probe printed `False`; `get_status()` normalizes to `cancelled` at lines 130-132 |
| P3-2 | Backoff can be shorter than configured `WATCHER_INTERVAL` above 900s | Still present | `bot/watcher.py:210`; probe with interval 1200 returned 900.0 |
| P3-3 | Missing-conversation tracking stops after three cycles | Still present | `MISSING_LIMIT=3` at line 57; `_handle_missing()` lines 428-437 |
| P3-4 | `waiting_for_confirmation` wording/terminal semantics | Still present | `_NO_REPORT_STATES` line 66; `_notify()` line 798; `DONE_STATES` in messages line 64 |
| P3-5 | Actual `_run()` timing and live integration unverified | Still present / unverified | `_run()` lines 181-190; `_wait_for_initial_check()` lines 192-197; no live timing test was run |

No P3 fix was implemented, as required.

## 10. Live-integration limitations

- No real OpenHands API, Telegram API, production database, deployment, or live task was
  used.
- All external boundaries were local test doubles; all SQLite files were temporary and
  outside the repository.
- Actual `_run()` scheduling/backoff timing, Telegram network behavior, and live Mini App
  rendering remain unverified.
- The full local test suite is evidence of local regression safety, not live integration.

## 11. Findings

| ID | Severity | File / line | Reproduction | Actual vs expected | Impact | Blocks acceptance? |
|---|---|---|---|---|---|---|
| R-P2-01 | Medium | `bot/messages.py:93-111`; `bot/watcher.py:593-600`; `bot/web/services.py:267` | `task_state("running", "timed_out")`; or run timeout path with a running provider and failed Telegram delivery, then build `_conversation_dto(..., "timed_out")` | Actual: `running` / `شغال`. Expected: an explicit local timeout (`timed_out`) for the nonterminal-timeout case. | If the timeout notice cannot be delivered and the watch remains, Mini App shows a running task after the local deadline. It does not claim completion. | No for the false-completion criterion; owner should decide whether explicit nonterminal timeout semantics are required. |
| R-P2-02 | Low-Medium | `bot/watcher.py:524-551` and `567`; `bot/db.py:4169-4180` | `finished` without report, then `error` with fake `TelegramError`; inspect `watched.last_state` | Actual: `last_state=finished`, `report_state=pending`, while `notification_state.status=error`. Expected: latest provider state persisted in the watched row, or explicitly documented as living only in `notification_state`. | A local status consumer using `watched.last_state` can show stale `finished`; no false completion and retry still works. | No for core P2-1 deduplication; follow-up recommended. |
| R-P2-03 | Low | `bot/handlers.py:1883`; `bot/messages.py:189-200`; `bot/web/services.py:267-275`; `app.js:868-872` | Compare `/status` for `finished` with pending report against Mini App DTO | Actual: Telegram `/status` shows provider `منتهي`; Mini App shows `report_pending` / `التقرير قيد الانتظار`. Expected by strict reading: consistent workflow labels. | User sees different labels on two surfaces; neither claims completion. | No. |
| R-P2-04 | Info / Low | `tests/frontend/*`; `tests/test_openhands_wait_until_terminal.py:542-577` | Inspect frontend tests | Actual: backend DTO task state is tested; no direct frontend test asserts `task_state_label`/`statusPill` behavior. Expected: direct regression coverage for the UI consumer. | Future UI regressions may be missed; no current functional defect found. | No. |
| R-P2-05 | Info | `bot/watcher.py:466-500`; target report uncertainty section | Restart/pending/missing event probes | The design intentionally treats an unproven send as `uncertain` and never auto-resends; exact-once is not claimed. | This is a documented conservative trade-off, not a defect. | No. |

No critical or high-severity regression was found.

## 12. Final verdict

**PASS_WITH_NOTES**

The core P2-1/P2-2/P2-3 safety properties are independently reproduced:

- terminal transitions and deduplication survive retries/restarts;
- uncertain Telegram delivery is not blindly resent and durable delivered events reconcile;
- provider `finished` is not presented as workflow completion while the report is pending
  or uncertain.

The two medium/low gaps above are follow-up items, not false-completion regressions.

## 13. Parent-task recommendation

**ACCEPTABLE FOR OWNER ACCEPTANCE**, with R-P2-01 and R-P2-02 recorded as follow-ups.
The parent task is **not closed**; owner acceptance remains a separate decision.

## 14. Read-only and Git safety confirmation

- No application source, existing test, configuration, migration, schema, or existing
  report was modified.
- No file was staged; no commit, amend, push, fetch, branch switch, PR, merge, deploy,
  release, Autopush, `git reset`, `git clean`, force operation, or broad deletion was
  performed.
- Existing modified/untracked/ignored content and `.openhands/` were preserved.
- The only new repository artifact is this review report.
