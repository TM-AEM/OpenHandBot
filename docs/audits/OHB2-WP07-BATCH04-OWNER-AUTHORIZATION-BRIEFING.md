# OHB2 — WP-07 / Batch 04 — Owner Authorization Briefing

**Task:** `OHB2-WP07-BATCH04-OWNER-AUTHORIZATION-READINESS`
**Date:** 2026-11-19
**Recorded by:** AI agent (OpenHands) on behalf of the repository owner
**Mode:** authorization-readiness only — **no publication, transfer, or execution was performed**

> ## ⚠️ NO AUTHORIZATION HAS BEEN GRANTED
> This document **asks** for a decision. Nothing here authorizes a push, a PR, a visibility
> change, a CI run, an artifact upload, or any external disclosure. Every action listed in §4
> remains **unauthorized** until the owner signs it explicitly and individually.
>
> **F-01 has NOT been independently reviewed, accepted, or closed.** It is implemented and
> locally verified only.

---

## 1. Verified current state (re-derived this task, not copied)

### 1.1 Repository and Git

| Field | Value |
|---|---|
| Repository root | `/workspace/project/OpenHandBot` |
| Remote | `https://github.com/TM-AEM/OpenHandBot.git` |
| Branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` |
| HEAD | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| `origin/main` | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` (identical, 0/0) |
| Staged | **0** |
| Modified (tracked) | **8** |
| Untracked | **40** |
| Ignored | **8** (`.openhands/`, `.venv/`, `__pycache__/`, `.pytest_cache/`) |
| Repository visibility | **PUBLIC** (`private: false`, verified read-only via API) |
| `pushed_at` | `2026-11-18T18:35:36Z` (unchanged since Batch 03) |
| Archived | no |

**No local changes appeared since the environment-discovery report** — it recorded
8 modified / 40 untracked, which is exactly the current state.

### 1.2 F-01 implementation files (exact, SHA-256)

| File | Git state | SHA-256 |
|---|---|---|
| `bot/attachments.py` | **modified** (tracked) | `d27fb79870d900f584aebfea861619f6e4000ba1b9cb026d359189ae1e914ed5` |
| `tests/test_f01_reaper_fs_offload.py` | **untracked** (new, 13 tests) | `0caa88c6e8c3cae176d90464d2f46e1495e6512fa282c33bdc795daf01fdae2e` |
| `tests/test_def011_fs_offload.py` | **untracked** (21 tests) | `db0f5b6177a7a51652a19be71c27dca56ce97182b1b09966f1dd2e97d3a7e99f` |

Call-site files touched by the F-01 path: `bot/app.py` (+1/−1: `reaper.sweep` →
`await reaper.sweep_async`), `bot/watcher.py` (+16/−4: `maybe_sweep` →
`await maybe_sweep_async`).

### 1.3 Batch 04 review package

| Field | Value |
|---|---|
| Archive | `/workspace/review-packages/OHB2-WP07-BATCH04-DEF011-F01-20261119.tar.gz` |
| Size | `107643` bytes |
| SHA-256 | `47b992300ec1bd5efec8c6c95afff4a63815a58ccd25f254975939f53f0bf71d` |
| Sidecar | `…tar.gz.sha256` — `sha256sum -c` → **OK** |
| Manifest | `MANIFEST.sha256` — **8/8 OK** from a fresh extraction |
| Changed since previous report? | **NO** — identical size, digest and mtime (`2026-11-19 16:06:26`) |

**Archive still corresponds to the current implementation — verified by hash comparison
(not by trusting the report):**

| File | Archive snapshot | Current worktree | Match |
|---|---|---|---|
| `bot/attachments.py` | `d27fb798…` | `d27fb798…` | ✅ |
| `tests/test_f01_reaper_fs_offload.py` | `0caa88c6…` | `0caa88c6…` | ✅ |
| `tests/test_def011_fs_offload.py` | `db0f5b61…` | `db0f5b61…` | ✅ |
| `docs/reviews/…F01-IMPLEMENTATION-REPORT.md` | identical | identical | ✅ |

### 1.4 Public repository and CI configuration — unchanged

- Visibility: **public** (unchanged).
- `.github/workflows/ci.yml`: identical to `origin/main` (`sha256 e2edadf0…`).
- Triggers: **`push: branches: [main]`** and **`pull_request: branches: [main]`** only.
  **There is no `workflow_dispatch`** ⇒ CI cannot be started manually.
- `permissions: contents: read`.

---

## 2. The exact disclosure risk (read this before choosing)

### 2.1 "Only the F-01 scope" is **not separable** — this is the central finding

