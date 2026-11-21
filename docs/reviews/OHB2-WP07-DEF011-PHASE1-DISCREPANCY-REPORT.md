# DEF-011 Implementation — Phase 1 Discrepancy Report (recorded before any code change)

**Date:** 2026-11-19
**Task:** `OHB2-WP07-DEF011-IMPLEMENTATION-AND-VERIFICATION`
**Trigger:** Phase 1 item 7 — "If the plan, source code, or current repository state materially differs from the audit, stop and report the discrepancy before making changes."

## Verified matches (no discrepancy)

| Check | Result |
|---|---|
| Branch / HEAD / origin/main | `openhands-workspace-…` / `52e7789` / `52e7789` — 0/0 |
| Staged | 0 |
| Modified tracked | exactly the 6 pre-existing WP-07 files |
| `bot/attachments.py` | `7e448b52ac3b5f47` — **matches audit** |
| `bot/polling.py` | `9b9c8d7e53ec467b` — **matches audit** |
| `bot/app.py` | `f28562f3551d59b8` — **matches audit** |
| Full suite baseline | **3385 passed** |
| Tables | 17 |

## MATERIAL DISCREPANCY

The approved implementation plan (Option 1) states:

> "`store()` becomes `async def` and `await`s it" … "`maybe_sweep` becomes `async def`" …
> "**Dependencies / approvals.** … the audit already enumerated them (`attachments.py:956`,
> `attachments.py:1523`, `app.py:241`, `watcher.py:183`)" — i.e. **4 call sites**.

**Reality measured in this task:**

| Symbol | Production call sites | **Existing-test call sites** | Total |
|---|---|---|---|
| `StagingStore.store(` | 1 (`attachments.py:956`) | **49** | 50 |
| `AttachmentReaper.sweep(` | 2 (`attachments.py:1523`, `app.py:241`) | **67** | 69 |
| `OpportunisticSweeper.maybe_sweep(` | 1 (`watcher.py:183`) | **38** | 39 |

All of those test call sites are in **synchronous** test functions (e.g.
`tests/test_attachment_staging_a1.py`: 29 sync `def test_`, 0 async;
`tests/test_attachment_cleanup_expiration_a4.py`: 44 sync, 0 async).

**Consequence:** converting `store()` / `sweep()` / `maybe_sweep()` to `async` would require
mechanically rewriting **~158 call sites across ~10 existing test files** — precisely what this task
forbids:

> "Do not modify unrelated tests merely to make the suite pass."

The plan's blast-radius estimate (4 sites) was wrong by ~40×.

## Resolution adopted (within authorized scope)

The *authorized scope* is unchanged and remains satisfiable:

1. Move blocking pure filesystem I/O off the event loop — **yes**
2. Keep SQLite in its owning context — **yes**
3. Add focused regression tests — **yes**

Implementation uses **additive async twins** instead of converting existing sync methods:

| Production async entry point | New async API | Sync API |
|---|---|---|
| `AttachmentService.accept()` (already async) | `StagingStore.store_async()` | `store()` **unchanged** |
| `Watcher.tick()` (already async) | `OpportunisticSweeper.maybe_sweep_async()` | `maybe_sweep()` **unchanged** |
| `app._post_init()` (already async) | `AttachmentReaper.sweep_async()` | `sweep()` **unchanged** |
| `_download_attachment_chunks` (already async) | offload `_read_local_capped` | — |

Logic is shared between sync and async variants via extracted pure helpers, so there is **one
source of truth** for each decision. Sync public APIs stay byte-identical ⇒ **zero test edits**.

This is a *justified deviation in mechanism only* (additive twins vs. in-place conversion); the
authorized behavioural scope is met in full.

## Effect on the four intended files

The plan named `bot/attachments.py`, `bot/handlers.py`, `bot/watcher.py`, `bot/app.py`.
The deviation keeps **exactly these four files** — no fifth file is touched.

---
