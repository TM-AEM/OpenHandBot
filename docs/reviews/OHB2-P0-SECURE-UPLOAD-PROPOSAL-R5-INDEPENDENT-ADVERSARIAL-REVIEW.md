# OHB2-P0-SECURE-UPLOAD-PROPOSAL-R5 — INDEPENDENT ADVERSARIAL REVIEW

**Task ID:** `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R5-INDEPENDENT-ADVERSARIAL-REVIEW`

Reviewer: fresh-context independent adversarial reviewer; **not** the author of the proposal, **not**
the author of the r5 self-review, and **not** the author of the r2/r3/r4 reviews. All actions were
**read-only**: public source and specs were re-fetched independently this session and re-hashed,
**no production call, no credential, no secret access, no modification** of the proposal, the
self-reviews, or any previous review. This review file is the **only** artifact created. No
commit/push/PR/merge/deploy, no branch change, no upstream issue/PR/maintainer contact. **P0 remains
unimplemented.**

## Verdict: **NEEDS_REVISION**

r5 is a **real, honest improvement over r4**: it fixes **all eight** r4 §12 documentation corrections
(verified item-by-item in §4), and two of its corrections are **stronger than the r4 reviewer asked
for** (the seven-fact model §5.14.0; the atomic-publish / mode-owner / partial-write guarantees §7.4).
The security direction is sound, no threat row, P0 invariant, or acceptance criterion was weakened,
and the "partly composable / partly new" re-framing (H-1c) is accurate.

**But r5 is not yet ready for owner approval**, because its central new rule — the `delivered`
successful-read evidence rule (H-1a) — is **still not sufficient to establish the property it claims
to establish**, and I found a **source-backed counterexample** that a maintainer would implement as a
**premature-reclaim defect** (the exact T-18/T-19 class r5 says it closes):

- **N-1 (MEDIUM, new, source-backed):** r5 defines F6 ("file contents successfully read") as an
  `ObservationEvent` correlated to an `ActionEvent` naming `delivered_path` **whose result is
  non-error**. Against the pinned source, a **terminal-tool read of a file that does not exist (or is
  unreadable) is a *non-error* observation**, so the rule can set `delivered` — and permit reclaim of
  the staging copy — for a file the agent **could not read**. §5.14.2 step 6 / T-18 / T-19 / §9 7c /
  I14 / §7.5 all inherit the same gap.
- **N-2 (LOW, new):** the r5 §5.5 **example response** still shows `"state": "accepted"`, the exact
  value r5's own prose (§5.5 text, §5.9) says is **never returned** — a residual self-contradiction
  in the very section S-1 was meant to fix.
- **N-3 (LOW, new):** r5 presents the Cloud `pending-messages` route as the "recommended composition"
  for the durable message-accept (§5.9.1, §5.14.1, §5.15 U-2, §8.2 S7). Source shows that queue is
  drained **only during the conversation-start handshake** (task→conversation transition), **not**
  for an already-running conversation — so it is **not** a general durable-accept primitive for the
  integration, and the proposal does not state this limitation.
- **N-4 (INFO, new):** §5.14.2 step 5 offers the agent's **terminal `cat`** as a reader, but the
  terminal tool treats **any non-zero exit as success** (`is_error` is only set for
  interaction/multi-command/close failures), so the same N-1 false-positive applies on that path too;
  the proposal should name the **read tool and the exact success signal**, not "normal file tools".
- **N-5 (INFO, pre-existing/housekeeping):** the proposal header (line 9) and the r5 notice still say
  "**r4 2026-11-11**", and the header Task-ID list omits the r5 remediation task id — the document
  body is r5 but its self-identification is stale.

**All required fixes are documentation-only** (one of them — N-1 — requires the proposal to name a
**precise, positive, tool-level** success signal, or to declare `delivered`/early-reclaim
**unsupported** and fall back to retention-until-`expires_at`). No new upstream *machinery* is
needed; the events and fields exist. Hence the verdict is `NEEDS_REVISION`, **not**
`BLOCKED_BY_MISSING_UPSTREAM_EVIDENCE`.

---

## 1. Baseline and file hashes

