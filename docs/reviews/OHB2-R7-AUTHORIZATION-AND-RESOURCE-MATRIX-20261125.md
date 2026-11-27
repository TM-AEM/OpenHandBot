# OHB2-R7 — Authorization and External Resource Matrix (2026-11-25)

**Task:** `OHB2-R7-PHASE-B-AUTHORIZATION-AND-ACTIVATION-READINESS`
**Scope:** read-only inspection and preparation. No credential value is printed. No
external service was called.

---

## 1. Status vocabulary

| Status | Meaning |
|---|---|
| `VERIFIED_LOCAL` | Implemented and covered by local code/tests. |
| `DESIGNED` | A bounded design exists; not implemented or authorized. |
| `OWNER_DECISION_REQUIRED` | Cannot be resolved without explicit owner approval. |
| `RESOURCE_REQUIRED` | A live resource/credential is absent or not authorized. |
| `BLOCKED` | Live use is not safe/authorized under current facts. |

---

## 2. D-03 authorization matrix

| Object/action | Required identity | Current check | Status | Residual gap |
|---|---|---|---|---|
| Telegram owner | One numeric Telegram user ID | `ALLOWED_TELEGRAM_ID` parser accepts exactly one positive ID; `Config.owner_id = allowed[0]` | `VERIFIED_LOCAL` | No multi-owner model; one owner only. |
| Incoming text/callback | Allowed user + private chat | `handlers._allowed()` requires `config.is_allowed(user.id)` and `effective_chat.type == "private"` | `VERIFIED_LOCAL` | Group/private distinction is handler-level; any future direct service caller must enforce it separately. |
| Canary PR-list submission | Configured owner, private chat, exact conversation | `CanaryLinkageService.resolve()` checks `chat_id == owner_id`; resolver checks `watched.chat_id`; no user-facing entrypoint exists | `DESIGNED` / `BLOCKED` for live | Factory must bind `Config.owner_id`; handler must enforce private chat; no command/callback exists. |
| OpenHands conversation | Existing watched conversation for the same owner chat | Resolver `_authorize()` checks not deleted and `watched.chat_id == chat_id` | `VERIFIED_LOCAL` | Canary source additionally requires one bot-created `done` job. |
| Conversation repository | Exact persisted `creation_jobs.repo` + exact conversation ID + owner | Canary source requires one row, owner chat, strict `owner/repo`, OpenHands `selected_repository` equality | `VERIFIED_LOCAL` | Same-name delete/recreate is not distinguishable (D-04). |
| Repository identity | GitHub numeric ID + canonical full name + allowlist | Resolver `_load_repository`; `GitHubClient._repo()` allowlist; full-name casefold | `VERIFIED_LOCAL` | Rename/transfer policy is reject-by-default (D-05). |
| Explicit PR list | Owner-supplied unique positive integers | `CanaryLinkageService` list/tuple validation; max 20; no discovery | `VERIFIED_LOCAL` | Not wired to a live command/UI. |
| PR identity/head | Repository ID/name, PR number, base/head repo IDs, open/unmerged, exact branch/head SHA, compare | Resolver `_validate_pull_request`, `_verify_branch`, `_resolve_base_sha`, re-reads | `VERIFIED_LOCAL` | Fork PRs rejected; repository-is-fork policy open (D-06). |
| Review cycle | Conversation-wide, one active cycle, immutable memberships | `reserve_conversation_review()` atomic; unique active conversation index; membership triggers | `VERIFIED_LOCAL` | No canary-specific claim filter. |
| Report destination | `cycle.chat_id` (owner private chat) | `schedule_auto_review_report_delivery()` uses cycle chat; outbox item carries it | `VERIFIED_LOCAL` | No re-check of `Config.owner_id` at send; relies on persisted cycle/outbox trust boundary. |
| Report details | Owner/private/cycle chat | `review_action()` and `_review_owner_allowed()` | `VERIFIED_LOCAL` | Direct Details resend bypasses outbox idempotency; duplicates possible. |
| Owner acceptance | Owner/private/cycle chat + persisted report version | Handler checks; DB checks `cycle.chat_id == owner_user_id`; unique first decision | `VERIFIED_LOCAL` | Internal DB callers are trusted; no external path bypasses handler. |
| Callback source | Owner/private/cycle chat + persisted review/version | `_review_owner_allowed()` checks callback message `chat_id`; callback data parsed strictly | `VERIFIED_LOCAL` | Not bound to exact Telegram `message_id`; same owner/chat copy can be used. No cross-chat bypass. |

