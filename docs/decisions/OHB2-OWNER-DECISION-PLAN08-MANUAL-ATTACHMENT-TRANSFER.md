# OHB2 — Owner Decision: Manual Attachment Transfer (Plan 08)

> **STATUS: `PROPOSED — OWNER DECISION REQUIRED`.** This document **prepares** a decision; it
> **does not make** one. No option is selected, no owner decision is resolved, no schema change is
> approved, and no implementation is authorized. The owner retains sole authority to select an
> option, approve architectural changes, and separately authorize implementation.

---

## 1. Decision record metadata

- **Task ID:** `OHB2-OWNER-DECISION-PLAN08-MANUAL-ATTACHMENT-TRANSFER`.
- **Document title:** OHB2 — Owner Decision: Manual Attachment Transfer (Plan 08).
- **Status:** `PROPOSED — OWNER DECISION REQUIRED`.
- **Date:** 2026-11-15 (environment date, UTC).
- **Prepared by:** OpenHands agent (autonomous) on behalf of the repository owner. This is a
  **decision-preparation** artifact, not an approved record.
- **Destination rationale:** the repository stores owner-decision material under `docs/decisions/`
  (register `OHB2-P0-OWNER-DECISIONS-REGISTER.md`, brief
  `OHB2-P0-F5-F6-ROUTE-ATTACHMENT-WINDOW-OWNER-DECISION-BRIEF.md`) and
  `docs/decisions/owner-briefs/`. This document follows that convention and is placed at
  `docs/decisions/OHB2-OWNER-DECISION-PLAN08-MANUAL-ATTACHMENT-TRANSFER.md`. It is written in
  English per the task requirement (the register and briefs are in Arabic; the content is
  equivalent in intent — preparation only).

**Related Plan 08 reports**
- Corrected design: `docs/reviews/OHB2-PLAN-08-MANUAL-ATTACHMENT-TRANSFER-UX-DESIGN.md`
  (SHA-256 `0914609f…`, 812 lines).
- First independent review: `docs/reviews/OHB2-REVIEW-PLAN08-MANUAL-ATTACHMENT-TRANSFER-UX-DESIGN.md`
  (SHA-256 `71cc88c8…`, 406 lines) — verdict `NEEDS_REMEDIATION`.
- Second independent review: `docs/reviews/OHB2-REVIEW-PLAN08-DESIGN-REMEDIATION.md`
  (SHA-256 `af943437…`, 427 lines) — verdict `PASS_WITH_NOTES`.
- Related investigations: `docs/reviews/OHB2-REPAIR-PLAN-05-SECURE-ATTACHMENT-DELIVERY-INVESTIGATION.md`
  (status `BLOCKED`), `docs/reviews/OHB2-REPAIR-PLAN-06-ATTACHMENT-DELIVERY-ALTERNATIVE-ARCHITECTURE.md`,
  `docs/reviews/OHB2-PLAN-07-A-SECURE-PULL-FEASIBILITY-INVESTIGATION.md` (Secure Pull feasibility),
  `docs/reviews/OHB2-PLAN-07-A2-DELIVERY-IDENTITY-AND-EVIDENCE-RESOLUTION.md`.

**Related architecture / owner decisions**
- **D-22** (outbox integration limit) — register `:1042–1060` — **unresolved, blocking**.
- **D-12** (size/type quota policy) — register `:158` — unresolved.
- **D-15** (`expires_at` 15-min window; no server batch) — register `:161` — **CONFIRMED (Option A, 2026-11-15)**.
- **D-16** (idempotency / dedup) — register `:162` — unresolved.
- Long-term verified-delivery blockers: **D-02/D-03** (U-3 signal + trusted issuer),
  **D-04** (quiesced evidence source), **D-06** (workspace-root binding) — register `:148–152`.
- Invariants: **I2** (single SQLite owner), **I3** (single bot process) — register `:2250–2256`.
- Remote-delivery stages **B1/B2/B3** — `docs/proposals/OHB2-P0-STAGED-IMPLEMENTATION-PLAN.md`
  `:739`, `:756`, `:768` — `NOT AUTHORIZED TO START`.

**Scope of this document**
- Present the three temporary-path alternatives (MT-1, MT-2, Defer) fairly with source evidence.
- Surface the decisions only the owner can make (esp. D-22) without resolving them.

**Explicit non-scope**
- No selection of an option; no approval of any architecture/schema/worker/route; no
  implementation; no remote delivery; no runtime activation; no commit/push/PR/merge/release/deploy.

---

## 2. Executive summary

**The problem.** OpenHandBot already accepts a supported Telegram attachment and stores its bytes
**locally** (staging) for a bounded 15-minute window. **No path currently lets the user get those
bytes back**, and **no path delivers the file to OpenHands**. The owner must decide whether to add a
**temporary manual retrieval mechanism** (Telegram send-back or Mini App download) or to **defer**
and keep local staging only.

**What works today (verified).**
- Bounded attachment intake with a hard 3 MiB per-file cap (`bot/attachments.py:99`).
- Secure local staging: directory mode `0700`, file mode `0600`, opaque 32-hex-char filenames
  (`bot/attachments.py:108–111`, `:199`).
- One authoritative SQLite owner holding all attachment metadata (`bot/db.py`), with an
  attachment↔message identity table (PK + `ON DELETE RESTRICT`, `bot/db.py:804–813`).
- Expiry/cleanup: a 15-minute deadline (`bot/db.py:261`) enforced by an existing reaper driven by
  the existing watcher tick (`bot/app.py:227–241`).

**What does not work today (verified).**
- **No user-facing retrieval of staged bytes.** No route or handler reads `attachment_staging/`
  (repo-wide grep returns nothing outside `bot/attachments.py`/`bot/db.py`).
- **No Telegram send-back.** `send_document` exists but is used only for unrelated in-memory
  content (`bot/handlers.py:1460`, `:1559`; `bot/sender.py:31`, `:76`); it is never used to send
  staged bytes.
- **No Mini App attachment-download route.** Existing Mini App routes serve a conversation export
  zip and a text preview of workspace files (`bot/web/app.py:733`, `:753`, `:768`), not staged bytes.