| Item | Value |
| --- | --- |
| Repository | `TM-AEM/OpenHandBot` |
| Branch | `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW` |
| HEAD | `907b20de3fa6627795c14f29677e9f39c68e82f4` |
| origin/main | `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c` |
| Review date | Thu Nov 12 10:16:59 UTC 2026 |

**Working-tree status before review** (read only; nothing reset/cleaned/deleted/checked out):

```
 M .agent/PROGRESS.md
 M bot/handlers.py
 M docs/proposals/OHB2-AGENT-SERVER-FILE-UPLOAD-ARCHITECTURE.md
 M docs/proposals/OHB2-TELEGRAM-ACK-ARCHITECTURE-ADR.md
?? docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R2-INDEPENDENT-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R3-INDEPENDENT-ADVERSARIAL-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R3-SELF-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R4-INDEPENDENT-ADVERSARIAL-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R4-SELF-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R5-SELF-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-UPSTREAM-PROPOSAL-INDEPENDENT-ADVERSARIAL-REVIEW.md
?? tests/test_stage2_high_ack_blocking_fix.py
?? tests/test_stage4_f1_status_cost_operational_ack.py
```

**Artifacts under review (sha256, this session):**

| Artifact | Version | Lines | sha256 |
| --- | --- | --- | --- |
| `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md` | **r5** (body + §13 row `r5`; header "Date" line still says r4 — N-5) | 1840 | `6008c3ab44149b4a4cd9988fb9760752a92b9c38caf86672557f133341227085` |
| `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R5-SELF-REVIEW.md` | r5 self-review (supporting evidence only) | 217 | `67a7d1a5ea4fd5b7dcc3ee21c9578e8456599b4583e3eebbd3b5d2a6f92f8748` |
| `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R4-INDEPENDENT-ADVERSARIAL-REVIEW.md` | r4 independent review (`NEEDS_REVISION`; drives r5) | 526 | `ce13bc944ecdb44d773cd0f6ce9a16c38fea23438781657cc21c9ad584112ef3` |
| `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R4-SELF-REVIEW.md` | r4 self-review | 113 | `0afa0a2c3777fb6b5e50e777c8a45acd06bfd233860e5312913a5d129d6d57c9` |
| `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R3-INDEPENDENT-ADVERSARIAL-REVIEW.md` | r3 independent review (`NEEDS_REVISION`) | 396 | `150ca10479c4b7a49e983d7bae6b4e4db051bd257c31a13fa1ecf72b59c6ac01` |

**r5 identity confirmed:** the header r5 correction notice is present (proposal lines 91–126); §13
carries five rows (r1/r2/r3/r4/r5); the state table, §5.14.0, §5.14.1, §5.15 Status column, §5.16 and
T-21 are present. The proposal is **untracked**, so the sha256 above is the only version anchor.

### 1.1 Baseline availability (LIMITATION, stated honestly)

The proposal is **untracked** (`git ls-files` → empty for it); there is **no** r4 (or r3) copy of the
proposal on disk, in any stash, or in any Git object. **Therefore a byte-level r4→r5 diff could not be
computed.** I did **not** invent one. What **was** reconstructable and **was** used: the r4 review's
§12 exact-correction list (`ce13bc94…`), the r5 text, and the r5 §13 row. The r4→r5 verification in
§4 is therefore **semantic** (r4 review requirement vs r5 text), **not** a textual diff.

---

## 2. Method and independence

- Read the r4 independent review in full (its §12 corrections and §9 findings), the r5 proposal in
  full (1840 lines), and the r5 + r4 self-reviews (as **supporting** evidence only, never as
  authority).
- **Independently re-fetched** every load-bearing source file from public raw GitHub at the pinned
  SHAs and re-hashed it this session (§3). The live Cloud V1 OpenAPI was re-fetched and re-parsed.
- **Attempted to break r5** on each axis the r4 review lists (H-1a, M-2-res, S-1, M-3b, M-4b, H-1b,
  H-1c, S-2, S-3) **and** on new axes (the tool-level meaning of "non-error observation"; the
  delivery timing of `pending-messages`; the residual `accepted` example; stale header identity).
