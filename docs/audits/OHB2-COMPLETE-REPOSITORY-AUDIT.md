# OHB2 Complete Technical Repository Audit

**Task ID:** `OHB2-COMPLETE-REPOSITORY-AUDIT-AND-REMEDIATION-MASTER-PLAN`  
**Audit Date:** 2026-11-17  
**Repository Baseline:** 328 files in `/app/applet` (read-only audit; 0 baseline files modified)  
**Scope Exclusion:** The Telegram Mini App subsystem (`bot/web/*`, `bot/web/static/*`, `tests/frontend/*`, `tests/test_miniapp_*.py`, `tests/test_real_http_miniapp_download.py`, `tests/_miniapp_helpers.py`, `docs/MINI_APP.md`, `mini_app_*` config fields) is **`EXCLUDED_MINI_APP`** and excluded from remediation scope.

---

## 1. Architecture & Runtime Topology Audit

OpenHandBot is a single-process Python 3.11+ asyncio application (`main.py` -> `bot/bootstrap.py` -> `bot/app.py`) combining:
- **Telegram Long Polling (`bot/polling.py`):** Replaced python-telegram-bot's built-in `Updater` (`updater(None)`) with `TelegramPoller`, committing monotonic acknowledgment boundaries (`commit_batch_outcomes`) to SQLite before advancing `getUpdates(offset=B+1)`.
- **Telegram Handlers (`bot/handlers.py`, `bot/keyboards.py`, `bot/messages.py`):** Interactive conversation routing (`reply`, `newchat`, `route`, `reposearch`), reply rendering/export, workspace file preview, deletion confirmation, manual outbox reconciliation (`/outbox_*`), and local attachment intake (`P0 A0–A4`).
- **Single-Owner Background Workers (`bot/outbox.py`, `bot/watcher.py`, `bot/notifier.py`):**
  - `OutboxWorker`: Claims mature (`>= 1.5s` `GROUP_WINDOW`) pending prompts and delivers to OpenHands `POST /conversations/{id}/messages`.
  - `CreationWorker`: Creates new OpenHands conversations (`POST /conversations` + `wait_for_start`), then feeds `CompletionWorker`.
  - `CompletionWorker`: Retries local post-delivery side effects (Telegram confirmation notice + watch setup) from `completion_pending`.
  - `Watcher` & `Notifier`: Poll OpenHands `/conversations/search`, normalize status via `get_status()`, coordinate ownership so watched conversations notify once via `Watcher` while unwatched conversations notify globally via `Notifier`, persist `notification_inbox` and `RetryAfter` deadlines, and run throttled `OpportunisticSweeper` ticks (`bot/attachments.py`).
