# OpenHandBot Plan 05 Closure Report — Independent Verification and Closure

- **Closure Task ID:** `OHB2-PLAN-15-OPERATIONAL-FAILURE-VISIBILITY-CLOSURE-01`
- **Parent Plan:** `OHB2-PLAN-15-OPERATIONAL-FAILURE-VISIBILITY`
- **Linked Execution Report (preserved unmodified):** `docs/reviews/OHB2-PLAN15-OPERATIONAL-FAILURE-VISIBILITY-REPORT.md`
- **Date:** 2026-11-16
- **Source Code Modified in This Closure Task:** None (verification & closure documentation only)

---

## 1. Phase 0 — Live Baseline & Environment

- **Workspace root:** `/app/applet`
- **Git availability:** `.git` directory is absent (`git status` → `fatal: not a git repository (or any of the parent directories): .git`). Commit identity, branch, HEAD, and git diff against the historical baseline cannot be established locally and were not fabricated. No git initialization or history mutation was performed.
- **Runtimes & disk space:**
  - `Python 3.10.12` (`/usr/bin/python3`)
  - `Node v22.23.2`
  - Disk space: `756G` available on `/` and `/tmp` (`1%` used)
- **Installed Python tooling & packaging:**
  - Standard library only (plus system `chardet`, `pkg_resources`, `lsb_release`).
  - `pip` and `ensurepip` are absent (`No module named pip`, `No module named ensurepip`); no virtualenv or third-party packages (`pytest`, `pyflakes`, `bandit`, `pip_audit`, `python-telegram-bot`, `httpx`, `python-dotenv`, `starlette`, `uvicorn`, `anyio`) are installed, making isolated installation via `pip` infeasible in this container without altering system packages.
- **Requirements, test, and CI configuration inspected:**
  - `requirements.txt`: pins `python-telegram-bot[all]==22.8`, `httpx==0.28.1`, `python-dotenv==1.2.4`, `starlette==1.3.1`, `uvicorn==0.34.0`, `anyio==4.16.0`.
  - `requirements-dev.txt`: adds `pytest==9.0.3`, `pytest-asyncio==1.3.0`, `pyflakes==4.0.3`, `pip-audit==2.10.1`, `bandit==1.9.4`.
  - `pytest.ini`: `asyncio_mode = auto`, `testpaths = tests`, `pythonpath = .`.
  - `.github/workflows/ci.yml`: runs Python 3.11 & 3.13 (`pyflakes bot/ automation/ tools/ main.py tests/`, `pip_audit -r requirements-dev.txt`, `bandit -r bot/ automation/ tools/ main.py -lll -s B613`, `pytest -q`) and Node 24 (`node --test tests/frontend/*.test.js`).
- **Live presence of the five reported files confirmed:**
  1. `bot/handlers.py`
  2. `bot/messages.py`
  3. `tests/test_plan05_status_cost_failure_visibility.py`
  4. `docs/reviews/OHB2-PLAN15-OPERATIONAL-FAILURE-VISIBILITY-REPORT.md`
  5. `.agent/PROGRESS.md`

---

## 2. Phase 1 — Independent Source Review

### 2.1 `bot/handlers.py` (`show_status`, `show_cost`)
- **Verified functions & lines:**
  - `show_status` (`lines 1345–1396`): wraps `await q.answer()` (`lines 1347–1350`) in `try ... except Exception as exc:` logging `log.warning("تعذّر الرد على الكولباك (%s)", type(exc).__name__)`.
  - `show_cost` (`lines 1399–1434`): identical `try ... except Exception as exc:` guard around `await q.answer()` (`lines 1401–1404`).
- **Checks verified:**
  - `BadRequest` / `TimedOut` on `q.answer()` (e.g., expired `callback_query` during redelivery or restart) logs only `type(exc).__name__` (no exception message/secrets) and allows `_allowed`, `_authorized_conversation_status`, `_safe_edit`, `_edit_or_send`, and outcome persistence (`mark_operational_failure` / `mark_display_failed` / `mark_explicitly_ignored`) to execute cleanly.
  - `asyncio.CancelledError` inherits from `BaseException` (not `Exception`), so it is never swallowed and propagates to `handle_processing_error` / `_classify_failure` (`PARTIAL_OR_UNKNOWN`, ack-ineligible).
  - No false success response is introduced; polling acknowledgment semantics remain untouched.

