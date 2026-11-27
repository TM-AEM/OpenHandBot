# OHB2-R7 — Owner Decisions Pack Self-Review (2026-11-25; post-approval addendum 2026-11-26)

**Task:** `OHB2-R7-OWNER-DECISIONS-PACK`
**Review type:** `AUTHOR_SELF_REVIEW` only.
**Package verdict:** `R7_OWNER_APPROVALS_RECORDED_WITH_NOTES`.
**Decision status:** D-03–D-06 `APPROVED`; D-04b `DEFERRED`; D-07 `APPROVED_DESIGN_ONLY`; D-08 `APPROVED_BLOCKED`.

> The body below is the pre-approval review of 2026-11-25. The 2026-11-26 owner
> approvals and implementation readiness plan are verified in §8.

This is not owner approval, not live validation, not an independent review, and not R8.
Only the project owner can mark a decision `APPROVED`. No worker was constructed or
activated. No external call was made.

---

## 1. Scope reviewed

1. Fresh Git baseline and working-tree inventory.
2. Phase B readiness report, authorization/resource matrix, activation design, and
   provider cost/egress report.
3. Phase A readiness/self-review, remediation report, canary-linkage report, and D-01/D-02
   decision records.
4. Current implementation: `bot/config.py`, `bot/app.py`, `bot/handlers.py`,
   `bot/outbox.py`, `bot/db.py`, `bot/review/canary_linkage.py`,
   `bot/review/resolver.py`, `bot/review/worker.py`, `bot/review/llm.py`,
   `bot/review/collector.py`, `bot/review/ci_contract.py`, `bot/review/verdict.py`,
   `bot/review/report.py`, `bot/review/prompts.py`, `bot/review/evidence.py`,
   `bot/review/github.py`, `.github/workflows/verify.yml`.
5. The upgraded owner decisions pack and this self-review.

No production database was opened or modified.

---

## 2. Acceptance checks

| Check | Result | Evidence |
|---|---|---|
| Fresh baseline recorded without destructive Git | PASS | Branch/HEAD/main/origin/main/tree, tracked/modified/untracked |
| Existing D-03–D-08 owner approvals searched | PASS | No recorded owner approval; only prior recommendations/deferral |
| D-03 through D-08 each have 14 required items | PASS | Pack §3–§8; 14 headings per decision |
| At least two viable options per decision | PASS | D-03 A/B/C; D-04 A/B/C/D; D-05 A/B/C; D-06 A/B/C; D-07 A/B/C; D-08 A/B/C |
| D-03 lifecycle coverage | PASS | Creation, stages, delivery, retry/restart, revocation, forged/replayed IDs, durable binding |
| D-04 explicit provenance cases | PASS | Same-name recreation, rename, transfer, numeric ID vs name, existing records, backward compatibility, rejection |
| D-05 explicit policy cases | PASS | Same-owner rename, cross-owner transfer, redirect, unverifiable identity, active cycle |
| D-06 per-category policy | PASS | Fork PR, cross-repo PR, fork repo, archived, private, deleted, recreated, visibility, ownership |
| D-07 all 14 issues analyzed | PASS | Exact claim, one PR, four calls, chunks, retries, timeout, lease expiry, restart, duplicates, second-cycle proof, tokens, outbox, audit, reuse vs wrapper |
| D-08 resource matrix fields | PASS | Availability, identity, permissions, cost, egress, isolation, cleanup, evidence |
| Provider cost/egress reconciliation | PASS | §9; four calls are not a monetary bound |
| Cross-decision consistency | PASS | §10; D-01/D-02/conversation-wide/R1/R3/R4/R5/R6/R7 remediation/architecture |
| Recommendations visibly separate from approvals | PASS | `RECOMMENDED_PENDING_APPROVAL`; no decision marked APPROVED |
| D-01 B and D-02 Explicit-list preserved | PASS | §2 and §10.4; no reopening |
| Conversation-wide scope preserved | PASS | §7.13.2 and §10 |
| No unsupported live-readiness claim | PASS | D-08 blocked; no live evidence |
| No external operation | PASS | No OpenHands/GitHub/provider/Telegram call |
| No worker activation | PASS | No supervisor/worker constructed |
| No code/test/schema change | PASS | Docs only |
| No Git publication | PASS | No commit/push/PR/merge/deploy/release |
| `git diff --check` | PASS | clean, exit 0 |
| Targeted doc parity | PASS | 16 passed |

---

## 3. Findings

### F1 — D-03 execution/delivery authorization gap (HIGH for live)

Creation checks `watched.chat_id` and owner; callbacks check current owner/private/cycle
chat. `ReviewRunner.run()` does not recheck `watched`, deletion, or current
`Config.owner_id`; `_post_claimed_review()` has no deletion-witness or current-owner
check. A cycle can execute or deliver after owner change, unwatch, or deletion.

Disposition: D-03 remains open; recommend `current-owner-revalidation`.

### F2 — D-04 no durable numeric repository ID (HIGH for continuity)

`creation_jobs` has `repo` and `conversation_id`, not the GitHub numeric ID observed at
creation. Same-name recreation is indistinguishable. No schema change was made. Recommend
canary attestation now; future numeric-ID persistence under separate schema approval.

### F3 — D-05 rename/transfer policy (MEDIUM)

Current behavior rejects redirects, name mismatch, and ID mismatch. Numeric ID continuity
is not authorization. Recommend reject-by-default.

### F4 — D-06 eligibility incomplete (MEDIUM)

