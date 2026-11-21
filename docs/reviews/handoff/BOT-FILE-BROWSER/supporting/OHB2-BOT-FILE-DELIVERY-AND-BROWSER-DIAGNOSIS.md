# OHB2 — Bot File Delivery & Browser Diagnosis

**Task ID:** `OHB2-BOT-FILE-DELIVERY-AND-BROWSER-DIAGNOSIS`
**Audit date:** 2026-11-21
**Type:** diagnosis only — no production code, tests, or user-facing behavior were changed.

**Final status:** `DIAGNOSIS_COMPLETE_WITH_BLOCKERS`

The ZIP-delivery problem has an upstream provider limitation for raw workspace-file bytes. Folder
organization and pagination are fully implementable bot-side with no upstream blocker.

---

## 1. Repository baseline and working-tree state

| Item | Value |
|---|---|
| Branch | `openhands-workspace-11yyMvqKPjTrIZt1RRpWq9` |
| HEAD | `30dfa0d6432cdb8f7787edde38f48fb482b6ced6` (= `origin/main`) |
| Working tree | **not clean** — contains pre-existing uncommitted work (see below) |
| Python | 3.13.15; pytest 9.0.3 |

Pre-existing changes present before this audit (preserved, not touched):

- `bot/attachments.py`, `bot/handlers.py` — uncommitted **DEF-011-A Option B** wiring
  (`StagingStore(max_items_per_batch=10, max_total_bytes=64 MiB)` in
  `bot/handlers.py::_attachment_service`, lines 1960–1985). This is relevant to **uploads** only.
- `docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md`, `tests/test_doc_code_parity.py`
  — pre-existing F-03/T-5 changes.
- Untracked DEF-011-A / F-03 reports, `docs/reviews/handoff/`, `tests/test_def011_a_option_b_limits.py`,
  and `DEF011-A-OPTION-B-REVIEW-HANDOFF.zip`.

**Important:** this diagnosis reads the **current working tree**, not only `origin/main`. The uncommitted
Option B caps (10 files / 64 MiB) are active in the running configuration and are noted where relevant.

---

## 2. Scope confirmation

**In scope (inspected):** Telegram bot handlers/callbacks, bot-side file listing/browsing, pagination and
navigation state, bot-side file retrieval/delivery, the OpenHands client integration used by the bot, and
the relevant DB/cache/persistence and tests/docs.

**Out of scope (not modified):** Mini App HTML/JS/CSS/assets, Mini App API contracts, and any redesign
unrelated to the three reported problems. The Mini App was inspected **read-only** only to document the
shared backend dependency (`bot/web/services.py::MiniAppService._files` uses the same `FileService`, and
`bot/web/static/files.js::buildTree` is the proven client-side folder-tree pattern).

No Mini App file or behavior was changed.

---

## 3. ZIP delivery execution-path analysis

### 3.1 There are two distinct ZIP paths — do not conflate them

| Path | Trigger | Method | Sends a ZIP? |
|---|---|---|---|
| **A. Workspace file preview** | User taps a file button in the chat file browser | `bot/handlers.py::show_file` (1780) → `FileService.read_preview` → `read_file_text_bounded` | **No** — text preview only |
| **B. Conversation export** | User taps «تصدير» | `bot/handlers.py::export_conversation` (1676) → `client.export_conversation` → `send_document` | **Yes** (ZIP of the conversation trajectory) |

The reported symptom ("ZIP fails while other extensions send") matches **Path A**: text files
(`.md`, `.py`, `.txt`, `.json`) pass the text classifier and are sent as preview documents; a `.zip`
workspace file is binary and is rejected **before** `send_document`.

### 3.2 Path A — workspace ZIP: exact trace and failure point

1. `bot/handlers.py::list_files` (1731) calls `FileService.list_files` (files.py:340), which calls
   `client.list_files` → `GET /app-conversations/{id}/files` (openhands_client.py:174). It returns a flat
   list of relative paths.
