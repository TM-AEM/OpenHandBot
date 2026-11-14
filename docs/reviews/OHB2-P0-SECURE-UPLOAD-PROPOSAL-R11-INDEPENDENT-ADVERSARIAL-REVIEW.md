# OHB2-P0-SECURE-UPLOAD-PROPOSAL-R11 — INDEPENDENT ADVERSARIAL REVIEW

**Task ID:** `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R11-INDEPENDENT-ADVERSARIAL-REVIEW`

Reviewer: fresh-context independent adversarial reviewer; **not** the author of the r11 proposal,
**not** the author of the r11 self-review, and **not** the author of any earlier (r2–r10) review or
self-review. The R11 completion report and the R11 self-review were treated as **claims to be
verified**, never as evidence. All actions were **read-only**: upstream public source and the live
spec were re-fetched independently this session and re-hashed; **no production call, no credential,
no secret access, no modification** of the proposal, the self-review, `PROGRESS.md`, memory, source
code, tests, or any previous review. This review file is the **only** artifact created. No
commit/push/PR/merge/deploy, no branch change, no upstream issue/PR/maintainer contact. **P0 remains
unimplemented.**

## Verdict: **PASS_WITH_NOTES**

r11 **fully and correctly remediates** the three R10 findings (N10-1, N10-2, N10-3) — I re-derived
each disputed fact from the pinned source and the live spec (§3) and every r11 correction **matches
ground truth**. No security requirement, threat-model mitigation, or P0 invariant was weakened, and
every prior finding (R6-1…R6-5, R7-1…R7-4, R8-1…R8-4, R9-1…R9-4) remains remediated (§5).

I did **not** reach `PASS` because I found **three residual citation-precision notes** (N11-1, N11-2,
N11-3) of the **same class** that N10-1 and N10-2 were raised for — a statement cited at the line of
its enclosing symbol instead of the statement, one off-by-three line citation, and one file
attributed with a decorator that lives in a different file. All three are **documentation-only**,
none affects any security conclusion, and all three **pre-date r11** (they are in r8/r9 material that
the R10 review did not flag). They are **non-blocking** for owner approval and should be folded into
the next revision.

---

## 1. Baseline and file hashes

Repo `TM-AEM/OpenHandBot`; branch `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW`; `HEAD`
`907b20de3fa6627795c14f29677e9f39c68e82f4`; `origin/main` `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c`
(unchanged; no commit, no push, no upstream tracking). Working tree: pre-existing modifications
(`.agent/PROGRESS.md`, `bot/handlers.py`, two other `docs/proposals/*.md`) plus untracked r-series
proposal/review files — **all left exactly as found**; this review added exactly one file.

| Artifact | Lines | sha256 (independently recomputed this session) |
| --- | --- | --- |
| `docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md` (r11) | 3139 | `31dc422e1b2ebdfe2f946552fa09b178c35ed04ff2de39194b0b45596f0e20bb` |
| `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R11-SELF-REVIEW.md` | 120 | `c00dd1f486ef400b42999779fdae47c1cf3ce432ad2a551e1ee237f8bdfd47f6` |
| `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R10-INDEPENDENT-ADVERSARIAL-REVIEW.md` (driving review) | 235 | `14d4d8a6c621abdd8d9211b4fdf08b7df2856ec21504d46fa21cdf7d18c24415` |
| `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R10-SELF-REVIEW.md` | 169 | `47e643aa213ed9a5831b7dace850aa73f1eb180a08cd5549c52a157b2dbf879c` |
| `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R9-INDEPENDENT-ADVERSARIAL-REVIEW.md` | 280 | `62c074d467d8665efe9841f93411abdd0cc2194cc1b0cde041565b349ac46a02` |
| `docs/reviews/OHB2-P0-SECURE-UPLOAD-PROPOSAL-R8-INDEPENDENT-ADVERSARIAL-REVIEW.md` | 346 | `843bb33e8b0011acdf6c2cc83a25587ab6fae0a84f788b949b707d44f94b2ed8` |

All five reported artifact hashes **match** the values the r11 self-review and the completion report
state. Structural sanity (independently recomputed): 6 triple-backtick fences (balanced); **0** real
markdown table column mismatches (escaped-pipe aware); paragraph-level parenthesis balance **0**
issues; §8.1 invariants **I1–I15** = 15 rows; §6 threat rows **T-01…T-25** = 25; §5.15 requirements
**U-1…U-12** = 12; §5.10.1 copies **C1–C5** = 5; §12 questions **Q1…Q22** = 22; §9 criteria
1–11 (incl. 7b/7c) present.

