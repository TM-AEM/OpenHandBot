# OHB2 Owner Decisions Briefing

**Task ID:** `OHB2-OWNER-DECISIONS-REVIEW`  
**Baseline Authority:** `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md` (consolidating `DEF-001`–`DEF-019`, `NEW-DEF-01`–`NEW-DEF-08`, and `WP-01`–`WP-10`)  
**Scope:** Plan-only owner-decision preparation (zero code, config, test, ADR, Mini App, or Git modifications)  
**Decision Status:** `PENDING_OWNER_DECISION — NO OPTIONS SELECTED, RECOMMENDED, OR IMPLEMENTED`

> **Governance Notice:** Per `AGENTS.md` §14 and the remediation baseline, silence is never treated as approval. All five owner decisions (`OD-01` through `OD-05`) remain explicitly unresolved (`PENDING_OWNER_DECISION`). No option in this briefing is preselected, ranked, endorsed, or executed.

---

## 1. Executive summary

Independent repository auditing (`OHB2-COMPLETE-REPOSITORY-AUDIT-AND-REMEDIATION-MASTER-PLAN`), independent report validation (`OHB2-INDEPENDENT-AUDIT-REPORT-VALIDATION`), and baseline errata consolidation (`docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md`) established ten ordered remediation work packages (`WP-01`–`WP-10`) covering `27` distinct defects (`DEF-001`–`DEF-019` and `NEW-DEF-01`–`NEW-DEF-08`). Although many technical fixes have deterministic engineering paths, **five high-impact architectural, behavioral, operational, and boundary decisions (`OD-01`–`OD-05`) require explicit owner resolution** before gated work packages or external operations can be authorized:

1. **`OD-01` — D-34 and Handling of Uncertain External Outcomes:** Current fail-closed global terminal routing (`TERMINAL_UNPROVEN` in `bot/db.py:1557-1569`) combined with non-deleting reaper expiration (`AttachmentReaper` transitioning `pending -> expired`) creates a permanent owner-wide text-prompting deadlock (`DEF-001`) after any Telegram document upload, while overlapping with unimplemented Stage B states (`dispatching`/`uncertain`) and ambiguous external outcome paths (`OUTBOX_SENDING`/`OUTBOX_UNKNOWN`, `CREATION_UNKNOWN`, `PARTIAL_OR_UNKNOWN`). The owner must choose how `D-34` terminal routing and uncertain/ambiguous state recovery behave going forward.
2. **`OD-02` — ADR §28.4 and Telegram/Network Exception-Handling Policy:** While transient network/Telegram exceptions can be fixed cleanly inside `_classify_failure` (`WP-04` Part 1), unblocking head-of-line polling deadlocks (`DEF-002`) caused by genuine `FAILED_PERMANENT` updates (including deterministic user-limit errors such as `TextDocumentTooLargeError`) requires an owner policy choice on implementing ADR §28.4 manual poison quarantine (`/updates_status`, `/updates_skip <update_id> confirm`, and separate schema metadata) versus deterministic rejection splitting or out-of-band SQLite intervention.
3. **`OD-03` — `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` Default and Relationship with `MT-2`:** Currently `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` defaults to `True` (`bot/config.py:43,315-317`). Flipping it to `False` affects the excluded Mini App `OHB2-MT-2` attachment-download feature (`bot/web/services.py:758-870`) without editing Mini App code by stopping out-of-the-box document staging (yet still leaving pre-existing bricked batches untouched unless `WP-01` resolves them). Keeping `True` preserves zero-config `MT-2` staging while depending critically on `OD-01` + `WP-01` `/cancel` mitigation.
4. **`OD-04` — `TelegramPoller` Concurrency and SQLite Safety:** `bot/app.py:86` passes `.concurrent_updates(True)` with an outdated `U04` comment (`L75-78`), whereas `TelegramPoller.process_updates` (`bot/polling.py:161-162`) strictly awaits each update sequentially via `dispatch_and_wait`, matching `docs/OPERATIONS_RUNBOOK.md:123-127`. The owner must decide whether to lock in sequential dispatch (reconciling comments/docs) or gate future intra-batch concurrency on a formal single-connection SQLite + per-user locking design and stress proof.
5. **`OD-05` — External Qualification, Live Verification, and `Stage B` Reopening:** All external infrastructure gates (`WP-10`, `DEF-015`, `DEF-016`) remain `NOT_RUN` / `UNVERIFIED`, including live Enzonic SFTP (`us-four.enzonic.com:2022`), SQLite `H1` persistence (`tools/katabump-sqlite-canary/canary.py`), `HOST-02` public HTTPS ingress, upstream OpenHands API schema alignment (`v1.68.1` vs `v1.79.0` vs `v1.87.1`), physical Android 12 WebView `MT-2` download verification, and `Stage B` remote upload reopening criteria (`.agent/PROGRESS.md:32-36`). The live Enzonic `"OpenHandBot"` (`Brave Grove`) server is strictly protected from canary or state-altering operations (`docs/DEPLOY_ENZONIC.md:27-42`).

This briefing presents the verified source facts, exact options without preselection, cross-decision interactions, work-package blocking status, permanently blocked boundaries, and verification limitations so the owner can record explicit decisions cleanly.

---

## 2. Current verified project state

The following facts were directly observed in the current workspace (`/app/applet`) during this review:

| Dimension | Verified Current State | Primary Evidence |
|---|---|---|
| **Runtime & Container Tooling** | `Python 3.11.2` and `Node v22.23.2` present; all `10/10` Python runtime/dev dependencies (`python-telegram-bot`, `httpx`, `starlette`, `uvicorn`, `python-dotenv`, `anyio`, `pytest`, `pyflakes`, `bandit`, `pip_audit`) are **absent** from the container. | Direct environment check (`requirements.txt`, `requirements-dev.txt`, `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md` §F/`WP-09`) |
| **Syntax & Test Inventory** | `165/165` Python files pass `ast.parse` (syntax-only, non-behavioral); `126` `test_*.py` modules among `131` `tests/**/*.py` files (`BLOCKED` due to missing Python packages); `280/280` read-only frontend JS tests pass across `23` `*.test.js` files (`tests/frontend/*.test.js` + `dom_stub.js`) under `Node v22.23.2`. | Direct Python `ast.parse` check + `node --test tests/frontend/*.test.js` |
| **Git Metadata** | `.git` directory is **absent** in this container (`GIT_EXISTS: False`); branch history, `HEAD` commit hash, working-tree diff, and remote CI logs cannot be verified locally. | Direct filesystem check |
| **SQLite Schema & Ownership** | `bot/db.py:550-816` initializes **`17` tables** on a single shared `sqlite3.Connection` (`check_same_thread=False`, `PRAGMA journal_mode=WAL`, `PRAGMA busy_timeout=5000`, `PRAGMA foreign_keys=ON`). **No `callback_refs` table exists** (`WP-06` design prerequisite). | `bot/db.py:550-816` |
| **Configuration & Flags** | `.env.example` defines **`20` environment variables**. `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` defaults to `True` (`bot/config.py:43,315-317`, strict `_parse_bool`). `DEFERRED_FEATURES_HIDDEN = False` (`bot/features.py:15`), keeping `files`, `export`, `cost`, and `followups` handlers registered (`bot/app.py:142-152`). `MINI_APP_ENABLED` defaults to `False`. | `.env.example:1-20`, `bot/config.py:43,99-117,315-317`, `bot/features.py:15` |
| **Attachment Intake & Staging** | Only `Document` (`filters.Document.ALL`) is accepted (`bot/app.py:34-45`); `handle_attachment` (`bot/handlers.py:1879-1990`) stages bytes locally into `<db_dir>/attachment_staging/` with `0700` dir / `0600` files (`bot/attachments.py:612-780`); `AttachmentReaper` (`bot/attachments.py:1062-1350`) transitions expired `pending` batches to `expired`, reaps item files (`reaped` + `unlink`), skips `invalid_t0` / `intent_recorded` / `dispatching` / `uncertain`, reaps orphan DB items, and leaves untracked files untouched. | `bot/app.py:34-45`, `bot/handlers.py:1879-1990`, `bot/attachments.py:600-780,1062-1350` |
| **Polling & Outcome Tracking** | `TelegramPoller` (`bot/polling.py:46-250`) pulls via `getUpdates(offset=boundary+1)`, dispatches each update sequentially via `dispatch_and_wait`, stores outcomes via `commit_batch_outcomes` (`bot/db.py:2945-3010`), and halts offset advancement fail-closed on any `FAILED_TRANSIENT`, `FAILED_PERMANENT`, or `PARTIAL_OR_UNKNOWN` (`bot/update_outcomes.py:1-111`). `ADR §28.4` (`ack_offset_submitted`/`confirmed` & poison-skip override) is **not implemented**. | `bot/polling.py:46-250`, `bot/update_outcomes.py:1-111`, `bot/db.py:2945-3010`, `docs/proposals/OHB2-TELEGRAM-ACK-ARCHITECTURE-ADR.md:1055,1115,1171` |
| **Mini App (`MT-2` & Exclusions)** | Excluded from modification scope (`bot/web/*`, `bot/web/static/*`, `tests/frontend/*`, `tests/test_miniapp_*.py`, `docs/MINI_APP.md`, `Config.mini_app_*`). Read-only inspection confirms `bot/web/app.py:365-373,771-826` and `bot/web/services.py:758-870` read local staged `pending`/`stored` attachments during the fixed `15`-minute window (`D-15`), checking `now > T0 + 15m` for expiry. | `bot/web/app.py:365-373,771-826`, `bot/web/services.py:758-870` |
| **External Hosting & Stage B** | `HOST-01`, `HOST-02`, and Enzonic canary execution remain `BLOCKED` (`docs/DEPLOY_ENZONIC.md:10-24`). `.github/workflows/enzonic-sftp-readonly-check.yml` is committed locally (`126` lines) but unexecuted/unverified live. `tools/katabump-sqlite-canary/canary.py` (`H1`) has not run on the target host. `P0` / `Stage B` remote upload remains `BLOCKED / DEFERRED BY EXPLICIT PRODUCT DECISION` (`.agent/PROGRESS.md:20-36`). | `docs/DEPLOY_ENZONIC.md:1-70`, `.github/workflows/enzonic-sftp-readonly-check.yml`, `tools/katabump-sqlite-canary/canary.py`, `.agent/PROGRESS.md:20-36` |

---

## 3. Decision dependency overview

The five unresolved owner decisions govern distinct release gates (`Gate 0` through `Gate D`) across `WP-01`–`WP-10`:

- **`Gate 0` (Governance & Decision Gate)** blocks code implementation on **`OD-01`**, **`OD-02`**, **`OD-03`**, **`OD-04`** (plus the non-owner `WP-06` `callback_refs` design spec and `WP-01` pre-change DB/staging inventory).
- **Phase 0 (`WP-01` + `Gate A`)** is directly governed by **`OD-01`** (whether/when terminal attachment batches stop blocking subsequent normal text prompts) and **`OD-03`** (whether `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` default flips from `True` to `False`, which also determines default `MT-2` availability). **`OD-01`** and **`OD-03`** also shape the risk profile of deferring **`OD-05`** (`Stage B`).
- **Phase 1 (`WP-02` -> `WP-03` -> `WP-04` -> `Gate B`)** executes sequentially on `bot/handlers.py`: `WP-02`, `WP-03`, and **`WP-04` Part 1** (transient classifier fixes) require **no** new policy choice from `OD-02`, whereas **`WP-04` Part 2** (ADR §28.4 manual poison quarantine schema & commands) is strictly gated on **`OD-02`**.
- **Phase 2 (`WP-05` & `WP-06`)** proceed independently of `OD-01`–`OD-05` for `STATE_LABELS`/worker bugs (`WP-06` schema work remains gated on the `callback_refs` TTL/cleanup/authz design spec).
- **Phase 2b (`WP-07`)** depends on `WP-01` for attachment I/O/cleanup stability and on **`OD-04`** if concurrent intra-batch polling is proposed (preserving sequential polling requires no concurrency redesign). **`WP-08`** documents final outcomes and env/schema parity after `WP-01`, `WP-04`, `WP-06`, and `WP-07`.
- **Phase 4 (`WP-10` + `Gate D`)** is wholly gated on **`OD-05`**, external credentials/hardware, and prior passage of `Gates A–C` in CI (`WP-09`).

---

## 4. OD-01 decision analysis

### A. Decision statement

What routing, classification, and recovery policy must govern subsequent owner text prompts and unresolved or terminal attachment batches under `classify_attachment_routing` (`bot/db.py:1493-1570`), `_handle_accompanying_text` (`bot/handlers.py:2052-2204`), and external-outcome tracking (`attachment_batches`, `outbox`, `creation_jobs`, and `processed_updates`), given that the historical `D-34 Option A` rule causes a permanent cross-conversation text-prompt deadlock (`DEF-001`) once any document batch reaches a terminal state?

### B. Current behavior