### 2.1 Threat-by-threat result

| Threat | Result | Basis |
|---|---|---|
| Different Telegram user submits PR list | **Rejected** if factory uses `Config.owner_id`; current service has no live entrypoint. | Service owner check; resolver watched chat. |
| Group chat starts canary | **Rejected** by private-chat handler policy; service would also fail positive owner-ID equality. | `_allowed`; owner ID positive. |
| Conversation owned by another chat | **Rejected** | `watched.chat_id`; canary job `chat_id`. |
| Repository mismatch | **Rejected** | Numeric ID, canonical name, allowlist. |
| PR list changed after reservation | **Rejected** | Reservation key/identity/conflict; immutable membership rows. |
| Callback from another chat | **Rejected** | `cycle.chat_id` and callback message `chat_id` checks. |
| Callback from another message in same chat | **Not exact-message-bound**; still owner/private/cycle-chat and persisted version. | `message.chat_id` only. |
| Unauthorized accept/reject | **Rejected** | Handler owner checks; DB owner/chat check; callback tests. |

### 2.2 Authorization conclusions

- The existing handler and DB boundaries are sufficient for the currently registered
  review callback.
- The D-02 canary service is locally implemented but not authorized for live use because
  no owner-facing entrypoint/factory exists.
- No new authorization convention or trusted identifier was introduced.
- D-03 broader authorization remains `OWNER_DECISION_REQUIRED`.

---

## 3. D-08 — OpenHands

### 3.1 Minimum operations for a controlled canary

| Operation | Client method | Permission/effect | Status |
|---|---|---|---|
| Create disposable conversation | `OpenHandsClient.start_conversation()` (`POST /app-conversations`) | Create conversation; selected repository/branch | `RESOURCE_REQUIRED` |
| Wait for readiness | `get_start_task()`, `wait_for_start()` | Read start-task status | `RESOURCE_REQUIRED` |
| Associate repository | `selected_repository` at start, or `update_conversation_repository()` (`PATCH`) | Repository selection; no PR identity | `DESIGNED` |
| Send controlled task | `send_message()` (`POST /app-conversations/{id}/send-message`) | Execute agent task | `RESOURCE_REQUIRED` |
| Read conversation evidence | `get_conversations()`, `search_events()`, `get_last_reply()`, `get_reply_since()`, `get_last_exchange()` | Read metadata/events | `VERIFIED_LOCAL` (client surface) |
| Read files if needed | `list_files()`, `read_file_text_bounded()` | Read conversation files | `VERIFIED_LOCAL` (client surface) |
| Cleanup disposable conversation | `delete_conversation()` (`DELETE /app-conversations/{id}`) | Destructive deletion; requires explicit confirmation and ownership check | `DESIGNED` / `RESOURCE_REQUIRED` |

### 3.2 OpenHands facts

- The API key is sent as `Authorization: Bearer` to `/api/v1`.
- The client does not expose scope introspection; scopes/permissions cannot be proven
  from code.
- `start_conversation()` sends `selected_repository` and `selected_branch`; it does not
  send `pr_number`. Exact PR/SHA must come from GitHub.
- A disposable conversation must be isolated from production conversations and from the
  production database.
- No OpenHands call was made.

