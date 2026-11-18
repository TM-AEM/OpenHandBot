# OHB2 F-01 / F-02 / F-03 — Discriminating Regression Tests (and Independent Review)

**Task ID (appended USER_CONTEXT):** `OHB2-F01-F02-F03-DISCRIMINATING-REGRESSION-TESTS-AND-INDEPENDENT-REVIEW`
**Header Task ID (already complete):** `OHB2-OWNER-DECISIONS-BRIEFING-REVIEW-FIXES`
**Mode:** Test-only (implementation of tests) + independent verification. **No application code changed.**
**Owner Decision Status:** `PENDING_OWNER_DECISION` — `OD-01`–`OD-05` untouched (this task is unrelated to them).
**Status:** `DONE`

---

## 1. Executive summary

Three test-evidence gaps (`F-01`, `F-02`, `F-03`) identified by the completed cumulative independent review
(`docs/reviews/OHB2-POST-REMEDIATION-CUMULATIVE-INDEPENDENT-REVIEW.md` §6) were closed with **new, discriminating
regression tests**:

- **`F-01` / `DEF-008`** — `deliver_outbox(outbox_id)` must claim the **requested** outbox id, not the oldest
  `pending` row.
- **`F-02` / `DEF-007`** — the `continue` (`bot/watcher.py`) and `return` (`bot/notifier.py`) after a failed
  `clear_retry_not_before` must actually skip the conversation.
- **`F-03` / `DEF-009`** — the user-visible status label must be normalized end-to-end through the real handler
  path for absent / uppercase / sandbox-error statuses.

All nine new tests are **mutation-proven non-vacuous**: reverting each corresponding fix (or removing the
`STATE_LABELS["unknown"]` key) turns the new tests red, and the fixes' own code paths are exercised through real
call paths (`deliver_outbox`, `Watcher.tick`, `Notifier._process`, `handlers.show_status`).

- **4 new test files, 9 new tests, 342 lines. Zero existing files modified.**
- Full suite: **`3272` (pre-task baseline) → `3281` passed** (`+9`, no regressions).
- Gates: `node --test` `280/0`; `pyflakes` clean (`0`); `bandit -lll` `High 0`; `pip-audit` clean.
- **Independent review verdict: `PASS`** — every new test is correct, deterministic, and discriminating.

> **Task-identity note (honest record).** The structured header names `OHB2-OWNER-DECISIONS-BRIEFING-REVIEW-FIXES`
> (a docs-only briefing-correction task). That task is **already complete and committed** at `HEAD 33530ca`
> (see §7). The appended `USER_CONTEXT` block describes a *different* task and is self-labelled "NEW AUTHORITATIVE
> TASK". Following the header-vs-appended precedent already recorded in this repository (§11 of
> `OHB2-OWNER-DECISIONS-BRIEFING-REVIEW-FIXES-REPORT.md`), the already-done header was not re-done; the appended
> test task was executed. This is the third distinct payload observed under the same header (prior: Plan-01;
> `WP-01`…`WP-10`). No out-of-scope work was performed.

---

## 2. Baseline & integrity record (before any change)

| Artifact | Value | Note |
|---|---|---|
| Branch / HEAD | `main` @ `33530ca` | `== origin/main`; unchanged by this task |
| Modified tracked files (pre-existing, not mine) | `23` | uncommitted remediation work from other tasks |
| Untracked reports (pre-existing) | several | preserved |
| `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md` | working tree `dccc28fd…`; **HEAD blob `e7b98175d66bb118e437a75380622e09392998bcc9f754d3f48f26f4f5709a6f`** | working tree carries pre-existing uncommitted edits from a separate task; committed blob matches the prompt |
| `docs/audits/OHB2-OWNER-DECISIONS-BRIEFING.md` | on-disk `b6c02bae…`; **`git show 57d82fd:…` = `8974a3b991f2ed32a5547b8db85f3d6e40c0160ce683cfcb10d1ca6f35599c45`** | prompt's "current" hash = the **pre-correction** parent; corrections already committed |
| `docs/reviews/OHB2-OWNER-DECISIONS-BRIEFING-INDEPENDENT-REVIEW.md` | `be7c0e1dc45b27dd2189e0aa1c4af34d42913a1c5174b8d2b8b05e49afc0137f` | **EXACT MATCH** |
| Pre-task file inventory + hashes | 350 files → `/workspace/ohb2-f0102-scratch/pretask-{filelist,hashes}.txt` | used to prove scope at the end |

No file was overwritten or restored. The two prompt hashes that differ are explained by the header task already
being applied (see §7); the independent-review hash matches exactly.

---

## 3. Changes (file-by-file)

Only **four new files** were added; **no existing file was modified**.

