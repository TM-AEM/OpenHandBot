# OHB2-R7 WP-02 / D-04 — Schema Design Revision v2

**Task ID:** `OHB2-R7-WP02-D04-SCHEMA-DESIGN-REVISION-V2`
**Date:** 2026-11-26
**Verdict:** `WP02_D04_SCHEMA_V2_READY_FOR_OWNER_REVIEW`
**Review label:** `AUTHOR_SELF_REVIEW — NOT INDEPENDENT REVIEW`
**Current WP-02 status:** `WP02_D04_BLOCKED`
**`OD-R7-D04-SCHEMA-01`:** `PENDING — NOT APPROVED`

**Scope:** design and documentation only. No tables, migrations, triggers, indexes,
application code, configuration, tests, workers, Canary, or external operations were
created or changed. The DDL below is **NOT EXECUTED and NOT APPROVED**.

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
| Modified tracked files | `.agent/PROGRESS.md`, `.env.example`, `README.md`, `bot/app.py`, `bot/config.py`, `bot/db.py`, `bot/handlers.py`, `bot/outbox.py`, `docs/OPERATIONS_RUNBOOK.md`, `tests/test_def011_a_option_b_limits.py`, `tests/test_def011_fs_offload.py`, `tests/test_doc_code_parity.py` |
| Untracked entries | 78 pre-existing: `.github/workflows/verify.yml`, `bot/review/`, review tests, docs/review reports, and other pre-existing artifacts |

All pre-existing modifications and untracked files, including `.openhands/`, were
preserved. No fetch, pull, reset, clean, or history change was performed.

### 1.1 Final state after this report

| Item | Value |
|---|---|
| Branch / HEAD / tree | unchanged |
| Modified tracked | 12 (same pre-existing set) |
| Untracked | 79 (78 pre-existing + this report) |
| Code / schema / migration / config / test changes | none |

### 1.2 Decision state

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

## 2. Summary of v1 defects

The previous technical validation
(`docs/reviews/OHB2-R7-WP02-D04-SCHEMA-TECHNICAL-VALIDATION-20261126.md`) found:

1. `binding_fingerprint UNIQUE` included `generation`; it did not enforce one active
   attestation per semantic binding.
2. Event uniqueness did not prevent invalid transitions such as acceptance without a
   request, consumption without acceptance, or revocation after consumption.
3. The event model lacked `from_state`, `to_state`, actor type, and safe reason code.
4. Consumption did not require `operation_key`; one review could be referenced by
   multiple consumed events; `review_id` had no uniqueness.
5. A2 could not bind an exact review cycle because the immutable header had no cycle
   reference.
6. A foreign key to mutable `creation_jobs` did not prove that the job remained valid
   or that its repository linkage was unchanged.

v2 corrects all six findings with:
- a stable semantic `binding_key` excluding `generation`;
- an explicit current-state projection with a partial unique active index;
- append-only events with from/to states, actor, reason, and binding reference;
- transition guards and projection triggers;
- complete consumption constraints;
- optional A2 cycle binding;
- explicit creation-job revalidation at request/confirmation/consumption.

### 2.1 Finding-to-correction map

| Finding | v2 correction |
|---|---|
| F1 active-binding uniqueness | Stable `binding_key` (§8) plus `canary_owner_attestation_state` partial unique index. |
| F2 transition enforcement | `from_state`/`to_state`, event guard, state projection trigger, and application transaction checks (§6-§7). |
| F3 audit event model | Event actor type/id, reason code, from/to state, operation key, binding reference, and append-only triggers (§4.2, §6.1). |
| F4 consumption invariants | Required review/operation key, unique consumed review, unique operation, and atomic reservation (§9, §12.2). |
| F5 A1/A2 compatibility | Optional `authorization_mode`/`bound_review_id` in one schema with exact-cycle checks (§10). |
| F6 creation-job linkage | Snapshot fields plus request/confirmation/consumption revalidation; FK is not validity proof (§11). |

## 3. Revised table definitions

v2 uses three tables:

1. `canary_owner_attestations` — immutable binding header.
2. `canary_owner_attestation_events` — append-only audit/transition log.
3. `canary_owner_attestation_state` — one current-state row per attestation and the
   partial unique active-binding guarantee.