The F-01 change **cannot** be published alone. Measured on this tree:

| Segment | Base | Target | Insertions / Deletions |
|---|---|---|---|
| **Batch-03 DEF-011 sub-defect B** | `origin/main` | Batch-03 snapshot | **+245 / −59** |
| **Batch-04 F-01** | Batch-03 snapshot | current worktree | **+162 / −65** |
| **Total** | `origin/main` | current worktree | **+386 / −103** (git `--shortstat`) |

(Sum: 245+162 = 407 insertions and 59+65 = 124 deletions of raw `diff` lines; git's
`--shortstat` reports 386/103 after hunk coalescing. Both views agree that the file carries
**two** unreviewed batches.)

Batch-03 DEF-011-B is itself **still independently unreviewed** (`store_async`,
`sweep_async`, `maybe_sweep_async`, `_accept_lock`, `_store_write` — **none of these exist on
`origin/main`**: verified, `grep -c` returns 0 for both `store_async` and `sweep_async`).

⇒ A review branch cut from `origin/main` and given the working-tree `bot/attachments.py`
publishes **both** the unreviewed Batch-03 DEF-011-B work **and** the unreviewed Batch-04
F-01 work. They share one file and one object; they cannot be split without a partial-file
commit, which would be a fabrication.

### 2.2 Full public exposure if Route A is chosen

Pushing a branch publishes, at minimum, these **unreviewed** changes:

| File | Change vs `origin/main` |
|---|---|
| `bot/attachments.py` | +386 / −103 (DEF-011 B **and** F-01) |
| `bot/db.py` | +269 / −66 (WP-07 atomicity work) |
| `bot/handlers.py` | +144 / −41 (incl. `_read_local_capped` offload) |
| `bot/watcher.py` | +16 / −4 |
| `bot/app.py` | +1 / −1 |
| `tests/test_handlers.py` | +2 / −2 |
| `tests/test_sw06_unwatch_db_failure_propagation.py` | +11 / −11 |
| `.agent/PROGRESS.md` | +236 |
| 32 further untracked docs/tests | (see §2.4) |

### 2.3 Secrets assessment (favourable)

- No `.env` file exists in the tree; only `.env.example` (already public).
- `.openhands/`, `.venv/`, `__pycache__/`, `.pytest_cache/` are **git-ignored** and would not
  be published.
- No credential value was printed or handled during this task.
- **Residual risk:** the 40 untracked files have not been individually secret-scanned. A
  pre-push scan is a **required** gate (§4, item 4).

### 2.4 Package completeness gap (newly discovered, affects reviewability)

The Batch-04 package **cannot reproduce a passing test run by itself**:

- It contains `snapshot/bot/attachments.py` and the two test files, but **not**
  `bot/handlers.py`, `bot/db.py`, `bot/watcher.py`, `bot/app.py`, `requirements*.txt`,
  `pytest.ini`, and **not** a `WORKTREE-VS-HEAD.diff` (Batch 03 had one).
- **Demonstrated:** building a tree from `origin/main` + the package snapshot and running
  the package's own tests gives **1 failed / 33 passed** —
  `test_T8b_local_capped_read_runs_off_event_loop_thread` fails because the
  `_read_local_capped` offload lives in `bot/handlers.py`, which the package omits.
- Running the same two files in the real working tree gives **34 passed**.
- The **F-01 file alone** passes from `origin/main` + snapshot: **13/13**.

⇒ The package is **sufficient for the F-01 reaper claim** but **insufficient for the full
DEF-011 B claim**. A reviewer would report a false failure unless given the diff or the
extra files. This must be fixed **before** handoff (a packaging change, not an
implementation change).

---

## 3. Route A vs Route B

### Route A — Public PR

| Step | Detail |
|---|---|
| 1 | Create a dedicated branch from `origin/main` |
| 2 | Apply the F-01 (and, unavoidably, DEF-011 B) working-tree changes |
| 3 | Push the branch — **the diff becomes world-readable immediately** |
| 4 | Open a PR against `main` |
| 5 | CI runs automatically on `pull_request` (no `workflow_dispatch` needed) |
| 6 | CI produces the test/lint evidence on a **genuinely separate** GitHub-hosted runner |
| 7 | Retrieve the run's evidence/artifact and the sidecar |
| 8 | Perform the independent review on that separate runner's evidence |

**Pros:** simplest; no visibility change; CI triggers natively; runner separation is real and
already evidenced (`GitHub Actions 1000000325/26/27`).
**Cons:** **permanent public disclosure of unreviewed code**; public git history is effectively
irreversible (mirrors, forks, caches); discloses more than F-01 (§2.1).

