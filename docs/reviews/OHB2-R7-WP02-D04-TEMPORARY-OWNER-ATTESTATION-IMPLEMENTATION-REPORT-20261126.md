# OHB2-R7 WP-02 / D-04 Temporary Owner Attestation — Implementation Report

**Task ID:** `OHB2-R7-WP02-D04-TEMPORARY-OWNER-ATTESTATION`
**Date:** 2026-11-26
**Verdict:** `WP02_D04_BLOCKED`
**Review label:** `AUTHOR_SELF_REVIEW — NOT INDEPENDENT REVIEW`

**Scope:** baseline audit, attestation contract design, persistence-boundary analysis,
and local regression verification only. No implementation code, schema, migration,
worker activation, external operation, or Git publication was performed.

---

## 1. Baseline Git state

Recorded before any edit for this task:

| Item | Value |
|---|---|
| Repository | `/workspace/project/OpenHandBot` |
| Branch | `agent/r6-review-delivery` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `origin/main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| HEAD tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| Tracked files | 569 |
| Modified tracked | 12 (pre-existing) |
| Untracked entries | 69 (pre-existing) |
| Python | 3.13.15 in `.venv` |
| pytest | 9.0.3 |
| Node | 24.22.2 |

The working tree already contained R1–R7 code, `bot/review/`, review tests, WP-01
authorization, and historical reports. They were preserved. No destructive Git
operation was used.

## 2. Approved D-04 scope

The owner approval is recorded in
`docs/reviews/OHB2-R7-OWNER-DECISIONS-PACK-20261125.md`:

- D-04: `canary-only-owner-attestation`.
- D-04b: `persist-numeric-repository-id` is `DEFERRED`; no schema, migration, column,
  index, trigger, backfill, or numeric-ID persistence is approved.

WP-02 is authorized only for local D-04 implementation. D-04b, WP-03..WP-06, bounded
Canary Supervisor, R5 worker activation, live Canary execution, external calls,
deployment, and Git publication are out of scope.

## 3. Attestation contract (design only)

If the required persistence is separately approved, the record must bind:

| Field | Required semantics |
|---|---|
| `attestation_version` | Immutable contract version, e.g. `canary-attestation.v1`. |
| `attestation_id` | Server-generated unique identifier; never accepted from a callback/client. |
| `owner_user_id` | Current authoritative `Config.owner_id` at request, confirmation, and consumption. |
| `conversation_id` | Exact OpenHands conversation identity. |
| `creation_job_id` | Exact D-01 B `creation_jobs` row used as the linkage context. Current `ConversationRepositoryLink` does not expose this field. |
| `repository_full_name` | Exact canonical GitHub full name verified for the link. This is display/allowlist evidence, not permanent identity. |
| `repository_identity_commitment` | A cryptographic commitment to the current GitHub numeric repository ID and full name. Raw numeric-ID persistence is forbidden by this task; the contract cannot record it without a separate D-04b decision. |
| `repository_link_source` | Exact source value, currently `canary_creation_job`; source alone is not proof. |
| `pr_numbers` | Exact explicit D-02 list, canonicalized as sorted unique positive integers. |
| `pr_selection_digest` | Commitment to the canonical PR list and repository identity. |
| `linkage_context` | Review cycle/reservation context or pre-cycle linkage context. |
| `created_at` | Durable server timestamp. |
| `expires_at` | Durable expiry; no silent extension. |
| `no_recreation_statement` | Explicit owner statement limited to the canary window; never proof of historical continuity. |
| `status` | `not_requested`, `pending`, `accepted`, `rejected`, `expired`, or `consumed`. |
| `fingerprint` | Deterministic SHA-256 over the canonical immutable binding fields. |

The record must not claim that a repository full name proves permanent identity, and
must not claim continuity across deletion and recreation.

## 4. Lifecycle contract (design only)

Valid transitions:

```text
not_requested -> pending
pending -> accepted | rejected | expired
accepted -> consumed | expired
rejected -> (terminal)
expired -> (terminal)
consumed -> (terminal)
```

Duplicate confirmation of the same pending attestation by the same current owner is
idempotent. A conflicting confirmation is rejected. Rejected, expired, or consumed
attestations cannot be consumed. An accepted attestation is immutable. Any repository
or PR-selection change requires a new attestation. Historical evidence is never silently
deleted.

## 5. Binding and fingerprint semantics (design only)

- Canonical serialization uses sorted keys, compact separators, UTF-8, and a fixed
  domain/version prefix.
- The fingerprint is recomputed server-side from authoritative persisted values; a
  client-supplied fingerprint is never trusted.
- The binding includes owner, conversation, creation-job linkage, repository identity
  commitment, full name, exact PR list, linkage context, and version.
- PR order is canonicalized by sorting; duplicate PRs are rejected; added or removed
  PRs invalidate the attestation.
- Full names compare case-insensitively after canonicalization; numeric identity must
  match exactly when available.
- Missing, malformed, altered, stale, contradictory, cross-repository, or fork PR
  evidence is rejected.
- A fingerprint is an integrity mechanism only. It is not proof of repository identity
  or owner authorization.

## 6. Owner authorization integration (design only)

The existing WP-01 helper `revalidate_review_authorization()` requires a review cycle.
D-04 attestation may be requested before a cycle exists, so a safe implementation needs
one of:

1. a cycle-less owner/conversation authorization helper that reuses the same
   `Config.owner_id`, `watched.chat_id`, deletion, and DB-read failure rules; or
2. an approved lifecycle that only allows attestation after a cycle exists.

Authorization must be revalidated at request, confirmation, and consumption. Callback
payloads, stale owner IDs, old Telegram updates, cached results, and client-supplied
repository/PR values are not trusted. Authorization and DB read failures fail closed.

## 7. Persistence analysis and blocker

### Existing persistence inspected

- `settings`: durable generic `key/value` table; values are mutable via
  `set_setting()`/upsert and there is no append-only or no-update/no-delete trigger.
  It cannot safely represent an immutable accepted attestation or enforce valid
  lifecycle transitions at the database boundary.
- `auto_review_owner_acceptance`: immutable, but schema-bound to R6 `review_id` +
  `report_version`, `event_type='OWNER_ACCEPTANCE'`, and `ACCEPT|REJECT`. It has no
  repository, PR, conversation-linkage, expiry, or attestation fields. Reusing it would
  conflate D-04 repository-linkage consent with R6 report acceptance.
- `auto_reviews`, `creation_jobs`, `watched`, `outbox`, `notification_inbox`,
  `completion_pending`: mutable operational rows without attestation lifecycle,
  immutable binding, expiry, or replay-consumption fields.
- Immutable tables (`auto_review_memberships`, `auto_review_evidence`,
  `auto_review_reports`, `auto_review_provider_snapshots`) are domain-specific and
  cannot store arbitrary attestation records without misuse or conflating review data.
- `ConversationRepositoryLink` currently carries only `conversation_id`,
  `repository_id`, `repository_full_name`, and `source`; it does not expose the exact
  `creation_job_id` required for a durable linkage-context binding.

### Exact missing persistence capability

There is no existing table that can durably and atomically store all of:

- a server-generated attestation ID;
- owner and conversation identity;
- exact D-01 B creation-job linkage context;
- repository full name and identity commitment;
- exact explicit PR selection;
- lifecycle status and valid transitions;
- creation and expiry timestamps;
- a deterministic fingerprint;
- consumption binding to one review/linkage operation.

Using `settings` would require application-only immutability and would not satisfy the
task's requirement not to weaken durability, immutability, or replay protection merely
to avoid a schema change. Using `auto_review_owner_acceptance` is explicitly
disallowed by the task's domain-separation rule.

### Minimal separately reviewable design

A future approved design should add a dedicated immutable table (or header + append-only
event table) with:

- a unique `attestation_id` and idempotency key;
- owner, conversation, creation-job, repository-full-name, PR-selection, linkage-context,
  version, status, created/expiry, fingerprint, and consumption fields;
- `BEFORE UPDATE`/`BEFORE DELETE` triggers that reject mutation;
- a unique constraint preventing two accepted attestations for the same binding;
- a transaction that checks current owner/deletion/watched state and transitions atomically.

A minimal DDL shape for separate review (not executed) is:

```sql
CREATE TABLE canary_owner_attestations (
    attestation_id          TEXT PRIMARY KEY,
    schema_version          INTEGER NOT NULL CHECK (schema_version = 1),
    owner_user_id           INTEGER NOT NULL CHECK (owner_user_id > 0),
    conversation_id         TEXT NOT NULL,
    creation_job_id         INTEGER NOT NULL CHECK (creation_job_id > 0),
    repository_full_name    TEXT NOT NULL,
    repository_identity_digest TEXT NOT NULL CHECK (length(repository_identity_digest) = 64),
    pr_numbers_json         TEXT NOT NULL,
    pr_selection_digest     TEXT NOT NULL CHECK (length(pr_selection_digest) = 64),
    linkage_context_json    TEXT NOT NULL,
    binding_fingerprint     TEXT NOT NULL UNIQUE CHECK (length(binding_fingerprint) = 64),
    created_at              TEXT NOT NULL,
    expires_at              TEXT NOT NULL,
    CHECK (expires_at > created_at)
);

