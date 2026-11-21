# OHB2 — WP-07 — DEF-011 / F-02 — Reviewer Independence Decision

**Task:** `OHB2-WP07-DEF011-F02-ROUTE-D-REVIEWER-INDEPENDENCE-DECISION-AND-EXECUTION-PLAN`
**Date:** 2026-11-21
**Review target:** `6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18` — **re-verified as the exact PR #8 head**
**Type:** documentation only. No workflow, source, test, branch, commit, PR, permission or secret changed.

---

## Verdict

# `F02_OWNER_REVIEW_ONLY`

Execution isolation is genuinely available. **Independent judgment is not.** The only reviewer that
exists is the repository owner, who is also the principal that commissioned the implementation. That is
a real review, but it is **not an independent external review**, and it is not described as one here.

---

## 1. Target re-verification (Phase 1)

The abbreviated SHA was **not** assumed to still be the head.

| Item | Value | Method |
|---|---|---|
| `6a1ca2e` resolves to | `6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18` | `git rev-parse 6a1ca2e` |
| `refs/pull/8/head` | `6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18` | `git fetch origin refs/pull/8/head` |
| Equal? | **YES — still the head** | direct comparison |
| Parent | `f37a3f524ec745f1b5d606161c6ad8b074613a2c` | `git rev-parse pr8^` |
| Merge-base / base | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` | `git merge-base origin/main pr8` |
| `main` | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` — unchanged | `git rev-parse origin/main` |
| PR #8 state | `OPEN`, `mergeable=MERGEABLE`, base `main`, 2 commits, **0 reviews**, **0 review requests** | GitHub API |
| PR #7 | `31dec52289142d0d0dc2bd16604d88644ba3baba` — OPEN, untouched | `git rev-parse pr7` |
| CI on head | run `44877192697` — `pull_request` — **completed / success** | `gh run list --commit` |

**Review target confirmed unchanged.**

### 1.1 Review surface (verified from the real commit)

| Fact | Value |
|---|---|
| Changed files | `bot/attachments.py`, `bot/handlers.py`, `tests/test_def011_fs_offload.py` |
| `bot/handlers.py` hunks | **3** (`import functools`, `from anyio import to_thread`, the `_download_attachment_chunks` swap) |
| F-02 tests | **45** (`grep -c '^def test'` = 45) |
| NEW-DEF-03 / NAV-01..06 markers added | **0** |
| D6 (repeated raw cancellation) | explicitly retained as deferred — `bot/attachments.py:916`, `:966` |

---

## 2. The distinction that decides this task

Two different things are routinely conflated. Only the second one satisfies "independent review".

| Property | What it means | Available here? |
|---|---|---|
| **Execution isolation** | The code runs somewhere other than this pod, on a fresh filesystem, in a separate session | **YES** — GitHub-hosted runner |
| **Judgment independence** | The entity that *decides whether the change is correct* is not the entity that wrote it | **NO** |

A runner that executes instructions written by the implementation agent proves the **first**. It says
nothing about the **second**. Conflating them is exactly the error this task forbids.

---

## 3. Option-by-option evaluation (Phase 2)

### Option A — Human owner review

**Who:** `TM-AEM`, the sole repository collaborator and admin (`permissions: admin, maintain, push, triage, pull`).

**What the owner must inspect:**

1. `bot/handlers.py` — the 3-hunk diff. Does moving `_read_local_capped` into
   `anyio.to_thread.run_sync` actually take blocking disk I/O off the event loop, and is
   `AttachmentTooLargeError` still propagated rather than swallowed by the new wrapper?
2. `bot/attachments.py` — the worker-lifecycle change: the atomic `threading.Lock` gate, `_done` set in
   `finally`, cancellation drain under an outer shield, and `abandoned=True` at the pre-start boundary.
3. `tests/test_def011_fs_offload.py` — whether the 45 tests are **meaningful**, i.e. whether they fail
   when the fix is absent (non-vacuity), and what they do **not** cover.
4. The negative control — that reverting the hunk genuinely breaks `T8b`.
5. Scope — that no schema, Mini App, dependency, API or queue surface moved, and that D6 is still
   explicitly deferred rather than silently claimed fixed.

**What the owner CAN reproduce (verified in this task, not assumed):**

The F-02 suite needs only `pytest`, `anyio`, `httpx` and `python-telegram-bot` — no network, no live
bot, no platform markers. Verified in a clean `python:3.11-slim` container:

```
pip install pytest anyio httpx python-telegram-bot
python -m pytest tests/test_def011_fs_offload.py -q
→ 45 passed
```

