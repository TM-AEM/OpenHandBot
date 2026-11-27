# OHB2-R7 WP-03 / D-05 — Reconstruction Gap Resolution Plan

**Task ID:** `OHB2-R7-WP03-D05-RECONSTRUCTION-GAP-RESOLUTION-PLAN`
**Date:** 2026-11-27
**Mode:** PLAN-ONLY / READ-ONLY
**Verdict:** `PARTIAL_PLAN`
**FIND-02 status:** `NOT_MODIFIED`

## 1. Baseline and artifact integrity verification

### 1.1 Source repository

| Item | Current value |
|---|---|
| Repository | `/workspace/project/OpenHandBot` |
| Branch | `agent/r6-review-delivery` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` |
| HEAD tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| `main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `origin/main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| Tracked modified | 12 pre-existing |
| Untracked before this report | 90 |
| `bot/review` tracked | 0 |
| `tests/test_review_*` tracked | 0 |

The source working tree was not modified. No reset, clean, stash, checkout, branch
switch, staging, commit, push, fetch, or pull was performed.

### 1.2 Prior reconstruction report

`docs/reviews/OHB2-R7-WP03-D05-CLEAN-RECONSTRUCTION-REPORT-20261127.md`

- SHA-256: `fe6ad93de099268107d7126e3c748596df0df1808b6cea91a9c55dcf79da5995`
- Verdict: `PARTIAL_RECONSTRUCTION`

### 1.3 Isolated reconstruction artifact

The previous report recorded:

```text
/tmp/ohb2-d05-recon-RgO1Cr
```

At this audit that path **does not exist**:

```text
ls: cannot access '/tmp/ohb2-d05-recon-RgO1Cr': No such file or directory
ls: cannot access '/tmp/ohb2-d05-recon-path': No such file or directory
```

Therefore the reconstructed files and `reconstruction_manifest.json` from the previous
task cannot be re-hashed or revalidated. This is a **reconstruction-artifact integrity
gap**. It is not evidence that the recorded hashes were wrong; it means the temporary
artifact is no longer available for direct verification.

The prior report and event-store evidence remain available. No new reconstruction
environment was created in this plan-only task.

## 2. Exact byte-level analysis of the unexplained blank line

### 2.1 The prior reconstruction omitted a heredoc newline

Event `07581` writes the D-05 test with:

```text
cat > tests/test_review_d05_rename_transfer.py <<'PY'
...
PY
```

The event command's heredoc body ends with:

```text
    assert_no_review_rows(db)
