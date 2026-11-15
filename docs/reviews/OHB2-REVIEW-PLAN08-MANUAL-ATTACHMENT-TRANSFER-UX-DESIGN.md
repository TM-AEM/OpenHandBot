# OHB2-REVIEW-PLAN08 — Independent Adversarial Review

- **Task ID:** `OHB2-REVIEW-PLAN08-MANUAL-ATTACHMENT-TRANSFER-UX-DESIGN`
- **Type:** Independent, read-only, adversarial review.
- **Target report:** `docs/reviews/OHB2-PLAN-08-MANUAL-ATTACHMENT-TRANSFER-UX-DESIGN.md`
  (SHA-256 `18b29203283cfc70319561969d0e182215f4bbd7b4cabb42060f3a7a486da7ab`, 419 lines).
- **Target task:** `OHB2-PLAN08-MANUAL-ATTACHMENT-TRANSFER-UX-DESIGN`.
- **Reviewer:** OpenHands agent (autonomous, independent). Date: 2026-11-15.
- **Verdict:** **`NEEDS_REMEDIATION`**.

> Evidence labels: **[F] independently verified** · **[I] inference** · **[U] unverified**
> · **[G] documented-but-untested** · **[R] recommendation** · **[OWNER] owner decision**.

---

## 1. Task ID and verdict

**Task ID:** `OHB2-REVIEW-PLAN08-MANUAL-ATTACHMENT-TRANSFER-UX-DESIGN`.

**Verdict: `NEEDS_REMEDIATION`.** The Plan 08 report's *core factual claims are independently
verified TRUE* (staging location/permissions, single SQLite owner, identity table, `file_id` not
stored, only three batch states written, no retrieval path, `delivered` unreachable). **However** the
report contains **one HIGH-severity accuracy defect** (a fabricated/unverified operational limit), a
**cross-document naming collision** that is *now correctly qualified* in this review but was **not
disclosed** in the report, and it **understates the owner-decision blocker** on the recommended B1
path. None of these change the report's *no-implementation* stance, but they must be corrected before
the design can be approved.

A `NEEDS_REMEDIATION` verdict **does not authorize implementation.**

---

## 2. Independent baseline audit (verified by this reviewer, not taken from the report)

| Item | Verified value | Command |
| --- | --- | --- |
| Branch | `main` | `git branch --show-current` |
| HEAD | `facf1f42578a20a4a37e220eca016ce3d534e750` | `git rev-parse HEAD` |
| `main` | `facf1f42578a20a4a37e220eca016ce3d534e750` | `git rev-parse main` |
| `origin/main` | `facf1f42578a20a4a37e220eca016ce3d534e750` | `git rev-parse origin/main` |
| Divergence | `0  0` | `git rev-list --left-right --count origin/main...HEAD` |
| Staged | none | `git diff --cached --name-only` |
| Unstaged | `.agent/PROGRESS.md` (` M`) | `git status --short` |
| Untracked | 5 review docs (Plan 05, 06, 07-A, 07-A2, 08) | `git ls-files --others --exclude-standard` |
| Ignored (relevant) | `.openhands/`, `.pytest_cache/`, `__pycache__/` | `git status --short --ignored` |
| `.openhands/` present | yes, unchanged (mtime `2026-11-14 16:27`, not touched) | `stat`, `git status --ignored` |
| `MINI_APP_ENABLED` | default `False` | `bot/config.py:262` |
| `concurrent_updates` | `True` (unchanged) | `bot/app.py:86` |
| Autopush | no `autopush`/`main.py` process running | `ps aux` |
| `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` | default `True` | `bot/config.py:315–316` |

**[F] Report hashes (independently recomputed):** Plan 05 `4944714a…` (428) · Plan 06 `4450b77c…`
(617) · Plan 07-A `8faec96b…` (509) · Plan 07-A2 `8aa583d2…` (451) · Plan 08 `18b29203…` (419).
All match the report's §2.2 table for 05/06/07-A/07-A2. **`git diff --numstat .agent/PROGRESS.md` =
`249  0`** (append-only; zero deletions) — matches the report's claim.

**Ownership of existing modifications:** the modified `PROGRESS.md` and the four untracked
05/06/07 reports are pre-existing agent artifacts from prior sessions; this review preserved them
untouched. No staged files. Nothing was cleaned, reset, restored, or deleted.

