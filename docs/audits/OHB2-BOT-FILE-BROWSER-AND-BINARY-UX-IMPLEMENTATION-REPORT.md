# OHB2 — Bot File Browser & Binary UX Implementation Report

**Task ID:** `OHB2-BOT-FILE-BROWSER-AND-BINARY-UX-IMPLEMENTATION`
**Date:** 2026-11-21
**Scope:** Telegram Bot only — folder-aware browsing, reliable pagination/navigation, and an accurate
binary/ZIP user experience. **No raw workspace ZIP/binary delivery.**

**Final status:** `IMPLEMENTATION_DONE_WITH_NOTES`

All acceptance criteria are met. The notes cover pre-existing DEF-010 breadth, API limitations (empty
directories), the bounded-snapshot trade-off, and the absence of an independent reviewer environment.

---

## 1. Baseline

| Item | Value |
|---|---|
| Branch | `openhands-workspace-11yyMvqKPjTrIZt1RRpWq9` |
| HEAD | `30dfa0d6432cdb8f7787edde38f48fb482b6ced6` (= `origin/main`; unchanged) |
| Working tree | **not clean** — pre-existing uncommitted work was present and preserved |
| Python | 3.13.15; pytest 9.0.3 |
| Prior recorded full-suite baseline | 3467 passed (DEF-011-A candidate working tree, previous session) |

Pre-existing working-tree changes (not made by this task, preserved):

- `bot/attachments.py` — DEF-011-A Option B limits (uncommitted).
- `bot/handlers.py` — DEF-011-A Option B wiring in `_attachment_service` (+19/−2 of the total diff).
- `docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md`, `tests/test_doc_code_parity.py`.
- Untracked DEF-011-A / F-03 reports, `docs/reviews/handoff/`, `tests/test_def011_a_option_b_limits.py`,
  `DEF011-A-OPTION-B-REVIEW-HANDOFF.zip`.

The diagnosis (`docs/audits/OHB2-BOT-FILE-DELIVERY-AND-BROWSER-DIAGNOSIS.md`) was re-verified against the
current working tree before editing: `show_file` is text-preview-only, the file API returns a flat path
array, and pagination re-fetched the whole list per page.

---

## 2. Implemented changes by problem

### Problem 1 — Folder-aware browsing

- New pure module `bot/file_browser.py`:
  - `build_state()` builds a directory tree from the flat relative-path list returned by
    `GET /app-conversations/{id}/files`. It filters with the existing `is_safe_workspace_path` (fail closed),
    derives every intermediate directory, and stores only directories that a real file path passes through.
    **No empty directories are invented.**
  - `BrowserState` keeps `dirs` (including `""` root), `dir_index`, `subdirs`, and `dir_files`. Entries are
    rendered **directories first, then files**, both deterministically sorted.
  - `parent_path()` provides parent navigation.
- New keyboard `bot/keyboards.py::browser_menu` renders `📁 <dir>/` and `📄 <file>` buttons, plus
  `⬆️ لأعلى`, `🏠 الرئيسية`, `⬅️ السابق`, `➡️ التالي`, `🔄 تحديث`, and `↩️ رجوع للشات`.
- New handlers in `bot/handlers.py`: `browse_open`, `browse_dir`, `browse_up`, `browse_root`, `browse_back`.
  The current directory is shown in the message (`📁 /` or `📁 src/util`) and in the page indicator.
- `bot/keyboards.py::conversation_actions` accepts an optional `files_cb`; the Files button now uses the
  short browser callback (`fbo:<token>`). All bot call sites that render the conversation actions pass it
  (`open_conversation`, `watch_conversation`, `show_status`, `show_cost`, the legacy empty `list_files`, and
  `reply_prompt`).
- `bot/app.py` registers the new `fbo:`, `fbd:`, `fbp:`, `fbu:`, `fbr:`, `fbf:`, `fbx:`, `fbb:` handlers.
  The legacy `files:`/`file:` handlers remain for old messages.

**Behavior and limitations**

