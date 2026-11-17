# OHB2 Owner Decisions Briefing Independent Review

**Task ID:** `OHB2-OWNER-DECISIONS-BRIEFING-INDEPENDENT-REVIEW`  
**Reviewed Document:** `docs/audits/OHB2-OWNER-DECISIONS-BRIEFING.md` (`544` lines, `99,383` bytes)  
**Baseline Authority:** `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md` (`806` lines, `124,204` bytes)  
**Review Mode:** Strictly Read-Only Independent Verification (this review file is the sole newly created artifact; zero existing files modified)  
**Owner Decision Status:** `PENDING_OWNER_DECISION — NO OPTION SELECTED, RECOMMENDED, OR IMPLEMENTED`  

---

## 1. Executive Verdict

**Verdict:** **`PASS_WITH_NOTES`**

Independent verification against `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md`, architecture/decision records, operational documentation, and live source code confirms that `docs/audits/OHB2-OWNER-DECISIONS-BRIEFING.md` is **technically sound, strictly neutral, internally consistent, and safe to use as the owner's decision-making reference for `OD-01` through `OD-05`**.

- **Zero Critical or High defects** were found in governance boundaries, neutrality, Mini App isolation, or decision-option completeness.
- **Zero options are preselected, ranked, or endorsed** across `OD-01`–`OD-05`; all five remain explicitly `PENDING_OWNER_DECISION`.
- **Non-blocking findings (`2` `MEDIUM`, `4` `LOW`, `1` `INFO`)** are documented in `§10` (`REV-OD-01` through `REV-OD-07`), notably:
  - `REV-OD-01` (`MEDIUM`): `docs/audits/OHB2-OWNER-DECISIONS-BRIEFING.md:78` mislabels the `CreationWorker` `wait_for_start` fallback gap as `DEF-008` instead of **`DEF-012`** (even though `§10` `WP-05` at `L480` cites `DEF-012` accurately).
  - `REV-OD-02` (`MEDIUM`): `§5.D` Option A (`L187`) states that `/updates_skip N confirm` in `[N, N+1, ...]` makes `N` skippable within the same batch without surfacing two implementation nuances proven in `bot/polling.py:161-165` and `bot/db.py:2966-2988`: (a) `N` is dispatched sequentially *before* `N+1` executes unless a pre-dispatch skip/quarantine check intervenes, and (b) `commit_batch_outcomes` computes `acknowledgment_boundary` via `_outcome_in_txn`, which reads only `processed_updates`, requiring explicit override/outcome handling so `N` advances cleanly.
  - Four `LOW` and one `INFO` precision notes (`NEW-DEF-07` omitted from explicit defect references despite `27`-defect total; `UNSUPPORTED_ATTACHMENT_TEXT` cited as `bot/messages.py` in `L244` rather than `bot/handlers.py:1603-1606`; `tests/test_real_http_miniapp_download.py` and `tests/_miniapp_helpers.py` omitted from the explicit excluded-file list; `ADR §28.4` shorthand vs `§18.6`/`§28` bullet `4` in `L38`; `collect_outcomes` vs `commit_batch_outcomes` DB write phrasing in `L79` and `WP-06` status taxonomy phrasing in `L481`).

None of these notes alters the decision space, biases any owner option, or invalidates using `docs/audits/OHB2-OWNER-DECISIONS-BRIEFING.md` immediately for `OD-01`–`OD-05` sign-off.

---

## 2. Baseline & File-Integrity Check

Direct SHA-256 digests, line counts, and byte counts were verified via `sha256sum` and filesystem inspection prior to generating this review:

| Artifact | Path | Lines | Bytes | Verified SHA-256 | Integrity Status |
|---|---|---:|---:|---|---|
| **Authoritative Corrected Baseline** | `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md` | `806` | `124,204` | `e7b98175d66bb118e437a75380622e09392998bcc9f754d3f48c26f4f5709a6f` | **Pristine / Unmodified** (exact expected baseline digest) |
| **Reviewed Briefing Document** | `docs/audits/OHB2-OWNER-DECISIONS-BRIEFING.md` | `544` | `99,383` | `8974a3b991f2ed32a5547b8db85f3d6e40c0160ce683cfcb10d1ca6f35599c45` | **Pristine / Unmodified** |
| **Root Runbook Path Check** | `OPERATIONS_RUNBOOK.md` (repo root) | — | — | — | **Absent at repo root** (`ROOT_OPERATIONS_RUNBOOK_MISSING`; actual path is `docs/OPERATIONS_RUNBOOK.md`) |

---

## 3. Review Methodology & Verification Scope

Every technical claim, symbol name, line number, cross-decision interaction, release gate, and limitation in `docs/audits/OHB2-OWNER-DECISIONS-BRIEFING.md` was checked independently against primary artifacts rather than prior completion summaries:

1. **Full Document Verification:** Read 100% of `docs/audits/OHB2-OWNER-DECISIONS-BRIEFING.md` (`L1–544`), `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md` (`L1–806`), `docs/audits/OHB2-INDEPENDENT-AUDIT-REPORT-VALIDATION.md` (`L1–208`), `docs/DEPLOY_ENZONIC.md` (`L1–70`), `docs/OHB2_ENZONIC_DEPLOYMENT_PREFLIGHT.md` (`L1–426`), `docs/OHB2_HOSTING_DECISION.md` (`L1–358`), `docs/reviews/OHB2-MT2-COMPLETION-AND-ADVERSARIAL-VERIFICATION.md` (`L1–174`), `.github/workflows/enzonic-sftp-readonly-check.yml` (`L1–126`), `tools/katabump-sqlite-canary/canary.py` (`L1–245`), `.env.example` (`L1–20`), and `.agent/PROGRESS.md` (`L1–561`), plus relevant sections of `docs/proposals/OHB2-TELEGRAM-ACK-ARCHITECTURE-ADR.md` (`§18.5–§37`, `L615–1184`), `docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md` (`D-34`, `D-34/J`, `D-35`, `D-15`, summary table), and `docs/OPERATIONS_RUNBOOK.md` (`L1–160`).
2. **Direct Source Inspection:** Inspected `bot/config.py`, `bot/update_outcomes.py`, `bot/features.py`, `bot/messages.py`, `bot/app.py`, `bot/polling.py`, `bot/outbox.py`, `bot/db.py`, `bot/handlers.py`, `bot/attachments.py`, `bot/openhands_client.py`, and read-only `bot/web/services.py` / `tests/_miniapp_helpers.py` / `tests/test_real_http_miniapp_download.py`.
3. **Read-Only Local Checks Executed Directly:**
   - Python runtime & syntax: `python3` `3.11.2`; `165/165` `.py` files pass syntax-only `ast.parse` (`0` syntax errors); `tests/` contains `131` `.py` files (`126` `test_*.py`). All `10/10` packages in `requirements.txt` / `requirements-dev.txt` (`telegram`, `httpx`, `starlette`, `uvicorn`, `dotenv`, `anyio`, `pytest`, `pyflakes`, `bandit`, `pip_audit`) are absent -> Python backend behavioral/integration/lint/SAST/SCA checks **`BLOCKED`**.
   - Frontend read-only JS tests: `node --test tests/frontend/*.test.js` on `Node v22.23.2` -> **`280` tests, `280` pass, `0` fail, `0` skipped** across `23` `*.test.js` files.
   - Git check: `.git` directory is absent (`ls: cannot access '.git': No such file or directory`) -> **`GIT STATE UNVERIFIED`**.

