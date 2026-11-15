# OHB2-PLAN-08 — Manual Attachment Transfer UX Design

- **Task ID:** `OHB2-PLAN08-MANUAL-ATTACHMENT-TRANSFER-UX-DESIGN`
  (remediated under `OHB2-REMEDIATE-PLAN08-MANUAL-ATTACHMENT-TRANSFER-DESIGN`).
- **Type:** Investigation + UX/product/technical **design only**. **No implementation.**
- **Author:** OpenHands agent (autonomous). Self-reviewed and remediated; **not** independently
  reviewed.
- **Date:** originally 2026-11-14; **remediated 2026-11-15** against
  `docs/reviews/OHB2-REVIEW-PLAN08-MANUAL-ATTACHMENT-TRANSFER-UX-DESIGN.md`.
- **Final verdict (revised):** **`DESIGN REMEDIATED — OWNER DECISIONS STILL OPEN`** (see §1, §17).
- **Remediation verdict:** **`REMEDIATION COMPLETE WITH OPEN OWNER DECISIONS`**.

> **Evidence labels:** **[F]** verified against current source/repo this session · **[F-R]**
> verified in source *after* being raised by the independent review · **[I]** inference ·
> **[U]** unverified/unknown · **[G]** documented-but-untested · **[R]** recommendation ·
> **[OWNER]** owner decision.
>
> **Provenance of claims:** the independent review
> (`docs/reviews/OHB2-REVIEW-PLAN08-MANUAL-ATTACHMENT-TRANSFER-UX-DESIGN.md`, sha256
> `71cc88c8…`, immutable) is treated as **evidence to investigate**, not as authority. Every
> review finding was **re-verified against current source** before this document was corrected;
> results are in §18.

---

## 1. Task ID and verdict

**Task ID:** `OHB2-PLAN08-MANUAL-ATTACHMENT-TRANSFER-UX-DESIGN`.

**Owner-approved direction applied:** adopt **manual attachment transfer** as the **temporary**
supported path; keep **provider-verified delivery (U-12/U-3/D-04)** as the long-term target;
**best-effort automatic delivery is rejected**; never claim remote delivery without sufficient
evidence.

**Revised verdict: `DESIGN REMEDIATED — OWNER DECISIONS STILL OPEN`.**

- The design's **factual base is source-verified** (§4, §5, §6).
- **No user-facing retrieval path exists today** (§4): no bot send-back of staged bytes, no Mini App
  download of staged bytes, no other route that reads `attachment_staging/`.
- The earlier claim that a safe implementation **"does not require a schema change"** was
  **incorrect for MT-1** and is withdrawn (§6, §7). MT-1 **requires a new durable
  Telegram-document operation**, which is blocked by **D-22** (owner).
- The earlier **B1-first recommendation is withdrawn** (§8): it was asserted, not derived. MT-1 and
  MT-2 are compared source-backed, and **neither is approved**.
- **No option may be selected or implemented until the owner resolves the decisions in §17.**

**Scope of this task:** documentation/design remediation only. **No implementation occurred** (§21).

---

## 2. Owner-approved direction and authorization boundary

**Direction (unchanged):**
- Manual attachment transfer = temporary supported direction.
- Reliable provider-verified delivery = long-term goal (U-12/U-3/D-04/D-06/D-02/D-03).
- Best-effort automatic delivery = **rejected**.
- Delivery guarantees must **not** be weakened.
- Local staging, user retrieval, user-initiated OpenHands upload, and independently verified remote
  delivery must remain **distinct events** (§12).

**Authorized by this task:** inspect source/docs; correct this document; reassess the alternatives
from source; fix inaccurate statements, naming conflicts, security analysis, UX copy, and
implementation prerequisites; append a remediation record to `.agent/PROGRESS.md`; run read-only
documentation checks.

**Not authorized (explicitly):** implement MT-1/MT-2/MT-3 or any attachment-transfer feature;
modify runtime/frontend code, tests, schema, migrations, config, dependencies, or deployment files;
change attachment lifecycle behavior; change the outbox or add an operation type; create a retrieval
endpoint, public URL, download token, or storage mechanism; resolve D-22 or any owner decision;
start Plan 07-B/07-C; commit/push/PR/merge/release/deploy/Autopush.

---

## 3. Baseline state and evidence (verified this session)

### 3.1 Git state

- **[F]** Repo `/workspace/project/OpenHandBot`; branch **`main`**;
  **HEAD = `main` = `origin/main` =** `facf1f42578a20a4a37e220eca016ce3d534e750`;
  divergence `git rev-list --left-right --count origin/main...HEAD` → **`0  0`**.
- **[F] `git status --short`:**
  - ` M .agent/PROGRESS.md` (pre-existing append-only from earlier sessions)
  - `?? docs/reviews/OHB2-REPAIR-PLAN-05-SECURE-ATTACHMENT-DELIVERY-INVESTIGATION.md`
  - `?? docs/reviews/OHB2-REPAIR-PLAN-06-ATTACHMENT-DELIVERY-ALTERNATIVE-ARCHITECTURE.md`
  - `?? docs/reviews/OHB2-PLAN-07-A-SECURE-PULL-FEASIBILITY-INVESTIGATION.md`
  - `?? docs/reviews/OHB2-PLAN-07-A2-DELIVERY-IDENTITY-AND-EVIDENCE-RESOLUTION.md`
  - `?? docs/reviews/OHB2-PLAN-08-MANUAL-ATTACHMENT-TRANSFER-UX-DESIGN.md` (this file)
  - `?? docs/reviews/OHB2-REVIEW-PLAN08-MANUAL-ATTACHMENT-TRANSFER-UX-DESIGN.md` (immutable review)
- **[F] Staged:** none. **Ignored (relevant):** `.openhands/`, `.pytest_cache/`, `__pycache__/`.
- **[F] Pre-existing artifacts preserved:** the five untracked reports + the modified PROGRESS
  (all left untouched; hashes in §3.2).

### 3.2 Report hashes (verified **unchanged** before and after remediation)

| Report | Lines | SHA-256 |
| --- | --- | --- |
| Plan 05 | 428 | `4944714a3469894a01093619a2b75072eb65b403eb3df665db520b35c857e676` |
| Plan 06 | 617 | `4450b77cb9981d4997a4f7cb41f3cb3e4821aad93d4d74b7ea982bedd1920303` |
| Plan 07-A | 509 | `8faec96b3c4844fb36d5b793b72fce340f837a3e2aa67a2cbee2d3a6a5e88d90` |
| Plan 07-A2 | 451 | `8aa583d2a315af60f69e5f7aa55959d44f9df6afb0f84f8306937b3bac1dffbc` |
| **Plan 08 (this file, pre-remediation)** | 419 | `18b29203283cfc70319561969d0e182215f4bbd7b4cabb42060f3a7a486da7ab` |
| Independent review (immutable) | 406 | `71cc88c8f2cddc74867bb8809c2e7c897cb18ecf081c87f345772f52003f3bc5` |

### 3.3 Runtime state