The state table is a projection, not an independent source of truth; the immutable
event ledger is the audit source. The projection is updated only by the event trigger
and is never deleted.

### 3.1 `canary_owner_attestations`

| Field | Type / constraint | Rationale |
|---|---|---|
| `attestation_id` | `TEXT PRIMARY KEY CHECK(length BETWEEN 16 AND 128)` | Server-generated stable ID; never accepted from a callback. |
| `schema_version` | `INTEGER NOT NULL CHECK (=2)` | Explicit contract version. |
| `generation` | `INTEGER NOT NULL CHECK (>0)` | Server-allocated attempt number after terminal state; not part of `binding_key`. |
| `binding_key` | `TEXT NOT NULL CHECK(length=64)` | Stable SHA-256 over semantic binding; excludes `generation`; not permanent repository identity. |
| `owner_user_id` | `INTEGER NOT NULL CHECK (>0)` | Authoritative owner at request/confirm/consume. |
| `conversation_id` | `TEXT NOT NULL CHECK(length 1..128)` | Exact OpenHands conversation. |
| `chat_id` | `INTEGER NOT NULL CHECK (>0)` + `chat_id = owner_user_id` | Private owner chat binding. |
| `creation_job_id` | `INTEGER NOT NULL REFERENCES creation_jobs(id) ON DELETE RESTRICT` | Exact D-01 B context; revalidated separately. |
| `repository_full_name` | `TEXT NOT NULL CHECK(length 1..255)` | Canonical current full name; not permanent identity. |
| `repository_link_source` | `TEXT NOT NULL CHECK (= 'canary_creation_job')` | Link provenance. |
| `pr_numbers_json` | `TEXT NOT NULL CHECK(length 2..4096)` | Canonical sorted unique exact PR set; semantic validation in application. |
| `pr_selection_digest` | `TEXT NOT NULL CHECK(length=64)` | Integrity of the PR set; not identity. |
| `attestation_version` | `TEXT NOT NULL CHECK(length 1..64)` | Attestation contract version. |
| `statement_version` | `TEXT NOT NULL CHECK(length 1..64)` | Owner statement version. |
| `authorization_mode` | `TEXT NOT NULL CHECK IN ('PRE_CYCLE','EXISTING_CYCLE')` | Accommodates A1/A2 without selecting either. |
| `bound_review_id` | `INTEGER NULL REFERENCES auto_reviews(id) ON DELETE RESTRICT` | A2 only; exact authorized cycle. NULL for A1. |
| `requested_at` | `TEXT NOT NULL CHECK(length 20..64)` | Canonical UTC ISO request timestamp. |
| `expires_at` | `TEXT NOT NULL CHECK(length 20..64)` | Fixed expiration; no silent extension. |
| uniqueness | `UNIQUE(binding_key, generation)`; `UNIQUE(attestation_id)` inherent | Prevents duplicate generation; terminal generations permit a later generation. |
| mode check | `CHECK ((authorization_mode='PRE_CYCLE' AND bound_review_id IS NULL) OR (authorization_mode='EXISTING_CYCLE' AND bound_review_id IS NOT NULL))` | Exact A1/A2 shape. |
| time check | `CHECK (expires_at > requested_at)` | Fixed positive TTL; duration is owner-selected later. |

No numeric repository ID column exists. No `status` column is stored in the immutable
header; current state lives in the projection table.

### 3.2 `canary_owner_attestation_events`

