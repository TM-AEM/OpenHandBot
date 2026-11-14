# OHB2-P0-SECURE-UPLOAD-PROPOSAL-R7 — HOSTILE SELF-REVIEW

**Task ID:** `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R7-LIFECYCLE-AND-TRUST-REMEDIATION`

**Status of this document:** the **author's own hostile consistency review** of the r7 proposal
(`docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md`). It is **not** an independent
review: the r6 findings were remediated by the same agent that wrote r6, so this is
**self-assessment**, not independent assurance. An **independent adversarial review of r7 is still
required** (proposal §9 criterion 10). Every claim that could not be verified is marked **UNVERIFIED**
or **UNKNOWN**; no test outcome or source semantic is fabricated.

- **Repo:** `TM-AEM/OpenHandBot` · **branch** `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW` ·
  **HEAD** `907b20de3fa6627795c14f29677e9f39c68e82f4` · **origin/main** `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c`.
- **r6 proposal SHA-256 (input):** `a02b9747d8639759f395a730bec468091a9dcef5ba510ae596245b4e276693c0` (2098 lines).
- **r7 proposal SHA-256 (output):** `d4e4fdc84b7a474e1ff166026dec187db65702ae238316466972d27a36342ba1` (2504 lines).
- **Driving review:** `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R6-INDEPENDENT-ADVERSARIAL-REVIEW.md`
  (sha256 `e264ebdf8c4d3c17566c99ea396c7fa106293486786ce3cdbac7c04a2049564e`), verdict **`NEEDS_REVISION`**,
  findings **R6-1** (MEDIUM, blocking) + **R6-2** (MEDIUM, blocking) + **R6-3/R6-4** (LOW) + **R6-5** (INFO).
- **Scope:** documentation only. **No code, test, schema, or runtime change. P0 is NOT implemented.**
- **Method:** read the R6 review findings R6-1…R6-5 and §5/§6/§7/§8/§9/§11/§12 in full; re-verified each
  claim against the pinned public source (re-fetched this session); applied the r7 corrections; then
  attempted to *break* r7 on the same axes (materialized-file lifetime, U-3 trust, event consistency,
  path form, stale wording) and on cross-section consistency.

---

## 1. Evidence re-verification (this session, read-only)

All sources fetched from the **pinned revisions** already used at r2–r6
(`OpenHands/software-agent-sdk@9f7d5cb11b1256c1878f5584a657401feca9ad16`,
`OpenHands/sandbox-server@43e91604ccd0a9960c8d5c52faadd60b30f10e63`,
`OpenHands/enterprise@3fac53df8c2efcb67ff3537d1162e8c8a108f565`). **No production call, no credential,
no secret access.**

| # | Claim (finding) | Source (pinned, sha256 prefix) | Result |
| --- | --- | --- | --- |
| 1 | The Cloud event store is a **polled replica**, not an atomic view (R6-3) | `enterprise` `…/sandbox/remote_sandbox_service.py` `d239ec43…`: `poll_agent_servers` (`while True … await asyncio.sleep(sleep_interval)`) → `refresh_conversation` (line 1345) → `event_service.save_event` (line 1438), one event at a time | **MATCH** |
| 2 | The named reader **requires an absolute path** (R6-4) | `openhands-tools/…/tools/file_editor/editor.py` `a1d735d4…`: `validate_path` (line 657) raises `EditorToolParameterInvalidError("path", …)` when `is_host_absolute_path(path)` is false (line 666) | **MATCH** |
| 3 | **No read-acknowledgment primitive exists** in the SDK (R6-2) | code search over the pinned SDK for `read_complete` / `read_receipt` / `bytes_read` ⇒ **0** results | **MATCH** |
| 4 | The `Observation.is_error` default and the terminal non-error failure semantics are as r6 stated (context for R6-2) | `openhands-sdk/…/sdk/tool/schema.py` `76b4f42a…`; `openhands-tools/…/tools/terminal/terminal/terminal_session.py` `72504a4d…` | **MATCH** (unchanged from r6) |

**Source-revision note:** the pinned SHAs are unchanged from r2–r6; sources were re-fetched this
session. The live Cloud V1 spec remains `1.87.1`, 242 paths, **no** upload operation.

---

## 2. Remediation mapping — all five R6 findings

