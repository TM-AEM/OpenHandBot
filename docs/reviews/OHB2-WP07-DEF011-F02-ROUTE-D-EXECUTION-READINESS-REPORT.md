# OHB2 — WP-07 — DEF-011 / F-02 — Route D Execution Readiness Report

**Task:** `OHB2-WP07-DEF011-F02-ROUTE-D-REVIEWER-INDEPENDENCE-DECISION-AND-EXECUTION-PLAN`
**Date:** 2026-11-21
**Review target:** `6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18` (PR #8 head, re-verified)
**Type:** documentation only. Nothing applied, committed, pushed, dispatched, published, or purchased.

---

## Final verdict

# `F02_OWNER_REVIEW_ONLY`

| Question | Answer |
|---|---|
| Who makes the technical judgment? | **The repository owner (`TM-AEM`)** |
| Is that judgment genuinely independent? | **No** — same principal that commissioned the work |
| Can Route D proceed without further owner decisions? | **No** — it needs authorization for the workflow file, and a decision accepting owner review |
| What exact action is next? | Owner accepts owner-review as the F-02 judgment and authorizes the workflow file |
| Does F-02 remain open? | **Yes — F-02 is OPEN** |

---

## 1. Verification performed in this task

Nothing below is carried over on trust; each item was re-probed.

| # | Check | Result |
|---|---|---|
| 1 | `6a1ca2e` resolves to a full 40-char SHA | `6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18` |
| 2 | That SHA **is still** `refs/pull/8/head` | **YES** — compared directly, not assumed |
| 3 | Parent / base | `f37a3f5…` / `52e7789…` (merge-base = `main`) |
| 4 | `main` unchanged | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| 5 | PR #7 unchanged | `31dec52289142d0d0dc2bd16604d88644ba3baba`, OPEN |
| 6 | PR #8 state | OPEN, MERGEABLE, 2 commits, **0 reviews**, **0 review requests** |
| 7 | CI on head | run `44877192697` — `pull_request` — **success** |
| 8 | Collaborators | exactly **one**: `TM-AEM` (admin) |
| 9 | Forks / stargazers / watchers | **0 / 1 / 0** |
| 10 | Distinct actors in repo events (last 50) | `["TM-AEM"]` |
| 11 | GitHub Models status | **RETIRED 2026-07-30** (live docs, quoted) |
| 12 | Copilot entitlement | `GET /user/copilot` → **404**, `plan: None` |
| 13 | GitHub App installed | `401 A JSON web token could not be decoded` — none |
| 14 | NVIDIA inference endpoint | Real; **one** genuine completion, then **7/7 attempts → HTTP 529** on real content |
| 15 | Changed files in target | 3 paths (`attachments.py`, `handlers.py`, test file) |
| 16 | `handlers.py` hunk count | **3** |
| 17 | F-02 test count | **45** |
| 18 | NEW-DEF-03 / NAV markers added | **0** |
| 19 | F-02 suite minimum deps | `pytest`, `anyio`, `httpx`, `python-telegram-bot` → **45 passed** |
| 20 | Negative control | hunk reverted → **T8b FAILS** (1 failed, 1 passed) |

---

## 2. Reviewer-judgment options — summary

Full analysis: `docs/audits/OHB2-WP07-DEF011-F02-REVIEWER-INDEPENDENCE-DECISION.md`.

| Option | Available? | Cost | Independent judgment? | Why |
|---|---|---|---|---|
| **A — Owner review** | **YES** | 0 | **NO** | Owner commissioned the work; accountable but not independent |
| **B — Second collaborator** | **NO** | 0 | would be yes | No second human exists; adding one = permission change (forbidden) |
| **C — Automated reviewer** | **NO** | — | would be yes | GitHub Models retired; Copilot unpaid/absent; NVIDIA unreliable + needs secret |
| **D — Runner + separately authored review** | **YES** | 0 | **NO** | Proves execution isolation; contains no reasoning step |

**No column satisfies all six dimensions.** Only B and C could supply reviewer identity and judgment
independence, and both require something forbidden in this task.

---

## 3. New evidence produced by this task

### 3.1 The F-02 suite is genuinely reproducible with four packages

This corrects an assumption in the earlier reports that independent re-execution was impractical on the
tablet. Verified in a clean `python:3.11-slim` container against the exact commit:

```
pip install pytest anyio httpx python-telegram-bot
python -m pytest tests/test_def011_fs_offload.py -q
→ 45 passed, 1 warning in 2.79s
```

With only `pytest` + `anyio`: **43 passed, 2 failed** (`T8b`, `T8c`) — so the four-package set is the
true minimum. No network, no live bot, no platform markers, no `skipif`.

**Consequence:** the owner *can* independently reproduce the F-02 evidence. This materially strengthens
Option A — it removes the "can't verify from a tablet" objection for the focused suite, though not for
the full 3330-test run.

### 3.2 Negative control re-verified with precision

```
fix present      → 45 passed
hunk reverted    → FAILED test_T8b_local_capped_read_runs_off_event_loop_thread
                   (1 failed, 1 passed, 43 deselected)
```

`T8b` fails; `T8c` still passes — correct, because `T8c` tests the byte cap rather than the offload.
This is evidence the 45 tests are not redundant copies of one another.

### 3.3 NVIDIA endpoint characterised fairly

- `GET /v1/models` → 200, 33 models.
- `minimaxai/minimax-m3.1-flash` → one genuine completion (`"HELLO"`, `finish_reason: stop`).
- **Every** attempt to review the real diff → `HTTP 529 Service temporarily overloaded` — 4 retries with
  backoff, then a 45-second wait plus 2 more, all 529.
- Other models → `404 Not found for account`.

It is real but cannot carry the workload, and using it would require a new repository secret. Recorded
as unusable rather than dismissed.

### 3.4 GitHub Models retirement re-confirmed from live documentation

> "As of July 30, 2026, GitHub Models has been fully retired. The playground, model catalog, inference
> API, and bring your own key (BYOK) are no longer available to any customer."

This is a fresh fetch, not a memory. It also closes the false-positive from two tasks ago, where a
stubbed `models.github.ai` returned `200 OK` and was misread as availability.

---

## 4. Route D readiness

### 4.1 Ready now (no further work needed)

| Item | State |
|---|---|
| Workflow design | Complete — `.github/workflows/f02-review.yml`, 252 lines |
| actionlint 1.7.7 | **exit 0** (YAML + shellcheck of every `run:` block) |
| YAML parse | OK |
| Scope guards | Validated against the real commit — "SCOPE OK", 0 markers, no protected surface |
| Merge-base resolution | Resolves to exactly `52e7789` |
| Negative control | Fail-closed, blob-hash asserted, `rc != 0` asserted; discriminates for real |
| Evidence preservation | `continue-on-error` + `if: always()` — artifact survives test failure |
| Instructions | Contain **no** PASS directive (grep = 0 matches); ship a blank findings template |
| Permissions | `contents: read`, `persist-credentials: false` — cannot push, comment, merge or deploy |

### 4.2 Not ready (requires owner action)

| Item | Blocker |
|---|---|
| Workflow file does not exist in the repository | It lives only in a disposable clone; adding it needs a branch + commit + push |
| No reviewer identity attached | The workflow deliberately has none |
| No judgment step | By design — adding one would require an LLM service, which does not exist here |

---

## 5. Execution plan — two branches

### Branch 1 — if the owner accepts owner-review (recommended, available now)

This is the only branch executable without a permission change or a purchase.

| # | Step | Exact action | Owner gate? |
|---|---|---|---|
| 1 | Accept the judgment model | Record in the F-02 report that the review is `OWNER_REVIEW`, not `INDEPENDENT_REVIEW` | **YES** |
| 2 | Authorize the workflow file | `git checkout -b review/f02-route-d-workflow 6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18`; add `.github/workflows/f02-review.yml`; `git add` **that path only**; commit `ci(f02): add read-only independent review evidence workflow`; push | **YES** |
| 3 | Run the workflow on the exact target | `gh workflow run f02-review.yml --repo TM-AEM/OpenHandBot -f head_sha=6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18` then `gh run watch` | no |
| 4 | Deliver the immutable package | `gh run download --name f02-review-evidence-6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18 -D <dir>`; verify `sha256sum full.diff` matches `diff-sha256.txt` | no |
| 5 | Owner applies the §6 contract | Read the diff, judge the tests, run the four-package command, fill the findings table **himself** | **YES** |
| 6 | Resolve findings | For each finding: fix → re-run CI **and** re-run the review on the new commit (a new SHA, so a new review) | **YES** |
| 7 | Closure | Only if no blocking finding remains; the report must say `OWNER_REVIEW` | **YES** |

**Important:** step 6 means a fix invalidates the review. A new commit is a new review target — the
evidence for `6a1ca2e` does not cover `6a1ca2e`-plus-a-fix.

### Branch 2 — if the owner requires true independence

Not executable by me. Requires one of:

- **Add a trusted second human** with read access (permission change → owner decision), then
  `gh pr edit 8 --add-reviewer <login>`; or
- **Authorize a working review service plus a repository secret** (secret → owner decision); GitHub
  Models is not an option (retired), Copilot review needs a paid plan.

Both are trust/policy decisions, not engineering tasks. Neither is proposed as something I can perform.

---

## 6. What Route D does and does not deliver

**Delivers:** execution on a genuinely separate host; exact-commit pinning with `HEAD` re-verification;
scope guards that fail loudly; a real negative control; a 30-day immutable artifact; zero write
capability; zero cost; zero secrets.

**Does not deliver:** a reviewer. No identity, no reasoning, no verdict. That is by design and is the
reason the verdict is `F02_OWNER_REVIEW_ONLY` rather than something stronger.

---

## 7. Compliance

| Constraint | Status |
|---|---|
| Documentation only | **Yes** — two new `.md` files |
| Workflow / application source modified | **No** |
| Tests modified | **No** |
| Branch or commit created | **No** |
| Staged / pushed / published | **No** |
| PR #8, PR #7, `main` modified | **No** — all three re-verified unchanged |
| GitHub permissions / visibility changed | **No** |
| Collaborators or secrets added | **No** |
| Services purchased / paid environments | **No** |
| `.agent/`, `.openhands/`, unrelated state | **Preserved** — memory notes appended only |
| Destructive git operations | **None** |
| Reviewer claimed to exist without evidence | **No** |
| F-02 claimed closed | **No** |

Workspace at completion: `HEAD 52e7789`, 8 pre-existing modifications preserved, **0 staged**.

Temporary artifacts created during verification (clone in `/tmp/tgt3`, test containers) were removed;
no container remains running.

---

## 8. Final answers

1. **Who will make the technical judgment?**
   The repository owner (`TM-AEM`) — the only party with access who is not an automated executor.

2. **Is that judgment genuinely independent?**
   **No.** The owner commissioned the work and set the acceptance criteria. It is an accountable
   review, not an independent external one, and it is labelled that way throughout.

3. **Can Route D proceed without further owner decisions?**
   **No.** Two are required: accepting owner-review as the judgment model, and authorizing the workflow
   file (branch + commit + push).

4. **What exact action is needed next?**
   The owner records acceptance of owner-review for F-02, then authorizes adding
   `.github/workflows/f02-review.yml` on a branch off `6a1ca2e`. After that the workflow can run and
   produce the artifact for the owner's judgment.

5. **Does F-02 remain open?**
   **Yes. F-02 is open.** WP-07 and DEF-011 also remain open. Nothing in this task closes them.
