# OHB2 — WP-06 Part 2 — Design Remediation Report (Revision 2)

**Task ID:** `OHB2-WP06-PART2-DESIGN-REMEDIATION`
**Date:** 2026-11-19
**Baseline:** HEAD `52e7789cc8cc97a7f7c09c9592226ab117db99a2` (== `origin/main`, 0/0)
**Revised document:** `docs/design/OHB2-WP06-PART2-CALLBACK-REFS-DESIGN-SPEC.md` (674 → **970** lines)
**Input:** `docs/reviews/OHB2-WP06-PART2-DESIGN-INTEGRITY-AUDIT.md` (D-1 … D-6)

## Verdict

# `DESIGN_CORRECTED_WITH_NOTES`

All six findings are corrected and re-verified against the **current working tree**. "WITH_NOTES"
reflects three items that cannot be closed by design alone:

1. **`watcher.unwatch` transaction composability** is not verifiable from source alone (§D-1 below).
2. **Performance figures are inherited**, not re-measured, because measuring them would require
   implementing the table (forbidden in this batch).
3. **Owner decisions O-1 … O-7 remain open.** A corrected design is not an approved design.

---

## D-1 — Critical transaction-composition defect

### Original claim (Revision 1)
Consumption should "mirror the proven `take_awaiting()` pattern": a **standalone**
`BEGIN IMMEDIATE` transaction that takes the write lock, reads, updates, and commits.

### Why it was wrong
Four of the fourteen target handlers already own a `BEGIN IMMEDIATE` transaction. A nested
`BEGIN IMMEDIATE` raises `OperationalError: cannot start a transaction within a transaction`, which
`is_transient_sqlite_error()` classifies as **non-transient** → `FAILED_PERMANENT` → the `DEF-002`
polling stall the design exists to prevent.

### Source evidence (re-verified this task)

**`take_awaiting` is dead code — the precedent was already superseded:**
```
$ grep -rn "take_awaiting(" bot/ | grep -v "def take_awaiting"
(no results — zero callers)

$ grep -n "def take_awaiting\|def awaiting_state" bot/db.py
2880:    def awaiting_state(
3265:    def take_awaiting(

$ grep -rn "awaiting_state(" bot/ | grep -v "def awaiting_state"
bot/handlers.py:2165, 2405, 2519   ← live path
```

**The 4 handlers that own a transaction (measured exhaustively, including indirect calls):**
```
open_conversation      -> set_awaiting_and_record_outcome      (direct BEGIN IMMEDIATE)
watch_conversation     -> add_watched_and_record_outcome       (direct BEGIN IMMEDIATE)
unwatch_conversation   -> _remove_watched_with_retry -> remove_watched / watcher.unwatch
                                                               (BEGIN IMMEDIATE at db.py:2093)
reply_prompt           -> set_awaiting_and_record_outcome      (direct BEGIN IMMEDIATE)

TOTAL: 4 of 14 cid-bearing handlers
```

**The composition convention already exists — 13 `_nocommit` helpers:**
```
bot/db.py::_insert_attachment_item_nocommit   _add_watched_nocommit
_remove_watched_nocommit                      _remove_watched_completing_nocommit
_tombstone_nocommit                           _begin_attempt_nocommit
_set_remote_state_nocommit                    _clear_tombstone_nocommit
_set_last_state_nocommit                      _set_awaiting_nocommit
_clear_awaiting_nocommit                      _mark_processed_nocommit
_upsert_completion_pending_nocommit
```
Plus the `commit=False` / `_commit=False` parameter variant used by `mark_update_outcome`,
`record_notification_sent`.

### Corrected design (spec §8.2-§8.5)
- **Transaction ownership rule:** the **caller** owns the boundary. The helper
  `consume_callback_ref_nocommit(...)` performs SQL only and **never** opens, commits, or rolls back.
- **Two safe modes:** *composed* (inside the caller's existing transaction) and *self-wrapped* (a
  short handler-owned transaction that commits before any other transactional call).
- **Hard prohibition** inside the 4 transaction-owning handlers.
- **Rollback/atomicity:** consumption commits together with the handler's durable record or not at
  all — **stronger** than Revision 1, which could commit a consumption and then fail the record write.

### Affected handlers — exact list
`open_conversation`, `watch_conversation`, `unwatch_conversation`, `reply_prompt`.

