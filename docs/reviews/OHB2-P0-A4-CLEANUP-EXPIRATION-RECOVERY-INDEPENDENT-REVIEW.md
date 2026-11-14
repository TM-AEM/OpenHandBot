# OHB2-P0-A4-CLEANUP-EXPIRATION-RECOVERY — Independent Adversarial Review

> Prepared by an AI agent (OpenHands) on behalf of the owner. **Read-only review**: the only
> repository write is this report at the exact `docs/reviews/` path (an authorized review artifact).
> No A4 code, test, `.agent/PROGRESS.md`, `.openhands/memory/*`, owner-decision register, or
> approved design was modified. No commit/push/PR/merge/deploy. All adversarial probes were run in
> isolated `/tmp` sandboxes; mutation testing was performed on a throwaway copy of the repo under
> `/tmp`, never in the workspace.

- **Task ID:** OHB2-P0-A4-CLEANUP-EXPIRATION-RECOVERY-INDEPENDENT-REVIEW
- **Date (UTC):** 2026-11-11
- **Role:** independent reviewer (not the implementer).
- **Scope reviewed:** the already-implemented, **uncommitted** A4 work in the current working tree,
  against **D-09-R2** and **D-25 / D-26 / D-32 / D-33 / D-34 / D-35**, and R4 Stage A4.
- **Verdict:** **`PASS_WITH_NOTES`** (no BLOCKER/HIGH/MEDIUM; findings are LOW/INFO).
- **A4 readiness:** the A4 implementation correctly and safely implements fixed persistent expiry,
  safe cleanup/reaping, recovery, FS/DB consistency, and fail-closed guarantees. **SAFE TO PROCEED**
  to the A4 closure/commit step. The single MEDIUM-adjacent item (F-1) is a pre-existing,
  reachability-bounded residual-cleanup gap, not a data-safety or fail-closed defect.

---

## 1. Verdict

**`PASS_WITH_NOTES`.**

A4 realizes R4 Stage A4 as intended and honors every binding owner decision that governs it:

- **Fixed persistent expiry (I4/I6):** `T0` is read once and never extended; the batch deadline is a
  separate constant `ATTACHMENT_BATCH_TTL` (15 min), distinct from the route window `AWAITING_TTL`
  (10 min). The reaper never writes `t0` (`mark_attachment_batch_status` explicitly does not touch it).
- **Safe cleanup/reaping:** every unlink is confined to the staging root, gated by
  `files.is_safe_workspace_path(token)` + `_is_within(root)` + `lstat` (no symlink following) + a
  regular-file check; directory/symlink/escape/absolute tokens are refused and reported.
- **DB-before-FS ordering:** the durable decision (batch `expired`, item `reaped` via CAS) is written
  **before** any byte deletion; a post-transition FS failure stays visible and retryable (no false
  success). Independently mutation-proved (M2).
- **Recovery:** crash-after-transition-before-unlink is healed on the next sweep (item `reaped` ⇒
  retry); missing files reconcile as `absent` (idempotent success); missing t0 / unknown status are
  fail-closed (left + reported), never guessed.
- **Fail-closed guarantees:** unknown batch/item status, unresolved batches
  (`intent_recorded`/`dispatching`/`uncertain`), symlinked roots, non-regular entries, and unsafe
  tokens all result in **no deletion**.
- **No new worker / scheduler / process / independent DB owner (F4, I3, D-09/H):** the sweep is
  invoked once from the pre-existing startup recovery hook in `bot/app.py`, on the existing single
  DB connection, best-effort (never blocks startup). Verified by inspection and by test.
- **D-35 identity independence:** `attachment_message_identity` is never touched by any A4 path
  (no DELETE against it anywhere in the codebase), survives expiry transitions, reaping, orphan
  cleanup, and `processed_updates` pruning; the `ON DELETE RESTRICT` FK blocks batch-row deletion
  while identity evidence exists. Independently reproduced.
