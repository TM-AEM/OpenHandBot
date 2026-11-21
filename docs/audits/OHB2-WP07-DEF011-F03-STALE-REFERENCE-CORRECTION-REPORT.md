# OHB2 — WP-07 / DEF-011 / F-03 — Stale Reference Correction Report

**Task:** `OHB2-WP07-DEF011-F03-REMAINING-STALE-REFERENCE-CORRECTION`
**Date:** 2026-11-21
**Scope:** correct the last stale historical F-03 status reference; documentation only.

---

## 1. Verdict

# `DONE`

The remaining stale F-03 reference in
`docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md` is now corrected by an **additive,
dated notice**; the original historical row is preserved **unchanged**. A focused regression test
(`T-5`) guards the notice and the preserved historical row. Full suite: **3451 passed / 0 failed**.

**`DEF-011` as a whole remains OPEN.** `DEF-011-A` and `DEF-011-C` remain NOT IMPLEMENTED; `D6` remains
deferred. This task closes **only** the stale-reference correction; it does not reopen F-03.

---

## 2. Baseline and source verification (Phase 1)

| Item | Value |
|---|---|
| Branch | `openhands-workspace-11yyMvqKPjTrIZt1RRpWq9` |
| `HEAD` | `30dfa0d6432cdb8f7787edde38f48fb482b6ced6` |
| `origin/main` | `30dfa0d…` (in sync) |
| Pre-existing tracked modifications | **none** |
| Pre-existing untracked | `docs/reviews/OHB2-WP07-DEF011-F03-GENUINELY-INDEPENDENT-REVIEW-REPORT.md` (from the prior review task; **preserved**) |

### 2.1 Exact stale statement

Located at **line 300** of
`docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md` (inside §9 "Explicit outstanding
findings"). The line number was re-checked live, not assumed:

```
| **F-03** (stale acceptance doc claiming "0 `to_thread`") | **OPEN / NOT FIXED** | Batch-03 DOC-01; not part of this task. |
```

### 2.2 Independent-review evidence (verified live)

`docs/reviews/OHB2-WP07-DEF011-F03-GENUINELY-INDEPENDENT-REVIEW-REPORT.md` exists and its §1 verdict is:

```
# `F03_REVIEW_PASS`
```

with the explicit statement: "This closes the F-03 documentation defect only. `DEF-011` as a whole
remains **open**." That report also records independence as established (separate conversation, fresh
clone from origin, HEAD `30dfa0d`).

### 2.3 Existing correction notices and tests (verified live)

- Proposal notice: `docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md` — dated
  `LATER CORRECTION — 2026-11-21` blockquote (append-only).
- Batch-report notice: `docs/reviews/OHB2-WP07-FINAL-STABILIZATION-BATCH-REPORT.md` — dated
  `LATER CORRECTION — 2026-11-21` blockquote.
- Tests: `tests/test_doc_code_parity.py` — `T-1`…`T-4` (7 test functions), constants `PROPOSAL`,
  `BATCH_REPORT`, `CORRECTION_MARKER`, `F03_DATE`, and helper `_correction_notice(text)`.

The new notice mirrors that established style and reuses the existing helper.

---

## 3. Minimal correction (Phase 2)

An additive blockquote was inserted **immediately after the §9 findings table** (adjacent to the stale
F-03 row), before the "Unchanged blockers carried forward" paragraph. It does not modify any historical
line.

**Correction text added (14 lines, all additive):**

```
> **⚠ LATER CORRECTION — 2026-11-21 (append-only; the historical F-03 row above is unchanged).**
> The **F-03** row above ("**OPEN / NOT FIXED**") was accurate when this report was written on
> **2026-11-19**; it is now **SUPERSEDED**. F-03 (the stale acceptance documents claiming
> "0 `to_thread`") was subsequently corrected with dated, additive supersession notices and guarded by
> parity tests, and it then passed a **genuinely independent review** with the verdict
> **`F03_REVIEW_PASS`** — see
> `docs/reviews/OHB2-WP07-DEF011-F03-GENUINELY-INDEPENDENT-REVIEW-REPORT.md`.
>
> This correction closes **only the F-03 documentation remediation**; it does not close `DEF-011`.
> **`DEF-011` as a whole remains OPEN.** `DEF-011-A` (quota reservation ledger) and `DEF-011-C`
> (attachment acceptance UX copy) remain **NOT IMPLEMENTED**, and `D6` (repeated raw cancellation during
> drain) remains **deferred**. The historical F-03 row is preserved unchanged above as a historical
> record.
```

