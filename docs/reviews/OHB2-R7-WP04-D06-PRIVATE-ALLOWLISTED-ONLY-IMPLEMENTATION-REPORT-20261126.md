# OHB2-R7 WP-04 / D-06 Private-Allowlisted-Only — Implementation Report

**Task ID:** `OHB2-R7-WP04-D06-PRIVATE-ALLOWLISTED-ONLY`
**Date:** 2026-11-26
**Verdict:** `WP04_D06_BLOCKED`
**Review label:** `AUTHOR_SELF_REVIEW — NOT INDEPENDENT REVIEW`

**Scope:** local implementation and verification of D-06 only. D-04/WP-02 remains
blocked and incomplete. D-04b remains deferred. D-07/D-08, WP-05, WP-06, R8, and R9
were not started. No live Canary, runtime worker, external API call, or Git
publication occurred.

## 1. Baseline and final Git state

| Item | Baseline | Final |
|---|---|---|
| Repository | `/workspace/project/OpenHandBot` | unchanged |
| Branch | `agent/r6-review-delivery` | unchanged |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` | unchanged |
| `main` / `origin/main` | same SHA | unchanged |
| HEAD tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` | unchanged |
| Modified tracked | 12 at baseline | 12 (includes `bot/config.py`) |
| Untracked | 72 pre-existing | 74 (D-06 code/test/report) |

All pre-existing modified and untracked files, including `.openhands/`, were
preserved. No destructive Git command was used.

## 2. Exact files changed

- `bot/config.py` — `REVIEW_REPOS` now rejects duplicate normalized entries instead
  of silently collapsing them.
- `bot/review/eligibility.py` — new pure D-06 metadata policy returning safe reason
  codes for non-private, fork, archived, and malformed identities.
- `bot/review/resolver.py` — enforces D-06 after D-01 B/D-02/D-05 identity checks and
  again after every PR/branch read.
- `bot/review/collector.py` — revalidates repository identity and D-06 eligibility
  before evidence collection and again after all evidence reads.
- `tests/test_review_d06_private_allowlisted.py` — new focused D-06 tests (23).
- `tests/test_review_config.py` — normalization test updated for unique entries and
  duplicate rejection cases added.
- `tests/test_review_resolver.py` — private-by-default repository fixture; collector
  fake now implements the repository identity read.
- `tests/test_review_d05_rename_transfer.py` — test repository payload is private, so
  D-05 tests continue to represent eligible repositories.
- `tests/test_review_collector.py`, `tests/test_review_branch_sha.py`,
  `tests/test_review_ci_jobs.py` — collector fakes implement the authoritative
  repository read and expected call sequences include D-06 revalidation.
- `.agent/PROGRESS.md` — additive WP-04 entry.
- `docs/reviews/OHB2-R7-WP04-D06-PRIVATE-ALLOWLISTED-ONLY-IMPLEMENTATION-REPORT-20261126.md`
  — this report.

No schema, migration, worker, configuration-field, or runtime change was made.

## 3. Existing implementation paths inspected

- WP-01/D-03: `bot/review/authorization.py`, `bot/review/worker.py`,
  `bot/review/report.py`, `bot/outbox.py`, `bot/app.py`, and
  `tests/test_review_authorization_revalidation.py`.
- WP-03/D-05: `bot/review/github.py` redirect rejection, canonical full-name
  checks, and `tests/test_review_d05_rename_transfer.py`.
- D-01 B: `bot/review/canary_linkage.py`, `CreationJobRepositoryLinkSource`,
  `creation_jobs`, and D-01 B tests.
- D-02: `CanaryLinkageService`, `_validate_owner_pr_numbers`,
  `ConversationMembershipResolver`, and explicit PR-list tests.
- Allowlist: `REVIEW_REPOS` parsing in `bot/config.py`,
  `GitHubClient._normalize_allowed_repositories`, `GitHubClient._repo`, and
  allowlist tests in `tests/test_review_config.py` and `tests/test_review_github.py`.
- Repository metadata: `RepositoryIdentity` (`private`, `fork`, `archived`,
  `full_name`, numeric ID) and `_parse_repository` in `bot/review/github.py`.
- Persistence boundaries: `bot/db.py`, review schema, reservation, membership
  snapshots, R5 leases/fencing, and R6 report/delivery paths.
- Tests: resolver, canary linkage, collector, branch SHA, CI jobs, authorization,
  callback, lifecycle, report, delivery, recovery, and worker integration.

## 4. D-06 eligibility policy implemented

The implementation is fail-closed and reuses the existing authoritative paths:

1. The repository must be in the explicit `GitHubClient` allowlist. The existing
   `_repo` check rejects any request outside it before HTTP.
2. `RepositoryIdentity.private` must be exactly `True`.
3. `RepositoryIdentity.fork` must be exactly `False`.
4. `RepositoryIdentity.archived` must be exactly `False`.
5. Missing, malformed, deleted, forbidden, or otherwise unavailable repository
   metadata is rejected with a safe reason code.
