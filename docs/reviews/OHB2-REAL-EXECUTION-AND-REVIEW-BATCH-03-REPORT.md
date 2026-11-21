# OHB2 Real Execution & Review — Batch 03 Report

**Task ID:** `OHB2-REAL-EXECUTION-AND-REVIEW-BATCH-03`
**Repository:** `/workspace/project/OpenHandBot` (real Git-backed working tree)
**Branch:** `openhands-workspace-40xxn2SbOi0tRICb3y8TE`
**HEAD at start:** `52e7789cc8cc97a7f7c09c9592226ab117db99a2` (unchanged at end)
**Mode:** Implementation + discriminating regression tests + local + isolated verification.
**Owner decision status:** `OD-01`..`OD-05` remain `PENDING_OWNER_DECISION` — none selected, recommended, or implemented.

> This report was produced by an AI agent (OpenHands) on behalf of the repository owner.

---

## 1. Executive summary

Real, narrowly scoped progress was made on the **eligible (non-owner-gated)** part of `WP-07`
(`DEF-013` and the `NEW-DEF-03` transaction-ordering portion), verified by execution, not by
inspection. Owner-gated work packages were **not** started.

Google AI Studio Build produced **no** OpenHandBot code/test/Git evidence; it is not treated as
implementation, test, or review evidence anywhere in this report.

| Work package | Status | Gate |
|---|---|---|
| `WP-07` — `DEF-013` (atomic expired-awaiting clear + outcome) | **IMPLEMENTED + TESTED** | none |
| `WP-07` — `NEW-DEF-03` (atomic state+outcome at clear/set sites; whitespace non-renewal was already done) | **IMPLEMENTED (clear + set sites) + TESTED** | none |
| `WP-07` — `DEF-011` async disk offload (**Option 1**, part 1) | **IMPLEMENTED + TESTED** (see §11) | none — quota ledger part stays `D-12` gated |
| `WP-07` — concurrency (`DEF-006`, `OD-04`) | **BLOCKED** | `OD-04` |
| `WP-01`, `WP-04` Part 2, `WP-06` Part 2, `WP-10` | **BLOCKED** | `OD-01`/`OD-02`/`OD-03`/design prereq/`OD-05` |

---

## 2. Workspace and baseline (recorded before any change)

- **Repository root:** `/workspace/project/OpenHandBot` — confirmed real Git tree (`git rev-parse --show-toplevel` = root).
- **Branch:** `openhands-workspace-40xxn2SbOi0tRICb3y8TE`; **HEAD** `52e7789`; `origin/main` == local `main` == HEAD.
- **`git status --short` at start:** clean (0 entries). **Tracked modifications:** none. **Untracked:** none. **`.openhands/`:** present and tracked-ignored (`gitignore` line `.openhands/`); `.openhands/memory/MEMORY.md` preserved untouched.
- **Python:** `3.13.15` (CI matrix targets `3.11` & `3.13`). **Node:** `v24.22.2`.
- **Dependencies:** none pre-installed; no system venv. Network to PyPI available.
- **Docker:** client present, **daemon not running** (`/var/run/docker.sock` absent) — the prior `ohb2-verify` container path is unavailable in this environment.

### Baseline gate (before changes), on the real tree

| Command | Result |
|---|---|
| `python -m pytest -q` (project-local `.venv` from `requirements-dev.txt`) | **3285 passed, 74 warnings, 0 failed** |
| `node --test tests/frontend/*.test.js` | **280 pass / 0 fail** |

`.venv/` is git-ignored (`.gitignore` line `.venv/`), so it does not enter version control.

---

## 3. Changes (files + reasons)

| File | Reason |
|---|---|
| `bot/db.py` | Added `_set_awaiting_nocommit` (refactor of `set_awaiting`; behavior-preserving), `clear_awaiting_and_record_outcome`, and `set_awaiting_and_record_outcome` — each performs the local state write **and** the update-outcome write in **one** `BEGIN IMMEDIATE` transaction (rollback-safe). |
| `bot/handlers.py` | `WP-07` `DEF-013`: the expired-awaiting branch of `handle_text` now clears state + records `EXPLICITLY_IGNORED` atomically. `WP-07` `NEW-DEF-03`: `cancel_route`, `cancel_route_button`, `reply_prompt`, `repo_search_prompt`, `pick_repo`, `new_chat_no_repo` now combine the state write with the outcome write atomically. |
| `tests/test_wp07_atomic_state_outcome.py` | New: 9 discriminating regression tests (mutation-proven). |

