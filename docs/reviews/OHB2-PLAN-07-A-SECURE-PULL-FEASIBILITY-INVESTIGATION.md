# OHB2-PLAN-07-A — Secure Pull-Based Attachment Delivery: Feasibility Investigation

- **Task ID:** `OHB2-PLAN07-A-SECURE-PULL-FEASIBILITY-INVESTIGATION`
- **Type:** Investigation only. **No runtime code, schema, dependency, config, route, or approved
  decision was changed.** No endpoint was created; the local staging directory was not exposed.
- **Author:** OpenHands agent (autonomous). Self-review quality only — **not** an independent review.
- **Date:** 2026-11-14 (repository evidence inspected this session; primary docs retrieved this session).
- **Repo state when written:** branch `main`, HEAD `facf1f42578a20a4a37e220eca016ce3d534e750`
  (= `origin/main`), divergence `0 0`; working tree holds only the pre-existing Plan 05/06 artifacts
  (see §2).

> Evidence labels: **[F] fact** (verified from a repository file / pinned source / configuration this
> session), **[I] inference**, **[U] unknown / unverified**, **[R] recommendation**,
> **[G] documented but not tested**.

---

## 1. Task ID and scope

**Task ID:** `OHB2-PLAN07-A-SECURE-PULL-FEASIBILITY-INVESTIGATION`.

**Proposed direction under investigation (Plan 07-A — "Secure Pull"):**

1. OpenHandBot receives and safely stages a Telegram attachment using the **existing** implementation.
2. OpenHandBot may expose a **narrowly scoped, temporary HTTPS download capability** for that
   specific staged attachment.
3. The **existing** OpenHands conversation receives an instruction containing the temporary download
   reference.
4. The OpenHands **agent downloads** the file into the **correct existing workspace** using an
   available tool (e.g. Terminal).
5. The downloaded file is **verified** using size and SHA-256.

**This is a feasibility investigation only.** It does **not** implement Secure Pull, does **not**
create any endpoint, does **not** expose the staging directory, and does **not** touch the delivery
state machine. Plan 07-B (design) and Plan 07-C (implementation) are **out of scope** and **not
performed** (see §13).

**Overall verdict (see §10):** **`FEASIBLE WITH BLOCKERS — DESIGN ONLY AFTER SPECIFIED BLOCKERS`**.

The flow is *technically plausible* using existing components (in-process ASGI, staged file,
existing conversation identity, agent Terminal), but it is **gated** by unresolved security and
identity blockers — above all the **unproven authoritative workspace root** (D-06) and the
**unproven positive delivery/verification evidence** (D-02/D-03). A successful HTTP GET or a byte
count **must not** be described as proof of correct workspace delivery.

---

## 2. Actual repository baseline

### 2.1 Git state (verified this session)

- **[F] Branch:** `main`. **HEAD / `main` / `origin/main`:** all
  `facf1f42578a20a4a37e220eca016ce3d534e750`. **Divergence** `git rev-list --left-right --count
  origin/main...HEAD` → `0  0`.
- **[F] `git status --short`:**
  - ` M .agent/PROGRESS.md` — **pre-existing** (Plan 05/06 sessions).
  - `?? docs/reviews/OHB2-REPAIR-PLAN-05-SECURE-ATTACHMENT-DELIVERY-INVESTIGATION.md` — pre-existing.
  - `?? docs/reviews/OHB2-REPAIR-PLAN-06-ATTACHMENT-DELIVERY-ALTERNATIVE-ARCHITECTURE.md` — pre-existing.
- **[F] Staged:** none. **Ignored (relevant):** `.openhands/`, `__pycache__/`, `.pytest_cache/`.
- **[F] Prior reports (untouched, hashes recorded):**
  - Plan 05: `sha256 4944714a3469894a01093619a2b75072eb65b403eb3df665db520b35c857e676` (428 lines).
  - Plan 06: `sha256 4450b77cb9981d4997a4f7cb41f3cb3e4821aad93d4d74b7ea982bedd1920303` (617 lines).
- **[F] `.agent/PROGRESS.md`:** 3337 lines; `git diff --numstat` = `85 0` (append-only from the
  Plan 06 remediation). This task appends (see §14).

### 2.2 Configuration and runtime flags

- **[F] `MINI_APP_ENABLED`** default `False` (`bot/config.py:262`). Unchanged.
- **[F] Autopush:** not running in this session (no `autopush`/`main.py` process; no listening
  sockets observed via `ss -tlnp`). No Autopush activation performed.