2. The user taps a file button; `bot/handlers.py::show_file` (1780) resolves the cached path.
3. `show_file` calls `FileService.read_preview` (files.py:352).
4. `read_preview` calls `client.read_file_text_bounded` (openhands_client.py:204) →
   `GET /app-conversations/{id}/file?file_path=...` with `Accept-Encoding: identity`, capped at
   **256 KiB** (`MAX_FILE_RESPONSE_BYTES`, line 28), and `json.loads(body)` expecting a **JSON string**.
5. `classify_text` (files.py:269) inspects the decoded string:
   - contains `\x00` ⇒ `FileStatus.BINARY`;
   - contains `U+FFFD` ⇒ `FileStatus.NOT_UTF8`;
   - larger than 256 KiB ⇒ `TOO_LARGE`.
6. `show_file` checks `content.status is not FileStatus.OK` (handlers.py:1809) and sends a **message**,
   not a document. For a ZIP the user sees `FILE_STATUS_MESSAGES[BINARY]` =
   **«الملف مش نص (مش قابل للعرض).»** (files.py:129), or `NOT_UTF8` / `TOO_LARGE` equivalents.

**Conclusion:** the bot never attempts to send the workspace ZIP. There is **no extension filter** in this
path; the rejection is content-based (`BINARY`/`NOT_UTF8`), because the only workspace read route is a
bounded **text** preview.

### 3.3 Why this is not a bot-only bug: upstream capability

`docs/API_NOTES.md` (lines 64–69) and `docs/MINI_APP.md` §13و (lines 672–700) record the verified provider
contract:

- `GET /app-conversations/{id}/file` → **`application/json` string** (text), not raw bytes; the local path
  is capped at 256 KiB and rejects binary/non-UTF-8.
- `GET /app-conversations/{id}/files` → **array of string** (relative paths).
- `GET /app-conversations/{id}/download` → **ZIP of the conversation trajectory** (`event_*.json` +
  `meta.json`), **not** a workspace file.
- Cloud V1 has **no** `application/octet-stream` / `format: binary` / `multipart` route for workspace
  files (`octet-stream=0`, `format: binary=0`, `multipart=0`).
- The Agent Server has `GET /api/file/download/{path}` (raw bytes), but it requires
  `X-Session-API-Key` — a **full-privilege** session key (same key reaches
  `POST /api/bash/execute_bash_command` and `/api/conversations/{id}/secrets`), documented as **risk B1**.
  The bot does **not** store `session_api_key` by policy.

Therefore **raw workspace ZIP delivery is blocked by provider capability** unless the owner approves a
security decision (store/use the session key or add a trusted proxy). This is the same conclusion already
recorded for the Mini App (`BLOCKED_BY_PROVIDER_CAPABILITY`).

### 3.4 Path B — conversation export ZIP (separate, works within limits)

`bot/handlers.py::export_conversation` (1676) → `client.export_conversation` (openhands_client.py:292) →
`GET /app-conversations/{id}/download` (application/zip), capped at **16 MiB** (`MAX_EXPORT_BYTES`, line 34),
then `send_document(InputFile(BytesIO, filename="conversation-<id>.zip"))` (handlers.py:1719–1721).

- No ZIP-specific filter. `InputFile` with a filename ending in `.zip` is accepted by Telegram.
- Failure modes: export > 16 MiB ⇒ `ResponseTooLargeError` ⇒ explicit «التصدير كبير أوي للتنزيل الآمن.»
  (no document); Telegram/API failure ⇒ `failed_transient`. These are size/transport failures, not a ZIP
  extension rejection.
- Existing test `tests/test_handlers.py::test_export_sends_zip` and
  `tests/test_openhands_client.py::test_export_conversation_returns_bytes` cover this path.

### 3.5 Upload path (if the user means sending a ZIP *to* the bot)

- `bot/app.py:34` `SUPPORTED_ATTACHMENT_FILTER = filters.Document.ALL` → ZIP documents are handled by
  `handle_attachment` (handlers.py:2156).
