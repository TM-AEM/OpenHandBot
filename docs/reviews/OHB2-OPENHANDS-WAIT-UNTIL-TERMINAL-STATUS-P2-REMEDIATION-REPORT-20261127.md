# OHB2-OPENHANDS-WAIT-UNTIL-TERMINAL-STATUS-P2-REMEDIATION — Report

**Task ID:** `OHB2-OPENHANDS-WAIT-UNTIL-TERMINAL-STATUS-P2-REMEDIATION`
**Date:** 2026-11-27
**Verdict:** `PASS_WITH_NOTES`
**Mode:** baseline audit + targeted implementation + regression testing
**Parent task:** not closed; this remediation needs a new independent review and owner acceptance.

## 1. Baseline

Recorded before edits:

| Item | Value |
|---|---|
| Branch | `agent/r6-review-delivery` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` |
| HEAD tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| Staged | 0 files |
| Modified tracked | 15 files |
| Untracked, status entries | 95 |
| Untracked, file-level | 111 |
| Relevant ignored | `.venv/`, `node_modules/`, `__pycache__/`, `.pytest_cache/` |

After the remediation and this report, the working tree has `18` modified tracked files,
`0` staged files, `96` untracked status entries, and `112` untracked files. The increase
is the three intentional Mini App/status files plus this report; existing user changes
were preserved.

The three P2 findings were reproduced on the unmodified implementation before
editing:

- **P2-1:** `finished` without a report followed by `error` without a report produced
  no notification; state became `last_state=error`, `report_state=pending`.
- **P2-2:** first successful report send count `1`; after `set_report_state` failed,
  the next tick produced send count `2`.
- **P2-3:** `task_state("finished")` returned `completed`, and `TASK_TIMED_OUT` had no
  runtime consumer.

## 2. Root cause and fix

### P2-1 — terminal transition while report pending

**Root cause:** `transition` was computed only as
`is_terminal(state) and not is_terminal(w.last_state)`. After a no-report `finished`
was persisted in `last_state`, a later `error`/`cancelled` was terminal-to-terminal and
therefore never entered the notification branch.

**Fix:** `bot/watcher.py` now has `_terminal_transition()`:

```python
is_terminal(state) and (not is_terminal(w.last_state) or w.last_state != state)
```

This treats a different terminal state as a new transition, while repeated polling of
the same terminal state remains idempotent. The existing transition identity
(`transition_seq`) and inbox event key prevent duplicate notifications across retries and
restarts.

### P2-2 — delivery marker failure after Telegram acceptance

**Root cause:** the delivered marker was written only after `_notify()` returned. If
`set_report_state(delivered)` failed, the watch remained with no delivered marker and
`_notify()` sent the same report again on the next tick.

**Fix:**

1. `REPORT_STATE_SENDING` is persisted **before** `_notify()`.
2. A definite Telegram rejection (`TelegramError`) resets to
   `REPORT_STATE_PENDING`, preserving safe retry.
3. After successful delivery, `REPORT_STATE_DELIVERED` is persisted and the watch is
   removed.
4. If the delivered marker write fails, the row stays `sending`.
5. `_reconcile_report_delivery()` uses the existing durable inbox event identity
   (`conversation_id|terminal|watch_seq|transition_seq`):
   - event `delivered` ⇒ persist delivered and remove the watch;
   - event `pending`/`failed` or absent ⇒ persist `REPORT_STATE_UNCERTAIN` and **do not
     resend automatically**.
6. Repeated uncertain polling and restarts do not blind-resend.

No new database owner, worker, table, or delivery subsystem was added.

### P2-3 — provider completion versus report completion

**Root cause:** `task_state()` accepted only provider status. `finished` was always
`completed`; report state was invisible. `TASK_TIMED_OUT` existed but was not used by a
runtime consumer.

**Fix:** `bot/messages.py` now provides:

```python
task_state(status, report_state=None)
task_state_label(state)
```

Semantics:

| Provider | Report state | Semantic state |
|---|---|---|
| `finished` | `None` / `not_requested` | `provider_finished` |
| `finished` | `pending` | `report_pending` |
| `finished` | `sending` | `report_available` |
| `finished` | `uncertain` | `report_uncertain` |
| `finished` | `delivered` / `not_required` | `completed` |
| `finished` | `timed_out` | `timed_out` |
| `error` / `stuck` / `sandbox_error` | any | `failed` |
| `cancelled` / `canceled` | any | `cancelled` |
| `running` / `idle` / `paused` | any | `running` |
| unknown / `waiting_for_confirmation` | any | `unknown` |

Provider facts remain available separately as `status` and `state_label`; the semantic
state is additive. `REPORT_STATE_TIMED_OUT` is produced by the existing timeout paths and
now maps to `TASK_TIMED_OUT` in runtime-facing DTOs.

## 3. Delivery uncertainty model and recovery policy

Durable report states:

- `not_requested` — no report request is active.
- `pending` — provider terminal, report not yet retrieved.
- `sending` — report is available and a send attempt is in progress. Written before
  Telegram.
- `uncertain` — Telegram may have accepted the message but local delivery is not proven.
- `delivered` — durable proof of delivery exists.
- `not_required` — terminal notification delivered without a report.
- `timed_out` — local 24-hour deadline reached.

The existing inbox event is the durable identity. A `delivered` event proves the send
already happened. A `pending`/`failed`/missing event does not prove that Telegram did
not accept the message, so the watcher does **not** automatically resend. The task remains
watched, becomes explicitly `uncertain`, and reaches the existing local timeout notice if
unresolved. This narrows but does not eliminate the uncertainty window between Telegram
acceptance and local commit.

**No exactly-once Telegram delivery claim is made.** A `TelegramError` is treated as a
definite pre-acceptance failure for retry purposes; generic exceptions and process
interruption are treated as uncertain. The trade-off is documented rather than hidden.

## 4. Status semantics and affected callers

- `bot/messages.py` — source of `task_state`, `task_state_label`, labels, and semantic
  constants.
- `bot/watcher.py` — report states and transitions; provider status remains from
  `get_status`.
- `bot/web/services.py` — `_conversation_dto` now includes `task_state` and
  `task_state_label`; list/detail/status/associate paths pass the watched row's
  `report_state`.
- `bot/web/static/app.js` — status pills and detail cards prefer `task_state_label`;
  `data-status` uses the semantic state.
- `bot/web/static/styles.css` — colors for `provider_finished`, `report_pending`,
  `report_available`, `report_uncertain`, `timed_out`, `completed`, `failed`, and
  `cancelled`.
- Telegram timeout/failure messages remain explicit; no COMPLETED notification is sent
  for a missing report.

The Mini App still exposes factual provider `status` and `state_label`; it no longer
shows `completed` solely because the provider reported `finished` while the report is
pending.

## 5. Files changed

| File | Reason |
|---|---|
| `bot/db.py` | Added `REPORT_STATE_SENDING` and `REPORT_STATE_UNCERTAIN`; no schema migration. |
| `bot/messages.py` | Added report-aware semantic states, `task_state_label`, labels, and `canceled` normalization. |
| `bot/watcher.py` | P2-1 terminal transitions; P2-2 write-ahead send state, durable reconciliation, uncertain no-resend, retry on definite Telegram rejection. |
| `bot/web/services.py` | Added `task_state`/`task_state_label` to conversation DTOs and report-state lookup for watched rows. |
| `bot/web/static/app.js` | Uses semantic task label for status pill and detail card. |
| `bot/web/static/styles.css` | Styles semantic status values. |
| `tests/test_openhands_wait_until_terminal.py` | Added P2-1/P2-2/P2-3 regression coverage; now 30 tests. |
| this report | Remediation evidence and uncertainty policy. |

No unrelated feature, R7 decision, D-05, FIND-02, dependency, schema, worker, or
outbox architecture was changed.

## 6. Regression tests

P2-1:

- `test_finished_then_error_after_pending_report_notifies_failure`
- `test_finished_then_cancelled_after_pending_report_notifies_cancellation`
- `test_finished_then_canceled_spelling_notifies_cancellation`
- `test_finished_then_error_after_restart_notifies_failure`
- `test_terminal_transition_retry_does_not_duplicate`

P2-2:

- `test_send_failure_before_acceptance_retries`
- `test_db_marker_failure_after_success_does_not_resend`
- `test_restart_during_uncertain_delivery_does_not_resend`
- `test_pending_delivery_event_is_recovered_without_resend`
- `test_delivered_event_reconciles_uncertain_delivery_without_resend`
- `test_uncertain_delivery_timeout_is_not_completed`

P2-3:

- `test_task_state_mapping_never_marks_unknown_as_completed`
- `test_mini_app_dto_separates_provider_and_task_state`

The P2-1 tests cover finished→error, finished→cancelled, finished→canceled, restart,
and retry without duplicate. The P2-2 tests cover definite send failure, successful send
followed by marker failure, restart, pending event, delivered event recovery, repeated
uncertain polling, and timeout. The P2-3 tests cover pending, available, uncertain,
delivered, timeout, failure, cancellation, unknown, running, and provider-only states.

## 7. Exact verification

Environment note: commands were run with the repository virtual environment because the
system interpreter does not have the project test dependencies.

```text
export PATH="$PWD/.venv/bin:$PATH"

