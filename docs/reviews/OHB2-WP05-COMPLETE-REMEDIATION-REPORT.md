# OHB2-WP05 — Complete Remediation and Verification Report

**Task:** `OHB2-WP05-COMPLETE-REMEDIATION-AND-VERIFICATION`
**Date:** 2026-11-19
**Implementation status:** `IMPLEMENTATION_COMPLETE`
**Review status:** `REVIEW_PENDING_INDEPENDENCE`

---

## 1. Executive summary

WP-05 (`Worker Correctness, Cache Invalidation, & Cursor-Loop Protection`) covers five findings: `DEF-007`, `DEF-008`, `DEF-012`, `NEW-DEF-02`, `NEW-DEF-05`. The corrected baseline records **`Required Owner Approvals: NONE`** for this work package, so all five items were in scope and unblocked.

**All five findings are implemented, committed at HEAD, and verified by discriminating regression tests.** During this task no new production code was required — the implementation was already present at HEAD `52e7789` (commit `chore: sync local remediation work to main`). This task therefore delivered **verification, not new remediation**: it recovered the authoritative scope, confirmed each fix at source level, proved every regression test is non-vacuous through eight mutations, and ran the full gate.

The material contribution is evidence: all eight mutations were killed by the intended tests with file hashes restored, the full suite passes at **3383/0**, and the working tree contains **only WP-07 work** (pre-existing, preserved untouched) — confirming WP-05 introduced no scope drift.

No finding was blocked. No owner decision was required. No CRITICAL/HIGH/MEDIUM defect was found in WP-05 code.

**Caveat that must not be glossed over:** the "already implemented at HEAD" state was established by *this* session's inspection, not by an independent reviewer. Implementation completeness is evidenced; independent acceptance is not claimed.

---

## 2. Repository identity and Git state

| Item | Before | After |
|---|---|---|
| Repository root | `/workspace/project/OpenHandBot` | unchanged |
| Branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` | unchanged |
| HEAD | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` | unchanged |
| Upstream | none configured | unchanged |
| Staged | 0 | **0** |
| Modified (tracked) | 6 | **6** |
| Untracked | 9 | **9** |

Modified: `.agent/PROGRESS.md`, `bot/db.py`, `bot/handlers.py`, `bot/watcher.py`, `tests/test_handlers.py`, `tests/test_sw06_unwatch_db_failure_propagation.py`.
Untracked: 3 WP-07 review docs + 6 WP-07 test files.

**Provenance finding:** every one of these working-tree changes is **WP-07** work (`OHB2-WP-07 (NEW-DEF-03)` markers in `watcher.py`/`db.py`, NAV tests). They pre-date this task and were **preserved untouched**. WP-05 code is entirely **committed at HEAD**.

**No commit, push, PR, merge, deploy, release, Autopush, reset, clean, force operation, broad staging, or fetch/pull was performed.** No `git add` of any kind.

---

## 3. Authoritative WP-05 scope (recovered)

Source: `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md` §`WP-05` (lines 637–663), corroborated by §line 788, §line 859 (dependency graph), and `OHB2-OWNER-DECISIONS-BRIEFING.md` line 481.

| Field | Authoritative value |
|---|---|
| Objective | Fix control-flow skip bugs, creation-polling exception leaks, target-ID claiming in `deliver_outbox`, post-creation `list_cache` invalidation, OpenHands cursor-loop protection |
| Included IDs | `DEF-007`, `DEF-008`, `DEF-012`, `NEW-DEF-02`, `NEW-DEF-05` |
| Explicit exclusions | `OutboxWorker` at-most-once CAS/tombstone invariants; Mini App routes (`bot/web/*`) |
| Required owner approvals | **`NONE`** (OD-01…OD-05 do not block) |
| Verification | `pytest`, `pyflakes`, `bandit` (WP-09) |

Scope was taken from the baseline document, **not** from the task prompt.

---

## 4. Complete finding-to-fix mapping

