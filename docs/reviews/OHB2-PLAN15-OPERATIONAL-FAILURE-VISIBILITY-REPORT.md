# OpenHandBot Plan 05 Execution Report — Status/Cost Failure Visibility and SW-02 Investigation

- **Task ID:** `OHB2-PLAN-15-OPERATIONAL-FAILURE-VISIBILITY-EXECUTION-01`
- **Plan ID:** `OHB2-PLAN-15-OPERATIONAL-FAILURE-VISIBILITY`
- **Priority:** `Medium` (confirmed **no** escalation to High: no evidence that users are misled into believing failed `show_status`/`show_cost` operations succeeded)
- **Date:** 2026-11-16

---

## 1. Baseline Environment & Workspace State

- **Git metadata:** `.git` directory is absent in `/app/applet` (all git commands fail with `fatal: not a git repository`). Commit history, branch name, and git status could not be verified locally.
- **Python runtime:** Python 3.10.12 (stdlib only; `pytest`, `pyflakes`, `bandit`, `pip_audit`, `python-telegram-bot`, `httpx`, `starlette`, `python-dotenv`, `anyio`, `uvicorn` are not installed).
- **Pre-edit checks:**
  - `python3 -m compileall -q bot automation tools main.py tests` → exit `0` (`COMPILEALL_OK`)
  - AST parse across all `164` `.py` files → exit `0` (`AST_OK:164`)
  - `node --test tests/frontend/*.test.js` → `280 pass / 0 fail` (exit `0`)
  - `python3 -m pytest -q` → exit `1` (`No module named pytest`)
  - `python3 -m pyflakes bot/ automation/ tools/ main.py tests/` → exit `1` (`No module named pyflakes`)
  - `python3 -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` → exit `1` (`No module named bandit`)
  - `python3 -m pip_audit -r requirements-dev.txt` → exit `1` (`No module named pip_audit`)
- **Preserved invariants:** `MINI_APP_ENABLED` defaults to `False` (`bot/config.py:262`), `concurrent_updates(True)` in `bot/app.py:86`, single bot + ASGI process, single SQLite owner, no new worker/scheduler/daemon/process/database/state owner, Autopush inactive, existing Plan 03 / Plan 04 / `.agent/PROGRESS.md` work preserved.

---

## 2. OPS-01: Pre-Edit Behavior & Failure Matrix (`show_status` and `show_cost`)

### 2.1 End-to-End Call Chain
- **Dispatch (`bot/app.py`):**
  - `group=-1`: `TypeHandler(Update, handlers.dedupe_update)` (reads `processed_updates` with bounded BUSY/LOCKED retry; failures are stored only in `update_failures` so redelivery still executes; already-processed updates raise `ApplicationHandlerStop`).
  - `group=0`: `CallbackQueryHandler(handlers.show_status, pattern=r"^status:")` (always registered) and `CallbackQueryHandler(handlers.show_cost, pattern=r"^cost:")` (registered unless `features.is_hidden("cost")`, currently `False`).
  - Error handler: `handlers.handle_processing_error` calls `record_update_failure(update, context, exc)` → `_classify_failure(exc)` → best-effort `db.mark_update_outcome(...)`.