1. **Implemented behavior in code:**
   - **Global terminal batch query & classification:** `Database.has_terminal_attachment_batch(telegram_id)` (`bot/db.py:1379-1384`) checks `WHERE telegram_id=? AND status IN ('delivered','expired','rejected','failed')` across **all** conversations of the owner (documented as behavior `N-2`). `Database.classify_attachment_routing` (`bot/db.py:1493-1570`) evaluates in order:
     1. Unknown or `NULL` batch status -> raises `AttachmentBatchIntegrityError` (`L1536-1539`, fail-closed).
     2. Any row in `('intent_recorded', 'dispatching', 'uncertain')` -> returns `AttachmentRoutingState.UNRESOLVED` (`L1540-1545`).
     3. More than one live `pending` row (`now < T0 + 15m`) -> returns `MULTI_LIVE` (`L1546-1550`).
     4. Exactly one live `pending` row -> returns `LIVE` (`L1551-1554`).
     5. Any clock-expired `pending` row (`now >= T0 + 15m`) -> returns `EXPIRED_PENDING` (`L1555-1556`).
     6. `has_terminal_attachment_batch(telegram_id)` true -> checks `attachment_message_identity`; returns `TERMINAL_ASSOCIATED` if a stored `(telegram_id, chat_id, message_id)` match exists, otherwise returns `TERMINAL_UNPROVEN` (`L1557-1569`).
     7. Only if none of the above hold -> returns `NONE` (`L1570`).
   - **Handler routing trap (`DEF-001`):** `handle_text` (`bot/handlers.py:2245`) calls `_handle_accompanying_text` (`bot/handlers.py:2052-2204`) before normal prompt dispatch (`_send_prompt`). Whenever `classify_attachment_routing` returns `UNRESOLVED`, `MULTI_LIVE`, `EXPIRED_PENDING`, `TERMINAL_ASSOCIATED`, or `TERMINAL_UNPROVEN` (`L2103-2135`), `_handle_accompanying_text` calls `_reject_accompanying_text` (committing `REJECTED_INELIGIBLE` first, then best-effort reply) and returns `True`, preventing `handle_text` from ever reaching `_send_prompt` or `outbox`.
   - **No row deletion / irreversible reaping:** `AttachmentReaper` (`bot/attachments.py:1062-1252`) transitions clock-expired `pending` batches to `expired`, transitions item statuses to `reaped`, and unlinks files on disk, while skipping `intent_recorded`/`dispatching`/`uncertain` (`step 0c`), corrupt `invalid_t0` (`L1188-1191`), and out-of-enum/ambiguous rows. There is no `DELETE FROM attachment_batches` in runtime code, and `attachment_message_identity` enforces `ON DELETE RESTRICT` (`D-35`, `bot/db.py:561`).
   - **Uncertain external outcomes elsewhere in the system:**
     - Prompt delivery (`bot/outbox.py:480-543`): Once CAS enters `OUTBOX_SENDING`, timeouts/errors/restarts transition to `OUTBOX_UNKNOWN` (`at-most-once`, zero automatic retry).
     - Chat creation (`bot/outbox.py:733-806`): Creation polls record `CREATION_UNKNOWN` on ambiguous/post-POST failure (with `DEF-008` gap leaving `wait_for_start` exceptions stranded until fixed in `WP-05`).
     - Update polling (`bot/handlers.py:589-610`, `bot/polling.py:180-200`): `mark_ambiguous_external`, `CancelledError`, and `outcome=None` fallback write `PARTIAL_OR_UNKNOWN`, keeping polling fail-closed.
2. **Documented intended behavior:**
   - `docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md:1689-1774,1983` records an earlier owner policy entry **`D-34 Option A`** (2026-11-14) plus **`D-34/J`** review-gate substitution (2026-11-15), which explicitly approved keeping `TERMINAL_UNPROVEN` fail-closed and explicitly disclosed the `N-2` cross-conversation availability trade-off (`L1731-1736`) while recording `D-34` as "policy only".
   - `D-35` (`OHB2-P0-OWNER-DECISIONS-REGISTER.md:1777-1833`) prohibits pruning or cascading deletion of `attachment_message_identity` across batch cleanup.
   - `D-15 Option A` (`L2094-2097`) defines a fixed 15-minute staging window (`T0 + 15m`) with no extension.
   - `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md` §E `WP-01` (`L474-508`) and §H (`L775`) formally mark **`OD-01` (`D-34` `TERMINAL_UNPROVEN`)** as unresolved because `D-34`'s global blocking behavior combines with non-expiring `attachment_batches` terminal rows to permanently brick normal text prompts for an owner (`DEF-001`)—even if `/cancel` transitions `pending`/`intent_recorded` to `rejected`.
3. **Missing or incomplete behavior:**
   - Neither `/cancel` (`cancel_route` / `cancel_route_button`) nor any command safely discards a live `pending` or `intent_recorded` batch (`WP-01` deliverable).
   - There is no implemented recovery or reconciliation command for pre-existing `intent_recorded`, `dispatching`, `uncertain`, `invalid_t0`, or out-of-enum batches, nor any un-reap/file-restore capability once `reaped` + unlinked.
4. **Previously proposed but unimplemented changes:**
   - `WP-01` (`docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md:481-508`) specifies DB-first `/cancel` abandonment (`pending`/`intent_recorded` -> `rejected` -> item `reaped` -> `unlink`), conservative state-by-state preservation (`dispatching`/`uncertain`/`invalid_t0`/out-of-enum preserved for manual reconciliation), and pre-change read-only inventory, **while freezing `classify_attachment_routing` (`bot/db.py:1557-1569`), `D-34`, and `D-35` until `OD-01` is explicitly decided**.

### C. Why a decision is required

Without an owner decision on `OD-01`, `WP-01` cannot safely resolve `DEF-001`:
- Under current `D-34` (`TERMINAL_UNPROVEN`), adding `/cancel` in `WP-01` transitions an unwanted `pending` or `intent_recorded` batch to terminal `rejected`—yet `has_terminal_attachment_batch` **still returns `True` globally**, so **every future unmapped text message in every conversation remains rejected as `TERMINAL_UNPROVEN` forever**!
- Conversely, relaxing `classify_attachment_routing` without explicit owner authorization would violate `AGENTS.md` §14 ("approved architectural/policy decisions do not change without explicit permission") and override the documented `D-34 Option A` / `D-35` contract (`OHB2-P0-OWNER-DECISIONS-REGISTER.md:1689-1833`).
- In addition, any resolution must preserve fail-closed treatment for genuinely ambiguous/uncertain external or DB states (`intent_recorded`, `dispatching`, `uncertain`, `MULTI_LIVE`, `EXPIRED_PENDING`, `invalid_t0`, out-of-enum statuses, `OUTBOX_UNKNOWN`, `CREATION_UNKNOWN`, `PARTIAL_OR_UNKNOWN`) and respect the `now == T0 + 15m` boundary split (`db.py` `>=` vs `web/services.py` `>`).

### D. Available options

#### Option A — Preserve Existing `D-34` `TERMINAL_UNPROVEN` Global Fail-Closed Behavior
- **Exact policy & behavior:** Keep `classify_attachment_routing` (`bot/db.py:1557-1569`), `has_terminal_attachment_batch` (`N-2`), `TERMINAL_UNPROVEN`, `TERMINAL_ASSOCIATED`, and `D-35` runtime semantics completely unchanged. Add `/cancel` (`pending`/`intent_recorded` -> `rejected` + `reaped` + `unlink`) in `WP-01`, and handle any unblocking after terminal/ambiguous states solely through an explicit, separate owner-authorized reconciliation or archival procedure.
- **Benefits:** Zero weakening of `D-34 Option A` guarantees; zero risk of an accompanying prompt intended for an expired/failed batch leaking into normal `_send_prompt` / `outbox`; preserves all existing `D-34` tests and `D-35` `ON DELETE RESTRICT` semantics unchanged.
- **Risks / failure modes:** **Does not resolve `DEF-001` automatic usability:** after a single document upload expires (`AttachmentReaper` -> `expired`) or is canceled (`rejected`), the owner remains blocked from sending normal text prompts in **all** conversations until manual operator DB intervention or an approved archival step is executed.
- **Data-loss / data-integrity implications:** Zero silent misrouting; zero batch or identity deletion; any future archival workflow would require explicit design to preserve `attachment_message_identity` (`D-35`).
- **User-visible consequences:** Owner continues seeing `ATTACHMENT_TEXT_AMBIGUOUS_TEXT` (`REJECTED_INELIGIBLE`) on normal text messages across all chats whenever any historical terminal batch exists for their `telegram_id`.
- **Affected work packages:** `WP-01` (blocks routing change; only `/cancel` + `NEW-DEF-06` + reaper safety apply; requires defining separate manual unblocking procedure), `WP-08` (documentation of fail-closed constraint), `WP-09`.
- **Reversibility:** High for policy (`D-34` untouched); **irreversible** at row/file level once `/cancel` or reaper transitions items to `reaped` and unlinks files.
- **Prerequisites / additional evidence:** Pre-change read-only inventory of existing SQLite `attachment_batches` / `attachment_items` and `<db_dir>/attachment_staging/` before any cleanup; explicit definition of what owner-authorized reconciliation/reset action is permitted if Option A is kept.

#### Option B — Permit Normal Text Routing Only Under a Precisely Defined, Verified Terminal Condition (Amend `D-34`)
- **Exact policy & behavior:** Under explicit owner authorization amending `D-34` (and updating `D-34` tests), allow unmapped text in `classify_attachment_routing` to return `NONE` (proceeding to `handle_text` subject to independent `route`/ownership/tombstone checks) **only when all of the following verified conditions hold**:
  1. Integrity check passes (`0` out-of-enum/`NULL` statuses).
  2. Zero `UNRESOLVED` batches (`intent_recorded`, `dispatching`, `uncertain`) exist.
  3. Zero `LIVE` or `EXPIRED_PENDING` batches exist (`AttachmentReaper` or `/cancel` has already finalized `pending` rows cleanly).
  4. Zero `attachment_message_identity` correlation matches the incoming `(telegram_id, chat_id, message_id)` (`TERMINAL_ASSOCIATED` remains strictly fail-closed `REJECTED_INELIGIBLE`).
  5. Terminal batches (`expired`, `rejected`, `delivered`, `failed`) have valid schema state and verified `t0`.
  *(Variant note: owner approval can specify whether this applies to all verified terminal statuses `expired`/`rejected`/`delivered`/`failed` or strictly `expired`/`rejected`.)*
- **Benefits:** Eliminates the `DEF-001` owner-wide self-DoS automatically once `/cancel` or reaper finalizes a batch, while retaining fail-closed protection on `LIVE`/`MULTI_LIVE`/`EXPIRED_PENDING`/`UNRESOLVED` (`intent_recorded`, `dispatching`, `uncertain`), `invalid_t0`, corrupt statuses, and proven `TERMINAL_ASSOCIATED` replays.
- **Risks / failure modes:** Reverses the documented `D-34 Option A` trade-off (`N-2` availability sacrifice): if Telegram drops or delays network delivery of a user's accompanying caption text until *after* a `pending` batch expires (e.g., past 15 minutes) and is swept to `expired`, and the user has no saved `attachment_message_identity` row for that text, the text could pass into normal `_send_prompt` / `outbox` as an unattached prompt rather than blocking.
- **Data-loss / data-integrity implications:** `attachment_batches` rows and `attachment_message_identity` (`D-35`, `ON DELETE RESTRICT`) remain preserved untouched; `/cancel` DB-first `rejected`/`reaped`/unlink transitions remain irreversible for staging bytes; Stage B (`dispatching`/`uncertain`) and `outbox`/`creation_jobs` `UNKNOWN` semantics remain strictly fail-closed.
- **User-visible consequences:** Once `/cancel` is used or an unused batch cleanly expires/is swept, the owner can immediately resume normal text prompting across all conversations (`route` checked independently). If an `intent_recorded` batch exists or `pending` just expired before reaper swept it (`EXPIRED_PENDING`), the prompt is still cleanly blocked until `/cancel` or sweep.
- **Affected work packages:** `WP-01` (routing logic + `/cancel` + `D-34` contract/test updates), `WP-08` (runbook parity), `WP-09` (updated D-34 + E2E regression tests).
- **Reversibility:** Policy/code change is reversible in code (`WP-01`), **though any text prompt already dispatched via `_send_prompt`/`outbox` while permitted, and any `/cancel`/reaped staging bytes, cannot be undone**.
- **Prerequisites / additional evidence:** Pre-change read-only DB/disk inventory; explicit owner enumeration of which terminal states (`expired`/`rejected` vs `delivered`/`failed`) qualify and confirmation of amending `OHB2-P0-OWNER-DECISIONS-REGISTER.md` `D-34` & D-34 test suite.