| Field | Type / constraint | Rationale |
|---|---|---|
| `id` | Integer primary key autoincrement | Deterministic event order. |
| `attestation_id` | FK to header, `ON DELETE RESTRICT` | Parent binding. |
| `binding_key` | `TEXT NOT NULL CHECK(length=64)` | Audit reference; trigger must match immutable header. |
| `event_type` | Closed enum: `REQUESTED`, `ACCEPTED`, `REJECTED`, `EXPIRED`, `CONSUMED`, `REVOKED` | Transition kind. |
| `from_state` | Closed enum: `not_requested`, `pending`, `accepted` | Previous state; makes expiry origin explicit. |
| `to_state` | Closed enum: `pending`, `accepted`, `rejected`, `expired`, `consumed`, `revoked` | Resulting state. |
| `actor_type` | `OWNER` or `SYSTEM` | Distinguishes owner actions from expiry/invalidation. |
| `actor_id` | nullable integer | Owner user ID for `OWNER`; NULL for `SYSTEM`. |
| `reason_code` | nullable bounded safe code | Rejection/expiry/revocation reason; no raw exceptions or secrets. |
| `operation_key` | nullable bounded text | Mandatory for consumption; optional elsewhere as needed. |
| `review_id` | nullable FK to `auto_reviews`, `ON DELETE RESTRICT` | Consumption binding. |
| `created_at` | canonical UTC ISO text | Transition timestamp. |
| `event_fingerprint` | 64-char integrity value | Tamper detection only; not identity/authorization. |
| uniqueness | `UNIQUE(attestation_id, event_type)` | At most one accepted/rejected/expired/consumed/revoked event per attestation. |
| operation uniqueness | `UNIQUE(attestation_id, operation_key) WHERE operation_key IS NOT NULL` | One operation per attestation; no conflicting replay. |
| consumption check | `CHECK (event_type <> 'CONSUMED' OR (review_id IS NOT NULL AND operation_key IS NOT NULL))` | Consumption must bind exactly one review and operation. |
| review uniqueness | `UNIQUE(review_id) WHERE event_type='CONSUMED'` | One review cannot be consumed by multiple attestations. |

No prompts, provider payloads, tokens, raw diffs, or unnecessary personal data are
stored.

### 3.3 `canary_owner_attestation_state`

| Field | Type / constraint | Rationale |
|---|---|---|
| `attestation_id` | `TEXT PRIMARY KEY REFERENCES header ON DELETE RESTRICT` | One projection row per attestation. |
| `binding_key` | `TEXT NOT NULL` | Stable semantic key; trigger checks it equals header. |
| `status` | `TEXT NOT NULL CHECK IN ('pending','accepted','rejected','expired','consumed','revoked')` | Current derived state. |
| `updated_at` | canonical UTC ISO text | Projection update timestamp. |
| active uniqueness | `CREATE UNIQUE INDEX ... ON state(binding_key) WHERE status IN ('pending','accepted')` | SQLite-enforced one active attestation per semantic binding. |
| no deletion | `BEFORE DELETE` trigger raises ABORT | Audit/history cannot lose the projection. |

The state table is mutable only through allowed transition updates driven by the event
insert trigger. The immutable event ledger remains the audit record.

## 4. Field-by-field rationale

### 4.1 Header fields

- `binding_key` excludes `generation`, `requested_at`, `expires_at`, and all
  fingerprints. It is stable for the same semantic binding and changes only when the
  semantic binding changes.
- `generation` is allocated under `BEGIN IMMEDIATE` as `MAX(generation)+1` for the
  binding after a terminal state; it is not included in `binding_key`.
- `owner_user_id`, `conversation_id`, `chat_id`, and `creation_job_id` are exact
  snapshots, never trusted from callback data.
- `repository_full_name` is a display/current name; `casefold()` is used only for
  canonical comparison in `binding_key`, not as proof of durable identity.
- `pr_numbers_json` is canonical JSON: sorted ascending, unique, positive integers,
  no whitespace, no duplicates, non-empty. `pr_selection_digest` is recomputed
  server-side.
- `authorization_mode` and `bound_review_id` are optional only to keep A1/A2 open.
  A1 rows have NULL `bound_review_id`; A2 rows must bind a specific existing cycle.
- `requested_at`/`expires_at` use canonical UTC ISO text. `expires_at` is fixed at
  creation; no update path exists.
- No numeric GitHub repository ID is persisted; no creation-time identity; no backfill.

### 4.2 Event fields

- `from_state` and `to_state` make every transition explicit and let triggers reject
  illegal sequences.
- `actor_type`/`actor_id` distinguishes owner actions from system expiry/invalidation.
- `reason_code` is a closed safe code, not free-form exception text.
- `operation_key` is mandatory for `CONSUMED` and unique per attestation.
- `review_id` is mandatory for `CONSUMED` and unique across consumed events.
- `binding_key` in events is validated against the immutable header; it is an audit
  reference, not a second identity source.
