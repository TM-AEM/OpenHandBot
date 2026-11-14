# OHB2-P0-SECURE-UPLOAD-UPSTREAM-PROPOSAL — INDEPENDENT ADVERSARIAL REVIEW

Reviewer: fresh-context independent adversarial reviewer; **not** the author of the proposal under
review (`docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md`). All actions were
read-only: public specs and public source re-fetched independently, no production call, no
credential, no secret access, no file modification, no commit/push/PR/merge/deploy.

- Target: `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md` (untracked).
- Baseline: branch `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW`; HEAD `907b20de3fa6627795c14f29677e9f39c68e82f4`; `origin/main` `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c`.
- All evidence re-derived from primary sources; hashes recorded in §6.

## Verdict: **PASS_WITH_MAJOR_FINDINGS — REVISION REQUIRED BEFORE ACTING ON §5/§7**

The proposal's *problem framing* (P0 cannot be built safely with the current broad key; the gap is
authorization + destination resolution + filesystem safety + reconciliation; a Cloud-hosted scoped
operation is the right shape) is **sound and largely confirmed**. Its *capability audit* is
**materially incomplete**: it misses an **already-existing conversation-scoped, workspace-confined
upload route** on the Agent Server, and consequently (a) overstates two of its four gap columns,
(b) mis-states the route shape of the endpoint it cites, and (c) proposes building confinement that
already exists. The recommended design is still reasonable, but its justification and its §7.1
"add a confined endpoint" plan must be corrected. No security claim in §6 was found to be *false* in
direction; one evidence row (§2.1, docs export) is stale and internally inconsistent with the
proposal's own prose.

Severity summary: **1 MAJOR (design/evidence — missed existing confinement)**, **1 MAJOR
(evidence provenance — stale spec + route-shape mismatch)**, **2 MODERATE (overstated gap table;
understated existing proxy surface)**, plus LOW/INFO.

---

## 1. What the proposal claims (recap, for adjudication)

