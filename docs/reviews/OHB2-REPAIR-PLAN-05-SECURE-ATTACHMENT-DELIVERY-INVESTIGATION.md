# OHB2-REPAIR-PLAN-05-SECURE-ATTACHMENT-DELIVERY — Gated Investigation Report

- **Plan ID:** `OHB2-REPAIR-PLAN-05-SECURE-ATTACHMENT-DELIVERY`
- **Task ID:** `OHB2-EXECUTE-PLAN-05-SECURE-ATTACHMENT-DELIVERY-GATED-INVESTIGATION`
- **Sub-task IDs:** `OHB2-UPLOAD-01-OFFICIAL-API-CAPABILITY-REVALIDATION`,
  `OHB2-UPLOAD-02-LEAST-PRIVILEGE-AND-TRUSTED-ORIGIN`,
  `OHB2-UPLOAD-03-STATE-MACHINE-AND-RECONCILIATION-DESIGN`,
  `OHB2-UPLOAD-04-REMOTE-DELIVERY-IMPLEMENTATION` (**NOT EXECUTED**)
- **Overall status:** **`BLOCKED`** — UPLOAD-01 passed (a supported upload endpoint exists), but
  **UPLOAD-02 failed**: no least-privilege upload credential exists, and no provider-committed,
  stable trusted origin for the agent-server endpoint can be established. UPLOAD-03 and UPLOAD-04
  were therefore **not reached** (correctly gated).
- **Type:** Investigation / design-only. **No runtime code, schema, dependency, config, or approved
  decision was changed.**
- **Author:** OpenHands agent (autonomous).
- **Date (retrieval):** 2026-11-15 (system date; primary sources retrieved `2026-11-15T11:21Z`).
- **Repo state when written:** branch `main`, HEAD `facf1f42578a20a4a37e220eca016ce3d534e750`
  (= `origin/main`); working tree **clean**.

> Evidence labels used below: **[F] fact** (verified from a primary source this session),
> **[I] inference**, **[U] unknown/unverified**, **[R] recommendation**. Facts and inferences are
> kept separate on purpose.

---

## 1. Task and plan IDs

See the header. This report executes the *investigation phases only* of
`OHB2-REPAIR-PLAN-05-SECURE-ATTACHMENT-DELIVERY`, in the mandated order UPLOAD-01 → UPLOAD-02 →
UPLOAD-03 → UPLOAD-04, stopping at the first failed gate. It does **not** implement remote
attachment upload or delivery.

## 2. Actual repository baseline and Git state

- **[F] Branch:** `main`. **HEAD:** `facf1f42578a20a4a37e220eca016ce3d534e750`.
  **`origin/main`:** same SHA. Divergence: `0 0`.
- **[F] `git status --short`:** empty (clean tree). **Staged:** none. **Untracked:** none.
- **[F] Ignored:** `.openhands/` (and caches `__pycache__/`, `.pytest_cache/`). `.openhands/` was
  **not** modified.
- **[F] Historical snapshot `02807b155e355f40352fe5e43967c58eea71162e`** is an **ancestor** of HEAD
  (`git merge-base --is-ancestor` → true), **5 commits behind** HEAD. It is *not* HEAD and *not* the
  current branch tip. It is the commit referenced by tags `ohb2-sync-backup-02807b1` and branch
  `agent/ohb2-repair-plan-01-resource-staging`.
- **[F] Recent history (top 5):** `facf1f4` (HEAD) → `9c8cf2e` → `4dbab4a` → `25ec46b` → `f6c0f24`
  → `02807b1`. Plan 01–04 work is committed and present.

### 2.1 Sources read before conclusions

- **[F]** `AGENTS.md` (full).
- **[F]** `docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md` — especially **§§16–27**
  (r2/r3/r5 re-validations; B1/B2 blockers; Option D deferral; reopen conditions).
- **[F]** `docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md` — decisions D-01…D-35.
- **[F]** Implementation: `bot/attachments.py`, `bot/db.py`, `bot/files.py`, `bot/outbox.py`,
  `bot/handlers.py`, `bot/openhands_client.py`.
