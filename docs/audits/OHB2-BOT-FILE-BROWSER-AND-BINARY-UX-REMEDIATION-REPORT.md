# OHB2 — Bot File Browser & Binary UX Remediation Report

**Task ID:** `OHB2-BOT-FILE-BROWSER-AND-BINARY-UX-REMEDIATION`
**Date:** 2026-11-21
**Final status:** `DONE_WITH_NOTES`

## 1. Executive summary

The reported naming inconsistencies, misspelled identifiers, and handler/API mismatches are **not present
in the live working tree or in the packaged `candidate.patch`**. They were introduced by the manual
plain-text chat export of the patch, not by the source code.

- Live source uses `conversation_id`, `entries()`, `page_entries()`, `page_count()`, `clamp_page()`,
  `conversation_for()`, and the canonical handler names.
- The packaged `docs/reviews/handoff/BOT-FILE-BROWSER/candidate.patch`
  (SHA-256 `0b29a107d8acfb3e607089d7590c33076ece3864ed83c924e8dbeefb017d8aa2`) contains **none** of
  `conversaion_id`, `entires`, `page_entires`, `isinstanse`, `ValueEror`, `IndexEror`, or
  `conversaion_for`.
- No production source change was required. Three regression tests were added to lock the canonical API,
  evicted-state safety, and confirmed-deletion cache invalidation.
- All executable gates pass: full Python suite **3506 passed**, pyflakes **exit 0**, Bandit **High 0**,
  pip-audit **no known vulnerabilities**, Node **280 passed / 0 failed**, `git diff --check` **exit 0**.
- Independent review is **`INDEPENDENCE_NOT_ESTABLISHED`**; a review handoff was prepared but was not
  independently executed.

## 2. Baseline audit

| Item | Value |
|---|---|
| Baseline branch | `main` |
| Baseline HEAD | `ea4a484815aab17c9456eaa6157e3f06475edcf4` |
| `origin/main` | `ea4a484815aab17c9456eaa6157e3f06475edcf4` (equal; no fetch performed) |
| Baseline working tree | clean (`git status --short` produced no entries) |
| Baseline diff | empty (`git diff --stat` produced no entries) |
| Python | 3.13.15 |
| pytest | 9.0.3 |

After recording the baseline, work continued on branch
`agent/ohb2-bot-file-browser-remediation` at the same HEAD. No commit, push, PR, merge, deployment, or
Autopush activation was performed.

### 2.1 Environment note

The host image initially had no `pytest` or `telegram` package. The pinned dependencies were installed with
`python3 -m pip install --user -r requirements-dev.txt`. The first full-suite run then produced one
environment-only failure:

- `tests/test_deploy_manifest.py::test_documented_manifest_is_import_sufficient` failed because its
  isolated subprocess used `HOME=<tmp>` and could not see the user-site `telegram` package.

The same pinned dependencies were then installed into the system site-packages with
`sudo -n python3 -m pip install -r requirements-dev.txt`. The failing test then passed, and the full suite
passed. This was an environment visibility issue, not a source defect.

## 3. Live source versus the transmitted candidate

The transmitted chat text contained manual transcription errors. Examples observed in that text:

| Transmitted text | Live source / packaged candidate |
|---|---|
| `conversaion_id` | `conversation_id` |
| `entires(...)` | `entries(...)` |
| `page_entires(...)` | `page_entries(...)` |
| `conversaion_for(...)` | `conversation_for(...)` |
| `isinstanse` | `isinstance` |
| `ValueEror` | `ValueError` |
| `IndexEror` | `IndexError` |
| `mark_explicity_ignored` | `mark_explicitly_ignored` |
| `_BINARY_UNAVAILEBLE` | `_BINARY_UNAVAILABLE` |

Verification commands:

```text
grep -RInE 'conversaion|entires|page_entires|isinstanse|ValueEror|IndexEror|mark_explicity|UNAVAILEBLE' \
  bot tests docs/reviews/handoff/BOT-FILE-BROWSER/candidate.patch
# no matches in bot/, tests/, or candidate.patch

grep -nE 'conversation_id: str|def entries|def page_entries|def conversation_for' \
  docs/reviews/handoff/BOT-FILE-BROWSER/candidate.patch
# canonical names found
```

The live source and the packaged candidate were therefore consistent. The remediation did not rewrite
correct code to match a corrupted transcript.

## 4. Defects found and fixes applied

### 4.1 Production source

No verified production naming, undefined-identifier, exception-name, or handler/API defect was found.
`bot/file_browser.py`, `bot/handlers.py`, `bot/keyboards.py`, `bot/app.py`, and the browser implementation
were left unchanged.

