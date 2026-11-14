# OH-P0 — Secure Conversation Attachment Upload API (upstream capability)

- **Task ID:** `OHB2-P0-OPENHANDS-SECURE-UPLOAD-CAPABILITY-INVESTIGATION-AND-UPSTREAM-SPEC` (r1);
  `OHB2-P0-SECURE-UPLOAD-PROPOSAL-EVIDENCE-CORRECTION-AND-REVISION` (r2);
  `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R3-FINDINGS-REMEDIATION` (r3);
  `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R4-CRITICAL-GAP-REMEDIATION` (r4);
  `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R5-REVIEW-FINDINGS-REMEDIATION` (r5);
  `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R6-READ-EVIDENCE-AND-PRIMITIVE-CORRECTIONS` (r6);
  `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R7-LIFECYCLE-AND-TRUST-REMEDIATION` (r7);
  `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R8-R7-INDEPENDENT-FINDINGS-REMEDIATION` (r8);
  `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R9-R8-INDEPENDENT-FINDINGS-REMEDIATION` (r9);
  `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R10-R9-INDEPENDENT-FINDINGS-REMEDIATION` (r10);
  `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R11-N10-FINDINGS-REMEDIATION` (r11);
  `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R12-N11-CITATION-REMEDIATION` (r12).
- **Type:** Investigation + specification. **No implementation** (upstream or OpenHandBot).
- **Author:** OpenHands agent (autonomous). **Self-review only** — not an independent security review.
- **Date:** r1 2026-11-12; r2 2026-11-11; r3 2026-11-11; r4 2026-11-11; r5 2026-11-11;
  r6 2026-11-11; r7 2026-11-12; r8 2026-11-11; r9 2026-11-11; r10 2026-11-11; r11 2026-11-11;
  **r12 2026-11-11** (r11 independent-findings remediation, see §13).
- **Repo state when written:** `TM-AEM/OpenHandBot`, branch `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW`,
  HEAD `907b20de3fa6627795c14f29677e9f39c68e82f4`; `origin/main` = `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c`.
- **Predecessor evidence:** `docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md` §27
  (verdict `BLOCKED — SECURE OPENHANDS UPLOAD CAPABILITY NOT ESTABLISHED`).
- **Independent reviews that drove revisions:**
  - r2 — `docs/reviews/OHB2-P0-SECURE-UPLOAD-UPSTREAM-PROPOSAL-INDEPENDENT-ADVERSARIAL-REVIEW.md`
    (verdict `PASS_WITH_MAJOR_FINDINGS — REVISION REQUIRED`; findings F1–F4).
  - r3 — `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R2-INDEPENDENT-REVIEW.md`
    (verdict `PASS_WITH_NOTES`; findings R2-1 … R2-9). r3 also carries its own hostile self-review:
    `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R3-SELF-REVIEW.md`.
  - r4 — `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R3-INDEPENDENT-ADVERSARIAL-REVIEW.md`
    (verdict **`NEEDS_REVISION`**; findings **H-1** + **M-1 … M-5** + L-1…L-4/I-1). r4 also carries
    its own hostile self-review: `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R4-SELF-REVIEW.md`.
  - r5 — `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R4-INDEPENDENT-ADVERSARIAL-REVIEW.md`
    (verdict **`NEEDS_REVISION`**; findings **H-1a** + **H-1c** + **M-2-res/M-3b/M-4b/S-1/S-2/S-3**).
  - r6 — `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R5-INDEPENDENT-ADVERSARIAL-REVIEW.md`
    (verdict **`NEEDS_REVISION`**; findings **N-1** (MEDIUM, blocking) + **N-2/N-3** + **N-4/N-5**).
  - r7 — `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R6-INDEPENDENT-ADVERSARIAL-REVIEW.md`
    (verdict **`NEEDS_REVISION`**; findings **R6-1** (MEDIUM, blocking) + **R6-2** (MEDIUM, blocking)
    + **R6-3/R6-4** (LOW) + **R6-5** (INFO)). r7 also carries its own self-review:
    `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R7-SELF-REVIEW.md`.
  - r8 — `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R7-INDEPENDENT-ADVERSARIAL-REVIEW.md`
    (verdict **`NEEDS_REVISION`**; findings **R7-1** (MEDIUM, blocking) + **R7-2** (MEDIUM, blocking)
    + **R7-3** (LOW) + **R7-4** (INFO)). r8 also carries its own self-review:
    `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R8-SELF-REVIEW.md`.
  - r9 — `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R8-INDEPENDENT-ADVERSARIAL-REVIEW.md`
    (verdict **`NEEDS_REVISION`**; findings **R8-1** (MEDIUM) + **R8-2** (MEDIUM) + **R8-3** (LOW)
    + **R8-4** (INFO)). r9 also carries its own self-review:
    `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R9-SELF-REVIEW.md`.
  - r10 — `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R9-INDEPENDENT-ADVERSARIAL-REVIEW.md`
    (verdict **`NEEDS_REVISION`**; findings **R9-1** (MEDIUM) + **R9-2/R9-3** (LOW) + **R9-4**
    (INFO)). r10 also carries its own self-review:
    `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R10-SELF-REVIEW.md`.
  - r11 — `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R10-INDEPENDENT-ADVERSARIAL-REVIEW.md`
    (verdict **`PASS_WITH_NOTES`**; findings **N10-1** (LOW) + **N10-2** (LOW) + **N10-3** (INFO)).
    r11 carries its own self-review: `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R11-SELF-REVIEW.md`.
  - r12 — `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R11-INDEPENDENT-ADVERSARIAL-REVIEW.md`
    (verdict **`PASS_WITH_NOTES`**; findings **N11-1** (LOW) + **N11-2** (LOW) + **N11-3** (INFO)).
    r12 carries its own self-review: `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R12-SELF-REVIEW.md`.
- **Source revisions used (r4):** all upstream facts re-verified against checked-out source at the
  **exact commit SHAs** in §2.1 — `OpenHands/software-agent-sdk@9f7d5cb11b1256c1878f5584a657401feca9ad16`
  (== current `main`, 2026-11-12), `OpenHands/sandbox-server@43e91604ccd0a9960c8d5c52faadd60b30f10e63`
  (== current `main`, 2026-10-22), `OpenHands/OpenHands@a8aaf6813753803cae5182d050909705b0eb02d0`
  (== current `main`, 2026-11-12), and `OpenHands/enterprise@3fac53df8c2efcb67ff3537d1162e8c8a108f565`
  (== current `main`, 2026-11-11 — the repository that serves the live Cloud V1 API, see §2.2). Where
  the generated docs export contradicts source, **source wins** (§2.1 note).
- **Scope note:** this document **specifies** a future capability and an integration contract. It
  does **not** authorize implementing it, does **not** change OpenHandBot behavior, and does
  **not** modify any schema, test, or runtime code.

