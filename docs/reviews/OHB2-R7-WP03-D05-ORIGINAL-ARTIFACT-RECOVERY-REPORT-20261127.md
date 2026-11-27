# OHB2-R7 WP-03 / D-05 — Original Artifact Recovery Report

**Task ID:** `OHB2-R7-WP03-D05-ORIGINAL-ARTIFACT-RECOVERY`
**Date:** 2026-11-27
**Verdict:** `PARTIAL_ARTIFACTS_RECOVERED`
**FIND-02 status:** `BLOCKED` (no remediation performed)

## 1. Executive result

The original D-05 **task prompt and execution trace** were found in the local
OpenHands conversation event store. The trace contains the exact D-05 file-edit actions,
including before/after payloads for the production files and the dedicated D-05 test.

This is substantially stronger than the previous reports, which had only prose reports.
However, it is **not a standalone Git patch or commit**, and the current working-tree
source files are not byte-identical to the D-05 final observations because later D-06
work modified some of the same files. A D-05-only patch can therefore be reconstructed
from the trace, but it has not been reconstructed or verified in this read-only task.

**Result:** `PARTIAL_ARTIFACTS_RECOVERED`, not `ORIGINAL_PATCH_RECOVERED`.

## 2. Current repository baseline

### 2.1 Git identity

