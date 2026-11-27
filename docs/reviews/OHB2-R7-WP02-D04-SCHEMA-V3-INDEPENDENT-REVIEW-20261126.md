# OHB2-R7 WP-02 / D-04 — Schema v3 Independent Design and Validation Review

**Task ID:** `OHB2-R7-WP02-D04-SCHEMA-V3-INDEPENDENT-DESIGN-AND-VALIDATION-REVIEW`
**Date:** 2026-11-26
**Verdict:** `WP02_D04_SCHEMA_V3_INDEPENDENT_REVIEW_NEEDS_REVISION`
**Review label:** `INDEPENDENT_REVIEWER_TASK — SAME AGENT, NOT A THIRD PARTY`
**Current WP-02 status:** `WP02_D04_BLOCKED`
**`OD-R7-D04-SCHEMA-01`:** `PENDING — NOT APPROVED`

**Scope:** review-only. No application code, SQL, schema, migration, configuration,
test, database, worker, Canary, or external operation was changed by this task.

## 1. Independence and evidence limitations

This is a separate reviewer task, but it was performed by the same agent/runtime that
authored the v3 design and validation reports. It is therefore **not** third-party
human independence. The review distinguishes:

- `INDEPENDENTLY_REPRODUCED` — rerun by this reviewer in a fresh disposable database
  using exact SQL extracted from the v3 report.
- `SOURCE_CONFIRMED` — confirmed by direct source inspection, including exact SQL,
  line-level behavior, or application architecture.
- `REPORT_ONLY` — accepted only as a claim from the v3 validation report, not rerun
  independently here.
- `NOT_REPRODUCED` — not tested because the exact SQL or application path is absent.

The reviewer did not modify the v3 design, the v3 validation report, any earlier
report, application source, tests, configuration, or the application database.

## 2. Baseline Git state

