# OHB2-R7 WP-02 / D-04 — Schema Design Revision v3

**Task ID:** `OHB2-R7-WP02-D04-SCHEMA-V3-DESIGN-REVISION`
**Date:** 2026-11-26
**Verdict:** `WP02_D04_SCHEMA_V3_DESIGN_READY_FOR_OWNER_REVIEW`
**Review label:** `AUTHOR_SELF_REVIEW — NOT INDEPENDENT REVIEW`
**Current WP-02 status:** `WP02_D04_BLOCKED`
**`OD-R7-D04-SCHEMA-01`:** `PENDING — NOT APPROVED`

**Scope:** design-only. The SQL below is a complete proposal, but it was **not executed**
against any database and no implementation, migration, application code, configuration,
test, worker, Canary, or external operation was performed.

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
| Untracked entries | 80 pre-existing |

Source artifacts:

- v2 design: `docs/reviews/OHB2-R7-WP02-D04-SCHEMA-DESIGN-REVISION-V2-20261126.md`
  (`80e596d79cfd1107c617dc8fa1723e833a86a9f5dc72d5a2e7b4ab33f5df4534`)
- v2 isolated validation:
  `docs/reviews/OHB2-R7-WP02-D04-SCHEMA-V2-ISOLATED-SQLITE-VALIDATION-20261126.md`
  (`8cf1a5c52532540f8cba7b74282061cfa8f174f64ef64206e89430b3b5b5a29f`)
- `bot/db.py` (`91b9e0282b767fc04a7d780e6714b2fc81e2424b55f0116b95bad75edf4841ff`)

All pre-existing changes and untracked files, including `.openhands/`, were preserved.
No fetch, pull, reset, clean, or history change was performed.

Existing SQLite conventions relevant to v3: WAL, `busy_timeout=5000`, explicit
`PRAGMA foreign_keys=ON` with fail-closed read-back, `BEGIN IMMEDIATE` for atomic
read/check/write operations, `RAISE(ABORT)` immutability triggers, and immutable
snapshot tests. The v3 SQL follows those conventions.

### 1.1 Final state after this report

| Item | Value |
|---|---|
| Branch / HEAD / tree | unchanged |
| Modified tracked | 12 (same pre-existing set) |
| Untracked | 81 (80 pre-existing + this report) |
| Application code / schema / migration / config / test changes | none |
| DDL executed | none |

## 2. v2 failure-to-v3 correction traceability

| v2 validation finding | v3 correction | Enforcement |
|---|---|---|
| B6 header-only orphan bypasses active uniqueness | `AFTER INSERT` header bootstrap creates the `REQUESTED` event and state row; state insert guard requires the event; state partial unique index is the active-binding gate | SQLite triggers + unique index + transaction |
| C1 acceptance without request | transition guard requires a pending state; state cannot exist without a valid `REQUESTED` event | SQLite trigger |
| C2 consumption without acceptance | transition guard requires an accepted state; state can only be accepted by an accepted event | SQLite trigger |
| C3 revocation after consumption | transition guard requires state `accepted`; terminal state blocks | SQLite trigger |
| C4 `ACCEPTED accepted→accepted` | table CHECK fixes event/from/to mapping; transition guard requires pending→accepted | SQLite CHECK + trigger |
| D1 direct projection update | `BEFORE UPDATE` state guard requires the latest event to match old/new state and an allowed transition | SQLite trigger |
| D6 event binding mismatch | event header guard requires event `binding_key` equal to header | SQLite trigger |
| D7 arbitrary reason code | finite reason-code lookup; event guard requires `(reason_code,event_type,actor_type)` match | SQLite FK + trigger |
| E6 A2 bound review mismatch | A2 trigger requires `CONSUMED.review_id = header.bound_review_id` | SQLite trigger |
| G1 expired pending accepted | time guard requires accepted events before `expires_at` | SQLite trigger |
| G2 expired accepted consumed | time guard requires consumed events before `expires_at` | SQLite trigger |
| G3 acceptance after expiry | time guard + terminal state; acceptance after expiry fails | SQLite trigger |
| I3 concurrent confirmations | accepted event/state transition + unique event; second confirmation sees accepted state | SQLite trigger + `BEGIN IMMEDIATE` |
| I5 expiry/confirmation race | timestamp guard and state transition; expiry first blocks acceptance; acceptance before expiry may be followed by valid expiry | SQLite trigger + transaction |
| H deletion/audit | `ON DELETE RESTRICT` FKs; append-only triggers; no cascade for audit | SQLite FK + triggers |
| E idempotency/replay | unique active state, unique event type, unique consumed review, unique `(attestation_id,operation_key)` | SQLite unique indexes; application retry mapping |

No v2 report is edited; the historical results remain unchanged.

## 3. Complete proposed SQL package

The SQL is complete at the design level. It is **NOT EXECUTED**. Parent tables
`creation_jobs` and `auto_reviews` already exist in the application schema; only the
new tables and triggers are shown.

