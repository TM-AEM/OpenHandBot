# OHB2-WP07-F1 — Option C Implementation & Independent Review (Report)

**Task ID:** `OHB2-WP07-F1-OPTION-C-IMPLEMENTATION-AND-INDEPENDENT-REVIEW`
**Repository:** `/workspace/project/OpenHandBot` (real Git-backed working tree)
**Branch:** `openhands-workspace-40xxn2SbOi0tRICb3y8TE`
**HEAD at start / end:** `52e7789cc8cc97a7f7c09c9592226ab117db99a2` (unchanged; no commit)
**Mode:** implementation-decision + discriminating regression tests + real-execution verification + isolated re-verification.

> This report was produced by an AI agent (OpenHands) on behalf of the repository owner.

---

## 1. Executive summary — outcome and the honest headline

The owner-approved **Option C** for `WP-07` finding **F-1** is **already implemented** by the
existing code base (the `WP-07` atomic-state work from Batch-03 + the pre-existing PTB
error-handler path). The mission's two required properties were confirmed **by execution, not by
inspection**, for all six handler paths and for the **real production poller**:

1. the local SQLite state transition and its **`durable_completed`** acknowledgement are preserved
   (one atomic transaction, never rolled back because of a later Telegram failure);
2. durable, **separate** evidence of a post-commit Telegram notification failure is retained via the
   existing supported mechanism (`update_failures`, written by `handle_processing_error` ⇒
   `record_update_failure`), and the failure is logged (no silent loss).

Because the behaviour is already correct, the **smallest safe change** was to add the missing
**discriminating regression coverage** (the deliverable that locks the contract in) and to document
the finding — **not** to rewrite working code. Making a production change to "implement" behaviour
that already exists would be an unrequested refactor and is prohibited by `AGENTS.md` §§3/6/14.

| Item | Status | Evidence |
|---|---|---|
| Atomic local state + `durable_completed` ack preserved after notification failure | **VERIFIED (already implemented)** | 14 new tests, all six paths + real poller |
| Separate durable evidence of post-commit Telegram failure retained | **VERIFIED (already implemented)** | `update_failures` row + log line, survives reopen |
| No silent loss of notification | **VERIFIED** | failure logged + durable `update_failures` row |
| Discriminating regression coverage | **ADDED** | `tests/test_wp07_f1_notification_failure.py` (14 tests, mutation-proven) |
| Production code change | **NOT REQUIRED** | behaviour already matches Option C |
| Independent review | **INDEPENDENCE_NOT_ESTABLISHED** | see §6 |

---

## 2. Workspace and baseline (recorded before any change)

- **Repository root:** `/workspace/project/OpenHandBot` (`git rev-parse --show-toplevel` = root).
- **Branch:** `openhands-workspace-40xxn2SbOi0tRICb3y8TE`; **HEAD** `52e7789`; **no upstream**.
- **`git status --short` at start:** pre-existing uncommitted work only —
  `M .agent/PROGRESS.md`, `M bot/db.py`, `M bot/handlers.py`,
  `?? docs/reviews/OHB2-REAL-EXECUTION-AND-REVIEW-BATCH-03-REPORT.md`,
  `?? tests/test_wp07_atomic_state_outcome.py`. All preserved untouched (I staged nothing).
- **`.openhands/`:** present and preserved; never modified.
- **Python:** `3.13.15`; project-local `.venv` (from `requirements-dev.txt`, git-ignored) holds PTB
  `22.8`. **Node:** `v24.22.2`. **Docker daemon:** not available (prior container path unusable).