- `event_fingerprint` protects row integrity; no secret or provider payload is included.

### 4.3 State fields

- `status` is the only mutable state field; it is maintained from events.
- The partial unique active index is the core F1 correction.
- `updated_at` is operational; it cannot override the event history.

## 5. Proposed DDL — NOT EXECUTED, NOT APPROVED

The following is illustrative only. It must not be executed or migrated by this task.

```sql
CREATE TABLE canary_owner_attestations (
    attestation_id         TEXT PRIMARY KEY
                           CHECK (length(attestation_id) BETWEEN 16 AND 128),
    schema_version         INTEGER NOT NULL CHECK (schema_version = 2),
    generation             INTEGER NOT NULL CHECK (generation > 0),
    binding_key            TEXT NOT NULL CHECK (length(binding_key) = 64),
    owner_user_id          INTEGER NOT NULL CHECK (owner_user_id > 0),
    conversation_id        TEXT NOT NULL CHECK (length(conversation_id) BETWEEN 1 AND 128),
    chat_id                INTEGER NOT NULL CHECK (chat_id > 0),
    creation_job_id        INTEGER NOT NULL
                           REFERENCES creation_jobs(id) ON DELETE RESTRICT,
    repository_full_name   TEXT NOT NULL
                           CHECK (length(repository_full_name) BETWEEN 1 AND 255),
    repository_link_source TEXT NOT NULL
                           CHECK (repository_link_source = 'canary_creation_job'),
    pr_numbers_json        TEXT NOT NULL CHECK (length(pr_numbers_json) BETWEEN 2 AND 4096),
    pr_selection_digest    TEXT NOT NULL CHECK (length(pr_selection_digest) = 64),
    attestation_version    TEXT NOT NULL CHECK (length(attestation_version) BETWEEN 1 AND 64),
    statement_version      TEXT NOT NULL CHECK (length(statement_version) BETWEEN 1 AND 64),
    authorization_mode     TEXT NOT NULL
                           CHECK (authorization_mode IN ('PRE_CYCLE','EXISTING_CYCLE')),
    bound_review_id        INTEGER REFERENCES auto_reviews(id) ON DELETE RESTRICT,
    requested_at           TEXT NOT NULL CHECK (length(requested_at) BETWEEN 20 AND 64),
    expires_at             TEXT NOT NULL CHECK (length(expires_at) BETWEEN 20 AND 64),
    CHECK (chat_id = owner_user_id),
    CHECK (expires_at > requested_at),
    CHECK ((authorization_mode = 'PRE_CYCLE' AND bound_review_id IS NULL) OR
           (authorization_mode = 'EXISTING_CYCLE' AND bound_review_id IS NOT NULL)),
    UNIQUE (binding_key, generation)
);

CREATE TABLE canary_owner_attestation_events (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    attestation_id    TEXT NOT NULL
                      REFERENCES canary_owner_attestations(attestation_id)
                      ON DELETE RESTRICT,
    binding_key       TEXT NOT NULL CHECK (length(binding_key) = 64),
    event_type        TEXT NOT NULL CHECK (event_type IN
                      ('REQUESTED','ACCEPTED','REJECTED','EXPIRED','CONSUMED','REVOKED')),
    from_state        TEXT NOT NULL CHECK (from_state IN
                      ('not_requested','pending','accepted')),
    to_state          TEXT NOT NULL CHECK (to_state IN
                      ('pending','accepted','rejected','expired','consumed','revoked')),
    actor_type        TEXT NOT NULL CHECK (actor_type IN ('OWNER','SYSTEM')),
    actor_id          INTEGER,
    reason_code       TEXT CHECK (reason_code IS NULL OR length(reason_code) BETWEEN 1 AND 64),
    operation_key     TEXT CHECK (operation_key IS NULL OR length(operation_key) BETWEEN 1 AND 128),
    review_id         INTEGER REFERENCES auto_reviews(id) ON DELETE RESTRICT,
    created_at        TEXT NOT NULL CHECK (length(created_at) BETWEEN 20 AND 64),
    event_fingerprint TEXT NOT NULL CHECK (length(event_fingerprint) = 64),
    UNIQUE (attestation_id, event_type),
    CHECK (event_type <> 'CONSUMED' OR
           (review_id IS NOT NULL AND operation_key IS NOT NULL))
);

CREATE TABLE canary_owner_attestation_state (
    attestation_id TEXT PRIMARY KEY
                   REFERENCES canary_owner_attestations(attestation_id)
                   ON DELETE RESTRICT,
    binding_key    TEXT NOT NULL CHECK (length(binding_key) = 64),
    status         TEXT NOT NULL CHECK (status IN
                   ('pending','accepted','rejected','expired','consumed','revoked')),
    updated_at     TEXT NOT NULL CHECK (length(updated_at) BETWEEN 20 AND 64)
);

CREATE UNIQUE INDEX ux_canary_attestation_active_binding
    ON canary_owner_attestation_state(binding_key)
    WHERE status IN ('pending','accepted');

CREATE UNIQUE INDEX ux_canary_attestation_operation
    ON canary_owner_attestation_events(attestation_id, operation_key)
    WHERE operation_key IS NOT NULL;

CREATE UNIQUE INDEX ux_canary_attestation_consumed_review
    ON canary_owner_attestation_events(review_id)
    WHERE event_type = 'CONSUMED';
```