| Item | Current value |
|---|---|
| Repository | `/workspace/project/OpenHandBot` |
| Working directory | `/workspace/project/OpenHandBot` |
| Branch | `agent/r6-review-delivery` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` |
| HEAD tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| `refs/heads/main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `refs/remotes/origin/main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `refs/remotes/origin/HEAD` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| Tracked modified | 12 pre-existing |
| Untracked | 88 at the baseline snapshot |
| Tracked `bot/review` files | 0 |
| Tracked `tests/test_review_*` files | 0 |
| Application DB opened | no |

Ignored project artifacts include `.pytest_cache/`, `__pycache__/`,
`bot/review/__pycache__/`, and other cache directories. They were not used as source
evidence.

### 2.2 Difference from the previous isolation report

Compared with
`docs/reviews/OHB2-R7-WP03-D05-BASELINE-ISOLATION-REPORT-20261127.md` (SHA-256
`ba73d62a2219dca971efe876d70694c8820a8ae78b1e4352f3df0b6d4cb59b5e`):

| Item | Previous report | Current |
|---|---|---|
| HEAD | `01079676351...` | unchanged |
| Tree | `3ceb3580...` | unchanged |
| Branch | `agent/r6-review-delivery` | unchanged |
| Tracked modified | 12 | 12 |
| Untracked | 87 before previous report | 88 (previous report now present) |
| Relevant current source hashes | recorded | unchanged |
| `bot/review` tracked | 0 | 0 |
| D-05 tests tracked | 0 | 0 |

No implementation source changed between the previous report and this audit. The only
new untracked file is the previous isolation report itself.

### 2.3 Current relevant hashes

| File | Current SHA-256 |
|---|---|
| `bot/review/github.py` | `8ec64cc2e9884a5b6aee58a25f0d27fb6107bc68a48e65424059298736884a51` |
| `bot/review/resolver.py` | `74198472d179fce4e0859675aafa5b81403dcc0890d220f9137a632a2951ddbc` |
| `bot/review/canary_linkage.py` | `c1797053344f51a3aed9782a512d045d461b8cca3e12a36fd228559cb053b142` |
| `bot/review/collector.py` | `eaeb4f872086a802c9505df0f666047cccaf16a888a91d6a0eead103aa7dc895` |
| `bot/review/authorization.py` | `9e64964f32e6c595eec6e40eba90694ce4348a5eed6deeae2fcb9bb12a6732f8` |
| `bot/review/eligibility.py` | `e29535572127ccfaac242378f9a05759e768afeb0e9a76832d9df1b9883f474e` |
| `tests/test_review_d05_rename_transfer.py` | `fe85d72831106b558772cbcb445e7ec8669785f0851c1b6069796c2d605dfde8` |
| `tests/test_review_resolver.py` | `b7e6fac173172edd4e04e4755de278b434ea833b5b0a59ebfb80553ccdd2f707` |
| `tests/test_review_canary_linkage.py` | `b44b6248b047657bc7e82b5bb786f31348a65a2b7da675ebfa79a26a056f7b53` |
| `tests/test_review_github.py` | `c9709562babf462249794c6b834ea433c42842fe094f0ed856694e3e4fa2a612` |
| `tests/test_review_authorization_revalidation.py` | `32e7451e857a2b51ff5cda6a69d8de63c3a0029a8b057b2e1784ccb42bd01157` |
| `tests/test_review_d06_private_allowlisted.py` | `07bea28aae56ed8eac02251bbbf500262b7837171c797049099a47bad53489d8` |

## 3. Search locations and methods

### 3.1 Git-local evidence

Read-only commands:

```text
git branch --all --verbose --no-abbrev
git reflog --all --date=iso
git stash list
git tag -n
git log --all --oneline --decorate -- bot/review
git rev-list --all --objects | grep bot/review
git fsck --full --unreachable --no-reflogs
git count-objects -v
git grep -l <terms> <each ref>
```

Results:

- No ref, reflog entry, stash, tag, or unreachable object contains `bot/review/` or
  `tests/test_review_*`.
- `git fsck --unreachable` produced no unreachable objects.
- The object database has 11,111 in-pack objects and no loose objects.
- No D-05 commit, tree, bundle, or patch exists in local Git history.

### 3.2 Project-local files and reports

Searched with content terms:

```text
OHB2-R7-WP03-D05
REJECT-RENAME-TRANSFER
reserve_resolved_memberships
ResolutionResult
repository_redirect_rejected
BRANCH_BLOCKED
resolve_and_reserve
```

Locations:

- `docs/reviews/` — D-05 implementation report, independent review, FIND-02 report,
  isolation report, and related B01/canary/D-06 reports.
- `.agent/PROGRESS.md` — D-05 progress entry; prose only.
- `bot/review/` — current implementation.
- `tests/` — current tests.
- `.openhands/` — memory file; no D-05 patch.
- `.github/workflows/verify.yml` — unrelated workflow; no D-05 evidence.

All report hits are **REFERENCE_ONLY**; they describe code but contain no original
before/after patch.

### 3.3 Other local filesystem locations

Searched:

- `/workspace` — project and unrelated NVIDIA proxy project; no D-05 patch.
- `/tmp` — temporary editor history and extracted runtime files.
- `/var/openhands/bash_events` — 154 opaque/compressed event files; no readable D-05
  artifact.
- `/root`, `/home/openhands` — no D-05 artifact.

Patch/bundle search found only unrelated handoff patches:

```text
docs/reviews/handoff/BOT-FILE-BROWSER/candidate.patch
docs/reviews/handoff/BOT-FILE-BROWSER-REMEDIATION/candidate.patch
docs/reviews/handoff/REV-01/REV-01-candidate.patch
docs/reviews/handoff/DEF011-A-OPTION-B/candidate.patch
docs/reviews/OHB2-WP07-DEF011-F02-ISOLATED-CANDIDATE.patch
```

None contains D-05 terms. They are excluded.

`/tmp/oh_editor_history_wytv3hr3/*.json` contains D-05 terms because it records the
current review-report editing history. It is **REFERENCE_ONLY**, not an original
implementation patch.

### 3.4 OpenHands conversation event store

Location:

```text
/var/openhands/conversations/40ced55b65114df4bfea7175717d5ca8/
```

Contents at inspection time:

- `TASKS.json` — SHA-256
  `670604b8285cbb121824686c29dd88346a6b3d4ce40cd7e19c340a6505c9e1f5`;
  it contains only the current task tracker, not historical task records.
- `events/` — 9,387 JSON event files, approximately 118 MB.
- `observations/` — terminal output captures.

The event store contains the original D-05 user prompt and the D-05 implementation
actions. This is the primary recovered artifact.

## 4. Recovered artifacts and integrity evidence

### 4.1 Original D-05 task prompt

| Property | Value |
|---|---|
| Path | `/var/openhands/conversations/40ced55b65114df4bfea7175717d5ca8/events/event-07431-89a903b3-2b51-4399-80ca-0e1636056c5e.json` |
| Type | OpenHands `MessageEvent`, source `user` |
| Timestamp | `2026-11-26T07:47:45.055069` |
| SHA-256 | `9fd288165094285824fb24820f7465ad123286124371073fdc6ebe4605f8dfcf` |
| Task ID | `OHB2-R7-WP03-D05-REJECT-RENAME-TRANSFER` |
| Content | Original implementation prompt; authorizes D-05 only and forbids D-04b, WP-04/05/06, worker/Canary, and Git publication |
| Status | **RECOVERED_AND_VERIFIED** |

The prompt is the authoritative start marker for the D-05 change set.

### 4.2 D-05 file-edit trace

The following ActionEvents contain exact `old_str`/`new_str` or full `file_text`
payloads. Each event file hash is recorded so the artifact can be re-read without
guessing.

| Event | Time (UTC) | Path / operation | Payload evidence |
|---|---|---|---|
| `event-07483-01fbf405-08ac-4a42-bd5e-2813626f17a4` | 07:50:03.700 | `github.py` `str_replace` | old `f13e06cb...`, new `6df11619...`; file hash `b7dc2e38...` |
| `event-07487-f6f411eb-625c-440d-8b48-603da1d99c11` | 07:50:07.473 | `github.py` `str_replace` | old `6af54edb...`, new `fc784aae...`; file hash `4c9c5f6d...` |
| `event-07491-076f99bb-3c55-4953-8837-e1a3cdf2536f` | 07:50:11.786 | `github.py` `str_replace` | old `1a1cfb8f...`, new `bc36fc1f...`; file hash `223beeb0...` |
| `event-07495-1e319204-a0af-4881-bfcd-87e40c1a964b` | 07:50:15.504 | `resolver.py` `str_replace` | old/new identical `e4979d64...`; **failed/no-op**; file hash `21f2c101...` |
| `event-07503-360f5744-d6c4-4a41-b5da-b8d34d67ef60` | 07:50:30.463 | `resolver.py` `str_replace` | old `03fe7a70...`, new `030baa5b...`; file hash `8aa41922...` |
| `event-07507-1c4b20c6-7d12-4a3a-a681-715796e41831` | 07:50:33.632 | `resolver.py` `str_replace` | old `927c9ea4...`, new `74de6972...`; file hash `d13f2132...` |
| `event-07515-cf2a035b-63d8-45ee-8f33-4a50b7fbfda3` | 07:50:43.397 | `resolver.py` `str_replace` | old `3d10f38a...`, new `e91ee658...`; file hash `62cf1f8f...` |
| `event-07519-404cb669-a95b-43c0-b9c5-62daebb9c71a` | 07:50:48.305 | `resolver.py` `str_replace` | old `c35861c3...`, new `2d111ba5...`; file hash `eb5757a6...` |
| `event-07523-99cf70fc-0130-4208-a398-a0fee8267c47` | 07:50:52.528 | `resolver.py` `str_replace` | old `a217e6e5...`, new `4dca0d0f...`; file hash `eb7f00bd...` |
| `event-07527-b3dfe3a7-7ce2-4d11-ac7b-bfee5c52c7e5` | 07:51:32.712 | `resolver.py` `str_replace` | old `d5687ded...`, new `4ca975c0...`; file hash `240c69c5...` |
| `event-07535-251d2880-55c7-4632-8a19-741070ce1467` | 07:51:50.221 | `tests/test_review_resolver.py`, `tests/test_review_canary_linkage.py` via terminal | command hash `ad426f38...`; adds `get_repository` call expectations |
| `event-07543-2318c5ba-9684-4714-baad-38c43492cc0a` | 07:52:05.221 | `tests/test_review_canary_linkage.py` | old `7af97708...`, new `a68a962f...`; file hash `87b96cb9...` |
| `event-07547-cbf557c3-3dc5-495b-a61d-0b6bde12c232` | 07:52:08.084 | `tests/test_review_canary_linkage.py` | old `87534175...`, new `b67fcc62...`; file hash `3c35aa95...` |
| `event-07555-bb38d01b-9be3-4562-bb03-2802031336b6` | 07:52:15.171 | `tests/test_review_canary_linkage.py` | old `a35a722e...`, new `603492ee...`; file hash `ba68076c...` |
| `event-07567-c227d18d-8300-4e36-b240-fd2072de95e8` | 07:53:14.520 | `tests/test_review_d05_rename_transfer.py` `create` | full text SHA `b0d60333...`; file hash `5210eb01...` |
| `event-07581-313bab15-bb7c-4a02-8ee0-2879bde38891` | 07:54:02.441 | D-05 test rewrite via terminal | command SHA `cb54412a...`; file hash `95e334b8...` |
| `event-07589-792654e3-da0d-49c2-a785-fd931d8b69f6` | 07:54:11.806 | D-05 test import cleanup | command SHA `1f65721a...`; file hash `b81ef00b...` |
| `event-07593-04b64e81-181f-4d1d-8672-070374d44dec` | 07:54:38.231 | D-05 test API/error cases | command SHA `94c8466c...`; file hash `2909f6f7...` |
| `event-07597-e1ab14ce-2138-41ea-b05b-1b6549720a1a` | 07:54:50.030 | D-05 test real-client redirect | command SHA `ed45c74b...`; file hash `374ac77b...` |
| `event-07619-c26728bd-e464-429f-bb94-393fd2568f9e` | 08:02:12.415 | Implementation report `create` | full text SHA `b1f2d526...`; file hash `ff44aba2...` |
| `event-07649-cc7afc13-be8f-485c-85ef-2ffb3bb25175` | 08:03:00.983 | Implementation report `str_replace` | old `70f7ade5...`, new `c44ea258...`; file hash `e9536b4c...` |
| `event-07653-8d716163-0a6b-45cd-8a68-b93e1d83eaf4` | 08:03:05.592 | Implementation report `str_replace` | old `ab8fdf17...`, new `8e496339...`; file hash `53769269...` |

The exact old/new payloads in these events are actual content, not merely prose
descriptions. The D-05 task prompt and the later implementation report provide
independent task-boundary evidence.

### 4.3 D-05 final observations

| Artifact | D-05 final content SHA-256 | Current SHA-256 | Match |
|---|---|---|---|
| `github.py` after last D-05 edit (event 07493 observation) | `a6274844a624ce45fd5788b648a25a4b59b16853458e06d900016badca21e1f6` | `8ec64cc2e9884a5b6aee58a25f0d27fb6107bc68a48e65424059298736884a51` | **No** |
| `resolver.py` after last D-05 edit (event 07529 observation) | `967cbe1dd13184b30c35b28e653bb0a26e0f7a5cfb1dd1e4a93ea5e692bab6c6` | `74198472d179fce4e0859675aafa5b81403dcc0890d220f9137a632a2951ddbc` | **No** |
| `tests/test_review_canary_linkage.py` (event 07557 observation) | `b44b6248b047657bc7e82b5bb786f31348a65a2b7da675ebfa79a26a056f7b53` | same | **Yes** |
| `tests/test_review_d05_rename_transfer.py` | current hash `fe85d728...`; event 07597 command SHA `ed45c74b...` | — | action recorded; final hash not independently re-derived in this audit |

The current production files are later states than the D-05 final observations; the
difference is consistent with later work in the same conversation, but this audit did not
fully attribute every later change. The current tree must not be treated as the original
D-05 snapshot.

### 4.4 Other artifacts

| Artifact | Status | Reason |
|---|---|---|
| `docs/reviews/OHB2-R7-WP03-D05-REJECT-RENAME-TRANSFER-IMPLEMENTATION-REPORT-20261126.md` | **REFERENCE_ONLY** | Prose implementation report; current SHA `1dc4f791...`; no patch. |
| `docs/reviews/OHB2-R7-WP03-D05-INDEPENDENT-REVIEW-20261126.md` | **REFERENCE_ONLY** | Independent review; current SHA `b791d55a...`; no patch. |
| `docs/reviews/OHB2-R7-WP03-D05-FIND02-TOCTOU-REMEDIATION-REPORT-20261127.md` | **REFERENCE_ONLY** | Prior blocked report; SHA `fe46d1cd...`; no patch. |
| `docs/reviews/OHB2-R7-WP03-D05-BASELINE-ISOLATION-REPORT-20261127.md` | **REFERENCE_ONLY** | Prior isolation audit; SHA `ba73d62a...`; no patch. |
| `.agent/PROGRESS.md` | **REFERENCE_ONLY** | D-05 progress entry; no original diff. |
| `/tmp/oh_editor_history_wytv3hr3/*.json` | **REFERENCE_ONLY** | Current report editing history, not original implementation. |
| Unrelated handoff patches | **REFERENCE_ONLY / excluded** | No D-05 terms. |
| `/var/openhands/bash_events` | **NOT_FOUND / opaque** | 154 files; no readable D-05 patch. |
| Git commit/patch/bundle | **NOT_FOUND** | No ref, reflog, stash, unreachable object, or bundle. |

## 5. File-by-file provenance findings

| File | Provenance finding |
|---|---|
| `bot/review/github.py` | **D-05_CONFIRMED_ACTION / MIXED_CURRENT.** Three D-05 `str_replace` actions are in the event trace: redirect error class, redirect status mapping, and canonical `full_name` rejection. Current file is later than D-05; current hash differs from D-05 final observation. |
| `bot/review/resolver.py` | **D-05_CONFIRMED_ACTION / MIXED_CURRENT.** Six effective D-05 edits: import/error mapping, explicit reason code, final repository revalidation, repository/PR identity checks, and error mapping. One event (`07495`) was a failed/no-op. Current file is later than D-05; later changes are not fully attributed in this audit. |
| `bot/review/canary_linkage.py` | **OTHER_WORK_PACKAGE / shared.** No D-05 file-edit action exists. D-05 changed only test call expectations; canary remains D-01 B/D-02-owned. |
| `bot/review/collector.py` | **OTHER_WORK_PACKAGE / shared.** No D-05 edit exists; current file is R3/R5/D-06 evidence collection. |
| `tests/test_review_d05_rename_transfer.py` | **D05_CONFIRMED.** Created and refined entirely within the D-05 task trace. |
| `tests/test_review_resolver.py` | **MIXED_OR_OVERLAPPING.** D-05 updated call expectations and fixtures; the file is also R7-B01 and later D-06 test surface. |
| `tests/test_review_canary_linkage.py` | **MIXED_OR_OVERLAPPING.** D-05 updated call expectations and identity fixtures; current hash matches the D-05 final observation. |
| `tests/test_review_github.py` | **D05_SHARED_DEPENDENCY.** GitHub client tests; no D-05 edit in the trace. |
| `bot/db.py` | **D05_SHARED_DEPENDENCY.** No D-05 edit; tracked pre-existing modified file. |
| `bot/review/authorization.py` | **OTHER_WORK_PACKAGE** (D-03). |
| `bot/review/eligibility.py` | **OTHER_WORK_PACKAGE** (D-06/eligibility). |
| `bot/review/worker.py`, `engine.py`, `evidence.py`, `schema.py`, `report.py`, `verdict.py`, `llm.py`, `prompts.py`, `redact.py` | **OTHER_WORK_PACKAGE**; no D-05 edit. |
| Other untracked tests/reports | **OTHER_WORK_PACKAGE / REFERENCE_ONLY**. |

## 6. Comparison against the current D-05 implementation

- Current `github.py` and `resolver.py` contain the D-05 logic, but their hashes differ
  from the D-05 final observations. They are later working-tree states, not the exact
  D-05 snapshot.
- Current `tests/test_review_canary_linkage.py` exactly matches the D-05 final
  observation hash.
- Current `tests/test_review_d05_rename_transfer.py` is present with hash
  `fe85d728...`; the trace records its creation and subsequent edits, including the final
  command at event 07597. This audit did not re-derive the final file content.
- The implementation report is present at the actual `OHB2-R7-WP03...` filename; its
  current hash is `1dc4f791...`. The initial creation and two later report edits are in
  the trace.
- No current source file can be used unchanged as the original D-05 baseline.

## 7. Recovery feasibility

### 7.1 What is recovered and verified

- The original D-05 task prompt: **RECOVERED_AND_VERIFIED**.
- The D-05 execution action trace: **RECOVERED_AND_VERIFIED** at the action/payload
  level.
- The dedicated D-05 test creation/edit trace: **RECOVERED_AND_VERIFIED**.
- The D-05 implementation report trace: **RECOVERED_AND_VERIFIED**.
- The current canary test matching the D-05 final observation: **verified by SHA-256**.

### 7.2 What is incomplete

- No standalone `.patch`, `.diff`, commit, bundle, or archive exists.
- No global event manifest or signature proves the event store is complete or immutable.
  The event count changed from 9,345 to 9,387 during this audit because the current
  session appended events.
- Current `github.py` and `resolver.py` are later than D-05; the D-05 final observations
  must be used, not the current files.
- The D-05 test final hash was not independently reconstructed in this audit.
- `TASKS.json` is the current task tracker only; it does not contain historical task
  records.

### 7.3 Can a reliable original D-05 patch be produced?

**Yes, with an authorized reconstruction step.** The event trace provides:

- the exact D-05 task boundary;
- exact file paths and operation order;
- old/new payloads for all production edits;
- full D-05 test creation and update commands;
- D-05 final observation hashes for `github.py` and `resolver.py`;
- D-05 report and test evidence.

A reconstruction can apply the D-05 action sequence to the pre-D-05 snapshots recorded
in the same event observations, then verify the resulting hashes against the D-05 final
observations. It must not use the current mixed files directly and must exclude later
D-06 events.

## 8. Remaining unknowns

- Whether every original D-05 event is still present; there is no signed event manifest.
- Whether the event store was pruned or compacted before this audit.
- Whether later D-06 changes fully explain every current hash difference.
- Whether the D-05 test final content hash can be reproduced exactly from the terminal
  commands without environment differences.
- Whether the owner authorizes reconstruction from runtime logs rather than a Git
  commit/patch.

## 9. Recommended next action

1. **Do not implement FIND-02 yet.**
2. Obtain authorization to reconstruct the D-05 change set from the recovered event
   trace on a clean base.
3. Use the pre-D-05 `old_content` snapshots in the event observations, apply the D-05
   actions in timestamp order, and verify against the D-05 final hashes:
   - `github.py`: `a6274844...`;
   - `resolver.py`: `967cbe1d...`;
   - canary test: `b44b6248...`;
   - D-05 test final command/action hash.
4. Exclude later D-06 events and all unrelated R3/R5/R6/R7 changes.
5. Only after that isolated D-05 baseline is verified should FIND-02 remediation begin.

**FIND-02 remains blocked.** Provenance is now partially established, but no clean
D-05 patch or baseline has been produced.

## 10. Safety confirmation

- No application code, tests, configuration, schema, migration, existing report, or
  `.agent/PROGRESS.md` was modified.
- No application DB was opened.
- No GitHub/OpenHands/Telegram/Canary/provider API was called.
- No branch, worktree, staging, commit, push, PR, merge, deploy, fetch, or pull occurred.
- Autopush remained disabled/inactive.
- WP-04, WP-05, and WP-06 were not started.
- This report is the only file created by this task.
