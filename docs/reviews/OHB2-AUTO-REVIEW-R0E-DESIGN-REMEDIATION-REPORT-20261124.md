# OHB2-AUTO-REVIEW-R0E — Design Correction & Artifact Completion Report

> **PROPOSED — NOT OWNER APPROVED — NOT IMPLEMENTED**

**Task ID:** `OHB2-AUTO-REVIEW-R0E`
**Date:** 2026-11-24
**Status:** design correction and documentation only; no implementation.
**Baseline:** `01079676351aac869d09d4d1747661cd6f07d82b` (tree `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc`).
**Companion:** `docs/reviews/OHB2-AUTO-REVIEW-R0E-REVISED-DESIGN-20261124.md` (SHA-256 `d15b7649b87d712c187b560865c7c1aa90e69e8bbeda84a55384a497694a3e9c`).

---

## 1. Executive verdict

**`R0E_DESIGN_READY_FOR_INDEPENDENT_REVIEW`**

This means the corrected design is complete enough to be handed to a **different** reviewer
session/agent. It does **not** mean:

- the design is owner-approved;
- B-01/B-02/B-03/B-04/B-05 are closed;
- R1 is authorized;
- the design has passed an independent review.

**Key corrections delivered:**

| Area | Correction | Status |
|---|---|---|
| D-01 | `lifecycle_state` + `stage` + `terminal_reason` + `lease_epoch` fencing; terminal immutability; atomic supersession | **DESIGNED** |
| D-02 | numeric `repository_id`; normalized `review_prs`; `(pr_id, head_sha)` uniqueness; conversation-wide serialization | **DESIGNED** |
| D-08 | separate Blind/Adversarial builders; strict Blind allowlist; fingerprint/content checks; no shared payload | **DESIGNED** |
| D-03/D-04 | immutable provider attempts; explicit billing states; hard attempt ceiling + estimated exposure; no false hard-cost claim | **DESIGNED** |
| D-05/D-06/D-07 | per-check evidence; latest suite; base/merge-base ancestry; revalidation before each external side effect; documented TOCTOU | **DESIGNED** |
| D-09 | four-layer verdict; evidence verification; rule table; model recommendation non-authoritative | **DESIGNED** |
| D-10 | scanner/policy versions; consent scope/expiry/revocation; in-flight handling; retention/model fingerprint risks | **DESIGNED** |
| D-11..D-18 | fencing, mandatory triggers, unique final report, append-only audit, UNKNOWN delivery, normalized PRs, single-process constraints | **DESIGNED** |
| B-01 | constrained commit-trailer token design; dedicated token table; ancestry/PR/repo/uniqueness rules; Option A remains unverified | **DESIGNED, NOT PROVEN** |

**Remaining blockers:** B-01 (correlation not proven), B-02 (inference/cost), B-03 (Katabump H1),
B-04 (credential/service-account scope), B-05 (owner consent). R1 remains **BLOCKED**.

---

## 2. Fresh baseline

| Item | Value | Evidence |
|---|---|---|
| UTC | `2026-11-24T15:06:54Z` | `date -u` |
| Branch | `openhands-workspace-11liARbsA7OSSoFJOM2RDr` | `git branch -vv` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` | `git rev-parse HEAD` |
| `main` | `01079676351aac869d09d4d1747661cd6f07d82b` | `git rev-parse main` |
| `origin/main` | `01079676351aac869d09d4d1747661cd6f07d82b` | `git rev-parse origin/main` |
| Upstream | **لا يوجد** | `git rev-parse @{u}` |
| Worktree before artifacts | **نظيف** | `git status --porcelain=v1` → فاضي |
| Untracked before artifacts | **لا شيء** | نفسه |
| Ignored | `.openhands/` فقط | `git status --porcelain --ignored` |
| HEAD tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` | `git rev-parse HEAD^{tree}` |
| R0D baseline match | **مطابق** | HEAD/tree |

**Open PRs (read-only GitHub API):** #7 `31dec52…`, #8 `6a1ca2e…`, #9 `1a84cad…` — unchanged.

