# OHB2-N10-28B-L1 — REPORT

Title: Close Autopush Credential-URL Redaction and Documentation Findings (L-1, L-2, L-3).
Type: implementation + adversarial self-review (this is **not** an independent review).
Repository: TM-AEM/OpenHandBot. Branch: `release/ohb2-20261101`. HEAD: `6021658cf3c1664ed0eadeaed2acee4e86721b6b`.

## 1. Baseline audit (before edits)

- HEAD = `6021658cf3c1664ed0eadeaed2acee4e86721b6b`; branch `release/ohb2-20261101`.
- Index empty; stash empty; all prior worktree/untracked changes preserved.
- `docs/reviews/OHB2-N10-28B-L1-REPORT.md` absent before creation.

## 2. Exact changed files

| File | Change |
|---|---|
| `automation/autopush/main.py` | URL userinfo validation + redacted display + docs |
| `automation/autopush/README.md` | Corrected/scoped security claims |
| `tests/test_autopush_security.py` | +8 focused tests (synthetic URLs only) |
| `docs/reviews/OHB2-N10-28B-L1-REPORT.md` | this report (new) |

No other file modified. No staging/commit/push/PR/merge/fetch/pull/deploy. Autopush was not
executed as a workflow and no automation was activated. No real credentials used. Backup files and
`requirements.txt` untouched.

## 3. Implementation

### `automation/autopush/main.py`
- **`_url_embeds_credentials(url)`** — fail-closed detection of userinfo:
  - `user:secret@host` → credential-bearing (always rejected).
  - bare `user@host` on `http`/`https` → rejected (a bare token is credential-bearing there).
  - bare `user@host` on `ssh`/`git+ssh` → accepted (conventional `git@host` username).
  - scp-like `git@host:path` (no `://`) → accepted.
  - Only the authority is inspected; `@` in a path/query is not treated as userinfo.
- **`_resolve_repo_url(raw)`** — raises `AutopushError` with a fixed, credential-free message when
  userinfo is present; otherwise returns the URL unchanged. `REPO_URL` is now built via
  `_resolve_repo_url(...)` at import time, so a credential-bearing URL is refused at startup.
- **`_safe_url(url)`** — display-safe form; strips only the authority userinfo, preserving scheme,
  host, port and path. Used by the clone log line.
- **`ensure_repo`** — `print(f"Cloning {_safe_url(REPO_URL)} -> {REPO_DIR}")` (was unredacted
  `REPO_URL`). This closes L-1: no displayed/logged repository URL can carry userinfo.
- Moved `AutopushError` above the module-level `REPO_URL` assignment (single definition; no
  duplicate class).
- Docstring/security-model updated to state URL validation and display stripping.

### `automation/autopush/README.md`
- Scoped the credential claim to "the token the script resolves" and to `.git/config`/argv/temp
  files (precise, verified guarantees).
- Added an explicit statement: `AUTOPUSH_REPO_URL` must not embed credentials; a userinfo URL is
  refused at startup; displayed URLs are stripped; legitimate HTTPS and SSH URLs are supported.
- Config table row updated to note "must not embed credentials".

## 4. Tests added (synthetic URLs only)

In `tests/test_autopush_security.py`:
1. `test_https_url_with_user_and_password_is_rejected`
2. `test_https_url_with_token_userinfo_is_rejected`
3. `test_bare_user_https_url_is_rejected`
4. `test_normal_https_url_is_accepted`
5. `test_normal_ssh_urls_are_accepted` (scp-like + `ssh://` + `ssh://…:22`)
6. `test_url_validation_error_never_exposes_credentials`
7. `test_displayed_repo_url_is_stripped_of_userinfo` (captures stdout/stderr; asserts no canary)
8. `test_safe_url_helper_strips_userinfo`

## 5. Exact commands, exit codes, counts, warnings

| Command | Result | Exit |
|---|---|---|
| `.venv/bin/python -m pytest tests/test_autopush_security.py tests/test_autopush_automation.py -q` | **37 passed** (33 security + 4 automation) | 0 |
| same, security file repeated ×5 | 33 passed each | 0 |
| `.venv/bin/python -m pytest -q` (full) | **1521 passed, 71 warnings** (49.19s) | 0 |
| `.venv/bin/python -m pyflakes bot/ main.py tests/ automation/autopush/main.py` | clean | 0 |
| `.venv/bin/python -m compileall -q bot/ main.py tests/ automation/autopush/` | COMPILE_OK | 0 |
| `node --test tests/frontend/*.test.js` | 134 pass / 0 fail | 0 |

Warnings are pre-existing deprecation warnings; none new. Full-suite count rose 1513 → 1521 (+8).

## 6. Adversarial self-review (not independent)

Probes run with synthetic canary only; no network, no real credential, no external git:

- **Bypass matrix (15 URLs)** all matched expectations: `user:pass@`, bare `user@` on https,
  uppercase `HTTPS://`, empty password `user:@`, `@` inside password, `@` only in path, `@` only in
  query, and the accepted HTTPS/SSH/scp-like forms.
- **Error text**: `_resolve_repo_url` messages contain neither the canary nor the username.
- **Import-time guard**: running `python3 main.py --once` with a canary-bearing `AUTOPUSH_REPO_URL`
  exits **1** with the generic message; canary absent from stdout and stderr.
- **Display path**: `ensure_repo()` prints `https://host/x.git` (userinfo stripped); clone argv is
  the bare URL; canary absent from output.
- **`_safe_url`**: strips authority userinfo only; `@`-in-path is preserved (no misleading display).

Residual (documented, out of scope): a URL with userinfo that is somehow passed directly to
`git(...)` bypassing module init would still be sanitized by `_sanitize_args` for the resolved token,
and `_safe_url` strips any userinfo at display. Symlink policy (L-4) and allowlist informational
items were intentionally not touched.

## 7. Finding status

| Finding | Status | Evidence |
|---|---|---|
| **L-1** (unredacted `REPO_URL` print) | **RESOLVED** | `_safe_url` at the clone print; test 7 + probe C/D |
| **L-2** (userinfo not enforced against operator input) | **RESOLVED** | `_resolve_repo_url` refuses userinfo at startup; tests 1–3, 6 + probe C |
| **L-3** (README overstates guarantee) | **RESOLVED** | README claims scoped to verified guarantees; new URL paragraph |

Remaining findings: none for L-1/L-2/L-3. L-4 and INFO items from the 28B review remain open by
design (out of scope for this task).

## 8. Safety / state

- No Git publication: no staging, commit, push, PR, merge, fetch, pull, or deployment.
- Autopush remains disabled/inactive (no process, no cron, no activation performed).
- All pre-existing worktree and untracked changes preserved.
- HEAD unchanged (`6021658c…`); index and stash empty.

STOP — awaiting separate authorization.
