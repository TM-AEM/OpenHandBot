# OHB2-P0-A4 — Cleanup, Expiration, Recovery & Observability — Implementation Report

> Prepared by an AI agent (OpenHands) on behalf of the owner. **Verdict: `IMPLEMENTED_PASS_WITH_NOTES`.**
> This report is the implementation evidence for a **separate, later, read-only adversarial review**;
> it is **not** an independent review of itself.

- **Task ID:** OHB2-P0-A4-ENTRY-GATE-AND-IMPLEMENTATION
- **Date (UTC):** 2026-11-14
- **Authorization:** `D-09-R2` (narrow local-only A0–A4 exception). A4 is the final authorized P0 stage.
- **Scope:** expiration enforcement, safe cleanup/reaping, recovery, filesystem/database consistency,
  and structured observability — **local only**, no remote call, no new worker/scheduler/process/DB owner.

---

## 1. Entry gate evidence

| # | Prerequisite | Path | Expected SHA-256 | Observed | Result |
|---|---|---|---|---|---|
| 1.1 | A3/F1 independent review | `docs/reviews/OHB2-P0-A3-F1-CONSOLIDATED-IMPLEMENTATION-INDEPENDENT-REVIEW.md` | `aeeee69d0de907165344ac29c84d348bdea1cb8b80ea286161942e0c07408e14` | identical | **PASS** |
| 1.2 | Owner decisions register | `docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md` | `1eca72c1c3a6e9962719b59d7ba0d7eff02d5b76e6464f7d052d0d9ea967471c` | identical | **PASS** |
| 1.3 | Staged P0 plan | `docs/proposals/OHB2-P0-STAGED-IMPLEMENTATION-PLAN.md` | `06be7ea850c0f605ab6c23a161b19da0733143adaba852ddae6650f0836de868` | identical | **PASS** |
| — | Repository instructions | `AGENTS.md` | (n/a) | `d6ceda4e890681aa8c50f8fb8052de810ab8320d0ee7e0b20a6476d7f6565bc4` | present |

- **1.1 verdict checks:** the review's verdict is **`PASS_WITH_NOTES`**; it reports **no BLOCKER, HIGH, or
  MEDIUM** findings (only LOW/INFO F-1…F-4); and it explicitly authorizes proceeding
  (`SAFE TO PROCEED to the A4 entry gate`). The `/tmp` copy of this report was **absent** at session
  start; it was **recreated from the verified durable report** (byte-identical, same SHA-256). The gate
  did **not** fail for that reason.
- **1.2 decisions read and treated as binding:** D-09-R2 (A0–A4 local-only), D-25 (10-min route vs
  15-min batch; keep separate), D-26 (route validity re-checked at dispatch), D-32 (blocking vs
  non-blocking batch statuses), D-33 (message↔batch identity), D-34 (`TERMINAL_UNPROVEN` fail-closed),
  D-35 (identity evidence independent of `processed_updates`).