- **Independence note:** I am not the author of any prior artifact. Where r5's own text is the only
  evidence, I say so; where I could reach source, I cite file + field + hash.

---

## 3. Source repositories, revisions, and file hashes (re-fetched this session)

Every re-derivable hash **matches** the proposal's §11 (or the proposal's stated identity). `✅` =
re-fetched + hashed this session.

| Source | Identifier | File (sha256, this session) | Verified |
| --- | --- | --- | --- |
| `OpenHands/software-agent-sdk` | `9f7d5cb11b1256c1878f5584a657401feca9ad16` | `event/llm_convertible/action.py` `7bd55c8e…` | ✅ |
| | | `event/llm_convertible/observation.py` `3d851084…` | ✅ |
| | | `event/types.py` `ec7d5b13…` | ✅ |
| | | `tool/schema.py` `76b4f42a…` | ✅ |
| | | `llm/message.py` `1b9f0693…` (matches §11) | ✅ |
| | | `agent/agent.py` `18b6bd0d…` | ✅ |
| | | `conversation/impl/local_conversation.py` `0227cf98…` (matches §11) | ✅ |
| | | `agent_server/file_router.py` `13f0cae7…` (matches §11) | ✅ |
| | | `agent_server/runtime_router.py` `5bea70f0…` (matches §11) | ✅ |
| | | `agent_server/event_router.py` `6450a7c3…` (matches §11) | ✅ |
| | | `agent_server/event_service.py` `d59ff6e1…` (matches §11) | ✅ |
| | | `agent_server/models.py` `57b3680c…` (matches §11) | ✅ |
| `OpenHands/software-agent-sdk` — tools | same SHA | `tools/file_editor/impl.py` `35353ad3…` | ✅ |
| | | `tools/file_editor/editor.py` `a1d735d4…` | ✅ |
| | | `tools/file_editor/exceptions.py` `ca35cad9…` | ✅ |
| | | `tools/terminal/terminal/terminal_session.py` `72504a4d…` | ✅ |
| | | `tools/terminal/definition.py` `a978161b…` | ✅ |
| `OpenHands/enterprise` | `3fac53df8c2efcb67ff3537d1162e8c8a108f565` | `app_conversation/app_conversation_router.py` `c43ed4f7…` (matches §11) | ✅ |
| | | `pending_messages/pending_message_router.py` `520c381d…` | ✅ |
| | | `pending_messages/pending_message_service.py` `5efde158…` | ✅ |
| | | `event/event_router.py` `b268dd17…` | ✅ |
| | | `event/event_service_base.py` `2766bb89…` | ✅ |
| | | `app_conversation/live_status_app_conversation_service.py` (delivery consumer) | ✅ |
| | | `server/utils/saas_pending_message_injector.py` | ✅ |
| Live Cloud V1 OpenAPI | `app.all-hands.dev/openapi.json`, `1.87.1` | 242 paths; `multipart`=0, `binary`=0, upload=0 | ✅ re-parsed |

**Independently re-derived facts (not taken on trust):**

1. **Cloud `send-message` is a thin proxy with no durable Cloud write** — confirmed (M-2 correct).
2. **The agent-server event append is durable** (`EventLog.append` → `atomic_write_text`) — confirmed.
3. **The message model is text/image only** (`SendMessageRequest.content: list[TextContent |
   ImageContent]`; live spec `AppSendMessageRequest.content` = `anyOf[TextContent, ImageContent]`) —
   confirmed (H-1 premise correct).
4. **`ActionEvent` carries `tool_call_id` + `tool_call: MessageToolCall`; `ObservationEvent` carries
   `tool_call_id` + `action_id`; `Observation.is_error: bool = False` is the only error flag on the
   observation** — confirmed (load-bearing for N-1).
5. **`AgentErrorEvent` is emitted by the agent loop only for a tool-execution `ValueError` (and for
   orphaned actions after an interrupt)** — i.e. **not** for an ordinary tool "file not found" — see
   N-1.
