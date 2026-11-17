# OHB2 Authoritative Corrected Remediation Baseline

**Task ID:** `OHB2-REMEDIATION-BASELINE-CONSOLIDATION`  
**Baseline Date:** 2026-11-17  
**Project Root Observed:** `/app/applet`  
**Observable Environment:** `Python 3.11.2` (`main, Oct 7 2026, 12:35:07`), `Node v22.23.2`, `.git` absent (`git_exists: False`)  
**Status:** **`PLANNING_BASELINE_ONLY — NOT IMPLEMENTATION AUTHORIZATION`**

---

## A. Authority and Status

### A.1 Consolidated Document Sources
This document establishes the single authoritative remediation baseline for **OpenHandBot** by consolidating:
1. The six original audit and planning reports under `docs/audits/`:
   - `docs/audits/OHB2-AUDIT-EXECUTIVE-SUMMARY.md`
   - `docs/audits/OHB2-COMPLETE-REPOSITORY-AUDIT.md`
   - `docs/audits/OHB2-COMPLETE-DEFECT-REGISTER.md`
   - `docs/audits/OHB2-INCOMPLETE-FEATURES.md`
   - `docs/audits/OHB2-REMEDIATION-MASTER-PLAN.md`
   - `docs/audits/OHB2-FILE-BY-FILE-AUDIT.md`
2. The independent adversarial validation report:
   - `docs/audits/OHB2-INDEPENDENT-AUDIT-REPORT-VALIDATION.md`

### A.2 Authority, Supersession, and Non-Modification Policy
- **Supersession:** Where any specification, count, line scope, feature classification, dependency ordering, or technical assumption in the six original audit reports conflicts with `OHB2-INDEPENDENT-AUDIT-REPORT-VALIDATION.md` or with this document, **this document supersedes the conflicting implementation guidance**.
- **Preservation of Historical Records:** None of the seven pre-existing audit reports have been rewritten or altered; their historical audit findings remain intact as archival inputs.
- **Authorization Boundary:** This document is a **planning and engineering specification baseline only**. It does **NOT** authorize code modification, dependency installation, configuration changes, Git operations, deployments, or execution of any work package (`WP-01`..`WP-10`). Explicit owner approval is required before implementation begins (and specifically for the owner decisions cataloged in Section H).
- **Strict Mini App Exclusion:** The Telegram Mini App subsystem (`bot/web/*`, `bot/web/static/*`, `tests/frontend/*`, `tests/test_miniapp_*.py`, `tests/test_real_http_miniapp_download.py`, `tests/_miniapp_helpers.py`, `docs/MINI_APP.md`, and `Config.mini_app_*` fields) is **`EXCLUDED_MINI_APP`** and must not be modified. Cross-boundary dependencies discovered via read-only inspection are documented explicitly and gated on owner decisions.

### A.3 Observable Workspace & Git Limitations
- **Actual Project Root:** `/app/applet`.
- **Git Metadata:** `.git` directory is absent (`git_exists: False`). Commit history, branch names, working-tree cleanliness (`git status` / `git diff`), and remote CI run logs cannot be verified locally in this environment.
- **Audit Package Inventory:** All 7 existing files under `docs/audits/` (`6` prior audit/plan docs + `OHB2-INDEPENDENT-AUDIT-REPORT-VALIDATION.md`) were verified present on disk prior to creating this file.
- **Runtime / Package State:** `Python 3.11.2` and `Node v22.23.2` are present. Runtime/dev Python packages (`pytest`, `pyflakes`, `bandit`, `pip_audit`, `telegram`, `httpx`, `starlette`, `uvicorn`, `dotenv`, `anyio`) are absent.

---

## B. Corrected Factual Baseline

Every remediation work package (`WP-01`..`WP-10`) and parity check must use these source-verified facts instead of the superseded claims from the original audit package:

1. **Container Python Version:** The active container executes **`Python 3.11.2`** (not `3.10.12`). Python `>= 3.11` (`bot/bootstrap.py::MIN_PYTHON`) is satisfied by the interpreter; local Python CI/runtime gates are blocked solely because the virtual environment and the `10` third-party packages from `requirements.txt` / `requirements-dev.txt` are not installed.
2. **SQLite Schema Table Count:** `Database._init_schema()` (`bot/db.py:590-816`) defines **`17` tables** (not `19`): `watched`, `user_state`, `outbox`, `creation_jobs`, `completion_pending`, `settings`, `notification_state`, `notifier_pending`, `notifier_retry_not_before`, `notification_inbox`, `deleted_conversations`, `web_sessions`, `processed_updates`, `update_failures`, `attachment_batches`, `attachment_items`, `attachment_message_identity`. `docs/OPERATIONS_RUNBOOK.md` §4 (`lines 73-74`) lists `4` tables and omits `13` (`4 + 13 = 17`); across the full runbook (`§§5–8`), `6` tables appear and `11` are missing (`settings`, `notification_state`, `notifier_pending`, `notifier_retry_not_before`, `notification_inbox`, `deleted_conversations`, `web_sessions`, `update_failures`, `attachment_batches`, `attachment_items`, `attachment_message_identity`).
3. **Feature Visibility State:** `bot/features.py:15` sets **`DEFERRED_FEATURES_HIDDEN = False`**. Therefore `is_hidden(feature)` (`bot/features.py:20-22`) returns `False` for `"files"`, `"export"`, `"cost"`, and `"followups"`, making all four active, rendered, and live-reachable in Telegram keyboards and handlers (`README.md` / `bot/app.py`).
4. **Already-Migrated Operational Failure Propagation:** In `bot/handlers.py`, both **`list_conversations` (`L917`)** and **`_show_repos` (`L2446`)** already call `await _raise_if_operational_api_failure(exc)` inside their `except ApiError:` handlers, so `5xx`/`429`/network failures in those two functions already propagate rather than being swallowed into `EXPLICITLY_IGNORED`.
5. **Exact `_ACK_ELIGIBLE` Outcome Set:** `bot/update_outcomes.py:40-48` defines `_ACK_ELIGIBLE` strictly as `{DURABLE_COMPLETED, DURABLE_INTENT_RECORDED, EXPLICITLY_IGNORED, DUPLICATE_COMPLETED, REJECTED_INELIGIBLE}`. Constants named `AMBIGUOUS_EXTERNAL` and `DISPLAY_FAILED` do **not** exist; `handlers.mark_ambiguous_external` records `PARTIAL_OR_UNKNOWN` (`bot/handlers.py:604`) and `handlers.mark_display_failed` records `FAILED_TRANSIENT` (`bot/handlers.py:626`), both of which belong to fail-closed `_INELIGIBLE` (`bot/update_outcomes.py:51-53`).
6. **`STATE_LABELS` Missing `"unknown"` Key:** `bot/messages.py:20-30` maps **`None: "غير معروف"`** and does **not** define an `"unknown"` key. Meanwhile `get_status(conv)` (`bot/messages.py:37-48`) converts missing `execution_status` (`None`) into lowercase string `"unknown"` (`L44`). Calling `state_label(get_status({}))` currently renders literal `"unknown"` instead of `"غير معروف"` until `"unknown": "غير معروف"` is added to `STATE_LABELS`.
7. **`notifications_toggle:857` Semantics:** In `bot/handlers.py:855-858`, `new_state is None` is the **duplicate `update_id` short-circuit** (`bot/db.py:4268-4270`), not a database-failure branch.

---

## C. Unified Defect Register (`DEF-001`..`DEF-019` + `NEW-DEF-01`..`NEW-DEF-08`)

Confidence legend: `CONFIRMED` (directly verified in source), `CONFIRMED_WITH_SCOPE_CORRECTION` (verified with narrowed/corrected scope), `UNVERIFIED_EXTERNAL` (code path verified, live runtime/external behavior unverified locally).

### C.1 Original Audit Defects (`DEF-001`..`DEF-019`)

#### `DEF-001` — Permanent Normal Text-Prompt Self-DoS ("Owner Brick") After Any Document Attachment
- **ID:** `DEF-001`
- **Category:** State Machine / Feature Integration / Operational Availability (Runtime Defect)
- **Severity:** `CRITICAL`
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `bot/config.py:43,315-317`; `bot/handlers.py:1885,2052-2204,2245,2291-2309`; `bot/db.py:812-814,1364-1395,1493-1663`; `bot/attachments.py:1095-1115`
- **Root Cause:** `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` defaults to `True` even though Stage B remote upload (`DEF-015`) is unimplemented. Any uploaded document enters `attachment_batches`; sending text within 15m triggers `record_attachment_intent` -> `intent_recorded` (`UNRESOLVED`, skipped by `AttachmentReaper` forever), while letting it expire -> `expired` triggers D-34 `TERMINAL_UNPROVEN` (`bot/db.py:1557-1569`), both scoped globally by `telegram_id` across all conversations. `handle_text:2245` invokes `_handle_accompanying_text` unconditionally without checking `attachment_document_intake_enabled`, and `/cancel` only clears `user_state`.
- **User / System Impact:** After one document upload, all subsequent normal text prompts across every conversation (and `/newchat`/`reposearch`) are permanently rejected. Setting `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=0` later still does not unbrick an already-affected owner.
- **Dependencies:** Interacts with `DEF-015` (Stage B blocked), `DEF-014` (`MT-2`), `NEW-DEF-06` (`UNSUPPORTED_ATTACHMENT_TEXT`), and `WP-07` concurrency safety.
- **Proposed Remediation:** See `WP-01` (change flag default only under owner sign-off; bypass/reconcile `_handle_accompanying_text` safely; add DB-first idempotent `/cancel` batch abandonment; reconcile D-34 `TERMINAL_UNPROVEN` under owner sign-off).
- **Required Regression Tests:** Multi-turn E2E tests covering `intent_recorded` -> `/cancel` -> prompt in Conv B; expired batch recovery (if D-34 approved); disabled-flag unbrick of pre-existing `expired`/`intent_recorded` DBs; preserving valid `TERMINAL_ASSOCIATED` dedupe.
- **Owner Approval Requirements:** **REQUIRED** (`Decision #1`: modifying D-34 `TERMINAL_UNPROVEN` semantics per `AGENTS.md` §14; `Decision #3`: changing `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` default because it alters excluded Mini App `MT-2` availability).
- **Mini App Cross-Boundary Implications:** **HIGH (`MT-2` Coupling).** `bot/web/services.py:758-870` (`list_staged_attachments`, `download_attachment`) reads `attachment_batches` created solely by Telegram `handle_attachment`. Disabling `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` by default silences `MT-2` staged attachment intake unless explicitly enabled by config (`Owner Decision #3`).

#### `DEF-002` — Head-of-Line Polling Offset Deadlock on `FAILED_PERMANENT` & Transient Exception Misclassification
- **ID:** `DEF-002`
- **Category:** Polling / Telegram ACK Reliability / Error Classification (Runtime Defect)
- **Severity:** `HIGH`
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `bot/update_outcomes.py:40-53,93-110`; `bot/polling.py:155-173,202-208`; `bot/handlers.py:477-495,1150-1154,1468,1567`
- **Root Cause:** `_ACK_ELIGIBLE` excludes `FAILED_PERMANENT`, `acknowledgment_boundary` stalls at the first ineligible update, and ADR §28.4 manual poison quarantine/skip was never implemented. Simultaneously, `_classify_failure` (`bot/handlers.py:488-495`) classifies all exceptions other than `CancelledError`, transient `sqlite3.Error`, and non-permanent `ApiError` as `FAILED_PERMANENT` — including transient `telegram.error.*`, `asyncio.TimeoutError`, and `httpx.TransportError`.
- **User / System Impact:** Any transient Telegram network timeout or deterministic permanent error (`TextDocumentTooLargeError`) locks `TelegramPoller._next_offset` indefinitely across restarts until Telegram 24h update expiry or manual SQLite edits.
- **Dependencies:** Triggered/amplified by `DEF-005`, `DEF-010`, `NEW-DEF-01`, and `NEW-DEF-04`.
- **Proposed Remediation:** See `WP-04` (context-aware transient classification; ADR §28.4 manual `/updates_status` + `/updates_skip` with explicit owner confirmation and auditability).
- **Required Regression Tests:** `_classify_failure` tests for `RetryAfter`/`TimedOut`/`NetworkError`/`BadRequest`/`asyncio.TimeoutError`/`httpx.TransportError`/scoped `OSError`; polling quarantine & boundary-advance tests.
- **Owner Approval Requirements:** **REQUIRED** (`Decision #2`: ADR §28.4 poison-update manual skip policy per `AGENTS.md` §14).
- **Mini App Cross-Boundary Implications:** `NONE` (polling layer only; Mini App uses ASGI HTTP).

#### `DEF-003` — Missing Outcome (`outcome=None` -> Ack Block) & `reposearch` Error/Expiry Handling
- **ID:** `DEF-003`
- **Category:** Handler Outcome Contract / Control Flow (Runtime Defect)
- **Severity:** `HIGH`
- **Validation Verdict:** `CONFIRMED_WITH_SCOPE_CORRECTION`
- **Exact Source Location:** `bot/handlers.py:2275-2283` (`handle_text` `reposearch`), `2351-2354` (`_send_prompt`), `2534-2536` (`_start_new_chat`), `2795-2798` (`outbox_mark_sent`); `(already fixed for 5xx: 2446 _show_repos)`
- **Root Cause:** `outbox_mark_sent:2795-2798` (`status_now == final`) returns without recording any outcome (`outcome=None` -> `PARTIAL_OR_UNKNOWN` ack block). `handle_text:2278-2283` calls `consume_one_shot_awaiting` unconditionally after `_show_repos` returns from a **4xx** `ApiError` (wiping `reposearch` state) and ignores `False` return values on expiry/race at `L2281` (leaving `outcome=None`). **Scope Correction:** `_show_repos` (`L2446`) already propagates `5xx`/`429`/timeout via `_raise_if_operational_api_failure`, so `5xx` does NOT reach `L2281`. `_send_prompt:2351-2354` (`out_id == 0`) and `_start_new_chat:2534-2536` (`job_id == 0`) rely on concurrent-winner durable commit; race paths must be verified/explicit.
- **User / System Impact:** `outcome=None` traps polling offset via `PARTIAL_OR_UNKNOWN`; `reposearch` loses user state on 4xx or expiry race.
- **Dependencies:** Coordinates with `WP-02`/`WP-04` (`bot/handlers.py` shared module).
- **Proposed Remediation:** See `WP-03` (add `mark_explicitly_ignored` on `outbox_mark_sent:2795-2798` and `consume_one_shot_awaiting == False`; preserve `reposearch` when `_show_repos` fails with 4xx; assert outcome coverage on `out_id == 0`/`job_id == 0`).
- **Required Regression Tests:** Branch tests for `outbox_mark_sent` CAS race (`status_now == final`), `reposearch` 4xx preservation & expiry-`False`, and concurrent `out_id==0`/`job_id==0` outcomes.
- **Owner Approval Requirements:** `NONE` (enforces existing Stage 2 outcome contract).
- **Mini App Cross-Boundary Implications:** `NONE` (Telegram bot handlers only).