---

## 4. Per-Decision Independent Verification (`OD-01`–`OD-05`)

Each decision in `docs/audits/OHB2-OWNER-DECISIONS-BRIEFING.md` (`§4`–`§8`) was audited against all ten review criteria: statement accuracy, source facts, completeness of options, fairness/balance, consequences & risks, WP dependencies, reversibility, deferral impact, missing technical nuances, and neutrality/non-preselection.

### 4.1 `OD-01` — `D-34` (`TERMINAL_UNPROVEN`) and Handling of Uncertain External Outcomes (`§4`, `L57–148`)

| Criterion | Verification Result | Direct Evidence & Observations |
|---|---|---|
| **Statement accuracy** | **PASS** | Accurately frames routing/classification/recovery policy for `classify_attachment_routing` (`bot/db.py:1493-1570`), `_handle_accompanying_text` (`bot/handlers.py:2052-2204`), and uncertain external states alongside `D-34 Option A` deadlock (`DEF-001`). |
| **Source facts** | **PASS_WITH_NOTE** | `has_terminal_attachment_batch` (`bot/db.py:1379-1384`), 7-step priority in `classify_attachment_routing`, `AttachmentReaper` skipping `intent_recorded`/`dispatching`/`uncertain`/`invalid_t0`, `D-35` `ON DELETE RESTRICT` (`bot/db.py:561`), `OUTBOX_UNKNOWN` (`bot/outbox.py:480-543`), and `D-34`/`D-34/J`/`D-35`/`D-15` register citations all verify cleanly. **Note (`REV-OD-01`):** `L78` cites `DEF-008` for the `CreationWorker` `wait_for_start` fallback gap, which is actually **`DEF-012`**. Also (`REV-OD-07`), `L79` says `collect_outcomes` writes `PARTIAL_OR_UNKNOWN`; strictly speaking `bot/polling.py:196-199` synthesizes it into `pairs` and `Database.commit_batch_outcomes` (`bot/db.py:2977-2984`) persists it to `update_failures`. |
| **Option completeness** | **PASS** | Faithfully captures Baseline §H Policy Outcomes 1–3 as Option A (preserve `D-34` global fail-closed), Option B (bounded verified terminal pass-through amending `D-34`), and Option C (hybrid: manual reconciliation for uncertain/ambiguous states + explicit owner confirmation/clearance before resuming text). |
| **Fairness & balance** | **PASS** | All three options present symmetric Benefits, Risks, Data-integrity implications, User consequences, Reversibility, and Prerequisites. Option C's extra UX friction and Option B's `N-2` late-caption trade-off are disclosed transparently alongside Option A's continuing `DEF-001` brick. |
| **WP dependencies & reversibility** | **PASS** | Correctly links to `WP-01`, `WP-07`, `WP-08`, `WP-09`, distinguishes policy reversibility from irreversible `reaped`/unlinked bytes and irreversible sent prompts, and notes pre-change SQLite inventory + `D-34` test contract impact. |
| **Neutrality** | **PASS** | `OWNER DECISION REQUIRED — NO OPTION SELECTED` (`L144`), balanced unchecked boxes (`L146-148`), zero leading language. |

### 4.2 `OD-02` — `ADR §28.4` and Telegram/Network Exception-Handling Policy (`§5`, `L152–226`)

| Criterion | Verification Result | Direct Evidence & Observations |
|---|---|---|
| **Statement accuracy** | **PASS** | Accurately frames `FAILED_PERMANENT` head-of-line polling deadlocks (`DEF-002`), `TextDocumentTooLargeError` (`bot/handlers.py:1150-1154`), and `ADR §28.4` `/updates_status` + `/updates_skip <update_id> confirm` + schema metadata. |
| **Source facts** | **PASS_WITH_NOTE** | `_classify_failure` (`bot/handlers.py:477-495`), `_INELIGIBLE` (`bot/update_outcomes.py:40-90`), `commit_batch_outcomes` (`bot/db.py:2945-3010`), and `ADR` references (`§18.6 L624-646`, `§30.5 L1055`, `§35 L1115`, `§37 L1171-1183`) verify directly. **Missing technical nuance (`REV-OD-02`):** In `L187`, when `[N, N+1]` arrives with `/updates_skip N confirm` at `N+1`, `process_updates` (`bot/polling.py:161-162`) dispatches `N` sequentially *before* `N+1` runs (since `N` is in `update_failures`, not `processed_updates`), so `N` re-executes once more unless quarantined prior to dispatch; furthermore `commit_batch_outcomes` (`bot/db.py:2985-2988`) evaluates `_outcome_in_txn` from `processed_updates` only, so implementing Option A/B requires `_outcome_in_txn` or `POISON_SKIPPED` recording to let `acknowledgment_boundary` advance past `N`. |
| **Option completeness** | **PASS** | Covers all three practical policy paths: Option A (strict `ADR §28.4` manual quarantine for all `FAILED_PERMANENT`), Option B (deterministic user-limit split for `TextDocumentTooLargeError` post-notification + `ADR §28.4` quarantine), and Option C (`WP-04` Part 1 transient fixes only +/- read-only `/updates_status`, deferring skip/schema changes). Also explicitly notes schema choice (`update_failures` columns vs `acknowledgment_overrides` table). |
| **Fairness & balance** | **PASS** | Highlights Option A's >50 MiB stall inconvenience + `>100`-update backlog risk, Option B's discipline boundary against expanding eligible rejection paths, and Option C's conflict with restricted Enzonic shell/panel rules (`docs/DEPLOY_ENZONIC.md:36`). |
| **WP dependencies & deferral** | **PASS** | Cleanly isolates unblocked `WP-04` Part 1 (`_classify_failure`) from `OD-02`-gated `WP-04` Part 2, flags `WP-03` post-notification guard coupling (`send_reply_txt:1152`) under Option B, and flags `17 -> 18/19` table parity under `WP-08`. |
| **Neutrality** | **PASS** | Unselected checkboxes (`L222-226`), neutral phrasing throughout. |

