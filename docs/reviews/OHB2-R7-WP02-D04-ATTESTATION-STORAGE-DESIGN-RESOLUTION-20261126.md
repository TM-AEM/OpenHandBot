# OHB2-R7 WP-02 / D-04 Attestation Storage — Design Resolution

**Task ID:** `OHB2-R7-WP02-D04-ATTESTATION-STORAGE-BLOCKER-RESOLUTION`
**Date:** 2026-11-26
**Verdict:** `WP02_D04_OWNER_DECISION_REQUIRED`
**Review label:** `AUTHOR_SELF_REVIEW — NOT INDEPENDENT REVIEW`

**Scope:** investigation and design only. No application code, schema, migration,
configuration, runtime, worker, or test change was made by this task. No implementation
of D-04, D-04b, WP-05, WP-06, the D-07 supervisor, or a live Canary was started.

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
| Untracked entries | 74 pre-existing |

### 1.1 Final state after this design task

| Item | Value |
|---|---|
| Branch / HEAD / tree | unchanged |
| Modified tracked | 12 (same pre-existing set; no new tracked code/test/schema file) |
| Untracked entries | 75 (74 pre-existing + this report) |
| New task artifacts | this report and the additive `.agent/PROGRESS.md` section |
| Code / schema / migration / runtime / test changes by this task | none |

The untracked D-06 implementation/test files and the pre-existing modified files
belong to earlier tasks and were not changed by this investigation.

The working tree already contained the D-03, D-05, and D-06 working-tree
implementation, review tests, and historical reports. Those changes were preserved
unchanged. This task intentionally created only this report and an additive
`.agent/PROGRESS.md` entry.

## 2. Files and schema inspected

Read-only inspection covered:

- `docs/reviews/OHB2-R7-WP02-D04-TEMPORARY-OWNER-ATTESTATION-IMPLEMENTATION-REPORT-20261126.md`
  — prior `WP02_D04_BLOCKED` report and its proposed contract.
- `docs/reviews/OHB2-R7-OWNER-DECISIONS-PACK-20261125.md`
  — binding D-04/D-04b/D-05/D-06/D-07/D-08 decision records.
- `docs/reviews/OHB2-R7-WP01-D03-AUTHORIZATION-REVALIDATION-IMPLEMENTATION-REPORT-20261126.md`
  — current-owner revalidation behavior.
- `docs/reviews/OHB2-R7-WP03-D05-REJECT-RENAME-TRANSFER-IMPLEMENTATION-REPORT-20261126.md`
  — redirect/rename/transfer identity handling.
- `docs/reviews/OHB2-R7-WP04-D06-PRIVATE-ALLOWLISTED-ONLY-IMPLEMENTATION-REPORT-20261126.md`
  — D-06 eligibility and unresolved same-name recreation blocker.
- `bot/db.py` — actual SQLite DDL, triggers, indexes, and DB methods.
- `bot/review/authorization.py` — WP-01 cycle-bound authorization.
- `bot/review/resolver.py` — `ConversationRepositoryLink`, `MembershipProvenance`,
  resolver and reservation boundary.
- `bot/review/canary_linkage.py` — D-01 B source and D-02 explicit PR list.
- `bot/review/worker.py`, `bot/review/report.py`, `bot/outbox.py`, `bot/app.py`
  — existing owner revalidation call sites and execution/delivery boundaries.
- `bot/review/github.py` — `RepositoryIdentity`, redirect/identity errors, and
  allowlist enforcement.
- `bot/review/eligibility.py` — D-06 private/fork/archive policy.
- Relevant tests: review authorization, canary linkage, resolver, callback,
  collector, lifecycle, report, delivery, recovery, and creation-job tests.

### 2.1 Actual schema facts verified