- **[F]** Tests: `tests/test_attachment_*` (staging A1, batch lifecycle A2, intent A3, message
  identity A3, batch schema, terminal routing remediation, cleanup/expiration A4),
  `tests/test_unsupported_attachment_rejection.py`.
- **[F]** Reviews: `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R9-INDEPENDENT-ADVERSARIAL-REVIEW.md`
  (`NEEDS_REVISION`), `…R12-INDEPENDENT-ADVERSARIAL-REVIEW.md` (`PASS_WITH_NOTES`).
- **[F]** `automation/autopush/main.py` (pre-existing use of `X-Session-API-Key`; **Autopush remains
  disabled/inactive** and was not touched).

### 2.2 Relevant approved/protected decisions (unchanged by this investigation)

- **[F]** **D-09** — owner product decision: **proceed with P0** (attachment delivery) *if* a secure
  supported path exists.
- **[F]** **D-10** (ownership: Cloud V1 vs Agent Server) — **OPEN**. Recommendation A (Cloud V1) is
  `RECOMMENDATION — NOT OWNER-APPROVED`.
- **[F]** **D-11** (scoping: delegated Cloud path vs capability token) — **OPEN**.
- **[F]** **D-14** (delivery mechanism design A/B/C/D; whether to extend `send-message`) — **OPEN**.
- **[F]** **D-15** (`expires_at` = fixed 15 min, staging-only reclaim, no server-side batch) — **OPEN**.
- **[F]** **D-16** (`Idempotency-Key` + `sha256` dedup + delivery idempotency U-4) — **OPEN**.
- **[F]** **D-22** (outbox integration limit: new outbox item type vs another approved mechanism) —
  **OPEN**.
- **[F]** **D-32** (batch statuses that block the normal prompt at the A3↔B boundary) — **RESOLVED,
  OWNER-APPROVED**.
- **[F]** **D-34** (message routing "unproven association" → fail-closed `TERMINAL_UNPROVEN`) —
  **OWNER-APPROVED (policy)**; implementation outstanding in a separate task.
- **[F]** **D-35** (message-identity evidence retention, independent of `processed_updates`) —
  **RESOLVED, OWNER-APPROVED**.

> No decision record was edited. D-10/D-11/D-14/D-15/D-16/D-22 remain **OPEN**, exactly as before.

---

## 3. UPLOAD-01 — Official API capability revalidation

**Task ID:** `OHB2-UPLOAD-01-OFFICIAL-API-CAPABILITY-REVALIDATION`. **Result: PASS (candidate exists).**

### 3.1 Primary sources retrieved (this session, 2026-11-15T11:21Z; no credentials, no API operation)

| # | Source | Location | Version |
| --- | --- | --- | --- |
| S1 | OpenHands **Cloud V1** OpenAPI | `https://app.all-hands.dev/openapi.json` | `info.version = 1.92.0` (`title = OpenHands`), 257 paths |
| S2 | OpenHands **Agent Server** OpenAPI | `https://docs.openhands.dev/openapi/agent-sdk.json` | `info.version = 0.1.0` (`title = OpenHands Agent Server`), 40 paths |
| S3 | Agent Server **source** (`_upload_file`, router wiring, auth dependency) | `github.com/OpenHands/software-agent-sdk` @ `main` `2aae48b67a57fa852ebca946ac64ee8b8500e889` — `openhands-agent-server/openhands/agent_server/{file_router.py,api.py,dependencies.py}` | — |
| S4 | Agent Server **auth doc** | `https://docs.openhands.dev/sdk/arch/agent-server.md` | — |
| S5 | Cloud **origin construction** source | `github.com/OpenHands/enterprise` @ `main` `7e8551f753e6bcbcc9c00ae42c692583e00360d7` — `openhands/app_server/sandbox/remote_sandbox_service.py` | — |

### 3.2 Cloud V1 API (S1) — no upload path

- **[F]** Programmatic scan of the raw spec: token `"upload"` = **0**, `multipart` = **0**,
  `format: binary` = **0**, `FileContent` = **0**, `attachment` = **0**.
- **[F]** File routes are **read-only**: `GET /api/v1/app-conversations/{conversation_id}/file`,
  `…/files`, `…/download`. No `POST`/`PUT`/`PATCH` file route.
