# OHB2-R7 WP-02 / D-04 — Schema Design Revision v4

**Task ID:** `OHB2-R7-WP02-D04-SCHEMA-V4-DESIGN-AND-ISOLATED-VALIDATION`
**Date:** 2026-11-26
**Verdict:** `WP02_D04_SCHEMA_V4_READY_FOR_OWNER_REVIEW`
**Review label:** `AUTHOR_SELF_REVIEW — NOT THIRD-PARTY INDEPENDENT REVIEW`
**D-04 state:** `APPROVED` in principle; implementation not authorized
**`OD-R7-D04-SCHEMA-01`:** `PENDING — NOT APPROVED`
**`OD-R7-D04-AUTH-03`:** `PENDING`
**`OD-R7-D04-LIFECYCLE-04`:** `PENDING`
**`OD-R7-D04-INTEGRATION-05`:** `PENDING`

**Status vocabulary for this report:** `DESIGN_ONLY`, `SQL_VALIDATED`,
`APPLICATION_NOT_IMPLEMENTED`, `APPLICATION_INTEGRATION_NOT_TESTED`,
`INDEPENDENT_REVIEW_NOT_PERFORMED`.

**Scope:** design and isolated SQLite validation only. No application code, application
schema, migration, configuration, application tests, application database, worker,
Canary, provider, GitHub, Telegram, or external operation was changed or used.

## 1. Executive verdict

The corrected v4 SQL package installs successfully in disposable SQLite databases and
addresses the six v3 review findings:

- F01 (`INSERT OR IGNORE` header-only orphan) is blocked by a header insert guard,
  explicit bootstrap-error checks, and a state insert guard.
- F02 (`INSERT OR REPLACE` state theft) is blocked by the same active-header guard and
  conflict-safe state insert rules.
- F03 (non-monotonic event timestamps) is blocked by a fixed timestamp format and a
  nondecreasing chronology guard.
- F04 (opaque binding key) is corrected by a canonicalization contract plus a semantic
  binding registry that prevents two different externally proposed keys for the same
  stored semantic fields.
- F05 (arbitrary parent cycle) is narrowed by a review-link table and trigger that
  verify conversation, chat, repository, parent status/scope, and exact PR membership;
  creation-job and owner checks remain application-enforced because `auto_reviews` does
  not carry `creation_job_id`.
- F06 (validation gaps) is addressed by a new isolated matrix covering conflict
  clauses, chronology, semantic twins, parent mismatch, and rollback.

The exact SQL has been executed; the core schema invariants pass the tested cases.
I1 atomic reservation is validated only in a disposable fixture harness, not in the
application. The verdict is therefore **ready for a separate owner design decision**,
not owner approval and not implementation authorization.

## 2. Baseline Git state

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
| Untracked entries | 83 pre-existing |

All pre-existing modifications and untracked files, including `.openhands/`, were
preserved. No fetch, pull, reset, clean, checkout over changes, or history operation
was performed.

### 2.1 Final state after this report

| Item | Value |
|---|---|
| Branch / HEAD / tree | unchanged |
| Modified tracked | 12 (11 pre-existing application files unchanged; `.agent/PROGRESS.md` additive) |
| Untracked | 84 (83 pre-existing + this report) |
| Application DB opened | no |
| Application code/schema/migration/config/tests changed | no |

## 3. Sources inspected

- `AGENTS.md` and project architecture rules (read-only).
- v3 design:
  `docs/reviews/OHB2-R7-WP02-D04-SCHEMA-DESIGN-REVISION-V3-20261126.md`
  (`d8b2bcd91ba80ab01889c7efa6c1dfec85ccd29a3002ca8d2bccfdc8fb96e1fb`).
- v3 isolated validation:
  `docs/reviews/OHB2-R7-WP02-D04-SCHEMA-V3-ISOLATED-SQLITE-VALIDATION-20261126.md`
  (`28803e83a3e548548dbfc555cebd5d6400132f7671609af41211c00ad488f4be`).
- v3 independent review:
  `docs/reviews/OHB2-R7-WP02-D04-SCHEMA-V3-INDEPENDENT-REVIEW-20261126.md`.
- v2 design and v2 isolated validation (historical; not edited).
- B1 approval/remaining decisions report.
- Attestation storage design resolution.
- R7 approved decisions implementation plan.
- `docs/reviews/OHB2-R7-OWNER-DECISIONS-PACK-20261125.md` §11.
- Read-only SQLite patterns in `bot/db.py`: WAL, `busy_timeout=5000`, fail-closed
  `PRAGMA foreign_keys=ON`, `_init_schema`, `BEGIN IMMEDIATE`, reservation and
  membership tables.

No required source was missing.

## 4. Preserved decisions and boundaries

Preserved exactly:

- D-03 `APPROVED — current-owner-revalidation`.
- D-04 `APPROVED — canary-only-owner-attestation`; implementation not authorized.
- D-04b `DEFERRED — NOT APPROVED`; no numeric repository ID, backfill, or substitute.
- D-05 `APPROVED — reject-rename-transfer`.
- D-06 `APPROVED — private-allowlisted-only`.
- D-07 `APPROVED_DESIGN_ONLY`.
- D-08 `APPROVED_BLOCKED`.
- B1 `APPROVED`; name-bound D-01 linkage only; same-name deletion/recreation remains
  indistinguishable; WP-04 remains `WP04_D06_BLOCKED`.

Pending and not selected by this report:

- `OD-R7-D04-SCHEMA-01`
- `OD-R7-D04-AUTH-03`
- `OD-R7-D04-LIFECYCLE-04`
- `OD-R7-D04-INTEGRATION-05`

## 5. v3 findings F01–F06 and remediation mapping

| Finding | v3 problem | v4 remediation | Test evidence |
|---|---|---|---|
| F01 | `INSERT OR IGNORE` could leave header + REQUESTED with no state | `BEFORE INSERT` header guard rejects active binding/duplicate generation; bootstrap uses explicit checks; state insert requires exactly the initial REQUESTED event; header bootstrap ends with a state-presence `RAISE(ABORT)` | `F01_OR_IGNORE_ACTIVE`, `F01_COUNTS`; no target rows |
| F02 | `INSERT OR REPLACE` could delete an active state and create a new pending state without terminal event | Header guard rejects any active-binding/new-generation insert before REPLACE can delete; state insert rejects non-initial or non-pending state; no-delete triggers retained | `F02_OR_REPLACE_ACTIVE`, `F02_BASE_TARGET`; base state remains pending, target absent |
| F03 | `CONSUMED` earlier than `ACCEPTED` accepted | Fixed UTC microsecond format; `julianday` validity; nondecreasing event timestamp guard; same-instant ties allowed | `F03_EARLIER` error; `TIE_CONSUME` pass; `F03_INVALID` error |
| F04 | Opaque `binding_key`; semantic twins with different keys | Canonical contract (below); `canary_owner_attestation_bindings` semantic registry with unique semantic tuple; header must match binding row; binding insert guard blocks alternate keys for same fields | `F04_BINDING_TWIN_1/2`; fixed vectors |
| F05 | A1/A2 could bind arbitrary parent review | `canary_owner_attestation_review_links` + consumed-event trigger verifies conversation, chat, repository, status/scope, A1/A2 mode, exact PR membership; link is immutable and unique; creation-job/owner remain application checks | `A1_WRONG_CHAT`, `A1_NO_PR_ROWS`, `A2_WRONG_REVIEW`, `A2_WRONG_CHAT` all error; exact links pass |
| F06 | Validation omitted conflict clauses/chronology/canonicalization/parent tests | New matrix with conflict forms, F03, F04 vectors, A1/A2 parent tests, I1 fixture transaction, concurrency, install/repeat | This report §13 |

No v3 report was edited.

## 6. Complete proposed v4 SQL (SQL_VALIDATED)

The exact text below is the proposed SQL package. It is executed in disposable
SQLite databases only; parent fixture tables (`creation_jobs`, `auto_reviews`,
`auto_review_memberships`) are separate harness fixtures and are not part of the
package. The exact SQL SHA-256 is recorded in §13.

