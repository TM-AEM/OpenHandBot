# OHB2-R7 WP-03 / D-05 — Independent Implementation Review

**Task ID:** `OHB2-R7-WP03-D05-INDEPENDENT-IMPLEMENTATION-REVIEW`
**Date:** 2026-11-26
**Verdict:** `PASS_WITH_NOTES`
**Review label:** `INDEPENDENT_READ_ONLY_REVIEW — SAME-AGENT RUNTIME, NOT THIRD-PARTY HUMAN REVIEW`

**Scope:** read-only review of the current working tree. No application code, test,
configuration, schema, migration, existing report, application database, worker,
Canary, or external API was changed or used.

## 1. Baseline and workspace identity

### 1.1 Repository and Git state

| Item | Value |
|---|---|
| Repository | `/workspace/project/OpenHandBot` |
| Working directory | `/workspace/project/OpenHandBot` |
| Branch | `agent/r6-review-delivery` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `origin/main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| HEAD tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| Tracked modified | 12 pre-existing |
| Untracked before this report | 85 |
| Untracked after this report | 86 (this report only) |
| Application DB opened | no |

`git status --short` showed 12 modified tracked files and untracked review/report files.
The 12 modified tracked files were pre-existing and were not changed by this review.
No fetch, pull, reset, clean, checkout, branch switch, stage, commit, or push was
performed.

### 1.2 Implementation report location

The task's expected filename:

`docs/reviews/OHB2-WP03-D05-REJECT-RENAME-TRANSFER-IMPLEMENTATION-REPORT-20261126.md`

is **missing**. The actual existing report is:

`docs/reviews/OHB2-R7-WP03-D05-REJECT-RENAME-TRANSFER-IMPLEMENTATION-REPORT-20261126.md`

It was read unchanged. Its stated verdict is `WP03_D05_PASS_WITH_NOTES` and its review
label is `AUTHOR_SELF_REVIEW — NOT INDEPENDENT REVIEW`.

### 1.3 Scope isolation limitation

**The WP-03/D-05 implementation cannot be isolated from unrelated working-tree changes
by Git diff.**

Observed:

- `git ls-tree HEAD bot/review` returned no entries; the entire `bot/review/` directory
  is untracked at this HEAD.
- `bot/review/github.py`, `bot/review/resolver.py`, and the D-05 tests are untracked,
  not modified tracked files.
- The D-05 implementation report claims specific changed files, but there is no tracked
  baseline in this working tree to diff them against.
- `git status` also contains many unrelated untracked review reports and test files.

Therefore this review can verify the **current code's behavior and tests**, but cannot
prove that the current `bot/review/github.py`/`resolver.py` contain only D-05 changes or
that unrelated review behavior was not altered in the same untracked files. This is a
**scope/evidence limitation**, not a demonstrated code defect. It is why the verdict is
qualified and not an unconditional PASS.

## 2. Scope reviewed

Read-only inspection:

- `bot/review/github.py` — HTTP client, redirect handling, repository identity, PR
  parsing.
- `bot/review/resolver.py` — identity checks, final repository revalidation, PR/SHA
  resolution, reservation bridge.
- `bot/review/canary_linkage.py` — D-01 B creation-job link source and linkage service.
- `bot/review/collector.py` — read-only evidence revalidation relevant to final identity.
- `bot/review/authorization.py` — D-03 boundary inspection.
- `tests/test_review_d05_rename_transfer.py`.
- `tests/test_review_resolver.py`.
- `tests/test_review_canary_linkage.py`.
- `tests/test_review_github.py`, authorization tests, and related D-05/resolver tests.
- The implementation report and owner decision records referenced by the task.

Architecture/decision files inspected: `AGENTS.md`, D-01 B/B1 records, D-02 explicit
PR-list records, D-03/D-05 approved decisions, D-04/D-04b boundaries, and D-06/WP-04
status records. The actual application database was not opened.

## 3. Independent code-flow analysis

### 3.1 HTTP boundary

`bot/review/github.py`:

- `GitHubClient.__init__` configures `httpx.AsyncClient(... follow_redirects=False,
  trust_env=False)` (lines 250-262).
- `_request_json` checks `300 <= resp.status_code < 400` **before** status-specific
  handling and raises `GitHubRedirectError` (lines 314-320). It never reads or follows
  `Location`.
- `get_repository` parses the response and rejects a canonical `full_name` that differs
  from the requested repository (lines 418-432).
- `get_pull_request` does not follow redirects and returns parsed PR identity; the
  resolver is responsible for base/head repository consistency (lines 435-442).
- `verify_branch_sha` catches `GitHubError` and returns `BranchVerification(status=
  "blocked")`; a redirect during branch verification therefore fails closed as a branch
  error, not as a successful result (lines 400-415).
- `get_repository` and PR parsing are read-only GET operations; no retry loop is present.

### 3.2 Resolver flow

`bot/review/resolver.py`:

1. `resolve()` validates request, authorizes conversation/owner, loads the link, loads
   the repository identity, loads each PR, validates PR repository identity, verifies
   branch SHA, compares base/head SHA, and builds memberships (lines 156-196).
2. It re-reads each PR head and branch after all reads (lines 197-203).
3. It performs a **final repository identity re-read** after all PR/branch reads and
   before returning `ResolutionResult` (lines 204-212; `_reverify_repository` lines
   279-293).
4. `_load_repository` checks numeric repository ID, canonical full-name equality, and
   eligibility (lines 257-277).
5. `_validate_pull_request` requires the PR's repository, base repository, base
   full-name, head repository, and head full-name to match the resolved repository;
   a different head repository is `PR_FORK_AMBIGUOUS` (lines 310-336).
6. `_verify_branch` rejects moved/missing/blocked branches (lines 338-357).
7. `_compare` binds compare evidence to repository and base/head/observed SHAs (lines
   372-393).
8. `reserve_resolved_memberships` accepts a `ResolutionResult` and checks internal
   provenance consistency, then calls the DB reservation API (lines 407-480). It does
   **not** perform a fresh GitHub identity read.

### 3.3 Canary linkage flow

`bot/review/canary_linkage.py`:

- `CreationJobRepositoryLinkSource.resolve` requires exactly one done creation job,
  owner chat, exact conversation, OpenHands `selected_repository` equality, and a
  GitHub repository identity with matching canonical full name (lines 48-95).
- It calls `get_repository` before returning a link; a redirect/identity mismatch
  propagates to the resolver link-loading boundary, which maps it to a safe failure.
- `CanaryLinkageService.resolve_and_reserve` resolves first, then calls
  `reserve_resolved_memberships` (lines 149-172); there is no fresh identity read
  between the two calls.

### 3.4 Error mapping

`_map_github_error` maps `GitHubRedirectError` to `repository_redirect_rejected` and
`GitHubRepositoryIdentityMismatch` to `repository_rename_ambiguous`. Transport/rate
limit/server errors map to retryable `github_unavailable`; malformed/response errors map
to `malformed_external_response`. No mapping converts an identity/redirect failure into
success.

## 4. Security case matrix

| # | Case | Result | Evidence / limitation |
|---|---|---|---|
| 1 | HTTP 301 | PASS | `github.py:317-320`; D-05 parametrized test; one call |
| 2 | HTTP 302 | PASS | same; real-client resolver test |
| 3 | HTTP 303 | PASS | parametrized test |
| 4 | HTTP 307 | PASS | parametrized test |
| 5 | HTTP 308 | PASS | parametrized test |
| 6 | Missing `Location` | PASS | 302 without Location rejected; code never reads it |
| 7 | Malformed `Location` | PASS by source inspection | Location unused; no dedicated test |
| 8 | Redirect chain | PASS | second 200 not reached; calls == 1 |
| 9 | Repository redirect | PASS | `get_repository` -> redirect error; resolver maps |
| 10 | PR URL redirect | PASS | D-05 test; no follow |
| 11 | Canonical `full_name` mismatch | PASS | HTTP boundary plus resolver check |
| 12 | Repository rename | PASS for tested redirect/200 mismatch | `get_repository` and final re-read; same-name limitation below |
| 13 | Repository transfer | PASS for tested redirect/200 mismatch | Full-name/ID checks |
| 14 | Old identity after redirect | PASS | no redirect follow; safe error |
| 15 | Old identity after same-name recreation | **RESIDUAL** | D-04b deferred; accepted; documented |
| 16 | Old identity after final read / before reservation | **RESIDUAL** | TOCTOU; reservation accepts prior result |
| 17 | PR from another repository | PASS | base/head repo ID and full-name checks |
| 18 | Fork PR | PASS | head repo mismatch -> `PR_FORK_AMBIGUOUS` |
| 19 | Additional transport calls | PASS/INFO | redirect tests one call; final revalidation adds one expected call |
| 20 | Final identity at correct point | PASS for resolver return | after all PR/branch reads; not repeated in reservation |
| 21 | Error converted to acceptance | PASS | no success path on identity/redirect errors |
| 22 | Resolver/Canary regression | PASS in tests, scope-limited | related suites pass; no tracked baseline |
| 23 | D-03 preservation | PASS in tests, scope-limited | authorization tests pass |
| 24 | D-04 preservation | PASS in tests, scope-limited | WP-02 remains blocked; no attestation code claim |
| 25 | D-04b exclusion | PASS by source/status, scope-limited | no numeric-ID persistence observed |
| 26 | D-06 separation | PASS in status, scope-limited | D-05 does not claim D-06 |
| 27 | Application integration | **NOT_TESTED** | resolver/service not wired into production execution |
| 28 | Live GitHub provider behavior | **NOT_TESTED** | mock/fake only |
| 29 | Branch/compare redirects | PASS by source; test gap | `verify_branch_sha` maps redirect to blocked; no dedicated test |
| 30 | Direct stale `reserve_resolved_memberships` | **RESIDUAL / test gap** | no live re-read in reservation |

## 5. Tests and commands actually executed

All commands were run read-only in `/workspace/project/OpenHandBot` with the existing
`.venv`; no dependency installation or external API call occurred.

| Command | Actual result |
|---|---|
| `python -m pytest -q tests/test_review_d05_rename_transfer.py` | **23 passed** in 0.92s |
| `python -m pytest -q tests/test_review_resolver.py tests/test_review_canary_linkage.py` | **74 passed** in 5.88s |
| `python -m pytest -q tests/test_review_github.py` | **44 passed** in 0.15s |
| Related suite (D-05 + resolver + canary + GitHub + authorization + callback + lifecycle + report + delivery + creation + miniapp creation) | **302 passed, 2 warnings** in 21.01s |
| `python -m pytest -q` | **4383 passed, 74 warnings** in 298.47s |
| `node --test tests/frontend/*.test.js` | **280 pass, 0 fail** |
| `python -m pyflakes bot/ automation/ tools/ main.py tests/` | exit 0 |
| `python -m compileall -q bot automation tools main.py tests` | exit 0 |
| `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | **0 High**, 7 Low, 20 Medium |
| `python -m pip_audit -r requirements-dev.txt` | **No known vulnerabilities found** |
| `python -m pytest -q tests/test_doc_code_parity.py` | **16 passed** |
| `git diff --check` | exit 0 |

**Historical claim mismatch:** the implementation report records **4358 passed** for
the full Python suite; the current actual run is **4383 passed**, 0 failed. The
difference is stale historical evidence, not a D-05 defect.

## 6. Findings

### FIND-01 — Scope isolation unavailable (HIGH evidence limitation, not a code defect)

- **Files:** `bot/review/github.py`, `bot/review/resolver.py`,
  `tests/test_review_d05_rename_transfer.py`, `tests/test_review_resolver.py`,
  `tests/test_review_canary_linkage.py`; all untracked.
- **Trigger:** review against HEAD.
- **Impact:** cannot prove the D-05 delta is limited to claimed files or exclude
  unrelated changes in the same untracked review code.
- **Evidence:** `git ls-tree HEAD bot/review` empty; `git status --short` shows these
  files untracked; implementation report claims "changed" but no tracked diff exists.
- **Classification:** confirmed scope/evidence limitation; not a functional defect.
- **Action:** provide a stable-baseline branch/patch or commit the WP-03 delta before an
  unconditional PASS.

### FIND-02 — Reservation bridge accepts a pre-resolved result without fresh identity read (MEDIUM)

- **Files:** `bot/review/resolver.py:407-480`, `bot/review/canary_linkage.py:149-172`.
- **Trigger:** caller retains a `ResolutionResult` across rename/transfer or constructs
  a stale result and calls `reserve_resolved_memberships`.
- **Impact:** reservation can commit a previously verified repository/PR identity; the
  final resolver re-read does not cover the interval to reservation.
- **Evidence:** source inspection; reservation validates internal provenance but makes
  no GitHub call; implementation report itself documents a TOCTOU window.
- **Classification:** confirmed residual limitation / integration risk; documented, not
  a redirect-following bypass.
- **Action:** revalidate current identity in/near the reservation transaction or use an
  approved durable identity commitment. D-04b remains deferred; no numeric-ID
  persistence may be added silently.

### FIND-03 — Branch redirects map to `BRANCH_BLOCKED`, not redirect-specific reason (LOW)

- **Files:** `bot/review/github.py:400-415`, `bot/review/resolver.py:338-357`.
- **Trigger:** `verify_branch_sha` gets a 3xx response.
- **Impact:** safe failure, but reason is not `repository_redirect_rejected`.
- **Evidence:** source inspection; no dedicated branch-redirect test.
- **Classification:** test/error-mapping gap; no fail-open behavior.
- **Action:** add branch-redirect test; decide whether exact reason code is required.

### FIND-04 — Missing tests for malformed Location, branch/compare redirects (LOW)

- **Files:** D-05 test file.
- **Trigger:** security matrix claims broader redirect coverage than dedicated tests.
- **Impact:** no observed bypass; code source-confirms rejection.
- **Classification:** test gap.
- **Action:** add malformed-Location, branch redirect, compare redirect, and final
  link-source redirect tests if D-05 is re-opened.

### FIND-05 — `BranchVerification.repository` not checked in resolver (LOW)

- **File:** `bot/review/resolver.py:338-357`.
- **Trigger:** alternate client returns a verification for another repository with
  status `unchanged`.
- **Impact:** resolver would accept it if client is trusted; real `GitHubClient` uses
  normalized request repository, so no direct external path found.
- **Classification:** defense-in-depth/test gap.
- **Action:** compare verification repository to expected repository and add a test.

### FIND-06 — Historical report counts and untracked counts are stale (INFO/LOW evidence)

- **Files:** implementation report; current `git status`.
- **Trigger:** comparison of report claims to current tree.
- **Impact:** report says 4358 full-suite passes; current is 4383. Report says 70/72
  untracked; current untracked is 85 before this report. No test failure.
- **Classification:** stale evidence; not a D-05 functional defect.
- **Action:** record current counts; do not use historical counts as current proof.

### FIND-07 — D-05 integration not wired into application execution (NOT_TESTED, INFO)

- **Files:** resolver/canary service call sites; untracked review feature.
- **Trigger:** operational D-05 test.
- **Impact:** resolver/service are tested locally but no current production review
  execution path was exercised.
- **Classification:** unverified integration; not a schema/code defect.
- **Action:** authorize and test application integration separately.

## 7. Comparison with the original implementation report

| Original claim | Independent result |
|---|---|
| `WP03_D05_PASS_WITH_NOTES` | **PASS_WITH_NOTES**, with scope/isolation and integration notes |
| D-05 tests 23 passed | Confirmed: 23 passed |
| Related tests 302 passed | Confirmed: 302 passed, 2 warnings |
| Full Python 4358 passed | **Not reproduced as stated:** current 4383 passed, 0 failed |
| Node 280 passed | Confirmed: 280 pass, 0 fail |
| pyflakes clean | Confirmed |
| compileall clean | Confirmed |
| Bandit 0 High / 7 Low / 20 Medium | Confirmed |
| pip-audit no known vulnerabilities | Confirmed |
| Documentation parity 16 passed | Confirmed |
| `git diff --check` clean | Confirmed |
| 301/302/303/307/308 rejected | Confirmed; code rejects all 3xx |
| Missing/malformed Location | Missing confirmed; malformed source-confirmed, no dedicated test |
| Redirect chain cannot bypass | Confirmed |
| PR redirect rejected | Confirmed |
| Rename/transfer rejected | Confirmed for tested redirect/200 mismatch; same-name limitation remains |
| Final identity re-read after PR reads | Confirmed in resolver; not in reservation bridge |
| D-04b untouched | No numeric-ID persistence observed; delta isolation limited |
| D-06 not claimed | Confirmed by report/status; D-06 files are separate untracked context |

## 8. Limitations and unverified areas

- **No tracked baseline** for `bot/review/` or the D-05 tests; no reliable D-05-only
  diff is possible in this workspace. This is the primary reason for the qualified
  verdict.
- `bot/review/` and D-05 tests are untracked; unrelated untracked review code may be
  present.
- No application integration was exercised; `NOT_TESTED`.
- No live GitHub/provider/Telegram call; provider behavior is mock/fake only.
- Same-name deletion/recreation remains indistinguishable under B1 without D-04b.
- TOCTOU between resolver return and reservation/execution remains; the reservation
  bridge itself performs no fresh identity read.
- The implementation report's full-suite count and untracked counts are stale.
- This review is same-agent read-only review, not third-party human review.

## 9. Final recommendation

**PASS_WITH_NOTES** for the current implementation's inspected D-05 behavior and
focused tests, **not an unconditional PASS** and **not a production/application
verification**.

The WP-03/D-05 implementation can be considered **independently inspected and locally
tested** for the covered resolver/GitHub/Canary cases. It cannot be considered
independently attributable as a clean D-05 delta, fully integrated, or operationally
verified. The next prerequisite is a stable baseline/diff for the WP-03 implementation
and a separate application-integration review; D-04b, D-06, WP-04, WP-05, and WP-06
remain out of scope and unchanged.

No implementation authorization, owner approval, commit, push, PR, merge, deployment,
or release is made by this review.

**Repository hygiene:** this review created only this report. It did not modify
`.agent/PROGRESS.md`, application code, tests, configuration, schema, migrations, or
existing reports. The `.agent/PROGRESS.md` modification shown by `git status` was
pre-existing.
