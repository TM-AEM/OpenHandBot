# OHB2 Dependency-Aware Remediation Master Plan

**Audit Task ID:** `OHB2-COMPLETE-REPOSITORY-AUDIT-AND-REMEDIATION-MASTER-PLAN`  
**Audit Date:** 2026-11-17  
**Planning Horizon:** Phase 0 (Emergency Stop-the-Bleeding) through Phase 4 (Operational, Documentation, & External Release Gates)  
**Absolute Scope Exclusion:** **0 Mini App files** (`bot/web/*`, `bot/web/static/*`, `tests/frontend/*`, `tests/test_miniapp_*.py`, `tests/test_real_http_miniapp_download.py`, `tests/_miniapp_helpers.py`, `docs/MINI_APP.md`, `mini_app_*` config fields) appear in any remediation work package. Any issue requiring Mini App code edits (`DEF-014`) is explicitly **`BLOCKED_BY_EXCLUDED_MINI_APP`**.

---

## 1. Execution Phases & Dependency DAG

```
Phase 0 (Emergency Unblock — MUST SHIP FIRST)
  └─► WP-01 [DEF-001, DEF-011, DEF-015] Stop Owner Brick & Add Batch Rescue/Safe Default

Phase 1 (Polling Deadlock & Outcome Integrity — Core Bot Availability)
  ├─► WP-02 [DEF-005] Harden All Callback Query Answers (_safe_answer + auth order)
  ├─► WP-03 [DEF-003, DEF-004] Complete Handler Outcome & Stage4-F1 Failure Propagation
  └─► WP-04 [DEF-002] Fix _classify_failure & Implement ADR §28.4 Poison Quarantine
        (WP-02 & WP-03 should precede/co-ship with WP-04 so transient errors stop locking boundary)

Phase 2 (Workers, Concurrency, & UI Consistency)
  ├─► WP-05 [DEF-007, DEF-008, DEF-012] Watcher/Notifier Skip Control Flow, CreationWorker Resumed Errors & deliver_outbox Contract
  ├─► WP-06 [DEF-009, DEF-010] Normalize Status via get_status() & Fix 64-Byte callback_data Overflow
  └─► WP-07 [DEF-006, DEF-011, DEF-013] Poller Batch Concurrency Alignment, Quota Reservation Lock & Atomic Expired-Awaiting Clear
        (WP-07 depends on WP-01 for attachment concurrency safety)

Phase 3 (Documentation, Startup Guard, & Verification Gates)
  ├─► WP-08 [DEF-017, DEF-018] Synchronize Runbooks/Startup Docs & Manifest Parity Tests
  └─► WP-09 [DEF-019] Execute Full CI Verification Matrix (Python 3.11/3.13 + Frontend + SAST/SCA)
        (WP-09 gates release of WP-01 .. WP-08)

Phase 4 (External / Infrastructure / Product-Decision Gates)
  └─► WP-10 [DEF-015, DEF-016] Enzonic SFTP Verification, H1 SQLite Persistence Canary & P0 Reopen Gate
```

---

## 2. Work Packages

### WP-01 — Emergency Stop-the-Bleeding: Resolve "Owner Brick" Normal Text Self-DoS

- **Priority:** `P0 — BLOCKER (Emergency)`
- **Addresses:** `DEF-001`, `DEF-011` (UX copy), `DEF-015` (surface boundary)
- **Exact Target Files:**
  - `bot/config.py` (`load_config` / `Config` default for `attachment_document_intake_enabled`)
  - `.env.example` (document safe default `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=0`)
  - `bot/handlers.py` (`handle_text`, `_handle_accompanying_text`, `cancel_route`, `cancel_route_button`, `ATTACHMENT_ACCEPTED_TEXT`)
  - `bot/db.py` (`classify_attachment_routing`, add explicit owner-scoped batch abandonment/close helper)
  - `bot/attachments.py` (`AttachmentReaper` / staging cleanup when owner abandons batch)
  - `tests/test_repair_plan_02_life03_intake_kill_switch.py`, `tests/test_attachment_batch_state_routing_f1_1a.py`, `tests/test_attachment_terminal_routing_remediation.py`, new E2E test `tests/test_def001_prompt_unbrick.py`