- `bot/attachments.py:126` `_DENIED_EXTENSIONS` does **not** contain `zip`; `_DENIED_MAGIC` (145) does
  **not** contain `PK\x03\x04`. So there is **no ZIP-specific intake rejection**.
- The relevant limit is **3 MiB per file** (`MAX_ATTACHMENT_BYTES`, attachments.py:105), plus the active
  Option B caps (10 files/batch, 64 MiB aggregate) in the working tree. A ZIP larger than 3 MiB is rejected
  as `REJECTED_SIZE` («الملف أكبر من الحد»), which can look extension-specific because ZIPs are often
  larger than text/code files.

**Verdict for problem 1:** if the ZIP is a **workspace file** (Path A), the confirmed root cause is the
text-only preview path + the upstream binary-download limitation (blocker). If the user means the
**conversation export** (Path B), it works within 16 MiB and fails only on size/transport. If the user
means **uploading** a ZIP, it works up to 3 MiB; larger ZIPs fail on size, not on extension.

---

## 4. Folder organization analysis

| Question | Answer (evidence) |
|---|---|
| Data source | `GET /app-conversations/{id}/files` returns a **flat array of relative path strings** (`openhands_client.py:174`; `docs/API_NOTES.md:64-65`). |
| Does the integration expose directory paths? | Only as **segments inside file paths** (`src/util/helper.js`). No directory entries are returned. |
| Are directory paths preserved or discarded? | Preserved in `FileCache` (full paths), but **discarded in the Telegram presentation**: `files_menu` renders one button per full path, truncated to 60 chars (`keyboards.py:199-216`). |
| Does the bot distinguish files from directories? | **No.** It has no directory objects; every list entry is a file path. |
| Where is the list flattened? | By the **API** (flat array) and by the **bot presentation** (one button per path). Not by the DB (no file table). |
| Can existing data support folders without architecture change? | **Yes.** The Mini App already builds a tree from the same flat list: `bot/web/static/files.js::buildTree` (81–108), `entryRows` (128–145), `breadcrumbs` (147–163), `safeDir` (165–170). No new API/route/table is needed. |
| Nested directories | Implicit in path segments; the bot shows them as long strings, not navigable folders. |
| Empty folders | **Not representable**: the API returns only file paths, so an empty directory has no entry and cannot be shown. |
| Duplicate filenames in different directories | The cache stores full paths, so `show_file` opens the correct file by index; but button labels are truncated full paths (`name[:60]`), so deep duplicates can look identical. A folder view resolves this naturally. |

**Smallest safe design (not implemented):** a pure bot-side tree builder over the flat path list
(mirroring the Mini App’s `buildTree`), with folder buttons that descend into a folder, breadcrumbs/«لأعلى»,
and file buttons that carry the full relative path (or an index into the current folder’s cached listing).
Store the current folder path in the existing per-chat `FileCache`/state; keep callback data ≤ 64 bytes by
using a server-side state token, not the full path. No API, DB, or Mini App change.

---

## 5. Pagination and navigation analysis

| Property | Current behavior (evidence) |
|---|---|
| Page size | **10** (`FILES_PAGE_SIZE`, handlers.py:58). |
| Offset/cursor | Pure **offset slicing**: `start = page * 10`, `files[start:start+10]` (handlers.py:1769-1770). No cursor. |
| Sort order | **None.** The bot paginates the API order as returned; no deterministic sort. The API does not document a stable file order. |
| Callback data | `files:<conversation_id>:<gen>:<page>` and `file:<conversation_id>:<gen>:<index>` (`keyboards.py:205-211`). `_btn` enforces the 64-byte Telegram limit; long conversation IDs (56–64 chars) can exceed it — existing **DEF-010** (see defect register). |
| State persistence/expiration | `FileCache` is an in-memory **LRU**: 16 conversations / 50,000 chars, **no TTL** (`bot/file_cache.py`). “Expired” means evicted or generation mismatch. |
| How “More” advances | `has_more = len(files) > start + 10`; button sends `page + 1` (`handlers.py:1771`, `keyboards.py:210-211`). |
| Can earlier pages be revisited? | Yes via «السابق» (`page - 1`), but each press **re-fetches** the full list and re-caches it with a **new generation**; old file buttons from earlier messages become invalid (`_FILE_MISSING`). |
| Can users jump to a later page? | **No.** Only sequential «المزيد» / «السابق». No page indicator beyond «صفحة N»; no total page count. |
| Direct file/folder search? | **No** bot-side search. (The Mini App also documents no search.) |
| Files added/removed between requests | Every page press calls `FileService.list_files` again (`handlers.py:1752`), so offsets shift; results can duplicate or skip across pages. |
| Duplicate/skipped results | Possible, because the list is re-fetched and sliced by index without a stable snapshot or sort. |
| Inefficiency | For N files, every page request re-fetches the **entire** list (O(N)) and re-caches it. With the observed 534-file conversation (`docs/API_NOTES.md:64`), that is ~54 pages and 54 full-list fetches. |

