# OHB2-P0-SECURE-UPLOAD-PROPOSAL-R11 — HOSTILE SELF-REVIEW

**Task ID:** `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R11-N10-FINDINGS-REMEDIATION`

**Status of this document:** the **author's own hostile consistency review** of the r11 proposal
(`docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md`). It is **not** an independent
review: the N10 findings were remediated by the same agent that produced r10, so this is
**self-assessment**, not independent assurance. A **fresh independent adversarial review of r11 is still
required**. Every claim that could not be verified is marked **UNVERIFIED** or **SOURCE REQUIRED**; no
test outcome or source semantic is fabricated. **P0 is NOT implemented.**

- **Repo:** `TM-AEM/OpenHandBot` · **branch** `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW` ·
  **HEAD** `907b20de3fa6627795c14f29677e9f39c68e82f4` · **origin/main** `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c`.
- **r10 proposal SHA-256 (input):** `c19eb3cd801def4b089b3a7c6667e8218c3a6e1caa684e62f113259a94847222` (3072 lines).
- **r11 proposal SHA-256 (output):** `31dc422e1b2ebdfe2f946552fa09b178c35ed04ff2de39194b0b45596f0e20bb` (3139 lines).
- **Driving review:** `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R10-INDEPENDENT-ADVERSARIAL-REVIEW.md`
  (sha256 `14d4d8a6c621abdd8d9211b4fdf08b7df2856ec21504d46fa21cdf7d18c24415`, 235 lines), verdict
  **`PASS_WITH_NOTES`**, findings **N10-1** (LOW) + **N10-2** (LOW) + **N10-3** (INFO).
- **Scope:** documentation only. **No code, test, schema, or runtime change. P0 is NOT implemented.**
- **Method:** read the R10 review findings N10-1…N10-3 and §9 "required changes" in full; re-fetched the
  two disputed source files at the **pinned** revisions and re-hashed them; applied the r11
  corrections; then attempted to *break* r11 on the same axes (citation accuracy, source
  classification, historical/current evidence labelling) **and** on the regression axes (R6–R9 timer
  scoping, lifecycle, workspace-deletion, provenance, evidence boundaries) and cross-section consistency.

---

## 1. Evidence re-verification (this session, read-only)

Sources fetched from the **pinned revisions** already used at r2–r10
(`OpenHands/software-agent-sdk@9f7d5cb11b1256c1878f5584a657401feca9ad16`,
`OpenHands/enterprise@3fac53df8c2efcb67ff3537d1162e8c8a108f565`). **No production call, no credential,
no secret access.**

| # | Claim (finding) | Source (pinned, sha256 prefix) | Result |
| --- | --- | --- | --- |
| 1 | The file_editor **missing-path** rejection: the r10 review reported condition L689, raise L690; r10 cited L691 (§5.15.5) and L693 (§11) | `software-agent-sdk@9f7d5cb1…` `openhands-tools/openhands/tools/file_editor/editor.py` (sha256 `a1d735d4…`, 879 lines): `def validate_path` at **L657**; `if not is_host_absolute_path(path):` at **L666** (→ `raise EditorToolParameterInvalidError(` L675-679); missing-path guard `if command != "create" and not path.exists():` at **L689**; its `raise EditorToolParameterInvalidError(` at **L690** (args `"path",` L691 / `str(path),` L692 / message L693 / `)` L694) | **MATCH** — the condition is L689 and the single raise is L690 (block 689-694); r10's L691/L693 were the raise's *arguments*, not the guard/raise. r11 states the **symbol + verified range 689-694** in both places |
| 2 | `conversation_service.py` belongs to **software-agent-sdk**, not enterprise (N10-2) | `software-agent-sdk@9f7d5cb1…` `openhands-agent-server/openhands/agent_server/conversation_service.py` (sha256 `9e9b3e63…`, 3132 lines): `async def delete_conversation` at **L1863**; comment `# Safely remove only the conversation directory (workspace is preserved).` at **L1911**. `OpenHands/enterprise` has **no** `conversation_service.py` (all candidate paths 404; `openhands/` contains no `agent_server` package) | **MATCH** — the file is an SDK agent-server file; r10 mis-placed it under the enterprise bullet. r11 moves it |
| 3 | The r8-era OpenAPI value `1.87.1` (and digest `0086b0b0…ff77916`) cannot be independently verified (N10-3) | r8 proposal **not on disk**; the pinned r8 **review** (`843bb33e…`) records only "`1.87.1` / 242 paths" (no hash); the live spec this session is `1.91.0` / 244 paths / sha256 `f0f4d4e9…` | **MATCH** — the historical value must be labelled **NOT INDEPENDENTLY VERIFIED** wherever it appears; only the current re-verified value supports capability claims |