The notice satisfies every required element:

| Requirement | Where in the notice |
|---|---|
| Historical statement was accurate at the time, now superseded | "was accurate … on **2026-11-19**; it is now **SUPERSEDED**" |
| Records the verdict `F03_REVIEW_PASS` | "verdict **`F03_REVIEW_PASS`**" |
| References the exact independent-review report path | `` `docs/reviews/OHB2-WP07-DEF011-F03-GENUINELY-INDEPENDENT-REVIEW-REPORT.md` `` |
| Closes only F-03 documentation remediation | "closes **only the F-03 documentation remediation**" |
| `DEF-011` as a whole remains OPEN | "**`DEF-011` as a whole remains OPEN.**" |
| Original historical statement preserved | "historical F-03 row is preserved unchanged above" |

### 3.1 Original historical wording preserved

The line-300 row is **unchanged**. The git diff shows it as an unchanged context line, and the total
diff has **0 deletions**:

```
$ git diff --numstat
14	0	docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md
32	0	tests/test_doc_code_parity.py
```

```
$ git diff | grep -cE '^-[^-]'
0
```

---

## 4. Regression protection (Phase 3)

Existing `T-1`…`T-4` cover the proposal and batch report only; **none** covered this third document.
So one focused test was added (not a duplicate): `T-5`.

**Test file change (32 additive lines, 0 deletions):**

- New constant:
  ```python
  F01_REPORT = (
      ROOT / "docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md"
  ).read_text(encoding="utf-8")
  ```
- New test `test_t5_batch04_f01_report_correction_notice`, which asserts:
  1. the dated notice is present (`F03_DATE in notice`);
  2. it records the verdict (`"F03_REVIEW_PASS" in notice`);
  3. it names the exact independent-review report path;
  4. the historical F-03 row is still present **verbatim** (not silently deleted);
  5. the notice does **not** falsely close `DEF-011` (`"remains open"` and `"not close"` present).

It reuses the existing `_correction_notice()` helper; no new infrastructure.

### 4.1 Non-vacuity proof (mutations on a scratch copy, live repo untouched)

| Mutation | Expected | Observed |
|---|---|---|
| Control (unmodified) | pass | **1 passed** |
| **MUT-A**: delete the inserted notice | fail | **FAILED** — `ValueError: substring not found` (marker gone) |
| **MUT-B**: delete the historical F-03 row | fail | **FAILED** — `AssertionError` (historical line missing) |
| Restore | pass | **1 passed** |

So `T-5` genuinely fails if either the notice is removed or the historical row is deleted.

---

## 5. Verification (Phase 4) — actual commands and results

