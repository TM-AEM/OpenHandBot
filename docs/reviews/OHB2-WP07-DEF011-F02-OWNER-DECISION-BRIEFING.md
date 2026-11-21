# OHB2 — WP-07 / DEF-011 / F-02 — Owner Decision Briefing

**Prepared:** 2026-11-21
**Purpose:** give the repository owner a verified, navigable basis to record a personal technical
decision on F-02.
**Prepared by:** an AI agent (OpenHands) on behalf of `TM-AEM`.

---

## ⚠️ What this document is not

- It is **not** an independent review.
- It does **not** recommend an outcome. No checkbox below is selected.
- It does **not** fill in the findings template.
- It does **not** close F-02, WP-07 or DEF-011.

**The technical decision is yours.** This briefing only organises verified evidence so that your
judgment is faster and better informed.

---

## 1. Verified candidate state

Re-verified against GitHub at the time of writing — not taken from earlier reports.

| Item | Value | How verified |
|---|---|---|
| Candidate commit | `6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18` | `git rev-parse refs/pull/8/head` |
| Is it still the PR #8 head? | **YES** | direct comparison |
| Parent | `f37a3f524ec745f1b5d606161c6ad8b074613a2c` | `git rev-parse` in the run |
| Base / merge-base | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` | `git merge-base origin/main` |
| PR #8 | **OPEN**, `mergedAt=null`, 0 reviews | GitHub API |
| Files in PR #8 | `bot/attachments.py`, `bot/handlers.py`, `tests/test_def011_fs_offload.py` | `gh pr view --json files` |
| `main` | `52e7789` — unchanged | `ls-remote` |
| Workflow-only PR | **#9**, head `1a84cad`, adds 1 file, **OPEN / unmerged** | GitHub API |

---

## 2. Verified evidence run

| Item | Value |
|---|---|
| **Run** | **`44881727141`** — https://github.com/TM-AEM/OpenHandBot/actions/runs/44881727141 |
| Conclusion | **success** (both jobs) |
| **Tested commit** (from run log `actual  =`) | `6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18` ✅ |
| Trigger head SHA | `1a84cad` (the workflow PR) — see the note below |
| Artifacts | `f02-review-evidence-6a1ca2e…-py3.11`, `…-py3.13` (22 files each) |
| Earlier failed run | `44881209033` — disclosed in §6 |
| Correction commit | `9d9dc51` |

**Important nuance.** The run was triggered by PR #9, whose head is `1a84cad`. The workflow then
**checked out and tested `6a1ca2e` explicitly**, and the log proves it (`expected=6a1ca2e…`,
`actual  =6a1ca2e…`, `parent=f37a3f5…`). So the *trigger* commit and the *tested* commit differ by
design — the tooling was new, the candidate was not. Verified from the artifact
`evidence/review-target-sha.txt` and the run log, not from the artifact name.

```bash
gh run download 44881727141 --repo TM-AEM/OpenHandBot -D evidence-package
```

---

## 3. Acceptance-criteria assessment

Evidence comes from the run above. Classifications: **VERIFIED** / **VERIFIED_WITH_LIMITATION** /
**NOT_VERIFIED** / **FAILED**.

| # | Criterion | Classification | Supporting evidence |
|---|---|---|---|
| 1 | **Worker-start gate + caller/worker mutual exclusion** — one `threading.Lock` decides `started` vs `abandoned`; both sides mutate state while holding it, so the two states are mutually exclusive with no timing window | **VERIFIED** | `bot/attachments.py` `store_async` gate block; `test_f02_case12_no_overlapping_acceptance` (max concurrency = 1); `test_f02_case18_no_await_while_holding_gate` statically asserts no `await` inside any `with _gate:` block (≥2 blocks checked) |
| 2 | **Cancellation before the worker acquires the gate** | **VERIFIED** | `test_f02_case01_cancel_before_submission`, `test_f02_case02_cancel_at_initial_checkpoint`, `test_f02_case03_cancel_while_waiting_for_limiter`, `test_f02_case04_cancel_after_submission_before_worker` — each asserts `cancelled`, lock released, no write, no `stored` |
| 3 | **Cancellation after the worker starts** | **VERIFIED** | `test_f02_case05_cancel_after_worker_start` — `held_at_cancel is True` (lock stays held), then released after the worker finishes; exactly 1 write; no `stored` claim |
| 4 | **Lock retention while an abandoned worker is still writing** | **VERIFIED** | `test_F02_lock_held_while_worker_writes_after_raw_cancel`; `test_f02_case05` asserts `held_at_cancel is True`; drain path uses `with anyio.CancelScope(shield=True)` before `raise` |
| 5 | **No second acceptance overlapping the abandoned worker** | **VERIFIED** | `test_f02_REV01_abandoned_worker_must_not_write_and_must_not_overlap` — deterministic (blocks the worker *thread* at the gate, so the caller wins the gate first ⇒ `abandoned=True`); asserts `writes_i1 == 0`, lock freed, second acceptance proceeds, `worker_gate_acquisitions >= 1` |
| 6 | **Unconditional worker completion signal** | **VERIFIED** | `_worker` wraps its entire body in `try/except BaseException/finally: _done.set()`; `test_f02_case10_unconditional_completion_signaling` raises a raw `BaseException` subclass and asserts the caller does not hang and the lock is released |
| 7 | **AnyIO cancellation shielding and drain behaviour** | **VERIFIED_WITH_LIMITATION** | Outer `anyio.CancelScope(shield=True)` around `run_sync(_done.wait)`; `test_f02_case13_anyio_scope_already_cancelled_at_drain` and `test_f02_case16_shutdown_completion_with_pending_cancellation` pass. **Limitation:** the shield does not stop a *second raw* `Task.cancel()` during the drain — D6, explicitly deferred (§5) |
| 8 | **Error propagation / failure behaviour** | **VERIFIED** | `except BaseException as exc: _box["error"] = exc` then re-raise to the caller; `test_f02_M4_worker_exception_not_masked_as_stored` (OSError ⇒ statuses `["pending"]`, never `stored`); `test_f02_case08_oserror_during_cancellation_path`; `test_f02_case09_unexpected_worker_exception`; `test_f02_case15_lock_released_on_every_exit_path` |
| 9 | **Regression-test quality, incl. the deterministic M4′ test** | **VERIFIED_WITH_LIMITATION** | `REV01` is genuinely mutation-sensitive: I removed the `abandoned` check and it failed for the intended reason (`writes_i1 == 0` violated), with no other test catching it — single-point coverage. A second mutation (caller never marks `abandoned`) was caught by **8** tests. **Limitation:** mutation coverage was proven for 2 mutants, not for all 45 tests |
| 10 | **Known limitations, especially D6** | **VERIFIED_WITH_LIMITATION** | D6 markers at `bot/attachments.py:916` and `:966`. `test_f02_M3_double_cancel_before_gate` covers double-cancel *before* the gate only. `test_F02_repeated_raw_cancel_keeps_single_writer` covers **sequential** cancels (3 rounds), each completing before the next — **not** a second cancel *during* the drain |

### Test results backing the table

| Check | Python 3.11.18 | Python 3.13.18 |
|---|---|---|
| F-02 focused suite | **45 passed** | **45 passed** |
| Full suite | **3330 passed** | **3330 passed** |
| Named cancellation / lock tests | **10 passed** | **10 passed** |
| pyflakes | 0 output lines | 0 output lines |
| bandit severity **High** | **0** (5 Low / 19 Medium) | **0** (5 Low / 19 Medium) |

### Negative control — genuine, not asserted

With the `bot/handlers.py` hunk reverted (blob hash asserted equal to the base blob), the run produced:

```
test_T8b_local_capped_read_runs_off_event_loop_thread FAILED [ 50%]
  AssertionError: القراءة حصلت على خيط الحلقة
  assert ([126936305281920] and False)