- **[F] `MINI_APP_ENABLED`** default **`False`** (`bot/config.py:262`); code refuses to enable it
  without a public HTTPS `MINI_APP_URL`.
- **[F] Autopush:** no `autopush`/`main.py` process running.
- **[F] `concurrent_updates(True)`** present (`bot/app.py:86`) — **unchanged** (must stay so).
- **[F] `ATTACHMENT_DOCUMENT_INTAKE_ENABLED`** default **`True`** (`bot/config.py:315–316`).
- **[F] `.openhands/`** present and **untouched**.

---

## 4. Verified attachment lifecycle (source-verified)

### 4.1 Text flow

```
Telegram message (Document only)  ── filters.Document.ALL ──►  handlers.handle_attachment
  (bot/app.py:159 SUPPORTED_ATTACHMENT_FILTER=filters.Document.ALL:34; bot/handlers.py:1818)
        │
        ├─ _guard: allowed user + PRIVATE chat            (handlers.py:234; _allowed:53)
        ├─ intake switch ATTACHMENT_DOCUMENT_INTAKE_ENABLED (handlers.py:1836–1848)
        ├─ requires an OPEN routed conversation (user_state kind=='route')  (handlers.py:1849–1852)
        ├─ needs a downloadable file_id                   (handlers.py:1860–1876)
        │
        └─ AttachmentService.accept(...)                   (attachments.py:822)
              ├─ (1) _authorized(conversation_id)  ── ownership + deletion witness, fail-closed
              │        (attachments.py:815; via files.authorize_conversation_detailed:220)
              ├─ (2) declared-size normalize + precheck_rejection (ext/denied)   (attachments.py:328,430)
              ├─ (3) classify_incoming_file  → NEW | APPEND | EXPIRED   (attachments.py:430)
              ├─ (4) ROW-FIRST: durable item row (status 'pending') written
              │        accept_attachment_item[_into_new_batch]  (db.py:1734/1782)
              ├─ (5) chunks_factory() → bounded Telegram stream (FIX-01/02)   (handlers.py:1740)
              └─ (6) StagingStore.store(...)   (attachments.py:609)
                       ├─ O_CREAT|O_EXCL|O_NOFOLLOW under 0700 root   (attachments.py:585–594)
                       ├─ hard byte cap = min(file cap, total, per-batch)  (_effective_cap:569)
                       ├─ verify: written>0 + magic-byte deny list   (attachments.py:718–740)
                       └─ atomic CAS → item status 'stored'   (try_mark_attachment_item_stored:1224)
        │
        └─ reply text (only after the durable row exists)   (handlers.py:1903–1930)
```

### 4.2 Findings (each with source)

- **[F] Where bytes are stored:** `<db_dir>/attachment_staging/` (dir mode `0700`; file mode `0600`),
  filename = **opaque random token** (`secrets.token_hex(16)` → 32 hex chars).
  Source: `attachments.py` (`STAGING_DIRNAME`:108, `STAGING_DIR_MODE`:109, `STAGING_FILE_MODE`:110,
  `_TOKEN_HEX_BYTES`:111, `new_staging_token`:199, `staging_root_for`:204, `store`:609,
  `os.open`:585).
- **[F] Owner of bytes + metadata:** the **single `Database` (SQLite)** owns all metadata
  (`attachment_batches`, `attachment_items`, `attachment_message_identity`); the filesystem holds
  only opaque byte files. **One** SQLite owner (shared by bot + Mini App). Source:
  `db.py:560–565` (`PRAGMA foreign_keys=ON`, fail-closed).
- **[F] Identity association:**
  - user + conversation + batch: `attachment_batches(telegram_id, conversation_id, batch_id)`.
  - item→bytes: `attachment_items(item_id, batch_id, staging_token, display_name, size_bytes,
    status)`.
  - message↔batch legal identity: `attachment_message_identity(telegram_id, chat_id, message_id,
    batch_id, conversation_id)`, **PK `(telegram_id,chat_id,message_id)`**, FK `ON DELETE RESTRICT`.
    Source: table DDL `db.py:804–813` (D-33/D-35 comments at `db.py:797–803`).
  - **[F] The Telegram `file_id` is NOT stored** anywhere (no `file_id` column exists). The bytes are
    the only copy the bot retains.
- **[F] Implemented vs reachable batch states.** Defined: `pending`, `intent_recorded`,
  `dispatching`, `uncertain`, `delivered`, `expired`, `rejected`, `failed`
  (`db.py:121–136`). **Actually written:** `pending` (insert, `attachments.py:704`),
  `intent_recorded` (`db.py:1630` CAS), `expired` (`attachments.py:869`, `:1128`).
  **Never written:** `dispatching`, `uncertain`, `delivered`, `rejected`, `failed`.
  → `delivered` is **unreachable**; **no remote delivery path exists**.
- **[F] Item states:** `pending` → `stored` (atomic CAS, `db.py:1224`) → `reaped` (`db.py:1463`;
  constant `db.py:171–175`).
- **[F] Expiry / cleanup / deletion:** fixed **15-minute** `T0` deadline
  (`ATTACHMENT_BATCH_TTL = timedelta(minutes=15)`, `db.py:261`); the **existing** `Watcher` tick
  drives an `OpportunisticSweeper` (`attachments.py:1376`, `maybe_sweep`:1432;
  wired `bot/app.py:227–241`). The reaper **DB-first** marks expired, then unlinks bytes with strict
  guards (`_remove_file` `attachments.py:1316`; token must be a single safe path segment +
  `_is_within`:284 + `lstat` + regular-file only; symlinks/other ⇒ `unsafe`, left alone). `sweep`:
  `attachments.py:1020`.
- **[F] Missing / expired / inaccessible / corrupted / partial:**
  - missing byte file on cleanup ⇒ `absent` = idempotent success (`attachments.py:1334`).
  - expired batch ⇒ refuses new files; a new batch starts (`attachments.py:865–871`).
  - partial write ⇒ the file is written **fully** then verified; on any failure it is unlinked and
    the item is left `pending` (never `stored`). Source: `attachments.py:718–768`.
  - **[U] Corrupted-after-store:** there is **no** post-store integrity re-verification (no read of
    staged bytes exists at all — §4.3).
- **[F] Original filename / MIME safety:** `display_name` is sanitized (`sanitize_display_name`,
  `attachments.py:212`) and stored as **metadata only**; it is **never** used as a path. The actual
  filename is the opaque token. **MIME type is not stored.**
- **[F] Size/integrity on retrieval:** **N/A — there is no retrieval.** Size is verified at **store**
  time (`written`, `size_bytes`) and via a magic-byte deny list (`attachments.py:718–740`;
  `_read_head`/`_HEAD_BYTES=4096` at `:322–325`, `:112`).
- **[F] Retrieve more than once / retrieval changes state:** **not possible today** — a repo-wide
  grep for staged-byte reads outside `attachments.py`/`db.py` returns **nothing**.
