# OHB2-REVIEW-PLAN08-DESIGN-REMEDIATION — Second Independent Adversarial Review

- **Task ID:** `OHB2-REVIEW-PLAN08-DESIGN-REMEDIATION`.
- **Type:** Second independent, adversarial, read-only review.
- **Remediation task under review:** `OHB2-REMEDIATE-PLAN08-MANUAL-ATTACHMENT-TRANSFER-DESIGN`.
- **Corrected design under review:** `docs/reviews/OHB2-PLAN-08-MANUAL-ATTACHMENT-TRANSFER-UX-DESIGN.md`
  (SHA-256 `0914609f3680aeefafa191b641631b6ed12a26a7d5434bc5bfa77f7e75ed6009`, 812 lines).
- **Original independent review (immutable):**
  `docs/reviews/OHB2-REVIEW-PLAN08-MANUAL-ATTACHMENT-TRANSFER-UX-DESIGN.md`
  (SHA-256 `71cc88c8f2cddc74867bb8809c2e7c897cb18ecf081c87f345772f52003f3bc5`, 406 lines).
- **Previous review verdict:** `NEEDS_REMEDIATION`.
- **Remediation verdict reported by the implementation agent:**
  `REMEDIATION COMPLETE WITH OPEN OWNER DECISIONS`.
- **Reviewer:** OpenHands agent (autonomous, independent). Date: 2026-11-15.
- **Verdict:** **`PASS_WITH_NOTES`**.

> Evidence labels: **[F] independently verified this session** · **[I] inference** ·
> **[U] unverified** · **[G] documented-but-untested** · **[R] recommendation** ·
> **[OWNER] owner decision**.

> **A favorable verdict is NOT implementation authorization.** This review selects no retrieval
> mechanism and resolves no owner decision. D-22 (and the scope/wording decisions) remain open.

---

## 1. Task ID and verdict

**Task ID:** `OHB2-REVIEW-PLAN08-DESIGN-REMEDIATION`.

**Verdict: `PASS_WITH_NOTES`.** All material remediation findings raised by the first review
(F-01, F-02, F-03, F-04, S-7, S-8, S-13, and the LOW/INFO items F-05, F-06, F-07) are **closed**
against the current source. The corrected design's factual base, outbox contract, MT comparison,
terminology, security classification, and Arabic UX wording are **independently verified**. No
BLOCKER, HIGH, or MEDIUM defect remains. Two **LOW** documentation-precision notes (R-1, R-2) and
two **INFO** notes (R-3, R-4) remain; none affect a material conclusion, and all owner decisions
remain explicitly open.

`PASS_WITH_NOTES` **does not** approve MT-1, MT-2, MT-3, remote delivery, or any owner decision.

---

## 2. Review scope and authorization boundary

**Authorized (per task):** inspect the repository and reports; independently verify source claims
and remediation changes; run safe non-production tests; create this review report; append a factual
entry to `.agent/PROGRESS.md`.

**Not authorized (and not done):** implementing MT-1/MT-2/MT-3; modifying the corrected Plan 08
document; modifying the original independent review; modifying runtime/frontend/test/schema/
migration/config/dependency/deployment files; resolving D-22/D-12/D-15/D-16 or any owner decision;
selecting MT-1/MT-2; starting remote-delivery Stage B1/B2/B3; starting Plan 07-B/07-C;
commit/push/PR/merge/release/deploy/Autopush.

**Files created/modified by this review (only two):**
1. `docs/reviews/OHB2-REVIEW-PLAN08-DESIGN-REMEDIATION.md` (this file, new).
2. `.agent/PROGRESS.md` (append-only entry).

Nothing else was written, staged, committed, or deleted.

---

## 3. Independent Git baseline and file hashes

Independently measured **before** reviewing (not copied from the remediation report):