- Enter a directory, go up one level, return to root, or return to the chat.
- Files are listed only for the current directory; nested files are not mixed in.
- Duplicate basenames in different directories are distinct: the state stores full paths, and file
  callbacks carry the directory index + file index.
- Paths with spaces and Unicode work (indices in callback data; no path encoding).
- Empty root: «ما فيهاش ملفات.» with the conversation actions.
- A directory containing only nested directories is handled (shows its subdirectories).
- **Empty directories are not representable**: the Cloud V1 API returns only file paths, so a directory
  with no files anywhere cannot appear. This is documented, not fabricated.
- Very large listings above the bounded cache budget produce a clear message instead of a broken keyboard.

### Problem 2 — Reliable and efficient pagination/navigation

- New `BrowserCache` in `bot/file_browser.py`:
  - Bounded snapshot: `MAX_ENTRIES=16`, `MAX_TOTAL_CHARS=50_000` (same budget family as `FileCache`),
    `STATE_TTL_SECONDS=30*60`, and `MAX_TOKENS=128` for short conversation tokens.
  - LRU eviction for snapshots and tokens; expired/invalid/evicted state returns the existing
    «قايمة الملفات دي قديمة…» message.
- Pagination is **local to the snapshot**: `browse_open`/`browse_refresh` fetch once; `browse_page`,
  `browse_dir`, `browse_up`, and `browse_root` reuse the cached state. The upstream list is **not**
  re-fetched for every page.
- `BrowserState.page_count`, `clamp_page`, and `page_entries` provide first/middle/final pages, Previous,
  Next, current page, total pages, and boundary clamping.
- The current directory is preserved while paging.
- Page/file/directory callbacks share the same snapshot nav, so moving between pages does **not**
  invalidate valid file-selection callbacks. A refresh deliberately replaces the snapshot.
- Deterministic ordering (`sorted()` dirs, then `sorted()` files) prevents duplicates/skips between pages.
- Files added/removed after the snapshot: the snapshot stays stable; `🔄 تحديث` re-fetches and rebuilds
  while trying to stay in the same directory. If the refreshed listing is empty, the browser returns to the
  conversation actions.
- Memory stays bounded: the cache evicts by count/chars/TTL; an oversized snapshot is refused with a clear
  message rather than retained unbounded. The API itself only offers a complete flat listing, so one
  bounded snapshot per browsing session is the documented trade-off.
- Cache lifecycle: snapshots are dropped for a conversation on refresh/new open; `_file_cache` and
  `_browser_cache` are invalidated when a conversation is confirmed deleted.

**DEF-010 result**

- New file-browser callbacks use a 16-hex token and small indices:
  - `fbo:<16 hex>` = 20 bytes (Files button);
  - `fbd:<nav>:<dir>`, `fbu:<nav>:<dir>`, `fbr:<nav>`, `fbx:<nav>:<dir>`, `fbb:<nav>`;
  - `fbp:<nav>:<dir>:<page>`, `fbf:<nav>:<dir>:<file>`.
  All stay well below 64 bytes even for a 64-character conversation ID (tested).
- A short fallback keyboard (`files_only_menu`: Files + «شاتاتي») is used if the full conversation actions
  would exceed 64 bytes for a long ID, so the browser's «رجوع للشات» and empty-root paths do not crash.
- **Note:** the pre-existing DEF-010 breadth in the rest of `conversation_actions` / conversation-list
  callbacks (e.g., `reply:<full-id>`, `open:<full-id>`, `deleteok:<full-id>`) is **not expanded** by this
  task. Those callbacks still embed the full conversation ID. The file-browser family is DEF-010-safe and
  tested; the broader issue remains tracked separately.

### Problem 3 — Binary/ZIP user experience

