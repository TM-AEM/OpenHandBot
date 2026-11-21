# OHB2 — WP-07 / DEF-011 / F-02 — Owner Review Workflow Execution Report

**Task:** `OHB2-WP07-DEF011-F02-OWNER-REVIEW-WORKFLOW-EXECUTION`
**Date:** 2026-11-21
**Verdict:** `F02_OWNER_REVIEW_EVIDENCE_READY`

---

## Verdict

# `F02_OWNER_REVIEW_EVIDENCE_READY`

The workflow tested the exact candidate (`6a1ca2e`) on a GitHub-hosted runner, both Python versions,
and the evidence package is complete. **F-02 is ready for the owner's judgment and remains OPEN.**

---

## 1. Phase 1 — Baseline verification

| Check | Result |
|---|---|
| Target still the exact PR #8 head | **YES** — `refs/pull/8/head` == `6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18` |
| PR #8 open and unmerged | **YES** — `OPEN`, `MERGEABLE`, 0 reviews |
| `main` at recorded baseline | **YES** — `52e7789cc8cc97a7f7c09c9592226ab117db99a2`, no movement |
| PR #7 untouched | **YES** — `31dec52289142d0d0dc2bd16604d88644ba3baba`, `OPEN` |
| User work preserved | **YES** — 8 pre-existing modified files and 84 untracked entries untouched; work done in a separate git worktree |

I read the three available baseline documents. The fourth
(`…ISOLATED-CANDIDATE-PUBLICATION-CI-INDEPENDENT-REVIEW-CLOSURE-REPORT.md`) **does not exist**; the
closest published artifacts are `…FINAL-CI-INDEPENDENT-REVIEW-AND-CLOSURE-REPORT.md` and
`…ISOLATED-FINAL-CLOSURE-REPORT.md`. I did not invent the missing one.

Note: `OHB2-WP07-DEF011-F02-INDEPENDENT-REVIEW-HANDOFF.md` documents **PR #7 / `31dec52`**, not our
target. It was reconciled, not reused as evidence.

---

## 2. Phase 2 — Workflow defects found and fixed

The prepared design was **not** usable as-is. Three concrete defects, found before publication:

| # | Defect | Effect if unfixed | Fix |
|---|---|---|---|
| 1 | Job gate hardcoded `github.head_ref == 'review/ohb2-wp07-def011-f02-isolated'` | The job would be **silently skipped** on the new branch — a green run with zero evidence, the worst failure mode | Removed the gate; target is pinned explicitly |
| 2 | Scope guard expected exactly 3 changed paths, computed `merge-base..HEAD` | Publishing the workflow on top of the candidate would make it 4 paths → guard fails | Scope guard now diffs `merge-base..REVIEW_SHA` (the candidate), and a separate step asserts the PR adds **only** the workflow file |
| 3 | No Python matrix, no `setup-python` | Phase 4 requires 3.11 **and** 3.13; the design tested only the runner default | Added `matrix: ["3.11","3.13"]` with `actions/setup-python@v5` |

A fourth defect appeared only at runtime and is reported in §5.

All four required safeguards are present and verified in the published file:

1. **Fail closed** — `if ! git checkout "${BASE}" -- bot/handlers.py` aborts, plus a blob-hash equality
   assertion (`git hash-object` vs `git rev-parse "${BASE}:bot/handlers.py"`).
2. **Evidence preserved on failure** — `continue-on-error: true` on all four check steps, `if: always()`
   on instructions and upload, `if-no-files-found: error`.
3. **Merge-base derived** — `git merge-base origin/main "${REVIEW_SHA}"`, with a warning if it drifts
   from `52e7789`.
4. **Obsolete `BASE_SHA` env mechanism removed** — 0 occurrences; it is computed inside the step.

The workflow asserts **no verdict** and contains **no** instruction to approve. The generated
instructions say, verbatim: *"You may reject this change even though every check above passed."*

### Validation

| Check | Tool | Result |
|---|---|---|
| Workflow lint | `actionlint 1.7.7` | **exit 0** (includes shellcheck of every `run:` block) |
| All repo workflows | `actionlint .github/workflows/*.yml` | **exit 0** (new file does not break the existing one) |
| YAML parse | PyYAML in `python:3.11-slim` | OK — triggers `[pull_request, workflow_dispatch]`, `permissions: {contents: read}`, matrix `["3.11","3.13"]`, 17→18 steps |
| Negative-control assertion logic | real pytest `-v` output in a container | verified before pushing (§5) |

