# Candidate Manifest — OHB2 Bot File Browser & Binary UX

**Candidate:** `OHB2-BOT-FILE-BROWSER-AND-BINARY-UX-IMPLEMENTATION`
**Base revision:** `30dfa0d6432cdb8f7787edde38f48fb482b6ced6`
**Application order:** base → `candidate.patch` (no prerequisite patches)
**Candidate file count:** 8

---

## 1. Candidate patch identity

| Field | Value |
|---|---|
| File | `candidate.patch` |
| SHA-256 | `0b29a107d8acfb3e607089d7590c33076ece3864ed83c924e8dbeefb017d8aa2` |
| Size | 75914 bytes |
| Format | `git diff` against `30dfa0d`, applies with `git apply` |
| Changed files | 8 |
| Insertions / deletions | 1562 / 9 |

The patch was generated from a clean base clone after copying the current-task files and restoring the
base `_attachment_service` function, so it contains **only** current-task hunks.

## 2. Candidate files and hashes

| Path | SHA-256 | Bytes | Change |
|---|---|---|---|
| `bot/file_browser.py` | `428d977e5a0bc1606e285f1094659489b46d4944a4cf4ee32d85b0d5129ac5c8` | 10168 | New: directory tree, `BrowserState`, bounded `BrowserCache`, pagination helpers, short tokens. |
| `bot/handlers.py` | `1603e6fc55b69a72247dc8856f73caadece99ef2aae26aaca80cc2e6961aa050` | 197783 | New `browse_*` handlers, binary/too-large/NOT_UTF8 messages, `files_cb` wiring, deletion cache invalidation, `MAX_PREVIEW_BYTES` import. |
| `bot/keyboards.py` | `aedc25cf52f559fc5299b68954d61d47b4ba87713fd49f7a992eeec8bbfa6b77` | 13710 | `files_cb` on `conversation_actions`, `files_only_menu`, `browser_menu`. |
| `bot/app.py` | `3d606b4ef5d5994c2d6a025917f46ea282f5307a950bb3a304d6b1c998a9a438` | 25984 | Register `fbo/fbd/fbp/fbu/fbr/fbf/fbx/fbb` handlers. |
| `tests/test_file_browser.py` | `92c1684e26efef313714ab65928e97ea258fb79f252b8368c1d60af2f9c67b0a` | 5185 | 16 pure tree/pagination/cache tests. |
| `tests/test_bot_file_browser.py` | `1010e481a62024e6ae7e83903255ae0db59482c3f539e2659b71b2db9cd6099c` | 16115 | 20 handler/binary/DEF-010 tests. |
| `tests/test_b06_file_routing.py` | `8ed216317d28e37bca5dab3947b3fa05c4abce4762d642b4a5e35efae319b3e1` | 13679 | Update legacy binary/too-large assertions to the new bot messages. |
| `docs/audits/OHB2-BOT-FILE-BROWSER-AND-BINARY-UX-IMPLEMENTATION-REPORT.md` | `c7ced294834a013db1108fe962d7372184e028952d6030d739dc094b16705c9c` | 15361 | Implementation report. |

`CANDIDATE-SHA256SUMS` is the machine-readable version of this table (repo-root-relative paths).

## 3. Diff statistics

```
 bot/app.py                                                               |  10 ++++
 bot/file_browser.py                                                      | 239 ++++++++++++++++++++++++++++++++
 bot/handlers.py                                                          | 376 ++++++++++++++++++++++++++++++++---
 bot/keyboards.py                                                         |  63 ++++++++++++++-
 docs/audits/OHB2-BOT-FILE-BROWSER-AND-BINARY-UX-IMPLEMENTATION-REPORT.md | 247 ++++++++++++++++++++++++++++++++
 tests/test_b06_file_routing.py                                           |   8 ++-
 tests/test_bot_file_browser.py                                           | 473 ++++++++++++++++++++++++++++++++++++++
 tests/test_file_browser.py                                               | 155 +++++++++++++++++++++++++++
 8 files changed, 1562 insertions(+), 9 deletions(-)
```

Per-file `git diff --numstat` in the candidate:

```
10      0       bot/app.py
239     0       bot/file_browser.py
370     6       bot/handlers.py
62      1       bot/keyboards.py
247     0       docs/audits/OHB2-BOT-FILE-BROWSER-AND-BINARY-UX-IMPLEMENTATION-REPORT.md
6       2       tests/test_b06_file_routing.py
473     0       tests/test_bot_file_browser.py
155     0       tests/test_file_browser.py
```

## 4. Reconstruction verification (packaging check — not independent review)

Performed in `/tmp/ohb2-handoff-verify`, a clean clone of `30dfa0d`:

| Step | Command | Result |
|---|---|---|
| Verify base | `git rev-parse HEAD` | `30dfa0d6432cdb8f7787edde38f48fb482b6ced6` |
| Apply check | `git apply --check candidate.patch` | OK |
| Apply | `git apply candidate.patch` | OK |
| Candidate hashes | `sha256sum -c CANDIDATE-SHA256SUMS` | **8/8 OK** |
| Changed-file scope | `git status --short` | Exactly the 8 candidate files; no excluded file |
| Focused tests | `pytest -q tests/test_file_browser.py tests/test_bot_file_browser.py tests/test_b06_file_routing.py` | **61 passed**, exit 0 |
| Full suite | `pytest -q` | **3486 passed**, 0 failed, exit 0 |
| Lint | `pyflakes bot/ tests/` | exit 0 |

