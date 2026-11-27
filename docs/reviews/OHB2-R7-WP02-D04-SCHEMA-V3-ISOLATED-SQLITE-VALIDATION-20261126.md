# OHB2-R7 WP-02 / D-04 — Schema v3 Isolated SQLite Validation

**Task ID:** `OHB2-R7-WP02-D04-SCHEMA-V3-ISOLATED-SQLITE-VALIDATION`
**Date:** 2026-11-26
**Verdict:** `WP02_D04_SCHEMA_V3_SQLITE_VALIDATED_WITH_NOTES`
**Review label:** `AUTHOR_SELF_REVIEW — NOT INDEPENDENT REVIEW`
**Current WP-02 status:** `WP02_D04_BLOCKED`
**`OD-R7-D04-SCHEMA-01`:** `PENDING — NOT APPROVED`

**Scope:** isolated runtime SQL validation only. No application database, schema,
migration, application code, configuration, test, worker, Canary, or external operation
was touched.

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
| Untracked entries | 81 pre-existing |

Source:

- v3 design:
  `docs/reviews/OHB2-R7-WP02-D04-SCHEMA-DESIGN-REVISION-V3-20261126.md`
  (`d8b2bcd91ba80ab01889c7efa6c1dfec85ccd29a3002ca8d2bccfdc8fb96e1fb`)
- Exact SQL code blocks extracted from that report: 13 blocks, 409 SQL lines,
  SHA-256 `26e90800f29616cdd384ae4a09437a0e7da3c31cbca2e0d9b88ce551e9148902`.

All pre-existing changes and untracked files, including `.openhands/`, were preserved.
No fetch, pull, reset, clean, or history change was performed.

### 1.1 Final state after this report

| Item | Value |
|---|---|
| Branch / HEAD / tree | unchanged |
| Modified tracked | 12 (same pre-existing set) |
| Untracked | 82 (81 pre-existing + this report) |
| Application code / schema / migration / config / test changes | none |
| Application DB opened | no |

## 2. SQLite environment

- SQLite version: **3.46.1**
- Disposable database: `/tmp/ohb2-d04-v3-isolated-*/v3.sqlite3` and
  `/tmp/ohb2-d04-v3-concurrency-*/v3.sqlite3`.
- Every connection: `PRAGMA foreign_keys=ON`, read-back = `1`.
- `PRAGMA journal_mode=WAL`, `PRAGMA busy_timeout=5000` for normal operations; `1` ms
  only for the deliberate lock/busy test.
- Writes use `BEGIN IMMEDIATE`; failures roll back explicitly.
- Parent fixture tables (`creation_jobs`, `auto_reviews`) were created only in the
  disposable database to satisfy the v3 foreign keys.
- No `Database(...)` application initialization and no project database path were used.

## 3. Exact SQL source and installation

The 13 SQL code blocks were extracted in report order and concatenated without editing:
reason table/seed, header, events, state, indexes, append-only triggers, bootstrap,
state guards, event header guard, transition guard, time guard, A2 guard, projection
trigger.

Exact SQL SHA-256:
`26e90800f29616cdd384ae4a09437a0e7da3c31cbca2e0d9b88ce551e9148902`.

Installation result:

```text
INSTALL RESULT=OK
TABLES ['canary_owner_attestation_events', 'canary_owner_attestation_reason_codes',
        'canary_owner_attestation_state', 'canary_owner_attestations']
INDEXES ux_canary_attestation_active_binding, ux_canary_attestation_operation,
        ux_canary_attestation_consumed_review, idx_canary_attestation_expires_at,
        idx_canary_event_attestation (+ SQLite autoindexes)
TRIGGERS 15 trg_canary_* triggers
REASON_COUNT 3
FK_CHECK []
```

No installation error was raised. The reason seed has exactly three rows:
`OWNER_REJECTED`, `OWNER_REVOKED`, and `SYSTEM_EXPIRED`.

The v3 SQL is not claimed to be idempotent; it has no `IF NOT EXISTS`. Repeat
installation was therefore not attempted and is `NOT_TESTED`.

## 4. Test matrix