### 4.3 `OD-03` — `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` Default and Relationship with `MT-2` (`§6`, `L230–292`)

| Criterion | Verification Result | Direct Evidence & Observations |
|---|---|---|
| **Statement accuracy** | **PASS** | Correctly pins `bot/config.py:43,315-317`, `.env.example:2`, and cross-boundary impact on excluded Mini App `OHB2-MT-2` (`bot/web/services.py:758-870`). |
| **Source facts** | **PASS_WITH_NOTE** | `_parse_bool(..., default=True)` (`bot/config.py:99-117`), `handle_attachment` (`bot/handlers.py:1879-1990`), `now > deadline` (`bot/web/services.py:805,850`) vs `now >= deadline` (`bot/db.py:1334,1360,1429,1624`), and pre-existing batch persistence verify cleanly. **Note (`REV-OD-04`):** `L244` cites `(bot/handlers.py:2008, bot/messages.py)` for `UNSUPPORTED_ATTACHMENT_TEXT`; `UNSUPPORTED_ATTACHMENT_TEXT` is defined at `bot/handlers.py:1603-1606`, not in `bot/messages.py` (`L1-211`). |
| **Option completeness** | **PASS** | Binary owner choice matches Baseline §H `OD-03`: Option A (`False` default, explicit `=1` opt-in for `MT-2`) vs Option B (retain `True` default relying on `WP-01` + `OD-01`). |
| **Fairness & balance** | **PASS** | Clearly warns that Option A breaks zero-config `MT-2` AND does **not** cure pre-existing bricked batches in SQLite, while Option B remains unsafe unless `OD-01` resolves `DEF-001` (not Option A). |
| **Neutrality** | **PASS** | `OWNER DECISION REQUIRED — NO OPTION SELECTED`, zero bias toward flipping or keeping `True`. |

### 4.4 `OD-04` — `TelegramPoller` Concurrency and SQLite Safety (`§7`, `L295–362`)

| Criterion | Verification Result | Direct Evidence & Observations |
|---|---|---|
| **Statement accuracy** | **PASS** | Accurately captures the contradiction between `bot/app.py:75-87` (`.concurrent_updates(True)` + `U04` comment) and sequential `TelegramPoller.process_updates` (`bot/polling.py:161-162`) / `docs/OPERATIONS_RUNBOOK.md:123-127`. |
| **Source facts** | **PASS** | Sequential `dispatch_and_wait` (`put` + `join` per update, `bot/polling.py:161-162,175-178`), single shared `sqlite3.Connection` (`check_same_thread=False`, WAL, `busy_timeout=5000`, `PRAGMA foreign_keys=ON` in `bot/db.py:550-565`), and lack of per-user async/DB locks verify 100%. |
| **Option completeness & balance** | **PASS** | Option A (preserve sequential + align `bot/app.py` comments/config) vs Option B (commission formal single-connection SQLite + per-user lock design and stress proof prior to refactor). Latency trade-off of Option A and complexity/race risks of Option B are stated evenly. |
| **WP dependencies & deferral** | **PASS** | Correctly isolates `WP-07` non-poller fixes (`DEF-011` async disk I/O + quota lock, `DEF-013`, `NEW-DEF-03`) as independent of `OD-04` (subject to `WP-01`), while gating concurrency refactor on `OD-04` + proof. |
| **Neutrality** | **PASS** | Neutral checkboxes, no preference expressed. |

### 4.5 `OD-05` — External Qualification, Live Verification, and `Stage B` Reopening (`§8`, `L365–442`)

| Criterion | Verification Result | Direct Evidence & Observations |
|---|---|---|
| **Statement accuracy** | **PASS** | Faithfully frames `WP-10` / `DEF-016` external checks (Enzonic SFTP, `H1` SQLite canary, `HOST-02` TLS/HTTPS ingress, upstream OpenHands schema, Android 12 `MT-2` download) and `Stage B` (`DEF-015` / `.agent/PROGRESS.md:20-36`). |
| **Source facts** | **PASS** | Verified line-for-line against `.github/workflows/enzonic-sftp-readonly-check.yml` (`126` lines, user `5s5k7kk.e56cc5c8`, `us-four.enzonic.com:2022`, fingerprint `SHA256:6MPMP1TJ75QuFqne7qrvN4+7vMW4tFvokGhmIE74fls`, `pwd` + `ls -la /`), `tools/katabump-sqlite-canary/canary.py` (`245` lines), `docs/DEPLOY_ENZONIC.md:10-42` (`Brave Grove` live protection + 8 `HOST-01`/`HOST-02` blockers), `docs/reviews/OHB2-MT2-COMPLETION-AND-ADVERSARIAL-VERIFICATION.md:139`, `docs/API_NOTES.md:81` (`v1.68.1`), `bot/openhands_client.py:344` (`v1.79.0`), `docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md` (`v1.87.1`), and `.agent/PROGRESS.md:20-36`. |
| **Option completeness & balance** | **PASS** | Covers all three non-destructive decision tiers: Option A (defer both `WP-10` and `Stage B`), Option B (narrow read-only/isolated-target `WP-10` after `Gates A–C`, `Stage B` closed), Option C (`WP-10` + evaluation-only `Stage B` feasibility check gated on scoped upload auth + static `Gate G1` SSRF allowlist + separate ADR before any code). |
| **Safety & deferral** | **PASS** | Strictly protects live `"OpenHandBot"` (`"Brave Grove"`), enforces Enzonic `C3` SQLite exclusion on live host, keeps `WP-01`–`WP-09` CI unblocked, and prevents premature `Stage B` implementation. |
| **Neutrality** | **PASS** | Explicit unchecked options (`L438-442`), zero endorsement. |

---

## 5. Neutrality & Decision-Preservation Audit

A repository-wide and structural neutrality audit of `docs/audits/OHB2-OWNER-DECISIONS-BRIEFING.md` confirmed **full compliance** with `AGENTS.md` §14 ("silence is never approval") and plan-only constraints:

1. **Zero Preselection Markers:** No `Recommended`, `Preferred`, `Default Choice`, `Best Option`, or checkmarks `[x]` appear anywhere in `docs/audits/OHB2-OWNER-DECISIONS-BRIEFING.md`; all five decision blocks carry `OWNER DECISION REQUIRED — NO OPTION SELECTED` and `[ ]` boxes.
2. **Balanced Consequence Analysis:** Every option (`OD-01` A/B/C, `OD-02` A/B/C, `OD-03` A/B, `OD-04` A/B, `OD-05` A/B/C) uses an identical eight-part schema (*Exact policy & behavior, Benefits, Risks / failure modes, Data-loss / data-integrity implications, User-visible consequences, Affected work packages, Reversibility, Prerequisites / additional evidence*), preventing one-sided framing.
3. **Neutral Deferral Analysis:** Each §E ("Consequences of deferring the decision") states both the risk of continuing current defects and the stability benefit of deferring without nudging an outcome.
4. **No Mini App Policy Drift:** `OD-03` explicitly informs the owner about the excluded `MT-2` impact (`bot/web/services.py:758-870`) without recommending either default (`False` vs `True`) or modifying Mini App boundaries.
5. **Decision Sequence Disclaimed (`§13`, `L515`):** Explicitly declares that sequencing `OD-01`/`OD-03` -> `OD-02` -> `OD-04` -> `OD-05` reflects technical dependency order and *"is **not** a choice of options and **not** an implementation schedule"*.

---

## 6. Cross-Decision Interaction Verification

All **10** unique unordered pairs among `{OD-01, OD-02, OD-03, OD-04, OD-05}` are explicitly tabulated in Briefing `§9` (`L446–461`) and verified against source code and Baseline §E–§I:

| Pair | Briefing Classification | Verified Technical Accuracy |
|---|---|---|
| `OD-01 <-> OD-03` | Direct dependency | **ACCURATE:** `OD-03=True` paired with `OD-01=A` leaves `DEF-001` active; `OD-03=False` protects only new installs, not pre-existing SQLite batches (`handle_text:2245`), and starves `MT-2`. `db.py` (`>=`) vs `web/services.py` (`>`) `15m` boundary asymmetry accurately noted. |
| `OD-01 <-> OD-05` | Direct dependency | **ACCURATE:** `dispatching`/`uncertain` currently have no runtime producer while `Stage B` stays deferred, yet pre-existing/future `Stage B` rows directly depend on `OD-01` terminal vs uncertain routing rules. |
| `OD-03 <-> OD-05` | Direct dependency | **ACCURATE:** Live Android 12 `MT-2` testing (`OD-05` B/C) requires `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=1` if `OD-03` flips default to `False`; future `Stage B` delivery changes `MT-2`'s interim rationale. |
| `OD-02 <-> OD-04` | Indirect interaction | **ACCURATE:** `OD-02` `/updates_skip` batch behavior is simpler under `OD-04` sequential dispatch than under concurrent intra-batch execution (noting `REV-OD-02` nuance on `N` pre-dispatch and `_outcome_in_txn` inside `OD-02` Option A/B). |
| `OD-01 <-> OD-02` | Indirect interaction | **ACCURATE:** Corrupt/out-of-enum `AttachmentBatchIntegrityError` (`bot/db.py:1536`) bubbles into `_classify_failure` -> `FAILED_PERMANENT`, linking corrupt-batch reconciliation (`OD-01`) with poison recovery (`OD-02`). |
| `OD-01 <-> OD-04` | Direct dependency | **ACCURATE:** Concurrent intra-batch messages from the same user would race `handle_attachment`, `classify_attachment_routing` (`LIVE`/`MULTI_LIVE`), `record_attachment_intent`, and `/cancel` unless serialized by per-user locks. |
| `OD-02 <-> OD-03` | No demonstrated dependency | **ACCURATE:** `bot/handlers.py:1891` and `1988-1989` mark `EXPLICITLY_IGNORED` / `DURABLE_INTENT_RECORDED`; Telegram send failures map to `WP-04` Part 1 (`FAILED_TRANSIENT`), not `OD-02` permanent poison policy. |
| `OD-02 <-> OD-05` | Indirect interaction | **ACCURATE:** `docs/DEPLOY_ENZONIC.md:36` bans shell/console SQLite tampering on `"Brave Grove"` and `HOST-01` lacks SSH, increasing the operational friction of `OD-02` Option C (out-of-band SQLite edits) on Enzonic-like hosts. |
| `OD-03 <-> OD-04` | Indirect interaction | **ACCURATE:** Under `OD-03=True`, intra-batch concurrency (`OD-04` Option B) would race `StagingStore` quotas (`DEF-011`) and `MULTI_LIVE` detection without per-user serialization. |
| `OD-04 <-> OD-05` | Requires further evidence | **ACCURATE:** Enzonic resource limits (`50% CPU`, `~500 MB / 512 MiB` RAM unverified per `docs/DEPLOY_ENZONIC.md:21`) and OpenHands latencies lack live benchmark data until `WP-10`. |

---

## 7. `WP-01`–`WP-10` Impact & Boundary Verification

Briefing `§10` (`L464–485`) was compared row-by-row against Baseline §E (`L474–698`), §G (`L716–765`), and §I (`L783–794`):

