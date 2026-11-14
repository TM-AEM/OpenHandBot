# OHB2-P0-SECURE-UPLOAD-PROPOSAL-R3 — HOSTILE SELF-REVIEW

**Task ID:** `OHB2-P0-SECURE-UPLOAD-PROPOSAL-R3-FINDINGS-REMEDIATION`

This is the **author's own hostile consistency review** of the r3 proposal
(`docs/proposals/OH-P0-SECURE-CONVERSATION-ATTACHMENT-UPLOAD-API.md`). It is **not** an independent
review: the r2 findings were remediated by the same agent that wrote r3, so this document is
**self-assessment**, not independent assurance. An independent adversarial review is still required
(§10 criterion 10 of the proposal).

- **Repo:** `TM-AEM/OpenHandBot` · **branch** `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW` ·
  **HEAD** `907b20de3fa6627795c14f29677e9f39c68e82f4` · **origin/main** `a29164ff0e5fdc34e35af39b89ff5d8cfa324c3c`.
- **Scope:** documentation only. No code/test/schema/runtime change. **P0 is NOT implemented.**
- **Method:** read the full r3 diff against r2; re-verified every finding's evidence against pinned
  public source; then attempted to *break* r3 on the axes the task lists.

---

## 1. Evidence re-verification (this session)

| Evidence | Source (pinned) | Result |
| --- | --- | --- |
| `/files` route exists only in `OpenHands/enterprise` | `enterprise@3fac53df…` `app_conversation_router.py` sha256 `c43ed4f7…` (`list_conversation_files`, line 1726) | **MATCH** |
| enterprise router is a **superset** of pinned `sandbox-server` | `sandbox-server@43e91604…` sha256 `864bff55…` | **MATCH** |
| enterprise exposes **no** upload/multipart | grep `upload`, `multipart`, `UploadFile`, `Form(` = 0 | **CONFIRMED** |
| legacy enterprise frontend upload route | `enterprise@3fac53df…` `v1-conversation-service.api.ts` sha256 `0a0b80c6…` → `/api/file/upload?path=…` | **MATCH** |
| agent-server `_upload_file` unconfined helper | `software-agent-sdk@9f7d5cb1…` `file_router.py` sha256 `13f0cae7…` | **MATCH** |
| live Cloud V1 = 242 paths, no upload | `app.all-hands.dev/openapi.json` 1.87.1 sha256 `0086b0b0…`; `multipart`=0, `binary`=0 | **MATCH** |
| Cloud file/git routes read-only | live spec: `/file`, `/files`, `/download`, `/git/changes`, `/git/diff` all `GET` | **MATCH** |
| `expires_at` was absent from the r2 status schema | r2 §5.9 (no `expires_at`) | **CONFIRMED** |

**Source-revision note:** `OpenHands/enterprise` `main` was **`3fac53df…`** at r3 time (pinned in
§2.1). The `sandbox-server`, `software-agent-sdk`, and `OpenHands` pinned SHAs are unchanged from r2.

---

## 2. Finding-by-finding self-assessment

| Finding | r3 action | Self-assessment |
| --- | --- | --- |
| **R2-1** (MEDIUM) enterprise provenance | §2.1 source row, §2.2 provenance bullet, §11 entry, header | **RESOLVED.** Names `OpenHands/enterprise` as the live-Cloud repo; explicitly "different, newer repo", not "newer build"; states no impact on the "no Cloud upload" conclusion. Evidence verified. |
| **R2-2** (MEDIUM) send-message hop | §2.2 bullet, §4 row 5 | **RESOLVED (documentation).** States Cloud `send-message` already performs the server-side hop; ImageContent *reachability* confirmed, *persistence* UNVERIFIED. |
| **R2-4** (LOW) legacy enterprise client | new §5.13 | **RESOLVED.** Which client, coexist (not replaced), out of scope, not equivalent. |
| **R2-6** (MEDIUM) observable `consumed` | new §5.9.1, §5.10, §7.5, §8.1 I12/S7, §9 7b, §10.1 | **RESOLVED (as a contract).** Owner, event, meaning, non-meaning, durability, crash rule, and interactions are all specified. **Residual: Q5** (Cloud must resolve `stored_path_ref`) and **Q12** (crash trade-off) are owner decisions, not silent assumptions. |
| **R2-8** (LOW) `expires_at` | §5.9 schema + semantics | **RESOLVED.** Present, UTC ISO-8601, fixed at accept, never extended, post-expiry terminal rule. |
| **R2-9** (LOW) `uploading` | §5.5, §5.9 | **RESOLVED.** Removed from the declared model; reachability rationale given; re-introduction gated on an owner decision (Q13). |
| **R2-7** (LOW) staging visibility | §5.7 note | **RESOLVED.** Visibility + cleanup bounded by TTL/sweep; no false confidentiality claim. |
| **R2-3, R2-5** (INFO) | — | No change required (verified correct in r2). |

---

## 3. Hostile attack attempts (task Phase 4 axes)

Each row: **attack attempted → what r3 says → residual risk / verdict.**