- **No proof of remote delivery to OpenHands.** The `delivered` batch state is defined but never
  written in runtime code; there is no delivery path.

**Why the owner must decide.** MT-1 and MT-2 are **not** interchangeable: MT-1 is blocked by an
unresolved owner decision (**D-22**, durable Telegram-document operation) and requires new durable
state; MT-2 avoids D-22 but needs a new authenticated route and **unverified real Telegram Android
WebView** behavior, plus a scope decision. "Defer" keeps the status quo but leaves users unable to
retrieve files. None of these is a free choice, and the owner's constraints (§3 of the task) forbid
weakening delivery guarantees to make any option easier.

**Why this decision does not authorize remote delivery.** Manual transfer moves bytes **to the
user**, not **to OpenHands**. The long-term reliable-delivery path requires provider-verified
identity/evidence (U-12/U-3; D-02/D-03/D-04/D-06) that remains unimplemented and unauthorized
(§13).

---

## 3. Current verified behavior

### 3.1 Attachment intake and validation (IMPLEMENTED)
- Telegram `Document` messages route to `handlers.handle_attachment` via
  `SUPPORTED_ATTACHMENT_FILTER = filters.Document.ALL` (`bot/app.py:34`, `:157–161`;
  `bot/handlers.py:1818`).
- Authorization: allowed user + private chat (`_allowed`, `bot/handlers.py:53`; `_guard`,
  `:234`), then conversation ownership (`_authorized`, `bot/attachments.py:815`).
- An explicit open routed conversation is required (no fallback) (`bot/handlers.py:1849–1852`).
- `MAX_ATTACHMENT_BYTES = 3 * 1024 * 1024` (**3 MiB = 3 145 728 bytes**) — `bot/attachments.py:99`;
  enforced on every accepted attachment (`bot/handlers.py:1878` → `_download_attachment_chunks`).
- Extension and magic-byte deny lists reject executable/script types
  (`bot/attachments.py:117–148`, `:319–320`).

### 3.2 Local staging (IMPLEMENTED)
- Directory: `<db_dir>/attachment_staging/` (`STAGING_DIRNAME`, `bot/attachments.py:108`;
  `staging_root_for`, `:204`).
- Permissions: dir `0o700`, file `0o600` (`bot/attachments.py:109–110`).
- Filename: opaque `secrets.token_hex(16)` → 32 hex chars (`new_staging_token`, `bot/attachments.py:199`;
  `_TOKEN_HEX_BYTES = 16`, `:111`).
- Write is `O_CREAT|O_EXCL|O_NOFOLLOW` under the 0700 root (`bot/attachments.py:585`), then verified
  (size > 0 + magic-byte deny list) before the item is atomically marked `stored`
  (`bot/attachments.py:718–740`; `db.try_mark_attachment_item_stored`, `bot/db.py:1224`).

### 3.3 SQLite ownership and attachment identity (IMPLEMENTED)
- **One authoritative SQLite owner** (`I2`, register `:2255`); all metadata lives in `bot/db.py`;
  the filesystem holds only opaque byte files.
- Tables: `attachment_batches(telegram_id, conversation_id, batch_id, …)`;
  `attachment_items(item_id, batch_id, staging_token, display_name, size_bytes, status)`;
  `attachment_message_identity(telegram_id, chat_id, message_id, batch_id, conversation_id)` with
  PK `(telegram_id, chat_id, message_id)` and FK `ON DELETE RESTRICT` (`bot/db.py:804–813`).
- The Telegram `file_id` is **not** stored anywhere (no such column); the staged bytes are the only
  copy the bot retains.

### 3.4 Current lifecycle states (IMPLEMENTED vs DEFINED-BUT-UNUSED)
- Batch states **defined** (`bot/db.py:121–137`): `pending`, `intent_recorded`, `dispatching`,
  `uncertain`, `delivered`, `expired`, `rejected`, `failed`.
- Batch states **actually written in runtime code**: `pending` (`bot/attachments.py:704`),
  `intent_recorded` (`bot/db.py:1630`), `expired` (`bot/attachments.py:869`, `:1128`).
  `dispatching`/`uncertain`/`delivered`/`rejected`/`failed` are **never written** (constants only).
- Item states: `pending` → `stored` (`bot/db.py:1224`) → `reaped` (`bot/db.py:1463`;
  constant `bot/db.py:171–175`).

### 3.5 Expiration and cleanup (IMPLEMENTED)
- Fixed 15-minute deadline from the first file of the batch (`ATTACHMENT_BATCH_TTL`,
  `bot/db.py:261`).
- Reaper is DB-first: marks the batch `expired` (CAS), then unlinks bytes with strict guards
  (`sweep`, `bot/attachments.py:1020`; `_remove_file`, `:1316`; `absent` idempotent, `:1334`).
- Driven by the **existing** watcher tick via `OpportunisticSweeper` (`bot/app.py:227–241`;
  `bot/watcher.py:182–183`) — no new worker/scheduler/process.

### 3.6 Retrievability today (NOT IMPLEMENTED)
- **Users cannot retrieve staged bytes.** No route/handler reads `attachment_staging/`
  (verified by repo-wide grep).
- **No Telegram send-back route exists.** `send_document` call sites are unrelated in-memory sends
  (`bot/handlers.py:1460`, `:1559`; `bot/sender.py:31`, `:76`).
- **No authenticated Mini App attachment-download route exists.** Existing routes:
  `…/export` (conversation zip, `bot/web/app.py:733`), `…/file?path=` (text preview of workspace
  files, `:768`; `docs/MINI_APP.md:649`), `…/reply` (full reply text, `:714`).
- **No current path proves remote delivery to OpenHands.**

### 3.7 Event distinctions (must not be collapsed)
| Event | Status today |
| --- | --- |
| Attachment **received** (Telegram intake accepted) | IMPLEMENTED (`ATTACHMENT_ACCEPTED_TEXT`, `bot/handlers.py:1601`) |
| Attachment **staged locally** (bytes on disk, item `stored`) | IMPLEMENTED (`bot/attachments.py:609`, `:1224`) |
| Attachment **retrievable by the user** | NOT IMPLEMENTED |
| Attachment **sent through Telegram** (send-back) | NOT IMPLEMENTED |
| Attachment **uploaded to OpenHands** | NOT IMPLEMENTED (user action; outside OpenHandBot) |
| **Remote delivery independently verified** | NOT IMPLEMENTED (U-12/U-3 absent) |

