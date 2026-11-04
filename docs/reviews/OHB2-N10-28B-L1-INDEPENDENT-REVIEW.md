# OHB2-N10-28B-L1 — INDEPENDENT REVIEW (fresh-context, read-only)

Reviewer: fresh-context independent reviewer; not the author of 28B-L1. All actions read-only.
No fixes or file modifications. No staging, commits, pushes, fetches, pulls, PRs, merges, or
deployment. Autopush was **not** executed as a workflow and no automation was activated. Only
synthetic credentials were used; no real credentials and no external Git operations. No backup
files, `requirements.txt`, or activation settings touched. Temporary probe scripts were created
under `/tmp` and removed.

Verdict: **PASS_WITH_NOTES** — L-1/L-2/L-3 are correctly resolved with no regression to the
existing 28B protections. No CRITICAL/HIGH/MEDIUM findings. Two LOW cosmetic notes (over-blocking
edge cases) and one INFO documentation nuance. 28B is ready for publication.

---

## 1. Repository state

- HEAD = `6021658cf3c1664ed0eadeaed2acee4e86721b6b` (matches expected).
- Branch = `release/ohb2-20261101`. Index empty. Stash empty. Nothing committed/pushed.
- 28B-L1 scope: `automation/autopush/main.py` (M), `automation/autopush/README.md` (M),
  `tests/test_autopush_security.py` (untracked, 33 tests), `docs/reviews/OHB2-N10-28B-L1-REPORT.md`
  (untracked). Target report `docs/reviews/OHB2-N10-28B-L1-INDEPENDENT-REVIEW.md` was absent before
  creation. No autopush process running.

## 2. Exact commands, exit codes, counts, warnings

| # | Command | Result | Exit |
|---|---|---|---|
| 1 | `.venv/bin/python -m pytest tests/test_autopush_security.py tests/test_autopush_automation.py -q` | **37 passed** (33 security + 4 automation) | 0 |
| 2 | same, security file repeated ×5 | 33 passed each | 0 |
| 3 | `.venv/bin/python -m pytest -q` (full) | **1521 passed, 71 warnings** (51.55s) | 0 |
| 4 | `.venv/bin/python -m pyflakes bot/ main.py tests/ automation/autopush/main.py` | clean | 0 |
| 5 | `.venv/bin/python -m compileall -q automation/autopush/` | COMPILE_OK | 0 |
| 6 | `node --test tests/frontend/*.test.js` | 134 pass / 0 fail | 0 |

Warnings are pre-existing deprecation warnings; none new. Counts match the L-1 report (37 focused,
1521 full).

## 3. Verification against the review checklist

**1. HTTPS credential-bearing URLs are rejected safely — PASS.** `_url_embeds_credentials`
(main.py:61-78) flags `user:pass@` and bare `user@` on http(s). `_resolve_repo_url` (main.py:93-105)
raises `AutopushError` with a fixed, credential-free message; error text contains neither the
canary nor the username (probe 3, test `test_url_validation_error_never_exposes_credentials`).

**2. SSH and scp-style URLs remain supported — PASS.** `git@github.com:o/r.git`,
`ssh://git@github.com/o/r.git`, `ssh://git@github.com:22/o/r.git`, and
`git+ssh://git@github.com/o/r.git` are accepted (probe 1; `test_normal_ssh_urls_are_accepted`).
Only a bare `user@` on ssh is tolerated (conventional `git@` username); ssh `user:pass@` is still
rejected.

**3. Parsing bypasses — PASS (fail-closed).** Probe 1 (27 inputs): uppercase/mixed-case schemes,
empty password (`user:@`), `@` inside password, percent-encoded userinfo, multiple `@`,
IPv6 userinfo, and non-default ports are all correctly classified. No bypass found: every
credential-bearing form is rejected. Two inputs are *over-blocked* (safe direction), see L1-1/L1-2.

**4. Import-time validation cannot expose credentials — PASS.** With a clean URL, import succeeds
(`REPO_URL` = default). With a credential URL, `python3 main.py --once` exits **1**; the canary and
username are absent from stdout and stderr (probe 4b). No subprocess is spawned at import
(`SUBPROC_CALLS_ON_IMPORT 0`, probe 4c).

**5. Logs/exceptions/stdout/stderr/clone diagnostics never expose userinfo — PASS.** The clone
diagnostic prints `_safe_url(REPO_URL)`; the clone argv and `remote set-url` argv use the bare URL
with no canary (probe 5). `git()` routes stdout/stderr and exception text through `redact()`
(main.py:277/279/283).

**6. `_safe_url` preserves legitimate info — PASS.** Host, port, and path are preserved
(`https://x-access-token:…@github.com:8443/TM-AEM/OpenHandBot.git` → `https://github.com:8443/TM-AEM/OpenHandBot.git`);
`@` in a path is left intact (probe 2). One cosmetic nuance for `ssh://git@` (L1-2).

