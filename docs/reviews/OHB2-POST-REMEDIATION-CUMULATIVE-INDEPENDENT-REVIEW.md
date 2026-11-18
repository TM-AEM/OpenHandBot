# OHB2 Post-Remediation — Cumulative Independent Review

**Task ID:** `OHB2-POST-REMEDIATION-CUMULATIVE-INDEPENDENT-REVIEW`
**Mode:** READ-ONLY, genuinely independent technical review
**Repository:** `TM-AEM/OpenHandBot`
**Branch / HEAD:** `main` @ `33530cad02f37755da47e7eedac57764a354a75b`
**Date:** 2026-11-18
**Owner Decision Status:** `PENDING_OWNER_DECISION — NO OPTION SELECTED, RECOMMENDED, OR IMPLEMENTED`

---

## 1. Task-identity reconciliation (recurring prompt concatenation)

This prompt contains **two** tasks spliced together (the recurring pattern recorded in project memory):

1. **Header / structured objective:** `OHB2-OWNER-DECISIONS-BRIEFING-REVIEW-FIXES` — a documentation-only task: apply seven `REV-OD-*` findings to `docs/audits/OHB2-OWNER-DECISIONS-BRIEFING.md`, then independently review.
2. **Appended `USER_CONTEXT`:** declares itself the *authoritative NEW task* `OHB2-POST-REMEDIATION-CUMULATIVE-INDEPENDENT-REVIEW` — a review-only task of the cumulative remediation in the working tree, explicitly noting that the header task "already DONE at HEAD `33530ca`".

**Resolution (verified, not assumed):**

- The header task is **already complete and committed** at HEAD `33530ca` ("docs: correct owner decisions briefing per independent review (REV-OD-01..07)"). The corrected briefing and the fixes report `docs/reviews/OHB2-OWNER-DECISIONS-BRIEFING-REVIEW-FIXES-REPORT.md` are both committed at that SHA.
- Therefore the header task's *work* is a no-op; its *verification* is folded into this review (§7).
- The appended `USER_CONTEXT` task (`OHB2-POST-REMEDIATION-CUMULATIVE-INDEPENDENT-REVIEW`) is performed as the primary deliverable.

Both are honoured: the header's corrections are re-verified (§7) and the review-only cumulative review is executed (§3–§6, §8). **No file was overwritten, restored, or committed.**

---

## 2. Baseline preservation & non-mutation proof

### 2.1 Git state (at session start)

- `.git` **is present** → Git state is **VERIFIED**.
- Branch: `main`; HEAD: `33530cad02f37755da47e7eedac57764a354a75b` (== `origin/main`).
- Working tree: **not clean** — pre-existing uncommitted remediation work from *other* sessions (23 modified tracked files, 9 untracked deliverables). None authored by this review.

### 2.2 Hash reconciliation (the prompt's expected hashes do not match on-disk — investigated, not "fixed")

| Artifact | Prompt-expected SHA-256 | On-disk (working tree) | Committed blob | Explanation |
|---|---|---|---|---|
| `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md` | `e7b98175…f5709a6f` | `dccc28fd…d0d5a2656f` | `e7b98175…f5709a6f` (**matches prompt**) | Working tree carries **pre-existing** uncommitted edits from a separate remediation task. The committed `HEAD` blob equals the prompt hash. |
| `docs/audits/OHB2-OWNER-DECISIONS-BRIEFING.md` | `8974a3b9…35599c45` | `b6c02bae…1e101cd8` | `b6c02bae…1e101cd8` | The prompt's "current" hash is the **pre-correction** parent `57d82fd`: `git show 57d82fd:… \| sha256sum` → `8974a3b991f2ed32a5547b8db85f3d6e40c0160ce683cfcb10d1ca6f35599c45`. The on-disk/HEAD file is the **corrected** version. |
| `docs/reviews/OHB2-OWNER-DECISIONS-BRIEFING-INDEPENDENT-REVIEW.md` | `be7c0e1d…afc0137f` | `be7c0e1d…afc0137f` | `be7c0e1d…afc0137f` | **EXACT MATCH.** |

**Conclusion:** the baseline's *committed* digest matches the prompt; the briefing "mismatch" is explained entirely by the header task having **already been applied and committed**. No file was overwritten or restored. This is reported (not silently ignored) per the "investigate and report the discrepancy" instruction.

