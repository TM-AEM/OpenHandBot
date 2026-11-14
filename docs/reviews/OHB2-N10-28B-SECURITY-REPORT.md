# OHB2-N10-28B — Autopush Security Hardening Report

Mission: OHB2-N10-28A (baseline revalidation) + OHB2-N10-28B (Autopush security hardening).
This report is local and untracked. Nothing was committed, staged, pushed, or executed.

## 1. Baseline identity and SHA

| Item | Value |
| --- | --- |
| Repository | `TM-AEM/OpenHandBot` (`origin` = `https://github.com/TM-AEM/OpenHandBot.git`) |
| Branch | `release/ohb2-20261101` |
| Local HEAD | `6021658cf3c1664ed0eadeaed2acee4e86721b6b` |
| `origin/main` (cached) | `6021658cf3c1664ed0eadeaed2acee4e86721b6b` |
| Baseline expected | `6021658cf3c1664ed0eadeaed2acee4e86721b6b` |
| Match | YES (local HEAD == origin/main == expected) |

Parent chain: `6021658` → `e76427a` (Sync automations from agent server) → `8ca61e2` → `7b959f5` → …

## 2. Initial worktree state

```
 M requirements.txt                    (pre-existing, local-only: paramiko backup dep)
?? bot/backup_lifecycle.py             (local-only backup)
?? docs/reviews/ ...                    (untracked reports)
?? tests/test_autopush_automation.py   (local-only autopush integration test)
?? tools/ ...                           (local-only backup)
   ... (backup tests, fake servers, backup docs)
```
Nothing staged. No `.env`, no database, no Autopush process running.

## 3. Protected local work — preservation evidence

SHA-256 (first 16) recorded before and after the task; all unchanged:

| File | sha256[0:16] |
| --- | --- |
| requirements.txt | 845c1fee6bdd321f |
| tools/__init__.py | 0bc1daf73cac04b7 |
| tools/backup_sqlite.py | 383e22e89254ca0d |
| tools/backup_scheduler.py | e386f7e112d4c488 |
| tools/backup_destination.py | f9279abdf64edfe3 |
| tools/backup_gdrive.py | b88463c2c41c00ea |
| bot/backup_lifecycle.py | 595a23a0e1b99496 |
| docs/BACKUP_OPERATIONS.md | 596f373b5dc63397 |
| docs/GOOGLE_DRIVE_BACKUP_SETUP.md | 36a4104aa1b3632a |
| tests/test_backup_sqlite.py | 5444b83be9b780f6 |
| tests/test_restart_recovery.py | 23eeec7c625b454e |

`requirements.txt` remains the single tracked modification and still contains only the
local `paramiko==3.5.1` line. No protected file was modified, moved, deleted, staged,
or published.

## 4. Findings — confirmed / rejected (against current source)

| # | Finding | Status |
| --- | --- | --- |
| F1 | Token embedded in authenticated remote URL (`authed_url`) and passed to `git clone`/`git push` as an argument → visible in argv (`/proc/<pid>/cmdline`) and transiently in the URL. | **CONFIRMED** → fixed |
| F2 | Broad staging via `git add -A` in `commit_all()` publishes arbitrary working-tree content (secrets, DBs, logs, backup files). | **CONFIRMED** → fixed |
| F3 | No allowlist / no protection against staging unrelated or sensitive files. | **CONFIRMED** → fixed |
| F4 | Exceptions interpolated raw `args`; callback/`main` printed raw `str(exc)`; `redact()` covered only `_token_cache`. | **CONFIRMED** → hardened |
| F5 | `git()` passed the full `os.environ` to the child (unnecessary secret exposure surface). | **CONFIRMED** → minimal env allowlist |
| F6 | `.git/config` credential persistence | **REJECTED** (already avoided; `remote set-url` reset). Kept belt-and-braces. |

## 5. Files modified and why

| File | Change |
| --- | --- |
| `automation/autopush/main.py` | Credential transport → env credential helper; argv sanitizer; fail-closed allowlist staging; staged-index verification; minimal child env; redaction on all diagnostics; `AutopushError`. |
| `automation/autopush/README.md` | Documents the new credential model and fail-closed staging (`AUTOPUSH_ALLOWLIST`). |
| `tests/test_autopush_security.py` | New (local, untracked): 25 security regression tests. |
| `tests/test_autopush_automation.py` | Updated (local, untracked): supplies allowlist; adds 2 fail-closed cases. |

`requirements.txt` was **not** modified by this task (its paramiko delta is pre-existing).

## 6. Credential flow — before vs after

**Before:** `authed_url()` produced `https://x-access-token:<TOKEN>@host/...` and it was
passed as a `git clone`/`git push` argument → the token appeared in subprocess argv and
in the remote URL, and redaction covered only the cached token.

**After:** authentication is supplied by an ephemeral git credential helper injected via
the child environment (`GIT_CONFIG_COUNT/KEY_0/VALUE_0` + `GITHUB_TOKEN`). The token is
never in a URL, argv, `.git/config`, or a temp file. `_sanitize_args()` strips userinfo
from URL arguments and refuses any other token-bearing argument. All printed/reported text
passes through `redact()` (cached token + `GITHUB_TOKEN`). TLS verification is unchanged.

