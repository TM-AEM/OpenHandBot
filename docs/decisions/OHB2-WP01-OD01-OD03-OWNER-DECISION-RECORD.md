# OHB2 — WP-01 Owner Decision Record: OD-01 Option C and OD-03 Option A

**Record ID:** `OD-WP01-OD01-OD03-01`
**Date:** 2026-11-22
**Recorded by:** AI agent (OpenHands) on behalf of the repository owner
**Authorization source:** Explicit owner authorization in task `OHB2-WP01-ATTACHMENT-LIFECYCLE-IMPLEMENTATION`
**Status:** `OWNER-APPROVED` for the exact scope below
**Baseline:** `main` at `0774c9cff923a2ed02da36a1111a283a61600ea5`

> This is an **append-only owner decision record**. It does not rewrite, reinterpret, or backdate
> `D-34`, `D-35`, the OD-01/OD-03 briefing, the decision package, or any historical report.
> It records the owner's current explicit authorization for WP-01 implementation only. It does not
> close WP-01 and does not authorize unrelated work.

---

## 1. OD-01 — approved policy

**Decision: Option C — Hybrid explicit terminal clearance.**

Binding rules:

1. `TERMINAL_ASSOCIATED` remains fail-closed and is never cleared or bypassed.
2. `TERMINAL_UNPROVEN` remains fail-closed and is never cleared or bypassed.
3. `UNRESOLVED` states (`intent_recorded`, `dispatching`, `uncertain`), `MULTI_LIVE`,
   `EXPIRED_PENDING`, `invalid_t0`, out-of-enum/NULL states, and ambiguous ownership remain
   fail-closed.
4. Clearance is **explicit**, **owner-scoped**, and **specific to one batch per operation**.
5. Only a durably verified **`expired`** or **`rejected`** batch is eligible for clearance.
6. **`delivered`** and **`failed`** batches are **not eligible** for clearance.
7. There is no automatic clearance on timeout, reaper sweep, startup, duplicate delivery, or `/cancel`.
8. Clearance must be durable before a success response is emitted; database errors fail closed.
9. Clearance must be idempotent and safe under duplicate Telegram updates.
10. No attachment files, staging files, directories, `attachment_batches`, or
    `attachment_message_identity` rows may be deleted by the clearance operation.
11. D-35 remains binding: message-identity evidence is preserved independently of
    `processed_updates` pruning.
12. No `exactly-once` external-delivery claim is made.

**Explicit non-authorization:** irreversible cleanup of pre-existing batches/files requires a
separate explicit owner approval. This record does not grant it.

---

## 2. OD-03 — approved policy

**Decision: Option A — `ATTACHMENT_DOCUMENT_INTAKE_ENABLED` defaults to `False`.**

Binding rules:

1. New installations have Telegram document intake disabled by default.
2. `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=1` explicitly enables the supported local intake path.
3. `ATTACHMENT_DOCUMENT_INTAKE_ENABLED=0` remains disabled.
4. Disabled intake must not silently accept, download, persist, or queue a new document.
5. Disabled intake must produce truthful, actionable Arabic user-facing behavior.
6. Unrelated attachment paths (unsupported-media rejection, text/buttons) remain functional.
7. No Mini App, `bot/web/*`, `docs/MINI_APP.md`, or `Config.mini_app_*` changes are authorized.
8. No dependency, lockfile, CI, or architecture change is authorized by this decision.

---

## 3. WP-01 implementation authorization

The owner authorizes implementation **within the existing WP-01 scope**:

- OD-03 default change and documentation parity;
- OD-01 Option C per-batch terminal clearance for `expired`/`rejected` only;
- safe active-batch abandonment that does not unlink or delete data;
- policy-aware attachment acceptance/unsupported-media messaging (`DEF-011-C` / `NEW-DEF-06`
  portions confirmed by WP-01);
- focused regression tests and verification.

The implementation must begin with a read-only inventory. Irreversible cleanup remains separately
unauthorized. WP-01 is not closed by this record; closure requires implementation verification and
the project's normal review/closure process.

---

## 4. Scope exclusions

- No `DEF-011-A` quota reservation ledger.
- No rewrite or reimplementation of `DEF-011-B`.
- No concurrency-policy change (`OD-04`).
- No poison-update skipping (`OD-02`).
- No Mini App/scaffold changes.
- No schema migration unless an authoritative WP-01 requirement proves it necessary and it is within
  the approved scope.
- No unrelated work-package changes, refactoring, or cleanup.

---

## 5. History preservation

- `D-34` and `D-35` remain recorded with their original dates and text.
- The OD-01/OD-03 decision package and analysis report are not rewritten.
- This record is additive and dated 2026-11-22.
