# OHB2-R7 — Temporary ReviewWorker Activation Design (2026-11-25)

**Task:** `OHB2-R7-PHASE-B-AUTHORIZATION-AND-ACTIVATION-READINESS`
**Status:** design only. No worker was constructed, started, or wired into `bot/app.py`.
**Readiness conclusion:** the current worker architecture is **not ready for live
activation as-is**. A bounded supervisor and provider/request guards are required first.

---

## 1. Current architecture facts

| Fact | Evidence |
|---|---|
| `bot/app.py` constructs `ReviewReportService` and registers `^review:` | `bot/app.py` startup and handler registration |
| `bot/app.py` does not construct `ReviewRunner` or `ReviewWorker` | `bot/app.py` only starts outbox/creation/completion/watcher/notifier workers |
| `REVIEW_ENABLED=1` validates config only | `bot/config.py`; runbook §“حدود تفعيل المراجعة” |
| `ReviewWorker._claim()` claims any eligible conversation-wide cycle | `bot/review/worker.py:_claim`; `bot/db.py:claim_auto_review` has no review/conversation filter |
| `ReviewWorker` inherits an unbounded `_BaseWorker._run()` loop | `bot/outbox.py:_BaseWorker` |
| `ReviewRunner` processes every membership and every prompt chunk | `bot/review/worker.py:ReviewRunner.run` |
| `MAX_CHUNKS = 20` per stage | `bot/review/prompts.py` |
| `execute_stage()` allows one schema-correction request | `bot/review/llm.py:execute_stage` |
| `ReviewRunner` has no provider-call/token budget | `bot/review/worker.py:_execute_requests` |
| `REVIEW_CI_TIMEOUT_MIN` is not consumed by collector/worker | config only; no runtime reference |
| `REVIEW_MAX_INPUT_CHARS` is not wired into a worker factory | config/tests only; no factory |
| `REVIEW_REPOS` is not wired into a live `GitHubClient` factory | config only; no factory |
| Lease token/epoch and stage/outbox idempotency exist | `bot/db.py`, `bot/review/worker.py`, tests |

### 1.1 Why the existing worker is unsafe for a one-canary run

1. **Claim scope is too broad.** `claim_auto_review()` can claim any eligible cycle in
   the database. A shared/production database could process unrelated work.
2. **No one-shot boundary.** The worker loop runs indefinitely and can claim another
   cycle after the first.
3. **No provider budget.** One PR can generate up to 40 blind calls and 40 adversarial
   calls when both stages have 20 chunks and each uses one correction. Multiple PRs and
   cycle retries multiply this.
4. **No activation configuration.** There is no exact conversation/repository/PR/cycle
   allowlist, expiry, or canary identity.
5. **No provider/cost ceiling.** There is no `max_tokens`, token ledger, price data, or
   hard spend stop.
6. **No live factory.** `REVIEW_REPOS`, `REVIEW_MAX_INPUT_CHARS`, and
   `REVIEW_CI_TIMEOUT_MIN` are validated but not consumed by a runtime path.

**Therefore: do not start the existing `ReviewWorker` against a production or shared
database. Use the design below only after owner approval and implementation.**

---

## 2. Proposed activation mode (disabled by default)

A new, separate mode, never enabled by `REVIEW_ENABLED` and never wired into
`bot/app.py`:

```text
REVIEW_CANARY_ENABLED=0                  # default; must be explicitly 1
REVIEW_CANARY_ID=<unique audit id>
REVIEW_CANARY_OWNER_ID=<must equal Config.owner_id>
REVIEW_CANARY_CONVERSATION_ID=<exact OpenHands conversation id>
REVIEW_CANARY_REPOSITORY_ID=<exact GitHub numeric repository id>
REVIEW_CANARY_REPOSITORY_FULL_NAME=<exact canonical owner/repo>
REVIEW_CANARY_PR_NUMBERS=<exactly one explicit PR number>
REVIEW_CANARY_PROVIDER_SNAPSHOT_ID=<exact immutable snapshot id>
REVIEW_CANARY_DB_PATH=<isolated SQLite path, never production>
REVIEW_CANARY_EXPIRES_AT=<UTC ISO-8601 deadline>
REVIEW_CANARY_MAX_PROVIDER_CALLS=4
REVIEW_CANARY_MAX_STAGE_REQUESTS=1
REVIEW_CANARY_MAX_INPUT_CHARS=20000
REVIEW_CANARY_MAX_ATTEMPTS=1
```

These names are a proposed design, not an implemented configuration contract. No new
trusted identifier is introduced: `REVIEW_CANARY_OWNER_ID` is only a redundant audit
check and must equal the existing `Config.owner_id`.

### 2.1 Hard design choices