6. **The file_editor tool converts `ToolError` into a *non-error-flagged* observation**:
   `FileEditorObservation.from_text(text=e.message, is_error=True)` — the tool **does** set
   `is_error=True` for its own `ToolError`s (good), **but** the editor's `view` of a **missing path**
   raises `EditorToolParameterInvalidError` (a `ToolError`) → caught → `is_error=True`; whereas a
   **`view` of an existing-but-huge/binary** file or a **`view` that returns a non-error** observation
   can still be a "partial read" — see N-1 for the terminal path, which is the sharper case.
7. **The terminal tool sets `is_error=True` only for interaction/multi-command/closed-terminal
   failures — never for a non-zero exit code** (`_handle_completed_command` returns
   `TerminalObservation.from_text(..., exit_code=metadata.exit_code)` with **no** `is_error`) — this
   is the **N-1 counterexample**: `cat missing` → non-error observation.

---

## 4. Verification of the eight r4 §12 corrections (item-by-item)

The r4 review §12 lists **eight** required documentation corrections. Each is checked against the
actual r5 text and, where relevant, against source.

| # | r4 §12 correction (finding) | r5 location | r5 action | Independent verdict |
| --- | --- | --- | --- | --- |
| **1** | Define the read evidence precisely — a **successful** read, exact event kinds/fields (**H-1a**, MEDIUM) | §5.14.0 (new); §5.14.2 step 6; §5.9 `delivered`; §7.5; §10.1; §6 T-18/T-19; §8.1 I12/I14; §9 7c | Adds F1–F7; step 6 requires an `ObservationEvent` correlated by `tool_call_id`/`action_id` to an `ActionEvent` naming `delivered_path` with a **non-error** result; bare `ActionEvent` (F4) and `AgentErrorEvent` ⇒ not `delivered` | **PARTIAL — see N-1.** The *structure* is fixed (exact kinds/fields named; F4 rejected; `AgentErrorEvent` rejected). But "non-error observation" is **not** a successful content read on the terminal path (source-backed), so the rule still permits a false `delivered`. |
| **2** | Remove the §7.5 self-contradiction on `consumed_at` (**M-2-res**, MEDIUM) | §5.9.1 (rewritten); §7.5 | One definition; `consumed_at` is **not** set by the thin proxy; would be set by the NEW durable step (U-2) or the existing durable `pending-messages` route | **PASS** — §5.9.1 and §7.5 agree; no "durably accepts" claim remains (grep clean). Residual: N-3 (the `pending-messages` timing limit is not stated). |
| **3** | Reconcile the `accepted`/staging-timing contradiction (**S-1**, MEDIUM) | §5.5; §5.9; §9 7b/7c; §10.1; §12 Q13 | Staging is synchronous within the create request; success returns `stored`; `accepted` is internal-only and never returned | **PARTIAL — see N-2.** The prose is reconciled, but the §5.5 **example** still prints `"state": "accepted"` (line 602), which the same section says is never returned. |
| **4** | Align the delivered-copy reclaim rule (**M-3b**, LOW) | §5.10 (rewritten per-artifact); §5.9 `delivered` row | On `delivered`, only the **staging** copy is reclaimed; the delivered copy persists; r4 wording withdrawn | **PASS** — §5.9 and §5.10 now agree (verified by reading both). |
| **5** | Make the correlation guarantee unconditional (**M-4b**, LOW) | §5.4 (field required); §5.6; §5.8 (409 code); §5.16; §6 T-21 (new) | `client_operation_id` **required** (UUID); unique per `(principal, conversation_id)`; same key + same payload ⇒ same op; different payload ⇒ `409 client_operation_id_conflict` | **PASS** — the field is `required` in §5.4; the 409 code and the two-case rule are present; T-21 added. |
| **6** | Tie "normal file tools" to the confined workspace root (**H-1b**, LOW) | §5.14.2 step 5 | `delivered_path` is **workspace-relative**, resolved against the same confined workspace root `bind_local_conversation_runtime` enforces | **PASS (as a contract).** Residual: N-4 (the specific reader/tool and its success signal are not named; terminal `cat` is offered). |
| **7** | Re-frame "NEW capability" vs composition of existing primitives (**H-1c**, LOW) | §5.14 status; §5.14.1 (classification); §5.15 (Status column U-1…U-9); §11(e); §12 Q14 | Documents the existing durable primitives (`pending-messages`, `events/search`) as composable; new = attachment op, materialization, delivery authz, successful-read **rule** | **PASS — and accurate.** `events/search` + `pending-messages` exist in the live spec and in source. Residual: N-3 (see above). |
| **8** | Note the outbox has no upload item type (**S-2**); state write atomicity + file mode/owner (**S-3**) | §8.3 (S-2 boundary); §5.14.2 step 4 + §7.4 (S-3) | §8.3 states the outbox carries **text only** (new payload capability, U-9); §7.4 lists atomic publish (`temp` + `os.replace`), readable mode/owner (UNVERIFIED), partial-write cleanup, cross-conversation isolation | **PASS (as a contract) — and stronger than asked.** Verified `bot/outbox.py` dispatches text only (`client.send_message(conversation_id, text)`). |

