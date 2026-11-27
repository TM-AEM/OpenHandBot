# OHB2-AUTO-REVIEW-R7 — Live End-to-End Readiness Report (2026-11-25)

## 0. Scope and verdict

**Task:** OHB2-AUTO-REVIEW-R7 — Live End-to-End Validation Readiness, Controlled Canary, and
Evidence Verification.

**Phase:** A only — readiness audit and non-invasive test preparation.

**Verdict:** `R7_READINESS_NEEDS_FIXES`

Phase A found a complete local R1–R6 implementation with a green local suite, but the live
end-to-end path is not yet ready for Phase B. The blocking gaps are the unresolved
conversation → PR → exact SHA association (B-01), the absence of an authorized runtime entrypoint
for the review worker, and a CI-evidence gap where a successful run with incomplete/missing job
evidence can still reach a deterministic `PASS`.

**No live operation was performed for this report.** No OpenHands conversation was created, no
GitHub branch/PR/Actions operation was performed, no provider inference was requested, no Telegram
message was sent, and no review worker was started.

---

## 1. Baseline Git state

Recorded before creating this report:

| Item | Value |
|---|---|
| Repository path | `/workspace/project/OpenHandBot` |
| Branch | `agent/r6-review-delivery` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `origin/main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| HEAD tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| Tracked files | 569 |
| Modified tracked files | 12 |
| Untracked files | 38 |
| Remote | `https://github.com/TM-AEM/OpenHandBot.git` |
| Git user | `openhands <openhands@all-hands.dev>` |

Working-tree inventory (preserved, not modified by this task):

- Modified: `.agent/PROGRESS.md`, `.env.example`, `README.md`, `bot/app.py`, `bot/config.py`,
  `bot/db.py`, `bot/handlers.py`, `bot/outbox.py`, `docs/OPERATIONS_RUNBOOK.md`,
  `tests/test_def011_a_option_b_limits.py`, `tests/test_def011_fs_offload.py`,
  `tests/test_doc_code_parity.py`.
- Untracked R1–R6 implementation: `.github/workflows/verify.yml`, `bot/review/` (12 modules),
  17 review test modules plus `tests/_review_r6_helpers.py`, and the R0E/R0F/R1–R6 review reports.
- The R1–R6 work is uncommitted. No commit, push, PR, merge, deploy, or release was performed.

Environment:

| Tool | Version |
|---|---|
| Python | 3.13.15 |
| Node | 24.22.2 |
| npm | 12.2.2 |
| SQLite | 3.46.1 |
| python-telegram-bot | 22.8 |
| httpx | 0.28.1 |
| pytest | 9.0.3 |
| Git | 2.47.3 |

No `.env` file exists in the workspace and no `REVIEW_*`/`REVIEWER_*` environment variable is set.
No real provider, GitHub, OpenHands, or Telegram credential was read or printed.

---

## 2. R1–R6 integration status

| Stage | Implemented artifacts | Local status | Live status / limitation |
|---|---|---|---|
| R1 — CI exact-SHA protections | `.github/workflows/verify.yml`, `tests/test_verify_workflow_security.py` | Verified locally; workflow structural tests pass | Remote Actions never executed; `ci.yml` unchanged and main-only |
| R2 — configuration, snapshots, reservations | `bot/config.py`, `bot/db.py`, `tests/test_review_config.py`, `tests/test_auto_reviews_db.py` | Verified locally; config validation, immutable snapshots, idempotent reservations pass | No real provider/model/key/base URL configured; no live inference |
| R3 — read-only GitHub + redaction | `bot/review/github.py`, `bot/review/redact.py`, `bot/review/collector.py`, tests | Verified locally with mock transports; exact SHA and path/secret controls pass | No live GitHub request; no required-check policy; job completeness gap |
| R4 — isolated review engine | `bot/review/schema.py`, `prompts.py`, `evidence.py`, `llm.py`, `engine.py`, `verdict.py`, tests | Verified locally; Blind/Adversarial isolation, schema, evidence validation, deterministic verdict pass | No provider call; no live model output |
| R5 — durable lifecycle/worker | `bot/review/worker.py`, R5 tables/APIs in `bot/db.py`, lifecycle tests | Verified locally; membership snapshots, leases/fencing, retry, resume, outbox intent pass | Worker is not started by `bot/app.py`; no conversation→PR membership discovery; no live run |
| R6 — Telegram report/owner interaction | `bot/review/report.py`, `bot/outbox.py`, `bot/handlers.py`, `bot/app.py`, R6 tests | Verified locally; deterministic report, exact-version Details, owner-only callbacks, durable owner decisions pass | No Telegram message or callback; no live file/caption limits verified |

Important integration facts:

- `bot/app.py` constructs `ReviewReportService` and registers `^review:` (`bot/app.py:114-117`,
  `:150`), but it starts only the existing outbox, creation, completion, watcher, and notifier
  workers (`bot/app.py:282-329`). It never constructs `GitHubClient`, `DirectProviderAdapter`,
  `ReviewRunner`, or `ReviewWorker`.
- `REVIEW_ENABLED=1` currently means configuration validation only. There is no runtime switch that
  starts a review worker.
- R5 membership APIs require a caller-supplied `AutoReviewMembership` tuple. No code maps an
  OpenHands conversation to its PR memberships or derives the exact head SHA from that conversation.
  `bot/messages.py:93-95` only reads an existing `pr_number` for a display link.
- The R1 `verify.yml` exact-SHA workflow is present but untracked. It has never run remotely.

---

## 3. External dependency readiness matrix

Status vocabulary: `LOCAL_OK`, `READY_FOR_LIVE`, `GAP`, `BLOCKED`, `UNVERIFIED_LIVE`.

### A. OpenHands

