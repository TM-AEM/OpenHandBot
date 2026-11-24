# OHB2 — WP03-AUD-01 Display Failure Repair

**Task ID:** `OHB2-WP03-AUD01-DISPLAY-FAILURE-REPAIR`
**Date:** 2026-11-23
**Mode:** implementation + regression tests + local verification
**Status:** **RESOLVED — IMPLEMENTATION AND TEST EVIDENCE**
**Scope:** WP-03 findings `WP03-AUD-01` and `WP03-AUD-02` only.

> This report does not claim independent review, owner acceptance, PASS, or WP-03 closure.

---

## 1. Baseline and repository state

### 1.1 Before edits

| Item | Value |
|---|---|
| Repository | `/workspace/project/OpenHandBot` |
| Branch | `main` |
| HEAD | `2d528633a86472a6a502d7dca5b69ae9f10359ab` |
| HEAD tree | `90b62951e53156ac55cffca2f471a0690f21b3d0` |
| Local `origin/main` | `2d528633a86472a6a502d7dca5b69ae9f10359ab` |
| Reference audit | `docs/reviews/OHB2-WP03-REVIEW-READINESS-AND-EVIDENCE-AUDIT-REPORT.md` |
| Reference audit SHA-256 | `7f570e6f105969c68c4efd0d0870fa4a32027149dc48072f3a2d6d2138a84746` |
| Reference audit current? | **Yes** — HEAD, tree, and audit hash matched at baseline |
| Staged changes | none |
| Pre-existing tracked changes | 13 modified files (A4-F5 attachment work) |
| Pre-existing untracked files | `tests/test_a4_f5_expiration_boundary.py`, `docs/reviews/OHB2-WP03-REVIEW-READINESS-AND-EVIDENCE-AUDIT-REPORT.md` |
| Ignored paths | `.openhands/`, `.pytest_cache/`, `__pycache__/`, etc. preserved |

The pre-existing `bot/handlers.py` change is an unrelated A4-F5 clock injection in
`_attachment_service`; it was left untouched. The WP-03 repair edits are in the auth/display
branches described below.

### 1.2 Contract inspected before editing

- `bot/update_outcomes.py`:
  - `EXPLICITLY_IGNORED` is in `_ACK_ELIGIBLE`.
  - `FAILED_TRANSIENT` is in `_INELIGIBLE`; `is_ack_eligible()` is fail-closed.
- `bot/db.py`:
  - `mark_update_outcome()` stores the durable outcome.
  - `is_update_acknowledgment_eligible()` uses `update_outcomes.is_ack_eligible()`.
- `bot/handlers.py`:
  - `mark_display_failed()` is the existing mechanism for a failed required Telegram display;
    it records `FAILED_TRANSIENT`.
  - `_safe_send_html()` catches only `(TelegramError, asyncio.TimeoutError)` and returns
    `False` on delivery failure.
  - `_display_conversation_view()` returns `False` when its edit/send fallback fails.
  - The affected paths are `copy_reply`, `full_reply`, `send_reply_txt`, and
    `_open_conversation_view` (used by `open_conversation` and `/chat`).

No new outcome class or architecture was introduced.

---

## 2. Root cause

`_safe_send_html()` and `_display_conversation_view()` correctly returned `False` on a Telegram
display failure, but several required-display branches discarded that result and continued to
`mark_explicitly_ignored()`. For expected 4xx rejections and no-reply results, this recorded
`EXPLICITLY_IGNORED` even though the user never received the required rejection/no-reply message.

Affected branches:

- `copy_reply`: auth rejection, exchange error, no-reply.
- `full_reply`: auth rejection, exchange error, no-reply.
- `send_reply_txt`: auth rejection, exchange error, no-reply.
- `_open_conversation_view`: auth rejection and exchange error (both callback and `/chat` command
  display paths).

The existing `mark_display_failed()` mechanism was already the correct contract for this condition;
the fix only makes the affected branches inspect the display result and use that mechanism.

---

## 3. Implementation changes

### 3.1 `bot/handlers.py`

Changed only the display-result handling in the affected branches:

- Auth rejection branches in `copy_reply`, `full_reply`, and `send_reply_txt`:
  - capture `displayed = await _safe_send_html(...)`;
  - preserve operational-failure propagation before any success/ignore decision;
  - if display failed, call `mark_display_failed(...)` and return;
  - if display succeeded, keep the existing `mark_explicitly_ignored()` behavior.
- Exchange-error branches in the same three handlers:
  - same pattern after `_raise_if_operational_api_failure()`; successful display still records
    `EXPLICITLY_IGNORED`, failed display records `FAILED_TRANSIENT`.
- No-reply branches in the same three handlers:
  - successful display still records `EXPLICITLY_IGNORED`;
  - failed display records `FAILED_TRANSIENT` via `mark_display_failed()`.
- `_open_conversation_view` auth-rejection branch:
  - capture the display result;
  - if failed, record `mark_display_failed()` and return before clearing routing state or recording
    an ignore;
  - successful display retains the existing terminal-rejection/ignore behavior.
