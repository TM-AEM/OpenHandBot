# OHB2-P0-SECURE-UPLOAD-PROPOSAL-R4 — INDEPENDENT ADVERSARIAL REVIEW

**Task ID:** `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R4-INDEPENDENT-ADVERSARIAL-REVIEW`

Reviewer: fresh-context independent adversarial reviewer; **not** the author of the proposal, **not**
the author of the r4 self-review, and **not** the author of the r3 independent review. All actions
were **read-only**: public source and specs were re-fetched independently and re-hashed, **no
production call, no credential, no secret access, no file modification** — this review file is the
only artifact created. No commit/push/PR/merge/deploy, no branch change, no upstream issue/PR/
maintainer contact. The proposal, the self-review, and all previous reviews were **not** modified.

## Verdict: **NEEDS_REVISION**

r4 is a **major, honest improvement**: the H-1 gap is now **specified** (not hand-waved), the
`send-message` thin-proxy fact is corrected, cleanup is evidence-based, the batch deadline is moved
to the client, and the crash-window analysis is real. The security direction is sound and the
"NEW upstream capability" framing is honest. **But r4 is not yet ready for owner approval**, because
three of its own new statements are either **imprecise** or **mutually inconsistent**, and each
would cause a maintainer to implement a materially different (and less safe) thing than intended:

- **H-1a (MEDIUM):** the `delivered` **read/ingestion evidence** is defined only as "a run whose
  tool calls read `delivered_path`" — it does not name the exact event kinds/fields, and it does not
  require the read to have **succeeded**. An ActionEvent whose tool-call arguments contain the path
  exists even when the read **failed** (and the agent-server persists `AgentErrorEvent`/
  `ObservationEvent` for failures too), so `delivered` could be set — and bytes reclaimed — while the
  agent could **not** actually read the file. This is exactly the "inert-token false success" class
  (T-18) r4 set out to close.
- **M-2-residual (MEDIUM):** §7.5 still says `consumed_at` "is set by the Cloud when its
  `send-message` route **durably accepts** a message" — the same claim §5.9.1/§2.2 retract. The
  document contradicts itself.
