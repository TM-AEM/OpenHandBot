# OHB2-AUTO-REVIEW-R7 — Author Self-Review (2026-11-25)

## 0. Status

**Author self-review only. This is not an independent review and not a `PASS`.**

- Task: OHB2-AUTO-REVIEW-R7 — Phase A readiness audit and non-invasive test preparation.
- Verdict under review: `R7_READINESS_NEEDS_FIXES`.
- Phase B (live external validation): **not authorized and not executed**.
- No commit, push, PR/MR, merge, deployment, release, remote CI trigger, provider inference,
  Telegram message, OpenHands task, or review-worker activation was performed.

---

## 1. What was reviewed

1. Baseline Git state and working-tree inventory.
2. R1 workflow security and exact-SHA protections.
3. R2 configuration, provider snapshots, and reservation semantics.
4. R3 read-only GitHub client, exact SHA/job binding, and redaction.
5. R4 schema, prompt isolation, provider adapter, evidence validation, and verdict rules.
6. R5 membership/evidence persistence, lease/fencing, worker recovery, and outbox intent.
7. R6 deterministic report, Telegram delivery path, callbacks, owner authorization, and
   `OWNER_ACCEPTANCE`.
8. Runtime activation boundaries in `bot/app.py`.
9. Database schema/migration behavior and table count.
10. The R7 readiness report itself, including the failure-injection matrix, canary design, data
    egress analysis, and Phase B checklist.

---

## 2. Acceptance criteria for Phase A

| Criterion | Result | Evidence |
|---|---|---|
| Baseline Git state recorded without destructive operations | MET | Branch/HEAD/main/origin/main/tree/status recorded; no reset/clean/checkout |
| R1–R6 integration inspected and preserved | MET | Source and tests inspected; no R1–R6 file changed by this task |
| External dependency readiness matrix covers OpenHands, GitHub Actions, provider, Telegram, DB/runtime | MET | Readiness report §3 A–E |
| Controlled canary design includes known defect and corrected defect, isolation, exact SHA, deterministic defect, cleanup | MET | Readiness report §8 |
| Failure-injection matrix covers all 25 requested cases with injection/state/verdict/recovery/evidence/local-vs-live | MET | Readiness report §9 |
| Authorized local verification completed | MET | 358 focused + 4182 full Python; 280 Node; pyflakes/compileall/Bandit/pip-audit/git diff check |
| Reports created at the requested paths | MET | This file and `OHB2-AUTO-REVIEW-R7-READINESS-REPORT-20261125.md` |
| No live operations | MET | No OpenHands/GitHub/provider/Telegram call; no worker start; no remote CI |
| No publication | MET | No commit/push/PR/merge/deploy/release |
| Independent review remains deferred | MET | Author self-review only; R0F remains blocked |

---

## 3. Self-review findings

### F1 — B-01 conversation → PR → SHA remains unresolved (BLOCKER)

**Evidence:** `OpenHandsClient.start_conversation()` sends `selected_repository` and
`selected_branch`, not `pr_number` (`bot/openhands_client.py:386-397`). R0E records B-01 as
`UNVERIFIED`: no real conversation with non-empty `pr_number` and matching PR/SHA/CI. R5
`reserve_conversation_review()` requires caller-supplied memberships; no discovery code exists.

**Impact:** The readiness report cannot claim a complete OpenHands-conversation → PR → review E2E.
Option B (explicit membership harness) can test R3–R6, but must be labelled as not validating
conversation→PR discovery.

**Disposition:** Keep `R7_READINESS_NEEDS_FIXES`; require an owner decision before Phase B.

### F2 — Incomplete CI job evidence can reach PASS (MEDIUM)

**Evidence:** `_validate_ci()` verifies only that supplied job groups are internally SHA/run-bound;
it does not require a group for every run or require jobs to be complete
(`bot/review/evidence.py:533-551`). `ReviewEvidence.ci_state` is derived from workflow runs only
(`bot/review/evidence.py:80-83`). A successful run with an empty/partial jobs response can therefore
produce `PASS` if there are no valid findings.

**Impact:** CI evidence completeness is not proven; this is a false-confidence risk, not a
provider/verdict fabrication.

**Disposition:** Marked `LOCAL_GAP` in the matrix; add a job-completeness assertion and test before
Phase B. Do not patch R3/R4 behavior in Phase A.

### F3 — Review worker has no runtime activation path (BLOCKER for live E2E)

