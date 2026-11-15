# OHB2-PLAN12-P0-REMOTE-UPLOAD-DESIGN-AND-SECURITY-REVIEW

- **Task ID:** `OHB2-PLAN01-REMAINING-AND-PLAN02-REMOTE-ATTACHMENT-DELIVERY`
- **Plans Covered:** `OHB2-REPAIR-PLAN-01-RESOURCE-STAGING` (Plan 01 closure + confirmed fixes) and `OHB2-PLAN-12-P0-REMOTE-ATTACHMENT-UPLOAD` (Plan 02 architecture, security, verification, reconciliation, and readiness review)
- **Date:** `2026-11-15`
- **Baseline Context:**
  - Historical audit SHA (from repository records): `facf1f42578a20a4a37e220eca016ce3d534e750`
  - Plan 01 reported completion commit (from repository records): `f6c0f24`
  - Local workspace note: `.git` directory is absent in this workspace snapshot (`git status` unavailable locally); verification below is anchored directly to the live workspace files on disk.
- **Plan 01 Closure Verdict:** **`PASS_WITH_NOTES`** (core `FIX-01..FIX-04` and `LIFE-01..LIFE-02` verified in source; 2 confirmed Plan 01 defects in `bot/attachments.py` + 1 header-normalization edge case in `bot/handlers.py` fixed and verified via stdlib runtime checks; full `pytest`/`pyflakes`/`bandit`/`pip_audit` remain `UNVERIFIED` locally due to absent third-party tools in this Python 3.10 stdlib-only environment and must run in CI).
- **Plan 02 Implementation Readiness Verdict:** **`BLOCKED`** (`BLOCKED_BY_PROVIDER` + `BLOCKED_BY_OWNER_DECISION` + `NOT_IMPLEMENTED` — zero remote upload code, zero schema changes, zero worker additions performed).
- **Independent Review Status (Phase J):** **`INDEPENDENT_REVIEW_NOT_RUN`** (self-review only performed below; no separate independent reviewer agent or `D-19` security sign-off executed).

---

## 1. Plan 01 Verification & Closure Summary (`OHB2-REPAIR-PLAN-01-RESOURCE-STAGING`)

### 1.1 `FIX-01..FIX-04` & Lifecycle Source Audit

| Fix ID | Original Defect | Existing Correction | Current Evidence | Remaining Issue Found & Status |
| --- | --- | --- | --- | --- |
| `FIX-01` | Unbounded `File.download_to_memory` buffered full body into RAM before size check | Streaming HTTPX `client.stream("GET", url, headers={"Accept-Encoding": "identity"})`, 3xx rejection, non-`identity` encoding rejection, local capped reader `_read_local_capped`, `StagingStore._write_to_path` byte cap + `os.fsync` + `_safe_unlink` | `bot/handlers.py:1724-1815`; `bot/attachments.py:583-608`; `0` calls to `download_to_memory(` in `bot/` | **Fixed in this task:** (1) FD leak in `StagingStore._write_to_path` if `os.fdopen(fd, "wb")` raised before entering `with`; (2) `Content-Encoding` whitespace/empty normalization in `bot/handlers.py:1800-1803` |
| `FIX-02` | Unbounded concurrent Telegram downloads | Loop-bound `_get_download_semaphore()` (`MAX_CONCURRENT_DOWNLOADS = 4`) wrapping `get_file` + full download | `bot/handlers.py:1695-1713, 1758` | None confirmed |
| `FIX-03` (`+R01/R02/R05`) | No batch/total staging resource accounting or quota hooks | `StagingStore` supports `max_items_per_batch`, `max_total_bytes`, `max_bytes_per_batch` (all `None` by default under `D-12` Option A; zero quota keys in `bot/config.py`); accounting via `_batch_active_files` / `staging_total_bytes` (`lstat` regular files) | `bot/attachments.py:290-312, 463-580, 666-692`; `bot/config.py` | **Fixed in this task:** uncaught non-`OSError` DB exception inside `StagingStore.store` when `_effective_cap(batch_id)` calls `_batch_active_files` (`sqlite3.Error` now returns `StageStatus.DB_FAILED` cleanly) |
| `FIX-04` | Silent permission failure on staging root | `ensure_staging_root` rejects symlinks/non-dirs, enforces `0o700` via `os.chmod` + re-`stat`, raises `StagingError` -> `StageStatus.WRITE_FAILED` | `bot/attachments.py:237-273, 652-657` | None confirmed |
| `LIFE-01/02` | Cleanup only at startup / race between late write and expiry | `AttachmentReaper` at startup + `OpportunisticSweeper` (`60s` min-interval) in `Watcher.tick()`; atomic `BEGIN IMMEDIATE` CAS `try_mark_attachment_item_stored` checking item=`pending` AND batch=`pending` | `bot/app.py:233-241`; `bot/watcher.py:100`; `bot/attachments.py:975-1482`; `bot/db.py:1224-1281` | None confirmed (note: `AttachmentReaper.sweep` line `1069` returns early if `list_expired_pending_attachment_batches` raises, a conservative fail-safe choice) |

