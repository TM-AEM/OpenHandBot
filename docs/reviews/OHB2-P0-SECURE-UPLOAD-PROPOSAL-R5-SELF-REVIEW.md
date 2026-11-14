# OHB2-P0-SECURE-UPLOAD-PROPOSAL-R5 — HOSTILE SELF-REVIEW

**Task ID:** `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R5-REVIEW-FINDINGS-REMEDIATION`

**Reconciliation note (added by `OHB2-P0-R5-DELIVERABLES-AND-SCOPE-RECONCILIATION`).** This file did
**not** exist when the R5 remediation task reported completion; it is created here from the **actual**
r4 independent review, the **actual** r5 proposal text, and the changes that can be established from
the repository. No test outcome, source semantic, or historical evidence is fabricated; every claim
that could not be verified is marked **UNKNOWN** (§6).

This is the **author's own hostile consistency review** of the r5 proposal
(`docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md`). It is **not** an independent
review: the r4 findings were remediated by the same agent that wrote r5, so this document is
**self-assessment**, not independent assurance. An independent adversarial review of r5 is still
required (§9 criterion 10 of the proposal).

- **Repo:** `TM-AEM/OpenHandBot` · **branch** `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW` ·
  **HEAD** `907b20de3fa6627795c14f29677e9f39c68e82f4` · **origin/main** `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c`.
- **r5 proposal SHA-256:** `6008c3ab44149b4a4cd9988fb9760752a92b9c38caf86672557f133341227085` (1840 lines).
- **Driving review:** `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R4-INDEPENDENT-ADVERSARIAL-REVIEW.md`
  (sha256 `ce13bc944ecdb44d773cd0f6ce9a16c38fea23438781657cc21c9ad584112ef3`), verdict **`NEEDS_REVISION`**.
- **Scope:** documentation only. No code/test/schema/runtime change. **P0 is NOT implemented.**
- **Method:** read the R4 review §12 (exact corrections) and §9 (findings) in full; verified each
  r5 change against the proposal text and against the pinned public source (re-fetched this session);
  then attempted to *break* r5 on the axes the review lists (H-1a, M-2-res, S-1, M-3b, M-4b, H-1b,
  H-1c, S-2, S-3).

---

## 1. Evidence re-verification (this session, read-only)

| Evidence | Source (pinned) | Result |
| --- | --- | --- |
| `ActionEvent.tool_call_id` + `tool_call.arguments` (JSON string) exist; action recorded **before** the tool runs | `OpenHands/software-agent-sdk` `event/action.py` (`ActionEvent` fields: `tool_name`, `tool_call_id`, `tool_call: MessageToolCall`); `llm/message.py` (`MessageToolCall.arguments: str`) | **MATCH** (H-1a) |
| `ObservationEvent` carries `tool_call_id` + `action_id` (correlation) and a result `observation` | `…/event/observation.py` (`ObservationBaseEvent.tool_call_id`; `ObservationEvent.action_id`) | **MATCH** (H-1a) |
| `AgentErrorEvent` exists as an **error** observation (agent-scaffold error), not a success | `…/event/observation.py` (`AgentErrorEvent(source="agent", error, classification, validation_errors)`) | **MATCH** (H-1a) |
| Cloud event store parses `ActionEvent`/`ObservationEvent` kinds and is queryable via `GET …/events/search` | `OpenHands/enterprise` `event/event_parsing.py` (branches on `kind == 'ActionEvent'` / `'ObservationEvent'`), `event/event_router.py` (`search_events`, `kind__eq`), `event/event_service_base.py` | **MATCH** (H-1c) |
| Cloud **durable** message-accept route exists | `enterprise` `pending_messages/pending_message_router.py` + `pending_message_service.py` (`StoredPendingMessage` + `db_session.commit()`; 429 > 10) | **MATCH** (H-1c) |
| Cloud `send-message` is a **thin proxy** (no durable write) | `enterprise` `app_conversation_router.py` `send_message_to_conversation` → `httpx.post(.../events)` | **MATCH** (M-2-res) |
| Agent-server message model is text/image only (no generic file block) | `software-agent-sdk` `llm/message.py` `Message.content: Sequence[TextContent \| ImageContent]` | **MATCH** (H-1) |