- **[F] This runtime** is an OpenHands **Kubernetes pod** (`HOSTNAME=runtime-tabexhtzguiacylr-…`),
  `RUNTIME_URL=https://tabexhtzguiacylr.prod-runtime.all-hands.dev`, with published worker ports
  `WORKER_1=12000`, `WORKER_2=12001` (matches the repository `work_hosts` context).

### 2.3 Current attachment lifecycle (verified from code)

- **[F] Staging root:** `<db_dir>/attachment_staging/`, mode `0700`, created/verified fail-closed by
  `ensure_staging_root` (`bot/attachments.py:200–265`); every write uses
  `O_CREAT|O_EXCL|O_NOFOLLOW` (`bot/attachments.py:587`) and is confined to the root
  (`_is_within(root)` + `lstat`, `bot/attachments.py:1323–1326`). Storage filenames are **opaque
  random tokens** (`secrets.token_hex`, `bot/attachments.py:200`), never derived from user input.
- **[F] Row-first ordering:** the durable `attachment_items` row (`status='pending'`) is written
  **before** any bytes; status flips to `stored` only after a complete verified write
  (`bot/attachments.py:22–27`, `bot/db.py:1813`).
- **[F] Batch schema:** `attachment_batches(batch_id, telegram_id, conversation_id, t0, status,
  …)` and `attachment_items(item_id, batch_id, staging_token, display_name, size_bytes, status, …)`
  (`bot/db.py:770–797`); identity evidence table `attachment_message_identity(telegram_id, chat_id,
  message_id, batch_id, conversation_id, …)` (`bot/db.py:804–815`).
- **[F] Lifecycle states (8 defined):** `pending`, `intent_recorded`, `dispatching`, `uncertain`,
  `delivered`, `expired`, `rejected`, `failed` (`bot/db.py:120–137`). **Produced today:** only
  `pending`, `intent_recorded`, `expired` (verified: the only batch-status writes are the `pending`
  INSERT at `bot/db.py:1813`, the `intent_recorded` UPDATE at `bot/db.py:1630`, and the `expired`
  updates at `bot/attachments.py:869`/`:1128`). `dispatching`/`uncertain`/`delivered`/`failed`/
  `rejected` are **defined but never written** — the remote-delivery state machine is **unimplemented**.
- **[F] Expiry/cleanup:** 15-minute batch deadline from a fixed `t0`; `AttachmentReaper` marks the
  batch `expired` **then** reclaims staging bytes (DB-first), driven from the **existing**
  `Watcher` tick via `OpportunisticSweeper` (`bot/attachments.py:1377–1432`, `bot/app.py:231–237`).
  No new worker/scheduler/process.
- **[F] Resource bounds (OHB2-REPAIR-PLAN-01):** streaming download with a hard byte cap (FIX-01),
  bounded concurrent downloads (FIX-02), per-batch/total staging quotas (FIX-03, **disabled by
  default** per owner Option A), fail-closed staging-permission enforcement (FIX-04).

### 2.4 Current delivery behavior (verified)

- **[F] Local acceptance only.** The bot acknowledges local receipt/recording
  (`ATTACHMENT_ACCEPTED_TEXT`, `ATTACHMENT_TEXT_RECORDED_TEXT`, `bot/handlers.py:1601/1627`).
  **No remote delivery to OpenHands exists** — confirmed by `bot/files.py:15` ("مفيش رفع ملفات") and
  by a repo-wide search of `bot/` finding **no** `file/upload`/`session_api_key`/manual-transfer text.
- **[F] The only outbound path the bot has today is the Cloud V1 API** (`bot/openhands_client.py`):
  `GET /app-conversations…`, `POST …/send-message`, `DELETE`, `PATCH`, plus read-only file routes.
  It never holds or uses the agent-server `session_api_key`.

---

## 3. Workstream A — OpenHandBot HTTPS download-serving feasibility

### 3.1 Can a scoped download route coexist with the single Bot + ASGI process? — **[F] Yes**

- **[F]** The bot already runs an **ASGI server in the same asyncio process** as the Telegram
  polling loop: `bot/web/runner.py::web_server_lifespan` starts Uvicorn as a task bound to
  `0.0.0.0:<port>`, wired in `bot/app.py::_wire_mini_app` (post_init/post_shutdown). Exactly one
  process, one `Database`, one `OpenHandsClient` (`docs/MINI_APP.md` §1).
