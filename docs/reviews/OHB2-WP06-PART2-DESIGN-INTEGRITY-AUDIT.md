# OHB2 — WP-06 Part 2 — Design Specification Integrity and Evidence Audit

**Task ID:** `OHB2-WP06-PART2-DESIGN-INTEGRITY-AUDIT`
**Date:** 2026-11-19
**Baseline:** branch `openhands-workspace-40xxn2SbOi0tRICb3y8TE`, HEAD `52e7789cc8cc97a7f7c09c9592226ab117db99a2` (== `origin/main`, 0/0)
**Nature:** analysis only. No file was edited during this audit.

---

## Final verdict

# `INTEGRITY_VERIFIED_WITH_NOTES`

The specification is present, internally structured, and its **core technical claims are
independently reproducible**. The central conclusion — that `files:`/`file:` payloads are the
binding constraint and that a 12-character token fits with large margin — is **correct**.

However, the audit found **six defects**, two of which are **material** and must be corrected
before the owner treats the spec as implementation-ready:

- **D-1 (MATERIAL):** The spec's transaction-reuse precedent is **outdated and unsafe for its own
  use case**. It cites `take_awaiting`'s self-contained `BEGIN IMMEDIATE`, but WP-07 now opens
  `BEGIN IMMEDIATE` inside the very handlers `callback_refs` must instrument. Nested
  `BEGIN IMMEDIATE` **raises `OperationalError`**, which classifies as **`FAILED_PERMANENT`** — the
  exact `DEF-002` polling stall the design promises to avoid. **Empirically confirmed.**
- **D-2 (MATERIAL):** The spec's claim that unresolved tokens cannot reach OpenHands is
  **overstated**. `is_valid_conversation_id` accepts every generated token (2000/2000 measured),
  and the validation happens **inside** `authorize_conversation_detailed`, i.e. **after** the value
  is already being treated as a conversation ID. The remote call **is** made; authorization then
  fails. No action is performed — the safety property holds — but the stated mechanism does not.

Four further defects are documentation/accuracy-level (D-3 … D-6) and are itemized below.

Because the two material defects are correctable within the existing design (they do not
invalidate the approach), TASK-B may proceed. Both are carried forward as mandatory corrections.

---

## 1. Specification presence and readability

| Check | Result |
|---|---|
| File exists | **Yes** — `docs/design/OHB2-WP06-PART2-CALLBACK-REFS-DESIGN-SPEC.md` |
| Line count | **674** — matches the claimed 674 exactly |
| Sections | **15** top-level + Appendix A — matches the claim |
| Accompanying report | `docs/reviews/OHB2-WP06-PART2-CALLBACK-REFS-DESIGN-REPORT.md`, 260 lines |
| Encoding/readability | UTF-8, renders cleanly; Arabic comments intact |

**Claim 1 verified.** The complete 674-line specification is present and readable.

---

## 2. Actual sections and cross-references

Enumerated from the file (not from the report):

| § | Title | Lines |
|---|---|---|
| 1 | Problem statement and scope | 15-63 |
| 2 | Current-state findings with exact source references | 64-144 |
| 3 | Proposed data model | 145-208 |
| 4 | TTL and expiration rules | 209-272 |
| 5 | Bounded cleanup algorithm and limits | 273-322 |
| 6 | Fail-closed behavior | 323-372 |
| 7 | Ownership binding and authorization | 373-413 |
| 8 | Atomic single-use consumption | 414-462 |
| 9 | Schema and migration proposal | 463-497 |
| 10 | Compatibility analysis | 498-546 |
| 11 | Failure-mode table | 547-568 |
| 12 | Security and concurrency analysis | 569-599 |
| 13 | Test strategy and acceptance criteria | 600-630 |
| 14 | Alternatives considered | 631-645 |
| 15 | Explicit unresolved owner decisions | 646-663 |
| A | Evidence commands used | 664-674 |

All 15 sections required by the originating task are present. **Claim 2 verified.**

---

## 3. Seven owner decisions O-1 through O-7

