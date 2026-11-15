# OHB2-PLAN-07-A2 — Delivery Identity and Evidence Resolution

- **Task ID:** `OHB2-PLAN07-A2-DELIVERY-IDENTITY-AND-EVIDENCE-RESOLUTION`
- **Type:** Investigation only. **No runtime code, schema, migration, dependency, config, route, or
  approved decision was changed.** No endpoint created; no public URL created/exposed/tested; no
  production API call; no credential used; no real user file touched.
- **Author:** OpenHands agent (autonomous). Self-review quality only — **not** an independent review.
- **Date:** 2026-11-14 (repo evidence read this session; primary docs/specs from session caches).
- **Repo state when written:** branch `main`, HEAD `facf1f42578a20a4a37e220eca016ce3d534e750`
  (= `origin/main`), divergence `0 0`.

> Evidence labels: **[F] fact** (verified from a repository file / pinned source / cached spec this
> session) · **[I] inference** · **[U] unknown/unverified** · **[G] documented but not tested** ·
> **[R] recommendation**. This document **proposes**; it **decides nothing** on the owner's behalf.

---

## 1. Task ID and authorization scope

**Task ID:** `OHB2-PLAN07-A2-DELIVERY-IDENTITY-AND-EVIDENCE-RESOLUTION`.

**Goal:** determine whether the Plan 07-A blockers — **D-06** (trusted workspace root), **D-02/D-03**
(independent delivery evidence), **F4** (secure token storage) — can be resolved **without**
violating existing architecture, identity, security, and delivery guarantees, and to surface the
**exact owner decisions** still required.

**Authorized:** read-only inspection of repo + reports + pinned source/specs; analysis; documentation
of designs/limitations/dependencies/decisions; create this report; append-only PROGRESS update.

**NOT authorized (and not performed):** runtime/schema/migration changes; new tables/columns/indexes/
token stores/state transitions; new workers/schedulers/processes/services/SQLite owners; new download
routes or public endpoints; creating/exposing/testing a public URL; changing OpenHands conversations/
workspaces/sandboxes/production resources; real user files / production secrets / production API
calls; Plan 07-B or 07-C; commit/push/PR/merge/release/deploy/Autopush.

> This prompt is **not** treated as approval of any architectural or product decision.

---

## 2. Actual repository baseline

### 2.1 Git state (verified this session)

- **[F]** Branch `main`; **HEAD = `main` = `origin/main` =** `facf1f42578a20a4a37e220eca016ce3d534e750`;
  divergence `git rev-list --left-right --count origin/main...HEAD` → **`0  0`**.
- **[F] `git status --short`:**
  - ` M .agent/PROGRESS.md` — pre-existing (Plan 05/06/07-A sessions).
  - `?? docs/reviews/OHB2-REPAIR-PLAN-05-SECURE-ATTACHMENT-DELIVERY-INVESTIGATION.md`
  - `?? docs/reviews/OHB2-REPAIR-PLAN-06-ATTACHMENT-DELIVERY-ALTERNATIVE-ARCHITECTURE.md`
  - `?? docs/reviews/OHB2-PLAN-07-A-SECURE-PULL-FEASIBILITY-INVESTIGATION.md`
- **[F] Staged:** none. **Ignored (relevant):** `.openhands/`, `__pycache__/`, `.pytest_cache/`.
- **[F] Prior reports (untouched; hashes recorded this session):**

| Report | Lines | SHA-256 |
| --- | --- | --- |
| Plan 05 | 428 | `4944714a3469894a01093619a2b75072eb65b403eb3df665db520b35c857e676` |
| Plan 06 | 617 | `4450b77cb9981d4997a4f7cb41f3cb3e4821aad93d4d74b7ea982bedd1920303` |
| Plan 07-A | 509 | `8faec96b3c4844fb36d5b793b72fce340f837a3e2aa67a2cbee2d3a6a5e88d90` |

- **[F] `.agent/PROGRESS.md`:** 3382 lines; `git diff --numstat` = `130 0` (append-only from
  Plan 07-A). This task appends (see §14).
- **[F] `MINI_APP_ENABLED`** default `False` (`bot/config.py:262`). **Autopush:** not running
  (no `autopush`/`main.py` process; no listening sockets).

