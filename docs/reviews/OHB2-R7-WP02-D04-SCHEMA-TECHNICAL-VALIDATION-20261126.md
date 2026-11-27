# OHB2-R7 WP-02 / D-04 — Schema Technical Validation

**Task ID:** `OHB2-R7-WP02-D04-SCHEMA-DESIGN-TECHNICAL-VALIDATION`
**Date:** 2026-11-26
**Verdict:** `WP02_D04_SCHEMA_DESIGN_NEEDS_REVISION`
**Review label:** `AUTHOR_SELF_REVIEW — NOT INDEPENDENT REVIEW`
**Current WP-02 status:** `WP02_D04_BLOCKED`
**`OD-R7-D04-SCHEMA-01`:** `PENDING — NOT APPROVED`

**Scope:** read-only technical validation and documentation only. No application code,
schema, migration, configuration, runtime, test, worker, Canary, or external operation
was created or changed. The SQL below is an unexecuted, unapproved proposal.

---

## 1. Baseline Git state

| Item | Value |
|---|---|
| Repository | `/workspace/project/OpenHandBot` |
| Branch | `agent/r6-review-delivery` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `origin/main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| HEAD tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| Modified tracked | 12 pre-existing |
| Untracked entries | 77 pre-existing |

All pre-existing modifications and untracked files, including `.openhands/`, were
preserved. This task adds only this report and an additive `.agent/PROGRESS.md`
section. No fetch, pull, reset, clean, or history change was performed.

### 1.1 Final state after this report

| Item | Value |
|---|---|
| Branch / HEAD / tree | unchanged |
| Modified tracked | 12 (same pre-existing set) |
| Untracked | 78 (77 pre-existing + this report) |
| Code / schema / migration / config / test changes | none |

### 1.2 Owner decision state

| Decision | Status |
|---|---|
| D-03 current-owner-revalidation | `APPROVED` |
| D-04 canary-only-owner-attestation | `APPROVED` in principle; implementation blocked |
| D-04b persist-numeric-repository-id | `DEFERRED — NOT APPROVED` |
| D-05 reject-rename-transfer | `APPROVED` |
| D-06 private-allowlisted-only | `APPROVED` |
| D-07 bounded Canary supervisor | `APPROVED_DESIGN_ONLY` |
| D-08 live Canary | `BLOCKED` |
| `OD-R7-D04-SCOPE-02` | `B1 APPROVED` |
| `OD-R7-D04-SCHEMA-01` | `PENDING` |
| `OD-R7-D04-AUTH-03` | `PENDING` |
| `OD-R7-D04-LIFECYCLE-04` | `PENDING`; TTL unselected |
| `OD-R7-D04-INTEGRATION-05` | `PENDING` |

## 2. Actual database architecture findings

### 2.1 Connection, durability, and foreign keys

`Database.__init__` (`bot/db.py:1115-1146`):

- one shared `sqlite3` connection with `check_same_thread=False`;
- `PRAGMA journal_mode=WAL`;
- `PRAGMA busy_timeout=5000`;
- `PRAGMA foreign_keys=ON`, with a fail-closed read-back check requiring `1`;
- schema initialization before normal operations.

Actual tests confirm WAL and busy timeout
(`tests/test_zero_touch_lifecycle.py:101`, `tests/test_security_invariants.py:29`) and
production foreign-key enforcement (`tests/test_attachment_message_identity_a3.py:64`).

### 2.2 Schema initialization and migration

`_init_schema()` uses `CREATE TABLE IF NOT EXISTS`, then `_migrate()` for additive
columns/indexes/triggers and a final commit (`bot/db.py:1152-1665`). There is no formal
schema-version table. Existing patterns are additive and idempotent. Tests demonstrate
repeated initialization and preservation of existing rows
(`tests/test_auto_reviews_db.py:90`, `:130`; `tests/test_auto_review_lifecycle.py:536`).

### 2.3 Existing immutable/append-only pattern

Actual protections are **no-update/no-delete triggers only**:

- `auto_review_provider_snapshots` (`bot/db.py:1411-1420`);
- `auto_review_memberships` (`bot/db.py:2022-2031`);
- `auto_review_evidence` (`bot/db.py:2032-2041`);
- `auto_review_reports` (`bot/db.py:2042-2051`);
- `auto_review_owner_acceptance` (`bot/db.py:2052-2061`).

They raise `ABORT` on update/delete. Tests assert `sqlite3.IntegrityError` on attempted
mutation (`tests/test_auto_reviews_db.py:140`; `tests/test_auto_review_lifecycle.py:469`;
`tests/test_review_canary_linkage.py:674`). There is no existing transition trigger or
generic lifecycle-state table. Immutability here means no row mutation, not legal
transition ordering.

### 2.4 Existing unique/partial indexes and idempotency

Active review-cycle enforcement uses mutable status + partial unique indexes
(`bot/db.py:1497-1502`). Idempotent reservation uses `reservation_key UNIQUE` plus
application identity comparison (`bot/db.py:8200-8220`); duplicate/conflict behavior is
tested (`tests/test_auto_reviews_db.py:190`).

R6 owner acceptance uses an idempotency key and unique
`(review_id, report_version, owner_user_id)` (`bot/db.py:1645-1658`). It is R6
report-acceptance, not D-04.

### 2.5 Reservation transaction

`reserve_conversation_review()` (`bot/db.py:8126-8349`):

- validates inputs first;
- `BEGIN IMMEDIATE`;
- rechecks provider snapshot, reservation key, active cycle, and pending memberships;
- inserts `auto_reviews`, then immutable `auto_review_memberships`;
- deletes consumed pending memberships;
- commits only at the end; any exception rolls back.

Existing tests cover idempotent duplicate, identity conflict, DB lock, and partial-state
rollback (`tests/test_auto_reviews_db.py:190`, `:413`;
`tests/test_review_canary_linkage.py:749`;
`tests/test_review_recovery_failures.py:35`).

### 2.6 Authorization and linkage

WP-01 `revalidate_review_authorization()` (`bot/review/authorization.py:40-130`) is
cycle-bound and re-reads current owner/chat/deletion/watched state. Tests cover stale
authorization, owner/chat mismatch, deletion, watched removal, DB-read failure,
restart, and delivery (`tests/test_review_authorization_revalidation.py:171`, `:222`,
`:273`, `:576`).

`creation_jobs` is mutable (`bot/db.py:1200-1215`) and has no numeric repository ID.
`CreationJobRepositoryLinkSource.resolve()` selects exactly one `done` job, checks
owner/chat and OpenHands selected repository, and verifies current GitHub identity
(`bot/review/canary_linkage.py:51-73`). `ConversationRepositoryLink` and
`MembershipProvenance` do not expose `creation_job_id`
(`bot/review/resolver.py:88-112`).

### 2.8 Why the existing tables are not substitutes

| Existing store | Actual constraint/problem |
|---|---|
| `settings` | Mutable upsert/delete; no immutability triggers or lifecycle columns. |
| `auto_review_owner_acceptance` | R6 report acceptance only; bound to `review_id`/`report_version`; no pre-cycle owner consent or repository/PR/expiry/consumption fields. |
| `auto_review_provider_snapshots` | Immutable but provider-configuration domain; no owner/conversation/PR/lifecycle. |
| `auto_review_memberships`, `auto_review_evidence`, `auto_review_reports` | Immutable but require an existing review cycle; R5/R6 evidence, not owner attestation. |
| `auto_reviews` | Mutable review-cycle state; using it before attestation inverts D-04. |
| `creation_jobs` | Correct D-01 B source, but mutable and no attestation lifecycle. |
| Operational tables (`outbox`, `notification_inbox`, `watched`, etc.) | Mutable delivery/ownership state; no immutable attestation semantics. |

This confirms that a dedicated lifecycle store is needed; it does not by itself make the
proposed two-table design sufficient.

## 3. Field review — `canary_owner_attestations`

| Field | Assessment |
|---|---|
| `attestation_id TEXT PRIMARY KEY` | Necessary; server-generated. No length/format/entropy check in the proposal. Add a bounded `CHECK`; never accept from callback. |
| `schema_version` / `generation` | Necessary contract and re-attestation version; `generation` does not enforce one active binding by itself. Allocate server-side under `BEGIN IMMEDIATE`. |
| `owner_user_id` | Necessary; `CHECK > 0` is useful, but “current owner” is application state and must be re-read at every transition. |
| `conversation_id` | Necessary; no pattern/length check in proposal. Validate in application/constraint. |
| `chat_id` + `chat_id = owner_user_id` | Necessary private-chat binding; equality check is useful but does not prove current watched chat. |
| `creation_job_id REFERENCES creation_jobs(id) ON DELETE RESTRICT` | Necessary exact D-01 B context; FK is real because FKs are ON. The referenced job remains mutable and may be discarded/changed; revalidate at request/confirm/consume. |
| `repository_full_name` | Necessary for B1; current name only, not permanent identity. Add canonical format/length validation. |
| `repository_link_source CHECK (= 'canary_creation_job')` | Necessary enum/provenance guard. |
| `pr_numbers_json` | Necessary payload, but no DB validation of JSON/canonical ordering/uniqueness/positivity/non-emptiness. Application canonicalization is mandatory. |
| `pr_selection_digest` | Useful integrity commitment; not identity. |
| `attestation_version`, `statement_version` | Necessary; add bounded format/length checks. |
| `binding_fingerprint UNIQUE` | Useful integrity commitment. It is **not** permanent repository identity and does not provide owner authentication. `UNIQUE` does not enforce one active attestation per semantic binding because it includes `generation`. |
| `requested_at`, `expires_at` | Necessary; `expires_at > requested_at` check is useful. Lexical comparison assumes canonical UTC ISO text; validate in application. |
| lifecycle status/timestamps in header | Not present. Event timestamps can be authoritative, but there is no direct `status` and no SQLite-enforced active-state key. Do not add a mutable status casually to the immutable header. |
| numeric repository ID | Correctly absent under B1. Do not add. Do not use a fingerprint as a substitute. |

Fields considered unsafe or redundant:

- Numeric repository ID or equivalent permanent identity: forbidden under B1.
- A mutable `status` header without an explicit state design: would conflict with the
  immutability claim and needs a state/projection design.
- Client-supplied `attestation_id`, `owner_user_id`, `chat_id`, `creation_job_id`,
  repository name, or PR set: must be derived server-side.
- Duplicated `confirmed_at`/`consumed_at`/`expired_at`/`revoked_at` in the header:
  unnecessary if events are mandatory and immutable; event timestamps are sufficient.

## 4. Field review — `canary_owner_attestation_events`

| Field | Assessment |
|---|---|
| `id INTEGER PRIMARY KEY AUTOINCREMENT` | Useful deterministic event ordering; `created_at` remains audit text. |
| `attestation_id REFERENCES ... ON DELETE RESTRICT` | Necessary; FK enforced. |
| `event_type` | Necessary closed enum, but insufficient to enforce transitions. |
| `from_state` / `to_state` | Missing. Needed to disambiguate `EXPIRED` from pending vs accepted and to validate transitions. Add bounded enum fields. |
| `owner_user_id` | Necessary for owner actions, but no actor-type distinguishes owner from system expiry/invalidation. Add `actor_type` (`OWNER`/`SYSTEM`) or equivalent. |
| `reason_code` | Missing. Required for safe rejection/expiry/revocation reasons; use a closed allowlist, never raw exception text. |
| `operation_key` | Partially present; partial unique index is useful, but `CONSUMED` is not required to have one. Add `CHECK`/constraint. |
| `review_id` | Useful consumption binding, but not unique. One review could be referenced by multiple consumed events unless app/partial unique index prevents it. |
| `created_at` | Necessary; validate canonical UTC ISO text. |
| `event_fingerprint` | Useful integrity only; not identity/authorization. |
| binding/version reference | The `attestation_id` FK to the immutable header is sufficient; duplicating `binding_fingerprint` or version in every event risks divergence. If retention/export requires it, copy it only as an audited immutable value. |
| `UNIQUE(attestation_id,event_type)` | Prevents duplicate same-type events, including duplicate accepted/consumed; does not prevent invalid combinations (e.g. accepted + rejected) or ensure `REQUESTED` exists. |
| append-only enforcement | Existing project pattern can block `UPDATE`/`DELETE` with `BEFORE` triggers, but does not block invalid `INSERT`, `DROP TABLE`, or out-of-band file modification. |

## 5. Constraint, index, and trigger recommendations

These are **recommendations only**, not applied:

1. Add `attestation_id`, `conversation_id`, `repository_full_name`, version, and
   timestamp length/format checks.
2. Require canonical `pr_numbers_json` in the application; do not trust client JSON.
3. Require `CONSUMED` to have both non-null `review_id` and non-null `operation_key`.
4. Add a unique partial index on `review_id WHERE event_type='CONSUMED'` if a review may
   be consumed by at most one attestation.
5. Add `from_state`/`to_state`, `reason_code`, and `actor_type` to the event table.
6. Add `BEFORE INSERT` transition triggers for at least:
   - `REQUESTED` only when no prior event exists;
   - `ACCEPTED` only from `pending`, before `expires_at`;
   - `REJECTED` only from `pending`;
   - `EXPIRED` only from `pending` or `accepted`, at/after `expires_at`;
   - `CONSUMED` only from `accepted`, before expiry;
   - `REVOKED` only from `accepted`, before consumption;
   - no event after a terminal state.
7. Add no-update/no-delete triggers on both tables, following the existing
   `RAISE(ABORT)` pattern.
8. Add indexes for `expires_at` and lifecycle lookups; not a security guarantee, but
   needed for bounded scanning.
9. For “one active attestation per semantic binding”, either add an explicit state
   projection with a partial unique index or document and test application-only
   enforcement under `BEGIN IMMEDIATE`. The two-table proposal cannot enforce this
   purely via SQLite constraints.

## 6. Transaction and concurrency analysis

Actual SQLite configuration provides WAL, a 5000 ms busy timeout, and fail-closed
foreign keys. `BEGIN IMMEDIATE` is the project’s proven write-lock pattern.

- **Request:** `BEGIN IMMEDIATE`; current owner/chat/deletion/watched checks; active
  binding query; generation allocation; canonical payload/fingerprint; insert header
  and `REQUESTED`; commit. Any failure rolls back.
- **Confirmation:** `BEGIN IMMEDIATE`; current owner/chat/deletion/watched; pending and
  expiry check; exact binding recomputation; insert `ACCEPTED`; duplicate returns
  existing accepted; conflict fails closed.
- **Consumption:** `BEGIN IMMEDIATE`; accepted/expiry/binding/owner checks; insert
  review + immutable memberships + `CONSUMED` event with `review_id` and operation key;
  commit all or roll back all.
- **External verification:** D-01 B/D-05/D-06 GitHub checks occur before the SQLite
  transaction because network I/O must not hold the write lock. The residual TOCTOU
  window remains; the transaction can only recheck persisted/current DB state.
- **Locks:** existing tests show lock failure leaves no reservation/partial state.
  The proposed transaction must not split consumption from reservation.
- **Concurrency:** unique accepted/consumed events and operation keys, plus
  `BEGIN IMMEDIATE`, prevent two winners; application still must handle `IntegrityError`
  and duplicate callbacks idempotently.
- **Expiry:** `expires_at` must be checked inside the transition transaction; no silent
  extension. A lazy expiry read/event is needed; there is no scheduler and none is
  authorized.

### 6.1 Foreign-key and deletion behavior

- `creation_job_id REFERENCES creation_jobs(id) ON DELETE RESTRICT` prevents deleting a
  referenced creation job; the current code does not delete creation jobs, but the FK is
  still meaningful. It does not freeze the job's mutable status/repo.
- `canary_owner_attestation_events.attestation_id` should use `ON DELETE RESTRICT`; both
  tables also get no-delete triggers, so events cannot be deleted independently.
- `review_id REFERENCES auto_reviews(id) ON DELETE RESTRICT` means a consumed
  attestation would block deletion of that review cycle. Current code has no
  `DELETE FROM auto_reviews` path; future cleanup must account for this FK.
- `ON DELETE CASCADE` used by existing R5/R6 child tables is **not** appropriate for
  an audit ledger; a cascade could erase attestation history.

### 6.2 Unauthorized state changes and replay

- Direct `INSERT` into the event table can create unauthorized transitions unless the
  application and/or `BEFORE INSERT` triggers enforce ownership and state. The no-update/
  no-delete triggers do not cover this.
- `owner_user_id` must be recomputed/revalidated from current owner state, not trusted
  from a callback or existing header alone.
- Cross-conversation reuse is prevented only by exact binding checks at request,
  confirmation, and consumption; the schema FK to conversation is not enough because
  `conversation_id` is just text.
- Reuse after owner, D-01 B, D-05/D-06, repository name, or PR-set change requires
  application revalidation and, where applicable, `REVOKED`/`EXPIRED` before
  consumption. The schema alone cannot detect external changes.

### 6.3 Invariant/enforcement matrix

| # | Invariant | SQLite-enforced? | Required enforcement |
|---|---|---|---|
| 1 | One active attestation per intended binding | Not by the proposed two tables; `binding_fingerprint` includes generation | App query under `BEGIN IMMEDIATE`; or add a state projection with partial unique index |
| 2 | Duplicate request handling | Unique fingerprint/event only if generation fixed; no semantic uniqueness | App semantic lookup plus unique event/operation checks |
| 3 | Duplicate confirmation idempotency | `UNIQUE(attestation_id,event_type)` | App exact owner/binding check; return existing accepted |
| 4 | Rejection/expiration terminality | No; unique type does not prevent later invalid events | App state check plus `BEFORE INSERT` triggers |
| 5 | One-time consumption | `UNIQUE(attestation_id,'CONSUMED')` helps | App accepted/expiry/binding checks; required operation key |
| 6 | Revocation semantics | No; no from/to enforcement | App `accepted` check; trigger rejects after consumed/expired |
| 7 | Expiration under concurrency | No | `BEGIN IMMEDIATE` and fresh `expires_at` check; optional trigger |
| 8 | Atomic event creation with every transition | No update/delete triggers do not cover inserts | Same transaction as state check and header write |
| 9 | Atomic consumption with reservation/membership | Foreign keys only | Same `BEGIN IMMEDIATE` transaction; review+membership+event commit/rollback together |
| 10 | Rollback on failure | SQLite transaction rollback | App `try/except` rollback; no partial commit |
| 11 | Lock and busy handling | WAL + `busy_timeout=5000` | Reuse actual `Database` connection and `BEGIN IMMEDIATE`; safe busy error |
| 12 | Foreign-key/deletion behavior | `foreign_keys=ON`, FK RESTRICT | Do not use CASCADE for audit; revalidate mutable creation job |
| 13 | Unauthorized state changes | No; direct INSERT can bypass | App authorization + `BEFORE INSERT` transition/owner checks |
| 14 | Replay/cross-conversation reuse | Unique operation/event only | Exact binding/owner/chat/conversation revalidation at each transition |
| 15 | Reuse after owner/link/PR-set changes | No | App revalidation; revoke/expire pending/accepted before consumption |

## 7. Lifecycle validation

`not_requested -> pending -> accepted | rejected | expired`
`accepted -> consumed | expired | revoked`

| Transition | Schema representation | SQLite-enforced? | Application requirement |
|---|---|---|---|
| `not_requested -> pending` | Header + `REQUESTED` | No transition trigger | No prior active/header; current owner/linkage; generation allocation |
| `pending -> accepted` | `ACCEPTED` | No; accepted can be inserted without requested | Pending, not expired, current owner, exact binding |
| `pending -> rejected` | `REJECTED` | No | Pending, actor/reason |
| `pending -> expired` | `EXPIRED` | No | `now >= expires_at`, no terminal |
| `accepted -> consumed` | `CONSUMED` + review | No; only review_id check | Accepted, before expiry, exact binding, atomic reservation |
| `accepted -> expired` | `EXPIRED` | No; from_state absent | Distinguish pending vs accepted; no consumed |
| `accepted -> revoked` | `REVOKED` | No; from/to absent | Accepted, before consumption, actor/reason |
| terminal | terminal event | Same-type duplicate only; invalid combinations possible | Reject all later transitions |

Ambiguities/answers:

- Expired attestation **cannot** be confirmed; transaction must reject or append
  `EXPIRED`.
- Accepted attestation **can** be revoked before consumption.
- Revocation **cannot** be allowed after consumption; the proposed DDL alone does not
  enforce this.
- Duplicate Telegram confirmations are idempotent only with exact attestation/owner/
  binding checks; unique event type is necessary but not sufficient.
- Owner/binding changes must invalidate pending (reject/expire) or accepted (revoke/
  expire) before consumption; schema cannot observe external changes by itself.
- **No TTL is selected here.** `expires_at` is required; exact duration belongs to
  `OD-R7-D04-LIFECYCLE-04`.

## 8. B1 and D-04b boundary validation

- No numeric GitHub repository ID field is proposed.
- No creation-time numeric identity or backfill is proposed.
- `binding_fingerprint` is integrity protection only, not permanent identity.
- Same-name deletion/recreation remains indistinguishable.
- D-05 rename/transfer/redirect checks remain application-enforced; the schema does not
  bypass them.
- D-06 private/allowlisted/fork/archive/deleted checks remain application-enforced; the
  schema does not bypass them.
- B1 does not complete WP-04; `WP04_D06_BLOCKED` remains.
- D-04b remains `DEFERRED` and untouched.

## 9. Authorization and integration dependencies

- Current WP-01 helper is cycle-bound. A1 can work with this schema (pre-cycle header
  has no cycle ID); A2 would need an explicit review-cycle reference in the immutable
  header, which the proposed schema does not have. Do not choose A1/A2 here.
- I1 can work with this schema (`creation_job_id` header + `review_id` in consumed
  event + future reservation transaction). I2 rejects integration; no schema decision
  is made.
- D-01 B exact creation-job binding requires exposing `creation_job_id` in the in-memory
  link/provenance. The schema FK alone does not prove the job is still current/done.
- R6 `auto_review_owner_acceptance` must not be reused.

## 10. Design defects and unresolved questions

### 10.1 Blocking/needs-revision findings

1. **No SQLite-level active-attestation uniqueness.** `binding_fingerprint` includes
   `generation`, so it does not enforce one pending/accepted attestation per semantic
   binding. Application enforcement under `BEGIN IMMEDIATE` or an explicit state
   projection is required.
2. **No lifecycle transition enforcement.** The proposed events table permits invalid
   combinations without application/triggers; `ACCEPTED` can exist without
   `REQUESTED`, and `REVOKED` can follow `CONSUMED`.
3. **Missing audit fields.** No `reason_code`; no `from_state`/`to_state`; no
   actor-type distinction. `EXPIRED` origin is ambiguous from the event row alone.
4. **Incomplete consumption constraints.** `CONSUMED` requires `review_id` but not
   `operation_key`; `review_id` is not unique across consumed events.
5. **A2 incompatibility.** The immutable header has no review-cycle reference; A2
   cannot bind an exact authorized cycle as proposed.
6. **`creation_jobs` mutability.** FK is valid, but it does not prove current `done`
   status/repo; revalidation is required.

### 10.2 Non-blocking/application invariants

- Canonical JSON, sorted unique PRs, non-empty list, positive PR numbers.
- Canonical UTC ISO timestamps and casefold full-name comparison.
- Current owner/chat/deletion/watched revalidation.
- Current D-01 B/D-05/D-06 revalidation.
- No secret/provider payloads in any column.

## 11. Recommended schema — documentation only, NOT APPROVED

The following illustrates the minimum revisions to address the findings. It is not
executed or approved. It intentionally omits numeric repository IDs.

```sql
CREATE TABLE canary_owner_attestations (
    attestation_id         TEXT PRIMARY KEY
                           CHECK (length(attestation_id) BETWEEN 16 AND 128),
    schema_version         INTEGER NOT NULL CHECK (schema_version = 1),
    generation             INTEGER NOT NULL CHECK (generation > 0),
    owner_user_id          INTEGER NOT NULL CHECK (owner_user_id > 0),
    conversation_id        TEXT NOT NULL CHECK (length(conversation_id) BETWEEN 1 AND 128),
    chat_id                INTEGER NOT NULL CHECK (chat_id > 0),
    creation_job_id        INTEGER NOT NULL
                           REFERENCES creation_jobs(id) ON DELETE RESTRICT,
    repository_full_name   TEXT NOT NULL
                           CHECK (length(repository_full_name) BETWEEN 1 AND 255),
    repository_link_source TEXT NOT NULL CHECK (repository_link_source = 'canary_creation_job'),
    pr_numbers_json        TEXT NOT NULL CHECK (length(pr_numbers_json) BETWEEN 2 AND 4096),
    pr_selection_digest    TEXT NOT NULL CHECK (length(pr_selection_digest) = 64),
    attestation_version    TEXT NOT NULL CHECK (length(attestation_version) BETWEEN 1 AND 64),
    statement_version      TEXT NOT NULL CHECK (length(statement_version) BETWEEN 1 AND 64),
    binding_fingerprint    TEXT NOT NULL UNIQUE CHECK (length(binding_fingerprint) = 64),
    requested_at           TEXT NOT NULL CHECK (length(requested_at) BETWEEN 20 AND 64),
    expires_at             TEXT NOT NULL CHECK (length(expires_at) BETWEEN 20 AND 64),
    CHECK (chat_id = owner_user_id),
    CHECK (expires_at > requested_at)
);