| ID | Present | Locations |
|---|---|---|
| O-1 | **Yes** | inline §3.3 (line 187) + table §15 (652) |
| O-2 | **Yes** | inline §4.1 (219) + table §15 (653) |
| O-3 | **Yes** | inline §5.1 (287) + table §15 (654) |
| O-4 | **Yes** | inline §8.1 (422) + table §15 (655) |
| O-5 | **Yes** | table §15 (656) only |
| O-6 | **Yes** | table §15 (657) only |
| O-7 | **Yes** | table §15 (658) only |

**All seven present. Claim 3 verified.** Note: O-5, O-6, O-7 have **no inline discussion** — they
appear only in the §15 summary table. This is acceptable for O-5 (a gate), but O-6 and O-7 lack
the evidence base the owner needs; TASK-B supplies it.

---

## 4. Claim-to-source trace

| # | Design claim | Source | Observed | Accurate? |
|---|---|---|---|---|
| 4.1 | `CALLBACK_DATA_LIMIT = 64` | `keyboards.py:8` | `64` | **Yes** |
| 4.2 | `_btn()` raises on `> 64` bytes | `keyboards.py:12-17` | Raises `ValueError` | **Yes** |
| 4.3 | `MAX_CONVERSATION_ID_LEN = 64` | `files.py:29` | `64` | **Yes** |
| 4.4 | `_ID_RE = ^[A-Za-z0-9_-]{1,64}$` | `files.py:36` | Exact match | **Yes** |
| 4.5 | 17 live tables | `sqlite_master` | **17** | **Yes** |
| 4.6 | `callback_refs` absent from code | `grep bot/ tests/` | **0 matches** | **Yes** |
| 4.7 | `AWAITING_TTL = 10 min` | `db.py:255` | `timedelta(minutes=10)` | **Yes** |
| 4.8 | `ATTACHMENT_BATCH_TTL = 15 min` | `db.py:261` | `timedelta(minutes=15)` | **Yes** |
| 4.9 | `MINI_APP_SESSION_TTL = 3600s` | `config.py:292` | `_positive("MINI_APP_SESSION_TTL", 3600)` | **Yes** |
| 4.10 | `busy_timeout=5000`, WAL | `db.py:555-556` | Both present | **Yes** |
| 4.11 | `web_sessions` DDL with indexed `expires_at` | `db.py:731-739` | Exact match | **Yes** |
| 4.12 | `AWAITING_TTL` is "too short for a keyboard" | Design reasoning | Judgment, defensible | **Reasonable** |

**Claim 4 verified** for every checkable item.

---

## 5. Validity of the proposed reuse of existing mechanisms

Each of the seven named mechanisms was inspected directly.

| Mechanism | Exists | Signature/behavior as described | Safe to reuse? |
|---|---|---|---|
| `prune_processed_updates` | **Yes** (`db.py:3226` worktree / `3023` HEAD) | Watermark-bounded delete, returns count | **Yes** — correct bounded-delete model |
| `prune_web_sessions` | **Yes** (`db.py:2689` / `2565`) | `DELETE ... WHERE expires_at <= ?`, returns `rowcount` | **Yes** — closest analogue |
| `web_sessions` DDL | **Yes** (`db.py:731-739`) | `TEXT PK`, `REAL created_at/expires_at`, `idx_..._expires` | **Yes** — convention to mirror |
| `is_transient_sqlite_error` | **Yes** (`db.py:37`) | Matches `sqlite_errorcode & 0xFF` | **Yes** — single source of truth |
| `_safe_answer` | **Yes** (`handlers.py:83`) | Catches only `(TelegramError, asyncio.TimeoutError)`; no re-raise | **Yes** — correct stale-tap guard |
| `_authorized_conversation_status` | **Yes** (`handlers.py:235`) | Returns `(conv, status, msg, exc)`; tombstone-aware | **Yes** — correct dispatch-time authz |
| `acknowledgment_boundary` | **Yes** (`update_outcomes.py:93`) | Monotonic prefix scan; `None` blocks all later | **Yes** — correct eligibility model |

**Claim 5 verified:** all seven mechanisms exist and behave as the design describes.

### 5.1 Defect D-3 — line numbers are HEAD-relative, not worktree-relative

The spec cites `db.py:3023` (`prune_processed_updates`) and `db.py:2565`
(`prune_web_sessions`). Both are **correct for committed HEAD**, but the working tree has them at
**3226** and **2689** because WP-07 adds +269 lines to `db.py`.

