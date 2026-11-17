# OHB2 Repository Audit — Executive Summary

**Task ID:** `OHB2-COMPLETE-REPOSITORY-AUDIT-AND-REMEDIATION-MASTER-PLAN`  
**Audit Date:** 2026-11-17  
**Baseline Scope:** 328 repository files (`0` baseline files modified during this audit)  
**Overall Readiness Verdict:** **`NOT_PRODUCTION_READY` (Critical Self-DoS & Polling Deadlock Risks Present)**

---

## 1. Executive Verdict

OpenHandBot has a well-engineered core persistence and delivery engine (`bot/outbox.py`, `bot/db.py`, `bot/deletion.py`, `bot/files.py`, `bot/watcher.py`, `bot/notifier.py`) with strong `at-most-once` CAS guarantees, remote deletion tombstones, secret redaction, and path-traversal protection. However, the codebase is **not ready for unattended production deployment** in its current state due to:

1. **A Critical Normal-Usage Self-DoS ("Owner Brick", `DEF-001`):** Local attachment intake (`P0 A0–A4`) is **enabled by default** (`ATTACHMENT_DOCUMENT_INTAKE_ENABLED=True`) even though remote upload (`Stage B1/B2`) is unimplemented (`DEF-015`). Sending even **one document** causes either permanent `UNRESOLVED` blocking (if accompanying text is sent) or permanent `TERMINAL_UNPROVEN` blocking (once the batch expires after 15 minutes) across **all** conversations for that user, with no `/cancel` escape hatch.
2. **Polling Head-of-Line Deadlocks & Incomplete Outcome Contracts (`DEF-002`..`DEF-005`):**
   - `FAILED_PERMANENT` locks `TelegramPoller._next_offset` indefinitely (ADR §28.4 poison skip unimplemented), while `_classify_failure` misclassifies transient `TelegramError` (`RetryAfter`, `TimedOut`, `NetworkError`), `asyncio.TimeoutError`, and `OSError` as `FAILED_PERMANENT`.
   - **24 of 28** `q.answer()` callback query sites in `bot/handlers.py` lack `try/except`, causing any stale inline button (`>30–60s`) to poison polling.
   - `outbox_mark_sent` and `reposearch` have branches returning with `outcome=None` (`PARTIAL_OR_UNKNOWN` ack block) or consuming `reposearch` on HTTP 503, and 8 handlers/helpers bypass `Stage4-F1` operational `5xx`/`429` failure propagation.
3. **Unverified Runtime & Hosting Gates (`DEF-016`, `DEF-019`):** Live Enzonic SFTP connectivity, SQLite restart durability (`H1`), `HOST-01`/`HOST-02` hosting, and local Python `pytest`/`pyflakes`/`bandit`/`pip_audit` verification in this container (`Python 3.10.12` stdlib only) remain unexecuted/unverified.

---

## 2. Severity & Scope Distribution

| Metric | Count | Details |
|---|---|---|
| **Baseline Files Audited** | **328** | Complete classification in `OHB2-FILE-BY-FILE-AUDIT.md` |
| **Total Defects Identified** | **19** | `1 CRITICAL`, `7 HIGH`, `9 MEDIUM`, `2 LOW` (`19 CONFIRMED`) |
| **Critical Risk** | **1** | `DEF-001` (Permanent Text-Prompt Self-DoS After Any Document Upload) |
| **High Risks** | **7** | `DEF-002` (Poison Lock / Network Misclass), `DEF-003` (`outcome=None` / `reposearch`), `DEF-004` (`Stage4-F1` Gaps), `DEF-005` (24 Unwrapped `q.answer()`), `DEF-015` (Stage B Blocked), `DEF-016` (Hosting / Live SFTP Unverified), `DEF-019` (Python Gate Blocked Locally) |
| **Medium / Low Risks** | **11** | `DEF-006`..`DEF-014`, `DEF-017`, `DEF-018` |
| **Mini App Scope Boundary** | **Strict** | `0` Mini App files scheduled for edit (`DEF-014` tagged `BLOCKED_BY_EXCLUDED_MINI_APP`) |

---

## 3. Top Risks Requiring Immediate Action

