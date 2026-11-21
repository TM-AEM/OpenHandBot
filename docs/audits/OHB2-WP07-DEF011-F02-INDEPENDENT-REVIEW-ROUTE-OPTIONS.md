# OHB2 — WP-07 — DEF-011 / F-02 — Independent Review Route Options

**Task:** `OHB2-WP07-DEF011-F02-INDEPENDENT-REVIEW-ROUTE-DISCOVERY`
**Date:** 2026-11-21
**Mode:** read-only discovery. No source, test, workflow, branch, commit, PR or setting was changed.

This document is the raw option inventory: every route examined, what it actually is, and why it
qualifies or fails. The qualification verdict is in
`docs/reviews/OHB2-WP07-DEF011-F02-INDEPENDENT-REVIEW-ROUTE-QUALIFICATION-REPORT.md`.

---

## 0. What "independent" means here, and what it excludes

Required by the task: a **separate host**, a **separate filesystem**, and a **separate session**, able
to inspect the exact published commit, run tests, and report findings without modifying the repository.

Explicitly **not** independent — verified as same-host in this environment:

| Thing | Why it fails |
|---|---|
| A second directory or `git clone` | same kernel, same disk, same session |
| A second shell / process / container on this pod | containers share this host's kernel and disk |
| A second agent or conversation on this host | same machine, same filesystem |
| `work-1` vs `work-2` hostnames | **both resolve to `34.27.211.76`** — one pod, two ports (§2) |

---

## 1. The review target (Phase 1, verified against live remote state)

