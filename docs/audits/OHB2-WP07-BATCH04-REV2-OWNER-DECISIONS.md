# OHB2 — WP-07 / Batch 04 — REV2 — Owner Decisions (A–D)

**Task:** `OHB2-WP07-BATCH04-REV2-OWNER-AUTHORIZATION-AND-EXECUTION-READINESS`
**Date:** 2026-11-19
**Status:** **AWAITING OWNER DECISIONS** — nothing below is granted until the owner signs it
**Prepared by:** AI agent (OpenHands) on behalf of the repository owner

> ## ⚠️ NOTHING IS GRANTED
> Every checkbox in §10 is **empty on purpose**. This document **asks**; it does not authorize.
> Checking a box is the owner's act. An agent must never tick one.
> **F-01 and DEF-011-B are NOT independently reviewed, NOT accepted, NOT closed.**

---

## 1. Recommendation: R2, with a mandatory scope decision

**Recommended:** R2 (private → narrow review branch → PR to `main` → existing `pull_request` CI).

**Why R2:**
- Uses the **existing** `pull_request` trigger — **no workflow modification** required.
- Makes the review material **private** before it exists publicly.
- Leaves `main` untouched; the review branch is disposable.
- Keeps CI as the executor, so no new infrastructure or credentials are introduced.

**But R2 alone does not solve the blocker.** A scope decision is required first — see §5.

---

## 2. Exact consequences of changing visibility to private (Decision A)

| Effect | Detail |
|---|---|
| Public URLs stop working | Existing `github.com/TM-AEM/OpenHandBot` pages, raw links, and any badge URLs return 404 to anonymous users |
| CI on `main` | **Continues to run** — GitHub Actions is free/unlimited for private repos on standard runners |
| Existing clones | Keep working; `origin` fetch continues for authenticated users |
| Public fork network | Public forks of a public repo **remain public** — visibility change does **not** retroactively privatize existing forks |
| Anyone who already cloned | Retains their copy — **private ≠ recall** |
| Actions minutes | Private repos consume included minutes on some plans; public repos do not. Standard `ubuntu-latest` usage is normally within the free allowance, but this is **plan-dependent and must be checked by the owner** |
| Search engine caches | May persist for a period after the change |
| GitHub Pages / public artifacts | Any published Pages site is disabled |
| Reversibility | Reversible (private → public) by the owner |

**Honest limitation:** making the repository private **does not** guarantee that only the intended reviewer sees the material. It only removes anonymous access. Anyone with an existing clone, a fork, or collaborator access still has the content.

---

## 3. Access-audit scope (Decision B)

Read-only inspection, **no modifications**. Exact list:

| # | Check | Why it matters for the review |
|---|---|---|
| B-1 | Repository visibility (`private` flag) | Confirms A took effect |
| B-2 | Collaborators (users) + their permission levels | Who can read the review branch/PR |
| B-3 | Teams with access + team membership | Indirect read paths |
| B-4 | Installed GitHub Apps + their repo permissions | A `contents:read` app can read everything |
| B-5 | Webhooks | A webhook can exfiltrate push/PR events to a third party |
| B-6 | Actions enabled state + allowed-actions policy | Whether third-party actions can run |
| B-7 | Default `GITHUB_TOKEN` workflow permissions (read vs write) | Least-privilege check |
| B-8 | Fork pull-request policy (approve-first for forks) | A fork PR runs attacker-controlled code with repo context |
| B-9 | Runner group / self-hosted runner restrictions | Self-hosted runners may be less isolated than GitHub-hosted |
| B-10 | Artifact + log retention settings | How long review logs/artifacts persist |
| B-11 | Environment protection rules / required reviewers | Any gate that would block or expose the run |
| B-12 | Branch protection on `main` (required checks, force-push ban) | Confirms no direct-push path is open |

**Explicitly out of scope for B:** removing collaborators, revoking apps, editing webhooks, rotating credentials, changing any permission. Those need separate authorization.

**Risk to report if found:** any collaborator, app, webhook, or fork that could read the review branch/PR/logs/artifacts, plus the least-privilege configuration the review would need.

---

## 4. Exact publication allowlist (Decision C)

**Base:** `52e7789cc8cc97a7f7c09c9592226ab117db99a2` (`origin/main`)