**Source-revision note:** the pinned SHAs used at r2–r4 are unchanged; the sources above were
re-fetched from the same pinned revisions this session. The live Cloud V1 spec remains `1.87.1`,
242 paths, **no** upload operation.

---

## 2. Remediation mapping — all eight R4 §12 corrections

The R4 review §12 lists **eight** required corrections. Each is mapped to the finding and to the
exact r5 location. "RESOLVED (as a contract)" means the text now states the rule unambiguously; it
does **not** mean the upstream capability exists.

| # | R4 §12 correction (finding) | r5 location | r5 action | Self-assessment |
| --- | --- | --- | --- | --- |
| **1** | Define the read evidence precisely — a **successful** read, exact event kinds/fields (**H-1a**, MEDIUM) | §5.14.0 (new, seven facts F1–F7); §5.14.2 step 6; §5.9 `delivered`; §7.5; §10.1; §6 T-18/T-19; §8.1 I12/I14; §9 7c | Added §5.14.0; step 6 now requires an `ObservationEvent` correlated by `tool_call_id`/`action_id` to an `ActionEvent` naming `delivered_path` with a **non-error** result; bare `ActionEvent` (F4) and `AgentErrorEvent` ⇒ **not** `delivered`; F7 not modeled | **RESOLVED (as a contract).** Residual uncertainty on the *sufficiency* of a non-error observation is stated in §3.1 and §6. |
| **2** | Remove the §7.5 self-contradiction on `consumed_at` (**M-2-res**, MEDIUM) | §5.9.1 (rewritten); §7.5 | One definition: `consumed_at` = message-accept marker, set **only** on a **durable** accept; **not** set by the thin-proxy `send-message`; would be set by the NEW durable step (U-2) if adopted | **RESOLVED.** §5.9.1 and §7.5 now agree. |
| **3** | Reconcile the `accepted`/staging-timing contradiction (**S-1**, MEDIUM) | §5.5; §5.9 (state table + notes); §9 7b/7c; §10.1; §12 Q13 | Staging is **synchronous within the create request**; a successful create returns **`stored`**; `accepted` is **internal-only and never returned**; status never reports `accepted` | **RESOLVED.** §5.5 and §5.9 now agree. |
| **4** | Align the delivered-copy reclaim rule (**M-3b**, LOW) | §5.10 (rewritten per-artifact); §5.9 `delivered` row | On `delivered`, only the **staging** copy is reclaimed; the **delivered** copy persists; the r4 "reclaim the delivered copy" wording is **withdrawn** | **RESOLVED.** §5.9 and §5.10 now agree. |
| **5** | Make the correlation guarantee unconditional (**M-4b**, LOW) | §5.4 (field); §5.6; §5.8 (409 code); §5.16; §6 T-21 (new) | `client_operation_id` is **required** (UUID); unique per `(principal, conversation_id)`; same key + same payload ⇒ same operation; different payload ⇒ **409 `client_operation_id_conflict`** | **RESOLVED.** |
| **6** | Tie "normal file tools" to the confined workspace root (**H-1b**, LOW) | §5.14.2 step 5 | `delivered_path` is **workspace-relative** and resolved by the agent's tools against the same confined workspace root that `bind_local_conversation_runtime` enforces | **RESOLVED.** |
| **7** | Re-frame "NEW capability" vs composition of existing primitives (**H-1c**, LOW) | §5.14 (status block); §5.14.1 (classification table); §5.15 (Status column U-1…U-9); §11 (e); §12 Q14 | Documents the **existing durable** primitives (`POST /api/v1/conversations/{id}/pending-messages`; `GET /api/v1/conversation/{id}/events/search`) as composable; new = attachment op, server-to-server materialization, delivery authorization, successful-read **rule** | **RESOLVED.** |
| **8** | Note the outbox has no upload item type (**S-2**); state write atomicity + file mode/owner (**S-3**) | §8.3 (S-2 boundary); §5.14.2 step 4 + §7.4 (S-3) | §8.3 states the outbox carries **text only** (new payload capability required, U-9); §7.4 lists atomic publish (`temp` + `os.replace`), readable mode/owner (UNVERIFIED), partial-write cleanup, cross-conversation isolation | **RESOLVED (as a contract).** File mode/owner remains UNVERIFIED (§6). |

