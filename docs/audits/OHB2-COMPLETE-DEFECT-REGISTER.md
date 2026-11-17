# OHB2 Complete Defect Register

**Audit Task ID:** `OHB2-COMPLETE-REPOSITORY-AUDIT-AND-REMEDIATION-MASTER-PLAN`  
**Audit Date:** 2026-11-17  
**Baseline Scope:** 328 repository files at `/app/applet` (read-only audit; 0 files modified)  
**Scope Exclusion:** Telegram Mini App (`bot/web/*`, `bot/web/static/*`, `tests/frontend/*`, `tests/test_miniapp_*.py`, `tests/test_real_http_miniapp_download.py`, `tests/_miniapp_helpers.py`, `docs/MINI_APP.md`, `mini_app_*` config fields) is **`EXCLUDED_MINI_APP`**.

---

## Summary Counts

| Severity | Count | Defect IDs |
|---|---|---|
| **CRITICAL** | 1 | `DEF-001` |
| **HIGH** | 7 | `DEF-002`, `DEF-003`, `DEF-004`, `DEF-005`, `DEF-015`, `DEF-016`, `DEF-019` |
| **MEDIUM** | 9 | `DEF-006`, `DEF-007`, `DEF-008`, `DEF-009`, `DEF-010`, `DEF-011`, `DEF-012`, `DEF-014`, `DEF-017` |
| **LOW** | 2 | `DEF-013`, `DEF-018` |
| **TOTAL** | **19** | `DEF-001` .. `DEF-019` |

Confidence breakdown: **19 `CONFIRMED`**, **0 `STRONGLY_SUSPECTED`**, **0 `UNVERIFIED`**.  
Mini App Exclusion breakdown: **1 `BLOCKED_BY_EXCLUDED_MINI_APP`** (`DEF-014`), **18 `NONE`**.

---

## Register

### DEF-001 — Permanent Normal Text-Prompt Self-DoS ("Owner Brick") After Any Document Attachment

- **Defect ID:** `DEF-001`
- **Title:** Permanent Normal Text-Prompt Self-DoS ("Owner Brick") After Any Document Attachment
- **Severity:** `CRITICAL`
- **Category:** State Machine / Feature Integration / Operational Availability
- **Affected File(s) and Line(s):**
  - `bot/config.py:43, 315-317` (`attachment_document_intake_enabled` defaults to `True`)
  - `bot/handlers.py:2245` (`handle_text` unconditionally calls `_handle_accompanying_text` before `reply`/`newchat`/`reposearch`/`route`)
  - `bot/handlers.py:2052-2204` (`_handle_accompanying_text`)
  - `bot/handlers.py:2291-2309` (`cancel_route` / `cancel_route_button` only clear `user_state`, leaving `attachment_batches` untouched)
  - `bot/db.py:1493-1570` (`classify_attachment_routing`, `has_terminal_attachment_batch` scoped by `telegram_id` only, not `conversation_id`)
  - `bot/db.py:812-814` (`attachment_message_identity.batch_id` FK `ON DELETE RESTRICT`)
  - `bot/db.py:1572-1663` (`record_attachment_intent`)
  - `bot/attachments.py:1095-1115` (`AttachmentReaper.sweep` leaves `UNRESOLVED` untouched and marks expired batches `expired` without removing rows)
- **Symptom:** After the owner sends a single Telegram document attachment while `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` is at its default (`True`), **every subsequent normal text prompt** (`/reply`, `/newchat`, `/reposearch`, active `route`) across **all** conversations becomes permanently rejected by Telegram bot text handling.
- **Root Cause:**
  1. `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` defaults to `True` (`bot/config.py:315-317`), exposing Phase A0–A4 local staging intake even though Phase B1/B2 remote upload to OpenHands does not exist.
  2. `classify_attachment_routing` (`bot/db.py:1493-1570`) inspects `attachment_batches` globally across the owner's `telegram_id` (not scoped to the active route/conversation).
  3. **Path A (user sends accompanying text within 15m):** `record_attachment_intent` (`bot/db.py:1630`) transitions the batch from `pending` to `intent_recorded`. Because no remote dispatcher (Stage B1/B2) exists, no code ever moves `intent_recorded` to a terminal state, and `AttachmentReaper` (`bot/attachments.py:1095-1104`) explicitly skips `ATTACHMENT_BATCH_UNRESOLVED_STATUSES`. `classify_attachment_routing` therefore returns `UNRESOLVED` on every future `handle_text` call forever.
  4. **Path B (batch expires after 15m without text, or reaches any terminal state):** `AttachmentReaper` (`bot/attachments.py:1106-1115`) transitions expired `pending` batches to `expired` (`TERMINAL`) and never deletes `attachment_batches` rows (`attachment_message_identity` even enforces `ON DELETE RESTRICT`). Under D-34 fail-closed logic (`bot/db.py:1557-1569`), any future unrelated text message lacks a row in `attachment_message_identity` and classifies as `AttachmentRoutingState.TERMINAL_UNPROVEN`, causing `_handle_accompanying_text` (`bot/handlers.py:2103-2113`) to reject it forever with `ATTACHMENT_TEXT_AMBIGUOUS_TEXT`.
- **Trigger / Reproduction Path:**
  1. Start bot with default `.env` (`ATTACHMENT_DOCUMENT_INTAKE_ENABLED` unset -> `True`).
  2. Open any conversation (creating `route` state) and send any valid document <= 3 MB. Bot stages locally and replies with `ATTACHMENT_ACCEPTED_TEXT`.
  3. Either send any text message within 15 minutes (Path A -> stuck `intent_recorded` / `UNRESOLVED`) OR wait > 15 minutes so `AttachmentReaper` / `classify_attachment_routing` observes expiration (Path B -> `EXPIRED_PENDING` then `expired` -> `TERMINAL_UNPROVEN`).
  4. Now open **any other conversation** (or start `/newchat` or `reposearch`) and send a text prompt. `handle_text` hits `_handle_accompanying_text` at line `2245` and rejects every prompt permanently; `/cancel` (`bot/handlers.py:2295`) does not clear `attachment_batches`.
