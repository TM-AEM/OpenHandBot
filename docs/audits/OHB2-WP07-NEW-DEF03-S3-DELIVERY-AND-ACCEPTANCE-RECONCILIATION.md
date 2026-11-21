# OHB2 — WP-07 — NEW-DEF-03 — S3 Delivery and Acceptance Reconciliation

**Task:** `OHB2-WP07-BATCH04-REV2-S3-EXECUTION`
**Date:** 2026-11-19
**Route:** S3 (land NEW-DEF-03 first, then DEF-011-B on top)
**Status:** **`S3_NEW_DEF03_READY`** — scope proven separable and CI-green; **formal acceptance of the delivered subset is already on record** (see §3)

> This document does **not** claim WP-07 complete, NEW-DEF-03 complete, or DEF-011 closed.
> No code was modified in this task. All measurements were performed on throwaway reconstructions.

---

## 1. Why this reconciliation exists

The previous report (`…REV2-OWNER-AUTHORIZATION-AND-EXECUTION-READINESS-REPORT.md` §5) proved that a
DEF-011-B-only branch **cannot** be CI-green because the DEF-011-B files depend on NEW-DEF-03 db
methods. S3 resolves this by landing NEW-DEF-03 first.

**Open question this document answers:** *what exactly must the NEW-DEF-03 delivery contain, and is
it separable from the unaccepted NAV-01..06 work that shares the same files?*

**Answer: yes, separable.** Proven by measurement (§4).

---

## 2. Scope decomposition (authoritative sources)

### 2.1 The three distinct scopes sharing `bot/handlers.py` and `bot/watcher.py`

| Scope | Definition source | Functions / items | Acceptance |
|---|---|---|---|
| **Scope A — NEW-DEF-03 non-concurrency** | `OHB2-CORRECTED-REMEDIATION-BASELINE.md:401`; acceptance record `.agent/PROGRESS.md:4272` | A-1..A-5 (§3.1) | **`NEW-DEF-03_NON_CONCURRENCY_OWNER_ACCEPTED`** |
| **Scope A′ — NAV-01..06** | `OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md:79` | `start`, `show_menu`, `list_conversations`, `list_watches`, `start_new_chat`, `open_conversation` | **`REQUIRES_SEPARATE_OWNER_DECISION`** — **NOT accepted** |
| **Scope B — DEF-006 / concurrency** | same proposal §4 | — | **`BLOCKED_PENDING_OD04`** |
| **DEF-011-B / F-01** | separate WP-07 finding | `attachments.py`, 1 `handlers.py` hunk, 1 `watcher.py` hunk, `app.py` | Under REV2 review — **NOT part of this delivery** |

### 2.2 Baseline statement on approval

`OHB2-CORRECTED-REMEDIATION-BASELINE.md` §NEW-DEF-03:

> **Owner Approval Requirements:** `NONE`.

and the acceptance record in `.agent/PROGRESS.md:4277`:

> **الحالة: `NEW-DEF-03_NON_CONCURRENCY_OWNER_ACCEPTED`** — ده **مش** `WP-07_COMPLETE` و**مش** `NEW-DEF-03_COMPLETE`.

⇒ Scope A is **owner-accepted**, but the acceptance is **bounded**: it covers exactly A-1..A-5 and
does **not** extend to NAV-01..06, DEF-006/concurrency, or DEF-011.

### 2.3 Measured hunk attribution in `bot/handlers.py`

Diff vs `origin/main` = **44 hunks**, attributed by enclosing top-level function:

| Bucket | Hunks | Functions |
|---|---|---|
| **DEF-011-B** | **3** | module imports (`anyio.to_thread`, `functools`), `_download_attachment_chunks` |
| **NEW-DEF-03 (Scope A)** | **24** | `watch_conversation`(4), `unwatch_conversation`(3), `_remove_watched_with_retry`(3), `handle_text`(2), `cancel_route`(2), `cancel_route_button`(2), `reply_prompt`(2), `repo_search_prompt`(2), `pick_repo`(2), `new_chat_no_repo`(2), `_is_deleted_with_retry`(1) |
| **NAV-01..06 (Scope A′)** | **17** | `list_conversations`(6), `list_watches`(3), `show_menu`(2), `start`(2), `start_new_chat`(2), `open_conversation`(2) |

`bot/watcher.py` = **3 hunks**: 1 DEF-011-B (`maybe_sweep_async`), 2 NEW-DEF-03 (`unwatch`).
`bot/db.py` = NEW-DEF-03 / DEF-013 only (**0** DEF-011 and **0** NAV markers).
`bot/app.py` = 1 DEF-011-B hunk only.

**⇒ All three scopes are hunk-separable even though they share files.**

---

## 3. Reconciliation table