## 2. Method

1. Read the R10 independent review (verdict `PASS_WITH_NOTES`, findings N10-1…N10-3) and its §9
   "recommended changes" in full; read the r11 self-review in full; read the r8/r9 review lineage
   (R8-1…R8-4, R9-1…R9-4) for the regression axes.
2. Read the **entire** r11 proposal (3139 lines) section by section: header + r10/r11 correction
   notices, §1–§4, §5.1–§5.16 (incl. §5.9/§5.9.1, §5.10/§5.10.0–§5.10.5, §5.14/§5.14.0–§5.14.4,
   §5.15/§5.15.1–§5.15.6), §6 (T-01…T-25), §7.0–§7.8, §8.1–§8.4, §9, §10.1–§10.2, §11, §12
   (Q1…Q22), §13.
3. Independently re-fetched and re-hashed **every** source the r11 changes and the driving findings
   rest on, from the **pinned** revisions and the live spec (§3), and re-derived the specific line
   numbers cited — **not** trusting the self-review's own table.
4. Attempted to **break** r11 on the axes N10-1…N10-3 address (citation accuracy, source
   classification, historical/current labelling) **and** on the regression axes (timer scoping,
   lifecycle, workspace-deletion, provenance, evidence boundaries) plus cross-section consistency,
   grepping exhaustively for every withdrawn absolute phrasing.

## 3. Independent verification of the r11 remediation

Pinned revisions (re-fetched this session, HTTP 200): `OpenHands/software-agent-sdk@9f7d5cb1…`,
`OpenHands/enterprise@3fac53df…`, `OpenHands/sandbox-server@43e91604…`, `OpenHands/OpenHands@a8aaf681…`.

| # | r11 claim (finding) | Independent source (pinned, sha256 prefix) | Result |
| --- | --- | --- | --- |
| 1 | The `editor.py` missing-path guard is the **condition at line 689**, its single `raise` at **line 690**; the cited range **689-694** is stated in **both** §5.15.5 and §11 (N10-1) | `…/tools/file_editor/editor.py` `a1d735d4…` (879 L): `def validate_path` L657; `if not is_host_absolute_path(path):` L666; guard `if command != "create" and not path.exists():` **L689**; `raise EditorToolParameterInvalidError(` **L690**; args `"path",` L691 / `str(path),` L692 / message L693 / `)` L694 | **MATCH** — both §5.15.5 (L2020-2022) and §11 (L2780-2781) now cite **689** and **689-694**; no residual "line 691"/"line 693" outside the two explicit correction notices |
| 2 | `conversation_service.py` is an **SDK** agent-server file, not enterprise; moved to the SDK bullet (N10-2) | `…/agent_server/conversation_service.py` `9e9b3e63…` (3132 L): `async def delete_conversation` L1863; `# Safely remove only the conversation directory (workspace is preserved).` L1911; `safe_rmtree(` L1914. `OpenHands/enterprise` path `…/openhands/agent_server/conversation_service.py` ⇒ **HTTP 404** | **MATCH** — the citation now sits under the `OpenHands/software-agent-sdk` bullet (L2786-2791); the enterprise bullet (L2847-2849) cross-references it and states the file is **not** in enterprise |
| 3 | Every historical `1.87.1` occurrence is labelled **r8-reported … historical, NOT INDEPENDENTLY VERIFIED** and distinguished from the current `1.91.0` (N10-3) | live `openapi.json` this session: `info.version = 1.91.0`, **244** paths, sha256 `f0f4d4e9…`; `multipart` = 0, `format: binary` = 0, no `attach`/`upload` path. r8 proposal **not on disk**; the pinned r8 review (`843bb33e…`) records only "`1.87.1` / 242 paths" (no hash) | **MATCH** — header R8-4 note (L348-350), §2.1 (L564), §2.2 (L582, L587-588, L655-656), §11 (L2715-2720) all carry the qualifier; no unqualified historical value remains |

### 3.1 Regression axes (independently re-derived — no weakening)

