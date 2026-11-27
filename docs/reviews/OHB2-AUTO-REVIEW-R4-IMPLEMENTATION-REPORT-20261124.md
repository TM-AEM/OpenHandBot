> **R4 IMPLEMENTATION — NOT INDEPENDENTLY REVIEWED**
>
> Verification mode: `AUTHOR_SELF_REVIEW` + `AUTOMATED_TESTS` + `SECURITY_TESTS`.
> Independent review remains deferred. This report does not claim
> `INDEPENDENT_REVIEW` or `INDEPENDENT_REVIEW_PASS`.

# OHB2-AUTO-REVIEW-R4 — Implementation Report

**Task:** OHB2-AUTO-REVIEW-R4 — Blind Review, Adversarial Review, Evidence Validation,
Deterministic Verdict Engine, and Provider Adapter
**UTC:** `2026-11-24T20:45:00Z`
**Status:** `R4_IMPLEMENTED_PENDING_INDEPENDENT_REVIEW`

---

## 1. Objective and scope

Implemented an isolated, in-process review pipeline:

- `bot/review/schema.py` — strict versioned blind/adversarial output schemas.
- `bot/review/prompts.py` — separate blind and adversarial payload builders.
- `bot/review/llm.py` — provider-neutral adapter interface and bounded HTTP adapter.
- `bot/review/evidence.py` — evidence validation and attribution.
- `bot/review/verdict.py` — deterministic, versioned verdict rules.
- `bot/review/engine.py` — blind-then-adversarial cycle orchestration.
- Focused tests for every R4 module.

Not implemented: ReviewWorker, leases/reservations, scope selection, Telegram delivery,
persistence of review cycles, runtime activation, automatic repair, Katabump, production
database changes, R5. No real provider or GitHub call is made by tests.

---

## 2. Baseline audit (recorded before edits)

| Item | Value |
|---|---|
| Repository | `/workspace/project/OpenHandBot` |
| Branch | `openhands-workspace-11liARbsA7OSSoFJOM2RDr` |
| HEAD | `01079676351aac869d09d4d1747661cd6f07d82b` |
| `main` | same as HEAD |
| `origin/main` | same as HEAD |
| Tree | `3ceb3580e3d0dfcebdd83ebbf9e285c6d4cc67bc` |
| Pre-R4 tracked modifications | R2 files (preserved) |
| Pre-R4 untracked | R0E/R0F/R1/R2/R3 artifacts and R3 review modules (preserved) |
| Pre-R4 Python suite | 3995 passed |
| Pre-R4 Node suite | 280 pass / 0 fail |
| Pre-R4 static checks | pyflakes 0; Bandit High 0; pip-audit clean |

No reset, clean, force, add-all, commit, push, PR, or deploy was performed. The pre-existing
R2 tracked changes and all R0E/R0F/R1/R2/R3 artifacts remain in place.

---

## 3. Files changed or created

### Created

| File | Purpose |
|---|---|
| `bot/review/schema.py` | Strict `r4.v1` blind/adversarial schemas |
| `bot/review/prompts.py` | Separate stage payloads, manifests, fencing, chunking |
| `bot/review/llm.py` | Provider protocol, snapshot binding, bounded HTTP adapter |
| `bot/review/evidence.py` | Line/path/SHA/CI evidence validation |
| `bot/review/verdict.py` | Deterministic verdict rules |
| `bot/review/engine.py` | Isolated two-stage cycle |
| `tests/test_review_schema.py` | Schema tests |
| `tests/test_review_prompts.py` | Isolation/redaction/chunking tests |
| `tests/test_review_llm.py` | Adapter/snapshot/error tests |
| `tests/test_review_evidence.py` | Evidence/attribution tests |
| `tests/test_review_verdict.py` | Precedence tests |
| `tests/test_review_engine.py` | End-to-end cycle tests |
| `docs/reviews/OHB2-AUTO-REVIEW-R4-IMPLEMENTATION-REPORT-20261124.md` | This report |
| `docs/reviews/OHB2-AUTO-REVIEW-R4-AUTHOR-SELF-REVIEW-20261124.md` | Author self-review |

