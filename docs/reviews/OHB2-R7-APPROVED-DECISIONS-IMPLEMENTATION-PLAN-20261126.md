# OHB2-R7 — Approved Decisions Implementation Readiness Plan (2026-11-26)

**Task:** `OHB2-R7-OWNER-APPROVAL-RECORD-AND-IMPLEMENTATION-READINESS` (documentation only)
**Plan status:** `IMPLEMENTATION_PLAN_READY_FOR_AUTHORIZATION`
**Approval source:** explicit owner approval in the ChatGPT conversation, dated 2026-11-26.
**Decision record:** `docs/reviews/OHB2-R7-OWNER-DECISIONS-PACK-20261125.md` §11.
**Final record verdict:** `R7_OWNER_APPROVALS_RECORDED_WITH_NOTES`.

> This is a readiness plan, not an implementation authorization. No work package below
> may be implemented, tested with live services, wired into the application, or activated
> without a separate explicit owner authorization. D-04b is deferred; D-07 is
> design-only; D-08 remains blocked; no live Canary operation is authorized.

---

## 1. Baseline and scope

| Item | Value |
|---|---|
| Repository path | `/workspace/project/OpenHandBot` |
| Branch | `agent/r6-review-delivery` |
| HEAD / main / origin/main | `01079676351aac869d09d4d1747661cd6f07d82b` |
| HEAD tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| Tracked files | 569 |
| Modified tracked | 12 |
| Untracked | 66 |
| Approval date | 2026-11-26 |
| Owner identity/signature | not recorded; not invented |

The work tree was pre-existing and preserved. No code, tests, schema, runtime wiring,
worker, credential, resource, external call, or Git publication was performed.

### 1.1 Preserved decisions

- D-01 B local canary linkage basis.
- D-02 Explicit-list PR selection.
- Conversation-wide review scope and one active cycle per conversation.
- Blind/Adversarial separation and deterministic verdict.
- R1–R6 architecture and verified behavior.
- Independent review deferred; autopush disabled; `REVIEW_ENABLED=1` config-only.
- R5 worker inactive; R8 not started.

---

## 2. Authorization summary

| Decision | Recorded status | Policy approval | Implementation authorized? | External operations authorized? |
|---|---|---|---|---|
| D-03 | `APPROVED` | `current-owner-revalidation` | `NO` | `NO` |
| D-04 | `APPROVED` | `canary-only-owner-attestation` | `NO` | `NO` |
| D-04b | `DEFERRED` | `persist-numeric-repository-id` — not approved | `NO` | `NO` |
| D-05 | `APPROVED` | `reject-rename-transfer` | `NO` | `NO` |
| D-06 | `APPROVED` | `private-allowlisted-only` | `NO` | `NO` |
| D-07 | `APPROVED_DESIGN_ONLY` | `approve-bounded-canary-supervisor-design` | `NO` | `NO` |
| D-08 | `APPROVED_BLOCKED` | `keep-blocked` | `NO` | `NO` |

These are policy/design approvals only. The implementation plan does not silently
authorize code, tests, schema, deployment, credentials, resources, or live Canary.

---

## 3. Work packages

### WP-01 — D-03 authorization revalidation

**Approved policy:** `current-owner-revalidation`.
**Implementation status:** `NOT_AUTHORIZED`.
**External operations:** `NOT_AUTHORIZED`.
**Separate owner approval required:** YES, before any code/test change.

#### Scope

- Revalidate current `Config.owner_id`.
- Revalidate the authorized private Telegram chat and exact cycle `chat_id`.
- Revalidate conversation ownership via the existing `watched` row.
- Revalidate conversation deletion state.
- Authorize before every review stage.
- Authorize before report delivery.
- Fail closed when authorization cannot be established.

#### Prerequisites

- D-03 approval recorded (done).
- A separate implementation authorization naming files and tests.
- Existing resolver/handler/worker tests remain green.
- No schema change; use existing `watched` and cycle fields.

#### Work breakdown

1. Define a single authorization-revalidation helper returning allow/deny plus a safe
   reason code; no secret values in logs.
2. Bind the canary factory to `Config.owner_id`; reject caller-supplied owner mismatch.
3. Call revalidation before claim/process, before Blind, before Adversarial, and before
   report send.
4. Add delivery-time owner/deletion check to the review outbox path.
5. Add Details-send revalidation without making Details idempotent by accident.
6. Preserve lease/epoch fencing; authorization failure must not complete the cycle.
7. Record allow/deny reason in audit evidence without secrets.

#### Required tests