#### Option C — Hybrid: Strict Manual Reconciliation for Uncertain/Ambiguous States + Explicit Scoped Terminal Clearance
- **Exact policy & behavior:** Keep **all** uncertain, corrupt, or ambiguous external/lifecycle states strictly fail-closed requiring explicit **manual reconciliation** (`intent_recorded`, `dispatching`, `uncertain`, `MULTI_LIVE`, `EXPIRED_PENDING`, `invalid_t0`, out-of-enum/`NULL` status, ambiguous ownership, `OUTBOX_UNKNOWN`, `CREATION_UNKNOWN`, `PARTIAL_OR_UNKNOWN`), AND require an explicit owner/operator confirmation step (such as `/cancel` acknowledgment or a dedicated terminal-clearance command referencing the specific expired/rejected batch) before resetting `classify_attachment_routing` back to `NONE` (never auto-unblocking silently when a batch expires via background `AttachmentReaper`). Keep `TERMINAL_ASSOCIATED` and `D-35` strictly fail-closed.
- **Benefits:** Prevents silent misrouting if text arrives right after background reaper expiration (solves Option B's late-text hazard) **while** still giving the owner a built-in bot command path to recover from `DEF-001` without raw SQLite CLI edits (solves Option A's permanent brick).
- **Risks / failure modes:** Adds operational UX friction—after a 15-minute batch expires unused, the owner must acknowledge/clear it explicitly before sending normal text prompts again; also requires designing and testing an explicit acknowledgment record that never violates `D-35` (`attachment_message_identity` preserved) or weakens `D-34` semantics unexpectedly.
- **Data-loss / data-integrity implications:** Zero silent unblocking; preserves `attachment_message_identity` (`ON DELETE RESTRICT`); explicit clearance updates or marks only verified expired/rejected owner-scoped rows; all uncertain/ambiguous rows remain preserved for inspection.
- **User-visible consequences:** Normal text prompting resumes only after explicit owner confirmation (`/cancel` or batch-ack command), never silently after passive timeout.
- **Affected work packages:** `WP-01` (expanded handler/DB command contract beyond baseline `/cancel`), `WP-07`, `WP-08`, `WP-09`.
- **Reversibility:** Policy/command reversible in code; byte unlinking and clearance state commits are irreversible in DB/filesystem.
- **Prerequisites / additional evidence:** Pre-change inventory; explicit design review of any new clearance column/state (`D-35` compliance) before implementation.

### E. Consequences of deferring the decision

- **Remains blocked:** Any modification to `classify_attachment_routing` (`bot/db.py:1557-1569`), `D-34`, or `D-35`; completion of `WP-01` `DEF-001` cross-conversation unblocking and **`Gate A`**; full closure of `WP-07` (`DEF-011` / state parity), `WP-08` (final attachment docs), and `WP-10`/`Stage B`.
- **Can proceed independently:** `WP-01` planning/inventory of existing DB rows; `NEW-DEF-06` copy planning (`UNSUPPORTED_ATTACHMENT_TEXT` fix); `WP-02`, `WP-03`, `WP-04` Part 1, `WP-05`, `WP-06` (`STATE_LABELS` + `callback_refs` design spec), and `WP-09` CI setup.
- **Operational risk if deferred:** `DEF-001` remains live whenever `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=True`: a single Telegram document upload will still permanently lock normal text prompting across all chats for the owner once that batch reaches a terminal state (or `intent_recorded`/`expired`). Preserves existing `D-34` fail-closed isolation and avoids introducing new misrouting bugs, at the cost of continuing total text-prompt unavailability after attachment usage.

### F. Explicit owner choice

`OWNER DECISION REQUIRED — NO OPTION SELECTED`

- [ ] **Option A** — Preserve existing `D-34` `TERMINAL_UNPROVEN` global fail-closed behavior (manual/authorized external reconciliation required after terminal batches; `/cancel` moves to `rejected` without unblocking future text).
- [ ] **Option B** — Amend `D-34` to permit verified terminal pass-through (`NONE`) when zero `UNRESOLVED`/`LIVE`/`EXPIRED_PENDING`/corrupt/`invalid_t0` batches and zero `attachment_message_identity` matches exist, keeping `TERMINAL_ASSOCIATED` and all uncertain/ambiguous states fail-closed.
- [ ] **Option C** — Hybrid: keep passive terminal/uncertain states fail-closed and require explicit owner acknowledgment/clearance action (plus manual reconciliation for ambiguous/uncertain states) to resume normal text prompting.

---

## 5. OD-02 decision analysis

### A. Decision statement

What recovery and classification policy should govern genuine permanent handler failures and deterministic user-limit rejections (`FAILED_PERMANENT`, such as `TextDocumentTooLargeError` in `bot/handlers.py:1150-1154`), including whether and under what contract to implement ADR §28.4 manual poison-update inspection and skip/quarantine commands (`/updates_status` and `/updates_skip <update_id> confirm`) along with their separate SQLite schema metadata?

### B. Current behavior

1. **Implemented behavior in code:**
   - `_classify_failure(exc)` (`bot/handlers.py:477-495`) maps **only**:
     - `asyncio.CancelledError` -> `PARTIAL_OR_UNKNOWN` (`L488-489`)
     - transient `sqlite3.Error` (`BUSY`/`LOCKED`) -> `FAILED_TRANSIENT` (`L490,493`)
     - non-permanent `ApiError` (not `4xx` except `429`) -> `FAILED_TRANSIENT` (`L491-493`)
     - **Everything else** -> `FAILED_PERMANENT` (`L495`).
   - Consequently, `telegram.error.RetryAfter`, `telegram.error.TimedOut`, `telegram.error.NetworkError`, `asyncio.TimeoutError`, `httpx.TransportError`, and transient socket `OSError` all misclassify as `FAILED_PERMANENT` (`DEF-002` Part 1).
   - `send_reply_txt` (`bot/handlers.py:1150-1154`) catches `TextDocumentTooLargeError`, sends `"الرد كبير أوي للتنزيل كملف نصي."`, and explicitly calls `mark_failed_permanent(update, context, "text_document_too_large")`.
   - In `bot/update_outcomes.py:40-90`, `_INELIGIBLE` contains `{FAILED_TRANSIENT, FAILED_PERMANENT, PARTIAL_OR_UNKNOWN}`. `TelegramPoller.process_updates` (`bot/polling.py:155-173`) + `Database.commit_batch_outcomes` (`bot/db.py:2945-3010`) advance the offset **only** up to the longest contiguous eligible prefix. Any single `FAILED_PERMANENT` update (`update_failures` row) blocks `get_acknowledgment_boundary()` and forces Telegram to re-deliver that update and every subsequent update indefinitely until manual SQLite editing or Telegram's 24-hour update retention expiry.
2. **Documented intended behavior:**
   - `docs/proposals/OHB2-TELEGRAM-ACK-ARCHITECTURE-ADR.md` (`§18.6` `L624-646`, `§30.5` item 4 `L1055`, `§35` item 1 `L1115`, `§37` item 6 `L1171-1183`) explicitly specifies fail-closed head-of-line blocking for poison updates, forbids auto-skipping (`max+1` banned), and records `/updates_status`, manual operator skip, and permanent audit schema fields (`update_failures.acknowledged_by_operator` + `acknowledged_at`, or `acknowledgment_overrides`, plus `ack_offset_submitted`/`ack_offset_confirmed`) as **deferred separate schema/policy decisions requiring owner approval**.
3. **Missing or incomplete behavior:**
   - There are no `/updates_status` or `/updates_skip` commands registered in `bot/app.py:BOT_COMMANDS` or `bot/handlers.py`.
   - There is no quarantine/override status or schema column/table in `bot/db.py` (`17` tables).
   - There is no handling for transient Telegram/network exceptions in `_classify_failure`.
4. **Previously proposed but unimplemented changes:**
   - `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md` (`WP-04`, `L550-566`) cleanly separates **Part 1** (fix `_classify_failure` for `RetryAfter`, `TimedOut`, `NetworkError`, `asyncio.TimeoutError`, `httpx.TransportError`, and context-verified transient socket `OSError` — never blanket all `OSError`, never catching `CancelledError`, never auto-skipping) from **Part 2** (ADR §28.4 manual quarantine commands + schema metadata, gated on `OD-02`).

### C. Why a decision is required

Even after fixing transient exception classification (`WP-04` Part 1) and callback hardening (`WP-02` / `WP-03`), genuine permanent failures remain possible—both expected deterministic user-limit rejections (`TextDocumentTooLargeError` >50 MiB Telegram file cap) and unexpected runtime bugs (`KeyError`/`TypeError`/corrupt payload). Today, any single `FAILED_PERMANENT` update **permanently freezes bot polling for up to 24 hours** (`DEF-002` head-of-line deadlock) with no in-bot inspection or safe quarantine mechanism—forcing raw production SQLite tampering or loss of Telegram updates. Choosing between strict manual skip, deterministic rejection splitting, or schema freeze requires explicit owner authorization under `AGENTS.md` §14 and ADR §28.4.

### D. Available options

#### Option A — Strict ADR §28.4 Manual Poison Quarantine (`/updates_status` + `/updates_skip <update_id> confirm`)
- **Exact policy & behavior:** Keep **all** `FAILED_PERMANENT` classifications (including `TextDocumentTooLargeError` and unexpected crashes) fail-closed in `_INELIGIBLE`. Add an ADR §28.4 separate schema extension (audit override column(s) on `update_failures` or `acknowledgment_overrides` table + `POISON_SKIPPED` or explicit audit flag) and two owner-only `_guard`-protected commands: `/updates_status` (displays boundary, stuck count, head-of-line `update_id`, exception `type(exc).__name__`, and timestamp without sensitive message payload) and `/updates_skip <update_id> confirm` (requires exact head-of-line `update_id` in `update_failures` plus explicit `confirm` token; records durable audit metadata and unlocks `acknowledgment_boundary` progression without auto-skip).
- **Benefits:** Preserves strict uniform fail-closed scrutiny over *every* `FAILED_PERMANENT` event; gives the owner an auditable, deterministic way to inspect and unblock head-of-line deadlocks from Telegram without touching raw SQLite files; keeps `update_failures` forensic records intact across restarts.
- **Risks / failure modes:** Any legitimate `>50 MiB` `.txt` reply download attempt (`TextDocumentTooLargeError`) will still pause bot polling until the owner notices or triggers `/updates_status` + `/updates_skip`; **if the head-of-line deadlock was caused by a Telegram outage or if the bot itself cannot receive the owner's `/updates_skip` message because polling is stalled on `update_id N` (`offset = N`)**: note a critical polling mechanics constraint—`TelegramPoller` fetches updates sequentially in batches starting at `boundary+1`, so as long as Telegram keeps delivering `[N, N+1, ...]` where `N+1` is the owner's `/updates_skip N confirm` command, **both** appear in the fetched batch, `/updates_skip` runs in `process_updates` and records the override so `N` becomes skippable within that batch! However, if more than `100` queued updates (`getUpdates` limit=100) precede the owner's command, or if `process_updates` fails before committing, in-bot `/updates_skip` could take multiple poll cycles or require direct CLI/maintenance rescue.
- **Data-loss / data-integrity implications:** Increases SQLite schema from `17` to `18` tables (or alters `update_failures` with additive columns, plus potentially `18`/`19` with `WP-06` `callback_refs`), requiring `WP-08` parity sync; intentionally drops reprocessing of the skipped `update_id` **only** after explicit owner confirmation and preserves the forensic failure row.
- **User-visible consequences:** Owner gains `/updates_status` and `/updates_skip` commands in `BOT_COMMANDS`; genuine `TextDocumentTooLargeError` pauses polling until skipped.
- **Affected work packages:** `WP-04` Part 2, `WP-08` (commands & schema table/column docs), `WP-09` (`test_poison_update_quarantine.py`).
- **Reversibility:** Additive schema/command feature; reversible in code/docs if not relied on operationally (existing `update_failures` audit rows preserved).
- **Prerequisites / additional evidence:** Explicit ADR §28.4 schema decision (columns on `update_failures` vs new `acknowledgment_overrides` table), plus batch-fetch verification test showing `/updates_skip <N> confirm` arriving in `updates[1:]` unblocks head-of-line `updates[0] == N` safely in one cycle (and >100-update backlog fallback behavior documented).

