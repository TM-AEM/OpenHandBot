# OHB2 — WP-06 Part 2 — `callback_refs` Design Specification

**Status:** `DESIGN_CORRECTED — NOT AUTHORIZED FOR IMPLEMENTATION`
**Task ID:** `OHB2-WP06-PART2-CALLBACK-REFS-DESIGN-SPECIFICATION`
**Revision:** 2 (2026-11-19) — corrected per `OHB2-WP06-PART2-DESIGN-INTEGRITY-AUDIT` D-1…D-6
**Date:** 2026-11-19
**Defect:** `DEF-010` — 64-Byte `callback_data` Overflow for Valid 56–64 Char Conversation IDs
**Baseline commit:** `52e7789cc8cc97a7f7c09c9592226ab117db99a2`

> This document specifies a design only. It does **not** authorize implementation, schema
> migration, callback-format changes, new workers, or closing WP-06 Part 2. Every numeric
> parameter marked **[OWNER]** is a proposal requiring explicit owner approval.
>
> **Revision 2 note — what changed and why.** An independent integrity audit
> (`docs/reviews/OHB2-WP06-PART2-DESIGN-INTEGRITY-AUDIT.md`) found six defects in Revision 1. The
> two material ones were a **critical transaction-composition defect** (D-1) and an **incorrect
> security claim** (D-2). Revision 2 corrects all six; each correction is marked
> `**[REV-2 D-x]**` inline so the owner can see exactly what moved. **No production code, test,
> schema, or payload was changed by this revision.**
>
> **Line-number policy [REV-2 D-3].** All line numbers in this document are **point-in-time
> references** against the working tree at the date above. `bot/db.py` and `bot/handlers.py` carry
> uncommitted WP-07 work (+269 and +176 lines respectively), so committed-HEAD line numbers differ.
> **Stable symbol names are the authoritative reference**; treat every line number as a hint that
> may drift.

---

## 1. Problem statement and scope

### 1.1 The defect

Telegram hard-caps `callback_data` at **64 bytes** of UTF-8. The bot builds callback payloads by
concatenating a textual prefix with the raw OpenHands `conversation_id`, whose valid maximum is
`MAX_CONVERSATION_ID_LEN = 64` (`bot/files.py:29`). Any valid conversation ID longer than
`64 - len(prefix)` therefore produces a payload that exceeds the cap.

The guard `_btn()` (`bot/keyboards.py:12-17`) raises `ValueError` rather than silently truncating —
which is the correct fail-fast choice, but the exception propagates into keyboard rendering and
becomes `FAILED_PERMANENT` via `_classify_failure` (`bot/handlers.py:618-642`), stalling polling
(the `DEF-002` interaction).

### 1.2 Measured overflow thresholds (executed, not estimated)

Verified by driving the real `_btn()` guard (`bot/keyboards.py::_btn`) with synthetic IDs of
increasing length, across **every** callback shape that embeds a conversation ID.

**Method [REV-2 D-4]:** for each template, `cid` length was incremented from 1 until `_btn()`
raised `ValueError`. The reported value is the **largest length that still fits**. Numeric segments
(`gen`, page/file index) were varied independently because they are unbounded runtime integers
(`bot/file_cache.py::FileCache.put` returns a monotonic per-process cursor; the file index is
`page*FILES_PAGE_SIZE + offset`).

**Single-segment payloads (no numeric fields) — exact:**

| Payload shape | Source symbol | Safe max `cid` |
|---|---|---|
| `deleteok:{cid}` | `keyboards.py::confirm_delete_keyboard` | **55** |
| `unwatch:{cid}` | `keyboards.py::conversation_keyboard` | **56** |
| `delete:{cid}` | `keyboards.py::conversation_keyboard` | 57 |
| `status:{cid}` | `keyboards.py::conversation_keyboard` | 57 |
| `export:{cid}` | `keyboards.py::conversation_keyboard` | 57 |
| `watch:{cid}` | `keyboards.py::conversation_keyboard` | 58 |
| `reply:{cid}` | `keyboards.py::conversation_keyboard` | 58 |
| `cost:{cid}` | `keyboards.py::conversation_keyboard` | 59 |
| `open:{cid}` | `keyboards.py::conversation_keyboard` | 59 |
| `full:{cid}` | `keyboards.py::reply_keyboard` | 59 |
| `copy:{cid}` | `keyboards.py::reply_keyboard` | 59 |
| `txt:{cid}` | `keyboards.py::reply_keyboard` | 60 |

**Two-segment payloads — digit-width dependent:**

| Payload shape | `gen`/index width | Safe max `cid` |
|---|---|---|
| `files:{cid}:0` | none | **56** |
| `files:{cid}:{gen}:{page}` | 1 / 1 digits | **54** |
| `files:{cid}:{gen}:{page}` | 1 / 2 digits | 53 |
| `files:{cid}:{gen}:{page}` | 2 / 3 digits | 51 |
| `files:{cid}:{gen}:{page}` | 4 / 5 digits | **47** |
| `file:{cid}:{gen}:{idx}` | 1 / 1 digits | **55** |
| `file:{cid}:{gen}:{idx}` | 1 / 2 digits | 54 |
| `file:{cid}:{gen}:{idx}` | 2 / 3 digits | 52 |
| `file:{cid}:{gen}:{idx}` | 4 / 5 digits | **48** |

> **[REV-2 D-4] Corrections to Revision 1:**
> 1. Revision 1 stated `file:` safe max = **54**. The measured value is **55** (at 1-digit numerics).
>    Revision 1 was off by one because `_btn()` raises only on `> 64` bytes — a payload of exactly
>    64 bytes is **valid**.
> 2. Revision 1 presented these as **fixed constants**. They are **ranges**: `files:` spans 47-56
>    and `file:` spans 48-55 depending on numeric digit width. A single representative identifier
>    does **not** establish the true maximum.

**The binding constraint is `files:{cid}:{gen}:{page}` at 47 characters** (worst realistic numeric
width). A 56-character ID — entirely valid under `_ID_RE` — overflows every two-segment payload and
most single-segment ones. **This is the constraint the token design must satisfy.**

### 1.3 In scope

A short opaque token resolver that replaces the raw `conversation_id` inside callback payloads,
with: TTL/expiration, bounded cleanup, fail-closed stale handling, ownership/conversation/action
binding, and single-use atomic consumption.

### 1.4 Out of scope

- Implementation, migration execution, callback-format changes (all prohibited by this task).
- The Mini App (uses REST URL paths, not `callback_data` — `DEF-010` records `NONE` cross-boundary impact).
- Any new worker, queue, service, or scheduler.
- Any change to WP-07 or other work packages.
- `DEF-009` (WP-06 Part 1) — already verified complete.

---

## 2. Current-state findings with exact source references

All findings verified against the working tree at `52e7789` + the 6 pre-existing WP-07 modified
files. `bot/db.py` and `bot/handlers.py` are **WP-07-dirty**; findings below were cross-checked
against `git show HEAD:` where the distinction matters.

### 2.1 No `callback_refs` exists

```
grep -rn "callback_refs" bot/ tests/   →  0 matches
```

The only mentions are in audit/design documents (`OHB2-REMEDIATION-MASTER-PLAN.md:159,164`,
`OHB2-COMPLETE-DEFECT-REGISTER.md:311`). Confirmed **17 tables** live (via `sqlite_master`, not
`grep -c 'CREATE TABLE'`, which returns 23 because migration/rebuild scaffolding also matches):

