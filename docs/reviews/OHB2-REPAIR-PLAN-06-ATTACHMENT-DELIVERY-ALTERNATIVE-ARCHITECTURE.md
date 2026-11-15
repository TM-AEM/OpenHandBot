# OHB2-REPAIR-PLAN-06 — Attachment Delivery: Alternative Architecture Investigation

- **Task ID:** `OHB2-REPAIR-PLAN-06-ATTACHMENT-DELIVERY-ALTERNATIVE-ARCHITECTURE`
- **Type:** Investigation and architecture design only. **No runtime code, schema, dependency,
  config, or approved decision was changed.**
- **Author:** OpenHands agent (autonomous). Self-review quality only — **not** an independent
  security review.
- **Date (evidence retrieval):** 2026-11-15 (primary sources retrieved 2026-11-15T11:42Z).
- **Repo state when written:** branch `main`, HEAD `facf1f42578a20a4a37e220eca016ce3d534e750`
  (= `origin/main`), divergence `0 0`; working tree contains only the pre-existing Plan 05
  artifacts (see §2).
- **Related prior work:** `docs/reviews/OHB2-REPAIR-PLAN-05-SECURE-ATTACHMENT-DELIVERY-INVESTIGATION.md`
  (`BLOCKED`), `docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md` (§§16–27).

> Evidence labels: **[F] fact** (verified from a primary source this session), **[I] inference**,
> **[U] unknown / unverified**, **[R] recommendation**. Facts and inferences are kept separate.

---

## 1. Task ID and overall verdict

- **Task ID:** `OHB2-REPAIR-PLAN-06-ATTACHMENT-DELIVERY-ALTERNATIVE-ARCHITECTURE`
- **Overall verdict:** **`INVESTIGATION_COMPLETE — NO_SECURE_ALTERNATIVE_FOUND`**

**[F]** No investigated alternative establishes a secure, automatic path to deliver a Telegram file
into the **same existing conversation and workspace** while preserving every non-negotiable
constraint (§3). The Plan 05 blockers **B1** (no least-privilege upload credential) and **B2** (no
provider-committed trusted origin) **remain unresolved and are now re-verified against current
sources**. The only alternative that is **feasible today** is **E** (reduced scope: keep the
**implemented** local staging / attachment-intent tracking). **[F] Within E, local staging is
implemented; manual-transfer guidance and any "blocked/manual" UX status are NOT implemented** —
they are a possible future product decision. E adds no remote delivery.

> **`IMPLEMENTATION NOT AUTHORIZED`.** This report does not authorize implementation of any
> alternative, including E.

---

## 2. Actual repository baseline and Git state

### 2.1 Git state (verified this session)

- **[F] Branch:** `main`. **HEAD:** `facf1f42578a20a4a37e220eca016ce3d534e750`.
  **`main`:** same. **`origin/main`:** same. **Divergence** `git rev-list --left-right --count
  origin/main...HEAD` → `0  0`.
- **[F] `git status --short`:**
  - ` M .agent/PROGRESS.md` — **pre-existing**, produced by the Plan 05 session (not by this task).
  - `?? docs/reviews/OHB2-REPAIR-PLAN-05-SECURE-ATTACHMENT-DELIVERY-INVESTIGATION.md` —
    **pre-existing** untracked file from the Plan 05 session (not by this task).
- **[F] Staged:** none (`git diff --cached --name-only` empty).
- **[F] Ignored relevant files:** `.openhands/` only (plus `__pycache__/`, `.pytest_cache/`).
  **`.openhands/` was not modified.**
- **[F] No commit, push, PR, merge, release, or deployment was performed.** Autopush remains
  disabled/inactive; `MINI_APP_ENABLED` unchanged (default `False`, `bot/config.py:23,262`).

### 2.2 Documents read

- **[F]** `AGENTS.md` (full).
- **[F]** `docs/reviews/OHB2-REPAIR-PLAN-05-SECURE-ATTACHMENT-DELIVERY-INVESTIGATION.md` (Plan 05).
- **[F]** `docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md` (§§16–27 in full; §17–§24
  read in detail).
- **[F]** `docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md` (D-01…D-35; status of D-09, D-10,
  D-11, D-14, D-15, D-16, D-22, D-32, D-34, D-35).
- **[F]** Implementation: `bot/attachments.py`, `bot/db.py`, `bot/files.py`, `bot/outbox.py`,
  `bot/openhands_client.py`, `bot/config.py`.
- **[F]** `docs/plan-openhandBot-2.md` §4.1 (one backend / one state owner).
- **[F]** Reviews: `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R9-…` (`NEEDS_REVISION`),
  `…R12-…` (`PASS_WITH_NOTES`).

### 2.3 Baseline re-validation of Plan 05

- **[F]** The Plan 05 report and the current source **still agree**: the bot has **no** upload code
  (`grep -rniE "file/upload|session_api_key|X-Session-API-Key" bot/ main.py` → none in `bot/` or
  `main.py`; the only first-party `X-Session-API-Key` use is the **separate, inactive**
  `automation/autopush/main.py`).
- **[F]** `bot/files.py:15` still states "no file upload (the API does not support upload), no second
  client, no worker, no new table".
- **[F]** No document required by §2 was missing; every status was establishable.

### 2.4 Evidence sources retrieved this session (all public; no credential; no production API call)