**Coverage:** 8/8 corrections are **addressed**; **5** are fully **PASS**, **2** are **PARTIAL**
(#1 → N-1; #3 → N-2), and **#7** passes but leaves a limitation (N-3). No r4 correction was ignored.

---

## 5. New findings (this review)

Severity: **CRITICAL / HIGH / MEDIUM / LOW / INFO**. `NEW` = introduced or left unresolved by r5's own
text; all are documentation-level.

### N-1 — MEDIUM (NEW, source-backed): the F6 "non-error observation" rule can still set `delivered` on a read that failed

**Where:** §5.14.0 (F6 row), §5.14.2 step 6, §5.9 `delivered` row, §7.5, §6 T-18/T-19, §8.1 I12/I14,
§9 7c, §10.1.

**What r5 says (proposal lines 1063–1069):**

> `delivered` ⇔ F2/F3 … AND F6 (a SUCCESSFUL read). F6 is established by an `ObservationEvent` whose
> `tool_call_id`/`action_id` correlates it to an `ActionEvent` whose `tool_call.arguments` name
> `delivered_path`, **and** whose result is a **non-error** observation for that action.

**The counterexample (pinned source).** The agent's terminal tool (`tools/terminal/…`) does **not**
set `Observation.is_error` for a command that exits non-zero. In
`terminal_session.py::_handle_completed_command` the completed-command path returns
`TerminalObservation.from_text(command=…, text=…, metadata=…, exit_code=metadata.exit_code)` **with no
`is_error=True`**; `is_error=True` is set only for interaction/empty-input, "cannot execute multiple
commands", and closed-terminal cases (grep: only those lines carry `is_error=True`). The only error
flag the observation carries is `Observation.is_error` (`tool/schema.py`, default `False`). Therefore:

- the agent runs `cat {delivered_path}` (or any shell read) for a **file that is not there / not
  readable** → the tool returns an **`ObservationEvent` correlated to the `ActionEvent` naming
  `delivered_path`** whose result is **non-error** (`exit_code != 0`, `is_error == False`);
- **r5's rule sets `delivered`**, and `delivered` is the sole authority that permits reclaim of the
  **staging** copy (§5.10) — for a file the agent could **not** read.

This is precisely the **T-18 "inert-token false success"** and **T-19 "premature deletion"** class r5
claims to close. r5's own §5.14.0 note "F4 ≠ F6" is correct as far as it goes, but F6 as **defined**
is satisfied by a non-error observation that is **not** a successful content read. The file_editor
path is safer (it raises `ToolError` → `is_error=True` for a missing path), but the **terminal** path
— which §5.14.2 step 5 itself offers as a reader ("file editor / terminal `cat`") — is not.

**Why it matters:** `delivered` gates early reclaim (§5.10) and is the "only success terminal state"
(§5.9). A false `delivered` deletes the staging copy while the agent still needs it, and reports
success to the owner — the exact failure the H-1 line of work exists to prevent.

**Required correction (documentation-only).** Either (a) name a **precise, positive, tool-level**
success signal (e.g. restrict F6 to a **file_editor `view`** whose observation has
`is_error == False` **and** whose structured payload proves content was returned — the live
`FileEditorObservation` carries `command`, `path`, `prev_exist`, and `content`; or require an explicit
`exit_code == 0` **and** a non-truncated read for any terminal-based reader), **and** state that a
bare non-error `ObservationEvent` is **necessary but not sufficient**; **or** (b) declare the F6
signal **not trustworthy as specified**, keep the safe default (operation stays `stored`,
retention-until-`expires_at`, no early reclaim), and record the precise rule as an owner decision
(Q16 already anticipates the fallback — r5 must not present the current rule as sufficient).

**Note:** r5's own self-review §3.1 already concedes the **same** point ("a non-error observation
string is not guaranteed to be a successful content read … the precise mapping … is **tool-specific**
and is not established"). An independent review must therefore mark H-1a as **not closed**, not merely
"UNKNOWN": a rule that is knowingly insufficient to establish its own claim must not gate an
irreversible action (`delivered` → reclaim).

### N-2 — LOW (NEW): §5.5 example still shows `"state": "accepted"`

**Where:** §5.5, proposal line 602: `"state": "accepted"`.

**Problem:** The §5.5 prose (same section) says a successful create "**never** reports `accepted` …
never returned", and §5.9 says the status read "**never reports `accepted`**". The JSON **example** in
the same section — the most copy-pasteable artifact in the document — still prints
`"state": "accepted"`. This is a residual instance of the S-1 contradiction r5 set out to remove: the
example must show `"state": "stored"`.

**Required correction:** change the §5.5 example to `"state": "stored"` (or annotate it as the
internal pre-staging value, explicitly marked "never returned").

### N-3 — LOW (NEW): the `pending-messages` route is drained only at conversation start, not for a running conversation

**Where:** §5.9.1 ("Composable today (H-1c)" block, lines 804–809), §5.14.1 (pending-messages row,
line 997), §5.15 U-2 (line 1125), §8.2 S7 (line 1396).

**What r5 says:** the Cloud "already exposes a durable queue … If a deployment routes the reference
message through **this** durable route, the Cloud **can** set `consumed_at` **without new upstream
work**. This is the **recommended composition** for the message-accept milestone."

**What source shows (pinned enterprise SHA):** the queue is consumed **only** by
`live_status_app_conversation_service.py::_process_pending_messages`, which is called **once**, from
the conversation-**start** path, immediately after the start task reaches `READY`
(`if sandbox.session_api_key: await self._process_pending_messages(...)`). It is **not** called by any
other component (grep: the only caller is that one site; `app_conversation_service.py` /
`app_conversation_service_base.py` contain no `get_pending_messages`). Messages are also **deleted
regardless of delivery success**, and the queue is **capped at 10** with a 429.

**Consequence for the proposal:** for the P0 integration — which sends the reference message to an
**already-running, existing** conversation (§8.1 I1: never create a new conversation) — the
`pending-messages` route is **not** a durable-accept primitive: it only fires during the start
handshake. Presenting it as "composable today / recommended" overstates the composition and could lead
a maintainer to build `consumed_at` on a route that never delivers for the target use case.

**Required correction:** state the limitation explicitly (the queue is start-time only, capped at 10,
and deleted regardless of delivery), and re-classify U-2 accordingly (still `NEW` for the running-
conversation case, or note that `consumed_at` has no durable-accept path for an existing conversation
today). This does **not** change the safe fallback (retention-until-`expires_at`).

### N-4 — INFO (NEW): §5.14.2 step 5 offers the terminal `cat` as a reader without its success signal

**Where:** §5.14.2 step 5 (proposal line 1056): "(file editor / terminal `cat`, relative to the
workspace)".