### 2.2 `bot/messages.py` (`state_label`, `format_cost`)
- **Verified functions & lines:**
  - `state_label` (`lines 56–61`): handles `state is None` (`STATE_LABELS[None]`), returns `"غير معروف"` when `not isinstance(state, str)` (preventing `TypeError` on unhashable `dict`/`list` and preventing raw `int`/`bool` return), and preserves `STATE_LABELS.get(state, state or "غير معروف")` for all string inputs.
  - `format_cost` (`lines 174–201`, guards at `lines 181–185`): returns `"مفيش بيانات تكلفة."` when `not isinstance(metrics, dict) or not metrics`, coerces `usage = raw_usage if isinstance(raw_usage, dict) else {}`, and preserves all valid cost/token formatting, `_finite_number` filtering, huge-int `OverflowError` fallback, and absence of currency symbols (`$`).
  - All other callers of `state_label` and `format_cost` across `bot/web/services.py`, `bot/keyboards.py`, `bot/watcher.py`, `bot/handlers.py`, and `bot/messages.py` were inspected and remain compatible.

### 2.3 `tests/test_plan05_status_cost_failure_visibility.py`
- **Verified coverage (`lines 1–191`):**
  - Imports and helper signatures (`OWNER_ID`, `DetailClient`, `FakeQuery`, `_cb_update`, `_ctx_with`, `_callback`, `_with_started_app`, `_patch_telegram`) verified against `tests/test_handlers.py`, `tests/test_duplicate_update_dispatch.py`, `tests/test_stage2_custom_polling.py`, and `tests/test_one_shot_awaiting_atomicity.py`.
  - No production Telegram API calls or real credentials (`_patch_telegram` intercepts `Bot.send_message`, `Bot.edit_message_text`, `Bot.answer_callback_query`, `Bot.set_my_commands`, `Bot.set_chat_menu_button`; local SQLite under `tmp_path`).
  - Covers `q.answer()` `BadRequest`/`TimedOut` continuation + secret-redacted warning log, `CancelledError` propagation, E2E `TelegramPoller` redelivery recovery after `503` + expired `answerCallbackQuery`, and malformed `metrics` / `accumulated_token_usage` / `execution_status` at unit and handler levels.
  - Verified that reintroducing D1 (unguarded `q.answer()`) or D2 (unguarded `STATE_LABELS.get` / `metrics.get`) regressions would fail the checks.
  - Minor non-blocking note: direct unit tests using `_ctx_with(tmp_path, ...)` follow `tests/test_handlers.py` style without calling `db.close()`, which is harmless on `tmp_path` cleanup.

### 2.4 Documentation Accuracy Check
- `docs/reviews/OHB2-PLAN15-OPERATIONAL-FAILURE-VISIBILITY-REPORT.md` matches actual code, verified test/blocker outcomes, and `.agent/PROGRESS.md` historical entries.
- Three minor line-number offsets were noted in §4 of that prior report (left unmodified as historical evidence):
  - `bot/handlers.py`: `show_cost` `q.answer()` guard is at `lines 1401–1404` (prior report wrote `1397–1400`) and `_edit_or_send` is at `line 1426` (prior report wrote `1423`).
  - `bot/messages.py`: `format_cost` guards are at `lines 181–185` (prior report wrote `176–181`).

---

## 3. Phase 2 — Test, Quality, and Security Execution Ledger