### 1.2 Preserved Invariants Checked in Code
- **`D-12` / Option A:** `StagingStore` defaults remain `None` for batch/total quotas; only `MAX_ATTACHMENT_BYTES = 3 MiB` is active. No `Config` field added (`bot/config.py`).
- **`D-15` (2026-11-15 Option A):** `ATTACHMENT_BATCH_TTL` remains fixed at 15 minutes from `T0` with no extension (`bot/attachments.py:361-377`).
- **`D-33/D-34/D-35`:** `attachment_message_identity` (`PRAGMA foreign_keys=ON` + `ON DELETE RESTRICT`), `TERMINAL_UNPROVEN` fail-closed routing in `bot/handlers.py:2041-2065`, and independent retention untouched.
- **Single Ownership (`I2/I3`) & N-4 Substitution:** Zero new workers/schedulers/SQLite owners; `bot/handlers.py:_read_local_capped` preserves `open(...)` compatibility with existing monkeypatch tests (`tests/test_repair_plan_01_review_findings.py:643`).

---

## 2. Phase C — Plan 02 Identity Mapping & Upstream API Verification

### 2.1 Authoritative Identity & Provenance Mapping (Phase C1)

| Identity Element | Authoritative Source | Persistence / Lifetime | Security & Integrity Rule |
| --- | --- | --- | --- |
| `telegram_id`, `chat_id`, `message_id` | Telegram `Update` -> `attachment_message_identity` (`bot/db.py:804`) | Permanent (`ON DELETE RESTRICT`, independent of `processed_updates`) | Canonical message identity (`D-33/D-35`); never substituted by `update_id` |
| `update_id` | Telegram `Update.update_id` -> `processed_updates` | Deduplication & polling ack window only | Delivery identifier only; never proves message-batch uniqueness |
| `conversation_id` | `db.awaiting_state` (`kind="route"`) -> `attachment_batches.conversation_id` | Immutable per batch (`A2`), re-checked at `A3` & dispatch | Regex `^[A-Za-z0-9_-]{1,64}$`; fail-closed on `db.is_deleted(cid)` |
| `OpenHands user_id` vs `created_by_user_id` | `GET /api/v1/users/me` (`IdentityCache`) vs `AppConversation.created_by_user_id` | Runtime / cached owner UUID (`bot/files.py`) | Fail-closed (`UNAUTHORIZED`) if missing or unequal (`I9`) |
| `batch_id`, `item_id` | `secrets.token_hex(16)` (`bot/attachments.py:351-358`) | Persistent primary keys in SQLite | Locally generated opaque IDs |
| `staging_token` | `secrets.token_hex(16)` (`bot/attachments.py`) | 32-hex filename in `0700` staging root | Opaque; validated by `^[0-9a-f]{32}$` (`bot/web/download.py`) & `is_safe_workspace_path` |
| `display_name` | Untrusted Telegram document `file_name` -> `sanitize_display_name` | Metadata only in `attachment_items.display_name` | **Never** used directly as a local or remote path |
| `client_operation_id` (Planned) | Deterministic derivation from `(batch_id, item_id, staging_token)` | Persistent once DB schema approved (`D-21`) | Anchors idempotent upload & crash-safe reconciliation |
| `sandbox_id`, `conversation_url`, `workspace_root` | `AppConversation` from Cloud V1 | Ephemeral / container-scoped | Must be re-fetched & validated per dispatch; never assumed static across restarts |
| `remote_relpath` (Planned) | Bot-computed: `.openhandbot_attachments/<batch_id>/<item_id>_<safe_leaf>` | Assigned per item inside verified workspace root | Normalized POSIX relative path confined to `workspace_root` (`D-05/D-06`) |

### 2.2 Official OpenHands API Capability Verification (Phase C2)

| API Surface & Source | Capability Verified (`[F]`) | Security / Functional Gap (`[F]` / `[U]`) | Plan 02 Impact |
| --- | --- | --- | --- |
| Cloud V1 (`https://app.all-hands.dev/openapi.json` `1.92.0`, 257 paths) | Read/export only: `GET .../file`, `GET .../files`, `GET .../download` (zip) | **0 upload endpoints**; `send-message` supports `TextContent \| ImageContent` only (`data:` URL support on Cloud unverified, image-only) | Cannot upload general documents through Cloud V1 today |
| Agent Server (`agent-sdk.json` `0.1.0`, 40 paths) | `POST /api/file/upload/{path}` (`multipart/form-data`, `file`) | **Blocker B1 (`D-10/D-11`):** single `X-Session-API-Key` grants `bash` execution & secrets access; **no** workspace confinement in `file_router.py::_upload_file`; **no** size cap; **no** idempotency or SHA-256 response | Unsafe to enable without owner/upstream resolution of B1 + client-side hardening |
| `AppConversation` (`remote_sandbox_service.py`) | Exposes `conversation_url`, `session_api_key`, `sandbox_id`, `repositories[].path` (`readOnly`) | **Blocker B2 (`D-14`):** `conversation_url` switches between path-mode & subdomain-mode with no committed origin allowlist; `sandbox_id` may be shared under non-`NO_GROUPING` (`D-06`) | Requires committed origin allowlist + workspace isolation check before connecting |
| MT-2 Mini App Download (`bot/web/download.py`) | Authenticated local user download from `staging` (`OwnedStreamingResponse`, `O_NOFOLLOW`, `fstat`) | Local browser download only — **not** remote workspace delivery | Kept strictly separate from OpenHands delivery status |

---

## 3. Phase D — Security & Threat Model (`B1`, `B2`, SSRF, Secret Isolation)

