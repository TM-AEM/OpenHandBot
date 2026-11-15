# OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE — Design & Threat Model

- **Task ID:** `OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE-AND-SECURITY-DESIGN`
- **Revision:** r5 — P0 reopen decision gate re-validation under
  `OHB2-P0-ATTACHMENT-WORKFLOW-REOPEN-AND-SECURE-COMPLETION` (§27): P0 was **explicitly reopened** by
  the owner, the feasibility gate was re-run against the current public API surface, and it **still
  fails** (`BLOCKED — SECURE OPENHANDS UPLOAD CAPABILITY NOT ESTABLISHED`). §1–§26 preserved. Earlier:
  r4 decision record under `OHB2-PLAN-01-APPROVE-DEFERRED-P0-AND-CONTINUE-STAGES-0-5` (§26.4).
- **Related task:** `OHB2-FILE-ATTACHMENT-TEXT-GATE-15M` (deferred — see §26.4)
- **Status:** `BLOCKED — SECURE OPENHANDS UPLOAD CAPABILITY NOT ESTABLISHED` (§27.2). The owner
  **reopened** P0 on 2026-11-12 and authorized implementation **only if** a secure supported upload
  path exists; it does not. Technical cause unchanged (`BLOCKED_BY_SECURITY_OR_API_LIMITATION`, §22).
  The decisive blockers remain **verified** rather than assumed: (B1) the only upload path needs a
  **full-privilege** agent-server credential, and (B2) the `conversation_url` **trusted origin**
  cannot be established from evidence. Both are hard blockers; neither is a weak-check shortcut.
  The earlier Option D product deferral (§26.4) is **superseded** by this reopen; the **safe
  rejection** of unsupported attachments remains in force (fail-closed).
- **Type:** Design-only. No implementation, no schema change, no dependency, no runtime change.
- **Author:** OpenHands agent (autonomous). **Self-review only** (§15, §23) — not an independent security review.
- **Date:** 2026-11-11
- **Repo state when written:** branch `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW`, HEAD `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c` (= `origin/main`).

> This is a **new proposal**. It does not modify `AGENTS.md`, `docs/PLAN.md`,
> `docs/plan-openhandBot-2.md`, or any approved decision. It exists to be reviewed and approved,
> or rejected, before any implementation task.

---

## 1. Current architecture baseline (verified from the repository)

The bot is a thin single-process mediator between Telegram and the OpenHands Cloud V1 API.

| Fact | Evidence |
| --- | --- |
| One HTTP integration target: `{base_url}/api/v1`, `Authorization: Bearer` | `bot/openhands_client.py:1-4,38-48` |
| One client instance owns all OpenHands calls; no second client | `bot/openhands_client.py`; `bot/files.py:130`; `bot/handlers.py:130` |
| No arbitrary-URL client exists | `grep -rn "AsyncClient" bot/` → only `bot/openhands_client.py:40` |
| 3xx redirects are rejected (never followed) | `bot/openhands_client.py:66-70` (OHB2-N10-28D) |
| URL logging is suppressed (httpx/httpcore/telegram) to avoid token leakage | `bot/bootstrap.py:82-83` |
| `sandbox_id` is known and used only for `POST /sandboxes/{id}/resume` | `bot/outbox.py:348-352`; `bot/openhands_client.py:373-374` |
| `conversation_url` / `session_api_key` are **not read anywhere today** | `grep -rn "conversation_url\|session_api_key" bot/ tests/` → none |
| Documented stance: no file upload, no second client/worker/table | `bot/files.py:15` |
| Single-owner resource rule | `docs/plan-openhandBot-2.md:61` (§4.1) |
| Architecture diagram: bot ↔ OpenHands Cloud REST V1 only | `docs/PLAN.md:51-58` |
| Sessions stored as SHA-256 hash only (raw token never persisted) | `bot/db.py` `web_sessions` table |
| No Document/Photo/Voice handler exists; non-text messages are dropped | `bot/app.py:80-125` (only `MessageHandler(TEXT & ~COMMAND)`) |
| Telegram update dedup is persistent (`processed_updates`) | `bot/db.py`; `bot/handlers.py` `dedupe_update` |
| At-most-once outbox delivery with CAS states | `bot/outbox.py` |

**Baseline conclusion:** today the bot has exactly **one** external integration (Cloud V1, bearer
auth, JSON-only, redirect-rejecting, no upload). Any upload capability is a **new** integration.

---

## 2. Verified API facts and their sources

All facts below were read from official, public artifacts. **No production call was made and no
production credential was used.**

### 2.A OpenHands Cloud V1 API

- **Spec fetched:** `https://app.all-hands.dev/openapi.json` → `info.version = 1.87.1`, 242 paths.
- **No upload endpoint exists.** Counted in the raw spec: `"upload"` = 0, `"multipart"` = 0,
  `"format": "binary"` = 0. Every `/api/v1/` request body is `application/json`.
- **File operations are read-only:**
  - `GET /api/v1/app-conversations/{conversation_id}/file` — "Read a file from a specific
    conversation's sandbox workspace."
  - `GET /api/v1/app-conversations/{conversation_id}/files` — "List Conversation Files".
  - No `POST`/`PUT`/`PATCH` file route exists under `/api/v1/`.
- **`send-message` cannot carry a file:** `POST /api/v1/app-conversations/{conversation_id}/send-message`
  body `content` is `anyOf: [TextContent, ImageContent]` only. `ImageContent` carries `image_urls`
  (strings: http(s) or base64 data URLs). No generic file/attachment content type.
- **Cloud V1 DOES expose Agent Server connection details** on the conversation object
  (`AppConversation` schema, `GET /api/v1/app-conversations?ids=…` and `/search`):
  - `conversation_url` (`string | null`) — "The URL where the conversation may be accessed".
  - `session_api_key` (`string | null`) — "The Session API Key for REST operations."
  - (Distinct from `conversation_ui_url`, which is the browser UI link.)
  - Source: `openhands/app_server/app_conversation/app_conversation_models.py` (field defs) and
    `docs.openhands.dev/.../batch-get-app-conversations.md` / `search-app-conversations.md`.