| Question | Finding | Status |
|---|---|---|
| Supported creation mechanism | `OpenHandsClient.start_conversation()` posts to `/app-conversations` with `initial_message`, optional `selected_repository`, optional `selected_branch`; `wait_for_start()` polls `/app-conversations/start-tasks` (`bot/openhands_client.py:386-444`). | LOCAL_OK |
| Repository association | `selected_repository` / `selected_branch` are accepted. The client does not send `pr_number`; R0E evidence records `pr_number` as an array field accepted at start but not populated by the bot (`bot/openhands_client.py:386-397`). | GAP |
| Exact PR and commit SHA | A controlled task can create/update a branch; the exact head SHA must be read from GitHub, not assumed from the conversation. R5 `AutoReviewMembership` requires `repository_id`, `repository_full_name`, `pr_number`, `branch`, `base_sha`, `head_sha`. | GAP |
| Prevent production work | Use a dedicated disposable repository and an `agent/r7-canary-*` branch; never select `main`; protect `main`; do not run against `TM-AEM/OpenHandBot`. | DESIGNED |
| Conversation isolation | Use one dedicated test conversation and one isolated SQLite database. Do not point it at the production bot DB or production chat. | DESIGNED |
| Disposable target available | **No disposable repository/branch exists in this workspace.** Creating one is a Phase B GitHub write and is not authorized here. | BLOCKED |
| Credentials/permissions | OpenHands API key able to create conversations and send messages; GitHub App installation/repository access; GitHub token read access for the review collector; provider key; Telegram owner bot. Exact scopes must be confirmed without printing values. | UNVERIFIED_LIVE |
| Conversation → PR mapping | No supported bot mechanism or verified resolver example. R0E B-01 remains `UNVERIFIED`: no real conversation with non-empty `pr_number` and matching PR/SHA/CI. | BLOCKED |

### B. GitHub Actions

| Question | Finding | Status |
|---|---|---|
| Existing workflows | `ci.yml` runs on `push`/`pull_request` to `main`, with `contents: read`, `Tests & lint` (Python 3.11/3.13) and `Frontend tests (Node)`. `verify.yml` runs on `push` to `agent/**` and `workflow_dispatch` with required `head_sha`. | LOCAL_OK |
| Exact-SHA checkout | `verify.yml` validates a full 40-character lowercase SHA, checks out `ref: ${{ needs.validate.outputs.sha }}` in both jobs, runs `git rev-parse HEAD`, compares it to the requested SHA, and verifies `git cat-file -e`. | LOCAL_OK |
| Required job names | `verify.yml`: `Validate requested SHA`, `Python 3.11 checks`, `Python 3.13 checks`, `Frontend tests (Node)`. `ci.yml`: `Tests & lint`, `Frontend tests (Node)`. | LOCAL_OK |
| Run lookup/pagination | R3 uses `GET /repos/{repo}/actions/runs?head_sha=<sha>`, `per_page=100`, at most 10 pages; jobs at most 10 pages of 100 (`bot/review/github.py:312-330`, `:434-526`). Overflow is an explicit pagination error, never silent truncation. | LOCAL_OK |
| Commit movement/stale SHA | Every run/job must carry the requested `head_sha`; a mismatch becomes `sha_mismatch`/`stale`, with no runs/jobs exposed (`bot/review/github.py:434-468`, `:490-526`). | LOCAL_OK |
| Required-check policy | There is no “latest per workflow/check” or required-check policy. All runs for the SHA are considered; an older failed run can conservatively cause `FAIL` (`R3` implementation report). | GAP (conservative, not false PASS) |
| Incomplete job evidence | `_validate_ci()` accepts zero job groups for a run and does not require a job group for every run. `ReviewEvidence.ci_state` is computed from workflow runs only (`bot/review/evidence.py:533-551`, `bot/review/github.py:735-744`). A successful run with missing/incomplete jobs can still reach `PASS`. | GAP |
| Permissions/token scope | Workflow permissions are `contents: read`. A manual `workflow_dispatch` is an API action requiring a caller with Actions write permission; that is outside the workflow’s own `GITHUB_TOKEN` scope. The review collector needs read-only `Contents` and `Actions` access. | UNVERIFIED_LIVE |
| Failure/cancellation semantics | `_ci_state`: pending → `pending`; failure/timed_out/action_required/startup_failure → `failure`; cancelled → `cancelled`; all success → `success`; skipped/neutral → `skipped`; otherwise `mixed`; empty → `missing`. R4 maps `failure` to `FAIL`; other non-success states to `BLOCKED`. | LOCAL_OK |
| Safest future controlled run | Push a canary commit to a dedicated repository branch and let `verify.yml` (or a minimal canary workflow) run on that exact SHA; do not dispatch against a protected branch and do not modify production branches. | DESIGNED |

### C. Reviewer provider

| Question | Finding | Status |
|---|---|---|
| Configured provider/model | No provider, model, base URL, or key is configured in `.env` or the environment. The repository ships neutral defaults only (`bot/config.py:46-55`, `.env.example:19-28`). | BLOCKED for live |
| Adapter compatibility | `DirectProviderAdapter` is OpenAI-chat-compatible: POST `<api_base>/chat/completions`, `stream=false`, `temperature=0`; no tools, no retries (`bot/review/llm.py:205-334`). | LOCAL_OK |
| Snapshot immutability | Provider snapshots are immutable via SQLite triggers; fingerprint covers provider/api_base/model/settings (`bot/db.py:1396-1420`). `ProviderBinding.from_config()` checks current config against the snapshot (`bot/review/llm.py:161-181`). | LOCAL_OK |
| Snapshot enforcement in R5 | `ReviewRunner.run()` only checks that the snapshot row exists; it accepts any `ReviewProvider` instance. It does not require `ProviderBinding.from_config()` or prove that the adapter matches the cycle snapshot. | GAP |
| Request limits | Default 256 KiB, maximum 2 MiB; oversized request fails closed. | LOCAL_OK |
| Response limits | Default 1 MiB, maximum 4 MiB; oversized response fails closed. | LOCAL_OK |
| Timeout | Default 20 s, maximum 120 s; connect/read/write/pool all bounded. | LOCAL_OK |
| Error classification | 401 → auth, 403 → forbidden, 429 → rate limit with `retry-after`/reset, 5xx → server, redirect → response error, transport → transport error, malformed/oversized → response error. No automatic retry for an ambiguous request. | LOCAL_OK |
| Rate-limit handling | `ProviderRateLimitError` carries safe headers; `execute_stage` returns `provider_error`; R5 treats it as retryable and applies bounded retry/backoff (`bot/review/llm.py:259-300`, `bot/review/worker.py:392-405`). | LOCAL_OK |
| Blind payload | System prompt, manifest, redacted diff, CI metadata (run/job names/status/conclusions), architecture decisions, review instructions. No OpenHands report/verdict, prior review, adversarial output, conversation history, PR body/comments, commit messages, or CI logs (`bot/review/prompts.py:139-180`). | LOCAL_OK |
| Adversarial payload | Adds the validated Blind result JSON and the OpenHands implementation report to the same diff/CI/architecture/instruction set (`bot/review/prompts.py:183-229`). | LOCAL_OK |
| Secret redaction | Pattern-based redaction for private keys, authorization headers, bearer tokens, connection credentials, GitHub/AWS/Slack/Stripe/Google/JWT/API-key patterns, generic assignments/query parameters. A re-scan failure blocks the payload. Path denylist excludes `docs/`, `*.patch`, `*.zip`, `package-lock.json`; binary files are excluded (`bot/review/redact.py:23-25`, `:72-195`). | LOCAL_OK |
| Residual false-negative risk | No entropy detector; arbitrary high-entropy secrets not matching a pattern can pass. Docs are excluded from review. Excluded/binary/truncated diffs fail closed in evidence/prompt paths, but the redactor itself is pattern-based. | RESIDUAL |
| Quota/cost information | R0E records NVIDIA catalog visibility (32 models, no deepseek), trial credits consumed by remote calls, and no reliable balance/usage API documented. No provider pricing or balance is stored locally. The proposed R0E attempt/billing ledger is not implemented in R2–R6. | UNVERIFIED |

