# OHB2 — P0 Staged Implementation Plan (secure conversation attachment workflow)

- **Task ID:** `OHB2-P0-STAGED-IMPLEMENTATION-PLAN-R1`.
- **Current revision:** **R4** (see the Revision notes below).
- **Type:** Planning artifact only. **No application-code, test-code, schema, or configuration change.**
- **Authorization source:** `docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md`, decisions
  **`D-09-R1` — Implement P0 (2026-11-13)** (supersedes the earlier Option C deferral for the current
  decision state) and **`D-09-R2` — local-only A0–A4 exception (2026-11-13)** (see §3.8).
- **Authorization scope (accurate, R4):** the register §7 execution gate still blocks **all** practical
  implementation **except** the narrow local-only **A0–A4** exception granted by **D-09-R2**. Under that
  exception, **A0–A4 are `AUTHORIZED TO START — LOCAL-ONLY D-09-R2 EXCEPTION`** (each stage subject to
  its own documented dependencies and acceptance criteria). **B1–B3 and Group C (C1, C2, D0) remain
  `NOT AUTHORIZED TO START`**, and release/acceptance remains **NOT GRANTED** (see §3.7, §3.8, §6, §9, §12).
- **Revision:** **R4 (2026-11-13)** — reconciliation with the owner's **`D-09-R2`** local-only A0–A4
  exception (independently reviewed `PASS_WITH_NOTES`; its three LOW findings were subsequently
  remediated in the register). A0–A4 statuses updated to `AUTHORIZED TO START — LOCAL-ONLY D-09-R2
  EXCEPTION`; §7 precedence and the D-19 distinction made explicit (§3.8); the former §12 owner question
  recorded as resolved (§12). **Documentation-only. No stage is executed by this revision, and the plan
  itself has NOT undergone independent review.** (Supersedes the R3 note.)
- **Revision (R3):** R3 (2026-11-13) — minor remediation of the R2 independent adversarial review
  (`PASS_WITH_NOTES`): corrected the D-19 gate wording and cross-reference (E-1/E-3), the
  executive-summary local-only authorization phrasing (E-2), the §5 existing-worker wording (E-4), the
  historical-baseline labeling (E-5), the D0 gate wording (E-6), and the test-count qualification (E-7).
  **Documentation-only. No implementation is authorized by this revision.**
- **Revision (R2):** R2 (2026-11-13) — remediation of `OHB2-P0-STAGED-PLAN-CODE-EVIDENCE-AND-WORKTREE-VERIFICATION`
  (verdict `NEEDS_REVISION`): corrected the authorization boundary (F1/F2) and technical notes (F3–F8).
  **Documentation-only.** No implementation is authorized by this revision.
- **Historical revision hash:** R3 = `70858fd7b8563e690e1ee3d01e3d43a4ad71ec0c6d30fcfc334c8e293d5b0997`
  (preserved as historical evidence; recorded in the D-09 register §5 → D-09/I). The R1/R2 revision
  texts above are preserved verbatim as history; their file hashes were not recorded at authoring time
  and are not asserted here.
- **Predecessor specification:** `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md`
  (the upstream capability contract; SHA-256 `6ea52debd62918e831555a7ea4787cde75fa62c75e376ac5df93ece33e34e4dc`).
- **Predecessor architecture note:** `docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md`
  (verdict `BLOCKED — SECURE OPENHANDS UPLOAD CAPABILITY NOT ESTABLISHED`).
- **Ack architecture:** `docs/proposals/OHB2-TELEGRAM-ACK-ARCHITECTURE-ADR.md`.
- **Author:** OpenHands agent (autonomous). **Self-review only** — not an independent security review.
- **Date:** 2026-11-13 (the system date available at authoring time; not invented).
- **Repo state when written:** `TM-AEM/OpenHandBot`, branch
  `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW`, HEAD `907b20de3fa6627795c14f29677e9f39c68e82f4`;
  local `origin/main` = `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c`; **no upstream tracking** configured.

> **تمييز إلزامي — تصريح ≠ إتمام.** **التصريح بالتنفيذ (D-09-R1/D-09-R2) ليس إتمامًا لـ P0.** هذه الوثيقة
> **خطة فقط**: لا تُنفّذ أي مرحلة، ولا تُغيّر أي كود/اختبار/مخطّط/إعداد. **P0 يبقى غير مُنفَّذ** حتى
> تُنجَز مراحله فعليًا وتُتحقَّق باستقلال.

> **حدود هذه الوثيقة.** هذه خطة **تحضير** فقط. **لا تُحسم أي قرارات مالك** (D-10…D-24). **لا تُعاد
> صياغة قرار غير محسوم كموافقة.** المراحل المعتمدة على قرار مالك غير محسوم تُوسَم صراحةً
> `BLOCKED — OWNER DECISION REQUIRED` ولا يُخترع جوابها.

---

## 1. Executive summary

The owner authorized the **P0 goal and planning** (D-09-R1) and, subsequently, a **narrow local-only
A0–A4 implementation exception** (D-09-R2, independently reviewed `PASS_WITH_NOTES`). The register §7
execution gate still blocks **all** practical implementation **except** that narrow exception. This
plan converts those authorizations into a **dependency-ordered, staged** plan grounded in the **actual**
code paths of this repository (not filenames or comments). **A0–A4 are authorized to start (locally
only); B1–B3 and Group C are not.**

Three facts dominate the plan:

1. **The secure upstream upload capability does not exist yet.** The proposal
   `OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md` records it as **BLOCKED / not established**
   (predecessor note `OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md` §27; proposal §2). Therefore the
   **end-to-end** attachment flow (upload → deliver → agent reads) **cannot be implemented in this
   repository alone**; it depends on unresolved **owner architecture decisions** (D-10, D-11, D-14)
   and **external/upstream confirmations** (D-01…D-04, D-08).
2. **A large, self-contained, local-only portion is technically implementable** without any
   upstream upload capability and without resolving most owner decisions. This portion comprises the
   local **attachment batch state machine** (per-user/per-conversation/per-batch), the **fixed
   15-minute deadline**, the **accompanying-text requirement**, **path/type/size validation**,
   **ownership + tombstone enforcement**, **durable outbox integration**, **cleanup/expiry**, and
   **observability**. Under **D-09-R2** these stages (**A0–A4**) are **`AUTHORIZED TO START —
   LOCAL-ONLY D-09-R2 EXCEPTION`**, each still subject to its own documented dependencies and
   acceptance criteria (see §3.8).
3. **The existing architecture must be reused unchanged in spirit:** one SQLite owner, one bot
   process, existing workers, existing Telegram ack boundary, existing outbox at-most-once
   semantics. No second DB owner, no second bot process, no new worker architecture, no backup
   feature.

The plan is therefore split into: **(A) local-only stages** — **authorized to start under D-09-R2**;
**(B) transport/architecture stages** — `NOT AUTHORIZED TO START`, blocked on owner decisions
D-10/D-11/D-14; and **(C) delivery/evidence stages** — `NOT AUTHORIZED TO START`, blocked on external
confirmations D-01…D-04, D-08. Groups (B)/(C) remain blocked by their own gates and by the general §7
gate; **group (A) is authorized to start locally under the narrow D-09-R2 exception** (see §3.8 and §5).

---

## 2. Verified repository baseline (this task)

| Item | Value |
| --- | --- |
| Repository root | `/workspace/project/OpenHandBot` |
| Branch | `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW` |
| HEAD | `907b20de3fa6627795c14f29677e9f39c68e82f4` |
| Local `origin/main` | `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c` |
| Upstream tracking | **none** (`fatal: no upstream configured`) |
| `git status --short` (R1 historical baseline) | **39 entries** = 9 modified (`M`) + 30 untracked (`??`); **staged: 0** — this was the count at R1 authoring time. At R2 the count became **40** (9 `M` + 31 `??`) because this plan document itself is the 31st untracked entry; the current count must be **re-checked** at any later time, not assumed. |
| D-09 register | `docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md`. **Historical (R1) SHA-256 `d239f4e827e7880ec740aa712c3046fb5fa3180060d8cf21c4d97aca0c07726d`** — **not** the current value (the register later gained `D-09-R2` and its LOW-finding remediation). **Current (R4 reconciliation) SHA-256 `846a9b2303ecd78eee15ee96b157d2b22a049ea38e797abe6bc04d7b62b93d01`.** |
| P0 proposal | `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md`, SHA-256 `6ea52deb…` |
| System date | 2026-11-13 (UTC) |

