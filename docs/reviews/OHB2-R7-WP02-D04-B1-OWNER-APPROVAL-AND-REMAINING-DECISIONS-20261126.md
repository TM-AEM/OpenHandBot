# OHB2-R7 WP-02 / D-04 — B1 Owner Approval and Remaining Decisions

**Task ID:** `OHB2-R7-WP02-D04-RECORD-B1-AND-REMAINING-OWNER-DECISIONS`
**Date:** 2026-11-26
**Verdict:** `WP02_D04_B1_RECORDED_AND_REMAINING_DECISIONS_READY`
**Current WP-02 status:** `WP02_D04_BLOCKED`
**Review label:** `AUTHOR_SELF_REVIEW — NOT INDEPENDENT REVIEW`

**Scope:** documentation and decision preparation only. No D-04 implementation,
schema, migration, configuration, runtime, test, worker, Canary, or external operation
was performed.

This is an additive record linked to:

- `docs/reviews/OHB2-R7-WP02-D04-FINAL-OWNER-DECISION-PACK-20261126.md`
- `docs/reviews/OHB2-R7-WP02-D04-ATTESTATION-STORAGE-DESIGN-RESOLUTION-20261126.md`

The earlier final decision pack remains a historical pending-state snapshot and is not
rewritten. This report records the later B1 approval and the four decisions still
pending.

---

## 1. Baseline Git state

Recorded before creating this report:

| Item | Value |
|---|---|
| Repository | `/workspace/project/OpenHandBot` |
| Branch | `agent/r6-review-delivery` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `origin/main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| HEAD tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| Modified tracked | 12 pre-existing |
| Untracked entries | 76 pre-existing |

All pre-existing modifications and untracked files, including `.openhands/`, were
preserved. This task adds only this report and an additive `.agent/PROGRESS.md`
section.

### 1.1 Final state after this report

| Item | Value |
|---|---|
| Branch / HEAD / tree | unchanged |
| Modified tracked | 12 (same pre-existing set) |
| Untracked | 77 (76 pre-existing + this report) |
| Application code / schema / migration / config / test changes | none |

## 2. B1 owner approval record

### 2.1 Decision record

| Field | Value |
|---|---|
| Decision ID | `OD-R7-D04-SCOPE-02` |
| Selected option | **`B1`** |
| Status | **`APPROVED`** |
| Approval date | `2026-11-26` |
| Approval source | Explicit owner approval in the ChatGPT conversation |
| Exact owner statement | **«موافق»** |
| Question context | The owner was asked whether to approve B1 while keeping D-04b deferred and unapproved. |
| Scope | Name-bound owner attestation without persisting a numeric GitHub repository ID. |
| Accepted limitation | The design cannot distinguish deletion and recreation of a repository under the same full name when no creation-time numeric repository ID exists. |
| D-04b | `DEFERRED — NOT APPROVED` |
| WP-04 | Remains `WP04_D06_BLOCKED` by the same-name deletion/recreation identity limitation. |

The approval is recorded only for the scope above. It is not inferred from a
recommendation, a prior assistant report, or inclusion in a decision pack.

### 2.2 What B1 approves

B1 approves this identity scope:

- Bind the attestation to the current D-01 B linkage context: exact `creation_job_id`,
  link source, canonical repository full name, exact explicit PR set, owner,
  conversation, and chat.
- Do **not** persist a numeric GitHub repository ID.
- Keep D-04b deferred and unapproved.
- Accept the same-name deletion/recreation limitation explicitly.
- Keep WP-04 blocked; completing D-04 under B1 does not resolve WP-04.
- A payload fingerprint is integrity protection only, not permanent repository
  identity and not evidence that a repository was not recreated.

### 2.3 What B1 does not approve

B1 does **not** approve:

- the dedicated schema (`OD-R7-D04-SCHEMA-01`);
- authorization timing (`OD-R7-D04-AUTH-03`);
- the lifecycle package or any TTL (`OD-R7-D04-LIFECYCLE-04`);
- the creation-job binding/consumption integration (`OD-R7-D04-INTEGRATION-05`);
- implementation, migration, deployment, runtime wiring, or tests;
- any numeric repository ID persistence, backfill, fingerprint substitute, or
  equivalent permanent identity mechanism;
- D-04b in any form.

### 2.4 No later decision supersedes B1

Searches of `docs/decisions/`, `docs/reviews/`, and `.agent/PROGRESS.md` found no later
R7 owner decision selecting B2, rejecting B1, or approving the schema, authorization,
lifecycle/TTL, or integration decisions. The earlier final decision pack remains a
historical pending-state snapshot; this additive report records the later B1 approval.
The unrelated P0 decision register uses a different namespace and is not treated as an
R7 decision.

## 3. D-04b deferred status

**D-04b: `DEFERRED — NOT APPROVED`.**

- No numeric GitHub repository ID persistence is authorized.
- No creation-time numeric ID capture is authorized.
- No backfill, column, index, trigger, migration, or equivalent identity mechanism is
  authorized.
- No fingerprint or digest may be presented as a substitute for permanent repository
  identity.
- B1 does not change D-04b.
- WP-04 remains blocked by the same missing identity evidence.

## 4. Remaining owner decisions

All four decisions below remain **`PENDING — NOT APPROVED`**.

### 4.1 OD-R7-D04-SCHEMA-01 — Dedicated persistence schema

**APPROVE:** approve the design of:
- `canary_owner_attestations` — immutable binding header.
- `canary_owner_attestation_events` — append-only lifecycle/audit events.

Approval is design/schema approval only. It does not authorize implementation,
migration, deployment, runtime wiring, or D-04b work. A separate implementation
authorization remains mandatory.

**REJECT:** reject the proposed tables and request an alternative design. D-04 remains
blocked.

**Why existing tables cannot safely substitute:**

| Existing store | Limitation |
|---|---|
| `settings` | Mutable upsert/delete, no immutability triggers, no lifecycle, no binding or one-time consumption. |
| `auto_review_owner_acceptance` | R6 report acceptance only; bound to `review_id`, `report_version`, `OWNER_ACCEPTANCE`, and `ACCEPT`/`REJECT`; no repository/PR/expiry/consumption. |
| `auto_review_provider_snapshots` | Immutable but provider-configuration domain; no owner/conversation/PR/lifecycle. |
| `auto_review_memberships` / `auto_review_evidence` / `auto_review_reports` | Immutable but require an existing review cycle; they are R5/R6 evidence, not pre-cycle owner consent. |
| `auto_reviews` | Mutable review-cycle state; using it before attestation inverts the D-04 flow. |
| `creation_jobs` | Correct D-01 B linkage source, but mutable and has no attestation lifecycle. |
| Operational tables (`outbox`, `notification_inbox`, `watched`, etc.) | Mutable operational state; no immutable attestation binding or consumption semantics. |

**Consequences:** APPROVE enables a future separately authorized implementation design;
REJECT leaves D-04 blocked. Neither choice authorizes code or migration now.

### 4.2 OD-R7-D04-AUTH-03 — Authorization timing

**A1:** approve a dedicated read-only pre-cycle authorization helper that faithfully
reuses WP-01 checks:
- current `Config.owner_id`;
- positive owner/chat identity;
- private-chat/`watched.chat_id` equality;
- conversation deletion check;
- watched-conversation presence;
- no cached authorization;
- DB read failures retryable/fail-closed;
- revalidation at request, confirmation, and consumption.

**Security consequence:** preserves WP-01 semantics but adds a code path that must
prove parity; any drift is a security blocker.

**Usability consequence:** permits resolve → owner attestation → reservation before a
review cycle exists.

**Integration consequence:** requires a new helper and careful call-site coverage.

**A2:** restrict attestation requests and confirmation to a context where an authorized
review cycle already exists.

**Security consequence:** reuses the existing cycle-bound `revalidate_review_authorization()`
directly.

**Usability consequence:** changes the canary flow; attestation may be post-cycle or
requires a draft/pre-attestation cycle.

**Integration consequence:** requires lifecycle/flow changes and may weaken the
meaning of pre-execution attestation.

No third authorization source is proposed. R6 owner acceptance must not be reused.

**Consequences:** A1 or A2 must be selected explicitly; either choice alone does not
authorize implementation.

### 4.3 OD-R7-D04-LIFECYCLE-04 — Lifecycle and TTL

Proposed lifecycle:

```text
not_requested -> pending
pending -> accepted | rejected | expired
accepted -> consumed | expired | revoked
rejected/expired/consumed/revoked -> terminal
```

Proposed safeguards requiring explicit approval:
- One-time consumption.
- Idempotent duplicate confirmation.
- Fixed expiration with no silent TTL extension.
- Append-only audit events.
- Transactional state transitions (`BEGIN IMMEDIATE`).
- Terminal rejected/expired/consumed/revoked states.
- `revoked` for owner cancellation or binding invalidation before consumption.

**`revoked` is part of the proposed package and requires explicit approval.** It is not
already approved by B1 or by the earlier design report.

**TTL:** the exact duration remains **unselected**. Existing design evidence mentions a
bounded value such as 15 minutes only as a prior proposal; it is **not approved** and
must not be treated as a default. The owner must select an explicit duration or an
explicit bounded policy. This pack does not invent or silently choose a TTL.

**APPROVE:** approve the lifecycle package plus the safeguards, with a separately
selected TTL value or bounded policy.

**REJECT:** reject the lifecycle package; D-04 remains blocked.

**Consequences:** approval without a TTL value is incomplete; no consumption or
expiry behavior can be implemented from this pack.

### 4.4 OD-R7-D04-INTEGRATION-05 — Creation-job binding and consumption

**I1:** expose the exact D-01 B `creation_job_id` in-memory and bind the attestation to
that exact linkage context; consume it in the same database transaction that creates
the review cycle and immutable PR membership snapshot.

- **Atomicity:** review, memberships, and consumption commit together or roll back
  together.
- **Rollback:** no consumed attestation without a cycle; no cycle without consumption.
- **Replay prevention:** unique consumed event/operation key plus one transaction.
- **Risk of splitting:** consumption without reservation creates a consumed but
  unusable attestation; reservation without consumption creates a cycle not authorized
  by the attestation. A crash between steps leaves ambiguous state.
- **Residual risk:** external GitHub verification cannot occur inside the SQLite
  transaction; the existing TOCTOU window remains.

**I2:** reject this integration design and request a revised design. D-04 remains
blocked.

**Consequences:** I1 enables a future atomic design but still requires separate
implementation authorization. I2 blocks.

## 5. Decision dependency matrix

| Decision | Current status | Prerequisite for WP-02 implementation? | Design-only? | Separate D-04b approval needed? | Effect on WP-04 | Effect on WP-05 |
|---|---|---|---|---|---|---|
| `OD-R7-D04-SCOPE-02` | **B1 APPROVED** | Yes, scope settled | Yes | No; D-04b stays deferred | WP-04 remains blocked | WP-05 still blocked |
| `OD-R7-D04-SCHEMA-01` | `PENDING` | Yes | Design/schema approval only; no migration | No | No direct resolution | WP-05 still blocked |
| `OD-R7-D04-AUTH-03` | `PENDING` | Yes | Design-only | No | No direct resolution | WP-05 still blocked |
| `OD-R7-D04-LIFECYCLE-04` | `PENDING` (TTL unselected) | Yes | Design-only | No | No direct resolution | WP-05 still blocked |
| `OD-R7-D04-INTEGRATION-05` | `PENDING` | Yes | Design-only | No | No direct resolution | WP-05 still blocked |

Additional constraints:

- B1 preserves D-04b as deferred and keeps WP-04 blocked.
- No remaining approval independently authorizes implementation.
- Approving all five decisions still does **not** authorize code or schema migration.
- A separate explicit implementation authorization is mandatory.
- WP-05 must not start until WP-01 through WP-04 are verified and the required
  implementation authorization exists.
- WP-06 and live Canary remain blocked.

## 6. Recommendation — non-binding

**RECOMMENDATION — NOT AN OWNER DECISION OR APPROVAL**

- **Schema:** approve the dedicated two-table design.
- **Authorization:** A1, only if implementation can prove parity with WP-01 checks.
- **Lifecycle:** approve one-time consumption, append-only events, revocation, and a
  fixed TTL explicitly selected by the owner.
- **Integration:** I1, with consumption and reservation in the same transaction.

Trade-offs and remaining limitations:

| Recommendation | Trade-off | Limitation |
|---|---|---|
| Approve dedicated schema | New additive schema/migration surface; separate implementation authorization required | No schema exists; D-04 unimplemented |
| A1 helper | Preserves pre-cycle usability but adds a new authorization path | Must prove parity with WP-01; drift is unsafe |
| Lifecycle with revocation and TTL | Strong replay/expiry control; TTL affects usability and exposure | Exact TTL not selected; no default |
| I1 atomic integration | Prevents split consumption/reservation | Changes reservation API/transaction; external TOCTOU remains |

These are recommendations only. The owner must select the remaining decisions
explicitly.

## 7. Implementation authorization gate

Even after all five decisions are resolved:

- D-04 is still **not implemented**.
- No code, schema, migration, configuration, runtime, worker, or test change is
  authorized by this report.
- A separate implementation task must explicitly authorize files, tests, verification,
  and any schema migration.
- D-04b remains deferred unless separately approved.
- WP-05 cannot start from this report; it depends on WP-01 through WP-04 and separate
  implementation authorization.
- WP-06 / live Canary remains blocked; D-08 is `BLOCKED`.

## 8. WP-04 same-name identity limitation

- B1 is name-bound and does not persist a creation-time numeric repository ID.
- A repository deleted and recreated under the same full name cannot be distinguished
  from the originally linked repository when no creation-time numeric ID exists.
- No fingerprint, digest, or equivalent mechanism is authorized as a substitute.
- B1 does not establish permanent repository identity.
- **WP-04 remains `WP04_D06_BLOCKED`.**
- Completing D-04 under B1 must not be presented as resolving WP-04.

## 9. Verification

- Documentation/code parity: `pytest -q tests/test_doc_code_parity.py` → **16 passed**.
- `git diff --check` → clean.
- B1 recorded only for its explicit scope.
- D-04b remains deferred and unimplemented.
- Schema, AUTH, LIFECYCLE/TTL, and INTEGRATION remain pending.
- No application code, schema, migration, configuration, or test file was changed.
- No full test suite is claimed as validation of unimplemented D-04 behavior.
- Only this report and the additive `.agent/PROGRESS.md` entry were introduced by this
  task.

## 10. Git and operational safety

- No commit, push, pull, fetch, PR, merge, deployment, or release.
- No GitHub, OpenHands, or provider API calls.
- No provider inference or external data transmission.
- No Telegram delivery, production database access, worker activation, or Canary.
- No destructive Git operation; pre-existing changes and untracked files preserved.
- Autopush remains disabled and inactive.
- Local working-tree changes only; unpublished.

## 11. Current verdict and status distinctions

- **Owner-approved decision:** `OD-R7-D04-SCOPE-02` = **B1 APPROVED**.
- **Pending decisions:** `SCHEMA-01`, `AUTH-03`, `LIFECYCLE-04` (including TTL),
  `INTEGRATION-05`.
- **Implementation:** not started; no implementation authorization.
- **Schema:** not created.
- **Independent review:** deferred/not present.
- **D-04b:** `DEFERRED` and untouched.
- **WP-02:** `WP02_D04_BLOCKED`; not complete.
- **WP-04:** `WP04_D06_BLOCKED`; same-name limitation remains.
- **WP-05 / WP-06:** not started / live Canary blocked.
- **Committed vs working tree:** working-tree changes only.
- **Published vs unpublished:** unpublished.
- **Report verdict:** `WP02_D04_B1_RECORDED_AND_REMAINING_DECISIONS_READY`.

The B1 approval is recorded. The remaining decisions are ready for explicit owner
selection, but none is approved by this report.
