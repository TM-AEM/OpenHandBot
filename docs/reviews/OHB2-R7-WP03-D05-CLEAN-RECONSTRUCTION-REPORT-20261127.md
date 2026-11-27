# OHB2-R7 WP-03 / D-05 — Clean Reconstruction Report

**Task ID:** `OHB2-R7-WP03-D05-CLEAN-RECONSTRUCTION`
**Date:** 2026-11-27
**Verdict:** `PARTIAL_RECONSTRUCTION`
**FIND-02 status:** `NOT_MODIFIED` (no remediation performed)

## 1. Executive result

A clean isolated clone was created from the exact baseline commit, and D-05 was
reconstructed from the original OpenHands event trace without using the current mixed
`bot/review/github.py` or `bot/review/resolver.py` as source files.

Three required files match their recorded D-05 final SHA-256 values exactly:

- `bot/review/github.py` — `a6274844...`
- `bot/review/resolver.py` — `967cbe1d...`
- `tests/test_review_canary_linkage.py` — `b44b6248...`

Two additional test files were reconstructed from exact event operations but do not
have a complete recorded final-hash proof:

- `tests/test_review_resolver.py` — actual `30dded74...`; no recorded final hash.
- `tests/test_review_d05_rename_transfer.py` — reconstructed `fe1801f4...`; current
  working-tree file is `fe85d728...` because of later changes, including a verified D-06
  `private=True` change and one unexplained blank line.

The reconstruction is therefore **PARTIAL_RECONSTRUCTION**, not full D-05 closure.

## 2. Baseline verification

### 2.1 Source repository

| Item | Value |
|---|---|
| Repository | `/workspace/project/OpenHandBot` |
| Branch | `agent/r6-review-delivery` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` |
| HEAD tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| `main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `origin/main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| Tracked modified | 12 pre-existing |
| Untracked before this task | 89 |
| `bot/review` tracked | 0 |
| `tests/test_review_*` tracked | 0 |

The source working tree was not modified. No reset, clean, stash, checkout, branch
switch, staging, commit, or push was performed in it.

### 2.2 Isolated reconstruction environment

Created with:

```text
git clone --no-hardlinks --no-checkout /workspace/project/OpenHandBot \
  /tmp/ohb2-d05-recon-RgO1Cr
git -C /tmp/ohb2-d05-recon-RgO1Cr checkout --detach \
  01079676351aac869d09d4d1747661cd6f07d82b
```

Verified isolated environment:

| Item | Value |
|---|---|
| Path | `/tmp/ohb2-d05-recon-RgO1Cr` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` |
| Tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| Initial status | clean (0 entries) |
| Source repo modified | no |
| Branch created in source | no |
| Staging/commit in source | no |

All reconstruction artifacts, including `reconstruct.py` and
`reconstruction_manifest.json`, are under `/tmp/ohb2-d05-recon-RgO1Cr`.

## 3. Event-store evidence

Authoritative event store:

```text
/var/openhands/conversations/40ced55b65114df4bfea7175717d5ca8/events/
```

### 3.1 Original task prompt

| Property | Value |
|---|---|
| Event | `event-07431-89a903b3-2b51-4399-80ca-0e1636056c5e.json` |
| Timestamp | `2026-11-26T07:47:45.055069` |
| Type | `MessageEvent` from user |
| Event SHA-256 | `9fd288165094285824fb24820f7465ad123286124371073fdc6ebe4605f8dfcf` |
| Task ID | `OHB2-R7-WP03-D05-REJECT-RENAME-TRANSFER` |

The prompt is the D-05 boundary and explicitly forbids D-04b, WP-04/05/06, worker
activation, live Canary, and Git publication.

### 3.2 Source operations applied

| File | Baseline source | Applied D-05 events | Excluded events |
|---|---|---|---|
| `bot/review/github.py` | `event-07485` observation `old_content` | `07483`, `07487`, `07491` | none |
| `bot/review/resolver.py` | `event-07505` observation `old_content` | `07503`, `07507`, `07515`, `07519`, `07523`, `07527` | `07495` failed/no-op |
| `tests/test_review_canary_linkage.py` | `event-07545` observation `old_content` | `07543`, `07555` | `07535` canary pairs failed before write; `07547` failed/no replacement |
| `tests/test_review_resolver.py` | `event-07461` observation content | `07535` pair 0 | canary pairs of 07535 |
| `tests/test_review_d05_rename_transfer.py` | `event-07581` cat heredoc | `07589`, `07593`, `07597` | none in this sequence |

