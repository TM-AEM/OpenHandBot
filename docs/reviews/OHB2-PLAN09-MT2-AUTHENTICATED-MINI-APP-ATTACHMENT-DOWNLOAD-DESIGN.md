# OHB2-PLAN09 — MT-2 Authenticated Mini App Attachment Download: Design & Feasibility Investigation

- **Task ID:** `OHB2-PLAN09-MT2-AUTHENTICATED-MINI-APP-ATTACHMENT-DOWNLOAD-DESIGN`.
- **Type:** Architecture investigation, security analysis, and design proposal only. **No
  implementation.** No runtime/frontend/test/schema/config/dependency/deployment file was changed.
- **Selected owner direction:** **MT-2 — Mini App download**, selected for **design investigation
  only** (owner decision doc `docs/decisions/OHB2-OWNER-DECISION-PLAN08-MANUAL-ATTACHMENT-TRANSFER.md`,
  Decision A2). **This is not implementation authorization.**
- **Author:** OpenHands agent (autonomous). Self-review quality only — **not** an independent review.
- **Date:** 2026-11-15 (repository evidence inspected this session).
- **Repo state when written:** branch `main`, HEAD `facf1f42578a20a4a37e220eca016ce3d534e750`
  (= `main` = `origin/main`), divergence `0 0`; working tree holds only pre-existing untracked
  reports and the pre-existing modified `.agent/PROGRESS.md` (see §3).
- **Verdict (see §1):** **`FEASIBLE WITH BLOCKERS — OWNER DECISIONS REQUIRED`**.

> Evidence labels: **[F]** verified against current source this session · **[I]** inference ·
> **[U]** unverified · **[G]** documented-but-untested · **[R]** recommendation ·
> **[OWNER]** owner decision. Every proposed behavior is labelled **PROPOSED — NOT IMPLEMENTED**;
> every Arabic string is labelled **PROPOSED — OWNER COPY APPROVAL REQUIRED**.

---

## 1. Task ID and verdict

**Task ID:** `OHB2-PLAN09-MT2-AUTHENTICATED-MINI-APP-ATTACHMENT-DOWNLOAD-DESIGN`.

**Verdict: `FEASIBLE WITH BLOCKERS — OWNER DECISIONS REQUIRED`.**

Rationale (source-grounded):
- **[F]** MT-2 can reuse the **existing** authenticated session model, the **existing** conversation
  authorization, the **existing** attachment identity, and the **existing** staging layout — **no new
  SQLite owner, no new process/service, no new worker/scheduler, no public URL, no bearer URL, no
  session/token-storage change, and no schema change is required** (§6, §8, §13, §14, §15).
- **[F]** A safe design exists in principle (authenticate → authorize → verify item/batch/expiry →
  open with `O_NOFOLLOW` + containment → bounded streaming) using primitives already present
  (`_guarded` `bot/web/app.py:432`; `_is_within` `bot/attachments.py:284`; `is_safe_workspace_path`
  `bot/files.py:75`; `lstat`; `os.open` `bot/attachments.py:585`).
- **Blockers remain (owner decisions / verification):**
  1. **Real Android 12 Telegram WebView download behavior is `UNVERIFIED`** (§12, §13). A design that
     streams a response is not proof the user can save the file. This must be verified on a real
     device before implementation or activation.
  2. **Cleanup/retrieval race** has no elimination under current architecture; a **minimum invariant**
     is required (bounded open + verify at open + honest failure), and one platform-specific case
     (`[U]` open-fd-after-unlink) must be verified (§11).
  3. **Scope** and **Arabic UX copy** decisions remain open (`[OWNER]`) (§21).
  4. **D-15** (15-minute window / no server batch) must be confirmed as it governs expiry handling
     (§21); **D-16** is **N/A** to MT-2 (idempotent GET); **D-22** is **N/A** to MT-2 (outbox-specific)
     (§21).

**A feasible-design verdict does not authorize implementation.** See §24.

---

## 2. Owner authorization and scope

**Authorized:** study and design only; produce this reviewable design report; append a factual entry
to `.agent/PROGRESS.md`.

**Non-negotiable direction preserved (from the task and the owner decision doc):**
1. MT-2 selected for **design investigation only**; no implementation, no feature changes.
2. No schema/migration changes; `MINI_APP_ENABLED` stays **disabled**; no runtime activation.
3. Reliable provider-verified remote delivery remains the long-term target; best-effort automatic
   remote delivery remains rejected.
4. Local staging must **never** be described as delivery to OpenHands.
5. MT-1 is **not** selected; **D-22 remains unresolved** (and is **not applicable** to MT-2, §21).
6. D-12/D-15/D-16 remain within their recorded scope.
7. Secure Pull remains **NOT IMPLEMENTED**; remote Stage **B1/B2/B3** **NOT AUTHORIZED**;
   Plan **07-B/07-C NOT AUTHORIZED**.

**Non-scope:** any code/schema/config change; any new endpoint actually registered; any change to
polling/acknowledgement/`concurrent_updates(True)`; any remote-delivery work.

---

## 3. Git baseline

Independently measured this session:

| Item | Value |
| --- | --- |
| Branch | `main` |
| HEAD / `main` / `origin/main` | `facf1f42578a20a4a37e220eca016ce3d534e750` |
| Divergence (`origin/main...HEAD`) | `0  0` |
| Staged | none |
| Unstaged (pre-existing) | `.agent/PROGRESS.md` (` M`) |
| Untracked (pre-existing) | `docs/decisions/OHB2-OWNER-DECISION-PLAN08-MANUAL-ATTACHMENT-TRANSFER.md` and 6 Plan 05/06/07-A/07-A2/08 review docs |
| Ignored (relevant) | `.openhands/` (mtime `2026-11-14 16:27:11`, untouched), `.pytest_cache/` |
| `MINI_APP_ENABLED` | `False` (`bot/config.py:262`) |
| `concurrent_updates(True)` | present (`bot/app.py:86`) |
| Polling | custom `bot.polling` loop, `updater(None)` (`bot/app.py:75–86`) |
| SQLite ownership | one `Database` object shared by bot + web (`bot/app.py:349`; `bot/web/app.py:118`) |
| Autopush | inactive (no `autopush`/`main.py` process) |