```sql
-- D-04 Schema v4 proposed SQL (design-only; isolated validation)
-- Parent fixtures are NOT part of this file: creation_jobs, auto_reviews,
-- auto_review_memberships are existing application tables in the fixture harness.

CREATE TABLE canary_owner_attestation_reason_codes (
    reason_code TEXT PRIMARY KEY CHECK (length(reason_code) BETWEEN 1 AND 64),
    event_type  TEXT NOT NULL CHECK (event_type IN ('REJECTED','EXPIRED','REVOKED')),
    actor_type  TEXT NOT NULL CHECK (actor_type IN ('OWNER','SYSTEM')),
    UNIQUE (reason_code, event_type, actor_type)
);
INSERT INTO canary_owner_attestation_reason_codes(reason_code,event_type,actor_type)
VALUES ('OWNER_REJECTED','REJECTED','OWNER'),
       ('OWNER_REVOKED','REVOKED','OWNER'),
       ('SYSTEM_EXPIRED','EXPIRED','SYSTEM');

CREATE TABLE canary_owner_attestation_bindings (
    binding_key            TEXT PRIMARY KEY
                           CHECK (length(binding_key)=64 AND binding_key NOT GLOB '*[^0-9a-f]*'),
    schema_version         INTEGER NOT NULL CHECK (schema_version=4),
    domain                 TEXT NOT NULL CHECK (domain='OHB2-D04-BINDING-V1'),
    authorization_mode     TEXT NOT NULL CHECK (authorization_mode IN ('PRE_CYCLE','EXISTING_CYCLE')),
    bound_review_id        INTEGER REFERENCES auto_reviews(id) ON DELETE RESTRICT,
    bound_review_slot      INTEGER NOT NULL CHECK (bound_review_slot >= 0),
    owner_user_id          INTEGER NOT NULL CHECK (owner_user_id > 0),
    conversation_id        TEXT NOT NULL CHECK (length(conversation_id) BETWEEN 1 AND 128),
    chat_id                INTEGER NOT NULL CHECK (chat_id > 0),
    creation_job_id        INTEGER NOT NULL REFERENCES creation_jobs(id) ON DELETE RESTRICT,
    repository_full_name   TEXT NOT NULL CHECK (length(repository_full_name) BETWEEN 1 AND 255),
    repository_link_source TEXT NOT NULL CHECK (repository_link_source='canary_creation_job'),
    pr_numbers_json        TEXT NOT NULL
                           CHECK (length(pr_numbers_json) BETWEEN 2 AND 4096
                                  AND pr_numbers_json <> '[]'
                                  AND substr(pr_numbers_json,1,1)='['
                                  AND substr(pr_numbers_json,-1,1)=']'),
    attestation_version    TEXT NOT NULL CHECK (length(attestation_version) BETWEEN 1 AND 64),
    statement_version      TEXT NOT NULL CHECK (length(statement_version) BETWEEN 1 AND 64),
    CHECK (chat_id=owner_user_id),
    CHECK ((authorization_mode='PRE_CYCLE' AND bound_review_id IS NULL AND bound_review_slot=0) OR
           (authorization_mode='EXISTING_CYCLE' AND bound_review_id IS NOT NULL AND bound_review_slot=bound_review_id))
);
CREATE UNIQUE INDEX ux_canary_binding_semantic ON canary_owner_attestation_bindings(
    schema_version, domain, authorization_mode, bound_review_slot,
    owner_user_id, conversation_id, chat_id, creation_job_id,
    repository_link_source, repository_full_name, pr_numbers_json,
    attestation_version, statement_version
);

CREATE TABLE canary_owner_attestations (
    attestation_id         TEXT PRIMARY KEY CHECK (length(attestation_id) BETWEEN 16 AND 128),
    schema_version         INTEGER NOT NULL CHECK (schema_version=4),
    generation             INTEGER NOT NULL CHECK (generation > 0),
    binding_key            TEXT NOT NULL REFERENCES canary_owner_attestation_bindings(binding_key) ON DELETE RESTRICT,
    owner_user_id          INTEGER NOT NULL CHECK (owner_user_id > 0),
    conversation_id        TEXT NOT NULL CHECK (length(conversation_id) BETWEEN 1 AND 128),
    chat_id                INTEGER NOT NULL CHECK (chat_id > 0),
    creation_job_id        INTEGER NOT NULL REFERENCES creation_jobs(id) ON DELETE RESTRICT,
    repository_full_name   TEXT NOT NULL CHECK (length(repository_full_name) BETWEEN 1 AND 255),
    repository_link_source TEXT NOT NULL CHECK (repository_link_source='canary_creation_job'),
    pr_numbers_json        TEXT NOT NULL
                           CHECK (length(pr_numbers_json) BETWEEN 2 AND 4096
                                  AND pr_numbers_json <> '[]'
                                  AND substr(pr_numbers_json,1,1)='['
                                  AND substr(pr_numbers_json,-1,1)=']'),
    pr_selection_digest    TEXT NOT NULL CHECK (length(pr_selection_digest)=64 AND pr_selection_digest NOT GLOB '*[^0-9a-f]*'),
    attestation_version    TEXT NOT NULL CHECK (length(attestation_version) BETWEEN 1 AND 64),
    statement_version      TEXT NOT NULL CHECK (length(statement_version) BETWEEN 1 AND 64),
    authorization_mode     TEXT NOT NULL CHECK (authorization_mode IN ('PRE_CYCLE','EXISTING_CYCLE')),
    bound_review_id        INTEGER REFERENCES auto_reviews(id) ON DELETE RESTRICT,
    requested_at           TEXT NOT NULL CHECK (length(requested_at)=27 AND requested_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-9][0-9][0-9][0-9][0-9][0-9]Z'),
    expires_at             TEXT NOT NULL CHECK (length(expires_at)=27 AND expires_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-9][0-9][0-9][0-9][0-9][0-9]Z'),
    CHECK (chat_id=owner_user_id),
    CHECK (expires_at > requested_at),
    CHECK ((authorization_mode='PRE_CYCLE' AND bound_review_id IS NULL) OR
           (authorization_mode='EXISTING_CYCLE' AND bound_review_id IS NOT NULL)),
    UNIQUE (binding_key, generation)
);

CREATE TABLE canary_owner_attestation_prs (
    attestation_id TEXT NOT NULL REFERENCES canary_owner_attestations(attestation_id) ON DELETE RESTRICT,
    pr_number      INTEGER NOT NULL CHECK (pr_number > 0),
    PRIMARY KEY (attestation_id, pr_number)
);

CREATE TABLE canary_owner_attestation_events (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    attestation_id    TEXT NOT NULL REFERENCES canary_owner_attestations(attestation_id) ON DELETE RESTRICT,
    binding_key       TEXT NOT NULL CHECK (length(binding_key)=64 AND binding_key NOT GLOB '*[^0-9a-f]*'),
    event_type        TEXT NOT NULL CHECK (event_type IN ('REQUESTED','ACCEPTED','REJECTED','EXPIRED','CONSUMED','REVOKED')),
    from_state        TEXT NOT NULL CHECK (from_state IN ('not_requested','pending','accepted')),
    to_state          TEXT NOT NULL CHECK (to_state IN ('pending','accepted','rejected','expired','consumed','revoked')),
    actor_type        TEXT NOT NULL CHECK (actor_type IN ('OWNER','SYSTEM')),
    actor_id          INTEGER,
    reason_code       TEXT REFERENCES canary_owner_attestation_reason_codes(reason_code) ON DELETE RESTRICT,
    operation_key     TEXT CHECK (operation_key IS NULL OR length(operation_key) BETWEEN 1 AND 128),
    review_id         INTEGER REFERENCES auto_reviews(id) ON DELETE RESTRICT,
    created_at        TEXT NOT NULL CHECK (length(created_at)=27 AND created_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-9][0-9][0-9][0-9][0-9][0-9]Z'),
    event_fingerprint TEXT NOT NULL CHECK (length(event_fingerprint)=64 AND event_fingerprint NOT GLOB '*[^0-9a-f]*'),
    UNIQUE (attestation_id, event_type),
    CHECK ((event_type='REQUESTED' AND from_state='not_requested' AND to_state='pending') OR
           (event_type='ACCEPTED'  AND from_state='pending' AND to_state='accepted') OR
           (event_type='REJECTED'  AND from_state='pending' AND to_state='rejected') OR
           (event_type='EXPIRED'   AND from_state IN ('pending','accepted') AND to_state='expired') OR
           (event_type='CONSUMED'  AND from_state='accepted' AND to_state='consumed') OR
           (event_type='REVOKED'   AND from_state='accepted' AND to_state='revoked')),
    CHECK ((actor_type='OWNER' AND actor_id IS NOT NULL AND actor_id>0) OR
           (actor_type='SYSTEM' AND actor_id IS NULL)),
    CHECK ((event_type IN ('REJECTED','EXPIRED','REVOKED') AND reason_code IS NOT NULL) OR
           (event_type IN ('REQUESTED','ACCEPTED','CONSUMED') AND reason_code IS NULL)),
    CHECK ((event_type='CONSUMED' AND review_id IS NOT NULL AND operation_key IS NOT NULL) OR
           (event_type<>'CONSUMED' AND review_id IS NULL AND operation_key IS NULL))
);
CREATE UNIQUE INDEX ux_canary_attestation_operation ON canary_owner_attestation_events(attestation_id,operation_key) WHERE operation_key IS NOT NULL;
CREATE UNIQUE INDEX ux_canary_consumed_review ON canary_owner_attestation_events(review_id) WHERE event_type='CONSUMED';
CREATE INDEX idx_canary_event_attestation ON canary_owner_attestation_events(attestation_id,id);
CREATE INDEX idx_canary_attestation_expires ON canary_owner_attestations(expires_at);

CREATE TABLE canary_owner_attestation_state (
    attestation_id TEXT PRIMARY KEY REFERENCES canary_owner_attestations(attestation_id) ON DELETE RESTRICT,
    binding_key    TEXT NOT NULL CHECK (length(binding_key)=64 AND binding_key NOT GLOB '*[^0-9a-f]*'),
    status         TEXT NOT NULL CHECK (status IN ('pending','accepted','rejected','expired','consumed','revoked')),
    updated_at     TEXT NOT NULL CHECK (length(updated_at)=27 AND updated_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-9][0-9][0-9][0-9][0-9][0-9]Z')
);
CREATE UNIQUE INDEX ux_canary_active_binding ON canary_owner_attestation_state(binding_key) WHERE status IN ('pending','accepted');

CREATE TABLE canary_owner_attestation_review_links (
    attestation_id         TEXT PRIMARY KEY REFERENCES canary_owner_attestations(attestation_id) ON DELETE RESTRICT,
    review_id              INTEGER NOT NULL UNIQUE REFERENCES auto_reviews(id) ON DELETE RESTRICT,
    authorization_mode     TEXT NOT NULL CHECK (authorization_mode IN ('PRE_CYCLE','EXISTING_CYCLE')),
    bound_review_id        INTEGER,
    owner_user_id          INTEGER NOT NULL CHECK (owner_user_id > 0),
    conversation_id        TEXT NOT NULL CHECK (length(conversation_id) BETWEEN 1 AND 128),
    chat_id                INTEGER NOT NULL CHECK (chat_id > 0),
    creation_job_id        INTEGER NOT NULL REFERENCES creation_jobs(id) ON DELETE RESTRICT,
    repository_full_name   TEXT NOT NULL CHECK (length(repository_full_name) BETWEEN 1 AND 255),
    repository_link_source TEXT NOT NULL CHECK (repository_link_source='canary_creation_job'),
    pr_numbers_json        TEXT NOT NULL,
    pr_selection_digest    TEXT NOT NULL CHECK (length(pr_selection_digest)=64 AND pr_selection_digest NOT GLOB '*[^0-9a-f]*'),
    created_at             TEXT NOT NULL CHECK (length(created_at)=27 AND created_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-9][0-9][0-9][0-9][0-9][0-9]Z'),
    CHECK (chat_id=owner_user_id),
    CHECK ((authorization_mode='PRE_CYCLE' AND bound_review_id IS NULL) OR
           (authorization_mode='EXISTING_CYCLE' AND bound_review_id IS NOT NULL))
);

CREATE TRIGGER trg_canary_reason_no_update BEFORE UPDATE ON canary_owner_attestation_reason_codes
BEGIN SELECT RAISE(ABORT,'canary reason codes are immutable'); END;
CREATE TRIGGER trg_canary_reason_no_delete BEFORE DELETE ON canary_owner_attestation_reason_codes
BEGIN SELECT RAISE(ABORT,'canary reason codes are immutable'); END;

CREATE TRIGGER trg_canary_binding_no_update BEFORE UPDATE ON canary_owner_attestation_bindings
BEGIN SELECT RAISE(ABORT,'canary bindings are immutable'); END;
CREATE TRIGGER trg_canary_binding_no_delete BEFORE DELETE ON canary_owner_attestation_bindings
BEGIN SELECT RAISE(ABORT,'canary bindings are immutable'); END;
CREATE TRIGGER trg_canary_binding_insert_guard BEFORE INSERT ON canary_owner_attestation_bindings
WHEN EXISTS (SELECT 1 FROM canary_owner_attestation_bindings b WHERE b.binding_key=NEW.binding_key)
  OR EXISTS (SELECT 1 FROM canary_owner_attestation_bindings b
             WHERE b.schema_version=NEW.schema_version AND b.domain=NEW.domain
               AND b.authorization_mode=NEW.authorization_mode
               AND b.bound_review_slot=NEW.bound_review_slot
               AND b.owner_user_id=NEW.owner_user_id
               AND b.conversation_id=NEW.conversation_id
               AND b.chat_id=NEW.chat_id
               AND b.creation_job_id=NEW.creation_job_id
               AND b.repository_link_source=NEW.repository_link_source
               AND b.repository_full_name=NEW.repository_full_name
               AND b.pr_numbers_json=NEW.pr_numbers_json
               AND b.attestation_version=NEW.attestation_version
               AND b.statement_version=NEW.statement_version)
BEGIN SELECT RAISE(ABORT,'canary binding already exists'); END;

CREATE TRIGGER trg_canary_header_no_update BEFORE UPDATE ON canary_owner_attestations
BEGIN SELECT RAISE(ABORT,'canary attestations are immutable'); END;
CREATE TRIGGER trg_canary_header_no_delete BEFORE DELETE ON canary_owner_attestations
BEGIN SELECT RAISE(ABORT,'canary attestations are immutable'); END;
CREATE TRIGGER trg_canary_header_insert_guard BEFORE INSERT ON canary_owner_attestations
WHEN NOT EXISTS (
    SELECT 1 FROM canary_owner_attestation_bindings b
     WHERE b.binding_key=NEW.binding_key AND b.schema_version=NEW.schema_version
       AND b.domain='OHB2-D04-BINDING-V1'
       AND b.authorization_mode=NEW.authorization_mode
       AND b.bound_review_id IS NEW.bound_review_id
       AND b.owner_user_id=NEW.owner_user_id
       AND b.conversation_id=NEW.conversation_id
       AND b.chat_id=NEW.chat_id
       AND b.creation_job_id=NEW.creation_job_id
       AND b.repository_link_source=NEW.repository_link_source
       AND b.repository_full_name=NEW.repository_full_name
       AND b.pr_numbers_json=NEW.pr_numbers_json
       AND b.attestation_version=NEW.attestation_version
       AND b.statement_version=NEW.statement_version
)
  OR EXISTS (SELECT 1 FROM canary_owner_attestation_state s
             WHERE s.binding_key=NEW.binding_key AND s.status IN ('pending','accepted'))
  OR EXISTS (SELECT 1 FROM canary_owner_attestations h
             WHERE h.binding_key=NEW.binding_key AND h.generation=NEW.generation)
  OR NEW.generation <> COALESCE((SELECT MAX(h.generation) FROM canary_owner_attestations h
                                 WHERE h.binding_key=NEW.binding_key),0)+1
BEGIN SELECT RAISE(ABORT,'invalid or competing canary header'); END;

CREATE TRIGGER trg_canary_pr_no_update BEFORE UPDATE ON canary_owner_attestation_prs
BEGIN SELECT RAISE(ABORT,'canary PR members are immutable'); END;
CREATE TRIGGER trg_canary_pr_no_delete BEFORE DELETE ON canary_owner_attestation_prs
BEGIN SELECT RAISE(ABORT,'canary PR members are immutable'); END;
CREATE TRIGGER trg_canary_pr_insert_guard BEFORE INSERT ON canary_owner_attestation_prs
WHEN EXISTS (SELECT 1 FROM canary_owner_attestation_prs p
             WHERE p.attestation_id=NEW.attestation_id AND p.pr_number=NEW.pr_number)
BEGIN SELECT RAISE(ABORT,'duplicate canary PR member'); END;

CREATE TRIGGER trg_canary_event_no_update BEFORE UPDATE ON canary_owner_attestation_events
BEGIN SELECT RAISE(ABORT,'canary attestation events are immutable'); END;
CREATE TRIGGER trg_canary_event_no_delete BEFORE DELETE ON canary_owner_attestation_events
BEGIN SELECT RAISE(ABORT,'canary attestation events are immutable'); END;
CREATE TRIGGER trg_canary_event_duplicate_guard BEFORE INSERT ON canary_owner_attestation_events
WHEN EXISTS (SELECT 1 FROM canary_owner_attestation_events e
             WHERE e.attestation_id=NEW.attestation_id AND e.event_type=NEW.event_type)
  OR (NEW.operation_key IS NOT NULL AND EXISTS (SELECT 1 FROM canary_owner_attestation_events e
             WHERE e.attestation_id=NEW.attestation_id AND e.operation_key=NEW.operation_key))
  OR (NEW.event_type='CONSUMED' AND EXISTS (SELECT 1 FROM canary_owner_attestation_events e
             WHERE e.event_type='CONSUMED' AND e.review_id=NEW.review_id))
BEGIN SELECT RAISE(ABORT,'duplicate canary event/operation/review'); END;

CREATE TRIGGER trg_canary_event_header_guard BEFORE INSERT ON canary_owner_attestation_events
WHEN NOT EXISTS (SELECT 1 FROM canary_owner_attestations h
                 WHERE h.attestation_id=NEW.attestation_id AND h.binding_key=NEW.binding_key)
  OR (NEW.actor_type='OWNER' AND NEW.actor_id IS NOT (SELECT h.owner_user_id FROM canary_owner_attestations h WHERE h.attestation_id=NEW.attestation_id))
  OR (NEW.actor_type='SYSTEM' AND NEW.actor_id IS NOT NULL)
  OR (NEW.reason_code IS NOT NULL AND NOT EXISTS (SELECT 1 FROM canary_owner_attestation_reason_codes r
                 WHERE r.reason_code=NEW.reason_code AND r.event_type=NEW.event_type AND r.actor_type=NEW.actor_type))
  OR (NEW.event_type IN ('REQUESTED','ACCEPTED','REJECTED','CONSUMED','REVOKED') AND NEW.actor_type<>'OWNER')
  OR (NEW.event_type='EXPIRED' AND NEW.actor_type<>'SYSTEM')
BEGIN SELECT RAISE(ABORT,'invalid canary event header/actor/reason'); END;

CREATE TRIGGER trg_canary_event_state_guard BEFORE INSERT ON canary_owner_attestation_events
WHEN (
    CASE NEW.event_type
        WHEN 'REQUESTED' THEN CASE WHEN NEW.from_state='not_requested' AND NEW.to_state='pending'
             AND NOT EXISTS (SELECT 1 FROM canary_owner_attestation_state s WHERE s.attestation_id=NEW.attestation_id)
             AND NOT EXISTS (SELECT 1 FROM canary_owner_attestation_events e WHERE e.attestation_id=NEW.attestation_id)
             THEN 1 ELSE 0 END
        WHEN 'ACCEPTED' THEN CASE WHEN NEW.from_state='pending' AND NEW.to_state='accepted'
             AND EXISTS (SELECT 1 FROM canary_owner_attestation_state s WHERE s.attestation_id=NEW.attestation_id AND s.status='pending')
             THEN 1 ELSE 0 END
        WHEN 'REJECTED' THEN CASE WHEN NEW.from_state='pending' AND NEW.to_state='rejected'
             AND EXISTS (SELECT 1 FROM canary_owner_attestation_state s WHERE s.attestation_id=NEW.attestation_id AND s.status='pending')
             THEN 1 ELSE 0 END
        WHEN 'EXPIRED' THEN CASE WHEN NEW.from_state IN ('pending','accepted') AND NEW.to_state='expired'
             AND EXISTS (SELECT 1 FROM canary_owner_attestation_state s WHERE s.attestation_id=NEW.attestation_id AND s.status=NEW.from_state)
             THEN 1 ELSE 0 END
        WHEN 'CONSUMED' THEN CASE WHEN NEW.from_state='accepted' AND NEW.to_state='consumed'
             AND EXISTS (SELECT 1 FROM canary_owner_attestation_state s WHERE s.attestation_id=NEW.attestation_id AND s.status='accepted')
             THEN 1 ELSE 0 END
        WHEN 'REVOKED' THEN CASE WHEN NEW.from_state='accepted' AND NEW.to_state='revoked'
             AND EXISTS (SELECT 1 FROM canary_owner_attestation_state s WHERE s.attestation_id=NEW.attestation_id AND s.status='accepted')
             THEN 1 ELSE 0 END
        ELSE 0
    END
) <> 1
BEGIN SELECT RAISE(ABORT,'invalid canary event transition'); END;

CREATE TRIGGER trg_canary_event_time_guard BEFORE INSERT ON canary_owner_attestation_events
WHEN julianday(NEW.created_at) IS NULL
  OR NOT EXISTS (SELECT 1 FROM canary_owner_attestations h WHERE h.attestation_id=NEW.attestation_id)
  OR julianday((SELECT h.requested_at FROM canary_owner_attestations h WHERE h.attestation_id=NEW.attestation_id)) IS NULL
  OR julianday((SELECT h.expires_at FROM canary_owner_attestations h WHERE h.attestation_id=NEW.attestation_id)) IS NULL
  OR julianday(NEW.created_at) < julianday((SELECT h.requested_at FROM canary_owner_attestations h WHERE h.attestation_id=NEW.attestation_id))
  OR (NEW.event_type='REQUESTED' AND NEW.created_at <> (SELECT h.requested_at FROM canary_owner_attestations h WHERE h.attestation_id=NEW.attestation_id))
  OR julianday(NEW.created_at) < (SELECT MAX(julianday(e.created_at)) FROM canary_owner_attestation_events e WHERE e.attestation_id=NEW.attestation_id)
  OR (NEW.event_type IN ('ACCEPTED','REJECTED','CONSUMED','REVOKED')
      AND julianday(NEW.created_at) >= julianday((SELECT h.expires_at FROM canary_owner_attestations h WHERE h.attestation_id=NEW.attestation_id)))
  OR (NEW.event_type='EXPIRED' AND julianday(NEW.created_at) < julianday((SELECT h.expires_at FROM canary_owner_attestations h WHERE h.attestation_id=NEW.attestation_id)))
BEGIN SELECT RAISE(ABORT,'invalid canary event timestamp'); END;

CREATE TRIGGER trg_canary_state_no_delete BEFORE DELETE ON canary_owner_attestation_state
BEGIN SELECT RAISE(ABORT,'canary state cannot be deleted'); END;
CREATE TRIGGER trg_canary_state_insert_guard BEFORE INSERT ON canary_owner_attestation_state
WHEN NEW.status<>'pending'
  OR NOT EXISTS (SELECT 1 FROM canary_owner_attestations h
                 WHERE h.attestation_id=NEW.attestation_id AND h.binding_key=NEW.binding_key)
  OR NOT EXISTS (SELECT 1 FROM canary_owner_attestation_events e
                 WHERE e.attestation_id=NEW.attestation_id AND e.event_type='REQUESTED' AND e.to_state='pending')
  OR (SELECT COUNT(*) FROM canary_owner_attestation_events e WHERE e.attestation_id=NEW.attestation_id)<>1
  OR NEW.updated_at IS NOT (SELECT h.requested_at FROM canary_owner_attestations h WHERE h.attestation_id=NEW.attestation_id)
BEGIN SELECT RAISE(ABORT,'canary state requires pending header and only REQUESTED event'); END;
CREATE TRIGGER trg_canary_state_transition_guard BEFORE UPDATE ON canary_owner_attestation_state
WHEN NEW.attestation_id<>OLD.attestation_id
  OR NEW.binding_key<>OLD.binding_key
  OR NOT ((OLD.status='pending' AND NEW.status IN ('accepted','rejected','expired')) OR
          (OLD.status='accepted' AND NEW.status IN ('consumed','expired','revoked')))
  OR NOT EXISTS (SELECT 1 FROM canary_owner_attestation_events e
                 WHERE e.attestation_id=OLD.attestation_id
                   AND e.id=(SELECT MAX(e2.id) FROM canary_owner_attestation_events e2 WHERE e2.attestation_id=OLD.attestation_id)
                   AND e.from_state=OLD.status AND e.to_state=NEW.status)
  OR NOT EXISTS (SELECT 1 FROM canary_owner_attestations h
                 WHERE h.attestation_id=OLD.attestation_id AND h.binding_key=OLD.binding_key)
  OR EXISTS (SELECT 1 FROM canary_owner_attestation_state s
             WHERE s.binding_key=OLD.binding_key AND s.attestation_id<>OLD.attestation_id
               AND s.status IN ('pending','accepted'))
BEGIN SELECT RAISE(ABORT,'invalid canary state transition'); END;

CREATE TRIGGER trg_canary_bootstrap AFTER INSERT ON canary_owner_attestations
BEGIN
    INSERT INTO canary_owner_attestation_events
      (attestation_id,binding_key,event_type,from_state,to_state,actor_type,actor_id,reason_code,operation_key,review_id,created_at,event_fingerprint)
    VALUES (NEW.attestation_id,NEW.binding_key,'REQUESTED','not_requested','pending','OWNER',NEW.owner_user_id,NULL,NULL,NULL,NEW.requested_at,lower(hex(randomblob(32))));
    INSERT INTO canary_owner_attestation_state
      (attestation_id,binding_key,status,updated_at)
    VALUES (NEW.attestation_id,NEW.binding_key,'pending',NEW.requested_at);
    SELECT RAISE(ABORT,'canary bootstrap incomplete') WHERE NOT EXISTS
      (SELECT 1 FROM canary_owner_attestation_state s WHERE s.attestation_id=NEW.attestation_id);
END;

CREATE TRIGGER trg_canary_event_project_state AFTER INSERT ON canary_owner_attestation_events
WHEN NEW.event_type<>'REQUESTED'
BEGIN
    UPDATE canary_owner_attestation_state SET status=NEW.to_state,updated_at=NEW.created_at
     WHERE attestation_id=NEW.attestation_id;
END;

CREATE TRIGGER trg_canary_event_a2_guard BEFORE INSERT ON canary_owner_attestation_events
WHEN NEW.event_type='CONSUMED' AND EXISTS (
    SELECT 1 FROM canary_owner_attestations h
     WHERE h.attestation_id=NEW.attestation_id AND h.authorization_mode='EXISTING_CYCLE'
       AND h.bound_review_id IS NOT NULL AND h.bound_review_id<>NEW.review_id)
BEGIN SELECT RAISE(ABORT,'A2 consumption does not match bound_review_id'); END;

CREATE TRIGGER trg_canary_event_consumed_link AFTER INSERT ON canary_owner_attestation_events
WHEN NEW.event_type='CONSUMED'
BEGIN
    INSERT INTO canary_owner_attestation_review_links
      (attestation_id,review_id,authorization_mode,bound_review_id,owner_user_id,conversation_id,chat_id,creation_job_id,repository_full_name,repository_link_source,pr_numbers_json,pr_selection_digest,created_at)
    SELECT h.attestation_id,NEW.review_id,h.authorization_mode,h.bound_review_id,h.owner_user_id,h.conversation_id,h.chat_id,h.creation_job_id,h.repository_full_name,h.repository_link_source,h.pr_numbers_json,h.pr_selection_digest,NEW.created_at
      FROM canary_owner_attestations h
      JOIN auto_reviews r ON r.id=NEW.review_id
     WHERE h.attestation_id=NEW.attestation_id
       AND h.binding_key=NEW.binding_key
       AND r.conversation_id=h.conversation_id
       AND r.chat_id=h.chat_id
       AND lower(r.repository_full_name)=lower(h.repository_full_name)
       AND r.status='reserved'
       AND r.scope='conversation'
       AND ((h.authorization_mode='PRE_CYCLE' AND h.bound_review_id IS NULL)
            OR (h.authorization_mode='EXISTING_CYCLE' AND h.bound_review_id=NEW.review_id))
       AND (SELECT COUNT(*) FROM canary_owner_attestation_prs p WHERE p.attestation_id=h.attestation_id)>0
       AND (SELECT COUNT(*) FROM auto_review_memberships m WHERE m.review_id=NEW.review_id AND lower(m.repository_full_name)=lower(h.repository_full_name))
           =(SELECT COUNT(*) FROM canary_owner_attestation_prs p WHERE p.attestation_id=h.attestation_id)
       AND NOT EXISTS (SELECT 1 FROM canary_owner_attestation_prs p
                        WHERE p.attestation_id=h.attestation_id AND NOT EXISTS
                          (SELECT 1 FROM auto_review_memberships m
                            WHERE m.review_id=NEW.review_id AND lower(m.repository_full_name)=lower(h.repository_full_name) AND m.pr_number=p.pr_number))
       AND NOT EXISTS (SELECT 1 FROM auto_review_memberships m
                        WHERE m.review_id=NEW.review_id AND lower(m.repository_full_name)=lower(h.repository_full_name) AND NOT EXISTS
                          (SELECT 1 FROM canary_owner_attestation_prs p
                            WHERE p.attestation_id=h.attestation_id AND p.pr_number=m.pr_number));
    SELECT RAISE(ABORT,'review parent/membership mismatch') WHERE NOT EXISTS
      (SELECT 1 FROM canary_owner_attestation_review_links l WHERE l.attestation_id=NEW.attestation_id);
END;

CREATE TRIGGER trg_canary_review_link_no_update BEFORE UPDATE ON canary_owner_attestation_review_links
BEGIN SELECT RAISE(ABORT,'canary review links are immutable'); END;
CREATE TRIGGER trg_canary_review_link_no_delete BEFORE DELETE ON canary_owner_attestation_review_links
BEGIN SELECT RAISE(ABORT,'canary review links are immutable'); END;
CREATE TRIGGER trg_canary_review_link_insert_guard BEFORE INSERT ON canary_owner_attestation_review_links
WHEN EXISTS (SELECT 1 FROM canary_owner_attestation_review_links l WHERE l.attestation_id=NEW.attestation_id)
  OR NOT EXISTS (SELECT 1 FROM canary_owner_attestation_events e
                 WHERE e.attestation_id=NEW.attestation_id AND e.event_type='CONSUMED' AND e.review_id=NEW.review_id)
BEGIN SELECT RAISE(ABORT,'canary review link must be first and match CONSUMED event'); END;

```

