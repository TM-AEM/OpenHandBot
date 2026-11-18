# OHB2 Authoritative Corrected Remediation Baseline

**Task ID:** `OHB2-REMEDIATION-BASELINE-CONSOLIDATION` *(Updated by Final Errata: `OHB2-REMEDIATION-BASELINE-FINAL-ERRATA`)*  
**Baseline Date:** 2026-11-17  
**Re-verified Environment (this session):** Project root `/workspace/project/OpenHandBot`; `Python 3.13.15`; `Node v24.22.2`; `.git` **present** (branch `main`, `HEAD` `33530ca`, clean working tree at session start).  
**Historical Observation (prior session, retained for provenance only):** Project root `/app/applet`; `Python 3.11.2`; `Node v22.23.2`; `.git` absent. The environment has since changed; the re-verified facts above supersede it.  
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
3. The corrected owner-decision briefing and its independent review (used for the owner-decision register, `OD-01`..`OD-05`, and the provisional priority sequence):
   - `docs/audits/OHB2-OWNER-DECISIONS-BRIEFING.md`
   - `docs/reviews/OHB2-OWNER-DECISIONS-BRIEFING-INDEPENDENT-REVIEW.md`
   - `docs/reviews/OHB2-OWNER-DECISIONS-BRIEFING-REVIEW-FIXES-REPORT.md`

**Consolidation scope (this session):** Re-verified the corrected factual baseline against live source, added the three-category defect classification (`A` Runtime / `B` AUDIT ERRATA / `C` QUALITY GAP), the owner-approved provisional priority sequence, and re-checked the environment. No implementation work is authorized.

### A.2 Authority, Supersession, and Non-Modification Policy
- **Supersession:** Where any specification, count, line scope, feature classification, dependency ordering, or technical assumption in the six original audit reports conflicts with `OHB2-INDEPENDENT-AUDIT-REPORT-VALIDATION.md` or with this document, **this document supersedes the conflicting implementation guidance**.
- **Preservation of Historical Records:** None of the seven pre-existing audit reports have been rewritten or altered; their historical audit findings remain intact as archival inputs.
- **Authorization Boundary:** This document is a **planning and engineering specification baseline only**. It does **NOT** authorize code modification, dependency installation, configuration changes, Git operations, deployments, or execution of any work package (`WP-01`..`WP-10`). Explicit owner approval is required before implementation begins (and specifically for the owner decisions cataloged in Section H).
- **Strict Mini App Exclusion:** The Telegram Mini App subsystem (`bot/web/*`, `bot/web/static/*`, `tests/frontend/*`, `tests/test_miniapp_*.py`, `tests/test_real_http_miniapp_download.py`, `tests/_miniapp_helpers.py`, `docs/MINI_APP.md`, and `Config.mini_app_*` fields) is **`EXCLUDED_MINI_APP`** and must not be modified. Cross-boundary dependencies discovered via read-only inspection are documented explicitly and gated on owner decisions.

### A.3 Observable Workspace & Git Limitations
- **Actual Project Root (re-verified this session):** `/workspace/project/OpenHandBot`.
- **Git Metadata (re-verified this session):** `.git` **is present**. `git rev-parse --abbrev-ref HEAD` -> `main`; `HEAD` = `33530cad02f37755da47e7eedac57764a354a75b`; `git status --porcelain` was **clean** at session start. Remote `origin` = `https://github.com/TM-AEM/OpenHandBot.git`. Working-tree cleanliness is therefore verifiable locally now (it was not in the prior session). Remote GitHub Actions run logs remain outside local verification scope.
- **Audit Package Inventory:** All `9` audit/baseline files under `docs/audits/` (`6` original audit/plan docs + `OHB2-INDEPENDENT-AUDIT-REPORT-VALIDATION.md` + `OHB2-OWNER-DECISIONS-BRIEFING.md` + this baseline) were verified present and tracked; the original audit and validation reports remain unmodified.
- **Runtime / Package State (re-verified this session):** `Python 3.13.15` and `Node v24.22.2` are present. Runtime/dev Python packages (`pytest`, `pyflakes`, `bandit`, `pip_audit`, `telegram`, `httpx`, `starlette`, `uvicorn`, `dotenv`, `anyio`) are **absent** (`BLOCKED` for Python behavioral/lint/SAST/SCA checks). `ast.parse` over `165/165` `.py` files passed (`0` syntax errors). `node --test tests/frontend/*.test.js` -> `280` tests, `280` pass, `0` fail (read-only).

---

## B. Corrected Factual Baseline

Every remediation work package (`WP-01`..`WP-10`) and parity check must use these source-verified facts instead of the superseded claims from the original audit package. Each item below records the **re-verified** value from this session (2026-11-17) with its evidence; where the environment changed since the prior baseline, the change is stated explicitly.

1. **Container Python Version:** The active container executes **`Python 3.13.15`** (re-verified this session via `python3 --version`). The **prior baseline's claim of `Python 3.11.2` is now superseded** — the environment changed. The original audit's claim of `3.10.12` was also wrong. Python `>= 3.11` (`bot/bootstrap.py::MIN_PYTHON`) is satisfied; local Python CI/runtime gates are blocked solely because the virtual environment and the `10` third-party packages from `requirements.txt` / `requirements-dev.txt` are not installed. The project's CI matrix (`.github/workflows/ci.yml:23`) targets `Python 3.11` & `3.13`, so `3.13.15` is a supported target version.
2. **SQLite Schema Table Count:** `Database._init_schema()` (`bot/db.py:587+`) defines **`17` tables** (not `19`) — re-verified this session by counting `CREATE TABLE IF NOT EXISTS` names: `watched`, `user_state`, `outbox`, `creation_jobs`, `completion_pending`, `settings`, `notification_state`, `notifier_pending`, `notifier_retry_not_before`, `notification_inbox`, `deleted_conversations`, `web_sessions`, `processed_updates`, `update_failures`, `attachment_batches`, `attachment_items`, `attachment_message_identity`. `docs/OPERATIONS_RUNBOOK.md` §4 (`lines 73-74`) lists only `4` tables (`watched`, `user_state`, `outbox`, `creation_jobs`) and omits `13` (`4 + 13 = 17`).
3. **Feature Visibility State:** `bot/features.py:15` sets **`DEFERRED_FEATURES_HIDDEN = False`**. Therefore `is_hidden(feature)` (`bot/features.py:20-22`) returns `False` for `"files"`, `"export"`, `"cost"`, and `"followups"`, making all four active, rendered, and live-reachable in Telegram keyboards and handlers (`README.md` / `bot/app.py`).
4. **Already-Migrated Operational Failure Propagation:** In `bot/handlers.py`, both **`list_conversations` (`L917`)** and **`_show_repos` (`L2446`)** already call `await _raise_if_operational_api_failure(exc)` inside their `except ApiError:` handlers, so `5xx`/`429`/network failures in those two functions already propagate rather than being swallowed into `EXPLICITLY_IGNORED`.
5. **Exact `_ACK_ELIGIBLE` Outcome Set:** `bot/update_outcomes.py:40-48` defines `_ACK_ELIGIBLE` strictly as `{DURABLE_COMPLETED, DURABLE_INTENT_RECORDED, EXPLICITLY_IGNORED, DUPLICATE_COMPLETED, REJECTED_INELIGIBLE}`. Constants named `AMBIGUOUS_EXTERNAL` and `DISPLAY_FAILED` do **not** exist; `handlers.mark_ambiguous_external` records `PARTIAL_OR_UNKNOWN` (`bot/handlers.py:604`) and `handlers.mark_display_failed` records `FAILED_TRANSIENT` (`bot/handlers.py:626`), both of which belong to fail-closed `_INELIGIBLE` (`bot/update_outcomes.py:51-53`).
6. **`STATE_LABELS` Missing `"unknown"` Key:** `bot/messages.py:20-30` maps **`None: "غير معروف"`** and does **not** define an `"unknown"` key. Meanwhile `get_status(conv)` (`bot/messages.py:37-48`) converts missing `execution_status` (`None`) into lowercase string `"unknown"` (`L44`). Calling `state_label(get_status({}))` currently renders literal `"unknown"` instead of `"غير معروف"` until `"unknown": "غير معروف"` is added to `STATE_LABELS`.
7. **`notifications_toggle:857` Semantics:** In `bot/handlers.py:855-858`, `new_state is None` is the **duplicate `update_id` short-circuit** (`bot/db.py:4268-4270`), not a database-failure branch.

---

## C. Unified Defect Register (`DEF-001`..`DEF-019` + `NEW-DEF-01`..`NEW-DEF-08`)

Confidence legend: `CONFIRMED` (directly verified in source), `CONFIRMED_WITH_SCOPE_CORRECTION` (verified with narrowed/corrected scope), `UNVERIFIED_EXTERNAL` (code path verified, live runtime/external behavior unverified locally).

**Defect-classification legend (mandatory three categories).** Every finding in this register carries exactly one category label:

- **`A. RUNTIME DEFECT`** — an actual or independently validated defect affecting runtime behavior, data integrity, reliability, security, or user-visible functionality.
- **`B. AUDIT ERRATA`** — an incorrect statement, unsupported claim, inaccurate source reference, or classification mistake in previous audit documentation. This is **not** an OpenHandBot runtime defect.
- **`C. QUALITY GAP`** — a missing test, incomplete verification, documentation/configuration parity gap, or other quality-assurance deficiency that is **not** an independently established runtime defect.

**Register integrity:** Each `DEF-ID` appears exactly once in `§C.1`; each `NEW-DEF-ID` appears exactly once in `§C.2`. Other sections reference IDs without duplicating register entries.

**Classification summary (per-finding labels appear as `- **Classification:**` in each entry):**
- **`A. RUNTIME DEFECT`:** `DEF-001`..`DEF-015` and `NEW-DEF-01`..`NEW-DEF-06` (defects affecting runtime behavior, data integrity, reliability, security, or user-visible functionality).
- **`B. AUDIT ERRATA`:** `NEW-DEF-07` (mandatory — incorrect statements/classifications in prior audit documentation; **not** a runtime defect).
- **`C. QUALITY GAP`:** `DEF-016` (external infrastructure qualification unverified), `DEF-017` (operational documentation/runbook parity drift), `DEF-018` (repository hygiene / startup-preflight gap), `DEF-019` (verification-environment/tooling gap), and `NEW-DEF-08` (mandatory — missing parity tests). These are verification, documentation-parity, or tooling gaps, **not** independently established runtime defects.

*Rationale for `C` on `DEF-016`..`DEF-019`:* none of these four is a confirmed defect in executing code — they are respectively an unexecuted external qualification, a documentation-parity gap, a repository-hygiene/preflight omission, and a blocked test environment. They are retained in the register (not removed) but separated from the runtime defects as required.

### C.1 Original Audit Defects (`DEF-001`..`DEF-019`)

