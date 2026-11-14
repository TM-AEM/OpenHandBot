# OHB2-P0-SECURE-UPLOAD-PROPOSAL-R6 — HOSTILE SELF-REVIEW

**Task ID:** `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R6-READ-EVIDENCE-AND-PRIMITIVE-CORRECTIONS`

**Status of this document:** the **author's own hostile consistency review** of the r6 proposal
(`docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md`). It is **not** an independent
review: the r5 findings were remediated by the same agent that wrote r5, so this is
**self-assessment**, not independent assurance. An **independent adversarial review of r6 is still
required** (proposal §9 criterion 10). Every claim that could not be verified is marked **UNVERIFIED**
or **UNKNOWN**; no test outcome or source semantic is fabricated.

- **Repo:** `TM-AEM/OpenHandBot` · **branch** `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW` ·
  **HEAD** `907b20de3fa6627795c14f29677e9f39c68e82f4` · **origin/main** `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c`.
- **r5 proposal SHA-256 (input):** `6008c3ab44149b4a4cd9988fb9760752a92b9c38caf86672557f133341227085` (1840 lines).
- **r6 proposal SHA-256 (output):** `a02b9747d8639759f395a730bec468091a9dcef5ba510ae596245b4e276693c0` (2098 lines).
- **Driving review:** `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R5-INDEPENDENT-ADVERSARIAL-REVIEW.md`
  (sha256 `4d5d708804c466a1b7832cfe95c07f962abba04f9e9f745921285734673e94b0`), verdict **`NEEDS_REVISION`**,
  findings **N-1** (MEDIUM, blocking) + **N-2/N-3** (LOW) + **N-4/N-5** (INFO).
- **Scope:** documentation only. **No code, test, schema, or runtime change. P0 is NOT implemented.**
- **Method:** read the R5 review findings N-1…N-5 and §5/§7/§8 in full; re-verified each claim against
  the pinned public source (re-fetched this session into `/tmp/r5rev`); applied the r6 corrections;
  then attempted to *break* r6 on the same axes (read evidence, `pending-messages` composability,
  reader choice, state/retention, header identity).

---

## 1. Evidence re-verification (this session, read-only)

All sources fetched from the **pinned revisions** already used at r2–r5
(`OpenHands/software-agent-sdk@9f7d5cb11b1256c1878f5584a657401feca9ad16`,
`OpenHands/sandbox-server@43e91604ccd0a9960c8d5c52faadd60b30f10e63`,
`OpenHands/enterprise@3fac53df8c2efcb67ff3537d1162e8c8a108f565`). **No production call, no credential,
no secret access.**

| # | Claim (finding) | Source (pinned, sha256 prefix) | Result |
| --- | --- | --- | --- |
| 1 | The **terminal** completed-command path returns a **non-error** `TerminalObservation` for a **non-zero** exit (N-1 counterexample) | `openhands-tools/…/tools/terminal/terminal/terminal_session.py` `72504a4d…`: `is_error=True` appears only at interaction/empty-input/multi-command/closed-terminal sites | **MATCH** |
| 2 | The only error flag on an observation is `Observation.is_error`, default **`False`** | `openhands-sdk/…/sdk/tool/schema.py` `76b4f42a…` (`is_error: bool = False`) | **MATCH** |
| 3 | file_editor `view` raises `ToolError` ⇒ `is_error=True`; a successful `view` is **truncated** | `…/tools/file_editor/impl.py` `35353ad3…`; `…/editor.py` `a1d735d4…`; `…/utils/constants.py` `a5b3f2bf…` (`MAX_RESPONSE_LEN_CHAR = 16000`) | **MATCH** |
| 4 | A **structured** `read_file` tool exists but is **not** a default tool | `…/tools/gemini/read_file/definition.py` `893fd5d5…`, `…/impl.py` `2d5f81f2…`; `openhands-sdk/…/sdk/tool/defaults.py` `357f005b…` (`DEFAULT_EXEC_TOOL_NAMES = ("terminal","file_editor","task_tracker")`); `tests/cross/test_default_tool_names.py` `3b406311…` | **MATCH** (N-4) |
| 5 | `pending-messages` is drained **only** at conversation **start** | `enterprise` `…/live_status_app_conversation_service.py` `9f4f1596…`: `_process_pending_messages` defined once and called **once** from the start path after `READY` | **MATCH** (N-3) |
| 6 | The §5.5 create example must show `stored`, not `accepted` | r6 proposal §5.5 (line ~667 `"state": "stored"`) | **MATCH** (N-2) |
| 7 | The header must self-identify as r6 and list the r5/r6 task ids | r6 proposal header (lines 1–29) | **MATCH** (N-5) |

