# OHB2 Plan 08 (`OHB2-PLAN-18-ATTACHMENT-POLICY-AND-MEDIA-SCOPE`) — Investigation & Policy-Decision Report

- **Task ID:** `OHB2-PLAN-17-18-COMBINED-EXECUTION-01` (Plan 08 portion)
- **Plan ID:** `OHB2-PLAN-18-ATTACHMENT-POLICY-AND-MEDIA-SCOPE`
- **Date (UTC):** 2026-11-16
- **Type:** Source investigation, policy traceability audit, and owner-decision preparation ONLY. Zero runtime code, quota defaults, media filters, schema, dependencies, or deployment changes.
- **Repository Root / VCS State:** `/app/applet` (`.git` directory is **absent** in this container, `git` exits `128`).

---

## 1. Executive Verdicts (Kept Separate)

| Workstream | Scope | Verdict |
| --- | --- | --- |
| **`ATT-01`** | Attachment aggregate quota investigation & policy reconciliation (`D-12` / Plan 01 Option A) | **`COMPLETE` (Investigation + Sync Only; `D-12` Scope 2 Remains `UNRESOLVED` / `OWNER_DECISION_REQUIRED`)** |
| **`ATT-02`** | Telegram supported-media scope investigation, matrix, `D-31` check, & owner-decision brief | **`COMPLETE` (Investigation + Decision Prep Only; `Document`-only active; no media expansion implemented)** |

---

## 2. `ATT-01` — Attachment Aggregate Quota Investigation

### 2.1 Configuration, Constants, and Active Defaults (`[F]`)
Verified directly from `bot/attachments.py`, `bot/config.py`, `.env.example`, and `bot/handlers.py`:

| Parameter | Location | Defined Value | Default Runtime State | Scope / Authority |
| --- | --- | --- | --- | --- |
| `MAX_ATTACHMENT_BYTES` | `bot/attachments.py:100` | `3 * 1024 * 1024` (3 MiB) | **ACTIVE** (`StagingStore.__init__` `max_bytes = MAX_ATTACHMENT_BYTES`) | Per-file resource/memory safety cap (independent of `D-12`, marked PROVISIONAL) |
| `MAX_ITEMS_PER_BATCH` | `bot/attachments.py:106` | `10` (reference constant only) | **DISABLED** (`StagingStore.__init__` `max_items_per_batch: int \| None = None`) | Provisional `D-12` reference value; not enforced |
| `MAX_STAGING_TOTAL_BYTES` | `bot/attachments.py:107` | `64 * 1024 * 1024` (64 MiB reference constant only) | **DISABLED** (`StagingStore.__init__` `max_total_bytes: int \| None = None`) | Provisional `D-12` reference value; not enforced |
| `max_bytes_per_batch` | `bot/attachments.py:500` | No numeric constant | **DISABLED** (`StagingStore.__init__` `max_bytes_per_batch: int \| None = None`) | Designed hook; no default constant |
| `bot/config.py` / `.env.example` | `bot/config.py:1–342`, `.env.example:1–20` | — | **No quota env keys exist** | No implicit env/config override path (`bot/attachments.py:53–55, 504`) |
| Production wiring | `bot/handlers.py:1691–1699` | `StagingStore(db, cfg.db_path)` | **`quota_enabled == False`** | Aggregate quotas are never passed in bot runtime |

