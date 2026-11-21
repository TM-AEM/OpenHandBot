# OHB2 — WP-06 Part 2 — Owner Decision Register Update

**Decision Batch:** `OD-WP06-PART2-02`
**Date:** 2026-11-19
**Decided by:** Project owner
**Recorded by:** AI agent (OpenHands) on behalf of the owner
**Baseline commit:** `52e7789cc8cc97a7f7c09c9592226ab117db99a2` (== `origin/main`, ahead/behind `0/0`)
**Supersedes:** nothing. This is an **incremental** register update; the prior analyses remain valid.

> This record documents **owner governance decisions**. It is not a technical review, not an
> independent verification, and not a claim that any work package was independently reviewed.
>
> **These decisions authorize NO production-code change, NO schema change, NO migration, NO test
> change, NO callback-payload change, NO Mini App change, NO Git operation, NO deployment, NO release,
> and NO Autopush activation.**

---

## 1. Decisions recorded in this batch

| ID | Decision | Status | Effect |
|---|---|---|---|
| **O-5** | `APPROVE_GATE` | `OWNER_APPROVED_WITH_HARD_IMPLEMENTATION_GATE` | Approves the schema **direction** and its gate. Does **not** authorize migration. |
| **O-7** | `DEFER_UNTIL_WP07_STABLE` | `OWNER_APPROVED_DEFER_UNTIL_WP07_STABLE` | WP-06 Part 2 implementation stays deferred until WP-07 stabilization evidence is complete. |

---

## 2. O-5 — Schema Migration Gate

### 2.1 Owner decision (verbatim intent)

**`APPROVE_GATE`** — the owner approves the **architectural direction** of introducing a dedicated
`callback_refs` table, increasing the table count from **17 to 18**.

**This approves the schema direction and its mandatory implementation gate only. It authorizes no
migration and no implementation.**

### 2.2 Binding conditions (recorded exactly as given)

| # | Condition |
|---|---|
| **C-5.1** | No schema migration is authorized by this decision. |
| **C-5.2** | No production schema, database initialization, or migration code may be modified without **separate explicit owner authorization**. |
| **C-5.3** | No callback-reference implementation may begin without **separate explicit owner authorization**. |
| **C-5.4** | The migration must be accompanied by the corresponding **runbook update in the same change set**. |
| **C-5.5** | `test_doc_code_parity.py` and all relevant migration, compatibility, and rollback tests must pass. |
| **C-5.6** | The implementation must preserve the approved **transaction-composition design**: caller-owned transaction boundaries and the `_nocommit` consumption-helper model. |
| **C-5.7** | The existing **17-table baseline remains authoritative** until a separately authorized migration is implemented and verified. |

### 2.3 What this decision changes in the project state

| Dimension | Before | After |
|---|---|---|
| Schema direction (17 → 18) | Proposed, unapproved | **Owner-approved as direction** |
| Migration execution | Not authorized | **Still NOT authorized** |
| `callback_refs` implementation | Not authorized | **Still NOT authorized** |
| 17-table baseline authority | Authoritative | **Remains authoritative** (C-5.7) |

### 2.4 Explicit non-authorizations

This decision does **not** authorize:
- creating the `callback_refs` table,
- editing `bot/db.py::_init_schema`,
- editing `docs/OPERATIONS_RUNBOOK.md` (that is required **at migration time**, C-5.4),
- writing the consumption helper,
- any test change.

### 2.5 Gate status

# `O-5 = OWNER_APPROVED — DIRECTION ONLY — MIGRATION STILL BLOCKED`

The gate is now **satisfied as a direction approval** but **remains closed for execution**. A
separate explicit owner authorization is required to open it.

---

## 3. O-7 — WP-07 Sequencing Prerequisite

### 3.1 Owner decision (verbatim intent)

**`DEFER_UNTIL_WP07_STABLE`** — WP-06 Part 2 callback-reference implementation must remain deferred
until WP-07 has reached a **demonstrably stable and documented** state.

### 3.2 Required stabilization evidence (the seven conditions)

| # | Required evidence | Current status (see §4) |
|---|---|---|
| **E-7.1** | Current inventory of all WP-07 changes (tracked, untracked, relevant ignored) | **PROVIDED** — §4.1 |
| **E-7.2** | Clear distinction: implementation completion / owner acceptance / independent-review status / Git publication status | **PROVIDED** — §4.2 |
| **E-7.3** | Preservation and verification of all existing WP-07 working-tree changes | **PROVIDED** — §4.3 |
| **E-7.4** | Documented disposition for every in-scope WP-07 finding and remaining limitation | **PARTIAL** — §4.4 |
| **E-7.5** | Review disposition explicitly identifying whether genuine independent review was established | **PROVIDED** — §4.5 |
| **E-7.6** | If independent review unavailable, a **separate explicit owner decision** on accepting WP-07 with documented reservations | **NOT SATISFIED — requires a new owner decision** |
| **E-7.7** | A stable, identifiable baseline for subsequent WP-06 work | **NOT SATISFIED** — §4.7 |