#### `DEF-004` — Incomplete `Stage4-F1` Operational Failure Propagation & Unguarded `send_document`
- **ID:** `DEF-004`
- **Category:** Error Propagation / Fail-Closed ACK Semantics (Runtime Defect)
- **Severity:** `HIGH`
- **Validation Verdict:** `CONFIRMED_WITH_SCOPE_CORRECTION`
- **Exact Source Location:** `bot/handlers.py:1129-1142` (`send_reply_txt`), `1206-1212` (`watch_conversation`), `1276-1282` (`delete_conversation_prompt`), `1307-1318` (`delete_conversation_confirm`), `1449-1468` (`export_conversation`), `1567` (`show_file`), `1585-1591` (`reply_prompt`); `(already fixed: 917 list_conversations, 2446 _show_repos)`
- **Root Cause:** 5 handlers call `_authorized_conversation(...)` instead of `_authorized_conversation_status(...)`, swallowing `5xx`/`429` into `EXPLICITLY_IGNORED`. `delete_conversation_confirm:1307-1318` calls `_authorized_conversation_status` yet ignores `_auth_exc` when returning `mark_explicitly_ignored` at `L1317`. Additionally, `send_reply_txt:1141` and `export_conversation:1465` record `PARTIAL_OR_UNKNOWN` (`mark_ambiguous_external`) on read/export API failures rather than operational `FAILED_TRANSIENT`, and `export_conversation:1468`/`show_file:1567` lack `try/except TelegramError` around `send_document`. **Scope Correction:** `list_conversations:917` and `_show_repos:2446` already propagate operational `ApiError` via `_raise_if_operational_api_failure`.
- **User / System Impact:** Transient `5xx`/`429` errors during those 6 authorization paths permanently ACK/drop updates instead of failing closed; `send_document` failures crash into `FAILED_PERMANENT`.
- **Dependencies:** Coordinates with `WP-02` and `WP-04` (`bot/handlers.py`, `_classify_failure`).
- **Proposed Remediation:** See `WP-03` (migrate 5 callers + `delete_conversation_confirm:1317`; align `send_reply_txt`/`export_conversation` failure outcomes; guard `send_document` with `mark_display_failed`).
- **Required Regression Tests:** Parameterized `503` vs `404` tests across all 6 authorization sites and `TelegramError` tests for `send_document`.
- **Owner Approval Requirements:** `NONE` (`Stage4-F1` parity; confirm read-only menu retry policy fits ADR §30).
- **Mini App Cross-Boundary Implications:** `NONE`.

#### `DEF-005` — Unwrapped `await q.answer()` Across 24 of 28 Callback Call Sites
- **ID:** `DEF-005`
- **Category:** Error Handling / Telegram Callback Lifecycle (Runtime Defect)
- **Severity:** `HIGH`
- **Validation Verdict:** `CONFIRMED` *(evidence note: `L857` is duplicate `update_id` short-circuit, not DB-fail)*
- **Exact Source Location:** `bot/handlers.py` bare sites (`780,799,834,850,857,893,965,1033,1072,1167,1195,1229,1266,1296,1439,1477,1526,1575,2302,2380,2401,2424,2473,2500`) vs wrapped (`866,1120,1348,1402`)
- **Root Cause:** 24 of 28 `q.answer()` sites lack `try/except`, and most invoke `q.answer()` before `_allowed(...)`.
- **User / System Impact:** Stale inline buttons (`BadRequest: Query is too old` after backlog/restart) or `TimedOut` abort handlers before outcome commit -> `FAILED_PERMANENT` -> polling deadlock (`DEF-002`).
- **Dependencies:** Pairs directly with `NEW-DEF-01` in `WP-02` and reduces triggers for `DEF-002`.
- **Proposed Remediation:** See `WP-02` (`_safe_answer` helper across all 28 sites; auth before UI side effects; never catch `CancelledError`).
- **Required Regression Tests:** Parameterized test across every `CallbackQueryHandler` raising `BadRequest("Query is too old")` / `TimedOut` on `q.answer()`.
- **Owner Approval Requirements:** `NONE`.
- **Mini App Cross-Boundary Implications:** `NONE`.

#### `DEF-006` — Custom Poller Batch Serialization vs `concurrent_updates(True)` Rationale
- **ID:** `DEF-006`
- **Category:** Concurrency / Responsiveness / Architecture Alignment (Runtime / Architecture)
- **Severity:** `MEDIUM`
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `bot/polling.py:161-162,175-178` vs `bot/app.py:75-87`; `docs/OPERATIONS_RUNBOOK.md:123-127`
- **Root Cause:** `TelegramPoller.process_updates` loops `await self.dispatch_and_wait(update)` sequentially, neutralizing `concurrent_updates(True)` within multi-update batches, while `bot/app.py:75-87` still claims intra-batch non-blocking concurrency (`OPERATIONS_RUNBOOK.md:123-127` already documents sequential dispatch).
- **User / System Impact:** A slow command/callback delays `"وصل ✅"` prompt receipt for later updates in the same `getUpdates` batch. Conversely, enabling raw concurrency without per-user locks risks SQLite `Database` (`self._conn`) contention and `user_state`/`attachment_batches` races.
- **Dependencies:** Blocked by `WP-01` and requires SQLite single-connection + per-user serialization proof (`WP-07`).
- **Proposed Remediation:** See `WP-07` (preserve sequential dispatch and align `bot/app.py:75-87` comments unless concurrency + SQLite connection safety + per-user ordering are rigorously proven).
- **Required Regression Tests:** Ordering/serialization tests (or timing + race tests if concurrency is approved).
- **Owner Approval Requirements:** **REQUIRED if changing architecture (`Decision #4`: enabling concurrent update dispatch per `AGENTS.md` §14).** `NONE` if keeping sequential polling and aligning `bot/app.py` documentation.
- **Mini App Cross-Boundary Implications:** Low/indirect (`bot/web/runner.py` shares the same event loop and `Database` connection when Mini App is enabled; shared-connection safety checks apply if concurrent DB writes increase).

#### `DEF-007` — `Watcher.tick` and `Notifier._process` Missing `continue`/`return` After `clear_retry_not_before` Failure
- **ID:** `DEF-007`
- **Category:** Notification Reliability / Control Flow (Runtime Defect)
- **Severity:** `MEDIUM`
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `bot/watcher.py:215-221`; `bot/notifier.py:522-528`
- **Root Cause:** Both catch `clear_retry_not_before` exceptions, log `"هيتخطّى"` ("will skip"), and omit `continue` (`watcher.py:221`) / `return` (`notifier.py:528`).
- **User / System Impact:** Logs a skip while falling straight into notification delivery anyway.
- **Dependencies:** Independent (`WP-05`).
- **Proposed Remediation:** See `WP-05` (insert `continue` in `bot/watcher.py:221` and `return` in `bot/notifier.py:528`).
- **Required Regression Tests:** Inject `sqlite3.OperationalError` into `clear_retry_not_before` and verify 0 notifications/DB writes in that pass.
- **Owner Approval Requirements:** `NONE`.
- **Mini App Cross-Boundary Implications:** `NONE`.

#### `DEF-008` — `deliver_outbox(outbox_id)` Helper Ignores Target `outbox_id` and `mature_before`
- **ID:** `DEF-008`
- **Category:** Outbox Delivery / Function Contract (Runtime Defect)
- **Severity:** `MEDIUM`
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `bot/outbox.py:210-224`; `bot/handlers.py:2366-2367`
- **Root Cause:** After verifying `get_outbox(outbox_id)` is pending, `deliver_outbox` calls `db.claim_outbox(now_iso())` with no `outbox_id` filter and no `mature_before` grouping window (unused by production `OutboxWorker`, called by tests).
- **User / System Impact:** Can claim and send a completely different pending row prematurely; bypasses `GROUP_WINDOW` (`1.5s`).
- **Dependencies:** Test suite references (`test_outbox_concurrency_28c.py`, `test_handlers.py`, etc.).
- **Proposed Remediation:** See `WP-05` (`db.claim_outbox_by_id(outbox_id, ...)` scoped CAS or explicit test-only cleanup).
- **Required Regression Tests:** Two pending rows test asserting `deliver_outbox(..., outbox_id=2)` leaves row 1 untouched.
- **Owner Approval Requirements:** `NONE`.
- **Mini App Cross-Boundary Implications:** `NONE`.

#### `DEF-009` — UI Formatters and Keyboards Pass Raw `execution_status` Instead of `get_status(conv)`
- **ID:** `DEF-009`
- **Category:** UI Consistency / Status Normalization (Runtime Defect)
- **Severity:** `MEDIUM`
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `bot/messages.py:20-61,105,138`; `bot/keyboards.py:113`; `bot/handlers.py:1377` *(plus `bot/handlers.py:1220` `watch_conversation`)*
- **Root Cause:** Four display sites pass `conv.get("execution_status")` directly to `state_label()`, bypassing `get_status(conv)`. Furthermore, `STATE_LABELS` maps `None: "غير معروف"` but omits `"unknown"`, while `get_status({})` returns `"unknown"`.
- **User / System Impact:** Uppercase statuses (`"FINISHED"`) and `sandbox_status ∈ {"ERROR", "MISSING"}` (`"sandbox_error"`) display raw/stale strings instead of normalized Arabic status matching `Watcher`/`Notifier`.
- **Dependencies:** Must fix `STATE_LABELS["unknown"]` before migrating callers (`WP-06`).
- **Proposed Remediation:** See `WP-06` (add `"unknown": "غير معروف"` to `STATE_LABELS`, switch 4 UI sites + `watch_conversation:1220` to `get_status(conv)`).
- **Required Regression Tests:** Tests for `execution_status=None`, lowercase/uppercase statuses, and `sandbox_status="ERROR"`/`"MISSING"` preserving `"غير معروف"` output.
- **Owner Approval Requirements:** `NONE`.
- **Mini App Cross-Boundary Implications:** `NONE` (read-only verify whether `bot/web/` uses `get_status`; do not touch `bot/web/*`).

#### `DEF-010` — 64-Byte `callback_data` Overflow for Valid 56–64 Char Conversation IDs
- **ID:** `DEF-010`
- **Category:** Input Bounds / Telegram API Compatibility (Runtime Defect)
- **Severity:** `MEDIUM`
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `bot/files.py:29,36` (`MAX_CONVERSATION_ID_LEN=64`); `bot/keyboards.py:9-16,94-95,114,138-215`
- **Root Cause:** Prefixes such as `deleteok:` (9 bytes), `unwatch:` (8 bytes), and `files:{cid}:{gen}:{page}` (8+ bytes) concatenate raw `conversation_id` up to 64 bytes, exceeding Telegram's 64-byte `callback_data` cap and raising `ValueError`.
- **User / System Impact:** Valid 56–64 char conversation IDs crash keyboard rendering -> `FAILED_PERMANENT` -> polling freeze (`DEF-002`).
- **Dependencies:** Interacts with `DEF-002`; requires DB/resolver design (`WP-06`).
- **Proposed Remediation:** See `WP-06` (persistent SQLite short-ref table `callback_refs` or opaque short tokens for IDs causing `>64`-byte callback payloads).
- **Required Regression Tests:** Parameterized tests with 64-char IDs across all keyboard builders and callback handlers including restart persistence.
- **Owner Approval Requirements:** `NONE` (additive SQLite table + handler resolution; verify D-35 / schema impact).
- **Mini App Cross-Boundary Implications:** `NONE` (Mini App uses REST URL paths, not Telegram `callback_data`).

#### `DEF-011` — Missing Cross-Download Reservation Lock, Sync Disk I/O, & Misleading Acceptance UX
- **ID:** `DEF-011`
- **Category:** Concurrency / Resource Quotas / UX Integrity (Runtime Defect)
- **Severity:** `MEDIUM`
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `bot/attachments.py:612-644,699-735,1062-1135`; `bot/handlers.py:1609-1611,1689,1714-1990`
- **Root Cause:** `StagingStore.store` checks quotas without reserving concurrent in-flight byte budgets across the 4 allowed download streams (`_get_download_semaphore`); `_write_to_path` (`os.fsync`) and `AttachmentReaper.sweep` run synchronous filesystem I/O inside the asyncio event loop; `ATTACHMENT_ACCEPTED_TEXT` omits that uploads are staged locally only (`Stage B` absent).
- **User / System Impact:** Dormant quota overshoot if aggregate limits are enabled; event-loop stalls during 3 MB sync writes or sweeps; users expect remote delivery to the AI agent.
- **Dependencies:** Coordinates with `WP-01` (UX copy) and `WP-07` (locks + async I/O offload).
- **Proposed Remediation:** See `WP-01` & `WP-07`.
- **Required Regression Tests:** Concurrent 4-stream quota race test + non-blocking disk offload test + UX text check.
- **Owner Approval Requirements:** `NONE` (unless altering D-12 aggregate defaults).
- **Mini App Cross-Boundary Implications:** Shared `attachment_items`/staging files; DB-first + token invariants for `MT-2` (`bot/web/download.py`) must remain preserved.