| Object | Verified facts |
|---|---|
| `settings` | `key TEXT PRIMARY KEY, value TEXT NOT NULL`; no append-only/update/delete triggers (`bot/db.py:1238-1241`). `_set_setting_nocommit` uses an `ON CONFLICT DO UPDATE` upsert and `set_setting` commits (`bot/db.py:6328-6343`). |
| `creation_jobs` | `id`, `chat_id`, `repo`, `text`, `status`, `task_id`, `conversation_id`, `error`, timestamps, `attempts`, `client_ref`, `notify_state` (`bot/db.py:1200-1214`). No numeric repository ID column. Rows are mutable through creation lifecycle methods (`add_creation_job`, `set_creation_done`, `finish_creation_done`, `discard_creation_job`, etc.). |
| `auto_review_provider_snapshots` | Immutable provider configuration snapshot; `BEFORE UPDATE` and `BEFORE DELETE` triggers reject mutation (`bot/db.py:1398-1419`). No owner, conversation, creation-job, PR, expiry, or lifecycle fields. |
| `auto_reviews` | Mutable review-cycle row with status/lifecycle/stage, repository ID/name, PR number, chat ID, reservation key, and provider snapshot (`bot/db.py:1426-1506`). It is created only by reservation, not by a pre-cycle owner attestation. |
| `auto_review_memberships` | Immutable PR snapshot rows with `review_id`, repository ID/name, PR number, branch, base/head SHA (`bot/db.py:1510-1530`); immutable triggers at `bot/db.py:2022-2029`. It is a child of an existing `auto_reviews` row. |
| `auto_review_pending_memberships` | Mutable pending observations associated with a conversation, not an owner attestation (`bot/db.py:1533-1550`). |
| `auto_review_stages` | Mutable per-cycle stage results; no owner decision semantics (`bot/db.py:1552-1576`). |
| `auto_review_evidence` | Immutable per-PR evidence; immutable triggers (`bot/db.py:1578-1600`, `bot/db.py:2032-2039`). Bound to an existing review and PR. |
| `auto_review_leases` | Mutable worker lease/fencing rows; no attestation semantics (`bot/db.py:1602-1618`). |
| `auto_review_reports` | Immutable generated report; immutable triggers (`bot/db.py:1620-1642`, `bot/db.py:2042-2049`). Bound to a review and report version. |
| `auto_review_owner_acceptance` | Immutable R6 audit row, but schema-bound to `review_id`/`report_version`, `event_type='OWNER_ACCEPTANCE'`, and `ACCEPT|REJECT` (`bot/db.py:1645-1662`); immutable triggers at `bot/db.py:2052-2059`. It is **not** a D-04 attestation store. |
| `outbox`, `notification_inbox`, `watched`, `deleted_conversations`, `user_state`, `web_sessions`, `processed_updates`, `update_failures` | Operational, mutable, or differently-domain-bound rows; none is an immutable owner-attestation lifecycle store. |

### 2.2 Current D-01 B / D-02 / D-04 integration facts

- `CreationJobRepositoryLinkSource.resolve()` selects exactly one `done`
  `creation_jobs` row, checks owner chat, checks OpenHands `selected_repository`
  equality, and verifies the current GitHub numeric ID/full name
  (`bot/review/canary_linkage.py:51-73`).
- `ConversationRepositoryLink` carries only `conversation_id`, `repository_id`,
  `repository_full_name`, and `source`; it does not expose `creation_job_id`
  (`bot/review/resolver.py:88-99`).
- `MembershipProvenance` carries conversation, source, repository ID/name, PR number,
  refs/SHAs, and `verified_at`; it does not carry `creation_job_id`
  (`bot/review/resolver.py:102-112`).
- `ConversationMembershipResolver.resolve()` verifies repository identity, PR
  association, exact SHAs, D-05/D-06 state, and final re-reads before returning
  (`bot/review/resolver.py:152-210`).
- `reserve_conversation_review()` creates the review and immutable membership
  snapshot in one `BEGIN IMMEDIATE` transaction (`bot/db.py:8126-8350`).
- `revalidate_review_authorization()` requires a non-`None` review cycle and current
  owner/chat/deletion/watched state (`bot/review/authorization.py:40-130`). Worker,
  report, and outbox call it at protected boundaries (`bot/review/worker.py:142-151`,
  `bot/review/report.py:612-624`, `bot/outbox.py:687-703`).
- There is no D-04 attestation table, column, request/confirmation/consumption method,
  or callback path in the current code.

## 3. Candidate A — existing persistence

### 3.1 `settings`

**Purpose:** generic durable key/value flags, clearances, routing, and notification
state (`bot/db.py:1238-1241`).

**Mutability:** fully mutable. `_set_setting_nocommit` upserts and `set_setting`
commits; `_delete_setting_nocommit` deletes. No `BEFORE UPDATE`/`BEFORE DELETE`
trigger exists.

**Binding:** only a string key and value. No enforced owner, conversation,
creation-job, repository, PR-set, expiry, or lifecycle columns.

**Verdict:** unsuitable. It could encode JSON by convention, but that is
application-only immutability with no database-enforced append-only audit,
no unique accepted/consumed events, and no atomic lifecycle. It would violate the
task’s prohibition on treating mutable settings as durable immutable attestation
storage.

### 3.2 `auto_review_owner_acceptance`

**Purpose:** R6 owner decision on a generated report, not repository-linkage consent.

**Mutability:** append-only and immutable at the DB boundary (triggers at
`bot/db.py:2052-2059`), with an idempotency key and a unique
`(review_id, report_version, owner_user_id)` constraint.

**Binding:** `review_id`, `report_version`, `owner_user_id`, `action`, and
`event_type='OWNER_ACCEPTANCE'`. It has no conversation ID, creation-job ID,
repository full name, exact PR set, expiry, or consumption field.

**Verdict:** explicitly prohibited by the task and semantically wrong. Reusing it
would conflate D-04 repository-linkage consent with R6 report acceptance and would
make D-04 impossible before a report/cycle exists.

### 3.3 `auto_review_provider_snapshots`

**Purpose:** immutable provider configuration snapshot.

**Mutability:** immutable, but only for provider config fields.

**Binding:** provider/API base/model/config JSON. It cannot represent owner,
conversation, creation job, PR selection, expiry, or consumption.

**Verdict:** unsuitable. Immutability alone is not enough; this is a provider-domain
record and using it as an attestation envelope would be domain conflation.