## 7. Semantic binding and canonicalization

### 7.1 Exact included fields

`binding_key = SHA-256(UTF-8(canonical JSON object))` with lowercase hex output. The
object contains exactly:

| Field | Type / rule |
|---|---|
| `attestation_version` | nonempty NFC string, 1-64 chars, case-sensitive |
| `authorization_mode` | `PRE_CYCLE` or `EXISTING_CYCLE` |
| `bound_review_id` | `null` for A1; positive integer for A2 |
| `chat_id` | positive integer; equal to owner |
| `conversation_id` | nonempty NFC string, 1-128 chars, case-sensitive |
| `creation_job_id` | positive integer |
| `domain` | fixed literal `OHB2-D04-BINDING-V1` |
| `owner_user_id` | positive integer |
| `pr_numbers` | sorted ascending unique positive integers; nonempty |
| `repository_full_name` | normalized `owner/name`, trimmed, NFC, casefolded |
| `repository_link_source` | fixed `canary_creation_job` |
| `schema_version` | integer `4` |
| `statement_version` | nonempty NFC string, 1-64 chars, case-sensitive |

### 7.2 Excluded fields

The key excludes `attestation_id`, `binding_key` itself, `generation`, requested/expiry
timestamps, lifecycle state, event IDs, event types, event operation keys, review link
rows, PR digest, event fingerprints, `pr_selection_digest`, and every numeric GitHub
repository ID.

