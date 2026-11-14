# OHB2-P0-SECURE-UPLOAD-PROPOSAL-R8 — HOSTILE SELF-REVIEW

**Task ID:** `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R8-R7-INDEPENDENT-FINDINGS-REMEDIATION`

**Status of this document:** the **author's own hostile consistency review** of the r8 proposal
(`docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md`). It is **not** an independent
review: the R7 findings were remediated by the same agent that produced r7, so this is
**self-assessment**, not independent assurance. An **independent adversarial review of r8 is still
required** (proposal §9 criterion 10). Every claim that could not be verified is marked **UNVERIFIED**
or **UNKNOWN**; no test outcome or source semantic is fabricated.

- **Repo:** `TM-AEM/OpenHandBot` · **branch** `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW` ·
  **HEAD** `907b20de3fa6627795c14f29677e9f39c68e82f4` · **origin/main** `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c`.
- **r7 proposal SHA-256 (input):** `d4e4fdc84b7a474e1ff166026dec187db65702ae238316466972d27a36342ba1` (2504 lines).
- **r8 proposal SHA-256 (output):** `229b5ae18e0222454f10bef4b94562736b983f711c07a452a35b5226fb240645` (2770 lines).
- **Driving review:** `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R7-INDEPENDENT-ADVERSARIAL-REVIEW.md`
  (sha256 `1b276ac684ee9ce3f1a72b460cff2fe667ea33ea5ff2662bc7c0e6b5ae5bd2ed`, 423 lines), verdict
  **`NEEDS_REVISION`**, findings **R7-1** (MEDIUM, blocking) + **R7-2** (MEDIUM, blocking) + **R7-3**
  (LOW) + **R7-4** (INFO).
- **Scope:** documentation only. **No code, test, schema, or runtime change. P0 is NOT implemented.**
- **Method:** read the R7 review findings R7-1…R7-4 and the R7 review §9 "required changes" in full;
  re-verified each cited fact against the pinned public source (re-fetched and re-hashed this session);
  applied the r8 corrections; then attempted to *break* r8 on the same axes (C2 reclaim, workspace-root
  provenance, replica universality, taxonomy drift) and on cross-section consistency.

---

## 1. Evidence re-verification (this session, read-only)

All sources fetched from the **pinned revisions** already used at r2–r7
(`OpenHands/software-agent-sdk@9f7d5cb11b1256c1878f5584a657401feca9ad16`,
`OpenHands/sandbox-server@43e91604ccd0a9960c8d5c52faadd60b30f10e63`,
`OpenHands/enterprise@3fac53df8c2efcb67ff3537d1162e8c8a108f565`). **No production call, no credential,
no secret access.** File `sha256` prefixes below match the R7 review's citations.