| # | Claim (paraphrased) | Proposal location |
| --- | --- | --- |
| C1 | Cloud V1 has **no** upload; file routes read-only; `send-message` = `anyOf[TextContent,ImageContent]` | §2.2, §3 |
| C2 | Agent Server's **only** upload is `POST /api/file/upload`; `securitySchemes = {}` | §2.3 |
| C3 | Upload handler `_upload_file` has **no** `resolve()`/`is_relative_to(workspace)` confinement, **no** symlink guard, **no** size/type limit | §2.3, §3(C), §7.4 |
| C4 | One server-wide `X-Session-API-Key` guards upload **and** `execute_bash_command`; **no** upload-scoped credential exists | §2.3, §5.1 |
| C5 | `conversation_url` origin is infrastructure-dependent ⇒ **no** stable trusted-origin allowlist | §2.4 |
| C6 | The GUI already uploads attachments with the broad key via `api_prefix` = `/api` **or** `/api/conversations/{runtime_conversation_id}` | §2.5 |
| C7 | Cloud proxies only **two** runtime calls (`git/changes`, `git/diff`) | §2.2 |
| C8 | Required gap: narrow authz + trusted destination + FS safety + reconciliation, all **upstream** | §3, §4 |
| C9 | Recommended: Cloud-hosted scoped upload op + status endpoint (approach #1) | §4, §5, §7 |

---

## 2. Adjudication of each claim (independent re-derivation)

### C1 — Cloud V1 has no upload — **CONFIRMED [F]**
Re-fetched `https://app.all-hands.dev/openapi.json` (http 200, 888015 bytes, sha256
`0086b0b0ec727d36ef528e7228d36c9c93fc6c7f1049ee762e7176e27ff77916`). `info.version = 1.87.1`,
**242 paths**. Counts: `multipart` token = **0**; `format: binary` = **0**; paths containing
`attach` = **0**. Request-body content types present: `application/json` (81 ops) and
`application/x-www-form-urlencoded` (5 ops, all `/oauth/*` device/idp). File routes are read-only:
`GET …/{id}/file`, `GET …/{id}/files`, `GET …/{id}/download` (all `get`). `send-message` body =
`AppSendMessageRequest.content` = `array(anyOf[TextContent, ImageContent])`, `minItems: 1`.
✔ Claim holds exactly.

### C2 — Agent Server's only upload; empty securitySchemes — **CONFIRMED for the *published* spec; provenance caveat (see F2)**
Re-fetched `https://docs.openhands.dev/openapi/agent-sdk.json` (http 200, 402351 bytes, sha256
`e42da6536ef87c38c8c0be5d472b3c2d9a4c8283cad55b8c7b6579a425374a4d` — **identical to the prior
investigation's snapshot**). `OpenHands Agent Server 0.1.0`, **40 paths**; the only upload path is
`/api/file/upload/{path}`; `securitySchemes` absent (null); no top-level `security`. ✔ as stated.
**But see F2**: this export is **stale relative to the pinned source** and its route *shape*
disagrees with the source the proposal also cites.

### C3 — "No workspace confinement, no symlink guard" — **PARTIALLY WRONG [MAJOR]**
The proposal inspected `file_router.py` decorators only. At the pinned SHA
`9f7d5cb11b1256c1878f5584a657401feca9ad16` (`file_router.py` sha256
`13f0cae7c5567028e06576e94b7b9d1707c00ced6098b611ba086c023b74cb95`):

- `runtime_router.py` (sha256 `5bea70f0bf69d8bff24aac9ffd9e791d1e2024a9f7a95cad6d1c3eb714ec9029`)
  line 77 `create_runtime_router()` builds a router with
  `prefix="/conversations/{runtime_conversation_id}"` (line 79) and
  `dependencies=[Depends(bind_local_conversation_runtime)]` (line 81), then `include_router(file_router)`
  (line 85) — plus `bash_router`, `runtime_git_router`, `vscode`.
- `bind_local_conversation_runtime` (line 31) **enforces workspace confinement**:
  for each of `("path", "workspace_dir")` it rejects with **422** unless
  `Path(requested_path).is_absolute()` **and**
  `Path(requested_path).resolve().is_relative_to(workspace_root)` (lines 44–51). It also validates
  `cwd`/`workspace_dir` and the trajectory conversation id.
- `conversation_registry.py` line 47 `add_execution_routes` mounts `create_runtime_router()`; `api.py`
  line 649 calls it under `api_router` (prefix `/api`, auth deps at line 647).

⇒ The **scoped** route `POST /api/conversations/{runtime_conversation_id}/file/upload?path=…` is
**conversation-bound and workspace-confined**, using exactly `resolve()` + `is_relative_to(workspace)`
— the mitigation the proposal says is absent (§2.3, §3(C), §7.4). Tests confirm the behavior:
`tests/agent_server/test_runtime_router.py` asserts cross-conversation file reads ⇒ 422, relative
path ⇒ 422, and upload-onto-directory / under-file ⇒ 400 (`test_local_runtime_workspace_and_terminal_context`,
`test_runtime_upload_onto_directory_or_under_file_is_400`).

**Fairness / what remains true:** the *legacy* route `POST /api/file/upload` (prefix `/api`) is
indeed **unconfined** — only `is_absolute()` (file_router.py `_upload_file`). Symlink hardening
(`O_NOFOLLOW`, TOCTOU between `resolve()` and `open()`) and **size/type/count limits** are genuinely
absent on *both* routes (verified: no size middleware in `middleware.py`; no size/type config in
`config.py`; `_upload_file` streams unbounded in 8 KiB chunks). So C3 is right about the *legacy*
route and about limits, but **wrong** to state that confinement does not exist at all — it exists on
the scoped route, which is the route the official clients actually use (see C6).

### C4 — one server-wide key; no upload-scoped credential — **CONFIRMED [F]**
`dependencies.py` (`check_session_api_key`) only checks `X-Session-API-Key ∈ config.session_api_keys`;
`config.py` sources them from `SESSION_API_KEY` / `OH_SESSION_API_KEYS_0`; `api.py` mounts one
`api_router` with that dependency over `file_router` **and** `bash_router`
(`POST /api/bash/execute_bash_command`), `git_router`, secrets, etc. The workspace-session **cookie**
is honored only by `check_workspace_session` on the workspace static-file router. ✔ Claim holds.

### C5 — no stable trusted-origin allowlist — **CONFIRMED [F]**
`live_status_app_conversation_service.py::_build_conversation` sets
`conversation_url = <AGENT_SERVER exposed_url> + "/api/conversations/{id.hex}"`;
`remote_sandbox_service.py::_to_sandbox_info` derives the AGENT_SERVER URL from `runtime['url']`, and
`_build_service_url` supports **path mode** and **subdomain mode**. The concrete host pattern is
deployment-dependent and undocumented. ✔ Claim holds.

### C6 — GUI uploads with the broad key via `api_prefix` — **CONFIRMED, and it strengthens the missed-route finding**
The proposal itself notes `api_prefix` may be `/api/conversations/{runtime_conversation_id}` (§2.5).
Independently confirmed in both clients:
- Python SDK `openhands-sdk/…/workspace/remote/remote_workspace_mixin.py`:
  `api_prefix` returns `f"/api/conversations/{self.runtime_conversation_id}"` when the runtime id is
  set; `file/upload` uses it.
- TS SDK `clients/typescript/src/client/runtime-transport.ts` (`ConversationScopedHttpClient`):
  rewrites `/api/file/upload` → `/api/conversations/{conversationId}/file/upload` **when the server
  advertises capability `conversation_runtime_routes_v1`** (default capability in
  `server_details_router.py` line 73). The GUI's `conversation-file-upload.api.ts` constructs a
  `RemoteWorkspace` whose runtime client is this scoped client.
⇒ The official GUI (cloud) uploads through the **scoped, confined** route, not the legacy unconfined
one. The proposal saw the scoped *prefix* but did not connect it to the confinement dependency in
`runtime_router.py`, which is the root of F1.

### C7 — Cloud proxies only two runtime calls — **PARTIALLY WRONG [MODERATE]**
The live Cloud spec exposes `GET …/{id}/file`, `GET …/{id}/files`, `GET …/{id}/download`,
`GET …/{id}/git/changes`, `GET …/{id}/git/diff` — and `/files` states it *"Mirrors the git-proxy
endpoints: browsers can't reach runtime sandboxes directly … the frontend hits this on the cloud API
host instead"*. So the server-side runtime-proxy surface is broader than two routes. The proposal's
recommended approach (#1) is therefore **more** consistent with existing patterns than it claims
("exactly as it already does for `GET …/git/changes`"). Minor accuracy issue; no security impact.

### C8 — the four required properties are upstream gaps — **PARTIALLY WRONG (see F3)**
Correct that all four need upstream work. Incorrect that **B** and **C** are "NO"/"mostly NO":
- **B (trusted destination):** server-side *confinement* to the conversation workspace already
  exists on the scoped route; what is still missing is server-side *destination resolution* (the
  client still supplies the absolute `path`, which must lie inside the workspace). ⇒ PARTIAL.
- **C (safe handling):** traversal/workspace-root containment **is** enforced (422) on the scoped
  route; symlink-at-target is partially handled by `resolve()` on the confinement check (TOCTOU
  remains). Missing: size/count/type limits and `O_NOFOLLOW` hardening. ⇒ PARTIAL, not "mostly NO".
- **A (narrow authz):** genuinely NO — the scoped route reuses the same server-wide key; it reduces
  *reach* to one workspace but does not remove command-exec reach. ✔
- **D (reconciliation):** genuinely NO. ✔

### C9 — recommended Cloud-hosted scoped op — **SOUND in shape; justification and plan need correction**
Removing the bot→runtime hop and using the caller's existing Cloud bearer is the right direction and
remains the best of the five options. **However** §7.1's instruction to *"Add a confined internal
store endpoint … not the current unconfined `/api/file/upload`"* (and §7.4's "add workspace-root
containment") **duplicates an existing upstream capability**. The plan should be restated as: reuse
the existing scoped route family (`/api/conversations/{runtime_conversation_id}/…`) and **add** the
genuinely-missing pieces — server-side destination resolution, size/count/type limits, a narrow
credential, operation id/status/idempotency, and symlink hardening.

---

## 3. Findings (ranked)

### F1 — MAJOR (design + evidence): missed an existing conversation-scoped, workspace-confined upload route
See §2/C3. Impact: the proposal's central "no confinement exists" premise is wrong; the gap table
(§3) and the upstream plan (§7.1/§7.4) overstate the required work and would duplicate an existing
mechanism. **Required fix:** add `runtime_router.py::create_runtime_router` /
`bind_local_conversation_runtime` to the inspected-source list; reclassify §3 B/C to PARTIAL;
restate §7.1 as "extend the existing scoped route family" rather than "add a confined endpoint".

### F2 — MAJOR (evidence provenance): the cited Agent Server spec is stale and its route shape contradicts the cited source
- The docs export `agent-sdk.json` (v0.1.0) is **stale relative to the pinned SHA**: it lacks the
  conversation-scoped runtime routes, `/api/auth/workspace-session`, and
  `/api/conversations/{conversation_id}/hooks`, and its `ServerInfo` has **no `capabilities`**
  property (main's does, including `conversation_runtime_routes_v1`).
- **Route-shape mismatch:** the export documents `POST /api/file/upload/{path}` with `path` **in the
  path**, but the pinned source defines `@file_router.post("/upload")` with `path` as a **`Query`**
  param (`upload_file_query`); no source decorator `upload/{path}` exists. The mismatch is **not** a
  version skew in the tags the proposal cites either: at `v1.58.1` and `v1.62.0` the decorator is
  also `@file_router.post("/upload")` (query form). The `/{path:path}` form is **older still**: it
  exists at `v1.10.0` (`@file_router.post("/upload/{path:path}")`) and was replaced by the query form
  by `v1.20.0`. So the published docs export reflects a **much older route shape** than both main and
  the cited tags — it matches neither.
- The proposal's §2.3 prose ("query `path`") contradicts its own §2.1 table row ("`POST /api/file/upload`"
  sourced to the export that shows `/{path}`). **Required fix:** cite the **source at the pinned
  SHA** as the authority for the upload contract; demote the docs export to "published snapshot,
  possibly stale" and reconcile the route form.

### F3 — MODERATE: §3 gap table overstates B/C
See §2/C8. **Required fix:** mark B and C as PARTIAL with the concrete split (confinement exists on
the scoped route; destination resolution, limits, and symlink hardening do not).

### F4 — MODERATE: §2.2 "only two runtime calls" understates the existing server-side proxy surface
See §2/C7. **Required fix:** enumerate `/file`, `/files`, `/download` as well; the recommendation's
"reuse the existing pattern" argument is stronger, not weaker, with the fuller list.

### F5 — LOW: pinned refs verified, but one date/attribution is loose
Independently confirmed all three pinned SHAs equal current `main` at review time
(software-agent-sdk `9f7d5cb1…`, OpenHands `a8aaf681…`, sandbox-server `43e91604…`). The proposal
labels the SDK/OpenHands pins "main, 2026-11-12" (correct) but the sandbox-server pin is undated and
its commit is from **2026-10-22**. Cosmetic.

### F6 — INFO: Cloud/agent-server security-scheme claims verified
Cloud `components.securitySchemes` = `{APIKeyHeader}` (no top-level `security`); agent-sdk export has
no `securitySchemes`/`security`. ✔

### F7 — INFO: strengths worth preserving
The proposal's threat model (§6) is well-structured and its T-01/T-02/T-03/T-05/T-08/T-12/T-14 rows
remain valid and relevant. The §8 integration invariants (I1–I13) correctly protect OpenHandBot's
existing P0 behavior (single SQLite owner, one bot process, fixed 15-min `T0`, durable batches,
tombstone/F-1 guard, no blind retry). The §12 open-questions list is appropriately explicit.

---

## 4. Does the recommendation still hold?

**Yes, with a corrected rationale.** A Cloud-hosted, caller-bearer-authenticated, conversation-bound
upload operation with a status/idempotency contract remains the best fit: it removes the bot→runtime
origin hop (C5), uses the existing Cloud ownership check, and gives reconciliation. The correction is
that the *filesystem-safety* half is **not** greenfield — the agent server already confines writes to
the conversation workspace on the scoped route. The upstream ask should therefore be **narrowed** to:
(1) a narrow credential distinct from the server-wide session key; (2) server-side destination
resolution; (3) size/count/type limits + symlink hardening; (4) operation id / status / idempotency.

---

## 5. Required revisions (actionable)

1. Add `runtime_router.py`, `conversation_registry.py` (and the SDK clients' `api_prefix` /
   `ConversationScopedHttpClient`) to §2.1's inspected sources.
2. Rewrite §2.3 and §3(B)(C) to state that a **conversation-scoped, workspace-confined** upload route
   exists (`POST /api/conversations/{runtime_conversation_id}/file/upload`), and separate the
   *legacy unconfined* `/api/file/upload` from it.
3. Fix the route-form inconsistency (§2.1 vs §2.3); cite the pinned **source** for the upload
   contract and mark the docs export as a possibly-stale snapshot.
4. Restate §7.1/§7.4: **extend** the existing scoped route family; add only the genuinely-missing
   controls (destination resolution, limits, narrow credential, operation semantics, symlink
   hardening).
5. Correct §2.2's "only two runtime calls" to include `/file`, `/files`, `/download`.

---

## 6. Independent evidence (commands + results)

All read-only, public sources, `/tmp` scratch removed after use. No credentials used.

| Source | Result |
| --- | --- |
| `curl https://app.all-hands.dev/openapi.json` | http 200, 888015 B, sha256 `0086b0b0…ff77916`; `1.87.1`, 242 paths; multipart 0; binary 0; attach 0 |
| `curl https://docs.openhands.dev/openapi/agent-sdk.json` | http 200, 402351 B, sha256 `e42da653…5374a4d`; 0.1.0, 40 paths; upload only `/api/file/upload/{path}`; no `securitySchemes`; no `capabilities`; missing scoped routes/hooks/workspace-session |
| `software-agent-sdk@9f7d5cb1…/file_router.py` | sha256 `13f0cae7…74cb95`; `file_router = APIRouter(prefix="/file")` (L75); `@file_router.post("/upload")` with `path: Query`, `file: UploadFile` (L742); `_upload_file` = `is_absolute()` only |
| `…/runtime_router.py` | sha256 `5bea70f0…ec9029`; `create_runtime_router()` prefix `/conversations/{runtime_conversation_id}` (L79), `dependencies=[Depends(bind_local_conversation_runtime)]` (L81), `include_router(file_router)` (L85); confinement `resolve().is_relative_to(workspace_root)` else 422 (L44–51) |
| `…/conversation_registry.py` | sha256 `4a479391…4ef36`; `add_execution_routes` → `create_runtime_router()` (L47) |
| `…/api.py` | api_router prefix `/api` with auth deps (L647); `add_execution_routes` (L649); `file_router` (L658) |
| `…/server_details_router.py` | default `capabilities` includes `conversation_runtime_routes_v1` (L73) |
| `…/tests/agent_server/test_runtime_router.py` | cross-conversation read ⇒ 422; relative path ⇒ 422; upload-onto-dir / under-file ⇒ 400 |
| SDK `remote_workspace_mixin.py` | `api_prefix` = `/api/conversations/{runtime_conversation_id}` when scoped |
| SDK TS `client/runtime-transport.ts` | `ConversationScopedHttpClient` rewrites to scoped route when `conversation_runtime_routes_v1` advertised |
| `software-agent-sdk` tags `v1.58.1`, `v1.62.0` | `@file_router.post("/upload")` (query form) — matches main, **not** the docs export |
| `software-agent-sdk` tags `v1.10.0` / `v1.20.0` | `v1.10.0`: `@file_router.post("/upload/{path:path}")` (path form); `v1.20.0`: `@file_router.post("/upload")` (query form) — explains the stale export's shape |
| GitHub commit metadata | pinned SHAs == current `main`: SDK `9f7d5cb1…` (2026-11-12), OpenHands `a8aaf681…` (2026-11-12), sandbox-server `43e91604…` (2026-10-22) |

---

## 7. Honest limitations of this review

- **UNVERIFIED:** I did not run `create_app().openapi()` (dependencies not installed here) to
  *generate* the scoped-route spec; the scoped routes' presence is established from source +
  tests, not from a live render. The docs-export staleness is inferred from the absence of routes
  that the pinned source demonstrably mounts.
- **UNVERIFIED:** the exact Cloud↔agent-server agent-server build in production may differ from the
  pinned SDK SHA; conclusions are relative to the pinned SHA, as in the proposal.
- I did not evaluate OpenHandBot-side integration code (the proposal is upstream-design only), and I
  did not assess the 15-minute deadline mechanism beyond noting it is preserved as an invariant.