**Minimum practical grant:** an API key for a dedicated test identity/workspace that can
create, read, message, and delete only the disposable conversation, with repository
selection limited to the disposable repository. The provider must confirm that the key
cannot access production conversations; if it cannot, do not use it.

---

## 4. D-08 — GitHub

### 4.1 Read-only review collection

| Operation | Client method | Minimum GitHub permission |
|---|---|---|
| Repository identity | `get_repository()` | Metadata: Read; Contents: Read |
| Branch identity/tip | `verify_branch_sha()` / `get_branch()` | Contents: Read |
| PR metadata | `get_pull_request()` | Pull requests: Read |
| Compare/base/head/diff | `compare()` | Contents: Read |
| Workflow runs for SHA | `get_workflow_runs_for_sha()` | Actions: Read |
| Workflow jobs | `list_run_jobs()` | Actions: Read |
| Workflow run by ID | `get_workflow_run()` | Actions: Read |

Recommended fine-grained token scope: **only the disposable repository**, with
`Metadata: Read`, `Contents: Read`, `Pull requests: Read`, and `Actions: Read`.
No write permission is needed for review collection.

### 4.2 Optional write operations for a canary setup

| Operation | Minimum permission | Separate approval |
|---|---|---|
| Create disposable branch | Contents: Write | Yes; never on production repository |
| Create disposable PR | Pull requests: Write | Yes |
| Dispatch exact-SHA verification workflow | Actions: Write (classic token may also require `workflow`) | Yes; only after exact SHA validation |
| Delete disposable branch | Contents: Write | Yes; only the named test branch |
| Close/delete disposable PR | Pull requests: Write | Yes; only the named test PR |

Use a separate write-capable token from the read-only review token. The review client
has no write methods and must not be given a write token.

### 4.3 Current status

- `REVIEW_GITHUB_TOKEN` is **not set**.
- No disposable repository, branch, PR, or workflow run is authorized.
- No GitHub API call or write was made.
- `verify.yml` is present but untracked; it has never run remotely.
- Workflow permissions are `contents: read`; workflow-dispatch permission is a caller
  permission, not granted by the workflow file.

---

## 5. D-08 — Reviewer provider

| Requirement | Current fact | Status |
|---|---|---|
| Supported adapter | OpenAI-compatible `POST <api_base>/chat/completions`, `stream=false`, `temperature=0` | `VERIFIED_LOCAL` |
| Provider/model configured | No `REVIEWER_PROVIDER`, `REVIEWER_API_BASE`, `REVIEWER_API_KEY`, or `REVIEWER_MODEL` in environment; `.env` absent | `RESOURCE_REQUIRED` |
| Entitlement | Cannot be inferred from catalog visibility; no provider call allowed | `UNVERIFIED` |
| Pricing/credits | No local pricing/balance/usage ledger; no reliable documented balance API in this implementation | `UNVERIFIED` |
| Hard request limit | Request body default 256 KiB, max 2 MiB; response default 1 MiB, max 4 MiB | `VERIFIED_LOCAL` |
| Token limit | No `max_tokens`/output-token field; no token accounting | `GAP` |
| Timeout | 20s default, 120s maximum; connect/read/write/pool bounded | `VERIFIED_LOCAL` |
| Retries | No automatic provider retry; one schema correction per stage | `VERIFIED_LOCAL` |
| Data transmitted | See provider report; redacted diff, CI metadata, instructions, Blind output, OpenHands report | `VERIFIED_LOCAL` |

**Minimum grant:** an API key/model entitled for inference, with a provider-side hard
spend limit, documented data-retention terms, and an owner-approved maximum exposure.
No entitlement is inferred from the presence of an OpenHands/GitHub platform key.

---

## 6. D-08 — Telegram