### 3.3 Binding restrictions (recorded exactly as given)

| # | Restriction |
|---|---|
| **R-7.1** | WP-06 implementation must **not** begin before the stabilization prerequisite is satisfied. |
| **R-7.2** | `INDEPENDENCE_NOT_ESTABLISHED` must **not** be represented as an independent-review pass. |
| **R-7.3** | This decision does **not** authorize committing, pushing, creating PRs, merging, or publishing WP-07. |
| **R-7.4** | Any such Git or publication operation requires **separate explicit authorization**. |

### 3.4 Gate status

# `O-7 = DEFERRED — PREREQUISITE NOT YET SATISFIED (E-7.6, E-7.7 OUTSTANDING)`

---

## 4. WP-07 stabilization evidence — current state

### 4.1 E-7.1 — Inventory of WP-07 changes (measured this session)

**Tracked modifications (uncommitted):**
```
 M .agent/PROGRESS.md
 M bot/db.py                                         (+335 lines changed)
 M bot/handlers.py                                   (+176 lines changed)
 M bot/watcher.py                                    (+18 lines changed)
 M tests/test_handlers.py
 M tests/test_sw06_unwatch_db_failure_propagation.py
                                    5 files: 433 insertions(+), 122 deletions(-)
```

**Untracked WP-07 test files (6):**
```
?? tests/test_wp07_atomic_state_outcome.py
?? tests/test_wp07_f1_notification_failure.py
?? tests/test_wp07_nav01_nav03_nav04_atomic.py
?? tests/test_wp07_nav02_nav05_simple_clear_atomic.py
?? tests/test_wp07_nav06_open_conversation_atomic.py
?? tests/test_wp07_watch_unwatch_atomicity.py
```

**Tracked WP-07 test files (already in HEAD, 1):**
```
   tests/test_wp07_route_renewal_and_policy.py
```

**Relevant ignored files:** only tool caches — `.openhands/`, `.pytest_cache/`, `.venv/`,
`__pycache__/` (8 entries). **No WP-07 artifact is hidden in an ignored path.**

**WP-07 marker counts (working tree):** `bot/app.py` 1, `bot/db.py` 5, `bot/handlers.py` 14,
`bot/watcher.py` 1, plus 1 marker in each of 6 untracked test files.

### 4.2 E-7.2 — The four status dimensions, kept strictly separate

| Dimension | Actual status | Evidence |
|---|---|---|
| **Implementation completion** | **PARTIAL / SELF-REPORTED** | 21 WP-07 markers in the working tree; 433+/122− across 5 tracked files |
| **Owner acceptance** | **NOT RECORDED for WP-07** | Only WP-05 has an acceptance record (`OD-WP05-ACCEPT-01`) |
| **Independent-review status** | **`INDEPENDENCE_NOT_ESTABLISHED`** | Both WP-07 review reports state it explicitly |
| **Git publication status** | **PARTIAL** — some WP-07 work IS committed | See §4.3 |

> **[CORRECTION — material]** Earlier reports in this project described WP-07 as *"entirely
> uncommitted"*. **That was imprecise and is corrected here.** WP-07 is **partially committed**:
>
> | WP-07 element | In `HEAD` (`52e7789`)? |
> |---|---|
> | `bot/app.py` — DEF-006 `concurrent_updates(True)` comment/config | **YES** (marker at HEAD `app.py:75`) |
> | `bot/handlers.py` — DEF-013 route-renewal-after-whitespace-check | **YES** (marker at HEAD `handlers.py:2460`) |
> | `tests/test_wp07_route_renewal_and_policy.py` | **YES** |
> | `bot/db.py` — `add_watched_and_record_outcome` | **NO** (0 occurrences in `HEAD:bot/db.py`) |
> | `bot/db.py` — `set_awaiting_and_record_outcome` | **NO** (0 occurrences) |
> | `bot/watcher.py` — atomicity work | **NO** (0 WP-07 markers in `HEAD:bot/watcher.py`) |
> | 6 untracked WP-07 test files | **NO** |
>
> **Consequence:** WP-07 spans both committed and uncommitted state. A "stable identifiable baseline"
> (E-7.7) therefore does **not** yet exist, because part of the work is in `HEAD` and part is not.

### 4.3 E-7.3 — Preservation verification

Verified this session:
- All 6 tracked modifications are **intact** and untouched by this batch.
- All 6 untracked WP-07 test files are **intact**.
- No `git restore`, `checkout`, `reset`, `clean`, or broad staging was performed.
- `staged = 0` — nothing was added to the index.

