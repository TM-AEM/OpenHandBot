# OHB2-AUTO-REVIEW-R2 — Implementation Report

> **R2 IMPLEMENTATION — NOT INDEPENDENTLY REVIEWED**
> **Temporary verification mode: AUTHOR_SELF_REVIEW + AUTOMATED_TESTS + SECURITY_TESTS**
> **Independent review is deferred. No `INDEPENDENT_REVIEW_PASS` is claimed.**

**Task ID:** `OHB2-AUTO-REVIEW-R2`
**Date:** 2026-11-24
**UTC:** `2026-11-24T18:02:22Z`
**Verdict:** `R2_VERIFIED_WITH_NOTES`

---

## 1. Scope

R2 only:

1. Reviewer/provider configuration.
2. `.env.example` updates.
3. SQLite `auto_reviews` schema.
4. Atomic reservation and idempotency functions.
5. Immutable per-cycle provider/model configuration snapshots.
6. Tests and reports.

No R3. No GitHub API integration, LLM calls, review prompts, review workers, Telegram review
handlers, runtime activation, or automatic repair.

---

## 2. Fresh baseline

| Item | Value |
|---|---|
| Repository | `/workspace/project/OpenHandBot` |
| Branch | `openhands-workspace-11liARbsA7OSSoFJOM2RDr` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `origin/main` | `01079676351aac869d09d4d1747661cd6f07d82b` |
| Upstream | none |
| Tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| Pre-R2 tracked changes | none |
| Pre-R2 untracked | R0E/R0F/R1 reports and R1 workflow/test files (preserved) |
| Ignored | `.openhands/`, `.pytest_cache/`, `__pycache__/`, `dist/`, `node_modules/` |
| Pre-R2 local suite | 3846 passed (R1 baseline; no R2 tests yet) |

### 2.1 Baseline audit (read-only, before edits)

- `git status --porcelain` showed **no tracked modifications**; the only untracked files were the
  preserved R0E/R0F/R1 reports plus `.github/workflows/verify.yml`,
  `tests/test_verify_workflow_security.py`, and the R1 reports.
- `git status --ignored` showed `.openhands/` ignored and untouched, along with the usual
  `.pytest_cache/`, `__pycache__/`, `dist/`, and `node_modules/`.
- `AGENTS.md` rules were read and followed: no commit/push/PR/deploy, no `git reset`/`clean`,
  no `git add -A`, preserve unrelated work, and use the existing project commands.
- R1 files were read but not modified; R0E/R0F/R1 reports were not overwritten.
- Existing config conventions inspected: `_clean`, `_parse_bool`, `_parse_positive`, `Config`
  dataclass, `ConfigError`, `Config.secrets`, `__repr__` safety.
- Existing DB conventions inspected: WAL, `busy_timeout=5000`, `_init_schema`,
  `_migrate`, `BEGIN IMMEDIATE`-style conditional updates, `commit`/`rollback` usage.
- Existing tests inspected: configuration, DB initialization, DB maintenance, concurrency, and
  attachment transaction tests.

---

## 3. Files changed

### Modified

| File | Reason |
|---|---|
| `bot/config.py` | Reviewer settings, validation, defaults, secret registry |
| `.env.example` | Documented all new review variables (empty values) |
| `bot/db.py` | `auto_reviews` schema, snapshots, atomic reservation |
| `README.md` | Config documentation parity |
| `docs/OPERATIONS_RUNBOOK.md` | Config + schema documentation parity |
| `tests/test_def011_a_option_b_limits.py` | Table-count guard updated **17 → 19** for the two additive R2 tables |
| `tests/test_def011_fs_offload.py` | Same additive table-count update |
| `tests/test_doc_code_parity.py` | Recognize `_parse_bounded_int` env names |

### New

| File | Purpose |
|---|---|
| `tests/test_review_config.py` | R2 configuration/security tests |
| `tests/test_auto_reviews_db.py` | Schema/snapshot/reservation/concurrency tests |
| `docs/reviews/OHB2-AUTO-REVIEW-R2-IMPLEMENTATION-REPORT-20261124.md` | This report |
| `docs/reviews/OHB2-AUTO-REVIEW-R2-AUTHOR-SELF-REVIEW-20261124.md` | Author self-review |

**Workflow files unchanged:** `ci.yml` SHA-256 `f030d01a9ab22079af26ab9139ffd717f13391ff9e339d1646e29bdcabdeda79`; `verify.yml` SHA-256 `948e52ad22031e663edec95601b01d43ce84506473a92cf1ba2137ac77f549e6`.

---

## 4. Configuration

### 4.1 New `Config` fields and defaults

