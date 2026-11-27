# OHB2-AUTO-REVIEW-R2 — Author Self-Review

> **AUTHOR_SELF_REVIEW — NOT INDEPENDENT REVIEW**
> **No `INDEPENDENT_REVIEW_PASS` is claimed. Independent review is deferred.**

**Task ID:** `OHB2-AUTO-REVIEW-R2`
**Date:** 2026-11-24
**UTC:** `2026-11-24T18:02:22Z`
**Reviewer:** the R2 implementation author (same session/agent)
**Verdict:** `R2_VERIFIED_WITH_NOTES` (author self-review + automated/security tests)

---

## 1. Scope reviewed

- `bot/config.py`
- `.env.example`
- `bot/db.py`
- `tests/test_review_config.py`
- `tests/test_auto_reviews_db.py`
- `README.md`
- `docs/OPERATIONS_RUNBOOK.md`
- table-count/doc-parity test updates

No R3, GitHub API, LLM, prompt, worker, Telegram handler, or runtime activation was added.

---

## 2. Checklist

| Area | Result | Evidence |
|---|---|---|
| Feature disabled by default | PASS | `test_review_disabled_by_default` |
| Empty optional credentials accepted while disabled | PASS | `test_empty_optional_credentials_accepted_while_disabled` |
| Required settings validated when enabled | PASS | parametrized `test_enabled_requires_each_review_setting` |
| Invalid Base URL rejected | PASS | FTP/HTTP/userinfo/query/fragment/malformed tests |
| Invalid provider/model rejected | PASS | provider/model parametrized tests |
| Invalid numeric settings rejected | PASS | bounds and autofix tests |
| Repo allowlist normalized/validated | PASS | normalization + invalid entries tests |
| Secrets redacted in errors/repr/logs | PASS | `test_review_secrets_are_in_registry_and_not_in_repr_or_errors`, log redaction test |
| Secrets in `Config.secrets` | PASS | `test_enabled_accepts_full_config_and_normalizes` |
| Provider/model changes affect new cycles only | PASS | snapshot IDs + reopen test |
| Schema created | PASS | `test_schema_created_and_initialization_is_idempotent` |
| Idempotent initialization | PASS | same test, schema-object count stable |
| Existing DB preserved | PASS | unrelated table/row test |
| Atomic reservation | PASS | `BEGIN IMMEDIATE` + new/duplicate/conflict tests |
| Duplicate event idempotency | PASS | `test_duplicate_event_is_idempotent...` |
| Conflicting identity rejected | PASS | same-key different-identity test |
| Transaction rollback | PASS | forced trigger failure ⇒ zero rows |
| Concurrent reservation safety | PASS | same-key and different-key thread tests |
| Snapshot immutability | PASS | UPDATE/DELETE trigger tests |
| No plaintext credentials persisted | PASS | DB row + DB file byte scan |
| Reopen behavior | PASS | provider/model isolation test reopens DB |
| Mixed scopes rejected | PASS | conversation vs per-PR active guard |
| No destructive migration | PASS | additive `CREATE TABLE IF NOT EXISTS` only |
| Workflows unchanged | PASS | `ci.yml`/`verify.yml` hashes match R1 |
| Full suite no regression | PASS | 3909 Python passed; 280 Node passed |

---

## 3. Findings

### INFO-01 — Final conversation-vs-PR policy remains an owner decision

R2 implements both `scope='conversation'` and `scope='per_pr'` with explicit caller input and
rejects mixing. It does **not** choose the R3 policy and does not default to either. This is
intentional and documented.

- Severity: **INFO / deferred decision**
- Action: owner must choose the R3 scope policy before R3 wiring.

### INFO-02 — Credential rotation binding is not implemented

Snapshots bind provider/API base/model/non-secret settings by fingerprint. They do not bind a
credential version, and they never copy the API key/token. Exact credential-version binding is
deferred.

- Severity: **INFO / deferred decision**
- Action: define a safe secret reference/versioning mechanism later if required.

