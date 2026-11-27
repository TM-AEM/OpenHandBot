# OHB2-AUTO-REVIEW-R0E — Revised Review-Cycle Design

> **PROPOSED — NOT OWNER APPROVED — NOT IMPLEMENTED**

**Task ID:** `OHB2-AUTO-REVIEW-R0E`
**Date:** 2026-11-24
**Status:** design proposal for independent review; no implementation.
**Baseline:** `01079676351aac869d09d4d1747661cd6f07d82b` (tree `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc`).
**Related:** `OHB2-AUTO-REVIEW-R0E-DESIGN-REMEDIATION-REPORT-20261124.md`, `OHB2-AUTO-REVIEW-R0E-INDEPENDENT-REVIEW-HANDOFF-20261124.md`.

---

## 0. Reading contract

This document is a **proposal**, not an approved architecture record. Every table, column,
constraint, trigger, rule and transition is **unimplemented**. Nothing here authorizes R1.

Where this document says "must", it means "the proposed design requires"; it does not mean the
repository already enforces it.

The design preserves the approved D1 decisions in §2. Any conflict with D1 is raised as an owner
decision, not silently changed.

---

## 1. Purpose and scope

The design defines a review system that:

1. observes a completed OpenHands conversation;
2. binds it to one GitHub PR and one immutable 40-character head SHA;
3. collects CI evidence for that SHA;
4. obtains owner consent for external data egress;
5. builds a redacted, immutable payload manifest;
6. runs a Blind Review that cannot see the OpenHands report or verdict;
7. runs an Adversarial Review that can see the report and the Blind result;
8. derives a deterministic verdict from verified findings and versioned rules;
9. delivers the verdict to Telegram with explicit at-most-once semantics;
10. preserves audit evidence across crashes, restarts and supersession.

Non-goals: implementation, migrations, provider calls, Katabump operations, R1 authorization.

---

## 2. D1 constraints (approved; do not change)

1. One reviewer model different from the OpenHands execution model.
2. Blind Review and Adversarial Review are separate stages.
3. Both stages use the same reviewer model.
4. Blind Review must not receive the OpenHands report or verdict.
5. Adversarial Review may receive the OpenHands report and the Blind Review result.
6. The final verdict is deterministic and rule-based, not the model's opinion.
7. The first release uses a direct Model API through a provider-neutral Provider Adapter.
8. A Proxy Adapter remains optional and must not change review-stage logic.
9. Provider/model/configuration snapshots are immutable per active cycle.
10. Model switching applies only to future cycles.
11. A second reviewer model remains deferred until after R7.

**D1 conflict rule:** if a correction below would change any D1 item, it is marked
`OWNER_DECISION_REQUIRED` and is not applied by this proposal.

---

## 3. Source status and limitations

| Artifact | Availability | Consequence |
|---|---|---|
| R0 report | Not saved in repository; conversation only | Historical context, not independently verifiable here. |
| R0A report | Not saved; conversation only | Same. |
| R0B report | Not saved; conversation only | Same. |
| R0C report | Not saved; conversation excerpt truncated at §7 | R0C §§8–16 are `UNVERIFIED`; this design is a **new proposal**, not a reconstruction of R0C. |
| R0D report | Not saved; conversation only | R0D findings are used as review input; the full R0D artifact is `UNVERIFIED`. |
| D1 decisions | Task prompts / conversation, not a repository decision record | Treated as historical owner decisions; no approval of this design is implied. |

This document does **not** claim to recover missing R0C/R0D sections. It replaces the invalid
parts with a new, explicitly proposed design.

---

## 4. Core model

### 4.1 Five separate concepts

| Concept | Column(s) | Meaning |
|---|---|---|
| Review-cycle lifecycle | `lifecycle_state` | `ACTIVE` or `TERMINAL` only. |
| Processing stage | `stage` | Where an ACTIVE cycle currently is. |
| Terminal outcome | `terminal_reason` | Why a cycle became TERMINAL. |
| Worker execution | `lease_owner`, `lease_expires_at`, `lease_epoch`, `last_heartbeat_at` | Who may write, and which epoch. |
| Scheduling | `next_attempt_at`, `claim_count` | When to retry and how often the worker claimed. |

A cycle is **not** terminal because its `stage` string looks terminal. Terminality is explicit in
`lifecycle_state`.

### 4.2 Lifecycle states

- `ACTIVE`: exactly one active cycle per conversation (Alternative 1, §5.3).
- `TERMINAL`: immutable; no transition back to ACTIVE; `terminal_reason` is NOT NULL.

### 4.3 Processing stages (ACTIVE only)

`AWAITING_SHA` → `SHA_CONFIRMING` → `SHA_PINNED` → `CI_CHECK` → `EGRESS_CHECK` →
`BLIND_QUEUED` → `BLIND_RUNNING` → `BLIND_DONE` → `ADVERSARIAL_QUEUED` →
`ADVERSARIAL_RUNNING` → `ADVERSARIAL_DONE` → `VERDICT_READY` → `DELIVERY_PENDING`.

An unknown stage fails closed: the CHECK constraint rejects it, and the state machine refuses to
advance it.

### 4.4 Terminal reasons

`DELIVERED`, `NEEDS_OWNER`, `NOT_REVIEWABLE`, `SUPERSEDED`, `EXHAUSTED`, `FAILED`,
`EGRESS_BLOCKED`, `CONSENT_REVOKED`, `TOMBSTONED`.

### 4.5 Terminal lease handling

On the terminal transition, in one transaction:

1. increment `lease_epoch` (fencing);
2. set `lease_owner = NULL`;
3. set `lease_expires_at = NULL`;
4. set `next_attempt_at = NULL`;
5. set `last_heartbeat_at = NULL`;
6. set `terminal_reason`;
7. set `terminal_at`;
8. append an audit event containing the previous lease owner/epoch (no secrets).

The terminal row may retain `lease_epoch` and `terminal_at` for audit. It must not retain an
active lease owner. A stale worker's write with the old epoch affects 0 rows and is discarded.

---

## 5. Identity model and uniqueness

### 5.1 Repository identity

- `repository_id` = GitHub numeric repository ID. It is the stable identity across rename/transfer.
- `repository_full_name` = mutable display snapshot at pin time.
- Rename does not create a new repository; the numeric ID stays.
- Deletion and recreation produce a different numeric ID; the old cycle remains bound to the old ID
  and becomes `NOT_REVIEWABLE` if the PR/repo is gone.
- `repository_id` is immutable inside a cycle.
- Reassignment of a conversation to another repository requires terminating the old cycle and
  creating a new one; it must never mutate `repository_id` in place.

### 5.2 PR identity

- A PR is identified by `(repository_id, pr_number)`.
- `pr_number` alone is not unique across repositories.
- `head_sha` is not unique across repositories.
- A PR may have multiple head SHAs over time; each review cycle pins one.
- A conversation may produce multiple PRs; each PR gets its own `review_prs` row and its own cycle.

### 5.3 Active-cycle uniqueness — two alternatives

#### Alternative 1 — Conversation-wide serialization (recommended for R1)

