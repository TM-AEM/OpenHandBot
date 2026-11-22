# OHB2-WP01 Stage 1 — Implementation Report Addendum (N1/N2)

- **Date:** 2026-11-21
- **Task:** `OHB2-WP01-STAGE1-CANCELLATION-N1-N2-REMEDIATION-AND-REGRESSION-TESTS`
- **Original report:** `docs/reviews/OHB2-WP01-STAGE1-CANCELLATION-IMPLEMENTATION-REPORT.md`
- **Scope:** correction and remediation note; the historical report is not rewritten.

## Correction

The original report says the synchronous `store()` lock is acquired through **"asyncio's
executor"**. That phrase is inaccurate.

Actual implementation: `StagingStore.cancellation_guard` uses
`anyio.to_thread.run_sync(self._sync_lock.acquire)` before entering `_accept_lock`. The
synchronous lock is acquired on a worker thread so the event loop is not blocked; the
synchronous `store()` path itself holds `_sync_lock`.

This is a documentation correction only. It does not change the approved Stage 1 behavior.

## N1/N2 remediation note

The subsequent N1/N2 remediation and T1-T7 regression work is documented in:

`docs/reviews/OHB2-WP01-STAGE1-CANCELLATION-N1-N2-REMEDIATION-REPORT.md`

In summary:

- **N1:** `_store_prepare` now rejects every non-`pending` parent before item insertion or byte
  writes, not only `cancelled`.
- **N2:** `mark_attachment_item_reaped` now requires a parent in the approved terminal set
  (`delivered`/`expired`/`rejected`/`failed`), while preserving the separate orphan-item policy.

Stage 2 retention policy, automatic cleanup, Mini App behavior, and the approved architecture were
not changed.
