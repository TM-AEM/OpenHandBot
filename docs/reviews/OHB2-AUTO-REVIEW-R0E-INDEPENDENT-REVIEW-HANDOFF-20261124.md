# OHB2-AUTO-REVIEW-R0E — Independent Review Handoff

> **PROPOSED — NOT OWNER APPROVED — NOT IMPLEMENTED**

**Task ID:** `OHB2-AUTO-REVIEW-R0E`
**Date:** 2026-11-24
**Purpose:** handoff package for a genuinely separate independent reviewer.
**Baseline:** `01079676351aac869d09d4d1747661cd6f07d82b` (tree `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc`).

---

## 1. Independence requirement (read first)

This handoff is addressed to a **different session/agent** from the one that authored R0C/R0D/R0E.

**A same-agent re-check is not an independent review.** The repository's own convention says so:
`docs/reviews/OHB2-WP08-BATCH-INDEPENDENT-REVIEW-REPORT-20261124.md` states that a same-agent
re-check is not a separate reviewer session. If the reviewer shares the authoring session, the
review must be labelled `INDEPENDENCE_NOT_ESTABLISHED` and must not be presented as third-party
review.

The reviewer must not modify implementation code, schema, tests, workflows, configuration, or
production state. This handoff does not authorize R1.

---

## 2. Exact source artifacts and hashes

### 2.1 R0E artifacts (new; proposed)

| Artifact | Path | SHA-256 |
|---|---|---|
| Remediation report | `docs/reviews/OHB2-AUTO-REVIEW-R0E-DESIGN-REMEDIATION-REPORT-20261124.md` | `b03156fa0892acd4dbfea90b3800b945abb651473015dfb70786423fd943d7e4` |
| Revised design | `docs/reviews/OHB2-AUTO-REVIEW-R0E-REVISED-DESIGN-20261124.md` | `d15b7649b87d712c187b560865c7c1aa90e69e8bbeda84a55384a497694a3e9c` |
| This handoff | `docs/reviews/OHB2-AUTO-REVIEW-R0E-INDEPENDENT-REVIEW-HANDOFF-20261124.md` | hash computed after creation; see §12 |

### 2.2 Historical artifacts (NOT available as saved repository files)

| Artifact | Availability | Status |
|---|---|---|
| R0 report | Not saved in repository | `UNVERIFIED` as an artifact |
| R0A report | Not saved | `UNVERIFIED` |
| R0B report | Not saved | `UNVERIFIED` |
| R0C report | Not saved; conversation excerpt truncated at §7 | §§8–16 `UNVERIFIED`; not reconstructed |
| R0D report | Not saved; conversation only | Findings summarized below; full artifact `UNVERIFIED` |
| D1 decisions | Task prompts/conversation, not a saved decision record | Historical owner decisions; no design approval implied |

**Do not treat this handoff as a recovered R0C/R0D artifact.** It is a new R0E proposal that uses
the R0D findings as review input.

### 2.3 Baseline code/document hashes

| File | SHA-256 |
|---|---|
| `AGENTS.md` | `1cab89465afdaf9cb793c41d52e6c2c400e6bcbcad73d9d38060414e922f607b` |
| `bot/db.py` | `18c350ecb6b138d324820a068b60b6686bb999b3aa8a580746fe3e643720141d` |
| `bot/app.py` | `70870c649b0fa1b9ba3f27bea227b521902ee7395ad6d29011249b4bf465b031` |
| `bot/outbox.py` | `adfee59757613725e16077e3419487f388fc09b5195cadcd4715a099d3db778a` |
| `bot/openhands_client.py` | `734a34d12b78b7e0dfd80e7bc7a4e2daee513924c696bfaa9cd05509f74cbfea` |
| `bot/messages.py` | `f24ebdf9531c110685573721f3518ad7b2b0bd39d77e212cee1df638657c82bd` |
| `docs/API_NOTES.md` | `ee4b666ab458b0dbbb077421aef34389f16f909cb62afb62f8c62ac192d1df1b` |
| `.github/workflows/ci.yml` | `f030d01a9ab22079af26ab9139ffd717f13391ff9e339d1646e29bdcabdeda79` |
| `.github/workflows/f02-review.yml` | `411314b7adf4e071b120d40f78ba414b01265c047ebd1c878edb873774f6f41c` |