### 3.1 Installation order

1. `PRAGMA foreign_keys=ON` (verify it reads back as `1`).
2. `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000` for the application
   connection, matching `bot/db.py`.
3. Ensure `creation_jobs` and `auto_reviews` exist.
4. Create `canary_owner_attestation_reason_codes` and seed its finite rows.
5. Create `canary_owner_attestations`.
6. Create `canary_owner_attestation_events`.
7. Create `canary_owner_attestation_state`.
8. Create indexes.
9. Create append-only and transition/projection triggers.
10. Verify with `PRAGMA foreign_key_check` after the implementation transaction.

Do not enable or disable recursive triggers for this design; no trigger recursion is
required.

### 3.2 Reason-code lookup

```sql
CREATE TABLE canary_owner_attestation_reason_codes (
    reason_code TEXT PRIMARY KEY
                CHECK (length(reason_code) BETWEEN 1 AND 64),
    event_type  TEXT NOT NULL
                CHECK (event_type IN ('REJECTED','EXPIRED','REVOKED')),
    actor_type  TEXT NOT NULL
                CHECK (actor_type IN ('OWNER','SYSTEM')),
    UNIQUE (reason_code, event_type, actor_type)
);

INSERT INTO canary_owner_attestation_reason_codes(reason_code,event_type,actor_type)
VALUES
    ('OWNER_REJECTED','REJECTED','OWNER'),
    ('OWNER_REVOKED','REVOKED','OWNER'),
    ('SYSTEM_EXPIRED','EXPIRED','SYSTEM');
```

### 3.3 Header

```sql
CREATE TABLE canary_owner_attestations (
    attestation_id         TEXT PRIMARY KEY
                           CHECK (length(attestation_id) BETWEEN 16 AND 128),
    schema_version         INTEGER NOT NULL CHECK (schema_version = 3),
    generation             INTEGER NOT NULL CHECK (generation > 0),
    binding_key            TEXT NOT NULL
                           CHECK (length(binding_key) = 64
                                  AND binding_key NOT GLOB '*[^0-9a-f]*'),
    owner_user_id          INTEGER NOT NULL CHECK (owner_user_id > 0),
    conversation_id        TEXT NOT NULL
                           CHECK (length(conversation_id) BETWEEN 1 AND 128),
    chat_id                INTEGER NOT NULL CHECK (chat_id > 0),
    creation_job_id        INTEGER NOT NULL
                           REFERENCES creation_jobs(id) ON DELETE RESTRICT,
    repository_full_name   TEXT NOT NULL
                           CHECK (length(repository_full_name) BETWEEN 1 AND 255),
    repository_link_source TEXT NOT NULL
                           CHECK (repository_link_source = 'canary_creation_job'),
    pr_numbers_json        TEXT NOT NULL
                           CHECK (length(pr_numbers_json) BETWEEN 2 AND 4096
                                  AND pr_numbers_json <> '[]'
                                  AND substr(pr_numbers_json,1,1) = '['
                                  AND substr(pr_numbers_json,-1,1) = ']'),
    pr_selection_digest    TEXT NOT NULL
                           CHECK (length(pr_selection_digest) = 64
                                  AND pr_selection_digest NOT GLOB '*[^0-9a-f]*'),
    attestation_version    TEXT NOT NULL
                           CHECK (length(attestation_version) BETWEEN 1 AND 64),
    statement_version      TEXT NOT NULL
                           CHECK (length(statement_version) BETWEEN 1 AND 64),
    authorization_mode     TEXT NOT NULL
                           CHECK (authorization_mode IN ('PRE_CYCLE','EXISTING_CYCLE')),
    bound_review_id        INTEGER
                           REFERENCES auto_reviews(id) ON DELETE RESTRICT,
    requested_at           TEXT NOT NULL
                           CHECK (length(requested_at) BETWEEN 20 AND 64),
    expires_at             TEXT NOT NULL
                           CHECK (length(expires_at) BETWEEN 20 AND 64),
    CHECK (chat_id = owner_user_id),
    CHECK (expires_at > requested_at),
    CHECK (
        (authorization_mode = 'PRE_CYCLE' AND bound_review_id IS NULL) OR
        (authorization_mode = 'EXISTING_CYCLE' AND bound_review_id IS NOT NULL)
    ),
    UNIQUE (binding_key, generation)
);
```

No numeric GitHub repository ID, creation-time numeric identity, backfill, or D-04b
field is present.

### 3.4 Events

