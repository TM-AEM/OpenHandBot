# OHB2 — WP-07 / DEF-011-A — Attachment Staging Capacity Reservation & Aggregate Quota — Diagnosis and Owner Decision Brief

**Task:** `OHB2-WP07-DEF011-A-ATTACHMENT-CAPACITY-RESERVATION-DIAGNOSIS-AND-DECISION-BRIEF`
**Date:** 2026-11-21
**Type:** read-only diagnosis + decision brief. **No implementation.** No code, test, schema, config, or
lifecycle change was made. The only file written is this report.

**Status:** `A_DIAGNOSIS_COMPLETE_DECISION_REQUIRED` (see §14).

---

## 1. Finding definition and source

### 1.1 What DEF-011-A is

`DEF-011` is the WP-07 attachment-staging finding set with three sub-defects:

| Sub-defect | Scope | Meaning |
|---|---|---|
| `DEF-011-B` | WP-07 | Filesystem writes/reads off the event loop (`to_thread`). **Implemented.** |
| **`DEF-011-A`** | WP-07 | **Attachment staging capacity reservation and aggregate quota enforcement.** |
| `DEF-011-C` | WP-01 | Attachment acceptance UX copy. **Not implemented.** |

### 1.2 The ATT-01 record (authoritative planning statement)

The task refers to a file named `PLAN-08-Attachment-Staging-Limits-and-Media-Scope.md`. **That exact file
does not exist in the live tree.** The live authoritative sources are:

- `docs/reviews/OHB2-PLAN-08-MANUAL-ATTACHMENT-TRANSFER-UX-DESIGN.md` — limits table **L1–L7** (lines 228–243).
- `docs/reviews/OHB2-PLAN18-ATTACHMENT-POLICY-AND-MEDIA-SCOPE-REPORT.md` — ATT-01/ATT-02 report.
- `.agent/PROGRESS.md:4188` and `.agent/PROGRESS.md:4199` — the ATT-01 working records.

The live ATT-01 statement (`.agent/PROGRESS.md:4188`) reads, in substance: the per-file cap
`MAX_ATTACHMENT_BYTES = 3 MiB` is always enforced, while the aggregate quotas
(`MAX_ITEMS_PER_BATCH=10`, `MAX_STAGING_TOTAL_BYTES=64 MiB`, `max_bytes_per_batch`) are **disabled by
default (`None`)** and have **no `bot/config.py` / `.env.example` keys**; permanent policy `D-12`
(scope 2) remains **unresolved / OWNER_DECISION_REQUIRED**.

