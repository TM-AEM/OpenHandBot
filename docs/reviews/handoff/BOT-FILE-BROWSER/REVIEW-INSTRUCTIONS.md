# Review Instructions — OHB2 Bot File Browser Handoff

**Audience:** a genuinely independent reviewer in a separate session and environment.
**Goal:** reconstruct, inspect, and independently verify the exact candidate; report findings with evidence.

---

## 0. Independence

Use a reviewer identity and environment that are genuinely separate from the implementation session. Do not
reuse the implementation agent's conversation, shell session, or workspace. If genuine separation cannot be
demonstrated, report `INDEPENDENCE_NOT_ESTABLISHED` and do not issue a passing verdict.

## 1. Verify the package

```bash
cd BOT-FILE-BROWSER
sha256sum -c SHA256SUMS
```

Every packaged file except `SHA256SUMS` itself must verify. `SHA256SUMS` is the integrity manifest and is
not self-referential.

## 2. Clone the repository independently

```bash
git clone <repository-url> ohb2-review
cd ohb2-review
git checkout 30dfa0d6432cdb8f7787edde38f48fb482b6ced6
git rev-parse HEAD
git status --short
```

Expected: HEAD is `30dfa0d6432cdb8f7787edde38f48fb482b6ced6`; the clone is clean.

## 3. Apply the candidate patch

```bash
git apply --check /path/to/BOT-FILE-BROWSER/candidate.patch
git apply /path/to/BOT-FILE-BROWSER/candidate.patch
```

Expected: both commands succeed. No prerequisite patch is required.

## 4. Verify candidate hashes and exact scope

```bash
sha256sum -c /path/to/BOT-FILE-BROWSER/CANDIDATE-SHA256SUMS
git status --short
git diff --name-only
```

Expected:

- All 8 candidate files verify.
- `git status --short` lists exactly these 8 paths and nothing else:
  - `bot/app.py`
  - `bot/file_browser.py`
  - `bot/handlers.py`
  - `bot/keyboards.py`
  - `docs/audits/OHB2-BOT-FILE-BROWSER-AND-BINARY-UX-IMPLEMENTATION-REPORT.md`
  - `tests/test_b06_file_routing.py`
  - `tests/test_bot_file_browser.py`
  - `tests/test_file_browser.py`
- No `bot/attachments.py`, no `tests/test_doc_code_parity.py`, no F-03 report, no DEF-011-A test.

## 5. Inspect every changed function and relevant caller

At minimum review:

- `bot/file_browser.py`: `build_state`, `parent_path`, `BrowserState.entries/page_count/clamp_page`,
  `BrowserCache.token_for/conversation_for/put/get/invalidate/clear`.
- `bot/keyboards.py`: `conversation_actions(files_cb=...)`, `files_only_menu`, `browser_menu`.
- `bot/handlers.py`: `_files_open_cb`, `_conversation_actions_or_files`, `_bot_file_status_message`,
  `browse_open`, `browse_dir`, `browse_page`, `browse_up`, `browse_root`, `browse_refresh`, `browse_file`,
  `browse_back`; all `conversation_actions` call sites; `list_files`/`show_file` legacy paths; deletion
  cache invalidation.
- `bot/app.py`: handler registration order and patterns.
- Callers: `open_conversation`, `watch_conversation`, `show_status`, `show_cost`, `reply_prompt`,
  `export_conversation`, `delete_conversation_confirm`, `list_files`, `show_file`.

Check for:

- Callback collisions and 64-byte limits.
- Authorization/owner checks on every browser path.
- Snapshot invalidation, TTL, LRU, and refresh behavior.
- Correct directory/file indexing and duplicate basenames.
- Path safety (`is_safe_workspace_path`) and fail-closed behavior.
- Binary/ZIP messaging accuracy and absence of a false download claim.
- No new network route, Agent Server call, or privileged credential.

## 6. Run focused tests

```bash
python3 -m pytest -q tests/test_file_browser.py tests/test_bot_file_browser.py tests/test_b06_file_routing.py
```

Expected during packaging: 61 passed. Reproduce independently; do not rely on this number.