**Mapping coverage:** 8/8 R4 §12 corrections are addressed; the nine findings they derive from
(H-1a, M-2-res, S-1, M-3b, M-4b, H-1b, H-1c, S-2, S-3) are each covered. The R4 review recorded
**no CRITICAL/HIGH** finding; r5 adds **one** threat row (T-21) and **weakens none**.

---

## 3. Semantics that must not be over-read

### 3.1 "Successful read" — what r5 actually claims, and the residual uncertainty

r5 (§5.14.2 step 6) defines **F6 = successful read** as: an `ObservationEvent` that is (a)
**correlated** (`tool_call_id`/`action_id`) to an `ActionEvent` whose `tool_call.arguments` name
`delivered_path`, **and** (b) a **non-error** observation for that action; an `AgentErrorEvent`, a
`UserRejectObservation`, an error result, a missing correlated observation, or an ambiguous sequence
⇒ **NOT** `delivered`.

**Honest limit (must not be over-read):** the presence of a **non-error** `ObservationEvent`
correlated to a path-naming `ActionEvent` is a **necessary** condition, but it is **not, by itself,
proof that the file contents were successfully read**. A tool can return a *non-error* observation
whose payload is e.g. "file not found" or an empty/partial read (a non-error observation string is
not guaranteed to be a successful content read). The precise mapping from an observation payload to
"contents read" is **tool-specific** and is **not established by the pinned source** — this is
recorded as an **UNKNOWN / residual uncertainty** (§6). r5's rule is therefore **stricter than r4**
(it rejects the F4-only and error cases) but **not a proven-complete** detector of a successful read.
The safe default in r5 (no positive evidence ⇒ stays `stored`, retained until `expires_at`) means the
residual uncertainty can only cause **over-retention**, never an early delete.

### 3.2 State consistency

- `accepted` is internal to the create request and **never returned** (§5.5, §5.9); observable
  non-terminal state after a successful create is **`stored`**.
- Terminal states: `delivered`, `rejected`, `failed`, `expired`; `stored` is non-terminal.
- `delivered` is reachable **only** with the §5.14.2 step 6 evidence (not decorative).
- `expires_at` is fixed at accept, never extended; after it, no non-terminal state is reported.

### 3.3 Crash windows

§8.3 traces **seven** crash boundaries (before intent; after intent before outcome; after outcome
before boundary advance; after boundary advance before dispatch; after dispatch before response;
after remote success before recording; restart with unknown outcome). The batch is not lost in any
window because the pending batch + dispatch intent are durable **before** the external call and the
ack boundary is **fail-closed** on ambiguity. **No exactly-once claim is made** (at-most-once).

---

## 4. Hostile attack attempts (attempts to break r5)

Each row: **attack attempted → what r5 says → residual risk / verdict.**

1. **"H-1a is fixed by words only."** Attack: does r5 actually change the rule, or reword r4? r5:
   it adds §5.14.0 (F1–F7) and rewrites step 6 to require **F6** and to reject F4 and
   `AgentErrorEvent`; the r4 "a run whose tool calls read the path" wording is explicitly replaced.
   **Verdict: rule changed.** Residual: F6 sufficiency limit (§3.1/§6).
