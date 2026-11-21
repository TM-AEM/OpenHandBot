# REV-01 Test Evidence

## Status of this evidence

These are **historical implementation-reported results**, taken from
`IMPLEMENTATION-REPORT.md` (the implementation report included in this package).

They are **not** independently verified by the packaging task. No original test log or captured command
output was supplied with the implementation workspace. The packaging environment currently has no
`pytest` installed, so the tests were not rerun here.

The independent reviewer must install `requirements-dev.txt` and run the commands below against the
reconstructed candidate in a separate reviewer session.

## Attributed implementation-reported results

| Command | Reported result | Reported exit |
|---|---|---|
| `python3 -m pytest -q tests/test_file_browser.py tests/test_bot_file_browser.py` | 47 passed | 0 |
| `python3 -m pytest -q tests/test_b06_file_routing.py` | 25 passed | 0 |
| Relevant file/handler/keyboard/cache/client/bounded/attachment set | 662 passed | 0 |
| `python3 -m pytest -q` | 3514 passed, 74 warnings | 0 |
| `python3 -m pyflakes bot/ automation/ tools/ main.py tests/` | no findings | 0 |
| `python3 -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | High 0; Low 5; Medium 19 | 0 |
| `python3 -m pip_audit -r requirements-dev.txt` | No known vulnerabilities found | 0 |
| `node --test tests/frontend/*.test.js` | 280 passed, 0 failed | 0 |
| `git diff --check` | no whitespace errors | 0 |

The implementation report attributes the 74 warnings to `PTBDeprecationWarning` and states that no tests
were skipped.

## New REV-01 tests present in the candidate

`tests/test_bot_file_browser.py`:

1. `test_refresh_success_invalidates_old_snapshot_and_publishes_new`
2. `test_empty_refresh_invalidates_old_snapshot`
3. `test_failed_refresh_invalidates_old_snapshot`
4. `test_refresh_exception_invalidates_old_snapshot`
5. `test_open_empty_invalidates_existing_snapshot`
6. `test_open_error_invalidates_existing_snapshot`
7. `test_failed_refresh_leaves_other_conversation_usable`

`tests/test_file_browser.py`:

8. `test_invalidate_snapshots_keeps_token_and_other_conversations`

The candidate also updates the existing API-name test to include `invalidate_snapshots`.

## What the reviewer must establish independently

- The focused tests pass on the reconstructed candidate.
- The routing tests pass.
- The relevant file-service/handler/keyboard/cache/client/bounded/attachment set passes.
- The full Python suite passes.
- Pyflakes, Bandit, pip-audit, Node tests, and `git diff --check` pass.
- The new tests genuinely fail if the invalidation is removed or moved after the listing request.
- Old page/folder/file callbacks are rejected after empty, failed, and exception paths.
- Unrelated conversation snapshots remain usable.
- Confirmed deletion still uses full invalidation.
