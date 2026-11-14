# OHB2-N10-28C-F1 — Fix the Order-Dependent Mini App Discard Race Test

Status: COMPLETE (test-only correction). No production change, no publication.

## 1. Baseline and final state

- Baseline HEAD (audited before editing): `6021658cf3c1664ed0eadeaed2acee4e86721b6b`.
- Final HEAD (unchanged): `6021658cf3c1664ed0eadeaed2acee4e86721b6b`.
- Branch: `release/ohb2-20261101` (unchanged).
- Index (staged): empty before and after. `git stash list`: empty. No commit/push/fetch/pull/
  branch-switch/PR/merge/deploy performed.
- All pre-existing tracked and untracked changes preserved.

## 2. Exact changed files

- `tests/test_miniapp_reconcile.py` — **only** file changed by this task
  (`test_reconcile_mark_sent_never_clobbers_a_discard`, around lines 220-272).
- No production files touched. Verified: a `find -newermt '-30 minutes'` over `bot/`,
  `automation/`, `requirements.txt`, `tests/`, `docs/reviews/` reports only
  `tests/test_miniapp_reconcile.py` (plus the earlier independent-review report written in the
  previous task). `git diff HEAD -- bot/ requirements.txt automation/` shows no new delta from this
  task.

## 3. The fix (F-1)

The original test asserted that `discard` always returns 200. Under a genuine barrier race,
`mark_sent` can win first (`unknown`→`sent`), after which `discard` correctly returns
**409 `already_terminal`**. Both interleavings are legitimate; only the assertion was wrong.

The corrected test now:
- Keeps the real concurrency (two threads, `threading.Barrier(2)`, two independent SQLite
  connections). Synchronization was **not** removed and the operations were **not** serialized.
- Asserts the invariant that holds in every legitimate interleaving:
  `db.get_outbox(oid).status == "sent"` (an ambiguous row can never become `discarded`).
- Asserts `mark_sent` won: status 200 and `state == "accepted"`.
- Accepts exactly the two legitimate `discard` outcomes:
  - `200` → body `cancellation == "not_confirmed"` and `state == "ambiguous"` (discard ran first,
    no change, no false cancellation claim);
  - else → `409` with `error == "already_terminal"` (mark_sent ran first).
- Any other status (e.g. 400/404/500) fails the `assert discard.status_code == 409` in the else
  branch; no unexpected status is hidden.

## 4. Verification (exact commands, exit codes, counts)

| # | Command | Result | Exit |
|---|---|---|---|
| 1 | `pytest tests/test_miniapp_reconcile.py::test_reconcile_mark_sent_never_clobbers_a_discard -q` × **30** | 30/30 passed | 0 |
| 2 | `pytest tests/test_miniapp_reconcile.py -q` × **20** | 20/20 runs passed (16 tests each) | 0 |
| 3 | `pytest -q` (full suite) ×2 | **1513 passed, 71 warnings** each (49.9s / 50.6s) | 0 |
| 4 | `node --test tests/frontend/*.test.js` | **134 pass, 0 fail** | 0 |
| 5 | `.venv/bin/python -m pyflakes bot/ main.py tests/` | clean (no output) | 0 |
| 6 | `.venv/bin/python -m compileall -q bot/ main.py tests/` | COMPILE_OK | 0 |

Warnings are deprecation-only (e.g. `starlette.testclient` anyio alias, PTB). No skips/xfails.

Before the fix, `pytest tests/test_miniapp_reconcile.py` failed ~50% of standalone runs (8/15 in the
independent review). After the fix: **0/20 standalone failures and 0/30 targeted failures.**

## 5. Branch-reachability evidence

- Under natural thread timing, the discard-first outcome dominated (200/200 over a 200-trial probe);
  the final state was always `sent`.
- The mark_sent-first outcome (`409 already_terminal`) was proven reachable and correct by forcing
  ordering deterministically (mark_sent POST before discard POST): result
  `final=sent mark_sent=200/accepted discard=409/already_terminal`.
- Both branches therefore correspond to real, correct product behavior; neither is dead code.

## 6. Focused adversarial review of the changed test

- Accepts only the two legitimate outcomes? YES — 200 (`not_confirmed`/`ambiguous`) or 409
  (`already_terminal`); anything else fails.
- Verifies final DB state? YES — `db.get_outbox(oid).status == "sent"`.
- Still detects genuine cancellation/state-transition regressions? YES —
  - a regression that let `discard` cancel an ambiguous row would make the final state `discarded`
    and fail the invariant assert;
  - a false cancellation claim (`cancellation == "discarded"`) on a 200 would fail the
    `not_confirmed` assert;
  - a `mark_sent` regression (not winning / wrong body) would fail the mark_sent asserts;
  - an unexpected discard status would fail the else-branch `409` assert.
- Race still genuinely concurrent? YES — barrier + two threads + two connections retained.

This is a focused self-review by the task author, **not** an independent review; no separate reviewer
performed one.

## 7. Confirmation of scope and safety

- Production code untouched: `bot/db.py`, `bot/outbox.py`, `bot/handlers.py`, `bot/web/services.py`,
  `bot/web/static/app.js`, `bot/openhands_client.py` unchanged by this task.
- Autopush, backup files, and `requirements.txt` untouched by this task.
- No staging, commit, push, PR, merge, or deployment.
- No real Telegram, OpenHands, or external network operations (tests use local SQLite and
  `TestClient`/fake clients only).

## 8. Remaining findings and publication readiness

- F-1 (this task): **FIXED**.
- Other findings from the independent review remain open and out of scope here:
  - F-2 (LOW, testing limitation): frontend not-confirmed test has a vacuous negative assertion
    because the DOM stub's element-level `querySelectorAll` returns `[]`. Test-only.
  - F-3 (LOW): creation discard boundary is Telegram-only (no Mini App route).
  - F-4 (INFORMATIONAL): `ERROR` enum treated as ambiguous — safe.
  - F-5 (INFORMATIONAL): discard boundary label uses a follow-up SELECT; mutation remains atomic.
- Publication readiness: the F-1 blocker is removed. Remaining items are LOW/INFORMATIONAL and do
  not block; the 28C/28D change set is now stable under repeated and full-suite runs. Publication
  still requires separate authorization.

STOP — no 28E, no publication.