#### `DEF-001` — Permanent Normal Text-Prompt Self-DoS ("Owner Brick") After Any Document Attachment
- **ID:** `DEF-001`
- **Category:** State Machine / Feature Integration / Operational Availability (Runtime Defect)
- **Classification:** `A. RUNTIME DEFECT`
- **Severity:** `CRITICAL`
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `bot/config.py:43,315-317`; `bot/handlers.py:1885,2052-2204,2245,2291-2309`; `bot/db.py:812-814,1364-1395,1493-1663`; `bot/attachments.py:1095-1115`
- **Root Cause:** `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` defaults to `True` even though Stage B remote upload (`DEF-015`) is unimplemented. Any uploaded document enters `attachment_batches`; sending text within 15m triggers `record_attachment_intent` -> `intent_recorded` (`UNRESOLVED`, skipped by `AttachmentReaper` forever), while letting it expire -> `expired` triggers D-34 `TERMINAL_UNPROVEN` (`bot/db.py:1557-1569`), both scoped globally by `telegram_id` across all conversations. `handle_text:2245` invokes `_handle_accompanying_text` unconditionally without checking `attachment_document_intake_enabled`, and `/cancel` only clears `user_state`.
- **User / System Impact:** After one document upload, all subsequent normal text prompts across every conversation (and `/newchat`/`reposearch`) are permanently rejected. Setting `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=0` later still does not unbrick an already-affected owner.
- **Dependencies:** Interacts with `DEF-015` (Stage B blocked), `DEF-014` (`MT-2`), `NEW-DEF-06` (`UNSUPPORTED_ATTACHMENT_TEXT`), and `WP-07` concurrency safety.
- **Proposed Remediation:** See `WP-01` (change flag default only under `OD-03` owner sign-off; reconcile pre-existing batches via conservative state-by-state policy with pre-change inventory and manual reconciliation for ambiguous batches — never blanket deletion/rejection; add DB-first idempotent `/cancel` batch abandonment; resolve D-34 `TERMINAL_UNPROVEN` only under explicit `OD-01` decision).
- **Required Regression Tests:** Multi-turn E2E tests covering `intent_recorded` -> `/cancel` -> prompt in Conv B; state-by-state pre-existing DB recovery tests matching owner decisions; mid-cleanup crash-retry tests; preserving valid `TERMINAL_ASSOCIATED` dedupe and unrelated records.
- **Owner Approval Requirements:** **REQUIRED** (`OD-01`: D-34 `TERMINAL_UNPROVEN` policy per `AGENTS.md` §14; `OD-03`: changing `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` default because it alters excluded Mini App `MT-2` availability; explicit authorized recovery decision before any irreversible cleanup).
- **Mini App Cross-Boundary Implications:** **HIGH (`MT-2` Coupling).** `bot/web/services.py:758-870` (`list_staged_attachments`, `download_attachment`) reads `attachment_batches` created solely by Telegram `handle_attachment`. Disabling `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` by default silences `MT-2` staged attachment intake unless explicitly enabled by config (`OD-03`).

#### `DEF-002` — Head-of-Line Polling Offset Deadlock on `FAILED_PERMANENT` & Transient Exception Misclassification
- **ID:** `DEF-002`
- **Category:** Polling / Telegram ACK Reliability / Error Classification (Runtime Defect)
- **Classification:** `A. RUNTIME DEFECT`
- **Severity:** `HIGH`
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `bot/update_outcomes.py:40-53,93-110`; `bot/polling.py:155-173,202-208`; `bot/handlers.py:477-495,1150-1154,1468,1567`
- **Root Cause:** `_ACK_ELIGIBLE` excludes `FAILED_PERMANENT`, `acknowledgment_boundary` stalls at the first ineligible update, and ADR §28.4 manual poison quarantine/skip was never implemented. Simultaneously, `_classify_failure` (`bot/handlers.py:488-495`) classifies all exceptions other than `CancelledError`, transient `sqlite3.Error`, and non-permanent `ApiError` as `FAILED_PERMANENT` — including transient `telegram.error.*`, `asyncio.TimeoutError`, and `httpx.TransportError`.
- **User / System Impact:** Any transient Telegram network timeout or deterministic permanent error (`TextDocumentTooLargeError`) locks `TelegramPoller._next_offset` indefinitely across restarts until Telegram 24h update expiry or manual SQLite edits.
- **Dependencies:** Triggered/amplified by `DEF-005`, `DEF-010`, `NEW-DEF-01`, and `NEW-DEF-04`.
- **Proposed Remediation:** See `WP-04` (context-aware transient classification; ADR §28.4 manual `/updates_status` + `/updates_skip` with explicit owner confirmation and auditability).
- **Required Regression Tests:** `_classify_failure` tests for `RetryAfter`/`TimedOut`/`NetworkError`/`BadRequest`/`asyncio.TimeoutError`/`httpx.TransportError`/scoped `OSError`; polling quarantine & boundary-advance tests.
- **Owner Approval Requirements:** **REQUIRED** (`OD-02`: ADR §28.4 poison-update manual skip policy per `AGENTS.md` §14).
- **Mini App Cross-Boundary Implications:** `NONE` (polling layer only; Mini App uses ASGI HTTP).

#### `DEF-003` — Missing Outcome (`outcome=None` -> Ack Block) & `reposearch` Error/Expiry Handling
- **ID:** `DEF-003`
- **Category:** Handler Outcome Contract / Control Flow (Runtime Defect)
- **Classification:** `A. RUNTIME DEFECT`
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
- **Classification:** `A. RUNTIME DEFECT`
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
- **Classification:** `A. RUNTIME DEFECT`
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
- **Classification:** `A. RUNTIME DEFECT`
- **Severity:** `MEDIUM`
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `bot/polling.py:161-162,175-178` vs `bot/app.py:75-87`; `docs/OPERATIONS_RUNBOOK.md:123-127`
- **Root Cause:** `TelegramPoller.process_updates` loops `await self.dispatch_and_wait(update)` sequentially, neutralizing `concurrent_updates(True)` within multi-update batches, while `bot/app.py:75-87` still claims intra-batch non-blocking concurrency (`OPERATIONS_RUNBOOK.md:123-127` already documents sequential dispatch).
- **User / System Impact:** A slow command/callback delays `"وصل ✅"` prompt receipt for later updates in the same `getUpdates` batch. Conversely, enabling raw concurrency without per-user locks risks SQLite `Database` (`self._conn`) contention and `user_state`/`attachment_batches` races.
- **Dependencies:** Blocked by `WP-01` and requires SQLite single-connection + per-user serialization proof (`WP-07`).
- **Proposed Remediation:** See `WP-07` (preserve sequential dispatch and align `bot/app.py:75-87` comments unless concurrency + SQLite connection safety + per-user ordering are rigorously proven).
- **Required Regression Tests:** Ordering/serialization tests (or timing + race tests if concurrency is approved).
- **Owner Approval Requirements:** **REQUIRED if changing architecture (`OD-04`: enabling concurrent update dispatch per `AGENTS.md` §14).** `NONE` if keeping sequential polling and aligning `bot/app.py` documentation.
- **Mini App Cross-Boundary Implications:** Low/indirect (`bot/web/runner.py` shares the same event loop and `Database` connection when Mini App is enabled; shared-connection safety checks apply if concurrent DB writes increase).

#### `DEF-007` — `Watcher.tick` and `Notifier._process` Missing `continue`/`return` After `clear_retry_not_before` Failure
- **ID:** `DEF-007`
- **Category:** Notification Reliability / Control Flow (Runtime Defect)
- **Classification:** `A. RUNTIME DEFECT`
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
- **Classification:** `A. RUNTIME DEFECT`
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
- **Classification:** `A. RUNTIME DEFECT`
- **Severity:** `MEDIUM`
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `bot/messages.py:20-61,105,138`; `bot/keyboards.py:113`; `bot/handlers.py:1377` *(plus `bot/handlers.py:1220` `watch_conversation`)*
- **Root Cause:** Four display sites pass `conv.get("execution_status")` directly to `state_label()`, bypassing `get_status(conv)`. Furthermore, `STATE_LABELS` maps `None: "غير معروف"` but omits `"unknown"`, while `get_status({})` returns `"unknown"`.
- **User / System Impact:** Uppercase statuses (`"FINISHED"`) and `sandbox_status ∈ {"ERROR", "MISSING"}` (`"sandbox_error"`) display raw/stale strings instead of normalized Arabic status matching `Watcher`/`Notifier`.
- **Dependencies:** Must fix `STATE_LABELS["unknown"]` before migrating callers (`WP-06`).
- **Proposed Remediation:** See `WP-06` (add `"unknown": "غير معروف"` to `STATE_LABELS`, switch 4 UI sites + `watch_conversation:1220` to `get_status(conv)`).
- **Required Regression Tests:** Tests for `execution_status=None`, lowercase/uppercase statuses, and `sandbox_status="ERROR"`/`"MISSING"` preserving `"غير معروف"` output.
- **Owner Approval Requirements:** `NONE`.
- **Mini App Cross-Boundary Implications:** `NONE` (read-only inspection confirms `bot/web/services.py:266,661` already calls `get_status(conv)`; do not touch `bot/web/*`).

#### `DEF-010` — 64-Byte `callback_data` Overflow for Valid 56–64 Char Conversation IDs
- **ID:** `DEF-010`
- **Category:** Input Bounds / Telegram API Compatibility (Runtime Defect)
- **Classification:** `A. RUNTIME DEFECT`
- **Severity:** `MEDIUM`
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `bot/files.py:29,36` (`MAX_CONVERSATION_ID_LEN=64`); `bot/keyboards.py:9-16,94-95,114,138-215`
- **Root Cause:** Prefixes such as `deleteok:` (9 bytes), `unwatch:` (8 bytes), and `files:{cid}:{gen}:{page}` (8+ bytes) concatenate raw `conversation_id` up to 64 bytes, exceeding Telegram's 64-byte `callback_data` cap and raising `ValueError`.
- **User / System Impact:** Valid 56–64 char conversation IDs crash keyboard rendering -> `FAILED_PERMANENT` -> polling freeze (`DEF-002`).
- **Dependencies:** Interacts with `DEF-002`; requires DB/resolver design (`WP-06`).
- **Proposed Remediation:** See `WP-06` (design and implement an additive persistent short-token resolver `callback_refs` — **`NOT_YET_IMPLEMENTED — DESIGN PREREQUISITE`** — with TTL/expiration, bounded cleanup, ownership/conversation binding, cross-user reuse rejection, and fail-closed stale handling while preserving the 64-byte `CALLBACK_DATA_LIMIT`).
- **Required Regression Tests:** Parameterized tests with 64-char IDs across all keyboard builders and callback handlers including restart persistence, TTL expiry, bounded pruning, malformed/missing ref handling, and cross-user authorization rejection.
- **Owner Approval Requirements:** `NONE` for planning; design prerequisite completion required prior to `WP-06` schema change (`17 -> 18` SQLite tables if `callback_refs` is added).
- **Mini App Cross-Boundary Implications:** `NONE` (Mini App uses REST URL paths, not Telegram `callback_data`).

#### `DEF-011` — Missing Cross-Download Reservation Lock, Sync Disk I/O, & Misleading Acceptance UX
- **ID:** `DEF-011`
- **Category:** Concurrency / Resource Quotas / UX Integrity (Runtime Defect)
- **Classification:** `A. RUNTIME DEFECT`
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
- **Classification:** `A. RUNTIME DEFECT`
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
- **Classification:** `A. RUNTIME DEFECT`
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
- **Classification:** `A. RUNTIME DEFECT`
- **Severity:** `MEDIUM`
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `bot/web/services.py:758-870` (`list_staged_attachments`, `download_attachment`); `bot/web/app.py:365-371,771-827`; `bot/db.py:1572-1663`; `docs/reviews/OHB2-MT2-COMPLETION-AND-ADVERSARIAL-VERIFICATION.md`
- **Root Cause:** `MT-2` serves attachments only while `batch.status == "pending"` inside `T0+15m`. Following Telegram instructions (`ATTACHMENT_ACCEPTED_TEXT`) moves the batch to `intent_recorded`, hiding `MT-2` downloads while bricking text prompts (`DEF-001`). Android 12 WebView native downloads remain untested.
- **User / System Impact:** Manual `MT-2` download workaround breaks immediately if the user sends accompanying text.
- **Dependencies:** Strict Mini App exclusion; directly coupled to `WP-01` flag `ATTACHMENT_DOCUMENT_INTAKE_ENABLED`.
- **Proposed Remediation:** **`BLOCKED_BY_EXCLUDED_MINI_APP`** for any change to `bot/web/*` or `bot/web/static/*`. Document `OD-03` on `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` default impact.
- **Required Regression Tests:** None scheduled on excluded Mini App files.
- **Owner Approval Requirements:** **REQUIRED** if ever expanding scope to `bot/web/*`, and `OD-03` required for backend default changes impacting `MT-2`.
- **Mini App Cross-Boundary Implications:** **DIRECT.** Any change to `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` default or `attachment_batches` lifecycle directly governs whether `MT-2` receives items.