| Axis | r11 state | Independent check | Verdict |
| --- | --- | --- | --- |
| **R9-1** timer scoping | operation `expires_at` reclaims **C1/C3 only**; a **separate** infrastructure timer (Enterprise sandbox lifecycle) may remove sandbox+workspace; the two are distinct | grepped `no timer deletes C2`, `C2 is never timer`, `only server-side clock`, `timer-deleted`, `timer-reclaimed`: the **only** survivors are the two **correction notices** (L366-367) that *quote* the withdrawn wording | **INTACT** |
| **R9-2** `RESERVED_TAG_KEYS` line | §11 cites **line 86** | `app_conversation_models.py` `7a4a54c0…`: `RESERVED_TAG_KEYS = frozenset(` **L86**; `def _validate_caller_tags(...)` L96 | **INTACT** |
| **R9-3** container-vs-workspace deletion | four-way separation (container removal / mounted data / physical file deletion UNVERIFIED for host-mounted / external storage lifecycle) | `docker_sandbox_service.py` `00953ee1…`: `container.remove()` **L698**; `mounts: list[VolumeMount] = Field(default_factory=list)` **L741** (empty default); `VolumeMount{host_path,container_path}` L103-107. `docker_sandbox_spec_service.py` `5401c0b7…`: `working_dir='/workspace/project'` L98, `OH_CONVERSATIONS_PATH='/workspace/conversations'` L92 | **INTACT** |
| **R8-1** modeled removal path (managed backends) | Enterprise lifecycle models sandbox+workspace delete for managed backends; Cloud delegated to runtime-api | `lifecycle/settings.py` `1cdd88d5…` L25-31 `delete_after_seconds` default 10 days, description "Delete a sandbox, and its workspace, once it has not run for this long."; `lifecycle/tasks.py` `834e9452…` L78 `@lifecycle.periodic(cron='* * * * *')`, L182 `sandbox_service.delete_sandbox(sandbox_id)`; `lifecycle/rules.py` `0f0df7a9…` L107-108 `Action.DELETE`/`Reason.INACTIVE`; `lifecycle/__init__.py` `446effa0…` scope "Docker, E2B and k8s … runtime-api manages the remote backend's sandboxes itself"; `worker/app.py` `a287ec5a…` L33 `namespace='sandbox_lifecycle'` | **INTACT** |
| **R8-2** root read existing / U-12 = binding only | tag→root read ships; identity/authorization binding is new; write fails closed | `app_conversation_models.py` `7a4a54c0…` L250-264 `@computed_field repositories` → `conversation_repositories(..., self.tags.get(ARCHIVE_WORKSPACE_PATH_TAG_KEY))`; `ARCHIVE_WORKSPACE_PATH_TAG_KEY = 'archiveworkspacepath'` L65; `additional_repositories.py` `a8d0bbe3…` L106 `path=f'{working_dir}/{folder}'`; live `AppConversation.repositories` → `ConversationRepository.path` = "Absolute path of the folder in the sandbox" | **INTACT** |
| **R8-3** citation corrections | `bb9bbe23…` = enterprise `sandbox_router.py`; sandbox-server `07fef71e…`; archive module `workspace_archive.py` | enterprise `sandbox/sandbox_router.py` = `bb9bbe23…` (L302 "delete_sandbox is sandbox-scoped (stop + delete) and never archives"); sandbox-server `sandbox_router.py` = `07fef71e…`; enterprise `sandbox/workspace_archive.py` = `202fc8e1…` (`archive_workspace` L334; `store.write` L516) | **INTACT** |
| **R8-4** live-spec identifier | current `1.91.0` / 244 / `f0f4d4e9…` | live spec re-verified this session: `1.91.0`, 244 paths, `f0f4d4e9…` | **INTACT** |
| **R7-1…R7-4** archive-preserve / root provenance / poll-vs-webhook / L↔F cross-map | unchanged in substance | `app_conversation_router.py` `c43ed4f7…` L1050 `_finalize_sandbox_delete`, L1071 `archive_conversation_workspace(...)`, L1090-1091 `count_conversations_by_sandbox_id(...) == 0` ⇒ `delete_sandbox`; `remote_sandbox_service.py` `d239ec43…` L1256 `poll_agent_servers`, L1345 `refresh_conversation`, L1438 `save_event`, L1518-1519 `web_url is None or 'localhost' in web_url`; `settings_models.py` `27bae62a…` L753-767 `grouped_workspace_dir` | **INTACT** |
| **R6-1…R6-5** C2-not-at-`expires_at` / U-3 trust / quiescence / absolute path / eight-fact model | unchanged in substance | §5.10/§5.15.1–§5.15.5/§5.14.0 read in full; consistent | **INTACT** |

