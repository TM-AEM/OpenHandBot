# OHB2 Independent Adversarial Audit Report Validation

**Validation Task ID:** `OHB2-INDEPENDENT-AUDIT-REPORT-VALIDATION`  
**Target Audited Package:** `docs/audits/OHB2-*.md` (6 files produced by `OHB2-COMPLETE-REPOSITORY-AUDIT-AND-REMEDIATION-MASTER-PLAN`)  
**Validation Mode:** Strictly Read-Only Repository Validation (only this single validation report added; `0` pre-existing code, config, test, or doc files modified)  
**Scope Exclusion Enforced:** Telegram Mini App (`bot/web/*`, `bot/web/static/*`, `tests/frontend/*`, `tests/test_miniapp_*.py`, `tests/test_real_http_miniapp_download.py`, `tests/_miniapp_helpers.py`, `docs/MINI_APP.md`, `mini_app_*` config fields) remains **`EXCLUDED_MINI_APP`**.

---

## A. Executive Verdict

**Overall Assessment:** **`CONDITIONALLY TRUSTWORTHY — SUBSTANTIVELY SOUND ON CORE DEFECTS, BUT CONTAINS MATERIAL FACTUAL AND SCOPE ERRORS REQUIRING ERRATA BEFORE EXECUTION`**

The six prior audit documents accurately diagnosed OpenHandBot's highest-severity architectural and operational risks — notably the `DEF-001` "Owner Brick" normal-prompt self-DoS, the `DEF-002` head-of-line polling deadlock and `_classify_failure` gap, the `DEF-005` 24/28 unwrapped `q.answer()` sites, worker bugs (`DEF-007`, `DEF-008`, `DEF-012`), `DEF-009` `get_status()` bypasses, `DEF-010` 64-byte `callback_data` overflow, and `DEF-017` runbook contradictions — and strictly respected the Mini App scope exclusion (`0` Mini App files targeted for edits).

However, independent source verification exposed **six factual/analytical errors** across the six reports and **eight additional de-duplicated findings (`NEW-DEF-01`..`NEW-DEF-08`)**:
1. **False Container Python Version (`3.10.12`):** Four audit docs claim the container only has `Python 3.10.12`; the container actually runs **`Python 3.11.2`** (`Py 3.11+` is present; third-party runtime/dev packages in `requirements*.txt` are what is missing).
2. **False SQLite Table Count (`19` vs `17`):** Four audit docs claim `bot/db.py` defines `19` SQLite tables; `Database._init_schema()` (`bot/db.py:590-816`) actually defines **17** tables (`4` listed in `docs/OPERATIONS_RUNBOOK.md` §4 + `13` omitted = `17`).
3. **False `Stage4-F1` Scope Claims on `list_conversations` & `_show_repos`:** `DEF-003` and `DEF-004` claim `list_conversations` and `_show_repos` swallow `5xx`/`429` operational `ApiError`s internally. In reality, **both already call `await _raise_if_operational_api_failure(exc)`** (`bot/handlers.py:917` and `2446`). The real gaps are narrower (`6` auth-error-swallowing callback handlers + `reposearch` 4xx/expiry-`False` handling + raw `send_document`/`send_message` sites).
4. **False `Disabled` Feature Classification:** `OHB2-INCOMPLETE-FEATURES.md:31` and `OHB2-FILE-BY-FILE-AUDIT.md:85` classify `followups`, `files`, `cost`, and `export` as `Disabled` via `HIDDEN_FEATURES`, contradicting **`bot/features.py:15` (`DEFERRED_FEATURES_HIDDEN = False`)**, where all four are **live and enabled**.
5. **Invented `_ACK_ELIGIBLE` Constants:** `OHB2-COMPLETE-REPOSITORY-AUDIT.md:51` lists `AMBIGUOUS_EXTERNAL` and `DISPLAY_FAILED` inside `_ACK_ELIGIBLE`. Neither constant exists in `bot/update_outcomes.py`, and both corresponding paths (`PARTIAL_OR_UNKNOWN`, `FAILED_TRANSIENT`) are **`_INELIGIBLE` (fail-closed)**.
6. **`WP-06` `STATE_LABELS["unknown"]` Trap:** `OHB2-REMEDIATION-MASTER-PLAN.md:166` assumes `STATE_LABELS["unknown"] == "غير معروف"`, whereas `bot/messages.py:20-30` defines **`None: "غير معروف"`** and omits `"unknown"`. Naively switching `conv.get("execution_status")` to `get_status(conv)` causes missing-status conversations to render literal `"unknown"` instead of `"غير معروف"`.

**Defect Verdict Summary (`DEF-001`..`DEF-019`):**
- **`CONFIRMED`:** **15** (`DEF-001`, `DEF-002`, `DEF-005`*, `DEF-006`, `DEF-007`, `DEF-008`, `DEF-009`, `DEF-010`, `DEF-011`, `DEF-012`, `DEF-013`, `DEF-014`, `DEF-015`, `DEF-016`, `DEF-018`) — *(`DEF-005` carries a minor evidence-label note on `handlers.py:857`).*
- **`CONFIRMED_WITH_SCOPE_CORRECTION`:** **4** (`DEF-003`, `DEF-004`, `DEF-017`, `DEF-019`).
- **`REFUTED`:** **0**.

---

## B. Review Baseline & Verification Scope

### B.1 Verified Locally in Container
- **Runtime Versions:** `python3` = **`3.11.2 (main, Oct 7 2026, 12:35:07) [GCC 12.2.0]`**; `node` = `v22.23.2`; `.git` directory = **`False`** (`git_exists: False`).
- **Repository File Inventory:** `334` total files excluding `.git`/`__pycache__`/`node_modules` (`328` baseline files + `6` existing audit files under `docs/audits/`). Exact baseline category counts verified:
  - `automation/`: `4` · `bot/` core: `22` · `bot/web/`: `20` · `docs/` root: `18` · `docs/decisions/`: `5` · `docs/proposals/`: `4` · `docs/reviews/`: `76` · `tests/*.py`: `131` · `tests/frontend/`: `24` · `tools/`: `3` · root/workflows/`.agent`/`src`: `21` (`328` total).
