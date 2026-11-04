# OHB2-N10-28C + 28D — INDEPENDENT REVIEW (fresh-context, read-only)

Reviewer context: fresh-context reviewer; not the author of the 28C/28D implementation in this
session. All actions were read-only. No commit/push/fetch/pull/merge/branch/PR/deploy. No Autopush
execution or edits. No backup execution/edits. No real Telegram/OpenHands/network calls (tests use
`httpx.MockTransport` / fake clients / local SQLite only).

Verdict: **PASS_WITH_NOTES** — implementation is correct and well-defended; one **flaky,
order-dependent test** must be fixed before publication. Publication readiness: **NOT ready to
publish until F-1 is corrected** (the implementation itself is safe; the test would intermittently
red a CI-equivalent run).

---

## 1. Actual repository state (independently observed)

- HEAD = `6021658cf3c1664ed0eadeaed2acee4e86721b6b` (matches BASELINE_EXPECTED).
- Branch = `release/ohb2-20261101`.
- Index (staged) = **empty** (`git diff --cached --name-only` → nothing).
- `git stash list` = empty. No refs/tags/branches created or changed by this review.
- Worktree dirty (unchanged by review — verified before and after):

Tracked modifications (`git status --short`):
`automation/autopush/README.md`, `automation/autopush/main.py`, `bot/db.py`, `bot/handlers.py`,
`bot/openhands_client.py`, `bot/outbox.py`, `bot/web/services.py`, `bot/web/static/app.js`,
`requirements.txt`, `tests/frontend/reconcile_watch.test.js`, `tests/test_db.py`,
`tests/test_miniapp_reconcile.py`, `tests/test_outbox_commands.py`.

Untracked: `bot/backup_lifecycle.py`, `docs/AUTOMATIONS.md`, `docs/BACKUP_OPERATIONS.md`,
`docs/GOOGLE_DRIVE_BACKUP_SETUP.md`, `docs/reviews/` (whole dir), `tests/_fake_gdrive.py`,
`tests/_fake_ssh_server.py`, `tests/test_autopush_automation.py`, `tests/test_autopush_security.py`,
`tests/test_backup_gdrive.py`, `tests/test_backup_gdrive_transport.py`, `tests/test_backup_lifecycle.py`,
`tests/test_backup_retention_policy.py`, `tests/test_backup_sqlite.py`,
`tests/test_integration_28c_28d.py`, `tests/test_openhands_http_28d.py`,
`tests/test_outbox_concurrency_28c.py`, `tests/test_restart_recovery.py`, `tools/`.

Baseline + pre-existing unrelated changes preserved: YES. `requirements.txt` still carries only the
pre-existing backup-only `paramiko==3.5.1` (+2 lines, comment referencing OHB2-N10-11); not touched
by 28C/28D. Autopush files are modified but were already modified before this mission.

28C/28D scope match: YES. The 28C/28D delta touches exactly `bot/db.py`, `bot/outbox.py`,
`bot/handlers.py`, `bot/web/services.py`, `bot/web/static/app.js`, `bot/openhands_client.py`, the four
updated legacy tests, and the three new test files — nothing in autopush/backup/requirements.

---

## 2. Independently verified test results

All commands run with `.venv/bin/python -m pytest` (pytest.ini: `asyncio_mode=auto`,
`testpaths=tests`) and `node --test`. No external requests.

| Command | Result | Exit |
|---|---|---|
| `pytest tests/test_outbox_concurrency_28c.py -q` | 16 passed | 0 |
| `pytest tests/test_openhands_http_28d.py -q` | 14 passed | 0 |
| `pytest tests/test_integration_28c_28d.py -q` | 6 passed, 1 warning | 0 |
| `pytest tests/test_outbox.py -q` | 29 passed | 0 |
| `pytest tests/test_openhands_client.py -q` | 40 passed | 0 |
| `pytest tests/test_creation.py -q` | 14 passed | 0 |
| `pytest tests/test_db.py -q` | 81 passed | 0 |
| `pytest tests/test_outbox_commands.py -q` | 32 passed | 0 |
| `pytest tests/test_miniapp_reconcile.py -q` (standalone) | **1 failed, 15 passed** (~50% of runs) | 1 |
| `pytest tests/test_handlers.py -q` | 72 passed | 0 |
| `pytest tests/test_u04_concurrency.py -q` | 9 passed | 0 |
| `pytest tests/test_miniapp_operations.py -q` | 17 passed | 0 |
| `pytest` (full suite) | **1513 passed, 71 warnings** (7/7 runs) | 0 |
| `node --test tests/frontend/*.test.js` | 134 pass / 0 fail | 0 |
| `.venv/bin/python -m pyflakes bot/ main.py tests/` | clean | 0 |
| `.venv/bin/python -m compileall -q bot/ main.py` | COMPILE_OK | 0 |