**Source-revision note:** the pinned SHAs are unchanged from r2–r10. This task **changed no technical
claim**; the only changes are citation line numbers (N10-1), one source classification (N10-2), and
evidence labelling (N10-3).

---

## 2. Remediation mapping — all three N10 findings

| # | N10 finding | r11 location(s) | r11 action | Self-assessment |
| --- | --- | --- | --- | --- |
| **N10-1** | LOW: the file_editor missing-path rejection was cited inconsistently — "(line 691)" in §5.15.5 and "(line 693)" in §11 — for the **same** fact | §5.15.5 (verified source fact), §11 (SDK bullet, read-tools entry) | Both places now cite the **symbol** (`validate_path` missing-path guard) with the **verified line range 689-694** (condition L689; `raise` L690), plus the pinned SHA `a1d735d4…`. No technical claim changed. | **RESOLVED.** The single fact is now stated once, consistently, with a stable symbol + range reference |
| **N10-2** | LOW: `conversation_service.py` (sha256 `9e9b3e63…`, line 1911) was classified under **`OpenHands/enterprise`** in §11 | §11 — removed from the **enterprise** bullet; added under the **`OpenHands/software-agent-sdk`** bullet | The citation now reads `openhands-agent-server/openhands/agent_server/conversation_service.py` (sha256 `9e9b3e63…`, 3132 lines, `delete_conversation` L1863, preserve comment L1911) under the SDK bullet; the enterprise bullet now cross-references the SDK bullet and notes the file is **not** in enterprise. **The technical claim is unchanged** (agent-server conversation delete preserves the workspace). | **RESOLVED.** Source classification corrected; claim preserved and still source-verified |
| **N10-3** | INFO: §2.2 still wrote "r8 evidence `1.87.1`" without a verification status; only the digest was labelled in §1/§2.1/§11 | §1 (header R8-4 note), §2.1 (source table), §2.2 (×3 occurrences), §11 (digest block), §13 (r11 row) | Every historical r8 occurrence is now labelled **"r8-reported … historical, NOT INDEPENDENTLY VERIFIED"** (version string **and** digest), and the **current** re-verified value (`1.91.0`, 244 paths, `f0f4d4e9…`) is clearly distinguished. The "no Cloud upload" conclusion explicitly rests on the **current** route evidence, **not** the historical value. | **RESOLVED.** Verification status is explicit at every occurrence, not merely implied by a neighbouring digest label |

**Preservation:** no security requirement, threat-model row, or P0 invariant was **weakened**. No
cleanup primitive was invented. No previously resolved finding was reopened. The changes are strictly
**citation-accuracy and evidence-labelling** corrections.

---

## 3. Regression check — prior findings not reintroduced

Re-read the full proposal after the edits and grepped for every withdrawn/remediated phrasing.

