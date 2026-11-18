# OHB2 WP-04 Part 1 — Implementation & Independent Review Report

**Task ID:** `OHB2-WP-04-PART-1-POLLING-NETWORK-ERROR-HANDLING-AND-INDEPENDENT-REVIEW`
**Baseline:** `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md` §`WP-04` (`DEF-002`)
**Repository:** `/workspace/project/OpenHandBot` (branch `main`, HEAD `33530ca`)
**Implementation outcome:** `DONE`
**Review outcome:** `INDEPENDENCE_NOT_ESTABLISHED` (isolated review: `PASS_WITH_NOTES`)

> Produced by an AI agent (OpenHands) on behalf of the repository owner. No owner decision is
> selected, recommended, or implemented. No commit, push, PR, merge, deploy, or Autopush.

---

## 1. Task identity and scope

The task header and the appended `USER_CONTEXT` refer to the **same** work: implement and
independently review **WP-04 Part 1** only. No conflict was found this session.

- **In scope (Part 1):** transient failure classification in `_classify_failure` / the scoped
  `OSError` rule (`DEF-002`); preserve sequential polling, the fail-closed acknowledgement
  boundary, poison-update safety, and cancellation propagation.
- **Out of scope / blocked:** Part 2 (`/updates_status`, `/updates_skip <update_id> confirm`,
  ADR §28.4) — **BLOCKED on `OD-02`**; no `OD-01..OD-05` option selected.

## 2. Baseline references and finding mappings

- Baseline §`WP-04` — `Included Defect IDs: DEF-002`; `Explicit Exclusions: NEVER implement
  automatic skipping … Do not weaken fail-closed ACK checks. Zero Mini App changes.`
- Baseline §`WP-04` constraint 1: known transient exceptions -> `FAILED_TRANSIENT`
  (`RetryAfter`, `TimedOut`, `NetworkError`, `asyncio.TimeoutError`, `httpx.TransportError`).
- Baseline §`WP-04` constraint 2 (Scoped `OSError`): socket/network errno transient; local
  disk/permission/structural `OSError` must remain `FAILED_PERMANENT` / surfaced.
- Baseline §F "Scoped `OSError` rule" and §G sequencing (`WP-02` -> `WP-03` -> `WP-04`).
- **Part 1 / Part 2 boundary:** baseline §F states the `OD-02` decision block —
  *"WP-04 Part 1 YES / Part 2 NO"*: transient classifier fixes may be implemented independently,
  but §28.4 skip commands **MUST NOT** be implemented without `OD-02`.

## 3. Initial repository state (pre-existing, not created this session)

- Branch `main`, HEAD `33530cad02f37755da47e7eedac57764a354a75b` (unchanged throughout).
- Working tree already carried an uncommitted remediation set from prior sessions: 18 tracked
  files modified, 16 untracked files (including `tests/test_wp04_transient_classification.py`).
- **WP-04 Part 1 was already implemented** (uncommitted) before this session:
  `_is_transient_operational_error` + `_TRANSIENT_OS_ERRNOS` in `bot/handlers.py`
  (`git show HEAD:bot/handlers.py` contains neither). The classifier delegates to the shared
  policy in `bot/update_outcomes.py`.
- **WP-03:** the reported implementation is present (`bot/handlers.py` carries `OHB2-WP-03`
  markers; `tests/test_wp03_*` present) and its independent-review report exists
  (`docs/reviews/OHB2-WP-03-…-INDEPENDENT-REVIEW-REPORT.md`, verdict `INDEPENDENCE_NOT_ESTABLISHED`).
  Per the task, WP-03 is **not** represented as independently reviewed or formally accepted.
- No prior `WP-04` implementation report existed.

## 4. Files modified and files added (this session)

| File | Change | Reason |
|---|---|---|
| `tests/test_wp04_transient_classification.py` | **modified** (untracked file): +1 discriminating test, +imports, docstring note | Close a genuine coverage gap (see §7). No production code changed. |
| `docs/reviews/OHB2-WP-04-PART-1-IMPLEMENTATION-AND-INDEPENDENT-REVIEW-REPORT.md` | **added** | This report. |

No other file was modified. The corrected baseline, the consolidation report, the owner-decisions
briefing, source code, configuration, ADRs, Mini App files, and deployment files are unchanged by
this session (verified: `OHB2-CORRECTED-REMEDIATION-BASELINE.md` = `dccc28fd…` and
`OHB2-REMEDIATION-BASELINE-CONSOLIDATION-REPORT.md` = `a29d6e13…`, identical to the pre-task
inventory).

## 5. Implementation details, mapped to authorized requirements

Part 1 was already present in the working tree; this session **verified** it against the baseline
(no production change was required or made).

1. **Known transient errors -> `FAILED_TRANSIENT`** — `bot/handlers.py::_is_transient_operational_error`:
   `RetryAfter` / `TimedOut` / `NetworkError` / `asyncio.TimeoutError` / `httpx.TransportError`.
   **MET.**