1. **Threat T1 — Over-Privileged Credential (`B1` / `D-10` / `D-11`):** Holding `X-Session-API-Key` grants full shell execution (`POST /api/bash/execute_bash_command`) and secret manipulation (`POST /api/conversations/{id}/secrets`). Mitigation requires either upstream Cloud V1 delegated upload proxy / scoped upload token (**recommended**) or explicit owner waiver + isolated proxy enforcement (**not approved**).
2. **Threat T2 — SSRF / Open Redirect / DNS Rebinding via `conversation_url` (`B2` / `D-14`):** Connecting blindly to `conversation_url` risks internal network SSRF or token exfiltration. Required controls:
   - Strict `https://` scheme, zero userinfo/query/fragment, exact match against owner/provider-committed `AGENT_SERVER_ALLOWED_ORIGINS`.
   - Single-shot DNS resolution rejecting all private, loopback, link-local, multicast, reserved, unspecified, and IPv4-mapped IPv6 addresses (`ipaddress`), pinning the socket connection to the validated IP while verifying TLS SNI and hostname certificate.
   - `follow_redirects=False` (`3xx` treated as hard fail-closed error).
   - Strict credential separation: Cloud Bearer token sent **only** to `OPENHANDS_BASE_URL`; `X-Session-API-Key` sent **only** to validated Agent Server origin.
3. **Threat T3 — Secret Persistence / Leakage:** `session_api_key` must remain volatile in memory only for the duration of an authorized dispatch — **never** stored in SQLite (`attachment_batches`, `attachment_items`, `outbox`, `settings`), exception strings, logs, or Mini App responses.
4. **Threat T4 — Arbitrary File Write Outside Workspace (`D-05` / `D-06`):** Because `file_router.py::_upload_file` checks only `is_absolute()` and executes `mkdir(parents=True)` before writing, the bot must refuse any upload unless `workspace_root` is positively verified from `AppConversation` (`created_by_user_id == owner_uuid`, not deleted, non-ambiguous sandbox grouping) and the computed path satisfies `PurePosixPath` normalization + `is_relative_to(workspace_root)` using an opaque prefix `.openhandbot_attachments/<batch_id>/<item_id>_<safe_leaf>`.

---

## 4. Phase E — Local Source Integrity & Honest Remote Verification

### 4.1 Local Source Integrity Guard (Pre-Upload & Streaming)
- Open staged file via `os.open(path, os.O_RDONLY | os.O_NOFOLLOW)` inside verified `0700` staging root.
- Verify `os.fstat(fd)`: regular file (`S_ISREG`), `0 < st_size <= MAX_ATTACHMENT_BYTES`, `st_size == item.size_bytes`.
- Record `(st_dev, st_ino, st_size)` and pre-compute `SHA-256`; re-hash chunks during streaming upload; abort fail-closed (`INTEGRITY_MISMATCH`) if size or digest shifts.

### 4.2 Honest Verification State Classification (`D-02` / `D-03` / `D-04`)

| Observed Remote Signal | Verification Classification | Allowed Batch Transition | User-Facing Truthfulness |
| --- | --- | --- | --- |
| Local `staging` write succeeded | `LOCALLY_STAGED` | Remains `pending` / `intent_recorded` | Local staging receipt only; never mention remote delivery |
| `POST /api/file/upload/{path}` returned `2xx` (`{success: true}`) | `TRANSPORT_ACCEPTED_UNVERIFIED` | Remains `dispatching` / `uncertain` (**NEVER** `delivered`) | Must NOT claim file was delivered to OpenHands |
| `GET .../files` lists `remote_relpath` AND independent re-read (`GET .../file` or upstream `stat+sha256`) matches exact byte length + `SHA-256` | `REMOTELY_VERIFIED` | Item `verified`; after all batch items verified + prompt sent -> `delivered` | Honest confirmation of verified delivery |
| Timeout, connection reset, `5xx`, process crash after HTTP request started | `AMBIGUOUS_IN_FLIGHT` | Transitions to `uncertain` (startup recovery + read-first reconciliation) | Honest pending/uncertain notice; no blind re-POST |
| Hash/size mismatch on re-read, `4xx` permanent rejection, or conversation deleted/unauthorized | `VERIFICATION_FAILED` / `PERMANENT_REJECTED` | `failed` (or `uncertain` if remote artifact state unknown) | Honest failure notice without claiming cleanup of C2 |

> **Verification Constraint Note:** `OpenHandsClient.read_file_text_bounded` (`bot/files.py`) currently caps reads at `256 KiB` and rejects binary/non-UTF-8 content. Therefore, full-content SHA-256 verification for arbitrary documents up to `3 MiB` requires either an upstream `stat + sha256` endpoint or a dedicated binary-safe bounded re-read verification path (`D-02/D-03/D-12`).

---

## 5. Phase F — Durable Outbox-Compatible Reconciliation & Schema Impact

### 5.1 Retry Classification Matrix (Phase F2)

