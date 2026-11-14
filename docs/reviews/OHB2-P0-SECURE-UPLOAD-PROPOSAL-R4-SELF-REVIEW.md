# OHB2-P0-SECURE-UPLOAD-PROPOSAL-R4 — HOSTILE SELF-REVIEW

**Task ID:** `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R4-CRITICAL-GAP-REMEDIATION`

This is the **author's own hostile consistency review** of the r4 proposal
(`docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md`). It is **not** an independent
review: the r3 adversarial findings were remediated by the same agent that wrote r4, so this document
is **self-assessment**, not independent assurance. An independent adversarial review is still
required (§9 criterion 10 of the proposal).

- **Repo:** `TM-AEM/OpenHandBot` · **branch** `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW` ·
  **HEAD** `907b20de3fa6627795c14f29677e9f39c68e82f4` · **origin/main** `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c`.
- **Scope:** documentation only. No code/test/schema/runtime change. **P0 is NOT implemented.**
- **Method:** read the r3 independent adversarial review in full; re-verified its evidence against
  pinned public source; revised the proposal; then attempted to *break* r4 on the axes the review
  lists (H-1 + M-1 … M-5 + L-1…L-4/I-1).

---

## 1. Evidence re-verification (this session)

| Evidence | Source (pinned) | Result |
| --- | --- | --- |
| Cloud `send-message` is a **thin proxy** (no durable write) | `OpenHands/enterprise` `app_conversation_router.py` `send_message_to_conversation` → `httpx.post(.../events)` → `AppSendMessageResponse(success, sandbox_status)` | **MATCH** (M-2) |
| Agent-server message model is text/image only | `software-agent-sdk@9f7d5cb1…` `event_router.py` (`/events` → `send_message`) + `event_service.py::send_message` → `_conversation.send_message`; `openhands-sdk` `llm/message.py` sha256 `1b9f0693…` = `Message.content: Sequence[TextContent \| ImageContent]` | **MATCH** (H-1) |
| `ImageContent.image_urls: list[str]` (required) | `software-agent-sdk@9f7d5cb1…` `llm/message.py` | **MATCH** (images only) |
| Agent-server event append is a durable agent-server step | `event_service.py::send_message` docstring + `save_meta`/`_persisted_events` in the same module | **MATCH** |
| `rejected` observability gap | r3 §5.5/§5.8/§5.9 (validation can precede any `operation_id`) | **CONFIRMED** (M-4) |
| Per-operation `expires_at` vs client-only batch deadline | r3 §5.4/§5.9/§8.1 I4/I6 | **CONFIRMED** (M-5) |

**Source-revision note:** pinned SHAs are unchanged from r2/r3; `OpenHands/enterprise` `main` was
`3fac53df…` at r3 time. The live Cloud V1 spec is still `1.87.1`, 242 paths, no upload.

---

## 2. Finding-by-finding self-assessment

| Finding | r4 action | Self-assessment |
| --- | --- | --- |
| **H-1** (HIGH) inert `stored_path_ref` | new **§5.14** (existing-mechanism audit, materialization design, alternatives, required answers); §5.1/§1/§3/§4/§9/§11/§12 Q5b updated; invariant **I14** | **RESOLVED (as a contract).** The ref is resolved + authorized by the Cloud and **materialized** in the workspace at a concrete `delivered_path`; the agent reads it with normal tools; `delivered` requires **agent-server read evidence**. Explicitly marked **NEW upstream capability** (owner decision Q14) — not claimed to exist. |
| **M-1** (MEDIUM) ack vs cleanup ordering | new **§8.3** (durable ordering + 7 crash windows); §8.1 I13, §8.2 S3/S10, §5.10 | **RESOLVED (as a contract).** Dispatch intent durable **before** the external call; ack boundary fail-closed on ambiguity; cleanup decoupled from the Telegram ack. No exactly-once claim. |
| **M-2** (MEDIUM) "durable accept" not backed by source | §2.2, §5.9.1 corrected; §5.15 **U-2**; §7.5; §11 (d) | **RESOLVED.** The thin-proxy fact is stated; a durable Cloud accept step is **new work**; `consumed_at` is demoted. |
| **M-3** (MEDIUM) cleanup deletes while reading | §5.10 rewritten (evidence-based); §5.9 state model adds **`delivered`**; §9 7b; §11 (f) | **RESOLVED.** Deletion requires **`delivered`** (read/ingestion confirmed) or `expires_at`; never `consumed_at` alone. Fallback (no evidence signal) = retention-until-`expires_at` (Q16). |
| **M-4** (MEDIUM) `rejected` unobservable | new **§5.16**; §5.4 (`client_operation_id`), §5.5 (op row before staging), §5.6, §5.8 (error correlation) | **RESOLVED.** Pre-operation rejection = structured error echoing `client_operation_id`, no `operation_id`; post-row rejection = terminal `rejected`. State machine made consistent with the create contract. |
| **M-5** (MEDIUM) per-op vs batch deadline | §5.9 `expires_at` note; new **§8.4**; §5.15 **U-5** | **RESOLVED.** Server has **no batch concept**; the batch deadline is client-side (`T0`, first file) and never extended by an operation's `expires_at`; multi-file batch → multiple operations, one batch deadline. |
| **L-1** (LOW) stale-ref/expiry race | §5.9.1, §8.4 | **RESOLVED.** Stale ref ⇒ treat as expired + **notify** + **no retry**. |
| **L-2** (LOW) partial staging on crash | §5.10 | **RESOLVED.** Partial staging removed on the `failed`/`expired` transition. |
| **L-3** (LOW) derive-on-read clock mixing | §5.9 | **RESOLVED.** The **server** status is authoritative; the client must not self-expire on its own clock. |
| **L-4** (LOW) legacy key weakness parity | §5.13 | **RESOLVED.** Explicit parity note added. |
| **I-1** (INFO) no `send-message` idempotency key | §5.9, §5.15 **U-6** | **RESOLVED (noted).** Risk stated; bot must not blind-retry a message; optional future upstream addition. |

