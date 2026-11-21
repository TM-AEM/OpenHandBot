# OHB2 — WP-06 Part 2 — Final Owner Decision Briefing

**Task ID:** `OHB2-WP06-PART2-OWNER-DECISION-BRIEFING`
**Date:** 2026-11-19
**Baseline:** HEAD `52e7789cc8cc97a7f7c09c9592226ab117db99a2` (== `origin/main`, 0/0)
**Inputs:** `OHB2-WP06-PART2-DESIGN-INTEGRITY-AUDIT.md` (`INTEGRITY_VERIFIED_WITH_NOTES`), `OHB2-WP06-PART2-OWNER-DECISIONS-ANALYSIS.md`

> **This briefing recommends. It does not decide, authorize, or record any owner answer.**
> Implementation is **not** authorized by this document.

---

## 1. Executive summary

**Is the design technically sound?**
**Yes, with two material corrections.** The core premise is verified: the 64-byte overflow is real,
`files:`/`file:` are the binding payloads, and a 12-char token resolves the defect with ≥31 bytes of
headroom. The proposed mechanisms (TTL, bounded cleanup, ownership binding, single-use) all map onto
patterns this codebase already uses.

**Two material defects were found and must be corrected before implementation:**

| Defect | What it is | Why it matters |
|---|---|---|
| **D-1** | The spec's atomic-consumption precedent (`take_awaiting`'s self-contained `BEGIN IMMEDIATE`) is **unsafe here** | WP-07 already opens `BEGIN IMMEDIATE` in 4 of the affected handlers. Nesting raises `OperationalError` → classified `FAILED_PERMANENT` → **the `DEF-002` polling stall the design exists to prevent**. Reproduced. |
| **D-2** | The claim that an unresolved token "cannot reach OpenHands" is **overstated** | All 2,000 generated tokens pass `is_valid_conversation_id`; validation happens *after* acceptance as an ID; the remote call **is** made. No action is authorized — safety holds — but the stated mechanism is wrong. |

**Is it ready for owner approval?**
**Yes — as a decision input.** All seven decisions are analyzed with measured evidence. The two
material defects are correctable **within** the design; neither invalidates the architecture.

**Is implementation authorized?**
**NO.** No owner decision has been recorded. No schema change is authorized. O-5 (schema gate) and
O-7 (WP-07 sequencing) both block all code.

**Most important unresolved risks:**
1. **Transaction nesting (D-1)** — the highest-risk item. Must be designed as transaction-composing.
2. **WP-07 is 420 uncommitted lines across the exact functions involved** — implementing now would
   entangle two work packages and risk the user's existing work.
3. **The runbook parity test will fail** the moment the table is added, unless updated atomically.

---

## 2. Seven-decision matrix