- **[F] Authorization:** intake requires an **allowed user in a private chat** (`_allowed`,
  `handlers.py:53`) **and** an authorized conversation (`_authorized`, `attachments.py:815`). There
  is **no read endpoint**, so cross-user retrieval is moot today; any future retrieval must reuse
  this ownership model.

### 4.3 Explicit distinction

- **[F] IMPLEMENTED:** bounded Telegram intake, local staging, identity tracking, expiry/cleanup,
  receipt replies.
- **[F] NOT IMPLEMENTED:** any retrieval of staged bytes; any manual-transfer workflow; any remote
  delivery; any user-visible statement that the file is "not delivered to OpenHands".

---

## 5. Correct application-level file-size limits (F-01)

**Remediation of review finding F-01.** The previous revision stated *"incoming Telegram downloads
are capped at 20 MB for the bot"* and used that as fact. **That claim is withdrawn**: the repository
contains **no** 20 MB constant (grep of `bot/` for `20 MB` / `20971520` returns nothing), and the
figure is **not** independently verified here. The 20 MB number appears only inside unrelated
*proposal* text (`docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md:317`, a **proposal**,
not a contract).

The verified limits, by scope:

| # | Limit | Verified value | Scope | Source | Status |
| --- | --- | --- | --- | --- | --- |
| L1 | **Application-level intake cap (per file)** | **3 MiB** = `3 * 1024 * 1024` = 3 145 728 bytes | every accepted Telegram attachment | `attachments.py:99` (`MAX_ATTACHMENT_BYTES`); defaults at `:332`, `:468`; applied via `service.store.max_bytes` → `handlers.py:1878` → `_download_attachment_chunks(..., max_bytes)` | **[F] ENFORCED** |
| L2 | **Actual staged-file validation** | hard byte cap = `min(file cap, remaining total, remaining per-batch)` | staging write | `attachments.py` `_effective_cap`:569, `_write_to_path`:585 (counts bytes, aborts on overflow) | **[F] ENFORCED** |
| L3 | **Additional staging quotas** | `MAX_ITEMS_PER_BATCH = 10`; `MAX_STAGING_TOTAL_BYTES = 64 MiB` | **DISABLED by default** (`None`) until explicitly configured (D-12) | `attachments.py:105–106`; `StagingStore.__init__` (`max_items_per_batch`/`max_total_bytes` default `None`) | **[F] DEFINED BUT NOT ENFORCED BY DEFAULT** |
| L4 | **Bot-API document upload cap (outgoing)** | `TELEGRAM_DOCUMENT_MAX_BYTES = 50 * 1024 * 1024` (50 MiB) | **outgoing** `send_document` only (reply `.txt`, export zip) | `sender.py:19–20`, `:67–71` | **[F] ENFORCED (outgoing)** |
| L5 | **Telegram incoming-download cap** | **not stated in this repo** | external Telegram/Bot-API behavior | none | **[U] UNVERIFIED — must not be asserted as fact** |
| L6 | **Future download/streaming constraint** | none today (no retrieval path) | — | — | **[F] NOT IMPLEMENTED** |
| L7 | **Mini App export/response caps** (unrelated to intake) | `MAX_EXPORT_BYTES = 16 MiB`; `MAX_FILE_RESPONSE_BYTES = 256 KiB`; `MAX_FULL_REPLY_CHARS = 100 000` | Mini App export/file/reply only | `openhands_client.py:34`, `:28`; `web/services.py:53` | **[F] ENFORCED (different path)** |

**Precise scope note (requirement 6):** L1 is enforced on **every accepted Telegram attachment**
because the only production service is built with the default `StagingStore` (`_attachment_service`,
`handlers.py:1684–1691`) and `handle_attachment` reads `service.store.max_bytes` (`handlers.py:1878`).
The 3 MiB cap is **not** a universal limit across the whole app — it is the **attachment-intake** cap
(L4/L7 are unrelated outgoing/export caps).

**Conclusion:** the only supportable statement about incoming attachment size is the **enforced 3 MiB
application cap (L1/L2)**. No claim about Telegram's own incoming limit (L5) is made. A future
retrieval path (L6) has no size behavior yet.

---

## 6. Current outbox contract (F-02)

**Remediation of review finding F-02.** The previous revision implied MT-1 could ride the existing
outbox with no schema change. **That is withdrawn.** The outbox is **text-only and targets
OpenHands**, not Telegram.

### 6.1 Existing outbox contract (source-verified)

- **[F] Schema** (`db.py:608–621`): `outbox(id, conversation_id, chat_id, text, status, error,
  created_at, updated_at, attempts, client_ref, notify_state)`. **No payload/blob column** and **no
  operation-kind column** — the only payload is `text`.
- **[F] Payload representation:** a single `text` string.
- **[F] Target/service:** `client.send_message(conversation_id, text)` →
  `POST /app-conversations/{id}/send-message` on **OpenHands** (`openhands_client.py:337–339`),
  **not** Telegram.
- **[F] Dispatch behavior:** CAS-driven `pending` → `claimed` → `sending`
  (`db.claim_outbox`:3346; `OUTBOX_*` constants `db.py:67–73`), then `_post_claimed` (`outbox.py:298`)
  performs the single POST at `outbox.py:452`.
- **[F] Retry / recovery:** `_recover_pre_cas_unexpected` (`outbox.py:~250`) returns a **pre-CAS**
  record to `pending` under the existing attempt policy (`bump_outbox_attempt`, `MAX_OUTBOX_ATTEMPTS`);
  **post-CAS** failures are **never** auto-retried.
- **[F] Uncertain-send handling:** confirmed rejection (`is_permanent`/4xx) ⇒ `failed`; network /
  timeout / 5xx / 429 ⇒ **`unknown`** (no auto-retry); `CancelledError` mid-send ⇒ `unknown` and the
  cancellation is **re-raised** (`outbox.py:447–470`). This is **at-most-once**, **not**
  exactly-once.
- **[F] Telegram document operations today:** **none.** The outbox has **no** document/file payload,
  no `InputFile`, and no Telegram send call.
- **[F] Completion kinds** (`COMPLETION_KIND_OUTBOX`/`COMPLETION_KIND_CREATION`, `db.py:179–180`) are
  **completion bookkeeping**, not payload kinds — they do not make the outbox carry documents.

**Conclusion:** the existing OpenHands text-message outbox is **not** a Telegram document outbox and
**cannot** perform MT-1 as-is.

### 6.2 MT-1 requirements (architectural alternatives — not chosen, not implemented)

MT-1 (Telegram send-back) **cannot** be treated as an already-supported operation. Two
architecture-compatible alternatives exist; **neither is selected**:

**Alternative A — a separately approved durable Telegram-document operation** integrated with the
existing ownership/lifecycle rules (e.g. an owner-approved extension of the durable-operation
mechanism). **Alternative B — another explicitly designed durable mechanism** proven compatible with
the approved architecture (e.g. an owner-approved separate dispatch table — the register's D-22
option "B").

For **each** alternative:

| Requirement | Alternative A | Alternative B |
| --- | --- | --- |
| Required persistence | durable record with a **document payload reference** (e.g. item id/`staging_token`) + status | durable dispatch record + payload reference |
| Attachment identity & ownership | `telegram_id` + `conversation_id` + item id; reuse `_allowed` + `_authorized` | same |
| Staged-file availability until dispatch | **must** keep the bytes alive until terminal send outcome — conflicts with the 15-min reaper (§13) | same |
| Crash recovery | reuse pre-CAS/post-CAS split (never auto-retry post-CAS) | same |
| Duplicate / uncertain semantics | CAS + `unknown`, **no** exactly-once claim | same |
| Cleanup coordination | required (new invariant; §13) | required |
| Schema migration | **YES** (new payload/kind or table) | **YES** (new table) |
| D-22 resolution | **REQUIRED** | **REQUIRED** |
| Required tests | identity/ownership, crash windows, duplicate, uncertain, expiry race | same |

**No schema or SQL is specified here as approved** — these are requirements, not a design, and the
mechanism must be chosen by the owner (D-22).

### 6.3 D-22

**[F] D-22** (`docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md:1042–1060`) is an **owner
(integration) decision**, status **unresolved**, listed as a **blocking** decision (register §6.3,
§7). It requires either **(a)** a new outbox payload capability or **(b)** another explicitly
owner-approved mechanism. **MT-1 implementation is blocked by D-22** and **must not** be labeled
implementation-ready while D-22 is unresolved. This document does **not** resolve D-22.

---

## 7. MT-1 / MT-2 / MT-3 comparison (F-03)

**Remediation of review finding F-03.** The previous "implement B1 first" recommendation is
**withdrawn**; the comparison below is source-backed and does not presuppose a winner.

### 7.1 Option MT-1 — Telegram send-back

The bot sends the locally staged attachment back to the requesting Telegram user.

- **[F] Existing Telegram API support:** `bot.send_document(..., InputFile(buffer, filename))` is
  already used (`handlers.py:1460`, `:1559`; `sender.py:31`, `:71`) — **but all in-memory and for
  other content**, not staged bytes.
- **[F] Existing `send_document` wrapper/usage:** `sender.py:61–76` uploads in-memory via `InputFile`
  (no temp files).
- **[F] Outbox compatibility:** **incompatible as-is** — outbox is text-only (§6.1).
- **[F] Required durable semantics:** a new durable document operation (§6.2) — **schema change**.
- **[F] Schema/architecture impact:** **YES** (new payload/kind or table); D-22 required.
- **[F] Telegram acceptance vs user receipt:** `send_document` success = **API acceptance**, not
  confirmed user download.
- **[F] Duplicate / uncertain risk:** real; must reuse CAS + `unknown` (§14); **no** exactly-once.
- **[F] Expiry/cleanup race:** real — the 15-min reaper can delete bytes before/while a send
  operation runs (§13).
- **[F/I] Android / weak-network usability:** **[I]** works inside Telegram without a WebView
  download; weak-network behavior is **UNVERIFIED**.
- **[F] Authorization & attachment identity:** reuse `_allowed` (`handlers.py:53`) + `_authorized`
  (`attachments.py:815`) + item/batch identity.
- **Status: `REQUIRES IMPLEMENTATION`** (plus a durable-operation decision).

### 7.2 Option MT-2 — Mini App download

The authenticated Mini App downloads the locally staged attachment.

- **[F] Existing authentication/session model:** `_guarded` (rate-limit → session → `_allowed` →
  Origin for state-changing) + server-side conversation ownership (`app.py:432–451`;
  `services.py:883`).
- **[F] Existing attachment retrieval routes:** `GET …/export` (OpenHands trajectory **zip**,
  `app.py:733–751`) and `GET …/file?path=` (**text preview of existing workspace files**,
  `MINI_APP.md:649`).
- **[F] Does any current route read `attachment_staging`?** **No** (repo-wide grep).
- **[F] Required endpoint / reusable capability:** a **new cookie-auth staged-download route**; can
  reuse `_guarded` + `_attachment` (`app.py:95–108`) — **no new bearer token, no public URL**.
- **[F] Ownership & conversation authorization:** reusable.
- **[F] Path traversal / symlink protections:** reusable (`staging_token` + `_is_within` +
  `lstat`).
- **[F] Bounded streaming & response size:** `_attachment` reads bytes **fully into memory** and has
  **no `Range`/206** support (grep); a future route should stream and cap.
- **[F] Expiry/cleanup coordination:** required (§13).
- **[U] Browser & Telegram WebView support:** Blob download is exercised **only** in the Node DOM
  stub (`tests/frontend/dom_stub.js:336–342`); **no real Telegram Android WebView test exists** ⇒
  **UNVERIFIED**.
- **[I] Android download behavior:** **[U]**.
- **[F] Frontend complexity & accessibility:** new UI + RTL/keyboard handling required.
- **[F] Schema / new durable operation required?** **No** — a route reads existing metadata; **no**
  schema change and **no** new durable operation. (But a **scope** decision is required.)
- **Status: `REQUIRES IMPLEMENTATION`** (WebView behavior `UNVERIFIED`).

### 7.3 Option MT-3 — other existing retrieval path

- **[F]** `GET …/file?path=` = text preview of an **existing workspace** file, not staged bytes.
- **[F]** `GET …/reply` + `send_text_document` = a **.txt of the assistant reply**, not the
  attachment.
- **[F]** No bot command/callback retrieves a staged attachment (handler registration,
  `bot/app.py:108–170`).
- **Status: `NOT FEASIBLE`** (no existing flow returns staged bytes). **No third option is
  invented.**

### 7.4 Mandatory comparison matrix

| Dimension | MT-1 Telegram send-back | MT-2 Mini App download | MT-3 Other existing path |
| --- | --- | --- | --- |
| Existing usable capability | **EXISTING AND USABLE** (`send_document`/`InputFile`) | **EXISTING AND USABLE** (`_guarded` + `_attachment`) | **NOT FEASIBLE** |
| New runtime implementation | **REQUIRES IMPLEMENTATION** | **REQUIRES IMPLEMENTATION** | **NOT FEASIBLE** |
| Durable persistence required | **REQUIRES IMPLEMENTATION** (new document op) | **EXISTING AND USABLE** (existing metadata; none new) | — |
| Schema impact | **REQUIRES IMPLEMENTATION** (new payload/kind or table) | **EXISTING AND USABLE** (none) | — |
| D-22 dependency | **REQUIRED** (blocks MT-1) | **EXISTING AND USABLE** (D-22 is outbox-specific; N/A) | — |
| Authentication/authorization | **EXISTING AND USABLE** (reuse `_allowed`+`_authorized`) | **EXISTING AND USABLE** (reuse `_guarded`+ownership) | **NOT FEASIBLE** |
| Attachment identity | **EXISTING AND USABLE** (item/batch rows) | **EXISTING AND USABLE** (item/batch rows) | — |
| Expiry/cleanup race | **UNVERIFIED** (needs new invariant; §13) | **UNVERIFIED** (needs new invariant; §13) | — |
| Duplicate/uncertain operation | **REQUIRES IMPLEMENTATION** (CAS + `unknown`; §14) | **EXISTING AND USABLE** (idempotent GET; no durable op) | — |
| Android usability | **UNVERIFIED** | **UNVERIFIED** (WebView) | — |
| Telegram WebView verification | **EXISTING AND USABLE** (no WebView needed) | **UNVERIFIED** (no device evidence) | — |
| Security risk | **MEDIUM** (send-side; reuses ownership) | **MEDIUM** (read-side; reuses ownership; no public URL) | — |
| Testing requirements | **REQUIRES IMPLEMENTATION** (crash/duplicate/race) | **REQUIRES IMPLEMENTATION** (route/WebView/stream) | — |
| Owner approval required | **REQUIRED** (D-22 + scope + wording) | **REQUIRED** (scope + WebView verification + wording) | — |