### D. Telegram

| Question | Finding | Status |
|---|---|---|
| Owner authorization | `_review_owner_allowed()` checks `config.is_allowed(user_id)`, `owner_id`, private chat, `cycle.chat_id`, and the callback message chat; callback data is parsed, never trusted (`bot/handlers.py:1490-1530`). | LOCAL_OK |
| Private-chat restriction | Only `ChatType.PRIVATE` with owner/cycle chat is accepted. | LOCAL_OK |
| Summary + Markdown document | `_post_claimed_review()` sends `send_document` with `InputFile(report.content, filename)`, escaped summary caption, HTML parse mode, and review buttons (`bot/outbox.py:660-736`). | LOCAL_OK |
| Details/Accept/Reject | `review_actions_markup()` creates `review:{d|a|r}:{review_id}:{version}`; `parse_review_callback()` enforces full-match and ≤64 UTF-8 bytes (`bot/review/report.py:45-153`). | LOCAL_OK |
| OWNER_ACCEPTANCE persistence | `auto_review_owner_acceptance` is immutable, unique per decision key; ACCEPT/REJECT do not change verdict, findings, SHAs, or R5 stages (`bot/db.py:1645-1661`, callback tests). | LOCAL_OK |
| Outbox idempotency | One report per `(review_id, version)`; one outbox intent; CAS `claimed ⇒ sending` before Telegram; duplicate completion does not send twice (`bot/review/report.py:593-622`, `bot/outbox.py:660-736`). | LOCAL_OK |
| Ambiguous delivery | `TelegramError`/timeout after the sending boundary becomes `unknown`; no automatic retry; never marked `sent` (`bot/outbox.py:710-735`). | LOCAL_OK |
| Retry behavior | Pre-CAS failures may retry under the existing outbox policy; post-CAS ambiguity is terminal `unknown`. Review delivery does not use the generic prompt retry path. | LOCAL_OK |
| Duplicate callback | Same action returns the existing owner record; a different action conflicts without mutation. | LOCAL_OK |
| Telegram limits | Summary ≤1024 chars; report ≤180,000 chars and ≤300,000 UTF-8 bytes; document filename from the report rule. Real Telegram caption/file limits remain unverified live. | LOCAL_OK / UNVERIFIED_LIVE |

### E. Database and runtime

| Question | Finding | Status |
|---|---|---|
| Schema | 26 tables; R2/R5/R6 review tables and outbox review columns are present. Local temp DB count = 26. | LOCAL_OK |
| Migrations | `CREATE TABLE IF NOT EXISTS` for new tables; additive `ALTER TABLE` for outbox review columns; migration preserves existing rows (tested). No destructive migration. | LOCAL_OK |
| Worker startup | `bot/app.py` does not start `ReviewWorker`; `REVIEW_ENABLED` does not start it. This is the intended R5/R6 boundary. | INACTIVE |
| Lease/fencing | `claim_auto_review` uses lease token/epoch; `renew`/`complete` reject stale owners; expired leases are takeover-able (`bot/db.py:8395-8630`). | LOCAL_OK |
| Restart recovery | Stages/evidence/verdict persist; `delivery_pending` recovery is called before claim; report service `ensure_pending` recreates the report/outbox intent (`bot/review/worker.py:553-650`). | LOCAL_OK |
| Outbox delivery state | `pending/claimed/sending/sent/unknown/failed` mirrored to cycle; terminal states never claim `sent` without a confirmed send (`bot/db.py` triggers, `bot/outbox.py:660-736`). | LOCAL_OK |
| Runtime activation boundary | No production DB modification, no worker start, no runtime flag change was made. Phase B would need an isolated DB/process and explicit approval. | INACTIVE |

---

## 4. OpenHands live-test design (not executed)

### 4.1 Target and isolation

- Use a **dedicated disposable GitHub repository** (preferred) or an explicitly isolated test
  repository with protected `main`. Do not use `TM-AEM/OpenHandBot` or any production branch.
- Create branch `agent/r7-canary-known-defect` from a recorded base commit.
- Use one dedicated OpenHands conversation and one dedicated SQLite database outside production.
- Record `repository_id`, `repository_full_name`, `pr_number`, `branch`, `base_sha`, `head_sha`
  before any review cycle. Never infer the head from the branch name.

### 4.2 Supported creation mechanism