#### `DEF-012` — `CreationWorker` `wait_for_start` Branches Missing Non-`ApiError` (& Resumed `CancelledError`) Fallback
- **ID:** `DEF-012`
- **Category:** Concurrency / Worker Error Recovery (Runtime Defect)
- **Severity:** `MEDIUM`
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `bot/outbox.py:592-595,733-746,792-806`
- **Root Cause:** Resumed `if job.task_id:` branch (`L733-746`) catches only `ApiError` (omitting `CancelledError` and unexpected `Exception`), and the fresh POST `wait_for_start` branch (`L792-806`) also omits `except Exception:`. `_BaseWorker._run` swallows `Exception` at `L592` without transitioning the job out of `CREATION_CLAIMED`/`CREATION_STARTING`.
- **User / System Impact:** Non-`ApiError` crashes inside `wait_for_start` strand `creation_jobs` in `claimed`/`starting` until process restart with no user notice.
- **Dependencies:** Independent (`WP-05`).
- **Proposed Remediation:** See `WP-05` (unified `CancelledError` + `Exception` post-CAS fallback to `CREATION_UNKNOWN` + `_UNKNOWN_CREATION_NOTICE` in both `733-746` and `792-806`).
- **Required Regression Tests:** Inject `RuntimeError`, `ValueError`, and `CancelledError` in both resumed and fresh `wait_for_start` branches.
- **Owner Approval Requirements:** `NONE`.
- **Mini App Cross-Boundary Implications:** `NONE` (`creation_jobs` status in Mini App sees clean `unknown` transition).

#### `DEF-013` — Non-Atomic Expired-Awaiting Clear vs `EXPLICITLY_IGNORED` Outcome Commit
- **ID:** `DEF-013`
- **Category:** Atomicity / Crash Consistency (Runtime Defect)
- **Severity:** `LOW`
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `bot/handlers.py:2253-2261`
- **Root Cause:** `db.clear_awaiting(telegram_id)` commits separately before `reply_text` and before `mark_explicitly_ignored(update, context)` (unlike `consume_one_shot_awaiting`).
- **User / System Impact:** Mid-reply crash causes redelivery to fall into the generic `"ابعت /start..."` branch instead of the timeout notice (no duplicate prompt risk).
- **Dependencies:** Related to `NEW-DEF-03` (`WP-07`).
- **Proposed Remediation:** See `WP-07` (atomic `clear_awaiting_and_record_outcome`, acknowledging Telegram reply happens outside SQLite transaction).
- **Required Regression Tests:** Crash/exception simulation at `reply_text:2256` verifying atomic clear + outcome semantics.
- **Owner Approval Requirements:** `NONE`.
- **Mini App Cross-Boundary Implications:** `NONE`.

#### `DEF-014` — Mini App `OHB2-MT-2` Attachment Download Blocked After `intent_recorded` & Unverified WebView Gate
- **ID:** `DEF-014`
- **Category:** Cross-Boundary Feature Coupling / Excluded Mini App (`EXCLUDED_MINI_APP`)
- **Severity:** `MEDIUM`
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `bot/web/services.py:758-870` (`list_staged_attachments`, `download_attachment`); `bot/web/app.py:365-371,771-827`; `bot/db.py:1572-1663`; `docs/reviews/OHB2-MT2-COMPLETION-AND-ADVERSARIAL-VERIFICATION.md`
- **Root Cause:** `MT-2` serves attachments only while `batch.status == "pending"` inside `T0+15m`. Following Telegram instructions (`ATTACHMENT_ACCEPTED_TEXT`) moves the batch to `intent_recorded`, hiding `MT-2` downloads while bricking text prompts (`DEF-001`). Android 12 WebView native downloads remain untested.
- **User / System Impact:** Manual `MT-2` download workaround breaks immediately if the user sends accompanying text.
- **Dependencies:** Strict Mini App exclusion; directly coupled to `WP-01` flag `ATTACHMENT_DOCUMENT_INTAKE_ENABLED`.
- **Proposed Remediation:** **`BLOCKED_BY_EXCLUDED_MINI_APP`** for any change to `bot/web/*` or `bot/web/static/*`. Document `Owner Decision #3` on `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` default impact.
- **Required Regression Tests:** None scheduled on excluded Mini App files.
- **Owner Approval Requirements:** **REQUIRED** if ever expanding scope to `bot/web/*`, and `Owner Decision #3` required for backend default changes impacting `MT-2`.
- **Mini App Cross-Boundary Implications:** **DIRECT.** Any change to `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` default or `attachment_batches` lifecycle directly governs whether `MT-2` receives items.

#### `DEF-015` — Remote Attachment Delivery (`P0 Stage B1/B2`) Blocked by Missing Scoped Credential & SSRF Allowlist
- **ID:** `DEF-015`
- **Category:** Missing Core Feature / Security Gate (Deferred)
- **Severity:** `HIGH`
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `bot/openhands_client.py` (no upload method); `README.md:175-184`; `docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md`; `.agent/PROGRESS.md:20-37`
- **Root Cause:** Upstream OpenHands Cloud lacks scoped upload tokens (`session_api_key` too broad) and `conversation_url` requires static SSRF origin allowlisting (`Gate G1`).
- **User / System Impact:** Telegram attachments are never sent to the remote OpenHands agent.
- **Dependencies:** Upstream OpenHands API support + owner reopen gate (`WP-10`).
- **Proposed Remediation:** Keep `Stage B` deferred behind `.agent/PROGRESS.md:32-36` reopen criteria (`WP-10`); mitigate `DEF-001` in `WP-01`.
- **Required Regression Tests:** Ensure intake kill-switch cleanly isolates bot when `Stage B` is absent.
- **Owner Approval Requirements:** **REQUIRED** to reopen `Stage B` (`Owner` + upstream OpenHands capability).
- **Mini App Cross-Boundary Implications:** `NONE` (unless `WP-01` toggles intake flag — covered by `Owner Decision #3`).

#### `DEF-016` — Hosting Qualification (`HOST-01`/`HOST-02`/`H1`) & Live Enzonic SFTP Verification Unconfirmed
- **ID:** `DEF-016`
- **Category:** Deployment Readiness / External Infrastructure (`UNVERIFIED_EXTERNAL`)
- **Severity:** `HIGH`
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `.github/workflows/enzonic-sftp-readonly-check.yml:1-126`; `tools/katabump-sqlite-canary/canary.py:1-245`; `docs/DEPLOY_ENZONIC.md`; `docs/OHB2_ENZONIC_DEPLOYMENT_PREFLIGHT.md`; `docs/OHB2_HOSTING_DECISION.md`
- **Root Cause:** Live SFTP connectivity to `us-four.enzonic.com:2022`, out-of-band host fingerprint confirmation, `ENZONIC_SSH_PRIVATE_KEY` secret setup, SQLite persistence across restarts (`H1`), and `HOST-02` Mini App HTTPS ingress have not executed on live infrastructure.
- **User / System Impact:** Production SQLite persistence (ephemeral wipe risk) and SFTP deployment access remain unproven.
- **Dependencies:** External operator credentials & Enzonic panel access (`WP-10`).
- **Proposed Remediation:** See `WP-10` (execute strictly external operational verification after explicit authorization).
- **Required Regression Tests:** Live multi-restart `canary.py` pass + green `enzonic-sftp-readonly-check.yml` run.
- **Owner Approval Requirements:** **REQUIRED** before any live server connection, secret configuration, or deployment cutover.
- **Mini App Cross-Boundary Implications:** `HOST-02` validates external HTTPS reverse proxy only (no Mini App code changes).

#### `DEF-017` — Severe Documentation, Runbook, and Startup Contract Drift
- **ID:** `DEF-017`
- **Category:** Documentation / Operational Runbook Integrity
- **Severity:** `MEDIUM`
- **Validation Verdict:** `CONFIRMED_WITH_SCOPE_CORRECTION`
- **Exact Source Location:** `docs/ZERO_TOUCH_STARTUP.md:52-53,242`; `docs/OPERATIONS_RUNBOOK.md:46-54,73-74,135-137,362`; `README.md:70-89`; `.env.example:1-20`; `docs/API_NOTES.md:81` vs `bot/openhands_client.py:344`
- **Root Cause:** Documentation drifted behind schema/code updates: `ZERO_TOUCH_STARTUP.md:242` falsely states local deletion does not delete the remote OpenHands conversation (contradicting `bot/deletion.py`); `§1:52-53` conflicts with `/ready`/`/status`; `OPERATIONS_RUNBOOK.md` §3 omits `13` env vars (`ATTACHMENT_DOCUMENT_INTAKE_ENABLED` + `12` `MINI_APP_*`), §4 omits `13` SQLite tables (`11` omitted across entire doc), and §9 omits `notification_inbox`; `README.md` omits `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` and `MINI_APP_TRUSTED_PROXIES`; `API_NOTES.md` cites `v1.68.1` vs `v1.79.0` in client vs `v1.87.1` in ADR. **Scope Correction:** `bot/db.py:590-816` contains **`17` SQLite tables** (not `19`).
- **User / System Impact:** Operators risk accidental remote deletion or incomplete SQLite backups/restores/env configurations.
- **Dependencies:** Execute `WP-08` after `WP-01` and `WP-04` finalize defaults/commands.
- **Proposed Remediation:** See `WP-08`.
- **Required Regression Tests:** See `NEW-DEF-08` parity tests.
- **Owner Approval Requirements:** `NONE` (unless Mini App docs are touched — `docs/MINI_APP.md` remains excluded).
- **Mini App Cross-Boundary Implications:** `OPERATIONS_RUNBOOK.md` must document `MINI_APP_*` env vars from `.env.example`/`bot/config.py` without modifying `docs/MINI_APP.md` or `Config.mini_app_*`.

#### `DEF-018` — Unwired AI Studio React/Vite Scaffold & Missing Explicit `anyio` Probe in `start.sh`
- **ID:** `DEF-018`
- **Category:** Repository Hygiene / Startup Preflight
- **Severity:** `LOW`
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `package.json:1-35`, `vite.config.ts:1-22`, `tsconfig.json:1-28`, `index.html:1-19`, `metadata.json:1-7`, `src/App.tsx:1-9`, `src/main.tsx:1-6`, `src/index.css:1-2`, `bun.lock`; `start.sh:56`
- **Root Cause:** Empty AI Studio React/Vite workspace scaffold coexists unwired at root; `start.sh:56` checks `telegram`, `httpx`, `dotenv`, `starlette`, `uvicorn`, omitting `anyio`.
- **User / System Impact:** Minor repo confusion (mitigated by `OHB2-PLAN04-UI01-FRONTEND-AUTHORITY.md`); missing `anyio` not explicitly caught at shell preflight.
- **Dependencies:** Respect platform constraints (`metadata.json`/`index.html` must not be deleted unapproved).
- **Proposed Remediation:** See `WP-08` (add `"anyio"` check in `start.sh:56`; leave AI Studio root files untouched).
- **Required Regression Tests:** Update `tests/test_start_script.py` to cover `anyio`.
- **Owner Approval Requirements:** `NONE` for `start.sh:56` + test; **REQUIRED** if ever deleting root AI Studio files.
- **Mini App Cross-Boundary Implications:** `NONE`.

#### `DEF-019` — Python Test Suite, Lint, SAST, and SCA Blocked Locally in Current Container
- **ID:** `DEF-019`
- **Category:** Verification Environment / Tooling Gap
- **Severity:** `HIGH`
- **Validation Verdict:** `CONFIRMED_WITH_SCOPE_CORRECTION`
- **Exact Source Location:** Container environment; `requirements.txt:1-10`; `requirements-dev.txt:1-10`; `.github/workflows/ci.yml:1-68`; `tests/test_*.py`
- **Root Cause:** Missing `.venv` and all `10` runtime/dev Python packages (`pytest`, `pyflakes`, `bandit`, `pip_audit`, `telegram`, `httpx`, `starlette`, `uvicorn`, `dotenv`, `anyio`). **Scope Correction:** Container already runs **`Python 3.11.2`** (NOT `3.10.12`).
- **User / System Impact:** Behavioral Python tests (`pytest`), lint (`pyflakes`), SAST (`bandit`), and SCA (`pip_audit`) cannot execute in this container; AST + Node checks alone cannot certify backend behavior.
- **Dependencies:** Gates release of every WP (`WP-09`).
- **Proposed Remediation:** See `WP-09` (run full `.github/workflows/ci.yml` matrix on Python 3.11 & 3.13 + Node 22 in clean venv/CI).
- **Required Regression Tests:** Full CI matrix green.
- **Owner Approval Requirements:** `NONE` (standard CI execution).
- **Mini App Cross-Boundary Implications:** Includes `tests/test_miniapp_*.py` execution in CI read-only verification without editing them.

---

### C.2 Newly Discovered Defects (`NEW-DEF-01`..`NEW-DEF-08`, Strictly De-Duplicated)

#### Group 1 — Runtime & Code Defects (`NEW-DEF-01`..`NEW-DEF-06`)

#### `NEW-DEF-01` — Five Bare `await q.edit_message_text(...)` Calls Without `_safe_edit`
- **ID:** `NEW-DEF-01`
- **Category:** Runtime Defect (Telegram UI Error Handling / Polling Deadlock Trigger)
- **Severity:** `HIGH`
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `bot/handlers.py:787,793` (`app_open`), `805` (`show_menu`), `841` (`notifications_menu`), `869` (`notifications_toggle`)
- **Root Cause:** Five callback handlers invoke raw `await q.edit_message_text(...)` instead of `_safe_edit(...)`.
- **User / System Impact:** Double-tapping `app:open` or `notif:menu` (triggering Telegram `BadRequest: Message is not modified`), clicking deleted messages, or hitting `TimedOut` throws an uncaught `TelegramError` into `handle_processing_error` -> `FAILED_PERMANENT` -> permanent polling deadlock (`DEF-002`) for lines `787,793,805,841`, and pollutes `update_failures` post-commit at line `869` (after `toggle_notifications_once` already committed `DURABLE_COMPLETED`).
- **Dependencies:** Pairs directly with `DEF-005` in `WP-02` and reduces `DEF-002` triggers.
- **Proposed Remediation:** Replace all 5 raw `q.edit_message_text` calls with `_safe_edit` (or explicit `"Message is not modified"` no-op + benign handling preserving `DURABLE_COMPLETED` after `toggle_notifications_once`).
- **Required Regression Tests:** Parameterized tests for `BadRequest("Message is not modified")`, deleted-message `BadRequest`, and `TimedOut` on all 5 handlers including post-commit `notifications_toggle`.
- **Owner Approval Requirements:** `NONE`.
- **Mini App Cross-Boundary Implications:** `NONE`.

