# OHB2 — WP-07 Git Stabilization Plan

**Task ID:** `OHB2-WP07-FINAL-STABILIZATION-AUDIT-AND-OWNER-ACCEPTANCE-PACKAGE`
**Date:** 2026-11-19
**Status:** **PLAN ONLY — NOT EXECUTED**
**Recorded by:** AI agent (OpenHands) on behalf of the repository owner.

> ## ⚠ This is a plan. Nothing in it has been executed.
>
> **Every future Git operation requires separate, explicit owner authorization.**
> No staging, commit, push, PR, merge, tag, or release is authorized by this document.

---

## 0. Forbidden operations (binding)

Never use, at any step:

- `git add .` / `git add -A` / `git add --all`
- `git reset` (any form), `git clean` (any form)
- `git checkout -- <file>` / `git restore <file>` (overwrite forms)
- force push, `--force`, `-f`
- broad deletion, `rm -rf`, file removal
- `git commit --amend` on published commits

**Permitted (after authorization):** `git add <explicit-path>`, `git add -p <explicit-path>`,
`git commit -m`, `git status`, `git diff`, `git show`, `git stash create` (read-only snapshot),
`git hash-object`.

---

## 1. Current state (verified 2026-11-19) [FACT]

```
Branch : openhands-workspace-40xxn2SbOi0tRICb3y8TE
HEAD   : 52e7789cc8cc97a7f7c09c9592226ab117db99a2  (== origin/main, 0/0)
Staged : 0
Modified: 6
Untracked: 24
Ignored : 8
```

**Key hashes (SHA-256, first 16):**

| File | Worktree | HEAD |
|---|---|---|
| `bot/db.py` | `205f1363aaf0b1f8` | `472fa573142ee426` |
| `bot/handlers.py` | `752db8a6604a0d4c` | `96325cf2d8f24d29` |
| `bot/watcher.py` | `e7dbce406374de4b` | `43a6d9446ac6d75a` |
| `tests/test_handlers.py` | `2b1f978091f45c69` | `8a2b080ed10e5379` |
| `tests/test_sw06_unwatch_db_failure_propagation.py` | `ba26331134244324` | `79a8a5a332e18245` |
| `.agent/PROGRESS.md` | `46e29c7266cd94ad` | `4d702201c3f2778b` |

---

## 2. Exact intended baseline contents

The stabilization plan proposes **up to three bounded commits**, each requiring separate authorization.

### Commit 1 — Scope A: accepted NEW-DEF-03 non-concurrency work

**Include exactly:**

| Path | Treatment |
|---|---|
| `bot/db.py` | **partial** — only WP-07 hunks (§4.1) |
| `bot/handlers.py` | **partial** — only WP-07 + NAV hunks per decision (§4.2) |
| `bot/watcher.py` | **full** — entirely WP-07 (1 marker, 18 lines) |
| `tests/test_handlers.py` | **full** — mechanical `**_kw` only |
| `tests/test_sw06_unwatch_db_failure_propagation.py` | **full** — mechanical `**_kw` only |
| `tests/test_wp07_atomic_state_outcome.py` | **full** (untracked) |
| `tests/test_wp07_f1_notification_failure.py` | **full** (untracked) |
| `tests/test_wp07_watch_unwatch_atomicity.py` | **full** (untracked) |

**Exclude from Commit 1:** NAV test files (unless decision D-A′ accepts them), `.agent/PROGRESS.md`,
`tests/test_f03_...`, all other docs.

### Commit 2 — Scope A′: NAV-01..06 (ONLY if owner grants D-A′)

| Path | Treatment |
|---|---|
| `bot/handlers.py` | the NAV-01..06 hunks (§4.2) |
| `tests/test_wp07_nav01_nav03_nav04_atomic.py` | **full** (untracked) |
| `tests/test_wp07_nav02_nav05_simple_clear_atomic.py` | **full** (untracked) |
| `tests/test_wp07_nav06_open_conversation_atomic.py` | **full** (untracked) |

> If D-A′ is not granted, these files **remain uncommitted** and are **not** part of any baseline.

### Commit 3 — Scope B: DEF-006 (ONLY if OD-04 is resolved)

**Nothing to commit** unless OD-04 selects a change. The current `bot/app.py` DEF-006 comment is
**already in HEAD**; there is no working-tree concurrency change.

---

## 3. Files that MUST remain excluded

| Path | Reason |
|---|---|
| `.agent/PROGRESS.md` | Progress log, +155 lines, not implementation. Contains mixed historical entries. |
| `tests/test_f03_watch_conversation_status_normalization.py` | **WP-06 Part 1 (F-03)**, not WP-07. |
| `docs/design/` | WP-06 Part 2 design spec — different work package. |
| `docs/reviews/OHB2-WP05-*` | WP-05 artifacts. |
| `docs/reviews/OHB2-WP06-*` | WP-06 artifacts. |
| `docs/reviews/OHB2-REAL-EXECUTION-AND-REVIEW-BATCH-03-REPORT.md` | Prior batch report. |
| `docs/reviews/OHB2-WP07-*-REPORT.md` | **Reports** — see §6 (owner decision needed) |
| `docs/audits/OHB2-WP05-OWNER-ACCEPTANCE-RECORD.md` | WP-05 governance record |
| `docs/audits/OHB2-WP06-PART2-OWNER-DECISION-REGISTER-*.md` | WP-06 governance record |
| `docs/audits/OHB2-WP07-*.md` (the 5 delivered now) | Audit/proposal docs — see §6 |
| `.openhands/` | Ignored user memory. Never commit. |
| `.venv/`, `__pycache__/`, `.pytest_cache/` | Ignored build artifacts. |