| # | R6 finding | r7 location(s) | r7 action | Self-assessment |
| --- | --- | --- | --- | --- |
| **R6-1** | MEDIUM (blocking): the **materialized** file is deleted at `expires_at` even if never read; §5.10 vs §5.14.2 step 7 contradiction | §5.10 (fully re-derived: §5.10.0 concepts, §5.10.1 per-copy table, §5.10.2 post-text lifecycle, §5.10.3 crash/race, §5.10.4 retention bound, §5.10.5 deadline); §5.9 `expired`/`delivered` rows; §5.14.2 step 7; §5.14.4; §5.11; §6 T-19/T-24; §8.1 I10/I12; §8.3; §9 7b/7c; §10.1/§10.2; §12 Q6/Q16/Q18; §13 | **Re-derived** the lifecycle: **eight** concepts are separated and **each physical copy** (C1 staging, C2 workspace, C3 recovery, C4 op rows, C5 local rows) has its own deletion rule. **`expires_at` reclaims C1/C3 only**; **C2 is never timer-deleted** — it is reclaimed only on a trustworthy **F7 end-of-use** (unmodeled) or **workspace removal**. The r6 "delete at `expires_at`" wording is **withdrawn** | **RESOLVED (as a contract).** Residual: **unbounded C2 storage** is a **disclosed** limitation and an owner decision (Q18) |
| **R6-2** | MEDIUM (blocking): the U-3 trust model is unspecified | §5.15.1 (trust boundary), §5.15.2 (provenance/authentication), §5.15.3 (fields + 8 validation invariants + fact mapping); §5.14.0 F6b; §5.14.2 step 6; §5.15 U-3 row; §5.11; §6 T-18/T-22; §8.1 I14; §9 7c; §10.1; §12 Q16/Q19; §1; §13 | Pinned the **trust boundary**: U-3 MUST be issued by a **trusted, non-agent** service-side component; an **agent/tool/prompt-emitted** acknowledgment is **never** evidence; specified **authenticated provenance**, **integrity**, **replay protection**, and **authorization scope**; the issuer is classified **NEW upstream capability** and **UNVERIFIED**; `delivered` stays **unreachable** until it exists | **RESOLVED (as a contract).** Residual: U-3 itself is a **proposed** capability (disclosed, Q16/Q19) |
| **R6-3** | LOW: the "Cloud-reachable event log" is a **polled replica**; the evidence read is not atomic | §5.15.4 (consistency requirement) + **U-10**; §5.14.1 table; §5.14.2 step 6; §2.2; §7.5; §6 T-23; §9 7c; §10.1; §11 (source entry); §12 Q20; §1; §13 | Verified the poll/replica path; required any **event-based evidence** to come from a **quiesced/finalized** source or an **agent-server re-verify**; disclosed the replication lag and the **non-atomic** read; classified the gap **NEW upstream work (U-10)** | **RESOLVED (as a contract).** Residual: a quiesced source is **NEW upstream work** (disclosed) |
| **R6-4** | LOW: the reader needs an **absolute** path, but `delivered_path` is workspace-relative | §5.15.5 (complete path contract) + **U-11**; §5.14.2 step 5; §5.14.4; §5.7; §5.9; §5.15 U-1; §6 T-22; §9 7c; §10.2; §11 (source entry); §12 Q21; §1; §13 | Specified the **absolute** agent-facing path and the full path contract (server-side resolution, workspace root, absolute representation, post-resolution confinement, symlink/TOCTOU, existence/regular-file, content identity, permissions, reader's accepted input); the r6 **relative** `delivered_path` is **superseded**; the producer-to-reader flow is **implementable** or classified **NEW upstream work (U-11)** | **RESOLVED (as a contract).** Residual: none beyond the deployment permission parameter (§12 Q14) |
| **R6-5** | INFO: stale "seven lifecycle facts" text survives | header (r5 notice bullet); §13 (r5 row); §5.14.0 (already eight) | Qualified the r5 "seven" references as **superseded** by the **eight-fact** model at r6/r7 | **RESOLVED.** |

**Preservation:** no security requirement, threat-model row, or P0 invariant was **weakened**. The
lifecycle and trust rules were made **stricter** and **more explicit**. The four-gap conclusion, the
rejected approaches, the §6 threat table (T-18/T-19 strengthened; T-22/T-23/T-24 added), and §8
invariants I1–I14 are intact.

---

## 3. Attempts to break r7 (hostile checks)

| # | Attack | Result |
| --- | --- | --- |
| 3.1 | "The workspace copy is still reclaimed at `expires_at` somewhere." | **Blocked.** §5.9 (`delivered`/`expired` rows), §5.10.1 (C2 row), §5.10.2, §5.14.2 step 7, §5.14.4, §5.11, §6 T-19/T-24, §8.1 I10/I12, §8.3, §9 7b/7c, §10.1/§10.2, §12 Q6/Q16/Q18 all state **C2 is never timer-deleted**. |
| 3.2 | "An agent-emitted 'read' event can still set `delivered`." | **Blocked.** §5.15.1 lists agent/tool/model-produced events as **never** authoritative; §5.15.2 requires authenticated provenance + integrity + replay protection; §5.15.3 invariant 1 + the "rejected acknowledgments" list; §5.11 forbids `attachment.read_confirmed` for non-trusted issuers; §6 T-22. |
| 3.3 | "A torn/lagging replica read can still set `delivered`." | **Blocked.** §5.15.4 requires a **quiesced** source or agent-server re-verify; §5.14.2 step 6 names the quiesced view; §10.1 adds the torn-replica check; §6 T-23. |
| 3.4 | "A relative `delivered_path` is still handed to the agent." | **Blocked.** §5.14.2 step 5 and §5.15.5 require an **absolute** path; the r6 relative wording is marked **superseded**; §10.2 adds the absolute-path test. |
| 3.5 | "The `expires_at` fallback silently becomes a success." | **Blocked.** §5.10.4/§5.14.2 step 6/§12 Q16 state the fallback is a **retention bound**, **not** a read proof, and authorizes **no** early reclaim. |
| 3.6 | "A read (F6b) is treated as end-of-use (F7)." | **Blocked.** §5.10.0 (L6 vs L7), §5.10.1 (C2 row: never on a read alone), §5.15.3 (fact mapping), §12 Q16/Q18. |
| 3.7 | "The proposal claims P0 is complete or that U-3/U-10/U-11 exist." | **No false claim.** §5.15.1/§5.15.4/§5.15.5 classify each as **NEW/UNVERIFIED**; §12 Q16/Q19/Q20/Q21 record them as owner decisions; §9 7c states `delivered` is **unreachable** today. |
| 3.8 | "A security requirement or invariant was dropped." | **No weakening.** All invariants I1–I14 present; T-18/T-19 strengthened; three threat rows added; §6 mitigations intact. |

---

## 4. State-model, lifecycle, and crash-window re-check (independent)

| Item | r7 claim | Check | Verdict |
| --- | --- | --- | --- |
| Observable states | `stored \| delivered \| rejected \| failed \| expired`; `accepted` internal-only | §5.5/§5.9 agree; examples show `stored` | **CONSISTENT** |
| `delivered` reachability | only via **U-3** (F6b) from a **trusted, non-agent** issuer, from a **quiesced** source | §5.9/§5.10/§5.14.2/§5.15.1–§5.15.4/§6/§8.1/§9/§10 all consistent | **CONSISTENT** |
| Staging reclaim authority | `delivered` (U-3) or `expires_at`; never `consumed_at` alone | §5.10.1 (C1 row) + §8.3 + §12 Q12 consistent | **CONSISTENT** |
| Workspace-copy lifetime | never timer-deleted; only F7/workspace-removal | §5.10.0–§5.10.4 + §5.14.2 step 7 + §5.14.4 + §6 T-19/T-24 + §8.1 I10/I12 consistent | **CONSISTENT** |
| Agent-facing path form | **absolute** | §5.14.2 step 5 + §5.15.5 + §5.14.4 + §5.7 + §5.9 consistent; no surviving "relative delivered_path to the agent" claim | **CONSISTENT** |
| Event-evidence source | quiesced/finalized (not the replica) | §5.15.4 + §5.14.1 + §5.14.2 step 6 + §2.2 + §7.5 + §6 T-23 consistent | **CONSISTENT** |
| Crash windows (§8.3) | 7 boundaries; no exactly-once claim | unchanged in substance; reclamation decoupled from the Telegram ack | **CONSISTENT** |
| Lifecycle crash/race (§5.10.3) | 11 cases; no copy needed for reconciliation or active use is deleted | each case states a required behaviour consistent with §5.10.1 | **CONSISTENT** |

---

## 5. What r7 does **not** claim

- It does **not** claim U-3 exists, nor that any existing primitive proves a successful content read,
  nor that a trusted non-agent issuer exists.
- It does **not** claim a quiesced evidence source (U-10) or the absolute-path producer (U-11) exist.
- It does **not** claim a durable **active-conversation** accept exists.
- It does **not** claim a **bounded** retention policy for the workspace copy exists (Q18 open).
- It does **not** claim P0 is complete; the capability still requires **upstream work + a maintainer
  decision** (§5.15, §12).

---

## 6. Unverified / limitations (honest list)

1. **U-3 is a proposal** and its issuer is **UNVERIFIED** to exist (no read-acknowledgment primitive
   found in the pinned SDK); the trust model is a **contract**, not an implemented signal.
2. **U-10** (quiesced source) and **U-11** (absolute-path producer/content identity) are **NEW upstream
   work** unless the implementation provides them.
3. **Unbounded workspace storage (Q18)** is a **disclosed, deliberate** safe default, not a closed
   item; no bounded policy is specified.
4. **Deployment parameters** — delivered-file mode/ownership (§7.4, §12 Q14) and whether a deployment
   enables a structured `read_file` tool — remain **UNVERIFIED**.
5. **Live Cloud V1** remains `1.87.1` with no upload operation (**UNVERIFIED** to have changed).
6. **No test was executed** for the upstream capability (it does not exist); existing OpenHandBot
   attachment-rejection tests are unchanged by this task.
7. **Independence:** this is a **self-review**; an independent adversarial review of r7 is still
   required (§9 criterion 10).

---

## 7. Verdict of this self-review

**The five R6 findings (R6-1…R6-5) are addressed in the r7 text**, with the lifecycle and trust rules
made **stricter** and **no** security requirement, threat-model row, or P0 invariant weakened. Three
residual uncertainties are inherent and disclosed: (a) U-3 and its trusted issuer are **proposed**
(and unverified), (b) a quiesced evidence source and the absolute-path producer are **NEW upstream
work**, and (c) the workspace-copy retention bound is an **open owner decision** with a disclosed
unbounded default. Because the r6 remediation was authored by the same agent, this document is
**self-assessment only**; **an independent adversarial review of r7 is required** before r7 is treated
as accepted.