| # | Claim (finding) | Source (pinned, sha256 prefix) | Result |
| --- | --- | --- | --- |
| 1 | Conversation delete **archives** the workspace and tears the **sandbox** down only when no sibling references it (R7-1) | `enterprise` `…/app_conversation/app_conversation_router.py` `c43ed4f7…`: `_finalize_sandbox_delete` (line 1050) → `archive_conversation_workspace` (line 1071); sandbox down only if `count_conversations_by_sandbox_id(...) == 0` (lines 1083-1091) | **MATCH** |
| 2 | The workspace archive is a **bucket capture**, not a byte deletion (R7-1) | `enterprise` `…/sandbox/ws_archive.py` `202fc8e1…`: `archive_workspace` (line 334) uploads via `store.write` (line 516) | **MATCH** |
| 3 | The agent-server delete **preserves** the workspace (R7-1) | `enterprise` `…/agent_server/conversation_service.py` `9e9b3e63…` (line 1911): "Safely remove only the conversation directory (**workspace is preserved**)" | **MATCH** |
| 4 | `_get_agent_server_context` carries **no** per-conversation workspace root (R7-2) | `enterprise` `…/app_conversation/app_conversation_router.py` `c43ed4f7…`: `AgentServerContext` (lines 220-228) has no workspace-path field; `sandbox_spec.working_dir` only (lines 278/300-306) | **MATCH** |
| 5 | The **grouped** root exists and is pinned in the `archiveworkspacepath` tag (R7-2) | `enterprise` `…/settings/settings_models.py` `27bae62a…`: `grouped_workspace_dir` (line 753), `SandboxGroupingStrategy` (lines 739-748); `…/app_conversation/app_conversation_models.py` `7a4a54c0…`: `ARCHIVE_WORKSPACE_PATH_TAG_KEY` (line 65), `RESERVED_TAG_KEYS` (line 96); written by `…/live_status_app_conversation_service.py` `9f4f1596…` (line 1124) | **MATCH** |
| 6 | The agent-server derives the root from its **own** conversation (R7-2) | `sdk` `…/agent_server/runtime_router.py` `5bea70f0…` (lines 41-43): `workspace_root = Path(event_service.get_conversation().workspace.working_dir).resolve()` | **MATCH** |
| 7 | The event-store poller is **conditional** on the absence of a public URL (R7-3) | `enterprise` `…/sandbox/remote_sandbox_service.py` `d239ec43…`: poll started only when `web_url is None or 'localhost' in web_url` (lines 1518-1526) | **MATCH** |
| 8 | The poll copies events **one at a time** (context for R7-3) | `enterprise` `…/sandbox/remote_sandbox_service.py` `d239ec43…`: `refresh_conversation` (line 1345) → `event_service.save_event` (line 1438) | **MATCH** |
| 9 | The sandbox-scoped delete **never archives** (R7-1 context) | `enterprise` `…/sandbox/sbx_router.py` `bb9bbe23…`; `…/sandbox/remote_sandbox_service.py` `d239ec43…` `delete_sandbox` (lines 917-925) | **MATCH** |

**Source-revision note:** the pinned SHAs are unchanged from r2–r7; sources were re-fetched this
session and the file hashes match the R7 review. The live Cloud V1 spec remains `1.87.1`, 242 paths,
**no** upload operation.

---

## 2. Remediation mapping — all four R7 findings