Pre-existing modified/untracked files were **preserved untouched**.

---

## 4. Evidence set inspected

1. `AGENTS.md`; 2. `.agent/PROGRESS.md`; 3. owner decision doc
`docs/decisions/OHB2-OWNER-DECISION-PLAN08-MANUAL-ATTACHMENT-TRANSFER.md`;
4. corrected Plan 08 `docs/reviews/OHB2-PLAN-08-MANUAL-ATTACHMENT-TRANSFER-UX-DESIGN.md`;
5. first Plan 08 review `docs/reviews/OHB2-REVIEW-PLAN08-MANUAL-ATTACHMENT-TRANSFER-UX-DESIGN.md`;
6. second review `docs/reviews/OHB2-REVIEW-PLAN08-DESIGN-REMEDIATION.md`; 7–10. Plan 05/06/07-A/07-A2;
11. register `docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md` (D-12/D-15/D-16/D-22; I2/I3);
12. `docs/MINI_APP.md`; 13. source `bot/attachments.py`, `bot/db.py`, `bot/files.py`,
`bot/handlers.py`, `bot/sender.py`, `bot/outbox.py`, `bot/app.py`, `bot/config.py`,
`bot/web/app.py`, `bot/web/services.py`, `bot/web/sessions.py`, `bot/web/initdata.py`,
`bot/web/ratelimit.py`, `bot/web/static/*.js`, `bot/web/static/index.html`; 14. tests
`tests/test_real_http_miniapp_download.py`, `tests/test_miniapp_http_journeys.py`,
`tests/test_miniapp_export_reply.py`, `tests/test_miniapp_session_persistence.py`,
`tests/test_miniapp_initdata.py`, `tests/test_a2_export_auth.py`, `tests/test_attachment_staging_a1.py`,
`tests/test_attachment_cleanup_expiration_a4.py`, `tests/frontend/*.test.js`.

All material claims were re-verified against **current source**; no design claim was copied
unverified.

---

## 5. Current attachment lifecycle (verified)

| Stage | Behavior | Evidence |
| --- | --- | --- |
| Intake filter | `filters.Document.ALL` → `handle_attachment` | `bot/app.py:34`, `:157–161`; `bot/handlers.py:1818` |
| Authorization | allowed user + private chat; conversation ownership | `bot/handlers.py:53`, `:234`; `bot/attachments.py:815` |
| Hard cap | `MAX_ATTACHMENT_BYTES = 3 * 1024 * 1024` (**3 MiB = 3 145 728 B**) | `bot/attachments.py:99`; enforced `bot/handlers.py:1878` |
| Deny lists | extension + magic-byte reject | `bot/attachments.py:120–148`, `:316–320` |
| Staging dir | `<db_dir>/attachment_staging/`, mode `0700` | `bot/attachments.py:108–110`, `:204` |
| Staging file | opaque `token_hex(16)` name, mode `0600`, `O_EXCL` + `O_NOFOLLOW` | `bot/attachments.py:111`, `:199`, `:585` |
| DB row | item `pending` → `stored` (atomic CAS) | `bot/db.py:1224` |
| Item fields | `item_id, batch_id, staging_token, display_name, size_bytes, status` | `bot/db.py:532–546`, `:786–792` |
| Batch | `telegram_id, conversation_id, t0, status` (client-side, no `expires_at`) | `bot/db.py:490–503`, `:769–777` |
| Expiry | `ATTACHMENT_BATCH_TTL = 15 min` from `t0` | `bot/db.py:261` |
| Cleanup | DB-first reaper; marks `expired`/`reaped` then unlinks | `bot/attachments.py:1020`, `:1122`, `:1316` |
| Cleanup trigger | existing watcher tick (`interval=25s`) via `OpportunisticSweeper` | `bot/app.py:227–241`; `bot/watcher.py:66`, `:182–183` |
| Retrieval | **none** — no route/handler reads `attachment_staging/` | repo-wide grep = none |
| Remote delivery | **none** — `delivered` never written | `bot/db.py:121–137` (constants only) |

**Event distinctions (unchanged from Plan 08 §3.7):** received ≠ staged locally ≠ retrievable ≠ sent
via Telegram ≠ uploaded to OpenHands ≠ independently verified remote delivery. Only *received* and
*staged locally* are implemented.

---

## 6. Authentication and authorization model

### 6.1 Mini App authentication (verified)
- **Session creation:** `POST /api/v1/auth` validates Telegram `initData` server-side
  (`validate_init_data`, HMAC-SHA256 with `secret = HMAC("WebAppData", bot_token)`, `auth_date`
  freshness `DEFAULT_MAX_AGE=300s`), then creates a session bound to the **Telegram user id**
  (`bot/web/initdata.py:53–58`, `:68–142`; `bot/web/app.py:494–530`).
- **Session storage:** `web_sessions(token_hash PK, user_id, created_at, expires_at, profile)` — the
  **raw token is never stored**, only SHA-256 (`bot/web/sessions.py:30–35`; `bot/db.py:732–740`).
- **Cookie:** `ohb_session`, `HttpOnly`, `Secure` (default `True`), `SameSite=Strict`, `path=/`
  (`bot/web/app.py:206–215`; `bot/config.py:27`, `:294`).