### 2.2 Enforcement, Accounting, Partial Writes, Expiry, and Restart Behavior (`[F]`)
1. **Enforcement gates (`bot/attachments.py:572–760`):**
   - `StagingStore.quota_block(batch_id, extra_items=1)` returns `None` immediately when `_max_items_per_batch is None`. If explicitly provided (`> 0`), counts `count + extra_items > _max_items_per_batch` and returns `"batch_items"` → `StageResult(StageStatus.REJECTED_QUOTA)`.
   - `StagingStore.byte_quota_block(batch_id)` returns `None` immediately when `_max_bytes_per_batch is None`. If explicitly provided, checks current batch active bytes `> _max_bytes_per_batch` → `StageStatus.REJECTED_QUOTA`.
   - `StagingStore._effective_cap(batch_id)` (`bot/attachments.py:598–609`) takes `min([_max_bytes, ...])` subtracting `staging_total_bytes(_root)` if `_max_total_bytes is not None` and batch active bytes if `_max_bytes_per_batch is not None`. With default `None` aggregate quotas, `cap == 3145728` (3 MiB).
   - If `_effective_cap <= 0`, `store()` fails closed before `add_attachment_item` / `_write_to_path` with `REJECTED_QUOTA` (`bot/attachments.py:732–734`). Note: in `AttachmentService.accept()` (`bot/attachments.py:920–966`), the `pending` item row is inserted atomically with `durable_intent_recorded` (`row_created=True`) *before* download and `store()` — so if `store()` later rejects on size/type/quota, the user receives `ATTACHMENT_QUOTA_TEXT` / `ATTACHMENT_TOO_LARGE_TEXT` (`bot/handlers.py:1951–1960`) while the unstored `pending` item awaits A4 cleanup (`AttachmentReaper`).
2. **Disk-backed accounting (`bot/attachments.py:296–319, 549–570`):**
   - `StagingStore._batch_active_files(batch_id)` queries `db.list_attachment_items(batch_id)` and stats **actual regular files** on disk (`os.lstat(root / token)` + `_stat.S_ISREG`), ignoring `rejected`/`expired`/`reaped` items whose files are absent and ignoring symlinks/directories.
   - `staging_total_bytes(root)` iterates `root.iterdir()` using `os.lstat` and sums `st_size` of regular files only (missing root ⇒ `0`; read/permission error propagates ⇒ fail-closed `WRITE_FAILED`).
3. **Partial-write & streaming safety:**
   - Download streaming (`bot/handlers.py:1703–1864`) enforces `MAX_CONCURRENT_DOWNLOADS = 4` (`asyncio.Semaphore`) and a hard `max_bytes` (3 MiB) byte-counter across HTTPX `aiter_raw()` and `_read_local_capped()` (`_DOWNLOAD_CHUNK_BYTES = 64 KiB`), raising `AttachmentTooLargeError` immediately on overflow. `File.download_to_memory` is explicitly rejected (`StagingError`, `bot/attachments.py:45–48`, `bot/handlers.py:1827–1833`).
   - Disk write (`_write_to_path`, `bot/attachments.py:612–644`) uses `O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW` (`0600`), unlinks partial files via `_safe_unlink(path)` on any error or `_TooLargeError`, and invokes `db.try_mark_attachment_item_stored` (`bot/db.py:1224–1281` `BEGIN IMMEDIATE` CAS checking item `pending` AND parent batch `pending`) **only** after write + `_is_denied_magic` validation succeed. If CAS fails, the file is unlinked (`bot/attachments.py:797, 803`).
4. **Concurrency gap if aggregate quotas are enabled in future (`[F]` + `[I]`):**
   - `bot/app.py:86` enables `concurrent_updates(True)` and `bot/handlers.py:1703` permits up to `4` concurrent downloads.
   - Because `StagingStore._batch_active_files` and `staging_total_bytes` measure files **already written on disk** at step `(0d)/(0f)/(0g)` before `_write_to_path` runs, **there is no reservation lock or in-flight byte reservation across concurrent calls**. Under default `None` quotas, each call enforces the 3 MiB per-file ceiling independently without racing; however, **if aggregate quotas were enabled without an in-process reservation lock**, concurrent uploads (`<= 4`) could both pass `quota_block`/`_effective_cap` before either file exists on disk and exceed `max_items_per_batch` or `max_total_bytes`.
5. **Expiry & restart behavior:**
   - `AttachmentReaper.sweep()` (`bot/app.py:238`) runs on startup and periodically via `OpportunisticSweeper` (`Watcher`, min interval `60.0s`), marking expired `pending` batches (`> 15 min` from `T0`) as `expired` DB-first and deleting terminal staging files. `StagingStore` has no cached quota counter in memory, so restart re-derives exact byte usage from disk + SQLite.
6. **Current effective storage bounds:**
   - With aggregate quotas `None`, individual files are strictly bounded to `(0, 3 MiB]` (`> 0` after write, `bot/attachments.py:771`), download concurrency to `4`, and staging retention to 15-minute `ATTACHMENT_BATCH_TTL` + opportunistic/startup reaping. No hard cap limits total items per batch or aggregate bytes in `attachment_staging` during the 15-minute active window (or idle periods between `Watcher` ticks/restarts).