| Phase / Failure Mode | Retryable? | Safe Action | Max Bounds & Notes |
| --- | --- | --- | --- |
| Authz failure (`UNAUTHORIZED` / `deleted_conversations` / `404`) | No | Fail closed -> `failed` | Zero upload HTTP calls; reaped later via `A4` (`D-17`) |
| Sandbox stopped/starting (`sandbox_status != RUNNING`) before upload | Yes | Keep queued / backoff | Bounded by `MAX_OUTBOX_ATTEMPTS` & `T0 + 15m` / op TTL (`D-15`) |
| DNS / SSRF allowlist / TLS handshake failure before request sent | No (config/origin) or bounded transient | Fail closed (`failed` on policy reject; bounded retry on DNS timeout) | Never bypass allowlist or fall back to unpinned IP |
| `429` / `503` before request body transmitted (or confirmed unstarted) | Yes | Respect `Retry-After` / backoff | Bounded by `MAX_OUTBOX_ATTEMPTS` |
| `400` / `413` / `415` / `422` permanent rejection on upload | No | `failed` | Never retry permanent 4xx |
| Network timeout / EOF / `5xx` / crash **after** upload bytes sent | **Never blind re-POST** | Mark `uncertain` -> read-only verify (`GET .../files` + `GET .../file` hash) | Re-POST allowed **only** if file is confirmed absent + within valid window (`I11`) |
| Upload verified (`REMOTELY_VERIFIED`), prompt `send-message` fails ambiguously | **Never blind re-POST prompt** | Mark prompt `unknown` (`OutboxWorker` `at-most-once`) | Existing `bot/outbox.py` invariant (`I13`) |

### 5.2 Crash / Timeout / Restart Reconciliation Scenarios (Phase F3)

1. **Crash before upload HTTP call (`intent_recorded` / pre-upload `dispatching`):** On restart, `OutboxWorker` recovery sees `remote_status == 'staged'` (no bytes sent), checks expiry (`T0 + TTL`) and `is_deleted`, re-validates `fstat`+`SHA-256`, and resumes deterministically.
2. **Crash mid-upload or response timeout (`uploading` / `dispatching`):** Startup recovery transitions `dispatching -> uncertain` (and item `uploading -> uploaded_unverified`). Reconciliation runs read-only check (`GET .../files` + content/checksum check) first:
   - Exact `SHA-256` & `size_bytes` match -> promotes item to `verified` without duplicate upload.
   - Partial/mismatched bytes -> fails closed (`failed` / `uncertain`); does **not** claim `delivered`.
   - Absent remotely + window valid + local file intact -> retries deterministically to the same `remote_relpath` (`client_operation_id`).
3. **Upload verified for 1..N items, crash before `send-message`:** Already-verified items remain `verified` (skipped on recovery); remaining items finish verification, then `OutboxWorker` executes existing `send-message` CAS (`pending -> claimed -> sending -> sent/unknown`).
4. **Conversation deleted mid-flight (`D-17`):** `db.is_deleted(cid)` check at each boundary stops further uploads/messages (`failed`), preserves `attachment_message_identity` (`D-35`), and leaves `staging` bytes for `A4` cleanup.
5. **Process restart during local `staging` (`A1/A2`):** Unchanged (`pending` items never marked `stored` are left for `AttachmentReaper` / `OpportunisticSweeper`).

### 5.3 Existing vs. Required Persistent State — Schema Gap Analysis (Phase F4 — Design Only)

- **Existing DB tables (`bot/db.py:770-816`) NOT modified in this task:**
  - `attachment_batches(batch_id, telegram_id, conversation_id, t0, status, created_at, updated_at, intent_text)`
  - `attachment_items(item_id, batch_id, staging_token, display_name, size_bytes, status, created_at, updated_at)`
  - `attachment_message_identity(telegram_id, chat_id, message_id, batch_id, conversation_id, created_at)`
  - `outbox(id, conversation_id, chat_id, text, status, error, created_at, updated_at, attempts, client_ref, notify_state)`
- **Confirmed Gaps Preventing Safe Plan 02 Implementation Without Schema Migration (`D-16/D-20/D-21/D-22`):**
  1. `attachment_items` lacks `sha256`, `source_dev`, `source_ino`, `remote_relpath`, `remote_status`, `remote_op_id`, `remote_attempts`, `remote_error`, `remote_verified_at`.
  2. `attachment_batches` lacks `outbox_id` / `dispatch_op_id` / `dispatch_attempts` / `last_error` / `dispatched_at` linking batch delivery to `OutboxWorker` single-owner recovery.
  3. **Rule compliance:** Zero tables, columns, lifecycle states, tokens, or secrets were added in this task.

---

## 6. Phase G — Component Readiness Classification Matrix

| Component | Classification | Rationale |
| --- | --- | --- |
| Telegram streaming intake, `0700` staging, `FIX-01..04`, `LIFE-01..02` (`bot/attachments.py`, `bot/handlers.py`) | `READY` | Verified + remaining FD leak & DB-cap bug fixed + stdlib runtime checks passed (full CI pytest/pyflakes pending) |
| Batch lifecycle `A2`, accompanying text intent `A3`, identity retention `D-33..D-35` (`bot/db.py`, `bot/attachment_text.py`) | `READY_WITH_NOTES` | Implemented locally; full CI pytest pending in this stdlib-only container |
| MT-2 local authenticated download (`bot/web/download.py`, `bot/web/services.py`) | `READY_WITH_NOTES` | Implemented locally; real Android 12 device gate `NOT_RUN`, `MINI_APP_ENABLED=False` preserved |
| Upstream upload endpoint authorization & least privilege (`D-10`, `D-11`, `B1`) | `BLOCKED_BY_PROVIDER` | No Cloud V1 upload route; Agent Server `X-Session-API-Key` grants full bash/secrets privilege |
| Trusted `conversation_url` origin allowlist (`D-14`, `B2`) | `BLOCKED_BY_PROVIDER` | No documented/committed Agent Server origin allowlist from provider |
| Workspace isolation proof & file permission contract (`D-05`, `D-06`, `D-24`) | `BLOCKED_BY_OWNER_DECISION` | Requires `D-05/D-06/D-24` approval and server-side confinement/grouping guarantees |
| Independent remote verification protocol (`D-02`, `D-03`, `D-04`) | `BLOCKED_BY_OWNER_DECISION` | Requires owner choice between upstream `stat+sha256` vs bounded Cloud binary re-read |
| Remote upload client, SSRF transport, & `OutboxWorker` reconciliation (`D-16`, `D-20`, `D-21`, `D-22`) | `NOT_IMPLEMENTED` | Deliberately deferred until `B1/B2` and owner decisions + schema approval are granted |
| DB schema migration for upload items/reconciliation | `NOT_IMPLEMENTED` | Explicitly prohibited without owner approval |
| Separate background worker / second SQLite DB | `NOT_REQUIRED` | Forbidden by invariants `I2/I3`; must reuse `OutboxWorker` + `Database` |

