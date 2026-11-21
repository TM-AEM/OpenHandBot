# OHB2 — WP-07 — DEF-011 / F-02 — Route D Workflow Validation Report

**Task:** `OHB2-WP07-DEF011-F02-ROUTE-D-INDEPENDENT-REVIEW-WORKFLOW-PREPARATION`
**Date:** 2026-11-21
**Proposal:** new file `.github/workflows/f02-review.yml` (252 lines)
**Design document:** `docs/audits/OHB2-WP07-DEF011-F02-ROUTE-D-WORKFLOW-DESIGN.md`

---

## Verdict

# `ROUTE_D_REVIEWER_INDEPENDENCE_NOT_PROVEN`

| Question | Answer |
|---|---|
| Does it provide **genuine execution isolation**? | **Yes** — separate host, filesystem, session; pinned commit; read-only |
| Does it provide an **independently generated technical judgment**? | **No** — it supplies evidence, not judgment |
| Can the gap be closed without owner authorization? | **No** — every candidate reviewer service is retired, paid, broken, or needs a new secret |

**The workflow was never executed.** It exists only in a disposable clone. Nothing was applied,
committed, pushed, dispatched, or published.

---

## 1. Validation performed

| Check | Method | Result |
|---|---|---|
| YAML parses | `yaml.safe_load` (PyYAML, in container) | **PASS** — "YAML OK" |
| Actions syntax + expression/context usage | `actionlint 1.7.7` | **PASS** — exit 0, no output |
| Shell correctness of every `run:` block | `actionlint -shellcheck=` | **PASS** — exit 0 |
| Existing workflows still lint | `actionlint` on the whole tree | **PASS** — baseline was already clean |
| Scope guard against the real commit | executed the guard logic on `52e7789..6a1ca2e` | **PASS** — "SCOPE OK" |
| NEW-DEF-03 / NAV guard | executed on the real diff | **PASS** — "no markers" |
| Protected-surface guard | executed on the real diff | **PASS** — "none touched" |
| Merge-base resolution | `git merge-base origin/main pr8` | **PASS** — exactly `52e7789` |
| SHA validation guard | 6 adversarial inputs | **PASS** — see §2 |
| Negative control genuinely discriminates | real `pytest -k T8b` with/without fix | **PASS** — see §3 |
| Negative control restore is byte-exact | `sha256sum` before/after | **PASS** — `82d9c4b8…` both times |
| Heredoc instructions step executes | extracted and ran the `run:` block | **PASS** — both files created, `rc=0` |
| No PASS/expected-conclusion instruction | `grep -ic` on generated file | **PASS** — 0 matches |
| No secrets referenced | manual review of all 13 steps | **PASS** — none |
| No write permissions | `permissions:` block review | **PASS** — `contents: read` only |
| No source/test modification | file list of the proposal | **PASS** — one new workflow file |

Validation tooling: `actionlint` 1.7.7 fetched from its official release page into `/tmp` (not added to
the repository, not installed system-wide). PyYAML used inside the existing `nct` container.

---

## 2. SHA validation guard — adversarial test

Input is rejected unless it is exactly 40 lowercase hex characters.

| Input | Result | Exit |
|---|---|---|
| `6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18` | ACCEPT | 0 |
| `6A1CA2E` | REJECT (hex) | 1 |
| `abc` | REJECT (len=3) | 1 |
| `` (empty) | REJECT (hex) | 1 |
| `6a1ca2e; rm -rf /tmp/x` | REJECT (hex) | 1 |
| `6a1ca2e596a26d9ae747c27f4e4361c5a85b0b1` (39 chars) | REJECT (len=39) | 1 |

Command injection and truncated SHAs are both refused before the value reaches `git` or `checkout`.

---

## 3. Negative control — verified against real code

Run in a clean container (`python:3.11-slim`, `git` + `requirements-dev.txt` installed) at `6a1ca2e`.

**With the fix applied:**

```
tests/test_def011_fs_offload.py -k T8b
1 passed, 44 deselected in 0.38s
```

**With `bot/handlers.py` reverted to base `52e7789`:**

```
FAILED tests/test_def011_fs_offload.py::test_T8b_local_capped_read_runs_off_event_loop_thread
1 failed, 44 deselected in 0.29s
```

`T8b` genuinely discriminates the fix. It is not a vacuous test.

**File restored byte-exactly:** `sha256 82d9c4b8e0fa0e005f2a7c9494a57903a94e7f79eb45d08babe5ebd9dbd57525`,
identical to `git show 6a1ca2e:bot/handlers.py` and to the candidate manifest.

