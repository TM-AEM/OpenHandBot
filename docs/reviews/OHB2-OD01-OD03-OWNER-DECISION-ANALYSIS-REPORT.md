# OHB2 — OD-01 and OD-03 Owner Decision Analysis — Task Report

**Task ID:** `OHB2-OD01-OD03-OWNER-DECISION-ANALYSIS`
**Date:** 2026-11-22
**Mode:** decision analysis and documentation only; no implementation, tests, dependencies, lockfiles, runtime configuration, CI, Mini App, historical reports, or owner decisions were modified.
**Repository:** `/workspace/project/OpenHandBot`

---

## 1. Overall verdict

**`COMPLETE_WITH_NOTES`**

Both decisions were recovered from their authoritative sources, compared against the current
implementation, and given a combined recommendation. The package is complete, but the host lacks the
project test dependencies, so the existing attachment-focused behavioral tests were **NOT RUN** here.
No owner decision was recorded.

---

## 2. Baseline

| Item | Value |
|---|---|
| Branch | `main` |
| HEAD | `0774c9cff923a2ed02da36a1111a283a61600ea5` |
| HEAD tree | `faa7a3f03aa361698c6854281c162358bf38b84f` |
| Upstream local ref | `origin/main` at `0774c9cff923a2ed02da36a1111a283a61600ea5` |
| Fetch/pull | **Not performed** |
| Master reconciliation | `docs/reviews/OHB2-MASTER-BACKLOG-RECONCILIATION-AND-NEXT-TASK-REPORT.md` |
| Reconciliation SHA-256 | `0a2f771178bfc52e69f924a68b90956390e430191f8e07088ed6082d58dfdc9d` (verified) |
| Staged/committed by this task | **None** |

The baseline is the recorded value; no remote fetch, pull, branch switch, reset, clean, or force
operation occurred.

---

## 3. Evidence inspected

### 3.1 Decision definitions

- `docs/audits/OHB2-OWNER-DECISIONS-BRIEFING.md` §4 (`OD-01`) and §6 (`OD-03`).
- `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md` §`DEF-001`, §`DEF-014`, §`DEF-015`,
  §`WP-01`.
- `docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md` D-34, D-35, D-15.
- `docs/reviews/OHB2-MASTER-BACKLOG-RECONCILIATION-AND-NEXT-TASK-REPORT.md`.

### 3.2 Current implementation

- `bot/config.py:23,43,262,315-317` — Mini App and intake defaults.
- `.env.example:2` — intake flag is blank (default applies).
- `bot/handlers.py:2254-2262,2538-2558,2663-2679,2723-2805,2908-2917,2982-3009` — copy,
  intake kill switch, unsupported-media rejection, accompanying-text routing, text dispatch, and
  `/cancel`.
- `bot/db.py:1313-1361,1364-1377,1379-1386,1493-1585` — live/expired/unresolved/terminal routing
  and global terminal query.
- `bot/attachments.py:1349-1355` — reaper skips unresolved states.
- `bot/web/services.py:758-870` — MT-2 pending-only, 15-minute staged download path.
- `README.md:92`, `docs/OPERATIONS_RUNBOOK.md:67`, `docs/ZERO_TOUCH_STARTUP.md:94` — current
  default documentation.
- `tests/test_repair_plan_02_life03_intake_kill_switch.py`,
  `tests/test_attachment_batch_state_routing_f1_1a.py`,
  `tests/test_attachment_terminal_routing_remediation.py`,
  `tests/test_unsupported_attachment_rejection.py` — existing behavior/contract tests.

### 3.3 Historical status handling

Historical reports were not treated as current proof. The current code was checked directly for:

- the intake kill switch;
- the unconditional `_handle_accompanying_text` call;
- the owner-wide terminal query;
- the terminal `TERMINAL_UNPROVEN` classification;
- the `MT-2` pending-only read path;
- the current copy and documentation defaults.

---

## 4. Findings

1. **OD-01 is a genuine policy decision, not a missing code branch.** D-34 Option A is an approved
   owner policy. Changing it requires explicit owner authorization.
2. **Option A does not solve `DEF-001`.** `/cancel` currently clears awaiting state only; a terminal
   batch remains and `TERMINAL_UNPROVEN` continues to block all ordinary text across conversations.