python -m pytest -q tests/test_openhands_wait_until_terminal.py tests/test_u01_watcher.py tests/test_watcher.py
128 passed, 28 warnings in 11.62s
exit 0

python -m pytest -q
4413 passed, 74 warnings in 310.20s (0:05:10)
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

git diff --check
exit 0

python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613
High severity: 0
Low: 7
Medium: 22
exit 0

python -m pip_audit -r requirements-dev.txt
No known vulnerabilities found
exit 0
```

No tests were skipped. The new tests use the real SQLite database and real watcher, with
fake OpenHands/Telegram boundaries; no network or production calls.

## 8. Remaining issues and limitations

- **P2-2 uncertainty window:** a process can die after Telegram accepts a message but
  before any local marker/event commit. The code avoids blind automatic resend when the
  outcome is uncertain, but cannot prove exactly-once delivery. This is documented and
  bounded by the existing local timeout.
- **P3-1:** `is_terminal("canceled")` remains false at the helper level; runtime paths
  normalize through `get_status`/`task_state`. This was intentionally not expanded beyond
  P2 scope.
- **P3-2:** backoff at a configured `WATCHER_INTERVAL` above 900 seconds can be shorter
  than the configured interval. Not changed in this P2 remediation.
- **P3-3:** missing-conversation path still stops after `MISSING_LIMIT` cycles with an
  explicit notice; not a false-completion path, but transient absence remains a risk.
- **P3-4:** `waiting_for_confirmation` still uses existing terminal wording and removes
  the watch; unchanged.
- **P3-5:** actual `_run()` timing and live provider/Mini App integration remain
  unverified. No live integration was performed.
- **No exactly-once claim:** this remediation explicitly does not claim it.

## 9. Architecture and preservation

- One bot + ASGI process, one authoritative SQLite owner, existing watcher/outbox/inbox
  only.
- No new database owner, worker system, backup feature, or parallel delivery subsystem.
- No schema migration was needed; report states use the existing `report_state` column.
- Existing conversation/task associations and `watch_seq` identity are preserved.
- No approved R7, D-05, or FIND-02 decision was changed.
- Baseline user changes and unrelated files were preserved.
- No production API, real OpenHands task, Telegram, Mini App live check, or paid
  inference was used.

## 10. Git and safety confirmation

- Branch: `agent/r6-review-delivery`
- HEAD before and after implementation: `01079676351aac869d09d4d1747661cd6f07d82b`
- Tree before and after implementation: `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc`
- No commit, push, PR, merge, deployment, release, or Autopush activation.
- No `git reset`, `git clean`, force operation, or broad deletion.
- No `git add .` or `git add -A`; staged remains 0.
- Existing modified/untracked files were preserved.

The parent task is **not closed**; this remediation must undergo a new independent review
and owner acceptance.

## 11. Assumptions and decisions

- `TelegramError` is treated as a definite pre-acceptance failure for retry purposes;
  generic exceptions and process interruption are treated as uncertain.
- A provider `finished` without a report state is represented as `provider_finished`, not
  `completed`; `completed` requires a delivered/not-required report marker.
- `sending` is used as the durable in-flight report state; no new schema column was added.
- P3 findings were intentionally left out of scope and recorded above rather than silently
  fixed.
- No live integration was performed, so live timing/provider/UI behavior remains
  unverified.
