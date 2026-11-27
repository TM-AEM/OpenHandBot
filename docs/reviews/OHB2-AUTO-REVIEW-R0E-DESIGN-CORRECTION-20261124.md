# OHB2-AUTO-REVIEW-R0E — Design Correction Report

> **PROPOSED — NOT OWNER APPROVED — NOT IMPLEMENTED**

**Task ID:** `OHB2-AUTO-REVIEW-R0E`
**Date:** 2026-11-24
**Scope:** design correction, evidence reconciliation, documentation only.
**Baseline:** `01079676351aac869d09d4d1747661cd6f07d82b` (tree `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc`).
**Independence:** **`INDEPENDENCE_NOT_ESTABLISHED`** — this report was authored by the same
session/agent that produced the prior R0C/R0D/R0E material. A same-agent check is not an
independent review. See `docs/reviews/OHB2-WP08-BATCH-INDEPENDENT-REVIEW-REPORT-20261124.md`.

---

## 1. Executive verdict

**`R0E_DESIGN_READY_FOR_INDEPENDENT_REVIEW`**

This means a complete, internally consistent proposal is ready for a **separate reviewer
session/agent**. It does **not** mean:

- the design is owner-approved;
- B-01/B-02/B-03/B-04/B-05 are closed;
- an independent review has occurred;
- R1 is authorized.

**R1 remains BLOCKED and unauthorized.**

**Critical corrections in this report:**

| Finding | Correction |
|---|---|
| D-01 | Explicit `lifecycle_state` / `stage` / `terminal_reason` / `lease_epoch` model; terminal immutability; fenced writes; atomic supersession. |
| D-02 | GitHub numeric `repository_id`; normalized `review_prs`; `(pr_id, head_sha)` uniqueness; same SHA in two repos distinguished. |
| D-08 | Separate Blind/Adversarial builders; strict Blind allowlist; serialized-payload content checks; no provider call on contamination. |
| D-03/D-04 | Immutable provider-attempt records; explicit billing states; bounded attempts + estimated exposure; **no hard monetary ceiling claim**. |
| D-06/D-07 | Per-check SHA validation; latest suite; base/merge-base ancestry; revalidation before every external side effect; documented TOCTOU. |
| D-09 | Four-layer verdict; evidence verification; versioned rule table; model recommendation non-authoritative. |
| D-10 | Versioned consent; scanner/policy versions; retention/alias/revocation semantics; in-flight request handling. |
| D-11..D-18 | Fencing, mandatory triggers, final-report uniqueness, append-only audit, UNKNOWN delivery, normalized PRs, single-process constraints. |
| B-01 | Native resolver, dedicated commit token, and owner-mapping alternatives; recommendation marked owner decision. |

---

## 2. Fresh baseline

| Item | Value | Evidence |
|---|---|---|
| UTC | `2026-11-24T15:18:13Z` | `date -u` |
| Branch | `openhands-workspace-11liARbsA7OSSoFJOM2RDr` | `git branch -vv` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` | `git rev-parse HEAD` |
| `main` | `01079676351aac869d09d4d1747661cd6f07d82b` | `git rev-parse main` |
| `origin/main` | `01079676351aac869d09d4d1747661cd6f07d82b` | `git rev-parse origin/main` |
| Upstream | **none** | `git rev-parse @{u}` |
| HEAD tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` | `git rev-parse HEAD^{tree}` |
| Worktree | **no tracked changes** | `git status --porcelain=v1` |
| Untracked | three prior R0E docs (preserved) | `git status` |
| Ignored | `.openhands/` only | `git status --ignored` |
| Target file | did not exist before creation | `test -e` → NO |

**Open PRs:** #7 `31dec52…`, #8 `6a1ca2e…`, #9 `1a84cad…` — unchanged from R0D.

**R0D baseline match:** HEAD/tree identical. No assumption of a changed baseline.

---

## 3. Evidence inventory

