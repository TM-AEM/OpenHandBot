# OHB2-P0-A2 — Independent Adversarial Review (read-only)

- Reviewer: separate OpenHands Cloud conversation (fresh context), branch
  `openhands-workspace-3jrWkL2U5fdqzu2fVdxOcW` (the reviewer noted the branch was **not** on the
  remote, so it reconstructed the change set from the verbatim diff embedded in the task and ran the
  real modules + mutation tests; the real repo was left untouched).
- Scope reviewed: P0 Stage A2 only — local attachment **batch lifecycle + authorization**
  (`bot/attachments.py`, `bot/db.py`, `bot/handlers.py`, `bot/app.py`, tests).
- Verdict: **PASS_WITH_NOTES** — all enumerated A2 guarantees survived adversarial probing:
  T0 immutability, exact 15-minute deadline, authorization-before-write, tombstone reject with no
  remote `get_conversations` call, cross-user isolation, row-first durability, no A2 scope creep,
  idempotent duplicate update. 5/5 mutations (T0 extension, expiry disabled, authz skipped, row-first
  broken, stored-before-write) were caught.

## Findings and disposition

| # | Sev | Summary | Disposition |
|---|-----|---------|-------------|
| F-1 | MEDIUM | The stored item never recorded its staging file (`staging_token` NULL) on the A2 path, so A4 could not reclaim staged bytes. | **FIXED** — the token is generated before the durable row and persisted (new/append writers + `set_attachment_item_status`); `StagingStore.store(staging_token=...)` reuses it. Regression: `test_stored_item_references_its_staging_file`, `test_appended_item_also_references_its_staging_file` (mutation-proved). |
| F-2 | MEDIUM | `display_name` was persisted raw (unsanitized), bypassing `sanitize_display_name`. | **FIXED** — `accept()` persists `sanitize_display_name(display_name)`. Regression: `test_display_name_is_sanitized_before_persisting` (mutation-proved). |
| F-3 | LOW | `accept_attachment_item` does not re-verify batch ownership (latent; current caller is scoped). | Accepted as-is for A2 (single-process, caller-scoped). Noted for future hardening. |
| F-4 | LOW | Duplicate `update_id` returns `ACCEPTED` with a non-existent `item_id`. | Accepted (harmless for integrity; group −1 dedupe barrier prevents it in real wiring). |
| F-5 | LOW | The `route` awaiting window is not enforced on the attachment path. | Out of the explicit A2 acceptance criteria; recorded for A3. |
| F-6 | INFO | Batch TTL (15 min) vs route TTL (10 min) gap. | Recorded for an explicit decision (A3/A4). |
| F-7 | INFO | Reply sent on the duplicate short-circuit. | Unreachable in real wiring (dedupe barrier). |
| F-8 | LOW | The two attachment filters are **not** strictly mutually exclusive for a message carrying both a document and an animation/video/audio/photo. | Benign today (PTB dispatches only the first matching handler per group — verified). Recorded; comment/test wording should not over-claim exclusivity. |
| F-9 | INFO | The reviewed tracked diff bundles unrelated non-A2 changes (OHB2-STAGE4-F1 / STAGE2-HIGH-ACK-BLOCKING-FIX) already present on the working branch. | Pre-existing branch state; **not** part of the A2 change set. |

## Notes
- The two MEDIUM defects (F-1, F-2) were in the A2 code and would have surfaced when A4 reclaims staged
  bytes; both are fixed and covered by mutation-proved regression tests.
- F-8: the filter-exclusivity claim is weaker than the code comment/test asserts. The current behavior is
  correct because of PTB's per-group first-match dispatch; the wording was corrected to rely on that.