### 2.3 Traceability of `None` Default vs `D-12` (`[F]`)
- **Historical trace:** During `OHB2-REPAIR-PLAN-01` (`FIX-03`), `StagingStore` implemented aggregate quota enforcement with `10 items/batch` and `64 MiB` total. During `OHB2-REPAIR-PLAN-01-REVIEW-FINDINGS` (`FIX-R01` + `FIX-R05`, recorded in `.agent/PROGRESS.md:2758–2816` and `bot/attachments.py:50–70`), those aggregate quotas were intentionally **changed to default `None` (disabled)** under **Plan 01 Option A** so that unapproved `D-12` product policy would not be implicitly enforced without owner approval, while retaining the 3 MiB per-file safeguard as an independent resource-safety ceiling.
- **Authoritative Two-Scope Reconciliation (`docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md` `§13.3` L2500–2504, `§13.5` L2533):**
  - **Scope 1 (Local Plan 01 Resource Guard — implemented under Option A):** 3 MiB per-file ceiling active; `MAX_ITEMS_PER_BATCH`, `MAX_STAGING_TOTAL_BYTES`, and `max_bytes_per_batch` remain `None` (disabled by default, no env toggle).
  - **Scope 2 (Permanent `D-12` Product Quota Policy — `UNRESOLVED` / `OWNER_DECISION_REQUIRED`):** Remains `غير محسوم` in `### D-12` (`§5` L794–820, `§9` L2081–2083).
- **Supporting docs & tests checked:**
  - `tests/test_repair_plan_01_resource_staging.py:155–227` verifies both explicit quota rejection and `test_quota_defaults_are_disabled` (`None` defaults, `quota_enabled is False`).
  - `tests/test_repair_plan_01_review_findings.py:205–215` asserts `### D-12` remains `غير محسوم` and `bot/attachments.py` preserves `جدول الحدود` with `مفعّل` / `معطّل` / `مؤقّت`.
  - `docs/decisions/OHB2-OWNER-DECISION-PLAN08-MANUAL-ATTACHMENT-TRANSFER.md:428–439` accurately documents `MAX_ITEMS_PER_BATCH = 10` and `MAX_STAGING_TOTAL_BYTES = 64 MiB` as disabled (`None`, PROVISIONAL / NOT APPROVED). No contradiction found in `README.md` or `docs/OPERATIONS_RUNBOOK.md`.

### 2.4 Owner-Decision Options for `ATT-01` (`RECOMMENDATION — NOT OWNER-APPROVED`)
- **Option A:** Keep `D-12` Scope 2 open (continue Plan 01 Option A: 3 MiB per-file cap only, aggregate quotas `None`/disabled) while P0 remote upload remains `BLOCKED`. Zero code change; preserves existing local testing/UX; leaves aggregate batch count/bytes unbounded during the 15-min window (mitigated only by 3 MiB/file + `MAX_CONCURRENT_DOWNLOADS=4` + A4 reaper).
- **Option B:** Explicitly resolve **`D-12`** and authorize enabling conservative aggregate staging quotas (e.g., `MAX_ITEMS_PER_BATCH = 10`, `MAX_STAGING_TOTAL_BYTES = 64 MiB`, and explicit `max_bytes_per_batch` policy—whether single-full-file 3 MiB or multi-file e.g. 30 MiB) passed explicitly by approved code + adding a concurrency reservation lock in `StagingStore.store` so concurrent downloads cannot overshoot. Protects bounded disk on small free-tier hosts.
- **Option C:** Defer `D-12` permanent quota numbers until P0 remote upload (`B1`/`B2`) or hosting qualification (`HOST-01`) unblocks, while optionally deciding later whether local-only staging needs an explicit cap.
- **`RECOMMENDATION — NOT OWNER-APPROVED`:** **Option A** right now (preserve current disabled aggregate defaults while hosting `HOST-01` and remote upload `B1`/`B2` remain `BLOCKED`), transitioning to **Option B** (explicit `D-12` policy + reservation lock) before any future activation of `Plan 02` / MT-2 / production hosting.