| ID | Defect | Fix | Location | Status |
|---|---|---|---|---|
| `DEF-007` (a) | `Watcher.tick` logged "will skip" but continued into notification path when `clear_retry_not_before` failed → contradictory log, duplicate-notification risk while retry deadline still active | Added `continue` in `except Exception` | `bot/watcher.py:222` | **FIXED** |
| `DEF-007` (b) | Same class of bug in notifier: logged skip then still sent notification | Added `return` in `except Exception` | `bot/notifier.py:531` | **FIXED** |
| `DEF-008` | `deliver_outbox(outbox_id)` called unscoped `claim_outbox()`, which claims the **oldest** pending row — could claim/send a different row and leave the target `pending` | New `db.claim_outbox_by_id(outbox_id, now, mature_before)` — ID-scoped CAS (`WHERE id=? AND status='pending' … RETURNING *`) | `bot/db.py:3580`, `bot/outbox.py:233` | **FIXED** |
| `DEF-012` (block 1) | Resumed-poll branch caught only `ApiError`; unexpected exception or cancellation left job stranded in `claimed`/`starting` until restart | Added `except asyncio.CancelledError` (→`CREATION_UNKNOWN`, re-raise) and `except Exception` (→`CREATION_UNKNOWN` + `_UNKNOWN_CREATION_NOTICE`) | `bot/outbox.py:758–775` | **FIXED** |
| `DEF-012` (block 2) | POST branch caught `ApiError`/`CancelledError`/`ValueError` only; other exceptions stranded the job | Added `except Exception` → `CREATION_UNKNOWN` + notice | `bot/outbox.py:839–849` | **FIXED** |
| `NEW-DEF-02` | Newly created conversation stayed invisible in "my chats" until `LIST_TTL` expiry — `list_cache` not invalidated on creation completion | Optional `on_created` callback invoked **after** successful `complete_creation_done` commit; wired in `bot/app.py` as `lambda: application.bot_data.pop("list_cache", None)`; failure logged, never fails creation | `bot/outbox.py:875–884`, `bot/app.py:255–258` | **FIXED** |
| `NEW-DEF-05` | Repeated `next_page_id` caused repeated HTTP calls up to `max_pages` and a **false** `truncated=True` | `seen_pages: set[str]`; on repeat → `page_id=None; break` (halts in one step, no false truncation) | `bot/openhands_client.py:609–627` | **FIXED** |

All fixes are surgical single-method changes preserving CAS transitions, as the baseline's rollback guidance requires.

---

## 5. Findings already resolved before this task

All five WP-05 findings were already implemented and committed at HEAD `52e7789`. Verified by source inspection with `OHB2-WP-05` markers present at HEAD:

```
bot/watcher.py: 1 marker   bot/notifier.py: 1 marker
bot/outbox.py: 7 markers   bot/openhands_client.py: 1 marker   bot/db.py: 1 marker
```

Committed regression tests at HEAD:

| Test file | Covers |
|---|---|
| `tests/test_wp05_worker_correctness.py` (178 lines, 7 tests) | DEF-012 (both blocks), NEW-DEF-02, NEW-DEF-05 |
| `tests/test_f01_deliver_outbox_constrained_claim.py` (2 tests) | DEF-008 |
| `tests/test_f02_watcher_continue.py` (2 tests) | DEF-007a |
| `tests/test_f02_notifier_return.py` (2 tests) | DEF-007b |
| `tests/test_f03_status_label_end_to_end.py` | WP-06 (out of WP-05 scope) |

---

## 6. Findings implemented during this task

**None.** No new production code was required. Adding code would have duplicated already-correct, already-tested fixes — explicitly prohibited by §2 of the task (*"Do not duplicate fixes or reopen accepted work without concrete evidence"*).

The work performed was **independent re-verification**: source-level confirmation of each fix, mutation testing of each regression test, and the full gate.

---

## 7. Findings blocked by owner decisions or dependencies

**None.** The baseline records `Required Owner Approvals: NONE` for WP-05, and no OD-01…OD-05 dependency applies.

---

## 8. Files changed and reasons

**Production/test files changed by this task: none.**

| File | State | Reason |
|---|---|---|
| `bot/watcher.py`, `bot/db.py`, `bot/handlers.py`, `tests/test_handlers.py`, `tests/test_sw06_unwatch_db_failure_propagation.py`, `.agent/PROGRESS.md` | modified **before** this task | **WP-07** work; preserved untouched |
| 6 WP-07 test files + 3 WP-07 docs | untracked **before** this task | WP-07 work; preserved untouched |
| `docs/reviews/OHB2-WP05-COMPLETE-REMEDIATION-REPORT.md` | **created by this task** | Required deliverable (§12) |

