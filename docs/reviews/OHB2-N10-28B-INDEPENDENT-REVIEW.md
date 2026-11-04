# OHB2-N10-28B — INDEPENDENT SECURITY REVIEW (fresh-context, read-only)

Reviewer: fresh-context independent security reviewer; not the author of 28B. All actions were
read-only. No file modifications or fixes. No staging, commits, pushes, fetches, pulls, PRs,
merges, or deployment. Autopush was **not** executed and no automation was activated. No real
credentials were used (synthetic canary only); no GitHub write operations; no backup-file or
`requirements.txt` changes. All temporary repositories/files were created under `/tmp` and removed.

Verdict: **PASS_WITH_NOTES** — the hardening is sound and correct for its intended (disabled,
inactive) automation, with no CRITICAL/HIGH findings. Several LOW/INFO notes, of which one (L-1)
is a latent plaintext-leak path that is unreachable under the documented configuration and should
be tracked.

---

## 1. Repository state and changed files

- HEAD = `6021658cf3c1664ed0eadeaed2acee4e86721b6b` (matches EXPECTED).
- Branch = `release/ohb2-20261101`. Index = empty. Stash = empty. Nothing committed/pushed.
- 28B scope:
  - Modified (tracked): `automation/autopush/main.py`, `automation/autopush/README.md`.
  - New (untracked): `tests/test_autopush_security.py` (25 tests),
    `tests/test_autopush_automation.py` (4 tests).
  - Report (untracked): `docs/reviews/OHB2-N10-28B-SECURITY-REPORT.md`.
- No other file touched by this review; target report
  `docs/reviews/OHB2-N10-28B-INDEPENDENT-REVIEW.md` was absent before creation.

## 2. Exact commands, exit codes, counts, warnings

| # | Command | Result | Exit |
|---|---|---|---|
| 1 | `.venv/bin/python -m pytest tests/test_autopush_security.py tests/test_autopush_automation.py -q` | **29 passed** (1.32s) | 0 |
| 2 | same, repeated ×5 | 29 passed each | 0 |
| 3 | `.venv/bin/python -m pytest -q` (full suite) | **1513 passed, 71 warnings** (52.63s) | 0 |
| 4 | `.venv/bin/python -m pyflakes automation/autopush/main.py tests/test_autopush_security.py tests/test_autopush_automation.py` | clean (no output) | 0 |

Warnings are pre-existing deprecation warnings (PTB/starlette). No skips/xfails. No network was
used; the automation tests use local bare repositories only.

## 3. Credential handling — independently challenged

**Verified correct:**
- **Helper transport.** `_CRED_HELPER` (main.py:64-67) is injected via
  `GIT_CONFIG_COUNT/KEY_0/VALUE_0` in `_child_env` (main.py:183-186). git passes the helper string
  to `sh` via `-c` (no user-controlled interpolated path). The helper reads `$GITHUB_TOKEN` from the
  child env and `exit 1`s when it is empty (probe: empty/unset ⇒ rc=1, no output).
- **No credential in argv.** `_sanitize_args` (main.py:190-203) strips userinfo from URL args and
  raises `AutopushError` for any other token-bearing arg (probe: refused before any subprocess).
  Push uses the remote **name** (`git push origin HEAD:main`, main.py:396) — confirmed argv
  `['git','push','origin','HEAD:main']`, no canary.
- **No credential in `.git/config`.** No credential-bearing URL is ever passed; the only
  `set-url` writes `REPO_URL` (main.py:257). Test `test_credential_not_written_to_git_config`
  exercises a real local repo and asserts the canary is absent from `.git/config` and that
  `credential.helper` is empty there.
- **Child-env minimization.** `_GIT_ENV_KEYS` (main.py:75-79) forwards only a fixed allowlist;
  `AUTOMATION_CALLBACK_API_KEY`, `OPENHANDS_API_KEY`, `SESSION_API_KEY` are **not** forwarded
  (probe confirmed).