| Requirement | Current fact | Status |
|---|---|---|
| Bot token | `TELEGRAM_BOT_TOKEN` required by config; no value printed | `RESOURCE_REQUIRED` |
| Destination | `cycle.chat_id` must equal the configured owner's private chat | `VERIFIED_LOCAL` |
| Summary + report | `send_document` with persisted Markdown content, escaped caption, HTML parse mode | `VERIFIED_LOCAL` |
| Details/Accept/Reject | Inline buttons `review:d|a|r:<id>:<version>`, each ≤64 UTF-8 bytes | `VERIFIED_LOCAL` |
| Callback authorization | Allowed user, private chat, owner, cycle chat, callback message chat | `VERIFIED_LOCAL` |
| Delivery confirmation | `send_document` return is treated as accepted; no user-read receipt | `VERIFIED_LOCAL` limitation |
| Ambiguous delivery | `TelegramError`/timeout after sending → outbox `unknown`; no automatic retry | `VERIFIED_LOCAL` |
| Group delivery | Not supported; group chat rejected | `VERIFIED_LOCAL` |

**Minimum practical setup:** the owner's private chat with the bot, bot permission to
send documents/messages, and the owner available to receive the report and press
Details/Accept/Reject. No channel/group or third-party chat is authorized. No Telegram
message was sent.

---

## 7. D-08 — Local runtime

| Item | Requirement | Current status |
|---|---|---|
| Required base env | `TELEGRAM_BOT_TOKEN`, `OPENHANDS_API_KEY`, `ALLOWED_TELEGRAM_ID` | Existing bot requirements; not authorized for live R7 |
| Review env | `REVIEW_ENABLED=1`, `REVIEW_REPOS`, `REVIEWER_PROVIDER`, `REVIEWER_API_BASE`, `REVIEWER_API_KEY`, `REVIEWER_MODEL`, `REVIEW_GITHUB_TOKEN` | Review-specific credentials absent |
| Tuning env | `REVIEW_MAX_INPUT_CHARS`, `REVIEW_CI_TIMEOUT_MIN`, `REVIEW_AUTOFIX_ROUNDS` | Parsed/validated; no R2–R7 worker factory consumes the first two; autofix must be 0 |
| Database isolation | Dedicated SQLite file outside production; WAL/-shm copied together if snapshotting | Required; not created |
| Worker lifecycle | Standalone supervisor; no `bot/app.py` wiring; one-shot; graceful stop; lease expiry recovery | `DESIGNED`, not implemented |
| Logging/redaction | `RedactingFilter` for configured secrets; safe error classes; no prompts/raw bodies in logs | `VERIFIED_LOCAL`; review logs still need review before live |
| Shutdown/recovery | Cancel worker, close GitHub/provider clients, preserve lease/DB state; no false sent state | `DESIGNED`; current base worker cancels but does not release lease |
| Production safety | No production DB, no production chat, no production repository/branch | Required; not authorized |

**No production database was opened or modified.** No worker was constructed or started.

---

## 8. Authorization checklist for a future live canary

Each item requires a separate, explicit owner approval; none is granted here.

- [ ] D-01 B and D-02 explicit-list approved for the exact canary.
- [ ] D-03 owner/private-chat/PR-list entrypoint approved.
- [ ] D-04 provenance option approved (or explicit no-continuity attestation).
- [ ] D-05 rename/transfer policy approved.
- [ ] D-06 fork/archived/private repository policy approved.
- [ ] D-07 bounded activation design approved and implemented.
- [ ] D-08 disposable OpenHands conversation, GitHub repository/branch/PR, provider
      model/credential, and Telegram owner chat authorized.
- [ ] Provider-side hard spend limit or explicit bounded exposure accepted.
- [ ] Data-egress/retention terms accepted.
- [ ] Isolated database path and backup/cleanup plan approved.
- [ ] Exact provider call/token/chunk limits and stop conditions approved.
- [ ] Independent review/R8 decision recorded (not claimed here).

Until all applicable boxes are approved, the live canary remains unauthorized.