#### Option B — Deterministic User-Limit Rejection Split + ADR §28.4 Manual Quarantine
- **Exact policy & behavior:** Classify strictly deterministic, pre-validated user-limit rejections where **no external mutation failed ambiguously and user notification succeeded**—specifically `TextDocumentTooLargeError` after `bot.send_message` notification succeeds (`bot/handlers.py:1150-1154`)—as an ack-eligible terminal rejection (`REJECTED_INELIGIBLE` or `EXPLICITLY_IGNORED` with reason `"text_document_too_large"`, keeping `send_message` failures as `FAILED_TRANSIENT` via `WP-03`), **AND** implement Option A's ADR §28.4 manual quarantine (`/updates_status` + `/updates_skip <update_id> confirm` + durable audit metadata) for all genuinely unexpected `FAILED_PERMANENT` errors.
- **Benefits:** Prevents routine deterministic `>50 MiB` file rejections from ever freezing polling at all, while retaining Option A's safe manual recovery for unexpected permanent bugs; minimizes operator intervention on non-retryable user limits without adding any auto-skip for real failures.
- **Risks / failure modes:** Introduces a deliberate distinction between "known deterministic non-retryable user limit already communicated to owner" (eligible) and "unexpected permanent failure" (blocked). Future engineers must never extend the eligible rejection path to exception types whose safety/post-commit state is unverified (`WP-03` guard required if `send_message` itself fails).
- **Data-loss / data-integrity implications:** Same schema addition as Option A (`update_failures` override columns or `acknowledgment_overrides` table); `>50 MiB` notice still cannot be retried anyway because Telegram rejects >50 MiB bot `sendDocument` payloads deterministically.
- **User-visible consequences:** Clicking `txt:` on a >50 MiB reply delivers the `"الرد كبير أوي للتنزيل كملف نصي."` message and keeps polling flowing smoothly; `/updates_status` and `/updates_skip` handle any unexpected poison crashes.
- **Affected work packages:** `WP-03` (post-notification guard on `send_reply_txt:1152`), `WP-04` Part 2, `WP-08`, `WP-09`.
- **Reversibility:** Classification of `TextDocumentTooLargeError` is trivially reversible in one call site; schema additions follow Option A.
- **Prerequisites / additional evidence:** Same ADR §28.4 schema choice + >100-update backlog verification as Option A, plus confirmation that `send_message` failure inside `TextDocumentTooLargeError` raises into `FAILED_TRANSIENT` (not masked as eligible).

#### Option C — Defer Schema Quarantine (Transient Classifier Fix + Read-Only `/updates_status` or Out-of-Band SQLite Runbook Only)
- **Exact policy & behavior:** Authorize **only** `WP-04` Part 1 (transient exception classification fixes for `RetryAfter`, `TimedOut`, `NetworkError`, `asyncio.TimeoutError`, `httpx.TransportError`, socket `OSError`), optionally paired with read-only `/updates_status` diagnostics (without `/updates_skip` or any SQLite schema changes), leaving genuine `FAILED_PERMANENT` poison resolution strictly as an out-of-band operator SQLite runbook procedure (no ADR §28.4 quarantine implemented now).
- **Benefits:** Keeps ADR §28.4 schema (`17` SQLite tables) and command surface unchanged; zero risk of an in-bot skip bug or `>100`-update deadlock interaction inside `TelegramPoller`.
- **Risks / failure modes:** Any single genuine `FAILED_PERMANENT` exception (including `TextDocumentTooLargeError`) continues wedging bot polling up to 24 hours until the operator accesses the host filesystem/SQLite directly (impossible without shell/panel access, which is currently restricted/blocked on Enzonic per `docs/DEPLOY_ENZONIC.md:36`).
- **Data-loss / data-integrity implications:** Out-of-band manual SQLite edits carry human error risk against WAL sidecars and `acknowledgment_boundary` monotonicity if performed while the bot runs.
- **User-visible consequences:** Transient network outages stop bricking polling (`WP-04` Part 1), but `TextDocumentTooLargeError` or unexpected permanent crashes require manual DB intervention or waiting 24h for Telegram expiry.
- **Affected work packages:** `WP-04` (limits scope to Part 1 +/- read-only `/updates_status`), `WP-08` (documents manual runbook procedure), `WP-09`.
- **Reversibility:** Fully additive later (ADR §28.4 quarantine can always be approved in a later phase).
- **Prerequisites / additional evidence:** Operator shell/SQLite recovery runbook documenting safe bot shutdown before WAL SQLite intervention.

### E. Consequences of deferring the decision

- **Remains blocked:** `WP-04` Part 2 (ADR §28.4 `/updates_status`, `/updates_skip`, and any `update_failures` / `acknowledgment_overrides` schema changes) and full closure of **`Gate B`** for genuine `FAILED_PERMANENT` deadlock recovery; `WP-08` final command/schema parity.
- **Can proceed independently:** **`WP-04` Part 1** (`_classify_failure` transient fixes for `RetryAfter`, `TimedOut`, `NetworkError`, `asyncio.TimeoutError`, `httpx.TransportError`, context-inspected socket `OSError`), `WP-02` (stopping `q.answer`/`q.edit_message_text` from throwing into `FAILED_PERMANENT`), `WP-03`, `WP-05`, `WP-06`, `WP-07`.
- **Operational risk if deferred:** Genuine `FAILED_PERMANENT` triggers (including a single `TextDocumentTooLargeError`) continue halting polling (`DEF-002`) until Telegram drops updates after 24h or manual SQLite edits occur. Preserves strict fail-closed ADR v6 boundaries without introducing unproven skip logic.

### F. Explicit owner choice

`OWNER DECISION REQUIRED — NO OPTION SELECTED`

- [ ] **Option A** — Implement strict ADR §28.4 manual poison quarantine (`/updates_status` + `/updates_skip <update_id> confirm` + durable audit schema), keeping `TextDocumentTooLargeError` fail-closed (`FAILED_PERMANENT`).
- [ ] **Option B** — Classify deterministic pre-checked `TextDocumentTooLargeError` (after successful reply notification) as ack-eligible (`REJECTED_INELIGIBLE`/`EXPLICITLY_IGNORED`) AND implement ADR §28.4 manual poison quarantine for all other `FAILED_PERMANENT` errors.
- [ ] **Option C** — Implement `WP-04` Part 1 transient classification fixes only (plus optional read-only `/updates_status`), deferring ADR §28.4 `/updates_skip` and schema quarantine to a future release.

---

## 6. OD-03 decision analysis

### A. Decision statement

Should the default value of `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` (`bot/config.py:43,315-317`, `.env.example:2`) be changed from `True` (`1`) to `False` (`0`), explicitly accepting that disabling default Telegram document staging leaves the excluded Mini App `OHB2-MT-2` staged-attachment download view (`bot/web/services.py:758-870`) empty unless opted into (`=1`), or should the default remain `True` contingent on `WP-01` (`OD-01` + `/cancel` + policy-aware copy) mitigating `DEF-001`?

### B. Current behavior

1. **Implemented behavior in code:**
   - `bot/config.py:43` declares `attachment_document_intake_enabled: bool = True`. `Config.from_env` (`L315-317`) parses `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` via `_parse_bool(..., default=True)` (`L99-117`, failing closed with `ConfigError` on invalid non-empty strings). `.env.example:2` lists `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=` blank (activating default `True`).
   - When `True`, `handle_attachment` (`bot/handlers.py:1879-1990`) accepts `Document` messages under an open `route`, stages them locally into `attachment_batches` (`pending`) / `attachment_items` (`stored`) + `<db_dir>/attachment_staging/`, and replies with `ATTACHMENT_ACCEPTED_TEXT`.
   - When `False`, `handle_attachment` (`L1884-1892`) replies with `ATTACHMENT_INTAKE_DISABLED_TEXT` and marks `EXPLICITLY_IGNORED` without creating batches or files.
   - **Critical existing-state asymmetry:** Setting `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=0` does **not** alter `handle_text` (`bot/handlers.py:2245`) or `_handle_accompanying_text` (`L2052-2204`), so **any pre-existing `pending`, `intent_recorded`, `expired`, or terminal batch in SQLite still blocks normal text prompts (`DEF-001`)**.
   - **Cross-boundary `MT-2` dependency (excluded Mini App):** `bot/web/services.py:758-870` (`list_staged_attachments`, `download_attachment`) and `bot/web/app.py:365-373,771-826` allow the authenticated owner in the Mini App to list and download **only** `pending` batches with `stored` items within the 15-minute `D-15` window (note boundary discrepancy: `bot/web/services.py:805,850` treats `now > T0 + 15m` as expired, whereas `bot/db.py:1334,1360,1429,1624` treats `now >= T0 + 15m` as expired).
   - **Copy bug (`NEW-DEF-06`):** `handle_unsupported_attachment` (`bot/handlers.py:2008`, `bot/messages.py`) always emits `UNSUPPORTED_ATTACHMENT_TEXT` advertising `"أو إرسال ملف كمستند (Document)"` even when `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=False`.
2. **Documented intended behavior:**
   - `AGENTS.md` / baseline rules explicitly exclude all Mini App code (`bot/web/*`, `bot/web/static/*`, `tests/frontend/*`, `tests/test_miniapp_*.py`, `docs/MINI_APP.md`, `Config.mini_app_*`) from modification, while requiring explicit owner decision **`OD-03`** whenever changing `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` alters excluded `MT-2` out-of-the-box behavior (`docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md:480,777`).
3. **Missing or incomplete behavior:**
   - No `BOT_CONFIG`/runtime warning clarifies to `MT-2` users why no staged attachments appear if intake is disabled.
   - Pre-existing batches require explicit state-by-state preservation/reconciliation (`WP-01` matrix, `L483-492`) rather than blanket cleanup.
4. **Previously proposed but unimplemented changes:**
   - `WP-01` (`L498`) proposes making `UNSUPPORTED_ATTACHMENT_TEXT` conditional on `cfg.attachment_document_intake_enabled` (`NEW-DEF-06`), updating `ATTACHMENT_ACCEPTED_TEXT` to state clearly that files are local-only (not sent to OpenHands) when enabled, and pairing `/cancel` + `OD-01` resolution before touching pre-existing data.

### C. Why a decision is required

`ATTACHMENT_DOCUMENT_INTAKE_ENABLED` sits directly on the boundary between Telegram attachment safety (`DEF-001`) and the excluded Mini App `MT-2` workflow (`DEF-014`):
- If left `True` by default without `OD-01` + `WP-01` shipped, any fresh deployment allows Telegram `Document` uploads out-of-the-box and immediately exposes owners to `DEF-001` permanent text-prompt blocking.
- If changed to `False` by default without explicit owner approval, a baseline remediation silently alters the default out-of-the-box behavior of the excluded `MT-2` Mini App feature (`DEF-014` cross-boundary violation) while creating a false sense of immunity if pre-existing SQLite batches remain in `bot_state.sqlite3`.

### D. Available options

#### Option A — Change Default of `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` to `False` (Explicit Opt-In via `=1`)
- **Exact policy & behavior:** Change `Config.attachment_document_intake_enabled` default from `True` to `False` in `bot/config.py:43,315-317` and document `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=0` (opt-in `=1`) in `.env.example` / `WP-08` docs. Zero edits to `bot/web/*`, `bot/web/static/*`, `docs/MINI_APP.md`, or `Config.mini_app_*`. Operators wanting `MT-2` local file transfer explicitly set `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=1` once `WP-01` (`/cancel` + `OD-01`) is verified.
- **Benefits:** Prevents accidental out-of-the-box document uploads in environments not using `MT-2` (especially while `Stage B` remote upload is `BLOCKED` and `HOST-02` Mini App is off); pairs cleanly with `NEW-DEF-06` copy fix so unsupported-media errors do not invite document uploads when disabled.
- **Risks / failure modes:** **Breaks zero-config `MT-2` expectation** for owners running Mini App `MT-2` without setting `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=1` (Mini App staged-attachments list remains empty even when Mini App is enabled); **does NOT cure pre-existing databases** that already contain `pending`, `intent_recorded`, `expired`, or terminal batches unless `WP-01` (`/cancel`, reaper, `OD-01`, pre-change DB inventory) also runs.
- **Data-loss / data-integrity implications:** Preserves existing DB rows untouched; config toggle (`=1` vs `=0`) does not touch staging files or historical batches; config rollback (`=1`) restores future intake only, never unlinked files or `reaped`/`rejected` rows.
- **User-visible consequences:** Sending a document in Telegram with default `.env` returns `ATTACHMENT_INTAKE_DISABLED_TEXT`; `MT-2` UI shows no staged files unless `=1` is set in env.
- **Affected work packages:** `WP-01`, `WP-08` (env docs/parity), `WP-09` (`test_repair_plan_02_life03_intake_kill_switch.py` updated to assert `False` default).
- **Reversibility:** Fully reversible in `.env` (`ATTACHMENT_DOCUMENT_INTAKE_ENABLED=1`) or `bot/config.py` at runtime/deploy; **does not reverse any pre-existing DB/file cleanup**.
- **Prerequisites / additional evidence:** Pre-change read-only inventory of any live SQLite `attachment_batches` (checking for active `15m` `MT-2` windows, `invalid_t0`, `dispatching`, `uncertain`) before any cleanup; explicit confirmation that `MINI_APP_ENABLED=True` operators understand `=1` opt-in is required.

