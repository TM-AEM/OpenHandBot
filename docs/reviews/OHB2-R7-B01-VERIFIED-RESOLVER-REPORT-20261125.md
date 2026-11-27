# OHB2-R7-B01 — Verified Resolver Design and Local Implementation Report (2026-11-25)

**Task ID:** `OHB2-R7-B01-VERIFIED-RESOLVER-DESIGN-AND-LOCAL-IMPLEMENTATION`
**Verdict:** `R7_B01_OWNER_DECISION_REQUIRED`
**Scope:** local investigation, safe implementation, documentation, mocked tests, and local verification.
**Live validation:** not performed and not claimed.

No live OpenHands/GitHub/provider/Telegram call, workflow dispatch, worker activation,
external data transmission, production database access, commit, push, PR, merge,
deployment, or release was performed. Independent review remains deferred. R8 has not
started.

---

## 1. Baseline and final Git state

Baseline was inspected before editing. Values below are from the current checkout, not
copied from an older report.

| Item | Value |
|---|---|
| Repository | `/workspace/project/OpenHandBot` |
| Branch | `agent/r6-review-delivery` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `origin/main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| HEAD tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| Tracked files | 569 |
| Modified tracked files | 12 |
| Untracked entries | 52 |
| Python | 3.13.15 in `.venv` |
| pytest | 9.0.3 |
| Node | 24.22.2 |

The current canonical GitHub `main` was not re-queried because this task forbids live
GitHub API calls. `main` and `origin/main` locally both point to the R7 baseline SHA.

### Committed vs working-tree changes

- **Committed code:** none added by this task.
- **Tracking:** R1–R7 implementation, review tests, and these reports remain untracked;
  the review package (`bot/review/`) and resolver tests are working-tree changes.
- **Modified tracked files:** pre-existing R1–R7 modifications plus
  `docs/OPERATIONS_RUNBOOK.md` and `.agent/PROGRESS.md` updated by this task.
- **No publication:** no commit, push, PR, merge, deployment, or release.
- **Preserved:** `.openhands/`, historical reports, `bun.lock`, and unrelated files.

---

## 2. Mandatory baseline audit

Inspected before implementation:

- `docs/reviews/OHB2-AUTO-REVIEW-R7-READINESS-REPORT-20261125.md`
- `docs/reviews/OHB2-R7-REMEDIATION-REPORT-20261125.md`
- `docs/reviews/OHB2-R7-AUTHOR-SELF-REVIEW-20261125.md`
- `docs/reviews/OHB2-R7-B01-CONVERSATION-PR-SHA-DECISION-20261125.md`
- `docs/reviews/OHB2-AUTO-REVIEW-R0E-REVISED-DESIGN-20261124.md`
- `docs/reviews/OHB2-AUTO-REVIEW-R0E-DESIGN-CORRECTION-20261124.md`
- R2 membership/reservation: `bot/db.py` (`AutoReviewMembership`,
  `reserve_conversation_review`, `observe_auto_review_membership`,
  membership validation/ordering).
- R3 GitHub primitives: `bot/review/github.py`.
- R5 collector/cycle/lifecycle: `bot/review/collector.py`,
  `bot/review/worker.py`, `bot/review/evidence.py`, `bot/review/verdict.py`.
- R6 report/delivery: `bot/review/report.py`, `bot/outbox.py`.
- OpenHands conversation metadata: `bot/openhands_client.py`, `bot/messages.py`.
- Configuration/authorization: `bot/config.py`, `bot/app.py`, `bot/db.py`
  (`watched`, `is_deleted`).
- R7 F-01/F-02/F-03 protections and their tests.

The audit did not assume old report values; all baseline values were re-read from the
checkout and Git.

---

## 3. Current identity chain and trust boundaries

### 3.1 Chain

```text
OpenHands conversation ID
  -> existing watched.chat_id authorization
  -> explicit ConversationRepositoryLink (caller-supplied claim; source is audit only)
  -> GitHub numeric repository ID + full_name (read-only, allowlisted)
  -> explicit PR numbers (never guessed from a branch name or arbitrary text)
  -> GitHub PR base/head repository IDs + refs + state + merged + head SHA
  -> branch head == exact SHA, checked before and after all reads
  -> GitHub compare/merge-base == exact base SHA
  -> AutoReviewMembership (immutable snapshot)
  -> existing R2/R5 atomic conversation-wide reservation