- **1.3 plan path/hash matched exactly**; no discrepancy; the applicable A4 section (§ "Stage A4 —
  Cleanup, expiry sweep, and observability") was read and followed.

**Entry-gate verdict: PASS.** Proceeded directly to implementation.

---

## 2. Baseline (pre-change) state

| Item | Value |
|---|---|
| Branch | `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW` |
| HEAD | `907b20de3fa6627795c14f29677e9f39c68e82f4` |
| origin/main | `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c` |
| upstream | none for the branch |
| `git status --short` | **61 entries** = 47 untracked + 14 modified |
| staged | 0 · stash: 0 |

- Pre-existing modifications (not mine): `bot/app.py`, `bot/db.py`, `bot/handlers.py`,
  `bot/update_outcomes.py`, `bot/web/*`, `docs/proposals/*`, several `tests/*`, `.agent/PROGRESS.md`,
  `.gitignore` — the A0–A3 (and unrelated Mini-App) work-in-progress. Untracked: `bot/attachments.py`,
  `bot/attachment_text.py`, all A0–A3 test files, and ~30 `docs/reviews/*` files.
- **Existing lifecycle hook identified for reuse:** `_post_init` in `bot/app.py` (the startup recovery
  hook that already calls `deletion.reconcile_pending_deletions`). A4's sweep is invoked from **that
  hook** — no new worker/scheduler/process/DB owner.
- **Baseline test counts (observed):** A0–A3 attachment lifecycle files = **264 passed**; full suite
  collection = **2840 tests**.

---

## 3. Files changed and why

| File | Change | Reason |
|---|---|---|
| `bot/db.py` | +`ATTACHMENT_ITEM_REAPED = "reaped"`; +6 read/CAS methods: `list_expired_pending_attachment_batches`, `list_attachment_batches_by_status`, `list_all_attachment_batches`, `list_attachment_items_by_status`, `list_all_attachment_items`, `mark_attachment_item_reaped`, `count_attachment_batches`, `count_attachment_items` | A4 needs owner-scoped/fail-closed **read** primitives and one **CAS** transition (`pending`/`stored` ⇒ `reaped`) as the durable decision that must precede filesystem deletion. A **new item status** (not a new batch status) is used so the approved batch-status set (D-32/D-34) is untouched. |
| `bot/attachments.py` | +`AttachmentReaper` (+ `SweepOutcome`, `BatchSweepResult`, `SweepReport`); module docstring updated to A4 | A4 sweep logic lives next to the staging store it governs, reusing `StagingStore`, `_is_within`, `is_safe_workspace_path`, `_parse_t0`. |
| `bot/app.py` | +step 1.3 in `_post_init`: construct `AttachmentReaper(db, config.db_path).sweep(now=…)` (best-effort, local, idempotent) | The plan requires invocation from an **already-existing lifecycle hook**; no new worker/scheduler. |
| `tests/test_attachment_cleanup_expiration_a4.py` (new) | 35 focused/adversarial tests | Required A4 regression + adversarial coverage. |

No other file was touched. Pre-existing user/agent work was preserved untouched.

---

## 4. A4 design and lifecycle behavior

`AttachmentReaper.sweep(now)` runs one full, **synchronous**, **non-throwing** pass:

1. **(0a) Known-token set** — collect every `attachment_items.staging_token` (any status) so an orphan
   item's file is not misclassified as an unreferenced file.
2. **(0b) Unknown batch status** — any `attachment_batches.status` outside `ATTACHMENT_BATCH_STATUSES`
   is reported (`errors`) and left untouched (fail-closed; no guessing).
3. **(0c) Unresolved batches** — `intent_recorded`/`dispatching`/`uncertain` (D-32) are counted
   `skipped` and left **deliberately untouched**.
4. **(1) Expiry** — every `pending` batch past its fixed `T0 + 15 min` deadline is transitioned to
   `expired` (durable, DB-first).
5. **(2) Terminal cleanup** — for batches now `delivered`/`expired`/`rejected`/`failed` (with a valid
   `t0`), each item is transitioned `pending`/`stored` ⇒ `reaped` (CAS) **before** its staged bytes are
   removed. Items already `reaped` are retried (a prior FS failure leaves them reaped).
6. **(3) Orphan items** — items whose parent batch row is missing are reaped.
7. **(4) Untracked files** — staged bytes with no matching item token are **reported, not deleted**.
8. **(5) Unsafe entries** — symlinks / non-regular files in the root are **reported, not followed or
   deleted**.
9. **Structured log line** — event names and counts only.

A `SweepReport` (`scanned/cleaned/partial/retry/skipped/errors/files_deleted/orphans_left/
unsafe_left/untracked_left`) is returned for observability and tests.

---

## 5. Database/filesystem ordering and failure semantics

- **DB-first ordering (mandatory):** the durable transition (`mark_attachment_item_reaped`, CAS) is
  committed **before** `os.unlink`. Mutation-proven: reordering delete-before-mark fails
  `test_db_transition_precedes_filesystem_deletion`.
- **Filesystem failure after the transition remains visible and retryable:** if `os.unlink` fails, the
  item is already `reaped`; the file remains; the report counts `retry` (never `cleaned`). A later sweep
  re-attempts removal (the `reaped` branch). No false success.
- **Partial multi-item cleanup** returns `PARTIAL`; already-removed files are not treated as proof of
  overall success (per-item accounting), and a subsequent sweep finishes the remainder.
- **Idempotency:** a missing file ⇒ `absent` (success); a missing root ⇒ `absent`; re-running the sweep
  deletes nothing further and reports `files_deleted=0`.

---

## 6. Expiration and recovery behavior

- **Fixed `T0`:** the deadline is computed from the persisted original `t0` only
  (`batch_deadline`/`_attachment_batch_deadline`). Retries, re-sweeps, restarts, partial processing, or
  re-encounters **never** extend or refresh it. Mutation-proven: disabling expiry yields 7 failures.
- **Boundary determinism:** `now >= T0 + 15 min` ⇒ expired (exact boundary is expired); `now < deadline`
  ⇒ live. Tested just-before, exactly-at, just-after.
- **Malformed/missing `t0`:** treated as expired (fail-closed) **but left for investigation** — the
  bytes are not deleted (an untrusted timestamp must not drive destructive cleanup).
- **D-26 preservation:** A4 expiration only concerns the **batch** 15-minute TTL. It does **not** apply
  or re-interpret the 10-minute route window; route/owner/conversation revalidation at dispatch is
  unchanged (A3). An expired batch is **never revived** and never attached to a replacement
  conversation (no A4 code touches routing or creation).
- **Recovery cases (all covered by tests):** directory-missing/records-present; batch-present/items-
  missing; item-present/file-missing; unreferenced file; interrupted creation; crash-after-transition/
  before-cleanup; partial multi-item deletion; expired partial batch; unknown status; owner/conversation
  mismatch (live batch of another owner untouched); symlink/path-traversal; conflicting/malformed
  metadata.

---

## 7. Identity-evidence preservation and D-33/D-34/D-35 compliance

- **No deletion of identity evidence:** A4 never executes any `DELETE`/`UPDATE` against
  `attachment_message_identity` (source-scan test asserts no such SQL and no `ON DELETE CASCADE`). The
  reaper only updates `attachment_items.status` and `attachment_batches.status`.
- **Independence from `processed_updates`:** the reaper does not touch `processed_updates` or its
  pruning; identity evidence is separate and retained (D-35).
- **`ON DELETE RESTRICT` preserved:** FK enforcement is unchanged; deleting a batch that has identity
  evidence still raises `IntegrityError` (tested). No cascade was added.
- **No new retention/pruning policy** for identity evidence was introduced.
- **`TERMINAL_UNPROVEN` fail-closed preserved:** the reaper does not alter classification; a terminal
  batch with no matching identity still classifies `TERMINAL_UNPROVEN` (tested). No text-equality,
  timestamp, latest-batch, or inferred-context logic was added.
- **Owner/route/conversation revalidation preserved** (A3 code paths untouched); the documented **N-2**
  owner-scoped query limitation is **not widened** by A4.
- **Survival tests:** identity rows survive `delivered`/`expired` transitions and full reaping
  (`count_message_identities()` unchanged; `message_identity_batch_id()` still resolves).

---

## 8. Required recovery cases — resulting behavior

| # | Case | Safe action | Test |
|---|---|---|---|
| 1 | Batch directory missing, records remain | reap items (file `absent` ⇒ success) | `test_batch_dir_missing_while_records_remain` |
| 2 | Batch present, item rows missing | leave untouched (`NOTHING`) | `test_batch_present_while_item_rows_missing` |
| 3 | Item row present, file missing | mark reaped (reconciled ⇒ `cleaned`) | `test_db_item_present_while_file_missing` |
| 4 | Unreferenced file in staging | **report, do not delete** | `test_unreferenced_file_is_left_and_reported` |
| 5 | Interrupted batch creation | reap on expiry | `test_interrupted_creation_pending_item_no_file` |
| 6 | Crash after transition, before cleanup | reaped item retried next sweep | `test_crash_after_transition_before_cleanup_recovered` |
| 7 | Partial deletion of multi-item batch | `PARTIAL` + retry | `test_partial_multi_item_cleanup_then_retry` |
| 8 | Expired partial batch | reap both items | `test_expired_partial_batch_is_reaped` |
| 9 | Unknown/unsupported status | report + leave | `test_unknown_batch_status_is_left_and_reported`, `test_unknown_item_status_is_left` |
| 10 | Owner/conversation mismatch | live batch untouched | `test_live_pending_batch_of_other_owner_untouched` |
| 11 | Symlink / path traversal | refuse + leave + report | `test_symlink_entry_is_not_followed_or_deleted`, `test_symlink_inside_root_is_left_not_removed`, `test_path_traversal_token_is_rejected`, `test_absolute_token_is_rejected` |
| 12 | Conflicting/malformed metadata | report + leave | `test_malformed_t0_is_treated_as_expired_and_left_for_investigation`, `test_missing_t0_is_treated_as_expired` |

No unresolved case is silently classified as successfully recovered.

---

## 9. Tests added or changed

- **Added:** `tests/test_attachment_cleanup_expiration_a4.py` — **35 tests** (expiry semantics &
  boundaries; retry does not extend TTL; malformed/missing `t0`; DB-before-FS ordering; FS-failure
  retryable/visible; partial + retry; idempotency; missing dir/items/files; unreferenced files;
  interrupted creation/cleanup; expired partial; unknown states; owner isolation; symlink/traversal;
  orphan items; D-35 identity survival + no cascade; architecture checks (no worker/asyncio, sweep
  invoked from `_post_init`, single DB connection); a real `_post_init` integration test; A3/F1
  `TERMINAL_UNPROVEN` regression).
- **Changed:** none. No existing test was modified, weakened, skipped, or deleted.

---

## 10. Exact commands and observed results

All run in the repo with the project `.venv`.

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest tests/test_attachment_cleanup_expiration_a4.py -q` | **35 passed** |
| `.venv/bin/python -m pytest <A0–A4 attachment files> -q` | **299 passed** |
| `.venv/bin/python -m pytest tests/test_attachment_message_identity_a3.py tests/test_attachment_terminal_routing_remediation.py -q` | **65 passed** |
| `.venv/bin/python -m pytest -q` (full) | **2875 passed, 0 failed, 0 skipped, 0 xfailed**, 72 warnings (~137 s) |
| `node --test tests/frontend/*.test.js` | **219 pass, 0 fail** |
| `.venv/bin/python -m pyflakes bot/ automation/ tools/ main.py tests/` | exit 0 (clean) |
| `.venv/bin/python -m bandit -r bot/ automation/ main.py -lll -s B613` | **High: 0** (Low 5, Medium 17 — pre-existing) |
| `.venv/bin/python -m pip_audit -r requirements-dev.txt` | No known vulnerabilities found |

**Comparison with baseline:** full-suite collection 2840 → 2875 (+35 new, all passing); the pre-existing
attachment lifecycle set 264 → 297 (+33; the other 2 new tests are the integration/architecture checks).
No previously passing test regressed.

**Mutation checks (reviewer-style, then restored byte-identically):**
- Disable expiry in `list_expired_pending_attachment_batches` ⇒ **7 A4 tests fail**.
- Reorder to delete-before-mark in `_sweep_batch` ⇒ `test_db_transition_precedes_filesystem_deletion`
  fails.
- Remove the symlink/non-regular-file guard in `_remove_file` ⇒ `test_symlink_inside_root_is_left_not_removed`
  fails.
Source files were restored byte-identical (`cmp` clean; pyflakes clean).

---

## 11. Test limitations / environmental constraints

- Tests are local-only: temporary SQLite + temporary staging dirs, injected `now`, no network, no
  production calls. One test toggles `PRAGMA foreign_keys=OFF` briefly to construct an orphan item
  (itself FK-impossible), then restores `ON`; this is test-only and does not alter production behavior.
- `pip_audit` may require network for the advisory DB; it reported no known vulnerabilities in this run.
- No coverage tooling was run (not part of §5/§7 of AGENTS.md).

---

## 12. Remaining findings, risks, and deferred work

- **Carried-forward LOW/INFO notes (from the A3/F1 review) are intentionally NOT fixed** (out of A4
  scope, cosmetic): `bot/db.py` `AttachmentRoutingState.TERMINAL` dead enum (F-3), and two stale
  docstrings referencing the superseded D-32 "terminal does not block" behavior (F-1/F-2), plus one
  stale test comment (F-4). They are preserved and shift only by line number.
- **Risk (low, bounded):** the sweep is invoked at startup only. Between startups, terminal batch bytes
  can persist up to the next restart. This matches the plan's "existing lifecycle hook" constraint and
  the "no new worker/scheduler" rule; it is a deliberate trade-off, not a defect.
- **Deferred (out of scope, blocked):** remote/materialized copy retention (D-07/D-08) remains
  `BLOCKED — OWNER DECISION REQUIRED`; B1–B3/Group C/Plan 02/release are not started.
- **Not claimed:** no exactly-once delivery/processing; no new backup feature.

---

## 13. Final `git status` (preservation)

- Working tree: **63 entries** = 49 untracked + 14 modified (baseline was 61 = 47 + 14). The two added
  entries are the new A4 test file `tests/test_attachment_cleanup_expiration_a4.py` and this report's
  durable copy `docs/reviews/OHB2-P0-A4-CLEANUP-EXPIRATION-RECOVERY-REPORT.md`.
- All pre-existing modified/untracked files are **preserved unchanged**; `.agent/PROGRESS.md`,
  `.openhands/memory/*`, the owner-decision register, and the staged plan were **not** modified
  (register/plan/AGENTS/review hashes unchanged).
- staged: 0 · stash: 0 · HEAD unchanged (`907b20de…`) · no new commit.
- **No `git reset`, `git clean`, force op, broad restore/revert, or deletion** was performed; **no
  `git add .`/`-A`** was used; no unrelated work was overwritten.

---

## 14. Authorization confirmation

**No commit, push, PR, merge, deployment, release, or Autopush activation occurred.** No external
production call, no user session, no remote operation of any kind. A4 was implemented strictly within
the local-only `D-09-R2` exception and the A4 section of the staged plan. B1–B3, Group B, Group C,
Plan 02, release, deployment, and production testing were **not** started.

---

## 15. Verdict

**`IMPLEMENTED_PASS_WITH_NOTES`.**

A4 scope is complete (expiration, safe cleanup/reaping, recovery, filesystem/database consistency,
structured observability), all required validations pass, and no BLOCKER/HIGH/MEDIUM finding remains.
The only notes are the intentionally-preserved LOW/INFO A3/F1 documentation items (§12) and the
bounded startup-only sweep cadence. Implementation is the evidence for a **separate** read-only
adversarial review — this report is **not** a self-declared independent review.