#### `DEF-015` — Remote Attachment Delivery (`P0 Stage B1/B2`) Blocked by Missing Scoped Credential & SSRF Allowlist
- **ID:** `DEF-015`
- **Category:** Missing Core Feature / Security Gate (Deferred)
- **Classification:** `A. RUNTIME DEFECT`
- **Severity:** `HIGH`
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `bot/openhands_client.py` (no upload method); `README.md:175-184`; `docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md`; `.agent/PROGRESS.md:20-37`
- **Root Cause:** Upstream OpenHands Cloud lacks scoped upload tokens (`session_api_key` too broad) and `conversation_url` requires static SSRF origin allowlisting (`Gate G1`).
- **User / System Impact:** Telegram attachments are never sent to the remote OpenHands agent.
- **Dependencies:** Upstream OpenHands API support + owner reopen gate (`WP-10`).
- **Proposed Remediation:** Keep `Stage B` deferred behind `.agent/PROGRESS.md:32-36` reopen criteria (`WP-10`); mitigate `DEF-001` in `WP-01`.
- **Required Regression Tests:** Ensure intake kill-switch cleanly isolates bot when `Stage B` is absent.
- **Owner Approval Requirements:** **REQUIRED** to reopen `Stage B` (`Owner` + upstream OpenHands capability).
- **Mini App Cross-Boundary Implications:** `NONE` (unless `WP-01` toggles intake flag — covered by `OD-03`).

#### `DEF-016` — Hosting Qualification (`HOST-01`/`HOST-02`/`H1`) & Live Enzonic SFTP Verification Unconfirmed
- **ID:** `DEF-016`
- **Category:** Deployment Readiness / External Infrastructure (`UNVERIFIED_EXTERNAL`)
- **Classification:** `C. QUALITY GAP`
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
- **Classification:** `C. QUALITY GAP`
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
- **Classification:** `C. QUALITY GAP`
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
- **Classification:** `C. QUALITY GAP`
- **Severity:** `HIGH`
- **Validation Verdict:** `CONFIRMED_WITH_SCOPE_CORRECTION`
- **Exact Source Location:** Container environment; `requirements.txt:1-10`; `requirements-dev.txt:1-10`; `.github/workflows/ci.yml:1-68`; `tests/test_*.py`
- **Root Cause:** Missing `.venv` and all `10` runtime/dev Python packages (`pytest`, `pyflakes`, `bandit`, `pip_audit`, `telegram`, `httpx`, `starlette`, `uvicorn`, `dotenv`, `anyio`). **Scope Correction:** At the time of the original audit the container ran **`Python 3.11.2`** (NOT `3.10.12`); the current container runs **`Python 3.13.15`** (re-verified this session).
- **User / System Impact:** Behavioral Python tests (`pytest`), lint (`pyflakes`), SAST (`bandit`), and SCA (`pip_audit`) cannot execute in this container; AST + Node checks alone cannot certify backend behavior.
- **Dependencies:** Gates release of every WP (`WP-09`).
- **Proposed Remediation:** See `WP-09` (run full `.github/workflows/ci.yml` matrix on Python 3.11 & 3.13 + Node 24 in clean venv/CI).
- **Required Regression Tests:** Full CI matrix green.
- **Owner Approval Requirements:** `NONE` (standard CI execution).
- **Mini App Cross-Boundary Implications:** Includes `tests/test_miniapp_*.py` execution in CI read-only verification without editing them.

---

### C.2 Newly Discovered Defects (`NEW-DEF-01`..`NEW-DEF-08`, Strictly De-Duplicated)

#### Group 1 — Runtime & Code Defects (`NEW-DEF-01`..`NEW-DEF-06`)

#### `NEW-DEF-01` — Five Bare `await q.edit_message_text(...)` Calls Without `_safe_edit`
- **ID:** `NEW-DEF-01`
- **Category:** Runtime Defect (Telegram UI Error Handling / Polling Deadlock Trigger)
- **Classification:** `A. RUNTIME DEFECT`
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
- **Classification:** `A. RUNTIME DEFECT`
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
- **Classification:** `A. RUNTIME DEFECT`
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
- **Classification:** `A. RUNTIME DEFECT`
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
- **Classification:** `A. RUNTIME DEFECT`
- **Severity:** `LOW`
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `bot/openhands_client.py:609-615`
- **Root Cause:** `collect_conversations` iterates up to `max_pages` (`20`) following `next_page_id` without checking whether `page_id` was already seen.
- **User / System Impact:** If OpenHands returns the same `next_page_id` repeatedly, `collect_conversations` executes up to `max_pages` (`20`) redundant HTTP requests and falsely sets `truncated=True` across both Telegram `list_conversations` (`bot/handlers.py:911`) and `MiniAppService.list_conversations` (`bot/web/services.py:626`).
- **Dependencies:** Independent (`WP-05`).
- **Proposed Remediation:** See `WP-05` (track `seen_pages: set[str]`; break deterministically and avoid false `truncated=True` or log repeated cursor safely).
- **Required Regression Tests:** Mock `search_conversations` returning repeated `next_page_id="p1"` and assert loop exits after seeing duplicate cursor.
- **Owner Approval Requirements:** `NONE`.
- **Mini App Cross-Boundary Implications:** **VERIFIED INDIRECT COUPLING (No Mini App Edits):** Read-only inspection confirms `MiniAppService.list_conversations` (`bot/web/services.py:626`, importing `bot/web/services.py:21`) calls `collect_conversations` (and `bot/web/services.py:266,661` calls `get_status`); fixing repeated cursor in `bot/openhands_client.py` prevents redundant upstream fetches for both surfaces without modifying Mini App files.

#### `NEW-DEF-06` — `UNSUPPORTED_ATTACHMENT_TEXT` Steers Users to Documents Even When Disabled
- **ID:** `NEW-DEF-06`
- **Category:** Runtime Defect (Policy-Inconsistent User Messaging)
- **Classification:** `A. RUNTIME DEFECT`
- **Severity:** `LOW`
- **Validation Verdict:** `CONFIRMED`
- **Exact Source Location:** `bot/handlers.py:1603-1606,1992-2013`
- **Root Cause:** Static constant `UNSUPPORTED_ATTACHMENT_TEXT` always includes *"أو إرسال ملف كمستند (Document) لو محتاج"* regardless of `config.attachment_document_intake_enabled`.
- **User / System Impact:** Once `WP-01` disables document intake by default, sending a photo/voice message actively instructs the user to send a Document that the next step immediately rejects.
- **Dependencies:** Directly tied to `WP-01` (`ATTACHMENT_DOCUMENT_INTAKE_ENABLED`).
- **Proposed Remediation:** See `WP-01` (render policy-aware message from `cfg.attachment_document_intake_enabled` in `handle_unsupported_attachment`).
- **Required Regression Tests:** Test `handle_unsupported_attachment` with intake `False` vs `True` asserting Document hint appears only when enabled.
- **Owner Approval Requirements:** Included under `WP-01` / `OD-03` if default flips.
- **Mini App Cross-Boundary Implications:** `NONE`.

#### Group 2 — Documentation & Audit Inaccuracies (`NEW-DEF-07`)

#### `NEW-DEF-07` — Factual & Classification Errors Across Prior Audit Reports
- **ID:** `NEW-DEF-07`
- **Category:** `B. AUDIT ERRATA` — Documentation / Audit Inaccuracy (**NOT** an OpenHandBot runtime defect)
- **Classification:** `B. AUDIT ERRATA`
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
- **Category:** `C. QUALITY GAP` — Test and Quality Gap (**NOT** an OpenHandBot runtime defect; **NOT** automatically a user-facing defect)
- **Classification:** `C. QUALITY GAP`
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

### E.0 Owner-Approved Provisional Priority Sequence

The following sequence is the **owner-approved provisional planning priority** (provisional planning guidance only — **not** permission to implement). It is preserved exactly as approved; any deviation must be documented with a technical reason and owner approval where required.

| Priority | Work package | Objective |
|---|---|---|
| `P0` | `WP-01` | Remove the normal-message sending obstruction and address attachment emergency mitigation |
| `P1` | `WP-02` | Protect Telegram callback answers and edits |
| `P1` | `WP-03` | Correct conversation authorization paths and operation outcomes |
| `P1` | `WP-04` | Prevent polling interruption caused by network and update-processing errors |
| `P2` | `WP-05` | Correct workers, cache invalidation, and cursor handling |
| `P2` | `WP-06` | Correct status presentation and oversized callback references |
| `P2` | `WP-07` | Ensure state consistency, attachment recovery, and SQLite safety |
| `P3` | `WP-08` | Correct documentation, configuration inventories, and parity tests |
| `P3` | `WP-09` | Execute the complete verification matrix |
| `P4` | `WP-10` | Qualify external hosting and infrastructure |

**Note on ordering vs. dependencies (`§G`):** `WP-02`, `WP-03`, and `WP-04` are all `P1` but must **not** be assumed parallelizable — they share `bot/handlers.py`, the outcome/acknowledgement code, and overlapping tests, and are therefore **sequenced** (`WP-02` -> `WP-03` -> `WP-04`). Likewise `WP-08` (`P3`) depends on `WP-01`, `WP-04`, `WP-06`, and `WP-07` finalizing defaults, commands, and schema before documentation/parity is frozen. The priority tiers express owner urgency; the dependency graph (`§G`) governs executable order.