---

## 4. Option MT-1: Telegram send-back

**Proposed journey (PROPOSED).** After a successful local staging, the user requests the bot to
send the staged file back to them in Telegram; the bot reads the staged bytes and calls
`send_document`; the user then manually uploads the file to the intended OpenHands conversation.

### 4.1 Existing capabilities that could be reused (CONFIRMED EXISTING)
- **Telegram document sending exists:** `bot.send_document(..., InputFile(...))` is already used
  (`bot/handlers.py:1460`, `:1559`; `bot/sender.py:31`, `:76`; wrapper `bot/sender.py:61–76`).
  **[F]** There are **4** `send_document` invocations, all in-memory and unrelated to staged bytes.
- **Authorization primitives:** `_allowed` (`bot/handlers.py:53`), `_authorized`
  (`bot/attachments.py:815`), private-chat guard (`_guard`, `:234`).
- **Attachment identity:** `attachment_batches` + `attachment_items` + `attachment_message_identity`
  (`bot/db.py:804–813`).
- **At-most-once mechanics pattern:** the existing outbox CAS/`unknown` semantics
  (`bot/db.py:3346`; `bot/outbox.py:298`, `:452`, `:472–478`).

### 4.2 The current outbox cannot be assumed to support document operations (NEW IMPLEMENTATION REQUIRED)
- Outbox schema (`bot/db.py:608–621`): `(id, conversation_id, chat_id, text, status, error,
  created_at, updated_at, attempts, client_ref, notify_state)` — **no payload/blob column, no
  operation-kind column**; the only payload is `text`.
- Dispatch target: `client.send_message(conversation_id, text)` → `POST
  /app-conversations/{id}/send-message` on **OpenHands** (`bot/openhands_client.py:337–339`),
  **not** Telegram.
- **[F]** The outbox has **no** document/file payload, no `InputFile`, and no Telegram send call.
  It is **not** a Telegram document-delivery mechanism.

### 4.3 Durable operation requirements and D-22 (OWNER DECISION REQUIRED)
- MT-1 needs a **durable Telegram-document operation**: a persisted record carrying a document
  reference (e.g. item id / `staging_token`) plus a status, with crash recovery.
- This requires either **(a)** a new outbox payload/kind capability or **(b)** another explicitly
  owner-approved mechanism — i.e. **D-22** (register `:1042–1060`; see §9).
- **MT-1 cannot be designed for implementation until D-22 is decided.**

### 4.4 Aspect-by-aspect assessment
| Aspect | Status |
| --- | --- |
| Telegram `send_document` support | **EXISTING** (in-memory only) |
| Reusable handler/wrapper | **EXISTING** (`bot/sender.py:61–76`) |
| Outbox document capability | **NEW IMPLEMENTATION REQUIRED** |
| Durable operation + recovery | **NEW IMPLEMENTATION REQUIRED** |
| D-22 | **OWNER DECISION REQUIRED** |
| Attachment identity + authorization | **EXISTING** (reuse) |
| File existence/integrity check before send | **NEW IMPLEMENTATION REQUIRED** (first-ever staged-byte read into a user path) |
| Expiry/cleanup coordination | **NEW IMPLEMENTATION REQUIRED** (must not delete bytes mid-send) |
| Duplicate/concurrent requests | **NEW IMPLEMENTATION REQUIRED** (dedupe by attachment identity) |
| Crash recovery | **NEW IMPLEMENTATION REQUIRED** (pre-CAS/post-CAS pattern reuse) |
| Telegram acceptance vs user receipt | **NOT IMPLEMENTED** — API acceptance ≠ user download |
| Unknown network outcome | **NEW IMPLEMENTATION REQUIRED** (map to `unknown`, no auto-retry) |
| Retry safety | **NEW IMPLEMENTATION REQUIRED** — no exactly-once claim possible |
| Weak-network reliability | **UNVERIFIED** |
| Android usability | **[I] plausible** (inside Telegram, no WebView) — **UNVERIFIED** |
| Operational complexity | **MEDIUM** (new durable op) |
| Testability | backend + integration + crash/race; no real Telegram send in tests |

### 4.5 Consequences of a lost local success record
If Telegram **accepts** the document but the local success record is lost (crash between the API
call and the local status write), the operation is **ambiguous**: the file may have been delivered
to Telegram while the local state says otherwise. The only honest handling is **`unknown`** with
**no automatic retry** (mirroring the existing outbox, `bot/outbox.py:447–478`). A retry could
produce a **duplicate** send. **No exactly-once delivery is claimed or possible.**

**MT-1 bottom line:** a bounded, honest, at-most-once design is conceivable, but it **requires
D-22 and new durable state** and **cannot be started** until the owner decides D-22.

---

## 5. Option MT-2: Mini App download

**Proposed journey (PROPOSED).** The authenticated Mini App shows a download control for a staged
attachment; a new authenticated route resolves the attachment server-side and returns its bytes;
the user then manually uploads the file to the intended OpenHands conversation.

### 5.1 Existing capabilities that could be reused (CONFIRMED EXISTING)
- **Session authentication:** cookie-based sessions (`COOKIE_NAME = "ohb_session"`,
  `bot/web/app.py:36`; `SessionStore`, `bot/web/sessions.py`; `_session_from_cookie`, `:203`).
- **Guard pipeline:** `_guarded` (rate-limit → session → `_allowed` → Origin for state-changing
  requests) (`bot/web/app.py:432`).
- **Ownership checks:** server-side conversation ownership inside `FileService`
  (`bot/web/services.py:878–890`); the route does not re-implement authorization.
- **Response helper:** `_attachment(data, filename)` sets safe `Content-Disposition`,
  explicit `Content-Length`, and security headers (`bot/web/app.py:95–108`).