| ID | Scenario | Result | Evidence |
|---|---|---|---|
| A1 | All v3 tables create | PASS | four `canary_owner_attestation*` tables |
| A2 | All indexes/partial indexes create | PASS | five named indexes + autoindexes |
| A3 | All 15 triggers create | PASS | 15 `trg_canary_*` triggers |
| A4 | Seed exactly once | PASS | `REASON_COUNT=3` |
| A5 | FK references resolve | PASS | `PRAGMA foreign_key_check=[]` |
| A6 | Repeat installation | NOT_TESTED | v3 does not claim idempotent install |
| B1 | Header creates one REQUESTED + pending state | PASS | counts `1,1,(pending)` |
| B2 | Second active same binding rejected | PASS | `UNIQUE state.binding_key` |
| B3 | Header-only orphan stays absent | PASS | failed request counts `(0,0,0)` |
| B4 | New generation after rejected | PASS | new header/state pending |
| B5 | New generation after expired | PASS | new header/state pending |
| B6 | New generation after consumed | PASS | new header/state pending |
| B7 | New generation after revoked | PASS | new header/state pending |
| B8 | Different semantic binding independent | PASS | independent header/state |
| B9 | State without header/request rejected | PASS | state insert guard error |
| B10 | Header/state binding mismatch rejected | PASS | state insert guard error |
| B11 | Duplicate same binding+generation rejected | PASS | header unique error |
| B12 | Failed bootstrap rolls back all rows | PASS | invalid chat counts `(0,0,0)` |
| C1 | `pending → accepted` | PASS | accepted event + state accepted |
| C2 | `pending → rejected` | PASS | rejected event + state rejected |
| C3 | `pending → expired` | PASS | expired event + state expired |
| C4 | `accepted → consumed` | PASS | consumed event + state consumed |
| C5 | `accepted → expired` | PASS | expired event + state expired |
| C6 | `accepted → revoked` | PASS | revoked event + state revoked |
| C7 | Accepted without request | PASS by bootstrap invariant | no state without `REQUESTED` |
| C8 | Consumption without acceptance | PASS | `invalid canary event transition` |
| C9 | Revocation after consumption | PASS | `invalid canary event transition` |
| C10 | `accepted → accepted` | PASS | `invalid canary event transition` |
| C11 | Direct state update without event | PASS | `invalid canary state transition` |
| C12 | Invalid from/to mapping | PASS | `invalid canary event transition` |
| C13 | Duplicate transition | PASS | second event rejected |
| C14 | Out-of-order/terminal transition | PASS | state/transition guard error |
| D1 | Event binding mismatch | PASS | `invalid canary event header/actor/reason` |
| D2 | Unknown reason code | PASS | header/actor/reason guard |
| D3 | Wrong actor for event | PASS | header/actor/reason guard |
| D4 | SYSTEM expiry event | PASS | expired event + state expired |
| D5 | Event UPDATE/DELETE | PASS | immutable trigger errors |
| D6 | Event without header | PASS | header/time guard error |
| D7 | Event timestamp malformed | PASS | `invalid canary event timestamp` |
| D8 | Failed projection update | NOT_TESTED | no safe runtime path to induce without disabling triggers |
| E1 | A2 exact bound review consumption | PASS | consumed event accepted |
| E2 | A2 different review | PASS | A2 guard error |
| E3 | A1 consume future review | PASS | consumed event accepted |
| E4 | A1 same review reused by second attestation | PASS | unique consumed review error; no consumed event |
| E5 | A1 reservation rollback | NOT_TESTED | no application reservation integration |
| F1 | Pending before expiry accepted | PASS | accepted at 12:10, expiry 12:15 |
| F2 | Pending at/after expiry accepted | PASS | timestamp error |
| F3 | Accepted before expiry consumed | PASS | consumed event accepted |
| F4 | Accepted at/after expiry consumed | PASS | timestamp error |
| F5 | Expiry event/projection | PASS | expired state/event |
| F6 | Revocation before consumption | PASS | revoked state/event |
| F7 | Revocation after consumption | PASS | transition error |
| F8 | Confirmation after expiry | PASS | timestamp/terminal error |
| F9 | Malformed/missing timestamp | PASS | timestamp guard error |
| F10 | Silent expiry extension | PASS | header immutable + no update |
| G1 | Duplicate active request | PASS | state unique |
| G2 | Duplicate confirmation | PASS | transition/unique error |
| G3 | Duplicate consumption same key | PASS | transition error; app maps existing |
| G4 | Consumption different key | PASS | transition/unique error |
| G5 | Two attestations same review | PASS | unique review error |
| H1 | Delete referenced creation job | PASS | FK error |
| H2 | Delete referenced review | PASS | FK error |
| H3 | Delete attestation/state | PASS | immutable/state delete error |
| H4 | Update immutable header field | PASS | immutable trigger error |
| H5 | Update parent ID | PASS | FK error |
| H6 | Update parent status | PASS (allowed) | application must revalidate |
| H7 | Delete reason code | PASS | reason immutable trigger |
| I1 | Two same-binding requests | PASS | one OK; one state unique |
| I2 | Two confirmations | PASS | one OK; one transition error |
| I3 | Confirmation vs expiry | PASS | ten state-aware races: final expired in all; both valid orderings observed |
| I4 | Two consumptions | PASS | one OK; one transition error |
| I5 | Two attestations same review | PASS | one OK; one unique review |
| I6 | Revocation vs consumption | PASS | one OK; one transition error |
| I7 | Busy lock | PASS | `OperationalError: database is locked` |
| I8 | Partial rollback | PASS | header/event/state counts `(0,0,0)` |
| T1 | Atomic consumption + review reservation | NOT_TESTED | no application integration; see §5 |