### `WP-01` — Attachment Emergency Mitigation & Safe Lifecycle Escape
- **Objective:** Eliminate `DEF-001` permanent text-prompt self-DoS while respecting D-34/D-35 governance, data safety, and Mini App `MT-2` decision boundaries.
- **Included Defect IDs:** `DEF-001`, `DEF-011` (UX copy portion), `NEW-DEF-06` (policy-aware unsupported attachment text); cross-boundary dependency tracking for `DEF-014` (`BLOCKED_BY_EXCLUDED_MINI_APP` — `MT-2` governed by `OD-03`).
- **Explicit Exclusions:** Do NOT implement Stage B1/B2 remote upload (`DEF-015`); do NOT modify `bot/web/*`, `bot/web/static/*`, `tests/test_miniapp_*`, or `docs/MINI_APP.md` (`DEF-014` stays excluded); do NOT bypass terminal-state protections via undocumented shortcuts or delete unrelated user tables.
- **Exact Source Areas:** `bot/config.py:43,315-317`; `.env.example:2`; `bot/handlers.py:1603-1611,1885,2052-2204,2245,2291-2309`; `bot/db.py:1493-1663`; `bot/attachments.py:1062-1252`; `tests/test_repair_plan_02_life03_intake_kill_switch.py`, `tests/test_attachment_batch_state_routing_f1_1a.py`, `tests/test_attachment_terminal_routing_remediation.py`, `tests/test_unsupported_attachment_rejection.py`.
- **Implementation Constraints & Special Safeguards:**
  1. **Cross-Boundary Check (`ATTACHMENT_DOCUMENT_INTAKE_ENABLED`):** Disabling `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` by default (`False`) prevents Telegram `handle_attachment:1885` from staging files into `attachment_batches`, which directly starves excluded Mini App `OHB2-MT-2` (`bot/web/services.py:758-870`) unless explicitly set `1`. Default change therefore requires **`OD-03`** (`NONE` of Mini App files edited; behavioral impact explicitly approved).
  2. **Pre-existing Attachment Batch Policy (Conservative State-by-State Handling — NO Blanket Rejection, Deletion, or Reaping):** Setting `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=0` only disables new `handle_attachment:1885` staging; it does **not** alter `handle_text:2245` (`_handle_accompanying_text`). **Do NOT prescribe blanket rejection, deletion, or reaping of all pre-existing batches.** Any batch whose ownership (`telegram_id`/`conversation_id`), active `MT-2` download requirement, or lifecycle state cannot be verified **must remain preserved and be classified for manual reconciliation** rather than automatically deleted. Unrelated user records (`outbox`, `creation_jobs`, `watched`, `user_state`, `attachment_message_identity`) must remain intact. Every schema state (`bot/db.py:121-138`) follows the verified matrix below:

     | Current Schema State / Sub-Case (`bot/db.py:121-138`, `bot/attachments.py:1080-1125`) | Needed by Excluded Mini App `MT-2` (`bot/web/services.py:758-870`)? | Eligible for Local Cleanup? | Staging Files Must Be Retained? | Owner Decision / Manual Reconciliation Required? | Transition Reversible? | Process Crash During Cleanup Behavior |
     |---|---|---|---|---|---|---|
     | **`pending`** *(live: valid `t0`, `now < T0 + 15m` per `bot/db.py:1334,1624`)* | **YES** (while `item.status='stored'` & `now <` or `<= T0+15m` — see boundary note below) | **NO** auto-cleanup; only via explicit owner `/cancel` action (or natural `T0+15m` expiry) | **YES** until explicit owner `/cancel` or verified expiry | **YES** if batch active/unknown download need; owner-initiated `/cancel` required for live discard (`OD-03` governs default flag) | **NO** once transitioned to terminal `rejected` & `reaped` + unlinked (cannot un-reap or restore deleted bytes) | DB-first: `batch -> rejected` then item CAS `-> reaped` then `unlink`; crash after `reaped` preserves metadata & retries `unlink` idempotently on next `AttachmentReaper.sweep` |
     | **`pending`** *(clock-expired: valid `t0`, `now >= T0 + 15m`)* | **Boundary difference at exact `now == deadline`:** `bot/db.py:1360,1429` classifies `now >= deadline` as expired (`not live`), whereas `bot/web/services.py:805,850` returns `410 expired` / empty list only strictly when `now > deadline` (at `now > T0 + 15m`, **NO** on both paths) | **YES** via `AttachmentReaper` (`pending -> expired -> reaped -> unlink`) **after** pre-change inventory confirms expiry | **NO** once `expired` committed (unless audit hold applies) | Pre-change inventory required before bulk cleanup; **`OD-01`** required for post-expiry text routing (`TERMINAL_UNPROVEN`) | **NO** (`expired`/`reaped`/unlinked bytes have no reversal mechanism) | `AttachmentReaper._mark_expired` runs DB-first (`expired`), then `mark_attachment_item_reaped` (`reaped`) before `unlink`; crash retries `unlink` idempotently |
     | **`pending`** *(corrupt/unparseable `t0`)* | **Fail-closed NO** (`batch_deadline` is `None` -> `410`) | **NO blanket cleanup** (`_sweep_batch` skips `invalid_t0` with `SweepOutcome.SKIPPED, reason="invalid_t0"` at `bot/attachments.py:1188-1191` even if `list_expired_pending_attachment_batches` marks row `expired`) | **YES** until verified | **Manual reconciliation REQUIRED** (do not auto-delete unverified corrupt rows without inspection) | N/A (preserved) | Preserved untouched (`SKIPPED: invalid_t0`); manual operator inspection determines disposition |
     | **`intent_recorded`** *(`UNRESOLVED`, `bot/attachments.py:1095-1104`)* | **NO** (`MT-2` requires `batch.status='pending'`) | **NO auto-cleanup** (`AttachmentReaper` skips `0c` intentionally); eligible only via explicit owner `/cancel` or authorized recovery | **YES** while unresolved / pending Stage B or until explicit owner `/cancel` / authorized recovery | **YES:** Owner action (`/cancel`) or explicit authorized recovery decision; **`attachment_message_identity` MUST remain preserved (`D-35`)** | **NO** once marked `rejected`/`reaped` and staging bytes unlinked | If crash occurs after `batch -> rejected` & `item -> reaped` before `unlink`, `AttachmentReaper` step `2` detects `reaped` items and safely completes byte `unlink` |
     | **`dispatching`** *(`UNRESOLVED` Stage B state, no current producer)* | **NO** | **NO** (never auto-delete; unexpected state in Stage A runtime) | **YES** | **Manual reconciliation REQUIRED** (`AttachmentReaper` skips `0c`) | N/A (preserved) | Remains skipped/preserved safely across restarts |
     | **`uncertain`** *(`UNRESOLVED` Stage B state, no current producer)* | **NO** | **NO** (ambiguous remote delivery state; fail-closed) | **YES** | **Manual reconciliation REQUIRED** (`AttachmentReaper` skips `0c`) | N/A (preserved) | Remains skipped/preserved safely across restarts |
     | **`expired` / `delivered` / `rejected` / `failed`** *(terminal schema states)* | **NO** | **YES** for byte reaping **only with valid `t0`** (`AttachmentReaper._sweep_batch` steps `2`: `items -> reaped -> unlink`); terminal batches with unparseable `t0` are skipped (`SweepOutcome.SKIPPED, reason="invalid_t0"`, `bot/attachments.py:1188-1191`); **NO deletion of `attachment_batches` or `attachment_message_identity` (`D-35`)** | **NO** for valid-`t0` terminal batches (reaper target); **YES** (preserved) if `invalid_t0` | **`OD-01` REQUIRED** for whether `TERMINAL_UNPROVEN` keeps blocking subsequent unrelated prompts (and manual reconciliation for `invalid_t0`) | **NO** (`reaped`/terminal states and unlinked files are irreversible; `attachment_message_identity` remains `RESTRICT`-protected) | DB-first `mark_attachment_item_reaped` commits before `unlink` for valid-`t0` batches; interrupted `unlink` self-heals on next `sweep`; `invalid_t0` terminal batches stay `SKIPPED` |
     | **Out-of-enum / `NULL` status, Ambiguous Ownership, Orphan DB `attachment_items`, or Untracked Root Files (`<db_dir>/attachment_staging/`)** | Unknown / NO (`MT-2` requires owned `pending` batch) | **Separated by reaper path:** Out-of-enum/`NULL` batch status (`step 0b`) and ambiguous ownership -> **NO** (`AttachmentBatchIntegrityError` fail-closed / skipped); **Orphan DB `attachment_items`** (`batch_id` missing from `attachment_batches`) -> **YES** (`AttachmentReaper._sweep_orphan_items`, `bot/attachments.py:1253-1308`, marks `pending`/`stored` -> `reaped` and deletes referenced token files); **Untracked files in `<db_dir>/attachment_staging/`** (not in `known_tokens`) -> **NO** (`AttachmentReaper._scan_root_untracked`, `bot/attachments.py:1310-1334`, logs count only and **preserves** without deletion) | **YES** for out-of-enum, ambiguous, and untracked root files; **NO** for orphan DB `attachment_items` reaped by `_sweep_orphan_items` | **Manual reconciliation REQUIRED** for out-of-enum/`NULL`, ambiguous ownership, and untracked root files (`_scan_root_untracked`) | N/A for preserved cases; **NO** once orphan DB items are `reaped` and unlinked | Out-of-enum, ambiguous, and untracked root files stay preserved untouched; `_sweep_orphan_items` uses DB-first `mark_attachment_item_reaped` before `_remove_file` so interrupted orphan unlinks retry idempotently |

     *Boundary Note (`now == T0 + 15m`):* Two backend paths apply different strictness at exact equality `now == deadline`: `bot/db.py` (`list_live_pending_attachment_batches:1334` `< deadline`, `record_attachment_intent:1624` `< deadline`, `has_expired_pending_attachment_batch:1360` `>= deadline`, `list_expired_pending_attachment_batches:1429` `>= deadline`) treats `now == deadline` as expired, whereas the excluded Mini App service layer (`bot/web/services.py:805,850`) checks strictly `now > deadline` (`410 expired` / empty list). They therefore do not share one universal boundary inequality; both behaviors are documented as-is without altering code or selecting one as intended policy.

  3. **Safe `/cancel` Batch Abandonment:** Extend `cancel_route` / `cancel_route_button` (with explicit owner action) to discard an owner's active `pending` or `intent_recorded` batch using **DB-first, idempotent, crash-recoverable ordering** matching `AttachmentReaper`: (a) transition batch atomically in SQLite (`BEGIN IMMEDIATE` CAS) to terminal `rejected` while keeping `attachment_message_identity` intact (`D-35`, `ON DELETE RESTRICT`); (b) CAS items `pending`/`stored` -> `reaped`; (c) unlink staging bytes afterward (or trigger `AttachmentReaper`), so interrupted unlinks self-heal on retry. Preserve valid `user_state` and unrelated batch history.
  4. **D-34 Decision Boundary (`OD-01`):** Do **NOT** alter `classify_attachment_routing` (`bot/db.py:1557-1569`), `D-34`, `D-35`, or their runtime semantics until **`OD-01`** is explicitly decided and recorded by the owner (`AGENTS.md` §14). Keep `TERMINAL_ASSOCIATED` (`attachment_message_identity` match) fail-closed.
  5. **Policy-Aware Copy (`NEW-DEF-06`):** `handle_unsupported_attachment` must reflect `cfg.attachment_document_intake_enabled` (omit *"أو إرسال ملف كمستند (Document)"* when disabled); `ATTACHMENT_ACCEPTED_TEXT` must honestly reflect local staging only when enabled.
- **Dependencies:** **`OD-01`** (D-34 policy outcome) and **`OD-03`** (`ATTACHMENT_DOCUMENT_INTAKE_ENABLED` default vs `MT-2`). Should complete before `WP-07` and `WP-08`.
- **Required Owner Approvals:** Explicit recorded owner decision on **`OD-01`** (before changing affected terminal-routing behavior), **`OD-03`** (before flipping intake flag default), and explicit authorized operational recovery decision before any irreversible cleanup of pre-existing user batches.
- **Acceptance Criteria:** Normal text prompting works across all conversations after document upload + `/cancel` (and under `OD-01`-approved terminal routing); pre-existing ambiguous/unknown/active batches are preserved per matrix rather than blanket-deleted; partial disk-unlink crash recovers cleanly on reaper retry; `UNSUPPORTED_ATTACHMENT_TEXT` never advertises disabled intake; D-35 FK integrity holds; `0` Mini App files touched.
- **Regression Tests:** Multi-turn E2E tests for `intent_recorded` -> `/cancel` -> prompt in Conv B; mid-cleanup crash recovery (`item=reaped` -> retry); pre-existing batch preservation tests (`pending` live, `dispatching`, `uncertain`, unknown status, ambiguous ownership preserved; expired batches swept without touching `attachment_message_identity`); policy-aware unsupported attachment test; `OD-01`-matched D-34 tests.
- **Rollback / Recovery Considerations (Strictly Separated — Do Not Invent Recovery Capabilities):**
  1. **Configuration Rollback:** Setting `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=1` restores **future Telegram document intake behavior only**. It does **not** restore previously unlinked staging files or revert prior SQLite batch/item state transitions.
  2. **Database Recovery:** Config toggles alone do not rewrite DB rows. Once committed, terminal batch states (`delivered`, `expired`, `rejected`, `failed`) and item status `reaped` (`mark_attachment_item_reaped`) have **no implemented reversal or un-reap mechanism** in `bot/db.py` / `bot/attachments.py` and must be treated as **irreversible**; `pending` -> `rejected` / `reaped` cannot be rolled back.
  3. **Staging-File Recovery:** Unlinked bytes under `<db_dir>/attachment_staging/` cannot be recovered by changing configuration flags or DB statuses. Restoring deleted staging bytes would require an external, verified filesystem/backup snapshot (or re-upload by the user if retained in Telegram), if applicable; **the application has no built-in backup/restore feature and none is assumed or introduced here**.
  4. **Operational Recovery Prerequisite:** Before executing any irreversible cleanup, operators must capture a **pre-change read-only inventory** and evidence of affected `attachment_batches` / `attachment_items` states (including active `MT-2` windows), obtain an **explicit authorized recovery decision**, and preserve `PRAGMA foreign_keys=ON` and `attachment_message_identity` (`ON DELETE RESTRICT`) protections at all times.