1. Create/push the canary branch and open a PR to the disposable repository's protected `main`.
2. Start a controlled OpenHands conversation with:
   - `initial_message`: a bounded task that only touches `canary/health.py` and
     `tests/test_canary_health.py`;
   - `selected_repository`: the disposable repository;
   - `selected_branch`: the canary branch.
3. Wait for `READY`; record the conversation ID and the exact head SHA produced by the task.
4. Verify the PR head SHA and CI run SHA from GitHub; do not accept a branch tip or merge SHA as
   the reviewed head.

### 4.3 Association limitation

`start_conversation()` does not send `pr_number`. R0E B-01 is unresolved: no verified example
shows the resolver populating a non-empty `pr_number` with matching PR/SHA/CI. Two future options:

- **Option A (preferred, strongest):** use a resolver-created conversation bound to the PR and
  prove non-empty `pr_number` + exact SHA + CI. This requires a supported resolver workflow and
  live evidence.
- **Option B (controlled harness, narrower):** manually supply the exact membership tuple to
  `reserve_conversation_review()` after verifying the PR/SHA. This tests R3–R6 end to end but does
  **not** validate conversation→PR discovery; the report must label B-01 unverified.

Do not silently choose Option B and claim full E2E. Phase B must state which option was approved.

### 4.4 Required credentials and permissions

- OpenHands API key able to create a conversation, send the task, and delete the test conversation.
- GitHub App installation/repository access plus a read-only review token (`Contents: Read`,
  `Actions: Read`, `Metadata: Read`); PR/branch creation requires a separate write authorization.
- Reviewer provider key/model/base URL and an owner-approved cost/credit exposure.
- Telegram bot token and owner private chat ID; bot able to send documents and receive callbacks.
- No production credentials or production database path.

### 4.5 Expected evidence

- Conversation ID, selected repository/branch, task ID/READY state.
- PR number, base SHA, exact head SHA, and GitHub compare result.
- Workflow run IDs/jobs all bound to the exact head SHA.
- Persisted `auto_reviews`, `auto_review_memberships`, `auto_review_evidence`, stages, verdict,
  report, outbox row, and owner decision (if exercised).

---

## 5. GitHub Actions live-test design (not executed)

### 5.1 Workflow choice

For the canary, use the existing `verify.yml` exact-SHA pattern in the disposable repository, or a
minimal canary workflow with the same security properties. Do not modify the production `ci.yml`.

### 5.2 Exact-SHA properties to exercise

- `head_sha` is a full 40-character lowercase hex SHA.
- Checkout uses the validated SHA, not `github.sha` for a PR merge commit and not a branch tip.
- `git rev-parse HEAD` equals the requested SHA.
- `git cat-file -e` confirms the commit exists.
- A stale/moved SHA is rejected rather than substituted.
- Workflow permissions remain read-only; no `continue-on-error` or `|| true`.
- The review collector sees every run/job for that SHA, and a mismatch is `stale`, not success.

### 5.3 Required job names and interpretation

- `verify.yml`: `Validate requested SHA`, `Python 3.11 checks`, `Python 3.13 checks`,
  `Frontend tests (Node)`.
- `ci.yml`: `Tests & lint`, `Frontend tests (Node)`.
- A completed `success` run is required for `PASS`; `failure` maps to `FAIL`; pending, cancelled,
  skipped, mixed, missing, and stale map to `BLOCKED`.
- **Gap:** the current collector does not require a job group for every run or require all jobs to
  be complete. Phase B must add/verify a job-completeness assertion before accepting `PASS`.

### 5.4 Safe future execution

1. Push the canary branch to the disposable repository; let the `agent/**` push trigger run
   `verify.yml`. This avoids dispatching against a protected branch.
2. If a manual dispatch is required, dispatch only against the disposable repository and the exact
   commit, with an Actions-write-capable token; record the request and run ID.
3. Read the failing step first; treat green CI as evidence only for the exact requested SHA.
4. Do not modify `main`, do not force-push, and do not reuse a prior run for a new SHA.

### 5.5 Permissions and failure/cancellation

- Workflow `GITHUB_TOKEN`: `contents: read` only.
- Manual dispatch: caller needs Actions write; not granted by this task.
- `failure`, `timed_out`, `action_required`, `startup_failure` → `failure`.
- `cancelled` → `cancelled`; `skipped`/`neutral` → `skipped`; queued/in-progress → `pending`;
  no run → `missing`; mixed conclusions → `mixed`.
- `failure` is the only state that produces `FAIL` from CI alone; the others produce `BLOCKED`
  (unless another deterministic rule applies).

---

## 6. Reviewer provider live-test design and cost uncertainty (not executed)

### 6.1 Configuration and binding

Required: `REVIEWER_PROVIDER`, `REVIEWER_API_BASE`, `REVIEWER_API_KEY`, `REVIEWER_MODEL`; all are
validated only when `REVIEW_ENABLED=1`. The live harness must construct a provider snapshot and a
`DirectProviderAdapter(ProviderBinding.from_config(config, snapshot))`; the R5 runner does not
enforce this binding today.

### 6.2 Limits and error behavior

- Timeout: 20 s default / 120 s maximum.
- Request: 256 KiB default / 2 MiB maximum; response: 1 MiB default / 4 MiB maximum.
- One schema correction is allowed after a valid provider response; no retry after an ambiguous
  request.
- 401/403/429/5xx/redirect/transport/malformed/oversized responses are classified; 429 carries
  safe retry metadata.
- `temperature=0`, `stream=false`; no `max_tokens` is set, so output-token cost is provider-default
  and not bounded by the adapter beyond the response byte cap.

### 6.3 Data transmitted

Blind: redacted diff, CI metadata (run/job names/status/conclusions, not logs), architecture
decisions, review instructions.

Adversarial: the same plus the validated Blind result and the OpenHands implementation report.
No PR body/comments, commit messages, conversation history, or raw CI logs.

### 6.4 Redaction and residual risk

Pattern-based redaction is deterministic and fail-closed on re-scan. It is not an entropy detector;
arbitrary secrets can pass. `docs/`, `*.patch`, `*.zip`, and `package-lock.json` are excluded;
binary files are excluded. The report must not claim that all secrets are guaranteed removed.

### 6.5 Cost/credit uncertainty