### 2.2 Evidence sources read (this session)

- **[F] Repo:** `bot/attachments.py`, `bot/db.py`, `bot/files.py`, `bot/openhands_client.py`,
  `bot/outbox.py`, `bot/watcher.py`, `bot/web/*`, `bot/config.py`; `docs/decisions/OHB2-P0-OWNER-
  DECISIONS-REGISTER.md`; `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md`
  (§§2.2, 2.3.5, 5.14, 5.15, 5.15.6); `docs/reviews/` Plan 05/06/07-A.
- **[F] Cached pinned source (read this session, not re-fetched):** agent-server
  `as_api.py`, `as_file_router.py`, `as_dependencies.py` (pinned
  `OpenHands/software-agent-sdk@2aae48b6…`); sandbox-server `oh_remote.py` (`grouped_workspace_dir`
  usage).
- **[F] Cached specs:** Cloud V1 `openapi.json` **v1.92.0** (257 paths); Agent Server
  `agent-sdk.json` **v0.1.0** (40 paths).

> **Evidence-freshness note [F]:** the proposal cites Cloud spec **1.91.0 / 244 paths**
> (`docs/proposals/OH-P0-…:603`); this session's cached spec is **1.92.0 / 257 paths**. The routes
> relied on below are present in **both**; the version delta is recorded, not hidden.

### 2.3 Current identity and attachment lifecycle (verified)

- **[F] Staging:** `<db_dir>/attachment_staging/`, mode `0700`, fail-closed (`ensure_staging_root`,
  `bot/attachments.py:200–265`); writes `O_CREAT|O_EXCL|O_NOFOLLOW` (`:587`); root confinement
  (`_is_within` + `lstat`, `:1323–1326`); storage filenames = **opaque random tokens**
  (`secrets.token_hex`, `:200`).
- **[F] Row-first:** the `attachment_items` row (`status='pending'`) is written **before** bytes;
  status → `stored` only after a complete verified write (`bot/attachments.py:22–27`,
  `bot/db.py:1813`).
- **[F] Batch/item/identity schema** (`bot/db.py:770–815`):
  - `attachment_batches(batch_id PK, telegram_id, conversation_id, t0, status DEFAULT 'pending',
    created_at, updated_at, intent_text)`.
  - `attachment_items(item_id PK, batch_id, staging_token, display_name, size_bytes,
    status DEFAULT 'pending', created_at, updated_at)`.
  - `attachment_message_identity(telegram_id, chat_id, message_id, batch_id, conversation_id,
    created_at, PK(telegram_id,chat_id,message_id), FK(batch_id) ON DELETE RESTRICT)`.
- **[F] Batch states (8 defined):** `pending`, `intent_recorded`, `dispatching`, `uncertain`,
  `delivered`, `expired`, `rejected`, `failed` (`bot/db.py:120–137`). **Produced today:** only
  `pending` (INSERT `db.py:1813`), `intent_recorded` (UPDATE `db.py:1630`), `expired`
  (`attachments.py:869`/`:1128`). The other five are **defined but never written** — the
  remote-delivery state machine is **unimplemented**.
- **[F] Expiry/cleanup:** fixed 15-minute `t0` deadline; reaper marks `expired` **then** reclaims
  staging bytes (DB-first), driven from the **existing** `Watcher` tick via `OpportunisticSweeper`
  (`bot/attachments.py:1377–1432`, `bot/app.py:231–237`). No new worker/scheduler/process.
- **[F] Conversation identity (bot-side):** `watched(conversation_id PK, …, chat_id, …)`
  (`bot/db.py:590`) + `conversation_id` columns in `outbox`/`creation_jobs`/`completion_pending`/
  `notification_state`. Delivery = `POST /app-conversations/{conversation_id}/send-message`
  (`bot/openhands_client.py:337–339`) with the held `OPENHANDS_API_KEY`.
- **[F] The bot does NOT store a workspace root, sandbox_id, or runtime URL.** Confirmed: no
  `working_dir`/`archiveworkspacepath`/`conversation_url` usage in `bot/` (only `sandbox_id` is read
  transiently from the conversation object to resume a paused sandbox, `bot/outbox.py:348–352`).

---

## 3. Workstream A — D-06: trusted workspace-root identification

