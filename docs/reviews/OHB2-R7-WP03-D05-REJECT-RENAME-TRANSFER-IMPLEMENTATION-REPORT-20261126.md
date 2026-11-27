# OHB2-R7 WP-03 / D-05 Reject Rename/Transfer — Implementation Report

**Task ID:** `OHB2-R7-WP03-D05-REJECT-RENAME-TRANSFER`
**Date:** 2026-11-26
**Verdict:** `WP03_D05_PASS_WITH_NOTES`
**Review label:** `AUTHOR_SELF_REVIEW — NOT INDEPENDENT REVIEW`

**Scope:** local implementation and verification of D-05 only. D-04/WP-02 remains
blocked and incomplete. D-04b remains deferred. WP-04 through WP-06 were not started.
No live Canary, worker activation, external API call, or Git publication occurred.

## 1. Baseline and final Git state

| Item | Baseline | Final |
|---|---|---|
| Repository | `/workspace/project/OpenHandBot` | unchanged |
| Branch | `agent/r6-review-delivery` | unchanged |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` | unchanged |
| `main` / `origin/main` | same SHA | unchanged |
| HEAD tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` | unchanged |
| Modified tracked | 12 pre-existing | 12 pre-existing |
| Untracked | 70 pre-existing | 72 (new test + this report) |

The 12 modified tracked files and all unrelated untracked files are pre-existing
working-tree changes. They were preserved and not staged, committed, reverted, or
cleaned.

## 2. Exact files changed

- `bot/review/github.py` — added explicit redirect and repository-identity errors;
  `_request_json` now raises `GitHubRedirectError` for every 3xx response; the HTTP
  client keeps `follow_redirects=False`; `get_repository` rejects a canonical full name
  that differs from the requested repository.
- `bot/review/resolver.py` — imported the new safe errors; added
  `REPOSITORY_REDIRECT_REJECTED`; mapped redirects and identity mismatches to explicit
  reason codes; mapped link-source identity failures; added a final repository identity
  re-read after all PR/branch reads.
- `tests/test_review_d05_rename_transfer.py` — new focused D-05 tests (23).
- `tests/test_review_resolver.py` — updated the expected call sequence for the added
  final repository revalidation.
- `tests/test_review_canary_linkage.py` — updated the expected call sequence and the
  same-name recreation fixture for the added final revalidation.
- `.agent/PROGRESS.md` — additive WP-03 entry.
- `docs/reviews/OHB2-R7-WP03-D05-REJECT-RENAME-TRANSFER-IMPLEMENTATION-REPORT-20261126.md`
  — this report.

No schema, migration, worker, configuration, or runtime changes were made.

## 3. Existing implementation paths inspected

- WP-01: `bot/review/authorization.py`, `bot/review/worker.py`,
  `bot/review/report.py`, `bot/outbox.py`, `bot/app.py`, and
  `tests/test_review_authorization_revalidation.py`.
- D-01 B: `bot/review/canary_linkage.py`,
  `CreationJobRepositoryLinkSource`, `creation_jobs`, and the D-01 B tests.
- D-02: `CanaryLinkageService`, `_validate_owner_pr_numbers`,
  `ConversationMembershipResolver`, and the explicit PR-list tests.
- GitHub identity: `GitHubClient.get_repository`, `get_pull_request`, `_request_json`,
  `httpx.AsyncClient(follow_redirects=False)`, `_parse_repository`,
  `_parse_pull_request`, and `_parse_pull_request_ref`.
- Review lifecycle: `reserve_resolved_memberships`, immutable PR memberships, R5 lease
  and fencing paths, and R6 owner acceptance/report/outbox paths.
- Tests: `tests/test_review_github.py`, `tests/test_review_resolver.py`,
  `tests/test_review_canary_linkage.py`, `tests/test_review_callback.py`,
  `tests/test_auto_review_lifecycle.py`, `tests/test_review_report.py`,
  `tests/test_review_delivery.py`, and related authorization tests.

## 4. D-05 behavior implemented

1. The exact repository full name comes from the existing authoritative D-01 B link
   context (`creation_jobs` plus the exact conversation/repository equality check).
