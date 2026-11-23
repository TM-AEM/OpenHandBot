# OHB2-NEW03 — Test Coverage F1/F2 Implementation Report

**Task:** `OHB2-NEW03-TEST-COVERAGE-F1-F2`
**Status:** `DONE — TEST-ONLY`
**Date:** 2026-11-23

---

## 1. Baseline

- Repository: `/workspace/project/OpenHandBot`
- Branch: `main`
- HEAD: `7d91f683047ae8bac8bb2000e90dab38532ef1ba`
- Parent: `de17463dd9c31a070f0e8a0f08a8da9c1ad42a5f`
- Tree: `fe8945e31d5c8714db8215d320a489d23a2980c7`
- Upstream: `origin/main` at the same commit.
- Initial working tree: no tracked modifications. The prior independent-review report
  `docs/reviews/OHB2-NEW03-INDEPENDENT-REVIEW-REPORT.md` was already untracked and
  was preserved unchanged.
- No production code or existing test was modified.

## 2. Files changed

Added:

- `tests/test_new03_f1_f2_coverage.py` — exactly two tests.
- `docs/reviews/OHB2-NEW03-TEST-COVERAGE-F1-F2-IMPLEMENTATION-REPORT.md` — this report.

Not changed:

- `bot/db.py`
- `bot/outbox.py`
- `bot/handlers.py`
- Existing tests, including `tests/test_new03_unavailable_selection_atomicity.py`
- Mini App/frontend files
- `.agent/PROGRESS.md`
- `docs/reviews/OHB2-NEW03-INDEPENDENT-REVIEW-REPORT.md`
- `docs/reviews/OHB2-NEW03-UNAVAILABLE-SELECTION-ATOMICITY-IMPLEMENTATION-REPORT.md`

## 3. F1 test design

Test: `test_clear_unavailable_selection_holds_begin_immediate_write_lock`.

- Two independent `Database` instances open the same temporary SQLite file.
- Cleanup runs in a separate thread and calls
  `Database.clear_unavailable_selection(OWNER, CID)`.
- A test hook on `_delete_setting_nocommit` pauses cleanup **after** `BEGIN` and
  the conditional reads, but **before** the first write.
- A `threading.Event` signals that cleanup has entered that boundary; no arbitrary
  sleep is used as the correctness mechanism.
- The competing connection sets `PRAGMA busy_timeout=50` and attempts
  `BEGIN IMMEDIATE`. While cleanup holds its write reservation, this must raise
  `sqlite3.OperationalError` (`database is locked`).
- The test then releases cleanup, joins the thread, and asserts the writer can
  start a new `BEGIN IMMEDIATE` transaction and write the newer `last_accessed`
  value `B`.
- Final invariants: cleanup cleared `last_accessed`/`awaiting`; the later writer
  successfully set `last_accessed=B`; no unrelated state was touched.

The hook is a test-only pause at the transaction boundary. It does not replace
the production cleanup logic.

## 4. F1 mutation result

Isolated copy: `/tmp/ohb2-f1-mutation.cKkaow`.

Mutation: in the temporary copy only, replaced

```python
conn.execute("BEGIN IMMEDIATE")
```

with

```python
conn.execute("BEGIN")
```

in `Database.clear_unavailable_selection()`.

Command:

```text
cd /tmp/ohb2-f1-mutation.cKkaow
/tmp/ohb2-review-venv/bin/python -m pytest -q \
  tests/test_new03_f1_f2_coverage.py::test_clear_unavailable_selection_holds_begin_immediate_write_lock
```

Result: **FAILED, exit 1**, at the expected assertion:

```text
AssertionError: competing writer entered while cleanup held BEGIN IMMEDIATE
assert False
 +  where False = isinstance(None, <class 'sqlite3.OperationalError'>)
```

The mutation was not applied to the real repository. The real tree remained
unchanged.

## 5. F2 test design

Test: `test_handler_cleanup_failure_logs_and_preserves_routing`.

- Uses a real temporary `Database`.
- Creates a confirmed tombstone with
  `delete_conversation(CID, ..., remote_confirmed=True)`.
- Seeds `last_accessed=A` and `awaiting=(A, "route")`.
- Replaces only `db.clear_unavailable_selection` with a function that raises
  `sqlite3.OperationalError`; this is a controlled database failure, not a mock
  of the handler result.
- Runs the real `handlers._send_prompt()` control flow with a real database and a
  minimal Telegram-shaped update/context.