- **Root Cause:** `attachment_document_intake_enabled` defaults to `True` with no Stage B remote dispatcher; `_handle_accompanying_text` runs unconditionally in `handle_text` across all conversations (`telegram_id`-global) and treats both `intent_recorded` (`UNRESOLVED`) and `expired` (`TERMINAL_UNPROVEN`) as permanent text rejections with no cancel/reset escape hatch.
- **Concrete Changes:**
  1. Change default `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` to `False` in `bot/config.py` and `.env.example` while remote upload (`Stage B1/B2`) remains unimplemented (`DEF-015`).
  2. When `config.attachment_document_intake_enabled` is `False` AND no active `pending` batch exists, bypass `_handle_accompanying_text` in `handle_text` (or auto-close stale local-only batches cleanly so already-affected owners are unbricked on upgrade/config toggle).
  3. Extend `/cancel` (`cancel_route` / `cancel_route_button`) — or add `/cancel` batch abandonment alongside explicit owner confirmation — so owners can explicitly discard stuck `pending` / `intent_recorded` batches (`rejected` + staging unlink).
  4. Fix D-34 `TERMINAL_UNPROVEN` (`bot/db.py:1557-1569`) so historical terminal batches (`expired`, `delivered`, `rejected`, `failed`) never block *new* unrelated messages (keep `TERMINAL_ASSOCIATED` dedupe/fail-closed strictly for messages whose `(telegram_id, chat_id, message_id)` is recorded in `attachment_message_identity`, OR require owner confirmation to clear). *(Note: Check/update D-34 owner decision record alongside code change per `AGENTS.md` §14!)*
  5. Update `ATTACHMENT_ACCEPTED_TEXT` to disclose honestly when intake is enabled that remote upload is offline / local-only staging.
- **Dependencies:** Owner approval required per `AGENTS.md` §14 if modifying D-32/D-34 fail-closed semantics; changing default flag to `False` + `/cancel` rescue + `attachment_message_identity`-scoped terminal check preserves safety invariants.
- **Risks:** Existing P0 A3 tests (`test_attachment_terminal_routing_remediation.py`) explicitly assert `TERMINAL_UNPROVEN` blocks subsequent unmapped messages! Must reconcile D-34 decision doc + update those tests explicitly under owner sign-off, rather than silently breaking tests.
- **Required Tests:** Multi-turn E2E tests covering: (a) upload doc -> send text -> send normal prompt in Conv B (unbricked); (b) upload doc -> let batch expire (>15m) -> send prompt in Conv B (succeeds); (c) upload doc -> `/cancel` -> staging files swept & normal prompting works; (d) `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=0` unblocks previously affected owner.
- **Acceptance Criteria:** Sending a document never permanently disables normal Telegram text prompting across restarts or conversations; default fresh `.env` safely rejects document intake with clear message until Stage B exists.
- **Independent Review Requirement:** Required (hostile review of D-34 / A3 decision impact and staging cleanup safety).

---

### WP-02 — Harden All Telegram Callback Query Answers

- **Priority:** `P1 — High`
- **Addresses:** `DEF-005`
- **Exact Target Files:**
  - `bot/handlers.py` (all 24 unwrapped `.answer(...)` sites + 4 existing `try/except` blocks)
  - `tests/test_handlers.py` (new parameterized callback resilience tests)
- **Root Cause:** 24 of 28 `q.answer()` call sites in `bot/handlers.py` lack `try/except`, causing stale callbacks (`BadRequest: Query is too old`) or transient `TimedOut`/`RetryAfter` to raise unhandled exceptions -> `FAILED_PERMANENT` -> polling freeze.
- **Concrete Changes:**
  1. Introduce `async def _safe_answer(q, text=None, *, show_alert: bool = False) -> None` in `bot/handlers.py` wrapping `await q.answer(text=text, show_alert=show_alert)` in `try/except TelegramError` (logging `type(exc).__name__` at `WARNING`).
  2. Replace all 28 `.answer(...)` calls across `bot/handlers.py` with `await _safe_answer(q, ...)`.
  3. Ensure authorization check (`_allowed`) runs consistently *before* any UI edit or side effect (keeping safe `_safe_answer` silent/non-blocking).