2. `GitHubClient.get_repository` compares the returned canonical `full_name` with the
   requested full name using GitHub's case-insensitive naming semantics. A mismatch
   raises `GitHubRepositoryIdentityMismatch`.
3. The resolver separately checks the link's numeric identity and exact full name, and
   maps a full-name change to `REPOSITORY_RENAME_AMBIGUOUS`. Rename and transfer are both
   rejected; the code does not guess which one occurred.
4. The resolver re-reads repository identity after all PR and branch reads and before
   returning the resolution. A rename, transfer, numeric-ID change, redirect, malformed
   response, or API failure during resolution fails closed.
5. A PR is accepted only when its base and head repository IDs and full names match the
   exact resolved repository. Cross-repository PRs and fork PRs remain rejected by the
   existing resolver checks.
6. Existing exact-SHA branch/compare verification, immutable PR membership snapshots,
   D-02 explicit selection, and conversation-wide cycle semantics are unchanged.
7. No stored repository name or PR association is rewritten after a rename or transfer;
   no retry against the new name is attempted.
8. Errors use safe internal reason codes: `repository_redirect_rejected`,
   `repository_rename_ambiguous`, `repository_id_mismatch`,
   `pr_repository_mismatch`, `malformed_external_response`, and existing safe codes.
   Error messages do not contain tokens or response bodies.

## 5. Redirect handling and verified limitations

Verified behavior:

- `GitHubClient` is constructed with `follow_redirects=False`.
- `_request_json` checks for any status in `[300, 400)` before status-specific handling
  and raises `GitHubRedirectError`; it never follows a `Location` header.
- Tests cover 301, 302, 303, 307, and 308, a missing `Location`, a redirect chain whose
  second response would be a valid 200, and a PR lookup redirect. Each test asserts that
  the transport is called only once.
- A successful 200 response whose canonical `full_name` differs from the requested name
  is rejected by `get_repository`, so a final successful response cannot bypass
  canonical identity validation.
- Redirects observed while resolving the D-01 B link or the repository identity map to
  `repository_redirect_rejected`; they are not converted into a retry or a new name.

Verified limitation:

- The HTTP client exposes the redirect status directly and the code rejects it before
  following. There is no reliance on a "final response URL" after following a redirect.
- A repository full name is not a permanent identity. If a repository is deleted and a
  different repository is created under the same full name, D-05 cannot distinguish
  them. D-04b numeric-ID persistence remains deferred and was not introduced.
- There remains a small TOCTOU window between the final identity re-read and the later
  DB reservation/execution. Closing it would require an approved durable identity
  commitment or transactional identity token, which is outside D-05 and D-04b.
- D-04/WP-02 remains blocked, so this task does not claim an owner attestation exists or
  that a repository/PR selection has completed D-04 approval.

## 6. Tests added and exact results

Focused D-05 file: `tests/test_review_d05_rename_transfer.py` — **23 passed, 0 failed**.

Coverage includes:

- exact canonical full name accepted case-insensitively;
- different full name, rename, transfer, and owner/name change rejected;
- missing/malformed repository identity rejected;
- 301/302/303/307/308 redirects rejected with one transport call;
- redirect without `Location` rejected;
- redirect chain cannot reach a valid second response;
- PR lookup redirect rejected;
- repository 404/500 fail closed without response-body leakage;
- final repository revalidation rejects rename, transfer, and numeric-ID change after PR
  reads;
- redirect and identity-mismatch mapping to explicit reason codes;
- malformed/API failure during final revalidation fails closed;
- PR repository change after the first read is rejected.

Related suite (D-05 + resolver + canary + GitHub + authorization + callback + lifecycle +
report + delivery + creation):

`pytest -q tests/test_review_d05_rename_transfer.py tests/test_review_github.py tests/test_review_resolver.py tests/test_review_canary_linkage.py tests/test_review_authorization_revalidation.py tests/test_review_callback.py tests/test_auto_review_lifecycle.py tests/test_review_report.py tests/test_review_delivery.py tests/test_creation.py tests/test_miniapp_creation_jobs.py`

