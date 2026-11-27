# OHB2-R7 WP-02 / D-04 — Schema v2 Isolated SQLite Validation

**Task ID:** `OHB2-R7-WP02-D04-SCHEMA-V2-ISOLATED-SQLITE-VALIDATION`
**Date:** 2026-11-26
**Verdict:** `WP02_D04_SCHEMA_V2_NEEDS_REVISION`
**Review label:** `AUTHOR_SELF_REVIEW — NOT INDEPENDENT REVIEW`
**Current WP-02 status:** `WP02_D04_BLOCKED`
**`OD-R7-D04-SCHEMA-01`:** `PENDING — NOT APPROVED`

**Scope:** isolated SQLite experiment only. No application database was opened, no
application schema or migration was changed, and no application code, configuration,
tests, workers, Canary, or external services were touched.

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
| Untracked entries | 79 pre-existing |

Source hashes:

- v2 report: `80e596d79cfd1107c617dc8fa1723e833a86a9f5dc72d5a2e7b4ab33f5df4534`
- `bot/db.py`: `91b9e0282b767fc04a7d780e6714b2fc81e2424b55f0116b95bad75edf4841ff`

All pre-existing modifications and untracked files, including `.openhands/`, were
preserved. No fetch, pull, reset, clean, or history change was performed.

### 1.1 Final state after this report

| Item | Value |
|---|---|
| Branch / HEAD / tree | unchanged |
| Modified tracked | 12 (same pre-existing set) |
| Untracked | 80 (79 pre-existing + this report) |
| Application code / schema / migration / config / test changes | none |

## 2. SQLite test environment

- SQLite version: **3.46.1**
- Database: disposable file `/tmp/ohb2-d04-v2-tests-*/v2.sqlite3` and
  `/tmp/ohb2-d04-v2-concurrency-*/v2.sqlite3`.
- Every connection: `PRAGMA foreign_keys=ON` and read-back check = `1`.
- File database: `PRAGMA journal_mode=WAL`.
- `PRAGMA busy_timeout=5000` for normal tests; `1` ms for deliberate lock/busy test.
- Transactions: `BEGIN IMMEDIATE` for writes; rollback on exceptions.
- Parent fixture tables created only in the disposable database:
  `creation_jobs(id, chat_id, repo, conversation_id, status)` and
  `auto_reviews(id, conversation_id, chat_id, status)`. These are test fixtures, not
  application schema.
- No `Database(...)` production initialization was called and no project database path
  was opened.

## 3. Exact DDL tested and its source

Tested from
`docs/reviews/OHB2-R7-WP02-D04-SCHEMA-DESIGN-REVISION-V2-20261126.md`:

- §5 lines 223-299: exact `CREATE TABLE` statements for the three proposed tables and
  the three proposed indexes.
- §6.1 lines 308-328: exact append-only `BEFORE UPDATE`/`BEFORE DELETE` triggers.

The exact executed text for the three tables and three indexes was copied verbatim
from those lines; the exact append-only triggers were copied verbatim from §6.1. No
repair or semantic change was made. The only additional DDL in the disposable database
was the two parent fixture tables `creation_jobs` and `auto_reviews` needed to satisfy
foreign keys. The DDL is not duplicated here to avoid drift from the source report.

The v2 report does **not** contain exact executable SQL for:

- §6.2 event transition guard;
- §6.3 state projection trigger.

Those sections contain prose requirements only. Therefore the transition/projection
trigger tests are **NOT_TESTED for Schema v2 as written**; no invented trigger SQL was
reported as v2. The exact table/index/append-only DDL was executed as written.

### 3.1 DDL integrity result

Created successfully:

- `canary_owner_attestations`
- `canary_owner_attestation_events`
- `canary_owner_attestation_state`
- `ux_canary_attestation_active_binding`
- `ux_canary_attestation_operation`
- `ux_canary_attestation_consumed_review`
- five exact append-only triggers (`trg_canary_attestation_*`, `trg_canary_event_*`,
  `trg_canary_state_no_delete`)