- **Execution (`bot/handlers.py:1345-1429`):**
  1. `await q.answer()` (pre-edit baseline: uncaught).
  2. `_allowed(update, config)` → on unauthorized user/non-private chat, `_authorization_ignored` records `EXPLICITLY_IGNORED`.
  3. `_authorized_conversation_status(client, context, conversation_id)` → `authorize_conversation_detailed` (`bot/files.py:220-266`): validates ID (`is_valid_conversation_id`), enforces tombstone (`db.is_deleted`), fetches `client.get_conversations([conversation_id])`, verifies owner via `IdentityCache.owner_id_detailed()` (`/users/me`).
  4. If `conv is None`: calls `await _safe_edit(q, message)` (returns `True` if edited, `False` if `"not modified"`, re-raises any other exception). If `status is FileStatus.UPSTREAM_ERROR and not _is_expected_upstream_rejection(auth_exc)` → strict `mark_operational_failure(..., "show_status_upstream_failure"|"show_cost_upstream_failure")` (`FAILED_TRANSIENT`). Otherwise → `mark_explicitly_ignored` (`EXPLICITLY_IGNORED`).
  5. If `conv is not None`: formats status (`state_label`, `pr_url`) or cost (`format_cost(conv.get("metrics"))`), then calls `await _edit_or_send(q, text, q.message.chat_id, context.bot, reply_markup=kb.conversation_actions(conversation_id))`.
     - Returns `True`: calls `mark_explicitly_ignored` (`EXPLICITLY_IGNORED`).
     - Returns `False`: logs `log.warning("تعذّر عرض ...")`, calls `mark_display_failed(..., "show_status_display_failed"|"show_cost_display_failed")` (`FAILED_TRANSIENT`), returns normally.
- **Polling & Acknowledgment (`bot/polling.py`, `bot/update_outcomes.py`, `bot/db.py`):**
  - `TelegramPoller.process_updates` waits on `update_queue.join()`, reads `db.update_outcome(uid)` (defaulting missing to `PARTIAL_OR_UNKNOWN`), computes longest eligible prefix `acknowledgment_boundary`, persists monotonically in `commit_batch_outcomes`, and advances `_next_offset = boundary + 1` only when `boundary is not None`.
  - No outbox rows are created (`show_status`/`show_cost` are read/display paths).

### 2.2 Compact Behavior / Failure Matrix (Baseline Observed Before Any Edit)