## 6. Constraints, indexes, and triggers

### 6.1 Append-only triggers

Follow the actual project pattern from `bot/db.py`:

```sql
CREATE TRIGGER trg_canary_attestation_no_update
BEFORE UPDATE ON canary_owner_attestations
BEGIN SELECT RAISE(ABORT, 'canary attestations are immutable'); END;

CREATE TRIGGER trg_canary_attestation_no_delete
BEFORE DELETE ON canary_owner_attestations
BEGIN SELECT RAISE(ABORT, 'canary attestations are immutable'); END;

CREATE TRIGGER trg_canary_event_no_update
BEFORE UPDATE ON canary_owner_attestation_events
BEGIN SELECT RAISE(ABORT, 'canary attestation events are immutable'); END;

CREATE TRIGGER trg_canary_event_no_delete
BEFORE DELETE ON canary_owner_attestation_events
BEGIN SELECT RAISE(ABORT, 'canary attestation events are immutable'); END;

CREATE TRIGGER trg_canary_state_no_delete
BEFORE DELETE ON canary_owner_attestation_state
BEGIN SELECT RAISE(ABORT, 'canary attestation state cannot be deleted'); END;
```

These triggers prevent row mutation but do not prevent out-of-band DB-file modification
or `DROP TABLE`; that trust boundary must be explicit.

### 6.2 Event transition guard

A `BEFORE INSERT` trigger must reject invalid event/from/to combinations and state
mismatches. The exact predicate should cover:

- `REQUESTED`: `from_state='not_requested'`, `to_state='pending'`, no state row, and
  no prior event for the attestation.
- `ACCEPTED`: `from_state='pending'`, `to_state='accepted'`, current state is pending,
  and `created_at < expires_at`.
- `REJECTED`: `from_state='pending'`, `to_state='rejected'`, current state pending.
- `EXPIRED`: `from_state IN ('pending','accepted')`, `to_state='expired'`,
  `created_at >= expires_at`.
- `CONSUMED`: `from_state='accepted'`, `to_state='consumed'`, current state accepted,
  `created_at < expires_at`, operation key and review present.
- `REVOKED`: `from_state='accepted'`, `to_state='revoked'`, current state accepted,
  and no prior consumed/expired/revoked event.
- Reject `binding_key` mismatch with the header.
- For A2 (`bound_review_id IS NOT NULL`), reject `CONSUMED` when
  `review_id <> bound_review_id`.
- Reject any event after rejected/expired/consumed/revoked.

SQLite does not support an `IF` statement inside a trigger; the implementation should
use `WHEN NOT (CASE ... END)` plus `SELECT RAISE(ABORT, ...)`, following the existing
`RAISE(ABORT)` style. This is a design requirement, not executed SQL here.

### 6.3 State projection trigger

After a valid event insert, an `AFTER INSERT` trigger inserts the initial state row for
`REQUESTED` and updates it for later events. A `BEFORE INSERT` trigger on the state
table permits only `status='pending'` and requires the matching immutable `REQUESTED`
event; it rejects a state row created without an event. The state `BEFORE UPDATE`
trigger permits only:

- `pending -> accepted | rejected | expired`;
- `accepted -> consumed | expired | revoked`.

It also rejects any change to `attestation_id` or `binding_key` during the update and
checks that the latest event matches `(from_state, to_state)`, that `binding_key`
matches the immutable header, and that the header exists. If the projection update
fails, the event insert and any reservation writes roll back.

The active partial unique index is evaluated on every projection update; a second
pending/accepted row for the same `binding_key` is rejected by SQLite, including under
concurrent writers after `BEGIN IMMEDIATE` serialization.

### 6.4 Required indexes

- `ux_canary_attestation_active_binding` — F1 active uniqueness.
- `ux_canary_attestation_operation` — operation idempotency.
- `ux_canary_attestation_consumed_review` — no review reused by another attestation.
- `idx_canary_attestation_expires_at` — bounded expiry lookup (operational).
- `idx_canary_event_attestation` — event history/state query.

## 7. Transition enforcement model

### 7.1 SQLite-enforced

- `UNIQUE(attestation_id, event_type)`.
- `UNIQUE(attestation_id, operation_key)` partial.
- `UNIQUE(review_id) WHERE event_type='CONSUMED'`.
- Partial unique active binding index.
- Foreign keys with `ON DELETE RESTRICT`.
- No-update/no-delete triggers for header/events/state; no-delete state.
- Event transition guard and state projection triggers (as designed).

### 7.2 Application-enforced

- Canonical JSON and PR ordering.
- Current owner/private-chat/deletion/watched revalidation (WP-01 rules).
- Current D-01 B, D-05, D-06 and exact PR-set revalidation.
- Agreement between `authorization_mode` and the caller's flow.
- A2 cycle membership/owner/chat validation.
- External GitHub checks before the DB transaction.
- Safe reason-code selection and redaction.
- `IntegrityError` mapping to idempotent/conflict results.

### 7.3 Rejections required by lifecycle

- Acceptance without a pending request.
- Consumption without acceptance.
- Revocation after consumption.
- Any transition out of rejected/expired/consumed/revoked.
- Duplicate or conflicting transitions.

The event guard and state trigger reject these at the database boundary; application
must also validate before attempting writes so failures are safe, deterministic, and
auditable.

## 8. Active-binding uniqueness model

### 8.1 Canonical `binding_key`

`binding_key = SHA-256(canonical_json({...}))` where the object includes:

- `schema_version` (`2`);
- `authorization_mode`;
- `bound_review_id` (null for A1; exact cycle ID for A2);
- `owner_user_id`;
- `conversation_id`;
- `chat_id` (equal to owner);
- `creation_job_id`;
- `repository_link_source`;
- `repository_full_name` casefolded;
- canonical PR array (sorted ascending unique positive integers);
- `attestation_version`;
- `statement_version`.

It excludes `generation`, requested/expiry timestamps, `pr_selection_digest`, event
fingerprints, and all numeric repository IDs.

Canonical serialization: UTF-8 JSON, lexicographically sorted keys, no insignificant
whitespace, arrays ordered, integers unquoted. `binding_key` is not permanent
repository identity and must not be used as an authorization token.

### 8.2 Generation and concurrency

Under `BEGIN IMMEDIATE`:

1. Compute `binding_key` from authoritative current values.
2. Query `canary_owner_attestation_state` for a pending/accepted row with that key.
3. If an active row exists, return it idempotently; do not create a new generation.
4. If no active row, query `MAX(generation)` for the binding and allocate
   `MAX+1`; insert the header and `REQUESTED`; the trigger inserts state pending.
5. Commit; unique constraints catch a competing writer. A second writer waits on
   `BEGIN IMMEDIATE`, then sees the active row and returns it/conflicts.

After a terminal state, the partial unique index releases. A later request may create
`generation+1`; the old terminal row remains immutable and auditable.

## 9. Consumption and idempotency model

### 9.1 Constraints

- A `CONSUMED` event requires exactly one `review_id` and a non-null `operation_key`.
- `UNIQUE(attestation_id, event_type)` allows at most one consumed event.
- `UNIQUE(attestation_id, operation_key)` prevents different operation keys from
  replaying the same attestation.