#### Option B — Preserve Default `ATTACHMENT_DOCUMENT_INTAKE_ENABLED = True` (Contingent on `WP-01` + `OD-01`)
- **Exact policy & behavior:** Retain `attachment_document_intake_enabled: bool = True` in `bot/config.py:43,315-317`. Rely on `WP-01` (safe `/cancel`, `OD-01`-approved terminal routing, and honest local-only `ATTACHMENT_ACCEPTED_TEXT` explaining `MT-2` download or `/cancel`) to prevent `DEF-001` bricks while keeping `MT-2` document staging active out-of-the-box.
- **Benefits:** Preserves 100% existing default behavior for `MT-2` (`bot/web/services.py:758-870`) with zero surprise breakage for Mini App users; existing kill-switch tests asserting default `True` remain valid.
- **Risks / failure modes:** **Depends entirely on `OD-01` resolving `DEF-001` cleanly**—if `OD-01` chooses Option A (preserving global `TERMINAL_UNPROVEN` block), keeping `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=True` by default continues exposing users to `DEF-001` owner lockouts after any upload expires! Also leaves document staging active even when `MINI_APP_ENABLED=False` (where `MT-2` is turned off anyway), though `/cancel` or reaper handles unwanted batches if `OD-01` allows post-terminal recovery.
- **Data-loss / data-integrity implications:** Same conservative `WP-01` matrix applies; live `pending` batches remain protected until `T0 + 15m` or explicit `/cancel`; `reaped`/unlinked bytes remain irreversible.
- **User-visible consequences:** Sending a document under open `route` continues staging it locally with honest copy (`MT-2` download / `/cancel`); accompanied text or `/cancel` follows `OD-01` policy.
- **Affected work packages:** `WP-01` (strongly coupled with `OD-01` Option B/C), `WP-08`, `WP-09`.
- **Reversibility:** Trivially overridable per deployment via `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=0` in `.env` (for future intake only).
- **Prerequisites / additional evidence:** Must be evaluated together with `OD-01` (because Option B here without `OD-01` unblocking leaves `DEF-001` unresolved by default) and `NEW-DEF-06` honest copy (`ATTACHMENT_ACCEPTED_TEXT` & `UNSUPPORTED_ATTACHMENT_TEXT`).

### E. Consequences of deferring the decision

- **Remains blocked:** Any change to `bot/config.py:43,315-317` default (`False` vs `True`), finalization of `WP-01` flag defaults & **`Gate A`**, and `WP-08` `.env.example` / `OPERATIONS_RUNBOOK.md` env documentation parity.
- **Can proceed independently:** `WP-01` `/cancel` design, `NEW-DEF-06` conditional `UNSUPPORTED_ATTACHMENT_TEXT` branch planning, pre-change SQLite inventory tooling/queries, `WP-02`–`WP-06`, and `WP-09` CI setup.
- **Operational risk if deferred:** Default remains `True`: operators leaving `.env` unset accept documents into local staging even when Mini App is off (`MINI_APP_ENABLED=0`), risking `DEF-001` bricks unless `OD-01` + `WP-01` land. Preserves `MT-2` tests/config unchanged until decided.

### F. Explicit owner choice

`OWNER DECISION REQUIRED — NO OPTION SELECTED`

- [ ] **Option A** — Change default `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` to `False` (`0`, explicit opt-in `=1` for `MT-2` local transfer), keeping Mini App files unmodified.
- [ ] **Option B** — Keep default `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` as `True` (`1`), preserving zero-config `MT-2` staging and relying on `WP-01` + `OD-01` mitigation against `DEF-001`.

---

## 7. OD-04 decision analysis

### A. Decision statement

Should `TelegramPoller.process_updates` (`bot/polling.py:161-162`) remain strictly sequential (`await self.dispatch_and_wait(update)` per update, matching `docs/OPERATIONS_RUNBOOK.md:123-127`), with `bot/app.py:75-87` comments/configuration reconciled to match reality, or should the project authorize a future concurrent intra-batch dispatch refactor backed by formal proof of single-connection SQLite safety and per-user serialization (`WP-07` / `DEF-006`)?

### B. Current behavior

1. **Implemented behavior in code:**
   - `bot/app.py:82-87` builds the PTB `Application` with `.updater(None).concurrent_updates(True)`, accompanied by a legacy `U04` comment (`L75-78`) asserting that concurrent updates prevent slow commands (export/file list) from delaying prompt `"وصل ✅"` acknowledgments.
   - However, `TelegramPoller.process_updates` (`bot/polling.py:155-173`) executes:
     ```python
     for update in updates:
         await self.dispatch_and_wait(update)
     ```
     where `dispatch_and_wait` (`L175-178`) calls `await self.application.update_queue.put(update)` followed immediately by `await self.application.update_queue.join()`. Because `join()` blocks until PTB finishes processing that single update, **actual runtime execution is 100% sequential per update**, rendering `.concurrent_updates(True)` effectively inert across updates.
   - `Database.__init__` (`bot/db.py:550-565`) opens **one** shared `sqlite3.Connection` (`check_same_thread=False`, WAL, `busy_timeout=5000`, `PRAGMA foreign_keys=ON`). Multiple async tasks (`OutboxWorker`, `CreationWorker`, `CompletionWorker`, `Watcher`, `Notifier`, `AttachmentReaper`, plus Mini App ASGI routes if enabled) share that connection on the single asyncio loop **assuming no interleaving `await` points occur inside multi-step SQLite transactions or non-atomic read-then-write sequences**.
   - In-memory state (`list_cache`, `repo_nav`, `Watcher` hints) and `user_state` / `attachment_batches` multi-step handler sequences currently have **no** per-user `asyncio.Lock` or transaction isolation lock across concurrent handler executions.
2. **Documented intended behavior:**
   - `docs/OPERATIONS_RUNBOOK.md:123-127` explicitly documents sequential update processing in `TelegramPoller`.
   - `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md` §E `WP-07` (`L615,620,718,778`) forbids enabling concurrent update dispatch inside `TelegramPoller.process_updates` unless `Database._conn` thread/async safety, `BEGIN IMMEDIATE` write contention, and per-user ordering invariants are rigorously proven and approved via `OD-04`.
3. **Missing or incomplete behavior:**
   - No concurrency stress harness or per-user lock exists to guard `user_state`, `attachment_batches`, `list_cache`, `repo_nav`, or shared `Database._conn` if `process_updates` were changed to enqueue an entire fetched batch before `join()`.
   - Code comments (`bot/app.py:75-78`) directly contradict `bot/polling.py:161-162` and `OPERATIONS_RUNBOOK.md:123-127`.
4. **Previously proposed but unimplemented changes:**
   - `WP-07` (`L620`) proposes preserving sequential batch processing by default and aligning `bot/app.py:75-87` comments with `OPERATIONS_RUNBOOK.md:123-127`—leaving concurrent intra-batch dispatch gated on `OD-04` and formal technical proof.

### C. Why a decision is required

There is a live architectural/product tension between latency and correctness (`DEF-006`):
- Leaving `.concurrent_updates(True)` + `U04` comments in `bot/app.py:75-87` while `TelegramPoller` runs sequentially misleads maintainers into assuming concurrent execution works and is already safe.
- Conversely, changing `TelegramPoller.process_updates` to dispatch updates concurrently (`put` all then `join`) without per-user serialization and strict SQLite connection locking would introduce silent race conditions on `user_state` (`route` vs `newchat` vs `reposearch`), `attachment_batches` (multi-file uploads racing `MULTI_LIVE`/`record_attachment_intent`), shared `self._conn` cursor/transaction state across `await` boundaries, and outcome ordering in `collect_outcomes`.

### D. Available options

#### Option A — Preserve Sequential Intra-Batch Dispatch & Reconcile `bot/app.py` Comments/Config
- **Exact policy & behavior:** Keep `TelegramPoller.process_updates` (`bot/polling.py:161-162`) strictly sequential (`dispatch_and_wait` per update). Update `bot/app.py:75-87` comments (and align `.concurrent_updates` configuration cleanly without breaking PTB `Application` contracts) so code, comments, and `docs/OPERATIONS_RUNBOOK.md:123-127` state accurately that updates execute sequentially one-at-a-time per fetched batch.
- **Benefits:** **Zero** new intra-batch SQLite locking, transaction-interleaving, or same-user `user_state`/`attachment_batches` race risk; maintains deterministic outcome ordering (`collect_outcomes`) and single-owner simplicity (`I2`/`I3`); unblocks `WP-07` & `Gate C` immediately once `WP-01` lands.
- **Risks / failure modes:** Accepted latency trade-off—if one slow command in a batch (e.g., `/export`, large file preview, slow OpenHands API read) takes several seconds while another user message sits behind it in the same `getUpdates` batch, the second update waits sequentially for the first to complete.
- **Data-loss / data-integrity implications:** Lowest possible risk; preserves existing `BEGIN IMMEDIATE` and single-owner SQLite assumptions (`WP-07` also fixes separate `DEF-013`/`NEW-DEF-03` atomicity and `DEF-011` blocking disk I/O via `asyncio.to_thread` without touching SQLite from worker threads).
- **User-visible consequences:** None relative to current runtime (already sequential), aside from occasional queuing delay behind slow read commands in multi-update bursts.
- **Affected work packages:** `WP-07` (comment/config alignment + poller parity test), `WP-08` (runbook parity), `WP-09`.
- **Reversibility:** Fully reversible in a future design cycle if Option B's proof prerequisites are ever completed.
- **Prerequisites / additional evidence:** Verify no existing test requires `.concurrent_updates(True)` flag specifically on `Application` (check `tests/test_app.py` / `tests/test_stage2_custom_polling.py` during `WP-07` so removing or retaining the flag with accurate comment does not break tests).

#### Option B — Authorize Future Concurrent Intra-Batch Dispatch Only After Formal Proof & Serialization Redesign
- **Exact policy & behavior:** Keep sequential dispatch for now until a dedicated technical design and verification package proves single-`sqlite3.Connection` safety across concurrent coroutines, implements per-user async/state locks protecting `user_state`, `attachment_batches`, `list_cache`, and `repo_nav`, guarantees deterministic arrival-order preservation in `collect_outcomes` / `commit_batch_outcomes` / head-of-line `acknowledgment_boundary()`, and passes multi-update concurrency & SQLite contention stress tests before refactoring `TelegramPoller.process_updates`.
- **Benefits:** Removes head-of-line latency behind slow OpenHands API reads within multi-update batches once safely engineered and proven.
- **Risks / failure modes:** High engineering complexity on a single-process shared `sqlite3.Connection` (`check_same_thread=False` has **no** internal coroutine-level transaction isolation if any async path yields mid-transaction); any unserialized `await` between SQL read and write creates `SQLITE_BUSY`, interleaved transaction rollback corruption, or wrong-chat prompt routing across simultaneous messages from the same owner.
- **Data-loss / data-integrity implications:** Unproven until redesigned; improper sharing risks silent transaction rollbacks across sibling tasks or corrupted `user_state` / `attachment_batches` transitions.
- **User-visible consequences:** Faster acknowledgment of queued prompts behind slow exports once proven and shipped; delays `WP-07` concurrency closure until proof is built.
- **Affected work packages:** `WP-07` (major concurrency redesign + stress suite), `WP-08` (rewriting `OPERATIONS_RUNBOOK.md:123-127`), `WP-09`.
- **Reversibility:** Can fall back to sequential `dispatch_and_wait`, though per-user lock and DB refactoring touches core dispatch paths.
- **Prerequisites / additional evidence:** Formal concurrency design doc proving: (1) zero `await` inside open SQLite transactions; (2) per-`telegram_id` async serialization; (3) deterministic `collect_outcomes` batch-order preservation; (4) `WP-07` `asyncio.to_thread` file-I/O separation; and (5) passing multi-coroutine stress tests on `Python 3.11` & `3.13`.

### E. Consequences of deferring the decision

- **Remains blocked:** Reconciling or refactoring `bot/app.py:75-87` vs `bot/polling.py:161-162` concurrency behavior (`DEF-006` in `WP-07`), finalizing `OPERATIONS_RUNBOOK.md:123-127` parity (`WP-08`), and closing **`Gate C`**.
- **Can proceed independently:** `WP-01`..`WP-06`, plus the non-poller parts of `WP-07` (`DEF-011` async `StagingStore` & `AttachmentReaper` I/O offload + quota reservation ledger; `DEF-013` / `NEW-DEF-03` SQLite state+outcome atomicity & whitespace `renew_awaiting` fix).
- **Operational risk if deferred:** Runtime stays sequentially safe, while the misleading `U04` comment (`bot/app.py:75-78`) continues contradicting `bot/polling.py:161-162` and `OPERATIONS_RUNBOOK.md`, risking accidental concurrency regressions by future contributors. Preserves stability without new race conditions.

### F. Explicit owner choice

`OWNER DECISION REQUIRED — NO OPTION SELECTED`

- [ ] **Option A** — Preserve strictly sequential intra-batch polling in `TelegramPoller.process_updates` and reconcile `bot/app.py:75-87` comments/configuration with `OPERATIONS_RUNBOOK.md:123-127`.
- [ ] **Option B** — Keep sequential polling blocked from concurrency changes for now and commission a formal concurrency/SQLite-safety design and proof before refactoring `TelegramPoller.process_updates` for intra-batch concurrency.

---

## 8. OD-05 decision analysis

### A. Decision statement