| Field | Env var | Default | Validation |
|---|---|---|---|
| `review_enabled` | `REVIEW_ENABLED` | `False` | strict bool |
| `review_repos` | `REVIEW_REPOS` | `frozenset()` | `owner/repo`, lowercase, deduplicated |
| `reviewer_provider` | `REVIEWER_PROVIDER` | `""` | lowercase provider slug; required when enabled |
| `reviewer_api_base` | `REVIEWER_API_BASE` | `""` | `http(s)://`, no userinfo/fragment/query; HTTPS for non-loopback; `rstrip("/")` |
| `reviewer_api_key` | `REVIEWER_API_KEY` | `""` | secret; length ≥ 8, no whitespace/control; required when enabled |
| `reviewer_model` | `REVIEWER_MODEL` | `""` | model slug; required when enabled |
| `review_github_token` | `REVIEW_GITHUB_TOKEN` | `""` | secret; length ≥ 8, no whitespace/control; required when enabled |
| `review_max_input_chars` | `REVIEW_MAX_INPUT_CHARS` | `120000` | int `1000..1000000` |
| `review_ci_timeout_min` | `REVIEW_CI_TIMEOUT_MIN` | `15` | int `1..120` |
| `review_autofix_rounds` | `REVIEW_AUTOFIX_ROUNDS` | `0` | must be `0` in R2 |

- The feature is **disabled by default**.
- Empty optional credentials are accepted while disabled.
- `REVIEW_ENABLED=1` requires `REVIEW_REPOS`, `REVIEWER_PROVIDER`, `REVIEWER_API_BASE`,
  `REVIEWER_API_KEY`, `REVIEWER_MODEL`, and `REVIEW_GITHUB_TOKEN`.
- Invalid values raise `ConfigError` without echoing the value.
- `Config.secrets` now returns a `tuple[str, ...]`: the two existing secrets plus non-empty
  `REVIEWER_API_KEY` / `REVIEW_GITHUB_TOKEN` (deduplicated). Existing callers are compatible.
- `Config.__repr__` remains secret-free and now includes only `review_enabled`.
- No real provider, model, API key, or Base URL is a default.

---

## 5. Database schema and invariants

### 5.1 `auto_review_provider_snapshots`

| Column | Notes |
|---|---|
| `id` | integer primary key |
| `provider` | normalized provider identifier |
| `api_base` | normalized base URL |
| `model` | model identifier |
| `config_json` | canonical non-secret JSON |
| `config_fingerprint` | SHA-256 of canonical JSON; unique |
| `created_at` | timestamp |

- `UPDATE`/`DELETE` are blocked by triggers.
- No API key/token column or JSON field exists.
- `config_json` rejects keys containing `key`, `token`, `secret`, `password`, `credential`,
  `authorization`, or `auth` (recursively).

### 5.2 `auto_reviews`

| Area | Columns |
|---|---|
| Identity | `id`, `reservation_key` (unique), `conversation_id`, `repository_id`, `repository_full_name`, `pr_number` |
| Revision | `branch`, `base_sha`, `head_sha` |
| State | `scope`, `status`, `stage`, `terminal_reason` |
| Future evidence | `ci_run_id`, `ci_conclusion`, `verdict`, `report_ref` |
| Config | `provider_snapshot_id` FK → snapshots, `rounds` |
| Reservation | `reserved_by`, `reserved_at` |
| Timestamps/errors | `created_at`, `updated_at`, `error_class`, `error_detail` |

Invariants:

- `repository_id` is the stable numeric identity; `repository_full_name` is a mutable snapshot.
  Idempotency compares `repository_id`, not the mutable full name, so a rename/case change does
  not create a false identity conflict.
- `scope` is explicit: `conversation` or `per_pr`; no silent policy choice.
- `pr_number` is required for `per_pr`; nullable for `conversation`.
- `reservation_key` is the exact-event idempotency key.
- Partial unique indexes:
  - `UNIQUE(conversation_id) WHERE status='reserved' AND scope='conversation'`
  - `UNIQUE(conversation_id, repository_id, pr_number) WHERE status='reserved' AND scope='per_pr'`
- Cross-scope mixing is rejected while a conversation has an active review.
- `status` is `reserved`/`terminal`; `stage` is separate (R2 writes only `reserved`).
- No worker lease/fencing fields are implemented; those remain R5.
- No plaintext credentials are stored in either table.

---

## 6. Atomic reservation

`Database.reserve_auto_review(...)`:

1. Validates all inputs before any write.
2. Uses `BEGIN IMMEDIATE`.
3. Verifies the provider snapshot exists.
4. Returns `already_reserved` for the same key + same identity.
5. Returns `conflicting_identity` for the same key + different identity.
6. Returns `conflicting_identity` for an active scope conflict or mixed scope.
7. Inserts with `INSERT OR IGNORE`; a race is re-read and classified.
8. Commits on success; rolls back on every failure path.
9. Returns one of:
   - `newly_reserved`
   - `already_reserved`
   - `conflicting_identity`
   - `invalid_input`

No partial row remains after a failure. No second SQLite owner/worker/thread is created.

---

## 7. Snapshot behavior

- `get_or_create_auto_review_provider_snapshot(...)` normalizes provider (lowercase), API base
  (`strip` + `rstrip("/")`), and model (`strip`).