---

## 7. Phase H — Explicit Non-Implementation Scope Confirmation

Confirmed **NOT** performed in this task:
- No remote attachment upload or `POST /api/file/upload/{path}` client code added.
- No production API calls, no real credentials, no real user attachments used.
- No changes to `bot/db.py` tables, columns, lifecycle states, tokens, or secrets.
- No new worker, scheduler, background process, or SQLite owner added.
- No change to `MINI_APP_ENABLED` (`False`), no Autopush activation, no `D-12` quota activation, no `D-33..D-35` / `A3` / `F1` / `outbox` ownership changes.
- No `git commit`, `push`, PR, merge, release, or deployment executed.

---

## 8. Phase I — Focused Test Plan & Verification Status

### 8.1 Executed Locally (Stdlib + Node)
- `python3 -m py_compile` across `bot/attachments.py`, `bot/handlers.py`, `tests/test_repair_plan_01_review_findings.py` (and full `bot/` sweep before finishing).
- Targeted stdlib verification exercising `bot.attachments.StagingStore` + `bot.db.Database` + `AttachmentReaper` + `OpportunisticSweeper` (proving `os.close(fd)` on `os.fdopen` failure, `StageStatus.DB_FAILED` on `_effective_cap` DB failure, `0700`/`0600` permissions, and expiry sweep cleanup).
- `node --test tests/frontend/*.test.js` -> **267 passed, 0 failed**.

### 8.2 Added Regression Tests (Require CI `pytest` Runner)
- `tests/test_repair_plan_01_review_findings.py::test_staging_write_fdopen_failure_closes_opened_fd`
- `tests/test_repair_plan_01_review_findings.py::test_store_effective_cap_db_failure_returns_db_failed`
- `tests/test_repair_plan_01_review_findings.py::test_stream_download_content_encoding_whitespace_handling`
- **Local CI-tool unavailability:** `pytest`, `pyflakes`, `bandit`, `pip_audit`, `httpx`, `telegram`, `starlette`, `dotenv` are not installed in this container (`Python 3.10.12` stdlib only); full suite execution is **UNVERIFIED** locally and required in CI.

### 8.3 Future Plan 02 Test Matrix (For Post-Approval Implementation Only)
1. **SSRF & Origin Rejection:** non-HTTPS, userinfo/query/fragment, unlisted host, private/loopback/link-local DNS result, DNS rebinding change, `302` redirect rejection, header token cross-origin leak prevention.
2. **Workspace Confinement & Path Safety:** `..`, NUL, backslash, non-ASCII traversal, non-owner `created_by_user_id`, deleted conversation tombstone, missing/ambiguous `workspace_root`.
3. **Source Integrity:** file replaced/truncated/symlinked between `A1` and upload (`fstat` dev/ino/size mismatch), streaming `SHA-256` mismatch.
4. **Honest Verification:** `HTTP 200` with missing remote file or mismatched remote `SHA-256` MUST NOT mark `delivered`; `TRANSPORT_ACCEPTED_UNVERIFIED` stays non-terminal.
5. **Reconciliation & Restart:** crash before POST, mid-POST timeout (`uncertain` -> read-only verify -> recover without duplicate upload), partial batch recovery, tombstone mid-dispatch, outbox single-owner concurrency.

---

## 9. Phase J — Independent Review Status & Self-Review

### 9.1 Independent Review Gate
- **`INDEPENDENT_REVIEW_NOT_RUN`:** No independent reviewer agent or external `D-19` security review ran in this session. `D-19` remains an open mandatory release gate.

### 9.2 Adversarial Self-Review (Author Self-Check — NOT Independent)
- **Check 1 (Did Plan 01 fixes touch approved policies or break tests?):** `bot/attachments.py` changes are localized strictly to FD cleanup in `_write_to_path` and `DB_FAILED` error mapping in `store()`. `bot/handlers.py` normalizes `Content-Encoding` whitespace consistently with `bot/openhands_client.py:561`. `D-12` (`None` defaults), `D-15`, `D-33..D-35`, `open()` monkeypatch target, and zero-sweep-on-intake remain untouched.
- **Check 2 (Is there any hidden implementation of Plan 02 or unapproved schema change?):** Verified `0` remote upload routes, `0` DB schema modifications, `0` new workers, `0` secret additions.
- **Check 3 (Remaining honest uncertainty):** Full `pytest` suite (`3094+` tests), `pyflakes`, `bandit`, and `pip_audit` could not run inside this stdlib-only container; additionally `.git` is absent so commit ancestry/SHAs rely on existing repository documentation rather than local `git` verification.

---

