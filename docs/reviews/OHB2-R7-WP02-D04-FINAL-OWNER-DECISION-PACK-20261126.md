# OHB2-R7 WP-02 / D-04 — Final Owner Decision Pack

**Task ID:** `OHB2-R7-WP02-D04-FINAL-OWNER-DECISION-PACK`
**Date:** 2026-11-26
**Pack verdict:** `WP02_D04_DECISION_PACK_READY_WITH_NOTES`
**Current WP-02 status:** `WP02_D04_BLOCKED`
**Review label:** `AUTHOR_SELF_REVIEW — NOT INDEPENDENT REVIEW`

**Scope:** decision preparation and documentation only. No D-04 implementation, schema,
migration, configuration, runtime, test, worker, Canary, or external operation was
performed. No choice in this document is an owner approval.

---

## 1. Baseline Git state

Recorded before creating this pack:

| Item | Value |
|---|---|
| Repository | `/workspace/project/OpenHandBot` |
| Branch | `agent/r6-review-delivery` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `origin/main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| HEAD tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| Modified tracked | 12 pre-existing |
| Untracked entries | 75 pre-existing |

The working tree already contained the D-03, D-05, D-06, and D-04 design working-tree
artifacts and historical reports. They were preserved. This task adds only this pack
and an additive `.agent/PROGRESS.md` section.

### 1.1 Final state after this pack

| Item | Value |
|---|---|
| Branch / HEAD / tree | unchanged |
| Modified tracked | 12 (same pre-existing set) |
| Untracked | 76 (75 pre-existing + this pack) |
| New task artifacts | this pack and the additive PROGRESS entry |
| Application code / schema / migration / config / test changes | none |

## 2. Existing design evidence and decision status

The authoritative design evidence is
`docs/reviews/OHB2-R7-WP02-D04-ATTESTATION-STORAGE-DESIGN-RESOLUTION-20261126.md`
(verdict `WP02_D04_OWNER_DECISION_REQUIRED`).

Verified conclusions from that design:

- No existing table can safely substitute for a dedicated immutable attestation
  lifecycle.
- `settings` is mutable (`ON CONFLICT DO UPDATE`), with no immutability triggers.
- `auto_review_owner_acceptance` is immutable but R6 report-bound; reuse is prohibited
  and semantically wrong.
- `auto_review_provider_snapshots` is immutable but provider-domain-bound.
- `auto_review_memberships`, `auto_review_evidence`, and `auto_review_reports` are
  immutable but require an existing review cycle and represent R5/R6 evidence, not
  pre-cycle owner consent.
- `auto_reviews` is mutable review-cycle state; `creation_jobs` is the D-01 B context
  source but not an attestation store.
- `outbox`, notification, `watched`, `processed_updates`, and similar operational
  tables are mutable or domain-bound.
- The recommended design uses dedicated immutable header `canary_owner_attestations`
  plus append-only `canary_owner_attestation_events`, with no numeric repository ID.

### 2.1 Existing decisions (unchanged)

| ID | Status | Meaning |
|---|---|---|
| D-03 | `APPROVED` | `current-owner-revalidation` |
| D-04 | `APPROVED` in principle | `canary-only-owner-attestation`; implementation remains blocked |
| D-04b | `DEFERRED`, not approved | `persist-numeric-repository-id` |
| D-05 | `APPROVED` | `reject-rename-transfer` |
| D-06 | `APPROVED` | `private-allowlisted-only` |
| D-07 | `APPROVED_DESIGN_ONLY` | bounded Canary supervisor; no implementation/activation |
| D-08 | `BLOCKED` | live Canary remains blocked |

### 2.2 No newer owner decision found

Searches of `docs/decisions/`, `docs/reviews/`, and `.agent/PROGRESS.md` found:

- no explicit approval of the proposed attestation schema;
- no selection of B1 or B2;
- no selection of A1 or A2;
- no lifecycle approval or TTL value;
- no selection of I1 or I2;
- no recorded owner response to the five `OD-R7-D04-*` IDs.

The only D-04/D-04b records found remain the original approval and deferral. The
unrelated P0 register uses a different decision namespace and was not treated as R7
D-04 approval. This pack does not infer approval from recommendations, prior assistant
reports, or inclusion in this document.

## 3. OD-R7-D04-SCHEMA-01 — Dedicated persistence schema

### Schema choices

**APPROVE — authorize the proposed schema design only.**

Approve the design of:
- `canary_owner_attestations` — immutable binding header.
- `canary_owner_attestation_events` — append-only lifecycle/audit events.

The header binds owner, conversation/chat, exact D-01 B creation job, repository full
name and link source, exact canonical PR set, version/statement, binding fingerprint,
requested/expiry times. Events represent `REQUESTED`, `ACCEPTED`, `REJECTED`,
`EXPIRED`, `CONSUMED`, and `REVOKED`, with no-update/no-delete triggers and unique
one-time lifecycle events.

**Approval scope:** design/schema authorization only. It does **not** authorize
implementation, migration, deployment, runtime wiring, or any D-04b numeric-ID work.
A separate implementation authorization is still required.

**REJECT — do not approve the proposed tables.**
The owner requests an alternative design. D-04 remains blocked; no schema or
implementation proceeds.

### 3.1 Why existing tables cannot substitute

| Existing store | Why it cannot be D-04 storage |
|---|---|
| `settings` | Mutable upsert/delete, no triggers, no lifecycle, no binding or one-time consumption. |
| `auto_review_owner_acceptance` | R6 report acceptance only; `review_id`/`report_version`/`OWNER_ACCEPTANCE`/`ACCEPT` / `REJECT`; no repository/PR/expiry/consumption and not pre-cycle. |
| `auto_review_provider_snapshots` | Immutable provider configuration domain; no owner/conversation/PR/lifecycle. |
| `auto_review_memberships` | Immutable R5 snapshot but requires an existing review cycle; no owner attestation or lifecycle. |
| `auto_review_evidence` / `auto_review_reports` | Immutable review evidence/report; not owner consent and requires a cycle. |
| `auto_reviews` | Mutable review-cycle state; creating it before attestation would invert the D-04 flow. |
| `creation_jobs` | Correct D-01 B linkage source, but mutable and no attestation lifecycle. |
| `outbox`, `notification_inbox`, `watched`, `processed_updates`, etc. | Mutable operational state; no immutable attestation binding, expiry, or consumption. |

### 3.2 Consequences

- **APPROVE:** design may proceed to a separately authorized implementation task.
  D-04 remains unimplemented until that task is authorized. WP-04 is unaffected.
- **REJECT:** D-04 remains blocked; no implementation path is authorized.

## 4. OD-R7-D04-SCOPE-02 — Repository identity scope

### B1 — Name-bound attestation

- Do not persist a numeric repository ID.
- Bind to the current D-01 B linkage context: exact `creation_job_id`, link source,
  canonical repository full name, exact explicit PR set, owner/conversation/chat.
- Keep D-04b `DEFERRED`.
- Accept explicitly that same-name deletion/recreation remains undetectable.
- Keep WP-04 `WP04_D06_BLOCKED`.
- A payload fingerprint protects integrity of the attested payload; it is **not**
  permanent GitHub repository identity and is not evidence that the repository was not
  recreated.

**Consequences:** D-04 can be a bounded canary owner-consent record, but it cannot
support a continuity claim and cannot resolve D-06’s same-name requirement.

### B2 — Request a separate D-04b decision

- Ask for a separate explicit owner decision to change D-04b and persist
  creation-time numeric GitHub repository identity.
- B2 selection is **not** approval of D-04b, not authorization to persist numeric IDs,
  and not authorization to implement or backfill.
- D-04b would require its own design, migration/backfill policy, compatibility analysis,
  and explicit implementation authorization.

**Consequences:** B2 may eventually make D-04/D-06 continuity possible, but neither is
unblocked by this pack. Existing records without creation-time identity remain
ineligible; no backfill may falsely claim continuity.

### 4.1 D-04 and D-06 are different acceptance requirements

- D-04 is owner consent for a bounded Canary linkage.
- D-06 is repository eligibility, including private/allowlisted/fork/archive/delete
  and same-name recreation policy.
- Completing D-04 under B1 does **not** resolve WP-04 and must never be presented as
  doing so.
- A fingerprint is integrity protection only; it is not a repository identity token.

## 5. OD-R7-D04-AUTH-03 — Authorization timing

### A1 — Dedicated pre-cycle authorization helper

Approve a read-only helper that reuses the WP-01 rules without weakening them:

- current authoritative `Config.owner_id`;
- positive owner/chat identity;
- `watched` row exists and `watched.chat_id == owner`;
- conversation not deleted;
- DB read failures are retryable/fail-closed;
- no cached authorization;
- revalidation at request, confirmation, and consumption.

**Lifecycle/usability:** permits resolve → owner attestation → reservation before a
review cycle exists. It adds a new code path that must be tested for parity with
WP-01; any drift is a security blocker.

### A2 — Require an existing review cycle

Permit attestation only in a context where a review cycle already exists and can be
authorized by the existing `revalidate_review_authorization()` path. This requires a
changed lifecycle (for example, a pre-attestation cycle/draft phase) or accepting that
D-04 is post-cycle.

**Lifecycle/usability:** reuses WP-01 directly but changes the current canary flow and
may weaken the meaning of pre-execution owner attestation. It is not a new
authorization source and must not use R6 acceptance.

No third authorization source and no R6 reuse is permitted.

## 6. OD-R7-D04-LIFECYCLE-04 — Attestation lifecycle

### Proposed lifecycle

```text
not_requested -> pending
pending -> accepted | rejected | expired
accepted -> consumed | expired | revoked
rejected/expired/consumed/revoked -> terminal
```

### Proposed safeguards

- Fixed TTL; no silent extension.
- One-time consumption.
- Idempotent duplicate confirmation.
- Terminal `rejected`, `expired`, `consumed`, and `revoked` states.
- `revoked` for owner cancellation or binding invalidation before consumption.
- Transactional state transitions (`BEGIN IMMEDIATE`).
- Append-only audit events; no accepted/consumed record is silently rewritten.

**TTL duration is not specified by this pack.** It is a separate parameter requiring
an explicit owner-selected value or an explicitly agreed bounded policy. No default
duration is invented or assumed.

### Approval options

- **APPROVE — lifecycle package**, with the TTL value separately selected.
- **REJECT — lifecycle package**; request changes or remain blocked.

**Consequences:** approval without a TTL value is incomplete. A TTL selection is
needed before implementation; rejection leaves D-04 blocked.

## 7. OD-R7-D04-INTEGRATION-05 — Creation-job binding and consumption

### I1 — Exact creation-job binding and atomic consumption

- Expose the exact D-01 B `creation_job_id` in-memory in `ConversationRepositoryLink`
  and `MembershipProvenance`.
- Bind the attestation to that exact creation job, link source, repository full name,
  exact PR set, owner, conversation, and chat.
- Consume the attestation in the same database transaction that creates the review
  cycle and immutable PR membership snapshot.
- If any step fails, roll back the review, memberships, and consumption together.

**Benefits:** no consumed attestation without a cycle; no cycle without consumption;
atomic rollback; one-time consumption and replay prevention through unique events and
operation keys.

**Risks:** requires extending the future reservation API and transaction; any split
(consume then reserve, or reserve then consume) creates a crash window with a consumed
attestation but no cycle, or a cycle authorized without consumption. External GitHub
checks cannot occur inside the SQLite transaction; the existing residual TOCTOU window
remains.

### I2 — Reject this integration design

Do not expose `creation_job_id` this way and do not couple consumption to reservation.
A revised design is requested. D-04 remains blocked.

## 8. Decision dependency table

| Decision | Type | Prerequisite for WP-02 implementation? | Design-only? | Requires separate D-04b approval? | Leaves/affects WP-04 | Blocks WP-05? |
|---|---|---|---|---|---|---|
| OD-R7-D04-SCHEMA-01 | Schema/design authorization | Yes | Yes (design only; no migration) | No | No direct effect; does not resolve WP-04 | Yes, until WP-02 implemented and separately authorized |
| OD-R7-D04-SCOPE-02 B1 | Policy scope | Yes | Yes | No (keeps D-04b deferred) | **Leaves WP-04 blocked** (same-name limitation) | Yes, until WP-02 implemented |
| OD-R7-D04-SCOPE-02 B2 | Direction request | Yes, conditionally | Yes | **Yes — separate D-04b decision** | May eventually help WP-04; does not unblock it now | Yes, until separate decisions and implementation |
| OD-R7-D04-AUTH-03 A1/A2 | Authorization design | Yes | Yes | No | No direct effect | Yes, until WP-02 implemented |
| OD-R7-D04-LIFECYCLE-04 | Lifecycle design + TTL parameter | Yes | Yes | No | No direct effect | Yes, until WP-02 implemented |
| OD-R7-D04-INTEGRATION-05 I1/I2 | Integration design | Yes | Yes | No for B1 | No direct effect | Yes, until WP-02 implemented |

**Important:** approving all five decisions does not authorize code implementation.
A separate explicit implementation authorization is mandatory after the decisions are
settled. WP-05 also remains blocked by WP-04 and by its own separate authorization
requirements.

## 9. Recommendation (not an owner decision)

**RECOMMENDATION — NOT OWNER APPROVAL**

The conservative path is:

- **SCHEMA:** approve the dedicated immutable header + append-only events design.
- **SCOPE:** B1, keeping D-04b deferred and explicitly preserving the same-name
  limitation.
- **AUTH:** A1 only if it can faithfully reuse WP-01 owner/private-chat/deletion/
  watched checks; otherwise A2 and a revised lifecycle.
- **LIFECYCLE:** approve one-time consumption, append-only events, revocation, and a
  bounded TTL whose exact duration is explicitly selected.
- **INTEGRATION:** I1, with consumption and reservation in one transaction.

### Trade-offs and unresolved limitations

| Recommendation | Trade-off | Unresolved limitation |
|---|---|---|
| Approve dedicated schema | New additive schema and migration surface; requires separate implementation authorization | No schema exists; no tests; implementation blocked |
| B1 name-bound scope | Does not require numeric-ID persistence and keeps D-04b deferred | Same-name recreation remains undetectable; WP-04 stays blocked; no permanent identity claim |
| A1 pre-cycle helper | Preserves pre-cycle usability but adds a new authorization code path | Must prove parity with WP-01; any drift is unsafe |
| Lifecycle with revocation and TTL | Strong replay/expiry control; TTL trade-off between usability and exposure | Exact TTL value not selected; no default invented |
| I1 atomic consumption | Prevents split-brain and double consumption | Requires reservation API/transaction changes; external TOCTOU remains |

This recommendation is only a design preference. It is not a choice by the owner and
does not authorize implementation.

## 10. Explicit owner approval section

**Status of all five decisions: `PENDING — NO OWNER APPROVAL RECORDED`.**

| Decision ID | Selected option | Owner approval | Date/evidence |
|---|---|---|---|
| OD-R7-D04-SCHEMA-01 | `PENDING` | `NOT APPROVED` | none |
| OD-R7-D04-SCOPE-02 | `PENDING` | `NOT APPROVED` | none |
| OD-R7-D04-AUTH-03 | `PENDING` | `NOT APPROVED` | none |
| OD-R7-D04-LIFECYCLE-04 | `PENDING` | `NOT APPROVED`; TTL `PENDING` | none |
| OD-R7-D04-INTEGRATION-05 | `PENDING` | `NOT APPROVED` | none |

To approve, the owner must record an explicit statement in the repository, for example:

```text
OD-R7-D04-SCHEMA-01: APPROVE | REJECT
OD-R7-D04-SCOPE-02: B1 | B2
OD-R7-D04-AUTH-03: A1 | A2
OD-R7-D04-LIFECYCLE-04: APPROVE | REJECT; TTL = <explicit duration or bounded policy>
OD-R7-D04-INTEGRATION-05: I1 | I2
```

A partial selection is allowed, but every unselected decision remains pending and
continues to block the corresponding scope. **Inclusion in this document is not
approval. Past recommendations and assistant wording are not approval.**

## 11. Implementation authorization gate

Even if the owner approves all five decisions:

- D-04 is still **not implemented**.
- No schema, migration, code, configuration, runtime, worker, or test change is
  authorized by this pack.
- A separate implementation task must explicitly authorize scope, files, tests,
  verification, and any schema migration.
- D-04b remains deferred unless separately approved; B2 is only a direction request.
- WP-05 cannot start from this pack; it depends on WP-01 through WP-04 and separate
  implementation authorization.
- WP-06 / live Canary remains blocked; D-08 is `BLOCKED`.

## 12. D-04b and WP-04 limitations

- **D-04b remains `DEFERRED` and untouched.** No numeric repository ID, creation-time
  numeric ID, backfill, column, index, trigger, migration, or identity substitute was
  added.
- **B1** leaves same-name deletion/recreation undetectable.
- **B2** only requests a separate D-04b decision; it does not approve or implement it.
- A payload fingerprint is integrity protection, not permanent GitHub identity.
- **WP-04 remains `WP04_D06_BLOCKED`.** Completing D-04 under B1 cannot resolve WP-04
  and must not be reported as doing so.
- **WP-05 / WP-06** remain not started/blocked; D-07 design-only; D-08 blocked.

## 13. Documentation-only verification

- Documentation/code parity: `pytest -q tests/test_doc_code_parity.py` → **16 passed**.
- `git diff --check` → clean.
- No application code, schema, migration, configuration, or test file was modified by
  this task.
- No full test suite is claimed as evidence of D-04 design or implementation.
- Only this pack and the additive `.agent/PROGRESS.md` entry were created by this task.
- No owner decision was recorded as approved without evidence.

## 14. Git and operational safety

- No commit, push, pull, fetch, PR, merge, deployment, or release.
- No OpenHands/GitHub/Telegram API call, provider inference, external transmission,
  production database access, worker activation, or live Canary.
- No destructive Git operation; all pre-existing modifications and untracked files
  were preserved.
- Autopush remains disabled and inactive.
- Local working tree only; unpublished.

## 15. Current verdict and status distinctions

- **Decision-pack preparation:** complete.
- **Owner decisions:** all five **pending**; no approval.
- **Implementation:** not started.
- **Schema:** not created.
- **Independent review:** deferred/not present.
- **D-04b:** `DEFERRED` and untouched.
- **WP-02:** `WP02_D04_BLOCKED`; not complete.
- **WP-04:** `WP04_D06_BLOCKED`; same-name limitation remains.
- **WP-05 / WP-06:** not started / live Canary blocked.
- **Committed vs working tree:** working-tree changes only.
- **Published vs unpublished:** unpublished.
- **Pack verdict:** `WP02_D04_DECISION_PACK_READY_WITH_NOTES`.

The pack is ready for owner review, but the owner has not selected any option. The
current WP-02 implementation verdict remains blocked pending explicit owner decisions
and a separate implementation authorization.