No local provider pricing, balance, quota, or usage API is documented. R0E records NVIDIA trial
credits consumed by remote calls and no reliable balance API. A hard monetary ceiling cannot be
guaranteed. Worst-case call count is material:

- up to 20 diff chunks per stage (`MAX_CHUNKS = 20`);
- up to one correction per chunk after invalid schema;
- Blind + Adversarial = up to 80 provider calls per PR per attempt;
- retries may repeat the cycle up to `max_attempts` (default 5);
- cycles may contain multiple PR memberships.

The owner must approve a maximum exposure and stop conditions before any inference. The adapter
does not implement the R0E attempt/billing ledger.

---

## 7. Telegram live-test design (not executed)

### 7.1 Owner and chat checks

Use the configured `owner_id` in a private chat. Verify `_review_owner_allowed()` rejects:

- a non-owner allowed Telegram user;
- a disallowed user;
- a forged callback payload;
- a callback whose message chat differs from `cycle.chat_id`;
- a callback for a missing report/version.

### 7.2 Delivery and callbacks

1. Prepare a completed R5 cycle with a persisted R6 report.
2. Confirm one outbox row with `review_kind=summary_document`, report ID/version, filename, summary.
3. Confirm `send_document` is called once with the exact report bytes, escaped caption, and
   Details/Accept/Reject buttons.
4. Press Details: the exact persisted version is sent again; no regeneration.
5. Press Accept/Reject: one durable `OWNER_ACCEPTANCE` row; technical verdict/findings/SHAs
   unchanged; duplicate press is idempotent; conflicting action is rejected.
6. Inject a Telegram transient error after the sending boundary: state must be `unknown`, never
   `sent`; no automatic resend.
7. Inject a duplicate completion/callback: no second send and no duplicate decision.

### 7.3 Limits and side effects

- Summary ≤1024 chars; report ≤180,000 chars / 300,000 bytes.
- Real Telegram caption/file limits and document rendering are **UNVERIFIED_LIVE**.
- Data leaving local: report summary/document and buttons to the owner’s private chat; report
  findings may include file paths, line numbers, code quotes, SHAs, and repository names.
- Cleanup: delete test messages if Telegram permits; otherwise record message IDs and do not reuse
  the chat for production.

---

## 8. Controlled canary design (prepared, not executed)

### 8.1 Disposable target layout

Use a dedicated repository (for example an owner-approved `*-r7-canary` repository), protected
`main`, and branch `agent/r7-canary-known-defect`.

Planned files:

```text
canary/health.py
tests/test_canary_health.py
```

Planned defect (Scenario 1):

```python
# canary/health.py
def add(a: int, b: int) -> int:
    return a - b  # R7 deliberate defect: line 2
```

```python
# tests/test_canary_health.py
from canary.health import add


def test_add_returns_sum():
    assert add(2, 3) == 5  # expected failure; actual -1
```

The defect is harmless, local to the disposable target, deterministic, and removable by a single
line change. The exact expected failing test is
`tests/test_canary_health.py::test_add_returns_sum` at line 4; the defect is
`canary/health.py:2`.

### 8.2 Scenario 1 — known defect

Expected sequence:

1. Controlled OpenHands task creates/updates the canary branch and PR with the defect.
2. GitHub Actions runs against the exact PR head SHA.
3. R3 collector retrieves the compare, workflow runs, and jobs for that SHA.
4. Blind receives only permitted evidence; Adversarial receives the validated Blind result and the
   OpenHands report.
5. Evidence validation rejects any stale/mismatched SHA.
6. Deterministic verdict: expected `FAIL` if the CI state is `failure` and SHA/diff evidence is
   verified (`R4-CI-01`). If SHA/coverage cannot be verified, expected `BLOCKED`, not a forced
   `FAIL`.
7. R6 report says `FAIL`/`BLOCKED` exactly; no fabricated PASS; summary and document bound to the
   report hash.
8. Outbox prepares one summary/document intent; no `sent` before Telegram confirmation.
9. Owner can inspect Details; Accept/Reject creates a separate record and does not alter the
   technical verdict.

Expected persisted state: one terminal cycle, one immutable membership snapshot, one evidence row
per PR, validated Blind/Adversarial stage rows (or terminal failure with a reason), one report, one
outbox intent/terminal delivery state, and no owner decision until the owner acts.

### 8.3 Scenario 2 — corrected defect

1. Change `canary/health.py:2` to `return a + b` in a new commit.
2. Record the new head SHA and open/update the PR.
3. Run CI against the exact new SHA; collect and validate the new evidence.
4. Reserve a new cycle for the same conversation with the new membership/head SHA.
5. Run Blind then Adversarial in order.
6. Produce the deterministic verdict from actual evidence.
7. Generate a report bound to the new evidence/SHA; filename must use the new head (single PR).
8. Assert the previous cycle/report/evidence were not reused: different review ID, head SHA,
   evidence SHA-256, stage evidence fingerprint, report ID/content/filename.

Do **not** assume the corrected result is `PASS`. It is `PASS` only if CI is `success` and there are
no valid findings; medium/low findings yield `PASS_WITH_NOTES`; high/critical or CI failure yields
`FAIL`; missing/invalid evidence yields `BLOCKED`.

### 8.4 Isolation and cleanup

- Use a separate repository and database; never production.
- Record the base SHA, branch, PR, head SHA, run IDs, and report/outbox IDs.
- Cleanup: close the PR, delete the canary branch, delete the OpenHands conversation/sandbox, and
  remove the isolated DB after evidence is captured. Deleting the disposable repository is a
  separate destructive action requiring explicit approval.

---

## 9. Failure-injection matrix

Legend: `LOCAL_TESTED` = existing deterministic local test; `LOCAL_GAP` = test design prepared but
not implemented/verified; `LIVE_REQUIRED` = requires explicit Phase B authorization.

