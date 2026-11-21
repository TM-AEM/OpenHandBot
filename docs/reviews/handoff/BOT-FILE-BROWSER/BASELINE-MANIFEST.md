# Baseline Manifest — OHB2 Bot File Browser Handoff

**Verified on:** 2026-11-21
**Repository audited:** `/workspace/project/OpenHandBot`
**Package:** `docs/reviews/handoff/BOT-FILE-BROWSER/`

---

## 1. Verified repository identity

| Field | Verified value |
|---|---|
| Branch | `openhands-workspace-11yyMvqKPjTrIZt1RRpWq9` |
| HEAD | `30dfa0d6432cdb8f7787edde38f48fb482b6ced6` |
| HEAD subject | `feat: sync complete OHB2 WP-05/WP-06/WP-07 remediation work to main` |
| `origin/main` | `30dfa0d6432cdb8f7787edde38f48fb482b6ced6` |
| `main` | `30dfa0d` (tracking `origin/main`) |
| Working tree | Not clean: pre-existing uncommitted work present |
| Implementation commit status | Uncommitted; HEAD not advanced |

The reported baseline (`30dfa0d`) was confirmed against the live repository. The branch was not modified,
committed, pushed, merged, or deployed during packaging.

## 2. Provenance classification of working-tree entries

| Path | Classification | Evidence / reason |
|---|---|---|
| `bot/file_browser.py` | **Current task** (new) | New pure tree/pagination/cache module created for this implementation. |
| `bot/handlers.py` | **Current task + DEF-011-A Option B** | All hunks except the last `_attachment_service` hunk are current task; the last hunk is DEF-011-A Option B. The current-task patch excludes that hunk at hunk level. |
| `bot/keyboards.py` | **Current task** | `files_cb`, `files_only_menu`, `browser_menu`; no other task touches this file. |
| `bot/app.py` | **Current task** | Registration of `fbo/fbd/fbp/fbu/fbr/fbf/fbx/fbb`; no other task touches this file. |
| `tests/test_file_browser.py` | **Current task** (new) | Pure module tests. |
| `tests/test_bot_file_browser.py` | **Current task** (new) | Handler, binary UX, and DEF-010 tests. |
| `tests/test_b06_file_routing.py` | **Current task** | Only the binary/too-large message assertions changed. |
| `docs/audits/OHB2-BOT-FILE-BROWSER-AND-BINARY-UX-IMPLEMENTATION-REPORT.md` | **Current task** (new) | Implementation report. |
| `bot/attachments.py` | **DEF-011-A Option B** | Entire diff is Option B limits; excluded. |
| `tests/test_doc_code_parity.py` | **F-03 / T-5** | F-03 documentation-parity additions and the pre-existing T-5 test; excluded. |
| `docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md` | **F-03** | F-03 stale-reference correction; excluded. |
| `tests/test_def011_a_option_b_limits.py` | **DEF-011-A** | Option B tests; excluded. |
| `docs/audits/OHB2-WP07-DEF011-A-DIAGNOSIS-AND-DECISION-BRIEF.md` | **DEF-011-A** | Unrelated prior work; excluded. |
| `docs/audits/OHB2-WP07-DEF011-A-IMPLEMENTATION-REPORT.md` | **DEF-011-A** | Unrelated prior work; excluded. |
| `docs/audits/OHB2-WP07-DEF011-F03-STALE-REFERENCE-CORRECTION-REPORT.md` | **F-03** | Unrelated prior work; excluded. |
| `docs/reviews/DEF011-A-REVIEW-HANDOFF-PACKAGE-REPORT.md` | **DEF-011-A** | Unrelated prior work; excluded. |
| `docs/reviews/OHB2-WP07-DEF011-A-INDEPENDENT-REVIEW-REPORT.md` | **DEF-011-A** | Unrelated prior work; excluded. |
| `docs/reviews/OHB2-WP07-DEF011-A-INDEPENDENT-REVIEW-RETRY-REPORT.md` | **DEF-011-A** | Unrelated prior work; excluded. |
| `docs/reviews/OHB2-WP07-DEF011-F03-GENUINELY-INDEPENDENT-REVIEW-REPORT.md` | **F-03** | Unrelated prior work; excluded. |
| `docs/reviews/handoff/` (existing contents) | **DEF-011-A handoff** | Prior handoff package; excluded. The new `BOT-FILE-BROWSER/` subdirectory is this package. |
| `DEF011-A-OPTION-B-REVIEW-HANDOFF.zip` | **DEF-011-A** | Prior handoff ZIP; excluded. |
| `.openhands/`, `.pytest_cache/`, `__pycache__/`, `bot/web/__pycache__/`, etc. | **Ignored environment/cache** | Not part of the candidate; excluded. |

## 3. Base (HEAD `30dfa0d`) identities for candidate paths

| Path | Base SHA-256 | Base bytes | Exists at base? |
|---|---|---|---|
| `bot/handlers.py` | `40dd8902595c1a63875f8c9d37d4fed4a454be15e1390e5386dcfa9bce058014` | 182968 | Yes |
| `bot/keyboards.py` | `54c97cedf6c4ba6d8d7a72caf63e74df15666c6a8121a99fb3d20f6f2f223131` | 11431 | Yes |
| `bot/app.py` | `fb3d5038fbe220ec736feb14b7ec7d1b1f396f31472ddcbc789f182695143e24` | 25081 | Yes |
| `tests/test_b06_file_routing.py` | `9a7aed72f476e27bc6bf8b7ea31377e40dfe3a343c5c46666419e4a4d9f6b560` | 13569 | Yes |
| `bot/file_browser.py` | — | — | **No (new)** |
| `tests/test_file_browser.py` | — | — | **No (new)** |
| `tests/test_bot_file_browser.py` | — | — | **No (new)** |
| `docs/audits/OHB2-BOT-FILE-BROWSER-AND-BINARY-UX-IMPLEMENTATION-REPORT.md` | — | — | **No (new)** |