- **Cloud provides no upload proxy.** The Cloud V1 proxies only *some* runtime calls
  (`/git/changes`, `/git/diff`, per their descriptions: "Proxy `GET /api/git/…` on the
  conversation's runtime"). There is **no** file-upload proxy route in v1.87.1.

### 2.B Agent Server API

- **Spec fetched:** `https://docs.openhands.dev/openapi/agent-sdk.json`
  (`info.title = "OpenHands Agent Server"`, `info.version = 0.1.0`, 40 paths).
- **Upload operation:** `POST /api/file/upload?path=<absolute>` (query parameter), multipart field
  `file`. Source of truth: `openhands-agent-server/openhands/agent_server/file_router.py`
  (`@file_router.post("/upload")`, `_upload_file`).
  - Response: `{"success": true, "file_size": <bytes>}` (`FileUploadResult(Success)`).
  - 400 if `path` is not absolute; 422 on validation error.
  - **No workspace confinement:** the handler checks only `Path(path).is_absolute()`. There is **no**
    `is_relative_to(workspace)` / `resolve()` confinement in `_upload_file`. Any absolute path the
    sandbox process can write is accepted (e.g. `/etc/cron.d/…`, `/home/*/.bashrc`, `/tmp/…`).
  - **No server-side size limit** in the agent-server config; the body is streamed to disk in 8 KB
    chunks (`_upload_file`). Limits, if any, come from the sandbox/proxy in front, not the API.
- **Authentication (critical):** a **single** `X-Session-API-Key` header guards **every** `/api/*`
  route. Source: `openhands-agent-server/openhands/agent_server/api.py` — one
  `api_router = APIRouter(prefix="/api", dependencies=[Depends(require_initialized),
  Depends(check_session_api_key)])` mounts `bash_router`, `conversation_router`, `file_router`,
  `credential_binding_router`, `skills_router`, `git_router`, `hooks_router`, `mcp_router`, …
  - Header-only on regular `/api/*` routes (`F02.http-header-only`: cookie, `?session_api_key=`, and
    `Authorization: Bearer` all get 401 on non-workspace routes).
  - **No per-endpoint authorization and no upload-scoped credential.** The same key reaches
    `POST /api/bash/execute_bash_command` (arbitrary command execution) and
    `POST /api/conversations/{id}/secrets`.
  - Official doc: an agent-server session key "can execute commands and read or write files in its
    configured workspace" (`docs.openhands.dev/sdk/arch/agent-server.md`).
- **`conversation_url` construction (source):** in
  `openhands/app_server/app_conversation/live_status_app_conversation_service.py`,
  `_build_conversation()` takes the sandbox `exposed_urls` entry whose `name == AGENT_SERVER`,
  appends `/api/conversations/{conversation_id_hex}`, and copies `sandbox.session_api_key`. The
  `AGENT_SERVER` URL itself comes from the runtime API (`runtime['url']`) in
  `openhands/app_server/sandbox/remote_sandbox_service.py`.

### 2.C Source/artifact references (all public)

- Cloud OpenAPI: `https://app.all-hands.dev/openapi.json` (v1.87.1).
- Agent Server OpenAPI: `https://docs.openhands.dev/openapi/agent-sdk.json` (v0.1.0).
- Agent Server auth: `https://docs.openhands.dev/sdk/arch/agent-server.md`.
- Upload endpoint doc: `https://docs.openhands.dev/sdk/guides/agent-server/api-reference/files/upload-file.md`.
- Conversation URL / session key fields:
  `https://docs.openhands.dev/openhands/usage/cloud/api-reference/conversations/batch-get-app-conversations.md`.
- Source repos: `github.com/OpenHands/software-agent-sdk`
  (`openhands-agent-server/openhands/agent_server/{api,file_router,auth_router}.py`,
  `.agents/skills/verify-agent-server/references/feature-map/F02-auth-and-sessions.md`,
  `F14-files.md`), `github.com/OpenHands/sandbox-server`
  (`openhands/app_server/app_conversation/live_status_app_conversation_service.py`,
  `openhands/app_server/sandbox/remote_sandbox_service.py`).

---

## 3. Explicitly UNVERIFIED assumptions

These are **not** established and must not be treated as facts:

1. **UNVERIFIED — Cloud host pattern for `conversation_url`.** We could not obtain, from
   documentation or the repo, the concrete, stable host(s) that OpenHands Cloud returns in
   `conversation_url`. Source shows it derives from the runtime API's `runtime['url']`
   (`remote_sandbox_service.py`), which is infrastructure-dependent (path-mode
   `…/{runtime_id}/…` vs subdomain-mode `…/{service}-{host}/…`, per `_build_service_url`). Whether
   the Cloud returns an `https://` origin with a fixed suffix, and whether it changes across
   regions/versions, is **unknown** to the bot. **No production call was made to learn it.**
2. **UNVERIFIED — that Cloud always populates `conversation_url`/`session_api_key`.** They are
   nullable; the live-status source only fills them when the sandbox is RUNNING with exposed URLs.
3. **UNVERIFIED — sandbox filesystem scope.** The exact set of paths the sandbox user can write
   (does it run as root? is `/etc` writable?) is not established. The API itself imposes no
   confinement, but the *container* may.
4. **UNVERIFIED — actual upload size ceiling** imposed by the Cloud runtime/proxy in front of the
   agent server (the API has none).
5. **UNVERIFIED — key lifetime/rotation semantics for Cloud-issued `session_api_key`.** The
   agent-server supports rotation via `OH_SESSION_API_KEYS_*`, but Cloud's issuance/refresh policy
   for these per-conversation keys is not documented in what we read.
6. **ASSUMPTION (conservative) — the `session_api_key` grants the full agent-server API**, because a
   single dependency guards all `/api/*` routes. We assume worst case: command execution.

---

## 4. Architecture diagram / sequence diagram

### 4.1 Trust boundaries (proposed Option A)

```mermaid
flowchart LR
    U[Telegram user] -->|file + text| BOT[OpenHandBot<br/>single process]
    BOT -->|Bearer, JSON| CLOUD[OpenHands Cloud V1<br/>app.all-hands.dev/api/v1]
    CLOUD -->|conversation_url + session_api_key| BOT
    BOT -->|X-Session-API-Key, multipart| AS[Agent Server<br/>= conversation_url host]
    AS --> FS[(Sandbox workspace + arbitrary writable paths)]

    subgraph Boundary A: trusted single owner
      BOT
    end
    subgraph Boundary B: Cloud API
      CLOUD
    end
    subgraph Boundary C: NEW external target
      AS
    end
```

The new element is **Boundary C**: a second external target with a second auth scheme. Boundary C is
reached only via a `conversation_url` supplied by Boundary B; the bot must validate that URL before
trusting it.

### 4.2 Proposed 15-minute pending workflow (design only — NOT implemented)

```mermaid
sequenceDiagram
    participant U as Telegram user
    participant B as OpenHandBot (SQLite)
    participant C as Cloud V1
    participant A as Agent Server

    U->>B: send file (no text)
    B->>B: store staged file (pending batch, T0 = first file)
    B-->>U: "في انتظار أوامرك"
    U->>B: send text (within 15 min)
    B->>B: mark batch = dispatching (persist BEFORE any external call)
    B->>C: GET /app-conversations?ids=CID  (conversation_url, session_api_key)
    C-->>B: conversation_url + session_api_key (nullable)
    B->>B: validate conversation_url (HTTPS, allowlist, no redirect, no private IP)
    B->>A: POST /api/file/upload?path=... (multipart) [X-Session-API-Key]
    A-->>B: {success, file_size}  |  timeout/error
    B->>C: POST /app-conversations/CID/send-message (text)
    C-->>B: success
    B->>B: mark batch = sent (idempotency key)
    B-->>U: confirmation
    Note over B: on expiry (no text) -> delete staged files, mark expired
    Note over B: on uncertain upload -> mark uncertain, reconcile (never blind retry)
```

---

## 5. Credential acquisition and lifecycle design

### 5.1 Where the key originates

- `session_api_key` is returned by Cloud V1 on the conversation object
  (`GET /api/v1/app-conversations?ids=CID`), together with `conversation_url`.
- It is associated with **exactly one conversation** (and its sandbox). The bot already fetches the
  conversation object in `bot/outbox.py` (`get_conversation`), so no new discovery mechanism is
  strictly required — but the field is currently ignored.

### 5.2 Storage and exposure rules (design constraints)

| Rule | Enforcement |
| --- | --- |
| Never expose to the Mini App / browser / Telegram user | Keep it inside the server-side client; never place in `web_sessions.profile`, JSON responses, or Telegram messages. |
| Never persist if avoidable | Prefer **on-demand fetch** per upload (fetch conversation → use key → drop). Avoids at-rest secret. |
| If persistence is unavoidable | Encrypt at rest with a key from env (there is no `OH_SECRET_KEY`-style facility today) — **this is a new capability** and a reason to prefer on-demand fetch. |
| Never log | Follow the existing `bot/bootstrap.py` redaction precedent; add the key to the redaction set and ensure `httpx` URL logs are suppressed for the agent-server host. |
| Never include in exceptions | `ApiError` messages must be constructed without the key; the existing client pattern avoids echoing headers. |
| Access restriction | Only the upload code path may read the key; no generic getter that other modules can call. |

### 5.3 Lifecycle

- **Expiration/revocation:** key validity is tied to the sandbox. A stale key ⇒ 401. The bot must
  treat 401 as "fetch a fresh conversation object and retry once", then fail closed.
- **Rotation/recovery:** the agent-server rotates keys across restarts; a conversation may present a
  new key after resume. On-demand fetch per upload naturally handles rotation.
- **Failure handling:** a 401/403/404/410/503 from the agent server is a **hard failure** for that
  upload; never blind-retry (see §9). Surface a clear Arabic error and leave the batch
  `uncertain` for reconciliation.

### 5.4 The credential is full-privilege (design consequence)

Because one key guards all `/api/*` routers (§2.B), holding it is equivalent to holding
"execute commands in this sandbox + read/write files + manage conversation secrets". The bot would
therefore be entrusted with a **command-execution-capable** credential to perform a **file upload**.
There is **no documented least-privilege option**. Per §5.D of the task, this must be weighed
explicitly — see §11 and §13.

---

## 6. Network and endpoint validation design

The bot must not trust a URL merely because it came from the API. Required, enforceable rules:

| # | Rule | Enforceable? |
| --- | --- | --- |
| N1 | Scheme must be `https` (reject `http`, `file`, others) | Yes (parse + compare) |
| N2 | Host must match an **allowlist** of documented Cloud runtime hosts | **NOT currently** — pattern UNVERIFIED (§3.1) |
| N3 | Reject any userinfo (`user:pass@host`), non-default explicit ports outside an allowed set | Yes |
| N4 | Resolve DNS and reject private/loopback/link-local/multicast/ULA/CGNAT ranges; pin the resolved IP for the connection | Yes (resolve → validate → connect to IP with SNI/Host preserved) |
| N5 | Disable redirects (`follow_redirects=False`) and treat any 3xx as failure | Yes (matches existing client policy) |
| N6 | Reject path that is not the expected `/api/conversations/{uuid}` prefix | Yes |
| N7 | Guard against DNS rebinding (validate the IP actually connected to, not just the pre-check) | Partially (pin IP at connect; httpx makes this awkward) |
| N8 | TLS verification on (never disabled) | Yes |

**Gate G1 (SSRF):** N2 is the blocker. Without a documented, stable host allowlist for
`conversation_url`, the only alternatives are (a) an IP-range check plus "any https host" — which is
**a weak check and explicitly rejected by the task**, or (b) an operator-configured allowlist in
`.env` — which pushes the trust decision to deployment config and is not verifiable from the repo.
Per the task: *"If a safe validation policy cannot be established for actual OpenHands Cloud
endpoints, state that the design is blocked rather than proposing a weak hostname check."*
→ **The design is blocked on G1.**

---

## 7. Threat model and mitigations

Legend — Enforceable: **Y** = technically enforceable in the proposed architecture; **P** = partial;
**N** = only a documentation promise (rejected as a mitigation).

| # | Threat | Attack scenario | Impact | Required mitigation | Enf. | Residual risk | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T1 | Key leakage via logs/exceptions/DB dump/debug | `session_api_key` echoed in an `ApiError`, an httpx URL log, a traceback, or a Mini App JSON | Full sandbox command execution for an attacker who reads the log/dump | Redaction set incl. the key; no key in URLs/messages; on-demand fetch (no at-rest copy); never in `web_sessions` | P | Any process-level memory/log access still sees it transiently | Unit test: assert key never appears in log records/`ApiError` strings; grep logs in tests |
| T2 | Cross-conversation / cross-user Agent Server access | Bot uses conversation A's key against conversation B's URL, or a stale key from another conversation | File written to the wrong workspace | Bind key↔URL from the **same** conversation object fetch; never cache across conversations | Y | — | Test: mismatched key/URL pair is rejected before any call |
| T3 | SSRF via manipulated `conversation_url` / redirect / DNS | Malicious/erroneous URL points at internal service; or a 30x redirects to metadata | Internal service access, credential leak to attacker host | N1–N8; **host allowlist (N2) is the gate** | **N** (until G1 closed) | HIGH while unclosed | SSRF test suite: `http`, `169.254.169.254`, `127.0.0.1`, `10.x`, `user@host`, redirect → all rejected |
| T4 | Path traversal / arbitrary path upload | Upload to `/etc/cron.d/x` or `../../…` via the `path` query | Overwrite sandbox files; possible sandbox escape if writable system paths | Bot-side: generate destination path internally under a fixed workspace subdir; reject any client-controlled path; normalize + confine | Y (bot-side) | Server imposes **no** confinement, so bot-side confinement is the only guard | Test: only internally generated `/workspace/project/.ohb2_uploads/<safe>` paths are ever sent |
| T5 | Privilege abuse (command execution) via the key | Compromised bot process calls `/api/bash/execute_bash_command` with the key | Arbitrary command execution in the sandbox | **No least-privilege credential exists** → cannot be mitigated within the design | **N** | HIGH: this is the core objection to Option A | N/A (accepted risk if Option A proceeds) |
| T6 | Cross-conversation file attachment | User's file lands in another conversation | Data disclosure to wrong workspace | Same as T2 | Y | — | Same as T2 |
| T7 | Credential expiration/revocation/stale | Upload fails 401 after rotation | Feature fails; possible retry storm | On-demand fetch; on 401 refresh once then fail closed | Y | Feature outage | Test: 401 → single refresh → still 401 → fail closed, no loop |
| T8 | Malicious/oversized file, MIME spoofing, storage exhaustion | Multi-GB file or spoofed type | Disk exhaustion in sandbox; downstream harm | Bot-side size cap + type allowlist + extension sanitization; reject before upload | Y (bot-side) | Server has no size limit; bot cap is the guard | Test: oversize/spoofed rejected locally |
| T9 | Duplicate upload after timeout/uncertain response | Timeout → retry uploads twice | Duplicate file, wasted quota | Idempotency key per batch + "uncertain ⇒ reconcile, no blind retry" | Y (design) | True exactly-once impossible across HTTP | Test: injected timeout yields `uncertain`, not a second upload |
| T10 | Crash between upload and prompt submit | File uploaded, text never sent | Orphan file, user confusion | Persist batch state (`uploaded`/`dispatched`) before each external step; reconcile on restart | Y | — | Restart-simulation test |
| T11 | Temp file exposure / cleanup failure | Staged file remains world-readable / never deleted | Local data leak | Staged dir with restrictive perms; TTL cleanup on expiry/startup | Y | Crash before cleanup | Test: expiry deletes staged files; startup sweeps stale ones |
| T12 | Concurrent requests / races | Two texts arrive for one batch; double dispatch | Duplicate prompt/upload | Single-worker + DB CAS state machine (mirror the outbox pattern) | Y | — | Concurrency test |
| T13 | Redirects / TLS / unsafe proxy | MITM or redirect to attacker host | Credential theft | `follow_redirects=False`; TLS verify on; treat 3xx as failure | Y | Proxy trust is deployment-level | Test: redirect → failure, no `X-Session-API-Key` forwarded |
| T14 | Bot process compromise + stored keys | Attacker with the bot's env/memory reaches the key | Command execution in the owner's sandbox | Minimize key lifetime (on-demand), never persist, redact | P | HIGH (same as T5) | Review of secret handling paths |

**Honest summary:** T3, T5, and T14 are the load-bearing risks. T5/T14 cannot be reduced within the
design (no least-privilege credential); T3 cannot be closed without G1. Everything else is
mitigable with normal engineering.

---

## 8. File handling and upload lifecycle (proposal, not fact)

All values below are **proposals**, not existing facts. They must be confirmed against the repo/API
before implementation.

| Item | Proposed value | Rationale |
| --- | --- | --- |
| Max size | 20 MB (proposal) | Conservative; no server limit exists |
| Allowed types | Text/code, PDF, images, common office docs (proposal) | Avoid executables/archives |
| Content validation | Magic-byte sniff + declared-type cross-check | Detect MIME spoofing |
| Internal naming | `{batch_id}/{index}-{sha256[:16]}.{safe_ext}` | Deterministic, collision-safe, no client name trust |
| Destination dir | `/workspace/project/.ohb2_uploads/<batch_id>/` (proposal) | Inside workspace; hidden |
| Path normalization | `posixpath.normpath`, reject `..`, NUL, backslash, control chars | Mirror `bot/files.py` allowlist rules |
| Upload timeout | 60 s (proposal) | Match SDK client default |
| Temp lifecycle | Staged under a restrictive dir; deleted on success, expiry, or startup sweep | Bound exposure |
| Partial upload | Delete partial; mark batch `uncertain` | Never leave half-written file as success |
| Uncertain result | Mark `uncertain`; reconcile by re-fetching state; never blind-retry | Matches outbox philosophy |

---

## 9. Failure modes and reconciliation strategy

- **State machine (proposed):** `pending → dispatching → uploaded → sent`, with side states
  `expired`, `uncertain`, `failed`.
- **Before any external call:** persist the intent (mirror `bot/outbox.py` CAS discipline).
- **Timeout / 5xx / connection error on upload:** mark `uncertain`. Reconciliation re-fetches the
  conversation and, if feasible, lists the destination to detect whether the file landed; otherwise
  surface the ambiguity to the user. **No blind retry.**
- **Crash between upload and `send-message`:** on restart, a batch in `uploaded` resumes at the
  `send-message` step; a batch in `dispatching` is treated as `uncertain`.
- **Expiry (no text within 15 min):** delete staged files, mark `expired`, notify the user.
- **Distributed-transaction limitation (unavoidable):** the bot's SQLite and the Agent Server cannot
  commit atomically. The bot can only guarantee *local* at-most-once intent plus *idempotent
  reconciliation*. A crash exactly between a successful upload and the local state write leaves an
  orphan file that the bot may not know about; the only mitigation is a reconciliation read, which
  the API does not guarantee (no "list uploads" endpoint). This is a **known residual limitation**.

---

## 10. Compatibility with the 15-minute pending workflow

The workflow (receive file → persist pending → "في انتظار أوامرك" → 15-min window → on text upload
file(s) + send text to the **same** conversation → expire/cleanup → restart-safe → no duplicates →
uncertain reconciliation) is fully expressible **only if Option A is approved**. The workflow's
hard dependency is a working upload path (§2). Without it, the workflow cannot be implemented at
all (which is why `OHB2-FILE-ATTACHMENT-TEXT-GATE-15M` is blocked).

---

## 11. Alternatives comparison

| Criterion | **Option A** — Agent Server upload (existing ownership) | **Option B** — Keep Cloud V1, reject uploads | **Option C** — Defer until Cloud offers upload / a restricted credential |
| --- | --- | --- | --- |
| Security exposure | **HIGH**: full-privilege (command-exec) credential; SSRF surface | **None added** | **None added** |
| Architectural impact | **Large**: second external target + second auth scheme; must stay inside `OpenHandsClient` ownership | **None** | **None** |
| Implementation complexity | High (upload client, URL validation, state machine, cleanup, reconciliation) | Trivial (reject with a clear message) | Trivial now |
| Operational requirements | Must validate hosts; handle rotation; monitor failures | None | None |
| Failure/recovery | Complex (uncertain states, orphan files) | N/A | N/A |
| 15-min workflow compatibility | Full | Not possible | Not possible (until enabled) |
| Long-term maintenance | High (tracks agent-server churn) | None | None until enabled |

**Evidence-driven recommendation:** **Option C is the safest default; Option A should not proceed
to implementation now** because (i) the SSRF gate G1 cannot be closed from available evidence, and
(ii) the credential is full-privilege with no least-privilege alternative (T5/T14). Option B is the
current effective behaviour and is the honest answer for `OHB2-FILE-ATTACHMENT-TEXT-GATE-15M` in the
meantime.

---

## 12. Required approvals and unresolved questions

**Approvals required before any implementation:**

1. Explicit approval of a **second external integration** (new host + `X-Session-API-Key` scheme),
   acknowledging it departs from `bot/files.py:15` and `docs/plan-openhandBot-2.md:61`.
2. Explicit acceptance of the **full-privilege credential risk** (T5/T14) *or* a decision to reject
   the integration.
3. Approval of the **SSRF policy** once G1 is resolved (see below).

**Unresolved questions / evidence required (blocking):**

- **Q1 (G1):** What are the concrete, stable host(s)/patterns OpenHands Cloud returns in
  `conversation_url`? Evidence needed without a production call: an official doc stating the
  runtime host pattern, or a provider-committed allowlist. *Without this, the SSRF mitigation is a
  weak check and must not be shipped.*
- **Q2:** Is there any restricted credential (upload-only) on the roadmap? If not, Option A carries
  command-execution privilege.
- **Q3:** What is the Cloud `session_api_key` lifetime/rotation policy?
- **Q4:** What real upload size ceiling does the Cloud runtime enforce?
- **Q5:** Does Cloud populate `conversation_url`/`session_api_key` for every RUNNING conversation
  the bot manages (nullable fields)?

---

## 13. Recommendation

**Do not implement.** Status: `NEEDS_EVIDENCE`.

- If the owner wants file attachments soon and accepts the risk, **Option A is designable** for
  T1/T2/T4/T6/T7–T13, but it remains blocked by **G1 (SSRF host validation)** and by the
  **full-privilege credential (T5/T14)**. Proceeding without Q1/Q2 would mean shipping a weak host
  check and an over-privileged credential — both explicitly disallowed.
- The conservative, reversible choice today is **Option B** (reject uploads with a clear Arabic
  message), keeping `OHB2-FILE-ATTACHMENT-TEXT-GATE-15M` blocked until Q1/Q2 are answered, with
  **Option C** as the strategic position.

---

## 14. Test strategy for a future implementation task (if approved)

Only *after* approval and only for the implemented code:

1. **URL validation (SSRF):** table-driven tests — reject `http://`, `file://`, userinfo,
   private/loopback/link-local/ULA IPs, unexpected ports, wrong path prefix, and any 3xx response;
   assert `X-Session-API-Key` is never sent to a rejected host.
2. **Credential redaction:** assert the key never appears in log records, `ApiError` text, or Mini
   App payloads.
3. **Path safety:** assert only internally generated destination paths are ever transmitted; reject
   traversal/NUL/backslash.
4. **Size/type:** oversize and MIME-spoofed inputs rejected locally.
5. **State machine:** `pending→dispatching→uploaded→sent`, plus `expired/uncertain/failed`;
   injected timeout ⇒ `uncertain` and **no** second upload; restart between upload and send resumes
   correctly.
6. **Cleanup:** expiry and startup sweeps delete staged files.
7. **Concurrency:** two texts for one batch dispatch exactly once (CAS).
8. **Conversation binding:** key/URL from the same fetch; mismatch rejected.
All tests must use a fake transport (no real network), mirroring the existing
`tests/test_outbox*.py` style.

---

## 15. Adversarial self-review (self-review only — NOT independent)

Challenging the proposal as a security reviewer:

1. **"HTTPS + API key = secure" is rejected.** The proposal explicitly relies on host allowlisting
   and IP validation, not on TLS alone.
2. **Weak-check rejection.** I refused to propose "any https host + private-IP block" as the SSRF
   mitigation; I marked G1 as **blocked** instead. ✅ (matches task instruction)
3. **Second resource owner?** The design keeps a **single** client boundary and a **single** worker
   (the existing outbox/state owner); it does **not** add a second process, DB, or scheduler. ✅
4. **Documentation-only mitigations?** The design does not rely on "we will be careful" anywhere;
   every listed mitigation is a code-level check, except where explicitly marked `N` (T3 until G1,
   T5/T14 — accepted risk). ✅
5. **Credential exposure:** on-demand fetch avoids at-rest storage; redaction is testable; the key
   never touches the Mini App/Telegram. Residual: in-process memory (T1/T14). Honest.
6. **Privilege escalation:** identified and **not** hand-waved — there is no least-privilege
   credential, so this is a reason to reject/defer, not a "mitigated" item.
7. **Cross-conversation access:** bound to the same conversation fetch (T2/T6).
8. **Duplicate external ops:** idempotency + "uncertain ⇒ reconcile" (T9/T10/T12).
9. **Unbacked assumptions flagged:** §3 lists six, including the pivotal host-pattern unknown.
10. **Does the proposal quietly weaken existing controls?** No: redirects stay disabled, bearer
    flow unchanged, no security control removed. It *adds* a target, which is the point of the
    review.

**Verdict of the self-review:** the design is **not safe to proceed to implementation** as-is. It
**requires further evidence** (Q1, Q2) and owner approval of the privilege trade-off, or it should
be rejected in favour of Option B/C. This is a self-review; an **independent** security review is
still required before any implementation.

---

# r2 — Reassessment: `OHB2-P0-FILE-UPLOAD-FEASIBILITY-AND-SECURITY-REASSESSMENT`

> **§1–§15 above are preserved.** This section re-verifies the API surface from primary sources
> (official OpenAPI specs + upstream source at HEAD of `main`) rather than relying on §1–§15, and
> resolves the prior gates (G1/Q1) into **verified blockers**. Legend: **[F] verified fact**,
> **[A] design proposal**, **[G] unresolved question**.

## 16) Verified baseline and governance

- **[F] Branch/HEAD:** `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW`, HEAD
  `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c` == `origin/main`, divergence `0 0`.
- **[F] Working tree (preserved untouched):** 4 tracked modifications — `.agent/PROGRESS.md`,
  `README.md`, `bot/app.py`, `bot/handlers.py` (= 101 insertions, from prior tasks) — and 3
  untracked files (`docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md` (this file),
  `docs/proposals/OHB2-TELEGRAM-ACK-ARCHITECTURE-ADR.md`, `tests/test_unsupported_attachment_rejection.py`).
- **[F] No P0 scaffolding exists.** `grep -rn "في انتظار أوامرك" bot/ tests/` → none. There is
  **no** pending-file table, staged-file directory, or 15-minute gate in the code today.
- **[F] `conversation_url` / `session_api_key` are read nowhere in first-party code.** Only
  `sandbox_id` is used (`bot/outbox.py:348-352` → `POST /sandboxes/{id}/resume`).
- **[F] The only first-party HTTP client is `bot/openhands_client.py`** (`httpx.AsyncClient`,
  `Authorization: Bearer`, base `{OPENHANDS_BASE_URL}/api/v1`, `follow_redirects` off, 3xx = error).
  No second client, no arbitrary-URL client.
- **[F] No temp-file facility exists.** `grep -rn "tempfile|mkdtemp|TemporaryDirectory|unlink|os.remove" bot/` → none.
- **[F] `bot/config.py` has no `conversation_url`/host allowlist.** It has
  `MINI_APP_ALLOWED_ORIGINS` (a *web* CORS allowlist, unrelated) and validates `OPENHANDS_BASE_URL`
  (must be `https://` for external hosts). There is no runtime-host allowlist.

## 17) Re-verified API surface (primary sources)

### 17.A OpenHands Cloud V1 API — **[F] no upload path**

- **Spec:** `https://app.all-hands.dev/openapi.json`, `info.version = 1.87.1`, **242 paths**.
- **[F] No upload operation anywhere.** Programmatic check over the raw spec: **0** operations
  mention `upload` or `multipart`; `format: binary` is absent.
- **[F] File routes are read-only:** `GET /api/v1/app-conversations/{conversation_id}/file` and
  `GET /api/v1/app-conversations/{conversation_id}/files`. No `POST`/`PUT`/`PATCH` file route.
- **[F] `send-message` cannot carry a generic file.** `POST /api/v1/app-conversations/{conversation_id}/send-message`
  body `AppSendMessageRequest.content` = `array` of `anyOf: [TextContent, ImageContent]`
  (`minItems: 1`). `ImageContent` = `{type:"image", image_urls: [string]}`. `TextContent` =
  `{type:"text", text}`. **No** `FileContent`/attachment type. The endpoint description says it is
  "intentionally a thin proxy that forwards messages to the agent server".
- **[F] The Cloud exposes the agent-server connection details** on `AppConversation`:
  `conversation_url` ("The URL where the conversation may be accessed", `string|null`),
  `session_api_key` ("The Session Api Key for REST operations.", `string|null`),
  `conversation_ui_url` (browser URL), `sandbox_id` (`string`). Source: Cloud OpenAPI
  `components.schemas.AppConversation` and the doc
  `docs.openhands.dev/openhands/usage/cloud/api-reference/conversations/batch-get-app-conversations.md`.
- **[F] Cloud proxies only *some* runtime calls** (`GET …/git/changes`, `GET …/git/diff` —
  "Proxy ``GET /api/git/…`` on the conversation's runtime"). **There is no file-upload proxy.**
- **[A] `ImageContent.image_urls` accepts a `data:` URL (base64)** — the SDK preserves them
  (`openhands-sdk/openhands/sdk/llm/message.py`: `image_urls: Annotated[list[str], PreserveDataUrls()]`).
  This is an **image-only** channel (data URL), **not** a generic file upload. It is the one
  *documented* Cloud-only path that avoids a second credential, but it only works for images the
  configured LLM can accept and it must be verified against Cloud before any use (see §21 Option C).

### 17.B Agent Server API — **[F] the only upload endpoint**

- **Spec:** `https://docs.openhands.dev/openapi/agent-sdk.json`, `title = "OpenHands Agent Server"`,
  `version = 0.1.0`, **40 paths**.
- **[F] Upload:** `POST /api/file/upload/{path}` (path parameter = "Absolute file path"),
  `multipart/form-data` field `file` (`format: binary`). Response `200` → `Success`
  (`{"success": true}`), and the concrete model is `FileUploadResult(Success)` with
  `file_size: int`. `422` on validation error.
- **[F] No workspace confinement.** Upstream `openhands-agent-server/openhands/agent_server/file_router.py`
  (`_upload_file`): the **only** check is `if not target_path.is_absolute(): raise 400`. There is
  **no** `resolve()` / `is_relative_to(workspace)` confinement. `target_path.parent.mkdir(parents=True,
  exist_ok=True)` is called first, so **any absolute path** the sandbox user can write is accepted
  (e.g. `/etc/cron.d/x`, `/home/*/.bashrc`, `/tmp/…`). The write streams in 8 KB chunks.
- **[F] No server-side size limit** in the agent-server upload handler.
- **[F] Authentication is a single full-privilege key.** Upstream `api.py`: one
  `api_router = APIRouter(prefix="/api", dependencies=[Depends(require_initialized), Depends(check_session_api_key)])`
  mounts `file_router`, `bash_router`, `conversation_router`, `credential_binding_router`,
  `git_router`, `skills_router`, `hooks_router`, `mcp_router`, … `dependencies.py`:
  `check_session_api_key` reads the `X-Session-API-Key` header and only checks membership in
  `config.session_api_keys` (401 otherwise) — **no scope, no per-endpoint authorization**.
  So the same key that uploads a file also reaches `POST /api/bash/execute_bash_command`
  (arbitrary command execution) and `POST /api/conversations/{id}/secrets`.
  Official doc confirms: an unauthenticated agent server "can execute commands and read or write
  files in its configured workspace"; clients "must send the session key in the `X-Session-API-Key`
  header"; the key is a **server-wide** session key.
- **[F] `X-Session-API-Key` cannot be obtained without reading Cloud's `session_api_key`.**
  (Cloud issues it per conversation; the agent server accepts only its configured keys.)

## 18) Authentication and authorization analysis

| Candidate | Auth | Scope | Targets existing conversation? | Preserves repo/conv? | Least privilege? |
| --- | --- | --- | --- | --- | --- |
| Cloud `POST /send-message` | `Bearer OPENHANDS_API_KEY` (already held) | Cloud org/user API | Yes | Yes | Yes (same key the bot already uses) |
| Cloud `GET …/file`, `…/files` | same Bearer | read-only | Yes | Yes | Yes |
| Agent Server `POST /api/file/upload/{path}` | `X-Session-API-Key` (Cloud `session_api_key`) | **entire agent-server `/api/*`** | Yes (per-conversation sandbox) | Yes | **No** — full privilege |

- **[F] `session_api_key` grants far more than this feature needs.** The feature needs *one*
  write of *one* file into *one* conversation's workspace. The key grants **command execution** and
  **secret management** in that sandbox. There is **no** upload-scoped credential. This is the
  **B1 blocker** (§22).
- **[A] Binding upload to the authenticated user's conversation is *doable*** (fetch the
  conversation object for the *stored* `conversation_id` the user is acting on, use *that*
  object's `conversation_url`+`session_api_key` together, never cache across conversations). So the
  *binding* problem is solvable; the *privilege* and *origin* problems are not.

## 19) SSRF and `conversation_url` trust boundary

- **[F] The upload target is fully attacker-influenced in the worst case.** `conversation_url`
  comes from Cloud, but if Cloud (or anything upstream of it) returns an unexpected value, the bot
  would send `X-Session-API-Key` to that host. A key sent to an attacker-controlled host = command
  execution in the owner's sandbox for that attacker.
- **[F] There is no trusted-origin anchor available.** The only anchor the bot has is the fixed
  `OPENHANDS_BASE_URL` (`https://app.all-hands.dev`) for the **Cloud** API. The **agent-server**
  origin is *infrastructure-dependent*: upstream `live_status_app_conversation_service.py`
  builds `conversation_url` from the sandbox `exposed_urls` `AGENT_SERVER` entry, which derives
  from the runtime API's `runtime['url']` (`remote_sandbox_service.py`, `_build_service_url`,
  path-mode vs subdomain-mode). No official doc states the concrete host/pattern.
