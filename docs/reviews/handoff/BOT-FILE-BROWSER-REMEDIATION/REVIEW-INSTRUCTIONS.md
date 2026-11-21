# Review instructions — BOT-FILE-BROWSER-REMEDIATION

This review is **read-only**. Do not modify, commit, push, merge, deploy, or open a PR.

## 1. Establish independence

Record your reviewer session/conversation identity and confirm that you are not the implementation session.
If genuine separation cannot be demonstrated, report exactly:

```text
INDEPENDENCE_NOT_ESTABLISHED
```

Do not describe a same-session self-review as independent.

## 2. Verify the patch

1. Create a clean copy of base commit `ea4a484815aab17c9456eaa6157e3f06475edcf4`.
2. Apply `candidate.patch` with `git apply --check` first, then apply it.
3. Confirm the patch touches only:
   - `tests/test_file_browser.py`
   - `tests/test_bot_file_browser.py`
4. Confirm `git diff --name-only -- bot/ automation/ tools/ main.py bot/web/ docs/` is empty.
5. Confirm `bot/file_browser.py` and `bot/handlers.py` are byte-identical to the base commit.
6. Confirm the live source contains the canonical API:
   - `conversation_id`, `entries`, `page_entries`, `page_count`, `clamp_page`
   - `token_for`, `conversation_for`, `put`, `get`, `invalidate`, `clear`
7. Confirm the misspelled names are absent:
   - `conversaion_id`, `entires`, `page_entires`, `conversaion_for`, `isinstanse`, `ValueEror`, `IndexEror`.

## 3. Run the verification

Run these commands from the clean base plus patch:

```text
python3 -m pytest -q tests/test_file_browser.py tests/test_bot_file_browser.py
python3 -m pytest -q tests/test_b06_file_routing.py
python3 -m pytest -q tests/test_files_service.py tests/test_handlers.py tests/test_keyboards.py \
  tests/test_file_cache.py tests/test_openhands_client.py tests/test_files_bounded.py \
  tests/test_files_negative.py tests/test_b06_file_routing.py tests/test_attachment_*.py \
  tests/test_unsupported_attachment_rejection.py tests/test_def011_a_option_b_limits.py
python3 -m pytest -q
python3 -m pyflakes bot/ automation/ tools/ main.py tests/
python3 -m bandit -r bot/ automation/ tools/ main.py -lll -s B613
python3 -m pip_audit -r requirements-dev.txt
node --test tests/frontend/*.test.js
git diff --check
```

Expected counts from the implementation session:

| Check | Expected |
|---|---|
| Focused browser tests | 39 passed |
| `test_b06_file_routing.py` | 25 passed |
| Relevant file/handler/attachment set | 662 passed |
| Full Python suite | 3506 passed, 74 warnings |
| pyflakes | exit 0 |
| Bandit | High 0, exit 0 |
| pip-audit | no known vulnerabilities |
| Node | 280 passed, 0 failed |
| `git diff --check` | exit 0 |

Do not claim a check passed unless you actually ran it and saw the result.

## 4. Report findings only

Report:

- Independence status.
- Patch scope and exclusion verification.
- Command outputs and exit codes.
- Any discrepancy, defect, or unverified check.
- A final verdict of `APPROVED`, `APPROVED_WITH_NOTES`, or `REJECTED`.

Do not modify files. Do not commit, push, or open a PR.
