# REV-01 Reconstruction Verification

## Base identity

| Item | Value |
|---|---|
| Base commit | `7cb9d7a0b37feac986e21622bfadd69a4baec978` |
| Base tree | `2ccdb866dce467dad55d3d83f0f757324d00409b` |
| Source branch | `main` |
| Source HEAD at packaging | `7cb9d7a0b37feac986e21622bfadd69a4baec978` |
| Candidate state | uncommitted in source workspace |

The source workspace `git status --short` at packaging time was:

```text
 M bot/file_browser.py
 M bot/handlers.py
 M tests/test_bot_file_browser.py
 M tests/test_file_browser.py
?? docs/audits/OHB2-REV-01-STALE-BROWSER-SNAPSHOT-INVALIDATION-REPORT.md
```

No unrelated tracked or untracked changes were present. Ignored `.openhands/`, `.pytest_cache/`, and
`__pycache__/` content was not part of the candidate.

## Patch construction

A temporary clone was created from the source workspace at the exact base, candidate files were copied
into it, and the patch was generated there. The source workspace was not modified to build the patch.

```sh
git clone --no-hardlinks /workspace/project/OpenHandBot <build>/candidate
git -C <build>/candidate checkout --detach 7cb9d7a0b37feac986e21622bfadd69a4baec978
cp -p bot/file_browser.py <build>/candidate/bot/file_browser.py
cp -p bot/handlers.py <build>/candidate/bot/handlers.py
cp -p tests/test_bot_file_browser.py <build>/candidate/tests/test_bot_file_browser.py
cp -p tests/test_file_browser.py <build>/candidate/tests/test_file_browser.py
cp -p docs/audits/OHB2-REV-01-STALE-BROWSER-SNAPSHOT-INVALIDATION-REPORT.md \
  <build>/candidate/docs/audits/OHB2-REV-01-STALE-BROWSER-SNAPSHOT-INVALIDATION-REPORT.md
git -C <build>/candidate add -N \
  docs/audits/OHB2-REV-01-STALE-BROWSER-SNAPSHOT-INVALIDATION-REPORT.md
git -C <build>/candidate diff --binary > REV-01-candidate.patch
```

Generated patch:

- Size: **22,511 bytes**
- Lines: **511**
- SHA-256: `c9071f7141fb46f0693d9fcb0791c12ef7726ef58198be078622d3e14b12d1a1`

The patch contains exactly these five files:

```text
bot/file_browser.py
bot/handlers.py
docs/audits/OHB2-REV-01-STALE-BROWSER-SNAPSHOT-INVALIDATION-REPORT.md
tests/test_bot_file_browser.py
tests/test_file_browser.py
```

## Independent reconstruction

A second temporary clone was created from the source workspace, checked out at the exact base, and the
packaged patch was applied.

```sh
git clone --no-hardlinks /workspace/project/OpenHandBot <verify>/repo
git -C <verify>/repo checkout --detach 7cb9d7a0b37feac986e21622bfadd69a4baec978
git -C <verify>/repo apply --check /path/to/REV-01-candidate.patch
git -C <verify>/repo apply /path/to/REV-01-candidate.patch
```

Results:

| Check | Result | Exit |
|---|---|---|
| Base HEAD | `7cb9d7a0b37feac986e21622bfadd69a4baec978` | 0 |
| Base tree | `2ccdb866dce467dad55d3d83f0f757324d00409b` | 0 |
| `git apply --check` | clean | 0 |
| `git apply` | clean | 0 |
| Reconstructed status | 4 modified + 1 untracked report | 0 |
| `git diff --check` | no whitespace errors | 0 |
| Reconstructed candidate tree | `f0f254166ff7f9723f3a1f52807fa2a3363c4430` | 0 |
| Reconstructed diff stat | 5 files, +412/−4 | 0 |

## Source-versus-reconstructed comparison

Every candidate file was compared byte-for-byte between the source workspace and the reconstructed
candidate:

```text
MATCH bot/file_browser.py
MATCH bot/handlers.py
MATCH tests/test_bot_file_browser.py
MATCH tests/test_file_browser.py
MATCH docs/audits/OHB2-REV-01-STALE-BROWSER-SNAPSHOT-INVALIDATION-REPORT.md
ALL_MATCH=1
```

The reconstructed `git status --short` contained exactly the five candidate paths and no unrelated
changes.

## Protected-scope checks

| Check | Result |
|---|---|
| `git diff --name-only -- bot/web/` in reconstructed candidate | empty |
| `bot/attachments.py` in patch | no |
| `tests/test_doc_code_parity.py` in patch | no |
| `tests/test_def011_a_option_b_limits.py` in patch | no |
| F-03/T-5 protected paths in patch | no |
| `_attachment_service` AST comparison, base vs candidate | unchanged (`True`) |
| `application/octet-stream` / `X-Session-API-Key` / `session_api_key` / privileged proxy / raw ZIP patterns in code or test diff | none |
| Secret patterns in patch | none |
| Unrelated architectural changes | none observed; patch contains only the five candidate files |

The implementation report contains the words `application/octet-stream`, `X-Session-API-Key`, and
`session_api_key` only as negative protected-scope statements; those strings are not present in the
candidate code or test diff.

## Test execution in this packaging task

No candidate tests were rerun. The packaging environment currently reports:

```text
python3 -m pytest --version
No module named pytest
```

The historical implementation-reported test results are recorded separately in `TEST-EVIDENCE.md` and are
attributed, not independently verified by this packaging task. The independent reviewer must install
`requirements-dev.txt` and run the required checks in a separate reviewer session.
