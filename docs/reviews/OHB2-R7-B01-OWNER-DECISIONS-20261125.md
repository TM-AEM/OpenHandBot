# OHB2-R7-B01 — Owner Decisions Required (2026-11-25)

**Task ID:** `OHB2-R7-B01-VERIFIED-RESOLVER-DESIGN-AND-LOCAL-IMPLEMENTATION`
**Status:** `R7_B01_OWNER_DECISION_REQUIRED`
**Purpose:** record the exact decisions needed to turn the local verifier into an
authorized automatic conversation→PR→exact-SHA resolver.

No decision below is approved by this document. No automatic source, new identity
convention, worker activation, live call, or publication was performed.

---

## 1. What is already implemented locally

The local verifier can:

- require an explicit conversation ID and an existing `watched.chat_id` authorization;
- accept an explicitly supplied `ConversationRepositoryLink` claim;
- verify the claim against GitHub's immutable numeric repository ID and full name;
- require explicit PR numbers (it never guesses one);
- verify PR base/head repository identity, refs, open/non-merged state, and head SHA;
- verify the branch points to the exact SHA before and after reads;
- derive/verify the merge-base with read-only compare calls;
- reject forks, cross-repository PRs, closed/merged PRs, moved branches, malformed
  responses, and ambiguous repository identity;
- return immutable `AutoReviewMembership` values with source/provenance;
- reserve through the existing atomic R2/R5 API without partial inserts.

It does **not** choose where the conversation→repository link or PR candidates come
from. That is the unresolved identity decision.

---

## 2. D-01 — Conversation-to-repository source

### Option A — OpenHands structured metadata as candidate only

Use the conversation's `selected_repository` (and possibly `selected_branch`) as
untrusted candidates. Verify the repository through GitHub immutable ID/full name before
creating membership.

- Evidence: `bot/openhands_client.py:386-397` sends `selected_repository` and
  `selected_branch`; `bot/messages.py:92-101` treats `pr_number` as a possible list.
- Advantage: supports a more automatic flow if OpenHands metadata is trustworthy for
  the authorized conversation.
- Required owner decision: whether `selected_repository` is authoritative enough to be a
  candidate for this bot's conversations, and whether an OpenHands owner/service-account
  check is required.
- Risk: metadata may be user-controlled or changed after creation; it must never be
  treated as proof without GitHub verification.

### Option B — Explicit server-side owner mapping

Store or supply a mapping from `conversation_id` to the expected numeric
`repository_id` and display name, in an explicitly authorized owner/server record.
Verify that mapping through GitHub.

- Advantage: strongest local trust boundary; no reliance on conversation text or
  user-editable metadata; suitable for a controlled canary.
- Required owner decision: where the mapping lives, who may write it, retention, and
  whether it is a temporary canary or a durable mechanism.
- Limitation: not automatic discovery; the owner/harness must associate the
  conversation.

### Option C — New commit-trailer or PR-reference convention

Create a bot-issued token/trailer or other new identity convention and correlate it to a
commit/PR.

- Advantage: can provide an auditable correlation if implemented carefully.
- Required owner decision: the convention, token lifecycle, replay protection, search
  window, ancestry rule, and how to handle copied/duplicated tokens.
- Risk: new architectural convention; not approved by this task and not recommended
  without a separate design approval.

### Recommendation

Do not select silently. For a controlled canary, Option B is the least trusting and
does not require a new OpenHands metadata trust assumption. For a future automatic
flow, Option A may be viable only after the owner explicitly approves
`selected_repository`/`pr_number` as candidate metadata plus GitHub verification and an
authorization rule.

---

## 3. D-02 — PR candidate source

The verifier currently requires explicit positive PR numbers.

Options:

1. **OpenHands `pr_number` metadata as candidates.** It is a documented field shape
   (possibly an array), but population semantics are unverified. Normalize exactly one
   positive integer or reject multiple/empty/malformed values; never auto-select the
   first candidate.
