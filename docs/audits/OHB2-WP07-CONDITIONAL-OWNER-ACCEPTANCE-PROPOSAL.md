# OHB2 — WP-07 Conditional Owner Acceptance Proposal

**Task ID:** `OHB2-WP07-FINAL-STABILIZATION-AUDIT-AND-OWNER-ACCEPTANCE-PACKAGE`
**Date:** 2026-11-19
**Status:** **PROPOSAL ONLY — NOT REGISTERED, NOT FINALIZED**
**Recorded by:** AI agent (OpenHands) on behalf of the repository owner.

> ## ⚠ This is a proposal, not an acceptance
>
> **No owner acceptance is granted by this document.** It proposes a structure for a future owner
> decision. The owner must issue a separate, explicit decision to make any of it effective.
>
> If the owner later accepts, that acceptance **does not authorize** Git publication (commit, push, PR,
> merge), deployment, release, Autopush activation, or any WP-06 Part 2 implementation.

---

> ## ⚠ LATER CORRECTION — 2026-11-21 (append-only; the historical text above and below is unchanged)
>
> This proposal was written on **2026-11-19** and is preserved **as-is** as the authoritative record of
> what was proposed then. Two of its statements about `DEF-011` are **superseded** and must not be read
> as current-state claims:
>
> | Historical statement | Location | Status |
> |---|---|---|
> | "an entirely **unimplemented** finding (DEF-011)" | §1, bullet 3 | **SUPERSEDED** — see below |
> | Reservation **R9** "DEF-011 is entirely unimplemented … 0 `to_thread` in `attachments.py`" | §5 | **PARTLY SUPERSEDED** — see below |
>
> **DEF-011 is NOT fully implemented and NOT closed.** Its three sub-defects have different status:
>
> | Sub-defect | Scope | Status as of 2026-11-21 |
> |---|---|---|
> | **`DEF-011-B`** — filesystem offload off the event loop | `WP-07` | **IMPLEMENTED.** `bot/attachments.py` contains **five** `to_thread` occurrences (module import, one docstring reference, and three `anyio.to_thread.run_sync` call sites); `bot/handlers.py` offloads `_read_local_capped`. |
> | **`DEF-011-A`** — cross-download quota reservation ledger | `WP-07` | **NOT IMPLEMENTED.** No reservation/in-flight byte accounting exists. Blocked by `D-12` / `OD-04`. |
> | **`DEF-011-C`** — attachment acceptance UX copy | `WP-01` | **NOT IMPLEMENTED.** Blocked on `OD-01` / `OD-03`. |
>
> **Reading rules:**
>
> - The historical "0 `to_thread` in `attachments.py`" observation was accurate on 2026-11-19 and is
>   **no longer true**. It is a historical observation, **not** a current-state claim.
> - The second half of R9 — "0 quota ledger" — **remains accurate**: no reservation ledger exists, so
>   `DEF-011-A` is still open.
> - Because `DEF-011-A` and `DEF-011-C` remain unimplemented, `DEF-011` **remains open**. Reading the
>   superseded lines as proof that `DEF-011` is closed, or that A, B and C are all implemented, would be
>   incorrect.
>
> **Unaffected sections.** §2.2 ("Verification against the current tree") remains accurate for items
> A-1…A-5 and is unchanged. §7 ("Explicit non-authorizations") is a **normative** statement of the
> authorization boundary that applied when this proposal was written — it is **not** a claim about the
> code and is unchanged. Neither section is corrected, reinterpreted, or converted into a present-day
> implementation claim by this notice.
>
> This correction is **additive only**. No historical sentence was edited or deleted.

---

## 1. Why the scope must be split

The working tree contains **more work than was previously accepted**. Accepting "WP-07" as one block
would silently absorb:

- six navigation handlers (NAV-01..06) implemented **after** the prior acceptance record and **not
  recorded** in `.agent/PROGRESS.md`;
- a committed DEF-006 comment block whose architectural decision (**OD-04**) is **still unresolved**;
- an entirely **unimplemented** finding (DEF-011).

Therefore this proposal separates **Scope A** (previously accepted non-concurrency work) from
**Scope B** (DEF-006 / concurrency, OD-04-blocked), and treats the NAV work as a **third, explicitly
unaccepted** scope requiring its own decision.

---

## 2. Scope A — Previously accepted non-concurrency work

### 2.1 Exact accepted boundary (historical record)

Source: `.agent/PROGRESS.md:4272` — `NEW-DEF-03_NON_CONCURRENCY_OWNER_ACCEPTED`.

The prior acceptance covered **exactly five items**:

| # | Item |
|---|---|
| A-1 | `watch_conversation` atomicity (`add_watched_and_record_outcome`, `_add_watched_nocommit`, `_set_last_state_nocommit`) |
| A-2 | `unwatch_conversation` atomicity, both branches (`remove_watched`, `_remove_watched_nocommit`, `remove_watched_completing`, `_remove_watched_completing_nocommit`, `watcher.unwatch`) |
| A-3 | Awaiting-state atomicity (`clear_awaiting_and_record_outcome`, `set_awaiting_and_record_outcome`) |
| A-4 | Backward compatibility for legacy callers (keyword-only optional args defaulting to `None`; single-arg `remover(cid)` preserved) |
| A-5 | F-1 Option C behaviour preserved across the six paths |

### 2.2 Verification against the current tree

| Item | Present? | Evidence |
|---|---|---|
| A-1 | **YES** | `def add_watched_and_record_outcome` ×1 in `bot/db.py` |
| A-2 | **YES** | `def remove_watched_completing` ×1, `_remove_watched_nocommit` ×1 |
| A-3 | **YES** | `def clear_awaiting_and_record_outcome` ×1, `def set_awaiting_and_record_outcome` ×1 |
| A-4 | **YES** | `_remove_watched_with_retry` retains single-arg path |
| A-5 | **YES** | all six handlers defined; 14 F-1 tests pass |

**All five accepted items remain intact and unmodified in substance.**

### 2.3 Recommendation for Scope A

# `ACCEPT_WITH_NOTES` — but only for A-1 … A-5

**Why `ACCEPT_WITH_NOTES` and not plain `ACCEPT`:**

1. The five items are present and behaviourally verified by 102 passing focused tests.
2. **But the tree now also contains unaccepted NAV work** (§3), so a blanket "Scope A unchanged"
   statement would be false. Acceptance must be **explicitly bounded** to A-1..A-5.
3. Independent review remains unavailable (reservation R1).

**Why not `REQUIRES_REOPENING`:** no accepted item regressed; nothing in A-1..A-5 is broken.

**Why not `BLOCKED`:** Scope A is not gated by OD-04.

---

## 3. Scope A′ — NAV-01..06: unaccepted additional work (must be decided separately)

### 3.1 What exists [FACT]

| Subtask | Handler | Markers | Test file | Lines |
|---|---|---|---|---|
| NAV-01 | `start` | `handlers.py:898` | `test_wp07_nav01_nav03_nav04_atomic.py` | 415 (shared) |
| NAV-02 | `show_menu` | `handlers.py:959` | `test_wp07_nav02_nav05_simple_clear_atomic.py` | 295 (shared) |
| NAV-03 | `list_conversations` | `handlers.py:1076`, `:1101` | `test_wp07_nav01_nav03_nav04_atomic.py` | shared |
| NAV-04 | `list_watches` | `handlers.py:1387` | `test_wp07_nav01_nav03_nav04_atomic.py` | shared |
| NAV-05 | `start_new_chat` | `handlers.py:2687` | `test_wp07_nav02_nav05_simple_clear_atomic.py` | shared |
| NAV-06 | `open_conversation` | `handlers.py:1199` | `test_wp07_nav06_open_conversation_atomic.py` | 250 |

All six are implemented, all tests pass, and the implementation is coherent with the A-1..A-5 model
(reuses `clear_awaiting_and_record_outcome` / `set_awaiting_and_record_outcome`).

### 3.2 Why it is not covered by the prior acceptance

The prior acceptance record states verbatim that the navigation sweep is **open and not done**:

> **بقية مواقع `NEW-DEF-03`** (مسح التنقّل + مسارات النية الدائمة) — **مفتوحة**، غير منفَّذة.

The NAV code was added **after** that record. It has **no acceptance record**, and
`.agent/PROGRESS.md` still describes the nav sweep as unimplemented (2 mentions, both negative).

### 3.3 Recommendation for Scope A′

# `REQUIRES_SEPARATE_OWNER_DECISION`

**Options for the owner:**

| Option | Meaning |
|---|---|
| **A′-1 Accept** | Extend acceptance to NAV-01..06 on the same basis as A-1..A-5. |
| **A′-2 Accept with conditions** | Accept but require a PROGRESS.md record entry + mutation proof per NAV handler. |
| **A′-3 Defer** | Leave NAV unaccepted; exclude from any baseline; keep in the working tree. |
| **A′-4 Reject** | Revert NAV work (requires explicit owner authorization; agent must not do this unilaterally). |

**Agent recommendation: A′-2** — the work is sound and tested, but it lacks a documentation record and
per-handler mutation proof, which the rest of WP-07 has.

---