### 3.4 `auto_review_memberships` / `auto_review_evidence` / `auto_review_reports`

**Purpose:** immutable R5/R6 child records of an existing review cycle.

**Mutability:** immutable at DB boundary.

**Binding:** all require an existing `auto_reviews.review_id`; they capture review
evidence/report facts. `auto_review_memberships` contains an exact PR set and
repository ID/name, but only after reservation and only as part of an existing
cycle. They have no owner attestation, lifecycle, expiry, request, or consumption
state.

**Verdict:** unsuitable. Using them would require creating a review cycle before
owner attestation, silently changing the D-04 flow and conflating attestation with
R5/R6 review evidence.

### 3.5 `auto_reviews`

**Purpose:** mutable review-cycle state and reservation registry.

**Mutability:** mutable status/stage/lifecycle/delivery fields; unique active-cycle
indexes.

**Binding:** repository ID/name, optional anchor PR, chat ID, reservation key, and
provider snapshot. It is not an owner attestation and does not contain exact
creation-job/linkage context or explicit PR-set attestation.

**Verdict:** unsuitable. Reusing it would make a review cycle the attestation record,
which is circular (attestation is needed before the cycle), changes R5/R6 semantics,
and cannot represent pending/expired/revoked state without schema and behavior
changes.

### 3.6 `creation_jobs`

**Purpose:** D-01 B creation-job linkage source.

**Mutability:** mutable status/task/conversation/timestamps and lifecycle methods;
no attestation state.

**Binding:** has `id`, `chat_id`, `repo`, and `conversation_id`, but no numeric ID,
exact PR set, owner attestation, expiry, or consumption fields. `list_done_creation_jobs_for_conversation`
currently requires exactly one `done` row by application check, not a DB unique
constraint.

**Verdict:** useful as a **referenced linkage context**, but not as attestation
storage. Adding attestation columns would be a schema change and would mix mutable
creation lifecycle with immutable consent.

### 3.7 Operational tables (`outbox`, `notification_inbox`, `watched`, etc.)

`outbox` and notification rows are mutable delivery/retry state. `watched` is mutable
ownership/state. `deleted_conversations` is a deletion tombstone. `processed_updates`
is a deduplication ledger without attestation payload/lifecycle. None can satisfy the
required immutable, expiring, one-time-consumption attestation contract.

### 3.8 Candidate A conclusion

No existing table can safely represent D-04 without violating its original domain
semantics. The only existing immutable tables are provider snapshots, review
memberships/evidence/reports, and R6 owner acceptance; all are domain-bound and lack
the required owner/conversation/creation-job/PR/expiry/consumption model or occur too
late in the lifecycle.

## 4. Candidate C — non-database / existing durable mechanism

| Candidate | Why rejected |
|---|---|
| Process memory | Lost on restart; cannot provide durable attestation or replay prevention. |
| Telegram callback/message metadata | Client-controlled, mutable, deletable, not atomic with DB reservation; not an audit store. |
| OpenHands conversation metadata | External, mutable, not a trusted attestation ledger; no atomic D-04 lifecycle. |
| Files on disk | No existing approved atomic durable store with lifecycle constraints; file replacement/loss is not append-only audit. |
| `settings` flags | Mutable upsert, no immutable accepted record, as above. |
| Environment/config values | Mutable deployment state, not evidence; cannot bind per-conversation/PR selection. |
| Reusing `processed_updates` / `update_failures` | Deduplication/failure classifications only; no owner consent, binding payload, expiry, or consumption. |
| Reusing R6 owner acceptance | Explicitly prohibited; wrong domain and no pre-cycle support. |

No already-approved non-database mechanism meets atomicity, durability, lifecycle
enforcement, binding, and append-only audit requirements.

## 5. Candidate comparison

| Criterion | A. Existing table | B. Dedicated attestation schema | C. Non-DB mechanism |
|---|---|---|---|
| D-04 owner/conversation binding | No single safe table | Yes | No durable trusted store |
| Exact creation-job context | `creation_jobs` has ID but no attestation lifecycle | Yes, by FK/context | No |
| Exact explicit PR set | Only R5 child after cycle | Yes, canonical immutable payload | No |
| Immutable accepted record | Only R6/implicit tables with wrong domain | Yes, immutable header + append-only events | No |
| Expiry / rejection / consumption | Absent or wrong domain | Yes | No |
| Replay prevention | `settings` no; R6 has idempotency but wrong domain | Unique event/operation constraints | No |
| Transactional confirmation | No dedicated transaction | Yes, `BEGIN IMMEDIATE` | No |
| Transactional consumption with reservation | No | Yes, extend reservation transaction | No |
| Preserve R5/R6 invariants | Reuse would conflate domains | Yes, separate tables | N/A |
| D-04b numeric-ID compatibility | No new numeric ID needed if B1 | B1 no numeric ID; B2 needs owner approval | No |
| Migration surface | None, but unacceptable semantics | Additive tables/triggers | None, but unacceptable guarantees |
| Verdict | Reject | **Recommended, with owner approval** | Reject |