`PRAGMA foreign_key_check` was empty after valid fixture rows. No DDL creation error
was observed.

## 4. Test scenario matrix

Legend:

- **PASS** — expected behavior observed.
- **FAIL** — actual behavior violates the intended invariant.
- **NOTE** — observation, not necessarily a blocker.
- **NOT_TESTED** — exact SQL is absent or application-only behavior was not executed.

| ID | Scenario | Result | Evidence |
|---|---|---|---|
| A1 | Create all three tables | PASS | tables listed |
| A2 | Create all indexes | PASS | three `ux_canary_*` indexes |
| A3 | Create exact append-only triggers | PASS | five `trg_canary_*` triggers |
| A4 | Foreign keys resolve/check | PASS | `PRAGMA foreign_key_check` empty |
| A5 | `chat_id != owner_user_id` rejected | PASS | `CHECK constraint failed: chat_id = owner_user_id` |
| A6 | Invalid `authorization_mode`/bound combination rejected | PASS | CHECK constraint failed |
| A7 | `pr_numbers_json='[]'` rejected as empty | **FAIL / weak** | accepted; only length 2-4096 is checked |
| A8 | Update/delete audit rows rejected | PASS | immutable trigger errors |
| B1 | First pending active binding | PASS | insert OK |
| B2 | Second pending same binding rejected | PASS | `UNIQUE ... state.binding_key` |
| B3 | Accepted remains active | PASS | second state pending rejected |
| B4 | New generation after rejected | PASS | insert OK |
| B5 | Different binding independent | PASS | insert OK |
| B6 | Header-only same binding without state | **FAIL** | accepted; DB cannot enforce active binding if state row is absent |
| B7 | Same binding + same generation duplicate | PASS | `UNIQUE(binding_key,generation)` |
| C1 | Accept without pending request | **FAIL** | direct event accepted |
| C2 | Consume without acceptance | **FAIL** | direct consumed event accepted |
| C3 | Revoke after consumption | **FAIL** | `REVOKED` accepted after consumed |
| C4 | Invalid from/to mapping | **FAIL** | `ACCEPTED accepted→accepted` accepted |
| C5 | Duplicate accepted event | PASS | unique `(attestation_id,event_type)` |
| C6 | Permitted transitions with exact v2 triggers | **NOT_TESTED** | exact trigger SQL absent |
| D1 | State pending→consumed without event | **FAIL** | direct state update accepted |
| D2 | Update header | PASS | immutable trigger error |
| D3 | Delete event | PASS | immutable trigger error |
| D4 | Update event | PASS | immutable trigger error |
| D5 | Delete state | PASS | state delete trigger error |
| D6 | Event binding_key mismatch | **FAIL** | mismatch accepted |
| D7 | Arbitrary reason code | **FAIL / weak** | `UNSAFE_REASON` accepted; only length checked |
| D8 | Failed transition leaves no event | **NOT_TESTED** | no exact transition trigger |
| E1 | Consume without review_id | PASS | CHECK constraint failed |
| E2 | Consume without operation_key | PASS | CHECK constraint failed |
| E3 | Valid consumption | PASS | insert OK |
| E4 | Duplicate consumption same review | PASS | unique review index |
| E5 | Another attestation same review | PASS | unique review index |
| E6 | A2 bound_review_id mismatch | **FAIL** | consumed with different review accepted |
| E7 | Same operation key on another attestation | PASS | allowed by `(attestation_id,operation_key)` |
| E8 | Duplicate same operation key | **NOT_TESTED** | separate run not performed; composite unique exists |
| E9 | Reservation + consumption atomicity | **NOT_TESTED** | no application reservation integration; see §5 |
| F1 | A1 structural binding (NULL review) | PASS | CHECK accepted PRE_CYCLE/NULL |
| F2 | A2 structural binding (non-NULL review) | PASS | CHECK accepted EXISTING_CYCLE/review |
| F3 | A2 cross-cycle reuse rejected | **FAIL** | no trigger; mismatch accepted |
| G1 | Expired pending cannot be accepted | **FAIL** | accepted event after expiry |
| G2 | Expired accepted cannot be consumed | **FAIL** | consumed event after expiry |
| G3 | Accept after `EXPIRED` event | **FAIL** | accepted after expired event accepted |
| G4 | Revocation after consumption | **FAIL** | see C3 |
| G5 | Concurrent expiry vs confirmation | **FAIL** | both events committed; state remained pending |
| H1 | Delete referenced creation job | PASS | `FOREIGN KEY constraint failed` |
| H2 | Delete referenced review | PASS | `FOREIGN KEY constraint failed` |
| H3 | Delete attestation with events | PASS | immutable trigger error |
| I1 | Lock/busy behavior | PASS | `database is locked` |
| I2 | Concurrent same-binding requests | PASS | one OK, one `UNIQUE state.binding_key` |
| I3 | Concurrent confirmation updates | **FAIL** | both updates OK; no event |
| I4 | Concurrent consumption | PASS | one OK, one unique review failure |
| I5 | Expiry race with confirmation | **FAIL** | both accepted/expired events committed |
| I6 | Partial rollback | PASS | header/event/state counts `(0,0,0)` |

