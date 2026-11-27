# OHB2-R7 — Provider Cost and Data-Egress Report (2026-11-25)

**Task:** `OHB2-R7-PHASE-B-AUTHORIZATION-AND-ACTIVATION-READINESS`
**Scope:** inspection and design only. No provider call, inference, quota check, or data
transmission occurred.

---

## 1. Current provider implementation

### 1.1 Adapter

`bot/review/llm.py:DirectProviderAdapter` is a small OpenAI-chat-compatible adapter:

- endpoint: `<REVIEWER_API_BASE>/chat/completions` (or the exact base ending in
  `/chat/completions`);
- request: `model`, `messages` (system + user), `stream=false`, `temperature=0`;
- auth: `Authorization: Bearer <REVIEWER_API_KEY>`;
- no tools, no function calling, no response format, no `max_tokens`;
- no automatic provider retry;
- one bounded schema-correction request after a valid provider response with invalid
  JSON/schema (maximum two calls for that stage/request);
- default timeout 20s, maximum 120s; connect/read/write/pool bounded;
- request body default 256 KiB, maximum 2 MiB;
- response body default 1 MiB, maximum 4 MiB;
- redirects rejected; non-2xx classified safely; no response body or key in errors.

### 1.2 Provider configuration

Current facts, without values:

- `.env` does not exist in the workspace.
- `REVIEWER_API_KEY` is not set.
- `REVIEWER_PROVIDER`, `REVIEWER_API_BASE`, and `REVIEWER_MODEL` are not configured.
- `REVIEW_GITHUB_TOKEN` is not set.
- An `OPENHANDS_API_KEY` is present in the runtime environment, but it is not a reviewer
  credential and is not authorized for live R7 use.
- No model entitlement, quota, pricing, balance, or credit state can be established
  locally. Model catalog visibility is not proof of entitlement.

`REVIEWER_PROVIDER` is a free-form bounded identifier; the adapter does not implement
provider-specific entitlement or pricing checks. `REVIEWER_MODEL` is passed through
unchanged.

---

## 2. Call-count exposure

### 2.1 Per request

`execute_stage()` performs:

1. one initial provider call; and
2. at most one schema-correction provider call if the initial response is a valid HTTP
   response but invalid schema.

Therefore one prompt request can produce **up to 2 provider calls**.

### 2.2 Per PR

`MAX_CHUNKS = 20` per stage (`bot/review/prompts.py`).

| Stage | Max requests | Max calls with correction |
|---|---:|---:|
| Blind | 20 | 40 |
| Adversarial | 20 | 40 |
| **Per PR** | **40** | **80** |

### 2.3 Per cycle

`CanaryLinkageService` permits up to 20 PR candidates. `ReviewWorker` default
`max_attempts=5`; the DB allows up to 20.

| Scenario | Max provider calls |
|---|---:|
| 1 PR, 1 chunk, 2 stages, no correction | 2 |
| 1 PR, 20 chunks, 2 stages, corrections | 80 |
| 20 PRs, 20 chunks, corrections | 1,600 |
| 20 PRs, 20 chunks, corrections, default 5 attempts | 8,000 |
| 20 PRs, 20 chunks, corrections, max 20 attempts | 32,000 |

These are upper bounds, not expected usage. Stage/evidence persistence can reduce repeat
calls, but there is **no provider-call counter or hard stop** in the current code.

### 2.4 Other controls that do not exist

- No `max_tokens` / output-token limit.
- No input-token accounting.
- No usage/ledger parsing from responses.
- No pricing table, balance check, quota API, or estimated-cost ceiling.
- No per-canary provider-call budget.
- No automatic model fallback (good) and no automatic provider switching (good), but also
  no explicit preflight rejection when pricing/limits are unknown.
- `REVIEW_CI_TIMEOUT_MIN` is parsed but unused; it cannot cap provider/CI work.
- `REVIEW_MAX_INPUT_CHARS` is parsed but not wired into a live worker factory.

---

## 3. Data sent to the provider

### 3.1 Blind stage

The provider receives:

- system prompt for the Blind Reviewer;
- trusted manifest metadata: repository, PR number, branch, base/head SHA, diff/CI
  hashes, chunk index/count, included/excluded source names;
- redacted unified diff chunk;
- CI metadata: workflow run/job names, statuses, conclusions, IDs, SHAs;
- architecture decisions and review instructions;
- no OpenHands implementation report, OpenHands verdict, prior review, adversarial
  output, conversation history, PR body/comments, commit messages, or CI logs.

### 3.2 Adversarial stage

The provider receives the same diff/CI/architecture/instructions plus:

- the validated Blind result JSON;
- the OpenHands implementation report (redacted/bounded);
- the Blind fingerprint.

### 3.3 Data not sent

- No API keys, Telegram tokens, GitHub tokens, database contents, owner chat ID, or
  credential values.
- No raw GitHub response body or raw provider response body is logged.
- Raw diffs are not persisted in the review evidence table; only hashes and metadata are
  stored there. Stage outputs are persisted after redaction.

### 3.4 Redaction and egress limitations

`bot/review/redact.py` applies pattern-based redaction for private keys, authorization
headers, bearer tokens, connection credentials, GitHub/AWS/Slack/Stripe/Google/JWT/API
key patterns, generic assignments, and query parameters. It re-scans and blocks if a
pattern remains.

Path controls exclude `docs/`, `*.patch`, `*.zip`, `package-lock.json`, binary sections,
unsafe paths, and path traversal. Excluded paths make prompt/evidence completeness fail
closed.

Residual risks:

- No entropy detector; a high-entropy secret not matching a pattern can pass.
- Secrets in reviewed source code are still transmitted as redacted diff content.
- Provider-side retention, logging, training use, and jurisdiction are outside local
  control and must be approved by the owner.
- CI metadata includes repository/job names and SHAs; these are not secrets but are
  external metadata.
- The OpenHands implementation report is transmitted in the adversarial stage; it must
  be treated as potentially sensitive.

---

## 4. Required cost-control design

This is a proposed design, not implemented.

### 4.1 Hard canary envelope

| Control | Proposed value |
|---|---|
| PRs per canary | **1** |
| Prompt requests per stage | **1** |
| Stages | Blind + Adversarial |
| Schema corrections | At most 1 per request |
| Max provider calls | **4** |
| Cycle attempts | **1** |
| Max input chars | **20,000** |
| Max output tokens | Only if provider supports it; otherwise explicitly unavailable |
| Max response bytes | Existing 1 MiB default |
| Timeout | Existing 20s default |
| Automatic fallback | **None** |
| Automatic provider switch | **None** |
| Hidden retry loop | **None** |

The `ReviewRunner` must abort before any provider call if the prompt builder would emit
more than one request per stage. A `BudgetedProvider` wrapper must count every
`complete()` call, including correction requests, and stop before call 5.

### 4.2 Preflight and hard stops

Before provider use, require:

- exact owner approval and canary identity;
- exact conversation/repository/PR/cycle/provider snapshot;
- one PR and one chunk per stage;
- provider snapshot binding verified;
- provider-side hard spend limit configured, or an explicit owner acceptance of bounded
  exposure;
- known model entitlement and pricing/usage terms, or an explicit owner acceptance;
- no automatic fallback or retry.

Stop immediately without retry on:

- unknown pricing/limit;
- provider auth/forbidden/rate-limit/server/transport/malformed/oversized response;
- budget exhaustion;
- lease loss;
- evidence/SHA/CI mismatch;
- any unexpected error.

### 4.3 Monetary ceiling

No monetary ceiling is invented. The implementation has no price table or balance API.
The owner must provide either:

1. a provider-side hard spend cap that cannot be exceeded by the canary; or
2. an explicit written acceptance of a bounded exposure, with a maximum call count,
   maximum input size, and no automatic retry.

Without one of these, **provider inference remains blocked**.

### 4.4 Token controls

The current adapter does not send `max_tokens`. If the selected provider supports it,
the implementation must add:

- an explicit output-token limit;
- an input-token estimate or provider-reported usage capture;
- a preflight rejection when the estimate exceeds the canary limit;
- tests for provider responses without usage data.

If the provider cannot enforce a hard token/spend limit, no token ceiling can be claimed;
the provider-side spend cap or owner acceptance is the only remaining control.

---

## 5. Audit and verification requirements

A live canary must record:

- provider/model/api-base snapshot identity (no key);
- exact call count, per stage and correction;
- request sizes and response sizes where available;
- provider-reported usage, if any;
- stop reason and terminal state;
- no retry/fallback/switch event;
- exact data-egress version (redaction rules, prompt version, schema version);
- owner approval reference and expiry.

No provider call was made for this report. No credential value was printed or
transmitted.

---

## 6. Conclusion

The current adapter is technically bounded in bytes and time, but it has **no reliable
cost ceiling, no token accounting, and no canary call budget**. The default code can
generate far more provider calls than are acceptable for a controlled canary. Live
inference remains blocked until the owner approves and implements the four-call/one-PR/
one-chunk envelope and either a provider-side hard spend limit or an explicit bounded
exposure.