```
attachment_batches, attachment_items, attachment_message_identity, completion_pending,
creation_jobs, deleted_conversations, notification_inbox, notification_state,
notifier_pending, notifier_retry_not_before, outbox, processed_updates, settings,
update_failures, user_state, watched, web_sessions
```

### 2.2 Callback dispatch surface

Registration is in `bot/app.py::_register_handlers` (point-in-time lines 121-155) via
`CallbackQueryHandler(..., pattern=r"^prefix...")`.

**[REV-2 D-5] There are exactly 14 handlers that carry a `conversation_id`.** Revision 1 stated 15
and mis-classified two page-only handlers. Re-enumerated from source:

| # | Handler symbol | Callback family (registration pattern) | Authorization path | Transaction exposure | Token resolution |
|---|---|---|---|---|---|
| 1 | `open_conversation` | `^open:` | `_authorized_conversation_status` | **`set_awaiting_and_record_outcome` → `BEGIN IMMEDIATE`** | resolve → cid |
| 2 | `copy_reply` | `^copy:` | `_authorized_conversation_status` | none | resolve → cid |
| 3 | `full_reply` | `^full:` | `_authorized_conversation_status` | none | resolve → cid |
| 4 | `send_reply_txt` | `^txt:` | `_authorized_conversation_status` | none | resolve → cid |
| 5 | `watch_conversation` | `^watch:` | `_authorized_conversation_status` | **`add_watched_and_record_outcome` → `BEGIN IMMEDIATE`** | resolve → cid |
| 6 | `unwatch_conversation` | `^unwatch:` | `_authorized_conversation_status` | **`_remove_watched_with_retry` → `remove_watched`/`watcher.unwatch` → `BEGIN IMMEDIATE`** | resolve → cid |
| 7 | `delete_conversation_prompt` | `^delete:` | `_authorized_conversation_status` | none | resolve → cid |
| 8 | `delete_conversation_confirm` | `^deleteok:` | `_authorized_conversation_status` | none (delegates to deletion service) | resolve → cid |
| 9 | `show_status` | `^status:` | `_authorized_conversation_status` | none | resolve → cid |
| 10 | `show_cost` | `^cost:` | `_authorized_conversation_status` | none | resolve → cid |
| 11 | `export_conversation` | `^export:` | `_authorized_conversation_status` | none | resolve → cid |
| 12 | `list_files` | `^files:` | `_authorized_conversation_status` | none | resolve → cid **+ preserve `gen`/`page`** |
| 13 | `show_file` | `^file:` | `_authorized_conversation_status` | none | resolve → cid **+ preserve `gen`/`index`** |
| 14 | `reply_prompt` | `^reply:` | `_authorized_conversation_status` | **`set_awaiting_and_record_outcome` → `BEGIN IMMEDIATE`** | resolve → cid |

**[REV-2 D-1] Exactly 4 of these 14 handlers reach a `BEGIN IMMEDIATE` transaction** (rows 1, 5, 6,
14). This set is the complete transaction-composition risk surface and is the basis of §8.

**Handlers that parse `q.data` but carry NO conversation ID (4 — not affected):**

| Handler | Pattern | Why unaffected |
|---|---|---|
| `list_conversations` | `^list:` | page number only |
| `list_watches` | `^watched:` | page number only |
| `repos_page` | `^repos:` | `gen` + page only |
| `pick_repo` | `^pickrepo:` | `gen` + index only |

> **[REV-2 D-5] Correction:** Revision 1 listed `list_conversations` and `list_watches` **inside** the
> cid-bearing table while simultaneously calling them page-only, and omitted `repos_page`/`pick_repo`
> from the non-cid list. Total is **14**, not 15.

### 2.3 Existing helpers the design must reuse (not reinvent)

**[REV-2 D-3]** Symbol names are authoritative; line numbers are point-in-time hints.

| Helper | Stable location | Contract |
|---|---|---|
| `_btn()` | `bot/keyboards.py::_btn` | Raises `ValueError` if `len(callback_data.encode("utf-8")) > 64`. **Keep unchanged.** |
| `_allowed()` | `bot/handlers.py::_allowed` | Owner/private-chat gate. Must run **first**. |
| `_safe_answer()` | `bot/handlers.py::_safe_answer` | Answers callback, swallows only `(TelegramError, asyncio.TimeoutError)`; never re-raises into `_classify_failure`. |
| `_authorization_ignored()` | `bot/handlers.py::_authorization_ignored` | Records `EXPLICITLY_IGNORED`. |
| `mark_explicitly_ignored()` | `bot/handlers.py::mark_explicitly_ignored` | Durable explicit-ignore record. |
| `mark_ambiguous_external()` | `bot/handlers.py::mark_ambiguous_external` | Records ambiguity (ineligible for ack). |
| `_authorized_conversation_status()` | `bot/handlers.py::_authorized_conversation_status` | Ownership + `is_deleted` + upstream classification at dispatch time. |
| `is_transient_sqlite_error()` | `bot/db.py::is_transient_sqlite_error` | BUSY/LOCKED via `sqlite_errorcode & 0xFF`. |
| `_classify_failure()` | `bot/handlers.py::_classify_failure` | **Must never be reached** by a stale/unknown token. |
| `acknowledgment_boundary()` | `bot/update_outcomes.py::acknowledgment_boundary` | Monotonic ack watermark; a non-eligible outcome blocks all later acks. |
| **`_nocommit` composition helpers** | `bot/db.py` — 13 methods, e.g. `_set_last_state_nocommit`, `_add_watched_nocommit`, `_remove_watched_nocommit`, `_set_awaiting_nocommit`, `_mark_processed_nocommit` | **[REV-2 D-1] The authoritative transaction-composition convention.** Each performs SQL only; the **caller** owns `BEGIN IMMEDIATE`/`commit`/`rollback`. |
| `commit=False` / `_commit=False` parameters | `bot/db.py` (e.g. `mark_update_outcome`, `record_notification_sent`) | Public-method variant of the same composition contract. |
| `prune_processed_updates()` | `bot/db.py::prune_processed_updates` | Bounded delete honoring a monotonic boundary. |
| `prune_web_sessions()` | `bot/db.py::prune_web_sessions` | TTL delete called from the **existing** boot maintenance hook. |
| `awaiting_state()` | `bot/db.py::awaiting_state` | **[REV-2 D-1] Read-only awaiting accessor — the live path.** `take_awaiting` has **zero callers** and is superseded. |

### 2.4 Established conventions to follow

- **Schema:** `CREATE TABLE IF NOT EXISTS` inside the single `_SCHEMA` script; additive
  `ALTER TABLE ... ADD COLUMN` guarded by `PRAGMA table_info` in `_migrate()` (`db.py:822+`).
  No version table, no down-migrations — **additive only**.
- **Timestamps:** two idioms coexist — `REAL` epoch seconds (`web_sessions.created_at/expires_at`)
  and `TEXT` ISO-8601 (`watched.added_at`, `processed_updates.processed_at`). This spec chooses
  **`REAL` epoch** to match `web_sessions`, the closest analogue (short-lived token with expiry).
- **Index on expiry:** `idx_web_sessions_expires ON web_sessions(expires_at)`.
- **Cleanup hooks (existing only):** boot maintenance (`bot/db.py::Database` healthcheck, alongside
  `prune_web_sessions`), boot step in `bot/app.py` (`prune_processed_updates`). **[REV-2 D-6]** The
  `OpportunisticSweeper` route is **rejected** (§5.1) — it is hard-typed to `AttachmentReaper`.
  **No new worker is needed or proposed.**
