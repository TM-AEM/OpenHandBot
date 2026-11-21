# OHB2 — WP-06 Part 2 — Seven Owner Decisions: Technical and Architectural Analysis

**Task ID:** `OHB2-WP06-PART2-OWNER-DECISIONS-ANALYSIS`
**Date:** 2026-11-19
**Baseline:** HEAD `52e7789cc8cc97a7f7c09c9592226ab117db99a2` (== `origin/main`, 0/0)
**Precondition:** TASK-A verdict `INTEGRITY_VERIFIED_WITH_NOTES` — proceeds with D-1/D-2 as mandatory conditions.

**This document recommends. It does not decide. No owner decision is recorded here.**

---

## How to read this document

Each decision follows the mandated 13-point format. Every recommendation is tied to a measurement or
a source location. Where the audit found a material defect (D-1, D-2), the recommendation
**incorporates the correction** rather than restating the spec's original position.

---

# O-1 — Token length and format

### 1. Exact question
Should `callback_refs.token` be a 12-character `secrets.token_urlsafe(9)` value, or a different
length/format?

### 2. Current proposal
12 chars, `secrets.token_urlsafe(9)`, alphabet `[A-Za-z0-9_-]`, `PRIMARY KEY`, collision retry ≤3.

### 3. Relevant evidence

| Measurement | Result |
|---|---|
| `secrets.token_urlsafe(9)` output length | **always exactly 12** (verified) |
| Entropy | 9 bytes = **72 bits** |
| Worst payload with 12-char token | `file:{t}:999999:99999999` = **33 bytes** (cap 64) |
| Headroom at worst case | **31 bytes** |
| Binding payload constraint | `files:`/`file:` at **47-55** cid chars (§6 of audit) |
| Collision probability @ 5,000 rows | ≈ **6.6 × 10⁻¹⁴** |
| Token passes `is_valid_conversation_id` | **2000/2000 = 100%** |

### 4. Available options

| Option | Description |
|---|---|
| **A** | 12 chars, `token_urlsafe(9)` (proposed) |
| **B** | 16 chars, `token_urlsafe(12)` |
| **C** | 8 chars, `token_urlsafe(6)` |
| **D** | 12 chars with a discriminator prefix (e.g. `~`) |

### 5. Advantages / disadvantages

| Option | Advantages | Disadvantages |
|---|---|---|
| **A (12)** | Fits every payload with ≥31 B headroom; 72-bit entropy; uniform alphabet matching `_ID_RE` | Still ambiguous with conversation IDs (D-2) |
| **B (16)** | 96-bit entropy | Shrinks `files:` headroom to ~27 B; no practical security gain at 5,000 rows |
| **C (8)** | Shortest | 48-bit entropy; collision ≈ 8.9 × 10⁻⁷ at 5,000 rows — **1000× worse** for no meaningful benefit |
| **D (prefix)** | Eliminates ambiguity: `~` fails `_ID_RE` (verified) | Consumes 1 byte; introduces a second format; **but makes the D-2 hazard structurally impossible** |

### 6. Security implications
- A/B/C all carry the **D-2 hazard**: a missed resolver silently reaches the upstream API.
- **D eliminates the hazard structurally** — `is_valid_conversation_id('~...')` returns `False`, so a
  leaked token would be rejected before any remote call.

### 7. Reliability / concurrency implications
None differ materially; token length does not affect locking or atomicity.

### 8. Architectural implications
D introduces a **second callback-data format**, which complicates parsing (`split(":")` still works,
but the discriminator must be stripped). A is architecturally neutral.

### 9. Dependencies
None on WP-07/WP-08. Interacts with D-2 correction.

### 10. Recommended option
**A (12 chars) — retained**, **plus** a mandatory non-negotiable implementation requirement: resolution
must be explicit and centralized (never value-sniffing), and a regression test must assert no
unresolved token reaches `authorize_conversation_detailed`.

**On option D:** the audit found it genuinely attractive as defence-in-depth, but it is **not
recommended now** because it adds a format change beyond what the defect requires, and the same
guarantee is achievable with the choke-point test. **Recorded as an owner-visible alternative.**

### 11. Confidence
**HIGH** — measured, not estimated.

### 12. Explicit owner approval required?
**Yes.** This is `O-1`; it fixes a schema column width.

