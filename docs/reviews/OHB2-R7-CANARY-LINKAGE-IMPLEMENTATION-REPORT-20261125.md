# OHB2-R7 — Canary Linkage Implementation Report (2026-11-25)

**Task ID:** `OHB2-R7-CANARY-LINKAGE-D01B-D02-EXPLICIT-LIST`
**Verdict:** `R7_CANARY_LINKAGE_IMPLEMENTED_AND_VERIFIED_WITH_NOTES`

**Approval basis:** the task instruction explicitly approves the provisional,
canary-limited D-01 B and D-02 Explicit-list decisions. This report does not infer
approval for D-03 through D-09.

**Scope:** local code, tests, documentation, and local verification only. No live
operation, worker activation, or Git publication was performed.

---

## 1. Baseline and final Git state

### Baseline (before editing)

| Item | Value |
|---|---|
| Repository | `/workspace/project/OpenHandBot` |
| Branch | `agent/r6-review-delivery` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `origin/main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| HEAD tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| Tracked files | 569 |
| Modified tracked | 12 (pre-existing) |
| Untracked entries | 56 |
| Python | 3.13.15 in `.venv` |
| pytest | 9.0.3 |
| Node | 24.22.2 |

The working tree already contained R1–R7 work, `bot/review/`, review tests, and reports.
They were preserved. No destructive Git operation was used.

### Final (after this task)

| Item | Value |
|---|---|
| Branch | `agent/r6-review-delivery` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` (unchanged) |
| `main` / `origin/main` | unchanged |
| HEAD tree | unchanged |
| New code | `bot/review/canary_linkage.py` |
| Changed code | `bot/db.py` (one read-only method), `bot/review/__init__.py` (docstring) |
| New tests | `tests/test_review_canary_linkage.py` (42 tests) |
| Docs | implementation report, self-review, runbook note, `.agent/PROGRESS.md` |
| Schema/migration | **none** |
| Commit/push/PR/merge/deploy/release | **none** |

The prior owner-decision-required report and self-review were archived, not deleted:

- `docs/reviews/OHB2-R7-CANARY-LINKAGE-OWNER-DECISION-REQUIRED-REPORT-20261125.md`
- `docs/reviews/OHB2-R7-CANARY-LINKAGE-OWNER-DECISION-REQUIRED-SELF-REVIEW-20261125.md`

---

## 2. Exact interpretation of the approved decisions

### D-01 B — bot-created conversation repository source

For a conversation created by OpenHandBot:

1. Find `creation_jobs` rows with the exact persisted `conversation_id`.
2. Accept only rows with `status='done'`.
3. Require exactly one row; zero or multiple rows fail closed.
4. Require the row's `chat_id` to equal the configured owner.
5. Require a strict `owner/repo` value.
6. Require OpenHands `selected_repository` to match that value exactly
   (case-insensitive); it is a check, never a fallback.
7. Resolve the repository through GitHub and require the canonical full name to match.
8. Use the GitHub numeric repository ID in the returned link.
9. The resolver re-verifies the numeric ID and full name before creating membership.

This is limited to bot-created conversations. It does not claim support for arbitrary
OpenHands conversations and does not use `watched.chat_id`, `created_by_user_id`, message
display fields, or historical `auto_reviews` rows as repository authority.

### D-02 Explicit-list

For one canary cycle:

1. Only the configured owner `chat_id` may submit.
2. The PR list must be explicitly supplied as a non-empty `list`/`tuple`.
3. Every item must be a unique positive integer (not `bool`, string, float, or `None`).
4. At most 20 PR candidates by default.
5. Every PR is verified through the existing resolver: repository ID/full name, PR
   number, base/head repository, fork, open state, branch, exact head SHA, compare.
6. No PR discovery, no branch/URL inference, no OpenHands `pr_number`, no first-PR
   selection, and no silent omission of invalid entries.
7. The existing reservation API persists one immutable conversation-wide membership
   snapshot.

---

## 3. Files and schema changed

### Added

- `bot/review/canary_linkage.py`
  - `CreationJobRepositoryLinkSource`
  - `CanaryLinkageService`
  - strict owner PR-list validation
- `tests/test_review_canary_linkage.py`
  - 42 deterministic tests using isolated SQLite databases and mocks.

### Changed

- `bot/db.py`
  - Added read-only `list_done_creation_jobs_for_conversation(conversation_id)`.
  - Uses existing `creation_jobs` columns; no schema change.