### INFO-03 — `REVIEW_GITHUB_TOKEN` is required when enabled

R2 does not use GitHub, but `REVIEW_ENABLED=1` requires the token for a complete future config.
This is a configuration contract, not a network call.

- Severity: **INFO**
- Action: none for R2.

### INFO-04 — Minimal lifecycle fields

`auto_reviews.status` (`reserved`/`terminal`) and `stage` (`reserved`) are intentionally minimal.
No lease, worker fencing, or recovery fields exist; those remain R5. R2 does not claim a terminal
review cannot have a stale worker because no worker exists yet.

- Severity: **INFO**
- Action: R5 design.

### INFO-05 — Future evidence columns are nullable and unused

`ci_run_id`, `ci_conclusion`, `verdict`, `report_ref`, `error_class`, and `error_detail` are
present because the R2 minimum data list requires them. R2 writes only reservation fields.

- Severity: **INFO**
- Action: R3–R5 populate them.

### INFO-06 — Python 3.11 not available locally

The full suite ran on Python 3.13. The R1 workflow matrix covers 3.11/3.13; remote execution is
still `NOT_RUN`.

- Severity: **INFO / verification limitation**
- Action: later authorized CI run.

### INFO-07 — Existing table-count guards updated

Two historical tests asserted exactly 17 tables. R2 adds two tables additively, so the guards
were updated to 19 and now also assert the two R2 table names exist. No test was deleted or
disabled.

- Severity: **INFO**
- Action: none.

### INFO-08 — Mutable repository name is not part of idempotency identity

`repository_full_name` is stored as a snapshot but is **not** compared in
`_auto_review_identity_matches`; `repository_id` is the stable identity. A rename/case change
therefore returns `already_reserved` instead of a false `conflicting_identity`. The stored row
retains its original full-name snapshot. Covered by
`test_repository_name_snapshot_does_not_break_idempotency`.

- Severity: **INFO**
- Action: none for R2.

---

## 4. Architecture compliance

| Constraint | Status |
|---|---|
| One bot + ASGI process | Preserved; no new process |
| One authoritative SQLite owner | Preserved; methods on `Database` |
| Existing DB initialization/transaction conventions | Preserved; `CREATE TABLE IF NOT EXISTS`, `BEGIN IMMEDIATE`, rollback |
| Existing worker architecture | No worker added |
| Direct Model API via replaceable adapter | Not implemented in R2; config/snapshot only |
| Optional future proxy adapter | Not implemented; no review logic coupling |
| Reviewer model different from execution model | Config has separate reviewer fields; no execution model coupling |
| Separate Blind/Adversarial stages | Not implemented; `stage` only `reserved` |
| Deterministic final verdict rules | Not implemented |
| Review disabled by default | Yes |
| No automatic prompt repair | `REVIEW_AUTOFIX_ROUNDS` must be 0 |
| Autopush disabled/inactive | Untouched |
| D1 decisions | Untouched |

---

## 5. Negative controls reviewed

- Missing/invalid required settings rejected.
- Invalid URL/provider/model/numeric/repo inputs rejected.
- Secretish snapshot config rejected.
- Same-key duplicate returns `already_reserved`.
- Same-key different identity returns `conflicting_identity`.
- Active conversation/per-PR conflict returns `conflicting_identity`.
- Mixed scopes rejected.
- Missing snapshot returns `invalid_input`.
- Forced insert failure rolls back with zero rows.
- Concurrent same-key/different-key calls return one winner and one idempotent/conflict result.
- Snapshot UPDATE/DELETE blocked.
- Existing unrelated rows preserved.
- Secret sentinels absent from DB rows and DB file bytes.

---

## 6. Conclusion

No CRITICAL/HIGH/MEDIUM defect was found in the R2 diff. R2 is locally verified with notes:
the final scope policy and credential-version binding are owner decisions, and R3 has not
started.

**This is not independent review.** Independent review remains deferred.
