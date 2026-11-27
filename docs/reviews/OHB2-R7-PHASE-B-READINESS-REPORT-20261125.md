# OHB2-R7 — Phase B Authorization and Activation Readiness Report (2026-11-25)

**Task:** `OHB2-R7-PHASE-B-AUTHORIZATION-AND-ACTIVATION-READINESS`
**Phase:** preparation only.
**Verdict:** `R7_PHASE_B_READINESS_PARTIALLY_VERIFIED`

**Why partial:** the local implementation facts are verified and the required designs
are documented, but the current architecture cannot yet enforce a strict one-canary
worker boundary, no reviewer credential/resource is authorized, and D-03 through D-09
remain owner decisions. Live R7 validation has not been executed and is not claimed.

---

## 1. Baseline and final Git state

### Baseline before this task

| Item | Value |
|---|---|
| Repository | `/workspace/project/OpenHandBot` |
| Branch | `agent/r6-review-delivery` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `origin/main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| HEAD tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| Tracked files | 569 |
| Modified tracked | 12 |
| Untracked entries | 59 |
| Python | 3.13.15 in `.venv` |
| pytest | 9.0.3 |
| Node | 24.22.2 |

The 12 modified tracked paths were pre-existing; three of them (`.agent/PROGRESS.md`,
`docs/OPERATIONS_RUNBOOK.md`, and `README.md`) were edited additively by this task. The other untracked
review artifacts were pre-existing. No destructive Git operation was used.

### Final after this task

- Branch, HEAD, `main`, `origin/main`, and HEAD tree are unchanged.
- No commit, push, PR/MR, merge, deploy, or release.
- Added five Phase B reports under `docs/reviews/`.
- Updated `.agent/PROGRESS.md` additively.
- Corrected the runbook and README `REVIEW_CI_TIMEOUT_MIN` wording and added a note
  that `REVIEW_REPOS`, `REVIEW_MAX_INPUT_CHARS`, and `REVIEW_CI_TIMEOUT_MIN` are
  validated but not consumed by any R2–R7 worker factory.
- No production code or test code changed in this task.
- No schema or migration change.

### Historical reports reconciled with the working tree

| Historical claim | Actual current fact |
|---|---|
| R7 Phase A: F-01 CI job completeness gap | Fixed in `bot/review/ci_contract.py`, `bot/review/evidence.py`, `bot/review/verdict.py`; 15 focused tests pass. |
| R7 Phase A: F-02 provider snapshot gap | Fixed in `bot/review/worker.py`; `ReviewRunner._verify_provider_binding()` rejects missing/mismatched/cycle-mismatched bindings before collection/provider calls; 11 focused tests pass. |
| R7 Phase A: F-03 branch movement partial | Fixed in `bot/review/collector.py`; branch/SHA verified before and after reads; 8 focused tests pass. |
| R7 Phase A: worker activation blocker | Still true. `bot/app.py` constructs `ReviewReportService` and registers `^review:`, but does not construct `ReviewRunner`/`ReviewWorker`. |
| Canary D-01/D-02 implemented locally | Still true; no runtime wiring. |
| `REVIEW_ENABLED=1` means configuration validation only | Still true. |
| `REVIEW_CI_TIMEOUT_MIN` bounds live CI | **False.** It is parsed and tested but not consumed by the collector or worker. |
| `REVIEW_MAX_INPUT_CHARS` bounds live review input | **Not yet wired.** It is parsed and stored in snapshots/tests, but no R2–R7 worker factory consumes it. |
| `REVIEW_REPOS` bounds live GitHub access | The client supports `allowed_repositories`, but no R2–R7 factory constructs the live review client with it. |
| Generated review wording calls the result “مراجعة مستقلة” | Existing product wording. This report does not claim independent verification; see §3.3 item 6. |

---

## 2. Verified R7 implementation facts

### 2.1 Canary linkage

`bot/review/canary_linkage.py` contains:

- `CreationJobRepositoryLinkSource`:
  - exact persisted `conversation_id`;
  - one `done` `creation_jobs` row;
  - owner `chat_id` equality;
  - strict `owner/repo`;
  - OpenHands `selected_repository` equality check only;
  - GitHub numeric repository ID and canonical full-name verification.
- `CanaryLinkageService`:
  - owner-only `chat_id == owner_id`;
  - non-empty explicit list/tuple of unique positive PR numbers;
  - default maximum 20 candidates;
  - delegates to the existing resolver;
  - uses existing `reserve_resolved_memberships()`.

It is intentionally not imported or constructed by `bot/app.py`.

### 2.2 Resolver and lifecycle

- `bot/review/resolver.py` verifies repository numeric ID/full name, PR base/head
  repository IDs/names, fork/cross-repository mismatch, PR open/merged state, branch
  tip, exact head SHA, compare/merge-base, and re-reads PR/branch after validation.
- `reserve_conversation_review()` is atomic and conversation-wide; membership rows are
  immutable; a new PR during an active cycle is pending, not an active mutation.
- `ReviewRunner` uses exact evidence/membership binding and the immutable provider
  snapshot; it refuses missing or mismatched bindings before collection/provider work.
- `ReviewWorker` claims eligible conversation-wide cycles and delegates to the runner.
  It has no canary-specific claim filter and no one-shot mode.
- `ReviewWorker` is not constructed by `bot/app.py`.

### 2.3 Report and callback path

- `ReviewReportService` builds a deterministic report from persisted R5 rows and creates
  one outbox intent per `(review_id, version)`.
- `_post_claimed_review()` sends the report document with summary caption and
  `review:d|a|r:<id>:<version>` buttons; CAS `claimed => sending` precedes the send.
- Ambiguous Telegram errors become `unknown`, not `sent`.
- `review_action()` requires allowed user, private chat, configured owner, exact cycle
  `chat_id`, and callback message `chat_id`.
- `record_auto_review_owner_decision()` records an immutable `OWNER_ACCEPTANCE` event;
  it does not alter the technical verdict.

---

## 3. D-03 — Authorization-source findings

### 3.1 Current authorization matrix

| Object / action | Current check | Where | Assessment |
|---|---|---|---|
| Telegram owner | `ALLOWED_TELEGRAM_ID` parsed to exactly one positive ID; `Config.owner_id = allowed[0]` | `bot/config.py` | Sufficient for a single-owner bot; no multi-owner support. |
| Incoming update | `_allowed()` requires allowed user **and** `chat.type == "private"` | `bot/handlers.py` | Group chats are rejected. |
| Review callback | `_allowed()`, `user.id == owner_id`, `chat.id == cycle.chat_id`, callback `message.chat_id == cycle.chat_id` | `bot/handlers.py:review_action`, `_review_owner_allowed` | Prevents different user, group chat, and another chat. |
| OpenHands conversation | `watched` row exists, `watched.chat_id == chat_id`, conversation not deleted | `bot/review/resolver.py:_authorize` | Existing conversation authorization boundary. |
| Canary creation job | Exact conversation ID, one `done` row, job `chat_id == owner_id` | `bot/review/canary_linkage.py` | Canary-only; not arbitrary OpenHands conversations. |
| Repository | `GitHubClient._repo()` allowlist; numeric ID and canonical full-name checks | `bot/review/github.py`, `bot/review/resolver.py` | Read-only; name is not durable identity. |
| Explicit PR list | `CanaryLinkageService` owner check; no discovery; resolver verifies each PR | `bot/review/canary_linkage.py`, `bot/review/resolver.py` | Not wired to a user-facing entrypoint. |
| Review cycle | `reserve_conversation_review()` checks conversation/chat, provider snapshot, immutable memberships; one active conversation-wide cycle | `bot/db.py` | Atomic and conversation-wide. |
| Report delivery | Outbox row carries `cycle.chat_id`; no send to group or arbitrary chat | `bot/db.py:schedule_auto_review_report_delivery`, `bot/outbox.py` | Delivery destination is DB-derived, not caller-supplied at send time. |
| Owner acceptance | Handler re-checks owner/private/cycle chat; DB checks `cycle.chat_id == owner_user_id`; first decision immutable | `bot/handlers.py`, `bot/db.py` | Prevents unauthorized accept/reject. |

### 3.2 Threats requested by the task

| Threat | Result | Evidence / limitation |
|---|---|---|
| A different Telegram user submits a PR list | **Rejected by design** if the future entrypoint uses `CanaryLinkageService` with `Config.owner_id`; no live entrypoint exists yet. | `CanaryLinkageService.resolve()` checks `chat_id == owner_id`; owner binding is constructor-supplied. |
| A group chat initiates a canary | **Rejected by existing handler authorization** (`_allowed` private only); a direct service call with a group ID would fail the positive owner-ID check. | No group path exists; no canary entrypoint exists. |
| A conversation belonging to another owner | **Rejected** by `watched.chat_id` and canary job `chat_id`. | Resolver `_authorize`; canary source owner check. |
| A repository mismatch | **Rejected** by allowlist, numeric ID, and canonical full-name checks. | Resolver `_load_repository` / `_validate_pull_request`. |
| A PR list changed after reservation | **Rejected** by reservation identity/conflict and immutable membership triggers. | `reserve_conversation_review`, `auto_review_memberships` triggers, lifecycle tests. |
| A callback from another chat or message | **Another chat:** rejected. **Another message in the same owner/cycle chat:** not bound to a specific Telegram message ID; the callback still must be owner/private/cycle-chat and contain a persisted review/version. | `_review_owner_allowed` checks `message.chat_id`, not `message.message_id`. Telegram inline keyboards are bot-issued, so this is a low residual risk, not a cross-chat bypass. |
| An unauthorized user accepts/rejects | **Rejected** by handler and DB checks; tests cover non-owner, forged review ID, and cross-chat callback. | `test_review_callback.py`. |

### 3.3 Trust-boundary gaps

1. **No user-facing D-02 entrypoint or factory.** `CanaryLinkageService` exists but is not
   constructed in `bot/app.py`; there is no command, callback, or activation path that
   binds it to `Config.owner_id` and a private owner chat. This is a runtime blocker, not
   an authorization bypass.
2. **Constructor-supplied owner.** A future factory must pass `Config.owner_id`; a caller
   that passes another positive ID would bypass the service's local check. The resolver's
   `watched.chat_id` still limits the conversation, but the factory must be reviewed.
3. **No exact Telegram message-ID binding.** Authorization is owner/private/cycle-chat,
   not “this callback came from the exact report message.” This does not permit another
   chat; it permits a callback from another bot-sent copy of the same report in the same
   owner chat.
4. **D-03 broader authorization remains unresolved.** The current checks use existing
   `watched.chat_id`, configured owner, and private-chat policy. No new trusted identifier
   was introduced. A broader OpenHands-owner check or alternate authorization source
   requires an owner decision.
5. **Direct Details resend bypasses the outbox.** `ReviewReportService.send_details()`
   sends the persisted report directly from the callback. It is owner-gated but is not
   idempotent like the outbox path; repeated Details can produce multiple copies. It never
   changes verdict or owner decision.
6. **Generated report wording.** The report title/summary says “مراجعة مستقلة”. This is a
   product label, not independent verification of this task. If it is intended to mean
   “independent reviewer,” that claim is not supported and needs an owner-approved
   wording change before live delivery.

**D-03 disposition:** current checks are sufficient for the existing callback and
conversation boundaries, but the canary PR-list entrypoint and broader authorization
source are not implemented. D-03 remains open.

---

## 4. D-04 — Durable repository provenance options

Current limitation: `creation_jobs` stores `repo` and `conversation_id`, but not the
GitHub numeric repository ID observed at creation. The canary source resolves the name
through GitHub now, so a deleted-and-recreated repository with the same name is
indistinguishable from the original.

| Option | Security guarantees | Failure modes | Migration | Backward compatibility | Tests | Impact |
|---|---|---|---|---|---|---|
| **A. Retain current name + numeric-ID verification** | Current GitHub identity is verified; name alone is not membership identity; no false claim of historical continuity | Same-name delete/recreate is accepted as the new repository; rename/transfer rejected by name mismatch/redirect; historical ID not available | None | Full | Existing canary tests, including same-name limitation | Current code; canary-only; requires explicit non-recreation attestation for live use |
| **B. Persist numeric repository ID at creation** | Future creation jobs can compare stored ID to current GitHub ID; delete/recreate produces ID mismatch | Existing jobs have NULL; creation path needs GitHub read; repository may change before persistence; rename policy still needed | New nullable column/backfill policy; no migration authorized | Existing rows must fail closed or remain canary-only | Creation capture, NULL fail-closed, same-name recreation, rename/transfer, immutable provenance | Changes creation flow and schema; D-04 decision required |
| **C. Separate immutable provenance record** | Durable audit record can bind conversation, repository ID, full name, creation time, and source; can support multiple cycles and explicit provenance | More schema/trigger surface; backfill of old jobs; record can be wrong if captured after recreation; authorization still separate | New table/triggers; no migration authorized | Existing jobs without record fail closed | Record immutability, creation binding, backfill, deletion/recreation, conflict | Largest change; strongest audit if designed correctly; D-04 decision required |
| **D. Reject identity-continuity claims for this canary** | No false continuity claim; canary remains valid only for a repository the owner attests was not deleted/recreated during the window | Operational restriction; cannot prove continuity; no durable evidence for future cycles | None | Full | Documentation/negative test; no schema | Safest wording; may block live canary if owner cannot attest |

**No option was selected or implemented.** The current code remains Option A. D-04
requires owner approval before any schema change, migration, or new durable identity
policy.

---

## 5. D-05 — Rename and transfer findings

| Event | Current behavior | Security interpretation |
|---|---|---|
| Repository renamed, old name requested | GitHub may return 301; `GitHubClient` rejects 3xx. Resolver maps the failure conservatively (malformed/response error) or canary source returns `None`. | Rejected by default. No silent redirect follow. |
| Repository renamed, new name supplied | If the link still has the old full name, `repository_rename_ambiguous`; if the numeric ID differs, `repository_id_mismatch`. | Rejected unless a new explicit link is supplied and verified. |
| Repository transferred to another owner | Old name may redirect or 404; new full name differs from the link; the allowlist is name-based. | Rejected by default. A numeric-ID match alone does not authorize the transfer. |
| Numeric ID continuity | ID may survive rename/transfer, but authorization is repository/owner/allowlist/link-specific. | **Not sufficient by itself.** Owner must re-authorize the new full name and allowlist. |
| Same-name delete/recreate | Numeric ID changes; current code has no stored prior ID to compare. | Indistinguishable under Option A; see D-04. |

**Required default:** reject rename, transfer, old-name redirects, full-name mismatch,
and numeric-ID mismatch until an explicit owner-approved policy exists. Current code
already rejects these; no change was made.

---

## 6. D-06 — Fork findings

- `PullRequestIdentity` includes base/head repository IDs and full names.
- `ConversationMembershipResolver._validate_pull_request()` requires:
  - `pr.repository_id` and `pr.repository_full_name` equal the verified repository;
  - `pr.base_repository_id/full_name` equal the verified repository;
  - `pr.head_repository_id/full_name` equal the verified repository.
- A PR from a different head repository is rejected as `pr_fork_ambiguous`; a PR whose
  base is another repository is rejected as `pr_repository_mismatch`.
- A closed or merged PR is rejected as `pr_not_open`.
- `RepositoryIdentity` parses `fork`, `archived`, and `private`, but the resolver does
  not currently reject a repository merely because it is itself a fork, archived, or
  private. That is a policy gap, not a cross-repository association bug.
- No PR from a fork can be silently associated with the upstream repository because the
  head repository ID/name must match the verified repository.

**Required default:** reject cross-repository/fork PRs (already true). Whether a
repository that is itself a fork/archived/private is eligible requires an explicit owner
policy. No fork/rename/transfer behavior was changed.

---

## 7. D-07 — Temporary worker activation summary

**Current architecture is not ready for activation as-is.**

Verified reasons:

- `ReviewWorker._claim()` calls `Database.claim_auto_review()` without a review ID,
  conversation ID, repository, or PR filter. It can claim any eligible conversation-wide
  cycle in the database.
- `ReviewWorker` inherits `_BaseWorker._run()`, an unbounded loop; there is no one-shot
  or canary-supervisor mode.
- No activation configuration exists for exact conversation/repository/PR/cycle/expiry.
- `ReviewRunner` has no provider-call or token budget. With `MAX_CHUNKS = 20`, one PR can
  produce up to 40 blind calls and 40 adversarial calls including schema corrections;
  multiple PRs and retries multiply this.
- `REVIEW_CI_TIMEOUT_MIN` is not consumed; `REVIEW_MAX_INPUT_CHARS` is not wired into a
  worker factory; `REVIEW_REPOS` is not used by a live client factory.
- No startup wiring exists; that is intentional and must remain so until approved.

A concrete bounded design is in
`docs/reviews/OHB2-R7-TEMPORARY-WORKER-ACTIVATION-DESIGN-20261125.md`. It requires a new
supervisor/budget/claim guard before activation. **Do not start the existing worker
against a production or shared database.**

---

## 8. D-08 — Live resource and permission summary

Detailed matrix: `docs/reviews/OHB2-R7-AUTHORIZATION-AND-RESOURCE-MATRIX-20261125.md`.

Current credential/resource facts, without values:

- `.env` does not exist in the workspace.
- `REVIEWER_API_KEY` is not set.
- `REVIEW_GITHUB_TOKEN` is not set.
- An `OPENHANDS_API_KEY` is present in the runtime environment, but it is not authorized
  for a live R7 operation by this task and its scopes cannot be proven from the client.
- No disposable repository/branch/PR, reviewer entitlement, provider pricing, or
  Telegram test destination is authorized.
- No live call or message was made.

The matrix distinguishes read-only review collection from optional GitHub writes
(disposable branch/PR creation, workflow dispatch, cleanup), and separates the review
token from any write-capable token.

---

## 9. Provider cost and data egress summary

Detailed report:
`docs/reviews/OHB2-R7-PROVIDER-COST-AND-DATA-EGRESS-REPORT-20261125.md`.

Current facts:

- The adapter is OpenAI-chat-compatible, `temperature=0`, `stream=false`, bounded by
  request/response bytes and a 20s default timeout (maximum 120s).
- No `max_tokens`, token accounting, pricing, balance, quota, or spend ceiling exists.
- No automatic provider retry; one schema-correction request is allowed per stage.
- `ReviewWorker` retryable failures can retry the cycle up to `max_attempts` (default 5);
  there is no provider-call budget.
- Worst-case per-PR provider calls can reach 80; the canary service permits up to 20 PRs,
  and retries can multiply this. This is not a safe live cost envelope.
- Provider data includes the redacted diff, CI metadata, architecture/review
  instructions, validated Blind output, and the OpenHands implementation report.
- Redaction is pattern-based; high-entropy secrets not matching a pattern can pass.
  Docs, `.patch`, `.zip`, `package-lock.json`, and binaries are excluded; raw diffs are
  not stored.

**Live inference remains blocked** until the owner supplies an entitled model, a hard
provider-side spend limit or explicitly accepts bounded exposure, and approves the data
egress/retention terms.

---

## 10. Local verification performed

No production code or test code was changed by this task. The runbook, README, and reports were
changed. Commands were run locally with mocks; no external service was called.

| Command | Result |
|---|---|
| Focused Phase B selection (11 modules) | **192 passed** in 15.74s |
| `pytest -q tests/test_review_*.py tests/test_auto_review*.py tests/test_verify_workflow_security.py` | **472 passed** in 17.96s |
| `pytest -q` | **4296 passed**, 74 warnings, 319.12s |
| `node --test tests/frontend/*.test.js` | **280 pass**, 0 fail |
| pyflakes | **0 issues** |
| compileall | **0 errors** |
| Bandit (`-lll -s B613`) | **High 0**; Low 7, Medium 20 |
| pip-audit | **No known vulnerabilities** |
| `git diff --check` | clean |

Python 3.11 and remote CI were not run; no claim is made for them.

---

## 11. Remaining owner decisions and blockers

- **D-03:** broader authorization source and owner-facing canary entrypoint.
- **D-04:** durable repository provenance/numeric-ID policy.
- **D-05:** rename/transfer policy.
- **D-06:** fork/archived/private repository policy.
- **D-07:** approval of the bounded activation design and implementation.
- **D-08:** live resources, credentials, and exact permissions.
- **D-09:** independent review and R8.

Additional readiness blockers:

- No reviewer entitlement/pricing/hard spend limit.
- No disposable GitHub repository/branch/PR.
- No authorized Telegram test target.
- No live worker activation path or canary supervisor.
- No proof of OpenHands/GitHub/provider behavior against real services.

---

## 12. Explicitly unauthorized actions

The following were **not** performed and remain unauthorized:

- OpenHands API calls or conversation creation/deletion.
- GitHub API calls, writes, branch/PR creation, or workflow dispatch.
- Reviewer provider calls or data transmission.
- Telegram messages or callbacks.
- ReviewWorker activation or startup wiring.
- Production database access, schema change, or migration.
- Commit, push, PR/MR, merge, deployment, release, or remote CI.
- Independent review or R8.

---

## 13. Final verdict

**`R7_PHASE_B_READINESS_PARTIALLY_VERIFIED`**

The local R7 linkage, resolver, lifecycle, report, callback, CI, and branch/SHA
implementations are verified. The authorization design is bounded and the required
resource/provider analyses are documented. Live activation remains blocked by D-03
through D-09, the missing canary supervisor/budget controls, and missing external
resources. This is a preparation result, not R7 live validation.
