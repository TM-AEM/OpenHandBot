# OHB2 — WP-07 — DEF-011 / F-02 — Isolated Final Closure Report

**Task:** `OHB2-WP07-DEF011-F02-ISOLATED-CANDIDATE-PUBLICATION-CI-INDEPENDENT-REVIEW-CLOSURE`
**Date:** 2026-11-21
**Base commit:** `52e7789cc8cc97a7f7c09c9592226ab117db99a2`

## Verdict: `F02_BLOCKED_INDEPENDENT_REVIEW`

Publication, CI and remediation all succeeded. **F-02 is not closed** because acceptance criterion 4 —
a genuine independent review — could not be obtained in this environment (§5). This is the only
unmet criterion; everything else passed.

> F-02 must **not** be reported as closed. WP-07 and DEF-011 also remain **open**: their other
> findings and owner decisions are untouched by this work.

---

## 1. Identity record

| Item | Value |
|---|---|
| Base / parent of candidate | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| **Candidate commit** | **`f37a3f524ec745f1b5d606161c6ad8b074613a2c`** (parent `52e7789`) |
| **Follow-up commit** | **`6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18`** (parent `f37a3f5`) |
| Branch | `review/ohb2-wp07-def011-f02-isolated` |
| PR | **#8** — https://github.com/TM-AEM/OpenHandBot/pull/8 — OPEN, unmerged, base `main` |
| Patch SHA-256 | `75f74a3661a070ba4034d8a125d45d31710d3e911805c7ae374e8e7541c5ae26` |
| CI run (candidate) | **`44874157557`** — `f37a3f5` — success |
| CI run (follow-up) | **`44877192697`** — `6a1ca2e` — success |
| PR #7 | `31dec52…` — **OPEN, unmerged, untouched** (`updated_at` 2026-11-20, before this task) |
| `main` | unchanged at `52e7789` |

---

## 2. Phase 1 — Freeze and verify (all checks passed)

| Check | Result |
|---|---|
| Patch exists, SHA-256 | `75f74a3661a0…` — **matches** the preparation report prefix |
| Path list (from the patch itself) | `bot/attachments.py`, `bot/handlers.py` — **2 paths** |
| `git apply --stat` | 2 files changed, 450 insertions(+), 105 deletions(−) |
| `bot/attachments.py` | `b98d561f0ba0…` — **matches manifest** (verified F-02 implementation) |
| `bot/handlers.py` | `82d9c4b8e0fa…` — **matches manifest**; exactly 3 regions (`functools`, `to_thread`, the `_download_attachment_chunks` swap) |
| `bot/db.py` | `472fa573142e…` — **byte-identical to base**, not in the patch |
| NEW-DEF-03 / NAV-01..06 markers in diff | **0** |
| Apply to fresh `52e7789` | `git apply --check` OK, applied clean |
| Focused tests | T8b **1 passed**; DEF-011 file **45 passed** |
| Full suite pre-publication | **3329 passed, 1 skipped, 0 failed** on 3.11.18 **and** 3.13.18 |

**No discrepancy** between patch, path list, manifest and reconstructed candidate. No rebuild or
broadening was needed.

> Note on the third declared file: the manifest's three-file set includes `bot/db.py`, which the
> preparation work proved byte-identical to base. The patch therefore carries 2 diffs. This is
> consistent with the verified report, not a mismatch.

---

## 3. Phase 2 — Publication (passed, exact scope)

- Branch created **from `52e7789`**; only `bot/attachments.py` and `bot/handlers.py` staged.
- **Staged diff SHA-256 `75f74a3661a0…` — byte-identical to the verified patch** (`cmp` clean).
- Commit `f37a3f5`: 2 files, +450/−105. Committed blobs re-verified against the manifest after commit.
- Pushed; PR #8 opened against `main`. **PR #7 was not reused, retargeted, edited, closed or merged.**
- No audit report, handoff doc, untracked file or unrelated workspace content was staged.

---

## 4. Phase 3 — Actual CI on the exact commits (passed)

**Run `44874157557`** — event `pull_request`, `headSha` **`f37a3f524ec745f1b5d606161c6ad8b074613a2c`** (exact match).

| Job | Steps | Result |
|---|---|---|
| `Tests & lint (3.11)` — Python **3.11.18** | checkout, install, pyflakes, pip-audit, bandit, pytest | **success** |
| `Tests & lint (3.13)` — Python **3.13.18** | same | **success** |
| `Frontend tests (Node)` | `node --test` | **success** — **280 pass / 0 fail** |

Every step in both Python jobs individually `success` (verified per-step, not just the run
conclusion). bandit `High: 0`. **3285 passed** on each Python version.