### 4.1 Option S2 — "CI-green" set (9 files)

Required if the PR's CI must be **green**.

| # | Path | Δ vs `origin/main` | Purpose in the 34-test review | In Batch03? | New disclosure? | Unrelated WP-07? |
|---|---|---|---|---|---|---|
| 1 | `bot/attachments.py` | +386 / −103 | DEF-011-B + F-01 core | differs (+162/−65) | No (already in Batch04) | No |
| 2 | `bot/handlers.py` | +144 / −41 | `_read_local_capped` offload (T-8b) | **IDENTICAL** | No (in Batch03) | **Yes** (43/44 hunks NEW-DEF-03) |
| 3 | `bot/watcher.py` | +16 / −4 | DEF-011-B call site | **IDENTICAL** | No (in Batch03) | **Yes** (unwatch signature) |
| 4 | `bot/app.py` | +1 / −1 | DEF-011-B startup call site | **IDENTICAL** | No (in Batch03) | No |
| 5 | `bot/db.py` | +269 / −66 | **CI-green only** — NEW-DEF-03 methods | not in B3 snapshot | **YES** | **YES** (NEW-DEF-03 / DEF-013) |
| 6 | `tests/test_def011_fs_offload.py` | new (21 tests) | DEF-011-B tests | differs +3/−3 | No (in Batch04) | No |
| 7 | `tests/test_f01_reaper_fs_offload.py` | new (13 tests) | F-01 tests | not present | No (in Batch04) | No |
| 8 | `tests/test_handlers.py` | +2 / −2 | **CI-green only** (`**_kw`) | n/a | **YES** | **YES** |
| 9 | `tests/test_sw06_unwatch_db_failure_propagation.py` | +11 / −11 | **CI-green only** (`**_kw`) | n/a | **YES** | **YES** |

**Measured result:** focused 34 = **34 passed**; full suite = **3319 passed**; pyflakes **clean**; bandit **No issues identified**; pip-audit **clean**; node **280/0**.

**Cost:** discloses 3 files of unrelated NEW-DEF-03 / DEF-013 work (`db.py` + 2 test files).

### 4.2 Option S1 — "focused-only" set (6 files)

Files 1–4, 6, 7 from the table above (`db.py` and the 2 `**_kw` test files excluded).

**Measured result:** focused 34 = **34 passed**; full suite = **100 failed**.

**Cost:** PR CI **fails**. A red PR cannot serve as the review gate.

### 4.3 Excluded from every option (mandatory)

| Excluded | Reason |
|---|---|
| `.agent/PROGRESS.md` | Work log; +236 lines of unrelated history |
| `.openhands/` | Agent-private notes; ignored |
| All ignored paths (`.venv/`, `__pycache__/`, `.pytest_cache/`) | Caches / non-portable |
| 7 untracked WP-07 test files | Broader WP-07 only |
| 36 untracked `docs/audits/*` + `docs/reviews/*` | Documentation-only; unrelated |
| `docs/design//` | Malformed stray path |
| `.env`, credentials, tokens | Never publishable |

### 4.4 Sensitive-data result

Secret scan across all 9 files: **CLEAN** — no credentials, tokens, private keys, real user data.
Every file reviewed contains only source code and tests.

---

## 5. ⚠️ The mandatory scope decision (blocks C)

**Measured facts:**

| Branch content | Focused 34 | Full suite (= what CI runs) | CI |
|---|---|---|---|
| 6 files (`db.py` from `main`) | 34 ✅ | **100 failed** | ❌ |
| 7 files (+ modified `db.py`) | 34 ✅ | 11 failed | ❌ |
| 8 files (`db.py` reverted) | 34 ✅ | **89 failed** | ❌ |
| **9 files** | 34 ✅ | **3319 passed** | ✅ |
| `attachments.py` only | 1 failed / 33 | 1 failed | ❌ |

**Root cause (exact error, reproduced):**

```
TypeError: Database.remove_watched_completing() got an unexpected keyword argument 'update_id'
  bot/watcher.py:739
```

`origin/main`'s `bot/db.py` has **0** of the three NEW-DEF-03 methods
(`add_watched_and_record_outcome`, `set_awaiting_and_record_outcome`,
`clear_awaiting_and_record_outcome`). The DEF-011-B files **share files** with NEW-DEF-03, so
DEF-011-B cannot be published without it.

