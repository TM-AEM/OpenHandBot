# OHB2-P0-A4-LOW-FINDINGS-REMEDIATION — Report

> Prepared by an AI agent (OpenHands) on behalf of the owner. Narrow A4 remediation of exactly two
> independent-review findings (F-1 functional, F-4 report accuracy). No commit/push/PR/merge/
> deployment/release/production call; Autopush not enabled. No owner-decision register, staged plan,
> `AGENTS.md`, `.agent/PROGRESS.md`, or `.openhands/memory/*` was modified.

- **Task ID:** OHB2-P0-A4-LOW-FINDINGS-REMEDIATION
- **Date (UTC):** 2026-11-11
- **Verdict:** **`REMEDIATED_PASS`**
- **Scope:** F-1 (orphan `reaped` item byte retention) and F-4 (two §10 row counts). F-2/F-3/F-5 are
  documented, unchanged, and deliberately **not** fixed.

---

## 1. Verdict

**`REMEDIATED_PASS`.**

- **F-1** is fixed with the smallest safe correction: `_sweep_orphan_items` now also considers
  `ATTACHMENT_ITEM_REAPED` orphan items and retries their deletion (idempotent). All safety
  predicates are preserved (batch-association guard, `_remove_file` confinement/path-safety, no
  inference from filenames, ambiguous records untouched). Proven by 9 new focused tests and by a
  reverted-fix mutation that fails 4 of them.
- **F-4** is corrected: the two §10 rows now read **299** (A0–A4 attachment set) and **65**
  (identity_a3 + terminal_routing), both verified from actual test output. Only those two rows changed.

No BLOCKER/HIGH/MEDIUM remains. No unrelated work was overwritten.

---

## 2. Baseline and final Git status

| Item | Baseline (before) | Final (after) |
|---|---|---|
| Branch | `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW` | same |
| HEAD | `907b20de3fa6627795c14f29677e9f39c68e82f4` | same |
| `origin/main` | `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c` | same |
| Working-tree entries | **64 = 50 untracked + 14 modified** | **65 = 51 untracked + 14 modified** (added this report) |
| Staged | 0 | 0 |
| Stash | 0 | 0 |

**Modified (14, all pre-existing, none by this task):** `.agent/PROGRESS.md`, `.gitignore`,
`bot/app.py`, `bot/db.py`, `bot/handlers.py`, `bot/update_outcomes.py`, `bot/web/app.py`,
`bot/web/ratelimit.py`, `bot/web/sessions.py`,
`docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md`,
`docs/proposals/OHB2-TELEGRAM-ACK-ARCHITECTURE-ADR.md`, `tests/test_miniapp_ratelimit.py`,
`tests/test_miniapp_session_persistence.py`, `tests/test_unsupported_attachment_rejection.py`.

**Files touched by this task (all already untracked):** `bot/attachments.py` (F-1 fix),
`tests/test_attachment_cleanup_expiration_a4.py` (+9 tests), and
`docs/reviews/OHB2-P0-A4-CLEANUP-EXPIRATION-RECOVERY-REPORT.md` (F-4 correction). Plus the two new
byte-identical report copies (§7).

### 2.1 Evidence hashes (verified before editing; do not rely on abbreviated hashes)

| Artifact | SHA-256 |
|---|---|
| `docs/reviews/OHB2-P0-A4-CLEANUP-EXPIRATION-RECOVERY-INDEPENDENT-REVIEW.md` | `fc3837e4df2e93bbfa9ec100e10fb82dc43b029fde05cde52d6e3fca0f05d03d` |
| `docs/reviews/OHB2-P0-A4-CLEANUP-EXPIRATION-RECOVERY-REPORT.md` (before F-4) | `d3041c1ebf5d906d04d9912169e3539e03343373e07e6d782eabf2fe7e8354da` |
| `docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md` | `1eca72c1c3a6e9962719b59d7ba0d7eff02d5b76e6464f7d052d0d9ea967471c` |
| `AGENTS.md` | `d6ceda4e890681aa8c50f8fb8052de810ab8320d0ee7e0b20a6476d7f6565bc4` |
| `docs/proposals/OHB2-P0-STAGED-IMPLEMENTATION-PLAN.md` | `06be7ea850c0f605ab6c23a161b19da0733143adaba852ddae6650f0836de868` |

Protected-file hashes (register, `AGENTS.md`, staged plan) are **identical after** the task.

### 2.2 Final artifact hashes

| Artifact | SHA-256 (after) |
|---|---|
| `bot/attachments.py` | `e958bb2bc91c8b4cfa9c8d3beee84055f4f1626a0dc6e6b8976d08bc891790aa` |
| `tests/test_attachment_cleanup_expiration_a4.py` | `25a65849fe0c8f8b719d501e91327e46cdb55db195190794b2150a6a82c48527` |
| `docs/reviews/OHB2-P0-A4-CLEANUP-EXPIRATION-RECOVERY-REPORT.md` (after F-4) | `025641f99419bf23c864773d530ead72f4a2860c90d894a5fcd3449159f88431` |

---

## 3. F-1 — root cause and fix

### 3.1 Root cause