### Baseline gate (before my change)

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q` | **3294 passed, 0 failed** |
| `node --test tests/frontend/*.test.js` | **280 pass / 0 fail** |

---

## 3. The F-1 finding and Option C, precisely

**F-1 (WP-07).** The six reply/routing paths commit local state together with a
`durable_completed` outcome (atomic since Batch-03), then send/edit a Telegram message. If that
Telegram call fails *after* the commit, the committed state and the `durable_completed`
acknowledgement must **not** be rolled back or downgraded, and the failure must not be silently
lost.

**Option C (owner-approved).** Preserve the atomic local SQLite transition and its
`durable_completed` acknowledgement; separately retain durable evidence of the post-commit Telegram
failure using an **existing supported mechanism**; prevent silent loss. No new worker/queue/table,
no redelivery driven by the notification failure, no exactly-once claim.

### 3.1 The existing mechanism (no new code)

- The six handlers call `db.set_awaiting_and_record_outcome(...)` /
  `db.clear_awaiting_and_record_outcome(...)`, which write the local state **and** the
  `durable_completed` outcome in **one** `BEGIN IMMEDIATE` transaction.
- The Telegram send/edit runs **outside** the transaction. On failure the exception propagates to
  PTB's `process_error`, which invokes the registered error handler
  `handlers.handle_processing_error` (registered at `bot/app.py:98`).
- `handle_processing_error` ⇒ `record_update_failure` ⇒ `db.mark_update_outcome(update_id, …,
  outcome=FAILED_*)`. Because `failed_*` is **ineligible**, this writes a row to **`update_failures`
  only** and never touches `processed_updates`. So:
  - `processed_updates.outcome` stays **`durable_completed`** (ack-eligible, dedup source intact);
  - `update_failures` gains a **durable, separate** `failed_transient` / `failed_permanent` row;
  - the failure is logged (`log.warning("تحديث فاشل …")` + `log.error("فشل معالجة تحديث …")`).
- `update_failures` is **not** pruned by `prune_processed_updates` (which deletes only from
  `processed_updates`), so the evidence survives normal pruning and DB reopen.

---

## 4. Changes (files + reasons)

| File | Reason |
|---|---|
| `tests/test_wp07_f1_notification_failure.py` | **New.** 14 discriminating regression tests locking in Option C across all six paths plus cross-cutting and real-poller cases. |
| `docs/reviews/OHB2-WP07-F1-OPTION-C-IMPLEMENTATION-AND-INDEPENDENT-REVIEW-REPORT.md` | **New.** This report. |
| `.agent/PROGRESS.md` | Appended a session section (planning artefact). |

**Not modified:** no `bot/*.py` production file (behaviour already correct); no Mini App file; no ADR
/ owner-decision record / architecture file; no dependency; no `.openhands/`; no commit/push/PR.

### 4.1 Test inventory (`tests/test_wp07_f1_notification_failure.py`)

Driven through the **real** `Application.process_update` (full PTB path: `dedupe_update` guard →
handler → `handle_processing_error`), plus one test through the **real** `TelegramPoller`.

1. `test_cancel_route_notification_failure_preserves_commit` — `/cancel` (message).
2. `test_cancel_route_button_notification_failure_preserves_commit` — `cancelroute` (callback).
3. `test_reply_prompt_notification_failure_preserves_commit` — `reply:<id>`.
4. `test_repo_search_prompt_notification_failure_preserves_commit` — `reposearch`.
5. `test_pick_repo_notification_failure_preserves_commit` — `pickrepo:<g>:<i>`.
6. `test_new_chat_no_repo_notification_failure_preserves_commit` — `norepo`.
7. `test_notification_permanent_rejection_preserves_commit` — `BadRequest` ⇒ `failed_permanent`.
8. `test_successful_notification_no_failure_record` — success ⇒ no false failure row.
9. `test_duplicate_delivery_does_not_repeat_local_transition` — dedup guard blocks replay.
10. `test_failure_recording_error_does_not_downgrade_commit` — failure-record write error is safe.
11. `test_failure_evidence_survives_reopen` — evidence survives DB close/reopen.
12. `test_cancellation_propagates_and_commit_preserved` — `CancelledError` propagates (not swallowed).
13. `test_acknowledgment_boundary_advances_after_notification_failure` — boundary not blocked.
14. `test_production_poller_records_evidence_and_advances` — real `TelegramPoller.process_updates`.

Each path asserts: committed state is as intended; `update_outcome == durable_completed`;
`is_update_acknowledgment_eligible is True`; `update_is_processed is True`;
`update_failure == failed_transient` (or `failed_permanent`).

---

## 5. Verification (real commands, real output)

### 5.1 On the real working tree

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q` | **3308 passed, 0 failed** (baseline 3294 → **+14**) |
| `.venv/bin/python -m pytest tests/test_wp07_f1_notification_failure.py -q` | **14 passed** |
| `.venv/bin/python -m pyflakes bot/ automation/ tools/ main.py tests/` | clean (exit 0) |
| `.venv/bin/python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | **High 0**, Medium 19, Low 5 |
| `.venv/bin/python -m pip_audit -r requirements-dev.txt` | `No known vulnerabilities found` |
| `node --test tests/frontend/*.test.js` | **280 pass / 0 fail** |

### 5.2 Isolated re-verification (fresh snapshot)

A fresh copy of the working tree (excluding `.git`/`.venv`/`__pycache__`/`.pytest_cache`; 361 files)
was created in a new temp dir and re-run with the project interpreter:

| Command | Result |
|---|---|
| `python -m pytest -q` (snapshot) | **3308 passed, 0 failed** |

### 5.3 Independent mutation reproduction (isolated snapshot, two different mechanisms)

| Mutation | Effect | Result |
|---|---|---|
| **M1** — drop the durable-ack write inside `set_awaiting_and_record_outcome` | lose `durable_completed` | **7 of 14 fail** (the `set_awaiting_and_record_outcome` paths + cross-cutting) |
| **M2** — drop the `update_failures` INSERT in `mark_update_outcome` | lose failure evidence | **11 of 14 fail** |

Restoring the source returns **14/14 green**. This proves the new tests are non-vacuous and
load-bearing for both Option-C properties (the preserved ack and the separate evidence).

### 5.4 Direct empirical confirmation of the mechanism

A one-off probe (neutralising `record_update_failure`) showed `update_failure` becomes `None` while
`update_outcome` stays `durable_completed` — i.e. the evidence row is produced by the existing error
path, not by the handler itself. This is the exact mechanism Option C relies on.

---

## 6. Independent review — honesty statement

**`INDEPENDENCE_NOT_ESTABLISHED`.** This environment cannot supply a genuinely separate reviewer
session/agent (same single agent-server, same provider profiles, no separately-provisioned reviewer;
Cloud delegation needs money/credentials that were not authorised). A fresh container plus a
different prompt is explicitly **not** sufficient for "independent reviewer session" independence.

The strongest achievable review **was** performed and is reported as such — **same-agent,
isolated-environment** review, **not** third-party review:

1. a truly isolated snapshot with a fresh copy reproducing the full suite (3308/0);
2. two independent mutations (M1 drop-ack, M2 drop-evidence) with the intended failure counts;
3. adversarial edge cases inside the suite (permanent rejection, success no-pollution, duplicate
   delivery, failure-record write error, cancellation, boundary advance, reopen durability).

---

## 7. Not verified / not implemented / still broken (honest list)

- **No production-code change was made** because none is required: the code already satisfies
  Option C. If the owner intended an **additional** mechanism (for example an operator-visible list
  or retry queue of lost notifications), that is a **new mechanism** and is prohibited without
  explicit owner approval and a design step (`AGENTS.md` §§6/14). Reported here, not started.
- **Operator surface:** `update_failures` is durable and queryable via `db.update_failure(update_id)`
  and is written on every post-commit notification failure, but there is **no** operator-facing
  command that lists it. That is a pre-existing gap, out of scope for Option C, and is **not**
  fixed here.
- **`WP-07` concurrency (`DEF-006`/`OD-04`)** and the other owner-gated packages remain
  **BLOCKED/untouched**.
- **Python 3.11 CI matrix (`WP-09`):** UNVERIFIED locally (only 3.13 available; CI triggers on
  push/PR and no push was made).
- **Docker-based verification:** UNVERIFIED (daemon not available in this environment).

---

## 8. Assumptions and decisions

1. The real Git tree at `/workspace/project/OpenHandBot` is the execution workspace.
2. "Already implemented" is the honest reading: Option C's two properties hold and are now proven by
   execution. Adding the discriminating tests — not editing working code — is the smallest safe
   change (`AGENTS.md` §§3/6/14).
3. The existing mechanism for "separate durable evidence" is `update_failures` (written by
   `record_update_failure`). No new mechanism was introduced.
4. No commit / branch / PR / merge / deploy / release; Autopush untouched.

---

## 9. Branch and commits

- Branch: `openhands-workspace-40xxn2SbOi0tRICb3y8TE` (no `agent/*` branch; no push requested).
- HEAD: `52e7789` (unchanged). All changes remain in the working tree (uncommitted).

## 10. Suggested next step

If the owner wants notifications that failed after commit to be **recoverable** (not only recorded),
commission a small design (operator-visible `update_failures` listing, or a bounded retry of the
already-committed message) and approve it explicitly — it is a new mechanism and currently out of
scope.
