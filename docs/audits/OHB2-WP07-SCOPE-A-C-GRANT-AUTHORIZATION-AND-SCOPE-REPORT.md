# OHB2 — WP-07 — Scope A — C-GRANT Authorization and Scope Report

**Task:** `OHB2-WP07-SCOPE-A-C-GRANT-SIGNATURE-VALIDATION-AND-PUBLICATION`
**Date:** 2026-11-19
**Verdict:** **`BLOCKED_OWNER_AUTHORIZATION_REQUIRED`**

> **C-GRANT-SCOPE-A is NOT signed.** Zero ticked boxes, blank signature and date fields, no
> authorization recorded in any authoritative owner-decision document. No branch, commit, push, PR,
> CI run, or visibility change was made. Everything in this report is **read-only local work**.

---

## 0. Latest gate re-check — 2026-11-19 (task `OHB2-SCOPE-A-OWNER-SIGNATURE-GATE-AND-RELEASE`)

**Result: still `BLOCKED_OWNER_AUTHORIZATION_REQUIRED`. Nothing has been signed.**

| Check | Result |
|---|---|
| Ticked boxes — 3 governing docs | **0 / 0 / 0** |
| `C-GRANT-SCOPE-A` checkbox | **`- [ ]` unticked** — §1.2 quote and the §6 signature-ready block |
| `C-DENY-SCOPE-A` / `C-DEFER-SCOPE-A` | both **unticked** |
| Owner signature / date fields, all `docs/` | **6 lines, all blank `______________________`** |
| Signed grant anywhere in repo | **none** (regex sweep for `YES`/`GRANTED`/`SIGNED`/Arabic grant wording) |
| Grant markers in `.agent/PROGRESS.md` | **none** |
| Owner commit since `52e7789` | **none** |
| Report mtime | `23:43` = **agent write**, not an owner edit |

**The five required permissions, each independently checked — all ABSENT:**

| # | Permission | State |
|---|---|---|
| 1 | Create a dedicated Scope A branch | **NOT GRANTED** |
| 2 | Commit the isolated Scope A changes | **NOT GRANTED** |
| 3 | Push / publish the branch | **NOT GRANTED** |
| 4 | Create a pull request | **NOT GRANTED** |
| 5 | Allow PR-triggered CI to run | **NOT GRANTED** |

No permission was inferred from another. Stop boundary = action zero: no branch, no commit, no push,
no PR, no CI. The owner's decision fields were **not** edited or signed.

**Candidate re-confirmed unchanged (cheap hash check, full suite deliberately not rerun):**
`205f1363` / `40dd8902` / `06f3dd4c` / `2b1f9780` / `ba263311` — identical to the run that produced
3285 / 3334 / 47 / 280. Isolation spot-checks on a fresh reconstruction: `NAV-0`=0, `to_thread`=0,
`maybe_sweep_async`=0, `attachments.py`/`app.py` byte-identical, exactly 5 files, 0 schema changes.

**Owner action required: the single signature-ready block in §6 below.**

---

## 1. Phase 0 — Authorization record (read in full)

### 1.1 Documents read, current versions

| Document | Read | Ticked boxes |
|---|---|---|
| `docs/audits/OHB2-WP07-SCOPE-A-C-GRANT-AUTHORIZATION-AND-SCOPE-REPORT.md` | ✅ | **0** |
| `docs/reviews/OHB2-WP07-SCOPE-A-C-GRANT-PUBLICATION-REPORT.md` | ✅ | **0** |
| `docs/audits/OHB2-WP07-BATCH04-REV2-OWNER-DECISIONS.md` | ✅ | **0** |
| `docs/audits/OHB2-WP07-NEW-DEF03-S3-DELIVERY-AND-ACCEPTANCE-RECONCILIATION.md` | ✅ | **0** |

### 1.2 Where the `C-GRANT-SCOPE-A` wording lives

`docs/audits/OHB2-WP07-SCOPE-A-C-GRANT-AUTHORIZATION-AND-SCOPE-REPORT.md` §4.1, lines 200-218.
Its checkbox block is **verbatim**:

```
- [ ] **C-GRANT-SCOPE-A** (as above)
- [ ] **C-DENY-SCOPE-A**
- [ ] **C-DEFER-SCOPE-A**

Owner signature / date: ______________________
```

**All three boxes unticked. Signature line blank. No date.** This wording is a **draft authored by
the agent** — it is the proposed text, not a recorded owner decision.

### 1.3 The four required owner acts — none performed

| Required owner act | State | Evidence |
|---|---|---|
| Selected the Scope A-only option | **NO** | `C-GRANT-SCOPE-A` unticked |
| Explicitly granted the external actions | **NO** | no grant text anywhere |
| Completed signature **and** date | **NO** | `______________________`, no date |
| Recorded in authoritative owner-decision doc or designated signed section | **NO** | `OWNER-DECISIONS.md` still 0/12 ticked, 4 blank signatures |

### 1.4 Exhaustive negative verification

| Check | Command | Result |
|---|---|---|
| Ticked boxes, 4 governing docs | `grep -cE '^\s*- \[x\]'` per file | **0 / 0 / 0 / 0** |
| All owner signature lines in `docs/` | `grep -rn "Owner signature / date"` | **9 lines, all blank** |
| Any signed Scope A grant in the whole repo | `grep -rniE "C-GRANT-SCOPE-A.*(signed\|granted\|authorized)"` | **none** |
| C-GRANT in `.agent/PROGRESS.md` | `grep -nE "C-GRANT"` | **none** |
| Any `*SIGNED*` record file | `find . -iname "*SIGNED*"` | **none** |
| Owner commit since `52e7789` | `git log --oneline -3` | **none** |
| File mtimes of the auth record | `ls -l --time-style` | `2026-11-19T23:33` — **my own write**, no later owner edit |
| New owner-authored files | `git status --porcelain` | **none** |

### 1.5 Gate decision

**FAIL — `BLOCKED_OWNER_AUTHORIZATION_REQUIRED`.**

A task title, an agent recommendation, an unticked checkbox, or a prior assistant report is **not**
authorization. No external action was taken.

---

## 2. Phase 1 — Permission matrix (each verified independently)

| # | Permission | Required | Granted? | Evidence | Action taken |
|---|---|---|---|---|---|
| 1 | Create a dedicated Scope A branch | Explicit grant | **NO** | C-GRANT-SCOPE-A unticked | **not performed** |
| 2 | Commit the isolated Scope A changes | Explicit grant | **NO** | same | **not performed** |
| 3 | Push / publish the branch | Explicit grant | **NO** | same | **not performed** |
| 4 | Create a pull request | Explicit grant | **NO** | same | **not performed** |
| 5 | Allow PR-triggered CI to run | Explicit grant | **NO** | same | **not performed** |

No permission was inferred from another. Since **all five** are absent, the stop boundary is at the
very first action — nothing at all was executed. No workaround branch or commit was created.

---

## 3. Phase 2 — Fresh read-only baseline (not assumed)