3. **Option B is effective but has a silent-routing trade-off.** It can automatically pass a delayed
   accompanying text after passive expiry when no identity record exists.
4. **Option C is the strongest safety/operability balance.** It preserves fail-closed behavior for
   ambiguous states and requires a durable, explicit owner clearance for terminal batches.
5. **OD-03 default is currently `True`.** This stages documents even though `MINI_APP_ENABLED`
   defaults to `False` and Stage B remote upload is blocked.
6. **OD-03 Option A is the safer default.** It prevents fresh-install `DEF-001` exposure and makes
   `MT-2` an explicit opt-in; the cost is documented empty `MT-2` until `=1`.
7. **The two decisions are coupled.** Option C makes default `True` survivable but not as safe as
   default `False`; Option A reduces exposure but does not cure pre-existing batches.
8. **Existing batches are outside both decisions.** Config changes do not rewrite SQLite rows; WP-01
   still needs a pre-change inventory and conservative state-by-state handling.
9. **Copy needs correction regardless of choice.** `UNSUPPORTED_ATTACHMENT_TEXT` still advertises
   document intake when disabled, and accepted copy does not clearly say local-only (`NEW-DEF-06`).

---

## 5. Recommendations

### 5.1 OD-01

**Recommend Option C** — hybrid explicit terminal clearance.

- Keep `TERMINAL_ASSOCIATED` fail-closed.
- Keep `UNRESOLVED`, `MULTI_LIVE`, `EXPIRED_PENDING`, `invalid_t0`, out-of-enum/NULL, and ambiguous
  ownership fail-closed.
- Keep passive terminal batches fail-closed until explicit owner clearance.
- Clear only a specific verified terminal batch; recommended subset `expired`/`rejected` only.
- Do not auto-clear on reaper expiry, startup, duplicate delivery, or timeout.
- Preserve D-35 identity evidence.

### 5.2 OD-03

**Recommend Option A** — default `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=False`.

- `=1` is an explicit opt-in for local `MT-2` staging.
- Update README, Runbook, ZERO_TOUCH, `.env.example`, config defaults, and default tests.
- No Mini App files or `docs/MINI_APP.md` changes.

### 5.3 Combined recommendation

**OD-01 Option C + OD-03 Option A.**

This is internally consistent: no new batches on fresh installs; opted-in users get local staging;
terminal recovery is explicit and cannot silently reroute delayed text; all ambiguous states remain
fail-closed.

---

## 6. Verification results

### 6.1 Baseline verification

```sh
git rev-parse HEAD
git rev-parse HEAD^{tree}
sha256sum docs/reviews/OHB2-MASTER-BACKLOG-RECONCILIATION-AND-NEXT-TASK-REPORT.md
```

Results matched the recorded baseline and reconciliation hash.

### 6.2 Attachment-focused tests

Attempted:

```sh
/tmp/rev-ind-01-wp07-venv/bin/python -m pytest -q \
  tests/test_repair_plan_02_life03_intake_kill_switch.py \
  tests/test_attachment_batch_state_routing_f1_1a.py \
  tests/test_attachment_terminal_routing_remediation.py \
  tests/test_unsupported_attachment_rejection.py \
  tests/test_miniapp_attachment_download_mt2.py
```

Result: **NOT RUN** — `/tmp/rev-ind-01-wp07-venv/bin/python` does not exist. The host `python3` also
lacks `pytest`, `telegram`, `anyio`, and `httpx`. No dependency installation was performed because
this task prohibits dependency changes and no disposable verification container was available.

This is an evidence limitation, not a test failure and not a pass.

### 6.3 Static verification

- `git diff --check`: exit **0**.
- No changes to `bot/config.py`, `bot/handlers.py`, `bot/db.py`, `bot/attachments.py`,
  `bot/web/services.py`, Mini App files, or the decision-relevant tests.
- Package approval section: **no checked boxes** (`grep '^- \[x\]'` returned none).
- No production calls, credentials, fetch/pull, staging, commit, push, PR, merge, deployment, or
  Autopush.

---

## 7. Created files and SHA-256

### 7.1 Decision package