| # | Source | Location | Version / commit |
| --- | --- | --- | --- |
| S1 | OpenHands **Cloud V1** OpenAPI | `https://app.all-hands.dev/openapi.json` | `info.version 1.92.0`, 257 paths |
| S2 | OpenHands **Agent Server** OpenAPI | `https://docs.openhands.dev/openapi/agent-sdk.json` | `info.version 0.1.0`, 40 paths |
| S3 | Agent Server **source** | `OpenHands/software-agent-sdk` @ `2aae48b6…` (`file_router.py`, `api.py`, `dependencies.py`, `bash_router.py`, `sockets.py`, `session_socket.py`) | 2026-11-15 |
| S4 | Agent Server **auth doc** | `https://docs.openhands.dev/sdk/arch/agent-server.md` | — |
| S5 | Cloud **origin construction** source | `OpenHands/enterprise` @ `7e8551f7…` (`remote_sandbox_service.py`) | 2026-11-15 |
| S6 | SDK **cloud workspace** source | `OpenHands/software-agent-sdk` @ `2aae48b6…` (`openhands-workspace/.../cloud/workspace.py`) | 2026-11-15 |
| S7 | Docs index | `https://docs.openhands.dev/llms.txt` (555 pages) + `.md` pages | — |
| S8 | Cookbooks | `docs.openhands.dev/cookbook/{start-sandbox,clone-and-attach,warm-sandbox-pool,custom-agent-with-tool,upload-skills}` | — |
| S9 | Enterprise doc | `docs.openhands.dev/enterprise/conversations-and-sandboxes` | — |

---

## 3. Plan 05 findings revalidated against current source

| Plan 05 claim | Re-validation (this session) | Status |
| --- | --- | --- |
| Cloud V1 has **no** upload route | **[F]** S1: `upload`/`multipart`/`"binary"`/`FileContent`/`attachment` tokens = **0**; file routes `GET …/file`, `…/files`, `…/download` only | **Confirmed** |
| Agent Server has exactly one upload endpoint | **[F]** S2: `POST /api/file/upload/{path}` (documented path-param shape), multipart `file` (`format: binary`) → `Success`; only upload op in 40 paths. **Shape caveat:** the pinned source (S3) registers `POST /api/file/upload` with a **query** param and returns `FileUploadResult` — see §4.2 | **Confirmed** (endpoint exists; shape differs, see §4.2) |
| Upload handler has **no** path confinement | **[F]** S3 `file_router.py::_upload_file`: only `if not target_path.is_absolute(): raise Invalid(...)`, then `mkdir(parents=True, exist_ok=True)`; **no** `resolve()`/`is_relative_to(workspace)` | **Confirmed** |
| Upload handler has **no** size limit | **[F]** S3: streams 8 KB chunks, no cap; `api.py` has no body-size middleware (only CORS + a runtime-dispatch middleware) | **Confirmed** |
| Single key guards everything (B1) | **[F]** S3 `api.py`: one `APIRouter(prefix="/api", dependencies=[Depends(require_initialized), Depends(check_session_api_key)])` mounts `file_router`, `bash_router`, `conversation_router`, `credential_binding_router`, `…/secrets`; `dependencies.py::check_session_api_key` checks only membership in `config.session_api_keys` (no scope) | **Confirmed** |
| Origin is infrastructure-dependent (B2) | **[F]** S5: `exposed_urls[AGENT_SERVER].url = runtime['url']`; `_build_service_url` emits **path-mode** `{scheme}://{netloc}/{runtime_id}/{service}` **or** **subdomain-mode** `{scheme}://{service}-{netloc}{path}` | **Confirmed** |
| No upload verification / no idempotency | **[F]** S2: no "list uploads"/"verify"/"stat" op; the response is `Success{success}` (documented) / `FileUploadResult{success, file_size}` (pinned source) — a **byte count only**, with no file id, no location, and no delivery proof; no `Idempotency-Key` parameter | **Confirmed** |
| No documented least-privilege scope | **[F]** S1 `securitySchemes = {APIKeyHeader: {in: header, name: X-Access-Token}}`; no `scope` on the upload surface; S2 `securitySchemes` **absent** | **Confirmed** |

**[F] Blockers B1 and B2 are not resolved.** They are re-verified against the *current* public API
surface and the *current* upstream source at the same commits Plan 05 cited.

---

## 4. Official provider API / documentation evidence

### 4.1 Cloud V1 (S1, v1.92.0) — the surface the bot already holds