### Unresolved assumption
`watcher.unwatch` is **not** a `Database` method (it is an external object supplied via
`bot_data`/watcher). Its transaction behavior cannot be established from the `Database` source. If it
cannot compose, `unwatch_conversation` must use self-wrapped mode with the consume committed first.
**Recorded in spec §8.5 and §10.6.**

### Security implications
None adverse. The correction removes a reliability defect that could stall polling, which is itself a
security-relevant availability property.

---

## D-2 — Incorrect security claim

### Original claim (Revision 1)
"The existing conversation-ID validator rejects callback tokens," and an unresolved token "cannot
reach OpenHands."

### Measured reality (re-verified this task)
```
is_valid_conversation_id(token)                → True
authorize_conversation_detailed(spy, id, token, None):
    remote calls: [['az4cmuldsx0o']]     ← CALL IS MADE
    status: FileStatus.NOT_FOUND
    authorized: False
2000/2000 generated tokens pass is_valid_conversation_id
```
The token **does** reach the remote API. Safety holds (no action authorized); the stated *mechanism*
was wrong.

### Corrected design (spec §3.4, §6.2, §10.6, §13)
- Explicit **five-layer boundary table**: token validation / local resolution / remote lookup /
  action authorization / action prevention — with what each does and does not guarantee.
- **Preventing an action** ≠ **preventing a remote lookup**; only resolving *before* any
  authorization helper prevents the lookup.
- **Ordering corrected:** resolve (step 3) must precede `_authorized_conversation_status` (step 6).
- **Required test:** spy client asserts `client.calls == []` for stale/unknown tokens.

### Security implications
No weakening. The correction makes the risk *more* accurately stated and adds a discriminating test
that would previously have been written to pass vacuously.

---

## D-3 — Source references

### Original problem
Revision 1 used bare line numbers against committed HEAD; the working tree carries WP-07 changes
(`bot/db.py` +269 lines, `bot/handlers.py` +176), so those numbers drift.

### Corrected design
- Header adds an explicit **line-number policy**: point-in-time references; **symbol names are
  authoritative**.
- §2.3 helper table now uses `module::symbol` locations (e.g. `bot/db.py::_init_schema`).
- Prose references converted from `db.py:5329` → `bot/db.py::Database` healthcheck, etc.
- `bot/app.py:121-155` → `bot/app.py::_register_handlers`.

### Verification
`grep` for the old stale forms returns **zero** matches (verified).

---

## D-4 — Callback payload length

### Original claim (Revision 1)
`files:` = 54, `file:` = 54, presented as **fixed constants**.

### Measured reality (re-verified this task, all 16 shapes)
Single-segment (exact):

| Shape | Safe max cid |
|---|---|
| `deleteok:{cid}` | **55** |
| `unwatch:{cid}` | **56** |
| `delete:`/`status:`/`export:` | 57 |
| `watch:`/`reply:` | 58 |
| `cost:`/`open:`/`full:`/`copy:` | 59 |
| `txt:{cid}` | 60 |

Two-segment (digit-width dependent):

| Shape | gen/idx digits | Safe max cid |
|---|---|---|
| `files:{cid}:0` | — | 56 |
| `files:{cid}:{gen}:{page}` | 1/1 | **54** |
| `files:{cid}:{gen}:{page}` | 1/2 | 53 |
| `files:{cid}:{gen}:{page}` | 2/3 | 51 |
| `files:{cid}:{gen}:{page}` | 4/5 | **47** |
| `file:{cid}:{gen}:{idx}` | 1/1 | **55** |
| `file:{cid}:{gen}:{idx}` | 1/2 | 54 |
| `file:{cid}:{gen}:{idx}` | 2/3 | 52 |
| `file:{cid}:{gen}:{idx}` | 4/5 | **48** |

### Corrections applied
1. `file:` = **55**, not 54 (Revision 1 was off by one; `_btn()` rejects only `> 64`, so exactly 64
   is valid).
2. Limits are **ranges**, not constants — `files:` spans 47-56, `file:` spans 48-55.
3. **Measurement method recorded** (increment cid length until `_btn()` raises).
4. **Why widths vary:** `gen` is `bot/file_cache.py::FileCache.put`'s monotonic per-process cursor
   (unbounded); the file index is `page*FILES_PAGE_SIZE + offset`.