- **Dependencies:** None.
- **Risks:** Swallowing non-Telegram `BaseException` (must NOT catch `asyncio.CancelledError`). Restrict `except` to `(TelegramError, TimeoutError, OSError)` or explicit `Exception` excluding `CancelledError`.
- **Required Tests:** Parameterized test exercising every `CallbackQueryHandler` in `bot/app.py` with `q.answer` raising `BadRequest("Query is too old")` and `TimedOut`, asserting expected handler logic + durable outcome still commit.
- **Acceptance Criteria:** 0 bare `await q.answer(` calls remain in `bot/handlers.py`; stale callbacks never cause `FAILED_PERMANENT` or ack blocks.
- **Independent Review Requirement:** Optional (standard peer/diff review).

---

### WP-03 — Complete Handler Outcome Coverage & `Stage4-F1` Operational Failure Propagation

- **Priority:** `P1 — High`
- **Addresses:** `DEF-003`, `DEF-004`
- **Exact Target Files:**
  - `bot/handlers.py` (`outbox_mark_sent:2791-2804`, `handle_text:2275-2283`, `_send_prompt:2351-2354`, `_start_new_chat:2534-2536`, `_show_repos:2434-2469`, `list_conversations:905-918`, `send_reply_txt:1129-1133`, `watch_conversation:1206-1212`, `delete_conversation_prompt:1276-1282`, `delete_conversation_confirm:1307-1318`, `export_conversation:1449-1468`, `show_file:1567`, `reply_prompt:1585-1591`)
  - `tests/test_stage4_f1_status_cost_operational_ack.py`, `tests/test_manual_polling_handler_outcome_coverage.py`, `tests/test_sw07_api_handler_failure_propagation.py`
- **Root Cause:** Partial rollout of `Stage4-F1` left 6 `_authorized_conversation` callers and 2 listing paths swallowing `5xx`/`429` into `EXPLICITLY_IGNORED`, left `outbox_mark_sent` racing `status_now == final` without an outcome commit, consumed `reposearch` on failed upstream calls, and left `send_document` unguarded in `export_conversation`/`show_file`.
- **Concrete Changes:**
  1. In `outbox_mark_sent` (`2795-2799`), add `mark_explicitly_ignored(update, context)`.
  2. In `_send_prompt`, `_start_new_chat`, and `handle_text` (`reposearch`), explicitly handle `consume_one_shot_awaiting(...) == False` by recording `mark_explicitly_ignored` (never `outcome=None`).
  3. Migrate `reply_prompt`, `watch_conversation`, `delete_conversation_prompt`, `delete_conversation_confirm`, `export_conversation`, `send_reply_txt`, and `_show_repos` / `list_conversations` to `_authorized_conversation_status` / `_raise_if_operational_api_failure` so `5xx`/`429`/network failures record `OPERATIONAL_FAILURE` (or `FAILED_TRANSIENT`) instead of `EXPLICITLY_IGNORED`, while `4xx`/deleted/unauthorized stay `EXPLICITLY_IGNORED`.
  4. Do NOT call `consume_one_shot_awaiting` in `reposearch` if `_show_repos` raised an operational `ApiError`.
  5. Guard `bot.send_document` in `export_conversation` and `show_file` consistently with `mark_display_failed` or transient `TelegramError` classification (`WP-04`).
- **Dependencies:** Coordinates closely with `WP-04` (`_classify_failure`).
- **Risks:** Blocking Telegram polling boundary on transient `5xx` during read menus (`list_conversations`) if OpenHands is down for hours — verify consistency with ADR §30 / `WP-04` before flipping `list_conversations`.
- **Required Tests:** Expand `test_stage4_f1` & outcome coverage matrix across all 13 modified handlers/branches (`503` vs `404` vs race `False`).
- **Acceptance Criteria:** Zero branches in `bot/handlers.py` can return normally from a matched update with `db.update_outcome(uid) is None`; all mutation/auth handlers propagate `5xx`/`429`.
- **Independent Review Requirement:** Required (adversarial review of outcome state transitions and ADR alignment).

---

### WP-04 — Fix `_classify_failure` & Implement ADR §28.4 Poison-Update Quarantine