- **[F]** Auth: `X-Access-Token` (the bot's existing `OPENHANDS_API_KEY`, `Authorization: Bearer`).
- **[F]** **No** upload / multipart / binary content anywhere.
- **[F]** File routes are **read-only** proxies: `GET /api/v1/app-conversations/{id}/file`,
  `…/files`, `…/download`.
- **[F]** `POST …/send-message` body `AppSendMessageRequest.content: anyOf[TextContent, ImageContent]`
  (`TextContent{type:"text",text}`; `ImageContent{type:"image",image_urls:[string]}`). **No** generic
  file/attachment content type. `ImageContent.image_urls` is `array<string>` with **no documented
  `data:`/base64 acceptance**.
- **[F]** `AppConversation` exposes `conversation_url`, `session_api_key`, `sandbox_id`.

### 4.2 Agent Server (S2/S3/S4, v0.1.0) — inside the sandbox

- **[F]** The upload endpoint exists on the Agent Server, but its **documented shape and its pinned
  source shape differ**. This discrepancy is recorded explicitly (not silently resolved):
  - **OpenAPI-documented path shape (S2):** `POST /api/file/upload/{path}` — the file path is a
    **path parameter** (`in: path`, "Absolute file path."); the documented 200 response is
    `Success` (`{success: boolean}`).
  - **Pinned source implementation shape (S3, `file_router.py` @ `2aae48b6…`):** the registered route
    is `@file_router.post("/upload")` with `path` as a **query parameter**
    (`path: Annotated[str, Query(...)]`, "Absolute file path"), i.e. `POST /api/file/upload?path=…`.
    The handler returns **`FileUploadResult`**, which **extends `Success`** with
    `file_size: int` ("Number of bytes written to the destination").
  - **SDK request shape (S6, `remote_workspace_mixin.py` @ `2aae48b6…`):** the SDK builds the URL as
    `f"{self.host}{self.api_prefix}/file/upload"` — the **query-parameter form** used by the pinned
    source.
- **[F]** Both shapes carry the same multipart `file` body and the same "absolute path" semantics;
  the differences are (a) path-parameter vs query-parameter, and (b) `Success` vs `FileUploadResult`.
- **[F]** Either way: **no** confinement, **no** size limit, **no** content validation, **no**
  ownership check, **no** idempotency, **no** verification op.
- **[F]** Auth: `X-Session-API-Key` = `config.session_api_keys` membership (server-wide). Same router
  also exposes `POST /api/bash/execute_bash_command` (arbitrary command execution) and
  `POST /api/conversations/{id}/secrets` (secret management).
- **[F]** Doc (S4): "Do not expose an unauthenticated Agent Server on a public network. It can execute
  commands and read or write files in its configured workspace."

**[F] Effect of the discrepancy on the B1/B2 conclusion: none.** B1 rests on the **shared, unscoped
`X-Session-API-Key`** guarding the same router as command execution and secrets, and B2 rests on the
**runtime-dependent, undocumented origin** — neither depends on whether the path is a path-parameter
or a query-parameter, nor on whether the response is `Success` or `FileUploadResult`. The mismatch is
reported as an observed fact; **no explanation for it is invented here** (the published spec and the
pinned source were inspected at the same commit and simply differ).

### 4.3 Official cookbooks (S8) — **new since the proposal**

**[F]** **Five** official cookbooks were retrieved (S8). **Three** of them directly demonstrate the
file-upload flow; **two** demonstrate other agent-server operations. The count is: **5 listed**,
**3 demonstrate upload**, **2 demonstrate non-upload agent-server operations**.

Cookbooks that **directly demonstrate upload** (`POST {agent}/api/file/upload`):

- `warm-sandbox-pool`: explicitly **uploads files** with
  `curl -X POST "$AGENT/api/file/upload?path=/tmp/init.sh" -H "X-Session-API-Key: $KEY" -F file=@…`.
- `custom-agent-with-tool`: uploads tool source via `POST /api/file/upload?path=…`.
- `upload-skills`: uploads a skills directory into the sandbox via
  `POST {agent}/api/file/upload?path=<tmp>`.

Cookbooks that demonstrate **other agent-server operations** (not upload):

- `start-sandbox`: `POST /api/v1/sandboxes` → poll `RUNNING` → read `exposed_urls[AGENT_SERVER]` and
  `session_api_key` → `POST {agent}/api/bash/execute_bash_command` (command execution, not upload).
- `clone-and-attach`: prepares a sandbox (clone + `.openhands/setup.sh`) then attaches a conversation
  via `POST /api/v1/app-conversations` with `sandbox_id` (conversation attach, not upload).

**[F]** The upload cookbooks confirm the endpoint is **official and supported** — but they **also
confirm** the credential used is the **full-privilege `session_api_key`** and the host is
`<sandbox-id>.prod-runtime.all-hands.dev`. They do **not** add a scoped credential, a size limit, or
a documented origin allowlist.

### 4.4 Origin evidence (S5, S6)

- **[F]** S5: origin = `exposed_urls[AGENT_SERVER].url = runtime['url']`; path-mode **or**
  subdomain-mode depending on the runtime URL.
- **[F]** S6 `OpenHandsCloudWorkspace._get_agent_server_url` returns `url_info.get("url")` with
  **no allowlist and no URL validation** (no `ipaddress`, no SSRF guard, no host check). The official
  SDK trusts the Cloud-returned URL verbatim.

---

## 5. All alternatives investigated

### Alternative A — Official OpenHands Cloud Upload API

- **[F]** No supported file-upload API for an existing conversation exists in Cloud V1 v1.92.0 (§4.1).
- **[F]** No least-privilege/upload-specific credential or scope is documented.
- **[F]** A stable way to identify the conversation exists (`GET /api/v1/app-conversations?ids=`), and
  `AppConversation.sandbox_id`/`conversation_url` exist — but there is no Cloud upload endpoint to
  use them with.
- **[F]** No server-side path confinement / size enforcement to evaluate (endpoint absent).
- **[F]** No documented roadmap item for a Cloud upload API in the public docs (llms.txt has none).
- **Verdict: `NOT_FEASIBLE`** (no such API today).

### Alternative B — Agent Server Upload with Security Improvements

- **[F]** The endpoint exists and is officially documented (§4.2–4.3), but:
  - **Authentication/authorization:** only the server-wide `X-Session-API-Key`; no scope (**B1**).
  - **Confinement/size/content/ownership:** none server-side; the bot would be the *only* guard.
  - **Trusted origin:** none documented; origin is runtime-dependent (**B2**).
  - **Verification/idempotency:** none; a lost response ⇒ permanent `uncertain`.
- **[F]** Client-side validation **cannot** compensate for missing server-side controls (explicitly
  forbidden to claim otherwise). A bot bug ⇒ arbitrary write inside the sandbox.
- **[F]** `bot/files.py:15` already documents that the OpenHands file read path is **not confined**
  (`file_path=/etc/hostname` returns container content) — the repo's security relies on a **local
  allowlist**, not on server confinement.
- **Verdict: `NOT_FEASIBLE`** under the current constraints (B1 + B2 unresolved; provider-side changes
  required).

### Alternative C — Official Alternative Integration Surface

Investigated candidates:

- **[F] Agent Server WebSocket event/session sockets** (`sockets.py`, `session_socket.py`):
  `events/{id}` is **receive-only** (server→client stream); the `session/{id}` socket accepts
  **inbound `Message` frames** whose content is `anyOf[TextContent, ImageContent]` — **text + image
  only, no file upload**. Same full-privilege key (`session_api_key` query param).
- **[F] Cloud `POST /api/v1/conversations/{id}/pending-messages`**: a **message queue** (delivered
  when the conversation is READY); **not** a file transfer. Text-oriented; request body not
  documented in the spec.
- **[F] MCP `POST /api/v1/mcp/servers/{name}/call-tool`**: runs an MCP tool **using the caller's
  stored server credentials** — **source-backed** (`OpenHands/enterprise` @ `7e8551f7…`,
  `openhands/app_server/mcp/mcp_tool_call_router.py`): the module docstring says it "calls one tool on
  an MCP server the caller has connected, with the credentials stored in their settings", and the
  handler loads the server from `settings_store.load()` → `enabled_mcp_servers(...)`, never from the
  request. It is a tool-invocation proxy, **not** a file-transfer-into-conversation mechanism. Not a
  workspace-delivery surface.
- **[F] Cloud `webhooks/*`**: inbound callbacks (conversation lifecycle / event stream) and
  `webhooks/conversations/{id}/children` (starts a **child conversation**). None transfers a file
  into the existing conversation's workspace.
- **[F] Agent Server `POST /api/skills` / `POST /api/hooks`**: load skills/hooks **from the sandbox
  filesystem** — they do **not** accept an uploaded payload.
- **[F] `ImageContent` via Cloud `send-message`**: **image-only**; `data:` URL acceptance is
  **undocumented and unverified against Cloud**; depends on a vision-capable LLM; cannot carry
  arbitrary files.
- **Verdict: `NOT_FEASIBLE`** for arbitrary files into the same conversation/workspace. The only
  image-only channel is `UNVERIFIED` and out of scope (not general file delivery).

### Alternative D — Provider-Managed or User-Mediated Transfer

- **[F] Provider-managed:** the only provider "upload" is the Agent Server endpoint (= Alternative B);
  Cloud has none. No provider-managed transfer workflow exists.
- **[F] User-mediated (Agent Canvas UI):** the user *can* upload images in a message and browse/download
  files in the conversation's Files view (S7, `agent-canvas/conversations`). But:
  - it is the **user's browser session** into the **same** conversation — the bot cannot drive it;
  - it does **not** transfer the Telegram file (the user would have to re-upload it manually);
  - it is a **genuine** attachment path (into the real workspace) **but** it is **not** an automatic
    Telegram→conversation delivery and cannot be verified or driven by OpenHandBot.
- **[U]** Whether a **future** provider-managed upload (with scoped credential + documented origin)
  will exist is unknown; no roadmap is published.
- **Verdict: `NOT_FEASIBLE`** for automatic delivery. A user-mediated manual path is a *workflow*, not
  an automatic solution; it delivers the file only if the **user** performs it.

### Alternative E — Alternative Product Scope (reduced feature)

**[F] LOCAL STAGING IS IMPLEMENTED. MANUAL TRANSFER GUIDANCE IS NOT IMPLEMENTED.** These two
statements are kept strictly separate; the second must not be read as current behavior.

- **[F] Implemented today (existing behavior):**
  - Telegram attachment **intake** and **bounded local staging** (A1 staging, A2 batches, A3 intent,
    A4 reaper; FIX-01…FIX-04 resource bounds).
  - Existing **local persistence and identity tracking** (durable batch rows + the
    `(telegram_id, chat_id, message_id)` identity evidence).
  - Existing **expiry/cleanup** behavior (15-minute batch deadline + reaper).
  - Existing **receipt/recording responses** — e.g. `ATTACHMENT_ACCEPTED_TEXT` ("استلمت الملف ✅ …")
    and `ATTACHMENT_TEXT_RECORDED_TEXT` ("وصل ✅ — حفظت النصّ المصاحب…"). These acknowledge local
    receipt/recording only.
  - **No automatic remote delivery to OpenHands.** No file leaves the bot's local staging.
- **[F] NOT implemented (must not be represented as existing behavior):**
  - **User-facing instructions** directing the user to upload/attach the file through the OpenHands
    UI. A repo-wide search of `bot/` finds **no** such text.
  - An **implemented manual-transfer workflow** (no bot flow walks the user through a manual upload).
  - A **UI state or workflow** that guarantees the file has been transferred into the intended
    OpenHands conversation/workspace.
- **[R] Possible future UX/product decision (NOT implemented, NOT authorized here):** adding a
  clearly-labelled manual-transfer guidance/blocked-state (Telegram text only; no new credential,
  host, or schema) *could* be proposed later. It is a **proposal**, not current behavior.
- **Verdict: `FEASIBLE` for the implemented local-staging behavior only.** Automatic remote delivery
  remains **blocked** (B1/B2). The attachment-delivery feature is **not** complete, and this
  alternative does **not** make it complete.

---

## 6. Security threat-model results

Enforcement boundary key: **P** = provider-enforced · **O** = OpenHandBot-enforced · **J** = joint ·
**N** = not available / unverified.

| # | Control | Alternative B (Agent Server upload) | Alternative C (other surfaces) | Alternative E (reduced scope) |
| --- | --- | --- | --- | --- |
| 1 | Authentication | **P** server-wide `X-Session-API-Key` (no scope) | **P** same key | N/A (no remote call) |
| 2 | Least-privilege credential | **N** — key = command exec + secrets | **N** — same key | N/A |
| 3 | Trusted-origin establishment | **N** — runtime-dependent, undocumented | **N** — same host problem | N/A |
| 4 | DNS resolution / rebinding | **O** (pinned-IP possible) but origin **N** ⇒ moot | **N** | N/A |
| 5 | IPv4 / IPv6 handling | **O** (blocklists possible) — but weak-vs-origin gap remains | **N** | N/A |
| 6 | Redirect behavior | **O** (can refuse redirects) | **O** | N/A |
| 7 | TLS verification / proxy | **O** (TLS on; ignore proxy) | **O** | N/A |
| 8 | Path-mode / subdomain-mode compat | **N** — both modes exist; no fixed pattern | **N** | N/A |
| 9 | SSRF exposure | **N** — no allowlist; key leak risk | **N** | **N/A** (none) |
| 10 | Workspace path traversal / confinement | **N** — server accepts any absolute path | **N** | N/A |
| 11 | File-size enforcement | **N** server-side; **O** client cap only | **N** | N/A |
| 12 | Content-type / content validation | **N** server-side; **O** client only (insufficient) | **N** | N/A |
| 13 | Conversation/workspace ownership | **N** — key not conversation-scoped | **N** | N/A |
| 14 | Credential rotation / revocation | **N** — no per-conversation revocation API documented | **N** | N/A |
| 15 | Upload retries / duplicate delivery | **N** — no idempotency key | **N** | N/A |
| 16 | Ambiguous network outcomes | **N** — no verify op | **N** | N/A |
| 17 | Verification of remote completion | **N** — response is a byte count (`FileUploadResult.file_size`); no delivery proof | **N** | N/A |
| 18 | Cleanup / retention | **O** local staging bounded (FIX-01…04) | **O** local | **O** local |
| 19 | Logging / sensitive-data exposure | **O** (must never log the key/URL) | **O** | **O** |

**[F] Summary:** for Alternative B every *remote* security control is **provider-side and absent**
(rows 1–3, 8–17). The controls OpenHandBot could enforce (rows 4–7, 18–19) do **not** close B1 (row 2)
or B2 (row 3). **[F] A control that cannot be demonstrated remains unresolved.** Therefore B stays
blocked. Alternative E adds **no** remote attack surface.

---

## 7. Same-conversation and same-workspace compatibility

- **[F] Same conversation:** every remote alternative targets a conversation identified by
  `conversation_id`; the bot already operates the same conversation (`send_message`, `PATCH`, `DELETE`
  on `/app-conversations/{id}`). No fallback creates a new conversation (`start_conversation` exists
  but is used only for explicit creation flows; it is **not** part of any proposed delivery path).
- **[F] Same workspace:** the agent-server upload writes into the sandbox filesystem; the sandbox is
  **shared** by conversations when grouping is on (S9: "A separate conversation is not a security
  boundary when it shares a sandbox"). So "same workspace" is only approximately guaranteed and
  depends on the user's **Sandbox Grouping Strategy** (S9) — a placement rule, not a hard guarantee.
- **[F] Compatible alternative:** Alternative E operates purely on local staging tied to the
  conversation row already stored in SQLite — **same conversation, same workspace, no remote call**.
- **[F] Conclusion:** same-conversation compatibility is **established only for E**; for B/C it is
  **`UNVERIFIED`** to the extent that the workspace may be shared with sibling conversations.

---

## 8. State and reconciliation feasibility

**[F] Actual existing states** (`bot/db.py:110–137`) — eight defined values. Every one is classified
below; **no new state or transition is introduced here**:

- **Produced by the current implementation (3):**
  - `pending` — written on batch creation (`bot/attachments.py`).
  - `intent_recorded` — written atomically by `record_attachment_intent` (`bot/db.py`).
  - `expired` — written by both `mark_attachment_batch_status` call sites (`bot/attachments.py`,
    both `EXPIRED`).
- **Defined/referenced but NOT produced by the implementation (5):**
  - `rejected` — the constant exists (`bot/db.py:127`) and is referenced in terminal-status sets
    (`bot/db.py:1391`, `bot/attachments.py` `_TERMINAL`), but **no code writes it** to
    `attachment_batches`; it is **not** an implemented transition.
  - `dispatching` — schema placeholder; no transition logic (unimplemented Phase B).
  - `uncertain` — schema placeholder; no transition logic (unimplemented Phase B).
  - `delivered` — schema placeholder; no transition logic (unimplemented Phase B).
  - `failed` — schema placeholder; no transition logic (unimplemented Phase B).

So: **3 produced**, **5 defined-but-not-produced** (of which `rejected` is referenced in read-side
terminal sets but never written). The four `dispatching`/`uncertain`/`delivered`/`failed` values are
future/placeholder states belonging to the unimplemented Phase B.

| Lifecycle checkpoint | Can Alternative B distinguish it? | Alternative E |
| --- | --- | --- |
| Local staging success | **[F] Yes** (local) | **[F] Yes** |
| Upload request acceptance | **[F] Partly** — HTTP 200 with a **byte count** (`FileUploadResult.file_size`; the documented `Success` has no size); no file id | N/A |
| Confirmed remote file existence | **[F] No** — no verify/stat op | N/A |
| Delivery to intended conversation/workspace | **[F] No** — key not conversation-scoped; shared sandbox | N/A |
| Text prompt delivery | **[F] Yes** — existing `send-message` | N/A |
| Final completion | **[F] No** — cannot be confirmed server-side | N/A |

- **[F]** With **no idempotency and no verification/query mechanism**, an ambiguous upload (timeout,
  lost response) cannot be reconciled without **blind retry (risk of duplicate delivery)**. The
  correct behavior — no blind retry, no premature delete — leaves a **permanent `uncertain`** state
  with **no resolution path**. **[F]** This limitation is exactly what Plan 05 flagged; it is
  **unchanged**.
- **[F]** Alternative E supports a **clean** lifecycle (local staging → intent → local expiry) and
  requires **no** remote reconciliation.
- **[F] The Telegram identity tuple `(telegram_id, chat_id, message_id)` is preserved** by this
  investigation (no change to `attachment_message_identity`, D-33/D-34/D-35).
- **[F] D-10, D-11, D-14, D-15, D-16, D-22 are unchanged** and remain **OPEN**.

---

## 9. Comparative evaluation matrix

| Alternative | Official provider support | Same-conversation | Same-workspace | Least-privilege auth | Trusted-origin feasibility | Server-side controls | Upload verification | Ambiguous-outcome reconciliation | Architectural compatibility | Required owner decisions | Main unresolved risks | Overall feasibility |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **A** Cloud upload API | **[F] None** (no route) | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | D-10/D-11 | No API exists | **`NOT_FEASIBLE`** |
| **B** Agent Server upload | **[F] Yes** (documented + cookbooks) | **[U]** (shared sandbox) | **[U]** (shared sandbox) | **[F] No** — full-privilege key | **[F] No** — runtime-dependent | **[F] None** (unconfined, no size) | **[F] None** | **[F] None** | **[F] Requires** 2nd target + 2nd auth scheme + new table | B1, B2, D-10/D-11/D-14/D-15/D-16/D-22, arch approval | Arbitrary write; key leak; no reconciliation | **`NOT_FEASIBLE`** |
| **C** Other integration surface | **[F] Partial** (sockets/messages; image-only) | **[U]** | **[U]** | **[F] No** (same key) | **[F] No** | **[F] None** | **[F] None** | **[F] None** | same as B | same as B | Cannot carry arbitrary files | **`NOT_FEASIBLE`** |
| **D** Provider/user-mediated | **[F] Provider: none**; **[F] user-mediated exists** | **[F] Yes** (user's own UI) | **[F] Yes** | **[F] N/A** (user session) | **[F] N/A** | **[F] N/A** | **[U]** (user-driven) | N/A | **[F] No bot automation** | Product/UX decision | Not automatic; bot cannot drive/verify | **`NOT_FEASIBLE`** (for automatic delivery) |
| **E** Reduced scope (local staging only) | **[F] N/A** (no remote call) | **[F] Yes** (local row) | **[F] Yes** (local row) | **[F] N/A** | **[F] N/A** | **[F] N/A** | **[F] N/A** | **[F] N/A** | **[F] Fits** existing architecture | None new for staging; manual UX guidance **not implemented** (product decision) | No file delivered; manual-transfer guidance not implemented | **`FEASIBLE`** (local staging only) |

**[F]** Every classification above is backed by the evidence in §3–§8. **[F]** No alternative is
ranked `FEASIBLE` merely for being technically possible; only **E** is, and only for its
**implemented local-staging behavior** — not for any manual-transfer guidance, which is
**not implemented** (see §5).

---

## 10. Recommended architecture (or explicit no-go)

**[R] Recommendation: retain the current safe local-staging behavior (implemented) and keep
automatic remote delivery blocked. Manual-transfer guidance is a possible future product decision
(not implemented). (Explicit no-go for automatic delivery.)**

- **[F] Why it is safer than the others:** it introduces **no** second external target, **no** second
  auth scheme, **no** full-privilege credential, **no** unconfined write path, and **no** unresolved
  origin — i.e. it eliminates B1 and B2 by **not** using them. It preserves every §3 constraint.
- **[F] Blockers it resolves:** **B1** and **B2** are resolved by *not* adopting a remote path.
- **[F] Blockers that remain unresolved:** B1/B2 remain **blocking** for any future remote design;
  the missing server-side confinement/size/content/ownership, verification, and idempotency
  (Plan 05 secondary blockers) remain **unresolved**.
- **[F] Provider-side changes required** for a future remote path: an upload-scoped credential, a
  documented/committed agent-server origin allowlist, workspace-root confinement, server-side size
  limits, content validation, ownership enforcement, an upload-verification/query operation, and
  idempotency. **None exists today.**
- **[F] New credential/service/architecture decision:** required for any remote path (2nd target +
  2nd auth scheme + new pending-batch table) — **not** granted.
- **[F] Existing SQLite/outbox:** fully sufficient for Alternative E; no change needed.
- **[F] Same-conversation / same-workspace:** fully preserved by E.
- **[R] Additional approvals required before any implementation:** see §11.

> **[F]** No secure alternative meeting the security and architectural requirements was found. The
> report does **not** manufacture a solution.

---

## 11. Required owner decisions and architectural approvals

None is granted here; all remain **OPEN**.

1. **[F] D-10** — capability ownership (Cloud V1 vs Agent Server). **Owner decision required.**
2. **[F] D-11** — scoping mechanism (delegated Cloud path vs capability token). **Owner decision.**
3. **[F] D-14** — delivery mechanism (design A/B/C/D; whether to extend `send-message`).
4. **[F] D-15** — `expires_at` fixed 15 min, staging-only reclaim, no server-side batch. **Confirm.**
5. **[F] D-16** — `Idempotency-Key` + `sha256` dedup + delivery idempotency (U-4).
6. **[F] D-22** — outbox integration (new item type vs another approved mechanism).
7. **[R] Security (B1)** — accept a full-privilege, command-execution-capable credential for a
   file-write feature, **or** obtain an upload-scoped credential.
8. **[R] Security (B2)** — a provider-committed, stable agent-server origin allowlist (must not be
   replaced by a weak hostname check or private-IP filtering).
9. **[R] Architecture** — approval for a second external target + second auth scheme + a new
   pending-batch table (departures from `bot/files.py:15` and `docs/plan-openhandBot-2.md` §4.1).
10. **[R] Reconciliation** — a documented reconciliation path for an ambiguous upload outcome, or an
    explicit product acceptance of a permanent `uncertain` state.
11. **[R] Product (E)** — explicit confirmation that the **implemented** reduced-scope behavior
    (local staging + receipt/recording responses) is the accepted product outcome, **and** whether to
    add **manual-transfer guidance** as a **future** UX/product decision (that guidance is
    **not implemented** today).

---

## 12. Provider-side dependencies and questions

**[R] Questions to put to the provider (OpenHands):**

1. Is a **file-upload API for an existing conversation** on the Cloud V1 surface planned, and if so
   with what auth and scope?
2. Does an **upload-scoped / least-privilege credential** exist or is one planned (so the upload key
   cannot execute commands or manage secrets)?
3. Is there a **provider-committed, stable host pattern** for `exposed_urls[AGENT_SERVER]` /
   `conversation_url` (a documented allowlist we can pin), for **both** path-mode and subdomain-mode?
4. Will the Agent Server upload endpoint gain **workspace-root path confinement**, a **server-side
   size limit**, **content validation**, and **conversation/workspace ownership enforcement**?
5. Will an **upload-verification/query** operation and **idempotency** be provided, so an ambiguous
   outcome can be reconciled without blind retry?
6. Is the **sandbox workspace** guaranteed private to a single conversation, or is it shared per the
   grouping strategy (which would make "same workspace" a best-effort guarantee)?

**[F]** Until questions 1–5 are answered with a committed, verifiable design, the blockers stand.

---

## 13. Proposed future implementation phases (NOT authorized)

These are sketches for a **future, separately authorized** task. **Nothing here is authorized.**

- **Phase P-0 (if the owner confirms E):** no code change; document the accepted reduced-scope
  behavior **and**, as a separate future product decision, any manual-transfer guidance. The
  guidance itself is **not implemented** today. *(No runtime change.)*
- **Phase P-1 (only if B1+B2 are resolved by the provider):** design the origin-allowlist + pinned-IP
  SSRF guard and the upload-scoped credential handling (design-only, reviewed).
- **Phase P-2:** design the pending-batch schema and the `pending→…→delivered/uncertain` transitions
  with no blind retry (design-only, reviewed).
- **Phase P-3:** implementation behind an explicit owner approval, with the provider-side controls
  present and independently verified.

**[F] Phase P-3 must not begin until B1 and B2 are resolved with committed provider evidence and the
§11 approvals are granted.**

---

## 14. Tests / verification performed and exact results

- **[F] Read-only static inspection only.** No runtime code changed ⇒ no new tests authored
  (AGENTS.md: do not invent tests for a read-only investigation).
- **[F] Commands run (evidence, not claims):**
  - `git rev-parse HEAD main origin/main` → all `facf1f42578a20a4a37e220eca016ce3d534e750`.
  - `git rev-list --left-right --count origin/main...HEAD` → `0  0`.
  - `git status --short` → ` M .agent/PROGRESS.md`, `?? docs/reviews/OHB2-REPAIR-PLAN-05-…md`.
  - `curl https://app.all-hands.dev/openapi.json` → HTTP 200, 919,136 bytes, `info.version 1.92.0`,
    257 paths; token counts `upload=0`, `multipart=0`, `"binary"=0`, `FileContent=0`, `attachment=0`.
  - `curl https://docs.openhands.dev/openapi/agent-sdk.json` → HTTP 200, 402,351 bytes,
    `info.version 0.1.0`, 40 paths; documented upload op `POST /api/file/upload/{path}` (path-param,
    `Success`); `securitySchemes` absent.
  - `curl` of `OpenHands/software-agent-sdk` @ `2aae48b6…` source files → `_upload_file` = `is_absolute()`
    + `mkdir`; **pinned route `@file_router.post("/upload")` with `path` as a query param and
    `FileUploadResult` response**; SDK `remote_workspace_mixin.py` builds `/file/upload` (query form);
    single-key router in `api.py`; `check_session_api_key` membership-only.
  - `curl` of `OpenHands/enterprise` @ `7e8551f7…` → `exposed_urls[AGENT_SERVER].url = runtime['url']`;
    `_build_service_url` path/subdomain modes.
  - `curl` of `openhands-workspace/.../cloud/workspace.py` @ `2aae48b6…` → `_get_agent_server_url`
    returns the URL with **no** allowlist/validation.
  - `curl` of cookbook `.md` pages (`start-sandbox`, `clone-and-attach`, `warm-sandbox-pool`,
    `custom-agent-with-tool`, `upload-skills`) → the three upload cookbooks (`warm-sandbox-pool`,
    `custom-agent-with-tool`, `upload-skills`) use `POST /api/file/upload` with the full-privilege
    `X-Session-API-Key`; the two others (`start-sandbox`, `clone-and-attach`) use other agent-server
    operations.
  - `grep -rniE "file/upload|session_api_key|X-Session-API-Key" bot/ main.py` → none.
  - `curl` of `OpenHands/enterprise` @ `7e8551f7…`
    `openhands/app_server/mcp/mcp_tool_call_router.py` → `call-tool` loads the MCP server from the
    caller's stored settings (`settings_store.load()` → `enabled_mcp_servers(...)`), never from the
    request (source for the §5 MCP claim).
  - `grep -rniE "واجهة OpenHands|من داخل الواجهة|attach.*OpenHands|the bot tells the user" bot/` →
    **none** (no user-facing manual-upload guidance in `bot/`; supports the M-1 distinction).
- **[U] Not run:** the pytest suite / linters were **not** run, because **no code changed**. The
  baseline for HEAD `facf1f4` is believed green from the prior synchronization session, but that is
  **[I]**, not re-verified here.
- **[F] No production API call and no credential were used** for any capability test.

---

## 15. Explicit list of files changed

- **[F] Created:** `docs/reviews/OHB2-REPAIR-PLAN-06-ATTACHMENT-DELIVERY-ALTERNATIVE-ARCHITECTURE.md`
  (this report).
- **[F] Modified:** `.agent/PROGRESS.md` (append-only progress note, per AGENTS.md §9).
- **[F] No other file changed.** No runtime source, no tests, no configuration, no protected path,
  no migration. The two pre-existing Plan 05 artifacts were **not** modified by this task.

---

## 16. Final Git status and confirmation of no runtime changes

- **[F] Branch `main`, HEAD `facf1f42578a20a4a37e220eca016ce3d534e750` (= `origin/main`), divergence
  `0 0`.**
- **[F] `git status --short` (final):**
  - ` M .agent/PROGRESS.md`
  - `?? docs/reviews/OHB2-REPAIR-PLAN-05-SECURE-ATTACHMENT-DELIVERY-INVESTIGATION.md` (pre-existing)
  - `?? docs/reviews/OHB2-REPAIR-PLAN-06-ATTACHMENT-DELIVERY-ALTERNATIVE-ARCHITECTURE.md` (this task)
- **[F] Staged:** none. **[F] `.openhands/` untouched.** **[F] `MINI_APP_ENABLED` unchanged
  (default `False`).** **[F] Autopush remains disabled/inactive.**
- **[F] No commit, push, PR, merge, release, or deployment. No destructive Git command was used.**

---

## 17. Remediation addendum — independent review findings (2026-11-14)

- **[F] Independent review verdict:** `NEEDS_REMEDIATION` (review of this report's
  `INVESTIGATION_COMPLETE — NO_SECURE_ALTERNATIVE_FOUND` output). The review **confirmed** the central
  security analysis, the B1/B2 blockers, the alternative classifications, and the remote-delivery
  no-go. The remediation below is **documentation-only**; it changes no runtime code, schema, state
  machine, or approved decision, and it does **not** weaken the no-go.
- **[F] Findings addressed (documentation corrections only):**
  - **M-1 (MEDIUM)** — Alternative E: removed the unsupported claim that "the bot tells the user how
    to attach the file in the OpenHands UI" and the "(and is the current behavior)" verdict. §1, §5,
    §9, §10, §11.11, §13 P-0, and the owner summary now state clearly: **local staging IS
    implemented; manual-transfer guidance is NOT implemented** (a possible future product decision).
  - **L-1 (LOW)** — §3/§4.2/§14 now explicitly distinguish the OpenAPI-documented path shape
    (`POST /api/file/upload/{path}` → `Success`), the pinned source shape
    (`POST /api/file/upload` with a **query** `path` → `FileUploadResult`), and the SDK request shape
    (query form). The discrepancy is reported as observed, with no invented explanation, and its
    **non-effect on B1/B2** is stated.
  - **L-2 (LOW)** — §4.3/§14 corrected: **five** cookbooks listed, **three** demonstrate upload,
    **two** demonstrate other agent-server operations.
  - **L-3 (LOW)** — §8 now classifies **every** defined state: **3 produced** (`pending`,
    `intent_recorded`, `expired`) and **5 defined-but-not-produced** (`rejected` referenced in
    read-side terminal sets but never written; `dispatching`/`uncertain`/`delivered`/`failed`
    placeholders). No state or transition was added.
  - **I-1 (INFO)** — §3/§6/§8 wording corrected: the response is a **byte count**
    (`FileUploadResult.file_size`), not a generic "Success only"; a returned size is **not** proof of
    workspace ownership, conversation identity, or delivery.
  - **I-2 (INFO)** — §5 MCP `call-tool` claim is now **source-backed** (enterprise @ `7e8551f7…`,
    `mcp_tool_call_router.py`): the server is loaded from the caller's stored settings, never from
    the request. §14 records the source.
- **[F] Unchanged by this remediation:** B1/B2 conclusions, the five alternative classifications, the
  D-10/D-11/D-14/D-15/D-16/D-22 open decisions, and the `IMPLEMENTATION NOT AUTHORIZED` status.
- **[R] A separate independent re-review is still required.**

---

## Owner-decision summary (concise)

1. **Confirm Alternative E** — the **implemented** local staging + receipt/recording responses — as
   the accepted product outcome, **and** decide separately whether to add **manual-transfer guidance**
   as a **future** UX/product decision (guidance is **not implemented** today; automatic remote
   delivery stays blocked). **Or** reject it. *(Decision 11 in §11.)*
2. To unblock any remote path, resolve **B1** (upload-scoped credential or explicit acceptance of the
   full-privilege key) and **B2** (provider-committed origin allowlist), plus D-10/D-11/D-14/D-15/
   D-16/D-22 and the architecture approval. *(Decisions 1–10 in §11.)*
3. Until then, **no** implementation.

> ## `IMPLEMENTATION NOT AUTHORIZED`
>
> **Attachment delivery is not complete. No file was delivered remotely. No unexecuted test and no
> unverified provider capability is claimed as PASS.**
