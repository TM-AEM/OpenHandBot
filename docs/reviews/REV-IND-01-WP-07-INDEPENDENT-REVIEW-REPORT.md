# REV-IND-01 — WP-07 Independent Review Report

**Task ID:** `REV-IND-01`
**Review target:** WP-07 — F-1 Option C, NEW-DEF-03 (non-concurrency), NAV-01..06
**Date:** 2026-11-21
**Overall verdict:** `BLOCKED`
**Mode:** read-only review; no implementation, test, configuration, staging, commit, push, PR, merge, deployment, or Autopush action.

## 1. Scope and exclusions

Reviewed only:

1. F-1 — Option C.
2. NEW-DEF-03 — non-concurrency scope only.
3. NAV-01 through NAV-06.

Explicitly excluded:

- DEF-006 and all poller-concurrency work, including the separate Option A review.
- DEF-011-A/B/C and attachment work.
- WP-05 and WP-06 findings except where a shared file is needed to understand a target.
- Mini App, BrowserCache, file-browser, outbox/worker, deployment, and release work.
- Any unrelated documentation cleanup.

## 2. Reviewer-session independence evidence

| Item | Value |
|---|---|
| Reviewer session | This OpenHands review conversation |
| Implementation session | Prior WP-07 implementation session represented by commit `30dfa0d`, branch `openhands-workspace-11yyMvqKPjTrIZt1RRpWq9` |
| Implementation reports | Dated 2026-11-19, authored before this review conversation |
| Implementation action in this review conversation | None |
| Review workspace | `/workspace/review-packages/REV-IND-01-WP-07-20261121` |
| Exact-candidate clone | `.../review-repo-wp07` at detached `30dfa0d` |
| Current-HEAD clone | `.../review-repo` at `0774c9c` |
| Shared mutable working tree with implementation? | No; separate local clones |
| Implementation workspace used for review? | No; only read-only status/doc inspection |

The WP-07 code was already committed in `30dfa0d` before this review. This review conversation
did not author, modify, stage, or commit any WP-07 implementation file. The review was performed in
a separate clone with no shared mutable working tree.

The current implementation workspace has unrelated pre-existing uncommitted concurrency changes
(`bot/app.py`, `tests/test_u04_concurrency.py`) and concurrency reports. Those were excluded and
left untouched.

## 3. Repository and candidate identity

### 3.1 Repository

| Item | Value |
|---|---|
| Repository path | `/workspace/project/OpenHandBot` |
| Remote | `https://github.com/TM-AEM/OpenHandBot.git` |
| Current branch | `main` |
| Current HEAD | `0774c9cff923a2ed02da36a1111a283a61600ea5` |
| Current tree | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| Current tracked modifications | `bot/app.py`, `tests/test_u04_concurrency.py` (pre-existing concurrency work, excluded) |
| Current untracked | three concurrency reports (pre-existing, excluded) |
| Ignored | `.openhands/`, `.pytest_cache/`, `__pycache__/` etc. (preserved) |

### 3.2 Exact WP-07 candidate

| Item | Value |
|---|---|
| Candidate commit | `30dfa0d6432cdb8f7787edde38f48fb482b6ced6` |
| Candidate tree | `ac61c5cf9080db92764273c31a7ba6bbe3669ab1` |
| Candidate parent/baseline | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| Baseline tree | `fa9f25802c8154510e86504e26dd1626075d5fdf` |
| Candidate state | committed; clean clone |
| Candidate commit date | 2026-11-21T09:40:48Z |
| Current HEAD relationship | `0774c9c` contains `30dfa0d` plus later unrelated REV-01 changes |

The WP-07 test files were unchanged between `30dfa0d` and `0774c9c`:

```sh
git diff --name-only 30dfa0d..HEAD -- tests/test_wp07_*.py
# empty
```

Focused WP-07 tests were run both on exact `30dfa0d` and on current `0774c9c`; both passed.

### 3.3 Candidate clone status

```text
## HEAD (no branch)
```

No tracked or untracked modifications in `review-repo-wp07`. The implementation workspace was not
used as the candidate review clone.

## 4. Baseline/candidate comparison by target