- **[F]** The Mini App is a Starlette app with a route table (`bot/web/app.py:296–425`) and an
  established pattern for **file responses**: `_attachment(data, filename)` returns a `Response`
  with `Content-Disposition: attachment`, explicit `Content-Length`, and the shared security headers
  (`bot/web/app.py:95–108`, `bot/web/app.py:65–83`). A scoped download route can reuse this exact
  helper — **no new dependency, no new process**.

### 3.2 Existing state owner and lifecycle reuse — **[F] Yes, with a caveat**

- **[F]** A route can read the **same** SQLite `Database` object the bot owns (the Mini App already
  does: `bot/web/app.py:118`, "same `db` … read-only"). No second owner, worker, or scheduler is
  needed; expiry can reuse the **existing** `t0 + 15 min` deadline and the existing `expired` state.
- **[I]** Serving does **not** require a new table: a per-file bearer token could be derived from, or
  stored alongside, `attachment_items.staging_token` (already an opaque per-item reference). However,
  **token hashing-at-rest** (see §6.2) would need a storage field; the current schema stores only the
  raw `staging_token`. Adding such a field is a **schema change** and is **out of this task's scope**.

### 3.3 Serve staged files without exposing paths or arbitrary access — **[F] Yes (pattern exists)**

- **[F]** Staging files are addressed by **opaque tokens**, and reads are confined to the staging
  root with `is_safe_workspace_path` + `_is_within` + `lstat` (`bot/attachments.py:1323–1326`,
  `bot/files.py:75–99`). A download handler can map `token → item → file` server-side and stream the
  bytes, **never** accepting a filesystem path from the client. The existing `_attachment` helper
  already emits a sanitized filename (`_HEADER_SAFE_NAME`, `bot/web/app.py:41–43`).
- **[F]** The current export route demonstrates the "authorize → fetch → stream with a hard cap"
  shape (`conversation_export`, `bot/web/app.py:729–751`) and the client already enforces a hard
  response cap for its own reads (`read_file_text_bounded`, `bot/openhands_client.py:207–260`).

### 3.4 Stable public HTTPS access — **[F] Yes on this runtime, [U] on the documented production host**

- **[F]** `docs/OHB2_HOSTING_DECISION.md` §1.2–1.3 **measured** that this runtime's published ports
  (12000/12001) are reachable over **public HTTPS** behind a **TLS-terminating Traefik ingress** with
  a **Let's Encrypt** cert (`CN=*.prod-runtime.all-hands.dev`). The mapping is 1:1 (work-1 ⇄ 12000).
- **[F]** The Mini App already assumes exactly this (`docs/MINI_APP.md` §1:
  `Telegram WebView ──HTTPS──▶ ingress (TLS) ──HTTP──▶ الحاوية:MINI_APP_PORT`).
- **[U]** The **documented production host** (`docs/DEPLOY_KATABUMP.md`) uses **long polling only —
  no inbound port**. So the "existing deployment model provides a stable public origin" claim is
  **true for the OpenHands runtime** and **false/unverified for Katabump**.

### 3.5 Per-file authorization, expiry, revocation, bounded streaming, one-file-only — **[F] Achievable**

- **[F]** The web layer already has the primitives: an in-memory sliding-window rate limiter
  (`bot/web/ratelimit.py`), session auth + owner allowlist + Origin checks
  (`bot/web/app.py::_guarded`), and a strong random-token + SHA-256-at-rest pattern
  (`bot/web/sessions.py::hash_token`, `SessionStore`). A scoped download route can compose these.
- **[F]** Bounded streaming is supported by the ASGI stack (the export route streams a capped zip).
- **[I]** "One-file-only" is enforceable server-side (token binds to exactly one `item_id`).

### 3.6 Accidental token disclosure through logs/proxies/errors — **[F] Risk is real but mitigable**

- **[F]** The bot has a **secret-redaction logging filter** (`RedactingFilter`,
  `bot/errors.py:27–34`, wired in `bot/bootstrap.py:62–80`) and the Mini App **never stores or logs
  the raw session token** (`bot/web/sessions.py` docstring: "التوكن الخام ما بيتخزّنش ولا بيتسجّلش").
  Access logging is **off** (`access_log=False`, `bot/web/runner.py`).
- **[U]** However, a **bearer token placed in a URL path/query** is exposed to the **reverse proxy's**
  own access logs, browser `Referer` headers, and history — none of which the application controls.
  The existing design deliberately keeps the session token in a **cookie**, not a URL. A pull
  reference that must travel in a **message to the agent** cannot use a cookie, so the URL-leak
  surface is **new** (see §6.3). This must be mitigated (short TTL, one-file scope, no logging of
  the path, `Referrer-Policy: no-referrer` which the app already sends, `Cache-Control: no-store`).

