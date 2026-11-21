# OHB2 — WP-07 / DEF-011 / F-02 — Final CI, Independent Review and Closure Report

**Task:** `OHB2-WP07-DEF011-F02-FINAL-CI-INDEPENDENT-REVIEW-AND-CLOSURE`
**Date:** 2026-11-18
**Predecessors:** F-02 implementation · `F02_REV01_FIXED_AND_VERIFIED`

---

## FINAL VERDICT

```
F02_BLOCKED_CI
```

Two mandatory closure conditions are **not** satisfied. CI is recorded as the primary blocker
because it is a hard structural gate with a concrete resolution path that requires owner
authorization; independent review is recorded as an additional, co-equal blocker.

1. **CI did not test this candidate.** GitHub Actions checks out *commits*; the F-02 candidate is
   entirely **uncommitted**. The green CI run on `52e7789` never contained `store_async` at all.
2. **No genuinely independent review environment exists** in this runtime
   (`INDEPENDENCE_NOT_ESTABLISHED`).

Both Python 3.11 and 3.13 were nevertheless executed **locally** against the exact frozen candidate,
with identical results (3443 passed, exit 0 each). That is strong evidence but it is **not** CI
evidence and **not** independent review, and it is not labelled as either.

---

## 1. Final snapshot identity

| Property | Value |
|---|---|
| Repository root | `/workspace/project/OpenHandBot` |
| Branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` |
| HEAD | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| `origin/main` | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| Divergence | `0 0` |

| File | SHA-256 (recomputed) | Matches verified snapshot |
|---|---|---|
| `bot/attachments.py` | `b98d561f0ba0ab27dea4e6bedee7955f68f1f6fa85a39fa81afe8aeb4d818356` | **yes** |
| `tests/test_def011_fs_offload.py` | `3d3b3a2ac399fec0420e2d769f98c7c2841c69c05f341734aecef68df4f503ea` | **yes** |

Both hashes were recomputed at the start and again at the end of this task; unchanged. The candidate
therefore **is** the verified snapshot — no drift, so the earlier test results remain valid evidence
for it.

### 1.1 The candidate is entirely uncommitted — decisive fact

| Evidence | Value |
|---|---|
| `git show HEAD:bot/attachments.py` occurrences of `store_async` | **0** |
| HEAD blob SHA-256 of `bot/attachments.py` | `7e448b52ac3b5f470cb23e5de073161539e61b47a7c89c8fe5c4e65ec0c2276c` |
| Working-tree SHA-256 | `b98d561f0ba0ab27dea4e6bedee7955f68f1f6fa85a39fa81afe8aeb4d818356` |
| `tests/test_def011_fs_offload.py` at HEAD | **UNTRACKED** (does not exist in any commit) |

The entire F-02 implementation and the REV-01 regression test exist **only in the working tree**.

### 1.2 Git preservation evidence

| Property | Phase 1 | End of task |
|---|---|---|
| Staged | 0 | 0 |
| Modified | 8 | 8 |
| Untracked | 67 | 67 |
| Ignored | 8 | 8 |
| HEAD | `52e7789` | `52e7789` |

All pre-existing modified, untracked and ignored files preserved. `.openhands/` (including
`MEMORY.md`, `2026-11-18.md`) and `.agent/` (`PROGRESS.md`) intact. No reset, clean, stash, checkout
or deletion was performed. All verification ran on copies under `/tmp/f02final/`.

---

## 2. Python 3.11 verification — LOCAL, not CI

### 2.1 How 3.11 was obtained

No Python 3.11 existed on this host (`python3.10`/`3.11`/`3.12` all absent; only 3.13.15). The
pre-installed `uv` was used to install a real interpreter:

```
uv python install 3.11   ->  Installed Python 3.11.18 (cpython-3.11.18-linux-x86_64-gnu)
```

Dependencies were installed from the repository's own pinned `requirements-dev.txt` (no new
dependency added to the project):

```
uv venv --python 3.11 .venv311
uv pip install -r requirements-dev.txt
```

Interpreter: **Python 3.11.18** · pytest **9.0.3**.

### 2.2 Candidate identity inside the 3.11 tree

The frozen tarball was extracted to an isolated directory and re-hashed **before** running:

```
b98d561f0ba0ab27dea4e6bedee7955f68f1f6fa85a39fa81afe8aeb4d818356  bot/attachments.py
3d3b3a2ac399fec0420e2d769f98c7c2841c69c05f341734aecef68df4f503ea  tests/test_def011_fs_offload.py
```

Identical to §1. So the 3.11 run used the **exact frozen candidate**.

### 2.3 Exact CI commands, run verbatim on 3.11

| CI step | Command | Result | Exit |
|---|---|---|---|
| Static check | `python -m pyflakes bot/ automation/ tools/ main.py tests/` | clean | **0** |
| Tests | `python -m pytest -q` | **3443 passed**, 74 warnings (191.21 s) | **0** |
| SAST | `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | Severity High **0** | **0** |
| SCA | `python -m pip_audit -r requirements-dev.txt` | No known vulnerabilities | **0** |