- **Staging token + safe-path guards:** `staging_token` + `_is_within` (`bot/attachments.py:284`) +
  `lstat` (`bot/attachments.py:1316`).

### 5.2 What does not exist (NEW IMPLEMENTATION REQUIRED)
- **No route reads `attachment_staging/`** (verified). MT-2 needs a **new authenticated
  download route**.
- **[F]** `_attachment` reads bytes **fully into memory** and there is **no `Range`/206** support in
  `bot/web/` (grep). A future route should stream and cap.
- **No frontend download control for staged bytes** exists (no `attachment`/`staging` reference in
  `bot/web/static/*.js`).

### 5.3 Aspect-by-aspect assessment
| Aspect | Status |
| --- | --- |
| Session auth model | **EXISTING** (`bot/web/app.py:36`, `:203`, `:432`) |
| Ownership/authorization | **EXISTING** (reuse `_guarded` + `FileService`) |
| Attachment retrieval route | **NEW IMPLEMENTATION REQUIRED** |
| Authorization on every request | **EXISTING pattern** (reuse) |
| Cross-user/cross-conversation protection | **EXISTING pattern** (reuse; must enforce structurally) |
| Safe file resolution / traversal / symlink | **EXISTING primitives** (`_is_within`, `lstat`) |
| Streaming / bounded resources | **NEW IMPLEMENTATION REQUIRED** (stream + cap; today `_attachment` buffers) |
| Content length / integrity | **NEW IMPLEMENTATION REQUIRED** (explicit `Content-Length`, size check) |
| Expiry/cleanup coordination | **NEW IMPLEMENTATION REQUIRED** |
| Interrupted download | **NEW IMPLEMENTATION REQUIRED** (no partial "success") |
| Duplicate download requests | **NOT APPLICABLE** (idempotent GET) |
| Browser & Telegram WebView behavior | **UNVERIFIED** (only Node DOM stub, `tests/frontend/dom_stub.js:336–342`) |
| Android download destination/UX | **UNVERIFIED** |
| Weak-network reliability | **UNVERIFIED** |
| Operational complexity | **LOWER than MT-1** (route + frontend; no durable op, no D-22) |
| Testability | backend + frontend; **real WebView verification required** |
| Schema impact | **NONE** (reads existing metadata) |

### 5.4 Required genuine verification
- **[F]** The only Blob-download exercise is the Node DOM stub
  (`tests/frontend/dom_stub.js:336–342`); it is **not** proof that a real Telegram Android WebView
  downloads a file. **Real-device WebView verification is required** before MT-2 implementation or
  activation. The Mini App is disabled by default (`MINI_APP_ENABLED=False`, `bot/config.py:262`)
  and, if enabled, requires a public HTTPS `MINI_APP_URL` (`bot/config.py:242–266`).

**MT-2 bottom line:** the architectural footprint is smaller (no schema change, no D-22), but MT-2
is **not decision-free** — it needs a **scope** decision and **real-device WebView verification**,
and its download UX on Android is `UNVERIFIED`.

---

## 6. Option MT-3 and other existing paths

Investigated against current source:
- `GET …/file?path=` serves a **text preview of existing workspace files**, not staged bytes
  (`bot/web/app.py:768`; `docs/MINI_APP.md:649`).
- `GET …/reply` + `send_text_document` serves a `.txt` of the assistant reply, not the attachment
  (`bot/web/app.py:714`; `bot/sender.py:61–76`).
- No bot command/callback retrieves a staged attachment (handler registration, `bot/app.py`).

**NO VERIFIED EXISTING ALTERNATIVE.** No currently usable path returns staged bytes to the user.
No alternative is invented to make the comparison appear complete.

---

## 7. Option: Defer implementation

**What remains available (IMPLEMENTED).**
- Bounded intake + local staging + identity tracking + 15-minute expiry/cleanup + receipt replies.

**What users cannot do.**
- Retrieve the staged bytes (no send-back, no download). After 15 minutes the bytes are deleted.

**What local staging does and does not guarantee.**
- **Does:** the bot retains the bytes locally (mode `0600`) for ≤15 minutes and records identity.
- **Does not:** deliver anything to OpenHands; guarantee retrievability; guarantee any upload.

**Operational burden.** None beyond the current reaper. **Expiration:** unchanged (15 minutes).

**User communication.** Must clearly state that staging ≠ delivery and that no retrieval exists yet
(today's `ATTACHMENT_ACCEPTED_TEXT`, `bot/handlers.py:1601`, does **not** distinguish local from
remote — the S-13 gap; corrected by the proposed §10 wording, pending owner copy approval).

**Security implications.** Unchanged; no new attack surface (no new route/endpoint).

**Can the current implementation safely remain unchanged?** **Yes** — it is bounded, fail-closed,
and does not expose staged bytes. Deferral is a **safe** option.

**Triggers to reconsider.** (a) Owner selects MT-1/MT-2; (b) a verified reliable-delivery path
(U-12/U-3) becomes available; (c) repeated user demand for file retrieval is observed.

**Deferral is not a solution.** It does not give the user the file; it preserves the status quo and
documents the limitation.

---

## 8. Comparative decision matrix