### 3.1 How identity is currently established (verified)

| Question | Finding |
| --- | --- |
| Conversation | **[F]** `conversation_id` stored in `watched` + operation tables; validated by `is_valid_conversation_id` (`bot/files.py:70`). |
| Runtime/sandbox | **[F]** Cloud object carries `sandbox_id` (`docs/API_NOTES.md`); the bot reads it transiently only to resume (`bot/outbox.py:348–352`). Not persisted. |
| Repository | **[F]** `AppConversation.selected_repository`/`repositories[]` exist; the bot lists repos (`/git/repositories/search`) but does **not** bind a conversation to a repo path. |
| Filesystem workspace root | **[F] Not known to the bot.** Not stored, not queried, not derived. |
| Shared sandbox/workspace | **[F] Yes, possible.** `grouped_workspace_dir(base, strategy, key)` under any non-`NO_GROUPING` strategy nests conversations under one base (`oh_remote.py:1021`). |
| Runtime/workspace change over time | **[F]** The runtime URL is **ephemeral** (`docs/OHB2_HOSTING_DECISION.md` §1.2); the archived workspace path can be re-derived on the fly. |
| Are runtime URLs stable identifiers? | **[F] No** — they are **access locations**, not identity. |

### 3.2 Candidate evidence sources for the authoritative root

| Candidate | Producer | Authenticated? | Bound to conversation? | Bound to sandbox/workspace? | Survives restart/reassign/reuse? | Another conv can observe/modify? | Independently verifiable by bot? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Conversation metadata `repositories[].path` (Cloud V1) | Cloud, from server-written `archiveworkspacepath` tag | **[F] Yes** (Cloud bearer, user-scoped) | **[F] Yes** (field on the conversation object) | **[F] Yes** (server-written at start) | **[F] Yes** (re-derived from tag/`resolve_existing_sandbox_spec`) | **[F] Possibly** under grouping (siblings share base) | **[F] Yes** (Cloud read exists — §3.3) |
| Runtime/sandbox ID | Cloud | Yes | Partial | Partial | **[U]** | — | Yes |
| Repository name/folder | Cloud | Yes | Yes | **No** (name ≠ path) | — | — | Yes |
| Agent Server `workspace.working_dir` (scoped route) | Agent Server (`bind_local_conversation_runtime`) | **[F] Yes** (`X-Session-API-Key`) | **[F] Yes** (`runtime_conversation_id`) | **[F] Yes** | Yes (per-request) | Possibly (grouping) | **[F] Yes** — but requires the full-privilege key |
| Agent-reported cwd | Agent | **No** | No | No | No | — | **No** |
| Marker/nonce created in a controlled op | Either | Depends | Depends | Depends | — | — | Only if re-read via an authenticated channel |

### 3.3 Key finding — the authoritative root **read** already exists and ships **[F]**