| Check | Command | Result | Exit |
|---|---|---|---|
| Focused parity tests | `python3 -m pytest tests/test_doc_code_parity.py -v` | **14 passed** (13 prior + `T-5`) | 0 |
| Full Python suite | `python3 -m pytest -q` | **3451 passed, 0 failed**, 74 warnings | 0 |
| pyflakes | `python3 -m pyflakes bot/ automation/ tools/ main.py tests/` | no output | 0 |
| bandit (high only) | `python3 -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | severity **High: 0** (Low 5, Medium 19) | 0 |
| Frontend Node | `node --test tests/frontend/*.test.js` | **pass 280, fail 0** | 0 |

Full-suite delta vs the previous task's baseline: **3450 → 3451 (+1)**, exactly the one new test `T-5`;
no other test changed state.

### 5.1 Final diff verification

```
$ git status --porcelain=v1
 M docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md
 M tests/test_doc_code_parity.py
?? docs/reviews/OHB2-WP07-DEF011-F03-GENUINELY-INDEPENDENT-REVIEW-REPORT.md
```

- The **target historical report is the only documentation file changed.**
- The **only test change** is the `T-5` addition in `tests/test_doc_code_parity.py`.
- The untracked independent-review report is **preserved**, not modified.
- **0 deletions** anywhere; no unrelated change was overwritten.
- No code/implementation file changed; no other DEF-011 finding or architectural decision modified.

---

## 6. Remaining DEF-011 status and open findings

| Item | Status | Evidence |
|---|---|---|
| `DEF-011-B` (filesystem offload) | **IMPLEMENTED** | 5 `to_thread` occurrences in `bot/attachments.py`; handlers offload |
| `DEF-011-A` (quota reservation ledger) | **NOT IMPLEMENTED** | 0 `reserv|in_flight|_ledger` tokens in `bot/attachments.py` |
| `DEF-011-C` (attachment UX copy) | **NOT IMPLEMENTED** | Owned by WP-01 (OD-01 / OD-03); no such change |
| `D6` (repeated raw cancellation during drain) | **DEFERRED** | Documented deferred in `bot/attachments.py` |
| **`DEF-011` as a whole** | **OPEN** | A and C unimplemented |

Out of scope and deliberately untouched: the `F-02` row and all other rows in the target historical
report; the two corrected F-03 documents; `bot/*`; any DEF-011 sub-finding.

---

## 7. Git state and limitations

- **Git state:** branch `openhands-workspace-11yyMvqKPjTrIZt1RRpWq9`, HEAD `30dfa0d` (unchanged).
  2 modified files, 1 pre-existing untracked file preserved. **No commit, push, PR, merge, deployment,
  or Autopush activation.** No `git add .` / `git add -A`. No reset/clean/force.
- **Not committed:** the correction exists in the working tree only (consistent with the no-publish
  rule for this task).
- **Scope limitation:** this task corrected the single F-03 reference; it did not re-audit other
  present-tense claims in the target document.
- **Environment:** verification used Python 3.13.15 with the repo's pinned dev deps installed
  system-wide; `git` is on `PATH`. The full suite requires those preconditions (the isolated-import
  deploy test disables user-site, so a `--user` install would fail it).

---

## 8. Changed files

| File | Change | Lines |
|---|---|---|
| `docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md` | Added dated correction notice in §9 (adjacent to the F-03 row) | **+14 / −0** |
| `tests/test_doc_code_parity.py` | Added `F01_REPORT` constant + `T-5` regression test | **+32 / −0** |
| `docs/audits/OHB2-WP07-DEF011-F03-STALE-REFERENCE-CORRECTION-REPORT.md` | This report | new |

---

## 9. Final report (AGENTS.md format)

- **Status:** **DONE**
- **Acceptance criteria:**
  1. Stale F-03 status corrected by additive dated notice — **MET** (§3).
  2. Historical statement unchanged — **MET** (§3.1; 0 deletions).
  3. Independent-review evidence referenced accurately — **MET** (§2.2, §3).
  4. `DEF-011` OPEN; A/C open; D6 deferred — **MET** (§6).
  5. Focused regression protection added (not duplicated) — **MET** (§4).
  6. Verification supported by actual output — **MET** (§5).
  7. No unrelated files/pre-existing changes disturbed — **MET** (§5.1).
- **Changes:** see §8.
- **Verification:** focused 14 passed; full 3451 passed/0 failed; pyflakes 0; bandit High 0; node 280/0;
  `T-5` mutation-proven non-vacuous.
- **Not verified / not implemented:** `DEF-011-A`, `DEF-011-C`, `D6` remain unimplemented (out of
  scope); no 3.11 run in this task (3.13 only).
- **Assumptions:** stayed on the current workspace branch (no new branch, no commit) because the task
  forbids publish actions and asks to preserve workspace state; did not update `.agent/PROGRESS.md` to
  keep the change narrowly scoped to the two intended files + this report.
- **Branch and commits:** `openhands-workspace-11yyMvqKPjTrIZt1RRpWq9` at `30dfa0d`; no commit.
- **Suggested next step:** if the owner wants the correction durable, commit these two files (plus this
  report) in a scoped docs-only commit — a separate, explicit action.