| Target | Baseline `52e7789` | Candidate `30dfa0d` | Primary files | Primary tests |
|---|---|---|---|---|
| F-1 Option C | Existing six handlers; no F-1 test file | Six handlers preserved; 14 F-1 tests added | `bot/handlers.py:1835,2585,2598,2738,2797,2825` | `tests/test_wp07_f1_notification_failure.py` (14) |
| NEW-DEF-03 (non-concurrency) | Atomic helpers absent; separate commits in handlers | Atomic watch/unwatch/awaiting helpers + handlers | `bot/db.py:1896-2175,2911-2973`, `bot/watcher.py:717`, `bot/handlers.py:1415-1490,2511-2610` | `tests/test_wp07_atomic_state_outcome.py` (9), `tests/test_wp07_watch_unwatch_atomicity.py` (24) |
| NAV-01 `start` | Clear + outcome separate | One transaction after reply | `bot/handlers.py:892-940` | `tests/test_wp07_nav01_nav03_nav04_atomic.py` (shared 25) |
| NAV-02 `show_menu` | Clear + outcome separate | One transaction after display helper | `bot/handlers.py:951-969` | `tests/test_wp07_nav02_nav05_simple_clear_atomic.py` (shared 14) |
| NAV-03 `list_conversations` | Clear + outcome separate; failure path separate | One transaction per exit; failure outcome atomic | `bot/handlers.py:1051-1143` | `tests/test_wp07_nav01_nav03_nav04_atomic.py` (shared 25) |
| NAV-04 `list_watches` | Clear + outcome separate | One transaction after display | `bot/handlers.py:1378-1412` | `tests/test_wp07_nav01_nav03_nav04_atomic.py` (shared 25) |
| NAV-05 `start_new_chat` | Clear + outcome separate | One transaction after `_show_repos` | `bot/handlers.py:2686-2715` | `tests/test_wp07_nav02_nav05_simple_clear_atomic.py` (shared 14) |
| NAV-06 `open_conversation` | Route activation + outcome separate | One transaction after successful display | `bot/handlers.py:1145-1245` | `tests/test_wp07_nav06_open_conversation_atomic.py` (12) |

The exact target diff (`52e7789..30dfa0d` limited to target files) is 11 files, +2,565/−124. The
sync commit also contains WP-05/WP-06/DEF-011-B and documentation changes; see `REV-SCOPE-01`.

## 5. Source documents inspected

- `.agent/PROGRESS.md:4255-4460` — owner acceptance record and NAV status.
- `docs/audits/OHB2-WP07-FINAL-STABILIZATION-AUDIT.md` — historical baseline, NAV scope, acceptance boundary.
- `docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md` — Scope A/A′/B proposal; not an acceptance.
- `docs/audits/OHB2-WP07-GIT-STABILIZATION-PLAN.md` — proposed bounded commits; plan only.
- `docs/audits/OHB2-WP07-NEW-DEF03-S3-DELIVERY-AND-ACCEPTANCE-RECONCILIATION.md` — Scope A accepted; NAV `REQUIRES_SEPARATE_OWNER_DECISION`.
- `docs/reviews/OHB2-WP07-F1-OPTION-C-IMPLEMENTATION-AND-INDEPENDENT-REVIEW-REPORT.md`.
- `docs/reviews/OHB2-WP07-NEW-DEF03-WATCH-UNWATCH-ATOMICITY-AND-INDEPENDENT-REVIEW-REPORT.md`.
- `docs/reviews/OHB2-WP07-BATCH04-DEF011-F02-HANDLERS-NEW-DEF03-SCOPE-AUDIT.md` — hunk/scope context.
- `bot/db.py`, `bot/handlers.py`, `bot/watcher.py`, and the seven WP-07 test files in the candidate clone.

Conflict found: the historical final audit says NAV-01..06 are **not in HEAD** and are
working-tree-only (`OHB2-WP07-FINAL-STABILIZATION-AUDIT.md:165,180-185,262-266`), while the current
repository has NAV markers in `HEAD:bot/handlers.py` and candidate `30dfa0d` committed them. The
historical audit was accurate at baseline `52e7789`; Git history and the current candidate are
authoritative for the current state. See `REV-DOC-01`.