**Important correction to the task's framing.** The task says the aggregate limits "were previously
recorded as an approved policy choice". The live record says the opposite for the *disabled* state:
`.agent/PROGRESS.md:4199` records that "Plan 01 Option A" (the disabled-by-default choice) was proven to
be **a conservative, reversible engineering interpretation — not a recorded owner approval** — and that
`D-12` remains **unresolved**. So **neither** "keep disabled" **nor** "enable" is currently owner-approved.
This brief therefore treats the policy as **open**, exactly as the task requires ("without assuming owner
approval").

### 1.3 Historical-vs-live drift (why the live tree was inspected)

The PLAN-08 document's line numbers are **stale** relative to the live tree, confirming that historical
baselines are evidence, not proof of current state:

| Reference | PLAN-08 historical | Live (2026-11-21) |
|---|---|---|
| `MAX_ATTACHMENT_BYTES` | `attachments.py:99` | `bot/attachments.py:105` |
| `_effective_cap` | `attachments.py:569` | `bot/attachments.py:609` |
| intake cap read | `handlers.py:1878` | `bot/handlers.py:2201` |

---

## 2. Live repository baseline (Phase 1)

| Item | Value |
|---|---|
| Branch | `openhands-workspace-11yyMvqKPjTrIZt1RRpWq9` |
| `HEAD` | `30dfa0d6432cdb8f7787edde38f48fb482b6ced6` |
| `origin/main` | `30dfa0d…` (in sync) |
| Remotes | `origin https://github.com/TM-AEM/OpenHandBot.git` |
| Pre-existing **tracked modifications** | `docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md`, `tests/test_doc_code_parity.py` (from earlier tasks) |
| Pre-existing **untracked** | `docs/audits/OHB2-WP07-DEF011-F03-STALE-REFERENCE-CORRECTION-REPORT.md`, `docs/reviews/OHB2-WP07-DEF011-F03-GENUINELY-INDEPENDENT-REVIEW-REPORT.md` (from earlier tasks) |
| Pre-existing **ignored** | `.openhands/`, `.agent/` (preserved; not touched) |

All pre-existing changes were **preserved**. This task modified **none** of them.

**Attachment staging implementation and DB ownership:**

- `bot/attachments.py` (1883 lines) — `StagingStore` (A1 write), `AttachmentService` (A2 accept),
  `AttachmentReaper` (A4 sweep), `OpportunisticSweeper` (LIFE-01).
- `bot/handlers.py` — intake handler and production `StagingStore` construction.
- `bot/db.py` — the **single** authoritative SQLite owner (`Database`); attachment tables
  `attachment_batches`, `attachment_items`, `attachment_message_identity` (17 unique tables total).
- `bot/config.py` — no aggregate-quota keys.
- `bot/app.py` — one `Application`, one `Database`, one reaper, one watcher.

**Single-process, single-connection, single-owner model is intact.** No new owner/worker/scheduler exists.

---

## 3. Effective configuration values and their sources

| Limit | Effective value | Source (live) | Enforced? |
|---|---|---|---|
| Per-file bytes | **3 MiB** = 3 145 728 B | `bot/attachments.py:105` `MAX_ATTACHMENT_BYTES`; default in `StagingStore.__init__` (`:502`) and `precheck_rejection` (`:366`) | **YES (always)** |
| Files per batch | **`None` (disabled)** | `bot/attachments.py:111` `MAX_ITEMS_PER_BATCH = 10` is a **reference only**; `StagingStore.__init__(max_items_per_batch=None)` (`:504`) | **NO** |
| Aggregate staged bytes | **`None` (disabled)** | `bot/attachments.py:112` `MAX_STAGING_TOTAL_BYTES = 64 MiB` is a **reference only**; `StagingStore.__init__(max_total_bytes=None)` (`:505`) | **NO** |
| Per-batch bytes | **`None` (disabled)** | `StagingStore.__init__(max_bytes_per_batch=None)` (`:506`); no default constant | **NO** |
| Staging expiry | **15 minutes** (fixed, never extended) | `bot/db.py:261` `ATTACHMENT_BATCH_TTL = timedelta(minutes=15)`; `batch_is_expired` (`attachments.py:406`) | **YES** |
| Concurrent downloads | **4** | `bot/handlers.py:1972` `MAX_CONCURRENT_DOWNLOADS = 4`; semaphore at `:1983`/`:2075` | **YES** |
| Document intake on/off | **True** | `bot/config.py:316` `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` (default True); `.env.example:2` | **YES** |
| Watcher tick | **25 s** | `bot/config.py:18` / `:224` `WATCHER_INTERVAL` default 25 | **YES** |
| Opportunistic sweep min interval | **60 s** | `bot/attachments.py:123` `OPPORTUNISTIC_SWEEP_MIN_INTERVAL_SECONDS = 60.0` | **YES** |

**No env/config override exists for any aggregate quota.** `grep -nE "ATTACH|STAG|QUOTA|MAX_" .env.example`
returns only `ATTACHMENT_DOCUMENT_INTAKE_ENABLED`. There are **no** explicit `max_items_per_batch=`,
`max_total_bytes=`, or `max_bytes_per_batch=` arguments anywhere in `bot/` (only the defaults). The single
production construction site is `bot/handlers.py:1960` `_attachment_service()`, which calls
`StagingStore(db, config.db_path)` with defaults (`:1966`) and caches it in
`context.bot_data["attachment_store"]` (`:1967`).

---

## 4. File-by-file staging lifecycle (Phase 2)

### 4.1 Intake entry

`bot/handlers.py:2141 handle_attachment`:

1. `_guard` (owner-only, private chat).
2. Intake kill-switch check (`attachment_document_intake_enabled`).
3. Requires an open explicit `route` conversation (`db.awaiting_state`), else rejects.
4. Extracts one `file_id` (`_attachment_file_id`) — **one file per update**.
5. `service = _attachment_service(context)`; `max_bytes = service.store.max_bytes` (`:2201`).
6. `service.accept(..., chunks_factory=_chunks_factory)` (`:2208`).

### 4.2 `AttachmentService.accept` (`bot/attachments.py:1034`)

Order (fail-closed):

| Step | What happens | Where |
|---|---|---|
| (1) | Conversation authorization (ownership + deletion witness) | `:1046` `_authorized` |
| (2) | Normalize declared size; cheap reject on declared > 3 MiB; extension check | `:1056`–`:1063` |
| (3) | Classify batch (read-only): `NEW` / `APPEND` / `EXPIRED` | `:1066` `classify_incoming_file` (`:464`) |
| (3b) | Expired batch is marked `expired`; file starts a **new** batch | `:1080`–`:1085` |
| (4) | **Row-first**: insert `attachment_items` row (`pending`) + durable update outcome, atomically (`BEGIN IMMEDIATE`) | `:1088`–`:1117`; DB `accept_attachment_item` (`db.py:1734`) / `accept_attachment_item_into_new_batch` (`db.py:1782`) |
| (5) | Download bytes (`chunks_factory`) — capped at 3 MiB, under download semaphore | `:1120`; `handlers._download_attachment_chunks` (`:2058`) |
| (5b) | `store_async(...)` — **quota check → write → mark**, all under `_accept_lock` | `:1126`; `store_async` (`:876`), lock at `:918` |

**Key ordering:** the DB row exists **before** any byte is written (`row-first`), and the bytes are
downloaded **before** the staging write (because the download is the input stream). The quota check and
the write happen **after** the download, inside the store lock.

### 4.3 `StagingStore.store_async` (`bot/attachments.py:876`)

```
async with self._accept_lock:              # :918
    prep = self._store_prepare(...)        # :919  quota checks + row (if not row_created) + cap
    ... await to_thread.run_sync(_worker)  # :966  pure FS write in a worker thread
    return self._store_finalize(...)       # :977  CAS pending→stored (or unlink+reject)
```

- `_store_prepare` (`:657`) performs: batch ownership check, declared-size/extension checks, **item
  quota** (`quota_block`, `:583`), **per-batch byte quota** (`byte_quota_block`, `:598`), and
  **effective cap** (`_effective_cap`, `:609`), then the row-first insert if `row_created=False`.
- `_write_to_path` (`:623`) enforces the cap **during** the streaming write: `if written + len(chunk) >
  cap: raise _TooLargeError` (`:648`), and unlinks any partial file on any exception (`:652`).
- `_store_finalize` (`:758`) rejects empty/denied-magic, then calls
  `db.try_mark_attachment_item_stored` (`db.py:1224`) — a **conditional CAS** requiring
  `item.status='pending' AND batch.status='pending'` in one `UPDATE`. On `False` it unlinks and fails closed.

### 4.4 Accounting model

| Function | Scope | What it counts |
|---|---|---|
| `_batch_active_files(batch_id)` (`:560`) | **per batch** | **Actual regular files on disk** for that batch's items (any item status; missing file ⇒ 0). Docstring: "المحاسبة على **الموارد الفعلية** لا على الصفوف التاريخية". |
| `quota_block(batch_id, extra_items=1)` (`:583`) | per batch | `count + extra_items > max_items_per_batch` |
| `byte_quota_block(batch_id)` (`:598`) | per batch | `total + extra_bytes > max_bytes_per_batch` |
| `_effective_cap(batch_id)` (`:609`) | per batch + **global** | `min(max_bytes, max_total_bytes − staging_total_bytes(root), max_bytes_per_batch − used)` |
| `staging_total_bytes(root)` (`:301`) | **global** (whole staging root) | sum of all regular files in `<db_dir>/attachment_staging`; symlinks/dirs not followed |

So: **count and per-batch byte caps are per-batch** (user + conversation + batch); the `max_total_bytes`
cap is **global across the whole staging root** (all users/conversations/batches); the per-file cap is
per file.

### 4.5 Batch lifecycle and cleanup

- Batch states: `pending` → `intent_recorded` → `dispatching` → `delivered` / `failed` / `rejected` /
  `expired` (plus `uncertain`).
- `AttachmentReaper` (`:1222`) is constructed once at startup (`app.py:240`) with **its own** `StagingStore`
  (`:1259`) but the **same** `Database` object (no second connection).
- `sweep_async` (`:1283`): DB phase on the loop thread (`_sweep_db_phase`, `:1308`) → FS tail in a worker
  thread (`_sweep_fs_tail`, `:1385`) → finalize/log.
- DB-first: mark batch `expired` → CAS item `reaped` (`db.py:1463`) → only then unlink bytes
  (`_remove_file`, `:1684`).
- Reaper runs at startup (`app.py:240`) and opportunistically on the existing Watcher tick via
  `OpportunisticSweeper` (`:1744`), throttled to ≥60 s (`:123`).

---

## 5. Actual concurrency and resource-exhaustion assessment (Phase 3)

### 5.1 Is intake actually concurrent?

**No, not in production.** `Application` is built with `.concurrent_updates(True)` (`app.py:89`), but the
custom poller dispatches **sequentially**:

```python
# bot/polling.py:175-178
async def dispatch_and_wait(self, update) -> None:
    await self.application.update_queue.put(update)
    await self.application.update_queue.join()
```

One update is enqueued and fully processed (`join()`) before the next. `app.py:75-85` documents this
explicitly and states that intra-batch concurrency (`OD-04`) is **forbidden** without a proven safety
argument. `handle_attachment` handles **one file per update** (`_attachment_file_id`), so there is no
multi-file parallel intake within an update. A media group (album) arrives as multiple sequential updates.

**Defense in depth:** even if concurrency were introduced, `store_async` holds `_accept_lock` (`:918`)
across **quota check → write → mark**, preserving the serial model that existed before the `to_thread`
offload (documented at `:519`–`:526`). `MAX_CONCURRENT_DOWNLOADS=4` bounds concurrent downloads, but the
staging write remains serialized.

### 5.2 Is a quota check atomic through the existing SQLite owner?

The quota check is a **filesystem scan** (`_batch_active_files`, `staging_total_bytes`) executed on the
event-loop thread (the SQLite owner thread) **while holding `_accept_lock`**, and the only capacity
consumer is the same serialized accept path. Therefore the check + write + mark is atomic with respect to
every other accept. The reaper only **deletes** (frees capacity), never adds, so it can only make the cap
more conservative. **No DB transaction or ledger is required for atomicity in the supported model.**

### 5.3 Is the per-file limit alone sufficient for the supported intake pattern?

Supported pattern (ATT-02): single owner, **Document-only**, sequential intake, 15-minute TTL.
The per-file 3 MiB cap bounds **each write** and **each download buffer**. The 15-minute TTL bounds
**retention time**. But there is **no cap on how many files** can be staged in that window, so total disk
is bounded only by `upload_rate × 15 min × 3 MiB` and the host disk size. For a trusted single owner this
is normally fine; as a **hard resource guarantee** it is insufficient.

### 5.4 Do the 10-file and 64 MiB caps add meaningful protection?

**Yes.**
- `max_items_per_batch = 10` bounds a single batch to 10 files (≤ 30 MiB, since 10 × 3 MiB < 64 MiB).
  For a single user/conversation, this is the **binding** constraint.
- `max_total_bytes = 64 MiB` bounds the **whole staging root** across batches/conversations. It binds
  when several batches coexist (e.g., an expired-but-not-yet-swept batch plus a new batch, or multiple
  conversations). 64 MiB ≈ 21 files of 3 MiB.
- Both are enforced by the **already-implemented** mechanism; enabling them is a wiring choice, not new
  code.

### 5.5 Worst-case staged disk usage

| Configuration | Worst case |
|---|---|
| Current (all aggregate caps `None`) | `N × 3 MiB`, `N` = files sent within the 15-min TTL (no fixed bound); physical deletion lags TTL by up to the sweep interval (watcher tick 25 s, sweep throttle 60 s; or until next startup if the watcher is down). |
| Option B (10/batch, 64 MiB global) | ≤ **64 MiB** total on disk (hard bound), ≤ **10 files / ≤ 30 MiB** per batch. The last write is capped at the remaining global budget and aborted+unlinked if it would exceed it. |

**Orphan caveat (Option B):** `staging_total_bytes` counts **all** regular files in the root, including
untracked orphans. The reaper **deliberately preserves** untracked files
(`_scan_root_untracked` reports them; `test_case12_orphan_filesystem_file_preserved`,
`test_unreferenced_file_is_left_and_reported`). So a row-less orphan would permanently consume part of
the 64 MiB global budget. Row-first makes row-less orphans unlikely (a crash mid-write leaves a `pending`
row that expiry reclaims), but it is a real limitation of a **global** cap.

---

## 6. Failure / restart / expiry analysis

| Case | What the code does | Reachable in production? | Evidence / test |
|---|---|---|---|
| **Two simultaneous intake operations** | Not reachable: sequential poller (`polling.py:175`). If forced, `store_async` serializes under `_accept_lock`. | **No** (sequential); handled if forced | `test_T14_store_async_serializes_concurrent_accepts` (`test_def011_fs_offload.py:474`), `test_concurrent_admission_against_real_sqlite` (`test_repair_plan_01_review_findings.py:338`) |
| **Two competing for final capacity** | Serialized: first writes, second re-checks actual disk and rejects. | No (same as above) | same two tests: 12 concurrent → exactly 3 stored, 9 `REJECTED_QUOTA`, 3 files |
| **Write fails after capacity "reserved"** | There is **no reservation**. Partial file is unlinked (`_write_to_path` `:652`); row stays `pending` with no file ⇒ not counted. | Yes (disk error) | `test_case2_failure_during_byte_writing`, `test_over_cap_write_leaves_no_partial_file` (`test_repair_plan_02_life02_crash_recovery.py`) |
| **Process interruption between reservation and write** | No reservation. Row-first: row exists, file absent/partial ⇒ reclaimed at expiry. | Yes (crash) | `test_case1_failure_immediately_after_row_insertion`, `test_case7_reopen_after_interruption_recovers_pending`, `test_case9_partial_file_discoverable_and_recovered` |
| **Expiry racing with another state transition** | `try_mark_attachment_item_stored` CAS requires item `pending` **and** batch `pending` in one `UPDATE`; late write fails closed and unlinks. No `stored` item can exist inside an `expired` batch. | Yes (tick during accept) | `test_race_a/b/c1/c2`, `test_store_into_already_expired_batch_is_rejected`, `test_direct_reaped_to_stored_is_rejected` (`test_repair_plan_02_life01_f2_race.py`) |
| **Repeated expiry/cleanup** | Idempotent: missing file = `absent` = success; `reaped` item retried; re-marking `expired` is a no-op. | Yes | `test_repeated_cleanup_is_idempotent` (`test_attachment_cleanup_expiration_a4.py:190`), `test_case15_repeated_recovery_is_idempotent`, `test_e2e_repeated_sweeps_are_idempotent` |
| **Restart with partial staging** | Startup `sweep_async` (`app.py:240`) reclaims expired/terminal/orphan items; `test_startup_post_init_runs_sweep_and_cleans_expired`. | Yes | `test_repair_plan_02_life02_crash_recovery.py`, `test_e2e_recovers_stale_partial_after_interruption` |
| **Orphaned files / stale rows distort accounting** | Stale rows: not counted if file missing (`_batch_active_files`). Orphan files: counted globally, **preserved** (not deleted) ⇒ can permanently consume a **global** cap. | Yes (rare) | `test_case12_orphan_filesystem_file_preserved`, `test_unreferenced_file_is_left_and_reported` |

**Conclusion:** the current lifecycle has **no reachable over-commit race**. The only "reservation-like"
window (check → write) is closed by `_accept_lock`; the only "release" operation is an idempotent unlink;
and the only real accounting distortion is orphan files under a **global** cap (documented, preserved by
design).

---

## 7. Is a reservation ledger technically necessary?

**No.** Evidence:

1. **Serialization already exists.** `_accept_lock` (`attachments.py:526`, used at `:918`) wraps quota
   check → write → mark. This is the same serial model that existed before the DEF-011 offload
   (documented at `:519`–`:526`).
2. **Capacity is measured from reality, not from a counter.** `_batch_active_files` counts actual regular
   files (`:560`); `staging_total_bytes` counts actual bytes (`:301`). A rejected/reaped item with no file
   consumes nothing. This is why no release accounting is needed.
3. **Release is inherently idempotent.** Deleting a file that is already gone returns `absent` = success
   (`_remove_file`, `:1704`). There is no counter to double-decrement.
4. **The enforcement mechanism is already implemented and tested** (quota tests listed in §6/§12). Only the
   **defaults** are `None`.
5. **A ledger would add**: a new table/columns (breaking the 17-table invariant,
   `test_T12_schema_table_count_unchanged`), a reserve/release transaction on every path (including
   cancellation and crash), reconciliation of reserved-vs-actual on restart, and new failure modes
   (double-release, drift, permanent leak from a stale reservation). None of this is needed for a
   single-process, serialized intake.

**Simpler alternative already satisfies the requirement:** existing `attachment_items` rows + actual files
on disk + `_accept_lock` + `_effective_cap`. Enabling Option B requires **no schema change and no ledger** —
only explicit limits at the single production construction site.

---

## 8. Options (presented without selecting)

### Option A — Keep aggregate limits disabled (status quo)

1. **Accounting scope:** none for aggregates; per-file 3 MiB applies to every file.
2. **Applies to:** successfully staged bytes per file (streaming cap); rejected/partial bytes never remain.
3. **Reserve/release:** no reservation; capacity = actual bytes; release = unlink on reject/expiry/reap.
4. **On exhaustion:** only `> 3 MiB` per file is rejected (`REJECTED_SIZE`).
5. **Rejection artifacts:** none — partial file unlinked; row stays `pending` without a file (reaped at
   expiry).
6. **Restart/expiry:** unchanged; startup + tick reaper; 15-min TTL; idempotent.
7. **Schema/config changes:** **none**.
8. **Tests required:** existing per-file + lifecycle tests suffice; optionally add a log/monitoring
   assertion (there is no metric today).
9. **Trade-offs / remaining risks:** total staged disk is **unbounded within the 15-min window**
   (bounded only by upload rate × TTL × 3 MiB and host disk); no hard aggregate DoS protection; no
   telemetry. Acceptable only if the owner explicitly accepts this exposure.

### Option B — Enable the existing proposed limits

1. **Accounting scope:** `max_items_per_batch = 10` → **per batch** (user + conversation + batch);
   `max_total_bytes = 64 MiB` → **global** across the staging root. (If the owner prefers a per-batch byte
   cap, use `max_bytes_per_batch = 64 MiB` instead; the named constant `MAX_STAGING_TOTAL_BYTES` is global.)
2. **Applies to:** **actual regular files on disk** (count and bytes); the byte cap is enforced **during**
   the streaming write. Reserved and staged bytes are the same thing (no separate reservation).
3. **Reserve/release:** implicit; capacity is consumed as bytes land on disk under `_accept_lock`; released
   by unlink (reject/expiry/reap). Atomic for the supported single-process model.
4. **On exhaustion:** `REJECTED_QUOTA` before write (count or global full) or mid-write abort (byte cap) ⇒
   user sees `ATTACHMENT_QUOTA_TEXT`; no `stored`.
5. **Rejection artifacts:** none — partial file unlinked; the `pending` metadata row remains (no file) and is
   reaped at expiry. The download already happened (≤3 MiB in memory) before the check, so a rejected file
   still consumes transient bandwidth/memory.
6. **Restart/expiry:** unchanged; no ledger to reconcile; reaper frees capacity; idempotent.
7. **Schema/config changes:** **no schema change**. Wiring only: pass explicit limits at
   `bot/handlers.py:1966` (`StagingStore(db, config.db_path, max_items_per_batch=10,
   max_total_bytes=64*1024*1024)`), ideally from an explicit owner-approved constant or a new config field.
   Do **not** add implicit env defaults (Plan 01 Option A principle).
8. **Tests required:** existing quota + concurrency tests already cover enforcement and serialization; add
   (a) a production-wiring assertion that the production store has the limits, (b) the 11th-file rejection
   end-to-end via `accept`, (c) the global cap across two batches (use small limits in the test), (d) no
   partial file on byte-cap rejection, (e) capacity released after reaping.
9. **Trade-offs / remaining risks:** rejects legitimate large batches (>10 files or >64 MiB staged); the
   global cap can be consumed by preserved orphan files; requires `D-12` resolution; single-user so no
   per-user isolation concern.

### Option C — Select different measured limits

1. **Accounting scope:** same mechanics as B; scope chosen by the owner (global or per-batch; per-conversation
   would need a new query, still no ledger).
2. **Applies to:** same as B (actual files/bytes).
3. **Reserve/release:** same as B.
4. **On exhaustion:** same as B.
5. **Rejection artifacts:** same as B.
6. **Restart/expiry:** same as B.
7. **Schema/config changes:** same as B (wiring only), with different values.
8. **Tests required:** same as B, parameterized to the chosen values.
9. **Trade-offs / remaining risks:** better fit to the host, but **requires measurement first**. There is
   no production telemetry today (and no production calls are allowed in this task), so any specific number
   would be arbitrary. A measurement task (peak staging bytes, files/batch, burst size) must precede a value
   choice. Examples of *provisional* ranges (NOT evidence-based): global 32 MiB (≈10 files) for a very small
   host, or 128 MiB for headroom.

---

## 9. Recommendation (separate from the owner's decision)

**RECOMMENDATION — NOT OWNER-APPROVED: Option B** (enable `max_items_per_batch=10` and
`max_total_bytes=64 MiB` global), because:

- It is the **smallest safe change** that converts the only unmitigated exposure (total staged bytes within
  the 15-min window) into a **hard bound**.
- The mechanism is **already implemented and tested**; no schema change, no ledger, no new owner/worker.
- It is **reversible** (pass `None` again).
- The UX cost is bounded (only unusually large bursts are rejected) and the rejection is honest
  (`ATTACHMENT_QUOTA_TEXT`, no artifact).

**Option A remains defensible** if the owner explicitly accepts the disk-exhaustion exposure on a trusted
single-user host. **Option C** should be chosen only after a measurement task.

This recommendation is **not** an owner approval and does not authorize implementation.

---

## 10. Exact implementation scope and acceptance criteria (if later authorized)

| Option | Scope | Acceptance criteria |
|---|---|---|
| **A** | Documentation only: record the accepted exposure and monitoring limitation (decision register / runbook). | No behavior change; docs updated; full suite green; no code/test/schema change. |
| **B** | One wiring change at `bot/handlers.py:1966` to pass explicit limits (constant or config field). No schema change, no ledger, no lifecycle change. | Production store reports `max_items_per_batch == 10` and `max_total_bytes == 64 MiB`; 11th file in a batch rejected; >64 MiB global rejected; no partial file on rejection; exactly-N stored under N concurrent accepts; capacity freed after reap; existing suite green. |
| **C** | Measurement task first, then the same wiring with measured values. | Values justified by measured data; same enforcement ACs as B. |

**Mandatory invariants for any option (Phase 4):** keep 3 MiB per-file cap; keep 15-min TTL; keep D-15
Option A (expiry reclaims staging only, not C2); do not change C2 or batch lifecycle semantics; do not add
a second SQLite owner/worker/scheduler; do not implement exactly-once Telegram semantics; do not touch
DEF-011-B/C, F-02, F-03.

---

## 11. Tests required if implementation is later authorized

1. **Production wiring:** assert the production `StagingStore` (from `_attachment_service`) has the chosen
   limits enabled.
2. **Item quota:** the 11th file in one batch is `REJECTED_QUOTA`; exactly 10 files exist.
3. **Global byte quota:** a second batch is rejected when the global cap is reached (use small values in the
   test to avoid writing 64 MiB).
4. **No partial artifact:** a byte-cap rejection leaves no file (`test_over_cap_write_leaves_no_partial_file`
   pattern).
5. **Concurrency:** N concurrent `accept` calls with a small cap ⇒ exactly cap stored, rest rejected
   (`test_T14` / `test_concurrent_admission_against_real_sqlite` pattern).
6. **Release on reap:** after the reaper removes files, a new accept succeeds again.
7. **No ledger introduced:** keep `test_T11b_no_reservation_ledger_introduced` green.
8. **Schema unchanged:** keep `test_T12_schema_table_count_unchanged` (17 tables) green.
9. **Orphan behavior (documented):** an untracked file consumes the global cap and is preserved
   (`test_case12_orphan_filesystem_file_preserved`); assert the documented behavior, do not "fix" it here.

---

## 12. Remaining uncertainties and limitations

1. **No production telemetry** on peak staging bytes, files per batch, or burst size ⇒ Option C cannot be
   evidence-based without a measurement task. No production calls were made.
2. **Orphan files** (no DB row) are preserved by design and count against a **global** cap ⇒ a global 64 MiB
   cap can be permanently reduced by such a file. Row-first makes this rare; manual cleanup or an
   owner-approved orphan policy would be a separate decision.
3. **Sweep latency:** TTL is logical; physical deletion happens at startup or on a throttled watcher tick
   (≥60 s). If the watcher is down, expired files linger until the next startup. Option A's exposure is
   therefore slightly larger than "15 minutes".
4. **Single-process assumption:** the `_accept_lock` serializes within one process. Running two bot processes
   against the same DB/staging root is not a supported deployment and would bypass the in-process lock (SQLite
   `BEGIN IMMEDIATE` would still serialize DB writes, but the FS scan+write is not cross-process atomic).
   This is an assumption, not a demonstrated risk.
5. **Download-before-check:** quota rejection happens **after** the ≤3 MiB download (the download is the
   input). A rejected file consumes transient bandwidth/memory. Not a safety gap; a possible future
   optimization (advisory pre-check) but not required.
6. **Historical docs are stale:** PLAN-08 line references do not match the live tree (§1.3). This brief uses
   live line numbers.

---

## 13. Final report (AGENTS.md format)

- **Status:** **DONE** — diagnosis complete, decision required. **No implementation.**
- **Acceptance criteria:**
  1. Live implementation/config inspected, not inferred — **MET** (§2, §3; live line numbers).
  2. Full lifecycle and actual concurrency traced — **MET** (§4, §5).
  3. Demonstrated vs hypothetical risks distinguished — **MET** (§5.1, §6: production intake is sequential;
     concurrency is tested but not reachable in production).
  4. Three options presented without assuming approval — **MET** (§8).
  5. Need for a reservation ledger evaluated, not presumed — **MET** (§7: not necessary).
  6. Existing architecture and D-15 unchanged — **MET** (read-only; no change).
  7. No implementation files or tests modified — **MET** (only this report was written).
  8. Detail sufficient to proceed after the policy choice — **MET** (§10, §11).
- **Changes:** added `docs/audits/OHB2-WP07-DEF011-A-DIAGNOSIS-AND-DECISION-BRIEF.md` (this report). Nothing
  else.
- **Verification:** read-only inspection of `bot/attachments.py`, `bot/handlers.py`, `bot/db.py`,
  `bot/config.py`, `bot/app.py`, `bot/polling.py`, `.env.example`, the PLAN-08/PLAN-18 docs, the decision
  register, `.agent/PROGRESS.md`, and the attachment/quota/race/crash tests. No test run was needed because
  no code changed; the cited tests are the existing evidence.
- **Not verified / not implemented:** `DEF-011-A`, `DEF-011-C`, `D6` remain unimplemented (out of scope);
  no production telemetry; no 3.11 run (not relevant to a read-only diagnosis).
- **Assumptions:** single-process deployment (supported model); production intake is sequential (proven by
  `polling.py:175` and `app.py:75-85`); D-12 is unresolved (per `.agent/PROGRESS.md:4199`), so neither the
  disabled nor the enabled state is owner-approved.
- **Branch and commits:** `openhands-workspace-11yyMvqKPjTrIZt1RRpWq9` at `30dfa0d`; **no commit**.
- **Suggested next step:** owner selects A, B, or C (or requests a measurement task for C); then one
  implementation task per §10.

---

## 14. Explicit status

# `A_DIAGNOSIS_COMPLETE_DECISION_REQUIRED`

`DEF-011` as a whole remains **OPEN**. `DEF-011-B` is implemented; `DEF-011-A` and `DEF-011-C` are not;
`D6` remains deferred. This brief does **not** authorize or implement any quota change.
