# OHB2 — WP-06 Part 2 — Owner Decision Review Batch — Final Report

**Batch ID:** `OHB2-WP06-PART2-OWNER-DECISION-REVIEW-BATCH`
**Date:** 2026-11-19
**Nature:** analysis only. No implementation, migration, payload change, or owner decision was made.

---

## Final batch verdict

# `OWNER_BRIEFING_READY_WITH_NOTES`

The briefing is complete, evidence-based, and ready for owner review. The "WITH_NOTES"
qualification reflects **two material defects found in the reviewed design** (D-1, D-2) that must be
corrected before implementation, plus four open questions the owner must answer.

---

## 1. Task IDs and execution order

| Order | Task ID | Result | Deliverable |
|---|---|---|---|
| 1 | `OHB2-WP06-PART2-DESIGN-INTEGRITY-AUDIT` | **`INTEGRITY_VERIFIED_WITH_NOTES`** | `docs/reviews/OHB2-WP06-PART2-DESIGN-INTEGRITY-AUDIT.md` |
| 2 | `OHB2-WP06-PART2-OWNER-DECISIONS-ANALYSIS` | **Complete** — 7 decisions analyzed | `docs/reviews/OHB2-WP06-PART2-OWNER-DECISIONS-ANALYSIS.md` |
| 3 | `OHB2-WP06-PART2-OWNER-DECISION-BRIEFING` | **`READY_WITH_CONDITIONS`** | `docs/reviews/OHB2-WP06-PART2-OWNER-DECISION-BRIEFING.md` |

TASK-B proceeded only after TASK-A confirmed the design was analyzable. TASK-C proceeded only after
both completed.

---

## 2. Actual repository state

| Field | Value |
|---|---|
| Repository root | `/workspace/project/OpenHandBot` |
| Branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` |
| HEAD | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| `origin/main` | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| ahead / behind | `0 / 0` |
| Upstream | none configured |
| Staged | **0** |
| Modified (pre-existing) | **6** |
| Untracked | **15 → 18** (only the 3 new analysis documents) |
| `.openhands/` | present, untouched |

**Pre-existing modifications preserved (WP-07 and prior tasks):**
```
 M .agent/PROGRESS.md
 M bot/db.py
 M bot/handlers.py
 M bot/watcher.py
 M tests/test_handlers.py
 M tests/test_sw06_unwatch_db_failure_propagation.py