#### `NEW-DEF-02` — Production Conversation Creation Never Invalidates `list_cache`
- **ID:** `NEW-DEF-02`
- **Category:** Runtime Defect (Cache Coherency)
- **Severity:** `MEDIUM`
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `bot/handlers.py:2513-2541` (`_start_new_chat`) vs `2356` (`_send_prompt`), `1331` (`delete_conversation_confirm`), `2558` (test-only `_create_chat`); `bot/outbox.py:811-833` (`_finish_creation`)
- **Root Cause:** `_send_prompt:2356`, `delete_conversation_confirm:1331`, and test helper `_create_chat:2558` pop `context.bot_data["list_cache"]`, whereas production `CreationWorker` -> `_finish_creation` has no `bot_data` reference and `_start_new_chat` never invalidates `list_cache`.
- **User / System Impact:** Newly created conversations remain missing from `شاتاتي` menu for up to `LIST_TTL` (`45s`).
- **Dependencies:** `WP-05` (`CreationWorker` lifecycle).
- **Proposed Remediation:** See `WP-05` (pass an optional invalidation callback/reference or cache-version token from `app.bot_data` to `CreationWorker` / `_finish_creation` upon `complete_creation_done` success).
- **Required Regression Tests:** Test verifying `bot_data["list_cache"]` is invalidated when `CreationWorker._finish_creation` completes `done`.
- **Owner Approval Requirements:** `NONE`.
- **Mini App Cross-Boundary Implications:** `NONE` (Mini App uses `OpenHandsClient` directly; no `list_cache` coupling).

#### `NEW-DEF-03` — Non-Atomic Active `user_state`/`watched` Mutations & Premature `renew_awaiting`
- **ID:** `NEW-DEF-03`
- **Category:** Runtime Defect (Transaction Ordering & Input Validation)
- **Severity:** `LOW/MEDIUM`
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `bot/handlers.py:1216-1224` (`watch_conversation`), `1241-1260` (`unwatch_conversation`), `1592-1598` (`reply_prompt`), `2262-2263` (`handle_text` `renew_awaiting`), `2295-2297` (`cancel_route`), `2307-2309` (`cancel_route_button`), `2429-2431` (`repo_search_prompt`), `2492-2494` (`pick_repo`), `2505-2510` (`new_chat_no_repo`)
- **Root Cause:** (1) Multiple handlers commit `set_awaiting`/`clear_awaiting`/`add_watched`/`remove_watched` before sending Telegram replies and before calling `mark_durable_completed`. (2) `handle_text:2263` calls `db.renew_awaiting(telegram_id)` before `_send_prompt:2321` checks `if not text.strip()`, extending route expiry on rejected whitespace.
- **User / System Impact:** Mid-reply Telegram failures leave mutated DB state without `processed_updates` completion proof; whitespace messages extend route TTL unnecessarily.
- **Dependencies:** Consolidated with `DEF-013` in `WP-07`.
- **Proposed Remediation:** See `WP-07` (combine local state changes + `DURABLE_COMPLETED` where safe and recovery-compatible without pretending SQLite + Telegram HTTP are one atomic transaction; move `renew_awaiting` after whitespace validation or inside prompt recording).
- **Required Regression Tests:** Mid-reply failure idempotency tests for `reply_prompt`/`cancel_route`/`pick_repo`; whitespace message not renewing route TTL.
- **Owner Approval Requirements:** `NONE`.
- **Mini App Cross-Boundary Implications:** `NONE`.

#### `NEW-DEF-04` — Uncaught Raw `send_message` / `send_copyable` / `send_long` Calls in Reply & Error Branches
- **ID:** `NEW-DEF-04`
- **Category:** Runtime Defect (Telegram Error Handling)
- **Severity:** `MEDIUM`
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `bot/handlers.py:1045,1057,1062,1065` (`copy_reply`), `1084,1096,1101,1104` (`full_reply`), `1131,1137,1144,1152,1160` (`send_reply_txt`)
- **Root Cause:** Error, auth-rejection, empty-reply, and display paths in these 3 handlers call raw `context.bot.send_message(...)`, `send_copyable(...)`, and `send_long(...)` without `try/except TelegramError`, unlike `_safe_edit` / `_edit_or_send`.
- **User / System Impact:** Any transient Telegram API timeout or `BadRequest` during `copy:`/`full:`/`txt:` throws directly into `_classify_failure` -> `FAILED_PERMANENT` (`DEF-002`), overriding operational error reporting and risking polling deadlock.
- **Dependencies:** Consolidated with `DEF-004` in `WP-03` & `WP-04`.
- **Proposed Remediation:** See `WP-03` (introduce `_safe_send_html` / display-error wrapper preserving `OPERATIONAL_FAILURE` when `auth_exc`/`exc` was operational, and recording `mark_display_failed` on display `TelegramError`).
- **Required Regression Tests:** Inject `TimedOut` and `BadRequest` on `bot.send_message`, `send_copyable`, and `send_long` across `copy_reply`, `full_reply`, `send_reply_txt` under both normal and `503` auth failure cases.
- **Owner Approval Requirements:** `NONE`.
- **Mini App Cross-Boundary Implications:** `NONE`.

#### `NEW-DEF-05` — `collect_conversations` Lacks Repeated-Cursor (`seen_pages`) Guard
- **ID:** `NEW-DEF-05`
- **Category:** Runtime Defect (Pagination Loop Resilience)
- **Severity:** `LOW`
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `bot/openhands_client.py:609-615`
- **Root Cause:** `collect_conversations` iterates up to `max_pages` (`20`) following `next_page_id` without checking whether `page_id` was already seen.
- **User / System Impact:** If OpenHands returns the same `next_page_id` repeatedly, the client executes 20 redundant HTTP requests and falsely sets `truncated=True`.
- **Dependencies:** Independent (`WP-05`).
- **Proposed Remediation:** See `WP-05` (track `seen_pages: set[str]`; break deterministically and avoid false `truncated=True` or log repeated cursor safely).
- **Required Regression Tests:** Mock `search_conversations` returning repeated `next_page_id="p1"` and assert loop exits after seeing duplicate cursor.
- **Owner Approval Requirements:** `NONE`.
- **Mini App Cross-Boundary Implications:** **READ-ONLY POSITIVE SIDE EFFECT (Check):** Verify whether `bot/web/services.py` calls `collect_conversations`; fixing repeated cursor in `bot/openhands_client.py` prevents redundant upstream fetches without modifying Mini App files.

#### `NEW-DEF-06` — `UNSUPPORTED_ATTACHMENT_TEXT` Steers Users to Documents Even When Disabled
- **ID:** `NEW-DEF-06`
- **Category:** Runtime Defect (Policy-Inconsistent User Messaging)
- **Severity:** `LOW`
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `bot/handlers.py:1603-1606,1992-2013`
- **Root Cause:** Static constant `UNSUPPORTED_ATTACHMENT_TEXT` always includes *"أو إرسال ملف كمستند (Document) لو محتاج"* regardless of `config.attachment_document_intake_enabled`.
- **User / System Impact:** Once `WP-01` disables document intake by default, sending a photo/voice message actively instructs the user to send a Document that the next step immediately rejects.
- **Dependencies:** Directly tied to `WP-01` (`ATTACHMENT_DOCUMENT_INTAKE_ENABLED`).
- **Proposed Remediation:** See `WP-01` (render policy-aware message from `cfg.attachment_document_intake_enabled` in `handle_unsupported_attachment`).
- **Required Regression Tests:** Test `handle_unsupported_attachment` with intake `False` vs `True` asserting Document hint appears only when enabled.
- **Owner Approval Requirements:** Included under `WP-01` / `Owner Decision #3` if default flips.
- **Mini App Cross-Boundary Implications:** `NONE`.

#### Group 2 — Documentation & Audit Inaccuracies (`NEW-DEF-07`)

#### `NEW-DEF-07` — Factual & Classification Errors Across Prior Audit Reports
- **ID:** `NEW-DEF-07`
- **Category:** Documentation / Audit Inaccuracy (NOT a runtime defect)
- **Severity:** `HIGH` *(for planning accuracy)*
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `docs/audits/OHB2-INCOMPLETE-FEATURES.md:31`; `docs/audits/OHB2-COMPLETE-REPOSITORY-AUDIT.md:20,51,84,94,96`; `docs/audits/OHB2-AUDIT-EXECUTIVE-SUMMARY.md:18-19`; `docs/audits/OHB2-COMPLETE-DEFECT-REGISTER.md` (`DEF-003`,`DEF-004`,`DEF-005`,`DEF-017`,`DEF-019`); `docs/audits/OHB2-REMEDIATION-MASTER-PLAN.md:166,202,207`; `docs/audits/OHB2-FILE-BY-FILE-AUDIT.md:82,85,145,181`
- **Root Cause:** Six audit docs misreported: Python `3.10.12` (actual `3.11.2`), `19` SQLite tables (actual `17`), `followups`/`files`/`cost`/`export` as `Disabled` (actual `DEFERRED_FEATURES_HIDDEN = False`), `list_conversations`/`_show_repos` swallowing `5xx`, non-existent `_ACK_ELIGIBLE` constants (`AMBIGUOUS_EXTERNAL`/`DISPLAY_FAILED`), `STATE_LABELS["unknown"]`, and `notifications_toggle:857` label.
- **User / System Impact:** Would misdirect remediation patches (especially `WP-03`, `WP-06`, `WP-08`) and cause runtime regressions if followed verbatim.
- **Dependencies:** Resolved by this consolidated baseline document (`Section B`).
- **Proposed Remediation:** Superseded explicitly by `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md` (Section B & E).
- **Required Regression Tests:** N/A (documentation correction).
- **Owner Approval Requirements:** `NONE`.
- **Mini App Cross-Boundary Implications:** `NONE`.

#### Group 3 — Test & Quality Gaps (`NEW-DEF-08`)

#### `NEW-DEF-08` — Missing Documentation, Env Var & Schema Parity Tests
- **ID:** `NEW-DEF-08`
- **Category:** Test and Quality Gap (NOT a runtime defect)
- **Severity:** `MEDIUM`
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `tests/test_deploy_manifest.py`; `tests/test_zero_touch_contract.py`
- **Root Cause:** Existing contract tests check selected env vars and startup wording without programmatically comparing all `20` env vars in `.env.example` / `bot/config.py` and all `17` `CREATE TABLE IF NOT EXISTS` tables in `bot/db.py` against `README.md` and `docs/OPERATIONS_RUNBOOK.md`.
- **User / System Impact:** Allows severe documentation drift (`DEF-017`) to pass CI undetected.
- **Dependencies:** Implements after `WP-08` doc updates.
- **Proposed Remediation:** See `WP-08` (add AST/regex parity tests for env vars and all 17 SQLite table names against `README.md` & `docs/OPERATIONS_RUNBOOK.md` without modifying `docs/MINI_APP.md` or Mini App config).
- **Required Regression Tests:** The new parity assertions themselves in `tests/test_deploy_manifest.py` / `tests/test_zero_touch_contract.py`.
- **Owner Approval Requirements:** `NONE`.
- **Mini App Cross-Boundary Implications:** Read-only check on `Config.mini_app_*` names only (no Mini App modifications).

---

## D. Corrected Incomplete-Features Register