### Route B — Private repository first

| Step | Detail |
|---|---|
| 1 | Convert `TM-AEM/OpenHandBot` to **private**, or use an owner-approved private mirror |
| 2 | **Verify** the target repo is actually private **before** any push |
| 3 | Create the review branch and push |
| 4 | Open the PR and trigger CI |
| 5 | Retrieve evidence/artifact and sidecar |
| 6 | Review on the separate runner |

**Pros:** no public disclosure; full diff and full tree can be handed over, fixing §2.4;
reviewer can be given a complete, runnable environment.
**Cons / risks:**

| Risk | Impact |
|---|---|
| GitHub Actions minutes on private repos | **Paid/quota** — this is a cost the owner must accept. Public-repo Actions are free; private-repo Actions are metered. |
| Existing forks/mirrors | A private repo does **not** retract content already public; forks stay public |
| Collaborators | All current collaborators must be re-checked; access is revoked by the visibility change |
| Tokens / integrations | Personal access tokens, deploy keys, and any OAuth app scoped to the repo may behave differently; the current token's self-hosted-runner listing already returns 403 |
| Webhooks / external CI | Any integration pointing at the repo keeps working but is now scoped to a private repo |
| GitHub Pages / public links | Any public URL (badges, Pages) would break |
| Irreversibility | Converting back to public re-publishes history |

---

## 4. Exact permission manifest (each item is separate; nothing is bundled)

### Required for **Route A**

| # | Action | Necessity | Notes |
|---|---|---|---|
| A1 | **Public disclosure** of the unreviewed diff (DEF-011 B **and** F-01) | **REQUIRED** | Irreversible in practice |
| A2 | Use the existing `GITHUB_TOKEN` for push | **REQUIRED** | Already present in the environment |
| A3 | Create and push a dedicated review branch | **REQUIRED** | |
| A4 | Pre-push secret scan of the 40 untracked files | **REQUIRED** (safety gate) | Not yet done |
| A5 | Open a PR against `main` | **REQUIRED** | |
| A6 | Let GitHub Actions run (no `workflow_dispatch` exists) | **REQUIRED** | Triggered by the PR |
| A7 | Retrieve the CI artifact / logs and the sidecar | **REQUIRED** | |
| A8 | Perform the independent technical review | **REQUIRED** | |
| A9 | Later commits / merge / deploy | **OPTIONAL** — and **NOT** requested here | Separate decision after review |

### Required for **Route B**

| # | Action | Necessity | Notes |
|---|---|---|---|
| B1 | Change repo visibility to **private** (or create a private mirror) | **REQUIRED** | Affects all collaborators |
| B2 | Verify private status **before** push | **REQUIRED** (safety gate) | |
| B3 | Accept **Actions minutes cost/quota** on private repos | **REQUIRED** | Money/quota — owner only |
| B4 | Re-verify collaborator access, tokens, webhooks, integrations | **REQUIRED** | |
| B5 | Use `GITHUB_TOKEN` for push | **REQUIRED** | |
| B6 | Create/push review branch; open PR | **REQUIRED** | |
| B7 | Trigger CI; retrieve artifact + sidecar | **REQUIRED** | |
| B8 | Perform the independent review | **REQUIRED** | |
| B9 | Restore visibility to public afterwards | **OPTIONAL** — **NOT** requested | |
| B10 | Later commits / merge / deploy | **OPTIONAL** — **NOT** requested | |

### Required for **either** route (packaging fix)

| # | Action | Necessity |
|---|---|---|
| C1 | Add `WORKTREE-VS-HEAD.diff` (and/or the missing `handlers.py`, `db.py`, `watcher.py`, `app.py`, `requirements*.txt`, `pytest.ini`) to the review package | **REQUIRED** for a valid review (§2.4) |
| C2 | Recompute and re-publish the archive SHA-256 after C1 | **REQUIRED** |

**Not requested under any route:** deploying, releasing, merging to `main`, enabling Autopush,
touching the Mini App, schema changes, or altering architectural decisions.

---

## 5. Review integrity requirements (must hold for the future review to count)

The reviewer must prove **all** of the following, with command output:

1. **Different machine identity** — `hostname`, `/etc/machine-id`, `uname -a` differ from the
   implementation host (`runtime-hjffxzvtsqfkfugy-…`, machine-id `17d2e919…`).
2. **Different execution environment and filesystem** — not the `/workspace` volume
   (device `66309`); implementation worktree not mounted.