- **D-32 / D-33 / D-34:** the reaper leaves `intent_recorded`/`dispatching`/`uncertain` batches
  untouched; `TERMINAL_UNPROVEN` still fails closed after A4; no A4 code path reaches `_send_prompt`,
  the outbox, or any remote call.

No BLOCKER/HIGH/MEDIUM data-safety, fail-closed, or authorization-boundary defect was found.
Findings F-1…F-5 are residual/observability/documentation items (one LOW functional-retry gap, the
rest LOW/INFO), none of which changes a durable decision, deletes the wrong bytes, reaches the
network, or violates a binding decision.

---

## 2. Repository baseline and preservation findings

| Item | Value |
|---|---|
| Repository root | `/workspace/project/OpenHandBot` |
| Branch | `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW` (no upstream configured) |
| HEAD | `907b20de3fa6627795c14f29677e9f39c68e82f4` |
| `origin/main` | `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c` |
| Working tree | **63 entries = 49 untracked + 14 modified** (matches the reported baseline; no staged, no stash) |
| A4-relevant files | `bot/attachments.py` (new), `bot/db.py` (M), `bot/app.py` (M), `bot/web/app.py` (M), `tests/test_attachment_cleanup_expiration_a4.py` (new), `docs/reviews/OHB2-P0-A4-CLEANUP-EXPIRATION-RECOVERY-REPORT.md` (new) |

**Preservation:** before the review the tree held 63 entries; after the review the tree still holds
**63 entries (49 `??` + 14 `M`), staged = 0, stash = 0, HEAD unchanged**. The review added exactly
one file (this report). No tracked A4 file was modified. Verified with `git status --short` and
`git diff --stat` before/after.

**Source-evidence hashes (verified matching before the review):**

| Artifact | SHA-256 |
|---|---|
| A4 report `docs/reviews/OHB2-P0-A4-CLEANUP-EXPIRATION-RECOVERY-REPORT.md` | `d3041c1ebf5d906d04d9912169e3539e03343373e07e6d782eabf2fe7e8354da` |
| Register `docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md` | `1eca72c1c3a6e9962719b59d7ba0d7eff02d5b76e6464f7d052d0d9ea967471c` |
| Staged plan `docs/proposals/OHB2-P0-STAGED-IMPLEMENTATION-PLAN.md` | `06be7ea850c0f605ab6c23a161b19da0733143adaba852ddae6650f0836de868` |
| `AGENTS.md` | `d6ceda4e890681aa8c50f8fb8052de810ab8320d0ee7e0b20a6476d7f6565bc4` |

Protected files (register, staged plan, `AGENTS.md`) were **not** modified by this review.

---

## 3. What A4 changes (as reviewed)

- `bot/attachments.py` (new, 1082 lines): `AttachmentReaper` (`sweep`, `_sweep_batch`,
  `_mark_expired`, `_sweep_orphan_items`, `_scan_root_untracked`, `_count_unsafe_entries`,
  `_validated_root`, `_is_unsafe_entry`, `_remove_file`, `_log_report`); `SweepOutcome`,
  `BatchSweepResult`, `SweepReport`. Reuses the existing `StagingStore` (no second connection).
- `bot/db.py` (M): adds `ATTACHMENT_ITEM_REAPED`; `list_expired_pending_attachment_batches`,
  `list_attachment_batches_by_status`, `list_all_attachment_batches`,
  `list_attachment_items_by_status`, `list_all_attachment_items`, `mark_attachment_item_reaped`
  (CAS `pending|stored → reaped`), `count_attachment_batches/items`; `_parse_iso` now tolerates
  `TypeError`.
- `bot/app.py` (M): one best-effort sweep call in `_post_init`, after
  `deletion.reconcile_pending_deletions`, before the workers start.
- `bot/web/app.py` (M): unrelated to the reaper (see §7 scope note).
- `tests/test_attachment_cleanup_expiration_a4.py` (new, 35 tests).

---

## 4. Independent verification (read-only)

All commands run with the project `.venv`.

