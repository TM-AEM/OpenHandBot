# OHB2 B01 — Conversation-to-PR Binding Decision (R7 remediation)

**Status:** `R7_B01_OWNER_DECISION_REQUIRED`  
**Task:** `OHB2-R7-REMEDIATION-AND-LOCAL-VERIFICATION`  
**Date:** 2026-11-25  
**Live operations:** none. This report is based on repository code only.

## 1. Finding

R7 correctly identified that the review system has no automatic, trustworthy
conversation-to-PR resolver. The local code proves the gap without needing a live
call:

- `AutoReviewMembership` requires `repository_id`, `repository_full_name`,
  `pr_number`, `branch`, `base_sha`, and `head_sha` (`bot/db.py:898-906`).
- `reserve_conversation_review` validates those values and snapshots them, but the
  caller must already know them (`bot/db.py:8110-8270`).
- `ReviewRunner.run` reads the persisted memberships and never discovers a PR from
  the OpenHands conversation (`bot/review/worker.py:122-136`).
- The OpenHands client exposes `selected_repository` when starting or patching a
  conversation (`bot/openhands_client.py:380-395`), but it does not expose a PR
  identity or a stable repository id.
- The UI helper treats `pr_number` as possibly a list (`bot/messages.py:92-101`),
  while review membership validation requires a positive integer
  (`bot/db.py:325-327`). A resolver must normalize or reject this shape explicitly.
- No code currently reads a PR number from the conversation to create a review
  cycle, and no trailer/PR-reference convention is implemented. Adding one would be
  a new identity convention, which this task must not invent silently.

The result is that R3–R6 can be exercised with an explicit membership snapshot, but
that is not the same as an automatic end-to-end binding from a real conversation.

## 2. Viable design options

### Option A — verified resolver from conversation metadata + GitHub PR API

Use `selected_repository` plus the conversation's `pr_number` metadata as a
*candidate*, then verify it against GitHub before reserving a cycle:

1. Require exactly one PR number (normalize an integer or a one-item list; reject
   missing, multiple, zero, negative, or non-integer values).
2. Resolve the repository's stable GitHub `repository_id` and verify the PR belongs
   to the allowlisted repository.
3. Verify the PR's head repository, head branch, base SHA, and current head SHA
   against the conversation's repository/branch and the requested commit.
4. Reject on any mismatch; never treat conversation metadata as trusted proof.

This is the only option that can support real automatic review. It requires an
owner-approved trust rule and tests for forged/missing/ambiguous metadata, a PR from
another repository, a moved branch, multiple PRs, and restart/idempotency. It does
not require a schema change, but it does require a new resolver boundary and a clear
failure state when metadata is absent.

### Option B — explicit controlled membership association (canary only)

Keep the existing explicit `AutoReviewMembership` snapshot and require an operator
or controlled harness to supply it. The system does not claim to discover the PR.
This is compatible with the current DB/API and is safe for a local or controlled
canary, but it does **not** close B01 and must not be reported as end-to-end
conversation-to-PR binding.

### Option C — new PR-reference/trailer convention (not recommended now)

A trailer or task-metadata convention could carry the PR number, but it would create
a new identity convention. The current code has no such parser, and this task must not
invent one without explicit owner approval. It also remains forgeable unless the
GitHub verification in Option A is applied.

## 3. Comparison

| Criterion | A | B | C |
|---|---|---|---|
| Automatic discovery | Yes | No | Yes, only if every producer follows the convention |
| Trust/forgeability | Can be made safe with GitHub verification | Caller-controlled; no discovery claim | Metadata remains untrusted; needs A's verification |
| Compatibility with current schema | No schema change required | No schema change | No schema change, but new convention |
| R7 live readiness | Can become ready after owner approval + tests | Not ready; canary only | Not recommended without owner approval |
| Risk of false PASS | Low if fail-closed | Low, but cannot validate the missing link | High if metadata is trusted |

## 4. Recommendation and required owner decision

Do **not** select an option silently. The owner must choose one of these two
decisions:

- **A (production path):** approve a verified resolver with the trust rule above;
  then implement it as a separate, reviewed task with the listed negative tests.
- **B (controlled canary path):** approve an explicitly labelled canary that supplies
  memberships manually; keep B01 recorded as unresolved and do not call it
  end-to-end.

For R7 live validation, Option A is required before claiming conversation-to-PR
readiness. Option B is acceptable only as a controlled, clearly labelled exercise.

## 5. What this remediation does not claim

- No live GitHub, Telegram, OpenHands, or provider calls were made.
- No resolver was implemented.
- No existing review PASS was produced or fabricated.
- No change was made to the approved conversation-wide architecture.