- **Verification Requirements:** Independent `WP-09` verification categories (`1` Backend behavioral, `2` Backend integration, `3` Static/SAST/SCA, `5` Environment) on Python `3.11` & `3.13` + simulated SQLite crash-recovery test.

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
  4. **ADR §28.4 Manual Poison Policy (`OD-02`):** `/updates_status` and `/updates_skip <update_id> confirm` require explicit owner approval before implementation, and MUST enforce: owner-only `_guard` authorization, explicit `<update_id> confirm` double-confirmation matching an existing `update_failures` head-of-line entry, durable audit recording (`POISON_SKIPPED` / `EXPLICITLY_IGNORED` with `reason` + timestamp in SQLite), clear recovery feedback, and zero auto-skip behavior.
- **Dependencies:** Benefits from `WP-02` and `WP-03` stopping false `FAILED_PERMANENT` triggers; gated on **`OD-02`**.
- **Required Owner Approvals:** **REQUIRED (`OD-02`: ADR §28.4 poison-skip contract per `AGENTS.md` §14).**
- **Acceptance Criteria:** Known transient Telegram/network errors classify as `FAILED_TRANSIENT`; local non-transient `OSError` sub-types are not silently treated as transient retries; operators can safely inspect and manually skip confirmed permanent poison updates without SQLite CLI edits (only if `OD-02` approved).
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
- **Exact Source Areas:** `bot/messages.py:20-30,105,138`; `bot/keyboards.py:9-16,94-95,113-114,138-215`; `bot/handlers.py:1220` (`watch_conversation`), `1377` (`show_status`), plus callback ID resolution helpers; `bot/db.py` (proposed additive `callback_refs` table — **`NOT_YET_IMPLEMENTED — DESIGN PREREQUISITE`**); `tests/test_messages.py`, `tests/test_keyboards.py`, `tests/test_handlers.py`.
- **Implementation Constraints & Special Safeguards:**
  1. **`STATE_LABELS["unknown"]` Pre-Fix:** Add `"unknown": "غير معروف"` to `STATE_LABELS` (`bot/messages.py:20-30`) **before** changing `format_conversation:105`, `format_conversation_view:138`, `conversations_menu:113`, and `show_status:1377` from `conv.get("execution_status")` to `get_status(conv)`. Also review `watch_conversation:1220` (`db.set_last_state(conversation_id, get_status(conv))` vs `execution_status` contract — ensure `watches_menu` `state_label(w.last_state)` matches `Watcher`).
  2. **64-Byte `CALLBACK_DATA_LIMIT` Preserved (`bot/keyboards.py:9-16`):** Telegram's 64-byte UTF-8 cap on `callback_data` remains strictly enforced; every serialized callback payload (`deleteok:`, `unwatch:`, `files:{ref}:{gen}:{page}`, `file:{ref}:{gen}:{idx}`, etc.) must stay `<= 64` bytes for valid `MAX_CONVERSATION_ID_LEN = 64` IDs.
  3. **`callback_refs` Design Prerequisite (`NOT_YET_IMPLEMENTED` — Must Be Specified Before Coding):** No `callback_refs` table or token resolver exists in the current `17`-table `bot/db.py` schema (`lines 590-816`). Because safe token parameters (concrete TTL duration, row caps) cannot be invented from unverified project rules, **completing the concrete `callback_refs` lifecycle & security specification is an explicit design prerequisite for `WP-06` implementation**, and MUST satisfy all of the following requirements:
     - **Expiration / TTL Policy:** Define an explicit TTL / retention policy for persisted tokens (`created_at` / `expires_at`) aligned with Telegram inline-menu usage without assuming unbounded retention.
     - **Bounded Cleanup & Unbounded DB Growth Prevention:** Define deterministic bounded pruning (e.g., periodic expiry/excess-row pruning integrated into a safe existing lifecycle hook or bounded insert/lookup sweep — never an unapproved background daemon or unbounded table growth).
     - **Missing, Expired, Malformed, or Unknown Reference Handling:** Resolving a missing, expired, pruned, malformed, or unknown token **must fail closed cleanly** (answer callback safely via `_safe_answer` with stale-menu guidance such as requesting `/start`, record `EXPLICITLY_IGNORED` or `REJECTED_INELIGIBLE`, and **never** raise an unhandled exception into `_classify_failure` -> `FAILED_PERMANENT` that stalls polling).
     - **Ownership, Authorization, and User/Conversation Binding:** Persist and validate explicit `telegram_id` ownership binding (and `conversation_id` + allowed action/prefix scope where required so a token issued for `status:`/`files:` cannot be replayed on `deleteok:`), enforce `_allowed(...)` first, reject cross-user reference reuse fail-closed (`_authorization_ignored` / generic denial without leaking another user's `conversation_id`), and re-verify conversation authorization + `is_deleted` (`_authorized_conversation_status`) at dispatch time.
     - **Stale Callback Resilience:** Handle stale/expired callback taps across restarts without crashing polling or blocking `acknowledgment_boundary()`.
- **Dependencies:** Independent of `WP-01`..`WP-05` for `STATE_LABELS`; `bot/handlers.py` callback decoding coordinates sequentially with `WP-02`/`WP-03`; **persistent `callback_refs` implementation is gated on completing the Lifecycle & Security Design Prerequisite above**, and any schema addition (`17 -> 18` tables) must feed into `WP-08`.
- **Required Owner Approvals:** `NONE` for planning; explicit design-spec review before adding `callback_refs` schema (`17 -> 18` SQLite tables), preserving zero Mini App changes.
- **Acceptance Criteria:** `state_label(get_status({})) == "غير معروف"`; `sandbox_status="ERROR"`/`"MISSING"` renders `"خطأ بيئة"` across all menus/views; all `64`-char conversation IDs render `<= 64`-byte `callback_data` payloads; once design prerequisite is satisfied, tokens enforce user/action binding, TTL expiry, bounded cleanup, cross-user rejection, and fail-closed stale callback handling across restarts.
- **Regression Tests:** Boundary tests for `execution_status=None`, uppercase statuses, `sandbox_status="ERROR"`; `64`-char IDs across all keyboard builders; **dedicated tests for `callback_refs` expiration, bounded cleanup/pruning, malformed/missing/unknown references, cross-user reuse rejection, action-scope mismatch, authorization failures, and restart persistence**.
- **Rollback / Recovery Considerations:** `STATE_LABELS["unknown"]` is backward-compatible; an additive `callback_refs` table (`IF NOT EXISTS`) is non-destructive to existing tables (if ever reverted, old inline buttons in Telegram chat fall back cleanly to stale-menu handling).
- **Verification Requirements:** Independent `WP-09` verification categories (`1`, `2`, `3`, `5`).

---

### `WP-07` — State Consistency, Attachment I/O & Quotas, and Poller Concurrency Governance
- **Objective:** Improve atomicity of `user_state`/outcome writes, eliminate event-loop blocking during staging/reaping and concurrent quota races, and reconcile polling concurrency policy safely.
- **Included Defect IDs:** `DEF-006`, `DEF-011` (quota lock + async disk I/O), `DEF-013`, `NEW-DEF-03`.
- **Explicit Exclusions:** **Do NOT enable concurrent update execution inside `TelegramPoller.process_updates`** unless `Database._conn` thread/async safety, `BEGIN IMMEDIATE` write contention, and per-user ordering invariants are rigorously proven and approved (`OD-04`). Zero Mini App changes.
- **Exact Source Areas:** `bot/polling.py:155-178`; `bot/app.py:75-87`; `bot/attachments.py:612-760,1062-1252`; `bot/handlers.py:1216-1260,1592-1598,1714,2253-2263,2295-2309,2429-2431,2492-2510`; `bot/db.py` (atomic `clear_awaiting_and_outcome` / `set_awaiting_and_outcome` / `add_watched_and_outcome` helpers); `tests/test_one_shot_awaiting_atomicity.py`, `tests/test_repair_plan_01_resource_staging.py`, `tests/test_stage2_custom_polling.py`.
- **Implementation Constraints & Special Safeguards:**
  1. **No False SQLite+Telegram Atomicity (`DEF-013`, `NEW-DEF-03`):** SQLite transactions and Telegram HTTP requests (`reply_text`/`_safe_edit`) **cannot** form one atomic distributed transaction. Combine local DB state mutations (`clear_awaiting`, `set_awaiting`, `add_watched`, `remove_watched`) with durable outcome recording (`EXPLICITLY_IGNORED`/`DURABLE_COMPLETED`) atomically inside SQLite where safe, ensure idempotent re-execution if Telegram delivery throws afterward, and move `db.renew_awaiting(telegram_id)` (`bot/handlers.py:2263`) to execute **only after** whitespace validation (`_send_prompt:2321` or inside `_send_prompt` after `not text.strip()` check).
  2. **Attachment Filesystem Offload & Quota Reservation (`DEF-011`):** Offload **both** `StagingStore._write_to_path` (`bot/attachments.py:612-644`, `os.fsync`) **and** `AttachmentReaper.sweep` (`bot/attachments.py:1062-1135`) blocking disk I/O off the event loop via `asyncio.to_thread` (separating SQLite queries on the owner connection from thread-offloaded file I/O so `sqlite3.Connection` is never shared unsafely across worker threads without explicit synchronization!), and add an in-process async reservation ledger for `max_batch_items` / `max_batch_bytes` / `max_staging_total_bytes` when enabled.
  3. **Concurrency Proof Gate (`DEF-006`, `OD-04`):** By default, **preserve sequential batch processing** in `TelegramPoller.process_updates` and align comments in `bot/app.py:75-87` with `docs/OPERATIONS_RUNBOOK.md:123-127`. Concurrent intra-batch dispatch is strictly blocked unless proven safe across `Database._conn`, per-user `user_state`/`attachment_batches` serialization locks, and `list_cache` / `repo_nav` state, and approved by the owner.
- **Dependencies:** Depends on `WP-01` (attachment policy & cleanup) and `OD-04` (if proposing concurrency).
- **Required Owner Approvals:** **REQUIRED if enabling concurrent update dispatch (`OD-04`).** None if preserving sequential batching and aligning comments.
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
- **Objective:** Execute and report seven strictly independent verification evidence categories on supported target runtimes (`Python 3.11`, `Python 3.13`, `Node 24`) before any remediation release gate can pass.
- **Included Defect IDs:** `DEF-019` (gates closure of `DEF-001`..`DEF-018` and `NEW-DEF-01`..`NEW-DEF-08`).
- **Explicit Exclusions & Hard Reporting Prohibitions:**
  - **Syntax checks (`ast.parse` / `node --check`) NEVER count as behavioral verification.**
  - **Frontend test success (`node --test`) NEVER counts as backend verification.**
  - **Missing dependencies NEVER produce `PASS` — they must be reported strictly as `BLOCKED`.**
  - **Unavailable external infrastructure NEVER counts as qualified — it remains `NOT_RUN` / `UNVERIFIED`.**
  - **Partial test execution MUST NEVER be reported as a complete suite pass.**
  - **Historical results (`docs/reviews/*`) MUST NEVER be reported as current execution evidence.**
  - **Mini App exclusion preserved:** execute existing `tests/test_miniapp_*.py` and `tests/frontend/*.test.js` strictly **read-only** without modifying any excluded Mini App code, test, configuration, or `docs/MINI_APP.md`.
- **Exact Source Areas:** `.github/workflows/ci.yml:1-68`, `requirements.txt`, `requirements-dev.txt`, `tests/` (`126` `test_*.py` test files out of `131` `.py` files total, excluding `5` helper/config files: `__init__.py`, `conftest.py`, `_miniapp_helpers.py`, `_mutation_harness.py`, `_real_http.py`), `tests/frontend/` (`23` `*.test.js` test files out of `24` files total, excluding helper `dom_stub.js`), `start.sh`, external `WP-10` qualification scripts/workflows.
- **Independent Verification Evidence Categories (`PASS` / `FAIL` / `BLOCKED` / `NOT_RUN` Strictly Separated):**

  | # | Independent Category | Target Commands / Scope | What It Proves | What It Does NOT Prove | Exact Pass Criteria & Required Output | Baseline Container Status (this session) |
  |---|---|---|---|---|---|---|
  | **1** | **Syntax Checks** | `ast.parse` over all `.py`; `node --check` on inline/standalone JS | Files are syntactically parsable only | **Nothing behavioral** — a file can parse and still be logically wrong | `ast_fail = 0`; no `node --check` syntax errors; output logged | **`PASS`** (`165/165` `.py` parse clean; JS unchanged) |
  | **2** | **Unit Tests** | `python -m pytest` over unit/handler/worker/DB behavioral modules (`Python 3.11` & `3.13`) | In-process handler/worker/DB/state-machine logic, exception paths, callback safety, unit invariants with test doubles | Real OS/multi-module E2E wiring, Telegram/OpenHands network behavior, live hosting durability, or frontend JS UX | Exit code `0`; exact `passed / failed / skipped / xfailed` counts (`0` failures; `0` skipped failures masking defects) | **`BLOCKED`** (`10/10` Python packages missing) |
  | **3** | **Integration Tests** | Full `python -m pytest -q` (E2E polling, SQLite WAL/crash recovery, startup contracts + read-only `tests/test_miniapp_*.py` & `tests/test_real_http_miniapp_download.py`) | Cross-module bot + SQLite + ASGI read-only integration, crash-recovery transitions, regression immunity across the full Python suite | Static lint/SAST/SCA hygiene, browser WebView rendering, or live Telegram/OpenHands/Enzonic infrastructure | Exit code `0` on **entire** Python suite (exact total count + `0` failures on both `Python 3.11` & `3.13`; partial subset runs invalid) | **`BLOCKED`** (`10/10` Python packages missing) |
  | **4** | **Static Analysis** | `python -m pyflakes bot/ automation/ tools/ main.py tests/` | Absence of undefined names / unused imports | Runtime behavioral correctness or logic defects | Exit code `0`; `0` `pyflakes` diagnostics | **`BLOCKED`** (`pyflakes` absent) |
  | **5** | **SAST** | `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | Zero high-severity Python SAST findings | Runtime behavioral correctness or zero-day host posture | Exit code `0`; `0` high-severity `bandit` findings | **`BLOCKED`** (`bandit` absent) |
  | **6** | **Dependency Vulnerability Scanning** | `python -m pip_audit -r requirements-dev.txt` | Zero known vulnerabilities in pinned packages | Runtime behavioral correctness or unpinned external host posture | Exit code `0`; `No known vulnerabilities found` | **`BLOCKED`** (`pip_audit` absent) |
  | **7** | **External Infrastructure Checks (`WP-10`)** | Out-of-band Enzonic host fingerprint + `enzonic-sftp-readonly-check.yml`, live `canary.py` (`H1`), `HOST-02` public HTTPS ingress, upstream OpenHands check | Real Enzonic SFTP authentication, durable SQLite persistence across host container restarts, live HTTPS/TLS ingress, and live OpenHands API schema support | Local code correctness without Categories 1–6; never inferred from local mocks or CI | Real external execution logs/artifacts under `OD-05` proving green `workflow_dispatch`, multi-restart `H1` persistence, and `HOST-02` TLS | **`NOT_RUN`** (unverified external infra) |

- **Frontend / Mini App regression suite (read-only, separate from backend):** `node --test tests/frontend/*.test.js` (CI target `Node 24`; read-only, `0` Mini App files edited) -> **`PASS`** this session (`280` tests, `280` pass, `0` fail, `0` skipped on local `Node v24.22.2`). This confirms JavaScript unit invariants only and **proves nothing** about backend Python behavior, ASGI runtime, or live Android 12 WebView download UX.
- **Evidence-source discipline (mandatory distinctions):**

  | Evidence class | Meaning | Reporting rule |
  |---|---|---|
  | **Actually run (this session)** | Commands executed in the current container with captured output | Report as `PASS`/`FAIL` with exact counts; only Categories `1` (syntax) and the read-only frontend suite qualify here. |
  | **Blocked by missing dependencies** | Command cannot execute because required packages are absent | Report strictly as **`BLOCKED`** — never `PASS`. |
  | **Not run** | Command not attempted (e.g., external infra, `Python 3.11`/`3.13` CI matrix) | Report strictly as **`NOT_RUN`** / `UNVERIFIED`. |
  | **Historical results** | Counts recorded in `docs/reviews/*` from earlier sessions | Archival only; **never** current execution evidence. |
  | **Future acceptance requirements** | What must pass before a release gate | State as acceptance criteria, **not** as achieved status. |

- **Dependencies:** Gates completion of `WP-01`..`WP-08`; Category `7` remains strictly decoupled under `WP-10` & `OD-05`.
- **Required Owner Approvals:** `NONE` for CI execution; **REQUIRED** if `pip_audit` forces dependency pin changes outside original scope (`AGENTS.md` §4), or for any Category `7` (`WP-10`) live operation (`OD-05`).
- **Acceptance Criteria:** Explicit per-category status ledger (`PASS` / `FAIL` / `BLOCKED` / `NOT_RUN`) with exact command output and counts; Categories `1`–`6` all **`PASS`** on `Python 3.11`, `Python 3.13`, and `Node 24` before local code release (`Gates A–C`), and Category `7` **`PASS`** before `Gate D` cutover.
- **Regression Tests:** Full repository suite (`126` `test_*.py` Python test modules among `131` `tests/**/*.py` files + `23` `*.test.js` JS test modules among `24` `tests/frontend/*` files + new WP tests), executed without skipping/disabling failing checks.
- **Rollback / Recovery Considerations:** Verification gate only; any `FAIL`, `BLOCKED`, or partial-run gap blocks gate transition.
- **Verification Requirements:** Real per-category command transcripts and counts from actual target environments (never historical `docs/reviews/*` archives or `ast.parse` substitutes).

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

- **`WP-01`:** `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` traced to Mini App `MT-2` (`bot/web/services.py:758-870`); requires `OD-03`; exact `now == T0 + 15m` difference (`bot/db.py` `>=` vs `bot/web/services.py` `>`) documented as-is; `_sweep_batch` skipping `invalid_t0`, `_sweep_orphan_items` DB orphans, and `_scan_root_untracked` preservation distinguished explicitly; rollback/recovery strictly separated (config flag restores future intake only; `rejected`/`reaped`/unlinked files irreversible; no invented backup feature; pre-change inventory + explicit recovery decision required); conservative state-by-state pre-existing batch matrix (NO blanket deletion/rejection; ambiguous/unknown/`dispatching`/`uncertain` batches preserved for manual reconciliation); safe DB-first `/cancel` (`rejected` -> `reaped` -> `unlink`, keeping `attachment_message_identity`); `OD-01` boundary explicit; includes `NEW-DEF-06`.
- **`WP-02`:** All `28` `q.answer()` + all `5` bare `q.edit_message_text()` (`787,793,805,841,869`); post-commit safety (`notifications_toggle:855->869`); `"Message is not modified"` handled as benign no-op.
- **`WP-03`:** False `list_conversations`/`_show_repos` 5xx claims removed; `5` `_authorized_conversation` callers + `delete_conversation_confirm:1307-1318`; `reposearch` 4xx & `False` race; `outcome=None` fixes; `send_document` + raw `send_message`/`send_copyable`/`send_long` (`NEW-DEF-04`); preserves `FAILED_TRANSIENT` operational vs `PARTIAL_OR_UNKNOWN` vs `FAILED_TRANSIENT` display distinctions.
- **`WP-04`:** Known transient exceptions (`RetryAfter`, `TimedOut`, `NetworkError`, `asyncio.TimeoutError`, `httpx.TransportError`); context-inspected `OSError` (never blanket all `OSError`); fail-closed preserved; no auto-skip; ADR §28.4 manual `/updates_status` + `/updates_skip` gated on `OD-02` with authz, confirmation, auditability, and recovery.
- **`WP-05`:** Watcher/Notifier `continue`/`return`; both `wait_for_start` fallback blocks (`733-746`, `792-806`); `deliver_outbox(outbox_id)` contract; creation `list_cache` invalidation (`NEW-DEF-02`); `collect_conversations` `seen_pages` guard (`NEW-DEF-05`).
- **`WP-06`:** `"unknown": "غير معروف"` added to `STATE_LABELS` before switching UI + `watch_conversation:1220` to `get_status(conv)`; 64-byte `CALLBACK_DATA_LIMIT` preserved; `callback_refs` explicitly flagged **`NOT_YET_IMPLEMENTED — DESIGN PREREQUISITE`** requiring TTL/expiry, bounded cleanup, malformed/missing/expired handling without polling crashes, `telegram_id`/conversation/action binding, cross-user reuse protection, and dedicated tests; zero Mini App edits.
- **`WP-07`:** `NEW-DEF-03` included; explicit separation between SQLite atomic commit and best-effort Telegram HTTP reply; `renew_awaiting` moved after whitespace check; both `StagingStore` and `AttachmentReaper.sweep` disk I/O handled safely; quota reservation lock; concurrent polling blocked unless connection safety + per-user serialization are proven (`OD-04`); comments/runbook aligned.
- **`WP-08`:** `17` SQLite tables (or `18` only if `callback_refs` design prerequisite is approved & implemented); all `20` env vars; `notification_inbox` recovery; `ZERO_TOUCH_STARTUP.md` deletion & readiness fixes; `NEW-DEF-08` parity tests; `docs/MINI_APP.md` and `Config.mini_app_*` untouched.
- **`WP-09`:** Python `3.11`/`3.13` + Node `24` matrix with 7 strictly independent evidence categories (Syntax `1`, Unit `2`, Integration `3`, Static Analysis `4`, SAST `5`, Dependency Scan `6`, External `7`) reported as `PASS` / `FAIL` / `BLOCKED` / `NOT_RUN`, exact test counts, mandatory evidence-source discipline (actually-run vs blocked vs not-run vs historical vs future acceptance), and hard bans on syntax-as-behavioral, frontend-as-backend, missing-deps-as-pass, partial-as-complete, or historical-as-current reporting; Mini App files strictly unmodified.
- **`WP-10`:** External live qualification completely decoupled and owner-authorized (`OD-05`).

---

## F.1 Special Technical Safeguard A — `NEW-DEF-03`: Distributed State & Delivery (`SQLite` + Telegram)

SQLite (durable local state) and the Telegram Bot API (external delivery) are **two separate systems** and **cannot** be treated as one atomic transaction. No design in this baseline may claim exactly-once external delivery. The required design contract for `NEW-DEF-03` (and its companion `DEF-013`) is:

1. **Durable state transitions:** All local state changes (`clear_awaiting`, `set_awaiting`, `add_watched`, `remove_watched`, attachment batch/item transitions) are committed **first and atomically inside SQLite** (a single `BEGIN IMMEDIATE` transaction together with the update outcome record where safe), so a crash never leaves a half-written local state.
2. **Retry semantics:** Local state changes are idempotent and safe to re-execute after a crash or redelivery; re-execution must converge to the same state (CAS / `INSERT OR IGNORE` / conditional `UPDATE ... WHERE status=...`).
3. **Idempotency boundaries:** The idempotency key is the Telegram `update_id` (via `processed_updates`). An operation whose local effect already committed must not re-apply a second time on redelivery.
4. **Ambiguous delivery outcomes:** A Telegram `send` that fails after the request may or may not have been delivered is recorded as ambiguous (`PARTIAL_OR_UNKNOWN`), **never** as success. The user may see a duplicate; the system must not lose data.
5. **Crash recovery:** On restart, in-flight operations are re-derived from durable SQLite state; `processed_updates` is the dedup source and `settings.acknowledgment_boundary` (monotonic) is the resume point.
6. **Duplicate prevention where technically possible:** Use `update_id` dedup and CAS to avoid re-sending where the delivery outcome is known; accept that **at-least-once** is the achievable guarantee for Telegram delivery.
7. **Reconciliation behavior:** Ambiguous/uncertain records remain for operator reconciliation; no silent auto-resolution of ambiguous external outcomes.
8. **Data retention & cleanup:** Terminal records (`reaped`, `expired`, `rejected`) and `attachment_message_identity` (FK `ON DELETE RESTRICT`) are retained per D-35; reaping is DB-first then file-unlink, idempotent on retry.
9. **Failure reporting:** Failures are recorded in `update_failures` (with `reason`/timestamp) and surfaced to operators; fail-closed blocking of the acknowledgement boundary is preserved.

**Prohibited:** claiming exactly-once delivery; proposing a false atomic transaction spanning SQLite and Telegram; silently treating an ambiguous outcome as success.

---

## F.2 Special Technical Safeguard B — `OSError` & Network Exception Classification

Exception retry classification must **not** use broad class-name matching alone (e.g., "all `OSError` are transient"). Each classification entry must document the following, and unknown/unsafe outcomes must **never** be silently treated as successful or safely retryable:

| Attribute | Requirement |
|---|---|
| **Exact exception class** | Name the precise class (`telegram.error.RetryAfter`, `telegram.error.TimedOut`, `telegram.error.NetworkError`, `asyncio.TimeoutError`, `httpx.TransportError`, specific `OSError` sub-types/`errno`). |
| **Originating operation** | State which call raised it (e.g., `q.answer`, `send_document`, `getUpdates`, staging `os.fsync`). |
| **Idempotent?** | Whether re-running the operation is safe (no duplicate side effect). |
| **External side effect may already have occurred?** | Whether the remote action could have partially completed. |
| **Retry safe?** | `FAILED_TRANSIENT` only when retry is provably safe; otherwise fail-closed. |
| **Retry limits & backoff** | Bounded attempts with backoff; no unbounded loops. |
| **Permanent failure behavior** | Deterministic non-retryable failures -> `FAILED_PERMANENT` (fail-closed, no auto-skip). |
| **Unknown-outcome behavior** | Ambiguous -> `PARTIAL_OR_UNKNOWN` (never success, never silent retry). |

**Scoped `OSError` rule:** transient socket/network errors (`ConnectionError`, `TimeoutError`, `errno` `EAGAIN`/`ECONNRESET`/`ETIMEDOUT`) may be `FAILED_TRANSIENT`; local disk/permission/structural errors (`PermissionError`, `FileNotFoundError`, `IsADirectoryError`, `ENOSPC`) must remain `FAILED_PERMANENT` or be surfaced for operator triage. The same contextual discipline applies to `httpx` and Telegram exceptions. This safeguard is realized in `WP-04` and must not introduce automatic poison-update skipping (`OD-02`).

---

## G. Corrected Dependency Graph & Execution Sequence

Because `WP-02`, `WP-03`, and `WP-04` all modify overlapping functions, error handlers, and outcome tests inside `bot/handlers.py`, **they are sequenced rather than parallelized** to prevent merge conflicts and masked outcome regressions. `WP-07` does **not** enable polling concurrency without explicit proof and `OD-04`.

```
[OD-01 (D-34 Policy) & OD-03 (Intake Default vs MT-2)]
   │
   ▼
Phase 0 — Emergency Attachment Mitigation
   └─► WP-01 [DEF-001, DEF-011 UX, NEW-DEF-06, DEF-014 cross-boundary]
          │
          ▼
Phase 1 — Sequential Handler & Polling Reliability (Shared file: bot/handlers.py)
   WP-02 [DEF-005, NEW-DEF-01] (Callbacks: 28 q.answer + 5 bare edits)
      │
      ▼
   WP-03 [DEF-003, DEF-004, NEW-DEF-04] (Outcomes, Stage4-F1, send_message/send_document)
      │
      ├───────────────────────◄ [OD-02 (ADR §28.4 Poison Policy)]
      ▼
   WP-04 [DEF-002] (_classify_failure + Manual Quarantine)
      │
      ├─────────────────────────────────────────┐
      ▼                                         ▼
Phase 2 — Functional & Worker Correctness   Phase 2 (UI / Long IDs)
   WP-05 [DEF-007, DEF-008, DEF-012,           WP-06 [DEF-009, DEF-010]
          NEW-DEF-02, NEW-DEF-05]               (STATE_LABELS["unknown"] + get_status
   (watcher/notifier/outbox/client)              + callback_refs [DESIGN PREREQUISITE])
      │                                         │
      └───────────────────┬─────────────────────┘
                          │
                          ├──────◄ [OD-04 (Only if proposing concurrency)]
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
   WP-09 [DEF-019] (Full Python 3.11 & 3.13 CI + Node 24 Gate for WP-01..WP-08)
      │
      ▼
Phase 4 — External Infrastructure Qualification (Strictly Separate & Owner-Gated)
   WP-10 [DEF-015, DEF-016] (Live Enzonic SFTP, H1 Canary, HOST-02, P0 Reopen Gate)
```

*Cycle Check:* Strictly acyclic (every edge flows strictly forward from Phase 0 -> Phase 1 -> Phase 2 -> Phase 2b -> Phase 3 -> Phase 4).

**Dependency-graph legend (mandatory classifications):**

| Edge / node class | Meaning | Members |
|---|---|---|
| **Mandatory prerequisites** | Hard sequencing edges between WPs | `WP-01` -> `WP-07`; `WP-02` -> `WP-03` -> `WP-04`; `WP-01`/`WP-04`/`WP-06`/`WP-07` -> `WP-08`; `WP-01`..`WP-08` -> `WP-09`; `Gates A–C` -> `WP-10` |
| **Owner-decision blockers** | Cannot proceed until the owner decides | `OD-01` + `OD-03` -> `WP-01`; `OD-02` -> `WP-04` Part 2; `OD-04` -> `WP-07` concurrency; `OD-05` -> `WP-10` |
| **Mini App cross-boundary blockers** | Backend changes that could alter excluded Mini App behavior | `DEF-014` (`MT-2`) `BLOCKED_BY_EXCLUDED_MINI_APP`; `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` default (`OD-03`) traced to `bot/web/services.py` |
| **Test-environment blockers** | Blocked by missing local dependencies | `WP-09` Categories `2`–`6` (`10/10` Python packages absent) |
| **External qualification (separate track)** | Strictly decoupled from local code fixes | `WP-10` (Enzonic SFTP, `H1` canary, `HOST-02`) |

**Phase mapping (preserved):** `1` Emergency reliability and message-path remediation; `2` Telegram callback and API functional correctness; `3` Polling and worker reliability; `4` State consistency and attachment recovery; `5` Documentation and quality parity; `6` Full verification; `7` External infrastructure qualification.

**Parallelization caution:** `WP-02`, `WP-03`, and `WP-04` share `bot/handlers.py`, the outcome/acknowledgement code, and overlapping tests, so they are **sequenced, not parallelized**. `WP-05` and `WP-06` touch largely disjoint files and may run in parallel after Phase 1. Any dependency requiring different ordering must be documented with its technical reason.

---

## H. Owner Decisions Register

Per `AGENTS.md` §14 and strict Mini App boundaries, **silence is NEVER treated as approval**. **`OD-01` through `OD-05` remain UNRESOLVED (`Status: PENDING_OWNER_DECISION`); no alternative below has been selected, preferred over owner policy, or executed.**

| Decision ID | Exact Question for Owner | Existing Behavior | Separated Policy Alternatives (Non-Selected) | Consequences | Can Work Proceed Without Decision? |
|---|---|---|---|---|---|
| **`OD-01`** *(D-34 `TERMINAL_UNPROVEN` — Genuine Owner Policy Decision)* | Under `classify_attachment_routing` (`bot/db.py:1557-1569`), which policy should govern future normal text prompts when an owner has terminal attachment batch rows without an `attachment_message_identity` match (`TERMINAL_UNPROVEN`)? **This decision cannot be inferred from preferred technical design; `classify_attachment_routing`, `D-34`, and `D-35` runtime semantics remain unchanged.** | `has_terminal_attachment_batch(telegram_id)` returns `True` globally across all conversations once any batch reaches `delivered`/`expired`/`rejected`/`failed`, so `_handle_accompanying_text` rejects all subsequent unmapped text via `TERMINAL_UNPROVEN` / `TERMINAL_ASSOCIATED` (`DEF-001`). | **Policy Outcome 1 — Preserve Existing `TERMINAL_UNPROVEN` Fail-Closed Behavior:** Keep `D-34` global terminal blocking unchanged in `classify_attachment_routing`; any unblocking requires an explicit, separate owner-authorized archival/reset action.<br>**Policy Outcome 2 — Permit Normal Text Routing Only Under a Precisely Defined, Verified Terminal Condition:** Permit unmapped text to pass only when an explicit, bounded, verified terminal criterion holds (e.g., confirmed `expired`/`rejected` terminal state with zero `LIVE`/`UNRESOLVED` batches and zero `attachment_message_identity` match, while keeping `TERMINAL_ASSOCIATED` strictly fail-closed) and update `D-34` contract/tests under owner authorization.<br>**Policy Outcome 3 — Require Manual Reconciliation When State or Message Identity Is Ambiguous:** Keep fail-closed blocking whenever batch status, ownership, `t0`, `UNRESOLVED` state (`intent_recorded`/`dispatching`/`uncertain`), `MULTI_LIVE`, or message-identity correlation is ambiguous, requiring explicit manual reconciliation rather than auto-routing. | **Outcome 1** preserves legacy `D-34` guarantees with zero relaxation, requiring manual/command unblocking.<br>**Outcome 2** unblocks unrelated text prompts automatically only within the verified condition, requiring explicit owner approval to amend `D-34` & D-34 tests.<br>**Outcome 3** prevents silent misrouting on ambiguity (combinable with Outcome 1 or 2 for ambiguous sub-cases). | **NO for affected `WP-01` routing behavior:** `classify_attachment_routing`, `D-34`, and `D-35` MUST NOT be altered and `WP-01` cannot implement terminal-routing changes until an explicit owner decision on `OD-01` is recorded. *(Unrelated `NEW-DEF-06` copy planning does not depend on `OD-01`.)* |
| **`OD-02`** *(ADR §28.4 Poison Quarantine)* | What manual recovery policy should unblock head-of-line polling deadlocks (`DEF-002`) caused by genuine `FAILED_PERMANENT` updates (e.g., `TextDocumentTooLargeError`)? | `FAILED_PERMANENT` stays in `_INELIGIBLE` permanently; polling halts until manual SQLite DB intervention or Telegram 24h expiry. `TelegramPoller.process_updates` (`bot/polling.py:161-162`) dispatches updates strictly sequentially in arrival order. The acknowledgement boundary is computed by `Database.commit_batch_outcomes` (`bot/db.py:2966-2988`) from `_outcome_in_txn` (`bot/db.py:3012-3016`), which reads **only** `processed_updates` — an `update_failures`-only record **cannot** advance the boundary. | **Option 1 (ADR §28.4 manual quarantine):** Add owner-only `/updates_status` and `/updates_skip <update_id> confirm` persisting a durable audit record and advancing offset only after explicit confirmation.<br>**Option 2 (Deterministic rejection split + manual skip):** Classify strictly deterministic user-limit rejections (like `TextDocumentTooLargeError` *after* user notification succeeded) as `REJECTED_INELIGIBLE` / `EXPLICITLY_IGNORED` while keeping unexpected exceptions fail-closed + `/updates_skip`.<br>**Option 3 (Defer schema quarantine):** `WP-04` Part 1 transient-classifier fix only, optional read-only `/updates_status`, leaving genuine permanent poison to an out-of-band operator runbook. | **Option 1** keeps all unhandled errors fail-closed until manual inspection.<br>**Option 2** reduces operator intervention for known >50MB file notices, while still requiring `/updates_skip` for unforeseen permanent crashes.<br>**Option 3** avoids any schema/command surface change but leaves `TextDocumentTooLargeError` wedging polling until manual DB work or 24h expiry. All options preserve `FAILED_TRANSIENT` fail-closed retries. **Risks of skipping/quarantining:** dropped reprocessing of a skipped `update_id`; same-batch interaction where the owner's `/updates_skip N confirm` arrives in `updates[1:]` while `updates[0]==N` is still head-of-line; required pre-dispatch skip check and an eligible override outcome readable by `_outcome_in_txn`. **Required if implemented:** owner-only authorization, explicit `<update_id> confirm` double-confirmation, durable auditability, and recovery behavior. | **WP-04 Part 1 YES / Part 2 NO:** Transient classifier fixes (`RetryAfter`/`TimedOut`/`NetworkError`/`asyncio.TimeoutError`/`httpx.TransportError`/scoped `OSError`) can be planned/implemented independently, but ADR §28.4 skip commands/outcomes MUST NOT be implemented without `OD-02`. No automatic poison-update skipping is implemented or authorized. |
| **`OD-03`** *(Backend Flag Default vs Excluded Mini App `MT-2`)* | Do you authorize changing the default of `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` (`bot/config.py:315-317`, `.env.example`) from `True` to `False`, knowing that this disables Telegram document staging unless explicitly opted into (`=1`), which in turn leaves the excluded Mini App `OHB2-MT-2` staged-attachments view empty by default? | `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` defaults to `True`: Telegram stages documents (`pending`) so `MT-2` can download them, **but** any follow-up text triggers `DEF-001` & `DEF-014`. | **Option 1 (Default `False` opt-in):** Set default to `False` (operators wanting `MT-2` local transfer set `=1` explicitly once `WP-01` `/cancel` & `OD-01` are settled).<br>**Option 2 (Keep default `True`):** Retain `True` and ship `OD-01`-approved resolution + `/cancel` + honest local-only `ATTACHMENT_ACCEPTED_TEXT` (`"ملف محفوظ محليًا فقط — افتح التطبيق للتنزيل أو /cancel للإلغاء"`). | **Option 1** prevents out-of-the-box document staging bricking, but disables zero-config `MT-2` usage.<br>**Option 2** keeps `MT-2` enabled out of the box, relying completely on `OD-01` + `/cancel` safety first. | **NO for changing default in `WP-01`:** Changing the default silently alters excluded Mini App behavior and is blocked without explicit `OD-03`. |
| **`OD-04`** *(Polling Concurrency vs Sequential Architecture in `WP-07`)* | Should `TelegramPoller.process_updates` (`bot/polling.py:161-162`) remain strictly sequential (`OPERATIONS_RUNBOOK.md:123-127` behavior), or be refactored to allow concurrent intra-batch dispatch (`bot/app.py:75-87`)? | `TelegramPoller.process_updates` runs one update at a time (`dispatch_and_wait`), while `Application.builder()` configures `.concurrent_updates(True)` over a single shared `sqlite3.Connection` (`check_same_thread=False`). | **Option 1 (Conservative sequential):** Preserve sequential per-batch dispatch and update `bot/app.py:75-87` comments to match `OPERATIONS_RUNBOOK.md:123-127`.<br>**Option 2 (Concurrent intra-batch):** Implement per-user async/DB locks, prove single-connection SQLite write safety, enqueue batch updates concurrently, and join once per batch. | **Option 1** carries zero intra-batch SQLite-lock/interleaving risk.<br>**Option 2** reduces batch head-of-line latency behind slow API reads, but risks SQLite transaction interleaving and same-user `user_state`/`attachment_batches` races unless proven. | **Option 1 comments-only alignment requires standard review; Option 2 BLOCKED** until technical proof and `OD-04` sign-off. |
| **`OD-05`** *(External Live Infra & Stage B Reopen — `WP-10`)* | Authorization & credentials to execute live Enzonic SFTP fingerprint check, `H1` persistence canary, and future `Stage B` reopen. | All live infra unverified; Stage B deferred. | Execute `WP-10` externally only upon owner instruction. | Required before production launch. | `WP-01`..`WP-09` local/CI work can proceed without `OD-05`; production cutover cannot. |

---

## I. Objective Release Gates

No gate may be declared passed using historical test records in `docs/reviews/*`, `ast.parse` syntax checks, partial suite runs, or Node frontend tests alone (`WP-09` Categories `1`–`7` are strictly independent). Every gate below records the **required evidence**, the **acceptance condition**, the **responsible WP**, the **blocking owner decisions**, and the **current status**.

| Gate | Prerequisite WPs & Decisions | Required Evidence | Acceptance Condition | Responsible WP | Blocking Owner Decisions | Current Status |
|---|---|---|---|---|---|---|
| **Gate 0 — Governance & Decision Gate** | `OD-01`, `OD-02`, `OD-03`, `OD-04`, plus `WP-06` `callback_refs` Design Prerequisite & `WP-01` Pre-Change DB Inventory | Written owner decisions recorded in a decision log | Decisions recorded before editing gated components (`D-34`, `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` default, ADR §28.4 poison skip, `WP-07` concurrency); `callback_refs` TTL/pruning/authz spec completed before `WP-06` DB changes; pre-change inventory captured before any irreversible `WP-01` cleanup | Governance / `WP-01`, `WP-06` | `OD-01`, `OD-02`, `OD-03`, `OD-04` | **`PENDING_OWNER_DECISION`** |
| **Gate A — Emergency Attachment Safety** | `WP-01` + `WP-09` (Categories `1`–`6`) | Test transcripts + `0`-diff proof on excluded Mini App files | `0` cross-conversation text bricks across `/cancel` and `OD-01`-approved terminal paths; ambiguous/unknown/`dispatching`/`uncertain` pre-existing batches preserved for manual reconciliation; idempotent reaper recovery verified; `UNSUPPORTED_ATTACHMENT_TEXT` accurate; `WP-09` Categories `1`–`6` `PASS`; `bot/web/*` & `bot/web/static/*` byte-for-byte unchanged (`0` diff) | `WP-01` | `OD-01`, `OD-03` | **`BLOCKED`** (`OD-01`/`OD-03` pending; backend tests `BLOCKED`) |
| **Gate B — Callback, Outcome & Polling Resilience** | `WP-02` + `WP-03` + `WP-04` + `WP-09` (Categories `1`–`6`) | Test transcripts (Python `3.11` & `3.13`) | `0` bare `q.answer(` and `0` bare `q.edit_message_text(` in `bot/handlers.py`; `0` matched handler exits with `outcome=None`; all `6` auth-failure paths preserve `5xx`/`429`; `send_document` and raw `send_message` errors handled safely; transient network/Telegram errors classify `FAILED_TRANSIENT`; ADR §28.4 skip tested (if `OD-02` approved); `WP-09` Categories `1`–`6` `PASS` | `WP-02`, `WP-03`, `WP-04` | `OD-02` (for `WP-04` Part 2) | **`PENDING_OWNER_DECISION`** / backend tests `BLOCKED` |
| **Gate C — Worker, UI Normalization, State & Docs Parity** | `WP-05` + `WP-06` + `WP-07` + `WP-08` + `WP-09` (Categories `1`–`6`) | Test transcripts (Python `3.11`/`3.13` + Node `24`) + parity tests | `clear_retry_not_before` failure skips cycle; both `wait_for_start` fallback paths tested; `deliver_outbox` target-isolated; `list_cache` cleared on creation; `seen_pages` halts loops; `STATE_LABELS["unknown"] == "غير معروف"` & `get_status()` unified; 64-char IDs pass `<= 64`-byte cap + `callback_refs` expiry/cleanup/authz tests pass; `StagingStore` & `AttachmentReaper.sweep` I/O non-blocking; `NEW-DEF-03` resolved; `17` (or schema-verified `18` if `callback_refs` added) SQLite tables & `20` env vars pass `NEW-DEF-08` parity tests; `WP-09` Categories `1`–`6` strictly `PASS` (`0` `FAIL`/`BLOCKED`) | `WP-05`–`WP-08` | `OD-04` (if concurrency proposed) | **`PENDING_OWNER_DECISION`** / backend tests `BLOCKED` |
| **Gate D — External Production Cutover Readiness** | `WP-10` + Gates A–C + `OD-05` + `WP-09` (Category `7`) | External run logs/artifacts | Live Enzonic SFTP fingerprint independently verified + green `enzonic-sftp-readonly-check.yml` run; `tools/katabump-sqlite-canary/canary.py` survives actual container restarts (`H1`); `HOST-02` HTTPS ingress verified externally with zero Mini App edits; `WP-09` Category `7` strictly `PASS` | `WP-10` | `OD-05` | **`NOT_RUN`** / `PENDING_OWNER_DECISION` |

*No gate may be marked passed on historical evidence alone. `NOT_RUN`, `BLOCKED`, `UNVERIFIED`, or `PENDING_OWNER_DECISION` are the correct statuses wherever the corresponding evidence has not been produced in the current environment.*

---

## J. Remaining Unknowns, Unverified Claims & Design Prerequisites

1. **`WP-09` Categories `2`–`6` Backend Dependencies (`BLOCKED` Locally):** Backend unit `pytest`, integration `pytest -q`, `pyflakes`, `bandit -lll -s B613`, and `pip_audit` remain **`BLOCKED`** in this container because all `10` Python packages in `requirements.txt` / `requirements-dev.txt` are absent. `Python 3.13.15` + `165/165` `ast.parse` syntax-only checks (Category `1` `PASS`) and `Node v24.22.2` `280/280` read-only frontend tests do **NOT** prove backend correctness. Historical `docs/reviews/*` reports are strictly archival, not current pass evidence.
2. **Git History & Working-Tree State (`PARTIALLY VERIFIED`):** `.git` **is present** this session (unlike the prior baseline). `HEAD` = `33530cad02f37755da7e7eedac57764a354a75b` on branch `main`, working tree **clean** at session start, remote `origin` = `https://github.com/TM-AEM/OpenHandBot.git`. Remote GitHub Actions run logs remain outside local verification scope (no authenticated CI-log inspection performed this session).
3. **`WP-06` `callback_refs` Lifecycle & Security (`DESIGN_PREREQUISITE`):** No `callback_refs` table exists in `bot/db.py` (`17` tables). Concrete TTL window, bounded cleanup strategy, malformed/expired ref behavior, and user/conversation/action binding remain an unimplemented design prerequisite prior to modifying `WP-06` schema (which would expand schema count from `17` to `18` tables if implemented).
4. **Live Hosting & Persistence (`DEF-016` / `WP-09` Category `7` — `NOT_RUN`):** Enzonic `us-four.enzonic.com:2022` SFTP host fingerprint validity, `ENZONIC_SSH_PRIVATE_KEY` functionality, SQLite durability across container restarts (`H1`), and `HOST-01`/`HOST-02` hosting capability remain unexecuted externally.
5. **Upstream OpenHands Cloud API Spec (`UNVERIFIED`):** `docs/API_NOTES.md:81` cites OpenAPI `v1.68.1`, `bot/openhands_client.py:344` cites `v1.79.0`, and proposals cite `v1.87.1` — live upstream schemas and scoped upload support (`DEF-015`) remain unverified externally.
6. **Excluded Mini App Runtime & WebView UX (`DEF-014` — `NOT_RUN` / `EXCLUDED_MINI_APP`):** Physical Android 12 Telegram WebView download verification for `MT-2` and live Mini App ASGI behavior under `HOST-02` remain unverified and outside modification scope. Backend configuration dependencies used by Mini App integration paths (e.g., `ATTACHMENT_DOCUMENT_INTAKE_ENABLED`, `Config.mini_app_*` defaults) are traced in `§E`/`§H` and any change to them is owner-gated (`OD-03`).
7. **Unresolved Owner Decisions (`OD-01`..`OD-05`):** All five owner decisions remain open (`PENDING_OWNER_DECISION`); no policy outcome or implementation step has been selected or executed on the owner's behalf.
8. **Finding-source evidence completeness:** All `19` `DEF` and `8` `NEW-DEF` entries carry source locations verified this session. No finding is classified `UNRESOLVED_CLASSIFICATION`; the mandatory categories (`NEW-DEF-07` = `B. AUDIT ERRATA`, `NEW-DEF-08` = `C. QUALITY GAP`) are applied, and `NEW-DEF-01`..`NEW-DEF-06` are classified `A. RUNTIME DEFECT` from direct source evidence.