**Repository state after this task:** three new untracked review documents under `docs/reviews/`;
no tracked file modified; no commit/push.

---

## 3. Source recovery and limitations

| Artifact | Availability | Handling |
|---|---|---|
| R0 report | Not saved in repo | Historical/conversation context; `UNVERIFIED` as an artifact. |
| R0A report | Not saved | Same. |
| R0B report | Not saved | Same. |
| R0C report | Not saved; conversation excerpt truncated at §7 | §§8–16 `UNVERIFIED`; not reconstructed. |
| R0D report | Not saved | Findings used as review input; full artifact `UNVERIFIED`. |
| D1 decisions | Task prompts/conversation | Treated as historical owner decisions; no design approval implied. |

`grep -rln "AUTO-REVIEW-R0" docs .agent` returned no results before this task. The R0E documents are
new proposals, not recovered historical reports.

---

## 4. D-01 correction — lifecycle and worker fencing

### 4.1 Rejected proposal

`UNIQUE(conversation_id) WHERE stage NOT IN (terminal)` is rejected because it conflates:

- lifecycle status;
- processing stage;
- worker execution state;
- terminal outcome.

It also permits terminal rows with active leases and stale-worker writes.

### 4.2 Corrected model

- `lifecycle_state`: `ACTIVE` | `TERMINAL` (NOT NULL).
- `stage`: explicit processing stage (NOT NULL; CHECK enum).
- `terminal_reason`: constrained enum; NOT NULL when TERMINAL.
- `lease_owner`, `lease_expires_at`, `lease_epoch`, `last_heartbeat_at`, `next_attempt_at`.
- `UNIQUE(conversation_id) WHERE lifecycle_state='ACTIVE'` (Alternative 1).
- Terminal transition: increment `lease_epoch`, clear lease fields, set reason/timestamp; terminal
  row immutable via trigger.
- Every worker write is conditional on `lifecycle_state='ACTIVE' AND lease_owner=? AND
  lease_epoch=? AND lease_expires_at > now`.
- Zero-row update ⇒ discard result; no report/delivery; audit `FENCED_WRITE_DISCARDED`.

### 4.3 Atomic supersession

Single `BEGIN IMMEDIATE` transaction:

1. verify old cycle ACTIVE;
2. terminalize old (`SUPERSEDED`, fence lease);
3. insert replacement ACTIVE cycle;
4. insert `review_supersessions(old,new)`;
5. append audit;
6. commit; any failure rolls back entirely.

### 4.4 Alternatives

- **Alternative 1 (recommended):** one active cycle per conversation; multiple PRs serialized.
- **Alternative 2:** one active cycle per `(conversation, repository, PR)`; parallel PR reviews.

Alternative 1 preserves the original D-01 intent; Alternative 2 requires an owner decision.

### 4.5 Negative cases

Concurrent creation, unknown lifecycle, unknown stage, NULL lifecycle/stage, terminal with old
lease, expired lease, stale worker after supersession, failed replacement insertion,
terminal→active, concurrent supersession.

**Status:** `RESOLVED_IN_DESIGN` (proposed, unimplemented).

---

## 5. D-02 correction — repository and PR identity

### 5.1 Rejected proposal

`UNIQUE(conversation_id, head_sha)` is rejected because:

- the same SHA can exist in two repositories;
- it does not include repository identity;
- it conflates a retargeted conversation with a duplicate.

### 5.2 Corrected model

- `repository_id` = GitHub numeric ID (stable across rename/transfer).
- `repository_full_name` = mutable snapshot.
- PR identity = `(repository_id, pr_number)`.
- `review_prs` table: `UNIQUE(conversation_id, repository_id, pr_number)`.
- `review_cycles`: `pr_id` nullable only during `AWAITING_SHA`, then required; `UNIQUE(pr_id, head_sha)`;
  one active per conversation.
- `repository_id` immutable per cycle; reassignment requires terminal + new cycle.
- Same SHA in two repos: distinct `review_prs`/cycles.
- Same PR number in two repos: distinct by `repository_id`.
- Multiple PRs: one `review_prs` row each; cycles serialized by conversation (Alternative 1).