*Cells marked `UNVERIFIED` are missing evidence, not assumptions.*

---

## 8. Reasoned recommendation (unresolved trade-offs)

The previous "MT-1 first" recommendation is **withdrawn**. On the current source evidence, the
trade-off is **not** one-sided:

| Criterion | Stronger option | Why (evidence) |
| --- | --- | --- |
| Lowest implementation complexity | **MT-2** | new cookie-auth route reusing `_guarded`+`_attachment`; **no** schema change, **no** durable op (§7.2) |
| Lowest architectural impact | **MT-2** | no outbox change, no D-22, no new durable state (§6, §7.2) |
| Strongest security properties | **MT-1 and MT-2 tie** | both reuse `_allowed`/`_authorized`/`_guarded`, token-only names, no public URL |
| Best Android user experience | **MT-1 (inferred)** | works inside Telegram without a WebView download — **[I]/[U]** |
| Most reliable under weak connectivity | **UNVERIFIED** | no evidence for either |
| Most practical verification path | **MT-1** | no real-device WebView dependency; MT-2 requires real Telegram Android WebView verification (§7.2) |

**No option should be selected until the owner resolves the relevant decisions (D-22 and scope).**
MT-2 has the **smaller architectural footprint** but carries an **UNVERIFIED** real-device WebView
risk; MT-1 avoids the WebView risk but **requires a new durable Telegram-document operation** and
**D-22**. The report therefore does **not** declare either option approved or preferable overall.

---

## 9. Terminology glossary (F-04)

**Remediation of review finding F-04.** The previous revision used **B1/B2/B3** for manual-retrieval
options, colliding with the remote-delivery **Stage B1/B2/B3** used elsewhere. That usage is
**removed**.

| Term | Meaning | Status |
| --- | --- | --- |
| **MT-1** | Telegram send-back of a locally staged attachment | manual-transfer option (this document only) |
| **MT-2** | Mini App download of a locally staged attachment | manual-transfer option (this document only) |
| **MT-3** | Any other existing retrieval path | `NOT FEASIBLE` today |
| **Stage B1** | Remote **transport**: create-op upload + narrow auth | remote-delivery stage — **`NOT AUTHORIZED TO START`** |
| **Stage B2** | Remote **reconciliation** (status endpoint) + uncertain handling | remote-delivery stage — **`NOT AUTHORIZED TO START`** |
| **Stage B3** | Remote **delivery to the same conversation** + outbox integration | remote-delivery stage — **`NOT AUTHORIZED TO START`** |

- **`MT-*` identifiers belong exclusively to the manual-transfer UX design.**
- They are **distinct** from the remote-delivery **Stage B1/B2/B3**
  (`docs/proposals/OHB2-P0-STAGED-IMPLEMENTATION-PLAN.md:739`, `:756`, `:768`) and from the
  register's **B1–B3** (`docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md:710`, `:1236`), which
  are **`NOT AUTHORIZED`**.
- **The remote-delivery stages remain unauthorized and are not started by this task.** The historical
  Plan 07 / other reports are **not** renamed.

---

## 10. Arabic RTL UX wording (S-13)

**Remediation of review finding S-13.** All wording below is **PROPOSED — NOT IMPLEMENTED** and
requires **owner wording approval** (§17). No message may claim remote success without evidence.

### 10.1 Attachment received and staged locally

Only after the staging operation **actually succeeded** (item `status='stored'`):

```
✅ استلمت الملف وخزّنته محليًّا في OpenHandBot.
⚠️ لسه ما اترفعش لـ OpenHands — التخزين محلي عندنا بس.
```

If only the durable row exists but bytes are **not** stored (`pending`):

```
⏳ سجّلت الملف — لسه بيتم التخزين. مش مرفوع لـ OpenHands.
```

### 10.2 Manual retrieval becomes available (PROPOSED future UX — MT-1)

```
📎 الملف جاهز للتنزيل من هنا.
بعد ما تنزّله: افتح محادثة OpenHands المقصودة وارفع الملف بنفسك.
```

*(until MT-1 exists — the honest current message):*

```
⚠️ التنزيل الذاتي لسه مش متاح في النسخة الحالية.
الملف محفوظ محليًّا بس، ومش متسلّم لـ OpenHands.
```

### 10.3 Telegram send-back accepted (PROPOSED — MT-1, if later implemented)

```
📤 بعتّ الملف ليك في الشات ده (تيليجرام استقبل الإرسال).
⚠️ ده مش معناه إن OpenHands استلمه — لازم ترفعه بنفسك.
```

*Distinguishes:* Telegram **API acceptance** ≠ confirmed user download ≠ OpenHands upload. **Never**
says OpenHands received the file.

### 10.4 Mini App download completed (PROPOSED — MT-2, if later implemented)

```
⬇️ تم تنزيل الملف في المتصفح.
⚠️ ده مش معناه إن OpenHands استلمه — لازم ترفعه بنفسك.
```

*Distinguishes:* the **HTTP download** completed ≠ OpenHands upload.

### 10.5 Expired or missing local attachment

```
⌛ الملف المحلي مش متاح (انتهت صلاحية الـ 15 دقيقة). ابعت الملف تاني لو محتاجه.
```

*States only that the **local staged file** is unavailable. Makes **no** claim about the remote
workspace.*

### 10.6 Retrieval failure

```
⚠️ التنزيل ماكملش. جرّب تاني.
لو استمرّت المشكلة، ابعت الملف من جديد.
```

*Does not claim the file is still available unless that is verified.*

### 10.7 Manual OpenHands upload instructions

```
1) نزّل الملف (لما تكون ميزة التنزيل متاحة).
2) افتح محادثة OpenHands المقصودة.
3) ارفع الملف جواها بنفسك.
4) اتأكّد إنه ظهر في مساحة العمل الصح.
```

*Explicit honest limitation:*

```
🔔 OpenHandBot مايقدرش يتأكد إنك رفعت الملف لـ OpenHands. التأكيد لازم يكون منك جوه OpenHands.
```

### 10.8 Status terminology (conceptual UX labels — NOT database states)