| Item | Value | Command |
| --- | --- | --- |
| Branch | `main` | `git branch --show-current` |
| HEAD | `facf1f42578a20a4a37e220eca016ce3d534e750` | `git rev-parse HEAD` |
| `main` | `facf1f42578a20a4a37e220eca016ce3d534e750` | `git rev-parse main` |
| `origin/main` | `facf1f42578a20a4a37e220eca016ce3d534e750` | `git rev-parse origin/main` |
| Divergence | `0  0` | `git rev-list --left-right --count origin/main...HEAD` |
| Staged | none | `git diff --cached --name-only` |
| Unstaged | `.agent/PROGRESS.md` (` M`) | `git status --short` |
| Untracked | **6** review docs (Plan 05, 06, 07-A, 07-A2, **corrected Plan 08**, **original review**) | `git ls-files --others --exclude-standard` |
| Ignored (relevant) | `.openhands/`, `.pytest_cache/` | `git status --short --ignored` |
| `.openhands/` present | yes; unchanged (mtime `2026-11-14 16:27:11`) | `stat -c '%y' .openhands` |
| `MINI_APP_ENABLED` | default `False` | `bot/config.py:262` |
| `concurrent_updates(True)` | present, unchanged | `bot/app.py:86` |
| Autopush | no `autopush`/`main.py` process running | `ps aux` |
| `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` | default `True` | `bot/config.py:315–316` |

**[F] File hashes (independently recomputed):**

| Report | Lines | SHA-256 |
| --- | --- | --- |
| Plan 05 | 428 | `4944714a3469894a01093619a2b75072eb65b403eb3df665db520b35c857e676` |
| Plan 06 | 617 | `4450b77cb9981d4997a4f7cb41f3cb3e4821aad93d4d74b7ea982bedd1920303` |
| Plan 07-A | 509 | `8faec96b3c4844fb36d5b793b72fce340f837a3e2aa67a2cbee2d3a6a5e88d90` |
| Plan 07-A2 | 451 | `8aa583d2a315af60f69e5f7aa55959d44f9df6afb0f84f8306937b3bac1dffbc` |
| **Corrected Plan 08 (reviewed here)** | **812** | **`0914609f3680aeefafa191b641631b6ed12a26a7d5434bc5bfa77f7e75ed6009`** |
| **Original review (immutable)** | **406** | **`71cc88c8f2cddc74867bb8809c2e7c897cb18ecf081c87f345772f52003f3bc5`** |
| `.agent/PROGRESS.md` (before this entry) | — | `5f15036420478a6d644ae5783ca1701622bde3471f7f2a59a06b05b99605386c` |

The Plan 05/06/07-A/07-A2 hashes match the corrected design's §3.2 table exactly. The original
review is **byte-for-byte unchanged** from the value it self-records (`71cc88c8…`), i.e. the
remediation did **not** rewrite historical findings. **[F]** the corrected design's §3.2
"pre-remediation" Plan 08 hash `18b29203…` matches the hash the original review recorded for its
target — consistent.

**Ownership of pre-existing changes:** the modified `PROGRESS.md` and the untracked reports are
pre-existing agent artifacts. This review preserved all of them untouched. Nothing was cleaned,
reset, restored, staged, or deleted.

---

## 4. Evidence set inspected

Read in full or in the cited ranges:

1. `AGENTS.md` (rules; Arabic reports; no-implementation discipline).
2. `.agent/PROGRESS.md` (pre-existing entries + remediation entry).
3. Corrected Plan 08 design report (812 lines) — read in full.
4. Original independent review (406 lines) — read in full.
5. Plan 05, Plan 06, Plan 07-A, Plan 07-A2 reports (headers/summary + referenced lines).
6. `docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md` (D-22 `:1042–1060`, D-12 `:158`, D-15
   `:161`, D-16 `:162`, §6.3 `:1908–1918`, §7 `:1920–1945`, B1–B3 `:710`, `:1236`).
7. `docs/proposals/OHB2-P0-STAGED-IMPLEMENTATION-PLAN.md` (Stage B1 `:739`, B2 `:756`, B3 `:768`).
8. Source: `bot/attachments.py`, `bot/handlers.py`, `bot/db.py`, `bot/outbox.py`,
   `bot/openhands_client.py`, `bot/app.py`, `bot/sender.py`, `bot/config.py`, `bot/watcher.py`,
   `bot/web/app.py`, `bot/web/services.py`, `bot/web/static/*.js`, `bot/files.py`,
   `docs/MINI_APP.md`, `tests/frontend/dom_stub.js`, `tests/`.

All material claims were resolved against **current source**, not against the remediation report's
own citations.

---

## 5. Summary of the first review's findings