Key independent result: the report's headline "1513 passed / 134 node / pyflakes clean" is
**confirmed**. However, the report's claim "`tests/test_miniapp_reconcile.py` … all green" is
**NOT reproducible**: run standalone the file fails ~50% of the time (F-1).

Warnings are deprecation-only (e.g. `starlette.testclient` anyio.abc.BlockingPortal alias, PTB).
No skips/xfails observed.

Flakiness quantification:
- `tests/test_miniapp_reconcile.py` alone: **8/15** runs failed (also 7/10 with a different loop).
- `tests/test_outbox_concurrency_28c.py` alone: 0/15 failed (deterministic).
- Full suite: 0/7 failed.
- `test_miniapp_reconcile.py` preceded by `test_miniapp_operations.py`: 0/10 failed.

---

## 3. Package 28C — Outbox concurrency (verified)

Independently confirmed correct (read + targeted probes):

- **Atomic ownership/claims.** `db.claim_outbox` (`bot/db.py:1153`) and `claim_creation_job` are
  single-statement `UPDATE … WHERE status='pending' … RETURNING *`. `bump_outbox_attempt`
  (`bot/db.py:1133`) is `UPDATE … WHERE id=? AND status='claimed' RETURNING attempts`, returns 0 when
  not owned and **does not change status** — it cannot resurrect a discarded/terminal row. Verified by
  `test_bump_outbox_attempt_does_not_resurrect_a_discarded_record`.
- **CAS immediately before dispatch.** Outbox: `set_outbox_status_if_in(id,'sending',{claimed})`
  (`bot/outbox.py:196`) — on failure it logs and returns **without POST** (`bot/outbox.py:198-200`).
  Creation: `claim_creation_starting({pending,claimed}→starting)` (`bot/db.py:1400`) — on failure
  returns without POST (`bot/outbox.py:512-514`).
- **No network when ownership is lost.** Verified by `test_discard_during_prep_prevents_post` and
  `test_creation_discard_before_post_prevents_start`.
- **No stale writer can overwrite a newer/terminal state.** All terminal writes are CAS from the
  non-terminal source (`bot/outbox.py:210-231, 234-241, 486-556`). `finish_creation_done`
  (`bot/db.py:1432`) is CAS from `{claimed,starting}`.
- **No DB transaction held across network I/O.** Each CAS helper commits internally before returning;
  the network `await`s happen after the CAS returns. Verified by reading all helpers (no `BEGIN` spans
  an `await`).
- **Discard boundaries** (`db.discard_outbox` `bot/db.py:1447`, `discard_creation_job` `bot/db.py:1471`):
  `pending`/`claimed` → `discarded`; `sending`/`unknown` (creation `starting`/`unknown`) →
  `not_confirmed` (row untouched); terminal/missing → `terminal`. Matches report §3.
- **Duplicate callbacks / repeated discard.** Repeated discard is idempotent (second call → `terminal`).
  `test_two_outbox_workers_cannot_send_same_record_twice` confirms a single send.
- **Status reporting.** Telegram (`bot/handlers.py:1026-1049`) and Mini App
  (`bot/web/services.py:558-626`) both distinguish `discarded` vs `not_confirmed`; frontend labels
  `bot/web/static/app.js:127,209` and the not-confirmed toast path `app.js:280-289`.
- **No auto-resend after ambiguous POST.** `sending`→`unknown`/`failed`; `unknown`/`failed`/`sent`/
  `discarded` are never eligible for claim. Confirmed by
  `test_ambiguous_send_outcome_is_unknown_and_never_auto_resent`.
- **SQLite concurrency with real competing connections.** `test_reconcile_discard_uses_atomic_cas_under_concurrency`
  uses two independent `Database` connections and a `threading.Barrier`; deterministic across 5 runs.
- **Creation cancel + restart recovery** (`bot/outbox.py:579-599`): `claimed`→`pending`;
  `starting`+task_id→`pending` (GET poll only); `starting` without task_id→`unknown`. No invented
  success/failure.

Edge cases exercised by me: claim/discard race (product final state always `sent`, correct), discard
during prep (no POST), late response after discard (CAS fails → no clobber).

---

## 4. Package 28D — OpenHands HTTP (verified)

Independently confirmed correct:

- **3xx rejected without following** (`bot/openhands_client.py:68`): raises `ApiError(status)` before
  the `>=400` branch; `httpx.AsyncClient` is constructed with default `follow_redirects=False`
  (no override found). `test_redirect_on_send_is_not_success` confirms a single request for a 307 and
  that it is not treated as success.
- **Malformed/empty/non-JSON/structurally-invalid fail safely.** `_decode_json`
  (`bot/openhands_client.py:412`) converts `ValueError`→`ApiError`; `start_conversation` uses a local
  try/except and `isinstance(payload, dict)` (`:349`) + strict `isinstance(task_id, str) and
  task_id.strip()` (`:354`); `wait_for_start` validates `app_conversation_id` (`:379`);
  `_as_items` raises on unexpected shapes.
- **Strict identifier validation.** Non-empty `str` required for `task_id` and `app_conversation_id`;
  numbers/`None`/empty rejected.
- **No secret leakage.** `ApiError` redacts registered secrets (`bot/errors.py`); `_detail`
  (`bot/openhands_client.py:480`) exposes only a `detail` field (≤300 chars) and returns "" for
  non-JSON bodies. `test_api_key_never_appears_in_exception_or_headers` passes.
- **Timeouts/TLS unchanged.** `timeout=30.0` default; no `verify=` override (default TLS verify on).
- **Definite vs ambiguous outcomes.** `is_permanent` = `400 ≤ status < 500` minus `{429}`
  (`bot/outbox.py:108-111`). 4xx (except 429) → `failed`; network/timeout/5xx/redirect → `unknown`.
- **No duplicate creation on ambiguous POST.** Creation CAS + `unknown` state means no automatic
  re-POST; `test_malformed_start_response_then_restart_does_not_duplicate` confirms exactly one POST.
- **No falsely-stuck / unsupported success/failure states.** Malformed start → `unknown` (not stuck
  `starting`); restart recovery correct; `finish_creation_done` CAS prevents false `done`.

---

## 5. Findings

### F-1 — MEDIUM (test correctness): flaky, order-dependent concurrency test
- File/line: `tests/test_miniapp_reconcile.py:220-256`, failing assertion at line 255
  (`assert results["discard"].status_code == 200`).
- Reproducible scenario: `pytest tests/test_miniapp_reconcile.py` fails ~50% of the time (8/15 in my
  runs). Two threads race `discard` and `mark_sent` on an `unknown` outbox row, coordinated by a
  `threading.Barrier`.
- Root cause (verified with a 12-trial probe): the test assumes `discard` always runs first. When
  `discard` wins, it sees `unknown` → `not_confirmed` → 200. When `mark_sent` wins first, the row
  becomes `sent` and `discard` correctly returns **409 `already_terminal`**. The product behaviour is
  correct in both interleavings; only the assertion is order-dependent. Probe results:
  `discard=200/not_confirmed` (11/12) vs `discard=409` (1/12), `final=sent` always.
- Impact: intermittent red in a CI-equivalent single-file run; contradicts the implementation report's
  "all green". The full-suite run happened to schedule `discard` first in 7/7 of my runs, so it is not
  currently caught by CI — a false sense of stability.
- Why existing tests don't catch it: the test encodes one specific interleaving; the file-level
  thread timing usually orders `discard` first, masking the defect. Full-suite import/scheduling
  happens to be deterministic here.
- Recommended correction: make assertions order-independent — accept either outcome, e.g.
  `assert results["discard"].status_code in (200, 409)`; if 200 assert
  `cancellation == "not_confirmed"`; if 409 assert the row is `sent`. Also assert the invariant
  `final == "sent"` (already present). Alternatively, force ordering deterministically instead of
  relying on a barrier race.

### F-2 — LOW (test coverage): frontend not-confirmed test has a vacuous negative assertion
- File/line: `tests/frontend/reconcile_watch.test.js:126-134` (assertion
  `!texts.includes("اتلغت")`); DOM stub `tests/frontend/dom_stub.js:91` (`El.querySelectorAll()` → `[]`).
- Scenario: the app.js not-confirmed path returns early (`bot/web/static/app.js:286-288`) and does
  **not** run the status-subtree rebuild at `app.js:290` (`box.querySelectorAll(".op-status, …")`).
  Because the stub returns `[]` for element-level `querySelectorAll`, the rebuild/removal is never
  exercised; the negative assertion passes even though the code path is untested.
- Impact: the negative assertion provides no real protection against a regression that would flip the
  pill to "اتلغت". The positive assertion (`toast` contains "غير مؤكد") is meaningful.
