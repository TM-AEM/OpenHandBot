# OHB2 — WP-06 Part 2 — Revised Owner Decision Briefing

**Task ID:** `OHB2-WP06-PART2-REVISED-OWNER-DECISION-BRIEFING`
**Date:** 2026-11-19
**Baseline:** HEAD `52e7789cc8cc97a7f7c09c9592226ab117db99a2` (== `origin/main`, 0/0)
**Inputs:** revised spec (Rev 2, 970 lines), `DESIGN-REMEDIATION-REPORT.md`, `REVALIDATION-AND-OWNER-DECISIONS-ANALYSIS.md`

> **No owner decision has been made. Nothing here authorizes implementation.**
> Every recommendation below is advice; the owner alone decides.

---

## 1. Revised design status

| Item | Status |
|---|---|
| Design specification | **Revision 2 — corrected** (674 → 970 lines) |
| TASK-A verdict | `DESIGN_CORRECTED_WITH_NOTES` |
| TASK-B verdict | `REVALIDATED_WITH_NOTES` |
| Implementation authorization | **NONE** |
| Owner decisions recorded | **NONE — O-1 … O-7 all open** |

---

## 2. D-1 … D-6 — what was wrong and how it was fixed

| ID | Original claim | Corrected position |
|---|---|---|
| **D-1** (critical) | Consume via a **standalone** `BEGIN IMMEDIATE` "mirroring `take_awaiting`" | **Transaction-composing helper.** The caller owns the boundary. 4 of 14 handlers already own a transaction; nesting is fatal and non-transient. `take_awaiting` is **dead code** (0 callers), superseded by `awaiting_state`. |
| **D-2** | Validator "rejects" tokens; unresolved tokens "cannot reach OpenHands" | **Wrong.** 2000/2000 tokens pass the validator and a **remote call IS made** (`NOT_FOUND`). Safety holds (no action) but the mechanism was misstated. Five-layer boundary table added; resolve **before** authorization. |
| **D-3** | Bare line numbers against committed HEAD | Point-in-time policy added; **symbol names authoritative**; `module::symbol` references. |
| **D-4** | `file:` = 54; limits treated as constants | `file:` = **55**; limits are **ranges** (`files` 47-56, `file` 48-55) driven by numeric digit width. Method and cases recorded. |
| **D-5** | 15 cid-bearing handlers | **14**, with a full table including transaction exposure. |
| **D-6** | `OpportunisticSweeper` as an optional hook | **Rejected** — hard-typed to `AttachmentReaper`. Boot hook + **mandatory** insert-path cap only. |

---

## 3. Updated decision matrix

| ID | Decision | Recommended | Confidence | Authorizes implementation |
|---|---|---|---|---|
| O-1 | Token length | 12 chars (`token_urlsafe(9)`) | HIGH | **NO** |
| O-2 | TTL / cap / batch | 30 min / 5,000 / 200, cap **mandatory** | HIGH | **NO** |
| O-3 | Cleanup lifecycle | Boot hook + insert cap, **no sweeper** | HIGH | **NO** |
| O-4 | Consumption contract | Single-use all, **transaction-composing** | HIGH | **NO** |
| O-5 | Schema 17→18 | Approve new table | HIGH | **NO — HARD GATE** |
| O-6 | Runbook coupling | Update atomically with DDL | HIGH | **NO** |
| O-7 | WP-07 sequencing | **Sequence after WP-07** | HIGH | **NO — HARD GATE** |

---

## 4. Explicit recommendation per decision

- **O-1 → 12 characters.** Worst-case `files:` payload leaves 47 chars for the token; 12 leaves 35
  bytes headroom and survives 20-digit numeric fields. 72-bit entropy. A `~`-prefixed variant would
  structurally eliminate ambiguity but adds a second format — recorded as an alternative, not advised.
- **O-2 → 30 min / 5,000 / 200, with the insert-path cap mandatory.** Measured consume ≈1.2 ms and
  prune ≈1.6 ms are ~3000× under `busy_timeout=5000`. The cap is the only bound in a process that
  never restarts.
- **O-3 → boot hook + insert-path cap. No sweeper.** The sweeper is hard-typed to `AttachmentReaper`;
  reusing it requires an out-of-scope `attachments.py` change, and a parallel sweeper is a prohibited
  new worker.
- **O-4 → single-use for all scopes, transaction-composing.** Proven in this task: composition works,
  rollback is correct, and the nested alternative produces a non-transient failure.
- **O-5 → approve the `callback_refs` table.** No existing table can serve; migration is idempotent
  and restart-tolerant.
- **O-6 → update `docs/OPERATIONS_RUNBOOK.md` §4 in the same change set.** Otherwise a live parity
  test fails.
- **O-7 → commit/stabilize WP-07 first.** WP-07 is **entirely uncommitted** (0 markers in HEAD, 21 in
  the working tree) and overlaps 4 of the 14 handlers.

---

## 5. Hard implementation gates