→ **302 passed, 2 warnings, 0 failed** in 26.58s.

Full Python suite: `pytest -q` → **4358 passed, 74 warnings, 0 failed** in 318.70s.

Node tests were run for completeness even though no shared frontend behavior changed:
`node --test tests/frontend/*.test.js` → **280 pass, 0 fail**.

Static/security checks:

- `python -m pyflakes bot/ automation/ tools/ main.py tests/` → exit 0.
- `python -m compileall -q bot automation tools main.py tests` → exit 0.
- `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` → **0 High**,
  7 Low, 20 Medium (pre-existing pattern).
- `python -m pip_audit -r requirements-dev.txt` → **no known vulnerabilities**.
- `git diff --check` → exit 0.
- `python -m pytest -q tests/test_doc_code_parity.py` → **16 passed**.

## 7. Author self-review

`AUTHOR_SELF_REVIEW — NOT INDEPENDENT REVIEW`

Findings and resolutions:

- Redirect-following defaults: verified `follow_redirects=False` and a pre-body 3xx
  rejection; added status/chain/call-count tests.
- Rename/transfer bypass through alternate lookup: `get_repository` now validates the
  canonical name at the HTTP boundary, and the resolver revalidates identity after PR
  reads.
- PR repository association: existing base/head ID and full-name checks remain; added a
  test where the PR repository changes between reads.
- Stale/cached identity: final re-read prevents a previously valid identity from
  authorizing later work after a change.
- TOCTOU: documented residual window between final re-read and reservation; no
  unapproved identity token or numeric-ID persistence was added.
- Fail-open handling: redirects, malformed identity, API errors, and final revalidation
  failures all map to safe failures; no success is returned on error.
- D-03/D-04/R5/R6 semantics: no changes to WP-01 authorization, D-04 attestation,
  R5 lifecycle/leases/fencing, or R6 acceptance/report/delivery.
- Numeric IDs: no new persistence, backfill, column, index, trigger, or migration.
- External transmission: no external call was made; tests use deterministic mocks and
  temporary SQLite databases.

## 8. Remaining limitations and risks

- Same-name deletion/recreation is not distinguishable without D-04b; documented and
  intentionally not worked around.
- A repository full name is not permanent identity; no continuity claim is made.
- The final identity re-read does not eliminate the unavoidable TOCTOU window before
  reservation/execution; a durable approved identity binding would be needed.
- D-04/WP-02 is blocked; D-05 does not fabricate or assume an attestation.
- No live Canary, no worker activation, and no external integration verification were
  performed.

## 9. D-04b exclusion confirmation

**D-04b remains `DEFERRED` and untouched.** No GitHub numeric repository ID was
persisted, backfilled, added as a column, indexed, triggered, or migrated. No schema or
migration change was made.

## 10. WP-02 status confirmation

**WP-02 remains `WP02_D04_BLOCKED` and incomplete.** D-04 attestation behavior was not
implemented or assumed. D-05 does not mark WP-02 complete.

## 11. WP-04 through WP-06

**Not started.** No private/allowlisted eligibility rules, bounded supervisor, or later
work package was implemented.

## 12. Live Canary, workers, external operations, and Git publication

- R5 worker remains inactive; no runtime worker was activated or modified.
- No live Canary execution occurred.
- No OpenHands API, GitHub API/write, Actions dispatch, provider inference, Telegram
  message, production database access, credential use, external data transmission,
  deployment, or release occurred.
- No commit, push, PR, merge, or Git publication occurred.
- Autopush remains disabled/inactive.

## 13. Independent review and R8

**Independent review remains deferred.** This report is an author self-review, not an
independent review. R8 has not started.

## 14. Final verdict

`WP03_D05_PASS_WITH_NOTES`

The D-05 protections are implemented for the authorized D-01 B/D-02 linkage and review
boundaries, with passing focused and full tests. The notes are the explicitly documented
same-name deletion/recreation limitation, the residual TOCTOU window, and the fact that
D-04/WP-02 remains blocked.