- At most one `ACTIVE` cycle per `conversation_id`, regardless of PR.
- Constraint: `UNIQUE(conversation_id) WHERE lifecycle_state = 'ACTIVE'`.
- Multiple PRs: discovered/queued; only one is reviewed at a time. If more than one PR is
  simultaneously eligible, the cycle becomes `NEEDS_OWNER` or queues them sequentially under an
  explicit owner policy.
- Scheduling: one active provider path per conversation; lower cost and simpler audit.
- Supersession: old cycle → TERMINAL `SUPERSEDED`; replacement inserted in the same transaction.
- Duplicate observations: deduped by conversation/PR/SHA keys.
- Operational complexity: low.
- Failure modes: one stuck PR blocks the conversation's other PRs; serialized latency.
- D-01 intent: preserved (one active cycle per conversation).
- Compatibility: D1-compatible.
- **Owner decision required** only if the owner wants parallel PR reviews.

#### Alternative 2 — Per-PR serialization

- A conversation may have multiple `ACTIVE` cycles for distinct `(repository_id, pr_number)`.
- Constraint: `UNIQUE(conversation_id, repository_id, pr_number) WHERE lifecycle_state='ACTIVE'`.
- Multiple PRs: reviewed in parallel; higher cost and concurrency.
- Scheduling: fairness and global provider-attempt budget required.
- Supersession: per PR.
- Failure modes: concurrent provider calls, cost spikes, cross-PR report ambiguity.
- D-01 intent: changes the semantics from "one active per conversation" to "one active per PR".
- **Owner decision required.**

**Recommendation:** Alternative 1 for R1. It is the conservative reading of D-01 and minimizes
cost/audit complexity. Alternative 2 is a later optimization, not an R1 default.

### 5.4 SHA identity

- `head_sha`: 40 lowercase hex characters; immutable after pin.
- `base_sha`: the merge-base SHA used for the diff; immutable after pin.
- `base_ref_tip_sha`: the base branch tip observed at pin time; mutable evidence, not the diff base.
- `merge_base_sha`: the merge-base returned by GitHub compare; must equal `base_sha` at pin time.
- The reviewed diff is `base_sha..head_sha`; never use a moving branch name as the diff base.

### 5.5 Correlation identity

A PR is linked to a conversation by exactly one of:

- `NATIVE_RESOLVER` (OpenHands resolver metadata; unverified until observed);
- `COMMIT_TRAILER` (bot-issued token in a commit in `base_sha..head_sha`);
- `OWNER_MAPPING` (explicit owner record; bootstrap only).

The correlation record stores `source`, `evidence_sha256`, `confidence`, `verified_at`, and the
token/PR/repository binding. A correlation is a **claim**, not proof of authorship.

---

## 6. Proposed schema (UNIMPLEMENTED)

All tables are additive. Existing tables are not modified. `PRAGMA foreign_keys=ON` is assumed
(existing `bot/db.py:698`). SQLite 3.46.1 is assumed to support partial indexes, `RETURNING`,
`ON CONFLICT`, and triggers.

**Create order:** create `review_provider_snapshots` and `review_consents` before `review_cycles`,
and `review_prs` before `review_cycles`. The DDL below is grouped for readability, not execution
order. `review_cycles.pr_id` is nullable only during `AWAITING_SHA`; it becomes NOT NULL at
`SHA_CONFIRMING`.

### 6.1 `review_conversations`

```sql
CREATE TABLE IF NOT EXISTS review_conversations (
    conversation_id      TEXT PRIMARY KEY,
    repository_id        INTEGER,
    execution_model      TEXT,
    execution_model_src  TEXT,
    execution_model_disp TEXT,
    baseline_at          TEXT NOT NULL,
    last_status          TEXT,
    last_report_ts       TEXT,
    last_observed_at     TEXT,
    miss_count           INTEGER NOT NULL DEFAULT 0,
    last_missing_at      TEXT,
    tombstoned_at        TEXT,
    last_error_class     TEXT,
    next_poll_at         TEXT,
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL
);
```

### 6.2 `review_prs`

```sql
CREATE TABLE IF NOT EXISTS review_prs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id     TEXT NOT NULL,
    repository_id       INTEGER NOT NULL,
    pr_number           INTEGER NOT NULL,
    pr_url              TEXT,
    pr_state            TEXT NOT NULL DEFAULT 'OPEN'
                        CHECK (pr_state IN ('OPEN','CLOSED','MERGED')),
    correlation_source  TEXT NOT NULL
                        CHECK (correlation_source IN
                          ('NATIVE_RESOLVER','COMMIT_TRAILER','OWNER_MAPPING')),
    correlation_confidence TEXT NOT NULL
                        CHECK (correlation_confidence IN ('HIGH','MEDIUM','LOW')),
    correlation_evidence_sha256 TEXT,
    correlation_verified_at TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    UNIQUE (conversation_id, repository_id, pr_number)
);
```

### 6.3 `review_cycles`

```sql
CREATE TABLE IF NOT EXISTS review_cycles (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    pr_id               INTEGER REFERENCES review_prs(id) ON DELETE RESTRICT,
    conversation_id     TEXT NOT NULL,
    repository_id       INTEGER NOT NULL,
    repository_full_name TEXT NOT NULL,
    head_sha            TEXT,
    base_sha            TEXT,
    base_ref_tip_sha    TEXT,
    merge_base_sha      TEXT,
    execution_model     TEXT,
    provider_snapshot_id INTEGER REFERENCES review_provider_snapshots(id) ON DELETE RESTRICT,
    consent_id          INTEGER REFERENCES review_consents(id) ON DELETE RESTRICT,
    lifecycle_state     TEXT NOT NULL DEFAULT 'ACTIVE'
                        CHECK (lifecycle_state IN ('ACTIVE','TERMINAL')),
    stage               TEXT NOT NULL DEFAULT 'AWAITING_SHA'
                        CHECK (stage IN
                          ('AWAITING_SHA','SHA_CONFIRMING','SHA_PINNED','CI_CHECK',
                           'EGRESS_CHECK','BLIND_QUEUED','BLIND_RUNNING','BLIND_DONE',
                           'ADVERSARIAL_QUEUED','ADVERSARIAL_RUNNING','ADVERSARIAL_DONE',
                           'VERDICT_READY','DELIVERY_PENDING')),
    terminal_reason     TEXT
                        CHECK (terminal_reason IS NULL OR terminal_reason IN
                          ('DELIVERED','NEEDS_OWNER','NOT_REVIEWABLE','SUPERSEDED',
                           'EXHAUSTED','FAILED','EGRESS_BLOCKED','CONSENT_REVOKED',
                           'TOMBSTONED')),
    ci_status           TEXT
                        CHECK (ci_status IS NULL OR ci_status IN
                          ('SUCCESS','FAILURE','PENDING','NONE','ERROR')),
    ci_head_sha         TEXT,
    ci_checked_at       TEXT,
    ci_evidence_sha256  TEXT,
    revalidated_sha     TEXT,
    revalidated_at      TEXT,
    claim_count         INTEGER NOT NULL DEFAULT 0,
    provider_attempt_count INTEGER NOT NULL DEFAULT 0,
    lease_owner         TEXT,
    lease_expires_at    TEXT,
    lease_epoch         INTEGER NOT NULL DEFAULT 0,
    last_heartbeat_at   TEXT,
    next_attempt_at     TEXT,
    last_error_class    TEXT,
    last_error_detail   TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    pinned_at           TEXT,
    terminal_at         TEXT,
    CHECK (head_sha IS NULL OR
           (length(head_sha)=40 AND head_sha NOT GLOB '*[^0-9a-f]*')),
    CHECK (base_sha IS NULL OR
           (length(base_sha)=40 AND base_sha NOT GLOB '*[^0-9a-f]*')),
    CHECK (merge_base_sha IS NULL OR
           (length(merge_base_sha)=40 AND merge_base_sha NOT GLOB '*[^0-9a-f]*')),
    CHECK (ci_head_sha IS NULL OR head_sha IS NULL OR ci_head_sha = head_sha),
    CHECK (lifecycle_state = 'ACTIVE' OR terminal_reason IS NOT NULL),
    CHECK (stage = 'AWAITING_SHA' OR pr_id IS NOT NULL),
    CHECK (stage NOT IN
           ('BLIND_QUEUED','BLIND_RUNNING','BLIND_DONE',
            'ADVERSARIAL_QUEUED','ADVERSARIAL_RUNNING','ADVERSARIAL_DONE',
            'VERDICT_READY','DELIVERY_PENDING')
           OR (head_sha IS NOT NULL AND provider_snapshot_id IS NOT NULL
               AND consent_id IS NOT NULL))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_cycle_active
    ON review_cycles(conversation_id)
    WHERE lifecycle_state = 'ACTIVE';

CREATE UNIQUE INDEX IF NOT EXISTS ux_cycle_pr_sha
    ON review_cycles(pr_id, head_sha)
    WHERE head_sha IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_cycle_claim
    ON review_cycles(lifecycle_state, stage, next_attempt_at);
```