| Gate | Requirement |
|---|---|
| **G-1 Schema (O-5)** | **No schema migration or `callback_refs` code may begin** without explicit, recorded owner approval of the 17 → 18 transition. |
| **G-2 Sequencing (O-7)** | **No callback-reference implementation may begin** while WP-07 remains uncommitted and not independently reviewed. |
| **G-3 Contract (O-4)** | No consumption helper may be written until the transaction-composing contract is approved. |
| **G-4 Docs (O-6)** | The runbook update must land in the **same change set** as the DDL. |

---

## 6. WP-07 sequencing and its actual review limitations

| Dimension | Actual status |
|---|---|
| Implementation | Present in the working tree (21 markers; 420+/109−) |
| Owner acceptance | **Not recorded** |
| Independent review | **`INDEPENDENCE_NOT_ESTABLISHED`** (both WP-07 review reports) |
| Working tree | Uncommitted (`bot/db.py`, `bot/handlers.py`, `bot/watcher.py`) |
| Committed / published | **NO** — 0 WP-07 markers in `HEAD:bot/db.py` |

**Honest statement:** WP-07 has **not** passed independent review. The review attempts returned
`INDEPENDENCE_NOT_ESTABLISHED` because this environment cannot supply a genuinely separate reviewer.
That limitation is preserved here and is not glossed over.

**Recommended gate:** treat WP-07 as a prerequisite to be committed and stabilized before WP-06
Part 2 implementation, regardless of its review status — because it occupies the same functions.

---

## 7. Schema migration requirements

- Add `callback_refs` (one table, two indexes) to `bot/db.py::_init_schema` with
  `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS`.
- No `ALTER TABLE`; `_migrate()` unchanged.
- **Same change set:** update `docs/OPERATIONS_RUNBOOK.md` §4 (count 17 → 18, add the table name).
- Verified: 17 → 17 idempotent on reopen; `journal_mode=wal`, `foreign_keys=ON`,
  `busy_timeout=5000` all preserved.
- No down-migration. Rollback leaves an inert table; no user data at risk.

---

## 8. Security and transaction guarantees

**Guaranteed:**
- At-most-once **effect** per token (no duplicate action from a replayed token).
- Cross-user and cross-scope reuse rejected.
- Fail-closed: every failure path returns without action and never reaches `_classify_failure`.
- Bounded growth via `MAX_ROWS` + mandatory insert-path cap + bounded prune.
- **No nested `BEGIN IMMEDIATE`** in the 4 transaction-owning handlers.
- Consumption and the durable record commit **together or not at all**.

**Explicitly NOT claimed:**
- Exactly-once Telegram delivery.
- Exactly-once processing.
- Any atomicity spanning SQLite and the Telegram API.
- That an unresolved token can never reach a remote lookup **unless** the choke-point test passes —
  the design mandates resolving before authorization precisely because the validator does not.

---

## 9. Required tests before implementation acceptance

1. **No nested transaction:** drive `open_conversation`, `watch_conversation`,
   `unwatch_conversation`, `reply_prompt` end-to-end; assert no `OperationalError` and no
   `FAILED_PERMANENT`.
2. **Composition rollback:** the `consumed_at` write rolls back with the caller (token reusable) and
   commits when the caller commits.
3. **No unresolved token reaches upstream:** spy client; `assert client.calls == []` for stale tokens
   across all 14 handlers.
4. **Payload boundary:** all 16 shapes × `cid` 1..64 × numeric widths 1..5 → `<= 64` bytes.
5. **TTL:** valid at `expires_at − 1`, expired at `expires_at` exactly.
6. **Bounded prune:** at most `PRUNE_BATCH` per call; table never exceeds `MAX_ROWS` + one batch.
7. **Cross-user / cross-scope rejection** with no information leak.
8. **Restart persistence.**
9. **Doc parity:** `tests/test_doc_code_parity.py` green after the runbook update.
10. **Mutation-proven non-vacuous** for each discriminating test.

---

## 10. Decisions that must be made by the owner

1. **O-5** — approve or reject the `17 → 18` schema transition. *(Hard gate.)*
2. **O-7** — confirm WP-07 must be committed/stabilized first. *(Hard gate.)*
3. **O-4** — accept transaction-composing consumption in place of the spec's original mechanism.
4. **O-1, O-2, O-3, O-6** — approve the recommended parameters.
5. **D-1 / D-2 corrections** — acknowledge the two material corrections to the design.

Until these are recorded, **implementation must not begin.**

---

## 11. Statement of non-approval

**Nothing in this briefing is an owner approval.** No owner decision has been made or implied.
O-1 … O-7 remain **open**. The recommendations are technical advice derived from executed evidence
and current source; they carry no authority to implement, migrate, or change any payload.

**Independent review is NOT claimed.** This briefing was produced by the same agent that revised the
specification and revalidated it. Reviewer-session and environment independence are **not**
established in this environment, and the prior WP-07 reviews confirm the same limitation.