**Effective decision (verbatim intent):** D-09-R1 — «يوافق المالك على تنفيذ P0» — recorded in the
register §5 → D-09/H; the earlier Option C is **superseded, not erased**.

**The 9 modified files** (all pre-existing, none touched by this task): `.agent/PROGRESS.md`,
`bot/handlers.py`, `bot/web/app.py`, `bot/web/ratelimit.py`, `bot/web/sessions.py`,
`docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md`,
`docs/proposals/OHB2-TELEGRAM-ACK-ARCHITECTURE-ADR.md`, `tests/test_miniapp_ratelimit.py`,
`tests/test_miniapp_session_persistence.py`.

---

## 3. Mandatory decision audit (D-09-R1 authorized vs. unresolved)

Source: the full D-09 register (§5 decision records, §6.3 classification, §7 readiness matrix, §9
owner-response checklist, §12 status). **Nothing below is silently resolved.**

### 3.1 Already authorized by D-09-R1

| Decision | Subject | Status | Effect on P0 |
| --- | --- | --- | --- |
| **D-09** | Product go/no-go for P0 | **RESOLVED → implement P0** (D-09-R1, 2026-11-13) | Authorizes the **P0 goal and planning**. It does **not** by itself authorize practical implementation (the register §7 gate blocks that), does **not** resolve any sub-decision (D-10…D-24), and does **not** by itself permit starting any stage. *(Starting the **A0–A4** subset locally is permitted only by the later **D-09-R2** exception — see §3.8.)* |

**No other decision is authorized by D-09-R1.** D-09-R1 explicitly states it «لا يحلّ أي قرار آخر
(D-10…D-24)». **Planning authorization is separate from implementation authorization and from
release/acceptance authorization** — see §3.7.

### 3.2 Decisions that block planning only (not implementation)

None: planning can proceed for every decision by documenting its consequence and options.

### 3.3 Decisions that can be safely determined by the implementation agent (no owner approval)

These are **technical details** inside the *design* of already-scoped work. They do **not** require
owner approval because they neither open a new attack surface nor change product behavior; they must
be recorded in the PR/commit for review. **Determining these details is not implementation
authorization** — no stage may start on the strength of this subsection (authorization derives from
§3.7/§3.8, not from this subsection).