Mutations were applied to a disposable copy in `/tmp/wp05m/` and to in-place files **only transiently**, each restored and hash-verified (§12).

---

## 9. Regression tests added or changed

**Added:** none. **Changed:** none.

Existing tests were assessed for discriminating power (§12) rather than duplicated. Each already fails against the defective behaviour and passes against the fix:

- `test_watcher_skips_conversation_when_clear_retry_deadline_fails` — asserts the target conversation is **not** notified (one message, not two).
- `test_deliver_outbox_claims_only_target_leaves_older_pending` — asserts the **target** is sent and the older eligible row stays `pending`.
- `test_deliver_outbox_claims_only_target_among_many_pending` — three pending rows; only the middle is sent, count stays 2.
- `test_resumed_wait_for_start_unexpected_error_marks_unknown` — parametrized `RuntimeError`/`KeyError`; asserts `CREATION_UNKNOWN` and `start_calls == 0`.
- `test_resumed_wait_for_start_cancelled_reraises_and_marks_unknown` — asserts re-raise **and** `CREATION_UNKNOWN`.
- `test_wait_for_start_unexpected_error_marks_unknown` — asserts no automatic re-POST.
- `test_finish_creation_invokes_on_created_callback` — asserts callback fires after `done`.
- `test_on_created_failure_does_not_break_creation` — asserts cache-invalidation failure does not fail creation.
- `test_collect_conversations_halts_on_repeated_cursor` — asserts `calls == 2` (halts at first repeat, not 20) and `truncated is False`.
- `test_collect_conversations_distinct_cursors_reach_max_and_truncate` — asserts `truncated is True` when cursors genuinely advance.

---

## 10. Exact test commands, exit codes, and results

**Environment:** Python 3.13.15 (`.venv`), Node v24.22.2, Linux container.

### Focused WP-05 baseline
```
$ .venv/bin/python -m pytest -q -p no:cacheprovider \
    tests/test_wp05_worker_correctness.py \
    tests/test_f01_deliver_outbox_constrained_claim.py \
    tests/test_f02_notifier_return.py tests/test_f02_watcher_continue.py \
    tests/test_f03_status_label_end_to_end.py
exit 0 — 18 passed in 1.22s
```

### Full Python suite
```
$ .venv/bin/python -m pytest -q -p no:cacheprovider
exit 0 — 3383 passed, 74 warnings in 179.10s (0:02:59)
```

`0 failed`, `0 errors`, `0 skipped`. No pre-existing failures.

### Related suites exercised (subset of the full run)
`tests/test_watcher.py`, `tests/test_notifier.py`, `tests/test_creation.py`, `tests/test_outbox_concurrency_28c.py`, `tests/test_openhands_client.py`, `tests/test_handlers.py`, `tests/test_manual_polling_outcome_and_ack.py`, `tests/test_doc_code_parity.py` — all pass.

### Schema parity
```
$ .venv/bin/python -m pytest -q tests/test_doc_code_parity.py -k "table"
exit 0 — 2 passed, 4 deselected
```
Unique tables: **17**, identical at HEAD and working tree (23 `CREATE TABLE` text occurrences include docstring/comment mentions).

---

## 11. Static analysis and dependency audit

```
$ .venv/bin/python -m pyflakes bot/ automation/ tools/ main.py tests/
exit 0 — no output

$ .venv/bin/python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613
exit 0 — Total issues (by severity): High: 0

$ .venv/bin/python -m pip_audit -r requirements-dev.txt
exit 0 — No known vulnerabilities found

$ node --test tests/frontend/*.test.js
exit 0 — tests 280 / pass 280 / fail 0
```

Frontend was run despite Mini App files being untouched, per §7.9, to detect accidental regressions: none found.

**Unavailable checks:** none. No dependency was installed or upgraded. Docker-specific checks are not part of WP-05's verification requirements (`pytest`, `pyflakes`, `bandit`).

---

## 12. Mutation / fault-injection evidence

Method: each mutation applied to the real file, targeted tests run, original restored from a byte-exact backup, restoration proven by SHA-256 comparison against the pre-mutation hash. Backups taken for `watcher.py`, `notifier.py`, `outbox.py`, `openhands_client.py`, `db.py`.