| # | Case | Injection point | Expected persisted state | Expected verdict/blocked | Recovery | Required evidence | Verification |
|---|---|---|---|---|---|---|---|
| 1 | Duplicate OpenHands events | Repeat `reserve_conversation_review()` with same conversation/memberships/head | One cycle, one membership set, no duplicate outbox | Unchanged | Idempotent `ALREADY` | DB row counts; same review ID | LOCAL_TESTED (`test_invalid_and_duplicate_reservations_do_not_mutate`, `test_concurrent_reservation_has_one_winner`) |
| 2 | Duplicate GitHub events | Run collector/schedule twice for same SHA | One evidence row, one stage set, one outbox intent | Unchanged | Reuse evidence/stage; unique delivery key | Evidence fingerprint; outbox count | LOCAL_TESTED (`test_membership_and_evidence_snapshots_are_immutable`, `test_resume_after_blind_reuses_validated_stage`) |
| 3 | Delayed events | Observe a new PR while a cycle is active, then finish/reopen | New PR in `auto_review_pending_memberships`; active snapshot unchanged; later cycle includes it | Active verdict unchanged; later cycle independent | Pending row consumed on later reservation | Pending/membership rows; cycle IDs | LOCAL_TESTED (`test_new_pr_is_persisted_as_pending_not_mutating_active`, `test_pending_pr_is_consumed_by_later_cycle`) |
| 4 | Out-of-order events | Observe/reserve with memberships in different order | Canonical sorted membership snapshot; deterministic reservation key | Same | Idempotent | Key/membership ordering | LOCAL_TESTED (`test_reservation_key_is_deterministic_and_conversation_independent`) |
| 5 | Branch movement after discovery | Move branch after head discovery; call `verify_branch_sha`/compare | `moved` or SHA mismatch; no substitution of branch tip | `BLOCKED` if exact SHA/evidence cannot be verified | New cycle with new head; old cycle terminal | Branch verification/compare status | LOCAL_TESTED at GitHub client (`test_branch_movement_is_explicit`); R5 integration LOCAL_GAP |
| 6 | Stale SHA | Run/job/compare carries another SHA | `sha_mismatch`/`stale`; no files/jobs; no PASS | `BLOCKED` (R4-SHA-01) | Re-collect exact SHA; new cycle if head changed | Error class, SHA evidence | LOCAL_TESTED (`test_workflow_run_with_another_sha_is_stale`, `test_stale_or_unverified_sha_blocks_stage`, `test_stale_sha_blocks_even_when_ci_failed`) |
| 7 | Missing CI run | Empty `workflow_runs` | Verified run set with `ci_state=missing`; evidence recorded | `BLOCKED` (R4-CI-02) | Re-run CI or new exact-SHA run | Run lookup; report limitation | LOCAL_TESTED (`test_existing_run_is_not_success_when_pending_or_empty`, `test_ci_unavailable_blocks`) |
| 8 | Incomplete CI jobs | Successful run but empty/partial jobs or no group for a run | Current code accepts; run success can reach `PASS` | **GAP: should be `BLOCKED` until job completeness is proven** | Re-collect jobs; add completeness assertion | Run/job counts and expected names | LOCAL_GAP (no test; `_validate_ci` does not require job groups) |
| 9 | Failed CI | Run conclusion `failure` | CI state `failure`; verdict durable | `FAIL` (R4-CI-01) | No retry for deterministic failure; delivery | Run ID/conclusion | LOCAL_TESTED (`test_workflow_conclusions_are_not_treated_as_success`, `test_ci_failure_wins...`) |
| 10 | Cancelled CI | Run conclusion `cancelled` | CI state `cancelled` | `BLOCKED` (R4-CI-02) | Re-run/collect new evidence | Run ID/conclusion | LOCAL_TESTED (`test_ci_unavailable_blocks`) |
| 11 | Provider timeout | Transport timeout | `provider_error`, retryable; `retry_wait` then terminal after max | `BLOCKED` if exhausted | Bounded backoff; lease release | Error class/attempts | LOCAL_TESTED (`test_adapter_maps_timeout...`, `test_retryable_failure_is_bounded...`) |
| 12 | Provider rate limit | 429 with retry headers | `provider_error`, retryable; no false success | `BLOCKED` if exhausted | Bounded retry | Status/retry metadata | LOCAL_TESTED (`test_adapter_maps_provider_failures_without_retry`) |
| 13 | Malformed provider response | Invalid JSON/schema | `invalid_output`; one correction; no accepted stage | `BLOCKED` after failure | One correction then bounded retry | Error code/attempt | LOCAL_TESTED (`test_execute_stage_blocks_after_second_invalid_output`, `test_adapter_bounds...`) |
| 14 | Invalid Blind Review result | Schema/evidence validation failure | Blind stage `invalid`; no adversarial stage | `BLOCKED` | New cycle/retry after fix; no adversarial | Stage status/reason | LOCAL_TESTED (`test_invalid_blind_never_runs_adversarial`, `test_blind_evidence_failure_blocks_without_adversarial`) |
| 15 | Adversarial Review failure | Provider/schema/binding failure | Adversarial stage failure; no verdict from model | `BLOCKED` | Bounded retry/resume; no fallback to PASS | Stage error/binding | LOCAL_TESTED (`test_forged_adversarial_blind_binding_is_blocked`, engine/lifecycle tests) |
| 16 | Worker crash after reservation | Kill after claim/evidence/before completion | Lease remains; cycle active/queued; verdict not claimed | No verdict until recovery | Expiry takeover; stage resume | Lease/cycle/stage rows | LOCAL_TESTED (`test_resume_after_evidence...`, `test_verdict_is_durable...`) |
| 17 | Worker lease expiration | Advance clock beyond lease | New worker claims; epoch increments | Old worker cannot complete | Takeover; stale token rejected | Lease epoch/token | LOCAL_TESTED (`test_lease_takeover_fences_stale_worker`, `test_renew_lease_extends_only_for_current_owner`) |
| 18 | Stale worker completion | Old token/epoch after takeover | `AutoReviewLeaseLost`; no overwrite | No false completion | Discard old worker; new worker owns | Lease error; cycle state | LOCAL_TESTED (`test_lease_takeover...`) |
| 19 | Database lock/write failure | Hold `BEGIN IMMEDIATE` or inject SQLite error | No partial success; transaction rollback; cycle remains recoverable | `BLOCKED`/retry, never PASS | Retry after lock clears; lease expiry | DB error class; row state | LOCAL_GAP (only callback DB failure tested; add lock/write-failure test) |
| 20 | Report generation failure | Make `save_auto_review_report`/build raise | Verdict durable; cycle `delivery_pending`; no outbox row | Technical verdict unchanged; delivery not claimed | `ensure_pending` retries; no false sent | Cycle state; outbox absence | LOCAL_GAP (missing-report test exists; add build/save failure test) |
| 21 | Outbox insertion failure | Make `schedule_auto_review_report_delivery` raise | Report may exist; no outbox; cycle `delivery_pending` | No delivery/PASS claim | Recovery creates outbox later | Outbox count; cycle state | LOCAL_GAP (add test) |
| 22 | Telegram retryable failure | `TelegramError` before/at send | `unknown` after sending boundary; no `sent` | No verdict change; delivery unknown | Manual reconciliation; no auto-retry | Outbox/cycle delivery state | LOCAL_TESTED (`test_delivery_failure_is_never_marked_sent`) |
| 23 | Ambiguous Telegram delivery | Timeout/cancel after `sending` | `unknown`; no automatic resend | No false success | Manual reconciliation | Message/outbox state | LOCAL_TESTED (`test_delivery_failure_is_never_marked_sent`, `test_terminal_outbox_unknown...`) |
| 24 | Duplicate Telegram callback | Send same callback twice | One `OWNER_ACCEPTANCE`; no second mutation | Technical verdict unchanged | Idempotent response | Acceptance row count | LOCAL_TESTED (`test_duplicate_and_conflicting_decisions_are_stable`) |
| 25 | Unauthorized Details/Accept/Reject | Non-owner/allowed/forged/cross-chat callback | No mutation; no content; no report sent | Unchanged | Reject and audit | Handler response; DB counts | LOCAL_TESTED (`test_allowed_non_owner_and_disallowed_users_mutate_nothing`, `test_forged_and_cross_conversation_callbacks_are_rejected`, `test_details_requires_owner...`) |