## 10. Follow-Up Code Repair & Verification Boundary (`OHB2-PLAN01-PLAN02-REMAINING-CODE-REPAIR-AND-COMPLETION`)

- **Date:** `2026-11-15` (static inspection & code-repair pass; **zero test/lint/compile commands executed** in this pass — all checks listed below are **NOT RUN** in this pass).
- **Verified Prior Session Edits On Disk:** Confirmed presence of the FD-close guard on `os.fdopen` failure in `bot/attachments.py:_write_to_path`, DB exception catch around `_effective_cap` in `bot/attachments.py:StagingStore.store`, `Content-Encoding` `.strip().lower()` normalization in `bot/handlers.py:_download_attachment_chunks`, the 3 regression tests in `tests/test_repair_plan_01_review_findings.py`, and the `13` resolved / `22` open (`35` total) decision tally in `docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md`.
- **Additional Confirmed Plan 01 Defects Fixed In This Pass:**
  1. `bot/attachments.py:extension_of`: Previously used `.strip().lower()` without stripping control characters or trailing dots, while `sanitize_display_name` and `bot/web/download.py:safe_download_filename` stripped control characters and trailing `.`. Filenames such as `"evil.exe."`, `"run.sh.. "`, or `"payload.py\x07"` bypassed `_DENIED_EXTENSIONS` (`REJECTED_TYPE`) and were stored with sanitized denied extensions. Updated `extension_of` to strip control chars (`ch >= " " and ch != "\x7f"`) and trailing whitespace/dots (`strip().rstrip(" .")`) without prematurely truncating to 200 chars.
  2. `bot/attachments.py:AttachmentReaper.sweep`, `_sweep_orphan_items`, and `_scan_root_untracked`:
     - `sweep()` returned `SweepReport(errors=1)` on `list_expired_pending_attachment_batches` failure, discarding prior `errors`/`skipped` counts from steps `(0a)–(0c)`; now increments `report["errors"] += 1` and returns `SweepReport(**report)`.
     - `_sweep_orphan_items` swallowed exceptions from `list_all_attachment_batches` and `list_attachment_items_by_status` and returned `0`, leaving `report["errors"] == 0` so `OpportunisticSweeper` could falsely advance `_last_success_at`; now passes `report` so DB failures increment `report["errors"]`.
     - `_scan_root_untracked` similarly swallowed `OSError` from `root.iterdir()` without incrementing `report["errors"]`; now increments `report["errors"]` when `report` is provided.
  3. `bot/handlers.py:_download_attachment_chunks`: Replaced `file_path[:7] in ("http://", "https:/")` with `file_path.startswith(("http://", "https://"))` so malformed single-slash local paths like `"https:/..."` are not misclassified as URLs.
- **Regression Tests Added (`tests/test_repair_plan_01_review_findings.py` — `NOT RUN`):**
  - `test_extension_of_blocks_trailing_dot_and_control_char_bypass` (**NOT RUN**)
  - `test_reaper_sweep_records_error_when_orphan_item_query_fails` (**NOT RUN**)
  - `test_reaper_sweep_preserves_prior_errors_when_expired_query_fails` (**NOT RUN**)
  - `test_download_chunks_does_not_treat_single_slash_https_as_url` (**NOT RUN**)
- **Plan 02 Implementation Classification Re-Confirmed:** No Plan 02 code change is safely implementable without resolving `B1` (`D-10/D-11`), `B2` (`D-14`), workspace confinement/verification (`D-01..D-06`, `D-24`), schema/outbox reconciliation approval (`D-16`, `D-20..D-22`), governance/quotas/deletion (`D-07`, `D-08`, `D-12`, `D-13`, `D-17`, `D-23`), and mandatory independent security review (`D-19`).

---

## 11. Final Closure Audit & Remediation (`OHB2-FINAL-CLOSURE-PLAN01-PLAN02`, 2026-11-15)

- **Workspace & Git State:** `.git` absent locally -> Git branch/HEAD/remote status **`UNVERIFIED`** (no Git initialization, no commit/push/PR/deploy).
- **Execution Policy Compliance:** Zero tests, linters, security scanners, compilers, or builds executed in this task — every check and test below is explicitly **`NOT RUN`**.
- **Plan 01 Verdict:** **`PLAN01_IMPLEMENTATION_COMPLETE_PENDING_VERIFICATION`** (not `PLAN01_CLOSED` until full automated verification + independent review run).
- **Plan 02 Verdict:** **`PLAN02_INVESTIGATION_AND_DESIGN_CLOSED_REMOTE_DELIVERY_BLOCKED`** (`ZERO_REMOTE_UPLOAD_ITEMS_IMPLEMENTABLE_UNDER_CURRENT_PROVIDER_CONTRACT_AND_OWNER_APPROVALS`).
- **Independent Review Status:** **`INDEPENDENT_REVIEW_NOT_RUN`**.

### 11.1 Final Plan 01 Remediations Completed In Code (`NOT RUN`)

1. **`bot/handlers.py` (`_classify_telegram_file_path` + `_download_attachment_chunks`):**
   - Replaced prefix-only check `file_path.startswith(("http://", "https://"))` with deterministic `urlsplit`-backed URI scheme classification rejecting empty/non-string paths, NUL bytes, whitespace/control chars in URIs, non-`http(s)` URI schemes (`ftp://`, `file://`, `data:`, `javascript:`), and malformed `http(s)` URLs (`https://`, missing host, invalid port, `https:/...`) with `StagingError` before `os.path.isfile` or `client.stream`.