2. **`BadRequest` not transient** — checked **before** `NetworkError` (correct for PTB 22.8, where
   `BadRequest ⊂ NetworkError`). **MET.**
3. **Scoped `OSError`** — `ConnectionError` (⊃ reset/refused/aborted/broken-pipe) -> transient;
   otherwise `errno ∈ _TRANSIENT_OS_ERRNOS` (`EAGAIN`/`EWOULDBLOCK`/`EINTR`/`ECONNRESET`/
   `ECONNREFUSED`/`ECONNABORTED`/`ETIMEDOUT`/`EPIPE`/`EHOSTUNREACH`/`ENETUNREACH`); local disk /
   permission / structural errors -> `FAILED_PERMANENT`. **MET.**
4. **Fail-closed boundary** — `bot/db.py::commit_batch_outcomes` computes the boundary from
   `processed_updates` only (`_outcome_in_txn`); non-eligible outcomes are written to
   `update_failures` and cannot advance it. **MET.**
5. **Sequential polling** — `bot/polling.py::process_updates` loops `await dispatch_and_wait(update)`
   one update at a time. **MET** (and now regression-tested — §7).
6. **No auto-skip / no Part 2** — no `/updates_status`, `/updates_skip`, or `POISON_SKIPPED` in
   `bot/`. **MET.**
7. **Cancellation propagation** — `_classify_failure` maps `CancelledError` -> `PARTIAL_OR_UNKNOWN`
   before delegation; `_safe_send_html` catches only `(TelegramError, asyncio.TimeoutError)`.
   **MET.**

## 6. Explicitly excluded and blocked items

- **Part 2 (`/updates_status`, `/updates_skip`, ADR §28.4): NOT IMPLEMENTED — BLOCKED on `OD-02`.**
- `OD-01..OD-05`: **NOT selected, recommended, or implemented.**
- Mini App: **unchanged.** `WP-05`..`WP-10`: **not started.** No unrelated refactoring.
- No new classification or retry policy was invented.

## 7. Tests added or changed

Added **one discriminating regression test** to `tests/test_wp04_transient_classification.py`:

- `test_process_updates_dispatches_sequentially_not_concurrently` — asserts `max_in_flight == 1`
  and the strict order `start1,end1,start2,end2` for `process_updates`. It is **mutation-killed**:
  the `asyncio.gather` (concurrent-dispatch) mutation survives the pre-existing suite but fails
  this test. This enforces the explicit WP-04 Part 1 constraint "preserve sequential update
  processing; do not introduce concurrency" (which is also gated by `OD-04`).

No existing test was weakened or deleted. No test asserting only that an exception was raised was
used where the durable-state requirement is what matters (existing tests already assert
`update_outcome` / `get_acknowledgment_boundary` state).

## 8. Exact test commands and results

Run in the project verification container `ohb2-verify` (`/work` = repo), Python 3.13, PTB 22.8.