### 5.3 Base/merge-base

- `base_sha` = GitHub compare `merge_base_commit`.
- `base_ref_tip_sha` = current base tip (evidence only).
- `merge_base_sha` = validated merge-base; must be an ancestor of `head_sha`.
- If merge-base changes, the reviewed diff is stale → `SUPERSEDED`/new cycle.

**Status:** `RESOLVED_IN_DESIGN` (proposed, unimplemented).

---

## 6. D-08 correction — Blind Review isolation

### 6.1 Rejected assumption

A manifest alone does not prove isolation. R0C's Blind allowlist included `commit_messages`,
`pr_metadata`, and `ci_evidence`; any of these can embed the OpenHands report or prior review text.

### 6.2 Corrected design

- Separate builders: `build_blind_payload(...)` and `build_adversarial_payload(...)`.
- Blind allowlist:
  - diff `base_sha..head_sha`;
  - changed-file metadata;
  - approved decisions;
  - CI metadata only (names/conclusions, **not logs**);
  - repository metadata.
- Blind denylist:
  - OpenHands report/verdict;
  - prior review reports/model outputs;
  - PR body/comments;
  - commit messages;
  - CI logs;
  - conversation messages;
  - unapproved files.
- Adversarial allowlist: Blind sources + OpenHands report + Blind result.
- Post-build checks:
  - every source type in the stage allowlist;
  - every file in the manifest;
  - compute report/prior-review fingerprints and search the payload;
  - compute `payload_sha256` over exact bytes; provider request uses those bytes.
- Any violation → `ISOLATION_BLOCKED`/`NEEDS_OWNER`; no provider call.

**Status:** `RESOLVED_IN_DESIGN` (proposed, unimplemented). This is the critical D1 fix.

---

## 7. D-03/D-04 correction — provider accounting and billing

### 7.1 Separation

- `claim_count`: free worker claims.
- `review_provider_attempts`: one immutable row per HTTP attempt.
- `billing_state`: `NOT_SENT`, `SENT_UNKNOWN`, `RESPONSE_RECEIVED`, `BILLING_CONFIRMED`,
  `BILLING_UNKNOWN`, `ERROR_RESPONSE`.
- `cost_estimate_low/high`, `usage_json`, `provider_request_id`.

### 7.2 Timeout/crash rules

- Timeout after transmission → `SENT_UNKNOWN`; **not** confirmed non-billable.
- Crash after response before persistence → ambiguous; retry only under explicit risk policy.
- No automatic retry of ambiguous attempts beyond the attempt/exposure budget.

### 7.3 Cost controls

The verified provider capabilities do not include a reliable balance API or idempotency key.
Therefore:

- **No hard monetary ceiling claim.**
- Hard request-attempt limit.
- Estimated maximum exposure = attempts × worst-case token cost.
- Unknown possible charges counted at worst-case.
- If next attempt could exceed the owner-approved exposure → `NEEDS_OWNER`; no call.

**Status:** `PARTIALLY_RESOLVED` — the limitation is explicit; owner must accept residual risk.

---

## 8. D-05/D-06/D-07 correction — SHA and CI integrity

- Pinned: `repository_id`, `pr_id`, `head_sha`, `base_sha`, `base_ref_tip_sha`, `merge_base_sha`,
  `ci_head_sha`, `ci_evidence_sha256`.
- Same-table CHECKs: 40-char SHA; `ci_head_sha == head_sha`; `revalidated_sha == head_sha` when
  verdict exists.
- Cross-table/JSON validation: application-level `review_pr_checks` per check-run; reject any
  `head_sha` mismatch; latest suite per name/app; rerun handling; stale check rejection.
- Base ancestry: compare API merge-base; verify ancestor; revalidate before each stage.
- Revalidation points: Blind, Adversarial, verdict, delivery. On change → `SUPERSEDED`; fence;
  no delivery.
- TOCTOU: no atomicity across GitHub/SQLite/provider/Telegram; revalidate immediately before each
  side effect; include SHA in payload/message; stale delivery marked and superseded.