`AttachmentReaper._sweep_orphan_items` (in `bot/attachments.py`) sweeps items whose parent batch row
is **absent** (true orphans). It fetched candidates only for `ATTACHMENT_BATCH_PENDING` and
`ATTACHMENT_ITEM_STORED`. An orphan item already in `ATTACHMENT_ITEM_REAPED` state — i.e. a prior
sweep marked it reaped but its unlink failed, leaving bytes on disk — was therefore never fetched, so
its bytes were never re-attempted. Additionally, its token was already added to `known_tokens` in
sweep step (0a) (`list_all_attachment_items`), so `_scan_root_untracked` also excluded it and it was
not even reported. Net effect: silent residual byte retention (LOW, reachability-bounded — normal
creation is atomic and the batch path already retries `reaped`).

### 3.2 Fix (smallest safe correction)

In `bot/attachments.py` (`_sweep_orphan_items`):

- Added `ATTACHMENT_ITEM_REAPED` to the candidate-status tuple.
- For a `reaped` orphan item, **retry the deletion directly** via the existing `_remove_file(token)`
  (no new CAS call: `mark_attachment_item_reaped` only accepts `pending|stored` and would return
  `False`). The durable decision is already recorded; `_remove_file` remains the single confinement
  and path-safety gate. A `"retry"` result increments the returned `left` (observable).

Nothing else changed. The batch-association guard (`if item.batch_id in all_batches: continue`),
the DB-first ordering for non-reaped items, the `_remove_file` contract
(`is_safe_workspace_path` + `_is_within` + `lstat` no-follow + regular-file check), and the
`known_tokens` accounting are all preserved. No new worker/scheduler/process/DB owner/retention
policy/dependency was introduced.

### 3.3 Why this is safe (revalidated)

- **Batch association:** only items whose `batch_id` is **not** in the set of existing batches are
  touched ⇒ live/terminal batches are never affected.
- **Ownership:** an orphan has no valid batch/owner by construction; the sweep is global (unchanged
  behavior) and never uses filenames to infer ownership/association.
- **Containment/path safety:** all deletion is delegated to `_remove_file`, which refuses
  non-safe tokens, paths outside the staging root, symlinks, and non-regular files (left + reported).
- **DB-first + idempotency:** for `reaped` orphans the durable decision already exists; a missing
  file reconciles as `absent` (idempotent); a transient FS failure yields `"retry"` and is reported.
- **Identity:** no path touches `attachment_message_identity`.

---

## 4. Tests proving the fix and its safety

Added **9** focused tests to `tests/test_attachment_cleanup_expiration_a4.py` (deterministic,
isolated `tmp_path`, injected clocks; no network, no sleeps):

| # | Test | Requirement covered |
|---|---|---|
| 1 | `test_orphan_reaped_item_with_remaining_bytes_is_reaped` | orphan `reaped` + remaining bytes ⇒ safely reaped |
| 2 | `test_orphan_reaped_item_second_sweep_is_idempotent` | second sweep idempotent |
| 3 | `test_orphan_reaped_item_deletion_failure_is_retryable_and_observable` | FS failure retryable + observable (`orphans_left`) |
| 4 | `test_orphan_reaped_item_of_live_batch_is_not_deleted` | protected/live batch not deleted |
| 5 | `test_orphan_reaped_item_of_terminal_batch_handled_by_batch_path` | terminal batch handled once by batch path |
| 6 | `test_orphan_reaped_item_cross_owner_and_conversation_isolation` | cross-owner/conversation isolation intact |
| 7 | `test_orphan_reaped_item_symlink_is_protected` | symlink target not deleted |
| 8 | `test_orphan_reaped_item_unsafe_token_is_protected` | unsafe/traversal token not deleted outside root |
| 9 | `test_orphan_reaped_item_does_not_delete_identity_evidence` | identity evidence preserved (D-35) |

Existing assertions were **not** weakened; the pre-existing orphan test
(`test_orphan_item_without_batch_is_reaped`) still passes.

**Load-bearing proof (reverted-fix mutation, isolated `/tmp` copy — workspace untouched):**
reverting only the candidate-status tuple back to `(PENDING, STORED)` causes **4 failures**:
`test_orphan_reaped_item_with_remaining_bytes_is_reaped`,
`test_orphan_reaped_item_second_sweep_is_idempotent`,
`test_orphan_reaped_item_deletion_failure_is_retryable_and_observable`,
`test_orphan_reaped_item_does_not_delete_identity_evidence` (40 passed).

---

## 5. F-4 — report correction

In `docs/reviews/OHB2-P0-A4-CLEANUP-EXPIRATION-RECOVERY-REPORT.md` §10, exactly two rows were
corrected (headline totals left untouched, as instructed):

| Row | Before | After | Evidence |
|---|---|---|---|
| `<A0–A4 attachment files>` | 297 passed | **299 passed** | 10-file run = 308 total; A4 file = 35; A0–A3 9-file run = 264 ⇒ A0–A4 attachment set = 264 + 35 = **299** (the 10-file run additionally includes the unsupported-rejection integration file) |
| `identity_a3 + terminal_routing` | 98 passed | **65 passed** | `pytest tests/test_attachment_message_identity_a3.py tests/test_attachment_terminal_routing_remediation.py -q` ⇒ **65 passed** |