- **TTL precedent:** `AWAITING_TTL = 10 min`, `ATTACHMENT_BATCH_TTL = 15 min` (`bot/config.py`),
  `MINI_APP_SESSION_TTL = 3600s` (`bot/config.py`).

---

## 3. Proposed data model

### 3.1 Table (proposal — `17 → 18` tables)

```sql
CREATE TABLE IF NOT EXISTS callback_refs (
    token            TEXT PRIMARY KEY,   -- opaque, URL-safe, fixed length
    telegram_id      INTEGER NOT NULL,   -- owner binding
    conversation_id  TEXT NOT NULL,      -- full, untruncated ID (<= 64)
    action_scope     TEXT NOT NULL,      -- 'status' | 'files' | 'delete' | ...
    created_at       REAL NOT NULL,      -- epoch seconds (UTC)
    expires_at       REAL NOT NULL,      -- epoch seconds (UTC)
    consumed_at      REAL,               -- NULL = unused; non-NULL = consumed
    CONSTRAINT ck_action_scope_nonempty CHECK (length(action_scope) > 0)
);
CREATE INDEX IF NOT EXISTS idx_callback_refs_expires ON callback_refs(expires_at);
CREATE INDEX IF NOT EXISTS idx_callback_refs_owner   ON callback_refs(telegram_id, conversation_id);
```

### 3.2 Field rationale

| Field | Why |
|---|---|
| `token` | `PRIMARY KEY` gives the uniqueness and the O(log n) lookup. Fixed 12 chars (§3.3). |
| `telegram_id` | Ownership binding (§7). `NOT NULL` so an unbound row cannot exist. |
| `conversation_id` | The real target, stored **whole** — the token exists precisely so this need not be truncated. |
| `action_scope` | Prevents replaying a `status:` token on `deleteok:` (§7.3). |
| `created_at` | Auditability + `expires_at` derivation. |
| `expires_at` | TTL enforcement + indexed pruning. |
| `consumed_at` | Single-use marker (§8). `NULL` = available. |

### 3.3 Token format

- **Length: 12 characters**, `secrets.token_urlsafe(9)` → exactly 12 URL-safe chars.
- **Byte budget check (executed):** the binding payload is `files:{token}:{gen}:{page}`. Measured
  maximum token length is **54** chars at 1-digit numerics and **47** at 5-digit numerics (§1.2).
  A 12-char token leaves **35 bytes** of headroom in the worst realistic case (47 − 12) and 42 in
  the best — ample for large `gen`/`page` values. Measured: a 12-char token survives even
  **20-digit** numeric fields (~52 B total).
- **Alphabet:** `[A-Za-z0-9_-]` — the same alphabet as `_ID_RE`.
- **Collision:** 72 bits of entropy. At a bounded table size of 5,000 rows the birthday
  collision probability is ≈ `5000² / (2 · 2⁷²)` ≈ **6.6 × 10⁻¹⁴** — negligible. The
  `PRIMARY KEY` still makes any collision a hard insert error, handled by retry (§5.3).

> **[OWNER] Decision O-1:** approve 12-char tokens (`secrets.token_urlsafe(9)`) vs. a longer
> 16-char token. 12 fits every payload with margin; 16 also fits but shrinks `files:` headroom
> to 31 bytes (47 − 16). Recommendation: **12**.

### 3.4 [REV-2 D-2] Token/ID ambiguity — corrected security claim

**Measured facts:**

```
is_valid_conversation_id('a1b2c3d4e5f6')   → True
is_valid_conversation_id('~a1b2c3d4e5f6')  → False
2000 generated secrets.token_urlsafe(9) tokens → 2000/2000 pass is_valid_conversation_id
```

A bare token **always** passes `_ID_RE` (`^[A-Za-z0-9_-]{1,64}$`). The ambiguity is **universal**,
not occasional.

> **[REV-2 D-2] Revision 1 stated that the existing conversation-ID validator "rejects" callback
> tokens and that an unresolved token "cannot reach OpenHands". Both claims were wrong.** The
> measured behavior is:

**What actually happens when an unresolved token reaches the authorization path:**

```
authorize_conversation_detailed(spy_client, identity, token, db=None)
  → is_valid_conversation_id(token)   → True   (passes; validator does NOT reject tokens)
  → client.get_conversations([token]) → CALL IS MADE
  → FileStatus.NOT_FOUND
  → authorized: False
```

So the token **does** reach the remote API. What holds is the *safety* property, not the *lookup*
property.

**Precise boundary distinction [REV-2 D-2]:**

| Layer | What it guarantees | What it does NOT guarantee |
|---|---|---|
| **Token validation** (`is_valid_conversation_id`) | Only that the string is syntactically ID-shaped | **Nothing** about tokens — every token passes |
| **Local resolution** (new resolver) | Maps token → `conversation_id` from `callback_refs` | — |
| **Remote lookup** (`client.get_conversations`) | Fetches conversation metadata | Will be **called** if a token is passed as a cid |
| **Action authorization** (`_authorized_conversation_status` + ownership) | Rejects non-owned / deleted / unknown conversations | — |
| **Preventing an action** | Guaranteed by authorization | — |
| **Preventing a remote lookup** | **Only** guaranteed by resolving the token **before** calling any authorization helper | — |

**Mitigation (unchanged in intent, corrected in justification):** resolution is decided by
**explicit prefix dispatch**, never by sniffing the value. Each affected prefix (`status:`,
`files:`, …) resolves its second segment through the resolver unconditionally; there is no code
path that falls back to treating the segment as a conversation ID. `~` is deliberately **not**
used, to keep the alphabet uniform. See §10.6 for the required regression test.

**Why this matters operationally:** a missed resolver does not authorize an action, but it does
consume an upstream API call and can contribute to rate limiting. The design therefore treats the
choke point as a **correctness requirement**, not merely defence-in-depth.

---

## 4. TTL and expiration rules

### 4.1 Proposed values

| Parameter | Proposed value | Rationale |
|---|---|---|
| `CALLBACK_REF_TTL` | **30 minutes** | Inline menus are ephemeral; `AWAITING_TTL` (10 min) is for one-shot routing and too short for a keyboard a user may return to. `MINI_APP_SESSION_TTL` (60 min) is for a session. 30 min sits between and covers realistic tap latency. |
| `CALLBACK_REF_MAX_ROWS` | **5,000** | Hard cap on live rows; bounds the table independent of TTL. |
| `CALLBACK_REF_PRUNE_BATCH` | **200** | Max rows deleted per cleanup invocation (§5). |

> **[OWNER] Decision O-2:** approve `CALLBACK_REF_TTL = 30 min`, `MAX_ROWS = 5000`,
> `PRUNE_BATCH = 200`. These are proposals; the baseline explicitly forbids inventing them as
> fact.

### 4.2 Expiration semantics

A reference is **valid** iff:

```
consumed_at IS NULL
AND now < expires_at            -- strict: expires_at itself is already expired
AND telegram_id = <caller>
AND action_scope = <expected scope for this prefix>
AND conversation still authorized (live check, §7.4)
```

`now = time.time()` (epoch seconds, UTC), compared against `REAL expires_at`.

**Clock handling.** Both `created_at` and `expires_at` are written from the same `time.time()`
call, so a backwards system-clock jump cannot make a fresh row look expired relative to its own
`created_at`. Monotonic clocks are **not** used because they do not survive a restart, and
restart-persistence is an explicit `DEF-010` requirement. Comparison is done in SQL/Python on the
same wall clock that wrote the value — consistent within one process, which is the only
consumer.

