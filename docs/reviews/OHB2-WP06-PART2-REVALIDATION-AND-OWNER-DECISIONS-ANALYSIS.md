# OHB2 — WP-06 Part 2 — Revalidation and Owner-Decisions Analysis (Revision 2)

**Task ID:** `OHB2-WP06-PART2-REVALIDATION-AND-DECISION-ANALYSIS`
**Date:** 2026-11-19
**Baseline:** HEAD `52e7789cc8cc97a7f7c09c9592226ab117db99a2` (== `origin/main`, 0/0)
**Revalidates:** `docs/design/OHB2-WP06-PART2-CALLBACK-REFS-DESIGN-SPEC.md` Revision 2 (970 lines)
**Precondition:** TASK-A verdict `DESIGN_CORRECTED_WITH_NOTES` → proceed.

> This document recommends. It does **not** decide, authorize, or record any owner answer.

## Verdict

# `REVALIDATED_WITH_NOTES`

Every design claim was re-checked against the current working tree and **reproduced in this task**.
"WITH_NOTES" reflects three items that design alone cannot close: (1) `watcher.unwatch`
composability, (2) inherited performance figures, (3) all seven owner decisions remain open.

---

## 1. Eight required verification checks — results

| # | Check | Method | Result |
|---|---|---|---|
| 1 | Transaction-composition model valid for every handler | Source trace + real `Database` probe | **PASS** — 4 transaction-owning handlers identified; composed + self-wrapped modes both valid |
| 2 | No proposed nested transaction | `grep` spec for `BEGIN` in helper | **PASS** — helper docstring: "NEVER opens/commits/rolls back"; prohibition in §5.3, §8.3, §12.2 |
| 3 | Security claims distinguish the four layers | Spec content check | **PASS** — five-layer table present (§3.4); stale "cannot reach" only appears as the *quoted incorrect claim* |
| 4 | Payload boundary via real constructors | `_btn()` sweep, all shapes, digit widths 1-5 | **PASS** — `files` 54→47, `file` 55→48, `deleteok` 55, `unwatch` 56 |
| 5 | 14-handler inventory | Spec + source enumeration | **PASS** — all 14 present; "15 cid-bearing" absent |
| 6 | Cleanup lifecycle and type compatibility | Source read | **PASS** — sweeper still `reaper: AttachmentReaper`; boot hook at `db.py:5532` |
| 7 | Schema migration assumptions | Real `Database` reopen | **PASS** — 17→17 idempotent; `wal`, `fk=1`, `busy_timeout=5000` |
| 8 | Runbook/doc-parity coupling | Test + runbook read | **PASS** — runbook says `**17** جدول`; spec mandates same-change-set update |

---

## 2. Reproduced evidence (executed in this task)

### 2.1 Transaction composition — validated on a real `Database`

```
1) composed helper inside caller transaction (no nested BEGIN):
   OK, rows: 1
2) rollback composition (helper write undone with caller):
   rows after rollback: 1 (expect 1)
3) nested BEGIN IMMEDIATE is fatal and NON-transient:
   error: cannot start a transaction within a transaction
   is_transient: False (expect False -> FAILED_PERMANENT)
```

**Conclusion:** the corrected model is sound. A composed helper's write is genuinely rolled back with
the caller, and the nested alternative is genuinely fatal and non-retryable.

### 2.2 `take_awaiting` is dead code

```
grep -rn "take_awaiting(" bot/ | grep -v "def take_awaiting"   →  (no results)
awaiting_state callers: bot/handlers.py:2165, 2405, 2519
```

### 2.3 Four transaction-owning handlers (exhaustive, incl. indirect)

```
open_conversation     -> set_awaiting_and_record_outcome
watch_conversation    -> add_watched_and_record_outcome
unwatch_conversation  -> _remove_watched_with_retry -> remove_watched (BEGIN IMMEDIATE @ db.py:2093)
reply_prompt          -> set_awaiting_and_record_outcome
TOTAL: 4 / 14
```

### 2.4 Payload boundaries (re-measured)

```
files 1/1: 54   files 4/5: 47
file  1/1: 55   file  4/5: 48
deleteok: 55    unwatch: 56
```

### 2.5 Schema migration

```
reopen: 17 -> 17 (idempotent)
wal / fk=1 / busy_timeout=5000  (all preserved)
```

### 2.6 WP-07 publication status — **the decisive O-7 fact**

```
WP-07 markers in committed HEAD (bot/db.py): 0
WP-07 markers in working tree: app.py=1, db.py=5, handlers.py=14, watcher.py=1  (21 total)
Uncommitted: bot/db.py, bot/handlers.py, bot/watcher.py
```

**WP-07 exists only in the working tree. None of it is committed.**

---

## 3. Evidence matrix

