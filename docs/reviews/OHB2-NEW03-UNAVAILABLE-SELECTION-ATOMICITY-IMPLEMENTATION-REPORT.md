# OHB2-NEW03 — Unavailable-Selection Atomicity

**Task:** `OHB2-NEW03-UNAVAILABLE-SELECTION-ATOMICITY`
**Status:** `IMPLEMENTED — SELF-VERIFIED`; **independent review NOT PERFORMED**; not release-ready.
**Date:** 2026-11-22
**Branch:** `agent/ohb2-new03-unavailable-selection-atomicity`
**Base:** `de17463dd9c31a070f0e8a0f08a8da9c1ad42a5f` (`main`, clean at start).

---

## 1. Status and scope

The unavailable-selection cleanup now performs one conditional SQLite transaction:

- clear `last_accessed` only when it still points at the confirmed-unavailable conversation;
- clear `awaiting` only when it still points at that same conversation;
- commit both changes together, or roll back both.

No new database owner, worker, scheduler, process, queue, or Mini App change was introduced.
NEW-01, NEW-02, and NEW-04 behavior was preserved. NEW-04's deferred independent review was
not started, resumed, or marked complete. DEF-011 was not changed or closed.

## 2. Baseline audit

- Repository: `/workspace/project/OpenHandBot`, remote `TM-AEM/OpenHandBot`.
- Baseline branch: `main`.
- Baseline HEAD: `de17463dd9c31a070f0e8a0f08a8da9c1ad42a5f`.
- Baseline working tree: clean; no staged changes.
- Important state difference from the task text: NEW-04 is **already committed and pushed**
  in this checkout (`0769234...` feature commit and `de17463...` sync-state commit). There was
  no uncommitted NEW-04 work to preserve at the start of this task. No existing work was
  overwritten or discarded.
- Inspected: `AGENTS.md`, `bot/outbox.py`, `bot/db.py`, `bot/handlers.py`,
  `bot/web/services.py`, routing/cancellation call sites, and the relevant tests
  (`test_persistent_ready_sticky_routing.py`, `test_new01_cancel_prompt_atomicity.py`,
  `test_new02_prompt_grouping_identity.py`, `test_new04_prompt_grouping_debounce.py`,
  `test_grouping.py`, `test_outbox.py`, `test_handlers.py`,
  `test_f1_tombstone_enforcement.py`).
- Baseline focused run before edits:
  `pytest -q` on the routing/cancellation/grouping/outbox/handlers suites ⇒ **213 passed**.
- The prior full-suite result (`3754 passed`) was from the previous synchronization run, not
  from a fresh NEW-03 baseline. It is not used as evidence for the implementation.

## 3. Files inspected and modified

Modified:

- `bot/db.py` — added `Database.clear_unavailable_selection()`.
- `bot/outbox.py` — `_clear_unavailable_selection()` now calls the atomic DB operation,
  returns a commit-success boolean, and the unavailable notice is emitted only after a
  successful commit.
- `bot/handlers.py` — the confirmed-deletion path in `_send_prompt()` now uses the same
  atomic operation instead of separate `clear_last_accessed_conversation()` and
  `clear_awaiting()` calls.
- `.agent/PROGRESS.md` — NEW-03 status, baseline, evidence, and limitations.

Added:

- `tests/test_new03_unavailable_selection_atomicity.py` — 15 deterministic tests.
- This report.

Not modified:

- Mini App files.
- NEW-01 cancellation transaction boundary.
- NEW-02 grouping/identity code.
- NEW-04 batching/outbox code.
- Approved architecture.

## 4. Root cause and atomicity gap

The old `_clear_unavailable_selection()` did this as separate operations:

1. read `last_accessed`, then `clear_last_accessed_conversation()` (independent commit);
2. read `awaiting`, then `clear_awaiting()` (another independent commit).

If operation 1 committed and operation 2 failed, the user was left with one half of the
routing state cleared. The confirmed-deletion path in `handlers._send_prompt()` had the same
two independent commits. A database failure could therefore leave stale or inconsistent
routing state while the user received a deletion/unavailable response.

## 5. Chosen transaction boundary and state transition

`Database.clear_unavailable_selection(telegram_id, conversation_id)`:

1. `BEGIN IMMEDIATE` — acquires the write lock before reading.
2. Read the `last_accessed` setting for the owner; delete it only if its value equals
   `conversation_id`.
3. Read the owner's `awaiting_conversation_id`; clear the awaiting row only if it equals
   `conversation_id`.
4. `COMMIT` both changes together; any exception executes `ROLLBACK` and re-raises.

The operation preserves:

- a newer `last_accessed` pointing at another conversation;
- a newer `awaiting` pointing at another conversation;
- repository selection and other `settings` rows;
- `routing_paused:<telegram_id>`;
- pending outbox rows and their routing identity.

`_clear_unavailable_selection()` catches a database failure, logs the original exception
with traceback, and returns `False`. Both outbox call sites now send
`_TARGET_UNAVAILABLE_NOTICE` only when that result is `True`.

## 6. Failure-injection and rollback evidence

Tests use real SQLite databases and a connection wrapper that raises before a selected
statement executes:

- first mutation (`DELETE FROM settings`) fails;
- second mutation (`UPDATE user_state`) fails after the first mutation has executed;
- final `COMMIT` fails.

In every case the test asserts that both `last_accessed` and `awaiting` remain at the
unavailable conversation, proving full rollback. The outbox failure test also asserts that
the outbox record becomes `failed` but `_TARGET_UNAVAILABLE_NOTICE` is not sent.