- **Priority:** `P1 — High`
- **Addresses:** `DEF-002`
- **Exact Target Files:**
  - `bot/handlers.py:477-495` (`_classify_failure`), `bot/handlers.py:1150-1154` (`send_reply_txt`)
  - `bot/update_outcomes.py`, `bot/db.py`, `bot/polling.py`, `bot/app.py` (ADR §28.4 quarantine/skip or bounded dead-letter outcome)
  - `tests/test_stage2_custom_polling.py`, `tests/test_stage2_high_ack_blocking_fix.py`, new `tests/test_poison_update_quarantine.py`
- **Root Cause:** `_classify_failure` classifies `telegram.error.RetryAfter`, `TimedOut`, `NetworkError`, `asyncio.TimeoutError`, and `OSError` as `FAILED_PERMANENT`, and `FAILED_PERMANENT` has no escape mechanism from head-of-line offset deadlock.
- **Concrete Changes:**
  1. Update `_classify_failure` (`bot/handlers.py:477-495`) to classify `telegram.error.RetryAfter`, `TimedOut`, `NetworkError`, `asyncio.TimeoutError`, `httpx.TransportError`, and `OSError` as `FAILED_TRANSIENT`.
  2. Implement ADR §28.4 manual poison quarantine/skip: add durable `poison_acknowledged` (or `SKIPPED_POISON`) outcome + `/updates_status` and `/updates_skip <update_id> confirm` owner commands (or explicit operator-documented policy for deterministic terminal non-retryables like `TextDocumentTooLargeError`).
- **Dependencies:** Benefits from `WP-02` & `WP-03` eliminating accidental `BadRequest`/`outcome=None` triggers first.
- **Risks:** Auto-advancing on genuine transient failures must NEVER happen (`fail-closed` invariant); manual `/updates_skip` must require explicit `confirm` and log `update_id` clearly.
- **Required Tests:** Classifier unit tests for `RetryAfter`/`TimedOut`/`NetworkError`/`BadRequest`; polling tests verifying `/updates_skip` advances wedged boundary while unskipped `FAILED_PERMANENT` / `FAILED_TRANSIENT` keeps failing closed.
- **Acceptance Criteria:** Transient Telegram network errors never become `FAILED_PERMANENT`; operators can inspect and safely unblock a genuine poison update without editing SQLite manually.
- **Independent Review Requirement:** Required (strict ADR §28.4 & ACK invariant audit).

---

### WP-05 — Worker Control-Flow & `deliver_outbox` / `CreationWorker` Hardening

- **Priority:** `P2 — Medium`
- **Addresses:** `DEF-007`, `DEF-008`, `DEF-012`
- **Exact Target Files:**
  - `bot/watcher.py:215-221` (add `continue`)
  - `bot/notifier.py:522-528` (add `return`)
  - `bot/outbox.py:733-746` (add `CancelledError` & unexpected `Exception` handling in `if job.task_id:`), `bot/outbox.py:210-224` (`deliver_outbox`), `bot/db.py` (`claim_outbox_by_id` if kept)
  - `tests/test_watcher.py`, `tests/test_notifier.py`, `tests/test_creation.py`, `tests/test_outbox_concurrency_28c.py`
- **Root Cause:** Missing `continue`/`return` after `clear_retry_not_before` failure; asymmetric exception handling in resumed `task_id` `wait_for_start`; `deliver_outbox(outbox_id)` ignores `outbox_id` and `mature_before`.
- **Concrete Changes:**
  1. Add `continue` in `bot/watcher.py:221` and `return` in `bot/notifier.py:528`.
  2. Mirror `except asyncio.CancelledError` and `except Exception` fallback (`{CREATION_CLAIMED, CREATION_STARTING}` -> `CREATION_UNKNOWN` + notice) on `wait_for_start` in `bot/outbox.py:733-746` and `792-806`.
  3. Update `deliver_outbox(outbox_id)` to atomically claim *specifically* `outbox_id` (`db.claim_outbox_by_id(outbox_id, now_iso())`), or remove dead production export if tests migrate to `OutboxWorker`.