| Prior finding | Axis | r11 check | Result |
| --- | --- | --- | --- |
| **R9-1** | timer scoping | Grepped for the withdrawn absolute phrasings ("no timer deletes C2", "C2 is never timer-deleted", "only server-side clock"). The **only** survivors are inside the r10 **correction notice** that *quotes* them to explain the fix (L366-367). Normative text keeps the **operation-scoped** `expires_at` (C1/C3 only) vs the **separate** infrastructure timer (Enterprise sandbox lifecycle) distinction. | **INTACT** |
| **R9-2** | `RESERVED_TAG_KEYS` line | §11 still cites **line 86** (4 mentions); no "line 96" as the constant's location survives outside the correction notices. | **INTACT** |
| **R9-3** | container-vs-workspace deletion | The §5.10.4 four-way separation (container removal / mounted data / physical file deletion UNVERIFIED for host-mounted / external storage lifecycle) is present; `container.remove()` and the **UNVERIFIED** mount caveat are intact. | **INTACT** |
| **R9-4** | historical digest labelling | The digest `0086b0b0…ff77916` remains labelled **NOT INDEPENDENTLY VERIFIED**; now additionally the `1.87.1` **version string** is labelled too (N10-3). | **INTACT + EXTENDED** |
| **R8-1** | modeled physical-removal path (managed backends) | §5.10.1 C2 row, §5.10.4, T-24 keep the managed-backend lifecycle **modeled** / Cloud **delegated** split; the R8-1 correction (contra r8's "unmodeled") stands. | **INTACT** |
| **R8-2** | Cloud root read existing / U-12 = binding only | §5.15.6, U-12, I15, T-25 unchanged: the tag→root **read** is existing; the **identity/authorization binding** is the new part; write fails closed. | **INTACT** |
| **R8-3** | `bb9bbe23…` = enterprise `sandbox_router.py` | §11 still attributes `bb9bbe23…` to enterprise `sandbox/sandbox_router.py` and `07fef71e…` to sandbox-server; the archive module is `workspace_archive.py`. | **INTACT** |
| **R8-4** | live-spec identifier `1.91.0` | §1/§2.1/§2.2/§11 keep the current identifier `1.91.0`/244/`f0f4d4e9…`; the historical value is now explicitly demoted (N10-3). | **INTACT** |
| **R7-1…R7-4** | archive-preserve, root provenance, poll-vs-webhook replica, L↔F cross-map | §5.10.1 (archive/preserve), §5.15.4 (replica vs authoritative), §5.15.6 (provenance), §5.10.0.1 (L1–L8 ↔ F1–F7/F6a/F6b) unchanged in substance. | **INTACT** |
| **R6-1…R6-5** | C2 not reclaimed at `expires_at`, U-3 trust boundary, replica quiescence, absolute path, eight-fact model | §5.10, §5.15.1–§5.15.5, §5.14.0 unchanged in substance. | **INTACT** |

### Structural / invariant checks (post-edit)

| Check | Result |
| --- | --- |
| Invariants **I1–I15** in §8.1 | **15 rows present** |
| Threat rows **T-01…T-25** | **25 rows present**; **T-19**, **T-24**, **T-25** present and consistent with §5.10/§5.15.6 |
| §9 P0 acceptance criteria | **1–11 (incl. 7b/7c) present** |
| Requirements **U-1…U-12** | **12 rows present** |
| Per-copy lifecycle **C1–C5** | **5 rows present** |
| §12 open questions **Q1…Q22** | **22 items present** |
| Markdown triple-backtick fences | **6 (balanced)** |
| Table column consistency (escaped-pipe aware) | **0 inconsistent blocks** |
| Paragraph-level parenthesis balance | **0 issues** |
| §-cross-reference integrity | unchanged from r10 (only pre-existing bold-label refs `2.3.x`, `18.1`, `27` are outside heading-based resolution) |

---

## 4. What r11 does **not** do

- It does **not** implement the P0 workflow or any upload API.
- It does **not** change the database schema, migrations, tests, configuration, or source code.
- It does **not** change any **technical claim** — only citation line references, one source
  classification, and evidence labelling.
- It does **not** claim the proposal is independently approved; a **fresh independent review is still
  required**.
- It does **not** invent a missing historical source or digest (the unavailable r8 digest stays labelled
  unverified).
- It does **not** reopen R6/R7/R8/R9 findings.

## 5. Unverified / limitations of this self-review

1. This is **self-assessment**, not independent assurance — the same agent remediated r10 and wrote r11.
2. The **r8 proposal** remains off disk; the historical `1.87.1` value is treated as reported-only (now
   labelled).
3. No code/test was run (P0 is a proposal; no capability exists).
4. The pinned SHAs are not the current upstream `main` heads — the proposal deliberately pins revisions,
   and all checks were performed at the pinned revisions (the correct basis).

---

**Independence statement.** This self-review was written by the **author** of the r11 remediation. It is
**not** an independent review and must **not** be treated as approval. The next required step is a
**fresh independent adversarial review of r11**.