| Item | Verified value | How |
|---|---|---|
| PR #8 | **OPEN**, base `main`, `mergeable=MERGEABLE`, 2 commits | `gh pr view 8` |
| PR #8 head | **`6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18`** | `refs/pull/8/head` **and** API — agree |
| Is `6a1ca2e` the head or an ancestor? | **It IS the head** (not merely an ancestor) | `git rev-parse pr8head` == `6a1ca2e`; `merge-base --is-ancestor` true |
| Parent of `6a1ca2e` | `f37a3f524ec745f1b5d606161c6ad8b074613a2c` | `git rev-parse 6a1ca2e^` |
| Parent of `f37a3f5` (i.e. merge base) | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` = `origin/main` | `git rev-parse origin/main` |
| Changed files vs `52e7789` | `bot/attachments.py`, `bot/handlers.py`, `tests/test_def011_fs_offload.py` | `git diff --stat` |
| Diff size | 3 files, **+2025 / −105** | `git diff --stat` |
| Full diff SHA-256 | `cb3da6526d536dddf1eca23ba1d8b94a01b86aaf360507838d0eb10c81b02ab0` | `git diff 52e7789 6a1ca2e \| sha256sum` |
| **Code-only diff SHA-256** | **`75f74a3661a070ba4034d8a125d45d31710d3e911805c7ae374e8e7541c5ae26`** | `git diff … -- bot/` — **matches the verified patch** |
| CI runs | **`44874157557`** @ `f37a3f5` → success; **`44877192697`** @ `6a1ca2e` → success | `gh run list` |
| PR #7 | **OPEN, unmerged, untouched** — head `31dec52…`, `updated_at` 2026-11-20 | `gh pr view 7` |
| `main` | unchanged, `52e7789` | `git ls-remote` |

Scope facts re-verified on the published commit (for the handoff, §5 of the qualification report):

| Check | Result |
|---|---|
| Tests in `tests/test_def011_fs_offload.py` | **45** (`grep -c "^def test"`) |
| `handlers.py` hunk regions | **3** (`grep -c "^@@"`) |
| NEW-DEF-03 / NAV-01..06 added lines | **0** |
| Schema / migration / Mini App / requirements / pyproject touched | **NONE** |

> **Stale-document defect found:** the existing handoff
> `docs/reviews/OHB2-WP07-DEF011-F02-ISOLATED-INDEPENDENT-REVIEW-HANDOFF.md` still states
> "**It is not: it has no CI run**" (§7) and "`tests/test_def011_fs_offload.py` is **not** in the patch"
> (§5.2, §6). Both became false after PR #8 was published. A reviewer following it would be misled.
> Recorded, not silently corrected — the fix is a documentation change outside this task's outputs.

---

## 2. Route A — "second work host" (`work-1` / `work-2`)

**Claimed by environment context:** two hosts, ports 12000 and 12001.

**Actual:**

```
work-1-hjffxzvtsqfkfugy.prod-runtime.all-hands.dev -> 34.27.211.76
work-2-hjffxzvtsqfkfugy.prod-runtime.all-hands.dev -> 34.27.211.76   <-- SAME IP
this pod: runtime-hjffxzvtsqfkfugy-566946795b-cjkbr
my egress IP: 35.222.133.153
curl https://work-1-…/ -> HTTP 502 (nothing listening locally)
```

Both names are ingress routes to **this same pod**, differing only by port. There is no second
machine behind them.

| Criterion | Result |
|---|---|
| Available now | Yes, but it is this host |
| Different host | **No** |
| Separate filesystem | **No** |
| Independent session | **No** |
| **Verdict** | **REJECTED — same host, different port** |

---

## 3. Route B — A new OpenHands Cloud sandbox

**Mechanism:** `POST /api/v1/app-conversations` creates a sandbox that is a genuinely separate
container/host with its own filesystem and its own agent session. This would satisfy host + filesystem
+ session separation, and it can clone the repo, run the suite, and report.

**Actual state:**

| Probe | Result |
|---|---|
| Cloud API reachable | Yes — `GET /api/v1/users/me` → 200 |
| Existing sandboxes | 10 total; **1 RUNNING** = `1lKbI4WbA2VdFqzkEoxUQw` |
| Owner of the RUNNING sandbox | **this conversation** `6715bb35bff4420d9802ed649c3cc2ea` |
| Any *other* already-running, free sandbox | **No** (the rest are `PAUSED`/`MISSING`) |
| Account role / plan | `role=owner`; `max_budget_per_task=None`; no credits field exposed |
| Cost to start a **new** sandbox | **Billable compute** |

A new sandbox is a new billable environment. AGENTS.md §9 lists "spending money" as an explicit
stop-and-ask condition, and this task forbids "purchasing credits, starting a paid trial, or creating a
billable environment". Resuming a `PAUSED` sandbox would also consume compute and would still be a
resource this task may not consume.

| Criterion | Result |
|---|---|
| Available now | Technically yes |
| Different host / filesystem / session | **Yes** — genuinely separate |
| Zero cost | **No** — new or resumed sandbox is billable |
| **Verdict** | **REJECTED for this task — billable.** This is the strongest *technical* route, but it
requires owner spend authorization |

---

## 4. Route C — GitHub Copilot code review

**Mechanism:** GitHub-native AI reviewer, requestable as `copilot-pull-request-reviewer[bot]`.

**Actual state (probed directly, not from documentation):**

| Probe | Result |
|---|---|
| `POST /pulls/8/requested_reviewers` with the Copilot bot | HTTP **200**, but `requested_reviewers` comes back **`[]`** — the request silently no-ops |
| `GET /pulls/8/reviews` | **0** reviews |
| `pr view 8 --json reviewRequests` | **0** review requests |
| Account plan | `TM-AEM` is a **User** (personal account), `plan=None` |
| `GET /user/copilot` | **404** — no Copilot entitlement |
| Any bot ever active on the repo | **No** — repo events show actor `TM-AEM` only |

Copilot code review requires a paid Copilot plan. This account has none, so the route is not merely
disabled — it is **not purchasable within a zero-cost constraint**.

| Criterion | Result |
|---|---|
| Available now | **No** |
| Zero cost | **No** — requires a Copilot subscription |
| **Verdict** | **REJECTED — requires a paid subscription** |

---

## 5. Route D — GitHub-hosted Actions runner as the reviewer host

This is the only route that plausibly satisfies **host + filesystem + session** separation at
**zero cost**, so it is examined in the most detail.

**Established facts:**

| Fact | Evidence |
|---|---|
| Runners are **genuinely separate machines** | CI logs show `##[group]Runner Image Provisioner`, `Hosted Compute Agent`, `Image: ubuntu-26.04`, `Version: 20261116.202.1` — a provisioned GitHub-hosted VM, not this pod |
| Cost for this repo | **Zero** — repo is **public**, so standard GitHub-hosted runners are free |
| Filesystem | Fresh VM checkout per job — separate |
| Session | Separate ephemeral runner process — separate |
| Can access the exact commit | Yes — `actions/checkout` at `6a1ca2e` |
| Can run tests | Yes — the existing CI job already does exactly this |
| Can be triggered **without** workflow changes | **No** |

**The blocking detail — what existing workflows can actually do:**

| Workflow | Triggers | What it does |
|---|---|---|
| `.github/workflows/ci.yml` | `push: [main]`, `pull_request: [main]` — **no `workflow_dispatch`** | pyflakes, pip-audit, bandit, `pytest`, `node --test`. **Deterministic tooling only.** |
| `.github/workflows/enzonic-sftp-readonly-check.yml` | `workflow_dispatch` | SFTP connectivity check. Does not read or judge source. |

Therefore:

- `ci.yml` **cannot be dispatched** (no `workflow_dispatch`), so it cannot be invoked on demand.
- Neither workflow contains any step that forms a **technical judgment**. A green run is
  *test execution*, not a *code review* — the task states this distinction explicitly.
- Using a runner as a **reviewer** would require adding a workflow (or a review job/step) — i.e. a
  **workflow modification and an additional commit**.

**A zero-secret enabler exists and was verified:** `POST https://models.github.ai/inference/chat/completions`
with the **existing `GITHUB_TOKEN`** returns **HTTP 200** (`openai/gpt-4o-mini` replied). So a
runner-hosted reviewer could reason about the diff **without adding any secret**. This removes the
"needs a new secret" objection — but not the "needs a workflow change" objection.

| Criterion | Result |
|---|---|
| Different host / filesystem / session | **Yes** — verifiable from the runner image log |
| Zero cost | **Yes** (public repo; GitHub Models on the built-in token) |
| Can inspect the exact commit and run tests | **Yes** |
| Read-only, findings-only | Achievable by design (review job posts a report; no push) |
| Requires workflow change / extra commit | **YES** |
| **Verdict** | **BEST AVAILABLE ROUTE — but REQUIRES SEPARATE OWNER AUTHORIZATION.** Not performed. |

### Caveat that must not be glossed over

Even on a separate runner, if the review prompt, checklist and diff selection are authored by **me**,
the *judgment* is not independent in the strongest sense — only the *execution host* is. That is a
real and honest limitation: host/fs/session separation is verifiable; **reviewer-author independence
is weaker** and must be disclosed to the owner, who may prefer a human or an externally-run reviewer.

---

## 6. Route E — Human reviewer (the owner) on their own device

**Mechanism:** `TM-AEM` reviews the diff on their own tablet/device, outside this pod.

| Criterion | Result |
|---|---|
| Different host / filesystem / session | **Yes** — their own device |
| Zero cost | **Yes** |
| Can inspect the exact commit and full diff | **Yes** |
| Can run the test suite | **Limited** — AGENTS.md records an Android/Termux environment with no PC; the full suite needs Python + Node deps |
| Requires workflow change / new secret | **No** |
| Independence of principal | **Weak** — same principal on whose behalf the agent works; not a third party |
| **Verdict** | **VIABLE as a human sign-off, WEAK on test execution and principal-independence.** Not a substitute for an independent technical review with executed evidence |

Note: `gh api repos/…/collaborators` returns exactly **one** collaborator, `TM-AEM` (admin). There is
no second human with repo access who could serve as an outside reviewer without being added — and
adding one would be a permission change, which this task forbids.

---

## 7. Route F — Other CI/review providers

| Route | Status |
|---|---|
| GitLab CI / Azure Pipelines / CircleCI / Jenkins / Travis / Drone / Buildkite configs in repo | **None** — `git ls-tree` finds no such files |
| Self-hosted GitHub runners | **Cannot verify** — `GET /actions/runners` → **403** (token lacks admin scope). No evidence any exist |
| Actions secrets/variables | **Cannot verify** — `GET /actions/secrets` and `/actions/variables` → **403** |
| Pre-provisioned remote machine (SSH) | **None** — no `~/.ssh`, no SSH config |
| Cloud CLIs to provision a free VM | **None** — no `gcloud`, `aws`, `az`, `doctl`, `flyctl` |
| Any installed AI review App | **None** — no bot actor in repo events |

---

## 8. Summary matrix

| Route | Different host | Separate FS | Independent session | Exact commit | Runs tests | Zero cost | Workflow change | Verdict |
|---|---|---|---|---|---|---|---|---|
| A. `work-1`/`work-2` | ✗ | ✗ | ✗ | — | — | ✓ | — | **Rejected — same pod** |
| B. New Cloud sandbox | ✓ | ✓ | ✓ | ✓ | ✓ | **✗ billable** | no | **Rejected — costs money** |
| C. Copilot code review | ✓ | ✓ | ✓ | ✓ | ✓ | **✗ paid plan** | no | **Rejected — paid** |
| D. **Actions runner reviewer** | **✓** | **✓** | **✓** | **✓** | **✓** | **✓** | **YES** | **Best route — needs owner authorization** |
| E. Owner human review | ✓ | ✓ | ✓ | ✓ | limited | ✓ | no | Weak — no executed evidence, same principal |
| F. Other providers | ✗ none available | — | — | — | — | — | — | **Not present** |

---

## 9. Route prohibited by AGENTS.md (recorded, not used)

Running the review in a container on **this** pod (`docker run …`) is what the previous task did. It
gives a separate filesystem *view* and a separate process, but shares the host kernel, disk and
session. AGENTS.md and the task definition both exclude it. It was **not** used as an independence
claim, and must not be counted as one.