### 13. What remains blocked until approval
Token generation, the `token TEXT PRIMARY KEY` column definition, and all payload-format work.

---

# O-2 — TTL and resource limits

### 1. Exact question
Are `CALLBACK_REF_TTL = 30 min`, `MAX_ROWS = 5000`, `PRUNE_BATCH = 200` the right values?

### 2. Current proposal
30 min / 5,000 / 200.

### 3. Relevant evidence — measured on a real SQLite database

| Measurement (at 5,000 rows, WAL) | Result |
|---|---|
| Consume transaction latency | **median 1.181 ms**, p99 2.100 ms |
| Bounded prune of 200 rows | **1.622 ms** |
| `busy_timeout` configured | **5000 ms** |
| `journal_mode` | **wal** |
| Existing TTL precedents | `AWAITING_TTL` 10 min; `ATTACHMENT_BATCH_TTL` 15 min; `MINI_APP_SESSION_TTL` 3600 s |

### 4. Available options

| Parameter | Options |
|---|---|
| TTL | 10 min (match `AWAITING_TTL`) / **30 min** / 60 min (match Mini App) |
| MAX_ROWS | 1,000 / **5,000** / unbounded |
| PRUNE_BATCH | 50 / **200** / 1,000 |

### 5. Advantages / disadvantages

| Choice | Advantages | Disadvantages |
|---|---|---|
| **TTL 30 min** | Covers realistic menu-return latency; ~3× `AWAITING_TTL` | Users who return after 30 min get stale menus (safe, but a UX cost) |
| TTL 10 min | Consistent with `AWAITING_TTL` | Too short — a user paging files can exceed it |
| TTL 60 min | Most forgiving | Larger live set; more stale-but-valid rows |
| **MAX_ROWS 5,000** | Bounds table; consume stays ~1.2 ms | A heavy multi-user burst could evict still-valid tokens |
| MAX_ROWS unbounded | Never evicts valid tokens | Unbounded growth — violates the baseline |
| **PRUNE_BATCH 200** | 1.6 ms; far under busy_timeout | Slow drain if a large backlog accumulates (needs repeated calls) |

### 6. Security implications
Bounded `MAX_ROWS` is itself a **DoS control**: an attacker cannot force unbounded growth by
triggering renders. Unbounded is unacceptable.

### 7. Reliability / concurrency implications
Measured consume (1.2 ms) and prune (1.6 ms) are **~3000× under** `busy_timeout` (5000 ms). Write-lock
hold time is negligible. **No contention risk at these values.**

### 8. Architectural implications
None — all three are constants.

### 9. Dependencies
Interacts with O-3 (cleanup frequency) and O-4 (whether consumed rows are retained).

### 10. Recommended option
**Accept 30 min / 5,000 / 200 as proposed**, with one **non-negotiable** addition:

> The **insert-path cap must be mandatory**, not optional. Audit §10.4 found that boot-hook-only
> cleanup without the insert-path cap allows unbounded growth in a long-lived process. This is the
> one place where the spec's own "optional" framing is unsafe.

### 11. Confidence
**HIGH** — values are backed by measured latencies, not intuition.

### 12. Explicit owner approval required?
**Yes** (`O-2`).

### 13. What remains blocked until approval
TTL constants, the `expires_at` index strategy, and the prune scheduling.

---

# O-3 — Cleanup integration points

### 1. Exact question
Where should `callback_refs` pruning run?

### 2. Current proposal
Boot hook only (recommended), optionally the `OpportunisticSweeper`, plus an insert-path cap.

### 3. Relevant evidence

| Hook | Location | Frequency | In a transaction? | Bounded? |
|---|---|---|---|---|
| Boot maintenance | `db.py:5532` `prune_web_sessions(time.time())` | Once per process start | **No** — own statement | Yes (own `LIMIT`) |
| `OpportunisticSweeper` | `attachments.py:1437-1482`, wired `app.py:242` | Throttled by `min_interval`, watcher tick | **No** | Yes |
| Insert-path cap | New, on token issue | Once per issue | **Would be inside the caller's flow** | Yes |

**Critical constraint found (audit D-6):** `OpportunisticSweeper.__init__(self, reaper: AttachmentReaper, ...)`
is **hard-typed** to `AttachmentReaper` and calls `reaper.sweep()`. It cannot serve `callback_refs`
without modifying `attachments.py` — a file **outside WP-06 scope** that **WP-07 also touches**.