- `bot/review/__init__.py`
  - Package docstring mentions the canary linkage module.
- `docs/OPERATIONS_RUNBOOK.md`
  - Documents that the canary adapter is not wired into `bot/app.py` and does not
    discover PRs.
- `.agent/PROGRESS.md`
  - Additive task entry; historical entries retained.

### Schema

**No schema change was made.** No table, column, index, trigger, migration, or
production database access was added. The canary uses the existing `creation_jobs.repo`
and `conversation_id` values.

---

## 4. D-01 B implementation

`CreationJobRepositoryLinkSource.resolve(conversation_id)`:

- Validates conversation ID shape.
- Calls `Database.list_done_creation_jobs_for_conversation()`.
- Rejects zero or more than one `done` row.
- Rejects a job whose `conversation_id` or owner `chat_id` does not match.
- Rejects null/malformed repository values.
- Requires exactly one OpenHands conversation record with the same ID.
- Requires `selected_repository` to normalize and match the job repository.
- Calls `GitHubClient.get_repository()` and requires `RepositoryIdentity`.
- Requires the canonical full name to match the job value.
- Returns `ConversationRepositoryLink` with the GitHub numeric ID and source
  `canary_creation_job`.

The existing resolver then calls `get_repository()` again and rejects a numeric ID or
canonical-name mismatch. This double read is deliberate fail-closed verification.

Failure behavior:

- Missing/ambiguous/malformed/untrusted association -> `None`; resolver reports
  `missing_conversation_repository_link`.
- DB read failure -> resolver reports `conversation_link_unavailable`.
- GitHub transport/rate/server failure -> resolver reports
  `conversation_link_unavailable`.
- No fallback to OpenHands metadata, repository-name discovery, or another job.

### Identity limitation retained

`creation_jobs` does not store the GitHub numeric repository ID observed at creation.
A deleted-and-recreated repository with the same name cannot be distinguished from the
original. The implementation and tests record this limitation; it is not claimed as
identity continuity. A durable numeric ID would require a separate D-04 schema decision.

---

## 5. D-02 implementation

`CanaryLinkageService`:

- Requires `chat_id == owner_id` before touching resolver, OpenHands, or GitHub.
- Rejects non-list/tuple, empty, over-limit, duplicate, bool, string, float, `None`,
  zero, and negative PR values.
- Sorts and preserves the explicit list.
- Delegates all repository/PR/SHA verification to the existing
  `ConversationMembershipResolver`.
- `resolve_and_reserve()` calls the existing `reserve_resolved_memberships()`.
- Does not discover PRs, inspect OpenHands `pr_number`, infer PRs from branch names,
  or select the first PR.
- Does not add a per-PR cycle mode.

Invalid entries fail the whole request. A valid PR followed by an invalid PR creates no
cycle and leaves no membership.

---

## 6. Resolver and lifecycle integration

- `bot/review/resolver.py` was **not modified**.
- The canary service uses the existing resolver and the existing atomic
  `reserve_conversation_review()` path.
- The single SQLite owner remains `Database`.
- No second database owner, worker, lease, fencing, outbox, or verdict path was added.
- The existing conversation-wide scope is preserved: one active cycle per conversation,
  containing the explicitly supplied PR set.
- Existing immutable membership triggers remain in force.
- A failed linkage or PR validation creates no active cycle.
- Identical retries are idempotent; conflicting retries return the existing
  `conflicting_identity` outcome and do not mutate the active snapshot.
- A new PR after an active cycle remains pending and does not mutate the active cycle.

No runtime wiring was added to `bot/app.py`; `ReviewWorker`/`ReviewRunner` remain
inactive.

---

## 7. Repository identity verification behavior

- GitHub numeric ID is the membership identity.
- Canonical full name is display/verification metadata.
- The local repository name is never used as durable identity.
- Repository allowlist enforcement remains in `GitHubClient`.
- A full-name mismatch is rejected even if GitHub returns an ID.
- A numeric ID mismatch between the canary source and resolver verification is rejected.
- Cross-repository PRs and forks are rejected by the resolver.
- Same-name delete/recreate is not distinguishable without a stored prior ID; this is
  explicitly documented.

---

## 8. Immutable membership and conversation-wide guarantees

Verified by existing and new tests:

- Membership rows are immutable once persisted.
- Reservation is atomic; failed validation inserts no partial membership.
- One active conversation-wide cycle is enforced.
- New PRs after reservation are pending, not active mutations.
- Duplicate and conflicting retries fail explicitly.
- Concurrent reservations produce one winner.
- Existing outbox and verdict behavior is unchanged.

---

## 9. Tests actually executed

New focused suite:

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q tests/test_review_canary_linkage.py` | **42 passed** |
| `.venv/bin/python -m pytest -q tests/test_review_resolver.py tests/test_review_canary_linkage.py tests/test_auto_review_lifecycle.py tests/test_auto_reviews_db.py` | **124 passed** |
| `.venv/bin/python -m pytest -q tests/test_review_*.py tests/test_auto_review*.py tests/test_verify_workflow_security.py` | **472 passed** |

Full local verification:

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q` | **4296 passed**, 74 warnings, 297.56s |
| `node --test tests/frontend/*.test.js` | **280 pass**, 0 fail |
| `.venv/bin/python -m pyflakes bot/ automation/ tools/ main.py tests/` | **0 issues** |
| `.venv/bin/python -m compileall -q bot automation tools main.py tests` | **0 errors** |
| `.venv/bin/python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | **High 0**; Low 7, Medium 20 |
| `.venv/bin/python -m pip_audit -r requirements-dev.txt` | **No known vulnerabilities** |
| `git diff --check` | clean |

Python 3.11 and remote CI were not run and are not claimed.

---

## 10. Security and adversarial test results

Covered by `tests/test_review_canary_linkage.py`:

- Missing creation job, job without conversation ID, wrong conversation, duplicate jobs,
  owner mismatch, malformed repository.
- OpenHands candidate mismatch/missing cannot override the job.
- Numeric repository ID mismatch, canonical full-name mismatch, missing identity, GitHub
  transport failure.
- Same-name delete/recreate limitation is documented.
- Non-owner submission rejected before external dependencies.
- Empty, malformed, duplicate, excessive, partial PR lists.
- Cross-repository PR, missing metadata, branch movement before/during validation,
  head SHA mismatch, invalid SHA.
- Immutable membership, conflicting retry, new cycle blocked, database lock rollback.
- Full mocked D-01 -> D-02 -> reservation path.
- No provider/Telegram calls; no live network.
- Secret sentinel absent from surfaced error text.

All tests use isolated temporary SQLite databases and deterministic fakes.

---

## 11. R7 remediation status

| Finding | Status |
|---|---|
| F-01 CI job completeness | `FIXED_AND_TESTED` — 15 tests pass |
| F-02 ProviderBinding | `FIXED_AND_TESTED` — 11 tests pass |
| F-03 branch/SHA | `FIXED_AND_TESTED` — 8 tests pass |
| DB lock/write failure | `TESTED` — 6 recovery tests pass |
| Report generation/save failure | `TESTED` — same 6 |
| Outbox insertion failure | `TESTED` — same 6 |
| Branch-movement integration | `TESTED` — same 6 |

No new R7 remediation defect was introduced.

---

## 12. Remaining owner decisions and live dependencies

D-03 through D-09 remain unresolved and were not inferred:

- **D-03:** broader authorization source (watched/owner vs OpenHands owner check).
  This canary uses the existing owner/chat + watched boundary only.
- **D-04:** durable provenance/schema. This implementation is in-memory/report-only.
- **D-05:** repository rename/transfer policy. Current behavior rejects name mismatch.
- **D-06:** fork policy. Current behavior rejects forks.
- **D-07:** worker activation. Not implemented.
- **D-08:** live resources/authorization. Not provided.
- **D-09:** independent review and R8. Deferred.

Live validation still requires explicit authorization and resources for OpenHands,
GitHub, provider, Telegram, a disposable repository, and a worker activation path.
None was used or claimed.

---

## 13. Safety confirmation

- No OpenHands API call.
- No GitHub API call/write, branch/PR creation, or Actions dispatch.
- No provider inference or external data transmission.
- No Telegram message.
- No `ReviewWorker` or `ReviewRunner` activation.
- No production database access or migration.
- No commit, push, PR/MR, merge, deployment, or release.
- Autopush remains inactive.
- Independent review remains deferred.
- R7 live validation has not started.
- R8 has not started.

Final verdict: **`R7_CANARY_LINKAGE_IMPLEMENTED_AND_VERIFIED_WITH_NOTES`**.
