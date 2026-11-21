# OHB2 — WP-07 Batch-03 External Review Checklist

**Companion to:** `OHB2-WP07-BATCH03-EXTERNAL-REVIEW-HANDOFF-REPORT.md`
**Package:** `/workspace/review-packages/OHB2-WP07-BATCH03-EXTERNAL-REVIEW-HANDOFF-20261119`
**Reviewer:** ____________________  **Date:** __________  **Environment:** ____________________

> Work through every box. Each `[ ]` needs evidence (command output, file:line, or test name).
> Do **not** copy the handoff report's numbers — re-derive them.
> Do **not** modify the snapshot.

---

## 0. Independence declaration (complete first)

- [ ] I am **not** the agent that produced this work.
- [ ] My execution environment is **separate** from the authoring host.
- [ ] I did not receive instructions from the authoring agent during this review.

If any box cannot be ticked, stop and record `INDEPENDENCE_NOT_ESTABLISHED`.

---

## 1. Package integrity

- [ ] `sha256sum -c MANIFEST.sha256` → all entries `OK`.
- [ ] `sha256sum -c PACKAGE.sha256` → `OK`.
- [ ] Archive extracts into a temp dir; no repo file is touched.
- [ ] `WORKTREE-VS-HEAD.diff` is a real `git diff HEAD --` (contains `diff --git` hunks).
- [ ] Manifest classes match reality: files labelled `untracked` are genuinely untracked at HEAD.
- [ ] No secrets: grep for tokens/keys/passwords → only env-var **names** appear.

## 2. Baseline state verification

- [ ] HEAD is `52e7789cc8cc97a7f7c09c9592226ab117db99a2`.
- [ ] `git status --porcelain` shows 8 modified + 34 untracked (or reconcile any difference).
- [ ] Table count in `bot/db.py` is **17**; the diff contains **no** `CREATE TABLE`/`ALTER TABLE`.
- [ ] The diff touches **no** Mini App path (`bot/web/*`, `tests/frontend/*`, `docs/MINI_APP.md`).

## 3. DEF-011 sub-defect B — filesystem offload (core of this batch)

- [ ] **Off-loop execution proven by execution, not inspection.** Write/confirm a test that captures
      `threading.get_ident()` inside the worker and compares it to the event-loop thread.
- [ ] `StagingStore._store_write` runs in a worker thread via `anyio.to_thread.run_sync`
      (`bot/attachments.py:909`).
- [ ] `AttachmentReaper._sweep_fs_tail` runs in a worker thread (`bot/attachments.py:1199`).
- [ ] `_read_local_capped` runs in a worker thread (`bot/handlers.py:2086`).

### 3.1 Ownership boundary (highest-risk area)

- [ ] SQLite is touched **only** on the owning loop thread. Verify `_store_prepare` and
      `_store_finalize` are **not** passed to `to_thread`.
- [ ] The worker receives **no** `Database`/`sqlite3.Connection` object — only primitives
      (`path`, `chunks`, `cap`, `item_id`, `token`).
- [ ] `_sweep_fs_tail` contains **zero** DB calls (only `iterdir`/`lstat`).
- [ ] **No mixed DB+FS function was moved wholesale** to a worker thread.
- [ ] Confirm `sqlite3.connect(..., check_same_thread=False)` + a single shared `_conn` is **not**
      reachable from two threads concurrently.

### 3.2 Cancellation / partial files / error propagation

- [ ] Cancelling a `store_async` mid-write never yields a `stored` claim.
- [ ] The resulting state (`pending` row + orphan bytes) is reclaimed by the A4 sweep
      (`pending → reaped`, file deleted) — i.e. equals the pre-existing crash-between-write-and-mark
      state.