```sql
CREATE TABLE canary_owner_attestation_events (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    attestation_id    TEXT NOT NULL
                      REFERENCES canary_owner_attestations(attestation_id)
                      ON DELETE RESTRICT,
    binding_key       TEXT NOT NULL
                      CHECK (length(binding_key) = 64
                             AND binding_key NOT GLOB '*[^0-9a-f]*'),
    event_type        TEXT NOT NULL
                      CHECK (event_type IN
                      ('REQUESTED','ACCEPTED','REJECTED','EXPIRED','CONSUMED','REVOKED')),
    from_state        TEXT NOT NULL
                      CHECK (from_state IN ('not_requested','pending','accepted')),
    to_state          TEXT NOT NULL
                      CHECK (to_state IN
                      ('pending','accepted','rejected','expired','consumed','revoked')),
    actor_type        TEXT NOT NULL
                      CHECK (actor_type IN ('OWNER','SYSTEM')),
    actor_id          INTEGER,
    reason_code       TEXT
                      REFERENCES canary_owner_attestation_reason_codes(reason_code)
                      ON DELETE RESTRICT,
    operation_key     TEXT
                      CHECK (operation_key IS NULL
                             OR length(operation_key) BETWEEN 1 AND 128),
    review_id         INTEGER
                      REFERENCES auto_reviews(id) ON DELETE RESTRICT,
    created_at        TEXT NOT NULL
                      CHECK (length(created_at) BETWEEN 20 AND 64),
    event_fingerprint TEXT NOT NULL
                      CHECK (length(event_fingerprint) = 64
                             AND event_fingerprint NOT GLOB '*[^0-9a-f]*'),

    UNIQUE (attestation_id, event_type),

    CHECK (
        (event_type = 'REQUESTED' AND from_state = 'not_requested' AND to_state = 'pending') OR
        (event_type = 'ACCEPTED'  AND from_state = 'pending'       AND to_state = 'accepted') OR
        (event_type = 'REJECTED'  AND from_state = 'pending'       AND to_state = 'rejected') OR
        (event_type = 'EXPIRED'   AND from_state IN ('pending','accepted')
                                 AND to_state = 'expired') OR
        (event_type = 'CONSUMED'  AND from_state = 'accepted'      AND to_state = 'consumed') OR
        (event_type = 'REVOKED'   AND from_state = 'accepted'      AND to_state = 'revoked')
    ),
    CHECK (
        (actor_type = 'OWNER' AND actor_id IS NOT NULL AND actor_id > 0) OR
        (actor_type = 'SYSTEM' AND actor_id IS NULL)
    ),
    CHECK (
        (event_type IN ('REJECTED','EXPIRED','REVOKED') AND reason_code IS NOT NULL) OR
        (event_type IN ('REQUESTED','ACCEPTED','CONSUMED') AND reason_code IS NULL)
    ),
    CHECK (
        (event_type = 'CONSUMED' AND review_id IS NOT NULL AND operation_key IS NOT NULL) OR
        (event_type <> 'CONSUMED' AND review_id IS NULL AND operation_key IS NULL)
    )
);
```

### 3.5 State projection

```sql
CREATE TABLE canary_owner_attestation_state (
    attestation_id TEXT PRIMARY KEY
                   REFERENCES canary_owner_attestations(attestation_id)
                   ON DELETE RESTRICT,
    binding_key    TEXT NOT NULL
                   CHECK (length(binding_key) = 64
                          AND binding_key NOT GLOB '*[^0-9a-f]*'),
    status         TEXT NOT NULL
                   CHECK (status IN
                   ('pending','accepted','rejected','expired','consumed','revoked')),
    updated_at     TEXT NOT NULL
                   CHECK (length(updated_at) BETWEEN 20 AND 64)
);
```

### 3.6 Indexes

```sql
CREATE UNIQUE INDEX ux_canary_attestation_active_binding
    ON canary_owner_attestation_state(binding_key)
    WHERE status IN ('pending','accepted');

CREATE UNIQUE INDEX ux_canary_attestation_operation
    ON canary_owner_attestation_events(attestation_id, operation_key)
    WHERE operation_key IS NOT NULL;

CREATE UNIQUE INDEX ux_canary_attestation_consumed_review
    ON canary_owner_attestation_events(review_id)
    WHERE event_type = 'CONSUMED';

CREATE INDEX idx_canary_attestation_expires_at
    ON canary_owner_attestations(expires_at);

CREATE INDEX idx_canary_event_attestation
    ON canary_owner_attestation_events(attestation_id, id);
```

### 3.7 Append-only and lookup triggers

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

CREATE TRIGGER trg_canary_reason_no_update
BEFORE UPDATE ON canary_owner_attestation_reason_codes
BEGIN SELECT RAISE(ABORT, 'canary reason codes are immutable'); END;

