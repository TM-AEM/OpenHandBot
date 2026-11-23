# OHB2-NEW03 — Independent Review Report

**Task ID:** `OHB2-NEW03-UNAVAILABLE-SELECTION-ATOMICITY`
**Verdict:** `INDEPENDENT REVIEW NOT PERFORMED — INDEPENDENT SESSION NOT ESTABLISHED`
**Review target:** `main` at `7d91f683047ae8bac8bb2000e90dab38532ef1ba`
**Date:** 2026-11-23

---

## 1. Independence evidence and reviewer identity

This review was executed in the **same OpenHands agent conversation** in which
NEW-03 was implemented. The implementation commit is
`7d91f683047ae8bac8bb2000e90dab38532ef1ba` (`openhands <openhands@all-hands.dev>`).
The reviewer has no separate conversation/session identity, no independently
provisioned reviewer checkout, and no separate reviewer account or agent-server
connection.

The only available checkout is the implementation checkout at the target commit.
A different container, a different shell, or a fresh virtual environment does not
constitute a genuinely independent reviewer session.

**Blocker:** `INDEPENDENT REVIEW NOT PERFORMED — INDEPENDENT SESSION NOT ESTABLISHED`.

The analysis and test execution below are therefore a **self-review**, not an
independent review. They must not be used to award a `PASS` or
`PASS_WITH_NOTES` verdict. No independent-review status is claimed for NEW-03 or
NEW-04.

## 2. Repository identity and remote

- Repository: `TM-AEM/OpenHandBot`
- Remote: `https://github.com/TM-AEM/OpenHandBot.git`
- Local branch: `main`
- Remote branch: `origin/main` → GitHub `main`
- GitHub `main` at review start: `7d91f683047ae8bac8bb2000e90dab38532ef1ba`

## 3. Exact target and baseline

- **Commit:** `7d91f683047ae8bac8bb2000e90dab38532ef1ba`
- **Parent:** `de17463dd9c31a070f0e8a0f08a8da9c1ad42a5f`
- **Tree:** `fe8945e31d5c8714db8215d320a489d23a2980c7`
- **Working tree at review start:** clean (`git status --short --branch` produced
  no modified, staged, or untracked paths).
- The review ran against this exact checkout. No implementation or test file was
  changed by the review.

## 4. Files and diff inspected

Commit diff `de17463..7d91f68`:

- `bot/db.py` — new `Database.clear_unavailable_selection()`.
- `bot/outbox.py` — atomic wrapper and two 404/410 call sites.
- `bot/handlers.py` — confirmed-deletion path in `_send_prompt()`.
- `tests/test_new03_unavailable_selection_atomicity.py` — 15 tests.
- `docs/reviews/OHB2-NEW03-UNAVAILABLE-SELECTION-ATOMICITY-IMPLEMENTATION-REPORT.md`
  — implementation report, read for comparison only.
- `.agent/PROGRESS.md` — implementation status notes, not changed by this review.

Additional code inspected for call-path and regression analysis:

- `bot/db.py`: `clear_awaiting_and_record_outcome`, `_clear_awaiting_nocommit`,
  `add_or_group_outbox`, routing/outcome helpers.
- `bot/outbox.py`: `_post_claimed`, `_clear_unavailable_selection`,
  `_is_selected_target`, `_tombstoned`, `_TARGET_UNAVAILABLE_NOTICE`.
- `bot/handlers.py`: `_send_prompt`, `handle_text`, cancellation paths.
- Tests: `test_persistent_ready_sticky_routing.py`,
  `test_new01_cancel_prompt_atomicity.py`,
  `test_new02_prompt_grouping_identity.py`,
  `test_new04_prompt_grouping_debounce.py`, `test_grouping.py`,
  `test_outbox.py`, `test_handlers.py`, `test_f1_tombstone_enforcement.py`,
  `test_conversation_deletion.py`, `test_remote_deletion.py`.

## 5. Transaction-boundary analysis

`Database.clear_unavailable_selection()` at `bot/db.py:3413-3437`:

1. `BEGIN IMMEDIATE` at line 3422.
2. Read `last_accessed` for the owner at lines 3424-3425.
3. Delete it only when it still equals `conversation_id` at lines 3426-3427.
4. Read `awaiting_conversation_id` at lines 3428-3431.
5. Clear the awaiting row only when it still equals `conversation_id` at
   lines 3432-3433.
6. `COMMIT` at line 3434.
7. `ROLLBACK` and re-raise on any exception at lines 3435-3437.

