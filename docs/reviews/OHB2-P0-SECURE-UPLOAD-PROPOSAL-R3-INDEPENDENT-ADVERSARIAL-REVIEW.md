# OHB2-P0-SECURE-UPLOAD-PROPOSAL-R3 — INDEPENDENT ADVERSARIAL REVIEW

**Task ID:** `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R3-INDEPENDENT-ADVERSARIAL-REVIEW`

Reviewer: fresh-context independent adversarial reviewer; **not** the author of the proposal and
**not** the author of the r3 self-review. All actions were **read-only**: public specs and public
source re-fetched independently, **no production call, no credential, no secret access, no file
modification** (this review file is the only artifact created), no commit/push/PR/merge/deploy, no
upstream issue/PR/maintainer contact. The proposal, the self-review, and the previous reviews were
**not** modified.

## Verdict: **NEEDS_REVISION**

r3 is **evidence-accurate** (every re-derivable source fact checks out) and its **R2-1 … R2-9
corrections are mostly genuine**, but it is **not yet ready for owner approval** because the
`consumed` mechanism introduced to close R2-6 is **not implementable as written** and, more
importantly, the proposal never specifies **how an uploaded file becomes usable content the agent can
read** — the `stored_path_ref` is inert prompt text with no resolver. A second, independent hazard
(the Cloud-side consumption/cleanup ordering versus the bot's durable Telegram acknowledgement) is
unspecified. The exact corrections are in §9 below. **The required fixes are targeted documentation
changes; no new upstream evidence is needed (hence not BLOCKED), and the design direction remains
sound.** **P0 remains unimplemented.**

---

## 1. Baseline and file hashes

| Item | Value |
| --- | --- |
| Repository | `TM-AEM/OpenHandBot` |
| Branch | `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW` |
| HEAD | `907b20de3fa6627795c14f29677e9f39c68e82f4` |
| origin/main | `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c` |

**Working-tree status before review** (preserved; nothing reset/cleaned/deleted):

```
 M .agent/PROGRESS.md
 M bot/handlers.py
 M docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md
 M docs/proposals/OHB2-TELEGRAM-ACK-ARCHITECTURE-ADR.md
?? docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R2-INDEPENDENT-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R3-SELF-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-UPSTREAM-PROPOSAL-INDEPENDENT-ADVERSARIAL-REVIEW.md
?? tests/test_stage2_high_ack_blocking_fix.py
?? tests/test_stage4_f1_status_cost_operational_ack.py
```

**Artifacts under review (sha256, this session):**

| Artifact | Version | Lines | sha256 |
| --- | --- | --- | --- |
| `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md` | **r3** (header §"Date" + §13 row `r3`) | 1112 | `88fd400edd61cf4a6900bb2dea65cdefa95f791e3e7e2250344c2bd9a8537073` |
| `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R3-SELF-REVIEW.md` | r3 self-review (supporting evidence only) | 130 | `8b29fa19fbbb2735ef5b503d03d685d0ac344b8d87b930df4013407c0085cfc8` |
| `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R2-INDEPENDENT-REVIEW.md` | r2 review (`PASS_WITH_NOTES`) | 324 | `8d5153cae86526c653dac95b311974586523f546c2205261abdacab6009ab19e` |
| `docs/reviews/OHB2-P0-SECURE-UPLOAD-UPSTREAM-PROPOSAL-INDEPENDENT-ADVERSARIAL-REVIEW.md` | r1 review (`PASS_WITH_MAJOR_FINDINGS`) | 272 | `a9c858004858397ca2e5e1f3f077423d47e82a4763215b24bb85cb693e9e5728` |

**r3 identity confirmed:** header line 5 names task `…R3-FINDINGS-REMEDIATION`; line 8 dates "r3
2026-11-11"; §13 has three rows (r1/r2/r3); §42 carries the "r3 correction notice". **This review is
of r3** (not a stale r2 copy). The proposal is **untracked**, so its sha256 above is the only version
anchor.

---

## 2. Source repositories, revisions, and file hashes

Re-verified **this session** from retained evidence (`/tmp/r3`, `/tmp/up`, `/tmp/ss`, `/tmp/gui`,
`/tmp/r3v`) **and** by re-fetching central files from public raw source. Every re-derivable hash
**matches** the proposal's §11.

| Source | Identifier | File (sha256) | Verified |
| --- | --- | --- | --- |
| `OpenHands/software-agent-sdk` | `9f7d5cb11b1256c1878f5584a657401feca9ad16` (== main) | `file_router.py` `13f0cae7…` | ✅ re-fetched/retained |
| | | `runtime_router.py` `5bea70f0…` | ✅ **re-fetched this session** |
| | | `conversation_registry.py` `4a479391…` | ✅ **re-fetched this session** |
| | | `server_details_router.py` `2878f452…` | ✅ **re-fetched this session** |
| | | `api.py` `5de71d80…`, `dependencies.py` `f5f51362…`, `models.py` `57b3680c…`, `config.py` `0b064821…` | ✅ retained |
| | | `openhands-sdk/…/workspace/remote/remote_workspace_mixin.py` `0e55f7ab…` | ✅ retained |
| | tags `v1.58.1` / `v1.62.0` / main | `@file_router.post("/upload")` (query form) | ✅ confirmed |
| `OpenHands/sandbox-server` | `43e91604ccd0a9960c8d5c52faadd60b30f10e63` (== main) | `app_conversation_router.py` `864bff55…` | ✅ retained |
| | | `live_status_app_conversation_service.py` `9653dd3d…`, `remote_sandbox_service.py` `c523a807…`, `session_auth.py` `893d725e…` | ✅ retained |
| `OpenHands/enterprise` | `3fac53df8c2efcb67ff3537d1162e8c8a108f565` (== main, r3 time) | `app_conversation_router.py` `c43ed4f7…` | ✅ retained (`/files` at L1725, no upload) |
| | | `frontend/src/api/conversation-service/v1-conversation-service.api.ts` `0a0b80c6…` | ✅ retained (legacy `/api/file/upload?path=…`) |
| `OpenHands/OpenHands` | `a8aaf6813753803cae5182d050909705b0eb02d0` (== main) | GUI upload/validation files | ✅ retained |
| Live Cloud V1 OpenAPI | `app.all-hands.dev/openapi.json`, `1.87.1` | `0086b0b0…` | ✅ retained, parsed |

**Independently re-derived facts (not taken on trust):**

- **Cloud V1:** `info.version 1.87.1`, **242 paths**, `multipart`=0, `"binary"`=0, `attach`=8 (all
  observability "attach metadata" strings, **not** attachments). Request content types =
  `application/json` (81) + `application/x-www-form-urlencoded` (5). File routes all `GET`
  (`/file`, `/files`, `/download`); `/git/changes`, `/git/diff` are `GET` (in the spec under the
  conversation resource). `send-message` body = `AppSendMessageRequest.content` = array
  `anyOf[TextContent, ImageContent]`, `minItems: 1`. `AppConversation` has `conversation_url`,
  `session_api_key`, `sandbox_id`. **No** `attachments` path exists. ✅ all match the proposal.
- **Agent Server scoped route:** `runtime_router.py::create_runtime_router` prefix
  `/conversations/{runtime_conversation_id}`, `dependencies=[Depends(bind_local_conversation_runtime)]`;
  `bind_local_conversation_runtime` rejects **422** unless
  `Path(requested_path).is_absolute()` **and** `Path(requested_path).resolve().is_relative_to(workspace_root)`;
  docstring: *"these path checks are routing safeguards, not a sandbox for arbitrary shell commands."*
  ✅ verbatim match.
- **Auth:** `check_session_api_key` only checks membership in `config.session_api_keys` (401 otherwise);
  the same `api_router` dependency guards `file_router` **and** `bash_router`. `FileUploadResult(Success) =
  {success, file_size}`. ✅
- **Capability flag:** `server_details_router.py` default capabilities include
  `conversation_runtime_routes_v1`. ✅
- **Legacy route form:** `@file_router.post("/upload")` (query `path`) at main **and** `v1.58.1` /
  `v1.62.0`; `_upload_file` only checks `is_absolute()`. ✅
- **enterprise:** router is a superset (adds `/files`, `/skills`, `/hooks`, `switch_acp_model`,
  `switch_profile`, `stream-start`, `start-tasks*`); **no** upload/multipart route. ✅
- **`send-message` is a thin proxy (verified in enterprise source):** `send_message_to_conversation`
  does `httpx_client.post(f'{agent_server_url}/api/conversations/{conversation_id}/events', …,
  headers={'X-Session-API-Key': sandbox.session_api_key})` and returns
  `AppSendMessageResponse(success=True, sandbox_status=…)`. **It writes no durable Cloud state.** ✅
  (This fact is load-bearing for findings M-1/M-2/H-1 below.)

---

## 3. R2-1 … R2-9 verification table

For each: original issue · r3 correction · independent evidence · fully resolved? · new risk.

| Finding | Original issue | r3 correction | Independent evidence (this review) | Resolved? | New risk introduced |
| --- | --- | --- | --- | --- | --- |
| **R2-1** (MEDIUM) | `/files` mis-attributed to "a newer build of the pinned repo" | §2.1/§2.2/§11 cite `OpenHands/enterprise` as a **different (newer) repo**, a superset; "no Cloud upload" unaffected | enterprise `app_conversation_router.py` `c43ed4f7…` has `@router.get('/{conversation_id}/files')` (L1725) and **no** upload route; enterprise route set ⊇ live 242 paths | **YES** | None. (Deployed commit still unverifiable — correctly flagged §11(a).) |
| **R2-2** (MEDIUM) | send-message server-side hop not stated | §2.2/§4 note `send-message` already performs the hop; ImageContent reachable, persistence UNVERIFIED | enterprise `send_message_to_conversation` posts to agent-server `/events` with the sandbox key — **thin proxy, no durable write** | **YES (as documentation)** | Enables M-2: the R2-6 design then *assumes* the same proxy "durably accepts" a message, which it does not. |
| **R2-3** (INFO) | form-urlencoded ops | none | verified (5 ops) | n/a | None |
| **R2-4** (LOW) | "official clients use the scoped route" not universal | new §5.13: enterprise frontend still uses legacy `/api/file/upload?path=…`; coexist; not equivalent | enterprise `v1-conversation-service.api.ts` `0a0b80c6…` → `buildRuntimeUrl(conversationUrl, "/api/file/upload?…")` + `FormData` + `multipart/form-data` | **YES** | None (see L-4 note) |
| **R2-5** (INFO) | legacy mount | none | `api.py` mounts `file_router` under `/api` with `check_session_api_key`; `add_execution_routes(api_router)` | n/a | None |
| **R2-6** (MEDIUM) | `consumed` not observable | new §5.9.1: durable `consumed_at` marker owned by the Cloud attachment service, set when the Cloud `send-message` path **durably accepts** a message containing the op's `stored_path_ref` | §5.9.1 event/owner/meaning are now *defined*; **but** (a) the ref is inert **prompt text** (§2.5, §8.2 S7) with **no resolver** ⇒ H-1; (b) the verified `send-message` is a **thin proxy with no durable write** ⇒ M-2; (c) ordering vs the bot's Telegram ack unspecified ⇒ M-1; (d) cleanup-vs-agent-read race ⇒ M-3 | **PARTIAL** | **HIGH** (H-1) + MEDIUM (M-1/M-2/M-3) |
| **R2-7** (LOW) | staging visibility | §5.7 note: staged files visible to agent/`/files`, untracked in git; bounded by TTL/sweep | storage under `{workspace}/.oh-attachments/{op}/{file_id}` (§5.7) | **YES** | None |
| **R2-8** (LOW) | `expires_at` absent from status schema | §5.9 schema + semantics (UTC ISO-8601, fixed at accept, never extended, derive-on-read) | schema present; consistent with §5.5 | **YES** | M-5 (per-op vs batch deadline), L-1/L-3 |
| **R2-9** (LOW) | `uploading` unreachable | §5.5/§5.9: removed; declared model = `accepted` / `stored` / `rejected` / `failed` / `expired`; re-intro gated (Q13) | removal is sound given synchronous staging | **YES for `uploading`** | **M-4:** the same reasoning exposes `rejected` reachability (a reject may occur before an op id exists ⇒ unobservable) |

**Net:** R2-1, R2-2 (as documentation), R2-3, R2-4, R2-5, R2-7, R2-8, R2-9(`uploading`) are
**resolved**; **R2-6 is only partially resolved** and is the principal driver of the verdict.

---

## 4. Crash-window analysis for `consumed`

The r3 self-review asserts the crash windows are "closed" by prose ("the marker write failing fails
the message-accept"; "durable before the response"). I traced the **ordering of durable operations**
against the verified source and the proposal's own invariants. The following windows are **not**
closed by the r3 text.

**Context (verified):** the Cloud `send-message` handler is a **thin proxy** — it forwards to the
agent-server and returns `{success, sandbox_status}` with **no durable Cloud write**. Therefore any
"durable acceptance" that §5.9.1 relies on is **new work not yet specified**, and the marker cannot
currently be "part of the same durable step as accepting the message".

- **CW-1 — consumption/cleanup runs ahead of the bot's Telegram ack (batch loss / duplicate).**
  Sequence: bot sends `send-message` (text + ref) → Cloud proxies it to the agent-server (**the agent
  now has the message and may start work**) and marks `consumed_at` → the bot **crashes before** it
  durably records local success. On restart the bot sees the batch as `dispatching` (§8.2 S10) and
  **re-sends**. If the ref is still valid ⇒ **duplicate message to the agent** (send-message has no
  idempotency). If the op has meanwhile expired and the sweep reclaimed the bytes ⇒ the re-send is
  rejected (stale ref) and **the user's prompt is never delivered, while the file is gone**. §5.9.1
  never ties `consumed_at` (or cleanup) to the bot's **durable Telegram acknowledgement** (I13).
  **Hazard: MEDIUM.**
- **CW-2 — false success / lost prompt via proxy 502.** Sequence: bot sends `send-message` → Cloud
  proxies → agent-server **received** it → Cloud's `response.raise_for_status()` throws (agent-server
  error) → Cloud returns **502** → bot treats as uncertain. The message **was** delivered, but the
  bot cannot tell; it may re-send (duplicate) or, if it treats 502 as terminal failure, notify the
  user of failure although the prompt arrived. §5.9.1 addresses only *upload* ambiguity, not
  *message* ambiguity, and send-message has no idempotency key. **Hazard: LOW–MEDIUM.**
- **CW-3 — crash between `stored` and persisting `operation_id`.** §8.2 S4/S5 say the bot creates the
  op and then persists `operation_id`. If the bot crashes **after** the create but **before**
  persisting the id, it has a local batch with **no** `operation_id` and cannot query status. The
  create is idempotent **only if** the `Idempotency-Key` was persisted **before** the call — §8.2 S4
  does not state that ordering. Without it, the retry creates a **second operation** (duplicate
  staged bytes). **Hazard: LOW–MEDIUM.**
- **CW-4 — crash after `consumed_at` set, before the agent reads.** `consumed_at` is set at
  message-**accept** (a proxy call), but the agent reads the file **asynchronously**. If cleanup is
  keyed on `stored`+`consumed`, the sweep can delete the bytes **while the agent is reading**. §5.10
  keys cleanup on "`stored`+consumed" without requiring proof the agent actually consumed the file.
  **Hazard: MEDIUM** (see M-3).
- **CW-5 — `accepted` row stranded by a mid-staging crash.** A crash during synchronous staging
  leaves the row `accepted` with partial bytes until `expires_at` (≤ 15 min). Derive-on-read makes
  status eventually report `expired`, so it is **bounded and safe**, but partial bytes linger up to
  15 min and the proposal does not state that a `failed`/`expired` transition cleans partial
  staging. **Hazard: LOW** (L-2).

**Conclusion:** the self-review's "closed" verdicts hold only **for the upload path**; the
**message/consumption path** (CW-1/CW-2/CW-4) is not ordered against the bot's durable ack and is
**not** closed by the r3 text.

---

## 5. State-machine and expiry analysis

### 5.1 State machine (R2-9)

For each declared state: entry event · owner · durable persistence · observable status · restart
behavior · terminal? · cleanup-eligible?

| State | Entry event | Owner | Durable | Observable | Restart | Terminal | Cleanup-eligible |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `accepted` | create request durably persists the row | Cloud attachment service | yes (row) | yes (status) | survives; if past `expires_at` ⇒ derives `expired` | no | no (§5.10) |
| `stored` | staging completes | Cloud attachment service | yes | yes | survives | yes | **only** with `consumed_at ≠ null` |
| `rejected` | validation/policy refuse | Cloud attachment service | **ambiguous (M-4)** | **ambiguous (M-4)** | n/a | yes | yes |
| `failed` | staging error after accept | Cloud attachment service | yes | yes | survives | yes | yes |
| `expired` | `expires_at` passes without consume | Cloud attachment service / derive-on-read | yes | yes | survives | yes | yes |

- **No missing state / ambiguous transition** for the happy path; removing `uploading` is **sound**
  given synchronous staging.
- **M-4 (MEDIUM):** `rejected` is listed as a state, but the §5.5/§5.6 contract issues an
  `operation_id` **only on durable accept**. A validation failure (413/415/422 per §5.8) plausibly
  occurs **before** an op exists, so a client may have **no id to query** — making `rejected`
  unobservable, i.e. the *same class of defect* R2-9 removed for `uploading`. The proposal must state
  whether a durable operation row is created on reject (so it is queryable) or not (so `rejected` is
  not an observable state).
- **M-5 (MEDIUM):** server-side `expires_at` is **per operation**. Multi-file batching is expressed
  either as multiple parts in **one** create (one op ⇒ one `expires_at`) or as **multiple creates**
  (multiple ops ⇒ **multiple independent `expires_at` values**). The P0 invariant "the deadline is
  fixed from the **first** file and never extends" (I4/I6) is therefore a **client-side** rule that
  the server **cannot enforce** and that the contract does not model as a batch. This must be stated
  explicitly (the proposal implies it via I4 but never says the server has no batch concept).

### 5.2 Expiry (R2-8)

- **In the contract?** Yes — `expires_at` is now in the §5.9 status schema. **Unambiguous?** Mostly:
  UTC ISO-8601, `= created_at + 15 min`, fixed at accept, never moved.
- **Computed vs persisted:** the r3 rule is **derive-on-read** ("status read derives `expired` from
  `expires_at` for any non-terminal row whose `expires_at` has passed"). `expires_at` itself is
  persisted at accept. **Restart-safe:** yes (persisted value). **Clock-change safe:** mostly — but
  the rule mixes **server** time (derivation) and **client** time ("the client must never observe
  `accepted` after its own clock is past `expires_at`"), which can disagree; the client must not rely
  on its own clock to *conclude* expiry (**L-3**, LOW).
- **Can more files extend it?** Within one op: no (stated). Across multiple ops: each op has its own
  `expires_at` — see M-5.
- **Expiry race with in-flight text (L-1, LOW):** text arriving just before the client-side deadline
  can reach the server just **after** the op's `expires_at` (clock skew / slow delivery) ⇒ the
  `send-message` carries a now-stale ref ⇒ per §5.9.1 the Cloud rejects it. The proposal notes the
  stale-ref rejection but does not specify the bot's behavior on this race (must treat as expired and
  notify, not retry). **Required: state the race handling.**

---

## 6. Owner-decision analysis (Q5/Q11/Q12/Q13 + Q3/Q7/Q10)

> Per task instruction, these are **not decided** here; only their impact, the minimum evidence/
> decision needed, and whether they block approval/submission/implementation.

| Q | Why it matters | Minimum evidence/decision needed | Blocks approval? | Blocks upstream submission? | Blocks implementation? |
| --- | --- | --- | --- | --- | --- |
| **Q5** — Cloud resolves `stored_path_ref` | **Central.** Without it, `consumed_at` cannot exist **and** (see H-1) the uploaded file can never be made usable. r3 scopes Q5 only to *consumption*; the **usable-content** resolution is **not** covered at all | Decide (a) how a ref is turned into a real path/tool the agent can read, and (b) whether the same resolver sets `consumed_at` | **YES (as currently scoped)** — Q5 is incomplete; it omits the usable-content question | YES | YES |
| **Q11** — implement P0 or keep fail-closed | Product direction; determines whether upstream work happens at all | Owner decision (no evidence needed) | No (it is *the* approval question) | YES | YES |
| **Q12** — `consumed_at` crash trade-off | Defines over-retention vs early-delete safety | Confirm over-retention ≤ 15 min is acceptable, **and** resolve CW-1/CW-2 ordering vs the Telegram ack | No (documented) — but its **ordering** half is a required correction, not an owner choice | No | YES |
| **Q13** — `uploading` re-intro if async | Keeps the state model honest | Confirm staging is **synchronous** (r3 assumes it) | No | No | YES |
| **Q3** — PROVISIONAL limits | `max_total = max_per_file = 3 MiB` ⇒ effectively one full-size file | Confirm the triple (`per_file`, `total ≥ files × per_file`, `files`) | No | No | YES |
| **Q7** — idempotency window | `sha256` dedup window unspecified | Confirm the window | No | No | YES |
| **Q10** — independent security review | §9 criterion 10 / §7.8 | Who performs it; release gate? | No | No | YES (gate) |

**Q5 answer to the task's specific question:** **yes — Q5 (as currently scoped) leaves a fundamental
gap.** Even a *perfect* secure upload is useless if nothing turns the opaque `stored_path_ref` into
content the agent can read. r3 never specifies that translation, so "accept a secure upload" and
"make the uploaded content usable by the target conversation" are **not connected** by the contract
(see H-1).

---

## 7. Security and architecture challenge

Requirement-by-requirement, with what is **specified with enforceable behavior** vs merely
**asserted**.

| Requirement | Assessment | Where |
| --- | --- | --- |
| Authentication | **Specified** — caller uses the Cloud bearer; agent-server key never leaves the server | §5.3, §7.2 |
| Authorization (conversation ownership) | **Specified** — bind to one principal + one conversation; reuse existing ownership checks | §5.3, §6 T-02 |
| Conversation isolation | **Specified** — server resolves destination from the authorized `conversation_id` | §5.2, §6 T-03 |
| Workspace containment | **Specified (reuse)** — `resolve().is_relative_to(workspace_root)` (422) | §7.0, §7.4 |
| Symlink/TOCTOU resistance | **Specified** — `O_NOFOLLOW` + `O_CREAT` + `O_EXCL`; note the existing route only `resolve()`s at check time | §5.7, §7.4, §6 T-07 |
| Size/type/count/aggregate limits | **Proposed, not approved** — PROVISIONAL and mutually inconsistent | §5.7, §12 Q3 |
| Server-side destination resolution | **Specified** — no client path | §5.2, §5.7 |
| Idempotency/replay | **Specified** — `Idempotency-Key` + `sha256`; window unspecified | §5.6, §12 Q7 |
| Operation status/reconciliation | **Specified** — op id + status endpoint | §5.6, §5.9 |
| Fixed expiry + cleanup | **Specified**, but per-op vs batch (M-5) and cleanup-vs-read race (M-3) | §5.9, §5.10 |
| Unknown remote outcomes | **Specified** for the **upload**; **not** for the **message/consumption** path (CW-2) | §5.9, §5.9.1 |
| No blind retries | **Specified** for upload; send-message has **no** idempotency (CW-1) | §5.6, §8.1 I11 |
| No deletion before terminal state | **Specified** — sweep only on terminal states | §5.10, §8.1 I12 |
| Existing SQLite/one DB, existing workers, single bot process | **Preserved** — no second DB/worker | §8.1 I2/I3 |
| Telegram ack + durable delivery | **Asserted "unchanged"** but **not ordered** against Cloud-side consumption/cleanup (CW-1) | §8.1 I13 |
| ImageContent limits | **Correctly scoped** — images only; not a P0 alternative | §4 #5 |
| No SSRF / confused deputy | **Specified** — bot→runtime hop eliminated; internal store call not reachable by a caller key | §6 T-04, §7.2 |
| No credential exposure | **Specified** — key never returned/logged | §6 T-10 |

**Asserted-but-not-specified (require enforceable behavior):**
1. **H-1** the ref→usable-content translation (nothing specified).
2. **M-2** durable Cloud acceptance of a `send-message` (contradicted by the verified thin proxy).
3. **M-1** ordering of `consumed_at`/cleanup vs the bot's durable Telegram ack.
4. **M-3** cleanup only after the agent has actually consumed the file (not merely after message-accept).

---

## 8. P0 acceptance matrix

Maps every P0 requirement to contract section · required durable state · required control ·
failure/recovery · **evidence status** (`verified upstream` / `proposed` / `unresolved` /
`unsupported`). **Nothing is marked implemented.**

| P0 requirement | Contract section | Durable state | Security control | Failure/recovery | Evidence status |
| --- | --- | --- | --- | --- | --- |
| Upload to an **exact existing** conversation | §5.2, §5.3 | op row keyed by `conversation_id` | server-resolved destination | status endpoint | **proposed** |
| Narrow credential (no agent-server key) | §5.3 | — | Cloud bearer only | — | **proposed** |
| No command exec / no workspace read by the op | §5.3 | — | scoped op | — | **proposed** |
| Server-resolved destination (no client path) | §5.2, §5.7 | op row | server-generated path | — | **proposed** |
| Size/type/count/aggregate limits | §5.7 | — | server enforcement | 413/415 | **proposed (PROVISIONAL, Q3)** |
| Symlink/traversal hardening | §5.7, §7.4 | — | `O_NOFOLLOW`, `O_EXCL`, containment | reject | **proposed** |
| Stable `operation_id` + status endpoint | §5.6, §5.9 | op row | — | poll status | **proposed** |
| Idempotent create (`Idempotency-Key`) | §5.6 | idempotency key | — | same op returned | **proposed (window Q7)** |
| Monotonic terminal states | §5.9 | op row | — | — | **proposed** |
| Ended/deleted conversation behavior (409) | §5.8, §5.10 | op row | — | 409 | **proposed** |
| **Multiple files join one pending batch** | §5.4 (repeatable `file`), §8.1 I6 | op row (+ local batch) | — | — | **proposed (client-side batch)** |
| **First-file deadline never extends** | §8.1 I4/I6, §5.9 | local `T0` | — | — | **proposed, client-side only (M-5)** |
| **Only accompanying text triggers sending** | §8.1 I7/I8, §8.2 S4/S7 | local batch state | — | — | **proposed (client invariant)** |
| **Non-text messages do not trigger sending** | §8.1 I8 | local batch state | — | — | **proposed (client invariant)** |
| **Sent to the same existing conversation** | §8.1 I1 | local batch | op bound to one conversation | — | **proposed** |
| **No new-conversation fallback** | §8.1 I1 | — | no create path in contract | — | **proposed** |
| **Expiry / late-text behavior safe** | §5.9, §5.9.1 | op row | — | stale-ref reject | **partly unresolved (L-1)** |
| **Unknown outcomes preserve files + reconciliation data** | §5.9, §8.1 I10 | op row | — | no blind retry | **proposed (upload); message path unresolved (CW-2)** |
| **Cleanup only after confirmed terminal outcomes** | §5.10, §8.1 I12 | op row | — | sweep | **proposed; cleanup-vs-read race (M-3)** |
| **Uploaded content usable by the conversation** | **— (absent)** | — | — | — | **unsupported (H-1)** |

**Bottom line:** every requirement is at most **proposed**; the **usable-content** requirement is
**unsupported** (absent from the contract), and expiry/unknown-outcome/cleanup carry the unresolved
races above.

---

## 9. Exact unresolved risks and required corrections

| ID | Severity | Section(s) | Issue | Required correction |
| --- | --- | --- | --- | --- |
| **H-1** | **HIGH** | §5.2, §5.9, §5.9.1, §8.2 S7 | The `stored_path_ref` is placed into **prompt text** and never resolved to anything the agent can read; the contract never states how an uploaded file becomes **usable content**. The feature cannot deliver its purpose as specified. | Specify the resolution: either the Cloud rewrites the ref to the real staged path when forwarding `send-message`, or a documented tool/endpoint the agent uses to fetch by ref. State that the agent receives a **readable** path/tool, not an inert token. |
| **M-1** | MEDIUM | §5.9.1, §8.1 I13, §8.2 S7/S10 | Cloud-side `consumed_at`/cleanup ordering vs the bot's **durable Telegram ack** is unspecified ⇒ CW-1 (batch loss / duplicate dispatch). | Specify the ordering: the bot must durably record dispatch intent (and the `Idempotency-Key`/`operation_id`) **before** the send-message call, and must **not** treat the prompt as delivered until its own durable ack; state how a Cloud-side `consumed_at`/cleanup cannot run ahead of that ack. |
| **M-2** | MEDIUM | §5.9.1, §2.2 | §5.9.1 assumes the Cloud `send-message` path "durably accepts" a message, but the verified handler is a **thin proxy with no durable write**. | State that making `consumed_at` durable requires **new** Cloud work (a durable message-accept step on the `send-message` route) and is not an existing capability; or drop the "same durable step" claim. |
| **M-3** | MEDIUM | §5.9.1, §5.10 | Cleanup keyed on `stored`+`consumed` can delete bytes **while the agent is reading** them (consumption is set at message-accept, not at agent read). | Require cleanup on `stored`+consumed to wait until the agent-server has **ingested** the message (or a defined grace), not merely until the Cloud accepted it. |
| **M-4** | MEDIUM | §5.5, §5.8, §5.9 | `rejected` may be **unobservable** if validation fails before an `operation_id` is issued — the same defect class R2-9 removed for `uploading`. | State whether a durable op row (with an id) is created on reject; if not, remove `rejected` from the observable state model. |
| **M-5** | MEDIUM | §5.4, §5.9, §8.1 I4/I6 | Server-side `expires_at` is **per operation**; the fixed-from-first-file 15-min deadline is **client-side only** and a batch spanning multiple creates has multiple deadlines. | State explicitly that the server has **no batch concept** and cannot enforce the batch deadline; define how a multi-file batch maps to one or more operations. |
| **L-1** | LOW | §5.9, §5.9.1 | Expiry race with in-flight text (client vs server clock; stale-ref rejection path). | Specify the bot's behavior on the stale-ref rejection (treat as expired + notify; no retry). |
| **L-2** | LOW | §5.9, §5.10 | A `accepted` row stranded by a mid-staging crash lingers ≤ 15 min with partial bytes. | State that partial staging is cleaned on the `expired`/`failed` transition. |
| **L-3** | LOW | §5.9 | Derive-on-read mixes server and client clocks. | Say the client must treat the **server** status as authoritative and not self-expire on its own clock. |
| **L-4** | LOW | §5.13 | §5.13 correctly says the legacy route is unconfined, but could note it carries the **same server-wide, command-capable** key weakness as §2.3.2. | Optional clarity note. |
| **I-1** | INFO | §5.6 | `send-message` has **no** idempotency key, so a retried message can duplicate (ties to CW-1/CW-2). | Note the risk; a message-level idempotency key is a possible future addition. |

---

## 10. Final verdict and rationale

**Verdict: `NEEDS_REVISION`.**

**Why not `PASS`/`PASS_WITH_NOTES`:** H-1 is a **material gap** — the contract accepts a secure
upload but never makes the uploaded content usable, so the recommended design, *as written*, does
not achieve P0's purpose. M-1/M-2/M-3 show the R2-6 `consumed` mechanism is **not implementable as
specified** (it depends on a durable Cloud message-accept that does not exist and is unordered
against the bot's durable ack). M-4/M-5 are internal-consistency defects of the same class R2-9
fixed. These are more than "notes".

**Why not `BLOCKED_BY_MISSING_UPSTREAM_EVIDENCE`:** the gaps are **design/specification** gaps, not
missing source evidence. All re-derivable upstream facts were verified; the missing pieces are
decisions and contract text the proposal can supply itself.

**Why not simply `PASS_WITH_NOTES`:** a `PASS_WITH_NOTES` requires the notes not to block approval;
H-1 blocks approval because the feature would not function.

**Rationale:** r3's **evidence work is sound and its R2-1…R2-9 corrections are mostly genuine** — I
re-verified the enterprise provenance, the scoped-route confinement, the auth model, the Cloud
"no upload" conclusion, and the legacy-client route against source. The proposal's **direction**
(Cloud-mediated scoped op reusing existing confinement) remains **sound and near-minimal**, and its
threat model and invariants are strong. But the **r3 additions around `consumed` and the missing
usable-content resolution** are not yet correct or complete. Fixing H-1 and M-1…M-5 is a **targeted,
documentation-only** change; once done, r3 should be re-reviewed (a focused delta review suffices).

**A `PASS` would mean only "ready for owner approval" — it would not authorize upstream submission,
implementation, or deployment. P0 remains unimplemented regardless of the verdict.**

---

## 11. Preservation and read-only compliance evidence

- **Only artifact created:** this file,
  `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R3-INDEPENDENT-ADVERSARIAL-REVIEW.md`.
- **Proposal unmodified:** `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md` was
  read only (sha256 unchanged, `88fd400e…`).
- **Self-review unmodified:** `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R3-SELF-REVIEW.md` read
  only (`8b29fa19…`).
- **Previous reviews unmodified:** r2 (`8d5153ca…`) and r1 (`a9c85800…`) read only.
- **Working tree preserved:** no reset/clean/checkout/force; the modified and untracked files listed
  in §1 are untouched.
- **No code/tests/schema/migration/config/doc change** other than this review file.
- **No production call, no credential, no secret access; no upstream issue/PR/maintainer contact; no
  commit/push/PR/merge/deploy.**
- **P0 is NOT implemented** and this review does not claim otherwise.