## 5. Actual SQL errors and reproduction

### 5.1 Constraint tests

```text
A_CHECK_CHAT_MISMATCH:
IntegrityError: CHECK constraint failed: chat_id = owner_user_id

A_CHECK_MODE_BOUND:
IntegrityError: CHECK constraint failed:
(authorization_mode = 'PRE_CYCLE' AND bound_review_id IS NULL) OR
(authorization_mode = 'EXISTING_CYCLE' AND bound_review_id IS NOT NULL)

A_EMPTY_PR_JSON_PASSES_ACTUAL_CHECK:
RESULT=OK
```

The last result means the actual v2 DDL accepts `pr_numbers_json='[]'`; only the
`length(...) BETWEEN 2 AND 4096` check is database-enforced. Non-empty canonical JSON
remains application-enforced.

### 5.2 Active-binding tests

```text
B2_SECOND_PENDING:
IntegrityError: UNIQUE constraint failed: canary_owner_attestation_state.binding_key

B3_SECOND_WHILE_ACCEPTED:
IntegrityError: UNIQUE constraint failed: canary_owner_attestation_state.binding_key

B4_NEW_AFTER_REJECTED: OK

B6_HEADER_ONLY_NO_STATE_SAME_BINDING: OK
```

B6 is a defect: a second header for the same `binding_key` can exist without a state
row. Active uniqueness is enforced only if the application/trigger inserts the
projection row. The exact v2 report does not provide executable projection-trigger SQL.

### 5.3 Invalid transitions accepted

```text
C1_ACCEPT_WITHOUT_REQUESTED: OK
C2_CONSUME_WITHOUT_ACCEPT: OK
C3_REVOKE_AFTER_CONSUME: OK
C4_INVALID_MAPPING ACCEPTED accepted->accepted: OK
D1_STATE_PENDING_TO_CONSUMED: OK
D6_EVENT_BINDING_MISMATCH: ACCEPTED
D7_ARBITRARY_REASON_CODE: ACCEPTED
```

These are not protected by the exact v2 DDL. The v2 append-only triggers block
`UPDATE`/`DELETE`, but not invalid `INSERT`s or direct state updates. The transition
guard and projection trigger are requirements without exact executable SQL in the v2
report.

### 5.4 Consumption and A2

```text
E1_CONSUME_NO_REVIEW:
IntegrityError: CHECK constraint failed:
event_type <> 'CONSUMED' OR (review_id IS NOT NULL AND operation_key IS NOT NULL)

E2_CONSUME_NO_OPKEY:
IntegrityError: same CHECK constraint

E3_CONSUME_VALID: OK

E4_DUP_CONSUME:
IntegrityError: UNIQUE constraint failed:
canary_owner_attestation_events.review_id

E5_SECOND_ATTESTATION_SAME_REVIEW:
IntegrityError: UNIQUE constraint failed:
canary_owner_attestation_events.review_id

E6_A2_BOUND_REVIEW_MISMATCH: OK
E7_SAME_OPKEY_OTHER_ATTESTATION: OK
```