## 5. Actual errors and evidence

Representative exact errors:

```text
B_SECOND_ACTIVE_SAME_BINDING:
IntegrityError: UNIQUE constraint failed:
canary_owner_attestation_state.binding_key

B_INVALID_CHAT_ROLLBACK:
IntegrityError: CHECK constraint failed: chat_id = owner_user_id
B_INVALID_CHAT_COUNTS: (0, 0, 0)

C_ACCEPTED_ACCEPTED_INVALID:
IntegrityError: invalid canary event transition

C_CONSUME_WITHOUT_ACCEPT:
IntegrityError: invalid canary event transition

C_DIRECT_STATE_UPDATE:
IntegrityError: invalid canary state transition

D_BINDING_MISMATCH:
IntegrityError: invalid canary event header/actor/reason

D_UNKNOWN_REASON:
IntegrityError: invalid canary event header/actor/reason

D_WRONG_ACTOR:
IntegrityError: invalid canary event header/actor/reason

D_MALFORMED_TIMESTAMP:
IntegrityError: invalid canary event timestamp

E_A2_MISMATCH_CONSUME:
IntegrityError: A2 consumption review does not match bound_review_id

F_EXPIRED_PENDING_ACCEPT:
IntegrityError: invalid canary event timestamp

F_EXPIRED_ACCEPTED_CONSUME:
IntegrityError: invalid canary event timestamp

F_ACCEPT_AFTER_EXPIRED:
IntegrityError: invalid canary event timestamp

G_DUP_CONFIRMATION:
IntegrityError: invalid canary event transition

H_DELETE_CREATION_JOB:
IntegrityError: FOREIGN KEY constraint failed

H_DELETE_REVIEW:
IntegrityError: FOREIGN KEY constraint failed

H_DELETE_ATTESTATION:
IntegrityError: canary attestations are immutable

H_UPDATE_CREATION_JOB_ID:
IntegrityError: FOREIGN KEY constraint failed

I7_BUSY:
OperationalError: database is locked
```

### 5.1 Header/bootstrap evidence

```text
A_ROWS: (1, 1, ('pending',))
B_HEADER_ONLY_COUNT: (0, 0, 0)
B_INVALID_CHAT_COUNTS: (0, 0, 0)
B_AFTER_REJECT_STATE: ('rejected',)
B_NEW_GEN_AFTER_TERMINAL: OK
B_DIFFERENT_BINDING: OK
B_STATE_BINDING_MISMATCH: ERROR
canary state requires header and REQUESTED event
```

The bootstrap trigger creates exactly one `REQUESTED` event and one pending state row.
The active unique index rejects a second active binding, and a failed header insertion
leaves no header/event/state residue.

### 5.2 Transition evidence

`pending → accepted`, `pending → rejected`, `pending → expired`, `accepted → consumed`,
`accepted → expired`, and `accepted → revoked` all produced the expected event and state
projection. Invalid/out-of-order/duplicate transitions all raised a trigger error. No
failed transition left a partial event or inconsistent projection in the final rows.

### 5.3 Expiry and A2 evidence

- Pending accepted at `12:10` with `expires_at=12:15` succeeded.
- Pending accepted at `12:20` failed with the timestamp guard.
- Accepted consumed at `12:00` with `expires_at=12:15` succeeded.
- Accepted consumed at `12:20` failed with the timestamp guard.
- `EXPIRED` from pending/accepted at `12:20` succeeded.
- A2 with `bound_review_id=2` rejected `review_id=3` and accepted `review_id=2`.
- A1 with no bound review accepted the review created at consumption; a second
  attestation using the same review was rejected by `ux_canary_attestation_consumed_review`.

### 5.4 Idempotency/replay evidence

- Duplicate active request: state unique error.
- Duplicate confirmation: transition/unique error; no second accepted event.
- Duplicate consumption same or different operation key: transition/unique error; no
  second consumed event. The application must map this to the existing consumed result;
  SQLite does not return idempotent success automatically.