### Modified

| File | Purpose |
|---|---|
| `.agent/PROGRESS.md` | R4 goal, baseline, acceptance criteria, implementation, verification, residual risks |
| `bot/review/__init__.py` | Package docstring only |

R3 `github.py` and `redact.py` were not modified. R2 `config.py` and `db.py` were not modified.

---

## 4. Strict schemas

- Schema version fixed to `r4.v1`; stage must match `blind` or `adversarial`.
- Exact top-level and finding/challenge key sets; unknown/missing/duplicate keys fail closed.
- Bounded output size, findings, reviewed files, gaps, challenges, line numbers, paths, and text.
- Findings have typed severity/category/confidence, optional quote, CI references, and commit SHA.
- `assessment` must be consistent with `findings`/`evidence_gaps`.
- JSON duplicate keys are rejected through `object_pairs_hook`.
- A model-provided `verdict`, `model_recommendation`, or other extra field is rejected as
  `unknown_field`; no model opinion can become the final verdict.
- Malformed output is retried once only through a bounded correction request; a second failure is
  `invalid_output`, never `PASS`.

---

## 5. Blind/Adversarial isolation

### Blind

`BlindReviewInput` has no field for the OpenHands report, OpenHands verdict, prior review,
adversarial output, PR body, PR comments, commit messages, or CI logs. The built payload contains
only the diff, CI check metadata, approved architecture decisions, review instructions, and
repository/SHA metadata.

### Adversarial

`AdversarialReviewInput` contains the validated blind result, the OpenHands report, diff, CI
metadata, architecture decisions, and review instructions. The blind result is bound by its
fingerprint; the adversarial output must echo the exact fingerprint. Adversarial output cannot
rewrite the stored blind result: disagreements are challenges with known blind finding IDs only.

### Enforcement

- Separate builders with separate immutable input dataclasses and separate schemas.
- Manifest records `included_sources` and `excluded_sources`, content hashes, chunk index/count,
  and source fingerprints.
- Untrusted content is fenced with a content-derived nonce; fence-prefix collisions are neutralised.
- Diff/report/architecture/instructions pass through R3 redaction before the prompt is built.
- Oversized input fails closed; no silent truncation.
- Diffs split only at `diff --git` file boundaries, with exact reconstruction verification and a
  maximum chunk count. A single oversized section blocks.

---

## 6. Provider adapter

- `ReviewProvider` protocol allows future provider implementations without changing the pipeline.
- `ProviderBinding` binds a cycle to the immutable R2 `AutoReviewProviderSnapshot`; provider, base
  URL, and model must match the current configuration or `ProviderSnapshotMismatch` is raised.
- The API key is never stored in the snapshot, repr, errors, manifest, or prompt.
- HTTXP adapter is OpenAI-chat-compatible (`POST .../chat/completions`, Bearer header).
- HTTPS required for remote hosts; credentials/query/fragment/traversal in base URL rejected.
- Bounded connect/read/write/pool timeout and bounded request/response bytes.
- No automatic retries. One explicit schema-correction request is allowed after a valid provider
  response; the correction is bounded and redacted.
- 401/403/429/5xx/4xx/3xx/timeout/transport/malformed/oversized responses map to safe typed errors.
- Tests use `httpx.MockTransport` only and assert no token appears in URL or repr.

---

## 7. Evidence validation

- Diff parsing validates unified hunk counts, rejects duplicate paths, and never trusts a content
  line as a path header.
- A finding is accepted only when its path is in the pinned diff, the full line range is covered,
  any quote exists in the patch, any commit SHA equals the pinned base/head, and any CI run/job/status
  exists in the verified evidence.
- Nonexistent lines, traversal paths, fabricated CI IDs, mismatched CI status, and unknown files are
  rejected; a rejected finding is never counted as verified.