## 6. Per-target review results

### 6.1 F-1 Option C — `PASS_WITH_NOTES`

**Problem:** six reply/routing paths commit local state plus `durable_completed`, then send/edit
Telegram. A post-commit Telegram failure must not roll back or downgrade the local acknowledgement,
and must leave separate durable failure evidence.

**Code:** the six paths are present and use the atomic helpers:

- `cancel_route` — `bot/handlers.py:2585-2595`
- `cancel_route_button` — `:2598-2610`
- `reply_prompt` — `:1835-1868`
- `repo_search_prompt` — `:2738-2748`
- `pick_repo` — `:2797-2823`
- `new_chat_no_repo` — `:2825-2840`

They write state/outcome atomically, then perform Telegram I/O outside the transaction. PTB's
`handle_processing_error` path writes `update_failures`; `processed_updates` remains the dedupe/ack
source. The 14 tests drive real `Application.process_update` (and one real `TelegramPoller`), with
patched Telegram I/O. Mutation M3 (drop `update_failures` insert) made the F-1 evidence tests fail.

**Limits:** pre-send failure, ambiguous Telegram delivery, and no operator surface for
`update_failures` remain. These are bounded and documented; no exactly-once claim is made.

### 6.2 NEW-DEF-03 non-concurrency — `PASS_WITH_NOTES`

**Problem:** state mutations and outcome writes were separate commits. The accepted Scope A requires
one SQLite transaction per transition for watch, unwatch, and awaiting state, with backward
compatibility and F-1 preservation.

**Code:** verified:

- `add_watched_and_record_outcome` — `bot/db.py:1953-2000`
- `remove_watched` / `_remove_watched_nocommit` — `:2065-2125`
- `remove_watched_completing` — `:2128-2185`
- `clear_awaiting_and_record_outcome` — `:2911-2941`
- `set_awaiting_and_record_outcome` — `:2943-2973`
- `Watcher.unwatch` — `bot/watcher.py:717-765`

The helper uses `BEGIN IMMEDIATE`, writes state and outcome with `mark_update_outcome(..., commit=False)`,
and commits once. Rollback paths are exercised by the 9 atomic-state tests and 24 watch/unwatch tests.
Mutation M1 (skip clear-helper outcome) failed 5 of 6 selected tests; M2 (skip watch/unwatch outcome)
failed all 4 selected tests.

**Limits:** this is not `NEW-DEF-03_COMPLETE`; navigation and durable-intent sites are separate.
The owner acceptance record explicitly covers five items only. `NAV-01..06` is reviewed separately
and is not accepted.

### 6.3 NAV-01 `start` — `BLOCKED` (acceptance), technical code/tests pass

`start` sends the welcome message before `clear_awaiting_and_record_outcome`; a send failure prevents
state clear and is handled by PTB error handling. Tests cover success, outcome-write rollback, send
failure, `update_id=None`, and unauthorized behavior. Code: `bot/handlers.py:892-940`.

**Acceptance:** NAV is not in the owner-accepted five items; `NAV-01..06` is explicitly unaccepted.
Code/tests pass; acceptance is blocked pending owner decision D-A′.

### 6.4 NAV-02 `show_menu` — `BLOCKED` (acceptance), technical code/tests pass

`show_menu` calls `_safe_edit_noop` then clears/records `explicitly_ignored` atomically. Tests cover
success, rollback, `update_id=None`, display failure, unexpected exception, and unauthorized behavior.
Code: `bot/handlers.py:951-969`.

**Bounded limitation:** `_safe_edit_noop` catches all `TelegramError`/`TimeoutError` and returns
False; a real display failure is therefore recorded as `explicitly_ignored`, not as failure evidence.
This is existing WP-02 policy and is explicitly tested; it is not a WP-07 regression. See
`REV-NAV02-01`.

**Acceptance:** NAV unaccepted; blocked pending D-A′.

### 6.5 NAV-03 `list_conversations` — `BLOCKED` (acceptance), technical code/tests pass