### 7.3 Normalization and parsing

- UTF-8 bytes, NFC normalization for all strings. No alternative Unicode normalization.
- `owner_user_id`, `chat_id`, and `creation_job_id` are positive integers; booleans are
  rejected as integers; null is rejected.
- `conversation_id` is exact case-sensitive NFC text, no leading/trailing whitespace.
- `repository_full_name` is trimmed, NFC-normalized, must contain exactly one `/`,
  both components must match `[A-Za-z0-9._-]+`, and is then `casefold()`-ed. No URL,
  redirect, extra slash, empty component, or whitespace is accepted. The header stores
  the canonical value; the display form is not a separate identity.
- `pr_numbers` accepts only positive integers, rejects booleans, duplicates, empty
  arrays, and unsorted user input; it sorts ascending and encodes as JSON integers.
- `attestation_version`/`statement_version` are NFC, nonempty, case-sensitive; no
  trimming or casefold.
- `bound_review_id` is explicit `null` for A1 and a positive integer for A2; no
  ambiguous string/number coercion.
- `domain` and `schema_version` prevent cross-version/cross-purpose collisions.

### 7.4 Canonical JSON

The object keys are lexicographically sorted; separators are exactly `,` and `:`;
there is no insignificant whitespace; arrays are ordered; null is explicit; integers
are unquoted; non-finite/floating values are rejected; `ensure_ascii=False` with UTF-8
encoding. The input to SHA-256 is exactly those bytes, with no BOM and no trailing
newline.