**Status:** `PARTIALLY_RESOLVED` — enforceable design, with documented TOCTOU.

---

## 9. D-09 correction — deterministic verdict

Four layers:

1. model findings;
2. evidence-backed findings (file/line in diff; evidence snippet/hash);
3. deterministic rule engine;
4. final verdict.

Rules (proposed): `R-01` HIGH upheld/new → FAIL; `R-02` HIGH uncertain → NEEDS_OWNER;
`R-03` only MEDIUM/LOW/INFO → PASS_WITH_NOTES; `R-04` no findings + CI success → PASS;
`R-05` CI failure → FAIL; `R-06` CI missing → NEEDS_OWNER; `R-07` malformed → NEEDS_OWNER/EXHAUSTED;
`R-08` unsupported HIGH → NEEDS_OWNER; `R-09` consent/egress/integrity failure → terminal reason.

Model recommendation is stored but never sets the verdict. Schema/rules/prompt versions are pinned.

**Status:** `RESOLVED_IN_DESIGN` (proposed, unimplemented).

---

## 10. D-10/B-05 correction — data egress and consent

Adds:

- `scanner_version`, `scanner_config_sha256`, `policy_version`, `policy_sha256`;
- provider identity, model ID/version/fingerprint;
- retention terms version;
- consent scope/expiry/revocation;
- in-flight revocation handling;
- redacted payload hash/reproducibility;
- explicit residual risks: scanner false negatives/positives, entropy limits, alias changes,
  provider retention, inability to retract sent data.

Fail-closed on scanner failure, unverified redaction, missing/revoked consent, payload hash mismatch,
tombstone, prohibited content, size/context overflow, ambiguous repo/PR.

**Status:** `RESOLVED_IN_DESIGN` (policy); owner approval required.

---

## 11. D-11 through D-18 matrix

| ID | Failure mode | Corrected invariant | Enforcement | Remaining risk | Negative test | Status |
|---|---|---|---|---|---|---|
| D-11 | RUNNING after crash; stale worker | ABANDONED only with expired lease; writes fenced by epoch | `review_stage_runs.status`, `lease_epoch`, conditional writes | worker may still run; cost possible | stale worker after lease expiry | RESOLVED_IN_DESIGN |
| D-12 | snapshot UPDATE/DELETE | snapshots/manifests/reports/verdicts/audit insert-only | mandatory `BEFORE UPDATE/DELETE RAISE(ABORT)` | offline tampering | snapshot UPDATE/DELETE | RESOLVED_IN_DESIGN |
| D-13 | multiple FINAL reports | one FINAL per cycle; immutable | partial unique `(cycle_id) WHERE kind='FINAL'`; trigger | none material | duplicate final | RESOLVED_IN_DESIGN |
| D-14 | CASCADE deletes audit | append-only; RESTRICT FKs; no delete API | triggers; FK RESTRICT; backup policy | DB loss without backup | audit delete; FK delete | RESOLVED_IN_DESIGN |
| D-15 | UNKNOWN auto-retry | UNKNOWN terminal for auto retries; manual reconciliation | state machine; `delivery_ref`; owner command | duplicate only if manual resend; no lookup | accepted but response lost | RESOLVED_IN_DESIGN |
| D-16 | baseline/missing/tombstone | baseline; transient≠missing; two-read terminal; tombstone before every side effect | `review_conversations`; `db.is_deleted`; miss counter | remote deletion not in local tombstone; cancellation ambiguity | tombstone before provider/delivery | RESOLVED_IN_DESIGN |
| D-17 | JSON PR arrays | normalized `review_prs`; one cycle per PR; conversation-wide serialization | unique `(conversation, repo, PR)`; FK | serialized latency | multiple PRs; same SHA two repos | RESOLVED_IN_DESIGN |
| D-18 | second DB owner | one process/one DB/in-process worker; worker lease guard | `review_worker_lease`; `_post_init/_post_shutdown`; no `to_thread` DB writes | platform may start replicas; guard refuses | second worker start; restart | RESOLVED_IN_DESIGN |