**Problem:** as N-1 shows, the terminal path's non-zero exit is a **non-error** observation, so
offering `cat` as a reader couples the delivery contract to the least-precise reader. The proposal
should name the **read tool** and the **exact success signal** used for F6 (and exclude the
non-zero-exit terminal case), rather than "normal file tools". (This is the same root cause as N-1;
recorded separately because it is a distinct, easily-missed sentence.)

### N-5 — INFO (NEW, housekeeping): the proposal's self-identification is stale

**Where:** header line 9 ("**Date:** … **r4 2026-11-11** …") and the header Task-ID list (lines 3–6),
which stops at r4.

**Problem:** the document body is r5 (state table, §5.14.0, §5.15 Status column, T-21, §13 r5 row) but
the header still identifies as r4 and omits the r5 remediation task id
(`OHB2-P0-SECURE-UPLOAD-PROPOSAL-R5-REVIEW-FINDINGS-REMEDIATION`). Cosmetic, but it undermines the
version anchor for an untracked file.

**Required correction:** add the r5 date and the r5 task id to the header (the r5 correction notice is
already present).

---

## 6. State-model, retention, and crash-window re-check (independent)

| Item | r5 claim | Independent check | Verdict |
| --- | --- | --- | --- |
| Observable states after create | `stored` (success) / definite non-2xx (failure); `accepted` never returned | §5.9 prose + §5.5 prose agree | **PASS** (except the §5.5 **example** → N-2) |
| `uploading` absent | removed (r3) | not present in the state table | **PASS** |
| `delivered` reachable only with evidence | "not decorative" | rule present, but the rule is insufficient → N-1 | **PARTIAL** |
| Reclaim on `delivered` | staging only; delivered copy persists | §5.9 + §5.10 agree | **PASS** |
| No early delete on unknown/failed read | stays `stored` until `expires_at` | §5.10 states the safe default | **PASS as written** — but N-1 means a *false positive* read can still trigger early reclaim |
| Crash windows (§8.3) | 7 windows; intent durable before call; ack fail-closed | consistent with `bot/outbox.py` (text-only dispatch) and the ADR §18.1 vocabulary | **PASS (contract)**; no exactly-once claim |
| `expires_at` fixed at accept | never extended | §5.9 states it | **PASS** |
| Batch deadline client-side | server has no batch concept | §8.4 states it | **PASS** |