| Criterion | MT-1 (Telegram send-back) | MT-2 (Mini App download) | Defer |
| --- | --- | --- | --- |
| Existing implementation available | **EXISTING** (`send_document`/`InputFile`) | **EXISTING** (`_guarded` + `_attachment` + sessions) | **EXISTING** (staging only) |
| New runtime capability required | **NEW IMPLEMENTATION REQUIRED** (durable doc op + handler) | **NEW IMPLEMENTATION REQUIRED** (auth download route + frontend) | **NOT APPLICABLE** |
| Schema impact | **NEW IMPLEMENTATION REQUIRED** (new payload/kind or table) | **NOT APPLICABLE** (reads existing metadata) | **NOT APPLICABLE** |
| D-22 dependency | **OWNER DECISION REQUIRED** (blocks design + implementation) | **NOT APPLICABLE** (D-22 is outbox-specific) | **NOT APPLICABLE** |
| Authentication/authorization requirements | **EXISTING** (reuse `_allowed`+`_authorized`) | **EXISTING** (reuse `_guarded`+ownership) | **NOT APPLICABLE** |
| File exposure risk | **MEDIUM** (send-side; reuses ownership; no public URL) | **MEDIUM** (read-side; reuses ownership; no public URL) | **NONE** (no new exposure) |
| Expiry/cleanup coordination | **NEW IMPLEMENTATION REQUIRED** | **NEW IMPLEMENTATION REQUIRED** | **NOT APPLICABLE** |
| Duplicate/uncertain operation handling | **NEW IMPLEMENTATION REQUIRED** (CAS + `unknown`; no exactly-once) | **NOT APPLICABLE** (idempotent GET) | **NOT APPLICABLE** |
| Weak-network reliability | **UNVERIFIED** | **UNVERIFIED** | **NOT APPLICABLE** |
| Android usability | **UNVERIFIED** (inferred OK inside Telegram) | **UNVERIFIED** (WebView download) | **NOT APPLICABLE** |
| Telegram WebView dependency | **NOT APPLICABLE** (no WebView needed) | **REQUIRED** (real-device verification) | **NOT APPLICABLE** |
| Operational complexity | **MEDIUM** (durable op + new state) | **LOWER** (route + frontend; no schema) | **NONE** |
| Verification effort | backend + integration + crash/race | backend + frontend + **real device/WebView** | none |
| Implementation prerequisites | **D-22** + scope + wording (+ D-15/D-16) | **scope** + **WebView verification** + wording | none |
| Remote-delivery guarantee | **NOT IMPLEMENTED** | **NOT IMPLEMENTED** | **NOT IMPLEMENTED** |

**Trade-off (not hidden behind a score).** MT-2 has the smaller architectural surface (no schema,
no D-22) but carries an `UNVERIFIED` real-device WebView risk and a scope decision. MT-1 avoids the
WebView risk but needs a durable operation and is blocked by **D-22**. Defer is safe but leaves
retrieval unimplemented. The criteria **conflict**: neither MT-1 nor MT-2 dominates.

**NO OPTION IS SELECTED BY THIS DOCUMENT. THE OWNER MUST DECIDE AFTER REVIEWING THE TRADE-OFFS AND
PREREQUISITES.**

---

## 9. D-22 decision

**D-22 — outbox integration limit** (register `:1042–1060`; status **unresolved**; type **owner
(integration) decision**; classified **blocking** in register §6.3).

### 9.1 The current outbox contract (verified)
- Schema (`bot/db.py:608–621`): text-only; no payload/blob column; no operation-kind column.
- Dispatch: `client.send_message(conversation_id, text)` → OpenHands `send-message`
  (`bot/openhands_client.py:337–339`).
- Status machine: `pending → claimed → sending → sent|unknown|failed` with CAS
  (`bot/db.py:3346`; `bot/outbox.py:298`, `:452`), pre-CAS recovery
  (`bot/outbox.py:249`), and `unknown` on ambiguous outcomes with no auto-retry
  (`bot/outbox.py:447–478`).

### 9.2 Why the text-only outbox does not represent Telegram document delivery
The outbox can only carry a `text` payload and only dispatches to OpenHands. A Telegram document
send-back is a **different operation** (a file payload, a Telegram target, and a distinct result
semantics: API acceptance ≠ user receipt). Treating the existing outbox as a Telegram document
mechanism would be incorrect.

### 9.3 Architectural questions a durable Telegram-document operation raises
- Where is the durable record stored, and how is a document reference (item id / `staging_token`)
  represented without breaking the single-SQLite-owner invariant (I2)?
- How is the operation keyed to attachment identity so duplicates can be detected?
- How is the staged file kept alive until a terminal outcome, given the 15-minute reaper?
- How are crash windows (before/after enqueue, during transmission, after acceptance) handled
  honestly with at-most-once semantics?

### 9.4 What must be decided before MT-1 can be designed for implementation
- The mechanism: **(a)** a new outbox payload/kind, or **(b)** another explicitly owner-approved
  mechanism (register D-22 options A/B).
- Confirmation that the chosen mechanism preserves I2/I3 (one SQLite owner, one bot process) and
  introduces **no** new worker/scheduler/process.

### 9.5 What would require separate approval
- Any schema change or migration; any new durable state; any new operation type; any change to the
  outbox contract. **None of these is approved by this document.**

### 9.6 If the owner does not approve the required mechanism
- MT-1 cannot proceed to design for implementation; only MT-2 or Defer remain. The register's D-22
  "do nothing" option (C) means attachments cannot be sent back (its recorded consequence:
  "P0 بلا معنى عملي" — the attachment capability has no practical effect).

### 9.7 D-22 and MT-2
- **[F]** D-22 is an **outbox-specific** integration decision. **MT-2 does not require D-22** —
  MT-2 reads existing metadata through a new route and needs **no** outbox change. This document
  **does not** use MT-2 to silently resolve D-22.

---

## 10. Other owner decisions

### D-12 — size/type quota policy (register `:158`; unresolved; **policy** decision)
- **Verified meaning:** the current bounds are `max_total (3 MiB) == max_per_file (3 MiB)`, so
  effectively one full-size file per batch; `MAX_ITEMS_PER_BATCH = 10` and
  `MAX_STAGING_TOTAL_BYTES = 64 MiB` are **defined but disabled by default** (`None`)
  (`bot/attachments.py:105–106`; `StagingStore.__init__` defaults `None`). Values are marked
  **PROVISIONAL / NOT APPROVED**.
- **Relationship to MT-1/MT-2:** shapes UX wording and any batch-level bounds; affects both options'
  copy and limits.
- **Blocking scope:** does **not** block MT-2 design (route reads a single item); affects wording and
  bounds; a **policy** confirmation is required before enforcing consistent limits.
- **Exact owner choice:** keep the single-full-file behavior (A), raise `max_total` (B), or lower
  `max_per_file` (C) — register D-12 options.

### D-15 — 15-minute window; no server-side batch (register `:161`; **CONFIRMED — Option A, 2026-11-15**)
- **Verified meaning:** `expires_at` = fixed 15 minutes, not extended; it reclaims **staging only**
  (not C2); the server has no batch concept (batch is client-side); no non-terminal state after
  `expires_at`.