```

and the terminating newline before `PY` is part of the file written by `cat`.

The previous reconstruction extracted the body with a regex that stopped before the
final newline. Its recorded baseline body hash was:

```text
74f9a80fe01dd541a3d25c86ec7115e5735736193ba13fe34e82a200a19e80da
```

The same body plus the actual trailing newline hashes to:

```text
ea4b43bc1ea3678acaffe227fc34efbce647b8953001db7738845f2eef434b52
```

### 2.2 Why this creates exactly one blank line

Event `07593` appends:

```text
s += '''

def test_api_error_after_pr_reads_fails_closed(tmp_path):
...
'''
```

- With the real trailing newline before the append, the result is
  `...db)\n\n\ndef ...` — two blank lines.
- With the omitted newline, the result is
  `...db)\n\ndef ...` — one blank line.

That is exactly the byte-level difference observed between the prior reconstructed
`fe1801f4...` and the current `fe85d728...`.

### 2.3 Event-derived final hash

Replaying event 07581 with the trailing newline and then events 07589, 07593, and
07597 **in memory, without writing any file**, gives:

| Content | SHA-256 | Lines |
|---|---|---|
| Event-derived D-05 test with correct heredoc newline | `00139e481ca33720fafb02e074be6fe917ca56bb6c5e4d5323155fdb46e2bf5d` | 316 |

Applying later D-06 event `07749` (`private: False` -> `True`) in memory gives:

```text
fe85d72831106b558772cbcb445e7ec8669785f0851c1b6069796c2d605dfde8
```

which is exactly the current working-tree hash.

### 2.4 Conclusion

The blank-line discrepancy is **EXPLAINED**:

- It is a prior reconstruction extraction error, not missing event evidence.
- The actual event-derived D-05 final content is `00139e48...`.
- The current `fe85d728...` is that content plus the later D-06 `private=True` change.
- `ed45c74b...` was the hash of the **terminal command**, not the file.
- No whitespace was normalized and no file was edited.

## 3. Shared dependency inventory and provenance

### 3.1 Direct and transitive imports

`tests/test_review_d05_rename_transfer.py` imports:

- `bot.review.github` — D05 reconstructed, hash-verified.
- `bot.review.resolver` — D05 reconstructed, hash-verified.
- `tests.test_review_resolver` — reconstructed, but no final hash and 23 pyflakes
  findings.

`tests/test_review_resolver.py` imports:

- `bot.db.AutoReviewMembership`, `bot.db.Database`
- `bot.review.ci_contract.jobs_complete`
- `bot.review.collector.EvidenceCollectionError`, `GitHubEvidenceCollector`
- `bot.review.evidence.ReviewEvidence`, `StageEvidenceValidation`
- `bot.review.github`
- `bot.review.resolver`
- `bot.review.verdict`

`tests/test_review_canary_linkage.py` additionally imports:

- `bot.db.Database`
- `bot.review.canary_linkage.CANARY_SOURCE`, `CreationJobRepositoryLinkSource`,
  `CanaryLinkageService`
- `bot.review.github`
- `bot.review.resolver`
- `tests.test_review_resolver`

### 3.2 Dependency classification

| Dependency | Used by D-05 tests | In clean HEAD? | Current state / hash | D-05 edits? | Historical snapshot evidence | Classification |
|---|---|---|---|---|---|---|
| `bot/review/collector.py` | `test_review_resolver.py` | No | untracked `eaeb4f87...` | No D-05 edit in D05 trace | Event history has R3/R5 edits; current also has D-06 edit `07745`; no verified pre-D05 snapshot | **PROVENANCE_UNRESOLVED** |
| `bot/review/evidence.py` | `test_review_resolver.py`, `verdict.py` | No | untracked `6cd287b8...` | No | Many earlier R3/R4 events; no verified final pre-D05 snapshot | **PROVENANCE_UNRESOLVED** |
| `bot/review/verdict.py` | `test_review_resolver.py` | No | untracked `3f1ff3b0...` | No | Earlier R4 events; no verified final pre-D05 snapshot | **PROVENANCE_UNRESOLVED** |
| `bot/review/ci_contract.py` | `test_review_resolver.py`, `collector.py` | No | untracked `5f327503...` | No | Earlier R3/R7 events; no verified final pre-D05 snapshot | **PROVENANCE_UNRESOLVED** |
| `bot/review/eligibility.py` | Not imported by D-05 final resolver; current later code uses it | No | untracked `e2953557...` | No; D-06 created/used it | D-06 event `07737`/`07741`; not D-05 | **NOT_PART_OF_D05** |
| `bot/db.py` | `test_review_resolver.py`, canary test | **Yes**, but HEAD version lacks `AutoReview*` classes and reservation APIs | tracked modified `91b9e028...`; HEAD `18c350ec...` | No D-05-specific edit | Many R5/D-05-support edits; no verified pre-D05 snapshot | **PROVENANCE_UNRESOLVED / SHARED** |
| `bot/review/canary_linkage.py` | canary test | No | untracked `c1797053...` | No D-05 edit | D-01 B/D-02 events; no verified D-05 baseline | **PROVENANCE_UNRESOLVED / SHARED** |
| `bot/review/github.py` | all focused tests | No | current mixed `8ec64cc2...`; D05 reconstruction `a6274844...` | Yes, reconstructed | Event 07485 baseline + 07483/07487/07491 | **D05_RECONSTRUCTED_HASH_VERIFIED** |
| `bot/review/resolver.py` | all focused tests | No | current mixed `74198472...`; D05 reconstruction `967cbe1d...` | Yes, reconstructed | Event 07505 baseline + 07503/07507/07515/07519/07523/07527 | **D05_RECONSTRUCTED_HASH_VERIFIED** |
| `tests/test_review_resolver.py` | D-05 and canary tests | No | reconstructed `30dded74...`; current `b7e6fac1...` | D-05 `07535` pair 0 | Event 07461 baseline | **D05_ONLY_VERIFIED** (no final hash) |
| `tests/test_review_canary_linkage.py` | canary test | No | reconstructed/current `b44b6248...` | D-05 `07543`, `07555` | Event 07545 baseline | **D05_RECONSTRUCTED_HASH_VERIFIED** |
| `tests/test_review_github.py` | not required for D-05 focused tests | No | current `c9709562...` | No D-05 edit | R3 tests | **NOT_PART_OF_D05** |

**Verified shared dependencies:** 0 of 6 shared production/test dependencies.
**Unresolved shared dependencies:** 6 (`collector`, `evidence`, `verdict`,
`ci_contract`, `bot/db.py`, `canary_linkage`).

The current `bot/db.py` is especially important: HEAD has no `AutoReviewMembership`,
`AutoReviewReservation`, or `reserve_conversation_review`; the current modified file has
them. D-05 tests cannot run against HEAD's DB module. The current file is a mixed
R5/D-05-support state, not a verified D-05 baseline.

## 4. Analysis of the 23 pyflakes findings

The reconstructed `tests/test_review_resolver.py` had 23 unused-import findings. The
D-05 operation `07535` pair 0 only changes a call expectation list; it does not add or
remove imports. The imports therefore come from the pre-D05 baseline read at event
07461.

| Group | Imports / finding | Origin | D-05-introduced? |
|---|---|---|---|
| 1 | `httpx` | event 07461 baseline | No |
| 2 | `AutoReviewMembership` | baseline | No |
| 3 | `jobs_complete` | baseline | No |
| 4-5 | `EvidenceCollectionError`, `GitHubEvidenceCollector` | baseline | No |
| 6-7 | `ReviewEvidence`, `StageEvidenceValidation` | baseline | No |
| 8-15 | `GitHubClient`, `GitHubMalformedResponse`, `GitHubRepoNotAllowed`, `GitHubTransportError`, `WorkflowJob`, `WorkflowJobsEvidence`, `WorkflowRun`, `WorkflowRunsEvidence` | baseline | No |
| 16-21 | `DUPLICATE_PR_MEMBERSHIP`, `GITHUB_UNAVAILABLE`, `MALFORMED_EXTERNAL_RESPONSE`, `REPOSITORY_NOT_ALLOWED`, `ResolutionResult`, `reserve_resolved_memberships` | baseline | No |
| 22-23 | `VERDICT_BLOCKED`, `evaluate_verdict` | baseline | No |

All 23 are **inherited from the pre-D05 baseline**, not introduced by D-05. The current
`tests/test_review_resolver.py` has no pyflakes findings, but it is a later D-06 state and
is not the D-05 reconstruction. Removing imports from the reconstructed file would alter
D-05 content and provenance; it must not be done in this plan-only task.

## 5. Minimum safe test dependency graph

### 5.1 D-05 focused test

```text
tests/test_review_d05_rename_transfer.py
  -> bot/review/github.py             [D05_RECONSTRUCTED_HASH_VERIFIED]
  -> bot/review/resolver.py           [D05_RECONSTRUCTED_HASH_VERIFIED]
  -> tests/test_review_resolver.py    [D05_ONLY_VERIFIED, no final hash]
       -> bot/db.py                   [PROVENANCE_UNRESOLVED / SHARED]
       -> bot/review/ci_contract.py   [PROVENANCE_UNRESOLVED]
       -> bot/review/collector.py     [PROVENANCE_UNRESOLVED]
       -> bot/review/evidence.py      [PROVENANCE_UNRESOLVED]
       -> bot/review/verdict.py       [PROVENANCE_UNRESOLVED]
       -> bot/review/github.py        [verified]
       -> bot/review/resolver.py      [verified]
