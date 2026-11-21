# OHB2 — WP-07 / DEF-011 Audit Batch Report

**Task ID:** `OHB2-WP07-DEF011-REMEDIATION-AUDIT-AND-IMPLEMENTATION-PLAN`
**Date:** 2026-11-19
**Mode:** audit + planning only. **No production code, test, schema, or Git state modified.**
**Recorded by:** AI agent (OpenHands) on behalf of the repository owner.

---

## FINAL VERDICT

# `DEF011_PLAN_READY_WITH_NOTES`

The plan is concrete, evidence-based, and executable — **with three notes that materially narrow
the task's premise**:

1. **DEF-011 has three sub-defects, not two.** The task described "no `to_thread`" + "no quota
   ledger". The authoritative finding also includes a **misleading UX copy** defect
   (`ATTACHMENT_ACCEPTED_TEXT`) that belongs to **WP-01**, not WP-07.
2. **The quota reservation ledger is unreachable today.** Dispatch is strictly sequential, so the
   4-stream race cannot occur. It becomes live only under **OD-04 Option B**.
3. **Only the async disk-I/O offload (sub-defect B) is both safe and unblocked** — and it needs
   exactly one approval: owner authorization to edit four files.

---

## 1. Exact DEF-011 requirement

Source: `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md:230-244` and
`docs/audits/OHB2-COMPLETE-DEFECT-REGISTER.md:320-340`.

| Sub-defect | Requirement | Owner |
|---|---|---|
| **A** | Reserve in-flight byte budgets across the 4 concurrent download streams so aggregate quotas cannot be overshot (TOCTOU) | WP-07 |
| **B** | Move blocking filesystem I/O off the asyncio event loop: `StagingStore._write_to_path` (`os.fsync`) and `AttachmentReaper.sweep` | WP-07 |
| **C** | Make `ATTACHMENT_ACCEPTED_TEXT` truthful — files are staged **locally only**, not delivered to OpenHands | **WP-01** |

**Severity:** `MEDIUM` · **Validation:** `CONFIRMED` · **Owner approval:** `NONE` unless altering
D-12 aggregate defaults.

---

## 2. Verified implementation status [FACT]

| Sub-defect | Status | Evidence |
|---|---|---|
| **A** — reservation ledger | **NOT IMPLEMENTED** | Zero `reserv` matches in `bot/`; `quota_block`/`byte_quota_block` read disk only |
| **B** — async disk I/O | **NOT IMPLEMENTED** | Zero `to_thread`/`run_in_executor` in `bot/attachments.py`; `store()` called synchronously at `attachments.py:956` from `async def accept` |
| **C** — UX copy | **NOT IMPLEMENTED** | `ATTACHMENT_ACCEPTED_TEXT` at `handlers.py:1876-1878` still omits local-only disclosure |

**No partial implementation exists** under any other helper. `bot/web/download.py` uses
`run_in_threadpool`, but that is a **separate, already-shipped Mini App feature** — a *precedent*,
not a partial fix.

**Target files unmodified:** `bot/attachments.py` (`7e448b52ac3b5f47`), `bot/polling.py`
(`9b9c8d7e53ec467b`), `bot/app.py` (`f28562f3551d59b8`) — all match HEAD.

---

## 3. Affected code paths [FACT]

```
handlers.handle_attachment (async)
  └─ await _download_attachment_chunks()      # async, network — OK
       └─ async with _get_download_semaphore(): # max 4 streams
            return iter([bytes(buf)])          # chunks fully materialized in RAM
  └─ await service.accept()                    # async
       └─ self._store.store(...)               # ← SYNC call, no await
            ├─ (0d/0f/0g) DB + disk-stat quota checks
            ├─ (2) _write_to_path  → os.open/write/flush/fsync   ← BLOCKS LOOP
            ├─ (3) _read_head      → open/read                   ← BLOCKS LOOP
            └─ (4) try_mark_attachment_item_stored (DB)

watcher.tick (async)
  └─ self._opportunistic_sweeper.maybe_sweep()   # SYNC
       └─ self._reaper.sweep()  → lstat/unlink/iterdir  ← BLOCKS LOOP

app._post_init (async)
  └─ reaper.sweep(now=...)   ← BLOCKS LOOP at boot
```

**Bounded by `MAX_ATTACHMENT_BYTES = 3 MiB`** per file — the stall is real but capped.

---

## 4. Is quota accounting actually required?

**Not now.** [FACT]

| Question | Answer |
|---|---|
| Do quota limits exist? | Yes — as constructor parameters |
| Enabled by default? | **No — all `None`** (`attachments.py:496-499`) |
| Production construction | `StagingStore(db, config.db_path)` — **no quota args** (`handlers.py:1964`) |
| Existing reservation ledger? | **None** |
| Durable ledger required by baseline? | **No — "in-process async reservation ledger"** (`:687`) |
| Schema change needed? | **No** — 17 tables preserved |
| Is the race reachable? | **No** — `process_updates` dispatches sequentially (`polling.py:164-165`) |

⇒ **Sub-defect A is dormant.** Implementing an always-on ledger would implicitly change **D-12**
defaults without approval.

---

## 5. Recommended remediation

# **Option 1** — offload only the pure-I/O regions with `anyio.to_thread.run_sync`

| Aspect | Detail |
|---|---|
| Files | `bot/attachments.py`, `bot/handlers.py`, `bot/watcher.py`, `bot/app.py` |
| Approach | Split each blocking function: file ops → sync inner function run in a thread; **all SQLite stays on the loop thread** |
| SQLite safety | Preserved — `check_same_thread=False` on one shared `_conn` with **no lock** means DB work must never cross threads |
| Cancellation | `_safe_unlink` stays inside the thread function; `abandon_on_cancel=False` (verified default) |
| New dependencies | **None** — `anyio==4.16.0`, `starlette==1.3.1` already pinned |
| Schema | **None** |
| Complexity | **MODERATE** — ~4 files, ~120-180 lines |
| Approvals needed | **Owner authorization to edit the 4 files only** |

