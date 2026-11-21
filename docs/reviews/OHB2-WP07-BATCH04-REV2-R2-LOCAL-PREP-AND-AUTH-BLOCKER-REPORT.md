# OHB2 — WP-07 / Batch 04 — REV2 — R2 Route — Local Preparation and Authorization Blocker Report

**Task:** `OHB2-WP07-BATCH04-REV2-R2-PRIVATE-REPOSITORY-AND-INDEPENDENT-REVIEW`
**Date:** 2026-11-19
**Mode:** **LOCAL PREPARATION COMPLETE — STOPPED AT EXTERNAL-ACTION BOUNDARY**
**Verdict:** **`BLOCKED_OWNER_AUTHORIZATION_REQUIRED`** (A, B, C, D all not granted)

> No visibility change, no GitHub API call, no branch, no PR, no push, no CI trigger,
> no package transfer. Nothing left this machine.

---

## A. Authorization ledger

The task states: *"Do not infer any of A–D from this prompt, the R2 selection, prior reports, or
the existence of a package."* The R2 selection is a **route preference**, explicitly *not* a grant.
No item was granted.

| # | Authorization | Status | Evidence |
|---|---|---|---|
| **A** | Change visibility public → private | **NOT GRANTED** | Task says R2 selection "does NOT grant"; no explicit statement present. Repo **unchanged**. |
| **B** | Read repo settings, collaborators, teams, apps, webhooks, Actions permissions | **NOT GRANTED** | Same. **Zero GitHub API calls made.** |
| **C** | Publish review material via branch + PR, trigger existing workflow | **NOT GRANTED** | Same. No branch, no PR, no push. |
| **D** | Allow runner to receive and execute the package | **NOT GRANTED** | Same. No transfer. |

Per the task: for each missing authorization → *do not perform the associated external action;
continue only with independently authorized local/read-only work*. That is what was done.

---

## B. Phase 0 — Baseline preservation (COMPLETE)

