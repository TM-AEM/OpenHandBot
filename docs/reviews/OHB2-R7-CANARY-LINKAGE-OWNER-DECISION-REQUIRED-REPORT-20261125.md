# OHB2-R7 — Canary Linkage Implementation Report (2026-11-25)

**Task ID:** `OHB2-R7-CANARY-LINKAGE-IMPLEMENTATION-AND-LOCAL-VERIFICATION`
**Verdict:** `R7_CANARY_LINKAGE_OWNER_DECISION_REQUIRED`

**Scope:** local audit, implementation-ready design, test plan, and existing-test
verification only. No implementation was authorized.

No OpenHands API call, GitHub API call/write, workflow dispatch, provider inference,
external data transmission, Telegram message, review-worker activation, production
database access, migration, real PR change, commit, push, PR, merge, deployment, or
release was performed.

Independent review remains deferred. R7 live validation and R8 have not started.

---

## 1. Baseline Git state

Recorded before any report was written:

| Item | Value |
|---|---|
| Repository | `/workspace/project/OpenHandBot` |
| Branch | `agent/r6-review-delivery` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `origin/main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| HEAD tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| Tracked files | 569 |
| Modified tracked | 12 |
| Untracked entries | 53 |
| Python | 3.13.15 in `.venv` |
| pytest | 9.0.3 |
| Node | 24.22.2 |

The working tree already contained the R1–R7 implementation, the resolver, the review
tests, and historical reports. They were preserved. No destructive Git operation was
used. `main` and `origin/main` both point to the baseline SHA; canonical GitHub `main`
was not re-queried because live GitHub access is forbidden.

### Final state for this task

- Added three reports under `docs/reviews/`.
- Appended `.agent/PROGRESS.md`.
- No code, schema, migration, table, index, trigger, resolver, test, or configuration
  file was changed.
- No commit/push/PR/merge/deploy/release.

---

## 2. Owner-decision gate

### 2.1 Search performed

Searched the repository for an explicit later approval:

- `docs/reviews/OHB2-R7-B01-OWNER-DECISIONS-20261125.md`
- `docs/reviews/OHB2-R7-B01-OWNER-DECISION-ANALYSIS-20261125.md`
- `.agent/PROGRESS.md`
- all `docs/` decision/review/proposal files
- `git log --oneline -5`

### 2.2 Result

**No explicit D-01/D-02 owner decision was found.**

Evidence:

- The owner-decision document still presents the approval template and ends with:
  "Until these are recorded, the automatic conversation→PR→SHA relationship is
  `R7_B01_OWNER_DECISION_REQUIRED`."
- The decision analysis classifies D-01 and D-02 as `OWNER_DECISION_REQUIRED`.
- `.agent/PROGRESS.md` records both as `OWNER_DECISION_REQUIRED`.
- Before this request, no record contained `D-01: B`, `D-02: explicit-list`, or an
  equivalent explicit selection. The new owner-decision request contains only an
  unselected example and states that no option is selected.
- The latest commit is `0107967` ("docs: add batch independent review reports and
  summary"); it is not an owner decision for D-01/D-02.

### 2.3 Gate decision

Because no explicit approval exists:

- **D-01 was not implemented.**
- **D-02 was not implemented.**
- `bot/review/resolver.py` was not modified.
- No schema, migration, table, index, or trigger was modified.
- No `CanaryLinkageService` or source adapter was created.
- The work product is an implementation-ready design and focused test plan.

This is the correct stop point under the task's owner-decision gate.

---

## 3. Code and test areas inspected

### 3.1 Resolver

`bot/review/resolver.py`:

- `ConversationRepositoryLink` and `ConversationRepositoryLinkSource` at `:88-105`.
- `ConversationMembershipResolver.resolve()` at `:152`:
  - validates conversation/chat/PR list;
  - authorizes through `watched` and `is_deleted`;
  - loads an injected link;
  - verifies GitHub repository ID/full name;
  - loads each explicit PR;
  - validates base/head repository identity, fork, open/merged state, SHA shape;
  - verifies branch SHA before and after reads;
  - derives/validates merge-base;
  - returns immutable `AutoReviewMembership` plus provenance.
- `reserve_resolved_memberships()` at `:378` validates provenance and calls
  `Database.reserve_conversation_review()` atomically.
- `_validate_request()` at `:454` requires non-empty unique positive PR integers.

The resolver already provides D-02's safe verifier. It does **not** choose D-01's
source or discover PRs.

### 3.2 Creation jobs and conversation association

`bot/db.py`:

- `CreationJob` at `:758-771`: `id`, `chat_id`, `repo`, `status`, `task_id`,
  `conversation_id`, timestamps, `client_ref`, `notify_state`.
- `creation_jobs` schema at `:1200-1215`: `repo` and `conversation_id` are nullable
  text columns; no repository ID, source, or verification timestamp.
- `add_creation_job()` at `:5525`: persists `chat_id`, `repo`, text before the OpenHands
  POST; idempotency is `client_ref`; no `conversation_id` yet.
- `finish_creation_done()` at `:5813-5830`: CAS `claimed/starting -> done` with
  `conversation_id`.
- `bot/outbox.py:1162-1303`: creation worker passes `job.repo` to
  `start_conversation`, then writes the resulting `conversation_id`.
- `bot/handlers.py:3654-3720`, `:3750`: Telegram repository picker and creation-job
  creation.
- `bot/web/services.py:1401-1445`: Mini App repository listing and creation-job
  creation.

The only local durable conversation→repository record is the `creation_jobs` row
(`repo` + `conversation_id`). It exists only for conversations created through this
bot. It is owner-scoped by `chat_id`, but `repo` is a user-supplied name, not a GitHub
identity.

### 3.3 GitHub repository and PR primitives

`bot/review/github.py`:

- `RepositoryIdentity` at `:114-122`.
- `PullRequestIdentity` at `:126-142`.
- `list_agent_branches()` at `:368-390`: branches only; not PR discovery.
- `verify_branch_sha()` at `:392-408`: exact SHA status.
- `get_repository()` at `:410-415`: immutable numeric ID and full name.
- `get_pull_request()` at `:417-424`: explicit PR number only.
- `compare()` at `:427-485`: exact base/head and merge-base.
- `get_workflow_runs_for_sha()` at `:488` and `list_run_jobs()` at `:544`.
- No PR list/search or commit→PR discovery method exists.

### 3.4 Membership, reservation, and collector

- `AutoReviewMembership` at `bot/db.py:898-906`: repository ID, full name, PR,
  branch, base SHA, head SHA.
- `_valid_review_membership()` at `:318-329`: positive repo/PR, valid repo name,
  valid SHA40, non-empty branch.
- `_ordered_memberships()` at `:340-360`: deterministic sort and duplicate rejection.
- `reserve_conversation_review()` at `:8110-8330`: one conversation-wide active cycle,
  atomic membership insert, pending membership handling, conflict detection.
- `get_auto_review_memberships()` at `:7882`.
- `GitHubEvidenceCollector.collect()` at `bot/review/collector.py:40-105`: consumes a
  supplied membership; verifies branch before/after; compare/runs/jobs exact SHA;
  `jobs_complete()` at `bot/review/ci_contract.py:58`.
- `ReviewRunner.run()` at `bot/review/worker.py:122-136`: reads persisted memberships;
  no discovery.

### 3.5 Tests and runbook

- `tests/test_review_resolver.py` — 32 tests.
- `tests/test_auto_reviews_db.py` — 23.
- `tests/test_auto_review_lifecycle.py` — 30.
- `tests/test_review_branch_sha.py` — 8 (F-03).
- `tests/test_review_ci_jobs.py` — 15 (F-01).
- `tests/test_review_provider_binding.py` — 11 (F-02).
- `tests/test_review_recovery_failures.py` — 6 (DB/report/outbox/branch).
- `tests/test_review_collector.py` — 3.
- `tests/test_review_report.py` — 11.
- `tests/test_review_delivery.py` — 8.
- `tests/test_review_worker_integration.py` — 1.
- Runbook `docs/OPERATIONS_RUNBOOK.md` §11 documents the resolver as verifier-only,
  inactive, and not live-validated.

---

## 4. D-01 — implementation-ready design (not implemented)

### 4.1 Proposed bounded source

Create, only in a future authorized task, a new module
`bot/review/canary_linkage.py` with:

```python
class CreationJobRepositoryLinkSource:
    def __init__(self, db, openhands, github, owner_id): ...
    async def resolve(self, conversation_id: str) -> ConversationRepositoryLink | None: ...
