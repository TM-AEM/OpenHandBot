# OHB2-R7 WP-03 / D-05 — FIND-02 TOCTOU Remediation Report

**Task ID:** `OHB2-R7-WP03-D05-FIND02-TOCTOU-REMEDIATION`
**Date:** 2026-11-27
**Verdict:** `BLOCKED_BASELINE`
**FIND-02 status:** `BLOCKED`
**Review scope:** read-only Phase 0 baseline gate; no implementation was performed.

## 1. Executive result

The mandatory Phase 0 baseline gate **failed**.

The WP-03/D-05 implementation and its tests are present only as **untracked
working-tree files**. `bot/review/` and the D-05 review tests are absent from the
tracked HEAD tree. There is therefore no historical baseline or Git diff from which
the FIND-02 changes can be isolated from unrelated working-tree content.

Per the task's Phase 0 instruction, this task stopped with `BLOCKED_BASELINE` and did
**not modify application code, tests, configuration, schema, migrations, existing
reports, or `.agent/PROGRESS.md`**. No remediation was attempted, so FIND-02 remains
unresolved.

## 2. Baseline manifest

### 2.1 Repository identity

| Item | Value |
|---|---|
| Repository | `/workspace/project/OpenHandBot` |
| Working directory | `/workspace/project/OpenHandBot` |
| Branch | `agent/r6-review-delivery` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` |
| HEAD tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| `main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `origin/main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| Tracked modified | 12 pre-existing |
| Untracked | 86 before this report |
| Application DB opened | no |

No fetch, pull, reset, clean, checkout, branch switch, staging, commit, or push was
performed.

### 2.2 Git status and diff evidence

`git status --porcelain=v1` showed:

- 12 modified tracked files;
- 86 untracked entries.

The tracked diff contains only pre-existing files:

```text
.agent/PROGRESS.md
.env.example
README.md
bot/app.py
bot/config.py
bot/db.py
bot/handlers.py
bot/outbox.py
docs/OPERATIONS_RUNBOOK.md
tests/test_def011_a_option_b_limits.py
tests/test_def011_fs_offload.py
tests/test_doc_code_parity.py
```

`git diff --stat` reported 12 files changed, 4927 insertions(+), 28 deletions(-), all
pre-existing changes. It contains **no `bot/review/` file and no D-05 test file**.

### 2.3 Review implementation tracking status

```text
git ls-files bot/review                 -> empty (0 tracked files)
git ls-tree HEAD bot/review             -> empty
git ls-files 'tests/test_review_*'      -> empty (0 tracked files)
```

Relevant WP-03 files exist in the working tree but are untracked:

| File | Presence | SHA-256 |
|---|---|---|
| `bot/review/github.py` | present, untracked | `8ec64cc2e9884a5b6aee58a25f0d27fb6107bc68a48e65424059298736884a51` |
| `bot/review/resolver.py` | present, untracked | `74198472d179fce4e0859675aafa5b81403dcc0890d220f9137a632a2951ddbc` |
| `bot/review/canary_linkage.py` | present, untracked | `c1797053344f51a3aed9782a512d045d461b8cca3e12a36fd228559cb053b142` |
| `bot/review/collector.py` | present, untracked | `eaeb4f872086a802c9505df0f666047cccaf16a888a91d6a0eead103aa7dc895` |
| `bot/review/authorization.py` | present, untracked | `9e64964f32e6c595eec6e40eba90694ce4348a5eed6deeae2fcb9bb12a6732f8` |
| `bot/review/eligibility.py` | present, untracked | `e29535572127ccfaac242378f9a05759e768afeb0e9a76832d9df1b9883f474e` |
| `tests/test_review_d05_rename_transfer.py` | present, untracked | `fe85d72831106b558772cbcb445e7ec8669785f0851c1b6069796c2d605dfde8` |
| `tests/test_review_resolver.py` | present, untracked | `b7e6fac173172edd4e04e4755de278b434ea833b5b0a59ebfb80553ccdd2f707` |
| `tests/test_review_canary_linkage.py` | present, untracked | `b44b6248b047657bc7e82b5bb786f31348a65a2b7da675ebfa79a26a056f7b53` |
| `tests/test_review_github.py` | present, untracked | `c9709562babf462249794c6b834ea433c42842fe094f0ed856694e3e4fa2a612` |
| `tests/test_review_authorization_revalidation.py` | present, untracked | `32e7451e857a2b51ff5cda6a69d8de63c3a0029a8b057b2e1784ccb42bd01157` |
| `tests/test_review_d06_private_allowlisted.py` | present, untracked | `07bea28aae56ed8eac02251bbbf500262b7837171c797049099a47bad53489d8` |

### 2.4 Relevant reports

| Report | SHA-256 |
|---|---|
| `docs/reviews/OHB2-R7-WP03-D05-REJECT-RENAME-TRANSFER-IMPLEMENTATION-REPORT-20261126.md` | `1dc4f791f56ded7366a37964f503dfabcb4576e812a120e4faa398480b539e01` |
| `docs/reviews/OHB2-R7-WP03-D05-INDEPENDENT-REVIEW-20261126.md` | `b791d55a1c74292bfc26b205fc8b339806b51744312b9385d881ab3e61c966e9` |

Both are untracked. They were read, not modified.

### 2.5 Existing test state at the blocked baseline

Fresh baseline runs, not remediation evidence:

| Command | Actual result |
|---|---|
| `python -m pytest -q tests/test_review_d05_rename_transfer.py` | **23 passed** in 1.03s, exit 0 |
| `python -m pytest -q tests/test_review_resolver.py tests/test_review_canary_linkage.py` | **74 passed** in 6.75s, exit 0 |

These tests passing does not close FIND-02; no reservation-boundary test was added and
no code was changed.

## 3. Historical-baseline limitations

### 3.1 What is known

- HEAD is `01079676351aac869d09d4d1747661cd6f07d82b`.
- HEAD tree is `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc`.
- `main` and `origin/main` point to the same SHA in the current local refs.
- The tracked diff contains only 12 pre-existing files.

### 3.2 What cannot be established

- The historical commit in which `bot/review/github.py` or `resolver.py` was introduced.
- Which current lines are D-05 changes versus earlier R3/R5/R6/R7 review work.
- Whether unrelated review behavior was altered in the same untracked files.
- A clean D-05-only diff against a trusted baseline.
- Whether the implementation report's claimed file set is the actual complete delta.

The implementation report itself says 70/72 untracked entries, while the current tree
has 86 untracked entries. That is further evidence that the report's baseline is
historical/stale, not a current clean baseline.

## 4. FIND-02 root cause (read-only analysis only)

Read-only source inspection shows the reported gap remains present:

- `bot/review/resolver.py:407-480` — `reserve_resolved_memberships` validates internal
  provenance/membership consistency and then calls the DB reservation API.
- `bot/review/resolver.py:204-212` — the resolver performs a final repository identity
  re-read before returning `ResolutionResult`.
- `bot/review/canary_linkage.py:149-172` — `resolve_and_reserve` resolves first, then
  calls `reserve_resolved_memberships`.
- The reservation bridge receives repository ID/full name from the previously built
  `ResolutionResult`; it does **not** perform a fresh GitHub repository identity read.

Therefore a rename/transfer/deletion or identity change between resolver return and
reservation can still leave a stale identity in the result accepted by the reservation
bridge. This is a real TOCTOU path; it was not remediated because the baseline gate
failed.

## 5. Files changed by this task

**Only this report was created.**

No application code, tests, configuration, schema, migration, existing report, or
`.agent/PROGRESS.md` was changed. The `.agent/PROGRESS.md` modification shown by
`git status` is pre-existing.

## 6. Remediation design status

**Not implemented.** No design was applied because Phase 0 failed.

A future authorized remediation must add a reservation-boundary repository identity
verification using the existing read-only GitHub client, reject all identity/redirect/
deletion/API/malformed outcomes, and ensure no DB reservation occurs after a failed
verification. It must not silently add D-04b numeric-ID persistence. A full design and
implementation cannot be safely based on the current untracked snapshot.

## 7. Reservation-boundary validation status

**Not implemented.** `reserve_resolved_memberships` still accepts the prior
`ResolutionResult`; no fresh identity read exists at that boundary. No new failure
reasons were added. No tests for rename/transfer/deletion/redirect/API/malformed
reservation-boundary cases were added.

## 8. Remaining distributed-system/TOCTOU limitations

Even a future local re-read immediately before reservation cannot make a remote GitHub
read and a local SQLite transaction globally atomic. A residual window remains between
the fresh GitHub response and the SQLite commit, and a same-name deletion/recreation
cannot be distinguished without a durable identity mechanism (D-04b remains
`DEFERRED — NOT APPROVED`).

A future remediation can reduce the stale-result window and fail closed on observed
changes, but must not claim global atomicity or permanent repository identity.

## 9. Regression tests and fresh results

No remediation tests were added because no code was changed. Baseline-only results:

- D-05 focused tests: **23 passed**, exit 0.
- Resolver + Canary tests: **74 passed**, exit 0.

These are not acceptance evidence for FIND-02.

## 10. Unresolved findings

- **FIND-02 remains unresolved**: reservation can still accept stale repository identity.
- The implementation baseline is not isolated: all relevant code/tests are untracked.
- No reservation-boundary failure reasons or regression tests exist.
- D-04b remains deferred; no durable identity solution is approved.
- D-03/D-04/D-05/D-06 decisions were not modified, but their implementation delta cannot
  be independently isolated from the untracked tree.

## 11. FIND-02 status

**BLOCKED**, not `RESOLVED` or `PARTIALLY_RESOLVED`. The blocker is the Phase 0
baseline gate: no safe, bounded, historically attributable WP-03 implementation exists
to modify.

## 12. WP-03 independent re-verification

WP-03 should **not** proceed to independent re-verification of a FIND-02 remediation.
There is no remediation to verify. The next prerequisite is a stable baseline branch or
a reviewed patch/diff that isolates the WP-03 implementation and its tests from
unrelated working-tree content.

## 13. Safety confirmation

- No application code, tests, configuration, schema, migration, existing report, or
  `.agent/PROGRESS.md` changed.
- No application DB opened.
- No GitHub/OpenHands/Telegram/provider API call.
- No worker activation or Canary.
- No commit, push, PR, merge, deploy, release, fetch, or pull.
- Autopush remained disabled/inactive.
- No WP-04, WP-05, or WP-06 started.
- No owner approval or production authorization is implied.