- **User / System Impact:** Complete loss of Telegram text prompting capability for the bot owner across all existing and new conversations until an operator manually executes SQL `DELETE FROM attachment_message_identity; DELETE FROM attachment_items; DELETE FROM attachment_batches;` or sets `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=0` (note: even setting `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=0` only stops *new* document intake at `handle_attachment:1872`, wait — let's check: `_handle_accompanying_text` in `handle_text:2245` does NOT check `config.attachment_document_intake_enabled`! Verified: setting `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=0` **does not even unbrick** an already-affected owner because `handle_text` still routes through `_handle_accompanying_text`!).
- **Data Integrity / Concurrency / Security Impact:** Breaks core availability; leaves staged bytes on disk forever in Path A (`intent_recorded` is skipped by `AttachmentReaper`). Security fail-closed guarantee D-34 was designed assuming a Stage B dispatcher would close out batches, but without Stage B, fail-closed becomes permanent self-DoS.
- **Evidence:** Direct code inspection of `bot/config.py:43,315-317`, `bot/handlers.py:1872,2052-2246,2291-2309`, `bot/db.py:812-814,1493-1663`, `bot/attachments.py:1095-1115`. Historical closure report `docs/reviews/OHB2-P0-FINAL-CLOSURE-AUDIT-REPORT.md` confirms A0–A4 shipped with Stage B deferred, and `tests/test_attachment_batch_state_routing_f1_1a.py` explicitly tested blocking on `UNRESOLVED`/`TERMINAL_UNPROVEN` in isolation without testing multi-turn recovery into another conversation.
- **Confidence:** `CONFIRMED`
- **Existing Test Coverage Gaps:** No end-to-end multi-conversation regression test verifies that sending a document in Conversation A allows sending normal text prompts in Conversation B (or after batch completion/expiration/cancel).
- **Recommended Fix Direction:**
  1. Immediately default `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` to `False` (`0`) in `bot/config.py` until remote upload or safe manual lifecycle closure exists (still honoring explicit opt-in tests).
  2. Guard `_handle_accompanying_text` in `bot/handlers.py` when `attachment_document_intake_enabled` is disabled AND only when no active unresolved state requires user rescue, OR add explicit owner batch cancel/reset command (`/cancel` or dedicated `/attachments_clear`) that clears `pending`/`intent_recorded`/`expired` batches safely after sweeping staging files.
  3. Revisit D-32/D-34 terminal blocking: D-34 `TERMINAL_UNPROVEN` must NOT permanently block *new* unrelated messages once a batch is terminal (`delivered`/`expired`/`rejected`/`failed`), or terminal batches must be archived/scoped by `conversation_id` + explicit window rather than global `SELECT 1 FROM attachment_batches WHERE telegram_id=? AND status IN TERMINAL`.
- **Mini App Exclusion Impact:** `NONE` (fixing `bot/config.py`, `bot/db.py`, `bot/handlers.py`, `bot/attachments.py` requires zero Mini App edits).
- **Dependencies / Blockers:** Owner product decision required if keeping A0–A4 enabled vs reverting D-34 blocking semantics; zero external dependencies to set safe default `False` and add explicit batch abandonment/cleanup.
- **Verification Strategy:** Add E2E regression tests covering Path A (`intent_recorded` -> `/cancel` or transition -> normal prompt in Conv B), Path B (`expired` -> normal prompt in Conv B succeeds), and kill-switch recovery (`ATTACHMENT_DOCUMENT_INTAKE_ENABLED=0` unblocks text prompts). Run full `pytest -q` and `pyflakes`.

---

### DEF-002 — Head-of-Line Polling Offset Deadlock on `FAILED_PERMANENT` & Transient `TelegramError` Misclassification

- **Defect ID:** `DEF-002`
- **Title:** Head-of-Line Polling Offset Deadlock on `FAILED_PERMANENT` & Transient `TelegramError`/Network Misclassification
- **Severity:** `HIGH`
- **Category:** Polling / Telegram ACK Reliability / Error Classification
- **Affected File(s) and Line(s):**
  - `bot/update_outcomes.py:40-53, 93-110` (`FAILED_PERMANENT` in `_INELIGIBLE`, never ack-eligible)
  - `bot/polling.py:155-173, 202-208` (`process_updates` / `advance_offset` stalls at first `_INELIGIBLE` update)
  - `bot/handlers.py:477-495` (`_classify_failure`)
  - `bot/handlers.py:1150-1154` (`send_reply_txt` records `FAILED_PERMANENT` on `TextDocumentTooLargeError`)
  - `bot/handlers.py:1468, 1567` (unwrapped `bot.send_document` calls in `export_conversation` and `show_file`)
- **Symptom:** (1) Any update whose outcome is `FAILED_PERMANENT` permanently freezes `acknowledgment_boundary()` and `TelegramPoller._next_offset`, replaying the same failing update and blocking all subsequent updates forever across restarts. (2) Any uncaught `telegram.error.RetryAfter`, `TimedOut`, `NetworkError`, `asyncio.TimeoutError`, or `httpx.HTTPError` reaching `handle_processing_error` is misclassified as `FAILED_PERMANENT` instead of `FAILED_TRANSIENT`.
- **Root Cause:**
  1. `update_outcomes.py:40-53` places `FAILED_PERMANENT` in `_INELIGIBLE`, while ADR §28.4 manual poison quarantine/skip (`poison_acknowledged` / `/updates_status`) was never implemented (`bot/polling.py` + `bot/db.py` + `bot/handlers.py`). Thus a permanent failure loops indefinitely at head-of-line.
  2. `_classify_failure` (`bot/handlers.py:477-495`) only inspects `sqlite3.Error` (using `is_transient_sqlite_error`) and `ApiError` (`status_code is None or >= 500 or == 429`). All other exceptions fall through to `FAILED_PERMANENT` — including transient Telegram Bot API network errors (`RetryAfter`, `TimedOut`, `NetworkError`), `asyncio.TimeoutError`, and `OSError`/`httpx.TransportError`.
- **Trigger / Reproduction Path:**
  - Trigger A: Click `txt:` (`send_reply_txt`) on a reply > 50 MB -> `TextDocumentTooLargeError` -> `mark_failed_permanent` (`handlers.py:1153`) -> polling boundary locks forever.
  - Trigger B: Click `export:` (`export_conversation`) or `file:` (`show_file`) when Telegram `send_document` raises `telegram.error.TimedOut` or `RetryAfter` -> unhandled exception hits `handle_processing_error` -> `_classify_failure` returns `FAILED_PERMANENT` (`handlers.py:495`) instead of `FAILED_TRANSIENT` -> polling stalls permanently on a transient Telegram error.
- **User / System Impact:** Complete polling freeze (bot becomes unresponsive to newer updates until Telegram's 24h update retention expires or DB `processed_updates` is manually patched). Misclassifying transient Telegram timeouts as permanent pollutes update telemetry and triggers permanent failure alerts.
- **Data Integrity / Concurrency / Security Impact:** Does not violate `at-most-once` external delivery guarantees, but defeats bounded retry/recovery and causes operational outage.
- **Evidence:** Direct inspection of `bot/update_outcomes.py:40-53,93-110`, `bot/polling.py:155-173`, `bot/handlers.py:477-495,1150-1162,1468,1567`, `.agent/PROGRESS.md:105` (explicitly noting §28.4 poison mechanism was not implemented).
- **Confidence:** `CONFIRMED`
- **Existing Test Coverage Gaps:** `tests/test_stage2_custom_polling.py` tests that `_INELIGIBLE` stalls boundary (by design), but no test verifies `_classify_failure` on `telegram.error.TimedOut`/`RetryAfter`/`NetworkError`, nor recovery from a poison `FAILED_PERMANENT` update.
- **Recommended Fix Direction:**
  1. Update `_classify_failure` in `bot/handlers.py` to classify `telegram.error.RetryAfter`, `telegram.error.TimedOut`, `telegram.error.NetworkError`, `asyncio.TimeoutError`, and `OSError` as `FAILED_TRANSIENT`.
  2. Implement ADR §28.4 bounded poison-update quarantine / terminal dead-letter outcome (e.g., `POISON_QUARANTINED` after explicit terminal non-retryable errors like `TextDocumentTooLargeError` or bounded `FAILED_PERMANENT` after operator alert), keeping transient failures fail-closed until succeeded or operator-skipped via `/updates_status` + `/updates_skip`.
  3. Wrap `bot.send_document` in `export_conversation` and `show_file` consistently with safe error handling so transient Telegram errors surface cleanly or record `FAILED_TRANSIENT`.
- **Mini App Exclusion Impact:** `NONE`
- **Dependencies / Blockers:** Requires ADR §28.4 product decision on whether `FAILED_PERMANENT` auto-advances after `N` retries + user alert or requires explicit `/updates_skip` operator command.
- **Verification Strategy:** Unit tests for `_classify_failure` with `RetryAfter`/`TimedOut`/`NetworkError`/`asyncio.TimeoutError`; polling tests proving permanent error quarantine prevents infinite head-of-line lock while preserving `FAILED_TRANSIENT` retry gating.

---

### DEF-003 — Missing Outcome (`outcome=None` -> Ack Block) & Broken Awaiting-State Error Consumption in `bot/handlers.py`

- **Defect ID:** `DEF-003`
- **Title:** Missing Outcome (`outcome=None` -> Ack Block) & Premature `reposearch` Consumption on Upstream Error
- **Severity:** `HIGH`
- **Category:** Handler Outcome Contract / Control Flow / Polling Reliability
- **Affected File(s) and Line(s):**
  - `bot/handlers.py:2791-2804` (`outbox_mark_sent` missing `mark_explicitly_ignored` when `not changed` and `status_now == final`)
  - `bot/handlers.py:2275-2283` (`handle_text` `reposearch` branch unconditionally consumes `awaiting` even when `_show_repos` failed upstream)
  - `bot/handlers.py:2434-2469` (`_show_repos` catches `ApiError` internally and returns normally without raising `OperationalApiFailure`, and `repos_page`/`start_new_chat` rely on it)
  - `bot/handlers.py:2351-2354` (`_send_prompt`) & `bot/handlers.py:2534-2536` (`_start_new_chat`) awaiting-expiry `False` race
- **Symptom:**
  1. In `outbox_mark_sent`, if a concurrent worker resolves the outbox row to `sent`/`done` between `_get_record` and `set_outbox_status_if_in`, the `if status_now == final:` branch replies and returns **without recording any update outcome**, leaving `outcome=None` -> `PARTIAL_OR_UNKNOWN` -> blocks Telegram polling offset ack!
  2. In `handle_text` (`reposearch`), if OpenHands returns `5xx`/`429`/timeout during repo search (`_show_repos`), `_show_repos` swallows `ApiError` into a UI message and `handle_text` proceeds to `db.consume_one_shot_awaiting(...)`. This both destroys the user's `reposearch` prompt state on a transient API outage AND, if `consume_one_shot_awaiting` returns `False` (concurrent expiry race), returns with **`outcome=None`** -> `PARTIAL_OR_UNKNOWN` (ack block)!
- **Root Cause:** Hand-rolled per-branch outcome calls (`mark_durable_completed` / `mark_explicitly_ignored`) lack a structural fallback check, and `_show_repos` mixes UI error swallowing with one-shot awaiting consumption.
- **Trigger / Reproduction Path:**
  1. Call `/outbox_mark_sent prompt:1 confirm` concurrently with `OutboxWorker` finishing prompt 1 -> hits `bot/handlers.py:2795-2798` -> `update_outcome(uid)` remains `None`.
  2. Trigger repo search (`reposearch`), then send search query while OpenHands `/user/repositories` returns HTTP 503 -> `_show_repos` eats `ApiError`, `consume_one_shot_awaiting` deletes `reposearch` and writes `DURABLE_COMPLETED` despite failed search; or if awaiting expired between line 2253 and line 2281, `consume_one_shot_awaiting` returns `False` leaving `update_outcome=None`.
- **User / System Impact:** Intermittent head-of-line Telegram polling offset blocks (`PARTIAL_OR_UNKNOWN`), replay of already-executed commands on restart, and lost `reposearch` user intent on transient API errors.
- **Data Integrity / Concurrency / Security Impact:** Violates Stage 2 contract invariant that every matched update records an explicit durable outcome before handler return.
- **Evidence:** Direct code inspection of `bot/handlers.py:2275-2283, 2351-2354, 2434-2469, 2534-2536, 2791-2804`. Note `tests/test_manual_polling_handler_outcome_coverage.py` did not exercise the race branches `status_now == final` or `reposearch` concurrent expiry / 503 failure.
- **Confidence:** `CONFIRMED`
- **Existing Test Coverage Gaps:** Missing branch coverage for `outbox_mark_sent` concurrent CAS race (`status_now == final`), `reposearch` on upstream 5xx/429, and `consume_one_shot_awaiting(...) == False`.
- **Recommended Fix Direction:**
  1. Add `mark_explicitly_ignored(update, context)` in `outbox_mark_sent` (`bot/handlers.py:2795-2799`).
  2. Propagate operational `ApiError` (`_raise_if_operational_api_failure`) in `_show_repos` (like Stage4-F1) so `reposearch` is NOT consumed on 5xx/429/timeout and the update is not acknowledged as completed; record explicit outcome (`mark_explicitly_ignored` or `mark_durable_completed`) when `consume_one_shot_awaiting` returns `False` due to concurrent expiry.
  3. Check return value of `consume_one_shot_awaiting` in `_send_prompt` / `_start_new_chat` so `False` records `mark_explicitly_ignored` (never leaving `outcome=None`).
- **Mini App Exclusion Impact:** `NONE`
- **Dependencies / Blockers:** None.
- **Verification Strategy:** Add deterministic unit tests for each of the three branches verifying `db.update_outcome(uid) is not None` and `reposearch` preservation on 503.

---

### DEF-004 — Incomplete `Stage4-F1` Operational Upstream Failure Propagation & Uncaught Document Send Errors

- **Defect ID:** `DEF-004`
- **Title:** Incomplete `Stage4-F1` Operational Upstream Failure Propagation & Unwrapped `send_document` Calls
- **Severity:** `HIGH`
- **Category:** Error Propagation / Fail-Closed ACK Semantics
- **Affected File(s) and Line(s):**
  - `bot/handlers.py:1129-1133` (`send_reply_txt`)
  - `bot/handlers.py:1206-1212` (`watch_conversation`)
  - `bot/handlers.py:1276-1282` (`delete_conversation_prompt`)
  - `bot/handlers.py:1307-1318` (`delete_conversation_confirm`)
  - `bot/handlers.py:1449-1454, 1468` (`export_conversation`)
  - `bot/handlers.py:1567` (`show_file`)
  - `bot/handlers.py:1585-1591` (`reply_prompt`)
  - `bot/handlers.py:905-918` (`list_conversations` — swallows `ApiError` into UI error & calls `mark_explicitly_ignored`!)
  - `bot/handlers.py:2442-2447` (`_show_repos` called by `start_new_chat` / `repos_page` / `handle_text`)
- **Symptom:** When OpenHands returns transient `5xx`, `429`, or connection timeout during conversation authorization (`authorize_conversation_detailed`), `send_reply_txt`, `watch_conversation`, `delete_conversation_prompt`, `delete_conversation_confirm`, `export_conversation`, and `reply_prompt` call `_authorized_conversation(...)` (instead of `_authorized_conversation_status(...)`) and record **`EXPLICITLY_IGNORED`** — causing Telegram polling to **ACK and permanently drop** the update instead of failing closed (`OPERATIONAL_FAILURE` / `FAILED_TRANSIENT`). Likewise `list_conversations` and `_show_repos` catch `ApiError` `5xx`/`429` and drop updates via `EXPLICITLY_IGNORED`. Meanwhile, `export_conversation` (`1468`) and `show_file` (`1567`) lack `try/except TelegramError` around `send_document`.
- **Root Cause:** `OHB2-SW-07` and `Stage4-F1` upgraded `open_conversation`, `copy_reply`, `full_reply`, `list_files`, `show_status`, and `show_cost` to `_authorized_conversation_status` + `mark_operational_failure` + `raise`, leaving the remaining 6 `_authorized_conversation` callers and 2 listing helpers un-migrated.
- **Trigger / Reproduction Path:** Tap `رد` (`reply_prompt`), `تصدير` (`export_conversation`), `ملف النص` (`send_reply_txt`), `تابع` (`watch_conversation`), `🗑 حذف الشات` (`delete_conversation_prompt`), or `شاتاتي` (`list_conversations`) while OpenHands API returns HTTP 503. Bot edits message with transient error AND marks update `EXPLICITLY_IGNORED`, advancing Telegram offset and losing retryability.
- **User / System Impact:** Inconsistent operational failure semantics across buttons; transient OpenHands outages silently acknowledge user actions as ignored instead of preserving fail-closed retry gating and consistent error telemetry.
- **Data Integrity / Concurrency / Security Impact:** No data corruption or auth bypass (all still deny fail-closed on upstream failure), but breaks `Stage4-F1` / ADR ACK consistency.
- **Evidence:** Direct code audit of `bot/handlers.py:164-212, 905-918, 1129-1133, 1206-1212, 1276-1282, 1307-1318, 1449-1468, 1567, 1585-1591, 2442-2447`. Contrast with `show_status` (`1355-1365`) and `open_conversation` (`971-981`).
- **Confidence:** `CONFIRMED`
- **Existing Test Coverage Gaps:** `tests/test_stage4_f1_status_cost_operational_ack.py` and `tests/test_sw07_api_handler_failure_propagation.py` only test `show_status`, `show_cost`, `open_conversation`, `copy_reply`, `full_reply`, and `files_page` — not `reply_prompt`, `export_conversation`, `send_reply_txt`, `watch_conversation`, `delete_conversation_*`, `list_conversations`, or `_show_repos`.
- **Recommended Fix Direction:** Migrate all remaining `_authorized_conversation` callers and listing handlers (`list_conversations`, `_show_repos`) to `_authorized_conversation_status` + `_raise_if_operational_api_failure` (recording `OPERATIONAL_FAILURE` / `FAILED_TRANSIENT` for 5xx/429/network failures while keeping `EXPLICITLY_IGNORED` for 4xx/deleted/unauthorized). Wrap `bot.send_document` in `export_conversation` and `show_file` consistently.
- **Mini App Exclusion Impact:** `NONE`
- **Dependencies / Blockers:** Confirm ADR §30 policy on whether read/menu queries (`list_conversations`) should block offset on 5xx or record `EXPLICITLY_IGNORED` intentionally (at minimum `reply_prompt`, `delete_conversation_confirm`, `watch_conversation`, `send_reply_txt`, `export_conversation` should match `show_status`/`open_conversation`).
- **Verification Strategy:** Extend `test_stage4_f1_status_cost_operational_ack.py` matrix to every callback handler in `bot/handlers.py` under simulated HTTP 503 vs HTTP 404.

---

### DEF-005 — Unwrapped `await q.answer()` Across 24 of 28 Callback Call Sites Blocks Handler Execution & Outcome Recording

- **Defect ID:** `DEF-005`
- **Title:** Unwrapped `await q.answer()` Across 24 of 28 Callback Call Sites Blocks Handler Execution on Stale/Timed-Out Callback Queries
- **Severity:** `HIGH`
- **Category:** Error Handling / Telegram Callback Lifecycle / Reliability
- **Affected File(s) and Line(s):**
  - `bot/handlers.py` unwrapped (`w=False`) lines: `780` (`app_open`), `799` (`show_menu`), `834` (`notifications_menu`), `850, 857` (`notifications_toggle` auth-fail/DB-fail paths — only `L866` is wrapped), `893` (`list_conversations`), `965` (`open_conversation`), `1033` (`copy_reply`), `1072` (`full_reply`), `1167` (`list_watches`), `1195` (`watch_conversation`), `1229` (`unwatch_conversation`), `1266` (`delete_conversation_prompt`), `1296` (`delete_conversation_confirm`), `1439` (`export_conversation`), `1477` (`list_files`), `1526` (`show_file`), `1575` (`reply_prompt`), `2302` (`cancel_route_button`), `2380` (`start_new_chat`), `2401` (`repos_page`), `2424` (`repo_search_prompt`), `2473` (`pick_repo`), `2500` (`new_chat_no_repo`).
  - Only 4 sites are wrapped: `L866` (`notifications_toggle` success), `L1120` (`send_reply_txt`), `L1348` (`show_status`), `L1402` (`show_cost`).
- **Symptom:** If a callback query is older than ~30–60 seconds (e.g., after brief downtime/restart recovery with `drop_pending_updates=False`, or a transient Telegram `TimedOut`/`BadRequest: Query is too old` during `answerCallbackQuery`), `await q.answer()` raises `telegram.error.BadRequest` or `TimedOut` at the very first line of the callback handler — aborting the action before execution, recording `FAILED_PERMANENT` via `_classify_failure` (`DEF-002`), and **permanently deadlocking polling**.
- **Root Cause:** `OPS01-D1` hardened `show_status`, `show_cost`, and `send_reply_txt` with `try/except` around `q.answer()`, while the other 24 callback call sites were left with bare `await q.answer()`. Even `notifications_toggle` (`L850, L857`) forgets to wrap its unauthorized/error `q.answer()` alerts.
- **Trigger / Reproduction Path:** Process any queued callback button after a 60s outage (or inject `TimedOut`/`BadRequest("Query is too old")` on `q.answer()`). E.g. tap `open:{cid}` or `list:0` or `deleteok:{cid}` -> raises `BadRequest` -> `handle_processing_error` -> `_classify_failure` -> `FAILED_PERMANENT` -> head-of-line polling deadlock (`DEF-002`)!
- **User / System Impact:** Old inline buttons become fatal polling-queue poisons after any short restart/backlog!
- **Data Integrity / Concurrency / Security Impact:** Severe availability risk (`drop_pending_updates=False` replays stale callbacks on startup recovery, hitting unwrapped `q.answer()` immediately). Notice `_allowed` checks happen *after* `q.answer()` in `L780..L2500` too!
- **Evidence:** Direct scan of all `.answer(` occurrences in `bot/handlers.py` showing 24/28 unwrapped vs 4/28 wrapped (`L866`, `L1120`, `L1348`, `L1402`).
- **Confidence:** `CONFIRMED`
- **Existing Test Coverage Gaps:** `tests/test_handlers.py` mocks `q.answer` as always succeeding; only `show_status`/`show_cost`/`send_reply_txt` have regression tests for `q.answer` failure.
- **Recommended Fix Direction:** Extract a shared `_safe_answer(q, text=None, *, show_alert=False)` helper in `bot/handlers.py` (logging exception type at `WARNING`, ignoring `BadRequest`/`TimedOut`/`NetworkError`), check `_allowed` cleanly, and replace all 28 `q.answer(...)` calls with `await _safe_answer(q, ...)`.
- **Mini App Exclusion Impact:** `NONE`
- **Dependencies / Blockers:** None.
- **Verification Strategy:** Add parameterized test across every `CallbackQueryHandler` verifying stale/failing `q.answer()` neither crashes the handler nor leaves an ack-blocking `FAILED_PERMANENT` outcome.

---

### DEF-006 — Custom Poller Batch Serialization Defeats `concurrent_updates(True)` Latency Isolation

- **Defect ID:** `DEF-006`
- **Title:** Custom Poller Batch Serialization Defeats `concurrent_updates(True)` Latency Isolation
- **Severity:** `MEDIUM`
- **Category:** Concurrency / Responsiveness / Architecture Inconsistency
- **Affected File(s) and Line(s):**
  - `bot/polling.py:161-162, 175-178` (`TelegramPoller.process_updates` loops `for update in updates: await self.dispatch_and_wait(update)`)
  - `bot/app.py:75-87` (`.concurrent_updates(True)` configured specifically so fast prompt acks aren't blocked by slow commands)
- **Symptom:** When a single `getUpdates` response returns multiple updates (e.g., `[list_files (slow OpenHands API), prompt_text (fast DB write + "وصل ✅")]`), `TelegramPoller.process_updates` awaits `update_queue.join()` **one update at a time**, completely neutralizing `ApplicationBuilder.concurrent_updates(True)` within a batch.
- **Root Cause:** Stage 2 replaced PTB's `Updater` with `TelegramPoller`. To wait until handlers wrote outcomes to SQLite before calling `collect_outcomes`, `process_updates` awaits `put(update)` + `queue.join()` inside a sequential `for` loop instead of submitting the batch (or concurrent-safe updates) and waiting once.
- **Trigger / Reproduction Path:** Send `/start` or click `list_files` on a slow upstream, then send a text prompt within the same poll interval so both arrive in one `getUpdates` batch. The fast `"وصل ✅"` prompt reply stalls behind the slow handler's HTTP timeout.
- **User / System Impact:** Degraded interactivity and delayed `"وصل ✅"` prompt receipts during concurrent commands/callbacks or attachment downloads.
- **Data Integrity / Concurrency / Security Impact:** Note: PTB's `concurrent_updates=True` *does* run handlers concurrently when multiple updates sit in `update_queue`; care must be taken if concurrent handlers for the *same* `telegram_id` mutate `user_state` or `attachment_batches` (`DEF-011`). Serializing per-batch loses the intended concurrency documented in `bot/app.py:75-87`.
- **Evidence:** `bot/app.py:75-87` comment vs `bot/polling.py:161-162, 175-178`.
- **Confidence:** `CONFIRMED`
- **Existing Test Coverage Gaps:** `tests/test_stage2_custom_polling.py` tests batch ordering and boundary calculation but has no concurrency/latency-isolation test matching `bot/app.py:75-87`.
- **Recommended Fix Direction:** Enqueue the whole batch into `application.update_queue` (or dispatch via `process_update` tasks) and await completion (`update_queue.join()` once per batch) *after* hardening attachment quota locks (`DEF-011`), OR explicitly document intentional sequential batching and remove the misleading `.concurrent_updates(True)` rationale in `bot/app.py:75-87`.
- **Mini App Exclusion Impact:** `NONE`
- **Dependencies / Blockers:** Depends on fixing `DEF-011` (quota reservation lock) if intra-batch concurrent attachment downloads are enabled.
- **Verification Strategy:** Add timing test with slow update 1 (`0.5s`) + fast update 2 (`0.01s`) in the same batch verifying fast update finishes in `< 0.1s` (if parallelized) while preserving ordered `collect_outcomes` / monotonic boundary.

---

### DEF-007 — `Watcher.tick` and `Notifier._process` Missing `continue`/`return` After `clear_retry_not_before` Failure

- **Defect ID:** `DEF-007`
- **Title:** `Watcher.tick` and `Notifier._process` Continue Processing After Logging Skip on `clear_retry_not_before` DB Failure
- **Severity:** `MEDIUM`
- **Category:** Notification Reliability / Control Flow Bug
- **Affected File(s) and Line(s):**
  - `bot/watcher.py:215-221`
  - `bot/notifier.py:522-528`
- **Symptom:** Both `Watcher.tick` and `Notifier._process` catch exceptions from `self._db.clear_retry_not_before(...)` and log `"تعذّر مسح موعد إعادة محاولة ... هيتخطّى"` ("will skip"), yet **lack `continue` (`watcher.py`) / `return` (`notifier.py`)** and immediately proceed to process and send the notification for that conversation anyway.
- **Root Cause:** Missing control-flow statement (`continue` in `bot/watcher.py:221`; `return` in `bot/notifier.py:528`) inside the `except Exception:` block.
- **Trigger / Reproduction Path:** Expire a `RetryAfter` deadline for a conversation, then inject `sqlite3.OperationalError` in `clear_retry_not_before`. Both components log that the conversation "will be skipped", then continue directly to `conv = convs.get(...)` / `first_run` and attempt Telegram delivery anyway (likely re-hitting failed DB writes or spamming repeat notifications if `clear_retry_not_before` keeps failing).
- **User / System Impact:** Misleading operational logs and potential duplicate notification attempts if DB writes fail after a Telegram `RetryAfter` expires.
- **Data Integrity / Concurrency / Security Impact:** Breaks stated skip-on-DB-failure invariant; could deliver stale state if partial DB errors persist.
- **Evidence:** Direct inspection of `bot/watcher.py:215-221` and `bot/notifier.py:522-528`.
- **Confidence:** `CONFIRMED`
- **Existing Test Coverage Gaps:** No test in `tests/test_watcher.py` or `tests/test_notifier.py` injects a DB exception into `clear_retry_not_before` on an expired retry deadline.
- **Recommended Fix Direction:** Add `continue` at `bot/watcher.py:221` and `return` at `bot/notifier.py:528` so behavior matches the explicit log and contract.
- **Mini App Exclusion Impact:** `NONE`
- **Dependencies / Blockers:** None.
- **Verification Strategy:** Unit tests mocking `clear_retry_not_before` raising `sqlite3.OperationalError` and asserting 0 Telegram messages / 0 further DB transition writes in that cycle.

---

### DEF-008 — `deliver_outbox(outbox_id)` Helper Claims Arbitrary Pending Row Without `outbox_id` Filter or Grouping Window

- **Defect ID:** `DEF-008`
- **Title:** `deliver_outbox(outbox_id)` Helper Ignores Target `outbox_id` and Bypasses Grouping Maturity Window
- **Severity:** `MEDIUM`
- **Category:** Outbox Delivery / Function Contract Bug
- **Affected File(s) and Line(s):**
  - `bot/outbox.py:210-224` (`deliver_outbox`)
  - `bot/handlers.py:2366-2367` (`_deliver_outbox` wrapper)
- **Symptom:** Calling `deliver_outbox(client, db, bot, outbox_id)` verifies `db.get_outbox(outbox_id)` is `pending`, then calls `db.claim_outbox(now_iso())` with **no `outbox_id` filter and no `mature_before` grouping window**, so it can claim and immediately post a completely different conversation's newly arrived (`< 1.5s`) outbox row instead of `outbox_id`.
- **Root Cause:** During `OHB2-N10-28C` concurrency hardening, `read-then-write` was replaced by atomic `db.claim_outbox(now_iso())` inside `deliver_outbox` without adding `outbox_id=...` or `mature_before=...` support. Currently production runtime uses `OutboxWorker` (which passes `mature_before`), leaving `deliver_outbox` / `_deliver_outbox` as an exported helper primarily called in tests (`tests/test_handlers.py`, `tests/test_outbox_concurrency_28c.py`, etc.).
- **Trigger / Reproduction Path:** Insert `outbox_id=1` (pending), insert `outbox_id=2` (pending, `created_at` newer or older), call `deliver_outbox(..., outbox_id=2)` when row 1 is older -> row 1 gets claimed and posted prematurely while row 2 remains untouched.
- **User / System Impact:** Dormant in `main.py` worker flow today, but dangerous latent trap for any caller, test, or future direct trigger expecting `outbox_id`-scoped or grouping-safe delivery.
- **Data Integrity / Concurrency / Security Impact:** Still atomic CAS (`at-most-once` preserved), but violates target-row contract and bypasses `GROUP_WINDOW` (`1.5s`) prompt batching.
- **Evidence:** Direct inspection of `bot/outbox.py:210-224`, `bot/handlers.py:2366-2367`, and `grep` of callers across `bot/` and `tests/`.
- **Confidence:** `CONFIRMED`
- **Existing Test Coverage Gaps:** Existing tests (`test_outbox_concurrency_28c.py`) only test single-row pending queues with `deliver_outbox`, masking the missing `outbox_id` filter.
- **Recommended Fix Direction:** Either add `db.claim_outbox_by_id(outbox_id, now)` (atomic `UPDATE outbox SET status='claimed' ... WHERE id=? AND status='pending'`) and pass `mature_before` if grouping applies, OR deprecate/remove `deliver_outbox` / `_deliver_outbox` if only legacy test glue (updating those tests to invoke `OutboxWorker._tick` or `claim_outbox_by_id`).
- **Mini App Exclusion Impact:** `NONE`
- **Dependencies / Blockers:** Requires updating callers in ~7 existing test files if signature/semantics change.
- **Verification Strategy:** Test with 2 pending outbox rows calling `deliver_outbox(..., outbox_id=2)` and verifying row 1 is untouched while row 2 is claimed.

---

### DEF-009 — Raw `execution_status` Passed to `state_label()` Instead of `get_status(conv)`

- **Defect ID:** `DEF-009`
- **Title:** UI Formatters and Keyboards Pass Raw `execution_status` to `state_label()` Instead of `get_status(conv)`
- **Severity:** `MEDIUM`
- **Category:** UI Consistency / Status Normalization Bug
- **Affected File(s) and Line(s):**
  - `bot/messages.py:37-48, 56-61` (`get_status`, `state_label`)
  - `bot/messages.py:105` (`format_conversation` passes `conv.get("execution_status")`)
  - `bot/messages.py:138` (`format_conversation_view` passes `conv.get("execution_status")`)
  - `bot/keyboards.py:113` (`conversations_menu` passes `conv.get("execution_status")`)
  - `bot/handlers.py:1377` (`show_status` passes `conv.get("execution_status")`)
- **Symptom:** Four user-facing Telegram views bypass `get_status(conv)` and pass `conv.get("execution_status")` directly to `state_label()`. Any uppercase/mixed-case OpenHands status (`"FINISHED"`, `"RUNNING"`, `"ERROR"`) misses `STATE_LABELS` (showing raw English instead of Arabic), and any conversation with `sandbox_status ∈ {"ERROR", "MISSING"}` (`SANDBOX_ERROR`) shows its old `execution_status` instead of `"خطأ في بيئة التنفيذ"`.
- **Root Cause:** `get_status(conv)` was created as the "single source of truth" (`bot/messages.py:38`) for `Watcher` and `Notifier`, but `format_conversation`, `format_conversation_view`, `conversations_menu`, and `show_status` were never updated to use `get_status(conv)`.
- **Trigger / Reproduction Path:** Open `/start` -> `شاتاتي` or open a conversation or press `الحالة` on an OpenHands conversation whose `sandbox_status` is `"MISSING"` or `"ERROR"`, or whose API returns `"FINISHED"`. Menu shows e.g. `"FINISHED"` or `"مكتمل"` instead of `"خطأ في بيئة التنفيذ"`.
- **User / System Impact:** Misleading conversation status in Telegram menus vs proactive watcher/notifier alerts (`"خطأ في بيئة التنفيذ"`).
- **Data Integrity / Concurrency / Security Impact:** Display-only inconsistency; does not affect DB state transitions.
- **Evidence:** Direct inspection of `bot/messages.py:37-61,105,138`, `bot/keyboards.py:113`, `bot/handlers.py:1377`.
- **Confidence:** `CONFIRMED`
- **Existing Test Coverage Gaps:** `tests/test_messages.py` and `tests/test_keyboards.py` test `STATE_LABELS` with lowercase keys and omit `sandbox_status="ERROR"` cases on `format_conversation_view`/`conversations_menu`.
- **Recommended Fix Direction:** Replace `conv.get("execution_status")` with `get_status(conv)` in `format_conversation`, `format_conversation_view`, `conversations_menu`, and `show_status` (preserving backward compatibility when `conv` only sets `execution_status`).
- **Mini App Exclusion Impact:** `NONE`
- **Dependencies / Blockers:** None.
- **Verification Strategy:** Unit tests for uppercase `execution_status` and `sandbox_status="ERROR"/"MISSING"` on `format_conversation`, `format_conversation_view`, `conversations_menu`, and `show_status`.

---

### DEF-010 — 64-Byte `callback_data` Overflow for Valid 56–64 Character Conversation IDs

- **Defect ID:** `DEF-010`
- **Title:** Telegram 64-Byte `callback_data` Overflow for Valid 56–64 Character Conversation IDs
- **Severity:** `MEDIUM`
- **Category:** Input Bounds / Telegram API Compatibility
- **Affected File(s) and Line(s):**
  - `bot/files.py:29, 36` (`MAX_CONVERSATION_ID_LEN = 64`)
  - `bot/keyboards.py:9-16` (`CALLBACK_DATA_LIMIT = 64`, `_btn` raises `ValueError`)
  - `bot/keyboards.py:94-95` (`open:{cid}` +5 bytes, `unwatch:{cid}` +8 bytes)
  - `bot/keyboards.py:114` (`open:{cid}` +5 bytes)
  - `bot/keyboards.py:138-185` (`unwatch:{cid}` +8, `watch:{cid}` +6, `copy:{cid}`, `full:{cid}`, `txt:{cid}`, `reply:{cid}`, `files:{cid}:0` +8, `cost:{cid}`, `status:{cid}`, `export:{cid}`, `delete:{cid}`)
  - `bot/keyboards.py:193-194` (`deleteok:{cid}` +9 bytes)
  - `bot/keyboards.py:206, 209, 211` (`file:{cid}:{gen}:{idx}` +7+digits, `files:{cid}:{gen}:{page}` +8+digits)
- **Symptom:** Valid OpenHands conversation IDs between 56 and 64 characters pass `is_valid_conversation_id()` (`MAX_CONVERSATION_ID_LEN = 64`) cleanly, yet immediately raise `ValueError("callback_data أطول من 64 بايت")` inside `kb._btn` whenever constructing `conversations_menu`, `watches_menu`, `conversation_actions`, `delete_confirm_menu`, or `files_menu`!
- **Root Cause:** Button prefixes (`deleteok:` = 9 bytes, `unwatch:` = 8 bytes, `files:{cid}:{gen}:{page}` = 8+ bytes) were combined directly with full `conversation_id` strings up to 64 bytes, exceeding Telegram's hard 64-byte `callback_data` limit.
- **Trigger / Reproduction Path:** Upstream OpenHands returns a 60-char conversation ID in `/conversations/search`, or owner taps a conversation with a 58-char ID -> `_btn` throws `ValueError` -> crashes `list_conversations` / `open_conversation` / `delete_conversation_prompt` / `files_page` -> triggers `handle_processing_error` (`FAILED_PERMANENT` -> `DEF-002` polling lock!).
- **User / System Impact:** Complete inability to list, open, reply to, inspect files, or delete any conversation whose valid ID is 56–64 bytes long — and can freeze polling if hit.
- **Data Integrity / Concurrency / Security Impact:** Cascading polling failure (`DEF-002`) triggered by valid upstream ID length.
- **Evidence:** Direct inspection of `bot/files.py:29` (`64`) vs `bot/keyboards.py:9-16, 94-95, 114, 138-211`.
- **Confidence:** `CONFIRMED`
- **Existing Test Coverage Gaps:** `tests/test_keyboards.py` tests short IDs (`"c1"`) and explicit >64-byte overflow rejection, missing tests for boundary valid lengths `56..64`.
- **Recommended Fix Direction:** Introduce a short-token / opaque callback ref mapping (or deterministic short DB/in-memory handle table `callback_refs(token TEXT PRIMARY KEY, conversation_id TEXT)` persisted in SQLite for restart resilience) whenever `len(cid) > 48`, or shorten fixed prefixes + cap/map long IDs cleanly without truncation ambiguity.
- **Mini App Exclusion Impact:** `NONE`
- **Dependencies / Blockers:** SQLite schema addition if persistent callback short-tokens are used (recommended so inline buttons remain valid across bot restarts).
- **Verification Strategy:** Parameterized tests with 64-char `conversation_id` across `conversations_menu`, `watches_menu`, `conversation_actions`, `delete_confirm_menu`, and `files_menu` (including `page=999`, `gen=99`).

---

### DEF-011 — Missing Cross-Download Reservation Lock for Staging Quotas & Misleading Attachment Acceptance UX

- **Defect ID:** `DEF-011`
- **Title:** Missing Cross-Download Reservation Lock for Staging Quotas & Misleading Attachment Acceptance UX
- **Severity:** `MEDIUM`
- **Category:** Concurrency / Resource Quotas / UX Integrity
- **Affected File(s) and Line(s):**
  - `bot/attachments.py:699-735` (`StagingStore.store` checks `quota_block` / `byte_quota_block` / `_effective_cap` sequentially per download without cross-download reservation)
  - `bot/handlers.py:1689, 1714-1990` (`_get_download_semaphore()` allows up to 4 concurrent downloads; `max_batch_items`, `max_batch_bytes`, `max_staging_total_bytes` default to `None` per D-12)
  - `bot/handlers.py:1609-1611` (`ATTACHMENT_ACCEPTED_TEXT` omits that files are staged locally only and not sent to OpenHands)
- **Symptom:**
  1. If `max_batch_items`, `max_batch_bytes`, or `max_staging_total_bytes` are ever configured non-`None` alongside concurrent downloads (`MAX_CONCURRENT_DOWNLOADS = 4`), `StagingStore.store` checks disk occupancy (`quota_block` / `_effective_cap`) *after* `accept` has already inserted `pending` item rows (`row_created=True`) and *without* reserving byte budgets across simultaneous streams, permitting parallel downloads to overshoot aggregate limits.
  2. `ATTACHMENT_ACCEPTED_TEXT` (`"استلمت الملف ✅ — ابعت أوامرك (النص المصاحب) خلال 15 دقيقة من أول ملف."`) gives the user zero indication that remote attachment upload to OpenHands is NOT implemented (`Stage B1/B2` blocked) and that following up with text will trigger `DEF-001` deadlock instead of delivering the file to the agent.
- **Root Cause:** D-12 left batch/total staging caps disabled (`None`) while concurrency mitigation (`_get_download_semaphore`) only throttled simultaneous HTTP streams without a byte/count reservation ledger, and Phase A2 UX copy kept pre-deferment placeholder wording.
- **Trigger / Reproduction Path:** Enable aggregate quotas and send 4 concurrent 3 MB documents while `concurrent_updates(True)` runs concurrently; or send any document on default config and observe `ATTACHMENT_ACCEPTED_TEXT` copy.
- **User / System Impact:** Users believe their document will be delivered to the AI agent after replying with text (`"استلمت الملف ✅ ..."`), when in reality it is stored locally with no remote upload path and permanently bricks text prompts (`DEF-001`).
- **Data Integrity / Concurrency / Security Impact:** Dormant quota overshoot TOCTOU if aggregate caps are turned on; misleading user mental model. Also note `StagingStore._write_to_path` performs synchronous `open`/`write`/`os.fsync` directly inside the `asyncio` event loop (`handlers.py:1941` -> `service.accept` -> `store.store`), briefly blocking heartbeat/poll responsiveness for up to 3 MB writes.
- **Evidence:** Direct inspection of `bot/attachments.py:615-760, 845-974`, `bot/handlers.py:1609-1611, 1689, 1714-1990`.
- **Confidence:** `CONFIRMED`
- **Existing Test Coverage Gaps:** `tests/test_repair_plan_01_resource_staging.py` and `tests/test_repair_plan_01_review_findings.py` test sequential quota calls rather than 4 concurrent async streams competing for `max_staging_total_bytes`.
- **Recommended Fix Direction:** Keep `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=0` (`DEF-001`) until Stage B or Mini App manual transfer exists; if kept enabled, update UX copy truthfully, wrap `StagingStore` disk I/O with `asyncio.to_thread` (or bounded reservation ledger), and add explicit reservation accounting in `StagingStore`.
- **Mini App Exclusion Impact:** `NONE`
- **Dependencies / Blockers:** Tied to `DEF-001` & `DEF-015`.
- **Verification Strategy:** Concurrency test launching 4 simultaneous `accept()` coroutines against `max_staging_total_bytes=4MB` with 2MB files verifying total stored bytes never exceed cap.

---

### DEF-012 — `CreationWorker` Resumed `task_id` `wait_for_start` Missing `CancelledError`/Unexpected-Exception Cleanup

- **Defect ID:** `DEF-012`
- **Title:** `CreationWorker` Resumed `task_id` Branch Lacks `CancelledError` and Non-`ApiError` Exception Handling
- **Severity:** `MEDIUM`
- **Category:** Concurrency / Shutdown Recovery / Worker Lifecycle
- **Affected File(s) and Line(s):**
  - `bot/outbox.py:733-746` (`if job.task_id:` branch in `_start_conversation`)
  - Compare `bot/outbox.py:792-806` (fresh POST branch catches `ApiError` AND `asyncio.CancelledError`)
  - `bot/outbox.py:592-595` (`_BaseWorker._run` swallows non-`CancelledError` unexpected exceptions without resetting claimed status)
- **Symptom:** When `CreationWorker` resumes a `creation_jobs` record that already has a `task_id` (e.g., recovered from `pending` after shutdown):
  1. If `CancelledError` hits `client.wait_for_start(job.task_id)` (`line 735`), it does NOT catch `CancelledError` (unlike `line 801`), leaving the row in `CREATION_CLAIMED` instead of `CREATION_UNKNOWN` (relying silently on `creation_recover` on next boot to reset `claimed` -> `pending` with `task_id` preserved).
  2. If `client.wait_for_start(job.task_id)` (or line 793 fresh `wait_for_start`) raises an unexpected non-`ApiError` exception (e.g. `KeyError`/`TypeError`/`ValueError` on malformed payload), `_BaseWorker._run` catches `Exception` at line `592` and increments `_consecutive_failures`, leaving that `creation_jobs` row **permanently stuck in `CREATION_CLAIMED`** until process restart!
- **Root Cause:** Asymmetric `try/except` in `_start_conversation` (`733-746` vs `792-806`) and absence of `except Exception:` post-CAS fallback (`_post_claimed` has `except Exception` at line `479`, whereas `_start_conversation` does not).
- **Trigger / Reproduction Path:** Malformed JSON/unexpected `ValueError` or `KeyError` returned from `wait_for_start(task_id)` in OpenHands client during creation polling -> `creation_jobs` row stays `claimed` indefinitely until restart.
- **User / System Impact:** Creation job hangs silently with neither a chat link nor an `"unknown"` error notice until restart.
- **Data Integrity / Concurrency / Security Impact:** Preserves `at-most-once` (no duplicate POST because `task_id` is saved), but strands the job row in `claimed` state during uptime.
- **Evidence:** Direct side-by-side comparison of `bot/outbox.py:479-490`, `733-746`, `771-806`, and `592-595`.
- **Confidence:** `CONFIRMED`
- **Existing Test Coverage Gaps:** `tests/test_creation.py` and `tests/test_openhands_http_28d.py` test `ApiError` and `ValueError` on `start_conversation`, not unexpected exceptions inside `wait_for_start`.
- **Recommended Fix Direction:** Add unified `except asyncio.CancelledError` and `except Exception:` post-POST fallback in both `wait_for_start` paths (lines `734` and `792`) transitioning `{CREATION_CLAIMED, CREATION_STARTING}` -> `CREATION_UNKNOWN` + user notice on unexpected errors (and re-raising `CancelledError`).
- **Mini App Exclusion Impact:** `NONE`
- **Dependencies / Blockers:** None.
- **Verification Strategy:** Unit tests for resumed `task_id` raising `CancelledError` and `RuntimeError` during `wait_for_start`, verifying row transitions cleanly to `CREATION_UNKNOWN`.

---

### DEF-013 — Non-Atomic Expired-Awaiting Clear vs Outcome Commit in `handle_text`

- **Defect ID:** `DEF-013`
- **Title:** Non-Atomic Expired-Awaiting State Clear vs `EXPLICITLY_IGNORED` Outcome Commit
- **Severity:** `LOW`
- **Category:** Atomicity / Crash Consistency
- **Affected File(s) and Line(s):**
  - `bot/handlers.py:2253-2261`
- **Symptom:** When `handle_text` detects an expired awaiting state (`reply`/`newchat`/`reposearch`/`route`), it executes `db.clear_awaiting(telegram_id)` (SQLite commit #1), sends the timeout reply, and then calls `mark_explicitly_ignored(update, context)` (SQLite commit #2).
- **Root Cause:** Two separate SQLite transactions without combining them (unlike `consume_one_shot_awaiting` which updates `user_state` and `processed_updates` in one transaction).
- **Trigger / Reproduction Path:** Process crash or `TimedOut` on `reply_text` at line `2256` between line `2255` and line `2260`. On restart, Telegram redelivers the update, `awaiting_state` is now `None`, and line `2287` sends the generic `"ابعت /start للقائمة..."` instead of `"انتهت مهلة التوجيه..."` (minor UX drift; safe against duplicate prompt dispatch).
- **User / System Impact:** Minor UX mismatch on crash-recovery redelivery (and brief extra reply attempt); zero duplicate-prompt risk.
- **Data Integrity / Concurrency / Security Impact:** Low risk; polling stays safe (`outcome=None` -> redelivery -> `EXPLICITLY_IGNORED`).
- **Evidence:** Direct inspection of `bot/handlers.py:2253-2261` vs atomic `consume_one_shot_awaiting` (`bot/db.py`).
- **Confidence:** `CONFIRMED`
- **Existing Test Coverage Gaps:** `tests/test_one_shot_awaiting_atomicity.py` tests live one-shot awaiting consumption, not expired awaiting crash mid-handler.
- **Recommended Fix Direction:** Record `clear_awaiting` + `EXPLICITLY_IGNORED` atomically (or send notice before clearing? Better: keep clear+outcome atomic, then best-effort reply) so restart does not change the UX semantics.
- **Mini App Exclusion Impact:** `NONE`
- **Dependencies / Blockers:** None.
- **Verification Strategy:** Unit test simulating `reply_text` raising `TimedOut` after expiry and verifying durable state & redelivery behavior.

---

### DEF-014 — Excluded Mini App Boundary Coupling: `OHB2-MT-2` Attachment Download Blocked After Text Intent & Unverified WebView Gate

- **Defect ID:** `DEF-014`
- **Title:** Mini App `OHB2-MT-2` Attachment Download Blocked Once Accompanying Text Records `intent_recorded` & Android WebView Gate Unverified
- **Severity:** `MEDIUM`
- **Category:** Feature Integration / Excluded Mini App Boundary
- **Affected File(s) and Line(s):**
  - `bot/web/services.py` (MT-2 download query boundary — excluded from modification)
  - `bot/web/download.py` (excluded from modification)
  - `bot/web/static/attachments.js` (excluded from modification)
  - `bot/db.py:1572-1663` (shared bot DB schema transitions `pending` -> `intent_recorded`)
  - `docs/reviews/OHB2-MT2-COMPLETION-AND-ADVERSARIAL-VERIFICATION.md`
- **Symptom:** Mini App `MT-2` authenticated download only serves attachments in `pending` batches inside the 15-minute window (`T0+15m`). If the user sends accompanying text in Telegram (`intent_recorded`), `MT-2` hides/stops serving the batch (and Telegram prompts brick via `DEF-001`), while Android 12 WebView native file-download compatibility remains `NOT_RUN` (`docs/reviews/OHB2-MT2-COMPLETION-AND-ADVERSARIAL-VERIFICATION.md`).
- **Root Cause:** `OHB2-MT-2` was built as a constrained manual transfer bridge for `pending` batches while remote upload Stage B remained deferred, and the Mini App subsystem is outside current remediation scope.
- **Trigger / Reproduction Path:** Send document -> send text -> open Mini App Attachments section -> batch is in `intent_recorded`, not `pending`.
- **User / System Impact:** Manual attachment download workaround stops working if user follows Telegram's prompt instructions (`ATTACHMENT_ACCEPTED_TEXT`: "send accompanying text within 15m"), compounding `DEF-001`.
- **Data Integrity / Concurrency / Security Impact:** No security regression; downloads remain fail-closed.
- **Evidence:** Direct inspection of `bot/db.py:1493-1663`, `bot/handlers.py:1609-1611`, `docs/reviews/OHB2-MT2-COMPLETION-AND-ADVERSARIAL-VERIFICATION.md`.
- **Confidence:** `CONFIRMED`
- **Existing Test Coverage Gaps:** No cross-layer test exercises Telegram accompanying-text followed by Mini App `MT-2` retrieval; live Android 12 Telegram WebView download UX unverified.
- **Recommended Fix Direction:** **Remediating Mini App routes/UI (`bot/web/*`, `bot/web/static/*`) is `BLOCKED_BY_EXCLUDED_MINI_APP`.** From the non-Mini-App side, disabling `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` by default (`DEF-001`) prevents users from entering this broken workflow until owner decisions reopen Stage B or approve Mini App scope.
- **Mini App Exclusion Impact:** **`BLOCKED_BY_EXCLUDED_MINI_APP`**
- **Dependencies / Blockers:** Absolute Scope Exclusion on Mini App files; Android 12 physical WebView device test required for `MT-2`.
- **Verification Strategy:** Boundary documented in audit; no Mini App changes scheduled in remediation WPs.

---

### DEF-015 — Remote Attachment Delivery (`P0 Stage B1/B2`) Blocked by Missing Upstream Scoped Token & SSRF Allowlist

- **Defect ID:** `DEF-015`
- **Title:** Remote Attachment Delivery (`P0 Stage B1/B2`) Unimplemented / Blocked by Upstream Security Gates
- **Severity:** `HIGH`
- **Category:** Architecture / Missing Core Feature / Security Gate
- **Affected File(s) and Line(s):**
  - `bot/openhands_client.py` (no conversation file-upload / `conversation_url` method implemented)
  - `docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md` (Gate G1 allowlist + T5/T14 scoped upload credential)
  - `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md`
  - `.agent/PROGRESS.md:20-37` (`BLOCKED / DEFERRED BY EXPLICIT PRODUCT DECISION`)
- **Symptom:** The bot accepts and stages Telegram document attachments locally (`A0–A4`), records accompanying text (`A3`), and provides manual Mini App download (`MT-2`), yet **never uploads any file or attachment prompt to OpenHands** (`Stage B1/B2` unimplemented).
- **Root Cause:** Architectural security audit identified two upstream OpenHands blockers: (1) `session_api_key` returned by OpenHands Cloud carries broad execution privileges unsuitable for untrusted/multi-tenant forwarding without a scoped upload token, and (2) `conversation_url` must pass strict origin allowlisting (SSRF prevention) before forwarding bearer tokens or file payloads.
- **Trigger / Reproduction Path:** Any document attachment workflow in OpenHandBot.
- **User / System Impact:** Automated document-to-agent attachment delivery does not work end-to-end; coupled with `DEF-001`, accepting documents actively harms availability.
- **Data Integrity / Concurrency / Security Impact:** Intentionally blocked to prevent SSRF and over-privileged credential forwarding.
- **Evidence:** Complete `bot/openhands_client.py` (no upload method), `docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md`, `.agent/PROGRESS.md:20-37`.
- **Confidence:** `CONFIRMED`
- **Existing Test Coverage Gaps:** N/A (feature intentionally absent/blocked).
- **Recommended Fix Direction:** Keep `Stage B1/B2` deferred/blocked behind `.agent/PROGRESS.md` §32–36 reopen gates; turn off local document intake default (`DEF-001`) so unfinished P0 machinery does not break normal prompting.
- **Mini App Exclusion Impact:** `NONE`
- **Dependencies / Blockers:** Upstream OpenHands Cloud capability (`OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md`) + Owner decision to reopen P0.
- **Verification Strategy:** Verify intake kill switch (`ATTACHMENT_DOCUMENT_INTAKE_ENABLED=0`) cleanly isolates bot runtime until P0 reopen gates are met.

---

### DEF-016 — Hosting Qualification (`HOST-01`/`HOST-02`/`H1`) & Live Enzonic SFTP Verification Unconfirmed

- **Defect ID:** `DEF-016`
- **Title:** Free/Target Hosting Qualification (`HOST-01`, `HOST-02`, Enzonic `H1` Persistence) and Live SFTP Access Remain Unverified
- **Severity:** `HIGH`
- **Category:** Deployment Readiness / Infrastructure / Operations
- **Affected File(s) and Line(s):**
  - `.github/workflows/enzonic-sftp-readonly-check.yml:1-125`
  - `docs/DEPLOY_ENZONIC.md:1-70`
  - `docs/OHB2_ENZONIC_DEPLOYMENT_PREFLIGHT.md:1-426`
  - `docs/OHB2_KATABUMP_H1_VALIDATION.md:1-349`
  - `docs/OHB2_HOSTING_DECISION.md:1-358`
  - `tools/katabump-sqlite-canary/canary.py:1-245`
- **Symptom:** Production deployment persistence (`SQLite` durability across container restarts/redeployments — Hypothesis `H1`), Mini App HTTPS reverse-proxy ingress (`HOST-02`), and actual read-only SFTP authentication to `us-four.enzonic.com:2022` via `.github/workflows/enzonic-sftp-readonly-check.yml` have **never executed against the live target environment**, and the workflow's pinned SSH host fingerprint (`SHA256:6MPMP1TJ75QuFqne7qrvN4+7vMW4tFvokGhmIE74fls`) is flagged as not independently verified out-of-band.
- **Root Cause:** Local execution environment lacks SFTP egress/live credentials, and Enzonic hosting canary/panel verification remains pending operator execution.
- **Trigger / Reproduction Path:** Attempt production deploy or trigger `enzonic-sftp-readonly-check.yml` without `ENZONIC_SSH_PRIVATE_KEY` configured / verified fingerprint.
- **User / System Impact:** Cannot certify production persistence (`SQLite` state loss would wipe `outbox`, `creation_jobs`, `deleted_conversations`, and `processed_updates` -> `DEF-001`/duplicate risks) or Mini App HTTPS reachability (`HOST-02`).
- **Data Integrity / Concurrency / Security Impact:** Losing SQLite on ephemeral hosting breaks all `at-most-once` and `deleted_conversations` tombstone guarantees.
- **Evidence:** `docs/OHB2_ENZONIC_DEPLOYMENT_PREFLIGHT.md`, `docs/DEPLOY_ENZONIC.md`, `docs/reviews/OHB2-PLAN04-HOST01-HOSTING-QUALIFICATION.md`, `docs/reviews/OHB2-PLAN04-HOST02-ACTIVATION-READINESS.md`, `.github/workflows/enzonic-sftp-readonly-check.yml`.
- **Confidence:** `CONFIRMED`
- **Existing Test Coverage Gaps:** Canaries are offline/standalone scripts; live Enzonic runtime durability is untested.
- **Recommended Fix Direction:** Execute `enzonic-sftp-readonly-check.yml` with out-of-band verified Enzonic host key fingerprint + `ENZONIC_SSH_PRIVATE_KEY` secret; run `tools/katabump-sqlite-canary/canary.py` on target host across restart/redeploy before promoting any bot runtime.
- **Mini App Exclusion Impact:** `NONE` (deployment infrastructure only; `HOST-02` Mini App HTTPS ingress cannot modify Mini App code).
- **Dependencies / Blockers:** External credentials, panel access, and Enzonic hosting operator action.
- **Verification Strategy:** Green GitHub Actions SFTP read-only check run + multi-restart `canary.py` persistence report.

---

### DEF-017 — Severe Documentation, Runbook, and Startup Contract Drift

- **Defect ID:** `DEF-017`
- **Title:** Critical Contradictions and Omissions Across `ZERO_TOUCH_STARTUP.md`, `OPERATIONS_RUNBOOK.md`, `README.md`, and `API_NOTES.md`
- **Severity:** `MEDIUM`
- **Category:** Documentation / Operational Runbook Integrity
- **Affected File(s) and Line(s):**
  - `docs/ZERO_TOUCH_STARTUP.md:242` (§5b.4 falsely states *"Local deletion does not permanently delete the remote OpenHands conversation, and no claim is made that it does"* — directly contradicting `bot/deletion.py`, `bot/openhands_client.py:341-362`, `README.md:12`, `docs/API_NOTES.md:43-56`)
  - `docs/ZERO_TOUCH_STARTUP.md:52-53` (endpoint expectations vs actual `/health`, `/ready`, `/status` in `bot/web/app.py:305-307`)
  - `docs/ZERO_TOUCH_STARTUP.md` env list (omits `ATTACHMENT_DOCUMENT_INTAKE_ENABLED`, `MINI_APP_TRUSTED_PROXIES`)
  - `docs/OPERATIONS_RUNBOOK.md` §3 (omits `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` and all 12 `MINI_APP_*` env vars), §4 (omits 13 SQLite tables: `completion_pending`, `settings`, `notification_state`, `notifier_pending`, `notifier_retry_not_before`, `notification_inbox`, `deleted_conversations`, `web_sessions`, `processed_updates`, `update_failures`, `attachment_batches`, `attachment_items`, `attachment_message_identity`), §9 (`362` omits `notification_inbox` persistence/recovery)
  - `README.md:70-89` (omits `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` present in `.env.example` and `MINI_APP_TRUSTED_PROXIES`)
  - `docs/API_NOTES.md:81` (cites OpenAPI `1.68.1` vs `bot/openhands_client.py:344` `1.79.0` vs ADR `1.87.1`)
- **Symptom:** Operators following `OPERATIONS_RUNBOOK.md` or `ZERO_TOUCH_STARTUP.md` receive materially wrong instructions (claiming conversation delete is local-only when it actually sends `DELETE` to OpenHands Cloud, missing 13 DB tables during backup/inspection/recovery, and missing config flags in deployment manifests).
- **Root Cause:** Incremental stabilization and P0/Mini App phases updated code and `.env.example` faster than top-level operator documentation was reconciled (`PLAN16` only patched selected paragraphs).
- **Trigger / Reproduction Path:** Compare `docs/ZERO_TOUCH_STARTUP.md:242` with `bot/deletion.py`; compare `docs/OPERATIONS_RUNBOOK.md` §4 with `bot/db.py` schema lines `580-950`.
- **User / System Impact:** High risk of accidental remote conversation deletion (if operator trusts §5b.4), incomplete SQLite diagnostics/recovery, and misconfigured deployments.
- **Data Integrity / Concurrency / Security Impact:** Operational/human-error risk leading to unintended remote data loss or broken backup/restore procedures.
- **Evidence:** Direct inspection of `bot/db.py:580-950`, `bot/deletion.py`, `bot/config.py`, `bot/web/app.py:305-307`, `.env.example`, and all 4 doc files cited above.
- **Confidence:** `CONFIRMED`
- **Existing Test Coverage Gaps:** `tests/test_deploy_manifest.py` and `tests/test_zero_touch_contract.py` validate `README`/`.env.example`/manifest parity selectively, missing `ATTACHMENT_DOCUMENT_INTAKE_ENABLED`, `MINI_APP_TRUSTED_PROXIES`, and `OPERATIONS_RUNBOOK.md` schema parity.
- **Recommended Fix Direction:** Synchronize `ZERO_TOUCH_STARTUP.md`, `OPERATIONS_RUNBOOK.md`, `README.md`, and `API_NOTES.md` with actual `bot/db.py` (all 19 tables), `bot/config.py` (all env vars), `bot/deletion.py` (remote DELETE + local tombstone), and `bot/web/app.py` (`/health`, `/ready`, `/status`), and add a manifest doc-sync regression check covering `.env.example` vs `README.md` vs `OPERATIONS_RUNBOOK.md`.
- **Mini App Exclusion Impact:** `NONE` (updates bot/ops documentation only; does not modify `docs/MINI_APP.md` or Mini App code).
- **Dependencies / Blockers:** None.
- **Verification Strategy:** Add automated test asserting every env var in `bot/config.py` / `.env.example` is documented in `README.md` and `OPERATIONS_RUNBOOK.md`, and every table in `bot/db.py` appears in `OPERATIONS_RUNBOOK.md` §4.

---

### DEF-018 — Co-Existing Unwired AI Studio React/Vite Scaffold & Missing Explicit `anyio` Check in `start.sh`

- **Defect ID:** `DEF-018`
- **Title:** Co-Existing Unwired AI Studio React/Vite Scaffold (`NON_RUNTIME`) & Missing Explicit `anyio` Guard in `start.sh`
- **Severity:** `LOW`
- **Category:** Repository Hygiene / Packaging / Startup Preflight
- **Affected File(s) and Line(s):**
  - `package.json:1-35`, `vite.config.ts:1-22`, `tsconfig.json:1-28`, `index.html:1-19`, `metadata.json:1-7`, `src/App.tsx:1-9`, `src/main.tsx:1-6`, `src/index.css:1-2`, `bun.lock` (`NON_RUNTIME` React+Vite scaffold unrelated to OpenHandBot)
  - `start.sh:56` (checks `telegram`, `httpx`, `dotenv`, `starlette`, `uvicorn`, omitting `anyio`)
- **Symptom:** (1) An unused empty React 19 / Express / `@google/genai` / Vite template sits at repository root alongside the real Python OpenHandBot runtime (`main.py`, `bot/`), creating confusion about repo ownership and build targets (already flagged in `docs/decisions/owner-briefs/OHB2-PLAN04-UI01-FRONTEND-AUTHORITY.md`). (2) `start.sh:56` checks 5 runtime modules before launch but does not check `anyio` explicitly (which `bot/` uses via Starlette/httpx).
- **Root Cause:** Workspace originated from an AI Studio Build template (`package.json`, `src/*`) onto which the OpenHandBot repository was imported, plus incomplete module list in `start.sh:56`.
- **Trigger / Reproduction Path:** Inspect root directory (`package.json` vs `requirements.txt`), or install broken partial deps missing `anyio` and run `sh start.sh`.
- **User / System Impact:** Repository confusion for maintainers/CI; negligible impact on normal installs (`starlette` pulls `anyio`).
- **Data Integrity / Concurrency / Security Impact:** None directly, though `package.json` declares unused npm deps (`@google/genai`, `express`, `vite`, etc.) that aren't part of OpenHandBot's runtime attack surface.
- **Evidence:** Direct inspection of `package.json`, `src/App.tsx`, `src/main.tsx`, `docs/decisions/owner-briefs/OHB2-PLAN04-UI01-FRONTEND-AUTHORITY.md`, and `start.sh:56`.
- **Confidence:** `CONFIRMED`
- **Existing Test Coverage Gaps:** `tests/test_start_script.py` verifies the 5 listed modules in `start.sh:56` without testing `anyio`.
- **Recommended Fix Direction:** Keep `NON_RUNTIME` AI Studio files untouched unless owner explicitly authorizes cleanup outside AI Studio platform contract (`metadata.json`/`index.html` platform requirements noted); optionally add `anyio` to `start.sh:56` if `requirements.txt` pins/uses it.
- **Mini App Exclusion Impact:** `NONE`
- **Dependencies / Blockers:** Platform runtime constraints (`metadata.json`, `index.html`, `package.json` expected by AI Studio environment — do not delete without explicit approval).
- **Verification Strategy:** Update `tests/test_start_script.py` if `start.sh:56` is extended.

---

### DEF-019 — Python Test Suite, Static Analysis, and Dependency SCA Blocked in Current Container Environment

- **Defect ID:** `DEF-019`
- **Title:** Full Python Test Suite (`pytest`), Lint (`pyflakes`), SAST (`bandit`), and SCA (`pip_audit`) Cannot Execute in Current Container
- **Severity:** `HIGH`
- **Category:** Verification / CI & Tooling Environment
- **Affected File(s) and Line(s):**
  - `requirements.txt:1-10`, `requirements-dev.txt:1-10`
  - `.github/workflows/ci.yml:1-68`
  - `tests/test_*.py` (108 Python test files / 165 `.py` files total across repo)
- **Symptom:** The active audit container has only Python `3.10.12` (stdlib) and Node.js `v22.23.2`. `python3.11+`, `.venv`, `pytest`, `pyflakes`, `bandit`, `pip_audit`, `python-telegram-bot`, `httpx`, `starlette`, `uvicorn`, `python-dotenv`, and `anyio` are absent. While Node frontend tests execute cleanly (`node --test tests/frontend/*.test.js` -> `280 pass / 0 fail`) and `ast.parse` confirms `165/165` `.py` files are syntactically valid (`0` syntax errors), runtime execution of the Python test suite and static security checks is `BLOCKED / NOT_RUN` locally.
- **Root Cause:** Container lacks Python >= 3.11 and installed Python dependencies from `requirements-dev.txt` (and `.git` / `gh` workflow logs are absent).
- **Trigger / Reproduction Path:** Run `python3 -m pytest -q` or `sh start.sh` inside current container.
- **User / System Impact:** Python behavioral tests and security scanners cannot be independently re-verified locally during this audit; prior green results recorded in `docs/reviews/*` cannot substitute for live re-execution after audit or before release.
- **Data Integrity / Concurrency / Security Impact:** Unverified live execution of `pytest`, `pyflakes`, `bandit`, and `pip_audit` creates a verification blind spot for runtime regressions and CVE advisories.
- **Evidence:** Observed container environment (`python3 --version` -> `3.10.12`, AST check `165/165` files valid, `node --test tests/frontend/*.test.js` -> `280 pass / 0 fail`), vs `.github/workflows/ci.yml` requiring Python `3.11` & `3.13`.
- **Confidence:** `CONFIRMED`
- **Existing Test Coverage Gaps:** Live execution gap (environment), separate from code coverage gaps noted in `DEF-001`..`DEF-013`. Note also `tests/test_d1_extended_transient_codes.py:348` and `tests/test_frontend_ops.py:21` carry legitimate conditional `skip`/`skipif` markers.
- **Recommended Fix Direction:** Run all CI verification (`pytest -q`, `pyflakes`, `bandit -lll -s B613`, `pip_audit -r requirements-dev.txt`, `node --test tests/frontend/*.test.js`) via `.github/workflows/ci.yml` on Python `3.11` & `3.13` (or local Termux/container venv matching `requirements-dev.txt`) as a mandatory gate for every remediation WP.
- **Mini App Exclusion Impact:** `NONE`
- **Dependencies / Blockers:** Python 3.11+ toolchain / GitHub Actions CI execution.
- **Verification Strategy:** Require green `CI` workflow run (`.github/workflows/ci.yml`) covering both `python` and `frontend` jobs before any remediation release gate passes.