| # | Scenario | Handler Branch & Exception Translation | User-Visible Outcome | Logging | Persisted Outcome & Ack Eligibility | Polling / Recovery / Restart Effect | Classification |
|---|---|---|---|---|---|---|---|
| 1 | **Normal success** (`conv` owned, Telegram edit/not-modified/`send_long` succeeds) | `_edit_or_send` → `True`; `mark_explicitly_ignored` | Status/cost message + `conversation_actions` keyboard shown (or unchanged if `"not modified"`) | Normal/none | `EXPLICITLY_IGNORED` (`processed_updates`) — **ack-eligible** | Offset advances cleanly; deduplicated on duplicate delivery | **Intentional ADR behavior** |
| 2a | **OpenHands transient failure** (`5xx`, `429`, HTTP timeout, connection error on `get_conversations` or `/users/me`) | `OpenHandsClient._request` translates `httpx.HTTPError` → `ApiError(..., None)` / `5xx,429` → `ApiError(..., code)`; `authz` returns `UPSTREAM_ERROR` + `auth_exc`; `_is_expected_upstream_rejection` is `False`; `_safe_edit` delivers `message`; `mark_operational_failure` (strict) | User sees sanitized Arabic upstream error message (no raw secrets/details; 0 automatic retries in `OpenHandsClient`) | None/DB warning if DB fails | `FAILED_TRANSIENT` (`update_failures` only) — **ineligible** (fail-closed) | Head-of-line blocks offset; `update_is_processed=False`; Telegram redelivers on poll/restart | **Intentional ADR §37 behavior** (`test_stage4_f1_status_cost_operational_ack.py`) |
| 2b | **Stale/failing `q.answer()`** (e.g., `BadRequest("Query is too old...")` on redelivery after transient failure/restart, or `TimedOut` on `q.answer()`) | Bare `await q.answer()` at `1347`/`1398` raises **before** `_authorized_conversation_status` → `handle_processing_error` → `_classify_failure(BadRequest)` | **No message edited or sent**; recovery blocked even after OpenHands recovers | `log.error` (`type(exc).__name__`) | `FAILED_PERMANENT` (`update_failures`) — **ineligible** | **Defeats Telegram redelivery recovery**; permanently wedges head-of-line offset on expired `callback_query` | **CONFIRMED IN-SCOPE DEFECT (`OPS01-D1`)** — safe to fix matching `send_reply_txt` / `SW09` |
| 2c | **SQLite transient failure (`BUSY`/`LOCKED`)** | In `dedupe_update`: bounded retry (`_DEDUPE_RETRY_DELAYS`), then `ApplicationHandlerStop` + `FAILED_TRANSIENT`. In `mark_operational_failure`: strict raise → `handle_processing_error` → `FAILED_TRANSIENT` (or `None` → `PARTIAL_OR_UNKNOWN`). In `is_deleted`: fail-closed `DELETED` (with retry missing on `is_deleted`, note `mark_explicitly_ignored` best-effort) | On `dedupe_update` failure: silent stop (fail-closed). On `mark_operational_failure` failure: upstream error already shown | `log.exception` / `log.warning` | `FAILED_TRANSIENT` or `PARTIAL_OR_UNKNOWN` — **ineligible** | Blocks offset fail-closed; redelivered on recovery | **Intentional ADR / existing design** |
| 3a | **Confirmed permanent rejection** (`401`/`403`/`404`/`409`/`410`/`422`, invalid ID, `NOT_FOUND`, `DELETED`, `UNAUTHORIZED`, non-allowed user) | `_authorized_conversation_status` → expected rejection; `_safe_edit(q, message)` → `mark_explicitly_ignored` (non-allowed → silent `_authorization_ignored`) | User sees explicit Arabic rejection (`"الشات مش موجود."`, `"مش مسموح..."`, or 4xx text); non-owner gets zero disclosure | None | `EXPLICITLY_IGNORED` (`processed_updates`) — **ack-eligible** | Offset advances normally; no permanent blocking | **Intentional ADR behavior** |
| 3b | **Telegram permanent or transient failure on `conv is None` error delivery** (`_safe_edit` raises `BadRequest`, `TimedOut`, etc.) | `_safe_edit` re-raises (anything except `"not modified"`) → `handle_processing_error` → `_classify_failure` | User does **not** see error text (spinner stopped via `q.answer()`); **no** false success shown | `log.error` (`type(exc).__name__`) | `FAILED_PERMANENT` (`update_failures`) — **ineligible** | Offset blocked (`test_stage4_f1` lines 330–374 explicitly requires `BadRequest` to raise & block) | **Intentional fail-closed contract** (protected by existing `test_stage4_f1` tests; `_classify_failure` TelegramError taxonomy is cross-handler) |
| 3c | **Malformed `conv` formatting fields** (`metrics` or `accumulated_token_usage` non-dict truthy value in `show_cost`; unhashable `execution_status` dict/list in `show_status`) | `format_cost` calls `.get()` without `isinstance(..., dict)`; `state_label` calls `STATE_LABELS.get()` with unhashable key → unhandled `AttributeError`/`TypeError` → `handle_processing_error` | Spinner stopped silently; **no output and no error notice shown to user** | `log.error` (`AttributeError`/`TypeError`) | `FAILED_PERMANENT` (`update_failures`) — **ineligible** | Permanent head-of-line offset deadlock on that conversation | **CONFIRMED IN-SCOPE DEFECT (`OPS01-D2`)** — safe to fix matching `_cost_dto` |
| 4 | **Timeout / ambiguous outcome** (OpenHands read timeout; Telegram `TimedOut` on `_edit_or_send` / `_safe_edit`) | OpenHands timeout → `ApiError(msg, None)` → `FAILED_TRANSIENT`. `_edit_or_send` `TimedOut` → `False` → `mark_display_failed` (`FAILED_TRANSIENT`). `_safe_edit` `TimedOut` → raises → `FAILED_PERMANENT` | On OpenHands timeout: sanitized error shown. On `_edit_or_send` timeout: spinner stops, **no user-visible error notice** (old message unchanged, no fake success) | `log.warning` (type only) / `log.error` | `FAILED_TRANSIENT` or `FAILED_PERMANENT` — **ineligible** | Blocks offset; redelivery executes; read-only so no duplicate external mutation | **Intentional / documented limitation** (see row 6) |
| 5 | **Repeated failure after bounded retries** | `OpenHandsClient` does 0 HTTP retries; `dedupe_update` retries transient DB via `_DEDUPE_RETRY_DELAYS`; `TelegramPoller` retries `getUpdates`/`deleteWebhook` with exponential backoff (`1s..30s`). Persistent update failure keeps `offset` behind head-of-line | Either sanitized error (on `conv is None`) or silent unchanged message (on `_edit_or_send` `False`) | Warning per poll/attempt | Remains ineligible (`FAILED_TRANSIENT`/`FAILED_PERMANENT`) — **no auto-skip / poison flag** | Head-of-line blocking persists until recovery or future §28.4 decision | **Intentional fail-closed / ADR §37 (poison §28.4 deferred)** |
| 6 | **Failure-notification delivery failure / silent display failure when `conv is not None` (`_edit_or_send` → `False`)** | `_edit_or_send` catches `TelegramError`/etc., logs type only, returns `False` (falls back to `send_long` **only** for `"too long"`, not `"Message to edit not found"`/`"Message can't be edited"`). Caller logs warning, calls `mark_display_failed`, returns normally | Spinner already stopped silently by `q.answer()`; user gets **zero visible failure notice**, though **no false success** is displayed | `log.warning("فشل عرض الشات (%s)")` + `log.warning("تعذّر عرض ...")` | `FAILED_TRANSIENT` (`update_failures`) — **ineligible** | Documented in `.agent/PROGRESS.md:129-132, 1396-1397` & `test_sw04_sw05`: adding extra `send_message`/alert changes behavior & risks spam on redelivery loops | **Documented limitation requiring Owner Decision** (do not invent alert/poison-bypass without approval) |
| 7 | **Process restart during/after operations** | `show_status`/`show_cost` create **no** outbox/creation/completion durable work. `processed_updates`, `update_failures`, and `acknowledgment_boundary` persist in SQLite. On restart `TelegramPoller.bootstrap()` deletes webhook with `drop_pending_updates=False` and resumes at `boundary + 1` (or `None`) | Previously failed/uncommitted updates are redelivered by Telegram (note `OPS01-D1` would cause expired `q.answer()` failure on restart redelivery unless fixed) | Bootstrap log | Persisted outcome preserved across restart; `update_is_processed=False` for failed updates | Safe restart recovery once `OPS01-D1` is fixed | **Depends on `OPS01-D1` fix** |