- **One PR only.** The explicit list must contain exactly one PR. This preserves D-02
  and avoids multi-PR cost multiplication.
- **One chunk per stage.** If a prompt builder would produce more than one request per
  stage, the supervisor aborts before any provider call.
- **Four provider calls maximum.** Blind initial + optional correction + adversarial
  initial + optional correction. No provider-level retry.
- **One cycle attempt.** `max_attempts=1`; no automatic retry, no model fallback, no
  provider switch.
- **No PR discovery.** The PR is supplied explicitly and verified by the existing
  resolver.
- **No production DB.** The supervisor must refuse a path equal to the normal
  `DB_PATH` or a production database.
- **No app wiring.** A standalone command/process only; `bot/app.py` remains unchanged.

---

## 3. Preflight (no external calls)

The supervisor must fail closed before constructing a provider or GitHub client if any
check fails:

1. `REVIEW_CANARY_ENABLED == 1` and the deadline is in the future.
2. `REVIEW_CANARY_OWNER_ID == Config.owner_id`.
3. The DB path is isolated and is not the normal production DB path.
4. The exact cycle exists and is `reserved`/eligible for this one run.
5. Cycle `conversation_id`, `chat_id`, `repository_id`, `repository_full_name`,
   `pr_number`, `head_sha`, `base_sha`, `branch`, `provider_snapshot_id`, and
   `membership_count` exactly match the canary config.
6. The cycle has exactly one membership and it is the configured PR.
7. The provider snapshot exists and is immutable; `ProviderBinding.from_config()` matches
   provider/api_base/model/fingerprint and the exact snapshot ID.
8. The repository is in the review allowlist and the explicit PR list has one valid
   positive integer.
9. `REVIEW_MAX_INPUT_CHARS` is the canary value. The Blind prompt can be preflighted
   locally; the Adversarial prompt is checked after the validated Blind output exists.
   Any stage that would produce more than one request aborts before that stage’s
   provider call.
10. No other claimable/active review cycle exists in the isolated DB.
11. `REVIEW_AUTOFIX_ROUNDS == 0`; no automatic fix loop.
12. A recorded owner approval identifier exists in the audit report; this is not a new
    authorization source, only an audit reference.

Preflight must not call OpenHands, GitHub, the provider, or Telegram. It may read the
isolated DB and the local config.

---

## 4. One-shot supervisor design

Proposed components (not implemented):

- `CanaryActivationConfig` — validated immutable settings.
- `CanaryPreflight` — local checks above.
- `BudgetedProvider` — wraps the existing `DirectProviderAdapter` and counts every
  `complete()` call; raises a safe `ProviderError` before exceeding the cap.
- `ExactCycleClaim` — exact DB claim by `review_id` (new optional filter/method), not
  the broad `claim_auto_review()` query.
- `CanaryReviewSupervisor` — one-shot orchestration.

### 4.1 Execution sequence

```text
preflight (local only)
  -> construct GitHubClient with exact allowlist
  -> construct ProviderBinding + DirectProviderAdapter
  -> construct BudgetedProvider(max_calls=4)
  -> construct GitHubEvidenceCollector
  -> construct ReviewRunner(provider_binding=..., max_input_chars=20000,
                            max_requests_per_stage=1)   # proposed guard
  -> exact claim of the configured review_id
  -> verify claim fields
  -> ReviewWorker._process(claim) once
  -> stop; never call _run()
```

The supervisor must **not** call `worker.start()` or `_BaseWorker._run()`.

### 4.2 Exact claim and unrelated-cycle prevention

Preferred implementation:

- Add an optional `review_id` (and conversation/chat) filter to
  `Database.claim_auto_review()` or a dedicated `claim_auto_review_exact()`.
- Claim only the configured cycle; return `None` if the lease is held by another worker.
- Re-check the claimed cycle fields before any collector/provider call.
- If the claim is not exact, release the lease only if no provider call has started, and
  abort.

Fallback (less strong): use a dedicated isolated DB containing only the canary cycle.
The design still requires the exact claim check; isolation alone is not a substitute for
the check.

### 4.3 Provider call and chunk limits

- `MAX_CANARY_PROVIDER_CALLS = 4` enforced by `BudgetedProvider`.
- `MAX_CANARY_STAGE_REQUESTS = 1` enforced by a `ReviewRunner` guard before
  `execute_stage()`.
- `MAX_CANARY_INPUT_CHARS = 20000`; if the diff cannot fit in one request, abort before
  provider.
- No `max_tokens` support exists in the adapter. If the provider supports it, the
  implementation must add an explicit output-token field and tests. If it does not, a
  hard token ceiling cannot be claimed; the provider-side spend limit or explicit
  bounded-exposure approval is mandatory.