**Rejected alternatives:**

| Option | Verdict |
|---|---|
| 2 — wrap `service.accept()` in `to_thread` | **REJECTED** — would run SQLite on a worker thread (forbidden by baseline `:336`, `:687`) |
| 3 — offload all of `store()` + add a global DB lock | **REJECTED** — breaks the single-owner model, worsens latency |
| 4 — build the ledger now | **DEFERRED** to OD-04 |
| 5 — accept the stall | **NOT RECOMMENDED** — inconsistent with the shipped `bot/web/download.py` pattern |

---

## 6. Schema and owner-decision dependencies

| Item | Required for Option 1? |
|---|---|
| Schema / migration | **NO** |
| **OD-04** | **NO** — only sub-defect A depends on it |
| **D-12** | **NO** — defaults stay `None`; respected, not changed |
| **OD-01 / OD-03** | **NO** — those block WP-01 (sub-defect C) |
| Owner authorization to edit 4 files | **YES — the only approval needed** |

---

## 7. Test gaps and proposed matrix

**Existing coverage** (`tests/test_repair_plan_01_resource_staging.py`): sequential quota
enforcement, stream caps, semaphore bound. `test_concurrent_downloads_are_bounded` asserts only that
**stream count** ≤ 4 — it does **not** verify quota correctness under concurrency.

**Four genuine gaps:**

| Gap | Proposed test |
|---|---|
| No event-loop responsiveness assertion | T-1, T-4 |
| No offload proof | T-2, T-3, T-8 |
| No thread-affinity assertion for SQLite | T-5, T-6 |
| No cancellation-mid-write test | T-7 |

Full matrix: **T-1 … T-14** (see implementation plan §4). Each test specifies the behaviour it must
prove. **No tests were written in this task.**

---

## 8. Files created

```
docs/audits/OHB2-WP07-DEF011-REMEDIATION-AUDIT.md
docs/audits/OHB2-WP07-DEF011-IMPLEMENTATION-PLAN.md
docs/reviews/OHB2-WP07-DEF011-AUDIT-BATCH-REPORT.md
```

---

## 9. Current Git state

| Field | Value |
|---|---|
| Branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` |
| HEAD | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` (unchanged) |
| `origin/main` | identical (`0 0`) |
| Staged | **0** |
| Tracked modifications | **6** (unchanged — all pre-existing WP-07) |
| Untracked | **29 → 32** (the three documents above) |
| Ignored | 8 |

**Modified files (unchanged, all pre-existing WP-07 work):**

```
 M .agent/PROGRESS.md
 M bot/db.py
 M bot/handlers.py
 M bot/watcher.py
 M tests/test_handlers.py
 M tests/test_sw06_unwatch_db_failure_propagation.py
```

---

## 10. Confirmation: implementation and tests were NOT modified

| Check | Result |
|---|---|
| Production code modified | **NO** |
| Test code modified | **NO** |
| Schema/migration modified | **NO** |
| Mini App modified | **NO** |
| WP-07 implementation modified | **NO** |
| WP-05 / WP-06 modified | **NO** |
| Dependencies installed/upgraded | **NO** |
| Database mutated | **NO** |
| Live Telegram / OpenHands calls | **NO** |
| Secrets accessed | **NO** |
| Staging / commit / push / PR / merge / release | **NO** |
| Autopush activated | **NO** |
| Destructive Git commands | **NO** |
| Broad staging or deletion | **NO** |
| `bot/attachments.py` hash changed | **NO** — `7e448b52ac3b5f47` before and after |

---

## 11. Notes and limitations (honest)

| # | Note |
|---|---|
| **N-1** | **The task's premise was incomplete.** DEF-011 includes a UX-copy sub-defect owned by WP-01. Implementing it here would be scope creep into a blocked work package. |
| **N-2** | **The reservation ledger cannot be justified today.** It is unreachable under sequential dispatch and gated by D-12. The plan defers it to OD-04 rather than inventing a decision. |
| **N-3** | **The 3 MiB stall was NOT measured.** Its existence is confirmed by source reading (`os.fsync` on the loop); its latency impact is not profiled. |
| **N-4** | **No independent review.** This is a same-agent audit. `INDEPENDENCE_NOT_ESTABLISHED` remains in force. No separate reviewer session, container, or provider connection was available. |
| **N-5** | **Historical figures not re-executed.** The baseline's "event-loop stalls" and "dormant overshoot" claims were corroborated by source inspection, not by runtime measurement. |
| **N-6** | **`store()` → `async` is the main regression risk.** A missed call site fails silently. The audit enumerated all four call sites; the plan requires per-phase green gates. |
| **N-7** | **Sub-defect C is genuinely user-impacting** (it is what makes DEF-001's bricking surprising), but it is **not** this task's to fix. |

---

## 12. Suggested next step

**One item:** obtain owner authorization to implement **Option 1 (sub-defect B only)** in
`bot/attachments.py`, `bot/handlers.py`, `bot/watcher.py`, and `bot/app.py`, following the ordered
phases P0–P5 and the T-1…T-14 test matrix.

Then, separately:

- **OD-04** decision → determines whether sub-defect A is ever needed.
- **WP-01** (OD-01 + OD-03) → owns sub-defect C.

---

## 13. Stop condition

**Stopped after producing the three documents.** No implementation, no tests, no commits.
Awaiting explicit owner authorization.
