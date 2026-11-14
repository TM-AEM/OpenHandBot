# OHB2-P0-SECURE-UPLOAD-PROPOSAL-R2 — INDEPENDENT ADVERSARIAL REVIEW

**Task ID:** `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R2-INDEPENDENT-ADVERSARIAL-REVIEW`

Reviewer: fresh-context independent adversarial reviewer; **not** the author of the proposal under
review. All actions were **read-only**: public specs and public source re-fetched independently,
**no production call, no credential, no secret access, no file modification** (this review file is
the only artifact created), no commit/push/PR/merge/deploy. The proposal and the r1 review were
**not** modified.

- **Repository:** `TM-AEM/OpenHandBot`
- **Branch:** `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW`
- **HEAD:** `907b20de3fa6627795c14f29677e9f39c68e82f4`
- **origin/main:** `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c`
- **Artifact under review:** `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md`
  (874 lines, untracked), **revision r2** (header + §13).
- **Prior review:** `docs/reviews/OHB2-P0-SECURE-UPLOAD-UPSTREAM-PROPOSAL-INDEPENDENT-ADVERSARIAL-REVIEW.md`
  (r1, verdict `PASS_WITH_MAJOR_FINDINGS — REVISION REQUIRED`, findings F1–F4).
- **Correction report:** task `OHB2-P0-SECURE-UPLOAD-PROPOSAL-EVIDENCE-CORRECTION-AND-REVISION`
  (recorded in `.agent/PROGRESS.md` and `.openhands/memory/2026-11-11.md`).

## Verdict: **PASS_WITH_NOTES**

r2 is **technically accurate, internally consistent, secure in design, and suitable for final owner
approval as an upstream request.** The four major/moderate findings from the r1 review (F1–F4) are
**corrected** and independently re-confirmed. The residual findings below (R2-1 … R2-6) are
accuracy/completeness **notes**; none invalidates the design, the security analysis, or the
recommendation. **A PASS here means only that r2 is fit for owner approval — it does NOT mean P0 is
implemented.** P0 remains unimplemented; the bot's fail-closed attachment rejection stays in force.

---

## 1. Independent source revisions and hashes

All fetched fresh this session from public raw/spec endpoints; `sha256` prefixes shown. Pinned SHAs
were **independently confirmed to still equal `main`** (`api.github.com/.../branches/main`).

| Source | Identifier | sha256 (this session) |
| --- | --- | --- |
| Cloud V1 live OpenAPI | `app.all-hands.dev/openapi.json`, `info.version 1.87.1`, 242 paths | `0086b0b0…ff77916` (888015 B) |
| Agent Server docs export | `docs.openhands.dev/openapi/agent-sdk.json`, 0.1.0, 40 paths | `e42da653…5374a4d` (402351 B) |
| `OpenHands/software-agent-sdk@9f7d5cb11b1256c1878f5584a657401feca9ad16` (**== main**) | `agent_server/file_router.py` | `13f0cae7…74cb95` |
| | `agent_server/runtime_router.py` | `5bea70f0…ec9029` |
| | `agent_server/conversation_registry.py` | `4a479391…4ef36` |
| | `agent_server/api.py` | `5de71d80…ce2423` |
| | `agent_server/dependencies.py` | `f5f51362…d5a15` |
| | `agent_server/server_details_router.py` | `2878f452…a1f34d` |
| | `agent_server/models.py` | `57b3680c…a8744b` |
| | `agent_server/config.py` | `0b064821…9caaf` |
| | `agent_server/middleware.py` | `59980d01…6ffd14` |
| | `tests/agent_server/test_runtime_router.py` | `98f931d8…a5e1dd` |
| | `openhands-sdk/…/llm/message.py` (ImageContent) | `1b9f0693…74904c6` |
| | `openhands-sdk/…/workspace/remote/remote_workspace_mixin.py` | `0e55f7ab…ada8c` |
| | `clients/typescript/src/client/runtime-transport.ts` | `83ed2772…1056b3` |
| | `clients/typescript/src/workspace/remote-workspace.ts` | `581712c2…d05a4a1` |
| | tags `v1.10.0` / `v1.20.0` / `v1.58.1` / `v1.62.0` `file_router.py` | `32a1664d…` / `8f864158…` / `995aabc0…` / `13f0cae7…` |
| `OpenHands/sandbox-server@43e91604ccd0a9960c8d5c52faadd60b30f10e63` (**== main**) | `app_conversation/app_conversation_router.py` | `864bff55…51259` |
| | `app_conversation/live_status_app_conversation_service.py` | `9653dd3d…1e69c` |
| | `sandbox/remote_sandbox_service.py` | `c523a807…d49cc` |
| | `sandbox/session_auth.py` | `893d725e…3dcf055` |
| `OpenHands/enterprise@main` (**NEW — see R2-1**) | `openhands/app_server/app_conversation/app_conversation_router.py` | `c43ed4f7…1f2af` |
| | `frontend/src/api/conversation-service/v1-conversation-service.api.ts` | `0a0b80c6…404bf` |
| `OpenHands/OpenHands@a8aaf6813753803cae5182d050909705b0eb02d0` (**== main**, GUI) | `src/api/conversation-file-upload.api.ts` | `d5ae6b81…d73a0` |
| | `src/api/workspace-upload-path.ts` | `caabd831…dc8c` |
| | `src/api/agent-server-client-options.ts` | `78364c26…b54d` |
| | `src/utils/file-validation.ts` | `51b16ff5…ab63` |
| | `src/utils/send-message-with-attachments.ts` | `fea01cfc…5b022` |
| | `src/utils/convert-image-to-base-64.ts` | `e3069cfb…683ac` |
| | `src/components/features/chat/utils/chat-input.utils.ts` | `70e91cd0…dcf4a` |
| | `src/api/cloud/conversation-service.api.ts` | `94f38037…8c39` |

