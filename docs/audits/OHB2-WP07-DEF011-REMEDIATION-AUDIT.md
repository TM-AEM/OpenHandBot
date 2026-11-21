# OHB2 — WP-07 / DEF-011 Remediation Audit

**Task ID:** `OHB2-WP07-DEF011-REMEDIATION-AUDIT-AND-IMPLEMENTATION-PLAN`
**Date:** 2026-11-19
**Mode:** audit + planning only. **No production code, test, schema, or Git state was modified.**
**Recorded by:** AI agent (OpenHands) on behalf of the repository owner.

> **Evidence classes** — every claim below is tagged:
> **[FACT]** verified in this task by command/source reading ·
> **[HIST]** inherited from an existing project document, not re-executed ·
> **[ASSUME]** stated assumption, unverified ·
> **[OPEN]** unresolved question requiring an owner decision.

---

## 1. Baseline (Phase 1) [FACT]

| Field | Value |
|---|---|
| Repository root | `/workspace/project/OpenHandBot` |
| Branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` |
| HEAD | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| `origin/main` | identical (`0 0` ahead/behind) |
| Staged | **0** |
| Tracked modifications | **6** |
| Untracked | **29** |
| Ignored | **8** |

### 1.1 Modified files (pre-existing WP-07 work — untouched by this task)

```
 M .agent/PROGRESS.md
 M bot/db.py
 M bot/handlers.py
 M bot/watcher.py
 M tests/test_handlers.py
 M tests/test_sw06_unwatch_db_failure_propagation.py