```

### 5.2 Resolver tests

Same as above; no additional verified dependency is available.

### 5.3 Canary-linkage tests

```text
tests/test_review_canary_linkage.py
  -> bot/db.py                        [PROVENANCE_UNRESOLVED / SHARED]
  -> bot/review/canary_linkage.py     [PROVENANCE_UNRESOLVED / SHARED]
  -> bot/review/github.py             [verified]
  -> bot/review/resolver.py           [verified]
  -> tests/test_review_resolver.py    [D05_ONLY_VERIFIED, no final hash]
```

### 5.4 Safe environment conclusion

A complete focused-test environment **cannot be assembled safely from verified evidence
alone**. The missing/unsafe links are:

- `bot/db.py` — HEAD lacks the required AutoReview schema/APIs; current is modified and
  unverified.
- `bot/review/collector.py`, `evidence.py`, `verdict.py`, `ci_contract.py` — untracked,
  current mixed; no verified pre-D05 snapshot.
- `bot/review/canary_linkage.py` — untracked D-01 B/D-02 implementation; not D-05.
- `tests/test_review_resolver.py` — reconstructed but no final-hash proof.

No tests were run by copying these dependencies.

## 6. Files that can and cannot be safely reconstructed

### Can be safely reconstructed

- `bot/review/github.py` — D-05 hash verified.
- `bot/review/resolver.py` — D-05 hash verified.
- `tests/test_review_canary_linkage.py` — D-05 hash verified.
- `tests/test_review_d05_rename_transfer.py` — event-derived final with correct heredoc
  newline is `00139e48...`; current is later D-06 state.
- `tests/test_review_resolver.py` — D-05 operation reconstructed; no final-hash proof.

### Cannot yet be reconstructed safely

- `bot/db.py` — no verified pre-D05 snapshot with the required AutoReview APIs.
- `bot/review/collector.py`, `evidence.py`, `verdict.py`, `ci_contract.py` — no verified
  pre-D05 snapshots.
- `bot/review/canary_linkage.py` — D-01 B/D-02, not D-05; current untracked state.
- `bot/review/eligibility.py` — D-06; not part of D-05 final resolver imports.
- Other shared modules/tests with no D-05 event evidence.

## 7. Remaining evidence gaps

1. The isolated `/tmp/ohb2-d05-recon-RgO1Cr` environment and its manifest are gone;
   direct revalidation of its files is impossible.
2. Shared dependency snapshots for the focused tests are not verified.
3. `tests/test_review_resolver.py` has no recorded final hash and retains 23 baseline
   unused imports.
4. The current D-05 test is later D-06 state; only the event-derived `00139e48...` is
   the correct D-05 final content.
5. No standalone Git patch/commit exists; event store has no signed manifest.

## 8. Sequenced remediation-free reconstruction plan

1. **Recreate the isolated environment** from the exact baseline commit under a new
   temporary path; record HEAD/tree; do not touch the source working tree.
2. **Correct the D-05 test extraction**: include the heredoc's terminating newline;
   replay 07589/07593/07597; verify `00139e48...` (316 lines).
3. **Reconstruct `tests/test_review_resolver.py`** from event 07461 baseline plus 07535
   pair 0; record actual `30dded74...` and the 23 baseline pyflakes findings; do not
   "fix" them in the reconstruction.
4. **Recover shared dependency snapshots** from event history, one at a time:
   - `bot/db.py`
   - `bot/review/collector.py`
   - `bot/review/evidence.py`
   - `bot/review/verdict.py`
   - `bot/review/ci_contract.py`
   - `bot/review/canary_linkage.py`
   Each must have an exact baseline event/snapshot and a recorded hash; current mixed
   files must not be copied.
5. **Assemble the minimum environment** only after all required dependencies are
   verified; run the focused D-05, resolver, and canary tests; distinguish fresh results
   from historical claims.
6. **Independent re-verification** of the isolated D-05 change set.
7. Only after that, consider FIND-02 remediation; this task does not authorize it.

## 9. Authorization requirements for later work

A separate explicit authorization is required to:

- Recreate the isolated reconstruction environment.
- Correct the heredoc extraction or add the missing newline in a reconstruction copy.
- Reconstruct any shared dependency (`bot/db.py`, collector, evidence, verdict,
  ci_contract, canary_linkage).
- Remove or change pyflakes findings.
- Run focused tests against reconstructed files.
- Modify any current working-tree file.
- Start FIND-02 remediation or any WP-04/WP-05/WP-06 work.

This plan does not grant any of those permissions.

## 10. Safety confirmation

- **FIND-02 was not touched** and no remediation was performed.
- No application code, tests, configuration, schema, migration, existing report, or
  `.agent/PROGRESS.md` was modified in the existing working tree.
- No reconstructed file was modified; the blank-line analysis was performed in memory.
- No application DB was opened.
- No GitHub/OpenHands/Telegram/Canary/provider API was called.
- No branch, worktree, staging, commit, push, PR, merge, deployment, release, fetch, or
  pull occurred.
- Autopush remained disabled/inactive.
- The only file created by this task is this report.