All five exits are handled: success/empty/expected 4xx clear + `explicitly_ignored`; operational
failure raises before clear; DB filter failure clears + writes a failure outcome atomically. Tests
cover success, empty, 4xx, operational 5xx/429/no-code, DB filter failure, rollback, `update_id=None`,
unauthorized, and repeated delivery. Code: `bot/handlers.py:1051-1143`.

**Coverage gap:** no explicit test for a Telegram display failure on the NAV-03 success path. The
code's `_safe_edit` raises before clear, so the current behavior is correct; see `REV-NAV-TEST-01`.

**Acceptance:** NAV unaccepted; blocked pending D-A′.

### 6.6 NAV-04 `list_watches` — `BLOCKED` (acceptance), technical code/tests pass

`list_watches` reads the watch list before display, then clears/records after display. Tests cover
empty/items, outcome rollback, DB read failure, `update_id=None`, and unauthorized behavior. Code:
`bot/handlers.py:1378-1412`.

**Coverage gap:** no explicit Telegram display-failure test on the success path; see
`REV-NAV-TEST-01`.

**Acceptance:** NAV unaccepted; blocked pending D-A′.

### 6.7 NAV-05 `start_new_chat` — `BLOCKED` (acceptance), technical code/tests pass

`start_new_chat` calls `_show_repos` before clearing/recording; operational API failure raises
before any write. Tests cover success, outcome rollback, `update_id=None`, operational 5xx, and
unauthorized behavior. Code: `bot/handlers.py:2686-2715`.

**Coverage gap:** no explicit Telegram display-failure test on the success path; see
`REV-NAV-TEST-01`.

**Acceptance:** NAV unaccepted; blocked pending D-A′.

### 6.8 NAV-06 `open_conversation` — `BLOCKED` (acceptance), technical code/tests pass

`open_conversation` activates the route and records the outcome only after `_edit_or_send` returns
True. Tests cover success, title/TTL, empty title, outcome-write rollback, prior-route survival,
`update_id=None`, display failure, unchanged display text, repeated delivery, and helper rollback.
Code: `bot/handlers.py:1145-1245`.

**Acceptance:** NAV unaccepted; blocked pending D-A′.

## 7. Tests and checks actually run

Environment:

- Python: 3.13.15
- PTB: 22.8 (`requirements.txt` pin `python-telegram-bot[all]==22.8`)
- pytest: 9.0.3
- Node: v24.22.2
- Isolated venv: `/tmp/rev-ind-01-wp07-venv`, installed from `requirements-dev.txt`
- No dependency files changed.

### 7.1 Focused WP-07 tests — exact candidate `30dfa0d`

Command:

```sh
/tmp/rev-ind-01-wp07-venv/bin/python -m pytest -q \
  tests/test_wp07_atomic_state_outcome.py \
  tests/test_wp07_f1_notification_failure.py \
  tests/test_wp07_nav01_nav03_nav04_atomic.py \
  tests/test_wp07_nav02_nav05_simple_clear_atomic.py \
  tests/test_wp07_nav06_open_conversation_atomic.py \
  tests/test_wp07_watch_unwatch_atomicity.py \
  tests/test_wp07_route_renewal_and_policy.py
```

Result: **100 passed in 7.03s**, exit 0.

Per-file:

| File | Result |
|---|---|
| `test_wp07_atomic_state_outcome.py` | 9 passed |
| `test_wp07_f1_notification_failure.py` | 14 passed |
| `test_wp07_nav01_nav03_nav04_atomic.py` | 25 passed |
| `test_wp07_nav02_nav05_simple_clear_atomic.py` | 14 passed |
| `test_wp07_nav06_open_conversation_atomic.py` | 12 passed |
| `test_wp07_watch_unwatch_atomicity.py` | 24 passed |
| `test_wp07_route_renewal_and_policy.py` | 2 passed |

### 7.2 Relevant integration/regression tests

Command:

```sh
/tmp/rev-ind-01-wp07-venv/bin/python -m pytest -q \
  tests/test_handlers.py \
  tests/test_sw06_unwatch_db_failure_propagation.py \
  tests/test_watcher.py \
  tests/test_duplicate_update_dispatch.py \
  tests/test_stage2_custom_polling.py \
  tests/test_4b.py \
  tests/test_sw07_api_handler_failure_propagation.py \
  tests/test_d1_extended_transient_codes.py
```

