# OHB2 — WP-09 npm Canonical Lockfile and CI Repair

**Task ID:** `OHB2-WP09-NPM-CANONICAL-LOCKFILE-AND-CI-REPAIR`
**Date:** 2026-11-23
**Mode:** implementation + verification; no commit/push/publication.
**Status:** implementation in progress; final evidence to be appended.

---

## 1. Historical audit baseline

The prior WP-09 audit used:

- Branch: `main`
- `HEAD`: `2d528633a86472a6a502d7dca5b69ae9f10359ab`
- Tree: `90b62951e53156ac55cffca2f471a0690f21b3d0`
- Date: 2026-11-23
- Python 3.11.18 / 3.13.15: 3823 passed each
- Node.js 24.22.2
- Node tests: 280 passed
- `npm install`, build, lint passed in a temporary copy
- `npm ci` failed in an isolated archive with missing optional platform packages
- CI ran Node tests only; no install/build/lint

The historical audit reports are preserved and are not rewritten by this task.

---

## 2. Actual implementation baseline

Recorded before edits:

| Item | Value |
|---|---|
| Branch | `main` |
| `HEAD` | `2d528633a86472a6a502d7dca5b69ae9f10359ab` |
| Tree | `90b62951e53156ac55cffca2f471a0690f21b3d0` |
| Local `origin/main` | `2d528633a86472a6a502d7dca5b69ae9f10359ab` |
| Staged | none |
| Worktree | pre-existing uncommitted WP-03/A4-F5 work preserved |
| Node | `v24.22.2` |
| npm | `12.2.2` |
| `package.json` SHA-256 | `7109dbebd687dce82f3c83190c74d95a6de4ac5de56f92286d033fb076478a0c` |
| `package-lock.json` SHA-256 | `91a6e25200bac0265e3d803a73064b1fa212a1373466579f42bb97b9733e6f7d` |
| `bun.lock` SHA-256 | `a56fa7c7f37cbc9bb6c53a7107f5e073f6612e714afa9d378eb10f4e341c77be` |
| `.github/workflows/ci.yml` SHA-256 | `e2edadf028a983b7e0c2c8cb7270e64ea99e8be1dce35339020e18e124fdd6d5` |

Pre-existing tracked modifications and untracked files were preserved; no reset, clean, stash,
broad deletion, or staging was performed.

---

## 3. Diagnosis before edits

### F01 — `npm ci` lockfile drift

`package-lock.json` is lockfileVersion 3. `npm ci` in an isolated `git archive HEAD` copy exits `1`
with `EUSAGE` because the lock is missing optional platform packages, including:

- `@tailwindcss/oxide-*`
- `lightningcss-*`
- `@rolldown/binding-*`
- `@typescript/typescript-*`
- `@emnapi/*`, `@napi-rs/wasm-runtime`, `@tybys/wasm-util`

The existing dependency versions are internally consistent; the defect is missing optional platform
entries and `dev` metadata on optional packages. A probe regeneration with npm 12.2.2 added 59 package
entries and removed no existing package entries; **no existing package version changed**.

### F04 — competing lockfiles / package manager

`bun.lock` exists alongside `package-lock.json`. `bun` is not installed. No active workflow, script, or
runtime reference to Bun was found outside historical documentation. npm is approved as canonical.

### F02 — CI coverage gap

`.github/workflows/ci.yml` frontend job runs only `node --test tests/frontend/*.test.js`. It does not
run `npm ci`, `npm run build`, or `npm run lint`.

### F03 — stale Node 22 references

The active master-plan text contains Node 22 references, while current CI, corrected baseline, and
Mini App documentation use Node 24. Historical audit records also contain Node 22; they are preserved as
historical evidence and will be documented as such rather than rewritten.

---

## 4. Proposed minimal changes (recorded before editing)

1. Add `"packageManager": "npm@12.2.2"` to `package.json`.
2. Regenerate `package-lock.json` with npm 12.2.2 using `npm install --package-lock-only` in the
   repository, preserving existing package versions and adding only missing optional platform entries.
3. Remove `bun.lock` because npm is canonical and no active Bun workflow references it.
4. Add `npm ci`, `npm run build`, and `npm run lint` to the existing Node 24 CI job; keep
   `node --test` and the existing Python matrix.
5. Update the active master-plan Node 22 references to Node 24; preserve historical audit records.
6. Verify `npm ci` in a clean archive, run Node tests/build/lint, Python suite if feasible, static
   checks, workflow syntax validation, and diff checks.

No dependency version upgrades are planned.

---

## 5. Implementation

### 5.1 F01/F04 — canonical npm lockfile

