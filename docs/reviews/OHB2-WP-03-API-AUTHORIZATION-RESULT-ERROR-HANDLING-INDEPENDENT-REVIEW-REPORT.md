# OHB2 — `WP-03` API Authorization, Result-Error Handling & Independent Review — Report

- **Task ID (task title):** `OHB2-WP-03-API-AUTHORIZATION-RESULT-ERROR-HANDLING-AND-INDEPENDENT-REVIEW`.
- **Type:** verification + coverage hardening of an existing (uncommitted) work package, then an independent review. **Documentation/test-only additions in this session.**
- **Owner Decision Status:** `PENDING_OWNER_DECISION — NO OD-01..OD-05 OPTION SELECTED, RECOMMENDED, OR IMPLEMENTED`.
- **Authoritative spec:** `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md` §`WP-03` (included defects `DEF-003`, `DEF-004`, `NEW-DEF-04`).
- **Repository / branch / HEAD:** `TM-AEM/OpenHandBot`, `main`, `33530cad02f37755da47e7eedac57764a354a75b` (unchanged by this session).
- **Prepared by:** an AI agent (OpenHands) on behalf of the repository owner.

> **Task-identity reconciliation (read first).** The prompt's structured header names `OHB2-OWNER-DECISIONS-BRIEFING-REVIEW-FIXES` (documentation-only briefing corrections) and its §4 requirements are the seven `REV-OD-01..07` fixes. A second, unrelated block was appended describing `OHB2-WP-03-...`. Per `AGENTS.md` (report honestly; verified truth over looking done) and the **repeated, established rule for this header** (recorded in `.openhands/memory/2026-11-18.md`): **the header task is already complete at HEAD `33530ca`** — the briefing is corrected, all seven `REV-OD-*` findings are resolved, and its report is committed. Therefore this session executed the **appended** task (`WP-03`), which is the only outstanding work. The header task was **not** re-executed (doing so would risk clobbering committed work). See §9 for the full evidence.

---

## 1. Executive summary

`WP-03` was already implemented in the working tree (uncommitted, from a prior session; 22 `OHB2-WP-03` source markers; `tests/test_wp03_handler_outcome_and_send_guards.py`). This session **verified** that implementation against the authoritative baseline and primary source, **mutation-tested** it, found **three genuine fail-closed coverage gaps** (untested outcome branches inside `WP-03`-owned handlers), and **closed them with three discriminating regression tests**. No production code was changed.

| Layer | Result |
|---|---|
| `WP-03` implementation (5 auth callers + `delete_conversation_confirm`, `reposearch` `4xx`, `out_id==0`/`job_id==0`, `outbox_mark_sent` CAS, raw-send guards, `_safe_send_html`) | **PRESENT & CORRECT** (verified against source) |
| Existing `WP-03` regression suite | **51 passed** |
| **Gaps closed this session** | **3** (see §5) — new tests, mutation-proven discriminating |
| Full suite | **3281 → 3284 passed** (0 failed) |
| `node --test tests/frontend/*.test.js` | **280 pass / 0 fail** |
| `pyflakes` | **0** |
| `bandit -lll -s B613` | **High 0** |
| `pip-audit` | **NOT_RUN** (needs network; unavailable in this environment) |
| Independent review | **`PASS_WITH_NOTES`** (technical) / **`INDEPENDENCE_NOT_ESTABLISHED`** (agent) / **`SNAPSHOT_INTEGRITY_ESTABLISHED`** |

**Owner-decision preservation:** zero `OD-01`–`OD-05` option was selected, recommended, or implemented. `WP-04` Part 2 / ADR §28.4 (`OD-02`) remains **not implemented** and **blocked on owner decision**.

---

## 2. Environment and evidence base

- Tests/lint/scan run **only inside pre-existing, owner-sanctioned containers** (host Python has no `pytest`/`telegram`; deps live in the containers):
  - `ohb2-verify` (bind-mounts the repo at `/work`; `ptb 22.8`, `pytest 9.0.3`) — primary gate.
  - `ohb2-wp03-review` (fresh `ohb2-review-base:latest`, `--network none`, `--read-only`, **no host repo mount**, frozen tarball snapshot) — independent review.
- No dependency install, no environment change, no network egress, no live/external service contact, no secret read/print.