**Boundary conditions.**

| Case | Behavior |
|---|---|
| `now == expires_at` | **Expired** (strict `<`). Deterministic and conservative. |
| `expires_at` missing/NULL | Impossible — `NOT NULL` column; if the row is malformed, treat as expired (§6.3). |
| `expires_at` not a number | Treated as expired (fail-closed). |
| Clock jumped backwards | Row remains valid up to its original `expires_at`; no premature invalidation. |
| Clock jumped forwards | Row expires early — safe direction (stale, not over-authorized). |

### 4.3 Outcome for each reference state

| State | Detection | User-facing | Internal outcome |
|---|---|---|---|
| Valid | all checks pass | normal action | — |
| **Expired** | `now >= expires_at` | stale-menu message + `/start` guidance | `EXPLICITLY_IGNORED` |
| **Missing/unknown** | no row for token | same stale-menu message | `EXPLICITLY_IGNORED` |
| **Malformed** | payload fails structural parse (e.g. non-int page) | same stale-menu message | `EXPLICITLY_IGNORED` |
| **Already consumed** | `consumed_at IS NOT NULL` | same stale-menu message | `EXPLICITLY_IGNORED` |
| **Wrong owner** | `telegram_id != caller` | generic denial, **no** leak | `EXPLICITLY_IGNORED` |
| **Wrong scope** | `action_scope != expected` | generic denial | `EXPLICITLY_IGNORED` |
| DB error (BUSY/LOCKED) | `is_transient_sqlite_error` | retry-safe stale message | `FAILED_TRANSIENT` |
| DB error (permanent) | other `sqlite3.Error` | safe generic message | `FAILED_PERMANENT` (but **no action performed**) |

All user-facing text reuses the existing style, e.g. `_FILES_EXPIRED` (`handlers.py:2700`):
`"قايمة الملفات دي قديمة، افتح «الملفات» من الشات تاني."`

---

## 5. Bounded cleanup algorithm and limits

### 5.1 [REV-2 D-6] When cleanup runs — existing hooks only

No new worker, scheduler, thread, or service. Cleanup is invoked from the **existing** boot
maintenance hook **plus** a mandatory insert-path row cap.

**Hook 1 — boot maintenance (adopted).**
`bot/db.py::Database` healthcheck/optimize cycle, which already calls
`prune_web_sessions(time.time())` and is wrapped in `try/except sqlite3.Error` with a
non-fatal `log.warning`. `prune_callback_refs(now, batch=200)` is called alongside it. Runs once per
process start, outside any user transaction, bounded by `LIMIT`.

**Hook 2 — insert-path hard cap (adopted, MANDATORY).**
On every token issue, if the live row count would exceed `MAX_ROWS`, prune expired rows first
(bounded by `PRUNE_BATCH`). This is what makes growth impossible in a long-lived process that never
restarts. **It is not optional** — see §5.2.

> **[REV-2 D-6] The `OpportunisticSweeper` route is REJECTED.** Revision 1 offered it as an
> optional second hook. Source evidence shows it cannot be reused without an out-of-scope change:
>
> ```python
> # bot/attachments.py::OpportunisticSweeper
> def __init__(self, reaper: AttachmentReaper, *, min_interval=..., clock=None):
>     self._reaper = reaper          # hard-typed to AttachmentReaper
>     ...
> # its sweep path calls self._reaper.sweep()
> ```
>
> It is **hard-typed to `AttachmentReaper`** and its lifecycle is bound to `AttachmentReaper.sweep`
> (retry throttling via `_last_attempt_at`, `_last_success_at`, `_running` re-entrancy guard). Serving
> `callback_refs` would require either:
> - **(a)** modifying `bot/attachments.py` to accept a generic sweep callable — an **out-of-scope**
>   change to a module WP-07 also touches, expanding blast radius for no correctness gain; or
> - **(b)** writing a second, parallel sweeper — which is a **new worker-like component** and
>   violates the approved architecture.
>
> Neither is justified. Boot hook + insert-path cap fully bounds the table with **zero new wiring**.

> **[OWNER] Decision O-3:** confirm **boot hook + insert-path cap only**; no sweeper, no new worker.
> If the owner nevertheless wants the sweeper, that requires a **separate architecture approval** to
> modify `attachments.py`.

### 5.2 Hard bounds

```python
def prune_callback_refs(self, now: float, *, batch: int = CALLBACK_REF_PRUNE_BATCH) -> int:
    # 1) expired rows, oldest-first, at most `batch`
    # 2) if live rows still exceed MAX_ROWS, delete oldest-by-expires_at, at most `batch`
```

- **Strict maximum per invocation:** `batch` (200) rows deleted, never more.
- **Never an unbounded scan:** both deletes carry `LIMIT ?` and are driven by
  `idx_callback_refs_expires`.
- **Insert-path cap — MANDATORY [REV-2 D-6]:** on every token issue, if `live_count >= MAX_ROWS`,
  prune before inserting. This is the **only** guarantee that bounds growth in a long-lived process
  that never restarts, because the sweeper route is rejected (§5.1). It is a **correctness
  requirement**, not optional defence-in-depth.
- **Amortization:** the insert-path cap runs at most once per issue, with the same `LIMIT`, so a
  burst of 100 button renders cannot trigger 100 unbounded deletes.
- **Transaction note [REV-2 D-1]:** the insert-path cap runs **inside the caller's transaction** if
  one is already open (it issues no `BEGIN`). If the caller has no transaction, the issue path wraps
  its own `BEGIN IMMEDIATE` … `commit` — and that wrapper must complete **before** any
  `*_and_record_outcome` call.

### 5.3 SQLite BUSY/LOCKED and database errors

| Situation | Behavior |
|---|---|
| `prune` hits BUSY/LOCKED (`is_transient_sqlite_error`) | Log at WARNING, return `0`, **do not raise**. Cleanup is non-critical; the next hook retries. |
| `prune` hits a permanent `sqlite3.Error` | Log at WARNING with exception **type only**, return `0`. Never fatal. |
| `INSERT` hits BUSY/LOCKED during issue | Retry the whole issue at most **3 times** with a short bounded backoff, then propagate so the caller renders without that button (fail-closed, no crash loop). |
| `INSERT` collides on `PRIMARY KEY` | Generate a new token, retry at most **3 times**, then propagate. |
| **Nested `BEGIN IMMEDIATE`** | **[REV-2 D-1]** Prohibited by design (§8.3). Would raise `OperationalError`, classify as **non-transient** → `FAILED_PERMANENT` → `DEF-002` stall. The helper never opens a transaction. |

Consistent with the existing project policy: `busy_timeout=5000` is already set
(`bot/db.py::Database` PRAGMA block), and `is_transient_sqlite_error` (`bot/db.py`) is the single
source of truth.

---

## 6. Fail-closed behavior

### 6.1 Invariant

> **No resolution failure may authorize an action.**

Every failure path returns *before* any upstream API call, any state mutation, and any
`delete`/`watch`/`reply` side effect.

### 6.2 [REV-2 D-2] Ordering (must be preserved exactly)

```
1. _allowed(update, config)            -- owner/private gate, FIRST, unchanged
2. structural parse of q.data          -- malformed => stale message, EXPLICITLY_IGNORED, return
3. resolve token -> conversation_id    -- BEFORE any authorization helper (§3.4 / D-2)
   + consume (transaction-composable, §8.3)
4. verify telegram_id  == caller       -- mismatch => generic denial, return
5. verify action_scope == expected     -- mismatch => generic denial, return
6. _authorized_conversation_status()   -- live ownership + is_deleted re-check
7. ONLY NOW perform the action
```