- **Dependencies:** None.
- **Risks:** `deliver_outbox` changes might require updating `tests/test_outbox_concurrency_28c.py` if signature/behavior assumptions differ — verify existing tests expect claiming *that* `outbox_id`.
- **Required Tests:** Inject `sqlite3.OperationalError` into `clear_retry_not_before`; simulate `RuntimeError`/`CancelledError` in resumed `wait_for_start`; test `deliver_outbox` with 2 rows verifying target-row isolation.
- **Acceptance Criteria:** Logged skips actually skip; resumed creation jobs never strand in `CREATION_CLAIMED`; `deliver_outbox(id)` only ever claims `id`.
- **Independent Review Requirement:** Optional (standard review).

---

### WP-06 — UI Status Normalization (`get_status`) & 64-Byte `callback_data` Safety

- **Priority:** `P2 — Medium`
- **Addresses:** `DEF-009`, `DEF-010`
- **Exact Target Files:**
  - `bot/messages.py:105, 138` (use `get_status(conv)`)
  - `bot/keyboards.py:113` (use `get_status(conv)`), `bot/keyboards.py:9-16, 94-215` (short-token callback resolution for `cid` > ~45 bytes)
  - `bot/handlers.py:1377` (use `get_status(conv)`), plus callback ID resolver helper
  - `bot/db.py` (optional `callback_refs` table if persistent short-tokens chosen)
  - `tests/test_messages.py`, `tests/test_keyboards.py`, `tests/test_handlers.py`
- **Root Cause:** UI formatters pass raw `conv.get("execution_status")` bypassing `get_status(conv)`, and `callback_data` concatenates prefixes (`deleteok:`, `files:...`) with 64-char valid `conversation_id`s.
- **Concrete Changes:**
  1. Replace `conv.get("execution_status")` with `get_status(conv)` in `format_conversation`, `format_conversation_view`, `conversations_menu`, and `show_status` (preserving `"غير معروف"` fallback if dict has neither field).
  2. Add short opaque callback token resolver (e.g., deterministic 12-char base64/hex DB ref `r:<short_id>` stored in SQLite `callback_refs` when `len(cid) > 44`, or always use short ref when needed), keeping inline payloads `<= 64` bytes for all `MAX_CONVERSATION_ID_LEN = 64` IDs.
- **Dependencies:** None (additive SQLite table if persistent refs used; zero Mini App impact).
- **Risks:** Watch out for `test_messages.py`/`test_keyboards.py` assertions expecting specific default status when `execution_status=None` (`get_status({})` returns `"unknown"` -> `STATE_LABELS["unknown"] == "غير معروف"`, whereas `state_label(None)` returns `"مستني"`; handle `execution_status is None and not sandbox_error` carefully to preserve exact existing contract!).
- **Required Tests:** Test 64-char `conversation_id` across all keyboards & callback dispatchers; test uppercase `FINISHED` and `sandbox_status="ERROR"`/`"MISSING"` across `format_conversation`, `format_conversation_view`, `conversations_menu`, and `show_status`.
- **Acceptance Criteria:** Valid 64-char IDs never raise `ValueError` in `keyboards.py`; UI status matches Watcher/Notifier `SANDBOX_ERROR` everywhere.
- **Independent Review Requirement:** Optional (verify backward compatibility of `state_label(None)` behavior).

---

### WP-07 — Poller Batch Concurrency Alignment, Quota Reservation Lock, & Awaiting Atomicity

- **Priority:** `P2 — Medium`
- **Addresses:** `DEF-006`, `DEF-011` (concurrency lock + sync I/O), `DEF-013`
- **Exact Target Files:**
  - `bot/polling.py:155-178` (`process_updates` / `dispatch_and_wait`)
  - `bot/attachments.py:646-760` (reservation accounting / `asyncio.to_thread` disk write if intake enabled)
  - `bot/handlers.py:2253-2261` (atomic expired-awaiting clear + `EXPLICITLY_IGNORED`)
  - `bot/db.py` (atomic `clear_expired_awaiting_with_outcome`)
  - `tests/test_stage2_custom_polling.py`, `tests/test_repair_plan_01_resource_staging.py`, `tests/test_one_shot_awaiting_atomicity.py`