**7. README matches implementation — PASS.** The README now (a) scopes the credential claim to "the
token the script resolves", (b) states `AUTOPUSH_REPO_URL` must not embed credentials and is refused
at startup, and (c) states displayed URLs are stripped and HTTPS/SSH URLs are supported. All three
match the code. See L1-3 for a minor wording nuance.

**8. No regression — PASS.** Credential helper (`_CRED_HELPER`, `_child_env`), argv sanitizer
(`_sanitize_args`), environment minimization (`_GIT_ENV_KEYS`), and the two-layer fail-closed
staging allowlist are unchanged by L-1 and still pass their tests.

**9. Tests meaningfully cover the behavior — PASS.** 8 new tests cover user:pass, token userinfo,
bare-user https, normal https, three SSH forms, error-text non-exposure, displayed-URL stripping
(via captured stdout/stderr), and `_safe_url`. Assertions are specific (exact strings, canary
absence), not vacuous.

## 4. Import-time validation safety (specific ask)

- **No unsafe import behavior.** Module import runs only pure string validation and reads env vars;
  it does not spawn processes, open sockets, or mutate state (probe 4c). The `AutopushError` raised
  on a bad URL is raised at import, which surfaces as a clean non-zero exit with a generic message
  (probe 4b).
- **No legitimate configuration broken.** Default, plain HTTPS, and SSH/scp forms import cleanly
  (probes 4a, 1). The only configs refused are those that embed credentials — exactly the intent.
- **Worst case** of an import-time failure is the automation aborting with a clear, secret-free
  error; there is no partial-init or credential-exposure risk.

## 5. Findings

### CRITICAL / HIGH / MEDIUM
None.

### LOW
- **L1-1 — Over-block: fragment `@` treated as userinfo.** `_url_embeds_credentials` inspects the
  authority as `rest.split("/",1)[0].split("?",1)[0]` and does not stop at `#`, so
  `https://host#frag@x` is treated as credential-bearing (probe 1). This is **fail-closed** (an
  unusual, non-credential URL is refused rather than a credential URL accepted); `#` is illegal in a
  git remote URL. No security impact. File/line: `automation/autopush/main.py:72`.
- **L1-2 — Cosmetic: `_safe_url` drops the SSH username.** For an explicit-scheme SSH URL,
  `_safe_url("ssh://git@github.com:22/o/r.git")` returns `ssh://github.com:22/o/r.git` (the `git@`
  username is stripped). This is display-only (the actual clone uses the real `REPO_URL`, probe 5),
  and SSH cannot be validated at startup to distinguish `git@` from a credential, so preserving it
  is not safe in general. No security impact. File/line: `automation/autopush/main.py:81-90`.

### INFORMATIONAL
- **L1-3 — README nuance.** The README states a userinfo URL is "refused at startup". This is exact
  when the script is the entrypoint (as configured: `python3 main.py`). On plain `import` the
  refusal occurs at module import (which is startup); the `except Exception` handler in `main()` is
  not reached, so the message is the raw `AutopushError` traceback (still secret-free). Accurate in
  effect; wording could note "at import/startup". File: `automation/autopush/README.md:25-29`.
- **INFO — Import-time hard failure for an embed-credential misconfiguration.** Setting
  `AUTOPUSH_REPO_URL` with userinfo makes import raise `AutopushError`, so the module cannot be
  imported at all (e.g. by a test harness). This is the intended fail-closed behavior; the config
  already advertises credential-free URLs. Not a defect.

### Resolved from the prior review
- **L-1 (unredacted `REPO_URL` print) — RESOLVED.** `ensure_repo` prints `_safe_url(REPO_URL)`
  (main.py:304); probe 5 confirms no canary in stdout/stderr.
- **L-2 (userinfo not enforced) — RESOLVED.** `REPO_URL` is built via `_resolve_repo_url` at
  import (main.py:109); credential URLs are refused.
- **L-3 (README overstates guarantee) — RESOLVED.** Claims scoped to verified behavior.

## 6. Regression check of prior 28B protections

| Protection | Status |
|---|---|
| Credential helper (env-injected, no URL/argv/config/temp) | Intact |
| argv sanitizer (`_sanitize_args`) | Intact (unchanged) |
| Environment minimization (`_GIT_ENV_KEYS`) | Intact |
| Staging allowlist, fail-closed + post-stage index verify | Intact (tests pass) |
| Branch restriction / push by remote name | Intact |

## 7. Publication recommendation

- **28B (with L-1/L-2/L-3 fixes) is ready for publication.** No CRITICAL/HIGH/MEDIUM findings; the
  credential-URL surface is now fail-closed and redacted, with no regression to the existing
  credential/staging protections.
- Carry L1-1/L1-2/L1-3 as optional, non-blocking cleanups (all fail-closed or cosmetic).

**Overall verdict: PASS_WITH_NOTES.**

STOP — no fixes, no publication, no 28E. Awaiting separate authorization.