| Label | Meaning | Evidence today |
| --- | --- | --- |
| `LOCAL_STAGED` | bytes stored locally | **[F]** item `status='stored'` |
| `RETRIEVAL_AVAILABLE` | retrieval offered | **future state only** (not implemented) |
| `TELEGRAM_SEND_ACCEPTED` | Telegram API accepted a send | **future operation result only** |
| `USER_DOWNLOAD_COMPLETED` | user downloaded | **only if technically observable** |
| `USER_ASSERTED_OPENHANDS_UPLOAD` | user *says* they uploaded | user statement, **not** verification |
| `REMOTE_DELIVERY_VERIFIED` | independent verified delivery | **not currently reachable** |

These are **conceptual labels, not approved database states**. **No** database state, column,
lifecycle transition, or event record is added by this document.

---

## 11. Security threat model

| Risk | Severity | Status | Basis |
| --- | --- | --- | --- |
| Cross-user / cross-conversation access | High | **MITIGATED (intake); must be reused** | `_allowed`+private (`handlers.py:53`), `_authorized` (`attachments.py:815`) |
| IDOR / authz bypass | High | **MITIGATED (partial)** | identity by server-side session/conversation id, never client path (`app.py:432`; `services.py:883`) |
| Path traversal / symlink | High | **MITIGATED** | token-only names, `O_NOFOLLOW`, `_is_within`, `lstat` (`attachments.py:585`, `:284`, `:1316`) |
| Unsafe filenames / MIME | Medium | **MITIGATED** | `sanitize_display_name` (metadata only), ext + magic deny lists (`attachments.py:212`, `:117–148`) |
| Unbounded memory / streaming | Medium | **PARTIALLY MITIGATED** | intake streamed with hard cap (`handlers.py:1740`); `_attachment` reads fully (bounded) |
| Large-file handling / interrupted download | Medium | **PARTIALLY MITIGATED** | intake cap + `_TooLargeError`; retrieval path not built |
| Expired / deleted staged file | Medium | **MITIGATED (cleanup)** | reaper DB-first, idempotent `absent` (`attachments.py:1020`, `:1334`) |
| **Retrieval vs cleanup race** | Medium | **FUTURE RISK — NOT MITIGATED (no retrieval)** | needs a new invariant (§13) |
| **Duplicate Telegram sends (MT-1)** | Medium | **FUTURE RISK — NOT MITIGATED** | needs a durable CAS (§14); D-22 |
| Sensitive content in logs/URLs/history | Medium | **MITIGATED (partial)** | token names, no content logs; a download URL must not embed content/paths |
| Internal filesystem path exposure | Low | **MITIGATED** | no path in responses; static confined to `STATIC_DIR` (`app.py:1110`) |
| Mini App session abuse | Medium | **MITIGATED (partial)** | session cookie + rate-limit + Origin (`app.py:432`) |
| Ambiguous attachment↔conversation | High | **MITIGATED** | explicit routed conversation required; no fallback (`handlers.py:1849–1852`) |
| User confusion local vs remote | High | **NOT MITIGATED today** | no current message distinguishes them (`ATTACHMENT_ACCEPTED_TEXT`, `handlers.py:1601`) — the core UX gap (S-13) |

**Severity vs status are separate columns** (remediation of F-06). A **future risk** is **not** an
existing vulnerability: the two "FUTURE RISK" rows are latent and unreachable today. **No security
downgrade is proposed**; every retrieval design **reuses** existing ownership, token-only naming,
and fail-closed behavior.

---

## 12. Distinct events (never collapsed into "delivered")

| Event | Evidence today |
| --- | --- |
| Local staging success | **[F]** item `status='stored'` |
| Telegram API acceptance (MT-1, future) | **[F] not implemented** |
| User retrieval / download (MT-1 or MT-2) | **[F] not implemented** |
| User-initiated upload to OpenHands | **[F] outside OpenHandBot** (user action) |
| Independently verified remote delivery | **[F] not possible** (U-12/U-3 absent) |

**Manual transfer never becomes a delivery guarantee.** U-12/U-3/D-04/D-06/D-02/D-03 remain the
long-term reliable-delivery requirements and are **not** replaced by Telegram send-back acceptance,
Mini App download completion, user assertion, agent-generated text, or an unverified workspace path.

---

## 13. Retrieval-versus-cleanup race analysis (S-7)

**Remediation of review finding S-7.** For MT-1 and MT-2 separately. **Existing source behavior:**
the reaper is DB-first: it marks the batch `expired` (CAS) and only then unlinks bytes
(`sweep` `attachments.py:1020–1138`; `_remove_file`:1316; `absent` is idempotent:1334). The
`OpportunisticSweeper` runs on the existing `Watcher` tick (`app.py:227–241`). There is **no
retrieval path today**, so **every race below is currently unreachable** — they are **future risks**.

Legend for **Reachable?**: **N** = not reachable today (no retrieval exists) · **Y-future** =
becomes reachable only if the option is implemented.

| # | Case | Existing behavior | Reachable? | Possible impact | Needs new invariant / coordination / owner decision? |
| --- | --- | --- | --- | --- | --- |
| 1 | Retrieval request begins shortly before 15-min expiry | reaper may expire concurrently | **Y-future** | retrieval may fail cleanly (`410`/`404`) — no data loss if handled | new invariant: reject expired before starting |
| 2 | Cleanup begins while retrieval waits for authorization | `_authorized` may `await`; reaper can run meanwhile | **Y-future** | file may vanish after auth → handle gracefully | coordination: re-check existence after auth |
| 3 | Cleanup begins after auth but before file open | reaper unlinks; `open` then `ENOENT` | **Y-future** | clean failure required (no partial/misleading) | open under a bounded lifecycle check |
| 4 | Cleanup begins while bytes are read | reaper unlinks a file with an open fd | **Y-future** | on POSIX the fd stays valid ⇒ read may still complete; **platform-specific [U]** | bounded streaming + verify size before/after |
| 5 | Process crash during retrieval | no durable retrieval record (MT-2) / partial op (MT-1) | **Y-future** | MT-2: nothing durable ⇒ safe; MT-1: durable op must recover | MT-1: durable op + CAS |
| 6 | File disappears/changes between DB lookup and open | `lstat` guards + `absent` idempotent | **Y-future** | must return clean not-found, never partial | verify identity/size at open |
| 7 | Attachment expired while an operation is queued | reaper marks `expired`, unlinks | **Y-future** | a queued MT-1 send could target missing bytes | durable op must not be invalidated after acceptance |
| 8 | Same attachment requested concurrently | no retrieval today | **Y-future** | MT-2 GET is idempotent (safe); MT-1 could double-send | MT-1: CAS/`unknown` (§14) |
| 9 | Open fd remains usable after unlink | POSIX semantics (unlink does not revoke open fd) | **Y-future / platform-specific [U]** | partial/complete read from an unlinked file | decide whether this is acceptable; verify on the real platform |

**Proposed mitigations (PROPOSALS ONLY; no new worker/scheduler/process/SQLite owner/schema):**
- Open and validate the file under a **bounded** lifecycle operation (verify identity + size at
  open).
- Coordinate retrieval with cleanup using the **existing** ownership mechanisms (DB-first reaper
  already exists).