**Note:** `ux_cycle_active` implements Alternative 1. For Alternative 2, replace it with
`UNIQUE(conversation_id, repository_id, pr_number) WHERE lifecycle_state='ACTIVE'` and add an
explicit owner decision.

### 6.4 `review_correlation_tokens`

```sql
CREATE TABLE IF NOT EXISTS review_correlation_tokens (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash          TEXT NOT NULL UNIQUE,
    token_prefix        TEXT NOT NULL,
    conversation_id     TEXT,
    repository_id       INTEGER NOT NULL,
    creation_job_id     INTEGER,
    issued_at           TEXT NOT NULL,
    expires_at          TEXT NOT NULL,
    consumed_at         TEXT,
    status              TEXT NOT NULL DEFAULT 'ISSUED'
                        CHECK (status IN ('ISSUED','CONSUMED','EXPIRED','REVOKED')),
    CHECK (token_hash NOT GLOB '*[^0-9a-f]*' AND length(token_hash)=64)
);
```

The raw token is not stored. The bot hashes the token found in the commit and compares to
`token_hash`.

### 6.5 `review_provider_snapshots`

```sql
CREATE TABLE IF NOT EXISTS review_provider_snapshots (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id           TEXT NOT NULL,
    base_url              TEXT NOT NULL,
    api_key_env           TEXT NOT NULL,
    model_id              TEXT NOT NULL,
    model_version         TEXT,
    model_fingerprint     TEXT,
    context_limit_tokens  INTEGER NOT NULL,
    max_output_tokens     INTEGER NOT NULL,
    temperature           REAL NOT NULL DEFAULT 0.0,
    timeout_seconds       INTEGER NOT NULL,
    max_retries           INTEGER NOT NULL,
    backoff_base_ms       INTEGER NOT NULL,
    backoff_max_ms        INTEGER NOT NULL,
    prompt_versions       TEXT NOT NULL,
    output_schema_versions TEXT NOT NULL,
    rules_version         TEXT NOT NULL,
    config_fingerprint    TEXT NOT NULL UNIQUE,
    created_at            TEXT NOT NULL
);
```

### 6.6 `review_consents`

```sql
CREATE TABLE IF NOT EXISTS review_consents (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    consent_ref           TEXT NOT NULL UNIQUE,
    repository_id         INTEGER NOT NULL,
    provider_id           TEXT NOT NULL,
    model_id              TEXT NOT NULL,
    model_version         TEXT,
    model_fingerprint     TEXT,
    data_classes          TEXT NOT NULL,          -- JSON array
    max_payload_bytes     INTEGER NOT NULL,
    policy_version        TEXT NOT NULL,
    policy_sha256         TEXT NOT NULL,
    retention_terms_version TEXT,
    granted_by            TEXT NOT NULL,
    granted_at            TEXT NOT NULL,
    expires_at            TEXT,
    revoked_at            TEXT,
    revocation_reason     TEXT
);
```

### 6.7 `review_stage_runs`

```sql
CREATE TABLE IF NOT EXISTS review_stage_runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id            INTEGER NOT NULL REFERENCES review_cycles(id) ON DELETE RESTRICT,
    stage               TEXT NOT NULL CHECK (stage IN ('BLIND','ADVERSARIAL')),
    attempt             INTEGER NOT NULL,
    status              TEXT NOT NULL
                        CHECK (status IN ('RUNNING','SUCCEEDED','FAILED','ABANDONED')),
    result_json         TEXT,
    result_text         TEXT,
    result_sha256       TEXT,
    parse_error         TEXT,
    error_class         TEXT,
    error_detail        TEXT,
    started_at          TEXT NOT NULL,
    finished_at         TEXT,
    UNIQUE (cycle_id, stage, attempt)
);
```

### 6.8 `review_provider_attempts`

```sql
CREATE TABLE IF NOT EXISTS review_provider_attempts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id            INTEGER NOT NULL REFERENCES review_cycles(id) ON DELETE RESTRICT,
    stage_run_id        INTEGER NOT NULL REFERENCES review_stage_runs(id) ON DELETE RESTRICT,
    attempt_no          INTEGER NOT NULL,
    billing_state       TEXT NOT NULL
                        CHECK (billing_state IN
                          ('NOT_SENT','SENT_UNKNOWN','RESPONSE_RECEIVED',
                           'BILLING_CONFIRMED','BILLING_UNKNOWN','ERROR_RESPONSE')),
    request_sha256      TEXT NOT NULL,
    http_status         INTEGER,
    provider_request_id TEXT,
    usage_json          TEXT,
    cost_estimate_low   REAL,
    cost_estimate_high  REAL,
    cost_currency       TEXT,
    error_class         TEXT,
    started_at          TEXT NOT NULL,
    finished_at         TEXT,
    UNIQUE (stage_run_id, attempt_no)
);
```

### 6.9 `review_manifests`

