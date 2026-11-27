# OHB2-R7 — Canary Linkage Author Self-Review (2026-11-25)

**Task ID:** `OHB2-R7-CANARY-LINKAGE-D01B-D02-EXPLICIT-LIST`
**Review type:** `AUTHOR_SELF_REVIEW` only.
**Verdict:** `R7_CANARY_LINKAGE_IMPLEMENTED_AND_VERIFIED_WITH_NOTES`

This is not independent review, not live validation, and not a claim that D-03 through
D-09 are approved. No worker was activated and no external call was made.

---

## 1. Complete diff reviewed

Changed/added:

- `bot/review/canary_linkage.py` — D-01 B source and D-02 owner entry point.
- `bot/db.py` — one read-only creation-job query; no schema change.
- `bot/review/__init__.py` — docstring only.
- `tests/test_review_canary_linkage.py` — 42 mocked tests.
- `docs/OPERATIONS_RUNBOOK.md` — canary adapter boundary.
- `.agent/PROGRESS.md` — additive entry.
- This report and the implementation report.

Archived prior owner-decision-required reports were preserved under explicit
`OWNER-DECISION-REQUIRED` names.

---

## 2. Required review checks

| Check | Result | Evidence |
|---|---|---|
| Accidental PR discovery | PASS | No PR list/search or GitHub discovery call; only `get_pull_request(number)` with owner-supplied numbers |
| Trust in names without numeric ID | PASS | Link and membership use `RepositoryIdentity.repository_id`; resolver re-verifies |
| Conversation-ID confusion | PASS | Exact `conversation_id` query; one row only; OpenHands record ID equality |
| Cross-repository PR acceptance | PASS | Resolver base/head repository ID and name checks; test rejects other repo |
| Stale SHA acceptance | PASS | Exact head SHA, compare observed SHA, branch re-verification; tests |
| Membership mutation | PASS | Existing triggers; update test raises `sqlite3.IntegrityError` |
| Partial cycle creation | PASS | Invalid partial list raises before reservation; zero cycles |
| Retry duplication | PASS | Identical retry returns `already_reserved`; one review row |
| Authorization bypass | PASS | Owner `chat_id` check before dependencies; resolver `watched` check remains |
| Secret leakage | PASS | Error is safe code; sentinel absent; no token logging |
| Runtime worker activation | PASS | No `bot/app.py` change; no worker/runner construction |
| Unintended network access | PASS | All tests use fakes; no live calls |
| R1–R6 behavior changes | PASS | Full suite 4296 passed; resolver untouched |

---

## 3. Design-specific notes

### Note 1 — D-01 semantic failures collapse to a missing link

`CreationJobRepositoryLinkSource` returns `None` for missing, ambiguous, malformed, and
untrusted associations. The existing resolver maps that to
`missing_conversation_repository_link`. Operational DB/GitHub failures surface as
`conversation_link_unavailable`. This is fail-closed but less granular than the
repository-name mismatch code. No resolver behavior was changed to manufacture extra
codes.

### Note 2 — OpenHands selected_repository is a check only

The source requires `selected_repository` equality when available. It never uses it as
a fallback or authority. If it is missing or mismatched, the association is rejected.

### Note 3 — Same-name delete/recreate remains unprovable

`creation_jobs` does not persist the GitHub numeric ID observed at creation. The source
therefore cannot distinguish the original repository from a same-name recreated one.
This is recorded in the implementation and a dedicated test; it is not claimed as
identity continuity. Fixing it requires a separate D-04 schema decision.

### Note 4 — Owner-only D-02 is canary authorization, not D-03 closure

The service requires `chat_id == Config.owner_id` and still passes through the existing
`watched.chat_id` authorization in the resolver. It does not add an OpenHands owner
check or a new authorization source. D-03 remains open for any broader rule.

### Note 5 — No schema change

The implementation uses the existing `creation_jobs` columns. No table, index, trigger,
or migration was added. `list_done_creation_jobs_for_conversation()` is read-only.

### Note 6 — No automatic PR omission

A list with one valid and one invalid PR fails as a whole. The test with a valid PR and
a closed second PR asserts no active cycle and no partial membership.

---

## 4. Test evidence

| Check | Result |
|---|---|
| New canary suite | 42 passed |
| Resolver + canary + lifecycle + membership | 124 passed |
| Review-focused suite | 472 passed |
| Full Python suite | 4296 passed, 0 failed |
| Node suite | 280 pass, 0 fail |
| pyflakes | 0 issues |
| compileall | 0 errors |
| Bandit high severity | 0 |
| pip-audit | no known vulnerabilities |
| `git diff --check` | clean |

Python 3.11 and remote CI were not run; no claim is made for them.

---

## 5. Residual risks and blockers

- Same-name repository deletion/recreation is indistinguishable (D-04).
- Rename/transfer policy remains reject-by-default (D-05).
- Fork policy remains reject-by-default (D-06).
- Worker activation is not implemented (D-07).
- No live OpenHands/GitHub/provider/Telegram validation exists (D-08).
- Independent review and R8 remain deferred (D-09).
- No schema/provenance persistence exists; provenance is in-memory only.
- Python 3.11 and remote CI are unverified.

---

## 6. Conclusion

The implementation is bounded to the approved canary scope. It preserves the existing
resolver, conversation-wide scope, immutable memberships, reservation/lifecycle
semantics, and worker inactivity. The only material limitation is the known
same-name repository recreation ambiguity, which is explicitly retained rather than
silently compensated for.

Final verdict: **`R7_CANARY_LINKAGE_IMPLEMENTED_AND_VERIFIED_WITH_NOTES`**.