3. **No writable access to the implementation worktree** — a `touch` probe must fail.
4. **Exact archive and sidecar transferred** — both, with documented provenance.
5. **SHA-256 verified before extraction** — `sha256sum -c` on the received bytes.
6. **Manifest verified after extraction** — `sha256sum -c MANIFEST.sha256` → 8/8 OK.
7. **No unmanifested files** — extracted set equals the manifest set exactly.
8. **Independent source inspection and test execution** — reviewer re-derives counts.
9. **Explicit F-01 regression verification** — with instrumentation proving
   `_remove_file` (`os.lstat` at `bot/attachments.py:1643,1657`; `os.unlink` at `:1667`)
   executes **outside the event-loop thread** during `sweep_async`, and that reverting to the
   pre-fix file (`e72745eb9d628c20…`) makes the assertion **fail**.
10. **Separate verdicts** — one for technical correctness, one for independence. A single
    "PASS" is not acceptable.

The reviewer must **not** modify the implementation.

---

## 6. Recommendation

**Recommended: Route B (private first), conditional on the packaging fix C1/C2.**

Reasons:

1. **§2.1 is decisive for Route A.** "Publish only the approved F-01 scope" is **not
   achievable** — the file carries unreviewed Batch-03 work. Route A would therefore disclose
   more than the owner is being asked to approve.
2. **Route A is effectively irreversible.** Public git history is mirrored and cached; a later
   visibility change does not retract it.
3. **Route B also fixes §2.4.** A private handoff can include the full diff and the missing
   files, so the reviewer can actually reproduce a green suite instead of hitting a false
   failure caused by the package, not the code.

**Limitations of the recommendation:**

- Route B **costs Actions minutes** (owner must accept).
- Route B **disrupts collaborators, tokens and integrations**; each needs re-verification.
- Route B does **not** by itself make the review valid — §5 must still hold.
- If the owner prefers **no visibility change**, the only alternative is Route A **plus**
  explicit acceptance that unreviewed DEF-011-B code becomes public.
- **Neither route** closes DEF-011: sub-defects **A** (ledger, blocked on D-12/OD-04) and
  **C** (UX copy, WP-01) remain open; **F-02** and **F-03** remain open; **WP-09** is
  unverified.

---

## 7. Owner decision fields

> Tick **one**. Leaving all blank means **no authorization** (the current state).

### Option 1 — Route A (public PR)

- [ ] I authorize **A1** public disclosure of the unreviewed DEF-011-B **and** F-01 diff,
      understanding it is effectively irreversible.
- [ ] I authorize **A2** use of the existing `GITHUB_TOKEN`.
- [ ] I authorize **A3** creating and pushing a dedicated review branch.
- [ ] I authorize **A4** running a pre-push secret scan.
- [ ] I authorize **A5** opening a PR against `main`.
- [ ] I authorize **A6** GitHub Actions running on that PR.
- [ ] I authorize **A7** retrieving the CI artifact and sidecar.
- [ ] I authorize **A8** performing the independent technical review.

**Owner signature / date:** ______________________________

### Option 2 — Route B (private repository first)

- [ ] I authorize **B1** converting `TM-AEM/OpenHandBot` to **private**
      (or: use private mirror — name: ____________________).
- [ ] I authorize **B2** verifying private status before any push.
- [ ] I accept **B3** the GitHub Actions **minutes cost/quota** for private-repo CI.
- [ ] I authorize **B4** re-verifying collaborators, tokens, webhooks and integrations.
- [ ] I authorize **B5–B7** token use, branch push, PR, CI run, artifact retrieval.
- [ ] I authorize **B8** performing the independent technical review.
- [ ] **B9** (optional) restore visibility to public afterwards — **yes / no**

**Owner signature / date:** ______________________________

### Option 3 — Neither (hold)

- [ ] I authorize **neither** route at this time. F-01 remains implemented, locally verified,
      and **not independently reviewed**.

**Owner signature / date:** ______________________________

### Mandatory for any chosen route

- [ ] I authorize **C1** adding the missing diff/files to the review package.
- [ ] I authorize **C2** recomputing and re-publishing the archive SHA-256.

---

## 8. Statement of current authorization status

**No authorization has been granted.** As of this document:

- The repository is still **public** and **unmodified** (`HEAD 52e7789`, 0 staged,
  8 modified, 40 untracked).
- Nothing was pushed, committed, staged, branched, PR'd, or had its visibility changed.
- No CI run was triggered. No artifact was uploaded. No token was used or exposed.
- No source code or package left this environment.
- **F-01 is not independently reviewed, not accepted, and not closed.**
- **DEF-011 is not closed** (A and C open). **F-02, F-03 open. WP-09 unverified.**