6. The numeric repository ID and full name must match the D-01 B link context;
   D-05 redirect and rename/transfer checks remain active.
7. Every selected PR must have matching repository, base repository, and head
   repository IDs and full names; cross-repository and fork PRs remain rejected.
8. The resolver re-reads repository identity after all PR/branch reads. The
   collector re-reads repository identity before and after evidence collection.
9. WP-01 current-owner authorization, deletion/revocation checks, and database
   failure handling remain mandatory.
10. No historical review record or prior eligibility is used as current evidence.

Safe reason codes added or reused include `repository_not_private`,
`repository_is_fork`, `repository_archived`, `malformed_repository_identity`,
`repository_not_allowed`, `repository_not_found`, `repository_redirect_rejected`,
`repository_rename_ambiguous`, `repository_id_mismatch`, and
`pr_repository_mismatch`.

## 5. Allowlist semantics and normalization

The existing allowlist is `REVIEW_REPOS`, parsed by `bot/config.py` into
`Config.review_repos`. The existing `GitHubClient(allowed_repositories=...)` is the
enforcement boundary for review reads.

- Entries are trimmed, split on commas or semicolons, lowercased, and normalized to
  exactly `owner/repo`.
- Invalid shapes, `.`/`..`, whitespace, and characters outside the existing repository
  name pattern are rejected.
- Empty or missing configuration produces an empty allowlist; every repository request
  then fails closed with `GitHubRepoNotAllowed`.
- Matching is exact set membership after normalization. There is no wildcard,
  prefix, organization-membership, or discovery behavior.
- Duplicate normalized entries are rejected with `ConfigError`; the GitHub client also
  rejects duplicate normalized allowlist inputs. No historical review record adds an
  entry.
- The allowlist is not rewritten after rename or transfer. A renamed/transferred
  repository must be explicitly re-added by the owner.

No new configuration field or secret was introduced.

## 6. Visibility, fork, archive, deletion, and ownership

- Public repository: rejected by `repository_not_private`.
- Private repository: accepted only when all other conditions pass.
- Fork: rejected by `repository_is_fork` even when private and allowlisted.
- Archived: rejected by `repository_archived`.
- Missing/malformed visibility, fork, or archive fields: rejected, never defaulted to
  eligible.
- Deleted/missing repository: `repository_not_found`.
- Forbidden/inaccessible repository: `github_unauthorized`.
- API/server error: `github_unavailable`.
- Owner/name mismatch: `repository_rename_ambiguous` or `repository_id_mismatch`.
- D-05 redirect rejection remains active; redirects are not followed.

## 7. PR association enforcement

The existing D-02 path remains authoritative:

- Every selected PR must belong to the exact resolved repository.
- Base and head repository IDs and full names must match.
- Cross-repository PRs are rejected with `pr_repository_mismatch`.
- Fork PRs are rejected with `pr_fork_ambiguous`.
- PR metadata errors and malformed PR identities fail closed.
- Exact-SHA branch/compare verification and immutable membership snapshots remain
  unchanged.

## 8. Revalidation boundaries

- Before reservation: `ConversationMembershipResolver.resolve` re-reads repository
  identity after all PR and branch reads; `resolve_and_reserve` reserves only after
  that succeeds.
- Before evidence collection: `GitHubEvidenceCollector._verify_repository` checks
  allowlist/identity/visibility/fork/archive state.
- After evidence collection: the collector checks repository identity and eligibility
  again before returning evidence.
- Existing branch re-verification before and after collection remains active.
- Stale eligibility cannot authorize a later operation through a cached result; the
  system has no eligibility cache and re-reads current metadata.

## 9. Same-name deletion/recreation limitation — unresolved blocker

The current approved data model stores the repository full name and the numeric ID
observed during the current linkage/resolution. It does **not** persist a
creation-time numeric ID for the D-01 B linkage. D-04b is deferred and this task is
forbidden from persisting, backfilling, indexing, or introducing GitHub numeric
repository IDs.

Therefore a repository that is deleted and recreated under the same full name, before
the current resolution, cannot be distinguished from the originally linked repository.
The existing test
`tests/test_review_canary_linkage.py::test_same_name_recreated_repository_is_not_distinguishable`
records this limitation. It was not changed into a false passing identity check.

This is an explicit unresolved D-06 blocker: the required rejection of recreated
repositories cannot be proven with the approved data model. No digest, fingerprint,
identity token, or name-based heuristic was invented as a substitute.

Within a single resolution/collection operation, D-05 revalidation does reject a
numeric-ID change observed after the first read. It does not solve the historical
same-name recreation case.

## 10. D-04 dependency and remaining blocker

WP-02/D-04 remains `WP02_D04_BLOCKED`. No owner attestation is created, inferred,
required, or assumed by D-06. D-06 does not use R6 owner acceptance as a substitute for
D-04 attestation. The same-name recreation blocker remains dependent on the deferred
D-04b identity decision.

## 11. Tests added and exact results

New D-06 focused tests: `tests/test_review_d06_private_allowlisted.py` — **23 passed,
0 failed**.