- **Python AST Parse Check:** `165 / 165` `.py` files parsed cleanly via `ast.parse` (`ast_fail: 0`).
- **Frontend Unit Test Suite (`tests/frontend/*.test.js`):** Executed `node --test tests/frontend/*.test.js` -> **`280 tests, 280 pass, 0 fail, 0 skipped`**.
- **Line-by-Line Source & Doc Inspection:** Directly inspected `bot/config.py`, `bot/app.py`, `bot/polling.py`, `bot/update_outcomes.py`, `bot/features.py`, `bot/handlers.py`, `bot/messages.py`, `bot/keyboards.py`, `bot/outbox.py`, `bot/watcher.py`, `bot/notifier.py`, `bot/attachments.py`, `bot/openhands_client.py`, `bot/db.py`, `.env.example`, `start.sh`, `README.md`, `docs/OPERATIONS_RUNBOOK.md`, `docs/ZERO_TOUCH_STARTUP.md`, `docs/API_NOTES.md`, `bot/web/services.py` (read-only lookup), and all 6 `docs/audits/OHB2-*.md` files.

### B.2 Blocked / Unavailable in Container
- **Missing Python Third-Party Packages (10/10 absent):** `pytest`, `pyflakes`, `bandit`, `pip_audit`, `telegram`, `httpx`, `starlette`, `uvicorn`, `dotenv`, `anyio`. All Python behavioral tests (`pytest`), static lint (`pyflakes`), SAST (`bandit`), and SCA (`pip_audit`) remain **`BLOCKED / NOT_RUN`** locally.
- **Live / External Checks:** Live Enzonic SFTP (`us-four.enzonic.com:2022`), `tools/katabump-sqlite-canary/canary.py` live restart canary (`H1`), live OpenHands Cloud API responses, Telegram Bot API behavior, and remote GitHub Actions CI run logs (`no .git` / read-only audit constraints) remain **`UNVERIFIED`**.

---

## C. Six-Document Validation Matrix

| Document | Overall Verdict | Verified Accurate Strengths | Verified Factual Errors, Inconsistencies, or Omissions |
|---|---|---|---|
| `OHB2-AUDIT-EXECUTIVE-SUMMARY.md` (68L) | **`ACCURATE_WITH_ERRATA`** | Correctly prioritizes `DEF-001` self-DoS, `DEF-002` polling deadlock, `DEF-005` `q.answer()`, and Phase 0–4 gate structure. | 1) Line `19`: falsely states container has `Python 3.10.12` (actual: **`Python 3.11.2`**).<br>2) Line `18`: inherits overstated "`8` handlers/helpers" claim for `DEF-004` (includes `list_conversations` & `_show_repos`, which already raise on operational failures).<br>3) Omits `5` bare `q.edit_message_text` calls (`NEW-DEF-01`). |
| `OHB2-COMPLETE-REPOSITORY-AUDIT.md` (116L) | **`ACCURATE_WITH_ERRATA`** | Strong architecture topology summary, accurate `DEF-001`..`DEF-018` synthesis, explicit Mini App boundary list (§7). | 1) Line `20` & `84`: miscounts SQLite schema as **19** tables (actual: **17** tables in `bot/db.py:590-816`).<br>2) Line `51`: **invents non-existent constants** `AMBIGUOUS_EXTERNAL` and `DISPLAY_FAILED` inside `_ACK_ELIGIBLE` (contradicts `bot/update_outcomes.py:40-53`, where neither exists and both states map to fail-closed `_INELIGIBLE` outcomes).<br>3) Line `57`: falsely includes `list_conversations` and `_show_repos` as swallowing `5xx`/`429`.<br>4) Line `94` & `96`: falsely states container is `Python 3.10.12` / missing Python `>= 3.11`. |
| `OHB2-COMPLETE-DEFECT-REGISTER.md` (550L, 69,889B) | **`MOSTLY_ACCURATE_ERRATA_REQUIRED`** | High-value 17-field entries; exact line numbers for `DEF-001`, `DEF-002`, `DEF-006..016`, `DEF-018`. | 1) `DEF-003` (`L111,115`) & `DEF-004` (`L149-152`): falsely assert `_show_repos` (`2446`) and `list_conversations` (`917`) do not call `_raise_if_operational_api_failure`.<br>2) `DEF-005` (`L173`): labels `notifications_toggle:857` `"DB-fail path"` whereas `L856-858` is the duplicate-`update_id` short-circuit (`bot/db.py:4268-4270`).<br>3) `DEF-017` (`L148`): repeats `19` tables instead of `17`.<br>4) `DEF-019` (`L189-194`): repeats `Python 3.10.12` error.<br>5) Misses `NEW-DEF-01`..`NEW-DEF-08`. |
| `OHB2-INCOMPLETE-FEATURES.md` (50L) | **`NEEDS_CORRECTION`** | Clean 7-category matrix; accurately identifies deferred Stage B, missing ADR §28.4 poison skip, missing `/cancel` batch reset, and Mini App boundary coupling. | 1) Line `31`: **critically misclassifies** `followups`, `files`, `cost`, `export` as **`Disabled`** via `HIDDEN_FEATURES`. `bot/features.py:15` sets **`DEFERRED_FEATURES_HIDDEN = False`**, so `is_hidden()` returns `False` for all 4 features — making `DEF-004`/`DEF-005`/`DEF-010` active production surfaces.<br>2) Line `27`: repeats overstated `DEF-004` listing-path scope.<br>3) Line `36`: repeats false `Python 3.10` container claim. |
| `OHB2-REMEDIATION-MASTER-PLAN.md` (263L) | **`FEASIBLE_WITH_REFINEMENTS`** | Sound Phase 0–4 DAG ordering, explicit D-34 owner-approval gate, zero Mini App files touched (`0/21`), well-structured verification requirements. | 1) `WP-03` (`L92-98`): includes already-migrated `list_conversations` & `_show_repos` 5xx claims; misses bare `send_message` guards (`NEW-DEF-04`).<br>2) `WP-06` (`L166`): claims `STATE_LABELS["unknown"] == "غير معروف"`, whereas `bot/messages.py:29` defines **`None: "غير معروف"`** (no `"unknown"` key!).<br>3) `WP-07` (`L179,187`): targets `StagingStore` sync I/O but overlooks `AttachmentReaper.sweep` sync filesystem calls (`bot/attachments.py:1062-1135`) and per-user serialization risks.<br>4) `WP-08` (`L202,207`): instructs documenting `19` tables (actual: **`17`**). |
| `OHB2-FILE-BY-FILE-AUDIT.md` (399L) | **`ACCURATE_INVENTORY_WITH_MINOR_DRIFT`** | Exact `328` baseline file accounting and exact Mini App exclusion partition (`20` `bot/web` + `1` `docs/MINI_APP.md` + `19` Python tests + `24` JS tests = `64` excluded files). | 1) Line `82` & `145`: states `19` SQLite tables instead of `17`.<br>2) Line `85`: marks `bot/features.py` as active Decision-4 hide list without noting `DEFERRED_FEATURES_HIDDEN = False`.<br>3) Line `181`: contains leaked scratch-file reference (`/tmp/ohb2_summary_328.txt`).<br>4) Line-count column uses `wc -l` (`\n` count, 1 less than 1-indexed `view_file` line count for newline-terminated files). |