---

## 3. `ATT-02` — Telegram Supported-Media Scope Investigation

### 3.1 Runtime Routing & Filter Topology (`[F]`)
- **Polling boundary (`bot/polling.py:37`):** `ALLOWED_UPDATES = ("message", "callback_query")` — non-message/non-callback updates (e.g., `edited_message`, `channel_post`, `message_reaction`) are not fetched from Telegram.
- **Intake switch (`bot/config.py:43, 315–317`; `bot/handlers.py:1884–1892`):** `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` defaults to `True`. When `False`, `handle_attachment` replies honestly (`ATTACHMENT_INTAKE_DISABLED_TEXT`), marks `explicitly_ignored`, and performs zero `get_file`/download/DB item creation/OpenHands calls, while `UNSUPPORTED_ATTACHMENT_FILTER` continues rejecting unsupported media cleanly.
- **PTB handler filters (`bot/app.py:34–45, 153–171`):**
  - `SUPPORTED_ATTACHMENT_FILTER = filters.Document.ALL` → `handlers.handle_attachment`
  - `UNSUPPORTED_ATTACHMENT_FILTER = (filters.PHOTO | filters.AUDIO | filters.VIDEO | filters.VOICE | filters.VIDEO_NOTE | filters.ANIMATION | filters.Sticker.ALL | filters.LIVE_PHOTO | filters.PAID_MEDIA) & ~filters.Document.ALL` → `handlers.handle_unsupported_attachment`
  - Mutual exclusion `& ~filters.Document.ALL` prevents duplicate execution in PTB group `0` (`bot/app.py:31–33`, verified in `tests/test_unsupported_attachment_rejection.py:316–320`).
  - Unmatched message updates fall through to `TypeHandler(Update, handlers.handle_unmatched_update)` (`bot/app.py:171`, `bot/handlers.py:2015–2049`), recording `explicitly_ignored` with zero reply/download/storage.

