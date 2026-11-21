# OHB2 — WP-06 Part 2 — Design Remediation Batch 02 — Final Report

**Batch ID:** `OHB2-WP06-PART2-DESIGN-REMEDIATION-AND-OWNER-DECISION-BATCH-02`
**Date:** 2026-11-19
**Nature:** documentation and design analysis only.

---

## Final batch verdict

# `OWNER_BRIEFING_READY_WITH_NOTES`

The design is corrected and independently re-validated against the current working tree. The
briefing is ready for owner review. "WITH_NOTES" reflects three items that documentation cannot
close: one unresolved implementation-time assumption (`watcher.unwatch`), inherited performance
figures, and seven owner decisions that remain **open**.

---

## 1. Task results

| Task | Task ID | Verdict | Deliverable |
|---|---|---|---|
| **A** | `OHB2-WP06-PART2-DESIGN-REMEDIATION` | **`DESIGN_CORRECTED_WITH_NOTES`** | Spec Rev 2 + `OHB2-WP06-PART2-DESIGN-REMEDIATION-REPORT.md` |
| **B** | `OHB2-WP06-PART2-REVALIDATION-AND-DECISION-ANALYSIS` | **`REVALIDATED_WITH_NOTES`** | `OHB2-WP06-PART2-REVALIDATION-AND-OWNER-DECISIONS-ANALYSIS.md` |
| **C** | `OHB2-WP06-PART2-REVISED-OWNER-DECISION-BRIEFING` | **`READY_WITH_CONDITIONS`** | `OHB2-WP06-PART2-REVISED-OWNER-DECISION-BRIEFING.md` |

D-1 was resolved in TASK-A, so the batch proceeded through B and C as required.

---

## 2. Current Git state

| Field | Value |
|---|---|
| Repository root | `/workspace/project/OpenHandBot` |
| Branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` |
| HEAD | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| `origin/main` | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| ahead / behind | `0 / 0` |
| Staged | **0** |
| Modified (all pre-existing) | **6** |
| Untracked | 19 → **22** (only my 3 new documents) |
| `.openhands/` | present, untouched |

**Pre-existing modifications preserved:**
```
 M .agent/PROGRESS.md
 M bot/db.py            <- WP-07, untouched
 M bot/handlers.py      <- WP-07, untouched
 M bot/watcher.py       <- WP-07, untouched
 M tests/test_handlers.py
 M tests/test_sw06_unwatch_db_failure_propagation.py