1. **Crash window that loses a pending batch.** Attack: crash between create-accept and staging, or
   between staging and response. r3: the operation row is durable **before** the create response
   (§5.5/§5.6); a lost response is reconciled by `operation_id`. **Verdict: closed.** Residual: the
   row must be written in a transaction that commits before the response is flushed — an
   implementation obligation, testable (§10.1 "server restart").
2. **False "consumed" or success.** Attack: report `consumed`/`stored` without durability. r3:
   `stored` is set only after the bytes are durably staged; `consumed_at` only after the message is
   durably accepted; the marker write failing **fails** the message-accept. **Verdict: closed.**
3. **Expiry race / deadline extension.** Attack: extend `expires_at` by adding files, or report a
   non-terminal state after expiry. r3: `expires_at` is fixed at accept, never moved; after
   `expires_at` no non-terminal state may be reported; adding files does not move it. **Verdict:
   closed.** Residual: the sweep must run at least once per expiry boundary; if the sweep is delayed,
   a status read must **derive** `expired` from `expires_at` rather than trusting a stale row — r3
   states the rule ("MUST NOT report non-terminal") but the **derivation-on-read** implementation is
   an obligation, flagged below (§5).
4. **Ambiguous retry that duplicates remote effects.** Attack: blind re-POST after a timeout creates
   two operations/files. r3: `Idempotency-Key` returns the same operation; `sha256` dedup within a
   window; the client must **query**, never blind-retry. **Verdict: closed at the contract level.**
   Residual: the dedup window is unspecified (Q7).
5. **State transition that cannot be observed/recovered.** Attack: a state the client cannot read or
   that cannot recover after restart. r3 declares only `accepted|stored|rejected|failed|expired`,
   all observable via the status endpoint; `consumed_at` is observable. **Verdict: closed** (this is
   exactly what R2-9 fixed).
6. **Cleanup before terminal confirmation.** Attack: sweep deletes bytes while the outcome is
   unknown. r3: the sweep reclaims **only** on a terminal state; never while `accepted`, never while
   `stored` with `consumed_at = null` before `expires_at`. **Verdict: closed.**
7. **Security requirement asserted but not specified.** Attack: find a mitigation with no mechanism.
   r3: symlink/TOCTOU (`O_NOFOLLOW` + `O_CREAT|O_EXCL`), limits, type sniff, server-generated path,
   scoped credential — all carry a mechanism and a test. **Verdict: acceptable.** Residual: exact
   numeric limits remain **PROVISIONAL** (§5.7) — correctly marked, not asserted as approved.
8. **Unsupported upstream capability claim.** Attack: find a claim of implemented capability. r3:
   the capability is repeatedly marked **not implemented**; `consumed_at` resolution is marked an
   owner decision, not an existing feature. **Verdict: closed.**

---

## 4. Remaining risks and unresolved questions (explicit)

| # | Risk / question | Why it is open | Owner decision |
| --- | --- | --- | --- |
| A | **`stored_path_ref` resolution by the Cloud** — required for `consumed_at` to exist at all | Design assumes it; not verified as implemented | §12 Q5 |
| B | **`consumed_at` crash trade-off** — a lost marker write ⇒ over-retention ≤ 15 min (never early delete) | Deliberate conservative choice | §12 Q12 |
| C | **`uploading` re-introduction** if staging is ever deferred/async | r3 assumes synchronous staging | §12 Q13 |
| D | **Expiry derivation-on-read** — status must derive `expired` from `expires_at` even if the sweep lags | Implementation obligation stated as a rule, not yet a spec detail | Implementation note (this review §3.3) |
| E | **PROVISIONAL limits** (`max_total = max_per_file = 3 MiB` ⇒ effectively one full-size file) | Not a product decision | §12 Q3 |
| F | **Idempotency dedup window** unspecified | Not a product decision | §12 Q7 |
| G | **Independent security review** of §6 not yet performed | Out of scope of this task | §12 Q10 / §9 criterion 10 |
| H | **Product decision**: implement P0 or keep fail-closed rejection | Owner decision | §12 Q11 |

**No assumption was silently chosen:** each of A–H is recorded as an open decision, not baked in.

---

## 5. Honest limitations of this self-review

- **Not independent.** Same author as r3; an independent adversarial pass is still required.
- **UNVERIFIED — enterprise deployed commit:** the exact `enterprise` revision serving the live
  Cloud is not readable from outside; R2-1 attribution rests on the public `main` router plus the
  live route/description match.
- **UNVERIFIED — `consumed_at` feasibility:** the Cloud resolving a `stored_path_ref` is an owner
  decision (risk A), not a verified capability.
- **UNVERIFIED — ImageContent persistence** (whether an embedded image is persisted as a workspace
  file) — unchanged from r2.
- **No production call, no credential, no secret access** were used.

---

## 6. Self-review verdict

**READY_WITH_EXPLICIT_OPEN_QUESTIONS** for the proposal itself (see the task's final report): the
r3 contract is internally consistent on the state machine, expiry, consumption, cleanup ordering, and
security requirements; **no security requirement was weakened**; every material correction is
source-backed or marked as a proposed contract decision; and the open items are all recorded as
owner decisions rather than hidden assumptions. **P0 is NOT implemented, and this self-review does
not claim otherwise.**