The failed events are not treated as changes:

- `event-07495` had identical `old_str`/`new_str`; no effective change.
- `event-07535` failed its third assertion before writing the canary file; only its
  test-resolver pair was persisted.
- `event-07547` reported no replacement; it was not persisted.

## 4. Reconstructed files and operations

### 4.1 `bot/review/github.py`

- Baseline: `event-07485` observation `old_content`, SHA-256
  `fdc8b151ca8df8e680db1882234a90ebed285af357a5473bcf7ae99480b7bec6`.
- Applied:
  - `event-07483` — redirect error classes.
  - `event-07487` — 3xx mapping to `GitHubRedirectError`.
  - `event-07491` — canonical `full_name` check in `get_repository`.
- Reconstructed SHA-256:
  `a6274844a624ce45fd5788b648a25a4b59b16853458e06d900016badca21e1f6`.
- Expected: same. **Exact match.**

### 4.2 `bot/review/resolver.py`

- Baseline: `event-07505` observation `old_content`, SHA-256
  `f4c847a3c11c6af77c766cb665aede80396b64473a1aac37cff3dfce3449621b`.
- Applied:
  - `event-07503` — import/error-class additions.
  - `event-07507` — explicit repository redirect reason.
  - `event-07515` — final repository revalidation.
  - `event-07519` — repository/PR identity checks.
  - `event-07523` — error mapping.
  - `event-07527` — link loading/error handling.
- Excluded: `event-07495` failed/no-op.
- Reconstructed SHA-256:
  `967cbe1dd13184b30c35b28e653bb0a26e0f7a5cfb1dd1e4a93ea5e692bab6c6`.
- Expected: same. **Exact match.**

### 4.3 `tests/test_review_canary_linkage.py`

- Baseline: `event-07545` observation `old_content` (pre-D05), SHA-256
  `7ec8ac0e393edb08e3a8948bc1a2c9ed8607e8c5d8765a7b297aed651c4839a7`.
- Applied:
  - `event-07543` — `get_repository` call expectation.
  - `event-07555` — identity fixture update.
- Excluded:
  - `event-07535` canary pairs 1/2: assertion failed before write.
  - `event-07547`: no replacement.
- Reconstructed SHA-256:
  `b44b6248b047657bc7e82b5bb786f31348a65a2b7da675ebfa79a26a056f7b53`.
- Expected: same. **Exact match.**

### 4.4 `tests/test_review_resolver.py`

- Baseline: `event-07461` observation content, SHA-256
  `962dc5a30a774de5b1b7465310e7c16c5c13de7f70469e0f4bb3c94d63b83160`.
- Applied: `event-07535` pair 0 (adds `get_repository` call expectation).
- Reconstructed SHA-256:
  `30dded749e14a22a83ed56552ce6a7a646255599d269ca935bc92c239f59da73`.
- No independently recorded final hash exists. **No final-hash proof.**
- `pyflakes` reports 23 unused imports in this reconstructed file; this is a
  validation finding, not a code change.

### 4.5 `tests/test_review_d05_rename_transfer.py`

- Baseline: `event-07581` cat heredoc, SHA-256
  `74f9a80fe01dd541a3d25c86ec7115e5735736193ba13fe34e82a200a19e80da`.
- Applied:
  - `event-07589` — import cleanup.
  - `event-07593` — API/error cases and append.
  - `event-07597` — real-client redirect case and append.
- Reconstructed SHA-256:
  `fe1801f4efb6eb37c2ddb69b8af2660cd1bdeadd6d5f84d972edba27db5dbdcf`.
- Current working-tree hash: `fe85d72831106b558772cbcb445e7ec8669785f0851c1b6069796c2d605dfde8`.
- Difference is not a command-hash mismatch: `ed45c74b...` was the SHA-256 of the
  **terminal command** at event 07597, not the file content.
