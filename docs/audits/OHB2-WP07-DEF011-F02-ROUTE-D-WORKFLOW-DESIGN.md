# OHB2 — WP-07 — DEF-011 / F-02 — Route D Workflow Design

**Task:** `OHB2-WP07-DEF011-F02-ROUTE-D-INDEPENDENT-REVIEW-WORKFLOW-PREPARATION`
**Date:** 2026-11-21
**Target:** PR #8 head `6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18`
**Status:** design prepared and validated in a disposable copy. **Not applied, not committed, not pushed, not executed.**

---

## 1. Target verification (Phase 1)

All SHAs resolved in full — no abbreviated values relied on.

| Item | Value | How verified |
|---|---|---|
| PR #8 head | `6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18` | `refs/pull/8/head` **and** GitHub API agree |
| Is `6a1ca2e` the head or an ancestor? | **It IS the head** | `git rev-parse pr8` == full SHA |
| Parent of head | `f37a3f524ec745f1b5d606161c6ad8b074613a2c` | `git rev-parse pr8^` |
| Base / merge-base | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` (= `origin/main`) | `git merge-base origin/main pr8` |
| Ancestry | `main` is an ancestor of the head → fast-forwardable | `git merge-base --is-ancestor` |
| CI on head | run `44877192697`, `pull_request`, **success** | `gh run list --commit …` |
| PR #7 head | `31dec52289142d0d0dc2bd16604d88644ba3baba`, OPEN, untouched | API |
| `main` | `52e7789…`, unchanged | `git ls-remote` |
| Workflows present at head | `ci.yml`, `enzonic-sftp-readonly-check.yml` | `git ls-tree` |

**The review target remains `6a1ca2e`.**

Existing CI convention (`ci.yml`): `permissions: contents: read`, triggers `push:[main]` +
`pull_request:[main]`, no `workflow_dispatch`. The proposal follows the same permission posture.

---

## 2. What the workflow is, and what it is not

**It is** an *evidence collector*. It runs on a GitHub-hosted runner, pins the exact commit, enforces
the scope guards, runs the existing test and static-analysis commands, runs a negative control, and
uploads a read-only artifact.

**It is not** a reviewer. It contains **no** step that forms a technical judgment, and it emits **no**
PASS/FAIL verdict about the change. Every step is deterministic tooling.

This split is deliberate: it is the only way to keep the *execution* isolated while leaving the
*judgment* genuinely independent.

---

## 3. Proposed workflow

File: `.github/workflows/f02-review.yml` (new file, 252 lines).

### 3.1 Triggers

```yaml
on:
  pull_request:
    branches: [main]
    paths:
      - "bot/attachments.py"
      - "bot/handlers.py"
      - "tests/test_def011_fs_offload.py"
      - ".github/workflows/f02-review.yml"
  workflow_dispatch:
    inputs:
      head_sha:
        required: true
        default: "6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18"
```

- `pull_request` keeps the existing repository convention and adds `paths` so the job runs only when
  the F-02 surface changes.
- `workflow_dispatch` allows an on-demand run pinned to an exact SHA — this is the primary route,
  because it does not require a new push.
- `pull_request` (not `pull_request_target`) is essential: `pull_request_target` runs in the base
  context with elevated trust, which is exactly the wrong posture for reviewing untrusted code.

### 3.2 Permissions

```yaml
permissions:
  contents: read
```

Job-level permissions are not widened. There is **no** `contents: write`, no `pull-requests: write`,
no `id-token`, no `actions: write`. The job cannot push, comment, label, merge, or alter settings.
`persist-credentials: false` on checkout removes the token from `.git/config` so no later step could
push even by accident.

### 3.3 Scope guard (branch restriction)

```yaml
if: >-
  github.event_name == 'workflow_dispatch' ||
  github.head_ref == 'review/ohb2-wp07-def011-f02-isolated'