| ID | Claim | Source and location | Timestamp | Status | What would close the gap |
|---|---|---|---|---|---|
| E-01 | Baseline HEAD/tree | `git rev-parse HEAD`, `HEAD^{tree}` | 2026-11-24T15:18Z | **VERIFIED** | — |
| E-02 | Worktree had no tracked changes | `git status --porcelain` | 2026-11-24T15:18Z | **VERIFIED** | — |
| E-03 | Three prior R0E docs exist untracked | `docs/reviews/OHB2-AUTO-REVIEW-R0E-*.md` | 2026-11-24 | **VERIFIED** | — |
| E-04 | R0/R0A/R0B/R0C/R0D reports are not saved in repo | `grep -rln "AUTO-REVIEW-R0" docs .agent` → no results | 2026-11-24 | **VERIFIED (absence)** | A saved historical artifact. |
| E-05 | R0C conversation excerpt was truncated at §7 | Conversation-provided excerpt | — | **PARTIALLY_VERIFIED** | Complete R0C artifact; not reconstructed here. |
| E-06 | D1 decisions are historical owner decisions | Task prompts / conversation | — | **VERIFIED (historical)** | A saved decision record. |
| E-07 | User search sees 4 conversations; org list sees 20 | OpenHands API read-only (R0C/R0D evidence) | 2026-11-24 | **VERIFIED** | Re-run if API scope changes. |
| E-08 | Personal org, 1 member, owner | OpenHands org API | 2026-11-24 | **VERIFIED** | — |
| E-09 | All 20 org conversations have `pr_number=[]` | OpenHands org list | 2026-11-24 | **VERIFIED (scope)** | A real conversation with non-empty `pr_number`. |
| E-10 | All 20 have `trigger=openhands_api`; no resolver conversation | OpenHands org list | 2026-11-24 | **VERIFIED (scope)** | A resolver-created conversation with PR metadata. |
| E-11 | GitHub App installation exists | `GET /api/v1/git/installations/search` → `169807727` | 2026-11-24 | **VERIFIED** | — |
| E-12 | `pr_number` is `array<integer>` and accepted at start, not update | OpenAPI `AppConversation`, `StartRequest`, `UpdateRequest` | 2026-11-24 | **VERIFIED** | Documentation of population semantics. |
| E-13 | Resolver is documented but `pr_number` population is not | `docs.openhands.dev/enterprise/integrations/github.md:169-205` | 2026-11-24 | **PARTIALLY_VERIFIED** | Real resolver conversation + `pr_number` + PR SHA/CI. |
| E-14 | Bot creation path does not send `pr_number` | `bot/openhands_client.py:386-397` | 2026-11-24 | **VERIFIED** | — |
| E-15 | `client_ref` is creation-job idempotency, not free | `bot/db.py:4638-4665`, `:779` | 2026-11-24 | **VERIFIED** | — |
| E-16 | NVIDIA catalog visible (32 models); no deepseek | `GET /v1/models` read-only | 2026-11-24 | **VERIFIED** | — |
| E-17 | NVIDIA base URL/auth/OpenAI-compatible | `build.nvidia.com/llms.txt` | 2026-11-24 | **VERIFIED (docs)** | — |
| E-18 | Trial credits are consumed by remote calls | NVIDIA FAQ §7 | 2026-11-24 | **VERIFIED (docs)** | — |
| E-19 | No reliable balance/usage API documented | NVIDIA FAQ/Quickstart; rate-limit page 404 | 2026-11-24 | **VERIFIED (absence)** | Provider balance API or owner dashboard evidence. |
| E-20 | No inference was performed | No POST /chat/completions in this task | 2026-11-24 | **VERIFIED (process)** | Owner authorization + test. |
| E-21 | Canary exists and is isolated | `tools/katabump-sqlite-canary/README.md`, `canary.py` | 2026-11-24 | **VERIFIED (repo)** | — |
| E-22 | H1 has no run evidence | No canary result files; no lifecycle run | 2026-11-24 | **VERIFIED (absence)** | Owner-operated isolated canary run. |
| E-23 | Existing architecture is single-process/one DB | `docs/OHB2_PHASE6...:132-133`; `bot/db.py:692-698` | 2026-11-24 | **VERIFIED** | — |
| E-24 | Existing workers use claim/lease patterns | `bot/outbox.py:902-1015`; `bot/db.py:4459`, `:5203` | 2026-11-24 | **VERIFIED** | — |
| E-25 | `notification_inbox` is not a review event source | `bot/notifier.py:561` (early return when disabled) | 2026-11-24 | **VERIFIED** | — |
| E-26 | Telegram delivery has no exactly-once guarantee | Existing at-most-once outbox pattern; Telegram API behavior | 2026-11-24 | **VERIFIED (architecture)** | — |
| E-27 | SQLite supports partial indexes/triggers/RETURNING | SQLite 3.46.1 in runtime | 2026-11-24 | **VERIFIED** | — |
| E-28 | No independent review occurred | Same authoring session | 2026-11-24 | **VERIFIED** | A genuinely separate reviewer session. |
| E-29 | No hard monetary ceiling can be guaranteed | No provider balance/idempotency evidence | 2026-11-24 | **VERIFIED (limitation)** | Provider-side enforcement or owner risk acceptance. |
| E-30 | R1 is blocked | R0D verdict + unresolved blockers | 2026-11-24 | **VERIFIED** | Closure of B-01..B-05 + approvals. |

---

## 4. R0D finding disposition