`actionlint` was available locally, so no check is claimed from an unavailable tool.

---

## 3. Phase 3 — Publication

| Item | Value |
|---|---|
| Branch | `f02-owner-review-workflow` (from `6a1ca2e`, via a separate worktree) |
| **Workflow PR** | **#9** — base `review/ohb2-wp07-def011-f02-isolated`, adds **1 file** |
| Files in PR | `.github/workflows/f02-review.yml` **only** (verified via `gh pr view --json files`) |
| Workflow head | `1a84cad` |

Commit history on the branch — every commit touches **only** the workflow file:

| Commit | Purpose |
|---|---|
| `128bcf1` | Initial workflow (321 lines) |
| `139b086` | Fix trigger: `workflow_dispatch` resolves only on the default branch, and `pull_request.branches` matches the PR **base** — added the candidate branch |
| `9d9dc51` | Fix negative-control assertion (see §5) |
| `1a84cad` | Add named cancellation/lock-drain evidence step |

**Base choice.** The PR targets the candidate branch, not `main`, so its diff is exactly one file. If it
targeted `main` it would also carry the whole F-02 change, which would conflate the tooling with the
thing under review.

**Scope compliance.** No change to `bot/attachments.py`, `bot/handlers.py`, any test file, or `ci.yml`.
No settings, secrets, visibility or permission changes. No merge, deploy, release or Autopush.

### Staging discipline

`git add` was invoked with the single explicit path `.github/workflows/f02-review.yml` — never `git add
.` or `-A`. Staged file count verified as exactly 1 before each commit.

---

## 4. Phase 4 — Evidence validation from the actual run