```

The `pull_request` path only fires for the isolated F-02 branch. Any other PR touching those paths is
skipped — so this workflow cannot become a general-purpose reviewer.

### 3.4 Exact commit selection

1. **Resolve** — `head_sha` comes from `github.event.pull_request.head.sha` or the dispatch input.
2. **Validate** — the value must be 40 lowercase hex characters:
   ```bash
   case "${HEAD_SHA}" in (*[!0-9a-f]*|"") exit 1 ;; esac
   if [ "${#HEAD_SHA}" -ne 40 ]; then exit 1; fi
   ```
   This rejects uppercase, short SHAs, empty input, and injection payloads.
3. **Checkout** — `actions/checkout@v4` with `ref: <sha>`, `fetch-depth: 0`, `persist-credentials: false`.
4. **Prove it** — `git rev-parse HEAD` must equal the requested SHA, or the job fails.

Step 4 matters: `checkout` with a branch name would silently follow the branch if it moved. Pinning to
a full SHA plus re-verifying `HEAD` makes a moving branch impossible to slip through.

### 3.5 Stable base resolution

```bash
BASE="$(git merge-base origin/main HEAD)"
```

`github.event.pull_request.base.sha` is the **current** `main` tip, so it changes whenever `main`
advances, which would silently alter the diff under review. `merge-base` is stable. The step warns if
the computed base differs from the recorded `52e7789`.

### 3.6 Scope verification

Three independent guards, each failing the job on violation:

| Guard | Check |
|---|---|
| Exact file set | sorted `git diff --name-only` must equal exactly `bot/attachments.py`, `bot/handlers.py`, `tests/test_def011_fs_offload.py` |
| No out-of-scope behaviour | no added line matching `NEW-DEF-03` or `NAV-0[1-6]` |
| Protected surfaces untouched | no path matching `bot/db.py`, `*schema*`, `migrations/`, `bot/web/`, `requirements*`, `pyproject.toml` |

### 3.7 Evidence produced

| File | Content |
|---|---|
| `full.diff` | complete diff base→head |
| `code-only.diff` | `bot/` only |
| `diff-sha256.txt`, `code-only-sha256.txt`, `file-sha256.txt` | integrity hashes |
| `changed-files.txt`, `diff-stat.txt`, `scope.txt` | scope proof |
| `pytest-f02.txt`, `pytest-full.txt` | test output |
| `negative-control.txt`, `negative-control-result.txt` | discrimination proof |
| `REVIEWER-INSTRUCTIONS.md` | the reviewer's mandate |
| `FINDINGS-TEMPLATE.md` | blank findings table |
| `manifest.txt` | artifact inventory + timestamp |

Uploaded as `f02-review-evidence-<sha>` with `retention-days: 30`.

### 3.8 Failure behaviour

- Test steps use `continue-on-error: true` **so the evidence still uploads when tests fail**. A failing
  test must produce a reviewable artifact, not a missing one.
- The instructions step and the upload step both use `if: always()`.
- The scope guards and the negative control do **not** use `continue-on-error` — a broken guard must
  fail the job loudly.

### 3.9 Negative control — hardened after a real defect was found

An earlier draft ran `git checkout <base> -- bot/handlers.py` unguarded. Testing revealed that when
that command fails (e.g. git's `dubious ownership` error), the file is **not** reverted and `T8b`
passes spuriously — a false "control works" signal. The final version fails closed:

```bash
if ! git checkout "${BASE}" -- bot/handlers.py; then exit 1; fi
REVERTED_SHA="$(git hash-object bot/handlers.py)"
BASE_SHA="$(git rev-parse "${BASE}:bot/handlers.py")"
if [ "${REVERTED_SHA}" != "${BASE_SHA}" ]; then exit 1; fi
```

and afterwards asserts that `T8b` **failed** (`rc != 0`).

---

## 4. Reviewer independence (Phase 3)

### 4.1 What the workflow guarantees

| Property | How |
|---|---|
| Separate host | GitHub-hosted runner — a provisioned VM, not this pod |
| Separate filesystem | fresh checkout per job |
| Separate session | ephemeral runner process |
| Exact commit | pinned SHA + `HEAD` re-verification |
| No source mutation | read-only token, `persist-credentials: false`, no push step |
| No publication | no merge/deploy/release/comment step exists |

### 4.2 What the workflow deliberately does NOT do

The reviewer instructions say, verbatim:

> You are the technical reviewer. Form your own judgment. Nothing in this artifact asserts that the
> change is correct, and a green test run is not a review.
> …
> You may reject this change even though every test above passed.

There is **no** "confirm PASS" instruction, no expected conclusion, and no reuse of the
implementation agent's verdict. The findings template is empty.

### 4.3 The honest limitation

**Execution isolation is real. Judgment independence is not established by this workflow.**

The artifact supplies evidence; a *reviewer* must still supply the judgment. If the implementation
agent also authors the review text, only the host is independent — not the reasoning. The task is
explicit that a separate runner alone does not prove independent technical judgment, and that is
correct.

### 4.4 Available judgment sources — probed, not assumed

| Candidate | Result |
|---|---|
| GitHub Models (LLM in Actions on the built-in token) | **RETIRED 2026-07-30** — catalog, inference API and BYOK all gone. `docs.github.com/en/github-models`: "GitHub Models has been fully retired… no longer available to any customer" |
| Copilot code review | Requires a paid Copilot plan. `GET /user/copilot` → **404**; account `plan=None`; a reviewer request silently returns `requested_reviewers: []` |
| NVIDIA inference API | Real endpoint, but this key can list 33 models and **cannot invoke any** — every call returns `404 … Not found for account`. Also would need a new repo secret (forbidden) |
| OpenHands Cloud LLM proxy | `401 Authentication Error` for both `OPENHANDS_API_KEY` and `PROXY_KEY` |
| Human reviewer (owner) | Works, zero cost, separate host — but the owner is the same principal, and has no local Python/Node toolchain to re-run the suite |

**No reviewer service is available without adding a secret or paying — both forbidden here.**
Per the task instruction, no integration was invented.

### 4.5 Correction to the previous task's report

The prior report claimed GitHub Models was a "verified zero-secret enabler" (HTTP 200). **That was a
false positive.** This sandbox stubs `models.github.ai`: it returns a 4-byte `OK` body for **every**
path, with or without auth, while the real GitHub API returns JSON on the same connection. The service
is also retired. The claim is retracted here; the previous report is left unedited and this note
supersedes it.

---

## 5. Exact workflow diff

New file only — no existing file is modified.

```diff
diff --git a/.github/workflows/f02-review.yml b/.github/workflows/f02-review.yml
new file mode 100644
index 0000000..d6bdcde
--- /dev/null
+++ b/.github/workflows/f02-review.yml
@@ -0,0 +1,252 @@
+name: F-02 Independent Review Evidence
+
+# Collects read-only evidence for an independent technical review of the
+# DEF-011 / F-02 candidate. It never edits source, never pushes, never merges.
+# It produces an evidence artifact; the technical judgment is made by the
+# reviewer who consumes it (see REVIEWER-INSTRUCTIONS.md inside the artifact).
+
+on:
+  pull_request:
+    branches: [main]
+    paths:
+      - "bot/attachments.py"
+      - "bot/handlers.py"
+      - "tests/test_def011_fs_offload.py"
+      - ".github/workflows/f02-review.yml"
+  workflow_dispatch:
+    inputs:
+      head_sha:
+        description: "Exact PR head commit to review (full 40-char SHA)"
+        required: true
+        default: "6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18"
+
+permissions:
+  contents: read
+
+concurrency:
+  group: f02-review-${{ github.event.pull_request.number || inputs.head_sha }}
+  cancel-in-progress: false
+
+jobs:
+  evidence:
+    name: Collect review evidence
+    runs-on: ubuntu-latest
+    timeout-minutes: 25
+    # Only the isolated F-02 review branch is in scope.
+    if: >-
+      github.event_name == 'workflow_dispatch' ||
+      github.head_ref == 'review/ohb2-wp07-def011-f02-isolated'
+    steps:
+      - name: Resolve target commit
+        id: target
+        env:
+          EVENT_NAME: ${{ github.event_name }}
+          PR_HEAD_SHA: ${{ github.event.pull_request.head.sha }}
+          INPUT_SHA: ${{ inputs.head_sha }}
+        run: |
+          set -euo pipefail
+          if [ "${EVENT_NAME}" = "workflow_dispatch" ]; then
+            HEAD_SHA="${INPUT_SHA}"
+          else
+            HEAD_SHA="${PR_HEAD_SHA}"
+          fi
+          case "${HEAD_SHA}" in
+            (*[!0-9a-f]*|"") echo "::error::head_sha must be a full lowercase hex SHA"; exit 1 ;;
+          esac
+          if [ "${#HEAD_SHA}" -ne 40 ]; then
+            echo "::error::head_sha must be 40 characters, got ${#HEAD_SHA}"; exit 1
+          fi
+          echo "head_sha=${HEAD_SHA}" >> "${GITHUB_OUTPUT}"
+          echo "Reviewing head=${HEAD_SHA}"
+
+      - name: Checkout exact head commit
+        uses: actions/checkout@v4
+        with:
+          ref: ${{ steps.target.outputs.head_sha }}
+          fetch-depth: 0
+          persist-credentials: false
+
+      - name: Resolve stable review base
+        id: base
+        run: |
+          set -euo pipefail
+          # merge-base is stable even if main advances, unlike pull_request.base.sha.
+          BASE="$(git merge-base origin/main HEAD)"
+          echo "merge_base=${BASE}"
+          echo "merge_base=${BASE}" >> "${GITHUB_OUTPUT}"
+          if [ "${BASE}" != "52e7789cc8cc97a7f7c09c9592226ab117db99a2" ]; then
+            echo "::warning::merge-base differs from the recorded F-02 base (52e7789)"
+          fi
+
+      - name: Verify the checked-out commit is the intended one
+        env:
+          EXPECTED: ${{ steps.target.outputs.head_sha }}
+        run: |
+          set -euo pipefail
+          ACTUAL="$(git rev-parse HEAD)"
+          echo "expected=${EXPECTED}"
+          echo "actual  =${ACTUAL}"
+          if [ "${ACTUAL}" != "${EXPECTED}" ]; then
+            echo "::error::checked-out commit does not match the requested head"
+            exit 1
+          fi
+          echo "parent=$(git rev-parse HEAD^)"
+
+      - name: Verify F-02-only changed-file scope
+        env:
+          BASE: ${{ steps.base.outputs.merge_base }}
+        run: |
+          set -euo pipefail
+          mkdir -p evidence
+          git diff --name-only "${BASE}" HEAD | tee evidence/changed-files.txt
+          git diff --stat "${BASE}" HEAD | tee evidence/diff-stat.txt
+
+          # Expected scope: exactly these three paths, nothing else.
+          EXPECTED="$(printf '%s\n' bot/attachments.py bot/handlers.py tests/test_def011_fs_offload.py | sort)"
+          ACTUAL="$(sort evidence/changed-files.txt)"
+          if [ "${ACTUAL}" != "${EXPECTED}" ]; then
+            echo "::error::changed-file scope does not match the expected F-02-only set"
+            printf 'expected:\n%s\nactual:\n%s\n' "${EXPECTED}" "${ACTUAL}"
+            exit 1
+          fi
+
+          # No NEW-DEF-03 / NAV-01..06 markers may be introduced.
+          if git diff "${BASE}" HEAD | grep -Eq '^\+.*(NEW-DEF-03|NAV-0[1-6])'; then
+            echo "::error::diff introduces NEW-DEF-03/NAV-01..06 content"
+            exit 1
+          fi
+
+          # Schema / Mini App / dependency / API surfaces must be untouched.
+          if git diff --name-only "${BASE}" HEAD \
+              | grep -Eq '^(bot/db\.py|.*schema.*|migrations/|bot/web/|requirements.*|pyproject\.toml)'; then
+            echo "::error::diff touches a protected surface"
+            exit 1
+          fi
+          echo "scope=ok" >> evidence/scope.txt
+
+      - name: Capture full diff and hashes
+        env:
+          BASE: ${{ steps.base.outputs.merge_base }}
+        run: |
+          set -euo pipefail
+          git diff "${BASE}" HEAD > evidence/full.diff
+          sha256sum evidence/full.diff | tee evidence/diff-sha256.txt
+          git diff "${BASE}" HEAD -- bot/ > evidence/code-only.diff
+          sha256sum evidence/code-only.diff | tee evidence/code-only-sha256.txt
+          sha256sum bot/attachments.py bot/handlers.py bot/db.py \
+            tests/test_def011_fs_offload.py | tee evidence/file-sha256.txt
+
+      - name: Install dependencies
+        run: |
+          set -euo pipefail
+          python -m pip install --upgrade pip
+          pip install -r requirements-dev.txt
+
+      - name: Static analysis (pyflakes)
+        run: python -m pyflakes bot/ automation/ tools/ main.py tests/
+
+      - name: Static analysis (bandit, high severity only)
+        run: python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613
+
+      - name: Run the F-02 regression suite
+        continue-on-error: true
+        run: python -m pytest tests/test_def011_fs_offload.py -q 2>&1 | tee evidence/pytest-f02.txt
+
+      - name: Run the full test suite
+        continue-on-error: true
+        run: python -m pytest -q 2>&1 | tee evidence/pytest-full.txt
+
+      - name: Negative control (F-02 hunk reverted must fail T8b)
+        env:
+          BASE: ${{ steps.base.outputs.merge_base }}
+        run: |
+          set -euo pipefail
+          mkdir -p evidence
+          cp bot/handlers.py /tmp/handlers.fixed.py
+          # Fail closed: a failed revert must abort, not silently test the fixed tree.
+          if ! git checkout "${BASE}" -- bot/handlers.py; then
+            echo "::error::could not revert bot/handlers.py to base; negative control invalid"
+            exit 1
+          fi
+          REVERTED_SHA="$(git hash-object bot/handlers.py)"
+          BASE_SHA="$(git rev-parse "${BASE}:bot/handlers.py")"
+          if [ "${REVERTED_SHA}" != "${BASE_SHA}" ]; then
+            echo "::error::reverted file does not match the base blob; negative control invalid"
+            exit 1
+          fi
+          set +e
+          python -m pytest tests/test_def011_fs_offload.py -q -k T8b \
+            > evidence/negative-control.txt 2>&1
+          rc=$?
+          set -e
+          cp /tmp/handlers.fixed.py bot/handlers.py
+          cat evidence/negative-control.txt
+          if [ "${rc}" -eq 0 ]; then
+            echo "::error::negative control passed; T8b does not discriminate the fix"
+            exit 1
+          fi
+          echo "negative_control=fails_as_expected" | tee evidence/negative-control-result.txt
+
+      - name: Write reviewer instructions
+        if: always()
+        run: |
+          set -euo pipefail
+          mkdir -p evidence
+          cat > evidence/REVIEWER-INSTRUCTIONS.md <<'DOC'
+          # Independent review instructions
+
+          You are the technical reviewer. Form your own judgment. Nothing in this
+          artifact asserts that the change is correct, and a green test run is not
+          a review.
+
+          You must:
+          1. Read `full.diff` and `code-only.diff` yourself.
+          2. Assess correctness, cancellation safety, race conditions, error handling.
+          3. Inspect `tests/test_def011_fs_offload.py` and judge whether the tests are
+             meaningful: do they fail when the fix is absent? What is untested?
+          4. Check the scope guards in `scope.txt`, `changed-files.txt`, and confirm no
+             NEW-DEF-03 / NAV-01..06 behaviour is present.
+          5. Re-run the commands below in your own environment where possible.
+          6. Report findings with file path, line reference, severity, and reproducible
+             evidence.
+
+          You may reject this change even though every test above passed.
+
+          Commands:
+            git diff <base> <head>
+            python -m pytest tests/test_def011_fs_offload.py -q
+            python -m pyflakes bot/ automation/ tools/ main.py tests/
+
+          Out of scope / deferred: D6 (repeated raw cancellation). Do not treat it as
+          fixed. Do not claim exactly-once Telegram delivery or SQLite-Telegram
+          atomicity on behalf of this change.
+          DOC
+
+          cat > evidence/FINDINGS-TEMPLATE.md <<'DOC'
+          # Findings
+
+          Fill this in yourself. Leave it blank if you find nothing.
+
+          | # | File:line | Severity | Finding | Reproducible evidence |
+          |---|-----------|----------|---------|-----------------------|
+          |   |           |          |         |                       |
+
+          ## Judgment
+
+          - Does the F-02 isolation hold?
+          - Is the negative control genuine?
+          - Are the tests sufficient?
+          - Any blocking defect?
+          DOC
+
+          printf 'artifact_built=%s\n' "$(date -u +%FT%TZ)" | tee evidence/manifest.txt
+          ls -la evidence | tee -a evidence/manifest.txt
+
+      - name: Upload review evidence
+        if: always()
+        uses: actions/upload-artifact@v4
+        with:
+          name: f02-review-evidence-${{ steps.target.outputs.head_sha }}
+          path: evidence/
+          retention-days: 30
+          if-no-files-found: error
```

---

## 6. Security considerations

| Risk | Mitigation |
|---|---|
| Workflow could push or merge | `permissions: contents: read`; no write scope; `persist-credentials: false`; no push/merge step |
| Fork PR could exfiltrate secrets | No secrets referenced at all; `pull_request` gives forks a read-only token and no secrets |
| `pull_request_target` misuse | Not used |
| Arbitrary code from the PR running with trust | The job only *reads*; it never checks out into a privileged context |
| SHA injection via dispatch input | Strict `[0-9a-f]{40}` validation before use |
| Branch moves mid-run | Full SHA + `HEAD` re-verification |
| Diff drifts when `main` advances | `merge-base` instead of `pull_request.base.sha` |
| Silent false pass in the negative control | Fail-closed revert + blob hash equality + assert `rc != 0` |
| Evidence lost on test failure | `continue-on-error` + `if: always()` upload |
| Secret leakage into logs | No secrets used; no `env` dump; artifact contains source and test output only |
| Artifact retention | 30 days, then auto-expired |
| Unbounded run | `timeout-minutes: 25` |

No secret, token, or paid integration is introduced.

---

## 7. Remaining prerequisites before this can be applied

1. **Owner authorization to add one workflow file and commit it.** This task forbids creating a
   branch, committing, and pushing. The file must be added by an authorized action.
2. **Owner decision on who supplies the judgment** — the decisive open question (§4.3–4.4). Options:
   - the owner reviews the artifact themselves (zero cost; weak on executed re-verification);
   - the owner authorizes a specific LLM integration plus a repository secret (currently forbidden);
   - the owner adds a second human collaborator with repo access (a permission change; forbidden here).
3. **Owner decision on where findings land** — artifact only (current design), a PR comment (needs
   `pull-requests: write`), or a committed report (needs a push).
4. Confirmation that `workflow_dispatch` is acceptable given `ci.yml` has none today.

Until 1–2 are settled, the workflow can be applied and executed but still cannot produce an
independent review on its own.

---

## 8. Exact commands to apply and validate

**Validate the proposal without applying it** (run in a disposable clone):

```bash
git clone https://github.com/TM-AEM/OpenHandBot.git /tmp/f02-wfd
cd /tmp/f02-wfd && git checkout 6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18
mkdir -p .github/workflows
# write the file from §5, then:
python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/f02-review.yml')); print('YAML OK')"
```

**actionlint** (structural + shellcheck of every `run:` block):

```bash
curl -sL -o /tmp/al.tgz \
  https://github.com/rhysd/actionlint/releases/download/v1.7.7/actionlint_1.7.7_linux_amd64.tar.gz