- **Reject expired attachments before starting retrieval.**
- Ensure cleanup **cannot invalidate an operation that has been durably accepted** (MT-1 only).
- Use **bounded streaming** and verify file identity/size before and during access.

**Restrictive file permissions do NOT solve this race** and are not claimed to.

---

## 14. Duplicate and uncertain Telegram-send analysis (S-8) — MT-1 only

**Remediation of review finding S-8.** **No exactly-once Telegram delivery is claimed.** There is
**no** verified idempotency key on the Telegram send path; none is assumed.

Legend: **Reachable?** N = not reachable today (MT-1 not implemented).

| # | Case | Provable | Uncertain | Duplicate possible? | Action | Persistence/coordination | Reuse existing outbox semantics? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | User taps send-back twice | two requests recorded | which Telegram received | **Yes** unless deduped | dedupe by attachment identity | durable op keyed on item | **Partially** (CAS pattern) |
| 2 | Duplicate Telegram update | `update_id` dedupe exists (identity) | — | No (deduped at intake) | ignore duplicate | existing identity table | **Yes** (pattern) |
| 3 | Two concurrent requests, same attachment | CAS outcome | — | No if CAS serializes | single durable op | durable CAS | **Yes** |
| 4 | Crash before durable op created | nothing recorded | nothing sent | No | safe (nothing sent) | — | **Yes** |
| 5 | Crash after op created, before dispatch | op pending | not sent | No | recover to `pending` (pre-CAS) | durable pending + CAS | **Yes** (pre-CAS recovery) |
| 6 | Crash during transmission | `sending` recorded | Telegram may have received | **Yes** | mark `unknown`, **no** auto-retry | CAS `sending`→`unknown` | **Yes** |
| 7 | Telegram accepts, crash before recording success | `sending` recorded | sent but unrecorded | **Yes** on retry | `unknown`, **no** auto-retry | CAS from `sending` only | **Yes** |
| 8 | Telegram definite rejection | `failed` | — | No | report failure | CAS `sending`→`failed` | **Yes** |
| 9 | Network timeout, unknown outcome | `unknown` | delivery | **Yes** on retry | report uncertain, no auto-retry | CAS `sending`→`unknown` | **Yes** |
| 10 | Staged file expires while op pending | expiry recorded | bytes gone | No (no bytes) | reject cleanly | cleanup coordination (§13) | new invariant needed |
| 11 | Retry after uncertain outcome | prior `unknown` | delivery | **Yes** | require explicit user action, new op | new op record | **No** (new policy — owner) |
| 12 | New send after earlier `unknown` | earlier `unknown` | prior delivery | **Yes** | warn user; do not claim dedupe | — | **No** (owner decision) |

**Conclusion:** the existing outbox's **at-most-once** CAS/`unknown` semantics **can be reused** for
the *mechanical* part (cases 4–9) **only if** MT-1 gets a durable document operation (§6.2). Cases
1, 10, 11, 12 need **new decisions/policies** and must not be presented as already solved. **No new
retry policy or operation state is created here as approved.**

---

## 15. Proposed future implementation phases (NOT authorized)

| Phase | Files/components | Reuse | New API/schema | Security prereq | Tests | Owner decision |
| --- | --- | --- | --- | --- | --- | --- |
| **P0 — wording only** | `bot/handlers.py` texts; `docs/MINI_APP.md` | existing replies | none | none (no delivery claim) | backend text tests | **wording sign-off** |
| **P1 — MT-1 send-back** | `bot/handlers.py`, `bot/outbox.py`(+kind), `bot/db.py`(kind/status) | `send_document`, outbox tick, staging read | **YES** (durable doc op) | ownership + window check + idempotency | backend + integration + crash/race | **D-22**, D-15, D-16, scope |
| **P2 — MT-2 Mini App** | `bot/web/app.py` route + `services.py` + `static/*.js` | `_guarded`, `_attachment`, export.js pattern | new cookie-auth route (**no** schema change) | ownership + bounded streaming + no public URL | backend + frontend + **real WebView** | scope (MT-2) + WebView verification |

**Tests separation:** **backend** (auth, identity, bounds, expiry) · **frontend** (RTL, keyboard,
states) · **integration** (staging→retrieval) · **manual browser/WebView** (MT-2 download, real
Telegram Android).

---

## 16. Acceptance criteria for future implementation (proposed; not met)

### 16.1 MT-1 acceptance criteria

