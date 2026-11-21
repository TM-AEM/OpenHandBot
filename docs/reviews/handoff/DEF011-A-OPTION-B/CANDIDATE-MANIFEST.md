# DEF-011-A Option B — Candidate Manifest

**Task ID:** `OHB2-WP07-DEF011-A-PREPARE-IMMUTABLE-REVIEW-HANDOFF`
**Prepared:** 2026-11-21

## Revisions

| Item | Value |
|---|---|
| Repository | `TM-AEM/OpenHandBot` |
| Base revision | `30dfa0d6432cdb8f7787edde38f48fb482b6ced6` |
| `origin/main` at preparation | `30dfa0d6432cdb8f7787edde38f48fb482b6ced6` |
| Candidate location | uncommitted working-tree artifacts (not on `origin/main`) |
| Candidate patch | `candidate.patch` (in this package) |

## Exact changed-file list

| # | Path | Status | Size (bytes) | Candidate SHA-256 | Base SHA-256 |
|---|---|---|---|---|---|
| 1 | `bot/handlers.py` | modified | 183595 | `a2e3f16556fda6ec4e14badda2a3908dcdda56779882d344d2906d035563bd0c` | `40dd8902595c1a63875f8c9d37d4fed4a454be15e1390e5386dcfa9bce058014` |
| 2 | `bot/attachments.py` | modified | 100128 | `d31320afb4e39dd8cbbd09df45e6a755b24eeca149a115c7ff516a2ec4eb61d4` | `b98d561f0ba0ab27dea4e6bedee7955f68f1f6fa85a39fa81afe8aeb4d818356` |
| 3 | `tests/test_def011_a_option_b_limits.py` | new | 17317 | `63a0033a4e5440ac0e762b77cc58f50da9aa09afa849e97c0d745c4cb795fb13` | — (new) |
| 4 | `docs/audits/OHB2-WP07-DEF011-A-IMPLEMENTATION-REPORT.md` | new | 16790 | `682527029c3d6762d6ac0ae7227ca4fcd90e98520d23f1ddd4e7731b76952e22` | — (new) |

## Diff statistics

```
 bot/attachments.py | 15 ++++++++++-----
 bot/handlers.py    | 19 +++++++++++++++++--
 2 files changed, 27 insertions(+), 7 deletions(-)
```

Plus two new files (`tests/test_def011_a_option_b_limits.py`,
`docs/audits/OHB2-WP07-DEF011-A-IMPLEMENTATION-REPORT.md`).

- `bot/handlers.py`: +17 / −2 (production wiring in `_attachment_service`).
- `bot/attachments.py`: +10 / −5 (docstrings/comments only; no executable change).

## Candidate provenance and verification

- The candidate was produced in the implementation workspace as **uncommitted** changes on top of
  `30dfa0d`. It was **not** committed or pushed.
- `candidate.patch` was generated against `30dfa0d`:
  - modified files: `git diff 30dfa0d -- bot/handlers.py bot/attachments.py`
  - new files: `git diff --no-index /dev/null <path>` for each new file
- The patch contains **only** the four candidate files (verified by inspecting every `diff --git` header).
- The patch was verified in a **fresh clone** of `TM-AEM/OpenHandBot` at `30dfa0d`:
  - `git apply --check candidate.patch` → **OK**
  - `git apply candidate.patch` → applied
  - reconstructed `git status --porcelain` → exactly the four candidate files
  - reconstructed SHA-256 → **all four match** the candidate hashes above
- The candidate hashes are identical to those recorded by the earlier (non-independent) review, so the
  artifact identity is stable.

## Unrelated pre-existing changes (excluded from the patch)

The implementation workspace also contained unrelated changes that are **not** part of this candidate and
are **not** in `candidate.patch`:

| Path | Change | Why excluded |
|---|---|---|
| `docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md` | +14/0 | pre-existing F-03 stale-reference correction |
| `tests/test_doc_code_parity.py` | +32/0 | pre-existing T-5 test |
| `docs/audits/OHB2-WP07-DEF011-F03-STALE-REFERENCE-CORRECTION-REPORT.md` | untracked | pre-existing F-03 artifact |
| `docs/reviews/OHB2-WP07-DEF011-F03-GENUINELY-INDEPENDENT-REVIEW-REPORT.md` | untracked | pre-existing F-03 artifact |
| `docs/audits/OHB2-WP07-DEF011-A-DIAGNOSIS-AND-DECISION-BRIEF.md` | untracked | diagnosis (included as a supporting copy, not in the patch) |

## Supporting reports (copied, originals untouched)

| Original path | Packaged copy | SHA-256 |
|---|---|---|
| `docs/audits/OHB2-WP07-DEF011-A-DIAGNOSIS-AND-DECISION-BRIEF.md` | `supporting/OHB2-WP07-DEF011-A-DIAGNOSIS-AND-DECISION-BRIEF.md` | `1b6e354b87ac4d4e32c6da71ad0c9e0efa33626ee90b7583ea95339f57fd508e` |
| `docs/audits/OHB2-WP07-DEF011-A-IMPLEMENTATION-REPORT.md` | `supporting/OHB2-WP07-DEF011-A-IMPLEMENTATION-REPORT.md` | `682527029c3d6762d6ac0ae7227ca4fcd90e98520d23f1ddd4e7731b76952e22` |
| `docs/reviews/OHB2-WP07-DEF011-A-INDEPENDENT-REVIEW-REPORT.md` | `supporting/OHB2-WP07-DEF011-A-INDEPENDENT-REVIEW-REPORT.md` | `2bf4faa5d927f4f1dddcdf957f3f72a72dffed8fed5cc74854be66ac05bbc0cc` |
| `docs/reviews/OHB2-WP07-DEF011-A-INDEPENDENT-REVIEW-RETRY-REPORT.md` | `supporting/OHB2-WP07-DEF011-A-INDEPENDENT-REVIEW-RETRY-REPORT.md` | `5ac7ad736896468292cf018c49dd4e93666ce6c90ff32332c984b27724b94a9a` |

All four originals exist and were copied without modification; each copy's hash matches its original.

## Integrity files

- `SHA256SUMS` — hashes of all **packaged** files (verify from this directory with `sha256sum -c SHA256SUMS`).
- `CANDIDATE-SHA256SUMS` — hashes of the four **candidate source files** at their clone-relative paths
  (verify from the reconstructed clone root with `sha256sum -c <package>/CANDIDATE-SHA256SUMS`).

`SHA256SUMS` cannot include itself; it covers every other packaged file.

## Scope confirmation

- No production code or tests were modified by the packaging task.
- No owner decision record was modified.
- No commit, push, PR, merge, deployment, or Autopush activation occurred.
- `DEF-011-A` remains pending genuine independent technical review; `DEF-011` remains open.