Every hash in the proposal's §11 that could be re-derived **matches** (agent-server
`api/runtime_router/conversation_registry/file_router/dependencies/server_details_router/models`,
sandbox-server `app_conversation_router/live_status_.../remote_sandbox_service/session_auth`, GUI
`conversation-file-upload/workspace-upload-path/agent-server-client-options/file-validation`,
SDK `remote_workspace_mixin`, TS `runtime-transport`, Cloud `0086b0b0…`, docs export `e42da653…`).

---

## 2. F1–F4 recheck (independent)

### F1 — conversation-bound upload route — **CORRECTED, CONFIRMED**

- **Route registration:** `conversation_registry.py::add_execution_routes` →
  `router.include_router(create_runtime_router())` (L47-52); `api.py` calls `add_execution_routes(api_router)`
  (L652) under `api_router = APIRouter(prefix="/api", dependencies=[Depends(require_initialized),
  Depends(check_session_api_key)])` (L643-647). ✅
- **Parameter semantics:** the scoped route inherits `file_router`'s decorator
  `@file_router.post("/upload")` with `path` as a **`Query`** parameter (`file_router.py` L742-748);
  no `upload/{path}` decorator exists at the pinned SHA (the `/{path:path}` form exists only at
  `v1.10.0`; `v1.20.0`, `v1.58.1`, `v1.62.0` and main are all the query form — verified). ✅
- **Auth dependency:** `bind_local_conversation_runtime(runtime_conversation_id, request)`
  (`runtime_router.py` L31-62). ✅
- **Workspace containment:** L44-52 rejects with **422** unless `Path(requested_path).is_absolute()`
  **and** `Path(requested_path).resolve().is_relative_to(workspace_root)`; `workspace_root =
  Path(...workspace.working_dir).resolve()` (L41-43). ✅
- **"Complete resolved destination" — IMPORTANT nuance:** containment is applied to the **request
  parameter** `path` (and `workspace_dir`), by resolving the *given string*. It is **not** a
  post-resolution guard on the final write. `_upload_file` then does
  `target_path.parent.mkdir(parents=True, exist_ok=True)` and `open(target_path, "wb")` with **no**
  `O_NOFOLLOW`/`O_EXCL` (`file_router.py` L103-110). Therefore: containment applies to the *path
  string* at request time; it does **not** guarantee the bytes land in a non-symlinked file. This is
  exactly the symlink/TOCTOU caveat r2 states (§2.3.5 "resolve() at check time only", §7.4). r2 does
  **not** equate containment with complete upload security — **confirmed correct**. ✅
- **Symlink / race implications:** `resolve()` follows symlinks at check time; a symlink created
  between the check and the `open()` (TOCTOU) is not prevented. r2 requires `O_NOFOLLOW` +
  `O_CREAT|O_EXCL` as *new* work (§5.7, §7.4). ✅
