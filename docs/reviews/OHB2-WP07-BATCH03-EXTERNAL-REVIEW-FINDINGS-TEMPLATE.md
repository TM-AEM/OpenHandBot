# OHB2 — WP-07 Batch-03 External Review — Findings Template

**Reviewer:** ____________________  **Date:** __________
**Package:** `/workspace/review-packages/OHB2-WP07-BATCH03-EXTERNAL-REVIEW-HANDOFF-20261119`
**Snapshot HEAD:** `52e7789cc8cc97a7f7c09c9592226ab117db99a2` (working tree uncommitted on top)

> Copy one block per finding. Do not merge unrelated findings.
> Every finding needs **exact evidence** — a file path, function name and line number — plus a
> reproduction. "Looks wrong" is not a finding.

---

## Severity scale

| Severity | Meaning |
|---|---|
| `CRITICAL` | Data loss, corruption, security breach, or silent wrong result in normal operation. |
| `HIGH` | Defect reachable in normal operation; blocks acceptance. |
| `MEDIUM` | Defect in a plausible edge case; needs a fix or an explicit accepted risk. |
| `LOW` | Minor correctness/robustness issue or maintainability risk. |
| `INFO` | Observation; no action required. |

---

## Finding F-___

**Title:**
**Severity:** `CRITICAL | HIGH | MEDIUM | LOW | INFO`
**Area:** `DEF-011-B | DEF-011-A | DEF-011-C | DEF-006 | DEF-013 | NEW-DEF-03 | NAV-0x | F-1 | WP-05 | packaging | other`
**File / function / line:**
**Classification:** `CONFIRMED DEFECT | SCOPE DEVIATION | TEST GAP | DOC DRIFT | OBSERVATION`

**What is wrong (factual, no speculation):**

**Why it matters (user/system impact):**

**Evidence (exact snippet or command output):**

```
<paste exact code lines / command output>
```

**Reproduction steps:**

1.
2.
3.

**Expected vs actual:**

**Recommended correction:**

**Blocks owner acceptance?** `YES | NO`

---

## Scope-deviation findings (pre-populated prompts — confirm or refute)

### SD-1 — DEF-011 sub-defect A (quota reservation ledger) not implemented

- Baseline §WP-07 constraint 2 requires an in-process reservation ledger.
- It is **absent**. `D-12` (aggregate defaults `None`) and `OD-04` (no concurrency) are the stated
  reasons.
- **Your position:** `ACCEPTABLE DEVIATION` / `MUST REOPEN` / `MUST REOPEN AFTER OD-04` —
  justify in one paragraph.

### SD-2 — DEF-011 sub-defect C (UX copy) out of scope

- `ATTACHMENT_ACCEPTED_TEXT` (`bot/handlers.py:1878`) still omits the local-only disclosure.
- Owner is **WP-01**, blocked on `OD-01`/`OD-03`.
- **Confirm** this is correctly excluded from WP-07 and that DEF-011 is therefore **not closed**.

### SD-3 — NAV-01..06 unaccepted

- Implemented and tested, but **no acceptance record**.
- **Confirm** they are `NEW-DEF-03` sub-scope, not independent baseline findings.
- **State** which owner option you would recommend: `A′-1 Accept` / `A′-2 Accept with conditions` /
  `A′-3 Defer` / `A′-4 Reject`.

### SD-4 — DEF-006 / OD-04

- Comment-only path is committed; concurrency is not.
- **Confirm** `OD-04` has no owner decision and that the code is sequential at runtime.

### SD-5 — Stale acceptance-proposal text

- `docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md` still says DEF-011 is entirely
  unimplemented (it predates the work).
- **Confirm** this is documentation drift, not a code defect, and that it must not be edited
  retroactively.

---

## DEF-011-B deep-dive checklist (record your evidence per item)

| # | Question | Evidence | Verdict |
|---|---|---|---|
| 1 | Do FS ops run off the event-loop thread (proven by execution)? | | |
| 2 | Does SQLite stay on the owning loop thread? | | |
| 3 | Were mixed DB/FS functions kept off the worker? | | |
| 4 | Is cancellation safe (no false `stored`, sweep reclaims)? | | |
| 5 | Is partial-file cleanup correct (no blind delete)? | | |
| 6 | Does error propagation stay fail-closed? | | |
| 7 | Does `anyio.Lock` preserve prior sequential admission? | | |
| 8 | Any quota ledger introduced? | | |
| 9 | Any schema change? | | |
| 10 | Any new worker/scheduler? | | |
| 11 | Any new dependency? | | |
| 12 | Synchronous API behaviour unchanged? | | |

---

## Independent execution log

| Command | My result | Author's claim | Match? |
|---|---|---|---|
| focused WP-07 suites | | 121 passed | |
| full `pytest -q` | | 3406 passed | |
| `pyflakes` | | exit 0 | |
| `bandit -lll -s B613` | | High 0 | |
| `node --test tests/frontend/*.test.js` | | 280 / 0 | |
| Python 3.11 | | UNVERIFIED | |
| mutation re-run (name: ______) | | non-vacuous | |

---

## Final verdict block

**Technical correctness:** `PASS | PASS_WITH_NOTES | FAIL`
**Scope compliance:** `PASS | PASS_WITH_NOTES | FAIL`
**Test reproducibility:** `REPRODUCED | PARTIAL | NOT_REPRODUCED`
**Architecture compliance:** `PASS | FAIL`
**Owner-acceptance readiness:** `READY | NOT_READY | BLOCKED`
**Independent-review status:** `COMPLETED | INDEPENDENCE_NOT_ESTABLISHED`

**Overall verdict:** `PASS | PASS_WITH_NOTES | FAIL | BLOCKED`

**Justification (required):**

**Findings summary:** `CRITICAL: _  HIGH: _  MEDIUM: _  LOW: _  INFO: _`

**Reviewer signature:** ____________________