**[REV-2 D-2] Step 3 must precede step 6.** Resolving *before* `_authorized_conversation_status`
is what prevents a remote `get_conversations` call with an unresolved token (§3.4). If resolution
were deferred until after authorization, the token would reach the remote API — measured to happen.

Steps 1–6 are all read-only with respect to the target conversation. A failure at any of them
cannot have performed a partial action. Note that step 3's **consume** is the one write; it is
scoped to `callback_refs` only and is rolled back with the caller's transaction on failure (§8.4).

### 6.3 Lookup / expiration / DB failure

- Lookup returns no row → stale message, `EXPLICITLY_IGNORED`, return.
- Row present but `expires_at` unusable → treated as expired → same path.
- DB unavailable → `_safe_answer` a retry-safe message; classify as `FAILED_TRANSIENT` so the
  existing bounded retry logic may re-deliver; **no action performed** either way.

### 6.4 User-facing vs. internal

| Audience | Content |
|---|---|
| User | Friendly Arabic stale-menu text; generic denial for ownership/scope failures. **Never** another user's `conversation_id`, title, or existence. |
| Logs | Exception **type** and token **prefix only** (never the full token, never conversation content) — matching the existing `_safe_answer` convention (`handlers.py:83-105`). |
| Durable outcome | `EXPLICITLY_IGNORED` / `mark_ambiguous_external` — never a success record. |

### 6.5 Retry without duplicate actions

- Transient DB failure ⇒ `FAILED_TRANSIENT` ⇒ existing retry may re-run the **whole** handler.
  Safe because no action was performed (steps 1–6 precede step 7).
- **Consumption is atomic (§8)**, so if the retry re-runs, the token is already consumed and the
  retry lands on the "already consumed" branch → stale message, no duplicate action.
- **No exactly-once claim.** This guarantees *at-most-once effect for the token*, not exactly-once
  Telegram delivery.

---

## 7. Ownership binding and authorization

### 7.1 Binding at creation

A token is created with `telegram_id` = the requesting user, `conversation_id` = the full ID,
`action_scope` = the prefix family that will consume it. All three are `NOT NULL`.

### 7.2 Verification at consumption (not only creation)

Step 4–6 of §6.2 re-verify at dispatch time. Creation-time checks are treated as **hints only**;
authorization is always re-established when the button is pressed, because ownership can change
and conversations can be deleted between render and tap.

### 7.3 Cross-user and cross-conversation reuse

| Attack | Defence |
|---|---|
| User B taps User A's button | `telegram_id != caller` → generic denial. |
| `status:` token replayed on `deleteok:` | `action_scope != 'delete'` → denial. |
| Token from conversation X used to reach Y | `conversation_id` comes **from the row**, never from the payload; the payload carries only the token. The caller cannot substitute a target. |
| Guessing a token | 72-bit entropy + bounded table; failures are indistinguishable from expired. |

The last row is the key structural property: because the payload contains **only** the token,
there is no attacker-controlled conversation identifier at all.

### 7.4 Missing or inconsistent ownership data

| Condition | Behavior |
|---|---|
| `telegram_id` NULL (impossible by schema) | Treated as invalid → denial. |
| Row references a conversation that no longer exists | `_authorized_conversation_status()` returns `NOT_FOUND`/`DELETED` → normal "not found" message, no leak. |
| Conversation tombstoned (`deleted_conversations`) | Existing tombstone guard (`F-1`) rejects before any remote call. |
| `action_scope` not in the known set | Denial (fail-closed). |

### 7.5 Unchanged authorization semantics

`_allowed()` runs first and is **not** modified. `_authorized_conversation_status()` is reused
as-is. The design adds a binding layer; it removes no existing check.

---

## 8. Atomic single-use consumption — transaction-composition model

> **[REV-2 D-1] This section was substantially rewritten.** Revision 1 proposed a *standalone*
> `BEGIN IMMEDIATE` consumption transaction "mirroring `take_awaiting()`". That is **unsafe in 4 of
> the 14 target handlers** and would cause a `DEF-002` polling stall. See §8.2 for the proof and
> §8.3 for the corrected model.

### 8.1 Single-use: yes

References are **single-use**. Rationale: a consumed `deleteok:` token must not be replayable,
and uniform single-use keeps the rule simple and auditable. Multi-tap menus (`files:` paging)
issue a **new** token per render, which the existing code already does (a fresh keyboard per page).

> **[OWNER] Decision O-4:** confirm single-use for **all** scopes. Alternative: single-use only
> for mutating scopes (`delete`, `watch`, `unwatch`, `reply`) and reusable for read-only
> (`status`, `files`, `cost`, `export`). Recommendation: **single-use for all** — simpler to
> reason about, and re-render already produces fresh tokens.

### 8.2 [REV-2 D-1] Why a standalone `BEGIN IMMEDIATE` is prohibited here

**Evidence — the superseded precedent.** `bot/db.py::take_awaiting` opens its own
`BEGIN IMMEDIATE`. It has **zero callers** in the codebase:

```
grep -rn "take_awaiting(" bot/ | grep -v "def take_awaiting"   →  (no results)
```

It was **superseded** by the read-only accessor `awaiting_state`
(`bot/db.py::awaiting_state`), whose docstring states that consumption "became separate and atomic
with the durable record write". Its live callers are
`bot/handlers.py` (`handle_text` paths). **Revision 1 cited the superseded pattern as its model.**

**Evidence — 4 target handlers already own a transaction.** Measured from source:

| Handler | Transaction owner |
|---|---|
| `open_conversation` | `db.set_awaiting_and_record_outcome` → `conn.execute("BEGIN IMMEDIATE")` |
| `watch_conversation` | `db.add_watched_and_record_outcome` → `conn.execute("BEGIN IMMEDIATE")` |
| `unwatch_conversation` | `_remove_watched_with_retry` → `db.remove_watched` / `watcher.unwatch` → `BEGIN IMMEDIATE` |
| `reply_prompt` | `db.set_awaiting_and_record_outcome` → `conn.execute("BEGIN IMMEDIATE")` |

**Evidence — nesting fails, and fails permanently.** Executed against real `sqlite3`:

```
outer BEGIN IMMEDIATE      → ok
nested BEGIN IMMEDIATE     → OperationalError: cannot start a transaction within a transaction
is_transient_sqlite_error(that error) → False
  ⇒ _classify_failure → FAILED_PERMANENT  (no retry)
  ⇒ DEF-002 polling stall
```

A standalone consuming `BEGIN IMMEDIATE` inside any of those 4 handlers would therefore **stall
polling** — precisely the failure the design exists to prevent.

### 8.3 [REV-2 D-1] Corrected model: transaction-composable helper

**Transaction ownership rule.**

> **The caller owns the transaction boundary. The `callback_refs` helper never opens, commits, or
> rolls back a transaction.**

This mirrors the codebase's **13 established `_nocommit` helpers** (`bot/db.py`), e.g.
`_set_last_state_nocommit`, `_add_watched_nocommit`, `_remove_watched_nocommit`,
`_set_awaiting_nocommit`, `_mark_processed_nocommit`. Each performs SQL only; the enclosing method
owns `BEGIN IMMEDIATE` / `commit` / `rollback`.

**Proposed helper (design only — not implemented):**

