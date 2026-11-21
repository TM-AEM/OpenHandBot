# OHB2 — WP-07 — DEF-011 / F-02 — Independent Review Route Qualification Report

**Task:** `OHB2-WP07-DEF011-F02-INDEPENDENT-REVIEW-ROUTE-DISCOVERY`
**Date:** 2026-11-21
**Target:** PR **#8**, head **`6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18`**
**Mode:** read-only discovery, documentation-only output.

---

## Final verdict

# `F02_REVIEW_ROUTE_REQUIRES_OWNER_AUTHORIZATION`

A route **does** exist that satisfies host, filesystem and session separation at zero cost, and it was
**empirically verified** rather than assumed. It is **not usable in this task** because it requires a
workflow change plus an extra commit — both forbidden here without a separate owner decision.

**F-02 remains open and blocked.** This report does **not** close it and does **not** contain a review.

---

## 1. Does a genuinely independent zero-cost route exist?

**Yes — one, conditionally.** A GitHub-hosted Actions runner is a real, separate machine
(`Hosted Compute Agent`, `Image: ubuntu-26.04`, `Version: 20261116.202.1` — from the actual CI logs, not
vendor claims), it is free for this public repo, it can check out `6a1ca2e`, run the full suite, and
report findings read-only. It requires **one** thing this task may not do: a workflow change and an
additional commit.

The only other technically-separate routes are a new OpenHands Cloud sandbox (**billable**) and Copilot
code review (**paid plan, absent**).

## 2. Which route is best, and why

**Route D — a reviewer job on a GitHub-hosted runner.** Reasons:

1. It is the **only** route that is simultaneously separate-host, separate-filesystem,
   separate-session, exact-commit-capable, test-capable, and zero-cost.
2. Separation is **verifiable from evidence already collected** — the CI logs name a provisioned
   runner image, not this pod.
3. No new secret is needed: `models.github.ai/inference` accepted the **existing `GITHUB_TOKEN`**
   (verified, HTTP 200), so the reviewer can reason over the diff without adding credentials.
4. It can be made **findings-only**: the job prints/posts a report and performs no push, no merge and
   no settings change.

Rejected alternatives, with the decisive reason:

| Route | Decisive reason for rejection |
|---|---|
| `work-1` / `work-2` | **Both resolve to `34.27.211.76`** — one pod, two ports. No separation at all |
| New Cloud sandbox | Billable compute; AGENTS.md §9 stop-and-ask; task forbids billable environments |
| Copilot code review | Request returns `200` but `requested_reviewers: []`; `GET /user/copilot` → **404**; account has no paid plan |
| Container on this pod | Shares host kernel/disk/session — explicitly not independent |
| Owner human review | Zero cost and separate host, but **no executed test evidence** and same principal |

## 3. Exact prerequisites that remain

To proceed on Route D, the owner must authorize **all** of the following (each is currently forbidden):

1. **A workflow change** — add a review job to `.github/workflows/ci.yml` or a new workflow file.
   `ci.yml` has **no `workflow_dispatch`**, so it cannot even be invoked on demand today.
2. **An additional commit** to the PR branch to carry that workflow change (this task forbids
   commits and pushes).
3. **A decision on who authors the review prompt/checklist.** If the agent authors it, only the
   *execution host* is independent — the *judgment* is not. This must be an explicit owner choice, not
   a silent assumption.
4. **A decision on where findings go** — a PR comment, an uploaded artifact, or a committed report.
   Commenting is read-only with respect to source; committing a report is not.
5. Optional: confirm whether any **self-hosted runner** exists. It could not be checked —
   `GET /actions/runners` → **403** with the current token.

## 4. Does the route comply with AGENTS.md?

The **route itself** complies: read-only with respect to source, no secrets added, no visibility
change, no destructive operation, no new paid environment, no architecture change.

**Using it in this task would not comply**, because AGENTS.md forbids pushing commits and modifying
workflows without explicit authorization, and this task additionally forbids branches, commits, pushes
and workflow changes. That is precisely why the verdict is "requires owner authorization" rather than
"qualified".