- **`WP-01` (`Fully blocked` on routing/default changes; pre-change inventory & `NEW-DEF-06` copy design unblocked):** **Verified accurate** — properly binds `OD-01`, `OD-03`, pre-change DB/disk inventory, conservative state-by-state preservation matrix, `Gate 0 -> Gate A`, and zero Mini App edits.
- **`WP-02` (`Eligible for future authorization after prerequisites`):** **Verified accurate** — `DEF-005` + `NEW-DEF-01` (`28 q.answer` + `5` bare `q.edit_message_text`), no `OD` blocker, sequential coordination on `bot/handlers.py` -> `Gate B`.
- **`WP-03` (`Eligible for future authorization after prerequisites`):** **Verified accurate** — `DEF-003`, `DEF-004`, `NEW-DEF-04`; preserves already-compliant `list_conversations` / `_show_repos`; notes conditional coupling if `OD-02` Option B touches `send_reply_txt:1152` -> `Gate B`.
- **`WP-04` (`Partially blocked`):** **Verified accurate** — Part 1 (`_classify_failure`) unblocked (after `WP-03`), Part 2 (`ADR §28.4` quarantine/schema) blocked on `OD-02` -> `Gate B`.
- **`WP-05` (`Eligible for future authorization after prerequisites`):** **Verified accurate** — `DEF-007`, `DEF-008`, `DEF-012`, `NEW-DEF-02`, `NEW-DEF-05` -> `Gate C`. (Properly names `DEF-012` here!).
- **`WP-06` (`Eligible for future authorization after prerequisites` + explicit `Gate 0` Design Prerequisite note):** **Substantively accurate, minor taxonomy note (`REV-OD-07`):** Briefing accurately states both that `OD-01`–`OD-05` do not block `WP-06` and that `callback_refs` DB work (`17 -> 18` tables) is gated at `Gate 0` on the mandatory TTL/cleanup/malformed/ownership-action-binding Design Prerequisite (while `STATE_LABELS["unknown"]` & `get_status` normalization are unblocked). Labeling `WP-06` `"Partially blocked"` (like `WP-04` and `WP-07`) or retaining `"Eligible..."` with the inline `Gate 0` prerequisite note is purely a taxonomy polish item.
- **`WP-07` (`Partially blocked`):** **Verified accurate** — depends on `WP-01`; non-poller tasks (`DEF-011` async offload + quota ledger, `DEF-013`, `NEW-DEF-03`) & Option A comments clear after `WP-01`; concurrent intra-batch polling blocked on `OD-04` + proof -> `Gate C`.
- **`WP-08` (`Partially blocked`, sequenced after `WP-01`, `WP-04`, `WP-06`, `WP-07`):** **Verified accurate** — tracks `DEF-017`, `DEF-018`, `NEW-DEF-08`; protects `docs/MINI_APP.md`, `bot/web/*`, `Config.mini_app_*`, and AI Studio scaffold files -> `Gate C`.
- **`WP-09` (`Partially blocked` locally, gates all WPs):** **Verified accurate** — separates `6` independent categories (`Cat 4` `PASS` `280/280`, `Cat 1–3 & 5` `BLOCKED` locally due to `10/10` absent Python packages, `Cat 6` `NOT_RUN` under `WP-10`/`OD-05`).
- **`WP-10` (`External qualification only`):** **Verified accurate** — `DEF-015`, `DEF-016`, strictly gated on `OD-05`, `Gates A–C`, credentials, isolated non-live canary target, Android 12 hardware, and `Stage B` prerequisites -> `Gate D`.

---

## 8. Baseline Alignment & Fact-Check Matrix

| Claim / Fact in Briefing | Baseline / Source Authority | Verification Outcome |
|---|---|---|
| `27` distinct defects (`DEF-001`–`DEF-019`, `NEW-DEF-01`–`NEW-DEF-08`) (`§1 L14`) | Baseline `§C.1`–`§C.2` (`19 + 8 = 27`) | **PARTIAL (`REV-OD-03`)**: Total `27` is exact, but `NEW-DEF-07` (`docs/audits/` supersession finding) appears `0` times in the briefing body. |
| `Python 3.11.2`, `Node v22.23.2`, `10/10` Python packages absent (`§2 L32`) | Direct CLI check & Baseline `§B`, `WP-09` | **EXACT MATCH** |
| `165/165` `ast.parse`, `126` `test_*.py` / `131` files, `280/280` across `23` `*.test.js` (`§2 L33`) | Direct AST & `node --test` execution + Baseline `§B`, `WP-09` | **EXACT MATCH** |
| `.git` directory absent (`§2 L34`, `§14 L535`) | `ls: cannot access '.git': No such file or directory` | **EXACT MATCH** |
| `17` SQLite tables in `bot/db.py`, no `callback_refs` (`§2 L35`) | `bot/db.py:550-820`, Baseline `§B` | **EXACT MATCH** (`__init__` `550-581` + `_init_schema` `587-820`) |
| `20` env vars in `.env.example`; `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=True` default; `DEFERRED_FEATURES_HIDDEN=False` (`§2 L36`, `§6 L239`) | `.env.example:1-20`, `bot/config.py:43,99-117,315-317`, `bot/features.py:15` | **EXACT MATCH** |
| `AttachmentReaper` transitions expired `pending -> expired`, item `-> reaped` + `unlink`, skips `intent_recorded`/`dispatching`/`uncertain`/`invalid_t0`, reaps DB orphans, preserves untracked files (`§2 L37`, `§4 L75`) | `bot/attachments.py:1062-1350`, Baseline `WP-01` matrix | **EXACT MATCH** |
| `bot/db.py` `>=` vs `bot/web/services.py` `>` at `now == T0 + 15m` (`§4 L96`, `§6 L243`, `§9 L448`) | `bot/db.py:1334,1360,1429,1624` vs `bot/web/services.py:805,850` | **EXACT MATCH** |
| `CreationWorker` `wait_for_start` exception gap cited as `DEF-008` in `§4 L78` vs `DEF-012` in `§10 L480` | Baseline `§C.1` (`DEF-008` = `deliver_outbox`; `DEF-012` = `wait_for_start`) | **MISMATCH (`REV-OD-01`)**: `L78` should read `DEF-012`. |
| `UNSUPPORTED_ATTACHMENT_TEXT` cited as `(bot/handlers.py:2008, bot/messages.py)` (`§6 L244`) | `bot/handlers.py:1603-1606`, `2008`; `bot/messages.py:1-211` | **MISMATCH (`REV-OD-04`)**: Constant is in `bot/handlers.py:1603-1606`, not `bot/messages.py`. |
| `ADR §28.4` cited at `L1055, 1115, 1171` (`§2 L38`, `§5 L170`) | `OHB2-TELEGRAM-ACK-ARCHITECTURE-ADR.md:624-646, 961-974, 1055, 1115, 1171` | **PARTIAL (`REV-OD-06`)**: `§5 L170` accurately includes `§18.6 L624-646`, whereas `§2 L38` omits `§18.6` / `§28` bullet `4` (`L970-971`). |
| `process_updates` `[N, N+1]` same-batch skip (`§5 L187`) | `bot/polling.py:161-165`, `bot/db.py:2966-2988` | **PARTIAL (`REV-OD-02`)**: Requires pre-dispatch skip check & `_outcome_in_txn` override awareness. |
| `bot/app.py:82-87` `.concurrent_updates(True)` vs `bot/polling.py:161-162` sequential (`§7 L301-307`) | `bot/app.py:75-87`, `bot/polling.py:161-178`, `docs/OPERATIONS_RUNBOOK.md:123-127` | **EXACT MATCH** |
| Enzonic workflow `126` lines, user `5s5k7kk.e56cc5c8`, `us-four.enzonic.com:2022`, pinned `SHA256:6MPMP1TJ75QuFqne7qrvN4+7vMW4tFvokGhmIE74fls`, `canary.py` `245` lines (`§8 L373-375`) | `.github/workflows/enzonic-sftp-readonly-check.yml`, `tools/katabump-sqlite-canary/canary.py` | **EXACT MATCH** |
| `"OpenHandBot"` (`"Brave Grove"`) protections & `C3` SQLite exclusion (`§8 L378`) | `docs/DEPLOY_ENZONIC.md:27-42`, `docs/OHB2_ENZONIC_DEPLOYMENT_PREFLIGHT.md:10-12,370-374` | **EXACT MATCH** |
| OpenHands OpenAPI `v1.68.1` vs `v1.79.0` vs `v1.87.1` (`§8 L381`, `§14 L540`) | `docs/API_NOTES.md:81`, `bot/openhands_client.py:344`, `docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md:62,82` | **EXACT MATCH** |