### 7.5 Authoritative helper

The future application must use one helper only:

```python
def d04_binding_key(*, schema_version=4, owner_user_id, conversation_id, chat_id,
                    creation_job_id, repository_full_name,
                    repository_link_source='canary_creation_job',
                    pr_numbers, attestation_version, statement_version,
                    authorization_mode, bound_review_id=None) -> str:
    # validate types/positivity/nullability; NFC all strings; trim and validate
    # exactly one owner/name; casefold repository; sort/unique PR integers;
    # build the exact 13-field object; canonical JSON; SHA-256; lowercase hex.
```

No alternate helper, field order, JSON library defaults, case handling, or digest
algorithm is permitted. The SQL registry enforces one row per stored semantic tuple;
the application helper is still required to map case/Unicode/PR-order variants to that
tuple. **SQLite does not independently verify the SHA-256 preimage.** A malformed
application could insert a valid 64-hex value not corresponding to the fields unless
the one-helper contract is enforced in future integration tests.

### 7.6 Fixed test vectors

Vector A (A1):

Canonical input fields:

```text
schema_version=4
domain=OHB2-D04-BINDING-V1
authorization_mode=PRE_CYCLE
bound_review_id=null
owner_user_id=7
conversation_id=conv-1
chat_id=7
creation_job_id=1
repository_full_name=Owner/Repo  -> owner/repo
repository_link_source=canary_creation_job
pr_numbers=(2,1) -> [1,2]
attestation_version=v1
statement_version=s1
```