**Not modified:** no Mini App file (`bot/web/*`, `bot/web/static/*`, `tests/frontend/*`, `tests/test_miniapp_*.py`, `tests/test_real_http_miniapp_download.py`, `tests/_miniapp_helpers.py`, `docs/MINI_APP.md`); no ADR; no approved architectural decision; no owner-decision record; no deployment file; no dependency; no `.openhands/`.
**No** commit / push / PR / merge / deploy / release; Autopush unchanged.

---

## 4. What was fixed and why it is correct

`DEF-013`/`NEW-DEF-03` report that reply/routing paths committed `clear_awaiting`/`set_awaiting`
**separately** from the durable outcome record. A crash between the two writes leaves the local
state mutated with **no** outcome ⇒ redelivery falls into the generic `/start` hint and the
acknowledgement boundary is unnecessarily blocked.

Fix contract (matches baseline §F.1 — **no** false SQLite↔Telegram atomicity):
1. The local state write and the outcome write commit in **one** SQLite transaction.
2. The Telegram send stays **outside** the transaction; if it fails after commit, the durable
   outcome is already correct and redelivery is a no-op (at-least-once, no exactly-once claim).
3. Ineligible outcomes (`failed_*`/`partial_or_unknown`) continue to be routed to
   `update_failures` only, never to the `processed_updates` dedup source (verified by an
   adversarial edge check).

---

## 5. Verification (real commands, real output)

### 5.1 On the real working tree

