# OHB2 — WP-06 Part 2 — `callback_refs` Design Report

**Task ID:** `OHB2-WP06-PART2-CALLBACK-REFS-DESIGN-SPECIFICATION`
**Date:** 2026-11-19
**Nature:** design-only. **No implementation, migration, or test change was made.**

---

## Final verdict

# `DESIGN_READY_FOR_OWNER_REVIEW`

A concrete, implementable design is complete and covers every requirement the baseline
prerequisite (`OHB2-CORRECTED-REMEDIATION-BASELINE.md`, `§WP-06` item 3) demands: TTL/expiration,
bounded cleanup, fail-closed handling, ownership/scope binding, and atomic single-use consumption.

**Seven owner decisions (O-1 … O-7) remain open** and are enumerated in §15 of the spec. They are
parameter choices and one hard gate (schema approval), not unresolved design gaps — the design
proceeds under stated recommendations and requires approval before coding.

---

## 1. Actual Git baseline

| Field | Value |
|---|---|
| Branch | `openhands-workspace-40xxn2SbOi0tRICb3y8TE` |
| HEAD | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| `origin/main` | `52e7789cc8cc97a7f7c09c9592226ab117db99a2` |
| ahead / behind | `0 / 0` |
| Staged | 0 |
| Modified (pre-existing) | 6 |
| Untracked (pre-existing) | 13 |

**Pre-existing modifications (WP-07 and prior tasks) — untouched:**

```
 M .agent/PROGRESS.md
 M bot/db.py
 M bot/handlers.py
 M bot/watcher.py
 M tests/test_handlers.py
 M tests/test_sw06_unwatch_db_failure_propagation.py
```

**Pre-existing untracked (13)** — prior reports, WP-07 tests, WP-05 acceptance record,
`tests/test_f03_watch_conversation_status_normalization.py`. None modified.

### Committed vs working-tree distinction (applied throughout)

| File | State used for findings |
|---|---|
| `bot/keyboards.py` | **Committed, clean** — read from working tree |
| `bot/messages.py`, `bot/files.py` | **Committed, clean** |
| `bot/app.py`, `bot/update_outcomes.py` | **Committed, clean** |
| `bot/db.py` | **WP-07-dirty** — cross-checked via `git show HEAD:bot/db.py` |
| `bot/handlers.py` | **WP-07-dirty** — cross-checked via `git show HEAD:bot/handlers.py` |

All schema, migration, and cleanup-hook findings were read from `git show HEAD:` because
`bot/db.py` carries uncommitted WP-07 work. All callback-parsing findings were read from the
working tree and line numbers are stated as working-tree line numbers.

---

## 2. Files inspected

**Governance / baseline**
- `AGENTS.md`
- `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md` — `§WP-06` (lines 663-672, design prerequisite)
- `docs/audits/OHB2-CORRECTED-REMEDIATION-BASELINE.md` — `DEF-010` full definition
- `docs/audits/OHB2-REMEDIATION-MASTER-PLAN.md:159,164` (prior `callback_refs` mentions)
- `docs/audits/OHB2-COMPLETE-DEFECT-REGISTER.md:311`
- `docs/audits/OHB2-INDEPENDENT-AUDIT-REPORT-VALIDATION.md:136,168`

**Source**
- `bot/keyboards.py` (1-40, 138-215) — `CALLBACK_DATA_LIMIT`, `_btn()`, all builders
- `bot/files.py` (29, 36, 72) — `MAX_CONVERSATION_ID_LEN`, `_ID_RE`, `is_valid_conversation_id`
- `bot/app.py` (111-170, 200-242) — callback registration, boot cleanup hooks
- `bot/handlers.py` (64, 83-112, 235-292, 618-660, 693, 734, 1056-1840, 2700) — auth helpers,
  failure classification, all cid-bearing handlers
- `bot/db.py` via `git show HEAD:` — (37-55) `is_transient_sqlite_error`, (255-261) TTL constants,
  (555-565) PRAGMAs, (590-816) schema, (822-870) `_migrate()`, (2565-2575) `prune_web_sessions`,
  (2699-2732) `list_watched`, (3023-3068) `prune_processed_updates`, (3070-3125) `take_awaiting`,
  (5320-5335) boot maintenance hook
- `bot/update_outcomes.py` (93-113) — `acknowledgment_boundary`
- `bot/config.py:292` — `MINI_APP_SESSION_TTL`