The base revision is `30dfa0d6432cdb8f7787edde38f48fb482b6ced6`. The candidate patch is generated against
this revision.

## 4. Implementation-workspace identities for candidate paths

| Path | Workspace SHA-256 | Workspace bytes | Note |
|---|---|---|---|
| `bot/file_browser.py` | `428d977e5a0bc1606e285f1094659489b46d4944a4cf4ee32d85b0d5129ac5c8` | 10168 | Same as candidate. |
| `bot/handlers.py` | `f1276068fb8ff85a4f0aaea0c00ee399626dc1671b73a5552630413dd016ec6a` | 198410 | **Includes excluded DEF-011-A Option B hunk.** Candidate hash differs: `1603e6fc…`. |
| `bot/keyboards.py` | `aedc25cf52f559fc5299b68954d61d47b4ba87713fd49f7a992eeec8bbfa6b77` | 13710 | Same as candidate. |
| `bot/app.py` | `3d606b4ef5d5994c2d6a025917f46ea282f5307a950bb3a304d6b1c998a9a438` | 25984 | Same as candidate. |
| `tests/test_file_browser.py` | `92c1684e26efef313714ab65928e97ea258fb79f252b8368c1d60af2f9c67b0a` | 5185 | Same as candidate. |
| `tests/test_bot_file_browser.py` | `1010e481a62024e6ae7e83903255ae0db59482c3f539e2659b71b2db9cd6099c` | 16115 | Same as candidate. |
| `tests/test_b06_file_routing.py` | `8ed216317d28e37bca5dab3947b3fa05c4abce4762d642b4a5e35efae319b3e1` | 13679 | Same as candidate. |
| `docs/audits/OHB2-BOT-FILE-BROWSER-AND-BINARY-UX-IMPLEMENTATION-REPORT.md` | `c7ced294834a013db1108fe962d7372184e028952d6030d739dc094b16705c9c` | 15361 | Same as candidate. |

**Overlap conclusion:** only `bot/handlers.py` overlaps with unrelated work. The workspace file contains
the current-task changes plus the last DEF-011-A Option B hunk. The candidate patch contains only the
current-task hunks. Applying the candidate to the base revision produces
`1603e6fc55b69a72247dc8856f73caadece99ef2aae26aaca80cc2e6961aa050` (197783 bytes); the only difference
from the workspace file is the excluded Option B hunk. No current-task change is omitted.

## 5. Excluded overlapping changes — identities

| Path | Workspace SHA-256 | Bytes | Classification |
|---|---|---|---|
| `bot/attachments.py` | `d31320afb4e39dd8cbbd09df45e6a755b24eeca149a115c7ff516a2ec4eb61d4` | 100128 | DEF-011-A Option B |
| `docs/reviews/OHB2-WP07-BATCH04-DEF011-F01-IMPLEMENTATION-REPORT.md` | `81333b5831b63a12dbfd9f0d1b681855ae46bae999901ebd0434616a97827ce3` | 17777 | F-03 |
| `tests/test_doc_code_parity.py` | `58766550853a77c1aca97d01e45e71738e8e518cfe1b534a70cbb2ae223b2603` | 17153 | F-03 / T-5 |
| `tests/test_def011_a_option_b_limits.py` | `63a0033a4e5440ac0e762b77cc58f50da9aa09afa849e97c0d745c4cb795fb13` | 17317 | DEF-011-A |

These files are **not** in `candidate.patch` and **not** in the package (except as prose references).

## 6. Supporting report identities

| Supporting copy | SHA-256 | Bytes | Original |
|---|---|---|---|
| `supporting/OHB2-BOT-FILE-DELIVERY-AND-BROWSER-DIAGNOSIS.md` | `a84495ed17604e9d1ca95a9161d8e61d1116e62ff620c6032a064967e069f995` | 27368 | `docs/audits/OHB2-BOT-FILE-DELIVERY-AND-BROWSER-DIAGNOSIS.md` (same hash) |
| `supporting/OHB2-BOT-FILE-BROWSER-AND-BINARY-UX-IMPLEMENTATION-REPORT.md` | `c7ced294834a013db1108fe962d7372184e028952d6030d739dc094b16705c9c` | 15361 | `docs/audits/OHB2-BOT-FILE-BROWSER-AND-BINARY-UX-IMPLEMENTATION-REPORT.md` (same hash) |

The originals were copied byte-for-byte and were not modified.

## 7. Prerequisite assessment

**No prerequisite patches are required.**

- The candidate touches only the file-browser/binary-UX surface and its tests/report.
- It does not import or depend on DEF-011-A Option B, F-03, or T-5 code/tests.
- The only overlap is the `bot/handlers.py` `_attachment_service` hunk, which is unrelated and excluded.
- The reconstructed candidate (base + `candidate.patch`, without Option B/F-03/T-5) passed 61 focused
  tests and 3486 full-suite tests during packaging. This demonstrates that no excluded work is a runtime
  or test dependency.

If a reviewer wants to reproduce the implementation workspace *including* the unrelated DEF-011-A Option B
work, that work must be obtained separately from its own handoff package; it is not part of this candidate.

## 8. Ignored and untracked artifacts not packaged

`git status --ignored --short` showed `.openhands/`, `.pytest_cache/`, `__pycache__/`,
`automation/autopush/__pycache__/`, `bot/__pycache__/`, `bot/web/__pycache__/`, and `tests/__pycache__/`.
None is packaged. No `.env`, secret, credential, or environment file is included.