| Command | Result |
|---|---|
| `python -m pytest -q` | **3294 passed, 0 failed** (baseline 3285 → +9 new tests) |
| `python -m pyflakes bot/ automation/ tools/ main.py tests/` | clean (exit 0) |
| `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | **High 0**, Medium 19, Low 5 |
| `python -m pip_audit -r requirements-dev.txt` | `No known vulnerabilities found` |
| `node --test tests/frontend/*.test.js` | **280 pass / 0 fail** |
| `tests/test_wp07_atomic_state_outcome.py` | **9 passed** |

### 5.2 Isolated re-verification (fresh snapshot, fresh venv)

A fresh copy of the working tree (excluding `.git`/`.venv`/`__pycache__`; 359 files) was created
in a new temp directory with a **new** venv, then re-run:

| Command | Result |
|---|---|
| `python -m pytest -q` | **3294 passed, 0 failed** |

This reproduces the real-tree result in a clean environment (no stale caches).

### 5.3 Independent mutation reproduction

Both helpers were reverted to the **old** non-atomic form (separate commits) **inside the isolated
copy** and the new tests re-run: **5 of 9 failed** exactly as intended
(`test_helper_rolls_back_state_when_outcome_write_fails`,
`test_expired_branch_is_atomic_on_outcome_failure`,
`test_cancel_route_is_atomic_on_outcome_failure`,
`test_set_helper_rolls_back_state_when_outcome_write_fails`,
`test_reply_prompt_is_atomic_on_outcome_failure`). Restoring the fix returns 9/9 green. This proves
the tests are non-vacuous and load-bearing.

### 5.4 Adversarial edge checks (isolated)

- `clear` on a user with **no** prior `user_state` row still records the outcome.
- An **ineligible** outcome goes to `update_failures` only (dedup source not poisoned).
- `set` helper **preserves** the `route` title.
- `update_id=None` → state change only (no outcome row, no dedup entry).

All four passed.

---

## 6. Independent review — honesty statement

**`INDEPENDENCE_NOT_ESTABLISHED`.** This environment cannot supply a genuinely separate
reviewer session/agent: no second agent-server is listening, the only profiles are the same
provider connections used by this session, and Cloud delegation requires money/credentials that
were not authorized. A fresh container + a different prompt is explicitly **not** sufficient for
"independent reviewer session" independence.

The strongest achievable review **was** performed and is reported as such: (a) a truly isolated
snapshot with a fresh venv reproducing the full suite; (b) an independent mutation reproduction
(different mechanism: in-place revert of both helpers) yielding the intended 5 failures; (c)
adversarial edge checks on the new helpers. This is **same-agent, isolated-environment** review,
not third-party review.

---

## 7. Not verified / not implemented / still blocked (honest list)

- **`WP-07` `DEF-011` — quota reservation ledger part: NOT IMPLEMENTED** (and must stay that way). Only the **filesystem offload** half of Option 1 was executed (§11). The in-process quota reservation ledger remains `D-12` (`OWNER_DECISION_REQUIRED`); aggregate quotas are still **disabled by default** (`max_items_per_batch` / `max_total_bytes` / `max_bytes_per_batch` all `None`), and **no** schema change or new table was introduced (still 17 `CREATE TABLE IF NOT EXISTS` in `bot/db.py`, 0 schema lines in its diff). The single-file cap (`MAX_ATTACHMENT_BYTES = 3 MiB`) is unaffected.
- **`WP-07` concurrency (`DEF-006`/`OD-04`):** NOT IMPLEMENTED — prohibited without owner proof/approval. Sequential polling preserved.
- **`NEW-DEF-03` remaining ordering sites** (`start`/`show_menu`/`list_conversations`/`list_watches` navigation clears that end in `mark_explicitly_ignored`, and `_send_prompt`/`_start_new_chat` durable-intent paths): **NOT CHANGED.** The navigation clears are a *different* concern (the clear is followed by a Telegram edit and then an outcome; converting them needs care so a legitimately unauthenticated/expired navigation still records its outcome) and the durable-intent paths already commit atomically with the outcome inside `add_or_group_outbox`/`add_creation_job`. Reported, not hidden.
- **Owner-gated packages** (`WP-01`, `WP-04` Part 2, `WP-06` Part 2, `WP-10`): NOT STARTED (unchanged from the prior execution report).
- **`WP-09` Python 3.11 matrix & CI:** UNVERIFIED locally (only 3.13 available; CI triggers on push/PR and no push was made).

---

## 8. Assumptions and decisions

1. The real Git tree at `/workspace/project/OpenHandBot` is the execution workspace (verified; `/app/applet` not used).
2. Installing the repo's **documented** `requirements-dev.txt` into a git-ignored project-local `.venv` is within `AGENTS.md` §1 ("Install: `pip install -r requirements-dev.txt`"); it is not a dependency/version change.
3. Scope was limited to the parts of `WP-07` that are **not** owner-gated; owner-gated parts were left untouched per `AGENTS.md` §14.
4. No commit/branch/PR was created (not requested; only `agent/*` branches may be pushed).

---

## 9. Branch and commits

- Branch: `openhands-workspace-40xxn2SbOi0tRICb3y8TE` (no `agent/*` branch created — no push requested).
- HEAD: `52e7789` (unchanged). All changes remain in the working tree (uncommitted).

## 10. Suggested next step

Obtain `OD-01`..`OD-05`, then execute the blocked work packages in baseline §G order; specifically,
the remaining `NEW-DEF-03` navigation-clear sites can be converted to the new atomic helper once a
discriminating test proves the navigation-expiry outcome is preserved.

---

## 11. `WP-07` `DEF-011` — filesystem offload (Option 1, part 1) — executed in a later batch

This section records work done **after** §1–§10 in the same working tree. It is the only part of
`DEF-011` that is **not** owner-gated; the quota-ledger half stays `D-12` and was **not** touched.

### 11.1 Design constraint discovered before editing

The approved implementation plan assumed ~4 call sites. Reality: **50 `store()` + 69 `sweep()` +
39 `maybe_sweep()`** synchronous call sites across ~10 existing test files (109 sync `def test_`,
0 async). Making those methods `async` would force rewriting unrelated tests — forbidden by the
task and by `AGENTS.md` §6. Documented in
`docs/reviews/OHB2-WP07-DEF011-PHASE1-DISCREPANCY-REPORT.md`.

**Adopted (compliant) approach:** additive async twins (`store_async`, `sweep_async`,
`maybe_sweep_async`) that leave the synchronous public API **byte-identical in behaviour**. Only
production async entry points call the async variants.

### 11.2 Changes

| File | Change |
|---|---|
| `bot/attachments.py` | `store()` split into `_store_prepare` (DB) / `_store_write` (pure FS) / `_store_finalize` (DB); `store()` is a thin sync wrapper; new `store_async()` runs `_store_write` via `anyio.to_thread.run_sync`; `sweep()` split into `_sweep_db_phase` / `_sweep_fs_tail`; new `sweep_async()`; `OpportunisticSweeper.maybe_sweep()` gate/throttle extracted to `_begin_attempt` / `_finish_attempt`; new `maybe_sweep_async()`. |
| `bot/handlers.py` | `_download_attachment_chunks`: the local `_read_local_capped` branch now runs in a worker thread. |
| `bot/watcher.py` | `tick()` → `await maybe_sweep_async()` (1 line). |
| `bot/app.py` | boot sweep → `await reaper.sweep_async(...)` (1 line). |
| `tests/test_def011_fs_offload.py` | **New**, 21 discriminating tests (T-1…T-14). |

### 11.3 Ownership boundary preserved (the load-bearing invariant)

`sqlite3.connect(path, check_same_thread=False)` with **one shared `_conn`** and **no threading
lock** means SQLite must never be touched from a worker thread. Enforced structurally:

- `_store_prepare` / `_store_finalize` are **not** passed to `to_thread` — they run on the loop.
- The worker receives only `path`, `chunks`, `cap`, `item_id`, `token` — **no `Database`/`_conn`**.
- `_sweep_fs_tail` contains **zero** DB calls (only `iterdir`/`lstat`).
- Verified by `test_T5` (all DB calls observed on the loop thread), `test_T6`/`test_T6b`
  (worker receives no DB reference; signature asserted).

### 11.4 Regression found and fixed during this work

Offloading the write introduced an `await` point the sync path never had, so 12 concurrent
`accept()` tasks began interleaving quota-check → write → mark. `test_concurrent_admission_against_real_sqlite`
failed (**12 stored vs. cap 3**). The old blocking call had accidentally serialized that section.

**Fix:** a per-store `anyio.Lock` (`_accept_lock`) held across the whole critical section, restoring
the **pre-existing serialized model** — not adding concurrency, not adding a quota ledger.
`anyio.Lock` was chosen over `asyncio.Lock` because the approved architectural guard
`test_cleanup_adds_no_worker_or_scheduler` asserts the literal string `"asyncio"` is absent from
`bot/attachments.py`; that guard was **not** weakened. Proven by `test_T14`.

### 11.5 Cancellation semantics (documented honestly)

`asyncio.Task.cancel()` on a `to_thread` call returns immediately; the worker thread still finishes
and may write the file **after** the coroutine is gone. Therefore a cancelled store can leave a
`pending` row plus its bytes. This is **not** a new defect: it is exactly the pre-existing
"crash between write and mark" state, and the approved recovery path handles it —
`test_T7` proves the sweep reaps it (`pending → reaped`, file deleted, `cleaned >= 1`) and that no
`stored` claim is ever made. No silent unlink was added at cancel time (an attempt was reverted:
it ran *before* the thread finished writing and was therefore ineffective **and** it contradicted
the approved `_scan_root_untracked` "report, never blind-delete" contract).

### 11.6 Verification (real commands, real output)

| Command | Before | After |
|---|---|---|
| `python -m pytest -q` | 3385 passed, 0 failed | **3406 passed, 0 failed** (+21) |
| `python -m pyflakes bot/ automation/ tools/ main.py tests/` | 0 | **0** (exit 0) |
| `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | High 0 | **High 0** |
| `python -m pip_audit -r requirements-dev.txt` | clean | **No known vulnerabilities found** |
| `node --test tests/frontend/*.test.js` | 280 pass | **280 pass / 0 fail** |

### 11.7 Mutation proof (tests are non-vacuous)

Each fix was reverted in place and the new tests re-run; all were caught:

| Mutation | Caught by |
|---|---|
| M1 — `store_async` calls `_store_write` inline (no offload) | `test_T2`, `test_T8`, `test_T7` |
| M2 — `sweep_async` calls `_sweep_fs_tail` inline | `test_T4` |
| M3 — `_accept_lock` replaced with a no-op context manager | `test_T14` |
| M4 — `_read_local_capped` read inline on the loop | `test_T8b` |

Restoring each fix returns the suite green.

### 11.8 Scope compliance

No Mini App file, no ADR, no schema/table change (17 tables), no quota ledger, no new dependency
(`anyio==4.16.0` and `starlette==1.3.1` were already pinned), no new worker/parallel polling, no
commit/push/PR/merge/deploy. Pre-existing user modifications in `bot/handlers.py`, `bot/watcher.py`,
`bot/db.py`, `.agent/PROGRESS.md` and the two SW-06 test files were **not** absorbed or reverted.