2. **"`delivered` can still be set on a failed read."** Attack: can an `ActionEvent` + error path
   trigger `delivered`? r5 §5.14.2 step 6: a bare `ActionEvent` (F4) is **not** sufficient; an
   `AgentErrorEvent`/error result ⇒ **not** `delivered`. **Verdict: closed at the rule level.**
   Residual: a *non-error* observation that is not a successful content read (UNKNOWN, §6).
3. **"M-2-res: `consumed_at` is still claimed durable via `send-message`."** Attack: search r5 for
   the r4 wording. r5 §5.9.1 + §7.5 state `consumed_at` is **not** set by the thin proxy and would be
   set by the NEW durable step (or the existing durable `pending-messages` route) if adopted.
   **Verdict: closed.**
4. **"S-1: create can still return `accepted` with staging in flight."** Attack: is `accepted` a
   response state? r5 §5.5/§5.9: staging is synchronous; success returns `stored`; `accepted` is
   internal-only and never returned; §10.1 asserts no response reports `accepted`. **Verdict: closed.**
5. **"M-3b: cleanup deletes the delivered copy."** Attack: does anything reclaim the delivered copy
   on `delivered`? r5 §5.10: `delivered` reclaims **staging only**; the delivered copy persists for
   the life of the conversation. **Verdict: closed.**
6. **"M-4b: a caller can still be uncorrelated."** Attack: omit `client_operation_id`; reuse it with
   a different payload. r5 §5.4/§5.16: the field is **required**; reuse with a different payload ⇒
   **409 `client_operation_id_conflict`**; same key + same payload ⇒ same operation. **Verdict: closed.**
7. **"H-1b: the agent is told a path it cannot resolve."** Attack: is `delivered_path` resolvable by
   the agent's tools? r5 §5.14.2 step 5: it is **workspace-relative** and resolved against the same
   confined workspace root the route enforces. **Verdict: closed (contract).** Residual: actual
   materialization is upstream work (not implemented).
8. **"H-1c: r5 over- or under-credits existing primitives."** Attack: does r5 claim the read signal
   already exists, or that nothing exists? r5 §5.14.1 classifies pieces as **EXISTS / composable** vs
   **MISSING (new)**; §5.15 carries a Status column. **Verdict: balanced.** Residual: the exact
   `events/search` retention window/authorization is not specified here (out of scope, §6).
9. **"S-2: r5 assumes the outbox already carries uploads."** Attack: does r5 rely on an existing
   upload item type? r5 §8.3 states the outbox carries **text only**; attachment dispatch requires a
   new payload capability (U-9). **Verdict: closed (boundary stated).**
10. **"S-3: the delivered write is non-atomic / unreadable."** Attack: crash mid-write; wrong mode.
    r5 §7.4: atomic publish via `temp` + `os.replace`; readable mode/owner **required** (concrete
    mode UNVERIFIED). **Verdict: atomicity closed (contract); mode/owner UNVERIFIED (§6).**
11. **"r5 weakened a security requirement to make the story fit."** Attack: diff the threat model and
    invariants. r5 **adds** T-21 and refines T-18/T-19; **no** T-row or invariant mitigation is
    weakened; I1–I14 intact. **Verdict: no weakening.**
12. **"r5 mutated r4/r3 identity or earlier reviews."** Attack: was an earlier review changed? The r5
    change is in-place on the **same proposal** (r4→r5), documented by the §13 r5 row; the r4 review
    (sha256 `ce13bc94…`) and the r3/r2 reviews are unchanged. **Verdict: intended revision; earlier
    reviews untouched.**

**Attempts with evidence: 12** (≥ the required eight).

---

## 5. Owner decisions (explicit, not silently assumed)

The r5 proposal keeps every affected decision open and flags it in §12 with why/options/evidence/
blocking status. The task-named items are:

| Q | Topic | r5 §12 reference | Status |
| --- | --- | --- | --- |
| **Q3** | Size/type/count limits triple (mutually inconsistent as proposed) | §12 item 3 | **Open (owner)** |
| **Q5** | Ref resolution (5a) + agent-readable delivery (5b) + exact `delivered` rule (5c, new r5) | §12 item 5 (5a/5b/5c) | **Open (owner)** |
| **Q7** | Idempotency (`Idempotency-Key` + `sha256` dedup window; delivery idempotency) | §12 item 7 | **Open (owner)** |
| **Q10** | Independent security review (who; release gate?) | §12 item 10 | **Open (owner)** |
| **Q11** | Product decision: implement P0 or keep the fail-closed rejection | §12 item 11 | **Open (owner)** |
| **Q12** | `consumed_at` semantics + durable-accept trade-off; which durable route sets it | §12 item 12 | **Open (owner)** |
| **Q13** | `uploading`/`delivering` re-introduction (settled r5: staging synchronous; `accepted` internal) | §12 item 13 | **Open (owner)** |
| **Q14** | Delivery mechanism (design A recommended) + whether to extend `send-message` | §12 item 14 | **Open (owner)** |
| **Q15** | Durable message-accept: reuse existing `pending-messages`, add a step on `send-message`, or drop `consumed_at` | §12 item 15 | **Open (owner)** |
| **Q16** | Availability/trustworthiness of the F6 successful-read signal; fallback retention-until-expiry | §12 item 16 | **Open (owner)** |
| **Q17** | Correlation contract (`client_operation_id` required + server `operation_id`) | §12 item 17 | **Open (owner)** |

None of these is resolved silently. (Q1, Q2, Q4, Q6, Q8, Q9 also remain open in §12 but were not
named in the reconciliation task.)

---

## 6. UNKNOWN / unverifiable items (honest)

- **Byte-level r4→r5 diff:** the proposal is **untracked** in Git; no r4 (or r3) baseline copy exists
  in any Git object, stash, or on disk (verified this session). The r4→r5 change set is therefore
  established **semantically** (r5 text + the R4 review's §12 corrections + the §13 r5 row), **not**
  by a byte diff. **UNKNOWN.**
- **`ObservationEvent` non-error ⇒ successful read:** the exact mapping from a non-error observation
  payload to "file contents successfully read" is **tool-specific and not established** by the pinned
  source. r5's F6 is necessary, not proven-complete (§3.1). **UNKNOWN.**
- **Delivered-file mode/owner readability:** whether the default umask/uid makes the materialized file
  readable by the agent's runtime user is **not established**; r5 §7.4 requires the property but does
  not fix a concrete mode. **UNKNOWN (owner/implementation).**
- **Deployed `enterprise` commit:** attribution is from public `main` + live route/description match,
  not a deployed-SHA read. **UNKNOWN (unchanged from r3/r4).**
- **`events/search` retention window / authorization semantics** for the read-evidence query are not
  specified in this proposal. **UNKNOWN (out of scope).**
- **Whether `ImageContent`-as-attachment persists:** **UNKNOWN** (unchanged; images only, irrelevant
  to H-1).
- **No tests were executed** (documentation-only task; no upstream capability exists to test).

---

## 7. Self-assessment verdict

**All eight R4 §12 corrections (findings H-1a, M-2-res, S-1, M-3b, M-4b, H-1b, H-1c, S-2, S-3) are
addressed as documentation contracts**, with exact r5 section references (§2). The r5 state model is
internally consistent (§3.2), the crash windows are traced (§3.3), and the central read-evidence rule
is **stricter than r4** — though its sufficiency remains an acknowledged UNKNOWN (§3.1/§6). No
security requirement, threat-model mitigation, or P0 invariant was weakened (one threat row added).
This document is **self-review only**; an **independent adversarial review of r5 is required** before
the proposal can be considered approved (§9 criterion 10).

**Verdict: `SELF_REVIEW_COMPLETE_WITH_EXPLICIT_UNKNOWNS`.** P0 is **NOT implemented**.