**Source-backed insufficiency claims re-checked (N-1 lineage).** `Observation.is_error` defaults
`False` (`sdk/tool/schema.py` `76b4f42a…`, L400/L417); the terminal `_handle_completed_command`
returns `TerminalObservation.from_text(..., exit_code=metadata.exit_code)` **without** `is_error`
(`terminal_session.py` `72504a4d…`, L342-346 etc.), and the `is_error=True` sites are exactly
interaction/empty-input/"cannot execute multiple commands"/no-previous-command/closed-terminal
(L506/520/526/542/608/670) ⇒ **a failed terminal read is a non-error observation** — the r6
counterexample stands. `file_editor/impl.py` `35353ad3…` maps `ToolError` → `is_error=True`
(L68-70); `file_editor/utils/constants.py` `a5b3f2bf…` L1 `MAX_RESPONSE_LEN_CHAR = 16000`.
`Message.content: Sequence[TextContent | ImageContent]` (`llm/message.py` `1b9f0693…`, L226) ⇒ no
generic file block. `DEFAULT_EXEC_TOOL_NAMES = ("terminal","file_editor","task_tracker")`
(`sdk/tool/defaults.py` `357f005b…`, L26-30). **All match.**

## 4. Adversarial findings (new)

### N11-1 (LOW) — a statement is cited at the line of its enclosing function (`additional_repositories.py`)

The proposal writes, in three places, that `conversation_repositories(...)` "build[s] `path =
f'{working_dir}/{folder}'`" and cites **line 89** for it:

- §5.15.6 / §11: "`conversation_repositories(...)` (`app_conversation/additional_repositories.py`,
  sha256 `a8d0bbe3…`, **line 89**) to build `path = f'{working_dir}/{folder}'`" (L2069, L2876); and
  the r9 note at L332.

Ground truth (`additional_repositories.py` `a8d0bbe3…`, 453 L): **line 89** is
`def conversation_repositories(` — the **function definition**. The statement that builds the path
is **line 106**: `path=f'{working_dir}/{folder}' if working_dir else None,`. (Notably, the **R10
review itself** cited this fact at **L106**, at its §3 row 7 — so the proposal is *less* precise than
its own driving review here.)

This is the **same class** as N10-1: a line that points at the enclosing symbol rather than the
statement. It is defensible ("the function at L89 builds…") but inconsistent with the document's own
statement-level citation style.

*Suggested fix:* cite **line 106** (or "L89 (def) → L106") for the `path = {working_dir}/{folder}`
statement.

### N11-2 (LOW) — off-by-three line citation for the `archiveworkspacepath` tag read (§11)

§11 (L2842-2843) states the conversation-delete route schedules the finalizer detached "with
`workspace_path` = the `archiveworkspacepath` tag (**line 1185**)".

Ground truth (`enterprise` `app_conversation_router.py` `c43ed4f7…`, 2209 L): **line 1185** is the
comment `# Delete the sandbox in the background if no other conversations reference it`; the
statement is at **line 1188**: `workspace_path = app_conversation_info.tags.get(ARCHIVE_WORKSPACE_PATH_TAG_KEY)`.
(The adjacent `asyncio.create_task` **line 1189** citation is correct.)

Same class as N10-1 (a single fact cited at a neighbouring line). No security impact.

*Suggested fix:* change "line 1185" → "line 1188" in §11.

### N11-3 (INFO) — the periodic cron is attributed to `sweep.py`, but it lives in `tasks.py` (§11)

§11 (L2890) writes "`sweep.py` cron `* * * * *`". The **only** cron decorator in the lifecycle
subsystem is in **`tasks.py`** (`834e9452…`, L78: `@lifecycle.periodic(cron='* * * * *')`, on the
`sweep` job at L82). `sweep.py` (`1d99bd1c…`, 57 L) contains **no** `cron` token at all (it holds
`find_due_sandbox_ids` and the `LAST_RAN_AT = func.greatest(...)` helper, L24-28). This is the **same
class** as N10-2 (a decorator/symbol attributed to the wrong file). The §5.10.4 phrasing "a periodic
`sweep` (cron `* * * * *`)" (L1419-1420) is fine — it names the **job**, not a file — so the defect is
localised to the §11 file→cron attribution.

*Suggested fix (optional):* in §11 write "`tasks.py` `@lifecycle.periodic(cron='* * * * *')` (the
`sweep` job; candidate selection in `sweep.py`)".