- Why existing tests don't catch it: the stub intentionally omits subtree `querySelectorAll`.
- Recommended correction: extend the DOM stub to return matching descendants for `querySelectorAll`,
  then assert the status subtree is unchanged; or assert directly on the element children (as other
  frontend tests do via `descendants`). This is the residual concern (1) from the implementation
  report — it is a **testing limitation, not a product defect** (the early return is correct).

### F-3 — LOW/INFORMATIONAL (product parity): creation discard boundary is Telegram-only
- Files: `bot/handlers.py:1013-1049` (Telegram `discard_creation_job` boundary) vs
  `bot/web/app.py:225` (Mini App exposes only `operations/outbox/reconcile`).
- Scenario: the Mini App cannot discard/reconcile a *creation* job; creation discard boundaries are
  reachable only via the Telegram command. Creation discard logic is unit-tested at the DB level
  (`test_discard_creation_job_boundaries`).
- Impact: feature asymmetry, not a safety defect (no false cancellation is possible anywhere).
- Recommended correction: document, or add a creation reconcile route in a later mission if desired.

### F-4 — INFORMATIONAL: `ERROR` enum treated as ambiguous (`unknown`)
- Files: `bot/openhands_client.py:381-384` (`wait_for_start` raises `ApiError` on `ERROR`),
  classified `unknown` at `bot/outbox.py:532-537`.
- Assessment: safe. `unknown` is terminal-ish (no auto-retry, not claimable); restart recovery leaves
  it. Treating `ERROR` as ambiguous can at worst require a manual `mark_sent`, never a duplicate
  creation. Residual concern (2) from the report is **not a defect**; it is a deliberate,
  safe-under-uncertainty choice (documented at `bot/openhands_client.py:381-383`).

### F-5 — INFORMATIONAL: discard classification is not a single atomic statement
- Files: `bot/db.py:1447-1469` (`discard_outbox`), `bot/db.py:1471-1493` (`discard_creation_job`).
- Detail: the guarded `UPDATE` (the mutation) is atomic; the boundary *label* is derived by a
  follow-up `SELECT` when the UPDATE matches 0 rows. Under extreme concurrency the returned label
  could reflect a slightly newer state than at UPDATE time. The mutation itself can never be wrong, and
  a fresher label is desirable. No corrective action required; noted for completeness.

---

## 6. Residual concerns — determination

1. **Frontend toast auto-hide + DOM removal not asserted** → **real but test-only** (F-2). The product
   code is correct; the DOM stub cannot exercise element-level `querySelectorAll`, so the negative
   assertion is vacuous. Fix the stub/test; no product change needed.
2. **`ERROR` enum treated as ambiguous** → **not a defect** (F-4). Safe under uncertainty; no
   auto-retry; recovery covered.

---

## 7. Unverified claims and environmental limitations

- "was 1477 (baseline)" in the report is **UNVERIFIED** — confirming the pre-28C count would require
  reverting the worktree (destructive), which this read-only review did not do. The post-change total
  (1513) is independently confirmed.
- The exact composition of the 71 warnings was not enumerated; spot checks show deprecation-only
  warnings (anyio/starlette alias, PTB).
- Timing/ordering of the full suite is environment-dependent; the flaky test (F-1) is currently masked
  in full-suite runs but reproducibly fails standalone.
- No real Telegram/OpenHands/network operations were performed; HTTP paths were validated only through
  `MockTransport` and fakes.

---

## 8. Overall verdict and publication recommendation

- Implementation (28C + 28D): **correct** — atomic ownership/claims, CAS at the dispatch boundary, no
  network on lost ownership, no terminal-state clobber, no txn across I/O, boundary-classified discard,
  safe HTTP/JSON handling, strict identifier validation, no secret leakage, no auto-resend after
  ambiguous POST, and sound creation-job lifecycle/recovery.
- Test suite: one **flaky/order-dependent test** (F-1) must be fixed; one **vacuous assertion**
  (F-2) should be strengthened.
- Verdict: **PASS_WITH_NOTES**.
- Publication readiness: **NOT READY** until F-1 is fixed (and ideally F-2). The product code is safe
  to publish; the blocker is test reliability, which would intermittently red a CI-equivalent run.

Recommended next step (separate authorization): fix F-1 (order-independent assertions) and F-2
(stub `querySelectorAll`), re-run `pytest tests/test_miniapp_reconcile.py` standalone ≥20× and the
full suite, then proceed to publication review.

No implementation changes were made and no Git publication was performed by this review.