- `_open_conversation_view` exchange-error branch:
  - same display-result handling;
  - successful display retains existing ignore/route-clear behavior;
  - failed display records `FAILED_TRANSIENT` and does not clear routing state.

Operational `5xx`/`429`/no-code failures still propagate through
`_raise_if_operational_api_failure()`; authorization and no-reply semantics are unchanged when the
display succeeds.

### 3.2 `tests/test_wp03_handler_outcome_and_send_guards.py`

Added 28 new handler-level regression cases (16 new test functions: 6 parameterized × 3 cases + 10 non-parameterized):

- Expected 4xx auth rejection:
  - success display → `EXPLICITLY_IGNORED`, ack-eligible.
  - failed display → `FAILED_TRANSIENT`, not ack-eligible.
- Expected 4xx exchange error:
  - success display → `EXPLICITLY_IGNORED`, ack-eligible.
  - failed display → `FAILED_TRANSIENT`, not ack-eligible.
- No-reply result:
  - success display → `EXPLICITLY_IGNORED`, ack-eligible.
  - failed display → `FAILED_TRANSIENT`, not ack-eligible.
- `_open_conversation_view` through `open_conversation` (callback):
  - auth rejection success/failure.
  - exchange error success/failure.
  - no-reply success/failure, including route activation only on success.
- `_open_conversation_view` through `/chat` (no callback):
  - auth rejection success/failure.
  - no-reply success/failure, including route activation only on success.

The three reply handlers are covered by a parameterized matrix for all three display-result
scenarios. Test doubles are deterministic and local: `_AuthClient`, `ExchangeClient`, `CQ`,
`_FailingEditQ`, `_FailingMessage`, `FailSendBot`, and `TimedOut`.

---

## 4. Finding resolution

| Finding | Severity | Status | Evidence |
|---|---|---|---|
| `WP03-AUD-01` — failed required display became `EXPLICITLY_IGNORED` | MEDIUM | **RESOLVED — IMPLEMENTATION AND TEST EVIDENCE** | All affected branches now check the display result and use `mark_display_failed()` on failure. Targeted tests prove `FAILED_TRANSIENT` / not ack-eligible on failed display, and `EXPLICITLY_IGNORED` / ack-eligible on successful display. |
| `WP03-AUD-02` — missing handler-level regression coverage | LOW | **RESOLVED — IMPLEMENTATION AND TEST EVIDENCE** | 28 new regression cases cover expected 4xx, exchange error, and no-reply outcomes with both successful and failed display across all four affected handler paths. |

No finding is reported as `PARTIALLY RESOLVED`, `NOT RESOLVED`, or `BLOCKED`.

---

## 5. Regression behavior proven

| Test group | Successful display | Failed display |
|---|---|---|
| `copy_reply` / `full_reply` / `send_reply_txt` auth 4xx | `EXPLICITLY_IGNORED`, eligible `True` | `FAILED_TRANSIENT`, eligible `False` |
| Same handlers, exchange 4xx | `EXPLICITLY_IGNORED`, eligible `True` | `FAILED_TRANSIENT`, eligible `False` |
| Same handlers, no reply | `EXPLICITLY_IGNORED`, eligible `True` | `FAILED_TRANSIENT`, eligible `False` |
| `open_conversation` auth 4xx | `EXPLICITLY_IGNORED`, eligible `True` | `FAILED_TRANSIENT`, eligible `False` |
| `open_conversation` exchange 4xx | `EXPLICITLY_IGNORED`, eligible `True` | `FAILED_TRANSIENT`, eligible `False` |
| `open_conversation` no reply | `EXPLICITLY_IGNORED`, eligible `True`; route activated | `FAILED_TRANSIENT`, eligible `False`; no route |
| `/chat` auth 4xx | `EXPLICITLY_IGNORED`, eligible `True` | `FAILED_TRANSIENT`, eligible `False` |
| `/chat` no reply | `EXPLICITLY_IGNORED`, eligible `True`; route activated | `FAILED_TRANSIENT`, eligible `False`; no route |

**Discriminating check:** the new tests were run against a clean `git archive HEAD` copy with only
the updated test file copied in. The pre-fix code produced **12 failed / 70 passed**; the repaired
code produces **82 passed**. This proves the failure-display tests are non-vacuous.

---

## 6. Verification

### 6.1 Environment

| Item | Value |
|---|---|
| Python | 3.13.15 |
| Python 3.11 | **NOT AVAILABLE** locally |
| `python-telegram-bot` | 22.8 |
| pytest | 9.0.3 |
| Node | v24.22.2 |
| Virtualenv | `/tmp/ohb2-wp03-repair-venv` (fresh install from `requirements-dev.txt`) |
| Test cache | `/tmp/ohb2-wp03-repair-pycache` (outside repository) |

### 6.2 Commands and results