- **Root Cause:** `TelegramPoller.process_updates` awaits each update one-by-one inside a batch; `StagingStore.store` lacks cross-download byte/count reservations; `handle_text` runs 2 non-atomic commits on expired awaiting state.
- **Concrete Changes:**
  1. Either enqueue all batch updates into `application.update_queue` and `await update_queue.join()` once per batch (after ensuring per-user state locks/atomic DB ops) OR document intentional batch serialization and remove contradictory concurrency rationale in `bot/app.py:75-87`.
  2. Add explicit atomic `clear_awaiting_and_record_outcome(...)` in `bot/db.py` for `handle_text:2253-2261`.
  3. Add thread/async reservation guard around `StagingStore.store` quota checks & offload blocking `os.fsync` writes via `asyncio.to_thread` when attachment staging runs.
- **Dependencies:** **Must execute after `WP-01`** if parallel batch updates can run concurrently for the same user.
- **Risks:** Parallelizing batch updates increases SQLite concurrent write contention (`SQLITE_BUSY`) and requires strict per-user serialization for `user_state`/`attachment_batches`. Test under concurrent load!
- **Required Tests:** Multi-update timing isolation test; 4-way concurrent quota race test; expired-awaiting crash-mid-reply test.
- **Acceptance Criteria:** Batch processing latency and concurrency match `bot/app.py` contract; concurrent attachment quota cannot overshoot; expired awaiting commits atomically.
- **Independent Review Requirement:** Required if `process_updates` is parallelized (to audit SQLite contention and update ordering invariants).

---

### WP-08 — Synchronize Operations Runbooks, Startup Contracts, & `start.sh` Probe

- **Priority:** `P3 — Medium/Low`
- **Addresses:** `DEF-017`, `DEF-018`
- **Exact Target Files:**
  - `docs/ZERO_TOUCH_STARTUP.md` (fix §5b.4 remote deletion claim line `242`, fix `/ready`+`/status` wording lines `52-53`, add `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` & `MINI_APP_TRUSTED_PROXIES`)
  - `docs/OPERATIONS_RUNBOOK.md` (document all 19 SQLite tables in §4, all env vars in §3, `notification_inbox` recovery in §9)
  - `README.md` (add `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` and `MINI_APP_TRUSTED_PROXIES` to env table)
  - `docs/API_NOTES.md` (reconcile OpenAPI spec version mismatch `1.68.1` vs `1.79.0`/`1.87.1`)
  - `start.sh:56` (optionally add explicit `anyio` check)
  - `tests/test_zero_touch_contract.py`, `tests/test_deploy_manifest.py`, `tests/test_start_script.py`
- **Root Cause:** Documentation drifted behind schema migrations (`19` tables vs `6` documented), env flags, and `OHB2-MINIAPP` remote `DELETE` implementation.
- **Concrete Changes:** Sync all 4 operational docs with verified code; add automated doc-parity test checking `bot/config.py` / `.env.example` / `bot/db.py` table names against `README.md` and `OPERATIONS_RUNBOOK.md` (leaving `docs/MINI_APP.md` and AI Studio `src/*` untouched).
- **Dependencies:** Run after `WP-01` (`ATTACHMENT_DOCUMENT_INTAKE_ENABLED` default) and `WP-04` (`/updates_*` commands if added) so docs reflect final behavior.
- **Risks:** None to runtime; keep `tests/test_zero_touch_contract.py` & `tests/test_deploy_manifest.py` passing.
- **Required Tests:** New parity assertions in `test_zero_touch_contract.py` / `test_deploy_manifest.py` + updated `test_start_script.py`.
- **Acceptance Criteria:** Zero factual contradictions between `ZERO_TOUCH_STARTUP.md`/`OPERATIONS_RUNBOOK.md`/`README.md` and code.
- **Independent Review Requirement:** Optional.

---

### WP-09 — Execute Full CI Verification Matrix & Live Hygiene Checks

