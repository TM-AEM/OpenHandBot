# OHB2-P0-SECURE-UPLOAD-PROPOSAL-R6 — INDEPENDENT ADVERSARIAL REVIEW

**Task ID:** `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R6-INDEPENDENT-ADVERSARIAL-REVIEW`

Reviewer: fresh-context independent adversarial reviewer; **not** the author of the proposal, **not**
the author of the r6 self-review, and **not** the author of any earlier (r2–r5) review. All actions
were **read-only**: upstream public source and specs were re-fetched independently this session and
re-hashed, **no production call, no credential, no secret access, no modification** of the proposal,
the self-reviews, or any previous review. This review file is the **only** artifact created. No
commit/push/PR/merge/deploy, no branch change, no upstream issue/PR/maintainer contact. **P0 remains
unimplemented.**

## Verdict: **NEEDS_REVISION**

r6 is a **genuine, well-executed correction of r5**. Its central claim — that a *correlated non-error
observation* is **not** proof of a successful content read, and that **no existing primitive proves
F6b**, so `delivered` must require a **new U-3 signal** — is **verified true against the pinned
source** (§3, finding N-1 confirmation). The read-evidence and retention rules were made **stricter**,
and I found **no** weakening of any threat-model row, P0 invariant, or acceptance criterion (§5). All
five r5 findings (N-1…N-5) are addressed in the r6 text (§4). The state-model self-consistency is
sound: `accepted` is internal-only and never returned; the §5.5 example is `stored` (§4).

**But r6 is not yet ready for owner approval**, because its **new safety argument creates a new
lifetime hazard**, and because the new **U-3** contract — now the *only* path to `delivered` — leaves
the signal's **trust model and its own completeness guarantee** unspecified:

- **R6-1 (MEDIUM, new, source-backed): the *materialized* file is deleted at `expires_at` even when
  the agent never read it.** Because r6 makes `delivered` **unreachable** (U-3 does not exist), the
  **only** reachable terminal path for a successfully materialized file is `expired`. §5.10 (line 948)
  and §5.9 (line 845) state the **delivered (materialized) copy** is removed "at `expires_at`" when the
  operation never reached `delivered`. So in **every deployment today**, a file the Cloud successfully
  materialized into the workspace for the agent is **removed ≤ 15 min later** — the exact
  *premature-deletion / inert-token* class (T-18/T-19) the document says it closes. This contradicts
  §5.14.2 step 7 ("the delivered copy remains the agent's file for the life of the conversation") and
  §5.10's own "Delivered copy … removed only when the workspace is removed". r6 made `delivered`
  unreachable **without** re-deriving what then becomes of an already-materialized file.
- **R6-2 (MEDIUM, new): the U-3 trust model is unspecified.** U-3 may be "emitted … by the reader, or
  by the delivery layer observing a complete read" (§5.14.2 step 6, line 1229-1231). Nothing states
  **who is trusted to emit it**, whether an **agent/tool** may emit it (i.e. whether it is
  agent-spoofable), or how it is authenticated. If U-3 is agent-emittable, the F6a counterexample r6
  closed **reopens one level up**: a model that emits a false `read_complete == true` acknowledgment
  still sets `delivered`. The field contract (§5.15, lines 1311-1322) specifies *fields, correlation,
  semantics, and fail-closed failure*, but **not** the producer's authority — the one property that
  determines whether U-3 is evidence or self-attestation.
- **R6-3 (LOW, new, source-backed): the "Cloud-reachable event log" is a *polled replica*, and the
  evidence read is **not** atomic.** The Cloud's `events/search` store is populated by a
  **best-effort poll loop** — `remote_sandbox_service.py::poll_agent_servers` → `refresh_conversation`
  → `event_service.save_event` (enterprise, sha256 `d239ec43…`, lines 1256/1345/1438) — which runs on
  a `sleep_interval` and pulls the **agent-server's** event list. The proposal calls `events/search` a
  "durable, conversation-bound, Cloud-reachable event log" (§5.14.1) without disclosing the
  replication lag, the poll interval, or the **non-atomic** read (events are fetched page-by-page and
  saved one at a time). A U-3 rule that reads this store can therefore observe a **torn** sequence; the
  contract needs a "read from a quiesced/finalized source" or a "re-verify on the agent-server" rule.