- **Relationship to MT-1:** affects MT-1 expiry handling (a pending send must not be invalidated
  after acceptance).
- **Relationship to MT-2:** affects download-window/expiry handling.
- **Blocking scope:** shapes design; **not** a hard blocker for design, but must be confirmed.
- **Exact owner choice:** confirm the current model (A) / model the batch server-side (B) / a
  different window (C).
- **OWNER DECISION (2026-11-15):** **Option A — confirmed.** The owner confirmed the current model
  (fixed 15-minute window, not extended; expiry reclaims staging only, not C2; no server-side batch
  modelling; no non-terminal batch state after expiry). Recorded authoritatively in the register
  (`docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md` → §5 → D-15). This is a **documentation-only
  confirmation**: it changes **no** staging lifecycle, **no** schema, and authorizes **no** unrelated
  architectural change. (This subsection note does not alter the MT-1/MT-2 direction status above.)

### D-16 — idempotency / dedup (register `:162`; unresolved; **design** decision + new requirement U-4)
- **Verified meaning:** whether `Idempotency-Key` + `sha256` dedup are accepted and over what window;
  whether delivery idempotency keyed on `(operation_id, file_id)` is confirmed. **[UNVERIFIED]:** no
  idempotency key exists on `send-message` today (U-6); U-6 is an optional message-level addition.
- **Relationship to MT-1:** directly relevant to duplicate-send safety (see §4.5, §8).
- **Relationship to MT-2:** **NOT APPLICABLE** (idempotent GET).
- **Blocking scope:** blocks MT-1 **implementation** (not design); classification is "blocking
  (design)" in the register.
- **Exact owner choice:** adopt full idempotency (A) / rely on `client_operation_id` only (B) /
  none (C, unsafe).

### Additional decisions required
- **Option selection:** MT-1 vs MT-2 vs Defer (§14 Decision A).
- **Scope:** individual attachments only vs broader (§14 Decision C).
- **Arabic UX wording:** approve/revise/defer the §10 copy (§14 Decision D).
- **WebView verification:** the required real-device verification before MT-2 (§14 Decision E).
- **Schema/architecture changes:** any discovered change requires separate approval (tied to D-22
  for MT-1).
- **Runtime activation:** requires separate authorization (§14 Decision F).

*All three of D-12/D-15/D-16 are located in the register and their scope is stated there; none is
inferred from its identifier.*

---

## 11. Arabic UX wording for owner approval

Source: corrected Plan 08 §10 (`docs/reviews/OHB2-PLAN-08-MANUAL-ATTACHMENT-TRANSFER-UX-DESIGN.md`
`:448–548`). **All wording below is `PROPOSED — OWNER COPY APPROVAL REQUIRED`.**

| # | Triggering event | Status | Wording (Arabic) | Explicitly does NOT claim |
| --- | --- | --- | --- | --- |
| 10.1a | Staging succeeded (item `stored`) | PROPOSED — OWNER COPY APPROVAL REQUIRED | `✅ استلمت الملف وخزّنته محليًّا في OpenHandBot.` `⚠️ لسه ما اترفعش لـ OpenHands — التخزين محلي عندنا بس.` | Does not claim OpenHands received the file |
| 10.1b | Durable row exists but bytes not stored (`pending`) | PROPOSED — OWNER COPY APPROVAL REQUIRED | `⏳ سجّلت الملف — لسه بيتم التخزين. مش مرفوع لـ OpenHands.` | Does not claim staging completed |
| 10.2a | Manual retrieval available (MT-1, future) | PROPOSED — OWNER COPY APPROVAL REQUIRED | `📎 الملف جاهز للتنزيل من هنا.` `بعد ما تنزّله: افتح محادثة OpenHands المقصودة وارفع الملف بنفسك.` | Does not claim upload to OpenHands |
| 10.2b | Until MT-1 exists (honest current) | PROPOSED — OWNER COPY APPROVAL REQUIRED | `⚠️ التنزيل الذاتي لسه مش متاح في النسخة الحالية.` `الملف محفوظ محليًّا بس، ومش متسلّم لـ OpenHands.` | Does not claim retrieval exists |
| 10.3 | Telegram send-back accepted (MT-1, future) | PROPOSED — OWNER COPY APPROVAL REQUIRED | `📤 بعتّ الملف ليك في الشات ده (تيليجرام استقبل الإرسال).` `⚠️ ده مش معناه إن OpenHands استلمه — لازم ترفعه بنفسك.` | Does not claim user downloaded or OpenHands received |
| 10.4 | Mini App download completed (MT-2, future) | PROPOSED — OWNER COPY APPROVAL REQUIRED | `⬇️ تم تنزيل الملف في المتصفح.` `⚠️ ده مش معناه إن OpenHands استلمه — لازم ترفعه بنفسك.` | Does not claim OpenHands upload |
| 10.5 | Expired/missing local attachment | PROPOSED — OWNER COPY APPROVAL REQUIRED | `⌛ الملف المحلي مش متاح (انتهت صلاحية الـ 15 دقيقة). ابعت الملف تاني لو محتاجه.` | Does not claim the file is still available remotely |
| 10.6 | Retrieval failure | PROPOSED — OWNER COPY APPROVAL REQUIRED | `⚠️ التنزيل ماكملش. جرّب تاني.` `لو استمرّت المشكلة، ابعت الملف من جديد.` | Does not claim the file is still available unless verified |
| 10.7 | Manual upload instructions | PROPOSED — OWNER COPY APPROVAL REQUIRED | `1) نزّل الملف (لما تكون ميزة التنزيل متاحة). 2) افتح محادثة OpenHands المقصودة. 3) ارفع الملف جواها بنفسك. 4) اتأكّد إنه ظهر في مساحة العمل الصح.` | Does not claim the bot performs the upload |
| 10.7b | Honest limitation notice | PROPOSED — OWNER COPY APPROVAL REQUIRED | `🔔 OpenHandBot مايقدرش يتأكد إنك رفعت الملف لـ OpenHands. التأكيد لازم يكون منك جوه OpenHands.` | Does not claim independent verification |