---

## 3. Hostile attack attempts (attempts to break r4)

Each row: **attack attempted → what r4 says → residual risk / verdict.**

1. **"H-1 is solved by prose, not by a mechanism."** Attack: §5.14 could be hand-waving. r4: it names
   the resolver (Cloud), the authorizer, the conversation-identity check, the materialization write
   (`O_NOFOLLOW`/`O_EXCL`, server-generated path), the point of access, the read-evidence source
   (agent-server event log), and the failure modes — and marks the whole contract **NEW upstream
   work** (Q14). **Verdict: honest.** Residual: it is a **proposal**, not implemented; a maintainer
   must confirm the mechanism (Q14).
2. **"`delivered` is just another decorative state (the R2-9 defect)."** Attack: is `delivered`
   reachable/observable? r4: `delivered` is reached **only** with materialization **and** agent-server
   read evidence (U-3); if that signal is unavailable the op stays `stored` and is reclaimed at
   `expires_at`. **Verdict: not decorative** — it has an entering event, an owner (Cloud attachment
   service), and a defined fallback.
3. **"M-1 still has a batch-loss window."** Attack: crash between the durable intent and the outbox
   dispatch. r4 §8.3 window 4: intent + boundary are durable ⇒ the outbox/recovery performs the
   dispatch exactly as recorded; window 5: a dispatched-but-unanswered call is `unknown` and is
   **never** auto-retried (at-most-once). **Verdict: no loss, no duplicate; no exactly-once claim.**
4. **"M-3: `consumed_at` still leaks into cleanup."** Attack: does anything still delete on
   `consumed_at`? r4 §5.10/§5.9.1/I12: deletion requires `delivered`/`expires_at`/`rejected`/`failed`;
   `consumed_at` is explicitly **demoted** and cannot authorize deletion. **Verdict: closed.**
5. **"M-4: a pre-row rejection is still ambiguous."** Attack: can a caller fail to correlate a
   rejection? r4 §5.16: the caller supplies `client_operation_id`, echoed in **every** response; a
   pre-row rejection carries that id and no server id; validation errors are a **definite** class.
   **Verdict: correlated.**
6. **"M-5: a multi-file batch extends the deadline."** Attack: does a new operation's `expires_at`
   move the batch deadline? r4 §8.4: the batch deadline is client-side `T0` (first file), persisted,
   never extended; the operation `expires_at` is only a server retention bound. **Verdict: closed.**
7. **"r4 weakened a security requirement to make the story fit."** Attack: diff the threat model.
   r4 **adds** T-16…T-20 and weakens **no** existing T-01…T-15; invariants I1–I13 are intact and I14
   is added. **Verdict: no weakening.**
8. **"r4 broke r3's identity / mutated r3."** Attack: is the r4 change in-place on the same file?
   The task is a **revision** (r3 → r4) of the same proposal; r3's *identity* is preserved by the
   revision-history row and the r4 correction notice (r1/r2/r3 rows intact, §13). No separate r3 file
   is mutated beyond the documented revision. **Verdict: intended (r3→r4 revision), as the task
   specifies.**

---

## 4. Residual open items (owner decisions, not silent assumptions)

- **Q14** — delivery mechanism (design A recommended) and whether to extend `send-message`.
- **Q15** — durable Cloud message-accept step (U-2) in scope, or drop `consumed_at`.
- **Q16** — availability of the read/ingestion evidence for `delivered` (else retention-until-expiry).
- **Q17** — hybrid correlation-id contract (`client_operation_id` + server `operation_id`).
- Plus r3's still-open **Q1–Q13** (ownership, scope mechanism, limits triple, reuse boundary, etc.).

None of these is resolved silently; each is flagged in §12 with why/options/evidence/blocking status.

---

## 5. Self-assessment verdict

**All 11 r3 findings (H-1 + M-1…M-5 + L-1…L-4 + I-1) are addressed as documentation contracts.** The
central H-1 gap is closed **as a specified, honest contract** — not as an implemented capability: the
delivery mechanism is explicitly **NEW upstream work** subject to owner decision **Q14**. No security
requirement, threat-model row, or P0 invariant was weakened. This document is **self-review only**;
an **independent adversarial review of r4 is required** before the proposal can be considered
approved (§9 criterion 10).