With **only** `pytest` + `anyio`, 43 pass and 2 fail (`T8b`, `T8c`) because the bot's runtime imports
are missing — so the four-package set is the true minimum, and it is Termux-feasible.

**Negative control, verified in this task:**

```
# fix present → 45 passed
# hunk reverted → FAILED test_T8b_local_capped_read_runs_off_event_loop_thread (1 failed, 1 passed)
```

`T8b` genuinely discriminates the fix. `T8c` correctly still passes, because it tests the byte cap,
not the offload — a useful signal that the tests are not all testing the same thing.

**What the owner CANNOT verify from the tablet:**

- A full-suite run comparable to CI (3330 tests, both Python 3.11 and 3.13) — heavy for Termux, and
  AGENTS.md warns against long local runs;
- `git`-dependent tests (`tests/test_autopush_*`) without a working `git` on PATH;
- Anything requiring the real Telegram API or the OpenHands API — and those are out of scope anyway;
- True environment separation: the owner's device is not a second host in any meaningful sense, and
  the owner is the same person.

**Why this is an owner review, not an independent external review:**

The owner commissioned the work, set the acceptance criteria, and is the sole principal able to approve
or reject it. When the person who asked for the change is also the person who signs it off, the
judgment is **accountable but not independent**. No amount of tooling changes that. This document does
not label it independent.

**Verdict on A: AVAILABLE, ZERO COST, but NOT independent.**

---

### Option B — Second human collaborator

| Probe | Result |
|---|---|
| `GET /collaborators` | exactly one: `TM-AEM`, role `admin` |
| Pending invitations | `403 Resource not accessible by integration` (token cannot list them) |
| Repository forks | **0** |
| Stargazers / watchers | 1 / 0 |
| Distinct actors in repository events (last 50) | `["TM-AEM"]` only |
| `requested_reviewers` on PR #8 | **0** |

**No second human with access exists.** GitHub only permits requesting review from a user who already
has read access, so obtaining one requires **adding a collaborator** — a permission change, which this
task forbids and which would also be an owner decision (a trust decision, not a technical one).

Note the visibility question the task raises: the repository is already **public**, so no visibility
change would be needed to let an outsider *read* it. But reading a public repository is not the same as
being a designated reviewer, and a volunteer from the public internet has no accountability, no
verifiable identity bound to the project, and no obligation to report. That is not a review process.

**Verdict on B: NOT AVAILABLE without a permission change (forbidden here).**

---

### Option C — Existing automated reviewer

Each candidate was **re-probed in this task** rather than taken on trust.

| Candidate | Fresh probe | Qualified? |
|---|---|---|
| **GitHub Models** | Live docs: *"As of July 30, 2026, GitHub Models has been fully retired. The playground, model catalog, inference API, and bring your own key (BYOK) are no longer available to any customer."* | **NO — service retired** |
| **Copilot code review** | `GET /user/copilot` → **404**; `plan: None`; 0 reviews on PR #8; `requested_reviewers: []` | **NO — no entitlement (paid)** |
| **GitHub Apps** | `GET /repos/…/installation` → `401 A JSON web token could not be decoded`; no app activity in events | **NO — none installed** |
| **NVIDIA inference API** | `GET /v1/models` → 200 (33 models). `POST /v1/chat/completions`: one model returned a **genuine** completion (`minimax-m3.1-flash` → `"HELLO"`), but every substantive review attempt returned **HTTP 529 Service temporarily overloaded** — 4 retries with backoff, then a 45-second wait and 2 more, all 529; other models → 404 `Not found for account` | **NO — unreliable, and needs a new secret** |

On the NVIDIA candidate specifically, to be fair rather than dismissive: the endpoint is real and it
did produce one correct short answer. But it could **not** produce a review of the actual F-02 diff —
seven consecutive attempts on real content failed with 529. Even if it had, it would have required
adding `NVIDIA_API_KEY` as a repository secret, which this task forbids. An intermittent endpoint that
fails on exactly the workload in question is not a reviewer.

**Qualification bar applied:** an automated reviewer qualifies only if it *actually generates a
substantive technical assessment of the exact diff*, not merely executes tests or replays a checklist.
No candidate cleared that bar.

**Verdict on C: NO QUALIFIED AUTOMATED REVIEWER AVAILABLE.**

---

### Option D — GitHub-hosted runner plus separately authored review