### 4.2 Regression tests added

1. `tests/test_file_browser.py::test_public_api_names_are_canonical`
   - Asserts the dataclass field `conversation_id`.
   - Asserts `entries`, `page_entries`, `page_count`, and `clamp_page` are callable.
   - Asserts the misspelled names `conversaion_id`, `entires`, and `page_entires` are absent.
   - Asserts `token_for`, `conversation_for`, `put`, `get`, `invalidate`, and `clear` are callable.
   - Asserts `conversaion_for` is absent.

2. `tests/test_bot_file_browser.py::test_evicted_state_callback_is_safe`
   - Evicts the active snapshot through `BrowserCache(max_entries=1)`.
   - Verifies a page callback for the evicted snapshot fails safely with the existing
     «قايمة الملفات دي قديمة…» message.

3. `tests/test_bot_file_browser.py::test_confirmed_deletion_invalidates_browser_cache`
   - Opens a browser snapshot.
   - Drives `delete_conversation_confirm` with a confirmed `STATUS_DELETED` result.
   - Verifies the snapshot and conversation token are invalidated.

No test was weakened, skipped, or rewritten to accommodate broken behavior.

## 5. Changed files and diff statistics

| File | Change | Stat |
|---|---|---|
| `tests/test_file_browser.py` | Canonical API consistency test + `BrowserState` import | **+14/−0** |
| `tests/test_bot_file_browser.py` | Evicted-state and confirmed-deletion regression tests | **+40/−0** |
| **Total** | **2 files** | **+54/−0** |

No production file changed:

```text
git diff --name-only -- bot/ automation/ tools/ main.py bot/web/ docs/
# empty
```

New, previously untracked artifacts created by this task:

- `docs/audits/OHB2-BOT-FILE-BROWSER-AND-BINARY-UX-REMEDIATION-REPORT.md`
- `docs/reviews/handoff/BOT-FILE-BROWSER-REMEDIATION/` (isolated review handoff)

### 5.1 File hashes

| File | HEAD (before) | Working tree (after) |
|---|---|---|
| `tests/test_file_browser.py` | `92c1684e26efef313714ab65928e97ea258fb79f252b8368c1d60af2f9c67b0a` | `34cf8f04e2f7f580a282b0bf14c64a8a89a47370764ef682572636c9276c10a4` |
| `tests/test_bot_file_browser.py` | `1010e481a62024e6ae7e83903255ae0db59482c3f539e2659b71b2db9cd6099c` | `828748992fc99e4c744c396d1f5ad02b8a3d5d7e21413ea867ff92e37ddf52be` |
| `bot/file_browser.py` | `428d977e5a0bc1606e285f1094659489b46d4944a4cf4ee32d85b0d5129ac5c8` | same |
| `bot/handlers.py` | `f1276068fb8ff85a4f0aaea0c00ee399626dc1671b73a5552630413dd016ec6a` | same |

## 6. Tests and commands actually executed