---

## 3. `WP-03` scope (baseline) and implementation mapping

Baseline `WP-03` (`docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md`) requires:

1. Close `outcome=None` gaps: `outbox_mark_sent` (CAS race), `consume_one_shot_awaiting == False`, `out_id == 0`, `job_id == 0`.
2. In `handle_text` `reposearch`: do **not** consume state when `_show_repos` returns on a **4xx**; the **5xx/429/no-code** operational failure must still propagate.
3. Migrate the **5** legacy `_authorized_conversation` callers to `_authorized_conversation_status` + `_raise_if_operational_api_failure`, and inspect `status`/`auth_exc` in `delete_conversation_confirm` before `mark_explicitly_ignored`.
4. Align `send_reply_txt` / `export_conversation` failure outcomes (operational `FAILED_TRANSIENT` vs expected `4xx` ignore vs genuine unknown).
5. Guard `send_document` and all raw `bot.send_message` / `send_copyable` / `send_long` calls in `copy_reply` / `full_reply` / `send_reply_txt` — never mask an upstream `OperationalApiFailure` behind a swallowed Telegram send error.

**Verification of each (primary source, `bot/handlers.py`):**

| Requirement | Evidence | Status |
|---|---|---|
| 5 legacy callers migrated | `_authorized_conversation(` appears only at its **definition** (`L265`); every former caller now uses `_authorized_conversation_status(` (`L1108 open`, `1175 copy`, `1223 full`, `1278 txt`, `1365 watch`, `1440 delete_prompt`, `1476 delete_confirm`, `1532 status`, `1582 cost`, `1620 export`, `1777 reply`) | ✅ |
| `delete_conversation_confirm` inspects `status`/`auth_exc` | `L1483-1490`: operational `UPSTREAM_ERROR` ⇒ `mark_operational_failure(...)`; expected rejection ⇒ `mark_explicitly_ignored` | ✅ |
| `reposearch` `4xx` preserves state | `_show_repos` (`L2653`) returns `bool`; `handle_text` consumes the one-shot **only** when it returns `True` (`L2489-2500`) | ✅ |
| `_send_prompt` / `_start_new_chat` `==0` paths | `L2578-2587` / `L2765-2774`: `outcome=None` closed with `mark_explicitly_ignored`, guarded against overwriting a concurrent winner's durable outcome | ✅ |
| `outbox_mark_sent` CAS race | `L3027-3034`: `status_now == final` ⇒ `mark_explicitly_ignored` | ✅ |
| Raw sends guarded | `_safe_send_html` (`L165`) wraps raw `send_message`; `copy_reply`/`full_reply` wrap `send_copyable`/`send_long`; `send_document` in `export_conversation`/`show_file` wrapped | ✅ |
| Operational-vs-display distinction | `_raise_if_operational_api_failure` raises **before** any ignore; Telegram delivery failure ⇒ `mark_display_failed` (`FAILED_TRANSIENT`) | ✅ |

`_safe_send_html` captures **only** `(TelegramError, asyncio.TimeoutError)` — it does **not** swallow `asyncio.CancelledError` or programming/DB errors (verified).

---

## 4. Mutation testing (non-vacuity)

Method: mutate a copy of the code, confirm the suite goes red, restore, confirm green. Performed in both the primary container (`ohb2-verify`, disposable copy) and the **independent** review container (`ohb2-wp03-review`).

| Mutation | Expected outcome | Observed (independent container) |
|---|---|---|
| `_show_repos` 4xx returns `True` (old behaviour) | red | **1 failed** |
| `delete_conversation_confirm` operational ⇒ ignore | red | **4 failed** |
| `copy_reply` display guard removed | red | **2 failed** |
| `send_reply_txt` exchange `ApiError` ⇒ ignore | red | **1 failed** |
| `export_conversation` `ApiError` ⇒ ignore | red | **1 failed** |
| `copy_reply` / `full_reply` **auth-site** propagation removed | red | **1 failed** each (via `test_stage2_high_ack_blocking_fix.py`) |
| `show_file` display guard removed | red | **1 failed** |
| `watch_conversation` operational ⇒ ignore | red | **4 failed** |
| **`send_reply_txt` oversized ⇒ ignore** (was **untested**) | red | **1 failed** *(new test)* |
| **`export_conversation` `ResponseTooLargeError` ⇒ no outcome** (was **untested**) | red | **1 failed** *(new test)* |
| **`delete_conversation_confirm` `STATUS_FAILED` ⇒ ignore** (was **untested**) | red | **1 failed** *(new test)* |