---

## D. `DEF-001`..`DEF-019` Validation Matrix

| ID | Audited Severity | Validation Verdict | Mini App Boundary | Verified Direct Code/Doc Evidence | Corrections & Reviewer Notes |
|---|---|---|---|---|---|
| **`DEF-001`** | `CRITICAL` | **`CONFIRMED`** | `NONE` | `bot/config.py:43,315-317`; `bot/handlers.py:1885,2052-2204,2245,2291-2309`; `bot/db.py:812-814,1493-1663`; `bot/attachments.py:1095-1115` | Confirmed 100%. Note also: setting `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=0` only disables new `handle_attachment` intake (`L1885`), NOT `_handle_accompanying_text` (`L2245`), so already-affected owners stay bricked without DB intervention or a handler fix. |
| **`DEF-002`** | `HIGH` | **`CONFIRMED`** | `NONE` | `bot/update_outcomes.py:40-53,93-110`; `bot/polling.py:155-173,202-208`; `bot/handlers.py:477-495,1150-1154,1468,1567` | Confirmed. `_classify_failure` only treats `sqlite3.Error` (transient) and non-permanent `ApiError` as transient; `telegram.error.*`, `asyncio.TimeoutError`, `httpx.TransportError`, and `OSError` fall into `FAILED_PERMANENT`, permanently wedging `TelegramPoller._next_offset`. |
| **`DEF-003`** | `HIGH` | **`CONFIRMED_WITH_SCOPE_CORRECTION`** | `NONE` | `bot/handlers.py:2275-2283,2351-2354,2442-2447,2534-2536,2795-2798` | `outbox_mark_sent:2795-2798` (`outcome=None`), `_send_prompt:2351-2354` (`out_id==0`), `_start_new_chat:2534-2536` (`job_id==0`), and `reposearch:2281` expiry/4xx consumption are **CONFIRMED**. **Scope Correction:** `_show_repos:2446` ALREADY calls `await _raise_if_operational_api_failure(exc)`, so `5xx`/`429`/timeout in `_show_repos` DOES raise before `L2281` (only `4xx` consumes `reposearch`, and `consume_one_shot_awaiting(...) == False` on expiry race leaves `outcome=None`). |
| **`DEF-004`** | `HIGH` | **`CONFIRMED_WITH_SCOPE_CORRECTION`** | `NONE` | `bot/handlers.py:912-920,1129-1142,1206-1212,1276-1282,1307-1318,1449-1468,1567,1585-1591,2442-2447` | Confirmed for the **5** `_authorized_conversation` callers (`send_reply_txt:1129`, `watch_conversation:1206`, `delete_conversation_prompt:1276`, `export_conversation:1449`, `reply_prompt:1585`), **`delete_conversation_confirm:1307-1318`** (calls `_authorized_conversation_status` yet ignores `_auth_exc` at `L1317`), and unguarded `send_document` at `L1468,1567`. **Scope Correction:** `list_conversations:917` and `_show_repos:2446` ALREADY propagate `5xx`/`429`/timeout via `_raise_if_operational_api_failure`! Also note `send_reply_txt:1141` and `export_conversation:1465` record `PARTIAL_OR_UNKNOWN` (`mark_ambiguous_external`) rather than `mark_operational_failure` (`FAILED_TRANSIENT`). |
| **`DEF-005`** | `HIGH` | **`CONFIRMED`** | `NONE` | `bot/handlers.py` — 24 bare `q.answer(` (`780,799,834,850,857,893,965,1033,1072,1167,1195,1229,1266,1296,1439,1477,1526,1575,2302,2380,2401,2424,2473,2500`) vs 4 wrapped (`866,1120,1348,1402`) | Exact `24 / 28` count confirmed. Minor evidence-label fix: `notifications_toggle:857` is the duplicate-`update_id` short-circuit (`new_state is None`), not a DB-failure path (`bot/db.py:4268-4270`). |
| **`DEF-006`** | `MEDIUM` | **`CONFIRMED`** | `NONE` | `bot/polling.py:161-162,175-178` vs `bot/app.py:75-87`; `docs/OPERATIONS_RUNBOOK.md:123-127` | Confirmed. Note `OPERATIONS_RUNBOOK.md:123-127` already documents that `TelegramPoller` dispatches sequentially despite `.concurrent_updates(True)` in `bot/app.py:75-87`, so the contradiction is specifically between `bot/app.py` comments and `bot/polling.py`. |
| **`DEF-007`** | `MEDIUM` | **`CONFIRMED`** | `NONE` | `bot/watcher.py:215-221`; `bot/notifier.py:522-528` | Confirmed. Both catch `clear_retry_not_before` exceptions, log `"هيتخطّى"` ("will skip"), and lack `continue` (`watcher.py`) / `return` (`notifier.py`), falling directly into notification processing. |
| **`DEF-008`** | `MEDIUM` | **`CONFIRMED`** | `NONE` | `bot/outbox.py:210-224`; `bot/handlers.py:2366-2367` | Confirmed. `deliver_outbox(..., outbox_id)` checks `get_outbox(outbox_id)` then calls `db.claim_outbox(now_iso())` without `outbox_id` or `mature_before`. Currently unused in `main.py` worker runtime (used by tests). |
| **`DEF-009`** | `MEDIUM` | **`CONFIRMED`** | `NONE` | `bot/messages.py:20-48,56-61,105,138`; `bot/keyboards.py:113`; `bot/handlers.py:1377` | Confirmed. Note nuance for fix: `STATE_LABELS` maps `None: "غير معروف"` (`messages.py:29`) and omits `"unknown"`, whereas `get_status({})` returns `"unknown"` (`messages.py:44`). Also `watch_conversation:1220` passes `conv.get("execution_status") or ""` rather than `get_status(conv)`. |
| **`DEF-010`** | `MEDIUM` | **`CONFIRMED`** | `NONE` | `bot/files.py:29,36` (`MAX_CONVERSATION_ID_LEN=64`); `bot/keyboards.py:9-16,94-95,114,138-215` | Confirmed. Any valid `56..64`-char `conversation_id` triggers `ValueError("callback_data أطول من 64 بايت")` across prefixes like `deleteok:` (9 bytes), `unwatch:` (8 bytes), `files:{cid}:{gen}:{page}` (8+ bytes). |
| **`DEF-011`** | `MEDIUM` | **`CONFIRMED`** | `NONE` | `bot/attachments.py:612-644,699-735`; `bot/handlers.py:1609-1611,1714` | Confirmed. Cross-download quota reservation lock missing (`None` caps by default under D-12), sync `os.fsync` runs on event loop, and `ATTACHMENT_ACCEPTED_TEXT` omits local-only/no-Stage-B status. (Note: `AttachmentReaper.sweep` also runs sync filesystem I/O inside `OpportunisticSweeper`.) |
| **`DEF-012`** | `MEDIUM` | **`CONFIRMED`** | `NONE` | `bot/outbox.py:592-595,733-746,792-806` | Confirmed. Note additionally that **both** `wait_for_start` blocks (`L733-746` AND `L792-806`) lack `except Exception:` post-CAS fallback (only catching `ApiError`, and `L792-806` catching `CancelledError`). |
| **`DEF-013`** | `LOW` | **`CONFIRMED`** | `NONE` | `bot/handlers.py:2253-2261` | Confirmed (`clear_awaiting` commits before `reply_text` and before `mark_explicitly_ignored`). Also generalized by `NEW-DEF-03` across active `user_state` mutations. |
| **`DEF-014`** | `MEDIUM` | **`CONFIRMED`** | **`BLOCKED_BY_EXCLUDED_MINI_APP`** | `bot/web/services.py:798-802,842`; `bot/db.py:1572-1663`; `docs/reviews/OHB2-MT2-COMPLETION-AND-ADVERSARIAL-VERIFICATION.md` | Confirmed. `list_staged_attachments` queries `latest_pending_attachment_batch` and `download_attachment` requires `ATTACHMENT_BATCH_PENDING`, cutting off MT-2 once accompanying text moves batch to `intent_recorded`. Properly excluded from remediation edits. |
| **`DEF-015`** | `HIGH` | **`CONFIRMED`** | `NONE` | `bot/openhands_client.py` (no upload method); `README.md:175-184`; `docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md` | Confirmed. Remote Stage B1/B2 upload remains unimplemented and gated on upstream scoped upload credential + SSRF allowlist. |
| **`DEF-016`** | `HIGH` | **`CONFIRMED`** | `NONE` | `.github/workflows/enzonic-sftp-readonly-check.yml:1-126`; `tools/katabump-sqlite-canary/canary.py:1-245`; `docs/DEPLOY_ENZONIC.md` | Confirmed. Workflow is present and properly hardened (`workflow_dispatch`, `permissions: {}`), but live Enzonic SFTP fingerprint verification, `H1` persistence canary, and `HOST-01`/`HOST-02` qualification remain unexecuted. |
| **`DEF-017`** | `MEDIUM` | **`CONFIRMED_WITH_SCOPE_CORRECTION`** | `NONE` | `docs/ZERO_TOUCH_STARTUP.md:52-53,242`; `docs/OPERATIONS_RUNBOOK.md:46-54,73-74,135-137,362`; `README.md:70-89`; `.env.example:1-20`; `docs/API_NOTES.md:81` vs `bot/openhands_client.py:344` | All contradictions & env omissions confirmed (`ZERO_TOUCH_STARTUP.md:242` falsely denies remote deletion; `§1:52-53` conflicts with `/ready`/`/status`; `OPERATIONS_RUNBOOK.md` omits 13 env vars and `notification_inbox` recovery; `README.md` omits `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` & `MINI_APP_TRUSTED_PROXIES`). **Correction:** `bot/db.py:590-816` defines **17** SQLite tables (`OPERATIONS_RUNBOOK.md` §4 lists `4` tables and omits `13`, `4 + 13 = 17` — NOT 19; across the whole runbook `6` appear and `11` are missing). |
| **`DEF-018`** | `LOW` | **`CONFIRMED`** | `NONE` | `package.json:1-35`, `src/*`, `index.html`, `metadata.json`, `vite.config.ts`, `tsconfig.json`, `bun.lock`; `start.sh:56` | Confirmed (`start.sh:56` checks `telegram`, `httpx`, `dotenv`, `starlette`, `uvicorn` without `anyio`; AI Studio root scaffold coexists unwired). |
| **`DEF-019`** | `HIGH` | **`CONFIRMED_WITH_SCOPE_CORRECTION`** | `NONE` | Container runtime (`python3` = `3.11.2`); `requirements-dev.txt`; `.github/workflows/ci.yml` | Python runtime gates (`pytest`, `pyflakes`, `bandit`, `pip_audit`) ARE blocked locally. **Correction:** Root cause is missing virtual environment / `10` third-party packages (`pytest`, `pyflakes`, `bandit`, `pip_audit`, `telegram`, `httpx`, `starlette`, `uvicorn`, `dotenv`, `anyio`), **NOT** missing Python 3.11+ (`python3` in container is **`3.11.2`**). |