Verified with a synthetic canary (no real credential):
* helper supplies `password=<token>` to `git credential fill` when a token is present (rc 0);
* with an empty token the helper exits non-zero (rc 128), so git fails cleanly with no
  credential and no bogus value.

## 7. Staging policy — before vs after

**Before:** `git add -A` staged everything.

**After (fail closed):**
1. `git status --porcelain -z --untracked-files=all` enumerates changed paths.
2. Each path is checked by `_path_is_allowed()`: must be repo-relative, no `..`, not
   absolute, not in deny segments (`tools`, `.git`, `.venv`, `__pycache__`, `docs`, …),
   not a deny basename (`.env`, `requirements*.txt`, `.gitignore`, keys), not a deny
   suffix (`.env`, `.sqlite*`, `.db*`, `.log`, `.pyc`, `.pem`, `.key`, …), not containing
   `backup`/`secret`/`credential`/`token`, **and** exactly present in `AUTOPUSH_ALLOWLIST`.
3. If any changed path is not allowed → `AutopushError` before any `git add`.
4. Only approved paths are staged via `git add -- <paths>` (no `-A`, no `.`).
5. The index is re-verified (`git diff --cached --name-only`) against the allowlist;
   any unexpected staged path aborts.
6. Empty allowlist (default) ⇒ stage nothing.

## 8. Security regression tests and results

File: `tests/test_autopush_security.py` — **25 passed**. Covers all required scenarios:
credential not in URL / argv / exception / logs / callback / `.git/config`; failed
credential op does not expose the secret; missing credential fails safe; approved path
accepted; unapproved modified/untracked path rejected; backup path rejected even if
allowlisted; `.env`/DB rejected; log/generated rejected; `requirements.txt` rejected;
traversal rejected; unexpected path fails closed; no broad staging command issued;
staged-path verification rejects an unexpected file; failed validation prevents later
publication; no import-time side effects; no real GitHub write; no Telegram/callback when
unconfigured; push uses remote name (not URL). A fake runner records the exact argv and
env for every simulated subprocess; a synthetic canary
(`SYNTHETIC_GITHUB_TOKEN_CANARY_DO_NOT_USE`) is used throughout — no real credential.

`tests/test_autopush_automation.py` — 4 passed (2 existing adapted to the allowlist + 2
new fail-closed integration cases against local bare repos only).

## 9. Full test commands and exit codes

| Command | Result | Exit |
| --- | --- | --- |
| `.venv/bin/python -m pytest tests/test_autopush_security.py tests/test_autopush_automation.py -q` | 29 passed | 0 |
| `.venv/bin/python -m pytest -q` (full suite) | **1475 passed**, 71 warnings | 0 |

Warnings are pre-existing PTB deprecation warnings; no network access was attempted.

## 10. Static analysis

* `pyflakes bot/ main.py automation/autopush/main.py tests/test_autopush_security.py tests/test_autopush_automation.py` → clean.
* `py_compile` on modified files → OK.
* AST import closure of `main.py` → 5 modules, **no** `tools`/backup modules.
* Autopush source scan: no `shell=True`, no `os.system`, no `git add -A`/`.`, no token in
  URL/argv construction; the only `x-access-token` literal is inside the credential
  helper that reads `$GITHUB_TOKEN` from the child environment.

## 11. Independent reviewer identity/method

**NOT_AVAILABLE.** A genuinely independent fresh-context LLM review could not be obtained
within the authorized scope (§1.1 does not authorize starting real OpenHands operations,
and no independent reviewer was provided). A separate shell process is not an independent
LLM review, so it is not claimed. A documented self-adversarial pass was performed instead
and its results are in §12; independent approval is **not** claimed.

## 12. Self-adversarial pass (not an independent review)

* Token→argv: `_sanitize_args` covers all `git()` calls; token-bearing URL args are
  stripped, other token-bearing args are refused. ✔
* Token→`.git/config`: no credential-bearing URL is passed; helper is env-only. ✔
* Redaction bypass: covers cached token and `GITHUB_TOKEN` env. ✔
* Allowlist bypass: rejects `..`, absolute paths, deny segments/basenames/suffixes and
  substring matches; requires exact allowlist membership. Residual: a symlink named as an
  allowlisted path is staged by path (git does not follow for staging) — low risk.
* Index pre-population: `commit_all` re-verifies the staged index and fails closed on any
  unexpected entry. ✔
* Push scope: Autopush pushes the branch HEAD; it only *creates* commits from allowlisted
  staged paths, but a branch already containing unrelated commits would carry them. This
  is inherent to branch push and is documented as a residual risk.

## 13. Remaining risks and limitations

1. The tracked `automation/autopush/` script still exists on `main`; this task makes it
   safe *if* ever explicitly authorized, but does not activate it.
2. Branch-push scope (see §12) is not fully preventable at the script level.
3. In-memory rate limiting and other core-app concerns are out of scope for this task.

## 14. Explicit statements

* **No real credential was used.** Only the synthetic canary value was used.
* **Autopush was never executed.** No daemon, scheduler, or cycle was started; no
  `run.sh`/`main.py` invocation occurred outside the isolated unit tests that use local
  bare repos and injected fake runners.
* No commit, push, PR, merge, tag, deploy, Telegram message, OpenHands production
  operation, or backup job occurred. No file was staged.
