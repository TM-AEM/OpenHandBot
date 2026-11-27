# OHB2-R7 — Phase B Author Self-Review (2026-11-25)

**Task:** `OHB2-R7-PHASE-B-AUTHORIZATION-AND-ACTIVATION-READINESS`
**Review type:** `AUTHOR_SELF_REVIEW` only.
**Verdict:** `R7_PHASE_B_READINESS_PARTIALLY_VERIFIED`

This is not independent review, not live validation, and not an R8 result. No worker was
activated and no external call was made.

---

## 1. Reviewed scope

1. Baseline Git state and working-tree inventory.
2. R7 canary linkage (`bot/review/canary_linkage.py`) and its 42 tests.
3. Resolver authorization, repository/PR/SHA verification, and reservation.
4. R1–R6 implementation and current reports.
5. `bot/app.py` worker construction, config, lifecycle, shutdown, and recovery.
6. `bot/review/worker.py`, `engine.py`, `collector.py`, `llm.py`, `report.py`,
   `prompts.py`, `redact.py`, `evidence.py`, `verdict.py`, `ci_contract.py`.
7. Telegram owner authorization, report delivery, callbacks, and `OWNER_ACCEPTANCE`.
8. OpenHands/GitHub/provider/Telegram/local runtime permissions.
9. Runbook and `.agent/PROGRESS.md`.
10. The five Phase B reports created by this task.

No production database was opened or modified.

---

## 2. Required checks

| Check | Result | Evidence |
|---|---|---|
| Baseline recorded without destructive Git | PASS | Branch/HEAD/main/origin/main/tree/status; no reset/clean/checkout |
| Historical claims reconciled with code | PASS | R7 F-01/F-02/F-03 fixed in current code; worker activation still absent; config fields not wired |
| D-03 authorization threats covered | PASS with gaps | Owner/private/cycle-chat/callback tests; missing canary entrypoint/factory; exact message-id not bound |
| D-04 options documented without schema change | PASS | Four options, migration/compat/tests/impact; no selection |
| D-05 rename/transfer documented | PASS | Reject-by-default; numeric ID not authorization |
| D-06 fork behavior documented | PASS | Cross-repo/fork PR rejected; repository-is-fork/archived policy open |
| D-07 activation design bounded | PASS | One PR/one chunk/four calls/one attempt/expiry/lease/outbox/audit |
| D-07 implementation authorized | **NO** | Design only; no worker construction or startup wiring |
| D-08 resource/permission matrix | PASS | OpenHands, GitHub, provider, Telegram, local runtime |
| Provider cost/egress controls | PASS with blocker | No hard cost/token limit; live inference blocked |
| Reports created at exact paths | PASS | Five required files present |
| PROGRESS updated additively | PASS | Existing history retained |
| No code changes | PASS | Only docs/runbook/progress changed |
| Full Python suite | PASS | 4296 passed, 74 warnings, 319.12s |
| Node suite | PASS | 280 pass, 0 fail |
| Focused review suite | PASS | 472 passed |
| pyflakes / compileall / Bandit / pip-audit / diff check | PASS | 0 issues / 0 errors / High 0 / no vulnerabilities / clean |
| No external calls/data transmission | PASS | No OpenHands/GitHub/provider/Telegram call |
| No worker activation | PASS | No `ReviewWorker`/`ReviewRunner` constructed |
| No Git publication | PASS | No commit/push/PR/merge/deploy/release |
| Independent review deferred | PASS | Author self-review only |

---

## 3. Findings

### F1 — D-03 canary entrypoint/factory is missing (BLOCKER for live)

`CanaryLinkageService` is locally implemented but not constructed by `bot/app.py`. There
is no command/callback that binds it to `Config.owner_id`, enforces private chat, accepts
an explicit PR list, and starts a reservation. The service constructor accepts a
caller-supplied `owner_id`; a future factory must pass `Config.owner_id`.

**Impact:** D-02 cannot be used live yet. This is a runtime gap, not an authorization
bypass in the existing callback path.

**Disposition:** Keep D-03 open; implementation requires approval.

### F2 — D-04 provenance remains unresolved (BLOCKER for identity continuity)

`creation_jobs` does not store the GitHub numeric ID observed at creation. The current
source verifies the current GitHub identity but cannot distinguish a same-name
deleted-and-recreated repository. Options A–D are documented; no schema change was made.

**Impact:** No identity-continuity claim is safe. The canary may proceed only with an
explicit no-recreation attestation or after an owner-approved durable-ID design.

**Disposition:** D-04 `OWNER_DECISION_REQUIRED`.

### F3 — D-05/D-06 policies are reject-by-default but not complete (MEDIUM)