**Run `44877192697`** — `headSha` **`6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18`** (exact match).
All 3 jobs `success`; **3330 passed** on 3.11 **and** 3.13.

**Count reconciliation — this is the key finding:**

| Figure | Meaning |
|---|---|
| 3330 | all tests in the follow-up commit |
| 3329 + 1 skipped | local run, which *includes* the 45 untracked F-02 tests |
| **3285** | **CI on `f37a3f5` = 3330 − 45** — the F-02 tests were not in the commit |
| 3443 | unrelated wider working tree (8 untracked NEW-DEF-03 test files + `watcher.py`/`app.py`) |

A green run for PR #7 or for `52e7789` was not used as evidence anywhere.

---

## 5. Phase 4 — Independent review: `INDEPENDENCE_NOT_ESTABLISHED`

The task requires a separate host, a separate filesystem, a separate session/process context, and
read-only access to the exact published commit. **None is available here.** Evidence:

| Route | Probe result |
|---|---|
| Second host | `hostname` = `runtime-hjffxzvtsqfkfugy-566946795b-cjkbr`; no cloud-instance metadata; no SSH config; `docker context ls` = local socket only |
| Second filesystem | containers share this host's kernel and disk |
| Second session | the only `RUNNING` Cloud sandbox (`1lKbI4WbA2VdFqzkEoxUQw`) belongs to **this** conversation `6715bb35…` |
| New Cloud sandbox | would **spend money** → AGENTS.md §9 explicit stop condition (not authorized) |
| GitHub Copilot reviewer | request returned `requested_reviewers: []`, `review_requests=0` — **not enabled** on this repo |

A second agent, a second container, or a different prompt on the same host is explicitly **not**
independent per the task definition.

**Therefore this report claims no independent review.** What was done instead — rigorous, but
**same-agent** and labelled as such:

- Reviewed in a container with the repo mounted **read-only** (`-v /tmp/rev:/work:ro`), working on a
  copy, on the exact published commit `f37a3f5`.
- All **45** F-02 tests pass; the **25** lifecycle tests (`F02*`, `case01–18`, `REV01`, `M4/M5`, `T8b`)
  pass; stable across **5 consecutive runs**.
- **Mutation testing (non-vacuity), each reverted after:**
  - remove the `abandoned` gate → **2 tests fail** (`case18_no_await_while_holding_gate`,
    `REV01_abandoned_worker_must_not_write_and_must_not_overlap`)
  - remove the drain block → **7 tests fail** (incl. `case13_anyio_scope_already_cancelled_at_drain`,
    `case17_T7_strengthened_pre_start`)
  - revert the `handlers.py` hunk to a direct call → **T8b fails** on the loop-thread assertion
- **Base check:** the suite on `52e7789` without the fix → **32 failures**, including T8b.
- Scope: 2 files changed vs parent; **no** schema, Mini App, API, dependency, worker or queue change;
  **0** NEW-DEF-03/NAV markers; D6 explicitly retained in code (lines 916, 966).
- pyflakes **0 issues**; bandit **High 0**.
- 5 `tests/test_autopush_*` failures in the review container are `FileNotFoundError: 'git'` (the slim
  image ships no git); installing git inside that container gives **41/41 pass**. CI, which has git,
  passed them. Not a code defect.

The ten review points required by the task were each exercised and found sound: the atomic
`threading.Lock` gate gives deterministic mutual exclusion between caller and worker; the worker sets
`_done` in `finally` on every path; cancellation drains under an outer shield; raw `Task.cancel()`
at the pre-start boundary leaves `abandoned=True` so the worker cannot write; error propagation
re-raises rather than masking; D6 is explicitly excluded. **This is my own verification, not a
reviewer's.**

---

## 6. Phase 5 — Findings and remediation

### Finding F-02-CI-01 — **HIGH** — CI green while covering zero F-02 behaviour — **FIXED**

- **Reproducible:** yes, deterministically (arithmetic, not timing).
- **Evidence:** the candidate changed `bot/attachments.py` and `bot/handlers.py` but shipped no test.
  `tests/test_def011_fs_offload.py` does not exist at base, so CI collected 3285 tests —
  exactly 45 fewer than the 3330 available — and none of them touched F-02. A green CI on `f37a3f5`
  therefore said nothing about whether F-02 works, while the task's acceptance criterion 6 requires
  regression tests proving the fix and the negative control.
- **In scope?** Yes — it is the F-02 regression coverage, nothing else.
- **Fix:** commit `6a1ca2e` adds **only** `tests/test_def011_fs_offload.py` (1575 lines, 45 tests).
- **Purity:** blob `8704a440…`, byte-identical to PR #7's copy of this file; **0** NEW-DEF-03/NAV
  references; imports only `bot.attachments` and `bot.db`.