- **Shared SQLite Persistence (`bot/db.py`, 5,308 lines, 19 tables):** Single connection per process (`WAL`, `synchronous=NORMAL`, `foreign_keys=ON`, `busy_timeout=5000`, `run_startup_maintenance()` fail-closed integrity gate).
- **Optional Embedded Mini App (`bot/web/runner.py`, `bot/web/app.py` — `EXCLUDED_MINI_APP`):** Disabled by default (`MINI_APP_ENABLED=0`); shares the single `Database` instance inside the same asyncio event loop when enabled.
- **Unwired Co-Existing Scaffold (`NON_RUNTIME`):** Root `package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, `metadata.json`, `src/*`, and `bun.lock` constitute an empty React 19 + Vite template left from workspace initialization (`DEF-018`).

---

## 2. State Machines, Concurrency & Transaction Safety

### 2.1 Critical Failure: Local Attachment Intake State Machine Traps All Normal Prompting (`DEF-001`)
Despite `.agent/PROGRESS.md` recording `P0` as `BLOCKED / DEFERRED BY EXPLICIT PRODUCT DECISION` (`Option D`), Phases `A0–A4` are **compiled into live runtime and enabled by default** (`bot/config.py:43,315-317`: `attachment_document_intake_enabled = True`). Because Stage B1/B2 remote upload is unimplemented:
1. Sending **any document** creates a batch in `attachment_batches`.
2. Sending **any text** within 15 minutes transitions it to `intent_recorded` (`bot/db.py:1630`), which `AttachmentReaper` intentionally skips (`bot/attachments.py:1095-1102`) and no worker consumes -> permanent `AttachmentRoutingState.UNRESOLVED` across **all** conversations for that `telegram_id`.
3. Letting the batch expire after 15 minutes moves it to `expired` (`TERMINAL`). Because `classify_attachment_routing` (`bot/db.py:1557-1569`) queries `has_terminal_attachment_batch(telegram_id)` globally and rejects any unmapped message as `TERMINAL_UNPROVEN` (`D-34`), **every unrelated prompt in any other conversation is permanently rejected forever**, and `/cancel` (`bot/handlers.py:2295`) only clears `user_state`. Even setting `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=0` afterward does **not** clear `handle_text:2245`!

### 2.2 `OutboxWorker` / `CreationWorker` / `CompletionWorker`
- **`OutboxWorker` & `CompletionWorker`:** Strong `at-most-once` invariants (`PRE-CAS` rollback vs `POST-CAS` `OUTBOX_SENDING` -> `OUTBOX_UNKNOWN`, tombstone witness enforcement before claim and before `sending` CAS, atomic `sent` + `completion_pending` commit).
- **Latent Gaps Found:**
  - `CreationWorker` resumed `job.task_id` path (`bot/outbox.py:733-746`) lacks `CancelledError` and unexpected-`Exception` handlers (contrast `792-806` & `479`), stranding `creation_jobs` in `CREATION_CLAIMED` on unexpected client errors until restart (`DEF-012`).
  - `deliver_outbox(outbox_id)` (`bot/outbox.py:210-224`) calls `claim_outbox(now_iso())` with no `outbox_id` filter and no `mature_before` window (`DEF-008`).

### 2.3 `Watcher` & `Notifier`
- Transition deduplication (`note_transition`, `upsert_notification_state`, `set_owner_delivery` coordination) is well-structured against stale snapshots and double alerts.
- **Bug Found (`DEF-007`):** Both `Watcher.tick` (`bot/watcher.py:215-221`) and `Notifier._process` (`bot/notifier.py:522-528`) log `"هيتخطّى"` ("will skip") on `clear_retry_not_before` DB failure, yet miss `continue`/`return` and immediately fall through to notify anyway.

### 2.4 Attachment Staging Quota Concurrency (`DEF-011`)
- `_get_download_semaphore()` bounds simultaneous Telegram downloads to 4 (`bot/handlers.py:1714`), yet `StagingStore.store` (`bot/attachments.py:699-735`) checks quota without cross-stream byte reservation (dormant while aggregate caps default to `None`, races if configured) and executes synchronous `os.fsync` writes directly on the asyncio event loop.

---

## 3. Polling & Telegram ACK Reliability Audit (`Stages 2–4`)

`TelegramPoller` (`bot/polling.py`) & `update_outcomes.py` enforce fail-closed ACK: `ALLOWED_UPDATES = ("message", "callback_query")`, `deleteWebhook(drop_pending_updates=False)`, and monotonic `commit_batch_outcomes` advancing `offset = boundary + 1` only across contiguous `_ACK_ELIGIBLE` updates (`DURABLE_COMPLETED`, `DURABLE_INTENT_RECORDED`, `EXPLICITLY_IGNORED`, `REJECTED_INELIGIBLE`, `AMBIGUOUS_EXTERNAL`, `DISPLAY_FAILED`, `DUPLICATE_COMPLETED`).

Four material defects weaken this layer:
1. **Unconditional `FAILED_PERMANENT` Head-of-Line Deadlock & Misclassification (`DEF-002`):** `FAILED_PERMANENT` blocks `acknowledgment_boundary()` forever with no ADR §28.4 quarantine/skip mechanism implemented, while `_classify_failure` (`bot/handlers.py:477-495`) misclassifies `telegram.error.RetryAfter`/`TimedOut`/`NetworkError`, `asyncio.TimeoutError`, and `OSError` as `FAILED_PERMANENT`.
2. **24/28 Unwrapped `q.answer()` Calls (`DEF-005`):** Stale inline buttons (`>30–60s` after restart backlog) or transient Telegram timeouts raise inside `await q.answer()`, aborting handlers before outcome recording and triggering `DEF-002` permanent polling lock.
3. **Missing Outcomes & `reposearch` Error Swallowing (`DEF-003`):** `outbox_mark_sent` (`bot/handlers.py:2795-2798`) returns without `mark_explicitly_ignored` on concurrent resolution race (`outcome=None` -> ack block); `handle_text` `reposearch` (`2275-2283`) consumes `awaiting` even when `_show_repos` fails with 5xx and leaves `outcome=None` on expiry race (`consume == False`).
4. **Incomplete `Stage4-F1` Operational Propagation (`DEF-004`):** `reply_prompt`, `export_conversation`, `send_reply_txt`, `watch_conversation`, `delete_conversation_prompt`, `delete_conversation_confirm`, `list_conversations`, and `_show_repos` still swallow upstream `5xx`/`429` into `EXPLICITLY_IGNORED` instead of `_authorized_conversation_status` + `OPERATIONAL_FAILURE`, and `export_conversation`/`show_file` lack `try/except TelegramError` around `send_document`.
5. **Intra-Batch Serialization (`DEF-006`):** `TelegramPoller.process_updates` awaits `dispatch_and_wait` sequentially (`bot/polling.py:161-162`), defeating `concurrent_updates(True)` in `bot/app.py:75-87` within multi-update batches.

---

## 4. Security, Authorization & Input-Bounds Audit

- **Secrets & Redaction (`bot/errors.py`, `bot/bootstrap.py`, `automation/autopush/main.py`):** Token, `sk-`/`oh_` API key, and Bearer redaction in `redact()` is thorough; `bootstrap.py` blocks logging secrets at startup; `autopush/main.py` uses `GIT_ASKPASS` and sanitized argv (`0` Bandit High findings reported historically).
- **Owner Authorization & Fail-Closed Ownership:**
  - `Config.is_allowed()` strictly compares `telegram_id` (`bot/config.py`).
  - `FileService` and `_authorized_conversation*` enforce `created_by_user_id == owner` + `is_deleted` tombstones before returning metadata, files, exports, or setting `reply` state.
- **Path Traversal & Size Bounds (`bot/files.py`, `bot/attachments.py`):** Strict `is_safe_workspace_path` validation, sanitized attachment display names, opaque UUID/hex `staging_token`, `O_NOFOLLOW`/`lstat` symlink rejection, denied executable/archive extensions + magic bytes, and hard streaming download caps (`3 MiB` attachment / `25 MiB` zip / `1 MiB` preview / `50 MiB` `.txt`).
- **Two Boundary/Security Observations:**
  - **Valid 56–64 Char Conversation IDs Crash Inline Keyboards (`DEF-010`):** `MAX_CONVERSATION_ID_LEN = 64` exceeds `64 - len("deleteok:")` (`55`), throwing `ValueError` in `kb._btn` -> polling failure.
  - **24 Bare `q.answer()` Calls Run Before `_allowed()` (`DEF-005`):** An unauthorized user clicking a stale button triggers Telegram's `answerCallbackQuery` error before `_allowed()` checks ownership.
  - **Stage B1/B2 SSRF & Credential Risk (`DEF-015`):** Properly prevented from shipping by deferring Stage B until scoped token + origin allowlist gates exist.

---

## 5. Operations, Hosting, CI & Documentation Audit

- **GitHub Workflows (`.github/workflows/`):**
  - `ci.yml`: Clean split between `python` (`3.11`, `3.13`: `pytest`, `pyflakes`, `bandit`, `pip_audit`) and `frontend` (`Node 22`: `node --test`). Note: CI was **NOT** run inside this local container (`DEF-019`).
  - `enzonic-sftp-readonly-check.yml`: `workflow_dispatch`-only, `permissions: {}`, pinned fingerprint check + `trap` key cleanup, strict SFTP read-only (`pwd`, `ls -la`). Untested against live Enzonic (`DEF-016`).
- **Hosting Qualification (`DEF-016`):** Both free hosting qualification (`HOST-01`/`HOST-02`) and Enzonic SQLite persistence canary (`H1` via `tools/katabump-sqlite-canary/canary.py`) remain unverified on live production hosting.
- **Documentation Drift (`DEF-017`):**
  - `docs/ZERO_TOUCH_STARTUP.md:242` directly contradicts `bot/deletion.py` by stating deletion does NOT delete remote OpenHands conversations, and §1 contradicts `/ready`+`/status`.
  - `docs/OPERATIONS_RUNBOOK.md` omits 13 of 19 SQLite tables and 13 env vars (`ATTACHMENT_DOCUMENT_INTAKE_ENABLED` + `MINI_APP_*`), and omits `notification_inbox` recovery.
  - `README.md:70-89` omits `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` (present in `.env.example`) and `MINI_APP_TRUSTED_PROXIES`.
  - `docs/API_NOTES.md:81` cites OpenAPI `1.68.1` vs `1.79.0` in `bot/openhands_client.py:344` vs `1.87.1` in ADR.

---

## 6. Verification Status & Honest Environment Accounting

| Check | Status in Current Container | Evidence |
|---|---|---|
| Python AST Syntax (`165/165` `.py` files) | **PASS** (`0` syntax errors) | Executed locally via Python 3.10.12 `ast.parse` |
| Node Frontend Suite (`tests/frontend/*.test.js`) | **PASS** (`280 pass / 0 fail`) | Executed locally via `node --test tests/frontend/*.test.js` |
| `python -m pytest -q` | **`BLOCKED / NOT_RUN`** | Missing Python >= 3.11 and `requirements-dev.txt` packages (`pytest`, `telegram`, `httpx`, `starlette`, `uvicorn`, `dotenv`, `anyio`) in container |
| `python -m pyflakes ...` | **`BLOCKED / NOT_RUN`** | `pyflakes` not installed in container |
| `python -m bandit ...` | **`BLOCKED / NOT_RUN`** | `bandit` not installed in container |
| `python -m pip_audit ...` | **`BLOCKED / NOT_RUN`** | `pip_audit` not installed in container |
| Live Enzonic SFTP & `H1` Canary | **`UNVERIFIED`** | No live server credentials / outbound probe prohibited |

Historical CI/venv test counts recorded in `docs/reviews/OHB2-PLAN15-OPERATIONAL-FAILURE-VISIBILITY-REPORT.md` and `.agent/PROGRESS.md` are noted strictly as historical document records, **not** as live local execution.

---

## 7. Mini App Exclusion Boundary Verification

All Mini App implementation, test, and documentation files remain untouched (`EXCLUDED_MINI_APP`):
- `bot/web/__init__.py`, `app.py`, `clientip.py`, `download.py`, `initdata.py`, `ratelimit.py`, `runner.py`, `services.py`, `sessions.py`
- `bot/web/static/app.js`, `attachments.js`, `copy.js`, `cost.js`, `export.js`, `files.js`, `inbox.js`, `index.html`, `jobs.js`, `ops.js`, `styles.css`
- `tests/frontend/*` (24 files), `tests/test_miniapp_*.py` (15 files), `tests/test_real_http_miniapp_download.py`, `tests/_miniapp_helpers.py`
- `docs/MINI_APP.md`
- `Config.mini_app_*` fields in `bot/config.py`

**Zero** remediation work packages in `OHB2-REMEDIATION-MASTER-PLAN.md` schedule changes to any Mini App file; cross-surface `DEF-014` is explicitly marked `BLOCKED_BY_EXCLUDED_MINI_APP`.