## 5. Substantive re-check (no weakening found)

| Item | r11 position | Independent check | Verdict |
| --- | --- | --- | --- |
| Observable states | `stored \| delivered \| rejected \| failed \| expired`; `accepted` internal-only; no `uploading` | §5.5 (L950-989) and §5.9 (L1104-1123) agree; grepped every JSON example: **no** example returns `accepted`/`uploading` | **CONSISTENT** |
| Operation timer | `expires_at` reclaims **C1/C3 only**; never C2 | §5.9 + §5.10.1 + §5.10.2 + §5.10.3 case 4 + §5.14.2 step 7 + §8.4 + T-19/T-24 + I12 + Q18 agree | **CONSISTENT** |
| Infrastructure timer | Enterprise sandbox lifecycle **may** remove sandbox+workspace; delegated for Cloud; not an F7 signal | §5.10.1 + §5.10.4 + §5.14.2 step 7 + T-24 + §11(f) + §13 agree; explicitly **distinct** from `expires_at` | **CONSISTENT** |
| C2 lifetime | never reclaimed by `expires_at` or conversation archive/delete; only F7 (unmodeled) or physical removal | §5.10.0.1 + §5.10.1 + §5.10.4 + §5.14.2 step 7 + §5.14.4 + T-19/T-24 + I12 + §9 7b + Q18 | **CONSISTENT** |
| Teardown mechanism | verified = **container removal**; underlying workspace deletion **UNVERIFIED** for host-mounted | §5.10.1 C2 row + §5.10.4 + §11(f) agree | **CONSISTENT** |
| Root provenance | tag→root read existing/shipped; **identity + write-authorization binding** new; fail closed | §5.14.2 step 3 + §5.15.5 + §5.15.6 + U-12 + T-25 + I15 + Q22 | **CONSISTENT** |
| Live-spec identifier | `1.91.0`, 244, `f0f4d4e9…` | §1 + §2.1 + §11 agree; re-verified live; historical `1.87.1` labelled | **CONSISTENT** |
| Threat table | T-01…T-25 present; T-19/T-24/T-25 scoped | §6 rows match §5.10/§5.15.6 | **CONSISTENT** |
| Crash windows (§8.3) / races (§5.10.3) | no copy needed for reconciliation or active use is deleted | §5.10.3 cases 1–11 internally consistent; §8.3 windows 1–7 consistent | **CONSISTENT** |
| L↔F cross-map (§5.10.0.1) | L6↔F6b, L7↔F7 only; others "none" | table matches §5.10.0/§5.14.0 | **CONSISTENT** |
| §9 acceptance criteria | 1–11 (incl. 7b/7c) unchanged in substance | read in full; no criterion relaxed | **CONSISTENT** |

**Exhaustive absolute-phrasing scan.** I grepped the full text for `no timer deletes C2`, `C2 is
never timer`, `only server-side clock`, `only clock that exists server-side`, `timer-deleted`,
`timer-reclaimed`, `never timer-deleted`, and every `timer` occurrence. The **only** surviving
absolute phrasings are inside the two **explicit correction notices** (L366-367) that *quote* the
withdrawn wording to explain the fix, and the §13 revision-history rows that quote it for the same
purpose. No unscoped absolute claim remains in the normative text.

**Self-review claim check.** The r11 self-review's §2 remediation table and §3 regression table were
verified against the proposal text: every touch-point it lists (N10-1 → §5.15.5/§11; N10-2 → §11;
N10-3 → §1 header/§2.1/§2.2 ×3/§11) is present and labelled as claimed, and its structural counts
(I1–I15, T-01–T-25, U-1–U-12, C1–C5, Q1–Q22, fences, table columns, paren balance) all **match** my
independent recomputation. The self-review's honesty about being **non-independent** is accurate.

## 6. What r11 does **not** claim (fairness note)