The transaction boundary is the intended `BEGIN IMMEDIATE`. Both conditional
reads and both cleanup mutations are inside that one transaction. Commit occurs
only after both conditional mutations succeed. There is no post-commit routing
cleanup, and no caller performs a separate routing-state clear before or after
this method.

Callers:

- `bot/outbox.py:567-582` wraps the DB method and returns `True` only after the
  method returns normally (successful commit), and `False` on any exception.
- `bot/outbox.py:719-722` and `810-813` gate the unavailable notice on that
  boolean.
- `bot/handlers.py:3358-3364` calls the same DB method for the confirmed-deletion
  path.

No direct `clear_last_accessed_conversation()` / `clear_awaiting()` pair remains
in production code; those methods are now unused except as database primitives.

## 6. Rollback and commit-failure analysis

The tests inject failures through the real SQLite connection:

- Before `DELETE FROM settings` (`tests/test_new03_unavailable_selection_atomicity.py:144-157`).
- Before `UPDATE user_state`, after the first mutation executed
  (`:160-173`).
- On `COMMIT` (`:176-200`).

In each case the test asserts the complete original state is restored:
`last_accessed = A` and `awaiting = (A, "route")`. This demonstrates that a
failure before commit cannot leave a half-cleared state, and a commit failure is
re-raised rather than converted to success.

`bot/outbox.py:575-582` catches the exception, logs it, and returns `False`.
`bot/outbox.py:719-722` and `810-813` then suppress
`_TARGET_UNAVAILABLE_NOTICE`. `tests/test_new03_unavailable_selection_atomicity.py:203-221`
asserts both `OUTBOX_FAILED` and absence of the notice for the first and second
mutation failures.

## 7. Conditional cleanup and stale-state analysis

The conditional checks are inside the transaction. Comparison is exact string
equality on:

- the owner's `last_accessed` setting value;
- the owner's `awaiting_conversation_id`.

Tests cover:

- newer selection in both `last_accessed` and `awaiting` is preserved
  (`:99-111`);
- newer `last_accessed` B with old `awaiting` A clears only A and preserves B
  (`:114-127`);
- old `last_accessed` A with newer `awaiting` B clears only A and preserves B
  (`:130-142`);
- `routing_paused` is preserved in the mixed-state case.

No code path clears repository selection, pending outbox rows, the pause flag, or
unrelated settings. The conditional checks do not use substring or loose
matching; they compare the exact conversation identifier.

## 8. Error propagation and acknowledgment analysis

- `_clear_unavailable_selection()` returns `True` only when
  `db.clear_unavailable_selection()` returned normally; SQLite exceptions return
  `False` and are logged with `log.exception`, retaining the original traceback.
- `_TARGET_UNAVAILABLE_NOTICE` is sent only when `cleared` is true and the target
  is not tombstoned.
- A failed cleanup leaves the outbox row `OUTBOX_FAILED`, preserves routing state,
  and emits no unavailable-success notice. This is fail-closed.
- The handler's confirmed-deletion path logs a cleanup failure and still sends
  the factual message "الشات ده اتحذف — مش ممكن نبعت له رسايل. افتح شات تاني."
  It does **not** claim that the local selection was cleared. The stale routing
  state is left intact, so the next attempt may encounter the same deletion
  condition; that is a retry/UX cost, not a false success claim.
- Logs contain the conversation identifier and traceback, not credentials or
  message text.

An ad-hoc lock probe held a second SQLite `BEGIN IMMEDIATE` write lock, set a
short busy timeout, and called `_clear_unavailable_selection()`. Result:
`cleanup_result=False`, `last_accessed=A`, `awaiting=('A','route')`. This
confirms fail-closed behavior under `database is locked`; it is not a substitute
for a dedicated suite test.

## 9. Concurrency analysis

The transaction uses `BEGIN IMMEDIATE`, so cleanup serializes with:

- `/cancel` (`clear_awaiting_and_record_outcome(..., pause_routing=True)`);
- new conversation selection (`set_awaiting_and_record_outcome`);
- prompt acceptance (`add_or_group_outbox` with `expected_routing`);
- outbox claim/finalization (`claim_outbox`);
- another unavailable-selection cleanup.

Because the conditional reads happen after the write lock is acquired, a newer
selection committed before cleanup is observed and preserved. If cleanup commits
first, the later selection overwrites the old target normally. Pending outbox
rows are never rewritten or redirected by cleanup.

Barrier-based tests cover cancel-vs-cleanup, acceptance-vs-cleanup, and
finalization-vs-cleanup (`tests/test_new03_unavailable_selection_atomicity.py:241-370`).
The tests assert final invariants rather than a forced scheduling order; this is
appropriate for race safety, but it is not an exhaustive proof of every possible
interleaving.

