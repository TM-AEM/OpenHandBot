# OHB2-R7 WP-03 / D-05 — Dependency Reconstruction Report

**Task ID:** `OHB2-R7-WP03-D05-DEPENDENCY-RECONSTRUCTION`
**Date:** 2026-11-27
**Verdict:** `BLOCKED_PROVENANCE`
**FIND-02 status:** `NOT_MODIFIED`

## 1. Baseline verification

### 1.1 Source repository

| Item | Value |
|---|---|
| Repository | `/workspace/project/OpenHandBot` |
| Branch | `agent/r6-review-delivery` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` |
| HEAD tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| `main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `origin/main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| Tracked modified | 12 pre-existing |
| Untracked before this report | 91 |
| `bot/review` tracked | 0 |
| `tests/test_review_*` tracked | 0 |

The original working tree was not modified. No reset, clean, stash, checkout,
branch switch, staging, commit, push, PR, merge, deployment, release, or fetch was
performed.

### 1.2 Isolated environment

A new, uniquely named environment was created:

```text
/tmp/ohb2-d05-deps-wUxVNK
```

Creation method:

```text
git clone --no-hardlinks --no-checkout /workspace/project/OpenHandBot \
  /tmp/ohb2-d05-deps-wUxVNK
git -C /tmp/ohb2-d05-deps-wUxVNK checkout --detach \
  01079676351aac869d09d4d1747661cd6f07d82b
```

Verified:

| Item | Value |
|---|---|
| Isolated HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` |
| Isolated tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| Initial status | clean (0 entries) |
| Source tree modified | no |
| Branch created in source | no |
| Staging/commit in source | no |

The previous `/tmp/ohb2-d05-recon-RgO1Cr` environment was absent and was not reused.
No unrelated temporary directory was deleted.

## 2. D-05 source reconstruction

The five identified D-05 files were reconstructed from the event trace, preserving exact
newlines.

| File | Baseline source | Applied events | Actual SHA-256 | Expected SHA-256 | Match |
|---|---|---|---|---|---|
| `bot/review/github.py` | event 07485 `old_content` | 07483, 07487, 07491 | `a6274844a624ce45fd5788b648a25a4b59b16853458e06d900016badca21e1f6` | same | **YES** |
| `bot/review/resolver.py` | event 07505 `old_content` | 07503, 07507, 07515, 07519, 07523, 07527 | `967cbe1dd13184b30c35b28e653bb0a26e0f7a5cfb1dd1e4a93ea5e692bab6c6` | same | **YES** |
| `tests/test_review_canary_linkage.py` | event 07545 `old_content` | 07543, 07555 | `b44b6248b047657bc7e82b5bb786f31348a65a2b7da675ebfa79a26a056f7b53` | same | **YES** |
| `tests/test_review_d05_rename_transfer.py` | event 07581 heredoc body **plus final newline** | 07589, 07593, 07597 | `00139e481ca33720fafb02e074be6fe917ca56bb6c5e4d5323155fdb46e2bf5d` | same | **YES** |
| `tests/test_review_resolver.py` | event 07461 content | 07535 pair 0 | `30dded749e14a22a83ed56552ce6a7a646255599d269ca935bc92c239f59da73` | none recorded | **NO FINAL-HASH PROOF** |

### 2.1 Event references

- D-05 task prompt: `event-07431-89a903b3-2b51-4399-80ca-0e1636056c5e.json`,
  SHA-256 `9fd288165094285824fb24820f7465ad123286124371073fdc6ebe4605f8dfcf`.
- `github.py`: `event-07483`, `event-07487`, `event-07491`.
- `resolver.py`: `event-07503`, `event-07507`, `event-07515`, `event-07519`,
  `event-07523`, `event-07527`; `event-07495` excluded as failed/no-op.
- Canary test: `event-07543`, `event-07555`; `event-07535` canary pairs and
  `event-07547` excluded as failed/no-persisted changes.
- Resolver test: `event-07461` baseline and `event-07535` pair 0.
- D-05 rename test: `event-07581` baseline plus final newline, then `event-07589`,
  `event-07593`, `event-07597`.
- D-06 `event-07749` (`private=False` -> `True`) was **not** included.

### 2.2 Newline and D-05 test discrepancy

The prior `fe1801f4...` reconstruction omitted the newline written by the heredoc at
event 07581. The correct event-derived D-05 content is:

```text
00139e481ca33720fafb02e074be6fe917ca56bb6c5e4d5323155fdb46e2bf5d
```

The current working-tree file is `fe85d728...`, which is the correct D-05 content plus
D-06 event 07749 (`private=True`). The current file is not the D-05 baseline.

## 3. Dependency provenance investigation

No current mixed-provenance dependency was copied into the isolated environment.
No dependency was reconstructed because no reliable pre-D05 full-file snapshot was found.

| Dependency | Earliest supported write | Latest pre-D05 write | Post-D05 write | Current SHA-256 | Classification | Reason |
|---|---|---|---|---|---|---|
| `bot/review/collector.py` | 2026-11-25T03:17:18 event-02690 | same event-02690 | 2026-11-26T09:21:16 event-07745 (D-06) | `eaeb4f87...` | **UNVERIFIABLE** | Only mutation events; no creation/full-file snapshot; current mixed. |
| `bot/review/evidence.py` | 2026-11-24T20:23:09 event-02194 | 2026-11-25T06:05:09 event-04886 | none found | `6cd287b8...` | **UNVERIFIABLE** | Multiple mutations; no creation/full-file snapshot. |
| `bot/review/verdict.py` | 2026-11-24T20:33:26 event-02324 | same event-02324 | none found | `3f1ff3b0...` | **UNVERIFIABLE** | Only one mutation; no creation/full-file snapshot. |
| `bot/review/ci_contract.py` | none found | none found | none found | `5f327503...` | **UNVERIFIABLE** | No write event for this path; current untracked file has no historical source. |
| `bot/db.py` | 2026-11-25T03:14:37 event-02634 | 2026-11-25T04:42:44 event-03643 | none found | `91b9e028...` | **UNVERIFIABLE** | HEAD `18c350ec...` lacks AutoReview classes/APIs; 30 pre-D05 mutations have no full snapshot; current modified file is mixed. |
| `bot/review/canary_linkage.py` | 2026-11-25T15:47:50 event-05872 | same event-05872 | none found | `c1797053...` | **UNVERIFIABLE** | Only a mutation event; no creation/full-file snapshot; D-01 B/D-02 provenance, not D-05. |

**Verified dependencies:** 0 of 6.
**Unresolved dependencies:** 6 of 6.

`eligibility.py` was not incorporated; it is D-06-owned and is not imported by the D-05
final resolver.

### 3.1 Overlap boundaries

- `collector.py`: R3/R5 history, D-06 edit 07745; no D-05 edit.
- `evidence.py`: R3/R4 history; no D-05 edit.
- `verdict.py`: R4 history; no D-05 edit.
- `ci_contract.py`: R3/R7 references; no write event found.
- `bot/db.py`: R5 and D-05-support history; HEAD lacks required AutoReview APIs.
- `canary_linkage.py`: D-01 B/D-02 history; not D-05.

No clean pre-D05 version can be reconstructed for any of these six without inference or
using a mixed current file, which is forbidden.

## 4. Dependency graph and test-readiness gate

### 4.1 D-05 rename/transfer

```text
tests/test_review_d05_rename_transfer.py
  -> bot/review/github.py             VERIFIED
  -> bot/review/resolver.py           VERIFIED
  -> tests/test_review_resolver.py    PARTIAL (no final hash)
       -> bot/db.py                   UNVERIFIABLE
       -> bot/review/ci_contract.py   UNVERIFIABLE
       -> bot/review/collector.py     UNVERIFIABLE
       -> bot/review/evidence.py      UNVERIFIABLE
       -> bot/review/verdict.py       UNVERIFIABLE
       -> bot/review/github.py        VERIFIED
       -> bot/review/resolver.py      VERIFIED
```

### 4.2 D-05 resolver tests

```text
tests/test_review_resolver.py
  -> bot/db.py                         UNVERIFIABLE
  -> bot/review/ci_contract.py         UNVERIFIABLE
  -> bot/review/collector.py           UNVERIFIABLE
  -> bot/review/evidence.py            UNVERIFIABLE
  -> bot/review/verdict.py             UNVERIFIABLE
  -> bot/review/github.py              VERIFIED
  -> bot/review/resolver.py            VERIFIED
```

### 4.3 Canary-linkage tests

```text
tests/test_review_canary_linkage.py
  -> bot/db.py                         UNVERIFIABLE
  -> bot/review/canary_linkage.py      UNVERIFIABLE (D-01 B/D-02, not D-05)
  -> bot/review/github.py              VERIFIED
  -> bot/review/resolver.py            VERIFIED
  -> tests/test_review_resolver.py     PARTIAL (no final hash)
```