- No model fallback, no provider switching, no hidden retries, no `REVIEW_AUTOFIX_ROUNDS`.

### 4.4 Lease and fencing

- Use the existing lease token/epoch.
- Renew before each stage and before completion.
- If the lease is lost, stop immediately; do not complete, deliver, or retry.
- A second supervisor cannot take over until the lease expires.
- Do not release the lease after a provider call has started; leave it to expire and
  require manual audit. Release only for a clean pre-provider abort.

### 4.5 Duplicate events and crash/restart

- One-shot supervisor: no second cycle claim.
- Existing stage/evidence/outbox idempotency remains in force.
- A crash after a provider call but before persistence is ambiguous; do not auto-retry.
  Restart is manual and requires an explicit operator decision.
- A crash after verdict/report persistence leaves `delivery_pending`; the existing report
  recovery/outbox path may deliver once, but only through the normal outbox and with the
  owner chat.
- A second process must lose the lease race; if it claims, it must verify the exact
  canary identity and budget before provider use.

### 4.6 Graceful shutdown

- Cancel the supervisor task and await it.
- Close the GitHub and provider HTTP clients.
- Do not mark a delivery `sent` if the Telegram call did not return success.
- Preserve the lease and DB state for audit if a provider call may have been sent.
- The existing `_BaseWorker.stop()` cancels but does not release the lease; that is
  compatible with fail-closed ambiguity, but the supervisor must document it.

### 4.7 Outbox and Telegram

- Reuse `ReviewReportService` and the existing single outbox intent.
- Destination is `cycle.chat_id` (owner private chat) only.
- Ambiguous Telegram error remains `unknown`; no automatic retry.
- Details/Accept/Reject use the existing owner-only callback path.
- No direct Telegram send from the supervisor.

### 4.8 Audit evidence

Use existing durable rows:

- `auto_reviews` (cycle, snapshot, lifecycle, attempts, verdict, delivery state);
- `auto_review_memberships` (exact immutable PR/SHA);
- `auto_review_evidence`, `auto_review_stages` (validated evidence/results);
- `auto_review_leases` (owner/token/epoch/expiry);
- `auto_review_reports`, `outbox` (report and delivery intent/status);
- `auto_review_owner_acceptance` (owner decision, if exercised).

Plus a separate local canary audit note (not a new DB table) recording the canary ID,
owner approval reference, exact config, preflight result, call count, and stop reason.
No schema change is proposed in this task.

### 4.9 Automatic expiration / shutdown

- Refuse to start after `REVIEW_CANARY_EXPIRES_AT`.
- Do not auto-extend.
- Stop after one claim/process attempt.
- If the cycle is not terminal after the attempt, leave it for manual inspection; do not
  start a second cycle.

---

## 5. Hard stop conditions

The supervisor must stop without retry or delivery on any of:

- wrong owner, conversation, repository ID/name, PR, cycle, or provider snapshot;
- more than one PR or more than one stage request;
- provider-call budget exhausted;
- provider auth/forbidden/rate-limit/server/transport/malformed/oversized response;
- unknown pricing or missing hard spend limit;
- evidence/SHA/branch/CI mismatch or incomplete CI;
- lease lost or expired;
- DB read/write/lock failure;
- report generation/save/outbox failure after verdict;
- ambiguous Telegram delivery (mark unknown, never sent);
- expiry;
- any unexpected exception before a safe terminal state.

A failed validation must not create an active cycle, and a failed delivery must not be
reported as success.

---

## 6. Implementation plan for owner approval

1. Add canary activation configuration and local preflight (no app wiring).
2. Add an exact cycle claim/filter with tests for wrong cycle/conversation/PR.
3. Add `BudgetedProvider` and a `ReviewRunner` per-stage request guard.
4. Add the one-shot `CanaryReviewSupervisor` and a standalone entrypoint (not
   `bot/app.py`).
5. Add tests:
   - disabled by default and expiry;
   - wrong owner/conversation/repository/PR/provider snapshot;
   - exact claim and second-claim rejection;
   - provider call cap and chunk cap;
   - no fallback/switch/retry;
   - lease loss and crash/restart;
   - outbox delivery, ambiguous Telegram, no false sent;
   - no provider/GitHub/Telegram call during preflight.
6. Obtain owner approval for D-03 through D-08 and the bounded exposure.
7. Provision disposable resources and run a local dry run with fakes.
8. Only then request authorization for a single live canary.

**No step in this plan is authorized by this report.**

---

## 7. Conclusion

The existing worker is a verified local orchestration primitive, not a safe live canary
runner. The bounded design above can enforce a one-conversation/one-PR/one-cycle/four-
provider-call boundary, but it requires new code, tests, and explicit owner approval.
Until then, `ReviewWorker` must remain unconstructed and inactive.