### 3.2 Complete Telegram Media & Message-Type Matrix (`[F]`, `[U]` noted for live PTB lib)
*(Note: `python-telegram-bot[all]==22.8` is pinned in `requirements.txt`, `[F]`; the `telegram` package is absent in this container's Python `3.10.12`, so live introspection of additional `ptb==22.8` `Message` fields beyond `bot/app.py` is `[U]` / `BLOCKED` here.)*

| Telegram Update / Media Type | PTB Filter / Attribute | Current Bot Behavior | Side Effects | Traceable Policy / Status |
| --- | --- | --- | --- | --- |
| **`Document`** (uncompressed file upload) | `filters.Document.ALL` → `handle_attachment` | **ACCEPTED locally** if owner private chat + active `route` + authorized/non-tombstoned chat + allowed ext/magic + `(0, 3 MiB]` | Creates SQLite batch/item + opaque `0600` file in `attachment_staging` (`15 min` `T0`); replies `ATTACHMENT_ACCEPTED_TEXT`; **NOT sent to OpenHands** | `D-09-R2` (`A0–A4` local only); **ACTIVE** |
| **`Photo`** (compressed image) | `filters.PHOTO` → `handle_unsupported_attachment` | **REJECTED safely** (`UNSUPPORTED_ATTACHMENT_TEXT`) | Zero `get_file`, zero storage, zero OpenHands call; outcome `explicitly_ignored` | Intentional exclusion; verified in `tests/test_unsupported_attachment_rejection.py` |
| **`Audio`** | `filters.AUDIO` → `handle_unsupported_attachment` | **REJECTED safely** | Zero side effects; `explicitly_ignored` | Intentional exclusion |
| **`Video`** | `filters.VIDEO` → `handle_unsupported_attachment` | **REJECTED safely** | Zero side effects; `explicitly_ignored` | Intentional exclusion |
| **`Voice`** | `filters.VOICE` → `handle_unsupported_attachment` | **REJECTED safely** | Zero side effects; `explicitly_ignored` | Intentional exclusion |
| **`VideoNote`** | `filters.VIDEO_NOTE` → `handle_unsupported_attachment` | **REJECTED safely** | Zero side effects; `explicitly_ignored` | Intentional exclusion |
| **`Animation`** (GIF) | `filters.ANIMATION` → `handle_unsupported_attachment` | **REJECTED safely** | Zero side effects; `explicitly_ignored` | Intentional exclusion |
| **`Sticker`** | `filters.Sticker.ALL` → `handle_unsupported_attachment` | **REJECTED safely** | Zero side effects; `explicitly_ignored` | Intentional exclusion |
| **`LivePhoto`** (`ptb 22.8` filter) | `filters.LIVE_PHOTO` → `handle_unsupported_attachment` | **REJECTED safely** | Zero side effects; `explicitly_ignored` | Intentional exclusion |
| **`PaidMedia`** (`ptb 22.8` filter) | `filters.PAID_MEDIA` → `handle_unsupported_attachment` | **REJECTED safely** | Zero side effects; `explicitly_ignored` | Intentional exclusion |
| **Combined `Document` + unsupported media** | `SUPPORTED_ATTACHMENT_FILTER` matches first; `& ~Document.ALL` excludes unsupported handler | **Processed ONCE as `Document`** | Single `Document` staging flow; no duplicate reply | Verified in `tests/test_unsupported_attachment_rejection.py:316–320` |
| **`Document` with `caption`** | `filters.Document.ALL` (`filters.TEXT` does NOT match media captions) | Document staged; **`message.caption` silently ignored** | Caption is **neither** stored/used as A3 accompanying text **nor** rejected | **`D-31` (`OWNER-APPROVED` 2026-11-13):** A3 accepts standalone text only; captions deferred |
| **Media Group (`media_group_id`)** | Each Telegram update arrives separately (`Document` items handled one-by-one; `Photo`/`Video` rejected one-by-one) | `media_group_id` **not inspected/grouped**; each `Document` goes through individual A2 `NEW`/`APPEND` | Multiple replies (one per file) | **`D-31` (`OWNER-APPROVED` 2026-11-13):** media groups & caption aggregation deferred |
| **Non-media structured `message` types** (`Location`, `Venue`, `Contact`, `Poll`, `Dice`, `Game`, `Invoice`, `Checklist`, service messages, etc.) | No specific `MessageHandler`; falls to `TypeHandler(Update, handle_unmatched_update)` | **Silently ignored** (no user reply, no download, no storage) | Records `explicitly_ignored` for polling offset progress | Unmatched fallback (`bot/app.py:171`, `bot/handlers.py:2015`) |
| **`edited_message` / other non-message updates** | Excluded by `ALLOWED_UPDATES = ("message", "callback_query")` | **Not fetched** by poller | None | `bot/polling.py:37` |

### 3.3 Additional Code & Documentation Observations (`[F]`)
- **Latent helper attributes (not modified):** `bot/handlers.py:1662–1688` (`_attachment_declared_size` and `_attachment_file_id`) still inspect `photo`, `audio`, `video`, `voice`, `video_note`, and `animation` attributes after checking `document`, even though `bot/app.py:34` only routes `filters.Document.ALL` to `handle_attachment`. Because `handle_attachment` checks `file_id` from `document` first, those branches are dead unless a future filter change routes non-Document media into `handle_attachment` (and `_attachment_display_name` at `bot/handlers.py:1650–1659` returns `None` for non-documents).
- **Doc/UI consistency (`[F]`):**
  - `README.md:18–28` accurately documents `Document`-only local staging (`15 دقيقة`, not delivered to OpenHands) and safe rejection of all 9 unsupported media types.
  - `bot/handlers.py:729–742` (`HELP_TEXT`) lists slash commands only and makes zero unsupported media claims.
  - `bot/handlers.py:1603–1606` (`UNSUPPORTED_ATTACHMENT_TEXT`) accurately directs the user to send text or send the file as a `Document`.
- **Owner-decision traceability (`[F]`):**
  - **`D-31`** (`docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md:1500–1540`, `§9` L2157–2161, `OWNER-APPROVED` 2026-11-13) explicitly locks A3 message scope to **standalone text only**, deferring `Document` captions and media groups (`no implicit support`).
  - **`D-09-R2`** limits active attachment work to local `A0–A4` `Document` staging while `P0` remote upload (`D-10`/`D-11`/`D-14`) remains `BLOCKED`.

### 3.4 Owner-Decision Brief for `ATT-02` (`RECOMMENDATION — NOT OWNER-APPROVED`)
- **Question:** Should Telegram intake remain strictly **`Document`-only** while P0 remote upload and `D-31` captions/media groups remain deferred, or should additional media types (starting with `Photo`) be explicitly scoped for future design?
- **Options:**
  - **Option A — Preserve `Document`-only intake (keep all 9 other media types safely rejected):** Users needing images/files send them uncompressed as Telegram `Document` (preserving exact bytes, filename, MIME/extension check, and `3 MiB` limit). Zero new validation surface, zero ambiguity with Telegram multi-size `photo` arrays (`photo[-1]`) or missing `file_name` (`voice`/`video_note`/`photo`), and strictly aligns with `D-31` (`OWNER-APPROVED`) and blocked P0 remote delivery.
  - **Option B — Prepare future design scope for compressed `Photo` (and optionally `Audio`/`Video`/`Voice`) as explicit future `Plan 09+` work:** Would require owner decisions on: (1) synthetic/extension-safe filename generation (`_attachment_display_name` currently `None` for non-documents), (2) choosing `photo[-1]` largest variant vs original-byte loss under Telegram JPEG recompression, (3) content-type/extension policy parity with `_DENIED_EXTENSIONS`/`_DENIED_MAGIC`, (4) `ImageContent` (`data:` URI support `[U]` in Cloud V1 vs `staging` bytes), and (5) aggregate quota `D-12` + `D-31` media-group/caption semantics. Not needed when users can send photos as `Document`.
  - **Option C — Explicitly re-affirm `Document`-only forever for bot intake (close media expansion permanently):** Same immediate behavior as A, removes future ambiguity about compressed media. Trade-off: less flexible if OpenHands `ImageContent` (`D-14` Option C or future upload) is ever prioritized for mobile Telegram camera uploads.
- **`RECOMMENDATION — NOT OWNER-APPROVED`:** **Option A** (preserve `Document`-only intake now; revisit compressed `Photo` only if and after P0 remote upload `D-10`/`D-11`/`D-14`, permanent quota `D-12`, and `D-31` caption/media-group rules are explicitly opened by the owner).

---

## 4. Facts vs Inferences vs Unknowns / Blocked Checks

- **[F] Verified Facts:**
  - Every file path and line number cited above in `bot/attachments.py`, `bot/handlers.py`, `bot/app.py`, `bot/db.py`, `bot/config.py`, `bot/polling.py`, `.env.example`, `README.md`, `tests/test_repair_plan_01_resource_staging.py`, `tests/test_repair_plan_01_review_findings.py`, `tests/test_unsupported_attachment_rejection.py`, `docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md`, and `docs/decisions/OHB2-OWNER-DECISION-PLAN08-MANUAL-ATTACHMENT-TRANSFER.md` was inspected directly.
  - Read-only Python `stdlib` verification confirms `StagingStore` default attributes (`max_bytes == 3145728`, `max_items_per_batch is None`, `max_total_bytes is None`, `max_bytes_per_batch is None`, `quota_enabled is False`).
- **[I] Engineering Inference:**
  - Because `StagingStore._batch_active_files` and `staging_total_bytes` inspect disk files prior to `_write_to_path` without an async/thread reservation lock, enabling aggregate quotas while `concurrent_updates(True)` and `MAX_CONCURRENT_DOWNLOADS=4` are active would permit a bounded TOCTOU overshoot window (`<= MAX_CONCURRENT_DOWNLOADS`) unless an explicit reservation lock is introduced alongside quota activation.
- **[U] Unknowns / Container Blockers:**
  - `pytest`, `pyflakes`, `bandit`, `pip_audit`, `python-telegram-bot`, and `starlette` are not installed in this container (`Python 3.10.12`, no `pip`). Therefore: (1) full `pytest` suite did not run locally, (2) live runtime inspection of `telegram.Message` / `ptb==22.8` attributes was not executed in container (`UNVERIFIED IN CONTAINER`), and (3) `INDEPENDENT_REVIEW_NOT_AVAILABLE` + `.git` absent.