| Command | Result | Exit |
|---|---|---|
| `python3 -m pytest -q tests/test_file_browser.py tests/test_bot_file_browser.py` | **39 passed** | 0 |
| `python3 -m pytest -q tests/test_b06_file_routing.py` | **25 passed** | 0 |
| `python3 -m pytest -q tests/test_files_service.py tests/test_handlers.py tests/test_keyboards.py tests/test_file_cache.py tests/test_openhands_client.py tests/test_files_bounded.py tests/test_files_negative.py tests/test_b06_file_routing.py tests/test_attachment_*.py tests/test_unsupported_attachment_rejection.py tests/test_def011_a_option_b_limits.py` | **662 passed** | 0 |
| `python3 -m pytest -q` | **3506 passed, 74 warnings** in 173.35 s | 0 |
| `python3 -m pyflakes bot/ automation/ tools/ main.py tests/` | no findings | 0 |
| `python3 -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | High **0**; Low 5, Medium 19; no High findings | 0 |
| `python3 -m pip_audit -r requirements-dev.txt` | **No known vulnerabilities found** | 0 |
| `node --test tests/frontend/*.test.js` | **280 passed, 0 failed** | 0 |
| `git diff --check` | no whitespace errors | 0 |

The full-suite increase from the previously recorded 3503 baseline is exactly the three new tests:
`3503 + 3 = 3506`. No skips were reported. The 74 warnings are PTB deprecation warnings
(`PTBDeprecationWarning`), not failures.

### 6.1 Isolated handoff self-check (not independent review)

The handoff patch was applied to a clean archive of `ea4a484` in a temporary directory:

```text
git apply --check candidate.patch   # exit 0
git apply candidate.patch           # exit 0
# changed files: only tests/test_file_browser.py and tests/test_bot_file_browser.py
python3 -m pytest -q tests/test_file_browser.py tests/test_bot_file_browser.py
# 39 passed
```

This confirms that the handoff applies cleanly and that the focused tests pass in the isolated base plus
patch. It is a self-check, not an independent review.

## 7. Security and product scope confirmations

- `FileService.read_preview` remains the only workspace-file read path used by the browser.
- Existing authorization, path validation, allowlist checks, and bounded 256 KiB text reads are unchanged.
- No raw-byte workspace route, `X-Session-API-Key`, privileged proxy, new production route, or new
  credential was added.
- Raw workspace ZIP/binary delivery remains deferred. The existing honest binary/ZIP messages are unchanged.
- Conversation export ZIP remains a separate supported path.
- Upload limits remain unchanged: 3 MiB per file, 10 files per batch, 64 MiB aggregate staged storage,
  and the existing staging TTL.
- No Mini App file was modified: `git diff --name-only -- bot/web/` is empty.
- No production Telegram/OpenHands call, secret, or live-service test was made.

## 8. DEF-011-A Option B and F-03/T-5 preservation

The following command returned exit 0, proving no diff in the preserved paths:

```text
git diff --exit-code -- \
  bot/attachments.py \
  tests/test_doc_code_parity.py \
  tests/test_def011_a_option_b_limits.py \
  docs/reviews/handoff/BOT-FILE-BROWSER \
  docs/reviews/OHB2-WP07-DEF011-F03-INDEPENDENT-REVIEW-REPORT.md \
  docs/audits/OHB2-WP07-DEF011-F03-STALE-REFERENCE-CORRECTION-REPORT.md \
  docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md
```

The DEF-011-A Option B hunk in `bot/handlers.py::_attachment_service` remains intact at lines 2324–2347:
`MAX_ITEMS_PER_BATCH` and `MAX_STAGING_TOTAL_BYTES` are still passed to `StagingStore`. The existing
handoff package, the F-03/T-5 reports, `tests/test_doc_code_parity.py`, and
`tests/test_def011_a_option_b_limits.py` are unchanged.

`git status --short` shows the two modified test files plus the new report and handoff directory:

```text
 M tests/test_bot_file_browser.py
 M tests/test_file_browser.py
?? docs/audits/OHB2-BOT-FILE-BROWSER-AND-BINARY-UX-REMEDIATION-REPORT.md
?? docs/reviews/handoff/BOT-FILE-BROWSER-REMEDIATION/
```

## 9. Remaining limitations

1. **DEF-010 breadth:** the new file-browser callback family is short-token and 64-byte safe, but legacy
   conversation-menu/list callbacks that embed full conversation IDs remain unchanged and tracked outside
   this task.
2. **Empty directories:** the Cloud V1 file listing returns only file paths, so empty directories remain
   unrepresentable.
3. **Bounded snapshot:** the browser keeps one bounded snapshot (16 entries / 50,000 chars / 30-minute TTL)
   and paginates locally; listings above the budget are refused with a clear message.
4. **Snapshot staleness:** refresh replaces the snapshot; old buttons remain valid only until eviction/TTL.
5. **No live service verification:** all tests use isolated fakes; no live Telegram or OpenHands call was
   made.
6. **No independent review:** see section 10.

## 10. Independent review status

**`INDEPENDENCE_NOT_ESTABLISHED`**

This remediation was performed in the implementation session. No separate reviewer conversation/identity
or independently provisioned reviewer environment was available. The prepared handoff at
`docs/reviews/handoff/BOT-FILE-BROWSER-REMEDIATION/` applies cleanly to `ea4a484` and passed the focused
tests in a self-check, but it has not been independently reviewed or independently executed. No
independence claim is made.

## 11. Git and publication status

- Branch: `agent/ohb2-bot-file-browser-remediation`
- HEAD: `ea4a484815aab17c9456eaa6157e3f06475edcf4` (unchanged from baseline)
- Changes: uncommitted (`tests/test_file_browser.py`, `tests/test_bot_file_browser.py` only)
- No commit, push, PR creation/update, merge, deployment, or Autopush activation occurred.
- No `git add .` or `git add -A` was used.
- No destructive Git operation (`reset`, `clean`, force operation, broad deletion, or overwriting of
  unrelated files) was used.