- **[F] Cloud V1 exposes the per-conversation workspace root.** `GET /api/v1/app-conversations`
  and `/search` return `AppConversation.repositories[]` → `ConversationRepository.path`
  = *"Absolute path of the folder in the sandbox"* (cached spec v1.92.0; field `readOnly: true`).
  Verified: `AppConversation` has a `repositories` array of `ConversationRepository`; the route is
  under `security: APIKeyHeader` (the bot's bearer).
- **[F] The read is provider-produced and server-written.** The proposal records the source:
  `AppConversationInfo.repositories` is a `@computed_field` reading the **reserved, server-managed**
  tag `archiveworkspacepath` (`RESERVED_TAG_KEYS`, `app_conversation_models.py`), written by the
  server at conversation start (`live_status_app_conversation_service.py:1124`). Callers cannot set
  it. (`docs/decisions/…:444–509`, `docs/proposals/…:2090–2160`.)
- **[F] Agent Server exposes its own root** on the conversation-scoped route:
  `bind_local_conversation_runtime` computes
  `workspace_root = Path(event_service.get_conversation().workspace.working_dir).resolve()` and
  enforces `resolve().is_relative_to(workspace_root)` (else 422)
  (`docs/proposals/…:739–742`, `:2.3.5`). This is the **runtime-side** authoritative value.

### 3.4 The residual gap (why D-06 is still open)

- **[F]** The proposal already distinguishes *read* (exists) from *binding* (new): what is **not**
  established is that the resolved root is **bound to `(principal, conversation_id, operation_id)`**
  and **authorized for the write** (U-12), and that it is **immutable/scope-safe against symlink/
  TOCTOU** (`docs/proposals/…:2090–2160`, §5.15.6).
- **[F]** `_get_agent_server_context` (the helper the Cloud uses for the runtime hop) carries only
  `sandbox_spec.working_dir` — the **ungrouped base** — not the per-conversation root
  (`docs/proposals/…:2090`; `docs/decisions/…:476–478`).
- **[F] Grouping ambiguity [F]:** under any non-`NO_GROUPING` strategy, sibling conversations share
  the base (`oh_remote.py:1021`), so "the root" is a **shared** location — an inherent property, not
  a defect.

### 3.5 D-06 resolution matrix

| Option | Classification | Basis |
| --- | --- | --- |
| **A.** Root from Cloud `AppConversation.repositories[].path` (tag→root), **no** new binding | **RESOLVABLE WITH EXISTING PROVIDER EVIDENCE** (read only) | §3.3 — read ships; **[I]** sufficient for a *best-effort* target path |
| **A′.** Root from **Agent Server** `workspace.working_dir` via the scoped route (requires full-privilege `X-Session-API-Key`) | **RESOLVABLE ONLY WITH NEW PROVIDER CAPABILITY** | §3.3 — route exists, but **no scoped credential** exists to call it (Plan 05 B1) |
| **B.** Root **bound** to `(principal, conversation_id, operation_id)` + write-authorization (U-12) | **RESOLVABLE ONLY WITH NEW PROVIDER CAPABILITY** (Cloud upstream work) | §3.4 — binding is new/UNVERIFIED |
| **C.** Owner approves "best-effort root = `repositories[].path`; no verified-workspace claim" | **RESOLVABLE ONLY WITH AN OWNER-APPROVED ARCHITECTURAL CHANGE** | §8 alternative 4 — a **deliberate** downgrade of the guarantee |
| **D.** No trusted root; fail closed (no delivery) | **NOT RESOLVABLE** (by design) | §3.4 |

**D-06 answer:** a **provider-authenticated read** of the conversation's workspace root **exists
today** (Cloud `repositories[].path`). What is **missing** is (1) the **identity/authorization
binding** (U-12) for a *verified* delivery claim, and (2) a **scoped credential** to use the
agent-server's own `workspace.working_dir` check without the full-privilege key. Absent those, D-06
for **verified** delivery remains **BLOCKED — OWNER ARCHITECTURAL DECISION + PROVIDER CAPABILITY
REQUIRED**; for **best-effort** placement it is resolvable with an **explicit owner waiver**.

---

## 4. Workstream B — D-02 / D-03: independent delivery evidence

### 4.1 The minimum evidence set (7 claims to establish)

1. correct attachment selected · 2. download authorized · 3. bytes transferred completely ·
4. received bytes match the staged attachment · 5. file written into the intended workspace ·
6. file remains available at the intended location · 7. workspace belongs to the intended
conversation (or an explicitly approved shared workspace).

### 4.2 Evidence-by-evidence: what each proves / does not prove

| Evidence | Proves | Does **not** prove |
| --- | --- | --- |
| **[F]** HTTP request/response status | the server answered | transfer completeness, integrity, workspace, conversation |
| **[F]** Byte count (server) | bytes were streamed to *some* client | who received them; where they landed |
| **[F]** SHA-256 at OpenHandBot **before** issuing the link | identity of the staged bytes | that those bytes were received or written anywhere |
| **[F]** SHA-256 **at the downloader** | the downloader held bytes with that hash | that the writer wrote them to the intended workspace; a hash match alone ≠ correct workspace |
| **[F]** Download-server access logs | a request happened | content, integrity, destination |
| **[F]** Agent-reported success | the agent *claims* success | anything (agent-authored; not independent) |
| **[F]** Agent Server filesystem metadata | what the runtime sees at a path | it does not by itself tie that path to `(principal, conversation_id, operation_id)` |
| **[F]** Provider-authenticated **re-read** (Cloud `GET …/file`) | the *runtime* serves that file's content for that conversation | it is a **proxy**; it does not return size/hash, and it is not a stat; it does not prove *this* upload |
| **[F]** Marker/nonce challenge | a value created by a trusted party was observed | who observed it, unless re-read via an authenticated channel |
| **[F]** Later independent read/stat | current presence | nothing about the transfer's integrity by itself |

### 4.3 The seven-fact distinction (per the task)

| Fact | Established by | Independent today? |
| --- | --- | --- |
| Link issued | OpenHandBot | **[F] Yes** (bot-side) |
| Download started | download-server log | **[F] Partially** (server-side only) |
| Download completed | server byte count | **[F] Partially** |
| Byte integrity verified | SHA-256 at **both** ends | **[F] Yes for the bytes** — but **not** for workspace placement |
| File written | agent tool | **[F] No** (agent-authored) |
| Correct workspace verified | provider-bound root (D-06) + authenticated read | **[F] No primitive binds the root to the op (U-12)** |
| Correct conversation/workspace association verified | provider binding | **[F] No** |

### 4.4 D-02 evidence requirements

- **[F] No existing primitive proves a *complete content read* (F6b).** The proposal establishes
  F1–F5 and F6a (non-error observation) but **not** F6b: a non-error terminal observation does **not**
  prove a successful read (`cat <missing>`), and a successful `file_editor view` is **truncated**
  (`docs/proposals/…:1621–1690`, §5.14.0).
- **[F]** `delivered` is therefore **unreachable** from existing primitives; it needs a **new
  explicit structured read acknowledgment (U-3)** from a **trusted, non-agent** issuer
  (D-02 + D-03).
- **[R] Minimum D-02 evidence:** a provider-authenticated statement, bound to
  `(principal, conversation_id, operation_id, file_id)`, reporting `bytes_read` + `sha256` +
  `truncated` for **that** file, read from a **quiesced** source (D-04).

### 4.5 D-03 evidence requirements

- **[F] The issuer must be outside agent control.** Any event the agent/tool/model produces is **not**
  evidence (`docs/decisions/…:340–386`).
- **[F] No authenticated service-to-service acknowledgment channel exists** in the pinned source
  (D-03 = new upstream capability).

### 4.6 A potentially **stronger existing** primitive — the Cloud read proxy **[F]**

- **[F] `GET /api/v1/app-conversations/{id}/file?file_path=…` (and `/files`)** already performs the
  **server-side runtime hop** and reads a workspace file for a **user-scoped** conversation
  (cached spec v1.92.0; `security: APIKeyHeader`; description: *"Read a file from a specific
  conversation's sandbox workspace … otherwise returns an empty string"*).
- **[F] OpenHandBot already uses these routes** (`bot/openhands_client.py:178–185`,
  `read_file_text_bounded`), with a hard response cap and redirect/TLS hardening.
- **[I] This is a provider-authenticated *read*, but it is NOT a delivery proof:**
  (a) it returns **content**, not size/hash metadata; (b) it is a **proxy** whose workspace resolution
  is the same unresolved root (D-06); (c) it cannot distinguish *this upload* from a pre-existing
  file at the same path; (d) it proves nothing about **who wrote** the file. So it **narrows** the gap
  (an independent, non-agent read exists) but does **not close D-02/D-03**.
- **[R]** A trustworthy *content* re-read could be combined with a **server-side SHA-256 of the staged
  bytes** and a **server-generated unique path/nonce** to build a *stronger* (still not fully bound)
  chain — but binding to `(principal, conversation_id, operation_id)` and quiescence (D-04) remain
  open.

### 4.7 Verdict (Workstream B)

**D-02/D-03 are NOT independently verifiable today.** A provider-authenticated read primitive
**exists** (Cloud `…/file`), but no primitive (a) proves a complete content read, (b) returns
size/hash, or (c) binds the result to the operation. The chain is **not** independently verifiable
without **new upstream capability** (U-3/U-12) — **BLOCKED**.

---

## 5. Workstream C — F4: secure token storage and lifecycle

### 5.1 Does a secure token fit the existing schema without modification?

- **[F] No genuinely compatible field exists.** `attachment_items.staging_token` stores the **raw**
  opaque storage filename (used as a filesystem name); it is **not** a token hash, and repurposing it
  would (a) require storing a **hash** where the code needs the **name**, and (b) overload a
  load-bearing column. `web_sessions.token_hash` is a **separate table** scoped to Mini App sessions,
  keyed by `token_hash` and joined to `user_id` — it cannot represent an attachment/conversation
  binding.
- **[F] No stable application secret exists.** `bot/config.py` defines **no** app/signing/HMAC
  secret. The only keyed secret available is the **Telegram bot token** (used by `initdata.py` via
  HMAC) — a **different trust domain** (Telegram), and reusing it for attachment tokens would couple
  two unrelated secrets and complicate rotation. **So option D (keyed derivation from an existing
  stable secret) is not available without inventing/adding a secret.**

### 5.2 Option analysis

| Option | Entropy/gen | Lookup | Binding | Expiry/revoke | Replay/concurrency | Rotation | DB-backup exposure | Logs/URL leakage | Atomicity w/ lifecycle | Single-owner fit | Migration/rollback | New worker? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **A.** Hash into an existing compatible field | 256-bit | **None fits** (§5.1) | ✗ | ✗ | ✗ | — | — | — | ✗ | ✗ | ✗ | — |
| **B.** Hash in a **new column** | 256-bit | by `token_hash` | ✔ (FK to item/batch) | ✔ (`expires_at`) | ✔ | N/A (no key) | safe (hash only) | same as sessions | ✔ | ✔ | additive `ALTER`/new column | No |
| **C.** Metadata in a **new table** | 256-bit | by `token_hash` PK | ✔ | ✔ | ✔ | N/A | safe | safe | ✔ | ✔ | additive `CREATE TABLE` | No |
| **D.** Keyed derivation from existing secret | 256-bit | by derived id | ✔ | ✔ | ✔ | needs rotation model | **no secret exists** (§5.1) | — | ✔ | ✔ | needs secret mgmt | No |
| **E.** No bearer URL (alternative auth) | n/a | n/a | ✔ | ✔ | ✔ | n/a | n/a | avoids URL leak | ✔ | ✔ | none | No |

### 5.3 Recommendation (F4)

- **[R] Least-invasive secure option: C — a new dedicated table** (or, equivalently, B — a new column),
  storing only a **SHA-256 hash** of a **256-bit** `secrets.token_urlsafe` token (reusing the proven
  `bot/web/sessions.py` pattern: hash-at-rest, server-side `expires_at`, delete-to-revoke). Rationale:
  additive, single-owner, no new worker, survives restart, safe against DB-backup exposure, and
  consistent with existing code.
- **[R] Preferred if acceptable: E — avoid bearer URLs entirely** (e.g. an authenticated pull the bot
  authorizes via its own session/identity), which removes the URL-leak surface (proxy logs,
  `Referer`) — but it changes the pull mechanism and needs a design decision.
- **[F] F4 cannot be satisfied without a schema change.** Options B/C/E are **schema/architecture
  changes** and are **NOT authorized** here. **Owner approval + a migration are required.**
- **[F] Non-negotiable invariants:** no plaintext token in the DB, logs, PROGRESS, or fixtures; the
  token binds to **one attachment + one intended conversation + the `(telegram_id, chat_id,
  message_id)` tuple**; TTL ≤ the 15-minute staging window; delete-to-revoke.

---

## 6. Workstream D — cross-check of owner decisions

| Decision | Recorded status | Applies to Secure Pull? | Blocks design? | Blocks implementation? | New owner decision? | Satisfiable without architecture change? |
| --- | --- | --- | --- | --- | --- | --- |
| **D-02** successful-read signal | **OPEN** (`delivered` unreachable) | **Yes** (delivery evidence) | **Yes** | **Yes** | **Yes** | **No** (needs U-3) |
| **D-03** trusted issuer boundary | **OPEN** (UNVERIFIED) | **Yes** | **Yes** | **Yes** | **Yes** | **No** (needs upstream) |
| **D-04** quiesced evidence source | **OPEN** | **Yes** (if event evidence used) | **Yes** | **Yes** | **Yes** | **No** |
| **D-06** workspace root + binding | **OPEN** (read exists, binding new) | **Yes** | **Yes** | **Yes** | **Yes** | **No** for verified; **Yes** for best-effort |
| **D-10** capability ownership (Cloud vs Agent Server) | **OPEN** | Partly (Secure Pull avoids the bot-side credential) | **Yes** if the agent-server route is used | — | **Yes** | — |
| **D-11** scoping mechanism (delegated route vs capability token) | **OPEN** | **Yes** (pull-token design) | **Yes** | **Yes** | **Yes** | — |
| **D-12** size/type limits (PROVISIONAL) | **OPEN** (quota disabled by default) | **Yes** (3 MiB cap) | No | **Yes** | **Yes** (confirm triple) | **Yes** |
| **D-14** delivery mechanism A/B/C/D | **OPEN** | **Yes** (pull = design C-ish) | **Yes** | **Yes** | **Yes** | — |
| **D-15** `expires_at` window, no server batch | **OPEN** (confirm) | **Yes** (link TTL) | No | **Yes** | **Yes** (confirm) | **Yes** |
| **D-16** idempotency + dedup | **OPEN** | **Yes** (replay) | No | **Yes** | **Yes** | — |
| **D-22** outbox integration | **OPEN** | **Yes** (if delivery goes through outbox) | **Yes** | **Yes** | **Yes** | — |
| **D-24** delivered-file mode/uid/gid | **OPEN** (UNVERIFIED) | **Yes** (agent must read the file) | No | **Yes** | **Yes** (technical) | — |

- **[F] Preserved identity rules:** message↔batch identity is the legal tuple
  `(telegram_id, chat_id, message_id)` (`attachment_message_identity`, `bot/db.py:804`); PK prevents
  silent re-binding (fail-closed). **D-35** keeps identity independent of `processed_updates` pruning.
  **D-32/D-33/D-34** gate the prompt path fail-closed. Secure Pull **must not** change these.
- **[F] Outbox ownership/retry:** text-only; bounded `MAX_OUTBOX_ATTEMPTS` + CAS claims
  (`bot/outbox.py:48–53`, `:266–298`). An attachment delivery would need D-22 (new item kind) —
  a schema/architecture change.
- **[F] SQLite ownership:** exactly one `Database` object shared by the bot + web layer
  (`docs/MINI_APP.md` §1). Secure Pull must not add a second owner.
- **[F] No decision above is marked resolved.** Proposing a technical alternative does **not**
  resolve an owner decision.

---

## 7. Workstream E — alternatives comparison

| # | Alternative | Security | Delivery guarantee | Workspace identity | Provider deps | Schema deps | Architectural impact | Ops reqs | Remaining uncertainty | Required owner decisions |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **1** | Secure Pull with **existing provider evidence only** | High (scoped token) | **Best-effort only** | **[F] Not verifiable** (D-06 binding missing) | Cloud read + `send-message` | F4 token store | Low (no new owner) | public HTTPS + egress | sandbox egress; grouping | D-06-waiver, D-11, D-15 |
| **2** | Secure Pull + **provider-authenticated workspace verification** (U-12/U-3) | High | **Verified** | **[F] Verifiable** *if* U-12 + U-3 ship | **new Cloud/agent-server capability** | F4 token store | Medium (upstream work) | + quiesced source (D-04) | availability of new capability | D-02, D-03, D-04, D-06, D-10 |
| **3** | Secure Pull into an **explicitly approved shared workspace** | Medium | Verified *for the shared workspace* | **[F] By definition** | Cloud read | F4 | Medium (grouping awareness) | public HTTPS | sibling exposure | D-06-variant approval, D-24 |
| **4** | Secure Pull with **no verified-workspace claim** (best-effort transfer) | Medium | **Best-effort** — explicitly **not** verified delivery | **None claimed** | Cloud read | F4 | Low | public HTTPS | egress; leak | D-06-waiver, D-15, D-16 |
| **5** | **Abandon** Secure Pull | Highest (no new surface) | n/a | n/a | none | none | none | none | none | D-09 (product) |

- **[F] Alternative 4 is a *deliberate downgrade*** and is **not equivalent** to verified delivery;
  it must be labeled as such and cannot be presented as a delivery guarantee.
- **[R] Alternatives 2 and 3 preserve the guarantee; 1 and 4 weaken it.** The task forbids
  recommending a weakened guarantee merely to appear feasible.

---

## 8. Minimum provider capabilities required

1. **[F] U-12 — workspace-root provenance/binding** (Cloud): resolve the conversation's
   **authoritative** root and **bind** it to `(principal, conversation_id, operation_id)` +
   write-authorization. *Read exists; binding is new.*
2. **[F] U-3 — trusted, non-agent read/delivery acknowledgment** (Cloud/control-plane): an
   authenticated statement bound to the operation reporting `bytes_read` + `sha256` (+ `truncated`).
   *Does not exist.*
3. **[F] D-04 — a quiesced/consistent evidence source** for any event-based evidence.
4. **[F] A scoped credential** (or a delegated Cloud route) so the agent-server's own
   `workspace.working_dir` check can be used **without** the full-privilege `X-Session-API-Key`
   (Plan 05 **B1**).
5. **[F] A stable public HTTPS origin** for the pull endpoint (or an owner-approved ephemeral-origin
   waiver).

---

## 9. Explicit unresolved owner decisions

- **[F] Still OPEN (blockers):** **D-02**, **D-03**, **D-04**, **D-06**, **D-10**, **D-11**,
  **D-14**, **D-22**.
- **[F] Still OPEN (non-blocking/confirmations):** **D-12**, **D-15**, **D-16**, **D-24**.
- **[F] New decisions implied by this investigation:** (a) accept **best-effort** delivery (D-06
  waiver) **or** require U-12/U-3; (b) approve **F4** schema change (option B/C) **or** option E;
  (c) approve a **stable origin** or an ephemeral-origin waiver.

---

## 10. Final feasibility verdict

**`BLOCKED — OWNER ARCHITECTURAL DECISION REQUIRED`.**

Rationale (evidence, not preference):

- **[F]** The D-06 workspace-root **read** exists and ships (Cloud `repositories[].path`), but the
  **identity/authorization binding** (U-12) does **not** — so a **verified** delivery destination is
  not established.
- **[F]** D-02/D-03 remain open: no primitive proves a complete content read; no trusted non-agent
  issuer exists.
- **[F]** F4 requires a **schema change** (no compatible existing field; no stable secret), which is
  an architecture decision.

Because D-06 **and** D-02/D-03 are unresolved, **full Plan 07-B design must not proceed.** A
**limited, best-effort** design may proceed **only** under an explicit owner waiver that delivery is
**not** verified.

> This is **not** `BLOCKED — PROVIDER CAPABILITY REQUIRED` alone, because D-06 also needs an
> **owner architectural decision** (accept best-effort vs require U-12/U-3); the primary blocker is
> the owner decision.

---

## 11. Recommended next step

1. **Owner decision on D-06, D-02, D-03** (verified delivery vs best-effort waiver), and **D-11**
   (pull-token vs delegated route).
2. **Owner approval for the F4 schema change** (option C recommended) — or select option E.
3. Only then begin **Plan 07-B** design, scoped to the chosen guarantee.

---

## 12. Exact statement of what was not implemented

- **[F]** No runtime code, schema, migration, dependency, config, route, or approved decision changed.
- **[F]** No new table/column/index/token store/state transition; no new worker/scheduler/process/
  service/SQLite owner.
- **[F]** No download route, no public endpoint, no URL created/exposed/tested.
- **[F]** No production API call, no credential use, no real user file, no conversation/workspace/
  sandbox change.
- **[F]** **Plan 07-B (design) and Plan 07-C (implementation) were NOT performed and are NOT
  authorized.**
- **[F]** No commit, push, PR, merge, release, deployment, or Autopush activation.
- **[F]** Plan 05, Plan 06, and Plan 07-A reports remain **byte-for-byte unchanged** (§2.1 hashes).
- **Secure Pull and attachment delivery to OpenHands remain NOT IMPLEMENTED.**

---

## 13. Files changed by this task

- **[F] Created:** `docs/reviews/OHB2-PLAN-07-A2-DELIVERY-IDENTITY-AND-EVIDENCE-RESOLUTION.md`
  (this report).
- **[F] Modified:** `.agent/PROGRESS.md` (append-only progress entry).
- **[F] No other file changed.**

> Evidence labels recap: **[F]** verified this session · **[I]** inference · **[U]** unknown/unverified
> · **[G]** documented but not tested · **[R]** recommendation.