Coverage includes:

- exact allowlisted private repository accepted;
- non-allowlisted, empty-allowlist, wildcard, prefix, duplicate, and case-normalization
  behavior;
- public, missing-visibility, fork, archived, deleted, forbidden, server-error, and
  malformed metadata rejection;
- private eligible PR resolution and cross-repository/fork PR rejection;
- eligibility changes after PR reads rejected by resolver;
- collector rejection before evidence and after evidence;
- missing repository identity rejection.

Related suite:

`pytest -q tests/test_review_d06_private_allowlisted.py tests/test_review_github.py tests/test_review_resolver.py tests/test_review_canary_linkage.py tests/test_review_d05_rename_transfer.py tests/test_review_collector.py tests/test_review_branch_sha.py tests/test_review_ci_jobs.py tests/test_review_authorization_revalidation.py tests/test_review_callback.py tests/test_auto_review_lifecycle.py tests/test_review_report.py tests/test_review_delivery.py tests/test_review_recovery_failures.py tests/test_review_worker_integration.py tests/test_creation.py tests/test_miniapp_creation_jobs.py`

→ **400 passed, 2 warnings, 0 failed** in 26.46s.

Allowlist/config tests: `pytest -q tests/test_review_config.py` → **42 passed,
0 failed**.

Full Python suite: `pytest -q` → **4383 passed, 74 warnings, 0 failed** in 329.37s.

Node tests were run for completeness even though no frontend path changed:
`node --test tests/frontend/*.test.js` → **280 pass, 0 fail**.

Static/security checks:

- `python -m pyflakes bot/ automation/ tools/ main.py tests/` → exit 0.
- `python -m compileall -q bot automation tools main.py tests` → exit 0.
- `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` → **0 High**,
  7 Low, 20 Medium (pre-existing pattern).
- `python -m pip_audit -r requirements-dev.txt` → **no known vulnerabilities**.
- `git diff --check` → exit 0.
- `python -m pytest -q tests/test_doc_code_parity.py` → **16 passed**.

Warnings are the existing Starlette/httpx and PTB deprecation warnings. No test was
skipped. No live GitHub API, GitHub Actions, or external integration test was run.

## 12. Author self-review

`AUTHOR_SELF_REVIEW — NOT INDEPENDENT REVIEW`

Findings and resolutions:

- Public repository acceptance: D-06 requires exact `private is True`; public and
  missing visibility are rejected.
- Fork/archive bypass: both are rejected in resolver and collector; private fork and
  private archived tests exist.
- Allowlist wildcard/prefix/case: exact normalized membership; wildcard construction and
  prefix requests are rejected; case normalization is tested.
- Stale eligibility/TOCTOU: resolver final re-read and collector before/after re-read
  reject changes; a residual window before reservation remains inherent to the existing
  architecture.
- Alternate resolver/reservation paths: no new resolver or reservation path was added;
  D-06 is in the existing resolver and collector.
- Cross-repository/fork PRs: existing checks retained and tested.
- Fail-open exception handling: metadata/API errors map to safe failures; malformed
  identity is rejected.
- D-03/D-05/R5/R6 drift: WP-01 authorization, D-05 redirects/identity, R5
  leases/fencing, and R6 report/delivery paths were not changed.
- Numeric ID persistence: none added; no schema or migration change.
- Same-name recreation: not claimed as detectable; reported as a blocker.

## 13. Remaining risks and limitations

- Same-name deletion/recreation before the current resolution remains undetectable
  without D-04b. This is the reason for the BLOCKED verdict.
- The full name is not a permanent identity.
- A residual TOCTOU window remains between the final repository re-read and the
  subsequent DB reservation/execution.
- D-04/WP-02 remains blocked; no attestation is available.
- No live Canary or production integration was exercised.

## 14. Confirmations

- **D-04b:** remains `DEFERRED` and untouched. No GitHub numeric repository ID was
  persisted, backfilled, indexed, introduced, or required by new schema.
- **WP-02:** remains `WP02_D04_BLOCKED` and incomplete. No D-04 attestation was
  fabricated or assumed.
- **WP-05 and WP-06:** not started.
- **D-07/D-08:** no bounded supervisor implementation; live Canary remains blocked.
- **R5 worker:** inactive; no runtime worker was activated.
- **Live Canary / external operations:** no live Canary, OpenHands API, GitHub write,
  Actions dispatch, provider inference, Telegram delivery, production database access,
  deployment, or release occurred.
- **Git publication:** no commit, push, pull/fetch, PR, merge, or publication occurred.
  Autopush remains disabled/inactive.
- **Independent review:** deferred; this is not an independent review. R8 and R9 were
  not started.

## 15. Final verdict

`WP04_D06_BLOCKED`

The private/allowlisted/fork/archive/deletion/redirect/PR/revalidation controls are
implemented and tested, but WP-04 cannot be declared complete because the required
same-name deletion/recreation rejection depends on deferred D-04b identity evidence.
The limitation was not converted into a false PASS.
