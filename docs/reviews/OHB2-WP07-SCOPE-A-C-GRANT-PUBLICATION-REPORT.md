# OHB2 — WP-07 — Scope A — C-GRANT Publication Report

**Task:** `OHB2-WP07-SCOPE-A-C-GRANT-SIGNATURE-VALIDATION-AND-PUBLICATION`
**Date:** 2026-11-19

## Final verdict: **`BLOCKED_OWNER_AUTHORIZATION_REQUIRED`**

> `C-GRANT-SCOPE-A` is unsigned: 0 ticked boxes, blank signature and date, no grant recorded in any
> authoritative owner-decision document, no owner commit since `52e7789`. **No branch, commit, push,
> PR, CI run, or visibility change was performed.** All work below is read-only local verification.

---

## 0. Latest gate re-check — 2026-11-19 (task `OHB2-SCOPE-A-OWNER-SIGNATURE-GATE-AND-RELEASE`)

**Verdict unchanged: `BLOCKED_OWNER_AUTHORIZATION_REQUIRED`.**

Per the task's mandatory stop condition, this re-check was **concise and did not rerun the full test
suite**. No branch, commit, push, PR, or CI action was taken, and the owner's decision fields were
**not** edited or signed.

### 0.1 The exact missing fields

| Field | Location | Current value |
|---|---|---|
| `C-GRANT-SCOPE-A` checkbox | auth report §6, line ~231 | **`- [ ]` unticked** |
| `C-DENY-SCOPE-A` checkbox | auth report §6 | `- [ ]` unticked |
| `C-DEFER-SCOPE-A` checkbox | auth report §6 | `- [ ]` unticked |
| **Owner signature** | auth report §6, after the three boxes | **`______________________`** |
| **Date** | same line | **absent** |
| Per-action grants (alternative) | auth report §6.1, 5 rows | **all `[ ]` unticked** |
| Authoritative record | `docs/audits/OHB2-WP07-BATCH04-REV2-OWNER-DECISIONS.md` | **0/12 ticked, 4 blank signatures** |

### 0.2 The five permissions — all absent, none inferred

| # | Permission | State |
|---|---|---|
| 1 | Create a dedicated Scope A branch | **NOT GRANTED** |
| 2 | Commit the isolated Scope A changes | **NOT GRANTED** |
| 3 | Push / publish the branch | **NOT GRANTED** |
| 4 | Create a pull request | **NOT GRANTED** |
| 5 | Allow PR-triggered CI to run | **NOT GRANTED** |

### 0.3 Candidate unchanged → existing evidence still valid

| Check | Result |
|---|---|
| 5 candidate file hashes | `205f1363` / `40dd8902` / `06f3dd4c` / `2b1f9780` / `ba263311` — **identical** to the 3285-pass run |
| `NAV-0` in candidate | **0** |
| `to_thread` in candidate | **0** |
| `maybe_sweep_async` in candidate | **0** |
| `attachments.py` / `app.py` | **byte-identical** to `origin/main` |
| Files differing from `origin/main` | **exactly 5** |
| Schema changes | **0** |
| HEAD / staged / modified / untracked / ignored | `52e7789` / 0 / 8 / 54 / 8 — **unchanged** |

Because the candidate bytes are unchanged, the recorded results (3285 / 3334 / 47 / 280; pyflakes,
bandit, pip-audit) **remain valid for this exact candidate**. They are local Python **3.13** results
only; **Python 3.11 remains unverified**.

**Single owner action needed: sign and date §6 of the authorization report.**

---

## 1. The nine dimensions, kept separate

| # | Dimension | Status | Evidence |
|---|---|---|---|
| 1 | **Owner authorization** | **`MISSING`** | 0/4 docs ticked; 9 blank signature lines; no signed grant |
| 2 | **Source-scope correctness** | **`PROVEN`** | exactly 5 files; 10/10 isolation conditions |
| 3 | **Local test verification** | **`PASSED` (fresh)** | 3285 / 3334 / 47 / 280; pyflakes, bandit, pip-audit exit 0 |
| 4 | **Commit status** | **`NO_COMMIT`** | no branch created; HEAD still `52e7789` |
| 5 | **Publication status** | **`NOT_PUBLISHED`** | nothing pushed; no PR |
| 6 | **CI status** | **`NOT_RUN`** | no PR → `pull_request` CI cannot trigger |
| 7 | **Python-version coverage** | **`3.13 ONLY`** | 3.11 absent locally — **3.11 unverified** |
| 8 | **Independent-review status** | **`NOT_ESTABLISHED`** | no separate reviewer/environment |
| 9 | **Owner acceptance** | **`SCOPE_A_ONLY`** | `.agent/PROGRESS.md:4272`, A-1..A-5 |

No dimension is collapsed into another. Local green tests do not imply CI green; CI green would not
imply independent review; candidate correctness does not imply acceptance.

---

## 2. Owner authorization (detail)

