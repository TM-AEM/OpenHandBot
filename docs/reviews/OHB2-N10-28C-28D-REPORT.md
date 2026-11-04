# OHB2-N10-28C + 28D — OUTBOX CONCURRENCY + OPENHANDS HTTP HARDENING

Status: COMPLETE (implementation + verification). No publication, no deployment.

## 1. Initial repository state and baseline

- Repository: `TM-AEM/OpenHandBot` (local working tree).
- Branch: `release/ohb2-20261101`.
- HEAD (baseline actual): `6021658cf3c1664ed0eadeaed2acee4e86721b6b` == BASELINE_EXPECTED.
- Working tree at start (and end): dirty by prior missions. Pre-existing modifications that
  this task did **not** touch: `automation/autopush/main.py`, `automation/autopush/README.md`,
  `requirements.txt` (+2 lines), plus untracked `bot/backup_lifecycle.py`, `docs/AUTOMATIONS.md`,
  `docs/BACKUP_OPERATIONS.md`, `docs/GOOGLE_DRIVE_BACKUP_SETUP.md`, `tools/`, and several
  `tests/_fake_*`/`tests/test_backup_*`/`tests/test_autopush_*` files. These are preserved
  byte-for-byte. No files staged; no commits; no push; no PR.

## 2. Outbox state machine

### 2.1 States
`pending` → `claimed` → `sending` → `sent`; plus `unknown`, `failed`, `discarded`.
Creation jobs: `pending` → `claimed` → `starting` → `done`; plus `unknown`, `failed`, `discarded`.

### 2.2 Original (pre-28C) behaviour and defects
- `bump_outbox_attempt` was a read-modify-write of `attempts` **and** implicitly restored a
  record to `pending`, so a record the user discarded between claim and POST could be
  "resurrected" and re-dispatched.
- The pre-POST transition (`claimed` → `sending`) and the terminal writes were plain
  `UPDATE ... WHERE id=?` (no state guard): a late worker could overwrite a newer terminal
  state (clobber).
- Discard was a read-then-write; concurrent `discard` vs `mark_sent` could produce
  contradictory outcomes.
- Creation `start_conversation` could leave a job in `starting` forever when the response was
  non-JSON (raw `ValueError` escaped the expected-error boundary).

### 2.3 Final behaviour
- `bump_outbox_attempt` is a single atomic `UPDATE ... WHERE id=? AND status='claimed'
  RETURNING attempts`; it **never changes status** and returns `0` when the record is not owned
  (so it cannot resurrect a discarded/terminal record).
- Ownership is established only by atomic claims: `claim_outbox` (`pending`→`claimed`, oldest
  first, `RETURNING *`) and `claim_creation_job` (`pending`→`claimed`).
- The last safe boundary before dispatch is a CAS: `set_outbox_status_if_in(id,'sending',{claimed})`
  for outbox and `claim_creation_starting` (`{pending,claimed}`→`starting`) for creation. If the
  record was discarded/changed meanwhile, rowcount=0 and **no POST is issued**.
- Terminal writes are CAS from the non-terminal state only (`sending`→`sent`/`failed`/`unknown`;
  `starting`→`done`). A late success/failure can never corrupt a terminal state.
- Discard is atomic with a returned boundary classification (see §3).
- No transaction is held open across a network call: each CAS commits before the `await`.

## 3. Cancellation boundary (C2)

`Database.discard_outbox` / `discard_creation_job` perform one guarded `UPDATE` and return:

- `"discarded"` — the record was eligible **before** dispatch (`pending`/`claimed`); it is now
  `discarded` (terminal). The worker cannot dispatch it (the pre-POST CAS will fail).
- `"not_confirmed"` — dispatch **may have started** (`sending`/`unknown`, or creation
  `starting`/`unknown`). The record is left untouched and the caller reports "cancellation not
  confirmed". No false cancellation claim is made.
- `"terminal"` — the record is already terminal (`sent`/`failed`/`discarded`) or missing.

Repeated discard is safe/idempotent (second call returns `terminal`).

User-visible distinctions:
- Telegram: `outbox_discard` prints "تم تعليم … كـ 'discarded'" / "ممكن يكون بدأ الإرسال …
  الإلغاء غير مؤكد" / "خلاص في حالة نهائية".