### 4.4 Gate decision

**Test-readiness gate: FAILED.**

The focused tests require unverified production and test dependencies. Running them
would require copying current mixed-provenance files or guessing missing historical
content. Neither is permitted. **No focused D-05 tests were run.**

## 5. Validation performed

Validation was limited to reconstruction integrity, hashes, syntax, and manifest
consistency.

| Check | Result |
|---|---|
| Isolated HEAD/tree | exact baseline `0107967...` / `3ceb3580...` |
| D-05 source hash checks | 3/3 required source/canary hashes exact |
| D-05 test hash | `00139e48...` exact |
| Resolver test | `30dded74...`; no recorded final hash |
| `python -m py_compile` on five files | exit 0 |
| `pyflakes` on source + canary + D-05 test | exit 0 |
| `pyflakes` on `tests/test_review_resolver.py` | 23 findings, all inherited from event 07461 baseline |
| `git diff --check` in isolated clone | exit 0; reconstructed files are untracked |
| Trailing whitespace | 0 |
| Focused behavioral tests | **NOT RUN** |

The 23 pyflakes findings were documented as inherited baseline findings. No imports
were removed or altered.

## 6. Unresolved sources and missing snapshots

1. No full pre-D05 snapshot exists for `bot/review/collector.py`, `evidence.py`,
   `verdict.py`, or `ci_contract.py`.
2. `ci_contract.py` has no write event at all.
3. `bot/db.py` has no full pre-D05 snapshot with the required AutoReview APIs; HEAD's
   version is insufficient.
4. `canary_linkage.py` is D-01 B/D-02-owned and has no clean pre-D05 full snapshot.
5. `tests/test_review_resolver.py` has no independently recorded final hash.
6. The event store is mutable and has no signed manifest; this limits proof of
   completeness.

## 7. Artifacts

| Artifact | Path | SHA-256 |
|---|---|---|
| D-05 reconstruction manifest | `/tmp/ohb2-d05-deps-wUxVNK/d05_reconstruction_manifest.json` | `f83b849c1314faa4cc86a9f0971f981b6f8d3115d65d870f805fa77949f51986` |
| Dependency provenance manifest | `/tmp/ohb2-d05-deps-wUxVNK/dependency_provenance.json` | `59d56ae3bbc6a9f652d429614edd0554ee8775bfca08716981beb8a752a79f25` |
| Human-readable dependency graph | `/tmp/ohb2-d05-deps-wUxVNK/dependency_graph.md` | `69f76b264ce74cdd0bf2ec4a66a5303d33b5c1b1f0410a4faa00b850b968d25e` |

Reconstructed file hashes:

```text
bot/review/github.py                              a6274844a624ce45fd5788b648a25a4b59b16853458e06d900016badca21e1f6
bot/review/resolver.py                            967cbe1dd13184b30c35b28e653bb0a26e0f7a5cfb1dd1e4a93ea5e692bab6c6
tests/test_review_canary_linkage.py               b44b6248b047657bc7e82b5bb786f31348a65a2b7da675ebfa79a26a056f7b53
tests/test_review_resolver.py                     30dded749e14a22a83ed56552ce6a7a646255599d269ca935bc92c239f59da73
tests/test_review_d05_rename_transfer.py           00139e481ca33720fafb02e074be6fe917ca56bb6c5e4d5323155fdb46e2bf5d
```

## 8. Safety and Git actions

- **FIND-02 was not modified**; no TOCTOU remediation or code fix was performed.
- No application code, tests, configuration, schema, migration, existing report, or
  `.agent/PROGRESS.md` in the original working tree was modified.
- No current mixed dependency was copied into the reconstruction.
- No application database was opened.
- No production/GitHub/OpenHands/Telegram/Canary/provider API was called.
- No staging, commit, push, PR, merge, deployment, release, or branch switch occurred.
- Autopush was not activated.
- The only new file in the original working tree is this report.

## 9. Recommended next task

Before focused tests can run, a separately authorized task must provide verifiable
pre-D05 snapshots for the six unresolved dependencies, or reconstruct them from a
complete, exact event sequence without inference. Only then can the D-05 resolver,
rename/transfer, and canary-linkage suites be run in an isolated environment.

WP-03/D-05 and FIND-02 remain open.