---

## 9. Confirmation of Always-Blocked / Non-Decision Items

All six permanently blocked or excluded boundaries listed in Briefing `§12` (`L505–510`) were verified against project governance and environmental constraints:

1. **Mini App Modification Exclusion:** Verified — zero owner option in `OD-01`–`OD-05` authorizes modifying `bot/web/*`, `bot/web/static/*`, `tests/frontend/*`, `tests/test_miniapp_*.py`, `tests/test_real_http_miniapp_download.py`, `tests/_miniapp_helpers.py`, `docs/MINI_APP.md`, or `Config.mini_app_*`. (`REV-OD-05` notes the two extra Mini App test/helper paths for completeness).
2. **Live Enzonic Server (`"OpenHandBot"` / `"Brave Grove"`) Safety Lock:** Verified against `docs/DEPLOY_ENZONIC.md:27-42` and `docs/OHB2_ENZONIC_DEPLOYMENT_PREFLIGHT.md:10-12,370-374` — untouched under all `OD-05` options.
3. **`Stage B` Implementation (`B1–B3` / `DEF-015`):** Verified against `.agent/PROGRESS.md:20-36` — `OD-05` Option C authorizes *evaluation only*; code implementation remains blocked pending scoped upload credentials, static `Gate G1` SSRF allowlist, and a separate approved ADR.
4. **Local Backend `WP-09` Categories `1–3` & `5` Execution:** Verified — physically **`BLOCKED`** inside this container (`10/10` Python packages missing); requires CI / full `.venv` on `Python 3.11` & `3.13`.
5. **Prohibited Protocol Shortcuts:** Verified — no automatic poison skipping (`max+1`), no caption-text guessing (`D-34`), no invented byte-restore backup feature, and no false `exactly-once` external delivery claims appear in any option.
6. **Irreversible Historical DB/Disk Losses & `.git` Absence:** Verified — unlinked staging bytes and missing local `.git` metadata cannot be reconstructed by policy choices.

---

## 10. Briefing Findings Register (`REV-OD-*`)

| Finding ID | Severity | Briefing Location | Verified Evidence & Technical Discrepancy | Impact on Owner Decision Use |
|---|---|---|---|---|
| **`REV-OD-01`** | **`MEDIUM`** | `§4.B.1` (`L78`) | States: *"with `DEF-008` gap leaving `wait_for_start` exceptions stranded until fixed in `WP-05`"*. In Baseline `§C.1`, **`DEF-008`** is `deliver_outbox(outbox_id)` ignoring `outbox_id`/`mature_before`; the `CreationWorker` `wait_for_start` fallback gap (`bot/outbox.py:733-746,792-806`) is **`DEF-012`** (which Briefing `§10` `WP-05` at `L480` cites correctly). | **Non-blocking:** Does not change `OD-01` options or `WP-05` scope, though `L78` misidentifies `DEF-012` as `DEF-008`. |
| **`REV-OD-02`** | **`MEDIUM`** | `§5.D` Option A (`L187`, `L192`) & Option B (`L194-202`) | States that if `[N, N+1, ...]` contains `/updates_skip N confirm` at `N+1`, `/updates_skip` runs in `process_updates` and makes `N` skippable within that batch. Direct source review (`bot/polling.py:161-165`, `bot/db.py:2966-2988`) shows two critical constraints not mentioned: (1) sequential loop executes `N` *before* reaching `N+1`, so `N` will fail/run one additional time unless quarantined prior to dispatch; (2) `commit_batch_outcomes` calculates `acknowledgment_boundary` via `_outcome_in_txn`, which reads **only** `processed_updates` (not `update_failures`), so `/updates_skip` must explicitly write an eligible override outcome or integrate into `_outcome_in_txn` inside `WP-04` Part 2. | **Non-blocking for choosing `OD-02` Option A/B/C**, but critical technical caveat to capture under `WP-04` Part 2 acceptance/design tests if Option A or B is selected. |
| **`REV-OD-03`** | **`LOW`** | `§1` (`L14`), `§2`, `§10` (`L483`) | `L14` declares `27` distinct defects (`DEF-001`–`DEF-019` and `NEW-DEF-01`–`NEW-DEF-08`), yet `NEW-DEF-07` (`HIGH` doc-accuracy finding superseding 6 earlier audit reports per Baseline `§C.2` Group 2) is omitted (`0` occurrences in briefing; `WP-08` lists only `DEF-017, DEF-018, NEW-DEF-08`). | **Non-blocking:** Briefing already applies corrected Section B baseline facts (`17` tables, `Python 3.11.2`, `DEFERRED_FEATURES_HIDDEN=False`); minor traceability gap only. |
| **`REV-OD-04`** | **`LOW`** | `§6.B.1` (`L244`) | Cites `(bot/handlers.py:2008, bot/messages.py)` for `UNSUPPORTED_ATTACHMENT_TEXT`. Direct inspection shows `UNSUPPORTED_ATTACHMENT_TEXT` is defined in `bot/handlers.py:1603-1606`, and does not exist in `bot/messages.py:1-211`. | **Non-blocking:** `WP-01` (`NEW-DEF-06`) targets `bot/handlers.py:1603-1606, 2008` correctly. |
| **`REV-OD-05`** | **`LOW`** | `§2` (`L39`), `§10` (`L476`), `§12` (`L507`) | Mini App exclusion enumeration names `bot/web/*, bot/web/static/*, tests/frontend/*, tests/test_miniapp_*.py, docs/MINI_APP.md, Config.mini_app_*`, omitting explicit mention of `tests/test_real_http_miniapp_download.py` and `tests/_miniapp_helpers.py` (both explicitly excluded in Baseline `§A.2` and listed in Baseline `WP-09`). | **Non-blocking:** Read-only exclusion holds; adding those two filenames aligns with Baseline `§A.2`. |
| **`REV-OD-06`** | **`LOW`** | `§2` (`L38`) vs `§5.B.2` (`L170`) | `§2 L38` summarizes `ADR §28.4` referencing only lines `1055, 1115, 1171` (without citing `§18.6 L624-646` or noting that the ADR heading is `## 28)` bullet `4` at `L970-971`, and exact `/updates_skip <update_id> confirm` syntax comes from Baseline `WP-04`). `§5.B.2` (`L170`) does cite `§18.6` correctly. | **Non-blocking:** Purely citation precision in §2 summary table. |
| **`REV-OD-07`** | **`INFO`** | `§4.B.1` (`L79`) & `§10` (`L481`) | Two minor phrasing notes: (a) `L79` attributes `PARTIAL_OR_UNKNOWN` DB fallback to `bot/polling.py:180-200` (`collect_outcomes` returns `PARTIAL_OR_UNKNOWN` in memory; `Database.commit_batch_outcomes` at `bot/db.py:2977-2984` persists it); (b) `§10` `L481` classifies `WP-06` as `"Eligible for future authorization after prerequisites"` while flagging its `Gate 0` `callback_refs` Design Prerequisite inline, whereas `WP-04` and `WP-07` use `"Partially blocked"` for mixed gated/ungated WPs. | **Non-blocking:** Informative clarity observations only. |