| Command | Observed result |
|---|---|
| `.venv/bin/python -m pytest tests/test_attachment_cleanup_expiration_a4.py -q` | **35 passed** |
| `.venv/bin/python -m pytest -q` (full suite) | **2875 passed**, 72 warnings (~143 s) |
| `.venv/bin/python -m pytest --collect-only --ignore=<A4 file>` | **2840 collected** (baseline) |
| `.venv/bin/python -m pytest <10 A0–A4 attachment files> -q` | **299 passed** |
| `.venv/bin/python -m pytest <9 A0–A3 attachment files> -q` | **264 passed** |
| `node --test tests/frontend/*.test.js` | **219 pass, 0 fail** |
| `.venv/bin/python -m pyflakes bot/ automation/ tools/ main.py tests/` | exit 0 (clean) |
| `.venv/bin/python -m bandit -r bot/ automation/ main.py -lll -s B613` | High: 0 (Low 5, Medium 17 — pre-existing) |
| `.venv/bin/python -m bandit -r bot/attachments.py -lll -s B613` | **0 issues** |
| `.venv/bin/python -m pip_audit -r requirements-dev.txt` | No known vulnerabilities found |

**Baseline delta:** full-suite collection **2840 → 2875 (+35)**, all passing; no previously passing
test regressed. The pre-existing attachment lifecycle set is **264 (A0–A3) → 299 (A0–A4) = +35**.

### 4.1 Independent mutation testing (isolated copy under `/tmp`, workspace untouched)

| Mutation | Expected | Observed |
|---|---|---|
| M1 — disable expiry in `list_expired_pending_attachment_batches` | A4 expiry tests fail | **7 failed**, 28 passed |
| M2 — delete-before-mark in `_sweep_batch` | DB-before-FS test fails | **10 failed**, 25 passed |
| M3 — remove symlink/non-regular guard in `_remove_file` | symlink test fails | **1 failed** (`test_symlink_inside_root_is_left_not_removed`) |

Each mutation was applied to a throwaway copy and the original restored from the workspace file; the
workspace file was never mutated. These confirm the expiry logic, the DB-before-FS ordering, and the
symlink guard are load-bearing (not vacuous tests).

### 4.2 Independent adversarial probes (isolated `/tmp` sandboxes)

17+ probes, all producing the fail-closed/safe outcome, including:

- **P1** staging root replaced by a symlink to an outside dir ⇒ victim bytes **survive**, no deletion
  through the link.
- **P2** a token path replaced by a symlink to an outside file ⇒ target survives; the symlink is not
  unlinked.
- **P3** traversal token (`../escape`) ⇒ refused, escape file survives.
- **P4/P12** live `pending` batches (own and other owner) ⇒ bytes retained.
- **P5/P6/P7** identity evidence survives reaping and expiry; no identity DELETE exists in source;
  `ON DELETE RESTRICT` blocks batch-row deletion while evidence exists.
- **P8** unknown batch status ⇒ left untouched, reported (`errors ≥ 1`).
- **P9** malformed `t0` on a terminal batch ⇒ left untouched (skipped).
- **P10** crash-after-mark (item `reaped`, file present) ⇒ healed on re-sweep.
- **P13** root replaced by a regular file ⇒ no crash, root not deleted.
- **P14** token path is a directory ⇒ not removed.
- **P15** naive `now` ⇒ normalized, expiry still correct.
- **P16** unreferenced file ⇒ left and reported (`untracked_left ≥ 1`).
- **P17** orphan item with a normal (non-reaped) status ⇒ reaped + file deleted.
- **Uncertain/dispatching** batches ⇒ retained (`skipped`), `files_deleted == 0`.
- **D-35 independence:** `processed_updates` pruned to 0 ⇒ identity row and its
  `message_identity_batch_id` resolution both survive; routing stays `TERMINAL_ASSOCIATED` for the
  bound message and `TERMINAL_UNPROVEN` (fail-closed) otherwise.

---

## 5. Decision conformance matrix