Canonical JSON bytes (escaped form):

```text
{"attestation_version":"v1","authorization_mode":"PRE_CYCLE","bound_review_id":null,"chat_id":7,"conversation_id":"conv-1","creation_job_id":1,"domain":"OHB2-D04-BINDING-V1","owner_user_id":7,"pr_numbers":[1,2],"repository_full_name":"owner/repo","repository_link_source":"canary_creation_job","schema_version":4,"statement_version":"s1"}
```

Expected SHA-256:

```text
bab74402ba66e19cee3a37973dc0cdb4e2165daac18e6cac3a759035e8801513
```

Semantically equivalent variations with the same key:

- repository `"  OWNER/REPO  "`;
- PR input `(1,2)` or `[2,1]`;
- `statement_version` `"se\u0301"` and `"s\u00e9"` after NFC;
- A1 `bound_review_id=null` again.

Vector A2 (different from A1):

```text
authorization_mode=EXISTING_CYCLE
bound_review_id=2
canonical JSON:
{"attestation_version":"v1","authorization_mode":"EXISTING_CYCLE","bound_review_id":2,"chat_id":7,"conversation_id":"conv-1","creation_job_id":1,"domain":"OHB2-D04-BINDING-V1","owner_user_id":7,"pr_numbers":[1,2],"repository_full_name":"owner/repo","repository_link_source":"canary_creation_job","schema_version":4,"statement_version":"s1"}
SHA-256:
eba014997f71a8899e1939933c2ed2eaa46ae9a7761d05458c27f9caddee75ef
```

Different inputs and expected distinct keys:

| Variation | SHA-256 |
|---|---|
| PR `[1,3]` | `882355b81e1b47e2e3c4105ec83f3de826ff112bb591e4118ce7511dc3349131` |
| repository `owner/other` | `cee3759300da5c1bbecb42f9b7d81f64bce9440f618697ed7187659ba36db0f5` |
| owner/chat `8/8` | `939aecf0cb79d992f84007ebec4cbdd78765af7f877fc58b20c3904185bb59f4` |

The reviewer reproduced these vectors with the single Python helper. The SQL
semantic registry independently rejects a second binding row with identical stored
fields but a different proposed key; a distinct semantic tuple is accepted. This
does not prove a bad application cannot bypass the helper; that remains an
application-enforced boundary and must be tested in WP-02 integration.

## 8. Lifecycle, timestamp, expiry, and chronology

### 8.1 Lifecycle

```text
not_requested -> pending
pending -> accepted | rejected | expired
accepted -> consumed | expired | revoked
rejected | expired | consumed | revoked -> terminal
```

`REQUESTED` is created only by the header bootstrap. `ACCEPTED`, `REJECTED`,
`CONSUMED`, `REVOKED` require owner actor/ID; `EXPIRED` requires system actor and
`SYSTEM_EXPIRED`. No actor/reason code outside the finite table is accepted.

### 8.2 Timestamp format

All timestamps are exactly **`YYYY-MM-DDTHH:MM:SS.ffffffZ`** (27 characters): UTC,
six fractional digits, uppercase `Z`. The SQL CHECK uses a digit/GLOB shape. The
application helper must produce this exact form; no timezone offset, no variable
precision, no timezone-less value, no `CURRENT_TIMESTAMP`.

- `requested_at` and `expires_at` are fixed at header creation.
- `expires_at > requested_at` by canonical lexical comparison.
- Event `created_at` is supplied by the caller; it is never derived from a database
  clock.
- `REQUESTED.created_at` must equal `requested_at`.
- `created_at` must be valid `julianday` and at or after `requested_at`.
- Non-requested events use **nondecreasing** chronology: `created_at` at least the
  latest prior event timestamp. Equal timestamps are allowed; earlier timestamps are
  rejected. This is tested by `F03_EARLIER` and `TIE_CONSUME`.
- Acceptance/rejection/consumption/revocation must be before `expires_at`; expiry must
  be at or after `expires_at`.
- Malformed or noncanonical values fail the CHECK or `julianday` guard.

### 8.3 Expiry/revocation

- Pending at/after expiry cannot be accepted or rejected.
- Accepted at/after expiry cannot be consumed or revoked.
- `SYSTEM EXPIRED` can move pending or accepted to expired at/after expiry.
- A confirmation after expiry cannot revive an expired state.
- No header timestamp update path exists; no silent extension.
- Expiry is emitted lazily by the application; no background worker is assumed.
- A separate system-invalidation event is not added; the approved lifecycle decision
  remains pending. This is a documented audit limitation, not silently chosen.
- TTL remains unselected.

## 9. A1/A2 authorization and parent-cycle validation

### 9.1 Modes without selection

`authorization_mode` is explicit. A1 (`PRE_CYCLE`) has `bound_review_id=NULL`; A2
(`EXISTING_CYCLE`) has a positive exact `bound_review_id`. Neither mode is selected by
this report. `OD-R7-D04-AUTH-03` remains pending.

### 9.2 Parent checks

The consumed-event trigger inserts a `canary_owner_attestation_review_links` row only if
all of these match:

- header `attestation_id` and `binding_key`;
- `auto_reviews.conversation_id` = header conversation;
- `auto_reviews.chat_id` = header chat;
- case-insensitive `auto_reviews.repository_full_name` = header repository;
- `auto_reviews.status='reserved'` and `scope='conversation'`;
- A1 has null bound review; A2 has `bound_review_id = review_id`;
- exact nonempty `canary_owner_attestation_prs` rows equal all
  `auto_review_memberships` PR numbers for the same review/repository, with no missing
  or extra membership.