- Authenticated request by the **correct** Telegram user (`_allowed`).
- Correct chat/message/**attachment identity** (item + batch + `attachment_message_identity`).
- **Bounded** file size and streaming (≤ enforced intake cap).
- Safe filename (token-only) and MIME handling (metadata only).
- **No** path traversal or symlink escape (`_is_within` + `lstat`).
- Correct handling of **missing/expired** files (clean `410`/`404`).
- **Cleanup coordination** (§13): a durably accepted op is never invalidated.
- **Durable operation semantics** with **crash recovery** (§14 cases 4–9).
- **No** duplicate-send guarantee claims; **explicit** uncertain-outcome handling.
- **No** false OpenHands-delivery status (§10).
- Existing polling/outbox constraints preserved; `concurrent_updates(True)` unchanged.
- Tests for **all** duplicate and race scenarios (§13, §14).

### 16.2 MT-2 acceptance criteria

- Authenticated Mini App **session** (`_guarded`).
- Correct **ownership** and conversation authorization.
- **Secure** attachment lookup (token + `_is_within`).
- **Bounded streaming** (no full-memory read for large files; explicit `Content-Length`).
- Correct response **headers** and safe filename (`_attachment`).
- Path traversal and symlink protection.
- **Expiry/cleanup race** handling (§13).
- **Interrupted download** behavior (no partial "success").
- **Browser** verification.
- **Real Telegram Android WebView** verification (else MT-2 stays `UNVERIFIED`).
- **Arabic RTL** and keyboard accessibility.
- **No** false OpenHands-delivery status (§10).

**Neither set of criteria has been met**; these are proposals for a future implementation.

---

## 17. Owner-decision matrix

| Decision | What it controls | Blocks which option | Prerequisite for | Evidence the owner needs | Status |
| --- | --- | --- | --- | --- | --- |
| **D-22** | Durable Telegram-document operation vs alternative mechanism | **MT-1** | design **and** implementation of MT-1 | §6.2 alternatives; register `:1042–1060` | **OPEN** |
| **D-12** | size/type quota triple (`3 MiB == 3 MiB`) scope | affects UX wording + bounds | design | `attachments.py:99`,`:105–106`; register `:158` | **OPEN** |
| **D-15** | fixed 15-min window; no server batch | affects MT-1 expiry handling | design | `db.py:261`; register `:161` | **OPEN** |
| **D-16** | idempotency/dedup window for retried send-back | **MT-1** (§14 cases 11–12) | implementation | register `:162` | **OPEN** |
| **Option selection** | MT-1 vs MT-2 (or both) | both | implementation | §7–§8 | **OPEN** |
| **Scope** | one or both manual paths approved | both | implementation | §7–§8 | **OPEN** |
| **Wording** | exact Arabic copy (§10) | both | runtime activation | §10 | **OPEN** |
| **WebView verification** | real Telegram Android WebView download | **MT-2** | MT-2 implementation | §7.2 | **OPEN** |
| **Any new schema/architecture** | discovered during comparison | MT-1 | implementation | §6.2 | **OPEN** |

**No owner decision is answered here.**

---

## 18. Finding-remediation matrix (all review findings)

| Finding (review) | Severity (review) | Re-verified vs current source | Correction in this document | Remaining unresolved |
| --- | --- | --- | --- | --- |
| **F-01** 20 MB stated as fact | HIGH | **CONFIRMED** — no 20 MB constant in `bot/`; enforced cap `MAX_ATTACHMENT_BYTES=3 MiB` (`attachments.py:99`) | §5: claim withdrawn; verified limit table L1–L7; scope note; **no** unverified external limit asserted | none (owner may cite a source for L5) |
| **F-02** understated MT-1 prerequisite | MEDIUM | **CONFIRMED** — outbox schema has no payload/kind (`db.py:608–621`); sends to OpenHands (`openhands_client.py:337`) | §6: full outbox contract; MT-1 alternatives A/B with requirements | **D-22** (owner) |
| **F-03** B1-first asserted not derived | MEDIUM | **CONFIRMED** — no prior comparison existed | §7 comparison matrix; §8 trade-off table; recommendation withdrawn | option selection (owner) |
| **F-04** B1/B2/B3 naming collision | HIGH | **CONFIRMED** — register `:710`,`:1236` + staged plan `:739`,`:756`,`:768` = remote stages, `NOT AUTHORIZED` | §9 glossary; **MT-1/MT-2/MT-3** used throughout; remote stages explicitly distinct | none |
| **S-7** retrieval/cleanup race under-analyzed | MEDIUM | **CONFIRMED** — no retrieval path; reaper DB-first (`attachments.py:1020`,`:1316`,`:1334`) | §13: 9-case analysis, MT-1/MT-2 split, proposals only | new invariant (owner/design) |
| **S-8** duplicate/uncertain send under-analyzed | MEDIUM | **CONFIRMED** — outbox CAS/`unknown` at-most-once (`outbox.py:447–470`); no Telegram idempotency key | §14: 12-case failure matrix | new retry policy (owner) |
| **S-13** local/remote ambiguity | HIGH | **CONFIRMED** — `ATTACHMENT_ACCEPTED_TEXT` (`handlers.py:1601`) has no "not uploaded" qualifier | §10: 8 wording blocks + conceptual status labels | wording approval (owner) |
| **F-05** imprecise citations | LOW | **CONFIRMED** — identity table DDL `db.py:804–813` (not 770–815); D-33 at `:797–803` | §4.2 uses precise refs; stable file/function refs preferred | none |
| **F-06** severity/status conflated | LOW | **CONFIRMED** | §11 splits **Severity** and **Status**; future risks labeled | none |
| **F-07** nonexistent "تنزيل الملف" button | INFO | **CONFIRMED** — no staged-download UI in `bot/web/static/` (grep) | §10.2 marks it PROPOSED; §19 lists all proposed controls | none |
| **F-08/§15** no remediation traceability | INFO | **CONFIRMED** | this §18 matrix + §21 | none |

---

## 19. Current UI vs proposed UX (F-07)

- **[F] Existing UI controls (verified in source):** conversation export button `⬇️ تصدير الشات`
  (`bot/web/static/app.js:1031`, `:1046–1056`); copy-reply button (`copy.js`); file text preview
  (`files.js`). **No** control references `attachment_staging`.
- **[F] Nonexistent today:** any "download staged attachment" button, any MT-1 "send back" button, any
  attachment callback.
- **PROPOSED — NOT IMPLEMENTED:** the MT-1/MT-2 download controls implied by §10.2/§10.4. They must
  not be described as existing and must not be shipped until the corresponding path exists.

---

## 20. Tests and verification actually performed

Documentation-only task. **No runtime test suite was run** for this remediation (not required, and
not claimed). Read-only checks actually run:

| Command | Purpose | Result |
| --- | --- | --- |
| `grep -rn "20 MB" bot/ docs/` | find unverified 20 MB claims | only proposal text (not a contract) |
| `grep -rnE "MAX_ATTACHMENT_BYTES\|TELEGRAM_DOCUMENT_MAX_BYTES\|MAX_EXPORT_BYTES" bot/` | confirm size constants | L1/L4/L7 confirmed |
| `sed -n '608,621p' bot/db.py` | outbox schema | text-only confirmed |
| `grep -n "send_message" bot/openhands_client.py` | outbox target | OpenHands confirmed |
| `grep -rn "attachment_staging" bot/` | staged-byte reads | none outside `attachments.py`/`db.py` |
| `grep -n "send_document\|InputFile" bot/*.py` | outgoing document capability | 3 in-memory call sites |
| `grep -n "B1–B3\|NOT AUTHORIZED" docs/decisions docs/proposals` | naming collision | remote stages confirmed |

No runtime tests are required for this documentation-only task; none are claimed.

---

## 21. Exact file changes and Git state

- **[F] Modified (in place):** `docs/reviews/OHB2-PLAN-08-MANUAL-ATTACHMENT-TRANSFER-UX-DESIGN.md`
  (this file).
- **[F] Modified (append-only):** `.agent/PROGRESS.md`.
- **[F] Not changed:** the independent review report (sha256 `71cc88c8…`), Plan 05/06/07-A/07-A2
  reports (hashes §3.2), runtime code, frontend code, tests, DB schema, migrations, config,
  dependencies, deployment files, `.openhands/`.
- **[F] Git state:** branch `main`; HEAD = `facf1f42…`; **nothing staged**; no commit/push/PR/merge/
  release/deploy/Autopush.

**No implementation occurred:** no MT-1/MT-2/MT-3 feature, no retrieval endpoint, no outbox/operation
type, no schema/migration, no public URL or token.

---

## 22. Exact next owner decision required

**Resolve D-22** (durable Telegram-document operation vs an explicitly approved alternative
mechanism) **and select the scope (MT-1, MT-2, or neither)**. Until then:

- **MT-1 cannot be implemented** (needs a durable operation + D-22).
- **MT-2 has the smaller footprint but is gated by UNVERIFIED real Telegram Android WebView
  behavior** and the same scope decision.
- **A limited implementation plan can be prepared without selecting an option only for P0 (wording),
  which itself needs owner wording approval.**

**No implementation may start until the owner approves D-22, the scope, and the §10 wording.**
Plan 07-B/07-C remain **not authorized**.

---

> Evidence labels recap: **[F]** verified against current source · **[F-R]** verified after review
> finding · **[I]** inference · **[U]** unverified · **[G]** documented-but-untested · **[R]**
> recommendation · **[OWNER]** owner decision.
>
> **This document is not independently reviewed.** The original independent review remains
> immutable; a **new separate read-only independent review** is required before implementation can
> be considered.