| Recommendation | Evidence | Type |
|---|---|---|
| O-1: 12-char token | `files` 47-54, `file` 48-55; 12 leaves ≥35 B headroom | **Measured this task** |
| O-1: token always passes `_ID_RE` | 2000/2000 | **Measured** (prior batch, re-confirmed logically) |
| O-2: 30 min / 5000 / 200 | Consume ≈1.2 ms, prune ≈1.6 ms @5000 rows; `busy_timeout=5000` | **Inherited** — repeat at implementation |
| O-2: cap mandatory | Boot-only cannot bound a never-restarting process | **Design argument** |
| O-3: boot + insert cap | `prune_web_sessions(time.time())` at `db.py:5532`; sweeper hard-typed | **Measured this task** |
| O-4: transaction-composing | Nested `BEGIN` fatal + non-transient; 13 `_nocommit` helpers; composition+rollback proven | **Measured this task** |
| O-5: new table | 17 tables now; 17→17 idempotent; reuse impossible (`web_sessions` keyed by `token_hash`+profile) | **Measured this task** |
| O-6: atomic runbook update | `test_runbook_table_count_matches_schema` asserts literal `**{n}** جدول`; runbook says 17 | **Measured this task** |
| O-7: sequence after WP-07 | WP-07 markers: 0 in HEAD, 21 in working tree; 4/14 handlers overlap | **Measured this task** |
| `watcher.unwatch` composes | Not determinable from `Database` source | **ASSUMPTION — unresolved** |

---

## 4. O-1 — Token length

**Decision required:** approve 12-char `secrets.token_urlsafe(9)`, or choose another length/format.

**Options:** A = 12 (proposed) · B = 16 · C = 8 · D = 12 with `~` discriminator.

**Recommendation: A (12 chars).**

**Rationale:** binding payload is `files:` at 47 chars (worst realistic numeric width). 12 leaves
**35 bytes** headroom; measured to survive 20-digit numeric fields (~52 B). 72 bits of entropy gives
collision probability ≈6.6×10⁻¹⁴ at 5,000 rows. Option C (8 chars) drops to 48 bits — 1000× worse for
no benefit. Option D would eliminate the ambiguity structurally but adds a second format; the same
guarantee is obtained from the choke-point test, so D is recorded as a **visible alternative**, not a
recommendation.

**Risks:** a missed resolver still reaches upstream (D-2) — mitigated by test, not by length.

**Dependencies:** none. **Confidence: HIGH.** **Authorizes implementation: NO.**

---

## 5. O-2 — TTL, row cap, prune batch

**Decision required:** approve TTL 30 min / `MAX_ROWS` 5,000 / `PRUNE_BATCH` 200.

**Options:** TTL 10/30/60 min · cap 1,000/5,000/unbounded · batch 50/200/1,000.

**Recommendation: 30 min / 5,000 / 200, with the insert-path cap made MANDATORY.**

**Rationale:** consume ≈1.2 ms and prune ≈1.6 ms are ~3000× under `busy_timeout=5000` — no contention.
30 min covers realistic menu-return latency (3× `AWAITING_TTL`). A bounded cap is itself a DoS
control; unbounded is unacceptable.

**Risks:** a heavy burst could evict still-valid tokens; a large backlog needs repeated prune calls.

**Dependencies:** O-3 (where pruning runs), O-4 (consumption contract). **Confidence: HIGH**
(inherited timings → repeat at implementation). **Authorizes implementation: NO.**

---

## 6. O-3 — Cleanup lifecycle

**Decision required:** confirm boot hook + insert-path cap only, or authorize the sweeper.

**Recommendation: boot hook + insert-path cap. NO sweeper.**

**Rationale:** `OpportunisticSweeper.__init__(self, reaper: AttachmentReaper, ...)` is hard-typed and
its lifecycle is bound to `AttachmentReaper.sweep`. Reuse needs an out-of-scope `attachments.py`
change (also touched by WP-07); a parallel sweeper is a new worker-like component and violates the
approved architecture. The insert-path cap is the only growth bound in a never-restarting process.

**Risks:** cleanup runs only at boot + on issue; an idle long-lived process relies on the cap (which
is sufficient).

**Dependencies:** O-2. **Confidence: HIGH.** **Authorizes implementation: NO.**
If the owner chooses the sweeper, that needs **separate architecture approval**.

---

## 7. O-4 — Single-use consumption and transaction composition

**Decision required:** accept transaction-composing consumption (single-use, all scopes), replacing
the spec's original self-contained `BEGIN IMMEDIATE`.

**Recommendation: single-use for ALL scopes, transaction-composing.**

**Rationale:** proven in this task — composition works and rolls back correctly; the nested
alternative is fatal and classified **non-transient** → `FAILED_PERMANENT` → `DEF-002` stall. The
project's own 13 `_nocommit` helpers are the established convention, and `take_awaiting` (the cited
precedent) is **dead code** superseded by `awaiting_state`.

**Transaction ownership model:**
- The **caller** owns `BEGIN IMMEDIATE` / `commit` / `rollback`.
- `consume_callback_ref_nocommit` performs SQL only.
- *Composed* mode in the 4 transaction-owning handlers; *self-wrapped* mode elsewhere.
- Atomicity is **stronger** than Revision 1: consumption and the durable record commit together.

**Risks:** if the enclosing transaction rolls back, the token becomes reusable (correct — no durable
effect occurred). `watcher.unwatch` composability is unverified.