The first review (`NEEDS_REMEDIATION`) identified: **HIGH** — F-01 (unverified "20 MB" stated as
fact), F-04 (undisclosed B1/B2/B3 naming collision), S-13 (no message distinguishes local vs
remote); **MEDIUM** — F-02 (understated B1 architectural prerequisite / D-22), F-03 (B1-first
asserted not derived), S-7/S-8 (future race/duplicate risks flagged but no mitigation design);
**LOW** — F-05 (imprecise citations), F-06 (severity/status conflation); **INFO** — F-07 (nonexistent
"تنزيل الملف" button). It also required (§12) F-01/F-04/F-02/F-03/S-13/F-05/F-06 corrections.

**Note on "F-08":** the first review contains **no** finding literally labelled `F-08`
(`grep -c "F-08"` = 0). The corrected design's §18 lists a row `F-08/§15 no remediation
traceability`. That row maps to the first review's **§12 remediation list / §15 confirmation**
(process completeness), not to a numbered first-review finding. This is a benign traceability label,
not a fabricated finding. **INFO (R-4).**

---

## 6. F-01 … F-07 verification matrix

| Finding | First review asked | Corrected design (section) | Independent source check | Status |
| --- | --- | --- | --- | --- |
| **F-01** (HIGH) unverified "20 MB" | Cite a source or restate as `[U]`; base the bound on enforced `MAX_ATTACHMENT_BYTES=3 MiB` | §5: claim **withdrawn**; table L1–L7; L5 = `[U]`; no external limit asserted | `MAX_ATTACHMENT_BYTES = 3*1024*1024` (`attachments.py:99`); no `20 MB`/`20971520` in `bot/`; the only 20 MB text is proposal-only (`OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md:317,602`); `TELEGRAM_DOCUMENT_MAX_BYTES=50 MiB` (`sender.py:19–20`) | **CLOSED** |
| **F-02** (MEDIUM) understated B1 prerequisite / D-22 | State B1 is blocked by D-22 and needs a schema/mechanism change | §6.1 outbox contract; §6.2 alternatives A/B; §6.3 D-22 blocks MT-1 | outbox schema has no payload/kind (`db.py:608–621`); dispatch = `client.send_message` → OpenHands (`openhands_client.py:337–339`); D-22 unresolved, blocking (`register:1042–1060`, §6.3 `:1908–1912`) | **CLOSED** |
| **F-03** (MEDIUM) B1-first asserted | Add a trade-off table; derive rather than assert | §7 comparison matrix; §8 trade-off table; recommendation withdrawn | No route reads `attachment_staging`; `_guarded`/`_attachment` exist (`app.py:432`, `:95`); no `Range`/206 in `bot/web/` | **CLOSED** |
| **F-04** (HIGH) naming collision | Disambiguate Plan 08 B1/B2/B3 vs register Stage B1/B2/B3 | §9 glossary: **MT-1/MT-2/MT-3**; remote stages distinct and `NOT AUTHORIZED` | register `:710`/`:1236` (`B1–B3 NOT AUTHORIZED`); staged plan `:739`/`:756`/`:768` = remote stages; corrected doc uses MT-* throughout | **CLOSED** |
| **F-05** (LOW) imprecise citations | Tighten citations | §4.2 identity table `db.py:804–813`, D-33 `:797–803` | `attachment_message_identity` DDL `db.py:804–813` (`PRIMARY KEY (telegram_id,chat_id,message_id)`, FK `ON DELETE RESTRICT`); D-33 comment `:797–803` | **CLOSED** |
| **F-06** (LOW) severity/status conflation | Split columns | §11 splits **Severity** vs **Status**; future risks labelled | matches S-7/S-8 "NOT MITIGATED (future)" intent | **CLOSED** |
| **F-07** (INFO) nonexistent button | Mark as future | §10.2/§10.4/§19 mark controls **PROPOSED — NOT IMPLEMENTED** | no staged-download control in `bot/web/static/*.js`; only export button `⬇️ تصدير الشات` (`app.js:1031`) | **CLOSED** |

---

## 7. S-7 — retrieval/cleanup race verification

§13 presents a 9-case table covering: (1) request before expiry, (2) cleanup during authorization,
(3) cleanup after auth before open, (4) cleanup while reading, (5) crash during retrieval,
(6) file change between lookup and open, (7) expiry while an operation is queued, (8) concurrent
retrieval, (9) open-fd-after-unlink. For each it states existing behavior, `Reachable? = Y-future`,
impact, and the needed invariant/decision. **[F]** it explicitly states **every race is currently
unreachable** because no retrieval path exists (grep: no `attachment_staging` reads outside
`attachments.py`/`db.py`). **[F]** it states **"Restrictive file permissions do NOT solve this
race"** — matching the first review's warning. Proposed mitigations are compatible with the single
SQLite owner (reuse the DB-first reaper), introduce **no** new worker/scheduler/process/schema, and
require a durable op only for MT-1. **Verdict: adequate; S-7 CLOSED as a design treatment** (the
underlying implementation risk legitimately remains an owner/design item). No new defect.

---

## 8. S-8 — duplicate/uncertain Telegram send verification

§14 presents a 12-case table matching the required cases exactly (double-tap, duplicate update,
concurrent requests, crash before/after op creation, crash mid-transmission, Telegram-accepts-but-
unrecorded, definite rejection, timeout/unknown, expiry-while-pending, retry-after-unknown,
new-send-after-unknown). **[F]** it states **no exactly-once claim**, **no assumed Telegram
idempotency key**, and reuses the existing at-most-once CAS/`unknown` semantics only for the
mechanical cases (4–9), flagging cases 1/10/11/12 as new owner decisions. **[F]** the described
outbox semantics match source: `pending→claimed→sending` CAS (`db.py:3346`), `_post_claimed`
(`outbox.py:298`), single POST (`outbox.py:452`), `failed` on 4xx vs `unknown` otherwise, and
`CancelledError`→`unknown` **with re-raise** (`outbox.py:472–478`). **S-8 CLOSED.** No invented
retry policy or operation state. Minor citation nit: the doc cites `outbox.py:447–470` while the
`CancelledError` block is at `472–478` — non-material (**INFO R-3**).

---

## 9. S-13 — Arabic UX and state-precision verification

§10 gives eight Arabic blocks (§10.1–§10.8) plus a conceptual-label table (§10.8). **[F]** the
wording keeps the required events distinct: local staging success ≠ Telegram API acceptance ≠ user
download ≠ OpenHands upload ≠ verified remote delivery. **[F]** §10.3/§10.4 never claim OpenHands
received the file; §10.5/§10.6 make no false "still available" claim; §10.7 states the honest
limitation. **[F]** the six labels (`LOCAL_STAGED`, `RETRIEVAL_AVAILABLE`, `TELEGRAM_SEND_ACCEPTED`,
`USER_DOWNLOAD_COMPLETED`, `USER_ASSERTED_OPENHANDS_UPLOAD`, `REMOTE_DELIVERY_VERIFIED`) are
explicitly declared **conceptual UX labels, not database states**, and **no** new state/column/
transition is added. **[F]** §10.1 conditions "خزّنته محليًّا" on `stored` (not on `ACCEPTED`),
satisfying the first review's §9 item 1. The current shipped text (`ATTACHMENT_ACCEPTED_TEXT`,
`handlers.py:1601`) still lacks the "not uploaded" qualifier — correctly noted as the open wording
decision. **S-13 CLOSED** (design); wording approval remains `[OWNER]`.

---

## 10. Current source and outbox contract verification

- **[F]** Outbox schema (`db.py:608–621`): `(id, conversation_id, chat_id, text, status, error,
  created_at, updated_at, attempts, client_ref, notify_state)` — **no payload/blob column, no
  kind column**. Text-only.
- **[F]** Dispatch target: `client.send_message(conversation_id, text)` → `POST
  /app-conversations/{id}/send-message` on **OpenHands** (`openhands_client.py:337–339`), **not**
  Telegram.
- **[F]** Status constants (`db.py:67–73`) include `discarded`; the corrected design's illustrative
  transition list omits `discarded` but correctly centres on `pending/claimed/sending/sent/unknown`.
  Non-material (informational completeness only).
- **[F]** Telegram document sending exists (`send_document`/`InputFile`: `handlers.py:1460`,
  `:1559`; `sender.py:31`, `:71`) but is **in-memory and unrelated to staged bytes**; the outbox
  itself has **no** document path. **[F]** No `file_id`/MIME columns exist in `db.py`.
- **[F]** No route reads `attachment_staging/` (repo-wide grep).
- **[F]** `delivered` and `dispatching/uncertain/rejected/failed` are **defined but never written**
  in runtime code (constants only, `db.py:121–137`); `delivered` is unreachable.

**Conclusion:** the corrected design's §6 outbox contract is **accurate**. MT-1 genuinely requires a
separately approved durable Telegram-document operation; D-22 remains open. No new worker/
scheduler/process/second-SQLite-owner/exactly-once claim is introduced.

---

## 11. MT-1 / MT-2 / MT-3 comparison review

**[F]** §7.4 matrix is evidence-backed and status labels match source:
- MT-1: `send_document`/`InputFile` exist; outbox incompatible as-is; needs a durable op + D-22.
- MT-2: `_guarded` (`app.py:432`) + `_attachment` (`app.py:95`) reusable; **new cookie-auth route**;
  **no** schema change; no existing route reads staged bytes.
- MT-3: `file?path=` = text preview of existing workspace files (`MINI_APP.md:649`); `reply` =
  `.txt` of the assistant reply; no staged-byte flow ⇒ `NOT FEASIBLE`. No invented option.

**Challenge to "MT-2 has smaller architectural impact":** verified as **source-backed and correctly
scoped** — MT-2 needs **no** schema/D-22 change (it adds a route + frontend), whereas MT-1 needs a
durable op. The design does **not** treat MT-2 as decision-free: §8 and §17 explicitly gate it on a
**scope** decision **and** `UNVERIFIED` real Telegram Android WebView behavior. **[F]** the WebView
claim is honest: the only Blob-download exercise is the Node DOM stub
(`tests/frontend/dom_stub.js:336–342`). **No winner is declared** (§8: "does not declare either
option approved or preferable overall"), which matches the first review's requirement. **F-03
CLOSED.**

---

## 12. Cross-document and architecture consistency

- **[F]** Manual local transfer = temporary path; provider-verified delivery (U-12/U-3/D-04/D-06/
  D-02/D-03) = long-term goal; best-effort automatic delivery rejected (§1, §2, §12). Unchanged.
- **[F]** D-22 unresolved; D-12/D-15/D-16 represented with their real scope (§17).
- **[F]** One Bot + ASGI process, one SQLite owner, existing outbox/workers only — no new owner/
  scheduler/service introduced by the design (§6.2, §13).
- **[F]** `concurrent_updates(True)` preserved (`app.py:86`); `MINI_APP_ENABLED` disabled
  (`config.py:262`); Autopush inactive.
- **[F]** Remote-delivery Stage B1/B2/B3 remain `NOT AUTHORIZED` (register `:710`/`:1236`; staged
  plan `:739`/`:756`/`:768`); Plan 07-B/07-C remain unauthorized (§2, §22).
- **[F]** Secure Pull is not claimed implemented; the design references only existing local staging.

**Minor documentation note (R-1):** §3.1 says *"the five untracked reports"* but the working tree now
has **six** untracked reports (the corrected Plan 08 **and** the original review are both untracked,
plus 05/06/07-A/07-A2). The phrase is a carry-over from the pre-remediation state. **LOW /
documentation-only.** **INFO (R-2):** §20's "3 in-memory call sites" for `send_document`/`InputFile`
is an undercount of the raw grep (there are 4 `send_document` invocations: 2 in `handlers.py`, 2 in
`sender.py`); the claim's substance ("in-memory, unrelated to staged bytes") is correct.

---

## 13. Owner-decision matrix (as stated in the corrected design §17)

| Decision | Stated scope | Blocks | Status | Review note |
| --- | --- | --- | --- | --- |
| **D-22** | Durable Telegram-document operation vs approved alternative | MT-1 design + implementation | **OPEN** | [F] register `:1042–1060`; blocking (§6.3) |
| **D-12** | size/type quota triple scope | wording + bounds | **OPEN** | [F] `attachments.py:99`,`:105–106`; register `:158` |
| **D-15** | fixed 15-min window; no server batch | MT-1 expiry handling | **OPEN** | [F] `db.py:261`; register `:161` |
| **D-16** | idempotency/dedup window for retried send-back | MT-1 (§14 cases 11–12) | **OPEN** | [F] register `:162` |
| Option selection | MT-1 vs MT-2 (or both) | both | **OPEN** | not resolved here |
| Scope | one or both manual paths | both | **OPEN** | not resolved here |
| Wording | exact Arabic copy (§10) | both (runtime activation) | **OPEN** | not resolved here |
| WebView verification | real Telegram Android WebView download | MT-2 | **OPEN** | [F] only DOM-stub evidence |
| Any new schema/architecture | discovered during comparison | MT-1 | **OPEN** | not resolved here |

**No owner decision is resolved or inferred by this review.** D-22 is the gating item for MT-1.

---

## 14. All remaining findings, grouped by severity

### BLOCKER — NONE FOUND
Scope inspected: the corrected design's factual base, outbox contract, MT comparison, terminology,
security model, Arabic wording, and owner-decision matrix — all against current source. No
implementation exists, and no factual/security/architectural defect of blocking severity was found.

### HIGH — NONE FOUND
Scope inspected: F-01 (size), F-04 (naming), S-13 (wording). All independently verified corrected.

### MEDIUM — NONE FOUND
Scope inspected: F-02 (D-22 blocker), F-03 (comparison), S-7/S-8 (future risks). All addressed and
correctly classified as future/owner items.

### LOW

- **R-1 — §3.1 "five untracked reports" is stale (six now).**
  - Severity: **LOW** (documentation-only).
  - Location: corrected design §3.1.
  - Evidence: `git ls-files --others --exclude-standard` returns 6 files.
  - Impact: minor internal-precision mismatch; no material consequence.
  - Required correction: say "six untracked reports" (or "the untracked reports").
  - Owner approval: no.

- **R-2 — §20 "3 in-memory call sites" undercounts `send_document` invocations.**
  - Severity: **LOW** (documentation-only).
  - Location: corrected design §20.
  - Evidence: 4 `send_document(...)` invocations (`handlers.py:1460`,`:1559`; `sender.py:31`,`:76`).
  - Impact: none on conclusions (substance is correct).
  - Required correction: state "in-memory; unrelated to staged bytes" without a precise count, or
    correct the count.
  - Owner approval: no.

### INFO

- **R-3 — `CancelledError` citation range.** §6.1 cites `outbox.py:447–470`; the `CancelledError`
  block is `outbox.py:472–478`. Substance correct.
- **R-4 — "F-08" label.** §18 lists `F-08/§15` which has no counterpart in the first review (which
  has no F-08). Benign traceability label for the §12/§15 process items.

---

## 15. Exact source references

- Size limits: `bot/attachments.py:99` (`MAX_ATTACHMENT_BYTES = 3*1024*1024`), `:105–106`
  (quotas, disabled by default), `:332`,`:468` (default `max_bytes`), `:569` (`_effective_cap`);
  `bot/sender.py:19–20` (`TELEGRAM_DOCUMENT_MAX_BYTES = 50*1024*1024`);
  `bot/openhands_client.py:28,34`; `bot/web/services.py:53`; `bot/handlers.py:1878`.
- Outbox: `bot/db.py:608–621` (schema), `:67–73` (status constants), `:3346` (`claim_outbox`),
  `bot/outbox.py:298` (`_post_claimed`), `:452` (POST), `:472–478` (`CancelledError`),
  `bot/openhands_client.py:337–339` (`send_message` → OpenHands).
- Staging/lifecycle: `bot/attachments.py:108–111`, `:199`, `:204`, `:212`, `:284`, `:322–325`,
  `:585–594`, `:609`, `:704`, `:718–740`, `:815`, `:822`, `:865–871`, `:1020`, `:1128`, `:1316`,
  `:1334`, `:1376`, `:1432`; `bot/db.py:121–137`, `:171–175`, `:261`, `:797–813`, `:1224`,
  `:1463`, `:1630`; `bot/app.py:86`, `:159`, `:227–241`, `:265`; `bot/watcher.py:182–183`.
- Web/auth: `bot/web/app.py:95–108`, `:432–451`, `:733–751`, `:1110`; `bot/web/static/app.js:1031`.
- Identity: `bot/db.py:804–813` (PK + `ON DELETE RESTRICT`); no `file_id`/MIME columns.
- Decisions: `docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md:158`, `:161`, `:162`, `:710`,
  `:1236`, `:1042–1060`, `:1908–1918`, `:1920–1945`;
  `docs/proposals/OHB2-P0-STAGED-IMPLEMENTATION-PLAN.md:739`, `:756`, `:768`;
  `docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md:317`, `:602`.

---

## 16. Independent tests and validation results

All commands were **executed by this reviewer** on the current tree. Python 3.13; no code was
modified to make any test pass. **No production API, credential, real attachment, or real Telegram
document was used.**

| Command | Exit | Result |
| --- | --- | --- |
| `python -m pytest tests/test_attachment_staging_a1.py tests/test_attachment_batch_lifecycle_a2.py tests/test_attachment_cleanup_expiration_a4.py tests/test_repair_plan_01_resource_staging.py tests/test_attachment_intent_a3.py tests/test_attachment_message_identity_a3.py tests/test_attachment_batch_schema.py tests/test_unsupported_attachment_rejection.py -q` | 0 | **245 passed** |
| `python -m pytest -q -k "outbox or repair_plan_02"` | 0 | **301 passed, 2759 deselected** |
| `python -m pytest -q` (full suite) | 0 | **3060 passed**, 72 warnings |
| `python -m pyflakes bot/ automation/ tools/ main.py tests/` | 0 | **0 issues** |
| `node --test tests/frontend/*.test.js` | 0 | **250 pass, 0 fail** |
| `grep -rn "20 MB" bot/ docs/` | 0 | only proposal text (`OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md:317,602`) |
| `grep -rn "attachment_staging" bot/` | 0 | no staged-byte reads outside `attachments.py`/`db.py` |
| `grep -rnE "Range\|206" bot/web/` | 0 | none (matches §7.2) |

**Provenance:** these are **independently rerun** by this reviewer (not copied). Source-inspection-
only items (crash windows, real Telegram WebView behavior) remain `[U]`. The remediation task itself
was documentation-only and correctly claimed no runtime test run.

**Note (environment):** the full suite passes cleanly here (3060) with dependencies installed in
user-site, unlike the first review which needed a system-wide install for one deploy-manifest test.
No test failure was observed by this reviewer.

---

## 17. Is the corrected design internally consistent?

**Yes, materially.** All 22 numbered sections are present and cross-references resolve to the correct
sections (`§1–§22`). No contradictory statements were found between the withdrawn-recommendation
language (§1, §8) and the comparison matrix (§7.4); no stale "20 MB" claim remains except the explicit
withdrawal; MT-* terminology is used consistently with no ambiguous manual-option B1/B2/B3 usage; the
verdict line and §17 agree that owner decisions remain open. The only inconsistencies are the two
**LOW** documentation-precision notes (R-1, R-2) and two **INFO** nits (R-3, R-4), none of which
change any conclusion.

---

## 18. Is it ready to present to the owner for decisions?

**Yes.** The corrected design is source-backed, accurately scoped, and honestly presents the
trade-offs without selecting a winner. It is suitable for owner review **as a decision input**. It is
**not** a decision and **not** an authorization.

---

## 19. May any implementation plan be prepared, and under what authorization?

- **MT-1:** No — blocked by **D-22** (owner) plus scope and wording decisions.
- **MT-2:** No — gated by the **scope** decision and by `UNVERIFIED` real Telegram Android WebView
  behavior; not decision-free.
- **Remote delivery (Stage B1/B2/B3) / Plan 07-B / 07-C:** No — `NOT AUTHORIZED`.
- A future implementation plan may be prepared **only after** the owner resolves D-22, the scope,
  and the §10 wording, **and** grants separate, explicit implementation authorization for the chosen
  option. Preparing P0 (wording) alone still requires owner wording approval.

---

## 20. Explicit statement — no implementation

**[F]** This review performed **no implementation**. No runtime code, frontend code, tests, DB
schema, migrations, configuration, dependencies, or deployment files were modified. The only
artifacts created/changed are this review report and an **append-only** `.agent/PROGRESS.md` entry.
**No** commit, push, PR, merge, release, deployment, or Autopush activation occurred. The corrected
Plan 08 design, the original review, and the Plan 05/06/07-A/07-A2 reports are **byte-for-byte
unchanged** (hashes §3). No file was staged; `.openhands/` remains untouched.

---

> Evidence labels recap: **[F]** independently verified · **[I]** inference · **[U]** unverified
> · **[G]** documented-but-untested · **[R]** recommendation · **[OWNER]** owner decision.