```

### 3.2 What the code can establish

| Layer | Established now | Trust boundary |
|---|---|---|
| Conversation ID | Strict string syntax; a `watched` row must exist and its `chat_id` must match the request | This proves local bot authorization, not OpenHands account ownership |
| Conversation repository link | Only an injected `ConversationRepositoryLink` is accepted; no automatic source is implemented | The link is an unverified claim; `source` is audit metadata only |
| Repository identity | GitHub numeric `repository_id`, full name, owner id/login, visibility flags | GitHub response is external data; strict parser and allowlist |
| PR identity | PR number, base repo ID/name/ref/SHA, head repo ID/name/ref/SHA, state, merged, draft | GitHub response; fork/cross-repo rejected |
| Exact SHA | Strict 40-character lowercase hex; PR head SHA; branch verification; compare base/head | Existing R3 and R7 F-03 protections |
| CI completeness | Existing R7 F-01 contract-gated job completeness | Not weakened; incomplete jobs cannot reach PASS |
| Membership | Existing immutable `AutoReviewMembership`; deterministic ordering; duplicate rejection; atomic reservation | Existing R2/R5 model; no new concurrency model |

### 3.3 Untrusted metadata

The following are not proof of repository ownership and were not treated as such:

- conversation text or prompt content;
- PR descriptions;
- branch names;
- arbitrary PR URLs;
- legacy SHA-like tokens;
- any caller-provided `source` string;
- `selected_repository`/`pr_number` metadata unless an owner-approved source adopts it
  as a *candidate* and verifies it through GitHub.

`bot/openhands_client.py:386-397` sends only `selected_repository` and
`selected_branch` when starting a conversation; it does not send `pr_number`.
`bot/messages.py:92-101` treats `pr_number` as possibly a list. This is evidence for a
candidate shape, not proof of a trusted conversation→PR binding.

---

## 4. Resolver implementation

### 4.1 New read-only GitHub primitives

`bot/review/github.py` now includes:

- `RepositoryIdentity` and `get_repository()` (`github.py:114`, `:410`).
- `PullRequestIdentity` and `get_pull_request()` (`github.py:126`, `:417`).
- Strict parsers `_parse_repository` and `_parse_pull_request`
  (`github.py:711`, `:764`) that require:
  - positive repository IDs;
  - valid owner/repository names;
  - boolean visibility/fork/archived fields;
  - PR number matching the request;
  - valid base/head refs;
  - exact 40-character lowercase base/head SHAs;
  - base/head repository identity.
- Existing read-only HTTP rules remain: no redirects, no token in URLs, no raw error
  bodies, response size limits, and allowlist checks before any request.

These primitives make no live call unless a caller explicitly constructs a client and
invokes them. This task did not do that.

### 4.2 Resolver abstraction

`bot/review/resolver.py` introduces:

- `ConversationRepositoryLink`: caller-supplied repository identity claim plus an audit
  `source`.
- `ConversationRepositoryLinkSource`: a protocol for the still-unresolved trusted source.
- `ConversationMembershipResolver.resolve()` (`resolver.py:152`):
  1. validates conversation ID, positive chat ID, explicit positive PR numbers, and
     duplicate rejection;
  2. authorizes via `Database.is_deleted()` and `Database.get_watched()`/`chat_id`
     (`resolver.py:206`);
  3. loads a link from the injected source; missing link fails with
     `missing_conversation_repository_link`;
  4. verifies the GitHub repository immutable ID and full name, rejecting ID mismatch
     and rename/transfer ambiguity (`resolver.py:247`);
  5. loads each explicit PR and verifies base/head repository identity, no fork,
     open/non-merged state, exact SHA, and branch head (`resolver.py:266`, `:282`,
     `:312`);
  6. derives the merge-base with the existing compare primitive; a moving base is
     resolved by a second exact compare (`resolver.py:330`);
  7. re-reads the PR and branch after all reads; movement fails closed
     (`resolver.py:366`);
  8. returns deterministic, sorted immutable memberships with provenance.
- `reserve_resolved_memberships()` (`resolver.py:378`) validates provenance-to-
  membership consistency and calls the existing atomic
  `Database.reserve_conversation_review()`.

The resolver never invokes a reviewer provider. It has no provider dependency.

### 4.3 Explicit failure codes

Safe codes include:

- conversation/repository link: `missing_conversation_repository_link`,
  `conversation_link_unavailable`, `conversation_link_mismatch`,
  `unauthorized_conversation`, `conversation_authorization_unavailable`;
- repository: `repository_not_allowed`, `repository_not_found`,
  `repository_id_mismatch`, `repository_rename_ambiguous`;
- PR: `pr_not_found`, `pr_repository_mismatch`, `pr_fork_ambiguous`,
  `pr_not_open`, `pr_head_moved`;
- SHA/branch/CI: `branch_moved`, `branch_missing`, `branch_blocked`,
  `compare_mismatch`, `malformed_external_response`, `invalid_resolution_request`;
- transport: `github_unauthorized`, `github_unavailable`, `github_error`;
- input: `duplicate_pr_membership`.

No code is amplified with a token, response body, or caller-supplied repository text.

### 4.4 What is deliberately not implemented

There is no automatic `OpenHands conversation -> repository` source. There is no
automatic PR discovery. PR numbers must be explicit. No PR URL, branch-name heuristic,
prompt text, or legacy token is treated as identity. This is the unresolved owner
decision, not a silent fallback.

---

## 5. Membership integrity

### 5.1 Existing R2/R5 model

`AutoReviewMembership` requires `repository_id`, `repository_full_name`, `pr_number`,
`branch`, `base_sha`, and `head_sha` (`bot/db.py:898`). `_valid_review_membership`
validates types and the 40-character SHA shape (`bot/db.py:318`).
`_ordered_memberships` sorts by `(repository_id, pr_number)` and rejects duplicate
keys (`bot/db.py:346`).

`reserve_conversation_review` (`bot/db.py:8110`) uses `BEGIN IMMEDIATE`, validates the
provider snapshot, and inserts the review plus all memberships atomically. It rejects
conflicts and does not partially insert.

`observe_auto_review_membership` (`bot/db.py:8335`) records a newly observed PR as
pending when an active cycle exists (`deferred_active_cycle`) instead of mutating the
active snapshot.

### 5.2 Resolver compatibility

- Resolver output is exactly a tuple of `AutoReviewMembership`.
- Ordering is deterministic by `(repository_id, pr_number)`.
- Duplicate PR numbers are rejected before any DB write.
- `reserve_resolved_memberships` validates that provenance matches the membership and
  calls the existing atomic reservation.
- A changed `head_sha` produces a conflicting membership/active-cycle result; the old
  snapshot remains unchanged.
- A new PR after reservation is pending; it does not enter the active cycle.
- Repeated resolution with the same inputs is deterministic and reservation is
  idempotent.
- No new concurrency model, lifecycle, or delivery path was added.

### 5.3 Provenance limitation

The current schema has no dedicated provenance column. The resolver returns explicit
`source`, repository/PR/SHA, and `verified_at` provenance in `MembershipProvenance`,
and `reserve_resolved_memberships` validates it before reservation. Persisting that
provenance in the database would require an owner-approved schema change and was not
performed. This is listed as an owner decision.

---

## 6. Security and negative testing

`tests/test_review_resolver.py` — **32 passed** in the focused run. It covers the
required 25 cases and additional hardening:

| # | Required case | Representative test | Result |
|---|---|---|---|
| 1 | Valid conversation-to-repository association | `test_valid_conversation_repository_link_resolves_exact_membership` | PASS |
| 2 | Missing repository association | `test_missing_repository_association_fails_closed` | fails `missing_conversation_repository_link` |
| 3 | Unauthorized conversation | `test_unauthorized_conversation_fails_before_github` | fails `unauthorized_conversation`; zero GitHub calls |
| 4 | Repository name mismatch | `test_repository_name_mismatch_or_rename_is_ambiguous` | fails `repository_rename_ambiguous` |
| 5 | Repository ID mismatch | `test_repository_id_mismatch_fails_closed` | fails `repository_id_mismatch` |
| 6 | Rename/transfer ambiguity | same repository-name test | fails closed |
| 7 | Valid single PR | `test_valid_conversation_repository_link_resolves_exact_membership` | PASS |
| 8 | Multiple valid PRs in one conversation | `test_valid_multiple_prs_are_deterministically_ordered` | PASS, sorted order |
| 9 | PR from unauthorized repository | `test_pr_from_another_repository_is_rejected` | fails `pr_repository_mismatch` |
| 10 | Fork PR ambiguity | `test_fork_pr_is_ambiguous` | fails `pr_fork_ambiguous` |
| 11 | Closed or merged PR | `test_closed_or_merged_pr_is_rejected` | fails `pr_not_open` |
| 12 | Head branch movement | `test_head_branch_movement_is_rejected`; `test_branch_movement_during_final_verification_is_rejected` | fails `branch_moved` |
| 13 | PR head SHA mismatch | `test_pr_head_sha_mismatch_in_compare_is_rejected` | fails `compare_mismatch` |
| 14 | Malformed SHA | `test_malformed_pr_sha_is_rejected` | fails `invalid_resolution_request` |
| 15 | Compare result mismatch | `test_compare_result_from_another_repository_is_rejected` | fails `compare_mismatch` |
| 16 | Workflow run SHA mismatch | `test_workflow_run_sha_mismatch_is_rejected_after_resolution` | collector fails `ci_sha_mismatch` |
| 17 | Incomplete CI jobs | `test_incomplete_ci_jobs_cannot_reach_pass_after_resolution` | `BLOCKED` / `R4-CI-03` |
| 18 | Duplicate PR membership | `test_duplicate_pr_membership_is_rejected` | fails `duplicate_pr_membership` |
| 19 | Conflicting membership | `test_conflicting_membership_does_not_mutate_active_cycle` | conflict; old `head_sha` retained |
| 20 | Repeated idempotent resolution | `test_repeated_resolution_is_idempotent` | same result; `already_reserved` |
| 21 | New PR after cycle reservation | `test_new_pr_after_cycle_reservation_is_pending_not_mutating` | `deferred_active_cycle`; snapshot unchanged |
| 22 | Process restart/membership recovery | `test_process_restart_recovery_returns_same_membership` | same result |
| 23 | API timeout/unavailable | `test_api_unavailable_is_explicit` | `github_unavailable`, retryable |
| 24 | Malformed external response | `test_malformed_external_response_is_explicit`; GitHub parser tests | `malformed_external_response` / `GitHubMalformedResponse` |
| 25 | User metadata forging repository identity | `test_user_controlled_repository_claim_cannot_bypass_allowlist` | `repository_not_allowed` |

Additional coverage: conversation-link mismatch, empty result never inserts, and raw
GitHub repository/PR parser validation. Every rejection test asserts that no
`auto_reviews` row was inserted. The resolver has no provider dependency, so rejected
resolution cannot invoke a reviewer provider by construction.

No test was weakened or disabled.

---

## 7. Integration boundaries

- **No worker activation.** `bot/app.py` does not construct `ReviewWorker` or
  `ReviewRunner`; no startup wiring was added.
- **No automatic resolver entry point.** The only safe helper is
  `reserve_resolved_memberships`, which requires an explicit `ResolutionResult`, an
  authorized conversation, a valid provider snapshot, and the existing DB reservation.
- **Atomicity.** Reservation is delegated to
  `Database.reserve_conversation_review`, which inserts the cycle and all memberships
  in one transaction.
- **Immutability.** No code path updates an active membership snapshot. New PRs are
  recorded as pending.
- **Unapproved identity convention.** The concrete conversation→repository link
  source and PR-candidate source remain behind `ConversationRepositoryLinkSource` and
  explicit PR numbers; neither is selected by this implementation.

---

## 8. Runbook and architecture documentation

`docs/OPERATIONS_RUNBOOK.md` now has section 11, documenting:

- the exact trust chain and immutable identities;
- untrusted conversation/PR/branch/source metadata;
- resolver failure states and retryability;
- fork/cross-repository rejection;
- branch movement behavior;
- membership immutability and pending-new-PR behavior;
- retry/recovery and no-partial-insert behavior;
- remaining owner decisions;
- why `REVIEW_ENABLED=1` does not activate the worker;
- why mocked local verification is not live validation.

The runbook does not describe the resolver as operationally live.

---

## 9. Owner decisions still required

1. **Conversation→repository source.** Approve whether OpenHands
   `selected_repository` is an authorized candidate, or require an explicit
   owner/server mapping, or another source. The current resolver accepts only an
   injected claim source.
2. **PR-candidate source.** Approve whether OpenHands `pr_number` metadata is a
   candidate list, require explicit owner-supplied PR numbers, or use a separate
   approved correlation mechanism. The current resolver never guesses PRs.
3. **Provenance persistence.** Decide whether `source`, verification time, and
   evidence fingerprints must be persisted in a new schema/audit table. The current
   result carries provenance but does not add a DB column/table.
4. **Rename/transfer policy.** Current behavior rejects a GitHub name change even when
   the numeric ID is stable. Approve accepting a rename using immutable ID if desired.
5. **Fork policy.** Current behavior rejects fork/cross-repository PRs. Approve a
   different policy only if explicitly needed.
6. **Conversation authorization source.** Decide whether `watched.chat_id` is enough,
   or require an OpenHands owner/service-account check.
7. **Worker activation.** R7-B02 remains deferred; explicit activation requires
   startup wiring, configuration/auth validation, lease/shutdown/recovery tests, and
   separate authorization.
8. **Live validation authorization.** Provider, disposable repository, Telegram target,
   and live OpenHands/GitHub calls remain blocked.

Until these decisions are recorded, the automatic conversation→PR→SHA relationship is
not claimed as solved.

---

## 10. Local verification

Environment: Python 3.13.15, pytest 9.0.3, Node 24.22.2. Python 3.11 is not installed
locally; no Python 3.11 claim is made. No remote CI was triggered.

| Check | Command | Result |
|---|---|---|
| Focused resolver | `.venv/bin/python -m pytest -q tests/test_review_resolver.py` | **32 passed** |
| Membership/immutability | `.venv/bin/python -m pytest -q tests/test_auto_reviews_db.py` | **23 passed** |
| R5 lifecycle | `.venv/bin/python -m pytest -q tests/test_auto_review_lifecycle.py` | **30 passed** |
| R3 branch/SHA | `.venv/bin/python -m pytest -q tests/test_review_branch_sha.py` | **8 passed** |
| R7 F-01 CI completeness | `.venv/bin/python -m pytest -q tests/test_review_ci_jobs.py` | **15 passed** |
| R7 F-02 ProviderBinding | `.venv/bin/python -m pytest -q tests/test_review_provider_binding.py` | **11 passed** |
| R5 recovery failures | `.venv/bin/python -m pytest -q tests/test_review_recovery_failures.py` | **6 passed** |
| R5 collector | `.venv/bin/python -m pytest -q tests/test_review_collector.py` | **3 passed** |
| R5 worker integration | `.venv/bin/python -m pytest -q tests/test_review_worker_integration.py` | **1 passed** |
| R6 report | `.venv/bin/python -m pytest -q tests/test_review_report.py` | **11 passed** |
| R6 delivery | `.venv/bin/python -m pytest -q tests/test_review_delivery.py` | **8 passed** |
| All review-focused | `.venv/bin/python -m pytest -q tests/test_review_*.py tests/test_auto_review*.py tests/test_verify_workflow_security.py` | **430 passed** |
| Full Python | `.venv/bin/python -m pytest -q` | **4254 passed**, 0 failed, 74 warnings, 307.85s |
| Node | `node --test tests/frontend/*.test.js` | **280 pass**, 0 fail |
| pyflakes | `.venv/bin/python -m pyflakes bot/ automation/ tools/ main.py tests/` | 0 findings |
| compileall | `.venv/bin/python -m compileall -q bot automation tools main.py tests` | 0 errors |
| Bandit | `.venv/bin/python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | High 0; Low 7; Medium 20 |
| Dependency audit | `.venv/bin/python -m pip_audit -r requirements-dev.txt` | No known vulnerabilities |
| Diff hygiene | `git diff --check` | clean |

No live service was called for any result.

---

## 11. Remaining blockers

- **R7-B01 automatic source:** owner decision required for conversation→repository and
  PR-candidate provenance.
- **R7-B02 worker activation:** deferred; worker remains inactive.
- **R7-B03 external resources:** blocked; no provider, disposable repository, or
  Telegram target.
- **Independent review:** deferred; this is an author implementation report, not an
  independent review.
- **R7 live validation:** not complete; no live conversation→PR resolution, provider,
  GitHub, OpenHands, Telegram, or Actions evidence.
- **Python 3.11 and remote CI:** UNVERIFIED locally.
- **R1–R7 changes:** uncommitted/untracked; no publication.

---

## 12. Classification summary

| Requirement | Classification |
|---|---|
| Conversation ID validation and watched/chat authorization | IMPLEMENTED_AND_TESTED |
| OpenHands conversation owner/authorization metadata | OWNER_DECISION_REQUIRED |
| GitHub immutable repository ID/full-name verification | IMPLEMENTED_AND_TESTED |
| Repository allowlist/token authorization | VERIFIED_NO_CHANGE_REQUIRED |
| PR base/head identity, fork, state, exact head SHA | IMPLEMENTED_AND_TESTED |
| Branch/SHA verification before/after reads | IMPLEMENTED_AND_TESTED |
| Compare/merge-base verification | IMPLEMENTED_AND_TESTED |
| CI job completeness protection | VERIFIED_NO_CHANGE_REQUIRED (existing F-01) |
| Resolver abstraction and explicit PR list | IMPLEMENTED_AND_TESTED |
| Trusted conversation→repository source | OWNER_DECISION_REQUIRED |
| Trusted PR-candidate source | OWNER_DECISION_REQUIRED |
| Provenance persistence in DB | OWNER_DECISION_REQUIRED |
| Fork/cross-repository support | VERIFIED_NO_CHANGE_REQUIRED (rejected by default) |
| Rename/transfer acceptance policy | OWNER_DECISION_REQUIRED |
| Membership immutability/conflict/pending/retry | IMPLEMENTED_AND_TESTED |
| Worker activation/startup wiring | DEFERRED |
| Live validation | BLOCKED |
| Independent review | DEFERRED |
| R8 | DEFERRED |

---

## 13. Safety confirmation

- No OpenHands API call, GitHub API call/write, provider inference, Telegram message,
  workflow dispatch, or external data transmission occurred.
- No worker activation or startup wiring.
- No production database access or migration.
- No secrets in this report.
- No commit, push, PR, merge, deployment, release, or destructive Git operation.
- `.openhands/`, unrelated files, and historical reports were preserved.
- Autopush remains disabled/inactive.
- Independent review remains deferred.
- R8 has not started.