| File | Tests | Closes | What it pins |
|---|---|---|---|
| `tests/test_f01_deliver_outbox_constrained_claim.py` | 2 | `F-01` / `DEF-008` | `deliver_outbox(client, db, bot, outbox_id)` claims **only** the target id (`claim_outbox_by_id`), leaving older `pending` rows untouched. Two cases: target vs. an older sibling; target in the middle of three. |
| `tests/test_f02_watcher_continue.py` | 2 | `F-02` / `DEF-007` | `Watcher.tick` **`continue`s** the conversation when `clear_retry_not_before` raises (no notification, deadline retained, other conversations unaffected). |
| `tests/test_f02_notifier_return.py` | 2 | `F-02` / `DEF-007` | `Notifier._process` **`return`s** when `clear_retry_not_before` raises (no send, no "computed" state, deadline retained, other conversations unaffected). |
| `tests/test_f03_status_label_end_to_end.py` | 3 | `F-03` / `DEF-009` | Real `bot.handlers.show_status` path emits the normalized Arabic label for: absent `execution_status` → `غير معروف`; uppercase → `منتهي`; `sandbox_status=ERROR` → `خطأ بيئة`. |

**Scope attribution note.** `DEF-009` belongs to work package **`WP-06` (Part 1)** — per
`OHB2-CORRECTED-REMEDIATION-BASELINE.md` `§WP-06` *Included Defect IDs: `DEF-009`, `DEF-010`* and the `§G`
mapping diagram — **not** `WP-05` (which is `DEF-007`, `DEF-008`, `DEF-012`, `NEW-DEF-02`, `NEW-DEF-05`).
`F-01`/`F-02` are `WP-05` coverage gaps; `F-03` is a `WP-06` coverage gap.

---

## 4. Verification (commands and real results)

Dependencies are installed **only inside containers** in this environment; the host shell has no `pytest`/`telegram`.
All runs used the approved image `ohb2-review-base:latest`.