---

## 3. Files and source locations inspected

- `bot/attachments.py` (staging store, reaper, service, precheck, token/root).
- `bot/handlers.py` (`handle_attachment`, `_download_attachment_chunks`, texts, semaphore).
- `bot/db.py` (schema, migrations, attachment + outbox + identity APIs, state constants).
- `bot/outbox.py` (`_post_claimed`, `OutboxWorker`, `_BaseWorker`, `deliver_outbox`, `safe_send`).
- `bot/openhands_client.py` (`send_message` target).
- `bot/app.py` (handler registration, reaper wiring, `concurrent_updates`).
- `bot/sender.py` (`TELEGRAM_DOCUMENT_MAX_BYTES`, `send_text_document`).
- `bot/web/app.py`, `bot/web/services.py` (auth guard, `_attachment`, export/preview, routes).
- `bot/files.py` (`is_safe_workspace_path`, `authorize_conversation_detailed`, `is_valid_conversation_id`).
- `docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md` (D-22, D-12, D-15, D-16, §6.3, §7).
- `docs/proposals/OHB2-P0-STAGED-IMPLEMENTATION-PLAN.md` (Stage B1/B2/B3 definitions).
- `docs/MINI_APP.md` (§2, §13ج, §13د).
- `tests/` (attachment, outbox, repair-plan-02, miniapp, frontend).
- `tests/frontend/dom_stub.js`, `tests/frontend/export_copy_ui.test.js`, `tests/test_real_http_miniapp_download.py`.

---

## 4. Attachment lifecycle verification (claim-by-claim)

| Report claim | Independent result |
| --- | --- |
| Bytes under `<db_dir>/attachment_staging/` | **[F] TRUE** — `staging_root_for` (`attachments.py:204–210`), `STAGING_DIRNAME="attachment_staging"` (`:108`). |
| Dir `0700`, files `0600` | **[F] TRUE** — `STAGING_DIR_MODE=0o700`, `STAGING_FILE_MODE=0o600` (`:109–110`). |
| Filename = opaque token `secrets.token_hex(16)` | **[F] TRUE** — `new_staging_token` (`:199–201`), `_TOKEN_HEX_BYTES=16` (`:111`). |
| Single SQLite owner | **[F] TRUE** — one `Database`, `PRAGMA foreign_keys=ON` fail-closed (`db.py:560–565`); Mini App shares it (`app.py:125`). |
| `attachment_message_identity` PK + FK RESTRICT | **[F] TRUE** — `db.py:804–813` (`PRIMARY KEY (telegram_id,chat_id,message_id)`, `ON DELETE RESTRICT`). |
| `file_id` not stored | **[F] TRUE** — no `file_id` column anywhere in `db.py`; the bytes are the only copy. |
| Only `pending`/`intent_recorded`/`expired` written | **[F] TRUE** — writes at `attachments.py:704` (`pending`), `db.py:1630` (`intent_recorded`), `attachments.py:869`,`:1128` (`expired`). Grep confirms **no** assignment of `dispatching/uncertain/delivered/rejected/failed` in runtime code (only in `tests/test_attachment_*`). |
| `delivered` unreachable | **[F] TRUE** — no writer exists; reaper `_TERMINAL` includes it but nothing produces it. |
| Item states `pending→stored→reaped` | **[F] TRUE** — `try_mark_attachment_item_stored` (`db.py:1224`), `mark_attachment_item_reaped` (`db.py:1463`). |
| 15-min TTL, existing `Watcher` tick drives sweeper | **[F] TRUE** — `ATTACHMENT_BATCH_TTL=timedelta(minutes=15)` (`db.py:261`); `OpportunisticSweeper` wired in `app.py:227–241`. |
| Reaper DB-first, `absent` idempotent, symlink ⇒ `unsafe` | **[F] TRUE** — `attachments.py:1020–1138`, `:1316–1360`. |
| `display_name` metadata only; MIME not stored | **[F] TRUE** — `sanitize_display_name` (`:212–235`); no MIME column. |
| No user-facing retrieval path serves staged bytes | **[F] TRUE** — repo-wide grep for staged-byte reads outside `attachments.py`/`db.py` returns **nothing**. Only reads: `_read_head` (magic check, `:324`) and the store write. |

