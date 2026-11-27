# OHB2-R7-B01 — Author Self-Review (2026-11-25)

**Task ID:** `OHB2-R7-B01-VERIFIED-RESOLVER-DESIGN-AND-LOCAL-IMPLEMENTATION`
**Review type:** author self-review only.
**Status:** `R7_B01_OWNER_DECISION_REQUIRED` for the automatic identity gap; the safe
local verifier components are implemented and locally tested.
**Not:** independent review, live validation, or a claim that conversation→PR resolution
works against real services.

No live operation, worker activation, external transmission, or Git publication was
performed.

---

## 1. Acceptance criteria check

| Criterion | Result | Evidence |
|---|---|---|
| Baseline audit without assuming old report values | MET | Re-read branch/HEAD/main/tree/status and inspected all requested areas |
| Identity/trust analysis | MET | Report §3; repository ID, PR base/head, SHA, authorization boundaries |
| Independently safe resolver components | MET | `bot/review/resolver.py`; GitHub repository/PR read primitives |
| No unapproved identity convention | MET | Concrete conversation→repository and PR-candidate sources remain injected/owner decisions |
| Membership compatibility and immutability | MET | Existing `AutoReviewMembership` and atomic reservation; tests |
| Required 25 negative/positive cases | MET | 32 focused resolver tests, including all 25 required cases |
| Rejected resolution cannot invoke provider | MET BY CONSTRUCTION | Resolver has no provider dependency; rejection tests assert zero `auto_reviews` rows |
| No worker activation/startup wiring | MET | `bot/app.py` unchanged for review worker |
| Runbook/architecture documentation | MET | `docs/OPERATIONS_RUNBOOK.md` §11 |
| Full local verification | MET | 4254 Python passed, 280 Node passed, lint/security/audit clean |
| No live operations/publication | MET | No external calls; no commit/push/PR/merge/deploy/release |
| Automatic conversation→PR resolution | NOT MET / OWNER DECISION | No trusted source implemented |
| Independent review | NOT MET / DEFERRED | This is an author self-review |

---

## 2. Self-review findings

### S1 — Resolver is a verifier, not a discovery engine (intentional)

`ConversationMembershipResolver` requires a `ConversationRepositoryLinkSource` and
explicit PR numbers. It does not read `selected_repository`, `pr_number`, prompt text,
branch names, PR descriptions, or PR URLs as proof. This is intentionally conservative:
the source of the conversation→repository link and PR candidates remains an owner
decision. A future source must pass candidates through this verifier, not replace it.

Residual: a caller with DB access can supply a link claim. That is explicit, not
automatic; the resolver still verifies GitHub identity. A concrete production source
must be authorized separately.

### S2 — GitHub primitives are read-only and strict

`get_repository()` and `get_pull_request()` use the existing `_request_json` path:
GET only, no redirects, no token in URL, response-size cap, allowlist before HTTP.
Parsers reject missing IDs, invalid repo/ref/SHA, PR number mismatch, and missing
base/head repository identity.

Residual: GitHub API behavior and live response shapes are not exercised against the
real service; only mocked transports were used.

### S3 — Exact SHA and branch checks are fail-closed

The resolver checks branch SHA before and after all reads, re-reads the PR, verifies
PR head/base repository identity and open/non-merged state, and requires exact compare
base/head evidence. A base-tip compare that is not the merge-base is resolved by a
second compare against the merge-base; a mismatch fails.

Residual: the collector still performs its own before/after branch checks and F-01 CI
completeness check; these were not weakened.

### S4 — Membership integrity uses the existing model

The resolver emits the existing `AutoReviewMembership`; ordering, duplicate rejection,
conflict detection, pending-new-PR behavior, and atomic insertion remain in `bot/db.py`.
No new concurrency model or lifecycle was added. `reserve_resolved_memberships`
validates provenance-to-membership consistency before calling the existing reservation.

Residual: provenance is not persisted in a dedicated column/table. The report lists
that as an owner decision; no schema change was made.

### S5 — Authorization is local, not OpenHands-owner proof

Authorization requires a `watched` row and matching `chat_id`; deleted conversations are
rejected. This is the existing bot authorization boundary. It does not prove an
OpenHands account owner. The owner must decide whether this is sufficient for live
review or whether an OpenHands owner/service-account check is required.

### S6 — Worker remains inactive

No `ReviewWorker`/`ReviewRunner` construction or startup wiring was added. The runbook
continues to distinguish configuration existence, feature eligibility, worker
activation, and external execution.

---

## 3. Test review

- Focused resolver tests: **32 passed**.
- Required cases 1–25 are represented in the report table.
- Additional tests cover conversation-link mismatch, final branch movement, empty
  resolution result, malformed GitHub payloads, and repository/PR parser behavior.
- Every rejection test asserts no `auto_reviews` row was inserted.
- The resolver has no reviewer-provider dependency, so rejected resolution cannot
  invoke a provider.
- No test was disabled, skipped, or weakened.

Potential test limitation: mocks model GitHub/DB behavior; they do not prove live API
compatibility or real concurrency under production load.

---

## 4. Local verification review

| Check | Result |
|---|---|
| Resolver | 32 passed |
| Membership/immutability | 23 passed |
| R5 lifecycle | 30 passed |
| R3 branch/SHA | 8 passed |
| F-01 CI completeness | 15 passed |
| F-02 ProviderBinding | 11 passed |
| Recovery | 6 passed |
| Collector | 3 passed |
| Worker integration | 1 passed |
| R6 report | 11 passed |
| R6 delivery | 8 passed |
| All review-focused | 430 passed |
| Full Python | 4254 passed, 0 failed, 74 warnings, 307.85s |
| Node | 280 pass, 0 fail |
| pyflakes | 0 findings |
| compileall | 0 errors |
| Bandit | High 0; Low 7; Medium 20 |
| pip-audit | No known vulnerabilities |
| `git diff --check` | clean |

Python 3.11 and remote CI were not verified. No live call was made.

---

## 5. Documentation review

- The resolver report clearly separates implemented verifier behavior from the
  unresolved automatic source.
- It does not claim live conversation→PR resolution, independent review, or a live PASS.
- It records exact baseline Git values and distinguishes committed from working-tree
  changes.
- It records exact commands/results and environment versions.
- The runbook section does not imply that `REVIEW_ENABLED=1` activates the worker.
- Owner decisions are explicit and do not silently select a new convention.
- No secret value appears in the reports.

---

## 6. Conclusion

The safe local verifier and membership-integrity components are implemented and tested.
The automatic conversation→PR→SHA relationship remains unresolved because the trusted
conversation→repository and PR-candidate sources require owner decisions. No live
validation or publication occurred. This is an author self-review, not independent
verification.