- **S-1 (MEDIUM, new):** the M-4 change ("durably create the op row **before** staging; the create
  response reports **`accepted`**, staging may still be in flight") re-opens the very intermediate
  state r3 removed: §5.9's justification for the absence of `uploading` is "staging happens **within
  that request**", which is false under §5.5's own new wording.

Two further LOW inconsistencies and one INFO framing gap are listed in §9/§12. **All required fixes
are documentation-only; no new upstream evidence is needed (hence not `BLOCKED`).** **P0 remains
unimplemented.**

---

## 1. Baseline and file hashes

| Item | Value |
| --- | --- |
| Repository | `TM-AEM/OpenHandBot` |
| Branch | `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW` |
| HEAD | `907b20de3fa6627795c14f29677e9f39c68e82f4` |
| origin/main | `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c` |

**Working-tree status before review** (read only; nothing reset/cleaned/deleted):

```
 M .agent/PROGRESS.md
 M bot/handlers.py
 M docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md
 M docs/proposals/OHB2-TELEGRAM-ACK-ARCHITECTURE-ADR.md
?? docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R2-INDEPENDENT-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R3-INDEPENDENT-ADVERSARIAL-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R3-SELF-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R4-SELF-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-UPSTREAM-PROPOSAL-INDEPENDENT-ADVERSARIAL-REVIEW.md
?? tests/test_stage2_high_ack_blocking_fix.py
?? tests/test_stage4_f1_status_cost_operational_ack.py
```

**Artifacts under review (sha256, this session):**

| Artifact | Version | Lines | sha256 |
| --- | --- | --- | --- |
| `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md` | **r4** (header "Date" + §13 row `r4`) | 1512 | `93798997e4fe0de5d728d66e699ba27df4665778a5e4c83f609c06e3202e43aa` |
| `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R4-SELF-REVIEW.md` | r4 self-review (supporting evidence only) | 113 | `0afa0a2c3777fb6b5e50e777c8a45acd06bfd233860e5312913a5d129d6d57c9` |
| `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R3-INDEPENDENT-ADVERSARIAL-REVIEW.md` | r3 independent review (`NEEDS_REVISION`) | 396 | `150ca10479c4b7a49e983d7bae6b4e4db051bd257c31a13fa1ecf72b59c6ac01` |
| `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R3-SELF-REVIEW.md` | r3 self-review | 130 | `8b29fa19fbbb2735ef5b503d03d685d0ac344b8d87b930df4013407c0085cfc8` |
| `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R2-INDEPENDENT-REVIEW.md` | r2 review (`PASS_WITH_NOTES`) | 324 | `8d5153cae86526c653dac95b311974586523f546c2205261abdacab6009ab19e` |
| `docs/reviews/OHB2-P0-SECURE-UPLOAD-UPSTREAM-PROPOSAL-INDEPENDENT-ADVERSARIAL-REVIEW.md` | r1 review (`PASS_WITH_MAJOR_FINDINGS`) | 272 | `a9c858004858397ca2e5e1f3f077423d47e82a4763215b24bb85cb693e9e5728` |

**r4 identity confirmed:** header line 9 dates "r4 2026-11-11"; the r4 correction notice is present
after the r3 notice; §13 carries four rows (r1/r2/r3/r4). The proposal is **untracked**, so its
sha256 above is the only version anchor.

---

## 2. Actual diff review and limitations

### 2.1 r3 baseline — availability (LIMITATION, stated honestly)

The proposal is **untracked** (`git ls-files` → empty), there are **no** stashes, and **no** r3 copy
of the proposal exists on disk or in any Git object (only the r4 file exists at
`docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md`; `git log --all` shows only the
project commits, none containing the proposal). **Therefore a byte-level r3→r4 diff could not be
computed.** I did **not** invent one.

What **was** reconstructable and **was** used:

- The **r3 independent review** (this repo, `150ca104…`) records the r3 proposal's exact identity:
  sha256 `88fd400edd61cf4a6900bb2dea65cdefa95f791e3e7e2250344c2bd9a8537073`, **1112 lines**, and
  enumerates the r3 contract (state model `accepted|stored|rejected|failed|expired`; §5.9.1
  `consumed_at`; §5.13 legacy note; §8.1 invariants I1–I13; §6 threats T-01–T-15; acceptance items
  1–10; Q1–Q13).
- r4 is **1512 lines**; the r4 §13 row and the header correction notice **declare** the intended
  scope.

### 2.2 Scope verification (what could and could not be compared)

| Check | Method | Result |
| --- | --- | --- |
| r3 findings H-1 + M-1…M-5 + L-1…L-4 + I-1 all touched | search r4 for each finding id / its section | **PASS** — H-1 (§5.14), M-1 (§8.3), M-2 (§2.2/§5.9.1), M-3 (§5.10), M-4 (§5.16), M-5 (§8.4), L-1…L-4, I-1 all present |
| No earlier P0 invariant removed/weakened | r3 review enumerates **I1–I13**; r4 §8.1 has **I1–I14** | **PASS** — I1–I13 intact (r3 baseline enumerated in the r3 review), I14 added |
| No earlier threat row removed/weakened | r3 review enumerates **T-01–T-15**; r4 §6 has **T-01–T-20** | **PASS** — T-01–T-15 present, T-16–T-20 added |
| No earlier acceptance criterion removed | r3 review enumerates items 1–10; r4 §9 has 1–11 (7b/7c inserted) | **PASS** — 1–10 intact, 7b/7c/11 added |
| No r4 marker outside the declared sections | map every r4 marker to its section | **PASS (see below)** |
| No claim of P0 implementation introduced | grep for "is implemented / P0 complete" | **PASS** — none; §Status says "P0 is NOT complete" |

**r4-marker distribution (r4 edits are confined to the declared sections):** markers appear only in
the header, §1, §2.2, §3, §4, §5.4–§5.10 (+ §5.9.1), §5.13, §5.14 (new), §5.15 (new), §5.16 (new),
§6, §7.0/§7.1/§7.3/§7.4/§7.5, §8.1/§8.3 (new)/§8.4 (new), §9, §10.1/§10.2, §11, §12, §13. §2.1,
§2.3–§2.5, §5.1, §5.2, §5.3, §5.11, §5.12, §7.2, §7.6–§7.8 carry **no** r4 edits. **No unrelated
section was silently changed.**

**LIMITATION (honest):** the *byte-level* r3→r4 diff is **not verifiable** (baseline unavailable).
The scope verification above is **semantic** (r3's contract as recorded by the r3 review vs r4), not
a textual diff. A reviewer with the r3 artifact should confirm no unintended textual drift.

---

## 3. Source repositories, revisions, and file hashes

Re-fetched **this session** from public raw source at the pinned SHAs and re-hashed. Every
re-derivable hash **matches** the proposal's §11 (or the proposal's stated file identity).

| Source | Identifier | File (sha256 prefix) | Verified this session |
| --- | --- | --- | --- |
| `OpenHands/software-agent-sdk` | `9f7d5cb11b1256c1878f5584a657401feca9ad16` | `file_router.py` `13f0cae7…` | ✅ re-fetched |
| | | `runtime_router.py` `5bea70f0…` | ✅ re-fetched |
| | | `models.py` `57b3680c…` | ✅ re-fetched |
| | | `event_router.py` `6450a7c3…` | ✅ re-fetched |
| | | `event_service.py` `d59ff6e1…` | ✅ re-fetched |
| | | `openhands-sdk/…/llm/message.py` `1b9f0693…` | ✅ re-fetched |
| | | `openhands-sdk/…/conversation/request.py` + `message_request.py` `edab8b23…` | ✅ re-fetched |
| | | `openhands-sdk/…/conversation/state.py` `c991e774…`, `event_store.py` `40e707b3…`, `impl/local_conversation.py` `0227cf98…`, `io/local.py` `90a3c58f…` | ✅ re-fetched |
| `OpenHands/enterprise` | `3fac53df8c2efcb67ff3537d1162e8c8a108f565` | `app_conversation_router.py` `c43ed4f7…` | ✅ re-fetched |
| Live Cloud V1 OpenAPI | `app.all-hands.dev/openapi.json`, `1.87.1` | `0086b0b0…` | ✅ retained + re-parsed |

**Independently re-derived facts (not taken on trust):**

1. **Cloud `send-message` is a thin proxy with no durable Cloud write.** `enterprise`
   `send_message_to_conversation` (L600) does `httpx_client.post(f'{agent_server_url}/api/
   conversations/{conversation_id}/events', json={role, content, run}, headers={'X-Session-API-Key':
   sandbox.session_api_key}, timeout=30.0)`, then `response.raise_for_status()`, and returns
   `AppSendMessageResponse(success=True, sandbox_status=…)`. **No DB write.** ✅ (M-2 correct.)
2. **The agent-server event append is a real durable step.** `event_router.py::send_message`
   (POST `/conversations/{id}/events`) → `event_service.send_message(message, request.run)` →
   `await loop.run_in_executor(None, self._conversation.send_message, message)` →
   `local_conversation.send_message` → `_on_event(MessageEvent(...))` →
   `ConversationState.append_event` → `EventLog.append` → `FileStore.write` →
   `atomic_write_text` (write-temp + `os.replace`). ✅ (r4's §5.14 "durable agent-server step"
   claim is accurate.)
3. **The message model has no generic file block.** `SendMessageRequest.content:
   list[TextContent | ImageContent]`; `Message.content: Sequence[TextContent | ImageContent]`;
   `ImageContent.image_urls: list[str]` (required, data URLs). ✅ (H-1's premise correct.)
4. **The live Cloud exposes a *durable* pending-message route** not mentioned by r4:
   `POST /api/v1/conversations/{conversation_id}/pending-messages` — description: *"Queue a message
   for delivery when conversation becomes ready … Messages are **stored server-side** and delivered
   automatically when the conversation transitions to READY status"*; response
   `PendingMessageResponse{id, queued, position}`; 429 when >10 queued. **This is an existing durable
   Cloud message-accept step.** (See finding H-1c / M-2.)
5. **The agent-server event log is readable through existing Cloud routes.**
   `GET /api/v1/conversation/{conversation_id}/events/search` exists in the live spec with a
   `kind__eq` filter whose enum includes `ActionEvent` and `ObservationEvent`. **The read-evidence
   source for `delivered` is therefore reachable today via the Cloud**, which softens r4's "NEW
   capability" framing (finding H-1c).
6. **`send-message` has no idempotency key** (no `Idempotency`/`idempotency` token anywhere in the
   live spec; `send-message` params = `conversation_id` only). ✅ (I-1 correct.)
7. **The conversation-bound upload route confines by `path`/`workspace_dir`.** `runtime_router.py`
   `bind_local_conversation_runtime` rejects **422** unless the requested `path`/`workspace_dir` is
   absolute **and** `resolve().is_relative_to(workspace_root)`; the module docstring states these
   checks are *"routing safeguards, not a sandbox for arbitrary shell commands"*. ✅ (r2/r3 reuse
   claim correct.)
8. **`ActionEvent` carries the tool-call arguments verbatim.** `ActionEvent.tool_call:
   MessageToolCall{name, arguments: str(JSON)}`; `ObservationEvent{tool_name, tool_call_id,
   observation, action_id}`; `AgentErrorEvent`/`UserRejectObservation` also exist as
   `ObservationBaseEvent`. ⇒ **an ActionEvent exists whenever the LLM emits a read tool call,
   independent of whether the read succeeded** (load-bearing for finding H-1a).
9. **OpenHandBot's durable ack boundary already exists at runtime.** `bot/polling.py:84`
   (`get_acknowledgment_boundary`), `bot/polling.py:164` (`commit_batch_outcomes`), `bot/app.py:206`;
   ADR `OHB2-TELEGRAM-ACK-ARCHITECTURE-ADR.md` §18.1 defines the eligible outcome values
   (`durable_completed`, `durable_intent_recorded`, `explicitly_ignored`, `duplicate_completed`) and
   `partial_or_unknown` as **not** eligible (fail-closed). ✅ (§8.3's reuse claim is accurate.)

---

## 4. H-1 end-to-end content-delivery verification (§5.14 + §5.15/§5.16/§8.3/§8.4)

### 4.1 The 12-step lifecycle — traced against r4 and against source

| # | Step | r4 location | Verdict |
| --- | --- | --- | --- |
| 1 | Upload + validation | §5.4, §5.7 | **Specified** (limits PROVISIONAL, Q3) |
| 2 | Secure storage | §5.7 (`{ws}/.oh-attachments/{op}/{file_id}`, server-generated) | **Specified** |
| 3 | `stored_path_ref` creation/ownership | §5.9 (opaque handle) + §5.14.2 step 1 (Cloud owns resolution) | **Specified** |
| 4 | Conversation-scoped authorization | §5.3, §5.14.2 step 2, T-16 | **Specified** |
| 5 | Ref resolution | §5.14.2 step 1 | **Specified** |
| 6 | Materialization into the workspace | §5.14.2 step 4, §7.4 | **Specified** |
| 7 | `delivered_path` creation | §5.14.2 step 4 (`uploads/{operation_id}/{sanitized_display_name}`) | **Specified** |
| 8 | Message construction/delivery | §5.14.2 step 5 (message references the concrete path) | **Specified** |
| 9 | Agent observation of the message | §5.14.2 step 6 (message appended) | **Partially specified** (see §5 below) |
| 10 | Agent access to the file | §5.14.2 step 5 ("normal file tools") | **Under-specified** (see H-1b) |
| 11 | Evidence to mark `delivered` | §5.14.2 step 6, §5.9, §7.5 | **Imprecise** (H-1a) |
| 12 | Retention/cleanup | §5.10 | **Specified, with one contradiction** (M-3b) |

### 4.2 Critical evidence distinction (the task's core question)

The task asks what the available event record actually **proves**. Against source, the distinct
levels are:

| Level | What exists (source) | What it proves |
| --- | --- | --- |
| Event **constructed** | client-side | nothing durable |
| Event **accepted** by agent-server | `send_message` handler returns `Success()` | the request passed validation |
| Event **durably appended** | `EventLog.append` → `atomic_write_text` | the message is in the conversation event log |
| Event **made available to the agent** | the log is the agent's input on the next run | the agent *can* see it |
| Agent **observed the event** | a `MessageEvent` in the log + a run that consumed it | the model received the text |
| Agent **accessed the path** | an `ActionEvent` whose `tool_call.arguments` contain the path | the model **attempted** to read it |
| Agent **successfully read** | an `ObservationEvent` (correlated by `action_id`/`tool_call_id`) whose result is not an error | the read **succeeded** |

**r4's §5.14.2 step 6 collapses the last two levels.** It says `delivered` requires "a **run** whose
tool calls **read the delivered path** (the agent's file-read tool events)". Under source, an
`ActionEvent` exists for **every emitted read tool call**, including ones that **fail** (a failed
`file_editor`/`terminal` read still appends an ActionEvent whose arguments contain the path, plus an
`AgentErrorEvent`/error `ObservationEvent`). Therefore the definition as written **does not require a
successful read** — see finding **H-1a**. This is exactly the "inert-token false success" (T-18)
class r4 claims to close.

**Minimum upstream capability needed to establish the intended guarantee:** name the **exact**
event correlation — a **successful** read = an `ObservationEvent` (or the file-read tool's success
result) **correlated by `action_id`/`tool_call_id` to an `ActionEvent` whose arguments name
`delivered_path`**, with an explicit **error/`AgentErrorEvent` ⇒ not delivered** rule. The primitives
already exist (event kinds `ActionEvent`/`ObservationEvent`/`AgentErrorEvent` are all in the
agent-server event log, and `GET …/events/search` exposes them via the Cloud), so this is a
**specification-precision** fix, not new upstream machinery.

### 4.3 Security checks

| Challenge | r4 control | Assessment |
| --- | --- | --- |
| Server-generated path safety | §5.14.2 step 4; §7.4 | **Adequate** — client never supplies the delivered path; display name sanitized |
| Workspace containment | reuse `bind_local_conversation_runtime` (422) | **Adequate** (verified in source) |
| Symlink/TOCTOU | `O_NOFOLLOW` + `O_CREAT\|O_EXCL` + `resolve().is_relative_to` re-checked pre-write | **Adequate** |
| Cross-conversation ref access | ref bound to `(conversation_id, principal)` ⇒ 403 (T-16) | **Adequate** |
| Stale/revoked refs | ref valid only while non-terminal and within `expires_at`; revoked on terminal (T-16, L-1) | **Adequate** |
| Path collisions/overwrites | `O_EXCL` + `(operation_id, file_id)` keying | **Adequate** |
| File permissions/ownership | **not stated** | **GAP (LOW)** — the delivered file's mode/owner vs the agent's runtime user is unaddressed |
| Materialization atomicity | "write under confined base" | **Partial** — the write is not stated to be atomic (temp+rename); a crash mid-write could leave a truncated `delivered_path` (LOW) |
| Partial materialization after crash | §5.10 (L-2) covers **staging** partials, not **delivered** partials | **GAP (LOW)** |
| Cleanup races with active reads | §5.10 (only on `delivered`/`expires_at`) | **Adequate for staging**; **the `delivered` evidence flaw (H-1a) can cause an early reclaim** |
| Unauthorized reuse of `delivered_path` | server-generated; delivered copy is a normal workspace file | **Acceptable** (the file is intentionally agent-visible) |

### 4.4 Implementability

The materialization design (A) is implementable by **composing existing upstream primitives**: the
Cloud already resolves the runtime server-side (`_get_agent_server_context`), the confined
conversation-bound route already exists (`runtime_router.py`), the agent-server event log already
persists events and is already readable via the Cloud (`GET …/events/search`), and the Cloud already
has a **durable** pending-message route. What is genuinely **new** is: (i) the attachment operation +
its durable store, (ii) a **server-to-server delivery endpoint** that materializes the ref (U-1), and
(iii) the **precise** read-evidence rule (H-1a). r4's "NEW upstream capability" label is therefore
**correct for (i)/(ii)** but **under-credits the existing primitives** for (iii) — see H-1c.

---

## 5. Event-persistence versus agent-reading evidence analysis

- **Durable append is proven** by source (§3 fact 2). r4 correctly does **not** claim a proxy `2xx`
  proves durability of *Cloud* state (§5.9.1). ✅
- **Agent observation** (the model saw the message) is **not** separately modeled by r4. r4 treats
  "message appended" as sufficient for the observation half; that is defensible (the message is the
  agent's input), but r4 does not distinguish "appended" from "consumed by a run". The `delivered`
  definition's "message appended **and** a run whose tool calls read the path" implicitly assumes the
  run happened; a stricter contract would key on a run that **consumed** the MessageEvent.
- **Agent reading is the weak link (H-1a).** As shown in §4.2, the definition does not require a
  **successful** read, and it does not name the exact events/fields.
- **`delivered` has a real, durable, conversation-bound evidence source** — the agent-server event
  log, which is (a) durable (`atomic_write_text`), (b) conversation-bound (one log per conversation),
  and (c) already exposed via the Cloud (`GET …/events/search`). So the **source** is sound; only the
  **rule** is imprecise. This is the difference between "unsupported" (r3's H-1) and "imprecise"
  (r4's H-1a) — a material improvement, but not yet sufficient.

---

## 6. "delivered" state and lifecycle analysis

| State | Entry event | Owner | Durable | Observable | Restart | Terminal | Cleanup-eligible | Assessment |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `accepted` | create durably persists the row | Cloud attachment service | yes (row) | yes | survives; derive `expired` past `expires_at` | no | no | **Consistent with §5.5**, but see **S-1** |
| `stored` | staging completes | Cloud attachment service | yes | yes | survives | no | **no** (delivery unconfirmed) | Correct (M-3) |
| `delivered` | materialization **and** read evidence | Cloud attachment service | yes | yes | survives | **yes** | yes | **Evidence rule imprecise (H-1a)** |
| `rejected` | validation/policy refuse | Cloud attachment service | yes (row before staging, §5.16) | yes | n/a | yes | yes | **Fixed** (M-4) |
| `failed` | staging/delivery error after accept | Cloud attachment service | yes | yes | survives | yes | yes | Correct |
| `expired` | `expires_at` passes before `delivered` | service / derive-on-read | yes | yes | survives | yes | yes | Correct |

**Transitions:** `accepted → (stored | rejected | failed | expired)`, `stored → (delivered | failed |
expired)`. Monotonic; terminal states frozen. ✅

**Challenge — does `delivered` mean "read"?** Per §5.9's own table, `delivered` = "materialized **AND
agent read/ingestion confirmed**". The **intent** is right; the **definition** of "read" (§5.14.2
step 6) is the flaw (H-1a). r4 does **not** need more states — it needs the existing `delivered`
definition to require a **successful, correlated** read, and (optionally) to split "materialized"
from "read-confirmed" if the owner wants observability of the materialization step (r4 already emits
an `attachment.materialized` audit event, §5.11, so a separate state is **not** required). Avoid
unnecessary states: **agreed** — no new state needed; fix the evidence rule.

---

## 7. Crash-window analysis (§8.3, M-1)

r4 §8.3 defines the durable ordering (intent durable before the external call; ack boundary
fail-closed on `partial_or_unknown`) and traces seven crash windows. **Independently verified against
source/ADR:**

- The ack boundary and outcome vocabulary exist at runtime (`bot/polling.py:84,164`,
  `bot/app.py:206`; ADR §18.1). ✅
- The outbox is at-most-once (`bot/outbox.py`: `pending → claimed → sending`; ambiguous ⇒ `unknown`,
  never auto-retried; `MAX_OUTBOX_ATTEMPTS` bounds only pre-POST retries). ✅
- **No new DB/worker/scheduler is introduced** — §8.3 explicitly reuses the existing SQLite owner and
  the existing outbox/recovery; verified there is no second store in the design. ✅
- **No exactly-once claim** is made. ✅

**Residual (INFO):** §8.3 window 4 says "the **outbox** worker (or recovery) performs the dispatch
exactly as recorded" — but the current outbox dispatches **prompt text** (`bot/outbox.py` sends
`item.text`); it has **no attachment-upload item type**. The design assumes an upload-dispatch path
exists. This is acceptable **as an integration contract**, but it should be stated explicitly so a
maintainer does not assume the existing outbox already carries uploads.

**M-1 verdict: resolved as a contract.** No batch-loss window remains that is not covered by
durable-intent + fail-closed ack + at-most-once dispatch.

---

## 8. M-1 … M-5 verification table

| Finding | r4 correction | Independent verification (this session) | Resolved? | Residual |
| --- | --- | --- | --- | --- |
| **M-1** | §8.3 durable ordering + 7 crash windows; §8.1 I13; §8.2 S3/S10 | ADR §18.1 + `polling.py`/`app.py` confirm the boundary exists; `outbox.py` confirms at-most-once; no new DB/worker | **YES (contract)** | INFO: outbox has no upload item type |
| **M-2** | §2.2/§5.9.1 correct the thin proxy; §5.15 U-2 | enterprise `send_message_to_conversation` re-read: **thin proxy, no DB write** ✅ | **PARTIAL** | **§7.5 (L1079) still says `consumed_at` is set "when its `send-message` route durably accepts" — self-contradiction** |
| **M-3** | §5.10 evidence-based cleanup; §5.9 `delivered` | deletion gated on `delivered`/`expires_at`/`rejected`/`failed`; fallback retention-until-`expires_at` is safe (≤15 min) ✅ | **YES** | LOW: §5.9 table says `delivered` "permits reclaim of **the delivered copy**" vs §5.10 ("delivered copy retained for the life of the conversation") — contradiction; and the `delivered` evidence flaw (H-1a) can still cause an early reclaim |
| **M-4** | §5.16 correlation; §5.4/§5.5/§5.6/§5.8 | op row before staging makes `rejected` observable; `client_operation_id` echoed | **PARTIAL** | `client_operation_id` is **optional** ("recommended") ⇒ the "every operation has an unambiguous correlation key" guarantee is **conditional**; no duplicate-id/different-payload policy; see **S-1** |
| **M-5** | §5.9 `expires_at` note; §8.4 batch deadline | server has no batch concept; client `T0` first-file, never extended; verified no per-op extension mechanism | **YES** | none |

**Net:** M-1 and M-5 are resolved; M-3 is resolved (with a wording contradiction); M-2 and M-4 are
**partially** resolved (M-2 by an internal contradiction; M-4 by an optional-vs-guaranteed gap).

---

## 9. Security findings

Severity: **CRITICAL / HIGH / MEDIUM / LOW / INFO**.

| ID | Severity | Section(s) | Finding | Required correction |
| --- | --- | --- | --- | --- |
| **H-1a** | **MEDIUM** | §5.14.2 step 6, §5.9 (`delivered`), §7.5, §10.1 | The read/ingestion evidence ("a run whose tool calls read `delivered_path`") does **not** name exact event kinds/fields and does **not** require the read to **succeed**. An `ActionEvent` exists for a **failed** read (its `tool_call.arguments` contain the path), so `delivered` — and therefore cleanup — could be triggered while the agent could **not** read the file (the T-18 class r4 set out to close). | Define `delivered` evidence as a **successful** read: an `ObservationEvent` correlated by `action_id`/`tool_call_id` to an `ActionEvent` naming `delivered_path`, with an explicit error/`AgentErrorEvent` ⇒ **not** `delivered` rule. State the exact event kinds + fields. |
| **M-2-res** | **MEDIUM** | §7.5 (L1079) vs §2.2/§5.9.1 | §7.5 still asserts `consumed_at` "is set by the Cloud when its `send-message` route **durably accepts** a message" — the exact claim §2.2/§5.9.1 retract (the route is a thin proxy with no durable write). | Reword §7.5: `consumed_at` **would** be set by the **NEW** durable accept step (§5.15 U-2), if adopted; it is **not** set by the current thin proxy. |
| **S-1** | **MEDIUM** | §5.5 vs §5.9 (and Q13) | §5.5 says the create response may report **`accepted`** with **staging still in flight**; §5.9 justifies the absence of `uploading` by "staging happens **within that request**". These cannot both hold: if the response can precede staging completion, an in-flight-staging intermediate state exists — the state r3 removed. | Reconcile: either (a) the create returns only after staging completes (`stored`/`rejected`), so `accepted` is never a response state; or (b) `accepted`-with-in-flight-staging is a real non-terminal state and the Q13 async model (entering event/owner/recovery) must be defined. |
| **M-3b** | **LOW** | §5.9 table vs §5.10 | §5.9 says `delivered` "permits reclaim of **the delivered copy**"; §5.10 says the **delivered** copy "is retained for the life of the conversation" and only the **staging** copy is reclaimed. Contradiction. | Align §5.9 to §5.10: `delivered` permits reclaim of the **staging** copy; the delivered copy persists. |
| **M-4b** | **LOW** | §5.4, §5.6, §5.16 | `client_operation_id` is optional; the "every submitted operation has an unambiguous correlation key" guarantee is **conditional**. No rule for duplicate `client_operation_id` with a different payload. | Either make `client_operation_id` **required**, or state the guarantee as conditional; add a duplicate-id/different-payload rejection rule. |
| **H-1b** | **LOW** | §5.14.2 step 5 | "the agent reads it with its normal file tools" is not tied to a defined workspace→tool path mapping (the agent's tools must resolve relative to the **same** workspace root that `bind_local_conversation_runtime` confines). | State that `delivered_path` is **workspace-relative** and is resolved by the agent's tools against the confined workspace root (the route already confines by that root). |
| **H-1c** | **LOW** | §5.14.1, §5.15 U-2/U-3, §11(e) | The "no existing mechanism / NEW capability" framing under-credits existing primitives: the Cloud already has a **durable** `pending-messages` route and already exposes the **agent-server event log** via `GET …/events/search` (incl. `ActionEvent`/`ObservationEvent`). | Distinguish "genuinely new" (attachment op + server-to-server materialization endpoint) from "composition of existing primitives" (durable message-accept, read-evidence query); update the effort framing and the Q14/Q15/Q16 evidence statements. |
| **S-2** | **INFO** | §8.3 window 4 | The existing outbox dispatches prompt **text**; it has no upload-dispatch item type. | Note that an upload-dispatch item path must be added (integration contract), so a maintainer does not assume the outbox already carries uploads. |
| **S-3** | **INFO** | §5.14.2 step 4 | Delivered-write atomicity and file mode/owner are not stated. | State temp-write+rename (atomicity) and the intended file mode/ownership so the agent's runtime user can read it. |
| **S-4** | **INFO** | §2.2, §5.9.1 | All re-derivable source facts verified correct (thin proxy; text/image-only model; `ImageContent` images-only; event append durable; no `send-message` idempotency). | None — recorded for completeness. |

**No CRITICAL or HIGH finding remains.** r4 did **not** weaken any threat row (T-01–T-15 intact,
T-16–T-20 added), any P0 invariant (I1–I13 intact, I14 added), or any of §9's criteria 1–10.

---

## 10. P0 acceptance matrix

Maps every P0 requirement to contract section · required upstream capability · durable local state ·
failure/recovery · **evidence status** (`verified existing` / `proposed upstream` / `unresolved` /
`unsupported`). **Nothing is marked implemented.**

| P0 requirement | Section | Upstream capability | Durable local state | Failure/recovery | Evidence status |
| --- | --- | --- | --- | --- | --- |
| Upload to an **exact existing** conversation | §5.2, §5.3 | Cloud attachment op (new) | op row keyed by conversation | status endpoint | **proposed upstream** |
| Narrow credential (no agent-server key) | §5.3 | scoped credential (new) | — | — | **proposed upstream** |
| No command exec / no workspace read by the op | §5.3, §6 T-01 | scoped op | — | — | **proposed upstream** |
| Server-resolved destination (no client path) | §5.2, §5.7 | server path generation | op row | — | **proposed upstream** |
| Size/type/count/aggregate limits | §5.7 | server enforcement | — | 413/415 | **proposed upstream (PROVISIONAL, Q3)** |
| Symlink/traversal hardening | §5.7, §7.4 | `O_NOFOLLOW`/`O_EXCL` + containment | — | reject | **proposed upstream** (containment part **verified existing**) |
| Stable `operation_id` + status endpoint | §5.6, §5.9 | op store + status route | op row | poll status | **proposed upstream** |
| Idempotent create (`Idempotency-Key`) | §5.6 | idempotency | idempotency key | same op returned | **proposed upstream (window Q7)** |
| Monotonic terminal states | §5.9 | op store | op row | — | **proposed upstream** |
| Ended/deleted conversation behavior (409) | §5.8, §5.10 | op store | op row | 409 | **proposed upstream** |
| Multiple files join one pending batch | §5.4, §8.1 I6 | (client-side) | local batch | — | **proposed (client-side)** |
| First-file deadline never extends | §8.1 I4/I6, §8.4 | (client-side) | local `T0` | — | **proposed (client-side)** |
| Only accompanying text triggers sending | §8.1 I7/I8, §8.2 | (client-side) | local batch | — | **proposed (client-side)** |
| Non-text messages do not trigger sending | §8.1 I8 | (client-side) | local batch | — | **proposed (client-side)** |
| Sent to the same existing conversation | §8.1 I1 | op bound to one conversation | local batch | — | **proposed upstream** |
| No new-conversation fallback | §8.1 I1 | no create path | — | — | **proposed** |
| Expiry / late-text behavior safe | §5.9, §5.9.1, §8.4 | stale-ref reject | op row | notify, no retry | **proposed upstream** |
| Unknown outcomes preserve files + reconciliation data | §5.9, §8.1 I10, §8.3 | status endpoint | op row | no blind retry | **proposed upstream** |
| Cleanup only after confirmed terminal outcomes | §5.10, §8.1 I12 | evidence-based sweep | op row | sweep | **proposed upstream; evidence rule imprecise (H-1a)** |
| **Uploaded content readable by the conversation** | §5.14, §8.1 I14, §9 7c | materialization + read evidence | op row + workspace file | fallback retention | **proposed upstream; evidence rule imprecise (H-1a)** |
| Telegram ack + durable delivery | §8.1 I13, §8.3 | (client-side) | SQLite + outbox | fail-closed boundary | **verified existing (reuse)** |

**Bottom line:** the previously **unsupported** "uploaded content usable by the conversation"
requirement is now **proposed upstream** (a material improvement over r3), but its evidence rule is
**imprecise** (H-1a) and must be tightened before it can be trusted.

---

## 11. Owner decision analysis

Not decided here; only impact, minimum evidence, and blocking status.

| Q | Decision required | Security/reliability impact | Minimum evidence | Blocks approval? | Blocks upstream submission? | Blocks implementation? |
| --- | --- | --- | --- | --- | --- | --- |
| **Q5** | (5a) opaque ref acceptable? (5b) **how content becomes agent-readable** (H-1) | **Central.** 5b unaddressed ⇒ feature inert | Maintainer decision on mechanism **+** a **precise** read signal (fix H-1a) | **YES** | YES | YES |
| **Q11** | implement P0 vs keep fail-closed rejection | Product direction | Owner decision (no evidence) | No (it *is* the approval question) | YES | YES |
| **Q12** | `consumed_at` crash trade-off | Over-retention vs early delete | Confirm ≤15 min over-retention acceptable; resolve M-2-res wording | No (documented) | No | YES |
| **Q13** | `uploading`/`delivering` re-intro if async | Keeps the state model honest | Confirm staging/delivery are synchronous **or** define the async model (fix S-1) | No | No | YES |
| **Q14** | delivery mechanism + whether to extend `send-message` | The H-1 fix | Maintainer decision; **feasibility confirmed** (materialization is implementable by composing existing primitives — §4.4) | **YES** | YES | YES |
| **Q15** | durable Cloud message-accept in scope, or drop `consumed_at` | Whether `consumed_at` exists at all | Maintainer decision; note the **existing durable `pending-messages` route** (H-1c) | No (documented) | YES | YES |
| **Q16** | read/ingestion evidence availability for `delivered` | Whether early reclaim is possible | Confirm the **exact** event correlation (H-1a); else retention-until-`expires_at` (safe, ≤15 min) | No | No | YES |
| **Q17** | hybrid correlation-id contract | Unambiguous correlation of pre-op rejections | Confirm `client_operation_id` is **required** (or accept a conditional guarantee; fix M-4b) | No | No | YES |
| **Q3** | limits triple | Resource exhaustion vs usability | Confirm `(per_file, total, files)` | No | No | YES |
| **Q7** | idempotency window | Duplicate handling | Confirm window | No | No | YES |
| **Q10** | independent security review | Release gate | Who + gate | No | No | YES (gate) |

**Q5 answer to the task's specific question:** Q5 **now covers both** reference resolution (5a) and
agent-readable delivery (5b) — this is the improvement over r3. **Q14 feasibility:** the design is
**implementable** (existing primitives: server-side runtime hop, confined route, event log readable
via the Cloud, durable pending-messages) — so Q14 is a genuine design choice, not a research risk.
**Q16:** the read signal's **primitives** exist; only the **rule** is imprecise (H-1a), so Q16's
fallback (retention-until-`expires_at`) is safe but is not the intended guarantee. **Q11 remains the
owner's product decision and is not decided here.**

---

## 12. Exact corrections and unresolved evidence

**Required corrections (documentation-only):**

1. **§5.14.2 step 6 / §5.9 `delivered` / §7.5 / §10.1 — define the read evidence precisely (H-1a).**
   State: `delivered` requires (a) materialization at `delivered_path` **and** (b) a **successful**
   read = an `ObservationEvent` correlated by `action_id`/`tool_call_id` to an `ActionEvent` whose
   `tool_call.arguments` name `delivered_path`; an error/`AgentErrorEvent` result ⇒ **not**
   `delivered`. Name the exact event kinds/fields.
2. **§7.5 (L1079) — remove the self-contradiction (M-2-res).** `consumed_at` is **not** set by the
   current thin-proxy `send-message`; it **would** be set by the NEW durable accept step (U-2), if
   adopted.
3. **§5.5 vs §5.9 — reconcile the `accepted`/staging-timing contradiction (S-1).** Either the create
   returns only after staging completes, or `accepted`-with-in-flight-staging is a real state and the
   Q13 async model is defined.
4. **§5.9 table vs §5.10 — align the delivered-copy reclaim rule (M-3b).** `delivered` permits
   reclaim of the **staging** copy; the delivered copy persists.
5. **§5.4/§5.6/§5.16 — make the correlation guarantee unconditional (M-4b).** Require
   `client_operation_id` (or state the guarantee as conditional) and add a duplicate-id policy.
6. **§5.14.2 step 5 — tie "normal file tools" to the confined workspace root (H-1b).**
7. **§5.14.1/§5.15/§11(e) — re-frame "NEW capability" to distinguish new components from composition
   of existing primitives (H-1c);** reference the existing durable `pending-messages` route and the
   Cloud-exposed `GET …/events/search`.
8. **§8.3 — note that the outbox has no upload item type (S-2); §5.14.2 step 4 — state write
   atomicity + file mode/owner (S-3).**

**Unresolved evidence (honest):**

- The **byte-level r3→r4 diff** is unverifiable (r3 baseline unavailable) — §2.1.
- The **deployed** `enterprise` commit is unverifiable from outside (attribution is from public
  `main` + live route/description match) — unchanged from r3.
- Whether the **materialized file is readable by the agent's runtime user** (mode/owner) is not
  established — §4.3.
- Whether `ImageContent`-as-attachment persists is unverified — unchanged from r3, and irrelevant to
  H-1 (images only).

---

## 13. Final verdict and rationale

**Verdict: `NEEDS_REVISION`.**

**Why not `PASS`/`PASS_WITH_NOTES`:** the notes **block approval**. H-1a is a **security-relevant
imprecision** in the new `delivered` evidence rule that can permit **premature reclaim** of a file
the agent could not actually read — the exact false-success class r4 claims to close (T-18).
M-2-res is an **internal contradiction** in the load-bearing `consumed_at` description. S-1 is a
**new internal inconsistency** introduced by the M-4 change (`accepted`+in-flight staging vs "no
`uploading`"). M-3b and M-4b are additional LOW inconsistencies. These are more than notes: each
would lead a maintainer to implement something different from the stated intent.

**Why not `BLOCKED_BY_MISSING_UPSTREAM_EVIDENCE`:** every required correction is a **specification**
fix. All re-derivable upstream facts were verified; the missing pieces are contract text and owner
decisions the proposal can supply itself.

**Rationale.** r4 is a **substantial and honest advance**: the H-1 gap is now **specified** with a
concrete mechanism (Cloud resolves → materializes into the workspace at a server-generated
`delivered_path` → message references the concrete path → `delivered` from agent-server event-log
evidence), the thin-proxy fact is corrected, cleanup is evidence-based, the batch deadline is moved
to the client, the crash-window analysis is real, and the "NEW upstream capability" framing is
honest. I independently verified the load-bearing source facts (thin proxy; text/image-only model;
durable event append; no `send-message` idempotency; confined route; existing ack boundary) and
confirmed r4 weakened **no** threat row, invariant, or acceptance criterion. The remaining issues are
**precision and consistency defects in r4's own new text**, all fixable in a **focused delta
revision**; no new upstream evidence is required. A `PASS` would mean only "ready for owner
approval" — it would **not** authorize upstream submission, implementation, or deployment. **P0
remains unimplemented regardless of the verdict.**

---

## 14. Read-only compliance and preservation evidence

- **Only artifact created:** this file,
  `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R4-INDEPENDENT-ADVERSARIAL-REVIEW.md`.
- **Proposal unmodified:** `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md` read
  only (sha256 unchanged, `93798997…`).
- **Self-review unmodified:** `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R4-SELF-REVIEW.md` read
  only (`0afa0a2c…`).
- **Previous reviews unmodified:** r3 independent (`150ca104…`), r3 self (`8b29fa19…`), r2
  (`8d5153ca…`), r1 (`a9c85800…`) read only.
- **Working tree preserved:** no reset/clean/checkout/force/stash; the modified and untracked files
  listed in §1 are untouched.
- **No code/tests/schema/migration/config change** other than this review file.
- **No production call, no credential, no secret access; no upstream issue/PR/maintainer contact; no
  commit/push/PR/merge/deploy; no branch change.**
- **P0 is NOT implemented** and this review does not claim otherwise.
