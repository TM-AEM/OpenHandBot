> **R3 IMPLEMENTATION — NOT INDEPENDENTLY REVIEWED**
>
> Verification mode: `AUTHOR_SELF_REVIEW` + `AUTOMATED_TESTS` + `SECURITY_TESTS`.
> Independent review remains deferred. This report does not claim
> `INDEPENDENT_REVIEW` or `INDEPENDENT_REVIEW_PASS`.

# OHB2-AUTO-REVIEW-R3 — Implementation Report

**Task:** OHB2-AUTO-REVIEW-R3 — Read-Only GitHub Integration and Secure Diff Redaction
**UTC:** `2026-11-24T18:41:47Z`
**Verdict:** `R3_VERIFIED_WITH_NOTES`

---

## 1. Objective and scope

Implemented the R3 primitives only:

- `bot/review/github.py` — read-only GitHub API client.
- `bot/review/redact.py` — deterministic, fail-closed text/diff redaction.
- Focused tests for both modules.

Not implemented: R4, Blind/Adversarial Review, prompts, LLM/provider calls, verdicts,
ReviewWorker, Telegram handlers, conversation-to-PR scope selection, runtime activation,
automatic repair, Katabump, production database changes.

---

## 2. Baseline audit (recorded before edits)

| Item | Value |
|---|---|
| Repository | `/workspace/project/OpenHandBot` |
| Branch | `openhands-workspace-11liARbsA7OSSoFJOM2RDr` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `main` | same as HEAD |
| `origin/main` | same as HEAD |
| Upstream | none |
| Tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| Pre-R3 tracked modifications | 8 R2 files (preserved) |
| Pre-R3 untracked | R0E/R0F/R1/R2 reports, R1 workflow/security test, R2 tests (preserved) |
| Ignored | `.openhands/`, caches, `dist/`, `node_modules/` (untouched) |
| Pre-R3 Python suite | 3909 passed |
| Pre-R3 Node suite | 280 pass / 0 fail |
| Pre-R3 static checks | pyflakes 0; Bandit High 0; pip-audit clean |

`AGENTS.md` commands and safety rules were followed. No reset/clean/force/add-all was used.

### Scope-policy gate

No explicit owner decision for `conversation-wide` vs `per_pr` was found. R0E/R0F/R2 records
still mark it unresolved. R3 therefore implements only scope-independent GitHub/redaction
primitives; it does not select a policy, default a policy, or change R2's explicit `scope`.

---

## 3. Files changed or created

### Created

| File | Purpose |
|---|---|
| `bot/review/__init__.py` | Review package marker |
| `bot/review/github.py` | Read-only GitHub client and validated result models |
| `bot/review/redact.py` | Secret redaction, path denylist, bounds, diff preservation |
| `tests/test_review_github.py` | GitHub client behavior, SHA provenance, error/security tests |
| `tests/test_review_redact.py` | Secret/path/binary/traversal/bounds/diff tests |
| `docs/reviews/OHB2-AUTO-REVIEW-R3-IMPLEMENTATION-REPORT-20261124.md` | This report |
| `docs/reviews/OHB2-AUTO-REVIEW-R3-AUTHOR-SELF-REVIEW-20261124.md` | Author self-review |

### Modified

| File | Purpose |
|---|---|
| `.agent/PROGRESS.md` | Added the R3 goal, baseline, acceptance criteria, plan, status |

R1/R2 source, tests, reports, and workflows were preserved. `ci.yml` and `verify.yml` were not
modified.

---

## 4. GitHub client

### Public capabilities