- [ ] `OSError` in the worker maps to `WRITE_FAILED` (fail-closed), not a silent success.
- [ ] No cancel-time blind `unlink` was introduced (would contradict
      `_scan_root_untracked`'s "report, never blind-delete" contract).

### 3.3 `anyio.Lock` admission serialization

- [ ] `_accept_lock` serializes the whole critical section (quota check → write → mark).
- [ ] Concurrent `accept()` cannot exceed the cap — re-run the 4-stream/concurrent-admission race test.
- [ ] The lock **restores** the previously accidental sequential behaviour; it does **not** add new
      concurrency.
- [ ] The architectural guard `test_cleanup_adds_no_worker_or_scheduler` still passes unmodified
      (it forbids the literal string `asyncio` in `bot/attachments.py`).

### 3.4 Non-introduction checks

- [ ] **No quota reservation ledger** was added (`grep -rn "reserv" bot/` → no ledger).
- [ ] **No schema change** (17 tables; diff has no DDL).
- [ ] **No new worker/scheduler/parallel polling.**
- [ ] **No new dependency** — `anyio`/`starlette` were already pinned in `requirements.txt`.
- [ ] Synchronous `store()`/`sweep()`/`maybe_sweep()` behaviour is unchanged (existing tests pass).

## 4. DEF-011 sub-defects A and C — confirm the disclosed gaps

- [ ] **A (ledger)** is indeed **absent**. Judge whether that is acceptable given `D-12` + `OD-04`,
      or whether it must be reopened. Record your position.
- [ ] **C (UX copy)** is still unmodified (`ATTACHMENT_ACCEPTED_TEXT`, `bot/handlers.py:1878`), and
      confirm it is **WP-01** scope blocked on `OD-01`/`OD-03` — **not** a WP-07 defect.
- [ ] `DEF-011` is therefore **NOT closed** — do not accept it as closed.

## 5. DEF-006 / OD-04

- [ ] `bot/app.py` `DEF-006` comment block is present **in HEAD** (committed).
- [ ] `TelegramPoller.process_updates` still awaits `dispatch_and_wait` per update ⇒ **sequential**.
- [ ] **OD-04 has no owner decision record.** Do not treat the comment as approval.
- [ ] Verdict for DEF-006: `BLOCKED_PENDING_OD04` unless you find a decision record.

## 6. DEF-013 / NEW-DEF-03 / NAV-01..06

- [ ] `clear_awaiting_and_record_outcome` / `set_awaiting_and_record_outcome` commit state + outcome
      in **one** `BEGIN IMMEDIATE` transaction.
- [ ] Telegram send/edit happens **outside** the transaction (no false distributed atomicity claimed).
- [ ] `renew_awaiting` runs **after** whitespace validation.
- [ ] Watch/unwatch atomicity present (`add_watched_and_record_outcome`, `remove_watched*`,
      `watcher.unwatch(update_id=, now=, outcome=)`).
- [ ] `NAV-01..06` reviewed **as `NEW-DEF-03` sub-scope**, not as independent register findings.
- [ ] `NAV-01..06` flagged **UNACCEPTED** (no acceptance record).

## 7. F-1 Option C

- [ ] Post-commit Telegram failure writes **only** `update_failures`; `processed_updates.outcome`
      stays `durable_completed`.
- [ ] `prune_processed_updates` deletes **only** from `processed_updates` ⇒ failure evidence survives.
- [ ] No new worker/queue/table, no redelivery driven by the notification failure, no exactly-once claim.

## 8. WP-05 separation

- [ ] WP-05 work is **already committed in HEAD** (markers in `bot/app.py`, `bot/db.py`,
      `bot/notifier.py`, `bot/openhands_client.py`, `bot/outbox.py`, `bot/watcher.py`).
- [ ] The working-tree `bot/db.py` diff is **WP-07 only** (no WP-05 hunk in the diff).
- [ ] `tests/test_handlers.py` and `tests/test_sw06_unwatch_db_failure_propagation.py` changes are
      the `**_kw` signature-compatibility updates required by NEW-DEF-03 — not unrelated rewrites.

## 9. Independent execution

- [ ] Focused WP-07 suites re-run; record the real count (author reported 121).
- [ ] Full suite re-run; record the real count (author reported 3406).
- [ ] `pyflakes` re-run → exit 0.
- [ ] `bandit -lll -s B613` re-run → High 0.
- [ ] `node --test tests/frontend/*.test.js` re-run (author reported 280/0).
- [ ] Python 3.11 attempt recorded; if impossible → **UNVERIFIED**.
- [ ] At least one **mutation** re-run to confirm the new tests are non-vacuous.

## 10. Verdict

| Dimension | Verdict | Evidence |
|---|---|---|
| Technical correctness | | |
| Scope compliance | | |
| Test reproducibility | | |
| Architecture compliance | | |
| Owner-acceptance readiness | | |
| Independent-review status | | |

**Overall:** `PASS` / `PASS_WITH_NOTES` / `FAIL` / `BLOCKED` — circle one, with justification.