**Source-revision note:** the pinned SHAs are unchanged from r2–r5; sources were re-fetched this
session. The live Cloud V1 spec remains `1.87.1`, 242 paths, **no** upload operation.

---

## 2. Remediation mapping — all five R5 findings

| # | R5 finding | r6 location(s) | r6 action | Self-assessment |
| --- | --- | --- | --- | --- |
| **N-1** | MEDIUM (blocking): the F6 "non-error observation" rule can set `delivered` on a **failed** read | §5.14.0 (eight-fact model, F6a/F6b); §5.14.2 step 6; §5.9 `delivered`; §7.5; §6 T-18/T-19; §8.1 I12/I14; §9 7c; §10.1/§10.2; §5.15 U-3 (+ field contract); §12 Q5b/Q5c/Q16; §11 (source entries; caveats e/f); §4; §5.10; §5.11; §1/§13 | **Withdrew** "correlated non-error observation" as sufficient; split **F6a** (non-error observation) from **F6b** (successful *content* read); stated **no existing primitive proves F6b**; required the **new U-3 structured read acknowledgment** with a field contract; `delivered` is **unreachable** without U-3 and the fallback is retention-until-`expires_at` (no early reclaim) | **RESOLVED (as a contract).** Residual: U-3 itself is a **proposed** upstream capability — recorded as an owner decision (Q16). |
| **N-2** | LOW: §5.5 example shows `"state": "accepted"` | §5.5 (example + note); §1/§13 | Changed to `"state": "stored"`; added an explicit note; re-checked all other examples (§5.9 status example already `stored`) | **RESOLVED.** |
| **N-3** | LOW: `pending-messages` is start-only, not an active-conversation accept | §5.9.1; §5.14.1 (table + classification); §5.15 U-2; §8.2 S7; §8.3 (a); §2.2; §11; §12 Q12/Q15 | Stated the **start-only** limitation (drained once at start, deleted regardless of delivery success, capped at 10); re-classified **U-2 as NEW for the running-conversation case** | **RESOLVED.** |
| **N-4** | INFO: §5.14.2 step 5 offers terminal `cat` without its success signal | §5.14.2 step 5 (reader + success signal); §11 (source entry) | Named the **structured read tool** and the **U-3** signal; **explicitly rejected** terminal `cat` (a non-zero `exit_code` is a failed read even when `is_error == false`); noted the structured `read_file` is **not** a default tool | **RESOLVED.** |
| **N-5** | INFO: header self-identification stale | header (task-id list, dates, review list) | Header now identifies **r6**, lists the r5 + r6 task ids and both driving reviews | **RESOLVED.** |

**Preservation:** no security requirement, threat-model row, or P0 invariant was **weakened**. The
read-evidence and retention rules were made **stricter** (a false `delivered` is now *unreachable*).
The four-gap conclusion, the rejected approaches, the §6 threat table (T-18/T-19 strengthened), and
§8 invariants I1–I14 are intact.

---

## 3. Attempts to break r6 (hostile checks)