---

## E. Newly Discovered Defects (`NEW-DEF-*`, Strictly De-Duplicated)

### E.1 Runtime & Correctness Defects

| ID | Severity | Location | Technical Finding & Impact |
|---|---|---|---|
| **`NEW-DEF-01`** | `HIGH` | `bot/handlers.py:787,793,805,841,869` | **5 Bare `await q.edit_message_text(...)` Calls Without `_safe_edit`:** All 5 UI callback edits (`app_open:787,793`, `show_menu:805`, `notifications_menu:841`, `notifications_toggle:869`) call raw `q.edit_message_text` instead of `_safe_edit`. Double-tapping `app:open` or `notif:menu` (or clicking after stale message deletion) causes Telegram `BadRequest("Message is not modified")` or `TimedOut`, hitting `handle_processing_error` -> `FAILED_PERMANENT` -> **head-of-line polling deadlock (`DEF-002`)** at lines `787/793/805/841`, and polluting `update_failures` post-commit at line `869` (after `toggle_notifications_once` already committed `DURABLE_COMPLETED`). |
| **`NEW-DEF-02`** | `MEDIUM` | `bot/handlers.py:2513-2541`; `bot/outbox.py:811-833` | **Production Conversation Creation Never Invalidates `list_cache`:** `_send_prompt:2356`, `delete_conversation_confirm:1331`, and test-only `_create_chat:2558` invalidate `context.bot_data["list_cache"]`, whereas production `CreationWorker` -> `_finish_creation` has no reference to `bot_data` and `_start_new_chat` never invalidates `list_cache`. Newly created chats stay missing from `شاتاتي` up to `LIST_TTL` (`45s`). |
| **`NEW-DEF-03`** | `LOW/MEDIUM` | `bot/handlers.py:1216-1224,1241-1260,1592-1598,2262-2263,2295-2297,2307-2309,2429-2431,2492-2494,2505-2510` | **General Non-Atomic `user_state`/`watched` Mutation vs Outcome Commit & Premature `renew_awaiting`:** Beyond expired awaiting (`DEF-013`), `set_awaiting`/`clear_awaiting`/`add_watched`/`remove_watched` commit BEFORE `reply_text`/`_safe_edit` and before `mark_durable_completed`. A Telegram failure mid-reply leaves mutated DB state alongside `FAILED_PERMANENT`/`FAILED_TRANSIENT` in `update_failures`. Additionally, `handle_text:2263` calls `db.renew_awaiting` BEFORE `_send_prompt:2321` checks `if not text.strip()`, extending route expiry on rejected whitespace input. |
| **`NEW-DEF-04`** | `MEDIUM` | `bot/handlers.py:1045,1057,1062,1065,1084,1096,1101,1104,1131,1137,1144,1152,1160` | **Uncaught Raw `context.bot.send_message` / `send_copyable` / `send_long` Calls in Error & Empty-Reply Branches:** Distinct from `send_document` (`DEF-004`), `copy_reply`, `full_reply`, and `send_reply_txt` call raw `bot.send_message(...)` inside auth-rejection, API-error, and no-reply paths (and `send_copyable`/`send_long` on display paths). Any transient Telegram `TimedOut`/`RetryAfter` or `BadRequest` throws directly into `_classify_failure` -> `FAILED_PERMANENT` (`DEF-002`), bypassing `mark_display_failed` and pre-empting outcome commits. |
| **`NEW-DEF-05`** | `LOW` | `bot/openhands_client.py:609-615` | **`collect_conversations` Lacks Repeated-Cursor (`seen_pages`) Guard:** Unlike cursor-loop protection patterns, `collect_conversations` does not track seen `next_page_id` values. If upstream returns the same cursor twice, it issues `CONVERSATIONS_MAX_PAGES` (`20`) redundant API calls and returns `truncated=True`. |