- **[F]** `POST /api/v1/app-conversations/{conversation_id}/send-message` body
  `AppSendMessageRequest.content` = array `anyOf[TextContent, ImageContent]`, `minItems: 1`.
  `ImageContent = {type:"image", image_urls: [string]}`; `TextContent = {type:"text", text}`.
  **No generic file/attachment content type.** (Unchanged from the proposal's V3.)
- **[F]** `AppConversation` exposes `conversation_url` ("The URL where the conversation may be
  accessed"), `session_api_key` ("The Session Api Key for REST operations."), `sandbox_id`.
- **[F]** Cloud `securitySchemes` = `{APIKeyHeader: {type: apiKey, in: header, name: X-Access-Token}}`
  — i.e. the bot's existing **Bearer** cloud API key. No scoped/upload token is documented.

### 3.3 Agent Server API (S2) — the only upload endpoint

- **[F]** The **only** upload-capable operation across all 40 paths is
  `POST /api/file/upload/{path}` (`operationId upload_file_api_file_upload__path__post`).
  - Path param `path` = "Absolute file path."
  - Request body `multipart/form-data`, field `file`, `format: binary` (required).
  - Response `200` → `Success` (`{success: boolean, default true}`); `422` on validation error.
  - **No** server-side size limit and **no** content-type/extension validation declared.
  - **No** idempotency key or dedup parameter.
  - **No** "list uploads"/"verify upload"/"stat file" endpoint in the spec (only `GET /api/file/download/{path}`).
- **[F]** Authentication: `components.securitySchemes` is **empty** in the spec and there is **no**
  global `security` — auth is enforced in code (see §3.4).
- **[F]** Adjacent privileged operations on the same router surface: `POST /api/bash/execute_bash_command`,
  `POST /api/conversations/{conversation_id}/secrets`, `POST /api/conversations` (create), etc.

### 3.4 Agent Server source (S3/S4) — confinement, size, auth

- **[F]** `file_router.py::_upload_file`: the **only** path check is
  `if not target_path.is_absolute(): raise Invalid("Path must be absolute")`. Then
  `target_path.parent.mkdir(parents=True, exist_ok=True)` **before** writing, and the body is
  streamed to disk in 8 KB chunks. **There is no `resolve()`/`is_relative_to(workspace)`
  confinement** ⇒ **any absolute path the sandbox user can write** is accepted (e.g.
  `/etc/cron.d/x`, `/home/*/.bashrc`, `/tmp/…`). **No server-side size limit** in the handler.
- **[F]** `api.py`: one `api_router = APIRouter(prefix="/api", dependencies=[Depends(require_initialized),
  Depends(check_session_api_key)])` mounts `file_router`, `bash_router`, `conversation_router`,
  `credential_binding_router`, `git_router`, `secrets`/settings, … ⇒ **one key guards everything**.
- **[F]** `dependencies.py::check_session_api_key`: reads header `X-Session-API-Key` and only checks
  membership in `config.session_api_keys` (else `Unauthenticated`). **No scope, no per-endpoint
  authorization.**
- **[F]** `bash_router.py::execute_bash_command` (`POST /api/bash/execute_bash_command`) is mounted on
  the same router ⇒ the same key grants **arbitrary command execution**.
- **[F]** Doc (S4): *"Do not expose an unauthenticated Agent Server on a public network. It can
  execute commands and read or write files in its configured workspace."* Clients "must send the
  session key in the `X-Session-API-Key` header".

### 3.5 Explicit distinctions (per task)

- **[F] General file upload vs text-message submission:** the only general file upload is the Agent
  Server `POST /api/file/upload/{path}`. Cloud `send-message` is a **text (+ image)** submission path,
  **not** a general file upload.
- **[F] General file upload vs image-only:** `ImageContent.image_urls: [string]` is an **image-only**
  channel. The OpenAPI does **not** document `data:`/base64 URL acceptance on the Cloud path, and
  does not accept arbitrary files. Not a substitute for "attached files".
- **[F] Official public API vs internal/SDK:** `POST /api/file/upload/{path}` **is** an official,
  documented Agent Server operation (in the published `agent-sdk.json`), not merely an SDK helper.
  No capability was inferred from an SDK method name.
- **[F] Documented vs assumed:** the endpoint, its multipart `file` field, and its `Success` response
  are documented. Its **lack** of confinement/size-limit is verified from **source**, and its
  **single-key** auth is verified from **source + doc**.

### 3.6 UPLOAD-01 gate decision

**[F] A plausible supported upload endpoint exists** (`POST /api/file/upload/{path}`, Agent Server
v0.1.0). Therefore UPLOAD-01 **PASSES** its gate ("if a plausible supported endpoint exists, proceed
to UPLOAD-02"). A plausible endpoint is **not** approval to use it.

> Note: Cloud V1 (v1.92.0) still offers **no** upload route, so **Option A (Cloud upload)** remains
> impossible; only **Option B (Agent Server upload)** is technically available, and only if
> UPLOAD-02 passes.

---

## 4. UPLOAD-02 — Least privilege and trusted origin

**Task ID:** `OHB2-UPLOAD-02-LEAST-PRIVILEGE-AND-TRUSTED-ORIGIN`. **Result: BLOCKED.**

### 4.A Credential privilege analysis

- **[F] No upload-only credential exists.** The only credential that authorizes
  `POST /api/file/upload/{path}` is the server-wide `X-Session-API-Key`
  (`config.session_api_keys`), and that **same** key authorizes `POST /api/bash/execute_bash_command`
  (command execution) and `POST /api/conversations/{conversation_id}/secrets` (secret management) on
  the identical router (§3.4). There is **no** documented scope, no per-endpoint authorization, and
  no restricted/upload-scoped key.
- **[F] The credential is server-wide, not workspace/conversation-scoped.** The Agent Server doc
  states the key is a server session key; membership is the only check.
- **[F] Privilege is therefore "full sandbox":** read/write files **and** execute commands in the
  configured workspace.
- **[U] Rotation/revocation:** the server reads `config.session_api_keys` (a list); the provider
  documents no rotation/revocation API for a single conversation's `session_api_key`. **[R]** Treat
  as "no independent revocation surface".
- **[F] Cloud issues the key per conversation** (`AppConversation.session_api_key`); the bot would
  have to read it from Cloud and hold it to upload.
- **[F] Precedent exists but does not change the privilege finding:** `automation/autopush/main.py`
  already uses `X-Session-API-Key` to read settings/secrets — but that is a **separate, currently
  inactive** automation, not a least-privilege upload credential, and it demonstrates the key's
  broad reach rather than narrowing it.

> **[F] Least-privilege verdict:** a server-wide key that enables **command execution** is **not**
> least privilege. Per the task, a general Agent Server key is **not** acceptable merely because the
> application *intends* to call only the upload endpoint. **BLOCKED (B1).**

### 4.B Trusted-origin and SSRF analysis

- **[F] The upload target origin is `conversation_url`, which is infrastructure-dependent and not
  documented as a stable host pattern.** Origin construction is verified in source (S5):
  `_to_sandbox_info` builds the `AGENT_SERVER` exposed URL as `url = runtime.get('url')`
  (`remote_sandbox_service.py`), and `_build_service_url(url, service_name, runtime_id)` yields
  **path-mode** `{scheme}://{netloc}/{runtime_id}/{service_name}` **or** **subdomain-mode**
  `{scheme}://{service_name}-{netloc}{path}` depending on the runtime URL's path. **[F] The concrete
  agent-server host therefore varies with deployment and is not a provider-committed, documented
  allowlist.**
- **[F] No stable origin allowlist is published** in any official doc or spec retrieved.
- **[F] Required SSRF controls that *are* technically enforceable** (and would not weaken existing
  behavior, since the repo already never follows redirects and never disables TLS):
  scheme `https` only; reject userinfo/odd ports; resolve DNS and reject loopback/private/link-local/
  ULA/CGNAT/multicast/reserved ranges; **pin the resolved IP** for the connection (DNS-rebinding
  guard); `follow_redirects=False` and treat 3xx as failure; require the expected path prefix; keep
  TLS + hostname verification on; ignore proxy env vars for this target.
- **[I] These controls are necessary but not sufficient:** "any `https` host + private-IP block" is
  exactly the weak hostname check the task **forbids**. A **strong** control needs an explicit
  allowlist of the actual agent-server origins (N2), which **does not exist in evidence**.
- **[F] Untrusted-field influence:** `conversation_url`/`session_api_key` come from Cloud responses;
  if Cloud (or anything upstream) returned an unexpected value, the bot would send
  `X-Session-API-Key` to that host — leaking a command-execution-capable key.
- **[F] Destination-change risk:** with a hostname-based check and no pinned IP, the destination can
  change between validation and connection (rebinding) — the pinned-IP control mitigates this but
  still does not make the *host* trusted.

> **[F] Trusted-origin verdict:** deterministic trusted-origin behavior is **not** established and
> the origin ambiguity is **unresolved**. Per the task, an unresolved origin ambiguity **remains a
> blocker**. **BLOCKED (B2).**

### 4.C Server-side upload controls

| Control | Finding (source-verified) | Enforced server-side? |
| --- | --- | --- |
| Workspace/path confinement | None — only `is_absolute()`; `mkdir(parents=True)` first | **No** |
| File-size limit | None in the upload handler; no body-size middleware in `api.py` | **No** |
| Filename/path-traversal protection | Caller supplies the absolute path; no normalization/confinement | **No** |
| Ownership / conversation binding | Not enforced at the endpoint (key is server-wide) | **No** |
| Content validation (type/magic bytes) | None declared | **No** |
| Response identity/location verification | Response is `Success{success}` only; no file id/location | **No** |
| Idempotency / dedup | None | **No** |

- **[F]** The bot would therefore be the **only** guard for confinement, size, type, and dedup —
  any bot bug becomes an arbitrary write in the sandbox. **[F]** There is no "verify upload" endpoint,
  so a lost response cannot be confirmed server-side (relevant to §5 ambiguity, had UPLOAD-03 been
  reached).

### 4.D UPLOAD-02 gate decision

**BLOCKED.** The only available credential enables **unrelated privileged operations** (command
execution, secret management), and the **trusted-origin** requirement is **unmet** (no documented,
stable, provider-controlled allowlist). Per the task's rules: mark the task **BLOCKED**, **do not
use that credential**, and **request a separate owner security/product decision**. Requirements were
**not** weakened to force a PASS.

---

## 5. UPLOAD-03 — State machine and reconciliation design

**Task ID:** `OHB2-UPLOAD-03-STATE-MACHINE-AND-RECONCILIATION-DESIGN`. **Result: NOT REACHED (gated).**

Per the mandated order, UPLOAD-03 runs **only if UPLOAD-01 and UPLOAD-02 pass**. UPLOAD-02 is
BLOCKED, so **no remote-delivery state machine is authored here** (authoring one would presuppose an
approved upload path that does not exist). For completeness and to keep the record honest, the
**existing local model** was mapped (below) so the future (blocked) design starts from verified
reality — but **no new state machine, transitions, or reconciliation design is proposed**.

### 5.A Actual existing model (verified from code/tests)

- **[F] Batch statuses** (`bot/db.py:110–137`): `pending`, `intent_recorded`, `dispatching`,
  `uncertain`, `delivered`, `expired`, `rejected`, `failed`.
- **[F] Actually produced today:** `pending` (on staging), `intent_recorded` (A3/D-27, when eligible
  text is stored), and `expired` (A4 reaper / on a later file arriving past T0+15m).
  **[F] `dispatching`, `uncertain`, `delivered`, `failed` have no transition logic** — they are
  schema placeholders ("مرحلة B"). **[F]** This matches D-32/D-34 wording that "terminal" states
  block the normal prompt via `TERMINAL_ASSOCIATED` / `TERMINAL_UNPROVEN`.
- **[F] Identity key** `(telegram_id, chat_id, message_id)` is the durable message↔batch evidence
  (`attachment_message_identity`, D-33/D-35), independent of `processed_updates`.
- **[F] Ownership:** `attachment_batches(telegram_id, conversation_id, t0, status, intent_text)`;
  `attachment_items(item_id, batch_id, staging_token, display_name, size_bytes, status)`.
- **[F] Outbox** (`bot/outbox.py`) sends **text only** (`client.send_message(conversation_id, text)`);
  no attachment payload type (matches D-22).
- **[F] Reaper** (`bot/attachments.py` `AttachmentReaper.sweep`) reclaims **staging only**, for
  **terminal** batches (`delivered/expired/rejected/failed`) plus orphan/temp cleanup; idempotent;
  never touches `attachment_message_identity` (D-35).
- **[F] Duplicate Telegram updates:** `processed_updates(update_id)` PK gives one-update→one-decision;
  repeats are recorded `duplicate_completed` (no exactly-once claim).
- **[F] Routing:** `classify_attachment_routing` returns `NONE` / `TERMINAL_ASSOCIATED` /
  `TERMINAL_UNPROVEN`; terminal batches **block** the normal prompt (D-34 fail-closed).
- **[F] Staging:** `StagingStore` (A1) + FIX-01…FIX-04 (streaming cap, bounded concurrency, quotas,
  fail-closed permissions) — preserved, unchanged.

### 5.B–5.D

Not produced. **[F]** UPLOAD-03 is correctly **not reached**; the required design and
ambiguous-outcome matrix are therefore **not** part of this report. The gating rule was honored
rather than bypassed.

---

## 6. UPLOAD-04 — Implementation gate

**Task ID:** `OHB2-UPLOAD-04-REMOTE-DELIVERY-IMPLEMENTATION`. **Result: NOT EXECUTED / NOT AUTHORIZED.**

- **[F]** No runtime code was changed; no upload client was added; no disabled upload path was
  enabled. The investigation **stopped before UPLOAD-04**.
- **[F]** Because UPLOAD-02 is BLOCKED, the technical preconditions are **not** satisfied, so even
  the conditional statement "preconditions appear satisfied" does **not** apply here.

---

## 7. Project invariants — preserved

- **[F]** One bot + ASGI process; **one** authoritative SQLite owner — unchanged.
- **[F]** Existing outbox/workers only — no new worker/scheduler.
- **[F]** No exactly-once Telegram delivery claims; duplicate-update protection intact
  (`processed_updates`).
- **[F]** Same authorized OpenHands conversation only; **no** fallback conversation creation; no
  repository-association change.
- **[F]** Local staging + safe rejection continue to work; no local bytes deleted on an unverified
  remote outcome (no remote outcome exists).
- **[F]** Fail-closed behavior intact; `MINI_APP_ENABLED` unchanged; Autopush remains disabled/inactive.
- **[F]** Plan 01–04 work preserved; **no** approved decision changed.

---

## 8. Gate-by-gate verdicts

| Gate | Verdict | Basis |
| --- | --- | --- |
| **UPLOAD-01** Official API capability | **PASS** (candidate endpoint exists) | §3 |
| **UPLOAD-02** Least privilege + trusted origin | **BLOCKED** | §4 (B1 no scoped credential; B2 no trusted origin) |
| **UPLOAD-03** State machine + reconciliation | **NOT REACHED** (gated) | §5 |
| **UPLOAD-04** Implementation | **NOT EXECUTED / NOT AUTHORIZED** | §6 |

---

## 9. Unresolved owner / architecture / security decisions

Each is **OPEN** and requires a **separate, explicit** owner decision. None is granted here.

1. **[F] D-10** — capability ownership: Cloud V1 (impossible today — no upload route) vs Agent Server
   (B1/B2 blockers). **Owner decision required.**
2. **[F] D-11** — scoping: delegated Cloud path vs capability token (TTL/binding/revocation).
   **Owner decision required.**
3. **[F] D-14** — delivery mechanism (design A/B/C/D; whether to extend `send-message`).
   **Owner decision required.**
4. **[F] D-15** — `expires_at` fixed 15 min, staging-only reclaim, no server-side batch. **Confirm.**
5. **[F] D-16** — `Idempotency-Key` + `sha256` dedup + U-4 (and optional message-level key U-6).
   **Owner decision required.**
6. **[F] D-22** — outbox integration (new item type vs another approved mechanism). **Owner decision
   required.**
7. **[R] Security (B1)** — an explicit product/security decision that a **full-privilege,
   command-execution-capable** agent-server credential is acceptable **for a file-write feature** —
   **or** an upstream **upload-scoped credential** with a documented scope. **Owner decision required.**
8. **[R] Security (B2)** — a **provider-committed, stable agent-server origin allowlist** (documented
   host pattern for `conversation_url`). **Owner decision required.** (Blocking; must not be replaced
   by a weak hostname check.)
9. **[R] Architecture** — approval for a second external target + second auth scheme + a new
   pending-batch table (departures from `bot/files.py:15` and `docs/plan-openhandBot-2.md` §4.1).
   **Owner decision required.**
10. **[R] Reconciliation** — a documented reconciliation path for an ambiguous upload outcome, **or**
    an explicit product acceptance of a permanent `uncertain` state (the server exposes no "verify
    upload" endpoint). **Owner decision required.**

---

## 10. Tests and checks actually performed

- **[F] Read-only static inspection only** — no runtime code changed, so no new tests were authored
  (per AGENTS.md, do not invent tests for a read-only investigation).
- **[F] Primary-source verification performed this session:**
  - `curl` of S1 (Cloud OpenAPI, 919,136 bytes) and S2 (Agent Server OpenAPI, 402,351 bytes); programmatic
    token/version counts (§3.2, §3.3).
  - `curl` of S3 source files from `OpenHands/software-agent-sdk` @ `2aae48b6…`; grep-verified
    `_upload_file` confinement and router/auth wiring (§3.4).
  - `curl` of S4 doc; grep-verified key scope wording.
  - `curl` of S5 source from `OpenHands/enterprise` @ `7e8551f7…`; verified `_build_service_url` /
    `exposed_urls` origin construction (§4.B).
- **[F] Repository checks used to ground the baseline:** `git rev-parse`, `git status --short`,
  `git merge-base --is-ancestor`, `grep` over `bot/` (first-party usage of
  `session_api_key`/`conversation_url`/`multipart`/upload). **No production API call** was made; **no
  credential** was used for any capability call.
- **[U] Not run:** the full pytest suite and linters were **not** run for this report, because **no
  code changed** (a pure read-only investigation). If the owner wants a green-suite confirmation for
  the unchanged tree, `python -m pytest -q` can be run separately (baseline for HEAD `facf1f4` is
  believed green from the prior synchronization session, but that is **[I]**, not re-verified here).

---

## 11. Final repository state

- **[F] Branch `main`, HEAD `facf1f42578a20a4a37e220eca016ce3d534e750` (= `origin/main`).**
- **[F] `git status --short`:** empty. Only this new report file was added
  (`docs/reviews/OHB2-REPAIR-PLAN-05-SECURE-ATTACHMENT-DELIVERY-INVESTIGATION.md`); no other file
  changed. **No commit, push, PR, merge, release, or deployment.**
- **[F] Autopush remains disabled/inactive; `MINI_APP_ENABLED` unchanged.**

---

## 12. Explicit statements

- **[F] UPLOAD-04 was NOT implemented and NOT authorized.**
- **[F] No remote attachment upload or delivery was implemented; no upload client was added; no
  disabled upload path was enabled.**
- **[F] No full-privilege Agent Server credential was used; no production credential/secret was used;
  no production OpenHands or Telegram API was called; no real user conversation/workspace was tested.**
- **[F] No approved architecture or product/security decision was changed; no new worker/scheduler/
  process/SQLite owner/external target/auth scheme/table/migration was added.**
- **[F] This report is evidence-based; facts, inferences, unknowns, and recommendations are labeled
  separately. This is a self-review-quality artifact, not an independent security review.**

---

## 13. Recommended next step (single item)

**[R]** Obtain a **single consolidated owner decision** covering: (a) the **B1** credential model
(accept the full-privilege key **or** provide an upload-scoped credential), and (b) the **B2**
provider-committed **agent-server origin allowlist**. Until **both** are granted **and** D-10/D-11/
D-14/D-15/D-16/D-22 are resolved, remote attachment delivery remains **BLOCKED** and the bot must
continue its current **safe rejection** of unsupported attachments (fail-closed).