- **Session TTL:** `MINI_APP_SESSION_TTL=3600s` default (`bot/config.py:26`, `:292`).
- **Validation on every request:** `_guarded` → rate-limit → session lookup (expired rejected
  fail-closed) → `_allowed(user_id)` (allowlist) → Origin for state-changing
  (`bot/web/app.py:432–451`; `bot/db.py:2546–2558`).
- **[F]** Session `user_id` is the **Telegram** id; `_allowed` checks `allowed_telegram_ids`
  (`bot/config.py:59–60`). Conversation ownership is a **separate** check (§6.2).
- **Revocation:** `revoke` deletes the row (persists across restart) (`bot/web/sessions.py:122–140`).

### 6.2 Conversation and attachment authorization (verified)
- **Conversation ownership:** `authorize_conversation_detailed` calls `/users/me` and requires
  `created_by_user_id == owner` (fail-closed); plus a local deletion witness
  (`bot/files.py:220–266`; `bot/web/services.py:375–399`).
- **Attachment identity:** `attachment_batches(telegram_id, conversation_id, batch_id)` and
  `attachment_items(item_id, batch_id, staging_token, display_name, size_bytes, status)`
  (`bot/db.py:769–792`). Index `idx_attachment_batches_owner(telegram_id, conversation_id)`
  (`bot/db.py:779–781`).
- **Lookup helpers:** `get_attachment_item(item_id, batch_id=…)`, `get_attachment_batch(batch_id,
  telegram_id=…)`, `list_attachment_items(batch_id)` (`bot/db.py:1716–1732`, `:1112–1128`, `:1179`).
- **[F]** An attachment can be resolved by opaque `item_id` **with ownership enforced** because the
  batch row carries `telegram_id` and `conversation_id`, and item→batch is by `batch_id`.
- **IDOR/cross-conversation paths:** the item row itself has **no** `telegram_id`; authorization must
  therefore resolve **item → batch → (telegram_id, conversation_id)** and compare against the
  authenticated session principal and the conversation-ownership result. A design that trusts a
  client-supplied item id alone would be an IDOR; the design must bind item to batch to owner (§8).

### 6.3 Is the existing session sufficient for a future download request?
**[F] Yes, structurally** — the session is bound to a server-side principal and validated on every
request. **[F] But** an authenticated page does **not** automatically secure a new route: the new
route must call `_guarded` and perform the attachment-specific authorization itself (§8).

---

## 7. Current file-service and path protections