| # | Attack | Result |
| --- | --- | --- |
| 3.1 | "A non-error observation still sets `delivered` somewhere." | **Blocked.** §5.9 `delivered`, §7.5, §6 T-18/T-19, §8.1 I12/I14, §9 7c, §10.1/§10.2 and §5.14.2 step 6 all require **U-3** (F6b); F6a is explicitly *necessary but not sufficient* (§5.14.0). |
| 3.2 | "The `expires_at` fallback silently becomes a success." | **Blocked.** §5.10/§5.14.2 step 6/§12 Q16 state the fallback is a **retention bound**, **not** a read proof, and authorizes **no** early reclaim. |
| 3.3 | "`pending-messages` is still offered as a durable accept for a running conversation." | **Blocked.** §5.9.1/§5.14.1/§5.15 U-2/§8.2 S7/§2.2 all state the **start-only** limitation; U-2 is **NEW** for the running case. |
| 3.4 | "Terminal `cat` is still named as an F6b reader." | **Blocked.** §5.14.2 step 5 rejects it explicitly; the only named readers are structured (file_editor `view`, or a deployment-enabled structured `read_file`). |
| 3.5 | "A bare `ActionEvent` (F4) or the appended message (F2/F3) is treated as a read." | **Blocked.** §5.14.0 and step 6 reject F4 and F2/F3 for `delivered`. |
| 3.6 | "The proposal claims a P0 invariant or threat mitigation was dropped." | **No weakening.** One threat row added at r5 (T-21); r6 strengthens T-18/T-19; all invariants I1–I14 present. |

---

## 4. State-model, retention, and crash-window re-check (independent)

| Item | r6 claim | Check | Verdict |
| --- | --- | --- | --- |
| Observable states | `stored \| delivered \| rejected \| failed \| expired`; `accepted` internal-only | §5.5/§5.9 agree; examples show `stored` | **CONSISTENT** |
| `delivered` reachability | only via **U-3** (F6b) | §5.9/§5.10/§5.14.2/§6/§8.1/§9/§10 all consistent | **CONSISTENT** |
| Reclaim authority | `delivered` (U-3) or `expires_at`; never `consumed_at` alone | §5.10 + §8.3 + §12 Q12 consistent | **CONSISTENT** |
| Crash windows (§8.3) | 7 boundaries; no exactly-once claim | unchanged in substance; reclamation decoupled from the Telegram ack | **CONSISTENT** |

---

## 5. What r6 does **not** claim

- It does **not** claim U-3 exists, nor that any existing primitive proves a successful content read.
- It does **not** claim a durable **active-conversation** accept exists.
- It does **not** claim P0 is complete; the capability still requires **upstream work + a maintainer
  decision** (§5.15, §12).

---

## 6. Unverified / limitations (honest list)

1. **U-3 is a proposal.** Its field contract is a **design**, not an implemented signal
   (**UNVERIFIED** upstream).
2. **Deployment parameters** — delivered-file mode/ownership (§7.4, §12 Q14) and whether a
   deployment enables a structured `read_file` tool — remain **UNVERIFIED**.
3. **Live Cloud V1** remains `1.87.1` with no upload operation (**UNVERIFIED** to have changed).
4. **No test was executed** for the upstream capability (it does not exist); existing OpenHandBot
   attachment-rejection tests are unchanged by this task.
5. **Independence:** this is a **self-review**; an independent adversarial review of r6 is still
   required (§9 criterion 10).

---

## 7. Verdict of this self-review

**The five R5 findings (N-1…N-5) are addressed in the r6 text**, with the read-evidence and retention
rules made **stricter** and **no** security requirement, threat-model row, or P0 invariant weakened.
Two residual uncertainties are inherent and disclosed: (a) U-3 is a **proposed** signal, and (b) some
deployment parameters remain **UNVERIFIED**. Because the r5 remediation was authored by the same agent,
this document is **self-assessment only**; **an independent adversarial review of r6 is required**
before r6 is treated as accepted.