**Conceptual status labels (NOT database states)** — corrected Plan 08 §10.8:
`LOCAL_STAGED`, `RETRIEVAL_AVAILABLE`, `TELEGRAM_SEND_ACCEPTED`, `USER_DOWNLOAD_COMPLETED`,
`USER_ASSERTED_OPENHANDS_UPLOAD`, `REMOTE_DELIVERY_VERIFIED`. These are explicitly **conceptual UX
labels, not implemented database states or approved lifecycle transitions**.

**Semantic guarantees preserved (verified):**
- Telegram API acceptance is **not** presented as confirmed user download (§10.3).
- A completed Mini App response is **not** presented as OpenHands upload (§10.4).
- A user assertion is **not** presented as independent verification (§10.7b).
- Expiry/failure messages make **no** "still available" claim (§10.5/§10.6).

**Today's shipped text** (`ATTACHMENT_ACCEPTED_TEXT`, `bot/handlers.py:1601`; `ATTACHMENT_TEXT_RECORDED_TEXT`,
`:1627`) does **not** distinguish local from remote — this is the S-13 gap the §10 copy addresses,
pending owner approval.

---

## 12. Security and reliability invariants

Non-negotiable for **any** future option:
1. **Authenticate and authorize** every retrieval/send request (`_allowed` + `_authorized` /
   `_guarded`).
2. **Preserve attachment-to-user and attachment-to-conversation identity**
   (`attachment_batches`, `attachment_items`, `attachment_message_identity`).
3. **Never expose attachments across users or conversations.**
4. **No public attachment endpoint and no bearer URL.**
5. **Preserve staging permissions** (`0700`/`0600`) and safe file access (`_is_within`, `lstat`,
   `O_NOFOLLOW`).
6. **Coordinate retrieval/send with expiry/cleanup** (do not delete bytes mid-operation; do not
   invalidate a durably accepted operation).
7. **No exactly-once delivery claim.**
8. **Handle uncertain external outcomes honestly** (`unknown`, no silent retry).
9. **Do not weaken existing delivery guarantees** (U-12/U-3/D-04/D-06/D-02/D-03).
10. **Keep local staging distinct from remote delivery.**
11. **Do not claim remote delivery without independent provider verification.**
12. **Preserve one authoritative SQLite owner** (I2).
13. **No unauthorized worker/scheduler/process/service** (I3).

---

## 13. Long-term remote-delivery boundary

The manual-transfer decision **does not** solve reliable remote delivery. Preserved requirements and
blockers (unchanged):
- **Provider-verified identity and authorization** are required for truthful delivery claims.
- **U-12** (workspace-root binding) and **U-3** (successful-read signal from a trusted issuer) remain
  unimplemented requirements.
- **D-02** (successful-read signal), **D-03** (trusted issuer boundary), **D-04** (quiesced evidence
  source), **D-06** (workspace-root source/binding) remain **blocking** (register `:148–152`).
- **F4 remains deferred** (the F4 signal is an `ActionEvent`; a bare `ActionEvent` is **not** proof
  of a successful read — see `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md:1637`,
  `:1804`, `:1846`). No F4 token-schema change is approved.
- **Secure Pull remains NOT IMPLEMENTED** (`docs/reviews/OHB2-PLAN-07-A-SECURE-PULL-FEASIBILITY-INVESTIGATION.md`).
- **No Plan 07-B/07-C authorization.**
- **No remote-delivery Stage B1/B2/B3 authorization** (`docs/proposals/OHB2-P0-STAGED-IMPLEMENTATION-PLAN.md:739`,
  `:756`, `:768` — `NOT AUTHORIZED TO START`).

These requirements are **not weakened or reinterpreted** by adopting MT-1, MT-2, or Defer.

---

## 14. Owner decision sheet

*Each decision is independent. Nothing here preselects an outcome, and none of these is an automatic
approval of implementation.*

**Decision A — Temporary retrieval direction** (owner selects one)
- A1. Approve **MT-1** (Telegram send-back) for further **design** only.
- A2. Approve **MT-2** (Mini App download) for further **design** only.
- A3. **Defer** both; keep local staging only.
- A4. Request **additional evidence** before choosing.

**Decision B — D-22**
- B1. Approve a **separately scoped architectural investigation** of a durable Telegram-document
  mechanism.
- B2. **Reject** the MT-1 direction (no document operation).
- B3. **Defer** D-22.
- B4. Request a **revised proposal**.

**Decision C — Scope**
- Define whether the selected option covers **individual attachments only** or a broader scope;
  identify excluded operations and limits (batch size, per-user limits, retention).

**Decision D — Arabic UX copy**
- D1. Approve the §10 wording as-is.
- D2. Request revisions.
- D3. Defer approval.

**Decision E — WebView verification (required for MT-2)**
- Identify the required **real-device** verification (Telegram Android WebView download) before
  MT-2 implementation or activation.

**Decision F — Implementation authorization**
- Implementation requires a **separate future authorization** that names the selected option, the
  scope, and the permitted files/changes. **No implementation is authorized by this document.**

---

## 15. Consequences and next steps

- **If MT-1 is selected (A1):** the next permitted action is a **separately scoped D-22
  design/investigation** (mechanism A/B), **not** implementation. D-15/D-16 and the scope/wording
  decisions must also be resolved first.
- **If MT-2 is selected (A2):** the next permitted action is a **separately scoped authenticated-
  download design** plus a **real-device/WebView verification plan**, **not** implementation. A
  scope decision and wording approval are prerequisites.
- **If both are deferred (A3):** **preserve the current implementation** and document the user-facing
  limitations; no code change.
- **If additional evidence is requested (A4):** identify the **smallest** evidence task that would
  resolve the specific uncertainty (e.g. a real-device WebView download test; a D-22 mechanism
  options analysis). **No follow-up task is created or authorized automatically by this document.**

---

## 16. Open risks and limitations

**Remaining LOW/INFO findings from the second independent review** (carried forward; the reviewed
design is **not** modified to remove them):
- **R-1 (LOW):** corrected Plan 08 §3.1 says "five untracked reports" while the working tree has
  **six** untracked reports. **Effect on owner decision: none** (documentation precision only).
