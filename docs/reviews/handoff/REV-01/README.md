# REV-01 Independent Review Handoff Package

This package contains the exact uncommitted REV-01 candidate for:

`OHB2-REV-01-STALE-BROWSER-SNAPSHOT-INVALIDATION`

The candidate is packaged as a patch against base commit
`7cb9d7a0b37feac986e21622bfadd69a4baec978` (tree
`2ccdb866dce467dad55d3d83f0f757324d00409b`).

## Important independence requirement

A genuinely independent review requires:

1. A **new OpenHands conversation**.
2. A separate, fresh clone/workspace.
3. No reuse of the implementation conversation or its working directory.
4. Verification of the ZIP and patch SHA-256 checksums before extraction or application.

Starting a fresh clone inside the implementation conversation does **not** establish independent
session review. Independence must be established by the reviewer session, not by a clone alone.

## Package contents

| File | Purpose |
|---|---|
| `README.md` | This reconstruction and review guide |
| `REV-01-candidate.patch` | Exact candidate patch against base `7cb9d7a` |
| `candidate-manifest.json` | Machine-readable base/candidate identity, file inventory, hashes, exclusions |
| `IMPLEMENTATION-REPORT.md` | Copy of the implementation report; its test claims are attributed, not independently verified here |
| `RECONSTRUCTION-VERIFICATION.md` | Commands and evidence that the patch reconstructs the candidate exactly |
| `TEST-EVIDENCE.md` | Historical implementation-reported test results, clearly attributed |
| `ENVIRONMENT.md` | Packaging environment and dependency limitations |
| `SHA256SUMS.txt` | SHA-256 checksums for package files (except itself) |

## Reviewer reconstruction procedure

### 1. Verify package integrity

From the extracted package directory:

```sh
sha256sum -c SHA256SUMS.txt
```

Verify the ZIP SHA-256 supplied in the handoff report before extraction.

### 2. Create an independent workspace

Use a genuinely separate reviewer session and a fresh clone or workspace. Do not use the implementation
conversation's working directory.

```sh
git clone https://github.com/TM-AEM/OpenHandBot.git review-repo
cd review-repo
git checkout --detach 7cb9d7a0b37feac986e21622bfadd69a4baec978
git rev-parse HEAD
git rev-parse HEAD^{tree}
```

Expected:

- HEAD: `7cb9d7a0b37feac986e21622bfadd69a4baec978`
- Tree: `2ccdb866dce467dad55d3d83f0f757324d00409b`

### 3. Apply the exact candidate patch

```sh
git apply --check /path/to/REV-01-candidate.patch
git apply /path/to/REV-01-candidate.patch
git status --short
```

Expected status:

```text
 M bot/file_browser.py
 M bot/handlers.py
 M tests/test_bot_file_browser.py
 M tests/test_file_browser.py
?? docs/audits/OHB2-REV-01-STALE-BROWSER-SNAPSHOT-INVALIDATION-REPORT.md
```

### 4. Verify reconstructed files against the manifest

For every candidate path in `candidate-manifest.json`, compare the reconstructed file's SHA-256 with the
manifest. The five candidate files are:

- `bot/file_browser.py`
- `bot/handlers.py`
- `tests/test_bot_file_browser.py`
- `tests/test_file_browser.py`
- `docs/audits/OHB2-REV-01-STALE-BROWSER-SNAPSHOT-INVALIDATION-REPORT.md`

Also run:

```sh
git diff --check
```

### 5. Install declared development dependencies

```sh
pip install -r requirements-dev.txt
```

The packaging environment currently has no `pytest` installed. The implementation report's historical
test results are not a substitute for the reviewer's own run.

### 6. Independently inspect and test

Inspect the actual candidate code and tests. Do not rely on `IMPLEMENTATION-REPORT.md` or
`TEST-EVIDENCE.md` as evidence. Run the required commands from the review task, including:

```sh
python3 -m pytest -q tests/test_file_browser.py tests/test_bot_file_browser.py
python3 -m pytest -q tests/test_b06_file_routing.py
python3 -m pytest -q
python3 -m pyflakes bot/ automation/ tools/ main.py tests/
python3 -m bandit -r bot/ automation/ tools/ main.py -lll -s B613
python3 -m pip_audit -r requirements-dev.txt
node --test tests/frontend/*.test.js
git diff --check
```

Run the broader relevant file-service, handler, keyboard, cache, OpenHands-client, bounded-file, and
attachment test set required by the review task.

### 7. Produce a separate review report

Write a new independent review report in the reviewer's own workspace. Do not modify implementation code
or tests. Classify findings and issue an exact verdict.

## Scope notes

- The patch contains only the five REV-01 candidate files.
- The handoff package itself is **not** part of the patch.
- The ZIP archive is outside the source-controlled project tree and is **not** part of the patch.
- No unrelated workspace changes were present when the patch was built.
- Ignored `.openhands/`, `.pytest_cache/`, and `__pycache__/` content was excluded.
- Historical test results are implementation-reported claims; this packaging task did not rerun them.