- Two attestations using one review: unique review error; no second consumption.
- Same-name repository identity remains indistinguishable under B1.

## 6. True concurrency evidence

Two separate connections to one disposable file, WAL, `foreign_keys=ON`,
`BEGIN IMMEDIATE`, barrier-synchronized starts:

```text
I1_CONCURRENT_REQUESTS:
(2, 'OK')
(1, 'IntegrityError: UNIQUE constraint failed:
    canary_owner_attestation_state.binding_key')

I2_CONCURRENT_CONFIRMATIONS:
(2, 'OK')
(1, 'IntegrityError: invalid canary event transition')

I4_CONCURRENT_CONSUME:
(1, 'OK')
(2, 'IntegrityError: invalid canary event transition')

I5_TWO_ATTESTATIONS_SAME_REVIEW:
(2, 'OK')
(1, 'IntegrityError: UNIQUE constraint failed:
    canary_owner_attestation_events.review_id')

I6_REVOCATION_CONSUMPTION_RACE:
(2, 'OK')
(1, 'IntegrityError: invalid canary event transition')

I7_BUSY:
OperationalError: database is locked

I8_ROLLBACK_COUNTS: (0, 0, 0)
```

The first confirmation/consumption/revocation winner is the only writer; the loser
fails before leaving a second event or inconsistent projection.

### 6.1 Confirmation versus expiry race

A state-aware expiry worker reads the current projection under `BEGIN IMMEDIATE` and
uses `from_state=pending` or `accepted` accordingly. Ten fresh headers produced:

```text
7x: expire OK from pending; accept IntegrityError
   final state: expired; events REQUESTED, EXPIRED

3x: accept OK; expire OK from accepted
   final state: expired; events REQUESTED, ACCEPTED, EXPIRED
```

Every run ended in `expired`, never `accepted` with a later rejected expiry. When
acceptance won first, it was before `expires_at`, so the later `accepted → expired`
transition was valid. When expiry won first, confirmation failed. No inconsistent
state/event pair remained.

### 6.2 Final rows from the concurrency DB

```text
FINAL_STATES:
[('attestation-0102-xxxx', 'pending'),
 ('attestation-0200-xxxx', 'accepted'),
 ('attestation-0300-xxxx', 'accepted'),
 ('attestation-0400-xxxx', 'consumed'),
 ('attestation-0500-xxxx', 'accepted'),
 ('attestation-0501-xxxx', 'consumed'),
 ('attestation-0600-xxxx', 'consumed')]

FINAL_EVENTS include:
attestation-0400: REQUESTED, ACCEPTED, CONSUMED
attestation-0501: REQUESTED, ACCEPTED, CONSUMED
attestation-0600: REQUESTED, ACCEPTED, CONSUMED
FINAL_FK_CHECK: []
```

The `0500` attestation lost the same-review race and retained only
REQUESTED+ACCEPTED; `0501` owns the consumed event.

## 7. Transaction and rollback evidence

- Header bootstrap: header + `REQUESTED` + pending state commit/rollback together.
- Invalid header (chat mismatch) left `(0,0,0)` rows.
- Active binding conflict left no header/event/state residue.
- Invalid transition events left the previous state unchanged and no new event.
- I8 explicit `BEGIN IMMEDIATE` multi-step block followed by rollback left
  header/event/state counts `(0,0,0)`.
- **Atomic consumption + review reservation + membership creation is NOT_TESTED**:
  this experiment has no application reservation implementation. I1 remains a
  documented application transaction, not a database guarantee.
- **Failed projection update is NOT_TESTED**: no safe runtime path was found to make the
  projection trigger fail without disabling the protection being tested. The trigger is
  statically present and the state guard is exercised indirectly by valid/invalid
  transitions.

## 8. SQLite-enforced versus application-enforced