### E.2 UX, Documentation & Verification Gaps

| ID | Severity | Location | Finding & Impact |
|---|---|---|---|
| **`NEW-DEF-06`** | `LOW` | `bot/handlers.py:1603-1606` | **Misleading Copy in `UNSUPPORTED_ATTACHMENT_TEXT` When Intake Disabled:** Even if `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=0` is defaulted (`WP-01`), rejecting photos/voice still sends *"أو إرسال ملف كمستند (Document) لو محتاج"* — actively steering users to a disabled feature. |
| **`NEW-DEF-07`** | `HIGH` (Doc Accuracy) | `docs/audits/OHB2-INCOMPLETE-FEATURES.md:31`; `docs/audits/OHB2-COMPLETE-REPOSITORY-AUDIT.md:51` | **Prior Audit Classification & Constant Errors:** `OHB2-INCOMPLETE-FEATURES.md:31` marks live `DEFERRED_FEATURES_HIDDEN = False` features as `Disabled`, and `OHB2-COMPLETE-REPOSITORY-AUDIT.md:51` cites non-existent `_ACK_ELIGIBLE` members `AMBIGUOUS_EXTERNAL`/`DISPLAY_FAILED`. |
| **`NEW-DEF-08`** | `MEDIUM` | `tests/test_deploy_manifest.py`; `tests/test_zero_touch_contract.py` | **Missing Doc/Env/Schema Parity Tests:** Existing manifest and startup tests pass despite `13` env vars and `11`/`13` SQLite tables missing from `OPERATIONS_RUNBOOK.md`, and `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` missing from `README.md`. |