---

## 12. B-01 correction — correlation strategy

### 12.1 Token record

- Dedicated `review_correlation_tokens` table; **do not reuse `client_ref`** (it is creation-job
  idempotency).
- 128-bit random token, namespace `OHB2R1-`; store SHA-256 hash, not raw.
- Persist before the agent starts; bind to `repository_id`, `creation_job_id`, and later
  `conversation_id`; expiry (e.g., 30 days); status `ISSUED/CONSUMED/EXPIRED/REVOKED`.
- Inject into the initial prompt with commit-trailer instructions.

### 12.2 Verification

- Read PR head and commit range `base_sha..head_sha`.
- Find `OpenHands-Correlation: <token>`; hash and match exactly one active token.
- Token must be bound to same repo/conversation.
- Commit must be an ancestor of `head_sha` and in the PR range.
- Exactly one PR per token; reject duplicates/multiple PRs.
- PR open; repository ID matches; head SHA pinned.
- Trailer absent/lost/ambiguous → `NEEDS_OWNER`; no inference.

### 12.3 Workflow edge cases

- Multiple commits: accept if at least one valid occurrence in range; reject duplicates.
- Multiple PRs: one token per PR or `NEEDS_OWNER`; token per creation job is not enough for multi-PR.
- Copied trailer: reject if token appears in >1 PR/repo or if repo/conversation binding fails.
- Amend/rebase/force-push: re-verify; if trailer lost → `NEEDS_OWNER`; if head changed → `SUPERSEDED`.
- Squash merge: pre-merge only; post-merge trailer may be lost.
- Closed/reopened: closed → `NOT_REVIEWABLE`; reopened same head → revalidate; changed head → new cycle.
- Trust boundary: possession, not authorship; repository write access; owner must accept for
  multi-contributor repos.

### 12.4 Option A

`resolver` trigger + GitHub App installation do not prove `pr_number` population. B-01 remains
`UNVERIFIED` until a real resolver conversation with non-empty `pr_number` and matching PR SHA/CI is
observed.

---

## 13. End-to-end lifecycle and crash windows

The complete 17-step lifecycle and 10-boundary crash-window table are in the companion revised
design, §17–§18. Summary:

- Discovery → repository ID → PR correlation → SHA pin → CI → consent → payload → scan → Blind →
  persist → Adversarial → evidence verify → verdict → final report → Telegram → manual reconcile →
  cancellation/supersession/recovery.
- Every external boundary has: state before, timeout/crash behavior, recovery state, duplicate risk,
  fencing requirement, evidence needed.
- No exactly-once provider or Telegram behavior is promised.

---

## 14. Acceptance matrix

The companion revised design, §19, contains 36 proposed, unexecuted tests covering all required
cases: concurrent creation, multiple PRs, same SHA in two repos, rename, deletion/recreation,
unknown/NULL lifecycle, terminal with stale worker, expired lease, supersession rollback, duplicate/
copied/ancestor/absent trailer, head change, CI mismatch, provider timeout/lost response, unknown
billing, Blind contamination, scanner failure, consent revocation, alias change, stale write,
duplicate final, Telegram lost, tombstone before provider/delivery, restart, snapshot/audit
tampering, malformed output, unsupported finding, rule precedence.

**No test was executed; none is claimed passing.**

---

## 15. D1 compatibility

| # | D1 decision | Status | Design rule / enforcement | Unresolved risk |
|---|---|---|---|---|
| 1 | Reviewer ≠ execution model | **PARTIAL** | store `execution_model` + reviewer `model_id`; rule rejects same/unknown → `NEEDS_OWNER` | `llm_model` is an alias; exact upstream version unverified |
| 2 | Blind/Adversarial separate | COMPATIBLE | separate stages/builders | none |
| 3 | Same reviewer model | COMPATIBLE | single `provider_snapshot_id` per cycle | none |
| 4 | Blind cannot see report/verdict | **FIXED IN DESIGN** | strict allowlist + fingerprint checks | scanner/report fingerprint residual |
| 5 | Adversarial sees report + Blind | COMPATIBLE | adversarial manifest | none |
| 6 | Deterministic verdict | **PARTIAL** | four layers + rule table | rule correctness/coverage needs tests |
| 7 | Direct provider API via adapter | COMPATIBLE | `ReviewProvider` protocol | none |
| 8 | Proxy optional | COMPATIBLE | same interface | none |
| 9 | Immutable snapshots | **PARTIAL** | mandatory triggers | offline tampering |
| 10 | Model switching future only | COMPATIBLE | snapshot per cycle | none |
| 11 | Second reviewer deferred | COMPATIBLE | one model per cycle | none |