| Item | Result |
|---|---|
| Ticked boxes — 4 governing docs | **0 / 0 / 0 / 0** |
| `C-GRANT-SCOPE-A` box | **unticked** (draft text, agent-authored) |
| Owner signature + date | **blank** (`______________________`, no date) |
| Owner signature lines across `docs/` | **9, all blank** |
| Signed grant anywhere in repo | **none** |
| C-GRANT in `.agent/PROGRESS.md` | **none** |
| Owner commit since `52e7789` | **none** |
| Auth-record mtime | `2026-11-19T23:33` — my own write; **no later owner edit** |

### 2.1 Permission matrix

| Permission | Granted | Action |
|---|---|---|
| Create Scope A branch | **NO** | not performed |
| Commit Scope A changes | **NO** | not performed |
| Push / publish branch | **NO** | not performed |
| Create pull request | **NO** | not performed |
| PR-triggered CI | **NO** | not performed |

**All five absent → stop boundary is at action zero.** Nothing was executed; no workaround branch or
commit was created to sidestep the gate.

---

## 3. Source-scope correctness (detail)

Candidate reconstructed fresh from `git archive origin/main`; 10/10 conditions passed.

| File | Change | In scope |
|---|---|---|
| `bot/db.py` | 9 NEW-DEF-03 methods, **0 schema change** | ✅ |
| `bot/handlers.py` | **12 of 25 hunks kept, 13 dropped** (+64/−24) | ✅ |
| `bot/watcher.py` | **2 of 3 hunks kept, 1 dropped** (+15/−3) | ✅ |
| `tests/test_handlers.py` | +2 / −2 | ✅ |
| `tests/test_sw06_unwatch_db_failure_propagation.py` | +11 / −11 | ✅ |

**Excluded, proven by measurement:** `NAV-0` = 0 · `to_thread` = 0 · `maybe_sweep_async` = 0 ·
`attachments.py` byte-identical · `app.py` byte-identical · schema changes 0 · `diff -rq` vs clean
`origin/main` = **exactly those 5 files**.

---

## 4. Local test verification (detail) — fresh in this task

Environment: **Python 3.13.15**, **Node v24.22.2**, **pytest 9.0.3**.