| Scope | Implementation state | Test evidence | Owner acceptance | Git state | Remaining action |
|---|---|---|---|---|---|
| **A-1** `watch_conversation` atomicity | **DONE** — `add_watched_and_record_outcome`, `_add_watched_nocommit`, `_set_last_state_nocommit` present | `test_wp07_watch_unwatch_atomicity.py` passes | **ACCEPTED** (`PROGRESS.md:4272`) | **uncommitted** (working tree) | land on branch, then merge |
| **A-2** `unwatch_conversation` atomicity (both branches) | **DONE** — `remove_watched`, `_remove_watched_nocommit`, `remove_watched_completing`, `_remove_watched_completing_nocommit`, `watcher.unwatch` | same file, both branches | **ACCEPTED** | **uncommitted** | same |
| **A-3** Awaiting-state atomicity | **DONE** — `clear_awaiting_and_record_outcome`, `set_awaiting_and_record_outcome`, `_set_awaiting_nocommit` | `test_wp07_atomic_state_outcome.py` | **ACCEPTED** | **uncommitted** | same |
| **A-4** Backward compatibility | **DONE** — keyword-only optional args default `None`; single-arg `remover(cid)` preserved | `test_handlers.py` +2/−2, `test_sw06_…` +11/−11 (`**_kw`) | **ACCEPTED** | **uncommitted** | same |
| **A-5** F-1 Option C behaviour preserved | **DONE** — 6 F-1 paths unchanged | `test_wp07_f1_notification_failure.py` (14) | **ACCEPTED** | **uncommitted** | same |
| **NEW-DEF-03 whitespace/renew_awaiting** | **DONE** — `renew_awaiting` after `text.strip()` check | covered in `handle_text` tests | **ACCEPTED** (part of Scope A) | **uncommitted** | same |
| **NAV-01..06** | **DONE but unaccepted** — 17 hunks in `handlers.py` | `test_wp07_nav0*.py` (51 tests, **untracked**) | **`REQUIRES_SEPARATE_OWNER_DECISION`** | **uncommitted, untracked tests** | **owner decision A′-1/A′-2/A′-3/A′-4** |
| **DEF-006 / concurrency** | **comment block only** | — | **`BLOCKED_PENDING_OD04`** | committed comment | OD-04 decision — **out of scope** |
| **DEF-011-B / F-01** | **DONE** | 34 tests | under REV2 review | **uncommitted** | separate delivery after S3 |
| **WP-05 / other worktree changes** | see §5 | — | — | **uncommitted** | **excluded** |

---

## 4. Proof that NAV-01..06 is separable (measured)

Two throwaway reconstructions from `git archive origin/main`, measured in this task.

### 4.1 NAV excluded — full CI gate

Delivery = `bot/db.py` + NEW-DEF-03-only `handlers.py` hunks + NEW-DEF-03-only `watcher.py` hunk
+ `test_handlers.py` + `test_sw06_…` (`**_kw` compatibility).

| Gate | Result |
|---|---|
| Full suite | **3285 passed**, 0 failed |
| Full suite + 3 WP-07 regression files | **3334 passed**, 0 failed |
| NEW-DEF-03 focused regression (3 files) | **47 passed** |
| pyflakes | **CLEAN** |
| bandit (`-lll`, HIGH only) | **No issues identified** |
| `NAV-0` markers in `handlers.py` | **0** |
| `to_thread` in `handlers.py` (DEF-011 leak) | **0** |
| `attachments.py` vs `origin/main` | **identical** |

### 4.2 NAV tests genuinely depend on NAV code (non-vacuity proof)

Running the NAV test files against the NAV-excluded build: **16 failed / 35 passed**.

⇒ NAV tests are **not** vacuous, and the 17 NAV hunks are **genuinely required** by them.
Excluding NAV is a real scope reduction, not test deletion.

### 4.3 The counter-experiment that mattered

Including the NAV hunks *without* the NAV tests still passed the tracked suite — but that is
**not** a licence to ship unaccepted work. The accepted subset is sufficient on its own (§4.1),
so **NAV must be excluded** from the S3 delivery.

---

## 5. Unrelated worktree content — explicitly excluded

| Item | Status |
|---|---|
| `bot/attachments.py` (+386/−103) | DEF-011-B + F-01 — **excluded** from NEW-DEF-03 |
| `bot/app.py` (+1/−1) | DEF-011-B — **excluded** |
| 1 `handlers.py` hunk (`_download_attachment_chunks` + imports) | DEF-011-B — **excluded** |
| 1 `watcher.py` hunk (`maybe_sweep_async`) | DEF-011-B — **excluded** |
| 17 NAV hunks | Scope A′ — **excluded** (unaccepted) |
| 7 untracked WP-07 test files | not part of Scope A delivery |
| `.agent/PROGRESS.md` (+236) | work log — **never published** |
| WP-05 / WP-06 changes | **none present** in the 8 modified files |

---

## 6. Minimum exact NEW-DEF-03 delivery (Scope A only)

### 6.1 Required production files