- **Required SSRF controls (all technically enforceable, but insufficient without a trusted origin):**
  N1 scheme `https` only; N3 reject userinfo/odd ports; N4 resolve DNS and reject
  private/loopback/link-local/ULA/CGNAT/multicast, pin the resolved IP for the connection;
  N5 `follow_redirects=False` and treat 3xx as failure; N6 require the expected path prefix;
  N7 guard DNS-rebinding by validating the *connected* IP; N8 TLS verification on.
- **[G] Even all of N1–N8 do not make the target trusted.** "Any `https` host + private-IP block"
  is exactly the **weak hostname check the task forbids**. A *strong* control needs an explicit
  **allowlist of the actual agent-server origins** (N2). That allowlist does not exist in evidence
  and cannot be derived from the repo. This is the **B2 blocker** (§22).
- **[F] Positive note:** the project already never follows redirects and never disables TLS, so the
  *existing* controls would not be weakened — but they are not sufficient for a new target.

## 20) File-security findings (upload lifecycle)

| Item | Finding | Enforceable? |
| --- | --- | --- |
| Server path confinement | **None** (only `is_absolute()`) | Bot-side only |
| Path traversal | Bot must generate the destination path internally; never accept a client path | Yes (bot-side) |
| Size cap | Server has **none**; bot must cap (proposal 20 MB) | Yes (bot-side) |
| Type/spoofing | Magic-byte sniff + declared-type cross-check | Yes (bot-side) |
| Filename | Never trust the Telegram filename; use `{batch}/{index}-{sha256[:16]}.{safe_ext}` | Yes (bot-side) |
| Temp storage | No facility exists today; must be created (restrictive perms, TTL sweep) | Yes (new code) |
| Logs/secrets | `session_api_key` must never enter logs/`ApiError`/Mini App payloads | Yes (redaction + suppress httpx URL logs for the new host) |
| Ambiguous result | Never blind-retry; never delete on uncertainty | Yes (state machine) |