- Applying later D-06 event 07749 (`private: False` -> `True`) to the reconstruction
  gives `c1c10e9e...`, but the current file still has one extra blank line before
  `test_api_error_after_pr_reads_fails_closed`. That blank-line change is not explained
  by the recovered D-05/D-06 events and is recorded as an unresolved evidence gap.

## 5. Excluded mixed changes

The following were deliberately not applied:

- Current `bot/review/github.py` and `bot/review/resolver.py`: later working-tree
  versions, not the D-05 final snapshots.
- Current test files: later D-06 changes are present.
- `event-07495`: failed/no-op.
- `event-07535` canary pairs: failed before persistence.
- `event-07547`: failed/no replacement.
- D-06 event `07749`: later `private=True` change; not part of D-05.
- Shared modules (`bot/review/collector.py`, `evidence.py`, `verdict.py`,
  `ci_contract.py`, `eligibility.py`, `bot/db.py`, and other tests): not reconstructed
  in this task because their full provenance is outside the D-05 event trace.

## 6. File-level provenance manifest

| File | Classification | Baseline hash | Reconstructed hash | Evidence / reasoning |
|---|---|---|---|---|
| `bot/review/github.py` | **D05_RECONSTRUCTED_HASH_VERIFIED** | `fdc8b151...` | `a6274844...` | Baseline event 07485; applied 07483/07487/07491; exact expected hash. |
| `bot/review/resolver.py` | **D05_RECONSTRUCTED_HASH_VERIFIED** | `f4c847a3...` | `967cbe1d...` | Baseline event 07505; applied 07503/07507/07515/07519/07523/07527; exact expected hash; 07495 excluded. |
| `tests/test_review_canary_linkage.py` | **D05_RECONSTRUCTED_HASH_VERIFIED** | `7ec8ac0e...` | `b44b6248...` | Baseline event 07545; applied 07543/07555; exact expected hash; failed 07535/07547 excluded. |
| `tests/test_review_resolver.py` | **D05_ONLY_VERIFIED** | `962dc5a3...` | `30dded74...` | Baseline event 07461; applied 07535 pair 0; no recorded final hash; 23 pyflakes unused-import findings. |
| `tests/test_review_d05_rename_transfer.py` (reconstructed) | **D05_ONLY_VERIFIED** | `74f9a80f...` | `fe1801f4...` | Baseline event 07581; applied 07589/07593/07597; event-derived final content; current file differs by later D-06 change and one unexplained blank line. |
| `tests/test_review_d05_rename_transfer.py` (current) | **MIXED_CHANGES_EXCLUDED** | current `fe85d728...` | not used | Later D-06 `private=True` and blank-line change; not original D-05. |
| `bot/review/canary_linkage.py` | **NOT_PART_OF_D05** | current `c1797053...` | not reconstructed | No D-05 file-edit event; D-01 B/D-02 shared behavior. |
| `bot/review/collector.py` | **NOT_PART_OF_D05** | current `eaeb4f87...` | not reconstructed | No D-05 edit; R3/R5/D-06 shared behavior. |
| `bot/review/authorization.py` | **NOT_PART_OF_D05** | current `9e64964f...` | not reconstructed | D-03 ownership. |
| `bot/review/eligibility.py` | **NOT_PART_OF_D05** | current `e2953557...` | not reconstructed | D-06/eligibility ownership. |
| `bot/db.py` | **SHARED_BASELINE_UNCHANGED** | tracked pre-existing modified | not reconstructed | D-05 dependency; no D-05 edit. |
| `tests/test_review_github.py` | **NOT_PART_OF_D05** | current `c9709562...` | not reconstructed | R3 client tests; no D-05 edit. |
| `tests/test_review_authorization_revalidation.py` | **NOT_PART_OF_D05** | current `32e7451e...` | not reconstructed | D-03 tests. |
| `tests/test_review_d06_private_allowlisted.py` | **NOT_PART_OF_D05** | current `07bea28a...` | not reconstructed | D-06 tests. |
| Other `bot/review` modules and review tests | **PROVENANCE_UNRESOLVED / NOT_PART_OF_D05** | current hashes not used | not reconstructed | No D-05 event evidence; shared R3–R7 dependencies. |

