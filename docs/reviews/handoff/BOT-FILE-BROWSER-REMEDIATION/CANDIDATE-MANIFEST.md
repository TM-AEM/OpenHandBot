# Candidate manifest — BOT-FILE-BROWSER-REMEDIATION

**Task:** `OHB2-BOT-FILE-BROWSER-AND-BINARY-UX-REMEDIATION`
**Base commit:** `ea4a484815aab17c9456eaa6157e3f06475edcf4`
**Patch:** `candidate.patch`
**Patch SHA-256:** `18c77bc80fb18940f0a33eab7078750e352d14fbb9c4e7040b8b8db29cdad329`
**Patch size:** 77 lines

## Changed files in the patch

| File | Change | HEAD hash (before) | Patched hash (after) |
|---|---|---|---|
| `tests/test_file_browser.py` | +14/−0: canonical API consistency test and `BrowserState` import | `92c1684e26efef313714ab65928e97ea258fb79f252b8368c1d60af2f9c67b0a` | `34cf8f04e2f7f580a282b0bf14c64a8a89a47370764ef682572636c9276c10a4` |
| `tests/test_bot_file_browser.py` | +40/−0: evicted-state safety and confirmed-deletion cache invalidation | `1010e481a62024e6ae7e83903255ae0db59482c3f539e2659b71b2db9cd6099c` | `828748992fc99e4c744c396d1f5ad02b8a3d5d7e21413ea867ff92e37ddf52be` |

Total: **2 files, +54/−0 lines**. No production source file is in the patch.

## Production files intentionally unchanged

| File | Base and patched SHA-256 |
|---|---|
| `bot/file_browser.py` | `428d977e5a0bc1606e285f1094659489b46d4944a4cf4ee32d85b0d5129ac5c8` |
| `bot/handlers.py` | `f1276068fb8ff85a4f0aaea0c00ee399626dc1671b73a5552630413dd016ec6a` |

## Exclusions

This handoff deliberately excludes:

- DEF-011-A Option B: `bot/attachments.py`, `bot/handlers.py::_attachment_service`,
  `tests/test_def011_a_option_b_limits.py`, and the DEF-011-A handoff package.
- F-03/T-5: `tests/test_doc_code_parity.py`, the F-03 reports, and the F-03/T-5 handoff content.
- Mini App: every file under `bot/web/`.
- Unrelated working-tree, ignored, cache, and handoff files.
- The existing `docs/reviews/handoff/BOT-FILE-BROWSER/` package.

## Expected verification

| Check | Expected |
|---|---|
| `python3 -m pytest -q tests/test_file_browser.py tests/test_bot_file_browser.py` | 39 passed |
| `python3 -m pytest -q tests/test_b06_file_routing.py` | 25 passed |
| Relevant file/handler/attachment set | 662 passed |
| `python3 -m pytest -q` | 3506 passed, 74 warnings |
| `python3 -m pyflakes ...` | exit 0 |
| `python3 -m bandit ...` | High 0, exit 0 |
| `python3 -m pip_audit ...` | no known vulnerabilities |
| `node --test tests/frontend/*.test.js` | 280 passed, 0 failed |
| `git diff --check` | exit 0 |

## Independence

**`INDEPENDENCE_NOT_ESTABLISHED`** at handoff time. The handoff has not been independently executed.