| Item | Value |
|---|---|
| Repo root | `/workspace/project/OpenHandBot` |
| Remote | `https://github.com/TM-AEM/OpenHandBot.git` |
| Branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` |
| HEAD | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| `origin/main` | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| Divergence | `0 0` |
| Staged / Modified / Untracked / Ignored | **0 / 8 / 46 / 8** |
| `.openhands/` | present, 1 file, ignored — **untouched** |
| `.agent/` | present, 1 file (`PROGRESS.md`) — **untouched** |

### REV2 package — independently hashed from actual bytes

| Item | Value |
|---|---|
| Path | `/workspace/review-packages/OHB2-WP07-BATCH04-DEF011-F01-REV2-FOCUSED34-20261119.tar.gz` |
| **SHA-256 (computed from bytes)** | `de8e4fc9c751f900d8235b5a5fd8302620e1841114b250441bcdaf3a3c8bf8b5` |
| Expected (task) | `de8e4fc9c751f900d8235b5a5fd8302620e1841114b250441bcdaf3a3c8bf8b5` |
| Match | **EXACT** |
| Size | `223474` B |
| Sidecar | same digest — **comparison value only, not independent authentication** |

### Original Batch04 archive — PRESERVED

| Item | Value |
|---|---|
| Path | `…OHB2-WP07-BATCH04-DEF011-F01-20261119.tar.gz` |
| SHA-256 | `47b992300ec1bd5efec8c6c95afff4a63815a58ccd25f254975939f53f0bf71d` — **matches `47b9923…`** |
| Size / mtime | `107643` B / `2026-11-19 16:06:26` |

Not overwritten, renamed, deleted or reused.

### Local review documents (hashes recorded)

| File | SHA-256 |
|---|---|
| `docs/reviews/…C1-C2-PACKAGE-IMPLEMENTATION-REPORT.md` | `d5e66ebdd20d99ba2a69cae1aacf1e3b5e29402dac9e032b75369c881f38fdb6` |
| `docs/reviews/…REV2-EXTERNAL-REVIEW-ROUTE-BLOCKER-REPORT.md` | `bf8646a8be37decb45ac62922d8ef1c52dec6bfbc815f99c81f2258423b843af` |

---

## C. Phase 1.1 — Worktree classification

### C.1 Modified tracked files (8)

| File | Δ vs origin/main | Classification |
|---|---|---|
| `bot/attachments.py` | +386 / −103 | **DEF-011-B + F-01** (required) |
| `bot/handlers.py` | +144 / −41 | **Mixed**: 1 hunk DEF-011-B + 43 hunks NEW-DEF-03 |
| `bot/watcher.py` | +16 / −4 | **Mixed**: 1 line DEF-011-B + NEW-DEF-03 unwatch signature |
| `bot/app.py` | +1 / −1 | **DEF-011-B** (startup call site) |
| `bot/db.py` | +269 / −66 | **UNRELATED** — NEW-DEF-03 / DEF-013 atomicity |
| `tests/test_handlers.py` | +2 / −2 | **UNRELATED** — `**_kw` compat for NEW-DEF-03 |
| `tests/test_sw06_unwatch_db_failure_propagation.py` | +11 / −11 | **UNRELATED** — `**_kw` compat for NEW-DEF-03 |
| `.agent/PROGRESS.md` | +236 | **UNRELATED** — work log, must not publish |

### C.2 Untracked (46) — classification

| Group | Files | Classification |
|---|---|---|
| Focused review tests | `tests/test_def011_fs_offload.py` (21), `tests/test_f01_reaper_fs_offload.py` (13) | **Required for test reconstruction** |
| Broader WP-07 tests (7) | `test_f03_…`, `test_wp07_atomic_state_outcome.py`, `test_wp07_f1_notification_failure.py`, `test_wp07_nav01_…`, `test_wp07_nav02_…`, `test_wp07_nav06_…`, `test_wp07_watch_unwatch_atomicity.py` | **Broader WP-07 only** — exclude |
| Audit/review docs (36) | `docs/audits/*`, `docs/reviews/*` | **Documentation-only** — exclude |
| `docs/design//` (1 file) | stray double-slash dir | **Unrelated / malformed path** — exclude |

### C.3 Ignored (8) — excluded from any publication

`.openhands/`, `.pytest_cache/`, `.venv/`, `__pycache__/` (×5 incl. `bot/`, `bot/web/`, `tests/`, `automation/autopush/`)

---

## D. Phase 1.2 — Exact disclosure analysis (REVERIFIED, not assumed)

### D.1 Re-verification of the "identical to Batch03" claim

The task required re-verification rather than assumption. Result:

| File | vs Batch03 snapshot | Verdict |
|---|---|---|
| `bot/handlers.py` | `40dd8902…` = `40dd8902…` | **IDENTICAL — re-verified** |
| `bot/watcher.py` | `06f3dd4c…` = `06f3dd4c…` | **IDENTICAL — re-verified** |
| `bot/app.py` | `fb3d5038…` = `fb3d5038…` | **IDENTICAL — re-verified** |
| `bot/attachments.py` | `e72745eb…` → `d27fb798…` | **DIFFERS +162 / −65** (the F-01 delta) |
| `tests/test_def011_fs_offload.py` | differs **+3 / −3** | F-01 signature change (`_sweep_fs_tail(known, report, plan)`) |
| `tests/test_f01_reaper_fs_offload.py` | not in Batch03 | New (F-01 batch) |

### D.2 Also verified against the delivered Batch04 package

| File | vs Batch04 package |
|---|---|
| `bot/attachments.py` | **IDENTICAL** — already delivered |
| `tests/test_def011_fs_offload.py` | **IDENTICAL** — already delivered |
| `tests/test_f01_reaper_fs_offload.py` | **IDENTICAL** — already delivered |
| `bot/handlers.py` | **NOT IN Batch04** — this was the REV2 defect; would be first delivery |
| `bot/watcher.py`, `bot/app.py` | **NOT IN Batch04** — would be first delivery |
| `bot/db.py` | **NOT IN Batch04** — would be first delivery |

⇒ Only `attachments.py` and the two focused test files were previously disclosed. `handlers.py`,
`watcher.py`, `app.py` were disclosed in **Batch03** (identical bytes). `db.py` would be a **new**
disclosure of unrelated NEW-DEF-03 work.

### D.3 Per-file disclosure report (proposed allowlist)

| Path | Why required | Δ vs `origin/main` | In Batch03? | New disclosure? | Unrelated WP-07? | Secrets? |
|---|---|---|---|---|---|---|
| `bot/attachments.py` | DEF-011-B + F-01 core | +386 / −103 | differs (+162/−65) | No — already in Batch04 | No | none |
| `bot/handlers.py` | `_read_local_capped` offload (T-8b) | +144 / −41 | **IDENTICAL** | No — already in Batch03 | **Yes** (43/44 hunks NEW-DEF-03) | none |
| `bot/watcher.py` | DEF-011-B call site | +16 / −4 | **IDENTICAL** | No — already in Batch03 | **Yes** (unwatch sig) | none |
| `bot/app.py` | DEF-011-B startup call site | +1 / −1 | **IDENTICAL** | No — already in Batch03 | No | none |
| `bot/db.py` | **needed only to keep CI green** | +269 / −66 | n/a | **YES** | **YES** (NEW-DEF-03/DEF-013) | none |
| `tests/test_def011_fs_offload.py` | 21 DEF-011-B tests | new file | differs +3/−3 | No — already in Batch04 | No | none |
| `tests/test_f01_reaper_fs_offload.py` | 13 F-01 tests | new file | not present | No — already in Batch04 | No | none |
| `tests/test_handlers.py` | **CI-green only** | +2 / −2 | n/a | **YES** | **YES** (`**_kw`) | none |
| `tests/test_sw06_…py` | **CI-green only** | +11 / −11 | n/a | **YES** | **YES** (`**_kw`) | none |

Secret scan across all 9: **clean** — no credentials, tokens, private keys, real user data, `.env`,
`.openhands/`, `.agent/` or `PROGRESS.md`.

---

## E. Phase 1.3 — Publication feasibility: **A HARD SCOPE CONFLICT WAS FOUND**

### E.1 Workflow reconfirmed from current state

`.github/workflows/ci.yml` (byte-identical to `origin/main`, `e2edadf0…`):

```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
permissions:
  contents: read
```

- `grep -c workflow_dispatch .github/workflows/ci.yml` → **0**
- ⇒ A PR to `main` **can** trigger CI without touching `main`. ✅ Feasible mechanism.

### E.2 But CI runs the FULL suite

The `test` job runs, in order: `pyflakes` → `pip_audit` → `bandit` → **`python -m pytest -q`**,
across Python **3.11 and 3.13**.

The focused 34 tests are only a **subset**. `pytest -q` collects **everything**.

### E.3 Measured consequences (all runs performed locally)

| Candidate branch content | Focused 34 | Full suite | CI outcome |
|---|---|---|---|
| **6 files** (attachments, handlers, watcher, app + 2 tests), `db.py` from `origin/main` | **34 passed** | **100 failed / 3219 passed** | **CI FAILS** |
| 7 files (+ modified `db.py`) | 34 passed | **11 failed / 3308 passed** | **CI FAILS** |
| **9 files** (+ `db.py` + 2 `**_kw` test files) | 34 passed | **3319 passed** | **CI GREEN** |
| `attachments.py` only | **1 failed / 33 passed** | 1 failed / 3318 passed | CI FAILS |

**Root cause of the 100 failures — proven by error message:**

```
TypeError: Database.remove_watched_completing() got an unexpected keyword argument 'update_id'
  bot/watcher.py:739
```

The modified `bot/handlers.py`, `bot/watcher.py` and `bot/app.py` call NEW-DEF-03 db methods
(`add_watched_and_record_outcome`, `set_awaiting_and_record_outcome`,
`clear_awaiting_and_record_outcome`) that **do not exist** on `origin/main`'s `db.py`
(`grep -c "def <method>"` → **0** for each). The DEF-011-B change cannot be published
independently of the NEW-DEF-03 change, because they share the same three files.

### E.4 The scope conflict, stated exactly

- The task **forbids** publishing unrelated WP-07 work (`.agent/PROGRESS.md`, `bot/db.py`,
  unrelated tests).
- The task **requires** the existing CI workflow to execute **without modification**.
- The existing CI runs the **full** suite.
- The full suite **cannot pass** on a focused-only branch, because the DEF-011-B files depend on
  NEW-DEF-03 db methods.
- Therefore: **a PR that is both (a) narrowly scoped to the focused 34 and (b) CI-green does not
  exist.** Publishing the 9-file set would require publishing `bot/db.py` + 2 test files that carry
  **unrelated NEW-DEF-03 / DEF-013 work** — exactly what the task forbids.

Per the task: *"If the required publication diff includes code or tests outside the explicitly
approved allowlist, stop and report the exact scope conflict."* **That is what this report does.**

### E.5 Additional finding: CI also runs Python 3.11

`matrix.python-version: ["3.11", "3.13"]`. Only 3.13 is available locally, so the 3.11 leg is
**UNVERIFIED** locally (this is the known WP-09 gap). A PR would exercise it for the first time.

---

## F. Phase 4 — Preparation artifacts produced (NOT published)

| Artifact | Location | Status |
|---|---|---|
| Proposed 9-file diff | `/tmp/proposed-9.diff` (2621 lines) | generated, **not published**, temp |
| Allowlist | §D.3 above | documented |
| Disclosure report | §D above | documented |
| Scope-conflict analysis | §E above | documented |
| Branch name (proposed, NOT created) | `review/ohb2-wp07-batch04-def011b-f01` | **not created** |
| PR (proposed, NOT created) | → `main` | **not created** |

The real repository index was never touched (`staged=0` verified after diff generation).

---

## G. Phase 2, 3, 5, 6, 7 — NOT EXECUTED

| Phase | Status | Reason |
|---|---|---|
| 2 — Private protection | **NOT STARTED** | Authorization **A** not granted |
| 3 — Read-only GitHub audit | **NOT STARTED** | Authorization **B** not granted — no API call made |
| 5 — Package transfer + verification | **NOT STARTED** | Authorization **D** (and **C**) not granted |
| 6 — Independent technical review | **NOT STARTED** | No route to a separate runner |
| 7 — Remediation planning | **NOT PRODUCED** | No independent findings exist yet |

**No findings were invented.** Remediation planning requires real review findings; producing a
plan without them would be fabrication.

---

## H. Git and preservation — before/after

| Metric | Before | After |
|---|---|---|
| HEAD | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` | **unchanged** |
| Branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` | **unchanged** |
| Staged | 0 | **0** |
| Modified | 8 | **8** |
| Untracked | 46 | **47** (+ this report only) |
| Ignored | 8 | **8** |
| `.openhands/` | present | **preserved** |
| `.agent/` | present | **preserved** |
| Original archive `47b9923…` | intact | **intact** |
| REV2 package `de8e4fc9…` | intact | **intact** |

No reset, clean, force, broad deletion, `git add .` or `git add -A` was used.

---

## I. Explicit non-claims

- **No technical review ran.** No `PASS`/`FAIL` is issued.
- **No independent review occurred.** No runner was used; independence was never demonstrated.
- **No package transfer occurred.** The archive stayed on this machine.
- **Repository visibility unchanged** — it was not verified either (needs B).
- **DEF-011 is NOT closed.** DEF-011-A, DEF-011-C, F-02, F-03 and WP-09 remain separate and open.
- **No owner acceptance** is recorded or implied.

---

## J. Exact owner authorizations required to unblock

Each must be stated **explicitly and individually**:

1. **A** — "I authorize changing `TM-AEM/OpenHandBot` from public to private."
2. **B** — "I authorize read-only inspection of repository settings, collaborators, teams, installed
   apps, webhooks, Actions permissions and related access configuration."
3. **C** — "I authorize creating branch `review/ohb2-wp07-batch04-def011b-f01` and a PR to `main`
   containing **[the exact file list I approve]**, and triggering the existing `pull_request` CI."
4. **D** — "I authorize the GitHub-hosted runner to receive and execute the REV2 review package."

### J.1 Mandatory owner decision on the scope conflict (§E)

One of these must be chosen **before** C can be granted:

| Option | Content | Consequence |
|---|---|---|
| **S1 — Focused, CI-red** | 6 files only | PR CI **fails**; review still possible from the package artifact. Contradicts "CI green". |
| **S2 — CI-green, scope-expanded** | 9 files (adds `bot/db.py` + 2 `**_kw` test files) | CI **passes**; publishes unrelated NEW-DEF-03 / DEF-013 work — contradicts the no-unrelated-work rule. |
| **S3 — Split the batches** | First land NEW-DEF-03 (`db.py` + handlers/watcher changes + its tests) on `main`; then publish a DEF-011-B-only PR on top | Cleanest, but requires a separate owner-approved task and changes the original scope. |
| **S4 — Dedicated review workflow** | Authorize a new `workflow_dispatch` workflow file that runs only the 34 tests | Avoids publishing unrelated code; **requires workflow-modification authorization**, currently forbidden. |

**S3 and S4 are the only options that satisfy both "no unrelated disclosure" and "CI green".**
The owner must choose; the agent must not choose unilaterally.

---

## K. Verdict

# `BLOCKED_OWNER_AUTHORIZATION_REQUIRED`

All permitted local preparation is complete: baseline captured, package independently verified
(`de8e4fc9…`, 223474 B), worktree classified, disclosure analysis re-verified, workflow reconfirmed,
and a **material scope conflict** documented with measured evidence. No external action was taken.