| Path | Content | Δ vs `origin/main` |
|---|---|---|
| `bot/db.py` | `add_watched_and_record_outcome`, `set_awaiting_and_record_outcome`, `clear_awaiting_and_record_outcome`, `remove_watched`, `_add_watched_nocommit`, `_remove_watched_nocommit`, `_remove_watched_completing_nocommit`, `_set_awaiting_nocommit`, `_set_last_state_nocommit` | +269 / −66 |
| `bot/handlers.py` | **24 NEW-DEF-03 hunks only** (11 functions, §2.3) | subset of +144 / −41 |
| `bot/watcher.py` | **2 NEW-DEF-03 hunks only** (`unwatch` signature + `remove_watched*` calls) | subset of +16 / −4 |

### 6.2 Required tests

| Path | Why |
|---|---|
| `tests/test_handlers.py` | +2 / −2 — `**_kw` compatibility for the new signatures |
| `tests/test_sw06_unwatch_db_failure_propagation.py` | +11 / −11 — `**_kw` compatibility |

**Optional but recommended** (currently untracked — would need to be added if the owner wants the
acceptance evidence in-repo):

| Path | Tests |
|---|---|
| `tests/test_wp07_watch_unwatch_atomicity.py` | 47 total across the 3 files |
| `tests/test_wp07_atomic_state_outcome.py` | |
| `tests/test_wp07_f1_notification_failure.py` | |

### 6.3 Documentation

| Path | Change |
|---|---|
| `docs/audits/OHB2-WP07-NEW-DEF03-S3-DELIVERY-AND-ACCEPTANCE-RECONCILIATION.md` | this document |
| `.agent/PROGRESS.md` | **local only, never published** — append a delivery record |

### 6.4 Dependencies

- None outside the three files above.
- **Does not** depend on NAV, DEF-011-B, F-01, DEF-006, OD-04, or any schema change.
- No new table, column, worker, queue, or concurrency model.

### 6.5 Acceptance criteria

1. `python -m pytest -q` → **≥3285 passed, 0 failed**.
2. `python -m pyflakes bot/ automation/ tools/ main.py tests/` → **clean**.
3. `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` → **No issues identified**.
4. `NAV-0` markers in `bot/handlers.py` → **0**.
5. `to_thread` in `bot/handlers.py` → **0**.
6. `bot/attachments.py` and `bot/app.py` byte-identical to `origin/main`.
7. The 47 NEW-DEF-03 regression tests pass.

### 6.6 Regression commands

```
python -m pytest -q tests/test_wp07_watch_unwatch_atomicity.py \
                  tests/test_wp07_atomic_state_outcome.py \
                  tests/test_wp07_f1_notification_failure.py
python -m pytest -q
```

### 6.7 CI commands

```
python -m pyflakes bot/ automation/ tools/ main.py tests/
python -m pip_audit -r requirements-dev.txt
python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613
python -m pytest -q
node --test tests/frontend/*.test.js
```

### 6.8 Rollback-safe recovery (no destructive Git)

- **Before** landing: the delivery lives only in a branch. Recovery = delete the branch locally
  (`git branch -D <branch>`) — the working tree is untouched.
- **After** landing but before merge: `git revert <commit>` on the branch.
- **After** merge: `git revert <merge-commit>` — never `reset --hard`.
- The working tree at `52e7789` with 8 modified files remains the reference copy throughout.

---

## 7. Separation of work classes

| Class | Items |
|---|---|
| **Already committed** | DEF-006 comment block (on `main`), `33530ca` docs |
| **Existing uncommitted** | 8 modified tracked files; 49 untracked (tests + docs) |
| **New changes needed** | **none** — the accepted Scope A work is already implemented; only *selection* (hunk filtering) is needed |
| **Documentation-only** | this reconciliation + the baseline manifest |
| **Requires new owner decision** | **NAV-01..06 acceptance** (A′); OD-04 concurrency (out of scope); publication (A–D) |

---

## 8. Owner decision record required for NAV-01..06

**Not accepted. Not silently accepted. Not included in the S3 delivery.**

| Option | Meaning | Consequence for S3 |
|---|---|---|
| **A′-1 Accept** | Extend acceptance to NAV-01..06 on the A-1..A-5 basis | NAV may be included in a later delivery; **not needed for S3** |
| **A′-2 Accept with conditions** *(agent recommendation)* | Accept, but require a `PROGRESS.md` record + per-handler mutation proof | same |
| **A′-3 Defer** | Leave unaccepted, exclude from any baseline, keep in working tree | **current effective state — S3 proceeds without NAV** |
| **A′-4 Reject** | Revert NAV work | requires explicit owner authorization; agent must not do this unilaterally |

**S3 does not depend on this decision.** The delivery in §6 excludes NAV entirely, so the owner may
choose A′-3 (defer) and S3 still proceeds.

---

## 9. Explicit non-claims

- **NEW-DEF-03 is not "complete"** — Scope A is delivered and accepted; Scope A′ (NAV) is
  unaccepted; Scope B (concurrency) is OD-04-blocked.
- **WP-07 is not complete.**
- **DEF-011 is not closed** (DEF-011-A, DEF-011-C, F-02, F-03, WP-09 remain open).
- **No independent review** of this delivery occurred in this task.
- **No code was modified** and **no commit/push/PR** was created.