E6 is a defect: `CONSUMED` with `review_id=4` was accepted for an A2 attestation whose
`bound_review_id=2`. No exact v2 trigger enforces equality.

### 5.5 Expiry

```text
G1_EXPIRED_PENDING_ACCEPT: OK
G2_EXPIRED_ACCEPTED_CONSUME: OK
G3_ACCEPT_AFTER_EXPIRED: OK
```

All three are defects for the proposed lifecycle. The exact v2 DDL has no expiry
trigger; `expires_at` is only stored, not enforced by event insertion.

### 5.6 Foreign keys

```text
H1_DELETE_CREATION_JOB:
IntegrityError: FOREIGN KEY constraint failed

H2_DELETE_REVIEW:
IntegrityError: FOREIGN KEY constraint failed

H3_DELETE_ATTESTATION_WITH_EVENTS:
IntegrityError: canary attestations are immutable
```

Foreign-key restrictions and append-only triggers preserve audit history in these
cases. No cascade erased history.

### 5.7 Minimal reproduction patterns

The following are the exact shapes used in the disposable harness (values shown
generically; IDs and timestamps are test data):

```sql
-- C1: acceptance without a REQUESTED event; no transition trigger in exact v2
INSERT INTO canary_owner_attestation_events
  (attestation_id,binding_key,event_type,from_state,to_state,actor_type,actor_id,
   reason_code,operation_key,review_id,created_at,event_fingerprint)
VALUES ('att-20','<64hex>','ACCEPTED','pending','accepted','OWNER',7,
        NULL,NULL,NULL,'2026-11-26T12:00:00+00:00','<64hex>');
-- actual: OK; required: rejected.

-- D1: state transition without an event/projection trigger
UPDATE canary_owner_attestation_state
   SET status='consumed'
 WHERE attestation_id='att-20';
-- actual: OK; required: rejected.

-- E6: A2 bound review mismatch; no bound_review_id guard in exact v2
INSERT INTO canary_owner_attestation_events
  (attestation_id,binding_key,event_type,from_state,to_state,actor_type,actor_id,
   reason_code,operation_key,review_id,created_at,event_fingerprint)
VALUES ('att-32','<64hex>','CONSUMED','accepted','consumed','OWNER',7,
        NULL,'op32',4,'2026-11-26T12:00:00+00:00','<64hex>');
-- header has bound_review_id=2; actual: OK; required: rejected.

-- G1: accepted after fixed expiry; exact v2 does not compare created_at to expires_at
-- header expires_at = '2026-11-26T11:00:00+00:00'
INSERT INTO canary_owner_attestation_events
  (attestation_id,binding_key,event_type,from_state,to_state,actor_type,actor_id,
   reason_code,operation_key,review_id,created_at,event_fingerprint)
VALUES ('att-40','<64hex>','ACCEPTED','pending','accepted','OWNER',7,
        NULL,NULL,NULL,'2026-11-26T12:20:00+00:00','<64hex>');
-- actual: OK; required: rejected.
```

These failures are DDL/trigger-completeness failures. They are not attributed to the
application because no application transition code was executed or implemented.

## 6. Concurrency evidence

Using separate connections to one disposable file, WAL, `foreign_keys=ON`,
`BEGIN IMMEDIATE`, and a barrier for simultaneous starts:

```text
I1_BUSY:
OperationalError: database is locked

I2_CONCURRENT_REQUESTS:
(2, 'OK')
(1, IntegrityError: UNIQUE constraint failed: canary_owner_attestation_state.binding_key)

I3_CONCURRENT_CONFIRM_UPDATES:
(2, 'OK')
(1, 'OK')

I4_CONCURRENT_CONSUME:
(1, 'OK')
(2, IntegrityError: UNIQUE constraint failed: canary_owner_attestation_events.review_id)

I5_EXPIRY_RACE_CONFIRM:
(2, 'OK')
(1, 'OK')

I6_ROLLBACK_COUNTS: (0, 0, 0)
```

