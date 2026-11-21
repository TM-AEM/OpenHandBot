# OHB2 — REV-01 Stale Browser Snapshot Invalidation Report

**Task ID:** `OHB2-REV-01-STALE-BROWSER-SNAPSHOT-INVALIDATION`
**Status:** `DONE`
**Date:** 2026-11-21

## 1. Baseline audit

| Item | Value |
|---|---|
| Branch | `main` |
| HEAD | `7cb9d7a0b37feac986e21622bfadd69a4baec978` |
| `origin/main` (local info only) | `7cb9d7a0b37feac986e21622bfadd69a4baec978` |
| Working tree before edits | clean (`git status --short` empty) |
| Python | 3.13.15 |
| pytest | 9.0.3 |

The baseline had no pre-existing diffs. The working tree was clean before the REV-01 edits.

## 2. Root cause

`browse_open` and `browse_refresh` requested the new listing **before** dropping the old snapshot:

- `browse_open` called `list_files` and returned on an empty or non-OK result without invalidating the
  existing snapshot.
- `browse_refresh` did the same.
- A raised listing exception also left the old snapshot in place.
- `BrowserCache.invalidate` could not be used directly for this path because it also removes the stable
  conversation token, which is needed for the “الملفات” retry button.

The old `nav` therefore remained usable through old page/folder/file callbacks until TTL or LRU eviction.

## 3. Exact invalidation behavior

### Before

```text
browse_open:
    listing = await list_files(conversation_id)
    if listing is not OK or listing.files is empty:
        return                      # old snapshot remains cached
    put new snapshot

browse_refresh:
    listing = await list_files(state.conversation_id)
    if listing is not OK or listing.files is empty:
        return                      # old snapshot remains cached
    put new snapshot
```

### After

```text
browse_open:
    cache.invalidate_snapshots(conversation_id)
    listing = await _browser_list_files(...)
    if listing is None: return      # old snapshot already gone
    if listing is not OK: return    # old snapshot already gone
    if listing.files is empty: show empty message with valid retry token
    put new snapshot

browse_refresh:
    old_dir = ...
    cache.invalidate_snapshots(state.conversation_id)
    listing = await _browser_list_files(...)
    if listing is None: return      # old snapshot already gone
    if listing is not OK: return    # old snapshot already gone
    if listing.files is empty: show empty message with valid retry token
    put new snapshot
```

### Cache method

`BrowserCache.invalidate_snapshots(conversation_id)` drops only the states for that conversation and
keeps the conversation token valid for retry. `BrowserCache.invalidate` is unchanged and still removes
both states and token for confirmed deletion.

### Exception boundary

`_browser_list_files` catches unexpected listing exceptions, edits the message to
`_FILES_LISTING_FAILED` (“تعذّر الوصول لقايمة الملفات دلوقتي. جرّب تاني.”), records
`mark_ambiguous_external(..., "files_listing_exception")`, and returns `None`. The caller has already
invalidated the old snapshot, so an exception cannot leave stale callbacks usable.

### Concurrency

The production poller serializes updates (`bot/polling.py:13,175-178`; `bot/app.py:75-81`). It puts an
update on `update_queue` and awaits `update_queue.join()` before the next one, so overlapping
open/refresh handlers do not occur in the current architecture. No new lock or coordination subsystem
was added. If a future concurrent dispatcher is introduced, a per-conversation generation check would be
needed; that is recorded as a remaining limitation, not implemented here.

## 4. Files changed and diff statistics

| File | Change |
|---|---|
| `bot/file_browser.py` | Added `BrowserCache.invalidate_snapshots` (snapshot-only invalidation) |
| `bot/handlers.py` | Invalidate before open/refresh listing; added `_browser_list_files` exception boundary and `_FILES_LISTING_FAILED` |
| `tests/test_bot_file_browser.py` | 7 handler-level REV-01 regression tests |
| `tests/test_file_browser.py` | 1 cache-level invalidation test + new API check |
| **Total** | **4 files, +221/−4** |

The report file itself is a new untracked artifact and is not included in the diff statistic above.

## 5. Regression tests added

1. `tests/test_file_browser.py::test_invalidate_snapshots_keeps_token_and_other_conversations`
2. `tests/test_bot_file_browser.py::test_refresh_success_invalidates_old_snapshot_and_publishes_new`
3. `tests/test_bot_file_browser.py::test_empty_refresh_invalidates_old_snapshot`
4. `tests/test_bot_file_browser.py::test_failed_refresh_invalidates_old_snapshot`
5. `tests/test_bot_file_browser.py::test_refresh_exception_invalidates_old_snapshot`
6. `tests/test_bot_file_browser.py::test_open_empty_invalidates_existing_snapshot`
7. `tests/test_bot_file_browser.py::test_open_error_invalidates_existing_snapshot`
8. `tests/test_bot_file_browser.py::test_failed_refresh_leaves_other_conversation_usable`