### 4. Available options

| Option | Description |
|---|---|
| **A** | Boot hook + mandatory insert-path cap (no sweeper) |
| **B** | Boot hook + generic sweeper (requires modifying `attachments.py`) |
| **C** | New dedicated background worker |

### 5. Advantages / disadvantages

| Option | Advantages | Disadvantages |
|---|---|---|
| **A** | Zero out-of-scope edits; no new worker; insert-path cap guarantees the bound | Cleanup only at boot + on issue; a fully idle long-lived process relies on the insert-path cap (which is sufficient) |
| **B** | Periodic cleanup during activity | Requires modifying `attachments.py` (out of scope, WP-07 conflict); expands blast radius for no correctness gain |
| **C** | Strict periodic cleanup | **Violates approved architecture** (one bot + ASGI, existing outbox/workers only) |

### 6. Security implications
All options are bounded. C adds a new attack surface and violates the single-owner model.

### 7. Reliability / concurrency implications
Boot hook runs **outside** any user transaction — no nesting risk. The insert-path cap **must** be
implemented transaction-composing (see O-4/D-1) to avoid nested `BEGIN IMMEDIATE`.

### 8. Architectural implications
**Option B is an architecture change** in disguise (modifying a shared module for a new consumer).
**Option C is a prohibited architecture change.** Only A respects the constraints.

### 9. Dependencies
Depends on O-2 (`PRUNE_BATCH`) and O-4 (consumption contract).

### 10. Recommended option
**A — boot hook + mandatory insert-path cap. No sweeper. No new worker.**

Explicitly **reject** the sweeper option: it is not free, it requires out-of-scope edits, and it
delivers no correctness benefit over A.

### 11. Confidence
**HIGH** — the sweeper's type coupling is directly observed in source.

### 12. Explicit owner approval required?
**Yes** (`O-3`). If the owner prefers B, that **also** requires a separate architecture approval
because it modifies `attachments.py`.

### 13. What remains blocked until approval
Where `prune_callback_refs` is called from; whether `attachments.py` may be touched (it may **not**,
under A).

---

# O-4 — Single-use scope and consumption contract

### 1. Exact question
Which scopes are single-use, and what exactly does "consumed" mean?

### 2. Current proposal
Single-use for **all** scopes, via a self-contained `BEGIN IMMEDIATE` (mirroring `take_awaiting`).

### 3. Relevant evidence

**The spec's precedent is unsafe here (audit D-1).** Measured:

```
nested BEGIN IMMEDIATE → OperationalError: cannot start a transaction within a transaction
is_transient_sqlite_error(that error) → False
  ⇒ classifies as FAILED_PERMANENT ⇒ DEF-002 polling stall
```

**WP-07 already opens `BEGIN IMMEDIATE` inside the affected handlers.** `db.py` (worktree)
`add_watched_and_record_outcome` executes `conn.execute("BEGIN IMMEDIATE")` and is called from
`watch_conversation`. WP-07 adds `set_awaiting_and_record_outcome`,
`clear_awaiting_and_record_outcome`, `remove_watched`, all with the same pattern.

**The project already abandoned `take_awaiting`'s self-contained transaction.** `db.py:2880-2900`
documents `awaiting_state` as its replacement: "read without consuming… consumption became separate
and atomic with the durable record write." The spec cites the **superseded** pattern.

### 4. Available options