```sql
CREATE TABLE IF NOT EXISTS review_manifests (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id            INTEGER NOT NULL REFERENCES review_cycles(id) ON DELETE RESTRICT,
    stage               TEXT NOT NULL CHECK (stage IN ('BLIND','ADVERSARIAL')),
    attempt             INTEGER NOT NULL,
    repository_id       INTEGER NOT NULL,
    head_sha            TEXT NOT NULL,
    base_sha            TEXT NOT NULL,
    provider_snapshot_id INTEGER NOT NULL REFERENCES review_provider_snapshots(id) ON DELETE RESTRICT,
    consent_id          INTEGER NOT NULL REFERENCES review_consents(id) ON DELETE RESTRICT,
    included_sources    TEXT NOT NULL,          -- JSON
    excluded_sources    TEXT NOT NULL,          -- JSON
    selected_files      TEXT NOT NULL,          -- JSON
    redaction_summary   TEXT NOT NULL,          -- JSON
    scanner_version     TEXT NOT NULL,
    scanner_config_sha256 TEXT NOT NULL,
    policy_version      TEXT NOT NULL,
    policy_sha256       TEXT NOT NULL,
    payload_bytes       INTEGER NOT NULL,
    payload_sha256      TEXT NOT NULL,
    prompt_sha256       TEXT NOT NULL,
    prompt_version      TEXT NOT NULL,
    output_schema_version TEXT NOT NULL,
    rules_version       TEXT NOT NULL,
    created_at          TEXT NOT NULL,
    UNIQUE (cycle_id, stage, attempt)
);
```

### 6.10 `review_reports`

```sql
CREATE TABLE IF NOT EXISTS review_reports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id    INTEGER NOT NULL REFERENCES review_cycles(id) ON DELETE RESTRICT,
    kind        TEXT NOT NULL CHECK (kind IN ('BLIND','ADVERSARIAL','FINAL')),
    content     TEXT NOT NULL,
    sha256      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    UNIQUE (cycle_id, kind, sha256)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_final_report
    ON review_reports(cycle_id)
    WHERE kind = 'FINAL';
```

### 6.11 `review_verdicts`

```sql
CREATE TABLE IF NOT EXISTS review_verdicts (
    cycle_id        INTEGER PRIMARY KEY REFERENCES review_cycles(id) ON DELETE RESTRICT,
    verdict         TEXT NOT NULL CHECK (verdict IN ('PASS','PASS_WITH_NOTES','FAIL','NEEDS_OWNER')),
    rule_id         TEXT NOT NULL,
    rules_version   TEXT NOT NULL,
    reason          TEXT NOT NULL,
    model_recommendation TEXT,
    created_at      TEXT NOT NULL
);
```

### 6.12 `review_deliveries`

```sql
CREATE TABLE IF NOT EXISTS review_deliveries (
    cycle_id             INTEGER PRIMARY KEY REFERENCES review_cycles(id) ON DELETE RESTRICT,
    state                TEXT NOT NULL DEFAULT 'PENDING'
                         CHECK (state IN ('PENDING','SENDING','DELIVERED','UNKNOWN','FAILED')),
    attempt_count        INTEGER NOT NULL DEFAULT 0,
    next_attempt_at      TEXT,
    telegram_chat_id     INTEGER,
    telegram_message_id  INTEGER,
    delivery_ref         TEXT,
    last_error_class     TEXT,
    last_error_detail    TEXT,
    updated_at           TEXT NOT NULL
);
```

### 6.13 `review_supersessions`

```sql
CREATE TABLE IF NOT EXISTS review_supersessions (
    old_cycle_id  INTEGER NOT NULL REFERENCES review_cycles(id) ON DELETE RESTRICT,
    new_cycle_id  INTEGER NOT NULL REFERENCES review_cycles(id) ON DELETE RESTRICT,
    reason        TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    PRIMARY KEY (old_cycle_id, new_cycle_id)
);
```

### 6.14 `review_audit_log`

```sql
CREATE TABLE IF NOT EXISTS review_audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id    INTEGER,
    event_type  TEXT NOT NULL,
    actor       TEXT NOT NULL,
    details     TEXT,
    created_at  TEXT NOT NULL
);
```

### 6.15 `review_worker_lease` and `review_meta`

```sql
CREATE TABLE IF NOT EXISTS review_worker_lease (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    owner         TEXT,
    expires_at    TEXT,
    heartbeat_at  TEXT
);

CREATE TABLE IF NOT EXISTS review_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

### 6.16 Mandatory triggers (immutability/append-only)

```sql
CREATE TRIGGER IF NOT EXISTS trg_provider_snapshot_no_update
BEFORE UPDATE ON review_provider_snapshots
BEGIN SELECT RAISE(ABORT, 'provider snapshots are immutable'); END;

CREATE TRIGGER IF NOT EXISTS trg_provider_snapshot_no_delete
BEFORE DELETE ON review_provider_snapshots
BEGIN SELECT RAISE(ABORT, 'provider snapshots are immutable'); END;

CREATE TRIGGER IF NOT EXISTS trg_cycle_terminal_no_update
BEFORE UPDATE ON review_cycles
WHEN OLD.lifecycle_state = 'TERMINAL'
BEGIN SELECT RAISE(ABORT, 'terminal review cycle is immutable'); END;

CREATE TRIGGER IF NOT EXISTS trg_stage_run_no_update_after_finish
BEFORE UPDATE ON review_stage_runs
WHEN OLD.status IN ('SUCCEEDED','FAILED','ABANDONED')
BEGIN SELECT RAISE(ABORT, 'finished stage runs are immutable'); END;

CREATE TRIGGER IF NOT EXISTS trg_manifest_no_update
BEFORE UPDATE ON review_manifests
BEGIN SELECT RAISE(ABORT, 'review manifests are immutable'); END;

CREATE TRIGGER IF NOT EXISTS trg_report_no_update
BEFORE UPDATE ON review_reports
BEGIN SELECT RAISE(ABORT, 'review reports are immutable'); END;

CREATE TRIGGER IF NOT EXISTS trg_verdict_no_update
BEFORE UPDATE ON review_verdicts
BEGIN SELECT RAISE(ABORT, 'review verdicts are immutable'); END;

CREATE TRIGGER IF NOT EXISTS trg_audit_no_update
BEFORE UPDATE ON review_audit_log
BEGIN SELECT RAISE(ABORT, 'review audit log is append-only'); END;