Result: **395 passed, 28 warnings in 23.62s**, exit 0.

### 7.3 Full Python suite — exact candidate `30dfa0d`

```sh
/tmp/rev-ind-01-wp07-venv/bin/python -m pytest -q
```

Result: **3450 passed, 74 warnings in 158.88s**, exit 0.

### 7.4 Current `HEAD` focused check

At `0774c9c` (candidate plus later REV-01 changes):

```sh
/tmp/rev-ind-01-wp07-venv/bin/python -m pytest -q [same seven WP-07 files]
```

Result: **100 passed in 6.47s**, exit 0. WP-07 test files are unchanged after `30dfa0d`.

### 7.5 Static, security, frontend, diff checks

| Check | Result | Exit |
|---|---|---|
| `pyflakes bot/ automation/ tools/ main.py tests/` | no findings | 0 |
| `bandit -r bot/ automation/ tools/ main.py -lll -s B613` | High 0, Low 5, Medium 19 | 0 |
| `pip_audit -r requirements-dev.txt` | No known vulnerabilities found | 0 |
| `node --test tests/frontend/*.test.js` | 280 passed, 0 failed | 0 |
| `git diff --check` | clean | 0 |

No production Telegram/OpenHands API call or real credential was used. Tests use fakes and patched
Telegram I/O. The dependency install contacted the package registry only.

### 7.6 Mutation checks (disposable copies only)

| Mutation | Selected tests | Result |
|---|---|---|
| M1 — `clear_awaiting_and_record_outcome` skips outcome write | 6 tests across atomic/NAV/F-1 | **5 failed, 1 passed** (expected; NAV-06 uses set helper) |
| M2 — `add_watched_and_record_outcome` / `remove_watched` skip outcome write | 4 watch/unwatch tests | **4 failed** |
| M3 — `mark_update_outcome` drops `update_failures` insert | F-1 cancel + watch timeout | **2 failed** |

The mutations were applied only to temporary clones; the candidate clone was not modified.

## 8. Findings

### REV-NAV-ACC-01 — NAV-01..06 are unaccepted and now committed on main

**Severity:** HIGH
**Blocks acceptance:** YES
**Files/evidence:** `bot/handlers.py:892,951,1051,1145,1378,2686`; `.agent/PROGRESS.md:4277` and `:4441`; `docs/audits/OHB2-WP07-FINAL-STABILIZATION-AUDIT.md:180-185,205-209`; `docs/audits/OHB2-WP07-NEW-DEF03-S3-DELIVERY-AND-ACCEPTANCE-RECONCILIATION.md:33,78,225-236`.
**Evidence:** the owner acceptance record covers exactly A-1..A-5 and explicitly lists NAV-01..06 as
unaccepted. The final audit and reconciliation both mark NAV as `REQUIRES_SEPARATE_OWNER_DECISION`.
Candidate `30dfa0d` commits NAV markers and tests to main.
**Impact:** NAV code/tests are technically verified, but the work has no owner acceptance; it cannot
be accepted as part of WP-07 on the current record.
**Recommended correction:** obtain owner decision A′-1/A′-2, or exclude/revert NAV in a separate
explicitly authorized change. Do not silently absorb it into Scope A.

### REV-SCOPE-01 — Candidate commit is a broad sync, not an isolated WP-07 commit

**Severity:** MEDIUM
**Blocks acceptance:** commit-level isolation only; not the target code
**Evidence:** `30dfa0d` includes `bot/attachments.py` (+548/−…), `bot/app.py`, WP-05/WP-06 docs, and
`.github/workflows/f02-review.yml`, in addition to WP-07 target files.
**Impact:** target hunks are identifiable and tested, but a dedicated WP-07 publication cannot be
claimed from this commit alone.
**Recommended correction:** separate target changes into a dedicated commit or record explicit
bundling authorization.

### REV-DOC-01 — Historical audit statements about NAV are stale