- Mini App (`bot/web/services.py`): `discard` on a not-confirmed state returns the current DTO
  with `cancellation = "not_confirmed"` (no DB change); on success returns `cancellation =
  "discarded"`; terminal → HTTP 409 `already_terminal`. `mark_sent` accepts `unknown` only
  (idempotent when already `sent`).
- Frontend (`app.js`): new `discarded` label ("اتلغت"); not-confirmed shows a note/toast and
  does **not** flip the pill to "اتلغت".

## 4. At-most-once and retry analysis (C4)

- Dispatch is attempted only after a successful pre-POST CAS, so a single record is dispatched
  at most once even with two workers (verified: two `OutboxWorker._tick()` → one send).
- Automatic retry is bounded to **pre-dispatch** safe failures (sandbox not `RUNNING`), capped
  at `MAX_OUTBOX_ATTEMPTS`; the atomic counter guarantees the cap and the single exhaustion
  notice are exact.
- Ambiguous outcomes (`sending`→`unknown`, timeouts, connection errors, 5xx, redirects) are
  **never** auto-resent. `unknown`/`failed`/`sent`/`discarded` are not eligible for claim.
- No new automatic resend path was introduced.

## 5. HTTP contracts (D1)

| Method | Endpoint | Success | Response contract | On malformed |
|---|---|---|---|---|
| `_request` | any | 2xx | — | 3xx → `ApiError(status)`; ≥400 → `ApiError(describe_status,status)`; `httpx.HTTPError` → `ApiError` (no status) |
| `search_conversations` | GET `/app-conversations/search` | 200 | dict `{items[],next_page_id}` | non-list items → `ApiError` |
| `get_conversations` | GET `/app-conversations` | 200 | array (items may be null) | other shape → `ApiError` |
| `get_current_user` | GET `/users/me` | 200 | dict | non-JSON → `ApiError` |
| `send_message` | POST `/app-conversations/{id}/send-message` | 2xx | ignored | non-2xx → `ApiError` |
| `start_conversation` | POST `/app-conversations` | 200/201 | dict with non-empty `str` `id` | non-JSON / non-dict / missing/invalid `id` → `ApiError` |
| `get_start_task` | GET `/app-conversations/start-tasks?ids=` | 200 | dict task | empty → `{}` |
| `wait_for_start` | GET start-tasks (poll) | 200 | `READY` + non-empty `str` `app_conversation_id` | invalid id → `ApiError`; `ERROR`/timeout → `ApiError` |

### 5.1 Redirect / malformed behaviour (D2)
- Any 3xx (301/302/303/307/308) is rejected in `_request` **without following** the redirect
  and without issuing a second request (verified with MockTransport call counting).
- 400/401/403/404/409/429/500/502/503/504 raise `ApiError` carrying the status code.
- Empty body, HTML/plain-text body, JSON array/primitive, and missing/invalid identifiers all
  raise a safe `ApiError` — never a raw `ValueError`/`JSONDecodeError`.
- Error detail is limited to a sanitized `detail` field (≤300 chars); non-JSON bodies are not
  echoed. TLS verification and configured timeouts are unchanged. Authorization header value
  never appears in exceptions (verified).

### 5.2 Creation-job lifecycle (D3)
- Malformed/empty start response → job `unknown` (not stuck `starting`); no auto-retry.
- Definite upstream rejection (4xx, except 429) → `failed`; ambiguous (network/timeout/5xx/
  redirect) → `unknown`; confirmed success → `done` with `task_id` + `conversation_id`.
- Restart recovery: `claimed`→`pending`; `starting`+task_id→`pending` (GET poll only, no POST);
  `starting` without task_id→`unknown`. No invented success/failure.
- Double safety: `outbox._start_conversation` also catches `ValueError` → `unknown`.

## 6. Files modified and reasons