| Status Category | Feature / Capability | Verified Location | Technical Reality |
|---|---|---|---|
| **Enabled and operational** | Core Prompt Outbox (`1.5s` grouping, CAS `at-most-once`, startup crash recovery) & `completion_pending` | `bot/outbox.py`, `bot/db.py`, `bot/handlers.py` | Operational when not intercepted by `DEF-001`. |
| **Enabled and operational** | Remote + Local Conversation Deletion & Tombstones | `bot/deletion.py`, `bot/openhands_client.py:341-362`, `bot/db.py` | Active remote `DELETE /app-conversations/{id}` + local tombstone witness (`ZERO_TOUCH_STARTUP.md:242` contradicts this). |
| **Enabled and operational** | Unsupported Media Rejection (`photo`/`audio`/`video`/`voice`/`sticker`) | `bot/handlers.py:1603-1606,1992-2013` | Operational fail-closed rejection (text needs `NEW-DEF-06` awareness once `WP-01` changes flag). |
| **Enabled and operational** | Bounded Reply Preview/Split/Copy/HTML Escape & Safe Zip/File Bounds | `bot/messages.py`, `bot/sender.py`, `bot/files.py`, `bot/file_cache.py` | Operational (`DEF-009`/`DEF-010`/`NEW-DEF-04` affect specific branches noted below). |
| **Enabled and operational** | Termux Autopush Automation | `automation/autopush/main.py`, `run.sh` | Hardened standalone automation (must NOT be activated during audit/planning). |
| **Enabled but defective** | **Re-enabled Bot Features: `followups` (`/watched`), `files`, `cost`, `export`** | `bot/features.py:15` (`DEFERRED_FEATURES_HIDDEN = False`), `bot/keyboards.py:76,163-176`, `bot/handlers.py` | **RECLASSIFIED FROM `Disabled`:** All 4 are active and reachable in production keyboards today. Affected by `DEF-004` (`watch_conversation`, `export_conversation`), `DEF-005` (`list_watches`, `watch_conversation`, `unwatch_conversation`, `export_conversation`, `list_files`, `show_file`), `DEF-009` (`watch_conversation:1220`), and `DEF-010` (`files`/`export`/`unwatch` 64-byte cap). |
| **Enabled but defective** | Local Document Attachment Intake (`P0 Phase A0–A4`) | `bot/config.py:43,315-317`, `bot/handlers.py:1879-2246`, `bot/db.py:1493-1663`, `bot/attachments.py` | **Enabled by default (`True`)** without Stage B, causing `DEF-001` permanent text brick, `DEF-011` quota/sync-I/O/UX gaps, and `NEW-DEF-06`. |
| **Enabled but defective** | Telegram Callback & UI Display Layer | `bot/handlers.py`, `bot/keyboards.py`, `bot/messages.py` | Affected by `DEF-005` (`24/28` bare `q.answer`), `NEW-DEF-01` (`5` bare `q.edit_message_text`), `NEW-DEF-04` (bare `send_message`), `DEF-009` (`get_status` bypasses + missing `"unknown"` key), `DEF-010` (64-byte cap). |
| **Enabled but defective** | Proactive Watcher, Notifier & Creation Lifecycle | `bot/watcher.py`, `bot/notifier.py`, `bot/outbox.py`, `bot/openhands_client.py` | Affected by `DEF-007` (missing `continue`/`return`), `DEF-012` (both `wait_for_start` fallback gaps), `NEW-DEF-02` (`list_cache`), `NEW-DEF-05` (`seen_pages`). |
| **Partially implemented** | Custom Polling Outcome & `Stage4-F1` Failure Contracts | `bot/polling.py`, `bot/update_outcomes.py`, `bot/handlers.py` | Monotonic boundary works; missing ADR §28.4 poison skip & transient exception handling (`DEF-002`), `DEF-003` races, `6` auth-error-swallowing sites (`DEF-004`), `DEF-006` batch vs app rationale, `DEF-013`/`NEW-DEF-03` awaiting atomicity. |
| **Partially implemented** | `get_status(conv)` Unified Normalization & Aggregate Attachment Quotas | `bot/messages.py:37-48`, `bot/attachments.py:699-735` | `get_status` used by Watcher/Notifier only (`DEF-009`); aggregate caps default `None` without concurrent reservation (`DEF-011`). |
| **Deferred** | `P0` Remote Attachment Upload to OpenHands (`Stage B1/B2/C`) & `SW-02` | `docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md`, `.agent/PROGRESS.md:20-37,66` | Intentionally deferred pending external/product gates (`DEF-015`). Webhook ingress also intentionally absent per single-process polling ADR. |
| **Not integrated** | Direct `deliver_outbox(outbox_id)` Helper & Root AI Studio React+Vite Scaffold | `bot/outbox.py:210-224`; `package.json`, `src/*`, `vite.config.ts` | `deliver_outbox` unused in runtime (`DEF-008`); AI Studio scaffold `NON_RUNTIME` (`DEF-018`). |
| **Blocked by external dependencies** | Local Python Verification Suite (`pytest`/`pyflakes`/`bandit`/`pip_audit`) & Stage B Upstream API | `requirements-dev.txt`, `bot/openhands_client.py` | Missing 10 Python packages in container (`DEF-019`); upstream OpenHands scoped token + SSRF allowlist missing (`DEF-015`). |
| **Blocked by the excluded Mini App** | Mini App `OHB2-MT-2` Attachment Download Post-`intent_recorded` & Android 12 WebView Verification | `bot/web/services.py:758-870`, `bot/web/download.py`, `bot/web/static/attachments.js` | **`EXCLUDED_MINI_APP`** (`DEF-014`): `MT-2` stops serving once accompanying text sets `intent_recorded`; `bot/web/*` cannot be modified here. |
| **Not independently verified** | Live Enzonic SFTP (`enzonic-sftp-readonly-check.yml`), `H1` SQLite Restart Canary (`canary.py`), `HOST-01`/`HOST-02` | `.github/workflows/enzonic-sftp-readonly-check.yml`, `tools/katabump-sqlite-canary/canary.py`, `docs/DEPLOY_ENZONIC.md` | Live server credentials, out-of-band fingerprint, persistence across restarts, and Python CI runtime execution unverified (`DEF-016`, `DEF-019`). |

---

## E. Corrected `WP-01`..`WP-10` Specifications (With Mandatory Technical Safeguards)

### `WP-01` — Attachment Emergency Mitigation & Safe Lifecycle Escape
- **Objective:** Eliminate `DEF-001` permanent text-prompt self-DoS while respecting D-34/D-35 governance, data safety, and Mini App `MT-2` decision boundaries.
- **Included Defect IDs:** `DEF-001`, `DEF-011` (UX copy portion), `NEW-DEF-06` (policy-aware unsupported attachment text); cross-boundary dependency tracking for `DEF-014` (`BLOCKED_BY_EXCLUDED_MINI_APP` — `MT-2` governed by `OD-03`).
- **Explicit Exclusions:** Do NOT implement Stage B1/B2 remote upload (`DEF-015`); do NOT modify `bot/web/*`, `bot/web/static/*`, `tests/test_miniapp_*`, or `docs/MINI_APP.md` (`DEF-014` stays excluded); do NOT bypass terminal-state protections via undocumented shortcuts or delete unrelated user tables.
- **Exact Source Areas:** `bot/config.py:43,315-317`; `.env.example:2`; `bot/handlers.py:1603-1611,1885,2052-2204,2245,2291-2309`; `bot/db.py:1493-1663`; `bot/attachments.py:1062-1252`; `tests/test_repair_plan_02_life03_intake_kill_switch.py`, `tests/test_attachment_batch_state_routing_f1_1a.py`, `tests/test_attachment_terminal_routing_remediation.py`, `tests/test_unsupported_attachment_rejection.py`.
- **Implementation Constraints & Special Safeguards:**
  1. **Cross-Boundary Check (`ATTACHMENT_DOCUMENT_INTAKE_ENABLED`):** Disabling `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` by default (`False`) prevents Telegram `handle_attachment:1885` from staging files into `attachment_batches`, which directly starves excluded Mini App `OHB2-MT-2` (`bot/web/services.py:758-870`) unless explicitly set `1`. Default change therefore requires **`Owner Decision #3`** (`NONE` of Mini App files edited, behavioral impact explicitly approved).
  2. **Already-Affected DB States:** Changing the config flag alone does not stop `handle_text:2245`. Must cleanly reconcile pre-existing `pending`, `intent_recorded` (`UNRESOLVED`), and `expired`/`terminal` batches on upgrade/disabled state without stranding affected owners or silently deleting unrelated `outbox`/`creation_jobs`/`watched` rows.
  3. **Safe `/cancel` Batch Abandonment:** Extend `cancel_route` / `cancel_route_button` (and/or explicit owner confirmation) to support discarding `pending` and `intent_recorded` attachment batches cleanly using **DB-first, idempotent, recoverable ordering** matching `AttachmentReaper`: (a) transition batch atomically in SQLite (`BEGIN IMMEDIATE` CAS) to terminal `rejected` while keeping `attachment_message_identity` intact (`D-35`, `ON DELETE RESTRICT` honored); (b) mark items `pending`/`stored` -> `reaped` (CAS); (c) unlink staging bytes afterward (or invoke `AttachmentReaper`), so partial/interrupted unlinks self-heal idempotently on subsequent reaper ticks. Preserve valid `user_state` and unrelated batch history.
  4. **D-34 Compliance:** Do NOT change `classify_attachment_routing` `TERMINAL_UNPROVEN` (`bot/db.py:1557-1569`) blocking semantics without **`Owner Decision #1`** (`AGENTS.md` §14). Keep `TERMINAL_ASSOCIATED` (`attachment_message_identity` match) fail-closed.
  5. **Policy-Aware Copy (`NEW-DEF-06`):** `handle_unsupported_attachment` must reflect `cfg.attachment_document_intake_enabled` (omit *"أو إرسال ملف كمستند (Document)"* when disabled); `ATTACHMENT_ACCEPTED_TEXT` must honestly reflect local staging only when enabled.
- **Dependencies:** **`Owner Decision #1`** (D-34) and **`Owner Decision #3`** (`ATTACHMENT_DOCUMENT_INTAKE_ENABLED` default vs `MT-2`). Should complete before `WP-07` and `WP-08`.
- **Required Owner Approvals:** Explicit approval on D-34 semantics + `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` default impact on `MT-2`.
- **Acceptance Criteria:** Normal text prompting works across all conversations after document upload + `/cancel` (and after approved terminal/disabled recovery); partial disk-unlink crash recovers cleanly on reaper retry; `UNSUPPORTED_ATTACHMENT_TEXT` never advertises disabled intake; D-35 FK integrity holds.
- **Regression Tests:** Multi-turn E2E tests for `intent_recorded` -> `/cancel` -> prompt in Conv B; mid-cleanup crash recovery (`item=reaped` -> retry); disabled kill-switch recovery of pre-existing bricked DB; policy-aware unsupported attachment test; updated D-34 tests matching owner decision.
- **Rollback / Recovery Considerations:** Reversible via `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=1`; additive batch-abandonment statuses (`rejected`/`reaped`) preserve FK rows and never drop SQLite tables.
- **Verification Requirements:** `pytest`, `pyflakes`, `bandit` (`WP-09`) on Python 3.11 & 3.13 + manual/simulated SQLite crash-recovery test.

---

### `WP-02` — Harden All Telegram Callbacks (`q.answer()` & Bare `q.edit_message_text()`)
- **Objective:** Prevent stale inline callbacks, Telegram `"Message is not modified"` no-ops, or transient callback timeouts from crashing handlers into `FAILED_PERMANENT` and wedging polling.
- **Included Defect IDs:** `DEF-005`, `NEW-DEF-01`.
- **Explicit Exclusions:** Does not alter business-logic outcomes of downstream OpenHands API calls (`WP-03`) or `_classify_failure` (`WP-04`). Zero Mini App changes.
- **Exact Source Areas:** `bot/handlers.py` (all `28` `q.answer` call sites + all `5` bare `q.edit_message_text` call sites at `787, 793, 805, 841, 869`); `tests/test_handlers.py`.
- **Implementation Constraints & Special Safeguards:**
  1. Introduce `_safe_answer(q, text=None, *, show_alert=False)` wrapping `(TelegramError, asyncio.TimeoutError)` — **never catch `asyncio.CancelledError`** — logging `type(exc).__name__` at `WARNING`. Replace all `28` `q.answer(...)` calls.
  2. Enforce `_allowed(...)` checks before performing state edits or side effects (`_safe_answer` silent/non-blocking).
  3. Replace all `5` bare `q.edit_message_text` calls (`787, 793, 805, 841, 869`) with `_safe_edit` / benign-no-op handling: `BadRequest("Message is not modified")` must be treated as a benign no-op (never `FAILED_PERMANENT` or `FAILED_TRANSIENT`), preserving `EXPLICITLY_IGNORED` (for menus) and **`DURABLE_COMPLETED` already committed by `toggle_notifications_once` at `L855` before `L869`**.
- **Dependencies:** Coordinates sequentially/region-safely with `WP-03` & `WP-04` because all three edit `bot/handlers.py`.
- **Required Owner Approvals:** `NONE`.
- **Acceptance Criteria:** `0` bare `q.answer(` and `0` bare `q.edit_message_text(` in `bot/handlers.py`; stale queries and `"Message is not modified"` never record `FAILED_PERMANENT` or stall `acknowledgment_boundary()`.
- **Regression Tests:** Parameterized tests over all `CallbackQueryHandler` callbacks with `q.answer` raising `BadRequest("Query is too old")` / `TimedOut`, and `q.edit_message_text` raising `BadRequest("Message is not modified")` / `TimedOut` (explicitly asserting `notifications_toggle:869` keeps `DURABLE_COMPLETED` intact).
- **Rollback / Recovery Considerations:** Localized helper swap in `bot/handlers.py`; trivially reversible.
- **Verification Requirements:** `pytest`, `pyflakes`, `bandit` (`WP-09`).

---

### `WP-03` — Handler Outcomes, Operational `Stage4-F1` Propagation & Response Send Guards
- **Objective:** Close all remaining `outcome=None` return paths, migrate un-migrated auth/read handlers to `Stage4-F1` operational failure propagation, and guard raw Telegram reply/document sends.
- **Included Defect IDs:** `DEF-003`, `DEF-004`, `NEW-DEF-04`.
- **Explicit Exclusions:** **Do NOT treat `list_conversations` (`L917`) or `_show_repos` (`L2446`) as missing `5xx`/`429` propagation** — both already call `_raise_if_operational_api_failure`. Do not alter Mini App error serialization (`bot/web/*`).
- **Exact Source Areas:** `bot/handlers.py` (`1030-1163` `copy_reply`/`full_reply`/`send_reply_txt`, `1206-1224` `watch_conversation`, `1276-1282` `delete_conversation_prompt`, `1307-1318` `delete_conversation_confirm`, `1449-1472` `export_conversation`, `1567` `show_file`, `1585-1591` `reply_prompt`, `2275-2283` `reposearch`, `2351-2354` `_send_prompt`, `2534-2536` `_start_new_chat`, `2795-2798` `outbox_mark_sent`); `tests/test_stage4_f1_status_cost_operational_ack.py`, `tests/test_manual_polling_handler_outcome_coverage.py`, `tests/test_sw07_api_handler_failure_propagation.py`.
- **Implementation Constraints & Special Safeguards:**
  1. Close `outcome=None` gaps: add `mark_explicitly_ignored` in `outbox_mark_sent:2795-2798`, `consume_one_shot_awaiting == False` (`L2281`), and confirm/document explicit durable outcome invariant on `out_id == 0` (`L2351`) & `job_id == 0` (`L2534`).
  2. In `handle_text:2275-2283`, do **NOT** call `consume_one_shot_awaiting` if `_show_repos` exits due to a **4xx** `ApiError` (currently only 5xx raises out via `L2446`, while 4xx returns normally and wipes `reposearch`).
  3. Migrate the `5` `_authorized_conversation` callers (`1129, 1206, 1276, 1449, 1585`) to `_authorized_conversation_status` + `_raise_if_operational_api_failure`, AND inspect `status`/`_auth_exc` in **`delete_conversation_confirm:1307-1318`** before `mark_explicitly_ignored`.
  4. Align `send_reply_txt:1141` and `export_conversation:1465` (`_raise_if_operational_api_failure` / `mark_operational_failure` vs `mark_ambiguous_external` on genuine unknown outcomes).
  5. Guard `send_document` (`1468, 1567`) AND all raw `bot.send_message` / `send_copyable` / `send_long` calls in `copy_reply` (`1045,1057,1062,1065`), `full_reply` (`1084,1096,1101,1104`), and `send_reply_txt` (`1131,1137,1144,1152,1160`): distinguish operational upstream failure (`OPERATIONAL_FAILURE`), ambiguous external execution (`PARTIAL_OR_UNKNOWN`), and Telegram display delivery failures (`mark_display_failed` -> `FAILED_TRANSIENT`), never masking an operational API error behind a swallowed Telegram send error.