## 5. Is owner authorization required?

**Yes.** Route D cannot be enabled without an owner decision covering: workflow modification, an extra
commit/push to the PR branch, and the reviewer-authorship question in §3.3.

Spend authorization is **not** required for Route D. It would be required for Route B (Cloud sandbox)
and a Copilot subscription for Route C — both recommended against, since Route D is free.

## 6. Does F-02 remain blocked?

**Yes.** F-02 remains open. Nothing in this task produced a review of `6a1ca2e`; no independent
judgment of the F-02 implementation exists. **F-02 is not closed**, and WP-07 / DEF-011 remain open.

---

## 7. Review scope to hand off (Phase 5)

The eventual independent reviewer must cover all twelve points. Each is paired with the verified
location so the reviewer can check it directly rather than trust the summary.

| # | Required focus | Where to look | Verified state |
|---|---|---|---|
| 1 | F-02 cancellation lifecycle and worker-start gate | `bot/attachments.py` — `store_async`, `_gate`/`_state`/`_done`/`_box` | present |
| 2 | Mutual exclusion between caller and worker | same; `_gate = threading.Lock()` guards both `started` and `abandoned` | present |
| 3 | Unconditional worker completion signalling | `_worker`'s `finally: _done.set()` | present |
| 4 | AnyIO cancellation and drain behaviour | `except anyio.get_cancelled_exc_class()` → `_needs_drain` → `CancelScope(shield=True)` + `_done.wait` | present |
| 5 | Raw `asyncio.Task.cancel()` at the pre-start boundary | the `_state["abandoned"] = True` branch | present |
| 6 | The 45 regression tests and their negative controls | `tests/test_def011_fs_offload.py` — **45** `def test` confirmed | present |
| 7 | Mutation-test evidence | prior report §5; must be **re-run by the reviewer**, not accepted | claimed only |
| 8 | Error propagation and fail-closed behaviour | `_box["error"]` re-raise; `BaseException` capture | present |
| 9 | The exact `handlers.py` F-02-only hunk | **3** `@@` regions: `functools`, `to_thread`, `_download_attachment_chunks` | present |
| 10 | Absence of NEW-DEF-03 / NAV-01..06 | whole diff — **0** matching added lines | confirmed |
| 11 | No schema / Mini App / API / architecture / dependency / worker / queue change | changed-file list is exactly 3 paths; **NONE** of those categories | confirmed |
| 12 | D6 limitations and the explicit scope boundary | `bot/attachments.py` lines ~916 and ~966 — repeated raw cancellation excluded | present |

### Exact review target and reproduction

```
base    52e7789cc8cc97a7f7c09c9592226ab117db99a2   (= origin/main)
parent  f37a3f524ec745f1b5d606161c6ad8b074613a2c
head    6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18   (= refs/pull/8/head, PR #8 head)
files   bot/attachments.py  bot/handlers.py  tests/test_def011_fs_offload.py
diff    3 files, +2025 / -105
sha256  full diff   cb3da6526d536dddf1eca23ba1d8b94a01b86aaf360507838d0eb10c81b02ab0
sha256  code only   75f74a3661a070ba4034d8a125d45d31710d3e911805c7ae374e8e7541c5ae26
CI      44874157557 @ f37a3f5 -> success
        44877192697 @ 6a1ca2e -> success (3330 passed, 3.11 + 3.13)
```

```bash
git clone https://github.com/TM-AEM/OpenHandBot.git f02-review
cd f02-review && git checkout 6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18
git diff --stat 52e7789..HEAD          # expect 3 files, +2025 / -105
sha256sum tests/test_def011_fs_offload.py
pip install -r requirements-dev.txt
python -m pytest -q                    # expect 3330 passed
python -m pytest tests/test_def011_fs_offload.py -q   # expect 45 passed
```

Negative control the reviewer **must** run independently: revert the `handlers.py` hunk to `52e7789`
and confirm `pytest tests/test_def011_fs_offload.py -k T8b` **fails**.