**Practical alternatives:**

1. **Snapshot + stable sort + Previous/Next (smallest, recommended).** Fetch once per browse session, sort
   by path deterministically, cache the snapshot, and paginate from the snapshot. Add a page indicator and
   a refresh button. This eliminates per-page re-fetching and duplicates/skips within a session. It still
   loads the list once (the API returns the full array anyway), but not repeatedly.
2. **Folder-scoped pagination.** If the API’s `?path=` parameter actually scopes the listing, fetch only
   the current folder’s entries and paginate within it. **Unverified** — the live notes show a flat list;
   the Mini App builds the tree client-side rather than relying on `path`. Needs a live probe.
3. **Previous/Next + direct page selection.** Add page numbers or a “go to page” prompt; callback-size
   constraints require a server-side state token for long conversation IDs.
4. **Filename search.** A text prompt that filters the cached snapshot; no API change, but needs a new
   handler and state.
5. **Cursor-based pagination.** The upstream file API exposes no cursor/page token (only `path`), so a
   true cursor would have to be a client-side snapshot cursor.

**Recommendation:** option 1 plus the folder tree from §4 (folder-scoped pagination if `path` scoping is
confirmed). This is the smallest solution that improves navigation without repeatedly loading the entire
collection.

---

## 6. Cross-problem analysis

- **Problems 2 and 3 share one layer:** the bot’s file-browser presentation/state. A single coherent change
  (folder tree + snapshot pagination + page indicator + server-side state token) addresses folder
  organization, “More” inefficiency, stale-page buttons, duplicate/skipped pages, and the long-ID callback
  risk (DEF-010).
- **Problem 1 is separate:** it is a **delivery capability** issue (text-only preview + no raw-byte route),
  not a navigation issue. It shares the same `FileService`/`list_files` data source but requires a
  different decision (UX message vs. owner-approved binary route).
- **No single root cause fixes all three.** Two workstreams: (A) browser navigation (implementable now),
  (B) binary/ZIP delivery (blocked by provider capability for exact bytes).

---

## 7. Findings table