- **Dependencies:** Coordinates sequentially with `WP-02` and `WP-04` (`bot/handlers.py`).
- **Required Owner Approvals:** `NONE` (unless ADR §30 review changes operational vs menu error policy).
- **Acceptance Criteria:** Zero matched-handler paths exit with `outcome=None`; all 6 auth-failure paths preserve `5xx`/`429` fail-closed semantics; raw `send_message`/`send_document` errors map to `mark_display_failed` without losing upstream `OperationalApiFailure` telemetry.
- **Regression Tests:** Expanded `503` vs `404` matrix across all 6 auth sites + `reposearch` 4xx/expiry-`False` + `outbox_mark_sent` CAS race + `TelegramError` injection in `copy_reply`/`full_reply`/`send_reply_txt`/`export_conversation`/`show_file`.
- **Rollback / Recovery Considerations:** Localized handler edits; preserve existing fail-closed DB invariants.
- **Verification Requirements:** `pytest`, `pyflakes`, `bandit` (`WP-09`).

---

### `WP-04` — Fix `_classify_failure` & Design/Implement ADR §28.4 Poison Quarantine
- **Objective:** Stop misclassifying transient network/Telegram errors as `FAILED_PERMANENT`, and provide a safe, explicit manual recovery path for genuine permanent poison updates (`DEF-002`).
- **Included Defect IDs:** `DEF-002`.
- **Explicit Exclusions:** **NEVER implement automatic skipping** of `FAILED_PERMANENT`, `FAILED_TRANSIENT`, or `PARTIAL_OR_UNKNOWN` updates. Do not weaken fail-closed ACK checks. Zero Mini App changes.
- **Exact Source Areas:** `bot/handlers.py:477-495` (`_classify_failure`), `1150-1154` (`send_reply_txt`); `bot/update_outcomes.py`; `bot/db.py`; `bot/polling.py`; `bot/app.py`; `tests/test_stage2_custom_polling.py`, `tests/test_stage2_high_ack_blocking_fix.py`, new `tests/test_poison_update_quarantine.py`.
- **Implementation Constraints & Special Safeguards:**
  1. Classify known transient exceptions as `FAILED_TRANSIENT`: `telegram.error.RetryAfter`, `telegram.error.TimedOut`, `telegram.error.NetworkError`, `asyncio.TimeoutError`, and `httpx.TransportError`.
  2. **Scoped `OSError` Rule:** Do **NOT** blindly classify every `OSError` as transient. Inspect origin/context (e.g., transient socket/network errors `ConnectionError`, `TimeoutError`, or `errno` `EAGAIN`/`ECONNRESET`/`ETIMEDOUT` -> `FAILED_TRANSIENT`; local disk/permission/structural `PermissionError`/`FileNotFoundError`/`IsADirectoryError`/`ENOSPC` -> remain `FAILED_PERMANENT` or non-silently surfaced for operator triage).
  3. Preserve fail-closed boundary blocking for all `FAILED_TRANSIENT`, `PARTIAL_OR_UNKNOWN`, and unacknowledged `FAILED_PERMANENT` updates.
  4. **ADR §28.4 Manual Poison Policy (`Owner Decision #2`):** `/updates_status` and `/updates_skip <update_id> confirm` require explicit owner approval before implementation, and MUST enforce: owner-only `_guard` authorization, explicit `<update_id> confirm` double-confirmation matching an existing `update_failures` head-of-line entry, durable audit recording (`POISON_SKIPPED` / `EXPLICITLY_IGNORED` with `reason` + timestamp in SQLite), clear recovery feedback, and zero auto-skip behavior.