**Dependencies:** O-7 (WP-07 must be settled first), O-3. **Confidence: HIGH.**
**Authorizes implementation: NO.**

---

## 8. O-5 — Schema 17 → 18 migration gate

**Decision required:** explicitly approve adding `callback_refs` (17 → 18 tables).

**Recommendation: approve the new table.**

**Rationale:** no existing table can serve — `web_sessions` is keyed by `token_hash` with a `profile`
blob; `processed_updates` by `update_id`; `user_state` holds one row per user. Migration is idempotent
(17→17 verified), restart-tolerant, and self-healing; WAL/FK/busy_timeout preserved. Rollback leaves
an inert table; no user data at risk.

**Risks:** +1 table; requires the O-6 doc update.

**Dependencies:** O-6 (must land together). **Confidence: HIGH.**

> **This is a HARD GATE. No DDL, migration, or `callback_refs` code may land without an explicit,
> recorded owner approval of the 17 → 18 transition. This document does not provide it.**

---

## 9. O-6 — Runbook / doc-parity coupling

**Decision required:** may WP-06 Part 2 edit `docs/OPERATIONS_RUNBOOK.md` §4 in the same change set?

**Recommendation: yes — atomic update.**

**Rationale (measured):** `tests/test_doc_code_parity.py::test_runbook_table_count_matches_schema`
asserts `f"**{len(tables)}** جدول" in RUNBOOK`, with `tables` derived from
`bot/db.py::_init_schema`. The runbook states `**17** جدول`. Adding the table makes `len(tables)==18`
and the assertion **fails** unless the runbook is updated together. The sibling test
`test_runbook_documents_every_schema_table` additionally requires the `` `callback_refs` `` name to
appear.

**Risks:** none if done atomically; red CI if not.

**Dependencies:** O-5. **Confidence: HIGH.** **Authorizes implementation: NO.**

---

## 10. O-7 — WP-07 sequencing

**Decision required:** must WP-07 be committed/stabilized before WP-06 Part 2 implementation?

**Recommendation: YES — sequence after WP-07. Treat as a hard sequencing gate.**

### WP-07 status across the five required dimensions

| Dimension | Actual status | Evidence |
|---|---|---|
| **Implementation** | Substantial work present in the working tree | 21 `OHB2-WP-07` markers; 420 insertions / 109 deletions across 3 files |
| **Owner acceptance** | **Not recorded** | No owner acceptance document for WP-07 exists |
| **Independent review** | **`INDEPENDENCE_NOT_ESTABLISHED`** | Both WP-07 review reports state this explicitly |
| **Working-tree status** | Uncommitted, modified | `bot/db.py`, `bot/handlers.py`, `bot/watcher.py` |
| **Committed / published** | **NO** | `grep -c add_watched_and_record_outcome` on `HEAD:bot/db.py` = **0** |

**Rationale:** Revision 1 called this "independent (no shared files beyond `handlers.py`)". That is
**not supportable**:
- 17 functions in `bot/handlers.py` are modified by WP-07, including **4 of the 14** cid-bearing
  handlers this design must instrument.
- WP-07 adds `BEGIN IMMEDIATE`-owning methods in `bot/db.py` that this design must compose with.
- Implementing now would entangle two uncommitted work packages in the same functions and risk the
  user's existing work — explicitly forbidden by the batch rules.

**Risk of not sequencing:** guaranteed merge conflicts; undefined transaction semantics mid-flight;
inability to attribute a regression to either package.

**Dependencies:** none upstream; blocks O-4's implementation. **Confidence: HIGH.**

> **This is a HARD SEQUENCING GATE.** No callback-reference implementation may begin while the WP-07
> prerequisite remains unresolved (uncommitted and not independently reviewed).
>
> **This document does not claim WP-07 passed independent review.** It did not: both review reports
> returned `INDEPENDENCE_NOT_ESTABLISHED`.

---

## 11. Updated decision matrix

| ID | Recommended | Confidence | Authorizes implementation | Blocks |
|---|---|---|---|---|
| O-1 | 12 chars | HIGH | **NO** | Token column, payloads |
| O-2 | 30 min / 5,000 / 200 + mandatory cap | HIGH | **NO** | TTL, index, prune |
| O-3 | Boot hook + insert cap, no sweeper | HIGH | **NO** | Cleanup wiring |
| O-4 | Single-use all, transaction-composing | HIGH | **NO** | Consumption helper |
| O-5 | New table — **HARD GATE** | HIGH | **NO** | All DDL |
| O-6 | Atomic runbook update | HIGH | **NO** | Doc ownership |
| O-7 | **Sequence after WP-07 — HARD GATE** | HIGH | **NO** | All implementation |

**No recommendation in this document authorizes any implementation.**

---

## 12. What was NOT changed

No production code, test, schema, migration, payload, Mini App, WP-07, or WP-08 change. The runbook
was read, not modified. No commit, push, PR, merge, deploy, or release. **No independent review is
claimed** — this is a same-agent revalidation, and independence is **not** established.