**Conclusion:** the Plan 08 lifecycle section is **substantially accurate**.

---

## 5. B1 feasibility and outbox analysis (highest-priority area)

### 5.1 Answers to the required questions (all source-backed)

1. **Can B1 use the existing outbox without a new worker/architecture?** **No, not as-is.**
   The outbox row schema is `(id, conversation_id, chat_id, text, status, error, created_at,
   updated_at, attempts, client_ref, notify_state)` (`db.py:608–621`) — **no payload/kind column**,
   and dispatch is `client.send_message(conversation_id, text)` targeting **OpenHands**
   (`openhands_client.py:337–339`), not Telegram. B1 needs a **new durable operation type**.
   A *direct* bounded send (no outbox) is possible but then **loses** the at-most-once machinery.
2. **Is the outbox genuinely text-only?** **[F] YES** — schema, `_post_claimed`, `OutboxWorker`,
   `deliver_outbox`, and recovery all handle text only; the only kinds are
   `COMPLETION_KIND_OUTBOX`/`COMPLETION_KIND_CREATION` (`db.py:179–180`), which are completion
   bookkeeping, not payload kinds.
3. **Would a document operation require a schema migration / architectural decision?** **[F] YES** —
   a new column/table (migration) **or** an owner-approved alternate mechanism ⇒ **D-22**.
4. **Can B1 send the exact staged bytes without a stored `file_id`?** **[F] YES** — read the staged
   file by `staging_token` and send via `InputFile` (the bytes are retained locally). **But** this
   adds the **first-ever** read of staged bytes into a user-facing path.
5. **Can B1 authorize the original requester and prevent cross-user retrieval?** **[F] YES** —
   reuse `_allowed` (private chat + allowlist, `handlers.py:53`) and `_authorized`
   (`attachments.py:815`). Note the deployment is effectively **single-owner**
   (`is_allowed` → `allowed_telegram_ids`, `config.py:59–60`), so cross-user risk is low but must
   still be enforced structurally.