---

## 3. OPS-02: `SW-02` Evidence Search & Classification

- **Search commands executed across workspace:**
  - `grep -rnE "SW[-_ ]?0?2\b|sw[-_ ]?0?2\b" . --exclude-dir=__pycache__ --exclude-dir=.git --exclude-dir=node_modules`
  - `grep -rnE "SW[-_ ]?0?[0-9]+" bot/ tests/ docs/`
- **Observed facts:**
  - `0` matches for `SW-02` / `SW02` in `bot/`, `tests/`, `docs/` (including all 68 files under `docs/reviews/`, `docs/decisions/`, `docs/proposals/`), `automation/`, `tools/`, `src/`, `main.py`, `README.md`.
  - Contrast: `SW-01`, `SW-03`, `SW-04`, `SW-05`, `SW-06`, `SW-07`, `SW09` all have dedicated definitions, inline comments, and regression test suites (`tests/test_sw01*`, `tests/test_sw03*`, `tests/test_sw04_sw05*`, `tests/test_sw06*`, `tests/test_sw07*`, `tests/test_notifications_controls.py`).
  - All matches for `SW-02` exist solely in `.agent/PROGRESS.md` (`lines 56, 66, 71, 74, 134-141, 197-218, 1360, 1398, 1605, 1675, 1703-1721, 3053`), all of which are self-referential audit statements recording that the original task definition is absent from the repository and historical sources (`CLOSED_WITH_EXPLICIT_UNKNOWN — SOURCE REQUIRED`).
  - Local `.git` history and `.openhands/memory` are not present in this container.