- **Redaction.** `redact()` (main.py:165-171) scrubs the cached token and `GITHUB_TOKEN`; applied to
  stdout/stderr (main.py:226/228), exception text (main.py:431/438), callback body (main.py:150),
  and callback errors (main.py:162). Probes confirmed the canary never appears in captured
  stdout/stderr or `AutopushError` text (`test_credential_absent_from_captured_output`,
  `test_credential_absent_from_exception_text`, `test_failed_credential_operation_does_not_expose_secret`).
- **Missing credential fails safe.** `resolve_token` returns `_PLACEHOLDER_TOKEN`
  (main.py:140); `_child_env` forwards the placeholder; `push_if_ahead` still runs but git gets no
  real credential and fails cleanly.

## 4. Staging allowlist — independently challenged

- **Fail-closed empty allowlist.** `ALLOWLIST` default empty (main.py:83-87); with no changes and an
  empty allowlist `stage_allowlisted` returns `[]`. Note: with any changed/untracked path present and
  an empty allowlist, `stage_allowlisted` raises (main.py:311-316) and the cycle exits non-zero —
  correct fail-closed behavior, exercised by `test_autopush_default_allowlist_stages_nothing`.
- **Exact path validation + traversal.** `_path_is_allowed` (main.py:252-274) rejects absolute
  paths, `..`, `\\`-prefixed paths, deny segments/basenames/suffixes/substrings, and requires exact
  allowlist membership. Probe of 31 attack inputs passed (traversal, `/etc/passwd`, `.env`,
  `requirements*.txt`, `.gitignore`, `id_rsa`, `.log/.pyc/.sqlite3/.pem/.key`, `tools/*`, `docs/*`,
  `secret*`/`token*`/`credential*`/`backup*`).
- **Pre-staged unrelated/forbidden files.** Two independent layers:
  1. `_porcelain_paths` scans the whole worktree (`--untracked-files=all`) and any disallowed path
     aborts before `git add` (main.py:308-316).
  2. After `git add`, `_staged_paths` re-reads the index and rejects any disallowed staged entry
     (main.py:323-329).
  **Adversarial probe (Experiment 8):** a forbidden file pre-staged in the index *after* the status
  scan (simulated race) is caught by the post-stage verification (raised
  `staged path verification failed ... .env`). Layer 2 is therefore load-bearing and works.
- **Backup / secret / DB / log / requirements excluded.** Confirmed by probes and
  `test_backup_path_is_rejected_even_if_allowlisted`, `test_env_and_database_files_are_rejected`,
  `test_log_and_generated_files_are_rejected`, `test_requirements_txt_is_rejected`.
- **No broad staging.** Only `git add -- <paths>` is issued (main.py:321); no `-A`/`.` anywhere
  (`test_no_broad_staging_command_is_ever_issued`).

## 5. Git execution — independently challenged

- **Branch restriction.** `run_cycle` aborts before any commit/push when the current branch !=
  `BRANCH` (main.py:384-386). Probe (Experiment 6): `AutopushError: on branch 'feature-branch',
  expected 'main'`; only `rev-parse` was invoked.
- **Push target.** `git push origin HEAD:main` (main.py:396); push by remote name, no URL/credential.
- **Push failure.** Surfaces as `AutopushError` with sanitized text; canary absent (Experiment 7).
- **Race between validation and execution.** The index is re-verified immediately before commit
  (Experiment 8). No transaction spans the scan→add→verify→commit→push sequence, but each step is
  fail-closed; a concurrent index mutation is detected at the verify step.
- **No automation activation.** `main()` (main.py:401-425) runs `--once` or `--daemon` only when
  invoked directly; importing the module has no side effects (`test_module_has_no_import_time_side_effects`).
  No autopush process, crontab, or systemd unit is active; `automations/` is absent (gitignored).

## 6. Findings (classified)

### CRITICAL / HIGH
None.

### MEDIUM
None.