```

### 1.2 DEF-011 target files — verified UNMODIFIED [FACT]

| File | SHA-256 (16) | Modified? |
|---|---|---|
| `bot/attachments.py` | `7e448b52ac3b5f47` | **NO** |
| `bot/polling.py` | `9b9c8d7e53ec467b` | **NO** |
| `bot/app.py` | `f28562f3551d59b8` | **NO** |

`git status --short bot/attachments.py bot/polling.py` returns empty ⇒ both match HEAD.
**No DEF-011 implementation exists in either committed or uncommitted form.**

### 1.3 WP-07 work preserved [FACT]

All 6 modified files and all 6 untracked `tests/test_wp07_*.py` files remain exactly as found.
No file was written, staged, restored, or deleted by this task.

---

## 2. What DEF-011 actually is (Phase 2)

### 2.1 Authoritative statement [HIST]

Source: `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md:230-244`

> **`DEF-011` — Missing Cross-Download Reservation Lock, Sync Disk I/O, & Misleading Acceptance UX**
> - **Severity:** `MEDIUM`
> - **Validation Verdict:** `CONFIRMED`
> - **Exact Source Location:** `bot/attachments.py:612-644,699-735,1062-1135`;
>   `bot/handlers.py:1609-1611,1689,1714-1990`
> - **Root Cause:** `StagingStore.store` checks quotas without reserving concurrent in-flight byte
>   budgets across the 4 allowed download streams (`_get_download_semaphore`); `_write_to_path`
>   (`os.fsync`) and `AttachmentReaper.sweep` run synchronous filesystem I/O inside the asyncio
>   event loop; `ATTACHMENT_ACCEPTED_TEXT` omits that uploads are staged locally only (`Stage B`
>   absent).
> - **Owner Approval Requirements:** `NONE` (unless altering D-12 aggregate defaults).

### 2.2 DEF-011 is THREE distinct sub-defects [FACT]

The finding title and root cause name three separable problems. The task's framing ("no
`asyncio.to_thread`" + "no quota-accounting mechanism") describes **only sub-defect B and part of
A** — it omits **sub-defect C** entirely.

| # | Sub-defect | Original location | Owner of remediation |
|---|---|---|---|
| **A** | Missing cross-download **reservation ledger** — quota checks read actual disk state but never reserve in-flight bytes across the 4 concurrent streams ⇒ dormant TOCTOU overshoot | `attachments.py:699-735` (`quota_block`, `byte_quota_block`, `_effective_cap`) | **WP-07** |
| **B** | **Synchronous disk I/O on the event loop** — `_write_to_path` (`os.fsync`) and `AttachmentReaper.sweep` | `attachments.py:612-644`, `:1062-1135` | **WP-07** |
| **C** | **Misleading acceptance UX** — `ATTACHMENT_ACCEPTED_TEXT` implies remote delivery when files are only staged locally | `handlers.py:1609-1611` (now `:1876-1878`) | **WP-01** |

### 2.3 Work-package split [HIST]

Source: baseline `:544` and `:682`.

- **WP-01** includes: `DEF-001`, **`DEF-011` (UX copy portion)**, `NEW-DEF-06`.
- **WP-07** includes: `DEF-006`, **`DEF-011` (quota lock + async disk I/O)**, `DEF-013`, `NEW-DEF-03`.

⇒ **Sub-defect C is NOT in WP-07's scope.** Implementing the UX copy change under this task would
be scope creep into WP-01, which is itself **fully blocked** on `OD-01` + `OD-03` + pre-change
inventory (baseline `:477`).

### 2.4 Dependencies [FACT + HIST]

| Dependency | Relationship |
|---|---|
| **DEF-006 / OD-04** | **[FACT] Sub-defect A is unreachable while dispatch is sequential.** `TelegramPoller.process_updates` awaits `dispatch_and_wait` per update (`put` → `join`) ⇒ only one attachment handler runs at a time ⇒ the 4-stream race cannot occur in production. Baseline `:462` confirms: *"Under `OD-04` Option A, intra-batch uploads stay strictly serialized."* |
| **DEF-013** | **[FACT] None.** Different code path (`renew_awaiting` / whitespace validation). No shared state with attachment staging. |
| **NEW-DEF-03** | **[FACT] None.** Different code paths (state+outcome atomicity in navigation/reply handlers). |
| **NAV-01..06** | **[FACT] None.** NAV changes touch `start`, `show_menu`, `list_conversations`, `list_watches`, `start_new_chat`, `open_conversation`. DEF-011 touches `StagingStore`, `AttachmentReaper`, `AttachmentService.accept`, `_download_attachment_chunks`. **No overlap ⇒ no dependency on unaccepted NAV work.** |
| **WP-05** | **[FACT] None.** WP-05 markers live in `outbox.py`, `notifier.py`, `openhands_client.py`, and `db.py:3585`. DEF-011 targets `attachments.py` (0 WP-05 markers). |
| **WP-06 Part 2** | **[FACT] None.** Blocked by O-7; unrelated tables (`callback_refs` absent). |
| **D-12** | **[FACT] Sub-defect A is inert by default.** All aggregate quotas default to `None` ⇒ disabled. Enabling them requires an owner decision. |

### 2.5 Owner-decision restrictions [FACT]

| Decision | Restriction on this work |
|---|---|
| **D-12** | Aggregate quota defaults must remain `None`. **Implementing a reservation ledger that is always-on would alter D-12 defaults ⇒ prohibited without owner approval.** A ledger that is inert when `quota_enabled is False` respects D-12. |
| **OD-04** | Unresolved. Must not introduce concurrency. A reservation ledger is only *meaningful* under concurrency, but it must not *create* concurrency. |
| **OD-01 / OD-03** | Block WP-01 (sub-defect C). Out of scope here. |

---

## 3. Source-level findings (Phase 3) [FACT]

### 3.1 Confirmed blocking operations on the event loop

| Operation | Function | Sync? | Runs on event loop? | Evidence |
|---|---|---|---|---|
| Attachment write + `os.fsync` | `StagingStore._write_to_path` | **YES** (`os.open`/`write`/`flush`/`os.fsync`) | **YES** | `attachments.py:612-644`; called at `:956` from `async def accept` (`:864`) |
| Staging directory walk | `staging_total_bytes` | **YES** (`iterdir` + `lstat` per entry) | **YES** | `attachments.py:296-323`; called from `_effective_cap` (`:598`) |
| Per-item disk stat loop | `StagingStore._batch_active_files` | **YES** (`os.lstat` per item) | **YES** | `attachments.py:549-570`; called by `quota_block`/`byte_quota_block` |
| Reaper sweep | `AttachmentReaper.sweep` | **YES** (`lstat`/`unlink`/`iterdir`) | **YES** | `attachments.py:1062-1148`; called from `async def tick` via `maybe_sweep` (`watcher.py:183`) |
| Local Bot-API file read | `_read_local_capped` | **YES** (`open`/`read` loop) | **YES** | `handlers.py:1999-2012`; called inside `_download_attachment_chunks` |
| Content head re-read | `_read_head` | **YES** | **YES** | `attachments.py:352-355`; called at `:757` |

### 3.2 Confirmed async / non-blocking operations

| Operation | Mechanism |
|---|---|
| Telegram file metadata | `await context.bot.get_file(file_id)` |
| HTTP stream download | `async with client.stream(...)` (httpx async) |
| Conversation authorization | `await files.authorize_conversation_detailed(...)` |
| Download concurrency bound | `async with _get_download_semaphore()` (max 4) |

### 3.3 The exact call chain that blocks [FACT]

```
handlers.handle_attachment (async)
  └─ await _download_attachment_chunks(...)          # async, network only
       └─ async with _get_download_semaphore():      # bounds to 4 streams
            ... await client.stream(...) ...         # network — fine
            return iter([bytes(buf)])                # ← chunks FULLY materialized in RAM
  └─ await service.accept(..., chunks_factory=...)   # async
       └─ await chunks_factory()                     # returns the in-memory iterator
       └─ self._store.store(...)                     # ← SYNC CALL, no await
            └─ _write_to_path(...)                   # ← os.open/write/fsync BLOCKS LOOP
            └─ _read_head(...)                       # ← blocks loop