| Check | Command (in container) | Result |
|---|---|---|
| New tests only | `python3 -m pytest -q tests/test_f01_… tests/test_f02_watcher_… tests/test_f02_notifier_… tests/test_f03_…` | **9 passed** |
| Related suites | `+ tests/test_wp05_worker_correctness.py tests/test_outbox*.py tests/test_watcher.py tests/test_notifier.py` | **196 passed** |
| **Full suite (pre → post)** | `python3 -m pytest -q tests/` | **3272 → 3281 passed** (0 failed) |
| Frontend | `node --test tests/frontend/*.test.js` | **280 pass / 0 fail** |
| Lint | `python3 -m pyflakes bot/ automation/ tools/ main.py tests/` | **clean (exit 0)** |
| SAST | `python3 -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | **High 0** |
| SCA | `pip-audit -r requirements-dev.txt` | **No known vulnerabilities** |

### 4.1 Mutation verification (proof the tests are discriminating, not vacuous)

Each fix was reverted in an **isolated disposable copy** (`ohb2-f0102-mut`, `--network none`); the tests went red
**for the intended reason**, then the copy was restored and re-confirmed green.

| # | Mutation applied | Expected failure | Observed |
|---|---|---|---|
| M1 | `deliver_outbox`: `claim_outbox_by_id(outbox_id,…)` → un-scoped `claim_outbox(…)` | target not sent; older record sent instead | **2 failed** — `assert [('c-a','A')] == [('c-b','B')]` |
| M2 | `bot/watcher.py`: delete the `continue` after the clear-failure warning | target wrongly notified | **2 failed** — `assert 2 == 1` (`الهدف` message appears) |
| M3 | `bot/notifier.py`: delete the `return` after the clear-failure warning | target wrongly notified + recorded | **2 failed** — `assert 2 == 1` |
| M4 | `bot/handlers.py` `show_status`: `state_label(get_status(conv))` → `state_label(conv.get("execution_status"))` | raw/uppercase/sandbox labels leak | **2 failed, 1 passed** |
| M4b | `bot/messages.py`: remove `STATE_LABELS["unknown"]` | `unknown` leaks in the absent case | **1 failed, 2 passed** |

---

## 5. Independent review (separate, read-only pass)

The review was performed against a **frozen tarball snapshot** (`sha256 17f973b0…`) extracted into a **fresh,
network-isolated container** (`ohb2-f0102-review`) — i.e. **not** the author's working tree, and using a
**different mutation mechanism** (`sed` / line-deletion scripts) than the author's `mutate.py`.

- **Independent full suite:** `3281 passed`.
- **Independent mutations M1–M4:** reproduced the exact failures above.
- **Restoration check:** all mutated source files restored to their original digests
  (`bot/handlers.py 96325cf2…`, `bot/messages.py f24ebdf9…`, `bot/notifier.py 9979a109…`, `bot/watcher.py 43a6d944…`,
  `bot/outbox.py 48f9f713…`); the four new test files pass.

### 5.1 Review findings

| Test file | Verdict | Notes |
|---|---|---|
| `test_f01_…` | ✅ `PASS` | Uses real `deliver_outbox`; asserts the *target* vs a *decoy* `pending` row. Non-vacuous (M1). |
| `test_f02_watcher_continue.py` | ✅ `PASS` | Exercises the real `Watcher.tick`; the decoy conversation proves the skip is per-conversation, not a global abort. Non-vacuous (M2). |
| `test_f02_notifier_return.py` | ✅ `PASS` | Exercises the real `Notifier._process`; asserts no inbox row + state not marked "computed". Non-vacuous (M3). |
| `test_f03_status_label_end_to_end.py` | ✅ `PASS` | Drives the real `handlers.show_status` + `FileService` authorization; asserts the user-visible text. Non-vacuous (M4/M4b). |

### 5.2 Independence statement

This independent pass was executed **in a separate container from a frozen snapshot, with independently written
mutations**, by the same agent session. It is a genuine re-derivation (fresh filesystem, fresh mutation code),
but it is **not** a human/third-party review. Recorded honestly as `INDEPENDENT_REVIEW_BY_SAME_AGENT`.

### 5.3 Overall verdict

`PASS` — the three coverage gaps `F-01`, `F-02`, `F-03` are closed with correct, deterministic,
mutation-proven discriminating tests. No new functional risk was introduced (test-only change).

---

## 6. Not verified / not implemented / still broken

- **Human/third-party review:** not performed (not available). The "independent" pass is by the same agent.
- **Live/CI run:** not performed. CI (`.github/workflows/ci.yml`) triggers on `push`/`pull_request` only, and this
  task is explicitly **not** authorized to push, branch, or open a PR — so no CI run covers these new tests yet.
  Verification here is local-container only.
- **Not implemented (out of scope, correctly):** no application code, config, ADR, operational doc, Mini App, or
  deployment file was changed. No `WP-01`…`WP-10` work package was implemented.
- **`F-03` scope nuance:** `DEF-009` is a `WP-06` item. Adding its test does **not** implement `WP-06` Part 2
  (`callback_refs`), which remains a design prerequisite.
- **Pre-existing environment quirk:** the host shell has no Python deps; all test execution goes through
  containers. (Not a defect of this task.)

---

## 7. Header-task reconciliation (why the header was not re-done)

- `HEAD 33530ca` message: *"docs: correct owner decisions briefing per independent review (REV-OD-01..07)"*; it
  changes exactly `docs/audits/OHB2-OWNER-DECISIONS-BRIEFING.md` (`27` lines) and adds
  `docs/reviews/OHB2-OWNER-DECISIONS-BRIEFING-REVIEW-FIXES-REPORT.md`.
- The briefing is **clean vs `HEAD`** and contains all seven corrections (`DEF-008`→`DEF-012` at `§4.B.1`; the
  two `OD-02` same-batch constraints; the `NEW-DEF-07` traceability row; `bot/handlers.py:1603-1606`; the Mini App
  exclusion paths; the ADR `§28.4` / `§18.6` citations; the `WP-06` `Partially blocked` label).
- Therefore the header task was already delivered. To avoid clobbering another session's work, the existing
  report `docs/reviews/OHB2-OWNER-DECISIONS-BRIEFING-REVIEW-FIXES-REPORT.md` (which already carries a prior
  session's uncommitted `§10`/`§11` edits) was **left untouched**; this report documents the *appended* task only.

---

## 8. Assumptions and decisions (chosen without asking)

1. **Header-vs-appended conflict → do the appended (not-yet-done) task.** Justified by the repository's own
   precedent (the same header previously carried a `WP-01`…`WP-10` payload that the header explicitly forbade).
   The header task being verifiably complete made this the only actionable, non-forbidden work.
2. **`F-03` = `WP-06`, not `WP-05`.** Confirmed from the baseline's own `Included Defect IDs` and `§G` mapping.
3. **Test placement:** one new file per finding group (`F-01`; `F-02` watcher; `F-02` notifier; `F-03`), matching
   the repo's one-concern-per-test-file style, rather than editing existing test files (which would touch
   pre-existing uncommitted work).
4. **F-03 drives the real handler** (`handlers.show_status`) instead of only unit-level `state_label`, so the
   gap ("not end-to-end pinned") is genuinely closed.
5. **No push / no PR / no branch** — the task forbids it and CI cannot be triggered otherwise.

---

## 9. Branch and commits

- **Branch:** `main` (unchanged). **HEAD:** `33530cad02f37755da47e7eedac57764a354a75b` (unchanged).
- **Commits made by this task:** **none** (test-only; commit/push/PR explicitly not authorized).
- **Working tree delta from this task:** 4 new untracked files (the test files in §3). All 23 pre-existing
  modified tracked files and all pre-existing untracked files are byte-identical to the pre-task state (verified
  by re-hashing the 350-file pre-task inventory).

---

## 10. Suggested next step

When the owning work packages are authorized, **stage and commit the four new test files on a dedicated
`agent/*` branch and let CI run them** (CI is the only permitted full-environment gate here), so the `F-01`/`F-02`
(`WP-05`) and `F-03` (`WP-06`) regression protection becomes part of the committed suite.

---

*This report was created by an AI agent (OpenHands) on behalf of the repository owner.*
