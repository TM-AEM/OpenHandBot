# OHB2-R7 — Canary Linkage Owner Decision Request (2026-11-25)

**Task ID:** `OHB2-R7-CANARY-LINKAGE-IMPLEMENTATION-AND-LOCAL-VERIFICATION`
**Status:** `OWNER_DECISION_REQUIRED`
**Purpose:** request the exact approvals needed before any D-01/D-02 implementation.

> **Update (2026-11-25):** the follow-up task
> `OHB2-R7-CANARY-LINKAGE-D01B-D02-EXPLICIT-LIST` provisionally approved the bounded
> choices. Sections 1–7 preserve the pre-approval request; section 8 records the
> update. D-03 through D-09 remain unresolved.

Sections 1–7 did **not** approve D-01 or D-02 and did not authorize implementation,
schema changes, worker activation, live calls, or publication. At that time the
repository contained no explicit owner decision for either item.

---

## 1. Why a decision is required

The current code can verify a supplied repository/PR/SHA membership, but it does not
choose a trusted conversation→repository source or discover PR candidates.

The proposed bounded canary inputs are:

- **D-01:** local `creation_jobs.repo` + `conversation_id` for bot-created conversations,
  followed by GitHub numeric-ID/full-name verification.
- **D-02:** an explicit owner-supplied list of PR numbers, verified through the existing
  resolver; no automatic PR discovery.

These are proposals, not approved architecture. The existing safe resolver remains
unchanged until the owner records the decision.

---

## 2. Exact D-01 decision

```text
D-01: A | B | C | reject-for-now
```

- **A — OpenHands candidate only:** use `selected_repository` as a candidate, verify
  GitHub numeric ID/full name, and never treat it as authoritative. It is mutable and
  user-supplied; it does not cover rename/reuse by itself.
- **B — Local creation context (proposed canary):** use `creation_jobs.repo` associated
  with the exact `conversation_id`, only for conversations created by this bot. Require
  exactly one `done` job, owner `chat_id`, a strict `owner/repo` value, OpenHands
  `selected_repository` equality, and GitHub numeric-ID/full-name verification. Reject
  missing/duplicate/conflicting/malformed/ambiguous rows. Do not fall back to
  `selected_repository`.
- **C — Explicit owner/server mapping:** add an owner-controlled conversation→repository
  mapping with a numeric repository ID. Strongest, but requires new storage and a
  separate schema/config approval.
- **reject-for-now:** keep explicit membership/canary only; no automatic D-01.

**Proposed canary choice:** B.

**Explicit limitation of B:** `creation_jobs` stores only `repo` and `conversation_id`,
not the GitHub numeric ID observed at creation. A deleted-and-recreated repository with
the same name cannot be distinguished from the original. B is therefore a bounded
canary input, not an authoritative identity closure. Durable `repository_id` capture
would require a separate additive-schema decision.

---

## 3. Exact D-02 decision

The owner-decision document's format is:

```text
D-02: OpenHands-candidate | explicit-list | new-convention | reject-for-now
```

- **OpenHands-candidate:** use OpenHands `pr_number` as a candidate only; normalize
  scalar/one-item list, reject empty/multiple/malformed, and verify every PR through
  GitHub. Population semantics are unverified; all 20 previously observed org
  conversations had an empty list, and the bot never sends it.
- **explicit-list (proposed canary):** require a non-empty, unique list of positive
  integers supplied by the authorized owner; reject empty/duplicate/malformed/over-limit
  input; verify every PR belongs to the verified repository and exact SHA; never choose
  the first PR from an ambiguous set.
- **new-convention:** a new PR-reference/trailer convention; not implemented and not
  recommended without a separate design approval.
- **reject-for-now:** no automatic PR discovery; keep explicit membership/canary only.

**Proposed canary choice:** `explicit-list`.

**Explicit limitation:** this is not PR discovery. It does not use OpenHands `pr_number`,
branch names, PR URLs, or GitHub search. It does not close D-02 as automatic discovery.

---

## 4. Proposed implementation scope if both are approved

Only after an explicit owner record:

1. Add a read-only DB query for done creation jobs by exact `conversation_id`.
2. Add a `CreationJobRepositoryLinkSource` adapter behind the existing
   `ConversationRepositoryLinkSource` protocol.
3. Add a canary-only `CanaryLinkageService` that requires `chat_id == owner_id` and
   accepts only explicit PR numbers.
4. Add D-01/D-02 tests from the main report's test plan.
5. Run focused and full local verification.
6. Request independent review.
7. Do not wire the adapter into `bot/app.py`; worker activation remains a separate
   decision.
8. Do not add schema, migrations, PR discovery, or OpenHands `pr_number` use.

### Not included

- No all-conversations D-01 claim.
- No automatic PR discovery.
- No durable provenance schema.
- No worker activation.
- No live validation.
- No OpenHands/GitHub/provider/Telegram calls.
- No commit/push/PR/merge/deploy/release.

---

## 5. Prerequisites that remain open

Even if D-01 B and D-02 explicit-list are approved, the following remain separate:

- **D-03** — whether `watched.chat_id` plus owner allowlist is sufficient authorization,
  or an OpenHands owner/service-account check is required.
- **D-04** — whether provenance must be persisted (additive audit schema) or remain
  in-memory/report-only.
- **D-05** — rename/transfer policy; current behavior rejects name mismatch even with a
  stable ID.
- **D-06** — fork/cross-repository policy; current behavior rejects forks.
- **D-07** — worker activation; currently deferred and unwired.
- **D-08** — live resources/authorization; currently blocked.
- **D-09** — independent review and R8; currently deferred.

The canary design is compatible with the current conversation-wide scope and immutable
membership model. It does not authorize changing those semantics.

---

## 6. Approval record

The owner may record the exact choice in this file or in the existing owner-decision
record. No option is selected by this request.

Example, only if the owner chooses the proposed canary:

```text
D-01: B
D-02: explicit-list
```

Until such a record exists, the status remains:

```text
R7_CANARY_LINKAGE_OWNER_DECISION_REQUIRED
```

---

## 7. Safety statement (pre-approval state)

- No implementation occurred at the time of this request.
- No resolver change occurred at the time of this request.
- No schema/migration/table/index/trigger change occurred at the time of this request.
- No tests were created at the time of this request; only existing tests were run.
- No live OpenHands/GitHub/provider/Telegram operation occurred.
- No worker activation occurred.
- No Git publication occurred.
- Independent review remains deferred.
- R7 live validation and R8 have not started.

---

## 8. Decision update (2026-11-25)

The follow-up task `OHB2-R7-CANARY-LINKAGE-D01B-D02-EXPLICIT-LIST` provisionally
approved the bounded canary choices:

```text
D-01: B
D-02: explicit-list
```

The implementation is limited to bot-created conversations and explicit owner-supplied
PRs. It does not close D-01 for arbitrary conversations or add PR discovery.

See `docs/reviews/OHB2-R7-CANARY-LINKAGE-IMPLEMENTATION-REPORT-20261125.md`.
D-03 through D-09 remain unresolved.
