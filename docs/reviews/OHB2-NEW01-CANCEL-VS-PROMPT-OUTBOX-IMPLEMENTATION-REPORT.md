# OHB2-NEW01 — Cancel vs Prompt Outbox Atomicity — Implementation Report

**Task ID:** `OHB2-NEW01-CANCEL-VS-PROMPT-OUTBOX-ATOMICITY`  
**Date:** 2026-11-21  
**Verdict:** **`DONE`**

## 1. Baseline

| Item | Baseline |
|---|---|
| Branch before work | `main` |
| HEAD | `2217a2538a019d5a3a712bae2e33e72ae35a8393` |
| Working tree | Clean (`git status --short` empty) |
| Staged changes | None |
| Untracked files | None |
| Implementation branch | `agent/ohb2-new01-cancel-race` (created from `main`) |
| Remote | Not fetched or pushed during this task |

The working tree contained no unrelated changes. `.openhands/`, `.agent/`, ignored caches and untracked files were left untouched.

## 2. Root cause

The prompt handler reads the selected route before an asynchronous deletion-witness check:

1. `handle_text` reads `pending`/`last_target` and checks `is_routing_paused`.
2. `_send_prompt` awaits `_is_deleted_with_retry`.
3. While it waits, `/cancel` commits `pause_routing=True` and clears `awaiting` in
   `clear_awaiting_and_record_outcome`.
4. The handler resumes and calls `add_or_group_outbox`.
5. The existing `expected_routing` CAS checked only `last_accessed` and the route target.
   `/cancel` intentionally leaves `last_accessed` intact for `/chat`, so the stale target
   still matched and the prompt was accepted.
6. `_send_prompt` then sent the queued acknowledgement.

The defect was a time-of-check/time-of-use gap at the actual durable acceptance boundary,
not merely a missing early pause check.

### Reproduction before the fix

Deterministic handler/DB script:

- `paused=True`
- `awaiting=(None, None)`
- `last_accessed=A`
- one pending outbox row for A
- acknowledgement: `وصل ✅ ← «A» — تم حفظ طلبك، ولسه هيتبعت.`

## 3. Atomic ordering invariant

For a given `(telegram_id, routing state)`:

- **Cancellation commits first:** the prompt must be rejected, with no outbox row and no
  success/queued acknowledgement.
- **Prompt acceptance commits first:** `/cancel` may follow, but the already accepted outbox
  row is preserved according to existing semantics; cancellation does not delete accepted work.
- There must be no state where cancellation commits first and a not-yet-accepted prompt is
  subsequently accepted from stale routing state.

Both operations serialize through the same SQLite `BEGIN IMMEDIATE` write boundary. The
acceptance transaction re-reads the durable `routing_paused:<telegram_id>` setting after the
target reads and before any outbox insert.

## 4. Files changed

| File | Reason |
|---|---|
| `bot/db.py` | Added the pause check inside the `expected_routing` CAS transaction; documented NEW-01. |
| `tests/test_new01_cancel_prompt_atomicity.py` | New deterministic R1–R8 regression tests using the real SQLite-backed handler/outbox path. |
| `docs/reviews/OHB2-NEW01-CANCEL-VS-PROMPT-OUTBOX-IMPLEMENTATION-REPORT.md` | This report. |

No other application, test, documentation, Mini App or architecture file was changed.

## 5. Transaction/CAS design

In `Database.add_or_group_outbox`, inside the existing `BEGIN IMMEDIATE` transaction and
inside the existing `expected_routing` block:

```sql
SELECT value FROM settings WHERE key = 'routing_paused:<telegram_id>'
```

If the value is `"1"`, the transaction is rolled back and `0` is returned before any outbox
row is inserted. `_send_prompt` already treats `0` as “not accepted” and does not send the
queued acknowledgement.

This preserves:

- the single authoritative SQLite owner;
- the existing outbox table and lifecycle;
- the existing worker model;
- the existing `expected_routing` destination CAS;
- existing duplicate-update handling;
- existing restart persistence (the pause and outbox state remain in SQLite).

The SQLite write lock gives the deterministic order:

- cancellation first → acceptance waits, then sees `routing_paused=1` and rejects;
- acceptance first → acceptance commits, cancellation follows and does not remove the row.

## 6. Regression tests

New file `tests/test_new01_cancel_prompt_atomicity.py`:

| Test | Proves |
|---|---|
| `test_new01_r1_cancel_committed_during_preparation_rejects_prompt` | Original race: cancellation commits while handler is blocked; no outbox row, no queued ack, pause remains. |
| `test_new01_r1b_reply_state_cancel_during_preparation_rejects_prompt` | Equivalent reply-state interleaving is rejected by atomic awaiting consumption. |
| `test_new01_r2_accepted_prompt_survives_later_cancel` | Acceptance-first ordering preserves the accepted outbox row; cancellation follows without deleting it. |
| `test_new01_r3_concurrent_cancel_and_acceptance_have_serial_order` | Deterministic two-task barrier: cancel commits before prompt release; no stale acceptance. |
| `test_new01_r4_destination_change_during_preparation_rejects_prompt` | Existing destination CAS still rejects A after B is selected; no row or success ack. |
| `test_new01_r5_busy_retry_does_not_bypass_pause` | Real second SQLite connection holds a write lock; BUSY is raised; after release, a paused acceptance still returns `0`. |
| `test_new01_r6_failure_at_acceptance_boundary_does_not_ack` | Injected `INSERT INTO outbox` failure propagates; no row, no acknowledgement, no false success. |
| `test_new01_r7_rejected_prompt_does_not_reappear_after_restart` | Reopened DB keeps pause; later text creates no outbox and receives only the pause explanation. |
| `test_new01_r8_duplicate_update_cannot_bypass_cancel_guard` | Retrying the same update after cancellation creates no second outbox row and no queued ack. |

Existing tests also cover cancellation atomicity, outbox routing, destination CAS, duplicate
updates, restart/recovery and durable cleanup; the full suite is green.

## 7. Test commands and results

Environment: Python **3.13.15**, Node **v24.22.2**, virtualenv `/tmp/ohb2-chat-venv`.

| Command | Result |
|---|---|
| `python -m pytest -q tests/test_new01_cancel_prompt_atomicity.py` | **9 passed**, 0 failed |
| Focused regression: NEW-01 + `test_def011_review_remediation` + cleanup + chat + sticky routing + duplicate dispatch + handlers + parity | **217 passed**, 0 failed |
| `python -m pytest -q` | **3723 passed**, 0 failed, 74 warnings (182.70s) |
| `node --test tests/frontend/*.test.js` | **280 passed**, 0 failed |
| `python -m pyflakes bot automation tools main.py tests/` | exit 0, no findings |
| `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | exit 0; High: 0 |
| `python -m pip_audit -r requirements-dev.txt` | exit 0; no known vulnerabilities |
| `python -m compileall -q bot automation tools main.py tests` | exit 0 |
| `git diff --check` | exit 0 |

The baseline full suite was 3714 passed; the final suite is 3723, a **+9** increase from the
nine new tests. No tests were skipped in these runs.

Not run: Python 3.11 suite (interpreter unavailable), real Telegram/OpenHands calls, Mini App
UI tests beyond the established Node frontend suite.

## 8. Quality checks

- `pyflakes`: clean.
- `bandit`: High 0; no new security finding.
- `pip-audit`: no known vulnerabilities.
- `compileall`: clean.
- `git diff --check`: clean.
- No secrets, production credentials or external service calls were used.

## 9. Self-review findings

- The protection is at the actual acceptance transaction, not only at the earlier handler
  check.
- Cancellation-first is rejected with no outbox row and no acknowledgement.
- Acceptance-first preserves the accepted row; existing cancellation semantics are unchanged.
- `out_id == 0` remains the single rejection path; no new user-facing success wording was
  introduced.
- Failure injection at the outbox insert propagates and leaves no partial row.
- The pause setting is read in the same SQLite write transaction as the target CAS.
- No new worker, process, database, queue or architectural subsystem was introduced.
- No unrelated files were modified.

Residual note: this is a self-review, not an independent review. The change does not address
NEW-02, NEW-03, F-01 callback residual, F-10 or F-11.

## 10. Limitations and remaining risks

- No real multi-process or production Telegram/OpenHands test; SQLite contention is covered
  with a real second connection in R5.
- Python 3.11 is not available.
- The Mini App is frozen and was not modified.
- A prompt accepted before cancellation remains in the outbox, matching existing semantics;
  this task intentionally does not invent cancellation semantics for already accepted work.
- Cancellation state is durable, but a later explicit `/start`/selection can resume routing
  as before.

## 11. Git status after implementation

Branch: `agent/ohb2-new01-cancel-race`  
Base commit: `2217a2538a019d5a3a712bae2e33e72ae35a8393`

Expected working-tree state:

- `M bot/db.py`
- `?? tests/test_new01_cancel_prompt_atomicity.py`
- `?? docs/reviews/OHB2-NEW01-CANCEL-VS-PROMPT-OUTBOX-IMPLEMENTATION-REPORT.md`

No commit was created.

## 12. Explicit safety confirmation

No commit, push, PR, merge, deployment, release or Autopush activation occurred. No
production Telegram or OpenHands operation was performed. No destructive Git operation or
broad staging command was used.