| ID | Problem | Severity | Confidence | Root cause | Affected bot-side components | Dependencies / constraints | Minimal remediation | Required regression tests |
|---|---|---|---|---|---|---|---|---|
| **F-01** | Workspace ZIP not delivered | **High** | **Confirmed** | `show_file` → `read_preview` → `read_file_text_bounded` (JSON text, 256 KiB) → `classify_text` rejects binary (`BINARY`/`NOT_UTF8`); no raw-byte path. | `handlers.py::show_file` (1780), `files.py::read_preview` (352), `files.py::classify_text` (269), `openhands_client.py::read_file_text_bounded` (204) | Cloud V1 has no binary workspace route; Agent Server `/api/file/download/{path}` needs full-privilege `X-Session-API-Key` (B1), not stored. | Clarify binary UX; raw delivery only after owner security decision. | Workspace ZIP → `BINARY`/clear message, no document; export ZIP → document; retrieval/Telegram failure; cleanup. |
| **F-02** | ZIP upload > 3 MiB fails | Medium | Strongly supported (if user means upload) | 3 MiB per-file cap; **no** ZIP extension/magic denial. | `attachments.py:105` (`MAX_ATTACHMENT_BYTES`), `handlers.py::handle_attachment` (2156), `app.py:34` | Option B adds 10 files/64 MiB aggregate (working tree). | Confirm size/error; explain limit; no ZIP filter to remove. | ZIP 3 MiB exact/over; spaces/Unicode filename; retrieval failure. |
| **F-03** | No folder organization | Medium | Confirmed | Flat API list + flat button presentation; no tree in the bot. | `handlers.py::list_files` (1731), `keyboards.py::files_menu` (199), `file_cache.py` | Data supports a tree (Mini App `files.js::buildTree`, read-only). Empty dirs absent. | Bot-side tree builder + folder navigation + breadcrumbs/up. | Root, nested, empty (absent), duplicates, mixed. |
| **F-04** | “More” inefficiency / unstable pages | Medium | Confirmed | Re-fetch full list on every page; offset slicing; no sort; gen churn; no page indicator/jump/search. | `handlers.py::list_files` (1752-1776), `keyboards.py::files_menu` (199-216), `file_cache.py` | API has no file cursor; `path` scoping unverified. | Snapshot cache + stable sort + Previous/Next + page indicator; optional search; folder-scoped if `path` works. | First/middle/last, empty, boundaries, add/remove, expired/invalid, stable order. |
| **F-05** | Long IDs exceed 64-byte callback data (DEF-010) | Medium | Confirmed (existing) | `files:<cid>:<gen>:<page>` / `file:<cid>:<gen>:<index>` with 56–64-char IDs. | `keyboards.py::_btn` (9-16, 94-95), `files_menu` (199-216) | Telegram 64-byte cap. | Server-side state token instead of full `cid`; or short ID. | 56–64-char IDs across `files:`/`file:`/`deleteok:` etc. |
| **F-06** | Empty folders not shown | Low | Confirmed | API returns only file paths; no directory entries. | `openhands_client.py::list_files` (174), `files.py::list_files` (340) | Upstream contract. | Document limitation; no fix without API support. | Empty-dir case (expect absent). |
| **F-07** | Duplicate names visually ambiguous | Low | Strongly supported | Labels are truncated full paths (`name[:60]`); deep duplicates can collide. | `keyboards.py::files_menu` (205-206) | — | Folder view/breadcrumbs (F-03) resolves ambiguity. | Same basename in two dirs. |
| **F-08** | No file/folder search | Low | Confirmed | No search handler in the bot files UI. | `handlers.py` files UI, `keyboards.py` | Mini App also documents no search. | Optional client-side search over cached snapshot. | Search hit/miss/empty. |
| **F-09** | Upstream raw binary download unavailable | **High** (blocks F-01) | Confirmed (documented) | Cloud V1 has no `octet-stream`/binary/multipart route; Agent Server route needs B1 key. | `openhands_client.py`, `docs/API_NOTES.md:64-69`, `docs/MINI_APP.md:672-700` | Security decision required. | Owner decision: session-key/proxy, or accept text-only UX. | N/A (capability). |

---

## 8. Root causes supported by evidence

1. **ZIP (workspace):** the only read path is a bounded **text** preview; `classify_text` rejects binary
   content, and `show_file` returns a status message instead of calling `send_document`. There is **no**
   ZIP extension/MIME filter and **no** ZIP-specific Telegram restriction. The absence of a raw-byte
   workspace route is an **upstream capability blocker** (Cloud V1), with the Agent Server route blocked by
   the B1 session-key security issue.
2. **Folders:** the API returns a flat path array; the bot renders it as a flat list. The directory
   structure is preserved in the data but discarded in presentation. The Mini App proves a client-side
   tree over the same data works.
3. **Pagination:** page size 10, offset slicing, no stable sort, and a full re-fetch on every page press.
   The cache is re-put with a new generation each time, invalidating older file buttons. There is no page
   indicator, no direct jump, and no search.

---

## 9. Minimal proposed remediation plan (not implemented)

