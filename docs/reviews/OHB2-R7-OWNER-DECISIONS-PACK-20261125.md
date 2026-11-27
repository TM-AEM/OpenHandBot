# OHB2-R7 — Owner Decisions Pack (2026-11-25; approvals recorded 2026-11-26)

**Task:** `OHB2-R7-OWNER-DECISIONS-PACK`
**Mode:** strictly plan-only and documentation-only.
**Decision status:** D-03, D-04, D-05, D-06 `APPROVED`; D-04b `DEFERRED`;
D-07 `APPROVED_DESIGN_ONLY`; D-08 `APPROVED_BLOCKED`.
**Final package verdict:** `R7_OWNER_APPROVALS_RECORDED_WITH_NOTES`.
**Owner approval date:** 2026-11-26.
**Source:** explicit owner approval in the ChatGPT conversation. No owner identity,
signature, or approval mechanism is inferred or invented.

> This verdict describes approval-record accuracy and documentation verification only.
> It is not implementation completion and not live readiness. D-07 is design-only;
> D-08 remains blocked; no live Canary operation is authorized.

No production code, test code, schema, migration, runtime wiring, worker activation,
external call, or Git publication was performed. The recommendations were approved as
policy/design on 2026-11-26; implementation and live operations remain separately
unauthorized.

---

## 0. Decision summary and approval checklist

### 0.1 Summary

| ID | Current status | Selected/approved option | Exact token | Dependencies |
|---|---|---|---|---|
| **D-03** | `APPROVED` | Current-owner revalidation | `D-03: current-owner-revalidation` | D-01 B, D-02 Explicit-list, D-07 |
| **D-04** | `APPROVED` | Canary-only owner attestation | `D-04: canary-only-owner-attestation` | D-05, D-06, D-08 |
| **D-04b** | `DEFERRED` | Persist numeric repository ID — not approved, no schema work | `D-04b: persist-numeric-repository-id` | D-04; future schema decision |
| **D-05** | `APPROVED` | Reject rename/transfer/redirect/unverifiable identity | `D-05: reject-rename-transfer` | D-04 |
| **D-06** | `APPROVED` | Private allowlisted only; reject other nonstandard categories | `D-06: private-allowlisted-only + reject-fork-cross-repo-archived-deleted-recreated` | D-04, D-05, D-08 |
| **D-07** | `APPROVED_DESIGN_ONLY` | Bounded one-shot supervisor design; no implementation/activation | `D-07: approve-bounded-canary-supervisor-design` | D-03, D-04, D-05, D-06, D-08 |
| **D-08** | `APPROVED_BLOCKED` | Keep live resources blocked | `D-08: keep-blocked` | D-03 through D-07 |

### 0.2 Approval checklist

- [x] D-01 B is preserved as the approved local canary linkage basis; not reopened.
- [x] D-02 Explicit-list is preserved as the approved local canary PR source; not reopened.
- [x] Conversation-wide scope and one active cycle per conversation are preserved.
- [x] Blind Review and Adversarial Review remain separate; the verdict remains deterministic.
- [x] D-03 owner choice recorded: `current-owner-revalidation` (2026-11-26).
- [x] D-04 owner choice recorded: `canary-only-owner-attestation` (2026-11-26).
- [x] D-04b recorded as `DEFERRED`; numeric-ID schema work is not approved.
- [x] D-05 owner choice recorded: `reject-rename-transfer` (2026-11-26).
- [x] D-06 owner choice recorded: `private-allowlisted-only` (2026-11-26).
- [x] D-07 owner choice recorded: `approve-bounded-canary-supervisor-design` — design only.
- [x] D-08 owner choice recorded: `keep-blocked`.
- [ ] Live resources, provider entitlement, spend cap, and data-egress terms approved.
- [ ] Bounded supervisor implementation separately authorized after D-03–D-08.
- [ ] Independent review requested (currently deferred).
- [ ] R8 authorized (not started).

### 0.3 Status semantics

| Status | Meaning in this pack |
|---|---|
| `OWNER_DECISION_REQUIRED` | No owner choice is recorded. |
| `RECOMMENDED_PENDING_APPROVAL` | The agent recommends an option; it is not approved. |
| `DEFERRED` | The owner explicitly postpones the decision. |
| `REJECTED` | The owner explicitly rejects an option. |
| `APPROVED` | Owner approved the policy choice. Implementation is not implied. |
| `APPROVED_DESIGN_ONLY` | Owner approved a design only; implementation/activation is not authorized. |
| `APPROVED_BLOCKED` | Owner approved keeping the decision in a blocked state; live use is not authorized. |

---

## 1. Baseline audit and evidence

### 1.1 Git baseline