Final rows after the concurrency experiment:

```text
FINAL_STATE_ROWS:
[('attestation-0102-xxxx', 'pending'),
 ('attestation-0200-xxxx', 'accepted'),
 ('attestation-0300-xxxx', 'accepted'),
 ('attestation-0400-xxxx', 'pending')]

FINAL_EVENT_ROWS:
[('attestation-0300-xxxx', 'CONSUMED', 'accepted', 'consumed'),
 ('attestation-0400-xxxx', 'EXPIRED', 'pending', 'expired'),
 ('attestation-0400-xxxx', 'ACCEPTED', 'pending', 'accepted')]
```

Interpretation:

- I2: state partial unique index serializes same-binding requests correctly **when a
  state row is written**.
- I3: both confirmation updates succeed because exact v2 has no state-update guard and
  no event projection trigger; no accepted event was created.
- I4: consumed review uniqueness prevents double consumption.
- I5: both expiry and acceptance events commit; final state remains pending and both
  events exist because exact v2 has no transition/projection trigger; this is an
  inconsistent final state.
- I6: explicit transaction rollback removed header, event, and state together.

## 7. SQLite-enforced versus application-enforced

| Guarantee | Enforced by exact v2 SQLite DDL? | Required additional enforcement |
|---|---|---|
| Table/index/append-only DDL validity | Yes | None for created objects |
| `chat_id = owner_user_id` | Yes | None |
| authorization mode/cycle shape | Yes | None |
| non-empty canonical PR JSON | No | Application canonicalization/validation |
| one active attestation per binding | Only when state row exists | State insert must be atomic; exact v2 projection trigger SQL missing |
| valid state transition | No | Exact `BEFORE INSERT` event trigger + state trigger needed |
| `from_state`/`to_state` match | No | Trigger/application |
| binding_key matches header | No | Trigger/application |
| safe reason code allowlist | No | Closed enum/application validation |
| consumed requires review and operation key | Yes | CHECK |
| one consumed event per attestation | Yes | `UNIQUE(attestation_id,event_type)` |
| one review per consumed event | Yes | partial unique review index |
| A2 bound review equality | No | Trigger/application |
| expiry rejection | No | Trigger/application |
| revocation after consumption | No | Trigger/application |
| append-only event rows | Yes for UPDATE/DELETE | Not for INSERT; trust boundary for file access |
| atomic reservation+consumption | No (not integrated) | Application transaction |
| concurrent same-binding one winner | Yes when state row inserted | State projection must be mandatory |
| concurrent confirmation one winner | No | Trigger/application |

## 8. Identified defects and proposed corrections

### D1 — Missing executable transition/projection triggers (blocking)

- **Invariant:** F2 lifecycle and F1 state projection.
- **Observed:** C1-C4, D1, G1-G3, I3, I5.
- **Cause:** v2 report describes triggers but does not provide exact SQL.
- **Correction:** Add exact `BEFORE INSERT` event guard, `AFTER INSERT` state
  projection, `BEFORE INSERT` state guard, and `BEFORE UPDATE` state transition trigger;
  test them as part of a new revision. Another schema/design revision is required.

### D2 — Header without state bypasses active uniqueness (blocking)

- **Invariant:** F1.
- **Observed:** B6 accepted a second header for the same binding with no state row.
- **Cause:** no mandatory state insertion / projection trigger; partial unique index
  applies only to state rows.
- **Correction:** Make state creation atomic with `REQUESTED` and reject headers
  without valid `REQUESTED`+state projection. Exact trigger SQL is required.

### D3 — A2 bound review equality is not enforced (blocking for A2)