- **Does the GUI use this route?** **YES.** The official GUI sets `conversationId` on the agent-server
  client (`getAgentServerClientOptions({conversationId, …})`, `agent-server-client-options.ts`), so
  the TS runtime client selects the scoped route when the server advertises
  `conversation_runtime_routes_v1` (`runtime-transport.ts` L44-48). See R2-4 for a second official
  frontend that still targets the legacy route.
- **Not equating containment with security:** confirmed — r2 states the gap as
  *authorization scoping + destination resolution + limits + reconciliation* (§1, §3, §5.1). ✅

### F2 — OpenAPI evidence / stale export — **CORRECTED, CONFIRMED**

- The docs export (`agent-sdk.json`, 0.1.0, 40 paths) is **stale**: only upload path
  `/api/file/upload/{path}` (path param), `securitySchemes = None`, **no** `capabilities` on
  `ServerInfo`, **no** `/api/auth/workspace-session`, **no** conversation-scoped runtime routes. ✅
- **Which revision controls the contract:** the **source at the pinned SHA**
  (`software-agent-sdk@9f7d5cb1…`) — the proposal's precedence rule (§2.1) is correct. ✅
- **Version/SHA accuracy:** all three pinned SHAs **== current `main`** (SDK 2026-11-12, OpenHands
  2026-11-12, sandbox-server 2026-10-22). ✅ (sandbox-server date is now stated in the header, fixing
  r1's F5.)

### F3 — gap classifications — **CORRECTED, CONFIRMED**

Independently re-derived against source:

| Property | r2 status | Verified |
| --- | --- | --- |
| **A. Narrow authorization** | **NO** | ✅ scoped route reuses the same server-wide `X-Session-API-Key`; `check_session_api_key` only checks membership in `config.session_api_keys`; the same key guards `bash_router` (`POST /api/bash/execute_bash_command`). |
| **B. Trusted destination** | **PARTIAL** | ✅ server-side *confinement* exists on the scoped route (422); server-side *destination resolution* does not (client supplies absolute `path`). |
| **C. Safe upload handling** | **PARTIAL** | ✅ traversal/workspace-root containment exists (422) + dir/parent guards (400); **no** size/total/count/type limits (no size middleware in `middleware.py`; no size/type config in `config.py`); **no** symlink/TOCTOU hardening. |
| **D. Reliable outcome + reconciliation** | **NO** | ✅ response is `FileUploadResult(Success) = {success, file_size}` only; no op id / status / idempotency. |
| **E. Operational constraints** | **PARTIAL** | ✅ key revocable by rotation; formal REST breakage policy exists; upload quotas/audit/deleted-conversation semantics missing. |

Executable evidence re-confirmed in `tests/agent_server/test_runtime_router.py`: cross-conversation
read ⇒ **422** (L83-85), relative path ⇒ **422** (L87), wrong key ⇒ **401** (L99), legacy
`/api/file/download` absolute path ⇒ **200** (L88-91), scoped upload onto dir / under file ⇒ **400**
(L231-249), `conversation_runtime_routes_v1` advertised (L102). ✅

### F4 — Cloud API coverage — **CORRECTED, CONFIRMED**

Live Cloud 1.87.1 file/git routes, all **read/download only**:
`GET …/{id}/file`, `GET …/{id}/files`, `GET …/{id}/download`, `GET …/{id}/git/changes`,
`GET …/{id}/git/diff`. **No** upload anywhere: `"multipart"` = 0, `format: "binary"` = 0;
request-body content types = `application/json` (81 ops) + `application/x-www-form-urlencoded`
(5 ops, exactly `/oauth/device/token`, `/oauth/device/verify-authenticated`, `/oauth/idp/login`,
`/oauth/idp/signup`, `/oauth/idp/invite` — the proposal's claim is precise). ✅
`send-message` body = `AppSendMessageRequest.content = array(anyOf[TextContent, ImageContent])`,
`minItems: 1`. ✅ `AppConversation` exposes `conversation_url`, `session_api_key`, `sandbox_id`. ✅
The server-side hop is confirmed in the pinned sandbox-server source (`app_conversation_router.py`:
`_get_agent_server_context` L134, `_proxy_git_runtime_call` L1224, `headers={'X-Session-API-Key':
ctx.session_api_key}` L727/L827/L1258). ✅

---

## 3. Additional investigation A — `ImageContent` (task §4)

Sources: SDK `llm/message.py` (sha256 `1b9f0693…`), live Cloud OpenAPI, GUI
`send-message-with-attachments.ts` / `convert-image-to-base-64.ts` / `chat-input.utils.ts`.

| # | Question | Answer | Evidence |
| --- | --- | --- | --- |
| 1 | Exact `ImageContent` schema | `{type:"image", image_urls: list[str], cache_prompt: bool=false}`; `image_urls` required | SDK `message.py` L208-217; live Cloud `components.schemas.ImageContent` (identical) |
| 2 | Binary file upload? | **NO** — carries **image URLs** only, not arbitrary bytes/files | same |
| 3 | How image data is represented/transmitted | **data URLs** (`data:image/png;base64,…`), produced by `FileReader.readAsDataURL`; SDK annotation `PreserveDataUrls()` keeps them for the LLM | `convert-image-to-base-64.ts`; SDK `message.py` L210 |
| 4 | Non-image files? | **NO** — non-image files are uploaded separately to the workspace; only images may be embedded, and even images can be *marked to upload as files* instead | `send-message-with-attachments.ts`; `partitionImagesForUpload` (chat-input.utils.ts L35-52) |
| 5 | Size/count constraints | **client-side only**: 3 MB per image + 3 MB total across all attachments (images + files); server enforces none | `file-validation.ts` (`MAX_FILE_SIZE`/`MAX_TOTAL_SIZE` = 3·1024·1024) |
| 6 | Attached to the exact existing conversation? | **YES** — `POST /api/v1/app-conversations/{id}/send-message` | live Cloud OpenAPI |
| 7 | Persists as attachment, or embedded in message? | **UNVERIFIED** — it becomes message `content` (`image_urls`); whether the agent server persists the image as a workspace file vs only as message content is **not** established by the source reviewed | SDK `Message.content`; GUI embeds via `content.push({type:"image", image_urls})` |
| 8 | Durable op id / reconciliation? | **NO** — `send-message` returns `AppSendMessageResponse`; no operation id / status endpoint | live Cloud OpenAPI |
| 9 | Satisfies P0 multi-file + 15-min batching? | **NO** — images only (no arbitrary files), no durable batch/op state, no reconciliation, no idempotency | combined |

**Conclusion:** `ImageContent` is **not** an alternative for P0 (general multi-file attachments to an
existing conversation). It is, at most, a narrow future feature for **images only**. r2's §4 row #5
already states this; the row is **accurate**, with the refinement that the *reachability* of the path
via the Cloud bearer is confirmed (the Cloud proxies `send-message` server-side — see R2-2), while
only the persistence semantics remain UNVERIFIED.

---

## 4. Additional investigation B — live Cloud / checked-out source mismatch (task §5)

**Finding R2-1 (MEDIUM — provenance, informational):** r2's §2.2 note attributes `GET …/{id}/files`
to *"a newer Cloud build than the pinned SHA."* The root cause is now determined:

- The route is `list_conversation_files` in
  **`OpenHands/enterprise`** `openhands/app_server/app_conversation/app_conversation_router.py`
  (sha256 `c43ed4f7…`), decorated `@router.get('/{conversation_id}/files')` (L1725), with the exact
  live description ("List every regular file under a conversation workspace directory… makes the
  runtime hop server-side using the sandbox's session API key"). GitHub code search for the live
  description/operationId returns **`OpenHands/enterprise`** as the only backend match.
- The `enterprise` router is a **superset** of the pinned `sandbox-server` router: it adds `/files`,
  `/skills`, `/hooks`, `switch_acp_model`, `switch_profile`, `stream-start`, `start-tasks*` — and the
  live Cloud path set (242 paths) matches this superset.
- Therefore the live Cloud V1 API is served by **`OpenHands/enterprise`**, not the pinned
  `OpenHands/sandbox-server`. The proposal's provenance statement is imprecise ("newer build of the
  same repo" vs "a different (public) repo").
- **Effect on other claims:** none. `enterprise` exposes **no** upload/multipart/attachments route
  (verified: no `UploadFile`, no `multipart`; its `/files` is a read-only `GET`). The "Cloud has no
  upload" conclusion (§1, §2.2, §3) **holds**.
- **Required correction (low-risk, accuracy):** cite `OpenHands/enterprise` as the Cloud API source
  in §2.2/§11, and phrase the mismatch as "served by a different (newer) repo" rather than "newer
  build of the pinned repo."

Sub-answers to task §5: belongs to a **different service/repo** (`OpenHands/enterprise`), **not**
`OpenHands/sandbox-server`; Cloud **has** a newer implementation deployed; the route is **generated**
by the enterprise FastAPI app (not an external proxy); it is **read-only** (`GET`); the mismatch
**does not** affect any other r2 claim.

---

## 5. Security design challenge (task §6)

The recommended design (Cloud-hosted, conversation-bound scoped op + status endpoint) is a **sound and
near-minimal** upstream change; it reuses the existing binding/containment and adds exactly the
missing four controls.

- **Confused deputy / credential exposure:** resolved — the caller uses its **Cloud bearer**; the
  sandbox `session_api_key` stays server-side (`_get_agent_server_context`). §7.2 correctly requires
  the internal store call to be unreachable by a caller-held session key. ✅
- **TOCTOU / symlink:** §5.7 + §7.4 require `O_NOFOLLOW` + `O_CREAT|O_EXCL`; correct, because the
  existing route only `resolve()`s at check time (§3 of this review). ✅
- **Cross-user / cross-conversation:** §6 T-02/T-03 + §5.3 ownership binding; consistent with the
  existing `UserContext` / user-scoped `AppConversationService` pattern. ✅
- **Replay:** §5.6 `Idempotency-Key` + `sha256` dedup. ✅
- **SSRF:** eliminated by removing the bot→runtime hop (§6 T-04). ✅
- **R2-6 (MEDIUM — under-specification):** the **"consumed"** transition (§5.9/§5.10: *"the
  conversation consumes them (the `stored_path_ref` is referenced by a follow-up message)"*) is not
  observable as specified. The proposal does not define **how** the server detects that a
  `stored_path_ref` was referenced (the reference is prompt **path text**, §2.5), nor the timing/
  race between consumption-detection and the retention sweep. Required: define the consumption
  signal (e.g. an explicit `POST …/attachments/{op}/consume`, or a documented message-scan rule) and
  the resulting state transition.
- **R2-7 (LOW — placement):** §5.7 stages files **inside the conversation workspace**
  (`{conversation_workspace}/.oh-attachments/…`). Staged-but-unconsumed files are then visible to the
  agent and to the read-only `/files` listing, and (in a git workspace) appear as untracked files.
  Not a security flaw, but worth an explicit note (visibility + eventual cleanup).

---

## 6. P0 compatibility matrix (task §7)

Evaluates the **proposed upstream contract** against each P0 requirement. "Contract" = whether the
API design supports it; "owner" = who implements it (OpenHandBot side is out of scope here).

| P0 requirement | Supported by the proposed contract? | Where |
| --- | --- | --- |
| Fixed 15-minute deadline from the **first** file | Yes — `expires_at` returned at accept; `T0` is client-side (I4) | §5.5, §5.10, §8.1 I4 |
| Multiple files in one batch | Yes — repeatable `file` part up to `max_files` | §5.4, §5.7 |
| Additional files do not extend the deadline | Yes — client invariant; server `expires_at` is per-op | §8.1 I6 |
| Accompanying text required | Yes — files alone never dispatch (client invariant) | §8.1 I7/I8 |
| Same existing conversation | Yes — op bound to one `conversation_id` | §5.2, §5.3 |
| No new-conversation fallback | Yes — no create path in the contract | §8.1 I1 |
| Durable pending batches | Yes — durable op rows + local batch rows | §5.6, §7.5, §8.1 I5 |
| Process-restart recovery | Yes — durable state; status endpoint | §5.9, §7.5, §8.1 S10 |
| Unknown outcome preserves files | Yes — non-terminal states preserved until resolved | §5.9, §8.1 I10 |
| No blind retry | Yes — query status, never re-POST bytes | §5.6, §5.9, §8.1 I11 |
| Cleanup only after confirmed terminal outcome | Yes — server-driven sweep; delete on `stored`+consumed or `expired` | §5.10, §8.1 I12 |
| Existing Telegram acknowledgement guarantees | Yes — unchanged handlers/outbox | §8.1 I13 |

**Missing / underspecified contract items (mapped to findings):**
- **Consumption signal** for the `stored → consumed` transition (R2-6, MEDIUM).
- **`expires_at` not present in the §5.9 status schema** (present in §5.5) — minor schema
  inconsistency (R2-8, LOW).
- **`uploading` state** is listed (§5.5/§5.9) but a single-request multipart create that returns
  "only after the server has durably accepted" makes `uploading` effectively unobservable — clarify
  whether it is reachable (R2-9, LOW).

No **P0 requirement is contradicted** by the design; the gaps are specification detail, not design
flaws.

---

## 7. Findings (ranked)

| ID | Severity | Section | Evidence | Impact | Required correction |
| --- | --- | --- | --- | --- | --- |
| **R2-1** | MEDIUM | §2.2, §11 | `/files` route found in `OpenHands/enterprise` (sha256 `c43ed4f7…`), a superset of pinned `sandbox-server` (`864bff55…`); live Cloud 242 paths match enterprise | Provenance statement imprecise; no security impact; "no upload" conclusion holds | Cite `OpenHands/enterprise` as the Cloud API source; say "different (newer) repo", not "newer build of pinned repo" |
| **R2-2** | MEDIUM | §2.2, §4 | Cloud `send-message` is a server-side runtime proxy (`send_message_to_conversation`, thin proxy) | Strengthens §7.0 reuse; makes the `ImageContent` path's *reachability* confirmed via the Cloud bearer | Note that `send-message` already performs the server→runtime hop with the sandbox key; state ImageContent reachability as confirmed, persistence UNVERIFIED |
| **R2-3** | INFO | §2.2 | form-urlencoded ops = the 5 `/oauth/*` routes | — | None (verified correct) |
| **R2-4** | LOW | §2.5, §11 | `OpenHands/enterprise/frontend` `v1-conversation-service.api.ts` posts to legacy `/api/file/upload?path=…` | "official clients use the scoped route" is not universal | Qualify: the current GUI uses the scoped route; the enterprise V1 client still targets the legacy route |
| **R2-5** | LOW | §2.3.1 | `api.py` L647-658 mounts `file_router` under `/api` with the session-key dep | — | None (verified correct) |
| **R2-6** | MEDIUM | §5.9, §5.10 | "consumed" is defined only as "the `stored_path_ref` is referenced by a follow-up message"; reference is prompt path text (§2.5) | Consumption transition is not observable ⇒ retention/cleanup semantics ambiguous | Define the consumption signal + state transition + race handling vs the sweep |
| **R2-7** | LOW | §5.7 | staging under `{workspace}/.oh-attachments/…` | Staged files visible to agent + `/files`; untracked in git | Add an explicit visibility/cleanup note |
| **R2-8** | LOW | §5.5 vs §5.9 | `expires_at` in create response, absent in status schema | Minor schema inconsistency | Add `expires_at` to the status schema |
| **R2-9** | LOW | §5.5, §5.9 | `uploading` state vs "create returns only after durable accept" | `uploading` may be unreachable | Clarify reachability of `uploading` |

**Strengths preserved (no change needed):** the threat model (§6) T-01/T-02/T-03/T-05/T-08/T-12/T-14
rows; the §8 invariants I1–I13; the §5.7 "PROVISIONAL" labelling and internal-consistency flag; the
§10.1 "must stay green" regression note; the §12 open questions.

---

## 8. Honest limitations of this review

- **UNVERIFIED (provenance of `/files` beyond the route set):** I did not deploy or read a
  Cloud-runtime artifact; the `OpenHands/enterprise` attribution is established from the repo's public
  `main` router + live-OpenAPI route/description/operationId match, not from the live deployment's
  exact commit SHA. The exact deployed revision of `enterprise` is unknown.
- **UNVERIFIED (ImageContent persistence):** whether the agent server persists an embedded image as a
  workspace file is not established by the source reviewed (finding §3 row 7).
- **UNVERIFIED (generated spec):** I did not run `create_app().openapi()` locally (dependencies not
  installed); the scoped route's presence is established from source + tests, as in r1.
- **Not assessed:** OpenHandBot-side integration code (the proposal is upstream-design only) and the
  concrete 15-minute deadline mechanism beyond confirming the contract supports it.
- **No production call, no credential, no secret access** were used at any point.

---

## 9. Deliverable and compliance

- **Review document:** `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R2-INDEPENDENT-REVIEW.md` (this
  file).
- **Proposal untouched:** `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md` was
  **read only** (no edits).
- **r1 review untouched:** `docs/reviews/OHB2-P0-SECURE-UPLOAD-UPSTREAM-PROPOSAL-INDEPENDENT-ADVERSARIAL-REVIEW.md`
  was **read only**.
- **No code/tests/schema/runtime change; no upstream issue; no maintainer contact; no production
  call; no commit/push/PR/merge/deploy.**
- **P0 is NOT implemented** and this review does not claim otherwise.