Which external qualification checks (`WP-10` / `DEF-016`: live Enzonic SFTP fingerprint & workflow execution, isolated `H1` SQLite persistence canary, `HOST-02` Mini App HTTPS ingress, upstream OpenHands API schema inspection, and physical Android 12 WebView `MT-2` download verification), if any, should be authorized after local `Gates A–C` pass, and should `Stage B` remote attachment upload (`DEF-015` / `B1–B3`) remain closed (`BLOCKED / DEFERRED`) or be formally reopened for evaluation?

### B. Current behavior

1. **Implemented behavior in code & infra tooling:**
   - **Enzonic read-only SFTP workflow:** `.github/workflows/enzonic-sftp-readonly-check.yml` (`126` lines) is strictly `workflow_dispatch`, `permissions: {}`, targets `us-four.enzonic.com:2022` as user `5s5k7kk.e56cc5c8`, pins `SHA256:6MPMP1TJ75QuFqne7qrvN4+7vMW4tFvokGhmIE74fls`, rejects missing/empty `ENZONIC_SSH_PRIVATE_KEY` without printing secrets, unsets the env var, verifies host key before auth, and runs only `pwd` and `ls -la /` (no `.env`, SQLite, or write operations).
   - **SQLite `H1` Canary tool:** `tools/katabump-sqlite-canary/canary.py` (`245` lines, stdlib-only, no network, no secrets) provides `write`, `read`, and `inspect` over an explicit absolute `--db` path outside the repo and refuses `bot_state.sqlite3`.
   - **Stage B remote upload:** No remote attachment upload worker, scoped upload credential handler, or agent-server static origin allowlist (`Gate G1`) exists in `bot/`.
2. **Documented intended behavior & safety boundaries:**
   - **`"OpenHandBot"` (`Brave Grove`) live server protection (`docs/DEPLOY_ENZONIC.md:27-42`, `docs/OHB2_ENZONIC_DEPLOYMENT_PREFLIGHT.md:10-12,370-374`):** Strictly protected as a **live project server, NOT a canary**. Restarting, stopping, starting, uploading/editing/deleting files, opening console/terminal, changing env vars, testing SQLite (`C3` explicitly excluded by owner), or deploying to it is strictly prohibited.
   - **`HOST-01` & `HOST-02` (`docs/DEPLOY_ENZONIC.md:10-24`):** Both remain **`BLOCKED` and deferred** due to 8 recorded Plan 04 obstacles (no Enzonic panel session, Cloudflare Turnstile blocking headless auth, no GUI/VNC, no SSH client, unverified SFTP auth/persistence/HTTPS ingress/always-on/sleep limits).
   - **Mini App & `MT-2` Android 12 gate (`docs/reviews/OHB2-MT2-COMPLETION-AND-ADVERSARIAL-VERIFICATION.md:139`):** Real Android 12 Telegram WebView download verification is `NOT_RUN (UNVERIFIED)`.
   - **OpenHands API spec (`docs/API_NOTES.md:81` vs `bot/openhands_client.py:344` vs proposals):** Upstream OpenAPI versions cited span `v1.68.1`, `v1.79.0`, and `v1.87.1`; live upstream schemas remain unverified externally.
   - **`Stage B` / `P0` reopening gates (`.agent/PROGRESS.md:20-36`):** Remains `BLOCKED / DEFERRED BY EXPLICIT PRODUCT DECISION` until either (1) an explicit product decision reverses Option D, OR (2) OpenHands exposes a **scoped upload-only credential** (no command-execution capability) AND a **static, verified `agent-server` origin allowlist (`Gate G1`)** + approved architectural design exist.
3. **Missing or incomplete behavior:**
   - No live GitHub Actions execution result or out-of-band confirmation exists for Enzonic's pinned SSH fingerprint (`SHA256:6MPMP1TJ75QuFqne7qrvN4+7vMW4tFvokGhmIE74fls`) or `ENZONIC_SSH_PRIVATE_KEY` (`DEF-016`).
   - No live `H1` persistence evidence exists on any target hosting volume.
   - No live `HOST-02` public HTTPS/TLS ingress verification exists (`MINI_APP_ENABLED=False`, `MINI_APP_URL=""`, `MINI_APP_TRUSTED_PROXIES=""`).
   - Remote attachment delivery (`DEF-015` / Stage B) does not exist (`UNIMPLEMENTED`).
4. **Previously proposed but unimplemented changes:**
   - `WP-10` (`docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md:712,761,793`) isolates all external qualification under **`Gate D`**, strictly decoupled from local/CI code remediation (`WP-01`–`WP-09` / `Gates A–C`).

### C. Why a decision is required

Local code fixes and CI testing (`WP-01`–`WP-09`) cannot verify third-party infrastructure, host persistence, secret-backed GitHub workflows, TLS reverse proxies, physical Android devices, upstream OpenHands API capabilities, or product scope for `Stage B`. Conversely, running external checks or opening `Stage B` without explicit owner authorization, credentials, isolated non-live targets, and strict guardrails risks violating `docs/DEPLOY_ENZONIC.md` live-server safety rules, `AGENTS.md` §6 (no unauthorized deployment/external calls/secrets), and `AGENTS.md` §14 (Option D `P0` deferment).

### D. Available options

#### Option A — Keep `WP-10` External Qualification and `Stage B` Completely Deferred / Closed
- **Exact policy & behavior:** Focus strictly on `WP-01`–`WP-09` (`Gates A–C`) in local/CI environments. Keep `WP-10` (`Gate D` external checks: Enzonic SFTP workflow run, `H1` canary, `HOST-02` TLS/HTTPS ingress, Android 12 `MT-2` verification, live OpenHands API verification) and **`Stage B` (`DEF-015` remote upload)** completely deferred (`BLOCKED / NOT_RUN`).
- **Benefits:** Zero risk of touching `"OpenHandBot"` (`Brave Grove`) or external secrets; avoids premature Stage B scope creep while `Gates A–C` and `OD-01`–`OD-04` are resolved cleanly; preserves `MINI_APP_ENABLED=False` and Option D (`P0` deferred) cleanly.
- **Risks / failure modes:** Production cutover readiness (`Gate D`), real Enzonic SFTP connectivity, SQLite persistence (`H1`), `HOST-02` HTTPS behavior, and Android 12 WebView `MT-2` downloads remain unverified indefinitely; bot users still cannot forward Telegram documents directly into OpenHands agent workspaces (`Stage B` remains unavailable).
- **Data-loss / data-integrity implications:** Zero external side effects; production host data remains untouched, though durability (`H1`) remains unproven (`SKIPPED / UNVERIFIED`).
- **User-visible consequences:** Local bot reliability improvements (`WP-01`–`WP-09`) can complete in CI, but production cutover (`Gate D`), Mini App live hosting (`HOST-02`), and direct remote file delivery (`Stage B`) remain unavailable.
- **Affected work packages:** `WP-10` (stays `NOT_RUN`), `Stage B` (`DEF-015` stays closed); `WP-01`–`WP-09` remain unaffected.
- **Reversibility:** Fully reversible whenever the owner later issues a separate `WP-10` or `Stage B` authorization.
- **Prerequisites / additional evidence:** None now; future execution requires explicit owner instruction.

#### Option B — Authorize Narrow, Guardrailed External Qualification (`WP-10`) After `Gates A–C`, Keeping `Stage B` Closed
- **Exact policy & behavior:** Keep `Stage B` (`DEF-015` remote upload) **closed/deferred** under Option D, and authorize **only** bounded, explicitly sequenced external `WP-10` verification checks after `Gates A–C` pass:
  1. Out-of-band Enzonic SSH host fingerprint confirmation + single `workflow_dispatch` run of `.github/workflows/enzonic-sftp-readonly-check.yml` (`pwd` + `ls -la /` only, non-mutating, secret in GitHub Secrets).
  2. Read-only OpenHands Cloud API OpenAPI/version inspection (`v1.68.1` vs `v1.79.0` vs `v1.87.1`) without creating/mutating live conversations.
  3. **Only if** the owner explicitly provisions a separate **isolated non-live canary server/container** (never `"OpenHandBot"` / `"Brave Grove"` and respecting Enzonic `C3` SQLite exclusion unless explicitly lifted on a separate isolated target): run `canary.py` (`H1` restart persistence) and `HOST-02` TLS/proxy header check, plus owner-run physical Android 12 Telegram WebView `MT-2` download verification.
- **Benefits:** Produces real evidence for `Gate D` (`DEF-016` closure) and physical Android 12 `MT-2` validation without jeopardizing the live Enzonic server or prematurely reopening Stage B architectural risks (`DEF-015`).
- **Risks / failure modes:** Requires operator time, out-of-band SSH fingerprint source, GitHub secret configuration (`ENZONIC_SSH_PRIVATE_KEY`), and an isolated non-live host if `H1`/`HOST-02` are tested; any mis-targeted panel action on `"Brave Grove"` remains catastrophic if guardrails are ignored.
- **Data-loss / data-integrity implications:** Read-only SFTP/OpenAPI checks make zero mutations; isolated `canary.py` refuses `bot_state.sqlite3` and writes only to a disposable `--db`. Live server remains untouched.
- **User-visible consequences:** Enables evidence-backed decision on `HOST-01`/`HOST-02` production readiness and confirms `MT-2` Android 12 UX, while Telegram -> OpenHands remote file upload remains local-only (`MT-2`).
- **Affected work packages:** `WP-10` (executes under `Gate D` after `Gates A–C`), `WP-09` Category 6; `Stage B` stays closed.
- **Reversibility:** Read-only checks are non-mutating; Mini App stays off (`MINI_APP_ENABLED=False`) unless explicitly promoted later.
- **Prerequisites / additional evidence:** Passing `Gates A–C` first; owner-supplied out-of-band Enzonic SSH fingerprint verification; confirmed `ENZONIC_SSH_PRIVATE_KEY` in GitHub Secrets; explicit confirmation of isolated (non-`Brave Grove`) canary target before any `H1` or `HOST-02` probe; physical Android 12 device access for `MT-2` check.

#### Option C — Authorize `WP-10` External Qualification PLUS Formal `Stage B` Scope Reopening Evaluation
- **Exact policy & behavior:** Authorize Option B's `WP-10` qualification steps **and** formally reopen `Stage B` (`DEF-015`) planning/requirements evaluation by tasking an upstream investigation into whether OpenHands Cloud now provides (1) a scoped file-upload credential incapable of arbitrary command execution, (2) a static, verifiable `agent-server` origin allowlist (`Gate G1`, zero SSRF), and (3) confirmed API semantics compatible with `D-15`/`D-34`/`D-35` and single-owner SQLite (`I2`/`I3`)—with **no Stage B implementation** permitted until a separate Stage B ADR & owner approval pass.
- **Benefits:** Establishes concrete truth on whether direct Telegram-to-OpenHands document upload (`P0` / `Stage B`) is technically feasible under OpenHands Cloud's live security model alongside hosting qualification.
- **Risks / failure modes:** If OpenHands still lacks a scoped upload credential or static `agent-server` origin contract, reopening `Stage B` investigation consumes effort without enabling implementation; prematurely loosening `Gate G1` or `Option D` would create severe credential-exposure or SSRF hazards.
- **Data-loss / data-integrity implications:** Evaluation-only (`read-only`) Stage B reopening alters zero code/DB state; any future Stage B implementation would introduce new batch transitions (`dispatching`/`uncertain`/`delivered`) that interact directly with `OD-01` and `OD-03`.
- **User-visible consequences:** None immediately until upstream feasibility is proven and a future Stage B ADR is approved; clarifies roadmap for `MT-2` temporary workaround vs long-term remote upload.
- **Affected work packages:** `WP-10`, plus future post-baseline `Stage B` planning (influences long-term framing of `OD-01` and `OD-03`).
- **Reversibility:** Investigation/evaluation is reversible (can re-close `Stage B` if upstream prerequisites fail); any future Stage B schema/API commitment would require separate gating.
- **Prerequisites / additional evidence:** All prerequisites of Option B, **plus** explicit owner authorization overriding `.agent/PROGRESS.md` Option D freeze for evaluation purposes, live OpenHands Cloud documentation/response proving scoped upload auth + static SSRF allowlist (`Gate G1`), and passing `Gates A–C`.

### E. Consequences of deferring the decision

- **Remains blocked:** All of `WP-10` (`DEF-016`, Enzonic live SFTP check, `H1` persistence canary, `HOST-02` HTTPS ingress, live OpenHands API check, Android 12 `MT-2` device test), **`Gate D`**, and any `Stage B` (`DEF-015`) reopening.
- **Can proceed independently:** **All** local/CI engineering work (`WP-01` through `WP-09`, `Gates A–C`), subject to `OD-01`–`OD-04` and Python CI dependency availability.
- **Operational risk if deferred:** Local code can be remediated and verified in CI, **but hosting durability (`H1`), SFTP reachability, Mini App TLS ingress (`HOST-02`), Android 12 downloads, and upstream OpenHands API compatibility remain completely `UNVERIFIED` / `NOT_RUN`**. Preserves live `"OpenHandBot"` (`Brave Grove`) and `Stage B` security boundaries intact with zero external risk.