### 2.4 M4′ discrimination on 3.11

The regression test was validated on 3.11 against both the correct and the mutated implementation
(mutation applied to a copy, outside the repository):

| Target | Result |
|---|---|
| Correct candidate (`b98d561f…`) | **1 passed** |
| M4′ mutant (abandoned check removed, gate intact) | **1 failed** — `assert 1 == 0` (forbidden write) |

So REV-01's behavioural discrimination holds on 3.11 as well as 3.13.

### 2.5 Status

**Python 3.11: VERIFIED LOCALLY.** It is **not** CI-verified. The distinction is preserved
deliberately and is not merged into a single PASS.

---

## 3. Python 3.13 verification — LOCAL and (separately) CI-historical

### 3.1 Local, isolated tree

Same frozen tarball, separate directory and venv: **Python 3.13.15**, pytest **9.0.3**.

| CI step | Result | Exit |
|---|---|---|
| pyflakes | clean | **0** |
| `pytest -q` | **3443 passed**, 74 warnings (180.85 s) | **0** |
| bandit | Severity High **0** | **0** |
| pip-audit | No known vulnerabilities | **0** |
| `node --test tests/frontend/*.test.js` | **280 pass, 0 fail** | **0** |

### 3.2 Historical CI run — does NOT cover this candidate

| Field | Value |
|---|---|
| Run ID | `44371404130` |
| Workflow | `CI` |
| Event | `push` |
| Head SHA | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` (== local HEAD) |
| Jobs | `Tests & lint (3.11)` ✅ · `Tests & lint (3.13)` ✅ · `Frontend tests (Node)` ✅ |
| Started | 2026-11-18T18:35:38Z |

This run is **green**, but its `headSha` is `52e7789`, and §1.1 proves that commit contains **zero
occurrences of `store_async`** and does not contain the test file at all. The F-02 work was never
committed, so **CI has never executed F-02**. Citing this run as F-02 CI evidence would be false.

---

## 4. CI blocker — `CI_BLOCKED_AUTHORIZED_ROUTE_UNAVAILABLE`

### 4.1 Workflow triggers

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
```

| Route | Available? | Blocked by |
|---|---|---|
| `workflow_dispatch` | **No** — `grep -c workflow_dispatch ci.yml` → 0 | Workflow has no manual trigger; adding one = modifying workflows (forbidden) |
| `push` to `main` | **No** | Requires a commit + push to `main` (forbidden) |
| `pull_request` | **No** | Requires a branch, commit and PR (forbidden) |
| `act` (local runner) | **No** | `act` absent; also needs Docker |
| Docker-based runner | **No** | `/var/run/docker.sock` absent; podman absent |
| Pre-approved external runner | **No** | None provisioned in this environment |
| `gh` API dispatch | **No** | `gh` present but unauthenticated; and dispatch still requires a dispatchable workflow |

### 4.2 Root blocker — a structural one, not a permission one

Even if authentication and a dispatch trigger existed, CI **cannot** test this candidate, because
**GitHub Actions checks out a commit ref**. The candidate exists only as uncommitted working-tree
state (§1.1). Supplying it to CI requires exactly the actions this task forbids: commit → branch →
push/PR.

### 4.3 Recorded status

```
CI_BLOCKED_AUTHORIZED_ROUTE_UNAVAILABLE
```

No push, branch, commit, PR, workflow edit, visibility change or settings change was performed. No
CI run was triggered through any unauthorized route. No claim of CI success is made.

---

## 5. Independent review — `INDEPENDENCE_NOT_ESTABLISHED`

### 5.1 Environment identity (measured)

| Property | Value |
|---|---|
| Hostname | `runtime-hjffxzvtsqfkfugy-fdb7c5747-mrgdg` |
| uid / user | `10001` / `openhands` (single identity) |
| Docker socket | **ABSENT** |
| podman / bwrap / firejail / lxc-start / systemd-nspawn | **all ABSENT** |
| `unshare --mount --pid --user` | **`Operation not permitted`** (cannot change root fs propagation) |
| `chroot` | present, but requires root and shares the same kernel and host |
| Agent servers | only `:60000`, which hosts **this** session |
| Device of repo vs `/tmp/f02final` | `66309` vs `237` |