- **Invariant:** A2 cross-cycle reuse.
- **Observed:** E6 accepted a consumed event with a different review ID.
- **Cause:** no exact trigger for `bound_review_id`.
- **Correction:** Add event guard enforcing `review_id = header.bound_review_id` when
  the header mode is `EXISTING_CYCLE`.

### D4 — Expiry and revocation ordering are not enforced (blocking)

- **Invariant:** lifecycle and expiration.
- **Observed:** G1-G3, C3, I5.
- **Cause:** no exact event trigger comparing timestamps/state.
- **Correction:** Add trigger checks for `created_at < expires_at` for
  `ACCEPTED`/`CONSUMED`, `created_at >= expires_at` for `EXPIRED`, and reject any
  event after a terminal state.

### D5 — Event binding and reason validation are weak (needs correction)

- **Invariant:** F3 audit integrity.
- **Observed:** D6 mismatch and D7 arbitrary reason accepted.
- **Cause:** event `binding_key` and `reason_code` have length checks only.
- **Correction:** Trigger/application checks for header binding equality and a closed
  safe reason-code allowlist.

### D6 — PR JSON emptiness is only application-enforced (note)

- **Invariant:** exact explicit PR set.
- **Observed:** `[]` accepted by the DDL.
- **Cause:** only length check.
- **Correction:** Keep application canonicalization; consider a stricter JSON
  shape/non-empty check if SQLite JSON support is acceptable.

### D7 — Reservation integration is untested (note)

- **Invariant:** atomic consumption + review reservation.
- **Status:** NOT_TESTED; exact v2 is schema-only and no application integration exists.
- **Correction:** implement in a future authorized task using `BEGIN IMMEDIATE` and the
  existing reservation transaction; do not claim this experiment proves it.

## 9. Is Schema v2 technically ready for owner approval?

**No.** The exact table/index/append-only DDL is executable; the exact transition and
state-projection SQL required for F1/F2/F3/G is not present in v2. The experiment shows
the exact v2 DDL accepts invalid transitions, expiry violations, A2 cross-cycle reuse,
and a header without state. This is a design-completeness defect, not merely an
application integration gap.

The design direction (binding key + state projection + append-only events) is viable,
but v2 needs a precise trigger specification and a re-run. This report does not approve
Schema v2.

## 10. No approval or implementation authorization

No owner approval was granted by this validation. `OD-R7-D04-SCHEMA-01` remains
`PENDING`. No implementation, migration, schema, application integration, worker,
Canary, or external operation is authorized.

## 11. Status boundaries

| Status | Value |
|---|---|
| Isolated SQLite test | performed on disposable `/tmp` DB; no application DB |
| Application integration | not attempted |
| Owner schema approval | `PENDING` |
| Implementation authorization | absent |
| Independent review | deferred/not present |
| D-04b | `DEFERRED` and untouched |
| WP-02 | `WP02_D04_BLOCKED` |
| WP-04 | `WP04_D06_BLOCKED` |
| WP-05 / WP-06 | not started / live Canary blocked |
| B1 | `APPROVED` only for name-bound/no-numeric-ID scope |
| Working tree vs committed | local working-tree only |
| Published | unpublished |

B1 remains limited: no numeric repository ID, no creation-time identity, no backfill,
same-name deletion/recreation indistinguishable, D-04b deferred, WP-04 blocked.

## 12. Verification and scope control

- Application DB opened: **no**.
- Application schema/migration changed: **no**.
- Application code/config changed: **no**.
- Tests added/modified: **no**.
- DDL execution confined to disposable `/tmp/ohb2-d04-v2-*` files.
- `git diff --check` → clean.
- Documentation parity: `pytest -q tests/test_doc_code_parity.py` → **16 passed**.
- Only this report and the additive `.agent/PROGRESS.md` entry were introduced.
- No commit, push, PR, merge, fetch, pull, deployment, release, GitHub/OpenHands/
  provider API call, Telegram delivery, worker activation, or Canary.
- Autopush disabled/inactive.

Report verdict: `WP02_D04_SCHEMA_V2_NEEDS_REVISION`.