- `bot/handlers.py::_bot_file_status_message` distinguishes:
  - `BINARY` → «الملف ده ثنائي (مثل ZIP أو صورة)، والبوت بيعرض الملفات النصية بس. تنزيل بايتات ملفات
    مساحة العمل مش متاح حاليًا عبر تكامل Cloud V1 المدعوم.»
  - `NOT_UTF8` → «الملف بترميز غير مدعوم (مش UTF-8)… تنزيل بايتات الملف مش متاح حاليًا عبر Cloud V1…»
  - `TOO_LARGE` → «الملف أكبر من حد المعاينة النصية الآمن (256 KiB)… تنزيل بايتات الملف مش متاح حاليًا…»
- The new `browse_file` handler and the legacy `show_file` handler use this bot-specific message. The shared
  `bot/files.py::FILE_STATUS_MESSAGES` was **not** changed, so Mini App behavior is untouched.
- The message does **not** say ZIP is forbidden or unsupported by Telegram, does **not** imply a download or
  delivery, and is never silent.
- Text preview is unchanged: `FileStatus.OK` still sends a text document with the existing truncation note.
- Security and size limits are unchanged: `FileService.read_preview` (authorization + allowlist + 256 KiB
  bounded read) is still the only workspace-file read path. No Agent Server route, no session key, no
  privileged proxy, no new network route.
- Conversation export ZIP (`export_conversation`) is unchanged and still works (tested).
- Attachment upload behavior and the approved Option B limits are unchanged.

---

## 3. Changed files and diff statistics

**Changed by this task**

| File | Change | Stat |
|---|---|---|
| `bot/file_browser.py` | New: tree builder, `BrowserState`, `BrowserCache` | **new, 239 lines** |
| `bot/handlers.py` | New browser handlers, binary messages, `files_cb`, deletion cache invalidation | **+387/−8 total**; 19 additions/2 deletions are the pre-existing Option B hunk → this task ≈ **+368/−6** |
| `bot/keyboards.py` | `files_cb` on `conversation_actions`, `files_only_menu`, `browser_menu` | **+62/−1** |
| `bot/app.py` | Register `fbo/fbd/fbp/fbu/fbr/fbf/fbx/fbb` handlers | **+10/−0** |
| `tests/test_file_browser.py` | New pure tree/pagination/cache tests (16) | **new, 155 lines** |
| `tests/test_bot_file_browser.py` | New handler/binary/DEF-010 tests (20) | **new, 473 lines** |
| `tests/test_b06_file_routing.py` | Updated legacy binary/too-large message assertions | **+6/−2** |
| `docs/audits/OHB2-BOT-FILE-BROWSER-AND-BINARY-UX-IMPLEMENTATION-REPORT.md` | This report | new |

**Pre-existing, untouched** (preserved): `bot/attachments.py`, the DEF-011-A Option B hunk in
`bot/handlers.py`, `docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md`,
`tests/test_doc_code_parity.py`, and all untracked DEF-011-A/F-03 artifacts and the handoff ZIP.

**Mini App:** `git status --short -- bot/web/` returned **0 entries**. No HTML, JS, CSS, frontend asset,
frontend behavior, or Mini App API contract was modified.

---

## 4. Regression tests added and executed

**New tests — 36 total, all pass**

`tests/test_file_browser.py` (16):
root mixed dirs/files, nested paths, duplicate names, directory-only-nested, Unicode/spaces, unsafe paths,
empty root, pagination boundaries/no duplicates, `parent_path`, token stability/length, put/get/invalidate,
TTL expiry, LRU eviction, char budget, token LRU, snapshot replacement, token survival.

`tests/test_bot_file_browser.py` (20):
root rendering + dirs first + ≤64-byte callbacks, enter/up/root navigation, duplicate names distinct,
previous/next/boundaries/no duplicates, snapshot stability + refresh, refresh preserving the directory,
expired/invalid/non-owner safety, binary ZIP message (no document, no download), NOT_UTF8/TOO_LARGE,
text preview still sends a document, 64-char conversation-ID callbacks ≤64 bytes, long-ID fallback for
back/empty-root, back-to-chat, empty root, directory-only-nested, Unicode/spaces, conversation ZIP export,
legacy `show_file` binary message, oversized-listing guard.

