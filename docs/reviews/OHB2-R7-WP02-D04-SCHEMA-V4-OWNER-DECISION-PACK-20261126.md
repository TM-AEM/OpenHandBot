# OHB2-R7 WP-02 / D-04 — Schema v4 Owner Decision Pack

**Task ID:** `OHB2-R7-WP02-D04-SCHEMA-V4-OWNER-DECISION-PACK`
**Date:** 2026-11-26
**Verdict:** `READY_FOR_OWNER_DECISION`
**Decision requested:** `OD-R7-D04-SCHEMA-01`
**Recommendation:** **CONDITIONAL APPROVAL** of the Schema v4 design, with the
conditions in §10. This is advisory only; the owner retains the decision.

**This package does not grant or record an owner decision, implementation
authorization, migration authorization, or operational authorization.**

## 1. Executive decision summary

### 1.1 What is being decided

The owner is asked whether to:

1. **APPROVE** the Schema v4 design.
2. **REJECT** the Schema v4 design.
3. **REQUEST SPECIFIC REVISIONS** before deciding.

The v4 design proposes an additive SQLite storage model for D-04 Canary owner
attestation. It has been executed only in disposable isolated SQLite databases. It
has not been implemented in the application and is not production-ready.

### 1.2 Recommendation

**CONDITIONAL APPROVAL**, not unconditional approval as-is.

The schema-level corrections for the v3 findings F01–F06 are supported by executed
evidence. The remaining material risks are application integration, missing
idempotent installation/recovery, and the pending AUTH/LIFECYCLE/INTEGRATION owner
decisions. These are not a reason to declare the logical schema invalid, but they are
reasons not to treat the design as implementation-ready or migration-ready.

### 1.3 What is verified and what is not

| Layer | Status |
|---|---|
| Design correctness (v3 F01–F06 addressed) | Supported within the stated SQL/application boundary |
| Isolated SQL validation | Clean install and selected adversarial cases independently re-executed from the report SQL; remaining cases `REPORTED_ONLY` |
| Application integration | `APPLICATION_NOT_IMPLEMENTED`; `APPLICATION_INTEGRATION_NOT_TESTED` |
| Migration/installation safety | **FAIL for repeat/partial recovery**; one-shot clean install only |
| Independent review | `INDEPENDENT_REVIEW_NOT_PERFORMED` |
| Production readiness | **Not established** |

### 1.4 Decision bottom line

The logical v4 design is a reasonable basis for an owner design decision. It is **not**
approved for implementation or migration by this pack. The owner should approve the
design only conditionally on the installer/recovery protocol and application
integration prerequisites, or request a revision if those conditions are unacceptable.

## 2. Verified baseline and evidence references

### 2.1 Current Git state

Recorded before creating this package:

| Item | Value |
|---|---|
| Repository | `/workspace/project/OpenHandBot` |
| Branch | `agent/r6-review-delivery` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `origin/main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| HEAD tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| Modified tracked | 12 pre-existing; 11 application files unchanged, `.agent/PROGRESS.md` additive |
| Untracked | 84 at baseline; 85 final (this report added) |
| Application DB opened | no |

No fetch, pull, reset, clean, checkout over changes, or history change was performed.
All pre-existing modified and untracked files, including `.openhands/`, were preserved.

### 2.2 Primary evidence

- **v4 design and validation report:**
  `docs/reviews/OHB2-R7-WP02-D04-SCHEMA-DESIGN-REVISION-V4-20261126.md`
  (report SHA-256 `ca6d6292d03c4ed036b952dbde0e4528b6dde79df19975b12b749d2709494c54`).
- **v4 exact SQL SHA-256:**
  `d1731c077c72d022820a5fcfa331525cab3db399e8946a4074f9d3b70c8e75a4`
  (365 lines; extracted from the v4 report).
- **v3 isolated validation:**
  `docs/reviews/OHB2-R7-WP02-D04-SCHEMA-V3-ISOLATED-SQLITE-VALIDATION-20261126.md`.
- **v3 independent review:**
  `docs/reviews/OHB2-R7-WP02-D04-SCHEMA-V3-INDEPENDENT-REVIEW-20261126.md`.
- **B1 approval/remaining decisions:**
  `docs/reviews/OHB2-R7-WP02-D04-B1-OWNER-APPROVAL-AND-REMAINING-DECISIONS-20261126.md`.
- **Attestation storage design resolution:**
  `docs/reviews/OHB2-R7-WP02-D04-ATTESTATION-STORAGE-DESIGN-RESOLUTION-20261126.md`.
- **R7 owner decision records:** `docs/reviews/OHB2-R7-OWNER-DECISIONS-PACK-20261125.md`
  §11 and `docs/reviews/OHB2-R7-APPROVED-DECISIONS-IMPLEMENTATION-PLAN-20261126.md`.
- **Project rules:** `AGENTS.md`.
- **Application architecture read-only:** `bot/db.py` (WAL, `busy_timeout=5000`,
  fail-closed `PRAGMA foreign_keys=ON`, `_init_schema`, `BEGIN IMMEDIATE`, review
  reservation/membership conventions).

### 2.3 Evidence classification

- `INDEPENDENTLY_REEXECUTED`: this owner-pack audit extracted the exact v4 SQL from
  the report and reran it in a fresh disposable SQLite database for the selected
  cases listed in §3.
- `REPORTED_ONLY`: accepted from the v4 report matrix, not rerun by this pack.
- `SOURCE_CONFIRMED`: confirmed by source inspection.
- `APPLICATION_NOT_TESTED`: no application path exists or was exercised.
- `INDEPENDENT_REVIEW_NOT_PERFORMED`: no third-party review was performed.

The v4 report itself is an **author self-review**, not a third-party review. This
pack is also a documentation review by the same agent.

### 2.4 Independent audit performed for this package

Fresh database: `/tmp/ohb2-owner-pack-*` (not application DB). Environment: SQLite
3.46.1, `PRAGMA foreign_keys=ON` read-back 1, WAL, `busy_timeout=5000`, exact v4 SQL
from the report.

Observed:

```text
SQL_SHA256 d1731c077c72d022820a5fcfa331525cab3db399e8946a4074f9d3b70c8e75a4
INSTALL (7 tables, 27 triggers, FK [])
BOOT (1 REQUESTED, pending)
A1_LINK [(1,)]
F01_OR_IGNORE ERROR invalid or competing canary header; target (0,0,0)
F02_OR_REPLACE ERROR invalid or competing canary header; base pending, target 0
F03_EARLIER ERROR invalid canary event timestamp; state accepted
F03_TIE OK
F04_BINDING_2_SAME_FIELDS_DIFF_KEY ERROR canary binding already exists
F05_WRONG_CHAT ERROR review parent/membership mismatch; state accepted
I1_EXACT OK; review 1, memberships 2, consumed 1, link 1
FINAL_FK []
```

The exact SQL was also rechecked for repeat/partial behavior:

```text
REPEAT ERROR OperationalError: table canary_owner_attestation_reason_codes already exists
PARTIAL_TABLES [canary_owner_attestation_bindings, canary_owner_attestation_reason_codes]
PARTIAL_RECOVERY ERROR OperationalError: table canary_owner_attestation_reason_codes already exists
AFTER_PARTIAL_TABLES 2
```

These are reproduced limitations, not inferred limitations.

## 3. Schema correctness assessment

### 3.1 F01 — `INSERT OR IGNORE` orphan creation

**Assessment: PASS within the tested SQL boundary.**

v4 adds a `BEFORE INSERT` header guard that rejects an active binding, a duplicate
`(binding_key,generation)`, and a non-`MAX+1` generation. The bootstrap trigger inserts
the `REQUESTED` event and state, then raises if the state is absent. The state insert
guard requires exactly the initial `REQUESTED` event and a matching timestamp.

Independently observed: `INSERT OR IGNORE` on an active header produced
`invalid or competing canary header`; target counts `(0,0,0)`; base remained pending.
Same-generation and `ON CONFLICT DO NOTHING/UPDATE` header attempts were also blocked
in the v4 reported matrix and the active cases were independently rechecked.

**No schema-level orphan path was observed.** The application must not bypass the
single header/bootstrap API; that is an implementation conformance condition, not a
missing schema guard.

### 3.2 F02 — `INSERT OR REPLACE` implicit deletion

**Assessment: PASS within the tested SQL boundary.**

The header guard rejects the new-generation/active case before replacement can remove
the old state. State insertion accepts only the initial pending projection with
exactly one `REQUESTED` event; a direct replace of a terminal state is rejected.
`UPDATE OR REPLACE`, `ON CONFLICT DO UPDATE`, and direct state/event/PR/link conflict
forms were exercised or source-confirmed with `RAISE(ABORT)`/immutability guards.

Independently observed: `INSERT OR REPLACE` active header produced the header guard
error; base state remained `pending`; target header count was 0. The v4 matrix records
state-replace, event, PR, link, and binding conflict cases as guarded.

**Residual limitation:** SQLite cannot prohibit every possible direct DML form if a
future code path mutates a table with a conflict clause in a way not covered by the
guards. The tested forms are listed in §7; the implementation must use normal
`INSERT`/`UPDATE` APIs and must not use `OR REPLACE`/`OR IGNORE` on lifecycle tables.

### 3.3 F03 — event timestamp chronology

**Assessment: PASS for tested chronology cases; one claimed boundary case is not
fully independently rerun.**

v4 fixes a single format: `YYYY-MM-DDTHH:MM:SS.ffffffZ`, UTC, six fractional digits.
The SQL checks the shape, uses `julianday` validity, requires `REQUESTED.created_at =
requested_at`, and rejects an event earlier than the latest prior event. Equal
timestamps are allowed (nondecreasing policy).

Independently observed: accepted `12:10` then consumed `12:05` was rejected and state
remained accepted; equal-timestamp consumed was accepted; malformed timestamp was
rejected in the earlier v4 matrix. The v4 report's full before/at/after expiry matrix
was not all independently rerun by this pack (`REPORTED_ONLY`).

**Remaining limitation:** application clock generation and timezone construction are
application responsibilities. The schema validates supplied text, not clock truth.

### 3.4 F04 — canonical binding identity

**Assessment: PASS for the semantic registry and fixed vectors; SHA preimage is
application-enforced.**

v4 specifies the 13-field canonical object, NFC/UTF-8 normalization, repository
parsing/casefold, PR sorting/uniqueness, canonical JSON separators, and SHA-256
lowercase output. Fixed vector A is
`bab74402ba66e19cee3a37973dc0cdb4e2165daac18e6cac3a759035e8801513`; A2 is
`eba014997f71a8899e1939933c2ed2eaa46ae9a7761d05458c27f9caddee75ef`; distinct
PR/repo/owner vectors are distinct.

The SQL `canary_owner_attestation_bindings` table has a unique semantic tuple and a
header guard requiring the header fields to match it. Independently, two binding rows
with the same stored fields and different proposed keys were rejected
(`canary binding already exists`); a distinct semantic binding was allowed.

**Enforcement boundary:** SQLite does not compute SHA-256 and cannot prove that a
64-hex value is the hash of the field tuple. The future application must use exactly
the specified one-helper contract. No database fixture can prove application
canonicalization correctness; that is `APPLICATION_NOT_TESTED`.

**Residual schema ambiguity:** the semantic unique index operates on stored raw
fields. Equivalent case/Unicode/PR-order variants must be normalized before storage by
the one helper; otherwise the database sees different tuples. This is explicitly an
application contract, not a claim of database-level canonical equivalence.

### 3.5 F05 — A1/A2 parent-cycle ownership and membership

**Assessment: PARTIAL database enforcement, with mandatory application checks.**

The v4 review-link trigger requires:

- parent conversation ID, chat ID, repository full name, `reserved` status, and
  conversation scope;
- A1 null bound review or A2 exact `bound_review_id`;
- exact nonempty PR child rows equal all parent `auto_review_memberships` for the
  review/repository, with no missing or extra membership.

Independently observed: wrong chat, wrong bound review, missing PR rows, wrong
conversation, wrong repository, and wrong PR membership were rejected by the link
trigger; exact A1/A2 links succeeded. The parent `review_links` row is immutable and
unique per review; consumed-event insertion is the only normal path.

**Not database-enforced:**

- `creation_job_id`: `auto_reviews` does not contain it. Application must compare
  the D-01 B creation job with the reservation context.
- Current owner beyond `chat_id = owner_user_id`: application must revalidate current
  `Config.owner_id`, watched row, deletion, and ownership.
- Exact PR source synchronization between `pr_numbers_json`, the PR child table, and
  the resolved PR set. If the application populates inconsistent values, SQL may not
  detect the mismatch before/alongside the link.
- Current repository/GitHub identity, D-05 rename/transfer, D-06 flags, same-name
  recreation.
- Mutable parent fields after the link snapshot; application revalidation remains
  necessary.
- One-PR Canary and pending-membership merging.

**Assessment:** F05 is **not fully closed at the database level**. It is a correct
database subset plus a mandatory application boundary. The owner must not read the
v4 report as proof that arbitrary parent cycles are impossible without application
integration.

### 3.6 F06 — validation coverage

**Assessment: materially improved, but not fully independent.**

The v4 report now includes conflict clauses, chronology, canonical vectors, parent
mismatch, I1 fixture transactions, concurrency, and install/repeat/partial cases. The
v3 validation's missing cases are addressed in the report.

However, this owner pack independently re-executed only the selected cases in §2.4.
The remaining v4 matrix entries are `REPORTED_ONLY` or `SOURCE_CONFIRMED`, and the
full application integration is `APPLICATION_NOT_TESTED`. No third-party independent
review exists.

### 3.7 Active binding uniqueness, event/state/append-only, foreign keys

- **Active binding uniqueness:** schema registry + active state index/header guard
  tested; active twins blocked. Within stored semantic fields, PASS.
- **Event/state consistency:** state projection is guarded by latest-event matching;
  direct state updates/invalid transitions rejected in the v4 matrix and selected
  cases.
- **Append-only:** header/binding/event/PR/reason/review-link update/delete triggers
  and conflict guards; selected append-only tests passed.
- **Foreign keys:** fail-closed FK connection; linked parent deletion restrictions;
  `PRAGMA foreign_key_check` empty in tested DBs. Parent non-key fields remain mutable
  (application revalidation).
- **Consumed-review uniqueness/operation:** unique indexes and duplicate guards;
  concurrency/duplicate tests supported, with the fixture transaction caveat.

### 3.8 Remaining schema-level findings

No verified F01/F02/F03 schema-level bypass remains within the tested SQL boundary.
The following remain **ambiguities or application-dependent correctness conditions**:

1. SHA preimage/canonicalization cannot be verified by SQL.
2. PR JSON/child/P R selection synchronization is application-only.
3. Creation-job/owner/current GitHub/D-05/D-06 parent validity is application-only.
4. Mutable parent rows can become stale after the link snapshot.
5. The one-shot installer has no state/version/recovery semantics.
6. SQLite conflict forms are guarded for tested paths, but no formal proof covers all
   possible direct DML; implementation must use normal insert/update APIs.

These are not to be hidden as "schema defects" where they are architecture boundaries,
nor excused as "implementation details" where they are required security controls.

## 4. F01–F06 remediation assessment

| Finding | Schema status | Evidence | Remaining condition |
|---|---|---|---|
| F01 orphan from `INSERT OR IGNORE` | Corrected at SQL boundary | Header guard + bootstrap state-presence check + state insert guard; active case independently rerun `(0,0,0)` | Normal insert/UPSERT API must be used; no arbitrary OR IGNORE path |
| F02 state deletion from `INSERT OR REPLACE` | Corrected at SQL boundary | Header active guard before REPLACE; state guard; base state preserved in independent rerun | Direct conflict DML outside tested forms remains an implementation restriction |
| F03 event chronology | Corrected for supplied timestamps | Fixed format, `julianday`, latest-event nondecreasing guard; earlier rejected, tie accepted | Application must produce canonical UTC timestamps; full expiry matrix `REPORTED_ONLY` |
| F04 canonical binding | Corrected for stored semantic tuple; hash application-only | 13-field contract, fixed vectors, semantic registry, header/binding guards; same-field/different-key rejected | SHA preimage/canonical variants require one application helper; not tested in app |
| F05 parent-cycle checks | Partially DB-enforced | Review-link trigger checks conversation/chat/repo/status/scope/exact PR membership; wrong parent cases rejected | `creation_job_id`, current owner, GitHub/D-05/D-06, PR-source synchronization, mutable parent currentness, one-PR/pending merge are application-only |
| F06 validation gaps | Materially improved, not independent | New conflict/chronology/canonical/parent/I1/concurrency/install matrix | Selected subset independently re-executed; remainder `REPORTED_ONLY`; no third-party review |

### 4.1 Material correction vs. boundary

F01/F02/F03 corrections are real schema guards. F04/F05 are **correct schema support
plus mandatory application controls**. Treating F04/F05 as fully solved by SQL would be
misleading.

## 5. Application-enforced guarantees and testing gaps

| Guarantee | v4 specification | Database can enforce? | Integration status |
|---|---|---|---|
| Canonical `binding_key` generation | Fully specified in v4 §7 (fields, NFC, JSON, SHA-256 vectors) | No: SQLite cannot hash/prove preimage; semantic registry only compares stored fields | `APPLICATION_NOT_TESTED` |
| Current-owner revalidation (`Config.owner_id`, watched, deletion) | Referenced to WP-01/D-03; not implemented in v4 SQL | No | Not tested |
| Exact `creation_job_id` linkage | Required in v4 §9.3; parent table lacks the column | No | Not tested |
| GitHub numeric/full-name/current identity | Required by D-01/D-05/D-06; external | No | Not tested; no provider call |
| Exact PR-set source between header JSON, PR child, and resolved PRs | Canonical JSON/PR child specified; synchronization requirement stated | Partially: child-vs-membership link check; JSON/child sync not DB-enforced | Not tested |
| One-PR Canary restriction | Not defined in v4; application reservation policy | No | Not tested |
| Pending-membership rejection/no merge | Not defined in v4; application reservation policy | No | Not tested |
| A1/A2 current authorization | Modes represented; link checks mode/bound ID; owner/current revalidation external | Partially | Not tested |
| I1 actual `reserve_conversation_review` integration | Transaction design specified; fixture only | No | `APPLICATION_INTEGRATION_NOT_TESTED` |
| Owner/Telegram callback, statement text, confirmation UX | Not part of v4 schema | No | Not implemented |
| TTL and system-invalidation semantics | Pending `OD-R7-D04-LIFECYCLE-04` | No | Not selected/tested |
| Idempotent error-to-result mapping | Application requirement; schema returns errors | No | Not tested |
| Audit export/redaction/secret handling | Application boundary | No | Not tested |

### 5.1 Consequence

A database fixture PASS does **not** prove that the application will use the helper,
populate the exact PR child rows, revalidate owner/current linkage, reject pending
memberships, or integrate reservation and consumption atomically. Those are mandatory
WP-02 implementation tests, not optional polish.

## 6. Installation and migration safety analysis

### 6.1 Observed behavior

- Clean exact install: PASS (7 tables, 27 triggers, 6 named indexes, 3 seeds, FK empty).
- Re-running exact SQL: **FAIL** — `table canary_owner_attestation_reason_codes already exists`.
- Partial prefix install: leaves `canary_owner_attestation_bindings` and
  `canary_owner_attestation_reason_codes`.
- Running full SQL after partial install: **FAIL** on the existing reason table; no
  recovery, no automatic repair.
- No idempotent installer, schema-version record, partial-state detection, or rollback
  protocol has been validated.

### 6.2 Is this a blocker to approving the schema design?

**No, not to the logical design decision**, if the owner treats approval as a design
decision only. The additive tables/triggers create the intended schema on a clean
database; F01–F06 are addressed within the stated boundary.

### 6.3 Is it a blocker before implementation?

**Yes, mandatory implementation prerequisite.** A future implementation cannot ship
the exact SQL as a blind one-shot installer. The implementation authorization must
include:

- a schema-version record and expected object inventory/hash;
- explicit `BEGIN IMMEDIATE` transactional installation;
- preflight detection of partial/unknown schemas;
- rollback/cleanup or a documented recovery/upgrade path;
- idempotent seed handling and trigger/index completeness checks;
- fail-closed behavior if any object is missing, unexpected, or different;
- tests for clean, repeat, interrupted/partial, and recovery paths.

Adding `IF NOT EXISTS` everywhere is **not sufficient** by itself: it can leave stale
or differently defined triggers/indexes, hide a partial previous install, skip seed
repair, and fail to detect schema drift. It may be part of a versioned installer, not
a substitute for one.

### 6.4 Is it a blocker before migration or operational use?

**Yes.** Partial installation cannot be migrated or operated safely. No application
database may be touched until the installer/recovery protocol is implemented and
verified.

### 6.5 Safest sequencing

1. Owner design decision on `OD-R7-D04-SCHEMA-01`.
2. Independent review if required.
3. Resolve `AUTH-03`, `LIFECYCLE-04`, `INTEGRATION-05`.
4. Separate implementation authorization with installer/migration plan.
5. Implement and test installer on disposable DBs; verify clean/repeat/partial/recovery.
6. Implement application canonical/parent/I1 integration; test.
7. Separate migration authorization, then operational use; no Canary/worker until
   separately authorized.

## 7. Validation coverage matrix

Legend: `PASS` observed; `FAIL` observed violation; `NOT_TESTED` absent/unsafe to
execute; `APPLICATION_NOT_TESTED` no application path; `REPORTED_ONLY` v4 report
claim not rerun by this pack; `SOURCE_CONFIRMED` source inspection only.

| Area | Reported result | Evidence | Remaining limitation |
|---|---|---|---|
| Clean exact v4 install | PASS | `INDEPENDENTLY_REEXECUTED`: 7 tables, 27 triggers, FK `[]` | One-shot only |
| Repeat install | **FAIL** | `INDEPENDENTLY_REEXECUTED`: reason table already exists | No idempotent installer |
| Partial install/recovery | **FAIL** | `INDEPENDENTLY_REEXECUTED`: 2 tables left; full rerun fails | No recovery/rollback protocol |
| Normal A1 bootstrap | PASS | `INDEPENDENTLY_REEXECUTED`: 1 REQUESTED, pending state | Application API not implemented |
| F01 `INSERT OR IGNORE` active | PASS | `INDEPENDENTLY_REEXECUTED`: error; target `(0,0,0)` | Other direct conflict forms `REPORTED_ONLY` |
| F02 `INSERT OR REPLACE` active | PASS | `INDEPENDENTLY_REEXECUTED`: error; base pending; target absent | Exhaustive direct-DML proof absent |
| F03 earlier consumed | PASS | `INDEPENDENTLY_REEXECUTED`: timestamp error; state accepted | Full expiry-boundary matrix `REPORTED_ONLY` |
| F03 equal timestamp | PASS | `INDEPENDENTLY_REEXECUTED`: consumed accepted (tie allowed) | Policy must be acceptable to owner |
| F03 malformed timestamp | PASS | v4 report matrix | `REPORTED_ONLY` in this pack |
| F04 fixed canonical vectors | PASS | Helper calculations; SHA values in v4 §7.6 | Application helper not implemented |
| F04 semantic twin different key | PASS | `INDEPENDENTLY_REEXECUTED`: binding already exists | Alternate raw normalization remains app-only |
| F04 distinct semantic binding | PASS | v4 report and selected binding audit | App not tested |
| F05 wrong parent chat | PASS | `INDEPENDENTLY_REEXECUTED`: link trigger rejects; state accepted | — |
| F05 wrong review/A1/A2 exact | PASS | v4 report matrix; A2 `REPORTED_ONLY` | App A1/A2 integration not tested |
| F05 wrong conversation/repo/PR | PASS | v4 report; cross conversation/repo/PR tested in v4 matrix | Creation-job/owner application-only |
| F05 creation-job/owner/current GitHub | `APPLICATION_NOT_TESTED` | No parent columns; no app path | Mandatory WP-02 integration |
| F06 conflict clauses | PASS/REPORTED_ONLY | v4 matrix; selected F01/F02 rerun | No formal all-DML proof |
| Valid lifecycle transitions | PASS | v4 matrix | App call sites not implemented |
| Invalid transitions | PASS | v4 matrix | — |
| Expiry/revocation/confirmation | PASS/REPORTED_ONLY | v4 matrix; selected guards | TTL/lifecycle owner decision pending |
| Append-only/FK | PASS | v4 matrix and selected append-only tests | Linked-review deletion not fully rerun; parent mutable fields app-enforced |
| I1 fixture exact | PASS | `INDEPENDENTLY_REEXECUTED`: review 1, memberships 2, consumed 1, link 1 | Fixture only |
| I1 wrong-parent rollback | PASS | v4 report matrix | Fixture only |
| I1 actual reservation API | `APPLICATION_NOT_TESTED` | No app integration | Mandatory prerequisite |
| Concurrent requests/confirmations/consumption | PASS/REPORTED_ONLY | v4 concurrency matrix | Not independently rerun in this pack |
| Busy lock | PASS/REPORTED_ONLY | v4 matrix | — |
| One-PR Canary/pending merge | `APPLICATION_NOT_TESTED` | No app path | Mandatory prerequisite |
| Provider/GitHub/owner authorization | `APPLICATION_NOT_TESTED` | No external calls | Mandatory prerequisite |
| Independent third-party review | `INDEPENDENT_REVIEW_NOT_PERFORMED` | No reviewer artifact | Process limitation |
| Production readiness | Not tested | No deployment/migration | Not claimed |

### 7.1 Matrix interpretation

- The clean SQL package is technically coherent and the selected critical v3 bypasses
  are closed in the tested boundary.
- The v4 report's **A2/A3 FAIL** cases are not hidden; they mean the SQL is not an
  installer.
- `REPORTED_ONLY` entries are not independent proof.
- `APPLICATION_NOT_TESTED` entries are not schema defects unless the schema claims to
  enforce them; they are mandatory implementation prerequisites.

## 8. Residual risks ranked by severity

| ID | Severity | Risk | Classification |
|---|---|---|---|
| R-01 | **HIGH** | No idempotent/transactional installer or recovery protocol; repeat install fails; partial install leaves two objects and cannot be repaired by the exact SQL | Implementation/migration blocker; not a logical schema-invariant defect |
| R-02 | **HIGH** | Current owner, `creation_job_id`, GitHub/D-05/D-06, original PR source, one-PR restriction, and pending-membership rejection remain application-only and untested | Application implementation blocker |
| R-03 | **HIGH** | Actual review reservation API is not integrated with consumption; I1 is fixture-only | Application integration blocker |
| R-04 | **MEDIUM** | SQLite cannot prove `binding_key` SHA preimage; equivalent normalization variants depend on one application helper | Application boundary |
| R-05 | **MEDIUM** | `pr_numbers_json`, PR child table, and resolved PR set can be inconsistent if the application writes them incorrectly; SQL only links child vs membership | Application boundary |
| R-06 | **MEDIUM** | `creation_jobs`/`auto_reviews` non-key fields can mutate after the attestation/link snapshot; currentness requires revalidation | Application boundary |
| R-07 | **MEDIUM** | No separate system-invalidation event; TTL and lifecycle approval pending | Pending owner decision |
| R-08 | **MEDIUM** | No independent third-party review; v4 is author self-review and this pack is same-agent documentation review | Process limitation |
| R-09 | **LOW** | Tested SQL conflict guards do not constitute a formal proof over every possible direct DML form | Implementation conformance |
| R-10 | **LOW** | Several v4 matrix entries are `REPORTED_ONLY` rather than independently rerun by this pack | Evidence limitation |
| R-11 | **INFO** | Production, provider, Telegram, GitHub, migration, and Canary behavior were not tested or authorized | Out of scope |

**No verified CRITICAL/HIGH schema-logical bypass remains within the tested v4
boundary.** R-01–R-03 are real high risks to implementation/migration and must not be
misrepresented as solved by the schema.

## 9. Recommended owner decision

### 9.1 Recommendation

**CONDITIONAL APPROVAL — approve Schema v4 as a design basis, subject to the
conditions in §10; do not authorize implementation, migration, or operation yet.**

This is not an owner decision and does not modify `OD-R7-D04-SCHEMA-01`.

### 9.2 Why conditional approval

- The v3 F01–F06 schema issues have credible v4 remediations with executed evidence.
- The clean exact SQL installs and selected critical adversarial cases pass.
- F04/F05 and the actual I1 integration have explicit application boundaries; they
  cannot be proven by SQL fixtures.
- Repeat and partial installation fail; the exact SQL is not an installer.
- AUTH, LIFECYCLE/TTL, and INTEGRATION decisions remain pending.
- No independent third-party review or production validation exists.

### 9.3 Why not unconditional approval as-is

Unconditional design approval would risk being read as implementation/migration
readiness. The package explicitly fails repeat/partial install and has no application
integration evidence. Those conditions must be visible in the approval.

### 9.4 Why not request a schema revision first

No verified F01/F02/F03 schema-level bypass remains. F04/F05 are partially
application-boundary issues, not proof that the SQL is invalid. The installer is a
deployment/implementation artifact; it can be a condition rather than a revision to the
logical schema. The owner may still choose revision if they want the installer contract
inside the design approval.

### 9.5 Why not reject

No evidence in this review supports rejecting the additive v4 schema outright. The
remaining high risks are implementable controls and migration prerequisites, not
demonstrated impossibility. This is advisory only; the owner may decide otherwise.

## 10. Conditions before implementation

These conditions are mandatory if the owner conditionally approves the design:

1. **Design-only approval boundary.** Approval is limited to the schema design; it
   does not authorize application code, schema migration, database opening, worker,
   Canary, or external operations.
2. **Installer/versioning.** Implement a versioned, transactional installer with
   schema-version record, object inventory/hash, `BEGIN IMMEDIATE`, preflight partial
   state detection, rollback or explicit recovery, idempotent seeds, and fail-closed
   behavior. `IF NOT EXISTS` alone is insufficient.
3. **Installer tests.** Prove clean install, repeat install policy, interrupted/partial
   install, recovery/upgrade, missing/unexpected object detection, and seed repair on
   disposable DBs.
4. **Canonical helper.** Implement one `d04_binding_key` helper matching v4 §7; include
   fixed vectors, equivalent-input tests, different-input tests, and a negative test
   that rejects alternate implementations.
5. **Application controls.** Implement current-owner/watch/deletion revalidation,
   exact `creation_job_id`, GitHub/D-01/D-05/D-06 checks, canonical PR child
   population/synchronization, one-PR policy, and pending-membership rejection/no-merge.
6. **I1 integration.** Wire the actual reservation API and consumption in one
   `BEGIN IMMEDIATE` transaction, no external calls inside it; test exact, failed
   reservation, failed consumption, replay, and concurrency against the real code
   paths, not only fixtures.
7. **A1/A2.** `OD-R7-D04-AUTH-03` must explicitly select A1 or A2; no silent choice.
8. **Lifecycle/TTL.** `OD-R7-D04-LIFECYCLE-04` must select TTL and system-invalidation
   semantics before implementation of expiry/revocation.
9. **Integration/implementation authorization.** `OD-R7-D04-INTEGRATION-05` and a
   separate owner implementation authorization must name files, tests, migration, and
   verification.
10. **Independent review.** If required by the owner, a third-party independent review
    of v4 and the implementation must occur; this pack is not independent.

## 11. Exact owner decisions still required

| Decision | State | This package |
|---|---|---|
| `OD-R7-D04-SCHEMA-01` | `PENDING — NOT APPROVED` | Owner decision requested; not decided here |
| `OD-R7-D04-AUTH-03` | `PENDING` | No A1/A2 selection made |
| `OD-R7-D04-LIFECYCLE-04` | `PENDING` | No TTL/system-invalidation selection made |
| `OD-R7-D04-INTEGRATION-05` | `PENDING` | No I1 authorization made |
| D-03 | `APPROVED — current-owner-revalidation` | Preserved |
| D-04 | `APPROVED — canary-only-owner-attestation` | Preserved; implementation not authorized |
| D-04b | `DEFERRED — NOT APPROVED` | Preserved; no numeric ID |
| B1 | `APPROVED — name-bound attestation` | Preserved; same-name limitation |
| D-05 | `APPROVED — reject-rename-transfer` | Preserved |
| D-06 | `APPROVED — private-allowlisted-only` | Preserved |
| D-07 | `APPROVED_DESIGN_ONLY` | Preserved |
| D-08 | `APPROVED_BLOCKED` | Preserved |

No owner decision is inferred or fabricated by this package.

## 12. Next-step dependency sequence

1. Owner reviews this pack and makes an explicit decision on
   `OD-R7-D04-SCHEMA-01`: APPROVE, CONDITIONAL APPROVAL, REQUEST REVISIONS, or REJECT.
2. If conditional/approve, resolve `OD-R7-D04-AUTH-03` and
   `OD-R7-D04-LIFECYCLE-04` explicitly.
3. Resolve `OD-R7-D04-INTEGRATION-05` and approve the application transaction design.
4. Obtain independent review if required.
5. Issue a separate implementation authorization with installer, migration, test, and
   rollback plans.
6. Implement and test on disposable databases; no application DB migration before the
   installer/recovery gate passes.
7. Obtain a separate migration authorization, then migrate; no worker/Canary until
   separately authorized.
8. D-04b remains deferred; B1 same-name limitation remains; WP-04 remains blocked.

## 13. Non-authorization statement

**No implementation authorization is granted.** No application code, schema,
migration, configuration, test, database, worker, or Canary operation is authorized.
No application DB was opened. No GitHub/OpenHands/Telegram/provider API was called.
No commit, push, PR, merge, deploy, release, fetch, or pull occurred. Autopush remains
disabled/inactive.

This package is documentation-only and advisory. The owner must make the explicit
decision; waiting for that decision is required.