| Item | Value |
|---|---|
| Repository path | `/workspace/project/OpenHandBot` |
| Branch | `agent/r6-review-delivery` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `origin/main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| HEAD tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| Tracked files | 569 |
| Modified tracked | 12 |
| Untracked entries | 66 |

The working tree was already dirty with R1–R7 implementation, tests, and reports. It was
preserved. No reset, clean, checkout, staging, deletion, commit, push, or publication was
performed.

### 1.2 Reports read

- `docs/reviews/OHB2-R7-PHASE-B-READINESS-REPORT-20261125.md` (372 lines)
- `docs/reviews/OHB2-R7-AUTHORIZATION-AND-RESOURCE-MATRIX-20261125.md` (212 lines)
- `docs/reviews/OHB2-R7-TEMPORARY-WORKER-ACTIVATION-DESIGN-20261125.md` (296 lines)
- `docs/reviews/OHB2-R7-PROVIDER-COST-AND-DATA-EGRESS-REPORT-20261125.md` (253 lines)
- `docs/reviews/OHB2-R7-REMEDIATION-REPORT-20261125.md` (301 lines)
- `docs/reviews/OHB2-R7-CANARY-LINKAGE-IMPLEMENTATION-REPORT-20261125.md` (332 lines)
- `docs/reviews/OHB2-R7-B01-OWNER-DECISIONS-20261125.md` (227 lines)
- `docs/reviews/OHB2-AUTO-REVIEW-R7-READINESS-REPORT-20261125.md` (Phase A)
- `docs/reviews/OHB2-R7-CANARY-LINKAGE-OWNER-DECISION-REQUEST-20261125.md`

### 1.3 Existing owner decisions for D-03 through D-08

A repository-wide search found **no recorded owner approval** for D-03 through D-08.
The only existing records are:

- the earlier owner-decision request listing D-03 through D-09 as open;
- the Phase B matrix checklist marking them unapproved;
- the previous owner-decision pack, which contains recommendations only;
- a prior statement that D-07 is deferred and unwired.

Examples, recommendations, and unselected options in earlier reports are **not**
approvals.

### 1.4 Implementation and configuration inspected

`bot/config.py`, `bot/app.py`, `bot/handlers.py`, `bot/outbox.py`, `bot/db.py`,
`bot/review/canary_linkage.py`, `bot/review/resolver.py`, `bot/review/worker.py`,
`bot/review/llm.py`, `bot/review/collector.py`, `bot/review/ci_contract.py`,
`bot/review/verdict.py`, `bot/review/report.py`, `bot/review/prompts.py`,
`bot/review/evidence.py`, `bot/review/github.py`, `.github/workflows/verify.yml`.

### 1.5 Credential/resource presence

Names only; no values printed.

| Item | Result |
|---|---|
| `.env` | absent |
| `REVIEWER_API_KEY` | not set |
| `REVIEW_GITHUB_TOKEN` | not set |
| `OPENHANDS_API_KEY` | present in runtime environment; not authorized by this task |
| `TELEGRAM_BOT_TOKEN` | not set |
| `REVIEW_*` / `REVIEWER_*` names | none |

Presence of a platform credential is not authorization and does not prove entitlement.

---

## 2. Preserved decisions and boundaries

- **D-01 B:** local `creation_jobs.repo` + exact `conversation_id`, bot-created
  conversations only, followed by GitHub numeric-ID/full-name verification. It does not
  establish historical identity continuity and does not authorize live operations.
- **D-02 Explicit-list:** owner-supplied explicit PR numbers only; no OpenHands
  `pr_number`, branch-name, PR-URL, or GitHub-search discovery.
- **Conversation-wide scope:** one active cycle per OpenHands conversation; immutable
  membership snapshot; multiple PRs are allowed by the general model.
- **R1:** exact-SHA verification workflow; the checked-out SHA must equal the requested
  SHA.
- **R3:** read-only GitHub evidence collection.
- **R4:** Blind and Adversarial stages remain separate; verdict precedence is
  deterministic.
- **R5:** lifecycle, lease/epoch, retry, and outbox behavior remain in force.
- **R6:** immutable report and owner-acceptance event remain separate from the technical
  verdict.
- **R7 remediation:** F-01/F-02/F-03 are fixed and tested; B-01/B-02/B-03 remain open.
- **`REVIEW_ENABLED=1`:** configuration validation only; not worker activation.
- **Autopush:** disabled/inactive.
- **R5 worker:** inactive.
- **Independent review:** deferred.
- **R8:** not started.

No approved decision is reopened. Any gap below is reported as a design/authorization
gap, not as a change to D-01, D-02, or conversation-wide scope.

---

## 3. D-03 — Authorization source

### 3.1 Decision status

`APPROVED` — `current-owner-revalidation` (owner approval 2026-11-26).

Implementation and live operations are not authorized by this policy approval. Existing
creation, resolver, callback, and owner-acceptance checks are implemented; the complete
lifecycle is not yet uniformly re-authorized, especially at execution and delivery.

### 3.2 Verified current facts

#### 3.2.1 Authorization chain

| Lifecycle point | Current check | Verified limitation |
|---|---|---|
| `Config.owner_id` | First and only `ALLOWED_TELEGRAM_ID`; `Config.is_allowed()` checks the allowed set | Single-owner model only; no multi-owner support |
| Private Telegram chat | `_allowed()` requires allowed user **and** `chat.type == "private"` | Group/private distinction is handler-level; direct service callers must enforce it |
| Telegram callback | `_review_owner_allowed()` checks allowed user, `user.id == Config.owner_id`, `effective_chat.id == cycle.chat_id`, and callback `message.chat_id == cycle.chat_id` | Not bound to exact Telegram `message_id`; another bot-sent copy in the same owner chat can be used |
| OpenHands conversation | `ConversationMembershipResolver._authorize()` requires an existing `watched` row with the same `chat_id` and rejects deleted conversations | Execution does not re-run this check |
| D-02 explicit PR list | `CanaryLinkageService.resolve()` checks `chat_id == owner_id`, validates unique positive PRs, and delegates to the resolver | Constructor owner is caller-supplied; no live factory binds it to `Config.owner_id` |
| Cycle creation | `reserve_conversation_review()` persists `chat_id`, immutable memberships, and one conversation-wide cycle | No explicit authorization snapshot beyond `chat_id` |
| Before Blind stage | `ReviewRunner._blind()` renews the lease and checks stored stage/evidence | No owner, watched, or deletion recheck |
| Before Adversarial stage | `ReviewRunner._adversarial()` renews the lease and checks stored stage/evidence | No owner, watched, or deletion recheck |
| Before report delivery | `schedule_auto_review_report_delivery()` uses persisted `cycle.chat_id`; `_post_claimed_review()` sends it | No current-owner check; no deletion-witness check in the review outbox path |
| After retry/restart | `cycle.chat_id` persists; lease token/epoch fences stale workers | Authorization is not rechecked after restart or retry |
| Revocation/owner change | New callbacks use current config; old outbox rows retain old `chat_id` | Active cycle can execute or deliver after owner change, unwatch, or deletion |
| Details resend | Handler rechecks owner/private/cycle chat; `send_details()` sends directly | No deletion/owner revalidation inside the send method; not idempotent |

#### 3.2.2 Forged, duplicated, delayed, and replayed identifiers

- Callback data is parsed strictly; review ID/version are checked against persisted rows.
- Accept/Reject is immutable after the first decision; duplicate decisions are stable.
- Details can be replayed and send another copy; it does not change the verdict.
- Lease token/epoch prevents two workers from completing the same cycle.
- No separate authorization token exists; authorization is derived from Telegram
  identity, cycle chat, and DB state.
- A delayed callback remains valid if the owner/chat/version still match.

#### 3.2.3 Durable binding

- `cycle.chat_id`, immutable memberships, provider snapshot, and owner decision are
  durable.
- The authorization decision itself is not a separate immutable record; it is implicit
  in `chat_id` and current config.
- Changing the owner configuration does not mutate existing cycles.

### 3.3 Unresolved question

Is the existing `watched.chat_id` + owner allowlist + callback checks sufficient for the
whole lifecycle, or must the current `Config.owner_id`, conversation ownership, and
deletion state be revalidated before each review stage and before report delivery?

### 3.4 Options

| Option | Trust boundary | Required code/config changes | Security guarantees / limitations | Tests | Migration | Operational risks |
|---|---|---|---|---|---|---|
| **A. `watched-chat-only`** | Creation-time `watched` + persisted cycle `chat_id` + callback-time config owner | None | Preserves current behavior; old cycle can execute/deliver after owner change, unwatch, or deletion; callback still rejects other chats/users | Existing callback/resolver tests; add owner-change/deletion tests | None | Revocation lag; old report may reach old chat |
| **B. `current-owner-revalidation` (recommended)** | Current `Config.owner_id` + persisted `cycle.chat_id` + current `watched`/deletion state | Bind factory to `Config.owner_id`; recheck before claim/process, before each stage, and before delivery; add review-outbox deletion/owner check; Details recheck | Fails closed after owner change/unwatch/deletion; no new trusted identifier; old cycles become manual | Owner change, unwatch, deletion, retry, restart, old outbox, callback replay | None | Stricter operation; manual new cycle after ownership change |
| **C. `OpenHands-owner-check`** | Add OpenHands account/service-owner verification in addition to Telegram/watched | New OpenHands metadata/API dependency; new authorization source; new tests | Stronger external ownership proof if reliable; introduces an unverified dependency and possible data exposure | Owner mismatch, unavailable, timeout; no cycle on failure | None for DB; new client behavior | Live dependency and ambiguous ownership |

### 3.5 Security implications

- Option A’s material risk is **revocation lag**: an active or delivery-pending cycle can
  still run or send after the owner changes or the conversation is removed.
- Option B closes that gap without adding a new identifier; it may block a legitimate
  cycle after a configuration change, which is intentional fail-closed behavior.
- Option C is not supported by verified local data; it would reopen the conversation-
  ownership question and should not be bundled with D-07.
- Exact-message binding remains absent; this is a low residual risk because callbacks
  must be owner/private/cycle-chat and bot-issued.

### 3.6 Operational risks

- Option B requires a documented manual recovery path when the owner changes.
- A deletion check at delivery may prevent a report from reaching the owner after the
  conversation is removed; that is safer than delivering stale content.
- Details resend remains non-idempotent unless separately fixed; it does not change the
  technical verdict.

### 3.7 Compatibility implications

- Option B is compatible with D-01 B, D-02 Explicit-list, conversation-wide scope,
  immutable memberships, R5 lease/outbox, and R6 owner acceptance.
- Option B requires no schema change.
- Option A preserves current code but leaves a live-canary authorization gap.
- Option C should be a separate decision if ever needed.

### 3.8 Selected/approved option

**`APPROVED` — Option B, `current-owner-revalidation` (owner approval 2026-11-26).**

### 3.9 Rationale

The creation and callback checks are sound, but a live canary must not execute or deliver
after the owner is revoked or the conversation is deleted. Revalidating current owner and
conversation state at execution and delivery closes the revocation gap without a schema
change or a new trusted identifier.

### 3.10 Exact owner approval statement

```text
D-03: current-owner-revalidation
```

If the owner wants to retain current behavior:

```text
D-03: watched-chat-only
```

### 3.11 Consequences of rejection

- Rejecting Option B keeps the revocation gap and requires D-07 to document that
  authorization is creation/callback-time only.
- Rejecting all options keeps D-03 open and live canary blocked.
- Option C rejection is acceptable; it is not required for the canary.

### 3.12 Consequences of deferral

- Had the owner deferred, the decision would remain `OWNER_DECISION_REQUIRED`; no live canary could begin. The owner did not defer D-03.
- The pack remains valid as a decision aid; no implementation may proceed.

### 3.13 Implementation tasks after approval

1. Bind the canary factory to `Config.owner_id`.
2. Add a revalidation helper for current owner, `watched.chat_id`, and deletion state.
3. Call it before claim/process, before each stage, and before report send.
4. Add a deletion/owner check to the review outbox path and Details send path.
5. Preserve lease/epoch checks and fail closed on mismatch.
6. Record authorization decisions and failures in the audit trail without secrets.

### 3.14 Required tests and verification

- Owner ID changed before execution.
- Watched row removed before execution.
- Conversation deleted before execution.
- Owner/chat mismatch at delivery.
- Retry and restart after owner change.
- Old outbox row after owner change.
- Callback from another user, group chat, another chat, and replayed callback.
- No provider/GitHub/Telegram call when revalidation fails.

---

## 4. D-04 — Durable repository provenance

### 4.1 Decision status

`APPROVED` — `canary-only-owner-attestation` (owner approval 2026-11-26).

`D-04b: persist-numeric-repository-id` is `DEFERRED` and not approved. No schema,
migration, column, index, trigger, or persistence implementation is authorized.
`creation_jobs` stores `repo` and `conversation_id`, not the GitHub numeric repository ID
observed at creation; current canary verification proves current GitHub identity, not
historical continuity.

### 4.2 Verified current facts

- `creation_jobs` columns: `id`, `chat_id`, `repo`, `text`, `status`, `task_id`,
  `conversation_id`, `error`, timestamps, `attempts`, `client_ref`, `notify_state`.
  There is no numeric repository ID column.
- `CreationJobRepositoryLinkSource` resolves the persisted `repo` name through GitHub now
  and returns the current numeric ID.
- `MembershipProvenance` is an in-memory result and is validated at reservation; no
  dedicated provenance table/column exists.
- `D-01 B` requires exactly one `done` job, owner chat, strict `owner/repo`, OpenHands
  `selected_repository` equality, and GitHub numeric-ID/full-name verification.
- D-01 B’s documented limitation remains: same-name deletion/recreation cannot be
  distinguished because no creation-time numeric ID is stored.
- Historical records without a numeric ID cannot prove continuity.
- Rename and transfer: numeric ID may survive, but D-05 still rejects authorization
  changes; D-04 B can detect continuity, not authorize a new owner/name.
- Numeric ID versus full name: the numeric ID is the stable technical identity; the full
  name is display/allowlist data and can change.
- Existing records: rows without a verified numeric ID are backward-compatible for
  reading, but they are not verified provenance.
- Records without verified identity must be rejected from any Canary that claims
  identity continuity.

### 4.3 Unresolved question

Must the canary require durable numeric repository identity, or may it proceed with an
explicit no-continuity limitation? Which records are eligible, and how must records
without verified identity be treated?

### 4.4 Options

| Option | Trust boundary | Required changes | Security guarantees / limitations | Tests | Migration | Operational risks |
|---|---|---|---|---|---|---|
| **A. No schema; documented limitation** | Current GitHub numeric ID + full name + creation job | None | Same-name delete/recreate is accepted as the new repository; no continuity claim | Existing canary tests plus explicit limitation/negative test | None | Canary must use a repository the owner attests was not recreated |
| **B. Persist numeric ID for future jobs** | Creation-time GitHub ID + current GitHub ID | Creation flow calls GitHub; additive nullable column or separate table; backfill policy | Detects same-name recreation for future jobs; existing NULL rows fail closed | Creation capture, NULL fail-closed, recreation, rename/transfer, immutability | New nullable column/table; no migration authorized now | Changes creation flow; historical records remain ineligible |
| **C. Canary-only owner attestation (narrow)** | Owner-attested canary manifest + current GitHub ID verification | No schema; record exact repository ID/full name, conversation ID, time, and no-recreation attestation in the audit package | No durable proof; bounded to one canary; false attestation remains possible | Manifest validation, mismatch, expiry, no-recreation statement | None | Manual attestation burden; canary-only |
| **D. Reject all provenance claims** | No continuity claim | None | Safest wording; may block canary | Negative tests/documentation | None | Live canary may be impossible |

### 4.5 Security implications

- Option A/C cannot distinguish a same-name recreated repository; this must be stated,
  not hidden.
- Option B reduces risk for future jobs but cannot repair existing rows; backfilling from
  current GitHub would falsely claim historical identity.
- Option B introduces a creation-time network dependency and a schema change.
- Option D is safest but blocks a live canary unless the owner accepts no continuity
  claim.

### 4.6 Operational risks

- Attestation is manual and can be wrong; it must be recorded with a time bound.
- A creation-time GitHub read can fail; the job must fail closed or remain canary-
  ineligible.
- Backward compatibility: existing rows have no numeric ID and must not be treated as
  verified.

### 4.7 Compatibility implications

- Option C is compatible with D-01 B, D-02 Explicit-list, and conversation-wide scope;
  it requires no schema change.
- Option B is the durable fix but requires a separate schema decision; it does not
  reopen D-01 B for existing records.
- D-05 remains reject-by-default regardless of provenance option.
- Records without verified identity must remain **ineligible for any Canary that claims
  identity continuity**; they may be used only under Option C with an explicit
  attestation and a no-continuity label.

### 4.8 Selected/approved option

**`APPROVED` — Option C, `canary-only-owner-attestation` (owner approval 2026-11-26).
Option B, `persist-numeric-repository-id`, is `DEFERRED` and not approved.**

### 4.9 Rationale

The task forbids schema changes, and existing records cannot be made historically
authoritative. A canary can proceed only with an explicit owner attestation and current
GitHub verification. Future creation jobs should capture numeric IDs under a separately
approved schema change.

### 4.10 Exact owner approval statement

```text
D-04: canary-only-owner-attestation
D-04b: persist-numeric-repository-id (future; separate schema approval)
```

If the owner accepts only the current limitation:

```text
D-04: no-schema-documented-limitation
```

### 4.11 Consequences of rejection

- Rejecting B leaves future same-name recreation risk and requires permanent
  attestation.
- Rejecting C while refusing B/D leaves no eligible canary path.
- Approving B without a migration plan leaves existing records ineligible and requires a
  separate schema task.

### 4.12 Consequences of deferral

- Had the owner deferred, `OWNER_DECISION_REQUIRED` would remain; a live canary would be
  blocked or labelled no-continuity. The owner did not defer D-04.
- No schema work may begin.

### 4.13 Implementation tasks after approval

1. Record the canary attestation: conversation ID, repository numeric ID/full name,
   timestamp, no-recreation statement, and owner reference.
2. Verify current GitHub numeric ID/full name before reservation and before execution.
3. For future B: add nullable numeric ID capture in the creation path; reject NULL for
   canary; add migration tests; never backfill historical rows as proof.
4. Reject malformed/mismatched/NULL provenance for canary continuity claims.
5. Do not add schema in this task.

### 4.14 Required tests and verification

- Same-name deletion/recreation with a new numeric ID.
- Rename and transfer behavior.
- Existing rows with NULL numeric ID.
- Malformed or missing repository ID.
- Attestation mismatch/expiry.
- Backfill must not create false historical continuity.
- No provider/GitHub call before provenance validation.

---

## 5. D-05 — Rename and transfer policy

### 5.1 Decision status

`APPROVED` — `reject-rename-transfer` (owner approval 2026-11-26).

Implementation is not authorized by this policy approval. Current behavior rejects
rename/transfer by default; no rename or transfer support is implemented.

### 5.2 Verified current facts

- `GitHubClient` rejects 3xx redirects; old-name redirects are not followed.
- Resolver requires numeric repository ID and canonical full-name match.
- `repository_id_mismatch` and `repository_rename_ambiguous` are explicit safe codes.
- The allowlist is name-based; numeric ID is verified after allowlisting.
- Active cycles store repository ID/full name and exact base/head SHAs.
- A rename/transfer during an active cycle can make branch/compare reads fail; the cycle
  fails closed and does not silently substitute.
- Numeric ID continuity does not authorize a new owner/name.

#### 5.2.1 Explicit policy cases

| Event | Recommended policy | Required evidence | Failure behavior | Owner override | Tests |
|---|---|---|---|---|---|
| Same-owner rename | Reject by default; require a new explicit cycle after owner reauthorization | New full name + same numeric ID + owner reauth + allowlist update | `repository_rename_ambiguous` / blocked; no auto-adopt | Only after explicit owner record; no automatic support | Rename before/during cycle; old/new name |
| Cross-owner transfer | Reject; numeric ID alone is insufficient | New owner authorization + new full name + allowlist + audit | Blocked; no transfer inheritance | Only with a new owner-approved policy and cycle | Same-ID transfer; new-ID transfer |
| Old-name redirect | Reject; do not follow 3xx | None; redirect is not evidence | `repository_rename_ambiguous` / malformed response; no follow | No | 301/302/307/308 |
| Unverifiable identity | Reject | Current GitHub numeric ID + canonical full name + allowlist | Blocked | No | 404/malformed/ambiguous |
| Active cycle during change | Stop/fail closed; do not deliver as current | Re-read repo/branch/compare; exact SHA | Blocked/manual; prior evidence remains bound to old ID/SHA but does not authorize new name/owner | Manual new cycle only | Rename/transfer between stages; delivery pending |

### 5.3 Unresolved question

May a repository rename or transfer be accepted when the numeric ID is unchanged, or must
the current reject-by-default policy remain?

### 5.4 Options

| Option | Trust boundary | Required changes | Security guarantees / limitations | Tests | Migration | Operational risks |
|---|---|---|---|---|---|---|
| **A. `reject-rename-transfer` (recommended/current)** | Numeric ID + canonical full name + allowlist; any change requires a new explicit cycle | None | No silent redirect/transfer; active cycles fail closed | Redirect, name/ID mismatch, active-cycle rename, allowlist | None | Canary must use a stable repository |
| **B. `accept-stable-id-with-owner-reauth`** | Same numeric ID + explicit owner reauthorization of new full name/allowlist | New policy/config, audit, active-cycle invalidation, revalidation | Can follow a legitimate rename/transfer, but ID alone is not authorization; risk of accepting a transferred repo | Rename/transfer with/without owner reauth; active cycle; audit | None | More operational complexity |
| **C. `accept-automatic`** | Numeric ID only | New redirect/ID policy | Not recommended: transfer can change control while ID stays | Extensive adversarial tests | None | High risk |

### 5.5 Security implications

- Accepting a numeric-ID match after transfer would let a new owner inherit review
  authorization; this is unacceptable without explicit reauthorization.
- Accepting redirects silently would break the exact-repository allowlist.
- Reject-by-default may require a new cycle after a legitimate rename; that is the safer
  operational cost.

### 5.6 Operational risks

- Active-cycle failure may leave a `delivery_pending` or blocked report requiring manual
  inspection.
- Previously collected evidence remains cryptographically bound to the old repository
  ID/SHA, but it does not authorize a new name/owner and must not be delivered as if
  current.
- A rename/transfer during a provider call cannot be prevented from completing that
  call; the supervisor must stop before completion/delivery.

### 5.7 Compatibility implications

- Option A is compatible with D-01 B, D-04 A/C, D-06, R1 exact-SHA, and R3 read-only.
- Option B would require D-03 revalidation and D-08 allowlist/owner updates; it does not
  change conversation-wide scope.
- No schema change is required for A.

### 5.8 Selected/approved option

**`APPROVED` — Option A, `reject-rename-transfer` (owner approval 2026-11-26).**

### 5.9 Rationale

Repository ownership is an authorization property, not only an identity property. A
stable numeric ID is necessary but not sufficient. The current reject-by-default behavior
is the correct canary policy.

### 5.10 Exact owner approval statement

```text
D-05: reject-rename-transfer
```

### 5.11 Consequences of rejection

- Rejecting A and choosing B requires an owner reauthorization workflow and more tests.
- Choosing C is not recommended and would require a separate security design.
- Rejecting all options keeps D-05 open and live canary blocked.

### 5.12 Consequences of deferral

- Had the owner deferred, current reject-by-default behavior would remain; D-05 is now
  `APPROVED` as `reject-rename-transfer`.
- No rename/transfer support may be implemented.

### 5.13 Implementation tasks after approval

1. Preserve current 3xx rejection and name/ID mismatch behavior.
2. Add explicit active-cycle invalidation on repository change.
3. Ensure prior evidence is not presented as current after a change.
4. If B is ever chosen, require explicit owner reauthorization and a new cycle.

### 5.14 Required tests and verification

- 301/302/307/308 old-name redirect.
- Same-ID rename with new/old name.
- Cross-owner transfer with same/new ID.
- Active cycle rename/transfer before/after a stage.
- Delivery-pending cycle after repository change.
- Unverifiable/malformed repository identity.

---

## 6. D-06 — Repository eligibility

### 6.1 Decision status

`APPROVED` — `private-allowlisted-only` (owner approval 2026-11-26).

Implementation is not authorized by this policy approval. Fork PRs and cross-repository
PRs are rejected; repository-level fork/archived/private eligibility is not yet explicit,
and deleted/recreated/visibility/ownership changes are not fully modeled.

### 6.2 Verified current facts

- `RepositoryIdentity` contains `repository_id`, `full_name`, `owner_id`, `owner_login`,
  `private`, `fork`, `archived`, and `default_branch`.
- `PullRequestIdentity` contains base/head repository IDs and full names.
- Resolver requires `pr.repository_id`/full name, `base_repository_id`/full name, and
  `head_repository_id`/full name all equal the verified repository.
- Different head repository → `pr_fork_ambiguous`; another base → `pr_repository_mismatch`.
- Closed/merged PR → `pr_not_open`.
- `fork`, `archived`, and `private` are parsed but not used for eligibility.
- Deleted/recreated repositories are not distinguishable without D-04.
- Visibility/ownership changes are not separately modeled; the allowlist is name-based
  and the owner is not part of repository identity.

#### 6.2.1 Category policy table

| Category | Recommended default | Required evidence | Failure behavior | Owner override | Tests |
|---|---|---|---|---|---|
| **Fork PR** | Reject | Head repository ID/name must equal verified repository | `pr_fork_ambiguous`; no provider | No for this canary | Fork PR with matching/different base |
| **Cross-repository PR** | Reject | Base/head IDs/names all equal verified repository | `pr_repository_mismatch`; no provider | No | PR from another repo |
| **Fork repository (`is_fork=true`)** | Reject | Explicit owner-approved fork policy; not present | Eligibility rejected | Only with a separate approved policy | Fork repository allowlisted |
| **Archived repository** | Reject | Not archived; owner approval if ever allowed | Eligibility rejected | No for this canary | Archived flag true |
| **Private repository** | Allow only if explicitly allowlisted and D-08 egress approved | Numeric ID/full name + allowlist + owner egress approval | Reject if not allowlisted/approved | Yes, explicit allowlist + egress only | Private allowlisted/non-allowlisted; egress missing |
| **Deleted repository** | Reject | Current GitHub read succeeds and identity matches | 404/identity failure; no provider | No | Deleted before/during cycle |
| **Recreated repository** | Reject for continuity; new ID required | Prior verified numeric ID (D-04 B/C) and no recreation | New ID mismatch; no provider | Only under D-04 attestation with no-continuity label | Same-name new ID |
| **Visibility change** | Reject; require new owner approval | Current visibility + explicit reapproval | Blocked/manual; no silent change | Yes, only with new approval | Private→public / public→private |
| **Ownership change** | Reject; require new owner/allowlist authorization | New owner authorization + full name + ID | Blocked; no transfer inheritance | Yes, only with new approval | Transfer same/new ID |

### 6.3 Unresolved question

Which repository categories are eligible beyond the current fork/cross-repo rejection:
fork repositories, archived, private, deleted, recreated, visibility changes, and
ownership changes?

### 6.4 Options

| Option | Trust boundary | Required changes | Security guarantees / limitations | Tests | Migration | Operational risks |
|---|---|---|---|---|---|---|
| **A. `reject-all-nonstandard`** | Explicit allowlist + non-fork + non-archived + stable ownership/visibility + no recreation | New eligibility checks | Most conservative; may block a legitimate private test repository | Each category reject | None | Canary may be impossible if only private repo exists |
| **B. `private-allowlisted-only` (recommended)** | Explicit allowlist + private allowed + D-08 egress approval; reject all other nonstandard categories | Add private eligibility and explicit allowlist/egress checks | Allows a private test repo without broadening to forks/archived/transferred repos | Private allowlisted/non-allowlisted, public, archived, fork, deleted, recreated, visibility/ownership | None | Private code leaves to provider; owner must approve egress |
| **C. `approve-fork-policy`** | Explicit fork PR/repository policy | New fork identity/authorization model | High risk; forks are different repositories/control domains | Extensive fork/transfer tests | None | Not recommended for R7 canary |

### 6.5 Security implications

- Technical identity (numeric ID/full name) must not be conflated with authorization
  (owner/allowlist/egress).
- A private repository does not change identity but changes data exposure; provider
  egress must be approved.
- Archived repositories are read-only but still contain code; reject for the canary.
- Deleted/recreated repositories need D-04; visibility/ownership changes need explicit
  reapproval.
- Fork repositories and fork PRs are different control domains; reject by default.

### 6.6 Operational risks

- A private-only test repository may be blocked under Option A.
- Option B requires a per-canary allowlist and egress record; a generic public allowlist
  is not sufficient.
- Visibility/ownership changes may be invisible in cached metadata; re-read current
  GitHub identity before execution.

### 6.7 Compatibility implications

- Option B preserves fork/cross-repo rejection and D-01/D-02; it only allows a private
  repository when explicitly allowlisted and approved.
- Option B depends on D-08 data-egress approval and D-03 owner revalidation.
- Option A is compatible but stricter.
- No schema change.

### 6.8 Selected/approved option

**`APPROVED` — Option B, `private-allowlisted-only`, with explicit rejection of fork PRs,
cross-repository PRs, fork repositories, archived repositories, deleted/recreated
repositories, and visibility/ownership changes (owner approval 2026-11-26).**

### 6.9 Rationale

A private disposable test repository is the most realistic canary target, but it must be
explicitly allowlisted and its code egress approved. Forks and transferred repositories
must not inherit eligibility.

### 6.10 Exact owner approval statement

```text
D-06: private-allowlisted-only + reject-fork-cross-repo-archived-deleted-recreated
```

If the owner wants maximum conservatism:

```text
D-06: reject-all-nonstandard
```

### 6.11 Consequences of rejection

- Deferral keeps current behavior; live canary remains blocked until the private-repo
  policy and egress are approved.
- Choosing A may block the canary if the test repository is private.
- Choosing C is not recommended and requires a separate fork/security design.

### 6.12 Consequences of deferral

- Had the owner deferred, `OWNER_DECISION_REQUIRED` would remain and no eligibility
  broadening could be implemented. D-06 is now `APPROVED` as `private-allowlisted-only`.
- The canary must use a repository already satisfying the current conservative checks
  and D-04 provenance.

### 6.13 Implementation tasks after approval

1. Add explicit eligibility checks for repository `fork`, `archived`, and `private`.
2. Require explicit allowlist membership; do not infer eligibility from visibility.
3. Reject deleted/recreated/ownership/visibility changes; require new owner reapproval.
4. Record the eligibility decision and evidence in the audit package.
5. Do not silently broaden the eligible repository set.

### 6.14 Required tests and verification

- Fork PR and cross-repository PR.
- Fork repository with `is_fork=true`.
- Archived repository.
- Private allowlisted and private non-allowlisted.
- Deleted and same-name recreated repository.
- Visibility change and ownership transfer.
- No provider call for any ineligible category.

---

## 7. D-07 — Bounded Canary Supervisor

### 7.1 Decision status

`APPROVED_DESIGN_ONLY` — `approve-bounded-canary-supervisor-design` (owner approval
2026-11-26).

The design is approved. Implementation and runtime activation are **not authorized** and
require separate explicit authorization. The bounded design exists; the supervisor is not
implemented. The current R5 worker is not safe for one-canary activation.

### 7.2 Verified current facts

- `claim_auto_review()` selects any eligible conversation-wide cycle ordered by `id`;
  there is no review/conversation/repository filter.
- `ReviewWorker._claim()` calls that broad claim; there is no exact-cycle mode.
- `ReviewWorker` inherits `_BaseWorker._run()`, an unbounded loop; there is no one-shot
  mode.
- `reserve_conversation_review()` is conversation-wide; it merges pending membership
  rows from the conversation. A one-PR canary can become multi-PR if pending rows exist.
- `ReviewRunner.run()` loops over all memberships; `_blind`/`_adversarial` build all
  requests; `_execute_requests()` calls the provider for every request.
- `MAX_CHUNKS = 20` per stage; `execute_stage()` allows one correction per request.
- `ReviewWorker` retryable failure enters `retry_wait`; `max_attempts` default 5, DB
  allows 1–20.
- `ReviewRunner`/`ReviewWorker` have no provider-call budget or token budget.
- `ReviewReportService.prepare()` creates an outbox intent; the outbox worker is started
  by `bot/app.py`, not by a standalone supervisor.
- `_post_claimed_review()` handles report delivery with at-most-once CAS; ambiguous
  Telegram errors become `unknown`.
- Lease token/epoch fencing exists; `_BaseWorker.stop()` cancels but does not release the
  lease.
- `REVIEW_CI_TIMEOUT_MIN` is unused; `REVIEW_MAX_INPUT_CHARS` is not wired into a factory.

### 7.3 Unresolved question

Are the proposed limits sufficient and internally consistent to authorize a one-shot
canary supervisor without any risk of processing another cycle, exceeding four provider
calls, retrying unexpectedly, or delivering after revocation/expiry?

### 7.4 Options

| Option | Trust boundary | Required changes | Security guarantees / limitations | Tests | Migration | Operational risks |
|---|---|---|---|---|---|---|
| **A. `keep-deferred` (current)** | No worker activation | None | No live risk; R7 live remains blocked | None | None | No canary |
| **B. `approve-bounded-canary-supervisor-design` (recommended)** | Exact cycle + exact owner/repo/PR + one-shot + budget + lease + outbox + audit | New supervisor, exact claim, budget wrapper, stage-request guard, delivery step, expiry checks | Bounded but requires careful implementation; no app wiring | Full negative/positive test plan below | None for DB | Implementation effort; strict fail-closed |
| **C. `approve-unbounded-worker`** | Broad claim + loop + no budget | None/new wiring | Not safe: unrelated cycles, excessive calls, retries | Not acceptable | None | Reject |

### 7.5 Security implications

- Four calls are sufficient only for one request per stage with at most one correction
  each; any multi-chunk stage must abort before provider, not chunk.
- A one-PR canary must explicitly reject pending membership rows; otherwise the
  conversation-wide reservation can include extra PRs.
- An exact claim filter is mandatory; isolated DB alone is not sufficient proof.
- Expiry must be checked before every provider call and before renewal; an expired lease
  can be taken over.
- A standalone supervisor must perform one explicit outbox delivery step or use an
  outbox worker; otherwise the report remains pending.
- No automatic retry after a provider timeout/ambiguous response; no repair loop.
- `max_tokens`/monetary ceiling is a D-08 dependency.

### 7.6 Operational risks

- A provider timeout after sending may have incurred an unknown charge; no retry.
- Lease expiry during an in-flight provider call cannot cancel the remote request; the
  supervisor must stop after it returns and must not complete/deliver.
- A crash after provider response but before persistence is ambiguous; manual audit.
- A standalone report may remain `delivery_pending` if no delivery step exists.
- A stale cycle may be claimed if exact claim is not enforced.

### 7.7 Compatibility implications

- Option B preserves conversation-wide scope with exactly one membership for the canary.
- It preserves D-01 B and D-02 Explicit-list; it does not add PR discovery.
- It preserves R1 exact-SHA, R3 read-only, R4 two-stage separation, R5 lease/outbox, and
  R6 report/owner acceptance.
- It does not wire into `bot/app.py`; no production worker starts.
- No schema change.

### 7.8 Selected/approved option

**`APPROVED_DESIGN_ONLY` — Option B design, with the mandatory implementation corrections
in §7.13 (owner approval 2026-11-26). Implementation and activation are not authorized.**

### 7.9 Rationale

The design is directionally sufficient, but it is not sufficient as written until exact
claim, one-PR preflight, four-call budget, stage-request guard, expiry, explicit outbox
delivery, audit, no-retry, and D-03 revalidation are explicit. The current R5 worker
cannot be reused as-is; it needs a separate one-shot supervisor wrapper.

### 7.10 Exact owner approval statement

```text
D-07: approve-bounded-canary-supervisor-design
```

This approves the **design only**. Implementation requires a separate authorized task
after D-03–D-08 are recorded.

### 7.11 Consequences of rejection

- Deferral keeps `ReviewWorker` inactive and live R7 blocked.
- Choosing A preserves safety but leaves no canary path.
- Choosing C is rejected: it can process unrelated cycles and exceed cost/authorization
  limits.

### 7.12 Consequences of deferral

- Had the owner deferred, `OWNER_DECISION_REQUIRED` would remain and no supervisor code
  could be written or started. D-07 is now `APPROVED_DESIGN_ONLY`.
- The existing R5 worker remains inactive.

### 7.13 Bounded implementation proposal and issue analysis

#### 7.13.1 Exact cycle selection

Required: exact `review_id` claim plus conversation/chat/provider-snapshot checks, or a
DB filter with the same fields. Never call `_BaseWorker._run()` or broad `_claim()`.
Test: two eligible cycles; exact claim of B leaves A untouched; wrong cycle returns
`None`; no provider call.

#### 7.13.2 One PR versus conversation-wide scope

Conversation-wide scope is preserved; the canary is a one-membership instance.
`reserve_conversation_review()` merges pending memberships; preflight must reject any
pending row or `membership_count != 1`. Test: one PR succeeds; pending second PR causes
preflight abort before provider; no membership mutation.

#### 7.13.3 Four calls versus Blind/Adversarial

Blind = one initial + at most one correction = 2. Adversarial = one initial + at most one
correction = 2. Total = 4. Four is sufficient only if each stage emits one request. If
either stage emits more than one request, abort before that stage’s provider call; do not
chunk. Test: exactly 4 calls on two invalid-then-corrected responses; 5th call refused.

#### 7.13.4 Input exceeds one chunk

`MAX_CHUNKS = 20` exists; the canary must set `max_input_chars=20,000` and abort if
`build_*_requests()` returns more than one request. Evidence collection may reject an
oversized/truncated diff before prompt building; that is a pre-provider abort. Test:
oversized diff → no provider call; multi-chunk builder → no provider call.

#### 7.13.5 Retries versus provider budget

Current worker retries retryable failures up to `max_attempts`; canary must set
`max_attempts=1`. The supervisor must not loop, reclaim, or repair; a retryable error
becomes terminal for the canary. The budget wrapper must count correction calls and must
not reset on retry. Test: provider error → one attempt, no second claim, no 5th call.

#### 7.13.6 Provider timeout and ambiguous response

Adapter timeout is 20s default, 120s maximum; `execute_stage()` returns `provider_error`.
A timeout after the request may be ambiguous; do not retry. `ReviewWorker` may mark
retryable; supervisor must stop and leave audit state. Telegram ambiguity is `unknown`,
never `sent`; no auto retry. Test: timeout, 429, 5xx, malformed response, invalid schema →
stop; no fallback.

#### 7.13.7 Lease expiration during a provider call

The supervisor must check `now < expires_at` before every provider call and renewal. It
must not renew after expiry. If the lease expires during a call, the call may still be
charged; after it returns, stop without completion or delivery. A second supervisor may
take over only after expiry; it must revalidate exact cycle/owner and must not resume an
ambiguous provider call. Test: expiry before claim, between stages, and during a provider
call; no completion after lease loss.

#### 7.13.8 Worker shutdown and restart

`_BaseWorker.stop()` cancels; no lease release. Before a provider call: release the lease
on a clean abort. After a provider call: leave the lease to expire; no automatic retry;
manual audit. Restart is manual; no auto-resume; exact claim and expiry rechecked. Test:
cancel before provider; cancel after provider; restart with active/expired lease; no
duplicate provider call.

#### 7.13.9 Duplicate and out-of-order events

Lease token/epoch prevents two workers. Stage/evidence/outbox idempotency remains.
One-shot supervisor never claims a second cycle. A new PR observed during an active cycle
is pending and does not mutate membership. Accept/Reject is idempotent; Details can
duplicate but does not mutate. Test: duplicate supervisor start, duplicate claim,
duplicate callback, duplicate report outbox, new PR during cycle.

#### 7.13.10 Proof the supervisor cannot process a second cycle

Exact claim returns only the configured `review_id`. The supervisor asserts
`claim.review_id == config.review_id`, `claim.conversation_id == config.conversation_id`,
`claim.chat_id == config.owner_id`, and exact repository/PR/snapshot. It never constructs
a broad worker loop. Test: an unrelated eligible cycle remains `queued` with no lease,
attempt, or provider call; the exact cycle is the only one touched.

#### 7.13.11 Token and output limits

The current adapter has no `max_tokens`, input-token accounting, usage ledger, or pricing.
The four-call budget is a call-count bound, not a token or monetary bound. D-08 must
supply a provider-side hard spend cap or an explicit bounded-exposure acceptance. If the
provider supports `max_tokens`, the implementation must add it with tests; if not, no
token ceiling may be claimed.

#### 7.13.12 Report and outbox failure

Verdict is durable before report preparation; report/outbox failure leaves
`delivery_pending`. A standalone supervisor must perform one explicit claimed delivery
or document a separately authorized outbox worker. Ambiguous Telegram delivery remains
`unknown`; never `sent`. Missing report/version fails closed. Test: report build failure,
save failure, outbox insert failure, ambiguous Telegram, duplicate delivery.

#### 7.13.13 Audit evidence for exact cycle and SHA

Use existing durable rows: `auto_reviews`, `auto_review_memberships`,
`auto_review_evidence`, `auto_review_stages`, `auto_review_leases`,
`auto_review_reports`, `outbox`, and `auto_review_owner_acceptance`. Add a local
append-only canary audit note with canary ID, owner approval reference, exact config,
preflight result, provider call count, lease epochs, exact review ID/SHA, and stop reason.
No schema change is proposed.

#### 7.13.14 Reuse versus separate wrapper

The current R5 `ReviewWorker` cannot safely be reused as-is because of broad claim,
unbounded loop, no budget, no exact expiry, and no standalone delivery. A separate
one-shot `CanaryReviewSupervisor` wrapper is required. It may reuse `ReviewRunner` stage
primitives and existing DB/report/outbox components, but not `_BaseWorker._run()`.

#### 7.13.15 Hard safety invariants

- Exact review ID/cycle only; no broad claim.
- Exactly one PR membership; no pending membership merge.
- Exactly one request per stage; otherwise abort before provider.
- At most four provider calls; budget counts corrections.
- One attempt; no retry, fallback, provider switch, or repair.
- Owner/conversation/deletion revalidation before execution and delivery.
- Expiry checked before every provider call and renewal.
- Lease fencing; no completion after lease loss.
- No production DB, app wiring, or background polling.
- Ambiguous provider/Telegram outcomes are never reported as success.

#### 7.13.16 Configurable limits

- Max provider calls: 4.
- Max requests per stage: 1.
- Max PRs: 1.
- Max attempts: 1.
- Max input chars: 20,000.
- Expiry timestamp.
- Lease seconds (bounded by existing 1–3600).
- Provider/response byte limits (existing adapter defaults).

#### 7.13.17 Operational assumptions

- The isolated DB contains only the canary cycle.
- No pending memberships exist.
- The provider supports the selected model and the owner supplies a spend cap.
- The owner is available to receive the report and decide.
- A human operator will audit any ambiguous/expired state.

#### 7.13.18 Unresolved owner decisions

D-03 authorization, D-04 provenance, D-05 rename/transfer, D-06 eligibility, D-07
design/implementation, and D-08 resources/spend cap. None is approved here.

### 7.14 Comprehensive local test plan

- Unit: config validation, expiry, owner mismatch, repo/PR/snapshot mismatch.
- DB: exact claim, wrong cycle, second claim, pending membership, membership count.
- Provider: 4-call cap, correction counting, 5th-call refusal, no fallback.
- Prompt: multi-chunk abort, oversized diff abort.
- Lifecycle: lease loss, expiry before/during provider, shutdown before/after provider,
  restart.
- Delivery: one outbox intent, ambiguous Telegram `unknown`, no false `sent`, report
  failure.
- Authorization: owner change/unwatch/deletion before execution/delivery.
- Negative: no OpenHands/GitHub/provider/Telegram call during preflight.
- Audit: append-only record with exact config, call count, lease epochs, exact SHA, stop
  reason.

---

## 8. D-08 — Live resources and permissions

### 8.1 Decision status

`APPROVED_BLOCKED` — `keep-blocked` (owner approval 2026-11-26).

Live Canary remains blocked. This approval does not authorize obtaining or creating any
resource. No live resource is authorized; no resource was created, tested, or used.

### 8.2 Verified current facts

- `.env` absent; no `REVIEWER_API_KEY`; no `REVIEW_GITHUB_TOKEN`; no
  `TELEGRAM_BOT_TOKEN`; no review env names.
- `OPENHANDS_API_KEY` is present in the runtime environment but is not authorized by this
  task and its scopes cannot be proven.
- No disposable OpenHands conversation, test repository/branch/PR, Actions run, provider
  entitlement, pricing visibility, spend cap, Telegram test target, or isolated DB is
  authorized.
- No external call, inference, message, or data transmission occurred.

### 8.3 Unresolved question

Which exact resources and permissions may be used for a future live canary, and what are
their cost, data-egress, isolation, cleanup, and evidence terms?

### 8.4 Options and resource matrix

| Option | Trust boundary | Required changes | Security guarantees / limitations | Tests | Migration | Operational risks |
|---|---|---|---|---|---|---|
| **A. `keep-blocked` (recommended now)** | No live resources | None | No live risk; canary remains blocked | None | None | No live validation |
| **B. `authorize-live-resources`** | Owner-specified identities, least privilege, spend cap, cleanup | Provision exact resources; verify permissions; isolated DB; dry run | Live code/data leaves; provider cost; Telegram delivery | Read-only permission checks; local dry run; live canary checklist | None | Cost, data exposure, cleanup |
| **C. `reject-for-now`** | No live resources | None | No live risk; closes canary | None | None | No canary |

| Resource | Current availability | Required identity | Minimum permissions | Cost/credit exposure | Data leaving local environment | Isolation | Cleanup/revocation | Evidence before use |
|---|---|---|---|---|---|---|---|---|
| Disposable OpenHands conversation | Missing/unauthorized | Dedicated test workspace/account and exact conversation ID | Create, read, send message, read events, delete; repository selection limited to test repo | OpenHands usage/sandbox may incur cost; amount unknown | Controlled task text, selected repository/branch, conversation metadata; agent changes in test repo | One dedicated conversation; not production chat | Delete conversation; revoke test key; verify deletion | Exact conversation ID, test identity, deletion proof |
| Disposable test repository or isolated branch | Missing | Dedicated repo owner; exact numeric ID/full name; branch `agent/r7-canary-*` | Contents: Write; Pull requests: Write; no production repo | GitHub Actions minutes may incur cost | Test code/diff/PR metadata; CI logs/artifacts | Dedicated private/public repo; protected main; no production repo | Delete branch/PR/repo; revoke write token | Repo ID/name, branch/PR IDs, cleanup proof |
| GitHub read token | Missing (`REVIEW_GITHUB_TOKEN` absent) | Dedicated fine-grained token | Metadata: Read, Contents: Read, Pull requests: Read, Actions: Read; only test repo | No direct token cost | Repository/PR/branch/compare/Actions metadata and diff content | Repository-scoped; read-only | Revoke token; confirm no other repo access | Token scope evidence, repo-only access |
| GitHub branch/PR write permissions | Missing | Separate setup identity/token | Contents: Write; Pull requests: Write; only test repo | No direct token cost; Actions may cost | Test branch/PR content and metadata | Separate from review token; test repo only | Delete branch/PR; revoke token | Write scope evidence, named branch/PR |
| GitHub Actions execution | `verify.yml` present but untracked; never run remotely | Test repo workflow identity | Workflow dispatch: Actions: Write (classic may need `workflow`); workflow itself `contents: read` | Runner minutes may incur cost | Test code, workflow logs/artifacts | Only test repo/branch; exact SHA | Delete runs/artifacts; disable/delete workflow if needed | Run ID, exact SHA, logs |
| Reviewer provider credentials | Missing | Dedicated provider key/model | Inference on selected model only | Per-token/per-request cost unknown | Redacted diff, CI metadata, instructions, Blind output, OpenHands report | Dedicated key; no production data | Revoke key; confirm no residual access | Key scope, model identity, no production data |
| Provider/model entitlement | Unverified | Exact provider/model identity | Entitled inference; no catalog inference | Yes, unknown | Same as provider payload | Dedicated model/key | Remove key; verify billing stop | Provider confirmation or owner acceptance |
| Provider pricing and usage visibility | Missing | Owner billing account | Read usage/pricing; no inference required | No direct cost | No local data; usage metadata | Owner-only | Revoke read access | Price/usage evidence |
| Hard monetary exposure ceiling | Missing | Owner/billing owner | Provider-side hard cap or written bounded exposure | Yes, capped by owner | No local data | Provider/account level | Lower/remove cap after canary | Cap value or signed bounded-exposure acceptance |
| Token and call limits | Partial: byte/time limits exist; 4-call is design-only | Canary config/operator | Enforce 4 calls, 1 request/stage, 1 attempt, max input 20k; no `max_tokens` currently | Bounded calls do not bound token cost | Same as provider payload | Supervisor budget wrapper | Stop after canary; audit call count | Exact config, call ledger |
| Telegram test target | Missing (`TELEGRAM_BOT_TOKEN` absent) | Bot + owner private chat; exact owner ID | `send_document`, receive callbacks; private chat only | No direct Telegram cost | Report document, summary, buttons, owner decision | Owner private chat; no group/channel | Delete messages; revoke bot token if dedicated | Owner chat ID, bot identity, delivery proof |
| Isolated local database | Missing | Dedicated SQLite path outside production | Local read/write; no production DB | No external cost | Local DB contains cycle/stages/evidence metadata/report; no raw diff | Separate file; WAL/-shm copied together | Backup/retain per policy; delete after audit; never copy production | Path proof, no production rows |
| Cleanup and credential revocation | Missing | Owner/operator | Revoke tokens, delete resources, verify | Cleanup may have minor cost | None if done correctly | N/A | Checklist with evidence | Cleanup log and post-cleanup verification |

### 8.5 Security implications

- Provider data egress includes source code (redacted diff), CI metadata, and the
  OpenHands report; private repository data must be explicitly approved.
- GitHub write permissions are separate from review read permissions; do not reuse the
  review token.
- OpenHands API key may be account-wide; use a dedicated test identity if possible.
- Telegram report delivery is external and at-most-once; ambiguous delivery remains
  `unknown`.
- Without a hard spend cap, provider cost is unbounded in principle.
- Cleanup must be proven; deleting local DB without revoking keys is insufficient.

### 8.6 Operational risks

- Live resources can create cost and data exposure before the canary is ready.
- Actions minutes, OpenHands sandbox time, and provider tokens are all potentially
  billable.
- A token with broader scope than intended can access production repositories.
- A missing cleanup leaves credentials/resources active.

### 8.7 Compatibility implications

- Option B depends on D-03 owner revalidation, D-04 provenance, D-05 reject-rename, D-06
  eligibility, and D-07 bounded supervisor.
- Option A preserves safety and blocks live validation.
- No schema change is required for resource setup; local DB is a file, not a schema
  change.

### 8.8 Selected/approved option

**`APPROVED_BLOCKED` — Option A, `keep-blocked`, until every resource and condition below
is supplied; then Option B may be authorized in stages (owner approval 2026-11-26).**

### 8.9 Rationale

No live resource currently exists, and provider cost/egress is unbounded. Keeping the
canary blocked is the only honest readiness state.

### 8.10 Exact owner approval statement

Current safe choice:

```text
D-08: keep-blocked
```

Future live authorization must list exact non-secret identifiers and conditions:

```text
D-08: authorize-live-resources
OpenHands conversation ID: <exact>
GitHub repository: <owner/repo> (ID <numeric>)
GitHub branch/PR: <exact>
Review token scope: Metadata/Contents/Pull requests/Actions Read only
Write token: <separate> Contents/Pull requests Write only for setup
Provider/model: <provider>/<model>
Provider spend cap: <hard cap or bounded exposure>
Telegram owner chat: <exact owner private chat>
Isolated DB path: <exact path outside production>
Cleanup/revocation: <exact plan>
```

No secrets belong in the approval record.

### 8.11 Consequences of rejection

- Option A/deferral keeps live R7 blocked; no data or cost exposure.
- Option B without a spend cap/egress approval is not authorized.
- Option C closes the canary path.

### 8.12 Consequences of deferral

- Had the owner deferred, `OWNER_DECISION_REQUIRED` would remain and no resource could be
  created or used. D-08 is now `APPROVED_BLOCKED`.
- D-07 implementation can be planned but not live-tested.

### 8.13 Staged resource-approval process

1. **Stage 0 — keep blocked:** no credentials/resources.
2. **Stage 1 — local dry run:** fakes only; isolated DB; no external call.
3. **Stage 2 — read-only GitHub:** test repo/token; verify permissions and exact SHA.
4. **Stage 3 — disposable OpenHands:** test conversation; no provider.
5. **Stage 4 — provider dry run:** owner-approved entitlement and spend cap; one call
   maximum or fake transport.
6. **Stage 5 — single live canary:** all D-03–D-08 approved; bounded supervisor.
7. **Stage 6 — cleanup:** revoke/delete and verify.

### 8.14 Required tests and verification

- Presence/scope checks without printing values.
- Read-only GitHub access limited to test repo.
- No write token used by review client.
- Provider entitlement confirmed by owner/provider, not by inference.
- Spend cap/usage evidence recorded.
- Telegram owner-only delivery and callback.
- Isolated DB contains no production rows.
- Cleanup/revocation evidence.

---

## 9. Provider cost and data-egress consistency

This section reconciles D-07 and D-08 with
`docs/reviews/OHB2-R7-PROVIDER-COST-AND-DATA-EGRESS-REPORT-20261125.md`.

### 9.1 Current provider controls and gaps

| Control | Current fact | D-07/D-08 implication |
|---|---|---|
| Entitlement | No confirmed reviewer entitlement; catalog visibility is not proof | Live inference remains blocked until provider/owner confirms |
| Pricing | No confirmed pricing table or price per model | No known monetary cost |
| Balance/usage API | No reliable balance/usage API in this implementation | No local spend visibility |
| Hard monetary ceiling | None | Four calls do not bound money |
| `max_tokens` | Not sent by the adapter | No output-token ceiling |
| Token accounting | No input/output token ledger | No token cost estimate |
| Request/response bytes | Request default 256 KiB/max 2 MiB; response default 1 MiB/max 4 MiB | Byte bounds only |
| Timeout | 20s default, 120s maximum | A timeout may still incur provider charge |
| Provider retries | None; one schema correction per stage | Four calls includes corrections, not provider retries |
| Worst-case calls | 20 chunks/stage × 2 stages × 2 with correction = 80/PR; 20 PRs = 1,600; retries multiply | Current worker is not a safe canary runner |
| Four-call canary | Blind 1 + correction 1 + Adversarial 1 + correction 1 | Real call bound only if one request/stage and no retry/fallback |
| Retry/ambiguous outcomes | Current worker can retry retryable failures; provider timeout may be ambiguous | Canary must set max_attempts=1 and never retry |
| Data egress | Redacted diff, CI metadata, instructions, Blind output, OpenHands report | Private code/egress requires explicit approval |
| Redaction | Pattern-based; no entropy detector | High-entropy secrets not matching a pattern can pass |

### 9.2 Required reconciliation statements

- The four-call limit is a **call-count hard bound** only when the supervisor enforces one
  request per stage, one correction per request, one attempt, no retry, no fallback, and
  no provider switch.
- Four calls **do not** imply a known maximum monetary cost because token counts, pricing,
  and provider billing are unknown.
- A provider timeout, connection reset, or malformed/ambiguous response can still cause a
  charge; the supervisor must not retry and must record the ambiguity.
- A schema correction is an additional provider call and must be counted.
- If input exceeds one chunk, the supervisor must abort before provider; chunking would
  exceed the four-call envelope.
- No `max_tokens` support means no output-token ceiling can be claimed.
- Live inference must remain blocked unless the owner supplies a provider-side hard spend
  cap or an explicit written bounded-exposure acceptance with call/input limits.
- Even with a hard spend cap, the owner must approve data-egress and retention terms.
- Redaction is not a guarantee that no secret leaves; it is a best-effort pattern filter.

---

## 10. Cross-decision consistency review

### 10.1 Consistency matrix

| Decision / invariant | Consistency | Notes |
|---|---|---|
| D-01 B | Preserved | Bot-created conversation + exact `conversation_id` + `creation_jobs.repo`; no all-conversation claim |
| D-02 Explicit-list | Preserved | Owner-supplied PR numbers; no discovery |
| Conversation-wide scope | Preserved | One active cycle; one-PR is a canary envelope, not a new scope |
| One active cycle per conversation | Preserved | `reserve_conversation_review()` remains authoritative |
| R1 exact-SHA | Compatible | Exact requested/checked-out SHA; membership SHA verified |
| R3 read-only GitHub | Compatible | Review path read-only; setup writes use separate token |
| R4 Blind/Adversarial | Compatible with 4-call envelope | One request per stage; one correction each |
| R4 deterministic verdict | Compatible | No model vote/fallback; fixed precedence |
| R5 lifecycle/lease/outbox | Gap | Exact claim and standalone delivery step are required |
| R6 report/owner acceptance | Compatible | Immutable report; owner decision separate |
| R7 remediation F-01/F-02/F-03 | Compatible | CI completeness, provider binding, branch/SHA revalidation remain |
| Architecture protection | Preserved | No schema, app wiring, or worker activation |

### 10.2 Dependencies

- D-03 → D-07 execution/delivery authorization.
- D-04 → D-05/D-06 identity continuity.
- D-05 → active-cycle behavior and D-04 provenance.
- D-06 private repository → D-08 data-egress approval.
- D-07 exact claim/one-PR → D-02 Explicit-list + conversation-wide scope.
- D-07 four-call budget → D-08 provider entitlement/spend cap.
- D-08 live resources → all preceding decisions.

### 10.3 Contradictions and concrete gaps

No approved decision is contradicted; the following are gaps, not approvals:

1. **Standalone outbox delivery gap:** `ReviewReportService.prepare()` creates an outbox
   intent, but a standalone supervisor does not start `OutboxWorker`. A single explicit
   delivery step is required.
2. **One-PR vs pending memberships:** `reserve_conversation_review()` merges pending
   memberships; the canary must reject pending rows and check `membership_count == 1`.
3. **Expiry vs lease:** expiry must be checked before every provider call and renewal.
4. **Four calls vs retries/chunks:** four calls is valid only with one request/stage, one
   attempt, and no retry/fallback.
5. **Revocation gap:** D-03 revalidation is not currently applied at execution/delivery.
6. **Cost ceiling gap:** D-08 has no hard spend cap; four calls do not bound money.

### 10.4 Preserved decisions

- D-01 B remains bot-created-conversation-only.
- D-02 Explicit-list remains no-discovery.
- Conversation-wide scope remains; one PR is a canary envelope.
- R1/R3/R4/R5/R6 boundaries remain unchanged.
- `REVIEW_ENABLED=1` remains configuration validation only.
- R5 worker remains inactive; autopush remains disabled; independent review deferred;
  R8 not started.

---

## 11. Authoritative owner approval record

**Owner approval date:** 2026-11-26
**Source:** explicit owner approval in the ChatGPT conversation.
**Owner identity/signature:** not recorded; no identity, signature, or approval mechanism
is inferred or invented.
**Scope:** policy approval for D-03 through D-06, design-only approval for D-07, and
blocked-status approval for D-08. No implementation or live operation is authorized.

### 11.1 Status vocabulary extension

The existing vocabulary is extended without changing existing meanings:

- `APPROVED` — owner approved the policy choice; implementation is not implied.
- `APPROVED_DESIGN_ONLY` — owner approved a design only; implementation and activation
  are not authorized.
- `APPROVED_BLOCKED` — owner approved keeping the decision blocked; live use is not
  authorized.
- `DEFERRED` — owner explicitly postponed the decision; not approved.

### 11.2 Decision records

| ID | Recorded status | Selected option | Approval scope | Explicit exclusions | Implementation authorization | Live-operation authorization |
|---|---|---|---|---|---|---|
| **D-03** | `APPROVED` | `current-owner-revalidation` | Revalidate current owner, private Telegram chat, conversation ownership/deletion; authorize before every stage and delivery; fail closed | No implementation, tests, runtime wiring, or live operation authorized by this record | `NOT_AUTHORIZED` — separate implementation task required | `NOT_AUTHORIZED` |
| **D-04** | `APPROVED` | `canary-only-owner-attestation` | Temporary Canary linkage basis; explicit owner attestation; no stronger continuity claim; unverified records cannot support continuity | No schema, migration, column, index, trigger, persistence, or implementation authorized | `NOT_AUTHORIZED` — separate implementation task required | `NOT_AUTHORIZED` |
| **D-04b** | `DEFERRED` | `persist-numeric-repository-id` — not approved | None; future decision only | No schema/migration/persistence implementation; no backfill | `NOT_AUTHORIZED` | `NOT_AUTHORIZED` |
| **D-05** | `APPROVED` | `reject-rename-transfer` | Reject same-owner rename, cross-owner transfer, old-name redirects, unverifiable identity; stop/invalidate active cycle on prohibited change; ID alone is not authorization | No rename/transfer support, redirect following, or implementation authorized | `NOT_AUTHORIZED` — separate implementation task required | `NOT_AUTHORIZED` |
| **D-06** | `APPROVED` | `private-allowlisted-only` | Only explicitly allowlisted private repositories; reject fork/cross-repository PRs, fork/archived/deleted/recreated repos, unverifiable visibility/ownership changes; fail closed | No broadening to public, fork, archived, deleted, recreated, transferred, or non-allowlisted repositories; no implementation authorized | `NOT_AUTHORIZED` — separate implementation task required | `NOT_AUTHORIZED` |
| **D-07** | `APPROVED_DESIGN_ONLY` | `approve-bounded-canary-supervisor-design` | Design constraints only: exact claim, one PR, one chunk/stage, max four provider calls/attempt, one attempt, expiry, lease fencing, explicit outbox delivery, append-only audit, no auto-repair, no unrestricted polling, no unrelated cycles | No implementation, runtime activation, app wiring, production DB, or provider call authorized | `NOT_AUTHORIZED` — separate explicit implementation authorization required | `NOT_AUTHORIZED` |
| **D-08** | `APPROVED_BLOCKED` | `keep-blocked` | Live Canary remains blocked until all resources, permissions, entitlement, pricing/usage, hard monetary ceiling, isolation, targets, and cleanup evidence exist and are explicitly authorized | Does not authorize obtaining/creating resources, credentials, accounts, tokens, repositories, conversations, provider calls, or Telegram targets | `NOT_AUTHORIZED` | `BLOCKED` — no live operation authorized |

### 11.3 Cross-record confirmation

- D-04b remains `DEFERRED`; numeric-ID schema work is not approved.
- D-07 is `APPROVED_DESIGN_ONLY`; implementation and activation are not authorized.
- D-08 is `APPROVED_BLOCKED`; live Canary remains blocked.
- No record authorizes live readiness, live operations, or external resources.
- No record changes D-01 B, D-02 Explicit-list, conversation-wide scope, R1–R6,
  independent-review deferral, autopush-disabled status, `REVIEW_ENABLED=1` config-only
  behavior, R5 worker inactivity, or R8.

## 12. Remaining live-resource blockers

- D-04b future schema decision; D-07 implementation authorization; D-08 resources.
- Exact cycle claim and one-PR preflight implementation.
- Provider call/chunk/attempt/expiry guards.
- Explicit outbox delivery step for standalone supervisor.
- Reviewer provider entitlement, pricing/usage, hard spend cap.
- Disposable OpenHands conversation, GitHub repository/branch/PR, Actions run.
- Telegram owner test target.
- Isolated DB and cleanup/revocation evidence.
- Independent review and R8 remain deferred.

---

## 13. Safety and documentation verification

### 13.1 Safety statement

- No production code changed.
- No test code changed.
- No schema, migration, table, index, or trigger changed.
- No OpenHands/GitHub/provider/Telegram call.
- No workflow dispatch.
- No worker constructed or activated.
- No production database opened.
- No credential or secret printed.
- No commit, push, PR, merge, deployment, or release.
- No destructive Git operation.
- D-01 B, D-02 Explicit-list, and conversation-wide scope preserved.
- No live-readiness claim is made.
- Approval record verified against the explicit owner decisions of 2026-11-26.
- D-04b is `DEFERRED`; D-07 is `APPROVED_DESIGN_ONLY`; D-08 is `APPROVED_BLOCKED`.

### 13.2 Documentation verification

- `git diff --check`: clean, exit 0.
- `pytest -q tests/test_doc_code_parity.py`: 16 passed.
- Report reference/path check: no missing referenced reports/modules.
- Secret-pattern scan of the two new reports and PROGRESS: no matches.
- Full test suite not rerun: no executable code changed.