---

## 4. Workstream B — OpenHands outbound connectivity and tool feasibility

### 4.1 Can the agent's execution environment make outbound HTTPS requests? — **[G]/[I], not source-proven here**

- **[F] Documented, not tested:** official cookbooks (retrieved this session) show the **sandbox**
  performing outbound work: `clone-and-attach` runs `git clone https://github.com/…` inside the
  sandbox (`POST /api/bash/execute_bash_command` step 3), and `upload-skills` runs a bash extract.
  This demonstrates outbound HTTPS is used **by the sandbox for git**, which strongly implies general
  egress — but the cookbooks do **not** document a network-policy allowlist.
- **[U] Not verified here:** whether egress is unrestricted, proxied, or allowlisted by the runtime.
  No repository source or configuration in this checkout states the sandbox egress policy.
- **[I] No inference from tool existence:** the presence of Terminal does **not** by itself prove
  outbound connectivity (as the task warns). This remains **[U]** until a controlled test (§9).

### 4.2 Is a download-capable tool available in the relevant conversation? — **[G] Likely, not guaranteed**

- **[F]** The SDK default tool set is documented (in `docs/proposals/OH-P0-SECURE-CONVERSATION-
  ATTACHMENT-UPLOAD-API.md:1783–1786`) as `TerminalTool | FileEditorTool | TaskTrackerTool`. A
  Terminal tool (bash) is therefore **expected** in a default OpenHands conversation and can run
  `curl`/`wget`/`git`. **[U]** The **concrete deployment**'s tool set is configuration-dependent and
  was **not** verified against a live conversation.
- **[F]** The bot itself has **no** capability to execute commands in the sandbox: the only shell-like
  route (`POST /api/bash/execute_bash_command`) lives on the agent-server and is guarded by the
  full-privilege `session_api_key` the bot **does not hold** (§5). So the **download must be performed
  by the agent**, not by the bot.

### 4.3 Constraints: size, timeout, redirects, TLS, content handling

- **[F] Bot-side read caps (existing):** `MAX_PREVIEW_BYTES = 256 KiB`, `MAX_EXPORT_BYTES = 16 MiB`
  (`bot/files.py:32`, `bot/openhands_client.py:34`); the client **rejects 3xx redirects** and
  **never disables TLS verification** (`bot/openhands_client.py:60–73`). The staging file cap is
  **3 MiB** (`MAX_ATTACHMENT_BYTES`, `bot/attachments.py:99`).
- **[U] Agent-side caps:** the agent's own download timeout/size limits are deployment-configured and
  **unverified** here.

### 4.4 Evidence classification (per the task's required distinction)

| Claim | Classification |
| --- | --- |
| Sandbox performs outbound HTTPS for `git clone` | **[G]** documented in official cookbook |
| Sandbox can reach **an arbitrary public HTTPS host** | **[U]** unverified |
| Terminal tool is in the default set | **[G]** documented in repo proposal (SDK default) |
| Terminal tool present in the target conversation | **[U]** deployment-dependent |
| Bot can download into the workspace itself | **[F] No** (no sandbox credential) |

---

## 5. Workstream C — Same-conversation and workspace identity

### 5.1 How the bot identifies the existing conversation — **[F] Verified**

- **[F]** The bot stores conversation identity locally: the `watched` table keyed by
  `conversation_id` (`bot/db.py:590`), plus `conversation_id` columns across
  `outbox`/`creation_jobs`/`completion_pending`/`notification_state` (`bot/db.py:610–674`).
- **[F]** Delivery to a conversation is `POST /app-conversations/{conversation_id}/send-message`
  (`bot/openhands_client.py:337–339`) using the **already-held** `OPENHANDS_API_KEY`. The bot also
  re-checks liveness/ownership (`conversation_exists`, `authorize_conversation`,
  `bot/files.py:199+`) and can `resume_sandbox` on `PAUSED` (`bot/openhands_client.py:373`).
- **[I] A pull instruction can be delivered to the exact conversation** by sending one `send-message`
  to the **stored** `conversation_id` — **no** new conversation, **no** new sandbox selection, **no**
  fallback creation. This reuses the existing identity rules unchanged.

### 5.2 The workspace-root problem — **[F] Blocking, unresolved (D-06)**