Focused result: **47 passed** (39 pre-existing + 8 new). Existing refresh/stability tests remain green.

## 6. Verification results

| Command | Result | Exit |
|---|---|---|
| `python3 -m pytest -q tests/test_file_browser.py tests/test_bot_file_browser.py` | **47 passed** in 1.69s | 0 |
| `python3 -m pytest -q tests/test_b06_file_routing.py` | **25 passed** in 1.50s | 0 |
| Relevant file/handler/keyboard/cache/client/bounded/attachment set | **662 passed** in 23.42s | 0 |
| `python3 -m pytest -q` | **3514 passed, 74 warnings** in 172.06s | 0 |
| `python3 -m pyflakes bot/ automation/ tools/ main.py tests/` | no findings | 0 |
| `python3 -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | High **0**; Low 5, Medium 19 | 0 |
| `python3 -m pip_audit -r requirements-dev.txt` | No known vulnerabilities found | 0 |
| `node --test tests/frontend/*.test.js` | **280 passed, 0 failed** | 0 |
| `git diff --check` | no whitespace errors | 0 |

The 74 warnings are `PTBDeprecationWarning` messages from python-telegram-bot, not failures. No tests
were skipped.

## 7. Evidence that stale callbacks are rejected

The regression tests exercise the actual handlers and `BrowserCache`:

- After an empty refresh, `cache.get(old_nav) is None`; old `fbp` (page), `fbd` (folder), and `fbf`
  (file) callbacks all return the existing “قديمة” expired response.
- After a non-OK refresh, the old snapshot is absent, the edit has no reply markup, and old callbacks
  return “قديمة”.
- After a raised refresh exception, the old snapshot is absent, the user sees the clear failure message,
  and old callbacks return “قديمة”.
- After an empty or failed `browse_open`, the existing snapshot is absent and old callbacks return
  “قديمة”.
- After a successful non-empty refresh, the old snapshot is absent, the new snapshot is present, and a
  page callback on the new `nav` works.
- Empty-result messages contain only the conversation-action retry controls; they do not expose stale
  `fbp`/`fbd`/`fbf`/`fbx`/`fbb` navigation.

## 8. Evidence that unrelated conversations remain unaffected

- `test_failed_refresh_leaves_other_conversation_usable` opens `c1` and `c2`, fails the `c1` refresh,
  and verifies `c1`’s snapshot is gone while `c2`’s snapshot remains present and its page callback still
  works.
- `test_invalidate_snapshots_keeps_token_and_other_conversations` verifies that invalidating `c1`
  leaves `c2`’s state and token intact, and that `c1`’s token remains valid for retry.

## 9. Protected-work and scope checks

- `git diff --name-only -- bot/web/` is empty. Mini App untouched.
- `git diff --name-only -- bot/attachments.py tests/test_doc_code_parity.py tests/test_def011_a_option_b_limits.py docs/reviews/handoff/BOT-FILE-BROWSER docs/reviews/OHB2-WP07-DEF011-F03-INDEPENDENT-REVIEW-REPORT.md docs/audits/OHB2-WP07-DEF011-F03-STALE-REFERENCE-CORRECTION-REPORT.md` is empty.
- An AST comparison of `_attachment_service` between `HEAD` and the working tree returned
  `attachment_service_unchanged: True`; the DEF-011-A Option B wiring is intact.
- No binary-download or privileged-access mechanism was added. The diff contains no
  `application/octet-stream`, `X-Session-API-Key`, `session_api_key`, or raw workspace binary route.
- Existing successful browsing, folder navigation, pagination, and file-preview tests remain green.

## 10. Remaining limitations

1. **Legacy DEF-010:** legacy callbacks that embed full conversation IDs remain unchanged and out of
   scope.
2. **Empty directories:** Cloud V1 returns only file paths, so empty directories remain unrepresentable.
3. **Bounded snapshots:** the existing 16-entry / 50,000-char / 30-minute snapshot limits remain.
4. **Concurrency:** the current poller is sequential; no new lock was added. A future concurrent
   dispatcher would need a generation check to prevent an older request from republishing after a newer
   one.
5. **No live service tests:** all tests use fakes; no production Telegram/OpenHands call was made.
6. **No independent review in this task:** this is implementation and self-verification only; a separate
   review is still required.

## 11. Git and publication status

- Branch: `main`
- HEAD before edits: `7cb9d7a0b37feac986e21622bfadd69a4baec978`
- Working tree after edits: 4 modified files plus this new untracked report.
- **No commit, push, PR creation/update, merge, deployment, or Autopush activation occurred.**
- No `git add .` or `git add -A` was used.
- No destructive Git command (reset, clean, force operation, or broad deletion) was used.
- Pre-existing tracked, untracked, ignored, `.openhands/`, and `.agent/` content was preserved.