```

It implements the existing `ConversationRepositoryLinkSource` protocol. It does not
change the resolver. It is constructed only by an explicit canary entrypoint; it must
not be wired into `bot/app.py`.

### 4.2 Resolution flow

1. Validate `conversation_id` syntax locally (same strict shape as the resolver).
2. Query local creation jobs:
   - add a read-only `Database` method:
     `list_done_creation_jobs_for_conversation(conversation_id)`;
   - SQL shape: `SELECT * FROM creation_jobs WHERE conversation_id=? AND status='done'
     ORDER BY id`;
   - no schema change; existing columns are enough.
3. Require **exactly one** row:
   - zero rows -> `None` (not bot-created / no trusted association);
   - more than one row -> `None` (ambiguous); do not choose the latest;
   - row `repo` missing/blank -> `None`;
   - row `chat_id` != configured `owner_id` -> `None`;
   - row status must be `done` (the query already enforces it).
4. Normalize `repo` strictly:
   - exactly `owner/repo` with the existing `_REPO_RE` shape;
   - no spaces/control characters, no `.`/`..` components, no extra slash;
   - preserve the case for display but compare case-insensitively.
5. Read OpenHands metadata:
   - `await openhands.get_conversations([conversation_id])`;
   - require exactly one dict and its `id` matches;
   - require `selected_repository` to be a non-empty string;
   - compare `selected_repository.casefold()` with the local `repo.casefold()`;
   - mismatch or missing -> `None`; do not fall back to OpenHands alone.
6. Verify GitHub:
   - `identity = await github.get_repository(repo)`;
   - require `identity.repository_id > 0`;
   - require `identity.full_name.casefold() == repo.casefold()`;
   - any name mismatch is a rename/ambiguous rejection, even if an ID is returned;
   - `get_repository` already enforces the review allowlist.
7. Return:

```python
ConversationRepositoryLink(
    conversation_id=conversation_id,
    repository_id=identity.repository_id,
    repository_full_name=identity.full_name,
    source="canary_creation_job",
)
```

The resolver then re-verifies the repository ID/full name through GitHub. This
double-read is intentional defense-in-depth; it is read-only and produces no side effect.

### 4.3 Failure behavior

- Missing/duplicate/conflicting/malformed/ambiguous local association -> `None`
  (the resolver maps to `missing_conversation_repository_link`); no fallback.
- DB read failure -> raise; resolver maps to `conversation_link_unavailable`
  (retryable).
- OpenHands/GitHub transport/rate/server errors -> raise; resolver maps to
  `conversation_link_unavailable` or `github_unavailable` as applicable.
- Repository not found/allowlist rejection -> resolver maps to
  `repository_not_found` / `repository_not_allowed`.
- `selected_repository` mismatch -> `None`; no fallback.
- GitHub full-name mismatch -> `None` / resolver `repository_rename_ambiguous`.
- No use of `watched.chat_id`, `created_by_user_id`, message fields, or historical
  `auto_reviews` as repository authority.

### 4.4 Identity-continuity limitation

The current `creation_jobs` schema does not store the GitHub numeric ID observed at
creation. Therefore:

- a rename or 404 is rejected by name mismatch/not-found;
- a deleted-and-recreated repository with the **same name** cannot be distinguished
  from the original because there is no stored prior ID;
- the source must not claim identity continuity in that case.

This is a bounded canary limitation. It does not close D-01 as an authority. Durable
`repository_id` capture would require an additive schema migration, which is not
authorized.

### 4.5 D-01 test plan

| Case | Expected |
|---|---|
| One done job, matching OpenHands repo, matching GitHub full name | accepted; membership uses GitHub numeric ID |
| No creation job | `missing_conversation_repository_link` |
| Two done jobs for same conversation | rejected; no insert |
| Job not `done` (pending/unknown/failed) | rejected |
| `repo` null/blank/malformed/extra slash/dot components | rejected |
| `chat_id` not owner | rejected |
| GitHub repository ID mismatch (mocked) | `repository_id_mismatch` |
| GitHub name mismatch (rename) | `repository_rename_ambiguous` |
| OpenHands `selected_repository` mismatch | rejected |
| OpenHands `selected_repository` missing | rejected |
| Conversation not created by this bot | rejected |
| DB read failure | `conversation_link_unavailable` |
| Duplicate/conflicting creation jobs | rejected; no partial insert |
| Same-name delete/recreate | documented as unprovable; rejected only if name/ID mismatch; otherwise canary risk remains |

No test file was created because implementation is not authorized.

---

## 5. D-02 — implementation-ready design (not implemented)

### 5.1 Proposed owner-input adapter

Add, only in a future authorized task, a `CanaryLinkageService` (or equivalent)
that requires:

- `owner_id` from the existing `Config.owner_id`;
- `db`, `openhands`, `github`, and the existing `ConversationMembershipResolver`;
- an explicit `pr_numbers` argument from the owner/harness.

It does **not** read OpenHands `pr_number`, prompt text, PR URLs, branch names, or any
GitHub discovery endpoint.

### 5.2 Input validation

- `pr_numbers` must be a `list` or `tuple`, not a string/generator/dict.
- Non-empty.
- At most `MAX_CANARY_PR_CANDIDATES` (proposed default: 20) to bound cost.
- Every item must be an exact `int`, not `bool`, not `str`, not `float`, not `None`.
- Every item must be `> 0`.
- No duplicates.
- `chat_id` must equal `owner_id` and must match the existing `watched.chat_id`
  authorization; no other chat may invoke it.
- Missing/empty/duplicate/malformed/over-limit -> `MembershipResolutionError`
  `INVALID_RESOLUTION_REQUEST` or `DUPLICATE_PR_MEMBERSHIP`; no provider/collector call.

### 5.3 PR verification

Use the existing resolver unchanged:

1. verify repository numeric ID/full name;
2. `get_pull_request(repository.full_name, number)` for every explicit number;
3. reject PR number mismatch, wrong repository, base/head repository mismatch, fork,
   closed/merged, malformed ref/SHA;
4. require exact head SHA and branch;
5. verify branch before/after; reject movement;
6. compare/merge-base exact;
7. return sorted immutable memberships; never choose the first PR.

Closed/inaccessible policy:

- `PR_NOT_FOUND` / `GITHUB_UNAUTHORIZED` / `GITHUB_UNAVAILABLE` -> fail closed;
- `PR_NOT_OPEN` (closed or merged) -> fail closed;
- `PR_FORK_AMBIGUOUS` / `PR_REPOSITORY_MISMATCH` -> fail closed;
- no retry for semantic rejection; retry only for transport/rate/server errors.

### 5.4 Exact SHA and evidence reuse

- Every accepted PR gets `base_sha`/`head_sha` from GitHub and an immutable
  `AutoReviewMembership`.
- The resolver re-reads the PR and branch after all reads; movement rejects.
- The R5 collector re-verifies the branch before/after; compare/runs/jobs must carry
  the exact head SHA; `jobs_complete()` must be true for PASS.
- A new SHA is a new membership/cycle; old evidence is never reused.
- No previous `auto_reviews` row is used as a candidate source.

### 5.5 D-02 test plan

| Case | Expected |
|---|---|
| One explicit positive PR | accepted; exact membership |
| Two explicit positive PRs | both accepted; sorted deterministically |
| Empty list | `invalid_resolution_request` |
| Duplicate numbers | `duplicate_pr_membership` |
| `bool`/`str`/`float`/`None`/zero/negative | `invalid_resolution_request` |
| Over max entries | `invalid_resolution_request` (or approved dedicated code) |
| Unauthorized chat/owner mismatch | `unauthorized_conversation` before GitHub |
| PR from another repo | `pr_repository_mismatch` |
| Fork PR | `pr_fork_ambiguous` |
| Closed/merged PR | `pr_not_open` |
| Missing/malformed head SHA | `malformed_external_response` / `invalid_resolution_request` |
| Branch moved before/after | `branch_moved` |
| PR head changed | `pr_head_moved` |
| Stale workflow run / wrong SHA | `ci_sha_mismatch` / blocked evidence |
| Incomplete CI jobs | `ci_jobs_complete=False`; verdict `BLOCKED` |
| Restart/retry | idempotent; same memberships or no partial insert |
| New PR after active cycle | pending; active snapshot immutable |
| Previous evidence for old SHA | rejected/not reused |

No test file was created because implementation is not authorized.

---

## 6. Provenance and lifecycle implications

### 6.1 No schema change authorized

Current state:

- `creation_jobs` has `repo` + `conversation_id`, no numeric repository ID/source/
  verification timestamp.
- `auto_reviews` and `auto_review_memberships` store repository/PR/SHA after explicit
  reservation; no source/verified_at columns.
- `auto_review_pending_memberships` stores `observed_at`; no source.
- The resolver's `MembershipProvenance` is in-memory only.

Therefore the design uses existing tables only. Durable provenance/stable repository
identity remains an additive-migration decision (D-04), not authorized here.

### 6.2 If durable provenance is later approved

Minimum fields:

- `conversation_id`, `chat_id` (authorization context, not repository identity);
- `repository_id`, `repository_full_name` (display snapshot);
- `source` (`canary_creation_job` / `explicit_owner_pr_list`);
- `observed_at`, `verified_at`;
- `pr_number`, `head_ref`, `base_sha`, `head_sha`;
- `verification_result`/safe reason code;
- `review_id`/membership link.

Rules:

- active membership rows stay immutable (existing no-update/no-delete triggers);
- new PR stays in pending membership, never mutates an active cycle;
- conflicting repository/PR/SHA rejects; stale observation is re-verified;
- no secrets/tokens/raw API bodies in provenance or logs.

### 6.3 Conversation-wide scope preserved

- `scope='conversation'`, `scope_policy='conversation-wide'`.
- One active cycle per conversation via `ux_auto_reviews_active_conversation`.
- Multiple explicitly supplied PRs are members of one cycle.
- No new concurrency model, no per-PR active cycle.

---

## 7. Security analysis

| Risk | Required fail-closed behavior | Existing support |
|---|---|---|
| Forged local creation job | Require `done`, exact `conversation_id`, owner `chat_id`, one row only | design |
| Malformed repo name | Strict `owner/repo` validation; reject dots/extra slash/control chars | resolver `_REPO_RE`; design |
| Repository rename/recreate | Name mismatch/404 rejects; same-name recreate unprovable without stored ID | design; limitation |
| OpenHands metadata spoofing | `selected_repository` is a check only; never authority | design |
| Forged PR numbers | Explicit owner list only; GitHub PR fetch and repo binding | resolver |
| Cross-repo/fork PR | Base/head IDs must equal verified repo; fork rejected | resolver |
| Closed/merged/inaccessible PR | Fail closed; no retry for semantic rejection | resolver |
| PR head movement | Re-read PR and branch before/after; reject | resolver/collector |
| Branch movement | Verify exact SHA; reject moved/missing/blocked | F-03 |
| Stale evidence | Exact SHA compare/runs/jobs; no reuse | F-01/F-03 |
| Incomplete CI | `jobs_complete` required for PASS | F-01 |
| Duplicate/conflicting candidates | Reject duplicates; DB conflict; pending, not mutation | resolver/DB |
| Unauthorized caller | `chat_id == owner_id` + `watched.chat_id` | design/resolver |
| Partial GitHub response | Strict parsers; pagination error; no empty success | GitHub client |
| DB read/write failure | No insert/acknowledgement; retry/recovery | R7 recovery tests |

---

## 8. Existing R7 remediation status (verified, not assumed)

| Finding | Current status | Evidence |
|---|---|---|
| F-01 CI job completeness | **FIXED_AND_TESTED** | `bot/review/ci_contract.py:58`; `bot/review/verdict.py:143`; `tests/test_review_ci_jobs.py` 15 pass |
| F-02 ProviderBinding | **FIXED_AND_TESTED** | `bot/review/worker.py:122-180`; `tests/test_review_provider_binding.py` 11 pass |
| F-03 branch/SHA | **FIXED_AND_TESTED** | `bot/review/collector.py:40-105`; `tests/test_review_branch_sha.py` 8 pass |
| DB lock/write failure | **TESTED** | `tests/test_review_recovery_failures.py` 6 pass |
| Report generation/save failure | **TESTED** | same 6 |
| Outbox insertion failure | **TESTED** | same 6 |
| Branch-movement integration | **TESTED** | same 6 |
| R7-B01 D-01/D-02 | **OWNER_DECISION_REQUIRED** | this report; no approval found |
| R7-B02 worker activation | **DEFERRED** | no startup wiring; `bot/app.py` starts only existing workers |
| R7-B03 live resources | **BLOCKED** | no authorized provider/repo/Telegram/live access |

Note: the historical `OHB2-R7-REMEDIATION-REPORT-20261125.md` shows older counts
(13/398/4222); the current focused run in this task is 15/430 and is the authoritative
local evidence. The historical report was not rewritten.

No locally actionable R7 remediation defect was found within this task's no-
implementation scope. No fix was made.

---

## 9. Local verification actually performed

Because no implementation was authorized, only relevant existing tests were run.

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q tests/test_review_resolver.py` | **32 passed** |
| `.venv/bin/python -m pytest -q tests/test_auto_reviews_db.py` | **23 passed** |
| `.venv/bin/python -m pytest -q tests/test_auto_review_lifecycle.py` | **30 passed** |
| `.venv/bin/python -m pytest -q tests/test_review_branch_sha.py` | **8 passed** |
| `.venv/bin/python -m pytest -q tests/test_review_ci_jobs.py` | **15 passed** |
| `.venv/bin/python -m pytest -q tests/test_review_provider_binding.py` | **11 passed** |
| `.venv/bin/python -m pytest -q tests/test_review_recovery_failures.py` | **6 passed** |
| `.venv/bin/python -m pytest -q tests/test_review_collector.py` | **3 passed** |
| `.venv/bin/python -m pytest -q tests/test_review_report.py` | **11 passed** |
| `.venv/bin/python -m pytest -q tests/test_review_delivery.py` | **8 passed** |
| `.venv/bin/python -m pytest -q tests/test_review_worker_integration.py` | **1 passed** |
| `.venv/bin/python -m pytest -q tests/test_review_*.py tests/test_auto_review*.py tests/test_verify_workflow_security.py` | **430 passed** |