Rename/transfer and cross-repository/fork PRs are rejected. However:

- a repository that is itself a fork/archived/private is parsed but not explicitly
  rejected by the resolver;
- `RepositoryIdentity.fork`/`archived` are not part of eligibility;
- rename/transfer handling may surface as `MALFORMED_EXTERNAL_RESPONSE` or canary
  `None`, not always a distinct policy code.

**Impact:** No false association, but the eligibility policy is incomplete. An owner
decision is needed for fork/archived/private repository eligibility.

**Disposition:** D-05/D-06 remain open; no behavior change.

### F4 — D-07 worker is not ready for one-canary activation (BLOCKER)

- `ReviewWorker._claim()` has no review/conversation filter.
- `_BaseWorker._run()` is unbounded; no one-shot mode.
- No canary activation config or exact claim.
- No provider call/chunk budget.
- No startup wiring, by design.

**Impact:** Starting the current worker against a shared DB could process unrelated
cycles and generate excessive provider calls.

**Disposition:** Design provided; implementation and owner approval required.

### F5 — Config fields are not wired (MEDIUM)

`REVIEW_CI_TIMEOUT_MIN` is parsed/tested but unused. `REVIEW_MAX_INPUT_CHARS` and
`REVIEW_REPOS` are not consumed by any R2–R7 worker factory. `REVIEW_ENABLED` only
validates config.

**Impact:** An operator could believe these settings bound live behavior. The runbook now
states they are not wired.

**Disposition:** Runbook corrected; no runtime change.

### F6 — Provider cost/token ceiling is absent (BLOCKER for live inference)

No `max_tokens`, token ledger, pricing, balance, quota, or spend ceiling exists. The
theoretical upper bound is large (up to 80 calls per PR; 1,600 for 20 PRs; multiplied by
attempts). The proposed canary envelope is one PR, one chunk per stage, four calls, one
attempt.

**Impact:** No safe live inference until a provider-side hard cap or explicit bounded
exposure is approved.

**Disposition:** Provider report; live inference blocked.

### F7 — “Independent review” wording may overclaim (LOW)

Generated report titles/summary and UI copy use “مراجعة مستقلة”. This task does not claim
independent review; the phrase should be clarified or changed only with owner approval
because it is user-facing product wording.

**Disposition:** Note; no wording change in this task.

### F8 — Callback is chat-bound, not exact-message-bound (LOW)

`_review_owner_allowed()` checks `cycle.chat_id` and the callback message `chat_id`, but
not the exact Telegram `message_id`. A callback from another bot-sent copy of the same
report in the same owner/cycle chat can be accepted. Cross-chat callbacks are rejected.

**Disposition:** Document; no code change.

---

## 4. Positive findings

- Owner/private-chat/cross-chat callback authorization is tested and fails closed.
- Conversation-wide reservation and immutable membership snapshots are atomic.
- Provider snapshot binding is enforced before collector/provider work.
- CI job completeness is contract-based and fail-closed.
- Branch/SHA is re-verified before and after evidence collection.
- Report delivery is outbox-backed with at-most-once semantics and `unknown` on ambiguity.
- Owner acceptance is separate, immutable, and does not alter the technical verdict.
- No production data or credentials were exposed.
- No worker was activated.

---

## 5. Local verification

No production code or test code changed. The runbook, README, five reports, and PROGRESS changed.

| Command | Result |
|---|---|
| Focused Phase B selection | **192 passed** in 15.74s |
| Broader review-focused suite | **472 passed** in 17.96s |
| Full Python suite | **4296 passed**, 74 warnings, 319.12s |
| Node suite | **280 pass**, 0 fail |
| pyflakes | **0 issues** |
| compileall | **0 errors** |
| Bandit (`-lll -s B613`) | **High 0**; Low 7, Medium 20 |
| pip-audit | **No known vulnerabilities** |
| `git diff --check` | clean |

Python 3.11 and remote CI were not run. No live external operation was performed.

---

## 6. Residual limitations

- Author self-review only; no independent verification.
- No live OpenHands/GitHub/provider/Telegram evidence.
- D-03 through D-09 remain owner decisions.
- No canary activation implementation.
- No provider entitlement, pricing, or spend cap.
- No disposable repository/branch/PR or Telegram test destination.
- The report wording “مراجعة مستقلة” is not an independent-review claim.
- R8 has not started.

---

## 7. Conclusion

The local implementation is verified and the Phase B designs are documented. The live
canary remains blocked by missing authorization, provenance, activation, resource, and
provider-cost decisions. Final verdict:
**`R7_PHASE_B_READINESS_PARTIALLY_VERIFIED`**.