```

**Pre-existing untracked preserved (15 at start):** prior reports, WP-05 acceptance record, WP-07
test files, `tests/test_f03_watch_conversation_status_normalization.py`.

No pre-existing file was overwritten, discarded, reformatted, or absorbed.

---

## 3. Files inspected

**Governance / baseline**
- `AGENTS.md`
- `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md` — `§WP-06` (incl. line 671 dependency, line 683
  exclusions), `§WP-07` (683-690), `§WP-08` (698-720, 791), `§G` dependency graph (873-889), Gate C (924)
- `docs/audits/OHB2-REMEDIATION-MASTER-PLAN.md`, `OHB2-COMPLETE-DEFECT-REGISTER.md` (cross-refs)

**Design under review**
- `docs/design/OHB2-WP06-PART2-CALLBACK-REFS-DESIGN-SPEC.md` (674 lines, all 15 sections)
- `docs/reviews/OHB2-WP06-PART2-CALLBACK-REFS-DESIGN-REPORT.md` (260 lines)

**Source**
- `bot/keyboards.py` (8-17 `CALLBACK_DATA_LIMIT`/`_btn`, 195-215 `files_menu`)
- `bot/files.py` (29, 36, 70-72 `_ID_RE`, 235-265 `authorize_conversation_detailed`)
- `bot/handlers.py` (64 `_allowed`, 83-112 `_safe_answer`, 235 `_authorized_conversation_status`,
  618 `_classify_failure`, 643, 693, 734; all cid-bearing handlers)
- `bot/db.py` (37 `is_transient_sqlite_error`, 255/261 TTLs, 555-556 PRAGMAs, 587-588 `_init_schema`,
  731-739 `web_sessions` DDL, 819 `_migrate`, 1983 `BEGIN IMMEDIATE`, 2689 `prune_web_sessions`,
  2880-2900 `awaiting_state`, 3226 `prune_processed_updates`, 5532 boot prune)
- `bot/attachments.py` (1437-1500 `OpportunisticSweeper` — type coupling)
- `bot/app.py` (121-155 callback registration, 234-278 sweeper wiring)
- `bot/update_outcomes.py` (93 `acknowledgment_boundary`)
- `bot/config.py` (292 `MINI_APP_SESSION_TTL`)

**Docs / tests**
- `docs/OPERATIONS_RUNBOOK.md` (86 — table count claim)
- `tests/test_doc_code_parity.py` (39-47, 82-90 — the NEW-DEF-08 parity assertion)

**No ADRs exist** (`docs/adr` absent) — recorded as a documentation gap, not a blocker; the baseline
documents serve as the architecture authority.

---

## 4. Evidence sources — all measured, none assumed

| # | Claim verified | Method | Result |
|---|---|---|---|
| E-1 | Spec is 674 lines / 15 sections | `wc -l`, `grep "^## "` | **Confirmed** |
| E-2 | O-1 … O-7 all present | `grep "O-[1-7]"` | **All 7, inline + §15** |
| E-3 | 7 reuse mechanisms exist | direct source read | **All 7 confirmed** |
| E-4 | `files:`/`file:` binding at 54-55 | real `_btn()` sweep | **files 54, file 55** |
| E-5 | Payload limits are digit-dependent | sweep at 4 digit widths | **files 47-54, file 48-55** |
| E-6 | 12-char token fits | real payload construction | **25-33 B (cap 64)** |
| E-7 | Token ambiguity universal | 2,000 generated tokens | **2000/2000 pass `_ID_RE`** |
| E-8 | Unresolved token reaches upstream | `authorize_conversation_detailed` with spy client | **Remote call MADE; NOT_FOUND** |
| E-9 | Nested `BEGIN IMMEDIATE` fails | real sqlite3 | **`OperationalError`** |
| E-10 | Nesting error → `FAILED_PERMANENT` | `is_transient_sqlite_error` | **False → no retry** |
| E-11 | WP-07 overlap in handlers | `git diff -U0` function hunks | **17 functions; 4 cid-handlers** |
| E-12 | Consume latency @ 5,000 rows | timing, 200 iterations | **median 1.181 ms** |
| E-13 | Bounded prune latency | timing, 200 rows | **1.622 ms** |
| E-14 | Schema init idempotent | reopen simulation | **17 → 17 → 18, no error** |
| E-15 | Runbook parity breaks on +1 table | simulate assertion | **`**18** جدول` absent → FAIL** |
| E-16 | WP-07 uncommitted scale | `git diff --stat` | **420 insertions, 109 deletions** |
| E-17 | WP-07 tests pass | `pytest tests/test_wp07_*.py` | **100 passed** |
| E-18 | `_nocommit` pattern precedent | `grep` | **12+ instances** |
| E-19 | 17 live tables | `sqlite_master` | **17** |
| E-20 | `callback_refs` absent from code | `grep bot/ tests/` | **0 matches** |

---

## 5. Results

### 5.1 TASK-A — Design Integrity Audit → `INTEGRITY_VERIFIED_WITH_NOTES`

Verified: spec presence (674 lines), 15 sections, 7 decisions, 12 claim-to-source traces, 7 reuse
mechanisms, payload thresholds, token fit, ambiguity, choke-point effectiveness.

**Six defects found:**

| ID | Severity | Defect |
|---|---|---|
| **D-1** | **MATERIAL** | Atomic-consumption precedent (`take_awaiting` self-contained `BEGIN IMMEDIATE`) is **unsafe**: WP-07 opens `BEGIN IMMEDIATE` in 4 affected handlers → nesting raises `OperationalError` → `FAILED_PERMANENT` → **DEF-002 polling stall**. Reproduced. Project already superseded `take_awaiting` with `awaiting_state` (`db.py:2880-2900`). |
| **D-2** | **MATERIAL** | "Unresolved token cannot reach OpenHands" is **overstated**. 2000/2000 tokens pass `is_valid_conversation_id`; validation occurs *after* acceptance as an ID; the remote call **is** made (returns `NOT_FOUND`). Safety holds (no action authorized), but the stated mechanism is wrong. |
| D-3 | LOW | `db.py` line numbers are HEAD-relative; WP-07 shifts them (+269 lines). |
| D-4 | LOW | `file:` safe max is **55**, not 54; limits are digit-width **ranges**, not constants. |
| D-5 | LOW | **14** cid-bearing handlers, not 15; `repos_page`/`pick_repo` are page/gen-only. |
| D-6 | MEDIUM | `OpportunisticSweeper` is hard-typed to `AttachmentReaper`; reuse needs out-of-scope `attachments.py` edits. |

### 5.2 TASK-B — Seven Decisions Analysis → Complete

All seven analyzed in the mandated 13-point format with measured evidence:

| ID | Recommendation | Confidence |
|---|---|---|
| O-1 | 12 chars retained (+ mandatory choke-point test) | HIGH |
| O-2 | 30 min / 5000 / 200, **insert-path cap mandatory** | HIGH |
| O-3 | Boot hook + insert-path cap; **no sweeper, no new worker** | HIGH |
| O-4 | Single-use all scopes, **transaction-composing** (reject spec's `BEGIN`) | HIGH |
| O-5 | New table; **hard gate** | HIGH |
| O-6 | Atomic runbook update with DDL | HIGH |
| O-7 | **Sequence after WP-07** (spec's "independent" is not supportable) | HIGH |

### 5.3 TASK-C — Owner Decision Briefing → `READY_WITH_CONDITIONS`

Produced all 8 required sections: executive summary, seven-decision matrix, mandatory gates,
security-critical requirements (S-1 … S-11, all marked non-negotiable where applicable), recommended
implementation sequence (Stage 0-4), rejected alternatives (10), owner decision checklist
(no preselection), final readiness verdict.

---

## 6. Files created

| File | Purpose |
|---|---|
| `docs/reviews/OHB2-WP06-PART2-DESIGN-INTEGRITY-AUDIT.md` | TASK-A deliverable |
| `docs/reviews/OHB2-WP06-PART2-OWNER-DECISIONS-ANALYSIS.md` | TASK-B deliverable |
| `docs/reviews/OHB2-WP06-PART2-OWNER-DECISION-BRIEFING.md` | TASK-C deliverable |
| `docs/reviews/OHB2-WP06-PART2-OWNER-DECISION-REVIEW-BATCH-REPORT.md` | This report |

**No other file was created, modified, or deleted.**

---

## 7. Unavailable checks and missing references

| Item | Status | Reason |
|---|---|---|
| ADR documents | **ABSENT** | No `docs/adr` directory exists. Baseline documents used as architecture authority. Not a blocker. |
| Runtime verification of TTL/concurrency | **NOT RUN — deliberately** | Would require the prohibited implementation |
| Migration dry-run on a real database | **NOT RUN — deliberately** | No schema change authorized |
| Independent review | **NOT PERFORMED** | Per batch rules: "Do not claim independent review. This is an analytical review in the current environment." This is a same-agent analytical review; independence is **not** established. |
| Live Telegram / OpenHands API | **NOT CALLED** | Prohibited; all client behavior tested with in-process spies |

Nothing above is claimed as passing.

---

## 8. Non-modification confirmation

| Area | Status | Evidence |
|---|---|---|
| Production source (`bot/`) | **NOT MODIFIED** | `git status --short bot/` shows only the 3 pre-existing WP-07 files |
| Tests | **NOT MODIFIED** | Only the pre-existing untracked WP-07 test files; no test edited |
| Database schema / migrations | **NOT MODIFIED** | Live table count still **17**; `_init_schema` untouched |
| Callback payloads | **NOT MODIFIED** | `bot/keyboards.py` untouched |
| Mini App | **NOT MODIFIED** | No Mini App path touched |
| WP-07 | **NOT MODIFIED** | 6 pre-existing modified files untouched; 420-line diff intact |
| WP-08 | **NOT MODIFIED** | `docs/OPERATIONS_RUNBOOK.md` untouched (only read) |
| Design spec under review | **NOT MODIFIED** | No edit made during TASK-A (per instruction) |
| Dependencies | **NOT INSTALLED/CHANGED** | All tools pre-existing |
| Git history | **NOT CHANGED** | HEAD still `52e7789`; staged = 0 |
| Secrets | **NOT ACCESSED/DISCLOSED** | No credential read or printed |
| Live services | **NOT CALLED** | No Telegram/OpenHands API call |

**Autopush:** disabled and inactive — no push attempted. **No commit, PR, merge, deploy, or release.**

---

## 9. Confirmation: no implementation or owner decision authorized

- **No `callback_refs` implementation** was written, scaffolded, or stubbed.
- **No database migration** was executed or prepared.
- **No callback payload** was changed.
- **No owner decision was recorded.** O-1 … O-7 remain **OPEN**. The recommendations in TASK-B and
  TASK-C are advisory; the checklist in briefing §7 explicitly does not preselect or record answers.
- **No work package was started.** WP-06 Part 2 remains **open and blocked on owner decisions**;
  WP-07 and WP-08 were not touched.

---

## 10. Verification gate (baseline health unchanged)

| Check | Result |
|---|---|
| `pytest -q` | **3385 passed**, 74 warnings, exit 0 |
| `pyflakes` | **0 issues** |
| `bandit -lll` | **High: 0** |
| `node --test tests/frontend/*.test.js` | **280 pass, 0 fail** |
| `pytest tests/test_doc_code_parity.py` | **6 passed** |

Identical to the pre-batch baseline — **no drift**, confirming the analysis changed nothing.

---

## 11. What the owner must decide next

1. **O-5 (hard gate)** — approve or reject the `17 → 18` schema transition.
2. **O-7** — commit/stabilize WP-07 before WP-06 Part 2 implementation.
3. **O-4** — accept transaction-composing consumption (replaces the spec's defective mechanism).
4. **O-1, O-2, O-3, O-6** — approve the recommended parameters.

Plus the two corrections: **D-1** (consumption contract) and **D-2** (risk wording).

Until these are recorded, **implementation must not begin.**