- **Priority:** `P1 — Release Gate`
- **Addresses:** `DEF-019`
- **Exact Target Files:** `.github/workflows/ci.yml` (verify execution — no code edits required unless Python 3.11/3.13 reveals warnings/failures)
- **Root Cause:** Local audit container lacks Python >= 3.11 and `requirements-dev.txt` packages.
- **Concrete Changes:** Run full `.github/workflows/ci.yml` (`python` job on 3.11 & 3.13 + `frontend` job on Node 24) via GitHub Actions or clean Termux/container venv:
  - `python -m pytest -q`
  - `node --test tests/frontend/*.test.js`
  - `python -m pyflakes bot/ automation/ tools/ main.py tests/`
  - `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613`
  - `python -m pip_audit -r requirements-dev.txt`
- **Dependencies:** Gates completion of `WP-01` .. `WP-08`.
- **Risks:** `pip_audit` may flag newly disclosed upstream CVEs requiring dependency pin review (per `AGENTS.md` §4, only bump if proven necessary and re-verify).
- **Required Tests:** Full repository suite.
- **Acceptance Criteria:** Exit code `0` across all 5 commands on both Python 3.11 and 3.13 + Node 24.
- **Independent Review Requirement:** Verification log inspection required.

---

### WP-10 — External Hosting Qualification (`HOST-01`/`HOST-02`), Enzonic SFTP Verification & P0 Reopen Gate

- **Priority:** `P3 — External / Deferred`
- **Addresses:** `DEF-015`, `DEF-016`
- **Exact Target Files:** Operational execution only (`.github/workflows/enzonic-sftp-readonly-check.yml`, `tools/katabump-sqlite-canary/canary.py`, `.agent/PROGRESS.md` gate tracking) — **no Mini App edits**
- **Root Cause:** Enzonic live SFTP host fingerprint and SQLite restart persistence (`H1`) are unverified; P0 Stage B1/B2 awaits upstream OpenHands Cloud scoped credential + SSRF allowlist decision.
- **Concrete Changes:**
  1. Independently verify Enzonic `us-four.enzonic.com:2022` SSH host key fingerprint from Enzonic panel; configure `ENZONIC_SSH_PRIVATE_KEY` secret in GitHub repo; run `enzonic-sftp-readonly-check.yml`.
  2. Run `tools/katabump-sqlite-canary/canary.py` on target host across container restarts/redeploys to qualify `H1` persistence.
  3. Only reopen `Stage B1/B2` remote attachment upload when `.agent/PROGRESS.md:32-36` criteria are met (scoped credential + static origin allowlist).
- **Dependencies:** External operator credentials, hosting environment access, and upstream OpenHands API support.
- **Risks:** Ephemeral filesystem wipe on free hosting would cause silent `outbox`/`deleted_conversations` loss -> MUST fail qualification gate if `H1` canary fails.
- **Required Tests:** `canary.py` restart pass + live workflow green run.
- **Acceptance Criteria:** Proven durable SQLite storage + verified SFTP access before production launch.
- **Independent Review Requirement:** Required prior to production cutover or reopening P0 Stage B.

---

## 3. Prioritization & Release-Readiness Gates

| Gate | Required WPs | Pass Criteria |
|---|---|---|
| **Gate A — Safe Daily Bot Usage (Unbricked)** | `WP-01` + `WP-09` | Fresh default config disables unfinished P0 document intake; `/cancel` / batch abandonment unbricks stuck owners; D-34 never blocks unrelated conversations; full CI green. |
| **Gate B — Polling & Operational Reliability** | `WP-02` + `WP-03` + `WP-04` + `WP-09` | Zero unwrapped `q.answer()`; zero `outcome=None` paths; transient `5xx`/`429`/`TelegramError` never ACK-dropped or `FAILED_PERMANENT`; ADR §28.4 poison skip operational. |
| **Gate C — Concurrency, Long IDs & Ops Runbook Parity** | `WP-05` + `WP-06` + `WP-07` + `WP-08` + `WP-09` | 64-char conversation IDs supported end-to-end; `get_status()` unified; Watcher/Notifier/CreationWorker/deliver_outbox bugs closed; runbooks 100% synced. |
| **Gate D — Production Cutover Readiness** | `WP-10` + Gates A–C | Live Enzonic/host `H1` SQLite persistence verified across restarts; out-of-band SFTP fingerprint verified; `HOST-02` ingress qualified externally (without altering excluded Mini App files). |
