# OHB2-R7-B01 — Conversation → PR → Exact SHA Decision (2026-11-25)

**Task:** `OHB2-R7-REMEDIATION-AND-LOCAL-VERIFICATION`
**Status:** `R7_B01_OWNER_DECISION_REQUIRED`
**Review scope:** repository code and documentation only.
**Live operations:** none. No OpenHands or GitHub API call was made.

---

## 1. Current implementation and evidence

The review pipeline can run only from an explicit membership snapshot. It has no
trustworthy resolver from an OpenHands conversation to a repository PR and exact SHA.

Evidence:

- `AutoReviewMembership` requires `repository_id`, `repository_full_name`, `pr_number`,
  `branch`, `base_sha`, and `head_sha` (`bot/db.py:898`).
- `reserve_conversation_review()` validates and snapshots those caller-supplied values;
  it does not discover them (`bot/db.py:8110`).
- `ReviewRunner.run()` reads the persisted memberships and never resolves a PR from a
  conversation (`bot/review/worker.py:122`).
- `OpenHandsClient.start_conversation()` sends `selected_repository` and
  `selected_branch`; it does not send a PR number
  (`bot/openhands_client.py:386-397`).
- The UI/message helper treats `pr_number` as possibly a list (`bot/messages.py:93-95`),
  while review membership validation requires a positive integer (`bot/db.py:325-327`).
  Any resolver must normalize or reject that shape explicitly.
- No code reads a PR identity from a conversation to create a review cycle. No commit
  trailer, PR-reference convention, or trust rule is implemented.

The result: R3–R6 can be exercised with an explicit membership snapshot, but that is
not an automatic conversation → PR → exact SHA binding.

---

## 2. Exact missing relationship

There is no verified chain of the form:

```text
OpenHands conversation
  -> repository identity
  -> PR number
  -> current head branch
  -> exact head SHA
  -> persisted AutoReviewMembership
```

The existing API can validate the last step if a caller supplies all values. It cannot
prove that the conversation actually produced that PR or that the SHA is the PR's
current head.

---

## 3. Viable design options

### Option A — verified resolver from conversation metadata plus GitHub PR API

Use conversation repository/branch metadata and a PR candidate only as untrusted input,
then verify against GitHub before reserving a cycle:

1. Require exactly one PR number; normalize an integer or a one-item list; reject
   missing, multiple, zero, negative, or non-integer values.
2. Resolve the repository's stable GitHub repository id and verify it is allowlisted.
3. Verify the PR's head repository, head branch, base SHA, and current head SHA against
   the conversation's repository/branch and requested commit.
4. Reject on any mismatch; never treat conversation metadata as proof.
5. Persist the verified membership and exact SHA atomically with the reservation.

This is the only option that can support real automatic review. It needs an owner-approved
trust rule and negative tests for forged/missing/ambiguous metadata, PRs from another
repository, moved branches, multiple PRs, retries, and process restarts.

### Option B — explicit controlled membership association (canary only)

Keep the existing explicit `AutoReviewMembership` snapshot and require an operator or
controlled harness to supply it. The system does not claim to discover the PR. This is
safe for a local/controlled canary and requires no schema change, but it does not close
B01 and must not be reported as end-to-end conversation binding.

### Option C — new PR-reference or commit-trailer convention

A trailer or task-metadata convention could carry a PR number, but it would create a new
identity convention. No parser exists, and the task forbids inventing one without owner
approval. It also remains forgeable unless Option A's GitHub verification is applied.

---

## 4. Security and spoofing risks

| Risk | A | B | C |
|---|---|---|---|
| Forged conversation metadata | Mitigated by GitHub verification | Caller-controlled; no discovery claim | Metadata remains untrusted; needs A's verification |
| PR from another repository | Rejected by repository id/allowlist | Caller must supply correct repo | Can point at another repo unless verified |
| Branch movement after discovery | Rejected by exact head SHA and final branch check | Caller supplies exact SHA; collector verifies | Stale trailer can point at an old SHA |
| Multiple PRs / ambiguous PR | Explicitly rejected | Caller must choose; no claim | Ambiguous trailer |
| Process restart / retry | Persisted verified snapshot is idempotent | Persisted explicit snapshot | Depends on parser/idempotency |
| Secret leakage | No change; resolver must not log credentials | No change | No change |

The conversation-wide review scope already approved is not reopened by this decision.

---

## 5. Migration and backward compatibility

- **Option A:** no mandatory schema change is required for the resolver itself; the
  existing membership tables can store the verified result. A new resolver boundary and
  failure state are needed. Existing explicit reservations remain valid.
- **Option B:** fully compatible with the current schema and R5 APIs; no migration.
- **Option C:** may require a new parser/identity field and migration; not recommended
  without a separate approved design.

No migration was performed in this task.

---

## 6. Test requirements before implementation

Option A would require deterministic mocked tests for:

- exact conversation → repository → PR → SHA match;
- missing, multiple, malformed, zero, and negative PR identifiers;
- list-shaped PR metadata;
- PR from another repository or head repository;
- branch moved before/during collection;
- PR head SHA mismatch and compare/run SHA mismatch;
- GitHub verification failure, missing SHA, and malformed response;
- retries, restarts, duplicate reservations, and idempotency;
- no provider call before a verified binding.

No live GitHub or OpenHands call is required for these tests.

---

## 7. Recommendation

Do not select an option silently. For a real automatic review path, **Option A** is the
only option that can establish the missing relationship safely, provided the owner
approves the trust rule and a separate reviewed implementation task. **Option B** is
acceptable only as an explicitly labelled controlled canary and leaves B01 unresolved.
**Option C** is not recommended without a separate approved identity design.

---

## 8. Exact owner decision required

The owner must choose one:

1. **Approve Option A:** authorize a verified resolver with the GitHub trust rule above,
   as a separate implementation task with the listed negative tests; or
2. **Approve Option B only:** authorize a controlled canary that supplies memberships
   manually, with B01 recorded as unresolved and no end-to-end claim; or
3. **Reject both for now:** keep R7 live validation blocked and leave the explicit
   membership harness as the only local mechanism.

Until the owner decides, R7-B01 remains `R7_B01_OWNER_DECISION_REQUIRED`; no resolver,
trailer convention, or trust rule is implemented.