## 7. Run the full Python suite

```bash
python3 -m pytest -q
```

Expected during packaging on the reconstructed candidate: 3486 passed, 0 failed. The implementation
workspace reports 3503 because it contains the excluded DEF-011-A Option B test file. Report your own
counts and any failure with the first failing test and traceback.

## 8. Run lint and security checks

```bash
python3 -m pyflakes bot/ automation/ tools/ main.py tests/
python3 -m bandit -r bot/ automation/ tools/ main.py -lll -s B613
python3 -m pip_audit -r requirements-dev.txt
node --test tests/frontend/*.test.js
```

During packaging: pyflakes 0, bandit High 0, pip-audit clean, Node 280/280. Reproduce independently.

## 9. Review security and callback size

- Confirm every new callback (`fbo:`, `fbd:`, `fbp:`, `fbu:`, `fbr:`, `fbf:`, `fbx:`, `fbb:`) is ≤64 bytes,
  including with a 64-character conversation ID.
- Confirm the short fallback (`files_only_menu`) is used only when the full conversation actions would
  exceed the limit.
- Confirm no raw workspace binary/ZIP download route, no Agent Server download call, and no
  `X-Session-API-Key` use were introduced.
- Confirm the existing `FileService.read_preview` authorization, allowlist, and 256 KiB limit are intact.

## 10. Review cache lifecycle and snapshot invalidation

- Confirm the snapshot is bounded (16 entries / 50,000 chars / 30-minute TTL; token LRU 128).
- Confirm `browse_page`/`browse_dir`/`browse_up`/`browse_root` reuse the snapshot and do not refetch the
  upstream list per page.
- Confirm `browse_refresh` rebuilds the snapshot and invalidates the old nav.
- Confirm conversation deletion invalidates the file/browser caches.
- Confirm expired/invalid/evicted state returns the safe «قديمة» message and does not crash.

## 11. Review folder navigation and pagination correctness

- Dirs first, then files; deterministic ordering.
- Enter directory, go up, return to root, return to chat.
- No duplicates or skips across pages; correct first/last page buttons.
- Duplicate basenames in different directories are distinct.
- Unicode and space-containing paths work.
- Empty root and directory-only-nested cases behave.
- Empty directories are not invented (API limitation).
- Oversized listings produce the bounded-cache message, not unbounded memory use.

## 12. Review binary UX

- `BINARY`, `NOT_UTF8`, and `TOO_LARGE` messages are accurate and do not claim a download.
- ZIP is not described as forbidden or unsupported by Telegram.
- Text preview still sends a document.
- Conversation ZIP export still works.
- Attachment upload and DEF-011-A Option B behavior are unchanged (they are outside this candidate).

## 13. Verify Mini App is unchanged

```bash
git diff --name-only | grep '^bot/web/' || echo 'NO MINI APP FILES'
```

Expected: no Mini App file. Review `bot/web/` behavior in the base revision; the candidate does not change
it.

## 14. Verify raw workspace binary delivery remains deferred

Search the candidate for any new download route or credential use:

```bash
git diff --name-only | xargs grep -nE 'X-Session-API-Key|/api/|download|Agent Server|agent_server' || true
```

Confirm no privileged download path was added. The intended behavior is an explanatory message only.

## 15. Report findings

Use this structure:

- Reviewer identity/session and how it differs from the implementation session.
- Independence statement: `ESTABLISHED` or `INDEPENDENCE_NOT_ESTABLISHED`.
- Base revision verified and package/candidate checksum results.
- Changed-file scope verified.
- Findings, each with severity (`BLOCKER` / `HIGH` / `MEDIUM` / `LOW` / `INFO`), evidence, file path, line
  number, and reproduction command.
- Confirmed defects vs recommendations.
- Test/lint/security results actually run, with commands and exit codes.
- Mini App unchanged: yes/no with evidence.
- Raw binary delivery deferred: yes/no with evidence.
- Any limitations (no live Telegram/OpenHands calls, etc.).

Do not claim acceptance or closure. A separate review verdict is the reviewer's responsibility.