**Workstream A — file browser (bot-only, no blockers):**

1. Add a pure tree builder over the flat relative paths (mirroring `buildTree`), with folder/file rows and
   deterministic sorting.
2. Render folder buttons (descend), breadcrumbs/«لأعلى», and file buttons for the current folder; store the
   current folder path in the per-chat `FileCache`/state.
3. Fetch the list once per browse session; paginate from the cached snapshot (or per-folder snapshot) with
   Previous/Next and a page indicator; add a refresh action.
4. Keep callback data ≤ 64 bytes: use an index/token into server-side state, not the full conversation ID
   or path (also mitigates DEF-010).
5. Optional: filename search over the cached snapshot.

**Workstream B — ZIP/binary delivery:**

1. **Minimal, no security change:** improve the binary-file message to state explicitly that binary/ZIP
   preview is not supported by the provider, and point users to the conversation-export ZIP if that is
   what they need. No raw ZIP delivery.
2. **If raw ZIP delivery is required:** owner security decision to use the Agent Server
   `/api/file/download/{path}` with a scoped key/proxy, documenting the B1 risk. Do **not** implement
   without explicit approval.
3. **If the user meant upload:** confirm the ZIP size and the 3 MiB limit; no ZIP filter needs removal.

**Suggested implementation order:** A (folders + stable pagination) → B1 (binary UX/message) → B2 only after
an owner decision. F-06 (empty folders) remains a documented limitation.

---

## 10. Required regression tests

**ZIP delivery**

- Workspace `.zip` (binary) → `FileStatus.BINARY`/clear message, **no** `send_document`.
- Conversation export ZIP → exactly one document with a `.zip` filename (existing behavior).
- ZIP filename with spaces/Unicode (upload path) → accepted/sanitized correctly.
- ZIP at 3 MiB exact / 3 MiB + 1 (upload) → accepted / `REJECTED_SIZE`.
- Retrieval failure (`ApiError`) and Telegram `send_document` failure → explicit outcome, no false success.
- No temp-file leak after success/failure (current path is in-memory; assert no staging artifact).

**Folder browsing**

- Root listing; nested directories; empty directory (expect absent/limited); duplicate filenames in
  different directories; mixed files/folders; breadcrumbs/up; invalid folder (fail closed).

**Pagination**

- First, middle, final pages; Previous/Next; empty result; exact page boundaries; files added/removed
  between requests; expired/invalid generation callbacks; stable ordering with no duplicates/skips;
  long conversation IDs (DEF-010) stay within 64-byte callback data.

**Existing tests actually executed in this audit (read-only):**

```
python3 -m pytest -q tests/test_files_service.py \
  tests/test_handlers.py::test_list_files_caches_and_paginates \
  tests/test_handlers.py::test_show_file_sends_document \
  tests/test_handlers.py::test_export_sends_zip \
  tests/test_keyboards.py::test_files_menu_uses_index_not_path \
  tests/test_keyboards.py::test_files_menu_pagination \
  tests/test_file_cache.py \
  tests/test_openhands_client.py::test_list_files \
  tests/test_openhands_client.py::test_read_file_uses_file_path_param \
  tests/test_openhands_client.py::test_export_conversation_returns_bytes \
  tests/test_wp03_handler_outcome_and_send_guards.py::test_show_file_document_delivery_failure_is_transient \
  tests/test_wp03_handler_outcome_and_send_guards.py::test_show_file_success_is_ignored
```

Result: **86 passed, 0 failed** (exit 0, 0.74 s). These confirm the existing text-preview, binary-rejection,
export-ZIP, cache, and basic pagination behavior. They do **not** cover workspace ZIP delivery (unsupported),
folder navigation, or boundary pagination — hence the proposed tests above.

---

## 11. Dependencies and unresolved questions

- **Which ZIP does the user mean?** Workspace file (Path A) vs. conversation export (Path B) vs. upload.
  The exact user-facing error message/screenshot would settle it. Evidence strongly points to Path A.