| Finding | R0D issue | R0E disposition | Status |
|---|---|---|---|
| D-01 | stage used as lifecycle; no fencing | explicit lifecycle/stage/terminal/lease model | **RESOLVED_IN_DESIGN** |
| D-02 | repository identity/uniqueness insufficient | numeric repo ID + normalized PR + keys | **RESOLVED_IN_DESIGN** |
| D-03 | claims vs paid attempts conflated | separate claim/attempt/billing records | **RESOLVED_IN_DESIGN** |
| D-04 | no hard cost ceiling | explicit limitation + attempt/exposure controls | **PARTIALLY_RESOLVED** |
| D-05 | SHA/snapshot invariants | NOT NULL guards + stage checks | **RESOLVED_IN_DESIGN** |
| D-06 | CI not structurally bound | per-check evidence + `ci_head_sha` | **RESOLVED_IN_DESIGN** |
| D-07 | revalidation only before verdict | revalidate before each side effect | **RESOLVED_IN_DESIGN** |
| D-08 | Blind could see report | separate builders + strict allowlist + content checks | **RESOLVED_IN_DESIGN** |
| D-09 | deterministic verdict on free text | four layers + evidence verification + rule table | **RESOLVED_IN_DESIGN** |
| D-10 | egress/consent gaps | versioned consent + scanner/policy versions | **RESOLVED_IN_DESIGN** |
| D-11 | abandoned stage recovery | fencing + ABANDONED recovery | **RESOLVED_IN_DESIGN** |
| D-12 | snapshots mutable | mandatory triggers | **RESOLVED_IN_DESIGN** |
| D-13 | multiple FINAL reports | partial unique final | **RESOLVED_IN_DESIGN** |
| D-14 | CASCADE destroys audit | RESTRICT + append-only triggers | **RESOLVED_IN_DESIGN** |
| D-15 | UNKNOWN auto-retry | terminal UNKNOWN + manual reconciliation | **RESOLVED_IN_DESIGN** |
| D-16 | baseline/tombstone gaps | explicit baseline/miss/tombstone rules | **RESOLVED_IN_DESIGN** |
| D-17 | JSON PR arrays | normalized `review_prs` | **RESOLVED_IN_DESIGN** |
| D-18 | single-process constraints | in-process worker + one DB + lease guard | **RESOLVED_IN_DESIGN** |

**D-04 is deliberately not marked fully resolved:** the verified provider capabilities do not
include a reliable balance API or idempotency key.

---

## 5. Corrected lifecycle model

### 5.1 Concepts

| Concept | Column(s) | Rule |
|---|---|---|
| Lifecycle | `lifecycle_state` | `ACTIVE` or `TERMINAL` only. |
| Stage | `stage` | Explicit processing stage; CHECK enum. |
| Terminal outcome | `terminal_reason` | Constrained enum; NOT NULL when TERMINAL. |
| Worker lease | `lease_owner`, `lease_expires_at`, `last_heartbeat_at` | Who may write. |
| Fencing | `lease_epoch` | Monotonic; every write must match. |
| Scheduling | `next_attempt_at`, `claim_count` | Retry timing and claim count. |

### 5.2 Legal transitions

`AWAITING_SHA → SHA_CONFIRMING → SHA_PINNED → CI_CHECK → EGRESS_CHECK → BLIND_QUEUED →
BLIND_RUNNING → BLIND_DONE → ADVERSARIAL_QUEUED → ADVERSARIAL_RUNNING → ADVERSARIAL_DONE →
VERDICT_READY → DELIVERY_PENDING`.

Any ACTIVE state → TERMINAL with one of: `DELIVERED`, `NEEDS_OWNER`, `NOT_REVIEWABLE`,
`SUPERSEDED`, `EXHAUSTED`, `FAILED`, `EGRESS_BLOCKED`, `CONSENT_REVOKED`, `TOMBSTONED`.

Unknown lifecycle/stage values are rejected by CHECK and by the state machine (fail closed).

### 5.3 Terminal immutability

- Terminal rows are immutable via a `BEFORE UPDATE` trigger.
- A terminal transition increments `lease_epoch`, clears `lease_owner`/`lease_expires_at`/
  `next_attempt_at`/`last_heartbeat_at`, and records `terminal_at`.
- Historical lease info is written to the audit log, not kept as an active lease.

### 5.4 Worker fencing

Every state-changing write includes:

```sql
UPDATE review_cycles
SET stage = :next_stage, updated_at = :now
WHERE id = :id
  AND lifecycle_state = 'ACTIVE'
  AND lease_owner = :owner
  AND lease_epoch = :epoch
  AND lease_expires_at > :now;
```

If `rowcount = 0`, the worker discards the result, writes no report, creates no delivery, and
audits `FENCED_WRITE_DISCARDED`. A stale worker cannot persist a result or deliver Telegram.

### 5.5 Atomic supersession

One `BEGIN IMMEDIATE` transaction:

1. verify old cycle ACTIVE;
2. terminalize old (`SUPERSEDED`, fence epoch);
3. insert replacement ACTIVE cycle;
4. insert `review_supersessions(old,new)`;
5. append audit;
6. commit.

Any failure rolls back; the old cycle remains ACTIVE. No zero-active-cycle window.

### 5.6 Concurrent creation

- SQLite `BEGIN IMMEDIATE` serializes writers.
- The partial unique index on active conversation cycles rejects a second active cycle.
- The loser catches the integrity error, re-reads the existing active cycle, and does not crash.
- If the existing cycle is for a different SHA/PR, the loser records an observation and waits.

### 5.7 Recovery