### LOW
- **L-1 — Latent plaintext credential leak via `REPO_URL` in an unredacted print.**
  `automation/autopush/main.py:253` — `print(f"Cloning {REPO_URL} -> {REPO_DIR}")` does **not** pass
  through `redact()`. If an operator sets `AUTOPUSH_REPO_URL` to a URL containing embedded userinfo
  (e.g. `https://x-access-token:<TOKEN>@github.com/o/r.git`), the token is printed in plaintext.
  **Reproducible (Experiment 14):** with `REPO_URL="https://x-access-token:SYNTH_CANARY_TOKEN_LEAK@github.com/o/r.git"`
  and `REPO_DIR` absent, stdout was
  `Cloning https://x-access-token:SYNTH_CANARY_TOKEN_LEAK@github.com/o/r.git -> ...`.
  Note the argv passed to `git clone` is sanitized to the bare URL, so the leak is confined to this
  one print. Reachability requires the operator to embed a credential in `AUTOPUSH_REPO_URL`, which
  contradicts the documented configuration (README:38 shows a bare URL; README:19-22 claims the token
  is "never placed in a remote URL" and is "scrubbed from every log line"). **Blocks publication: NO**
  (unreachable under documented config; the default and documented value is credential-free), but it
  contradicts the README's absolute claim and should be fixed (route through `redact()`, or reject
  userinfo in `REPO_URL`).
- **L-2 — "never placed in a remote URL" is not enforced against operator input.**
  `automation/autopush/main.py:54` reads `AUTOPUSH_REPO_URL` verbatim. The script does not reject a
  URL that already contains userinfo; it only strips credentials from *argv* when the token is
  known. Same root as L-1. **Blocks publication: NO.**
- **L-3 — Documentation overstates the "remote URL" guarantee.**
  `automation/autopush/README.md:19-22` states the token is "never placed in a remote URL … and it is
  scrubbed from every log line." True for the script's own credential path, but (a) line 253 prints
  `REPO_URL` unredacted and (b) an operator-supplied `REPO_URL` can itself carry a credential that is
  then used as the remote URL (main.py:255/257). The claim should be scoped to "the token the script
  resolves". **Blocks publication: NO.**
- **L-4 — Symlink named as an allowlisted path.**
  `_path_is_allowed` (main.py:252-274) validates the path string, not the filesystem object.
  **Reproducible (Experiment 2):** with `link.txt` allowlisted and `link.txt` a symlink to
  `/etc/passwd`, `stage_allowlisted()` staged it and the index blob recorded the symlink target
  (`/etc/passwd`). git stores a symlink as the target path (no target contents leaked), so impact is
  low, but a symlinked allowlisted path could publish a link pointing outside the repo. **Blocks
  publication: NO** (requires an operator to allowlist a path that is a symlink). Documented as a
  residual in the 28B report §12.

### INFORMATIONAL
- **I-1 — Broad substring deny-list can over-block.** `_DENY_SUBSTRINGS` (main.py:102) rejects any
  path containing `token`, `secret`, `credential`, `backup`; `_DENY_SEGMENTS` includes `docs` and
  `tools`. Legitimate allowlisted paths (e.g. `src/tokenizer.py`) are rejected. Fail-closed, so this
  is safe, but it may surprise operators. No security impact.
- **I-2 — Absolute-path allowlist entries are unusable.** Because `norm in ALLOWLIST` is compared
  against the normalized relative form (main.py:274), an absolute or `./`-prefixed allowlist entry
  does not match a normalized git path; e.g. allowlisting `./allowed.txt` did not match the status
  path `allowed.txt` (probe). Safe (fail-closed), minor usability.
- **I-3 — Case sensitivity.** `_path_is_allowed` lowercases for deny checks but compares the
  allowlist case-sensitively; a case-only mismatch over-blocks. Safe.
- **I-4 — Rename/copy parsing.** `_porcelain_paths` (main.py:277-297) drops the second (origin) path
  of a rename, so a rename of a non-allowlisted path to an allowlisted path is evaluated only on the
  new path (probe: `R  renamed.txt` → `[('R ', 'renamed.txt')]`). The new path still must pass the
  allowlist, so no forbidden path is staged. Safe.