- Owner ID changed before claim, before Blind, before Adversarial, before delivery.
- `watched` row removed or chat mismatch.
- Conversation deleted before/after a stage.
- Callback from another user, group chat, other chat, forged ID.
- Retry/restart after owner change.
- Old outbox row after owner change.
- No provider/GitHub/Telegram call when authorization fails.

#### Expected artifacts

- One small authorization helper.
- Focused unit/integration tests.
- A short implementation report with exact commands/results.
- No schema or migration.

#### Current blocker

Implementation is not authorized. D-07 cannot be implemented until WP-01 is separately
authorized and verified.

#### Acceptance criteria

All authorization failures are fail-closed before any stage/provider/delivery action;
successful tests prove current-owner, chat, ownership, and deletion checks.

---

### WP-02 — D-04 temporary owner attestation

**Approved policy:** `canary-only-owner-attestation`.
**Implementation status:** `NOT_AUTHORIZED`.
**External operations:** `NOT_AUTHORIZED`.
**Separate owner approval required:** YES.

#### Scope

- Record explicit owner attestation evidence.
- Bind the attestation to the exact repository and PR selection.
- Make the attestation auditable and resistant to replay.
- Reject missing or unverifiable identity.
- No numeric-ID schema change.

#### Prerequisites

- D-04 approval recorded (done).
- D-04b remains `DEFERRED`; no schema/migration/column/index/trigger.
- A separate implementation authorization.
- Owner supplies non-secret attestation identifiers in the future authorization.

#### Work breakdown

1. Define the attestation record fields: canary ID, exact conversation ID, exact
   repository full name/numeric ID observed now, exact PR number(s), owner reference,
   timestamp, no-recreation statement, and expiry.
2. Bind attestation to the exact cycle/membership snapshot; reject a different PR/repo.
3. Reject missing, expired, malformed, mismatched, or replayed attestation.
4. Audit the attestation and the current GitHub verification result.
5. Do not add schema; store the attestation in the authorized audit package or an
   existing durable text field only if separately approved.
6. State the limitation explicitly: no historical identity continuity.

#### Required tests

- Missing attestation.
- Expired attestation.
- Repository full name/numeric ID mismatch.
- PR selection mismatch.
- Replayed attestation for another cycle.
- Same-name recreated repository cannot claim continuity.
- No provider call when attestation fails.

#### Expected artifacts

- Attestation schema/format documented and implemented under separate authorization.
- Negative/positive tests.
- Audit sample with no secrets.
- Explicit no-continuity statement.

#### Current blocker

Implementation not authorized; D-04b schema work is deferred.

#### Acceptance criteria

Only an exact, current, explicit attestation can support the canary linkage; all other
records fail closed without an identity-continuity claim.

---

### WP-03 — D-05 repository identity policy

**Approved policy:** `reject-rename-transfer`.
**Implementation status:** `NOT_AUTHORIZED`.
**External operations:** `NOT_AUTHORIZED`.
**Separate owner approval required:** YES.

#### Scope

- Reject same-owner rename.
- Reject cross-owner transfer.
- Reject old-name redirects.
- Reject unverifiable repository identity.
- Stop/invalidate an active cycle on a prohibited identity change.
- Numeric ID alone does not establish authorization.

#### Prerequisites

- D-05 approval recorded (done).
- D-04 attestation/identity policy available.
- Separate implementation authorization.

#### Work breakdown

1. Keep 3xx rejection and canonical full-name/numeric-ID matching.
2. Detect rename/transfer/redirect and map to stable safe reason codes.
3. Invalidate the active cycle; do not continue or deliver as current.
4. Ensure prior evidence remains bound to the old ID/SHA but is not presented as current.
5. Do not follow redirects or auto-adopt a new name/owner.
6. Audit the detected transition and stop reason.

#### Required tests

- 301/302/307/308 redirects.
- Same-owner rename with same ID.
- Cross-owner transfer with same/new ID.
- Active cycle rename/transfer before/after a stage.
- Delivery-pending cycle after a change.
- Unverifiable/malformed identity.
- No provider call after a prohibited transition.

#### Expected artifacts

- Policy helper/reason codes.
- Focused tests.
- Implementation report.
- No rename/transfer support.

#### Current blocker

Implementation not authorized.

#### Acceptance criteria

Every prohibited rename/transfer/redirect/unverifiable case fails closed and invalidates
the active cycle; numeric ID alone never authorizes.

---

### WP-04 — D-06 repository eligibility

**Approved policy:** `private-allowlisted-only`.
**Implementation status:** `NOT_AUTHORIZED`.
**External operations:** `NOT_AUTHORIZED`.
**Separate owner approval required:** YES.

#### Scope

- Private allowlist enforcement.
- Fork and cross-repository PR rejection.
- Fork/archived/deleted/recreated repository rejection.
- Visibility and ownership revalidation.
- Missing/ambiguous metadata fail-closed behavior.