- Asserts:
  - the cleanup method was called with `(OWNER, CID)`;
  - the exact factual deletion message was sent;
  - `_TARGET_UNAVAILABLE_NOTICE` was not sent;
  - `last_accessed` and `awaiting` remain unchanged;
  - the tombstone remains confirmed;
  - no outbox row was created;
  - the handler records `EXPLICITLY_IGNORED`;
  - an error log record contains the cleanup-failure context.

## 6. F2 mutation result

Isolated copy: `/tmp/ohb2-f2-mutation.rmSQ03`.

Mutation: in the temporary copy only, removed the `try/except` around
`db.clear_unavailable_selection()` in the confirmed-deletion branch of
`_send_prompt()`.

Command:

```text
cd /tmp/ohb2-f2-mutation.rmSQ03
/tmp/ohb2-review-venv/bin/python -m pytest -q \
  tests/test_new03_f1_f2_coverage.py::test_handler_cleanup_failure_logs_and_preserves_routing
```

Result: **FAILED, exit 1**, with the injected exception propagating from
`bot/handlers.py:3359`:

```text
sqlite3.OperationalError: injected F2 cleanup failure
```

The mutation was not applied to the real repository. The real tree remained
unchanged.

## 7. Test commands and results

Environment: `/tmp/ohb2-review-venv`, Python 3.13.15, created from the repository's
`requirements-dev.txt` because the prior environment was unavailable. No
dependency file was changed.

| Command | Result |
|---|---|
| New tests only | **2 passed**, exit 0, 0.42s |
| Focused: new tests + NEW-03 + persistent-routing + NEW-01 + NEW-02 + NEW-04 + grouping + outbox + handlers + F-1 tombstone + conversation/remote deletion | **450 passed**, exit 0, 2 warnings, 24.38s |
| Full Python: `pytest -q` | **3771 passed**, 0 failed, 74 warnings, 179.17s, exit 0 |
| F1 mutation (isolated copy) | **1 failed**, exit 1, expected `BEGIN IMMEDIATE` assertion |
| F2 mutation (isolated copy) | **1 failed**, exit 1, expected propagated `sqlite3.OperationalError` |
| `node --test tests/frontend/*.test.js` | **280 pass / 0 fail**, exit 0 |
| `pyflakes bot automation tools main.py tests/` | exit 0 |
| `compileall -q bot automation tools main.py tests` | exit 0 |
| `git diff --check` | exit 0 |
| `bandit -r bot/ automation/ tools/ main.py -lll -s B613` | High **0**, exit 0 |
| `pip_audit -r requirements-dev.txt` | No known vulnerabilities, exit 0 |

No skipped tests were reported by the full run. Warnings are pre-existing
third-party deprecation warnings.

## 8. Static and scope verification

- `pyflakes` initially reported one unused `pytest` import in the new test file;
  it was removed and the final run is clean.
- `compileall` and `git diff --check` pass.
- `git diff --stat` for tracked files is empty: no production or existing test
  file changed.
- `git status` shows only the new test file, the new report, and the pre-existing
  untracked independent-review report.
- No Mini App/frontend source was changed.
- No worker, scheduler, process, queue, or database owner was introduced.
- NEW-04 implementation and its deferred independent-review status were not
  changed.
- No DEF-011 scope was changed.

## 9. Production code and defect status

No production code was modified. No genuine implementation defect was
demonstrated by either test. The tests cover the existing intended behavior:

- `BEGIN IMMEDIATE` provides the required write reservation before cleanup
  writes.
- Handler cleanup failure is caught, logged, and does not produce a false
  success/target-unavailable notice; the deletion message remains factual.

## 10. Limitations

- F1 uses a test-only instance hook to pause cleanup at the transaction boundary;
  this is necessary to make the lock acquisition observable deterministically.
- F1's mutation replaces `BEGIN IMMEDIATE` with deferred `BEGIN`; removing the
  explicit BEGIN entirely would also be detected by the same boundary hook.
- F2 uses a controlled failure at the database-method boundary; it does not
  simulate every possible SQLite failure mode.
- No live Telegram/OpenHands calls were made.
- The review environment was created locally; no dependency files were changed.
- NEW-04 independent review remains deferred and is not marked reviewed.

## 11. Git and safety confirmation

No commit, push, PR/MR, merge, deployment, release, or Autopush activation was
performed. No `git reset`, `git clean`, force operation, broad deletion, or
`git add .`/`git add -A` was used. The real working tree contains only the
intended new test and report, plus the pre-existing untracked review report.