## 6. Recommended storage design (design only, not authorized for implementation)

### 6.1 Recommendation

Use a new additive, dedicated immutable header plus append-only event ledger:

- `canary_owner_attestations` — immutable binding header.
- `canary_owner_attestation_events` — append-only lifecycle and audit events.

Do **not** reuse `auto_review_owner_acceptance`, `settings`, `auto_reviews`, or any
R5/R6 child table. Do **not** add a numeric repository ID column under this task.

This design requires a new schema, which is **not authorized** by the current D-04
record. It is therefore a design proposal pending explicit owner approval, not an
implementation.

### 6.2 Recommended logical shape

The following is a design sketch, not executable authorization:

```sql
CREATE TABLE canary_owner_attestations (
    attestation_id        TEXT PRIMARY KEY,
    schema_version        INTEGER NOT NULL CHECK (schema_version = 1),
    generation            INTEGER NOT NULL CHECK (generation > 0),
    owner_user_id         INTEGER NOT NULL CHECK (owner_user_id > 0),
    conversation_id       TEXT NOT NULL,
    chat_id               INTEGER NOT NULL CHECK (chat_id > 0),
    creation_job_id       INTEGER NOT NULL
                          REFERENCES creation_jobs(id) ON DELETE RESTRICT,
    repository_full_name  TEXT NOT NULL,
    repository_link_source TEXT NOT NULL CHECK (repository_link_source = 'canary_creation_job'),
    pr_numbers_json       TEXT NOT NULL,
    pr_selection_digest   TEXT NOT NULL CHECK (length(pr_selection_digest) = 64),
    attestation_version   TEXT NOT NULL,
    statement_version     TEXT NOT NULL,
    binding_fingerprint   TEXT NOT NULL UNIQUE CHECK (length(binding_fingerprint) = 64),
    requested_at          TEXT NOT NULL,
    expires_at            TEXT NOT NULL,
    CHECK (chat_id = owner_user_id),
    CHECK (expires_at > requested_at),
    CHECK (length(conversation_id) BETWEEN 1 AND 128),
    CHECK (length(repository_full_name) BETWEEN 1 AND 255)
);

CREATE TABLE canary_owner_attestation_events (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    attestation_id   TEXT NOT NULL
                     REFERENCES canary_owner_attestations(attestation_id)
                     ON DELETE RESTRICT,
    event_type       TEXT NOT NULL
                     CHECK (event_type IN
                       ('REQUESTED','ACCEPTED','REJECTED','EXPIRED','CONSUMED','REVOKED')),
    owner_user_id    INTEGER NOT NULL CHECK (owner_user_id > 0),
    operation_key    TEXT,
    review_id        INTEGER REFERENCES auto_reviews(id) ON DELETE RESTRICT,
    created_at       TEXT NOT NULL,
    event_fingerprint TEXT NOT NULL CHECK (length(event_fingerprint) = 64),
    UNIQUE (attestation_id, event_type),
    CHECK (event_type <> 'CONSUMED' OR review_id IS NOT NULL)
);

CREATE UNIQUE INDEX ux_canary_attestation_operation
    ON canary_owner_attestation_events(attestation_id, operation_key)
    WHERE operation_key IS NOT NULL;

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

The design intentionally omits a raw numeric repository ID. `binding_fingerprint` is
an integrity commitment to the attested payload, **not** proof of permanent repository
identity. It must never be described as a substitute for a GitHub numeric ID.

### 6.3 Required in-memory linkage context

Before implementation, `ConversationRepositoryLink` and `MembershipProvenance` must
expose the exact `creation_job_id` (and the existing `source`) from the D-01 B source.
This is an in-memory model change, not a database schema change. Without it, a durable
attestation cannot bind to the exact creation job required by D-04.

### 6.4 Canonicalization and fingerprints

- Canonical JSON: sorted keys, compact separators, UTF-8, explicit version/domain.
- `pr_numbers_json` is a sorted, unique list of positive integers; duplicates are
  rejected and order is canonical.
- `pr_selection_digest` = SHA-256 over the canonical repository full name plus the
  canonical PR list (and the fixed domain/version).
- `binding_fingerprint` = SHA-256 over schema/version, owner, conversation, chat,
  creation-job ID, repository full name, link source, PR list, statement version, and
  generation. It does not include a numeric repository ID in this design.
- `generation` is allocated under the same `BEGIN IMMEDIATE` transaction used for
  request. The transaction first looks for a non-terminal attestation with the same
  semantic binding (owner, conversation, chat, creation job, repository full name,
  source, PR list, version). A pending/accepted match is returned idempotently; if the
  prior attestation is terminal, the next generation is `MAX(generation) + 1`.
  `binding_fingerprint` remains unique because it includes the generation. This
  prevents duplicate requests from creating parallel pending records while allowing a
  new attestation after expiry/rejection/revocation.
- `event_fingerprint` = SHA-256 over event type, attestation ID, owner, operation key,
  review ID, and timestamp.
- Fingerprints are recomputed server-side from authoritative persisted values.
  Client-supplied fingerprints, repository IDs, PR lists, or owner IDs are never
  trusted.
- A fingerprint is an integrity check only; it is not owner authentication and not
  permanent repository identity.

## 7. Lifecycle state machine

Recommended states:

```text
not_requested -> pending
pending -> accepted | rejected | expired
accepted -> consumed | expired | revoked
rejected -> terminal
expired -> terminal
consumed -> terminal
revoked -> terminal
```

`not_requested` is represented by absence of an attestation row. The derived current
state is the latest lifecycle event; the header has no mutable `status` column.

### 7.1 Transition rules

| Transition | Authorized actor | Preconditions | Atomic persistence | Idempotency / replay | Failure behavior |
|---|---|---|---|---|---|
| `not_requested -> pending` | Current configured owner (`Config.owner_id`) for the exact conversation/chat | Owner config valid; watched row exists; `watched.chat_id == owner`; conversation not deleted; D-01 B link and creation job exact; D-02 PR list non-empty, sorted, unique; D-05/D-06 current checks pass; no conflicting active attestation | `BEGIN IMMEDIATE`; insert immutable header + `REQUESTED` event; commit | Same owner/binding/generation returns existing pending; mismatched binding or owner is conflict | No row/event on any failure; DB error fails closed |
| `pending -> accepted` | Current owner | Pending attestation exists, not expired; current owner/chat/watched/deletion revalidated; current D-01 B/D-02/D-05/D-06 revalidated; exact binding fingerprint matches | `BEGIN IMMEDIATE`; append `ACCEPTED` event; unique `(attestation_id,event_type)`; commit | Duplicate same-owner confirmation returns accepted; different owner/binding/action is conflict | No acceptance on expiry, owner change, changed PR set, repo/linkage mismatch, D-05/D-06 rejection, or DB failure |
| `pending -> rejected` | Current owner | Pending; exact attestation; owner current | Append `REJECTED`; commit | Duplicate rejection is idempotent; acceptance after rejection is conflict | No consumption after rejection |
| `pending -> expired` | Any authorized lifecycle reader/worker, or lazy check by owner action | `now >= expires_at` | Append `EXPIRED`; commit; no extension | Repeated expiry returns same terminal state | Expired cannot become accepted; no silent extension |
| `accepted -> consumed` | Current owner through the exact reservation operation | Accepted; not expired/revoked; owner/chat/deletion/watched current; D-01 B/D-02/D-05/D-06 current; exact binding matches; review reservation is otherwise valid; no prior consumption | `BEGIN IMMEDIATE`; verify + insert review/memberships + `CONSUMED` event with `review_id`/operation key; commit all | Duplicate same operation/review returns consumed; different review/operation is conflict; replay cannot create a second cycle | Roll back review, memberships, and consumption together; no partial consumption |
| `accepted -> expired` | Lifecycle reader/worker or lazy check | `now >= expires_at` and no consumption | Append `EXPIRED`; commit | Idempotent terminal | Cannot consume after expiry |
| `accepted -> revoked` | Current owner, or a fail-closed lifecycle invalidation on owner/context/repository/PR change | Accepted; current owner for owner-initiated revoke; invalidation detected by revalidation | Append `REVOKED` with reason/operation key; commit | Repeated revoke is idempotent; consumption after revoke is conflict | Cannot consume after revoke |

### 7.2 Why `revoked` is recommended in addition to the requested model

The requested model has no explicit accepted-cancellation state. Without `revoked`,
an accepted attestation can remain logically accepted after owner/repository/PR context
changes and would only become unusable through revalidation or expiry. A terminal
`revoked` event gives an append-only audit record and prevents an old accepted record
from becoming consumable again if mutable context changes back. This is a design
recommendation requiring owner approval; it does not alter the approved D-04 policy.

### 7.3 Owner change, repository, linkage, and PR-set rules

- Owner change before confirmation: confirmation fails; pending cannot be accepted by
  the new owner; it expires unless explicitly rejected/revoked.
- Owner change after acceptance before consumption: consumption fails; accepted should
  be `REVOKED` by lifecycle invalidation or left to expire; a new attestation is
  required.
- Repository rename/transfer: D-05 rejects; full-name/redirect change invalidates;
  accepted is revoked/expired; no new owner/name authorization is inherited.
- Same-name deletion/recreation: not detectable without D-04b; the attestation is
  name-bound and may be accepted for a recreated repository under the current
  limitation. This must be displayed, not hidden.
- PR membership change: fingerprint mismatch; old attestation cannot be consumed; new
  attestation required.
- Creation-job/linkage mismatch: fingerprint/context mismatch; reject.
- Visibility/fork/archive/deletion change: D-06/D-05 current check fails; reject or
  revoke.

## 8. Transaction and concurrency design

### 8.1 Request and confirmation

- Use the existing single SQLite connection with `PRAGMA foreign_keys=ON`,
  `journal_mode=WAL`, and `busy_timeout=5000` (`bot/db.py:1116-1127`).
- Every state transition uses `BEGIN IMMEDIATE`; checks and writes are in the same
  transaction. No network call is made while the DB write transaction is held.
- `UNIQUE(attestation_id, event_type)` makes accepted/consumed/rejected/expired/revoked
  single events. `ux_canary_attestation_operation` makes consumption idempotent per
  operation key.
- A duplicate Telegram callback is handled by the existing update dedupe/processed
  update path plus the attestation operation key. A duplicate confirmation returns the
  existing accepted event; a conflicting confirmation raises a safe conflict and does
  not change state.
- Concurrent confirmations serialize on `BEGIN IMMEDIATE`. The first insert wins; the
  second reads the accepted event and returns idempotent or conflict.

### 8.2 Reservation and consumption

- `resolve`/GitHub verification happens **before** the DB transaction, as it does
  today; the DB transaction must not perform network I/O.
- Extend the future reservation operation (design only) so that the attestation ID is
  passed into the reservation transaction. Inside the transaction, verify the accepted
  attestation, exact binding, current owner/chat/deletion/watched state, and exact
  membership snapshot; then insert `auto_reviews` + `auto_review_memberships` and the
  `CONSUMED` event in the same transaction.
- If the review insert, membership insert, or event insert fails, roll back all of
  them. There must never be a consumed attestation without a cycle or a cycle created
  from a non-consumed attestation.
- Concurrent consumption: unique consumed event / operation key and `BEGIN IMMEDIATE`
  allow exactly one winner. A second consumer with a different operation gets a
  conflict; the same operation is idempotent.
- There is a residual TOCTOU window between the last external GitHub read and the
  SQLite transaction. This already exists in the current resolver/reservation design
  and must be documented; the DB transaction can only re-check persisted/current DB
  state, not remote GitHub state. Collector revalidation remains required.

### 8.3 Expiry during processing

- The transition transaction reads a server-supplied `now` and checks
  `now < expires_at`; expiry is final. A request already in flight cannot extend it.
- If confirmation/consumption loses the race with expiry, it fails and appends
  `EXPIRED` only if that event is not already present; no accepted/consumed event.

## 9. Authorization and binding requirements

### 9.1 WP-01 / D-03 integration

`revalidate_review_authorization()` is cycle-bound, but D-04 may need attestation
before a cycle exists. The design requires one of:

1. a new read-only pre-cycle authorization helper with the same rules
   (`Config.owner_id`, positive owner/chat, `watched.chat_id == owner`, deletion
   check, DB-read failure is retryable/fail-closed); or
2. a lifecycle change that only permits attestation after a review cycle exists.

Option 1 is recommended because it preserves the current canary flow (resolve → owner
attestation → reserve). It must be implemented later under a separate authorization,
and must not weaken WP-01. At consumption, the reservation transaction must use the
same helper plus exact cycle/ownership checks.

### 9.2 Exact binding

The attestation must bind all of:

- `owner_user_id`: current configured owner at request, confirmation, and consumption.
- `conversation_id`: exact OpenHands conversation.
- `chat_id`: exact owner private chat; must equal owner.
- `creation_job_id`: exact D-01 B `creation_jobs` row.
- `repository_full_name`: exact canonical full name verified at request; not permanent
  identity.
- `repository_link_source`: `canary_creation_job`.
- `pr_numbers_json`: exact sorted unique explicit D-02 list.
- `attestation_version` and `statement_version`: immutable contract/statement.
- `generation`: new generation for a new attestation attempt after terminal state.
- Optional `binding_fingerprint`: integrity only; no numeric repository ID in B1.

### 9.3 What is not sufficient

- Telegram callback data, message text, client-supplied repository/PR values, stale
  `ResolutionResult` objects, cached owner IDs, or OpenHands metadata alone.
- R6 `auto_review_owner_acceptance`; it is report acceptance only.
- A full name alone; it does not prove permanent identity or no recreation.
- A fingerprint alone; it does not prove owner authorization or repository identity.

## 10. Security threat analysis

| Threat | Required control | Achievable with current schema? |
|---|---|---|
| Forged confirmation | Server-generated `attestation_id`; callback bound to owner/chat; exact pending state; no client-supplied binding; current owner revalidation | No dedicated store now; design table provides it |
| Replayed confirmation | `UNIQUE(attestation_id,event_type)`; operation key; duplicate returns existing accepted; owner/current binding checked | No; new table needed |
| Duplicate Telegram callback delivery | Existing update dedupe plus attestation unique accepted event and operation key | Partial now; complete with new table |
| Owner change before confirmation | Re-read `Config.owner_id`, `watched`, deletion in transaction; reject/expire | No D-04 path now; design supports |
| Owner change after acceptance before consumption | Revalidate owner/chat/deletion at consumption; reject; revoke/expire accepted | No D-04 path now; design supports |
| Repository rename or transfer | D-05 redirect/full-name rejection; invalidate; no inherited authorization | Existing identity layer; attestation design must revalidate |
| Same-name deletion/recreation | No reliable control without D-04b; explicit limitation; fail closed for all other checks | **No**; unresolved blocker |
| Visibility private→public | D-06 `private is True` revalidation at request/confirm/consume | Existing D-06 code; design integrates it |
| Repository becomes fork/archived | D-06 `fork is False`, `archived is False` revalidation | Existing D-06 code; design integrates it |
| PR membership changes | Exact canonical PR set + digest; re-resolve; reject | No D-04 store now; design supports |
| Creation-job/linkage mismatch | Exact `creation_job_id` in link/provenance + binding; reject | Needs in-memory context exposure; no schema |
| Concurrent confirmation | `BEGIN IMMEDIATE`; unique accepted event; CAS-like read/write | No D-04 store now; design supports |
| Concurrent consumption | `BEGIN IMMEDIATE`; unique consumed event/operation; consume + reserve one transaction | No D-04 store now; design supports |
| DB lock/write failure | `busy_timeout`, rollback, fail closed; no success without commit | Existing DB behavior; design must use it |
| Partial transaction failure | Header/event/review/membership all-or-nothing | No D-04 store now; design supports |
| Expiry during processing | Transaction reads `now` and checks `expires_at`; no extension | No D-04 store now; design supports |
| Stale worker/callback | Revalidate current owner/context/status/expiry; no cached eligibility; R5 lease fencing remains | Existing WP-01/R5; design must not bypass |
| Process restart | Durable SQLite header/events; no in-memory authority | No D-04 store now; design supports |
| Audit tampering | Immutable header/event triggers; append-only; event fingerprints; DB access remains trusted | No D-04 store now; design supports |
| Accidental R6 reuse | Separate table/purpose; reject `auto_review_owner_acceptance` access; tests to enforce | Explicitly avoided by design |

## 11. D-04b conflict analysis (mandatory)

D-04b is `DEFERRED` and not approved. Existing `auto_reviews`/`auto_review_memberships`
do persist a current numeric repository ID for the review cycle, but they do **not**
persist a creation-time or historical numeric ID and do not solve D-04b’s provenance
question. This design does not add a new numeric-ID column, backfill, index, or
creation-time capture.

1. **D-04 requirements achievable without numeric-ID persistence:**
   - Owner identity and consent.
   - Exact conversation and chat.
   - Exact D-01 B `creation_job_id` and source.
   - Exact repository full name current at request.
   - Exact explicit PR set and PR-selection digest.
   - Lifecycle, expiry, rejection, revocation, consumption, replay prevention.
   - Transactional confirmation/consumption and append-only audit.
   - Current D-05/D-06 revalidation.
2. **D-04 requirements not provable without numeric-ID persistence:**
   - Historical repository continuity across same-name deletion/recreation.
   - A durable comparison of the creation-time repository ID with the current ID.
   - A claim that D-06 rejects recreated repositories before the current resolution.
   - A permanent identity guarantee; a full name and current ID read are not enough.
3. **Can D-04 be implemented safely with an explicit limitation and fail-closed
   policy?** Yes, as a **name-bound canary attestation**: bind owner/conversation/
   creation job/full name/PR set, revalidate D-01 B/D-02/D-05/D-06 at every transition,
   and explicitly state that same-name recreation is not detectable. This is safe only
   if the owner accepts the limitation and does not claim D-06 continuity.
4. **Can it bind to D-01 B without claiming permanent identity?** Yes, by adding
   `creation_job_id` to the in-memory link/provenance and binding it with the full name
   and PR set. It must be labelled “current D-01 B linkage context”, not permanent
   identity.
5. **Is the WP-04 same-name recreation blocker independent of D-04?** It shares the
   same missing evidence: no creation-time numeric ID. It is independent in code path
   (D-06 repository eligibility vs D-04 owner attestation), but not independent in
   root cause. D-04 attestation cannot make D-06’s same-name rejection provable.
6. **Would any proposed solution implicitly implement D-04b?** Yes, any design that
   stores a raw creation-time numeric ID, a durable numeric-ID-derived continuity
   token, or a fingerprint used to compare historical and current numeric IDs would
   implement D-04b or an equivalent identity commitment. This design deliberately
   avoids that and does not present `binding_fingerprint` as identity.

**Conflict:** D-04 can be implemented as a name-bound canary attestation, but D-06’s
approved requirement to reject same-name recreated repositories cannot be met without
D-04b. Both cannot be fully satisfied under current approvals. The design does not
resolve this conflict by silently accepting a weaker D-06 or by inventing an identity
substitute.

## 12. WP-04 same-name recreation dependency

- `test_same_name_recreated_repository_is_not_distinguishable` in
  `tests/test_review_canary_linkage.py` records the current limitation.
- D-05 catches a numeric-ID change observed **within** a resolution/collection
  operation, but not a same-name recreation before the first read.
- D-04 attestation can record the owner’s current statement and bind the exact current
  D-01 B linkage, but it cannot prove that the repository is the one the owner created
  earlier.
- Therefore WP-04 remains `WP04_D06_BLOCKED` even if D-04 is implemented name-bound.
  A D-04 pass would not unlock WP-04’s same-name requirement.

## 13. Migration and compatibility considerations

- Additive only: new `canary_owner_attestations` and
  `canary_owner_attestation_events` tables, indexes, and no-update/no-delete triggers.
- No change to existing tables, columns, indexes, triggers, existing rows, or
  `creation_jobs`.
- No backfill and no historical attestation. Existing canary candidates without an
  attestation remain D-04-ineligible; no false historical consent.
- Old databases receive the tables through the existing idempotent schema setup only
  if the owner authorizes the schema change.
- Code rollback: an older binary can ignore the added tables; no existing table is
  altered, and no data needs deletion. A forward migration must not delete/alter prior
  data.
- The design requires the in-memory `creation_job_id` exposure change; it requires no
  numeric-ID schema.
- If D-04b is later approved, a separate additive numeric-ID design may extend the
  header; it must not be smuggled into this design.

## 14. Unresolved assumptions

1. The owner will approve a **new additive schema**; current D-04 approval explicitly
   did not authorize schema, migration, or persistence.
2. The owner will choose whether D-04 is **name-bound** (accept same-name recreation
   limitation; D-06 remains blocked) or **D-04b numeric-ID** (requires a separate
   identity decision).
3. A cycle-less WP-01-equivalent authorization helper is acceptable, or attestation
   must occur only after a cycle exists.
4. Attestation TTL is not specified by the existing decision; a bounded value such as
   15 minutes is proposed, not approved.
5. `creation_job_id` can be exposed in `ConversationRepositoryLink` and
   `MembershipProvenance` without a schema change; this is a code-design assumption.
6. “Exact repository ID” in the prior D-04 contract cannot be durably recorded under
   the D-04b prohibition; this report treats that as a conflict requiring an owner
   decision, not as permission to ignore the contract.

## 15. Exact owner decisions required before implementation

- **OD-R7-D04-SCHEMA-01:** Approve or reject the additive immutable
  `canary_owner_attestations` + append-only events schema (including no-update/no-delete
  triggers). No schema work is authorized by the current D-04 record.
- **OD-R7-D04-SCOPE-02:** Choose the attestation trust boundary:
  - **B1 — name-bound canary attestation:** no numeric repository ID; current D-01 B
    linkage + full name + PR set; same-name recreation remains undetectable; D-06
    remains blocked for recreated repositories; or
  - **B2 — D-04b:** separately approve persistence of a creation-time numeric
    repository ID (and its migration/backfill policy) so D-04/D-06 continuity can be
    proven.
- **OD-R7-D04-AUTH-03:** Approve a cycle-less authorization helper with the same
  owner/chat/deletion/watched rules as WP-01, or require attestation after a cycle
  exists. The helper must not weaken D-03.
- **OD-R7-D04-LIFECYCLE-04:** Approve expiry duration, one-time consumption, and whether
  `revoked` is an approved additional terminal state.
- **OD-R7-D04-INTEGRATION-05:** Approve the future in-memory `creation_job_id`
  exposure and the reservation transaction to consume the attestation; no WP-05/D-07
  implementation is authorized by this report.

The smallest decision that unblocks a safe design is the schema approval plus the
B1/B2 choice. If the owner refuses both, D-04 remains blocked and no live Canary can
claim D-04 compliance.

## 16. Implementation-readiness verdict

`WP02_D04_OWNER_DECISION_REQUIRED`

The recommended design is technically coherent and can be implemented safely only
after explicit schema authorization and an owner choice between a name-bound
limitation and D-04b numeric identity. D-04 implementation is **not started**, the
schema is **not created**, no migration exists, and no tests for the new design exist.
The existing full test suite is not evidence that D-04 is implemented or verified.

## 17. Status distinctions and confirmations

- **Investigation status:** complete for the existing code/schema and reports.
- **Design status:** proposed, not approved; no schema or code created.
- **Implementation status:** not started; D-04 and WP-02 remain blocked.
- **Schema status:** no table, column, index, trigger, or migration added.
- **Test status:** no new D-04 tests; existing tests were not used as D-04 proof.
- **Author self-review:** this report is `AUTHOR_SELF_REVIEW — NOT INDEPENDENT REVIEW`.
- **Independent review:** deferred/not present; R8 and R9 not started.
- **D-04b status:** `DEFERRED` and untouched; no numeric-ID persistence, backfill,
  column, index, trigger, or migration.
- **WP-02 status:** remains blocked; not complete.
- **WP-04 same-name limitation:** explicitly retained; D-04 cannot make it disappear.
- **Local working tree vs committed:** only this report and an additive PROGRESS entry
  are new local changes; no commit, push, PR, merge, deployment, or release.
- **Published vs unpublished:** unpublished.
- **WP-05 / WP-06 / D-07 / D-08:** not started; no worker, R5, Canary, or external
  operation was activated.
- **External operations:** none; no OpenHands/GitHub/Telegram/API call, provider
  inference, or data transmission.

## 18. Final statement

D-04 cannot be safely implemented against `settings`, `auto_review_owner_acceptance`,
`auto_reviews`, or any R5/R6 child table. A dedicated immutable header plus append-only
event ledger is the smallest viable storage model. It requires new schema authorization,
and the current D-04/D-04b conflict requires an explicit owner decision. The report
stops here; no implementation or WP-05 work was started.