CREATE TABLE canary_owner_attestation_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    attestation_id  TEXT NOT NULL REFERENCES canary_owner_attestations(attestation_id),
    event_type      TEXT NOT NULL CHECK (event_type IN ('REQUESTED','ACCEPTED','REJECTED','CONSUMED')),
    owner_user_id   INTEGER NOT NULL CHECK (owner_user_id > 0),
    operation_key   TEXT,
    created_at      TEXT NOT NULL,
    event_fingerprint TEXT NOT NULL CHECK (length(event_fingerprint) = 64),
    UNIQUE (attestation_id, event_type),
    UNIQUE (attestation_id, operation_key)
);

CREATE TRIGGER trg_canary_attestation_header_no_update
BEFORE UPDATE ON canary_owner_attestations
BEGIN SELECT RAISE(ABORT, 'canary attestations are immutable'); END;

CREATE TRIGGER trg_canary_attestation_header_no_delete
BEFORE DELETE ON canary_owner_attestations
BEGIN SELECT RAISE(ABORT, 'canary attestations are immutable'); END;

CREATE TRIGGER trg_canary_attestation_event_no_update
BEFORE UPDATE ON canary_owner_attestation_events
BEGIN SELECT RAISE(ABORT, 'canary attestation events are immutable'); END;

CREATE TRIGGER trg_canary_attestation_event_no_delete
BEFORE DELETE ON canary_owner_attestation_events
BEGIN SELECT RAISE(ABORT, 'canary attestation events are immutable'); END;
```

Migration and compatibility considerations:

- Additive table creation only; no backfill and no mutation of existing rows.
- Existing `creation_jobs`/`auto_reviews` rows without an attestation remain ineligible
  for D-04; no false historical continuity.
- Old databases receive the tables through the existing idempotent schema setup, but
  this is still a schema change and therefore requires separate authorization.
- Raw GitHub numeric repository IDs are deliberately absent. If the owner requires the
  exact numeric ID in the audit record, D-04b must be separately approved; a one-way
  identity digest is the only non-D-04b-compatible alternative.
- The unique event constraints enforce one accepted and one consumed event per
  attestation; the transaction checks current owner, deletion, watched state, and exact
  binding before inserting an event.

Because D-04b forbids persisting numeric repository IDs, the design must also decide
whether a one-way identity commitment is sufficient or whether raw numeric-ID storage
requires a separate D-04b approval. The current D-04 policy asks to record the exact
numeric ID, while this task forbids persisting it; that conflict must be resolved before
implementation.

## 8. Integration points inspected

- `bot/review/canary_linkage.py`: D-01 B source and D-02 explicit-list service; no
  attestation request/consume hook.
- `bot/review/resolver.py`: verifies repository/PR/SHA and reserves memberships; no
  attestation parameter.
- `bot/review/authorization.py`: WP-01 cycle-bound owner revalidation; no cycle-less
  attestation path.
- `bot/db.py`: `reserve_conversation_review()` is the existing atomic conversation-wide
  reservation; no attestation field or table.
- `auto_review_owner_acceptance`: R6 report acceptance, separate domain.
- `creation_jobs`: exact D-01 B linkage source, but no numeric ID or attestation fields.

The current canary service can still resolve and reserve a verified explicit PR list
without a D-04 attestation. That is precisely why D-04 remains unimplemented rather than
being approximated with mutable storage.

## 9. Changed files and rationale

No implementation code, test code, schema, migration, configuration, worker, or runtime
wiring was changed. This report and the additive `.agent/PROGRESS.md` entry are the only
artifacts created by this task.

The blocker is reported before any forbidden schema change, as required.

## 10. Tests and exact results

Because safe durable persistence is unavailable, no D-04 implementation tests were
added: a test suite for a nonexistent durable lifecycle would create a false impression
of security. Existing behavior was regression-checked instead:

- `pytest -q tests/test_review_canary_linkage.py tests/test_review_resolver.py tests/test_review_callback.py tests/test_review_authorization_revalidation.py tests/test_auto_review_lifecycle.py tests/test_review_report.py tests/test_review_delivery.py tests/test_creation.py tests/test_miniapp_creation_jobs.py`
  → **235 passed, 2 warnings, 0 failed**.
- Full Python suite: `pytest -q` → **4335 passed, 74 warnings, 0 failed** in 323.24s.
- Node tests (run for completeness even though no frontend behavior changed):
  `node --test tests/frontend/*.test.js` → **280 pass, 0 fail**.
- `python -m pyflakes bot/ automation/ tools/ main.py tests/` → exit 0.
- `python -m compileall -q bot automation tools main.py tests` → exit 0.
- `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` → **0 High**,
  7 Low, 20 Medium (pre-existing pattern).
- `python -m pip_audit -r requirements-dev.txt` → **no known vulnerabilities**.
- `git diff --check` → exit 0.
- `pytest -q tests/test_doc_code_parity.py` → **16 passed**.

Required D-04 test cases are **not claimed as passing**; they remain blocked with the
implementation.

## 11. AUTHOR_SELF_REVIEW — NOT INDEPENDENT REVIEW

Findings:

1. **Replay/lifecycle:** cannot be proven without durable append-only state; no
   implementation was added.
2. **Owner changes:** current-owner revalidation must occur at request, confirmation,
   and consumption; a cycle-less path is missing for pre-cycle attestation.
3. **Stale authorization:** no cache is acceptable; current code has no D-04 cache, but
   no implementation exists.
4. **Conversation/repository/PR substitution:** the existing resolver checks D-01 B and
   D-02 inputs, but there is no attestation binding to those exact values.
5. **Fingerprint ambiguity:** canonical serialization and a version/domain separator are
   required; not implemented.
6. **TOCTOU:** owner/deletion/watched state must be re-read in the same transaction as
   the attestation transition; no safe transaction surface exists in current schema.
7. **Concurrency:** `settings` upsert and mutable rows cannot enforce one immutable
   accepted attestation; a unique key plus append-only event rows would be needed.
8. **Duplicate callbacks:** no D-04 callback path was added; future path must use
   idempotency and current-owner checks.
9. **Invalid transitions:** no state machine exists; must be enforced atomically.
10. **Database failure:** no implementation can falsely accept; any future implementation
    must fail closed on read/write failure.
11. **D-04/R6 conflation:** explicitly avoided; `auto_review_owner_acceptance` was not
    reused.
12. **Repository name vs identity:** full name is not permanent identity; no continuity
    claim was made.
13. **D-04b:** no numeric-ID persistence, column, index, trigger, migration, or backfill
    was added.
14. **External operations:** none performed.

No negative D-04 tests were added because no safe D-04 implementation exists. Adding
tests that only exercise a helper without durable persistence would not prove the
required security properties.

## 12. Remaining risks

- Current canary linkage can reserve a verified explicit PR list without a D-04
  attestation; live Canary use remains blocked by policy.
- Same-name repository deletion/recreation remains indistinguishable without a durable
  numeric-ID commitment; no continuity claim is made.
- The D-04 contract's request for an exact numeric ID conflicts with this task's
  prohibition on persisting numeric IDs; a separate owner decision is required.
- `ConversationRepositoryLink` lacks the exact creation-job ID needed for a complete
  linkage-context binding.
- `settings` is not an immutable audit ledger and must not be used as one.

## 13. D-04b exclusion confirmation

**D-04b remains `DEFERRED` and untouched.** No GitHub numeric repository ID was persisted,
backfilled, added as a column, indexed, triggered, or migrated. No D-04b implementation
was performed.

## 14. Final Git state

Recorded after this report and the additive PROGRESS entry:

- Branch: `agent/r6-review-delivery` (unchanged).
- HEAD: `01079676351aac869d09d4d1747661cd6f07d82b` (unchanged).
- `main` / `origin/main`: unchanged.
- HEAD tree: unchanged.
- Modified tracked: 12 (same pre-existing set; `.agent/PROGRESS.md` is one of them).
- Untracked entries: 70 (69 pre-existing plus this report).
- New artifact: this report; `.agent/PROGRESS.md` received an additive section.
- No code, test, schema, migration, runtime, or configuration changes by this task.
- No commit, push, PR, merge, deployment, or release.

## 15. External-operation confirmation

No OpenHands API call, GitHub API call/write, Actions dispatch, provider inference,
Telegram message, production database access, credential use, external data
transmission, worker activation, live Canary execution, deployment, or Git publication
was performed. Independent review remains deferred. R8 has not started.