| Decision / invariant | Requirement | A4 evidence | Status |
|---|---|---|---|
| D-09-R2 | Local-only A0–A4; no new worker/DB owner/backup/exactly-once/remote | Sweep called once from existing startup hook; single connection; no remote calls; no new task | ✅ |
| D-25 / D-26 | Route window (10) and batch window (15) separate; expiry independent | `ATTACHMENT_BATCH_TTL` (15) separate from `AWAITING_TTL` (10); reaper uses only the batch TTL | ✅ |
| I4 / I6 | Fixed `t0`, never extended/reset | `mark_attachment_batch_status` never writes `t0`; expiry computed from stored `t0` | ✅ |
| D-32 | `intent_recorded`/`dispatching`/`uncertain` block & are not reaped; terminal doesn't auto-convert | Unresolved statuses counted `skipped`, bytes retained; no conversion path in the reaper | ✅ |
| D-33 | Message↔batch identity; fail-closed | Unchanged by A4; `TERMINAL_UNPROVEN` still fails closed (test + probe) | ✅ |
| D-34 | Terminal routing behaviour | Unchanged by A4 | ✅ |
| D-35 | Identity evidence retained independently; no cascade; RESTRICT future-only | No identity DELETE in source; FK RESTRICT enforced; survives prune/reap/expiry (probe) | ✅ |
| I12 | Cleanup only after terminal evidence | Reap only for terminal batches (`delivered`/`expired`/`rejected`/`failed`) with valid `t0` | ✅ |
| F4 / I3 | No new worker/scheduler/process/DB owner | Verified by inspection + test `test_reaper_introduces_no_worker_or_task` | ✅ |

---

## 6. Findings

### F-1 — LOW (functional, residual-cleanup only): orphan item already `reaped` is not retried by the orphan sweep

- **Location:** `bot/attachments.py:940` (`_sweep_orphan_items` iterates only
  `(ATTACHMENT_BATCH_PENDING, ATTACHMENT_ITEM_STORED)`).
- **Observation:** if an orphan item (its parent batch row is absent) is already `reaped` **and** its
  staging file is still present (a prior unlink failed after the mark), the orphan sweep skips it, so
  the byte is never re-attempted. In this exact case `_scan_root_untracked` also excludes it, because
  the token was added to `known_tokens` in step (0a) — so it is not even reported as `untracked_left`.
  Independently reproduced (`/tmp` probe 4): file persists, `untracked_left == 0`, `files_deleted == 0`.
- **Why it is LOW, not higher:** (a) the batch-path (`_sweep_batch`) **does** handle
  `reaped`+present and retries it — so this gap is confined to orphan items; (b) orphan items are
  **not produced by the normal atomic creation paths** (`accept_attachment_item_into_new_batch` /
  `accept_attachment_item` write batch+item in one transaction; A1 writes the item row first, so the
  batch always precedes the item in practice); (c) the gap only arises from a **pre-existing** orphan
  plus a **pre-existing** failed unlink — i.e. two independent failure conditions on data that A2/A1
  do not normally create; (d) no data-safety, fail-closed, or decision violation results — it is a
  residual-space/observability imperfection.
- **Suggested (non-blocking) follow-up for the A4 closure step, if the owner wants zero residual:**
  include `ATTACHMENT_ITEM_REAPED` in the orphan sweep's status set (and, when skipping, do not add
  the token to `known_tokens` so it is at least reported as `untracked_left`). This is a one-line,
  behaviour-preserving extension. **Not required for A4 to pass.**

### F-2 — INFO (observability): a symlinked staging **root** is not counted in `unsafe_left`

- **Location:** `bot/attachments.py:1003` (`_validated_root`) and `:987` (`_count_unsafe_entries`).
- **Observation:** when the root itself is a symlink, `_validated_root` returns `None`, so
  `_count_unsafe_entries` returns 0 and `unsafe_left` stays 0; the condition is only logged (a
  warning). Safety is preserved (no deletion through the link — verified by probe P1), but the
  structured report does not surface the condition.
- **Impact:** none on safety; only on the observability completeness of the report. The `errors`
  counter is not incremented for this case.

### F-3 — INFO (reporting consistency): `_mark_expired` success is not reflected in any report counter