**Executed commands and results**

| Command | Result |
|---|---|
| `python3 -m pytest -q tests/test_file_browser.py tests/test_bot_file_browser.py` | **36 passed**, exit 0 |
| `python3 -m pytest -q tests/test_b06_file_routing.py` | **25 passed**, exit 0 |
| `python3 -m pytest -q` (full suite) | **3503 passed**, 0 failed, 74 warnings, exit 0 (166.01 s) |
| `python3 -m pyflakes bot/ automation/ tools/ main.py tests/` | **exit 0** (no findings) |
| `python3 -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | **High: 0**, exit 0 |
| `python3 -m pip_audit -r requirements-dev.txt` | **No known vulnerabilities**, exit 0 |
| `node --test tests/frontend/*.test.js` | **280 passed, 0 failed**, exit 0 |
| `git diff --check` | my files clean; one **pre-existing** blank line at EOF in `tests/test_doc_code_parity.py` (not introduced by this task) |

The full-suite increase is consistent with the 36 new tests (prior recorded baseline 3467 → 3503). I did not
re-run the baseline before editing, so the before/after comparison uses the prior recorded baseline, not a
freshly measured one.

---

## 5. Remaining risks and blockers

1. **Raw workspace ZIP/binary delivery remains deferred.** Cloud V1 exposes no binary workspace-file route;
   the Agent Server download route requires a full-privilege `X-Session-API-Key` (B1) which the bot does not
   request or store. This task does not implement or bypass it. The unresolved security decision is recorded
   separately.
2. **Empty directories cannot be shown** — the Cloud V1 file listing returns only file paths.
3. **Bounded snapshot trade-off.** The API only offers a complete flat listing. The browser retains one
   bounded snapshot (16 entries / 50,000 chars / 30-minute TTL) and paginates locally. Listings above the
   budget are refused with a clear message; they are not loaded unbounded.
4. **Snapshot staleness.** Files added/removed after opening are visible after «تحديث». Old message buttons
   remain valid until eviction/TTL; refresh replaces the snapshot and expires the old nav.
5. **Per-file allowlist re-check.** `browse_file` still calls `FileService.read_preview`, which re-fetches the
   listing for the security allowlist. This preserves the existing security contract at the cost of one
   extra API call per file click.
6. **DEF-010 breadth.** The file-browser family and the Files button are fixed and tested. The pre-existing
   conversation-menu/list callbacks that still embed full conversation IDs are unchanged and remain tracked
   as DEF-010 outside this task.
7. **No live service verification.** All tests use isolated fakes; no live Telegram or OpenHands production
   call was made.

---

## 6. Independent review status

**`INDEPENDENCE_NOT_ESTABLISHED`**

The diff was self-reviewed file by file and all gates were re-run in this same session. That is **not**
independent review. No separate reviewer session/identity or independently provisioned reviewer environment
was available, so no independence claim is made.

---

## 7. Git and publication status

- Branch `openhands-workspace-11yyMvqKPjTrIZt1RRpWq9`; HEAD `30dfa0d6432cdb8f7787edde38f48fb482b6ced6`
  (unchanged).
- All changes are **uncommitted**. No `git add .`/`git add -A`, no commit, push, PR, merge, deployment, or
  Autopush activation.
- No destructive Git operation was used. All pre-existing tracked, untracked, and ignored files were
  preserved; the DEF-011-A handoff package was not modified.
- Mini App files were not modified.

---

## 8. Final status

# `IMPLEMENTATION_DONE_WITH_NOTES`

The three approved bot-side improvements are implemented and verified: folder-aware browsing from the
existing flat path list, stable Previous/Next pagination with snapshot reuse and page indicators, and an
accurate binary/ZIP explanation that preserves text preview and security limits. Raw ZIP/binary delivery
remains explicitly deferred. The notes above record the pre-existing DEF-010 breadth, the API's empty-directory
limitation, the bounded-snapshot trade-off, and the unestablished independent review.