- Fingerprint = SHA-256 of canonical JSON over `{provider, api_base, model, settings}`.
- Same settings ⇒ same snapshot ID (idempotent).
- Changing provider/model/settings ⇒ new snapshot ID.
- Existing `auto_reviews` rows keep their `provider_snapshot_id`; they do not switch after
  restart or config change.
- No secret is part of the fingerprint or snapshot JSON.

---

## 8. Tests and exact commands

| Command | Result | Exit |
|---|---|---|
| `python -m pytest -q tests/test_review_config.py tests/test_auto_reviews_db.py` | **63 passed** | 0 |
| `python -m pytest -q tests/test_config.py tests/test_4b.py tests/test_db.py tests/test_db_maintenance.py tests/test_miniapp_config.py tests/test_sw06_unwatch_db_failure_propagation.py` | **215 passed** | 0 |
| `python -m pytest -q` | **3909 passed, 74 warnings** in 256.13s | 0 |
| `node --test tests/frontend/*.test.js` | **280 pass, 0 fail** | 0 |
| `python -m pyflakes bot/ automation/ tools/ main.py tests/` | **no output** | 0 |
| `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | **No issues identified; High 0** | 0 |
| `python -m pip_audit -r requirements-dev.txt` | **No known vulnerabilities found** | 0 |

The full suite includes the R1 workflow tests and the R2 tests. The two existing table-count
guards were updated from 17 to 19 because R2 adds two tables additively; no test was deleted or
disabled.

---

## 9. Negative controls

Covered by `tests/test_review_config.py` and `tests/test_auto_reviews_db.py`:

- Invalid base URLs: FTP, external HTTP, userinfo, query, fragment, malformed.
- Invalid provider/model identifiers.
- Invalid numeric bounds and `REVIEW_AUTOFIX_ROUNDS != 0`.
- Invalid repository allowlist entries.
- Missing required settings when enabled.
- Secret leakage in `ConfigError`, `repr`, logs, DB rows, and DB file bytes.
- Secretish snapshot config keys rejected.
- Duplicate event ⇒ idempotent; same key + different identity ⇒ conflict.
- Active conversation scope / per-PR scope conflicts.
- Mixed scopes rejected.
- Missing provider snapshot ⇒ invalid input.
- Invalid identity fields (SHA, repository ID, conversation ID, PR number).
- Transaction rollback via a forced insert trigger ⇒ zero rows.
- Concurrent same-key and different-key reservations.
- Snapshot UPDATE/DELETE blocked by triggers.
- Existing unrelated database rows preserved.
- Repeated initialization does not duplicate schema objects.

---

## 10. Author self-review

Recorded separately in
`docs/reviews/OHB2-AUTO-REVIEW-R2-AUTHOR-SELF-REVIEW-20261124.md`.

Summary:

- Config defaults, required-when-enabled behavior, secret redaction, and secret registry are
  covered.
- Snapshot immutability and provider/model change isolation are covered.
- Reservation transaction boundaries and concurrency are covered.
- No unrelated database rows are modified.
- No provider/network calls or external effects.
- **INFO:** final scope policy (conversation-wide vs per-PR) remains an owner decision; R2
  supports both explicitly and rejects mixing, but does not choose for R3.
- **INFO:** credential rotation/version binding is represented only by the non-secret
  fingerprint; exact credential-version binding is deferred.

---

## 11. Deferred design decisions and blockers

| Item | Status |
|---|---|
| Conversation-wide vs per-PR review policy for R3 | **Owner decision required.** R2 supports both via explicit `scope`; no default. |
| Credential rotation/version binding | **Deferred.** Non-secret fingerprint only; no secret copy. |
| Worker lease/fencing/recovery | **R5.** Not implemented. |
| GitHub API / LLM / prompts / worker / Telegram handlers | **R3+.** Not implemented. |
| R0E lifecycle/repository/concurrency/billing proposals | **Proposed, not approved.** Not silently adopted. |
| R1 remote GitHub Actions | **NOT_RUN.** |
| R2 independent review | **Deferred.** |
| R3 | **Not started.** |

---

## 12. Git publication state

| Item | State |
|---|---|
| Commit | **no** |
| Push | **no** |
| PR/merge/deploy/release | **no** |
| Autopush | **disabled/inactive; untouched** |
| Tracked modifications | 8 files (config, DB, docs, tests) |
| New untracked files | 2 R2 tests, 2 R2 reports, prior R0E/R0F/R1 artifacts |
| Production database | **not touched** |
| `ci.yml` / `verify.yml` | **unchanged** |

---

## 13. Independent review and external effects

**Independent review is deferred.** This is author self-review plus automated/security tests.
No `INDEPENDENT_REVIEW_PASS` is claimed.

No provider inference, provider API call, external data egress, Katabump operation, production
database modification, commit, push, PR, merge, deploy, or release occurred.

**R3 has not started.**

---

## 14. Verdict

# `R2_VERIFIED_WITH_NOTES`

Configuration, schema, snapshots, atomic reservation, rollback, concurrency, secret handling,
and documentation parity are locally verified. The final scope policy for R3 and credential
rotation binding remain owner decisions; R2 does not silently choose them.