- **R6-4 (LOW, new): the named reader requires an *absolute* path, but `delivered_path` is
  workspace-relative.** §5.14.2 step 5 tells the agent the file is at a **workspace-relative**
  `delivered_path`. The preferred reader — file_editor `view` — raises
  `EditorToolParameterInvalidError("path", …)` for any **non-absolute** path
  (`editor.py::validate_path` → `is_host_absolute_path`, sha256 `a1d735d4…`, line 666), and the file
  is **not** created if it is missing. So the "workspace-relative path the agent's normal tools
  resolve" (§5.14.2 step 5, line 1193) is **not** directly openable by the tool r6 names as the
  preferred reader; the resolution step (relative → absolute against the workspace root) is asserted
  but not specified.
- **R6-5 (INFO, new): stale "seven lifecycle facts" text survives.** §5.14.0's heading and body are
  corrected to **eight** facts (F1–F5, F6a/F6b, F7) and the header now says "r6: eight"
  (lines 107, 1074), but **§1/§5.14.0 predecessor text still says "seven lifecycle facts F1–F7"**
  (line 106, the r5 bullet) and §13's r5 row retains the r5 wording — a residual self-identification
  inconsistency of the same class as r5's N-5, now only partly cleaned.

**All required fixes are documentation/contract-level** (R6-1 and R6-2 require a contract decision:
re-derive the materialized-file lifetime for the "unreachable `delivered`" case, and state U-3's
producer trust model; R6-3/R6-4 require the read rule to name a quiesced source and the exact
resolution of the relative path; R6-5 is a text fix). No new upstream *machinery* beyond what r6
already lists (U-1…U-9) is needed. Hence the verdict is `NEEDS_REVISION`, **not**
`BLOCKED_BY_MISSING_UPSTREAM_EVIDENCE`.

---

## 1. Baseline and file hashes