test_T8c_local_capped_read_enforces_cap PASSED [100%]
1 failed, 1 passed, 43 deselected
```

The traceback contains a real thread identifier — this is executed output, not an echoed claim.
`T8c` passing is correct: it tests the byte cap, not the offload.

### Hashes — independently reproduced

I recomputed every hash from the candidate commit myself; all match the artifact byte for byte.

| Path | SHA-256 |
|---|---|
| `bot/attachments.py` | `b98d561f0ba0ab27dea4e6bedee7955f68f1f6fa85a39fa81afe8aeb4d818356` |
| `bot/handlers.py` | `82d9c4b8e0fa0e005f2a7c9494a57903a94e7f79eb45d08babe5ebd9dbd57525` |
| `bot/db.py` (unchanged) | `472fa573142ee4265cdb2a26ec882906d743d798300e73ad16a9583ef5343314` |
| `tests/test_def011_fs_offload.py` | `3d3b3a2ac399fec0420e2d769f98c7c2841c69c05f341734aecef68df4f503ea` |
| `full.diff` | `cb3da6526d536dddf1eca23ba1d8b94a01b86aaf360507838d0eb10c81b02ab0` |

My own `git diff 52e7789 6a1ca2e` reproduces `cb3da652…` exactly.

---

## 4. Confirmed findings and unresolved limitations

| Category | Item | Status |
|---|---|---|
| **Implementation defects** | **None confirmed.** I looked for a defect and found none in the gate, drain, error propagation or lock-release paths | none |
| **Test / evidence gaps** | Only 2 mutants were exercised (M4′ by me, T8b by the workflow). The other 44 tests are asserted by passing, not by mutation | open |
| **Test / evidence gaps** | `REV01` is the **sole** catcher of the M4′ mutant — single-point coverage for a critical guarantee | open (observation, not a defect) |
| **Test / evidence gaps** | `pip-audit` was **not** run in this workflow (0 occurrences). Dependency SCA remains covered only by `ci.yml` | open |
| **Test / evidence gaps** | Suite has no `pytest-timeout`; several tests bound their own waits via `_F02_TIMEOUT = 2.0`, but a hang outside those waits would stall CI until the job timeout (25 min) | open (minor) |
| **Deferred risk** | **D6 — repeated raw cancellation during the drain.** Markers at `bot/attachments.py:916`, `:966`. Not fixed, not tested | **DEFERRED / OPEN** |
| **Deferred risk** | `test_F02_repeated_raw_cancel_keeps_single_writer` is *sequential*, not concurrent-with-drain. Its name could be misread as covering D6 | observation |
| **Out of scope** | NEW-DEF-03, NAV-01..06, DEF-006, other WP-07 work | not present (0 markers in the diff) |
| **Unsupported claim** | "Independent review" | **NOT available and not claimed.** No reviewer identity, no reasoning step |
| **Unsupported claim** | "Mutation coverage of all 45 tests" | **NOT established.** 2 mutants only |
| **Unsupported claim** | "`pip-audit` passed" | **NOT claimed** — it did not run here |
| **Unsupported claim** | "Exactly-once Telegram delivery" | **NOT established.** A successful test run cannot prove it |
| **Unsupported claim** | "SQLite–Telegram atomicity" | **NOT established.** Cross-system atomicity is not proven by these tests |
| **Documentation nit** | Evidence package labels `runnervm0hi8g` as the runner; it is the **hostname**. `RUNNER_NAME` is `GitHub Actions 1000000341/342`. The isolation claim is unaffected | minor, cosmetic |

I deliberately list no speculative findings. Where I found nothing, I say nothing.

---

## 5. Questions you must decide

1. **Is the F-02 worker-lifecycle guarantee sound** — specifically, is the single-`threading.Lock` gate
   (with no `await` inside it) sufficient to guarantee that a caller never releases `_accept_lock`
   while an abandoned worker is still writing?
2. **Is the drain correct** — is shielding with `anyio.CancelScope(shield=True)` around
   `run_sync(_done.wait)` the right boundary, given it cannot stop a second raw `Task.cancel()`?
3. **Is deferring D6 acceptable** — repeated raw cancellation during the drain remains unhandled and
   untested. Is that an acceptable risk for this change, or a blocker?
4. **Is the test evidence strong enough** — 45 passing tests plus 2 proven mutants. Is single-point
   coverage of the `abandoned` guarantee (only `REV01` catches M4′) acceptable?
5. **Is the `handlers.py` change correct** — does moving `_read_local_capped` into
   `to_thread.run_sync` genuinely take blocking disk I/O off the event loop, while still re-raising
   `AttachmentTooLargeError` and `OSError`?
6. **Is the scope right** — exactly 3 files, 3 hunks in `handlers.py`, 0 NEW-DEF-03/NAV markers,
   no schema / Mini App / dependency / API change?
7. **Do you accept that this is an owner review, not an independent one** — and that no independent
   reviewer exists in this environment?

---

## 6. Evidence you should inspect personally

Minimum set, roughly in order of value:

1. `evidence/full.diff` and `evidence/code-only.diff` — the actual change.
2. `bot/attachments.py` — the `store_async` gate/drain block (around the `_gate` definition), and the
   D6 markers at lines 916 and 966.
3. `bot/handlers.py` — the 3-hunk diff; check the exception re-raise survived the wrapper.
4. `tests/test_def011_fs_offload.py` — especially `REV01` (line ~1440), `case12` (~1027), `case05`
   (~971), `case10` (~1156), `case18` (~1399).
5. `evidence/negative-control.txt` — the raw failure, not the summary.
6. `evidence/file-sha256.txt` vs §3 of this briefing.
7. `evidence/FINDINGS-TEMPLATE.md` — blank, for you to fill.
8. **Reproduce it yourself** (only 4 packages needed):

```bash
git clone https://github.com/TM-AEM/OpenHandBot.git && cd OpenHandBot
git checkout 6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18
pip install pytest anyio httpx python-telegram-bot
python -m pytest tests/test_def011_fs_offload.py -q     # expect 45 passed
```

If your numbers differ from §3, stop — that would mean the target moved.

---

## 7. Possible outcomes

Select exactly one. **All fields are intentionally blank.**

| Outcome | Meaning |
|---|---|
| `ACCEPT_F02` | The implementation is correct as published; F-02 may be closed |
| `ACCEPT_F02_WITH_NOTES` | Correct, with recorded non-blocking findings (e.g. D6 deferral, single-point mutation coverage) |
| `REJECT_F02` | A blocking defect exists |
| `REQUEST_SPECIFIC_REMEDIATION` | Acceptable in principle, but specific named remediation must land first (e.g. implement D6, add mutation coverage) |
| `DEFER_OWNER_DECISION` | Not enough information yet; state what is missing |

### Owner decision record

```
Outcome:            ______________________________________________

Rationale:          ______________________________________________
                    ______________________________________________
                    ______________________________________________

Follow-ups:         ______________________________________________

Owner (identity):   ______________________________________________

Date (UTC):         ______________________________________________
```

---

## 8. Status statement

F-02 is **open**. WP-07 is **open**. DEF-011 is **open**. PR #8 and PR #9 are **open and unmerged**.
No independent review exists or is claimed. Nothing in this briefing constitutes a decision.