2. **Explicit owner/server PR list.** The owner/harness supplies PR numbers; the verifier
   checks all of them. This is compatible with the current implementation and is the
   conservative canary option.
3. **New correlation convention.** Requires D-01 Option C approval and additional
   security tests.

Required decision: approve one source and its behavior for zero, one, or multiple PRs.
The approved conversation-wide scope remains: one active cycle per conversation,
multiple eligible PRs may be members, membership immutable after start.

---

## 4. D-03 — Conversation authorization source

Current implementation uses `watched.chat_id` and rejects deleted conversations. This is
the existing bot authorization boundary, not proof of OpenHands account ownership.

Decide whether:

- `watched.chat_id` plus the bot's owner allowlist is sufficient for review
  authorization; or
- an explicit OpenHands owner/service-account check must be added before resolution.

No such external check was added.

---

## 5. D-04 — Provenance persistence

The resolver returns `source`, repository/PR/SHA, and `verified_at` in
`MembershipProvenance`, and `reserve_resolved_memberships` validates it. The existing
schema has no dedicated provenance column/table.

Decide whether to:

- keep provenance in the in-memory result/report only (no schema change); or
- add an additive append-only audit table/columns for source, verification time,
  repository ID/full name, PR, head/base SHA, and evidence fingerprint.

A schema change was not made.

---

## 6. D-05 — Rename/transfer policy

Current behavior:

- repository ID mismatch → `repository_id_mismatch`;
- repository name mismatch with a stable ID → `repository_rename_ambiguous`.

Decide whether the owner approves accepting a GitHub rename/transfer when the immutable
numeric ID is unchanged, or requires the conservative rejection currently implemented.

---

## 7. D-06 — Fork/cross-repository policy

Current behavior rejects any PR whose head repository ID/name differs from the base
repository. This avoids fork ambiguity.

Decide whether fork PRs should remain unsupported (current conservative default) or
whether an explicit fork policy is approved. No fork support was added.

---

## 8. D-07 — Worker activation

R7-B02 remains deferred. `bot/app.py` does not construct `ReviewWorker` or
`ReviewRunner`, and no startup wiring exists.

Any activation requires separate approval and a reviewed implementation covering:

- explicit construction/startup wiring;
- configuration and authorization validation;
- disabled-by-default behavior;
- graceful shutdown;
- lease acquisition/expiry/recovery;
- duplicate-owner protection;
- crash/restart tests;
- no external call before authorization/pinned evidence.

`REVIEW_ENABLED=1` alone must continue to mean configuration eligibility only.

---

## 9. D-08 — Live validation resources and authorization

R7 live validation remains blocked because no authorized provider, disposable GitHub
repository, Telegram target, or live OpenHands/GitHub access is configured.

Decide whether to authorize a future live validation with:

- an explicit test conversation ID;
- an authorized allowlisted repository and PR;
- a provider/model and cost/consent policy;
- a Telegram test target;
- a rollback/cleanup plan;
- an independent reviewer.

This task performed none of these external operations.

---

## 10. D-09 — Independent review and R8

- Independent review of R7/R7-B01 remains deferred.
- R8 has not started.
- No publication occurred.

Decide when to request an independent review and whether R8 may begin before the
remaining B01/B02/B03 items are closed.

---

## 11. Exact approval format

The owner can approve by recording, for each decision:

```text
D-01: A | B | C | reject-for-now
D-02: OpenHands-candidate | explicit-list | new-convention | reject-for-now
D-03: watched-chat | OpenHands-owner-check | reject-for-now
D-04: in-memory-only | additive-audit-schema | reject-for-now
D-05: reject-rename | accept-stable-id | reject-for-now
D-06: reject-fork | approve-fork-policy | reject-for-now
D-07: keep-deferred | approve-activation-task
D-08: keep-blocked | authorize-live-validation
D-09: keep-deferred | request-independent-review
```

Until these are recorded, the automatic conversation→PR→SHA relationship is
`R7_B01_OWNER_DECISION_REQUIRED`.