CREATE TRIGGER trg_canary_reason_no_delete
BEFORE DELETE ON canary_owner_attestation_reason_codes
BEGIN SELECT RAISE(ABORT, 'canary reason codes are immutable'); END;
```

### 3.8 Header bootstrap: initial request, event, and projection

The application inserts the header only, inside `BEGIN IMMEDIATE`. The `AFTER INSERT`
trigger writes the `REQUESTED` event first and the pending state second. If the state
insert fails (for example, active-binding uniqueness), the entire header statement,
including the event, rolls back.

```sql
CREATE TRIGGER trg_canary_attestation_bootstrap
AFTER INSERT ON canary_owner_attestations
BEGIN
    INSERT INTO canary_owner_attestation_events
        (attestation_id, binding_key, event_type, from_state, to_state,
         actor_type, actor_id, reason_code, operation_key, review_id, created_at,
         event_fingerprint)
    VALUES
        (NEW.attestation_id, NEW.binding_key, 'REQUESTED', 'not_requested', 'pending',
         'OWNER', NEW.owner_user_id, NULL, NULL, NULL, NEW.requested_at,
         lower(hex(randomblob(32))));

    INSERT INTO canary_owner_attestation_state
        (attestation_id, binding_key, status, updated_at)
    VALUES
        (NEW.attestation_id, NEW.binding_key, 'pending', NEW.requested_at);
END;
```

The initial state is `pending`; accepted state cannot be inserted directly.

### 3.9 State insert and transition guards

```sql
CREATE TRIGGER trg_canary_state_insert_guard
BEFORE INSERT ON canary_owner_attestation_state
WHEN
    NEW.status <> 'pending'
    OR NOT EXISTS (
        SELECT 1
          FROM canary_owner_attestations h
         WHERE h.attestation_id = NEW.attestation_id
           AND h.binding_key = NEW.binding_key
    )
    OR NOT EXISTS (
        SELECT 1
          FROM canary_owner_attestation_events e
         WHERE e.attestation_id = NEW.attestation_id
           AND e.event_type = 'REQUESTED'
           AND e.to_state = 'pending'
    )
BEGIN
    SELECT RAISE(ABORT, 'canary state requires header and REQUESTED event');
END;

CREATE TRIGGER trg_canary_state_transition_guard
BEFORE UPDATE ON canary_owner_attestation_state
WHEN
    NEW.attestation_id <> OLD.attestation_id
    OR NEW.binding_key <> OLD.binding_key
    OR NOT (
        (OLD.status = 'pending' AND NEW.status IN ('accepted','rejected','expired')) OR
        (OLD.status = 'accepted' AND NEW.status IN ('consumed','expired','revoked'))
    )
    OR NOT EXISTS (
        SELECT 1
          FROM canary_owner_attestation_events e
         WHERE e.attestation_id = OLD.attestation_id
           AND e.id = (
               SELECT MAX(e2.id)
                 FROM canary_owner_attestation_events e2
                WHERE e2.attestation_id = OLD.attestation_id
           )
           AND e.from_state = OLD.status
           AND e.to_state = NEW.status
    )
    OR NOT EXISTS (
        SELECT 1
          FROM canary_owner_attestations h
         WHERE h.attestation_id = OLD.attestation_id
           AND h.binding_key = OLD.binding_key
    )
BEGIN
    SELECT RAISE(ABORT, 'invalid canary state transition');
END;
```

`accepted → accepted`, `pending → pending`, and every transition out of a terminal
state are absent from the allowed pairs and are rejected.

### 3.10 Event header, actor, and reason guard

```sql
CREATE TRIGGER trg_canary_event_header_guard
BEFORE INSERT ON canary_owner_attestation_events
WHEN
    NOT EXISTS (
        SELECT 1
          FROM canary_owner_attestations h
         WHERE h.attestation_id = NEW.attestation_id
           AND h.binding_key = NEW.binding_key
    )
    OR (NEW.actor_type = 'OWNER' AND NEW.actor_id IS NOT (
        SELECT h.owner_user_id
          FROM canary_owner_attestations h
         WHERE h.attestation_id = NEW.attestation_id
    ))
    OR (NEW.actor_type = 'SYSTEM' AND NEW.actor_id IS NOT NULL)
    OR (
        NEW.reason_code IS NOT NULL
        AND NOT EXISTS (
            SELECT 1
              FROM canary_owner_attestation_reason_codes r
             WHERE r.reason_code = NEW.reason_code
               AND r.event_type = NEW.event_type
               AND r.actor_type = NEW.actor_type
        )
    )
    OR (
        NEW.event_type IN ('REQUESTED','ACCEPTED','REJECTED','CONSUMED','REVOKED')
        AND NEW.actor_type <> 'OWNER'
    )
    OR (NEW.event_type = 'EXPIRED' AND NEW.actor_type <> 'SYSTEM')
BEGIN
    SELECT RAISE(ABORT, 'invalid canary event header/actor/reason');