| Item | Value |
|---|---|
| Repository | `/workspace/project/OpenHandBot` |
| Branch | `agent/r6-review-delivery` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `origin/main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| HEAD tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| Modified tracked | 12 pre-existing |
| Untracked entries | 82 before this report |

All pre-existing changes and untracked files, including `.openhands/`, were preserved.
No fetch, pull, reset, clean, or history operation was performed.

### 2.1 Final state after this report

| Item | Value |
|---|---|
| Branch / HEAD / tree | unchanged |
| Modified tracked | 12 (same pre-existing set) |
| Untracked | 83 (82 pre-existing + this report) |
| Application code / schema / migration / config / test changes | none |
| Application database opened | no |

## 3. Source documents inspected

Read and cross-checked:

1. `docs/reviews/OHB2-R7-WP02-D04-SCHEMA-DESIGN-REVISION-V3-20261126.md`
   SHA-256 `d8b2bcd91ba80ab01889c7efa6c1dfec85ccd29a3002ca8d2bccfdc8fb96e1fb`.
2. `docs/reviews/OHB2-R7-WP02-D04-SCHEMA-V3-ISOLATED-SQLITE-VALIDATION-20261126.md`
   SHA-256 `28803e83a3e548548dbfc555cebd5d6400132f7671609af41211c00ad488f4be`.
3. `docs/reviews/OHB2-R7-WP02-D04-SCHEMA-DESIGN-REVISION-V2-20261126.md`,
   especially §4.1, §8.1, and §9.
4. `docs/reviews/OHB2-R7-WP02-D04-SCHEMA-V2-ISOLATED-SQLITE-VALIDATION-20261126.md`,
   especially the B6/C/D/E/G findings.
5. `docs/reviews/OHB2-R7-WP02-D04-B1-OWNER-APPROVAL-AND-REMAINING-DECISIONS-20261126.md`.
6. `docs/reviews/OHB2-R7-WP02-D04-ATTESTATION-STORAGE-DESIGN-RESOLUTION-20261126.md`,
   especially §3, §6, §7, §9, and §10.
7. `docs/reviews/OHB2-R7-APPROVED-DECISIONS-IMPLEMENTATION-PLAN-20261126.md`.
8. `docs/reviews/OHB2-R7-OWNER-DECISIONS-PACK-20261125.md` §11.
9. `AGENTS.md` and the project architecture rules.
10. Read-only SQLite architecture in `bot/db.py`: WAL, `busy_timeout=5000`,
    `PRAGMA foreign_keys=ON` fail-closed, `_init_schema()` and `BEGIN IMMEDIATE`
    reservation conventions.

The official owner record preserves D-03, D-04, D-05, D-06, D-07, D-08, D-04b, B1,
and the four pending D-04 decisions exactly as stated in the task. This review does
not reinterpret any of them.

## 4. Exact SQL and hash verification

The v3 report contains 13 fenced `sql` blocks. Independent extraction produced:

| Item | Value |
|---|---|
| Blocks | 13 |
| SQL block content lines | 397 |
| Joined lines (blocks plus 12 blank separators) | 409 |
| Exact joined SQL SHA-256 | `26e90800f29616cdd384ae4a09437a0e7da3c31cbca2e0d9b88ce551e9148902` |
| Installation | no exception |
| Tables | 4 |
| Triggers | 15 |
| Named indexes | 5 |
| Reason seeds | 3 |
| `PRAGMA foreign_key_check` | `[]` |

The v3 validation report's "409 SQL lines" is reproducible as **409 joined lines**;
the actual SQL text content is **397 lines**, with 12 blank separator lines. The v3
validation's hash is reproducible and matches. The only additional DDL in the
reviewer database was the parent fixture tables `creation_jobs` and `auto_reviews`,
clearly marked as fixtures.

## 5. Findings summary

| ID | Severity | Finding | Evidence |
|---|---|---|---|
| `IR-V3-F01` | **CRITICAL** | `INSERT OR IGNORE` on a header with an active binding creates a header + `REQUESTED` event but **no state**, violating the claimed no-orphan/active-binding bootstrap invariant | `INDEPENDENTLY_REPRODUCED` |
| `IR-V3-F02` | **CRITICAL** | `INSERT OR REPLACE` on a header for a new generation deletes the prior active state projection and creates a new active pending state without any terminal event | `INDEPENDENTLY_REPRODUCED` |
| `IR-V3-F03` | **HIGH** | Event timestamps are not monotonic: `CONSUMED` at `12:05` is accepted after `ACCEPTED` at `12:10`, leaving a valid-looking but chronologically impossible audit history | `INDEPENDENTLY_REPRODUCED` |
| `IR-V3-F04` | **HIGH** | `binding_key` canonicalization is undefined in v3, regressed from v2 §8.1; SQLite cannot prove the key includes all B1 fields or excludes generation. Two different keys for identical semantic fields produce two active attestations | `SOURCE_CONFIRMED` + `INDEPENDENTLY_REPRODUCED` |
| `IR-V3-F05` | **HIGH** | A1/A2 consumption accepts an `auto_reviews` row from another conversation/chat (A1 arbitrary review; A2 exact ID only); parent-cycle identity/authorization is application-only and not tested | `INDEPENDENTLY_REPRODUCED` |
| `IR-V3-F06` | **HIGH** | The v3 validation report omits conflict clauses, event chronology, canonical key vectors, and parent-cycle mismatch tests, yet concludes "no critical bypass" and "V4 not required" | `SOURCE_CONFIRMED` + independent adversarial results |
| `IR-V3-F07` | **MEDIUM** | `pr_numbers_json` only checks bracket/nonempty shape; duplicate/order/positivity/canonical JSON and `pr_selection_digest` relation are application-only; no schema proof of the explicit B1 PR set | `SOURCE_CONFIRMED` |
| `IR-V3-F08` | **MEDIUM** | Mutable `creation_jobs` and `auto_reviews` parent fields can change after header creation; FK does not preserve current linkage; application revalidation is required and untested | `SOURCE_CONFIRMED` |
| `IR-V3-F09` | **MEDIUM** | No separate system-invalidation event exists; only `SYSTEM EXPIRED`; a system-detected invalidation cannot be recorded as an approved audit event without an owner decision | `SOURCE_CONFIRMED` |
| `IR-V3-F10` | **LOW** | Installation is one-time, non-idempotent, with no explicit installation transaction/recovery path; partial installation behavior is not documented/tested | `SOURCE_CONFIRMED` |
| `IR-V3-F11` | **LOW** | `INSERT OR IGNORE` on a duplicate header (same generation) returns OK without creating a new attestation; idempotent success semantics are application-only and ambiguous | `INDEPENDENTLY_REPRODUCED` |
| `IR-V3-F12` | **INFO** | `A6` repeat-install, `D8` failed-projection, `E5` reservation rollback, and `T1` atomic reservation are correctly marked NOT_TESTED in the validation report; they must remain untested until integration authorization | `SOURCE_CONFIRMED` |

`CRITICAL`/`HIGH` findings block owner schema approval in this review.

## 6. Binding identity and canonicalization

### 6.1 What v3 actually specifies

The header contains the B1 fields: `owner_user_id`, `conversation_id`, `chat_id`,
`creation_job_id`, `repository_full_name`, `repository_link_source`,
`pr_numbers_json`, `attestation_version`, `statement_version`, and
`authorization_mode`. The v3 design says the application must "recompute canonical
`binding_key` from owner/conversation/chat/creation job/name/link source/PR set/
version and authorization mode" (v3 §4.1). It does **not** define:

- the exact serialization/domain separation;
- UTF-8/Unicode normalization;
- case normalization for the repository name;
- delimiter and escaping rules;
- whether `bound_review_id` is included;
- whether `schema_version` is included;
- how canonical PR ordering/uniqueness is enforced;
- test vectors for collisions or equivalent semantic inputs.

The schema stores `binding_key` as opaque 64-hex text and enforces only length/hex
characters. It cannot prove the hash preimage, field inclusion, or exclusion of
`generation`.

This is a regression from v2 §8.1, which explicitly specified SHA-256 over canonical
JSON including `schema_version`, `authorization_mode`, `bound_review_id`, B1 fields,
casefolded repository name, canonical PR array, and versions, while excluding
`generation`, timestamps, digests, and numeric IDs.

### 6.2 Independent probe: two active semantic twins

Fresh exact-v3 database, identical semantic B1 fields, different opaque
`binding_key` values:

```text
A_HEADER_1 OK
A_HEADER_2 OK
ACTIVE_COUNT 2
STATES [('attestation-0001-xxxx', 'pending'),
        ('attestation-0002-xxxx', 'pending')]