---

## 4. Overlapping files and hunk separation

### 4.1 `bot/db.py` — WP-05 vs WP-07 [FACT]

**Verified:** the WP-05 marker (`DEF-008`, `deliver_outbox`) is at **line 3585**. All WP-07 hunks in
`bot/db.py` are at **≤ line 2911** (changed-range upper bound measured from `git diff -U0`).

⇒ **The two work packages are in disjoint line regions and are hunk-separable.**

**Procedure (when authorized):**

```bash
git add -p bot/db.py        # select ONLY WP-07 hunks (lines ~1885-2911)
git diff --cached bot/db.py # review: must show only WP-07 additions
```

**Acceptance gate for this hunk selection:** every staged hunk must contain an
`OHB2-WP-07` marker or be a direct mechanical consequence of one (e.g. a signature change).
Reject any hunk mentioning `DEF-008`, `deliver_outbox`, `claim_outbox`, or `OHB2-WP-05`.

### 4.2 `bot/handlers.py` — WP-02/03/04 vs WP-07 [FACT]

**Verified marker counts, HEAD vs working tree:**

| Work package | HEAD | Working tree | Δ |
|---|---|---|---|
| WP-02 | 4 | 4 | **0** |
| WP-03 | 22 | 22 | **0** |
| WP-04 | 1 | 1 | **0** |
| WP-07 | **1** | **14** | **+13** |

⇒ **The uncommitted `handlers.py` diff adds WP-07 work only.** WP-02/03/04 work is already committed
and unchanged.

**Hunk inventory (from `git diff -U0`), grouped by target:**

| Handler / function | Finding | Line range |
|---|---|---|
| `_remove_watched_with_retry` | NEW-DEF-03 (A-2) | 395-411 |
| `start` | NAV-01 | 892-898 |
| `show_menu` | NAV-02 | 955-959 |
| `list_conversations` | NAV-03 | 1076-1137 |
| `open_conversation` | NAV-06 | 1199-1203 |
| `list_watches` | NAV-04 | 1387-1407 |
| `watch_conversation` | NEW-DEF-03 (A-1) | 1441-1451 |
| `unwatch_conversation` | NEW-DEF-03 (A-2) | 1464-1492 |
| `reply_prompt` | F-1 (A-5) | 1857-1865 |
| `handle_text` | DEF-013 | 2521-2532 |
| `cancel_route` | F-1 (A-5) | 2582-2588 |
| `cancel_route_button` | F-1 (A-5) | 2598-2603 |
| `start_new_chat` | NAV-05 | 2685-2687 |
| `repo_search_prompt` | F-1 (A-5) | 2738-2742 |
| `pick_repo` | F-1 (A-5) | 2811-2815 |
| `new_chat_no_repo` | F-1 (A-5) | 2826-2833 |

**This grouping is what makes Commit 1 / Commit 2 separation feasible.**

---

## 5. Untracked WP-07 tests — treatment

| File | Lines | Commit 1 (Scope A) | Commit 2 (Scope A′) |
|---|---|---|---|
| `tests/test_wp07_atomic_state_outcome.py` | 216 | **include** | — |
| `tests/test_wp07_f1_notification_failure.py` | 399 | **include** | — |
| `tests/test_wp07_watch_unwatch_atomicity.py` | 548 | **include** | — |
| `tests/test_wp07_nav01_nav03_nav04_atomic.py` | 415 | exclude | **include** |
| `tests/test_wp07_nav02_nav05_simple_clear_atomic.py` | 295 | exclude | **include** |
| `tests/test_wp07_nav06_open_conversation_atomic.py` | 250 | exclude | **include** |
| `tests/test_f03_...` | 45 | **never** (WP-06) | **never** |

Add each with an explicit path: `git add tests/test_wp07_atomic_state_outcome.py` etc.

---

## 6. Generated reports and audit documents — treatment

**Recommendation [REC]: exclude all report/audit `.md` files from code commits.**

Rationale: they are governance artifacts, not implementation. Mixing them into an implementation commit
makes the diff unreviewable and violates "one commit, one concern".

**If the owner wants them versioned**, use a **separate docs-only commit** containing only:

```
docs/reviews/OHB2-WP07-F1-OPTION-C-IMPLEMENTATION-AND-INDEPENDENT-REVIEW-REPORT.md
docs/reviews/OHB2-WP07-NEW-DEF03-WATCH-UNWATCH-ATOMICITY-AND-INDEPENDENT-REVIEW-REPORT.md
docs/audits/OHB2-WP07-FINAL-STABILIZATION-AUDIT.md
docs/audits/OHB2-WP07-CONDITIONAL-OWNER-ACCEPTANCE-PROPOSAL.md
docs/audits/OHB2-WP07-GIT-STABILIZATION-PLAN.md
docs/audits/OHB2-WP07-O7-READINESS-ASSESSMENT.md
docs/reviews/OHB2-WP07-FINAL-STABILIZATION-BATCH-REPORT.md
```

This requires its own authorization and must not be merged with implementation.

---

## 7. Required pre-stabilization backups / snapshots

**Before any staging**, create a read-only snapshot (non-destructive, no index change):

```bash
# 1. Record exact state
git status --short > /tmp/wp07-prestabilize-status.txt
git rev-parse HEAD > /tmp/wp07-prestabilize-head.txt

# 2. Record hashes of every WP-07 file
sha256sum bot/db.py bot/handlers.py bot/watcher.py \
          tests/test_handlers.py tests/test_sw06_unwatch_db_failure_propagation.py \
          tests/test_wp07_*.py > /tmp/wp07-prestabilize-hashes.txt

# 3. Create a non-destructive blob snapshot WITHOUT touching the index or working tree
git stash create            # prints a commit SHA; does NOT modify the working tree
# record that SHA in /tmp/wp07-prestabilize-stash.txt

# 4. Optional: full tarball backup outside the repo
tar czf /workspace/review-packages/WP07-PRESTABILIZE-$(date +%Y%m%d).tgz \
    bot/ tests/ .agent/PROGRESS.md
```

**`git stash create` is preferred over `git stash push`** because it produces a commit object without
altering the working tree or index — no risk of losing user work.

---

## 8. Proposed commit boundaries

| # | Commit | Content | Precondition |
|---|---|---|---|
| 1 | `feat(wp07): atomic state+outcome writes for accepted NEW-DEF-03 scope` | Scope A code + 3 tests + mechanical test fixes | Owner authorization |
| 2 | `feat(wp07): NAV-01..06 navigation atomicity` | NAV hunks + 3 NAV tests | **Decision D-A′ granted** |
| 3 | `docs(wp07): stabilization audit and acceptance proposal` | the 7 report docs | Owner authorization (optional) |

**Never combine 1 and 2** — they are different acceptance scopes.

---

## 9. Required validation after staging, before committing

```bash
# 1. Confirm only intended paths are staged
git diff --cached --name-only

# 2. Confirm no excluded file slipped in
git diff --cached --name-only | grep -E '\.agent/PROGRESS\.md|test_f03_|docs/design/' && echo "ABORT: excluded file staged"

# 3. Confirm no WP-05 content staged
git diff --cached bot/db.py | grep -E 'OHB2-WP-05|deliver_outbox|claim_outbox' && echo "ABORT: WP-05 hunk staged"

# 4. Confirm no secrets
git diff --cached | grep -iE 'api[_-]?key|token\s*=|password|secret' && echo "REVIEW: possible secret"

# 5. Full gate on the staged tree
python -m pytest -q
python -m pyflakes bot/ automation/ tools/ main.py tests/
python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613
node --test tests/frontend/*.test.js
python -m pytest -q tests/test_doc_code_parity.py
```

**Every check must pass with the same or better results as the baseline:**

| Gate | Baseline |
|---|---|
| pytest | 3385 passed / 0 failed |
| pyflakes | 0 |
| bandit (severity High) | 0 |
| node | 280 pass / 0 fail |
| doc parity | 6 passed |

---

## 10. Required final verification after committing

```bash
git log --oneline -3
git status --short                    # must be clean of WP-07 code
git rev-parse HEAD
sha256sum bot/db.py bot/handlers.py bot/watcher.py   # must equal HEAD blobs
git show --stat HEAD                  # confirm exact file list
```

**Then re-run the full gate** on the committed tree to prove the commit did not change behaviour.

---

## 11. Preconditions before any of this is executed

| Precondition | Status |
|---|---|
| Owner authorizes Git operation | **NOT GRANTED** |
| Decision D-A (Scope A acceptance) | **NOT GRANTED** |
| Decision D-A′ (NAV scope) | **NOT GRANTED** |
| OD-04 resolved (Scope B) | **NOT GRANTED** |
| Independent review | **NOT ESTABLISHED** |
| Backups created | Not yet (plan only) |

**Until every precondition above is satisfied, this plan must not be executed.**

---

## 12. Summary

- **Baseline is achievable** as 2 code commits (Scope A, Scope A′) plus an optional docs commit.
- **Hunk separation is proven feasible**: WP-05 lives at `db.py:3585`, outside all WP-07 hunks; the
  `handlers.py` diff adds WP-07 only (WP-02/03/04 counts unchanged).
- **4 files must be excluded** from code commits (`.agent/PROGRESS.md`, `test_f03_...`, `docs/design/`,
  and — by default — the report/audit docs).
- **Two owner decisions gate the plan** (D-A′ for NAV, OD-04 for DEF-006).
- **Nothing was executed.**