| Capability | Method | Evidence binding |
|---|---|---|
| List `agent/*` branches | `list_agent_branches(repository)` | Returns each branch's current SHA |
| Branch metadata | `get_branch(repository, branch)` | Returns exact branch SHA |
| Branch movement check | `verify_branch_sha(repository, branch, expected_sha)` | `unchanged` / `moved` / `missing` / `blocked` |
| Compare explicit SHAs | `compare(repository, base_sha, head_sha)` | Validates base, head, merge-base; mismatch exposes no files/commits |
| Actions runs by SHA | `get_workflow_runs_for_sha(repository, head_sha)` | Validates every run `head_sha` |
| Direct run | `get_workflow_run(repository, run_id, expected_head_sha=...)` | Expected SHA required |
| Jobs for run | `list_run_jobs(repository, run_id, head_sha)` | Validates every job `head_sha` and `run_id` |
| CI state | `WorkflowRunsEvidence.ci_state` / `is_success` | Success requires verified non-empty all-completed/all-success runs |

### Validation and safety

- Repository must be `owner/repo`, present in the fail-closed allowlist, and contain no `.`/`..`
  segments.
- SHA must be exactly 40 lowercase hex characters.
- Branch names reject traversal, control/whitespace, `..`, `@{`, `\`, and invalid ref
  characters; branch path segments are URL-quoted.
- Base URL must be HTTPS without credentials, query, fragment, or `..` path segments.
- Token must be non-empty, at least 8 characters, without whitespace/control characters.
- `allowed_repositories` is required for any repository operation; an empty allowlist rejects
  all repositories.
- No POST/PUT/PATCH/DELETE method is exposed.

### HTTP behavior

- GET only; `Authorization: Bearer <token>` header only; token never in URL/query.
- `trust_env=False`; redirects disabled; HTTPS only.
- Timeout default 10 s, maximum 60 s.
- Response cap default 2 MiB, maximum 16 MiB; `Accept-Encoding: identity`; non-identity
  encoding rejected; raw bytes capped; `Content-Length` is an additional early guard.
- Pagination: `per_page` 1..100, `max_pages` 1..100; a full final allowed page raises
  `GitHubPaginationError` rather than silently truncating.
- Error mapping: 401 auth, 403 forbidden or rate-limit, 404 not-found, 429 rate-limit, 5xx
  server, other 4xx/3xx response error, transport/timeout error, malformed JSON/shape.
- Error messages contain status/class/retry metadata only; never response bodies or tokens.
- `repr(GitHubClient)` contains base URL and allowlist only.

---

## 5. Redaction

### Public capabilities

- `redact_text(text, max_input_chars=..., max_output_chars=...)`
- `redact_diff(diff_text, max_input_chars=..., max_output_chars=...)`
- Structured `RedactionResult` with `status`, `text`, bounds, `truncated`,
  `blocked_reason`, `excluded_paths`, redaction counts, and per-file status.

### Secret handling

Redacts/masks:

- Private-key PEM blocks.
- `Authorization: Bearer/Basic/token` headers and standalone Bearer tokens.
- URL/connection-string credentials.
- GitHub tokens (`ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_`, `github_pat_`).
- OpenAI-style `sk-` keys, AWS access keys, Slack tokens, Stripe keys, Google API keys, JWTs.
- Generic `api_key` / `access_key` / `secret` / `token` / `password` assignments (quoted and
  unquoted, including diff `+`/`-`/context prefixes).
- Query parameters such as `?token=...`.

Placeholders are `[REDACTED:<type>]`; redaction counts contain type names/counts only. The
sanitized output is re-scanned; any remaining match fails closed with
`blocked_reason="rescan_found_secret"`. Secret values in paths are redacted from result metadata.

### Path and content handling

- Excludes `docs/**`, `*.patch`, `*.zip`, and any basename `package-lock.json`.
- Normalizes diff prefixes, backslashes, `./`, repeated slashes, percent-encoding (twice),
  Unicode NFKC, and case for denylist checks.
- Rejects absolute paths, drive paths, `.`/`..` traversal, control characters, overlong paths,
  and malformed/missing paths (fail closed).
- Excludes Git binary markers (`Binary files ... differ`, `GIT binary patch`, `literal`, NUL).
- Preserves `diff --git`, `---`, `+++`, `@@` and complete file sections; truncates only at
  whole-section boundaries and reports `truncated=True`.
- Input over `max_input_chars` returns `status="oversized"` with no text, rather than silently
  truncating.

---

## 6. SHA provenance evidence

| Path | Evidence |
|---|---|
| Branch discovery | `get_branch` parses exact `commit.sha`; `verify_branch_sha` compares against expected and returns `moved` on change |
| Compare | Request path uses `base...head`; validates `base_commit.sha == base`, `commits[-1].sha == head`, `merge_base_commit.sha == base`; mismatch returns `base_sha_mismatch` / `head_sha_mismatch` / `merge_base_mismatch` with empty files/commits |
| Actions runs | Request query uses `head_sha`; every returned run must have the same `head_sha`; any mismatch returns `status="sha_mismatch"`, `ci_state="stale"`, and empty runs |
| Jobs | Requires expected `head_sha`; every job must match both `head_sha` and `run_id`; any mismatch returns `status="sha_mismatch"` with empty jobs |
| Direct run | `expected_head_sha` is required and validated before the HTTP request; mismatch raises `GitHubShaMismatchError` |
| CI success | `is_success` is true only when evidence is verified, runs are non-empty, every run is completed, and every conclusion is `success` |

No branch tip is substituted for an explicit SHA. A workflow run's mere existence is never
reported as success.

---

## 7. Tests and exact results

| Command | Result | Exit |
|---|---|---|
| `python -m pytest -q tests/test_review_github.py tests/test_review_redact.py` | **86 passed** | 0 |
| `python -m pytest -q tests/test_review_config.py tests/test_auto_reviews_db.py tests/test_verify_workflow_security.py tests/test_doc_code_parity.py` | **101 passed** | 0 |
| `python -m pytest -q` | **3995 passed, 74 warnings** in 238.54s | 0 |
| `node --test tests/frontend/*.test.js` | **280 pass, 0 fail** | 0 |
| `python -m pyflakes bot/ automation/ tools/ main.py tests/` | no output | 0 |
| `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | No issues identified; High 0 | 0 |
| `python -m pip_audit -r requirements-dev.txt` | No known vulnerabilities found | 0 |
| `python -m compileall -q bot/ automation/ tools/ main.py tests/` | success | 0 |
| `git diff --check` | no output | 0 |

---

## 8. Negative controls

Isolated copy: `/tmp/r3-negative` (copy of `bot/` and the two R3 test files). Baseline on the copy:
85 passed. The repository was not mutated.

| Mutation | Targeted test | Result |
|---|---|---|
| Disable compare base-SHA check | `test_compare_rejects_evidence_for_another_sha` | **1 failed** (`verified` vs `base_sha_mismatch`) |
| Make `_is_excluded` always false | excluded/alternate-path tests | **9 failed** |
| Disable both response-size guards | `test_oversized_response_is_rejected` | **1 failed** |
| Make `_redact_secrets` a no-op | common-secret tests | **9 failed** (fail-closed `blocked`) |
| Remove `..` rejection | traversal tests | **4 failed** |

These controls show the tests reject insecure variants; they are not independent review.

---

## 9. Security analysis

- Read-only: only GET operations exist; no write methods, shell, or code execution.
- Token lifecycle: injected at construction, sent only in the Authorization header, absent from
  URLs, errors, `repr`, and logs; no logging statements in either module.
- Network isolation: tests use `httpx.MockTransport` and fake credentials; no real GitHub,
  provider, or LLM requests were made.
- Egress: R3 does not transmit repository data; redaction is local and returns structured data.
- Response handling: bounded timeout/size, identity encoding, no redirects, no error-body
  reflection, strict JSON/shape validation.
- Allowlist: fail-closed repository allowlist; repository and branch path injection checks.
- Redaction: fail-closed on rescan; excluded paths normalized before exclusion; binary and
  traversal paths omitted/blocked; oversized input never silently truncated.

---

## 10. Unresolved dependency and limitations

### Required owner decision

Before R5 orchestration, the owner must choose the review scope policy:

- conversation-wide serialization, or
- per-PR serialization.

R3 does not choose or default either. R2's explicit `scope` behavior is unchanged.

### R3 limitations (documented, not hidden)

1. `get_workflow_runs_for_sha` is conservative: it evaluates all runs for the SHA and has no
   "latest per workflow/check" or required-check policy. An older failed run can make
   `ci_state="failure"` even if a newer run succeeded. R5 must implement selection rules.
2. `compare` requires `merge_base_commit.sha == base_sha`; callers must pin the merge base.
3. `ChangedFile.patch` is returned as GitHub-provided text. It must pass through
   `redact_diff` before any external submission; R3 does not transmit it.
4. Redaction is pattern-based; no entropy detector. Legacy 40-hex GitHub tokens are
   indistinguishable from git SHAs and are not redacted when bare (contextual assignments are).
5. Binary detection relies on Git binary markers/NUL; an unmarked binary diff could be treated
   as text.
6. No retry/backoff; rate-limit metadata is exposed for the caller.
7. HTTPS only and `trust_env=False`; an enterprise proxy requirement needs a later explicit
   design.
8. Python 3.11 was not available locally; full suite ran on 3.13.15. CI was not run.
9. `bot/review/github.py` is large (822 lines); it follows the project's existing single-module
   style, but later splitting by responsibility may be warranted.

---

## 11. Git and publication state

- No commit.
- No push.
- No PR/MR.
- No merge.
- No deployment/release.
- Autopush remained disabled/inactive.
- No `git reset`, `git clean`, force operation, or broad deletion.
- `.openhands/` preserved.
- R0E/R0F/R1/R2 artifacts preserved.
- Final working tree: `.agent/PROGRESS.md` modified; R3 new files untracked; prior R2 tracked
  modifications remain.

---

## 12. Explicit statements

- **Independent review remains deferred.** No `INDEPENDENT_REVIEW_PASS`.
- **R4 has not started.**
- No provider inference, LLM call, external model egress, real GitHub request, paid API call, or
  Katabump operation occurred.
- No production database was modified.
- No workflow was modified.

---

## 13. Hashes

### Source and tests (final)

| File | SHA-256 |
|---|---|
| `bot/review/__init__.py` | `f6d59dacf54d77c5dcd046b36ef3aad37bc25819841f79d309cc26e09f04e61e` |
| `bot/review/github.py` | `7a0961a1b321a71fbedbbf728eef7ca30b22a7af0a370295672000c0bbec2c56` |
| `bot/review/redact.py` | `9f38534e4e0d4ca48cf44149ba11bcfedbed45fc520a9a243ae43f8cbc5b16fb` |
| `tests/test_review_github.py` | `c9709562babf462249794c6b834ea433c42842fe094f0ed856694e3e4fa2a612` |
| `tests/test_review_redact.py` | `b598f8e251efbc1df358636baf988c74f356fe37268a54dc0a7bf8c5d4e5d483` |
| `.agent/PROGRESS.md` | `40796a71f753315aa25a01eb0ed06aa6043fe68ae829bf7f81eb11fe26fd418b` |

### Workflows (unchanged)

| File | SHA-256 |
|---|---|
| `.github/workflows/ci.yml` | `f030d01a9ab22079af26ab9139ffd717f13391ff9e339d1646e29bdcabdeda79` |
| `.github/workflows/verify.yml` | `948e52ad22031e663edec95601b01d43ce84506473a92cf1ba2137ac77f549e6` |
| `tests/test_verify_workflow_security.py` | `66957890c0a85b809b9c179d1080f03911f3c316cb1c95e4e49702b01b2880a3` |

### Report hash convention

`REPORT_HASH` below is SHA-256 of this report with the `REPORT_HASH:` line removed. This avoids a
self-referential hash; the final full-file hash is recorded in the handoff.

REPORT_HASH: `67bae882164e06c4ff269e2d28b6a2a0a955e52253a92906187d1f8078abedc1`