| Detail | Proposed determination | Justification |
| --- | --- | --- |
| Local staging directory location | A dedicated subdirectory under the DB/state directory (co-located with `DB_PATH`, e.g. `…/attachment_staging/`), mode `0700`, one file per staged item named by an opaque random token (never the user's original filename). **Git safety (F3):** this path is **outside tracked source content** (it lives beside the DB, not under `bot/`/`tests/`/`docs/`), and the implementation **must** add an explicit `.gitignore` entry for it so staged user bytes can never be committed. | Reuses the existing single state location; no new subsystem; avoids `/tmp` cross-user leakage. |
| Batch/item identifier scheme | Opaque random `batch_id`/`item_id` (e.g. `secrets.token_hex`) stored as `TEXT`; never derived from user input. | Matches existing opaque-id conventions (`watch_seq` uses `randomblob`). |
| Deadline constant | New named constant `ATTACHMENT_BATCH_TTL = timedelta(minutes=15)` in `bot/db.py` (parallel to `AWAITING_TTL`), **distinct** from the existing 10-minute routing TTL. | The 15-minute window is a fixed P0 requirement (I4); reusing `AWAITING_TTL` (10 min) would violate it. |
| Ack message copy | «استلمت الملف. ابعت الأوامر النصية في خلال 15 دقيقة وهبعتهم مع بعض.» (truthful; promises no upload). | Preserves the current "no false promise" copy discipline of `UNSUPPORTED_ATTACHMENT_TEXT`. |
| Local max size/type policy defaults | Provisional: size cap and an extension/MIME allowlist mirroring the proposal §5.7 (values **PROVISIONAL**, overridable by D-12). | D-12 is a product-policy decision; a conservative default is safe and reversible. |
| Structured audit event names | Reuse the existing logging style (no secrets, no file content). | §5.11 / I-series "no content in logs". |
| Rollback mechanism / feature flag (F7) | **No attachment feature flag exists today.** Verified: `bot/features.py` exposes only `DEFERRED_FEATURES_HIDDEN` and `HIDDEN_FEATURES = {files, export, cost, followups}` — there is **no** attachment/upload flag. A rollback-by-flag therefore **requires adding a new flag**, which is a **design/implementation detail requiring verification** at implementation time (and is **not** implemented by this document). | Avoids claiming a rollback mechanism that does not exist in the current source. |

### 3.4 Decisions requiring explicit owner approval before implementation (blocking)

For each: **status**, **blocks planning?**, **blocks implementation?**, **exact implementation
consequence**, **minimum owner decision to unblock**, **recommended option (with technical
justification)**, and **risks of each materially different option**.

---

#### D-10 — Capability ownership: Cloud V1 vs Agent Server (Q1)

- **Status:** unresolved. **Blocks planning?** No. **Blocks implementation?** **Yes (transport).**
- **Consequence:** decides whether the bot talks to the **Cloud V1** API (new upload path) or the
  **Agent Server** (existing confined route). Determines auth model, URL origin trust, and which
  upstream primitives exist.
- **Minimum owner decision:** choose Cloud V1 or Agent Server (or a third explicit mechanism).
- **Recommended option:** **Cloud V1** — the proposal §5 is built on it; Agent Server reintroduces
  the untrusted-origin problem (§2.4) and broad-key trust.
- **Risks:** Cloud V1 ⇒ requires new upstream capability (long lead). Agent Server ⇒ depends on
  `conversation_url` origin (infrastructure-dependent, no stable allowlist) ⇒ wider trust.

#### D-11 — Scoping mechanism: per-operation Cloud path vs capability token (+TTL/binding/revocation) (Q2)

- **Status:** unresolved. **Blocks planning?** No. **Blocks implementation?** **Yes (transport).**
- **Consequence:** how an upload is bound to one conversation and revoked; determines whether a
  leaked credential can be replayed.
- **Minimum owner decision:** choose the scoping mechanism.
- **Recommended option:** **per-operation scoped path/token with TTL + conversation binding**
  (least-privilege; avoids the current broad key, §5.1).
- **Risks:** per-op token ⇒ more upstream work; broad key ⇒ replay/abuse surface.

#### D-14 — Delivery mechanism (design A/B/C/D) and whether to extend `send-message` (Q5a/Q5b/Q14)

- **Status:** unresolved; **owner (architectural)**. **Blocks planning?** No. **Blocks
  implementation?** **Yes (delivery).**
- **Consequence:** how the uploaded file is delivered to the **same** conversation and whether the
  existing outbox (text-only) is extended with an attachment item type (proposal §8.3 r5 S-2).
- **Minimum owner decision:** choose the delivery design and whether to extend `send-message`/outbox.
- **Recommended option:** **a new outbox payload capability** (a distinct item kind carrying the
  operation reference / `delivered_path`) — reuses the single worker architecture (I2/I3) instead of
  inventing a parallel dispatcher.
- **Risks:** extending outbox ⇒ touches the ack/at-most-once core (must be guarded); a separate
  mechanism ⇒ risks a second owner/worker and duplicate dispatch.

#### D-06 — Workspace-root source and identity/authorization binding (Q22)

- **Status:** unresolved; reading exists, binding **UNVERIFIED**. **Blocks implementation?** **Yes
  (delivery).** **Minimum owner decision:** choose binding source. **Recommended:** server-side
  binding (never client-supplied path). **Risks:** client-supplied root ⇒ path-traversal / wrong
  conversation.

#### D-02 — Successful-read signal (U-3) (Q16)

- **Status:** unresolved; `delivered` not reachable today. **Blocks implementation?** **Yes
  (`delivered`).** **Minimum owner decision:** adopt U-3 or accept a weaker fallback.
  **Recommended:** adopt U-3 (truthful `delivered`). **Risks:** weaker fallback ⇒ cannot assert
  delivery truthfully.

#### D-03 — Trusted issuer boundary + authentication (U-3) (Q19)

- **Status:** unresolved; **UNVERIFIED** (no trusted issuer in pinned source). **Blocks
  implementation?** **Yes.** **Minimum owner decision:** define the trusted issuer. **Recommended:**
  Cloud control-plane issuer. **Risks:** untrusted issuer ⇒ forged evidence.

#### D-04 — Quiesced evidence source (Q20)

- **Status:** unresolved; `events/search` is an inconsistent replica. **Blocks implementation?**
  **Yes.** **Minimum owner decision:** choose a quiesced source. **Recommended:** a quiesced source
  or re-verify against agent-server. **Risks:** replica reads ⇒ race / false terminal.

#### D-01 — Durable accept for an **active** conversation (U-2) (Q12/Q15)

- **Status:** unresolved; `pending-messages` is start-only. **Blocks implementation?** **Yes
  (durable `consumed_at`).** **Minimum owner decision:** choose the durable-accept mechanism.
  **Recommended:** a durable accept on `send-message`. **Risks:** trusting a non-durable signal ⇒
  premature cleanup.

#### D-22 — OpenHandBot outbox integration limit for attachment payloads (U-9) (S-2)

- **Status:** unresolved. **Blocks implementation?** **Yes (integration).** **Minimum owner
  decision:** approve the outbox payload extension limit. **Recommended:** a bounded new item kind
  (one operation reference + `delivered_path`). **Risks:** unbounded payload ⇒ ack-core churn.

#### D-07 — Restricted retention policy for the materialized copy (C2) (Q18/Q6)

- **Status:** unresolved; conservative default stands (C2 retained). **Blocks implementation?**
  **Yes (cleanup policy).** **Minimum owner decision:** choose the retention policy. **Recommended:**
  retain until conversation end (conservative). **Risks:** aggressive reclaim ⇒ data loss.

#### D-08 — Cloud/runtime-api lifecycle/teardown + physical deletion (R9-3)

- **Status:** unresolved; delegated to runtime-api (external). **Blocks implementation?** **Yes
  (retention guarantees).** **Minimum owner decision:** obtain upstream confirmation.
  **Recommended:** fail-safe (no assumption). **Risks:** assuming teardown ⇒ over-claiming deletion.

#### D-19 — Independent security review: who performs it and is it a release gate (Q10)

- **Status:** unresolved. **Blocks implementation?** **No longer blocks starting the locally authorized
  A0–A4 subset (per the subsequent D-09-R2 exception, §3.8); still a mandatory release/acceptance gate.**
  **Minimum owner decision:** name the reviewer and whether it is a gate. **Recommended:** independent
  review as a gate — it conditions the **release/acceptance** decision (register §8, line 1241: «ثم
  **D-19** (بوّابة المراجعة الأمنية) قبل أي إصدار»), and in general it still conditions implementation
  outside the narrow A0–A4 exception (register §7, line 1189: «التصريح بالتنفيذ يتطلّب … + المراجعة
  الأمنية (D-19)»). **Risks:** self-review only ⇒ unverified security claims.

#### D-16 — Idempotency-Key + dedup + delivery idempotency (U-4) (Q7)

- **Status:** unresolved. **Blocks implementation?** **Yes for dispatch** (safe-retry contract).
  **Minimum owner decision:** approve the idempotency contract. **Recommended:** `Idempotency-Key` +
  `client_operation_id` + `(operation_id, file_id)` dedup. **Risks:** no idempotency ⇒ duplicate
  files on retry.

#### D-12 — Inconsistent size/type bounds (`3 MiB == 3 MiB`) (Q3)

- **Status:** unresolved; values PROVISIONAL. **Blocks implementation?** No (local default safe).
  **Minimum owner decision:** confirm product bounds. **Recommended:** confirm the provisional
  bounds. **Risks:** too large ⇒ resource pressure; too small ⇒ UX.

#### D-13 — Reuse-boundary confirmation (Q4)

- **Status:** unresolved (confirmation). **Blocks implementation?** No. **Recommended:** confirm the
  existing reuse boundary. **Risks:** silent divergence if not confirmed.

#### D-15 — `expires_at` reconciliation window (15 min) and no server-side batch model (Q6)

- **Status:** unresolved (confirmation). **Blocks implementation?** No for the **local** A0–A4 design;
  **Yes** for **remote reconciliation (Stage B2)**. **Recommended:** confirm 15 min, no server batch
  concept. **Risks:** mismatch ⇒ stale references.
- **Classification note (F6):** D-15 governs **remote** `expires_at`/reconciliation semantics. It does
  **not** block local A0–A4 design merely because **B2** depends on it; its effect is confined to B2.
  It remains **unresolved** here — this document does not decide its value.

#### D-17 — Ended/deleted conversation behavior (409) + recovery (Q8)

- **Status:** unresolved (confirmation). **Blocks implementation?** No (tombstone already enforced).
  **Recommended:** confirm 409 + no recovery. **Risks:** divergent error handling.

#### D-20 — Reintroduce `uploading`/`delivering`; staging/delivery sync (Q13)

- **Status:** unresolved (confirmation). **Blocks implementation?** No. **Recommended:** confirm.
  **Risks:** state-model mismatch with upstream.

#### D-21 — Correlation identifier contract `client_operation_id` (Q17)

- **Status:** unresolved (confirmation). **Blocks implementation?** No (local id can be generated).
  **Recommended:** confirm the contract. **Risks:** correlation gaps.

#### D-23 — Server-side audit/operation record retention policy (C4)

- **Status:** unresolved. **Blocks implementation?** No (local logging only). **Recommended:**
  conservative retention. **Risks:** unbounded audit growth.

#### D-24 — Delivered-file permissions/ownership (mode/uid/gid) (Q14)

- **Status:** unresolved; **UNVERIFIED**. **Blocks implementation?** No for local; **Yes for
  delivered-file guarantees.** **Recommended:** require readable-by-agent mode. **Risks:** unreadable
  delivered file ⇒ silent failure.

#### D-18 — Legacy `/api/file/upload` deprecation (Q9)

- **Status:** unresolved; **out of P0 scope.** **Blocks implementation?** No. Not planned here.

### 3.5 Separation summary

1. **Authorized by D-09-R1:** the *goal* of implementing P0 (D-09 only).
2. **Authorized by the subsequent D-09-R2 exception:** the narrow **local-only A0–A4** subset (see
   §3.8); this is an exception to the general §7 gate, limited to A0–A4.
3. **Technical details safely determined by the implementation agent:** §3.3 (staging layout, id
   scheme, `ATTACHMENT_BATCH_TTL=15min`, copy, provisional limits, audit naming).
4. **Requiring explicit owner approval before implementation (outside A0–A4):** D-10, D-11, D-14, D-06,
   D-02, D-03, D-04, D-01, D-22, D-07, D-08, D-16, D-19 (blocking); D-12/D-13/D-17/D-20/D-21/D-23/D-24
   (confirmations or local-only, see matrix). **D-15 is distinct:** it is a confirmation whose effect
   is confined to **Stage B2 (remote reconciliation)** and does **not** block local A0–A4
   (see §3.4/D-15).

### 3.6 Material unresolved decisions and the plan's response

The following **materially prevent a reliable end-to-end plan** and are therefore recorded as
**blockers** rather than guessed: **D-10, D-11, D-14** (transport/architecture) and **D-01, D-02,
D-03, D-04, D-08** (external/upstream evidence). The rest of the plan (group A) is prepared in full
without inventing their answers.

### 3.7 Authorization boundary (three distinct levels)

The register distinguishes three levels of authority. This document does **not** collapse them:

| Level | Meaning | Current status |
| --- | --- | --- |
| **Planning authorization** | Permission to investigate, specify, and stage the work. | **GRANTED** (D-09-R1 authorizes the P0 goal and this planning work; register §5 → D-09/H, line 608). |
| **Implementation authorization** | Permission to change code/tests/schema/config and start a stage. | **PARTIALLY GRANTED — A0–A4 only.** Register §7 keeps implementation **blocked** in general, but the subsequent owner decision **D-09-R2** grants a narrow **local-only A0–A4** exception. So **A0–A4 = `AUTHORIZED TO START — LOCAL-ONLY D-09-R2 EXCEPTION`**, while **B1–B3 and C1/C2/D0 = `NOT AUTHORIZED TO START`** (see §3.8). |
| **Release / acceptance authorization** | Permission to declare P0 complete and release. | **NOT GRANTED.** Requires all of the above plus the D-19 independent security review gate (register §7 line 1189; §6.3, §8). |

**Consequences for this document:**
- **A0, A1, A2, A3, A4: `AUTHORIZED TO START — LOCAL-ONLY D-09-R2 EXCEPTION`** (each subject to its own
  documented dependencies and acceptance criteria; see §3.8, §6).
- **B1, B2, B3, C1, C2, D0: `NOT AUTHORIZED TO START`.**
- **The §7 execution gate is not weakened, reinterpreted, bypassed, or amended by this document.** The
  D-09-R2 exception is narrow, local-only, and limited to A0–A4; it is **not** a general cancellation
  or weakening of §7.
- **Release/acceptance remains `NOT GRANTED`**, and **D-19 remains mandatory** for the security/release
  sequence (see §3.8).

### 3.8 D-09-R2 — narrow local-only A0–A4 exception and its §7 precedence (R4 reconciliation)

**Authority.** `docs/decisions/OHB2-P0-OWNER-DECISIONS-REGISTER.md`, decision **`D-09-R2` — local-only
A0–A4 exception (2026-11-13)** (register §5 → D-09/I). It is a **subsequent, explicit owner decision**
added after `D-09-R1`; it does **not** erase the historical record (Option C, D-09-R1 remain intact).

**What it grants.** A **narrow, local-only** exception permitting the stages **A0, A1, A2, A3, A4** to
proceed **before** resolution of the Group B/Group C blocking decisions and **before** completion of
**D-19**. New status of these stages:
**`AUTHORIZED TO START — LOCAL-ONLY D-09-R2 EXCEPTION`**.

**Precedence over §7 (limited).** D-09-R2 takes precedence over the general **§7** execution gate
**only** for the exact A0–A4 scope. For **everything else** (B1–B3, Group C, release/acceptance, and all
work not in A0–A4) the general §7 gate **remains fully in force, unchanged and not weakened**.

**Not authorized by this exception:** the entire P0 implementation; **B1, B2, B3**; **C1, C2, D0**;
remote transport/reconciliation/remote-delivery work; release, production deployment, or acceptance;
any relaxation of the D-19 security requirements applicable to release/acceptance; a second bot
process, independent DB owner, new worker architecture, or backup feature; exactly-once delivery
claims; and production calls or real user sessions during testing.

**Per-stage caveat (no blanket execution).** The exception authorizes the **A0–A4 subset**, but does
**not** remove each stage's own technical prerequisites, sequencing, acceptance criteria, or safety
controls (documented per stage in §6). The five stages are **not** required to execute simultaneously;
each remains subject to its own documented dependencies and acceptance requirements.

**D-19 distinction (see also §3.4/D-19 and §6/C2):**
1. D-19 is **no longer a prerequisite for starting** the locally authorized **A0–A4** subset under
   D-09-R2.
2. D-19 **remains mandatory** for the **security/release sequence** and for all applicable
   release/acceptance requirements.
3. **Release/acceptance remains `NOT GRANTED`.** This exception weakens **no** security-review
   requirement.

**Authorization matrix (R4).**

| Scope | Status |
| --- | --- |
| Planning | **GRANTED** |
| A0–A4 (local-only) | **AUTHORIZED TO START — LOCAL-ONLY D-09-R2 EXCEPTION** |
| B1–B3 | **NOT AUTHORIZED** |
| Group C (C1, C2, D0) | **NOT AUTHORIZED** |
| Release / acceptance | **NOT GRANTED** |
| D-19 | **mandatory for the security/release sequence** (not a prerequisite for starting A0–A4) |

**Authorization ≠ completion.** Recording the exception is **not** implementation and **not**
completion. **P0 remains unimplemented**, and **A0–A4 have not started** by virtue of this document.

---

## 4. Architecture and code-path audit (traced from source)

All references are to the current working tree at HEAD `907b20de…`.

### 4.1 Telegram message/update handling and handlers

- `bot/app.py::build_application` registers handlers (§ lines 105–168). Order: `dedupe_update`
  (`TypeHandler(Update, …)`, **group −1**, line 109) → commands → callback handlers →
  `MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_text)` (line 154) →
  `MessageHandler(UNSUPPORTED_ATTACHMENT_FILTER, handlers.handle_unsupported_attachment)` (lines
  159–163) → `TypeHandler(Update, handlers.handle_unmatched_update)` fallback (line 168).
- `UNSUPPORTED_ATTACHMENT_FILTER` (`bot/app.py:35–45`) is an **explicit union** (`Document.ALL |
  PHOTO | AUDIO | VIDEO | VOICE | VIDEO_NOTE | ANIMATION | Sticker.ALL | LIVE_PHOTO | PAID_MEDIA`),
  deliberately complementing the text filter so each message reaches exactly one handler.
- **Attachment rejection today:** `handlers.handle_unsupported_attachment` (`bot/handlers.py:1580`)
  sends one fixed Arabic message (`UNSUPPORTED_ATTACHMENT_TEXT`, lines 1574–1577), performs **no**
  download, **no** persistence, **no** OpenHands call, and marks the update `explicitly_ignored`
  (ack-eligible). **This is the exact insertion point for the new workflow** (group A).

### 4.2 Custom poller and acknowledgment

- `bot/polling.py::TelegramPoller` pulls `getUpdates` with an offset equal to the **durable ack
  boundary** (`settings.acknowledgment_boundary`), feeds `application.update_queue`, and advances the
  offset **only after** the update's durable outcome is fixed. No exactly-once claim; at-most-once +
  idempotent redelivery.
- `bot/update_outcomes.py` defines outcomes and `_ACK_ELIGIBLE = {durable_completed,
  durable_intent_recorded, explicitly_ignored, duplicate_completed}`; everything else (incl.
  `partial_or_unknown`) is **fail-closed not eligible**.
- `handlers.dedupe_update` (`bot/handlers.py:372`) is the group −1 guard; `db.mark_update_processed`
  (`bot/db.py:1760`) is the atomic `INSERT OR IGNORE` on `processed_updates(update_id PK)`.

### 4.3 Conversation selection, ownership, and the awaiting state machine

- `handlers.handle_text` (`bot/handlers.py:1640`) reads `db.awaiting_state(telegram_id)` (non-consuming)
  and dispatches on `kind ∈ {reply, newchat, reposearch, route}`. `reply`/`route` route to
  `_send_prompt`; `newchat` → `_start_new_chat`; `reposearch` → repo list.
- **Deadline:** `AWAITING_TTL = timedelta(minutes=10)` (`bot/db.py:187`) governs routing; it is
  **distinct** from the required 15-minute attachment window. `db.awaiting_is_expired` (`:1667`).
- `handlers._send_prompt` (`bot/handlers.py:1710`): tombstone check first
  (`_is_deleted_with_retry`), then `db.add_or_group_outbox(..., reengage=True, update_id=…,
  consume_awaiting=…)` writes the durable outbox row **and** the processed-update marker **in one
  transaction** (`bot/db.py:2064`), then acks «وصل ✅».
- **Ownership:** `handlers._authorized_conversation_status` /
  `_authorized_conversation` (`bot/handlers.py:158/188`) reuse the shared
  `files.authorize_conversation_detailed` + `FileService` path (ownership, id validity, tombstone,
  fail-closed). Mini App uses `bot/web/services.py::_authorize_conversation` (`:375`).

### 4.4 OpenHands conversation API integration

- `bot/openhands_client.py::OpenHandsClient`: `search_conversations`, `get_conversations`,
  `search_events`, `get_last_reply`, `get_last_exchange`, `list_files`, `read_file*`,
  `get_current_user` (ownership), `export_conversation`, `send_message(conversation_id, text)`
  (`:337`, `POST /app-conversations/{id}/send-message`), `delete_conversation`. **No upload method
  exists** — confirms the proposal §8.3 r5 S-2 boundary.
- Bounded reads (`_read_capped`, `Accept-Encoding: identity`, strict redirect rejection) are the
  existing safe-download pattern to reuse for any byte transfer.

### 4.5 Current file upload/attachment handling

- **No inbound upload path exists.** Outbound file delivery is `send_document`
  (`bot/handlers.py:1439`, `:1538`). Inbound attachments are **rejected** (§4.1). There is **no**
  staging directory, **no** temp-file handling (grep for `tempfile|mkdtemp|staging|/tmp` in `bot/`
  returns nothing).

### 4.6 SQLite schema, migrations, transactions, ownership

- `Database` (`bot/db.py:380`): `sqlite3.connect(path, check_same_thread=False)`,
  `journal_mode=WAL`, `busy_timeout=5000`. **Single authoritative DB.**
- Tables created in `_init_schema` (`:408`) with `CREATE TABLE IF NOT EXISTS`; non-destructive
  migrations in `_migrate` (`:589`) via `ALTER TABLE … ADD COLUMN` guarded by `PRAGMA table_info`.
  Existing tables: `watched`, `user_state`, `outbox`, `creation_jobs`, `completion_pending`,
  `settings`, `notification_state`, `notifier_pending`, `notifier_retry_not_before`,
  `notification_inbox`, `deleted_conversations`, `web_sessions`, `processed_updates`,
  `update_failures`. **No attachment/batch table exists.**
- Tombstone: `deleted_conversations`; `db.is_deleted` (`:1099`) is the single source of truth.
- Atomic multi-write pattern: `BEGIN IMMEDIATE` … `commit()`/`rollback()`
  (e.g. `consume_one_shot_awaiting` `:1704`), and `_mark_processed_nocommit` for the durable outcome
  in the same txn.

### 4.7 Outbox and workers

- `bot/outbox.py`: `OutboxWorker`, `CreationWorker`, `CompletionWorker`, all subclassing
  `_BaseWorker` (`:545`, single-owner sleep/backoff/wake/start/stop). Statuses:
  `pending/claimed/sending/unknown/failed/discarded`; `MAX_OUTBOX_ATTEMPTS = 5`.
- `deliver_outbox` (`:210`) → `claim_outbox` (atomic claim of oldest `pending`) → `_post_claimed`
  (`:298`). `_post_claimed` has **fail-closed tombstone guards** at entry and immediately before the
  `claimed→sending` CAS (the OHB2-OUTBOX-TOMBSTONE-TOCTOU fix). Pre-CAS recovery returns rows to
  `pending`; post-CAS unknown → `unknown` (never blind-retried).
- Workers are started once in `bot/app.py` `_post_init` (lines 227–244) **after**
  `deletion.reconcile_pending_deletions` (line 221).

### 4.8 Retry, failure, reconciliation

- Outbox: bounded attempts, pre-CAS recovery, post-CAS `unknown`. Deletion:
  `deletion.reconcile_pending_deletions` (`bot/deletion.py:203`) reconciles `deleting`/`uncertain`
  on restart (best-effort, non-fatal). This is the **recovery-hook pattern** the attachment
  reconciler must mirror.

### 4.9 Temporary-file storage and cleanup

- **None exists.** File *previews* use bounded in-memory reads (`files.FileService.read_preview`).
  `file_cache.FileCache` is a bounded LRU of **file listings** (not bytes). A new local staging area
  must be introduced (group A) — inside the existing state location, not a new subsystem.

### 4.10 Mini App and bot user-facing flows

- Bot: menu/commands (`/start`, `/outbox*`, callback handlers) + `handle_text`. Mini App:
  `bot/web/` (Starlette) with `_authorize_conversation` ownership and tombstone enforcement. P0's
  workflow is **bot-side**; the Mini App is unaffected except it must **not** expose staged files.

### 4.11 Existing file type/size/path/content validation

- `bot/files.py`: `MAX_CONVERSATION_ID_LEN=64`, `MAX_PATH_LEN=1024`, `MAX_PREVIEW_BYTES=256 KiB`,
  `_ID_RE`, `is_valid_conversation_id`, `is_safe_workspace_path`, `is_listed_path` (allowlist),
  `classify_text`. `openhands_client.MAX_FILE_RESPONSE_BYTES` mirrors the preview cap. These are the
  reusable validation primitives for group A.

### 4.12 Existing tests and infrastructure

- 110 test modules under `tests/`, `pytest.ini`, `tests/conftest.py`, helpers
  `_miniapp_helpers.py`, `_mutation_harness.py`, `_real_http.py`; frontend tests via
  `node --test tests/frontend/*.test.js`.
- Directly relevant: `tests/test_unsupported_attachment_rejection.py`,
  `tests/test_one_shot_awaiting_atomicity.py`, `tests/test_duplicate_update_dispatch.py`,
  `tests/test_outbox_tombstone_toctou.py`, `tests/test_outbox.py`,
  `tests/test_outbox_pre_cas_recovery.py`, `tests/test_stage2_custom_polling.py`.
- **Focused test command:** `python -m pytest -q`; frontend `node --test tests/frontend/*.test.js`;
  lint `python -m pyflakes bot/ automation/ tools/ main.py tests/`.

### 4.13 Smallest safe integration points (summary)

1. **New module** `bot/attachments.py` (batch state machine + staging + validation) — new file, no
   edits to unrelated modules.
2. **DB additions** in `bot/db.py`: two new tables (`attachment_batches`, `attachment_items`) +
   migration block; new constant `ATTACHMENT_BATCH_TTL`.
3. **Handler swap** in `bot/app.py`: replace `handle_unsupported_attachment` with the new
   `handle_attachment` for the **supported** subset; keep the rejection path for unsupported types.
4. **Text dispatch** in `bot/handlers.py::handle_text`: when a live batch exists for the user,
   require text and route to the attachment-dispatch path (durable intent first).
5. **Outbox extension** (group B/C only, blocked): a new item kind or an explicit owner-approved
   mechanism.

---

## 5. Non-negotiable P0 requirements (preserved; ambiguities flagged)

| # | Requirement | Plan handling | Ambiguity |
| --- | --- | --- | --- |
| 1 | Attachments belong to a specific, explicitly selected conversation | Batch row stores `conversation_id`; dispatch reuses `_authorized_conversation`. | What if no conversation is selected (no `awaiting` route)? **Ambiguity A1** — plan: reject with a prompt to open a conversation first (no new-conversation fallback). |
| 2 | Temp state bound to user+conversation+batch | `attachment_batches(telegram_id, conversation_id, batch_id)`. | None. |
| 3 | Wait **exactly** 15 min for accompanying text | `ATTACHMENT_BATCH_TTL=15min`; `T0` persisted. | None (fixed). |
| 4 | Extra attachments never extend/reset the deadline | `T0` written once at first file; appends never touch it. | None. |
| 5 | Never submit attachments without accompanying text | Dispatch only triggered by a text update within deadline. | None. |
| 6 | Never silently fall back to creating a new conversation | No `start_conversation` call in the attachment path; explicit reject otherwise. | None. |
| 7 | Existing SQLite DB + existing workers only | Two tables in the existing DB. **No new worker instance, scheduler, process, or independent database owner**: reuse an **existing lifecycle hook or an existing worker's tick** (see A4). | None. |
| 8 | Ownership + cross-user/conversation isolation | Reuse `authorize_conversation*`; batch keyed by `telegram_id`. | None. |
| 9 | Validate paths/types/sizes | Reuse `files.is_safe_workspace_path` etc. + new size/type allowlist. | Exact bounds are **D-12** (PROVISIONAL default used). |
| 10 | Fail-closed when state/ownership unverifiable | Any DB/ownership error ⇒ reject/abort, never dispatch. | None. |
| 11 | No exactly-once claim | at-most-once + reconciliation; documented. | None. |
| 12 | Single bot process + single authoritative DB | No new process/worker/DB. | None. |

**Other ambiguities flagged (not guessed):**
- **A2:** whether the 15-minute window starts at the **first file** or at **last activity** — the
  proposal I4/I6 is explicit (**first file, never extended**), so this is resolved by the
  specification, not by us.
- **A3:** whether a batch may span multiple conversations — resolved: **no** (one
  `conversation_id` per batch).
- **A4:** behavior when the selected conversation is tombstoned mid-batch — plan: **fail-closed**
  (discard batch, notify), mirroring `_send_prompt`.

---

## 6. Staged implementation plan

Stages are dependency-ordered. Each stage: objective, scope/files, current vs intended behavior,
DB impact, security/ownership invariants, failure/crash scenarios, required tests, acceptance
criteria, evidence for PASS, rollback/recovery, dependencies/blockers, and whether it can proceed
without another owner decision.

> **Gate legend (R4):**
> - `AUTHORIZED TO START — LOCAL-ONLY D-09-R2 EXCEPTION` = the owner's narrow local-only A0–A4
>   exception permits starting this stage (each stage still subject to its own documented dependencies
>   and acceptance criteria; see §3.8). **A0–A4 carry this status.**
> - `NOT AUTHORIZED TO START` = the current recorded decisions do **not** permit starting this stage.
>   **B1–B3, C1, C2, D0 carry this status.**
> - `BLOCKED — OWNER DECISION REQUIRED (…)` = in addition to the above, a specific owner decision
>   must be resolved before the stage can even be *eligible* to start.
>
> **No Group B/C stage is `PROCEED` today.** The former `PROCEED (D-09-R1)` label is withdrawn; the
> current authorization for group (A) derives solely from the D-09-R2 local-only exception (§3.8).

### Stage A0 — Local attachment batch schema + migration (foundation)

- **Objective:** add durable local batch/item state in the existing DB.
- **Scope/files:** `bot/db.py` (new tables `attachment_batches`, `attachment_items`; `_migrate`
  additions; `ATTACHMENT_BATCH_TTL`; accessor methods).
- **Current behavior:** no attachment state. **Intended:** rows persisted per user/conversation/
  batch/item with statuses (`pending`, `dispatching`, `uncertain`, `delivered`, `expired`,
  `rejected`, `failed`).
- **DB impact:** two **new** tables (`CREATE TABLE IF NOT EXISTS`); additive migration; **no** change
  to existing tables/columns.
- **Security/ownership invariants:** batch keyed by `telegram_id`; `conversation_id` validated with
  `files.is_valid_conversation_id`; no secrets stored.
- **Failure/crash:** writes are single-transaction; partial writes impossible.
- **Tests:** schema creation; migration idempotency on an old DB; isolation (batch of user A
  invisible to user B).
- **Acceptance:** `python -m pytest -q` green; new tables present after init and after re-init.
- **Evidence:** test names + `PRAGMA table_info` output.
- **Rollback:** additive tables can remain unused; no destructive migration.
- **Dependencies/blockers:** **none beyond its own acceptance criteria** — authorized under the narrow
  **D-09-R2 local-only exception** (see §3.8). **Current status: `AUTHORIZED TO START — LOCAL-ONLY
  D-09-R2 EXCEPTION`.** It remains technically local-only and must still satisfy its documented
  acceptance criteria before being considered complete.

### Stage A1 — Local staging store + secure validation

- **Objective:** store accepted attachment bytes locally, safely.
- **Scope/files:** `bot/attachments.py` (new), `bot/files.py` (reuse validators), config (optional
  size/type knobs), **`.gitignore`** (add the staging path — see F3).
- **Current behavior:** attachments rejected, nothing stored. **Intended:** download to a `0700`
  staging dir with opaque names; enforce size cap + extension/MIME allowlist; never trust the
  original filename as a path.
- **DB impact:** item rows reference staging tokens.
- **Security invariants:** no path traversal (opaque names, no user path components); bounded size;
  allowlist; no symlink following.
- **Crash-safe write ordering (F5) — no cross-store atomicity claimed.** SQLite and the filesystem
  are **separate stores**; this design does **not** claim atomicity across them. The intended
  sequence is **row-first** so recovery can always find and clean incomplete items:
  1. **Create durable item metadata** (row, status `pending`) **before** any byte is written.
  2. **Download/write** bytes to the staging file under the opaque token.
  3. **Validate** (size cap, type allowlist, content policy) against the written bytes.
  4. **Transition** the item to `stored` only after validation succeeds.
  - **Crash between 1 and 2:** row is `pending` with no file ⇒ the expiry sweep (A4) reaps it as an
    orphaned-metadata item; no user-visible success was claimed.
  - **Crash between 2 and 4:** row is `pending`, file may exist ⇒ sweep reaps both (delete file,
    mark item terminal). The item was never `stored`, so it is never dispatched.
  - **Orphaned temporary bytes** (file written but row lost/crashed pre-commit) are bounded by the
    sweep scanning the staging dir for tokens with no live `pending`/`stored` row.
  - **Recovery is idempotent and at-most-once** (no exactly-once claim); re-running the sweep on a
    partially-cleaned item is safe.
- **Failure/crash:** staging write failure ⇒ item stays `pending` (row exists), notify; **no `stored`
  state and no dispatch**.
- **Tests:** oversized file rejected; disallowed type rejected; traversal filename neutralized;
  staging dir mode; download failure ⇒ item not `stored`; crash-before-write and crash-after-write
  recovery (row-first) leave no dispatchable item.
- **Acceptance:** adversarial validation tests pass; no file created on rejection; every incomplete
  item is reachable by the sweep.
- **Evidence:** test names + staging-dir listing.
- **Rollback:** delete staging dir contents; **disable via the new flag** (F7 — the flag does not
  exist yet and must be added; see §3.3).
- **Blockers:** size/type bounds are **D-12** (PROVISIONAL default; not blocking) — no owner decision
  blocks this stage. **Current status: `AUTHORIZED TO START — LOCAL-ONLY D-09-R2 EXCEPTION`** (see §3.8).

### Stage A2 — Batch identity, ownership, and 15-minute deadline

- **Objective:** bind files to user+conversation+batch; persist `T0`; never extend.
- **Scope/files:** `bot/attachments.py`, `bot/db.py`, `bot/handlers.py` (new `handle_attachment`
  entry), `bot/app.py` (handler registration for the supported subset).
- **Current behavior:** `handle_unsupported_attachment` rejects. **Intended:** supported attachments
  create/append to a batch; `T0` set at first file only; reply «استلمت… ابعت الأوامر في 15 دقيقة».
- **DB impact:** `attachment_batches(T0, status)`, `attachment_items`.
- **Security invariants:** ownership check (`_authorized_conversation`) **before** any durable
  accept; tombstone fail-closed; cross-conversation isolation.
- **Failure/crash:** crash after accept ⇒ batch row durable ⇒ recovery resumes; crash before accept
  ⇒ redelivery re-runs (dedup by `update_id`).
- **Tests:** first-file sets `T0`; second file does **not** change `T0`; expired batch rejects a new
  file (starts a new batch — **decision A1/A4** recorded); tombstoned conversation ⇒ reject;
  non-owner ⇒ ignored; duplicate update ⇒ single batch.
- **Acceptance:** deadline tests pass; isolation tests pass; the accept writes a **durable intent
  outcome** — see the ack-outcome rule below (no false success).
- **Acknowledgement outcome (F8) — do not overload `explicitly_ignored`.** The outcomes must be
  distinguished exactly:
  - **Accepted durable work** (a batch/item row is durably written) ⇒ `durable_intent_recorded`
    (ack-eligible). **`explicitly_ignored` must NOT be used to represent accepted durable work.**
  - **No durable work / intentionally dropped update** (e.g. unauthorized user, or an update that
    matched no action) ⇒ `explicitly_ignored`.
  - **Rejected attachment** (unsupported type/oversize, nothing persisted) ⇒ `explicitly_ignored`
    **only if** no durable row was written; if a `rejected` item row is written, the outcome is
    `durable_intent_recorded` (durable record exists) — **not** a bare ignore.
  - **Transient processing failure** ⇒ `failed_transient` (not ack-eligible; retried by redelivery).
  - **Permanent processing failure** ⇒ `failed_permanent` (not ack-eligible).
  - **Ambiguous/unknown** ⇒ `partial_or_unknown` (not ack-eligible; fail-closed).
- **Evidence:** test names + DB row dumps + the recorded `processed_updates.outcome` value.
- **Rollback:** drop the two tables; revert handler registration.
- **Blockers:** **none beyond its own acceptance criteria** — authorized under the narrow **D-09-R2
  local-only exception** (see §3.8). **Current status: `AUTHORIZED TO START — LOCAL-ONLY D-09-R2
  EXCEPTION`.**

### Stage A3 — Accompanying-text requirement + durable dispatch intent

- **Objective:** dispatch **only** on text within the deadline; record intent durably **before** any
  external call.
- **Scope/files:** `bot/handlers.py::handle_text` (batch-aware branch), `bot/attachments.py`,
  `bot/db.py`.
- **Current behavior:** `handle_text` routes by `awaiting_kind`. **Intended:** if a live batch exists
  for the user, the text is the accompanying command; write the dispatch intent row **in the same
  transaction** as the update's `processed_updates.outcome`.
- **DB impact:** intent row (batch status → `dispatching`), atomic with outcome.
- **Security invariants:** deadline evaluated **once, atomically** with the intent write (no
  text/expiry race); late text cannot revive an expired batch.
- **Failure/crash:** crash after intent, before external call ⇒ durable intent ⇒ recovery performs
  it; crash before intent ⇒ redelivery re-runs.
- **Tests:** text within deadline ⇒ intent + eligible outcome; text after deadline ⇒ expired, no
  dispatch; text+expiry race ⇒ exactly one outcome; files-only ⇒ never dispatch.
- **Acceptance:** atomicity tests (BEGIN IMMEDIATE) pass; ack-eligibility correct.
- **Evidence:** test names + txn assertions.
- **Blockers:** the **local intent** portion is **authorized** under the narrow **D-09-R2 local-only
  exception** (see §3.8) — **Current status: `AUTHORIZED TO START — LOCAL-ONLY D-09-R2 EXCEPTION`.**
  The **external call** it ultimately feeds is Stage B1 and remains `NOT AUTHORIZED TO START`
  (`BLOCKED — OWNER DECISION REQUIRED (D-10, D-11)`).

### Stage A4 — Cleanup, expiry sweep, and observability

- **Objective:** reclaim local staging on terminal/expiry; structured, secret-free logging.
- **Scope/files:** `bot/attachments.py` (sweep logic); the sweep is **invoked from an already-existing
  lifecycle hook** — the startup recovery hook in `bot/app.py` (alongside
  `deletion.reconcile_pending_deletions`) and/or an **existing** worker's tick. **No new worker,
  scheduler, process, or independent database owner** (F4; register I3; D-09/H lines 625–626). The
  exact integration point must be confirmed during implementation.
- **Current behavior:** none. **Intended:** on `expired`/`rejected`/`failed`/`delivered`-terminal,
  delete staged bytes; log event names only.
- **DB impact:** status transitions only.
- **Security invariants:** cleanup **only** after terminal evidence (I12); never before
  reconciliation completes; never log content/paths of user files beyond opaque ids.
- **Failure/crash:** crash mid-sweep ⇒ idempotent re-sweep on restart; no new lifecycle is created.
- **Tests:** expired batch ⇒ staging removed; `uncertain` batch ⇒ staging **retained**; logs contain
  no content/secret.
- **Acceptance:** retention/cleanup tests pass; log scan clean; **no new worker/scheduler is
  introduced** (verified by inspection).
- **Evidence:** test names + staging listing before/after.
- **Blockers:** **D-07/D-08** govern the **remote/materialized** copy retention (not the local sweep),
  which remains `BLOCKED — OWNER DECISION REQUIRED`. The **local sweep** itself is authorized under the
  narrow **D-09-R2 local-only exception** (see §3.8) — **Current status: `AUTHORIZED TO START —
  LOCAL-ONLY D-09-R2 EXCEPTION`.**

### Stage B1 — Transport: create-op upload + narrow auth + validation contract

- **Objective:** call the upstream create-op endpoint (multipart) with a narrow, conversation-bound
  credential and an `Idempotency-Key`/`client_operation_id`.
- **Scope/files:** `bot/openhands_client.py` (new upload method), `bot/attachments.py`,
  `bot/outbox.py` (item kind — see B3).
- **Current behavior:** no upload path. **Intended:** per proposal §5.2–§5.7.
- **DB impact:** persist returned `operation_id`; `dispatching` state.
- **Security invariants:** narrow auth (no broad key); server-side binding; size/type validated
  **before** upload.
- **Failure/crash:** timeout/5xx ⇒ `uncertain` (**never** blind-retry).
- **Tests:** contract tests against a **local stub** (no production calls); idempotency replay;
  validation-before-upload.
- **Acceptance:** stub-based tests pass; no production contact.
- **Blockers:** **D-10, D-11** (owner) and **§5.2/§5.3/§5.7** (upstream). **Current status:
  `NOT AUTHORIZED TO START`.** **Gate: BLOCKED — OWNER DECISION REQUIRED (D-10, D-11).**

### Stage B2 — Reconciliation (status endpoint) + uncertain handling

- **Objective:** resolve `uncertain` via the status endpoint; never assume delivery.
- **Scope/files:** `bot/openhands_client.py`, `bot/attachments.py`, recovery hook.
- **Current behavior:** n/a. **Intended:** poll `GET …/attachments/{operation_id}` until terminal or
  expiry; `stored`/`rejected`/`failed`/`uncertain`.
- **DB impact:** terminal state transitions.
- **Security invariants:** no blind retry; bounded polling; fail-closed on ambiguity.
- **Tests:** uncertain → terminal; still-uncertain at `expires_at` ⇒ `expired`; no retry storm.
- **Blockers:** **D-15** (window confirmation), **§5.9** upstream. **Current status: `NOT AUTHORIZED
  TO START`.** **Gate: BLOCKED — OWNER DECISION REQUIRED (D-15 for the remote window; upstream §5.9).**

### Stage B3 — Delivery to the same conversation + outbox integration

- **Objective:** deliver the staged content to the **same** conversation and send the accompanying
  text; integrate with the existing outbox at-most-once.
- **Scope/files:** `bot/outbox.py` (new item kind or owner-approved mechanism), `bot/handlers.py`,
  `bot/openhands_client.py`.
- **Current behavior:** outbox is **text-only** (`send_message`). **Intended:** per proposal §5.14
  delivery contract; the agent can read the file.
- **DB impact:** outbox item carries the operation reference/`delivered_path`.
- **Security invariants:** ack boundary advances only on eligible outcomes; tombstone guards at entry
  and pre-CAS; no exactly-once claim.
- **Failure/crash:** crash windows 1–7 (proposal §8.3) traced; no batch loss.
- **Tests:** outbox item lifecycle; tombstone discard; crash-window simulation; no duplicate file.
- **Blockers:** **D-14** (owner, architecture), **D-22** (outbox limit), **D-16** (idempotency),
  **D-06** (root binding), **§5.14** upstream. **Current status: `NOT AUTHORIZED TO START`.** **Gate:
  BLOCKED — OWNER DECISION REQUIRED (D-14, D-22, D-16, D-06).**

### Stage C1 — Delivery evidence (`delivered`) + truthful success

- **Objective:** assert `delivered` only with the successful-read signal (U-3) from a trusted issuer
  and a quiesced source.
- **Scope/files:** `bot/attachments.py`, `bot/openhands_client.py`.
- **Current behavior:** n/a. **Intended:** per proposal §5.14/§5.15 U-3.
- **Security invariants:** fail-closed when evidence is missing; never claim delivery.
- **Tests:** missing signal ⇒ not `delivered`; forged signal (untrusted issuer) ⇒ rejected.
- **Blockers:** **D-01, D-02, D-03, D-04** (owner + external/upstream). **Current status: `NOT
  AUTHORIZED TO START`.** **Gate: BLOCKED — OWNER DECISION REQUIRED.**

### Stage C2 — Independent security review gate (release)

- **Objective:** independent adversarial review before declaring P0 complete.
- **Scope/files:** none (review artifact).
- **Blockers:** **D-19**. **Current status: `NOT AUTHORIZED TO START`.** **Gate: BLOCKED — OWNER
  DECISION REQUIRED.** *(D-19 is not a prerequisite for starting the locally authorized A0–A4 subset
  under D-09-R2, but it **remains mandatory** for this security/release stage and for release/acceptance;
  see §3.8.)*

### Stage D0 — End-to-end acceptance (only after B/C)

- **Objective:** verify the full flow against a **non-production** environment/stub.
- **Blockers:** all of B/C; the register §7 gate. **Current status: `NOT AUTHORIZED TO START`.**

---

## 7. Delivery and Telegram ACK safety analysis

- **Durable state transitions and recoverability points** (mirrors proposal §8.3):
  1. Batch accept (A2): durable **before** any ack copy ⇒ redelivery re-runs (dedup by `update_id`).
  2. Dispatch intent (A3): durable **in the same txn** as `processed_updates.outcome` ⇒ recoverable.
  3. External call (B1): after intent ⇒ crash ⇒ `uncertain`, reconciled (B2), **never** blind-retried.
  4. Result record (B2): atomic with outcome.
  5. Outbox dispatch (B3): existing at-most-once; tombstone guards fail-closed.
- **Explicit prohibitions honored by design:**
  - **No ack before durable state:** ack only on `durable_completed`/`durable_intent_recorded`/
    `explicitly_ignored`/`duplicate_completed`; attachment intents must map to these (never
    `partial_or_unknown`).
  - **No silent loss after dedup:** dedup (`processed_updates`) is written **with** the durable row;
    a crash before the write ⇒ redelivery re-executes.
  - **No false success after outbox/DB failure:** failures map to non-eligible outcomes; the boundary
    stops (head-of-line) — existing behavior preserved.
  - **No unsafe duplicate-dispatch assumptions:** at-most-once + reconciliation; no exactly-once
    claim.
- **`AWAITING_TTL` (10 min) vs attachment window (15 min):** kept **separate**; the attachment batch
  does not reuse the routing TTL.

---

## 8. Testing and independent-review strategy

- **Focused tests per stage:** listed under each stage (§6).
- **Full-suite regression:** `python -m pytest -q` (the figure "2595 passed" is a **historical/unverified
  reference from project memory — it is NOT a currently verified test result** and **must be
  independently re-established before implementation acceptance**; this documentation-only task does
  not run the suite) + `node --test tests/frontend/*.test.js`; lint
  `python -m pyflakes bot/ automation/ tools/ main.py tests/`.
- **Failure injection / rollback:** simulate DB errors mid-transaction; assert `rollback` and no
  partial state (pattern: `tests/test_one_shot_awaiting_atomicity.py`,
  `tests/test_outbox_pre_cas_recovery.py`).
- **Cross-user / cross-conversation isolation:** user A's batch invisible/undispatchable by user B;
  conversation X's batch cannot target conversation Y.
- **Expiration / deadline boundary:** exactly-15-min boundary; late text cannot revive; extra files
  do not extend.
- **Multiple attachments:** append without `T0` change; ordering stable.
- **Crash/restart + retry:** restart mid-batch, mid-intent, mid-call; recovery resumes correctly.
- **Duplicate Telegram updates:** reuse `Application.process_update` harness
  (`tests/test_duplicate_update_dispatch.py`).
- **Adversarial security review:** required before completion (Stage C2, D-19).
- **Independent review requirement:** independent adversarial review (project practice: Cloud API
  conversation with `selected_repository`/`selected_branch`, embedding the diff) before P0 is
  declared complete.
- **Constraint:** tests must **not** contact production OpenHands or use real user sessions; use
  local stubs (`tests/_real_http.py`, `httpx` MockTransport).

---

## 9. Blockers and authorization by stage

**A0–A4 are `AUTHORIZED TO START — LOCAL-ONLY D-09-R2 EXCEPTION`.** **B1–B3, C1, C2, and D0 are
`NOT AUTHORIZED TO START`** under the current recorded decisions (general register §7 gate, with the
narrow D-09-R2 exception applying **only** to A0–A4; see §3.8).

| Stage | Status | Additional blocker(s) beyond the §7 gate | Type |
| --- | --- | --- | --- |
| A0 | **AUTHORIZED (local, D-09-R2)** | none (own acceptance criteria apply) | owner (exception) |
| A1 | **AUTHORIZED (local, D-09-R2)** | D-12 (bounds, PROVISIONAL; not blocking) | owner (exception) |
| A2 | **AUTHORIZED (local, D-09-R2)** | none (own acceptance criteria apply) | owner (exception) |
| A3 | **AUTHORIZED (local, D-09-R2)** | local intent only; external call = B1 (not authorized) | owner (exception) + upstream |
| A4 | **AUTHORIZED (local, D-09-R2)** | local sweep only; D-07/D-08 govern remote retention (not authorized) | owner (exception) |
| B1 | `NOT AUTHORIZED TO START` | D-10, D-11 (+ upstream §5.2/§5.3/§5.7) | owner + upstream |
| B2 | `NOT AUTHORIZED TO START` | D-15 (+ upstream §5.9) | owner + upstream |
| B3 | `NOT AUTHORIZED TO START` | D-14, D-22, D-16, D-06 (+ upstream §5.14) | owner + upstream |
| C1 | `NOT AUTHORIZED TO START` | D-01, D-02, D-03, D-04 | owner + external |
| C2 | `NOT AUTHORIZED TO START` | D-19 (security/release gate) | owner |
| D0 | `NOT AUTHORIZED TO START` | all of B/C | depends |

**A0–A4 are local-only and are authorized to start under the D-09-R2 exception (each stage still
subject to its own documented dependencies and acceptance criteria).** **B1–B3 and Group C remain
`NOT AUTHORIZED TO START`** — no stage outside A0–A4 can proceed under D-09-R1 alone or under D-09-R2.

---

## 10. What this plan deliberately does NOT do

- Does **not** modify the D-09 register or any existing document.
- Does **not** change application code, tests, schema, config, or `.env`.
- Does **not** resolve, reinterpret, or approve any unresolved owner decision.
- Does **not** invent an upstream capability or a delivery mechanism.
- Does **not** introduce a second DB owner, bot process, worker architecture, or backup feature.
- Does **not** authorize any stage beyond the narrow local-only A0–A4 subset already granted by
  D-09-R2; it does **not** authorize B1–B3, Group C, remote transport/delivery, or release/acceptance.

---

## 11. Recommended next step (single)

**Independent adversarial review of this R4 plan before starting A0.** After that review, the locally
authorized **A0–A4** subset may begin under D-09-R2 (each stage subject to its own documented
dependencies and acceptance criteria). **B1–B3 and Group C still require** the resolution of their
blocking decisions (D-10, D-11, D-14, D-15, D-06, D-22, D-16, D-01…D-04) and, for release/acceptance,
the completion of the **D-19** security review.

---

## 12. Owner decision on the local-only A0–A4 exception (RESOLVED — recorded as D-09-R2)

> **This section previously recorded an open question. It has now been answered YES by the owner and
> recorded as `D-09-R2` in the owner decision register. It is preserved below as resolved history.**

**Resolution entry.**

- **Decision:** `D-09-R2` — local-only A0–A4 exception (2026-11-13), register §5 → D-09/I.
- **Owner answer:** **YES**.
- **Precise scope:** **A0–A4 only**, **local-only** (schema/batch model, temporary storage + secure
  validation, batch identity + 15-minute deadline, accompanying text + durable send intent, cleanup +
  expiry + observability).
- **Effect:** these stages may proceed **before** resolution of the Group B/Group C blocking decisions
  and **before** completion of D-19, as a **narrow exception** to the general §7 gate (see §3.8).
- **Still not authorized:** **B1–B3** and **Group C**; **release/acceptance** remains `NOT GRANTED`;
  **D-19 remains mandatory** for the security/release sequence.
- **Not started:** this resolution **does not start** any stage — it is authorization, **not**
  completion.

**Historical question (R3, preserved as resolved):**

> *Does the owner explicitly authorize a local-only A0–A4 implementation subset before resolution of
> the Group B/Group C blocking decisions and completion of D-19, as an exception to the current §7
> execution gate?* — **Answered: YES (recorded as D-09-R2).**

**Historical consequences-of-answers (R3, retained for context):**

- **YES** — requires a **separately recorded, explicit owner decision** with **exact scope, boundaries,
  and conditions**. **This is what occurred:** the decision was recorded as D-09-R2 with the exact
  A0–A4 scope and the §7/D-19 treatment specified.
- **NO** — the existing §7 execution gate would be retained unchanged.

**The owner decision register is the authoritative record** and is **not** modified by this document.

---

*أُعِدَّت هذه الوثيقة بواسطة وكيل ذكاء اصطناعي (OpenHands) نيابةً عن مالك المستودع. خطة تحضير فقط:
لا تُنفّذ أي مرحلة، ولا تُحسم أي قرارات مالك (D-10…D-24)، ولا تُصرّح بأي إجراء غير ما وافق عليه
المالك صراحةً (D-09-R1، وD-09-R2 للاستثناء المحلي المحدود للـ A0–A4). التصريح بالتنفيذ ليس إتمامًا.*