The spec's §2 methodology states it cross-checked via `git show HEAD:`, so this is **internally
consistent** — but a reader grepping the working tree will not find them. **Correction required:**
state both coordinate systems, or cite function names only.

---

## 6. Callback payload length constraints — independent re-measurement

Driven directly against the real `_btn()` guard.

### 6.1 Minimal-digit payloads (`:0:0`)

| Payload | Spec claims safe max | **Measured** | Verdict |
|---|---|---|---|
| `deleteok:{cid}` | 55 | **55** | **Matches** |
| `unwatch:{cid}` | 56 | **56** | **Matches** |
| `status:{cid}` | 57 | **57** | **Matches** |
| `export:{cid}` | 57 | **57** | **Matches** |
| `cost:{cid}` | 59 | **59** | **Matches** |
| `files:{cid}:{gen}:{page}` | 54 | **54** | **Matches** |
| `file:{cid}:{gen}:{idx}` | 54 | **55** | **Off by one — D-4** |

### 6.2 Defect D-4 — `file:` is 55, not 54; and both are digit-width-dependent

`file:{cid}:0:0` at `cid=55` produces exactly **64 bytes**, which is **allowed** (`> 64` raises, not
`>= 64`). The spec's "54" is off by one for `file:`.

More importantly, the spec presents these as **fixed constants**. They are not — `gen` and `page`
are unbounded integers derived from runtime values (`keyboards.py:206-211`):

| Segment width | `files:` max cid | `file:` max cid |
|---|---|---|
| `:0:0` (minimal) | 54 | 55 |
| `:1:0` (typical) | 51 | 52 |
| `:1234:56789` (larger) | 47 | 48 |

**Correction required:** present these as ranges, not constants. The **design conclusion is
unaffected** — a 12-char token leaves ≥35 bytes of headroom in every measured case (§7).

---

## 7. The 12-character token and its actual fit

Executed against `secrets.token_urlsafe(9)`:

```
secrets.token_urlsafe(9) → 'M08xxGveolr5'   len = 12   (always exactly 12)
```

| Payload with 12-char token | Bytes | Cap | Fits? |
|---|---|---|---|
| `files:{t}:99:999` | 25 | 64 | **Yes** |
| `file:{t}:99:99999` | 26 | 64 | **Yes** |
| `files:{t}:999999:999999` (extreme) | 32 | 64 | **Yes** |
| `file:{t}:999999:99999999` (extreme) | 33 | 64 | **Yes** |

**Claim 7 verified.** The 12-char token fits every payload shape with ≥31 bytes of headroom even
under extreme `gen`/`page` values. The design's token sizing is sound.

Entropy: `token_urlsafe(9)` = 9 bytes = **72 bits**. At the proposed 5,000-row cap, birthday
collision probability ≈ `5000² / (2·2⁷²)` ≈ **6.6 × 10⁻¹⁴**. The spec's arithmetic is **correct**.

---

## 8. Raw-token ambiguity with `is_valid_conversation_id`

The spec (§3.4) states a bare token passes `_ID_RE`. Measured over 2,000 generated tokens:

```
2000 tokens: 2000 pass as valid conversation IDs, 0 fail
```

**The ambiguity is universal, not occasional.** Every token the design generates would be accepted
as a syntactically valid conversation ID.

### 8.1 Defect D-2 (MATERIAL) — the "cannot reach OpenHands" claim is overstated

The spec asserts (§10.6) that a missed resolver is mitigated because the token "would silently call
upstream with garbage" is prevented by resolving at one choke point. The audit tested what actually
happens if a token reaches `authorize_conversation_detailed`:

```
token passed as cid -> FileStatus.NOT_FOUND
remote calls made: [['M08xxGveolr5']]      <-- the remote call IS made
=> authorized? False
```

**What actually happens:**

1. `is_valid_conversation_id('M08xxGveolr5')` → **True** (passes).
2. Validation occurs **inside** `authorize_conversation_detailed` (`files.py:243`), i.e. **after**
   the value has already been accepted as a conversation ID.
3. `client.get_conversations([token])` **is executed** — a real upstream call with a garbage ID.
4. Upstream returns empty → `NOT_FOUND` → no action.