This is the design validated in the previous task
(`docs/audits/…ROUTE-D-WORKFLOW-DESIGN.md`, `docs/reviews/…ROUTE-D-WORKFLOW-VALIDATION-REPORT.md`).
It must be assessed on four separate axes, not one:

| Axis | Status | Evidence |
|---|---|---|
| **Host independence** | **PROVEN** | GitHub-hosted runner. This repo's own CI logs record `Runner Image Provisioner`, `Hosted Compute Agent`, `Image: ubuntu-26.04`, `Version: 20261116.202.1` — a provisioned VM, not this pod (`runtime-hjffxzvtsqfkfugy-566946795b-cjkbr`) |
| **Session / filesystem independence** | **PROVEN** | fresh checkout, ephemeral process, nothing shared with this container |
| **Reviewer identity independence** | **NOT ESTABLISHED** | the workflow has no reviewer identity; it has an executor identity (the runner) and an author identity (the implementation agent) |
| **Independence of technical reasoning** | **NOT ESTABLISHED** | the workflow contains no reasoning step. It emits an evidence artifact and an empty findings template |

**Why this does not count as fully independent:** a runner executing instructions written by the
implementation agent proves **execution isolation only**. The judgment would still be authored by
whoever reads the artifact — and the only reader available is the implementation agent or the owner.