END;
```

This rejects cross-attestation event injection, owner-ID mismatch, unknown reason codes,
and wrong actor/event pairings at the database boundary.

### 3.11 Event transition guard

```sql
CREATE TRIGGER trg_canary_event_transition_guard
BEFORE INSERT ON canary_owner_attestation_events
WHEN (
    CASE NEW.event_type
        WHEN 'REQUESTED' THEN
            CASE WHEN NEW.from_state = 'not_requested'
                  AND NEW.to_state = 'pending'
                  AND NOT EXISTS (
                      SELECT 1 FROM canary_owner_attestation_state s
                       WHERE s.attestation_id = NEW.attestation_id
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM canary_owner_attestation_events e
                       WHERE e.attestation_id = NEW.attestation_id
                  )
                 THEN 1 ELSE 0 END
        WHEN 'ACCEPTED' THEN
            CASE WHEN NEW.from_state = 'pending'
                  AND NEW.to_state = 'accepted'
                  AND EXISTS (
                      SELECT 1 FROM canary_owner_attestation_state s
                       WHERE s.attestation_id = NEW.attestation_id
                         AND s.status = 'pending'
                  )
                 THEN 1 ELSE 0 END
        WHEN 'REJECTED' THEN
            CASE WHEN NEW.from_state = 'pending'
                  AND NEW.to_state = 'rejected'
                  AND EXISTS (
                      SELECT 1 FROM canary_owner_attestation_state s
                       WHERE s.attestation_id = NEW.attestation_id
                         AND s.status = 'pending'
                  )
                 THEN 1 ELSE 0 END
        WHEN 'EXPIRED' THEN
            CASE WHEN NEW.from_state IN ('pending','accepted')
                  AND NEW.to_state = 'expired'
                  AND EXISTS (
                      SELECT 1 FROM canary_owner_attestation_state s
                       WHERE s.attestation_id = NEW.attestation_id
                         AND s.status = NEW.from_state
                  )
                 THEN 1 ELSE 0 END
        WHEN 'CONSUMED' THEN
            CASE WHEN NEW.from_state = 'accepted'
                  AND NEW.to_state = 'consumed'
                  AND EXISTS (
                      SELECT 1 FROM canary_owner_attestation_state s
                       WHERE s.attestation_id = NEW.attestation_id
                         AND s.status = 'accepted'
                  )
                 THEN 1 ELSE 0 END
        WHEN 'REVOKED' THEN
            CASE WHEN NEW.from_state = 'accepted'
                  AND NEW.to_state = 'revoked'
                  AND EXISTS (
                      SELECT 1 FROM canary_owner_attestation_state s
                       WHERE s.attestation_id = NEW.attestation_id
                         AND s.status = 'accepted'
                  )
                 THEN 1 ELSE 0 END
        ELSE 0
    END
) <> 1
BEGIN
    SELECT RAISE(ABORT, 'invalid canary event transition');
END;
```

### 3.12 Event time guard

```sql
CREATE TRIGGER trg_canary_event_time_guard
BEFORE INSERT ON canary_owner_attestation_events
WHEN
    julianday(NEW.created_at) IS NULL
    OR NOT EXISTS (
        SELECT 1 FROM canary_owner_attestations h
         WHERE h.attestation_id = NEW.attestation_id
    )
    OR julianday((SELECT h.requested_at FROM canary_owner_attestations h
                   WHERE h.attestation_id = NEW.attestation_id)) IS NULL
    OR julianday((SELECT h.expires_at FROM canary_owner_attestations h
                   WHERE h.attestation_id = NEW.attestation_id)) IS NULL
    OR julianday(NEW.created_at) <
       julianday((SELECT h.requested_at FROM canary_owner_attestations h
                   WHERE h.attestation_id = NEW.attestation_id))
    OR (NEW.event_type = 'REQUESTED'
        AND NEW.created_at <>
            (SELECT h.requested_at FROM canary_owner_attestations h
              WHERE h.attestation_id = NEW.attestation_id))
    OR (NEW.event_type IN ('ACCEPTED','REJECTED','CONSUMED','REVOKED')
        AND julianday(NEW.created_at) >=
            julianday((SELECT h.expires_at FROM canary_owner_attestations h
                        WHERE h.attestation_id = NEW.attestation_id)))
    OR (NEW.event_type = 'EXPIRED'
        AND julianday(NEW.created_at) <
            julianday((SELECT h.expires_at FROM canary_owner_attestations h
                        WHERE h.attestation_id = NEW.attestation_id)))
BEGIN
    SELECT RAISE(ABORT, 'invalid canary event timestamp');
END;
```

The transaction supplies `created_at`; the database does not use `CURRENT_TIMESTAMP`.
This lets callers pass an explicit test or operation timestamp and prevents an
application clock from silently extending `expires_at`.

### 3.13 A2 cycle guard

```sql
CREATE TRIGGER trg_canary_event_a2_guard
BEFORE INSERT ON canary_owner_attestation_events
WHEN
    NEW.event_type = 'CONSUMED'
    AND EXISTS (
        SELECT 1
          FROM canary_owner_attestations h
         WHERE h.attestation_id = NEW.attestation_id
           AND h.authorization_mode = 'EXISTING_CYCLE'
           AND h.bound_review_id IS NOT NULL
           AND h.bound_review_id <> NEW.review_id
    )