```python
def consume_callback_ref_nocommit(
    self, token: str, *, telegram_id: int, action_scope: str, now: float
) -> tuple[dict | None, str]:
    """Consume a callback reference INSIDE the caller's transaction.

    NEVER opens/commits/rolls back a transaction. Caller owns the boundary.
    Returns (row, "ok" | "missing" | "expired" | "consumed" | "owner" | "scope" | "raced").
    """
```

The SQL it performs (no transaction control):

```sql
SELECT token, telegram_id, conversation_id, action_scope, expires_at, consumed_at
  FROM callback_refs WHERE token = ?;
-- validate in Python: consumed_at IS NULL, now < expires_at,
--                     telegram_id == caller, action_scope == expected
UPDATE callback_refs SET consumed_at = ?
 WHERE token = ? AND consumed_at IS NULL;   -- rowcount != 1 → "raced"
```

**Two invocation modes, both safe:**

| Mode | When | Transaction boundary owner |
|---|---|---|
| **Composed** | Handler already has (or will open) a transaction — e.g. `watch_conversation` | The handler's existing `*_and_record_outcome` method |
| **Self-wrapped** | Handler has no transaction (e.g. `show_status`, `show_cost`) | The handler, via one explicit `BEGIN IMMEDIATE` … `commit` around **only** the resolve+consume step, which must **complete before** any other transactional call |

**Hard prohibition [REV-2 D-1]:** within `open_conversation`, `watch_conversation`,
`unwatch_conversation`, and `reply_prompt`, the resolver **must not** open its own transaction. In
these handlers the consumption must be composed into the existing `*_and_record_outcome` /
`remove_watched` transaction, or performed in a self-wrapped step that fully commits **before** that
call begins.

### 8.4 [REV-2 D-1] Rollback, exception propagation, atomicity

| Concern | Contract |
|---|---|
| **Rollback** | The helper performs **no** rollback. If it raises, the caller's `except: rollback; raise` (the standard pattern in every `_nocommit` caller) undoes the partial write. |
| **Exception propagation** | `sqlite3.Error` propagates unchanged to the caller. `is_transient_sqlite_error()` decides retryability. The helper never swallows. |
| **Atomicity guarantee** | Consumption + the handler's durable record (watch row, awaiting state, update outcome) commit **together or not at all** — because they share one transaction. This is *stronger* than Revision 1, which could commit a consumption and then fail the record write. |
| **Consumed-then-failed** | If the enclosing transaction rolls back, the `consumed_at` write is rolled back too. The token becomes **reusable**, which is correct: no durable effect occurred. See O-4 in the analysis for the owner-visible trade-off. |
| **Read-only handlers** | `show_status`, `show_cost`, `export_conversation`, `copy_reply`, `full_reply`, `send_reply_txt`, `list_files`, `show_file`, `delete_conversation_prompt`, `delete_conversation_confirm` have no existing transaction → self-wrapped mode is safe there. |

### 8.5 Callers that cannot participate — required alternatives

| Caller | Problem | Required alternative |
|---|---|---|
| `open_conversation`, `reply_prompt` | `set_awaiting_and_record_outcome` opens `BEGIN IMMEDIATE` | Compose consumption into that method via a `nocommit` variant, **or** self-wrap and commit before calling it |
| `watch_conversation` | `add_watched_and_record_outcome` opens `BEGIN IMMEDIATE` | Same |
| `unwatch_conversation` | `remove_watched`/`watcher.unwatch` open `BEGIN IMMEDIATE` | Same; note `watcher.unwatch` is an **external** object — verify it exposes a composable path, else self-wrap and commit first |
| Any future handler | Unknown | Rule: resolve+consume **before** any `*_and_record_outcome` call, or compose into it |

> **Unresolved assumption (carried to the report):** `watcher.unwatch` is not a `Database` method,
> so its transaction behavior must be confirmed at implementation time. If it cannot compose,
> `unwatch_conversation` must use self-wrapped mode with the consume committed first.

### 8.6 Simultaneous deliveries

| Scenario | Result |
|---|---|
| Same token delivered twice concurrently | `BEGIN IMMEDIATE` in the owning transaction serializes them; the loser sees `rowcount == 0` → `raced` → stale message, **no** action. |
| Same token delivered twice sequentially | Second sees `consumed_at` set → stale message. |
| Different tokens, same conversation | Both succeed independently (correct — distinct user intents). |

### 8.7 Explicit non-claim

This provides **at-most-once effect per token** and **no duplicate action from a replayed
token**. It does **not** claim exactly-once Telegram delivery, exactly-once processing, or any
atomicity spanning SQLite and the Telegram API. A crash after `commit` but before the reply is
sent leaves the token consumed and the user seeing a stale message — the safe direction.

---

## 9. Schema and migration proposal

### 9.1 Smallest necessary change

One new table + two indexes (§3.1): **17 → 18 tables**. No column added to any existing table, no
data rewritten, no existing row touched.

### 9.2 Migration mechanics (following existing convention)

- Added to the `_SCHEMA` script using `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS`
  — idempotent, additive, non-destructive (`bot/db.py::_init_schema` convention).
- No `ALTER TABLE` is needed, so `_migrate()` needs no change.
- Runs automatically on `Database.__init__` for both new and existing databases.

**Verified migration properties (executed against real SQLite):**

| Property | Result |
|---|---|
| Re-running `_init_schema` on an existing DB | 17 → 17, **no error** (idempotent) |
| Adding the table, then re-init | 17 → 18, **no error** |
| `journal_mode` | `wal` (preserved) |
| `busy_timeout` | `5000` (preserved) |
| `foreign_keys` | `ON` (preserved) |
| Interrupted `executescript` | Self-heals on next boot — `IF NOT EXISTS` skips already-created objects |

### 9.2b [REV-2 O-6] Mandatory documentation coupling — same change set

**This is a hard coupling, not a documentation nicety.** `tests/test_doc_code_parity.py` contains
`test_runbook_table_count_matches_schema`, which asserts:

```python
tables = _schema_tables()                                  # derived from bot/db.py::_init_schema
assert f"**{len(tables)}** جدول" in RUNBOOK
```

`docs/OPERATIONS_RUNBOOK.md` §4 currently states `**17** جدول`. Adding `callback_refs` makes
`len(tables) == 18`, so **the assertion fails** unless the runbook is updated.

**Required in the same change set as the DDL:**
1. Update `docs/OPERATIONS_RUNBOOK.md` §4 count from `17` to `18`.
2. Add the `` `callback_refs` `` table name to the runbook's table list (the sibling test
   `test_runbook_documents_every_schema_table` asserts each `` `table` `` name appears).

**Verified by simulation:** with 18 tables, `f"**18** جدول" in RUNBOOK` → `False` (test would fail).

### 9.3 Rollback limitations (stated honestly)

- **No down-migration exists** in this project and none is proposed.
- Rolling back the *code* while leaving the table is harmless: an unused table with no readers.
- Rolling back by dropping the table **invalidates every outstanding token**. Users holding
  rendered keyboards would get stale-menu messages until the keyboards are re-rendered. This is
  a degraded-but-safe outcome, not data loss.
- **No user data is at risk** — `callback_refs` holds only transient routing pointers, all of
  which are reconstructible by re-rendering the menu. It is the lowest-risk possible schema
  addition.

### 9.4 Compatibility

- Old databases: table is created empty on first boot. No backfill needed.
- Old code + new table: never referenced → inert.
- New code + old rows: not applicable (new table).

---

## 10. Compatibility analysis

### 10.1 Existing payload formats