- **[F]** The bot does **not** know the conversation's **authoritative workspace root**. Per the owner
  decisions register (`docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md:444–509`): the root must
  come from a trusted source (D-06); the agent-server context helper exposes only
  `sandbox_spec.working_dir` (the **ungrouped base**), while the real per-conversation root is
  `grouped_workspace_dir(base, strategy, id)` for any non-`NO_GROUPING` strategy, pinned in the
  `archiveworkspacepath` tag. **D-06 is a BLOCKER** and remains **OPEN**.
- **[F]** Under **sandbox grouping**, the workspace is **shared** with sibling conversations — so
  "same workspace" is a best-effort placement, not a hard guarantee (also recorded in Plan 06 §7 and
  `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md` r7).

### 5.3 What would prove the file landed in the intended workspace? — **[F] No existing primitive**

- **[F]** A successful HTTP GET at the sandbox, or a byte count returned by a tool, proves only that
  **a** transfer happened into **a** path in **a** sandbox. It does **not** prove the path is the
  intended conversation's workspace root, nor that the bytes are the intended file.
- **[F]** The Plan 05/06 evidence chain established there is **no** existing authoritative
  "complete-read" signal: a non-error terminal observation is **not** proof (Plan 06 §6/§8;
  `docs/proposals/OH-P0-…:1787–1791`). The related decisions **D-02** (successful-read signal) and
  **D-03** (trusted issuer boundary) are **BLOCKERS** and remain **OPEN**.
- **[I] The closest available positive signal** for Secure Pull would be an **independent,
  authenticated re-read of the exact file** (size + SHA-256) from the **authoritative** workspace
  root — which is precisely what **D-06 + D-02** must first resolve.

---

## 6. Workstream D — Security threat model and mitigations

Legend: **P** provider-enforced · **O** OpenHandBot-enforceable · **J** joint · **N** not available.

### 6.1 Does Secure Pull avoid the Plan 05 blockers? — partially

| Blocker | Plan 05/06 meaning | Secure Pull effect |
| --- | --- | --- |
| **B1** — no least-privilege upload credential | the only upload key is the full-privilege `session_api_key` (also reaches `execute_bash_command` + secrets) | **[F] Avoided by the bot**: Secure Pull **inverts** the direction — the bot **serves** bytes and the **agent pulls**. The bot never obtains or sends the `session_api_key`. The write into the workspace is performed by the agent's own tool, inside the sandbox trust boundary. **But** the agent's Terminal is itself full-privilege **inside** the sandbox (a different, pre-existing exposure). |
| **B2** — no trusted agent-server origin | the bot cannot pin the agent-server origin for an outbound upload | **[F] Avoided by the bot**: the bot makes **no** outbound call to the agent-server. **But** a **new, inverted** origin problem appears: the **sandbox** must be allowed to reach the **bot's** public HTTPS origin, and the **bot** must trust the **caller** (see §6.4). |

**[F] Conclusion:** Secure Pull **does not resolve B1/B2** — it **sidesteps** them by changing who
makes the network call. It introduces **new** risks (below) and inherits the **D-02/D-03/D-06**
evidence/identity blockers unchanged.

### 6.2 Token design

- **[F] Reusable pattern:** cryptographically strong opaque tokens (`secrets.token_urlsafe(32)`,
  `bot/web/sessions.py`) with **SHA-256 hashing at rest** and server-side expiry — already used for
  Mini App sessions. **[I]** The same pattern fits a pull token.
- **[F] Gap:** the current attachment schema stores the raw `staging_token` (an opaque storage
  filename), not a hash. A **token-hash-at-rest** design would need a new field/table — a **schema
  change**, out of scope here.
- **[R]** Token must be bound to **one attachment**, **one intended conversation**, and the original
  **`(telegram_id, chat_id, message_id)`** identity tuple (`attachment_message_identity`).

### 6.3 Leakage, replay, and access semantics

- **[U] New leak surface:** a pull reference must travel **inside a message to the agent**, so it
  cannot use the cookie mechanism. It is exposed to the **proxy access log**, `Referer`, and any
  agent-side logging of the command. Mitigations available: **short TTL** (≤ batch 15 min),
  **one-file scope**, `Cache-Control: no-store` + `Referrer-Policy: no-referrer` (already emitted,
  `bot/web/app.py:65–83`), and **not** logging the path at the app layer (`access_log=False`).
- **[I] Replay/concurrency:** one-time vs bounded-repeat is a **policy decision**; the safe default
  is **one-time** (delete/disable the token on first successful stream), with the caveat that a
  **partial/interrupted** transfer must be handled (re-issuable within TTL, never a silent partial
  "success").
