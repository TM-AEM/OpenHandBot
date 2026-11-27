# OHB2-R7 — Local Remediation and Verification Report (2026-11-25)

**Task:** `OHB2-R7-REMEDIATION-AND-LOCAL-VERIFICATION`
**Scope:** local code, tests, documentation, and local verification only.
**Final verdict:** `R7_REMEDIATION_VERIFIED_WITH_NOTES` (local verification only; not live R7 validation).

No live operation was performed: no OpenHands API call, GitHub API call or write,
workflow dispatch, provider inference, Telegram message, worker activation, remote CI,
deployment, or release.

---

## 1. Baseline and final Git state

Baseline was inspected before editing and is preserved in the working tree.

| Item | Value |
|---|---|
| Repository | `/workspace/project/OpenHandBot` |
| Branch | `agent/r6-review-delivery` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `origin/main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| HEAD tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| Tracked files | 569 |
| Modified tracked files | 12 |
| Untracked files | R1–R6 implementation, review tests, and review reports |

The current canonical GitHub `main` was not re-queried because this task forbids live
GitHub API calls. The local `main` and `origin/main` both point to the same SHA as the
R7 readiness baseline. All R1–R7 implementation remains uncommitted; no commit, push,
PR, merge, deployment, or release was performed.

Preserved without deletion: `.openhands/`, historical reports, `bun.lock`, and unrelated
working-tree changes. No destructive Git operation was used.

---

## 2. Findings and disposition

| ID | Disposition | Evidence / reason |
|---|---|---|
| R7-F01 — incomplete CI job evidence could reach PASS | **FIXED_AND_TESTED** | Contract-based `jobs_complete`; evidence defaults incomplete; verdict blocks with `R4-CI-03`. 15 focused tests. |
| R7-F02 — runner accepted any provider under a snapshot | **FIXED_AND_TESTED** | `ReviewRunner` verifies snapshot identity, fingerprint, exact snapshot id, and adapter binding before collection/provider calls. 11 focused tests, including zero provider calls. |
| R7-F03 — branch movement not explicitly revalidated | **FIXED_AND_TESTED** | Collector verifies branch/SHA before and after all reads; 8 focused tests. |
| R7-F04 — no required-check/latest-per-workflow policy | **VERIFIED_NO_CHANGE_REQUIRED** | Existing behavior is conservative: all runs for the SHA are considered and older failures can over-block, never create a false PASS. No scope change made. |
| R7-F05 — stale `REVIEW_ENABLED` runbook wording | **FIXED_AND_TESTED** | Runbook now separates configuration existence, feature eligibility, worker activation, and external execution; worker remains inactive. |
| R7-B01 — conversation → PR → exact SHA unresolved | **OWNER_DECISION_REQUIRED** | Decision report: `docs/reviews/OHB2-R7-B01-CONVERSATION-PR-SHA-DECISION-20261125.md`. |
| R7-B02 — no authorized worker activation path | **DEFERRED** | Activation boundary documented; no startup wiring or worker activation added. |
| R7-B03 — no provider/disposable repository/Telegram target | **BLOCKED** | External resources and live operations are outside this task. |
| R7-F06 — uncommitted work and independent review deferred | **DEFERRED** | No publication; independent review remains deferred and is not claimed. |
| Missing coverage B/C/D/E | **FIXED_AND_TESTED** | `tests/test_review_recovery_failures.py` (6 tests) covers DB, report, outbox, and branch-movement failures. |

---

## 3. F-01 — CI job completeness is fail-closed

### Implementation

- `bot/review/ci_contract.py` defines expectations only for the checked-in workflow
  contract:
  - `.github/workflows/ci.yml`: `Tests & lint` (two matrix jobs, prefix match) and
    `Frontend tests (Node)`.
  - `.github/workflows/verify.yml`: `Validate requested SHA`, `Python 3.11 checks`,
    `Python 3.13 checks`, and `Frontend tests (Node)`.
- `expectations_for_run()` returns `None` for an unknown workflow path/name. An unknown
  workflow cannot establish completeness.
- `jobs_complete()` returns `True` only when:
  - the workflow-run evidence is verified and non-empty;
  - every run has exactly one verified job group with the same head SHA;
  - job ids are unique and every job belongs to its run and SHA;
  - every job is `completed` with conclusion `success`;
  - the documented expected job names/counts are present;
  - no extra or unmatched job records exist.
- `ReviewEvidence.from_raw_diff()` now defaults `ci_jobs_complete` to `False` when the
  caller does not supply an explicit contract result. It no longer infers completeness
  from an arbitrary successful run/job shape.
- `ReviewEvidence.from_compare()` forwards the collector's explicit completeness result.
- `evaluate_verdict()` checks `evidence.ci_jobs_complete` before returning `PASS` and
  returns `BLOCKED` / `ci_jobs_incomplete_or_unverified` / `R4-CI-03` otherwise.

### Regression coverage

`tests/test_review_ci_jobs.py` — **15 passed**:

1. All expected jobs present and successful → `PASS`.
2. One expected job missing → `BLOCKED`.
3. Empty job list → `BLOCKED`.
4. Job retrieval failure → explicit `EvidenceCollectionError`.
5. Pagination/truncation failure → explicit `GitHubPaginationError` evidence error.
6. Failed job → `BLOCKED`.
7. Cancelled job → `BLOCKED`.
8. Duplicate job records → `BLOCKED`.
9. Job belonging to another run → `ci_job_mismatch`.
10. Evidence belonging to another SHA → `ci_sha_mismatch`.
11. Unknown workflow contract → completeness false and `BLOCKED`.
12. Direct evidence construction without explicit completeness → false and `BLOCKED`.
13. CI matrix prefix contract → completeness true only with both matrix jobs.
14. Job group from another repository → completeness false and `BLOCKED`.
15. Duplicate workflow-run records → completeness false and `BLOCKED`.

No successful workflow-run conclusion alone can produce `PASS`.

---

## 4. F-02 — provider snapshot binding enforced before invocation

### Implementation

- `ProviderBinding.from_config()` validates current provider/api-base/model against the
  immutable snapshot and keeps the API key out of `repr` (`bot/review/llm.py:170-191`).
- `ReviewRunner.run()` calls `_verify_provider_binding()` before membership collection or
  any provider stage (`bot/review/worker.py:122-180`).
- The check validates:
  - provider identity;
  - API base URL;
  - model identifier;
  - configuration fingerprint;
  - exact persisted snapshot id (a missing id cannot prove cycle association);
  - adapter binding equality when the provider exposes one.
- Failures raise `ReviewPipelineError` with safe codes only:
  `provider_binding_required`, `provider_binding_mismatch`,
  `provider_binding_cycle_mismatch`, `provider_adapter_binding_mismatch`.
- No API key or snapshot contents are included in exception text.
- The immutable snapshot is only read; it is never updated to make a mismatch pass.

`run_review_cycle()` is the pure R4 evidence-in/stage-out primitive used by tests; it is
not wired to the R5 worker or any startup path. The only R5 cycle entry point is
`ReviewRunner.run()`.

### Regression coverage

`tests/test_review_provider_binding.py` — **11 passed**:

- valid binding reaches the provider and completes;
- missing binding fails before collector/provider (zero calls);
- changed provider, API base, model, or fingerprint fails (zero provider calls);
- binding from another cycle fails;
- same-content binding with another snapshot id fails;
- binding without a snapshot id fails cycle association;
- adapter binding mismatch fails;
- mismatch does not mutate the immutable snapshot;
- secret sentinel is absent from the exception text.

---

## 5. F-03 — explicit branch/SHA verification

### Implementation

`GitHubEvidenceCollector.collect()` (`bot/review/collector.py:45-110`) now performs an
explicit `verify_branch_sha()`:

1. before compare/runs/jobs reads;
2. again after all reads, before evidence is returned.

Any status other than `unchanged` becomes `branch_moved`, `branch_missing`, or
`branch_blocked`. Compare membership mismatch, workflow-run SHA mismatch, malformed SHA,
and GitHub verification errors fail explicitly. The read-only client design, redaction,
and response-size controls are unchanged.

### Regression coverage

`tests/test_review_branch_sha.py` — **8 passed**:

1. exact branch/SHA match collects evidence;
2. branch moved before collection → `branch_moved`;
3. branch moved during collection → `branch_moved`;
4. malformed requested SHA → `invalid_branch_or_sha`;
5. compare result SHA mismatch → `compare_membership_mismatch`;
6. workflow run SHA mismatch → `ci_sha_mismatch`;
7. GitHub verification failure → explicit transport error;
8. GitHub response missing the required SHA → `branch_missing`.

No live GitHub API call was made.

---

## 6. Missing local coverage B–E

`tests/test_review_recovery_failures.py` — **6 passed**:

- **B — Database lock/write failure:** reservation under an exclusive SQLite lock fails
  without acknowledging or persisting a review; a forced lifecycle write failure leaves
  the cycle reserved with no verdict and its lease intact.
- **C — Report generation/save failure:** report build or save failure creates no report,
  no outbox row, and no `sent` state; a later service instance recovers the pending report.
- **D — Outbox insertion failure:** the verdict remains durable in `delivery_pending`;
  no outbox row exists until recovery; recovery inserts exactly one row. The existing
  verdict-before-outbox ordering and idempotency are preserved.
- **E — Branch-movement integration:** the complete mocked R5 collection path moves the
  branch between initial discovery and final validation; the worker records retry-wait,
  no verdict is set, no provider is called, and no outbox row is created.

All tests use deterministic mocks and isolated temporary SQLite databases; no production
data was used.

---

## 7. R7-B01 — conversation → PR/SHA decision

Status: **`R7_B01_OWNER_DECISION_REQUIRED`**.

The code can accept an explicit `AutoReviewMembership` snapshot and validate it, but it
does not resolve a PR or exact head SHA from an OpenHands conversation. The current
OpenHands client exposes `selected_repository`/`selected_branch` at start, not a trusted
PR identity; `pr_number` handling is not a resolver, and no trailer/PR-reference
convention exists.

Options and the exact owner decision are in
`docs/reviews/OHB2-R7-B01-CONVERSATION-PR-SHA-DECISION-20261125.md`. The approved
conversation-wide review scope is unchanged.

---

## 8. R7-B02 — worker activation boundary

No activation was implemented.

- `bot/app.py` still constructs only the existing outbox/creation/completion/watcher/
  notifier workers; it does not construct `ReviewWorker` or `ReviewRunner`.
- A future activation task would need explicit construction and startup wiring,
  configuration validation (repositories, provider, model, API base, keys), authorization
  for external execution, a disabled-by-default switch, graceful shutdown, lease
  recovery, and tests for startup/shutdown, duplicate ownership, lease expiry, and
  crash recovery.
- `REVIEW_ENABLED=1` alone does not start the worker or any external execution.
- Worker activation remains unauthorized and inactive.

---

## 9. R7-F05 — runbook correction

`docs/OPERATIONS_RUNBOOK.md` now states:

- `REVIEW_ENABLED=1` validates review configuration and makes the feature eligible for
  setup only;
- feature eligibility is not worker activation;
- `ReviewWorker` is not started by `main.py` in R2–R7;
- external execution requires an explicit cycle/membership/SHA and branch/SHA/CI checks;
- `REVIEW_ENABLED=1` alone starts neither the collector nor the provider and sends no
  report.

The runbook does not imply that setting `REVIEW_ENABLED=true` activates the pipeline.

---

## 10. Local verification (exact commands and results)

Environment: Python 3.13.15 in `.venv`, pytest 9.0.3, Node 24.22.2. Python 3.11 is not
installed locally; no Python 3.11 claim is made. No remote CI was run.

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q tests/test_review_ci_jobs.py` | **13 passed** |
| `.venv/bin/python -m pytest -q tests/test_review_provider_binding.py` | **11 passed** |
| `.venv/bin/python -m pytest -q tests/test_review_branch_sha.py` | **8 passed** |
| `.venv/bin/python -m pytest -q tests/test_review_recovery_failures.py` | **6 passed** |
| `.venv/bin/python -m pytest -q tests/test_review_*.py tests/test_auto_review*.py tests/test_verify_workflow_security.py` | **398 passed** |
| `.venv/bin/python -m pytest -q` | **4222 passed**, 0 failed, 74 warnings, 338.36s |
| `node --test tests/frontend/*.test.js` | **280 pass**, 0 fail |
| `.venv/bin/python -m pyflakes bot/ automation/ tools/ main.py tests/` | 0 findings |
| `.venv/bin/python -m compileall -q bot automation tools main.py tests` | 0 errors |
| `.venv/bin/python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | High 0 (Low 7, Medium 20) |
| `.venv/bin/python -m pip_audit -r requirements-dev.txt` | No known vulnerabilities |
| `git diff --check` | clean |

No test was disabled or weakened to obtain these results. The only fixture adjustments
pass an explicit `ci_jobs_complete=True` where a test intentionally isolates verdict
precedence from F-01 contract checks.

---

## 11. Remaining blockers and notes

- **B01 remains an owner decision.** No automatic conversation → PR → exact SHA resolver
  exists, and none was invented.
- **B02 remains deferred.** The R5 worker is not activated.
- **B03 remains external.** No provider, disposable repository, or Telegram test target
  was configured.
- **Independent review is deferred.** This report is an author implementation report, not
  an independent review and not a live `PASS`.
- **R7 live validation is not complete.** No live provider, GitHub, OpenHands, Telegram,
  or Actions evidence exists.
- **Python 3.11 and remote GitHub Actions are unverified locally.**
- **R1–R7 changes are uncommitted.** No publication occurred.

---

## 12. Safety confirmation

- No OpenHands API call, GitHub API call/write, workflow dispatch, provider call,
  Telegram message, or external data transmission.
- No worker activation or startup wiring.
- No production database access or migration.
- No secrets in this report.
- No commit, push, PR, merge, deployment, release, or destructive Git operation.
- `.openhands/`, unrelated untracked files, and historical reports were preserved.
- Autopush remains disabled/inactive.
- Independent review remains deferred.
- R8 has not started.