1. **`DEF-001` [CRITICAL] — "Owner Brick" on Document Upload:** Must be mitigated immediately (**Phase 0 / `WP-01`**) by defaulting `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` to `False`, enabling `/cancel` batch abandonment + staging cleanup, and reconciling D-34 `TERMINAL_UNPROVEN` global blocking so a finished/expired attachment batch never permanently bricks normal prompting across conversations.
2. **`DEF-002` + `DEF-005` [HIGH] — Polling Freeze on Stale Buttons / Telegram Timeouts:** Wrapping all 28 `q.answer()` calls (`WP-02`), classifying `TelegramError`/`asyncio.TimeoutError`/`OSError` as transient (`WP-04`), and adding ADR §28.4 poison quarantine prevent routine network hiccups or queued stale callbacks from halting the bot.
3. **`DEF-003` + `DEF-004` [HIGH] — Outcome & Operational Error Gaps:** Closing `outbox_mark_sent` / `reposearch` `outcome=None` races and migrating the remaining 6 `_authorized_conversation` callers + listing handlers (`WP-03`) makes Telegram ACK guarantees consistent across every bot command and button.
4. **`DEF-017` [MEDIUM] — Runbook Contradictions:** `docs/ZERO_TOUCH_STARTUP.md:242` falsely denies remote OpenHands conversation deletion while `bot/deletion.py` actively sends `DELETE`, and `docs/OPERATIONS_RUNBOOK.md` omits 13 SQLite tables (`WP-08`).

---

## 4. Phased Remediation Roadmap & Release Gates

| Phase | Work Packages | Objective | Release Gate |
|---|---|---|---|
| **Phase 0 (Emergency)** | `WP-01` | Stop `DEF-001` self-DoS (`ATTACHMENT_DOCUMENT_INTAKE_ENABLED=0` default + `/cancel` batch reset + D-34 reconciliation) | **Gate A:** Safe daily text prompting |
| **Phase 1 (Availability)** | `WP-02`, `WP-03`, `WP-04` | Wrap all `q.answer()`, close `outcome=None` & `Stage4-F1` gaps, fix `_classify_failure`, add ADR §28.4 poison skip | **Gate B:** Resilient polling & ACK |
| **Phase 2 (Correctness)** | `WP-05`, `WP-06`, `WP-07` | Fix Watcher/Notifier skip control flow, CreationWorker resume errors, `deliver_outbox`, `get_status()` UI, 64-char `callback_data`, quota lock, poller batch concurrency | **Gate C:** Full concurrency & long-ID parity |
| **Phase 3 (Docs & CI)** | `WP-08`, `WP-09` | Reconcile runbooks/startup docs + run full Python 3.11/3.13 CI (`pytest`, `pyflakes`, `bandit`, `pip_audit`) + Node tests | **Gate C/CI Green** |
| **Phase 4 (Infra/External)** | `WP-10` | Verify live Enzonic SFTP fingerprint + secret, pass `H1` SQLite restart canary, keep P0 Stage B gated | **Gate D:** Production cutover readiness |

---

## 5. Verification Summary & Deliverables Index

- **Directly Verified in Container:** `ast.parse` **165/165** Python files (`0` syntax errors); `node --test tests/frontend/*.test.js` **280 pass / 0 fail**.
- **Blocked Locally (`NOT_RUN`):** `pytest`, `pyflakes`, `bandit`, `pip_audit` (Python 3.11+ / `requirements-dev.txt` absent in container), live Enzonic SFTP, and live hosting persistence canary.
- **Audit Package Deliverables (`/docs/audits/`):**
  - `OHB2-AUDIT-EXECUTIVE-SUMMARY.md` (this file)
  - `OHB2-COMPLETE-REPOSITORY-AUDIT.md` (comprehensive technical audit)
  - `OHB2-COMPLETE-DEFECT-REGISTER.md` (19 defects × 17 fields each)
  - `OHB2-INCOMPLETE-FEATURES.md` (7-category feature completeness matrix)
  - `OHB2-REMEDIATION-MASTER-PLAN.md` (`WP-01`..`WP-10` dependency-aware plan)
  - `OHB2-FILE-BY-FILE-AUDIT.md` (all 328 baseline files classified)