All mutations were **non-vacuous**. The restored `bot/handlers.py` hash equals the live tree exactly (`96325cf2…affb4f6a`).

---

## 5. Gaps found and closed (this session's only source change)

Three `WP-03`-owned handlers contain outcome branches that no test exercised, so a regression flipping them to an **ack-eligible** `explicitly_ignored` would have passed silently — a fail-closed risk (a failed operation could be acknowledged/dropped). All three branches are **pre-existing at HEAD** and were **touched by `WP-03`** (`send_reply_txt`/`export_conversation` are explicit `WP-03` sites; `delete_conversation_confirm` is an explicit `WP-03` site), so closing them is in scope.

| Gap | Correct behaviour | Risk if regressed | New discriminating test |
|---|---|---|---|
| `send_reply_txt` `TextDocumentTooLargeError` | `mark_failed_permanent` (`FAILED_PERMANENT`, **not** ack-eligible) | oversized `.txt` reply silently acknowledged | `test_send_reply_txt_oversized_records_permanent` |
| `export_conversation` `ResponseTooLargeError` | `mark_explicitly_ignored` (`EXPLICITLY_IGNORED`, ack-eligible) — the explicit terminal rejection must be recorded | export-limit rejection left `outcome=None` (blocks the boundary unnecessarily) or mislabelled | `test_export_response_too_large_records_ignored` |
| `delete_conversation_confirm` `STATUS_FAILED` | `mark_ambiguous_external` (`PARTIAL_OR_UNKNOWN`, **not** ack-eligible) | a confirmed remote-delete failure silently acknowledged | `test_delete_confirm_remote_failed_records_ambiguous` |

**Change:** `tests/test_wp03_handler_outcome_and_send_guards.py` — added 3 tests (+ import lines). No production code changed. `51 → 54` tests in that file.

---

## 6. Verification (real commands and results)

Executed in `ohb2-verify` (`/work` = repo):

```
python3 -m pytest -q tests/                       -> 3284 passed  (baseline 3281 + 3 new)
python3 -m pytest -q tests/test_wp03_handler_outcome_and_send_guards.py  -> 54 passed
node --test tests/frontend/*.test.js              -> # pass 280  # fail 0
python3 -m pyflakes bot/ automation/ tools/ main.py tests/  -> exit 0
python3 -m bandit -r bot/ automation/ tools/ main.py -lll -s B613  -> High: 0
```

Reproduced independently in `ohb2-wp03-review` (isolated, offline, snapshot 359/359 manifest OK):

```
sha256sum -c MANIFEST.sha256                      -> 359/359 OK
python3 -m pytest -q tests/                       -> 3284 passed
node --test tests/frontend/*.test.js              -> 280 pass / 0 fail
python3 -m pyflakes ...                           -> exit 0
python3 -m bandit ... -lll -s B613                -> High: 0
```

**Error count before → after:** `0 failed` → `0 failed` (tests 3281 → 3284).

---

## 7. Independent review

- **Agent independence: `INDEPENDENCE_NOT_ESTABLISHED`.** A genuinely separate reviewer agent/session cannot be provisioned in this environment: the only agent-server hosts **this** conversation, no alternate `switch_llm` profile / provider connection exists, and cloud delegation is out of scope (cost/credentials). A different container/prompt is **not** a different agent. Per the task's own rule and the prior-session precedent, this is reported honestly rather than dressed up as independent.
- **Maximum-rigor review performed anyway** in a **fresh, network-isolated, read-only container** (`ohb2-wp03-review`) built from `ohb2-review-base:latest` with **no host repo mount** and **no access** to the original repo or the conversation store (verified: distinct hostname; `/workspace/project/OpenHandBot` and `/var/openhands` absent; no project bind mounts).
- **Snapshot integrity: `SNAPSHOT_INTEGRITY_ESTABLISHED`** — tarball `sha256 21d93faa…b00aca1`; extracted manifest **359/359 OK**; restored `bot/handlers.py` hash equals the live tree.
- **Independent verdict:** **`PASS_WITH_NOTES`** — all `WP-03` acceptance criteria satisfied; every covered fix mutation-proven non-vacuous; the three gaps closed this session are themselves mutation-proven. Notes: (a) `pip-audit` not run (no network); (b) `WP-04` Part 2 / ADR §28.4 (`OD-02`) correctly **not** implemented.