---

## 11. Required Corrections Before Owner Decision Use

- **Mandatory Blocking Corrections Before Owner Decision Use:** **`0`** (none). The briefing's decision statements, options, risk disclosures, cross-decision dependencies, neutrality, and excluded boundaries are all accurate and safe for immediate owner review of `OD-01`–`OD-05`.
- **Recommended Non-Blocking Documentation Clarifications (if an optional future doc revision is authorized; NOT modified by this review):**
  1. Correct `DEF-008` -> **`DEF-012`** in `§4.B.1` (`L78`).
  2. Add the two `bot/polling.py:161-165` / `bot/db.py:2985-2988` same-batch `/updates_skip` pre-dispatch & `_outcome_in_txn` prerequisites explicitly to `OD-02` Option A/B (`L187`, `L192`).
  3. Reference `NEW-DEF-07` in `§10` (`WP-08`) / `§2` so all `27` baseline defect IDs are explicitly accounted for.
  4. Replace `bot/messages.py` with `bot/handlers.py:1603-1606` in `§6.B.1` (`L244`), include `tests/test_real_http_miniapp_download.py` and `tests/_miniapp_helpers.py` in Mini App exclusion lists, add `§18.6 L624-646` / `§28` bullet `4` (`L970-971`) to `§2` (`L38`), and clarify `commit_batch_outcomes` persistence (`L79`) + optional `WP-06` label consistency (`L481`).

---

## 12. Recommended Owner Decision Sequence Verification

Briefing `§13` (`L513–523`) recommends resolving decisions in four steps strictly by technical dependency:
1. **`OD-01` + `OD-03` paired first** -> Governs Phase 0 (`WP-01` / `Gate A`), directly interacting (`OD-03=True` + `OD-01=A` perpetuates `DEF-001`). **Verified accurate and optimal.**
2. **`OD-02` second** -> Allows Phase 1 (`WP-02 -> WP-03 -> WP-04` Part 1) prep and gates `WP-04` Part 2 / `Gate B` / `WP-08` schema parity (`send_reply_txt:1152` coupling). **Verified accurate.**
3. **`OD-04` third** -> Unblocks Phase 2b (`WP-07` / `Gate C`) concurrency vs sequential reconciliation after `WP-01`–`WP-04` stabilize polling/state semantics. **Verified accurate.**
4. **`OD-05` fourth** -> Keeps `WP-10` / `Gate D` / `Stage B` evaluation strictly decoupled until local/CI remediation (`Gates A–C`) finishes and isolated/external prerequisites are ready. **Verified accurate.**

No hidden option preference is implied by this ordering.

---

## 13. Mini App Scope Exclusion Verification

Verified zero edits to any Mini App artifact (`bot/web/*`, `bot/web/static/*`, `tests/frontend/*`, `tests/test_miniapp_*.py`, `tests/test_real_http_miniapp_download.py`, `tests/_miniapp_helpers.py`, `docs/MINI_APP.md`, `Config.mini_app_*`):
- All `23` `tests/frontend/*.test.js` files executed read-only cleanly (`280/280` passing on `Node v22.23.2`).
- Read-only inspection of `bot/web/services.py:758-870` confirms the briefing accurately models `MT-2`'s dependency on `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` (`OD-03`), `pending`/`stored` status requirements, and the `now > T0 + 15m` (`bot/web/services.py:805,850`) vs `now >= T0 + 15m` (`bot/db.py:1334,1360,1429,1624`) boundary distinction without proposing any Mini App modification.
- Minor completeness note logged under `REV-OD-05` for `tests/test_real_http_miniapp_download.py` and `tests/_miniapp_helpers.py`.

---

## 14. Git / Environment / External-Infra Evidence & Limitations

All verification boundaries are reported transparently without inference:

1. **Git Metadata (`GIT STATE UNVERIFIED`):** `.git` does not exist in `/app/applet` (`ls: cannot access '.git': No such file or directory`). Local branch, `HEAD` commit hash, prior diffs, and remote CI logs cannot be verified from Git.
2. **Backend Python Environment (`BLOCKED` Locally):** `python3 --version` is `3.11.2`; `165/165` `.py` files pass syntax-only `ast.parse` (`0` errors). All `10/10` packages in `requirements.txt` and `requirements-dev.txt` (`telegram`, `httpx`, `starlette`, `uvicorn`, `dotenv`, `anyio`, `pytest`, `pyflakes`, `bandit`, `pip_audit`) are absent; therefore **`WP-09` Categories `1`, `2`, `3`, and `5` are `BLOCKED`** in this container.
3. **Frontend Unit Suite (`PASS`, Read-Only):** `node --test tests/frontend/*.test.js` on `Node v22.23.2` executed `280` tests across `23` `*.test.js` files -> **`280 pass / 0 fail / 0 skipped`** (`WP-09` Category `4` only; proves nothing about Python backend or WebView runtime).
4. **Root Runbook Path Note:** Prompt references `OPERATIONS_RUNBOOK.md`; actual repository path is `docs/OPERATIONS_RUNBOOK.md` (no `OPERATIONS_RUNBOOK.md` at workspace root).
5. **External Infrastructure & Devices (`NOT_RUN` / `UNVERIFIED`):** Enzonic SFTP fingerprint & `.github/workflows/enzonic-sftp-readonly-check.yml`, live `H1` SQLite canary (`tools/katabump-sqlite-canary/canary.py`), `HOST-01`/`HOST-02` hosting/TLS, physical Android 12 `MT-2` download testing, and live OpenHands Cloud OpenAPI schema verification remain unexecuted externally.
6. **Secrets & Live Targets:** Zero `.env` secrets, SSH keys, or live server panels were read, printed, or accessed.

---

## 15. Explicit Confirmation of Prohibited Operations Not Performed

Confirmed directly for this review task (`OHB2-OWNER-DECISIONS-BRIEFING-INDEPENDENT-REVIEW`):
- **Zero existing files modified, renamed, deleted, or reformatted** (including `docs/audits/OHB2-OWNER-DECISIONS-BRIEFING.md`, `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md`, `bot/`, `tests/`, `docs/MINI_APP.md`, ADRs, decision registers, config files, and `.openhands/`).
- **Zero implementation fixes written** (`WP-01`–`WP-10` untouched).
- **Zero owner decisions selected or recorded** (`OD-01`–`OD-05` remain `PENDING_OWNER_DECISION`).
- **Zero Mini App edits** (`0` files modified in `bot/web/*`, `tests/frontend/*`, `tests/test_miniapp_*.py`, `tests/test_real_http_miniapp_download.py`, `tests/_miniapp_helpers.py`, `docs/MINI_APP.md`, `Config.mini_app_*`).
- **Zero dependency installations, DB migrations, batch cleanups, deployments, external network calls, Git commands (`commit`/`push`/`PR`/`merge`), or Autopush activations performed.**

---

## 16. Independent Verdict & Safe-To-Use Determination

- **Independent Verdict:** **`PASS_WITH_NOTES`**
- **Safe-To-Use Determination:** **`SAFE_FOR_OWNER_DECISION_USE`**
  - An owner reviewing `OD-01` through `OD-05` receives accurate source facts, complete and unbiased policy options, transparent reversibility and deferral risks, intact Mini App and live-Enzonic protections, and honest local/CI verification boundaries.
  - Before executing `WP-04` Part 2 (if `OD-02` Option A or B is chosen), implementers should incorporate the `REV-OD-02` same-batch pre-dispatch/`_outcome_in_txn` requirement alongside correcting the `DEF-012` ID (`REV-OD-01`) in future documentation syncs.

---

## 17. Summary Checklists / Owner Sign-Off Readiness

| Decision | Options Presented Neutrally? | Baseline Alignment | Preselected / Biased? | Ready for Explicit Owner Sign-Off? | Current Status |
|---|---|---|---|---|---|
| **`OD-01`** (`D-34` & Uncertain Outcomes) | Yes (`A`, `B`, `C`) | Aligned (`REV-OD-01` `DEF-012` ID typo non-blocking) | No | **YES** | `PENDING_OWNER_DECISION` |
| **`OD-02`** (`ADR §28.4` Poison Policy) | Yes (`A`, `B`, `C`) | Aligned (`REV-OD-02` same-batch nuance documented) | No | **YES** | `PENDING_OWNER_DECISION` |
| **`OD-03`** (`INTAKE_ENABLED` vs `MT-2`) | Yes (`A`, `B`) | Aligned (`REV-OD-04` line ref minor) | No | **YES** | `PENDING_OWNER_DECISION` |
| **`OD-04`** (`TelegramPoller` Concurrency) | Yes (`A`, `B`) | Exact Match | No | **YES** | `PENDING_OWNER_DECISION` |
| **`OD-05`** (External Qual & `Stage B`) | Yes (`A`, `B`, `C`) | Exact Match | No | **YES** | `PENDING_OWNER_DECISION` |

---

## 18. References Verified

1. `docs/audits/OHB2-OWNER-DECISIONS-BRIEFING.md` (`L1–544`, SHA-256 `8974a3b991f2ed32a5547b8db85f3d6e40c0160ce683cfcb10d1ca6f35599c45`)
2. `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md` (`L1–806`, SHA-256 `e7b98175d66bb118e437a75380622e09392998bcc9f754d3f48c26f4f5709a6f`)
3. `docs/audits/OHB2-INDEPENDENT-AUDIT-REPORT-VALIDATION.md` (`L1–208`)
4. `docs/proposals/OHB2-TELEGRAM-ACK-ARCHITECTURE-ADR.md` (`§18.5–§37`, `L615–1184`)
5. `docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md` (`D-34`, `D-34/J`, `D-35`, `D-15`)
6. `docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md` (`v1.87.1` schema citations)
7. `docs/OPERATIONS_RUNBOOK.md` (`L1–160`), `docs/DEPLOY_ENZONIC.md` (`L1–70`), `docs/OHB2_ENZONIC_DEPLOYMENT_PREFLIGHT.md` (`L1–426`), `docs/OHB2_HOSTING_DECISION.md` (`L1–358`), `docs/reviews/OHB2-MT2-COMPLETION-AND-ADVERSARIAL-VERIFICATION.md` (`L1–174`)
8. `.agent/PROGRESS.md` (`L1–561`), `.env.example` (`L1–20`), `.github/workflows/enzonic-sftp-readonly-check.yml` (`L1–126`), `tools/katabump-sqlite-canary/canary.py` (`L1–245`)
9. Application source files: `bot/config.py`, `bot/update_outcomes.py`, `bot/features.py`, `bot/messages.py`, `bot/app.py`, `bot/polling.py`, `bot/outbox.py`, `bot/db.py`, `bot/handlers.py`, `bot/attachments.py`, `bot/openhands_client.py`, `bot/web/services.py`
10. Read-only Mini App exclusion/test paths: `tests/_miniapp_helpers.py`, `tests/test_real_http_miniapp_download.py`, `tests/frontend/*.test.js`