### 3.1 A real defect found and fixed during validation

The first draft reverted the file with a bare `git checkout`. In the container that command failed with
`fatal: detected dubious ownership in repository at '/work'`, the file was **not** reverted, and `T8b`
then **passed** — a false "the control works" signal. Under `set -euo pipefail` the bare form would
have aborted the step; but the deeper risk is any path where the revert silently no-ops.

The final version fails closed and asserts the outcome:

```bash
if ! git checkout "${BASE}" -- bot/handlers.py; then exit 1; fi
REVERTED_SHA="$(git hash-object bot/handlers.py)"
BASE_SHA="$(git rev-parse "${BASE}:bot/handlers.py")"
[ "${REVERTED_SHA}" = "${BASE_SHA}" ] || exit 1
… pytest … ; rc=$?
[ "${rc}" -ne 0 ] || { echo "::error::negative control passed"; exit 1; }
```

Without this validation run the workflow would have shipped with a negative control that could report
a false success.

---

## 4. Defects found and fixed during preparation

| # | Defect | Impact if shipped | Fix |
|---|---|---|---|
| 1 | Unchecked `git checkout` in the negative control | False "control works" result | Fail-closed + blob-hash equality + assert `rc != 0` |
| 2 | Evidence uploaded only on success | A failing test produced **no artifact** — the most important case lost | `continue-on-error` on test steps; `if: always()` on instructions + upload |
| 3 | `github.event.pull_request.base.sha` used as base | Diff silently changes when `main` advances | `git merge-base origin/main HEAD` + warning on drift |
| 4 | Dead `BASE_SHA` computed in the target step | Misleading, unused output | Removed; base resolved once in its own step |

All four were caught by executing the logic, not by reading it.

---

## 5. Reviewer independence — the decisive finding

### 5.1 Execution isolation: proven

| Property | Evidence |
|---|---|
| Separate host | GitHub-hosted runner. The real CI log for this repo shows `##[group]Runner Image Provisioner`, `Hosted Compute Agent`, `Image: ubuntu-26.04`, `Version: 20261116.202.1` — a provisioned VM, not this pod (`runtime-hjffxzvtsqfkfugy-566946795b-cjkbr`) |
| Separate filesystem | fresh checkout per job |
| Separate session | ephemeral runner process |
| Exact commit | full SHA + `git rev-parse HEAD` equality assertion |
| Read-only | `contents: read`, `persist-credentials: false`, no push/merge/deploy step |

### 5.2 Judgment independence: not established

The workflow produces evidence and an empty findings template. It contains no reviewing step and
asserts no verdict. Whether the resulting judgment is independent depends entirely on **who writes
it** — and that is unresolved.

### 5.3 Candidate reviewer services — each probed, none usable

| Candidate | Probe result | Usable? |
|---|---|---|
| **GitHub Models** (LLM in Actions on the built-in token) | **RETIRED 2026-07-30.** `docs.github.com/en/github-models`: "GitHub Models has been fully retired… the playground, model catalog, inference API, and bring your own key (BYOK) are no longer available to any customer" | **No — service gone** |
| **Copilot code review** | `GET /user/copilot` → **404**; account `plan=None`; reviewer request returns HTTP 200 but `requested_reviewers: []`; 0 reviews on PR #7/#8 | **No — needs a paid Copilot plan** |
| **NVIDIA inference API** | Endpoint is real: `GET /v1/models` → 200 with 33 models. But `POST /v1/chat/completions` → **404 "Not found for account"** for every model tried (`gemma-3-12b-it`, and `llama-3.1-8b-instruct` → 410 EOL). Also would need a new repo secret | **No — key cannot invoke; needs a secret** |
| **OpenHands Cloud LLM proxy** | `POST /chat/completions` → **401 Authentication Error** with both `OPENHANDS_API_KEY` and `PROXY_KEY` | **No — not usable as a repo secret** |
| **Human reviewer (owner)** | Zero cost, separate host. But: same principal that commissioned the work; AGENTS.md records an Android/Termux setup with no local Python/Node toolchain to re-run the suite | **Partly — no executed re-verification** |
| **Second human collaborator** | `GET /collaborators` returns exactly one: `TM-AEM` (admin) | **No — would be a permission change (forbidden)** |

No integration was invented. The task's instruction — "if the proposed workflow depends on an
unavailable reviewer service, do not invent an integration" — is honoured: the workflow depends on
**no** service.