Current formats are `prefix:raw_conversation_id` and `prefix:cid:gen:page`. The design changes
the **second segment only** for the **14** cid-bearing prefixes, from a raw ID to a 12-char token.
Prefixes, separators, segment counts, and numeric segments are unchanged.

### 10.2 Callers and consumers

| Layer | Impact |
|---|---|
| Producers — `bot/keyboards.py` (8 builders) | Second segment becomes a token; `_btn()` guard unchanged. |
| Consumers — **14** handlers (`bot/handlers.py`) | Resolve the token before use. **[REV-2 D-5]** |
| Registration — `bot/app.py::_register_handlers` | **No change**; `pattern=r"^prefix"` matching is unaffected. |
| Mini App | **No change** (REST paths, not `callback_data`). |
| `processed_updates` dedupe | Unaffected — keyed by `update_id`, not payload. |
| `acknowledgment_boundary` | Unaffected — token failures map to existing eligible outcomes. |

### 10.3 Stale buttons (the main real-world case)

A keyboard rendered before a deploy, or older than the TTL, carries a token that no longer
resolves. Behavior: friendly stale message + `/start` guidance, `EXPLICITLY_IGNORED`, **no
exception**, no polling stall. This is strictly better than today, where an over-long ID raises
`ValueError` → `FAILED_PERMANENT`.

### 10.4 Duplicate updates / retries

Handled by single-use consumption (§8) plus the existing `processed_updates` dedupe. A retried
update whose token is already consumed gets the stale path — never a second action.

### 10.5 Deleted conversations

Token resolves, then `_authorized_conversation_status()` rejects with the existing not-found
message; the tombstone guard still runs first. No new leak surface: the token row is per-user and
the response is the pre-existing generic text.

### 10.6 [REV-2 D-2] Regression risk register

| Risk | Severity | Mitigation |
|---|---|---|
| **A handler forgets to resolve and passes the raw token to an authorization helper** | **HIGH** | Token is 12 chars and **always** passes `_ID_RE` (§3.4), so this **will** issue a real upstream `get_conversations` call (measured). It cannot authorize an action, but it wastes an upstream call and risks rate limiting. **Required test:** assert the upstream client is never invoked with a value that matches an issued-but-unresolved token — a spy client on `authorize_conversation_detailed` with `assert client.calls == []`. |
| **Nested `BEGIN IMMEDIATE` in the 4 transaction-owning handlers** | **HIGH** | **[REV-2 D-1]** Would raise `OperationalError` → `FAILED_PERMANENT` → `DEF-002` stall. Mitigated by the transaction-composition rule (§8.3) + an explicit prohibition, and by a test that drives each of the 4 handlers end-to-end and asserts no `OperationalError` surfaces. |
| `files:`/`file:` lose `gen`/`page` while migrating | MEDIUM | Segment count asserted in tests for both shapes (§1.2). |
| Token issue inside a render loop exceeds `MAX_ROWS` | LOW | Insert-path cap (§5.2). |
| Cleanup competes for the write lock | LOW | `LIMIT 200`, boot hook only, BUSY tolerated (§5.3). |
| Two taps in the same millisecond | LOW | Owning transaction's `BEGIN IMMEDIATE` + `rowcount` guard (§8.3). |
| `watcher.unwatch` cannot compose | MEDIUM | Unresolved assumption (§8.5): verify at implementation; fall back to self-wrapped consume-then-commit. |

---

## 11. Failure-mode table

| # | Failure | Detection | User sees | Durable outcome | Action performed? |
|---|---|---|---|---|---|
| 1 | Token expired | `now >= expires_at` | stale-menu + `/start` | `EXPLICITLY_IGNORED` | **No** |
| 2 | Token missing/unknown | no row | stale-menu + `/start` | `EXPLICITLY_IGNORED` | **No** |
| 3 | Payload malformed | structural parse fails | stale-menu | `EXPLICITLY_IGNORED` | **No** |
| 4 | Already consumed | `consumed_at NOT NULL` | stale-menu | `EXPLICITLY_IGNORED` | **No** |
| 5 | Wrong owner | `telegram_id != caller` | generic denial | `EXPLICITLY_IGNORED` | **No** |
| 6 | Wrong scope | `action_scope` mismatch | generic denial | `EXPLICITLY_IGNORED` | **No** |
| 7 | Conversation deleted | `_authorized_conversation_status` | existing not-found text | `EXPLICITLY_IGNORED` | **No** |
| 8 | DB BUSY/LOCKED | `is_transient_sqlite_error` | retry-safe message | `FAILED_TRANSIENT` | **No** |
| 9 | DB permanent error | other `sqlite3.Error` | generic safe text | `FAILED_PERMANENT` | **No** |
| 10 | Concurrent same token | `rowcount == 0` | stale-menu | `EXPLICITLY_IGNORED` | Exactly one |
| 11 | Upstream 5xx during action | existing `ApiError` path | existing message | `mark_ambiguous_external` | Possibly (unchanged from today) |
| 12 | Telegram answer fails | `_safe_answer` catches | nothing extra | unchanged | unaffected |

**Row 11 note:** once steps 1–6 pass and the action begins, upstream failure semantics are exactly
today's — this design neither improves nor degrades them, and does not claim atomicity there.

---

## 12. Security and concurrency analysis

### 12.1 Threats addressed

| Threat | Control |
|---|---|
| Cross-user reference reuse | `telegram_id` binding, verified at consumption. |
| Cross-conversation reuse | Target comes from the row, never the payload. |
| Cross-action replay (`status:` → `deleteok:`) | `action_scope` binding. |
| Token guessing / enumeration | 72-bit entropy; failures indistinguishable from expiry. |
| Information disclosure via denial text | Generic denial; no IDs/titles in user text. |
| Secret leakage in logs | Exception type + token prefix only. |
| Stale-tap crash → polling freeze (`DEF-002`) | Every path returns via `_safe_answer`; never raises into `_classify_failure`. |
| Unbounded growth (DoS by rendering) | `MAX_ROWS` cap + bounded prune. |

### 12.2 [REV-2 D-1] Concurrency

- **Single writer process** is preserved (one authoritative SQLite owner). No new process.
- **[REV-2 D-1]** Consumption **does not** open its own `BEGIN IMMEDIATE`. It either composes into
  the caller's existing transaction (the 4 transaction-owning handlers) or is wrapped by a
  short-lived transaction the handler itself opens and commits **before** any other transactional
  call. WAL mode + `busy_timeout=5000` are already configured (`bot/db.py` PRAGMA block).
- Consumption is short and index-driven (`PRIMARY KEY` lookup), so lock hold time is minimal
  (measured ≈1.2 ms at 5,000 rows; inherited from the prior batch — **to be re-measured at
  implementation time**).
- **No lock is held across a network call.** In composed mode the transaction commits before the
  Telegram/OpenHands action begins; in self-wrapped mode the consume commits before authorization.
- A nested `BEGIN IMMEDIATE` is **structurally prohibited** (§8.3) because it would raise
  `OperationalError` → non-transient → `FAILED_PERMANENT` → `DEF-002` stall.

### 12.3 Explicitly not claimed

- No exactly-once Telegram delivery or processing.
- No SQLite↔Telegram atomicity.
- No distributed or multi-writer guarantees.

---

## 13. Test strategy and acceptance criteria

### 13.1 Test strategy (to be written at implementation time — none written now)