- **[R] Rate limiting / resource exhaustion:** reuse `SlidingWindowLimiter` per-token and per-IP;
  bound the streamed size by the existing 3 MiB staging cap and the staging-root total quota.

### 6.4 Inverted origin / SSRF and abuse

- **[I] The bot's download route is a new public surface.** It must enforce strict per-file
  authorization, and must **not** be drivable to read arbitrary files (token→single-item mapping
  only). The token itself is the only "authorization" the sandbox holds; it must be scoped so that a
  leaked token grants **one file, briefly**, and nothing else.
- **[F] No SSRF from the bot side** (the bot makes no outbound call). The SSRF concern is **inverted**
  and weaker: the risk is the **bot** being abused as a file oracle, mitigated by token scoping + TTL
  + rate limiting.
- **[U] Unknown:** whether the sandbox can reach the bot's ingress origin at all (network policy) —
  this is the same **[U]** as §4.1 and must be tested.

### 6.5 Independent verification of size and SHA-256

- **[F]** SHA-256 can be computed **at the bot** over the exact staged bytes. **[I]** The agent can
  compute `sha256sum` + `wc -c` after download and report them. **But** per D-02/D-03, that report
  is **not** authoritative unless it comes over an **authenticated, non-agent** channel — the agent's
  own report is **not** trusted evidence (Plan 06 r7, D-03). So **"verified" cannot be asserted**
  from an agent report alone.
- **[R]** Distinguish four facts explicitly: **link issuance** → **download start** →
  **completed transfer (byte count at the bot)** → **verified workspace presence (independent,
  authenticated re-read)**. Only the last is delivery evidence; the first three are **not**.

### 6.6 Threat table

| # | Threat | Mitigation | Enforceable? |
| --- | --- | --- | --- |
| T1 | Token guessing / enumeration | 256-bit opaque token; rate limit; single-item scope | **O** |
| T2 | Token leak via URL/proxy/referer | short TTL; `no-store`; `no-referrer`; no app access log; no path logging | **O** (partial) |
| T3 | Replay / concurrent downloads | one-time token (or bounded), consumed on first full stream | **O** |
| T4 | Partial/interrupted transfer treated as success | require full byte count before marking used; allow re-issue within TTL | **O** |
| T5 | Path traversal / symlink | token→item map; `is_safe_workspace_path` + `_is_within` + `O_NOFOLLOW` | **O** |
| T6 | Filename / content-type trust | sanitized filename; content-type from policy, not client | **O** |
| T7 | Resource exhaustion | 3 MiB cap + quotas + rate limit + bounded streaming | **O** |
| T8 | Wrong workspace / not intended conversation | **requires D-06** (authoritative root) | **N (blocked)** |
| T9 | Agent report trusted as delivery proof | **requires D-02/D-03** (authenticated evidence) | **N (blocked)** |
| T10 | Sandbox cannot reach the bot origin | connectivity policy; **requires test** | **U** |
| T11 | Staging deleted before the agent pulls | TTL/cleanup race (15 min) — see §6.7 | **O** (needs policy) |

### 6.7 Cleanup race

- **[F]** Staging bytes are reclaimed at `t0 + 15 min` by the reaper (DB-first). A pull link that
  outlives the staging copy would fail. **[R]** The link TTL must be **≤** the staging TTL, and the
  "pull in progress" window must be coordinated with cleanup (a policy decision, not implemented).

---

## 7. Workstream E — Hosting and operational requirements

- **[F] Inbound connectivity required:** unlike the current long-polling bot (no inbound port), Secure
  Pull **requires** the bot to be reachable **inbound over public HTTPS** so the sandbox can pull.