**⇒ A PR that is both "focused-34 only" and "CI-green" does not exist.** Choose one:

| Option | Content | CI | Disclosure | Verdict |
|---|---|---|---|---|
| **S1** | 6 files, focused only | ❌ red | Minimal | Accepts a red PR |
| **S2** | 9 files | ✅ green | Includes NEW-DEF-03 | Accepts unrelated disclosure |
| **S3** | Land NEW-DEF-03 on `main` first, then DEF-011-B PR on top | ✅ green | Clean per-batch | **Cleanest** — needs a separate owner-approved task |
| **S4** | New `workflow_dispatch` workflow running only the 34 | ✅ green | Minimal | Needs workflow-modification authorization (currently forbidden) |

**S3 and S4 are the only options satisfying both constraints.** Recommendation: **S3** if the
owner intends to land NEW-DEF-03 anyway; **S4** if DEF-011-B must be reviewed in isolation.

---

## 6. Exact CI execution mechanism

- **Trigger:** `pull_request` → `branches: [main]` (already present; **no workflow change**).
- **Jobs that will run:** `test` ("Tests & lint") and `frontend` ("Frontend tests (Node)").
- **Job selection without workflow modification:** **NOT POSSIBLE.** Both jobs run; there is no
  `workflow_dispatch`, no `inputs`, and no path filter on `ci.yml`. This is a hard limitation.
- **`test` job steps:** `pyflakes` → `pip_audit` → `bandit` → `python -m pytest -q`.
- **Matrix:** Python **3.11** and **3.13**. Only 3.13 exists locally, so the 3.11 leg would run
  for the **first time** on the runner (this is the known WP-09 gap).
- **Permissions:** `contents: read` — least privilege already in place.
- **Concurrency:** `ci-${{ github.ref }}`, `cancel-in-progress: true`.

**Honest statement:** the existing CI runs the **full** suite. It does **not** and **cannot** be
made to run "the 34 tests only" without modifying a workflow file or `pytest.ini`.

---

## 7. Runner data and execution boundaries (Decision D)

If D is granted, the GitHub-hosted `ubuntu-latest` runner would:

| Boundary | Detail |
|---|---|
| Receives | The REV2 archive `de8e4fc9…` (223474 B) via the approved PR/CI mechanism |
| Independently computes | SHA-256 from the received bytes |
| Compares | Against `de8e4fc9c751f900d8235b5a5fd8302620e1841114b250441bcdaf3a3c8bf8b5` |
| Sidecar | Used **only** as a comparison value, never as authentication |
| Extracts | Into a clean isolated directory |
| Verifies | Manifest: **20 files declared = 20 present**, all hashes OK, no symlinks, no traversal |
| Executes | 21 DEF-011-B tests, 13 F-01 tests, combined 34 |
| Must demonstrate | Different machine identity, separate filesystem, no access to the implementation worktree |
| Must NOT claim | A full 3419-test run from this package |

**Independence caveat:** GitHub-hosted runners are ephemeral and separate from this environment,
but **independence must be evidenced** (runner name, `GITHUB_RUN_ID`, machine-id, filesystem
paths). If that evidence is not captured, the correct verdict is `INDEPENDENCE_NOT_ESTABLISHED`.

---

## 8. Known workflow limitations

| # | Limitation |
|---|---|
| L-1 | No `workflow_dispatch` — cannot run on demand, cannot select a job |
| L-2 | CI runs the full suite; the focused 34 cannot be isolated without editing a workflow or `pytest.ini` |
| L-3 | The DEF-011-B files depend on NEW-DEF-03 db methods ⇒ focused-only branch is CI-red |
| L-4 | `ci.yml` runs on Python 3.11 and 3.13; 3.11 is unverified locally (WP-09) |
| L-5 | The 2 pre-existing failures noted in earlier memory are not present at `52e7789` (full suite is green) |
| L-6 | Both CI jobs run on every PR; `frontend` is irrelevant to this review but cannot be skipped |

---

## 9. Remaining technical risks