CREATE TABLE canary_owner_attestation_events (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    attestation_id    TEXT NOT NULL
                      REFERENCES canary_owner_attestations(attestation_id)
                      ON DELETE RESTRICT,
    event_type        TEXT NOT NULL CHECK (event_type IN
                      ('REQUESTED','ACCEPTED','REJECTED','EXPIRED','CONSUMED','REVOKED')),
    from_state        TEXT NOT NULL CHECK (from_state IN
                      ('not_requested','pending','accepted')),
    to_state          TEXT NOT NULL CHECK (to_state IN
                      ('pending','accepted','rejected','expired','consumed','revoked')),
    owner_user_id     INTEGER NOT NULL CHECK (owner_user_id > 0),
    actor_type        TEXT NOT NULL CHECK (actor_type IN ('OWNER','SYSTEM')),
    reason_code       TEXT CHECK (reason_code IS NULL OR length(reason_code) BETWEEN 1 AND 64),
    operation_key     TEXT,
    review_id         INTEGER REFERENCES auto_reviews(id) ON DELETE RESTRICT,
    created_at        TEXT NOT NULL CHECK (length(created_at) BETWEEN 20 AND 64),
    event_fingerprint TEXT NOT NULL CHECK (length(event_fingerprint) = 64),
    UNIQUE (attestation_id, event_type),
    CHECK (event_type <> 'CONSUMED' OR
           (review_id IS NOT NULL AND operation_key IS NOT NULL))
);