## 10. NEW-01 regression analysis

NEW-01's `/cancel` transaction and `routing_paused:<telegram_id>` behavior were
not modified. `clear_awaiting_and_record_outcome` remains unchanged and uses the
same `BEGIN IMMEDIATE` pattern. The cancellation-vs-cleanup barrier test passed.
`tests/test_new01_cancel_prompt_atomicity.py` passed independently in the focused
run.

## 11. NEW-02 regression analysis

NEW-02's identity-based grouping in `add_or_group_outbox` was not modified.
Explicit `reply_to_message_id` matching, duplicate message-identity protection,
and per-batch cleanup remain intact. `tests/test_new02_prompt_grouping_identity.py`
passed independently in the focused run.

## 12. NEW-04 regression analysis

NEW-04's 3-second inactivity window, durable pending batch, message ordering,
duplicate protection, recovery, and routing isolation were not modified.
`grouping_mature_before()` and the worker's `claim_outbox(..., mature_before=...)`
path remain unchanged. `tests/test_new04_prompt_grouping_debounce.py`,
`tests/test_grouping.py`, and outbox/routing tests passed independently.

**NEW-04 independent-review status remains DEFERRED. This review does not
reopen, complete, waive, or change that status, and does not mark NEW-04 as
independently reviewed.**

## 13. Mini App and architecture scope

`git diff --name-only de17463..7d91f68` contains only:

- `.agent/PROGRESS.md`
- `bot/db.py`
- `bot/handlers.py`
- `bot/outbox.py`
- `docs/reviews/OHB2-NEW03-UNAVAILABLE-SELECTION-ATOMICITY-IMPLEMENTATION-REPORT.md`
- `tests/test_new03_unavailable_selection_atomicity.py`

No Mini App file, worker, scheduler, process, queue, or database owner was added
or changed. The existing outbox/worker architecture remains intact. No
exactly-once Telegram delivery guarantee was introduced or claimed. No unrelated
DEF-011 scope was closed.

## 14. Independent test commands and results

Environment: Python 3.13.15. A fresh review virtual environment was created at
`/tmp/ohb2-review-venv` from the repository's pinned `requirements-dev.txt`
(the previously available environment was absent). No dependency file was
modified.

| Command | Result |
|---|---|
| `pytest -q tests/test_new03_unavailable_selection_atomicity.py` | **15 passed**, exit 0, 1.09s |
| Focused: NEW-03 + persistent-routing + NEW-01 + NEW-02 + NEW-04 + grouping + outbox + handlers + F-1 tombstone + conversation/remote deletion | **448 passed**, exit 0, 2 warnings, 25.37s |
| Full: `pytest -q` | **3769 passed**, 0 failed, 74 warnings, 188.56s, exit 0 |
| NEW-03 repeated 5 times | **15 passed** on every run (0.94–0.99s) |
| `node --test tests/frontend/*.test.js` | **280 pass / 0 fail**, exit 0 |
| `pyflakes bot automation tools main.py tests/` | exit 0 |
| `bandit -r bot/ automation/ tools/ main.py -lll -s B613` | High **0**, exit 0 |
| `pip_audit -r requirements-dev.txt` | No known vulnerabilities, exit 0 |
| `compileall -q bot automation tools main.py tests` | exit 0 |
| `git diff --check` | exit 0 |

No skipped tests were reported by the full run. Warnings are pre-existing
third-party deprecation warnings from `python-telegram-bot`,
Starlette/httpx/anyio. The ad-hoc BUSY/LOCKED probe is described in section 8.

## 15. Findings

### REV-NEW03-F01 — INFO — Handler cleanup failure leaves stale state but does not claim success
- **Files/lines:** `bot/handlers.py:3358-3368`.
- **Path:** confirmed remote deletion → `db.clear_unavailable_selection()` raises →
  exception logged → deletion message sent → `mark_explicitly_ignored()`.
- **Actual:** the local routing state remains at the deleted conversation; the
  user receives the factual deletion message.
- **Expected:** no claim that local selection was cleared; the message is a
  deletion notice, not a cleanup-success notice.
- **Impact:** the next prompt may hit the same deleted target and repeat the
  condition. This is a retry/UX cost, not a false-success or data-corruption
  defect.
- **Origin:** pre-existing failure-path behavior; NEW-03 makes the successful
  path atomic.
- **Remediation (narrow):** if desired, add a separate user-facing retry/error
  message for cleanup failure; do not change the deletion semantics without owner
  approval.