2. **`bot/attachments.py` (`sanitize_display_name`, `extension_of`):**
   - Applied `unicodedata.normalize("NFKC", ...)` + stripping Unicode `C*` category characters (`Cc` ASCII/C1 controls + `Cf` invisible format/zero-width/bidi override characters such as `\u200b`, `\u202e`) before `.strip().rstrip(" .").lower()`, closing extension deny-list bypass mismatches against `bot/web/download.py:safe_download_filename` (`evil.e\u200bxe`, `run.s\u202eh`, `bad.\uff45\uff58\uff45`, `bad.sh\u0085`).
3. **`bot/attachments.py` (`AttachmentReaper.sweep`, `_sweep_orphan_items`, `_count_unsafe_entries`):**
   - Passed `report` to `_count_unsafe_entries(report=report)` so `OSError` on `root.iterdir()` logs a warning and increments `report["errors"] += 1` (preventing false `last_success_at` advancement in `OpportunisticSweeper`).
   - Logged and incremented `report["errors"] += 1` when `self._db.mark_attachment_item_reaped(item.item_id)` raises an exception inside `_sweep_orphan_items`.

### 11.2 Honest Status Classification Matrix

| Category | Exact Scope & Items |
| --- | --- |
| `Implemented` | Plan 01 `FIX-01..FIX-04`, `LIFE-01..LIFE-02`, FD-leak guard, `_effective_cap` DB error mapping, `Content-Encoding` normalization, `extension_of`/`sanitize_display_name` Unicode hardening, `AttachmentReaper` orphan/unsafe error reporting, `_classify_telegram_file_path` fail-closed URL/URI validator (`bot/attachments.py`, `bot/handlers.py`) |
| `Independently reviewed` | **None** — **`INDEPENDENT_REVIEW_NOT_RUN`** (self-audit only; `D-19` open) |
| `Tests added (NOT RUN)` | `tests/test_repair_plan_01_review_findings.py`: `test_extension_of_blocks_unicode_format_c1_and_fullwidth_bypass`, `test_download_chunks_rejects_malformed_urls_and_non_http_schemes`, `test_reaper_sweep_records_errors_on_unsafe_scan_and_orphan_mark_failure` (plus prior 4 & 3 tests in same file — all **`NOT RUN`**) |
| `Automated verification pending` | `python -m pytest -q`, `node --test tests/frontend/*.test.js`, `python -m pyflakes ...`, `python -m bandit ...`, `python -m pip_audit ...`, `python -m compileall`, GitHub Actions `CI` — all **`NOT RUN`** |
| `Provider blocked` (`BLOCKED_BY_PROVIDER`) | Cloud V1 upload route absent (`1.92.0`); Agent Server `X-Session-API-Key` full-privilege bash/secrets exposure (`B1`); absent provider origin allowlist for `conversation_url` (`B2`); absent `stat + sha256` & server-side workspace confinement; `ImageContent` image-only/`data:` unverified; shared `grouped_workspace_dir`; unconfirmed `runtime-api` C2 deletion (`D-08`) |
| `Owner approval pending` (`BLOCKED_BY_OWNER_DECISION`) | 22 unresolved decisions: `D-01..D-08`, `D-10..D-14`, `D-16..D-18`, `D-20..D-24`, including `attachment_items` / `attachment_batches` SQLite schema migration |
| `Architecture forbidden` (`BLOCKED_BY_ARCHITECTURE`) | Second SQLite owner (`I3`), second worker/scheduler/process (`I2`), blind retry after ambiguous upload (`I11`), cross-conversation fallback (`I1`), upload prompt dispatch without text (`I7/I8`), claiming `exactly-once` |
| `Release blocked` (`BLOCKED_BY_RELEASE_GATE`) | **`D-19`** (mandatory independent security review gate before production enablement) |
| `Not implemented` | Plan 02 remote upload client, SSRF/IP-pinned origin transport, SQLite remote-reconciliation columns, `OutboxWorker` remote batch dispatcher, remote `SHA-256` verifier (`MINI_APP_ENABLED=False`, `D-12` quotas `None`, `D-33..D-35` untouched) |

---

## 12. Final Execution, Verification & Closure Reconciliation (`OHB2-FINAL-EXECUTION-AND-CLOSURE-PLAN01-PLAN02`, 2026-11-15)

- **Official Plan 01 Status:** **`PLAN01_IMPLEMENTATION_COMPLETE_PENDING_VERIFICATION`** (upgraded from prior `NOT RUN` state for stdlib/compile/AST checks; **not** `PLAN01_CLOSED` until full CI `pytest`/`pyflakes`/`bandit` and independent review pass).
- **Official Plan 02 Status:** **`PLAN02_INVESTIGATION_AND_DESIGN_CLOSED_REMOTE_DELIVERY_BLOCKED`**.
- **Independent Review Status:** **`INDEPENDENT_REVIEW_NOT_AVAILABLE`** (no separate subagent/reviewer session or tool exists in this execution environment; self-audit only; `D-19` remains open).
- **Git / Workspace State:** `.git` absent locally -> Git branch/HEAD/remote status **`UNVERIFIED`** (no Git initialization, commit, push, PR, or deploy performed).

### 12.1 Final Plan 01 Code & Test Corrections Executed