CREATE UNIQUE INDEX ux_canary_attestation_operation
    ON canary_owner_attestation_events(attestation_id, operation_key)
    WHERE operation_key IS NOT NULL;

CREATE UNIQUE INDEX ux_canary_attestation_consumed_review
    ON canary_owner_attestation_events(review_id)
    WHERE event_type = 'CONSUMED';

CREATE TRIGGER trg_canary_attestation_no_update
BEFORE UPDATE ON canary_owner_attestations
BEGIN SELECT RAISE(ABORT, 'canary attestations are immutable'); END;

CREATE TRIGGER trg_canary_attestation_no_delete
BEFORE DELETE ON canary_owner_attestations
BEGIN SELECT RAISE(ABORT, 'canary attestations are immutable'); END;

CREATE TRIGGER trg_canary_attestation_event_no_update
BEFORE UPDATE ON canary_owner_attestation_events
BEGIN SELECT RAISE(ABORT, 'canary attestation events are immutable'); END;

CREATE TRIGGER trg_canary_attestation_event_no_delete
BEFORE DELETE ON canary_owner_attestation_events
BEGIN SELECT RAISE(ABORT, 'canary attestation events are immutable'); END;
```

This revised sketch still does **not** provide SQLite-level uniqueness of one active
attestation per semantic binding. If the owner requires that guarantee in the database,
add an explicit state projection/active-key table with a partial unique index. If
application-only enforcement is accepted, it must be specified and tested under
`BEGIN IMMEDIATE`.

## 12. Owner decision summary — `OD-R7-D04-SCHEMA-01`

**Current status: `PENDING — NOT APPROVED`.**

The proposed v1 two-table design is not ready for approval as written. Before approving,
the owner should decide whether to:

- require the revisions in §10-§11 (reason/actor/from/to, consumed operation/review
  constraints, transition enforcement), and whether active-binding uniqueness must be
  SQLite-enforced or application-enforced; or
- approve a revised design explicitly.

No schema is approved by this report. B1 remains approved only for its name-bound scope.
The owner has not approved any revision.

## 13. Implementation authorization gate

Even after schema approval:

- D-04 is not implemented.
- No code, schema, migration, configuration, runtime, worker, or test change is
  authorized by this report.
- A separate explicit implementation authorization is required.
- D-04b remains deferred; no numeric ID or identity substitute.
- WP-04 remains blocked.
- WP-05 must not start; WP-06/live Canary remain blocked.

## 14. Verification and status distinctions

- Actual tests inspected, not executed for this unimplemented design; no test result is
  claimed as proof of D-04 behavior.
- Documentation parity: `pytest -q tests/test_doc_code_parity.py` → **16 passed**.
- `git diff --check` → clean.
- Only this report and the additive `.agent/PROGRESS.md` entry were introduced.
- No application code, schema, migration, configuration, or test file was modified.
- B1 remains approved without expansion; D-04b deferred; `OD-R7-D04-SCHEMA-01` pending.

### 14.1 Status distinctions

- **Technical design validation:** complete; findings require revision.
- **Owner schema approval:** not granted; `PENDING`.
- **Implementation authorization:** absent.
- **Implementation:** not started; WP-02 blocked.
- **Independent review:** deferred/not present.
- **D-04b:** `DEFERRED` and untouched.
- **WP-04:** `WP04_D06_BLOCKED`.
- **WP-05 / WP-06:** not started / live Canary blocked.
- **Working tree vs committed:** local working-tree only; unpublished.
- **Report verdict:** `WP02_D04_SCHEMA_DESIGN_NEEDS_REVISION`.