**WP-07 test result (executed this session):**
```
pytest tests/test_wp07_*.py  →  100 passed
```

### 4.4 E-7.4 — Finding dispositions — **PARTIAL**

| Finding | Disposition | Evidence source |
|---|---|---|
| **NEW-DEF-03** (watch/unwatch atomicity) | **DONE for the async watch/unwatch part** (self-reported) | `OHB2-WP07-NEW-DEF03-WATCH-UNWATCH-ATOMICITY-…-REPORT.md` |
| **F-1** (Option C) | **Already implemented** — review confirmed existing code satisfies it | `OHB2-WP07-F1-OPTION-C-…-REPORT.md` |
| **DEF-013** (route renewal after whitespace) | **Committed in HEAD** | marker at `HEAD:bot/handlers.py:2460` |
| **DEF-006** (`concurrent_updates`) | **Committed in HEAD** | marker at `HEAD:bot/app.py:75` |
| Remaining `NEW-DEF-03` sites | **NOT DONE** — navigation sweep, durable-intent paths, `callback_refs` | Report §266 explicitly lists these as remaining |

**Gap:** there is **no single consolidated disposition table** covering *every* in-scope WP-07
finding. **E-7.4 is therefore PARTIAL**, not satisfied.

### 4.5 E-7.5 — Independent-review disposition

**`INDEPENDENCE_NOT_ESTABLISHED`** — stated verbatim in both WP-07 review reports:

```
| Independent review | **INDEPENDENCE_NOT_ESTABLISHED** | see §6 |
**`INDEPENDENCE_NOT_ESTABLISHED`.** This environment cannot supply a genuinely separate reviewer
```

Per **R-7.2**, this is **not** an independent-review pass and must never be described as one.

### 4.6 E-7.6 — Separate owner decision required — **NOT SATISFIED**

Independent review is unavailable. O-7's condition 6 therefore requires a **new, separate explicit
owner decision** on whether to accept WP-07 **with documented reservations** (analogous to
`OD-WP05-ACCEPT-01`).

**This has not been given. The agent cannot supply it.**

### 4.7 E-7.7 — Stable identifiable baseline — **NOT SATISFIED**

WP-07 work is split across `HEAD` and the working tree. No commit, tag, or documented snapshot
identifies "WP-07 stable". Creating one would require a Git operation, which **R-7.3 prohibits**
without separate authorization.

---

## 5. Remaining owner decisions

| ID | Decision | Status |
|---|---|---|
| **O-1** | Token length (12 chars recommended) | **PENDING** |
| **O-2** | TTL / `MAX_ROWS` / `PRUNE_BATCH` | **PENDING** |
| **O-3** | Cleanup lifecycle (boot + insert cap; no sweeper) | **PENDING** |
| **O-4** | Single-use consumption + transaction composition | **PENDING — must be resolved before implementing consumption** |
| **O-5** | Schema 17 → 18 gate | **APPROVED (direction only)** — this batch |
| **O-6** | Runbook / doc-parity coupling | **PENDING** — must remain consistent with the O-5 gate (C-5.4, C-5.5) |
| **O-7** | WP-07 sequencing prerequisite | **DEFERRED** — this batch |

**O-4 must be resolved before implementing callback-reference consumption.**
**O-6 must remain consistent with the O-5 runbook and documentation-parity gate.**

---

## 6. Authorization boundary

These decisions authorize **none** of the following:

- production-code changes,
- schema changes or migrations,
- test changes,
- callback-payload changes,
- Mini App changes,
- Git operations (commit, push, PR, merge),
- deployment,
- release,
- Autopush activation.

**Any implementation phase requires a separate explicit owner authorization after its prerequisites
have been satisfied.**

---

## 7. What the agent did NOT do in this batch

| Action | Status |
|---|---|
| Production code change | **NONE** |
| Test change | **NONE** |
| Schema / migration change | **NONE** — table count still 17 |
| Callback payload change | **NONE** |
| Mini App change | **NONE** |
| WP-07 modification | **NONE** — all 6 modified + 6 untracked files untouched |
| Runbook change | **NONE** — still states 17 tables |
| Git operation | **NONE** — no commit, push, PR, merge, tag |
| Independent-review claim | **NONE** — explicitly not established |
| Autopush | **NOT ACTIVATED** |

---

## 8. Recommended next step

To satisfy **E-7.6** and **E-7.7** and unblock O-7, the owner would need to:

1. Issue a **separate explicit owner decision** on WP-07 acceptance with documented reservations
   (E-7.6), and
2. Separately authorize a Git operation to create a stable, identifiable WP-07 baseline (E-7.7),
   since R-7.3 forbids one without authorization.

**Neither is authorized by this record. This record stops here.**