- Expired leases are claimable.
- `review_stage_runs` RUNNING with expired lease → `ABANDONED`.
- `review_deliveries` SENDING → `UNKNOWN`.
- Queued stages remain claimable; no automatic provider re-POST without the billing/risk policy.

---

## 6. D-01/D-17 owner-choice comparison — multiple PRs

### Option 1 — Conversation-wide serialization (recommended, not approved)

| Aspect | Design |
|---|---|
| Uniqueness | `UNIQUE(conversation_id) WHERE lifecycle_state='ACTIVE'` |
| Relations | `review_prs` normalized; multiple rows per conversation |
| Multiple PRs | queued sequentially; one active review at a time |
| Fairness/ordering | FIFO by `review_prs.created_at`; owner can reprioritize |
| Cancellation | queued PR can be marked `NOT_REVIEWABLE` without affecting active |
| PR change while queued | re-resolve when it becomes active; stale queue entries become `NEEDS_OWNER` |
| Locking | one write transaction per transition; `BEGIN IMMEDIATE` |
| Fencing | per conversation/cycle; one active cycle |
| Recovery | queued cycles resume after restart |
| Advantages | simple, low cost, clear audit, preserves D-01 intent |
| Disadvantages | one stuck PR blocks others; serialized latency |
| Failure scenarios | long provider timeout blocks queue; owner must intervene |
| Single-process compatibility | **COMPATIBLE** |

### Option 2 — Per-PR concurrency

| Aspect | Design |
|---|---|
| Uniqueness | `UNIQUE(conversation_id, repository_id, pr_number) WHERE lifecycle_state='ACTIVE'` |
| Relations | `review_prs` normalized; one active cycle per PR |
| Multiple PRs | independent active cycles |
| Fairness/ordering | global scheduler with per-conversation/per-provider limits |
| Cancellation | per PR |
| PR change | per-PR supersession |
| Locking | more frequent write transactions; claim fairness needed |
| Fencing | per cycle |
| Recovery | multiple active cycles resume |
| Advantages | parallel reviews, lower per-PR latency |
| Disadvantages | cost spikes, concurrency limits, shared conversation state ambiguity |
| Failure scenarios | provider rate limits, duplicate costs, cross-PR report confusion |
| Single-process compatibility | **COMPATIBLE**, but more complex |

**Recommendation:** Option 1 for R1.  
**Status:** **PROPOSED — OWNER DECISION REQUIRED.** Do not treat as approved.

---

## 7. Repository and PR identity model

- `repository_id` = GitHub numeric ID; stable across rename/transfer.
- `repository_full_name` = descriptive snapshot, not the identity key.
- PR identity = `(repository_id, pr_number)`.
- `review_prs` normalized: `UNIQUE(conversation_id, repository_id, pr_number)`.
- `review_cycles` references `pr_id`; `UNIQUE(pr_id, head_sha)`.
- `head_sha`, `base_sha`, `base_ref_tip_sha`, `merge_base_sha` are distinct:
  - `base_sha` = merge-base used for diff;
  - `base_ref_tip_sha` = current base tip (evidence);
  - `merge_base_sha` = validated merge-base; must be ancestor of head.
- Repository rename: same ID, new full-name snapshot; no new cycle.
- Repository deletion/recreation: new numeric ID; old cycle `NOT_REVIEWABLE`; new cycle for new ID.
- Reassignment: `repository_id` immutable per cycle; terminate old + new cycle/owner decision.
- Same SHA in different repositories: distinct `(repository_id, head_sha)`.
- Same PR number in different repositories: distinct by `repository_id`.
- `pr_numbers_json` is **not** authoritative; normalized rows only.

**Immutable after pin:** `repository_id`, `pr_id`, `head_sha`, `base_sha`, `merge_base_sha`,
`provider_snapshot_id`, `consent_id`, `created_at`.

---

## 8. Provider attempt and billing model

### 8.1 Separate records

| Record | Meaning |
|---|---|
| `claim_count` | free worker claims |
| `review_provider_attempts` | one immutable row per HTTP attempt |
| `billing_state` | transmission/response/billing state |
| `cost_estimate_low/high` | estimated exposure |
| `usage_json` | observed usage |
| `provider_request_id` | provider response ID if present |

### 8.2 Billing states

`NOT_SENT`, `SENT_UNKNOWN`, `RESPONSE_RECEIVED`, `ERROR_RESPONSE`, `BILLING_CONFIRMED`,
`BILLING_UNKNOWN`.

- Timeout after transmission → `SENT_UNKNOWN`; **not** confirmed non-billable.
- Crash after response before persistence → ambiguous; no automatic retry without risk policy.
- `SENT_UNKNOWN`/`BILLING_UNKNOWN` counted at worst-case exposure.
- If next attempt could exceed owner-approved exposure → `NEEDS_OWNER`; no call.

### 8.3 Cost limitation

A true hard monetary ceiling **cannot be guaranteed** without reliable provider balance/pricing
enforcement and/or provider-side idempotency. An output-token cap is not a total-cost guarantee.
Bounded attempts + estimated worst-case cost are mitigations, not a guaranteed financial ceiling.