mkdir -p /tmp/al && tar xzf /tmp/al.tgz -C /tmp/al
/tmp/al/actionlint .github/workflows/f02-review.yml    # expect exit 0, no output
```

**Apply, once authorized** (not performed by this task):

```bash
git checkout -b review/f02-route-d-workflow 6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18
cp /path/to/f02-review.yml .github/workflows/f02-review.yml
git add .github/workflows/f02-review.yml          # explicit path, never -A
git commit -m "ci(f02): add read-only independent review evidence workflow"
git push -u origin review/f02-route-d-workflow
```

**Execute after merge/authorization:**

```bash
gh workflow run f02-review.yml --repo TM-AEM/OpenHandBot \
  -f head_sha=6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18
gh run watch --repo TM-AEM/OpenHandBot
gh run download --repo TM-AEM/OpenHandBot \
  --name f02-review-evidence-6a1ca2e596a26d9ae747c27f4e4361c5a85b0b18 -D /tmp/evidence
```

**Verify the artifact:**

```bash
cd /tmp/evidence && ls -la && cat manifest.txt
sha256sum full.diff                    # must equal diff-sha256.txt
python -m pytest tests/test_def011_fs_offload.py -q   # in a clean clone at 6a1ca2e
```

---

## 9. Verdict

`ROUTE_D_REVIEWER_INDEPENDENCE_NOT_PROVEN`

The workflow design is complete, lint-clean, and its guards are behaviourally validated against the
real commit. It delivers **genuine execution isolation**. It does **not**, by itself, deliver an
**independently generated technical judgment**, and no zero-cost reviewer service exists that could
supply one without adding a secret or paying.