- **R-2 (LOW):** corrected Plan 08 §20 says "3 in-memory call sites" for `send_document`/`InputFile`;
  the actual count is **4** `send_document` invocations (`bot/handlers.py:1460`, `:1559`;
  `bot/sender.py:31`, `:76`). **Effect: none** (the substance — in-memory, unrelated to staged
  bytes — is correct).
- **R-3 (INFO):** corrected Plan 08 §6.1 cites `outbox.py:447–470`; the `CancelledError` block is at
  `bot/outbox.py:472–478`. **Effect: none.**
- **R-4 (INFO):** corrected Plan 08 §18 lists an `F-08/§15` row with no counterpart in the first
  review. **Effect: none** (benign traceability label).

**Newly noted uncertainties (with evidence and severity):**
- **U-A (MEDIUM, unverified):** real Telegram Android WebView Blob-download behavior is `UNVERIFIED`
  — the only evidence is a Node DOM stub (`tests/frontend/dom_stub.js:336–342`). Relevant to MT-2.
- **U-B (MEDIUM, unverified):** Telegram API acceptance of a document send does not confirm user
  download; and a crash between API acceptance and local recording is ambiguous. Relevant to MT-1
  (at-most-once only).
- **U-C (LOW):** Android download destination/UX (where the downloaded file lands, whether the user
  can find it) is `UNVERIFIED`. Relevant to MT-2.

---

## 17. Evidence and traceability

**Source code / schema**
- `bot/attachments.py:99` (`MAX_ATTACHMENT_BYTES=3*1024*1024`), `:105–106` (quotas disabled),
  `:108–111` (staging name/modes/token), `:199` (`new_staging_token`), `:204` (`staging_root_for`),
  `:284` (`_is_within`), `:585` (`os.open`), `:609` (`store`), `:704` (`pending`), `:718–740`
  (verify/magic), `:815` (`_authorized`), `:1020` (`sweep`), `:1128` (`expired`), `:1316`
  (`_remove_file`), `:1334` (`absent`), `:1376`/`:1432` (`OpportunisticSweeper`).
- `bot/db.py:67–73` (outbox statuses), `:121–137` (batch statuses), `:171–175` (item states),
  `:261` (TTL 15m), `:608–621` (outbox schema), `:804–813` (identity table), `:1224` (`stored`),
  `:1463` (`reaped`), `:1630` (`intent_recorded`), `:3346` (`claim_outbox`).
- `bot/outbox.py:249` (`_recover_pre_cas_unexpected`), `:298` (`_post_claimed`), `:452` (POST),
  `:472–478` (`CancelledError`).
- `bot/openhands_client.py:337–339` (`send_message` → OpenHands).
- `bot/handlers.py:53` (`_allowed`), `:234` (`_guard`), `:1601` (`ATTACHMENT_ACCEPTED_TEXT`),
  `:1627` (`ATTACHMENT_TEXT_RECORDED_TEXT`), `:1460`/`:1559` (`send_document`), `:1818`
  (`handle_attachment`), `:1849–1852` (routed conversation), `:1878` (max_bytes).
- `bot/sender.py:19–20` (`TELEGRAM_DOCUMENT_MAX_BYTES=50 MiB`), `:31`/`:61–76` (send_document wrapper).
- `bot/app.py:34`/`:157–161` (attachment filter), `:86` (`concurrent_updates(True)`), `:227–241`
  (reaper wiring), `:265` (Watcher).
- `bot/config.py:262` (`MINI_APP_ENABLED=False`), `:242–266` (public HTTPS requirement).
- `bot/web/app.py:36`/`:203` (session cookie), `:95–108` (`_attachment`), `:432` (`_guarded`),
  `:714` (`conversation_reply`), `:733` (`conversation_export`), `:753`/`:768`
  (`conversation_files`/`conversation_file_preview`).
- `bot/web/services.py:878–890` (FileService ownership).
- `tests/frontend/dom_stub.js:336–342` (Blob download stub).

**Decision records**
- `docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md:148–152` (D-02/D-03/D-04/D-06),
  `:158` (D-12), `:161` (D-15), `:162` (D-16), `:710`/`:1236` (B1–B3 not authorized),
  `:1042–1060` (D-22), `:1908–1918` (§6.3 classification), `:2250–2256` (I2/I3).
- `docs/proposals/OHB2-P0-STAGED-IMPLEMENTATION-PLAN.md:739`, `:756`, `:768` (Stage B1/B2/B3).
- `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md:1637`, `:1804`, `:1846`
  (F4 ≠ proof of read).

**Plan 08 / reviews**
- Corrected design `docs/reviews/OHB2-PLAN-08-MANUAL-ATTACHMENT-TRANSFER-UX-DESIGN.md` §4–§10, §17.
- First review `docs/reviews/OHB2-REVIEW-PLAN08-MANUAL-ATTACHMENT-TRANSFER-UX-DESIGN.md` §5–§14.
- Second review `docs/reviews/OHB2-REVIEW-PLAN08-DESIGN-REMEDIATION.md` §6–§16.

---

## 18. Approval status and explicit exclusions

**STATUS: `PROPOSED — OWNER DECISION REQUIRED`.**

Explicitly:
- **No option has been selected.** (MT-1, MT-2, and Defer are all open.)
- **D-22 remains unresolved.**
- **No schema change is approved.**
- **No implementation is approved.**
- **No remote-delivery work is approved.**
- **No Plan 07-B or Plan 07-C work is approved.**
- **No runtime activation is approved.**
- **No commit, push, PR, merge, release, or deployment is authorized.**

**NO OPTION IS SELECTED BY THIS DOCUMENT. THE OWNER MUST DECIDE AFTER REVIEWING THE TRADE-OFFS AND
PREREQUISITES.**

---

> Evidence labels: **[F]** verified against current source this session · **[I]** inference ·
> **[U]** unverified · **[G]** documented-but-untested · **[R]** recommendation ·
> **[OWNER]** owner decision. This is a decision-preparation artifact; it is **not** an approved
> owner record.