| Command | Exit | Result |
|---|---|---|
| `python -m pytest -q` | **0** | **3285 passed**, 0 failed |
| `python -m pytest -q` (3 focused files) | **0** | **47 passed** |
| `python -m pytest -q` (+4 WP-07 files) | **0** | **3334 passed**, 0 failed |
| `node --test tests/frontend/*.test.js` | **0** | **280 pass / 0 fail** |
| `python -m pyflakes bot/ automation/ tools/ main.py tests/` | **0** | **clean** |
| `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | **0** | **No issues identified**; severity High **0** |
| `python -m pip_audit -r requirements-dev.txt` | **0** | **No known vulnerabilities found** |

**Reconciliation:** 3285 + 47 + 2 (`test_f03_…status_normalization`) = **3334**.
**Bandit:** "High: 6" is *confidence*; severity High is **0**, matching an unmodified control.

### 4.1 Python-version coverage

| Version | Ran | Evidence |
|---|---|---|
| 3.13 | **YES** | all checks above |
| 3.11 | **NO** | `python3.11`/`python3.12` absent; CI matrix `["3.11","3.13"]` |

**Python 3.11 compatibility is NOT established.** Only a real CI run on a PR can prove it.

---

## 5. Commit, publication, CI status

| Item | Status |
|---|---|
| Branch created | **NO** |
| Files staged | **NO** — 0 staged; no broad staging used |
| Commit | **NO** |
| Push | **NO** |
| Pull request | **NO** |
| CI workflow run | **NO** — no PR exists to trigger `pull_request` |
| Visibility / access settings | **unchanged (public)** |
| `.github/workflows/ci.yml` | **unmodified** (`e2edadf028a983b7…`); no `workflow_dispatch` added |

### 5.1 Preservation, before → after

| Metric | Before | After |
|---|---|---|
| HEAD | `52e7789` | **`52e7789`** |
| Staged | 0 | **0** |
| Modified | 8 | **8** |
| Untracked | 54 | **54** (2 reports rewritten in place) |
| Ignored | 8 | **8** |
| Local branches | 2 | **2** |
| 5 candidate file hashes | — | **byte-identical** (`205f1363`, `40dd8902`, `06f3dd4c`, `2b1f9780`, `ba263311`) |
| Archives `47b9923…`, `de8e4fc9…` | intact | **intact** |

No `reset`, `clean`, stash, force push, broad staging, or destructive operation. No source or test
file was modified. No owner-signed record was altered.

---

## 6. Why CI could not run

`ci.yml` triggers on `push[main]` and `pull_request[main]` **only** — there is **no
`workflow_dispatch`**. Therefore CI cannot be triggered without a branch and PR, both of which
require the absent authorization. Adding `workflow_dispatch` is explicitly forbidden by the task.

**No CI result exists. None is claimed.**

---

## 7. Phase 7 — Next-stage handoff (prepared, NOT executed)

### 7.1 Scope A identity

| Field | Value |
|---|---|
| Base commit | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| Validated commit | **none** — not committed |
| Proposed branch | `review/ohb2-wp07-scope-a-newdef03` |
| Content | 5 files; `db.py` + 12 handlers hunks + 2 watcher hunks + 2 test files |
| Verification | 3285 / 3334 / 47 / 280; pyflakes, bandit, pip-audit exit 0 |

### 7.2 Remaining DEF-011-B / F-01 changes (NOT published, NOT authorized)

| File | Content |
|---|---|
| `bot/attachments.py` | +386 / −103 (`StagingStore`, `AttachmentReaper.sweep_async`, `AttachmentService.accept`) |
| `bot/app.py` | 1 hunk (`await reaper.sweep_async(...)`) |
| `bot/handlers.py` | 3 hunks (imports + `_download_attachment_chunks` offload) |
| `bot/watcher.py` | 1 hunk (`maybe_sweep_async`) |
| `tests/test_def011_fs_offload.py` | 21 tests |
| `tests/test_f01_reaper_fs_offload.py` | 13 tests |

### 7.3 Package / baseline compatibility

| Item | Status |
|---|---|
| REV2 archive | **intact** — `de8e4fc9c751…`, 223474 B, 20/20 manifest |
| vs declared baseline (`52e7789` worktree) | **valid** — 34/34 |
| vs a NAV-excluded stabilized baseline | **NOT valid** — 1 failed / 33 passed |
| Cause | `snapshot/bot/handlers.py` carries the 17 unaccepted NAV hunks; DEF-011-B test T-8b needs the `_download_attachment_chunks` hunk |
| Required action | regenerate with a **DEF-011-B-only** `handlers.py` snapshot (3 hunks, not 44), fresh manifest, built twice for digest equality |

### 7.4 Independent-runner requirements (D-GRANT, not granted)

1. Fresh environment, network-isolated, no access to this session or its shell history.
2. Verify archive digest and manifest **before** extraction.
3. Run 21 DEF-011-B + 13 F-01 tests and the full suite.
4. Report findings independently — the reviewer must not be this agent or this session.

### 7.5 Separate authorizations still needed

| Stage | Authorization | Purpose |
|---|---|---|
| Publish Scope A | **`C-GRANT-SCOPE-A`** (auth report §6) | branch, commit, push, PR, CI |
| Publish DEF-011-B / F-01 | **separate C-GRANT** for that set | second PR on the validated Scope A base |
| Independent execution | **`D-GRANT`** | runner hashes, extracts, verifies manifest, runs 21/13/34 |

### 7.6 Unresolved findings still open

Kept open — none resolved or verified by this task:

| Item | State |
|---|---|
| **DEF-011-A** | **OPEN** |
| **DEF-011-C** | **OPEN** |
| **F-02** | **OPEN** |
| **F-03** | **OPEN** |
| **WP-09** — Python 3.11 verification | **OPEN** — 3.11 never executed locally; only a real CI run proves it |
| **Independent technical review** | **NOT ESTABLISHED** — no separate reviewer/environment |
| **Remaining WP-07 findings** | **OPEN** (NAV-01..06 unaccepted; DEF-006/OD-04 blocked) |

**DEF-011-B / F-01 are NOT published and NOT authorized.** They require, separately: their own scope
review, a regenerated package whose `handlers.py` snapshot contains only the 3 DEF-011-B hunks (the
current REV2 snapshot carries the 17 unaccepted NAV hunks and therefore fails on a NAV-free baseline),
and an explicit authorization.

---

## 8. Deliverables

| # | Path | Status |
|---|---|---|
| 1 | `docs/audits/OHB2-WP07-SCOPE-A-C-GRANT-AUTHORIZATION-AND-SCOPE-REPORT.md` | **rewritten** |
| 2 | `docs/reviews/OHB2-WP07-SCOPE-A-C-GRANT-PUBLICATION-REPORT.md` | **this file** |

Both are **agent evidence reports**, kept separate from owner decisions. No owner-signed record was
overwritten — the owner-decision documents remain untouched with their blank fields.

---

## 9. Explicit non-claims

- **No publication occurred.** Nothing committed, pushed, or opened as a PR.
- **No CI ran.** No workflow run or result exists.
- **Python 3.11 is unverified.**
- **No independent technical review** — `NOT_ESTABLISHED`.
- **Scope A is not landed** — it is verified and ready, nothing more.
- **DEF-011 is not closed. WP-07 is not complete.** The overall remediation program is not complete.

## 10. Single next action

**Owner signs and dates `C-GRANT-SCOPE-A`** in an authoritative owner-decision record
(text ready in the authorization report §6). No engineering work remains before publication — only
the signature and date.