No D1 change is proposed.

---

## 16. Owner decisions (separate, non-implied)

1. Conversation-wide (Alternative 1) vs per-PR (Alternative 2) cycle uniqueness.
2. Commit-trailer token convention and trust boundary.
3. OpenHands credential/service-account scope.
4. Data-egress policy and consent.
5. Provider/model selection and cost-risk acceptance.
6. Katabump persistence canary.
7. Revised lifecycle and repository identity design.
8. Final review-cycle design approval.
9. Authorization for a separate independent review.
10. R1 implementation authorization.

No approval is implied by this report or the companion documents.

---

## 17. Remaining blockers

| Blocker | Status | Why |
|---|---|---|
| B-01 correlation | **UNVERIFIED** | No conversation with `pr_number`; trailer not implemented/proven; resolver population undocumented. |
| B-02 inference/cost | **UNVERIFIED** | No authorized call; no balance API; no cost evidence. |
| B-03 Katabump H1 | **UNVERIFIED** | No canary run; no mount/persistence evidence. |
| B-04 credential scope | **PARTIALLY_RESOLVED** | 20-conversation personal org known; service-account/filter decision pending. |
| B-05 egress | **POLICY_READY** | Needs owner approval; residual scanner/retention risks. |
| B-06 design | **CORRECTED** | Ready for independent review; not owner-approved. |
| Independent review | **PENDING** | Must be a different session/agent. |
| R1 | **BLOCKED** | All above. |

---

## 18. Safety confirmation

| Check | Result |
|---|---|
| Production implementation files modified | **No** |
| Database/schema/migration implemented | **No** |
| Tests/workflows/config modified | **No** |
| Model inference requests | **No** |
| Provider credits consumed by inference | **No** |
| Repository content sent to external model providers | **No** |
| OpenHands settings changed | **No** |
| Katabump operations | **No** |
| Production changes | **No** |
| Commit/push/PR/merge/deployment/release | **No** |
| Autopush | **Disabled/inactive; untouched** |
| R1 implementation | **No** |
| Existing reports overwritten | **No** |
| New artifacts | Three new files under `docs/reviews/` (untracked; not committed) |

---

## 19. Artifact inventory and hashes

| Artifact | SHA-256 |
|---|---|
| `docs/reviews/OHB2-AUTO-REVIEW-R0E-REVISED-DESIGN-20261124.md` | `d15b7649b87d712c187b560865c7c1aa90e69e8bbeda84a55384a497694a3e9c` |
| `docs/reviews/OHB2-AUTO-REVIEW-R0E-DESIGN-REMEDIATION-REPORT-20261124.md` | computed in the handoff |
| `docs/reviews/OHB2-AUTO-REVIEW-R0E-INDEPENDENT-REVIEW-HANDOFF-20261124.md` | computed after creation |

**Key code/doc hashes at baseline:**

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

## 20. Recommended next task

**`OHB2-AUTO-REVIEW-R0F — Independent Review of the R0E Design`** by a **different session/agent**.

The reviewer must:

1. read the three R0E artifacts;
2. verify D-01/D-02/D-08 enforceability;
3. challenge D-03/D-04 cost claims;
4. verify D1 compatibility;
5. execute no implementation;
6. return `PASS`, `PASS_WITH_NOTES`, `NEEDS_REDESIGN`, or `BLOCKED`.

After that, owner decisions 1–10 must be resolved before R1.