| Area | Test shape |
|---|---|
| 64-char IDs across all builders | Parameterized over **all 16 payload shapes** (§1.2) and `cid` lengths 1..64, **including multi-digit `gen`/`page`/index widths (1..5 digits)**; assert `<= 64` bytes. |
| Restart persistence | Issue, close DB, reopen, resolve → success. |
| TTL expiry | Freeze clock; assert valid at `expires_at - 1`, expired at `expires_at` exactly. |
| Bounded pruning | Seed `MAX_ROWS + N`; assert at most `PRUNE_BATCH` removed per call. |
| Malformed/missing refs | Each of failure rows 1–4 asserts no exception and `EXPLICITLY_IGNORED`. |
| Cross-user rejection | User B consumes User A's token → denial, no leak, no action. |
| Cross-scope rejection | `status:` token on `deleteok:` → denial. |
| Single-use / concurrency | Two concurrent consumes → exactly one `ok`, one `raced`. |
| Deleted conversation | Tombstone present → not-found, no remote call. |
| **[REV-2 D-1] No nested transaction** | Drive each of the 4 transaction-owning handlers (`open_conversation`, `watch_conversation`, `unwatch_conversation`, `reply_prompt`) end-to-end with a real `Database`; assert **no `OperationalError`** surfaces and no `FAILED_PERMANENT` outcome is recorded. |
| **[REV-2 D-1] Consumption composes** | Assert the `consumed_at` write is rolled back when the enclosing transaction rolls back (token reusable), and committed when it commits. |
| **[REV-2 D-2] No unresolved token reaches upstream** | Spy client on `authorize_conversation_detailed`; drive every cid-bearing handler with a stale/unknown token; assert `client.calls == []` (no remote lookup). |
| **Discriminating** (per project convention) | Each test must fail when the specific protection is removed — mutation-verified. |

### 13.2 [REV-2] Acceptance criteria for implementation

1. Every payload for every valid `cid` length (1..64) **and every numeric-field width** is `<= 64`
   bytes — asserted against all 16 shapes, not one representative.
2. **All 14** cid-bearing handlers resolve through one choke point; no path treats a token as a cid.
3. **[REV-2 D-2]** No unresolved token reaches `client.get_conversations` (asserted with a spy).
4. **[REV-2 D-1]** No handler raises `OperationalError` from a nested `BEGIN IMMEDIATE`; no token
   path produces `FAILED_PERMANENT`.
5. Expired/missing/malformed/consumed tokens never raise and never reach `_classify_failure`.
6. Cross-user and cross-scope attempts are rejected with no information leak.
7. Consumption is atomic under concurrent delivery; at most one action per token.
8. Cleanup deletes at most `PRUNE_BATCH` rows per invocation and never scans unbounded.
9. Live table size never exceeds `MAX_ROWS` + one batch (insert-path cap mandatory).
10. Full suite green; pyflakes 0; bandit High 0; no Mini App change; no new worker.
11. All new tests are mutation-proven non-vacuous.

---

## 14. Alternatives considered

| # | Alternative | Verdict |
|---|---|---|
| A1 | **Shorten prefixes** only | Insufficient: `files:` with gen+page still overflows at 54; and `deleteok:`/`pickrepo:` still fail at 56. Does not solve `DEF-010`. |
| A2 | **Truncate the conversation ID** | **Rejected.** Ambiguous (two IDs sharing a 40-char prefix collide) and lossy — would target the wrong conversation. |
| A3 | **Hash the ID deterministically** (no table) | Rejected: cannot reverse a hash; would still need a lookup table, so it is strictly worse than a random token. |
| A4 | **In-memory token dict** | Rejected: fails the explicit restart-persistence requirement of `DEF-010`; also breaks the single-owner SQLite model. |
| A5 | **Compress/encode the ID** (base64 of 64 bytes) | Rejected: base64 *expands*; a 64-char ID becomes 86 chars. |
| A6 | **Persistent table + random token** (this proposal) | **Chosen.** Survives restart, fits every payload with margin, enables ownership/scope binding and single-use. |
| A7 | **Reusable tokens (no `consumed_at`)** | Rejected for mutating actions (replay risk). Considered for read-only scopes — see O-4. |
| A8 | **New background pruning worker** | **Rejected** — violates the approved architecture. Existing hooks suffice. |

---

## 15. [REV-2] Explicit unresolved owner decisions

Implementation is **blocked** until these are decided. None is answered by the current baseline.

| ID | Decision | Options | Recommendation | Impact if unanswered |
|---|---|---|---|---|
| **O-1** | Token length/alphabet | 12 (`token_urlsafe(9)`) vs 16 vs prefixed `~` | **12** | Blocks table/token design |
| **O-2** | TTL and caps | TTL 30 min; `MAX_ROWS` 5000; `PRUNE_BATCH` 200 | As proposed, **insert-path cap mandatory** | Blocks TTL + cleanup design |
| **O-3** | Cleanup attachment points | **Boot hook + insert-path cap** vs sweeper (needs `attachments.py` change) | **Boot hook + insert-path cap only** — **[REV-2 D-6] sweeper route rejected** | Blocks cleanup wiring |
| **O-4** | Consumption contract | Single-use all + **transaction-composing** vs spec-original self-contained `BEGIN` | **Single-use all, transaction-composing** — **[REV-2 D-1] self-contained `BEGIN` is unsafe** | Blocks consumption helper + all consuming handlers |
| **O-5** | Schema addition approval | Approve `17 → 18` tables | Required by baseline | **Hard gate** — baseline mandates explicit design-spec review before adding the table |
| **O-6** | WP-08 runbook coupling | Update `docs/OPERATIONS_RUNBOOK.md` §4 **in the same change set** as the DDL | **Yes — atomic** | **[REV-2]** `tests/test_doc_code_parity.py::test_runbook_table_count_matches_schema` asserts the literal count; adding the table **fails the test** unless the runbook is updated together |
| **O-7** | Whether Part 2 ships with or after WP-07 | Independent vs sequenced | **Sequenced after WP-07** — **[REV-2]** 4 of 14 handlers are already modified by uncommitted WP-07 work | **Hard sequencing gate** |

**[REV-2 O-6 detail]** The parity test asserts `f"**{len(tables)}** جدول"` appears in the runbook.
The runbook currently states `**17** جدول` (`docs/OPERATIONS_RUNBOOK.md`, §4). Adding
`callback_refs` makes `len(tables) == 18`, so the assertion fails unless the runbook is updated in
the same change set. **The count must be derived from `bot/db.py::_init_schema`, not hardcoded.**

**[REV-2 O-7 detail]** Revision 1 called this "Independent (no shared files beyond `handlers.py`)".
That is **not supportable**: WP-07's uncommitted work modifies 17 functions in `bot/handlers.py`,
including 4 of the 14 cid-bearing handlers, and adds `BEGIN IMMEDIATE`-owning methods in
`bot/db.py` that this design must compose with.

> **Owner approval is required before any implementation.** This document stops here by design.
> **A recommendation in this document is not an owner approval.**

---

## Appendix A — Evidence commands used

```
git rev-parse HEAD                       → 52e7789cc8cc97a7f7c09c9592226ab117db99a2
git status --short                       → 6 modified, 13 untracked (all pre-existing)
grep -rn "callback_refs" bot/ tests/     → 0 matches
sqlite_master table count                → 17
_btn() overflow sweep                    → deleteok: 55, unwatch: 56, files: 54
is_valid_conversation_id('a1b2c3d4e5f6') → True   (token/cid ambiguity, §3.4)
pytest -q                                → 3385 passed (baseline, unchanged)
```