- It does **not** claim P0 is implemented; the capability still requires upstream work + a maintainer
  decision.
- It does **not** claim U-3 exists, nor that a trusted non-agent issuer exists.
- It does **not** claim the Cloud/runtime-api sandbox-lifecycle bound is known (delegated/external).
- It does **not** claim `container.remove()` establishes universal physical deletion of the
  underlying workspace data.
- It does **not** claim a bounded C2 retention policy exists for the Cloud path (Q18 open).
- It does **not** claim the historical r8 digest `0086b0b0…` is verified, nor that any historical
  value supports a current capability claim.
- It does **not** claim this self-review (or this review) is owner approval.

## 7. Unverified / limitations of this review (honest list)

1. The **r10 proposal** is **not on disk** (the file at that path is now r11); the "no weakening
   versus r10" property was assessed from the r11 text + the R10 review's verbatim quotes, **not**
   from a byte diff of r10. The **r8 proposal** is likewise off disk.
2. The **r8-spec digest** `0086b0b0…ff77916` could not be independently confirmed (correctly labelled
   unverified in the proposal).
3. I did **not** run any code or test (P0 is a proposal; no capability exists). No claim here rests on
   an executed test.
4. Whether the modeled teardown removes the **workspace directory** (vs only the container) remains
   **unverified** for host-mounted layouts — the proposal states this correctly.
5. I did not contact any maintainer and made no production call. The live spec was fetched read-only.
6. The pinned `software-agent-sdk` / `enterprise` / `OpenHands` SHAs are **not** the current upstream
   `main` heads (they have moved since; e.g. SDK `main` = `10be259c…`, enterprise `main` =
   `50b1916d…` at review time). This is **expected** — the proposal deliberately pins revisions; I
   re-verified every claim at the **pinned** revisions, which is the correct basis. (The proposal's
   "== current `main`" annotations are stale but explicitly dated "at r2 time", §11.)
7. This review covers **r11 only**; it does not re-adjudicate the closed r6/r7 findings except where
   r11 touches them.
8. §-reference integrity: heading-based resolution flags `2.3.1/2.3.2/2.3.4/2.3.5` — these are
   **bold-label** subsections (not `###` headings), so they resolve; `18.1` and `27` are cross-document
   references (the ack ADR and the predecessor proposal). No real broken internal reference found.

## 8. Verdict and required changes

**Verdict: `PASS_WITH_NOTES`.**

The three R10 findings are **independently confirmed remediated** in the r11 text — the `editor.py`
missing-path citation is now stable and consistent (689 / 689-694 in both places), the
`conversation_service.py` citation is re-attributed to `OpenHands/software-agent-sdk` (and the
enterprise bullet states the file is absent there), and the historical `1.87.1` value is labelled
**NOT INDEPENDENTLY VERIFIED** at every occurrence while the current `1.91.0` / 244 / `f0f4d4e9…` is
distinguished — **without weakening any security requirement, threat-model mitigation, or P0
invariant** (fail-closed rules preserved; no cleanup primitive invented; R6-1…R9-4 remain closed).

Recommended (documentation-only, **non-blocking**, for the next revision):

1. **N11-1 (LOW):** in §5.15.6/§11 (and the r9 note), cite the `path = f'{working_dir}/{folder}'`
   statement at **line 106** of `additional_repositories.py` (line 89 is the function definition).
2. **N11-2 (LOW):** in §11, change the `archiveworkspacepath` tag-read citation from "line 1185" to
   **line 1188**.
3. **N11-3 (INFO, optional):** in §11, attribute the `cron='* * * * *'` decorator to **`tasks.py`**
   (the `sweep` job), noting candidate selection lives in `sweep.py`.

If items 1–2 are folded in, the document is ready to move to `PASS` for the citation axis. The
residual **substantive** uncertainties (U-3/issuer, U-10, U-11, U-12-binding, C2 retention bound,
Cloud/runtime-api teardown) remain honestly open and are **owner decisions**, not review defects.

---

**Independence statement.** This review was authored by a fresh-context reviewer that is not the
author of the r11 proposal, the r11 self-review, or any earlier review/self-review in this series.
All artifacts were read-only; the only file created is this one. No secrets, credentials, or
production calls were used.

*This review was produced by an AI agent (OpenHands) on behalf of the repository owner.*