6. **Association with the correct attachment/chat/message?** **[F]** via
   `attachment_batches(telegram_id, conversation_id)` + `attachment_message_identity` (PK) — but the
   **send target chat** must be captured explicitly (the outbox's `chat_id`).
7. **Crash windows:** before the send op is recorded ⇒ nothing sent (safe). After recorded but
   before dispatch ⇒ recoverable **only if** a durable pending state + CAS exist (as the text outbox
   does: `pending→claimed→sending`, `outbox.py:298–408`). During transmission ⇒ the text outbox maps
   this to `unknown` (at-most-once, no auto-retry). After Telegram accepts but before local
   completion is recorded ⇒ **local `sent` may be missing while Telegram already delivered** ⇒
   re-send risk. **[F]** the repo already models exactly this with `sending→sent|unknown`
   (at-most-once); B1 must reuse it.
8. **Can retries produce duplicate sends?** **[F] Yes, if built naively.** The text outbox prevents
   it via CAS + `unknown` (no auto-retry). Any B1 path that does not reuse this **will** duplicate.
9. **Is there an existing safe way to distinguish confirmed vs uncertain send?** **[F] YES** — the
   `sending`→`sent`(confirmed) vs `sending`→`unknown`(ambiguous) CAS (`outbox.py:440–470`).
10. **Can B1 avoid falsely claiming upload to OpenHands?** **[F] YES** — it must only ever report
    "file sent to your Telegram chat", never "delivered to OpenHands".

### 5.2 Explicit event separation (as required)

**[F] These are seven distinct events and the report keeps them separate:**
local staging success ≠ outbox enqueue success ≠ Telegram API acceptance ≠ Telegram delivery to the
user ≠ user download ≠ user upload to OpenHands ≠ independently verified remote delivery.
**A successful B1 send-back is NOT OpenHands delivery.** The report states this (§5.2, §6.6).

### 5.3 B1 blocker status

**B1 requires a new durable operation type and/or a new lifecycle state — i.e. an architectural
decision (D-22) and an owner-approved scope.** The report itself says this (§4.1, §8, §9, §10) but
its §1 headline ("does **not** require … schema change, worker") and §13 ("Yes — bounded and safe")
**understate** the blocker. See **F-02** and **F-03**.

---

## 6. B2 feasibility and WebView verification status

- **[F] No existing route serves staged bytes.** `export` serves the OpenHands trajectory zip;
  `file` serves a text preview of **existing workspace** files (`MINI_APP.md:649`); neither reads
  `attachment_staging/`.
- **[F] A cookie-auth staged route could reuse** `_guarded` (`app.py:432–451`) + ownership +
  `_attachment` (`app.py:95–108`), with **no public URL / no bearer token**.
- **[F] `_attachment` reads bytes fully into memory** (`Response(data, …)`); **no `Range`/206
  support** exists in `bot/web/` (grep). Bounded by construction, but a future route should stream.
- **[F] WebView download is NOT verified.** The only Blob-download test is the Node DOM stub
  (`tests/frontend/dom_stub.js:336–342`); the "real HTTP" test
  (`tests/test_real_http_miniapp_download.py`) covers **export/preview**, not staged bytes, and does
  not exercise a real Telegram WebView. **Real Telegram Android WebView Blob-download behavior =
  `UNVERIFIED`.** The report correctly marks this `UNVERIFIED` (§4.2) — **no overclaim**.

---

## 7. Security findings

| ID | Issue | Status | Severity | Evidence |
| --- | --- | --- | --- | --- |
| S-1 | Cross-user / cross-conversation access (intake) | **MITIGATED** | — | `_allowed` (`handlers.py:53`), `_authorized` (`attachments.py:815`) |
| S-2 | IDOR / authz bypass | **MITIGATED** | — | server-side session + conversation id; no client path (`app.py:432`, `services.py:883`) |
| S-3 | Path traversal / symlink | **MITIGATED** | — | token-only names, `O_EXCL|O_NOFOLLOW` (`attachments.py:585–589`), `_is_within` (`:284`), `lstat` (`:1316`) |
| S-4 | Unsafe filenames / MIME | **MITIGATED** | — | `sanitize_display_name` (metadata only), ext + magic deny lists (`:117–148`, `:212`) |
| S-5 | Unbounded memory / streaming | **PARTIALLY MITIGATED** | LOW | intake streamed + hard cap (`handlers.py:1740`); `_attachment` buffers fully (bounded) |
| S-6 | Large file / interrupted transfer | **PARTIALLY MITIGATED** | LOW | intake cap; retrieval path not built |
| S-7 | Expiry / cleanup race (no retrieval yet) | **NOT MITIGATED (future)** | MEDIUM | a future read must tolerate the byte file vanishing mid-window |
| S-8 | Duplicate Telegram sends (B1) | **NOT MITIGATED (future)** | MEDIUM | needs an outbox-style CAS; naive B1 duplicates |
| S-9 | Sensitive data in logs/errors | **MITIGATED** | — | token names; no content logs; `safe_error_label` |
| S-10 | Internal filesystem path disclosure | **MITIGATED** | — | no path in responses; static confined to `STATIC_DIR` (`app.py:1110–1127`) |
| S-11 | Unauthorized Mini App access | **PARTIALLY MITIGATED** | MEDIUM | session cookie + rate-limit + Origin (`app.py:432`); **no public URL needed** |
| S-12 | Attachment identity confusion | **MITIGATED** | — | explicit routed conversation required, no fallback (`handlers.py:1849–1852`) |
| S-13 | Incorrect user-facing delivery claims | **NOT MITIGATED today** | HIGH | no current message distinguishes local vs remote (`ATTACHMENT_ACCEPTED_TEXT`, `handlers.py:1601`) |

**No security downgrade is proposed by the design.** The report's own security table is materially
accurate; S-7/S-8 are correctly marked "not mitigated (future)".

---

## 8. D-22 and other owner-decision dependencies

- **[F] D-22** (`docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md:1042–1060`): outbox is text-only;
  sending an attachment requires **(a)** a new outbox payload capability **or (b)** another
  **explicitly owner-approved** mechanism. **Status: unresolved. Type: owner (integration)
  decision.** Register §6.3 lists D-22 as a **blocking** decision; §7 lists it among the blockers
  that keep implementation **`BLOCKED`**.
- **[F] D-12/D-15/D-16** are register-classified **non-blocking** (deferrable): D-12/D-15 are
  confirmations; D-16 is idempotency (owner). They shape B1's bounds but do not gate it.
- **[F] U-12/U-3/D-04/D-06/D-02/D-03** remain the long-term verified-delivery path and are **not**
  replaced by the manual UX (report agrees).
- **[F] Critical naming collision (see F-04).** The register's and the P0 staged plan's
  **B1/B2/B3** denote *remote P0 transport stages* — **Stage B1** = "create-op upload + narrow auth"
  (`STAGED-IMPLEMENTATION-PLAN.md:739`), **Stage B2** = "reconciliation/status", **Stage B3** =
  "delivery to the same conversation + outbox integration" (`:756`, `:768`) — and they are
  **`NOT AUTHORIZED TO START`** (register `:697`, `:710`; plan `:12`, `:347`, `:865`). Plan 08's
  **B1/B2/B3** are entirely different (Telegram send-back / Mini App download / no-op). The report
  **never disambiguates this**, which risks a reader mapping Plan 08's "B1" onto the register's
  blocked "Stage B1".

---

## 9. Arabic UX wording review

**Overall:** the wording is clear, RTL-appropriate, short, and mobile-friendly, and it **avoids**
"تم التسليم" without a destination. Corrections required:

1. **[F] §6.1 "استلمت الملف" is weaker than the actual stored state.** The stored reply today is
   `ATTACHMENT_ACCEPTED_TEXT` = *"استلمت الملف ✅ — ابعت أوامرك (النص المصاحب) خلال 15 دقيقة…"*
   (`handlers.py:1601`). §6.1 proposes a **new** sentence not currently shipped — acceptable as a
   design, but it must be labelled as **proposed**, and the "خزّنته محليًّا" wording must only appear
   when `outcome is STORED`, not for `ACCEPTED` (bytes not stored). *(The report does say "if
   `stored`" — keep that conditionality explicit in the final copy.)*
2. **[F] §6.3 "انتهت صلاحية الملف (15 دقيقة)" is accurate** to `ATTACHMENT_BATCH_TTL=15m` — good.
3. **[F] §6.2/§6.5 "نزّل الملف من الرسالة دي"** is fine **only after** B1 exists; until then §6.2's
   fallback ("التنزيل الذاتي لسه مش متاح") is the honest one — keep both, gated.
4. **[F] §6.4 "تعذّر تنزيل الملف"** — must not be shown when retrieval is simply unimplemented;
   distinguish "not available yet" (§6.2 fallback) from "failed" (§6.4).
5. **[R] Add an explicit destination token everywhere**, e.g. "…محليًّا في OpenHandBot (لسه ما اترفعش
   لـ OpenHands)". §6.1/§6.2 already do this; extend it to any future success toast.
6. **[R] Avoid the bare word "تنزيل" alone**; prefer "تنزيل من البوت" to distinguish from an
   OpenHands download. Minor.

**No wording implies an OpenHands-delivery guarantee.** Good.

---

## 10. Independent test commands and results

Environment: Python 3.13.15. `pytest`/deps were **not** preinstalled; installed per repo standard
(`pip install -r requirements-dev.txt`) **system-wide** to match CI (see note below). **No code was
modified to make tests pass.**

| Command | Result |
| --- | --- |
| `python -m pytest tests/test_attachment_staging_a1.py tests/test_attachment_batch_lifecycle_a2.py tests/test_attachment_cleanup_expiration_a4.py tests/test_repair_plan_01_resource_staging.py tests/test_attachment_intent_a3.py tests/test_attachment_message_identity_a3.py tests/test_attachment_batch_schema.py tests/test_unsupported_attachment_rejection.py -q` | **245 passed**, exit 0 |
| `python -m pytest -q -k "outbox or repair_plan_02"` | **301 passed, 2759 deselected**, exit 0 |
| `python -m pytest -q` (first run, deps in user-site) | **1 failed, 3059 passed** |
| `python -m pytest tests/test_deploy_manifest.py::test_documented_manifest_is_import_sufficient -q` | **1 failed** (before system install) → **passed** (after) |
| `python -m pytest -q` (after system-wide install) | **3060 passed, 0 failed**, exit 0 |
| `python -m pyflakes bot/ automation/ tools/ main.py tests/` | **0 issues**, exit 0 |
| `node --test tests/frontend/*.test.js` | **250 pass, 0 fail**, exit 0 |

**Environmental note (not a regression):** the single failure was
`test_deploy_manifest.py::test_documented_manifest_is_import_sufficient`, which spawns
`python -c "import main"` with `HOME=<tmp>` and `PATH=/usr/bin:/bin`. Because my initial install
landed in the **user-site** (`/home/openhands/.local/...`, overridden by `HOME`), `telegram` was not
importable there. Installing the pinned requirements **system-wide** (exactly what CI does at
`.github/workflows/ci.yml:33–34`) made it pass. This is an **environment artifact of my sandbox**,
**not** a defect in the repository or in Plan 08. No production API, credential, real attachment
content, or real Telegram document was used.

**Test provenance:** the original task ran no runtime tests (doc-only). All Python/Node results above
are **independently rerun by this reviewer**. Source-inspection-only items: outbox/Telegram crash
windows (§5.1) — no real Telegram/network exercised. Unverified: real Telegram WebView download.

---

## 11. Findings grouped by severity

### BLOCKER — none

No BLOCKER finding: the report does not implement anything, and its central factual claims hold.

### HIGH

- **F-01 — Unverified "20 MB" operational limit presented as fact.** *Location:*
  `OHB2-PLAN-08…md:172–173` and `:200`. *Evidence:* the repo contains **no** 20 MB Telegram-download
  constant (grep found only the proposal's *own* 20 MB proposal text in
  `OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md:317`, unrelated). The enforced incoming cap is
  `MAX_ATTACHMENT_BYTES = 3 MiB` (`attachments.py:99`); the only 50 MB constant is the **upload**
  cap (`sender.py:19–20`). *Impact:* the "≤20 MB < 50 MB ⇒ no size conflict" argument rests on an
  **external, uncited** figure; if the real Telegram bot download limit is lower (or the server
  returns a URL larger than the bot limit), the claim is wrong. *Required action:* cite an
  authoritative source for the Telegram bot download limit, or restate as `[U]` and base the bound
  solely on the **enforced** `MAX_ATTACHMENT_BYTES`. *Owner approval:* no.

- **F-04 — Undisclosed naming collision between Plan 08's B1/B2/B3 and the register's blocked
  P0 Stage B1/B2/B3.** *Location:* report §4.4, §8, §9, §13 vs
  `OHB2-P0-OWNER-DECISIONS-REGISTER.md:697,710,1929` and
  `OHB2-P0-STAGED-IMPLEMENTATION-PLAN.md:739,756,768,865`. *Evidence:* the register's "B1–B3" are
  **remote transport stages** marked **`NOT AUTHORIZED TO START`**; Plan 08's B1/B2/B3 are unrelated.
  *Impact:* a reader could conflate the two and misread Plan 08's B1 as the blocked Stage B1, or
  misread the register as having blessed a Telegram send-back. *Required action:* add an explicit
  disambiguation note ("Plan 08 B1/B2/B3 ≠ register Stage B1/B2/B3") in the report. *Owner
  approval:* no.

- **S-13 — No user-facing message currently distinguishes local storage from remote delivery.**
  *Location:* `handlers.py:1601` (`ATTACHMENT_ACCEPTED_TEXT`), `:1627`
  (`ATTACHMENT_TEXT_RECORDED_TEXT`). *Evidence:* current replies say "استلمت الملف" / "وصل" with no
  "not uploaded to OpenHands" qualifier. *Impact:* the user may believe the file reached OpenHands.
  *Required action:* the report's proposed §6 wording (P0) must be implemented and is a **product
  wording decision** (owner). *Owner approval:* **yes** (wording).

### MEDIUM

- **F-02 — Report understates B1's architectural prerequisite.** *Location:* report §1 ("does **not**
  require … schema change, worker"), §13 ("Yes — bounded and safe"). *Evidence:* B1 needs a new
  durable op type (outbox schema has **no** payload/kind column, `db.py:608–621`) and/or a new
  lifecycle state ⇒ D-22 (§8). *Impact:* "bounded and safe" reads as lower-risk than it is.
  *Required action:* state plainly that **B1 is blocked by D-22** and requires a schema/mechanism
  change. *Owner approval:* **yes** (D-22).

- **F-03 — B1 is presented as the recommended *first* path without weighing its outbox/schema cost
  against B2.** *Location:* report §4.4 recommendation, §10 P1. *Evidence:* B1 needs an outbox
  payload/kind + idempotency + a new staged-byte read; B2 needs a cookie-auth route reusing existing
  `_guarded`+`_attachment` (**no** schema change). On raw source evidence, **B2 has the smaller
  durable-surface change**; B1's advantage (works inside Telegram without WebView uncertainty) is
  real but **WebView is the only `UNVERIFIED` part of B2**. *Impact:* the recommendation is not
  wrong, but it is **asserted, not derived**. *Required action:* add an explicit trade-off table and
  the reasoning that B1 avoids the WebView uncertainty while B2 avoids schema/D-22. *Owner
  approval:* yes (scope).

- **S-7/S-8 — Retrieval-vs-cleanup race and duplicate-send** are correctly flagged as *future*
  issues but have **no concrete mitigation design** (only "must tolerate"). *Required action:*
  specify the CAS/idempotency and the vanish-tolerant read in the P1 acceptance criteria (the report
  partly does in §11). *Owner approval:* no.

### LOW

- **F-05 — Two line citations are imprecise.** `db.py:770–815` for the identity table is generous
  (table is `:804–816`); `db.py:1591` cited for D-33 is a docstring, not the FK (FK at `:813`).
  *Required action:* tighten citations. *Owner approval:* no.

- **F-06 — §7 lists severity "High" for rows that are actually MITIGATED** (e.g. cross-user). Not a
  defect, but mixing "residual severity" with "status" is easy to misread. *Required action:* split
  columns. *Owner approval:* no.

### INFO

- **F-07 — Plan 08's §6.2 "button 'تنزيل الملف'"** implies a UI control that does not exist; keep it
  clearly marked "future". (The report does mark §6 as proposal-only.) *Owner approval:* no.

---

## 12. Required remediation

1. **F-01:** cite the Telegram bot download-limit source or restate as `[U]`; base the bound on the
   enforced `MAX_ATTACHMENT_BYTES = 3 MiB`.
2. **F-04:** add the B1/B2/B3 naming disambiguation vs the register/staged plan.
3. **F-02/F-03:** state B1 is **blocked by D-22** and add the B1-vs-B2 trade-off table.
4. **S-13:** mark the wording change as an owner wording decision.
5. **F-05/F-06:** tighten citations; split severity/status columns.

None of these require touching runtime code; all are report corrections.

---

## 13. Is the design safe to approve?

**Partially.** The design's **facts are sound** and it proposes **no security downgrade**, but
approving the *report as-is* would ratify (a) an **unverified 20 MB claim (F-01)** and (b) an
**undisclosed naming collision (F-04)** that could cause a governance error. **Remediate §12 items
1–3 first.** The UX wording is safe to *adopt as policy* only after owner wording approval (S-13).

---

## 14. Can a separate B1 implementation task be prepared?

**Only after D-22 is resolved (owner) and the scope is approved.** B1 **cannot** be implemented
within the *current approved architecture* without a new outbox payload/kind or an owner-approved
alternate mechanism, and without a new durable state for confirmed-vs-uncertain send. **Do not
prepare or start a B1 implementation task** until:
- **D-22** is decided (owner) — new outbox item kind vs another mechanism;
- **scope** is approved (B1 only vs B1+B2);
- **D-15/D-16** are confirmed for the 15-min window and dedup;
- the §12 remediation is applied to the design.

A **B2** implementation task is *closer* to the existing architecture (route + `_guarded` +
`_attachment`, no schema change) but is gated by **`UNVERIFIED` real Telegram WebView download
behavior** and the same scope approval.

---

## 15. Explicit confirmation — no implementation

**[F]** This review performed **no implementation**. No runtime/frontend/test/schema/migration/
config/dependency file was modified. The only artifacts created are this review report and an
append-only `.agent/PROGRESS.md` entry. **No** commit, push, PR, merge, release, deploy, or Autopush
activation occurred. **No** production API/credential/real attachment/real Telegram document was
used. Plan 08 and the earlier Plan 05/06/07 reports are **byte-for-byte unchanged** (hashes §2).

---

> Evidence labels recap: **[F]** independently verified · **[I]** inference · **[U]** unverified
> · **[G]** documented-but-untested · **[R]** recommendation · **[OWNER]** owner decision.