### Token sizing conclusion
A 12-char token leaves **35 bytes** of headroom at the worst realistic width (47 − 12) and survives
even 20-digit numeric fields (~52 B). Token sizing is **safe**.

### Unresolved assumption
`gen` is monotonic and unbounded in principle. At 20+ digits the margin narrows but the token still
fits; a defensive assertion in the builder is recommended at implementation time.

---

## D-5 — Handler count

### Original claim
**15** cid-bearing handlers, with `list_conversations`/`list_watches` inconsistently included.

### Measured reality (re-enumerated from source)
**Exactly 14.** Verified table now includes handler symbol, callback family, authorization path,
**transaction exposure**, and token-resolution behavior (spec §2.2).

The 4 non-cid handlers are now listed separately and correctly: `list_conversations`,
`list_watches`, `repos_page`, `pick_repo`.

### Corrections applied
- Count corrected 15 → 14 everywhere (spec §2.2, §10.1, §10.2, §13.2).
- Added the transaction-exposure column, which is what makes D-1's risk surface visible.

---

## D-6 — Sweeper typing and lifecycle

### Original claim
The `OpportunisticSweeper` was offered as an optional second cleanup hook.

### Measured reality (re-verified)
```python
# bot/attachments.py::OpportunisticSweeper
def __init__(self, reaper: AttachmentReaper, *, min_interval=..., clock=None):
    self._reaper = reaper        # hard-typed
```
Its lifecycle is bound to `AttachmentReaper.sweep` (`_last_attempt_at`, `_last_success_at`,
`_running` re-entrancy guard). It cannot serve `callback_refs` without either modifying
`bot/attachments.py` (out of scope; also touched by WP-07) or writing a parallel sweeper (a new
worker-like component — architecture violation).

### Corrected design (spec §5.1)
**Sweeper route rejected.** Adopted: **boot maintenance hook + mandatory insert-path row cap**.
The insert-path cap is now stated as a **correctness requirement**, not optional defence-in-depth,
because it is the only growth bound in a long-lived process that never restarts.

---

## Additional design requirements — preserved and re-evaluated

| Requirement | Status |
|---|---|
| 12-char token | **Preserved**, headroom re-measured (35 B worst case) |
| 30-min TTL | Preserved |
| 5,000-row cap | Preserved; **insert-path cap made mandatory** |
| 200-row prune batch | Preserved |
| Single-use semantics | Preserved; contract now transaction-composing |
| Cleanup at existing hooks only | Preserved; sweeper route removed |
| 17 → 18 schema migration | Preserved; idempotency re-verified |
| FK / WAL assumptions | Re-verified: `foreign_keys=ON`, `journal_mode=wal`, `busy_timeout=5000` |
| Authorization / ownership binding | Preserved |
| Bounded resource usage | Strengthened (mandatory cap) |
| No new worker/queue/service | Preserved; sweeper rejected |

### Measurements: still applicable vs. must be repeated

| Measurement | Status |
|---|---|
| `_init_schema` idempotency (17→17→18) | **Re-verified this task** — applicable |
| WAL / FK / busy_timeout preserved | **Re-verified this task** — applicable |
| Payload boundaries (all 16 shapes) | **Re-measured this task** — applicable |
| 2000/2000 token ambiguity | **Re-verified this task** — applicable |
| Unresolved token reaches remote | **Re-verified this task** — applicable |
| `take_awaiting` zero callers | **Re-verified this task** — applicable |
| 4-of-14 transaction ownership | **Re-measured this task** — applicable |
| Runbook parity breakage | **Re-verified this task** — applicable |
| Consume latency ≈1.2 ms @ 5,000 rows | **Inherited** — must be re-measured after implementation (needs the real table) |
| Prune 200 rows ≈1.6 ms | **Inherited** — must be re-measured after implementation |

> The design change (transaction-composing consumption) does **not** invalidate the latency
> measurements' order of magnitude, but they were taken against a prototype, not the shipped
> helper. They must be repeated at implementation time.

---

## Remaining owner decisions

O-1 … O-7 are **all still open**. See spec §15 and the TASK-B analysis. **Nothing in this
remediation authorizes implementation.**

---

## What was NOT changed

- No production code, test, schema, migration, payload, Mini App, WP-07, or WP-08 change.
- The runbook was **not** modified (O-6 requires it at *implementation* time, not now).
- No commit, push, PR, merge, deploy, or release.