| Command | Result | Exit |
|---|---|---|
| `pytest -q tests/test_wp03_handler_outcome_and_send_guards.py` | **82 passed** | 0 |
| `pytest -q tests/test_stage4_f1_status_cost_operational_ack.py tests/test_manual_polling_handler_outcome_coverage.py tests/test_sw07_api_handler_failure_propagation.py tests/test_reply_txt_file_button.py tests/test_conversation_deletion.py` | **192 passed** | 0 |
| `pytest -q` (full suite) | **3823 passed, 0 failed, 74 warnings** | 0 |
| `node --test tests/frontend/*.test.js` | **280 pass, 0 fail** | 0 |
| `python -m pyflakes bot/ automation/ tools/ main.py tests/` | no findings | 0 |
| `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | **High 0**; Low 5 / Medium 19 | 0 |
| `python -m pip_audit -r requirements-dev.txt` | **No known vulnerabilities found** | 0 |
| `python -m compileall -q bot automation tools main.py tests` | no errors | 0 |
| `git diff --check` | clean | 0 |
| Pre-fix negative control with new tests | **12 failed / 70 passed** | 1 |

Full-suite baseline before this repair was **3795 passed**; after the 28 new cases it is
**3823 passed** (+28). No previously passing test fails.

### 6.3 Limitations

- **Python 3.11 was not run**; only Python 3.13.15 was available. This report does not claim 3.11
  compatibility.
- **GitHub Actions was not run or queried**; current CI success is **NOT VERIFIED** here.
- No production Telegram/OpenHands requests, real credentials, or live services were used.

---

## 7. Remaining risks and unverified items

1. The repair relies on the existing `mark_display_failed()` contract; no new outcome class was added.
2. Operational `5xx`/`429`/no-code behavior was intentionally left propagating before the display
   result decision; only expected 4xx/no-reply branches were changed.
3. The `_open_conversation_view` `/chat` path is covered with a deterministic message fake; no real
   Telegram network behavior was tested.
4. Python 3.11 and GitHub Actions remain unverified in this environment.
5. This repair does not constitute independent review, owner acceptance, or WP-03 closure.

---

## 8. Changed files

### 8.1 Changes made by this task

| File | Change |
|---|---|
| `bot/handlers.py` | WP-03 display-result handling in `copy_reply`, `full_reply`, `send_reply_txt`, and `_open_conversation_view`; `mark_display_failed()` used for failed required displays. The file also contains a pre-existing A4-F5 clock line that this task did not author. |
| `tests/test_wp03_handler_outcome_and_send_guards.py` | Added 28 regression cases (16 test functions: 6 parameterized × 3 cases + 10 non-parameterized) covering successful and failed display for expected 4xx, exchange error, and no-reply across all affected paths. |
| `docs/reviews/OHB2-WP03-AUD01-DISPLAY-FAILURE-REPAIR-REPORT.md` | This report. |

### 8.2 Pre-existing work preserved (not authored by this task)

- `.agent/PROGRESS.md`
- `bot/attachments.py`
- `bot/db.py`
- `tests/test_attachment_batch_lifecycle_a2.py`
- `tests/test_attachment_staging_a1.py`
- `tests/test_def011_a_option_b_limits.py`
- `tests/test_def011_fs_offload.py`
- `tests/test_f01_reaper_fs_offload.py`
- `tests/test_miniapp_attachment_download_mt2.py`
- `tests/test_repair_plan_01_resource_staging.py`
- `tests/test_repair_plan_02_life01_f2_race.py`
- `tests/test_repair_plan_02_life02_crash_recovery.py`
- `tests/test_a4_f5_expiration_boundary.py` (untracked)
- `docs/reviews/OHB2-WP03-REVIEW-READINESS-AND-EVIDENCE-AUDIT-REPORT.md` (untracked; prior audit)
- ignored `.openhands/`, caches, and agent state

No Mini App file, `bot/web/` file, dependency, migration, ADR, or historical report was modified.

---

## 9. Final repository state

| Item | Value |
|---|---|
| Branch | `main` |
| Final HEAD | `2d528633a86472a6a502d7dca5b69ae9f10359ab` (unchanged) |
| Final tree | `90b62951e53156ac55cffca2f471a0690f21b3d0` (unchanged) |
| Local `origin/main` | `2d528633a86472a6a502d7dca5b69ae9f10359ab` |
| Staged | none |
| Uncommitted | `bot/handlers.py`, `tests/test_wp03_handler_outcome_and_send_guards.py`, this report, plus all pre-existing A4-F5/audit work |
| `bot/handlers.py` SHA-256 | `966d1d5ecac3b67eb02a516b153df87a5fa4fba79e5a51ae978cd27db402e568` |
| WP-03 test file SHA-256 | `b22e5ebb95d78e1581163251410aabc827cfa1dccbaf151bd67cbdd47d906524` |
| WP-03 test file size | 740 lines, 43 test functions / **82 parametrized cases** |

No commit, push, pull, fetch, branch creation/deletion, rebase, merge, PR, deployment, release, or
Autopush action occurred. No destructive Git operation was used.

---

## 10. Report integrity

**Report body SHA-256 (excluding this footer):** `a1b0c8a5a789a5a173dc7d5e432758f8bb0d40ba167a3d5b13aa05b27563eece`