#### Prerequisites

- D-04/D-05 policy available.
- D-08 egress approval before any private code leaves local.
- Separate implementation authorization.

#### Work breakdown

1. Require explicit allowlist membership; no inference from visibility.
2. Reject `fork=true`, `archived=true`, deleted/recreated, and unverifiable metadata.
3. Reject fork PRs and cross-repository PRs using base/head IDs/names.
4. Re-read visibility/owner before execution; reject changes without new approval.
5. Fail closed on missing/ambiguous fields.
6. Audit eligibility evidence without secrets.

#### Required tests

- Private allowlisted/non-allowlisted.
- Public, fork, archived, deleted, recreated.
- Visibility change and ownership transfer.
- Fork/cross-repository PR.
- Missing/ambiguous metadata.
- No provider call for ineligible repositories.

#### Expected artifacts

- Eligibility helper/reason codes.
- Tests and implementation report.
- No broadening of the eligible set.

#### Current blocker

Implementation and private-code egress are not authorized.

#### Acceptance criteria

Only explicitly allowlisted private repositories with stable eligibility pass; every other
category fails closed.

---

### WP-05 — D-07 bounded supervisor implementation design

**Approved design:** `approve-bounded-canary-supervisor-design`.
**Implementation status:** `NOT_AUTHORIZED`.
**External operations:** `NOT_AUTHORIZED`.
**Separate owner approval required:** YES, explicitly for implementation and again for
runtime activation.

#### Scope

Design-only breakdown. No code, app wiring, worker, provider call, production DB, or
activation. The existing R5 worker must not be reused or activated without a separately
verified safety boundary.

#### Mandatory resolutions

1. **Exact cycle claim:** add an exact `review_id` claim/filter plus chat/conversation/
   provider-snapshot checks; never call broad `_claim()` or `_BaseWorker._run()`.
2. **One PR while preserving conversation-wide scope:** canary is one membership; scope
   remains conversation-wide. Reject pending membership rows and require
   `membership_count == 1`.
3. **Pending memberships:** preflight reject; no membership mutation.
4. **Four-call hard budget:** Blind initial + correction, Adversarial initial +
   correction = 4; a fifth call is refused.
5. **One request per stage:** if `build_*_requests()` returns more than one request,
   abort before provider; no chunking.
6. **No retry/fallback:** `max_attempts=1`; no provider switch, repair, or re-claim.
7. **Provider timeout/ambiguous outcome:** stop; record ambiguity; no retry; unknown
   charge may exist.
8. **Expiry checks:** before every provider call and renewal; no renewal after expiry.
9. **Lease fencing/stale workers:** exact token/epoch; no completion after lease loss.
10. **Restart/interruption:** manual restart only; revalidate exact cycle/owner/expiry;
    no auto-resume of ambiguous provider call.
11. **Explicit delivery:** one claimed outbox delivery step or separately authorized
    outbox worker; report/outbox failure leaves `delivery_pending`; ambiguous Telegram is
    `unknown`.
12. **Append-only audit:** canary ID, approval reference, exact config, preflight, call
    count, lease epochs, exact review/SHA, stop reason.
13. **Proof second cycle cannot be processed:** exact claim assertion and test that an
    unrelated eligible cycle remains untouched.
14. **Token/output limits/unknown cost:** no `max_tokens`/token ledger/pricing/hard cap;
    four calls are not a monetary bound; D-08 gate remains.
15. **Report/outbox failure:** fail closed; no false `sent`.

#### Hard safety invariants

- Exact cycle only.
- Exactly one PR membership.
- Exactly one request/stage.
- Max four provider calls.
- One attempt.
- Current owner/conversation/deletion revalidation.
- Expiry before every call/renewal.
- Lease fencing.
- No background polling or unrelated cycles.
- No success claim on ambiguous outcomes.

#### Required tests

- Unit: config, expiry, owner/repo/PR/snapshot mismatch.
- DB: exact claim, wrong cycle, second claim, pending membership, membership count.
- Provider: 4-call cap, correction count, 5th refusal, no fallback.
- Prompt: multi-chunk/oversized abort before provider.
- Lifecycle: lease loss, expiry before/during provider, shutdown/restart.
- Delivery: one outbox intent, ambiguous Telegram `unknown`, report failure.
- Authorization: owner change/unwatch/deletion before execution/delivery.
- Negative: no external call during preflight.
- Audit: exact config, call count, lease epochs, exact SHA, stop reason.

#### Expected artifacts

- Design/implementation plan only.
- Test plan.
- No code, no schema, no activation.

#### Current blocker

Implementation and activation are not authorized. D-08 resources/cost cap are missing.