---

## F. Incomplete-Features Validation (`OHB2-INCOMPLETE-FEATURES.md`)

| Audit Category | Prior Claims Verified Accurate | Required Corrections |
|---|---|---|
| **Fully Implemented** (10 rows) | Core routing, grouping/recovery, `completion_pending`, remote deletion + tombstones, watcher/notifier/inbox, unsupported media rejection, local A0–A4 staging/reaper, reply formatters, files/zip bounds, autopush are all present and accurately cited. | Note `deliver_outbox` (`bot/outbox.py:210-224`) is unused at runtime and `NEW-DEF-02`/`04`/`05` affect prompt creation cache invalidation, raw `send_message`, and cursor loops. |
| **Implemented but Not Integrated** (4 rows) | Accurate for `deliver_outbox`, `.github/workflows/enzonic-sftp-readonly-check.yml`, `tools/katabump-sqlite-canary/canary.py`, and root React+Vite template. | None. |
| **Partially Implemented** (4 rows) | Accurate on polling coverage, `get_status()`, aggregate quota locks, and Mini App MT-2 / `HOST-02` status. | Line `27` overstates `DEF-004` listing scope (`list_conversations` & `_show_repos` already propagate 5xx/429); add 5 bare `q.edit_message_text` (`NEW-DEF-01`). |
| **`Disabled`** (1 row, `L31`) | **`INCORRECT CATEGORY`** | **Reclassify to `ACTIVE / ENABLED` (`Fully Enabled`):** `bot/features.py:15` sets `DEFERRED_FEATURES_HIDDEN = False`. `followups`, `files`, `cost`, and `export` are all rendered in Telegram keyboards and handlers today (`README.md:30-35`). |
| **Deferred** (2 rows) | Accurate (`P0 Stage B1/B2/C` and `SW-02`). | None. |
| **Broken** (3 rows) | Accurate on `DEF-001` co-existence and `DEF-010` 56–64 char IDs. | Line `36`: correct blocker description from *"Python 3.10 stdlib container"* to *"Python 3.11.2 container lacking `requirements-dev.txt` packages"*. |
| **Missing** (5 rows) | Accurate (`ADR §28.4` poison skip, `/cancel` batch discard, upstream scoped upload/SSRF allowlist, webhook mode intentionally absent, live Enzonic proof). | Add missing operator visibility/remediation for `NEW-DEF-01` (bare edits) and `NEW-DEF-06` (policy-aware unsupported-attachment copy). |

---

## G. `WP-01`..`WP-10` Remediation Plan Validation

### G.1 Mini App Exclusion Compliance Check
- **Result:** **`PASS (100% COMPLIANT)`**. Inspected all 10 WPs (`OHB2-REMEDIATION-MASTER-PLAN.md:39-252`): **0** Mini App files (`bot/web/*`, `bot/web/static/*`, `tests/frontend/*`, `tests/test_miniapp_*.py`, `tests/test_real_http_miniapp_download.py`, `tests/_miniapp_helpers.py`, `docs/MINI_APP.md`, `Config.mini_app_*`) are targeted for modification. `DEF-014` remains `BLOCKED_BY_EXCLUDED_MINI_APP`.

### G.2 Work-Package-by-Work-Package Technical Review