---

## 8. Safety, scope, and preservation

- **Files changed this session:** exactly **one** — `tests/test_wp03_handler_outcome_and_send_guards.py` (test-only). Verified against a 363-hash pre-task inventory: the only differing source file is that test file (plus gitignored `.pytest_cache`).
- **Files created:** this report only. The temporary review snapshot lives **outside** the repo (`/workspace/ohb2-wp03-review-snapshot/`).
- **Preserved:** all pre-existing working-tree, untracked, ignored, and `.openhands/` content (the 38 pre-existing working-tree changes were not touched, staged, or removed).
- **No forbidden actions:** no commit, push, branch, PR, merge, deploy, or Autopush; no destructive Git; no dependency install or environment change; no live/external checks; no secrets read or printed; no `OD-01`–`OD-05` option selected; no Mini App / ADR / operational / deployment file modified; `WP-01`–`WP-10` **not** implemented.

---

## 9. Task-identity reconciliation (evidence)

| Artifact | Digest | Meaning |
|---|---|---|
| `docs/reviews/OHB2-OWNER-DECISIONS-BRIEFING-INDEPENDENT-REVIEW.md` | `be7c0e1d…afc0137f` | **exact match** with the prompt (independent-review report, unchanged) |
| `docs/audits/OHB2-OWNER-DECISIONS-BRIEFING.md` (on disk / HEAD) | `b6c02bae…1e101cd8` | the **corrected** briefing; the prompt's `8974a3b9…` equals `git show 57d82fd:…` (the **pre-correction** version) |
| `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md` | worktree `dccc28fd…d0d5a2656f`; **HEAD blob `e7b98175…f5709a6f`** (matches the prompt) | the prompt's hash is the committed blob; the worktree carries a *separate* task's pre-existing edits |

HEAD `33530ca` = *"docs: correct owner decisions briefing per independent review (REV-OD-01..07)"* — the header task's own commit; all seven `REV-OD-*` corrections are present in the committed briefing. **Conclusion:** the header task is complete; the appended `WP-03` task was executed. No file was overwritten or restored.

---

## 10. Not verified / not implemented / still broken

- **`pip-audit`** — **NOT_RUN** (requires network; unavailable in this environment). `WP-09` verification item.
- **`WP-04` Part 2 / ADR §28.4** (`/updates_status`, `/updates_skip`, `POISON_SKIPPED`) — **NOT IMPLEMENTED** (correctly gated on `OD-02`).
- **Agent independence** for the independent review — **NOT ESTABLISHED** (environment limitation; isolated-container review performed instead).
- No functional failure found in `WP-03`; all acceptance criteria satisfied.

---

## 11. Assumptions and decisions

1. Header vs appended task: header already complete at HEAD ⇒ executed the appended `WP-03` task (established, recorded rule; `AGENTS.md` honesty rule).
2. Closed only the three genuinely-uncovered branches that are inside `WP-03`-owned handlers; introduced **no** new behaviour and **no** scope creep.
3. Added tests to the **existing** `WP-03` test file rather than a new file (keeps `WP-03` evidence together).
4. Used pre-existing owner-sanctioned containers for all test/lint/scan execution; changed no dependency or environment.
5. Reported the independent review as `INDEPENDENCE_NOT_ESTABLISHED` rather than overstating it.

---

## 12. Branch and commits

- Branch `main`, HEAD `33530cad02f37755da47e7eedac57764a354a75b` — **unchanged**. No commit/push/PR this session.

---

## 13. Suggested next step

Owner obtains the outstanding decisions (`OD-01`…`OD-05`); then authorize and execute the gated follow-ons (`WP-04` Part 2 for `OD-02`, plus `WP-08`/`WP-09` documentation-and-verification sync). Optionally, commission a genuinely separate reviewer (outside this environment) for `WP-03` to satisfy the independence requirement.

---

*This report was created by an AI agent (OpenHands) on behalf of the repository owner.*