- **OPS-02 Classification:** `UNTRACEABLE — SOURCE REQUIRED` (no code modified for `SW-02`).

---

## 4. OPS-01: Implemented Remediation & Regression Tests

### 4.1 In-Scope Fixes Applied (Existing Mechanisms Only)
1. **`OPS01-D1` — `bot/handlers.py` (`show_status` lines `1347-1350`, `show_cost` lines `1397-1400`):**
   - Wrapped `await q.answer()` in `try ... except Exception as exc:` with type-only logging (`log.warning("تعذّر الرد على الكولباك (%s)", type(exc).__name__)`), matching `send_reply_txt` (`lines 1119-1122`) and `notifications_toggle` (`OHB2-SW09`, `lines 865-868`).
   - Preserves `asyncio.CancelledError` propagation (`BaseException`) and prevents expired `callback_query` errors (`BadRequest("Query is too old...")`) or transient `TimedOut` during Telegram redelivery/restart recovery from crashing into `FAILED_PERMANENT` head-of-line deadlock.
2. **`OPS01-D2` — `bot/messages.py` (`state_label` lines `56-61`, `format_cost` lines `176-181`):**
   - Added `isinstance(state, str)` guard in `state_label` (after `state is None`) so unhashable upstream `execution_status` (`dict`/`list`) renders `"غير معروف"` instead of raising `TypeError`.
   - Added `isinstance(metrics, dict)` and `isinstance(raw_usage, dict)` guards in `format_cost` (matching `_cost_dto` in `bot/web/services.py:324-327`) so malformed upstream `metrics` / `accumulated_token_usage` do not raise `AttributeError` after `q.answer()` silently stops the spinner.

### 4.2 Focused Regression Tests Added
- Added `tests/test_plan05_status_cost_failure_visibility.py`:
  - `q.answer()` `BadRequest` / `TimedOut` continuation, type-only logging (no secret leakage), `CancelledError` non-swallowing.
  - E2E `TelegramPoller` redelivery recovery after `503` even when `answer_callback_query` expires (`BadRequest("Query is too old...")`).
  - `format_cost` / `state_label` malformed input unit tests and handler-level `show_cost` / `show_status` malformed payload tests.

### 4.3 Items Intentionally Not Changed (Existing Contracts / Owner-Decision Items)
- **`_edit_or_send` returning `False` on `conv is not None` (`show_status:1385`, `show_cost:1423`):** Remains silent to the user (`q.answer()` already ran; `mark_display_failed` records `FAILED_TRANSIENT` fail-closed; no false success). Sending an extra fallback `bot.send_message` is explicitly prohibited on `_edit_or_send` by `tests/test_sw04_sw05_authz_upstream_and_delivery.py:378-383`, risks chat spam on persistent redelivery loops, and is recorded as requiring an owner decision (`.agent/PROGRESS.md:129-132, 1396-1397`, `ADR §37`).
- **`_safe_edit` on `conv is None`:** Re-raises non-`"not modified"` `TelegramError`, which is explicitly asserted by `tests/test_stage4_f1_status_cost_operational_ack.py:330-374`.
- **`§28.4` poison-update bypass & `_classify_failure` global `TelegramError` taxonomy:** Out of scope.

---

## 5. Post-Edit Verification Ledger & Invariants Audit