| Command | Result |
|---|---|
| `python3 -m pytest -q tests/test_wp04_transient_classification.py` | **26 passed** (was 25) |
| `python3 -m pytest -q tests/` (full) | **3285 passed, 0 failed**, 74 warnings (168.8s) |
| `node --test tests/frontend/*.test.js` | **280 pass / 0 fail** |
| `python3 -m pyflakes bot/ automation/ tools/ main.py tests/` | exit 0 |
| `python3 -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | High: **0** |

Baseline comparison: the prior session recorded the full suite at 3284 passed; after adding the
new test the count is 3285 and the failure count stays **0** (error count did not increase).

Checks **not run:** `pip-audit` (requires network; unavailable — **NOT RUN**), CI matrix Python
3.11 (local runtime is 3.13 only — **UNVERIFIED**). No environment or dependency change was made.

## 9. Mutation-test evidence and source-restoration verification

Mutations applied in a disposable copy (implementer) and independently in the isolated review
container. "Killed" = a test actually failed under the mutation.

| # | Mutation | Implementer (kill) | Independent (kill) |
|---|---|---|---|
| 1 | `BadRequest` classified transient | 3 fail | 3 fail |
| 2 | blanket `OSError` -> transient | 4 fail | 4 fail |
| 3 | `PermissionError` -> transient | 4 fail | 4 fail |
| 4 | `CancelledError` -> transient | 2 fail | 2 fail |
| 5 | `update_failures` advances boundary | 4 fail | 4 fail |
| 6 | concurrent dispatch (`asyncio.gather`) | **survived before §7; killed after** | 1 fail |
| 7 | `None` outcome -> `EXPLICITLY_IGNORED` | 2 fail | 2 fail |
| 8 | failure outcomes added to `_ACK_ELIGIBLE` | 96 fail | 96 fail |

**Restoration:** after mutations the four touched source files were restored and verified against
the manifest — `bot/handlers.py`, `bot/db.py`, `bot/polling.py`, `bot/update_outcomes.py` all
`OK` (4/4). The live working tree was never mutated. This is a targeted sample, **not**
comprehensive mutation coverage.

## 10. Independent-review status and evidence

- **Outcome: `INDEPENDENCE_NOT_ESTABLISHED`.**
- A **separate, isolated** execution environment was used: container `ohb2-wp04-review`
  (`ohb2-review-base:latest`, `--network none --read-only`, hostname `4d9c7ccfa56e`). Verified no
  host repo mount, no `/var/openhands`, no conversation store.
- **However**, the reviewer runs the same underlying model/harness as the implementer; it is not a
  different LLM session with an independent, accountable reviewer role. Per the task, a separate
  container alone does not prove reviewer independence, and a different prompt/agent identity in
  the same session is not sufficient. Therefore independence is **not** established.
- The isolated review is still reported as a rigorous, read-only review: `PASS_WITH_NOTES`.

**Frozen snapshot:** `/workspace/ohb2-wp04-review-snapshot/`
- `tree.tar.gz` sha256 `a1bc754950d07bc298f5c47895f7fb7f7761a76dc8aab94bdcd4f3016ad60cee`
- `MANIFEST.sha256` — **360 files**; `sha256sum -c` => **360/360 OK, 0 mismatches**.
- Package also contains the implementation diff (`wp04-part1-handlers.diff`), the WP-04 test file,
  baseline §WP-04, the prior execution report, and review instructions.

**Independent reproduction inside the container:** full suite **3285 passed**; pyflakes exit 0;
bandit High 0; node 280/0; all 8 mutations killed; source restored exactly (4/4 manifest match);
independent source read confirmed classifier, sequential polling, boundary invariant, and the
absence of Part 2.

## 11. Review findings and their resolution status

| ID | Severity | Location | Evidence | Impact | Blocks Part 1? | Correction | Status |
|---|---|---|---|---|---|---|---|
| F-1 | Low | `tests/test_wp04_transient_classification.py` (missing coverage) | `asyncio.gather` mutation survived the pre-existing suite | Sequential-processing invariant was untested | No | Added the discriminating test (§7) | **RESOLVED** |
| F-2 | Info | `bot/handlers.py::_TRANSIENT_OS_ERRNOS` | includes `EHOSTUNREACH`/`ENETUNREACH` beyond the baseline's illustrative list | Both are network-transient; consistent with the rule's intent | No | None needed | Accepted |
| F-3 | Process | review method | isolation confirmed; agent identity not separate | Independence cannot be claimed | No | Report as `INDEPENDENCE_NOT_ESTABLISHED` | Accepted |

No blocking findings. The single actionable finding (F-1) was fixed within the authorized Part 1
scope, and a **new** frozen snapshot (the one in §10) was produced for the review of the corrected
implementation — no obsolete review was reused as approval.

## 12. Security checks performed and checks not run

- **Performed:** `pyflakes` (exit 0), `bandit -lll -s B613` (High: 0). No secrets were read,
  printed, or exposed. No production system or credential was accessed. No dependency installed;
  no environment change.
- **Not run:** `pip-audit` (network required) — **NOT RUN**; CI Python 3.11 matrix — **UNVERIFIED**
  locally. These are stated as not-run rather than passed.

## 13. Remaining risks, limitations, and owner decisions required

- **`OD-02` (required):** Part 2 (`/updates_status`, `/updates_skip <update_id> confirm`, ADR §28.4)
  remains unimplemented; `FAILED_PERMANENT` poison updates still halt head-of-line polling until
  manual DB intervention or Telegram's 24h expiry.
- **No exactly-once claim:** this work does **not** claim exactly-once Telegram processing or
  SQLite/Telegram atomicity (at-most-once + idempotent redelivery only).
- **No owner acceptance:** only the owner can provide it; none is claimed.
- **Independence:** agent-identity independence was not established.
- **Mutation coverage:** a targeted sample, not comprehensive.

## 14. Final Git state

- **HEAD:** `33530cad02f37755da47e7eedac57764a354a75b` — **unchanged.**
- **Committed this session:** none.
- **Working tree — changed by this session:** `tests/test_wp04_transient_classification.py`
  (untracked; sha256 `656f96dc87f85a859851c39f41013be81b079b5f34058fa2becccf409391fee8`).
- **Added by this session:** this report file.
- **Pre-existing (not this session):** the 18 tracked modifications and 15 other untracked files
  already present at task start (WP-02/WP-03/WP-05/WP-07 work, audit docs, other reports).
- **Ignored / agent state:** `.openhands/`, `.pytest_cache/`, `.agent/` preserved untouched.

---

### Outcome summary

- **Implementation: `DONE`** (Part 1 verified present and conformance-proven; one coverage gap
  closed with a mutation-killed test; full suite 3285 passed / 0 failed).
- **Independent review: `INDEPENDENCE_NOT_ESTABLISHED`** (isolated review `PASS_WITH_NOTES`).
- **Blocked:** WP-04 Part 2 — requires owner decision `OD-02`.
- **Next required owner action:** decide `OD-02` (ADR §28.4 poison-quarantine contract) before any
  Part 2 work; WP-04 Part 2 and all subsequent work packages remain stopped.