- **Proof it is a real regression test:** on base `52e7789` without the fix → **32 failures**
  (including T8b); with the fix → **45 passed**.
- **Stability:** 5/5 consecutive runs green.
- **Re-verified by CI:** run `44877192697` on `6a1ca2e` → **3330 passed** on 3.11 and 3.13, all jobs
  success. The +45 delta is the direct proof CI now exercises F-02.

### Out-of-scope findings recorded, not implemented

| ID | Finding | Why not fixed |
|---|---|---|
| D6 | Repeated raw cancellation (second cancel during drain) is still unsafe | Explicitly deferred; task forbids changing D6 |
| NEW-DEF-03 | Watch/unwatch/awaiting work remains unreviewed and unpublished | Separate scope + owner decision |
| NAV-01..06 | Navigation work remains unreviewed and unpublished | `REQUIRES_SEPARATE_OWNER_DECISION` |
| PR #7 | Still bundles mixed scope and was published without a signed grant | Must not be modified by this task |

---

## 7. Phase 6 — Evidence reconciliation

| Dimension | Status | Evidence |
|---|---|---|
| **Source implementation correctness** | **Verified by same-agent review only** | Gate/drain/`_done`/error paths inspected; 3 mutations caught; D6 excluded |
| **Local test verification** | **Pass** | 3329 passed / 1 skipped / 0 failed on 3.11.18 + 3.13.18; 45/45 F-02; 280/280 frontend; pyflakes 0; bandit High 0; pip-audit clean |
| **Actual CI verification** | **Pass on exact commits** | `44874157557` @ `f37a3f5` (3285, 3.11+3.13+frontend) and `44877192697` @ `6a1ca2e` (3330, all jobs) |
| **Independent review** | **NOT ESTABLISHED** | Single host; only sandbox is this session; Copilot review disabled; new Cloud sandbox = cost |
| **Publication state** | **Published, unmerged** | PR #8 open, base `main`; `main` still `52e7789`; PR #7 untouched |
| **Owner acceptance** | **Not given** | No signed grant for this candidate; earlier PR #7 grant was unticked |
| **Deferred limitations** | **Retained** | D6 deferred; NEW-DEF-03/NAV-01..06 open; no exactly-once or atomicity claim |

### Acceptance criteria

| # | Criterion | Status |
|---|---|---|
| 1 | Published candidate matches the verified isolated patch | **MET** — staged diff SHA `75f74a36…` byte-identical |
| 2 | Only isolated F-02 paths committed | **MET** — `attachments.py`, `handlers.py`, plus the F-02 test file only |
| 3 | CI passes on the exact published commit, 3.11 and 3.13 | **MET** — runs `44874157557`, `44877192697` |
| 4 | **A genuine independent review passes** | **NOT MET** — `INDEPENDENCE_NOT_ESTABLISHED` |
| 5 | Critical/high findings resolved and re-reviewed | **PARTIAL** — the one high finding is fixed and CI-reverified; **re-review** is impossible without criterion 4 |
| 6 | Regression tests prove the fix and the negative control | **MET** — 45 tests; fails on base (32); T8b fails when the hunk is reverted; gate/drain mutations caught |
| 7 | No NEW-DEF-03/NAV changes included | **MET** — 0 markers in both commits |
| 8 | D6 explicitly retained as deferred | **MET** — documented in code (916, 966) and in the PR body |
| 9 | Report distinguishes verified facts from limitations | **MET** — §5 and this table |

---

## 8. What is verified vs what is not

**Verified by execution:**
- The published commits contain exactly the isolated F-02 change plus its regression test.
- CI is green on both commits for Python 3.11.18 and 3.13.18, and for the frontend.
- The F-02 suite fails without the fix and passes with it; three independent mutations are caught.
- No NEW-DEF-03/NAV code, schema, Mini App, API, dependency, worker or queue change is present.
- PR #7 and `main` are untouched.

**Not verified:**
- **Independent review.** Same-agent only. This is the blocking gap.
- **Owner acceptance.** Not granted.
- **Production behaviour.** No live Telegram/OpenHands operation was performed (and none was
  authorized).

---

## 9. Next steps

1. **Obtain a genuinely independent review** of `6a1ca2e` in a separate host/filesystem/session —
   the only remaining blocker. The handoff material is
   `docs/reviews/OHB2-WP07-DEF011-F02-ISOLATED-INDEPENDENT-REVIEW-HANDOFF.md`.
2. On a passing independent review, the owner decides whether to merge PR #8. Merging is **not**
   authorized here and was not performed.
3. Keep PR #7 as comparison evidence; resolve its mixed scope separately under an owner decision.
4. Keep D6 deferred; do not treat repeated raw cancellation as safe.
5. WP-07 and DEF-011 remain open regardless of F-02's outcome.