| File | Reason |
|---|---|
| `bot/db.py` | Atomic `bump_outbox_attempt` (RETURNING, no status change); CAS `claim_creation_starting` / `finish_creation_done`; boundary-returning `discard_outbox` / `discard_creation_job`; `set_outbox_status_if_in` / `set_creation_status_if_in`; permissive low-level setters kept. |
| `bot/outbox.py` | Atomic claim in `deliver_outbox`; CAS pre-POST boundary; failure branches restore `pending` via CAS; creation CAS; `ValueError` safety. |
| `bot/handlers.py` | `outbox_discard` atomic + boundary; `outbox_mark_sent` CAS (`unknown`→terminal). |
| `bot/web/services.py` | `_OUTBOX_STATES`, `_TERMINAL_OUTBOX`, `_NOT_CONFIRMED_OUTBOX`; `reconcile_outbox` not-confirmed / 409 semantics. |
| `bot/web/static/app.js` | `discarded` label/note; not-confirmed toast; discard handling. |
| `bot/openhands_client.py` | D2 3xx rejection; D3 safe JSON decode + `id` validation; D4 `app_conversation_id` validation. |
| `tests/test_db.py`, `tests/test_outbox_commands.py`, `tests/test_miniapp_reconcile.py` | Updated legacy tests to the new (correct) contract. |
| `tests/frontend/reconcile_watch.test.js` | Added discard confirmed / not-confirmed UI tests. |
| `tests/test_outbox_concurrency_28c.py` (new) | C concurrency/cancellation tests. |
| `tests/test_openhands_http_28d.py` (new) | D HTTP hardening tests. |
| `tests/test_integration_28c_28d.py` (new) | Cross-package mocked integration tests. |

## 7. Test commands and results

Run with `.venv/bin/python -m pytest` and `node --test`; no real network (MockTransport /
fake client only).

| # | Command | Result |
|---|---|---|
| 1 | `pytest tests/test_outbox_concurrency_28c.py` | 16 passed (0.91s) |
| 2 | `pytest tests/test_outbox.py` | 29 passed (1.32s) |
| 3 | `pytest tests/test_openhands_http_28d.py` | 14 passed (0.41s) |
| 4 | `pytest tests/test_openhands_client.py` | 40 passed (0.22s) |
| 5 | `pytest tests/test_creation.py` | 14 passed (0.70s) |
| 6 | `pytest tests/test_integration_28c_28d.py` | 6 passed (0.46s, 1 deprecation warning) |
| 7 | `node --test tests/frontend/*.test.js` | 134 passed, 0 fail |
| 8 | `pytest` (full suite) | **1513 passed**, 71 warnings (52.45s) |

Warnings are pre-existing (PTB deprecation, Starlette/anyio alias). No skips, no xfails.

## 8. Static analysis

- `.venv/bin/python -m pyflakes bot/ tests/` → clean (no output).
- `.venv/bin/python -m compileall -q bot/` → OK.
- No dependency changes.

## 9. Independent review

`INDEPENDENT_REVIEW = NOT_AVAILABLE`. No genuinely independent, fresh-context reviewer was
available in this session. A structured self-review (state transitions, cancellation, duplicate
dispatch, HTTP validation, redirects, secret leakage, creation recovery, cross-package) was
performed and is recorded here; it is explicitly **not** labelled independent. `SECOND_REVIEW =
NOT_AVAILABLE`.

## 10. Remaining risks and limitations

- REMAINING_HIGH_FINDINGS: none.
- REMAINING_MEDIUM_FINDINGS: none open.
- REMAINING_LOW_FINDINGS:
  - Frontend toast auto-hide (2600 ms) and DOM node removal are not asserted in tests (the
    test DOM stub does not implement subtree `querySelectorAll`); tests assert observable
    pill/toast text instead.
  - Ambiguity classification assumes the documented `ERROR` enum means "ambiguous"; treated as
    `unknown` deliberately.
- REMAINING_BLOCKERS: none.
- Limitations: single-process architecture preserved; SQLite WAL + `busy_timeout=5000` respected;
  no new retry paths.

## 11. Final safety confirmation

- No commit, push, PR, merge, or deployment. `FILES_STAGED = NO` (nothing staged).
- No real Telegram polling/messages; no real OpenHands requests; no external network calls
  (all tests use MockTransport / fake clients).
- Autopush not executed and not modified (`UNCHANGED_DISABLED_INACTIVE`).
- No backup execution or backup-file changes.
- `requirements.txt` unchanged by this task (its pre-existing +2 lines preserved).
- All 28B and unrelated local changes preserved.
- No secrets in this report or in test output.

NEXT_RECOMMENDED_TASK: run a genuinely independent, fresh-context read-only review of 28C/28D
before any publication (none performed here).