- **[F] `bot/files.py:15` documents the current stance** ("مفيش رفع ملفات … ومفيش عميل تاني ولا
  worker ولا جدول جديد") and the *read* path already had to add a local allowlist because the
  OpenHands read endpoint is unconfined. The **write** endpoint is equally unconfined.

## 21) Implementation options compared

| Criterion | **A** Cloud-supported upload | **B** Agent Server upload (trusted origin + scoped auth) | **C** Other supported existing-conversation mechanism | **D** No safe implementation |
| --- | --- | --- | --- | --- |
| Feasibility | **Not available** — Cloud V1 has no upload route (§17.A) | Technically works, but **blocked** (B1+B2) | **Partial only:** `ImageContent` data-URL, **images only**, Cloud-only; needs Cloud verification; not a generic file | **Available today** |
| Security risk | N/A | **HIGH** — full-privilege key (command exec) + unconfined path + SSRF origin gap | **MEDIUM** (no new credential; data URLs stay inside the existing Bearer boundary) — but not a file upload | **None added** |
| Auth required | — | Cloud `session_api_key` (full privilege) | Existing `Bearer OPENHANDS_API_KEY` | — |
| Architecture fit | N/A | Breaks "one client / no second auth scheme" | Fits (same client), **but** image-only and unverified | Fits perfectly |
| Code/schema changes | — | Upload client, origin allowlist, temp store, state machine, cleanup, reconciliation, new table | Small (extend `send-message` content), **image-only**; schema for the pending batch still needed | None |
| Failure/recovery | — | Complex (uncertain states, orphan files) | Same pending-batch machinery needed | N/A |
| Meets **all** P0 criteria | No | No (blocked) | **No** (image-only ⇒ cannot carry arbitrary files) | Yes, by rejecting files |

**Option C in detail (the one thing worth a follow-up):** `POST /send-message` *can* carry
`ImageContent.image_urls`, and the SDK preserves `data:` (base64) URLs. If Cloud's `send-message`
forwards data URLs unchanged to the agent server, the bot could deliver **images** to the existing
conversation **using only the credential it already holds** — no second host, no `session_api_key`,
no SSRF surface. **But** this is **(a)** image-only (not the general "attached files" the P0
requires), **(b)** **[G] unverified against Cloud** (the OpenAPI says `image_urls: [string]` but
does not document `data:` acceptance, and the Cloud path may reject or re-fetch non-http URLs), and
**(c)** dependent on the configured LLM having vision. It is therefore **not** a solution to P0 as
stated; it is at most a future, narrower feature.

## 22) Verdict and blockers

**Verdict: `P0 BLOCKED BY SECURITY OR API LIMITATION`.**

**B1 — No least-privilege upload credential. [F]** The only upload endpoint
(`POST /api/file/upload/{path}`) is guarded by the **same** `X-Session-API-Key` that also allows
arbitrary command execution and secret management in the sandbox. The feature needs a file write;
it would have to hold a **command-execution-capable** credential. No scoped/upload-only credential
exists or is documented.

**B2 — No trusted origin for `conversation_url`. [F]+[G]** A strong SSRF defense requires an
allowlist of the concrete agent-server origins. That allowlist is not documented and cannot be
derived from the repo or public docs; the origin is infrastructure-dependent. Per the task, a weak
hostname check must **not** be shipped — so the design is **blocked**, not "mitigated".

**Secondary blockers (independent of B1/B2):**
- **[F] The server imposes no path confinement and no size limit** — the bot would be the *only*
  guard; any bot bug becomes an arbitrary-write.
- **[G] No "list uploads"/verification endpoint** — an upload that succeeds at the server but whose
  response is lost cannot be confirmed, so "unknown result ⇒ no blind retry, no premature delete"
  is correct but leaves a permanent `uncertain` state with no reconciliation path.

**Minimum approvals that *would* be required to unblock (not granted, not made):**
1. Product approval to **not** ship file upload (Option D) — the safe default — **or**
2. A decision that the **full-privilege credential (B1) is acceptable**, plus
3. A **provider-committed, stable agent-server origin allowlist (B2)**, plus
4. A **new architectural approval** for a second external target + second auth scheme (departs from
   `bot/files.py:15` and `docs/plan-openhandBot-2.md` §4.1), plus
5. A **new schema** for the pending batch (a new table — also a §4.1 departure).

**None of these approvals is granted here. No architectural change is made.**

## 23) Architecture-constraint compliance (of the *proposed* design, for the record)

The *proposed* (unapproved) design keeps: one process; one SQLite owner; existing workers
(`OutboxWorker`/`CreationWorker`/`CompletionWorker`/`Watcher`/`Notifier`) and their scheduling only;
existing storage only; no second DB; no independent worker/scheduler; **no** automatic conversation
creation; **no** automatic retry on an ambiguous external result. **However**, it *would* require a
**second external target + second auth scheme** and a **new table**, which are themselves
architecture changes needing approval (§22). So the design **cannot** be implemented "within the
existing approved architecture" as-is.

## 24) P0 acceptance-criteria feasibility (per criterion)

| # | P0 requirement | Feasible under A/B/C? | Why |
| --- | --- | --- | --- |
| 1 | File in an existing conversation becomes temporarily pending | Yes (local) | Local state only |
| 2 | Bot replies «في انتظار أوامرك» | Yes (local) | Telegram only |
| 3 | 15-min deadline from first file | Yes (local) | Persisted T0 |
| 4 | Text within deadline sends files+text to the **same** conversation | **No** | Needs the upload path (B1/B2) |
| 5 | No new conversation created | Yes | Design never creates one |
| 6 | Repository association unchanged | Yes | No `PATCH`/create |
| 7 | Multiple files accumulate without extending the deadline | Yes (local) | T0 fixed |
| 8 | Non-text does not trigger submission | Yes (local) | Filter |
| 9 | Expired files are not sent | Yes (local) | TTL |
| 10 | Restart preserves pending state + original deadline | Yes (local) | Persisted |
| 11 | Temp files deleted after confirmed success or safe expiry/cancel | Partly | "Confirmed success" needs the upload path |
| 12 | Unknown upload result ⇒ no blind retry, no premature delete | Yes (local) | State machine |
| 13 | Ownership, storage isolation, cleanup enforced | Yes (local) | Bot-side |

**Conclusion:** every *local* criterion is satisfiable, but the **core** criterion (#4, sending the
files) is **not** satisfiable safely. So P0 as a whole **cannot** be met now.

## 25) Revision history (this proposal)

| Rev | Date | Change | Source |
| --- | --- | --- | --- |
| r1 | 2026-11-11 | Original design + threat model (§1–§15) | `OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE-AND-SECURITY-DESIGN` |
| **r2** | 2026-11-11 | **Added §16–§25**: re-verified API surface (Cloud 1.87.1 = no upload; Agent Server 0.1.0 upload + full-privilege auth + no path confinement), SSRF/trusted-origin analysis, file-security findings, options comparison, verdict `BLOCKED`, blocker list, P0-criteria feasibility. **§1–§15 preserved.** Status `NEEDS_EVIDENCE` → `BLOCKED_BY_SECURITY_OR_API_LIMITATION`. | `OHB2-P0-FILE-UPLOAD-FEASIBILITY-AND-SECURITY-REASSESSMENT` |

**Explicit statements (r2):** `P0_IMPLEMENTATION_AUTHORIZED = NO`;
`OTHER_PLAN_PHASES_AUTHORIZED = NO`; `COMMIT_PUSH = NONE`. **No implementation, no schema change,
no dependency/config change, no runtime change.** Self-review only; **no independent review** was
performed.

---

## 26) r3 — P0 decision gate re-validation (`OHB2-PLAN-01-FULL-READ-IMPLEMENT-REVIEW-AND-REPAIR`)

**Purpose.** Re-run the P0 feasibility check against the *current* repo + *live* API specs before any
implementation, per the plan's mandatory order (P0 first). **No runtime code was changed.**

### 26.1 Re-verified evidence (2026-11-11, this session)

| # | Check | Result |
| --- | --- | --- |
| R1 | Cloud V1 `openapi.json` | v**1.87.1**, 242 paths; `multipart`=**absent**, `format: binary`=**absent**; **0** ops mention `upload`; file routes read-only (`GET …/file`, `GET …/files`) |
| R2 | Cloud `send-message` body | `content` = `anyOf[TextContent, ImageContent]` only — **no generic file/attachment block** |
| R3 | Cloud "import/download/fetch" scan | Only `GET …/download` (= **export trajectory zip**, read) and secret-lookup/admin routes — **no file-into-workspace upload** |
| R4 | Cloud proxy routes | Only `GET …/git/changes`, `GET …/git/diff` are proxied to the runtime — **no upload proxy** |
| R5 | Agent Server `agent-sdk.json` | v**0.1.0**, 40 paths; the **only** upload = `POST /api/file/upload/{path}` (multipart `file`); `securitySchemes` empty (auth is a code-level dependency) |
| R6 | Agent Server `file_router.py::_upload_file` | only `Path(path).is_absolute()`; `parent.mkdir(parents=True)` first ⇒ **no workspace confinement**; no size limit |
| R7 | Agent Server `dependencies.py::check_session_api_key` + `api.py` | one `APIRouter(prefix="/api", dependencies=[require_initialized, check_session_api_key])` mounts file+bash+conversation+secrets+git ⇒ **one full-privilege key, no scope** |
| R8 | `conversation_url` origin | built from runtime `exposed_urls` (`AGENT_SERVER`) whose url = `runtime['url']`; `_build_service_url` shows **path-mode** (`…/{runtime_id}/…`) vs **subdomain-mode** (`…/{service}-{netloc}…`) ⇒ host **not stable/documented** |
| R9 | Repo code | **no** `conversation_url`/`session_api_key`/upload/staging/tempfile usage in first-party code; `bot/files.py:15` + `docs/plan-openhandBot-2.md` §4.1 still assert no-upload / single-owner |
| R10 | `ImageContent` data-URL path | SDK preserves `data:` URLs, but it is **image-only**, **unverified against Cloud**, and vision-dependent ⇒ **not** general file support |

### 26.2 Safe-alternative search result

**No safe alternative exists** that satisfies *every* original P0 requirement:
- **A (Cloud upload):** impossible — no endpoint (R1–R4).
- **B (Agent Server upload):** technically works but violates the security requirements (R6/R7) and
  has no trusted origin (R8).
- **C (image data-URL):** image-only ⇒ does **not** meet "attached files" (R10).
- **D (reject):** safe but is **not** the requested feature, and is **not** adopted here.

### 26.3 Decision

**`P0 BLOCKED`** — unchanged. The minimum decision required from the user is **exactly one** of:
1. **Approve abandoning/weakening** the P0 file-upload requirement (adopt a narrower or no-upload
   behavior) — a product decision, **not** made here; **or**
2. **Approve the full-privilege Agent Server credential (B1) AND supply/approve a stable, trusted
   agent-server origin allowlist (B2) AND approve the second-integration + new-table architecture
   change.**

**Nothing in this file authorizes implementation.** `P0_IMPLEMENTATION_AUTHORIZED = NO`;
`OTHER_PLAN_PHASES_AUTHORIZED = NO` (the plan's order forbids later stages while P0 is open);
`COMMIT_PUSH = NONE`. **No runtime change. No schema change. Self-review only.**

**Revision r3 added by:** `OHB2-PLAN-01-FULL-READ-IMPLEMENT-REVIEW-AND-REPAIR`.

### 26.4 Decision record — Option D approval (`OHB2-PLAN-01-APPROVE-DEFERRED-P0-AND-CONTINUE-STAGES-0-5`)

- **Date:** 2026-11-11. **Authorizing actor:** the repository owner (explicit user approval).
- **Decision:** **Option D** — *temporarily defer* the general file-attachment delivery feature.
  The user additionally granted permission to continue **Stages 0–5** of
  `OHB2-PLAN-01-TELEGRAM-ACK-AND-DELIVERY-RELIABILITY` in their original order, and required that
  the **safe rejection of unsupported attachments** be preserved.
- **Effect on the P0-first order:** the original P0-first execution order is **exceptionally
  changed by this explicit product decision only**. Nothing else about the plan changes.
- **P0 status (authoritative):** `BLOCKED / DEFERRED BY EXPLICIT PRODUCT DECISION`.
  P0 is **NOT** DONE / PASS / IMPLEMENTED / CLOSED.
- **P0 requirements preservation:** the complete original P0 requirements in §16–§25 above are
  **preserved unchanged**; this decision record does **not** delete, weaken, or redefine any of
  them. The technical blockers B1/B2 (§22) remain valid for future work.
- **Not approved by this decision:** the ack architecture (Option A), any schema change, and the
  open product decisions in the ACK ADR §28. Those still require separate approval.
- **Reopen conditions:** P0 may be reopened only per §26.3 (product decision to un-defer, **or** a
  scoped upload credential + a stable trusted origin allowlist + architecture approval).

---

## 27) r5 — P0 reopen decision gate re-validation (`OHB2-P0-ATTACHMENT-WORKFLOW-REOPEN-AND-SECURE-COMPLETION`)

**Purpose.** The owner **explicitly reopened P0** and authorized renewed investigation and
implementation of the attachment workflow. This section re-runs the mandatory feasibility gate
against the **current** public API surface. **No runtime code, schema, dependency, or config was
changed.** §1–§26 preserved.

### 27.1 Re-verified evidence (2026-11-12, this session — public sources only, no credential, no production call)

| # | Check | Result |
| --- | --- | --- |
| V1 | Cloud V1 `https://app.all-hands.dev/openapi.json` | `info.version = **1.87.1**`, **242** paths; tokens `"upload"`=**0**, `multipart`=**0**, `format: binary`=**0** |
| V2 | Cloud file routes | only `GET /api/v1/app-conversations/{conversation_id}/file` and `.../files` — **read-only**; no POST/PUT/PATCH file route |
| V3 | Cloud `POST .../send-message` body | `AppSendMessageRequest.content` = array `anyOf[TextContent, ImageContent]` (`minItems: 1`) — **no generic file/attachment content type** |
| V4 | Cloud write routes mentioning file/media/attach | **none** (scan of all POST/PUT/PATCH paths) |
| V5 | Cloud exposes agent-server details on `AppConversation` | `conversation_url` (`string|null`, "URL where the conversation may be accessed"), `session_api_key` (`string|null`, "Session Api Key for REST operations."), `sandbox_id` |
| V6 | Agent Server `https://docs.openhands.dev/openapi/agent-sdk.json` | `version = **0.1.0**`, **40** paths; the **only** upload = `POST /api/file/upload/{path}` (multipart `file`, `format: binary`); `securitySchemes = {}` (auth is a code-level dependency) |
| V7 | Agent Server source `openhands-agent-server/.../file_router.py::_upload_file` (main) | only `if not target_path.is_absolute(): raise 400`; `target_path.parent.mkdir(parents=True, exist_ok=True)` **before** writing ⇒ **no workspace confinement**; no server-side size limit |
| V8 | Agent Server source `.../api.py` + `.../dependencies.py` (main) | **one** `APIRouter(prefix="/api", dependencies=[require_initialized, check_session_api_key])` mounts `bash_router` (`POST /api/bash/execute_bash_command`), `conversation_router`, `credential_binding_router`, `file_router`, … ; `check_session_api_key` = header `X-Session-API-Key` membership only — **no scope, no per-endpoint authz** |
| V9 | Agent Server doc `docs.openhands.dev/sdk/arch/agent-server.md` | the key is a **server-wide** session key; an unauthenticated/held-key server "can execute commands and read or write files in its configured workspace"; clients "must send the session key in the `X-Session-API-Key` header" |
| V10 | Repo first-party code | **no** `upload`/`multipart`/`session_api_key`/`conversation_url`/staging usage anywhere in `bot/`, `automation/`, `main.py` |

### 27.2 Decision

**Verdict: `P0 BLOCKED — SECURE OPENHANDS UPLOAD CAPABILITY NOT ESTABLISHED`.** Unchanged from r2/r3;
the reopening authorizes implementation **only if** a secure, supported upload path exists, and none
does. The decisive blockers are re-verified, not assumed:

- **B1 — no least-privilege upload credential. [F]** (V6–V9) The only upload endpoint is guarded by
  the **same** `X-Session-API-Key` that also allows arbitrary command execution and secret
  management. The feature needs one file write; it would have to hold a **command-execution-capable**
  credential. No scoped/upload-only credential exists.
- **B2 — no trusted origin for `conversation_url`. [F]+[G]** (V5, §19) A strong SSRF defense needs an
  allowlist of the concrete agent-server origins; that origin is infrastructure-dependent and not
  documented. "Any https host + private-IP block" is the weak check the task **forbids**.
- **Secondary [F]:** the server imposes **no** path confinement and **no** size limit (V7) ⇒ the bot
  would be the only guard; and there is no "verify upload" endpoint ⇒ a lost response leaves a
  permanent `uncertain` state with no reconciliation path.

**No secure supported mechanism exists ⇒ implementation MUST NOT proceed.** The only remaining
in-scope path is Option D (reject attachments), which the bot **already** implements safely
(`handlers.handle_unsupported_attachment`; `tests/test_unsupported_attachment_rejection.py`).
Attachment handling stays **fail-closed**. **P0 is NOT DONE / PASS / IMPLEMENTED / CLOSED.**

### 27.3 Exact evidence needed to unblock (all required, none granted)

1. **Product approval** that the **full-privilege, command-execution-capable** agent-server
   credential is acceptable for a file-write feature (**or** an upstream **upload-scoped credential**
   with a documented scope), **and**
2. A **provider-committed, stable agent-server origin allowlist** (documented host pattern for
   `conversation_url`), **and**
3. **Architecture approval** for a second external target + second auth scheme + a new pending-batch
   table (departures from `bot/files.py:15` and `docs/plan-openhandBot-2.md` §4.1), **and**
4. A documented **reconciliation path** for an ambiguous upload outcome (or an explicit product
   acceptance of a permanent `uncertain` state).

**Explicit statements (r5):** `P0_IMPLEMENTATION_AUTHORIZED = NO` (blocked by B1/B2);
`OTHER_PLAN_PHASES_AUTHORIZED = NO`; `COMMIT_PUSH = NONE`. **No runtime change. No schema change.
Self-review only; no independent review performed.**

---

## 28) r6 — Plan 02 Reconciled Design & Readiness Addendum (`OHB2-PLAN-12-P0-REMOTE-ATTACHMENT-UPLOAD`, 2026-11-15)

**Preservation note:** Sections `§1–§27` above remain intact. This addendum records the reconciled
architecture, security, integrity, verification, and outbox-reconciliation design produced under
`OHB2-PLAN01-REMAINING-AND-PLAN02-REMOTE-ATTACHMENT-DELIVERY` **without** modifying database
tables/columns/lifecycle states, **without** adding workers/schedulers/SQLite owners, and
**without** implementing remote attachment upload while `B1/B2` and owner decisions remain open.

### 28.1 Authoritative Identity & Provenance Mapping (Phase C1)

| Layer / Field | Authoritative Source | Mutability & Scope | Trust & Verification Rule |
| --- | --- | --- | --- |
| `telegram_id`, `chat_id`, `message_id` | Telegram `Update` / `attachment_message_identity` (`bot/db.py:804`) | Immutable canonical message identity (`D-33/D-35`); `ON DELETE RESTRICT` | Never conflate `update_id` (delivery seq) with `message_id` |
| `conversation_id` | `db.awaiting_state` (`kind="route"`) + `attachment_batches.conversation_id` | Bound at batch creation (`A2`), re-validated at `A3` (`D-26`) and dispatch (`D-17`) | Strict `^[A-Za-z0-9_-]{1,64}$`; fail-closed if `db.is_deleted(cid)` |
| `created_by_user_id` vs `/users/me.id` | Cloud V1 `GET /api/v1/app-conversations` + `IdentityCache` (`bot/files.py`) | Owner-scoped (`ALLOWED_TELEGRAM_ID` single-user policy) | Fail-closed (`UNAUTHORIZED`) if missing or mismatched |
| `batch_id`, `item_id` | `secrets.token_hex(16)` (`bot/attachments.py:351-358`) | Immutable opaque IDs generated locally on `A2` accept | Primary keys for `attachment_batches` / `attachment_items` |
| `staging_token` | `secrets.token_hex(16)` (`bot/attachments.py`) | Immutable opaque 32-hex filename inside `0700` staging root | Never derived from `display_name`; `O_NOFOLLOW` + `lstat`/`fstat` |
| `display_name` | Sanitized metadata (`bot/attachments.py`) | Display-only; sanitized (`[A-Za-z0-9._-]`) for final leaf | **Never** trusted as path or component alone |
| `client_operation_id` (Design) | Deterministic hash/key of `(batch_id, item_id, staging_token)` | Stable across retries & process restarts (`D-21`) | Required for idempotent remote reconciliation (`D-16`) |
| `sandbox_id`, `conversation_url`, `workspace_root` | Cloud V1 `AppConversation` runtime metadata | Ephemeral/provider-controlled per sandbox lifecycle | Requires grouping/isolation check (`D-06`) + origin allowlist (`B2`) |
| `remote_relpath` (Design) | Server-derived under verified `workspace_root`: `.openhandbot_attachments/<batch_id>/<item_id>_<safe_name>` | Fixed once assigned to item; single-use per batch (`D-13`) | Must satisfy `PurePosixPath` normalization + confinement (`D-05`) |

### 28.2 Verified Upstream API Boundaries (Phase C2)

- **Cloud V1 (`https://app.all-hands.dev/openapi.json` v1.92.0, 257 paths):**
  - **Upload:** **NONE** (`0` upload/multipart/binary write routes).
  - **File read/list:** `GET /api/v1/app-conversations/{id}/file` (currently bounded to 256 KiB in `OpenHandsClient.read_file_text_bounded`), `GET /api/v1/app-conversations/{id}/files`, `GET /api/v1/app-conversations/{id}/download` (trajectory export zip).
  - **Message dispatch:** `POST /api/v1/app-conversations/{id}/send-message` accepts `TextContent | ImageContent` only. `ImageContent.image_urls` on Cloud V1 for `data:` URLs is **UNVERIFIED** and image-only (cannot carry PDFs/docs/archives/code).
  - **Conversation metadata:** `AppConversation` returns `conversation_url`, `session_api_key` (ephemeral/full-privilege runtime credential), `sandbox_id`, and `repositories[].path` (`readOnly: true`, from `archiveworkspacepath`).
- **Agent Server (`agent-sdk.json` v0.1.0, 40 paths):**
  - **Only upload endpoint:** `POST /api/file/upload/{path}` (`multipart/form-data`, `file`, `format: binary`).
  - **Verified security gaps in `software-agent-sdk`:**
    1. **Blocker B1 (`D-10/D-11`):** `dependencies.py::check_session_api_key` protects `/api/*` uniformly with a single `X-Session-API-Key` granting bash execution (`POST /api/bash/execute_bash_command`) and secrets management (`POST /api/conversations/{id}/secrets`).
    2. **No path confinement (`D-05/D-06`):** `file_router.py::_upload_file` checks only `target_path.is_absolute()` and executes `target_path.parent.mkdir(parents=True, exist_ok=True)` before writing; no workspace confinement and no size limit.
    3. **No verification/idempotency (`D-02/D-16`):** Returns only `Success{success}` (or `file_size` in some SDK variants) — no SHA-256, no `stat`, no idempotency key.
  - **Blocker B2 (`D-14`):** `conversation_url` origin varies across path-mode and subdomain-mode (`remote_sandbox_service.py`) without a provider-committed allowlist.

### 28.3 SSRF, Origin Allowlist, TLS, IP Pinning & Credential Isolation Design (Phase D)

Until **B1** and **B2** are resolved (either via a Cloud V1 delegated upload proxy or explicit owner approval + committed origin pattern), no upload HTTP client may connect to `conversation_url`. If an Agent Server upload path is later authorized under `D-10/D-11/D-14`, the following controls are mandatory:
1. **Strict Origin Allowlist (No arbitrary HTTPS):** Parse `conversation_url` (`urlsplit`), require `scheme == "https"`, reject `userinfo`, query, fragment, and non-standard ports, and enforce exact match against an owner/provider-configured `AGENT_SERVER_ALLOWED_ORIGINS` (exact `host` or strict anchored subdomain pattern, never wildcard `*`).
2. **DNS Resolution & IP Pinning (Anti-Rebinding):** Resolve host via `socket.getaddrinfo` once per request/connection, reject **all** non-global IPs (`is_private`, `is_loopback`, `is_link_local`, `is_multicast`, `is_reserved`, `is_unspecified`, IPv4-mapped IPv6), and connect directly to the validated IP while preserving TLS SNI + certificate hostname verification (`ssl` context / pinned transport).
3. **No Redirects & No Proxy Leakage:** `follow_redirects=False`; any `3xx` response fails closed (`StagingError` / retry-safe pre-upload abort). Strip all Cloud Bearer tokens when talking to Agent Server origins, and never send `X-Session-API-Key` to Cloud V1 or any unpinned host.
4. **Volatile Secret Handling (`X-Session-API-Key`):** Fetch `session_api_key` only in memory at dispatch time from `GET /api/v1/app-conversations`; **never** persist `session_api_key` in SQLite (`attachment_batches`, `outbox`, `settings`), logs, exceptions, or Mini App responses; redact headers unconditionally.

### 28.4 Workspace Proof, Path Confinement, Local Source Integrity & Honest Remote Verification (Phase E)

1. **Workspace Identity Proof (`D-06`):** Before generating a destination path, re-verify conversation ownership (`created_by_user_id == owner_uuid`), verify `not db.is_deleted(conversation_id)`, verify sandbox state is live/compatible, obtain authoritative `workspace_root` from `AppConversation`, and reject shared/ambiguous `grouped_workspace_dir` layouts unless unambiguous conversation isolation is proven.
2. **Deterministic Safe Remote Path (`D-05`):**
   - Never pass user-supplied `display_name` as a path.
   - Normalize leaf (`[A-Za-z0-9._-]`, bounded length, no `.`/`..`/control chars/NUL/backslash, fallback `attachment`).
   - Construct relative path `.openhandbot_attachments/<batch_id>/<item_id>_<safe_leaf>` and validate via `PurePosixPath` + `bot/files.py:is_safe_workspace_path`; join only to verified `workspace_root` after confirming `PurePosixPath(full_path).is_relative_to(workspace_root)`.
3. **Local Source Integrity Guard (TOCTOU & Corruption Prevention):**
   - Open staged file with `os.O_RDONLY | os.O_NOFOLLOW` inside verified `0700` staging root.
   - Verify `os.fstat(fd)`: `S_ISREG`, `0 < st_size <= MAX_ATTACHMENT_BYTES`, and `st_size == item.size_bytes`.
   - Record `(st_dev, st_ino, st_size)` and compute `SHA-256` prior to upload; stream chunks from `fd` while recomputing `SHA-256` on the exact uploaded byte stream; fail closed (`INTEGRITY_MISMATCH`) if bytes read != `st_size` or digest differs.
4. **Honest Remote Verification Taxonomy (`D-02/D-03/D-04`):**
   - **HTTP 2xx / `Success` response alone:** Classified strictly as **`TRANSPORT_ACCEPTED_UNVERIFIED`** — **NEVER** transitions batch to `delivered`.
   - **`REMOTELY_VERIFIED` (required for `delivered`):** Requires independent confirmation over an authenticated read channel: (a) path presence in `GET /api/v1/app-conversations/{id}/files`, AND (b) full-content re-read via `GET /api/v1/app-conversations/{id}/file` (or future upstream `stat+sha256` endpoint) proving exact byte length and `SHA-256` match against the local staged file. Note: current `OpenHandsClient.read_file_text_bounded` enforces `256 KiB` and rejects binary/non-UTF-8 (`bot/files.py`), so full binary re-read verification up to `3 MiB` requires an explicit binary-safe verification helper (pending `D-02/D-03/D-12`).
   - **User-Facing Truthfulness:** Only state "تم تسليم المرفق والتحقق منه في مساحة العمل" after **`REMOTELY_VERIFIED`** + prompt dispatch completion; otherwise report `uncertain` / `failed` honestly.

### 28.5 Durable Outbox-Compatible Reconciliation & Schema Impact Analysis (Phase F)

- **Single Ownership Invariant (`I2/I3`):** Remote attachment delivery MUST run inside the existing `OutboxWorker` loop (`bot/outbox.py`) on the single `Database` SQLite owner. No new worker, scheduler, background daemon, or second DB is permitted.
- **Bounded Pre-Upload Retries vs Ambiguous Post-Upload:**
  - Failures **strictly before** sending upload request bytes (auth check failed, sandbox starting, DNS/allowlist/pre-connect failure, `429`/`5xx` before body upload if confirmed unstarted) use bounded `attempts < MAX_OUTBOX_ATTEMPTS` backoff.
  - Once upload HTTP write begins and ends ambiguously (timeout, EOF, `5xx`, process crash while `dispatching`), **NO blind re-POST** (`I11`): transition/hold in **`uncertain`** (`dispatching` -> `uncertain` on startup recovery) and execute **read-only reconciliation** first (`GET .../files` + `GET .../file` SHA-256 check).
    - If remote file exists with **exact matching `SHA-256` & `size_bytes`**: mark item verified without re-uploading!
    - If remote file exists with **mismatching hash/size** (partial/corrupted): fail closed (`failed` / `uncertain` — never silently overwrite or claim `delivered` unless owner-approved idempotent replace contract `D-16` exists).
    - If remote file is **absent** and upload window (`expires_at` = `T0 + 15m` or bounded op TTL per `D-15`) has **not** expired and local staged file passes `fstat`+`SHA-256`: bounded retry to the **exact same deterministic `remote_relpath`** (`client_operation_id`).
    - Once **all** batch items are verified remotely, dispatch the accompanying `intent_text` via existing `at-most-once` `send-message` outbox CAS (`pending -> claimed -> sending -> sent/unknown`).
- **Schema Gap Evaluation (Design Only — NO DB Changes Applied Today):**
  Existing `attachment_batches` (`batch_id, telegram_id, conversation_id, t0, status, created_at, updated_at, intent_text`) and `attachment_items` (`item_id, batch_id, staging_token, display_name, size_bytes, status, created_at, updated_at`) are **insufficient** for crash-safe remote upload reconciliation without a future owner-approved migration adding:
  - On `attachment_items`: `sha256 TEXT`, `source_dev INTEGER`, `source_ino INTEGER`, `remote_relpath TEXT`, `remote_status TEXT` (`staged|uploading|uploaded_unverified|verified|failed|reaped`), `remote_op_id TEXT`, `remote_attempts INTEGER DEFAULT 0`, `remote_error TEXT`, `remote_verified_at TEXT`.
  - On `attachment_batches`: `outbox_id INTEGER` (or `dispatch_op_id TEXT`, `dispatch_attempts INTEGER DEFAULT 0`, `last_error TEXT`, `dispatched_at TEXT`) to coordinate batch delivery + accompanying `intent_text` under `OutboxWorker` without double-sending.
  - Under the current task constraints, **none** of these schema additions are applied.

### 28.6 Final Closure Blocker Taxonomy & Scope Status (`OHB2-FINAL-CLOSURE-PLAN01-PLAN02`)

- **Implementability verdict:** **`ZERO_REMOTE_UPLOAD_ITEMS_IMPLEMENTABLE_UNDER_CURRENT_PROVIDER_CONTRACT_AND_OWNER_APPROVALS`**. Neither a remote upload HTTP client nor a DB schema migration nor an `OutboxWorker` upload adapter can be implemented safely without inventing unapproved provider trust rules or silently overriding unresolved owner decisions.
- **`D-12` Two-Scope Reconciliation:**
  - *Scope 1 (Plan 01 local resource guard):* `MAX_ATTACHMENT_BYTES = 3 MiB` stays active as a local memory/resource safety bound under the temporary Option A baseline, while batch/total quotas remain disabled (`None` default, zero config toggles).
  - *Scope 2 (Plan 02 / permanent product quota policy):* `### D-12` remains **`UNRESOLVED`** (`غير محسوم`) until explicit owner approval defines permanent limits for remote delivery.
- **Four-Way Blocker Separation:**
  1. **`BLOCKED_BY_PROVIDER`:** Missing Cloud V1 upload endpoint (`1.92.0`), full-privilege `X-Session-API-Key` protecting Agent Server `POST /api/file/upload/{path}` (`B1`), absent provider-committed `conversation_url` origin allowlist (`B2`), absent `stat + sha256` & server-side workspace confinement, unverified/image-only `ImageContent`, shared `grouped_workspace_dir` risk, and missing `runtime-api` C2 teardown guarantee.
  2. **`BLOCKED_BY_OWNER_DECISION`:** All 22 open decisions (`D-01..D-08`, `D-10..D-14`, `D-16..D-18`, `D-20..D-24`, plus **`attachment_items` / `attachment_batches` schema additions** classified cleanly as awaiting owner approval rather than architecturally forbidden).
  3. **`BLOCKED_BY_ARCHITECTURE`:** Second SQLite owner (`I3`), second worker/scheduler/process (`I2`), blind re-POST after ambiguous failure (`I11`), cross-conversation fallback (`I1`), upload delivery without accompanying prompt (`I7/I8`), or claiming `exactly-once`.
  4. **`BLOCKED_BY_RELEASE_GATE`:** **`D-19`** (mandatory independent adversarial security review prior to any Plan 02 enablement/release).

### 28.7 Final Decision Tally & Investigation Closure Addendum (`OHB2-FINAL-EXECUTION-AND-CLOSURE-PLAN01-PLAN02`)

- **Official Plan 02 Status:** **`PLAN02_INVESTIGATION_AND_DESIGN_CLOSED_REMOTE_DELIVERY_BLOCKED`**.
- **Reconciled Register Tally (`35` total records `D-01..D-35`):**
  - **`13` `OWNER-APPROVED`** (`D-09` [`D-09-R1` + narrow local `D-09-R2`], `D-15` [Option A in MT-2 scope], and `D-25..D-35` local A3/identity/retention policy decisions + `D-34/J`).
  - **`21` unresolved non-gate owner decisions (`UNRESOLVED`)**: `D-01..D-08`, `D-10..D-14`, `D-16..D-18` (`D-18` outside P0), `D-20..D-24` (with `D-12` Plan 01 Option A local resource-guard `None` quota defaults preserved separately from Plan 02's unresolved permanent product-policy scope).
  - **`1` unresolved governance/release-gate decision (`BLOCKED_BY_RELEASE_GATE`)**: **`D-19`**.
  - **Total:** `13 + 21 + 1 = 35` (`22` unresolved total records in the register = `21` non-gate + `1` `D-19`).
- **Authorized Schema/Runtime Boundary:** Zero remote upload implementation, zero `bot/db.py` schema edits, zero new workers/schedulers/SQLite owners, `MINI_APP_ENABLED=False`, Autopush inactive. See `docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md §13.5` for the owner decision package (`RECOMMENDATION — NOT OWNER-APPROVED`).