| Option | Description |
|---|---|
| **A** | Single-use all scopes, **transaction-composing** consumption (`commit=False` helper inside the caller's transaction, mirroring `_set_last_state_nocommit`) |
| **B** | Single-use all scopes, self-contained `BEGIN IMMEDIATE` (spec as written) |
| **C** | Single-use mutating only; reusable read-only |
| **D** | No consumption tracking (reusable tokens) |

### 5. Advantages / disadvantages

| Option | Advantages | Disadvantages |
|---|---|---|
| **A** | Composes with WP-07's existing transactions; **no nesting error**; preserves `FAILED_PERMANENT` avoidance | Requires a `nocommit` helper and careful call ordering |
| **B** | Simple, self-contained | **Raises `OperationalError`** whenever nested — guaranteed `DEF-002` stall in `watch_conversation`, `unwatch_conversation`, `reply_prompt`, `open_conversation` |
| **C** | Fewer writes for read-only menus | Two consumption rules; `status:` replay becomes possible (low impact but inconsistent) |
| **D** | Simplest | Replay of `deleteok:`/`watch:` — **unacceptable** |

### 6. Security implications
- B is a **reliability/security hazard**: a stale tap on a watched conversation would stall polling.
- C leaves read-only tokens replayable (minor, but removes a uniform guarantee).
- D permits replay of destructive actions — **rejected outright**.

### 7. Reliability / concurrency implications
**A is the only option compatible with WP-07's transaction ownership.** It also preserves the
`DEF-002` guarantee that `_classify_failure` is never reached from a token path.

**Precise consumption contract recommended:**

1. **Single-use per token** (one successful resolution → `consumed_at` set).
2. Consumption is written **inside the caller's existing transaction** via a `nocommit` helper; the
   resolver **never** opens its own transaction.
3. The `UPDATE … WHERE consumed_at IS NULL` predicate is retained as the race guard (`rowcount == 0`
   → "raced").
4. A token consumed before a downstream failure **stays consumed**. Rationale: the user can re-render
   the menu; retaining a token after a failed mutation invites duplicate side effects.
5. **No exactly-once claim.** This is at-most-once effect per token, not exactly-once Telegram
   delivery.

### 8. Architectural implications
A introduces a `nocommit` helper — the **established** pattern in this codebase
(`_set_last_state_nocommit`, `_add_watched_nocommit`, `mark_update_outcome(..., commit=False)`).

### 9. Dependencies
Depends on O-3 (where pruning runs) and O-5 (schema).

### 10. Recommended option
**A — single-use for all scopes, transaction-composing consumption.** **Option B must be rejected**
despite being what the spec currently describes.

### 11. Confidence
**HIGH** — the nesting failure was reproduced, and the classification path was verified.

### 12. Explicit owner approval required?
**Yes** (`O-4`) — and the owner should be told the spec's original mechanism is defective.

### 13. What remains blocked until approval
The consumption helper's signature, and any handler that both consumes and writes.

---

# O-5 — Hard schema approval gate: 17 → 18

### 1. Exact question
Is a new `callback_refs` table strictly necessary, and is the migration safe?

### 2. Current proposal
One new table + two indexes, added via `CREATE TABLE IF NOT EXISTS` in `_init_schema`.

### 3. Relevant evidence — all measured

| Check | Result |
|---|---|
| Current live tables | **17** |
| `_init_schema` mechanism | `executescript(...)` with `IF NOT EXISTS` — **idempotent** |
| Re-open (restart) simulation | 17 → 17, **no error** |
| Add table then re-init | 17 → 18, **no error** |
| `foreign_keys` | **ON** |
| `journal_mode` | **wal** |
| `busy_timeout` | **5000** |
| Existing table with same shape | `web_sessions` (`TEXT PK`, `REAL created_at/expires_at`, indexed expiry) |

**Could an existing table serve?** No. `web_sessions` is keyed by `token_hash` for Mini App sessions
with a `profile` blob and `user_id`; `processed_updates` is keyed by `update_id`; `user_state` holds
one row per user. None can store `(token → conversation_id, action_scope)` without contorting an
existing contract. A new table is **strictly necessary**.

### 4. Available options

| Option | Description |
|---|---|
| **A** | New `callback_refs` table (17 → 18) |
| **B** | Reuse/overload an existing table | 
| **C** | No table (in-memory / stateless encoding) |

### 5. Advantages / disadvantages

| Option | Advantages | Disadvantages |
|---|---|---|
| **A** | Clean contract; restart-persistent; indexed expiry; mirrors `web_sessions` | +1 table; requires WP-08 doc sync (O-6) |
| **B** | No table-count change | Overloads an unrelated contract; high regression risk in `processed_updates`/`user_state` |
| **C** | No schema change | **Fails the restart-persistence requirement**; breaks the single-owner SQLite model |

### 6. Security implications
A is auditable and per-user bound. C loses ownership binding across restarts.

### 7. Reliability / concurrency implications
Migration is **idempotent and self-healing**: an interrupted `executescript` simply re-runs on next
boot. `IF NOT EXISTS` means a partially-created table is not re-created. **No down-migration exists**
and none is proposed; rollback leaves an inert table (safe).

### 8. Architectural implications
**This is the hard gate.** The baseline (`§WP-06`, line 671) requires the schema addition to feed
into WP-08. Adding a table is an approved-architecture event, not a convenience.

### 9. Dependencies
**Blocks on O-6** (WP-08 doc sync must land in the same change — see below). No dependency on WP-07
completion, but WP-07's `db.py` edits must be committed first to avoid a conflict.

### 10. Recommended option
**A — new `callback_refs` table.** The schema change is safe, idempotent, restart-tolerant, and
strictly necessary.

> **This recommendation does not authorize the migration.** The owner must explicitly approve the
> `17 → 18` transition. No migration may run until that approval is recorded.

### 11. Confidence
**HIGH** — every migration property was executed, not assumed.

### 12. Explicit owner approval required?
**YES — mandatory hard gate.** No schema change may occur without a recorded owner decision.

### 13. What remains blocked until approval
All DDL, the table creation, and any code referencing `callback_refs`.

---

# O-6 — WP-08 dependency and coupling

### 1. Exact question
Must WP-06 Part 2 precede WP-08, or can they proceed independently?

### 2. Current proposal (spec §15)
"Accept that the new table must be reflected in WP-08" — treated as documentation coupling only.

### 3. Relevant evidence — this is **stronger** than the spec states

`tests/test_doc_code_parity.py:88-90` (the `NEW-DEF-08` parity test) contains:

```python
tables = _schema_tables()
assert f"**{len(tables)}** جدول" in RUNBOOK
```

The runbook currently states **17** (`docs/OPERATIONS_RUNBOOK.md:86`). Verified:

```
tables now: 17
runbook asserts '**17** جدول' -> True
SIMULATION: if callback_refs were added (18 tables):
  assertion f'**18** جدول' in RUNBOOK -> False
  => parity test WOULD FAIL unless runbook updated in same commit
```

**This is not "documentation-only coupling."** Adding the table **breaks a live test** unless
`docs/OPERATIONS_RUNBOOK.md` is updated in the same change.

### 4. Available options

| Option | Description |
|---|---|
| **A** | WP-06 Part 2 updates the runbook table count + table list **atomically** with the DDL |
| **B** | WP-06 Part 2 lands first; WP-08 fixes docs later (test fails in between) |
| **C** | WP-08 completes first at 17 tables; WP-06 Part 2 reopens it |

### 5. Advantages / disadvantages

| Option | Advantages | Disadvantages |
|---|---|---|
| **A** | CI stays green; no broken intermediate state | Slightly widens WP-06 Part 2's file set (1 doc file) |
| **B** | Clean package separation | **Red CI** between the two changes — unacceptable |
| **C** | WP-08 done once | WP-08 must be reopened; docs churn twice |

### 6. Security implications
None.

### 7. Reliability / concurrency implications
None — documentation and a parity test.

### 8. Architectural implications
A keeps the "one authoritative schema, one authoritative doc" invariant intact.

### 9. Dependencies
WP-08 depends on the **final table set**, which `callback_refs` changes. So the dependency is
**real and bidirectional in effect**: WP-08 cannot be "final" before WP-06 Part 2 decides.

### 10. Recommended option
**A — atomic update.** WP-06 Part 2 must update `docs/OPERATIONS_RUNBOOK.md` §4 (count 17→18 and add
`callback_refs` to the list) **in the same commit** as the DDL.

**Also:** WP-08 can otherwise proceed **independently** — it covers 20 env vars, `start.sh`, runbook
sections, and API notes, none of which `callback_refs` affects.

### 11. Confidence
**HIGH** — the test assertion and its breakage were executed.

### 12. Explicit owner approval required?
**Yes** (`O-6`) — the owner should accept that WP-06 Part 2 touches one WP-08-owned document.

### 13. What remains blocked until approval
Whether WP-06 Part 2 may edit `docs/OPERATIONS_RUNBOOK.md`.

---

# O-7 — WP-07 sequencing and concurrency

### 1. Exact question
Can `callback_refs` be implemented while WP-07's work is uncommitted, or must WP-07 land first?

### 2. Current proposal (spec §15)
"Independent (no shared files beyond `handlers.py`)."

### 3. Relevant evidence — the spec **understates** this significantly

**WP-07's work is large and entirely uncommitted:**

```
bot/db.py       | 269 insertions, 66 deletions
bot/handlers.py | 176 changed lines
bot/watcher.py  |  18 changed lines
total: 420 insertions(+), 109 deletions(-)
100 WP-07 tests passing (untracked)
```

**Function-level overlap measured** (`git diff -U0 bot/handlers.py` → 17 functions touched):

| Overlap | Handlers `callback_refs` must instrument |
|---|---|
| **4 direct** | `open_conversation`, `reply_prompt`, `unwatch_conversation`, `watch_conversation` |

**Transaction-ownership conflict (the serious one):** WP-07 adds `BEGIN IMMEDIATE` methods
(`add_watched_and_record_outcome`, `set_awaiting_and_record_outcome`,
`clear_awaiting_and_record_outcome`, `remove_watched`) called from those same handlers. A
self-contained consuming `BEGIN IMMEDIATE` would **nest** and raise
`OperationalError` → `FAILED_PERMANENT` (audit D-1, reproduced).

### 4. Available options

| Option | Description |
|---|---|
| **A** | Commit/stabilize WP-07 first, then implement WP-06 Part 2 on top |
| **B** | Implement WP-06 Part 2 concurrently on the same working tree |
| **C** | Implement WP-06 Part 2 on a separate branch from `52e7789` without WP-07 |

### 5. Advantages / disadvantages

| Option | Advantages | Disadvantages |
|---|---|---|
| **A** | Clean base; transaction model settled; no merge conflicts | Serializes two packages |
| **B** | Parallel progress | **Guaranteed conflicts** in 4 handlers + `db.py`; transaction semantics undefined mid-flight; risks entangling uncommitted work |
| **C** | Isolation | WP-06 Part 2 would lack WP-07's transaction helpers and would need rebasing later; the `BEGIN IMMEDIATE` conflict resurfaces on merge |

### 6. Security implications
B is the riskiest: mixing two uncommitted work packages in the same functions makes it impossible to
attribute a regression, and could corrupt the user's existing WP-07 work — explicitly forbidden by
the batch rules.

### 7. Reliability / concurrency implications
The transaction contract **must** be settled before `callback_refs` consumption is designed. WP-07
defines how those handlers own transactions; `callback_refs` must compose with it.

### 8. Architectural implications
Sequencing, not architecture. Both preserve one SQLite owner and sequential polling.

### 9. Dependencies
Depends on WP-07 completion **and** on O-4 (the consumption contract that composes with WP-07's
transactions).

### 10. Recommended option
**A — stabilize (commit) WP-07 before implementing WP-06 Part 2.**

The spec's "independent" claim is **not supportable**: 4 cid-bearing handlers are already modified,
and the transaction pattern conflicts. Recommend the owner treat O-7 as **sequenced, not independent**.

### 11. Confidence
**HIGH** — overlap and transaction conflict both measured.

### 12. Explicit owner approval required?
**Yes** (`O-7`), and it changes the spec's stated answer.

### 13. What remains blocked until approval
Any implementation touching `handlers.py`/`db.py` — i.e. all of WP-06 Part 2.

---

## Cross-decision dependency map

```
O-5 (schema gate) ──┬──► O-1 (token column width)
                    └──► O-2 (expires_at index)
O-2 ──► O-3 (prune batch size)
O-4 (consumption contract) ──► O-3 (insert-path cap placement)
O-7 (WP-07 committed) ──► O-4 (transaction composition) ──► implementation
O-6 (runbook atomic update) ──► O-5 (DDL landing)
```

**Hard blocking chain:** `O-5` and `O-7` must be resolved **before any code**. `O-4` must be
resolved **before any consumption helper**. `O-6` must be resolved **with** `O-5`.

---

## Summary table

| ID | Recommended | Confidence | Approval | Blocks |
|---|---|---|---|---|
| O-1 | 12 chars retained | HIGH | Yes | Token column, payloads |
| O-2 | 30 min / 5000 / 200, **cap mandatory** | HIGH | Yes | TTL, index, prune |
| O-3 | Boot hook + insert-path cap, **no sweeper** | HIGH | Yes | Cleanup wiring |
| O-4 | Single-use all, **transaction-composing** | HIGH | Yes | Consumption helper |
| O-5 | New table, **hard gate** | HIGH | **YES (mandatory)** | All DDL |
| O-6 | Atomic runbook update | HIGH | Yes | Doc ownership |
| O-7 | **Sequence after WP-07** | HIGH | Yes | All implementation |