### 8.4 Owner approval information before any inference test

- exact provider/model ID and version/fingerprint;
- endpoint/body/max_tokens;
- expected usage fields;
- known pricing/credit uncertainty;
- before/after dashboard evidence;
- owner-set maximum acceptable exposure;
- stop conditions for 404/429/5xx/timeout/unexpected usage/ambiguous credit;
- explicit acceptance of at-least-once/unknown billing risk.

---

## 9. CI and SHA validation

- `head_sha` pinned; every relevant check-run must have `head_sha == pinned head_sha`.
- `review_pr_checks` stores `check_run_id`, `check_suite_id`, `name`, `head_sha`, `status`,
  `conclusion`, `completed_at`, `is_latest`, `evidence_sha256`.
- Latest suite per check name/app; older runs `is_latest=0`; rerun replaces latest.
- Queued/in-progress → `PENDING`; cancelled/skipped → `ERROR`/`NONE` per rule; failed → `FAILURE`;
  missing required check → `NONE`/`ERROR`.
- Base validation: `base_sha` = compare merge-base; `merge_base_sha` must be ancestor of head;
  `base_ref_tip_sha` recorded separately.
- Revalidation before Blind, Adversarial, verdict, delivery. Change → `SUPERSEDED`; fence; no
  delivery.
- Timestamps/hashes stored for every collection.
- **TOCTOU:** cannot be eliminated; revalidate immediately before each external side effect; include
  head SHA in payload/message; stale delivery is marked and superseded.

---

## 10. Blind and Adversarial payload isolation

### 10.1 Separate builders

- `build_blind_payload(...)`
- `build_adversarial_payload(...)`

No shared mutable payload; no shared cache.

### 10.2 Blind allowlist

- exact pinned diff `base_sha..head_sha`;
- required immutable SHA/repository context;
- approved architectural decisions;
- minimal structured CI summaries after validation (names/conclusions, no logs).

### 10.3 Blind denylist

OpenHands report/output/verdict, prior reviewer outputs, adversarial findings, PR comments/review
comments, untrusted commit messages, arbitrary PR metadata, raw CI logs, unapproved files.

### 10.4 Field-level schema and checks

Every source: `source_type`, `source_sha256`, `provenance`. Manifest: `included_sources`,
`excluded_sources`, `selected_files`, `redaction_summary`, `payload_sha256`, `payload_bytes`.

Before transmission:

1. validate source types against the stage allowlist;
2. validate every file is in the manifest;
3. compute report/prior-review fingerprints and search the serialized payload;
4. compute `payload_sha256` over exact bytes;
5. send exactly those bytes.

If any check fails → `ISOLATION_BLOCKED`/`NEEDS_OWNER`; no provider request.

A manifest alone is not proof; the content check on the serialized payload is the proof.

---

## 11. Evidence verification and deterministic verdict

### 11.1 Layers

1. Model-generated findings.
2. Evidence-verified findings.
3. Rule-engine inputs.
4. Final deterministic verdict.

### 11.2 Finding schema

`id`, `severity`, `claim`, `file`, `line_start`, `line_end`, `evidence`, `evidence_sha256`,
`commit_sha`, `diff_identity`, `verification_status`, `verification_failure_reason`.

### 11.3 Verification

- file must be in the pinned diff;
- line range must be in a changed hunk;
- evidence snippet must exist in the diff/file at the pinned SHA;
- unsupported finding → `UNSUPPORTED_FINDING`;
- duplicate finding → merge/count once;
- malformed JSON → retry bounded → `NEEDS_OWNER`/`EXHAUSTED`.

### 11.4 Rule table (proposed)

| Rule | Preconditions | Output |
|---|---|---|
| `R-01` | verified HIGH upheld/new | `FAIL` |
| `R-02` | verified HIGH uncertain | `NEEDS_OWNER` |
| `R-03` | only MEDIUM/LOW/INFO | `PASS_WITH_NOTES` |
| `R-04` | no verified findings + CI success | `PASS` |
| `R-05` | CI failure | `FAIL` |
| `R-06` | CI missing/pending beyond budget | `NEEDS_OWNER` |
| `R-07` | malformed output after retries | `NEEDS_OWNER`/`EXHAUSTED` |
| `R-08` | unsupported HIGH | `NEEDS_OWNER` |
| `R-09` | consent/egress/integrity failure | terminal reason |

Precedence: integrity/consent/CI failures override findings; HIGH > MEDIUM > LOW; uncertainty on
HIGH → `NEEDS_OWNER`. Model recommendation is stored but never sets the verdict.

---

## 12. Consent and egress model

Versioned consent identifies:

- repository identity;
- provider;
- reviewer model and immutable version/fingerprint where available;
- data classes permitted;
- scanner/redaction version;
- provider retention policy/known limitations;
- consent timestamp, expiry, policy version;
- revocation semantics before/during in-flight request.

Handling:

- alias changes/version unknown → new snapshot/consent or `NEEDS_OWNER`;
- retention policy changes → re-consent;
- revocation during request → response stored but marked; no verdict/delivery without owner review;
- revocation cannot retract data already sent.

No external data egress is authorized by this task.

---

## 13. Recovery and audit integrity

- D-11: abandoned workers fenced by `lease_epoch`; RUNNING + expired lease → `ABANDONED`.
- D-12: mandatory `BEFORE UPDATE/DELETE` triggers on snapshots/manifests/reports/verdicts/audit.
- D-13: one FINAL report per cycle; partial unique index.
- D-14: `ON DELETE RESTRICT`; append-only audit; backup/restore and retention are owner decisions.
- Optional triggers are **not** sufficient; the design uses mandatory triggers.

---

## 14. Telegram delivery uncertainty

- Durable intent before send: `PENDING`.
- Atomic claim → `SENDING`.
- `DELIVERED` only after a message_id.
- Crash/timeout after send → `UNKNOWN`; no automatic resend.
- Restart: `SENDING` → `UNKNOWN`.
- Manual reconciliation: owner checks the chat; confirms delivered or creates a new manual delivery.
- No exactly-once claim.

---

## 15. Baseline and tombstone semantics

- `created_at` (conversation creation), `submitted_at` (prompt submission, if known),
  `first_seen_at` (review observer first saw it) are distinct.
- Baseline = earliest reliable of `submitted_at`/`created_at`/`first_seen_at`.
- Transient API failure ≠ missing; only successful observations increment `miss_count`.
- After N successful misses (e.g., 3) → `NOT_REVIEWABLE`/missing.
- Two-read confirmation for terminal transitions where appropriate.
- Tombstone check before provider egress and again before Telegram delivery.
- Tombstone read failure → fail closed (no egress/delivery).

---

## 16. B-01 correlation alternatives

### 16.1 Native resolver

Evidence needed: a real resolver-created conversation with non-empty `pr_number`, matching
`repository_id`, PR head SHA, and CI. OpenAPI field presence + GitHub App installation are **not**
proof. Status: `UNVERIFIED`.

### 16.2 Dedicated commit correlation token

- Dedicated table; **do not reuse `client_ref`** (creation idempotency).
- Persist token before the creation POST; 128-bit random; store hash; expiry; repo/conversation
  binding; replay protection.
- Inject into initial prompt/commit instructions; agent compliance unguaranteed.
- Search `base_sha..head_sha`; exactly one valid occurrence; one repository; one PR; commit must be
  ancestor of PR head; eligible pre-merge PR state.
- Missing/duplicated/copied/reused/ambiguous/inconsistent → `NEEDS_OWNER`.
- Token possession does not prove authorship.

### 16.3 Temporary owner mapping

Manual, auditable lab fallback only; not durable automatic correlation.

**Recommendation:** commit token as primary, native resolver as fallback, owner mapping only as lab
fallback. **Status: PROPOSED — OWNER DECISION REQUIRED.**

---

## 17. Complete lifecycle sequence

1. Discover conversation (org endpoint, bot user/repo filter).
2. Resolve repository ID and full-name snapshot.
3. Correlate PR (native/token/owner mapping).
4. Pin head SHA (two reads), base SHA/merge-base, base tip.
5. Collect CI evidence (per-check SHA, latest suite).
6. Verify owner consent (scope/version/expiry).
7. Build payload manifest from pinned diff.
8. Scan/redact; verify payload hash.
9. Blind Review (allowlisted payload only).
10. Persist Blind result + evidence verification.
11. Adversarial Review (report + Blind result + diff).
12. Verify adversarial findings.
13. Deterministic verdict (rules).
14. Persist final report + verdict.
15. Revalidate SHA/consent/tombstone; Telegram delivery.
16. Manual reconciliation for `UNKNOWN`.
17. Cancellation/supersession/recovery (fencing, terminal, new cycle).

---

## 18. Crash-window analysis

| Boundary | State before | Crash/timeout | Recovery | Duplicate risk | Fencing/evidence |
|---|---|---|---|---|---|
| Conversation discovery | cursor | no write | retry | none | timestamps |
| Repository resolution | `AWAITING_SHA` | no write | retry | none | API response |
| PR correlation | `SHA_CONFIRMING` | no write | retry/NEEDS_OWNER | none | token/PR evidence |
| SHA pin | `SHA_CONFIRMING` | no write | retry | none | two-read evidence |
| CI collection | `CI_CHECK` | no write | retry | none | check-run hashes |
| Consent | `EGRESS_CHECK` | no write | revoked → terminal | none | consent row |
| Scan/redact | `EGRESS_CHECK` | local | fail → terminal | none | scan summary |
| Blind provider call | `BLIND_RUNNING` | response lost | attempt `SENT_UNKNOWN`; risk policy | possible billing | attempt row |
| Blind persistence | stage commit | crash before commit | retry; no advancement | provider cost possible | stage run |
| Adversarial call | `ADVERSARIAL_RUNNING` | same | same | possible billing | attempt row |
| Verdict | `VERDICT_READY` | crash before commit | retry | none | rule inputs |
| Telegram send | `SENDING` | accepted but lost | `UNKNOWN`; manual | manual only | delivery_ref |
| Restart | any | leases expired | recover; SENDING→UNKNOWN | no auto provider/Telegram retry | startup log |