### Constraints on the reviewer

- Findings only. **No** edits, commits, pushes, merges, or repository-setting changes.
- Run the tests in the qualified environment and report **reproducible** findings with file/line refs.
- Must not claim exactly-once Telegram delivery or SQLite-Telegram atomicity on behalf of this change.

### Materials to include in the read-only package

| Item | Path |
|---|---|
| Full diff | `git diff 52e7789 6a1ca2e` (hash above) |
| Verified patch | `docs/reviews/OHB2-WP07-DEF011-F02-ISOLATED-CANDIDATE.patch` |
| Candidate report | `docs/audits/OHB2-WP07-DEF011-F02-ISOLATED-CANDIDATE-REPORT.md` |
| Manifest | `docs/reviews/OHB2-WP07-DEF011-F02-ISOLATED-CANDIDATE-MANIFEST.md` |
| Prior closure report | `docs/reviews/OHB2-WP07-DEF011-F02-ISOLATED-FINAL-CLOSURE-REPORT.md` |
| Original handoff | `docs/reviews/OHB2-WP07-DEF011-F02-ISOLATED-INDEPENDENT-REVIEW-HANDOFF.md` — **stale, see §8** |

---

## 8. Defects found in existing documentation (reported, not fixed)

The original handoff is **stale** in two places that would mislead a reviewer:

| Location | Statement | Reality now |
|---|---|---|
| §7 "What you must not accept" | "That this candidate is build-verified. **It is not: it has no CI run.**" | CI **now exists and passed** on both commits (`44874157557`, `44877192697`) |
| §5.2 and §6 | "`tests/test_def011_fs_offload.py` is **not** in the patch" | It **is** committed in `6a1ca2e` |

Correcting those files is a documentation change outside this task's two permitted outputs, so it was
left alone and reported here instead.

---

## 9. Evidence proving separation (and its limit)

| Claim | Evidence |
|---|---|
| CI runners are separate machines | CI log: `##[group]Runner Image Provisioner`, `Hosted Compute Agent`, `Image: ubuntu-26.04`, `Version: 20261116.202.1` |
| This pod is not a runner | pod hostname `runtime-hjffxzvtsqfkfugy-566946795b-cjkbr`; egress `35.222.133.153` |
| `work-1`/`work-2` are not separate hosts | both resolve to `34.27.211.76`; `work-1` returns HTTP 502 locally |
| The RUNNING cloud sandbox is this session | sandbox `1lKbI4WbA2VdFqzkEoxUQw` ↔ conversation `6715bb35…` (this task) |
| Copilot review is unavailable | `requested_reviewers` → `[]`; `GET /user/copilot` → **404** |
| No AI review bot is installed | repo events: actors = `["TM-AEM"]` only |
| GitHub Models works with the existing token | `POST models.github.ai/inference/chat/completions` → **200** |

**Limit — stated plainly:** all of the above proves **host/filesystem/session** separation for Route D.
It does **not** prove *reviewer-author* independence, because the same agent would author the review
prompt and the checklist. Anyone claiming a fully independent review must address that separately.

---

## 10. Exact next action

**One item, for the owner:**

> Authorize, or refuse, Route D: a findings-only reviewer job on a GitHub-hosted runner for
> `6a1ca2e`, which requires (a) a workflow change, (b) one extra commit/push to the PR #8 branch, and
> (c) a decision on whether the agent may author the review prompt.

Until that decision, F-02 stays blocked and no review exists.

If the owner refuses Route D, the remaining honest options are: the owner performs the review
themselves (weak on executed evidence), or F-02 stays open indefinitely.

---

## 11. Compliance statement

- No source, test, workflow, branch, commit, PR, setting, secret or visibility change was made.
- PR #8 head is still `6a1ca2e`; PR #7 is still `31dec52…`; `main` is still `52e7789`.
- The working tree keeps its 8 pre-existing modifications; `.agent/` and `.openhands/` were untouched
  except for appending memory notes.
- Two new untracked documentation files were added, as the task requires.
- No paid resource was created, resumed, or started.