### 5.4 Correction to the previous task's report

The previous report stated GitHub Models was a "verified zero-secret enabler" (HTTP 200). **That was a
false positive.** This sandbox stubs `models.github.ai`: it returns a 4-byte `OK` body for every path,
with or without authentication, while the real GitHub API returns JSON over the same connection. The
service is also retired.

Evidence:

```
GET  https://models.github.ai/                       -> 200 size=4  "OK"
GET  https://models.github.ai/catalog/models         -> 200 size=4  "OK"
GET  https://models.github.ai/nonexistent-path-xyz   -> 200 size=4  "OK"
POST https://models.github.ai/inference/chat/completions (no auth) -> 200 size=4 "OK"
GET  https://api.github.com/rate_limit (control)     -> 200 size=1917 valid JSON
```

The prior claim is retracted here. The previous report is left unedited; this section supersedes it.

---

## 6. What the workflow does and does not guarantee

**Guarantees:**

- the exact commit `6a1ca2e…` is what gets examined;
- the changed-file set is exactly the three expected paths;
- no NEW-DEF-03 / NAV-01..06 content is present;
- no schema, Mini App, dependency or API surface is touched;
- the regression suite and full suite are run and their output is captured;
- `T8b` genuinely fails without the fix;
- all of it lands in a 30-day read-only artifact;
- nothing in the repository is modified, published, merged or deployed.

**Does not guarantee:**

- that anyone forms an independent judgment;
- that the judgment is correct;
- that the tests are adequate — the reviewer must judge that;
- F-02 closure. **F-02 remains open.**

---

## 7. Remaining owner decisions

| # | Decision | Why it blocks |
|---|---|---|
| 1 | Authorize adding one workflow file + commit + push | This task forbids branch/commit/push |
| 2 | **Who supplies the technical judgment?** | No service exists that is free, working, and secret-free. Options: owner reviews the artifact; owner authorizes an LLM integration + secret; owner adds a second collaborator |
| 3 | Where findings land | Artifact only (current, read-only) vs PR comment (`pull-requests: write`) vs committed report (push) |
| 4 | Accept `workflow_dispatch` | `ci.yml` has none today; this adds a new trigger style to the repo |

Decision 2 is the real blocker. Decisions 1 and 3–4 are mechanical once 2 is settled.

---

## 8. Compliance

| Constraint | Status |
|---|---|
| Original `ci.yml` / any original-tree workflow modified | **No** |
| Branch or commit created | **No** |
| Staged or pushed | **No** |
| PR opened/closed/retargeted/merged | **No** |
| Repository settings or visibility changed | **No** |
| Secrets, tokens, paid integrations added | **No** |
| Credits purchased / paid trial started | **No** |
| Application source or tests modified | **No** |
| PR #7 or `main` changed | **No** — PR #7 still `31dec52…`, `main` still `52e7789` |
| `.agent/`, `.openhands/`, unrelated state preserved | **Yes** — memory notes appended only |
| Reset / clean / force / broad deletion | **No** |
| Claimed the workflow executed or a review occurred | **No** |

Workspace at completion: `HEAD 52e7789`, 8 pre-existing modifications preserved, 0 staged. Two new
documentation files added. The workflow proposal lives only in `/tmp/wfd` (disposable clone), which was
returned to a clean state apart from the new file.

---

## 9. Final report

### Can the proposed workflow provide both?

1. **Genuine execution isolation — YES.** Separate host, filesystem, and session; exact-commit pinning;
   read-only permissions; no publish path. This is verifiable from the runner image recorded in the
   repository's own CI logs.
2. **An independently generated technical judgment — NO.** The workflow deliberately supplies evidence
   only. No zero-cost, secret-free reviewer service is available: GitHub Models is retired, Copilot
   review needs a paid plan, the NVIDIA key cannot invoke models, and the OpenHands proxy rejects both
   available keys.

### Remaining owner decision

**One decision gates everything:** who supplies the technical judgment.

- If the owner reviews the artifact personally → F-02 can close, but the review is the owner's, and
  re-execution of the suite is limited by the tablet environment.
- If the owner authorizes an LLM integration plus a repository secret → a genuinely separate judgment
  becomes possible; this needs an explicit decision because it adds a secret and a paid/free-tier
  dependency.
- If the owner adds a second collaborator → the strongest option, but it is a permission change.

Alongside it: authorize the workflow file itself (branch + commit + push), and choose where findings go.

**F-02 remains open** until an actual independent review is performed and its findings are resolved.