BEGIN
    SELECT RAISE(ABORT, 'A2 consumption review does not match bound_review_id');
END;
```

For A1 (`PRE_CYCLE`), `bound_review_id` is NULL and the `CONSUMED.review_id` becomes the
binding inside the same transaction that creates the review. For A2, the immutable
header binds the exact cycle and the trigger rejects any other review.

### 3.14 Event projection

```sql
CREATE TRIGGER trg_canary_event_project_state
AFTER INSERT ON canary_owner_attestation_events
WHEN NEW.event_type <> 'REQUESTED'
BEGIN
    UPDATE canary_owner_attestation_state
       SET status = NEW.to_state,
           updated_at = NEW.created_at
     WHERE attestation_id = NEW.attestation_id;
END;
```

If this projection update fails, SQLite rolls back the event insert; if the event is
inside an application transaction, the whole transaction also rolls back.

## 4. Insertion and transaction protocol

### 4.1 Request

1. Perform all external/current checks outside SQLite.
2. `BEGIN IMMEDIATE`.
3. Recompute canonical `binding_key` from owner/conversation/chat/creation job/name/
   link source/PR set/version and authorization mode.
4. Revalidate current owner, private chat, deletion, watched state, D-01 B, D-05, D-06,
   and exact PR set.
5. Insert the header only.
6. The header bootstrap trigger writes `REQUESTED` and the pending state.
7. Commit. On `IntegrityError`/`OperationalError`, roll back and classify:
   active binding exists, generation conflict, invalid data, or busy.
8. A duplicate active request must return the existing active attestation; it must not
   create a new generation.

The header row, initial event, and state row are atomic because they are produced by
one header `INSERT` statement/trigger chain inside the application transaction.

### 4.2 Confirmation

1. `BEGIN IMMEDIATE`.
2. Re-read header/state, owner, chat, conversation, creation job, repository name,
   D-01 B/D-05/D-06, exact PR set, and A2 cycle where applicable.
3. Read the explicit `now` timestamp.
4. If `now >= expires_at`, insert a `SYSTEM` `EXPIRED` event with
   `SYSTEM_EXPIRED`; the transition guard moves pending/accepted to expired. If the
   caller intended acceptance, acceptance must fail after expiry; do not revive.
5. Otherwise insert `ACCEPTED` with `actor_type='OWNER'`, owner `actor_id`,
   `from_state='pending'`, `to_state='accepted'`, and `created_at=now`.
6. Commit; the event projection moves state to accepted. A duplicate confirmation gets
   a unique/transition error; application returns the existing accepted result for the
   same binding/operation semantics or a conflict.

### 4.3 Consumption / reservation (I1)

1. External D-01 B/D-05/D-06/GitHub identity checks outside the DB transaction.
2. `BEGIN IMMEDIATE`.
3. Re-read accepted state, expiry, exact binding, owner/chat/deletion/watched state, and
   A2 cycle where applicable.
4. For A1, create the review cycle and immutable PR memberships in the same transaction;
   the new `review_id` is the A1 consumption binding.
5. Insert exactly one `CONSUMED` event with:
   - `review_id` (A1 new cycle or A2 exact bound cycle);
   - mandatory `operation_key`;
   - `actor_type='OWNER'`, owner `actor_id`;
   - `from_state='accepted'`, `to_state='consumed'`, `created_at=now < expires_at`.
6. The transition, A2, time, and projection triggers run; unique review and operation
   indexes are checked.
7. Commit all. Any failure rolls back review, memberships, event, and projection.

No external API call may occur inside the DB transaction.

### 4.4 I2 if selected

If I2 is selected instead of I1, consumption and review reservation are separate. The
consequence is a crash/replay window between consumption and review creation; the proof
of atomicity is unavailable. D-04 remains blocked unless the owner explicitly accepts
the weaker protocol. v3 does not choose I1 or I2.

### 4.5 Lock/busy and retries

- WAL, `busy_timeout=5000`, `BEGIN IMMEDIATE`.
- A busy/locked error is retryable only with bounded retries (for example one retry) and
  the same idempotency key; never unbounded retries.
- On `IntegrityError`, do not retry blindly: classify active binding, duplicate event,
  duplicate operation, duplicate review, or invalid transition.
- On `OperationalError: database is locked`, roll back and report a safe busy outcome;
  the caller may retry once within its request budget.

## 5. SQLite-enforced versus application-enforced

| Guarantee | SQLite enforcement | Application protocol |
|---|---|---|
| Header immutable | no-update/no-delete trigger | none |
| Events append-only | no-update/no-delete trigger | no direct event rewrite |
| State not deleted | no-delete trigger | none |
| Header creates initial request | `AFTER INSERT` bootstrap trigger | insert header only |
| Header-only orphan impossible | bootstrap + state insert guard + active unique index | use the header insert API |
| One active attestation per binding | partial unique index on state | allocate generation under `BEGIN IMMEDIATE` |
| Generation after terminal | unique `(binding_key,generation)` + state index | query max generation and allocate |
| Valid transition/from/to | table CHECK + transition guard | supply correct event |
| State update only after event | state transition guard latest-event check | state is projection only |
| Event binding matches header | event header guard | use exact header values |
| Actor/reason allowlist | FK + header guard | choose allowlisted reason |
| Expiry timing | time guard | supply explicit UTC `created_at` |
| A2 exact cycle | A2 guard | revalidate cycle authorization |
| One consumed review | partial unique review index | check/translate `IntegrityError` |
| One operation per attestation | unique `(attestation_id,operation_key)` | use stable operation key |
| Atomic reservation | not schema alone | I1 `BEGIN IMMEDIATE` transaction |
| Cross-conversation/owner/PR revalidation | not schema alone | WP-01/D-01/D-05/D-06 application checks |
| Same-name repository identity | impossible under B1 | no claim; D-04b deferred |
| External GitHub identity | not schema | external checks + DB recheck |
| Busy handling | SQLite lock semantics | bounded retry/rollback |

The schema does not claim to prove external GitHub identity, owner authorization, or
same-name repository persistence. Those remain application/WP-01/B1 concerns.

`binding_key` is computed by the application from the canonical fields; SQLite enforces
uniqueness of the stored key but cannot prove that the hash preimage is correct. The
application must recompute and compare the canonical key under `BEGIN IMMEDIATE`.
Likewise, `pr_numbers_json` checks bracket/non-empty shape only; ordering, uniqueness,
positivity, and canonical JSON are application-enforced.

## 6. A1/A2 compatibility

One schema supports both with `authorization_mode` and nullable `bound_review_id`.

### A1 — pre-cycle

- `authorization_mode='PRE_CYCLE'`, `bound_review_id IS NULL`.
- A1 helper must reuse WP-01 owner/private-chat/deletion/watched checks without weakening
  them; it cannot substitute R6 owner acceptance.
- The review is created in the consumption transaction; `CONSUMED.review_id` becomes
  the binding.
- A1 has no cycle FK at request time; the future review is bound atomically at
  consumption.

### A2 — existing cycle

- `authorization_mode='EXISTING_CYCLE'`, `bound_review_id` non-null.
- The app must verify the existing cycle is authorized for the same owner/chat/
  conversation and exact PR membership before request, confirmation, and consumption.
- The immutable header plus A2 trigger require `CONSUMED.review_id =
  bound_review_id`; unique consumed review prevents two attestations from consuming it.
- A2 prevents cross-cycle reuse structurally; it does not by itself prove the cycle is
  currently authorized.

Neither A1 nor A2 is selected. `OD-R7-D04-AUTH-03` remains pending.

## 7. Expiration and concurrency

- `expires_at` is fixed at header creation; header is immutable, so no silent extension.
- The caller supplies `created_at`; the time guard uses `julianday` comparisons.
- A pending attestation cannot be accepted at or after expiry.
- An accepted attestation cannot be consumed at or after expiry.
- A `SYSTEM` `EXPIRED` event is the only terminal expiry representation; it requires
  `created_at >= expires_at` and reason `SYSTEM_EXPIRED`.
- Expiry may be emitted lazily during any operation; no background worker is required.
- Revocation is an owner event from accepted only and is rejected after consumption or
  expiry.
- Duplicate confirmation after expiry cannot revive: accepted event is time-rejected;
  expired state blocks accepted transition.
- Concurrent confirmation: the first accepted event moves state to accepted; the second
  fails its transition/unique check.
- Expiry racing confirmation: if expiry commits first, acceptance fails; if acceptance
  commits before expiry and expiry timestamp is at/after expiry, final state is expired
  with a valid accepted event in history. No state/event mismatch is possible because
  the projection trigger and state guard use the same event.
- Concurrent consumption: consumed state/unique event/unique review prevents a second
  winner.
- All mutations use `BEGIN IMMEDIATE`; `busy_timeout` is bounded and retry is bounded.

TTL is **not selected**. The schema supports any fixed positive `expires_at` supplied by
the owner decision; no default duration exists in the SQL.

## 8. Idempotency and replay

| Operation | Database guarantee | Required application behavior |
|---|---|---|
| Request | active partial unique index; `UNIQUE(binding_key,generation)` | return existing active on duplicate; allocate generation only after terminal |
| Confirmation | `UNIQUE(attestation_id,event_type)` + pending-state transition | return existing accepted for same semantic request; reject conflicting owner/binding |
| Consumption | unique event, unique operation, unique review, A2 guard | same key retry reads/returns existing consumed result; different key is conflict |
| Duplicate Telegram callback | same unique constraints | use stable operation key; catch `IntegrityError` and classify |
| Different-key replay | unique consumed event per attestation | return conflict/replay-rejected; never create second consumption |
| Same review, second attestation | partial unique review index | return conflict; do not consume |

Important: SQLite uniqueness prevents a second row; it does **not** automatically return
the previous result. Idempotent success semantics require the application to query the
existing row after a unique conflict or before retry. This is not claimed as a pure
database guarantee.

## 9. Foreign-key and audit retention

- `creation_jobs` FK is `ON DELETE RESTRICT`: deleting a referenced job fails.
- `auto_reviews` FKs from header `bound_review_id` and event `review_id` are
  `ON DELETE RESTRICT`: audit history prevents parent deletion.
- Header/event/state FKs are `ON DELETE RESTRICT`; no `CASCADE` for audit.
- Header update/delete, event update/delete, state delete, and reason-code update/delete
  are blocked by triggers.
- Parent-row status/name updates are not DB-immutable; the application must revalidate
  them and must not treat the FK as proof of current validity. Updating a referenced
  parent primary-key value fails under the default `NO ACTION` FK behavior.
- No cascading delete is permitted for attestation audit data.
- Deleting a creation job or review while referenced fails; deleting an attestation with
  events fails.

## 10. Remaining limitations and unresolved owner decisions

| Item | Status |
|---|---|
| `OD-R7-D04-SCHEMA-01` | `PENDING`; this report does not approve it |
| `OD-R7-D04-AUTH-03` | `PENDING`; A1/A2 both structurally supported |
| `OD-R7-D04-LIFECYCLE-04` | `PENDING`; TTL duration unselected; lifecycle preserved |
| `OD-R7-D04-INTEGRATION-05` | `PENDING`; I1 documented, I2 consequence documented |
| D-04b numeric repository ID | `DEFERRED — NOT APPROVED`; no field/backfill |
| B1 | `APPROVED` only name-bound; same-name deletion/recreation indistinguishable |
| WP-04 | `WP04_D06_BLOCKED` |
| WP-05 | not started |
| WP-06 / live Canary | blocked |

Additional limitations:

- SQLite cannot prove external GitHub identity or current owner authorization.
- SQLite cannot distinguish same-name repository deletion/recreation under B1.
- SQLite cannot guarantee atomic review reservation without the I1 application
  transaction.
- The schema does not store prompts, provider payloads, tokens, or secrets.
- A2 requires application validation of the existing cycle; the FK is not authorization.
- The approved lifecycle has no separate system-invalidation state. v3 allows only
  `SYSTEM` `EXPIRED`; any additional system invalidation event/reason would require an
  owner decision and is not added here.
- No migration or `_init_schema` change is part of this design.

## 11. Static technical self-review

Checked manually against SQLite 3.46.1 syntax and the repository conventions:

- All table/column/index/trigger names are consistent.
- `CHECK` constraints cover the event/from/to mapping, actor shape, reason presence,
  operation/review presence, and the authorization-mode shape.
- The bootstrap trigger inserts `REQUESTED` before pending state; the state insert guard
  requires that event; active uniqueness aborts the whole header statement on conflict.
- The event header guard checks header existence, binding equality, owner ID, actor
  pairing, and reason-code lookup.
- The event transition guard uses `CASE` and `EXISTS` and rejects every terminal
  transition and invalid from/to combination.
- The event time guard uses `julianday` and explicit caller timestamps; no silent
  extension.
- The A2 guard rejects a consumed review different from `bound_review_id`.
- The state transition guard checks allowed pairs and the latest matching event.
- Event projection updates state only for non-requested events; a failed update aborts
  the event insert.
- Append-only triggers use the project's `SELECT RAISE(ABORT, ...)` pattern.
- No trigger uses unsupported `IF` syntax; no recursive trigger behavior is required.
- No numeric repository ID or D-04b mechanism exists.
- No application DB, DDL, migration, code, config, or test was executed or changed.

This is a static review only. It is **not** runtime validation; v3 SQL has not been
executed.

## 12. Approval and implementation status

**No owner approval or implementation authorization is granted by this report.**
`OD-R7-D04-SCHEMA-01` remains `PENDING — NOT APPROVED`. DDL was not executed.

| Status | Value |
|---|---|
| Design readiness | complete for owner review |
| DDL execution | none |
| Application integration | not attempted |
| Owner schema approval | `PENDING` |
| Implementation authorization | absent |
| Independent review | deferred/not present |
| D-04b | `DEFERRED` and untouched |
| WP-02 | `WP02_D04_BLOCKED` |
| WP-04 | `WP04_D06_BLOCKED` |
| WP-05 | not started |
| WP-06 / live Canary | blocked |
| Working tree vs committed | local working-tree only |
| Published | unpublished |

**Verdict:** `WP02_D04_SCHEMA_V3_DESIGN_READY_FOR_OWNER_REVIEW`.