### 2.3 Non-mutation proof (this review)

- `git status --porcelain` before == after: **23 ` M` + 9 `??`**, byte-identical set.
- The corrected briefing digest is unchanged by this session: `b6c02bae0f477f5c…`.
- This review created **no** repository file except this report; it modified **no** source, test, config, ADR, operational doc, Mini App file, or existing report.
- All mutation experiments were performed on **disposable copies outside the repository** (§3.2).

---

## 3. Independence of the review environment

### 3.1 Isolation (genuinely separate environment)

A fresh container was used so that the reviewer cannot mutate the reviewed artifact and so that the review does not share the authoring runtime:

| Property | Value |
|---|---|
| Container ID | `877e34fd1a24570dfe99dc2377f2f8aacc34131b27a6636cb42d5b676f387961` |
| Image | `ohb2-review-base:latest` (`430da7e6ce0d`) |
| Mounts | **only** `/workspace/ohb2-review-snapshot` → `/review` (`ro`) — the live workspace is **NOT** mounted |
| Network | `none` (disconnected) |
| `/workspace/project/OpenHandBot` visible inside? | **No** |
| `.git` visible inside? | **No** |

The review source tree is a frozen snapshot (`ohb2-snapshot.tar`, 8 284 160 bytes, 381 entries) taken from the live workspace. **Snapshot byte-identity was re-verified this session**: `bot/handlers.py` `96325cf2…`, `bot/app.py` `f28562f3…`, `bot/outbox.py` `48f9f713…`, `bot/db.py` `472fa573…`, `bot/watcher.py` `43a6d944…`, `bot/notifier.py` `9979a109…`, `bot/openhands_client.py` `734a34d1…`, `start.sh` `3e056806…`, `tests/test_doc_code_parity.py` `f83547d4…` — all equal between the tar, the container `/work`, and the live workspace.

**Verdict:** `INDEPENDENCE_ESTABLISHED` (separate filesystem, no live-workspace access, no network, frozen inputs).

### 3.2 Dependency-audit isolation note

`pip-audit` requires its advisory database over the network, so it was run in a **separate** fresh container (`docker run --rm`) that mounted **only** the frozen snapshot read-only — the live workspace was never mounted. Result: **"No known vulnerabilities found"**.

---

## 4. Full-gate reproduction (isolated container)

All gates reproduced on the frozen snapshot inside the isolated container:

| Gate | Command | Result |
|---|---|---|
| Python tests | `python3 -m pytest -q tests/` | **3272 passed, 0 failed** (74 warnings) |
| Frontend tests | `node --test tests/frontend/*.test.js` | **280 pass, 0 fail** |
| Lint | `python3 -m pyflakes bot/ automation/ tools/ main.py tests/` | exit `0` |
| SAST | `python3 -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | **High (severity): 0** (Medium 19, Low 5) |
| Dependency SCA | `python3 -m pip_audit -r requirements-dev.txt` | **No known vulnerabilities found** |

**Note (honest):** the historical "1 failed (`test_deploy_manifest`)" failure does **not** appear here. That failure is an environment artifact (the test spawns `python -c "import main"` with a stripped `HOME`, which breaks user-site package resolution); it passes in this container's configuration. No code defect.

---

## 5. Per-work-package code review

The cumulative remediation consists of uncommitted work for `WP-02`, `WP-03`, `WP-04` (Part 1), `WP-05`, `WP-06` (Part 1), `WP-07` (partial), and `WP-08` (partial). Each was reviewed against primary source and, where feasible, **mutation-tested** (revert the fix → confirm the suite goes red). A mutation that does **not** turn the suite red reveals a coverage gap and is reported as a finding.

### 5.1 `WP-02` — Telegram callback hardening (`DEF-005`, `NEW-DEF-01`)

- **Helpers:** `_safe_answer(q, text=None, *, show_alert=False)` and `_safe_edit_noop(query, text, **kwargs)`.
- **Verified:** both catch **only** `(TelegramError, asyncio.TimeoutError)`; `asyncio.CancelledError` (BaseException) propagates; logs `type(exc).__name__` only (no payload); `_safe_edit` and `_edit_or_send` are **byte-identical** to `HEAD`. `_safe_answer` = 29 call sites; `_safe_edit_noop` = 6; the only remaining bare `q.answer(` occurrences are *inside* `_safe_answer` itself (correct).
- **Provenance:** helpers are identical to the externally reviewed WP-02 package (per project memory); the external review found only INFO-level notes (no blocking defect).
- **Mutation tests:** reverting `_safe_answer`'s catch → suite red; reverting `_safe_edit_noop` → suite red; broadening to `BaseException` → suite red. **Non-vacuous.**

### 5.2 `WP-03` — Handler outcomes, `Stage4-F1` propagation & send guards (`DEF-003`, `DEF-004`, `NEW-DEF-04`)

- **Verified:** all `5` legacy `_authorized_conversation` callers migrated to `_authorized_conversation_status` + `_raise_if_operational_api_failure`; `delete_conversation_confirm` inspects `status`/`auth_exc` before `mark_explicitly_ignored`; `reposearch` no longer consumes state on a `4xx` (`_show_repos` now returns `bool`); `_send_prompt`/`outbox_mark_sent` close the `outcome=None` gaps; raw `send_message`/`send_document`/`send_copyable`/`send_long` replaced with `_safe_send_html` or wrapped to map Telegram delivery failures to `mark_display_failed` (`FAILED_TRANSIENT`) without masking upstream `OperationalApiFailure`.
- **Mutation test:** reverting the `copy_reply` display-guard → 2 failures in `tests/test_wp03_handler_outcome_and_send_guards.py`. **Non-vacuous.**

### 5.3 `WP-04` (Part 1) — `_classify_failure` transient classification (`DEF-002`)

- **Verified:** network/Telegram transients (`RetryAfter`, `TimedOut`, `NetworkError`, `asyncio.TimeoutError`, `httpx.TransportError`, socket `OSError`) → `FAILED_TRANSIENT`; `BadRequest` (a `NetworkError` subclass in PTB 22.8) and local non-network `OSError` → `FAILED_PERMANENT`; SQLite BUSY/LOCKED preserved transient.
- **Mutation test:** reverting `_is_transient_operational_error` → 13 failures. **Non-vacuous.**
- **Part 2 (`/updates_*` commands, ADR §28.4 quarantine):** correctly **NOT implemented** (gated on owner decision `OD-02`). Confirmed absent (`grep` for `updates_status`/`updates_skip`/`POISON_SKIPPED` → none).

### 5.4 `WP-05` — Worker correctness, cache invalidation & cursor-loop protection

- **`DEF-012` (CreationWorker `wait_for_start` non-`ApiError` fallback):** both the resumed-poll and post-POST branches now record `CREATION_UNKNOWN` + notify, and `CancelledError` re-raises. **Mutation test:** removing the resumed-branch fallback → 2 failures. **Non-vacuous.** ✅
- **`NEW-DEF-02` (`on_created` list-cache invalidation):** threaded through `_finish_creation` → `CreationWorker` → `app.py`. **Mutation test:** removing it → 1 failure. **Non-vacuous.** ✅
- **`NEW-DEF-05` (`collect_conversations` repeated-cursor halt):** stops on a repeated `next_page_id` instead of looping to `max_pages` and falsely reporting `truncated=True`. **Mutation test:** removing the `seen_pages` guard → 1 failure. **Non-vacuous.** ✅
- **`DEF-008` (`deliver_outbox(outbox_id)` ignores its target):** replaced un-scoped `claim_outbox` with targeted `claim_outbox_by_id`. The fix is **correct and load-bearing** (proven: a discriminating test on the old code fails), **but the committed suite has no discriminating test** — see finding **F-01**. ⚠️
- **`DEF-007` (missing `continue`/`return` after retry-deadline clear failure in `watcher.py` / `notifier.py`):** both fixes are **correct**, **but the committed suite has no discriminating test** — see finding **F-02**. ⚠️

### 5.5 `WP-06` (Part 1) — Status normalization (`DEF-009`)

- **Verified:** `STATE_LABELS["unknown"] = "غير معروف"` added; display sites now use `state_label(get_status(conv))` (messages.py ×2, keyboards.py, handlers.py); no remaining raw `state_label(conv.get("execution_status"))`.
- **Part 2 (`callback_refs` table):** correctly **NOT implemented** (design prerequisite). Confirmed absent.

### 5.6 `WP-07` (partial) — State consistency & poller policy (`DEF-006`, `DEF-013`)

- **Verified:** `renew_awaiting` is now gated on `update.message.text.strip()` (whitespace-only no longer renews the `route` TTL); `bot/app.py` comment rewritten to state the custom poller dispatches **sequentially** (`dispatch_and_wait`).
- **Mutation test:** reverting to the old `if kind == "route" and pending:` → 1 failure. **Non-vacuous.**
- **Not implemented (correctly blocked):** intra-batch polling concurrency (`OD-04`) and the `DEF-011` filesystem offload/quota (overlaps `WP-01`). `concurrent_updates(True)` in `app.py` is **pre-existing at HEAD** — no new concurrency introduced; `bot/polling.py` is **unmodified** and remains strictly sequential.

### 5.7 `WP-08` (partial) — Operational docs, `start.sh` probe & parity tests (`DEF-017`, `DEF-018`, `NEW-DEF-08`)

- **Verified against source:** `tests/test_doc_code_parity.py` asserts the **20** env vars (`bot/config.py`) are covered by `.env.example`/`README.md`/`RUNBOOK`, and the **17** schema tables are documented in the RUNBOOK with the correct count. Independently re-counted: config env vars = **20**; `CREATE TABLE` names = **17**; web routes `/health`, `/ready`, `/status` = **3** (all confirmed present in `bot/web/app.py`). `start.sh` `anyio` probe and the doc edits (README/RUNBOOK/ZERO_TOUCH_STARTUP/API_NOTES) are present.
- **Mutation test:** `tests/test_doc_code_parity.py` is mutation-verified per the prior session's record.
- **Not implemented (correctly blocked):** final `updates_*`/`17→18` schema parity (owner-gated).

### 5.8 Blocked / not-started work packages (correctly absent)

`WP-01` (`OD-01`+`OD-03`), `WP-04` Part 2 (`OD-02`), `WP-06` Part 2 (design prereq), `WP-07` concurrency (`OD-04`), `WP-10` (`OD-05`+live creds). All confirmed **not implemented** — no over-reach. `WP-09` local execution is limited to this container.

---

## 6. Findings register (this review)

| ID | Severity | Finding | Evidence |
|---|---|---|---|
| **F-01** | `LOW` | **`DEF-008` fix lacks a discriminating regression test.** The committed suite passes unchanged when `deliver_outbox` is reverted to the un-scoped `claim_outbox` — so the fix is unprotected against future regression. (A throwaway discriminating test *does* fail on the old code and *passes* on the new code, proving the fix itself is real.) | `tests/` grep shows no test asserting that `deliver_outbox(outbox_id)` targets the *requested* id; mutation of `bot/outbox.py:233` → `3272 passed`. |
| **F-02** | `LOW` | **`DEF-007` fixes lack discriminating regression tests.** Removing the new `continue` (`bot/watcher.py`) and `return` (`bot/notifier.py`) leaves the suite fully green. Both fixes are correct and improve a real fail-closed inconsistency, but are untested. | Combined mutation of `watcher.py`+`notifier.py` → `3272 passed`. |
| **F-03** | `INFO` | **`DEF-009` normalization is not end-to-end pinned.** No test asserts the user-visible label for a conversation whose `execution_status` is absent (`get_status({}) == "unknown"` → `"غير معروف"`). | Not mutation-tested here; noted as a gap, not a defect. |

No `MEDIUM`/`HIGH` correctness, security, or data-integrity defect was found in the reviewed code. The fixes that *are* covered are all non-vacuous under mutation. F-01/F-02 are **coverage** gaps (regression protection), not functional defects — they do not block use, but should be closed when the owning work package is finalized.

---

## 7. Header task re-verification — the seven `REV-OD-*` corrections

The header task (`OHB2-OWNER-DECISIONS-BRIEFING-REVIEW-FIXES`) is already applied at HEAD `33530ca`. All seven corrections were independently re-verified against primary source / the committed baseline:

| Finding | Corrected location | Re-verified evidence | Result |
|---|---|---|---|
| `REV-OD-01` | `§4.B.1` (`L79`) | Now reads `DEF-012`; baseline §C.1 `L245-246` = `CreationWorker wait_for_start` fallback; `DEF-008` (`L185-186`) = `deliver_outbox(outbox_id)`. The only other `DEF-008` reference is the legitimate `§10` `WP-05` inclusion list. | ✅ |
| `REV-OD-02` | `§5.D` Option A risks + A/B prerequisites | Two same-batch constraints present; re-read source: `bot/polling.py:161-162` (sequential `dispatch_and_wait`), `bot/db.py:2985-2988` (`acknowledgment_boundary` from `_outcome_in_txn`), `bot/db.py:3012-3016` (`_outcome_in_txn` reads **only** `processed_updates`). | ✅ |
| `REV-OD-03` | `§2` new "Defect Register & Supersession" row + `§10` `WP-08` | `NEW-DEF-07` now referenced (2 occurrences); baseline §C.2 Group 2 defines it. | ✅ |
| `REV-OD-04` | `§6.B.1` (`L245`) | Cites `UNSUPPORTED_ATTACHMENT_TEXT` at `bot/handlers.py:1603-1606` (verified at HEAD: defined `L1603`, used `L2008`); `bot/messages.py` no longer appears in the briefing (0 matches). | ✅ |
| `REV-OD-05` | `§2`, `§6.B.2`, `§10` `WP-01`, `§12` | `tests/test_real_http_miniapp_download.py` and `tests/_miniapp_helpers.py` added to all four enumerations (4 matches each); both files exist. | ✅ |
| `REV-OD-06` | `§2` (`L38`) | Cites `§18.6 L624-646` (verified: `L624` = `### 18.6 …`) and `§28` bullet `4` at `L970-971` (verified). | ✅ |
| `REV-OD-07` | `§4.B.1` (`L80`) + `§10` `WP-06` (`L482`) | Persistence phrasing (in-memory synthesize / `update_failures` persist) present; `WP-06` relabeled **`Partially blocked`**. | ✅ |

**Neutrality re-check (corrected briefing):** `5` `OWNER DECISION REQUIRED — NO OPTION SELECTED` blocks; `13` unchecked `- [ ]` boxes; `0` checked boxes; no `Recommended`/`Preferred`/`Best Option` preselection markers. **No `OD-01`–`OD-05` option selected, ranked, endorsed, or implemented.**

**Verdict:** all seven corrections `PASS`; the briefing remains neutral, technically accurate, complete, and `SAFE_FOR_OWNER_DECISION_USE`.

---

## 8. Scope, safety & forbidden-action confirmation

- **Read-only review:** no source, test, config, ADR, operational-doc, Mini App, or deployment file was modified; the existing independent-review report and the fixes report were **not** modified.
- **No `WP-01`–`WP-10` implementation**; no approved architectural decision changed; no `OD-01`–`OD-05` option selected.
- **No dependency install or environment change** in the live workspace; all experiments ran in disposable containers.
- **No live/external checks; no secrets read or printed.**
- **No `commit`/`push`/branch/PR/merge/deploy/Autopush**; no destructive Git commands.
- All existing working-tree, untracked, ignored, and `.openhands/` content preserved (verified by before/after `git status`).
- The isolated review container remains available (`877e34fd1a24…`), mounting the frozen snapshot read-only with `network=none`; the live workspace is not mounted.

---

## 9. Verdict

- **Cumulative remediation (reviewed slice):** `PASS_WITH_NOTES` — all reviewed fixes are correct and fail-closed where required; the covered fixes are mutation-proven non-vacuous. Three coverage gaps (`F-01`, `F-02`, `F-03`) are recorded; none is a functional defect.
- **Full gate:** `PASS` — `3272 passed / 0 failed`; node `280/0`; pyflakes `0`; bandit High-severity `0`; pip-audit clean.
- **Independence:** `INDEPENDENCE_ESTABLISHED`.
- **Briefing (header task):** `PASS` — all seven `REV-OD-*` findings resolved; document `SAFE_FOR_OWNER_DECISION_USE`.
- **Owner decisions:** `OD-01`–`OD-05` remain `PENDING_OWNER_DECISION`.

---

*This report was created by an AI agent (OpenHands) on behalf of the repository owner.*