| Check | Exact Command | Exit Code | Result |
|---|---|---|---|
| Python bytecode compile | `python3 -m compileall -q bot automation tools main.py tests` | `0` | **PASS** (`COMPILEALL_EXIT=0`) |
| Python AST parse | `ast.parse` across all `165` `.py` files | `0` | **PASS** (`AST_OK:165`) |
| Unused-import AST check | `ast.walk` on `bot/handlers.py`, `bot/messages.py`, `tests/test_plan05_status_cost_failure_visibility.py` | `0` | **PASS** (`{}` unused imports) |
| Frontend test suite | `node --test tests/frontend/*.test.js` | `0` | **PASS** (`280 pass / 0 fail`) |
| Isolated stdlib behavioral check | Ephemeral `python3` stdlib run with in-memory `telegram`/`httpx` stubs | `0` | **PASS** (`INDEPENDENT_STDLIB_BEHAVIORAL_VERIFICATION_PASS:11_GROUPS` — supplementary only, **not** real `pytest`) |
| Python test suite | `python3 -m pytest -q` | `1` | **BLOCKED / UNVERIFIED** (`/usr/bin/python3: No module named pytest`) |
| Static check (`pyflakes`) | `python3 -m pyflakes bot/ automation/ tools/ main.py tests/` | `1` | **BLOCKED / UNVERIFIED** (`/usr/bin/python3: No module named pyflakes`) |
| SAST (`bandit`) | `python3 -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | `1` | **BLOCKED / UNVERIFIED** (`/usr/bin/python3: No module named bandit`) |
| Dependency SCA (`pip-audit`) | `python3 -m pip_audit -r requirements-dev.txt` | `1` | **BLOCKED / UNVERIFIED** (`/usr/bin/python3: No module named pip_audit`) |

*Note:* Focused `pytest` runs (`test_plan05_status_cost_failure_visibility.py`, `test_stage4_f1_status_cost_operational_ack.py`, `test_sw04_sw05_authz_upstream_and_delivery.py`, `test_stage2_custom_polling.py`) are all blocked by the missing `pytest`/`requirements-dev.txt` dependencies and absent `pip`/`ensurepip` in this container.

---

## 4. Phase 3 — Preserved Architecture & Safety Contracts

- **`concurrent_updates(True)`:** Preserved in `bot/app.py:86`.
- **Polling acknowledgment semantics:** Preserved in `bot/polling.py`, `bot/update_outcomes.py`, and `bot/db.py` (unmodified; `acknowledgment_boundary` still blocks head-of-line on `FAILED_TRANSIENT` / `FAILED_PERMANENT` / `PARTIAL_OR_UNKNOWN`; no `exactly-once` claim).
- **Outbox & worker mechanisms:** Preserved (`OutboxWorker`, `CreationWorker`, `CompletionWorker`, `Watcher`, `Notifier` in `bot/app.py` and `bot/outbox.py`); **0** new workers, schedulers, daemons, processes, databases, or state owners added.
- **No recursive failure-notification loop:** Preserved (`_edit_or_send` fallback `send_message` remains restricted strictly to `"too long"`).
- **Autopush & Mini App:** No autopush process running (`ps -ef` verified); `MINI_APP_ENABLED` defaults to `False` (`bot/config.py:262`).
- **`_edit_or_send(False)` when `conv is not None`:** Intentionally preserved unchanged (`show_status:1385–1391`, `show_cost:1426–1432`) — calls `mark_display_failed` (`FAILED_TRANSIENT`), leaves head-of-line blocked without fallback `send_message` or poison-skip, and remains tracked as an open **Owner Decision**.

---

## 5. Phase 4 & Phase 5 — Independent Review & OPS-02 (`SW-02`)

- **Independent Review:** `INDEPENDENT_REVIEW_NOT_AVAILABLE` (single-agent execution environment; source review above is closure inspection and is not claimed as a separate independent reviewer session).
- **OPS-02 (`SW-02`) Independent Re-Search:**
  - `grep -rnE "SW[-_ ]?0?2\b|sw[-_ ]?0?2\b" . --exclude-dir=__pycache__ --exclude-dir=.git --exclude-dir=node_modules` returned **0** matches across `bot/`, `tests/`, `docs/` (except Plan 05's own report), `automation/`, `tools/`, `src/`, `main.py`, and `README.md`.
  - Only self-referential audit notes exist in `.agent/PROGRESS.md` (`lines 56, 66, 71, 74, 134–141, 197–218, 1360, 1398, 1605, 1675, 1703–1721, 3053, 4146`), and neither `.git` nor `.openhands/memory` is present locally.
  - No speculative code was written for `SW-02`.

---

## 6. Final Closure Verdicts & Remaining Owner Decisions

- **OPS-01 Verdict:** **`PASS_WITH_NOTES`**
  - *Basis:* D1 and D2 source implementation and preserved contracts are independently verified via source review, `compileall`, AST checks (`165` files, `0` unused imports), `node --test` (`280/280`), and 11-group isolated stdlib behavioral tests. `PASS` is withheld strictly per verdict rules because `pytest`, `pyflakes`, `bandit`, `pip_audit`, local `.git` diff verification, and `INDEPENDENT_REVIEW_NOT_AVAILABLE` remain blocked/unavailable in this container.
- **OPS-02 Verdict:** **`UNTRACEABLE — SOURCE REQUIRED`**
- **Outstanding Items / Owner Decisions:**
  1. Run `pip install -r requirements-dev.txt` followed by `python -m pyflakes bot/ automation/ tools/ main.py tests/`, `python -m pip_audit -r requirements-dev.txt`, `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613`, and `python -m pytest -q` in CI (`GitHub Actions`) or a Python 3.11/3.13 environment, plus an independent review session.
  2. Owner decision on silent user UX when `_edit_or_send` returns `False` on `conv is not None` (`show_status`/`show_cost`) together with `ADR §28.4` poison-update policy.
  3. Supply original `SW-02` specification/handoff source if OPS-02 is ever to be reopened.
