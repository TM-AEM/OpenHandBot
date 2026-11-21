# DEF-011-A Option B — Immutable Review Handoff Package

**Task ID:** `OHB2-WP07-DEF011-A-PREPARE-IMMUTABLE-REVIEW-HANDOFF`
**Prepared:** 2026-11-21
**Repository:** `TM-AEM/OpenHandBot`
**Base revision:** `30dfa0d6432cdb8f7787edde38f48fb482b6ced6` (`origin/main`)

## Purpose and scope

This package transfers the **exact, uncommitted** DEF-011-A Option B candidate to an external reviewer so
that a genuinely independent technical review can be performed. It exists because the OpenHands environment
that produced the candidate exposes only one conversation/session and therefore cannot establish reviewer
independence.

**This package is packaging and evidence only. It is NOT an independent review and does NOT establish
reviewer independence.** Independence must come from the external reviewer's own separate session and
working environment.

## Candidate identity

The candidate is exactly four files (two modified, two new) relative to `30dfa0d`:

| # | Path | Status | Size (bytes) | SHA-256 |
|---|---|---|---|---|
| 1 | `bot/handlers.py` | modified | 183595 | `a2e3f16556fda6ec4e14badda2a3908dcdda56779882d344d2906d035563bd0c` |
| 2 | `bot/attachments.py` | modified | 100128 | `d31320afb4e39dd8cbbd09df45e6a755b24eeca149a115c7ff516a2ec4eb61d4` |
| 3 | `tests/test_def011_a_option_b_limits.py` | new | 17317 | `63a0033a4e5440ac0e762b77cc58f50da9aa09afa849e97c0d745c4cb795fb13` |
| 4 | `docs/audits/OHB2-WP07-DEF011-A-IMPLEMENTATION-REPORT.md` | new | 16790 | `682527029c3d6762d6ac0ae7227ca4fcd90e98520d23f1ddd4e7731b76952e22` |

The candidate is **not** on `origin/main`. It is reproduced by applying `candidate.patch` to a clean
checkout of `30dfa0d`.

## Package layout

```
docs/reviews/handoff/DEF011-A-OPTION-B/
├── README.md                      # this file
├── candidate.patch                # exact diff: 30dfa0d -> candidate (4 files only)
├── SHA256SUMS                     # hashes of packaged files (verify in this directory)
├── CANDIDATE-SHA256SUMS           # hashes of candidate source files (verify in the reconstructed clone)
├── CANDIDATE-MANIFEST.md          # changed-file list, sizes, hashes, provenance, diff stats
├── REVIEW-INSTRUCTIONS.md         # step-by-step external reviewer procedure
└── supporting/
    ├── OHB2-WP07-DEF011-A-DIAGNOSIS-AND-DECISION-BRIEF.md
    ├── OHB2-WP07-DEF011-A-IMPLEMENTATION-REPORT.md
    ├── OHB2-WP07-DEF011-A-INDEPENDENT-REVIEW-REPORT.md
    └── OHB2-WP07-DEF011-A-INDEPENDENT-REVIEW-RETRY-REPORT.md
```

## Quick reconstruction (full procedure in `REVIEW-INSTRUCTIONS.md`)

1. Use a **genuinely separate** reviewer session and environment.
2. `git clone https://github.com/TM-AEM/OpenHandBot.git`
3. `git checkout 30dfa0d` and verify `git rev-parse HEAD`.
4. From this package directory: `sha256sum -c SHA256SUMS`.
5. From the clone root: `git apply --check <package>/candidate.patch` then `git apply <package>/candidate.patch`.
6. From the clone root: `sha256sum -c <package>/CANDIDATE-SHA256SUMS`.
7. Confirm `git status --porcelain` shows exactly the four candidate files and no others.
8. Only then begin the independent technical review.

## Explicit limitations

- The candidate was **uncommitted** in the implementation workspace; this package is the immutable copy.
- The candidate patch contains **only** the four candidate files. Unrelated pre-existing workspace changes
  (the F-03 stale-reference correction in `docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md`
  and the pre-existing T-5 test in `tests/test_doc_code_parity.py`) are **excluded** from the patch.
- The previous review reports are included as historical context. Their independence was **not**
  established; they are not a substitute for this external review.
- The implementation report's test results are **historical implementation evidence**, not new independent
  verification.
- `DEF-011-A` remains pending genuine independent technical review. `DEF-011` as a whole remains open.