### REV-NEW03-F02 — INFO — BUSY/LOCKED has no explicit retry beyond busy_timeout
- **Files/lines:** `bot/db.py:3422`; `bot/outbox.py:574-582`.
- **Path:** another writer holds `BEGIN IMMEDIATE`; SQLite waits per connection
  busy timeout, then raises; wrapper logs and returns `False`.
- **Actual:** ad-hoc probe produced `cleanup_result=False` and preserved
  `last_accessed=A`, `awaiting=('A','route')`.
- **Expected:** fail-closed; no false success.
- **Impact:** a transient lock can suppress the unavailable notice and leave the
  outbox failed. This matches the existing optional-cleanup convention but is a
  reliability trade-off.
- **Origin:** design trade-off; not a NEW-03 regression.
- **Remediation (narrow):** only if owner wants retry semantics, add bounded
  retry around this optional cleanup; do not broaden without approval.

### REV-NEW03-F03 — LOW — Handler test uses a fake DB, not the production transaction
- **Files/lines:** `tests/test_new03_unavailable_selection_atomicity.py:383-425`.
- **Path:** `_HandlerDB` records `clear_unavailable_selection` calls.
- **Actual:** verifies handler wiring, but not the real SQLite transaction in the
  handler path.
- **Expected:** core transaction is covered by direct real-DB tests; handler
  integration is covered at the call boundary.
- **Impact:** a future handler-specific DB failure could regress without this test
  catching it.
- **Origin:** test-coverage gap, not a production defect.
- **Remediation (narrow):** add a real-DB handler test with a failure-injected
  connection if handler-path atomicity needs explicit regression coverage.

### REV-NEW03-F04 — INFO — Concurrency tests assert final invariants, not every interleaving
- **Files/lines:** `tests/test_new03_unavailable_selection_atomicity.py:241-370`.
- **Path:** two threads, `threading.Barrier`, two SQLite connections.
- **Actual:** tests pass and assert no newer state is erased / no pending row is
  redirected; they do not enumerate all possible commit orders.
- **Expected:** barrier coverage plus `BEGIN IMMEDIATE` reasoning is appropriate
  for the stated race surfaces.
- **Impact:** residual untested interleavings are possible; no defect observed.
- **Origin:** test-design limitation.
- **Remediation (narrow):** no change required for this task; add deterministic
  scheduling hooks only if a specific race is suspected.

### REV-NEW03-F05 — INFO — Dedicated helper duplicates conditional-clear logic
- **Files/lines:** `bot/db.py:3413-3437` versus `bot/db.py:3363-3411`.
- **Path:** `clear_unavailable_selection` repeats the conditional
  `last_accessed`/`awaiting` reads and clears already present in
  `clear_awaiting_and_record_outcome`.
- **Actual:** behavior is correct and narrowly scoped.
- **Expected:** no behavior change required; maintainability could improve by
  reusing a shared private transaction helper.
- **Impact:** future drift risk between two similar transaction implementations.
- **Origin:** design/maintainability trade-off; not a defect.
- **Remediation (narrow):** only in a separate refactor task, not in this review.

**No CRITICAL, HIGH, or MEDIUM findings were confirmed.** No material atomicity,
rollback, stale-state, acknowledgment, or concurrency defect was reproduced.

## 16. Remaining limitations and unverified behavior

- **Independence is not established**; this is the controlling limitation.
- No live Telegram/OpenHands production call was made.
- The ad-hoc BUSY/LOCKED probe is a manual check, not a committed regression test.
- The handler-path test uses a fake DB; the core transaction is covered by real
  SQLite tests.
- Concurrency tests are barrier-based and do not exhaust all interleavings.
- No exactly-once delivery guarantee is claimed or tested.

## 17. Final verdict and justification

**`INDEPENDENT REVIEW NOT PERFORMED — INDEPENDENT SESSION NOT ESTABLISHED`.**

The core atomicity design and the reproduced tests show no material defect in
this self-review: one `BEGIN IMMEDIATE` transaction, conditional clears, complete
rollback on first/second/commit failure, no notice on cleanup failure, and
preserved NEW-01/NEW-02/NEW-04 behavior. However, the review was performed in the
same session that implemented NEW-03. Under the task's independence requirement,
that is not an independent review and cannot support a `PASS` or
`PASS_WITH_NOTES` verdict.

## 18. Confirmation of no implementation/test modification

No implementation file, test file, implementation report, or `.agent/PROGRESS.md`
was modified by this review. This review report is the only new artifact.

## 19. Confirmation of no publication or deployment

No commit, push, PR, merge request, merge, deployment, release, production
restart, or Autopush activation occurred during this review.