---

## 3. Baseline SHAs

| Item | Value |
|---|---|
| Repository | `/workspace/project/OpenHandBot` |
| Branch | `openhands-workspace-11liARbsA7OSSoFJOM2RDr` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `origin/main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| Tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| Upstream | none |
| Worktree | clean before R0E artifacts; three new untracked docs after |
| Open PRs | #7 `31dec52…`, #8 `6a1ca2e…`, #9 `1a84cad…` |

---

## 4. D1 decisions and evidence status

| # | D1 decision | Evidence status |
|---|---|---|
| 1 | Reviewer model differs from OpenHands execution model | Execution model observed as `openhands/deepseek-v4.1-flash`; reviewer candidates `moonshotai/kimi-k3.1-pro` etc.; **alias-level**, exact upstream version `UNVERIFIED`. |
| 2 | Blind and Adversarial are separate stages | Design requirement; not implemented. |
| 3 | Both use same reviewer model | Design requirement; single `provider_snapshot_id`. |
| 4 | Blind cannot access report/verdict | **Critical**; R0C allowlist was unsafe; corrected in R0E. |
| 5 | Adversarial sees report + Blind result | Design requirement. |
| 6 | Deterministic verdict | Design requirement; rule table proposed. |
| 7 | Direct provider API via adapter | Design requirement; no provider call made. |
| 8 | Proxy optional | Design requirement. |
| 9 | Immutable snapshots per cycle | Design requirement; mandatory triggers proposed. |
| 10 | Model switching future only | Design requirement. |
| 11 | Second reviewer deferred | Design requirement. |

No D1 decision is changed by R0E.

---

## 5. R0D findings that must be challenged

R0D concluded `R0D_NEEDS_REDESIGN` with these critical findings:

- **D-01:** stage-based uniqueness conflated lifecycle/stage/worker state; no fencing.
- **D-02:** `UNIQUE(conversation_id, head_sha)` insufficient for repository identity.
- **D-08:** Blind inputs could contain OpenHands report/verdict via commit messages, PR metadata, CI logs.
- **D-04:** hard monetary ceiling not guaranteed without balance/idempotency.
- **D-17:** multiple PRs need normalized representation.
- **B-01:** commit-trailer correlation unproven and needs constraints.
- **Source:** R0C report unavailable/truncated.
- **Independence:** R0D was same-agent; not independent.

R0E's corrections are in the revised design. The reviewer must verify they actually close these
findings, not merely rename them.

---

## 6. Corrected design summary

### 6.1 Lifecycle

- `lifecycle_state` (`ACTIVE`/`TERMINAL`), `stage`, `terminal_reason`, `lease_owner`,
  `lease_expires_at`, `lease_epoch`, `last_heartbeat_at`, `next_attempt_at`.
- `UNIQUE(conversation_id) WHERE lifecycle_state='ACTIVE'` (Alternative 1).
- Terminal rows immutable via trigger; terminal transition increments `lease_epoch` and clears lease.
- Worker writes require `ACTIVE` + owner + epoch + unexpired lease; zero rows ⇒ discard.
- Atomic supersession: terminalize old, insert new, link in `review_supersessions`, commit.

### 6.2 Identity

- `repository_id` numeric stable; full name snapshot.
- `review_prs` normalized by `(conversation_id, repository_id, pr_number)`.
- `review_cycles` per PR; `pr_id` nullable only during `AWAITING_SHA`, then required;
  `UNIQUE(pr_id, head_sha)`.
- Same SHA in two repos allowed; same PR number in two repos distinct.
- `base_sha` = merge-base; `base_ref_tip_sha` evidence; ancestry validated.
- Multiple PRs serialized conversation-wide (Alternative 1).

### 6.3 Blind isolation

- Separate `build_blind_payload` / `build_adversarial_payload`.
- Blind allowlist: diff, changed files, approved decisions, CI metadata (not logs), repo metadata.
- Blind denylist: OpenHands report/verdict, prior review, PR body/comments, commit messages, CI logs,
  conversation messages, unapproved files.
- Post-build source-type allowlist, file membership, report/prior-review fingerprint scan,
  payload hash; any failure ⇒ no provider request.

### 6.4 Billing

- Immutable `review_provider_attempts` with `billing_state`.
- `NOT_SENT`, `SENT_UNKNOWN`, `RESPONSE_RECEIVED`, `BILLING_CONFIRMED`, `BILLING_UNKNOWN`,
  `ERROR_RESPONSE`.
- Timeout/lost response = `SENT_UNKNOWN`/`BILLING_UNKNOWN`, not confirmed non-billable.
- Hard attempt limit; estimated worst-case exposure; `NEEDS_OWNER` at exposure limit.
- **No hard monetary ceiling claim.**

### 6.5 SHA/CI

- Pinned `head_sha`, `base_sha`, `merge_base_sha`, `ci_head_sha`.
- Per-check evidence table; latest suite; rerun/stale handling.
- Revalidate before Blind, Adversarial, verdict, delivery.
- Change ⇒ `SUPERSEDED`; fence worker; no delivery.
- Documented TOCTOU; no cross-system atomicity claim.

### 6.6 Verdict

- Four layers: model findings → evidence-backed findings → rule engine → final verdict.
- Findings validated against file/line/evidence in the pinned diff.
- Unsupported/duplicate/malformed handling.
- Rule table versioned; model recommendation non-authoritative.

### 6.7 Data egress

- Scanner/policy versions; consent scope/expiry/revocation; retention terms; model fingerprint.
- In-flight revocation: response may exist but is not used for verdict/delivery without owner review.
- Residual risks: scanner false negatives/positives, entropy limits, alias changes, provider retention.

### 6.8 Multi-PR and single-process

- Normalized `review_prs`; one active cycle per conversation (Alternative 1).
- In-process worker, one `Database`, one process, no second DB owner, no multi-replica.
- `review_worker_lease` startup guard.

---

## 7. Questions the reviewer must challenge

1. Does `UNIQUE(conversation_id) WHERE lifecycle_state='ACTIVE'` actually prevent all concurrent
   active cycles under SQLite `BEGIN IMMEDIATE`? Show the transaction interleavings.
2. Can a terminal cycle ever be written by a stale worker? Show the `lease_epoch` guard and the
   zero-row behavior.
3. Can a supersession transaction leave zero active cycles? Show rollback behavior.
4. Is `UNIQUE(pr_id, head_sha)` sufficient when the same SHA appears in two repos? Show the keys.
5. Does `review_prs` normalize multiple PRs without ambiguity? Show the query for the active PR.
6. Does the Blind builder actually exclude report/verdict/prior review? Try to inject each through
   diff, commit message, PR body, CI log, and prompt.
7. Does the manifest/payload hash prove what was sent? Show the exact bytes and hash.
8. Can a timeout be mistaken for a non-billable request? Show `billing_state` transitions.
9. Can the design enforce a hard monetary ceiling? If not, is the limitation explicit and bounded?
10. Does the CI evidence reject a check-run from a different SHA? Show the latest-suite logic.
11. Does base/merge-base revalidation detect a stale diff? Show the invalidation.
12. Does the deterministic rule engine ignore the model's recommendation? Show the rule precedence.
13. Can an unsupported/hallucinated finding become HIGH? Show the evidence verification.
14. Does the design preserve all 11 D1 decisions? Identify any conflict.
15. Does the design introduce a second DB owner, process, or replica? Show the startup guard.
16. Is B-01's commit-trailer mechanism sufficient? Challenge token copying, multiple PRs, ancestry,
    rebase/force-push, and trust boundary.
17. Is Option A (`pr_number` from resolver) proven? If not, mark it `UNVERIFIED`.

---

## 8. Required negative tests

The reviewer must inspect the proposed 36-test matrix in the revised design, §19. At minimum, verify
the design covers:

1. Concurrent cycle creation.
2. Multiple PRs in one conversation.
3. Same SHA in two repositories.
4. Repository rename.
5. Repository deletion/recreation.
6. Unknown lifecycle status.
7. NULL lifecycle/stage.
8. Terminal cycle with stale worker.
9. Expired lease.
10. Supersession + replacement rollback.
11. Duplicate correlation token.
12. Token copied into unrelated PR.
13. Trailer in an earlier ancestor commit.
14. Trailer absent from PR ancestry.
15. PR head changed after CI collection.
16. CI check SHA mismatch.
17. Provider timeout after transmission.
18. Provider response lost before persistence.
19. Unknown billing at exposure limit.
20. Blind payload contaminated with OpenHands report.
21. Blind payload contaminated with prior review output.
22. Secret scanner failure.
23. Consent revoked before request.
24. Consent revoked during request.
25. Provider alias changes underlying model.
26. Stale worker attempts a write.
27. Duplicate final report.
28. Telegram accepted but response lost.
29. Tombstone before provider call.
30. Tombstone before Telegram delivery.
31. Restart recovery.
32. Snapshot UPDATE/DELETE attempt.
33. Audit record deletion attempt.
34. Malformed model output.
35. Unsupported finding.
36. Deterministic rule precedence.

**These are proposed tests. Do not execute them in the review and do not report them as passing.**

---

## 9. Forbidden assumptions

The reviewer must not assume:

- that R0C/R0D full reports exist or were recovered;
- that `pr_number` is populated by the resolver without an observed example;
- that a commit trailer proves authorship rather than token possession;
- that repository write access is a sufficient trust boundary for multi-contributor repos;
- that a SQLite CHECK can validate another table's rows;
- that a manifest proves Blind isolation without content checks;
- that a timeout is non-billable;
- that a hard monetary ceiling is enforceable with the verified provider;
- that Telegram delivery is exactly-once;
- that a model alias is an immutable model identity;
- that the design is owner-approved or implemented;
- that R1 is authorized.

---

## 10. Pass/fail criteria for the independent review

- **PASS:** all critical invariants (D-01/D-02/D-08) are coherent and enforceable; D-04 limitation is
  explicit; multi-PR model is unambiguous; D1 is preserved; design is complete; handoff is complete.
- **PASS_WITH_NOTES:** only bounded, documented residual risks remain; none undermines correctness,
  security, cost control, or audit integrity.
- **NEEDS_REDESIGN:** any core invariant is invalid/insufficient (D-01/D-02/D-08), or D1 is violated.
- **BLOCKED:** essential source artifacts/evidence are unavailable, or independence cannot be
  established.

A passing review does **not** authorize R1.

---

## 11. Owner decisions not implied

1. Conversation-wide vs per-PR cycle uniqueness.
2. Commit-trailer token convention and trust boundary.
3. OpenHands credential/service-account scope.
4. Data-egress policy and consent.
5. Provider/model selection and cost-risk acceptance.
6. Katabump persistence canary.
7. Revised lifecycle and repository identity design.
8. Final review-cycle design approval.
9. Authorization for a separate independent review.
10. R1 implementation authorization.

No approval is implied by this handoff or by the R0E artifacts.

---

## 12. Artifact inventory

| Artifact | Path | SHA-256 |
|---|---|---|
| Remediation report | `docs/reviews/OHB2-AUTO-REVIEW-R0E-DESIGN-REMEDIATION-REPORT-20261124.md` | `b03156fa0892acd4dbfea90b3800b945abb651473015dfb70786423fd943d7e4` |
| Revised design | `docs/reviews/OHB2-AUTO-REVIEW-R0E-REVISED-DESIGN-20261124.md` | `d15b7649b87d712c187b560865c7c1aa90e69e8bbeda84a55384a497694a3e9c` |
| Handoff | `docs/reviews/OHB2-AUTO-REVIEW-R0E-INDEPENDENT-REVIEW-HANDOFF-20261124.md` | A file cannot contain its own SHA-256; the final R0E task report records the post-creation hash. |

**No historical report was overwritten. No implementation file was modified. No commit/push.**