A different device number for `/tmp` does **not** confer isolation: same kernel, same host, same uid,
same process namespace, and no mechanism to create a genuinely separate one. Copies under
`/tmp/f02final/` and the different Python interpreters are **same-host** artifacts.

### 5.2 Verdict

```
INDEPENDENCE_NOT_ESTABLISHED
```

No independent review was performed, and none is claimed. A second directory, worktree, named
"review" folder, or second agent on this host is explicitly **not** independent and is not offered
as a substitute. Publishing code or altering repository settings to obtain a reviewer is forbidden
by the task and was not done.

### 5.3 Consequence for the reviewer checklist

The 10 required reviewer checks (§Phase 3 of the task) were **not** performed by an independent
party. They were performed by this agent in the previous two tasks and re-validated here. This
report therefore records the local findings for reference but **does not** represent them as
satisfying the independent-review requirement:

| # | Reviewer check | Local status | Independently reviewed |
|---|---|---|---|
| 1 | Atomic gate / `started`-`abandoned` transitions | verified (§6.1) | **no** |
| 2 | Worker lifecycle, unconditional completion, fail-closed | verified (§6.1) | **no** |
| 3 | AnyIO cancellation / shielding limits | verified vs installed source | **no** |
| 4 | REV-01 behavioural regression test | verified (§6.2) | **no** |
| 5 | Detects M4′ behaviourally, not by formatting | verified (§6.2) | **no** |
| 6 | Mutation removes only the abandoned guard | verified (gate blocks = 2) | **no** |
| 7 | Correct impl prevents write, `max_concurrent_writers == 1` | verified (§6.2) | **no** |
| 8 | Architectural guards / SQLite ownership | verified (§6.3) | **no** |
| 9 | D6 deferred, not described as safe | verified (§8) | **no** |
| 10 | No unrelated changes or regressions | verified (§7) | **no** |

---

## 6. F-02 and REV-01 evidence (re-validated on the frozen candidate)

### 6.1 F-02 implementation — unchanged and intact

| Check | Result |
|---|---|
| `bot/attachments.py` SHA-256 | `b98d561f…` (byte-identical to reviewed) |
| F-02 region markers (`with _gate:`, `_needs_drain`, `CancelScope(shield=True)`, `_done.set()`) | 7 matches present |
| Architecture tokens: `asyncio` / `create_task` / `create_task_group` / `TaskGroup` / `Thread(` / `opportunistic_cleanup` | **0 / 0 / 0 / 0 / 0 / 0** |
| `StagingStore.start` / `.stop` | **absent** (no new worker lifecycle) |

### 6.2 REV-01 regression test

| Check | Result |
|---|---|
| Test present (`test_f02_REV01_abandoned_worker_must_not_write_and_must_not_overlap`) | **yes** |
| Behavioural assertions present (`writes_i1 == 0`, `max_conc == 1`) | **yes** |
| Test file change | **append-only** (+149 lines, 0 removed — proven byte-prefix in the REV-01 report) |
| Correct candidate, 3.13 | **pass** (`max_concurrent_writers=1`, `writes_i1=0`) |
| M4′ mutant, 3.13 | **fail** — `assert 1 == 0` (`writes_i1=1`, `max_concurrent_writers=2`) |
| Correct candidate, 3.11 | **pass** |
| M4′ mutant, 3.11 | **fail** — `assert 1 == 0` |
| Mutation scope | only the abandoned early-return removed; `with _gate:` blocks still **2** |

### 6.3 SQLite ownership and architecture

Filesystem work stays in the existing worker-thread path; SQLite preparation/finalisation stays on
the event-loop owner path. The worker receives only `path`, `chunks`, `cap`, `item_id`, `token` — no
database handle. No schema, Mini App, API, queue, worker, background service, process, or dependency
was added.

---

## 7. Verification matrix — dimensions kept separate