- **[F] TLS + stable origin:** required. On the **OpenHands runtime** this exists today (Traefik +
  Let's Encrypt, `docs/OHB2_HOSTING_DECISION.md` §1.2–1.3). **[U]** The origin is **ephemeral** — the
  runtime URL changes on re-provision, so a **stable** origin for a link embedded in a message is
  **not** guaranteed.
- **[F] Storage persistence:** the staged file must survive until the pull completes; on an ephemeral
  runtime this is a **risk**. The documented **Katabump** host has **no inbound port** and a
  4-day renewal (`docs/DEPLOY_KATABUMP.md`), so it **cannot** host the pull endpoint as-is.
- **[F] Request-size/duration/process-lifecycle:** the ASGI stack handles streaming; the 3 MiB cap
  bounds size. Background execution is already in-process.
- **[F] No hosting provider is selected or deployed** here. **[U]** Whether a **free, no-card,
  stable, inbound-HTTPS** host exists is **unverified** (the Phase 6 plan documents candidates with
  caveats: Katabump = no inbound; free PaaS tiers often need a card; Oracle/GCP need a card).

---

## 8. Feasibility matrix

| # | Requirement | Classification | Basis |
| --- | --- | --- | --- |
| F1 | Scoped download route coexists in the single process | **PASS** | §3.1 (`bot/web/runner.py`, `bot/app.py`) |
| F2 | Reuses existing SQLite owner + lifecycle, no new worker | **PASS** | §3.2 (`docs/MINI_APP.md` §1) |
| F3 | Serves staged files by opaque token, no path exposure | **PASS** | §3.3 (`bot/attachments.py:1323`) |
| F4 | Token hashing-at-rest without schema change | **FAIL** | §6.2 (schema stores raw token) |
| F5 | Per-file auth, expiry, revocation, bounded streaming | **PASS** (design) | §3.5 (`ratelimit`, `sessions`, `_attachment`) |
| F6 | Public HTTPS origin on the OpenHands runtime | **PASS** | §3.4 (`OHB2_HOSTING_DECISION.md`) |
| F7 | Stable (non-ephemeral) public origin | **UNVERIFIED** | §7 (runtime URL changes on re-provision) |
| F8 | Production host (Katabump) supports inbound HTTPS | **FAIL** | §7 (`DEPLOY_KATABUMP.md`: polling only) |
| F9 | Sandbox can make outbound HTTPS | **UNVERIFIED** | §4.1 (cookbook `git clone` = **[G]**, not tested) |
| F10 | Download-capable tool (Terminal) in the conversation | **UNVERIFIED** | §4.2 (default set **[G]**; deployment-dependent) |
| F11 | Deliver instruction to the exact existing conversation | **PASS** | §5.1 (`send-message`, stored `conversation_id`) |
| F12 | Determine the authoritative workspace root | **BLOCKED** | §5.2 (D-06 OPEN) |
| F13 | Prove the file landed in the intended workspace | **BLOCKED** | §5.3 (D-02/D-03 OPEN) |
| F14 | Verify size + SHA-256 at the bot | **PASS** | §6.5 (bot owns the staged bytes) |
| F15 | Trust the agent's verification report as delivery proof | **FAIL** | §6.5 (agent report not authoritative) |
| F16 | No token leakage via logs/proxy/referer | **UNVERIFIED** | §6.3 (URL-borne token is a new surface) |
| F17 | No new worker/process/scheduler/DB owner | **PASS** | §3.2, §2.3 |

**Aggregate:** the **serving** half (F1–F6, F11, F14, F17) is **feasible with existing components**.
The **delivery-proof** half (F12, F13, F15) is **blocked** by unresolved owner decisions. The
**operational** half (F7–F10, F16) is **unverified/failed** and needs a controlled test or a stable
host.

---

## 9. Controlled test decision

- **[F] No safe isolated environment is currently available.** The repository's tests are hermetic
  (local sockets via `tests/_real_http.py`, `httpx.MockTransport`); there is **no** existing harness
  that exercises a **live sandbox** pulling from a **live public HTTPS origin**. The documented
  production host has **no inbound port**. This runtime's ingress is **ephemeral** and its use for a
  cross-boundary test is not clearly authorized as safe/non-production.
- **[F] Per the authorization boundary**, I did **not** create a public endpoint, did **not** expose
  the staging directory, and did **not** make production API calls or use credentials. The relevant
  claims (F9, F10, F16) are therefore marked **UNVERIFIED**, **not** PASS.
- **[R] Reproducible test plan (NOT executed — for a separately authorized task):**
  1. Use a **disposable** sandbox and a **disposable** conversation (never a real user conversation).
  2. Serve **synthetic** content (e.g. a few bytes with a known SHA-256) from a **throwaway** local
     HTTPS endpoint on the runtime's published port (or a tunnel), **not** the real staging dir.
  3. Send a `send-message` to the disposable conversation instructing the agent to
     `curl -sS <url> -o /tmp/x && sha256sum /tmp/x && wc -c /tmp/x`.
  4. Observe whether the sandbox reaches the origin (F9/F10) and whether the reported hash/size
     match the synthetic bytes — **without** trusting the report as delivery proof.
  5. Delete the disposable sandbox/conversation and the throwaway endpoint afterwards.
- **Isolation requirements for such a test:** synthetic-only content; no user data; no production
  credentials; no persistent changes; explicit owner authorization for the ephemeral-origin use.

---

## 10. Verdict and recommendation

**Final recommendation: `FEASIBLE WITH BLOCKERS — DESIGN ONLY AFTER SPECIFIED BLOCKERS`.**

Secure Pull is **technically plausible** — the serving half reuses existing, verified components
(in-process ASGI, opaque-token staging, existing conversation identity, existing rate-limit/session
primitives). It **does not weaken** Plan 05/06 conclusions; instead it **sidesteps** B1/B2 by
inverting the network direction, while **inheriting** the unresolved evidence/identity blockers.

**Blockers that must be resolved before Plan 07-B design can be trusted:**

1. **D-06 (authoritative workspace root)** — without it, "correct existing workspace" is unprovable.
2. **D-02 + D-03 (authoritative, non-agent delivery/read evidence)** — without them, "verified
   delivery" cannot be asserted; a byte count or agent report is **not** proof.
3. **Outbound connectivity + Terminal availability (F9/F10)** — must be **tested** in an authorized,
   disposable environment; currently **UNVERIFIED**.
4. **Stable public HTTPS origin (F7/F8)** — the runtime origin is ephemeral; the documented
   production host has no inbound port.
5. **Token-at-rest hashing without a schema change (F4)** — currently a **schema gap**.
6. **Token-leakage policy (F16)** — URL-borne token is a new surface; needs a decided mitigation.

This recommendation is **design-gated**: it does **not** authorize implementation, and it explicitly
**does not** claim that a download endpoint being "technically possible" means delivery is solved.

---

## 11. Dependencies and unresolved decisions

- **D-06** — workspace-root source + identity binding. **OPEN, BLOCKER.**
- **D-02** — successful-read / delivery signal. **OPEN, BLOCKER.**
- **D-03** — trusted issuer boundary + authentication. **OPEN, BLOCKER.**
- **D-04** — quiesced evidence source. **OPEN, BLOCKER.**
- **D-10/D-11** — capability ownership + scoping mechanism. **OPEN** (relevant if the bot ever holds
  an agent-server credential; Secure Pull avoids this).
- **D-12** — size/type limits (quota enforcement **disabled by default**). **OPEN, policy.**
- **D-14/D-16/D-22** — delivery mechanism, idempotency, outbox integration. **OPEN.**
- **D-15** — `expires_at` window + staging-only reclaim. **OPEN, near-blocker.**
- **D-24** — delivered-file permissions/ownership. **OPEN, near-blocker.**

---

## 12. Recommended next step

1. **Owner decision on D-06, D-02, D-03** (the identity/evidence blockers) — these gate any
   trustworthy "correct workspace" claim.
2. If the owner wishes to proceed, authorize a **narrowly scoped, disposable** connectivity test
   (§9) to convert F9/F10/F16 from **UNVERIFIED** to measured facts.
3. Only then begin **Plan 07-B (design)** — with the workspace-root contract, the authenticated
   evidence channel, and the token/leakage policy fixed as explicit design inputs.

**Do not begin Plan 07-B design before the blockers above are resolved or explicitly waived by the
owner.**

---

## 13. Explicit authorization boundary

- **[F] No runtime code, schema, dependency, config, route, or approved decision was changed.**
- **[F] No public download endpoint was created; the local staging directory was not exposed.**
- **[F] No database/outbox/worker/polling/acknowledgement/delivery-state-machine change.**
- **[F] No production API call, no credential use, no real user file, no account/infrastructure/DNS/
  TLS change.**
- **[F] Plan 07-B (design) and Plan 07-C (implementation) were NOT performed and are NOT authorized.**
- **[F] No commit, push, PR, merge, release, deployment, or Autopush activation.**
- **[F] Plan 05 and Plan 06 reports remain byte-for-byte unchanged (hashes in §2.1).**
- **Attachment delivery remains NOT IMPLEMENTED.** This report does not claim otherwise.

---

## 14. Files changed by this task

- **[F] Created:** `docs/reviews/OHB2-PLAN-07-A-SECURE-PULL-FEASIBILITY-INVESTIGATION.md` (this report).
- **[F] Modified:** `.agent/PROGRESS.md` (append-only progress entry).
- **[F] No other file changed.** No runtime source, tests, config, protected path, or migration.

> Evidence labels recap: **[F]** verified this session from repo/pinned source/config · **[I]**
> inference · **[U]** unknown/unverified · **[G]** documented but not tested · **[R]** recommendation.