If no such parent/link exists, the AFTER trigger raises `review parent/membership
mismatch`, rolling back the event and projection. The link table is immutable, unique
per review, and cannot be updated or deleted.

### 9.3 Checks not enforced by v4 SQL

The following remain application-enforced and are **APPLICATION_INTEGRATION_NOT_TESTED**:

- `creation_job_id`: `auto_reviews` has no `creation_job_id` column; the application
  must compare the attestation's D-01 B job ID with the reservation context.
- Owner identity beyond `chat_id=owner_user_id`; application must compare
  `Config.owner_id`/watched/current ownership.
- Exact PR membership source: application must populate `canary_owner_attestation_prs`
  from the canonical header/PR resolution, and must not merge unrelated pending
  memberships into a different PR set.
- Current repository identity/GitHub verification, D-05 rename/transfer, D-06
  visibility/fork/archive/allowlist, and same-name recreation: application/WP-01/
  WP-04/D-04b boundaries.
- Parent mutation after request/confirmation/consumption: application revalidation is
  required; the link is a snapshot, not current validity.
- One-PR Canary and pending-membership merging: application reservation logic.

### 9.4 Parent mutation

Mutable `creation_jobs` and `auto_reviews` non-key fields are not immutable in v4.
The application must re-read and revalidate at request, confirmation, consumption, and
reservation. The immutable review link records the accepted snapshot but cannot prove
that the parent is still current later.

## 10. I1 atomic reservation, consumption, and membership

### 10.1 Transaction design

The future application transaction must use `BEGIN IMMEDIATE`:

1. Re-read and validate attestation/binding/parent/expiry/state.
2. Revalidate current owner, chat, conversation, creation job, repository, PR set,
   D-01 B, D-05, D-06, and A1/A2 authorization.
3. Reserve the exact intended review cycle and create exact membership rows.
4. Insert exactly one `CONSUMED` event with `review_id` and `operation_key`.
5. The consumed-event trigger validates the parent/membership and inserts the immutable
   review link.
6. Commit all; any error rolls back review, memberships, event, state projection, and
   link together.

No network, GitHub, provider, Telegram, or external call occurs inside the transaction.

### 10.2 Isolated fixture result

The reviewer created fixture `auto_reviews`/`auto_review_memberships` tables and ran:

- `I1_EXACT`: review 10 + 2 memberships + consumed event + link committed; observed
  `(review=1, memberships=2, consumed=1, link=1)`.
- `I1_FAIL_BAD`: review 11/memberships inserted with wrong chat; consumed event failed
  parent check; rollback left `(review=0, memberships=0, consumed=0)` and state
  `pending` for the failed transaction; the previous accepted state was not changed
  outside that transaction.
- `NOPARENT_CONSUME`: accepted header, no review; consumed event failed and state
  remained `accepted`, with only `REQUESTED`/`ACCEPTED` events.
- Concurrent consumption: one attestation succeeded; the other received duplicate
  event/review error; one review link remained.

### 10.3 I1 status

`I1` is **SQL_VALIDATED in a fixture harness**, but **APPLICATION_INTEGRATION_NOT_TESTED**
because the actual WP-02 reservation/API integration was not implemented or authorized.
No exactly-once or production guarantee is claimed.

## 11. Database-enforced versus application-enforced

| Invariant | v4 enforcement |
|---|---|
| Exact v4 install | SQLite DDL (one-shot; see §12) |
| Binding semantic registry | SQLite unique semantic index; application canonical helper for normalization/SHA |
| Header fields match binding | header insert trigger |
| No active semantic twin | semantic registry + header active guard |
| Generation sequence | header guard requires `MAX+1` |
| Bootstrap no orphan | header guard + bootstrap state-presence check + state guard |
| No conflict-clause state deletion | header guard + state insert/update guards + no-delete triggers |
| Valid lifecycle events | CHECK + transition guard |
| State projection consistent | state update guard latest event |
| Monotonic timestamp | CHECK format + `julianday` + latest-event guard |
| Expiry/revocation | time guard + terminal state |
| Actor/reason allowlist | FK + header/actor/reason guard |
| Append-only audit | no-update/no-delete triggers + conflict guards |
| A2 exact review | A2 guard + review link |
| Parent conversation/chat/repo/status/scope | review-link trigger |
| Exact PR membership | review-link trigger vs PR child table |
| Creation-job/owner/current GitHub | application/WP-01 integration |
| Parent mutation currentness | application revalidation |
| Review reservation atomicity | application BEGIN IMMEDIATE; fixture-tested only |
| `binding_key` SHA preimage | application one-helper contract; not DB-proven |
| Same-name repository identity | impossible under B1/D-04b deferred |
| Idempotent success result | application maps unique/transition errors |

## 12. Installation, repeat installation, and recovery

### 12.1 Exact installation

The exact v4 SQL is executed only in disposable databases:

- SQLite: **3.46.1**
- Every connection: `PRAGMA foreign_keys=ON`, read-back `1`
- `PRAGMA journal_mode=WAL`
- `PRAGMA busy_timeout=5000`
- `BEGIN IMMEDIATE` for write sequences
- Exact SQL: 7 tables, 6 named indexes, 27 triggers, 3 seed rows, FK check `[]`
- SQL SHA-256: `d1731c077c72d022820a5fcfa331525cab3db399e8946a4074f9d3b70c8e75a4`
- SQL lines: 365

Exact SQL installation succeeded with no error.

### 12.2 Repeat installation

The SQL is intentionally **one-shot**; it does not use `IF NOT EXISTS` for the v4
tables/triggers. Re-running it produced:

```text
OperationalError: table canary_owner_attestation_reason_codes already exists
```

This is an expected non-idempotent behavior, not a hidden PASS. The future application
installer must use the existing `_init_schema`/`CREATE ... IF NOT EXISTS` strategy or
an explicitly versioned migration; the v4 SQL package alone must not be blindly
repeated.

### 12.3 Partial installation

A deliberately partial prefix created only:

```text
canary_owner_attestation_bindings
canary_owner_attestation_reason_codes
```

Running the full package afterward failed on the already-created reason table and
left the partial schema. Therefore:

- **Partial installation recovery is NOT_TESTED / not supplied by v4 SQL.**
- The implementation task must wrap installation in `BEGIN IMMEDIATE` and roll back on
  failure, or use idempotent object creation plus schema-version checks.
- This is a migration/install prerequisite, not a claim of application readiness.

No migration was executed against the application database.

## 13. Isolated test matrix and exact outcomes

Legend: PASS means the exact v4 SQL ran and the expected outcome was observed.
FAIL means an observed behavior violates the claimed invariant. NOT_TESTED means the
exact path was absent or application-only.