#### Acceptance criteria

The design is complete enough to request separate implementation authorization, but it is
not itself an implementation authorization.

---

### WP-06 — D-08 resource gate

**Approved status:** `keep-blocked`.
**Implementation status:** `NOT_AUTHORIZED`.
**External operations:** `NOT_AUTHORIZED`.
**Separate owner approval required:** YES, per resource and per live stage.

#### Checklist

- [ ] Disposable OpenHands conversation ID and test identity.
- [ ] Disposable test repository/numeric ID/branch/PR.
- [ ] GitHub read token scoped only to the test repo.
- [ ] Separate GitHub write token, only if setup requires it.
- [ ] GitHub Actions execution approval and exact SHA.
- [ ] Reviewer provider credential and exact model.
- [ ] Provider/model entitlement confirmed by provider/owner, not catalog inference.
- [ ] Pricing and usage visibility.
- [ ] Hard monetary exposure ceiling or explicit bounded-exposure acceptance.
- [ ] Token/call limits and unknown-cost acknowledgement.
- [ ] Telegram owner private test target.
- [ ] Isolated local database outside production.
- [ ] Data-egress approval for private code/diff/CI/report.
- [ ] Cleanup and credential-revocation plan with evidence.
- [ ] No resource created or used before explicit approval.

#### Current blocker

All items are missing/unverified. Live Canary remains `APPROVED_BLOCKED`.

#### Acceptance criteria

Every item has evidence and explicit owner approval; until then no live operation may
start.

---

## 4. Dependency and authorization matrix

| WP | Approved policy | Implementation scope | Prerequisites | Required tests | Expected artifacts | Current blocker | Implementation authorized? | External operations authorized? | Separate owner approval? |
|---|---|---|---|---|---|---|---|---|---|
| WP-01 | D-03 `current-owner-revalidation` | Auth revalidation at stages/delivery | D-03; existing resolver/worker; separate task auth | Owner/deletion/restart/delivery negatives | Helper + tests + report | Implementation not authorized | `NO` | `NO` | `YES` |
| WP-02 | D-04 `canary-only-owner-attestation` | Attestation evidence/binding | D-04; D-04b deferred; separate task auth | Missing/expiry/mismatch/replay | Attestation format + tests + audit | Implementation not authorized | `NO` | `NO` | `YES` |
| WP-03 | D-05 `reject-rename-transfer` | Rename/transfer/redirect rejection | D-04/D-05; separate task auth | Every prohibited transition | Policy helper + tests | Implementation not authorized | `NO` | `NO` | `YES` |
| WP-04 | D-06 `private-allowlisted-only` | Eligibility/allowlist/egress gate | D-04/D-05; D-08 egress; separate task auth | Category matrix negatives | Eligibility helper + tests | Implementation/egress not authorized | `NO` | `NO` | `YES` |
| WP-05 | D-07 design only | Bounded supervisor design | D-03..D-06; D-08 resources; separate implementation auth | Full local plan | Design + test plan only | Implementation/activation not authorized | `NO` | `NO` | `YES` |
| WP-06 | D-08 `keep-blocked` | Resource gate checklist | Owner resource evidence | Presence/scope/cleanup checks | Resource evidence package | Resources missing/unverified | `NO` | `NO` | `YES` |

### 4.1 Sequencing

1. WP-01, WP-02, WP-03, WP-04 can be separately authorized and implemented in any order
   after their prerequisites.
2. WP-05 requires WP-01..WP-04 verified plus a separate implementation authorization.
3. WP-06 must supply evidence before WP-05 live testing.
4. Runtime activation requires another explicit authorization after WP-05 verification.
5. D-04b remains deferred; no schema work is sequenced.

---

## 5. Readiness definition

The project is implementation-ready only when:

- all policy approvals are recorded (done);
- D-04b remains deferred;
- D-07 is design-only;
- D-08 remains blocked;
- each WP has a separate implementation authorization;
- required tests and artifacts are defined (done);
- no live operation is implied by policy approval.

This plan does **not** satisfy those authorizations by itself.

---

## 6. Documentation verification

| Check | Result |
|---|---|
| Approval source matches task | yes; explicit owner approval 2026-11-26 |
| D-03–D-06 approved | yes |
| D-04b deferred | yes |
| D-07 design-only | yes |
| D-08 blocked | yes |
| No live readiness claim | yes |
| Plan does not authorize implementation | yes |
| Referenced code paths exist | checked |
| Existing reports preserved | checked by pre/post hashes |
| `git diff --check` | clean |
| `pytest -q tests/test_doc_code_parity.py` | 16 passed |

No executable code, tests, schema, migration, runtime, worker, credential, resource, or
external operation was performed.