| Guarantee | Runtime result | Where enforced |
|---|---|---|
| Exact v3 SQL installs | PASS | SQLite DDL |
| Tables/indexes/triggers/seed | PASS | SQLite DDL |
| Header creates initial request + pending state | PASS | bootstrap trigger |
| No header-only orphan | PASS | bootstrap + state insert guard + active index |
| One active binding | PASS | partial unique state index |
| Generation-only bypass | PASS | active state index |
| Allowed lifecycle transitions | PASS | table CHECK + transition guard + state guard |
| Terminal state transitions | PASS | transition/state guards |
| Event binding/owner/actor/reason | PASS | header/actor/reason guard + FK |
| Event timestamps/expiry | PASS | time guard |
| A2 exact bound review | PASS | A2 guard |
| One consumed review | PASS | partial unique index |
| Operation key uniqueness | PASS | partial unique index |
| Event/header/state append-only | PASS | immutable/delete triggers |
| FK audit retention | PASS | `ON DELETE RESTRICT` + triggers |
| Busy lock behavior | PASS | SQLite/WAL + `busy_timeout` |
| Atomic review reservation | NOT_TESTED | application I1 transaction required |
| Owner identity/authorization | not DB-proven | WP-01/application |
| A2 cycle authorization | not DB-proven | application revalidation |
| `binding_key` hash preimage | not DB-proven | application canonical computation |
| Same-name repository identity | impossible under B1 | no numeric ID; D-04b deferred |
| Same-key idempotent success | not automatic | application maps unique/transition errors |

SQLite enforces structural constraints and transition/event rules. It does not prove
external identity, owner authorization, A2 cycle authorization, or atomic review
reservation.

## 9. Findings

### V3-NOTE-1 — Atomic review reservation remains application-only

- **Invariant:** I1 consumption + review + membership atomicity.
- **Result:** NOT_TESTED; no application integration exists.
- **Correction:** implement in a separately authorized task with `BEGIN IMMEDIATE`.
- **V4 required?** No, for this schema; integration protocol remains required.

### V3-NOTE-2 — Failed projection update not directly induced

- **Invariant:** event rollback if projection update fails.
- **Result:** NOT_TESTED; no safe runtime path without disabling triggers.
- **Correction:** test during implementation with a controlled fault injection or a
  dedicated integration test.
- **V4 required?** No; static trigger path reviewed.

### V3-NOTE-3 — Idempotent success is application mapping

- **Invariant:** same-key retry returns the existing result.
- **Result:** database returns unique/transition error; it does not return success.
- **Correction:** application must query existing row after conflict and map it.
- **V4 required?** No; documented application requirement.

### V3-NOTE-4 — Canonical binding/PR JSON is application-enforced

- **Invariant:** semantic binding correctness and canonical PR set.
- **Result:** SQLite checks stored key/shape only; no hash preimage or PR ordering.
- **Correction:** application recomputes canonical fields under `BEGIN IMMEDIATE`.
- **V4 required?** No.

### V3-NOTE-5 — No separate system-invalidation event

- **Invariant:** system-originated audit distinction.
- **Result:** only `SYSTEM EXPIRED` exists; other system invalidation is not modeled.
- **Correction:** owner decision/new event reason if needed.
- **V4 required?** Only if owner requires additional invalidation semantics.

### V3-NOTE-6 — Installation is not idempotent

- **Invariant:** repeatable installation.
- **Result:** NOT_TESTED; v3 does not claim idempotent installation.
- **Correction:** application schema installer must create once or use its existing
  `IF NOT EXISTS` strategy in a future implementation.
- **V4 required?** No.

No critical exact-SQL execution failure, state-transition bypass, active-binding bypass,
event-integrity bypass, A2 bypass, expiry bypass, or audit-deletion bypass was observed.

## 10. Readiness for owner approval

The exact v3 SQL executes and the tested critical invariants pass. The remaining
untested items are application integration/atomic reservation and a deliberately induced
projection failure, plus documented application-only checks.

Therefore v3 is **technically validated with notes**, not approved. A v4 schema revision
is not required by the observed results.

## 11. Approval and status boundaries

**No owner approval or implementation authorization is granted by this validation.**
`OD-R7-D04-SCHEMA-01` remains `PENDING — NOT APPROVED`.

| Status | Value |
|---|---|
| Isolated SQLite validation | passed with notes |
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

B1 remains name-bound: no numeric repository ID, no backfill, same-name
deletion/recreation indistinguishable, D-04b deferred, WP-04 blocked.

## 12. Scope verification

- Application DB opened: **no**.
- Only disposable `/tmp/ohb2-d04-v3-*` databases used.
- Application DDL/schema/migration changed: **no**.
- Application code/config/tests changed: **no**.
- v3 design and historical v2 reports not edited.
- `git diff --check` → clean.
- Documentation parity: `pytest -q tests/test_doc_code_parity.py` → **16 passed**.
- Only this validation report and the additive `.agent/PROGRESS.md` entry were introduced.
- No commit, push, PR, merge, fetch, pull, deployment, release, external API call,
  Telegram delivery, worker activation, or Canary.
- Autopush disabled/inactive.

Report verdict: `WP02_D04_SCHEMA_V3_SQLITE_VALIDATED_WITH_NOTES`.