- Stale/unverified SHA and incomplete evidence coverage block the whole stage.
- Model-reported `evidence_gaps` block the stage.
- Adversarial challenges may reference only blind finding IDs; a wrong blind fingerprint blocks.
- R3 secret redactions and excluded paths are recorded; a secret in the reviewed diff produces a
  deterministic `FAIL` verdict.

---

## 8. Deterministic verdict

Precedence, implemented in `bot/review/verdict.py`:

1. `R4-SHA-01` — stale/unverified SHA or incomplete diff coverage → `BLOCKED`.
2. `R4-CI-01` — failed `verify`/CI evidence → `FAIL`.
3. `R4-SEC-01` — secret detected in the reviewed diff → `FAIL`.
4. `R4-FINDING-01` — any validated critical/high finding → `FAIL`.
5. `R4-BLOCK-01` — failed/invalid stage, invalid finding, or model evidence gap → `BLOCKED`.
6. `R4-BLOCK-02` — insufficient evidence or adversarial dissent → `BLOCKED`.
7. `R4-CI-02` — CI missing/pending/cancelled/skipped/mixed → `BLOCKED`.
8. `R4-PASS-01` — CI success + no validated findings → `PASS`.
9. `R4-NOTES-01` — only validated medium/low findings → `PASS_WITH_NOTES`.

Duplicate file/ID findings keep the highest severity. The model recommendation is not an input.
Owner acceptance is deliberately separate and is not computed or stored by R4.

---

## 9. Orchestration

`run_review_cycle` is in-process and explicit-input only:

1. Build and validate blind requests.
2. Execute blind stage(s), including at most one correction each.
3. Validate the combined blind output against evidence.
4. Build adversarial requests with the validated blind result and report.
5. Execute adversarial stage(s), validate fingerprint and findings.
6. Return stage executions, validations, request fingerprints, and the deterministic verdict.

No worker, lease, reservation, scope selection, persistence, Telegram delivery, or R5 code was
added.

---

## 10. Verification

| Check | Command | Result |
|---|---|---|
| R4 focused | `pytest -q tests/test_review_schema.py tests/test_review_prompts.py tests/test_review_llm.py tests/test_review_evidence.py tests/test_review_verdict.py tests/test_review_engine.py` | **123 passed** |
| Full Python | `pytest -q` | **4118 passed**, 0 failed, 74 warnings (213.52s) |
| Node | `node --test tests/frontend/*.test.js` | **280 pass**, 0 fail |
| Lint | `python -m pyflakes bot/ automation/ tools/ main.py tests/` | **0** |
| SAST | `python -m bandit -r bot/ automation/ tools/ main.py -lll -s B613` | **High 0** |
| SCA | `python -m pip_audit -r requirements-dev.txt` | **No known vulnerabilities** |
| Compile | `python -m compileall -q bot automation tools main.py` | **0** |
| Whitespace | `git diff --check` | **0** |

### Negative controls

Run on isolated copies under `/tmp/r4-negative` (`/tmp/r4_negative_controls.py`). All ten mutations
were caught by the focused tests:

| Control | Mutation | Result |
|---|---|---|
| C1 | failed CI treated as PASS | caught |
| C2 | Blind receives OpenHands report | caught |
| C3 | Adversarial receives no Blind result | caught |
| C4 | nonexistent finding line accepted | caught |
| C5 | stale SHA accepted | caught |
| C6 | malformed JSON treated as no findings | caught |
| C7 | oversized input silently truncated | caught |
| C8 | secret survives redaction | caught |
| C9 | provider failure treated as successful review | caught |
| C10 | model-provided verdict accepted | caught |

---

## 11. Security review

- No provider/GitHub network call in tests; no real API key used.
- No secret in source, tests, reports, manifests, prompts, reprs, or error messages.
- Prompt injection is treated as data through nonce fences and explicit system instructions.
- Blind stage structurally cannot receive the report/verdict or adversarial output.
- Invalid/stale/fabricated evidence cannot contribute an accepted finding.
- CI failure, secret exposure, and validated high/critical findings cannot be overridden by the
  model or by later stages.
