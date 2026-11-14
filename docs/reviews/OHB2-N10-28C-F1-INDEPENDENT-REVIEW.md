# OHB2-N10-28C-F1 — INDEPENDENT REVIEW (fresh-context, read-only)

Reviewer: fresh-context independent reviewer; not the author of the F-1 change. All actions were
read-only. No edits, staging, commits, pushes, fetches, pulls, branch switches, PRs, merges, or
deployment. No Autopush/backup/`requirements.txt` edits. No real Telegram/OpenHands/external network
operations (local SQLite + `TestClient`/fake clients only).

Verdict: **PASS**.

---

## 1. Repository state (independently observed)

- HEAD = `6021658cf3c1664ed0eadeaed2acee4e86721b6b` (matches EXPECTED HEAD).
- Branch = `release/ohb2-20261101`.
- Index (staged) = empty. `git stash list` = empty.
- Worktree dirty (unchanged by this review): the pre-existing 28C/28D edits plus untracked
  backup/autopush/tools/docs files and the three new test files. No file was created/modified by
  this review except this report.
- Target report `docs/reviews/OHB2-N10-28C-F1-INDEPENDENT-REVIEW.md` was **absent** before creation.

---

## 2. F-1 diff (independently verified)

The F-1 change is confined to the test function
`tests/test_miniapp_reconcile.py::test_reconcile_mark_sent_never_clobbers_a_discard`
(current lines 220-271). The rest of the file's diff vs HEAD belongs to the earlier 28C work
(e.g. `test_discard_pending_marks_discarded_terminal`, `test_discard_after_send_may_have_started_not_confirmed`),
not to F-1.

Original (broken) assertions:
```
assert results["discard"].status_code == 200
assert results["discard"].json().get("cancellation") == "not_confirmed"
```
Corrected assertions:
```
assert db.get_outbox(oid).status == "sent"
assert results["mark_sent"].status_code == 200
assert results["mark_sent"].json()["state"] == "accepted"
discard = results["discard"]
if discard.status_code == 200:
    assert discard.json().get("cancellation") == "not_confirmed"
    assert discard.json()["state"] == "ambiguous"
else:
    assert discard.status_code == 409
    assert discard.json()["error"] == "already_terminal"
```

No production file was modified by F-1: `git diff HEAD --numstat -- bot/` lists only the pre-existing
28C/28D files (`bot/db.py`, `bot/handlers.py`, `bot/openhands_client.py`, `bot/outbox.py`,
`bot/web/services.py`, `bot/web/static/app.js`). A `find -newermt '-60 minutes'` over `bot/`,
`automation/`, `tools/`, `requirements.txt`, `main.py` returned **NONE**.

---

## 3. Concurrency retained (verified)

- Two threads: `threading.Thread(target=worker, args=(c1, "discard"))` and
  `(c2, "mark_sent")`.
- A `threading.Barrier(2)` is still used; each worker calls `barrier.wait()` before issuing its POST.
- Two independent SQLite connections: `db = Database(path)` and `db2 = Database(path)`. `Database.__init__`
  calls `sqlite3.connect(path, ...)` per instance, so these are genuinely separate connections on the
  same WAL file.
- The competing operations were **not** serialized and synchronization was **not** removed.

---

## 4. Accepted outcomes (verified against product)

The test accepts exactly:
- discard `200` with `cancellation == "not_confirmed"` and `state == "ambiguous"` (discard ran first;
  no change, no false cancellation claim), **or**
- discard `409` with `error == "already_terminal"` (mark_sent ran first and won).

It also asserts `mark_sent` returns `200` / `state == "accepted"` and the final persisted state is
`"sent"` in either outcome. Any other discard status (e.g. 500/400/404) fails the else-branch
`assert discard.status_code == 409`; incorrect bodies fail the corresponding body asserts. No
unexpected status is hidden.

I reproduced both branches independently (forced ordering) and captured the exact bodies:

| Ordering | discard | mark_sent | final |
|---|---|---|---|
| discard first | `200 {'state':'ambiguous','cancellation':'not_confirmed'}` | `200 {'state':'accepted'}` | `sent` |
| mark_sent first | `409 {'error':'already_terminal', ...}` | `200 {'state':'accepted'}` | `sent` |

Both branches are real, correct product behavior; neither assertion is dead code.

---

## 5. Regression-detection assessment (verified)

Using in-memory monkeypatches of `MiniAppService.reconcile_outbox` (no files changed), I confirmed the
test's assertion logic detects:
1. A false cancellation claim on a 200 (`cancellation == "discarded"`) — **DETECTED**.
2. An unexpected discard status (500) — **DETECTED**.
3. A wrong `mark_sent` body (`state != "accepted"`) — **DETECTED**.
4. A genuine cancellation regression that actually flips the DB row to `discarded` — **DETECTED**
   by the final-state `== "sent"` assert (final was `discarded` in the probe).

Compared with the HEAD baseline version of the same test (which accepted
`final in ("discarded","sent")`), the F-1 version is **stronger**: it pins the final state to `sent`,
consistent with the 28C product contract that a `discard` on an `unknown` row never mutates it.

---

## 6. Independently reproduced test results

All commands run locally; no external requests.

| # | Command | Result | Exit |
|---|---|---|---|
| 1 | `pytest tests/test_miniapp_reconcile.py::test_reconcile_mark_sent_never_clobbers_a_discard -q` × 30 | **30/30 passed** | 0 |
| 2 | `pytest tests/test_miniapp_reconcile.py -q` × 20 | **20/20 runs passed** (16 tests collected) | 0 |
| 3 | `pytest -q` (full suite) | **1513 passed, 71 warnings** (50.24s) | 0 |
| 4 | `node --test tests/frontend/*.test.js` | **134 pass, 0 fail** | 0 |
| 5 | `.venv/bin/python -m pyflakes bot/ main.py tests/` | clean (no output) | 0 |
| 6 | `.venv/bin/python -m compileall -q bot/ main.py tests/` | COMPILE_OK | 0 |

These match the F-1 report's reported counts (30/30, 20/20, 1513, 134, pyflakes clean, COMPILE_OK).
Warnings are deprecation-only. No skips/xfails.

---

## 7. Findings

No blocking findings.

- **INFORMATIONAL (I-1):** `results` is a plain dict written from two threads without a lock. In
  CPython this is safe here: the two threads write distinct keys and `dict.__setitem__` is atomic
  under the GIL; both threads are joined before reads. Not a defect.
- **INFORMATIONAL (I-2):** The test name ("mark_sent never clobbers a discard") reads as if the final
  state could be either; the docstring and asserts correctly pin the `unknown`-row contract to a final
  state of `sent`. Cosmetic naming nit only.
- **INFORMATIONAL (I-3):** The corrected test is a useful guard: if a future product change made an
  `unknown` row discardable, the final-state assert would fail — desirable.

---

## 8. Limitations

- The natural interleaving observed in this environment is discard-first (the mark_sent-first branch
  was reached by forcing ordering). Both branches were nevertheless proven reachable and correct.
- No real Telegram/OpenHands/network operations were performed; behavior was validated via local
  SQLite and the in-process `TestClient` only.
- Regression-detection was assessed via in-memory monkeypatches of the service method, not by
  modifying any source file.

---

## 9. Verdict

- F-1 diff independently verified and correctly scoped (test-only).
- Genuine concurrency retained (2 threads + barrier + 2 independent connections).
- Accepts exactly the two legitimate outcomes; rejects unexpected statuses/bodies.
- `mark_sent` 200/`accepted` and final state `sent` verified.
- Regression detection confirmed.
- Production and unrelated files unchanged; test counts reproduced.

**Verdict: PASS.**

Publication readiness: the F-1 blocker is resolved and the change set is stable under repeated and
full-suite runs. Remaining review items (F-2 LOW, F-3 LOW, F-4/F-5 INFORMATIONAL) are out of scope
and non-blocking. Publication still requires separate authorization.

STOP — no 28E, no publication. This review made no edits except creating this report.