The implementation workspace's full suite reports **3503 passed** because it additionally contains the
excluded DEF-011-A Option B test file and the F-03/T-5 test changes. The reconstructed candidate does not
need them: base + candidate alone is green.

## 5. Overlap with DEF-011-A Option B in `bot/handlers.py`

The implementation workspace `bot/handlers.py` contains an unrelated DEF-011-A Option B change in
`_attachment_service`. It was excluded at hunk level. The candidate patch has 11 `bot/handlers.py` hunks;
the full workspace diff has 12. The dropped hunk is exactly:

```diff
@@ -1958,12 +2322,27 @@ def _attachment_file_id(message) -> str | None:


 def _attachment_service(context: ContextTypes.DEFAULT_TYPE):
-    from .attachments import AttachmentService, StagingStore
+    from .attachments import (
+        MAX_ITEMS_PER_BATCH,
+        MAX_STAGING_TOTAL_BYTES,
+        AttachmentService,
+        StagingStore,
+    )

     db = context.bot_data["db"]
     store = context.bot_data.get("attachment_store")
     if store is None:
-        store = StagingStore(db, context.bot_data["config"].db_path)
+        # OHB2-WP07-DEF011-A (Option B, owner-approved 2026-11-21): enforce the
+        # per-batch file cap (10) and the global staged-byte cap (64 MiB) in the
+        # single production store. `StagingStore` defaults stay `None`, so no
+        # other caller gets implicit enforcement; the 3 MiB per-file cap remains
+        # always on. Preserved orphan files still count toward the global cap.
+        store = StagingStore(
+            db,
+            context.bot_data["config"].db_path,
+            max_items_per_batch=MAX_ITEMS_PER_BATCH,
+            max_total_bytes=MAX_STAGING_TOTAL_BYTES,
+        )
         context.bot_data["attachment_store"] = store
     return AttachmentService(db, store, context.bot_data["client"], _identity_cache(context))
```

**Proof of isolation:** `diff -u` between the reconstructed candidate `bot/handlers.py` and the workspace
`bot/handlers.py` contains **only** this block. No current-task hunk is missing or altered.

Workspace `bot/handlers.py`:
`f1276068fb8ff85a4f0aaea0c00ee399626dc1671b73a5552630413dd016ec6a` (198410 bytes).

Candidate `bot/handlers.py`:
`1603e6fc55b69a72247dc8856f73caadece99ef2aae26aaca80cc2e6961aa050` (197783 bytes).

## 6. Intentionally excluded changes

| Path / area | Classification | Why excluded |
|---|---|---|
| `bot/attachments.py` | DEF-011-A Option B | Unrelated pre-existing work; no dependency of the file-browser candidate. |
| `bot/handlers.py` `_attachment_service` hunk | DEF-011-A Option B | Unrelated; excluded at hunk level (proof above). |
| `tests/test_def011_a_option_b_limits.py` | DEF-011-A | Option B tests; not needed by the candidate. |
| `docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md` | F-03 | Documentation correction; unrelated. |
| `tests/test_doc_code_parity.py` | F-03 / T-5 | Documentation-parity and T-5 changes; unrelated. |
| DEF-011-A and F-03 audit/review reports | DEF-011-A / F-03 | Evidence for other tasks; not reconstruction prerequisites. |
| `DEF011-A-OPTION-B-REVIEW-HANDOFF.zip` | DEF-011-A | Prior handoff artifact; unrelated. |
| Existing `docs/reviews/handoff/` contents | DEF-011-A | Prior handoff package; unrelated. |
| Ignored caches / `.openhands/` | Environment | Not source; not packaged. |

No F-03 or T-5 change is a dependency: the candidate was reconstructed and tested without them.

## 7. Required dependencies supplied by the base revision

The candidate relies on existing base modules and does not patch them:

- `bot/files.py` — `FileService`, `FileStatus`, `MAX_PREVIEW_BYTES`, `is_safe_workspace_path`.
- `bot/file_cache.py` — legacy file cache (kept for old messages).
- `bot/openhands_client.py` — bounded reads / conversation client.
- `bot/features.py` — `is_hidden("files")` gate.
- `bot/db.py` — deletion witness / database access.
- `bot/keyboards.py`, `bot/handlers.py`, `bot/app.py` — modified only by the candidate hunks.
- `telegram` (python-telegram-bot) and the repository's existing dependencies.

No new external dependency is introduced.

## 8. Scope and security notes

- The candidate does not add a raw workspace binary/ZIP download route.
- It does not call the Agent Server or use an `X-Session-API-Key`.
- It does not add a new network endpoint or privileged proxy.
- It does not modify `bot/web/` (Mini App) files.
- It preserves the existing `FileService.read_preview` authorization, allowlist, and 256 KiB limit.
- Callback sizes in the new `fbo/fbd/fbp/fbu/fbr/fbf/fbx/fbb` family are ≤64 bytes even for a 64-character
  conversation ID (covered by tests).
- Cache lifecycle: bounded snapshot (16 entries / 50,000 chars / 30-minute TTL), token LRU 128, refresh
  replaces the snapshot, deletion invalidates file/browser caches.

## 9. Historical results are not independent verification

The test counts above were produced during implementation and packaging. The external reviewer must rerun
them independently and report their own results. No independent review is claimed by this package.