- **Does `GET /files?path=` scope the listing?** The client supports `path`, but the bot never passes it and
  the live notes show a flat array. Needs a live probe before relying on folder-scoped pagination.
- **Are empty directories returned by the API?** Current evidence says no (only file paths).
- **Is a 3 MiB cap acceptable for ZIP uploads?** Product decision; no ZIP-specific filter exists.
- **Will the owner approve a raw-byte download route?** Requires the Agent Server session key/proxy and a
  B1 security decision; not a bot-only change.
- **Shared backend dependency:** the Mini App uses the same `FileService` (`bot/web/services.py:1004-1031`)
  and builds its tree client-side (`bot/web/static/files.js`). Any future change to `FileService` affects
  both; this diagnosis changed neither.

---

## 12. Files inspected (read-only)

**Bot code**

- `bot/handlers.py` — `FILES_PAGE_SIZE` (58), `_attachment_service` (1960), `export_conversation` (1676),
  `list_files` (1731), `show_file` (1780), `handle_attachment` (2156), `_file_cache` (185),
  `_files_service` (208), `_attachment_*` helpers (1919-1956).
- `bot/files.py` — `FileStatus`/`FileListing`/`FileContent` (39-68), `is_safe_workspace_path` (75),
  `classify_text` (269), `FileService` (291), `list_files` (340), `read_preview` (352),
  `FILE_STATUS_MESSAGES` (124-132).
- `bot/openhands_client.py` — constants (28-34), `list_files` (174), `read_file` (182),
  `read_file_text` (189), `read_file_text_bounded` (204), `export_conversation` (292).
- `bot/keyboards.py` — `_btn` (9-16, 94-95), `conversation_actions` (126), `files_menu` (199-216).
- `bot/file_cache.py` — `FileCache` LRU (16 entries / 50k chars, no TTL).
- `bot/attachments.py` — `MAX_ATTACHMENT_BYTES` (105), `_DENIED_EXTENSIONS` (126), `_DENIED_MAGIC` (145),
  `classify_incoming_file` (464), `StagingStore` (491+).
- `bot/app.py` — `SUPPORTED_ATTACHMENT_FILTER` (34), handler registration (120-170).
- `bot/features.py` — files feature enabled (`DEFERRED_FEATURES_HIDDEN = False`).
- `bot/web/services.py` — `MiniAppService._files` / `list_files` / `read_preview` (1004-1031), read-only
  shared-backend dependency.
- `bot/web/static/files.js` — `buildTree`/`entryRows`/`breadcrumbs`/`safeDir` (81-170), read-only Mini App
  pattern.

**Docs / tests**

- `docs/API_NOTES.md` (64-69), `docs/MINI_APP.md` §13و (672-700),
  `docs/reviews/OHB2-PLAN03-ADMINISTRATIVE-CLOSURE-REPORT.md` (hierarchy evidence),
  `docs/audits/OHB2-COMPLETE-DEFECT-REGISTER.md` (DEF-010).
- `tests/test_files_service.py`, `tests/test_handlers.py`, `tests/test_keyboards.py`,
  `tests/test_file_cache.py`, `tests/test_openhands_client.py`,
  `tests/test_wp03_handler_outcome_and_send_guards.py`, `tests/test_files_bounded.py`,
  `tests/test_real_http_file_download.py`, `tests/test_miniapp_files.py`.

---

## 13. Confirmation

- **No production code, tests, Mini App files, configuration, or user-facing behavior were changed.**
- The only artifact created by this task is this report.
- No commit, push, PR, merge, deployment, or Autopush activation occurred.
- No destructive Git operations; all pre-existing working-tree changes were preserved.

---

## 14. Final status

# `DIAGNOSIS_COMPLETE_WITH_BLOCKERS`

The diagnosis is complete and the folder/pagination workstream is implementation-ready. The ZIP-delivery
workstream is complete as a diagnosis but **blocked for raw-byte delivery** by the upstream OpenHands Cloud
capability (no binary workspace-file route) and the Agent Server session-key security constraint (B1).
`DEF-011` and the broader project state are unchanged; no implementation is started by this task.