- Added `"packageManager": "npm@12.2.2"` to `package.json`.
- Regenerated `package-lock.json` with npm `12.2.2` using
  `npm install --package-lock-only --ignore-scripts --no-audit --no-fund`.
- The regeneration added **59 optional platform package entries** and removed none.
- **No existing package version changed** (verified by comparing the old and new `packages` maps).
- The resulting lockfile has 270 package entries and retains lockfileVersion 3.

### 5.2 F04 — Bun removal

`bun.lock` was removed because:

- `bun` is not installed.
- No active workflow, script, runtime, or test references Bun.
- The only `bun.lock` references are historical audit/decision documents.
- npm is the approved canonical package manager.

The historical documents that mention Bun were preserved unchanged.

### 5.3 F02 — CI coverage

Added to the existing Node 24 frontend job in `.github/workflows/ci.yml`:

1. `npm ci`
2. existing `node --test tests/frontend/*.test.js`
3. `npm run build`
4. `npm run lint`

No new scripts or parallel dependency installation were introduced. The Python job and matrix are
unchanged.

### 5.4 F03 — Node.js references

Updated the active WP-09 master-plan text from Node 22 to Node 24:

- `docs/audits/OHB2-REMEDIATION-MASTER-PLAN.md` WP-09 concrete changes
- `docs/audits/OHB2-REMEDIATION-MASTER-PLAN.md` WP-09 acceptance criteria

Historical audit documents that mention Node 22 were preserved as historical evidence. They are not
active configuration; current CI, `docs/MINI_APP.md`, and the corrected baseline use Node 24. The
remaining references are in `docs/audits/OHB2-INDEPENDENT-AUDIT-REPORT-VALIDATION.md`,
`docs/audits/OHB2-COMPLETE-REPOSITORY-AUDIT.md`, `docs/audits/OHB2-FILE-BY-FILE-AUDIT.md`, and
`docs/audits/OHB2-OWNER-DECISIONS-BRIEFING.md`; these are preserved historical records.

---

## 6. Verification evidence

### 6.1 Clean-copy `npm ci`

An isolated copy was built from `git archive HEAD` plus the final worktree files for
`package.json`, `package-lock.json`, `.github/workflows/ci.yml`, and the master-plan update; `bun.lock`
was absent.

```sh
cd /tmp/ohb2-wp09-final
npm ci
```

Result: **exit 0**, `added 178 packages`, `audited 185 packages`, `found 0 vulnerabilities`.

The lockfile SHA-256 before and after `npm ci` was identical:

```text
85eb4f97e69b6aa189542e064b588536e3f867163a70ca5ca636f382102d3c76  package-lock.json
85eb4f97e69b6aa189542e064b588536e3f867163a70ca5ca636f382102d3c76  /tmp/ohb2-wp09-final/package-lock.json
```

Optional platform entries now present include:

- `@tailwindcss/oxide-linux-x64-gnu@4.3.5`
- `@tailwindcss/oxide-linux-x64-musl@4.3.5`
- `lightningcss-linux-x64-gnu@1.33.0`
- `lightningcss-linux-x64-musl@1.33.0`
- `@rolldown/binding-linux-x64-gnu@1.2.19`
- `@rolldown/binding-linux-x64-musl@1.2.19`

`npm ls --depth=0` exited `0` and listed the expected direct dependency tree (Vite 8.3.8, React
19.3.1, Tailwind 4.3.5, TypeScript 7.0.2, etc.).

### 6.2 Frontend tests, build, and lint

In the same clean copy, after `npm ci`:

| Command | Result | Exit |
|---|---|---|
| `node --test tests/frontend/*.test.js` | **280 passed, 0 failed, 0 skipped** | 0 |
| `npm run build` | Vite 8.3.8; 16 modules; `dist` built in 251 ms | 0 |
| `npm run lint` | `tsc --noEmit` clean | 0 |

npm reported three blocked install scripts (`@google/genai`, `esbuild`, `protobufjs`) as a policy
warning; tests, build, and lint still succeeded.

### 6.3 Python regression

No Python source, test, requirements, or Python CI job was changed. For regression safety, both Python
versions were still run against the current worktree:

| Runtime | Full suite | Exit |
|---|---|---|
| Python 3.11.18 | **3823 passed, 0 failed, 74 warnings** | 0 |
| Python 3.13.15 | **3823 passed, 0 failed, 74 warnings** | 0 |

Static checks on Python 3.13:

| Check | Result | Exit |
|---|---|---|
| `pyflakes bot/ automation/ tools/ main.py tests/` | no diagnostics | 0 |
| Bandit | **High 0**; Low 5 / Medium 19 | 0 |
| `pip-audit -r requirements-dev.txt` | **No known vulnerabilities found** | 0 |
| `git diff --check` | clean | 0 |

### 6.4 CI workflow syntax

The updated `.github/workflows/ci.yml` parses as YAML. The frontend steps are:

- Set up Node.js 24 (LTS)
- Install frontend dependencies (npm ci)
- Frontend tests (node --test)
- Frontend build
- Frontend lint

The Python matrix remains `["3.11", "3.13"]`.

### 6.5 CI execution status

**No GitHub Actions run was performed or queried.** `gh` is not authenticated in this environment, and
no fetch/pull was performed. The workflow change is syntax-validated locally; actual GitHub CI
execution remains **NOT VERIFIED**.

---

## 7. Per-finding status

| Finding | Status | Evidence |
|---|---|---|
| `WP09-F01` — `npm ci` lockfile inconsistency | **RESOLVED** | Clean-copy `npm ci` exit 0; lock unchanged; 59 optional entries added; 0 existing version changes |
| `WP09-F02` — CI does not validate frontend install/build/lint | **RESOLVED (local workflow)** | Node 24 job now runs `npm ci`, tests, `npm run build`, `npm run lint`; YAML parses; actual GitHub run **NOT VERIFIED** |
| `WP09-F03` — stale Node 22 references | **RESOLVED (active docs)** | Active master-plan WP-09 references updated to Node 24; historical audit references preserved |
| `WP09-F04` — competing lockfiles / no canonical package manager | **RESOLVED** | `packageManager: npm@12.2.2`; `bun.lock` removed; no active Bun workflow; historical docs preserved |

No finding is `PARTIALLY RESOLVED`, `BLOCKED`, or still open.

---

## 8. Remaining risks and limitations

1. **GitHub Actions was not executed.** Local workflow syntax and equivalent local commands pass, but
   published CI results are not available in this environment.
2. `packageManager` declares npm `12.2.2`; the actual npm version on a GitHub Node 24 runner may differ.
   The lockfile is v3 and locally verified with npm 12.2.2.
3. npm reports three blocked install scripts in this environment. They did not block tests/build/lint;
   this is an npm policy/security setting, not a code failure.
4. Historical audit/decision documents still mention Node 22 and `bun.lock`; they are intentionally
   preserved as historical evidence and are not active configuration.
5. The Python full suite includes pre-existing uncommitted A4-F5/WP-03 work; those changes are not
   authored by this task.
6. This is implementation and local verification evidence only. **No independent review, owner
   acceptance, or WP-09 closure has occurred.**

---

## 9. Final Git state and changed files

| Item | Value |
|---|---|
| Branch | `main` |
| `HEAD` | `2d528633a86472a6a502d7dca5b69ae9f10359ab` (unchanged) |
| Tree | `90b62951e53156ac55cffca2f471a0690f21b3d0` (unchanged) |
| Staged | none |
| Commits/push/PR/merge/deploy/release | none |

Changed by this task:

- `package.json`
- `package-lock.json`
- `bun.lock` (removed)
- `.github/workflows/ci.yml`
- `docs/audits/OHB2-REMEDIATION-MASTER-PLAN.md`
- `docs/reviews/OHB2-WP09-NPM-CANONICAL-LOCKFILE-AND-CI-REPAIR-REPORT-20261123.md` (new)

Pre-existing modifications and untracked files remain preserved and unstaged.

---

## 10. Readiness

**`READY — AWAITING BATCH INDEPENDENT REVIEW`**

All four WP09 findings are implemented and locally verified. This is **not** independent review,
owner acceptance, or WP-09 closure; the batch independent review must still examine the implementation
and the exact working-tree snapshot.

### Critical file hashes

| File | SHA-256 |
|---|---|
| `package.json` | `6a7931e96d84c232cabd5f7097901955ad1db87a441a06d5faca7c7556cbdefb` |
| `package-lock.json` | `85eb4f97e69b6aa189542e064b588536e3f867163a70ca5ca636f382102d3c76` |
| `.github/workflows/ci.yml` | `f030d01a9ab22079af26ab9139ffd717f13391ff9e339d1646e29bdcabdeda79` |
| `docs/audits/OHB2-REMEDIATION-MASTER-PLAN.md` | `a04b57f774e9737342e2e5c25b3d4f9b9201ce4d27dbc6366339731ff4d24ffb` |

---

## 11. Report integrity

**Report body SHA-256 (excluding this footer):** `9ff2710807ae964c6ad65cf8c28ca76c6b3589576af8e2148ee20f6d0f768e25`