**Safety property holds** (no action is authorized, no data leaks). **But the stated mechanism is
wrong:** the token *does* reach OpenHands. The correct statement is "a missed resolver wastes an
upstream call and yields a not-found error; it cannot authorize an action." The implementation must
still resolve at a single choke point to avoid the wasted call, but the owner should not be told the
call cannot happen.

**Correction required** in §10.6 and §3.4.

---

## 9. Does the proposed choke point prevent unresolved tokens from reaching OpenHands?

**No — not as specified.** Three facts combine:

1. Every token passes `_ID_RE` (§8).
2. `_ID_RE` enforcement is *inside* `authorize_conversation_detailed`, after acceptance as an ID.
3. There is **no** existing "is this a token?" discriminator anywhere in the codebase
   (`grep callback_refs bot/` → 0; `grep` for any token/lookup helper → none).

Therefore the choke point must be **explicit and new**: a resolver called by each handler *before*
any authorization helper, whose return value replaces the payload segment. The spec says this, but
it presents it as belt-and-braces rather than as the **only** thing preventing a wasted (and
potentially rate-limited) upstream call. Given `_classify_failure` and upstream rate limits, this is
material.

### 9.1 Defect D-1 (MATERIAL) — the atomic-consumption precedent is unsafe here

The spec (§8.2) says consumption "mirrors `take_awaiting` (`db.py:3070-3125`)" — a self-contained
`BEGIN IMMEDIATE` … `commit`. **This is not safe in the handlers `callback_refs` must instrument.**

**Evidence — WP-07 already opens `BEGIN IMMEDIATE` inside those handlers:**

- `db.py` (worktree) `add_watched_and_record_outcome` executes `conn.execute("BEGIN IMMEDIATE")`
  (line ~1983) and is called from `watch_conversation`.
- WP-07 adds `set_awaiting_and_record_outcome`, `clear_awaiting_and_record_outcome`,
  `remove_watched`, etc., all following the same pattern.

**Nested `BEGIN IMMEDIATE` was empirically tested:**

```
outer BEGIN IMMEDIATE ok
nested BEGIN IMMEDIATE raises: OperationalError -> cannot start a transaction within a transaction
```

**And its classification was tested:**

```
is_transient_sqlite_error(nested error) -> False
=> classifies as FAILED_PERMANENT (no retry) -> DEF-002 polling stall
```

This is precisely the failure mode the design exists to prevent. If a handler resolves/consumes a
token with its own `BEGIN IMMEDIATE` and then calls `add_watched_and_record_outcome` (or vice
versa), the second `BEGIN` raises, `_classify_failure` returns `FAILED_PERMANENT`, and polling
stalls.

**Additional corroboration:** the project has **already moved away** from `take_awaiting`'s
self-contained transaction. `db.py:2880-2900` documents `awaiting_state` as the replacement:
"read without consuming… consumption became separate and atomic with the durable record write."
The spec cites the *superseded* pattern as its model.

**Correction required:** the consumption contract must be **transaction-composing**, not
self-opening. Options for TASK-B:
- **(a)** Resolve+consume in a read-only step, then record consumption inside the caller's existing
  transaction (`commit=False` helper, matching `_set_last_state_nocommit` precedent).
- **(b)** A `nocommit` variant guarded by `conn.in_transaction`.
- **(c)** Explicitly forbid calling the resolver inside any transaction and document the ordering.

This is the single most important correction in this audit.

---

## 10. Contradictions, missing edge cases, unsupported assumptions

### 10.1 Defect D-5 — handler count

Spec §2.2 states "**15 handlers** extract a `conversation_id`" and lists 15 rows, of which two
(`list_conversations`, `list_watches`) are explicitly page-only. Independent count:

- Handlers parsing `q.data`: **18**
- Handlers actually carrying a `conversation_id`: **14**
- Page/gen-only: **4** (`list_conversations`, `list_watches`, `repos_page`, `pick_repo`)

The spec's table includes 2 non-cid handlers while claiming they are cid-bearing, and **omits
`repos_page` and `pick_repo`** from the non-cid list. The count "15" is wrong in both directions.
**Correction required:** 14 cid-bearing handlers.

### 10.2 Defect D-6 — `OpportunisticSweeper` is not generic