## 4. Scope B — DEF-006 and concurrency

### 4.1 State [FACT]

| Question | Answer |
|---|---|
| Committed? | `bot/app.py:75-89` DEF-006 comment + `.concurrent_updates(True)` — **committed in HEAD** |
| Working tree? | **No concurrency changes** — 0 `asyncio.Lock`/`concurrent`/`gather(` additions |
| Active behaviour? | Flag is set, but `TelegramPoller.process_updates` awaits `dispatch_and_wait` (`put` → `join`) per update ⇒ **sequential at runtime**; flag effectively inert across updates |
| Proposed but unauthorized? | Option 2 intra-batch concurrency (needs OD-04 + formal SQLite/per-user proof) |
| Does the committed change need an owner decision? | **YES.** OD-04 is unresolved. A committed comment matching the baseline's preferred Option 1 is **not** owner approval of the architectural decision. |

### 4.2 Recommendation for Scope B

# `BLOCKED_PENDING_OD04`

**Rationale:** the baseline states DEF-006 requires either (Option 1) comments-only alignment — which
appears done — or (Option 2) concurrency with formal proof and OD-04 sign-off. Since **OD-04 has no
recorded owner decision**, the architectural choice is **not ratified**, even though the code currently
behaves sequentially.

**Scope B is NOT included in Scope A** and must not be silently absorbed.

---

## 5. Reservations (evidence-supported only)

| # | Reservation | Evidence |
|---|---|---|
| **R1** | **Independent technical review was NOT completed.** | `INDEPENDENCE_NOT_ESTABLISHED` in both WP-07 reports; no separate session/host; Docker absent; provider-connections empty |
| **R2** | The `INDEPENDENCE_NOT_ESTABLISHED` verdict is **unchanged** and not superseded. | Same |
| **R3** | **Historical test results were NOT independently reproduced.** | The 3332-passed figure is from `.agent/PROGRESS.md`; this task measured 3385 (a different number, different tree state) |
| **R4** | **Mutation results were NOT independently reproduced.** | M1–M5 (WP-07) and 8/8 (WP-05) are prior self-reports; not re-executed |
| **R5** | **The implementation is uncommitted.** | `staged = 0`; `bot/db.py`, `bot/handlers.py`, `bot/watcher.py` modified but uncommitted |
| **R6** | **Tests are untracked.** | 6 WP-07 test files untracked (plus 1 non-WP-07 F-03 file) |
| **R7** | **Mixed HEAD / working-tree state.** | DEF-006 + DEF-013 committed; atomicity + NAV uncommitted |
| **R8** | **Unaccepted NAV scope present in the tree.** | §3 — 7 markers, 3 test files beyond the accepted five items |
| **R9** | **DEF-011 is entirely unimplemented** while inside WP-07's authoritative scope. | 0 `to_thread` in `attachments.py`; 0 quota ledger |
| **R10** | **OD-04 unresolved** — DEF-006 architecture not ratified. | No owner decision record found |
| **R11** | **Unverified architecture assumption:** WP-05/WP-07 hunks in `bot/db.py` are assumed separable by hunk. | Not verified at hunk level in this read-only audit |
| **R12** | **No operational surface for `update_failures`** — pre-existing gap. | Prior reports; not re-verified |

---

## 6. Proposed decision structure

If the owner wishes to proceed, **three separate decisions** are required:

| Decision | Scope | Proposed disposition |
|---|---|---|
| **D-A** | Scope A (A-1..A-5) | `ACCEPT_WITH_NOTES` |
| **D-A′** | NAV-01..06 | `REQUIRES_SEPARATE_OWNER_DECISION` (recommend A′-2) |
| **D-B** | DEF-006 / concurrency | `BLOCKED_PENDING_OD04` |

A single blanket "accept WP-07" is **not** recommended and would be inaccurate.

---

## 7. Explicit non-authorizations

Even if the owner later grants acceptance:

- **No Git publication** — commit, push, PR, merge, tag, or release are **not** authorized.
- **No WP-06 Part 2 implementation** — O-7 remains a separate gate.
- **No deployment or release.**
- **No Autopush activation.**
- **No schema change** — the 17-table baseline remains authoritative (O-5, C-5.7).
- **No DEF-011 implementation.**
- **No OD-04 resolution** — that is a separate owner decision.
- **No scope expansion** beyond what is explicitly named.

---

## 8. What this proposal does NOT do

- It does **not** register or finalize any acceptance.
- It does **not** convert self-verification into independent evidence.
- It does **not** mark E-7.6 or E-7.7 complete in the O-7 readiness assessment.
- It does **not** authorize any Git or implementation action.