### F. Explicit owner choice

`OWNER DECISION REQUIRED — NO OPTION SELECTED`

- [ ] **Option A** — Keep `WP-10` external qualification and `Stage B` (`DEF-015`) deferred/blocked while completing `WP-01`–`WP-09` in local/CI scope only.
- [ ] **Option B** — Authorize narrow, read-only / isolated-target `WP-10` external qualification after `Gates A–C` pass (protecting `"OpenHandBot"`/`"Brave Grove"` and keeping `Stage B` closed).
- [ ] **Option C** — Authorize `WP-10` external qualification after `Gates A–C` AND formally reopen `Stage B` (`DEF-015`) feasibility evaluation (strictly gated on scoped upload auth + static `Gate G1` SSRF allowlist before any implementation).

---

## 9. Cross-decision interactions and conflicts

No decision operates in isolation. Changing one boundary frequently alters the risk profile or prerequisites of another.

| Decision Pair | Classification | Verified Technical & Operational Interaction |
|---|---|---|
| **`OD-01` <-> `OD-03`** | **Direct dependency** | If `OD-03` keeps `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=True` (Option B), then `OD-01` Option A (preserving global `TERMINAL_UNPROVEN` block) leaves **every** out-of-the-box document upload causing permanent `DEF-001` lockouts unless external/manual DB clearing exists. Conversely, `OD-03` Option A (`False` default) reduces *new* `DEF-001` exposure for fresh installs (while starving `MT-2` until `=1`), yet **does not** fix pre-existing bricked batches (`handle_text:2245` still enforces `_handle_accompanying_text` regardless of `OD-03`) and still requires `OD-01` for any user opting into `=1`. Also, `WP-01` must preserve the `now >=` (`db.py`) vs `now >` (`web/services.py`) `15m` boundary asymmetry unless aligned later. |
| **`OD-01` <-> `OD-05`** | **Direct dependency** | Keeping `Stage B` (`DEF-015`) deferred (`OD-05` Option A or B) means `dispatching` and `uncertain` attachment batch states currently have **no producer** in runtime (`AttachmentReaper` step `0c` skips them); however, if pre-existing DB snapshots or future `Stage B` reopening (`OD-05` Option C) produce `dispatching`/`uncertain` or `delivered`/`failed` rows, `OD-01`'s policy on ambiguous/uncertain states vs verified terminal pass-through directly governs whether `Stage B` batches leave users locked out after delivery/failure. |
| **`OD-03` <-> `OD-05`** | **Direct dependency** | Setting `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=False` (`OD-03` Option A) disables local staging, making `MT-2` (`HOST-02` Mini App download) show an empty list unless `=1` is configured. Testing `MT-2` on real Android 12 hardware under `HOST-02` (`OD-05` Option B/C) explicitly requires either keeping `=True` (`OD-03` Option B) or configuring `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=1` during qualification. Furthermore, if `Stage B` (`OD-05` Option C) ever delivers remote upload cleanly, the interim `MT-2` local-transfer rationale for `=True` changes. |
| **`OD-02` <-> `OD-04`** | **Indirect interaction** | Both govern `TelegramPoller` (`bot/polling.py:155-178`) head-of-line behavior. Under `OD-04` Option A (sequential dispatch), any `FAILED_PERMANENT` error (`OD-02`) halts immediately at `updates[i]` and stops `acknowledgment_boundary()` there; `/updates_skip` (`OD-02` Option A/B) arriving later in `updates[j > i]` still executes sequentially in that same batch before `collect_outcomes`. If `OD-04` Option B (concurrent intra-batch dispatch) were ever pursued, **combining concurrent batch dispatch with `/updates_skip` introduces new race hazards** (e.g., `/updates_skip <id> confirm` racing concurrently against the target update or another update committing `commit_batch_outcomes` out of order). `OD-02` quarantine therefore becomes significantly safer and simpler under `OD-04` Option A. |
| **`OD-01` <-> `OD-02`** | **Indirect interaction** | `_handle_accompanying_text` (`OD-01`) runs inside `TelegramPoller` (`bot/handlers.py:2052-2204`). Under `OD-01` + `WP-01`, unexpected SQLite failures (including `AttachmentBatchIntegrityError` on out-of-enum/`NULL` batch statuses in `db.py:1536`) bubble out to `handle_processing_error` -> `_classify_failure` (`OD-02`). Currently `_classify_failure` classifies `AttachmentBatchIntegrityError` and corrupt-DB exceptions as `FAILED_PERMANENT`, halting polling (`OD-02` head-of-line deadlock) **on top of** `DEF-001`! If `/updates_skip` (`OD-02` Option A/B) were used to skip a batch-integrity crash without repairing the corrupt DB row (`OD-01`), subsequent text messages would immediately trigger the exact same deadlock again. Thus manual reconciliation for corrupt/out-of-enum rows (`OD-01`) and poison handling (`OD-02`) share operational triage dependencies. |
| **`OD-01` <-> `OD-04`** | **Direct dependency** | If `OD-04` Option B (intra-batch concurrency) were ever enabled without per-user locks, two simultaneous messages from the same owner in one batch (e.g., a `Document` upload + an immediately following text prompt, or two concurrent `Document` uploads) would race between `handle_attachment` staging (`pending`), `classify_attachment_routing` (`LIVE` vs `MULTI_LIVE`), `record_attachment_intent`, and `/cancel`. Preserving `OD-04` Option A (sequential dispatch) eliminates intra-batch concurrency races against `OD-01` batch/route invariants. |
| **`OD-02` <-> `OD-03`** | **No demonstrated dependency** | `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` (`True` vs `False`) marks `EXPLICITLY_IGNORED` cleanly when disabled (`bot/handlers.py:1891`) and `DURABLE_INTENT_RECORDED` / `EXPLICITLY_IGNORED` when enabled (`L1988-1989`), provided `reply_text` succeeds (`TelegramError` goes to `WP-04` Part 1 transient classification, not `OD-02` permanent poison policy). |
| **`OD-02` <-> `OD-05`** | **Indirect interaction** | `OD-05` Option A/C (`OD-02` Option C manual SQLite editing) interacts operationally: `docs/DEPLOY_ENZONIC.md:36` prohibits using Enzonic panel console/terminal on `"OpenHandBot"` (`Brave Grove`), and `HOST-01` has no SSH access (`§3` obstacle #4). Relying on manual out-of-band SQLite intervention (`OD-02` Option C) is therefore much harder to execute safely on Enzonic-style restricted hosting than in-bot `/updates_status` + `/updates_skip` (`OD-02` Option A/B). |
| **`OD-03` <-> `OD-04`** | **Indirect interaction** | Only if `OD-03` keeps intake `True` **and** `OD-04` Option B were ever pursued: concurrent `Document` uploads from the same user within one batch would race `StagingStore` quota checks (`DEF-011`) and `classify_attachment_routing` (`MULTI_LIVE`) unless serialized by per-user locks (`OD-04` Option B prerequisite). Under `OD-04` Option A, intra-batch uploads stay strictly serialized. |
| **`OD-04` <-> `OD-05`** | **Requires further evidence** | `bot/polling.py` sequential vs concurrent behavior interacts with hosting CPU/RAM constraints (`Enzonic` reported `50% CPU`, `~500 MB / 512 MiB RAM` unverified per `docs/DEPLOY_ENZONIC.md:21`) and OpenHands API response latencies during live qualification (`WP-10`). Until `WP-10` benchmarks real host behavior, intra-batch concurrency (`OD-04` Option B) lacks runtime resource evidence in addition to lacking SQLite safety proof. |

---

## 10. Work-package impact matrix (`WP-01`–`WP-10`)

Status classifications follow strict dependency gating from `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md` (§E, §G, §I):
- **`Fully blocked`**: Cannot proceed cleanly to implementation/closure without prerequisite owner decision(s) (`Gate 0`).
- **`Partially blocked`**: Non-gated sub-tasks can be implemented/prepared, while decision-gated sub-tasks remain frozen until owner sign-off.
- **`Eligible for future authorization after prerequisites`**: Not blocked by `OD-01`–`OD-05`, needing only standard task authorization (and any noted non-owner design prerequisite or sequential file coordination on `bot/handlers.py`).
- **`External qualification only`**: Outside local code remediation (`Gates A–C`); requires external credentials/infrastructure and `OD-05`.

| Work Package | Included Defects | Classification | Governing Decisions & Non-Owner Prerequisites | Mini App Exclusion & Gate Impact |
|---|---|---|---|---|
| **`WP-01`** — Attachment Emergency Mitigation & Safe Lifecycle Escape | `DEF-001`, `DEF-011` (copy), `NEW-DEF-06`; tracks `DEF-014` | **Fully blocked** *(on routing & default changes)* / *(Pre-change DB inventory & `NEW-DEF-06` design only unblocked)* | **`OD-01`** (freezes `classify_attachment_routing`, `D-34`, `D-35` until decided) + **`OD-03`** (freezes changing `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` default) + **pre-change read-only DB/staging inventory** before any irreversible cleanup. | Zero edits to `bot/web/*`, `bot/web/static/*`, `tests/test_miniapp_*`, `docs/MINI_APP.md`. Gates **`Gate 0` -> `Gate A`**. |
| **`WP-02`** — Harden All Telegram Callbacks (`28 q.answer` + `5` bare edits) | `DEF-005`, `NEW-DEF-01` | **Eligible for future authorization after prerequisites** | **None (`OD-01`–`OD-05` do not block).** Must coordinate sequentially on shared `bot/handlers.py` with `WP-03` & `WP-04`, after Phase 0 (`WP-01`) or clean branching. | Zero Mini App changes. Contributes to **`Gate B`**. |
| **`WP-03`** — Handler Outcomes, Operational `Stage4-F1` Propagation & Send Guards | `DEF-003`, `DEF-004`, `NEW-DEF-04` | **Eligible for future authorization after prerequisites** | **None directly** (unless **`OD-02` Option B** alters `send_reply_txt` `TextDocumentTooLargeError` outcome after message send; must sequence after `WP-02` on `bot/handlers.py`). Does not alter `list_conversations` or `_show_repos` (already compliant). | Zero Mini App changes (`bot/web/*` error serialization untouched). Contributes to **`Gate B`**. |
| **`WP-04`** — Fix `_classify_failure` & Design/Implement ADR §28.4 Poison Quarantine | `DEF-002` | **Partially blocked** | **Part 1 (`_classify_failure` transient fixes):** **Eligible** (sequenced after `WP-03` on `bot/handlers.py`; no `OD` blocker).<br>**Part 2 (ADR §28.4 `/updates_status`, `/updates_skip`, schema quarantine):** **Blocked on `OD-02`** (explicit owner approval required). | Zero Mini App changes. Part 1 + `OD-02`-gated Part 2 complete **`Gate B`**. |
| **`WP-05`** — Worker Correctness, Cache Invalidation & Cursor-Loop Protection | `DEF-007`, `DEF-008`, `DEF-012`, `NEW-DEF-02`, `NEW-DEF-05` | **Eligible for future authorization after prerequisites** | **None (`OD-01`–`OD-05` do not block).** Touches `watcher.py`, `notifier.py`, `outbox.py`, `openhands_client.py`, `app.py` (minimal `on_created` callback). | Zero Mini App changes. Contributes to **`Gate C`**. |
| **`WP-06`** — Status Normalization (`STATE_LABELS` + `get_status`) & 64-Byte Callback Refs | `DEF-009`, `DEF-010` | **Eligible for future authorization after prerequisites** | **None from `OD-01`–`OD-05`.** `STATE_LABELS["unknown"]` & `get_status` normalization are unblocked; **persistent `callback_refs` DB table (`17 -> 18` tables) is gated on completing the mandatory TTL / bounded cleanup / stale-ref / user-action-authz Design Prerequisite** (`Gate 0`), plus sequential `bot/handlers.py` coordination and feeding schema count into `WP-08`. | Zero Mini App changes. Contributes to **`Gate C`**. |
| **`WP-07`** — State Consistency, Attachment I/O & Quotas & Poller Concurrency | `DEF-006`, `DEF-011` (quota/async I/O), `DEF-013`, `NEW-DEF-03` | **Partially blocked** | Depends on **`WP-01`** finishing first. Non-poller fixes (`DEF-011` `asyncio.to_thread` offload + quota ledger; `DEF-013`/`NEW-DEF-03` DB+outcome atomicity & whitespace non-renewal) and conservative sequential comments (`OD-04` Option A) are clear after `WP-01`; **enabling intra-batch polling concurrency (`OD-04` Option B) is strictly BLOCKED** on **`OD-04`** + formal SQLite/per-user proof. | Zero Mini App changes (ensure ASGI download/read paths share single `Database` safely). Contributes to **`Gate C`**. |
| **`WP-08`** — Operational Docs Sync, `start.sh` Probe & Parity Tests | `DEF-017`, `DEF-018`, `NEW-DEF-08` | **Partially blocked** *(Sequenced after `WP-01`, `WP-04`, `WP-06`, `WP-07`)* | Requires final outcomes from **`OD-01`**..**`OD-04`** (final `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` default, `/updates_*` commands if approved, final `17` vs `18` vs `19` SQLite table count, final polling behavior) so `OPERATIONS_RUNBOOK.md`, `README.md`, `ZERO_TOUCH_STARTUP.md`, `API_NOTES.md`, and `NEW-DEF-08` parity tests reflect truth. `start.sh:56` (`anyio`) and parity test design are clear once schema/env settle. | **`docs/MINI_APP.md`, `bot/web/*`, and `Config.mini_app_*` MUST remain untouched**; AI Studio scaffold files preserved untouched unless explicitly ordered. Completes **`Gate C`**. |
| **`WP-09`** — Full CI Verification Matrix Execution (`6` Independent Categories) | `DEF-019` | **Partially blocked** *(Local container lacks Python deps; gates all WPs)* | **Categories 1–3 & 5 (Python `3.11` & `3.13`):** Ready in CI once packages from `requirements.txt` / `requirements-dev.txt` are installed (currently `BLOCKED` in local container).<br>**Category 4 (Frontend JS on `Node 22`):** `PASS` (`280/280`, read-only).<br>**Category 6 (External live checks):** Strictly gated on **`WP-10` & `OD-05`**. | Mini App tests (`tests/test_miniapp_*.py`, `tests/frontend/*.test.js`) run strictly **read-only** (`0` edits). Gates **`Gates A–D`**. |
| **`WP-10`** — External Infrastructure Qualification & Future Cutover Checks | `DEF-015`, `DEF-016` | **External qualification only** | Strictly gated on **`OD-05`**, passing **`Gates A–C`**, external credentials (`ENZONIC_SSH_PRIVATE_KEY` + out-of-band fingerprint), isolated non-live canary target (never `"Brave Grove"`), Android 12 device, and separate `Stage B` prerequisites. | Zero Mini App edits; `HOST-02` TLS/Android 12 verification runs strictly externally. Gates **`Gate D`**. |

---

## 11. Decisions requiring explicit owner approval

Every item below requires explicit, written owner authorization before any code, schema, config default, or external execution proceeds (`AGENTS.md` §14, Baseline §H, `Gate 0`):

1. **`OD-01` (D-34 `TERMINAL_UNPROVEN` & Uncertain/Ambiguous Outcomes Policy):** Explicit owner selection between Option A (keep `D-34` global terminal blocking as-is + manual external reconciliation), Option B (bounded verified terminal pass-through amending `D-34` while preserving fail-closed on `UNRESOLVED`/`EXPIRED_PENDING`/`invalid_t0`/corrupt/`TERMINAL_ASSOCIATED`), or Option C (hybrid explicit owner confirmation/clearance + manual reconciliation for uncertain/ambiguous states)—plus confirmation before any irreversible cleanup of pre-existing user attachment batches.
2. **`OD-02` (ADR §28.4 Manual Poison Quarantine Contract):** Explicit owner selection between Option A (strict ADR §28.4 `/updates_status` + `/updates_skip <update_id> confirm` + durable audit schema for all `FAILED_PERMANENT`), Option B (deterministic pre-checked `TextDocumentTooLargeError` rejection split + ADR §28.4 quarantine), or Option C (`WP-04` Part 1 transient classifier fix only + optional read-only `/updates_status`, deferring skip/schema changes)—including explicit choice of SQLite schema extension (`update_failures` columns vs `acknowledgment_overrides` table) if Option A or B is chosen.
3. **`OD-03` (`ATTACHMENT_DOCUMENT_INTAKE_ENABLED` Default vs `MT-2`):** Explicit owner authorization either to flip default from `True` to `False` in `bot/config.py:43,315-317` & `.env.example` (Option A, acknowledging `MT-2` becomes empty unless opted into `=1`) or to retain `True` relying on `WP-01` + `OD-01` mitigation (Option B).
4. **`OD-04` (`TelegramPoller` Concurrency vs Sequential Execution):** Explicit owner approval either to preserve strictly sequential intra-batch polling and align `bot/app.py:75-87` comments with `OPERATIONS_RUNBOOK.md:123-127` (Option A) or to authorize a future formal concurrency/SQLite-safety redesign & proof prerequisite before refactoring `TelegramPoller.process_updates` (Option B).
5. **`OD-05` (External Infrastructure Qualification & `Stage B` Scope):** Explicit owner decision on keeping `WP-10` & `Stage B` deferred (Option A), authorizing narrow read-only / isolated-target `WP-10` qualification after `Gates A–C` (Option B), or also reopening `Stage B` (`DEF-015`) feasibility evaluation under `Gate G1` / scoped-credential requirements (Option C).

*Note on non-owner prerequisite:* `WP-06` persistent `callback_refs` requires completing the written **Lifecycle & Security Design Specification** (TTL, bounded cleanup, malformed/expired behavior, `telegram_id` + `conversation_id` + action scope binding, and restart resilience) prior to modifying `bot/db.py` (`17 -> 18` tables), in addition to standard technical review.

---

## 12. Items that remain blocked regardless of decision

Even if the owner resolves **all five** decisions (`OD-01`–`OD-05`) immediately, the following boundaries and constraints remain strictly **blocked or excluded** under current project governance and physical/environmental reality:

1. **Mini App Modification Exclusion (Hard Project Boundary):** `bot/web/*`, `bot/web/static/*`, `tests/frontend/*`, `tests/test_miniapp_*.py`, `docs/MINI_APP.md`, and `Config.mini_app_*` (`Config` fields/behavior/routes/UI) remain **strictly untouchable** (`0` edits) across `WP-01`–`WP-10`. Neither `OD-01`–`OD-05` nor `WP-01`–`WP-10` authorizes modifying the Mini App frontend, ASGI endpoints, or `Config.mini_app_*` logic.
2. **Live Enzonic Server (`"OpenHandBot"` / `"Brave Grove"`) Safety Lock:** Regardless of `OD-05`, touching, restarting, stopping, uploading/deleting files, opening console/terminal, altering env vars, testing SQLite (`C3`), or deploying to the existing live Enzonic `"OpenHandBot"` (`Brave Grove`) server remains **strictly prohibited** (`docs/DEPLOY_ENZONIC.md:27-42`).
3. **Stage B Implementation (`B1–B3` / `DEF-015` Code):** Even under `OD-05` Option C (reopening `Stage B` evaluation), **implementing remote file upload code remains blocked** until OpenHands Cloud provides a verifiable **scoped upload-only credential** (no command execution), a **static verified `agent-server` origin allowlist (`Gate G1`)** proves zero SSRF, and a separate approved ADR/review passes.
4. **Full Backend Behavioral, Integration, Static & Security Verification (`WP-09` Categories 1–3 & 5) inside This Container:** Because all `10/10` Python packages (`python-telegram-bot`, `httpx`, `starlette`, `uvicorn`, `python-dotenv`, `anyio`, `pytest`, `pyflakes`, `bandit`, `pip_audit`) are missing here, backend verification (`pytest`, `pyflakes`, `bandit`, `pip_audit`) remains physically **`BLOCKED`** in this sandbox regardless of decisions and **must** execute in a proper `Python 3.11` & `Python 3.13` CI or installed `.venv` environment before any code gate (`Gates A–C`) can pass.
5. **No Automatic Poison Skipping & No False `exactly-once` Claims:** Automatic skipping of failed/poison Telegram updates (`max+1` without confirmation), guessing companion prompt routing via text/timestamps (`D-34`), silent un-reap/byte restoration (non-existent backup subsystem), and claiming `exactly-once` external delivery (`bot/outbox.py`, ADR §30.4) remain **permanently prohibited** across all options.
6. **Irreversible Historical DB/Disk Losses & `.git` Inspection Locally:** Deleted/unlinked staging files (`reaped`), absence of `.git` metadata in this container, and un-captured historical external states cannot be retroactively reconstructed by policy choices.

---

## 13. Recommended decision sequence

This sequence orders **owner discussion and decision resolution** strictly by dependency direction—it is **not** a choice of options and **not** an implementation schedule:

1. **First — Resolve `OD-01` (`D-34` & Uncertain Outcomes) and `OD-03` (`ATTACHMENT_DOCUMENT_INTAKE_ENABLED` Default vs `MT-2`) Together:**
   - *Why first & paired:* `OD-01` and `OD-03` directly interact (`§9`) and jointly block Phase 0 (`WP-01` / `Gate A`), which eliminates the live `DEF-001` owner-bricking defect. Deciding whether intake stays `True` (`OD-03` Option B) depends directly on how `OD-01` resolves terminal/post-`/cancel` routing, and deciding `OD-01` establishes the safety contract before `WP-07` or `WP-08` can follow.
2. **Second — Resolve `OD-02` (ADR §28.4 Exception & Poison Quarantine Policy):**
   - *Why second:* Phase 1 (`WP-02` -> `WP-03` -> `WP-04` Part 1) can prepare `bot/handlers.py` reliability, while **`WP-04` Part 2** (`DEF-002` poison recovery + any schema addition) needs `OD-02` settled before leaving Phase 1 (`Gate B`) and before `WP-08` freezes command/schema parity.
3. **Third — Resolve `OD-04` (`TelegramPoller` Concurrency vs Sequential Policy):**
   - *Why third:* Follows Phase 0–1 safety (`WP-01`–`WP-04`) and determines whether Phase 2b (`WP-07` / `Gate C`) simply reconciles comments/docs cleanly with sequential polling or must pause for a full single-connection SQLite + per-user lock concurrency redesign prior to `WP-08`.
4. **Fourth — Resolve `OD-05` (External Qualification & `Stage B` Scope):**
   - *Why fourth:* `WP-10` (`Gate D`) cannot execute safely until local/CI remediation passes `Gates A–C` (`WP-01`–`WP-09`) and `OD-01`–`OD-04` stabilize what code/flags would be qualified; evaluating `OD-05` last keeps local CI stabilization decoupled from external hosting credentials, isolated canary provisioning, physical Android 12 testing, and `Stage B` upstream requirements.

---

## 14. Evidence and verification limitations

All claims in this briefing were verified directly against repository files present at task execution time, subject to the following explicit limitations (never omitted or masked):

1. **Missing Python Packages in Container (`WP-09` Categories 1–3 & 5 `BLOCKED`):** `python3 --version` is `3.11.2`, and `165/165` Python files pass syntax-only `ast.parse` (`0` syntax errors). However, all `10/10` packages in `requirements.txt` and `requirements-dev.txt` (`python-telegram-bot`, `httpx`, `starlette`, `uvicorn`, `python-dotenv`, `anyio`, `pytest`, `pyflakes`, `bandit`, `pip_audit`) are absent. Therefore, **no Python behavioral test, integration suite (`pytest -q`), `pyflakes`, `bandit`, or `pip_audit` was executed here**, and historical counts in `docs/reviews/*` (e.g., `3094 passed`) are archival records only, not current execution proof.
2. **Frontend Regression Suite (`WP-09` Category 4 `PASS`, Read-Only):** `node --test tests/frontend/*.test.js` executed cleanly on `Node v22.23.2` (`280` tests, `280` pass, `0` fail across `23` `*.test.js` files) with zero edits to any frontend or Mini App file. This confirms JavaScript unit invariants only; it proves nothing about Python backend handlers, ASGI integration, or live Telegram WebView downloads.
3. **Missing `.git` Directory (`UNVERIFIED`):** `.git` does not exist in `/app/applet`. Local commit history, current branch name, exact `HEAD` commit SHA, uncommitted diff history prior to this session, and GitHub Actions remote workflow run history cannot be verified from Git locally.
4. **External Infrastructure & Devices (`NOT_RUN` / `UNVERIFIED`):**
   - Enzonic SFTP host fingerprint (`SHA256:6MPMP1TJ75QuFqne7qrvN4+7vMW4tFvokGhmIE74fls` at `us-four.enzonic.com:2022`), `ENZONIC_SSH_PRIVATE_KEY` validity, and `.github/workflows/enzonic-sftp-readonly-check.yml` remote execution were **not** run (`WP-10` / `DEF-016`).
   - Live SQLite `H1` persistence (`tools/katabump-sqlite-canary/canary.py`), `HOST-01`/`HOST-02` public HTTPS ingress, and `WP-09` `Python 3.13` CI runs remain `NOT_RUN` / `UNVERIFIED`.
   - Physical Android 12 Telegram WebView download testing for `MT-2` (`docs/reviews/OHB2-MT2-COMPLETION-AND-ADVERSARIAL-VERIFICATION.md:139`) remains `NOT_RUN`.
   - Upstream OpenHands Cloud API OpenAPI schema discrepancy (`v1.68.1` in `docs/API_NOTES.md:81` vs `v1.79.0` in `bot/openhands_client.py:344` vs `v1.87.1` in proposals) and scoped upload credential support (`DEF-015`) remain `UNVERIFIED` externally.
5. **No Secrets Inspected or Printed:** Zero tokens, private keys, `.env` secrets, or live user data were read, requested, or recorded in this briefing.