- No write path to GitHub, Telegram, database, or runtime.

---

## 12. Not verified / residual risks

- **Independent review was not performed.** No `INDEPENDENT_REVIEW_PASS` claim.
- Python 3.11 and GitHub Actions were not run locally; the local runtime is Python 3.13.15.
- No real provider was called, so provider-specific response variations beyond the mocked
  OpenAI-compatible contract are unverified.
- R3 redaction is pattern-based; false negatives remain possible (inherited residual risk).
- R4 has no persistence, worker, lease, scope selection, delivery, or R5 integration by design.
- The owner scope policy (conversation-wide vs per-PR) remains unresolved.
- `ProviderSnapshot` binds provider/base/model and rejects secret-like settings, but cannot detect
  a silent upstream model alias change; this remains a future consent/snapshot concern.

---

## 13. Explicit statements

- No commit, push, PR, merge, deploy, or CI trigger occurred.
- No production database was modified.
- No workflow was modified.
- No provider/LLM call or external egress occurred.
- No independent review PASS is claimed.

---

## 14. Hashes

### Source and tests (final)

| File | SHA-256 |
|---|---|
| `bot/review/__init__.py` | `6cb67ec3490f5610bde0e98e0e4e5c34699e8eee009ee4e194341c8ee04de401` |
| `bot/review/schema.py` | `420ec77ab6d0ecaea4e39f0381c11a9959a9303975c520b48a94c00552feff4a` |
| `bot/review/prompts.py` | `4d2fbcffcfc8e797c77557cdf1d6658d481aca280d75006fb2d7ec5d891634da` |
| `bot/review/llm.py` | `e19873e3b81b37fbf80aa387eae3b5ab8ae8d5da311097bf31b00010d6bbc5b7` |
| `bot/review/evidence.py` | `523d512059a548a3e42103bc8409e5ebe3c42dcf9e7f753df8a3752104113920` |
| `bot/review/verdict.py` | `7aa043338754ae11b4bef1b07179ac6ceecff14a2280dd90230366188047b054` |
| `bot/review/engine.py` | `8dcac642fddd3dfff71b5a2eb458e5dbe4199c3de58dee07e93c6e53befafc5b` |
| `tests/test_review_schema.py` | `461e4b0802fa35d1d47ef7cd66747b8251b0b094f94bccf5bd03749e76674283` |
| `tests/test_review_prompts.py` | `21ad0df3976289fe20fcd5483efd5ee3c5ffd13e6fa7bea5e24c66adcbfdea98` |
| `tests/test_review_llm.py` | `ade5dc67bed985ebf6a8ddc4a7c1dc761f41432d6f833abe06844f26ea04a0c8` |
| `tests/test_review_evidence.py` | `ac53eb196ef0817332b1e08aefab0f7c1bed78e7df6e55e1b0242125848d3e17` |
| `tests/test_review_verdict.py` | `4e116f6aa58340e74fa55d66f866186f5f45626527cf03f23fe69b95215e4118` |
| `tests/test_review_engine.py` | `696bd7fca259f74f8fa1cf4310703767e23d29a133c853fa7a0130fd0b262f37` |
| `.agent/PROGRESS.md` | `cb82b81b21568661e822afa968e820ad9343a19129b5814ba76145860f33fa0d` |

### R3 integration primitives (unchanged)

`bot/review/github.py` and `bot/review/redact.py` were not edited in R4. Their existing R3 hashes
remain the source of truth in the R3 report.

### Report hash convention

`REPORT_HASH` below is SHA-256 of this report with the `REPORT_HASH:` line removed. The final
full-file hash is recorded in the author self-review / handoff.

REPORT_HASH: `bd893e46caddf208b9ec1f90f7431342171a4a90c03cc7bb45d2f462550d30a5`