| Primitive | Location | What it guarantees | What it does **not** guarantee |
| --- | --- | --- | --- |
| `_attachment(data, filename)` | `bot/web/app.py:95–108` | Safe `Content-Disposition` filename (ASCII allowlist), explicit `Content-Length`, security headers | Buffers **all** bytes in memory; **no** streaming; **no** `Range`/206 |
| `_is_within(root, path)` | `bot/attachments.py:284–287` | `realpath` containment under root | Does **not** prevent TOCTOU between check and open; follows `realpath` (symlink resolution) |
| `is_safe_workspace_path` | `bot/files.py:75–92` | Single relative segment, no `/`/`\`/control/`..`, normalized | Only validates the string, not the filesystem |
| `lstat` checks | `bot/attachments.py:1316–1370` | Detects symlink / non-regular entry (no follow) | Does **not** stop replacement after the check |
| `os.open` with `O_EXCL` + `O_NOFOLLOW` | `bot/attachments.py:585–589` | Write-time: no overwrite, no symlink follow | Not used by any read path today |
| Directory mode `0700` / file `0600` | `bot/attachments.py:109–110` | Only the process user can read staging | Not a substitute for per-request authorization |

**[F] No current code path returns staged file bytes.** No `StreamingResponse`/`FileResponse` is used
anywhere in `bot/` (grep). **[F] No `Range`/206** support exists in `bot/web/`. **[F]** `lstat` or
`_is_within` alone is **not** claimed to guarantee safe access — a read path must combine
authorization + containment + `O_NOFOLLOW` + metadata verification (§9).

---

## 8. Proposed MT-2 user journey (PROPOSED — NOT IMPLEMENTED)

| # | Step | Implementation status | Required authorization | Possible failure | User-visible outcome | Independently observable? |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Open authenticated Mini App session | **EXISTING** (`auth`) | initData | invalid initData | 401 | Server: yes |
| 2 | View the conversation | **EXISTING** (`/conversations/{id}`) | session + ownership | 403/404 | error | Server: yes |
| 3 | See an attachment **confirmed staged** (`stored`) | **PROPOSED** (list UI for staged items) | session + ownership | none staged | empty state | Server: yes |
| 4 | Request the download | **PROPOSED** (new route + UI) | session | 401 | error | Server: yes |
| 5 | Server authenticates session | **EXISTING** (`_guarded`) | session cookie | 401 | error | Server: yes |
| 6 | Server verifies conversation ownership | **EXISTING** (`authorize_conversation`) | ownership | 403/404 | error | Server: yes |
| 7 | Server verifies item→batch→conversation | **PROPOSED** (new check) | item/batch identity | 404 | error | Server: yes |
| 8 | Server verifies staging metadata + expiry | **PROPOSED** (new check) | `status='stored'`, `t0+15m > now` | 410/404 | error | Server: yes |
| 9 | Server safely opens the staged file | **PROPOSED** (`O_NOFOLLOW` + containment) | — | ENOENT/EACCES | error | Server: yes |
| 10 | Server streams with bounded reads | **PROPOSED** (streaming + cap) | — | read error | partial/error | Server: yes |
| 11 | Client receives the response | **PROPOSED** | — | disconnect | unknown | **Client only** |
| 12 | User saves/opens the file on Android | **PROPOSED / `[U]`** | — | WebView blocks download | `[U]` | **No (server cannot observe)** |

**[F]** Steps 5–10 are server-observable. **[F]** Step 11 (client received) and step 12 (user saved)
are **not** server-observable and must **not** be claimed as success. **[F]** A completed HTTP
response is **not** proof the user saved the file, and **never** proof of OpenHands upload.

---

## 9. Proposed endpoint contract (PROPOSED — NOT IMPLEMENTED)

**Route (proposed):** `GET /api/v1/conversations/{conversation_id}/attachments/{item_id}/download`.

- **Method — `GET`:** read-only, idempotent, no body; consistent with existing read routes
  (`…/export`, `…/file`). **[R]** `GET` chosen for idempotent download semantics.
- **Path parameters:** `conversation_id` (validated by `is_valid_conversation_id`) and `item_id`
  (opaque). **No** filesystem path and **no** `staging_token` is accepted from the client.

**Authentication:** require the existing session via `_guarded(request, state_changing=False)`;
reject missing/expired/revoked sessions (401); reject non-allowlisted users (403). **[F]** Never
accept a client-supplied user id as identity.

**Authorization (every request):**
1. `authorize_conversation(conversation_id)` → 403/404 on failure (reuse).
2. `get_attachment_item(item_id)` → must exist and its `batch_id` must resolve to a batch whose
   `conversation_id == conversation_id` **and** `telegram_id == session.user_id`; otherwise **404**
   (do not distinguish "not yours" from "not found").
3. Item must be `status='stored'` and the batch `status='pending'` with `t0 + 15m > now`; otherwise
   **410** (expired) or **404** (missing/reaped).

**Identifier design:** **[F]** the existing opaque `item_id` (`token_hex(16)`) is suitable; the
`staging_token` is a **server-side-only** reference and must **not** be exposed. **[F] No new bearer
secret, no token-storage change, and no new identifier type is required.**

**HTTP behavior:**
- `Content-Type`: the file's type is not stored today; **[R]** `application/octet-stream` (safe,
  non-sniffed via `X-Content-Type-Options: nosniff`).
- `Content-Disposition: attachment; filename="<safe>"` where `<safe>` is derived from the stored
  `display_name` and filtered through the existing ASCII allowlist (`_HEADER_SAFE_NAME`).
- `Content-Length`: the verified `size_bytes`.
- Cache: `Cache-Control: no-store` (+ existing `_SECURITY_HEADERS`).
- `Range`/206: **[R] excluded from the initial design** (no current support; adds complexity and
  race surface). If added later, it requires its own design/verification.
- `HEAD`: **[R] not required initially**; `GET` is sufficient. If added, it must run the same
  authorization.
- Errors: JSON `_error(status, code, message)` consistent with existing routes; **no** internal path
  or token in body or logs.

**Origin/CSRF:** **[F]** the cookie is `SameSite=Strict`; the app and API are **same-origin**
(`docs/MINI_APP.md:178–190`). **[F]** `_guarded` applies the Origin check only to state-changing
requests (`state_changing=True`); a `GET` download is read-only and does not require it. **[F]**
`SameSite=Strict` is the primary CSRF defense for this pattern; the design must **not** weaken it and
must **not** introduce a public/bearer URL.

---

## 10. Safe file opening and bounded streaming design (PROPOSED — NOT IMPLEMENTED)

**Order of operations (proposed):**
1. Authenticate (`_guarded`) and authorize (§9) — **before** touching the filesystem.
2. Resolve the on-disk path as `staging_root / staging_token` with `staging_token` validated by
   `is_safe_workspace_path` and `_is_within(root, path)`.
3. Open with `os.open(path, os.O_RDONLY | os.O_NOFOLLOW)`; on any error → clean failure.
4. `fstat` the fd and require a regular file; compare `st_size` to `size_bytes`; reject on mismatch.
5. Stream in bounded chunks (e.g. 64 KiB) with `StreamingResponse` (available in Starlette 1.3.1).
6. Close the fd in a `finally` (including on client disconnect / exception).

**Guarantees vs non-guarantees (explicit):**
- Directory/file permissions: **only** the process user can read staging — **not** an authorization
  substitute.
- `_is_within` + `O_NOFOLLOW`: prevent traversal and symlink substitution **at open time**.
- `fstat` + size check: detect replacement/shortening between lookup and open.
- SQLite ownership: establishes **which** attachment the user may read — **not** a file-integrity
  guarantee.
- **[F]** These mechanisms **do not eliminate** a TOCTOU race where the reaper unlinks the file
  between the DB check and the `open`. §11 defines the minimum invariant.

**Do not** introduce a new worker/scheduler/SQLite owner as a workaround. **[F]** `StreamingResponse`
is importable from the installed `starlette==1.3.1` (verified) and is compatible with the existing
ASGI stack.

---

## 11. Expiry and cleanup race analysis

**[F] Existing behavior:** the reaper is DB-first (marks batch `expired`, item `reaped` via CAS,
**then** unlinks; `absent` is idempotent) and runs on the existing watcher tick
(`bot/attachments.py:1020–1138`, `:1122–1200`, `:1316–1370`; `bot/app.py:227–241`). **No retrieval
path exists today**, so **every case below is currently unreachable** (future risk).

Legend: **Reachable?** N = not reachable today (no retrieval) · **Y-future** = reachable only if
MT-2 is implemented.

| # | Case | Current behavior | Reachable? | Partial bytes possible? | Misleading result? | Coordination needed? | Schema/arch decision? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Request just before expiry | reaper may expire concurrently | Y-future | no (if rejected pre-open) | no if 410 | reject expired before open | no |
| 2 | Expiry after auth, before open | reaper unlinks | Y-future | no | no if open fails cleanly | re-verify at open | no |
| 3 | Cleanup between lookup and open | `open` → `ENOENT` | Y-future | no | no | bounded open | no |
| 4 | Cleanup while streaming | reaper unlinks an open fd | Y-future | **yes (POSIX)** `[U]` | must not report success on truncation | verify size; detect short read | no |
| 5 | Process crash during streaming | no durable retrieval record | Y-future | n/a | client sees incomplete | none (nothing durable) | no |
| 6 | File disappears before headers | open fails | Y-future | no | clean 404/410 | open before headers | no |
| 7 | File disappears after headers | stream errors mid-body | Y-future | **yes** | must not claim success | abort on read error | no |
| 8 | Client disconnect/reconnect | new GET is idempotent | Y-future | no | no | idempotent GET | no |
| 9 | Multiple downloads, one attachment | each GET independent | Y-future | no | no | idempotent GET | no |
| 10 | Concurrent cleanup + retrieval | CAS on `reaped`; unlink race | Y-future | **yes (case 4)** | must be honest | bounded open + verify | no |

**Minimum required invariant (proposed):** *authorize → verify item/batch/expiry → open with
`O_NOFOLLOW` → `fstat`/size check → bounded stream → honest failure on any error.* Expiry is checked
**before** open; a file that vanishes mid-stream yields an **aborted** response, never a claimed
success.

**Not claimed:** **[F]** an open fd does **not** automatically provide all lifecycle guarantees
across every platform (case 4/9 POSIX semantics are `[U]`); restrictive permissions do **not** solve
the race. **[F] No new lifecycle state is invented**; coordination uses the existing DB-first reaper.

---

## 12. Android 12 / Telegram WebView feasibility

- **[F]** The app is designed for the Telegram client WebView / Telegram Web (`docs/MINI_APP.md:178–190`);
  `MINI_APP_ENABLED=False` by default and requires a public HTTPS `MINI_APP_URL` if enabled
  (`bot/config.py:242–266`).
- **[F]** The only Blob-download exercise is the Node DOM stub (`tests/frontend/dom_stub.js:336–342`);
  it is **not** evidence of real Telegram WebView behavior.
- **[F]** The existing export button uses a `fetch → blob → objectURL → <a download>` pattern
  (`bot/web/static/app.js:1031–1061`) — **[U]** whether this works in Telegram Android WebView is
  **unverified**.
- **[U]** Desktop/Chromium testing is **not** sufficient for Android 12.
- **[U]** A successful HTTP response is **not** proof the user can locate the saved file.

**Status: real-device behavior = `UNVERIFIED`.** §13 defines the verification plan.

---

## 13. Manual real-device verification plan (NOT PERFORMED)

Environment: a real **Android 12** device with the official **Telegram** app, `MINI_APP_ENABLED=1`
with a public HTTPS `MINI_APP_URL`, a bot instance reachable from the device, and an allowlisted
owner account. **Not performed in this task** (would require activation + deployment).

For every test: **Evidence to capture** = screen recording/screenshot + app/server logs (no secrets)
+ file hash where applicable.

| # | Test | Preconditions | Steps | Expected | Failure criteria | Mandatory before implementation? |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Small valid file | staged item `stored` | tap download | file downloads; correct bytes | no download / corrupt | **Yes** |
| 2 | Near max (3 MiB) | staged item `stored` | tap download | file downloads; correct size | truncation | **Yes** |
| 3 | Filename/extension | staged item with known name | tap download | saved name = safe filename, correct ext | wrong/missing ext | Yes |
| 4 | Content integrity | known content | download, compare SHA-256 | hashes match | mismatch | **Yes** |
| 5 | Progress/feedback | any file | observe UI | some progress/feedback | silent hang | Yes |
| 6 | Save location | any file | find file on device | file discoverable | cannot locate | **Yes** |
| 7 | Open/share saved file | saved file | open/share | opens/shares | fails | Yes |
| 8 | WebView blocks download | any file | tap download | defined failure surfaced honestly | silent no-op | **Yes** |
| 9 | Expired session | session expired | tap download | 401 → re-auth prompt | wrong success | Yes |
| 10 | Expired attachment | past 15 min | tap download | 410/404 honest message | false availability | Yes |
| 11 | Unauthorized conversation | other user's conv | craft request | 403/404, no data | data leak | **Yes** |
| 12 | Invalid item id | random id | request | 404 | leak/existence oracle | Yes |
| 13 | Network interruption | any file | interrupt mid-download | incomplete → retry guidance | false success | Yes |
| 14 | Repeated download | same item | tap twice | both idempotent | error/dup | Yes |
| 15 | Storage exhaustion | full storage | download | honest write failure | false success | Best-effort |
| 16 | Backgrounding during transfer | any file | background app mid-download | defined behavior | crash/false success | Yes |

**This task is design only.** It is expected to produce the plan rather than claim verification
passed. **[F] No real-device test was performed.**

---

## 14. Weak-network and usability analysis

- **[U]** Slow connections: streaming with bounded reads avoids buffering the whole file server-side;
  client-side behavior is `[U]`.
- **[F]** Client retries: a repeated `GET` is idempotent (no durable state) — safe by design.
- **[F]** Memory: streaming avoids `_attachment`'s full buffering; per-request memory is bounded by
  the chunk size.
- **[F]** File descriptors: one fd per active download; closed in `finally`; **[R]** a per-session
  concurrency bound should be considered (reuse the existing rate-limiter, `bot/web/ratelimit.py`) —
  **owner decision**, not implemented.
- **[F]** Server connection lifetime: bounded by the stream duration; the existing ASGI server
  (`uvicorn`) handles it.
- **[U]** Session expiry mid-transfer: the session is validated at request start; behavior if it
  expires mid-stream is `[U]` (the response may still complete).
- **[U]** Download destination discoverability and Android storage handling: `[U]`.
- **[F]** Accessibility/RTL: the Mini App is Arabic RTL; new UI must follow existing patterns
  (labelled **PROPOSED**, §19).

---

## 15. Data-model and schema impact

Explicit answers:
- **New table required?** **No.**
- **New column required?** **No.**
- **New lifecycle state required?** **No** (reads existing `stored`/`pending`/`expired`).
- **New token required?** **No** (reuses opaque `item_id`).
- **New secret required?** **No.**
- **Can existing identity/ownership be reused safely?** **Yes** (item → batch → `telegram_id` +
  `conversation_id`).
- **Can cleanup coordination be achieved without schema changes?** **Yes** — the existing DB-first
  reaper plus the §11 invariant suffice; no new state is needed.
- **Unrepresentable invariant?** **[F] None identified** for MT-2.

**[F]** The absence of a schema change does **not** mean there is no architectural impact: the
impact is a **new route + frontend + a documented cleanup invariant**, all within existing
architecture. **[F] No schema change is approved by this document.**

---

## 16. Architecture compatibility

| Constraint | Status under the proposed design |
| --- | --- |
| One Bot + ASGI process | **COMPATIBLE** (route added to the existing `MiniApp`) |
| One authoritative SQLite owner | **COMPATIBLE** (reads the shared `Database`) |
| Existing outbox/workers only | **COMPATIBLE** (no outbox use) |
| Existing polling/acknowledgement | **COMPATIBLE** (unchanged) |
| `concurrent_updates(True)` | **COMPATIBLE** (unchanged) |
| No new scheduler/worker/process/service | **COMPATIBLE** |
| No second SQLite owner | **COMPATIBLE** |
| No exactly-once claims | **COMPATIBLE** (idempotent GET; none claimed) |
| No public attachment endpoint / bearer URL | **COMPATIBLE** (session-cookie only) |
| No production credentials/secrets | **COMPATIBLE** |
| No remote attachment delivery | **COMPATIBLE** (none) |
| No F4 token-schema change | **COMPATIBLE** (none) |
| No session-schema/token-storage change | **COMPATIBLE** (reuses existing sessions) |

**No proposal here violates a constraint.** Any deviation would be **NOT COMPATIBLE** without
separate owner approval.

---

## 17. Threat model

| # | Threat | Asset | Attacker capability | Attack path | Existing mitigation | Proposed mitigation | Residual risk | Required test | Present today? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T1 | Cross-user access | staged bytes | authenticated other user | guess/steal another user's `item_id` | batch `telegram_id` | item→batch→`telegram_id==session.user_id` → 404 | low | test 11/12 | **introduced by feature** |
| T2 | Cross-conversation access | staged bytes | authenticated user | `item_id` from another conversation | batch `conversation_id` | compare batch `conversation_id` | low | test 11 | introduced |
| T3 | Session theft/expiry | session | token theft | reuse cookie | `HttpOnly`/`Secure`/`SameSite=Strict`; server-side expiry | reject expired; revoke on non-allowlist | low | test 9 | existing |
| T4 | CSRF/origin confusion | data/actions | cross-site page | force a request | `SameSite=Strict`; Origin for state-changing | GET read-only; keep `SameSite=Strict` | low | manual | existing |
| T5 | IDOR | staged bytes | authenticated user | tamper `item_id`/`conversation_id` | none yet (no route) | full item→batch→owner check every request | low | test 11/12 | introduced |
| T6 | Path traversal | filesystem | authenticated user | inject path in params | `is_safe_workspace_path`; `_is_within` | accept only opaque ids; server derives path | low | unit | introduced |
| T7 | Symlink attack | filesystem | local attacker | place symlink in staging | `O_NOFOLLOW` at write; `lstat` guards | `O_NOFOLLOW` at read; `lstat` verify | low | unit | introduced |
| T8 | File replacement | staged bytes | local attacker | swap file after check | none at read | `fstat`+size verify at open | low-medium | unit | introduced |
| T9 | Cleanup/retrieval race | staged bytes | timing | race reaper | DB-first reaper | §11 invariant; honest failure | medium | test 13/16 | introduced |
| T10 | Error info disclosure | internal details | any | read errors | generic messages; no path in responses | keep generic; no path/token in logs | low | unit | introduced |
| T11 | Filename/header injection | response headers | attacker-supplied name | inject CR/LF in `display_name` | `_HEADER_SAFE_NAME` allowlist | reuse allowlist | low | unit | introduced |
| T12 | Resource exhaustion | server | many requests | many concurrent downloads | rate-limiter | **consider** per-session bound | medium | load | introduced |
| T13 | Slow-client exhaustion | server | slow reader | hold connection | uvicorn limits | bounded chunking; **[OWNER]** policy | medium | load | introduced |
| T14 | Unauthorized caching | staged bytes | shared cache | cache response | `Cache-Control: no-store` | keep `no-store` | low | manual | introduced |
| T15 | Download URL leakage | URL | referrer/logs | share URL | `Referrer-Policy: no-referrer`; `no-store` | opaque ids; no token in URL | low | manual | introduced |
| T16 | Log leakage | logs | log access | tokens/paths logged | structured logs w/o secrets | never log token/path/name | low | review | introduced |

**[F]** T3/T4 are **existing** properties; the rest are **introduced by the proposed feature** and
are **not** current vulnerabilities (no retrieval path exists today).

---

## 18. Failure and observability model

| Event | Server-observable? | Proposed user-visible outcome | Notes |
| --- | --- | --- | --- |
| Invalid/expired session | Yes | 401 → re-auth | no details |
| Unauthorized conversation | Yes | 403/404 | 404 does not reveal existence |
| Missing attachment | Yes | 404 | generic |
| Expired attachment | Yes | 410 | no "still available" claim |
| File missing from staging | Yes | 404/410 | clean failure |
| Integrity mismatch (size) | Yes | 502/500 | generic |
| Unsupported type | Yes | **n/a** (intake already denies) | intake deny lists |
| Streaming failure | Yes | aborted response | never claim success |
| Client disconnect | No | (client-side) | server sees disconnect |
| Server resource limit | Yes | 429/503 | reuse limiter |
| Unknown completion (client) | **No** | `[U]` | must not be claimed |

**Event ladder (only these are claimable):** server authorized download · server opened the staged
file · server completed streaming · (**client received** — client-only) · (**user saved** —
unobservable) · (**user uploaded to OpenHands** — unobservable) · (**remote delivery verified** —
not reachable). **[F] No new DB state; user-side saving is not observable.**

---

## 19. Proposed Arabic RTL UX (PROPOSED — NOT IMPLEMENTED / OWNER COPY APPROVAL REQUIRED)

All elements **PROPOSED — NOT IMPLEMENTED**. All strings **PROPOSED — OWNER COPY APPROVAL REQUIRED**.

| # | Trigger | Status | Arabic copy | Explicitly does NOT claim |
| --- | --- | --- | --- | --- |
| U1 | Staged attachment ready for local download | PROPOSED — NOT IMPLEMENTED | `📎 الملف جاهز للتنزيل من هنا.` `⚠️ ده تخزين محلي عندنا، مش تسليم لـ OpenHands.` | Not delivered to OpenHands |
| U2 | Download starting | PROPOSED — NOT IMPLEMENTED | `⏳ بيتم تجهيز الملف للتنزيل…` | No completion |
| U3 | Download in progress/waiting | PROPOSED — NOT IMPLEMENTED | `⏳ التنزيل شغّال…` | No completion |
| U4 | Server completed the response | PROPOSED — NOT IMPLEMENTED | `✅ خلّصنا إرسال الملف للمتصفّح.` `⚠️ ده مش معناه إن OpenHands استلمه — لازم ترفعه بنفسك.` | Not upload |
| U5 | Session expired | PROPOSED — NOT IMPLEMENTED | `🔒 الجلسة انتهت. سجّل دخول تاني وجرّب.` | — |
| U6 | Attachment expired | PROPOSED — NOT IMPLEMENTED | `⌛ الملف المحلي مش متاح (انتهت الـ 15 دقيقة). ابعت الملف تاني لو محتاجه.` | Not "still available" |
| U7 | File unavailable | PROPOSED — NOT IMPLEMENTED | `⚠️ الملف مش متاح دلوقتي. جرّب تاني.` | No false availability |
| U8 | Network interruption | PROPOSED — NOT IMPLEMENTED | `⚠️ التنزيل اتقطع. جرّب تاني.` | No success |
| U9 | Retry guidance | PROPOSED — NOT IMPLEMENTED | `لو استمرّت المشكلة، ابعت الملف من جديد.` | — |
| U10 | Not-delivered statement | PROPOSED — NOT IMPLEMENTED | `🔔 OpenHandBot مايقدرش يتأكد إنك رفعت الملف لـ OpenHands. التأكيد لازم يكون منك جوه OpenHands.` | No independent verification |

**[F]** No message implies remote delivery; no message claims the file remains available after
expiration; no button is presented as currently implemented.

---

## 20. Alternative MT-2 delivery approaches

| Approach | Auth | Authz | File exposure | Memory | Streaming | Android WebView | Filename | Large file | Session expiry | Cleanup races | Op. complexity | Testability | Arch impact |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A. Direct authenticated streaming response (new route + `StreamingResponse`) | existing session | existing ownership + item/batch check | session-only, no URL token | bounded | **yes** | `[U]` | `Content-Disposition` | bounded | validated at start | §11 invariant | low | backend + frontend + real device | low |
| B. Short-lived server-side retrieval operation tied to session | existing session | existing ownership | session-only | bounded | yes | `[U]` | same | bounded | needs durable op + expiry coordination | needs new state | **medium** | backend + crash tests | **medium** (new durable state — likely schema) |
| C. Browser-managed download vs controlled fetch/blob flow | existing session | existing ownership | session-only | `[U]` (blob buffers client-side) | depends | `[U]` | `[U]` | `[U]` | `[U]` | same | low | frontend + real device | low |

- **[F]** Approach A reuses `_guarded` + ownership + `StreamingResponse` and needs **no** schema/new
  state.
- **[F]** Approach B would introduce a durable retrieval operation ⇒ **new state** ⇒ likely a
  **schema** decision (owner); **[F]** it is **not** required to satisfy the design and is **not
  selected**.
- **[U]** Approach C's blob behavior in Telegram WebView is **unverified**; `a.download` support is
  `[U]`.
- **No approach is selected.** **[F]** The evidence required to choose between A and C is exactly the
  §13 real-device tests (does WebView honor `Content-Disposition` directly, or is a fetch/blob flow
  required?). **[R]** Approach A is the smallest-surface candidate, but **no winner is declared**.

---

## 21. Owner decision matrix

| Item | Evidence | Decision needed | Blocking stage | Consequence if unresolved |
| --- | --- | --- | --- | --- |
| Existing session sufficient? | `_guarded`, `web_sessions`, cookie (`bot/web/app.py:432`, `:206`; `bot/db.py:732`) | confirm reuse | design | cannot proceed |
| Current attachment identity sufficient? | item→batch→owner (`bot/db.py:769–792`) | confirm reuse | design | IDOR risk |
| Cleanup coordination w/o schema? | DB-first reaper + §11 invariant | confirm invariant | design/implementation | race mishandled |
| Response compatible with ASGI stack? | `StreamingResponse` in Starlette 1.3.1 **[F]** | confirm streaming approach | design | must buffer (unbounded) |
| New route acceptable? | existing routes pattern (`bot/web/app.py:300+`) | approve route addition | implementation | no download |
| New schema/lifecycle required? | **[F] no** | confirm none | — | — |
| Token-storage change required? | **[F] no** | confirm none | — | — |
| Android 12 Telegram WebView passes? | §13 plan (`[U]` today) | run §13 tests | **implementation/activation** | MT-2 stays `UNVERIFIED` |
| Arabic UX copy approved? | §19 | approve/revise/defer | implementation | copy blocked |
| Future implementation authorized? | this doc | separate authorization | implementation | cannot implement |
| **D-15** (15-min window/no server batch) | `bot/db.py:261`; register `:161` | confirm window handling | design | expiry handling unstable |
| **D-16** (idempotency) | register `:162` | **N/A to MT-2** (idempotent GET) | — | — |
| **D-22** (outbox) | register `:1042–1060` | **N/A to MT-2** (outbox-specific) | — | — |
| **D-12** (quota policy) | `bot/attachments.py:105–106`; register `:158` | policy (UX/bounds) | wording | limits unset |

**No owner decision is resolved here.** D-22 is **not applicable** to MT-2 (MT-2 needs no outbox
change); D-16 is **N/A** (idempotent GET); D-15 governs expiry handling and must be confirmed;
D-12 shapes wording/bounds.

---

## 22. Remaining risks and prerequisites

**Prerequisites before implementation:**
1. §13 real-device verification passed (or an owner-accepted alternative).
2. §11 cleanup invariant accepted (bounded open + verify + honest failure).
3. Scope + Arabic copy decisions (`[OWNER]`).
4. D-15 confirmed.
5. Separate implementation authorization.

**Residual risks:** T9 (cleanup race — medium), T12/T13 (resource/slow-client — medium), T8 (file
replacement — low-medium), all WebView/Android `[U]` items.

**Evidence gaps:** real Telegram Android WebView download support; download destination discovery;
mid-stream session expiry; open-fd-after-unlink semantics on the target platform.

---

## 23. Exact implementation boundary

**If** (and only if) the owner later authorizes implementation, the boundary would be:
- **New backend route** in `bot/web/app.py` (registration in `_routes`) plus a handler method.
- **New service logic** in `bot/web/services.py` (or a new small module) for item→batch→owner
  resolution and metadata/expiry verification.
- **New read-only staging access** helper (open + `fstat` + bounded stream) — **[F] no change** to
  `StagingStore`/reaper semantics.
- **New frontend control** in `bot/web/static/` (follow `export.js`/`files.js` patterns) + tests.
- **New tests**: backend (authz/IDOR/expiry/race), frontend (Node), and the §13 real-device plan.

**Explicitly out of boundary:** schema/migrations, session/token storage, outbox, workers,
scheduler, remote delivery, `MINI_APP_ENABLED` activation, D-22.

---

## 24. Explicit non-authorization statement

This report **does not** authorize implementation, runtime activation, or remote attachment delivery.
**No option is selected by this document.** D-22 remains unresolved (and is not applicable to MT-2).
No schema change, no session/token change, no route, no frontend change, and no activation is
approved. Real-device WebView verification is **outstanding** and must be completed before any
implementation or activation. Any implementation requires a **separate, explicit owner
authorization** naming the option, scope, and permitted files.

---

## 25. Source references and verification evidence

**Auth/session:** `bot/web/app.py:30–36`, `:195–215`, `:432–451`, `:494–530`; `bot/web/sessions.py:30–35`,
`:58–140`; `bot/web/initdata.py:53–58`, `:68–142`; `bot/db.py:732–740`, `:2546–2558`;
`bot/config.py:26–27`, `:59–60`, `:262`, `:292–301`, `:322–333`.
**Authorization:** `bot/files.py:75–92`, `:199–266`; `bot/web/services.py:375–399`, `:711–747`.
**Attachment/staging:** `bot/attachments.py:99`, `:105–111`, `:120–148`, `:199–204`, `:284–287`,
`:457–520`, `:585–589`, `:609–740`, `:815–880`, `:975–1200`, `:1316–1370`, `:1376–1432`;
`bot/db.py:121–175`, `:261`, `:279–300`, `:490–546`, `:769–813`, `:1088–1200`, `:1224–1284`,
`:1716–1732`.
**Web routes/frontend:** `bot/web/app.py:65–108`, `:275–292`, `:300–420`, `:714–800`;
`bot/web/static/app.js:1031–1061`; `bot/web/static/export.js:1–63`; `bot/web/static/files.js`.
**Framework:** `starlette==1.3.1`, `uvicorn==0.34.0` (`requirements.txt`); `StreamingResponse`
importable **[F]**.
**Docs/decisions:** `docs/MINI_APP.md:59–101`, `:178–205`, `:532–655`;
`docs/decisions/OHB2-OWNER-DECISION-PLAN08-MANUAL-ATTACHMENT-TRANSFER.md`;
`docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md:148–162`, `:1042–1060`, `:2250–2256`;
`docs/reviews/OHB2-PLAN-08-MANUAL-ATTACHMENT-TRANSFER-UX-DESIGN.md:340–400`, `:592–650`.

**Verification commands run this session (no files changed):**
- `python -m pytest tests/test_miniapp_http_journeys.py tests/test_real_http_miniapp_download.py tests/test_miniapp_export_reply.py tests/test_miniapp_session_persistence.py tests/test_miniapp_initdata.py tests/test_a2_export_auth.py -q` → **119 passed** (exit 0).
- `node --test tests/frontend/*.test.js` → **fail 0** (exit 0).
- `grep` checks for `StreamingResponse`/`FileResponse`, `attachment_staging` reads, and `Range`/206
  (all confirmed absent).

> Evidence labels recap: **[F]** verified · **[I]** inference · **[U]** unverified ·
> **[G]** documented-but-untested · **[R]** recommendation · **[OWNER]** owner decision. This report
> is **not** independently reviewed.