CREATE TRIGGER IF NOT EXISTS trg_audit_no_delete
BEFORE DELETE ON review_audit_log
BEGIN SELECT RAISE(ABORT, 'review audit log is append-only'); END;
```

**Note:** SQLite triggers are database-level but not tamper-proof against an operator who edits the
file offline. Backup/restore and access control remain owner responsibilities.

---

## 7. Lifecycle transition table

| From | To | Guard |
|---|---|---|
| `AWAITING_SHA` | `SHA_CONFIRMING` | exactly one PR identity; repository ID resolved |
| `SHA_CONFIRMING` | `SHA_PINNED` | two consecutive reads return same head SHA; PR open; base/merge-base recorded |
| `SHA_PINNED` | `CI_CHECK` | base ancestry validated |
| `CI_CHECK` | `EGRESS_CHECK` | CI evidence stored or `CI_MISSING` rule applied |
| `EGRESS_CHECK` | `BLIND_QUEUED` | consent valid; scan/redaction pass; payload hash matches manifest |
| `BLIND_QUEUED` | `BLIND_RUNNING` | claim with valid lease/epoch |
| `BLIND_RUNNING` | `BLIND_DONE` | structured result persisted; evidence verified |
| `BLIND_DONE` | `ADVERSARIAL_QUEUED` | adversarial manifest includes report + Blind result |
| `ADVERSARIAL_QUEUED` | `ADVERSARIAL_RUNNING` | claim with valid lease/epoch |
| `ADVERSARIAL_RUNNING` | `ADVERSARIAL_DONE` | structured result persisted; evidence verified |
| `ADVERSARIAL_DONE` | `VERDICT_READY` | rules evaluated; SHA/CI revalidated |
| `VERDICT_READY` | `DELIVERY_PENDING` | final report + verdict persisted |
| `DELIVERY_PENDING` | (terminal `DELIVERED`) | Telegram returns message_id |
| any ACTIVE | TERMINAL `SUPERSEDED` | head/base/merge-base changed; lease fenced |
| any ACTIVE | TERMINAL `NEEDS_OWNER` | ambiguity, missing info, unknown billing, consent issue |
| any ACTIVE | TERMINAL `NOT_REVIEWABLE` | error/stuck/waiting_for_confirmation/deleting/missing |
| any ACTIVE | TERMINAL `EGRESS_BLOCKED` | scan/redaction/consent/payload failure |
| any ACTIVE | TERMINAL `CONSENT_REVOKED` | consent revoked |
| any ACTIVE | TERMINAL `TOMBSTONED` | local tombstone |
| any ACTIVE | TERMINAL `EXHAUSTED` | attempt budget exceeded |
| any ACTIVE | TERMINAL `FAILED` | non-retryable internal error |

Terminal states never transition back to ACTIVE. A new SHA requires a new cycle.

---

## 8. Worker claim, lease and fencing

### 8.1 Worker model

The review worker is an **in-process** worker using the existing `Database` instance and event
loop. It is not a second process, not a second DB owner, and not a new independent service.
It follows the existing `_BaseWorker` pattern (`bot/outbox.py:902-1015`) and is started/stopped in
`bot/app.py:_post_init`/`_post_shutdown`.

### 8.2 Startup guard

`review_worker_lease` is a single row (`id=1`). On startup:

- If `expires_at` is in the future and `owner` is not this process: **refuse to start** the
  review worker (fail closed; no multi-replica).
- If expired or empty: take ownership, set `owner`, `expires_at`, `heartbeat_at`.
- Heartbeat every `lease_ttl/3`.

### 8.3 Claim SQL (proposed)

```sql
UPDATE review_cycles
SET lease_owner = :owner,
    lease_expires_at = :lease_until,
    lease_epoch = lease_epoch + 1,
    last_heartbeat_at = :now,
    claim_count = claim_count + 1,
    updated_at = :now
WHERE id = (
    SELECT id FROM review_cycles
    WHERE lifecycle_state = 'ACTIVE'
      AND stage IN ('AWAITING_SHA','SHA_CONFIRMING','CI_CHECK','EGRESS_CHECK',
                    'BLIND_QUEUED','BLIND_RUNNING',
                    'ADVERSARIAL_QUEUED','ADVERSARIAL_RUNNING')
      AND (lease_expires_at IS NULL OR lease_expires_at <= :now)
      AND (next_attempt_at IS NULL OR next_attempt_at <= :now)
    ORDER BY next_attempt_at IS NOT NULL, next_attempt_at, id
    LIMIT 1
)
RETURNING id, lease_epoch, stage;
```

### 8.4 Fenced write (proposed)

Every state-changing write includes:

```sql
UPDATE review_cycles
SET stage = :next_stage, updated_at = :now
WHERE id = :id
  AND lifecycle_state = 'ACTIVE'
  AND lease_owner = :owner
  AND lease_epoch = :epoch
  AND (lease_expires_at IS NULL OR lease_expires_at > :now);