Spec §5.1 offers the existing `OpportunisticSweeper` as a cleanup hook. Inspection of
`attachments.py:1437-1482` shows it is **hard-typed**:

```python
def __init__(self, reaper: AttachmentReaper, *, min_interval=..., clock=None)
```

It holds an `AttachmentReaper` and calls `reaper.sweep()`. Reusing it for `callback_refs` would
require modifying `attachments.py` — a file outside WP-06's scope and one WP-07 also touches.
**Correction required:** state that the sweeper route needs a new adapter (scope expansion), or
drop it in favour of boot-hook + insert-path cap (the spec's own recommendation).

### 10.3 Genuine gaps the spec handles correctly

For completeness — these were checked and are **not** defects:

- Expiration boundary (`now == expires_at` → expired) is explicit and conservative. ✔
- Clock-jump handling (both timestamps from one `time.time()`) is sound. ✔
- Single-use vs. exactly-once distinction is explicitly disclaimed (§8.4, §12.3). ✔
- Cross-scope replay via `action_scope` is addressed. ✔
- BUSY/LOCKED tolerance for pruning (non-fatal) is correct. ✔

### 10.4 Unsupported assumption

The spec assumes boot-hook cleanup alone bounds growth. It adds an insert-path cap as "defence in
depth," which does close the gap — but §5.1's claim that boot-only is "sufficient for correctness"
depends entirely on that insert-path cap, which is listed under O-3 as optional. If the owner
selects "boot hook only" **without** the insert-path cap, a long-lived process grows unbounded.
**TASK-B must make the insert-path cap non-optional.**

---

## 11. Required corrections summary

| ID | Severity | Correction |
|---|---|---|
| **D-1** | **MATERIAL** | Replace the `take_awaiting` self-contained-`BEGIN` precedent with a transaction-composing consumption contract; explicitly forbid nested `BEGIN IMMEDIATE`; document the `FAILED_PERMANENT`/`DEF-002` consequence. |
| **D-2** | **MATERIAL** | Reword §3.4/§10.6: an unresolved token **does** reach the upstream API; safety holds because no action is authorized. |
| **D-3** | LOW | Cite function names, or state both HEAD and worktree line numbers. |
| **D-4** | LOW | `file:` safe max is 55, not 54; payload limits are digit-width-dependent ranges, not constants. |
| **D-5** | LOW | 14 cid-bearing handlers, not 15; `repos_page`/`pick_repo` are page/gen-only. |
| **D-6** | MEDIUM | `OpportunisticSweeper` is hard-typed to `AttachmentReaper`; reuse requires modifying out-of-scope `attachments.py`. |

---

## 12. Can TASK-B proceed?

**Yes.** Both material defects (D-1, D-2) are correctable **within the proposed design** — they
concern the consumption contract and the wording of a risk claim, not the fundamental approach
(persistent short-token table with TTL, bounded cleanup, ownership binding, single-use).

The design's central technical premise — **that 64-byte overflow is real, that `files:`/`file:` are
the binding constraint, and that a 12-char token resolves it with margin** — is **independently
confirmed**. Nothing found invalidates the architecture.

TASK-B proceeds with D-1 and D-2 as **mandatory conditions** on any recommendation.

---

## Appendix — Commands executed during this audit

```
git rev-parse HEAD                          → 52e7789cc8cc97a7f7c09c9592226ab117db99a2
wc -l design spec                           → 674
grep "^## " spec                            → 15 sections + Appendix A
grep "O-[1-7]" spec                         → all 7 present (inline + §15)
_btn() overflow sweep (minimal digits)      → deleteok 55, unwatch 56, status 57,
                                              export 57, cost 59, files 54, file 55
_btn() sweep (large digits)                 → files 47, file 48
secrets.token_urlsafe(9)                    → always 12 chars
12-char token payloads                      → 25-33 bytes (cap 64)
is_valid_conversation_id(token) x2000       → 2000/2000 pass
authorize_conversation_detailed(token)      → NOT_FOUND, remote call MADE
nested BEGIN IMMEDIATE                      → OperationalError
is_transient_sqlite_error(nested)           → False → FAILED_PERMANENT
git diff handlers.py function hunks         → 17 functions; 4 overlap cid handlers
sqlite_master table count                   → 17
```