- **Location:** `bot/attachments.py:844` (`_mark_expired`).
- **Observation:** a successful `pending → expired` transition increments no counter. Such a batch is
  swept in the same cycle (step 2), so it appears under `scanned`/`cleaned`/`nothing` — but the
  number of batches *transitioned to expired* is not separately visible. Purely informational.

### F-4 — LOW (report accuracy): two subset test counts in the A4 report do not reproduce exactly

- **Location:** `docs/reviews/OHB2-P0-A4-CLEANUP-EXPIRATION-RECOVERY-REPORT.md` §10.
- **Observation:** the report states the "A0–A4 attachment files" subset = **297 passed** and
  `identity_a3 + terminal_routing` = **98 passed**. Independently, the 10-file A0–A4 set yields
  **299** and the two named files yield **65**. The **headline claims reproduce exactly** (A4 file =
  35; full suite = 2875; baseline 2840; +35). The discrepancy is confined to two non-headline subset
  rows and is most consistent with a slightly different file set / double-counted run at report time;
  it does **not** affect the verified totals or any conclusion. Recommend correcting the two rows.
- **Impact:** documentation accuracy only.

### F-5 — INFO (documentation): exact-boundary operator differs by ±1 instant between A2 and A4

- **Location:** `bot/attachments.py:263` (`batch_is_expired`: `now > deadline`) vs
  `bot/db.py:1373` (`list_expired_pending_attachment_batches`: `now >= deadline`).
- **Observation:** at **exactly** `T0 + 15 min`, A2 still treats the batch as live (`APPEND`) while
  A4's expiry query classifies it as expired. This is a one-instant boundary asymmetry; both are
  fail-closed in spirit and the tests document the A4 boundary (`test_pending_batch_at_exact_deadline_is_expired`).
  It is a consistency note, not a defect. If strict single-source-of-truth is desired, align the two
  operators in a later, separately-reviewed change (out of scope for this review).

### Carried-forward A3/F1 notes (unchanged, pre-existing — not A4)

F-1…F-4 from the A3/F1 consolidated review (stale docstrings in `classify_attachment_routing` and
`has_terminal_attachment_batch`; the dead `AttachmentRoutingState.TERMINAL` enum member at
`bot/db.py:521`; a stale race-test comment) remain present and untouched. They are LOW/INFO
documentation items, already recorded, and outside A4 scope.

---

## 7. Scope / non-goals

- The review is **read-only**. It did not modify A4 code, tests, `.agent/PROGRESS.md`,
  `.openhands/memory/*`, the register, the staged plan, or `AGENTS.md`. The only write is this report.
- `bot/web/app.py` appears in the working-tree diff, but the change is unrelated to the reaper (its
  `_attachment` helper is Mini App file download). It is not part of A4 and is not assessed here.
- This review does **not** authorize commit/push/PR/merge/deploy, remote/materialized retention
  (D-07/D-08, still `BLOCKED — OWNER DECISION REQUIRED`), or any B/C-stage work.
- No production calls, no real user sessions, no network were used.

---

## 8. Limitations

- Mutation testing and adversarial probes were run in isolated `/tmp` copies/sandboxes; they exercise
  the real code paths (no mocks) but not a live Telegram/OpenHands environment.
- The exact-boundary (F-5) and subset-count (F-4) observations are documented, not "fixed" — fixing
  them would be an implementation change and is out of scope for a read-only review.

---

## 9. Conclusion

**Verdict: `PASS_WITH_NOTES`.** A4 correctly and safely implements fixed persistent expiry, safe
cleanup/reaping, recovery, FS/DB consistency, and fail-closed guarantees, in conformance with
D-09-R2, D-25/D-26, D-32, D-33, D-34, and D-35. No BLOCKER/HIGH/MEDIUM finding exists. The one LOW
functional item (F-1) is a reachability-bounded residual-cleanup gap with an optional one-line
follow-up; the remainder are LOW/INFO observability, reporting-accuracy, and documentation items.
**A4 is SAFE TO PROCEED** to its closure/commit step.