- `UNIQUE(review_id) WHERE event_type='CONSUMED'` prevents one review from being
  consumed by multiple attestations.
- For A2, `review_id` must equal `bound_review_id` (trigger).
- For A1, `review_id` is the cycle created in the same transaction.

### 9.2 Idempotency

- Same attestation + same operation key + same review: `IntegrityError` is caught;
  return the existing consumed event as `ALREADY_CONSUMED`.
- Same attestation + different operation key: reject as conflict, not a second
  consumption.
- Different attestation + same review: unique review index rejects.
- Duplicate Telegram confirmation: same accepted event/attestation/owner/binding
  returns existing accepted; a conflicting owner or binding fails closed.

## 10. A1/A2 compatibility analysis

One schema supports both, with `authorization_mode` and nullable `bound_review_id`.

### A1 — pre-cycle attestation

- `authorization_mode='PRE_CYCLE'`, `bound_review_id IS NULL`.
- A dedicated helper reuses WP-01 owner/private-chat/deletion/watched checks without
  weakening them; it may not call the cycle-bound helper as-is.
- Consumption later binds the review created in the reservation transaction.
- This is the pre-cycle usability option; it adds a new authorization path that must
  prove parity with WP-01.

### A2 — existing authorized cycle

- `authorization_mode='EXISTING_CYCLE'`, `bound_review_id` non-null.
- Attestation requests/confirmation require an existing cycle authorized by
  `revalidate_review_authorization()`.
- The immutable header binds the exact cycle; the event trigger requires
  `CONSUMED.review_id = bound_review_id`; unique review consumption prevents cross-cycle
  reuse.
- The application must verify cycle owner/chat, deletion/watched state, and exact PR
  membership; the FK alone is not authorization.
- This option changes usability (attestation only after a cycle exists).

No R6 `auto_review_owner_acceptance` reuse is permitted. The schema accommodates both;
the owner still must select `OD-R7-D04-AUTH-03`. This design does not choose it.

## 11. Creation-job revalidation model

`creation_jobs` is mutable, so the FK only proves that a row existed. Snapshot into the
attestation:

- `creation_job_id`;
- `repository_full_name`;
- `repository_link_source`;
- canonical exact PR set and digest;
- owner/conversation/chat;
- `authorization_mode`/`bound_review_id` where applicable.

Revalidate at:

| Stage | Required checks |
|---|---|
| Request | Current owner/private chat; conversation not deleted/watched; exact done creation job; selected repository equality; D-05/D-06; exact PR set; no external numeric ID persistence. |
| Confirmation | Same current checks; attestation pending/not expired; exact binding; current owner/chat. |
| Consumption | Same current checks; attestation accepted/not expired; exact binding; A2 bound cycle; current D-05/D-06/D-01 B; reservation transaction. |

The stored snapshot is evidence of what was attested; it is not proof that the job is
still valid. WP-01 semantics remain unchanged; no new owner source is introduced.

## 12. Transaction and rollback sequence

### 12.1 Request/confirmation

1. External/current checks (no DB transaction).
2. `BEGIN IMMEDIATE`.
3. Recompute canonical binding; query state; validate owner/chat/deletion/watched.
4. Insert header (if new generation) and event; event trigger validates.
5. State projection trigger inserts/updates state; active unique index enforced.
6. Commit; any failure rolls back header/event/state.

### 12.2 Consumption with reservation (I1)

1. External D-01 B/D-05/D-06 and exact PR resolution (outside DB transaction).
2. `BEGIN IMMEDIATE`.
3. Re-read state `accepted`, expiry, exact binding, owner/chat/deletion/watched; A2
   bound cycle check.
4. Insert `auto_reviews` and immutable `auto_review_memberships` (existing
   `reserve_conversation_review` pattern).
5. Insert `CONSUMED` event with `review_id` and `operation_key`; event trigger checks
   accepted state, expiry, binding, A2 review match, and consumption constraints.
6. Projection updates to consumed; unique review/operation checks.
7. Commit all; any failure rolls back review, memberships, event, and projection.