- **Dependencies:** Benefits from `WP-02` and `WP-03` stopping false `FAILED_PERMANENT` triggers; gated on **`Owner Decision #2`**.
- **Required Owner Approvals:** **REQUIRED (`Decision #2`: ADR §28.4 poison-skip contract per `AGENTS.md` §14).**
- **Acceptance Criteria:** Known transient Telegram/network errors classify as `FAILED_TRANSIENT`; local non-transient `OSError` sub-types are not silently treated as transient retries; operators can safely inspect and manually skip confirmed permanent poison updates without SQLite CLI edits (only if Decision #2 approved).
- **Regression Tests:** Classifier unit tests covering `RetryAfter`, `TimedOut`, `NetworkError`, `BadRequest`, `httpx.TransportError`, socket `OSError` vs `PermissionError`; `/updates_status` authz + `/updates_skip` confirmation & boundary-advance tests.
- **Rollback / Recovery Considerations:** Keep `update_failures` audit row even when poison-skipped so forensic trace survives restarts.
- **Verification Requirements:** `pytest`, `pyflakes`, `bandit` (`WP-09`).

---

### `WP-05` — Worker Correctness, Cache Invalidation, & Cursor-Loop Protection
- **Objective:** Fix control-flow skip bugs, creation-polling exception leaks, target-ID claiming in `deliver_outbox`, post-creation `list_cache` invalidation, and OpenHands cursor-loop protection.
- **Included Defect IDs:** `DEF-007`, `DEF-008`, `DEF-012`, `NEW-DEF-02`, `NEW-DEF-05`.
- **Explicit Exclusions:** Do not alter `OutboxWorker` `at-most-once` CAS/tombstone invariants or Mini App routes (`bot/web/*`).
- **Exact Source Areas:** `bot/watcher.py:215-221`; `bot/notifier.py:522-528`; `bot/outbox.py:210-224,733-746,792-806,811-833`; `bot/app.py` (worker wiring if cache invalidator callback passed); `bot/openhands_client.py:609-615`; `tests/test_watcher.py`, `tests/test_notifier.py`, `tests/test_creation.py`, `tests/test_outbox_concurrency_28c.py`, `tests/test_openhands_client.py`.
- **Implementation Constraints & Special Safeguards:**
  1. Add `continue` at `bot/watcher.py:221` and `return` at `bot/notifier.py:528` inside `clear_retry_not_before` `except Exception:` blocks.
  2. Add identical `except asyncio.CancelledError:` (mark `{CREATION_CLAIMED, CREATION_STARTING}` -> `CREATION_UNKNOWN`, re-raise) AND `except Exception:` (mark `CREATION_UNKNOWN` + `safe_send` `_UNKNOWN_CREATION_NOTICE`) fallback blocks around **both** `wait_for_start` calls in `bot/outbox.py:733-746` and `792-806`.
  3. Fix `deliver_outbox(outbox_id)` (`bot/outbox.py:210-224`) via atomic `db.claim_outbox_by_id(outbox_id, now_iso())` (respecting `outbox_id` + optional `mature_before`), or confirm test migration if removed cleanly.
  4. Invalidate `list_cache` when production `CreationWorker` -> `_finish_creation` (`bot/outbox.py:824-832`) transitions `job_id` to `done` (e.g., via an optional `on_created` callback injected by `bot/app.py` popping `app.bot_data["list_cache"]`).
  5. Track `seen_pages: set[str]` in `collect_conversations` (`bot/openhands_client.py:609-615`) to halt repeated-cursor loops immediately.
- **Dependencies:** Independent of `WP-01`..`WP-04` (can run cleanly after Phase 1 or in parallel with `WP-06` since files barely overlap — check `bot/app.py` & test files only).
- **Required Owner Approvals:** `NONE`.
- **Acceptance Criteria:** Failed `clear_retry_not_before` genuinely skips cycle; neither `wait_for_start` branch leaves jobs stranded in `claimed`/`starting`; `deliver_outbox(id)` claims only `id`; `list_cache` clears after creation completion; repeated `next_page_id` halts in 1 duplicate step.
- **Regression Tests:** Fault-injection tests for `clear_retry_not_before`, both `wait_for_start` branches (`RuntimeError` + `CancelledError`), multi-row `deliver_outbox`, creation `list_cache` invalidation, and repeated `next_page_id`.
- **Rollback / Recovery Considerations:** Surgical single-method fixes preserving CAS transitions.
- **Verification Requirements:** `pytest`, `pyflakes`, `bandit` (`WP-09`).

---

### `WP-06` — Status Normalization (`STATE_LABELS` + `get_status`) & 64-Byte Callback Refs
- **Objective:** Unify Telegram UI status rendering via `get_status(conv)` while preserving Arabic `"غير معروف"` fallback, and support valid `56..64`-char `conversation_id`s under Telegram's 64-byte `callback_data` cap.
- **Included Defect IDs:** `DEF-009`, `DEF-010`.
- **Explicit Exclusions:** Zero changes to Mini App routing, static JS, or Mini App tests (`bot/web/*`, `bot/web/static/*`).
- **Exact Source Areas:** `bot/messages.py:20-30,105,138`; `bot/keyboards.py:9-16,94-95,113-114,138-215`; `bot/handlers.py:1220` (`watch_conversation`), `1377` (`show_status`), plus callback ID resolution helpers; `bot/db.py` (additive `callback_refs` table if persistent short tokens used); `tests/test_messages.py`, `tests/test_keyboards.py`, `tests/test_handlers.py`.
- **Implementation Constraints & Special Safeguards:**
  1. **`STATE_LABELS["unknown"]` Pre-Fix:** Add `"unknown": "غير معروف"` to `STATE_LABELS` (`bot/messages.py:20-30`) **before** changing `format_conversation:105`, `format_conversation_view:138`, `conversations_menu:113`, and `show_status:1377` from `conv.get("execution_status")` to `get_status(conv)`. Also review `watch_conversation:1220` (`db.set_last_state(conversation_id, get_status(conv))` vs `execution_status` contract — ensure `watches_menu` `state_label(w.last_state)` matches `Watcher`).
  2. **64-Byte Callback Solution:** Implement a persistent short-token resolver in `bot/db.py` + `bot/keyboards.py` + `bot/handlers.py` (e.g., opaque short handle mapped to `conversation_id` in SQLite `callback_refs` when `conversation_id` exceeds safe inline budget, or consistently resolved transparently) so `deleteok:`, `unwatch:`, `files:{ref}:{gen}:{page}`, and `file:{ref}:{gen}:{idx}` stay `<= 64` bytes for any valid `MAX_CONVERSATION_ID_LEN = 64` ID across bot restarts.
- **Dependencies:** Independent of `WP-01`..`WP-05` (`bot/handlers.py` edits focus on `show_status`, `watch_conversation`, and callback prefix decoding — sequence cleanly with `WP-02`/`WP-03` to avoid merge conflicts; `bot/db.py` schema count must feed into `WP-08` if `callback_refs` table is added!).
- **Required Owner Approvals:** `NONE` (unless `callback_refs` table impacts schema retention rules — verify with `WP-08` table inventory -> `18` tables if added!).
- **Acceptance Criteria:** `state_label(get_status({})) == "غير معروف"`; `sandbox_status="ERROR"`/`"MISSING"` renders `"خطأ بيئة"` across all menus/views; all `64`-char conversation IDs render and dispatch cleanly across restarts without `ValueError`.
- **Regression Tests:** Boundary tests for `execution_status=None`, uppercase statuses, `sandbox_status="ERROR"`, and `64`-char IDs across all keyboard builders + callback handlers + simulated DB restart.
- **Rollback / Recovery Considerations:** Additive `callback_refs` table (`IF NOT EXISTS`) is non-destructive; `STATE_LABELS["unknown"]` backward-compatible.
- **Verification Requirements:** `pytest`, `pyflakes`, `bandit` (`WP-09`).

---

### `WP-07` — State Consistency, Attachment I/O & Quotas, and Poller Concurrency Governance
- **Objective:** Improve atomicity of `user_state`/outcome writes, eliminate event-loop blocking during staging/reaping and concurrent quota races, and reconcile polling concurrency policy safely.
- **Included Defect IDs:** `DEF-006`, `DEF-011` (quota lock + async disk I/O), `DEF-013`, `NEW-DEF-03`.
- **Explicit Exclusions:** **Do NOT enable concurrent update execution inside `TelegramPoller.process_updates`** unless `Database._conn` thread/async safety, `BEGIN IMMEDIATE` write contention, and per-user ordering invariants are rigorously proven and approved (`Owner Decision #4`). Zero Mini App changes.
- **Exact Source Areas:** `bot/polling.py:155-178`; `bot/app.py:75-87`; `bot/attachments.py:612-760,1062-1252`; `bot/handlers.py:1216-1260,1592-1598,1714,2253-2263,2295-2309,2429-2431,2492-2510`; `bot/db.py` (atomic `clear_awaiting_and_outcome` / `set_awaiting_and_outcome` / `add_watched_and_outcome` helpers); `tests/test_one_shot_awaiting_atomicity.py`, `tests/test_repair_plan_01_resource_staging.py`, `tests/test_stage2_custom_polling.py`.
- **Implementation Constraints & Special Safeguards:**
  1. **No False SQLite+Telegram Atomicity (`DEF-013`, `NEW-DEF-03`):** SQLite transactions and Telegram HTTP requests (`reply_text`/`_safe_edit`) **cannot** form one atomic distributed transaction. Combine local DB state mutations (`clear_awaiting`, `set_awaiting`, `add_watched`, `remove_watched`) with durable outcome recording (`EXPLICITLY_IGNORED`/`DURABLE_COMPLETED`) atomically inside SQLite where safe, ensure idempotent re-execution if Telegram delivery throws afterward, and move `db.renew_awaiting(telegram_id)` (`bot/handlers.py:2263`) to execute **only after** whitespace validation (`_send_prompt:2321` or inside `_send_prompt` after `not text.strip()` check).
  2. **Attachment Filesystem Offload & Quota Reservation (`DEF-011`):** Offload **both** `StagingStore._write_to_path` (`bot/attachments.py:612-644`, `os.fsync`) **and** `AttachmentReaper.sweep` (`bot/attachments.py:1062-1135`) blocking disk I/O off the event loop via `asyncio.to_thread` (separating SQLite queries on the owner connection from thread-offloaded file I/O so `sqlite3.Connection` is never shared unsafely across worker threads without explicit synchronization!), and add an in-process async reservation ledger for `max_batch_items` / `max_batch_bytes` / `max_staging_total_bytes` when enabled.
  3. **Concurrency Proof Gate (`DEF-006`, `Owner Decision #4`):** By default, **preserve sequential batch processing** in `TelegramPoller.process_updates` and align comments in `bot/app.py:75-87` with `docs/OPERATIONS_RUNBOOK.md:123-127`. Concurrent intra-batch dispatch is strictly blocked unless proven safe across `Database._conn`, per-user `user_state`/`attachment_batches` serialization locks, and `list_cache` / `repo_nav` state, and approved by the owner.
- **Dependencies:** Depends on `WP-01` (attachment policy & cleanup) and `Owner Decision #4` (if proposing concurrency).
- **Required Owner Approvals:** **REQUIRED if enabling concurrent update dispatch (`Decision #4`).** None if preserving sequential batching and aligning comments.
- **Acceptance Criteria:** Expired/active `user_state` updates commit atomically with outcomes and handle mid-reply errors idempotently; whitespace input never renews `route` TTL; staging & reaper disk I/O never block the asyncio loop or access `sqlite3.Connection` unsafely from worker threads; concurrent quota streams cannot exceed caps; polling policy and docs match code 100%.
- **Regression Tests:** Crash-mid-reply idempotency tests; whitespace non-renewal test; 4-way async quota race test; reaper + staging async offload test; poller ordering & doc/comment parity test.
- **Rollback / Recovery Considerations:** Keep sequential `process_updates` fallback; maintain existing row-first staging invariants.
- **Verification Requirements:** `pytest` concurrency tests, `pyflakes`, `bandit` (`WP-09`).

---

### `WP-08` — Operational Documentation Sync, `start.sh` Probe & Parity Tests
- **Objective:** Eliminate factual contradictions across operational documentation and enforce automated doc/env/schema parity in CI.
- **Included Defect IDs:** `DEF-017`, `DEF-018`, `NEW-DEF-08` (ensures live runbooks align with Section B / `NEW-DEF-07` factual corrections rather than repeating superseded counts).
- **Explicit Exclusions:** **Do NOT modify `docs/MINI_APP.md`, `bot/web/*`, or `Config.mini_app_*` fields**, and do NOT change Mini App configuration defaults or behavior. Do not delete root AI Studio scaffold files (`package.json`, `index.html`, `metadata.json`, `src/*`) without explicit approval. Also leave historical `docs/audits/OHB2-*` reports intact (superseded by this baseline per `NEW-DEF-07`).
- **Exact Source Areas:** `docs/OPERATIONS_RUNBOOK.md`; `docs/ZERO_TOUCH_STARTUP.md`; `README.md`; `docs/API_NOTES.md`; `start.sh:56`; `tests/test_deploy_manifest.py`, `tests/test_zero_touch_contract.py`, `tests/test_start_script.py`.
- **Implementation Constraints & Special Safeguards:**
  1. Document the exact **`17` SQLite tables** (or `18` if `WP-06` adds `callback_refs` — derive count dynamically from `bot/db.py::_init_schema`) in `docs/OPERATIONS_RUNBOOK.md` §4 (`completion_pending`, `settings`, `notification_state`, `notifier_pending`, `notifier_retry_not_before`, `notification_inbox`, `deleted_conversations`, `web_sessions`, `processed_updates`, `update_failures`, `attachment_batches`, `attachment_items`, `attachment_message_identity` + the 4 existing tables).
  2. Document all `20` env vars from `.env.example` / `bot/config.py` in `docs/OPERATIONS_RUNBOOK.md` §3 and `README.md` (adding `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` and `MINI_APP_TRUSTED_PROXIES` accurately without changing `Config.mini_app_*` code/behavior).
  3. Add `notification_inbox` persistence/recovery guidance to `docs/OPERATIONS_RUNBOOK.md` §9.
  4. Fix `docs/ZERO_TOUCH_STARTUP.md:242` (accurately document remote `DELETE` + local tombstone per `bot/deletion.py`) and `L52-53` (align `/health`, `/ready`, `/status` with `OPERATIONS_RUNBOOK.md:135-137`).
  5. Reconcile OpenAPI spec versions in `docs/API_NOTES.md:81` (`v1.68.1` historical capture vs `v1.79.0` client / `v1.87.1` ADR).
  6. Add `"anyio"` to `start.sh:56` and implement `NEW-DEF-08` parity tests comparing `.env.example`/`bot/config.py` env vars and `bot/db.py` table names against `README.md` and `docs/OPERATIONS_RUNBOOK.md`.
- **Dependencies:** Must execute **after** `WP-01`, `WP-04`, and `WP-06`/`WP-07` so docs match final defaults, `/updates_*` commands (if approved), and final SQLite table set.
- **Required Owner Approvals:** `NONE` (unless modifying `docs/MINI_APP.md` or removing AI Studio scaffold — both excluded).
- **Acceptance Criteria:** Zero contradictions across `ZERO_TOUCH_STARTUP.md`, `OPERATIONS_RUNBOOK.md`, `README.md`, `API_NOTES.md`, `.env.example`, and source code; `NEW-DEF-08` parity tests pass automatically.
- **Regression Tests:** Automated env-var & schema-table parity checks in `tests/test_deploy_manifest.py` / `tests/test_zero_touch_contract.py` + `tests/test_start_script.py`.
- **Rollback / Recovery Considerations:** Documentation/test-only updates.
- **Verification Requirements:** `pytest`, `pyflakes`, `bandit` (`WP-09`).

---

### `WP-09` — Full CI Verification Matrix Execution
- **Objective:** Execute and pass the complete supported verification matrix outside this dependency-stripped container before releasing any remediation package.
- **Included Defect IDs:** `DEF-019` (gates closure of `DEF-001`..`DEF-018` and `NEW-DEF-01`..`NEW-DEF-08`).
- **Explicit Exclusions:** Do NOT treat `ast.parse` syntax checks or `node --test tests/frontend/*.test.js` (`280/280`) as substitutes for Python runtime behavioral tests, lint, SAST, or SCA. Do NOT inspect/run against live production servers.
- **Exact Source Areas:** `.github/workflows/ci.yml:1-68`, `requirements.txt`, `requirements-dev.txt`, full test suites (`tests/*.py` + `tests/frontend/*.test.js`).
- **Implementation Constraints & Special Safeguards:** Separate and report results distinctly across all 7 verification classes on both **Python `3.11` & `3.13`** and **Node `22`**:
  1. **Syntax checks:** `ast.parse` across all `.py` files.
  2. **Unit tests (Backend & Frontend):** isolated `pytest` unit modules + `node --test tests/frontend/*.test.js`.
  3. **Integration tests:** full `python -m pytest -q` (including Mini App tests executed read-only, SQLite concurrency/crash recovery, and E2E handler/poller suites).
  4. **Static analysis:** `python -m pyflakes bot/ automation/ tools/ main.py tests/` (`0` warnings/errors).
  5. **SAST:** `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` (`0` high-severity findings).
  6. **Dependency vulnerability scanning (SCA):** `python -m pip_audit -r requirements-dev.txt` (`No known vulnerabilities found`; any CVE remediation requires explicit pin review per `AGENTS.md` §4).
  7. **External infrastructure checks:** Explicitly separated into `WP-10` (never claimed green from local/mocked CI).
- **Dependencies:** Gates completion of `WP-01`..`WP-08`.
- **Required Owner Approvals:** `NONE` for CI execution; **REQUIRED** if `pip_audit` forces dependency pin changes outside original scope (`AGENTS.md` §4).
- **Acceptance Criteria:** Exit code `0` across all CI commands on Python 3.11 & 3.13 and Node 22 with `0` skipped failures masking defects.
- **Regression Tests:** Entire repository test suite (`131` Python test modules + `24` JS test modules + new WP tests).
- **Rollback / Recovery Considerations:** CI gate only; any failing check blocks gate transition.
- **Verification Requirements:** Actual command logs from Python 3.11, Python 3.13, and Node 22 runs (never historical review docs).

---

### `WP-10` — External Infrastructure Qualification & P0 Stage B Reopen Gate
- **Objective:** Keep all live hosting, SFTP, SQLite durability, and upstream OpenHands API qualification strictly separate from local code fixes, governed by explicit authorization.
- **Included Defect IDs:** `DEF-015`, `DEF-016`.
- **Explicit Exclusions:** Zero code edits to Mini App files (`HOST-02` validates TLS/reverse-proxy ingress externally only). No unauthorized live Enzonic/Telegram/OpenHands access during planning.
- **Exact Source Areas:** `.github/workflows/enzonic-sftp-readonly-check.yml`, `tools/katabump-sqlite-canary/canary.py`, `docs/DEPLOY_ENZONIC.md`, `docs/OHB2_ENZONIC_DEPLOYMENT_PREFLIGHT.md`, `docs/OHB2_HOSTING_DECISION.md`, `.agent/PROGRESS.md:20-37`.
- **Implementation Constraints & Special Safeguards:**
  1. Independently verify Enzonic `us-four.enzonic.com:2022` SSH host key fingerprint from the provider panel before configuring `ENZONIC_SSH_PRIVATE_KEY` in GitHub Secrets and triggering `enzonic-sftp-readonly-check.yml` (`workflow_dispatch`, read-only `pwd`/`ls`).
  2. Execute `tools/katabump-sqlite-canary/canary.py` across actual container restarts/redeploys on target hosting (`H1`) — fail qualification immediately if WAL state disappears.
  3. Qualify `HOST-02` public HTTPS ingress externally without modifying Mini App implementation.
  4. Keep `Stage B1/B2` remote attachment delivery closed until upstream OpenHands supports scoped upload credentials and static SSRF origin allowlisting (`Gate G1`) is approved.
- **Dependencies:** External operator credentials, live hosting access, and upstream OpenHands Cloud features.
- **Required Owner Approvals:** **REQUIRED** for every live host operation, secret addition, workflow dispatch, hosting selection, or P0 Stage B reopen.
- **Acceptance Criteria:** Verified out-of-band host fingerprint + green read-only SFTP workflow; proven multi-restart `H1` SQLite durability; `HOST-02` HTTPS verified; documented `Stage B` gate status.
- **Regression Tests:** Multi-restart `canary.py` output + GitHub Actions workflow artifact/run verification.
- **Rollback / Recovery Considerations:** Live deployment must NOT proceed until `H1` canary proves durable storage.
- **Verification Requirements:** Real external run logs (never assumed).

---

## F. Special Technical Safeguards Checklist (Verification Summary)

- **`WP-01`:** `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` traced to Mini App `MT-2` (`bot/web/services.py:758-870`); requires `Owner Decision #3`; safe DB-first idempotent `/cancel` (`rejected` -> `reaped` -> unlink, keeping `attachment_message_identity`); handles pre-existing affected DB rows; preserves valid user data; D-34 gated on `Owner Decision #1`; includes `NEW-DEF-06`.
- **`WP-02`:** All `28` `q.answer()` + all `5` bare `q.edit_message_text()` (`787,793,805,841,869`); post-commit safety (`notifications_toggle:855->869`); `"Message is not modified"` handled as benign no-op.
- **`WP-03`:** False `list_conversations`/`_show_repos` 5xx claims removed; `5` `_authorized_conversation` callers + `delete_conversation_confirm:1307-1318`; `reposearch` 4xx & `False` race; `outcome=None` fixes; `send_document` + raw `send_message`/`send_copyable`/`send_long` (`NEW-DEF-04`); preserves `FAILED_TRANSIENT` operational vs `PARTIAL_OR_UNKNOWN` vs `FAILED_TRANSIENT` display distinctions.
- **`WP-04`:** Known transient exceptions (`RetryAfter`, `TimedOut`, `NetworkError`, `asyncio.TimeoutError`, `httpx.TransportError`); context-inspected `OSError` (never blanket all `OSError`); fail-closed preserved; no auto-skip; ADR §28.4 manual `/updates_status` + `/updates_skip` gated on `Owner Decision #2` with authz, confirmation, auditability, and recovery.
- **`WP-05`:** Watcher/Notifier `continue`/`return`; both `wait_for_start` fallback blocks (`733-746`, `792-806`); `deliver_outbox(outbox_id)` contract; creation `list_cache` invalidation (`NEW-DEF-02`); `collect_conversations` `seen_pages` guard (`NEW-DEF-05`).
- **`WP-06`:** `"unknown": "غير معروف"` added to `STATE_LABELS` before switching UI + `watch_conversation:1220` to `get_status(conv)`; persistent short callback refs for 56–64 char IDs; zero Mini App edits.
- **`WP-07`:** `NEW-DEF-03` included; explicit separation between SQLite atomic commit and best-effort Telegram HTTP reply; `renew_awaiting` moved after whitespace check; both `StagingStore` and `AttachmentReaper.sweep` disk I/O handled safely; quota reservation lock; concurrent polling blocked unless connection safety + per-user serialization are proven (`Owner Decision #4`); comments/runbook aligned.
- **`WP-08`:** `17` SQLite tables; all `20` env vars; `notification_inbox` recovery; `ZERO_TOUCH_STARTUP.md` deletion & readiness fixes; `NEW-DEF-08` parity tests; `docs/MINI_APP.md` and `Config.mini_app_*` untouched.
- **`WP-09`:** Python `3.11`/`3.13` + Node `22` matrix with 7 separated verification tiers; AST/Node never substitute for `pytest`.
- **`WP-10`:** External live qualification completely decoupled and owner-authorized.

---

## G. Corrected Dependency Graph & Execution Sequence

Because `WP-02`, `WP-03`, and `WP-04` all modify overlapping functions, error handlers, and outcome tests inside `bot/handlers.py`, **they are sequenced rather than parallelized** to prevent merge conflicts and masked outcome regressions. `WP-07` does **not** enable polling concurrency without explicit proof and `Owner Decision #4`.

```
[Owner Decisions #1 (D-34) & #3 (Intake Default vs MT-2)]
   │
   ▼
Phase 0 — Emergency Attachment Mitigation
   └─► WP-01 [DEF-001, DEF-011 UX, NEW-DEF-06]
          │
          ▼
Phase 1 — Sequential Handler & Polling Reliability (Shared file: bot/handlers.py)
   WP-02 [DEF-005, NEW-DEF-01] (Callbacks: 28 q.answer + 5 bare edits)
      │
      ▼
   WP-03 [DEF-003, DEF-004, NEW-DEF-04] (Outcomes, Stage4-F1, send_message/send_document)
      │
      ├───────────────────────◄ [Owner Decision #2 (ADR §28.4 Poison Policy)]
      ▼
   WP-04 [DEF-002] (_classify_failure + Manual Quarantine)
      │
      ├─────────────────────────────────────────┐
      ▼                                         ▼
Phase 2 — Functional & Worker Correctness   Phase 2 (UI / Long IDs)
   WP-05 [DEF-007, DEF-008, DEF-012,           WP-06 [DEF-009, DEF-010]
          NEW-DEF-02, NEW-DEF-05]               (STATE_LABELS["unknown"] + get_status
   (watcher/notifier/outbox/client)              + callback_refs)
      │                                         │
      └───────────────────┬─────────────────────┘
                          │
                          ├──────◄ [Owner Decision #4 (Only if proposing concurrency)]
                          ▼
Phase 2b — State Consistency, Attachment I/O & Polling Policy
   WP-07 [DEF-006, DEF-011, DEF-013, NEW-DEF-03]
   (Requires WP-01; preserves sequential polling unless concurrency proven)
      │
      ▼
Phase 3 — Documentation & Verification Gate
   WP-08 [DEF-017, DEF-018, NEW-DEF-08] (Must follow WP-01, WP-04, WP-06, WP-07)
      │
      ▼
   WP-09 [DEF-019] (Full Python 3.11 & 3.13 CI + Node 22 Gate for WP-01..WP-08)
      │
      ▼
Phase 4 — External Infrastructure Qualification (Strictly Separate & Owner-Gated)
   WP-10 [DEF-015, DEF-016] (Live Enzonic SFTP, H1 Canary, HOST-02, P0 Reopen Gate)
```

*Cycle Check:* Strictly acyclic (every edge flows strictly forward from Phase 0 -> Phase 1 -> Phase 2 -> Phase 2b -> Phase 3 -> Phase 4).

---

## H. Owner Decisions Register

Per `AGENTS.md` §14 and strict Mini App boundaries, **silence is NEVER treated as approval**.

| Decision ID | Exact Question for Owner | Existing Behavior | Proposed Alternatives | Consequences | Can Work Proceed Without Decision? |
|---|---|---|---|---|---|
| **`OD-01`** *(D-34 `TERMINAL_UNPROVEN`)* | Should `classify_attachment_routing` (`bot/db.py:1557-1569`) stop blocking all future unrelated text prompts across conversations after an attachment batch enters `expired`/`rejected`/`delivered`/`failed` (`TERMINAL_UNPROVEN`), while preserving `TERMINAL_ASSOCIATED` blocking for messages recorded in `attachment_message_identity`? | `has_terminal_attachment_batch(telegram_id)` returns `True` forever once any terminal batch exists, causing `_handle_accompanying_text` to reject every unmapped text message permanently (`DEF-001`). | **Alt A (Recommended):** Scope terminal blocking to `attachment_message_identity` (`TERMINAL_ASSOCIATED`) + same-route active/unproven window, or allow non-attachment prompts once batch is `rejected`/`expired` and explicitly acknowledged.<br>**Alt B:** Keep D-34 strict global block, and require owner to confirm an explicit reset command (`/attachments_reset`) to archive/clear terminal lock state.<br>**Alt C:** Bypass `_handle_accompanying_text` completely when `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=0` AND active unresolved/pending batches are `0`. | **Alt A** eliminates permanent brick cleanly, requires updating `test_attachment_terminal_routing_remediation.py` under owner approval.<br>**Alt B** preserves legacy D-34 tests untouched, worse UX on 15m expiration.<br>**Alt C** leaves brick active if flag is ever turned back `On`. | **PARTIAL NO:** `NEW-DEF-06` and `/cancel` `pending` draft design are clear, but `WP-01` cannot finalize terminal-state routing or modify D-34 tests without `OD-01`. |
| **`OD-02`** *(ADR §28.4 Poison Quarantine)* | What manual recovery policy should unblock head-of-line polling deadlocks (`DEF-002`) caused by genuine `FAILED_PERMANENT` updates (e.g., `TextDocumentTooLargeError`)? | `FAILED_PERMANENT` stays in `_INELIGIBLE` permanently; polling halts until manual SQLite DB intervention or Telegram 24h expiry. | **Alt A (Recommended per ADR §28.4):** Add owner-only `/updates_status` and `/updates_skip <update_id> confirm` persisting a durable audit record and advancing offset only after explicit confirmation.<br>**Alt B:** Classify strictly deterministic user-limit rejections (like `TextDocumentTooLargeError` *after* user notification succeeded) as `REJECTED_INELIGIBLE` / `EXPLICITLY_IGNORED` while keeping unexpected exceptions fail-closed + `/updates_skip`. | **Alt A** keeps all unhandled errors fail-closed until manual inspection.<br>**Alt B** reduces operator intervention for known >50MB file notices, while still requiring `/updates_skip` for unforeseen permanent crashes. Both preserve `FAILED_TRANSIENT` fail-closed retries. | **WP-04 part 1 YES / part 2 NO:** Transient classifier fixes (`RetryAfter`/`TimedOut`/`NetworkError`) can be implemented independently, but ADR §28.4 skip commands/outcomes MUST NOT be implemented without `OD-02`. |
| **`OD-03`** *(Backend Flag Default vs Excluded Mini App `MT-2`)* | Do you authorize changing the default of `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` (`bot/config.py:315-317`, `.env.example`) from `True` to `False`, knowing that this disables Telegram document staging unless explicitly opted into (`=1`), which in turn leaves the excluded Mini App `OHB2-MT-2` staged-attachments view empty by default? | `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` defaults to `True`: Telegram stages documents (`pending`) so `MT-2` can download them, **but** any follow-up text bricks the bot (`DEF-001` & `DEF-014`). | **Alt A (Recommended):** Set default to `False` until `OD-01` + safe lifecycle are shipped (operators wanting `MT-2` local transfer set `=1` explicitly after `WP-01` `/cancel` & `OD-01` land).<br>**Alt B:** Keep default `True` and ship `OD-01` + `/cancel` + honest local-only `ATTACHMENT_ACCEPTED_TEXT` (`"ملف محفوظ محليًا فقط — افتح التطبيق للتنزيل أو /cancel للإلغاء"`) in `WP-01`. | **Alt A** eliminates out-of-the-box brick immediately, disables zero-config `MT-2` usage.<br>**Alt B** keeps `MT-2` working out of the box, relies on `OD-01` being completely solved first. | **NO for changing default in `WP-01`:** Changing the default silently alters excluded Mini App behavior and is blocked without explicit `OD-03`. |
| **`OD-04`** *(Polling Concurrency vs Sequential Architecture in `WP-07`)* | Should `TelegramPoller.process_updates` (`bot/polling.py:161-162`) remain strictly sequential (`OPERATIONS_RUNBOOK.md:123-127` behavior), or be refactored to allow concurrent intra-batch dispatch (`bot/app.py:75-87`)? | `TelegramPoller.process_updates` runs one update at a time (`dispatch_and_wait`), while `Application.builder()` configures `.concurrent_updates(True)` over a single shared `sqlite3.Connection` (`check_same_thread=False`). | **Alt A (Recommended, Conservative):** Preserve sequential per-batch dispatch and update `bot/app.py:75-87` comments to match `OPERATIONS_RUNBOOK.md:123-127`.<br>**Alt B:** Implement per-user async/DB locks, prove single-connection SQLite write safety, enqueue batch updates concurrently, and join once per batch. | **Alt A** has zero concurrency/SQLite-lock risk.<br>**Alt B** reduces batch head-of-line latency behind slow API reads, but risks SQLite transaction interleaving and same-user `user_state`/`attachment_batches` races unless proven. | **Alt A can proceed if comments-only fix is approved; Alt B BLOCKED** until technical proof and `OD-04` sign-off. |
| **`OD-05`** *(External Live Infra & Stage B Reopen — `WP-10`)* | Authorization & credentials to execute live Enzonic SFTP fingerprint check, `H1` persistence canary, and future `Stage B` reopen. | All live infra unverified; Stage B deferred. | Execute `WP-10` externally only upon owner instruction. | Required before production launch. | `WP-01`..`WP-09` code/CI work can proceed locally/CI without `OD-05`; production cutover cannot. |

---

## I. Objective Release Gates

No gate may be declared passed using historical test records in `docs/reviews/*`, `ast.parse` syntax checks, or Node frontend tests alone.

| Gate | Prerequisite WPs & Decisions | Objective, Measurable Pass Criteria |
|---|---|---|
| **Gate 0 — Governance & Decision Gate** | `OD-01`, `OD-02`, `OD-03`, `OD-04` | Written owner decisions recorded in `.agent/PROGRESS.md` / decision log before editing gated components (`D-34`, `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` default, ADR §28.4 poison skip, `WP-07` concurrency). |
| **Gate A — Emergency Attachment Safety** | `WP-01` + `WP-09` (CI partial/full) | `0` permanent cross-conversation text bricks across `/cancel`, disabled mode, and `OD-01`-approved terminal paths; idempotent reaper recovery verified; `UNSUPPORTED_ATTACHMENT_TEXT` accurate; `bot/web/*` & `bot/web/static/*` byte-for-byte unchanged (`0` diff). |
| **Gate B — Callback, Outcome & Polling Resilience** | `WP-02` + `WP-03` + `WP-04` + `WP-09` | `0` bare `q.answer(` and `0` bare `q.edit_message_text(` in `bot/handlers.py`; `0` matched handler exits with `outcome=None`; all `6` auth-failure paths preserve `5xx`/`429`; `send_document` and raw `send_message` errors handled safely; transient network/Telegram errors classify `FAILED_TRANSIENT`; ADR §28.4 skip tested; full `WP-09` CI green on Python `3.11` & `3.13`. |
| **Gate C — Worker, UI Normalization, State & Docs Parity** | `WP-05` + `WP-06` + `WP-07` + `WP-08` + `WP-09` | `clear_retry_not_before` failure skips cycle; both `wait_for_start` fallback paths tested; `deliver_outbox` target-isolated; `list_cache` cleared on creation; `seen_pages` halts loops; `STATE_LABELS["unknown"] == "غير معروف"` & `get_status()` unified; 64-char IDs pass all keyboards/callbacks; `StagingStore` & `AttachmentReaper.sweep` I/O non-blocking; `NEW-DEF-03` resolved; `17` (or schema-verified) SQLite tables & `20` env vars pass `NEW-DEF-08` parity tests; full `WP-09` CI matrix (`pytest`, `pyflakes`, `bandit -lll -s B613`, `pip_audit`, `node --test`) exits `0` on Python `3.11`, Python `3.13`, and Node `22`. |
| **Gate D — External Production Cutover Readiness** | `WP-10` + Gates A–C + `OD-05` | Live Enzonic SFTP fingerprint independently verified + green `enzonic-sftp-readonly-check.yml` run; `tools/katabump-sqlite-canary/canary.py` survives actual container restarts (`H1`); `HOST-02` HTTPS ingress verified externally with zero Mini App edits. |

---

## J. Remaining Unknowns & Unverified Items

1. **Backend Runtime Tests (`pytest`), Lint (`pyflakes`), SAST (`bandit`), and SCA (`pip_audit`):** Blocked in this container (`10` Python packages absent). Historical `docs/reviews/*` reports are treated strictly as unverified archival claims until live Python 3.11/3.13 execution completes.
2. **Git History & Working-Tree Cleanliness:** `.git` is absent (`git_exists: False`); actual branch name, commit history, upstream remote sync, and prior GitHub Actions run logs cannot be inspected locally.
3. **Live Hosting & Persistence (`DEF-016`):** Enzonic `us-four.enzonic.com:2022` SFTP host fingerprint validity, `ENZONIC_SSH_PRIVATE_KEY` functionality, SQLite durability across container restarts (`H1`), and `HOST-01`/`HOST-02` hosting capability remain unverified.
4. **Upstream OpenHands Cloud API Spec:** `docs/API_NOTES.md:81` cites OpenAPI `v1.68.1`, `bot/openhands_client.py:344` cites `v1.79.0`, and proposals cite `v1.87.1` — live upstream schemas and scoped upload support (`DEF-015`) remain unverified externally.
5. **Excluded Mini App Runtime & WebView UX (`DEF-014`):** Physical Android 12 Telegram WebView download verification for `MT-2` and live Mini App ASGI behavior under `HOST-02` remain unverified and outside modification scope.
6. **Potential Schema Update in `WP-06`:** If persistent `callback_refs` table is added in `bot/db.py`, total SQLite table count will increase from `17` to `18`, which `WP-08` parity tests must track against `bot/db.py` directly.