Not run: full Python suite, Node suite, pyflakes, Bandit, pip-audit, compileall,
remote CI. Reason: no implementation was authorized; the task says to run only
relevant existing tests. No Python 3.11 claim is made.

Environment: Python 3.13.15, pytest 9.0.3, Node 24.22.2 (Node not exercised).

---

## 10. Remaining blockers and owner decisions

1. **D-01** — choose `A | B | C | reject-for-now`. No approval exists.
2. **D-02** — choose `OpenHands-candidate | explicit-list | new-convention |
   reject-for-now`. No approval exists.
3. **D-03** — authorization source (`watched-chat` vs OpenHands-owner-check) remains
   open; D-01 B uses the existing watched/chat boundary only.
4. **D-04** — durable provenance/schema remains open; this design is in-memory only.
5. **D-05** — rename/transfer policy remains reject-by-default; identity continuity
   cannot be proven without a stored numeric ID.
6. **D-06** — fork policy remains reject-by-default.
7. **D-07** — worker activation deferred; no `ReviewWorker`/`ReviewRunner` startup.
8. **D-08** — live resources/authorization blocked.
9. **D-09** — independent review and R8 remain deferred.

---

## 11. Exact proposed approval (not approved by this report)

The owner decision request is in:

`docs/reviews/OHB2-R7-CANARY-LINKAGE-OWNER-DECISION-REQUEST-20261125.md`

Exact format if the owner chooses the proposed bounded canary:

```text
D-01: B
D-02: explicit-list
```

This is a proposal only. It does not authorize implementation until the owner records
the decision explicitly. Even if recorded, D-01 B remains limited to bot-created
conversations and does not close automatic D-01 for all conversations. D-02 remains
explicit-owner input and does not add PR discovery.

---

## 12. Safety confirmation

- No implementation of D-01 or D-02.
- No resolver change.
- No schema/migration/table/index/trigger change.
- No code/test/config change.
- No live OpenHands/GitHub/provider/Telegram call.
- No worker activation.
- No commit/push/PR/merge/deploy/release.
- Independent review remains deferred.
- R7 live validation has not started.
- R8 has not started.
- Autopush remains disabled/inactive.

Final verdict: **`R7_CANARY_LINKAGE_OWNER_DECISION_REQUIRED`**.