```

If `rowcount == 0`, the worker **discards** the result, does not write reports, does not create a
delivery, and appends an audit event `FENCED_WRITE_DISCARDED` (no secrets). It must not retry with
the stale epoch.

### 8.5 Stage result transaction

```
BEGIN IMMEDIATE;
-- 1. verify cycle still ACTIVE + lease owner/epoch + allowed transition
-- 2. update review_stage_runs RUNNING -> SUCCEEDED/FAILED
-- 3. insert review_provider_attempts (immutable)
-- 4. insert review_manifests (immutable)
-- 5. insert review_reports (immutable)
-- 6. update review_cycles.stage (fenced)
-- 7. append audit event
COMMIT;
```

Any failure rolls back all of it. A crash before commit leaves no advancement; a crash after commit
leaves all evidence durable.

### 8.6 Atomic supersession

```
BEGIN IMMEDIATE;
-- 1. SELECT old cycle FOR the conversation WHERE lifecycle_state='ACTIVE'
-- 2. UPDATE old SET lifecycle_state='TERMINAL', terminal_reason='SUPERSEDED',
--      lease_epoch=lease_epoch+1, lease_owner=NULL, lease_expires_at=NULL,
--      next_attempt_at=NULL, terminal_at=:now
--    WHERE id=:old AND lifecycle_state='ACTIVE'
-- 3. INSERT new cycle (ACTIVE) with new head_sha
-- 4. INSERT review_supersessions(old, new, reason)
-- 5. append audit events
COMMIT;
```

If step 3 fails, the transaction rolls back, and the old cycle remains ACTIVE. There is no window
with zero active cycles. If step 2 affects 0 rows, another worker won; the transaction rolls back
and the caller re-reads.

### 8.7 Recovery

On startup:

- Mark `review_stage_runs` with `status='RUNNING'` and an expired cycle lease as `ABANDONED`.
- Clear active leases whose `lease_expires_at <= now`.
- `review_deliveries.state='SENDING'` → `UNKNOWN` (no auto-resend).
- Leave `BLIND_QUEUED`/`ADVERSARIAL_QUEUED` claimable.
- Do not re-POST a provider request automatically; the attempt record/billing state governs.

---

## 9. Provider accounting and billing states

### 9.1 Separation

| Concept | Record |
|---|---|
| Worker claim | `review_cycles.claim_count` (free) |
| Request preparation | `review_manifests` (no call) |
| Provider request attempt | `review_provider_attempts` (one row per HTTP attempt) |
| Transmission | `billing_state='SENT_UNKNOWN'` |
| Response receipt | `billing_state='RESPONSE_RECEIVED'` |
| Known billing | `BILLING_CONFIRMED` |
| Unknown billing | `BILLING_UNKNOWN` |
| Error response | `ERROR_RESPONSE` |

### 9.2 Billing state transitions

- `NOT_SENT` → `SENT_UNKNOWN` on transmission.
- `NOT_SENT` → `ERROR_RESPONSE` if a local error occurs before transmission.
- `SENT_UNKNOWN` → `RESPONSE_RECEIVED` on a valid response.
- `SENT_UNKNOWN` → `ERROR_RESPONSE` on an HTTP error response.
- `SENT_UNKNOWN` → `BILLING_UNKNOWN` on timeout/reset with no response.
- `RESPONSE_RECEIVED` → `BILLING_CONFIRMED` when usage/cost is known and accepted.
- `RESPONSE_RECEIVED` → `BILLING_UNKNOWN` when usage/cost is missing or ambiguous.
- `ERROR_RESPONSE` → `BILLING_UNKNOWN` unless the provider confirms non-billing.
- No transition back to `NOT_SENT`.

### 9.3 Cost controls (explicit limitation)

The verified provider capabilities do **not** include a reliable balance API or an idempotency key.
Therefore the design **cannot guarantee a hard monetary ceiling**. It can enforce:

- a hard **request-attempt limit** (`max_provider_attempts` per cycle/stage);
- an **estimated maximum exposure** = attempts × worst-case input/output token cost;
- **observed usage** from responses;
- **confirmed charges** from owner/dashboard evidence;
- **unknown possible charges** from `SENT_UNKNOWN`/`BILLING_UNKNOWN`, counted at worst-case.

If the next attempt could push the worst-case exposure above the owner-approved limit:

- do not send;
- transition to `NEEDS_OWNER` with `EXPOSURE_LIMIT`;
- require explicit owner approval to continue.

A timeout is **not** a confirmed non-billable request. A crash after response receipt but before
persistence is an **ambiguous** outcome unless recoverable provider evidence exists.

---

## 10. SHA and CI integrity

### 10.1 Pinned values

`repository_id`, `pr_id`, `head_sha`, `base_sha`, `base_ref_tip_sha`, `merge_base_sha`,
`ci_head_sha`, `ci_evidence_sha256`.

### 10.2 SQLite CHECK vs application validation

| Invariant | Enforcement |
|---|---|
| 40-char lowercase SHA | SQLite CHECK (same table) |
| `ci_head_sha == head_sha` | SQLite CHECK (same table) |
| `revalidated_sha == head_sha` when verdict exists | SQLite CHECK (same table) or application |
| Each check-run `head_sha == head_sha` | Application validation; `review_pr_checks` rows; cannot be a cross-table CHECK |
| Check suite is the latest | Application validation (`is_latest`, `completed_at`) |
| Base/merge-base ancestry | Application validation via GitHub compare + git ancestry |
| PR identity matches repository | Application validation via GitHub API |

### 10.3 Per-check evidence

`review_pr_checks` (add to schema):

```sql
CREATE TABLE IF NOT EXISTS review_pr_checks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id        INTEGER NOT NULL REFERENCES review_cycles(id) ON DELETE RESTRICT,
    check_run_id    INTEGER NOT NULL,
    check_suite_id  INTEGER NOT NULL,
    name            TEXT NOT NULL,
    head_sha        TEXT NOT NULL,
    status          TEXT NOT NULL,
    conclusion      TEXT,
    completed_at    TEXT,
    is_latest       INTEGER NOT NULL DEFAULT 1,
    evidence_sha256 TEXT NOT NULL,
    UNIQUE (cycle_id, check_run_id)
);
```

Validation:
- reject any check-run whose `head_sha != cycle.head_sha`;
- for each check name/app, keep the latest suite; mark older `is_latest=0`;
- if the latest suite is pending, `ci_status='PENDING'`; do not use an older success;
- if a required check is missing, `ci_status='NONE'`/`ERROR`;
- rerun creates a new check-run/suite; update `is_latest`.

### 10.4 Revalidation points

Before **Blind**, **Adversarial**, **verdict**, and **delivery**:

1. re-fetch PR `head.sha`, `base.sha`, `state`;
2. re-fetch compare `merge_base_commit` and base tip;
3. if `head_sha`, `base_sha`, or `merge_base_sha` changed → `SUPERSEDED`; fence worker; no further
   stages/delivery;
4. record `revalidated_sha`, `revalidated_at`.

**TOCTOU limitation:** there is an unavoidable race between the last revalidation and the next
external side effect (provider call or Telegram send). The design does not claim atomicity across
GitHub, SQLite, the provider and Telegram. Mitigation: revalidate immediately before the side
effect; include `head_sha` in the payload/manifest and delivery message; if the head changes after
send, the delivered report is marked stale and a new cycle supersedes it.

---

## 11. Blind and Adversarial isolation

### 11.1 Separate builders

```python
build_blind_payload(cycle, pr, diff, approved_decisions, ci_metadata, repo_metadata)
build_adversarial_payload(cycle, pr, diff, blind_result, openhands_report,
                          ci_metadata, approved_decisions)