**Final run: `44881727141` — success on both jobs.** Evidence is from this run only; the earlier CI run
on `31dec52` (PR #7) is *not* counted.

### 4.1 Runner identity (execution-host isolation)

| Field | Value |
|---|---|
| `RUNNER_NAME` / hostname | `runnervm0hi8g` |
| `RUNNER_OS` / image | `ubuntu26` |
| Image version | `20261116.202.1` |

This is a GitHub-provisioned VM, not the development container. **Execution-host isolation is proven.**
It is *not* reviewer independence — the workflow has no reviewer.

### 4.2 Exact tested commit and hashes

| Item | Value |
|---|---|
| Tested commit | `6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18` (verified by `git rev-parse HEAD` inside the job) |
| Base | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| `bot/attachments.py` | `b98d561f…818356` |
| `bot/handlers.py` | `82d9c4b8…d57525` |
| `bot/db.py` | `472fa573…343314` (unchanged) |
| `tests/test_def011_fs_offload.py` | `3d3b3a2a…f503ea` |
| `evidence/full.diff` | `cb3da652…b02ab0` |

I re-derived all four file hashes locally from the commit; they match the artifact exactly.

### 4.3 Results

| Check | py3.11.18 | py3.13.18 |
|---|---|---|
| F-02 suite | **45 passed** | **45 passed** |
| Full suite | **3330 passed** | **3330 passed** |
| pyflakes | **0 lines** | **0 lines** |
| bandit severity High | **0** | **0** |
| Named cancellation/lock-drain | **10 passed** | **10 passed** |

`handlers.py` hunks = **3**; F-02 test count = **45**; `scope=ok`.

### 4.4 Negative control

```
T8b_local_capped_read_runs_off_event_loop_thread  FAILED   (AssertionError: القراءة حصلت على خيط الحلقة)
T8c_local_capped_read_enforces_cap                PASSED
negative_control=T8b_fails_as_expected,T8c_still_passes
```

`T8b` discriminates the fix. `T8c` correctly still passes — it tests the byte cap, not the offload.

### 4.5 Artifacts

Two artifacts, 22 files each, 30-day retention:
`f02-review-evidence-6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18-py3.11` and `…-py3.13`.
They include failure evidence by construction (`if: always()`), though this run had none.

---

## 5. The failure I hit, and the fix

Honesty over a clean-looking history.

**Run `44881209033` failed.** The failing step was the negative control — on **both** Python jobs. Every
other step passed (45 tests, 3330 full suite, static analysis).

**Root cause:** my own assertion, not the control. I grepped for
`test_T8c_local_capped_read_enforces_cap` in `pytest -q` output, but `-q` **omits the names of passing
tests**, so the grep could never match and the step exited 1 even though the control behaved correctly.
The log confirms the real behaviour was right: `1 failed, 1 passed, 43 deselected`.

**Fix (`9d9dc51`):** run with `-v` and assert each outcome by name —
`test_T8b_… FAILED` and `test_T8c_… PASSED`. I verified the new assertion against real `-v` output in a
clean container *before* pushing:

```
tests/test_def011_fs_offload.py::test_T8b_local_capped_read_runs_off_event_loop_thread FAILED [ 50%]
tests/test_def011_fs_offload.py::test_T8c_local_capped_read_enforces_cap PASSED [100%]
```

Re-run `44881446348` → success. Then I added the named-test step (`1a84cad`) and re-ran →
`44881727141` → success. The diff hash `cb3da652…` is **identical across runs**, confirming
reproducibility.

This is recorded because a failed run that is quietly dropped is exactly how evidence packages become
untrustworthy.

---

## 6. Phase 5 — Owner review package

Created: `docs/reviews/OHB2-WP07-DEF011-F02-OWNER-REVIEW-EVIDENCE-PACKAGE.md`.

It contains the exact hashes, run/PR identifiers, results, negative-control evidence, nine explicit
limitations, and the four-way separation of **execution-host isolation / technical evidence / owner
judgment / independent review (not available)**. It contains **no pre-filled PASS** and **no
instruction to approve**; the findings template ships blank.

---

## 7. Published tooling vs. the original candidate

This distinction matters and is easy to blur:

| | F-02 candidate | Owner-review tooling |
|---|---|---|
| Commit | `6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18` | `1a84cad` (workflow file only) |
| Branch | `review/ohb2-wp07-def011-f02-isolated` | `f02-owner-review-workflow` |
| PR | **#8** (open, unmerged) | **#9** (open, unmerged) |
| Files changed | `bot/attachments.py`, `bot/handlers.py`, `tests/test_def011_fs_offload.py` | `.github/workflows/f02-review.yml` |
| Status | **Unchanged by this task** | Newly published |

PR #8 was not modified. The tooling PR adds nothing to the reviewed change.

---

## 8. Scope compliance

| Constraint | Status |
|---|---|
| `bot/attachments.py` changed | **NO** |
| `bot/handlers.py` changed | **NO** |
| Any test file changed | **NO** |
| D6 / repeated-cancellation implemented | **NO** |
| NEW-DEF-03 / NAV-01..06 / DEF-006 / other WP-07 work included | **NO** |
| `ci.yml` modified | **NO** (`actionlint` on all workflows: exit 0) |
| Settings / secrets / visibility / permissions changed | **NO** |
| Merged / deployed / released / Autopush enabled | **NO** |
| Independent review claimed | **NO** |
| WP-07 or DEF-011 claimed complete | **NO** |
| `git reset` / `git clean` / force push / `git add .` | **NONE** |
| Pre-existing user work disturbed | **NO** — separate worktree used |

---

## 9. Commands, commits, PRs, runs, artifacts

**Commands of record**

```
git fetch origin 6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18
git worktree add -b f02-owner-review-workflow /tmp/wt-f02 6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18
git add .github/workflows/f02-review.yml          # explicit path only
/tmp/al/actionlint .github/workflows/f02-review.yml   # exit 0
git push -u origin f02-owner-review-workflow
gh pr create --base review/ohb2-wp07-def011-f02-isolated --head f02-owner-review-workflow
gh run list --branch f02-owner-review-workflow
gh run view 44881727141 --repo TM-AEM/OpenHandBot --json jobs
gh run download 44881727141 --repo TM-AEM/OpenHandBot -D /tmp/ev2
```

**Commits:** `128bcf1` → `139b086` → `9d9dc51` → `1a84cad`
**PRs:** #9 (new, tooling); #8 and #7 untouched
**Runs:** `44881209033` (failure, fixed), `44881446348` (success), **`44881727141` (final success)**
**Artifacts:** `f02-review-evidence-…-py3.11`, `f02-review-evidence-…-py3.13`

---

## 10. What remains

- **F-02 is OPEN.** The owner must record an explicit technical decision.
- **PR #9 is OPEN and unmerged.** Merging it is the owner's call; nothing here requires it.
- **WP-07 and DEF-011 remain open.**
- **D6 remains deferred.**
- **No independent review exists** and none is claimed.

### Suggested next step

The owner downloads artifact `44881727141`, applies the §8 checklist in the evidence package, fills
`FINDINGS-TEMPLATE.md`, and records Accept / Accept-with-follow-ups / Reject on PR #8.