| # | Mutation | Target | Result | Restored |
|---|---|---|---|---|
| M1 | Remove `continue` after failed `clear_retry_not_before` (DEF-007a) | `bot/watcher.py` | **2 failed**, 138 passed | hash OK |
| M2 | Remove `return` after failed `clear_retry_not_before` (DEF-007b) | `bot/notifier.py` | **2 failed**, 138 passed | hash OK |
| M3 | Revert to unscoped `db.claim_outbox()` (DEF-008) | `bot/outbox.py` | **2 failed** | hash OK |
| M4a | Drop generic `except Exception` fallback, block 2 (DEF-012) | `bot/outbox.py` | **2 failed**, 21 passed | hash OK |
| M4b | Drop generic `except Exception` fallback, block 1 (DEF-012) | `bot/outbox.py` | **2 failed**, 21 passed | hash OK |
| M4c | Swallow `CancelledError` (`raise`→`return`), block 1 (DEF-012) | `bot/outbox.py` | **1 failed** | hash OK |
| M5 | Disable `on_created` invocation (NEW-DEF-02) | `bot/outbox.py` | **1 failed**, 22 passed | hash OK |
| M6 | Remove `seen_pages` repeat guard (NEW-DEF-05) | `bot/openhands_client.py` | **2 failed**, 61 passed | hash OK |

**8/8 mutations killed, each by the intended test.** Intended-failure confirmation for M4b/M4c:

```
M4b → FAILED test_resumed_wait_for_start_unexpected_error_marks_unknown[exc0]
      FAILED test_resumed_wait_for_start_unexpected_error_marks_unknown[exc1]
M4c → FAILED test_resumed_wait_for_start_cancelled_reraises_and_marks_unknown
```

Post-mutation restoration re-verified for all five files; `git status` count unchanged at 15 (no mutation artefacts left behind). No surviving mutation ⇒ no coverage gap found.

---

## 13. Review findings and severity

Self-review of the WP-05 diff, tests, and acceptance criteria.

| ID | Severity | Finding | Evidence / disposition |
|---|---|---|---|
| R-1 | **INFO** | WP-05 is fully committed at HEAD; the task's premise ("complete remediation") implies new code was needed, but the correct action was verification, not duplication. | §5, §6. Documented rather than papered over. |
| R-2 | **INFO** | Working tree contains WP-07 changes that overlap `bot/watcher.py` and `bot/db.py` — files also touched by WP-05 at HEAD. | Confirmed disjoint hunks: WP-05 hunks are in HEAD; the uncommitted diff is `unwatch()` signature/atomicity (WP-07). No conflict; WP-05 intent preserved. |
| R-3 | **LOW** | `NEW-DEF-02` `on_created` swallows exceptions (logs type only). | Deliberate and documented in code: cache invalidation is an optimization, not correctness. Creation completion must not fail on it. Matches baseline constraint 4. Accepted as designed. |
| R-4 | **LOW** | `DEF-008` `claim_outbox_by_id` commits immediately after the `UPDATE … RETURNING`. | Consistent with the existing `claim_outbox` pattern and the baseline's "surgical single-method fixes preserving CAS transitions". The `status='pending'` predicate makes double-claim impossible. |
| R-5 | **INFO** | `NEW-DEF-05` `truncated` stays `False` on a repeated cursor. | Correct: a repeated cursor means no real additional pages. Asserted by test. |

**No CRITICAL, HIGH, or MEDIUM findings.**

### Acceptance criteria check (baseline §`WP-05`)

| Criterion | Status | Evidence |
|---|---|---|
| Failed `clear_retry_not_before` genuinely skips cycle | **MET** | M1/M2 killed; tests assert absence of second notification |
| Neither `wait_for_start` branch leaves jobs in `claimed`/`starting` | **MET** | M4a/M4b/M4c killed; tests assert `CREATION_UNKNOWN` |
| `deliver_outbox(id)` claims only `id` | **MET** | M3 killed; tests assert older row stays `pending` |
| `list_cache` clears after creation completion | **MET** | M5 killed; test asserts callback fires |
| Repeated `next_page_id` halts in 1 duplicate step | **MET** | M6 killed; test asserts `calls == 2` |

---

## 14. Independence evidence (or lack thereof)

**No genuine independent review was established.**

A genuinely independent review requires **both** a separate reviewer session **and** a separate execution environment. Neither is available:

- The only agent-server hosts **this** session; the sole conversation is the implementation conversation.
- No Docker/podman/firejail/bwrap; `unshare --mount` is denied; exactly one RUNNING sandbox exists, and it is this host.
- Cloud sandbox creation requires credits; the org balance is `0.00` with no subscription — prohibited by the no-cost constraint.

Not accepted as independence: another process in the same runtime, another directory or virtualenv in the same container, a second shell, or self-review by the implementation agent.

Therefore the review status is **`REVIEW_PENDING_INDEPENDENCE`**. The self-review in §13 is clearly labelled as such and **must not** be treated as independent acceptance.

---

## 15. Protected-scope verification

| Protection | Status |
|---|---|
| Mini App source/tests/design/config/docs | **Untouched** — `git status bot/web/ src/` empty; frontend tests still 280/0 |
| Approved architecture (one bot+ASGI process, one SQLite owner, existing outbox/workers) | **Preserved** — no new process, worker, queue, or table |
| No app backup feature | **Not introduced** |
| No exactly-once Telegram claim | **Not made** |
| Autopush | **Remained disabled/inactive** |
| New tables/migrations/workers/queues/deps | **None** — 17 tables identical at HEAD and working tree |
| Production Telegram/OpenHands calls in tests | **None** — all clients are fakes |
| Production credentials/secrets | **None used** |
| WP-02/WP-03/WP-04/WP-07 behaviour | **Preserved** — full suite 3383/0, WP-07 working tree untouched |
| WP-06 work | **Not started** (`callback_refs`, `messages.py`, `keyboards.py` all clean) |
| Unrelated WP findings | **Not modified** |

---

## 16. Remaining risks and limitations

1. **No independent acceptance.** WP-05 is verified by the implementation agent only. `REVIEW_PENDING_INDEPENDENCE` stands.
2. **WP-05 fixes are committed but unaccepted.** They sit in HEAD `52e7789` without formal owner sign-off; this report does not grant acceptance.
3. **Concurrency not addressed.** By design — `DEF-006`/`OD-04` are out of scope. `claim_outbox_by_id` is atomic at the SQLite statement level but no broader concurrency guarantee is claimed.
4. **`on_created` swallows exceptions** (R-3). A silent cache-invalidation failure would leave stale list data until `LIST_TTL`. Accepted trade-off: cache is an optimization.
5. **Working tree carries WP-07 changes.** Not a risk to WP-05, but any future commit must separate the two cleanly.
6. **Python 3.11 CI leg not run locally** (local is 3.13). The full suite passes on 3.13; 3.11 is covered only by CI, which was not triggered (no push permitted).

---

## 17. Final implementation status

# `IMPLEMENTATION_COMPLETE`

- All five WP-05 findings (`DEF-007`, `DEF-008`, `DEF-012`, `NEW-DEF-02`, `NEW-DEF-05`) have a documented disposition: **FIXED**.
- Every fix is verified at source level and by a regression test proven non-vacuous through mutation testing (8/8 killed).
- All required tests pass: **3383 passed / 0 failed**.
- No unexplained regressions; static analysis, dependency audit, and frontend all clean.
- Protected files and excluded areas unchanged.
- The task's own diff contains only the required report.

**Not claimed:** formal owner acceptance of WP-05, or independent review.

---

## 18. Exact recommended next task

**`OHB2-WP05-INDEPENDENT-REVIEW`** — execute the independent review of WP-05 using the prepared snapshot handoff package at `/workspace/review-packages/OHB2-REV-IND-01-REVIEW-SNAPSHOT-20261119/`.

WP-05 cannot be formally closed while `REVIEW_PENDING_INDEPENDENCE` stands. Because WP-05's implementation is demonstrably complete and all its findings are closed, **`WP-06` is the next implementation candidate** — but WP-06 must **not** start until either WP-05's independent review is obtained or the owner explicitly accepts WP-05 on the strength of this evidence.

WP-06 carries its own hard prerequisite: the **`callback_refs` lifecycle and security design specification** (TTL, bounded cleanup, fail-closed handling, ownership binding, stale-callback resilience) must be completed and reviewed before any `17 → 18` schema change. `WP-06`'s `STATE_LABELS` portion is independent of that prerequisite and may proceed first.