The machine-readable manifest is:

```text
/tmp/ohb2-d05-recon-RgO1Cr/reconstruction_manifest.json
```

Manifest SHA-256: `b7f0d3b51e55a128258fd77ce804ddcaaf817722a969d0c5a0ce92d7075cfd8d`.

## 7. Expected versus actual SHA-256

| File | Expected | Actual | Match |
|---|---|---|---|
| `bot/review/github.py` | `a6274844...` | `a6274844...` | **YES** |
| `bot/review/resolver.py` | `967cbe1d...` | `967cbe1d...` | **YES** |
| `tests/test_review_canary_linkage.py` | `b44b6248...` | `b44b6248...` | **YES** |
| `tests/test_review_resolver.py` | no recorded final hash | `30dded74...` | **NO PROOF** |
| `tests/test_review_d05_rename_transfer.py` | event-derived `fe1801f4...` | `fe1801f4...` | **event-derived only** |
| Current D05 test | later current `fe85d728...` | `fe85d728...` | **not original D-05** |

## 8. Tests and validation

Performed against `/tmp/ohb2-d05-recon-RgO1Cr` only:

| Check | Result |
|---|---|
| Isolated HEAD/tree | exact baseline `0107967...` / `3ceb3580...` |
| `python -m py_compile` on five reconstructed files | exit 0 |
| `pyflakes` on source + canary + D05 test | exit 0 |
| `pyflakes` on reconstructed `test_review_resolver.py` | 23 unused-import findings |
| `git diff --check` in isolated clone | exit 0; reconstructed files are untracked |
| Trailing whitespace on reconstructed files | 0 |
| Focused D-05 tests | **NOT RUN** |
| Resolver/canary tests | **NOT RUN** |

Focused tests were not run because the clean baseline does not contain the shared
`bot/review` modules (`collector`, `evidence`, `verdict`, `ci_contract`, `eligibility`)
or their shared test fixtures. Running them would require copying current unverified
shared modules into the reconstruction, which the task forbids. No historical test
result is presented as current evidence.

## 9. Unresolved evidence gaps

1. `tests/test_review_resolver.py` has no recorded final hash and has 23 pyflakes
   unused-import findings in the reconstructed content.
2. `tests/test_review_d05_rename_transfer.py` current differs from the event-derived
   reconstruction by:
   - the later D-06 `private=True` change (verified as event 07749);
   - one extra blank line not explained by the recovered event trace.
3. The shared review modules and test dependencies were not reconstructed; focused
   tests therefore remain unrun.
4. The event store is mutable and has no signed manifest; event count changed during
   the prior audit because the current session appended events.
5. No standalone Git patch/commit exists.

## 10. Reconstruction coverage

- **Source implementation:** 2 of 2 D-05 production files reconstructed and
  hash-verified.
- **Canary test:** 1 of 1 required test reconstructed and hash-verified.
- **Additional tests:** 2 reconstructed from exact operations; neither has a complete
  final-hash proof.
- **Shared dependencies:** not reconstructed; tests not run.
- **Current working tree:** not modified.

## 11. Safety confirmation

- FIND-02 was **not modified**; no remediation code, tests, or behavior was changed.
- No application code, tests, configuration, schema, migration, existing report, or
  `.agent/PROGRESS.md` in the existing working tree was modified.
- No application DB was opened.
- No GitHub/OpenHands/Telegram/Canary/provider API was called.
- No commit, push, PR, merge, deployment, release, branch switch, or Autopush activation
  occurred.
- All reconstruction writes occurred only under `/tmp/ohb2-d05-recon-RgO1Cr`.

## 12. Recommended next step

Before any FIND-02 remediation:

1. Reconstruct or obtain a verified clean baseline for the shared `bot/review`
   dependencies and test fixtures.
2. Resolve the `test_review_d05_rename_transfer.py` extra blank-line provenance gap.
3. Re-run the focused D-05 tests against the reconstructed source.
4. Perform independent re-verification of the isolated D-05 reconstruction.

WP-03/D-05 is not closed by this report.