| Item | Value |
| --- | --- |
| Repository | `TM-AEM/OpenHandBot` |
| Branch | `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW` |
| HEAD | `907b20de3fa6627795c14f29677e9f39c68e82f4` |
| origin/main | `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c` |
| Review date | Thu Nov 12 11:35 UTC 2026 |
| r6 proposal | `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md` — sha256 `a02b9747d8639759f395a730bec468091a9dcef5ba510ae596245b4e276693c0` (2098 lines) |
| r6 self-review | `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R6-SELF-REVIEW.md` — sha256 `908caa60a1123285a852fae469c4f94dfd81280f3246d1d3030e6f606cf805c4` (121 lines) |
| r5 review (driver) | `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R5-INDEPENDENT-ADVERSARIAL-REVIEW.md` — sha256 `4d5d708804c466a1b7832cfe95c07f962abba04f9e9f745921285734673e94b0` (440 lines) |

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
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R5-INDEPENDENT-ADVERSARIAL-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R5-SELF-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R6-SELF-REVIEW.md
?? docs/reviews/OHB2-P0-SECURE-UPLOAD-UPSTREAM-PROPOSAL-INDEPENDENT-ADVERSARIAL-REVIEW.md
?? tests/test_stage2_high_ack_blocking_fix.py
?? tests/test_stage4_f1_status_cost_operational_ack.py
```

The pre-existing untracked/modified files (proposal, prior reviews, `bot/handlers.py`, `PROGRESS.md`,
the two new tests) were **left untouched**. The r6 review file this task creates
(`docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R6-INDEPENDENT-ADVERSARIAL-REVIEW.md`) is intentionally
**not** shown above.

**Source revisions used (re-fetched and re-hashed this session, read-only).** The pinned SHAs are
unchanged from r2–r5:

| Repo | Pinned commit |
| --- | --- |
| `OpenHands/software-agent-sdk` | `9f7d5cb11b1256c1878f5584a657401feca9ad16` |
| `OpenHands/sandbox-server` | `43e91604ccd0a9960c8d5c52faadd60b30f10e63` |
| `OpenHands/enterprise` | `3fac53df8c2efcb67ff3537d1162e8c8a108f565` |
| `OpenHands/OpenHands` | `a8aaf6813753803cae5182d050909705b0eb02d0` |

---

## 2. Method

1. Read the whole r6 proposal (2098 lines), the r6 self-review, and the r5 review that drove it.
2. Re-fetched every upstream file the r6 read-evidence and composability claims depend on, at the
   pinned SHAs, and re-computed sha256 prefixes (below). Nothing was taken from the proposal.
3. Traced each of the **eight lifecycle facts** (F1–F5, F6a, F6b, F7) to a concrete source symbol.
4. Attacked r6 on the same axes the r5 review used (read evidence, `pending-messages` composability,
   reader choice, state/retention, header identity) **and** on the new axes r6 itself introduces
   (U-3 trust, materialized-file lifetime under "unreachable `delivered`", event-store freshness,
   relative-path reading).
5. Cross-checked every state/retention/invariant/criterion mention for internal contradictions.

**Source hash table (sha256 prefix, this session).**

| Source (pinned) | sha256 | What it establishes |
| --- | --- | --- |
| `openhands-sdk/…/sdk/tool/schema.py` | `76b4f42a` | `Observation.is_error: bool = False` (line 417); `from_text(..., is_error=False)` (line 430); `to_llm_content` prepends `ERROR_MESSAGE_HEADER` iff `is_error` (lines 451/469) |
| `openhands-tools/…/terminal/terminal/terminal_session.py` | `72504a4d` | `_handle_completed_command` returns `TerminalObservation.from_text(..., exit_code=metadata.exit_code)` **without** `is_error` (lines 282-287); `is_error=True` only at lines 506/520/526/542/608/670 (interaction / empty-input / multi-command / closed-terminal) |
| `openhands-tools/…/terminal/definition.py` | `a978161b` | `TerminalObservation.exit_code: int \| None` (line 152); non-error completed path |
| `openhands-tools/…/file_editor/impl.py` | `35353ad3` | `FileEditorExecutor.__call__` maps `ToolError → FileEditorObservation.from_text(..., is_error=True)` (lines 68-71) |
| `openhands-tools/…/file_editor/editor.py` | `a1d735d4` | `validate_path` raises `EditorToolParameterInvalidError` for non-absolute paths (line 666-679) and for a missing path on non-`create` commands (line 691-694); `validate_file` skips missing files (line 744); `with_encoding` supplies the default encoding for missing files |
| `openhands-tools/…/file_editor/utils/constants.py` | `a5b3f2bf` | `MAX_RESPONSE_LEN_CHAR = 16000`; clip notices |
| `openhands-tools/…/file_editor/utils/encoding.py` | `6fe560f9` | `with_encoding` (line 191): missing files get the default encoding, so `_count_lines`/`read_file` **raise `FileNotFoundError`** (not `ToolError`) |
| `openhands-tools/…/gemini/read_file/definition.py` | `893fd5d5` | `ReadFileObservation{file_path, file_content, is_truncated, lines_shown, total_lines}`; `MAX_LINES_PER_READ = 1000` |
| `openhands-tools/…/gemini/read_file/impl.py` | `2d5f81f2` | sets `is_truncated`/`lines_shown`/`total_lines`; `is_error=True` for missing/dir/offset/binary failures |
| `openhands-sdk/…/sdk/tool/defaults.py` | `357f005b` | `DEFAULT_EXEC_TOOL_NAMES = ("terminal", "file_editor", "task_tracker")` (line 26) |
| `tests/cross/test_default_tool_names.py` | `3b406311` | parity pin of the default tool names |
| `openhands-sdk/…/sdk/event/llm_convertible/action.py` | `7bd55c8e` | `ActionEvent.tool_name` (line 59), `tool_call_id` (line 60) |
| `openhands-sdk/…/sdk/event/llm_convertible/observation.py` | `3d851084` | `ObservationEvent{observation, action_id}` (line 32-39); `AgentErrorEvent{error, classification}` (line 146) |
| `openhands-sdk/…/sdk/conversation/event_store.py` | `40e707b3` | `EventLog.append` → `self._fs.write(...)` (line 338) |
| `openhands-sdk/…/sdk/io/local.py` | `90a3c58f` | `LocalFileStore.write` uses `atomic_write_text` for str (line 67) — **atomicity lives in the SDK file store, not in a named `atomic_write_text` step in `EventLog`** |
| enterprise `…/event/filesystem_event_service.py` | `409dbfcb` | `_store_event` = `path.write_text(...)` (line 41); store path `{persistence_dir}/{user_id}/v1_conversations` |
| enterprise `…/event/event_service_base.py` | `2766bb89` | `save_event` (line 435); index writes use `os.replace` |
| enterprise `…/event_callback/event_callback_models.py` | `84aec66c` | `EventKind = Literal[tuple(c.__name__ …)]` (line 30) ⇒ `kind__eq` accepts the SDK event class names (`ActionEvent`, `ObservationEvent`, `AgentErrorEvent`) |
| enterprise `…/app_conversation/live_status_app_conversation_service.py` | `9f4f1596` | `_process_pending_messages` defined once (line 3976), called once from the start path (line 1239); deletes all entries regardless of success (lines 4048-4050) |
| enterprise `…/pending_messages/pending_message_service.py` | `5efde158` | `add_message` → `StoredPendingMessage` + `db_session.commit()` (line 83-113) |
| enterprise `…/pending_messages/pending_message_router.py` | `520c381d` | 429 above 10 (line 87-92) |
| enterprise `…/sandbox/remote_sandbox_service.py` | `d239ec43` | `poll_agent_servers` (line 1256) → `refresh_conversation` (line 1345) → `event_service.save_event` (line 1438) — the **replica** poller |
| enterprise `…/app_conversation/app_conversation_router.py` | `c43ed4f7` | `list_conversation_files` `GET …/{conversation_id}/files` (line 1725); no upload/multipart route |
| sandbox-server `…/app_conversation/app_conversation_router.py` | `864bff55` | pinned-router read routes |
| sandbox-server `…/app_conversation/live_status_app_conversation_service.py` | `9653dd3d` | `_build_conversation` |
| sandbox-server `…/sandbox/remote_sandbox_service.py` | `c523a807` | `_to_sandbox_info` / `_build_service_url` |
| sandbox-server `…/sandbox/session_auth.py` | `893d725e` | session-key handling |

All r6 source citations I checked **match** the pinned source. No citation was found to be wrong.

---

## 3. The r6 central claim is verified (the strongest part of r6)

**Claim (r6 N-1).** r5's F6 — "a correlated **non-error** `ObservationEvent` for an `ActionEvent`
naming `delivered_path`" — is insufficient, because a **failed terminal read is non-error**, so
`delivered` could be set (and the staging copy reclaimed) for a file the agent could not read.

**Independent verification — TRUE.**

- `Observation.is_error` defaults to **`False`** (`schema.py` line 417) and is the only error flag.
- The terminal tool's **completed-command** path returns
  `TerminalObservation.from_text(command=…, text=…, metadata=…, exit_code=metadata.exit_code)` with
  **no** `is_error` (`terminal_session.py` line 283). `is_error=True` appears only at lines
  506/520/526/542/608/670 — interaction / empty-input / "cannot execute multiple commands" /
  closed-terminal cases. A non-zero `exit_code` does **not** set `is_error`.
- Therefore `cat <missing>` (or any failing terminal read) yields an `ObservationEvent` whose
  `observation.is_error == false`, correlated to the `ActionEvent` naming the path ⇒ r5's F6 holds
  while the read failed. r6's withdrawal is correct.
- r6's further claims are also verified: file_editor `view` of a **missing** path raises
  `EditorToolParameterInvalidError` in `validate_path` (`editor.py` line 691) — a `ToolError`
  subclass — which `impl.py` maps to `is_error=True`; and a **successful** `view` is truncated at
  `MAX_RESPONSE_LEN_CHAR = 16000`. So neither `terminal` nor `file_editor` proves a **complete**
  read. The structured `read_file` tool (which *does* carry `is_truncated`/`lines_shown`/`total_lines`)
  is a **Gemini-preset** tool and is **not** in `DEFAULT_EXEC_TOOL_NAMES` ⇒ deployment-dependent.
  r6's N-1/N-4 statements are accurate.

**Conclusion:** r6's read-evidence correction is sound and is the correct direction. The findings
below are about what r6 does **not** yet specify, not about the core correction.

---

## 4. Remediation mapping — all five r5 findings (independent re-verification)

| # | r5 finding | r6 location(s) | Independent verdict |
| --- | --- | --- | --- |
| **N-1** | MEDIUM: F6 "non-error observation" can set `delivered` on a **failed** read | §5.14.0 (F6a/F6b split), §5.14.2 step 6, §5.9 `delivered`, §7.5, §6 T-18/T-19, §8.1 I12/I14, §9 7c, §5.15 U-3 (+field contract), §12 Q5b/Q5c/Q16, §11 caveats (e)/(f) | **RESOLVED as a contract.** Verified against source (§3). `delivered` now requires the new U-3 signal; the fallback is retention-until-`expires_at`. *Residual:* U-3 is a proposal (disclosed) and its trust model is unspecified (**R6-2**). |
| **N-2** | LOW: §5.5 example showed `"state": "accepted"` | §5.5 example now `"state": "stored"` (line 682); note added (line 715) | **RESOLVED.** The §5.5 create example (line 682) and §5.9 status example (line 806) both show `stored`; the only `accepted` mentions are the state-enum prose and the changelog. |
| **N-3** | LOW: `pending-messages` is start-only | §5.9.1, §5.14.1 (table+classification), §5.15 U-2, §8.2 S7, §8.3(a), §2.2, §11, §12 Q12/Q15 | **RESOLVED.** Verified: `_process_pending_messages` is defined once and called once from the start path (lines 3976/1239), deletes all entries regardless of delivery success (line 4044), and 429s above 10 (router line 87). r6's start-only statement is accurate. |
| **N-4** | INFO: terminal `cat` named with no success signal | §5.14.2 step 5 (reader + U-3 signal); §11 source entry | **RESOLVED.** Terminal `cat` is explicitly rejected; the structured `read_file` is correctly flagged as non-default. *Residual:* the preferred reader needs an **absolute** path but `delivered_path` is relative (**R6-4**). |
| **N-5** | INFO: header self-identification stale | header (task-id list, dates, review list) | **RESOLVED (mostly).** The header now identifies r6 and lists the r5+r6 task ids and both driving reviews. *Residual:* the "seven lifecycle facts" wording survives in the r5 bullet (§1, line 106) — **R6-5**. |

**Preservation check (no weakening).** I compared r6 against r5 across the threat model (§6), the P0
invariants (§8.1 I1–I14), and the acceptance criteria (§9). T-18/T-19 are **strengthened** (they now
require U-3); T-21 is retained; I12/I14 are **strengthened**; criteria 7b/7c are **strengthened**. No
row, invariant, or criterion was weakened. **Confirmed.**

---

## 5. Adversarial findings (new)

### R6-1 (MEDIUM, new, source-backed) — the materialized file is deleted at `expires_at` even if never read

**Claim in r6.** §5.14.2 step 7 (line 1242-1244): "Only after `delivered` (via U-3) or `expires_at`
may the **staging** copy be reclaimed … the delivered copy remains the agent's file for the life of
the conversation." §5.10 (line 948): the **delivered (materialized) copy** "**Persists for the life of
the conversation** … it is removed only when the **workspace** is removed (conversation
archived/deleted) **or, if the operation never reached `delivered`, at `expires_at`**."

**The contradiction / hazard.** r6's own conclusion is that, **in every deployment today**, U-3 does
not exist, so `delivered` is **unreachable** (§5.9 line 855; §5.14.2 step 6 line 1236-1238; §5.10
line 971). Therefore **every** operation that materializes a file takes the second clause of §5.10
line 948: "**if the operation never reached `delivered` … at `expires_at`**" ⇒ the materialized
(delivered) copy is **removed ≤ 15 min after materialization**. The same clause is echoed in §5.9's
`expired` row (line 845): "the delivered copy (if any) is reclaimed with the workspace."

This is exactly the T-18/T-19 class the document says it closes: a file the agent can read is
**deleted underneath it** — here, **not** because of a false `delivered`, but because `delivered` is
**unreachable**, so a *successfully materialized* file is treated like an abandoned one. r6 made
`delivered` unreachable **without** re-deriving the lifetime of a file that was already materialized.

**Why it matters.** The bot's own contract (§8.2 S7, line 1593) sends the message referencing the
concrete `delivered_path` **while the operation is `stored`** (i.e. before any `delivered`). So the
normal path is: materialize → tell the agent the path → agent reads it (or not) → **≤ 15 min later the
file is gone**. A conversation whose agent reads the attachment after a pause (or on a later turn)
loses the file. §5.14.2 step 7's own wording ("the delivered copy remains the agent's file for the
life of the conversation") **contradicts** §5.10 line 948 for the (only reachable) case.

**Required fix (contract).** State the lifetime of the **materialized** copy **independently of
`delivered`**: once the bytes are materialized into the workspace, the file is the agent's file for
the life of the conversation (or a separate, explicitly-stated retention bound), and is **not** removed
by the `expires_at` sweep merely because U-3 is unavailable. Distinguish "staging retention bound"
(from which the `expires_at` sweep is derived) from "delivered-file lifetime". If the intent really is
to remove a materialized file at `expires_at`, then §5.14.2 step 7 and §5.10's "Persists for the life
of the conversation" must be corrected, and the hazard (agent loses a file it was told to read) must
be disclosed as an accepted limitation with its own threat row.

### R6-2 (MEDIUM, new) — the U-3 trust model is unspecified

**Claim in r6.** U-3 is "a structured read acknowledgment emitted (by the reader, or by the delivery
layer observing a **complete** read) that is durably recorded and reachable via the event log"
(§5.14.2 step 6, line 1229-1231). The field contract (§5.15, lines 1311-1322) lists fields,
correlation, semantics, and fail-closed failure behaviour.

**Gap.** The contract does **not** state **who is trusted to emit U-3**. Two readings are possible
from the text: (a) the **delivery layer** observes a complete read and emits U-3 (trusted,
Cloud-owned); or (b) the **reader tool / agent** emits it. If (b), then U-3 is **agent-emittable**,
and the F6a counterexample r6 closed **reopens one level up**: the model can emit a U-3 with
`read_complete == true` and a plausible `sha256` **without** having read the file, and `delivered`
(and the staging reclaim) is set. Since the SDK's `Observation.is_error` is model-adjacent and the
event log is the agent's own output stream, an agent-emittable acknowledgment is **self-attestation**,
not evidence.

**Why it matters.** U-3 is now the **sole** path to `delivered`. If its producer is not pinned to a
trusted, non-agent component, the "successful read" property is not actually established — the same
class of defect as r5's N-1, one abstraction level higher. The field contract is necessary but not
sufficient; the **producer's authority** is the load-bearing part.

**Required fix (contract).** State explicitly that U-3 **MUST** be emitted by a **trusted,
non-agent** component (the delivery layer / a reader whose observation the Cloud can authenticate),
that an **agent/tool-emitted** acknowledgment is **not** valid evidence, and how the Cloud
authenticates the emitter (internal credential, signed event, out-of-band channel). Add a test:
"an agent-emitted U-3 with `read_complete == true` for a file it did not read does **not** set
`delivered`."

### R6-3 (LOW, new, source-backed) — the "Cloud-reachable event log" is a polled replica; the evidence read is not atomic

**Claim in r6.** §5.14.1 calls `GET /api/v1/conversation/{id}/events/search` "a **durable,
conversation-bound, Cloud-reachable event log** — the evidence source for the read rule" (§5.14.1,
line 1136; §2.2, line 366). §5.14.2 step 6 defines the rule "over the agent-server conversation event
log, reachable via `GET …/events/search`".

**Gap.** Against the pinned source, that store is a **polled replica** of the agent-server event log,
not the agent-server log itself:

- `remote_sandbox_service.py::poll_agent_servers` (line 1256) runs `while True: … await
  asyncio.sleep(sleep_interval)`, listing running runtimes and calling `refresh_conversation` per
  conversation.
- `refresh_conversation` (line 1345) GETs the **agent-server** `…/events/search` and, for each event
  not already present, `event_service.save_event(...)` (line 1438) into the **Cloud** store
  (`filesystem_event_service.py::_store_event` = `path.write_text`, line 41).
- The proposal's own caveat (a) already says the sandbox host pattern is deployment-dependent, and
  caveat (c) is about the origin — but **none** of the r6 text discloses the replication lag, the poll
  interval, or that events are fetched page-by-page and saved **one at a time** (non-atomic read).

**Why it matters.** A U-3 rule that reads the Cloud store can observe a **torn** sequence: a valid
U-3 may be **not yet replicated** (false negative ⇒ stays `stored`; safe), but the reverse ordering
(ActionEvent present, its later error `AgentErrorEvent` not yet replicated) can make a **downgraded**
read look valid (false positive ⇒ `delivered`). r6's semantics (§5.15) require "no later
`AgentErrorEvent`/error observation for the same action" — a condition that is **only** decidable
against a **quiesced** source, which the Cloud replica is not guaranteed to be at read time.

**Required fix (contract).** State the freshness/quiescence requirement: the evidence read must be
taken from a **quiesced** source (or the rule must re-verify against the **agent-server** log, or must
wait a bounded settle interval), and the "no later error event" condition must be defined relative to
that quiesced read. Disclose the replica's lag as a caveat.

### R6-4 (LOW, new) — the named reader needs an absolute path, but `delivered_path` is workspace-relative

**Claim in r6.** §5.14.2 step 5 (line 1193-1196): "**`delivered_path` is workspace-relative**, and
the agent's tools resolve it against **the same confined workspace root** … so the agent's normal file
tools can open it." The preferred reader is file_editor `view`.

**Gap.** file_editor `view` **requires an absolute path**: `FileEditor.__call__` → `validate_path`
raises `EditorToolParameterInvalidError("path", …)` when `is_host_absolute_path(path)` is false
(`editor.py` line 666-679). A **relative** `delivered_path` (e.g. `uploads/{operation_id}/name`) is
**rejected** by the tool r6 names, and a missing path is also rejected on non-`create` commands (line
691). So "the agent's normal file tools can open it" is asserted but the relative→absolute resolution
is **not specified**; the agent would need to know the workspace root and prefix it.

**Why it matters.** This is the H-1 core: "the agent receives a **readable path**, not an inert
token." If the path handed to the agent is relative and the named reader requires absolute, the
"readable path" claim is not yet true end-to-end.

**Required fix (contract).** State how the **absolute** path is produced and given to the agent
(workspace-root-absolute `delivered_path`, or an explicit instruction to join the workspace root), and
name the exact tool invocation that will succeed. Add a test that the path as delivered to the agent is
accepted by file_editor `view` without further transformation.

### R6-5 (INFO, new) — stale "seven lifecycle facts" text survives

**Gap.** §5.14.0's heading/body are corrected to **eight** facts, and the header says "r6: eight"
(lines 107, 1074). But the r5 bullet in §1 still says "**seven lifecycle facts** (F1–F7…)" (line 106),
and §13's r5 row retains the r5 wording. This is the same *class* as r5's N-5 (stale
self-identification), only partly cleaned: the number "seven" now contradicts the "eight-fact" model
in the same document.

**Required fix.** Change the r5 bullet to note it was **superseded to eight facts in r6** (or restate
it as the historical r5 statement, explicitly marked superseded), so no live text claims seven facts.

---

## 6. State model, retention, and crash windows (independent re-check)

| Item | r6 claim | Check | Verdict |
| --- | --- | --- | --- |
| Observable states | `stored \| delivered \| rejected \| failed \| expired`; `accepted` internal-only | §5.5 (line 682) and §5.9 (line 806) examples both `stored`; §5.5 prose (line 693-701) consistent | **CONSISTENT** |
| `delivered` reachability | only via **U-3** (F6b) | §5.9/§5.10/§5.14.2/§6/§8.1/§9/§10 all consistent | **CONSISTENT** |
| Reclaim authority | `delivered` (U-3) or `expires_at`; never `consumed_at` alone | §5.10 + §8.3 + §12 Q12 consistent | **CONSISTENT** |
| Staging reclaim | `delivered`+terminal, or `expires_at` | §5.10 line 947 | **CONSISTENT** |
| **Materialized-file lifetime** | "persists for the life of the conversation" **but** "removed at `expires_at` if never `delivered`" | §5.10 line 948 vs §5.14.2 step 7 line 1243; today `delivered` is unreachable ⇒ **always** removed | **INCONSISTENT — R6-1** |
| Crash windows (§8.3) | 7 boundaries; no exactly-once claim | unchanged in substance; reclamation decoupled from the Telegram ack | **CONSISTENT** |
| `kind__eq` filter | supports `ActionEvent`/`ObservationEvent`/`AgentErrorEvent` | `EventKind = Literal[tuple(class names)]` (enterprise `84aec66c`) ⇒ the SDK class names are valid values | **CONSISTENT** |

---

## 7. What r6 does **not** claim (fairness note)

r6 is honest about its own limits: it does **not** claim U-3 exists, does **not** claim any existing
primitive proves a successful content read, does **not** claim a durable active-conversation accept
exists, and does **not** claim P0 is complete. It marks U-3 and the durable accept as **NEW upstream
work** and records the fallback (retention until `expires_at`). This candour is why the verdict is
`NEEDS_REVISION` and not `BLOCKED`.

---

## 8. Unverified / limitations of this review (honest list)

1. **No test was executed** for the upstream capability (it does not exist). I did not run the
   OpenHandBot test suite (this is a review-only task; no code changed).
2. **The live Cloud V1 spec** was not re-fetched this session; I rely on the proposal's `1.87.1`
   observation and on the pinned `enterprise` router, which is the repo that serves it. **UNVERIFIED**
   that the live spec is unchanged.
3. **The exact `sleep_interval`** of `poll_agent_servers` is a deployment value I did not read; the
   **existence** of the poll/replica path is source-verified (R6-3), the interval is not.
4. **R6-2** (U-3 producer) is a **design** gap, not a source error: the proposal simply does not pin
   the producer's authority. Whether the eventual upstream implementation makes U-3 trusted or
   agent-emittable is an owner/implementation decision.
5. This is a **single** independent review; it does not replace the upstream security review required
   by §7.8 / §9 criterion 10.

---

## 9. Verdict and required changes

**Verdict: `NEEDS_REVISION`.**

r6 correctly and verifiably fixes the r5 read-evidence defect (N-1) and the four smaller findings
(N-2…N-5), strengthens the read-evidence/retention rules, and weakens nothing. But it introduces one
**new lifetime hazard** and leaves three contract-level gaps in its new U-3 design.

**Required before owner approval (all documentation/contract-level):**

1. **R6-1 (MEDIUM, blocking).** Re-derive the **materialized-file lifetime** so a file materialized
   into the workspace is **not** deleted at `expires_at` merely because `delivered` is unreachable;
   resolve the §5.10 line 948 vs §5.14.2 step 7 contradiction. If deletion at `expires_at` is
   intended, correct the "persists for the life of the conversation" claims and disclose the hazard.
2. **R6-2 (MEDIUM, blocking).** Pin the **U-3 producer's trust model**: U-3 must be emitted by a
   **trusted, non-agent** component; an agent/tool-emitted acknowledgment must be **invalid**; state
   how the emitter is authenticated; add the spoofing test.
3. **R6-3 (LOW).** State the **freshness/quiescence** requirement for the evidence read (the Cloud
   store is a **polled replica**; the "no later error event" condition needs a quiesced source or an
   agent-server re-verify); disclose the replica lag as a caveat.
4. **R6-4 (LOW).** Specify the **absolute** path given to the agent (file_editor `view` requires an
   absolute path); add the "path is openable as delivered" test.
5. **R6-5 (INFO).** Remove/qualify the stale "seven lifecycle facts" text (§1 line 106; §13 r5 row).

**No new upstream machinery beyond U-1…U-9 is required.** The events, fields, and primitives exist;
the gaps are in the **contract's precision**, not in the upstream inventory. After items 1–2 (and
preferably 3–5) are fixed, an r7 review should be able to move to `PASS_WITH_NOTES` or `PASS`.

---

*This review was produced by an independent adversarial reviewer agent (OpenHands) on behalf of the
repository owner. Read-only: no production call, no credential, no modification of the proposal or
any other tracked file. This file is the only artifact created.*