### 9.1 Required local tests before Phase B

The following are **not** implemented as executable tests yet and must be added before a live canary:

1. Incomplete CI jobs must be `BLOCKED`, with a test proving no `PASS` when job groups are missing
   or incomplete.
2. A database-lock/write-failure test proving no false success and recoverable state.
3. A report-build/save failure test proving `delivery_pending` + no outbox + later recovery.
4. An outbox-insertion failure test proving no false delivery and later recovery.
5. A branch-movement integration test proving R5 does not silently review a moved tip.

---

## 10. Local verification results

All commands were local; no remote CI, provider, GitHub, OpenHands, or Telegram call was made.

| Command | Result |
|---|---|
| Focused R1–R6 suite: `pytest -q tests/test_verify_workflow_security.py tests/test_review_config.py tests/test_auto_reviews_db.py tests/test_review_github.py tests/test_review_redact.py tests/test_review_schema.py tests/test_review_prompts.py tests/test_review_llm.py tests/test_review_evidence.py tests/test_review_verdict.py tests/test_review_engine.py tests/test_auto_review_lifecycle.py tests/test_review_collector.py tests/test_review_report.py tests/test_review_delivery.py tests/test_review_callback.py tests/test_review_worker_integration.py` | **358 passed**, 0 failed, 9.69 s |
| Full Python: `python -m pytest -q` | **4182 passed**, 0 failed, 74 warnings, 326.29 s |
| Node: `node --test tests/frontend/*.test.js` | **280 pass**, 0 fail |
| `python -m pyflakes bot/ automation/ tools/ main.py tests/` | **0** findings |
| `python -m compileall -q bot/ automation/ tools/ main.py tests/` | **0** errors |
| `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | **0 High** (7 Low / 20 Medium) |
| `python -m pip_audit -r requirements-dev.txt` | **No known vulnerabilities found** |
| `git diff --check` | **clean** |

Warnings are the pre-existing PTB/Starlette deprecations (74). Python 3.11 was not available
locally; CI matrix coverage is the only 3.11 verification path.

Schema check: a fresh local database creates **26 tables**, including 9 `auto_review_*` tables.

---

## 11. Data-egress and privacy analysis

| Destination | Data that would leave | Controls | Residual risk |
|---|---|---|---|
| OpenHands | Task text and selected repository contents; sandbox execution | Dedicated disposable repo/conversation; no production credentials | OpenHands sees repository content; cleanup must delete conversation/sandbox |
| GitHub (review collector) | Read-only compare/runs/jobs GETs; token in header | Allowlist; exact SHA; no token in URL/repr; no redirects | GitHub sees repository identity and token; no writes in review path |
| Reviewer provider | Redacted diff, CI metadata, architecture decisions, review instructions; Adversarial adds Blind JSON + OpenHands report | Path denylist, binary exclusion, pattern redaction, size bounds, fail-closed | Pattern false negatives; no entropy detector; docs excluded; provider sees code/report |
| Telegram | Summary caption, report document, buttons; findings may include code quotes/paths/SHAs | Owner-only private chat; escaped HTML; exact persisted report; no secret scan failure | Owner chat is external; report may contain sensitive code; ambiguous delivery possible |
| Local SQLite | Cycle/membership/evidence metadata, stage outputs, report content; no raw diff/API keys | Secret scans; no credentials persisted; bounded fields | Report/stage content can include code quotes; DB path must be isolated |
| Logs | IDs, statuses, error classes | No tokens/prompts/raw bodies; safe error classes | Operator must avoid debug logging payloads |

No secret value was printed or written in this report. The review collector never sends the GitHub
token in a URL and never follows redirects.

---

## 12. Exact Phase B operations requiring explicit authorization

**None of these operations were executed.** Authorization is required separately for each category;
this readiness task does not imply approval.

### 12.1 OpenHands task creation/execution

- External service: OpenHands.
- Action: `POST /app-conversations` with the canary task, selected repository/branch; poll start
  task; send messages; optionally delete the conversation.
- Target: dedicated canary conversation; disposable repository/branch only.
- Permissions: conversation create/send/delete; repository installation access.
- Data leaving: task text and repository content to the OpenHands sandbox.
- Cost: OpenHands credits/subscription; amount unknown.
- Side effects: sandbox/agent execution; branch/PR changes by the task.
- Cleanup: delete conversation/sandbox; close PR; delete branch; isolated DB removal.
- Verification: conversation ID, READY, exact PR/head SHA, CI run binding.

### 12.2 GitHub branch/PR/Actions operations

- External service: GitHub.
- Action: create/push canary branch, open/update PR, optionally dispatch `verify.yml`.
- Target: disposable repository only; protected `main` untouched.
- Permissions: repository write/PR write; Actions dispatch requires Actions write; review collector
  needs Contents/Actions read.
- Data leaving: canary source/test files and commit metadata.
- Cost: GitHub Actions minutes; amount unknown.
- Side effects: branch/PR/run creation; possible notifications.
- Cleanup: close PR, delete branch, delete repository only with separate destructive approval.
- Verification: exact head SHA, run IDs/job names, checkout SHA equality, no stale substitution.

### 12.3 Reviewer provider inference and data transmission

- External service: configured reviewer provider.
- Action: POST `/chat/completions` for Blind and Adversarial (and at most one correction per stage).
- Target: canary evidence only; provider/model fixed by immutable snapshot.
- Permissions: provider API key with inference entitlement; no assumption from model catalog.
- Data leaving: redacted diff, CI metadata, architecture decisions, review instructions; Adversarial
  also Blind result and OpenHands report.
- Cost: unknown; trial credits may be consumed; no reliable balance API; hard ceiling not guaranteed.
- Side effects: provider logs/retention; possible rate limits.
- Cleanup: no provider-side delete guarantee; record request IDs/usage.
- Verification: response schema, usage fields if present, no secret in payload, stage binding.

### 12.4 Telegram message delivery

- External service: Telegram Bot API.
- Action: `send_document` with summary caption and Details/Accept/Reject buttons; owner callback.
- Target: owner private chat only; no groups.
- Permissions: bot token; owner ID; bot can send documents.
- Data leaving: report summary/document and buttons to the owner.
- Cost: none expected.
- Side effects: messages in owner chat; callbacks.
- Cleanup: delete test messages if permitted; record message IDs.
- Verification: document bytes/filename, caption, buttons, callback authorization, owner decision
  row, no false `sent`.

### 12.5 Runtime worker activation

- External service: local process (with provider/GitHub/Telegram effects).
- Action: construct/start `ReviewWorker` + `ReviewRunner` with isolated DB and explicit clients.
- Target: isolated canary DB; no production DB; no production bot process.
- Permissions: local process; review credentials as above.
- Data leaving: as provider/GitHub/Telegram categories.
- Cost: provider/OpenHands/Actions costs.
- Side effects: claims cycles, writes DB, sends Telegram, consumes provider credits.
- Cleanup: stop worker; preserve/export DB; delete isolated DB after evidence.
- Verification: cycle state transitions, lease/fencing, report/outbox, no duplicate delivery.

---

## 13. Remaining blockers and findings

| ID | Severity | Finding | Effect on R7 | Required action |
|---|---|---|---|---|
| R7-B01 | BLOCKER | Conversation → PR → exact SHA association is unresolved; no supported bot mapping; R0E B-01 unverified. | Cannot prove complete live E2E from an OpenHands conversation. | Approve resolver evidence or an explicit controlled membership harness; label scope honestly. |
| R7-B02 | BLOCKER (authorization) | Review worker is not started by `bot/app.py`; `REVIEW_ENABLED` is config-only. | No live cycle can start without a new authorized entrypoint. | Explicit Phase B runtime activation approval and isolated harness. |
| R7-B03 | BLOCKER (external) | No provider/model/key/base URL, no disposable repo/branch, no Telegram test target. | Phase B cannot run. | Owner supplies/authorizes resources without exposing secrets. |
| R7-F01 | MEDIUM | Successful CI run with incomplete/missing job evidence can still reach `PASS`. | Potential false confidence in CI evidence. | Require job completeness for each run; add test. |
| R7-F02 | MEDIUM | R5 runner does not enforce `ProviderBinding`/snapshot match; it accepts any provider. | A live harness could review with the wrong model under a snapshot ID. | Enforce binding in runner/harness and test mismatch rejection. |
| R7-F03 | LOW | R5 collector does not call `verify_branch_sha`; branch movement is only caught by exact SHA/compare. | Exact SHA protects the reviewed commit, but branch-movement semantics are not explicit. | Add integration assertion/test or document exact-SHA-only policy. |
| R7-F04 | LOW | No required-check/latest-per-workflow policy; older failed runs can make a conservative `FAIL`. | Can over-block, not false PASS. | Accept as conservative or add required-check policy. |
| R7-F05 | LOW | `docs/OPERATIONS_RUNBOOK.md` still labels `REVIEW_ENABLED` as R2-only in the env table. | Operator confusion. | Update runbook wording in a later approved doc change. |
| R7-F06 | INFO | R1–R6 work is uncommitted; no independent review; R0F remains blocked. | Publication/review status unchanged. | Do not commit/push until explicitly authorized; independent review remains deferred. |

---

## 14. Explicit statements

- **No live operations were performed.** No OpenHands conversation/task, GitHub branch/PR/Actions
  dispatch, provider inference, Telegram message, or review worker activation occurred.
- **The R5 review worker remains inactive.** `bot/app.py` starts only the existing outbox/creation/
  completion/watcher/notifier workers; no `ReviewWorker` is constructed.
- **No publication occurred.** No commit, push, PR/MR, merge, deployment, or release was made.
- **Independent review remains deferred.** This is an author readiness report, not an independent
  review and not a `PASS`.
- **R8 has not started.**
- **Phase B is not authorized by this task.** Stop here and request explicit approval for each
  Phase B category.

---

## 15. Suggested next step

Resolve R7-B01 and R7-F01 first: obtain an owner decision on the conversation→PR association
mechanism (resolver evidence vs. explicit controlled harness), and add a job-completeness assertion
test that prevents `PASS` on incomplete CI job evidence. Then request the five Phase B
authorizations separately.