| Decision | Recommended option | Confidence | Approval required | Blocking impact |
|---|---|---|---|---|
| **O-1** Token length | **12 chars** (`token_urlsafe(9)`) retained | HIGH | Yes | Blocks token column + all payload formats |
| **O-2** TTL & limits | **30 min / 5,000 / 200**, with **insert-path cap mandatory** | HIGH | Yes | Blocks TTL constants, expiry index, prune scheduling |
| **O-3** Cleanup points | **Boot hook + insert-path cap; no sweeper, no new worker** | HIGH | Yes | Blocks cleanup wiring; sweeper option needs separate architecture approval |
| **O-4** Single-use | **Single-use all scopes, transaction-composing** (reject spec's self-contained `BEGIN`) | HIGH | Yes | Blocks the consumption helper and every handler that consumes |
| **O-5** Schema 17→18 | **New `callback_refs` table** | HIGH | **YES — mandatory hard gate** | Blocks **all** DDL and any code referencing the table |
| **O-6** WP-08 coupling | **Atomic runbook update in the same commit** | HIGH | Yes | Blocks whether WP-06 Part 2 may edit `OPERATIONS_RUNBOOK.md` |
| **O-7** WP-07 sequencing | **Commit/stabilize WP-07 first** (not "independent") | HIGH | Yes | Blocks **all** implementation |

---

## 3. Mandatory gates

### 3.1 Decisions that can be accepted as design parameters
These set values but do not change architecture:
- **O-1** token length
- **O-2** TTL and resource limits

### 3.2 Decisions requiring architectural approval
- **O-3** — if the owner selects the `OpportunisticSweeper` route, that requires modifying
  `attachments.py` (out of scope) → **separate architecture approval**. The recommended option (A)
  does **not** require it.
- **O-4** — choosing transaction-composing consumption changes the helper contract. Recommend
  approval as a design decision, not an architecture change (it uses the **existing** `_nocommit`
  pattern, 12+ precedents).

### 3.3 The hard schema 17→18 gate
**O-5 is a mandatory hard gate.** No DDL, no migration, no `callback_refs` code may land without an
explicitly recorded owner approval of the `17 → 18` transition.

### 3.4 Decisions dependent on WP-07 or WP-08
- **O-7** — depends on WP-07 being committed.
- **O-6** — depends on WP-08's parity test; the runbook must change **with** the DDL.

### 3.5 Unresolved questions that prevent implementation
| # | Question | Owner |
|---|---|---|
| Q-1 | Is transaction-composing consumption (O-4 option A) accepted in place of the spec's self-contained `BEGIN`? | Owner |
| Q-2 | Must WP-07 be committed before WP-06 Part 2 implementation begins? | Owner |
| Q-3 | May WP-06 Part 2 edit `docs/OPERATIONS_RUNBOOK.md` §4 (O-6)? | Owner |
| Q-4 | Is the `17 → 18` schema transition approved? (O-5) | Owner |

---

## 4. Security-critical requirements

Requirements marked **NON-NEGOTIABLE** must be implemented regardless of which options are chosen.

| # | Requirement | Detail | Non-negotiable |
|---|---|---|---|
| S-1 | **Token generation** | `secrets.token_urlsafe(9)`, exactly 12 chars, `PRIMARY KEY`, collision retry ≤3 | **YES** — must use `secrets`, never `random` |
| S-2 | **Centralized resolution** | One resolver; each cid-bearing prefix resolves its segment **unconditionally** | **YES** |
| S-3 | **No unresolved token reaches OpenHands** | Regression test asserts `authorize_conversation_detailed` is never called with an unresolved token | **YES** — this is the D-2 control |
| S-4 | **Ownership binding** | `telegram_id` + `conversation_id` + `action_scope`, all `NOT NULL`, re-verified at consumption | **YES** |
| S-5 | **Atomic consumption** | Transaction-**composing**; `UPDATE … WHERE consumed_at IS NULL` race guard; `rowcount == 0` → raced | **YES** — D-1 correction |
| S-6 | **Never nested `BEGIN IMMEDIATE`** | Resolver must not open its own transaction | **YES** — prevents `FAILED_PERMANENT` stall |
| S-7 | **Expiration** | Strict `now < expires_at`; `now == expires_at` → expired; both timestamps from one clock read | **YES** |
| S-8 | **Bounded cleanup** | `LIMIT`-bounded delete; **insert-path cap mandatory**; never unbounded | **YES** |
| S-9 | **Fail-closed DB behavior** | BUSY/LOCKED → non-fatal, `FAILED_TRANSIENT`; no action on any failure path | **YES** |
| S-10 | **Safe error handling** | `_safe_answer` only; **never** raise into `_classify_failure`; log exception type + token prefix only | **YES** |
| S-11 | **Duplicate callback delivery** | Second delivery → stale message, no action; **no exactly-once claim** | **YES** |

**Explicit non-claim (must be preserved in code comments and docs):** at-most-once effect per token;
**not** exactly-once Telegram delivery; **not** SQLite↔Telegram atomicity.

---

## 5. Recommended implementation sequence

**Dependency-aware. Does not assume all seven decisions are approved.**

### Stage 0 — Blocked on owner (no code)
```
[O-5 schema gate] + [O-7 WP-07 committed] + [O-4 consumption contract]
```
Nothing below may start until these three are resolved.

### Stage 1 — Schema (requires O-5 + O-6)
1. Add `callback_refs` DDL + 2 indexes to `_init_schema`.
2. **Same commit:** update `docs/OPERATIONS_RUNBOOK.md` §4 (17 → 18, add the table name).
3. Verify `tests/test_doc_code_parity.py` still passes.

*Can proceed independently of WP-07 if WP-07's `db.py` edits are committed first.*

### Stage 2 — Token issue path (requires O-1 + O-2 + Stage 1)
4. Token generator + resolver.
5. Insert-path cap (mandatory).
6. Boot-hook prune (`prune_callback_refs`, `LIMIT 200`).

### Stage 3 — Consumption (requires O-4 + Stage 2)
7. `consume_callback_ref_nocommit` (transaction-composing).
8. Wire the 14 cid-bearing handlers **after WP-07's versions are committed**.

### Stage 4 — Verification
9. Mutation-proven tests for S-1 … S-11.
10. Full gate: pytest, pyflakes, bandit, node, doc-parity.

### What can proceed independently
- **WP-08** can proceed now for everything **except** the table count/list (20 env vars,
  `start.sh`, API notes, runbook §3/§9). It must leave §4 for Stage 1.
- **O-1/O-2/O-3 analysis** is complete; only approval is needed.

### What must remain blocked
- **All** `callback_refs` code until O-5 and O-7 are resolved.
- Any consumption helper until O-4 is resolved.
- Any `OPERATIONS_RUNBOOK.md` §4 edit until O-6 is resolved.

---

## 6. Rejected alternatives

| Alternative | Why it must not be selected |
|---|---|
| **Shorten prefixes only** | Insufficient: `files:` still overflows at 47-54 depending on digit width; `deleteok:` fails at 56. Does not solve DEF-010. |
| **Truncate the conversation ID** | Ambiguous (prefix collisions target the wrong conversation) and lossy. **Unsafe.** |
| **Deterministic hash, no table** | Cannot reverse a hash; still needs a table → strictly worse. |
| **In-memory dict** | Fails restart persistence (an explicit DEF-010 requirement); breaks single-owner model. |
| **Base64-encode the ID** | **Expands**: 64 chars → 86 chars. Worse than the defect. |
| **Reusable tokens** | Permits replay of `deleteok:`/`watch:` — **unacceptable**. |
| **New background pruning worker** | **Violates approved architecture** (one bot + ASGI, existing outbox/workers only). |
| **`OpportunisticSweeper` reuse (as-is)** | Hard-typed to `AttachmentReaper`; requires modifying out-of-scope `attachments.py`. No correctness gain over boot hook + insert-path cap. |
| **Self-contained `BEGIN IMMEDIATE` consumption (spec's original)** | **Raises `OperationalError` when nested** in WP-07's handlers → `FAILED_PERMANENT` → polling stall. Reproduced. |
| **Value-sniffing dispatch** (guess token vs. cid by shape) | Every token passes `_ID_RE` (2000/2000), so sniffing is impossible. Must be explicit prefix dispatch. |

---

## 7. Owner decision checklist

> Each item is presented for the owner to accept, reject, defer, or revise.
> **No answer is preselected or recorded.**

### O-1 — Token length and format
- **Recommended choice:** 12 chars, `secrets.token_urlsafe(9)`.
- **If accepted:** every payload fits with ≥31 B headroom; 72-bit entropy; standard `_ID_RE` alphabet.
- **If rejected (e.g. 16 chars):** still fits, but `files:` headroom drops; no security benefit at
  5,000 rows.
- **If deferred:** token column and all payload work remain blocked.

### O-2 — TTL and resource limits
- **Recommended choice:** TTL 30 min, `MAX_ROWS` 5,000, `PRUNE_BATCH` 200, **insert-path cap mandatory**.
- **If accepted:** consume ≈1.2 ms, prune ≈1.6 ms at max size — negligible vs. 5000 ms busy_timeout.
- **If rejected (e.g. TTL 10 min):** more stale menus; consistent with `AWAITING_TTL` but short for paging.
- **If deferred:** TTL constants, expiry index, and prune scheduling remain blocked.

### O-3 — Cleanup integration points
- **Recommended choice:** boot hook + insert-path cap; **no sweeper, no new worker**.
- **If accepted:** zero out-of-scope edits; bounded growth guaranteed.
- **If rejected (sweeper chosen):** requires **separate architecture approval** to modify `attachments.py`.
- **If deferred:** cleanup wiring remains blocked.

### O-4 — Single-use consumption contract
- **Recommended choice:** single-use **all scopes**, **transaction-composing** (`nocommit` helper).
- **If accepted:** composes with WP-07's transactions; `DEF-002` stall avoided.
- **If rejected (spec's self-contained `BEGIN`):** **will raise `OperationalError`** in 4 handlers → `FAILED_PERMANENT`. Strongly advised against.
- **If deferred:** consumption helper and all consuming handlers remain blocked.

### O-5 — Hard schema gate 17 → 18
- **Recommended choice:** approve the new `callback_refs` table.
- **If accepted:** migration is idempotent, restart-tolerant, self-healing; +1 table.
- **If rejected:** DEF-010 cannot be fixed with a persistent design; requires a different (inferior) approach.
- **If deferred:** **all** DDL and all `callback_refs` code remain blocked. **This is a hard gate.**

### O-6 — WP-08 coupling
- **Recommended choice:** update `OPERATIONS_RUNBOOK.md` §4 atomically with the DDL.
- **If accepted:** CI stays green; WP-08 otherwise proceeds independently.
- **If rejected:** `test_doc_code_parity.py` **fails** between the two changes (proven).
- **If deferred:** ownership of the runbook edit is undefined; blocks Stage 1.

### O-7 — WP-07 sequencing
- **Recommended choice:** **commit/stabilize WP-07 first**; treat as sequenced, not independent.
- **If accepted:** clean base; no conflicts in 4 handlers + `db.py`; user's WP-07 work protected.
- **If rejected (concurrent):** guaranteed merge conflicts and undefined transaction semantics mid-flight.
- **If deferred:** **all** implementation remains blocked.

---

## 8. Final readiness verdict

# `READY_WITH_CONDITIONS`

**Rationale:**
The design is technically sound, its core premise is independently verified, and all seven decisions
are analyzed with measured evidence. It is ready to be **put to the owner**.

It is **not** `READY_FOR_OWNER_APPROVAL` without qualification because two material defects (D-1, D-2)
must be corrected in the spec before implementation, and four questions (Q-1 … Q-4) must be answered.

**Conditions:**
1. **D-1 corrected** — consumption must be transaction-composing; the `take_awaiting` precedent must
   be replaced. (Non-negotiable.)
2. **D-2 corrected** — reword the "cannot reach OpenHands" claim.
3. **O-5 and O-7 resolved** before any code.
4. **O-4 resolved** before any consumption helper.
5. **O-6 resolved** with O-5.

**This verdict is a design-readiness statement only. It is not implementation authorization.**
The owner alone decides whether to accept, reject, defer, or revise O-1 … O-7.