1. **`bot/handlers.py` (`_classify_telegram_file_path`):**
   - Wrapped `urlsplit(file_path)`, `parts.hostname`, and `parts.port` in `try ... except ValueError` so malformed IPv6 brackets/ports (`"https://[::1/a"`, `"http://["`, invalid ports) raise `StagingError` fail-closed instead of leaking an uncaught `ValueError`.
   - Rejected protocol-relative `"//..."` paths fail-closed with `StagingError` before local file fallback.
2. **`bot/attachments.py` (`_ascii_leaf_projection`, `_is_denied_extension`):**
   - Added multi-form `_is_denied_extension` evaluation across `raw_leaf`, `NFKC`, `NFKD`, and `sanitized` (200-char truncated leaf) plus `[A-Za-z0-9-_.]`-projected leaf matching `bot/web/download.py:safe_download_filename`. Using `NFKD` closes the fullwidth+combining recomposition bypass (`"bad.\uff45\uff58\uff45\u0301"` -> `"bad.exe"` instead of recomposing `"é"` and stripping `"e"`), while preserving benign Unicode names such as `"تقرير_نهائي.txt"`.
3. **`tests/test_repair_plan_01_review_findings.py`:**
   - Fixed a latent `FileNotFoundError` at lines `804` and `884` (`assert not store.root.exists() or list(store.root.iterdir()) == []`), since `(0c)` rejects denied extensions before `ensure_root()` creates `store.root`.
   - Added adversarial test coverage for `"https://[::1/a"`, `"http://["`, `"//evil.example/file"`, combining marks/punctuation/fullwidth+combining/truncation bypasses, and benign `"تقرير_نهائي.txt"` acceptance; removed stale `NOT RUN —` docstring markers.

### 12.2 Executed Verification Ledger (Python 3.10.12 Stdlib-Only Container)

| Check | Result | Details |
| --- | --- | --- |
| `python3 -m compileall -q bot automation tools main.py tests` | **`PASS`** (exit 0) | Clean bytecode compilation across all Python trees |
| `AST parse` (`bot/`, `tests/`, `main.py`) | **`PASS`** (exit 0) | Zero syntax errors (`AST_PARSE_ALL_OK`) |
| Focused stdlib behavioral suite (`7/7` assertion groups) | **`PASS`** (exit 0) | Verified `D-12` `None` quota defaults + `MAX_ATTACHMENT_BYTES=3MiB` + `D-15` `15m` TTL; `13/13` hostile extension/Unicode bypasses `REJECTED_TYPE` + benign `"تقرير_نهائي.txt"` `STORED` (`0700`/`0600`); `os.fdopen` leak guard + clean partial removal; `_effective_cap` DB failure (`DB_FAILED`), explicit batch quota (`FIX-03`), `ensure_staging_root` `chmod` fail-closed (`FIX-04`); `AttachmentReaper` + `OpportunisticSweeper` expiry cleanup, `orphan_mark` error propagation, `iterdir` `OSError` -> `errors >= 1` & `last_success_at is None`; AST-extracted `_classify_telegram_file_path` accepting `5` valid cases and rejecting `16` malformed/non-`http(s)` inputs with `StagingError`; zero `download_to_memory`/`asyncio` in `bot/attachments.py` + `validate_accompanying_text("مرحبا\r\n") == ELIGIBLE` |
| `python -m pytest -q` | **`NOT RUN / BLOCKED`** | Missing runtime/test deps in container: `pytest`, `telegram`, `httpx`, `starlette`, `dotenv` |
| `python -m pyflakes bot/ automation/ tools/ main.py tests/` | **`NOT RUN / BLOCKED`** | `pyflakes` not installed in container |
| `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | **`NOT RUN / BLOCKED`** | `bandit` not installed in container |
| `python -m pip_audit -r requirements-dev.txt` | **`NOT RUN / BLOCKED`** | `pip_audit` not installed / network dependency audit deferred to CI |
| `node --test tests/frontend/*.test.js` | **`SKIPPED`** | Zero frontend files modified |

### 12.3 Reconciled Plan 02 Owner-Decision & Blocker Count (`13 + 21 + 1 = 35`)

- **Reconciled Count (`docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md §13.5` & `docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md §28.7`):**
  - **`13` `OWNER-APPROVED`:** `D-09`, `D-15`, `D-25`..`D-35` (note: §9 D-15 checkbox historically lagged `§4`/`§5 -> D-15`/`§13.1`, reconciled in `§13.5`).
  - **`21` Unresolved Non-Gate Decisions:** `D-01..D-08`, `D-10..D-14`, `D-16..D-18`, `D-20..D-24` (`D-12` Option A defaults `None` batch/total quotas; `D-12` explicit numeric ceiling if ever requested later remains unapproved).
  - **`1` Unresolved Release/Security Gate:** `D-19` (mandatory independent security review before production enablement).
  - **Total:** `13 + 21 + 1 = 35`.
- **Blocker Taxonomy:** Separated cleanly across **`BLOCKED_BY_PROVIDER`** (no Cloud V1 upload route, `X-Session-API-Key` full bash privilege `B1`, unpinned `conversation_url` origin `B2`, no atomic `stat + sha256`, unverified `ImageContent`, shared workspace `grouped_workspace_dir`, unverified `runtime-api` `D-08`), **`BLOCKED_BY_OWNER_DECISION`** (`21` open decisions including `bot/db.py` schema), **`BLOCKED_BY_ARCHITECTURE`** (`I1..I12`), and **`BLOCKED_BY_RELEASE_GATE`** (`D-19`).