| # | Risk |
|---|---|
| T-1 | **`bot/handlers.py` mixes DEF-011-B with 43 NEW-DEF-03 hunks.** A reviewer must not read those as DEF-011-B evidence |
| T-2 | **`bot/watcher.py`** likewise mixes one DEF-011-B line with a NEW-DEF-03 `unwatch` signature change |
| T-3 | The focused 34 tests do **not** exercise the full reaper pipeline; F-02 (lock released while worker writes) and F-03 (stale acceptance doc) remain **OPEN** and untested |
| T-4 | Private visibility does not recall existing clones or public forks |
| T-5 | DEF-011-A (quota ledger) and DEF-011-C (UX copy) are **not implemented** — any "DEF-011 complete" claim would be false |
| T-6 | WP-09 (Python 3.11) is **UNVERIFIED** locally |

---

## 10. The four authorization statements — owner signs each individually

> An agent must never tick these. Each is deliberately separable; approving one does not approve
> another.

### A — Visibility change

- [ ] **A-GRANT** — "I authorize changing `TM-AEM/OpenHandBot` from **public** to **private**."
- [ ] **A-DENY** — "Do not change visibility. Keep the repository public."
- [ ] **A-DEFER** — "Decide later; do not change visibility now."

Owner signature / date: ______________________

### B — Read-only access audit

- [ ] **B-GRANT** — "I authorize **read-only** inspection of repository visibility, collaborators,
      teams, installed GitHub Apps, webhooks, Actions state and permissions, fork-PR policy, runner
      restrictions, artifact retention and branch protection. No changes."
- [ ] **B-DENY** — "Do not inspect repository access configuration."
- [ ] **B-DEFER** — "Decide later; do not inspect now."

Owner signature / date: ______________________

### C — Review branch + PR + CI

- [ ] **C-GRANT** — "I authorize creating branch `review/ohb2-wp07-batch04-def011b-f01` from
      `52e7789` and opening a PR to `main` containing **exactly** the allowlist in
      §4.1 (option **S2**) / §4.2 (option **S1**) / per option **S3** / **S4** [circle one],
      and triggering the existing `pull_request` CI. **No direct push to `main`. No merge.**"
- [ ] **C-DENY** — "Do not create a branch or PR."
- [ ] **C-DEFER** — "Decide later."

Owner signature / date: ______________________

**C requires the §5 scope decision:** S1 / S2 / S3 / S4 → __________

### D — Runner receives and executes the package

- [ ] **D-GRANT** — "I authorize the GitHub-hosted runner to receive the REV2 archive, compute its
      SHA-256 independently, extract it, verify the manifest, and execute the 21 + 13 = 34 focused
      tests, recording runner identity evidence."
- [ ] **D-DENY** — "Do not transfer or execute the package on a runner."
- [ ] **D-DEFER** — "Decide later."

Owner signature / date: ______________________

---

## 11. Exact next action after decisions are recorded

Execute **only** the stages whose authorization was granted, in order:

| Stage | Requires | Action |
|---|---|---|
| **A** | A-GRANT | Verify repo identity → change to private → read back → record timestamp. **Stop if read-back fails.** |
| **B** | B-GRANT | Run the 12 read-only checks in §3 → report access paths + risks. **Change nothing.** |
| **C** | C-GRANT + §5 choice | Create branch from `52e7789` → apply **only** the chosen allowlist → verify diff byte-for-byte → open PR to `main` → confirm the `pull_request` run starts → record `GITHUB_RUN_ID` + commit SHA. |
| **D** | C-GRANT + D-GRANT | In the runner job: hash the archive → extract → verify manifest → run 21 / 13 / 34 → record identity evidence. |
| **E** | D | Source-level review of `store_async`, `_store_prepare/_write/_finalize`, `sweep_async`, `_sweep_db_phase`, `_sweep_fs_tail`, `maybe_sweep_async`, `_read_local_capped`, `_remove_file`, `os.lstat`, `os.unlink`. |
| **F** | E | Findings with stable IDs + remediation plan. **No fixes implemented** without separate authorization. |

**If every box is DENY or DEFER:** nothing external happens; the package stays local and the
focused 34 remain locally verified only. That is a legitimate outcome, not a failure.

---

## 12. What this document is not

- Not a grant of any permission.
- Not an independent review.
- Not owner acceptance.
- Not a DEF-011 closure.
- Not evidence that the runner is independent — that must be proven at run time.