**Evidence:** `bot/app.py` constructs `ReviewReportService` and registers `^review:` but starts only
the existing outbox/creation/completion/watcher/notifier workers (`bot/app.py:114-117`, `:150`,
`:282-329`). No `ReviewRunner`/`ReviewWorker` is constructed. `REVIEW_ENABLED` is configuration
validation only.

**Impact:** No live cycle can start from the normal bot process. Phase B needs an explicit isolated
harness/activation approval.

**Disposition:** Keep as blocker; do not activate in Phase A.

### F4 — R5 does not enforce provider snapshot binding (MEDIUM)

**Evidence:** `ProviderBinding.from_config()` checks current provider/api_base/model against the
snapshot (`bot/review/llm.py:161-181`), but `ReviewRunner.run()` only checks that the snapshot row
exists (`bot/review/worker.py:112-120`) and accepts any `ReviewProvider`.

**Impact:** A live harness could use a different model/adapter under a snapshot ID, weakening the
immutable-provider guarantee.

**Disposition:** Require the live harness to construct `DirectProviderAdapter` from
`ProviderBinding.from_config`; add a mismatch test before Phase B.

### F5 — Branch movement is not explicitly revalidated by R5 (LOW)

**Evidence:** R3 has `verify_branch_sha()` and branch-movement tests, but
`GitHubEvidenceCollector.collect()` does not call it; it relies on exact compare/runs/jobs SHAs.

**Impact:** The reviewed commit remains exact; a moved branch is not silently substituted, but the
branch-movement failure case is only partially integrated.

**Disposition:** Document exact-SHA-only behavior or add an integration test.

### F6 — Runbook wording is stale (LOW)

**Evidence:** `docs/OPERATIONS_RUNBOOK.md:68` still describes `REVIEW_ENABLED` as an R2-only
configuration validation. R6 has since added report/delivery/callback behavior.

**Impact:** Operator confusion; no runtime/security effect.

**Disposition:** Note for a later approved documentation change; do not expand scope here.

### F7 — Repository/publication state is unchanged (INFO)

**Evidence:** R1–R6 work remains uncommitted; no commit/push/PR. Independent review is still
deferred; R0F remains blocked.

**Impact:** R7 Phase A does not publish or approve R1–R6.

**Disposition:** Preserve; no publication.

---

## 4. Local verification self-check

Commands run (all local; no OpenHands/GitHub/provider/Telegram call, no remote CI):

| Check | Actual result |
|---|---|
| Focused R1–R6 suite | **358 passed**, 0 failed |
| Full Python suite | **4182 passed**, 0 failed, 74 warnings |
| Node suite | **280 pass**, 0 fail |
| pyflakes | 0 findings |
| compileall | 0 errors |
| Bandit (`-lll -s B613`) | 0 High (7 Low / 20 Medium) |
| pip-audit | no known vulnerabilities |
| `git diff --check` | clean |
| Fresh local DB table count | 26 tables |

No test was changed or disabled. No test output was fabricated. Python 3.11 is not installed
locally; only the CI matrix can verify 3.11.

---

## 5. Report-quality self-review

Checked:

- Baseline and environment are factual and include the uncommitted R1–R6 state.
- R1–R6 integration table distinguishes local verification from live evidence.
- OpenHands, GitHub Actions, provider, Telegram, and DB/runtime sections each state mechanism,
  permissions/limits, current status, and gaps.
- Canary design uses a harmless deterministic defect, exact file/line references, isolated target,
  exact SHA, and a separate correction scenario.
- Failure-injection matrix covers all 25 requested cases and marks local-tested vs. local-gap vs.
  live-required.
- Data-egress section distinguishes GitHub reads, provider payloads, Telegram report, OpenHands
  task execution, and local DB/logs.
- Phase B checklist separates the five authorization categories and does not imply approval.
- The report explicitly states that no live operation occurred, R5 remains inactive, no publication
  occurred, independent review remains deferred, and R8 has not started.

No secret value appears in either R7 report. No API key, token, password, or private key was printed.

---

## 6. Residual limitations

- This is an author self-review, not independent verification.
- No live provider/GitHub/Actions/Telegram/OpenHands evidence exists.
- B-01, worker activation, and incomplete-job handling remain unresolved.
- The report's canary design is not an executed test; expected verdicts are conditional on actual
  validated evidence.
- Python 3.11 and remote GitHub Actions remain unverified locally.
- R1–R6 remain uncommitted; no publication or review approval is claimed.

---

## 7. Conclusion

Phase A is complete and stops before Phase B. The readiness verdict remains
`R7_READINESS_NEEDS_FIXES`. Do not interpret this report as authorization for any live operation,
provider inference, GitHub write/dispatch, Telegram delivery, or worker activation.