```

**Severity of the stall:** capped at `MAX_ATTACHMENT_BYTES = 3 MiB` per file
(`attachments.py:100`). So the worst case is a ~3 MiB write + fsync per attachment, not unbounded.

### 3.4 Critical safety fact: `chunks` contains no I/O [FACT]

`_download_attachment_chunks` ends with `return iter([bytes(buf)])` (`handlers.py:~2190`).
The download is **already complete** and fully buffered before `store()` is called.

⇒ Consuming `chunks` in a worker thread performs **no network and no generator I/O**. It is a pure
in-memory iteration. **This makes offloading `_write_to_path` safe.**

### 3.5 Critical safety fact: SQLite must NOT cross the thread boundary [FACT]

| Fact | Evidence |
|---|---|
| One shared connection | `bot/db.py:551` — `sqlite3.connect(path, check_same_thread=False)` |
| **No threading lock** guarding it | grep for `threading.Lock` / `_lock` in `db.py` ⇒ **none** |
| Transaction convention | `conn.execute("BEGIN IMMEDIATE")` at 10+ sites (`:1257,1601,1704,1761,1804,1883,1981,…`) |
| Baseline's explicit warning | `:687` — *"separating SQLite queries on the owner connection from thread-offloaded file I/O so `sqlite3.Connection` is never shared unsafely across worker threads"* |
| Baseline's intent | `:336` — *"`DEF-011` blocking disk I/O via `asyncio.to_thread` **without touching SQLite from worker threads**"* |

⇒ **Any offload must move ONLY file operations.** All `self._db.*` calls must stay on the loop
thread. `check_same_thread=False` disables sqlite3's *guard*, not the underlying thread-safety
requirement — a shared connection driven from two threads concurrently can corrupt transaction
state or raise `InterfaceError`/`ProgrammingError`.

### 3.6 `store()` interleaves DB and file I/O [FACT]

Reading `store()` (`attachments.py:646-810`) shows strict interleaving:

```
(0)   self._db.get_attachment_batch(...)        ← DB
(0b)  declared_size check                       ← pure
(0c)  _is_denied_extension                      ← pure
      self.ensure_root()                        ← FS (mkdir/chmod)
