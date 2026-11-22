# OHB2 — WP-07 / DEF-011 / F-03 — Implementation Report

**Task:** `OHB2-WP07-DEF011-F03-DOCUMENT-SUPERSESSION-REMEDIATION`
**Date:** 2026-11-21
**Plan of record:** `docs/audits/OHB2-WP07-DEF011-F03-DIAGNOSIS-AND-REMEDIATION-PLAN.md`

---

## 1. Final verdict

# `F03_REMEDIATED`

Both historical documents now carry dated, additive supersession notices; the original historical
text is **byte-for-byte preserved** (proven by hash reconstruction, §9); `DEF-011-B` is recorded as
implemented, `DEF-011-A` and `DEF-011-C` as not implemented, and `DEF-011` as still open; T-1…T-4 pass
and are mutation-proven non-vacuous; the full suite moved from **3442 → 3449 passed**, a delta of
exactly **+7** for the 7 added test functions; all gates pass.

**F-03 is a documentation defect, so "remediated" means the drift is corrected and guarded — not that
`DEF-011` is closed.** `DEF-011` remains open (`DEF-011-A`, `DEF-011-C` unimplemented).

---

## 2. Files changed

Exactly the three authorized files. Nothing else.

| # | File | Change | Lines |
|---|---|---|---|
| 1 | `docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md` | Inserted dated correction notice after the header blockquote (after old line 14) | **+39 insertions, 0 deletions** (200 → 239 lines) |
| 2 | `docs/reviews/OHB2-WP07-FINAL-STABILIZATION-BATCH-REPORT.md` | Inserted dated correction notice under `## 11.` | **+8 insertions, 0 deletions** (269 → 277 lines) |
| 3 | `tests/test_doc_code_parity.py` | Appended T-1…T-4 (7 test functions, 3 private helpers, 8 module constants) | **+206 insertions, 0 deletions** |

`git diff --stat` for the test file: `1 file changed, 206 insertions(+)` — **no deletions**.
Both documents are **untracked**, so they show as `??` rather than `M`; the edit is verified by
hash reconstruction in §9.

### Not changed (explicitly)

`bot/attachments.py` (hash unchanged, §8) · all other `bot/*` · all other `tests/*` · `.github/` ·
schema · dependencies · Mini App · `ci.yml`.

---

## 3. Notice locations

### 3.1 Proposal

`docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md` — inserted **immediately after the
existing header blockquote**, before the `---` separator that precedes `## 1. Why the scope must be
split`. Marked:

```
> ## ⚠ LATER CORRECTION — 2026-11-21 (append-only; the historical text above and below is unchanged)
```

The notice contains: a supersession table naming the two stale statements and their locations
(§1 bullet 3, §5 R9); a three-row sub-defect status table (B / A / C); explicit reading rules; and a
statement that §2.2 and §7 are unaffected.

### 3.2 Batch report

`docs/reviews/OHB2-WP07-FINAL-STABILIZATION-BATCH-REPORT.md` — inserted directly under
`## 11. Findings that materially changed the picture`, before the findings table. Marked:

```
> **⚠ LATER CORRECTION — 2026-11-21 (append-only; the historical table below is unchanged).**
```

---

## 4. Evidence: B implemented, A and C not

Measured against the **actual source**, not against prior reports.

| Claim | Evidence | Result |
|---|---|---|
| **`DEF-011-B` implemented** | `grep -c "to_thread" bot/attachments.py` → **5** (lines 88 import, 900 docstring, 953, 968, 1295 `await to_thread.run_sync`); `bot/handlers.py:2087` `to_thread.run_sync(functools.partial(_read_local_capped, …))` | **CONFIRMED** |
| **`DEF-011-A` not implemented** | `grep -cE "reserv\|in_flight\|_ledger" bot/attachments.py` → **0** | **CONFIRMED absent** |
| **`DEF-011-C` not implemented** | Owned by `WP-01`, blocked on `OD-01`/`OD-03`; no UX copy change exists | **CONFIRMED** (unchanged, out of scope) |