No exactly-once provider or Telegram behavior is promised.

---

## 19. D1 compatibility matrix

| # | D1 decision | Status | Rule/enforcement | Risk |
|---|---|---|---|---|
| 1 | Reviewer ≠ execution model | **COMPATIBLE_WITH_CONSTRAINTS** | store execution model + reviewer model; same/unknown → `NEEDS_OWNER` | alias/version uncertainty |
| 2 | Blind/Adversarial separate | **COMPATIBLE** | separate stages/builders | none |
| 3 | Same reviewer model snapshot | **COMPATIBLE** | single `provider_snapshot_id` | none |
| 4 | Blind no report/output | **COMPATIBLE_WITH_CONSTRAINTS** | strict allowlist + payload content check | scanner/fingerprint residual |
| 5 | Adversarial sees report + Blind | **COMPATIBLE** | adversarial manifest | none |
| 6 | Deterministic verdict | **COMPATIBLE_WITH_CONSTRAINTS** | four layers + rule table | rule coverage needs tests |
| 7 | Direct provider API via adapter | **COMPATIBLE** | `ReviewProvider` protocol | none |
| 8 | Proxy optional | **COMPATIBLE** | same interface | none |
| 9 | Immutable snapshots | **COMPATIBLE_WITH_CONSTRAINTS** | mandatory triggers | offline tampering |
| 10 | Model switching future only | **COMPATIBLE** | snapshot per cycle | none |
| 11 | Second reviewer deferred | **COMPATIBLE** | one model per cycle | none |

No D1 decision is changed.

---

## 20. Proposed adversarial test matrix

**All tests: PROPOSED — NOT EXECUTED.** No external calls.

| # | Test | Preconditions | Fault/action | Expected DB | Expected external | Evidence |
|---|---|---|---|---|---|---|
| 1 | Concurrent cycle creation | no active cycle | two inserters | one active; loser re-reads | none | integrity handling |
| 2 | Multiple PRs | conversation with 2 PRs | observe both | one active (Option 1); others queued | none | `review_prs` |
| 3 | Same SHA two repos | same SHA, two repo IDs | create cycles | distinct cycles | none | repo key |
| 4 | Repo rename | same ID, new name | resolve | same cycle; snapshot updated | none | repo ID |
| 5 | Repo delete/recreate | old 404, new ID | resolve | old terminal; new cycle | none | 404/new ID |
| 6 | Terminal immutability | terminal row | update | trigger abort | none | trigger |
| 7 | Stale worker after supersession | old epoch | write | 0 rows; discard | none | lease_epoch |
| 8 | Lease epoch mismatch | wrong epoch | write | 0 rows | none | lease_epoch |
| 9 | Unknown lifecycle/stage | invalid value | insert/update | CHECK reject | none | CHECK |
| 10 | CI head mismatch | check-run other SHA | collect | reject/ERROR | none | check-run |
| 11 | Base/merge-base change | base moves | revalidate | `SUPERSEDED` | none | compare evidence |
| 12 | Blind contamination | report in payload | build | `ISOLATION_BLOCKED` | none | fingerprint |
| 13 | Scanner failure | scanner error | build | `EGRESS_BLOCKED` | none | scan error |
| 14 | Consent revoked before | revoked | request | terminal | none | consent |
| 15 | Consent revoked during | revoke mid-call | response | stored; no verdict/delivery | possible retention | timestamps |
| 16 | Model alias/version drift | version changes | resolve | `NEEDS_OWNER`/new snapshot | none | model version |
| 17 | Provider timeout after send | timeout | call | `SENT_UNKNOWN` | possible billing | attempt |
| 18 | Crash after response | kill before commit | recover | no SUCCEEDED; retry policy | possible duplicate billing | stage run |
| 19 | Unknown billing at limit | exposure limit | call | `NEEDS_OWNER`; no call | none | ledger |
| 20 | Duplicate final report | second FINAL | insert | unique violation | none | partial index |
| 21 | Telegram accepted/lost | timeout | send | `UNKNOWN` | possible delivered | delivery_ref |
| 22 | Tombstone before provider | tombstone | call | `TOMBSTONED` | none | `db.is_deleted` |
| 23 | Tombstone before delivery | tombstone | send | blocked | none | tombstone |
| 24 | Restart recovery | kill/restart | startup | leases recovered; SENDING→UNKNOWN | no duplicate POST | startup log |
| 25 | Snapshot UPDATE/DELETE | snapshot | update/delete | trigger abort | none | trigger |
| 26 | Audit deletion | audit row | delete | trigger abort | none | trigger |
| 27 | Malformed model output | invalid JSON | parse | retry/EXHAUSTED | provider per budget | stage run |
| 28 | Unsupported finding | file not in diff | verify | `UNSUPPORTED_FINDING`; HIGH→NEEDS_OWNER | none | evidence |
| 29 | Rule precedence | conflicting findings | evaluate | deterministic verdict | none | rule_id/version |
| 30 | Duplicate token | token twice | correlate | NEEDS_OWNER | none | occurrence count |
| 31 | Token copied to unrelated PR | token in PR2 | correlate | NEEDS_OWNER | none | binding |
| 32 | Trailer in ancestor commit | token in ancestor | correlate | accept if unique/ancestor | none | range |
| 33 | Trailer absent | no token | correlate | NEEDS_OWNER | none | range |
| 34 | PR head changed after CI | head moves | revalidate | `SUPERSEDED` | none | old/new SHA |
| 35 | Blind prior-review contamination | prior text | build | `ISOLATION_BLOCKED` | none | fingerprint |
| 36 | Secret scanner false negative | pattern missed by A, caught by B | scan | blocked by B | none | scanner versions |