**Severity:** LOW
**Blocks acceptance:** NO
**Evidence:** `docs/audits/OHB2-WP07-FINAL-STABILIZATION-AUDIT.md:165,180-185,262-266` says NAV is
not in HEAD and uncommitted; current `HEAD:bot/handlers.py` contains NAV markers and `30dfa0d`
committed them.
**Impact:** a reader may treat the historical audit as current state. The audit was accurate at
`52e7789`; Git history/current candidate are authoritative now.
**Recommended correction:** add a superseding note in a separate documentation task.

### REV-NAV-TEST-01 — NAV-03/04/05 display-failure coverage gap

**Severity:** LOW
**Blocks acceptance:** NO
**Evidence:** `tests/test_wp07_nav01_nav03_nav04_atomic.py:221-290` covers NAV-03 success/empty/4xx/
operational/DB failure but not Telegram display failure; `:141-205` covers NAV-04 reads/rollback but
not display failure; `tests/test_wp07_nav02_nav05_simple_clear_atomic.py:174-239` covers NAV-05
success/rollback/operational but not display failure. NAV-02 and NAV-06 do have display-failure tests.
**Impact:** a future regression that swallows `_safe_edit` errors could pass NAV-03/04/05 tests even
though the current code raises before clearing state.
**Recommended correction:** add explicit display-failure tests if NAV is accepted.

### REV-NAV02-01 — `show_menu` treats all display failures as no-op

**Severity:** LOW
**Blocks acceptance:** NO
**Evidence:** `bot/handlers.py:951-969` uses `_safe_edit_noop`; `:109-126` catches all
`TelegramError`/`TimeoutError` and returns False; then state is cleared and outcome is recorded as
`explicitly_ignored`. `tests/test_wp07_nav02_nav05_simple_clear_atomic.py:111-128` codifies this.
**Impact:** a real display failure is ack-eligible rather than recorded as failure evidence. This is
existing WP-02 policy, not a WP-07 regression, but it is a bounded limitation.
**Recommended correction:** decide whether NAV-02 should use fail-closed display semantics; do not
change it without owner approval.

### REV-F1-01 — F-1 Option C is test-only and has documented limits

**Severity:** INFO
**Blocks acceptance:** NO
**Evidence:** no production file was changed for F-1; the six handlers already used the atomic
helpers; 14 tests and M3 verify the contract. Limits: pre-send failure, ambiguous delivery, no
operator surface for `update_failures`, no exactly-once.
**Recommended correction:** none for Option C; a recovery/operator surface is a new mechanism.

### REV-ND03-01 — Scope A is accepted, but NEW-DEF-03 is not complete

**Severity:** INFO
**Blocks acceptance:** NO for A-1..A-5; NAV is separate
**Evidence:** owner acceptance covers five items; remaining NEW-DEF-03 navigation/durable-intent
sites are open; NAV is the unaccepted sub-scope.
**Recommended correction:** keep the bounded acceptance wording; do not mark NEW-DEF-03 complete.

## 9. Missing evidence and limitations

- The historical audit hash/report integrity topic was outside this task; not re-audited here.
- No live Telegram/OpenHands production service was used.
- No Python 3.11 CI matrix was run; only Python 3.13.15 was available.
- The candidate commit is broad; target hunks were isolated by file/function and marker, not by a
  dedicated WP-07-only commit.
- The review did not grant or infer owner acceptance for NAV.

## 10. Overall verdict

**`BLOCKED`.**

The target code and tests are technically sound: F-1 Option C and accepted NEW-DEF-03 Scope A pass
focused, relevant, full-suite, static/security, Node, and mutation checks. NAV-01..06 also pass their
tests, but they remain **unaccepted** by the owner and are now present in main via `30dfa0d`. The
weakest blocking result is NAV acceptance; therefore the overall verdict cannot be PASS or
PASS_WITH_NOTES.

## 11. Files modified during review

Only this review report was created:

`docs/reviews/REV-IND-01-WP-07-INDEPENDENT-REVIEW-REPORT.md`

No implementation file, test, configuration, dependency, protected path, or candidate clone was
modified. The pre-existing uncommitted concurrency changes in `/workspace/project/OpenHandBot` were
left untouched. No stage, commit, push, fetch, merge, PR, deployment, or Autopush action occurred.