**Both halves of the historical R9 are handled distinctly:** the "0 `to_thread`" half is now false and
is marked superseded; the "0 quota ledger" half is **still true** and is explicitly reaffirmed as
accurate in the notice. This is the distinction the plan flagged as the main overclaim risk.

---

## 5. DEF-011 remains open — explicit confirmation

Both notices state, verbatim:

- Proposal: "**DEF-011 is NOT fully implemented and NOT closed.**" and "`DEF-011` **remains open**".
- Batch report: "**`DEF-011` remains open** — it is **not** fully implemented and **not** closed."

Neither notice claims A, B and C are all implemented, and neither converts §7's historical
non-authorization into a present-day implementation claim.

---

## 6. Test results — T-1 … T-4

`python -m pytest tests/test_doc_code_parity.py -v` → **13 passed** (6 pre-existing + 7 new).

| Test | Purpose | Result |
|---|---|---|
| `test_t1_correction_notice_matches_actual_implementation_state` | Notice status rows match real code (B implemented, A/C not); `to_thread` count in the notice matches the code | **PASS** |
| `test_t1_reservation_ledger_absence_still_accurate` | "0 quota ledger" remains true, so A stays NOT IMPLEMENTED | **PASS** |
| `test_t2_protected_sections_are_byte_for_byte_unchanged` | §2.2 and §7 equal golden byte-exact literals | **PASS** |
| `test_t2_historical_stale_claims_are_preserved_verbatim` | The three stale historical statements still exist verbatim | **PASS** |
| `test_t3_both_documents_state_def011_remains_open` | Both notices say "remains open" and "not closed" | **PASS** |
| `test_t3_no_claim_that_all_sub_defects_are_implemented` | Any "fully implemented" mention is negated; "not implemented" present | **PASS** |
| `test_t4_both_notices_share_date_status_and_scope_language` | Same date, same three sub-defect IDs, same "five" count in both | **PASS** |

The tests parse **document sections** (by textual boundaries, not line numbers) and compare against
golden byte-exact literals — they are not arbitrary substring greps.

### 6.1 Mutation proof (non-vacuity)

Each mutation applied to a scratch copy, focused tests re-run, then restored.

| # | Mutation | Caught by | Observed |
|---|---|---|---|
| **M1** | Rewrite the historical "0 `to_thread`" claim in place | `t2_historical_stale_claims…` | **1 failed**, 12 passed |
| **M2** | Delete the entire proposal correction notice | T-1, both T-3s, T-4 | **4 failed**, 9 passed |
| **M3** | Flip `DEF-011-A` to **IMPLEMENTED** in the notice | `t1_correction_notice_matches_actual…` | **1 failed**, 12 passed |
| **M4** | Tamper §2.2 by one character (`(edited)` appended) | `t2_protected_sections…` | **1 failed**, 12 passed |
| **M5** | Change the batch report notice date to 2026-11-20 | `t4_both_notices_share_date…` | **1 failed**, 12 passed |

All five reproduced with the **intended** cause. After each, files were restored and the suite
re-verified green (13/13).

---

## 7. Full suite: baseline vs final, with arithmetic

Both runs in the same container (`python:3.11-slim`, deps from `requirements-dev.txt`, `git` installed),
same working tree except for this remediation.

| Run | Result |
|---|---|
| **Baseline (pre-change)** | `3442 passed, 1 skipped, 74 warnings` |
| **Final (post-change)** | `3449 passed, 1 skipped, 74 warnings` |
| **Delta** | **+7 passed, 0 skipped change, 0 new failures** |

**Arithmetic:** `3442 + 7 = 3449`. ✅ Exactly 7 — matching the 7 new test functions in T-1…T-4
(2×T-1, 2×T-2, 2×T-3, 1×T-4 = 7). No other test changed state; nothing that passed before fails now.