| WP | Verdict | Feasibility, Governance & Technical Review Findings |
|---|---|---|
| **`WP-01`** | **`VALID_WITH_PRECONDITIONS`** | **Correct #1 priority.** Preconditions to enforce:<br>1) **Owner Sign-Off Required (`AGENTS.md` §14):** Modifying D-34 `TERMINAL_UNPROVEN` (`bot/db.py:1557-1569`) affects `tests/test_attachment_terminal_routing_remediation.py` and `tests/test_attachment_batch_state_routing_f1_1a.py` — do not alter D-34 semantics without explicit owner sign-off.<br>2) **Handle Already-Affected DBs & Disable Escape:** Setting `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=0` alone does NOT bypass `handle_text:2245` (`_handle_accompanying_text`); `WP-01` must cleanly auto-resolve or allow `/cancel` abandonment of `pending` & `intent_recorded` rows (with staging file unlink) before bypassing `TERMINAL_*` when disabled.<br>3) **Fix `NEW-DEF-06`:** Make `UNSUPPORTED_ATTACHMENT_TEXT` conditional on `config.attachment_document_intake_enabled` so disabled mode doesn't tell users to send Documents. |
| **`WP-02`** | **`VALID_EXPAND_SCOPE`** | Solid (`_safe_answer` for all 28 `.answer` sites). **Recommended Scope Expansion:** Bundle **`NEW-DEF-01`** (replace all 5 bare `await q.edit_message_text(...)` calls at `787,793,805,841,869` with `_safe_edit` / `_edit_or_send`, especially `869` post-commit) into `WP-02` so callback UI safety is closed completely in one step. |
| **`WP-03`** | **`NEEDS_SCOPE_REVISION`** | **Mandatory Scope Corrections:**<br>1) Remove false claim that `list_conversations` and `_show_repos` ignore `5xx`/`429` (`L917` & `L2446` already call `_raise_if_operational_api_failure`).<br>2) In `reposearch:2275-2283`, focus on: (a) NOT consuming `reposearch` when `_show_repos` returns from **4xx** `ApiError`, and (b) handling `consume_one_shot_awaiting(...) == False` (expiry race -> `mark_explicitly_ignored`).<br>3) Include `delete_conversation_confirm:1307-1318` (already calls `_authorized_conversation_status` — just check `_auth_exc` before `mark_explicitly_ignored`!) alongside the 5 `_authorized_conversation` callers (`1129,1206,1276,1449,1585`).<br>4) Fix `send_reply_txt:1141` and `export_conversation:1465` (`mark_ambiguous_external` vs `mark_operational_failure`) and guard both `send_document` (`L1468,1567`) **AND raw `send_message`/`send_copyable`/`send_long` (`NEW-DEF-04`)**.<br>5) Also check `watch_conversation:1220` (`get_status(conv)`) and `NEW-DEF-02` (`list_cache` invalidation on creation) or coordinate with `WP-05`/`WP-06`. |
| **`WP-04`** | **`VALID_WITH_GOVERNANCE_NOTE`** | Sound. Update `_classify_failure` (`handlers.py:490-495`) to classify `telegram.error.RetryAfter`, `TimedOut`, `NetworkError`, `asyncio.TimeoutError`, `httpx.TransportError`, and `OSError` as `FAILED_TRANSIENT`. Enforce ADR §28.4 owner sign-off on manual `/updates_skip <id> confirm` + `/updates_status` before auto-skipping any permanent failure; preserve strict fail-closed invariant for `FAILED_TRANSIENT`. |
| **`WP-05`** | **`VALID_WITH_SMALL_FIX`** | Confirmed (`watcher.py:221` `continue`, `notifier.py:528` `return`, `deliver_outbox` `claim_outbox_by_id` or removal, `outbox.py:733-746` AND `792-806` `CancelledError`/`Exception` cleanup). Also integrate **`NEW-DEF-02`** (invalidate `list_cache` or signal UI cleanly) and **`NEW-DEF-05`** (`seen_pages` cursor guard in `collect_conversations:609-615`). |
| **`WP-06`** | **`BUG_IN_PROPOSED_FIX`** | **Critical Catch in `WP-06` (`L166`):** `OHB2-REMEDIATION-MASTER-PLAN.md:166` claims `get_status({}) -> "unknown" -> STATE_LABELS["unknown"] == "غير معروف"`, which is **FALSE** — `bot/messages.py:29` defines `None: "غير معروف"` and **has no `"unknown"` key!** Replacing `conv.get("execution_status")` with `get_status(conv)` without adding **`"unknown": "غير معروف"`** to `STATE_LABELS` (`bot/messages.py:20-30`) will display raw `"unknown"` in UI menus whenever `execution_status` is absent! Also check `watch_conversation:1220` (`conv.get("execution_status")`). Short callback-ref table (`callback_refs`) is clean and Mini-App-safe. |
| **`WP-07`** | **`VALID_WITH_ORDERING_GUARDS`** | Enforcing `WP-01` prerequisite is right. Two cautions before parallelizing `TelegramPoller.process_updates`:<br>1) `bot/db.py` uses a **single shared `sqlite3.Connection`** across handlers + 5 background workers — per-user serialization lock (not just quota lock) is mandatory if multiple updates for the same `telegram_id` enter `update_queue` concurrently (`user_state`, `attachment_batches`, `NEW-DEF-03`). Otherwise keep sequential batching and align `bot/app.py:75-87` comments with `OPERATIONS_RUNBOOK.md:123-127`.<br>2) Async disk-I/O offload must cover **both** `StagingStore._write_to_path` (`612-644`) **and** `AttachmentReaper.sweep` (`1062-1135`). |
| **`WP-08`** | **`NEEDS_COUNT_CORRECTION`** | Must target **`17` SQLite tables** (NOT `19`) in `docs/OPERATIONS_RUNBOOK.md` §4 (`completion_pending`, `settings`, `notification_state`, `notifier_pending`, `notifier_retry_not_before`, `notification_inbox`, `deleted_conversations`, `web_sessions`, `processed_updates`, `update_failures`, `attachment_batches`, `attachment_items`, `attachment_message_identity`), plus `13` missing env vars (`ATTACHMENT_DOCUMENT_INTAKE_ENABLED` + `12` `MINI_APP_*`), `notification_inbox` §9, `ZERO_TOUCH_STARTUP.md:52-53,242`, `README.md`, `API_NOTES.md`, and `NEW-DEF-08` parity tests. Keep `WP-08` after `WP-01` and `WP-04` so final config defaults and `/updates_*` commands match docs. |
| **`WP-09`** | **`VALID`** | Must run full 5-command CI matrix (`pytest`, `pyflakes`, `bandit -lll -s B613`, `pip_audit`, `node --test`) on Python 3.11 & 3.13 + Node 22 outside this stripped container. |
| **`WP-10`** | **`VALID`** | Enzonic SFTP fingerprint out-of-band check + secret provisioning (`enzonic-sftp-readonly-check.yml`), `H1` persistence canary (`canary.py`), and P0 reopen gates remain strictly external & well-gated. |

---

## H. Corrected Remediation Sequence & Release Gates