---

## 7. Preservation check (no weakening)

| Check | Method | Result |
| --- | --- | --- |
| Threat rows intact + added | r4 review recorded T-01–T-20; r5 has T-01–T-21 | **PASS** — none removed; T-18/T-19 refined; T-21 added (21 rows) |
| P0 invariants intact + added | r3 review enumerated I1–I13; r4 added I14; r5 §8.1 has I1–I14 | **PASS** — I1–I14 present |
| Acceptance criteria intact + added | r3 items 1–10; r5 has 1–11 + 7b/7c | **PASS** |
| No new implementation claim | grep for "is implemented" / "P0 complete" | **PASS** — §Status says "P0 is NOT complete" |
| r5 edits confined to declared sections | header notice lists the sections | **PASS** (consistent with §4 findings) |

---

## 8. P0 acceptance matrix (evidence status — nothing implemented)

| P0 requirement | Section | Evidence status |
| --- | --- | --- |
| Upload to an **exact existing** conversation | §5.2–§5.3 | proposed upstream |
| Narrow credential (no agent-server key) | §5.3, T-01 | proposed upstream |
| Server-resolved destination (no client path) | §5.2, §5.7 | proposed upstream |
| Size/type/count/aggregate limits | §5.7 | proposed upstream (PROVISIONAL, Q3) |
| Symlink/traversal hardening | §5.7, §7.4 | containment part **verified existing**; rest proposed |
| Stable `operation_id` + status endpoint | §5.6, §5.9 | proposed upstream |
| Idempotent create | §5.6 | proposed upstream (window Q7) |
| Ended/deleted conversation behavior | §5.8, §5.10 | proposed upstream |
| **Uploaded content readable by the agent** | §5.14, I14, §9 7c | **proposed upstream; evidence rule INSUFFICIENT (N-1)** |
| Cleanup only after confirmed terminal evidence | §5.10, I12 | **proposed upstream; inherits N-1** |
| Telegram ack + durable delivery | §8.1 I13, §8.3 | verified existing (reuse) |

**Bottom line:** the H-1 delivery **contract** is well-specified, but its **success gate** (`delivered`)
is not yet trustworthy (N-1), so "cleanup only after confirmed terminal evidence" is **not** satisfied
as specified.

---

## 9. Owner decision analysis (impact / evidence / blocking)