**Path:** `docs/reviews/OHB2-OD01-OD03-OWNER-DECISION-PACKAGE.md`

**SHA-256:**

`49a10e17d1bfe7316e3e49a26ade0d4044b7db2fa3aa3905a7e52bc78342b212`

### 7.2 Task report

**Path:** `docs/reviews/OHB2-OD01-OD03-OWNER-DECISION-ANALYSIS-REPORT.md`

**Final SHA-256:** reported in the task final response after the final write. It is not embedded here
because embedding it would change the file hash.

---

## 8. Git safety status

The pre-existing working tree was preserved. No pre-existing tracked, untracked, or ignored file was
deleted, reset, cleaned, staged, committed, or overwritten. The only additions from this task are the
two documents above.

Exact final `git status --short --branch`:

```text
## main...origin/main
 M .agent/PROGRESS.md
 M README.md
 M bot/app.py
 M docs/ZERO_TOUCH_STARTUP.md
 M docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md
 M docs/audits/OHB2-WP07-FINAL-STABILIZATION-AUDIT.md
 M docs/audits/OHB2-WP07-NEW-DEF03-S3-DELIVERY-AND-ACCEPTANCE-RECONCILIATION.md
 M tests/test_doc_code_parity.py
 M tests/test_start_script.py
 M tests/test_u04_concurrency.py
?? docs/audits/OHB2-POLLER-CONCURRENCY-OPTION-A-IMPLEMENTATION-REPORT.md
?? docs/audits/OHB2-POLLER-CONCURRENCY-OPTION-A-INDEPENDENT-REVIEW-HANDOFF.md
?? docs/audits/OHB2-POLLER-CONCURRENCY-STRUCTURAL-SAFETY-AUDIT-REPORT.md
?? docs/audits/OHB2-WP08-OWNER-ACCEPTANCE-RECORD.md
?? docs/reviews/OHB2-MASTER-BACKLOG-RECONCILIATION-AND-NEXT-TASK-REPORT.md
?? docs/reviews/OHB2-OD01-OD03-OWNER-DECISION-ANALYSIS-REPORT.md
?? docs/reviews/OHB2-OD01-OD03-OWNER-DECISION-PACKAGE.md
?? docs/reviews/OHB2-WP07-NAV-OWNER-DECISION-PACKAGE.md
?? docs/reviews/OHB2-WP08-OWNER-ACCEPTANCE-RECORD-REPORT.md
?? docs/reviews/OHB2-WP08-REMAINING-SCOPE-RECONCILIATION-REPORT.md
?? docs/reviews/OHB2-WP08-SCOPE-RECOVERY-AND-STATUS-AUDIT-REPORT.md
?? docs/reviews/OHB2-WP08-UNBLOCKED-PARITY-HARDENING-IMPLEMENTATION-REPORT.md
?? docs/reviews/OHB2-WP09-COMPATIBILITY-AND-ENVIRONMENT-VERIFICATION-REPORT.md
?? docs/reviews/REV-IND-01-WP-07-INDEPENDENT-REVIEW-REPORT.md
```

No `git add .` or `git add -A` was used. No destructive Git operation was used.

---

## 9. Limitations

1. **No behavioral test execution.** The host lacks project test dependencies and no disposable
   verification environment was available.
2. **No independent review.** No separate reviewer session is available; this package is an
   evidence-based analysis, not an independent review.
3. **No owner decision.** The recommendation is not an approval. The owner must select options in the
   package.
4. **Implementation design remains open.** The exact terminal-clearance persistence mechanism and
   command name must be designed and reviewed after owner approval.
5. **Existing batches remain unresolved.** Neither decision cleans or repairs pre-existing SQLite
   batches; WP-01 inventory and explicit recovery authorization are still required.

---

## 10. Explicit non-actions

- No application code changed.
- No tests changed.
- No dependencies/lockfiles changed.
- No runtime configuration changed.
- No CI changed.
- No Mini App or protected files changed.
- No historical report or previous owner decision rewritten.
- No `.agent/PROGRESS.md` owner-acceptance implication added.
- No WP-01 implementation started.
- No staging, commit, push, PR, merge, deployment, release, or Autopush.
- No fetch/pull.
- No production calls or real credentials.
- No claim of independent review.