| Field | Value |
|---|---|
| HEAD | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| `origin/main` | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| Branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` |
| Upstream tracking | **none** |
| Divergence | `0 0` |
| Staged | **0** |
| Modified | **8** |
| Untracked | **54** |
| Ignored | **8** |
| Local branches | **2** |
| `.openhands/`, `.agent/` | **present, preserved** |
| `ci.yml` sha256 | `e2edadf028a983b7…` — **unmodified** |
| Batch04 archive | `47b992300ec1…` — **intact** |
| REV2 archive | `de8e4fc9c751…` — **intact** |

**The five Scope A candidate files, hashed fresh in this task:**

| File | SHA-256 | Matches prior record |
|---|---|---|
| `bot/db.py` | `205f1363aaf0b1f8…` | ✅ |
| `bot/handlers.py` | `40dd8902595c1a63…` | ✅ |
| `bot/watcher.py` | `06f3dd4c23e3e154…` | ✅ |
| `tests/test_handlers.py` | `2b1f978091f45c69…` | ✅ |
| `tests/test_sw06_unwatch_db_failure_propagation.py` | `ba26331134244324…` | ✅ |

No `git reset`, `git clean`, force push, broad deletion, `git add .`, or `git add -A` was used.

---

## 4. Phase 3 — Scope A isolation revalidated (all 10 conditions)

Reconstructed fresh from `git archive origin/main` in `/tmp`, then deleted.

| # | Condition | Result |
|---|---|---|
| 1 | Exactly the five listed files included | **5 files differ** from `origin/main` — ✅ |
| 2 | `bot/db.py` only accepted NEW-DEF-03 functions, no schema change | **0** `create/alter/drop table`, **0** `add column` — ✅ |
| 3 | `bot/handlers.py` only the **12** accepted hunks (not 17 NAV, not DEF-011-B) | **12 kept / 13 dropped** — ✅ |
| 4 | `bot/watcher.py` only the **2** accepted hunks | **2 kept / 1 dropped** — ✅ |
| 5 | Both test files only accepted Scope A changes | `+2/−2` and `+11/−11` — ✅ |
| 6 | `NAV-0` remains zero | **0** — ✅ |
| 7 | `to_thread` remains zero | **0** — ✅ |
| 8 | `maybe_sweep_async` remains zero | **0** — ✅ |
| 9 | `attachments.py` and `app.py` byte-identical | **YES / YES** — ✅ |
| 10 | Schema changes remain zero | **0** — ✅ |

**Hunks dropped from `handlers.py` (13):** 2 module-import hunks (`anyio.to_thread`, `functools`) +
`_download_attachment_chunks` (DEF-011-B) and `start`, `show_menu`, `list_conversations`(4),
`list_watches`(2), `start_new_chat`, `open_conversation` (NAV-01..06).

**`db.py` accepted methods (9):** `_add_watched_nocommit`, `add_watched_and_record_outcome`,
`remove_watched`, `_remove_watched_nocommit`, `_remove_watched_completing_nocommit`,
`_set_last_state_nocommit`, `_set_awaiting_nocommit`, `clear_awaiting_and_record_outcome`,
`set_awaiting_and_record_outcome`.

**Isolation: PROVEN. No `BLOCKED_SCOPE_ISOLATION`.** The candidate was not rebuilt or broadened.

---

## 5. Phase 4 — Fresh local verification

Environment: **Python 3.13.15**, **Node v24.22.2**, **pytest 9.0.3**.
All runs on the reconstructed candidate, not on the working tree.

| # | Command | Exit | Result |
|---|---|---|---|
| 1 | `python -m pytest -q` | **0** | **3285 passed**, 0 failed, 74 warnings |
| 2 | `python -m pytest -q tests/test_wp07_watch_unwatch_atomicity.py tests/test_wp07_atomic_state_outcome.py tests/test_wp07_f1_notification_failure.py` | **0** | **47 passed** |
| 3 | `python -m pytest -q` (+4 WP-07 regression files) | **0** | **3334 passed**, 0 failed |
| 4 | `node --test tests/frontend/*.test.js` | **0** | **280 pass / 0 fail** |
| 5 | `python -m pyflakes bot/ automation/ tools/ main.py tests/` | **0** | **clean** (0 output lines) |
| 6 | `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | **0** | **No issues identified**; severity **High: 0** |
| 7 | `python -m pip_audit -r requirements-dev.txt` | **0** | **No known vulnerabilities found** |

**Count reconciliation:** 3285 (tracked) + 47 (focused) + 2 (`test_f03_…status_normalization`)
= **3334**.

**Bandit note:** the "High: 6" figure sometimes seen is **confidence**, not severity. Severity
`High: 0`, identical to an unmodified `origin/main` control.

### 5.1 Python-version coverage — honest statement

| Version | Ran? | Result |
|---|---|---|
| **3.13** | **YES** (local) | all checks above passed |
| **3.11** | **NO** | `python3.11` / `python3.12` **not installed** on this host |

**Python 3.11 compatibility is NOT established by these runs.** CI's matrix is
`["3.11", "3.13"]`; the 3.11 leg can only be proven by an actual CI run on a PR, which requires
authorization. Local 3.13 success does **not** imply 3.11 success.

**No check failed. No `BLOCKED_VERIFICATION_FAILURE`.**

---

## 6. The exact owner-decision text needed to proceed

The existing draft cannot be reused for a Scope-A-only publication as a matter of record: it must be
signed **and dated** in an authoritative location. Copy the block below into
`docs/audits/OHB2-WP07-BATCH04-REV2-OWNER-DECISIONS.md` (or a new owner-signed record), tick **one**
option, then sign and date.

> ### C-GRANT-SCOPE-A — Owner decision
>
> - [ ] **C-GRANT-SCOPE-A** — "I authorize, and only authorize:
>   1. creating branch `review/ohb2-wp07-scope-a-newdef03` from
>      `52e7789cc8cc97a7f7c09c9592226ab117db99a2`;
>   2. committing **exactly** these five paths and nothing else — `bot/db.py`,
>      `bot/handlers.py` (12 NEW-DEF-03 hunks only; no NAV, no DEF-011-B),
>      `bot/watcher.py` (2 NEW-DEF-03 hunks only), `tests/test_handlers.py`,
>      `tests/test_sw06_unwatch_db_failure_propagation.py`;
>   3. pushing that branch to `origin`;
>   4. opening a pull request from that branch to `main`;
>   5. letting the existing `pull_request` CI workflow run on that PR.
>
>   **No direct push to `main`. No merge. No visibility change. No workflow change.
>   No NAV-01..06, DEF-011-B, F-01, DEF-006, Mini App, schema, or architecture change.**"
> - [ ] **C-DENY-SCOPE-A** — "Do not create a branch or PR."
> - [ ] **C-DEFER-SCOPE-A** — "Decide later."
>
> Owner signature / date: ______________________

### 6.1 If the owner prefers per-action grants

| # | Statement | Tick |
|---|---|---|
| 1 | "I authorize creating branch `review/ohb2-wp07-scope-a-newdef03` from `52e7789`." | [ ] |
| 2 | "I authorize committing the five Scope A paths listed above to that branch." | [ ] |
| 3 | "I authorize pushing that branch to `origin`." | [ ] |
| 4 | "I authorize opening a PR to `main`." | [ ] |
| 5 | "I authorize the `pull_request` CI workflow to run on that PR." | [ ] |

### 6.2 Still outstanding, and not required for Scope A

| # | Decision | State | Blocks Scope A? |
|---|---|---|---|
| A | Visibility public → private | **MISSING** | No |
| B | Read-only access audit | **MISSING** | No |
| D | Runner executes the package | **MISSING** | No (needed for DEF-011-B review) |
| A′ | NAV-01..06 acceptance | **MISSING** — recommend A′-3 defer | No |

---

## 7. Ready the moment the signature exists

| Item | Status |
|---|---|
| Candidate | **verified, isolation proven**, regenerable deterministically |
| Full suite | **3285 passed** (fresh) |
| Focused | **47 passed** (fresh) |
| + WP-07 regression | **3334 passed** (fresh) |
| Frontend | **280 pass** (fresh) |
| pyflakes / bandit / pip-audit | **clean** (fresh) |
| Proposed branch | `review/ohb2-wp07-scope-a-newdef03` |
| Base commit | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| Remaining blocker | **owner signature only** |

---

## 8. Explicit non-claims

- **C-GRANT-SCOPE-A is NOT granted.** No branch, commit, push, PR, or CI occurred.
- **Python 3.11 is NOT verified** — the interpreter is absent locally.
- **No independent review** — no separate reviewer or environment was established.
- **Owner acceptance** covers Scope A (A-1..A-5) only; NAV, DEF-011-B, F-01 are **not** accepted.
- **WP-07 is not complete. DEF-011 is not closed.** The remediation program is not complete.