| Q | Decision | Impact | Minimum evidence | Blocks approval? |
| --- | --- | --- | --- | --- |
| **Q5 (5b/5c)** | delivery mechanism + exact `delivered` rule | **Central** | a **precise, positive** success signal (N-1) or the safe fallback | **YES** |
| **Q11** | implement P0 vs keep fail-closed rejection | product direction | owner decision | (it *is* the approval question) |
| **Q12** | `consumed_at` retained? which durable route? | over-retention vs early delete | resolve N-3 (start-only delivery) | No (documented) |
| **Q13** | `accepted` internal / staging synchronous | state-model honesty | fix the §5.5 example (N-2) | No |
| **Q14** | delivery mechanism placement | the H-1 fix | maintainer decision | **YES** |
| **Q15** | durable message-accept in scope | whether `consumed_at` exists | note N-3 | No |
| **Q16** | F6 availability/trustworthiness | early reclaim | **N-1 is the crux** | No (but gates `delivered`) |
| **Q17** | correlation contract | unambiguous correlation | already required (M-4b PASS) | No |

**Q16 is the blocking one:** r5 presents F6 as available and sufficient; source shows the chosen
signal is **not** sufficient on the terminal path. The proposal must either tighten the rule or accept
the fallback **explicitly**.

---

## 10. Read-only compliance and preservation evidence

- **Only artifact created:** this file,
  `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R5-INDEPENDENT-ADVERSARIAL-REVIEW.md`.
- **Proposal unmodified:** `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md` read
  only (sha256 unchanged, `6008c3ab…`).
- **Self-review unmodified:** `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R5-SELF-REVIEW.md` read
  only (`67a7d1a5…`).
- **Previous reviews unmodified:** r4 independent (`ce13bc94…`), r4 self (`0afa0a2c…`), r3 independent
  (`150ca104…`) read only.
- **Working tree preserved:** no reset/clean/checkout/force/stash; the modified and untracked files
  listed in §1 are untouched.
- **No code/tests/schema/migration/config change** other than this review file.
- **No production call, no credential, no secret access; no upstream issue/PR/maintainer contact; no
  commit/push/PR/merge/deploy; no branch change.**
- **P0 is NOT implemented** and this review does not claim otherwise.

---

## 11. Final verdict and rationale

**Verdict: `NEEDS_REVISION`.**

**Why not `PASS`/`PASS_WITH_NOTES`:** the notes **block approval**. **N-1** is a security-relevant
**insufficiency** in the load-bearing `delivered` rule: the pinned terminal tool returns a
**non-error** observation for a **failed** read, so r5's F6 can set `delivered` — and authorize
**premature reclaim** of the staging copy — for content the agent could not read (the exact T-18/T-19
class r5 claims to close). r5's own self-review concedes the same insufficiency, which means the rule
is not merely "UNKNOWN" but **known-insufficient** to gate an irreversible action. N-2 and N-3 are
additional residual inconsistencies; N-4/N-5 are informational.

**Why not `BLOCKED_BY_MISSING_UPSTREAM_EVIDENCE`:** every required correction is a **specification**
fix. The events/fields the rule needs already exist (`Observation.is_error`, `FileEditorObservation`'s
structured payload, `exit_code`); the proposal can name a precise signal itself, or adopt the safe
fallback it already documents. No new upstream machinery is required.

**Rationale.** r5 is a genuine advance over r4: **all eight** r4 §12 corrections are addressed, five
fully and two partially, and two of them (the seven-fact model; the atomic-publish/mode-owner/
partial-write guarantees) exceed what the r4 reviewer asked for. I independently re-verified the
load-bearing source facts (thin proxy; text/image-only model; durable event append; `ActionEvent`/
`ObservationEvent`/`AgentErrorEvent` fields; the terminal tool's error semantics; the `pending-messages`
start-only delivery) and confirmed r5 weakened **no** threat row, invariant, or acceptance criterion.
The remaining defects are **precision and consistency defects in r5's own new text**, fixable in a
focused delta revision. A `PASS` would mean only "ready for owner approval" — it would **not**
authorize upstream submission, implementation, or deployment. **P0 remains unimplemented regardless of
the verdict.**