| # | R7 finding | r8 location(s) | r8 action | Self-assessment |
| --- | --- | --- | --- | --- |
| **R7-1** | MEDIUM (blocking): the "workspace is removed on conversation delete" C2-reclaim premise is not source-grounded | §5.10.1 (C2 row + cleanup-eligibility bullet + "Conversation ended/deleted"), §5.10.3 case 10, §5.10.4, §5.9 (`expired`), §5.14.2 step 7, §5.14.4 (2 rows), §6 T-19/T-24, §8.1 I12, §9 7b, §10.1, §12 Q18, §11 (caveat (f) + new source entry), §13 | **Withdrew** the premise: conversation archive/delete **archives** the workspace (`_finalize_sandbox_delete` → `archive_conversation_workspace` → `archive_workspace`) and tears the **sandbox** down only when **no sibling references it**; the agent-server delete **preserves** the workspace. Stated plainly that **today no conversation-scoped event reclaims C2**; defined the only physical-removal path as **sandbox/pod teardown** ("runtime-api idle reap", **unmodeled**, **indefinitely delayed** under grouping); added a **grouping caveat**; **strengthened** the disclosed unbounded-storage limitation. **No cleanup primitive invented.** | **RESOLVED (as a contract).** Residual: **unbounded C2 storage** remains a **disclosed** limitation and an owner decision (Q18) |
| **R7-2** | MEDIUM (blocking): the path contract resolved the workspace root from `_get_agent_server_context`, which does not carry it | §5.14.2 step 3, §5.15.5 (2 rows), **new §5.15.6**, §5.15 U-12, §7.0 (Q3 + reuse map), §7.1, §7.4, §5.14.4, §6 T-25, §8.1 I15, §10.1, §12 Q22, §11 (new source entry), §13 | Pinned the **authoritative** root source (`archiveworkspacepath` tag, or an agent-server query for the runtime's own `workspace.working_dir`); stated the **grouping** behavior (`{base}/{conversation_id.hex}` under any non-`NO_GROUPING`); added a **provenance/binding contract** (bind to `(principal, conversation_id, operation_id)`; tag is server-managed; `_get_agent_server_context` resolves the **endpoint + key**, not the root); classified the binding **NEW (U-12) + UNVERIFIED**; the write **fails closed** if the binding is unavailable | **RESOLVED (as a contract).** Residual: U-12 is a **proposed** capability (disclosed, Q22) |
| **R7-3** | LOW: the polled-replica description is not universal | §5.15.4, §5.15 U-10, §11 (event-store entry), §12 Q20, §10.1, §13 | Separated **authoritative** (agent-server event log) from **replicated** (Cloud store) state; stated **both** population paths (poll **only when no public URL**, else **webhooks**); kept the **quiescence requirement** on **both** paths | **RESOLVED.** |
| **R7-4** | INFO: two "eight"-item taxonomies without a cross-map | **new §5.10.0.1**, §5.14.0 (back-reference), §13 | Added the explicit, complete **L1–L8 ↔ F1–F7/F6a/F6b cross-map** (only **L6 ↔ F6b** and **L7 ↔ F7** are the *same* milestone) and a §5.14.0 back-reference | **RESOLVED.** |

**Preservation:** no security requirement, threat-model row, or P0 invariant was **weakened**. The
lifecycle, provenance, and replica rules were made **stricter** and **more explicit**. The four-gap
conclusion, the rejected approaches, the §6 threat table (T-19/T-24 refined; T-25 added), and §8
invariants I1–I14 (I15 added) are intact.

---

## 3. Attempts to break r8 (hostile checks)

| # | Attack | Result |
| --- | --- | --- |
| 3.1 | "Somewhere r8 still claims conversation archive/delete removes the workspace / reclaims C2." | **Blocked.** §5.10.1, §5.9, §5.10.3, §5.10.4, §5.14.2 step 7, §5.14.4, §6 T-19/T-24, §8.1 I12, §9 7b, §10.1, §12 Q18 all now state the **archive + preserve** behavior and that **no conversation-scoped event reclaims C2**. |
| 3.2 | "r8 still presents `_get_agent_server_context` / `sandbox_spec.working_dir` as the per-conversation root." | **Blocked.** §5.14.2 step 3, §5.15.5, §5.15.6, §7.0, §7.4 all state the helper carries the **ungrouped base** and is **not** a valid root source; the authoritative source is pinned. |
| 3.3 | "r8 presents the per-conversation root as currently available (false 'implementable' claim)." | **No false claim.** §5.15.6 classifies the Cloud-side root read as **NEW (U-12) + UNVERIFIED**; §12 Q22 records it; §7.4 requires **fail-closed**. |
| 3.4 | "The grouping behavior is hidden or contradicted." | **Blocked.** §5.10.1, §5.10.4, §5.15.5, §5.15.6, §5.14.2 step 3/5, §10.1, §12 Q22 all state the **grouped** `{base}/{conversation_id.hex}` root under any non-`NO_GROUPING` strategy. |
| 3.5 | "The polled-replica wording is still universal." | **Blocked.** §5.15.4 and §11 state the poller runs **only when there is no public URL**; otherwise **webhooks**; the quiescence requirement holds **both** ways. |
| 3.6 | "The L/F cross-map is partial or wrong." | **Blocked.** §5.10.0.1 maps **every** L-concept (L1–L8) and lists the F-only facts (F1–F5, F6a); §5.14.0 back-references it. |
| 3.7 | "A security requirement or invariant was dropped." | **No weakening.** All invariants I1–I14 present; **I15 added**; T-19/T-24 refined; **T-25 added**; §6 mitigations intact. |
| 3.8 | "r8 invents a C2 cleanup primitive or claims the storage bound is closed." | **No.** §5.10.4 and Q18 keep it an **open owner decision** with a **disclosed** unbounded default; §7.0 states **no** primitive is invented. |

---

## 4. State-model, lifecycle, and crash-window re-check (independent)

| Item | r8 claim | Check | Verdict |
| --- | --- | --- | --- |
| Observable states | `stored \| delivered \| rejected \| failed \| expired`; `accepted` internal-only | §5.5/§5.9 agree; `expired` row updated | **CONSISTENT** |
| `delivered` reachability | only via **U-3** (F6b) from a **trusted, non-agent** issuer, from a **quiesced** source | §5.9/§5.10/§5.14.2/§5.15.1–§5.15.4/§6/§8.1/§9/§10 all consistent | **CONSISTENT** |
| Staging reclaim authority | `delivered` (U-3) or `expires_at`; never `consumed_at` alone | §5.10.1 (C1 row) + §8.3 + §12 Q12 consistent | **CONSISTENT** |
| Workspace-copy lifetime | never timer-deleted; only F7 (unmodeled) or **physical** workspace removal (sandbox teardown); **not** conversation archive/delete | §5.10.0–§5.10.4 + §5.14.2 step 7 + §5.14.4 + §6 T-19/T-24 + §8.1 I12 + §9 7b consistent | **CONSISTENT** |
| Workspace-root provenance | authoritative source pinned; bound to `(principal, conversation_id, operation_id)`; fail closed | §5.14.2 step 3 + §5.15.5 + §5.15.6 + §6 T-25 + §8.1 I15 + §12 Q22 consistent | **CONSISTENT** |
| Agent-facing path form | **absolute** | §5.14.2 step 5 + §5.15.5 + §5.14.4 + §5.7 + §5.9 consistent | **CONSISTENT** |
| Event-evidence source | quiesced/finalized (not the replica), on **either** population path | §5.15.4 + §5.14.1 + §5.14.2 step 6 + §2.2 + §7.5 + §6 T-23 consistent | **CONSISTENT** |
| L/F taxonomy | two vocabularies, explicitly cross-mapped | §5.10.0.1 + §5.14.0 consistent | **CONSISTENT** |
| Crash windows (§8.3) / lifecycle races (§5.10.3) | unchanged in substance; no copy needed for reconciliation or active use is deleted | §5.10.3 case 10 updated; each case states a required behaviour consistent with §5.10.1 | **CONSISTENT** |

---

## 5. What r8 does **not** claim

- It does **not** claim U-3 exists, nor that any existing primitive proves a successful content read,
  nor that a trusted non-agent issuer exists.
- It does **not** claim a quiesced evidence source (U-10), the absolute-path producer (U-11), or the
  Cloud-side **workspace-root provenance/binding** (U-12) exist.
- It does **not** claim a durable **active-conversation** accept exists.
- It does **not** claim a **bounded** retention policy for the workspace copy exists (Q18 open), nor
  that conversation archive/delete reclaims C2.
- It does **not** claim P0 is complete; the capability still requires **upstream work + a maintainer
  decision** (§5.15, §12).

---

## 6. Unverified / limitations (honest list)

1. **U-3 is a proposal** and its issuer is **UNVERIFIED** to exist (no read-acknowledgment primitive
   found in the pinned SDK).
2. **U-10** (quiesced source), **U-11** (absolute-path producer/content identity), and **U-12**
   (Cloud-side workspace-root provenance/binding) are **NEW upstream work** unless the implementation
   provides them.
3. **Unbounded workspace storage (Q18)** is a **disclosed, deliberate** safe default, not a closed
   item; r8 **strengthens** the disclosure (no conversation-scoped C2 reclaim).
4. **The physical-removal backstop ("runtime-api idle reap") is outside the pinned repos** — its
   exact trigger, delay, and grouping interaction are **UNVERIFIED**; r8 names it only as the
   source-visible *backstop*, not a modeled mechanism.
5. **Deployment parameters** — delivered-file mode/ownership (§7.4, §12 Q14) and whether a deployment
   enables a structured `read_file` tool — remain **UNVERIFIED**.
6. **Live Cloud V1** remains `1.87.1` with no upload operation (**UNVERIFIED** to have changed).
7. **No test was executed** for the upstream capability (it does not exist); existing OpenHandBot
   attachment-rejection tests are unchanged by this task.
8. **Independence:** this is a **self-review**; an independent adversarial review of r8 is still
   required (§9 criterion 10).

---

## 7. Verdict of this self-review

**The four R7 findings (R7-1…R7-4) are addressed in the r8 text**, with the lifecycle, provenance, and
replica rules made **stricter** and **source-grounded**, and **no** security requirement,
threat-model row, or P0 invariant weakened. Two residual uncertainties are inherent and disclosed:
(a) U-3 and its trusted issuer are **proposed** (and unverified), and (b) the workspace-copy retention
bound is an **open owner decision** with a disclosed unbounded default, now **strengthened** by the
verified fact that conversation archive/delete does not reclaim C2. Because the R7 remediation was
authored by the same agent that produced r7, this document is **self-assessment only**; **an
independent adversarial review of r8 is required** before r8 is treated as accepted.