| ID | Test | Result | Observed |
|---|---|---|---|
| A1 | Exact v4 install | PASS | 7 tables, 27 triggers, 6 named indexes, 3 seeds, FK `[]` |
| A2 | Repeat install | FAIL (expected one-shot) | reason table already exists |
| A3 | Partial prefix then full install | FAIL (not recoverable by SQL alone) | 2 tables left; full run fails |
| B1 | Normal A1 bootstrap | PASS | `(1 REQUESTED, 1 pending state)` |
| B2 | `INSERT OR IGNORE` active header | PASS | `invalid or competing canary header`; target counts `(0,0,0)` |
| B3 | `INSERT OR REPLACE` active header | PASS | error; base state remains pending; target absent |
| B4 | `INSERT OR IGNORE` same generation | PASS | error; no target |
| B5 | `UPDATE OR REPLACE` header | PASS | immutable error |
| B6 | Normal A1 accept/consume/link | PASS | state consumed; review link 1 |
| C1 | Pending → accepted | PASS | state accepted |
| C2 | Pending → rejected | PASS | state rejected |
| C3 | Pending → expired | PASS | state expired |
| C4 | Accepted → consumed | PASS | state consumed |
| C5 | Accepted → expired | PASS | state expired |
| C6 | Accepted → revoked | PASS | state revoked |
| C7 | Invalid transitions/direct state update | PASS | transition/state guard errors |
| D1 | `INSERT OR REPLACE` state accepted | PASS | state insert guard error |
| D2 | `INSERT OR REPLACE` state pending after terminal | PASS | state insert guard error |
| D3 | `UPDATE OR REPLACE` state | PASS | state transition guard error |
| D4 | `ON CONFLICT DO UPDATE` state | PASS | state insert guard error |
| D5 | `INSERT OR IGNORE`/`REPLACE` event duplicate | PASS | transition/duplicate guard errors |
| D6 | `ON CONFLICT DO NOTHING/DO UPDATE` event duplicate | PASS | transition/immutable guard errors |
| D7 | `UPDATE OR REPLACE` event | PASS | immutable event error |
| D8 | `INSERT OR IGNORE`/`REPLACE` binding twin | PASS | binding semantic guard error |
| D9 | `ON CONFLICT DO UPDATE` binding twin | PASS | binding guard error |
| D10 | `INSERT OR IGNORE`/`REPLACE` PR duplicate | PASS | PR guard error |
| D11 | `UPDATE OR REPLACE` PR | PASS | immutable PR error |
| D12 | `INSERT OR IGNORE`/`REPLACE` review link | PASS | link guard error |
| D13 | `UPDATE OR REPLACE` review link | PASS | immutable link error |
| E1 | `ON CONFLICT DO NOTHING` active header | PASS | header guard error |
| E2 | `ON CONFLICT DO UPDATE` active header | PASS | header guard error |
| F1 | Accepted `12:10` then consumed `12:05` | PASS | timestamp error; state remains accepted |
| F2 | Equal timestamp accepted/consumed | PASS | tie allowed; consumed |
| F3 | Malformed timestamp | PASS | timestamp error |
| F4 | Expiry boundary before/at/after | PASS | before accepted; at/after rejected; expiry accepted at/after |
| G1 | Canonical vector A | PASS | SHA `bab74402...` |
| G2 | A1 canonical-equivalent variants | PASS | same SHA as A |
| G3 | A2 vector | PASS | SHA `eba01499...` |
| G4 | Different PR/repo/owner vectors | PASS | distinct SHA values listed in §7.6 |
| H1 | Semantic twins, same stored fields/different key | PASS | binding guard rejects second |
| H2 | Distinct semantic binding | PASS | second binding allowed |
| I1 | A1 exact parent + membership | PASS | consumed event + review link |
| I2 | A1 wrong chat | PASS | link trigger rejects; state accepted |
| I3 | A1 no PR child rows | PASS | link trigger rejects |
| I4 | A2 exact bound review | PASS | consumed + link |
| I5 | A2 wrong review | PASS | A2 guard rejects |
| I6 | A2 wrong chat | PASS | link trigger rejects |
| I7 | Cross-conversation, cross-repository, wrong PR membership | PASS | link trigger rejects all three; state remains `accepted` |
| I8 | Cross-owner/creation-job | APPLICATION_NOT_TESTED | `auto_reviews` has no owner/creation_job column; application must check |
| J1 | Expiry/confirmation/revocation | PASS | expiry/revocation guards; lazy expiry |
| J2 | Confirmation/expiry race | PASS | state-aware race ended `expired`; accepted first can be followed by valid expiry |
| K1 | Append-only header/binding/event/state/PR/reason | PASS | update/delete errors |
| K2 | FK creation_job/review restrictions | PASS | FK errors in tested linked cases |
| K3 | Consumed review uniqueness | PASS | duplicate consumed/review errors |
| L1 | I1 exact fixture transaction | PASS | review 1, memberships 2, consumed 1, link 1 |
| L2 | I1 wrong-parent fixture rollback | PASS | review/membership/event 0; state unchanged |
| L3 | I1 no-parent rollback | PASS | state accepted; no consumed event |
| L4 | Concurrent consumption | PASS | one consumed/link; other duplicate/review error |
| M1 | Concurrent requests | PASS | one header OK; one header guard error |
| M2 | Concurrent confirmations | PASS | one accepted; one transition error |
| M3 | Concurrent expiry race | PASS | final expired; no inconsistent pair |
| M4 | Busy lock | PASS | `OperationalError: database is locked` |
| N1 | Application I1 reservation/membership API | NOT_TESTED | fixture only; no WP-02 integration |
| N2 | One-PR pending-membership merge | NOT_TESTED | requires application reservation path |
| N3 | Provider/GitHub/owner authorization | NOT_TESTED | no external call or app integration |
| N4 | Failed projection update | NOT_TESTED | no safe fault-injection path without disabling guards |

### 13.1 Exact SQL hash and counts

```text
SQL_SHA256 d1731c077c72d022820a5fcfa331525cab3db399e8946a4074f9d3b70c8e75a4
SQL_LINES 365
TABLES 7
TRIGGERS 27
NAMED_INDEXES 6
REASON_SEEDS 3
FK_CHECK []
```

The exact SQL block in §6 is the executed package; parent fixture tables are separate
and were not included in the hash.

### 13.2 Failure classification

`A2`/`A3`: install/repeat behavior is explicitly limited; not presented as a successful
idempotent installer.

`N1`–`N4`: application integration/external identity is not claimed.

No F01/F02/F03/F04/F05/F06 critical/high v3 bypass was observed after v4 corrections
within the stated enforcement boundary.

## 14. Residual risks and unresolved owner decisions

| Risk / decision | Status |
|---|---|
| `OD-R7-D04-SCHEMA-01` | `PENDING — NOT APPROVED` |
| `OD-R7-D04-AUTH-03` | `PENDING`; A1/A2 both structurally supported; neither selected |
| `OD-R7-D04-LIFECYCLE-04` | `PENDING`; TTL and full system-invalidation semantics unselected |
| `OD-R7-D04-INTEGRATION-05` | `PENDING`; I1 fixture tested, app integration not tested |
| D-04b numeric repository ID | `DEFERRED — NOT APPROVED` |
| B1 same-name deletion/recreation | indistinguishable; WP-04 `WP04_D06_BLOCKED` |
| Application binding helper bypass | application-enforced; SQL cannot prove SHA preimage |
| Creation-job/owner parent checks | application-enforced; `auto_reviews` lacks creation_job_id |
| One-PR/pending-membership merge | application reservation contract; not tested |
| System invalidation audit | no separate system event; owner lifecycle decision pending |
| Installation/repeat/partial recovery | one-shot SQL; migration installer prerequisite |
| Provider/GitHub/current authorization | not tested; external and application-only |
| Independent third-party review | not performed |

No application integration, provider call, GitHub/Telegram delivery, worker, Canary,
or production validation is claimed.

## 15. Adversarial self-review

The author self-review checked:

- all v3 F01–F06 remediations against the executed matrix;
- header/state conflict clauses (`IGNORE`, `REPLACE`, `UPDATE OR REPLACE`,
  `ON CONFLICT DO NOTHING/UPDATE`);
- binding semantic twins and canonical vectors;
- parent review conversation/chat/repository/PR mismatch;
- A1/A2 exact parent; no AUTH choice;
- event chronology and malformed timestamp;
- state/link/PR/event append-only;
- I1 fixture transaction and rollback;
- concurrent requests/confirmations/consumption/busy lock;
- installation/repeat/partial behavior.

This is **AUTHOR_SELF_REVIEW**, not independent review. No third-party independent
review was performed. A future independent review must not treat this report as
independent evidence.

## 16. Implementation prerequisites and non-authorization

Before any implementation, a separate owner authorization must resolve at least:

- `OD-R7-D04-SCHEMA-01` (the v4 SQL itself);
- `OD-R7-D04-AUTH-03` (A1 or A2; no silent choice);
- `OD-R7-D04-LIFECYCLE-04` (TTL and system invalidation);
- `OD-R7-D04-INTEGRATION-05` (I1 reservations/API/transaction).

The future implementation must also:

- implement one canonical `d04_binding_key` helper and fixed growth/regression vectors;
- implement parent `creation_job_id`/owner/current D-01/D-05/D-06 validation;
- populate exact PR child rows and never merge unrelated pending memberships;
- use one `BEGIN IMMEDIATE` reservation/consumption transaction;
- use `CREATE ... IF NOT EXISTS`/schema-version or a one-shot transactional installer;
- test application integration and external authorization where authorized;
- keep D-04b deferred and not present any numeric-ID substitute.

**This report grants no owner approval, no implementation authorization, and no runtime
authorization.** D-04 remains unimplemented. No migration, worker, Canary, provider,
GitHub, Telegram, or production operation was performed.