| Dimension | Required status | Actual status | Evidence |
|---|---|---|---|
| F-02 implementation | Previously verified; revalidate snapshot | **REVALIDATED, unchanged** | `b98d561f…` recomputed twice |
| F-02-REV-01 | Fixed and behaviourally verified | **FIXED AND VERIFIED** | passes correct, fails M4′ on 3.11 **and** 3.13 |
| Python 3.13 | Local and CI evidence identified separately | **LOCAL: PASS** (3443) · **CI: does not cover candidate** | §3.1, §3.2 |
| Python 3.11 | Verified only with actual successful execution | **LOCAL: PASS** (3443, 3.11.18) · **CI: none** | §2.3 |
| CI | Actual run evidence or explicit blocker | **BLOCKED** | `CI_BLOCKED_AUTHORIZED_ROUTE_UNAVAILABLE` §4 |
| Independent review | Established or not established | **NOT ESTABLISHED** | §5 |
| D6 | Deferred and open | **DEFERRED AND OPEN** | §8 |
| Owner acceptance | Tracked separately | **NOT GRANTED** | — |
| F-02 closure | Only if all mandatory conditions satisfied | **NOT CLOSED** | §9 |

These dimensions are deliberately **not** collapsed into one PASS label.

---

## 8. D6 — deferred and open

**D6 remains DEFERRED and OPEN.** Repeated raw `Task.cancel()` during the drain is **not safe**:
a second raw cancel interrupts the drain, `_accept_lock` is released under an active writer, and
`max_concurrent_writers` reaches 2. `anyio.CancelScope(shield=True)` does not prevent this and the
implementation does not claim it does. D6 was out of scope for this task; no code, test, or
mitigation was added, and nothing here describes repeated raw cancellation as safe.

---

## 9. Closure recommendation

### 9.1 Not closed

**F-02 must not be closed on this evidence.** The two mandatory closure conditions are unmet:

| Condition for `F02_CLOSED_VERIFIED` | Status |
|---|---|
| Exact candidate passes required CI matrix on 3.11 **and** 3.13 | **NOT MET** — no CI run exists for this candidate (§4) |
| Genuinely independent review passes | **NOT MET** — no isolated environment (§5) |
| F-02-REV-01 remains behaviourally verified | **MET** (§6.2) |
| No unresolved Critical/High finding within F-02 | **MET** — none found |
| D6 documented as deferred | **MET** (§8) |
| Evidence recorded in final report | **MET** (this report) |

### 9.2 What is genuinely established

- The frozen candidate is **identical** to the verified snapshot; no drift.
- **Both** Python 3.11.18 and 3.13.15 execute the full CI command set against the exact candidate
  with **identical** results: 3443 passed / 0 failed, pyflakes 0, bandit severity High 0,
  pip-audit clean, frontend 280/280.
- REV-01's M4′ discrimination is reproduced on **both** interpreters.
- The production implementation is byte-identical; architecture and SQLite ownership preserved; no
  unrelated change.
- Python 3.11 is no longer an untested gap in substance — though still not CI-verified.

### 9.3 Conditions to close F-02

1. Commit the candidate to a branch and let the existing `CI` workflow run it on 3.11 and 3.13
   (owner-authorised commit/push — outside this task's authority).
2. Obtain a genuinely independent review in an environment with real isolation.
3. Track owner acceptance separately.

---

## 10. Remaining limitations

1. **CI not executed for this candidate** — structural: the candidate is uncommitted and Actions
   checks out commits; the only routes require forbidden commit/push/PR or workflow edits.
2. **Independent review not established** — no isolation primitive exists in this runtime.
3. **Python 3.11 verified locally only** — not via CI, not on a GitHub runner.
4. **D6 open** — repeated raw cancellation unsafe; deferred by owner decision.
5. **Owner acceptance** not granted and not implied.
6. The local 3.11 result is a faithful execution of the CI command set on a real CPython 3.11.18 with
   the repository's pinned dependencies, but a local environment is not a GitHub runner; OS-level and
   runner-level differences are not excluded.

---

## 11. Report metadata

| Item | Value |
|---|---|
| Verdict | `F02_BLOCKED_CI` |
| CI status | `CI_BLOCKED_AUTHORIZED_ROUTE_UNAVAILABLE` |
| Independence status | `INDEPENDENCE_NOT_ESTABLISHED` |
| Files modified by this task | **none** (this report only) |
| Candidate after task | `b98d561f…` / `3d3b3a2a…` — unchanged |
| Git after task | `HEAD 52e7789`, staged 0, modified 8, untracked 67, ignored 8 |
| Verification artifacts | `/tmp/f02final/` (outside the repository) |
| Commits / pushes / PRs / CI triggers / deploys | **none** |

**This report does not claim that F-02 is closed, that CI passed, that an independent review
occurred, or that WP-07 / DEF-011 is complete.**