```

This is the expected behavior if the application supplies two different opaque keys.
It demonstrates that the database's "one active attestation per binding" is only
"one active attestation per stored opaque key", not a semantic B1 binding guarantee.
If the application includes `generation`, omits a field, or canonicalizes a field
differently, the schema does not detect it.

### 6.3 `IR-V3-F04` — canonical binding key is unproven

- **Severity:** HIGH.
- **Files/objects:** v3 §3.3 `binding_key`, §3.6 active index, §4.1 request,
  §5 application-only note; compare v2 §8.1.
- **Invariant:** one active attestation per exact B1 semantic binding; key excludes
  generation and includes all B1 components.
- **Reproduction:** two headers with identical fields and different 64-hex keys;
  both bootstrap to active `pending` state.
- **Expected:** one active semantic binding; a second request either returns the active
  attestation or is rejected.
- **Actual:** both are active; only the application's key computation prevents this.
- **Evidence:** `SOURCE_CONFIRMED` plus `INDEPENDENTLY_REPRODUCED`.
- **Blocks approval?:** yes, until canonicalization is specified and tested.
- **Correction:** restore and tighten the v2 §8.1 canonical contract, include
  `schema_version`, `authorization_mode`, `bound_review_id`, all B1 fields, casefold
  rules, canonical PR array, and version; exclude `generation`, timestamps,
  fingerprints, and numeric IDs; add collision/Unicode/case/whitespace/JSON-order test
  vectors. If possible, add a relational uniqueness constraint on canonical semantic
  columns or a generated canonical token owned by a trusted DB function.
- **V4 required?:** yes.

### 6.4 `IR-V3-F07` — PR JSON/digest is shape-only

- **Severity:** MEDIUM.
- **Files/objects:** v3 §3.3 `pr_numbers_json`, `pr_selection_digest`; §5.
- **Invariant:** exact sorted unique positive PR set and digest agreement.
- **Reproduction:** `[ ]`, `[1,1]`, unsorted values, whitespace, and a digest not tied
  to the PR list are accepted by the SQL shape checks.
- **Expected:** schema or a named application contract rejects noncanonical values.
- **Actual:** only bracket/nonempty/length and 64-hex digest shape are checked.
- **Evidence:** `SOURCE_CONFIRMED`; validation report's V3-NOTE-4 acknowledges it.
- **Blocks approval?:** no independently, but it is part of the F04 canonicalization
  contract and must be tested.
- **Correction:** define canonical JSON and digest algorithm, add test vectors, and
  reject duplicate/unsorted/nonpositive values in the application boundary.
- **V4 required?:** yes, bundled with F04 if owner approval depends on exact B1 PR
  binding.

### 6.5 `IR-V3-F08` — mutable parent linkage

- **Severity:** MEDIUM.
- **Files/objects:** `creation_jobs` and `auto_reviews` FKs, v3 §9.
- **Invariant:** current D-01 B linkage and D-05/D-06 authorization must be revalidated;
  a parent mutation must not silently retain authorization.
- **Reproduction:** update `creation_jobs.repo`/`status` or `auto_reviews` status/name
  after header creation; no trigger changes the header or rejects the update.
- **Expected:** the application revalidates the parent and rejects/revokes on mismatch.
- **Actual:** FK allows mutable non-key parent fields; header remains.
- **Evidence:** `SOURCE_CONFIRMED`; v3 explicitly assigns this to the application.
- **Blocks approval?:** no, if the application contract is explicit and separately
  tested; it remains unproven in this review.
- **Correction:** add current-linkage revalidation tests at request/confirmation/
  consumption; document that FK is not validity proof.
- **V4 required?:** no schema change necessarily; integration evidence required.

## 7. Bootstrap, state, and event integrity

### 7.1 Ordinary bootstrap is good

The bootstrap trigger creates one `REQUESTED` event and one pending state. The
reviewer reproduced the ordinary valid path: counts `(1,1,('pending',))`; a failed
ordinary header insert left `(0,0,0)`. The event/header binding guard, reason lookup,
A2 guard, and transition/time guards work on ordinary inserts.

### 7.2 `IR-V3-F01` — `INSERT OR IGNORE` orphan

- **Severity:** CRITICAL.
- **File/object:** v3 §3.8 `trg_canary_attestation_bootstrap`, state insert at
  `canary_owner_attestation_state`; v3 §3.9 state insert guard; active index.
- **Invariant:** a header cannot exist without a matching state projection; active
  binding uniqueness cannot be bypassed by a header-only orphan.
- **Reproduction (fresh exact-v3 DB):**

```sql
-- parent fixtures existing; header B/gen1 active
INSERT INTO canary_owner_attestations VALUES (<header B/gen1>, ...);
-- second request for same binding, different generation
INSERT OR IGNORE INTO canary_owner_attestations
VALUES (<header B/gen2>, ...);
```

- **Expected:** the second statement aborts or rolls back entirely; no target header
  or event remains.
- **Actual:** `OR_IGNORE_HEADER` returned OK; target
  `(header=1, REQUESTED=1, state=NULL)` while base remained `(1,1,pending)`.
- **Evidence:** `INDEPENDENTLY_REPRODUCED`.
- **Root cause:** the outer `OR IGNORE` conflict resolution suppresses the state
  unique conflict inside the bootstrap trigger. The state insert guard never fires
  because no state row is inserted.
- **Blocks approval?:** yes.
- **Correction:** make bootstrap dependent inserts `INSERT OR ABORT` (or otherwise
  immune to outer conflict resolution), and add an `AFTER INSERT` orphan check that
  raises if the state row is absent. Add `INSERT OR IGNORE`/`REPLACE`/UPSERT tests.
- **V4 required?:** yes.

### 7.3 `IR-V3-F02` — `INSERT OR REPLACE` state theft

- **Severity:** CRITICAL.
- **File/object:** same bootstrap trigger and state no-delete trigger.
- **Invariant:** a new generation is allowed only after the prior generation is
  terminal; the existing state projection cannot be silently deleted; state is
  append-only/immutable at the database boundary.
- **Reproduction:**

```sql
INSERT INTO canary_owner_attestations VALUES (<base B/gen1>, ...);
INSERT OR REPLACE INTO canary_owner_attestations
VALUES (<target B/gen2>, ...);
```

- **Expected:** abort; base header/event/state remain pending; no target state.
- **Actual:** `OR_REPLACE_HEADER` returned OK. Base became
  `(header=1, event=1, state=NULL)`; target became
  `(header=1, event=1, state=pending)`; total `(2,2,1)`.
- **Observed evidence:** the target active state exists without any terminal event on
  the base, and `trg_canary_state_no_delete` did not prevent the conflict-resolution
  deletion of the base state.
- **Evidence:** `INDEPENDENTLY_REPRODUCED`.
- **Blocks approval?:** yes, because it bypasses the terminal-generation rule and
  destroys a projection while leaving the header/event audit pair.
- **Correction:** use explicit `INSERT OR ABORT` in the bootstrap trigger and add a
  conflict-clause test matrix; consider a `BEFORE INSERT` header guard that checks
  active state under a write lock, and document/forbid REPLACE. A raw SQLite trigger
  may not see internal REPLACE deletes, so the dependent insert must be OR ABORT and
  the application must not use conflict clauses.
- **V4 required?:** yes.

### 7.4 `IR-V3-F11` — duplicate header returns OK without a row

- **Severity:** LOW.
- **Reproduction:** `INSERT OR IGNORE` of a duplicate header with the same
  `(binding_key, generation)` returns OK but creates no target rows.
- **Issue:** the application cannot treat `OK` as success; it must query existing
  state/header. This is an idempotency semantics gap, not a state bypass.
- **Correction:** standardize application idempotency lookup; reject unknown conflict
  outcomes. Test both same-key and different-key duplicates.
- **V4 required?:** no schema change if application contract is precise.

## 8. Transitions, expiry, revocation, and replay

### 8.1 Ordinary transition matrix

The reviewer reproduced all six intended transitions in fresh exact-v3 DBs:

- `pending → accepted`
- `pending → rejected`
- `pending → expired`
- `accepted → consumed`
- `accepted → expired`
- `accepted → revoked`

Invalid transitions, direct state updates, expired acceptance/consumption, duplicate
events, and terminal re-entry were rejected. This part of v3 is strong and matches the
validation report's ordinary-path evidence.

### 8.2 `IR-V3-F03` — timestamp chronology is not enforced

- **Severity:** HIGH.
- **Files/objects:** v3 §3.12 `trg_canary_event_time_guard`; v3 §3.4 event table.
- **Invariant:** an event's `created_at` must be chronologically consistent with the
  prior event, especially under clock rollback or caller-supplied timestamps.
- **Reproduction (fresh exact-v3 DB):**

```sql
-- header requested 12:00, expires 12:15
INSERT ... ACCEPTED ... created_at='2026-11-26T12:10:00+00:00';
INSERT ... CONSUMED ... created_at='2026-11-26T12:05:00+00:00';
```

- **Expected:** the consumed event is rejected; an event cannot precede its accepted
  transition.
- **Actual:** `CHRON_CONSUME_EARLIER OK`; state became `consumed`; event history is:

```text
REQUESTED 12:00
ACCEPTED  12:10
CONSUMED  12:05
```

- **Evidence:** `INDEPENDENTLY_REPRODUCED`.
- **Root cause:** the time guard checks only `created_at` against the header's
  `requested_at`/`expires_at`, not the latest event timestamp.
- **Blocks approval?:** yes for audit correctness; owner-facing event chronology can be
  falsified without any state inconsistency.
- **Correction:** add a monotonic guard (`NEW.created_at >= MAX(prior.created_at)` and
  likely `>` for distinct transitions), with canonical UTC timestamps. Test clock
  rollback, equal timestamps, and timezone-less input.
- **V4 required?:** yes.

### 8.3 Expiry and revocation observations

- Expiry boundary: acceptance/consumption `< expires_at`; expiry `>= expires_at`.
- Expiry/confirmation race: independent state-aware test can end in either valid
  ordering; final state must be `expired`. The reviewer did not rerun all ten race
  variants; the validation report's race evidence remains `REPORT_ONLY`.
- Revocation before consumption is accepted for the owner; revocation after
  consumption is rejected.
- No silent header extension is possible through the header update trigger.
- Expiry is lazy: the application must emit `SYSTEM EXPIRED`; no worker is assumed.
- **IR-V3-F09:** no separate system-invalidation event/reason exists; the only
  system-originated lifecycle event is expiry. This is consistent with the owner
  decision being pending, but it is an audit gap for D-05/D-06 system-detected
  invalidation.
- **Evidence:** source-confirmed + ordinary runtime for expiry/revocation; system
  invalidation `SOURCE_CONFIRMED`.

## 9. Idempotency and replay

SQLite guarantees:

- active `binding_key` uniqueness;
- one event type per attestation;
- one consumed review globally;
- one operation key per attestation;
- append-only/immutable rows under ordinary DML.

SQLite does **not** guarantee:

- translation of a duplicate/transition error into the original successful result;
- semantic idempotency for two different opaque keys for the same B1 binding;
- `INSERT OR IGNORE` success meaning a row exists;
- application-level Telegram callback dedupe beyond a stable operation key.

Observed:

- Duplicate active request: state unique error.
- Duplicate confirmation: transition/unique error; no second accepted event.
- Duplicate consumption same/different key: transition error; application must query
  the existing consumed event and operation key.
- Two attestations using one review: unique review error.
- `INSERT OR IGNORE` same-generation duplicate: OK but no target row.
- `INSERT OR IGNORE` second-generation request: header/event orphan (F01).
- `INSERT OR REPLACE` second-generation request: state theft (F02).

These are not all idempotency failures, but they show that "same-key idempotent
success" is an application contract, not a schema PASS.

## 10. A1/A2 and I1 transaction analysis

### 10.1 A2

A2 header requires `bound_review_id`; the A2 guard requires `CONSUMED.review_id` equal
to it. The exact ID equality is independently confirmed. The schema does **not** prove
that the bound `auto_reviews` row belongs to the same conversation, chat, owner,
repository, or PR membership set. Application revalidation remains required.

### 10.2 A1

A1 has no `bound_review_id`; consumption accepts any `auto_reviews` FK and binds it.
The unique consumed review prevents reuse, but the schema does not check that the
review is the one created in the same application transaction. A1 is therefore
application-only beyond the FK/unique constraints.

### 10.3 `IR-V3-F05` — parent review mismatch accepted

- **Severity:** HIGH (unproven critical authorization invariant).
- **Reproduction:** create `auto_reviews` rows with `conversation_id='OTHER-CONV',
  chat_id=8`; create an A1 attestation for `conv-1/owner 7`, accept it, consume
  `review_id=1`; same for A2 with `bound_review_id=1` and consume it.
- **Actual:** both `A1_CONSUME_MISMATCHED_REVIEW` and `A2_CONSUME_BOUND_OTHER` returned
  OK; both states became `consumed`.
- **Expected:** the application must reject the mismatched cycle before insertion; the
  schema alone cannot claim A1/A2 authorization.
- **Evidence:** `INDEPENDENTLY_REPRODUCED`.
- **Blocks approval?:** yes as an unproven critical boundary unless the owner explicitly
  approves the application-only contract and integration tests.
- **Correction:** add application transaction tests for owner/chat/conversation/
  repository/PR-membership equality; consider DB triggers for immutable parent fields
  only if architecture permits. Do not choose A1/A2 in this review.
- **V4 required?:** probably not for A2 ID equality, but the integration contract and
  tests are required.

### 10.4 I1 atomic reservation

The v3 schema can place consumption, a new review, and membership rows in one
`BEGIN IMMEDIATE` transaction because the existing `reserve_conversation_review`
already uses `BEGIN IMMEDIATE`. However, this review did not implement or test that
integration. I1 remains `NOT_TESTED` and unapproved; no claim of atomic reservation is
made.

## 11. Foreign keys, retention, and migration safety

Independently confirmed:

- deleting a referenced `creation_jobs` row fails with FK error;
- deleting a referenced `auto_reviews` row fails;
- deleting header/event/state/reason rows is blocked under ordinary DELETE;
- updating the header is blocked by immutable trigger;
- updating a parent primary key fails under FK;
- updating a parent non-key field (`creation_jobs.status`, `auto_reviews.status`) is
  allowed; application revalidation is required.

### 11.1 `IR-V3-F10` — installation/partial migration

- v3 installation has no explicit transaction/recovery section and no `IF NOT EXISTS`.
- `A6` repeat installation is correctly `NOT_TESTED`; v3 does not claim idempotence.
- A partial failure can leave some tables/triggers created and later statements
  failing; the application `_init_schema` uses `IF NOT EXISTS` conventions that v3
  does not copy.
- **Blocks approval?:** not by itself, but a migration/initialization plan and
  rollback/recovery test are needed before implementation.
- **Correction:** define one-time initialization transaction and failure behavior, or
  explicitly adopt the existing `IF NOT EXISTS`/migration convention.

### 11.2 Trigger deletion/alteration

SQLite triggers can be dropped by an actor with database write access. The schema
cannot protect its own triggers from out-of-band DDL; this is an existing trust
boundary. It is an `INFO` architecture risk, not a v3-only defect.

## 12. Independent reproduction summary

| Experiment | Result | Evidence |
|---|---|---|
| Fresh exact-v3 install | PASS: 4 tables, 15 triggers, 5 named indexes, 3 seeds, FK empty | INDEPENDENTLY_REPRODUCED |
| Ordinary header bootstrap | PASS: one REQUESTED, pending state; failure rollback `(0,0,0)` | INDEPENDENTLY_REPRODUCED |
| Two concurrent requests | one OK, one state unique error | INDEPENDENTLY_REPRODUCED |
| Two concurrent confirmations | one OK, one transition error | INDEPENDENTLY_REPRODUCED |
| `INSERT OR IGNORE` header gen2 | **FAIL**: target `(1,1,NULL)` orphan | INDEPENDENTLY_REPRODUCED |
| `INSERT OR REPLACE` header gen2 | **FAIL**: base state deleted, target active | INDEPENDENTLY_REPRODUCED |
| `INSERT OR IGNORE` duplicate same gen | OK but no target row | INDEPENDENTLY_REPRODUCED |
| `OR REPLACE`/UPSERT state accepted | rejected by state guard | INDEPENDENTLY_REPRODUCED |
| `OR REPLACE`/IGNORE duplicate event | rejected by transition/immutability guards | INDEPENDENTLY_REPRODUCED |
| Event chronology (accepted 12:10, consumed 12:05) | **FAIL**: consumed accepted | INDEPENDENTLY_REPRODUCED |
| Identical B1 fields, different opaque keys | **FAIL**: two active pending states | INDEPENDENTLY_REPRODUCED |
| A1/A2 mismatched parent review | **FAIL**: both consumed accepted | INDEPENDENTLY_REPRODUCED |
| All v3 validation concurrency cases | not all rerun | REPORT_ONLY |
| I1 atomic reservation | no application integration | NOT_TESTED |
| Failed projection update | no safe induction path | NOT_TESTED |

No application database was opened. All databases were disposable `/tmp` files.

## 13. Validation-report quality assessment

### 13.1 What the validation report did well

- All 13 v3 SQL blocks are accounted for and the exact SQL hash is reproducible.
- Parent fixture tables are clearly distinguished from the v3 package.
- Ordinary bootstrap, transition, A2, expiry, FK, and append-only tests are supported
  by observed database state.
- `A6` repeat installation, `D8` failed projection, `E5` reservation rollback, and
  `T1` atomic reservation are correctly marked `NOT_TESTED`.
- Concurrency tests use multiple connections to one file-backed database.
- The report distinguishes application-only guarantees in several places.

### 13.2 `IR-V3-F06` — missing adversarial cases undermine the verdict

- **Severity:** HIGH.
- **Files/objects:** v3 validation §4 matrix, §5 evidence, §9 "No critical ... observed",
  and §10 "V4 required? No".
- **Invariant:** a validation verdict must cover the adversarial checklist it claims to
  validate, especially request/conflict clauses and event ordering.
- **Missing tests:**
  - `INSERT OR IGNORE` / `INSERT OR REPLACE` / UPSERT / REPLACE on header, state, and
    event;
  - two identical B1 semantic fields with different opaque keys;
  - event chronology/clock rollback;
  - parent-review conversation/chat/PR mismatch;
  - canonical binding/PR JSON test vectors;
  - true `INSERT OR IGNORE` effect on bootstrap atomicity.
- **Actual:** the report's `B3` "header-only orphan" PASS is true only for ordinary
  inserts; it is false for `INSERT OR IGNORE`. Its "No critical bypass" statement is
  contradicted by the independent F01/F02/F03 probes.
- **Evidence:** `SOURCE_CONFIRMED` plus independent adversarial results.
- **Blocks approval?:** yes; a validation report cannot convert untested critical
  cases into a PASS, and its "V4 not required" conclusion is not supported.
- **Correction:** extend the matrix with conflict-clause, chronology, semantic-key,
  parent-cycle, and canonicalization tests; classify F01/F02/F03 as failures; rerun
  the verdict.
- **V4 required?:** yes for the schema corrections; validation rerun required after
  corrections.

### 13.3 Evidence labels and reproducibility

The reviewer independently reproduced the installation, ordinary bootstrap, ordinary
transitions, FK restrictions, concurrent request/confirmation, conflict-clause
bypasses, chronology bypass, opaque-key twins, and A1/A2 parent mismatch. The full
validation report's state-aware expiry race, all consumption/review races, and some
lock/rollback variants remain `REPORT_ONLY`; they are not treated as independently
proven here.

## 14. Owner-approval readiness recommendation

**Not ready for owner schema approval.** The exact v3 SQL installs and many ordinary
invariants pass, but two **CRITICAL** conflict-clause bypasses and one **HIGH** audit
chronology bypass remain, plus an **HIGH** unresolved binding/canonicalization
contract and an **HIGH** A1/A2 parent-authorization gap. These are not safely
deferred as ordinary application polish because the schema itself claims to enforce
no-orphan, active-binding, append-only, and event-time invariants.

A **v4 design revision is required** for at least:

1. `OR ABORT`/orphan-safe bootstrap and conflict-clause-proof state/event handling
   (F01/F02/F11).
2. Monotonic event timestamp enforcement (F03).
3. Exact canonical `binding_key` and PR/digest contract, including generation
   exclusion and all B1 components (F04/F07).
4. Explicit A1/A2 parent-cycle verification contract and tests, or DB-enforced
   parent checks where architecture permits (F05/F08).
5. A documented one-time initialization/recovery path or explicit adoption of the
   existing `IF NOT EXISTS` convention (F10).
6. A rerun validation matrix that includes conflict clauses, chronology, semantic-key
   twins, canonicalization vectors, parent-cycle mismatch, and the already-noted
   `NOT_TESTED` integration items (F06/F12).

## 15. Pending owner decisions

- `OD-R7-D04-SCHEMA-01`: **PENDING — NOT APPROVED**.
- `OD-R7-D04-AUTH-03`: **PENDING**; A1/A2 both structurally represented, neither
  selected.
- `OD-R7-D04-LIFECYCLE-04`: **PENDING**; TTL and complete system-invalidation
  semantics remain unselected.
- `OD-R7-D04-INTEGRATION-05`: **PENDING**; I1 atomic reservation is not implemented or
  tested.
- `OD-R7-D04-SCOPE-02`: B1 **APPROVED**, but same-name deletion/recreation remains
  indistinguishable.
- D-04b: **DEFERRED — NOT APPROVED**; no numeric repository ID, no backfill, no
  substitute identity is proposed.
- D-05: **APPROVED**; no rename/transfer/redirect support.
- D-06: **APPROVED**; private allowlisted only.
- D-07: **APPROVED_DESIGN_ONLY**.
- D-08: **APPROVED_BLOCKED**.

## 16. Status and authorization boundaries

This review grants **no owner approval**, **no implementation authorization**, and
**no runtime authorization**. D-04 remains unimplemented. No migration or Canary was
created or activated.

| Status | Value |
|---|---|
| Independent review | completed, same-agent reviewer only |
| Schema v3 owner approval | **NOT RECOMMENDED** |
| v4 design revision | **REQUIRED** |
| Application integration | not attempted |
| I1 atomic reservation | `NOT_TESTED` |
| Independent third-party review | not present |
| D-04b | `DEFERRED` and untouched |
| WP-02 | `WP02_D04_BLOCKED` |
| WP-04 | `WP04_D06_BLOCKED` |
| WP-05 | not started |
| WP-06 / live Canary | blocked |
| Application DB | not opened |
| Application code/schema/migration/config/tests | unchanged |
| Working tree vs committed | local working-tree only |
| Published | unpublished |