**Verification tooling**
- `pytest`, `pyflakes`, `bandit`, `pip_audit`, `node --test` (all already installed; nothing added)

---

## 3. Evidence and references

Every claim in the spec is backed by an executed command, not source reading alone.

### 3.1 No `callback_refs` exists

```
grep -rn "callback_refs" bot/ tests/     → 0 matches
```

Live table count read from `sqlite_master` on a freshly constructed `Database`:

```
17 tables: attachment_batches, attachment_items, attachment_message_identity,
completion_pending, creation_jobs, deleted_conversations, notification_inbox,
notification_state, notifier_pending, notifier_retry_not_before, outbox,
processed_updates, settings, update_failures, user_state, watched, web_sessions
```

> Method note: `grep -c 'CREATE TABLE' bot/db.py` returns **23**, not 17, because the file also
> contains migration/rebuild scaffolding. The `sqlite_master` count is authoritative.

### 3.2 Measured overflow thresholds (executed against the real `_btn()` guard)

```
deleteok:  overflows at cid length 56   (safe max 55)
unwatch:   overflows at cid length 57   (safe max 56)
watch:     overflows at cid length 59   (safe max 58)
status:    overflows at cid length 58   (safe max 57)
cost:      overflows at cid length 60   (safe max 59)
export:    overflows at cid length 58   (safe max 57)
files:     overflows at cid length 55   (safe max 54)   <-- worst case
```

**New finding beyond the baseline text:** the baseline names `deleteok:` (9 bytes) and `unwatch:`
as the tight cases, but the genuinely binding constraint is **`files:`/`file:` at 54 characters**,
because those payloads carry two extra numeric segments (`:{gen}:{page}`). A 56-char ID — fully
valid under `_ID_RE` — already crashes both. This tightens the token size budget.

### 3.3 Token/cid ambiguity (security-relevant, newly identified)

```
is_valid_conversation_id('a1b2c3d4e5f6')  → True
is_valid_conversation_id('~a1b2c3d4e5f6') → False
```

A bare token **passes** the conversation-ID validator. This is not a flaw in the proposal but a
hazard for the *implementation*: a missed resolver call would silently send a garbage ID upstream
instead of failing loudly. The spec mandates resolution at a single choke point, forbids
value-sniffing dispatch, and requires a regression test asserting no unresolved 12-char value
reaches the client.

### 3.4 Proposed token verified to fit every payload

```
secrets.token_urlsafe(9) → 'jxt84_YgzkwB'  (12 chars)
files:{token}:0:0    → 22 bytes
file:{token}:0:0     → 21 bytes
deleteok:{token}     → 21 bytes
```

Maximum allowed token length measured at 54 bytes (`files:` worst case); a 12-char token leaves
42 bytes of headroom.

### 3.5 Existing patterns the design reuses (not invents)

| Pattern | Source | Reused for |
|---|---|---|
| `BEGIN IMMEDIATE` + explicit `rollback()` + `raise` | `db.py:3070-3125` (`take_awaiting`) | Atomic single-use consumption |
| Bounded delete honoring a watermark | `db.py:3023` (`prune_processed_updates`) | Bounded cleanup shape |
| TTL delete from boot maintenance | `db.py:2565` + `db.py:5329` | Cleanup hook placement |
| `CREATE TABLE IF NOT EXISTS` + indexed `expires_at` | `db.py:731-739` (`web_sessions`) | Schema + index convention |
| `is_transient_sqlite_error` (`sqlite_errorcode & 0xFF`) | `db.py:37-51` | BUSY/LOCKED classification |
| `_safe_answer` swallowing only Telegram/timeout errors | `handlers.py:83-105` | Stale-tap safety |
| `_authorized_conversation_status` | `handlers.py:235` | Dispatch-time re-authorization |

### 3.6 Baseline suite confirmed green before writing

```
pytest -q  →  3385 passed, 74 warnings in 168.30s  (exit 0)
```

Unchanged from the WP-06 Part 1 baseline — confirms no drift and that this task's baseline is real.

---

## 4. Files created

| File | Lines | Purpose |
|---|---|---|
| `docs/design/OHB2-WP06-PART2-CALLBACK-REFS-DESIGN-SPEC.md` | 674 | The design specification (15 sections + appendix) |
| `docs/reviews/OHB2-WP06-PART2-CALLBACK-REFS-DESIGN-REPORT.md` | this file | The design report |
| `docs/design/` | — | New directory (did not exist) |