**Disclosure — baseline method.** The first baseline attempt in a bare slim image gave
`5 failed, 3437 passed, 1 skipped` because `git` was absent and 5 autopush tests shell out to `git`
(`FileNotFoundError: [Errno 2] No such file or directory: 'git'`). After installing `git` the baseline
became `3442 passed, 0 failed`. This is an **environment** artifact, not a code or F-03 issue, and is
recorded here rather than concealed. The final run used the identical environment, so the comparison
is apples-to-apples.

---

## 8. Lint / static / security gates

| Gate | Command | Result |
|---|---|---|
| **pyflakes** | `python -m pyflakes bot/ automation/ tools/ main.py tests/` | **exit 0, no output** — clean |
| **bandit** | `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | **exit 0**; `Severity: High` issues = **0**. (Metrics block prints a raw pre-filter `High: 6` count; the filtered issue list is empty and exit is 0 — pre-existing, unrelated to this docs-only change.) |
| **Node frontend** | `node --test tests/frontend/*.test.js` | **pass 280, fail 0** (identical to baseline) |
| **pip-audit** | not re-run | No dependency change; `requirements*.txt` untouched. No new risk introduced by a docs edit. |

---

## 9. Byte-for-byte preservation evidence

### 9.1 Protected sections compared against pre-change snapshots

| Section | Pre-change SHA-256 | Post-change | Result |
|---|---|---|---|
| Proposal §2.2 | `b10cdb6dca9017e195b911d98bd603b3f243056dc2146468b2d65888d067a98d` | identical (`diff` empty) | **UNCHANGED** |
| Proposal §7 | `ba02416da1b943bffb10cd99338a8c406d428fae18b660378f5d92b4ad5f8374` | identical (`diff` empty) | **UNCHANGED** |
| Batch report row 1 | `71270e5c1add25d8377dce978ceb352da65423c032b4f3c85d64819aad6947a7` | identical | **UNCHANGED** |

§7 includes the historical `- **No DEF-011 implementation.**` line — preserved, **not** reinterpreted
as a present-day claim.

### 9.2 Insertion-only proof (strongest evidence)

Removing the inserted notice from each file and re-hashing reproduces the **exact original SHA-256**:

| File | Reconstructed SHA-256 | Original SHA-256 | Match |
|---|---|---|---|
| Proposal | `82fbf9869e9393b5f3c7d756aea82991ffff97a77124a8dfbb9f82d2681c2b7c` | `82fbf986…c2b7c` | **EXACT** |
| Batch report | `2cce88dd4290a285dc383b9c4ada43a9fe9ce36b3141a0369a7065f7a171512c` | `2cce88dd…512c` | **EXACT** |

This proves both edits are **pure insertions** — not one byte of the original was altered, moved, or
deleted. The three historical stale statements (`§1` bullet 3, `§5` R9, batch row 1) remain present
verbatim.

---

## 10. Git state — no commit / push / PR / merge / deploy

| Item | Value |
|---|---|
| `HEAD` | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` (unchanged) |
| `origin/main` | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| Branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` |
| Staged | **0** |
| Commit / push / PR / merge / deploy / Autopush | **none performed** |

Final `git status --short` (relevant entries):

```
 M tests/test_doc_code_parity.py          <- authorized test edit
?? docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md   <- authorized (untracked doc)
?? docs/reviews/OHB2-WP07-FINAL-STABILIZATION-BATCH-REPORT.md       <- authorized (untracked doc)
```

No `git add`, no `git add .`, no `git add -A`, no reset/clean/stash/force operation was used.

---

## 11. Pre-existing workspace preserved

| Item | Status |
|---|---|
| The **8** pre-existing modified files | **all intact**, untouched: `.agent/PROGRESS.md`, `bot/app.py`, `bot/attachments.py`, `bot/db.py`, `bot/handlers.py`, `bot/watcher.py`, `tests/test_handlers.py`, `tests/test_sw06_unwatch_db_failure_propagation.py` |
| Their mtimes | all `2026-11-19` / `2026-11-20` — predate this session; not modified by me |
| `.openhands/` and `.agent/` | present and untouched |
| Pre-existing untracked/ignored files | preserved; untracked count grew only by the 2 authorized docs + this report |
| `bot/attachments.py` | **hash unchanged** `b98d561f0ba0ab27dea4e6bedee7955f68f1f6fa85a39fa81afe8aeb4d818356` |

`git diff --name-only` now lists **9** files = the **8** pre-existing + `tests/test_doc_code_parity.py`.
That +1 is the only tracked modification I introduced, and it is authorized.

---

## 12. Remaining limitations (not presented as completed)

1. **`DEF-011-A` and `DEF-011-C` remain unimplemented.** This task corrected documentation only. No
   quota reservation ledger was added; no attachment UX copy was changed. `DEF-011` is **open**.
2. **`D6` (repeated raw cancellation during drain) remains deferred and unimplemented.**
3. **The incorrect F-01 cross-reference was deliberately NOT changed.** `OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md:300`
   attributes F-03 to "Batch-03 DOC-01", which is a different identifier (Mini App session
   persistence). The diagnosis recorded this as a **separate historical attribution issue, not part of
   this remediation**, and it was left alone per the task's explicit instruction.
4. **The other two findings sharing the `F-03` label** (WP-05/`DEF-009` status-label test gap;
   P0-register U-5/U-6 fold explanation) were **not touched** — both were already closed in their own
   contexts.
5. **Both corrected documents remain untracked.** Closing F-03 does not require publishing them;
   committing is a separate Git action, not authorized here.
6. **`pip-audit` was not re-run** (no dependency change). If the owner wants a fresh SCA pass, it
   should run in CI.
7. **Independent review was not performed.** This is a self-implementation report; Prompt 3 is the
   review/closure step.

---

## 13. Readiness for Prompt 3 (final review / closure)

The reviewer can verify everything above with:

```bash
cd /workspace/project/OpenHandBot
grep -c "LATER CORRECTION" docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md   # 1
grep -c "LATER CORRECTION" docs/reviews/OHB2-WP07-FINAL-STABILIZATION-BATCH-REPORT.md        # 1
grep -c '0 `to_thread` in `attachments.py`; 0 quota ledger' \
  docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md                             # 1 (history intact)
grep -c "to_thread" bot/attachments.py                                                       # 5 (B implemented)
grep -cE "reserv|in_flight|_ledger" bot/attachments.py                                       # 0 (A absent)
python -m pytest tests/test_doc_code_parity.py -q                                            # 13 passed
python -m pytest -q                                                                          # 3449 passed, 1 skipped
sha256sum bot/attachments.py   # b98d561f0ba0ab27dea4e6bedee7955f68f1f6fa85a39fa81afe8aeb4d818356
```

The core question for closure is settled: the stale present-tense claims are corrected **without
altering a single byte of the historical record**, and a regression guard now prevents both silent
re-drift and overclaiming.

---

## LATER CORRECTION — 2026-11-22 (append-only; historical evidence above is unchanged)

This implementation report was correct for its original snapshot, but two evidence statements are
now stale and must not be read as current-state claims:

1. **`to_thread` count:** the current `bot/attachments.py` contains **six** `to_thread` occurrences
   (module import, one docstring reference, and four `await anyio.to_thread.run_sync` call sites),
   not five. The current proposal/batch notices and `tests/test_doc_code_parity.py` assert six.
2. **`DEF-011-C`:** the current `ATTACHMENT_ACCEPTED_TEXT` explicitly states the file is stored
   locally and is **not uploaded to OpenHands**, and is emitted only after `AcceptOutcome.STORED`.
   The F-03 notices now mark `DEF-011-C` **IMPLEMENTED** (2026-11-22).

`DEF-011-A` (quota reservation ledger) remains **NOT IMPLEMENTED**; therefore `DEF-011` as a whole
remains **OPEN**. No historical sentence above was deleted or rewritten.