## 7. Concurrency and stale-selection protections

`BEGIN IMMEDIATE` serializes the cleanup with existing writers:

- `/cancel` (`clear_awaiting_and_record_outcome(..., pause_routing=True)`) and cleanup;
- new conversation selection (`set_awaiting_and_record_outcome`);
- prompt acceptance (`add_or_group_outbox` with `expected_routing`);
- outbox claim/finalization (`claim_outbox`).

The conditional reads happen inside the same write transaction, so cleanup cannot erase a
newer valid selection that committed before it. If cleanup commits first, a later selection
wins normally. Tests use `threading.Barrier` rather than sleeps for the concurrency cases.

## 8. User acknowledgment behavior

- Successful cleanup: the existing `_TARGET_UNAVAILABLE_NOTICE` wording and send path are
  unchanged.
- Failed outbox cleanup: no unavailable-selection notice is sent; the outbox record remains
  `failed`, the routing state remains unchanged, and the original error is logged.
- Confirmed deletion in `handlers._send_prompt()`: the factual deletion message is still sent
  because remote deletion was already confirmed; a cleanup failure is logged and is not
  reported as a successful selection clear. The stale routing state is left intact rather
  than falsely cleared.

## 9. NEW-01 regression evidence

The NEW-01 cancellation transaction boundary and `routing_paused` checks are unchanged.
`tests/test_new01_cancel_prompt_atomicity.py` passed in the focused run and in the full suite.
The new cancel-vs-cleanup barrier test also passed.

## 10. NEW-02 regression evidence

NEW-02 grouping identity, cleanup identity, and duplicate protections were not modified.
`tests/test_new02_prompt_grouping_identity.py` passed in the focused run and full suite.

## 11. NEW-04 regression evidence

NEW-04 3-second debounce, durable batching, recovery, expected-routing checks, and outbox
behavior were not modified. `tests/test_new04_prompt_grouping_debounce.py`,
`tests/test_grouping.py`, and the outbox/routing tests passed. The new finalization race test
confirms that cleanup does not redirect or delete a pending/claimed outbox row.

## 12. Exact commands and results

All Python commands used the repository virtual environment:
`/tmp/ohb2-chat-venv/bin/python`.

| Command | Result |
|---|---|
| Baseline focused: `pytest -q tests/test_persistent_ready_sticky_routing.py tests/test_new01_cancel_prompt_atomicity.py tests/test_new02_prompt_grouping_identity.py tests/test_new04_prompt_grouping_debounce.py tests/test_grouping.py tests/test_outbox.py tests/test_handlers.py` | **213 passed** |
| NEW-03 file: `pytest -q tests/test_new03_unavailable_selection_atomicity.py` | **15 passed** |
| Focused final: NEW-03 + routing + NEW-01 + NEW-02 + NEW-04 + grouping + outbox + handlers + F-1 tombstone suites | **334 passed**, 2 warnings |
| Full Python suite: `pytest -q` | **3769 passed**, 0 failed, 74 warnings, 191.64s |
| Frontend: `node --test tests/frontend/*.test.js` | **280 pass / 0 fail** |
| `pyflakes bot automation tools main.py tests/` | exit **0** |
| `bandit -r bot/ automation/ tools/ main.py -lll -s B613` | High **0**, exit 0 |
| `pip_audit -r requirements-dev.txt` | No known vulnerabilities, exit 0 |
| `compileall -q bot automation tools main.py tests` | exit **0** |
| `git diff --check` | exit **0** |

No tests were skipped in the final full run. The 74 warnings are pre-existing third-party
deprecation warnings (`python-telegram-bot`, Starlette/httpx/anyio), not NEW-03 failures.

## 13. Independent review

**INDEPENDENT REVIEW NOT PERFORMED.**

A genuinely separate reviewer session with a separate checkout was not available in this
environment. This report is implementation plus self-review only; it is not an independent
review. NEW-04's deferred review status is unchanged.

## 14. Remaining findings and limitations

- A failed cleanup leaves the unavailable target in place and the outbox record `failed`;
  a later prompt may encounter the same missing target again. This is fail-closed, not a
  false success.
- `_clear_unavailable_selection()` relies on the repository's existing `busy_timeout=5000`
  and fail-closed caller behavior; no new retry loop was added.
- The handler deletion message is still sent when remote deletion is confirmed even if the
  local atomic cleanup fails; it reports deletion, not a successful selection clear.
- No live Telegram/OpenHands production calls were made.
- No exactly-once delivery claim is made.

## 15. Final Git state

- Branch: `agent/ohb2-new03-unavailable-selection-atomicity`.
- Base: `de17463dd9c31a070f0e8a0f08a8da9c1ad42a5f`.
- Intended changes are committed on `main` as part of the authorized exact
  synchronization: `.agent/PROGRESS.md`, `bot/db.py`, `bot/outbox.py`,
  `bot/handlers.py`, `tests/test_new03_unavailable_selection_atomicity.py`, and this report.
- No PR, merge request, deployment, or Autopush activation was performed.
- The final local/GitHub commit and tree hashes are recorded in the synchronization
  verification response.

## 16. Safety confirmation

No `git reset`, `git clean`, force operation, broad deletion, `git add .`, PR, merge,
deployment, release, production Telegram/OpenHands call, or Autopush activation was
performed. The user-authorized synchronization commit and push to `main` were performed.
Mini App files were not modified.