Fork/cross-repository PRs are rejected. `RepositoryIdentity.fork/archived/private` are
parsed but not used for eligibility. Recommend private allowlisted only; reject fork/
archived/deleted/recreated/visibility/ownership changes.

### F5 — D-07 design is not sufficient as written (HIGH)

The four-call/one-PR/one-chunk/one-attempt envelope is coherent only if:

- exact cycle claim is implemented;
- pending membership rows are rejected;
- each stage emits one request, otherwise abort;
- budget counts corrections and no retry/fallback occurs;
- expiry is checked before every provider call/renewal;
- a standalone outbox delivery step exists;
- audit is append-only;
- D-03 current-owner revalidation is applied.

These are implementation requirements, not approvals. The current R5 worker cannot be
reused as-is; a separate one-shot wrapper is required.

### F6 — D-08 resources and cost ceiling missing (BLOCKED)

No reviewer key, review GitHub token, Telegram token, disposable repository, provider
entitlement, pricing visibility, hard spend cap, or isolated DB exists. Live resources
remain blocked.

### F7 — Provider consistency

No confirmed entitlement/pricing/balance API; no hard monetary ceiling; no `max_tokens`
or token ledger. Four calls are a call-count bound, not a known monetary maximum.
Timeouts/ambiguous outcomes may incur unknown charges. Live inference remains blocked
unless the owner supplies a provider-side hard cap or explicit bounded-exposure acceptance.

### F8 — Cross-decision gaps (not contradictions)

- Standalone supervisor/outbox delivery gap.
- One-PR reservation vs pending membership merge.
- Expiry vs active lease.
- Four calls vs retry/multi-chunk.
- Revocation vs execution/delivery.
- Four-call budget vs token/monetary cost.

No approved decision is reopened.

---

## 4. Positive findings

- Existing callback authorization is tested and fails closed for different user, group
  chat, forged review ID, and cross-chat callback.
- Reservation is atomic and conversation-wide; memberships are immutable.
- Provider snapshot binding is enforced before collection/provider work.
- CI job completeness and branch/SHA revalidation are implemented and tested.
- Report delivery is outbox-backed with at-most-once CAS and `unknown` on ambiguity.
- Owner acceptance is immutable and separate from the technical verdict.
- The pack preserves D-01 B, D-02 Explicit-list, conversation-wide scope, and R1–R6.

---

## 5. Documentation-only verification

| Check | Result |
|---|---|
| Required pack path exists | `docs/reviews/OHB2-R7-OWNER-DECISIONS-PACK-20261125.md` |
| Required self-review path exists | `docs/reviews/OHB2-R7-OWNER-DECISIONS-SELF-REVIEW-20261125.md` |
| Report references/paths checked | yes; no missing referenced reports/modules |
| D-03–D-08 each have 14 items | yes; 14 headings per decision |
| No `APPROVED` assigned by the agent | yes; only `OWNER_DECISION_REQUIRED` / `RECOMMENDED_PENDING_APPROVAL` |
| No live-readiness claim | yes |
| `git diff --check` | **clean**, exit 0 |
| Secret-pattern scan of new reports/PROGRESS | **no matches** |
| Targeted doc parity | `pytest -q tests/test_doc_code_parity.py` → **16 passed** |
| Full test suite rerun | not run; no executable change |
| Live operations | none |
| Final branch / HEAD / tree | `agent/r6-review-delivery` / `01079676351aac869d09d4d1747661cd6f07d82b` / `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| Final tracked/modified/untracked | 569 / 12 / 66 |

No code, test, schema, migration, runtime wiring, worker activation, external call, or
publication was performed.

---

## 6. Residual limitations

- Author self-review only; no independent review.
- Pre-approval recommendations were approved on 2026-11-26; implementation remains unauthorized.
- No live OpenHands/GitHub/provider/Telegram evidence.
- D-03–D-06 approved; D-04b deferred; D-07 design-only; D-08 blocked.
- D-07 supervisor is design-only.
- D-08 resources and provider spend cap are missing.
- Python 3.11 and remote CI were not run.
- Independent review remains deferred; R8 has not started.

---

## 7. Conclusion

The decision pack is complete and the owner approvals are recorded. D-03–D-06 are
approved policies; D-04b is deferred; D-07 is design-only; D-08 is approved blocked. Live
canary remains blocked by the D-07 implementation gaps and missing D-08 resources. Package
verdict: `R7_OWNER_APPROVALS_RECORDED_WITH_NOTES`.

---

## 8. Post-approval addendum (2026-11-26)

- D-03: `APPROVED` — `current-owner-revalidation`.
- D-04: `APPROVED` — `canary-only-owner-attestation`.
- D-04b: `DEFERRED` — no schema/migration/persistence authorization.
- D-05: `APPROVED` — `reject-rename-transfer`.
- D-06: `APPROVED` — `private-allowlisted-only`.
- D-07: `APPROVED_DESIGN_ONLY` — implementation and activation not authorized.
- D-08: `APPROVED_BLOCKED` — live Canary remains blocked.
- Approval record: `docs/reviews/OHB2-R7-OWNER-DECISIONS-PACK-20261125.md` §11.
- Implementation readiness plan:
  `docs/reviews/OHB2-R7-APPROVED-DECISIONS-IMPLEMENTATION-PLAN-20261126.md`.
- No code, tests, schema, runtime wiring, worker, credential, resource, external call, or
  Git publication was performed.
- D-01 B, D-02 Explicit-list, conversation-wide scope, R1–R6, independent-review deferral,
  autopush-disabled status, `REVIEW_ENABLED=1` config-only behavior, R5 worker inactivity,
  and R8 not-started status are preserved.