```
Phase 0 (Emergency Unbrick — Must Execute First)
  └─► WP-01 [DEF-001, DEF-011 UX, NEW-DEF-06]
        Default ATTACHMENT_DOCUMENT_INTAKE_ENABLED=0, fix UNSUPPORTED_ATTACHMENT_TEXT copy,
        add owner /cancel batch discard + staging unlink, and reconcile D-34 with owner approval.

Phase 1 (Polling & Callback Resilience — Core Availability)
  ├─► WP-02 [DEF-005, NEW-DEF-01]
  │     Wrap all 28 q.answer() in _safe_answer AND migrate all 5 bare q.edit_message_text() to _safe_edit.
  ├─► WP-03 [DEF-003, DEF-004, NEW-DEF-04]
  │     Migrate 5 _authorized_conversation callers + delete_conversation_confirm:1317,
  │     close outbox_mark_sent/reposearch 4xx+False races, guard send_document AND raw send_message.
  └─► WP-04 [DEF-002]
        Classify TelegramError/TimeoutError/OSError/httpx.TransportError as FAILED_TRANSIENT;
        implement ADR §28.4 manual poison quarantine (/updates_status, /updates_skip) with owner sign-off.

Phase 2 (Workers, Consistency, Concurrency — Can Parallelize After Phase 1)
  ├─► WP-05 [DEF-007, DEF-008, DEF-012, NEW-DEF-02, NEW-DEF-05]
  │     Fix watcher/notifier continue/return, CreationWorker both wait_for_start fallback blocks,
  │     deliver_outbox(outbox_id) contract, list_cache invalidation on creation, seen_pages guard.
  ├─► WP-06 [DEF-009, DEF-010]
  │     Add "unknown": "غير معروف" to STATE_LABELS BEFORE switching UI + watch_conversation:1220
  │     to get_status(conv); add persistent SQLite callback_refs for 56-64 char conversation IDs.
  └─► WP-07 [DEF-006, DEF-011, DEF-013, NEW-DEF-03] (After WP-01; review SQLite single-conn lock)
        Combine expired & active awaiting/watched mutations atomically with outcome where safe
        (or move renew_awaiting after whitespace check); fix StagingStore reservation lock & async I/O;
        align process_updates vs app.py:75-87 with per-user serialization or documented serial batching.

Phase 3 (Docs Parity & Full Verification Gate)
  ├─► WP-08 [DEF-017, DEF-018, NEW-DEF-08] (After WP-01 & WP-04)
  │     Sync 17 SQLite tables, all env vars, remote deletion & /ready+/status docs; add parity tests.
  └─► WP-09 [DEF-019]
        Execute full .github/workflows/ci.yml suite (Python 3.11/3.13 pytest/pyflakes/bandit/pip_audit + Node 22).

Phase 4 (External Infrastructure & P0 Reopen Gate)
  └─► WP-10 [DEF-015, DEF-016]
        Out-of-band Enzonic host fingerprint + SFTP check, H1 SQLite persistence canary, P0 Stage B gate.
```

### Updated Release Gates
- **Gate A (Safe Daily Prompting):** `WP-01` + `WP-09` pass (`DEF-001` & `NEW-DEF-06` fixed; D-34 sign-off recorded; CI green).
- **Gate B (Resilient Polling & ACK):** `WP-02` + `WP-03` + `WP-04` + `WP-09` pass (zero bare `q.answer` / `q.edit_message_text` / `send_document` / unguarded `send_message` in `DEF-004`/`NEW-DEF-04` branches; zero `outcome=None`; poison skip tested).
- **Gate C (Workers, Long IDs, Concurrency & Docs):** `WP-05` + `WP-06` + `WP-07` + `WP-08` + `WP-09` pass (`"unknown"` label preserved; 64-char IDs pass; `17` tables synced in runbook).
- **Gate D (Production Cutover Readiness):** `WP-10` + Gates A–C pass (`H1` canary durable across restarts, Enzonic SFTP fingerprint independently confirmed, `HOST-02` verified externally without editing excluded Mini App files).

---

## I. Unverified Claims & Remaining Risks

1. **Python Test Suite, Static Analysis & Vulnerability Scan (`BLOCKED` Locally):** None of `pytest`, `pyflakes`, `bandit`, or `pip_audit` could run inside this container because all 10 runtime/dev packages (`pytest`, `pyflakes`, `bandit`, `pip_audit`, `telegram`, `httpx`, `starlette`, `uvicorn`, `dotenv`, `anyio`) are absent. Historical test claims in `docs/reviews/*` are **not** live execution evidence.
2. **Enzonic Hosting & SFTP Persistence (`UNVERIFIED`):** Live `us-four.enzonic.com:2022` SFTP connectivity, out-of-band host key fingerprint verification, SQLite persistence across container restarts (`H1`), and Mini App external HTTPS ingress (`HOST-02`) remain completely unverified against live infrastructure.
3. **Upstream OpenHands Spec Drift (`UNVERIFIED`):** `docs/API_NOTES.md:81` cites OpenAPI `v1.68.1`, `bot/openhands_client.py:344` cites `v1.79.0`, and `docs/proposals/` cites `v1.87.1` — live upstream endpoint schema behavior was not probed.
4. **Git History & Branch Protection (`UNVERIFIED`):** `.git` is absent in the container, preventing inspection of recent commit history or GitHub Actions logs.
5. **Excluded Mini App Cross-Boundary Risk (`BLOCKED_BY_EXCLUDED_MINI_APP`):** Disabling `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` by default (`WP-01`) prevents new `MT-2` transfers in the excluded Mini App while `Stage B` remains blocked (`DEF-014`/`DEF-015`); Android 12 physical WebView download verification remains unexecuted.

---

## J. Final Recommendation

1. **Accept the audit package with the mandatory errata documented in Sections C–G above** — do **not** treat `WP-03`, `WP-06`, or `WP-08` as drop-in specs until their factual corrections (`17` SQLite tables, `Python 3.11.2`, `DEFERRED_FEATURES_HIDDEN = False`, `list_conversations`/`_show_repos` already propagating `5xx`, `STATE_LABELS` missing `"unknown"`, and `NEW-DEF-01`..`NEW-DEF-08`) are applied.
2. **Request explicit owner decisions (`AGENTS.md` §14) upfront** on: (a) reconciling D-34 `TERMINAL_UNPROVEN` global text blocking in `WP-01`, and (b) ADR §28.4 `/updates_skip` poison-update policy in `WP-04`.
3. **Execute Phase 0 (`WP-01`) + Phase 1 (`WP-02` + `NEW-DEF-01`, `WP-03` + `NEW-DEF-04`, `WP-04`) first**, then validate every change against the complete CI matrix (`WP-09`) on Python 3.11 and 3.13 before resuming any live Enzonic deployment qualification (`WP-10`).