```

They are separate functions with separate allowlists. They must not share a mutable payload object.

### 11.2 Blind allowlist

Allowed:
- `diff` (`base_sha..head_sha`);
- `changed_files` metadata;
- `approved_decisions`;
- `ci_metadata` (check names/conclusions only, **not logs**);
- `repo_metadata` (repository ID/name, PR number, SHAs).

Forbidden:
- OpenHands report;
- OpenHands verdict;
- prior review reports/model outputs;
- PR body;
- PR comments;
- commit messages;
- arbitrary CI logs;
- conversation messages;
- unapproved files/artifacts.

**Rationale:** PR body/comments/commit messages/CI logs can embed the OpenHands report or prior
review text. Excluding them is the only safe default. If a future owner wants commit messages in
Blind, the builder must scan them for report/prior-review fingerprints and fail closed on a match.

### 11.3 Adversarial allowlist

Allowed: all Blind sources + `openhands_report` + `blind_result`.

Forbidden: prior review outputs other than Blind; unapproved files; unrelated conversations.

### 11.4 Enforceable isolation

- Each source has a `source_type`, `source_sha256`, and `provenance` (API endpoint/file/DB row).
- The manifest records `included_sources` and `excluded_sources`.
- Post-build validation:
  1. every source type is in the stage allowlist;
  2. every file is in the manifest selected files;
  3. compute the OpenHands report fingerprint and the prior-review fingerprint;
  4. search the payload for those fingerprints; if found → `ISOLATION_VIOLATION`;
  5. compute `payload_sha256` over exact bytes; store it;
  6. the provider request uses exactly those bytes; mismatch → fail closed.
- Separate stage-specific prompts; store `prompt_sha256` and `prompt_version`.
- A shared payload cache is forbidden; each stage builds its own payload.

### 11.5 Failure behavior

Any isolation failure → `ISOLATION_BLOCKED`/`NEEDS_OWNER`; **no provider request**; audit event.
No fallback to a less strict builder.

---

## 12. Data egress, consent and redaction

### 12.1 Classification

- **Safe metadata:** repo ID/name, PR number, SHAs, file paths, diff stats, check names/conclusions,
  timestamps, provider/model IDs, prompt/schema/rules versions.
- **Reviewable source:** diff, changed source, approved decisions.
- **Sensitive:** secrets/tokens/keys, `.env`, connection strings, personal data, customer data,
  internal URLs, proprietary logic.
- **Prohibited:** production credentials, private keys, customer PII/data exports, regulated data,
  binaries/large artifacts, `.git` internals, untracked files, code outside the pinned diff.

### 12.2 Scanning and redaction

- Path denylist and content patterns (cloud keys, GitHub/Slack/Stripe tokens, private-key blocks,
  JWT, basic-auth URLs, connection strings, `password=`, `secret=`, `token=`, `api_key=`).
- Entropy detection as a secondary signal; never the only signal.
- Binary/oversize detection; diff-only; changed hunks + necessary context.
- Redaction to `[REDACTED:<type>]`; re-scan the redacted payload; if any match remains, fail closed.
- Store `scanner_version`, `scanner_config_sha256`, `policy_version`, `policy_sha256`,
  `redaction_summary`, `payload_sha256`, `payload_bytes`.
- **No scanner is perfect:** false negatives/positives remain a documented residual risk. High-risk
  repos may require owner review of the redacted manifest.

### 12.3 Consent

- Scope: repository + provider + model + data classes + max payload + policy version.
- Record `consent_ref`, `policy_version`, `policy_sha256`, `retention_terms_version`, `granted_by`,
  `granted_at`, `expires_at`, `revoked_at`.
- Owner sees: repo, provider, model/version, data classes, payload estimate, redaction policy,
  retention terms, cost ceiling.
- Revocation: blocks future requests; cannot retract data already sent.
- In-flight request: check consent immediately before send; if revoked during the request, store the
  response but mark `CONSENT_REVOKED_DURING_REQUEST`; no verdict/delivery without owner review.
- Model alias: store `model_version`/`model_fingerprint`; a changed alias/version requires a new
  snapshot/consent. A silent upstream change behind the same alias cannot be detected; residual risk.

### 12.4 Fail-closed conditions

No transmission if: scanner fails; redaction unverified; consent missing/expired/revoked; payload
hash mismatch; tombstoned conversation; prohibited content; payload/context limit exceeded; repo/PR
ambiguous; provider snapshot mismatch.

---

## 13. Deterministic verdict contract

### 13.1 Four layers

1. **Model findings** — raw structured output.
2. **Evidence-backed findings** — validated against the pinned diff.
3. **Rule-engine evaluation** — deterministic rules on verified findings.
4. **Final verdict** — rule output, stored in `review_verdicts`.

### 13.2 Finding schema (proposed)

```json
{
  "schema_version": "findings.v1",
  "findings": [
    {
      "id": "F-1",
      "severity": "HIGH",
      "file": "bot/example.py",
      "line_start": 10,
      "line_end": 12,
      "category": "correctness",
      "claim": "Short claim",
      "evidence": "Exact snippet from the diff",
      "evidence_sha256": "...",
      "confidence": 0.8
    }
  ],
  "model_recommendation": "PASS_WITH_NOTES"
}
```

### 13.3 Validation

- `id` unique within the stage.
- `severity` in `HIGH|MEDIUM|LOW|INFO`.
- `file` is a changed file in the pinned diff.
- `line_start/line_end` are within a changed hunk (or the file at the pinned SHA).
- `evidence` snippet exists in the diff/file; compute `evidence_sha256`.
- Unsupported finding → `UNSUPPORTED_FINDING`; not counted as verified; HIGH unsupported →
  `NEEDS_OWNER`.
- Duplicate findings (same file/line/category/claim hash) → merge; count once.
- Malformed JSON → retry bounded → `EXHAUSTED`/`NEEDS_OWNER`; never parse free text for verdict.

### 13.4 Rule table (proposed, unimplemented)

| Rule ID | Condition | Verdict |
|---|---|---|
| `R-01` | any verified HIGH upheld or new | `FAIL` |
| `R-02` | any verified HIGH uncertain | `NEEDS_OWNER` |
| `R-03` | only verified MEDIUM/LOW/INFO | `PASS_WITH_NOTES` |
| `R-04` | no verified findings + CI SUCCESS + no new adversarial | `PASS` |
| `R-05` | CI FAILURE | `FAIL` |
| `R-06` | CI MISSING/PENDING beyond budget | `NEEDS_OWNER` |
| `R-07` | malformed output after retries | `NEEDS_OWNER`/`EXHAUSTED` |
| `R-08` | unsupported HIGH finding | `NEEDS_OWNER` |
| `R-09` | consent/egress/integrity failure | `NEEDS_OWNER`/terminal reason |

Precedence: integrity/consent/CI failures override model findings; HIGH > MEDIUM > LOW;
uncertainty on HIGH → `NEEDS_OWNER`; model recommendation is stored but never sets the verdict.

---

## 14. Delivery uncertainty

- State machine: `PENDING → SENDING → DELIVERED | UNKNOWN | FAILED`.
- `DELIVERED` only after Telegram returns a message_id.
- Crash/timeout after send → `UNKNOWN`; no automatic resend.
- Manual reconciliation: owner checks the chat; if delivered, mark `DELIVERED` with evidence; if
  not, the owner may create a new manual delivery (new `delivery_ref`), accepting duplicate risk.
- `FAILED` only for pre-send failures; owner action required to retry.
- No exactly-once claim.

---

## 15. Audit retention, backup and deletion

- `review_audit_log`, `review_stage_runs`, `review_provider_attempts`, `review_manifests`,
  `review_reports`, `review_verdicts` are append-only; mandatory triggers block UPDATE/DELETE.
- FKs use `ON DELETE RESTRICT`; no delete API.
- Retention: owner-configurable; default keep all R1 evidence.
- Backup/restore: owner responsibility; restore must preserve audit rows; no destructive cleanup
  without explicit owner approval.
- Offline tampering cannot be prevented by SQLite triggers; access control/backups are external.

---

## 16. Single-process constraints

- One Bot + ASGI process; one authoritative `Database` instance; existing outbox/workers only.
- Review worker is an in-process `_BaseWorker`; no second process, no second DB owner.
- No multi-replica; `review_worker_lease` refuses a second active owner.
- Same event loop; no `asyncio.to_thread` for SQLite writes; short synchronous DB calls.
- WAL + `busy_timeout=5000` + `foreign_keys=ON` (existing `bot/db.py:692-698`).
- `BEGIN IMMEDIATE` for writes; no HTTP inside a write transaction.
- Start after existing recovery in `_post_init`; stop before `db.close()` in `_post_shutdown`.

---

## 17. End-to-end lifecycle

1. **Discovery:** org endpoint, filtered to the bot user/repo allowlist; baseline; tombstone check.
2. **Repository resolution:** GitHub numeric ID; verify `selected_repository`; store full-name snapshot.
3. **PR correlation:** native/trailer/owner mapping; verify token/PR/repo/ancestry; one PR per token.
4. **SHA pinning:** two reads; PR open; `base_sha` = merge-base; `base_ref_tip_sha`; ancestry.
5. **CI evidence:** check-runs for exact head; latest suite; per-check head SHA; store.
6. **Consent:** repo/provider/model/data classes/policy version/expiry.
7. **Payload construction:** diff `base_sha..head_sha`; selected files; manifest.
8. **Scan/redact:** path/content/entropy; re-scan; hash; fail closed.
9. **Blind Review:** allowlisted payload only; no report/verdict/prior output.
10. **Blind persistence:** structured JSON + evidence verification + report.
11. **Adversarial Review:** report + Blind result + diff; separate manifest.
12. **Evidence verification:** file/line/evidence; unsupported/duplicate handling.
13. **Deterministic verdict:** rule table; versioned; model recommendation ignored.
14. **Final report:** immutable; unique per cycle.
15. **Telegram delivery:** revalidate SHA/consent/tombstone; send; message_id.
16. **Manual reconciliation:** `UNKNOWN`; owner confirms; no auto-resend.
17. **Cancellation/supersession/recovery:** fence; terminal; new cycle; startup recovery.

---

## 18. Crash-window table

| # | Boundary | State before | Timeout/crash | State after recovery | Duplicate risk | Fencing/evidence |
|---|---|---|---|---|---|---|
| 1 | Org list/search | cursor | no write | retry; no missing until N misses | none | response timestamps |
| 2 | GitHub PR | `AWAITING_SHA` | no write | retry; NEEDS_OWNER after budget | none | PR JSON |
| 3 | GitHub compare | `SHA_CONFIRMING` | no write | retry; pin after two reads | none | compare JSON |
| 4 | GitHub check-runs | `CI_CHECK` | no write | retry; CI_MISSING after budget | none | check-run JSON |
| 5 | Provider Blind | `BLIND_RUNNING`, attempt row | response lost | attempt `SENT_UNKNOWN`; retry only per risk policy | possible billing | attempt row |
| 6 | Provider Adversarial | `ADVERSARIAL_RUNNING` | same | same | possible billing | attempt row |
| 7 | Telegram send | `SENDING` | accepted but lost | `UNKNOWN`; no auto-resend | manual only | delivery_ref |
| 8 | DB commit stage | local | crash before commit | no advancement; retry | provider cost possible | stage run |
| 9 | Consent check | `EGRESS_CHECK` | none | revoked → terminal | none | consent row |
| 10 | Secret scan | `EGRESS_CHECK` | local | fail → `EGRESS_BLOCKED` | none | scan summary |

No exactly-once provider or Telegram behavior is promised.

---

## 19. Acceptance-test matrix (36 proposed, unexecuted)

| # | Test | Expected DB | Expected external | Evidence |
|---|---|---|---|---|
| 1 | Concurrent cycle creation | one active cycle; loser re-reads | none | unique violation handled |
| 2 | Multiple PRs in one conversation | one active cycle; others queued/NEEDS_OWNER | none | `review_prs` rows |
| 3 | Same SHA in two repos | distinct cycles per repo | none | `(repository_id, head_sha)` |
| 4 | Repository rename | same cycle; full name updated snapshot | none | repository_id stable |
| 5 | Repo deletion/recreation | old `NOT_REVIEWABLE`; new ID/new cycle | none | 404/new ID |
| 6 | Unknown lifecycle | rejected | none | CHECK/state machine |
| 7 | NULL lifecycle/stage | rejected | none | NOT NULL/CHECK |
| 8 | Terminal cycle with stale worker | fenced; 0-row write | none | lease_epoch |
| 9 | Expired lease | claim by new worker; epoch++ | none | lease row |
| 10 | Supersession + replacement rollback | old remains ACTIVE | none | transaction rollback |
| 11 | Duplicate correlation token | reject/NEEDS_OWNER | none | token hash unique |
| 12 | Token copied to unrelated PR | reject/NEEDS_OWNER | none | repo/conversation binding |
| 13 | Trailer in ancestor commit | accept if ancestor+unique | none | commit range |
| 14 | Trailer absent from ancestry | NEEDS_OWNER | none | ancestry check |
| 15 | PR head changed after CI | `SUPERSEDED`; no delivery | none | old/new SHA |
| 16 | CI check SHA mismatch | reject; `CI_ERROR`/NEEDS_OWNER | none | check-run JSON |
| 17 | Provider timeout after transmission | `SENT_UNKNOWN`; attempt++ | possible billing | attempt row |
| 18 | Response lost before persistence | no SUCCEEDED; retry per risk | possible duplicate billing | stage run |
| 19 | Unknown billing at exposure limit | `NEEDS_OWNER`; no further calls | none | exposure ledger |
| 20 | Blind payload contains report | `ISOLATION_BLOCKED` | none | fingerprint match |
| 21 | Blind payload contains prior review | `ISOLATION_BLOCKED` | none | fingerprint match |
| 22 | Secret scanner failure | `EGRESS_BLOCKED` | none | scanner error |
| 23 | Consent revoked before request | `CONSENT_REVOKED` | none | consent row |
| 24 | Consent revoked during request | stored but marked; no verdict/delivery | possible provider retention | consent timestamps |
| 25 | Provider alias changes model | `NEEDS_OWNER`/new snapshot | none | model_version |
| 26 | Stale worker write | fenced; 0 rows | none | lease_epoch |
| 27 | Duplicate final report | unique violation | none | partial index |
| 28 | Telegram accepted, response lost | `UNKNOWN`; no auto-resend | possible delivered | delivery_ref |
| 29 | Tombstone before provider | `TOMBSTONED`; no call | none | `db.is_deleted` |
| 30 | Tombstone before Telegram | delivery blocked | none | tombstone check |
| 31 | Restart recovery | leases recovered; SENDING→UNKNOWN; PENDING resumes | no duplicate POST | startup log |
| 32 | Snapshot UPDATE/DELETE | trigger abort | none | trigger |
| 33 | Audit deletion | trigger abort | none | trigger |
| 34 | Malformed model output | retry/`EXHAUSTED`; no verdict | provider calls per budget | stage run |
| 35 | Unsupported finding | `UNSUPPORTED_FINDING`; HIGH→NEEDS_OWNER | none | evidence verification |
| 36 | Rule precedence | deterministic verdict | none | rule_id/rules_version |

All tests are **proposed**; none executed.

---

## 20. Open owner decisions

1. Conversation-wide (Alternative 1) vs per-PR (Alternative 2) serialization.
2. Commit-trailer convention and trust boundary.
3. OpenHands credential/service-account scope.
4. Data-egress policy and consent.
5. Provider/model selection and cost-risk acceptance.
6. Katabump persistence canary.
7. Revised lifecycle/repository identity design.
8. Final review-cycle design approval.
9. Authorization for a separate independent review.
10. R1 implementation authorization.

No approval is implied by this document.

---

## 21. Implementation boundaries

- No production code.
- No schema/migration.
- No tests/workflows/config.
- No provider calls.
- No Katabump operations.
- No R1.

---

## 22. Artifact inventory

- This document: `docs/reviews/OHB2-AUTO-REVIEW-R0E-REVISED-DESIGN-20261124.md`.
- Remediation report: `docs/reviews/OHB2-AUTO-REVIEW-R0E-DESIGN-REMEDIATION-REPORT-20261124.md`.
- Independent-review handoff: `docs/reviews/OHB2-AUTO-REVIEW-R0E-INDEPENDENT-REVIEW-HANDOFF-20261124.md`.