| Check | Command | Outcome / Evidence | Notes |
|---|---|---|---|
| Python bytecode compile | `python3 -m compileall -q bot automation tools main.py tests` | **PASS** (exit `0`, `COMPILEALL_OK`) | Verified after all edits |
| Python AST parse | `ast.parse` over `*.py` | **PASS** (exit `0`, `AST_OK:165`) | Includes new test file |
| AST unused-import check | `ast.walk` on modified files | **PASS** (`unused_imports={}` for `handlers.py`, `messages.py`, `test_plan05_...`) | Static supplement only |
| Frontend tests | `node --test tests/frontend/*.test.js` | **PASS** (`280 pass / 0 fail`, exit `0`) | Unchanged baseline |
| Isolated stdlib behavioral verification | Ephemeral Python script with in-memory `telegram`/`httpx` stubs | **PASS** (`9/9` groups: normal success, `q.answer()` `BadRequest`/`TimedOut` + secret redaction, `CancelledError`, malformed `metrics`/`execution_status`, `5xx`/`429`/timeout/`/users/me` `503` → `FAILED_TRANSIENT`, `404`/`NOT_FOUND` → `EXPLICITLY_IGNORED`, `conv is None` `_safe_edit` `BadRequest` re-raise, `_edit_or_send` `False` → `FAILED_TRANSIENT`, `TelegramPoller.acknowledgment_boundary` recovery) | **Not real `pytest`**; uses lightweight stubs because `telegram`/`httpx` are not installed |
| Python test suite (`pytest`) | `python3 -m pytest -q` | **BLOCKED / UNVERIFIED** (exit `1`: `No module named pytest`) | Must run in full environment with `requirements-dev.txt` |
| Python lint (`pyflakes`) | `python3 -m pyflakes bot/ automation/ tools/ main.py tests/` | **BLOCKED / UNVERIFIED** (exit `1`: `No module named pyflakes`) | Same |
| SAST (`bandit`) | `python3 -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | **BLOCKED / UNVERIFIED** (exit `1`: `No module named bandit`) | Same |
| Dependency SCA (`pip_audit`) | `python3 -m pip_audit -r requirements-dev.txt` | **BLOCKED / UNVERIFIED** (exit `1`: `No module named pip_audit`) | Same |
| Independent review | Separate reviewer session | `INDEPENDENT_REVIEW_NOT_AVAILABLE` | Single-agent execution session |

### Preserved Architecture & Safety Invariants
- Single coordinated bot + ASGI process, single SQLite owner (`bot/db.py` schema untouched).
- Existing outbox and worker mechanisms only; **0** new workers, schedulers, daemons, processes, databases, or state owners.
- Polling acknowledgment semantics (`bot/polling.py`, `bot/update_outcomes.py`, `bot/db.py`), `concurrent_updates(True)` (`bot/app.py:86`), bounded retries, `MINI_APP_ENABLED=False` default (`bot/config.py:262`), and inactive Autopush preserved.
- No `exactly-once` Telegram delivery claim; no secrets logged or exposed.

---

## 6. Final Verdicts

- **OPS-01 Verdict:** `PASS_WITH_NOTES`
  - *Basis:* End-to-end investigation and matrix completed; confirmed in-scope defects `OPS01-D1` and `OPS01-D2` fixed minimally and verified with `compileall`, AST checks, and 9-group isolated stdlib behavioral verification; priority remains `Medium` (no false-success evidence). Caveats: real `pytest` (including `tests/test_plan05_status_cost_failure_visibility.py`), `pyflakes`, `bandit`, and `pip_audit` remain unverified in this stdlib-only container; `INDEPENDENT_REVIEW_NOT_AVAILABLE`; silent display failure on `_edit_or_send` returning `False` for `conv is not None` remains an owner-decision-gated item.
- **OPS-02 Verdict:** `UNTRACEABLE — SOURCE REQUIRED`
  - *Basis:* Zero occurrences in live code, tests, docs, or reviews outside self-referential audit records in `.agent/PROGRESS.md`; no code modified for `SW-02`.