- **I-5 — `redact()` does not scrub the placeholder.** `redact("token is unset-no-token")` is
  unchanged (main.py:169). The placeholder is not a secret; harmless.
- **I-6 — Short-token over-scrub.** `_sanitize_args` uses a substring test; a 1-char token would
  match many args and raise. Tokens are long in practice; fail-closed.

## 7. Adversarial scenario matrix (all safe / no real push)

| Scenario | Result |
|---|---|
| Empty allowlist | Fail-closed (raises when changed paths exist; stages nothing when clean) |
| Path traversal / absolute / `\\` | Rejected |
| Symlink alias | Staged as a link (L-4); no target contents leaked |
| Pre-staged forbidden file | Rejected by post-stage index verification (Experiment 8) |
| Unexpected untracked file | Rejected |
| Credential in argv | Stripped (URL) / refused (non-URL) |
| Credential in exceptions/stdout/stderr/callback | Redacted |
| Malformed credential-helper output | git parses line-oriented; no shell eval of the token (Experiment 9) |
| Unexpected branch | Aborts before commit/push (Experiment 6) |
| Remote with embedded credential | Sanitized in argv; unredacted `REPO_URL` print (L-1) |
| Git subprocess failure / partial failure | `AutopushError`, sanitized; partial index not committed (Experiment 7) |
| Concurrent index mutation during validation | Caught by post-stage verification (Experiment 8) |

## 8. Tests — quality assessment

- `tests/test_autopush_security.py` (25) and `tests/test_autopush_automation.py` (4) both pass, 5×
  repeatable. Assertions are meaningful (exact argv assertions, real local-repo `.git/config`
  inspection, capture of stdout/stderr/callback). No vacuous assertions found in the credential or
  staging suites.
- **Coverage gap (ties to L-1):** no test asserts that a credential embedded in `AUTOPUSH_REPO_URL`
  is absent from the clone **log line**. The suite sanitizes argv but not the `print` at main.py:253.
- **Test-side minor:** `test_no_broad_staging_command_is_ever_issued` uses a slightly convoluted
  assertion; it still correctly rejects `git add -A`/`git add .`. Not a defect.

## 9. Documentation vs implementation

- README configuration table (lines 33-43) matches the code env vars and defaults.
- README run modes (lines 24-31) match `main()` (`--once`/`--daemon`).
- README staging description (lines 11-14) matches `stage_allowlisted` (allowlist-only, fail-closed,
  no `-A`/`.`).
- **Mismatch (L-3):** the credential claims (lines 19-22) are stronger than the implementation
  guarantees for operator-supplied `REPO_URL` and for the unredacted `print` at main.py:253.
- README deployment snippet (lines 47-58) references `automations/…` in `docs/AUTOMATIONS.md`, but no
  `automations/` tree exists here (gitignored); the snippet itself performs no action and is
  informational.

## 10. Publication recommendation

- 28B is **safe to publish** as an inactive/disabled automation hardening: no CRITICAL/HIGH/MEDIUM
  findings, credentials are handled correctly on the script's own path, staging is fail-closed with
  an independently verified second index check, and the module has no import-time side effects.
- **Notes to carry (non-blocking):** L-1/L-2/L-3 (route `REPO_URL` through `redact()` and/or reject
  userinfo; scope the README claim), L-4 (symlink residual, already documented). None is reachable
  under the documented configuration.
- This is a **fresh-context independent review** performed by a separate reviewer; unlike the 28B
  implementation report (which recorded `INDEPENDENT_REVIEW = NOT_AVAILABLE`), this review is
  independent.

**Overall verdict: PASS_WITH_NOTES.** 28B is recommended for publication, with the L-1/L-3
documentation/redaction note tracked as a follow-up.

STOP — no fixes, no publication, no 28E. Awaiting separate authorization.