(0d)  self.quota_block(...)                     ← DB + FS (lstat loop)
(0f)  self.byte_quota_block(...)                ← DB + FS (lstat loop)
(0g)  self._effective_cap(...)                  ← DB + FS (iterdir)
(1)   self._db.add_attachment_item(...)         ← DB  (skipped when row_created=True)
(2)   self._write_to_path(...)                  ← FS  ← PURE-I/O REGION
(3)   _read_head(path)                          ← FS  ← PURE-I/O REGION
(4)   self._db.try_mark_attachment_item_stored  ← DB
```

⇒ **You cannot wrap `store()` in `to_thread`.** Only step (2) and step (3) are offloadable; steps
(0), (0d), (0f), (0g), (1), (4) must remain on the loop thread.

### 3.7 Cancellation and partial-file semantics [FACT]

`_write_to_path` already handles this correctly:

```python
except BaseException:
    _safe_unlink(path)   # no partial file left under the item name
    raise
```

Because `BaseException` (not `Exception`) is caught, `asyncio.CancelledError` also triggers cleanup.
**Any offload must preserve this guarantee.** A naive `to_thread` around a partial write that is
cancelled mid-flight leaves the thread running (Python cannot kill threads) — so the cleanup must
remain *inside* the thread function, not outside it.

---

## 4. Quota analysis (Phase 4)

### 4.1 Is a durable quota ledger required? **No.** [FACT]

| Question | Answer | Evidence |
|---|---|---|
| Do quota limits exist? | **Yes**, as parameters | `max_items_per_batch`, `max_total_bytes`, `max_bytes_per_batch` (`attachments.py:492-506`) |
| Are they enabled by default? | **NO — all `None`** | Constructor defaults (`:496-499`); `quota_enabled` property returns `False` (`:538-545`) |
| How is the store constructed in production? | **With no quota args** | `handlers.py:1964` — `StagingStore(db, config.db_path)` |
| Is there an existing reservation ledger? | **NO** | grep `reserv` across `bot/` ⇒ zero matches (only unrelated `ip.is_reserved`) |
| Does a quota column exist in the schema? | **NO** | grep `quota\|reserved_bytes\|reservation` in `db.py` ⇒ zero |
| Does the baseline ask for a *durable* ledger? | **NO — "in-process async reservation ledger"** | baseline `:687` |

⇒ **The requirement is an in-process ledger, not a durable one.** No schema change is required, and
the 17-table baseline is preserved.

### 4.2 What the quota is intended to limit [FACT]

| Limit | Intended to bound |
|---|---|
| `max_bytes` (always on) | A single file — 3 MiB (`MAX_ATTACHMENT_BYTES`) |
| `max_items_per_batch` | Files per batch (`MAX_ITEMS_PER_BATCH = 10`, reference only) |
| `max_total_bytes` | Total staging directory size (`MAX_STAGING_TOTAL_BYTES = 64 MiB`, reference only) |
| `max_bytes_per_batch` | Bytes per batch |

All three aggregate limits are **reference values only, explicitly not enforced by default** under
D-12 (`attachments.py:106-107` comments).

### 4.3 Current accounting model [FACT]

`_batch_active_files` and `staging_total_bytes` count **actual files on disk**, not historical rows
(a deliberate FIX-R02 decision). This is correct for steady state but has two consequences:

1. **TOCTOU window:** between the check (`quota_block`) and the write (`_write_to_path`), another
   concurrent stream can write bytes. With N concurrent streams the overshoot is bounded by
   `(N-1) × 3 MiB` — with N=4, up to **9 MiB** past the limit.
2. **It self-heals:** because accounting reads real disk state, an abandoned in-flight item
   consumes nothing until bytes land. No reservation cleanup is needed for correctness — only for
   accurate *admission*.

### 4.4 Race reachability [FACT]

**The race is unreachable in production today.** `process_updates` awaits each update to completion
before starting the next (`polling.py:164-165`), so at most **one** attachment handler runs at a
time. `MAX_CONCURRENT_DOWNLOADS = 4` bounds *streams within one handler*, not *handlers*.

⇒ Sub-defect A is **dormant** — exactly as the baseline classifies it ("Dormant quota overshoot if
aggregate limits are enabled"). It becomes live **only** under OD-04 Option B.

### 4.5 Owner-decision boundary [OPEN]

Implementing a reservation ledger that is **always active** would change the effective admission
behaviour even with quotas disabled — an implicit D-12 change.

**Correct boundary:** the ledger must be **inert when `quota_enabled is False`**, so default
behaviour is byte-identical to today.

---

## 5. Architecture assessment (Phase 5)

| Constraint | Compatible? | Reasoning |
|---|---|---|
| One bot + ASGI process | **YES** | An `asyncio.to_thread` offload uses the default executor; no new process |
| One authoritative SQLite owner | **YES — if DB stays on loop thread** | `to_thread` is used only for file ops |
| Existing outbox/workers only | **YES** | No new worker, queue, or scheduler |
| No new background service | **YES** | `to_thread` uses the existing default thread pool |
| No app backup feature | **YES** | Unrelated |
| No exactly-once Telegram claim | **YES** | Offload does not change delivery semantics |
| Fail-closed where required | **YES** | `store()` already returns `WRITE_FAILED`/`DB_FAILED`; offload preserves the exception contract |
| Existing `_nocommit` conventions | **YES** | Untouched — no DB refactor |
| Existing cleanup abstractions | **YES** | `_safe_unlink` reused inside the thread function |

### 5.1 Interaction summary

| Item | Interaction |
|---|---|
| **DEF-006 / OD-04** | Sub-defect A's *necessity* depends on OD-04 Option B. Offload (sub-defect B) is **independent** of OD-04 and safe today. |
| **DEF-013** | **None** |
| **NEW-DEF-03 (accepted)** | **None** |
| **NAV-01..06 (unaccepted)** | **None — no dependency** |
| **WP-05** | **None** |
| **WP-06 Part 2** | **None** |
| **WP-01 (sub-defect C)** | Blocked on OD-01/OD-03 — **must not be touched here** |

---

## 6. Implementation status — verified

| Sub-defect | Status | Evidence |
|---|---|---|
| **A** — reservation ledger | **NOT IMPLEMENTED** | Zero `reserv` matches in `bot/`; `quota_block` reads disk without reserving |
| **B** — async disk I/O offload | **NOT IMPLEMENTED** | Zero `to_thread`/`run_in_executor` in `bot/attachments.py`; `store()` called synchronously from `async def accept` |
| **C** — UX copy | **NOT IMPLEMENTED** | `ATTACHMENT_ACCEPTED_TEXT` (`handlers.py:1876-1878`) still says only "استلمت الملف ✅ — ابعت أوامرك…" with no local-only disclosure |

**No partial implementation exists under another helper or abstraction.** [FACT — verified by
repository-wide grep]

> One *precedent* exists, but it is not a partial DEF-011 implementation:
> `bot/web/download.py` uses `starlette.concurrency.run_in_threadpool` for the Mini App download
> path (a separate, already-shipped feature). It is **architectural evidence that offloading is
> acceptable in this codebase**, and it establishes the pattern (offload `os.read` only; never DB).

---

## 7. Existing test coverage [FACT]

| Test file | Covers | Gap |
|---|---|---|
| `tests/test_repair_plan_01_resource_staging.py` | Sequential quota enforcement (`max_items_per_batch`, `max_total_bytes`), stream caps, semaphore bound | `test_concurrent_downloads_are_bounded` asserts only that **stream count** ≤ 4 — it does **not** assert quota correctness under concurrency |
| `tests/test_attachment_staging_a1.py` | Staging write path, collision, size rejection | No event-loop-responsiveness assertion |
| `tests/test_attachment_cleanup_expiration_a4.py` | Reaper sweep correctness | No blocking/offload assertion |
| `tests/test_repair_plan_02_life01_opportunistic_cleanup.py` | Sweeper throttling/re-entrancy | No blocking assertion |

**Missing coverage (all four are new):**

1. **Event-loop responsiveness** during a 3 MiB write — no test measures loop latency while `store()` runs.
2. **Offload proof** — no test asserts the write happened off the loop thread.
3. **Concurrent quota race** — no test drives N concurrent `accept()` calls against an enabled aggregate cap.
4. **Cancellation mid-write** — no test cancels during the write and asserts no partial file survives.

---

## 8. Verified facts vs historical claims vs assumptions vs open questions

### 8.1 Verified facts [FACT]

1. `bot/attachments.py`, `bot/polling.py`, `bot/app.py` are unmodified (match HEAD).
2. `store()` is called synchronously from `async def accept` (`attachments.py:956`).
3. `_write_to_path` performs `os.open`/`write`/`flush`/`os.fsync` synchronously (`:612-644`).
4. `AttachmentReaper.sweep` runs synchronously from `async def tick` (`watcher.py:183`).
5. Zero `to_thread`/`run_in_executor` in `bot/attachments.py`.
6. Zero reservation-ledger code anywhere in `bot/`.
7. All aggregate quotas default to `None`; production constructs `StagingStore` with no quota args.
8. `sqlite3.connect(..., check_same_thread=False)` with a single shared `_conn` and **no** threading lock.
9. 17 unique tables; no quota/reservation column.
10. `chunks` is fully materialized (`iter([bytes(buf)])`) before `store()` is called.
11. `process_updates` dispatches strictly sequentially.
12. `_write_to_path` catches `BaseException` and unlinks partial files.
13. `bot/web/download.py` already offloads file reads via `run_in_threadpool`.
14. DEF-011's UX portion belongs to WP-01, not WP-07.

### 8.2 Historical claims (not re-executed) [HIST]

- "Event-loop stalls during 3 MB sync writes or sweeps" (baseline `:239`) — plausible from source,
  **not measured** in this task.
- "Dormant quota overshoot … permitting parallel downloads to overshoot aggregate limits"
  (defect register `:334`) — **consistent with source**, not reproduced by a live test.
- Baseline's assertion that `AttachmentReaper.sweep` is blocking — **confirmed by source reading**,
  not by measurement.

### 8.3 Assumptions [ASSUME]

1. The default asyncio thread-pool executor is acceptable for a ≤3 MiB write; no custom executor is
   required.
2. `anyio.to_thread.run_sync` (via `starlette.concurrency.run_in_threadpool`, already a project
   dependency through Starlette/FastAPI) is available and preferable to raw `asyncio.to_thread`
   for cancellation semantics.
3. A per-`StagingStore`-instance in-process ledger is sufficient; no cross-process coordination is
   needed because there is exactly one bot process.

### 8.4 Open questions [OPEN]

1. **OD-04** — unresolved. Determines whether sub-defect A is ever reachable. **Does not block
   sub-defect B.**
2. **D-12** — no owner decision recorded authorizing aggregate quota enablement. A ledger that is
   inert by default respects it, but whether to build it *now* is an owner call.
3. **DEF-011 UX copy (sub-defect C)** — blocked in WP-01 by OD-01/OD-03. Not this task.
4. **DEF-001** — attachment intake remains enabled by default while Stage B is absent. Out of scope
   here, but it is the reason sub-defect C matters.

---

## 9. Conclusion

**DEF-011 is a three-part finding.** Only two parts belong to WP-07:

- **B (async disk I/O offload)** — safe, self-contained, **independent of every unresolved owner
  decision**, and implementable now.
- **A (reservation ledger)** — dormant while dispatch is sequential; meaningful only under OD-04
  Option B; must be inert by default to respect D-12.

**C (UX copy)** belongs to WP-01 and is blocked there.

**The task's premise is partly imprecise:** DEF-011 is not merely "no `to_thread` + no quota
ledger". It also includes a UX-copy defect owned by a different, currently blocked work package.

**Recommendation:** implement **sub-defect B only** now, under an explicit owner authorization; defer
**A** to OD-04; leave **C** to WP-01.

See `OHB2-WP07-DEF011-IMPLEMENTATION-PLAN.md` for the concrete option set and ordered plan.