---

## 21. Updated blocker table

| Blocker | Status | Evidence available | Evidence missing | Closure condition | Owner approval? |
|---|---|---|---|---|---|
| **B-01** conversation→PR→SHA | **UNVERIFIED** | 20 org conversations, all `pr_number=[]`; no resolver conversation; no trailer | real conversation with non-empty `pr_number` or verified token/PR/ancestry | end-to-end correlation with PR head SHA + CI | Yes (convention) |
| **B-02** inference/cost | **UNVERIFIED** | catalog 32 models; docs base URL/auth; no balance API | authorized minimal inference + usage/cost evidence | one approved call with cost evidence | Yes |
| **B-03** Katabump H1 | **UNVERIFIED** | canary code/README; no run | isolated lifecycle run (write/Stop/restart/redeploy) | H1 evidence | Yes |
| **B-04** credential scope | **PARTIALLY_VERIFIED** | personal org, 1 member, 20 conversations; 4 user search | service-account/filter confirmation | bot-only conversation filter confirmed | Yes |
| **B-05** egress consent | **PROPOSED** | policy in this report | explicit owner consent | signed/recorded consent | Yes |
| **B-06** design | **DESIGN_CORRECTED** | this report + prior R0E docs | separate independent review + owner approval | independent review pass + approval | Yes |

No blocker is closed by documentation or field presence.

---

## 22. Owner decisions required

1. Conversation-wide (Option 1) vs per-PR (Option 2) uniqueness.
2. Commit-trailer token convention and trust boundary.
3. OpenHands credential/service-account scope.
4. Data-egress policy and consent.
5. Provider/model selection and cost-risk acceptance.
6. Katabump persistence canary.
7. Revised lifecycle/repository identity design.
8. Final review-cycle design approval.
9. Authorization for a separate independent review.
10. R1 implementation authorization.

No approval is implied by this report.

---

## 23. Residual risks and explicit non-goals

**Residual risks:**

- No hard monetary ceiling; at-least-once/unknown billing possible.
- Secret scanners can miss secrets; entropy detection is imperfect.
- Provider retention/alias changes cannot be fully controlled.
- Telegram delivery is at-most-once, not exactly-once.
- TOCTOU between SHA revalidation and external side effects.
- SQLite triggers do not protect against offline DB tampering.
- Execution model identity is alias-level; exact upstream version unverified.

**Non-goals:**

- implementation;
- schema/migration;
- provider inference;
- Katabump operations;
- production changes;
- R1 authorization.

---

## 24. Safety confirmation

| Check | Result |
|---|---|
| Application/runtime code modified | **No** |
| Database schema/migration implemented | **No** |
| Workflows/tests/config modified | **No** |
| Provider inference/API calls | **No** |
| Provider credits consumed | **No** |
| Repository content sent externally | **No** |
| OpenHands settings/integrations changed | **No** |
| Katabump lifecycle/canary | **No** |
| Production changes | **No** |
| Commit/push/PR/merge/deploy/release | **No** |
| Autopush | **Disabled/inactive; untouched** |
| R1 implementation | **No** |
| Existing reports overwritten | **No** |
| New document | `docs/reviews/OHB2-AUTO-REVIEW-R0E-DESIGN-CORRECTION-20261124.md` (untracked) |

---

## 25. Final R0E verdict and next permitted task

**Verdict:** `R0E_DESIGN_READY_FOR_INDEPENDENT_REVIEW`

**This does not authorize R1.**

**Next permitted task:** `OHB2-AUTO-REVIEW-R0F — Independent Review of the R0E Design` by a
**different session/agent**. The reviewer must read this report and the three prior R0E artifacts,
challenge D-01/D-02/D-08/D-04, verify D1, and return `PASS`, `PASS_WITH_NOTES`,
`NEEDS_REDESIGN`, or `BLOCKED`.

After the independent review and owner decisions 1–10, R1 may be requested separately. R1 remains
BLOCKED until then.