If I2 is selected instead, consumption is not coupled to reservation. The consequence
is either a consumed attestation without a review or a review without consumption,
creating a crash window and replay/authorization ambiguity; D-04 remains blocked. No
choice is made here.

### 12.3 Residual TOCTOU

External GitHub identity/linkage can change between the pre-transaction checks and the
local commit. The transaction rechecks current DB/owner/linkage state only; it cannot
prove remote identity. B1 does not provide permanent identity, so this residual
limitation must remain explicit. No external API call is made inside a DB transaction.

## 13. B1 and D-04b boundaries

- No numeric GitHub repository ID column.
- No creation-time numeric identity.
- No D-04b backfill or migration.
- `binding_key`/`pr_selection_digest` are integrity/binding keys, not permanent
  repository identity.
- Same-name deletion/recreation remains indistinguishable.
- D-05 rename/transfer/redirect rejection remains application-enforced.
- D-06 private/allowlist/fork/archive/deletion/ownership checks remain
  application-enforced.
- B1 does not complete WP-04; `WP04_D06_BLOCKED` remains.
- D-04b remains `DEFERRED — NOT APPROVED`.

## 14. Remaining unresolved owner decisions

| Decision | Status | Design impact |
|---|---|---|
| `OD-R7-D04-SCHEMA-01` | `PENDING` | v2 requires owner review/approval; no implementation. |
| `OD-R7-D04-AUTH-03` | `PENDING` | v2 has nullable `authorization_mode`/`bound_review_id`; owner selects A1 or A2. |
| `OD-R7-D04-LIFECYCLE-04` | `PENDING` | v2 preserves lifecycle; TTL duration unselected; `revoked` needs explicit approval. |
| `OD-R7-D04-INTEGRATION-05` | `PENDING` | v2 supports I1; I2 would leave consumption/reservation split and remain blocked. |

Additional constraints:

- No implementation authorization exists.
- Even after schema approval, a separate explicit implementation authorization is
  mandatory.
- WP-05 must not start; WP-06/live Canary remain blocked.

## 15. Recommendation for `OD-R7-D04-SCHEMA-01`

**RECOMMENDATION — NOT AN OWNER DECISION.**

Recommend owner review of v2 as the technically complete schema design:

- approve the three-table design (header, append-only events, state projection) if the
  active-binding uniqueness and transition triggers are accepted;
- preserve A1/A2 and I1/I2 as pending choices;
- preserve the lifecycle proposal and leave TTL unselected;
- require separate implementation authorization after approval.

Trade-offs and limitations:

- The state projection adds a third table and trigger complexity, but provides the
  SQLite-enforced active-binding guarantee missing from v1.
- The event transition trigger is more complex than the project’s existing no-update/
  no-delete triggers; it must be tested during implementation.
- `binding_key` is a semantic binding hash, not permanent GitHub identity.
- A2 adds a cycle reference and cross-cycle checks; A1 does not.
- I1 is required for atomic consumption; I2 leaves a dangerous split.
- No runtime verification is claimed; DDL is unexecuted.

`OD-R7-D04-SCHEMA-01` remains **PENDING**. This report does not approve v2.

## 16. Verification and status distinctions

- DDL/SQL reviewed logically; **not executed**.
- No D-04 tables, indexes, triggers, migrations, code, config, or tests created.
- Documentation parity: `pytest -q tests/test_doc_code_parity.py` → **16 passed**.
- `git diff --check` → clean.
- Only this report and the additive `.agent/PROGRESS.md` entry were introduced.
- Existing tests were not used as proof of unimplemented D-04 behavior.

| Status | Value |
|---|---|
| Design revision | complete for owner review |
| Technical validation | logical review only; no runtime verification |
| Owner schema approval | `PENDING` |
| Implementation authorization | absent |
| Independent review | deferred/not present |
| D-04b | `DEFERRED` and untouched |
| WP-02 | `WP02_D04_BLOCKED` |
| WP-04 | `WP04_D06_BLOCKED` |
| WP-05 / WP-06 | not started / live Canary blocked |
| Working tree vs committed | local working-tree only |
| Published | unpublished |
| Report verdict | `WP02_D04_SCHEMA_V2_READY_FOR_OWNER_REVIEW` |