> **Status: `PARTIALLY COMPLETE — UPSTREAM CAPABILITY OR MAINTAINER DECISION REQUIRED`.**
> A secure design is specified (§5), but the capability does not exist today; it requires an
> upstream OpenHands change and a maintainer decision. **P0 is NOT complete.**
>
> **r2 correction notice.** r1 overstated the gap by treating *all* Agent Server upload routes as
> unconfined and by omitting an existing **conversation-bound, workspace-confined** upload route
> (`POST /api/conversations/{runtime_conversation_id}/file/upload`). r2 corrects the header, §1, §2.1,
> §2.2, §2.3, §2.5, §3, §4, §5.1, §5.7, §7, §10, §11, §12 and §13, and adds §7.0 (minimum upstream
> changes + reuse map). §2.4, §5.2–§5.6, §5.8–§5.12, §6, §8 and §9 are **unchanged**.
> The **recommended design and the security/integration requirements are preserved**; only the
> evidence, the existing-vs-missing classification, and the "minimum change" analysis changed.
>
> **r3 correction notice (findings remediation).** r3 resolves the residual notes from the r2
> independent review (`PASS_WITH_NOTES`, findings R2-1 … R2-9). **R2-1:** corrected the Cloud
> provenance to name **`OpenHands/enterprise`** as the repository that serves the live Cloud V1 API
> (not a "newer build of the same repo"); §2.1, §2.2, §11. **R2-6:** defined an **observable
> `consumed` transition** with an explicit owner, event, durability rule, crash rule, and its
> interaction with Telegram delivery / the 15-minute deadline / late text / ambiguous outcomes; §5.9,
> §5.10, §7.5, §8.1. **R2-8:** added **`expires_at`** to the operation-status schema with semantics;
> §5.9. **R2-9:** **removed the unreachable `uploading` state** from the declared state model; §5.5,
> §5.9. **R2-4:** added a **legacy-Enterprise/frontend compatibility note**; §5.13. **R2-2:** noted
> that Cloud `send-message` already performs the server-side runtime hop; §2.2, §4. **R2-7:** added a
> **staging-visibility** note; §5.7. **Preservation:** no security requirement, threat-model row, or
> P0 invariant was **weakened** — the four-gap conclusion, the rejected approaches, the §6 threat
> mitigations, and §8 invariants I1–I13 are intact. Textual changes are confined to §2.1, §2.2,
> §2.5, §4, §5.5, §5.7, §5.9 (+ new §5.9.1), §5.10, §5.13 (new), §7.5, §8.1, §9, §10.1, §11, §12,
> §13; §5.2–§5.4, §5.6, §5.8, §5.11, §5.12, §6 and §8 are otherwise unchanged. See §13.
>
> **r4 correction notice (critical-gap remediation).** r4 resolves the r3 independent adversarial
> review (`docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R3-INDEPENDENT-ADVERSARIAL-REVIEW.md`,
> verdict **`NEEDS_REVISION`**; findings **H-1** + **M-1 … M-5** + L-1…L-4/I-1). **The central
> problem — securely storing a file does not establish that the agent can read it — is now solved by
> a complete end-to-end delivery contract (new §5.14).** Summary (details in §13):
> **H-1 (HIGH):** added **§5.14 "Agent-readable content delivery"** defining the full path from
> uploaded bytes to agent-readable content — resolution of `stored_path_ref` → **materialization as a
> real file in the conversation workspace** (chosen over an unverified tool), the resolving and
> authorizing components, conversation-identity verification, how the agent learns the content
> exists, the read/ingestion evidence required, and the failure modes; the delivery contract is
> marked **NEW upstream capability (owner decision Q14)** and the *existing* alternatives are
> explicitly classified **unsupported** **(superseded by the r5 notice below: the capability is
> *partly composable, partly new* — §5.14.1; and the read evidence is a *successful* read — §5.14.0;
> **and again by the r6 notice: the read evidence requires a NEW U-3 signal, not a non-error
> observation — §5.15 U-3**)**. **M-1 (MEDIUM):** added **§8.3 durable-ordering + crash-window
> analysis** (seven crash boundaries) reconciled with the OpenHandBot ack architecture
> (`OHB2-TELEGRAM-ACK-ARCHITECTURE-ADR.md`); no exactly-once claim. **M-2 (MEDIUM):** corrected the
> `send-message` description — it is a **thin proxy** with **no durable Cloud write**; §5.9.1 now
> requires **NEW** Cloud work for a durable accept and defines the missing contract (§5.9.1, §5.15).
> **M-3 (MEDIUM):** cleanup no longer keys on `consumed_at`; deletion requires **new terminal
> evidence** (`delivered` after agent read/ingestion, or `expires_at`) — §5.10/§5.15. **M-4
> (MEDIUM):** added **§5.16 correlation + rejection observability** (client `operation_id` + server op
> row on reject) and made the state machine match the create contract. **M-5 (MEDIUM):** moved the
> fixed deadline to the **batch** and mapped batches to operations (§5.10/§5.15, §8.4). **L-1…L-4/I-1**
> addressed. **Preservation:** no security requirement, threat-model row, or P0 invariant was
> **weakened**; §5.2–§5.4, §5.6–§5.8, §5.11–§5.13, §6, §7.0–§7.4, §7.6–§7.8 and §9 items 1–10 are
> intact. Textual changes are confined to the header, §2.2, §4, §5.5, §5.7, §5.9 (+ §5.9.1), §5.10,
> §5.14 (new), §5.15 (new), §5.16 (new), §7.1, §7.5, §8.1 (I12–I14), §8.2 (S3/S5/S7/S8/S10), §8.3
> (new), §8.4 (new), §9 (criteria 7b/7c/11), §10.1/§10.2, §11, §12 (Q5/Q11/Q12/Q13 updated;
> Q14–Q17 new), §13. See §13.
>
> **r5 correction notice (R4 review findings remediation).** r5 resolves the R4 independent
> adversarial review
> (`docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R4-INDEPENDENT-ADVERSARIAL-REVIEW.md`, verdict
> **`NEEDS_REVISION`**). The review found that r4's **own new text** was imprecise or
> self-contradictory; r5 corrects **all eight** findings with no weakening of any security
> requirement:
> - **H-1a (MEDIUM) — read evidence must be a *successful* read.** §5.14.0 now separates the
>   lifecycle facts (r5 stated **seven**, F1–F7 — **superseded**; **r6: eight**, F1–F5 + F6a/F6b + F7;
>   **r7 retains eight**); §5.14.2 step 6 requires **F6**
>   (a correlated **non-error**
>   `ObservationEvent` for an `ActionEvent` naming `delivered_path`) and explicitly rejects a bare
>   `ActionEvent` (F4) and an `AgentErrorEvent`. F7 is **not** modeled. **⚠ SUPERSEDED by r6 (N-1,
>   see the r6 notice below):** the r5 rule "a correlated **non-error** observation" is
>   **insufficient** — a failed terminal read is non-error; §5.14.0 now separates **F6a** (non-error
>   observation) from **F6b** (successful content read), and `delivered` requires the **new U-3
>   signal** (§5.14.2 step 6, §5.15).
> - **H-1c (LOW) — "partly composable, partly new".** §5.14.1 now cites the **existing durable**
>   Cloud primitives `POST /api/v1/conversations/{id}/pending-messages` (durable SQL message-accept)
>   and `GET /api/v1/conversation/{id}/events/search` (durable, conversation-bound, Cloud-reachable
>   event log); the attachment op, server-to-server materialization, delivery authorization, and the
>   successful-read **rule** remain new. **⚠ CORRECTED by r6 (N-3):** the `pending-messages` record is
>   **start-only** (drained once at conversation start) and is **not** an active-conversation accept —
>   a durable accept for a **running** conversation is **new work** (U-2); only `events/search` is
>   composable for the running-conversation case (§5.9.1, §5.14.1, §5.15 U-2).
> - **M-2-res (MEDIUM) — one definition of `consumed_at`.** §5.9.1 now defines it as a **message-accept
>   marker** (set **only** on a **durable** accept; **not** by the thin-proxy `send-message`), removing
>   the r4 §7.5 contradiction.
> - **S-1 (MEDIUM) — staging is synchronous.** §5.5/§5.9 now agree: a successful create returns
>   **`stored`**; `accepted` is **internal-only** and never returned.
> - **M-3b (LOW) — reclaim of the delivered copy.** §5.10 now states the per-artifact rule: on
>   `delivered`, only the **staging** copy is reclaimed; the delivered copy persists.
> - **M-4b (LOW) — `client_operation_id` is required.** §5.4/§5.16 now require it, with uniqueness
>   scope `(principal, conversation_id)` and a duplicate-payload rule (`409
>   client_operation_id_conflict`).
> - **H-1b / S-2 / S-3 (LOW/INFO) — path, boundary, filesystem.** §5.14.2 step 5 ties
>   `delivered_path` to the confined workspace root; §8.3 states the **integration boundary** (the
>   outbox carries **text only**; attachment dispatch needs a new payload capability); §7.4 lists the
>   required **filesystem guarantees** (atomic publication, readable mode/owner, partial-write
>   cleanup).
>
> **Preservation:** no security requirement, threat-model row (one row **added**: T-21), or P0
> invariant was weakened. Textual changes are confined to the header, §1, §2.2, §4, §5.4, §5.5,
> §5.6, §5.8, §5.9 (+ §5.9.1), §5.10, §5.11, §5.14 (incl. new §5.14.0), §5.15, §5.16, §6 (T-18/T-19
> refined, T-21 added), §7.1, §7.4, §7.5, §8.1 (I12/I14), §8.2 (S7), §8.3, §9 (7b/7c), §10.1/§10.2,
> §11, §12, §13. See §13.
>
> **r6 correction notice (read-evidence + primitive corrections).** r6 resolves the r5 independent
> adversarial review
> (`docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R5-INDEPENDENT-ADVERSARIAL-REVIEW.md`, verdict
> **`NEEDS_REVISION`**; findings **N-1 … N-5**). **No security requirement, threat-model mitigation,
> or P0 invariant is weakened; the changes make the read-evidence and retention rules *stricter*.**
> - **N-1 (MEDIUM) — the successful-read evidence rule was insufficient.** r5 accepted *any*
>   correlated **non-error** `ObservationEvent` as F6. Source (pinned) shows a **terminal** tool call
>   that **fails** still returns a **non-error** `TerminalObservation` (the tool sets `is_error=True`
>   only for interaction/multi-command/closed-terminal cases; a non-zero `exit_code` does **not** set
>   it) ⇒ `cat <missing>` could set `delivered`. r6 **withdraws** "non-error observation" as a
>   sufficient signal, adds the **eight-fact** model (**§5.14.0**), and states that **no existing
>   primitive proves a successful content read**; the **safe contract** is that `delivered` is
>   **not reachable** from existing primitives — it requires a **new, explicit structured read
>   acknowledgment** (**U-3**, a proposed upstream capability, §5.14.2 step 6 / §5.15), and until it
>   exists the operation **stays `stored`** and the bytes are retained **until `expires_at`**
>   (§5.10). The **fallback authorizes no early reclaim**.
> - **N-2 (LOW) — the §5.5 example returned `accepted`.** Fixed to `"state": "stored"` (§5.5), and
>   every example re-checked against the state machine.
> - **N-3 (LOW) — the `pending-messages` "composable durable accept" was overstated.** Source
>   (pinned) shows that queue is drained **only during the conversation-*start* handshake**
>   (`_process_pending_messages`, called once after the start task reaches `READY`), is **deleted
>   regardless of delivery success**, and is **capped at 10** — it is **not** a durable accept for an
>   **already-running** conversation. §5.9.1/§5.14.1/§5.15 U-2/§8.2 S7 now state the **start-only**
>   limitation and re-classify U-2 as **NEW for the running-conversation case**.
> - **N-4 (INFO) — the `cat` reader had no success signal.** §5.14.2 step 5 now names the reader and
>   its success signal, and **explicitly rejects** a terminal reader whose non-zero exit is a
>   **failed** read (a non-zero `exit_code` is a failure even when `is_error` is `false`).
> - **N-5 (INFO) — stale revision identity.** The header now identifies the document as **r6** and
>   lists the r5 + r6 task ids (§13 carries the r6 row).
>
> **r7 correction notice (lifecycle + trust remediation).** r7 resolves the r6 independent adversarial
> review
> (`docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R6-INDEPENDENT-ADVERSARIAL-REVIEW.md`, verdict
> **`NEEDS_REVISION`**; findings **R6-1 … R6-5**). **The central change is that the 15-minute
> wait-for-text deadline is *never* a content-deletion authorization**, and that every physical copy
> gets its own **independent** lifecycle. **No security requirement, threat-model mitigation, or P0
> invariant is weakened; the lifecycle and trust rules are made *stricter* and *more explicit*.**
> - **R6-1 (MEDIUM, blocking) — the workspace copy could be deleted at `expires_at` while the agent
>   still needed it.** r6 left the **materialized (delivered) copy** subject to an `expires_at`
>   reclaim when `delivered` was not reached; because r6 also made `delivered` **unreachable** (no
>   U-3), a successfully materialized file was removed ≤ 15 min after materialization — the very
>   **premature-deletion (T-19)** class the document claims to close, and a contradiction with r6's
>   own "persists for the life of the conversation". r7 introduces a **dedicated lifecycle section
>   (§5.10, re-derived)** that separates **eight** distinct deadlines/lifetimes (wait-for-text
>   deadline, batch cancellation, staged/recovery copy, workspace copy, operation records, read
>   evidence, end-of-use evidence, and the deletion policy), and states that **`expires_at` reclaims
>   only the staged/recovery copy — never the workspace copy**. A materialized workspace copy is
>   reclaimed **only** on a trustworthy **end-of-use** condition or when the **workspace itself** is
>   removed (§5.10.2). The r6 contradiction is **withdrawn**.
> - **R6-2 (MEDIUM, blocking) — U-3 had no trustworthy issuer.** r6 allowed U-3 to be "emitted by the
>   reader, or by the delivery layer" — an **agent-controlled** acknowledgment would then be
>   self-attestation. r7 defines the **U-3 trust boundary (§5.15.1)**: U-3 is a **service-to-service,
>   authenticated, Cloud/Agent-Server-side** signal that the **agent cannot forge**; an agent/tool/
>   model-produced event (a tool result, an `ObservationEvent`, a prompt reply, an arbitrary event)
>   is **never** authoritative evidence. Because the pinned source does **not** establish that such an
>   issuer exists, the issuer is classified **NEW upstream capability** and the trust property is
>   **UNVERIFIED**; **`delivered` stays unreachable** until it is implemented and independently
>   verified. §5.15.2/§5.15.3 specify the **provenance/authentication** requirements and the **exact
>   fields + validation invariants**, and §5.14.0/§5.14.2 step 6 keep **tool invocation, file open,
>   complete bytes read, untruncated return, delivery-to-execution-context, and end-of-use** distinct.
> - **R6-3 (LOW) — the Cloud event history is a *polled replica*, not an atomic view.** r7 verifies
>   the pinned source (`remote_sandbox_service.py::poll_agent_servers` → `refresh_conversation` →
>   `event_service.save_event`, sha256 `d239ec43…`) and states the **required consistency guarantee**
>   (§5.15.4): any event-based evidence MUST be read from a **quiesced/finalized** source (or
>   re-verified on the **agent-server**), not from the replica; where the current API cannot provide
>   that, it is **NEW upstream work (U-10)** and **no** evidence may be taken from the replica.
> - **R6-4 (LOW) — the reader expects an *absolute* path.** r7 verifies `file_editor::validate_path`
>   (`is_host_absolute_path`, sha256 `a1d735d4…`) and defines a full **path contract (§5.15.5)** —
>   server-side resolution, workspace root, **absolute** representation handed to the agent,
>   post-resolution confinement, symlink/TOCTOU protection, existence/regular-file checks, content
>   identity, permissions, and the **reader's exact accepted input** — and proves the
>   producer-to-reader flow is implementable, or classifies any missing piece as **NEW upstream
>   work**.
> - **R6-5 (INFO) — stale "seven lifecycle facts" wording.** r7 removes every surviving "seven
>   lifecycle facts"/"F1–F7"-as-current reference so the header, overview, tables, threat analysis,
>   requirements, and revision history consistently describe the **eight-fact** model (historical
>   rows are marked **superseded**).
>
> **r8 correction notice (r7 independent-findings remediation).** r8 resolves the independent
> adversarial review of r7
> (`docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R7-INDEPENDENT-ADVERSARIAL-REVIEW.md`, verdict
> **`NEEDS_REVISION`**; findings **R7-1 … R7-4**). **No security requirement, threat-model
> mitigation, or P0 invariant is weakened; the lifecycle and provenance rules are made *stricter*,
> *more precise*, and *source-grounded*.**
> - **R7-1 (MEDIUM, blocking) — the "workspace is removed on conversation delete" C2-reclaim premise
>   was not source-grounded and is false for grouped sandboxes.** r7 made **workspace removal**
>   (conversation archived/deleted) the *sole* non-F7 way a materialized workspace copy (C2) is ever
>   reclaimed. Against the pinned source this is **not** what a conversation delete does: the Cloud
>   delete finalizer **archives** the workspace to a bucket (`_finalize_sandbox_delete` →
>   `archive_conversation_workspace` → `workspace_archive.archive_workspace`) and tears the **sandbox**
>   down only when **no sibling conversation still references it**; the agent-server delete explicitly
>   **preserves** the workspace ("Safely remove only the conversation directory (**workspace is
>   preserved**)"). Under **sandbox grouping** (any non-`NO_GROUPING` strategy) a sibling keeps the
>   sandbox alive, so the workspace directory is **not** removed at all. r8 therefore **withdraws** the
>   "workspace is removed on conversation delete" premise, states plainly that **today no
>   conversation-scoped event reclaims C2**, defines the physical-removal path as the **sandbox/pod
>   teardown** (**r9/R8-1 precision:** teardown *is* modeled for the **managed** backends by the
>   Enterprise sandbox lifecycle with a configurable idle bound, and is **delegated to runtime-api**
>   for the Cloud remote backend — the only part that is genuinely unmodeled), and adds a **grouping
>   caveat**. The disclosed unbounded-storage limitation (Q18) is
>   **strengthened** — there is today **no** conversation-scoped C2 reclaim — and **no cleanup
>   primitive is invented**. See §5.10.1/§5.10.4/§5.14.2 step 7, T-24, I12, §9 7b, Q18.
> - **R7-2 (MEDIUM, blocking) — the path contract resolved the workspace root from a source that does
>   not carry it.** §5.14.2 step 3 and §5.15.5 named `_get_agent_server_context` as resolving the
>   conversation **workspace root**, but that helper exposes only `sandbox_spec.working_dir` (the
>   **ungrouped base**) and its `AgentServerContext` dataclass has **no** per-conversation path field;
>   the grouped root `{base}/{conversation_id.hex}` (`grouped_workspace_dir`) lives in the
>   `archiveworkspacepath` conversation tag, which the helper does **not** read. r8 pins the
>   **authoritative** Cloud-side root source (the `archiveworkspacepath` tag, or an agent-server query
>   for the runtime's own `workspace.working_dir`), states the **grouping** behavior explicitly, adds a
>   **provenance/binding contract** (identity bound to `(principal, conversation_id, operation_id)`;
>   tag write-authority is the server; `_get_agent_server_context` resolves the **runtime endpoint +
>   key**, not the root), and classifies the binding as **proposed/NEW (U-12) + UNVERIFIED** where the
>   pinned source does not establish it — so the proposal no longer presents the per-conversation root
>   as currently available. See §5.14.2 step 3, §5.15.5, U-11/U-12, Q21/Q22.
> - **R7-3 (LOW) — the polled-replica description was not universal.** §5.15.4 said the Cloud
>   `events/search` store "is populated by a best-effort poll loop". Source shows the poller is
>   **conditional**: it starts only when the app server has **no public URL**
>   (`web_url is None or 'localhost' in web_url`); otherwise the store is fed by **webhook callbacks**
>   (whose freshness/lag differ). r8 separates **authoritative state** (the agent-server event log)
>   from the **replicated/eventually-refreshed** Cloud store, states both population paths, and keeps
>   the **quiescence requirement** as applying **regardless of which path populates the store**.
> - **R7-4 (INFO) — two eight-item taxonomies had no cross-map.** r8 adds an explicit, complete
>   **L1–L8 ↔ F1–F7/F6a/F6b cross-map** (new §5.10.0.1) and a **back-reference from §5.14.0**, so the
>   two vocabularies cannot drift and no reader must infer correspondence from ordering.
>
> **r9 correction notice (r8 independent-findings remediation).** r9 resolves the independent
> adversarial review of r8
> (`docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R8-INDEPENDENT-ADVERSARIAL-REVIEW.md`, verdict
> **`NEEDS_REVISION`**; findings **R8-1 … R8-4**). **No security requirement, threat-model mitigation,
> or P0 invariant is weakened.** The r8 remediation was **substantively correct**; r9 corrects two
> **source-grounding / classification** errors and two **citation** defects, and re-states one
> lifecycle distinction more precisely:
> - **R8-1 (MEDIUM) — the physical-removal path is *modeled in the pinned source*, not "unmodeled /
>   outside the pinned repos".** r8 asserted the workspace directory's physical removal happens "only
>   on sandbox/pod teardown ('runtime-api idle reap')", which it called **"not modeled by any primitive
>   in the pinned source"** and **"outside the pinned repos"**. The pinned `OpenHands/enterprise@3fac53df…`
>   contains a **complete, wired sandbox-lifecycle subsystem** —
>   `sandbox/lifecycle/{__init__,settings,sweep,rules,tasks}.py` + `worker/app.py` — whose
>   `delete_after_seconds` (default 10 days) is documented **"Delete a sandbox, and its workspace, once
>   it has not run for this long"** and whose DELETE action calls `sandbox_service.delete_sandbox(...)`.
>   r9 therefore **distinguishes explicitly and consistently**: (a) the **Enterprise sandbox lifecycle**
>   (managed backends **Docker / E2B / k8s**; a periodic sweep + `decide()` → `Action.DELETE` →
>   `delete_sandbox`; a *configurable* bound; the row's `LAST_RAN_AT = greatest(state_changed_at,
>   last_active_at)`) **is** a modeled mechanism in the pinned source, so the removal of the workspace
>   **directory** on teardown is **not** universally "unmodeled"; (b) the **Cloud/runtime-api**
>   conversation lifecycle is **delegated to runtime-api** (`lifecycle/__init__.py`: "runtime-api
>   manages the remote backend's sandboxes itself") and is therefore the **only** part whose exact
>   trigger/delay is **not** modeled by these repos; (c) **workspace archival** (a bucket capture) is
>   **not** a deletion; (d) **detachment** (agent-server delete) **preserves** the directory;
>   (e) **aggregation/retention** does not reclaim C2. r9 also states the **applicability** limit: the
>   Enterprise sweeper governs the **managed** backends, **not** the Cloud remote backend, so it does
>   **not** prove any particular Cloud conversation reached a safe terminal state. The
>   **C2-must-not-be-deleted-while-in-use invariant is preserved** (no copy is deleted while agent
>   consumption may still be active). **No cleanup primitive is invented.** See §5.10.1/§5.10.4,
>   §5.10.3 case 10, §5.14.2 step 7, T-19/T-24, I12, §9 7b, §11, Q18.
> - **R8-2 (MEDIUM) — the Cloud-side per-conversation workspace-root read *exists and ships live*;
>   only the identity/authorization binding is new.** r8 classified the whole root-provenance read as
>   **NEW (U-12) + UNVERIFIED**. The pinned `AppConversationInfo.repositories`
>   (`app_conversation_models.py` `7a4a54c0…`, lines 250-265) is a `@computed_field` that reads the
>   pinned, server-managed `archiveworkspacepath` tag and calls `conversation_repositories(...)`
>   (`additional_repositories.py` `a8d0bbe3…`, `conversation_repositories` def at line 89; the
>   `path=f'{working_dir}/{folder}'` expression at line 106) to build `path = {working_dir}/{folder}` — a
>   Cloud-side resolution of the per-conversation root — and it is exposed in the **live** Cloud V1 API
>   (`AppConversation.repositories` → `ConversationRepository.path` = "Absolute path of the folder in
>   the sandbox", returned by `GET /api/v1/app-conversations` and `/search`). r9 **re-classifies**:
>   the **tag→root resolution is *existing and verified*** (shipped); what remains **NEW/proposed** is
>   only the **identity + authorization binding** of that root to `(principal, conversation_id,
>   operation_id)` and the **write-authorization** — no pinned primitive binds that tuple to the upload
>   operation. r9 keeps the **fail-closed** rule and **does not** treat the existence of the path
>   property as proof that the path is **authorized, immutable, correctly scoped, or symlink/TOCTOU-safe**.
>   See §5.15.6, U-12, T-25, I15, Q22.
> - **R8-3 (LOW) — citation defects.** (a) the `bb9bbe23…` hash is the **enterprise**
>   `sandbox/sandbox_router.py`, not sandbox-server (sandbox-server is `07fef71e…`); (b) the r8
>   self-review named `ws_archive.py` (actual: `workspace_archive.py`) and a nonexistent enterprise
>   `sbx_router.py` (actual: `sandbox_router.py`); (c) a garbled sentence in §2.2. All three are
>   corrected, and duplicate/stale forms are searched for.
> - **R8-4 (INFO) — live-spec identifier refreshed.** The live Cloud V1 `openapi.json` is now
>   `info.version = 1.91.0`, **244** paths, sha256 `f0f4d4e9…` (was `1.87.1`/242/sha256 `0086b0b0…`;
>   **r10/R9-4, extended r11/N10-3: that entire r8-reported value — both the `1.87.1` version string
>   and the `0086b0b0…` digest — is a historical reported value only, NOT INDEPENDENTLY VERIFIED** — see
>   §2.1/§2.2/§11).
>   r9 updates the identifier/evidence date and **re-confirms** the **"no Cloud upload"** conclusion
>   (`multipart` = 0, `format: binary` = 0, no `attach`/`upload` path) — the conclusion is **unchanged**
>   because the route evidence is unchanged, not because the version changed. r9 preserves the
>   distinction between a **live specification observation** and a **pinned repository source**.
>
> **r10 correction notice (r9 independent-findings remediation).** r10 resolves the independent
> adversarial review of r9
> (`docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R9-INDEPENDENT-ADVERSARIAL-REVIEW.md`, verdict
> **`NEEDS_REVISION`**; findings **R9-1 … R9-4**). **Documentation-only; no security requirement,
> threat-model mitigation, or P0 invariant is weakened.** The r9 remediation was **substantively
> correct**; r10 fixes one **internal consistency** defect in the C2 lifecycle wording and three
> **citation/precision** items:
> - **R9-1 (MEDIUM) — the C2 timer claims are now scoped consistently.** r9 correctly documented the
>   **Enterprise sandbox lifecycle** (a **separate** infrastructure timer, `delete_after_seconds`) but
>   left **absolute** statements elsewhere ("no timer deletes C2", "C2 is never timer-deleted", "the
>   only server-side clock is `expires_at`"). r10 replaces every such absolute statement with **precise,
>   scoped** wording: the **operation's `expires_at`** timer reclaims **C1/C3 only** and **never** deletes
>   **C2**; a **separate** infrastructure timer (the Enterprise sandbox lifecycle) **may** remove the
>   sandbox **and its workspace** in governed environments; the two clocks are **distinct and must not be
>   conflated**; applicability to the **Cloud/runtime-api** backend is **delegated** and **not assumed**;
>   and the existence of any infrastructure lifecycle timer **does not prove** that a particular
>   conversation reached a safe terminal-use state. The **C2-must-not-be-deleted-while-in-use invariant
>   is preserved** (it binds the **application**; it does **not** claim the application can prevent
>   external infrastructure deletion). Touches §5.9, §5.10.2, §5.10.3 (case 4 + invariant), §5.10.4,
>   §8.4, §12 Q18, §11(f), §9 7b/§10.1 (already scoped in r9; re-read for consistency). **No cleanup
>   primitive is invented.**
> - **R9-2 (LOW) — `RESERVED_TAG_KEYS` source line corrected.** §11 cited `RESERVED_TAG_KEYS` at "line
>   96"; the correct line is **86** (line 96 is `def _validate_caller_tags(...)`). Fixed in §11; §5.15.6
>   already cited line 86. **No validation behavior or security contract changes.**
> - **R9-3 (LOW) — the modeled teardown is qualified.** The only mechanism the pinned source establishes
>   is **container removal** (`container.remove()`); whether the **underlying workspace data** is
>   physically deleted depends on the **mount layout** (container-local vs host bind-mount), which is
>   **deployment-configurable** (`mounts` empty by default). r10 states explicitly that **physical
>   deletion of the underlying workspace data for all configurations is UNVERIFIED / SOURCE REQUIRED**,
>   and separates container removal, mounted data, physical file deletion, and any external storage
>   lifecycle. The **R8-1 correction stands** (the removal path **is** modeled, contra r8). See §5.10.4.
> - **R9-4 (INFO) — the historical r8 spec digest is labelled unverified.** The r8-era
>   `1.87.1` / 242 paths / sha256 `0086b0b0…ff77916` is a **reported value only — NOT INDEPENDENTLY
>   VERIFIED** (the r8 proposal is not on disk and no artifact establishes the digest). It is retained
>   for **audit history** and is **not** used as evidence for current Cloud V1 route behavior; the
>   **current** evidence is the re-verified `1.91.0` / 244 paths / sha256 `f0f4d4e9…`. See §2.1/§2.2/§11.
>
> **r11 correction notice (r10 independent-findings remediation).** r11 resolves the independent
> adversarial review of r10
> (`docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R10-INDEPENDENT-ADVERSARIAL-REVIEW.md`, verdict
> **`PASS_WITH_NOTES`**; findings **N10-1 … N10-3**). **Documentation-only; no security requirement,
> threat-model mitigation, or P0 invariant is weakened; no cleanup primitive is invented; no
> previously resolved finding is reopened.** All three N10 findings are **citation/labelling**
> corrections; no technical claim changes:
> - **N10-1 (LOW) — the `editor.py` missing-path rejection reference is made stable and consistent.**
>   r10 cited the **same** fact at two different lines — "(line 691)" in §5.15.5 and "(line 693)" in
>   §11. r11 re-fetched `openhands-tools/…/tools/file_editor/editor.py` at the pinned SDK SHA
>   `9f7d5cb1…` (sha256 `a1d735d4…`) and confirms the missing-path guard is the **condition** at
>   **line 689** (`if command != "create" and not path.exists():`) whose body is the
>   `raise EditorToolParameterInvalidError(…)` at **line 690** (the message at line 693 is the third
>   argument of that single raise, lines 690-694). r11 states the **symbol** (`validate_path` →
>   missing-path guard) with the **verified line range 689-694** in **both** places, removing the
>   inconsistency. Touches §5.15.5 and §11.
> - **N10-2 (LOW) — `conversation_service.py` is re-classified to its correct repository.** r10
>   listed the "agent-server delete **preserves** the workspace" citation (`conversation_service.py`,
>   sha256 `9e9b3e63…`, line 1911) under the **`OpenHands/enterprise`** bullet in §11, but the file
>   belongs to **`OpenHands/software-agent-sdk`** at the pinned SHA `9f7d5cb1…`
>   (`openhands-agent-server/openhands/agent_server/conversation_service.py`; independently
>   re-verified this session: sha256 `9e9b3e63…`, 3132 lines, `delete_conversation` at line 1863, the
>   `# Safely remove only the conversation directory (workspace is preserved).` comment at line 1911).
>   `OpenHands/enterprise` has **no** `conversation_service.py`. r11 **moves** the citation to the
>   correct SDK bullet. **The technical claim itself is unchanged** (the agent-server conversation
>   delete preserves the workspace — source-verified). Touches §11.
> - **N10-3 (INFO) — the historical `1.87.1` evidence is qualified everywhere it appears.** r10
>   labelled the unverifiable r8-era **digest** in §1/§2.1/§11, but §2.2 still wrote "**r8 evidence**
>   `1.87.1`" without a verification status. r11 replaces every §2.2 occurrence with "**r8-reported**
>   `1.87.1` (**historical, not independently verified — see §11**)" and adds the same qualifier to
>   the header R8-4 note, so the **historical** r8 value (version string **and** the unavailable
>   digest) is explicitly distinguished from the **current** re-verified evidence (`1.91.0`, 244
>   paths, `f0f4d4e9…`), and no historical value is used to support a current capability claim (the
>   "no Cloud upload" conclusion rests on the **current** route evidence). Touches §1 (header R8-4
>   note), §2.2, §11.
> Self-review: `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R11-SELF-REVIEW.md`. The **next required
> step** is a **fresh independent adversarial review**; this self-review is **not** independent
> approval.

> **r12 correction notice (r11 independent-findings remediation).** r12 resolves the three
> **citation/labelling** findings of the independent adversarial review of r11
> (`docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R11-INDEPENDENT-ADVERSARIAL-REVIEW.md`, verdict
> **`PASS_WITH_NOTES`**; findings **N11-1 … N11-3**). **Documentation-only; no security requirement,
> threat-model mitigation, or P0 invariant is weakened; no cleanup primitive is invented; no
> previously resolved finding is reopened.** All three findings are **line/attribution precision**
> corrections; **no technical claim changes**. Each fact was independently re-derived from the pinned
> source this session:
> - **N11-1 (LOW) — `additional_repositories.py` line reference corrected to the statement line.** r11
>   cited the `path = f'{working_dir}/{folder}'` build at **line 89**; at the pinned revision
>   (`OpenHands/enterprise@3fac53df…`, sha256 `a8d0bbe3…`, 453 lines) **line 89** is the
>   `def conversation_repositories(` definition and the expression is at **line 106**
>   (`path=f'{working_dir}/{folder}' if working_dir else None,`). r12 states the **symbol** plus the
>   **verified line range** (`conversation_repositories` def at line 89; the
>   `path=f'{working_dir}/{folder}'` expression at line 106) at **every** occurrence. Touches §1
>   (r9/R8-2 notice), §5.15.6, §11.
> - **N11-2 (LOW) — `archiveworkspacepath` read line reference corrected.** r11 cited the tag read at
>   **line 1185**; at the pinned revision (`c43ed4f7…`, 2209 lines) **line 1185** is the comment
>   `# Delete the sandbox in the background if no other conversations reference it` and the read is at
>   **line 1188** (`workspace_path = app_conversation_info.tags.get(ARCHIVE_WORKSPACE_PATH_TAG_KEY)`).
>   r12 cites **line 1188** (and notes line 1185 is the preceding comment). Touches §11.
> - **N11-3 (INFO) — cron declaration re-attributed from `sweep.py` to `tasks.py`.** r11 wrote
>   "`sweep.py` cron `* * * * *`". At the pinned revision the **only** cron declaration in the
>   lifecycle subsystem is in **`tasks.py`** (`834e9452…`, line 78:
>   `@lifecycle.periodic(cron='* * * * *')`, on the `sweep` job, `name='sweep'`, line 80);
>   **`sweep.py`** (`1d99bd1c…`, 57 lines) contains **no** `cron` token and holds only the candidate
>   selection (`find_due_sandbox_ids`, `LAST_RAN_AT`). r12 separates the **scheduled-task declaration**
>   (`tasks.py` cron) from the **sweep implementation** (`sweep.py`) from the **lifecycle behavior**
>   (`rules.py::decide` → `Action.DELETE` → `tasks.py` → `delete_sandbox`), and does not imply that the
>   cron declaration proves successful execution or physical workspace deletion. Touches §5.10.4, §11.
> Self-review: `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R12-SELF-REVIEW.md`. The **next required
> step** is a **fresh independent adversarial review**; this self-review is **not** independent
> approval.

---

## 1. Executive summary

OpenHands today has **no supported, least-privilege way for a third party (OpenHandBot) to place a
file into an exact existing conversation.** There are **two** Agent Server upload routes, and they
differ in exactly the way that matters:

- **Legacy, host-level, unconfined:** `POST /api/file/upload` (query `path`). The only path check is
  `is_absolute()`; **no** workspace containment, **no** size/type/count limit. Guarded by the
  **server-wide `X-Session-API-Key`**.
- **Conversation-bound, workspace-confined:** `POST /api/conversations/{runtime_conversation_id}/file/upload`
  (query `path`). Registered by `runtime_router.py::create_runtime_router`, gated by
  `bind_local_conversation_runtime`, which enforces `resolve().is_relative_to(workspace_root)` (else
  **422**). This is the route the official SDK/GUI clients use when the server advertises the
  `conversation_runtime_routes_v1` capability. **But** it is guarded by the **same server-wide
  `X-Session-API-Key`** — conversation binding narrows *reach*, it does **not** narrow *privilege*.

So the accurate statement is **not** "there is no confinement" (r1's error). It is:

> **The missing pieces are authorization scoping, server-side destination resolution, upload
> validation limits, and outcome reconciliation — not conversation binding or workspace
> containment.** Conversation binding and workspace containment already exist on the
> conversation-bound route; they simply are not sufficient on their own, and they are not reachable
> by a third party without the full agent-server key.

What is genuinely absent: **no scoped upload token** (the only credential is the server-wide key,
which also permits arbitrary command execution), **no server-resolved conversation destination**
(the client still supplies the absolute `path`), **no size/type/count limit** (client-side 3 MiB only),
**no upload-operation status/reconciliation endpoint**, and — **r4 (H-1)** — **no mechanism that turns
stored bytes into content the agent can read** (the agent-server message model is text/image only and
read endpoints are not ingestion, §5.14).

This was **re-verified against current source** (not the earlier snapshots and not the stale docs
export): Cloud V1 `openapi.json` v1.91.0 (244 paths, zero upload operations) and Agent Server source
pinned at commit SHAs (§2.1), plus the agent-server tests that assert the confinement behavior.

**New finding (r1, retained).** The official OpenHands **GUI** (`OpenHands/OpenHands`) already ships
user-facing file/image attachment upload — and it does so by calling the Agent Server
`/file/upload` route with the **per-conversation `session_api_key`**. So the capability is
"official" at the product level but remains **unscoped** at the credential level: the official
client is entrusted with the full agent-server key. This confirms the previous verdict and shows
the gap is an **upstream authorization/architecture** gap, not a missing endpoint.

**Recommendation.** Specify a **Cloud-hosted, conversation-bound, scoped upload operation** with a
separate status/reconciliation endpoint (§5). This keeps the bot on a single origin (its existing
`OPENHANDS_BASE_URL`), gives narrow authorization, server-resolved destinations, and reliable
outcome reconciliation, and never grants the bot an agent-server key. It **reuses** the existing
conversation-binding and workspace-containment machinery rather than rebuilding it (§7.0). Approaches
that require the broad agent-server key or arbitrary command execution are **rejected** (§4).

**New finding (r4) — storing a file is not the same as letting the agent read it.** The r3
independent adversarial review (`NEEDS_REVISION`, finding **H-1**) established that a secure upload
alone does **not** establish that the intended OpenHands agent can **read** the uploaded content:
r3's `stored_path_ref` was inert prompt text with no resolver, and no component turned the bytes into
content the agent could open. r4 therefore added a **complete delivery contract (§5.14)** — the
uploaded bytes are resolved by the Cloud, **materialized as a real file inside the conversation
workspace**, and referenced to the agent by a concrete **absolute path** (not an opaque
token), with a defined point of access, a defined read evidence, and defined failure modes.

**r5 corrections (r4 independent adversarial review, verdict `NEEDS_REVISION`).** The r4 review
(`docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R4-INDEPENDENT-ADVERSARIAL-REVIEW.md`) found that r4's
own new text was **imprecise or self-contradictory** in eight places; r5 fixes all eight:
- **H-1a (MEDIUM):** r4's read rule ("a run whose tool calls read `delivered_path`") did **not**
  require the read to **succeed** — an `ActionEvent` is recorded even for a **failed** read. r5
  distinguishes lifecycle facts (§5.14.0) and required a **successful** read (F6): a correlated
  **non-error** `ObservationEvent`; a failed read / `AgentErrorEvent` ⇒ **not** `delivered`
  (§5.14.2 step 6). **r6 (N-1) supersedes this bullet:** a correlated **non-error** observation is
  **not** sufficient (a failed **terminal** read is non-error — see the r6 notice below), so
  `delivered` requires the **new U-3 structured read acknowledgment** and is otherwise
  **unreachable** (§5.14.0, §5.15 U-3).
- **H-1c (LOW):** r4 called the whole delivery capability "new"; r5 documents that it is **partly
  composable** from **existing durable Cloud primitives** — `GET /api/v1/conversation/{id}/events/search`
  (durable, conversation-bound, Cloud-reachable event log) and the durable **`pending-messages`**
  record — and only the attachment op, the server-to-server materialization, the delivery
  authorization, and the **successful-read rule** are new (§5.14.1). **r6 (N-3):** the
  `pending-messages` primitive is **start-time only** — it is **not** an active-conversation accept,
  so a durable accept for a **running** conversation is **new work** (U-2). **r7 (R6-3):**
  `events/search` is a **polled replica**, so it is composable for evidence **only when quiesced**
  (U-10, §5.15.4).
- **M-2-res (MEDIUM):** r4 §7.5 still claimed `consumed_at` is set when `send-message` "durably
  accepts"; r5 gives **one** definition of `consumed_at` (a **message-accept** marker, §5.9.1) and
  removes the contradiction.
- **S-1 (MEDIUM):** r4 §5.5 vs §5.9 contradicted on staging timing; r5 fixes **staging as
  synchronous** (a successful create returns `stored`; `accepted` is internal-only and never
  returned) (§5.5, §5.9).
- **M-3b (LOW):** r4 §5.9 vs §5.10 contradicted on reclaiming the **delivered** copy; r5 states the
  authoritative per-artifact rule — `delivered` reclaims the **staging** copy only (§5.10).
- **M-4b (LOW):** r4 made `client_operation_id` optional; r5 makes it **required** with a uniqueness
  scope and a duplicate-payload rule (§5.4, §5.16).
- **H-1b/S-2/S-3 (LOW/INFO):** r5 ties `delivered_path` to the confined workspace root (§5.14.2
  step 5), states the **integration boundary** (the outbox carries **text only**; attachment dispatch
  needs a new payload capability — §8.3), and lists the required **filesystem guarantees** (atomic
  publication, readable mode/owner, partial-write cleanup — §7.4).

Also corrected: the `send-message` durability description (M-2: a **thin proxy** with no durable
Cloud write), evidence-based cleanup (M-3), observable rejection (M-4), and the client-side **batch**
deadline (M-5). See §13.

**r6 corrections (r5 independent adversarial review, verdict `NEEDS_REVISION`).** The r5 review
(`docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R5-INDEPENDENT-ADVERSARIAL-REVIEW.md`) found that r5's
**read-evidence rule** was still insufficient and that two of its claims were overstated; r6 corrects
all five findings (N-1 … N-5):
- **N-1 (MEDIUM, blocking):** r5's F6 accepted **any** correlated **non-error** `ObservationEvent`.
  Source (pinned) shows a **failed terminal** read is a **non-error** observation (`is_error` is not
  set for a non-zero `exit_code`), so `cat <missing>` could set `delivered` and permit **premature
  reclaim**. r6 adds the **eight-fact** model (§5.14.0), states that **no existing primitive proves a
  successful content read**, and requires a **new explicit structured read acknowledgment (U-3)**;
  until it exists `delivered` is **unreachable** and the **staging** bytes are retained until
  `expires_at` while the **workspace copy persists** (r7, R6-1 — §5.14.2 step 6, §5.10, §5.15 U-3).
- **N-2 (LOW):** the §5.5 create example returned `"state": "accepted"` (which the prose says is never
  returned); fixed to `"state": "stored"` and all examples re-checked (§5.5).
- **N-3 (LOW):** the `pending-messages` route is **start-only** (drained once at conversation start,
  deleted regardless of success, capped at 10) — **not** a durable accept for a **running**
  conversation; corrected in §5.9.1/§5.14.1/§5.15 U-2/§8.2 S7.
- **N-4 (INFO):** §5.14.2 step 5 named the reader and its success signal, and **rejected** terminal
  `cat` (a non-zero `exit_code` is a failed read even when `is_error == false`).
- **N-5 (INFO):** the header now identifies the document as **r6** and lists the r5 + r6 task ids.

---

## 2. Current capability audit and authoritative sources

### 2.1 Authoritative sources inspected (versions / commit identifiers)

**Precedence rule (r2):** when the **generated docs export** and the **source at the pinned SHA**
disagree, **source wins**. The docs export is treated as a possibly-stale snapshot, never as the
sole authority.

| Source | Identifier | What it establishes |
| --- | --- | --- |
| Cloud V1 OpenAPI | `https://app.all-hands.dev/openapi.json`, `info.version = 1.91.0`, 244 paths, sha256 `f0f4d4e9…` (**current** — re-verified this session). **Historical r8-reported value (NOT INDEPENDENTLY VERIFIED):** `1.87.1`, 242 paths, sha256 `0086b0b0…ff77916` (r10/R9-4; r11/N10-3) | no upload; file routes read-only; `send-message` carries only text/image |
| Agent Server OpenAPI (public docs export) — **possibly stale** | `https://docs.openhands.dev/openapi/agent-sdk.json`, `OpenHands Agent Server 0.1.0`, 40 paths, sha256 `e42da653…5374a4d` | a **legacy** upload shape `POST /api/file/upload/{path}` (path param) that **contradicts source**; `securitySchemes` absent. **Do not treat as authoritative** (§2.3) |
| `OpenHands/software-agent-sdk` @ `9f7d5cb11b1256c1878f5584a657401feca9ad16` (**== current `main`, 2026-11-12**) | `api.py`, `dependencies.py`, `file_router.py`, `runtime_router.py`, `conversation_registry.py`, `server_details_router.py`, `models.py`, `config.py`, `auth_router.py`, `init_router.py` | **authoritative**: auth model, both upload routes, conversation binding, workspace containment, capability flag, response models |
| `OpenHands/software-agent-sdk` @ `9f7d5cb11b1256c1878f5584a657401feca9ad16` — `tests/agent_server/test_runtime_router.py` | test file | **executable evidence** of confinement (422/401) and the capability flag |
| `OpenHands/software-agent-sdk` tags `v1.62.0`, `v1.58.1`, `v1.20.0`, `v1.10.0` | `file_router.py`, `runtime_router.py` | route-form history: `/{path:path}` at `v1.10.0`; query form since `v1.20.0`; scoped runtime router present at `v1.58.1`/`v1.62.0` |
| `OpenHands/sandbox-server` @ `43e91604ccd0a9960c8d5c52faadd60b30f10e63` (**== current `main`, 2026-10-22**) | `app_conversation/app_conversation_router.py`, `app_conversation/live_status_app_conversation_service.py`, `sandbox/remote_sandbox_service.py`, `sandbox/session_auth.py` | how `conversation_url` + `session_api_key` are produced; the server-side runtime-proxy pattern (`_get_agent_server_context`, `_proxy_git_runtime_call`) |
| `OpenHands/enterprise` @ `3fac53df8c2efcb67ff3537d1162e8c8a108f565` (**== current `main`, 2026-11-11**) — **serves the live Cloud V1 API** | `openhands/app_server/app_conversation/app_conversation_router.py`, `frontend/src/api/conversation-service/v1-conversation-service.api.ts` | the **actual** source of the live Cloud V1 routes (a **superset** of the pinned `sandbox-server` router, adding `/files`, `/skills`, `/hooks`, `switch_acp_model`, `switch_profile`, `stream-start`, `start-tasks*`); confirms **no** upload route; the legacy frontend upload client (§5.13) |
| `OpenHands/OpenHands` @ `a8aaf6813753803cae5182d050909705b0eb02d0` (**== current `main`, 2026-11-12**) | `src/api/conversation-file-upload.api.ts`, `src/api/workspace-upload-path.ts`, `src/api/agent-server-client-options.ts`, `src/utils/file-validation.ts` | official GUI attachment upload flow + client-side limits |
| SDK client source (same SDK SHA) | `openhands-sdk/…/workspace/remote/remote_workspace_mixin.py`, `clients/typescript/src/client/runtime-transport.ts`, `clients/typescript/src/workspace/remote-workspace.ts` | how official clients select the scoped route (`api_prefix`, `ConversationScopedHttpClient` + capability gate) |
| `docs.openhands.dev` | `sdk/arch/agent-server.md`, `sdk/guides/agent-server/api-reference/files/upload-file.md`, `openhands/usage/cloud/cloud-api.md`, `llms.txt` | documented auth ("can execute commands…"), upload doc, cloud API overview |

**Method:** public specs and public source only. **No production call, no credential, no secret
access.** All facts below are marked **[F]** (fact, quoted/cited) or **[G]** (gap / not established).
Each pinned SHA was confirmed to still equal `main` at r2 time; files were fetched and hashed
(§11).

### 2.2 Cloud V1 API — **[F] no upload path; read/download proxies only**

- **[F]** `openapi.json` v1.91.0 (**current**, re-verified this session; r8-reported `1.87.1` — **historical, NOT INDEPENDENTLY VERIFIED**, see §11): token `multipart` = **0**,
  `format: binary` = **0**, paths with
  `attach` = **0**. Only request-body content types present: `application/json` and
  `application/x-www-form-urlencoded` (the latter only on `/oauth/*` device/idp routes).
- **[F]** File routes are read-only, and there are **more than two** runtime-facing routes.
  The **current** live Cloud spec (`1.91.0`, re-verified this session; r8-reported `1.87.1` —
  **historical, NOT INDEPENDENTLY VERIFIED**, §11) exposes at least:
  - `GET /api/v1/app-conversations/{id}/file` — read one workspace file;
  - `GET /api/v1/app-conversations/{id}/files` — list workspace files (description: *"Mirrors the
    git-proxy endpoints: browsers can't reach runtime sandboxes directly (no CORS for non-localhost
    origins), so the frontend hits this on the cloud API host and we make the runtime hop
    server-side"*);
  - `GET /api/v1/app-conversations/{id}/download` — download the conversation trajectory zip;
  - `GET /api/v1/app-conversations/{id}/git/changes`, `GET …/{id}/git/diff` — git proxies.
  **All are read/download; none is an upload.** (r1 said "only two runtime calls" — corrected.)
- **[F]** `POST /api/v1/app-conversations/{id}/send-message` body `AppSendMessageRequest.content`
  = `array(anyOf[TextContent, ImageContent])`, `minItems: 1` — **no generic file/attachment block**.
  Its own description: *"intentionally a thin proxy that forwards messages to the agent server"*,
  and it lists *"Agent Server REST API: Call the agent server's REST endpoints directly using the
  `conversation_url` from `GET /api/v1/app-conversations/{id}`"* as an **alternative approach**.
  **[F] (r3, R2-2)** This route therefore **already performs the server-side runtime hop** with the
  sandbox key (`send_message_to_conversation` → `_get_agent_server_context` → the runtime), exactly
  like the read routes — which is why §7.0 reuses that hop for the proposed attachment op.
  **[F] (r4, M-2) Correction — the hop is a *thin proxy*, it is not durable acceptance.** The
  inspected Enterprise handler `send_message_to_conversation` does an `httpx_client.post(...)` to the
  agent-server `POST /api/conversations/{id}/events` and returns `AppSendMessageResponse(success=…,
  sandbox_status=…)` — it performs **no durable write of its own**. So a Cloud `send-message` `2xx`
  proves only that the agent-server **accepted the request** (the agent-server `event_service.send_message`
  appends the event to the conversation event log, §5.14 evidence); it does **not** prove the agent
  **ran**, the model **read** anything, or that any generic **file** was ingested (the message model
  is text/image only). r3's §5.9.1 claim that `consumed_at` is written "in the same durable step" as
  accepting the message is therefore **not backed by the current source** — see §5.9.1 (r4) and §5.15
  (M-2): a durable accept step **on `send-message`** is **new upstream work**.
- **[F] (r5, H-1c) Existing Cloud primitives relevant to the delivery contract — verified.**
  Two routes the r4 proposal did not cite exist **today** and are **durable**:
  - `POST /api/v1/conversations/{id}/pending-messages` — **`queue_pending_message`** →
    `SQLPendingMessageService.add_message` → a `StoredPendingMessage` row + **`db_session.commit()`**
    (durable SQL store); response
    `PendingMessageResponse{id, queued, position}`; 429 above 10. **r6 (N-3) correction:** the queue is
    drained **only at conversation *start*** (`live_status_app_conversation_service.py::
    _process_pending_messages`, called once after the start task reaches `READY`; entries deleted
    regardless of delivery success) ⇒ it is a durable record for a ***starting*** conversation,
    **NOT** an active-conversation accept. For the P0 target (an **already-running** conversation)
    it is **not usable**; a durable active-conversation accept is **new work** (§5.9.1, §5.15 U-2).
  - `GET /api/v1/conversation/{id}/events/search` — **`search_events`** over the **Cloud-side**
    conversation event store (per-conversation path `…/{user}/v1_conversations/{conversation_id.hex}`;
    `kind__eq` filter supports `ActionEvent`/`ObservationEvent`/`AgentErrorEvent`). **A durable,
    conversation-bound, Cloud-reachable event log** — the evidence source for the H-1a read rule.
    **r7 (R6-3); qualified r8 (R7-3): it is a *replica*, not the agent-server log** — `remote_sandbox_service.py`
    `poll_agent_servers` → `refresh_conversation` → `event_service.save_event` (sha256 `d239ec43…`); the poll loop
    runs **only when there is no public URL** (`web_url is None or 'localhost'`), else **webhooks** feed the store.
    The **poll loop** copies events **one at a time** on a `sleep_interval`, so the store is **not** an
    atomic/consistent snapshot and may lag or tear; event-based evidence MUST come from a **quiesced**
    source or an
    agent-server re-verify (§5.15.4, U-10).
  **Neither** route delivers a **general file** to the agent (both accept only `TextContent |
  ImageContent`), and **durable persistence does not establish a successful agent-side read**
  (§5.14.0). They make part of the §5.14 contract **composable**; the rest (attachment op,
  server-to-server materialization, delivery authorization, the **new successful-read signal**, and
  the **durable active-conversation accept**) remains new
  (§5.14.1 classification). **r6 (N-3):** the `pending-messages` route is **start-only**, so for the
  P0 target (an already-running conversation) it is **not** a composable accept; only
  `events/search` is composable there.
- **[F]** Cloud exposes agent-server connection details on `AppConversation`:
  `conversation_url` (`string|null`, "The URL where the conversation may be accessed"),
  `session_api_key` (`string|null`, "The Session Api Key for REST operations."), `sandbox_id`.
- **[F]** The Cloud **already performs the server-side runtime hop** for the read routes above using
  the sandbox's own session key. Source (sandbox-server `@43e91604…`): `app_conversation_router.py`
  `_get_agent_server_context(...)` resolves the conversation → sandbox → `AGENT_SERVER` exposed URL
  → `session_api_key`, and `_proxy_git_runtime_call(...)` / the `/file` route perform
  `httpx_client.get(f'{ctx.agent_server_url}{runtime_path}', headers={'X-Session-API-Key': …})`.
  **There is no upload proxy** — this is the gap §5 fills.
- **[F] (r3, R2-1) Provenance — which repository serves the live Cloud V1 API.** The live Cloud spec
  (`1.91.0`, re-verified this session; r8-reported `1.87.1` — **historical, NOT INDEPENDENTLY
  VERIFIED**, §11) exposes a route set that is **not** present in the pinned
  `OpenHands/sandbox-server`
  source (`@43e91604…`): it includes `GET …/{id}/files`, `/skills`, `/hooks`, `switch_acp_model`,
  `switch_profile`, `stream-start`, `start-tasks*`. That route set **is** present in
  **`OpenHands/enterprise`** (`openhands/app_server/app_conversation/app_conversation_router.py`
  `@3fac53df…`, sha256 `c43ed4f7…`), whose `list_conversation_files` carries the exact live
  description ("List every regular file under a conversation workspace directory … we make the
  runtime hop server-side using the sandbox's session API key"). **Conclusion:** the live Cloud V1
  API is served by **`OpenHands/enterprise`** — a **different repository** whose router is a
  **superset** of the pinned `OpenHands/sandbox-server` router. It is **not** merely a newer build of
  the same repository; it is a separate (newer) repository. **Impact: none on any conclusion** —
  `enterprise` exposes **no** upload/multipart/attachments route either (`UploadFile`/`multipart`
  grep = 0; its `/files` is a read-only `GET`), so the "no Cloud upload path" conclusion holds, and
  the pinned `sandbox-server` source remains the correct reference for the **server-side runtime-hop
  pattern** and for the agent-server route mechanics (which live in `software-agent-sdk`).

### 2.3 Agent Server upload — **two routes: legacy unconfined vs conversation-bound confined**

**Source authority:** `OpenHands/software-agent-sdk@9f7d5cb11b1256c1878f5584a657401feca9ad16`
(== current `main`). The published docs export (`agent-sdk.json` v0.1.0) is **stale and must not be
used as the authority** — see the F2 note below.

**2.3.1 Route shape and registration (source-verified).**

- **[F]** The upload handler is `file_router.py::_upload_file(path, file)`. Its decorator is
  `@file_router.post("/upload")` with **`path` as a QUERY parameter** (`Annotated[str,
  Query(description="Absolute file path")]`), `file` as `UploadFile`. There is **no**
  `upload/{path}` decorator in the source. `file_router = APIRouter(prefix="/file")`.
- **[F]** `_upload_file` itself performs **only** `if not target_path.is_absolute(): raise 400`, then
  `target_path.parent.mkdir(parents=True, exist_ok=True)` before streaming the body to disk.
  **No** size/type/count limit; **no** symlink guard; the path containment (when present) comes from
  the **route-level dependency**, not from this helper (§2.3.2).
- **[F]** `api.py` mounts the **legacy** route under the host-level `api_router`:
  `api_router = APIRouter(prefix="/api", dependencies=[Depends(require_initialized),
  Depends(check_session_api_key)])` … `api_router.include_router(file_router)`. Effective path:
  **`POST /api/file/upload?path=…`** — **host-level, unconfined** (only `is_absolute()`).
- **[F]** `conversation_registry.py::add_execution_routes(router)` calls
  `router.include_router(create_runtime_router())`. `runtime_router.py::create_runtime_router()`
  builds a router with `prefix="/conversations/{runtime_conversation_id}"`,
  `dependencies=[Depends(bind_local_conversation_runtime)]`, and includes `bash_router`,
  `file_router`, `runtime_git_router`, plus the VSCode routes. Effective path:
  **`POST /api/conversations/{runtime_conversation_id}/file/upload?path=…`** — **conversation-bound,
  workspace-confined**.
- **[F]** `bind_local_conversation_runtime(runtime_conversation_id, request)` resolves the
  conversation (404 if absent), reads `workspace_root = Path(event_service.get_conversation()
  .workspace.working_dir).resolve()`, and for each of `("path", "workspace_dir")` **rejects with 422**
  unless `Path(requested_path).is_absolute()` **and**
  `Path(requested_path).resolve().is_relative_to(workspace_root)`. It also binds the trajectory
  conversation id (422 on mismatch). The module docstring states these are *"routing safeguards, not
  a sandbox for arbitrary shell commands."*

**2.3.2 Authorization is the SAME on both routes (the real gap).**

- **[F]** Both routes sit under the **same** host-level `api_router` dependency chain
  (`require_initialized` + `check_session_api_key`); the runtime router adds the *binding* dependency
  on top, not a different credential. `check_session_api_key` only checks
  `X-Session-API-Key ∈ config.session_api_keys` (401 otherwise) — **no scope, no per-endpoint
  authorization**. Keys are **server-wide** (`config.session_api_keys`, from
  `OH_SESSION_API_KEYS_*` / `SESSION_API_KEY`, or delivered by `POST /api/init`).
- **[F]** The same key also reaches `POST /api/bash/execute_bash_command` and every other `/api/*`
  route. Therefore **conversation binding narrows *reach* (which workspace) but not *privilege***
  (what the credential may do). A third party holding it can still execute commands.
- **[F]** No upload-scoped credential exists. The only other scoping mechanism is a **cookie**
  (`oh_workspace_session_key`) honored **only** by the workspace static-file router
  (`check_workspace_session`, `POST /api/auth/workspace-session`), not by the file/command routers.

**2.3.3 Capability flag and client behavior (why the confined route is the real one in use).**

- **[F]** `server_details_router.py` advertises default capability `conversation_runtime_routes_v1`
  in `GET /server_info`. Official clients select the **scoped** route when it is advertised:
  - Python SDK `remote_workspace_mixin.py::api_prefix` → `/api/conversations/{runtime_conversation_id}`
    when `runtime_conversation_id` is set; `fileUpload` posts to `{api_prefix}/file/upload`
    (`params={"path": …}`, `files={"file": …}`, header `X-Session-API-Key`).
  - TypeScript SDK `clients/typescript/src/client/runtime-transport.ts::ConversationScopedHttpClient`
    rewrites `/api/…` → `/api/conversations/{conversationId}/…` **iff** `capabilities` includes
    `conversation_runtime_routes_v1`; otherwise it falls back to `?cid=…`.
- **[F]** **Executable evidence** (`tests/agent_server/test_runtime_router.py`): own-conversation file
  download OK; **other-conversation** download → **422**; **relative** path → **422**; wrong
  `X-Session-API-Key` → **401**; legacy `/api/file/download` with an absolute path → **200** (proving
  the legacy route is unconfined); `conversation_runtime_routes_v1` present in `/server_info`
  capabilities; scoped upload onto a directory / under a file → **400**.

**2.3.4 F2 — the docs export is stale and contradicts source (corrected evidence).**

- **[F]** The docs export declares `POST /api/file/upload/{path}` with `path` **in the path**. That
  shape matches an **old** release (`v1.10.0`: `@file_router.post("/upload/{path:path}")`) and was
  replaced by the **query** form by `v1.20.0`; at `v1.58.1`, `v1.62.0` and `main` the decorator is
  `@file_router.post("/upload")`. So the export matches only the old `v1.10.0`-era shape — **not**
  `main` and not the recently cited tags.
- **[F]** The export is also **incomplete** vs source: it lacks the conversation-scoped runtime
  routes, `POST /api/auth/workspace-session`, `/api/conversations/{conversation_id}/hooks`, and the
  `capabilities` field on `ServerInfo`.
- **Consequence:** the export's `securitySchemes = {}` and its "only upload" framing remain true as
  *observations about the export*, but the export must **not** be used to describe the current route
  set or route shape. Source at the pinned SHA governs (§2.1 precedence rule).

**2.3.5 What each route does and does not provide.**

| Property | Legacy `POST /api/file/upload` | Conversation-bound `POST /api/conversations/{runtime_conversation_id}/file/upload` |
| --- | --- | --- |
| Workspace containment | **No** (only `is_absolute()`) | **Yes** — `resolve().is_relative_to(workspace_root)` else **422** |
| Conversation binding | **No** | **Yes** — `runtime_conversation_id` resolved; 404 if absent |
| Credential | server-wide `X-Session-API-Key` | **same** server-wide `X-Session-API-Key` |
| Command-exec reach with same key | **Yes** | **Yes** |
| Size / total / count limit | **None** | **None** |
| Symlink hardening (`O_NOFOLLOW`, TOCTOU) | **None** | **None** (resolve() at check time only) |
| Server-resolved destination | **No** (client sends absolute `path`) | **No** (client sends absolute `path`, must be inside workspace) |
| Operation id / status / idempotency | **No** | **No** |
| Reachable by third party without the key | n/a (needs the key) | n/a (needs the same key) |

- **[F]** Documented consequence (`sdk/arch/agent-server.md`): *"Do not expose an unauthenticated
  Agent Server on a public network. It can execute commands and read or write files in its
  configured workspace."* Clients *"must send the session key in the `X-Session-API-Key` header."*

### 2.4 `conversation_url` origin — **[F] infrastructure-dependent, no stable allowlist**

- **[F]** `live_status_app_conversation_service.py::_build_conversation`: `conversation_url` =
  the sandbox `exposed_urls` entry with `name == AGENT_SERVER`, then `+ "/api/conversations/{id.hex}"`;
  `session_api_key = sandbox.session_api_key`.
- **[F]** `remote_sandbox_service.py::_to_sandbox_info`: the `AGENT_SERVER` exposed URL is
  `runtime['url']` (from the runtime API); sibling services are built by `_build_service_url`, which
  supports **path mode** (`{scheme}://{netloc}/{runtime_id}/{service}`) **and** **subdomain mode**
  (`{scheme}://{service}-{netloc}{path}`). **[G]** The concrete host pattern is therefore
  deployment-dependent and **not documented** ⇒ no stable trusted-origin allowlist can be derived.

### 2.5 Existing official attachment upload — **[F] the GUI already does it, with the broad key**

- **[F]** `OpenHands/OpenHands` (GUI) ships file/image attachment upload:
  `src/api/conversation-file-upload.api.ts` → `RemoteWorkspace(...).fileUpload(file, uploadPath)`;
  `src/hooks/chat/use-chat-attachment-upload.ts`; `src/utils/send-message-with-attachments.ts`;
  plus component/tests (`uploaded-file(s).tsx`, `pending-task-attachment-delivery.tsx`, e2e
  `mock-llm-image-upload.spec.ts`).
- **[F]** The SDK's `RemoteWorkspace.fileUpload` (`remote_workspace_mixin.py`) issues
  `POST {host}{api_prefix}/file/upload` with `params={"path": …}`, `files={"file": …}`, and header
  `X-Session-API-Key: <api_key>`. `api_prefix` is `/api/conversations/{runtime_conversation_id}`
  when a runtime conversation id is set (the **confined** route, §2.3), else `/api` (legacy).
- **[F]** The GUI sets a `conversationId` on the agent-server client
  (`getAgentServerClientOptions({conversationId, …})`, which also derives it from
  `conversation_url` via regex `\/api\/conversations\/([^/?#]+)`), so the TypeScript runtime client
  selects the **scoped** route (`ConversationScopedHttpClient`, gated on the
  `conversation_runtime_routes_v1` capability). ⇒ In practice the GUI uploads through the
  **conversation-bound, workspace-confined** route, **not** the legacy one.
  **[F] (r3, R2-4) Qualification:** this is **not universal** across official clients. The
  `OpenHands/enterprise` frontend's V1 client
  (`frontend/src/api/conversation-service/v1-conversation-service.api.ts::uploadFile`) still posts to
  the **legacy** `/api/file/upload?path=…` (multipart) against a runtime base URL. See §5.13 for the
  compatibility note; the proposed P0 contract does not depend on that client.
- **[F]** For **cloud** conversations the GUI resolves `conversation_url` + `session_api_key` from
  `GET /api/v1/app-conversations?ids=…` and calls the agent server **directly** with the key
  (`resolveConversationRuntime` → `requireCloudRuntime` → `uploadFilesToRuntime`).
- **[F]** The destination path is computed client-side: the absolute `working_dir` (or the agent
  server home joined with the relative `working_dir`) is used, and the file name is sanitized by
  `getSafeUploadFileName` (basename only, rejects `.`/`..`); `buildWorkspaceUploadPath` anchors the
  result. The server still receives an **absolute `path`** and does not resolve the destination itself.
- **[F]** Attachments are referenced in the prompt by **path text** ("Uploaded files" block), not by
  a server-resolved file id; images are additionally embedded as base64 `ImageContent`.
- **[F]** Client-side limits only: `validateFiles` caps **3 MB per file and 3 MB total**
  (`src/utils/file-validation.ts`); the server enforces **none** on either upload route.
- **Implication:** the official product path is functionally complete and **does** use the confined,
  conversation-bound route — but **authorization-wise it is broad**: it hands the full, server-wide
  agent-server key to the calling client (the same key that permits command execution). It is **not**
  a least-privilege capability, and it is not exposed as a first-class Cloud endpoint (the client
  must reach the runtime origin directly, which re-introduces the origin-trust problem for a third
  party).

---

## 3. Existing API limitations (mapped to the required properties)

Status vocabulary: **NO** = absent; **PARTIAL** = some capability exists but is insufficient;
**YES** = satisfied.

| Required property | Status today | What already exists | What is still missing | Evidence |
| --- | --- | --- | --- | --- |
| **A. Narrow authorization** — dedicated upload capability, bound to user/app + one conversation, no command exec, no unrestricted R/W, revocable | **NO [F]** | Conversation **binding** exists on the scoped route (which conversation) | A **scoped credential** distinct from the server-wide key; per-endpoint authorization | one server-wide key guards both upload routes **and** `execute_bash_command` (§2.3.2) |
| **B. Trusted destination** — canonical id, no client host/URL, server-side resolution + authz | **PARTIAL [F]** | Server-side **workspace containment** on the scoped route (`resolve().is_relative_to(workspace_root)` → 422); conversation id is in the route path | **Server-side destination resolution** (the client still supplies the absolute `path`); a first-class Cloud route so the client never needs the runtime origin | §2.3.1, §2.3.5, §2.4 |
| **C. Safe upload handling** — size/count/type limits, safe names, traversal & symlink prevention, workspace-root containment, no client paths | **PARTIAL [F]** | Traversal / workspace-root **containment** on the scoped route (422); directory/parent-type guards (400) | **Size / total / count / type limits** (server enforces none); **symlink/TOCTOU hardening**; **no client-supplied path** | §2.3.1, §2.3.5; `validateFiles` client-only 3 MB (§2.5) |
| **D. Reliable outcome + reconciliation** — explicit outcomes, stable operation id, query/reconcile, idempotency | **NO [F]** | — | Operation id, status endpoint, idempotency; response is `{success, file_size}` only | §2.3.1 |
| **E. Operational constraints** — auth lifecycle, versioning, rate limits, quotas, audit, retention, error contract, deleted-conversation behavior | **PARTIAL [F]** | Key is revocable by env rotation; REST API has a formal breakage/deprecation policy (§11) | Upload-specific quotas/audit/status semantics; documented deleted-conversation behavior | §11 |

**Conclusion (corrected in r2).** The gap is **not** "conversation binding" or "workspace
containment" — those already exist on the conversation-bound route and should be **reused, not
rebuilt**. The genuinely missing pieces are **five** (r4 added the fifth), and all are upstream changes:

1. **Narrow authorization** — a scoped credential (bound to one conversation + one principal) that
   is **not** the server-wide command-capable key.
2. **Server-side destination resolution** — the caller supplies a conversation id, not an absolute
   path; the server chooses the destination inside the workspace.
3. **Upload validation limits + symlink hardening** — size/total/count/type enforcement and
   `O_NOFOLLOW`/TOCTOU-safe writes, beyond the existing containment check.
4. **Outcome reconciliation** — durable operation id + status endpoint + idempotency.
5. **Agent-readable delivery (r4, H-1; corrected r5, H-1a/H-1c; corrected r6, N-1)** — the uploaded
   bytes must be **materialized** in the conversation workspace and referenced to the agent by a
   concrete path, with **successful-content-read** evidence (F6b) for `delivered`; the delivery is
   **partly composable** from existing durable Cloud primitives (`events/search`; the **start-only**
   `pending-messages` record) and **partly new** (the attachment op, server-to-server
   materialization, delivery authorization, a **durable active-conversation accept**, and the
   **new successful-read signal** U-3) (§5.14).

The recommended design (§5) is therefore a **Cloud-mediated wrapper** over the existing confined
route, adding those pieces — **not** a new upload endpoint or new confinement machinery (§7.0).

---

## 4. Alternative comparison

Legend: **AS** = authorization scope · **SSRF** = SSRF exposure · **FS** = filesystem isolation ·
**CB** = conversation binding · **AMB** = ambiguous-outcome handling · **CX** = implementation
complexity · **COMPAT** = compatibility implications · **UP** = upstream changes required.

| # | Approach | AS | SSRF | FS | CB | AMB | CX | COMPAT | UP |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **1** | **Cloud-hosted scoped upload op + status endpoint** (recommended) | narrow: bot's existing Cloud bearer + per-op scope to one conversation | none (single fixed Cloud origin) | **reuse** existing workspace containment; **add** server-side path generation + limits | server resolves `conversation_id` (reuse existing resolution) | **strong**: op id + status endpoint | medium (new Cloud routes + service; reuse the runtime hop) | additive (new routes) | **yes** (authorization, limits, op state) |
| **2** | **Conversation-bound upload capability token** on the Agent Server | narrow: token minted by Cloud, valid for one conversation + upload only | low (token still needs a trusted origin) | containment already exists on the scoped route; still add limits + destination resolution | token binds conversation (binding already exists) | weak (no op id/status) | medium | additive | **yes** |
| **3** | **Server-issued upload operation with separate status/reconciliation endpoint** on the Agent Server | medium: needs an upload-scoped credential | **origin problem remains** (bot reaches runtime origin) | containment exists; add limits + destination resolution | server resolves destination from an op | **strong** | high | additive | **yes** |
| **4** | **Existing official mechanism** (GUI agent-server upload with `session_api_key`) | **rejected** — full-privilege key | **rejected** — client trusts runtime origin | **confined** (scoped route) but **no limits** | client-supplied path | none | low (already exists) | n/a | **no** (exists) |
| **5** | **Image `data:` URL via Cloud `send-message` `ImageContent`** | narrow: existing Cloud bearer | none | n/a (no filesystem) | yes (same conversation) | weak (proxy) | low | additive | **no** (route exists; **reachable via the Cloud bearer** — r3, R2-2; **persistence UNVERIFIED**) — but **images only**, not general files. **[r4]:** the message model is `TextContent \| ImageContent` only; there is **no** generic file/attachment content block and **no** agent-side file **ingestion** — an image is passed as a base64 `data:` URL to the model, not materialized as a readable workspace file. So this is **not** a delivery mechanism for general files (H-1). |

**Rejected outright (per task):** any approach that requires OpenHandBot to hold an unrestricted
Agent Server credential (**#4**) or that would grant arbitrary command execution. Approach **#5**
is noted as a possible **future, narrower** feature (images only) and is **not** a P0 solution.

**Why #1 over #2/#3:** #1 removes the bot's need to know or trust the runtime origin at all (the
Cloud resolves and calls the runtime server-side, exactly as it already does for `GET …/git/changes`,
`GET …/file` and `GET …/files`), gives server-resolved conversation binding, and provides a
first-class operation id + status endpoint for reconciliation. #2/#3 keep the origin problem and
still require the bot to reach a second external host. Note that **#1/#2/#3 all reuse the existing
conversation-binding and workspace-containment machinery** (§7.0); none of them rebuilds it.

---

## 5. Recommended upstream API contract

> **Design only. Not implemented. Not an existing supported capability.** All examples use
> placeholders (`{CLOUD_BASE}`, `{CONVERSATION_ID}`, `{OPERATION_ID}`, `{FILE}`); **no real
> credentials, session keys, or production URLs are included.**

### 5.1 Why the current broad key cannot satisfy this

The feature needs **one file write into one conversation's workspace**. A **confined,
conversation-bound** upload route already exists (`POST /api/conversations/{runtime_conversation_id}/file/upload`,
§2.3), so containment and conversation binding are **not** the problem. The problem is the
**credential**: the only credential that can perform the write is the server-wide
`X-Session-API-Key`, which also reaches `POST /api/bash/execute_bash_command`, secret routes, and
unrestricted workspace R/W. Granting it to the bot converts a "write a file" feature into "run any
command in the owner's sandbox". Additionally, no **server-side destination resolution**, no
**size/type/count limits**, and no **outcome reconciliation** exist on any route. Therefore the
capability **cannot** be achieved safely with the current broad key — it requires the scoped,
server-resolved operation specified below, layered on the **existing** confined route.

### 5.2 Endpoint purpose and HTTP methods

| Method | Path (Cloud V1) | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/app-conversations/{conversation_id}/attachments` | Create an upload operation and (multipart) supply the file(s) |
| `GET` | `/api/v1/app-conversations/{conversation_id}/attachments/{operation_id}` | Query the operation's status (reconciliation) |
| `GET` | `/api/v1/app-conversations/{conversation_id}/attachments` | List operations for a conversation (bounded, paginated) |

Design intent: **server resolves the destination**; the client never supplies a host, URL, or
absolute path.

### 5.3 Authentication and authorization

- **Auth:** the caller's existing **Cloud** bearer credential (`Authorization: Bearer …`) — the
  same credential OpenHandBot already holds. **No agent-server key, ever.**
- **Authorization:** the Cloud verifies the caller may act on `{conversation_id}` (same ownership
  check already used for `GET …/file` and `send-message`). The operation is bound to **exactly one**
  conversation and one owning principal.
- **Least privilege:** the operation grants **no** command execution, **no** secret access, and
  **no** workspace read; it may only deposit validated bytes under a server-generated path in the
  conversation's workspace.
- **Credential lifecycle:** the Cloud bearer's existing expiry/rotation applies; the operation itself
  is short-lived (see §5.9) and does not create a durable credential.

### 5.4 Request schema — create operation

```http
POST {CLOUD_BASE}/api/v1/app-conversations/{CONVERSATION_ID}/attachments
Authorization: Bearer <CALLER_CLOUD_TOKEN>
Idempotency-Key: <client-generated-uuid>            # optional; see §5.6
Content-Type: multipart/form-data; boundary=...
```

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `file` | binary (multipart) | yes | one file per part; repeatable up to `max_files` |
| `client_filename` | string | no | display only; **never** used as a path component |
| `declared_content_type` | string | no | advisory; server sniffs independently |
| `purpose` | enum(`prompt_attachment`) | no | defaults to `prompt_attachment` |
| `client_operation_id` | string (uuid) | **required** (r5, M-4b) | client-supplied correlation id; **required** so that *every* operation has an unambiguous correlation key; echoed in **every** response including pre-operation rejections; see §5.16 |

### 5.5 Response schema — create operation

```json
{
  "operation_id": "{OPERATION_ID}",
  "conversation_id": "{CONVERSATION_ID}",
  "state": "stored",
  "files": [
    { "file_id": "f_...", "client_filename": "report.pdf",
      "size_bytes": 123456, "sha256": "…", "content_type": "application/pdf" }
  ],
  "created_at": "2026-11-12T00:00:00Z",
  "expires_at": "2026-11-12T00:15:00Z",
  "status_url": "/api/v1/app-conversations/{CONVERSATION_ID}/attachments/{OPERATION_ID}"
}
```

`state` ∈ `accepted | stored | delivered | rejected | failed | expired` (terminal: `delivered`,
`rejected`, `failed`, `expired`; `accepted` and `stored` are non-terminal). **r3 (R2-9):** the
`uploading` state declared in r2 has been **removed** — see §5.9. **r4 (M-4):** the create response is now
**consistent with the state model** — the server **durably creates the operation row** (and returns
its `operation_id`) **before** it stages bytes. **r5 (S-1): staging is synchronous within the create
request**, so a successful create response reports **`stored`** (staging already complete) — it
**never** reports `accepted` (that state exists only transiently *inside* the request, between row
creation and staging completion, and is never returned) and never reports
`rejected`/`failed`/`expired`/`delivered`, which are **status-only** terminal states reached after
the create call returns. A create that cannot complete staging returns a **definite** non-2xx
(`rejected`/`failed`/`expired` via the error contract, §5.8) — it does **not** return a 2xx with
in-flight staging (there is no asynchronous staging in the r5 model; see §5.9, Q13). A
**pre-operation rejection** — validation that fails **before** any operation row exists (e.g.
malformed multipart, missing `file`, missing `client_operation_id`, over-limit size rejected on the
first read, unsupported type) — returns a **structured error with no `operation_id`**, and the
caller correlates it via its own client-supplied **`client_operation_id`** (§5.16, now **required**).
**`expires_at` here is the
operation's *server retention bound*** (when the server may reclaim staged bytes that were never
delivered), **not** the batch deadline; the authoritative **batch deadline** is the client-side
`T0 + 15 min` (§8.4, M-5). `created_at`/`expires_at` are UTC ISO-8601 with a `Z` suffix;
`expires_at = created_at + 15 min` (fixed at accept, never extended; see §5.9/§5.10).

**r6 (N-2):** the example above now shows `"state": "stored"` — matching this rule. (The r5 example
wrongly showed `"state": "accepted"`, contradicting the very prose that says `accepted` is
internal-only and never returned.) Every JSON example in this document was re-checked against the
authoritative state machine (§5.9); **no** example returns `accepted` or `uploading`.

### 5.6 Upload operation identifier and idempotency semantics

- **Operation id:** server-issued, stable, opaque (`{OPERATION_ID}`). It is the reconciliation key.
- **Client correlation id (r4, M-4; r5, M-4b — now REQUIRED):** the caller **MUST** send
  `client_operation_id` (a client-generated UUID). The server echoes it in **all** responses —
  including **pre-operation rejections** that have no server `operation_id` — so every submitted
  operation has an unambiguous correlation key (§5.16). **Uniqueness scope:** `(principal,
  conversation_id, client_operation_id)` is **unique per principal+conversation**; the server
  rejects a create whose `client_operation_id` was already used for a **different** payload
  (`409 client_operation_id_conflict`), and treats a **repeat with the same payload** as the same
  operation (idempotent, §5.16).
- **Idempotency:** if `Idempotency-Key` is supplied, a repeat create with the **same** key (same
  principal, same conversation) returns the **existing** operation instead of creating a second one.
  Without it, the server still deduplicates **byte-identical** files (same `sha256`) within a
  bounded window and returns the prior `file_id`.
- **No blind retry:** a client that loses the response must **query** the status endpoint, never
  re-`POST` the bytes unless the operation is confirmed `failed`/absent.

### 5.7 File validation, maximum size and count

> **⚠️ PROVISIONAL — NOT APPROVED REQUIREMENTS.** The numeric limits below are **proposals only**,
> aligned with the GUI's existing client cap (§2.5). They are **not** authoritative product
> requirements and must be confirmed by maintainers (§12). Do not treat them as approved.

| Rule | **Provisional** value | Notes |
| --- | --- | --- |
| Max size per file | **3 MiB** | aligns with the GUI client cap (3 MB) — see consistency note below |
| Max total per operation | **3 MiB** | with a per-file cap of 3 MiB, this means **at most one full-size file**, or several small ones |
| Max files per operation | **10** | only meaningful for files well below the per-file cap |
| Allowed content | any, **except** executable/script types rejected by policy (configurable) | policy list itself is provisional |
| Validation | server-side magic-byte sniff + declared-type cross-check; reject on mismatch | required |
| Storage name | server-generated: `{conversation_workspace}/.oh-attachments/{operation_id}/{file_id}` — **never** the client filename | **r4 (H-1):** the *staging* location is opaque to the client, but the **delivered** copy the agent reads is materialized at a known path (an **absolute** `delivered_path` handed to the agent, r7/R6-4 — §5.14, §5.15.5); the opaque `stored_path_ref` is an internal handle, not the agent's access path |

**Internal-consistency check (r2).** The three limits are *not* independent:
`max_total (3 MiB) == max_per_file (3 MiB)` ⇒ the **effective** file count is **1** at full size, so
`max_files = 10` can only be reached by files whose *combined* size ≤ 3 MiB. If multiple full-size
files are desired, **either** `max_total` must rise (e.g. `max_files × max_per_file`) **or**
`max_per_file` must fall. This is flagged for maintainers rather than silently resolved (§12, Q3).

**Staging-visibility note (r3, R2-7).** Staged files live under
`{conversation_workspace}/.oh-attachments/{operation_id}/…` — i.e. **inside** the conversation
workspace. Consequences to accept or mitigate:
- The staged bytes are **visible to the agent** (and to the read-only `GET …/files` listing) during
  the staging window (bounded by `expires_at`).
- In a git-backed workspace they appear as **untracked** files until reclaimed.
- The retention sweep (§5.10) **must** remove them on `expired`/`rejected`/`failed` and once the
  **delivered** copy exists (r4, M-3), so the window is bounded. A hidden/ignored directory name does
  **not** itself provide confidentiality; the mitigations are the short TTL and the sweep, not the
  path name.
- **r4 (H-1) note:** the **delivered** copy (§5.14) is intentionally a **normal, agent-visible
  workspace file** (that is the point of delivery); only the **staging** copy is meant to be
  short-lived.
This is a **visibility** note, not a new security control; it does not change the confinement
requirement (§7.4).

### 5.8 Error codes

| HTTP | Code | Meaning |
| --- | --- | --- |
| 400 | `invalid_destination` | conversation id malformed / not a conversation |
| 401 | `unauthenticated` | missing/invalid caller credential |
| 403 | `forbidden` | caller may not act on this conversation |
| 404 | `conversation_not_found` | conversation does not exist |
| 409 | `conversation_ended` | conversation archived/deleted (see §5.10) |
| 409 | `client_operation_id_conflict` | `client_operation_id` reused with a **different** payload (r5, M-4b; §5.16) |
| 413 | `file_too_large` | per-file or total size exceeded |
| 415 | `unsupported_content_type` | policy-rejected content |
| 422 | `validation_error` | malformed multipart / missing `file` |
| 429 | `rate_limited` | quota/rate exceeded (see §5.9) |
| 500 | `internal_error` | server fault; **outcome unknown ⇒ reconcile** |
| 503 | `sandbox_unavailable` | target workspace not RUNNING; **transient** |

**r4 (M-4); r5 (M-4b) correlation in errors.** Every error body echoes `client_operation_id`
(**required**, §5.16). A **validation-class** error (`400`/`413`/`415`/`422`) is a **definite**
rejection (never "unknown"); only `500`/timeouts are ambiguous. A rejection that occurs **after** the
operation row exists is instead reported as a terminal **`rejected`** state queryable by
`operation_id`; a rejection **before** the row exists is the structured error above (no
`operation_id`).

### 5.9 Status / reconciliation endpoint

```json
{
  "operation_id": "{OPERATION_ID}",
  "client_operation_id": "…",
  "conversation_id": "{CONVERSATION_ID}",
  "state": "stored",
  "files": [
    { "file_id": "f_...", "size_bytes": 123456, "sha256": "…",
      "stored_path_ref": "opaque://{OPERATION_ID}/f_...",
      "delivered_path": null }
  ],
  "failure_reason": null,
  "created_at": "2026-11-12T00:00:00Z",
  "expires_at": "2026-11-12T00:15:00Z",
  "updated_at": "2026-11-12T00:00:02Z",
  "consumed_at": null,
  "delivered_at": null
}
```

**`expires_at` (r3, R2-8; refined r4, M-5; clarified r5).** `expires_at` is present in the status
schema and
means **UTC ISO-8601, `Z`-suffixed**, equal to `created_at + 15 min`, **set at accept and never
moved** (adding files does not extend it). A **separate** `updated_at` records the last state change.
After `expires_at`, the server MUST NOT report any **non-terminal** state: the status read
**derives `expired` from `expires_at`** for any non-terminal row whose `expires_at` has passed, and
the sweep finalizes it. **r5 (S-1):** the status read **never reports `accepted`** — that state is
internal to the create request and is not observable; a poll either returns `stored` (or later) or a
terminal state. **r4 (M-5) clarification — this is the *operation's server retention bound*,
not the product's batch deadline.** The product deadline (15 minutes from the **first** file of a
pending **batch**) is a **client-side** rule (§8.4); the **server has no batch concept** and cannot
enforce it. A multi-file batch may therefore map to **several** operations, each with its own
`expires_at`; the *batch* deadline is authoritative on the client and is **never** extended by a new
operation's `expires_at` (§8.4).

**Declared state model (r4 — `uploading` absent; `delivered` added for M-3).** The declared states:

| State | Terminal? | Meaning |
| --- | --- | --- |
| `accepted` | no | The operation row is **durably created**; the server is staging the bytes **within the same create request** (r5, S-1: this state is **internal to the request** and is **never returned** by create or status — a successful create returns `stored`; a failed create returns a definite non-2xx). |
| `stored` | no | The validated bytes are durably staged at the server-generated path; **delivery to the agent is not yet confirmed**. |
| `delivered` | **yes** | The uploaded content is **materialized in the conversation workspace** AND a **successful *content* read (F6b) is confirmed** by the §5.14 read-evidence rule (r5, H-1a; corrected r6, N-1: **only** via the new **U-3** structured read acknowledgment — **not** via a bare `ActionEvent` or a non-error observation). This is the **only** success terminal state that permits reclaim of the **staging** copy (the **workspace-materialized** copy (C2) persists — §5.10.1, M-3b/r7 R6-1). |
| `rejected` | **yes** | Validation/policy refused the upload (413/415/422-class); nothing usable was staged. |
| `failed` | **yes** | A server-side staging/delivery error after accept; outcome is final and unambiguous. |
| `expired` | **yes** | `expires_at` passed before `delivered`; **only the staged/recovery copy is reclaimed**; **the workspace-materialized copy (if any) PERSISTS** (r7, R6-1; r8, R7-1; precision r9, R8-1 — it is reclaimed only on end-of-use (F7, unmodeled) or **physical workspace removal** via sandbox/pod teardown, which *is* modeled for the managed backends and *delegated to runtime-api* for the Cloud backend; **not** on conversation archive/delete — §5.10.1). |

Transitions: `accepted → (stored | rejected | failed | expired)` and `stored → (delivered | failed |
expired)`. **r5 (S-1):** `accepted` is a **transient in-request** state; because staging is
**synchronous** within the create request, no observable surface ever reports `accepted` (this
removes the r4 contradiction between §5.5 and §5.9). **`uploading` is not declared** (r3, R2-9):
staging completes within the create request, so a long-lived `uploading` status is unreachable; if
staging is ever deferred/async, `uploading`/`delivering` must be re-introduced **together with** its
entering event, owner, and crash-recovery rule (§12, Q13). **`delivered` is reachable only with the
§5.14 read evidence (r6, N-1: the new U-3 signal)** — it is not a decorative state. **r6 (N-1):**
because U-3 does not exist today, `delivered` is **unreachable** in current deployments; the only
reachable **staging** reclaim path is `expires_at` (safe, never an early delete), and the
**workspace-materialized copy is never reclaimed by the operation's timer** (r7, R6-1; scoped r10,
R9-1 — a separate infrastructure timer, the Enterprise sandbox lifecycle §5.10.4, may still remove the
sandbox **and its workspace** in governed environments; that is **not** the operation's `expires_at` and
**not** an F7 end-of-use signal) (§5.10.1).

- `state` is **authoritative and monotonic**; terminal states never change.
- **`stored_path_ref` is opaque and is NOT the agent's access path (r4, H-1).** It is an internal
  handle the Cloud resolves and authorizes (§5.14); the **agent** reads the file via the concrete
  **absolute** `delivered_path` (r7, R6-4 — §5.15.5). Returning an opaque ref to the *client* still
  removes the path-injection surface; the **agent** is given the real path by the delivery contract.
- Reconciliation contract: **timeout / connection drop / 5xx ⇒ poll status** until a terminal state
  or `expires_at`. **Never** infer failure from a timeout. **Never** blind-retry.
- **r4 (L-3) clock authority:** the **server** status is authoritative for the operation's
  `expires_at` and derived state; the client must **not** self-expire on its own clock (clock skew is
  absorbed by trusting the server's `expires_at`/derived state). The client-side **batch** deadline
  (§8.4) is separate and is evaluated against the persisted `T0`.
- **Idempotent retries:** repeating the create with the same `Idempotency-Key` is safe and returns
  the same operation.
- **r4 (I-1) — `send-message` has no idempotency key:** a retried message can duplicate. The bot must
  **not** blind-retry a message; it reconciles via the operation status (§8.3). A message-level
  idempotency key is a possible future upstream addition (§5.15).

#### 5.9.1 The `consumed_at` marker — one coherent definition (r5, resolves M-2/M-2-res)

**One definition (authoritative for the whole document).** `consumed_at` is a **Cloud-side marker on
the *message*, not on the *file*.** It is set **if and only if** the Cloud has a **durable record
that it accepted a user message referencing this operation's `stored_path_ref`** — i.e. the
**message-accept milestone**. It is **not** upload success, **not** event append, **not** delivery,
**not** a successful read, and **not** ingestion.

**What sets it, and what does not (r5, resolving the r4 §7.5/§2.2 contradiction).**
- **Today (verified source):** the `send-message` route is a **thin proxy** — the Enterprise handler
  `send_message_to_conversation` does `httpx_client.post(...)` to the agent-server
  `POST /api/conversations/{id}/events` and returns `AppSendMessageResponse(success, sandbox_status)`
  with **no durable write of its own**. **Therefore `consumed_at` is NOT set by the current
  `send-message` path**, and a `2xx` from it proves only that the **agent-server accepted the
  request** (the agent-server's own `event_service.send_message` appends the event to the
  conversation event log — a real agent-server durable step, §5.14).
- **Durable today, but *start-only* (r5, H-1c; corrected r6, N-3):** the Cloud **already** exposes a
  **durable** queue — `POST /api/v1/conversations/{id}/pending-messages` — which stores the message
  **server-side in SQL** (`StoredPendingMessage`, `db_session.commit()`). **However, against the
  pinned source that queue is drained ONLY during the conversation-*start* handshake:**
  `live_status_app_conversation_service.py::_process_pending_messages` is called **once**, from the
  start path, right after the start task reaches `READY` (it is the **only** caller — not invoked for
  an **already-running** conversation); the entries are **deleted regardless of delivery success**;
  and the queue is **capped at 10** (429 above). **Therefore, for the P0 target — a message to an
  exact *existing, running* conversation (invariant I1, never create a new conversation) — this route
  is NOT a usable durable accept.** It is a durable accept **only for a conversation that is still
  starting**. A durable accept for a **running** conversation is **NEW upstream work** (§5.15 U-2,
  owner choice Q15).
- **NEW work (if the message-accept must ride `send-message`):** a **durable accept step on the
  `send-message` route** would be **new upstream work** (§5.15 U-2) — the r3 claim that `consumed_at`
  is written "in the same durable step" as accepting the message is **not backed by the current
  source** and is **withdrawn**.

**`consumed_at` does NOT authorize deletion (M-3, unchanged).** It is **insufficient to authorize
deletion of file bytes**. Deletion is authorized only by the **`delivered`** terminal state (a
**successful** read, §5.14) or by `expires_at` (§5.10) — **never** by `consumed_at` alone.

**Crash windows around the transition (r5, M-2).**
- **Crash before the durable accept commit:** no durable record ⇒ `consumed_at` stays unset ⇒ the
  operation is treated as **not consumed** ⇒ **no** early delete; the client re-sends/duplicates the
  message via the existing outbox semantics (at-most-once, §8.3).
- **Crash after the durable accept commit, before the response:** the message is durably queued
  (Cloud row committed) but the caller sees a timeout ⇒ the caller **reconciles** (status/`send`-side
  query) and **never blind-retries** (§8.3). `consumed_at` may be set while the client still thinks
  "unknown" — that is safe, because `consumed_at` **never** drives deletion; the **staging** copy
  is retained until `delivered`/`expires_at`, and any **workspace-materialized** copy is retained
  **beyond the life of the conversation** — no conversation-scoped event reclaims it (r7, R6-1;
  corrected r8, R7-1 — §5.10.1).

**Interaction with the deadline, late text, and ambiguous remote outcomes.**
- **Deadline:** `expires_at` is fixed at accept and **independent** of `consumed_at`/`delivered_at`.
- **Late text (after `expires_at`):** the operation is terminal (`expired`); a `stored_path_ref`
  from it is **no longer valid**, so a message carrying it is rejected (stale ref). OpenHandBot
  invariant I7/I8 (files alone never dispatch) already prevents a late-text dispatch of an expired
  batch. **r4 (L-1):** the bot must treat a stale-ref rejection as **expired** and **notify** the
  user; it must **not** retry (§8.3/§8.4).
- **Ambiguous remote outcomes:** a `send-message` timeout is **unknown** for the *message*, not the
  *upload*. The upload `state` stays `stored`; `consumed_at`/`delivered_at` are set only on the
  durable evidence above; an ambiguous send neither sets nor clears them, and the client reconciles
  the message separately (existing outbox semantics, §8.3).

**Telegram handling (updated r4).** OpenHandBot's Telegram acknowledgement and durable-delivery
guarantees (invariant I13) are **unchanged**. Critically, **`consumed_at` does not drive
deletion** (M-3): deletion is evidence-based (`delivered` or `expires_at`), so the bot's local
durable ack (I13) and the server's reclamation are **decoupled** and cannot cause the M-1
batch-loss/duplicate hazard — see the crash-window analysis in §8.3.

### 5.10 Lifecycle, retention, and cleanup — independent per-copy rules (r7; re-derived; supersedes r5/r6)

> **r7 (R6-1) — the 15-minute deadline is NEVER a content-deletion authorization.** This section is
> the single authoritative lifecycle rule; **no other section may contradict it**. It separates the
> **eight** distinct concepts that r4–r6 partially conflated and gives **each physical copy its own
> independent lifecycle**. In particular, **`expires_at` reclaims the *staged/recovery* copy only —
> it NEVER reclaims the workspace-materialized copy.** The r6 rule that a materialized copy could be
> removed at `expires_at` is **withdrawn** (it re-introduced the premature-deletion hazard T-19 the
> document claims to close).

#### 5.10.0 The eight lifecycle concepts — never conflated (r7, R6-1)

These are **eight separate** deadlines/lifetimes/evidences. **No two may be equated**, and **none of
them may be used as proof of another**:

| # | Concept | Scope / owner | What it *is* | What it is **NOT** |
| --- | --- | --- | --- | --- |
| **L1** | **15-minute wait-for-text deadline** | **client-side** (OpenHandBot), from the first file of a pending batch (§8.4) | the window in which accompanying text may still dispatch the batch | **not** an upload outcome; **not** read evidence; **not** end-of-use evidence; **not** a workspace-copy deletion authorization; **not** proof that recovery data is unnecessary |
| **L2** | **Pending-batch cancellation** | **client-side** (OpenHandBot) | the action taken when L1 expires with **no** text: the batch will **not** be dispatched | **not** a server content deletion; it does **not** delete any server-side copy (staging or workspace) |
| **L3** | **Lifetime of the staged/recovery copy** | **server** (Cloud) | the internal staging bytes (`C1`) and any deployment recovery copy (`C3`) | **not** the agent's file; **not** needed once materialization succeeds |
| **L4** | **Lifetime of the workspace-materialized copy** | **server** (Cloud), but the file belongs to the **conversation workspace** | the agent's readable file (`C2`) | **not** governed by L1/L2; **not** reclaimed at `expires_at` |
| **L5** | **Lifetime of reconciliation metadata / operation records** | **server** (Cloud) + **client** (OpenHandBot local batch rows) | the op rows (`C4`) and the local batch state (`C5`) used to reconcile and audit | **not** a content copy; retaining it does not imply retaining bytes |
| **L6** | **Read evidence (F6b)** | **server** (Cloud/Agent-Server), see §5.15.1 | a trustworthy **U-3** acknowledgment that the intended content was **completely read** | **not** end-of-use evidence; a successful read does **not** prove the agent finished using the file |
| **L7** | **End-of-use evidence (F7)** | **not modeled by any current primitive** | evidence that the agent **stopped using** the content | **not** inferred from L6; **not** inferred from L1/L2 |
| **L8** | **Deletion policy** | **server** (Cloud), per copy | the rule that **permits** vs **prohibits** deleting each physical copy (§5.10.1) | **not** a single global timer |

**The 15-minute deadline (L1) MUST NOT be treated as evidence that:** the upload failed; the agent did
not read the file; the agent finished using the file; a workspace copy is safe to delete; or recovery
data is no longer required. **L1 gates *dispatch only*.**

#### 5.10.0.1 Cross-map: the L1–L8 concepts ↔ the F1–F7/F6a/F6b facts (r8, R7-4)

§5.10.0 (concepts **L1–L8**: deadlines/lifetimes/deletion policy) and §5.14.0 (facts **F1–F7/F6a/F6b**:
milestones a run reaches) are **two different vocabularies** and are **not** equivalent: the L-set is
about **time windows and copy lifetimes**, the F-set is about **milestones in the agent's run**. To
prevent drift, the mapping is stated explicitly here. **"none"** means the L-concept has **no**
counterpart fact (and vice versa); it does **not** mean the two are equal.

| L-concept (§5.10.0) | Counterpart fact (§5.14.0) | Relationship (exact) |
| --- | --- | --- |
| **L1** 15-minute wait-for-text deadline | **none** | client-side dispatch window; no F-fact corresponds |
| **L2** pending-batch cancellation | **none** | client-side action; deletes no server copy |
| **L3** lifetime of the staged/recovery copy (C1/C3) | **none** | server copy lifetime; independent of any run milestone |
| **L4** lifetime of the workspace-materialized copy (C2) | **F7** (end-of-use) **+** the physical-removal path (modeled for managed backends; delegated to runtime-api for the Cloud backend) | C2's *permitted* reclaim is gated by **F7** (or physical removal); a **read** (F6b) does **not** end L4 |
| **L5** lifetime of reconciliation metadata / op records (C4/C5) | **none** | metadata lifetime; not a content copy |
| **L6** read evidence | **F6b** (successful content read) | **L6 *is* the evidence for F6b** — the same milestone seen from the deadline side |
| **L7** end-of-use evidence | **F7** (agent finished using the content) | **L7 *is* the evidence for F7** — the same milestone seen from the deadline side |
| **L8** deletion policy (per copy) | **none** | the rule that permits/prohibits deleting each copy (§5.10.1) |
| *(no L-concept)* | **F1, F2, F3, F4, F5, F6a** | run-construction/observation milestones with no lifetime counterpart |

**Rule (unchanged):** no L-concept may be used as proof of an F-fact, or vice-versa, except where the
table above explicitly states they are the **same milestone** (L6 ↔ F6b, L7 ↔ F7). In particular,
**L6 (a read) never proves L7/F7 (end-of-use)**.

#### 5.10.1 Per-copy lifecycle (independent; authoritative)

Each physical copy has its **own** owner, authoritative state, and deletion rule. `expires_at` is the
**operation's server retention bound** (fixed at accept, never extended) and reclaims **only** the
**staging/recovery** copies.

| Copy | Created by | Owner | Authoritative state | Deletion **PERMITTED** by | Deletion **PROHIBITED** by |
| --- | --- | --- | --- | --- | --- |
| **C1 — Staged bytes** `{conversation_workspace}/.oh-attachments/{operation_id}/{file_id}` | the create op, after row creation (§5.16) | Cloud | the operation row (`stored`/terminal) | (a) the operation is **terminal** (`delivered`/`rejected`/`failed`/`expired`) — staging's purpose is served once the workspace copy exists or the op is closed; **or** (b) `expires_at` | while the operation is `accepted`/`stored` **before** `expires_at`; **never** on `consumed_at` alone |
| **C2 — Workspace-materialized copy** `{conversation_workspace}/uploads/{operation_id}/{sanitized_display_name}` | the delivery materialization (§5.14.2 step 4) | the **conversation workspace** (the agent's file) | the workspace file itself (independent of the op row) | **only** (a) a **trustworthy end-of-use (F7) condition** — *not modeled today*; **or** (b) the **workspace directory is physically removed** on **sandbox/pod teardown**. Teardown **is modeled for the *managed* backends** (Docker/E2B/k8s) by the Enterprise **sandbox lifecycle** (`delete_after_seconds`, a *configurable* idle bound — §5.10.4, r9/R8-1; **r10/R9-3:** the verified mechanism is **container removal**; physical deletion of the **underlying** workspace data is **UNVERIFIED** for host-mounted layouts), and is **delegated to runtime-api** for the **Cloud/remote backend** (whose exact trigger/delay is **not** modeled by these repos). **Neither** `expires_at` **nor** conversation archive/delete reclaims C2 (r8, R7-1); **r10/R9-1:** the infrastructure lifecycle timer above is a **separate** clock from the operation's `expires_at` and is **not** an F7 end-of-use signal | **NEVER at `expires_at`**; never on `stored`/`expired`/`failed`/`rejected`; never on `consumed_at`; never on a read (F6b) alone (a read is not end-of-use); **never on conversation archive/delete** (it archives + preserves the workspace — r8, R7-1) |
| **C3 — Recovery copy** (optional, deployment-defined) | deployment | Cloud | deployment policy | with **C1** (same rule) | presented as the agent's file; relied upon after `expires_at` |
| **C4 — Operation rows / audit** (server) | the create op | Cloud | the op row | per the Cloud audit-retention policy (owner decision, §12) — **metadata only, not content** | (not a content copy) |
| **C5 — Local pending-batch rows** (client) | the bot, on first file (§8.2 S1) | OpenHandBot | local SQLite batch state | on the bot's **own** terminal batch state (dispatched/expired/cancelled) | (not a server content copy) |

**Cleanup eligibility (exact).** A content copy is reclaimed **only** when the **deletion-permitted**
column holds **and** the deletion-prohibited column does not. Concretely:
- **C1 (staging)** ⇒ reclaim when the operation is **terminal** (any terminal state) **or** at
  `expires_at`. This is the **only** copy `expires_at` reclaims.
- **C2 (workspace copy)** ⇒ reclaim **only** on a trustworthy **F7 end-of-use** condition (not
  modeled ⇒ **effectively never today**) or on the **physical removal of the workspace directory**
  (sandbox/pod teardown). **Today there is NO conversation-scoped event that reclaims C2**: conversation
  archive/delete **archives** the workspace and **preserves** the directory (§5.10.1, r8/R7-1), so the
  only physical-removal path is **sandbox/pod teardown**. Teardown **is a modeled mechanism** for the
  **managed** backends (the Enterprise **sandbox lifecycle**, §5.10.4, r9/R8-1) with a *configurable*
  idle bound; for the **Cloud/remote** backend the lifecycle is **delegated to runtime-api** and its
  exact trigger/delay is **not modeled by these repos**. A teardown (when it happens) does delay under
  **sandbox grouping** (a sibling keeps the sandbox alive), but the bound is **not** unbounded for the
  managed backends. **`expires_at` does NOT reclaim C2.**
- **C3 (recovery)** ⇒ same as C1.
- **C4/C5** ⇒ metadata; reclaimed per the respective owner's audit/local-retention policy.

**No restoration after reclamation (explicit).** Once a copy is reclaimed it is **not recoverable**;
there is **no** client-facing "restore" operation. **But the validity of a path is governed by the
copy's own lifetime, not by the operation's terminal state** (r7 correction of r6 §5.14.4): a
`delivered_path` for a materialized file **remains valid (readable) as long as C2 exists**, even if
the operation is terminal (`expired`/`failed`); conversely, a `stored_path_ref` becomes **invalid**
as soon as **C1** is reclaimed. The status endpoint reports each path's validity by **copy lifetime**,
not by `state`.

**Unknown / failed delivery or read outcomes (safe default).** If delivery or the successful-read
evidence is unknown or inconclusive, the operation **stays `stored`** (non-terminal) and the
**staging** bytes are retained **until `expires_at`**; **C2, if it was materialized, is retained
regardless** (it is the agent's file). There is **no** early delete of any copy on an
unknown/inconclusive outcome (M-3, H-1a/N-1). **r6 (N-1): this is the *only* reachable behaviour
today**, because U-3 does not exist; `delivered` is therefore never asserted, **but the materialized
file still persists** (r7, R6-1).

- **Partial-write cleanup.** A crash during staging leaves a partial **C1** file; the
  `failed`/`expired` transition MUST remove partial **staging** bytes. A partial **C2** write MUST be
  removed/overwritten atomically (temp-write + `os.replace`), never left as a truncated
  `delivered_path` (§7.4). **The removal of a partial C2 is the *only* case in which C2 is deleted
  without an F7/workspace-removal condition** — it is not a valid file, so it is not the agent's file.
- **What happens if upstream cannot provide the read evidence (M-3, H-1a; corrected r6, N-1;
  re-derived r7, R6-1):** the operation can only reach `stored` (then `expired` at `expires_at`); the
  **staging** copy is reclaimed at `expires_at`, and the **workspace copy (if materialized) persists**.
  The proposal **does not invent** a read-completion event, and **does not** treat `expires_at` as a
  read proof or as an end-of-use proof.
- **Cleanup:** deletion is server-driven and auditable; a client-side delete endpoint is **not**
  required (and is avoided to prevent unauthorized cleanup — §9 threat T-13).
- **Conversation ended/deleted (r8, R7-1 — corrected against the pinned source):** once the
  conversation is archived/deleted, create returns **409 `conversation_ended`** and status returns the
  operation's terminal state; no new files are accepted. A conversation deleted while an operation is
  `stored` is a terminal condition; the operation is finalized `expired`/`failed` (never left
  non-terminal), and any staged-but-undelivered files (**C1/C3**) are reclaimed by the server's
  retention sweep. **However, conversation archive/delete does NOT physically remove the workspace
  directory, so it does NOT reclaim C2.** Verified source behavior: the Cloud delete finalizer
  **archives** the workspace to a bucket (`_finalize_sandbox_delete` → `archive_conversation_workspace`
  → `workspace_archive.archive_workspace`) and tears the **sandbox** down **only when no sibling
  conversation still references it**; the agent-server delete **preserves** the workspace ("Safely
  remove only the conversation directory (**workspace is preserved**)"). Under **sandbox grouping**
  (any non-`NO_GROUPING` strategy) a sibling conversation keeps the sandbox alive, so the workspace
  directory is **not removed at all** while a sibling lives. The path by which the workspace
  directory (and therefore C2) is physically removed is **sandbox/pod teardown**. Teardown **is a
  modeled mechanism** in the pinned source for the **managed** backends (Docker/E2B/k8s): the
  Enterprise **sandbox lifecycle** (`sandbox/lifecycle/{settings,rules,tasks,sweep}.py` + `worker/app.py`,
  `delete_after_seconds` default 10 days) deletes a sandbox **and its workspace** after an idle bound
  (§5.10.4, r9/R8-1); for the **Cloud/remote** backend the lifecycle is **delegated to runtime-api**
  (`lifecycle/__init__.py`: "runtime-api manages the remote backend's sandboxes itself"), so its exact
  trigger/delay is **not modeled by these repos**. **Therefore: `archival ≠ deletion ≠ detachment ≠
  physical removal`; today NO conversation-scoped event reclaims C2** (only a teardown can), and this
  proposal does **not** invent a C2 cleanup primitive. (r8/R7-1; precision r9/R8-1 — see §5.10.4 for
  the limitation and Q18.)

#### 5.10.2 Transitions after accompanying text arrives (r7, R6-1)

Once **valid accompanying text arrives before the deadline (L1)**, the wait-for-text phase is
**complete**; the subsequent delivery lifecycle is **independent** of L1. Explicit rules:

- **A successful `stored` transition MUST NOT arm any operation-scoped timer that deletes the workspace
  copy.** There is **no** "auto-expire timer" tied to the operation's `expires_at` whose firing deletes
  **C2**. The **operation's** `expires_at` clock reclaims **C1/C3 only** (§5.10.1). **r10 (R9-1):** this
  is **not** a claim that **no** server-side timer can ever remove C2 — a **separate** infrastructure
  timer (the Enterprise **sandbox lifecycle**, `delete_after_seconds`; §5.10.4) may remove the sandbox
  **and its workspace** in environments governed by that mechanism. The two clocks are **distinct** and
  **must not be conflated**; neither the operation's `expires_at` nor any other timer is a **conversation
  end-of-use (F7)** signal.
- **A batch that has entered an uncertain remote-delivery or agent-use state MUST retain sufficient
  recovery evidence for reconciliation.** `stored` + the op row (C4) + the reference message are
  retained; the bot must not discard its local batch row (C5) until its own terminal batch state
  (§8.3).
- **`delivered` (when U-3 exists) is an *additional* terminal state, not a deletion trigger for C2.**
  On `delivered`, **only C1** is reclaimed; **C2 persists** (it is the agent's file; the agent may
  still be reading it).
- **`expired` closes the operation, not the file.** On `expired`, C1/C3 are reclaimed; **C2, if
  materialized, persists** **beyond the life of the conversation** (r8, R7-1: conversation
  archive/delete archives + preserves the workspace and does not reclaim C2 — §5.10.1).

#### 5.10.3 Mandatory crash and race analysis (r7, R6-1)

The design MUST never delete a copy needed for **unresolved reconciliation** or **potentially active
agent use**. Each case below states the required behaviour:

| # | Case | Required behaviour |
| --- | --- | --- |
| 1 | **Expiry while the operation is still pending** (`stored`, no text yet) | L1 expires ⇒ the **batch is cancelled** (L2, client-side). Server: `expires_at` finalizes the op `expired` and reclaims **C1/C3 only**; **C2 does not exist yet** (nothing materialized). No content loss. |
| 2 | **Expiry immediately after accompanying text arrives** | The batch deadline is evaluated **atomically** with the dispatch-intent write (§8.4); the outcome is "dispatch" **or** "expired", never both. If dispatch won, the op proceeds; `expires_at` still reclaims **C1/C3 only**, **never C2**. If a materialization raced ahead of expiry, **C2 persists**. |
| 3 | **Expiry while the upload outcome is unknown** | The op stays `stored` (non-terminal) until reconciled; `expires_at` finalizes it `expired` and reclaims **C1/C3 only**. The bot surfaces "expired, outcome unknown" and **never** blind-retries (§8.3). |
| 4 | **Expiry while the agent is reading the workspace copy** | **C2 is not reclaimed at `expires_at`** (§5.10.1), so an in-progress read cannot be invalidated by the **operation's** timer. This is the direct R6-1 fix. **r10 (R9-1):** a **separate** infrastructure timer (the Enterprise sandbox lifecycle, §5.10.4) can still tear down the sandbox **and its workspace** in governed environments — but that is **not** the operation's `expires_at`, **not** a conversation-scoped event, and **not** an end-of-use (F7) signal. |
| 5 | **Crash before and after the delivery state is committed** | The `delivered` transition is committed **after** the materialization is durably published (temp + `os.replace`). Crash **before** commit ⇒ op stays `stored`; on restart the reconciliation re-derives the state from the durable row + the durable file; **C2 exists and is not deleted**. Crash **after** commit ⇒ op is `delivered`; C1 reclaim is idempotent. |
| 6 | **Crash between a database cleanup transition and filesystem deletion** | Ordering: **commit the DB transition first**, then delete the file; a re-run of the sweep is **idempotent** (deleting an already-absent file is a no-op). If the DB says "reclaimed" but the file remains, the next sweep re-attempts (bounded); **C2 is never in this path except for a partial-write cleanup**. |
| 7 | **Filesystem deletion succeeds but the database update fails** | The file is gone but the row still shows the copy present. Reconciliation re-checks the file's existence and **re-derives** the true state; a missing **C1** with a non-terminal op is treated as **recoverable-from-C2-if-present, else `failed`** (never a silent success). **C2 is never deleted by this path.** |
| 8 | **A delayed read acknowledgment (U-3) arrives after expiry** | The op is already terminal (`expired`). A late U-3 **does not resurrect** the op and **does not** cause any deletion; it is recorded as an audit event only. **C2 is unaffected** (already persisting). |
| 9 | **A delayed event arrives after a cleanup attempt** | Late events are **not** authoritative for deletion; the sweep re-reads durable state and treats a late event as audit only. A late event never causes C2 deletion. |
| 10 | **Two cleanup paths race** | All copy deletions are **idempotent** and guarded by a **compare-and-set** on the copy's authoritative state (delete only if still eligible); a loser of the race is a no-op. **No** path deletes C2 without the F7/physical-removal condition (r8, R7-1). **r9 (R8-1):** the physical-removal condition is the **sandbox/pod teardown** — *modeled* for the managed backends (Enterprise sandbox lifecycle) and *delegated to runtime-api* for the Cloud backend (§5.10.4); it is **not** a conversation-scoped event and **not** an F7 signal. |
| 11 | **A new reconciliation attempt begins while cleanup is in progress** | Reconciliation **re-reads** durable state and does **not** assume a copy is gone; it may find a copy still present (cleanup not yet finished) and must **not** delete it again if the condition no longer holds. |

**Invariant (r7; scoped r10, R9-1):** the system **never** deletes a copy that is needed for unresolved
reconciliation or potentially active agent use. `expires_at` is a **staging-only** bound; **no
operation-scoped (`expires_at`) timer ever deletes C2**. This invariant binds the **application**
(OpenHandBot/Cloud); it does **not** claim that **no** infrastructure timer can ever remove the workspace
— a **separate** Enterprise sandbox-lifecycle timer (`delete_after_seconds`; §5.10.4) may tear down the
sandbox and its workspace in governed environments, and the application **cannot** prevent that external
infrastructure deletion. That lifecycle timer is **not** an end-of-use (F7) signal and does **not** prove
that agent consumption has ended (§5.10.4).

#### 5.10.4 Retention bound — owner decision required (r7, R6-1; strengthened r8, R7-1; corrected r9, R8-1)

- **No universal retention duration is invented here.** The source and product requirements do **not**
  establish a safe finite retention period for **C2** (the agent's file).
- **Conservative fallback (chosen):** retain **C2** and do **not** transition it to a
  cleanup-eligible state until a **trustworthy terminal condition** exists — i.e. an **F7 end-of-use**
  signal (not modeled) or the **physical removal of the workspace directory** (r8, R7-1). Today this
  means **C2 persists beyond the life of the conversation**.
- **r9 (R8-1) — the physical-removal path *is modeled in the pinned source* for the managed backends
  (corrects the r8 "unmodeled / outside the pinned repos" wording).** The pinned
  `OpenHands/enterprise@3fac53df…` contains a **complete, wired sandbox-lifecycle subsystem**
  (`sandbox/lifecycle/{__init__,settings,sweep,rules,tasks}.py`; `worker/app.py` adds it as the
  `sandbox_lifecycle` blueprint). Its settings define `delete_after_seconds` (default 10 days) with the
  description **"Delete a sandbox, and its workspace, once it has not run for this long"**; a periodic
  `sweep` job (`tasks.py`, `@lifecycle.periodic(cron='* * * * *')`, line 78) selects candidates from
  the sandbox table alone (`sweep.py::find_due_sandbox_ids`); `rules.decide()` returns
  `Action.DELETE` (`Reason.INACTIVE`) once `delete_after_seconds` has elapsed (using the row's
  `LAST_RAN_AT = greatest(state_changed_at, last_active_at)`); and the `check` job calls
  `sandbox_service.delete_sandbox(sandbox_id)` (`ManagedSandboxService.delete_sandbox` →
  `_delete_at_provider`, which removes the container/pod). The scope is **explicit** in
  `lifecycle/__init__.py`: it "covers every backend that subclasses `ManagedSandboxServiceInjector`:
  **Docker, E2B and k8s agent-sandbox**. **runtime-api manages the remote backend's sandboxes
  itself.**" So:
  - For the **managed** backends, sandbox-and-workspace teardown **is a modeled mechanism with a
    *configurable* idle bound** — the r8 assertion that the removal path is "not modeled by any
    primitive in the pinned source" is **incorrect**.
  - **r10 (R9-3) — what the verified mechanism *proves* (and what it does NOT).** The only mechanism the
    pinned source establishes is **container removal** (`docker_sandbox_service.py`
    `_delete_at_provider` → `container.remove()`; the pod analogue for k8s). The lifecycle setting's
    **description** ("Delete a sandbox, **and its workspace**, …") states the **intent**, but the
    **code path** shown is container removal. Whether that removes the **underlying workspace data**
    depends on where the workspace lives: the pinned Docker spec puts it **inside the container**
    (`docker_sandbox_spec_service.py`: `working_dir='/workspace/project'`, `OH_CONVERSATIONS_PATH=
    '/workspace/conversations'`), while the mount layout is **deployment-configurable**
    (`DockerSandboxServiceInjector.mounts: list[VolumeMount] = Field(default_factory=list)` — **empty by
    default**). For the **container-local** layout, removing the container removes its writable layer
    and therefore the workspace files; for a **host bind-mounted** workspace, `container.remove()`
    would **NOT** delete the underlying host data. The pinned source does **not** establish **physical
    deletion of the underlying workspace data for all configurations** — that is **UNVERIFIED /
    SOURCE REQUIRED**. Explicitly distinguished here: (i) **container removal** (verified), (ii)
    **mounted workspace data** (layout-dependent; **not** deleted by container removal if bind-mounted),
    (iii) **physical deletion of underlying workspace files** (**UNVERIFIED** for host-mounted layouts),
    (iv) **any external storage lifecycle** (deployment/runtime-api owned; **not** modeled by these
    repos). The R8-1 correction stands — the removal path **is** modeled (contra r8) — but it must
    **not** be read as a universal physical-deletion guarantee, and it is **not** an F7 end-of-use signal.
  - For the **Cloud/remote** backend (the path this proposal's Cloud API actually uses —
    `RemoteSandboxService`, which subclasses `SandboxService`, **not** `ManagedSandboxService`), the
    lifecycle is **delegated to runtime-api** and its exact trigger/delay is **not modeled by these
    repos**. This is the **only** part that is genuinely "external/unmodeled" — r8's statement is true
    **only** for this one path.
- **r8 (R7-1), retained and made precise.** r7 said C2 "persists for the life of the conversation" and
  that conversation archive/delete would remove it. The pinned source shows that is **false**:
  conversation archive/delete **archives** the workspace and **preserves** the directory, so it does
  **not** reclaim C2. Under **sandbox grouping** (any non-`NO_GROUPING` strategy) a sibling conversation
  keeps the sandbox alive, so teardown is **delayed** while a sibling lives — but for the **managed**
  backends the delay is **bounded** by `delete_after_seconds` once **all** conversations in the sandbox
  are idle (r9/R8-1; the r8 "indefinitely delayed" wording over-states this). So **today no
  conversation-scoped event reclaims C2** (only a sandbox/pod teardown can), and C2 can outlive the
  conversation. This is disclosed, not hidden.
- **Applicability limit (r9, R8-1 — explicit).** The Enterprise sandbox lifecycle governs the
  **managed** backends, **not** the Cloud remote backend; and a *configured* rule does **not** prove
  that any **particular** conversation has reached a safe terminal state, nor that the agent has
  finished using the file. It is a **sandbox-scoped idle bound**, **not** an F7 end-of-use signal, and
  it must **not** be treated as evidence that agent access has ended.
- **Storage-growth implications (explicit):** because C2 is not reclaimed by the **operation's** timer
  (`expires_at`; §5.10.1) **and** not
  reclaimed by conversation end, a conversation that accumulates materialized attachments grows for as
  long as the sandbox/workspace survives (bounded only by the sandbox-lifecycle teardown for the
  managed backends, and by the external runtime-api lifecycle for the Cloud backend). This is **not** a
  complete operational policy and **must not be presented as one**; it is a **safe** default that
  shifts the bound to a product decision.
- **Owner decision required (new, §12 Q18):** define a bounded retention policy for **C2** that is
  compatible with F7 semantics — e.g. a per-conversation storage cap, an explicit
  end-of-conversation cleanup, or an F7 signal — and confirm the **Cloud/runtime-api** teardown bound
  and its interaction with grouping. **Until the owner decides, the conservative fallback
  holds** and the growth implication is disclosed.
- **Status (r9):** this is **NOT fully resolved** — the residual, explicitly disclosed limitation is
  **unbounded-per-conversation workspace storage** (C2 is not reclaimed by any conversation-scoped
  event; only a sandbox/pod teardown reclaims it) (§12 Q18). It is a **deliberate safe default**, not
  an oversight; it is reported here so no reviewer mistakes it for a closed item. **No cleanup
  primitive is invented to close it.**

#### 5.10.5 The 15-minute wait-for-text deadline and batch cancellation (client-side; unchanged semantics)

The **product batch deadline** is **15 minutes from the first file of a pending batch** and is
**client-side** (§8.4); the server has **no batch concept**. **L2 (pending-batch cancellation)** is
the client action on expiry without text: the batch will not dispatch. **L1/L2 never delete server
content** — they gate *dispatch* only (§5.10.0). The server's per-operation `expires_at` remains a
**staging-only** retention bound (§5.10.1).

- **Retention window (staging):** the staged bytes (C1) live until the operation is terminal or
  `expires_at` (fixed at accept, never extended).
- **r4 (L-2), retained:** a crash during staging leaves a partial **staging** file; the
  `failed`/`expired` transition MUST remove partial staging bytes (bounded by `expires_at`).
  **r5 (S-3):** the same rule applies to a partial **delivered** write — it MUST be removed/overwritten
  atomically (temp-write + rename), never left as a truncated `delivered_path` (§7.4).

### 5.11 Audit events

Each operation emits structured audit events: `attachment.row_created`, `attachment.stored`,
`attachment.resolved` (ref resolved + authorized, §5.14), `attachment.materialized`,
`attachment.read_confirmed` (the **U-3 successful *content*-read** acknowledgment of §5.14.2 step 6
was observed; r6, N-1; r7, R6-2 — recorded **only** for a trusted-issuer acknowledgment),
`attachment.delivered` (== read_confirmed + terminal), `attachment.rejected` (with reason),
`attachment.failed`, `attachment.expired`, `attachment.consumed` (the **message-accept** marker,
§5.9.1), `attachment.workspace_copy_retained` (r7, R6-1: the materialized C2 copy was **not** reclaimed
at `expires_at`). Events carry `operation_id`, `conversation_id`, principal, sizes, and hashes —
**never** file
contents or credentials. **r5:** the r4 event name `attachment.accepted` is renamed
`attachment.row_created` so it cannot be confused with the (never-returned) `accepted` **state**; an
`attachment.action_attempted` event MAY be emitted for observability but **MUST NOT** be treated as
read evidence (H-1a). **r6 (N-1):** a bare correlated **non-error** observation is **also** not read
evidence; only the **U-3** complete-read acknowledgment may emit `attachment.read_confirmed`. **r7
(R6-2):** an **agent/tool-emitted** acknowledgment (or any U-3-shaped event not issued by the trusted
issuer) **MUST NOT** emit `attachment.read_confirmed`.

### 5.12 Compatibility and versioning

- **Additive only.** New Cloud V1 routes and new `AppConversation` fields (if any) are added
  without changing existing routes. This matches the upstream REST policy (additive `oneOf`
  expansion and additive response-property widening allowed; removals require a deprecation runway
  — §11).
- **Versioning:** ships under the existing Cloud V1 surface (`/api/v1/...`); no new version needed
  for an additive route.

### 5.13 Legacy `Enterprise/frontend` upload client — compatibility note (r3, R2-4)

**[F]** The `OpenHands/enterprise` frontend V1 client still uploads via the **legacy** route:
`frontend/src/api/conversation-service/v1-conversation-service.api.ts::uploadFile` builds
`buildRuntimeUrl(conversationUrl, "/api/file/upload?path=…")` and posts multipart with the
per-conversation `session_api_key`. This is the **host-level, unconfined** route (§2.3), **not** the
conversation-bound route and **not** the proposed Cloud operation.

- **Which client path uses it:** the Enterprise frontend's V1 conversation client, when it needs to
  place a file into a running conversation's workspace. (Contrast: the current `OpenHands/OpenHands`
  GUI uses the **conversation-bound scoped** route — §2.5.)
- **Replace / coexist / migrate:** the proposed P0 contract **coexists** with it. It neither removes
  nor rewrites the legacy route (removal would require the upstream deprecation runway — §11, §7.7).
  Migrating the Enterprise client to the scoped or new route is a **separate** upstream change.
- **Scope:** changing that Enterprise client is **outside** this P0 proposal's scope. This proposal
  specifies a **new, additive** Cloud operation for third parties; it does **not** touch any existing
  client.
- **Why the legacy route is not equivalent:** `/api/file/upload?path=…` is **host-level and
  unconfined** (only `is_absolute()`; no conversation binding, no workspace containment, no limits,
  no operation id/status) and requires the **server-wide, command-capable** `session_api_key`. The
  proposed operation is **conversation-bound, workspace-confined, limit-enforced, and
  operation/reconciliation-aware**, and uses **only** the caller's Cloud bearer. They are **not**
  interchangeable, and the legacy route must not be treated as a substitute for the secure
  operation.
- **[r4 (L-4)] Key weakness parity:** like the legacy Agent Server route (§2.3.2), this legacy
  Enterprise path carries the **same server-wide, command-capable** `session_api_key`; it is **not**
  equivalent to the proposed conversation-scoped, Cloud-bearer-only operation.

### 5.14 Agent-readable content delivery — the H-1 contract (r4; corrected r5; r6 N-1/N-3/N-4)

> **Status: NOT an existing capability as a whole. Partly composable from existing Cloud primitives;
> partly NEW upstream work.** No existing upstream mechanism *by itself* safely delivers uploaded
> bytes to the agent as readable content (§5.14.1). **r5 (H-1c):** some of the *pieces* already exist
> (the Cloud's **durable** pending-message queue and its **durable, conversation-bound event store**
> with a read API); the **missing** pieces are the attachment operation, the server-to-server
> **materialization**, the **authorization/scope** of the delivery, and the **successful-read**
> evidence rule. **r6 (N-1):** the *successful-read evidence rule* is **stronger** than r5 stated —
> **no existing primitive proves a successful content read** (§5.14.0), so `delivered` requires a
> **new explicit structured read acknowledgment (U-3)** and is otherwise **unreachable** (safe
> fallback: **staging** retention until `expires_at`; **workspace copy retained** — r7, R6-1). **r6
> (N-3):** the durable pending-message queue is a
> **start-only** primitive, **not** a general active-conversation accept (§5.9.1, §5.14.1). **r7
> (R6-2/R6-3):** the U-3 issuer must be a **trusted, non-agent** component (§5.15.1) and the evidence
> must come from a **quiesced** source (§5.15.4). The choice
> of mechanism remains an **owner decision** (§12, Q14).

**The problem H-1 states.** Storing bytes does not let the agent read them. r3 put an opaque
`stored_path_ref` into prompt **text** with no resolver and no reader. r4 defined the complete path;
**r5 corrected the "all-new" framing (H-1c); r6 corrects the read-evidence rule (N-1), the
`pending-messages` composability claim (N-3), and the reader example (N-4).**

#### 5.14.0 The eight lifecycle facts — never conflated (r5, H-1a; corrected r6, N-1)

A secure-upload feature can conflate several very different milestones. This document treats them as
**eight distinct facts**, each with its own evidence, and **no two may be equated**. **r6 (N-1)**
split the former single "F6" into **F6a/F6b** and **downgraded** the "non-error observation" signal:
a non-error observation is **necessary but NOT sufficient** for a successful content read.

**r8 (R7-4):** this F-set is **not** the same vocabulary as the **L1–L8** concepts in §5.10.0; the
explicit, complete cross-map between the two is **§5.10.0.1** (only **L6 ↔ F6b** and **L7 ↔ F7** are
the *same* milestone; every other pair is either unrelated or has no counterpart).

| # | Lifecycle fact | What it means | Evidence (source-verified) | Sufficient for `delivered`? |
| --- | --- | --- | --- | --- |
| **F1** | **Message/event constructed** | The client built the request body | client-side only | **No** |
| **F2** | **Event durably appended** | The message is in the conversation event log | agent-server `EventLog.append` → `atomic_write_text` (`MessageEvent` persisted) | **No** |
| **F3** | **Agent observes/receives the event** | The event is the agent's input for a run | the log is the agent's input on the next run | **No** (necessary, not sufficient) |
| **F4** | **Tool invocation attempted** | The model emitted a read tool call | an `ActionEvent` exists (its `tool_call.arguments` name the path) — **recorded even if the read FAILS** | **No** |
| **F5** | **Tool returned an observation** | The tool returned *some* result for the action | an `ObservationEvent` may exist for the action (success **or** failure) | **No** on its own |
| **F6a** | **Non-error observation recorded** | The observation is **not flagged** as an error (`Observation.is_error == false`) | an `ObservationEvent` correlated (`tool_call_id`/`action_id`) to the `ActionEvent` whose `tool_call.arguments` name the path — **but a non-error flag does not prove the intended file was read** | **No** (r6, N-1 — necessary, not sufficient) |
| **F6b** | **File contents successfully read** | The **intended file's contents** were read and delivered to the agent | **no existing primitive establishes this** (see the insufficiency below); requires a **new explicit structured read acknowledgment** (**U-3**), issued by a **trusted, non-agent** component (§5.15.1) | **Yes — but only via the NEW U-3 signal** |
| **F7** | **Agent finishes using the contents** | The agent stopped using the file | (not modeled by any current primitive) | **No** — explicitly out of scope |

**Source-backed insufficiency of the "non-error observation" signal (r6, N-1).** The r5 rule
equated **F6b** with **F6a**. That is **unsafe**. Against the pinned source
(`OpenHands/software-agent-sdk@9f7d5cb1…`):

- `Observation.is_error` is a **plain flag** that defaults to **`false`**
  (`openhands-sdk/openhands/sdk/tool/schema.py`, sha256 `76b4f42a…`); it is the **only** error flag on
  an observation.
- The **terminal** tool sets `is_error=True` **only** for interaction / empty-input / "cannot execute
  multiple commands" / closed-terminal cases. On the **completed-command** path,
  `_handle_completed_command` returns `TerminalObservation.from_text(command=…, text=…, exit_code=
  metadata.exit_code)` **without** setting `is_error` — a **non-zero exit code does NOT set it**
  (`openhands-tools/openhands/tools/terminal/terminal/terminal_session.py`, sha256 `72504a4d…`;
  `…/terminal/definition.py`, sha256 `a978161b…`).
- Therefore a **terminal** read of a **missing / unreadable** file (`cat <missing>`) yields an
  **`ObservationEvent` correlated to an `ActionEvent` naming the path, with `is_error == false`** —
  i.e. **F6a holds while the read failed**. The r5 rule would have set `delivered` (and permitted
  reclaim of the **staging** copy) for a file the agent could **not** read (threats T-18/T-19).
- The **file_editor `view`** path is **safer** for a missing path — `FileEditor.__call__` catches a
  `ToolError` and returns `FileEditorObservation.from_text(..., is_error=True)`
  (`…/tools/file_editor/impl.py`, sha256 `35353ad3…`; `…/editor.py`, sha256 `a1d735d4…`). **But** a
  successful `view` returns a **truncated text projection** (`MAX_RESPONSE_LEN_CHAR = 16000` with a
  clip notice, `…/tools/file_editor/utils/constants.py`, sha256 `a5b3f2bf…`) — so even a non-error
  `view` does **not** prove the **complete** intended bytes were read.

**Consequences (the r6 correction).**
- **F4 ≠ F6a ≠ F6b.** An `ActionEvent` mentioning `delivered_path` is **not** proof of a read; a
  correlated **non-error** observation is **not** proof of a **successful** read (the terminal
  counterexample above).
- **F2/F3 ≠ F6b.** A durably appended message (even one the agent's run consumed) proves the agent
  **saw the reference text**, **not** that it **read the file**.
- **A failed/ambiguous sequence ⇒ no success.** A failed tool call, an associated error event, a
  non-zero terminal `exit_code` (even when `is_error == false`), an incomplete/truncated observation,
  or an ambiguous event sequence **cannot** authorize cleanup.
- **No existing primitive proves F6b.** The pinned source establishes F1–F5 and **F6a**; it does
  **not** establish **F6b**. `delivered` therefore **cannot be reached from existing primitives** —
  it requires the **new, explicit structured read acknowledgment (U-3, §5.15)** (recorded as an owner
  decision, §12 Q5c/Q16). **F7 is not modeled at all.**
- **Retention default (unchanged, safe):** any unknown/inconclusive outcome — including "F6b not
  provable" — retains the file until `expires_at` (§5.10). **The fallback authorizes no early
  reclaim**; there is **no** "expiry implies a successful read" claim.

#### 5.14.1 Existing mechanisms checked (r5, H-1c)

| Candidate existing mechanism | Verified behavior (pinned source) | What it **does** establish | What it does **NOT** establish |
| --- | --- | --- | --- |
| Agent-server `POST /api/conversations/{id}/events` message (`event_service.send_message`) | **[F]** appends a `Message` (`content: Sequence[TextContent \| ImageContent]`) to the conversation event log via `EventLog.append` → `atomic_write_text` (**durable agent-server step**) | **F2** (durable event append); the message is the agent's input ⇒ **F3** on the next run | **No** generic file block ⇒ the content model is text/image only; a `stored_path_ref` string is inert text; **no** F5/F6a/F6b |
| Cloud `send-message` `ImageContent` (base64 image) | **[F]** reachable via the Cloud bearer (**thin proxy**, §5.9.1); persistence UNVERIFIED | reachability of the proxy hop | **Images only**; not materialized as a workspace file; **no** general-file read |
| **Cloud `POST /api/v1/conversations/{id}/pending-messages` (r5, H-1c; corrected r6, N-3)** | **[F]** Enterprise `queue_pending_message` → `SQLPendingMessageService.add_message` → `StoredPendingMessage` row + **`db_session.commit()`** ⇒ **durable SQL store**; **drained only at conversation *start*** — `live_status_app_conversation_service.py::_process_pending_messages` is called **once**, right after the start task reaches `READY` (the **only** caller; not invoked for an already-running conversation); entries are **deleted regardless of delivery success**; **429 above 10** | **a durable *pending*-message record + a *start-time* accept** (the **message-accept milestone** of §5.9.1, *for a conversation that is still starting*); content model is `list[TextContent \| ImageContent]` | **No** file ingestion (same text/image model); **no** F5/F6a/F6b; does **not** authorize file deletion; **and it is NOT an active-conversation delivery mechanism** — for the P0 target (an **already-running** conversation, I1) it is **not usable** (§5.9.1) |
| **Cloud `GET /api/v1/conversation/{id}/events/search` (r5, H-1c; corrected r7, R6-3)** | **[F]** Enterprise `search_events` → `EventService.search_events` over the **Cloud-side** conversation event store (per-conversation path; `kind__eq` filter supports `ActionEvent`/`ObservationEvent`); read-only. **r7 (R6-3):** this store is a **polled replica** of the agent-server event log — `remote_sandbox_service.py::poll_agent_servers` → `refresh_conversation` → `event_service.save_event` (sha256 `d239ec43…`) copies events **one at a time**; it is **not** an atomic/consistent snapshot (**r8, R7-3:** fed by the poll loop **only when there is no public URL**, else by **webhooks**) | a **durable, conversation-bound, Cloud-reachable event log** — the **evidence source** for the read rule **only when quiesced** (§5.15.4) | It **returns** events from a **replica**; it does **not** itself prove a **successful** read, and a **torn/lagging** read is **not** authoritative (a false positive is unsafe) |
| `GET …/{id}/file` / `GET …/{id}/files` (read/list) | **[F]** read-only proxies | a client read | a **read** endpoint is **not** agent ingestion — it serves a *client*, not the agent |
| Agent-server `/file/upload` (confined scoped route) | **[F]** writes into the workspace with a **client-supplied absolute path**, guarded by the **server-wide key** | a confined write primitive | requires the server-wide key + a client path; not an ingestion primitive; unsafe for a third party (§2.3) |
| Conversation workspace **git** / tool access | **[F]** the agent can read files already in its workspace | the **destination** | not a delivery mechanism: something must first place the file there |

**Classification (r5, H-1c; corrected r6, N-1/N-3) — existing vs composable vs missing:**

| Piece | Status |
| --- | --- |
| Durable **pending-message record** (Cloud SQL) | **EXISTS** — Cloud `pending-messages` (durable SQL commit). *Composable — but **start-time only** (r6, N-3), not for an already-running conversation.* |
| Durable, conversation-bound, Cloud-reachable **event log** | **EXISTS** — Cloud `events/search` over the Cloud event store. *Composable today — **but it is a replica** (r7, R6-3; r8, R7-3: poll loop only when no public URL, else webhooks): authoritative for evidence **only when quiesced** (U-10, §5.15.4).* |
| Server-side **runtime hop** (conversation → sandbox → agent-server) | **EXISTS** — `_get_agent_context`/`_proxy_git_runtime_call` pattern (§7.0). *Composable today.* |
| Conversation-bound, workspace-confined **file write** primitive | **EXISTS** — agent-server scoped route (`bind_local_conversation_runtime`, §2.3). *Reusable.* |
| **Attachment upload operation + limits + idempotency + reconciliation** | **MISSING** — new upstream work. |
| **Server-to-server ref resolution + materialization into the workspace** (design A) | **MISSING** — new upstream work (U-1). |
| **Scoped authorization** of the delivery (principal + conversation) | **MISSING** — new upstream work (§5.3, §7.2). |
| **Durable *active-conversation* message-accept** | **MISSING** (r6, N-3) — `pending-messages` is **start-only**; a durable accept for a **running** conversation is **new work** (U-2). |
| **Successful-read evidence signal** (`delivered`) | **MISSING as a *signal*** (r6, N-1; trust pinned r7, R6-2) — the **primitives exist** (`ActionEvent`/`ObservationEvent`/`AgentErrorEvent` in the event log), but **no existing primitive proves F6b** (a successful content read) **and none is a trusted, non-agent issuer**; a **new explicit structured read acknowledgment (U-3)** with a **trust boundary/provenance contract** is required (§5.15.1–§5.15.3). |
| **Quiesced evidence source** | **MISSING** (r7, R6-3; r8, R7-3) — the Cloud `events/search` store is a **replica** (poll loop only when no public URL, else webhooks); a quiesced/finalized source (or an agent-server re-verify) is **new work** (U-10, §5.15.4). |
| **Absolute delivered-path contract** | **MISSING** (r7, R6-4) — the reader requires an **absolute** path; the r6 relative `delivered_path` is superseded by the §5.15.5 contract (U-11). |

**Conclusion (corrected r6).** The **delivery mechanism as a whole** is not an existing capability;
it is **partly composable** from existing primitives. **But** (r6) two r5 overstatements are
corrected: (i) the read-evidence **primitives** exist, yet **no existing primitive proves a
successful content read** (N-1) — the **rule *and* the signal** are new (U-3); (ii) the durable
pending-message queue is **start-time only**, not an active-conversation accept (N-3). The genuinely
missing pieces are the attachment operation, the server-to-server materialization, the delivery
authorization, a durable **active-conversation** accept, and the **new successful-read signal/rule**.
**Durable message/event persistence does not establish successful agent-side file reading.**

#### 5.14.2 Recommended design — Cloud-resolved **materialization** into the workspace

The uploaded bytes are stored once under an opaque staging path (§5.7). **Delivery** then:

1. **Resolution (Cloud).** The **Cloud attachment service** resolves the opaque `stored_path_ref`
   to `(operation_id, conversation_id, file_id, staging_path, sha256)` using its own operation
   store. The ref is **not** accepted from an untrusted party as a filesystem path — it is an
   internal key.
2. **Authorization (Cloud).** Resolution succeeds only if the ref belongs to **this**
   `conversation_id` and the **authorized principal** of the current request; a ref for another
   conversation/principal ⇒ **403** (cross-conversation reference access prevented).
3. **Conversation-identity verification and workspace-root provenance (r7, R6-4; corrected r8, R7-2; corrected r9, R8-2).**
   The Cloud resolves the target conversation's **runtime endpoint and session key** server-side via
   `_get_agent_server_context` (§7.0) — that helper returns `conversation`/`sandbox`/`sandbox_spec`/
   `agent_server_url`/`session_api_key` and **does NOT carry the per-conversation workspace root**
   (it exposes only `sandbox_spec.working_dir`, the **ungrouped base**; its `AgentServerContext`
   dataclass has **no** workspace-path field). The Cloud therefore obtains the conversation's
   **authoritative workspace root** from the **pinned conversation tag** `archiveworkspacepath`
   (written by the server at conversation start with the **grouped** path
   `{base}/{conversation_id.hex}` for any non-`NO_GROUPING` strategy), **or** from an **agent-server
   query** for the runtime's own `workspace.working_dir` (the value
   `bind_local_conversation_runtime` derives on the agent-server side). The Cloud then verifies the
   operation's `conversation_id` matches the **resolved** workspace **and** the authorized principal
   before any write. **r8 (R7-2): the root is trusted only when its provenance binds it to the
   intended `(principal, conversation_id, operation_id)` and to the authenticated request — a path is
   NOT trusted merely because it is absolute or resolves successfully.** **r9 (R8-2):** the tag→root
   **read already exists and ships** (`AppConversationInfo.repositories` →
   `conversation_repositories`; live `AppConversation.repositories.path`); what is **not** established
   by the pinned source is the **identity/authorization binding** of that root to the intended
   `(principal, conversation_id, operation_id)` — that binding is the **proposed contract (U-12) and is
   UNVERIFIED** (§5.15.6, Q22). The agent server's
   `bind_local_conversation_runtime` containment (`resolve().is_relative_to(workspace_root)` → 422) is
   the **second, defense-in-depth** check **on the agent-server**, where the correct root is already
   available — it is **not** the Cloud's resolution source.
4. **Materialization (atomic publication — r5, S-3).** The Cloud calls the (new)
   **server-to-server delivery endpoint** (§5.15) which, **under the confined base**, writes the
   bytes to a **server-generated delivered path** — e.g.
   `uploads/{operation_id}/{sanitized_display_name}` (a **workspace-relative storage form**; the path
   **handed to the agent** is the **absolute** form, r7/R6-4 — §5.15.5) — using
   `O_NOFOLLOW` + `O_CREAT|O_EXCL`
   (symlink/TOCTOU-safe, §7.4). **The write MUST be atomic:** bytes are written to a
   server-generated temporary file in the same directory and **published with `os.replace`** (rename),
   so a crash never leaves a truncated `delivered_path`. The final file's **mode/ownership MUST be
   readable by the agent's runtime user** (an explicit deployment requirement; whether the default
   umask/uid already satisfies this is **UNVERIFIED** — §7.4, §12 Q14). The client **never** supplies
   this path; the client-supplied `client_filename` is used **only** for a sanitized display name.
5. **Reference to the agent (r5, H-1b; reader corrected r6, N-4; path corrected r7, R6-4).** The agent
   learns the content exists because the delivered file is **inside the agent's own workspace** at the
   concrete `delivered_path`, which is included in the message the bot sends (via the existing
   `send-message` path): *"the file you uploaded is at `<delivered_path>`"*. **r7 (R6-4): the path
   handed to the agent is ABSOLUTE** (workspace-root-joined), because the named reader (file_editor
   `view`) **rejects a relative path** (`validate_path`/`is_host_absolute_path`, §5.15.5); the
   materialization writes under the confined workspace root (`workspace.working_dir` that
   `bind_local_conversation_runtime` derives on the agent-server side — the **grouped**
   `{base}/{conversation_id.hex}` under any non-`NO_GROUPING` strategy; r8, R7-2), so the **absolute** path the agent receives is directly
   openable by its normal file tools. **The agent receives a readable (absolute) path, not an
   inert token** (this is the core H-1 fix); the full path contract is §5.15.5. **r6 (N-4) — the reader and its success signal:**
   - **Preferred reader — a structured read tool.** The **file_editor `view`** tool returns a
     structured `FileEditorObservation` (`command`, `path`, `prev_exist`, `content`); a missing path
     raises a `ToolError` that the tool maps to **`is_error=True`**
     (`…/tools/file_editor/impl.py`). Even so, a successful `view` returns a **truncated** projection
     (`MAX_RESPONSE_LEN_CHAR = 16000`, with a clip notice) — so a non-error `view` alone still does
     **not** prove the **complete** intended bytes were read. (The SDK also ships a **structured**
     `read_file` tool with `ReadFileObservation{file_path, file_content, is_truncated, lines_shown,
     total_lines}` and an explicit `is_error` — but it is a **Gemini-preset** tool and is **NOT** in
     the SDK's default tool set `TerminalTool | FileEditorTool | TaskTrackerTool`; its presence is
     therefore **deployment-configuration-dependent**, not guaranteed.)
   - **Terminal `cat` is NOT an acceptable F6b signal.** A non-zero `exit_code` is a **failed read
     even when `is_error == false`** (the r6 counterexample, §5.14.0). A terminal reader may be used
     only if the deployment supplies a **complete-read** signal; `cat` alone is **insufficient**.
   - **If no authoritative complete-read signal exists, the operation uses the conservative retention
     fallback** (step 6) — it does **not** assert `delivered` on the mere existence of an observation.
6. **Successful-read evidence (r5, H-1a; corrected r6, N-1; trust/consistency added r7, R6-2/R6-3 — the safe
   contract).** The operation
   transitions to **`delivered`** **only** when the system observes **positive evidence of a
   successful *content* read (F6b)** — which **no existing primitive establishes**, and which **must
   come from a trusted, non-agent issuer (§5.15.1) read from a quiesced source (§5.15.4)**. The rule
   (over a **quiesced** view of the agent-server conversation event log — *not* the lagging Cloud
   `events/search` replica, §5.15.4):

   > **`delivered` ⇔ F2/F3 (the reference message is durably appended and is the run's input) AND
   > F6b (a SUCCESSFUL content read), where F6b is established ONLY by the new explicit structured
   > read acknowledgment (U-3, §5.15).**
   > **A bare `ActionEvent` (F4) is NOT sufficient.** **A correlated non-error `ObservationEvent`
   > (F6a) is NOT sufficient** — a **terminal** tool call that **fails** (non-zero `exit_code`) still
   > returns a **non-error** observation (the r6 N-1 counterexample, §5.14.0). An **`AgentErrorEvent`**,
   > a `UserRejectObservation`, an error result, a **non-zero terminal `exit_code`**, a missing
   > correlated observation, an **incomplete/truncated** read, or an ambiguous sequence ⇒ **NOT
   > `delivered`.**

   **U-3 (proposed capability — NOT implemented upstream).** A **structured read acknowledgment** that
   is **emitted by a trusted, non-agent issuer** (a Cloud/Agent-Server-side component), **durably
   recorded**, and **reachable via a quiesced evidence source** (§5.15.4). It must carry at minimum
   `operation_id`, `file_id`, `delivered_path`, `sha256`, a **complete-read** indicator (bytes/lines
   read vs total), and a monotonic timestamp. **r7 (R6-2):** the issuer MUST be **outside the agent's
   control**; an acknowledgment **produced or relayed by the agent** (a tool result, an
   `ObservationEvent`, a prompt reply, an arbitrary event) is **NOT** valid evidence. **The trust
   boundary, provenance/authentication, and the exact fields + validation invariants are specified in
   §5.15.1/§5.15.2/§5.15.3.** This proposal **does not claim** upstream implements U-3, and — because
   the pinned source does **not** establish a trusted issuer — the issuer is **UNVERIFIED** and U-3
   remains a **NEW upstream capability** (owner decision, §12 Q16).

   **If this positive evidence is unavailable in a given deployment — which is the case for *every*
   deployment today, since U-3 does not exist — `delivered` is NEVER asserted** and the operation
   stays `stored` until `expires_at` (safe default, §5.10). **The `expires_at` fallback does NOT
   prove a successful read**; it is a **retention bound**, not a delivery signal. **No early reclaim
   happens without U-3.** **F7 (the agent finished using the contents) is NOT modeled** — it is
   neither required nor claimed (owner decision, Q16).
7. **Retention/deletion (r7, R6-1; corrected r8, R7-1; precision r9, R8-1 — see §5.10.1).** **Only the staged/recovery copy (C1/C3)
   is reclaimed** — on `delivered` (via U-3) or at `expires_at`. **The workspace-materialized copy (C2)
   is the agent's file and is NEVER reclaimed by `expires_at`;** it is removed only on a trustworthy
   **end-of-use (F7)** condition (not modeled today) or on the **physical removal of the workspace
   directory**. **Conversation archive/delete does NOT physically remove the workspace** (it
   **archives** it and **preserves** the directory; the directory is removed only on **sandbox/pod
   teardown**). Teardown **is modeled** for the **managed** backends (Docker/E2B/k8s) by the
   Enterprise **sandbox lifecycle** (`delete_after_seconds`, a *configurable* idle bound) and is
   **delegated to runtime-api** for the **Cloud/remote** backend (§5.10.4, r9/R8-1). **r10 (R9-1/R9-3):**
   that lifecycle timer is a **separate clock** from the operation's `expires_at` (never conflate them)
   and is **not** an F7 end-of-use signal; and the verified teardown mechanism is **container removal**
   — physical deletion of the **underlying** workspace data is **UNVERIFIED** for host-mounted layouts
   (§5.10.4).
   Because U-3 does not exist today **and no conversation-scoped event reclaims C2**, the materialized
   file **persists beyond the life of the conversation** until a sandbox/pod teardown (r8, R7-1;
   precision r9, R8-1 — §5.10.4/Q18).

**Rejected weaker alternatives for step 6 (explicitly):** "any event mentioning the path" (F4) is
**insufficient**; "message appended" alone (F2) is **insufficient**; **"a correlated non-error
observation" (F6a) is *also* insufficient** (r6, N-1 — the terminal counterexample). Only the **new
U-3 complete-read acknowledgment** (or the safe retention fallback) may gate `delivered`. This is the
r6 correction of the r5 rule, which accepted a correlated non-error observation.

#### 5.14.3 Alternatives compared (and why materialization is recommended)

| Design | Security | Reliability | Compatibility | Verdict |
| --- | --- | --- | --- | --- |
| **A. Materialize into the workspace + tell the agent the real path** (recommended) | Strong: reuses workspace confinement; server-generated path; no client path; agent reads via normal tools | Strong: successful-read evidence is derived from the **event log** **only via the new U-3 structured read acknowledgment** (r6, N-1 — existing primitives are **insufficient**); works for **any** file type | Additive; no change to the message model | **Recommended** (requires U-3) |
| B. New **message attachment content block** (e.g. `FileContent{ref}`) the agent server ingests | Medium–strong, but changes the SDK message model and the LLM-facing content | Strong **only if** the agent server implements ingestion (new work) | **Breaks/adds** to the public message schema | Rejected for r5 (larger surface; not required) |
| C. **Agent-side tool/endpoint** to fetch by ref (agent calls `GET …/attachments/{ref}`) | Medium (needs a new tool + an authorized read path) | Depends on the model *choosing* to call the tool (not guaranteed) | New tool + endpoint | Rejected (delivery not guaranteed) |
| D. **Inline the bytes** as text/base64 in the prompt | Weak (size limits; binary corruption) | Poor for general files | No schema change | Rejected |

**Recommendation: A.** It reuses existing confinement and works for every file type; successful-read
evidence is derived from the event log **only via the new U-3 structured read acknowledgment** (r6,
N-1 — existing primitives are **insufficient**; §5.14.2 step 6).
**Owner decision (§12, Q14)** — the
choice of delivery mechanism (and whether the *existing* `send-message` path may be extended instead
of a new endpoint) is a maintainer call.

#### 5.14.4 H-1 required answers (explicit; corrected r6, N-1/N-4)

| Question | Answer |
| --- | --- |
| Which component resolves `stored_path_ref`? | The **Cloud attachment service** (§5.14.2 step 1). |
| Which component authorizes access? | The **Cloud** (principal + conversation ownership), with the agent-server `bind_local_conversation_runtime` containment as defense-in-depth (§5.14.2 step 2–3). |
| How is conversation identity verified during resolution? | Server-side resolution of conversation → runtime endpoint + key, and (r8, R7-2) of the **authoritative workspace root** from the `archiveworkspacepath` tag or an agent-server query, **bound** to `(principal, conversation_id, operation_id)` (§5.14.2 step 3, §5.15.6 / U-12); the op's `conversation_id` must match the resolved workspace. |
| Materialized in the workspace, message attachment, or other? | **Materialized in the agent workspace** at a server-generated `delivered_path`; the message references that path (design A). |
| How does the agent learn the content exists? | The bot's `send-message` includes the concrete **absolute** `delivered_path`; the agent reads it with normal tools (the reader requires an absolute path — §5.15.5), resolved against the confined workspace root (§5.14.2 step 5). |
| How is agent readability established? | **Only** by a **successful *content* read (F6b)**, established by the **new U-3 structured read acknowledgment** issued by a **trusted, non-agent issuer** (§5.15.1) — **not** by a bare `ActionEvent` (F4), **not** by a correlated **non-error** observation (F6a — a **failed** terminal read is non-error), and **not** by the appended message alone (F2/F3) (§5.14.2 step 6, §5.14.0). |
| Is "the agent finished using the contents" (F7) modeled? | **No.** F7 is **not** modeled by any current primitive and is **neither required nor claimed**. Only F6b (successful content read) gates `delivered` (§5.14.0, §12 Q16). |
| If the deployment cannot provide F6b evidence? | `delivered` is **never** asserted; the operation stays `stored` and the **staging** bytes are retained until `expires_at`, while the **workspace-materialized copy (if any) persists beyond the life of the conversation** (r7, R6-1; corrected r8, R7-1 — §5.10.1, §12 Q16/Q18). **This is the case for every deployment today** (U-3 does not exist). |
| Which reader/tool and success signal? | A **structured read tool** (file_editor `view`, or a deployment-enabled structured `read_file`) whose observation proves a **complete** read; the **U-3** acknowledgment is the authoritative signal. **Terminal `cat` is NOT acceptable** — a non-zero `exit_code` is a failed read even when `is_error == false` (§5.14.2 step 5, N-4). |
| If resolution succeeds but delivery fails? | Operation stays `stored` (or `failed`); no `delivered`; **no deletion** before `expires_at`; the bot may retry delivery (idempotent, §5.15) but never blind-retries the upload (§8.3). |
| If delivery succeeds but the ack is lost? | The agent already has the file; the client reconciles via status (`delivered`/`stored`). No duplicate **file** is created (materialization is idempotent on `operation_id`+`file_id`). |
| Path traversal / symlink / TOCTOU / cross-conversation / stale refs? | Server-generated path; `O_NOFOLLOW`+`O_EXCL`; atomic publish via `os.replace`; `resolve().is_relative_to(base)`; ref bound to `(conversation, principal)` ⇒ 403 on mismatch; expired ref ⇒ rejected (§5.14.2, §5.9.1, §7.4). |
| How is the ref revoked? | The `stored_path_ref` is valid only while the **staging** copy (C1) exists — i.e. non-terminal and within `expires_at`; on `delivered`/`expired`/`failed`/`rejected` it is **revoked** (status reports it invalid) and the **staging** bytes are reclaimed. **The `delivered_path` is governed by the *workspace copy* lifetime (r7, R6-1):** it stays valid as long as C2 exists (**beyond the life of the conversation** today — no conversation-scoped reclaim; r8, R7-1), **even for a terminal op** (§5.10.1). |
| Evidence required before deleting the stored bytes? | **`delivered`** (materialized + **F6b successful content read** confirmed via U-3) **or** `expires_at` — never `consumed_at` alone (§5.10, M-3, H-1a/N-1). **r7 (R6-1); r8 (R7-1); precision r9 (R8-1):** this deletes the **staging** bytes only; the **workspace copy** is deleted only on end-of-use (F7, unmodeled) or **physical workspace removal** (sandbox/pod teardown — *modeled* for the managed backends, *delegated to runtime-api* for the Cloud backend) — **never** on conversation archive/delete. |

### 5.15 New upstream requirements implied by H-1/M-2/M-3/M-5 (r4; re-framed r5; corrected r6; extended r7; extended r8; corrected r9)

These are **additions to the upstream change set** (§7.1). Each is a **proposed contract**, not an
existing capability. **r5 (H-1c):** the column "Status" distinguishes requirements that are
**partly composable from existing primitives** from requirements that are **genuinely new**.
**r6:** U-2 is corrected (**start-only** `pending-messages`, N-3) and U-3 is upgraded to a **new
signal** requirement (N-1). **r7 (R6-2/R6-3/R6-4):** U-3 gains a **trust-boundary/provenance/field
contract** (§5.15.1–§5.15.3); **U-10** (a **quiesced evidence source**) and **U-11** (a **complete
path contract**) are added. **r8 (R7-2/R7-3):** **U-12** (a **workspace-root provenance/binding**
capability, §5.15.6) is added, and the replica description of U-10 is qualified (poll loop **only
when there is no public URL**, else **webhooks**). **r9 (R8-2):** U-12 is **re-scoped** — the
**tag→root read already exists and ships** (`AppConversationInfo.repositories`; live
`AppConversation.repositories.path`), so U-12 covers **only** the **identity/authorization binding**
(§5.15.6).

| # | Requirement | Why (finding) | Status (r5/r6/r7/r8) |
| --- | --- | --- | --- |
| U-1 | A **server-to-server delivery endpoint** (internal credential) that materializes a resolved ref into the conversation workspace at a server-generated path (design A), **atomic publish** (`temp` + `os.replace`) and a readable mode/owner; the path **handed to the agent** is **absolute** (r7, R6-4 — §5.15.5). | H-1, S-3 | **NEW** (endpoint + materialization); reuses the confined-write primitive |
| U-2 | A **durable *active-conversation* message-accept step**: the Cloud must durably record that it accepted the reference message **for a running conversation**. | M-2, **N-3** | **NEW for the P0 case** (r6, N-3). The **existing** `POST /api/v1/conversations/{id}/pending-messages` is durable **but start-only** (drained once at conversation start, deleted regardless of success, capped at 10) ⇒ **not usable** for an already-running conversation. A durable step **on `send-message`** is also **NEW**. Owner choice (Q15). |
| U-3 | A **successful-read evidence *signal***: a **new explicit structured read acknowledgment** that proves a **complete content read (F6b)** — `delivered` is set **only** on it, **never** on a bare `ActionEvent` (F4), **never** on a correlated **non-error** `ObservationEvent` (F6a — a failed terminal read is non-error, N-1), and **never** on the appended message alone (F2/F3). **r7 (R6-2):** the acknowledgment MUST be issued by a **trusted, non-agent** component (§5.15.1) with **authenticated provenance** (§5.15.2) and **exact content binding** (§5.15.3). | M-3, H-1, **H-1a**, **N-1**, **R6-2** | **NEW** (the **signal** is new; the read-evidence **primitives** exist — `ActionEvent`/`ObservationEvent`/`AgentErrorEvent` readable via `GET …/events/search` — but they are **insufficient** *and* the trusted issuer does **not** exist today: **UNVERIFIED**). See the **U-3 trust/provenance/field contract** below. |
| U-4 | **Delivery idempotency**: materialization keyed on `(operation_id, file_id)`; a retried delivery does not create a second file. | H-1, M-1 | **NEW** |
| U-5 | The server documents that it has **no batch concept**; the batch deadline is client-side (§8.4). | M-5 | **NEW** (documentation) |
| U-6 | (Optional) A **message-level idempotency key** on `send-message` (the route has none today), so a retried message cannot duplicate. | I-1 | **NEW** (optional) |
| U-7 | **Filesystem guarantees for delivered files**: atomic publication, server-generated destination + path containment, symlink/TOCTOU resistance, readable mode/owner, partial-write cleanup, cross-conversation isolation (§7.4). | S-3 | **NEW** (contract; reuses containment) |
| U-8 | **Correlation contract**: `client_operation_id` **required**, echoed in every response, unique per `(principal, conversation)` with duplicate-payload handling (§5.16). | M-4, **M-4b** | **NEW** (contract) |
| U-9 | **OpenHandBot integration boundary**: the existing outbox carries **prompt text only**; attachment dispatch requires a **new outbox payload capability** or another explicitly approved mechanism (§8.3). | **S-2** | **NEW** (integration contract) |
| U-10 | A **quiesced/finalized evidence source** for the U-3 rule: the Cloud `events/search` store is a **replica** of the agent-server event log (not atomic), so event-based evidence MUST be read from a **quiesced** source, or re-verified on the **agent-server**, before it may gate `delivered`. | **R6-3** | **NEW.** Verified: `remote_sandbox_service.py::poll_agent_servers` → `refresh_conversation` → `event_service.save_event` (sha256 `d239ec43…`) copies events **one at a time**; the replica is **not** a consistent snapshot. **r8 (R7-3):** the population path is **deployment-dependent** — a poll loop **only when there is no public URL** (`web_url is None or 'localhost'`), else **webhooks**; the quiescence requirement holds on **both** paths. |
| U-11 | A **complete path contract** for the delivered file: the agent-facing path MUST be **absolute** (the reader, file_editor `view`, rejects relative paths — `validate_path`/`is_host_absolute_path`, sha256 `a1d735d4…`), with post-resolution confinement, symlink/TOCTOU protection, existence/regular-file checks, content identity, and readability (§5.15.5). | **R6-4** | **NEW** (contract; the reader's absolute-path requirement is verified; the relative `delivered_path` of r6 is **superseded**). |
| U-12 | A **workspace-root provenance/binding capability** for the Cloud side: resolve the conversation's **authoritative** workspace root from the pinned `archiveworkspacepath` tag **or** an agent-server query for the runtime's own `workspace.working_dir`, **bound** to `(principal, conversation_id, operation_id)`. `_get_agent_server_context` carries only `sandbox_spec.working_dir` (the **ungrouped base**), so it is **not** a valid root source. **r9 (R8-2) — re-scoped:** the **tag→root read is EXISTING** (`AppConversationInfo.repositories` → `conversation_repositories`, sha256 `7a4a54c0…`/`a8d0bbe3…`; live `AppConversation.repositories.path`); U-12 covers **only** the **identity/authorization binding** (no pinned primitive binds `(principal, conversation_id, operation_id)` to the upload op). | **R7-2** | **PARTLY EXISTING / PARTLY NEW.** *Existing:* the tag→root read ships (`AppConversationInfo.repositories`, sha256 `7a4a54c0…`; `conversation_repositories`, sha256 `a8d0bbe3…`; live Cloud V1 `AppConversation.repositories.path`). *NEW (U-12):* the **identity + authorization binding** of that root to `(principal, conversation_id, operation_id)`. Verified: `_get_agent_server_context` exposes only the base (`AgentServerContext` has no workspace-path field, sha256 `c43ed4f7…`); the grouped path exists (`grouped_workspace_dir`, sha256 `27bae62a…`) and is pinned in the server-managed reserved tag `archiveworkspacepath` (sha256 `7a4a54c0…`). See §5.15.6. |

#### 5.15.1 U-3 trust boundary — who may issue the acknowledgment (r7, R6-2)

> **r7 (R6-2) — an agent-controlled acknowledgment is NOT evidence.** U-3 is only meaningful if its
> **issuer** is outside the agent's control. This subsection pins that boundary.

**Trusted issuer (required).** The authoritative issuer of U-3 MUST be a **service-side,
non-agent** component — a **Cloud/control-plane** service or an **Agent-Server** component that
performs (or directly observes) the content read **on its own authority**, not a value the agent can
write. Concretely, the issuer is the component that:
- holds the **materialized file identity** (path + `sha256` + byte length) from the delivery
  materialization it performed or verified; **and**
- can attest **how many bytes of that exact file were read** in a read it performed or intercepted.

**What is explicitly NOT a valid issuer (fail-closed).** Any of the following is **never**
authoritative evidence and MUST be ignored by the consumer:
- an **agent/tool/model-produced** event (a tool result, an `ObservationEvent`, an `AgentErrorEvent`,
  a `UserRejectObservation`, a message/prompt reply, or **any** event the agent can author);
- an event **relayed** from the agent by a service that merely forwards the agent's assertion;
- a client-supplied field named `issuer`/`success`/`read`/`verified` (a **name is not trust**).

**Classification (r7).** The pinned source does **not** establish that such a trusted, non-agent
read-attesting issuer exists today (no read-acknowledgment primitive was found in the SDK at
`9f7d5cb1…`). Therefore U-3's issuer is classified **NEW upstream capability**, its **trust property
is UNVERIFIED**, and **`delivered` stays unreachable** until (a) the issuer is implemented **and**
(b) its trust property is independently verified. This is recorded as owner decision **§12 Q16/Q19**.

#### 5.15.2 U-3 provenance and authentication (r7, R6-2)

If the issuer is implemented, the consumer MUST verify **all** of the following **before** treating a
U-3 as evidence. A field *named* `issuer`/`success`/`read`/`verified` **creates no trust**:

| Property | Requirement |
| --- | --- |
| **Issuer identity** | the acknowledgment is attributed to a **known, expected** service-side issuer (not an agent/tool), and the attribution is **cryptographically or transport-authenticated** (e.g. a signed service-to-service assertion, or an internal-credential-authenticated server-to-server channel — the *mechanism* is a proposed upstream contract, **not** an existing feature). |
| **Authenticated provenance** | the acknowledgment is delivered over an **authenticated service-to-service** path (internal credential / network boundary), never accepted from a client or from the conversation event stream authored by the agent. |
| **Integrity** | the acknowledgment is **tamper-evident** (signed or covered by a MAC), so a field cannot be altered in transit or at rest without detection. |
| **Uniqueness / replay protection** | each acknowledgment carries a **unique `ack_id`**; a **replayed** `ack_id` (or a stale one) is **rejected**. |
| **Authorization scope** | the acknowledgment is authorized for **exactly** the `(principal, conversation_id, operation_id, file_id)` it claims; a mismatch ⇒ **rejected**. |

**If a signed/authenticated service-to-service acknowledgment is required** (it is, for the trust
property to hold), it is described here as a **proposed upstream contract**, **not** an existing
feature, unless source evidence proves otherwise (**it does not** — see §5.15.1).

#### 5.15.3 U-3 exact fields and validation invariants (r7, R6-2)

**Required fields (minimum).** U-3 MUST bind **all** of:

- `ack_id` — **unique** acknowledgment identifier (replay protection).
- `issuer` — the **service-side** issuer identity (see §5.15.1; **not** an agent/tool).
- `operation_id`, `file_id` — the operation and file.
- `conversation_id`, `principal` — the authorized conversation and principal.
- `content_version` / immutable object id — the **exact stored object version** (a path alone does
  **not** uniquely identify content).
- `delivered_path` — the **resolved** workspace destination (see §5.15.5).
- `sha256` **and** `byte_length` — the content digest and size of the **exact** delivered bytes.
- `bytes_read` **and** `byte_length` (or `lines_read`/`lines_total`) — so **completeness** is
  provable; `read_complete: bool`.
- `truncated: bool` — explicit partial/truncation status.
- `read_op_id` / `tool_call_id` — the read operation and (where applicable) the tool/action
  correlation id.
- `read_at` — a **monotonic** timestamp.
- `issuer_sig` / `issuer_mac` — the authentication material (§5.15.2).

**Validation invariants (all MUST hold; otherwise the acknowledgment is ignored, fail-closed).**

1. **Issuer** is a trusted, non-agent service-side issuer and its authentication verifies.
2. **Uniqueness:** `ack_id` has not been seen before (replay ⇒ reject).
3. **Identity match:** `operation_id`/`file_id`/`conversation_id`/`principal` match the operation and
   the authorized principal **exactly**.
4. **Content match:** `sha256` and `byte_length` match the **materialized** file's digest and size.
5. **Completeness:** `read_complete == true` **and** `truncated == false` **and**
   `bytes_read == byte_length` (no partial read).
6. **No later error:** **no later** `AgentErrorEvent`/error observation for the **same** action.
7. **Freshness / quiescence:** the evidence was read from a **quiesced** source (§5.15.4) and is not
   stale relative to the operation.
8. **Semantics:** `delivered` ⇔ F2/F3 **AND** a valid U-3 (all of the above).

**Rejected acknowledgments (⇒ stay `stored`, retain staging until `expires_at`; never `delivered`):**
missing, malformed, **agent-issued**, unauthenticated, **mismatched identity/content**, **truncated**
or partial, **duplicated/replayed**, or **stale**; and any acknowledgment **downgraded** by a later
error event for the same action.

**Distinguish reading from delivery and use (r7, R6-2; aligned with §5.14.0).** U-3 proves **F6b** (a
**successful content read**, and presupposes F1–F5/F6a) — it **never** proves F7 (end-of-use). Using
the **same** fact labels as §5.14.0:

| Fact (§5.14.0) | Proved by U-3? | Cleanup implication |
| --- | --- | --- |
| F1 message/event constructed | context only | none |
| F2 event durably appended | required **separately** by the rule (§5.14.2 step 6), not by U-3 | none |
| F3 agent observes/receives the event | context only | none |
| F4 tool invocation attempted | **presupposed** (a read occurred) — never sufficient alone | none |
| F5 tool returned an observation | **presupposed** — never sufficient alone | none |
| F6a non-error observation | **presupposed**, and **NOT sufficient** (§5.14.0) | none |
| **F6b successful content read** | **yes** (with the completeness fields) | **staging (C1)** may be reclaimed once the op is terminal |
| **F7 agent finished using the content** | **NO — never** | **workspace copy (C2) is NOT reclaimed on a read** |

**A successful read (F6b) does NOT prove the agent finished using the content (F7).** If no trustworthy
signal
proves F7, the design **MUST NOT** infer it from a read acknowledgment, and **C2 is retained**
(§5.10.1/§5.10.4). The cleanup implication of a read is **staging-only**; the cleanup implication of
end-of-use is **separate and unmodeled**.

#### 5.15.4 Event-log consistency requirement (r7, R6-3; corrected r8, R7-3)

**Verified source fact — authoritative vs replicated.** The **authoritative** state is the
**agent-server's own conversation event log** (the source of truth for what a run did). The Cloud
`GET /api/v1/conversation/{id}/events/search` store is a **replica** of that log, **eventually
refreshed**, and is **not** an atomic/consistent snapshot. The replica is populated by **one of two
deployment-dependent paths** (r8, R7-3):

- **Poll loop (no public URL):** `remote_sandbox_service.py::poll_agent_servers`
  (`while True … await asyncio.sleep(sleep_interval)`) → `refresh_conversation` →
  `event_service.save_event` (**one event at a time**) — sha256 `d239ec43…`. Source: the poller is
  **started only when the app server has no public URL** (`web_url is None or 'localhost' in
  web_url`), "because webhook callbacks cannot be invoked".
- **Webhook callbacks (public URL present):** in a deployment with a public URL, the store is fed by
  **webhook callbacks** from the runtime, whose **freshness/lag** characteristics differ from the poll
  interval.

**What the source does and does not establish (precise).** *Verified:* the replica exists, is
eventually refreshed, is written **one event at a time**, and its **population path is
deployment-dependent**. *UNVERIFIED:* the exact `sleep_interval` value, and the webhook path's lag
bound. The replica is **not** a consistent snapshot on either path.

**Required consistency guarantee (r7, unchanged; applies regardless of the population path — r8).**
Any **event-based evidence** used to gate `delivered` (or any cleanup) MUST be read from a
**quiesced/finalized** source — i.e. a source guaranteed to be **complete and consistent** for the
action in question — **or** re-verified against the **agent-server** event log directly. A **torn** or
**lagging** replica read MUST NOT be treated as authoritative: a false **negative** (U-3 not yet
replicated) is merely conservative (`stored`), but a false **positive** (a later error event not yet
replicated) is **unsafe**. **This requirement holds whether the store is fed by the poll loop or by
webhooks.**

**Classification.** Where the current API cannot provide that guarantee, the required capability is
**NEW upstream work (U-10)**. **Until U-10 exists, no evidence may be taken from the replica** to
assert `delivered`.

#### 5.15.5 Complete path contract for the delivered file (r7, R6-4)

**Verified source fact.** file_editor `view` **requires an absolute path**: `FileEditor.__call__` →
`validate_path` raises `EditorToolParameterInvalidError("path", …)` when `is_host_absolute_path(path)`
is false (sha256 `a1d735d4…`, line 666); a missing path is also rejected for non-`create` commands by
the `validate_path` missing-path guard (`if command != "create" and not path.exists():` at line 689,
whose `raise EditorToolParameterInvalidError(…)` is at line 690 — lines 689-694; **corrected r11,
N10-1**: r10 cited this single fact inconsistently as "line 691" here and "line 693" in §11). r6
handed the agent a **workspace-relative** `delivered_path`, which the named reader
**rejects** — so "the agent's normal tools can open it" was asserted but not implementable.

**Path contract (r7 — required; the r6 relative-path wording is superseded).**

| Property | Requirement |
| --- | --- |
| **Server-side resolution** | the destination is **server-generated**; the client supplies **no** path (§5.14.2 step 4). |
| **Workspace root** | the write happens under the **authoritative** conversation workspace root, resolved **server-side** from the **pinned `archiveworkspacepath` tag** (the **grouped** path `{base}/{conversation_id.hex}` under any non-`NO_GROUPING` strategy) **or** an **agent-server query** for the runtime's own `workspace.working_dir` — **NOT** from `_get_agent_server_context`/`sandbox_spec.working_dir` (that helper carries the **ungrouped base**, not the per-conversation root — r8, R7-2). The op's `conversation_id` and the authorized **principal** must match the resolved workspace (§5.14.2 step 3). **Provenance/binding contract: §5.15.6 (U-12) — the read is *existing*; the identity/authorization binding is *proposed/UNVERIFIED* (r9, R8-2).** |
| **Root provenance / binding** | the root MUST be bound to the intended `(principal, conversation_id, operation_id)` and to the **authenticated** request; a path is **NOT** trusted merely because it is **absolute** or resolves successfully. The tag is **server-written** (a reserved key callers cannot set); the write-authority is the server. **r9 (R8-2):** the tag→root **read** already exists (`AppConversationInfo.repositories`, live `AppConversation.repositories.path`) — what remains **NEW (U-12)** is the **identity/authorization binding**, which no pinned primitive provides (§5.15.6). |
| **Absolute representation** | the path **handed to the agent** is **absolute** (workspace-root-joined), so the reader accepts it **without further transformation**; the **relative** form may be shown for readability but the **authoritative** path is absolute. |
| **Confinement after resolution** | `resolve().is_relative_to(workspace_root)` is re-checked **immediately before** the write (TOCTOU-safe). |
| **Symlink / TOCTOU** | `O_NOFOLLOW` + `O_CREAT\|O_EXCL`; atomic publish via temp + `os.replace` (§7.4). |
| **Existence / regular-file** | the reader must confirm the path exists and is a **regular file** (not a directory/device). |
| **Content identity** | the file's `sha256`/`byte_length` match the operation's materialized identity (a path alone does **not** identify content). |
| **Permissions / readability** | the published file is readable by the agent's runtime user (deployment parameter, §7.4/§12 Q14). |
| **Reader's accepted input** | the reader's **actual** accepted input is an **absolute** path (verified); the producer-to-reader flow is therefore: server generates absolute path → writes under the confined root → the bot references that **absolute** path in the message → the reader opens it directly. |

**Implementability.** With the **absolute** path produced server-side and referenced by the bot, the
flow is implementable with the **existing** file_editor reader (a deployment that enables the
structured `read_file` tool may use it instead). Where a deployment cannot produce the **absolute**
path or cannot guarantee **content identity**, that piece is **NEW upstream work (U-11)** and the read
proof is **unavailable** (the op stays `stored`). **r8 (R7-2); corrected r9 (R8-2):** the **root
identity/authorization binding** (§5.15.6 / U-12) is a **separate** new capability (the tag→root
**read** already exists); where the binding is not established, the write MUST NOT
proceed on a path whose identity is unproven.

#### 5.15.6 Workspace-root provenance and binding contract (r8, R7-2; corrected r9, R8-2)

**Problem (r7, R7-2).** §5.14.2 step 3 and §5.15.5 previously named `_get_agent_server_context` as the
source of the conversation's **workspace root**. Against the pinned source that helper returns only
`conversation`/`sandbox`/`sandbox_spec`/`agent_server_url`/`session_api_key`; its `AgentServerContext`
dataclass has **no** workspace-path field, and it exposes `sandbox_spec.working_dir` — the **ungrouped
base** — not the per-conversation (grouped) root. The per-conversation root
`{base}/{conversation_id.hex}` is produced by `grouped_workspace_dir(base, strategy, id)` for every
strategy other than `NO_GROUPING`, and is pinned in the conversation tag
`ARCHIVE_WORKSPACE_PATH_TAG_KEY = 'archiveworkspacepath'` at conversation start.

**r9 (R8-2) — what is *existing and verified* (the read), and what is *new* (the binding).** The pinned
source and the **live** Cloud V1 API establish that a **Cloud-side read of the per-conversation root
already exists and ships**:

- `AppConversationInfo.repositories` (`app_conversation/app_conversation_models.py`, sha256 `7a4a54c0…`,
  lines 250-265) is a `@computed_field` that reads the pinned, **server-managed** reserved tag via
  `self.tags.get(ARCHIVE_WORKSPACE_PATH_TAG_KEY)` and calls
  `conversation_repositories(selected_repository, selected_branch, git_provider, additional_repositories, working_dir)`
  (`app_conversation/additional_repositories.py`, sha256 `a8d0bbe3…`; `conversation_repositories`
  def at line 89; the `path=f'{working_dir}/{folder}'` expression at line 106) to build
  `path = f'{working_dir}/{folder}'` — i.e. the per-conversation root subtree.
- The tag itself is **written by the server** at conversation start
  (`live_status_app_conversation_service.py`, sha256 `9f4f1596…`, line 1124:
  `tags[ARCHIVE_WORKSPACE_PATH_TAG_KEY] = working_dir`) and is a **reserved key** callers cannot
  set/delete (`RESERVED_TAG_KEYS`, `app_conversation_models.py` line 86).
- It is exposed in the **live** Cloud V1 API: `AppConversation.repositories` →
  `ConversationRepository.path` = *"Absolute path of the folder in the sandbox"*, returned by
  `GET /api/v1/app-conversations` and `GET /api/v1/app-conversations/search` (live OpenAPI
  `1.91.0`, sha256 `f0f4d4e9…`).

So the **tag→root resolution** is **EXISTING + VERIFIED (shipped)** — r8's classification of the whole
read as "NEW + UNVERIFIED" was **incorrect**. The read is nonetheless **not sufficient** for the write:
it returns a **path string**; it does **not** establish that the path is **authorized** as a delivery
destination, **immutable**, **correctly scoped** to this principal/operation, or **safe against
symlink/TOCTOU**. **That** binding is the genuinely new part.

**Required provenance contract (proposed; U-12 — scoped to the binding).** The Cloud MUST resolve the
conversation's workspace root from an **authoritative, identity-bound** source, and MUST NOT accept a
root that is only "absolute" or merely "resolves". The contract:

| Requirement | Detail |
| --- | --- |
| **Authoritative source** | the pinned `archiveworkspacepath` tag (**server-written** at conversation start; the reader exists — see above) **or** an **agent-server** query returning the runtime's own `workspace.working_dir`. **Not** `sandbox_spec.working_dir`. |
| **Identity binding (NEW — U-12)** | the resolved root MUST be bound to the intended `(principal, conversation_id, operation_id)`; the op's `conversation_id` and principal MUST match the conversation that owns the root. **No pinned primitive binds this tuple to the upload operation** — this is the new capability. |
| **Write-authorization (NEW — U-12)** | the existing read returns a path; it does **not** authorize writing there for this operation. The delivery MUST be authorized (principal owns the conversation; the operation belongs to it) **before** any write. |
| **Write-authority** | the tag is a **server-managed reserved key** (callers cannot set/delete it via the public API); the root's authority is the server's, not the caller's. |
| **No absolute-path trust** | being absolute, or `resolve()`-ing, is **not** evidence of identity, authorization, immutability, or scope; the root is trusted only via the binding above. |
| **Grouping awareness** | the root is the **per-conversation nested dir** under any non-`NO_GROUPING` strategy; the proposal MUST NOT assume the bare base. |
| **Fail-closed** | if the authoritative source or the binding cannot be established, the write MUST NOT proceed (no fallback to a guessed/base path). |

**Classification (r9, R8-2).** The pinned source establishes that (a) `_get_agent_server_context` does
**not** carry the per-conversation root, (b) the grouped path exists and is pinned in the
`archiveworkspacepath` tag, (c) the tag is a server-managed reserved key, and (d) a **Cloud-side read of
the per-conversation root already exists and ships** (`AppConversationInfo.repositories`, live via
`AppConversation.repositories.path`). What the pinned source does **not** establish is a **Cloud-side
verification of the identity/authorization binding** — i.e. that the resolved root is bound to the
intended `(principal, conversation_id, operation_id)` and authorized for the write. Therefore **only
that binding** is classified **NEW upstream capability (U-12)**; the tag→root read is **existing**.
Until U-12 is implemented and independently verified, the delivery write MUST fail closed. (The r8
wording — that "no single Cloud-side read of the per-conversation root exists" — is **withdrawn**.)

### 5.16 Correlation and observable rejection (r4, M-4; tightened r5, M-4b)

**Problem.** A validation failure may occur **before** a server `operation_id` exists (e.g. malformed
multipart, missing `file`, over-limit size on the first read, unsupported type), making `rejected`
unobservable — the same defect class r3 removed for `uploading`.

**Chosen contract (coherent with the state machine, §5.9).**

1. The caller **MUST** send a **`client_operation_id`** (§5.4) — a client-generated UUID. It is
   echoed in **every** response. **Validation:** it must be a well-formed UUID; a malformed value is
   a `422 validation_error` (pre-operation, no `operation_id`).
2. **Server-side op row before staging:** the server **durably creates** the operation row (and its
   server `operation_id`) **before** it stages bytes. Therefore a rejection that happens **at or
   after** row creation is reported as a **terminal `rejected`** operation, queryable by
   `operation_id` — `rejected` is **observable**.
3. **Pre-operation rejection** (before any row exists) returns a **structured error**:
   `{ "error": { "code": "…", "client_operation_id": "…", "message": "…" } }` with **no**
   `operation_id`. The caller correlates it by `client_operation_id`. The error body contains
   **no internal paths, credentials, or sensitive details** (only a code + a safe message).

**Uniqueness and duplicate handling (r5, M-4b).** The correlation key is
**`(principal, conversation_id, client_operation_id)`** — unique **per principal+conversation**
(not globally). Two cases:
- **Same key, same payload** (same file set + `sha256`): treated as the **same operation** — the
  server returns the **existing** `operation_id` (idempotent; safe retry). This is the intended
  retry-safety behavior.
- **Same key, different payload:** a **conflict** ⇒ **`409 client_operation_id_conflict`** (§5.8);
  the server does **not** silently create a second operation or silently return the first.
- **Different key, same bytes:** the server may still dedupe byte-identical files by `sha256`
  (§5.6) within a bounded window, returning the prior `file_id` — this is **not** a correlation-key
  collision.

**Guarantees (now unconditional).** Because `client_operation_id` is **required**, **every**
submitted operation has an unambiguous correlation key (server `operation_id`, else the echoed
`client_operation_id`). A validation error carries a **distinct class** from an unknown remote
outcome (`500 internal_error` / timeout ⇒ reconcile via status; a `4xx` validation error is a
**definite** rejection). Rejected files are **never** treated as pending or consumed (they are
terminal and not `delivered`). **Alternative considered:** a fully client-generated id — rejected
because it shifts collision/idempotency handling onto the client and weakens the server's
reconciliation key; the hybrid (client id **required** + echoed, server id when a row exists) is
chosen.

---

## 6. Threat model

For each threat: **attacker capability · vulnerable boundary · required mitigation · test evidence
needed**. (This covers the task's required list.)

| ID | Threat | Attacker capability | Vulnerable boundary | Required mitigation | Test evidence needed |
| --- | --- | --- | --- | --- | --- |
| T-01 | **Unrestricted command execution** | Bot (or stolen bot credential) calls `POST /api/bash/execute_bash_command` | broad agent-server key | Upload op must **not** use/return the agent-server key; scoped op with no exec capability | Op cannot reach any bash route; no key in responses/logs |
| T-02 | **Cross-user upload** | Authenticated user A uploads into user B's conversation | Cloud authorization | Bind op to caller principal + owned conversation; 403 otherwise | A→B upload returns 403 |
| T-03 | **Cross-conversation upload** | Client supplies another conversation's id | destination binding | Server resolves destination from the authorized `conversation_id`; no client host/URL | Op for conv X never writes to conv Y |
| T-04 | **SSRF** | Malicious/erroneous `conversation_url`/redirect/host | bot→runtime hop | **Eliminate the bot→runtime hop**: Cloud resolves and calls the runtime server-side (as for `git/changes`) | No client-supplied host accepted; only fixed Cloud origin used |
| T-05 | **Arbitrary path write** | Client supplies absolute `path` | upload `path` param | No client path at all; server generates storage path | Request schema has no `path`; rejected if provided |
| T-06 | **Path traversal** | Filename `../../etc/x` | storage name | Ignore client filename; server-generated name; normalize + confine | Traversal filename cannot escape base dir |
| T-07 | **Symlink attack** | Pre-existing symlink at destination | filesystem | `open(O_NOFOLLOW)` / `lstat` checks; confine with `resolve().is_relative_to(base)` | Symlink at target is rejected |
| T-08 | **Oversize / resource exhaustion** | Multi-GB upload or many files | size/count limits | Server-enforced per-file, total, and count limits; reject before write | 413 at limit; count cap enforced |
| T-09 | **Malicious file content** | Polyglot/executable content | type policy | Magic-byte sniff + declared-type cross-check; policy reject list | Spoofed type rejected |
| T-10 | **Credential leakage** | Key echoed in logs/errors/DB/JSON | logging & errors | Never log/return the key; redaction; scoped op avoids the broad key entirely | Key absent from logs and all responses |
| T-11 | **Replay / duplicate upload** | Re-send same request | idempotency | `Idempotency-Key` + `sha256` dedup; status endpoint | Duplicate create yields one op |
| T-12 | **Ambiguous remote outcome** | Timeout after possible acceptance | reconciliation | Status endpoint + operation id; **no blind retry**; preserve until terminal | Injected timeout ⇒ `unknown` → status resolves |
| T-13 | **Unauthorized cleanup** | Client deletes another op's files | cleanup | Server-driven retention/cleanup only; no client delete endpoint | No client route can delete another op's files |
| T-14 | **Race conditions / restarts** | Concurrent ops / server restart mid-upload | operation state | Durable operation state; monotonic states; idempotent create; restart-safe reconciliation | Restart mid-upload leaves a reconcilable op |
| T-15 | **Ownership/isolation leak** | Listing another user's attachments | list endpoint | Scope list to authorized conversation + principal | Cross-user list returns nothing/403 |
| T-16 | **Cross-conversation reference access (r4, H-1)** | Caller presents another conversation's `stored_path_ref` at delivery | ref resolution | Ref is bound to `(conversation_id, principal)`; resolution mismatch ⇒ **403** | Ref for conv X cannot deliver into conv Y |
| T-17 | **Delivered-path traversal / symlink (r4, H-1)** | Attacker-controlled display name or a pre-existing symlink at the delivered path | materialization write | Server-generated path; `client_filename` sanitized to a display name only; `O_NOFOLLOW` + `O_CREAT\|O_EXCL`; `resolve().is_relative_to(base)` | Traversal/symlink at delivered path rejected |
| T-18 | **Inert-token false success (r4, H-1; corrected r5, H-1a; corrected r6, N-1; trust pinned r7, R6-2)** | System reports success while the agent cannot read the content — including a **failed** read, a **failed terminal read that is non-error**, or an **agent-forged** acknowledgment | delivery contract | `delivered` requires materialization **and** the **new U-3 successful *content*-read** signal (F6b) from a **trusted, non-agent issuer** (§5.15.1); an inert token, a bare `ActionEvent` (F4), a correlated **non-error** observation (F6a), an `AgentErrorEvent`, or an **agent/tool-emitted acknowledgment** never yields `delivered` | A non-readable upload — a failed read (including a non-error failed terminal read) — or an agent-forged ack never reaches `delivered` |
| T-19 | **Premature deletion (r4, M-3; extended r5, H-1a; corrected r6, N-1; corrected r7, R6-1; refined r8, R7-1; precision r9, R8-1)** | Bytes reclaimed before the agent **successfully** read them, **or the workspace copy deleted while the agent still needs it** | retention sweep | Deletion of the **staging** copy only on `delivered` (**U-3**) / `expires_at` / `rejected` / `failed`; never on a proxy `2xx`, `consumed_at`, a **failed read** (F4), or a **non-error** observation (F6a). **r7 (R6-1): the workspace-materialized copy is NEVER reclaimed at `expires_at`** — only on end-of-use (F7, unmodeled) or **physical workspace removal** (sandbox/pod teardown; **not** conversation archive/delete — r8, R7-1) (§5.10.1) | Sweep cannot reclaim a file the agent still needs; a materialized file survives `expires_at` **and conversation archive/delete** |
| T-20 | **Duplicate delivery (r4, M-1/H-1)** | Retried delivery after an ambiguous outcome | delivery idempotency | Delivery keyed on `(operation_id, file_id)`; no second file | Retry yields one delivered file |
| T-21 | **Correlation-id collision (r5, M-4b)** | A caller reuses a `client_operation_id` for a **different** payload, or omits it, to make a rejection ambiguous | create contract | `client_operation_id` **required**; uniqueness scoped to `(principal, conversation_id)`; same key + different payload ⇒ **409 `client_operation_id_conflict`** (§5.16) | No operation is unidentifiable; no silent second op |
| T-22 | **Agent-forged read acknowledgment (r7, R6-2)** | The agent (or a tool/prompt it controls) emits an event claiming a complete read, to trigger `delivered` and reclaim | U-3 evidence source | U-3 MUST be issued by a **trusted, non-agent** service-side component with **authenticated provenance** and **exact content binding** (§5.15.1–§5.15.3); an agent/tool-emitted event is **never** evidence | An agent-emitted "read" event never sets `delivered` |
| T-23 | **Torn/lagging replica read (r7, R6-3)** | A stale/torn read of the Cloud `events/search` **replica** hides a later error event (false positive) | evidence consistency | Event-based evidence MUST come from a **quiesced** source or an **agent-server** re-verify (U-10, §5.15.4); the replica is **not** authoritative | A torn replica read never sets `delivered` |
| T-24 | **Workspace-copy deletion on expiry (r7, R6-1; refined r8, R7-1; precision r9, R8-1; scoped r10, R9-1)** | The 15-minute deadline (or **any operation-scoped** timer) deletes the materialized workspace copy the agent still needs; **or** the two timer kinds (operation `expires_at` vs infrastructure sandbox lifecycle) are **conflated** | lifecycle | The workspace copy is reclaimed **only** on end-of-use (F7, unmodeled) or **physical workspace removal** (sandbox/pod teardown — *modeled* for managed backends, *delegated to runtime-api* for the Cloud backend; **not** an F7 signal); **never** at the **operation's** `expires_at`; **never** on conversation archive/delete (§5.10.1, r8/R7-1). **r10 (R9-1):** a **separate** infrastructure timer (the Enterprise sandbox lifecycle, `delete_after_seconds`) **may** remove the sandbox **and its workspace** in governed environments; it is **distinct** from the operation's `expires_at` and **must not** be conflated with it; it does **not** prove agent use ended | `expires_at` never removes the agent's file; neither does conversation archive/delete; the two timer kinds are never conflated |
| T-25 | **Workspace-root mis-resolution / cross-conversation write (r8, R7-2; corrected r9, R8-2)** | The Cloud resolves the write root from a source that carries the **ungrouped base** (or a stale/other conversation's path), so a delivery is written outside the intended conversation subtree, or the identity check compares against the wrong value | materialization destination resolution | Resolve the root from the **authoritative** source (`archiveworkspacepath` tag, or an agent-server query) and **bind** it to `(principal, conversation_id, operation_id)` (§5.15.6 / U-12); **fail closed** if the binding is unavailable; **never** trust a path for being absolute/resolvable. **r9 (R8-2):** the **tag→root read already ships** (`AppConversationInfo.repositories` → `conversation_repositories`; live `AppConversation.repositories.path`); only the **identity/authorization binding** is new — the shipped property does **not** by itself prove the path is authorized, immutable, or symlink/TOCTOU-safe | A write whose root is not identity-bound to the intended conversation does not proceed |

---

## 7. Upstream implementation plan (for OpenHands maintainers)

> **Not implemented here.** Component/file names below are **verified from source** at the pinned
> SHAs (§2.1); everything else is a plan. **Corrected in r2:** the plan now **reuses** the existing
> conversation-bound, workspace-confined route instead of proposing a new confined endpoint.

### 7.0 Minimum required upstream changes + reuse map

**Answers to the seven reassessment questions (task §4):**

1. **Can the existing conversation-bound Agent Server upload route be safely reused behind a Cloud
   authorization layer?** — **Yes, with additions.** It already provides conversation binding and
   workspace containment. What must be added around it: a scoped credential, server-side destination
   resolution, size/type/count limits, and operation state. Reuse the route; do not rebuild it.
2. **What exact authorization checks are missing?** — (a) a credential scoped to one conversation +
   one principal (not the server-wide key); (b) an ownership check that the caller may act on the
   conversation (the Cloud already has this for its read routes); (c) assurance that the upload
   credential grants **no** command-execution and **no** workspace read.
3. **Can Cloud resolve the correct runtime and conversation without accepting arbitrary client
   URLs?** — **Yes, for the runtime endpoint and key.** `_get_agent_server_context(conversation_id, …)`
   already resolves conversation → sandbox → `AGENT_SERVER` exposed URL → `session_api_key` from the
   **server side**. The client sends only the conversation id; the origin never comes from the client.
   **r8 (R7-2); corrected r9 (R8-2):** it does **not** resolve the conversation's **workspace root** (it
   exposes only `sandbox_spec.working_dir`, the ungrouped base) — the workspace root must come from the
   `archiveworkspacepath` tag or an agent-server query (§5.15.6 / U-12), and the tag→root **read
   already exists** (`AppConversationInfo.repositories`); only the **identity/authorization binding** is
   new work.
4. **Can the Cloud layer issue a short-lived, conversation-scoped capability?** — **Yes** (new work).
   The Cloud can mint a per-operation capability bound to (principal, conversation) and use its own
   server-side hop; the caller never sees the agent-server key.
5. **What additional filesystem validation is required beyond existing workspace containment?** —
   Server-side destination resolution (no client `path`), per-file/total/count limits, magic-byte
   type policy, and symlink/TOCTOU hardening (`O_NOFOLLOW`, no-follow + create-with-`O_EXCL` under the
   confined base). Containment itself is already enforced (`resolve().is_relative_to(workspace_root)`).
6. **What durable operation state is required for reconciliation?** — Rows keyed by
   `operation_id` holding (conversation, principal, state, files, `sha256`, timestamps, `expires_at`,
   idempotency key) with **monotonic** transitions, so a timeout/restart is always resolvable via the
   status endpoint.
7. **Which existing components can be reused?** — see the reuse map below.

**Reuse map — do NOT rebuild these (they already exist):**

| Existing capability | Where (source-verified) | Reuse how |
| --- | --- | --- |
| Conversation binding + workspace containment | `runtime_router.py::create_runtime_router` / `bind_local_conversation_runtime` (`resolve().is_relative_to(workspace_root)` → 422) | Call the existing scoped route; do **not** add new containment code |
| Server-side runtime resolution + hop | Cloud `app_conversation_router.py::_get_agent_server_context` + `_proxy_git_runtime_call` (+ `/file`, `/files` routes) | Same pattern for the upload op; the agent-server key stays server-side. **r8 (R7-2):** this helper resolves the **runtime endpoint + session key**, **not** the workspace root (only `sandbox_spec.working_dir`, the ungrouped base) — the root comes from the `archiveworkspacepath` tag or an agent-server query (§5.15.6 / U-12) |
| Conversation ownership / user scoping | Cloud `app_conversation_router.py`: `UserContext` (`depends_user_context()`) is used on create / `/stream-start` / `/download`; the runtime-proxy read routes rely on the user-scoped `AppConversationService` | Reuse the same caller-scoping mechanism for the attachment op (return 403 when the caller does not own the conversation) |
| Session-key delivery to the runtime | `sandbox.session_api_key` (never exposed to third parties by the new op) | Reuse internally; do not return it |
| Capability negotiation | `server_details_router.py` capability `conversation_runtime_routes_v1` | Keep; the scoped route already advertised |
| File write mechanics | `file_router.py::_upload_file` (streaming, 8 KiB chunks, dir/parent guards) | Extend with limits + destination resolution; keep the streaming core |

**Net new upstream work (minimum):** a Cloud attachment service + routes; a scoped credential;
server-side destination generation; limit/type enforcement + symlink hardening; durable operation
state + status endpoint; **r4/r5/r6 (H-1/M-2/M-3/N-1/N-3):** the **agent-readable delivery contract**
(§5.14; **r5:** partly composable, partly new — §5.14.1), a **durable *active-conversation*
message-accept step** (§5.15 U-2; **r6, N-3:** the existing `pending-messages` route is **start-only**
⇒ a running-conversation accept is new work), and the **successful-content-read signal** (§5.15 U-3;
**r6, N-1:** the signal is **new** — existing primitives are insufficient). **r8 (R7-1/R7-2);
corrected r9 (R8-1/R8-2):** the **workspace-root identity/authorization binding** capability (§5.15.6
U-12 — the **tag→root read already exists** via `AppConversationInfo.repositories`; only the
**binding** is new), and a **C2 retention bound** if the owner decides on one (Q18 — **no** primitive
is invented here; today **no** conversation-scoped event reclaims C2, and the physical-removal path is
the sandbox-lifecycle teardown, **modeled** for the managed backends and **delegated to runtime-api**
for the Cloud backend). Everything else is reuse.

### 7.1 Components/files to change

| Layer | File (verified path) | Change |
| --- | --- | --- |
| Cloud (sandbox-server) | `openhands/app_server/app_conversation/app_conversation_router.py` | Add `POST/GET …/{id}/attachments[/{op}]` routes; **reuse** the existing `_get_agent_server_context` + `_proxy_git_runtime_call` pattern to reach the runtime **server-side** with the sandbox key (never exposed to the caller) |
| Cloud | new module e.g. `openhands/app_server/app_conversation/attachment_service.py` | Operation state machine, persistence, retention sweep, audit events, scoped capability; **r4/r5/r6:** ref **resolution + authorization** (§5.14.2), the **durable *active-conversation* message-accept** step (M-2; **r6, N-3:** `pending-messages` is **start-only** ⇒ new work — §5.15 U-2), the **`delivered`** transition from the **new successful-content-read signal** (**r6, N-1:** U-3; existing primitives are insufficient — §5.14.2 step 6), and **r8 (R7-2); corrected r9 (R8-2):** the **workspace-root identity/authorization binding** (U-12) — the root is **read** from the existing `archiveworkspacepath` tag reader (`AppConversationInfo.repositories`) or an agent-server query, and the **new** work is to **bind** it to `(principal, conversation_id, operation_id)` and **authorize** the write (§5.15.6) |
| Cloud | `openhands/app_server/app_conversation/app_conversation_models.py` | New request/response models; optionally expose an opaque `stored_path_ref`; **r4/r5:** expose `delivered_path`, `delivered_at`, `read_confirmed_at`, and the **required** `client_operation_id` (§5.9) |
| Agent Server | `openhands/agent_server/file_router.py` | **Extend** the existing upload handler with (a) server-side destination resolution (ignore any client `path`), (b) size/total/count limits, (c) type policy, (d) symlink/TOCTOU hardening. **Keep** the existing conversation-bound route + `bind_local_conversation_runtime` containment — do **not** add a parallel unconfined path. **r4:** add a **server-to-server delivery** route (U-1) that materializes a resolved ref at a server-generated `delivered_path` under the confined base |
| Agent Server | `openhands/agent_server/api.py` / `dependencies.py` | Internal auth for the server-to-server store **and delivery** calls (not the public session key) |

### 7.2 Authorization changes

- Introduce a **narrow** authorization path for attachments (Cloud principal → one conversation),
  distinct from the server-wide session key.
- The agent-server store call must be reachable **only** by the Cloud's server-side call (internal
  credential / network boundary), never by an arbitrary client holding a session key.
- **Do not** remove or weaken the existing `bind_local_conversation_runtime` containment or the
  existing session-key check on the legacy route without the upstream deprecation runway (§11).

### 7.3 API and schema changes

- Additive Cloud routes (§5.2) and models; no changes to existing `send-message` or file-read routes.
- Optional additive `AppConversation` fields if a `stored_path_ref` must be surfaced; additive only.
- **r4 (H-1/M-4):** the status/create models add `client_operation_id`, `delivered_path`,
  `delivered_at`, and the `delivered` state (§5.9/§5.16); a **server-to-server delivery route**
  (§5.15 U-1) is added on the Agent Server. If the maintainers instead extend `send-message`
  (owner decision Q14), the message model must gain a **file-reference** content block — a
  **breaking/additive** change to the public message schema, which is why design A (materialization)
  is recommended.

### 7.4 Filesystem safety requirements (delta over existing containment)

**r5 (S-3) — required guarantees for delivered files (explicit list).** These are **proposal
requirements**, not implemented here.

- **Already present (reuse):** workspace-root containment on the scoped route
  (`resolve().is_relative_to(workspace_root)` → 422) and directory/parent-type guards (400).
- **To add:** server-generated destination under a fixed workspace subdir with **no** client path;
  symlink/TOCTOU hardening (`O_NOFOLLOW`; create with `O_CREAT|O_EXCL` under the confined base);
  server-enforced size, total, and count limits; magic-byte type validation.
- **r4 (H-1) delivered-path hardening:** the **delivered** write re-applies the same rules —
  server-generated path, sanitized display name only, `O_NOFOLLOW` + `O_EXCL`,
  `resolve().is_relative_to(workspace_root)` re-checked immediately before the write (TOCTOU-safe).
- **r5 (S-3) atomic publication:** the delivered bytes are written to a **server-generated temporary
  file in the same directory** and published with **`os.replace`** (atomic rename). A crash therefore
  never leaves a truncated `delivered_path`; a partially written temp file is removed on the
  `failed`/`expired` transition (§5.10).
- **r5 (S-3) permissions/ownership:** the published file's **mode/ownership MUST be readable by the
  agent's runtime user** (the same user the agent-server tools run as). The concrete uid/gid/mode is a
  deployment parameter; whether the default already satisfies it is **UNVERIFIED** (owner/implementation
  item, §12 Q14). The contract requires the check, not a specific numeric mode.
- **r5 (S-3) partial-write cleanup:** any partial **staging** or **delivered** temp artifact is
  removed on `failed`/`expired` (bounded by `expires_at`), never left visible as a valid file.
- **r5 (S-3) cross-conversation isolation:** the write happens under the **resolved** conversation's
  workspace root only; the operation's `conversation_id` must match the resolved workspace before any
  write (§5.14.2 step 3); a mismatch is rejected (no write). **r8 (R7-2):** the root itself MUST come
  from the **authoritative, identity-bound** source (`archiveworkspacepath` tag or an agent-server
  query; §5.15.6 / U-12) — **not** from `sandbox_spec.working_dir`; a path is **not** trusted merely
  for being absolute/resolvable. If the binding cannot be established, the write **fails closed**.
  **r9 (R8-2):** the tag→root **read already exists** (`AppConversationInfo.repositories`; live
  `AppConversation.repositories.path`); the **new** work is the **identity/authorization binding** of
  that root to `(principal, conversation_id, operation_id)` — the existence of the read does **not**
  authorize or identity-bind the write.

### 7.5 Operation-state persistence and reconciliation logic

- Persist operation rows (`operation_id`, `client_operation_id`, conversation, principal, state,
  files, timestamps, `expires_at`, idempotency key, `delivered_path`, `delivered_at`,
  `read_confirmed_at`) in the Cloud store; monotonic state transitions; restart-safe.
- **Delivery + read evidence (r4, H-1/M-3; corrected r5, H-1a; corrected r6, N-1; corrected r7,
  R6-2/R6-3):** persist the
  `delivered` transition **only** when the content is **materialized in the workspace** *and* a
  **successful *content* read (F6b)** is established — which **no existing primitive proves** (r6,
  N-1) — **and** the evidence is issued by a **trusted, non-agent** component (§5.15.1) and read from
  a **quiesced** source (§5.15.4). The r5 rule ("an `ObservationEvent` correlated to an `ActionEvent`
  naming `delivered_path`
  with a **non-error** result") is **withdrawn as insufficient** (a failed **terminal** read is
  non-error). `delivered` now requires the **new explicit structured read acknowledgment (U-3,
  §5.15)**. A bare `ActionEvent` (F4), a correlated **non-error** observation (F6a), an
  **agent-emitted** event, or the appended
  message alone (F2/F3) is **not** sufficient. This is the **only** success terminal state that
  permits reclaim of the **staging** copy (the workspace copy persists — **beyond the life of the
  conversation** today, since no conversation-scoped event reclaims it — and is **never** reclaimed at
  `expires_at` — §5.10.1/§5.10.4, r7 R6-1 / r8 R7-1).
- **Message-accept marker (r3, R2-6; corrected r4, M-2; made coherent r5, M-2-res; corrected r6,
  N-3):** `consumed_at`
  is a **message-side** marker — it is set **iff** the Cloud has a **durable record** that it accepted
  a reference message (§5.9.1). **It is NOT set by the current `send-message` route** (a thin proxy
  with no durable write). The Cloud's **existing durable** `POST /api/v1/conversations/{id}/pending-messages`
  route (SQL commit) **can** set it — **but that route is drained only at conversation *start*, so it
  cannot serve the P0 target (an already-running conversation, r6, N-3)**; a durable accept for a
  **running** conversation (on `send-message` or elsewhere) is **NEW** work (§5.15 U-2). `consumed_at`
  **never authorizes deletion**
  (M-3): cleanup is driven by `delivered`/`expires_at` (§5.10). *(This corrects the r4 §7.5 wording
  that said `consumed_at` is set when `send-message` "durably accepts" — the r4 self-contradiction.)*
- Reconciliation: status endpoint reads durable state; retention sweep finalizes expired ops and
  reclaims staged files **only after** a terminal state (§5.10). The sweep must not reclaim bytes
  while `accepted` or while `stored` (delivery unconfirmed) before `expires_at`.

### 7.6 Test plan

- See §10 (upstream tests).

### 7.7 Migration and backward compatibility

- Purely additive; existing clients and routes unaffected. The existing **conversation-bound** route
  (`POST /api/conversations/{runtime_conversation_id}/file/upload`) is **reused and unchanged** in
  its contract; the new Cloud op wraps it. The existing **legacy** unconfined `/api/file/upload` is
  **not** removed by this proposal (removal would require the upstream deprecation runway — §11); the
  new path is the **supported** one for third parties.

### 7.8 Security review requirements

- Independent security review of: authorization scoping, the server-side runtime hop (SSRF),
  filesystem confinement/symlinks, size/type enforcement, idempotency/reconciliation, and audit
  completeness. Required **before** the capability is documented as supported.

---

## 8. OpenHandBot integration contract (future consumption — not implemented now)

> The integration below is **not** implemented in this task. It describes how OpenHandBot **could**
> consume the future capability while preserving every P0 behavior and reliability guarantee.

### 8.1 Preserved invariants (mandatory)

| # | Invariant | Preserved by |
| --- | --- | --- |
| I1 | Existing conversation identity (never create a new conversation) | use the stored `conversation_id`; never call `start_conversation` |
| I2 | One SQLite owner | no second DB; new batch state is rows in the existing DB |
| I3 | One bot process | no new worker/scheduler; reuse existing workers |
| I4 | Fixed 15-minute deadline from the **first** file | `T0` persisted at first file; never extended |
| I5 | Durable pending batches | persisted batch + item rows |
| I6 | Multiple files join the same batch without extending the deadline | append items; `T0` unchanged |
| I7 | Accompanying text required before sending | files alone never dispatch |
| I8 | No sending files without accompanying text | dispatch only on text within deadline |
| I9 | Ownership and conversation isolation | reuse the existing ownership checks |
| I10 | Preserve files while the remote outcome is unknown | state machine keeps `uncertain`; **r4:** server keeps **staging** bytes until `delivered`/`expires_at`; **r7 (R6-1):** the **workspace-materialized copy is retained regardless** (§5.10.1) |
| I11 | No blind retry after ambiguous outcomes | reconcile via status endpoint |
| I12 | Cleanup only after confirmed terminal evidence (r4, M-3; r5, H-1a/M-3b; r6, N-1; r7, R6-1; refined r8, R7-1; precision r9, R8-1) | delete **staging** bytes **only** on **`delivered`** (materialized + **F6b successful *content* read** confirmed via **U-3**, §5.14.2 step 6) or `expired`/`rejected`/`failed` (§5.10); **never** on `consumed_at` alone; **never** on a bare `ActionEvent` or a non-error observation; unconfirmed **or unsuccessful** delivery ⇒ treated as not delivered. **r7 (R6-1): the workspace-materialized copy is NEVER reclaimed by `expires_at`** — only on end-of-use (F7, unmodeled) or **physical workspace removal** (sandbox/pod teardown; **not** conversation archive/delete — r8, R7-1) (§5.10.1) |
| I13 | Existing Telegram acknowledgement + durable delivery guarantees | unchanged handlers/outbox; **r4 (M-1):** server reclamation is **decoupled** from the Telegram ack (§8.3); **r7 (R6-1):** the 15-minute wait-for-text deadline is **never** a content-deletion authorization (§5.10.0) |
| I14 | Agent can actually **read** the uploaded content (r4, H-1; r6, N-1; r7, R6-2/R6-4) | delivery materializes the file in the workspace at an **absolute** `delivered_path` (§5.15.5); the bot references that concrete path; the operation reaches `delivered` only with the **new U-3 successful-content-read** signal (F6b) from a **trusted, non-agent issuer** (§5.15.1), read from a **quiesced** source (§5.15.4) — never on an attempted read (F4), a mere non-error observation (F6a), or an **agent-emitted** acknowledgment (§5.14) |
| I15 | The delivery destination root is **identity-bound** to the intended conversation (r8, R7-2; corrected r9, R8-2) | the Cloud resolves the conversation's workspace root from the **authoritative** source (`archiveworkspacepath` tag, or an agent-server query for `workspace.working_dir`) and **binds** it to `(principal, conversation_id, operation_id)`; **not** from `sandbox_spec.working_dir`; **fail closed** if the binding is unavailable — a path is never trusted for being absolute/resolvable (§5.15.6 / U-12). **r9 (R8-2):** the tag→root **read** already exists (`AppConversationInfo.repositories`); the **new** work is the **identity/authorization binding**, which no pinned primitive provides |

### 8.2 Integration steps and their upstream prerequisites

| Step | OpenHandBot action | Upstream prerequisite |
| --- | --- | --- |
| S1 | On first file: create a local batch row, persist `T0` (batch deadline), reply «في انتظار أوامرك» | none (local) |
| S2 | On more files: append items; do **not** move `T0` | none (local) |
| S3 | On text within deadline: **durably** record dispatch intent + `Idempotency-Key`/`client_operation_id` **before** any external call (§8.3) | none (local) |
| S4 | `POST …/attachments` (multipart) with the bot's **Cloud** bearer + `Idempotency-Key` + `client_operation_id` | **§5.2 create op**, **§5.3 narrow auth**, **§5.7 validation**, **§5.8 errors**, **§5.16 correlation** |
| S5 | Persist the returned `operation_id`; treat timeout/5xx as `uncertain` (never blind-retry) | **§5.6 operation id**, **§5.9 status endpoint** |
| S6 | On `uncertain`: `GET …/attachments/{operation_id}` until terminal (or expiry) | **§5.9 reconciliation** |
| S7 | On `stored`: send the message with the text + the concrete **`delivered_path`** (the delivery contract materializes the file, §5.14); the Cloud sets `consumed_at` only on a **durable** accept — **r6 (N-3): the existing `pending-messages` route is start-only and does NOT serve a running conversation**, so today no durable active-conversation accept exists (§5.9.1) | **§5.14 delivery contract**, **§5.9 opaque ref**, **§5.9.1**, existing `send_message` |
| S8 | On `rejected`/`failed`: clear staged files, notify user, no retry storm | **§5.9 terminal states**, **§5.10 cleanup** |
| S9 | On deadline expiry with no text: delete staged files, mark batch `expired` | **§5.10 retention**, local sweep |
| S10 | On restart: reconcile every `dispatching`/`uncertain` batch via status endpoint; never assume delivery | **§5.9**, **§8.3**, existing recovery hooks |

**Prerequisite summary (explicit):** S4 needs create-op + narrow auth + validation + error +
correlation; S5–S7 need operation id + status endpoint + opaque `stored_path_ref` + the **§5.14
delivery contract**; S8–S9 need terminal-state semantics + retention; S10 needs durable operation
state. **Without all of these the integration must not be built** (a timeout would be unresolvable,
and the bot would risk blind retries — exactly the failure mode the current design avoids).

### 8.3 Durable ordering and crash-window analysis (r4, M-1; integration boundary clarified r5, S-2)

This resolves M-1: the ordering between the **durable pending-batch state**, the **durable
dispatch/consumption intent**, the **Telegram update-outcome record**, the **acknowledgement
boundary**, the **outbox dispatch**, and the **Cloud/Agent-Server interaction** — reconciled with the
OpenHandBot ack architecture (`OHB2-TELEGRAM-ACK-ARCHITECTURE-ADR.md`) and the outbox at-most-once
semantics (`bot/outbox.py`). **No exactly-once claim is made.**

**r5 (S-2) — the integration boundary is explicit, not assumed.** The **current** OpenHandBot outbox
(`bot/outbox.py`) dispatches **prompt text only** (`client.send_message(conversation_id, text)`); it
has **no attachment/upload item type**, and there is **no** existing code path that uploads bytes.
Therefore the attachment dispatch **requires** either (a) a **new outbox payload capability** (a
distinct item kind carrying the operation reference/`delivered_path`) or (b) **another explicitly
approved** integration mechanism. This proposal **does not assume** attachment support already
exists; it is recorded as upstream/integration work (§5.15 U-9). The durable-ordering rule below is
unchanged by this: the **intent** is durable before the external call; **which** component performs
the dispatch is an integration decision (owner, §12).

**Durable ordering (the rule).** Within one Telegram update handling the bot MUST, in this order:
(1) durably persist the batch/item rows and, on text, the **dispatch intent** (a row that is part of
the **same SQLite transaction** as the update's `processed_updates.outcome`); (2) only then call the
Cloud; (3) record the remote outcome (`stored`/`rejected`/`failed`/`uncertain`) **and** the outcome
row atomically. The **acknowledgement boundary** advances only over updates with an **ack-eligible**
outcome (ADR §18.1: `durable_completed`, `durable_intent_recorded`, `explicitly_ignored`,
`duplicate_completed`); an **ambiguous remote result** is `partial_or_unknown` ⇒ **not** eligible ⇒
the boundary **stops** there (fail-closed). This is the existing behavior; r4 adds the requirement
that the **dispatch intent is durable before the external call** so a crash cannot lose the batch.

**Crash windows (traced).** The batch is **not** lost in any window because the pending batch +
intent are durable before the remote call, and the update is **not** acked until an eligible outcome
exists:

| # | Crash point | What is durable | Ack boundary | Recovery | Safe? |
| --- | --- | --- | --- | --- | --- |
| 1 | Before durable consumption intent | pending batch only; no intent | not advanced | redelivery re-runs the handler; intent written | ✅ no loss |
| 2 | After consumption intent, before Telegram outcome record | batch + intent (one txn); outcome not written | not advanced (no eligible outcome) | redelivery ⇒ `dedupe_update` sees no committed outcome ⇒ re-runs; intent is idempotent | ✅ no loss |
| 3 | After outcome record, before boundary advance | batch + intent + outcome | not advanced | restart resumes from stored boundary; outcome already durable | ✅ |
| 4 | After boundary advance, before dispatch request | all of the above | advanced | the intent + boundary are durable ⇒ the **outbox** worker (or recovery) performs the dispatch exactly as recorded | ✅ no loss (at-most-once) |
| 5 | After dispatch request, before response | intent + `sending` state | advanced (intent eligible) | result is **unknown** ⇒ record `unknown`; **never** auto-retry (at-most-once) | ✅ no duplicate |
| 6 | After remote success, before recording result | remote effect done; local result missing | advanced | local row `sending`; reconciliation (`GET …/attachments/{op}`) reveals `stored`/`delivered`; **no** second upload | ✅ |
| 7 | Restart with unknown remote outcome | intent + `sending`/`uncertain` | advanced | status reconciliation resolves the op; if still `uncertain` at `expires_at` ⇒ surface to the user, never silent retry | ✅ |

**Why server-side reclamation cannot lose the batch (the M-1 fix).** M-1's hazard was that a
Cloud-side `consumed_at`/cleanup could run **ahead** of the bot's durable Telegram ack. r4 removes
that coupling: cleanup is keyed on **`delivered`/`expires_at`** (M-3), **not** on `consumed_at`, and
`delivered` requires the **new U-3 successful-content-read signal** (§5.14, r5 H-1a; r6 N-1) — which
can only happen **after**
the bot's durable dispatch. So the server never reclaims bytes the bot still needs, and the bot never
reports "delivered" before its own durable ack. **If the upstream cannot provide the successful-read
signal (§5.15 U-3), the safe fallback is retention of the staging copy until `expires_at`** (bounded
by the 15-min operation window) **and retention of the workspace-materialized copy for the life of the
conversation** (r7, R6-1) — which is still safe for I12 (§12, Q16/Q18).

**Guarantees requiring upstream support (explicit).** (a) A **durable *active-conversation*
message-accept step** — **NEW** work (M-2, §5.15 U-2; **r6, N-3:** the existing `pending-messages`
route is **start-only** and cannot serve a running conversation) — without a durable accept,
`consumed_at` is not a durable signal and must not be
trusted (and it never authorizes deletion regardless). (b) **Delivery idempotency** keyed on
`(operation_id, file_id)` (U-4) — without it, a retried delivery could create a second file. (c) The
**successful-read evidence** (U-3) — without it, `delivered` cannot be asserted and the fallback
above applies. **No local guarantee is invented for these.**

### 8.4 One fixed batch deadline (r4, M-5)

**Authoritative batch deadline.** The 15-minute deadline belongs to the **pending batch**, not to
individual upload operations. It is:

- **Created** when the **first supported file** of the batch is accepted (the bot persists `T0`),
- **Never extended** by subsequent files or by a later operation's `expires_at`,
- **Shared** by every operation that joins the batch (the bot records which operations belong to the
  batch),
- **Persisted** in the existing SQLite DB (`T0`, same owner) — **not** derived per operation,
- **Consistent across restart** (persisted) and **clock changes** (stored as an absolute UTC instant;
  the client uses the **server** status as authoritative for the operation's own `expires_at`, L-3),
- **Enforced atomically against text arrival** — see below.

**Text/expiry races (explicit).**
- **Text just before expiry:** the bot checks the batch deadline against its persisted `T0`; if text
  arrives with `now ≤ T0 + 15 min`, it dispatches; the operation(s) it references must still be
  `stored`. If an operation already expired server-side, the reference is stale and the Cloud
  rejects it (L-1) ⇒ the bot treats it as expired, **notifies** the user, and does **not** retry.
- **Text and expiry race:** the batch deadline is evaluated **once, atomically** with the dispatch
  intent write (same SQLite transaction); the outcome is either "dispatch" (≤ deadline) or "expired"
  (> deadline) — never both. **Late text cannot revive an expired batch.**
- **Upload started before expiry may finish after it:** an operation accepted before the batch
  deadline may reach `stored` after it; the bot still will **not** dispatch past the batch deadline
  (the batch is expired), and the operation is reclaimed at its own `expires_at`.
- **Expiry exposure:** the operation status exposes its own `expires_at` (§5.9); the **batch**
  deadline is a client-side value (the server has no batch concept) and is reported to the user by
  the bot, not the API.
- **Cleanup waits for terminal evidence:** the server reclaims **staging** copies (C1/C3) only on
  `delivered`/`expired`/
  `rejected`/`failed` (§5.10.1); the **workspace-materialized copy (C2) is never reclaimed by the
  operation's timer** (r7, R6-1; scoped r10, R9-1 — a separate infrastructure timer, the Enterprise
  sandbox lifecycle §5.10.4, may remove the sandbox **and its workspace** in governed environments;
  that is **not** the operation's `expires_at` and **not** an F7 signal); the bot reclaims its local
  staging only after its own terminal batch
  state, and never before reconciliation completes (§8.3).

---

## 9. Required upstream acceptance criteria

1. A third-party caller can upload a file into an **exact existing conversation** using **only** a
   Cloud credential — never an agent-server session key.
2. The upload credential grants **no** command execution and **no** workspace read.
3. The destination is **server-resolved**; the caller supplies **no** host, URL, or absolute path.
4. The server enforces **size, total-size, count, and content-type** limits and **confines** writes
   to a workspace subdir with symlink/traversal protection.
5. Every upload returns a stable **`operation_id`** and is queryable via a **status endpoint**;
   timeouts are reconcilable and **never** require blind retries.
6. Create is **idempotent** under a caller-supplied `Idempotency-Key`.
7. Terminal states are explicit and monotonic; retention/cleanup is server-driven and auditable.
7b. **r3 (R2-6/R2-8); r4 (M-2/M-3) correction; r5 (H-1a/M-2-res); r7 (R6-1); corrected r8 (R7-1); precision r9 (R8-1):**
   the status endpoint
   exposes a **fixed `expires_at`** (never extended by later files). `consumed_at` is a
   **message-accept** marker only (§5.9.1) — **not** durable via the thin-proxy `send-message` **and,
   r6 (N-3), not available for a running conversation via `pending-messages` either (start-only)**.
   It is **never** a deletion authority. Deletion of the **staging/recovery copy** requires
   **`delivered`** (materialized + **F6b successful *content* read** confirmed via **U-3**) or
   `expires_at`; **`expires_at` NEVER reclaims the workspace-materialized copy** (§5.10.1), **and
   neither does conversation archive/delete** — the workspace copy is removed only on end-of-use (F7,
   unmodeled) or **physical workspace removal** (sandbox/pod teardown; **r9, R8-1:** *modeled* for the
   managed backends, *delegated to runtime-api* for the Cloud backend), so **today no
   conversation-scoped event reclaims it** (r8, R7-1).
7c. **r4 (H-1); r5 (H-1a); corrected r6 (N-1); corrected r7 (R6-2/R6-4):** uploaded bytes can be
   turned into **agent-readable content**: the Cloud resolves the ref, **materializes** the file into
   the conversation workspace at a server-generated, **absolute** `delivered_path` (atomic publish;
   readable mode/owner — §5.15.5), and the agent reads it with normal tools; `delivered` is set
   **only** on the **new U-3 successful *content*-read** signal (F6b) **issued by a trusted,
   non-agent component** (§5.15.1) and read from a **quiesced** source (§5.15.4), **never** on an
   attempted read (F4), **never** on a correlated **non-error** observation (F6a — a failed terminal
   read is non-error), **never** on an **agent/tool-emitted** event, and **never** on the appended
   message alone (§5.14). **Until U-3 exists (and its issuer is verified), `delivered` is
   unreachable** and the safe fallback is **staging** retention until `expires_at` **and retention of
   the workspace copy beyond the life of the conversation** (r8, R7-1 — no conversation-scoped reclaim; §5.10.1).
8. Behavior for **ended/deleted conversations** is defined and tested.
9. A **documented, stable** way for a third party to reach the destination exists **without**
   trusting an infrastructure-dependent origin (or the destination is reached server-side only).
10. An **independent security review** signs off on §6 mitigations.
11. **r4 (M-1/M-4/M-5):** (a) the durable-ordering rule of §8.3 is satisfiable (dispatch intent
    durable before the external call; ack boundary fail-closed on ambiguity); (b) **rejection is
    observable** — a `client_operation_id` is echoed, or a server op row is created before staging
    (§5.16); (c) the **batch** deadline (client-side, first file) is distinct from and never extended
    by a per-operation `expires_at` (§8.4).

---

## 10. Tests and verification strategy

### 10.1 Upstream tests (required when implemented — not executed here)

- **Existing-confinement regression (must stay green):** the current
  `tests/agent_server/test_runtime_router.py` assertions — cross-conversation/relative path ⇒ **422**,
  wrong `X-Session-API-Key` ⇒ **401**, scoped upload onto a directory / under a file ⇒ **400**,
  `conversation_runtime_routes_v1` advertised — must remain green after the change.
- **Authorized / unauthorized uploads:** valid principal succeeds; missing/invalid credential ⇒ 401.
- **Conversation ownership:** non-owner ⇒ 403; owner ⇒ 200.
- **Scope isolation:** the attachment credential/operation cannot reach bash/secret/read routes.
- **Invalid destination:** malformed id ⇒ 400; unknown ⇒ 404; archived ⇒ 409.
- **Path traversal:** filename with `../` cannot escape the base dir.
- **Symlink attack:** pre-existing symlink at target is rejected.
- **Oversized files:** per-file and total over limit ⇒ 413; count over limit ⇒ rejected.
- **Unsupported content:** policy-rejected type ⇒ 415; spoofed declared type ⇒ rejected.
- **Duplicate operation identifiers:** same `Idempotency-Key` ⇒ one operation.
- **Idempotent retries:** repeated create is safe.
- **Timeout / connection loss:** client sees `unknown`, status resolves to a terminal state.
- **Server restart:** operation state survives; reconciliation still resolves.
- **Reconciliation after ambiguous outcomes:** status endpoint is authoritative; no blind retry.
- **r3 state-model checks (R2-8/R2-9):** no response ever reports `uploading`; `expires_at` is present
  and constant across a status poll sequence; after `expires_at` no non-terminal state is reported.
- **r4 delivery checks (H-1); r5 corrected (H-1a); corrected r6 (N-1):** a stored ref is **resolved +
  authorized** only for its own conversation/principal (cross-conversation ref ⇒ 403); the file is
  **materialized** atomically at a server-generated `delivered_path` (temp + `os.replace`; readable
  mode/owner); the agent can **read** it; `delivered` is set **only** on the **new U-3 successful
  *content*-read** signal (F6b); a **failed** read (`ActionEvent` + `AgentErrorEvent`/error
  observation, F4) does **not** set `delivered`; **a failed *terminal* read that is non-error
  (`exit_code != 0`, `is_error == false`) does NOT set `delivered`** (the r6 N-1 counterexample); a
  missing/inconclusive evidence signal leaves the op `stored`.
- **r4 correlation checks (M-4); r5 tightened (M-4b):** a **pre-operation rejection** returns a
  structured error echoing the **required** `client_operation_id` and **no** `operation_id`; a
  post-row rejection is a queryable terminal `rejected`; a **same-key/different-payload** create ⇒
  **409 `client_operation_id_conflict`**; a **same-key/same-payload** create ⇒ the **same**
  operation; the two error classes (validation vs unknown-outcome) are distinguishable; error bodies
  leak no paths/credentials.
- **r4 delivery-idempotency checks (H-1/M-1):** a retried delivery keyed on `(operation_id, file_id)`
  does **not** create a second file.
- **r3 consumption-marker checks (R2-6; corrected r4 M-2; made coherent r5 M-2-res; corrected r6
  N-3):** `consumed_at`
  is set **only** on a **durable** message-accept — **not** via the thin-proxy `send-message`, and
  **not** via `pending-messages` for a **running** conversation (r6, N-3: that route is **start-only**);
  it is **never** used to
  authorize deletion; a stale (expired) ref is rejected and sets nothing.
- **r4 cleanup-evidence checks (M-3); r5 extended (H-1a/M-3b); corrected r6 (N-1); corrected r7
  (R6-1); refined r8 (R7-1); precision r9 (R8-1):** the **staging** copy is reclaimed **only** on
  `delivered` or `expired`/`rejected`/`failed`; on `delivered` **only the staging copy** is
  reclaimed; **the workspace-materialized copy is NEVER reclaimed at `expires_at`** and is removed
  only on end-of-use (F7, unmodeled) or **physical workspace removal** (sandbox/pod teardown —
  *modeled* for the managed backends, *delegated to runtime-api* for the Cloud backend)
  — **never** on conversation archive/delete (§5.10.1); a proxy `2xx`, a `consumed_at`, **a failed read
  (F4)**, **or a non-error observation (F6a, including a failed terminal read)** reclaims nothing;
  partial staging **or delivered** temp artifacts are removed on the
  `failed`/`expired` transition.
- **r6 U-3 signal checks (N-1); extended r7 (R6-2/R6-3):** a valid U-3 acknowledgment
  (`read_complete == true`, matching `sha256`/size, no later error event) **issued by a trusted,
  non-agent issuer** sets `delivered`; a **missing/malformed/mismatched/truncated/agent-issued/
  unauthenticated/replayed/stale** acknowledgment leaves the op `stored`; a **later** error event for
  the same action downgrades a prior acknowledgment (⇒ not `delivered`); evidence read from a
  **torn/lagging replica** does not set `delivered` (§5.15.4).
- **r5 state-model checks (S-1):** no response ever reports `uploading` **or `accepted`**; a
  successful create returns `stored`; a failed create returns a definite non-2xx (never a 2xx with
  in-flight staging).
- **Cancellation / cleanup:** expired ops are reclaimed; no client-driven unauthorized cleanup.
- **Cross-conversation / cross-user isolation:** writes never land in the wrong workspace.
- **r8 workspace-root provenance checks (R7-2; corrected r9, R8-2):** the delivery write resolves the
  root from the
  **authoritative** source (`archiveworkspacepath` tag — via the **existing** reader
  `AppConversationInfo.repositories`/`conversation_repositories` — or an agent-server query for
  `workspace.working_dir`) and **binds** it to `(principal, conversation_id, operation_id)`;
  a root that is only "absolute"/resolvable, a stale/other-conversation root, or the **ungrouped
  base** (`sandbox_spec.working_dir`) is **rejected** (fail closed) — §5.15.6 / U-12. The **read** is
  existing; the **binding + write-authorization** is the new part (r9, R8-2).
- **r8 grouping checks (R7-1):** under a non-`NO_GROUPING` strategy, the conversation workspace is the
  **nested** `{base}/{conversation_id.hex}` dir; a **sibling** conversation keeps the sandbox alive;
  conversation archive/delete **preserves** the workspace directory (so C2 is **not** reclaimed by it).
- **r8 replica-path checks (R7-3):** the quiescence requirement is enforced whether the Cloud store is
  fed by the poll loop (no public URL) **or** by webhooks; a torn/lagging read never sets `delivered`.

### 10.2 OpenHandBot integration tests (required once the upstream capability exists)

- Pending-batch creation on first file; `T0` fixed; multiple files do not extend the deadline.
- Text-within-deadline dispatches files + text to the **same** conversation; no new conversation.
- Files without text never dispatch; **non-text messages never trigger sending**.
- **The agent can read the delivered file** at the **absolute** `delivered_path` referenced in the
  prompt (H-1; r7, R6-4); `delivered` is asserted **only** on the **new U-3 successful *content*-read**
  signal (F6b) from a **trusted, non-agent issuer** (§5.15.1); a
  **failed** read — including a **non-error failed terminal read** (`exit_code != 0`, `is_error ==
  false`) — leaves the op `stored` (H-1a; r6, N-1; r7, R6-2).
- **The path handed to the agent is absolute** and openable by the reader without transformation; a
  relative path is **not** accepted (r7, R6-4; §5.15.5).
- Timeout/5xx ⇒ `uncertain`; status reconciliation resolves; **no** second upload (no blind retry).
- **Crash windows (§8.3):** crash before/after intent, after outcome, after boundary advance, after
  dispatch, after remote success — the batch is never lost and no remote effect is blindly repeated.
- **Lifecycle crash/race cases (§5.10.3):** expiry while pending / just after text / outcome-unknown /
  agent-reading; crash before/after the delivery commit; crash between DB cleanup and FS delete; FS
  delete succeeds but DB update fails; delayed U-3 after expiry; delayed event after cleanup; two
  cleanup paths race; reconciliation during cleanup — **no copy needed for reconciliation or active
  agent use is ever deleted**.
- Restart preserves pending state + original deadline; recovery reconciles `dispatching` batches.
- **Text/expiry race:** text just before expiry dispatches; late text cannot revive an expired batch;
  a stale-ref rejection ⇒ notify + no retry (L-1).
- Expiry deletes **staged** files only; confirmed **`delivered`** (U-3) deletes **staged** files only;
  unknown keeps them; **the materialized workspace file survives `expires_at`** (r7, R6-1).
- Tombstone/F-1 guard still blocks any send to a deleted conversation.

**No test was executed for the upstream capability** (it does not exist). Existing OpenHandBot
attachment-rejection tests remain green (they are unchanged by this task).

---

## 11. Evidence and source references

All upstream files below were **fetched and hashed at r2** (public raw/spec fetch only); hashes are
`sha256` prefixes. Pinned SHAs were confirmed to equal current `main` at r2 time. **r4** re-verified
the M-2 claim (the `send-message` thin proxy) and the agent-server event-persistence path against
source (see the new entries below). **r5** additionally verified the existing Cloud primitives
`pending-messages` and `events/search` (§2.2, §5.14.1) and the event kinds/fields used by the H-1a
read-evidence rule. **r6** re-verified the **terminal exit-code / observation semantics** (§5.14.0,
N-1), the **file_editor `view` / structured `read_file`** read paths (N-1/N-4), and the
**start-only** `pending-messages` processing (N-3). **r7** re-verified the **polled-replica**
event path (`remote_sandbox_service.py::poll_agent_servers` → `refresh_conversation` →
`save_event`, sha256 `d239ec43…`, R6-3), the **absolute-path** requirement of the reader
(`file_editor/editor.py::validate_path` → `is_host_absolute_path`, sha256 `a1d735d4…`, R6-4), and
**re-confirmed the absence of any read-acknowledgment primitive** in the SDK (R6-2; a code search for
`read_complete`/`read_receipt`/`bytes_read` returned **0** results). **r8** re-verified, against the
pinned SHAs (re-fetched and re-hashed this session), the **conversation-delete archive/preserve**
behavior (R7-1), the **workspace-root provenance** (`AgentServerContext` has no workspace-path field;
the grouped root lives in the server-managed `archiveworkspacepath` tag; the agent-server derives it
from its own conversation — R7-2), and the **conditional poll-vs-webhook** replica population
(`web_url is None or 'localhost'` — R7-3); the r8 file hashes match the r7 review's citations
(`c43ed4f7`/`202fc8e1`/`d239ec43`/`27bae62a`/`7a4a54c0`/`5bea70f0`/`9e9b3e63`/`9f4f1596`). **r9**
re-verified, against the same pinned SHAs, the **sandbox-lifecycle** subsystem
(`sandbox/lifecycle/{__init__,settings,sweep,rules,tasks}.py`, `worker/app.py`), the **existing**
workspace-root reader (`app_conversation_models.py::AppConversationInfo.repositories`,
`additional_repositories.py::conversation_repositories`), and the **live** OpenAPI identifier
(`1.91.0`, 244 paths, sha256 `f0f4d4e9…`); it also **corrected two citation defects** in the r8
material (R8-3): the `bb9bbe23…` hash is the **enterprise** `sandbox/sandbox_router.py` (the
sandbox-server file is `07fef71e…`), and the archive module is `workspace_archive.py` (not
`ws_archive.py`).

- **Cloud V1 OpenAPI:** `https://app.all-hands.dev/openapi.json` — `info.version = 1.91.0`,
  244 paths, sha256 `f0f4d4e9…` (r9 re-fetch; **independently re-verified this session**). (No
  `multipart`/`binary`/`attach`; file routes read/download
  only; `send-message` = `anyOf[TextContent, ImageContent]`.) The **"no Cloud upload" conclusion is
  unchanged** — it rests on the **route evidence**, which is unchanged, **not** on the version string.
  **r10 (R9-4); re-affirmed r11 (N10-3):** the r8-era spec digest `1.87.1` / 242 paths / sha256
  `0086b0b0…ff77916` is a
  **historical reported value only** — the r8 proposal is **not on disk** and no artifact or
  authoritative record establishes that digest, so it is **NOT INDEPENDENTLY VERIFIED** and **must not**
  be used as evidence for current Cloud V1 route behavior (the r8 review records only "`1.87.1` / 242
  paths", not the hash). It is retained solely for audit history; the **current** evidence is the
  re-verified `1.91.0` / 244 paths / `f0f4d4e9…`.
- **Agent Server OpenAPI (public docs export) — possibly stale, do not use as authority:**
  `https://docs.openhands.dev/openapi/agent-sdk.json` — `OpenHands Agent Server 0.1.0`, 40 paths,
  sha256 `e42da653…5374a4d`. (Legacy shape `POST /api/file/upload/{path}`; `securitySchemes = {}`;
  missing scoped runtime routes, `/api/auth/workspace-session`, `/hooks`, and `capabilities`.)
- **`OpenHands/software-agent-sdk` @ `9f7d5cb11b1256c1878f5584a657401feca9ad16` (== `main`):**
  - `openhands-agent-server/openhands/agent_server/file_router.py` (sha256 `13f0cae7…`):
    `file_router = APIRouter(prefix="/file")`; `@file_router.post("/upload")` with **query** `path`;
    `_upload_file` only enforces `is_absolute()`.
  - `…/agent_server/runtime_router.py` (sha256 `5bea70f0…`): `create_runtime_router` prefix
    `/conversations/{runtime_conversation_id}`, `Depends(bind_local_conversation_runtime)`;
    `bind_local_conversation_runtime` enforces `resolve().is_relative_to(workspace_root)` → 422.
  - `…/agent_server/conversation_registry.py` (sha256 `4a479391…`): `add_execution_routes` →
    `create_runtime_router()`.
  - `…/agent_server/api.py` (sha256 `5de71d80…`): host-level `api_router` with
    `check_session_api_key`; mounts `file_router` (legacy) and `add_execution_routes` (scoped).
  - `…/agent_server/dependencies.py` (sha256 `f5f51362…`): `check_session_api_key`,
    `check_workspace_session`, `WORKSPACE_SESSION_COOKIE_NAME`.
  - `…/agent_server/server_details_router.py` (sha256 `2878f452…`): default capability
    `conversation_runtime_routes_v1`.
  - `…/agent_server/models.py` (sha256 `57b3680c…`): `FileUploadResult(Success) = {success, file_size}`.
  - **[r4]** `…/agent_server/event_router.py` (`POST /api/conversations/{id}/events` → `send_message`;
    returns `Success`; docstring: *"If starting the run returns 429, the message is already saved"*).
  - **[r4]** `…/agent_server/event_service.py::send_message` → `self._conversation.send_message(message)`
    (the agent-server appends the event to the conversation event log — a real durable agent-server
    step); **[r4]** `openhands-sdk/…/llm/message.py` (sha256 `1b9f0693…`): `Message.content =
    Sequence[TextContent | ImageContent]` — **no generic file block** (the H-1 evidence).
  - `tests/agent_server/test_runtime_router.py` (sha256 `98f931d8…`): confinement assertions
    (422/401/400), capability flag, legacy unconfined route returns 200.
  - `openhands-sdk/…/workspace/remote/remote_workspace_mixin.py` (sha256 `0e55f7ab…`): `api_prefix`,
    `fileUpload` → `POST {api_prefix}/file/upload`.
  - `clients/typescript/src/client/runtime-transport.ts` (sha256 `83ed2772…`):
    `ConversationScopedHttpClient` + `conversation_runtime_routes_v1` capability gate.
  - Tags `v1.62.0`, `v1.58.1`, `v1.20.0`, `v1.10.0` (`file_router.py`): route-form history
    (`/{path:path}` at `v1.10.0` → query form since `v1.20.0`).
  - REST compatibility policy: `.github/scripts/check_agent_server_rest_api_breakage.py`
    (additive unions allowed; removals need a deprecation runway; **REST clients need 5 minor
    releases of runway**).
  - **[r6, N-1] terminal tool error semantics:** `openhands-tools/…/tools/terminal/terminal/terminal_session.py`
    (sha256 `72504a4d…`): `_handle_completed_command` returns
    `TerminalObservation.from_text(..., exit_code=metadata.exit_code)` **without** `is_error`; the
    **only** `is_error=True` sites are interaction/empty-input/"cannot execute multiple commands"/
    closed-terminal. `openhands-tools/…/tools/terminal/definition.py` (sha256 `a978161b…`).
    `openhands-sdk/…/sdk/tool/schema.py` (sha256 `76b4f42a…`): `Observation.is_error` defaults to
    **`False`** — the sole error flag. ⇒ **a failed terminal read can be a non-error observation.**
  - **[r6, N-1/N-4] read tools:** `openhands-tools/…/tools/file_editor/impl.py` (sha256 `35353ad3…`)
    maps a `ToolError` to `is_error=True`; `…/tools/file_editor/editor.py` (sha256 `a1d735d4…`)
    implements `view`; `…/tools/file_editor/utils/constants.py` (sha256 `a5b3f2bf…`):
    `MAX_RESPONSE_LEN_CHAR = 16000` (truncated `view`). **Structured** tool:
    `openhands-tools/…/tools/gemini/read_file/definition.py` (sha256 `893fd5d5…`) defines
    `ReadFileObservation{file_path, file_content, is_truncated, lines_shown, total_lines}`;
    `…/tools/gemini/read_file/impl.py` (sha256 `2d5f81f2…`) returns `is_error=True` for
    missing/dir/offset/binary/permission failures. **But** it is a **Gemini-preset** tool and is
    **NOT** in the SDK default tool set (`openhands-sdk/…/sdk/tool/defaults.py`, sha256
    `357f005b…`: `DEFAULT_EXEC_TOOL_NAMES = ("terminal", "file_editor", "task_tracker")`; parity
    pinned by `tests/cross/test_default_tool_names.py`, sha256 `3b406311…`) ⇒ **deployment-dependent**.
    **[r7, R6-4; corrected r11, N10-1] the reader requires an ABSOLUTE path:** `…/tools/file_editor/editor.py`
    (sha256 `a1d735d4…`) `validate_path` (line 657) raises `EditorToolParameterInvalidError("path", …)`
    when `is_host_absolute_path(path)` is false (line 666) and rejects a missing path for non-`create`
    commands via the missing-path guard (`if command != "create" and not path.exists():` at line 689;
    `raise EditorToolParameterInvalidError(…)` at line 690 — lines 689-694). ⇒ a **workspace-relative**
    `delivered_path` is **rejected** by the named reader (§5.15.5, U-11). **[r7, R6-2] no read-acknowledgment primitive exists:** a code search over
    the SDK for `read_complete`/`read_receipt`/`bytes_read` returned **0** results ⇒ U-3's issuer does
    not exist today.
  - **[r8, R7-1; re-classified r11, N10-2] the agent-server conversation delete PRESERVES the
    workspace (it does NOT delete it):** `openhands-agent-server/openhands/agent_server/conversation_service.py`
    (sha256 `9e9b3e63…`, 3132 lines): `delete_conversation` (line 1863) calls `safe_rmtree(...)` on the
    **conversation directory** with the comment `# Safely remove only the conversation directory
    (workspace is preserved).` (line 1911). ⇒ conversation delete **preserves** the workspace directory
    (consistent with the §5.10.1/§5.10.4 C2 rule). This file was **mis-attributed** to
    `OpenHands/enterprise` in r10 (which has **no** `conversation_service.py`); it belongs to
    `OpenHands/software-agent-sdk@9f7d5cb1…` and is listed here accordingly.
- **`OpenHands/sandbox-server` @ `43e91604ccd0a9960c8d5c52faadd60b30f10e63` (== `main`):**
  - `openhands/app_server/app_conversation/app_conversation_router.py` (sha256 `864bff55…`):
    `_get_agent_server_context`, `_proxy_git_runtime_call`, read routes `/file`, `/download`,
    `/git/changes`, `/git/diff`. (No `/files`, no upload — see §2.2 provenance note.)
  - `…/app_conversation/live_status_app_conversation_service.py` (sha256 `9653dd3d…`):
    `_build_conversation` sets `conversation_url = <AGENT_SERVER url>/api/conversations/{id.hex}` and
    `session_api_key = sandbox.session_api_key`.
  - `…/sandbox/remote_sandbox_service.py` (sha256 `c523a807…`): `_to_sandbox_info`, `_build_service_url`
    (path mode / subdomain mode).
  - `…/sandbox/session_auth.py` (sha256 `893d725e…`): sandbox session-key handling.
- **`OpenHands/enterprise` @ `3fac53df8c2efcb67ff3537d1162e8c8a108f565` (== `main`; the repo that
  serves the live Cloud V1 API — r3, R2-1):**
  - `openhands/app_server/app_conversation/app_conversation_router.py` (sha256 `c43ed4f7…`): a
    **superset** of the pinned `sandbox-server` router; `list_conversation_files` (`GET
    …/{conversation_id}/files`, the live description), plus `/skills`, `/hooks`, `switch_acp_model`,
    `switch_profile`, `stream-start`, `start-tasks*`. **No** upload/`multipart`/`UploadFile` route.
  - `frontend/src/api/conversation-service/v1-conversation-service.api.ts` (sha256 `0a0b80c6…`):
    the legacy `/api/file/upload?path=…` upload client (§5.13).
  - **[r5] `openhands/app_server/pending_messages/pending_message_router.py` +
    `pending_message_service.py`:** `POST /conversations/{id}/pending-messages` →
    `queue_pending_message` → `SQLPendingMessageService.add_message` → `StoredPendingMessage` row +
    **`db_session.commit()`** (durable SQL store);
    `PendingMessageResponse{id, queued, position}`; 429 above 10. **[r6, N-3] drain is start-only:**
    `openhands/app_server/app_conversation/live_status_app_conversation_service.py::_process_pending_messages`
    (sha256 `9f4f1596…`) is invoked **once**, from the start path right after the start task reaches
    `READY` — the **only** caller; entries are **deleted regardless of delivery success**. **So this
    is a durable *pending*-message record for a *starting* conversation, NOT an active-conversation
    accept** (§5.9.1, §5.14.1).
  - **[r5] `openhands/app_server/event/event_router.py` + `event_service_base.py` +
    `filesystem_event_service.py`:** `GET /conversation/{id}/events/search` →
    `EventService.search_events` over the **Cloud-side** conversation event store (per-conversation
    path `…/{user}/v1_conversations/{conversation_id.hex}`; `kind__eq` filter; atomic `os.replace`
    index writes). **A durable, conversation-bound, Cloud-reachable event log** — the evidence source
    for the H-1a read rule (§5.14.1). **[r7, R6-3; corrected r8, R7-3] it is a *replica*, not the
    agent-server log:** `openhands/app_server/sandbox/remote_sandbox_service.py` (sha256 `d239ec43…`)
    has `poll_agent_servers(...)` (`while True … await asyncio.sleep(sleep_interval)`) →
    `refresh_conversation(...)` (line 1345) → `event_service.save_event(...)` (line 1438), copying
    events **one at a time** from the agent-server `events/search`. **The poller is conditional
    (r8, R7-3):** it is started **only when the app server has no public URL**
    (`web_url is None or 'localhost' in web_url`, lines 1518-1526: "When the app server does not have
    a public facing url, we poll the agent servers"); with a public URL the store is fed by
    **webhook callbacks**. Either way the Cloud store is an **eventually-refreshed replica** with a
    **non-atomic** read (§5.15.4, U-10).
  - **[r8, R7-1] conversation delete ARCHIVES + PRESERVES the workspace (not deletes):**
    `openhands/app_server/app_conversation/app_conversation_router.py` (sha256 `c43ed4f7…`):
    `_finalize_sandbox_delete` (line 1050) calls `sandbox_service.archive_conversation_workspace(...)`
    (line 1071) → `workspace_archive.archive_workspace` (sha256 `202fc8e1…`, line 334; capture
    uploads to a bucket via `store.write`, line 516) and tears the **sandbox** down **only when**
    `count_conversations_by_sandbox_id(...) == 0` (lines 1085-1091); the route schedules it detached
    (`asyncio.create_task`, line 1189) with `workspace_path` = the `archiveworkspacepath` tag read
    (line 1188: `app_conversation_info.tags.get(ARCHIVE_WORKSPACE_PATH_TAG_KEY)`; line 1185 is the
    preceding comment). `remote_sandbox_service.py::delete_sandbox` (sha256 `d239ec43…`, lines 917-925) is
    documented "**Purely sandbox-scoped**: stop the runtime and delete the record. Workspace capture
    is a separate conversation-scoped step"; enterprise `sandbox/sandbox_router.py` (sha256 `bb9bbe23…`;
the sandbox-server equivalent is `07fef71e…`, r9/R8-3)
    repeats it ("delete_sandbox … **never archives**"). The **agent-server** delete **preserves** the
    workspace: see the **`OpenHands/software-agent-sdk`** bullet above
    (`openhands-agent-server/…/agent_server/conversation_service.py`, sha256 `9e9b3e63…`, line 1911 —
    re-classified r11, N10-2: this file is **not** in `OpenHands/enterprise`). The physical-removal
    backstop is the
    **sandbox lifecycle** (r9/R8-1): `sandbox/lifecycle/{settings,rules,tasks,sweep}.py` +
    `worker/app.py` define `delete_after_seconds` (default 10 days; "Delete a sandbox, and its
    workspace, once it has not run for this long"), a periodic sweep, `decide()` → `Action.DELETE`, and
    `sandbox_service.delete_sandbox(...)` — for the **managed** backends (Docker/E2B/k8s); the
    Cloud/remote backend is **delegated to runtime-api** (`lifecycle/__init__.py`). The older
    "**runtime-api idle reap**" references (`app_conversation_router.py` lines 1067/1078;
    `remote_sandbox_service.py` lines 1088/1125) name the **external** (runtime-api) side. ⇒ **conversation
    archive/delete does not reclaim C2** (§5.10.1/§5.10.4, T-24, I12).
  - **[r8, R7-2; corrected r9, R8-2] workspace-root provenance:** `app_conversation_router.py::AgentServerContext`
    (sha256 `c43ed4f7…`, lines 220-228) has **no** workspace-path field; `_get_agent_server_context`
    exposes only `sandbox_spec.working_dir` (spec fetched line 278, context built lines 300-306).
    The grouped root is produced by `settings/settings_models.py::grouped_workspace_dir`
    (sha256 `27bae62a…`, line 753: `{base}/{conversation_id_hex}` for any strategy other than
    `NO_GROUPING`; `SandboxGroupingStrategy`, lines 739-748) and pinned in the **server-managed
    reserved** tag `ARCHIVE_WORKSPACE_PATH_TAG_KEY = 'archiveworkspacepath'`
    (`app_conversation/app_conversation_models.py`, sha256 `7a4a54c0…`, lines 65/89/263;
    `RESERVED_TAG_KEYS` line 86 — corrected r10/R9-2; the former "line 96" was wrong: line 96 is
    `def _validate_caller_tags(...)`, the validator that **uses** `RESERVED_TAG_KEYS`), written at
    conversation start by
    `live_status_app_conversation_service.py` (sha256 `9f4f1596…`, line 1124:
    `tags[ARCHIVE_WORKSPACE_PATH_TAG_KEY] = working_dir`). **The Cloud-side *read* of the
    per-conversation root already exists (r9, R8-2):** `AppConversationInfo.repositories`
    (`app_conversation_models.py`, sha256 `7a4a54c0…`, lines 250-265) is a `@computed_field` that
    reads `self.tags.get(ARCHIVE_WORKSPACE_PATH_TAG_KEY)` and calls `conversation_repositories(...)`
    (`app_conversation/additional_repositories.py`, sha256 `a8d0bbe3…`; `conversation_repositories`
    def at line 89; the `path=f'{working_dir}/{folder}'` expression at line 106) to build
    `path = f'{working_dir}/{folder}'`; it is exposed **live** as `AppConversation.repositories` →
    `ConversationRepository.path` ("Absolute path of the folder in the sandbox"; live OpenAPI
    `1.91.0`). The agent-server side derives the correct
    (grouped) root from its own conversation: `runtime_router.py::bind_local_conversation_runtime`
    (sha256 `5bea70f0…`, lines 41-43) —
    `workspace_root = Path(event_service.get_conversation().workspace.working_dir).resolve()`;
    `ConversationInfo.workspace` is exposed by the agent-server `GET /conversations/{id}`
    (`models.py`, sha256 `57b3680c…`, line 157). ⇒ the tag→root **read is existing**; the **identity/
    authorization binding** of that root to `(principal, conversation_id, operation_id)` is **U-12**
    (§5.15.6, T-25, I15).
  - **[r9, R8-1] sandbox lifecycle (physical removal of the workspace):**
    `openhands/app_server/sandbox/lifecycle/{__init__,settings,sweep,rules,tasks}.py` +
    `worker/app.py`; `settings.py` `delete_after_seconds` ("Delete a sandbox, and its workspace, once
    it has not run for this long"); the periodic `sweep` job is declared in `tasks.py`
    (`@lifecycle.periodic(cron='* * * * *')`, line 78; `name='sweep'`, line 80) with candidate
    selection in `sweep.py` (`find_due_sandbox_ids`); `rules.py::decide` → `Action.DELETE`
    (`Reason.INACTIVE`) over `LAST_RAN_AT = greatest(state_changed_at, last_active_at)`;
    `tasks.py` → `sandbox_service.delete_sandbox(...)`; scope per `lifecycle/__init__.py`:
    "covers every backend that subclasses `ManagedSandboxServiceInjector`: **Docker, E2B and k8s
    agent-sandbox**… **runtime-api manages the remote backend's sandboxes itself.**" ⇒ teardown is a
    **modeled** mechanism for the managed backends and **delegated to runtime-api** for the Cloud
    backend (§5.10.4).
- **`OpenHands/OpenHands` @ `a8aaf6813753803cae5182d050909705b0eb02d0` (== `main`, official GUI):**
  `src/api/conversation-file-upload.api.ts` (sha256 `d5ae6b81…`),
  `src/api/workspace-upload-path.ts` (sha256 `caabd831…`),
  `src/api/agent-server-client-options.ts` (sha256 `78364c26…`),
  `src/api/cloud/conversation-service.api.ts` (sha256 `94f38037…`),
  `src/utils/file-validation.ts` (sha256 `51b16ff5…`, 3 MB per-file + 3 MB total),
  plus `src/hooks/chat/use-chat-attachment-upload.ts`, `src/utils/send-message-with-attachments.ts`,
  `tests/e2e/mock-llm/conversations/mock-llm-image-upload.spec.ts`.
- **Docs:** `https://docs.openhands.dev/sdk/arch/agent-server.md`,
  `https://docs.openhands.dev/sdk/guides/agent-server/api-reference/files/upload-file.md`,
  `https://docs.openhands.dev/openhands/usage/cloud/cloud-api.md`,
  `https://docs.openhands.dev/llms.txt`.
- **OpenHandBot (local):** `bot/openhands_client.py` (Cloud-only, bearer, redirect-rejecting),
  `bot/files.py:15` (documented no-upload stance), `bot/handlers.py`
  `handle_unsupported_attachment` (fail-closed rejection),
  `tests/test_unsupported_attachment_rejection.py`.

**Unverified / caveats.** (a) **R2-1 resolved:** the live Cloud V1 API is served by
`OpenHands/enterprise` (§2.2, §11); the exact **deployed commit** of `enterprise` is not verifiable
from outside, so the attribution is from the public `main` router + the live route/description
match, not a deployed-SHA read. (b) `send-message` `ImageContent`-as-attachment **persistence** is
**not** established by the source reviewed (the Cloud proxies `send-message` server-side — R2-2 — so
the path is *reachable*, but whether an image is persisted as a workspace file is unverified).
(c) The concrete sandbox host pattern (§2.4) is deployment-dependent and not documented.
(d) **r4 (M-2) — the `send-message` hop is a thin proxy with no durable Cloud write** (verified
source: `send_message_to_conversation` → `httpx.post` → `AppSendMessageResponse(success,
sandbox_status)`). r3's claim that `consumed_at` is written "in the same durable step" is **not
backed by the current source**. **r5 (H-1c):** a durable message-accept **already exists** in a
**different** Cloud route — `POST /api/v1/conversations/{id}/pending-messages` (SQL commit, §11);
a durable step **on `send-message`** would be **new upstream work** (§5.15 U-2). **r6 (N-3):** that
route is **start-only** (drained once at conversation start) ⇒ it is **not** a durable accept for a
**running** conversation.
(e) **r4 (H-1); corrected r5 (H-1c); corrected r6 (N-1/N-3) — no existing mechanism *by itself*
delivers uploaded bytes to the agent as readable content, and no existing primitive *proves* a
successful content read** (verified: the agent-server message model is `TextContent |
ImageContent`; `ImageContent` is images-only; read endpoints are not ingestion; a **failed terminal
read is a non-error observation**, §5.14.0). **r5:** the delivery contract (§5.14) is **partly
composable** from existing primitives (the durable event store `events/search`, the server-side
runtime hop, the confined write primitive) and **partly new** (the attachment operation, the
server-to-server materialization, the delivery authorization, the **durable active-conversation
accept**, and the **new successful-read signal** U-3); the
choice of mechanism is an owner decision (§12, Q14). Calling the whole thing "new" (r4) understated
the composition; **calling the read-evidence rule "new but its primitives sufficient" (r5) overstated
it** (r6, N-1).
(f) **r4 (M-3); corrected r5 (H-1a); corrected r6 (N-1); corrected r7 (R6-1); corrected r8 (R7-1);
corrected r9 (R8-1) —
no existing primitive provides the `delivered` successful-content-read signal (F6b)**; it requires the
**new U-3** signal, and until it exists the safe fallback is **staging** retention until `expires_at`
**and** retention of the **workspace-materialized copy** — which, per the pinned source (r8, R7-1),
is reclaimed by **no conversation-scoped event at all** (conversation archive/delete **archives** +
**preserves** the workspace; only a **sandbox/pod teardown** removes it — **r9, R8-1:** *modeled* for
the managed backends by the Enterprise sandbox lifecycle, *delegated to runtime-api* for the Cloud
backend; **r10, R9-1:** that lifecycle timer is a **separate clock** from the operation's `expires_at`
and is **not** an F7 signal, and **r10, R9-3:** the verified mechanism is **container removal**, with
physical deletion of the underlying workspace data **UNVERIFIED** for host-mounted layouts)
(§5.10.1/§5.10.4/§12
Q16/Q18). **F7 (the agent finished using the contents) is not modeled** by any primitive and is not
required.
(g) **r4 (M-5) — the server has no batch concept**; the fixed batch deadline is client-side (§8.4).
(h) **r5 (S-3) — the delivered file's concrete mode/ownership** is a deployment parameter; whether
the default umask/uid already makes it readable by the agent's runtime user is **UNVERIFIED**
(§7.4, §12 Q14).

---

## 12. Open questions and maintainer decisions

1. **Ownership of the capability:** should the scoped upload live in **Cloud V1** (recommended, §5)
   or on the **Agent Server**? (Cloud removes the origin problem; Agent Server keeps the origin
   problem.)
2. **Scope mechanism:** a per-operation Cloud-authorized route vs a conversation-bound **capability
   token**. If a token, what is its TTL, binding, and revocation model?
3. **Size/type policy — internal consistency (r2).** The proposed limits are mutually inconsistent:
   `max_total = 3 MiB = max_per_file` ⇒ at most one full-size file. Confirm the intended triple
   (e.g. `max_per_file`, `max_total ≥ max_files × max_per_file`, `max_files`) — or accept the
   single-full-file behavior. (§5.7)
4. **Reuse boundary (r2).** Confirm that the design should **reuse** the existing conversation-bound
   route + `bind_local_conversation_runtime` containment rather than adding a parallel confined path
   (§7.0), and confirm the existing confinement is considered sufficient as a base.
5. **Reference resolution + agent-readable delivery (r3 Q5; expanded r4, H-1; corrected r5, H-1a/H-1c;
   corrected r6, N-1).**
   Two parts, both owner decisions:
   - **(5a) Ref resolution.** Is an opaque `stored_path_ref` acceptable (recommended, removes path
     injection)? The **Cloud** must be able to **resolve** it back to its operation/conversation.
   - **(5b) Agent-readable content (NEW, r4).** **How does the uploaded content become readable by
     the agent?** This is the H-1 gap and is **not** answered by (5a) alone. Recommended: the Cloud
     **materializes** the file into the conversation workspace at a server-generated `delivered_path`
     and the message references that **concrete path** (§5.14). **Alternatives:** a new message
     content block the agent server ingests (design B); an agent-side tool to fetch by ref (design
     C); inlining bytes (design D). **Minimum evidence (r5; corrected r6):** a maintainer decision on
     the mechanism **+ a *verified* successful-content-read signal** — **r6 (N-1): no existing
     primitive provides it** (`ActionEvent`/`ObservationEvent`/`AgentErrorEvent` are **insufficient**;
     a failed terminal read is a non-error observation), so a **new signal (U-3)** must be
     designed/approved. **Blocks:** approval (the feature is inert without it) and implementation.
   - **(5c) NEW (r5, H-1a; corrected r6, N-1; corrected r7, R6-2).** Confirm the **exact** `delivered`
     evidence rule of §5.14.2 step 6 — **r7 supersedes r6**: `delivered` requires the **new U-3
     structured read acknowledgment** issued by a **trusted, non-agent** component (§5.15.1) with
     **authenticated provenance** (§5.15.2) and **exact content binding** (§5.15.3),
     **not** a correlated **non-error** `ObservationEvent` (F6a), **not** a bare `ActionEvent` (F4),
     and **never** an **agent/tool-emitted** event. **Blocks:** the `delivered` state and
     all early reclaim.
6. **Reconciliation window (r3; refined r4, M-5; corrected r7, R6-1).** Confirm the **operation**
   `expires_at` (15 min, fixed at accept) and the retention/cleanup sweep for **staged/undelivered
   files**; confirm the rule that after `expires_at` the status never reports a non-terminal state.
   **r4:** the **product batch deadline** (15 min from the first file) is **client-side**; the server
   has **no batch concept** (§8.4) — confirm the API does not need to model the batch. **r7 (R6-1):**
   `expires_at` reclaims the **staging/recovery copy only**; the **workspace-materialized copy is
   NEVER reclaimed at `expires_at`** (§5.10.1) — confirm this split and the resulting C2 retention
   (Q18).
7. **Idempotency:** is `Idempotency-Key` + `sha256` dedup acceptable, and over what window? **r4:**
   also confirm **delivery** idempotency keyed on `(operation_id, file_id)` (§5.15 U-4).
8. **Ended/deleted conversations:** confirm 409 semantics and reclamation behavior.
9. **The legacy unconfined `/api/file/upload`:** should it be deprecated (with the required runway)
   once the scoped path ships? (Out of scope here; flagged for the maintainers.) Also see §5.13: the
   Enterprise frontend still uses it — is migrating that client in scope upstream?
10. **Independent security review:** who performs it, and is it a release gate for the capability?
11. **Product decision for OpenHandBot (r3; unchanged).** Even with the capability, does the project
    owner want P0 implemented, or keep the current fail-closed rejection? **r4/r5/r6:** the delivery
    contract (§5.14) is **partly composable and partly new upstream work**, and **r6 (N-1/N-3)** adds
    two new upstream requirements (a **new successful-read signal U-3** and a **durable
    active-conversation accept U-2**), so P0 depends on **more**
    than the upload op; the owner may still choose to keep the fail-closed rejection. **This is the
    owner's decision and is not made here.**
12. **`consumed_at` semantics + durable-accept trade-off (r3, R2-6; reframed r4, M-2/M-3; made
    coherent r5, M-2-res; corrected r6, N-3).** r3 assumed `consumed_at` was written "in the same
    durable step" as
    accepting the message; **r4** established the `send-message` route is a **thin proxy** with no
    durable write; **r5** fixed the definition (§5.9.1): `consumed_at` is a **message-accept** marker,
    set **only** on a **durable** accept. **r6 (N-3):** the existing durable
    `POST /api/v1/conversations/{id}/pending-messages` route is **start-only** and does **not** serve a
    **running** conversation, so **no durable active-conversation accept exists today** — one would be
    **NEW** on `send-message` (or elsewhere).
    Confirm: (i) whether `consumed_at` is retained at all, and (ii) if retained, **which durable
    route** sets it. `consumed_at` **never** authorizes deletion (M-3). **Blocks:** the `consumed_at`
    signal and any guarantee that depends on it.
13. **`uploading`/`delivering` re-introduction (r3, R2-9; extended r4; settled r5, S-1).** r3 removed
    `uploading`; r4 kept it absent and added `delivered`. **r5** makes the model **coherent**:
    staging is **synchronous within the create request**, so the observable states are
    `stored | delivered | rejected | failed | expired` — **`accepted` is internal-only and never
    returned**, and `uploading`/`delivering` are absent. **If maintainers intend deferred/async
    staging or delivery**, the corresponding intermediate state(s) MUST be re-added **with** the
    entering event, owner, and crash-recovery rule (this would reopen the r3 decision). Confirm
    staging **and** delivery are synchronous within the request (or specify the async model).
14. **NEW (r4, H-1) — delivery mechanism + whether to extend `send-message`.** Confirm the delivery
    design (§5.14.2 design A) and whether it may be implemented by **extending** the existing
    `send-message` path (server resolves the ref and materializes before forwarding) rather than a
    new endpoint. **Why:** it is the central H-1 fix. **Options:** A/B/C/D (§5.14.3). **Recommended:**
    A. **r5 (H-1c):** the design is **partly composable** (Cloud-reachable `events/search`, the
    **start-only** `pending-messages` record, server-side runtime hop, confined write) and **partly
    new** (attachment op, server-to-server materialization, delivery authorization, the **new U-3
    successful-read signal**, and the **durable active-conversation accept** U-2) — the decision is
    therefore a **composition/placement** decision, not a from-scratch design. **Minimum evidence:**
    maintainer decision (+ the U-3 signal, Q16). **Blocks:** approval + implementation.
15. **NEW (r4, M-2; corrected r6, N-3) — durable message-accept.** Confirm whether a durable
    message-accept is in scope:
    (a) reuse the **existing durable** `pending-messages` route — **r6 caveat: it is start-only and
    cannot serve a running conversation** (§5.15 U-2), or
    (b) add a durable accept step **on `send-message`** (new work), or (c) **drop** `consumed_at` and
    reconcile via the event log alone. **Blocks:** the `consumed_at` signal and any guarantee that
    depends on it.
16. **NEW (r4, M-3; corrected r5, H-1a; corrected r6, N-1; extended r7, R6-2) — successful-read
    evidence availability + issuer trust.** Confirm the **exact** §5.14.2 step 6 rule — **r7
    supersedes r6**: `delivered` requires the **new U-3 structured read acknowledgment** (a **complete
    content read**, F6b) issued by a **trusted, non-agent** component with **authenticated provenance**
    and **exact content binding** (§5.15.1–§5.15.3) — **not** a correlated **non-error**
    `ObservationEvent` (F6a — insufficient: a **failed terminal read is non-error**), **not** a bare
    `ActionEvent` (F4), and **never** an **agent/tool-emitted** event. Because **no existing primitive
    provides this signal *and* no trusted issuer exists today** (UNVERIFIED, §5.15.1), confirm whether
    the **new U-3 capability + trusted issuer** are accepted; if not, accept the fallback (**staging**
    retention until `expires_at`; **workspace copy retained beyond the life of the conversation** (no conversation-scoped reclaim — r8, R7-1), Q18).
    **F7 (agent finished using the contents) is not modeled** and is not required. **Blocks:** the
    `delivered` terminal state and early reclaim.
17. **NEW (r4, M-4; tightened r5, M-4b) — correlation id contract.** Confirm the contract:
    `client_operation_id` is **required** (a UUID), echoed in all responses, unique per
    `(principal, conversation_id)`, with **same-key/same-payload ⇒ same operation** and
    **same-key/different-payload ⇒ `409 client_operation_id_conflict`** (§5.16). **Blocks:**
    unambiguous correlation of **all** operations (now unconditional).
18. **NEW (r7, R6-1; strengthened r8, R7-1; corrected r9, R8-1) — bounded retention policy for the
    workspace-materialized copy (C2).** The workspace copy is the agent's file and is **not**
    deleted by the **operation's** timer (`expires_at`; scoped r10, R9-1 — a **separate** infrastructure
    timer, the Enterprise sandbox lifecycle §5.10.4, may remove the sandbox **and its workspace** in
    governed environments; that is **not** the operation's `expires_at` and **not** an F7 signal); with
    no **F7 end-of-use** signal **and no conversation-scoped reclaim** (r8, R7-1: conversation
    archive/delete **archives** the workspace and **preserves** the directory) it therefore persists
    **beyond the life of the conversation** — a **safe but unbounded-per-conversation** default
    (storage grows with accumulated attachments). **r9 (R8-1) correction:** the physical-removal path
    is **not** universally unmodeled — the pinned Enterprise source **models** an idle
    (`delete_after_seconds`) sandbox-and-workspace delete for the **managed** backends (Docker/E2B/k8s),
    wired in the worker; for the **Cloud/remote** backend the lifecycle is **delegated to runtime-api**
    (external). The sweeper is a **sandbox-scoped idle bound, not an F7 signal**, and does not prove a
    conversation reached a safe terminal state. Confirm a **bounded** retention policy for C2 that is
    compatible with F7
    semantics (e.g. a per-conversation storage cap, an explicit end-of-conversation cleanup, or a new
    F7 signal) and confirm the **Cloud/runtime-api** teardown bound and its interaction with grouping.
    **Until decided, the conservative fallback holds** (§5.10.4). **Blocks:** an
    operational retention bound for materialized files.
19. **NEW (r7, R6-2) — U-3 trusted issuer + authentication mechanism.** Confirm **which** service-side
    component is the **authoritative U-3 issuer** (Cloud/control-plane or Agent Server), and the
    **authentication/provenance mechanism** (signed service-to-service assertion, or internal-credential
    channel) that makes the acknowledgment unforgeable by the agent (§5.15.1/§5.15.2). **UNVERIFIED:**
    no such issuer exists in the pinned source today. **Blocks:** the `delivered` state (and therefore
    any early reclaim).
20. **NEW (r7, R6-3; corrected r8, R7-3) — quiesced evidence source (U-10).** Confirm the
    **consistency guarantee** for the event-based evidence used by the U-3 rule — a
    quiesced/finalized source or an agent-server re-verify — since the Cloud `events/search` store is a
    **replica** populated by a poll loop (only when there is **no public URL**) **or** by **webhooks**
    (r8, R7-3), and is not a consistent snapshot on either path (§5.15.4). **Blocks:** the
    trustworthiness of any event-based evidence.
21. **NEW (r7, R6-4) — absolute delivered-path contract (U-11).** Confirm that the agent-facing
    `delivered_path` is **absolute** and that the producer-to-reader flow (§5.15.5) is implemented and
    tested, since the named reader (file_editor `view`) rejects relative paths. **Blocks:** the
    end-to-end "agent can read the file" guarantee (I14).
22. **NEW (r8, R7-2; corrected r9, R8-2) — workspace-root provenance/binding (U-12).** Confirm the
    **authoritative** source of the conversation's workspace root for the Cloud side (the pinned
    `archiveworkspacepath` tag, or an agent-server query for the runtime's own `workspace.working_dir`),
    the **grouping** behavior (per-conversation nested dir under any non-`NO_GROUPING` strategy), and
    the **binding** of the resolved root to `(principal, conversation_id, operation_id)` (§5.15.6).
    `_get_agent_server_context` exposes only `sandbox_spec.working_dir` (the **ungrouped base**) and is
    **not** a valid root source. **EXISTING (r9, R8-2):** the **tag→root read already exists and
    ships** — `AppConversationInfo.repositories` reads the reserved `archiveworkspacepath` tag via
    `conversation_repositories` and is exposed live as `AppConversation.repositories.path`.
    **UNVERIFIED / NEW:** no pinned primitive binds that root to `(principal, conversation_id,
    operation_id)` or authorizes the write for the operation. **Blocks:** the correct, identity-bound
    delivery destination (I15, T-25).

---

## 13. Revision history

| Rev | Date | Change |
| --- | --- | --- |
| r1 | 2026-11-12 | Initial investigation + specification under `OHB2-P0-OPENHANDS-SECURE-UPLOAD-CAPABILITY-INVESTIGATION-AND-UPSTREAM-SPEC`. Re-validated the upstream capability against current sources; documented the official GUI attachment flow; specified the recommended Cloud-hosted scoped upload operation + status endpoint; threat model; upstream plan; OpenHandBot integration contract; acceptance criteria; open questions. |
| r2 | 2026-11-11 | **Evidence correction + revision** under `OHB2-P0-SECURE-UPLOAD-PROPOSAL-EVIDENCE-CORRECTION-AND-REVISION`, driven by the independent adversarial review (`PASS_WITH_MAJOR_FINDINGS — REVISION REQUIRED`, findings F1–F4). **F1:** distinguished the **legacy unconfined** `POST /api/file/upload` from the **conversation-bound, workspace-confined** `POST /api/conversations/{runtime_conversation_id}/file/upload`; corrected the header, §1, §2.3, §3, §4, §5.1, §7, §7.7 so the gap is stated as *authorization scoping + destination resolution + limits + reconciliation*, not missing confinement. **F2:** demoted the stale docs export (`agent-sdk.json`) from "authority" to "possibly-stale snapshot" (§2.1/§2.3.4) and used source at the pinned SHAs (all three SHAs == current `main`); recorded the export's route-form contradiction and its missing routes. **F3:** rewrote the §3 gap table to separate *existing* from *missing* (A/B/C/D/E). **F4:** corrected the "only two runtime calls" claim (§2.2) to the full read/download set (`/file`, `/files`, `/download`, `/git/changes`, `/git/diff`) and added the Cloud server-side hop provenance. Added §7.0 (minimum upstream changes + reuse map, answering the 7 reassessment questions); updated §2.5 (GUI uses the scoped route); flagged the §5.7 limits inconsistency; added a "must stay green" note to §10.1; added hashes + caveats to §11; updated §12 open questions. **Design, security requirements and invariants (§5.2–§5.12, §6, §8, §9) preserved unchanged.** |
| r3 | 2026-11-11 | **Findings remediation** under `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R3-FINDINGS-REMEDIATION`, driven by the r2 independent review (`docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R2-INDEPENDENT-REVIEW.md`, `PASS_WITH_NOTES`, findings R2-1 … R2-9). **R2-1 (MEDIUM):** corrected the Cloud provenance to name **`OpenHands/enterprise`** (`@3fac53df…`, sha256 `c43ed4f7…`) as the repository serving the live Cloud V1 API — a **different, newer repo** that is a superset of the pinned `sandbox-server` router, **not** a newer build of the same repo; confirmed the "no Cloud upload" conclusion is unaffected (§2.1, §2.2, §11). **R2-2 (MEDIUM):** noted that Cloud `send-message` already performs the server-side runtime hop (`send_message_to_conversation`), confirming ImageContent reachability via the Cloud bearer (persistence still UNVERIFIED) (§2.2). **R2-4 (LOW):** added §5.13, a legacy-Enterprise/frontend compatibility note (the `enterprise` frontend still uses `/api/file/upload?path=…`; coexist, out of scope to change, not equivalent to the secure op). **R2-6 (MEDIUM):** added §5.9.1 defining an **observable `consumed` transition** — a durable `consumed_at` marker owned by the Cloud attachment service, set when the Cloud's `send-message` path **durably accepts** a message referencing a `stored_path_ref`; covers meaning (≠ upload success, ≠ delivery), durability, crash rule (unconfirmed consume ⇒ treated as not consumed ⇒ never early delete), and interaction with the deadline / late text / ambiguous outcomes / Telegram. **R2-8 (LOW):** added **`expires_at`** to the §5.9 status schema with UTC ISO-8601 semantics, fixed-at-accept, never-extended, and post-expiry terminal-state rule. **R2-9 (LOW):** **removed** the unreachable `uploading` state; declared the model `accepted` → `stored`/`rejected`/`failed`/`expired` with reachability rationale. **R2-7 (LOW):** added a staging-visibility note (§5.7). Consistent updates to §5.5, §5.10, §7.5, §8.1 (I12/S7), §9 (new criterion 7b), §10.1 (new state-model + consumption-marker tests), §11 (hashes/caveats), §12 (Q5/Q6 + new Q12/Q13), §13. **No security requirement weakened; §5.2–§5.12, §6, §8, §9 design preserved.** Self-review: `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R3-SELF-REVIEW.md`. |
| r4 | 2026-11-11 | **Critical-gap remediation** under `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R4-CRITICAL-GAP-REMEDIATION`, driven by the r3 independent adversarial review (`docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R3-INDEPENDENT-ADVERSARIAL-REVIEW.md`, verdict **`NEEDS_REVISION`**, findings **H-1** + **M-1 … M-5** + L-1…L-4/I-1). **H-1 (HIGH):** added **§5.14 "Agent-readable content delivery"** — a complete end-to-end contract from uploaded bytes to agent-readable content (Cloud resolves + authorizes the ref; **materializes** the file into the conversation workspace at a server-generated `delivered_path`; the message references the **concrete path**; `delivered` requires agent-server event-log evidence of a read). Verified that **no existing** mechanism (agent-server message model `TextContent \| ImageContent`, `ImageContent`, read endpoints, `/file/upload`) delivers general files to the agent, so the contract is a **NEW upstream capability** (owner decision Q14). **M-1 (MEDIUM):** added **§8.3** durable-ordering + seven crash-window analysis, reconciled with `OHB2-TELEGRAM-ACK-ARCHITECTURE-ADR.md` + `bot/outbox.py`; no exactly-once claim. **M-2 (MEDIUM):** corrected §2.2/§5.9.1 — the `send-message` hop is a **thin proxy with no durable Cloud write**; a durable accept step is **new work** (§5.15 U-2). **M-3 (MEDIUM):** cleanup is **evidence-based** — deletion only on `delivered` (or `expires_at`/`rejected`/`failed`), **never** on `consumed_at` alone (§5.10). **M-4 (MEDIUM):** added **§5.16** correlation (client `client_operation_id` echoed in all responses; server op row created before staging; pre-operation rejections carry no server id) and made §5.5 consistent with the state model. **M-5 (MEDIUM):** the fixed deadline is the **client-side batch deadline** (`T0`+15 min, §8.4); the server's `expires_at` is a per-operation retention bound with no batch concept. **L-1 (stale-ref ⇒ notify, no retry), L-2 (partial staging cleaned on `failed`/`expired`), L-3 (server status authoritative for `expires_at`), L-4 (legacy key weakness parity), I-1 (`send-message` has no idempotency key)** addressed. New state **`delivered`**; invariants **I14**; criteria **7c/11**; questions **Q14–Q17**; §10.1/§10.2 tests. **No security requirement, threat-model row, or P0 invariant weakened; §5.2–§5.4, §5.6–§5.8, §5.11–§5.13, §6, §7.0–§7.4, §7.6–§7.8, §9 items 1–10 preserved.** Self-review: `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R4-SELF-REVIEW.md`. |
| r5 | 2026-11-11 | **R4 review findings remediation** under `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R5-REVIEW-FINDINGS-REMEDIATION`, driven by the **R4 independent adversarial review** (`docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R4-INDEPENDENT-ADVERSARIAL-REVIEW.md`, verdict **`NEEDS_REVISION`**). **H-1a (MEDIUM):** corrected the read-evidence rule — added **§5.14.0** (r5 stated **seven** lifecycle facts F1–F7, never conflated — **superseded** by the **eight-fact** model at r6/r7) and rewrote **§5.14.2 step 6** so `delivered` requires a **successful** read (**F6**: a correlated **non-error** `ObservationEvent` for an `ActionEvent` naming `delivered_path`); a bare `ActionEvent` (**F4**) or an `AgentErrorEvent` ⇒ **not** `delivered`; **F7** is **not** modeled. **H-1c (LOW):** re-framed §5.14/§5.14.1 from "all new" to **"partly composable, partly new"** — documented the **existing durable** Cloud primitives `POST /api/v1/conversations/{id}/pending-messages` (durable SQL message-accept) and `GET /api/v1/conversation/{id}/events/search` (durable, conversation-bound, Cloud-reachable event log) as the composable pieces; the attachment op, server-to-server materialization, delivery authorization, and the successful-read **rule** remain new. **M-2-res (MEDIUM):** §5.9.1 rewritten with **one** definition of `consumed_at` (a **message-accept** marker, set **only** on a durable accept; **not** by the thin-proxy `send-message`), removing the r4 §7.5 self-contradiction. **S-1 (MEDIUM):** fixed the §5.5/§5.9 contradiction — staging is **synchronous within the create request**; a successful create returns **`stored`**; `accepted` is **internal-only and never returned**. **M-3b (LOW):** §5.10 rewritten as the authoritative **per-artifact** retention rule — on `delivered`, only the **staging** copy is reclaimed; the **delivered** copy persists; the r4 "reclaim the delivered copy" wording is **withdrawn**. **M-4b (LOW):** `client_operation_id` is now **required** (UUID) with uniqueness scope `(principal, conversation_id)`; same key + same payload ⇒ same operation; same key + different payload ⇒ **409 `client_operation_id_conflict`** (§5.4/§5.8/§5.16). **H-1b/S-2/S-3 (LOW/INFO):** tied `delivered_path` to the confined workspace root (§5.14.2 step 5); stated the **integration boundary** (the outbox carries **text only**; attachment dispatch needs a new payload capability — §8.3); listed the required **filesystem guarantees** (atomic publication via `os.replace`, readable mode/owner, partial-write cleanup — §7.4). Also: audit event `attachment.accepted` renamed `attachment.row_created` + `attachment.read_confirmed` added (§5.11); threat rows **T-18/T-19** refined and **T-21** added; §5.15 re-framed with a **Status** column (U-1…U-9); §9 criteria 7b/7c tightened; §10.1/§10.2 test checks updated; §11 source list extended with the r5-verified primitives and caveats (d)/(e)/(f) corrected; §12 Q5/Q11/Q12/Q13 corrected and Q14–Q17 updated. **No security requirement, threat-model mitigation, or P0 invariant weakened (one threat row added).** |
| r6 | 2026-11-11 | **Read-evidence + primitive corrections** under `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R6-READ-EVIDENCE-AND-PRIMITIVE-CORRECTIONS`, driven by the **R5 independent adversarial review** (`docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R5-INDEPENDENT-ADVERSARIAL-REVIEW.md`, verdict **`NEEDS_REVISION`**, findings **N-1 … N-5**). **N-1 (MEDIUM):** withdrew the r5 rule that a correlated **non-error** `ObservationEvent` (F6) proves a successful read — the pinned **terminal** tool returns a **non-error** `TerminalObservation` for a **failed** read (`is_error` is not set for a non-zero `exit_code`; `Observation.is_error` defaults `False`), so `cat <missing>` could set `delivered` and permit **premature reclaim**. Added the **eight-fact** model (§5.14.0: F1–F5, **F6a** non-error observation, **F6b** successful content read, F7), stated that **no existing primitive proves F6b**, and required a **new explicit structured read acknowledgment (U-3, §5.15)** with a **field contract** (fields, correlation, semantics, fail-closed failure behavior); until U-3 exists `delivered` is **unreachable** and the operation stays `stored` until `expires_at` (the fallback **authorizes no early reclaim** and **never** implies a successful read). **N-2 (LOW):** the §5.5 create example returned `"state": "accepted"`; fixed to `"state": "stored"` and all examples re-checked against the state machine. **N-3 (LOW):** the Cloud `pending-messages` route is **drained only at conversation *start*** (`_process_pending_messages`, one caller after `READY`; deleted regardless of delivery success; capped at 10) ⇒ **not** an active-conversation accept; §5.9.1/§5.14.1/§5.15 U-2/§8.2 S7 corrected and U-2 re-classified **NEW for the running-conversation case**. **N-4 (INFO):** §5.14.2 step 5 names the reader and its success signal and **rejects** terminal `cat` (a non-zero `exit_code` is a failed read even when `is_error == false`); notes the **structured `read_file`** tool exists but is a **Gemini-preset** tool (not in the SDK default tool set) ⇒ deployment-dependent. **N-5 (INFO):** the header now identifies the document as **r6** and lists the r5 + r6 task ids. Updated §1, §4, §5.5, §5.9, §5.9.1, §5.10, §5.11, §5.14 (intro/§5.14.0/§5.14.1/§5.14.2/§5.14.3/§5.14.4), §5.15 (U-2/U-3 + field contract), §6 (T-18/T-19), §7.0/§7.1/§7.5, §8.1 (I12/I14), §8.2 (S7), §9 (7b/7c), §10.1/§10.2, §11 (r6 source entries; caveats d/e/f), §12 (Q5/Q11/Q12/Q14/Q15/Q16), §13. **No security requirement, threat-model mitigation, or P0 invariant weakened; the read-evidence and retention rules were made *stricter*.** |
| r7 | 2026-11-12 | **Lifecycle + trust remediation** under `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R7-LIFECYCLE-AND-TRUST-REMEDIATION`, driven by the **R6 independent adversarial review** (`docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R6-INDEPENDENT-ADVERSARIAL-REVIEW.md`, verdict **`NEEDS_REVISION`**, findings **R6-1 … R6-5**). **R6-1 (MEDIUM, blocking):** the **materialized (workspace) copy** could be deleted at `expires_at` while the agent still needed it (the T-19 premature-deletion class). **Re-derived §5.10** into an independent per-copy lifecycle: **§5.10.0** separates the **eight** concepts (L1 wait-for-text deadline, L2 batch cancellation, L3 staging copy, L4 workspace copy, L5 operation records, L6 read evidence, L7 end-of-use, L8 deletion policy); **§5.10.1** gives **each physical copy** (C1 staging, C2 workspace, C3 recovery, C4 op rows, C5 local rows) its own owner/state/permitted-vs-prohibited deletion rule — **`expires_at` reclaims the staged/recovery copy ONLY, never the workspace copy**; **§5.10.2** defines the post-text delivery lifecycle independently of the 15-minute deadline; **§5.10.3** adds an **11-case crash/race analysis**; **§5.10.4** states the conservative retention fallback and its **storage-growth implication** plus the **owner decision (Q18)**; **§5.10.5** restates the client-side batch deadline. **R6-2 (MEDIUM, blocking):** pinned the **U-3 trust boundary** — new **§5.15.1** (trusted, **non-agent** service-side issuer; agent/tool/prompt-produced events are **never** evidence), **§5.15.2** (authenticated provenance, integrity, uniqueness/replay protection, authorization scope), **§5.15.3** (exact fields + 8 validation invariants; **complete-read vs agent-use** distinction) — with the issuer classified **NEW upstream capability** and **UNVERIFIED**; `delivered` stays unreachable until it exists. **R6-3 (LOW):** new **§5.15.4** + **U-10** — the Cloud `events/search` store is a **polled replica** (`poll_agent_servers`→`refresh_conversation`→`save_event`, sha256 `d239ec43…`); event-based evidence MUST come from a **quiesced** source or an agent-server re-verify. **R6-4 (LOW):** new **§5.15.5** + **U-11** — the agent-facing path MUST be **absolute** (file_editor `validate_path`/`is_host_absolute_path`, sha256 `a1d735d4…`); the r6 **relative** `delivered_path` is superseded; the producer-to-reader flow is proven implementable or classified new work. **R6-5 (INFO):** removed the stale "seven lifecycle facts"/"F1–F7"-as-current wording (header r5 notice + §13 r5 row marked **superseded**). Also strengthened **T-18/T-19** and added **T-22/T-23/T-24**; updated **I10/I12/I13/I14**; §5.9/§5.14.2 step 6/7/§5.14.4/§8.3; added **§12 Q18–Q21**; updated §1/§5.15 table (**U-10/U-11**)/§11/§13. **No security requirement, threat-model mitigation, or P0 invariant weakened; the lifecycle and trust rules were made *stricter* and *more explicit*.** Self-review: `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R7-SELF-REVIEW.md`. |
| r8 | 2026-11-11 | **r7 independent-findings remediation** under `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R8-R7-INDEPENDENT-FINDINGS-REMEDIATION`, driven by the **R7 independent adversarial review** (`docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R7-INDEPENDENT-ADVERSARIAL-REVIEW.md`, verdict **`NEEDS_REVISION`**, findings **R7-1 … R7-4**). **R7-1 (MEDIUM, blocking):** the "workspace is removed on conversation delete" C2-reclaim premise was **not** source-grounded and is **false** for grouped sandboxes — the Cloud delete finalizer **archives** the workspace (`_finalize_sandbox_delete` → `archive_conversation_workspace` → `archive_workspace`) and tears the **sandbox** down only when **no sibling references it**, and the agent-server delete **preserves** the workspace. r8 **withdraws** the premise, states that **today no conversation-scoped event reclaims C2**, defines the only physical-removal path as the **unmodeled sandbox/pod teardown** ("runtime-api idle reap", indefinitely delayed under grouping), adds a **grouping caveat**, and **strengthens** the disclosed unbounded-storage limitation (Q18) — **no cleanup primitive is invented**. Touches §5.10.1 (C2 row, cleanup eligibility, "Conversation ended/deleted"), §5.10.3 (case 10), §5.10.4, §5.9 (`expired`), §5.14.2 step 7, §5.14.4, §6 **T-19/T-24**, §8.1 **I12**, §9 **7b**, §10.1, §12 **Q18**, §11, §13. **R7-2 (MEDIUM, blocking):** the path contract resolved the workspace root from `_get_agent_server_context`, which exposes only `sandbox_spec.working_dir` (the **ungrouped base**) and whose `AgentServerContext` has **no** workspace-path field; the grouped root `{base}/{conversation_id.hex}` (`grouped_workspace_dir`) lives in the server-managed reserved tag `archiveworkspacepath`. r8 pins the **authoritative** root source and adds a **provenance/binding contract** (new **§5.15.6**, **U-12**, **I15**, **T-25**, **Q22**), correcting §5.14.2 step 3, §5.15.5, §7.0 (Q3 + reuse map), §7.1, §7.4, §10.1; the Cloud-side per-conversation root read is classified **NEW + UNVERIFIED** and the write **fails closed**. **R7-3 (LOW):** the polled-replica description was not universal — the poller runs **only when there is no public URL** (`web_url is None or 'localhost'`), else the store is fed by **webhooks**; r8 separates **authoritative** (agent-server log) from **replicated** (Cloud store) state in §5.15.4, updates **U-10**, and keeps the quiescence requirement on **both** paths. **R7-4 (INFO):** added the explicit, complete **L1–L8 ↔ F1–F7/F6a/F6b cross-map** (new **§5.10.0.1**) plus a §5.14.0 back-reference. **No security requirement, threat-model mitigation, or P0 invariant weakened; the lifecycle, provenance, and replica rules were made *stricter* and *source-grounded*.** Self-review: `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R8-SELF-REVIEW.md`. |
| r9 | 2026-11-11 | **r8 independent-findings remediation** under `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R9-R8-INDEPENDENT-FINDINGS-REMEDIATION`, driven by the **R8 independent adversarial review** (`docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R8-INDEPENDENT-ADVERSARIAL-REVIEW.md`, verdict **`NEEDS_REVISION`**, findings **R8-1 … R8-4**). **Documentation-only; no security requirement, threat-model mitigation, or P0 invariant weakened.** **R8-1 (MEDIUM):** the physical-removal path for the workspace directory is **modeled in the pinned source** for the **managed** backends — `OpenHands/enterprise` ships a wired **sandbox-lifecycle** subsystem (`sandbox/lifecycle/{__init__,settings,sweep,rules,tasks}.py`, `worker/app.py`) with `delete_after_seconds` (default 10 days; "Delete a sandbox, and its workspace, once it has not run for this long") → `sandbox_service.delete_sandbox(...)`, while the **Cloud/remote** backend is **delegated to runtime-api** (`lifecycle/__init__.py`); r9 **corrects** the r8 "unmodeled / outside the pinned repos" wording, states the **applicability limit** (managed-only; not an F7 signal; does not prove a conversation's terminal state), and **preserves** the "no conversation-scoped event reclaims C2" invariant and the C2-not-deleted-while-in-use rule. Touches §5.10.1 (C2 row, cleanup eligibility, "Conversation ended/deleted"), §5.10.0.1 (L4), §5.10.4, §5.9 (`expired`), §5.14.2 step 7, §5.14.4, §6 **T-19/T-24**, §8.1 **I12**, §9 **7b**, §12 **Q18**, §11, §13. **R8-2 (MEDIUM):** the Cloud-side per-conversation workspace-root **read already exists and ships** (`AppConversationInfo.repositories` → `conversation_repositories`; live `AppConversation.repositories.path`), so r9 **re-scopes** U-12 to the **identity/authorization binding** only (the tag→root read is existing) while keeping the **fail-closed** rule and the "existence ≠ authorized/immutable/safe" caveat. Touches §5.14.2 step 3, §5.15.5, §5.15.6, §5.15 **U-12**, §7.0 (Q3 + net-new), §7.1, §7.4, §6 **T-25**, §8.1 **I15**, §12 **Q22**, §11, §13. **R8-3 (LOW):** corrected citation defects — the `bb9bbe23…` hash is the **enterprise** `sandbox/sandbox_router.py` (sandbox-server is `07fef71e…`); the archive module is `workspace_archive.py`; the garbled §2.2 sentence is fixed. **R8-4 (INFO):** refreshed the live Cloud V1 identifier to `info.version = 1.91.0`, 244 paths, sha256 `f0f4d4e9…` (was `1.87.1`/242/`0086b0b0…`), **re-confirming** the "no Cloud upload" conclusion (route evidence unchanged; version string is not the basis). Self-review: `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R9-SELF-REVIEW.md`. |
| r10 | 2026-11-11 | **r9 independent-findings remediation** under `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R10-R9-INDEPENDENT-FINDINGS-REMEDIATION`, driven by the **R9 independent adversarial review** (`docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R9-INDEPENDENT-ADVERSARIAL-REVIEW.md`, verdict **`NEEDS_REVISION`**, findings **R9-1 … R9-4**). **Documentation-only; no security requirement, threat-model mitigation, or P0 invariant weakened; no cleanup primitive invented.** **R9-1 (MEDIUM):** r9 correctly documented the Enterprise sandbox-lifecycle mechanism (a **separate** infrastructure timer, `delete_after_seconds`) but left **absolute** statements ("no timer deletes C2", "C2 is never timer-deleted", "the only server-side clock is `expires_at`") that contradicted it; r10 **scopes every such statement** — the **operation's `expires_at`** reclaims **C1/C3 only** and never deletes **C2**, while a **separate** infrastructure timer (Enterprise sandbox lifecycle) **may** remove the sandbox **and its workspace** in governed environments; the two clocks are **distinct and must not be conflated**; applicability to the **Cloud/runtime-api** backend is **delegated** and **not assumed**; and no infrastructure lifecycle timer proves a conversation reached a safe terminal-use state. The **C2-must-not-be-deleted-while-in-use invariant is preserved** (it binds the **application**; it does **not** claim the application can prevent external infrastructure deletion). Touches §5.9, §5.10.1 (C2 row), §5.10.2, §5.10.3 (case 4 + invariant), §5.10.4 (storage-growth bullet), §8.4, §6 **T-24**, §12 **Q18**, §11(f), §13. **R9-2 (LOW):** corrected the `RESERVED_TAG_KEYS` source line in §11 from "line 96" to **line 86** (line 96 is `def _validate_caller_tags(...)`, the validator that **uses** the constant); §5.15.6 already cited line 86; no validation behavior or security contract changes. **R9-3 (LOW):** qualified the modeled teardown — the verified mechanism is **container removal** (`container.remove()`), and whether the **underlying workspace data** is physically deleted depends on the **mount layout** (container-local vs host bind-mount; `mounts` empty by default, deployment-configurable), so **physical deletion for all configurations is UNVERIFIED / SOURCE REQUIRED**; container removal, mounted data, physical file deletion, and any external storage lifecycle are separated explicitly; the R8-1 correction stands (the removal path **is** modeled). Touches §5.10.1 (C2 row), §5.10.4. **R9-4 (INFO):** labelled the r8-era spec digest `1.87.1` / 242 paths / sha256 `0086b0b0…ff77916` as a **historical reported value — NOT INDEPENDENTLY VERIFIED** (retained for audit history only; **not** used as evidence for current route behavior; the current evidence is the re-verified `1.91.0` / 244 paths / `f0f4d4e9…`). Touches §1 (R8-4 note), §2.1, §2.2, §11. Self-review: `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R10-SELF-REVIEW.md`. |
| r11 | 2026-11-11 | **r10 independent-findings remediation** under `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R11-N10-FINDINGS-REMEDIATION`, driven by the **R10 independent adversarial review** (`docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R10-INDEPENDENT-ADVERSARIAL-REVIEW.md`, verdict **`PASS_WITH_NOTES`**, findings **N10-1 … N10-3**). **Documentation-only; no security requirement, threat-model mitigation, or P0 invariant weakened; no cleanup primitive invented; no previously resolved finding reopened.** All three findings are **citation/labelling** corrections; **no technical claim changes**. **N10-1 (LOW):** the file_editor missing-path rejection was cited inconsistently as "line 691" (§5.15.5) and "line 693" (§11); r11 re-fetched `openhands-tools/…/tools/file_editor/editor.py` at the pinned SDK SHA `9f7d5cb1…` (sha256 `a1d735d4…`) and states the **symbol** (`validate_path` missing-path guard) with the **verified line range 689-694** (condition `if command != "create" and not path.exists():` at line 689; `raise EditorToolParameterInvalidError(…)` at line 690) in **both** places. Touches §5.15.5, §11. **N10-2 (LOW):** the "agent-server delete preserves the workspace" citation (`conversation_service.py`, sha256 `9e9b3e63…`, line 1911) was listed under the **`OpenHands/enterprise`** bullet in §11; the file actually belongs to **`OpenHands/software-agent-sdk@9f7d5cb1…`** (`openhands-agent-server/openhands/agent_server/conversation_service.py`; re-verified: sha256 `9e9b3e63…`, 3132 lines, `delete_conversation` line 1863, preserve-workspace comment line 1911) — `OpenHands/enterprise` has no such file. r11 **moves** the citation to the SDK bullet; the technical claim is unchanged. Touches §11. **N10-3 (INFO):** §2.2 still wrote "r8 evidence `1.87.1`" without a verification status; r11 qualifies **every** occurrence (header R8-4 note, §2.1 table, §2.2 ×3, §11) so the **historical** r8 value (version string **and** the unavailable digest) is explicitly labelled **NOT INDEPENDENTLY VERIFIED** and clearly distinguished from the **current** re-verified evidence (`1.91.0`, 244 paths, `f0f4d4e9…`), and no historical value supports a current capability claim. Touches §1 (header R8-4 note), §2.1, §2.2, §11. Self-review: `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R11-SELF-REVIEW.md`. **Next required step: a fresh independent adversarial review (this self-review is not independent approval).** |

| r12 | 2026-11-11 | **r11 independent-findings remediation** under `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R12-N11-CITATION-REMEDIATION`, driven by the **R11 independent adversarial review** (`docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R11-INDEPENDENT-ADVERSARIAL-REVIEW.md`, verdict **`PASS_WITH_NOTES`**, findings **N11-1 … N11-3**). **Documentation-only; no security requirement, threat-model mitigation, or P0 invariant weakened; no cleanup primitive invented; no previously resolved finding reopened.** All three findings are **line/attribution precision** corrections; **no technical claim changes**. **N11-1 (LOW):** `additional_repositories.py` cited the `path=f'{working_dir}/{folder}'` build at "line 89" (which is the `def conversation_repositories(` definition); r12 re-fetched the pinned `OpenHands/enterprise@3fac53df…` file (sha256 `a8d0bbe3…`, 453 lines) and states the **symbol plus verified line range** — `conversation_repositories` def at line 89, the `path=f'{working_dir}/{folder}'` expression at **line 106** — at **every** occurrence. Touches §1 (r9/R8-2 notice), §5.15.6, §11. **N11-2 (LOW):** the `archiveworkspacepath` tag read was cited at "line 1185" (the comment `# Delete the sandbox in the background if no other conversations reference it`); the read is at **line 1188** (`workspace_path = app_conversation_info.tags.get(ARCHIVE_WORKSPACE_PATH_TAG_KEY)`) in the pinned `c43ed4f7…` router. r12 cites **line 1188** (noting line 1185 is the comment). Touches §11. **N11-3 (INFO):** the cron declaration was attributed to `sweep.py`; at the pinned revision the only `cron='* * * * *'` is in **`tasks.py`** (`834e9452…`, line 78, on the `sweep` job, `name='sweep'`, line 80), while **`sweep.py`** (`1d99bd1c…`, 57 lines) has **no** `cron` token and holds only candidate selection (`find_due_sandbox_ids`). r12 separates the scheduled-task declaration (`tasks.py` cron) from the sweep implementation (`sweep.py`) from the lifecycle behavior (`rules.py::decide` → `Action.DELETE` → `tasks.py` → `delete_sandbox`), and does not imply the cron declaration proves successful execution or physical workspace deletion. Touches §5.10.4, §11. Self-review: `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R12-SELF-REVIEW.md`. **Next required step: a fresh independent adversarial review (this self-review is not independent approval).** |