```
All 19 pre-existing untracked files preserved (WP-05/WP-06/WP-07 reports and 7 WP-07 test files).

---

## 3. Checks actually executed in this task

| Check | Command / method | Result |
|---|---|---|
| Full Python suite | `pytest -q` | **3385 passed**, 74 warnings, exit 0 |
| Static analysis | `pyflakes bot/ automation/ tools/ main.py tests/` | **0 issues** |
| SAST (high severity) | `bandit -r ... -lll -s B613` | **High severity: 0** |
| Frontend tests | `node --test tests/frontend/*.test.js` | **280 pass, 0 fail** |
| Doc parity | `pytest tests/test_doc_code_parity.py` | **6 passed** |
| `take_awaiting` callers | `grep -rn` | **0 callers** (dead code) |
| `awaiting_state` callers | `grep -rn` | 3 live call sites |
| `_nocommit` helpers | `grep` | **13 helpers** |
| `BEGIN IMMEDIATE` sites | `grep` | 50 occurrences in `bot/db.py` |
| Transaction-owning cid handlers | AST-ish body scan + indirect wrapper trace | **4 of 14** |
| Composition validity | real `Database` probe: composed insert, rollback, nested | **composed OK; rollback correct; nested fatal + non-transient** |
| Payload boundaries | `_btn()` sweep, all shapes, digit widths 1-5 | `files` 54→47; `file` 55→48; `deleteok` 55; `unwatch` 56 |
| Token ambiguity | `is_valid_conversation_id` on generated tokens | 2000/2000 pass |
| Unresolved token → remote | spy client on `authorize_conversation_detailed` | **call made**, `NOT_FOUND`, not authorized |
| Handler inventory | source enumeration | **14 cid-bearing**, 4 non-cid |
| Sweeper typing | source read | `reaper: AttachmentReaper` (hard-typed) |
| Boot hook | `grep` | `prune_web_sessions(time.time())` at `db.py:5532` |
| Schema idempotency | real `Database` reopen | 17 → 17, no error |
| PRAGMAs | real `Database` | `wal`, `fk=1`, `busy_timeout=5000` |
| Runbook coupling | test source + runbook read | runbook says `**17** جدول`; literal assertion confirmed |
| WP-07 publication | `git show HEAD:bot/db.py \| grep -c` | **0** WP-07 markers in HEAD; 21 in working tree |
| WP-07 review status | report grep | **`INDEPENDENCE_NOT_ESTABLISHED`** (both reports) |

---

## 4. Checks NOT executed, and why

| Check | Reason |
|---|---|
| Consume/prune latency re-measurement | Requires implementing `callback_refs` — **forbidden** in this batch. Figures inherited from the prior batch and flagged for re-measurement. |
| Migration dry-run with the real table | Same — would require a schema change. |
| Live Telegram / OpenHands API calls | Prohibited. All client behavior tested with in-process spies. |
| `watcher.unwatch` transaction behavior | Not a `Database` method; cannot be established from `Database` source. **Recorded as an unresolved assumption.** |
| Independent review | **Not established.** This is a same-agent revalidation; the batch rules forbid claiming independence. |

---

## 5. Results reproduced vs. inherited

**Reproduced in this task (fresh execution):**
- 4-of-14 transaction-owning handler set
- `take_awaiting` has zero callers
- Nested `BEGIN IMMEDIATE` fatal + `is_transient_sqlite_error → False`
- Composition and rollback correctness on a real `Database`
- All payload boundaries across 16 shapes and 5 digit widths
- 2000/2000 token ambiguity
- Unresolved token reaches the remote API
- Schema idempotency (17→17) and PRAGMA preservation
- Runbook literal-count coupling
- WP-07 publication status (0 markers in HEAD)

**Inherited (not re-executed):**
- Consume ≈1.2 ms and prune ≈1.6 ms at 5,000 rows — must be re-measured at implementation time.

---

## 6. D-1 … D-6 disposition

| ID | Disposition |
|---|---|
| **D-1** (critical) | **Resolved** — transaction-composing model; standalone `BEGIN IMMEDIATE` prohibited; ownership, rollback, atomicity, and the 4-handler exception list specified. One sub-assumption (`watcher.unwatch`) flagged. |
| **D-2** | **Resolved** — incorrect claim removed; five-layer boundary table; resolve-before-authorize ordering; spy-client test mandated. |
| **D-3** | **Resolved** — point-in-time policy; symbol-authoritative references; stale forms verified absent. |
| **D-4** | **Resolved** — `file:` = 55; ranges documented; method and cases recorded; 12-char token proven safe. |
| **D-5** | **Resolved** — 14 handlers with full table incl. transaction exposure. |
| **D-6** | **Resolved** — sweeper rejected with source evidence; insert-path cap made mandatory. |

---

## 7. Files created / modified

| File | Change |
|---|---|
| `docs/design/OHB2-WP06-PART2-CALLBACK-REFS-DESIGN-SPEC.md` | **Modified** (Rev 1 → Rev 2; 674 → 970 lines) |
| `docs/reviews/OHB2-WP06-PART2-DESIGN-REMEDIATION-REPORT.md` | **Created** |
| `docs/reviews/OHB2-WP06-PART2-REVALIDATION-AND-OWNER-DECISIONS-ANALYSIS.md` | **Created** |
| `docs/reviews/OHB2-WP06-PART2-REVISED-OWNER-DECISION-BRIEFING.md` | **Created** |
| `docs/reviews/OHB2-WP06-PART2-DESIGN-REMEDIATION-BATCH-02-REPORT.md` | **Created** (this file) |

No other file was created, modified, or deleted.

---

## 8. Non-modification confirmation

| Area | Status | Evidence |
|---|---|---|
| Production code (`bot/`) | **NOT MODIFIED** | Only the 3 pre-existing WP-07 files appear in `git status` |
| Tests | **NOT MODIFIED** | Only pre-existing untracked WP-07 test files; no test edited |
| Database schema / migrations | **NOT MODIFIED** | Live table count still **17**; `callback_refs` in `bot/` = **0** |
| Callback payloads | **NOT MODIFIED** | `bot/keyboards.py` untouched |
| Mini App | **NOT MODIFIED** | No Mini App path touched |
| WP-07 | **NOT MODIFIED** | 6 pre-existing modified files untouched; 21 markers intact |
| WP-08 / runbook | **NOT MODIFIED** | `docs/OPERATIONS_RUNBOOK.md` read only; still states 17 |
| Dependencies | **NOT INSTALLED / CHANGED** | All tools pre-existing |
| Database data | **NOT MUTATED** | All DB work on `tempfile.mkdtemp()` throwaway databases |
| Git history | **NOT CHANGED** | HEAD still `52e7789`; staged = 0 |
| Secrets / production credentials | **NOT ACCESSED** | None read or printed |
| Live services | **NOT CALLED** | No Telegram/OpenHands call |
| Commits / pushes / PRs / merges / deploys | **NONE** | No git write operation performed |
| Autopush | **DISABLED / INACTIVE** | No push attempted |
| Destructive Git commands | **NONE** | No reset/clean/force/restore/checkout |
| Broad staging / deletion | **NONE** | No `git add .`/`-A`; nothing deleted |
| Independent review claim | **NOT CLAIMED** | Explicitly stated as not established |

---

## 9. Verification gate

| Gate | Result |
|---|---|
| `pytest -q` | **3385 passed** (identical to baseline — no drift) |
| `pyflakes` | **0** |
| `bandit -lll` | **High severity: 0** |
| `node --test` | **280 pass / 0 fail** |
| `test_doc_code_parity.py` | **6 passed** |

Identical to the pre-batch baseline, confirming the documentation-only work changed no behavior.

> Note: a documentation test would **fail** if the schema changed without the runbook update. That
> is documented as a future implementation-time requirement (O-6) and was **not** forced to pass by
> editing unrelated files.

---

## 10. Remaining owner decisions

| ID | Decision | Hard gate |
|---|---|---|
| **O-5** | Approve the `17 → 18` schema transition | **YES** |
| **O-7** | Commit/stabilize WP-07 first | **YES** |
| **O-4** | Accept transaction-composing consumption | — (blocks helper) |
| O-1 | 12-char token | — |
| O-2 | 30 min / 5,000 / 200 + mandatory cap | — |
| O-3 | Boot hook + insert cap, no sweeper | — |
| O-6 | Atomic runbook update | — (must land with O-5) |

**No owner decision has been recorded. No implementation is authorized.**

---

## 11. Suggested next step

Record **O-5** and **O-7** first — they gate everything else. Then commit/stabilize WP-07, then
approve **O-4**, then implement in the staged order given in the briefing (§7).

**Stopping here as instructed. Awaiting explicit owner decisions.**