**No other file was created, modified, or deleted.**

---

## 5. Confirmation of non-modification

| Area | Status | Evidence |
|---|---|---|
| Production code | **NOT modified** | `git status --short` shows only the 6 pre-existing modified files; `bot/` diff is byte-identical to the pre-task state |
| Tests | **NOT modified** | No test file appears in the post-task diff; 13 pre-existing untracked files unchanged |
| Schema / migrations | **NOT modified** | `bot/db.py` untouched by this task; live table count still **17** |
| Callback payloads | **NOT modified** | `bot/keyboards.py` untouched (clean, unmodified) |
| Mini App | **NOT modified** | No `bot/web/` or Mini App path touched |
| WP-07 | **NOT modified** | The 6 pre-existing WP-07 modified files are untouched |
| Dependencies | **NOT installed/changed** | `requirements*.txt` untouched; all tools pre-existing |
| Git history | **NOT changed** | HEAD still `52e7789`; no commit, push, PR, merge, deploy, release |
| Secrets | **NOT accessed/disclosed** | No credential read; no `.env` content printed |
| Live services | **NOT called** | No Telegram or OpenHands API call made |

Autopush remained disabled/inactive — no push was attempted.

---

## 6. Unavailable checks

| Check | Status | Reason |
|---|---|---|
| Implementation-level tests | **NOT APPLICABLE** | Design-only task; no code written, so nothing to test |
| Migration dry-run | **NOT RUN — deliberately** | Task prohibits executing migrations or changing schema |
| Runtime verification of TTL/concurrency | **NOT RUN — deliberately** | Would require the prohibited implementation |
| Independent review | **NOT PERFORMED** | This is a design deliverable, not a review; and independence cannot be established in this environment (documented in prior sessions) |

Nothing above is claimed as passing. Where a claim required execution (overflow thresholds, table
count, token fit, ambiguity check, baseline suite), it **was** executed and the output is quoted.

---

## 7. Design completeness against the baseline prerequisite

The baseline (`§WP-06` item 3) requires the spec to satisfy five areas. Mapping:

| Baseline requirement | Spec section | Status |
|---|---|---|
| Explicit TTL / retention policy (`created_at`/`expires_at`) | §4 | **Covered** — 30 min proposal + full boundary table |
| Bounded cleanup, no unbounded growth, no new daemon | §5 | **Covered** — batch 200, `LIMIT`, insert-path cap, existing hooks only |
| Missing/expired/malformed/unknown → fail closed via `_safe_answer`, record ignored/rejected, never raise into `_classify_failure` | §4.3, §6, §11 | **Covered** — 12-row failure table |
| Ownership/authorization/user+conversation binding, `_allowed` first, cross-user rejection, dispatch-time re-verify | §7 | **Covered** — incl. `action_scope` for cross-prefix replay |
| Stale callback resilience across restarts without blocking `acknowledgment_boundary()` | §5, §10.3, §12 | **Covered** — restart persistence + eligible outcomes |

Also delivered beyond the minimum: single-use atomic consumption (§8), alternatives analysis
(§14), and a token/cid ambiguity control (§3.4) that the baseline does not mention but that the
implementation would otherwise be exposed to.

---

## 8. Risks the owner should weigh before approving

1. **`O-5` is a hard gate.** The baseline mandates explicit design-spec review before the
   `17 → 18` table addition. Approval of this document is that review.
2. **Token/cid ambiguity (§3.3)** is the single highest implementation risk. The design mitigates
   it structurally, but it must be enforced by a test, not by discipline.
3. **`files:`/`file:` are the binding payloads (54 chars)**, not `deleteok:` as the baseline text
   implies. Token sizing must respect 54, not 55.
4. **Rollback drops all outstanding tokens** — safe (degraded menus) but user-visible.
5. **`bot/db.py` and `bot/handlers.py` are WP-07-dirty.** Implementation must be sequenced against
   WP-07 to avoid conflicts in those two files; `O-7` records this.

---

## 9. Recommended next step

Owner reviews this spec and resolves **O-1 … O-7**. On approval, WP-06 Part 2 becomes eligible
for an implementation task with its own acceptance criteria. Until then WP-06 Part 2 remains
**open and blocked on design approval** — this task does not close it.