The workflow was deliberately built this way (it states *"You may reject this change even though every
test above passed"*, and ships a blank findings table), precisely so that it would never be mistaken for
a reviewer. That design choice is vindicated by this evaluation: no reviewer exists to consume it.

**Verdict on D: EXECUTION ISOLATION ONLY — not independent judgment.**

---

## 4. Decision table (Phase 4)

| Dimension | Evidence required | A — Owner | B — Collaborator | C — Automated | D — Runner |
|---|---|---|---|---|---|
| **Host separation** | different physical/virtual host | ✗ same device | ✓ would be | — n/a | ✓ **GitHub-hosted VM** |
| **Filesystem separation** | separate filesystem | ✗ | ✓ | — | ✓ fresh checkout |
| **Session separation** | separate execution context | ✗ same person/session | ✓ | — | ✓ ephemeral process |
| **Reviewer identity** | distinct reviewer identity | ✗ same principal | ✓ distinct human | ✗ none exists | ✗ no identity at all |
| **Judgment independence** | reviewer generates own assessment | ✗ accountable, not independent | ✓ | ✗ no qualified service | ✗ no reasoning step |
| **Cost** | no payment / paid trial | ✓ 0 | ✓ 0 | ✗ Copilot paid; NVIDIA needs secret | ✓ 0 (public repo) |
| **Authorization** | existing permission or identified grant | ✓ owner already has it | ✗ **needs add-collaborator grant** | ✗ needs subscription / secret | ✓ already available |

**Reading the table:** no column has five checks. Only Option B and Option C could supply reviewer
identity and judgment independence, and both require something forbidden here (a permission change, a
paid subscription, or a new secret).

---

## 5. Recommended route

**Recommendation: Option A (owner review), explicitly labelled as an owner review — combined with
Option D as the evidence engine.**

This is the strongest route that is **already available, zero-cost, and compliant with AGENTS.md**:

1. **Route D collects the evidence** on a genuinely separate host, pinned to `6a1ca2e`, with the scope
   guards and negative control already validated. This is worth doing even though it is not a review:
   it produces an artifact nobody can dispute was generated outside this environment.
2. **The owner performs the judgment** against the review contract in §6, using the artifact plus the
   locally reproducible commands verified in §3-Option A.
3. The report **states plainly that this is an owner review**, and does not claim external independence.

**Explicit statement: no fully independent reviewer is available.** I am not redefining independence
to make the task look complete. The verdict is `F02_OWNER_REVIEW_ONLY`.

### 5.1 What would upgrade the verdict, and what each costs

| Upgrade | What it needs | Forbidden here? |
|---|---|---|
| → `F02_HUMAN_INDEPENDENT_REVIEWER_AVAILABLE` | add a trusted second human with read access | **YES** (permission change) — owner decision |
| → `F02_AUTOMATED_INDEPENDENT_REVIEWER_AVAILABLE` | a working, non-retired review service + a repository secret | **YES** (secret) — owner decision |

Both are **owner decisions**, not engineering tasks. Neither is proposed as something I can do.

---

## 6. Minimum acceptable review contract (Phase 3)

Any reviewer — owner or otherwise — must satisfy all ten points. This contract is what makes an owner
review *rigorous* even though it is not independent.

1. **Inspect the entire exact commit diff** `52e7789..6a1ca2e`, not a summary and not only `handlers.py`.
2. **Analyse cancellation and worker-lifecycle behaviour independently** — the atomic `threading.Lock`
   gate, `_done` in `finally`, the drain under an outer shield, `abandoned=True` at the pre-start
   boundary, and what a raw `Task.cancel()` at each boundary leaves behind.
3. **Inspect the 45 F-02 regression tests and the negative controls** — and judge whether they are
   *meaningful*, i.e. whether each would fail if its target defect returned.
4. **Evaluate race conditions, error handling and failure propagation** — specifically that
   `AttachmentTooLargeError` and `OSError` re-raise rather than being masked by the new
   `to_thread.run_sync` wrapper.
5. **Check that `bot/handlers.py` contains only the F-02 hunk** — exactly 3 regions: `import functools`,
   `from anyio import to_thread`, and the `_download_attachment_chunks` swap.
6. **Verify no NEW-DEF-03 / NAV-01..06 changes are included** — verified here as **0 markers**, but the
   reviewer must confirm it independently.
7. **Identify missing tests and untested edge cases** — D6 (repeated raw cancellation) is declared out
   of scope; the reviewer should say whether that exclusion is acceptable and what else is uncovered.
8. **Run the relevant tests independently when possible** — minimum verified set:
   `pip install pytest anyio httpx python-telegram-bot` then
   `python -m pytest tests/test_def011_fs_offload.py -q` → expect 45 passed.
9. **Report findings with severity, file/line references and reproducible evidence** — a finding with no
   reproduction is not a finding.
10. **Issue its own verdict, including the possibility of rejection.**

**Prohibited instructions.** The reviewer must **not** be told to produce PASS, must **not** be given the
implementation agent's conclusion as a target, and must **not** be handed a pre-filled findings table.
The existing workflow already complies: its instructions say *"Form your own judgment. Nothing in this
artifact asserts that the change is correct, and a green test run is not a review… You may reject this
change even though every test above passed."*

---

## 7. Required owner decisions

| # | Decision | Blocks what |
|---|---|---|
| **1** | **Accept owner review as the F-02 judgment**, with the report labelled `OWNER_REVIEW` rather than `INDEPENDENT_REVIEW` | F-02 closure |
| 2 | Authorize adding `.github/workflows/f02-review.yml` (branch + commit + push) so Route D can run | Evidence generation |
| 3 | Where findings land — artifact only (current), PR comment (`pull-requests: write`), or committed report (push) | Reporting |
| 4 | Accept `workflow_dispatch` as a new trigger style (`ci.yml` has none) | Workflow approval |
| 5 | Optional: authorize a second human collaborator **or** a review-service secret, if true independence is required | Upgrading the verdict |

Decision 1 is the one that actually unblocks F-02. Decisions 2–4 are mechanical. Decision 5 is only
needed if the owner rejects owner-review as sufficient.

---

## 8. Limitations — stated plainly

- **No independent reviewer exists in this environment.** Not a tooling gap; a structural one.
- **Option A is accountable, not independent.** The owner wrote the requirements and approves the
  result.
- **Option D proves execution isolation only.** A runner executing my instructions is not a reviewer.
- **The NVIDIA endpoint is unreliable** (529 on real workloads) *and* would need a new secret. It is not
  offered as a solution.
- **GitHub Models is retired** — re-confirmed from live documentation in this task, not from memory.
- **Copilot review is unavailable** — re-confirmed (404, no plan).
- **F-02 remains open.** This document decides *who judges*, not *whether the change is correct*.
- No workflow, source, test, branch, commit, PR, permission, secret or repository setting was changed.

---

## 9. Next steps (Phase 5)

Because **no qualified independent reviewer exists**, this is the owner decision brief rather than an
execution plan for a review run. The full readiness assessment, including the exact sequence that would
follow each decision, is in
`docs/reviews/OHB2-WP07-DEF011-F02-ROUTE-D-EXECUTION-READINESS-REPORT.md`.

Short form:

1. Owner decides on decision 1 (§7). If accepted → proceed to step 2.
2. Owner authorizes the workflow file (decision 2) — a branch off `6a1ca2e`, one added file, one commit,
   one push. No application source is touched.
3. `gh workflow run f02-review.yml -f head_sha=6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18`.
4. Owner downloads the artifact and applies the §6 contract.
5. Findings are recorded; if any are blocking, they are fixed and CI **and** the review are re-run.
6. Only then may F-02 be considered for closure — and the closure report must say `OWNER_REVIEW`.