Headline totals (unchanged, verified): A4 focused = **35 passed**; full suite = **2875 passed**
(baseline 2840). No other section of the historical report was altered and the implementation
verdict was not retroactively changed.

---

## 6. Full validation results (exact commands)

All run in the repo with the project `.venv`.

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest tests/test_attachment_cleanup_expiration_a4.py -q` | **44 passed** (35 original + 9 new) |
| `.venv/bin/python -m pytest <A0–A4 10 attachment files> -q` | **308 passed** |
| `.venv/bin/python -m pytest <A0–A3 9 attachment files> -q` | **264 passed** |
| `.venv/bin/python -m pytest tests/test_attachment_message_identity_a3.py tests/test_attachment_terminal_routing_remediation.py -q` | **65 passed** |
| `.venv/bin/python -m pytest <A3/F1 5 files: identity, terminal_routing, f1_1a, intent, text> -q` | **145 passed** |
| `.venv/bin/python -m pytest -q` (full) | **2884 passed, 0 failed, 0 skipped, 0 xfailed**, 72 warnings (~140 s) |
| `node --test tests/frontend/*.test.js` | **219 pass, 0 fail** |
| `.venv/bin/python -m pyflakes bot/ automation/ tools/ main.py tests/` | exit 0 (clean) |
| `.venv/bin/python -m bandit -r bot/ automation/ main.py -lll -s B613` | **High: 0** (Low 5, Medium 17 — pre-existing) |
| `.venv/bin/python -m bandit -r bot/attachments.py -lll -s B613` | **0 issues** |
| `.venv/bin/python -m pip_audit -r requirements-dev.txt` | No known vulnerabilities found |

**Baseline delta:** full suite **2875 → 2884 (+9)**, all passing; no previously passing test
regressed. A4 file **35 → 44**. No skips, no xfails introduced.

---

## 7. Reports (byte-identical)

- `/tmp/OHB2-P0-A4-LOW-FINDINGS-REMEDIATION-REPORT.md`
- `docs/reviews/OHB2-P0-A4-LOW-FINDINGS-REMEDIATION-REPORT.md`

Verified byte-identical with `cmp`; SHA-256 in §7.1.

### 7.1 SHA-256

- SHA-256 (sha256 of this file with this line removed): `a139384e29f5911ac36240286cd3ba1104afa40460daa562045ef04d3789a2c5`

---

## 8. Remaining findings (unchanged, not fixed)

- **F-2 (INFO):** a symlinked staging **root** is not counted in `unsafe_left` (only logged).
  Unchanged. **Not fixed** (out of scope).
- **F-3 (INFO):** `_mark_expired` success is not reflected in any report counter. Unchanged.
  **Not fixed** (out of scope).
- **F-5 (INFO):** exact-boundary operator differs by one instant between A2 (`>`) and A4 (`>=`) at
  `T0 + 15 min`. Unchanged. **Not fixed** (out of scope).
- Carried-forward A3/F1 documentation notes (stale docstrings, dead `AttachmentRoutingState.TERMINAL`
  enum member) remain untouched.

All three were re-verified present in
`docs/reviews/OHB2-P0-A4-CLEANUP-EXPIRATION-RECOVERY-INDEPENDENT-REVIEW.md` (hash unchanged:
`fc3837e4df2e93bbfa9ec100e10fb82dc43b029fde05cde52d6e3fca0f05d03d`).

---

## 9. Unresolved issues / limitations

- None blocking. The fix removes the F-1 residual-retention gap for orphan `reaped` items.
- The orphan sweep (both before and after) does **not** count deleted orphan bytes into the global
  `files_deleted` counter (pre-existing behavior: `_sweep_orphan_items` returns only `left`, and the
  caller assigns it to `orphans_left`). This task deliberately did **not** change that reporting
  behavior to keep the change minimal; orphan deletion is observable via `orphans_left` (non-zero on
  failure) and the per-item warning log. Noted as a documentation/observability item, not a defect.
- Ambiguous/unknown orphan item statuses remain untouched and are not re-fetched by the orphan sweep
  (pre-existing behavior, out of F-1 scope).

---

## 10. Scope and preservation confirmation

- **No** commit, push, PR, merge, deployment, release, or production call occurred. **Autopush was
  not enabled.**
- **No** `git reset`/`git clean`/force operation/broad restore/revert/broad deletion; **no**
  `git add .` or `git add -A`; staged = 0, stash = 0 throughout.
- Owner-decision register, staged plan, `AGENTS.md`, `.agent/PROGRESS.md`, and `.openhands/memory/*`
  were **not** modified (hashes unchanged for the first three).
- **No unrelated work overwritten:** only the three pre-existing untracked files listed in §2 were
  edited, plus the two new report copies. All other tracked/untracked/ignored/user work is intact
  (working tree 64 → 65 entries; the single addition is this report).
- No B1–B3, Group B/C, or Plan 02 work was started.

---

## 11. Final verdict

**`REMEDIATED_PASS`.**
