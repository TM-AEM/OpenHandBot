# BOT-FILE-BROWSER-REMEDIATION — isolated review handoff

**Task:** `OHB2-BOT-FILE-BROWSER-AND-BINARY-UX-REMEDIATION`
**Base commit:** `ea4a484815aab17c9456eaa6157e3f06475edcf4`
**Handoff status:** ready for a genuinely separate reviewer
**Independent review status:** `INDEPENDENCE_NOT_ESTABLISHED`

## What this handoff contains

This is a **test-only remediation delta** on top of `ea4a484`. The browser/binary-UX implementation itself
is already in the base commit and in the earlier
`docs/reviews/handoff/BOT-FILE-BROWSER/` package (base `30dfa0d`). This handoff exists to let a separate
reviewer verify the remediation changes without any pre-existing DEF-011-A Option B, F-03/T-5, Mini App,
or unrelated working-tree content.

Included:

- `candidate.patch` — only `tests/test_file_browser.py` and `tests/test_bot_file_browser.py`.
- `CANDIDATE-MANIFEST.md` — base commit, changed files, before/after hashes, exclusions, expected results.
- `SHA256SUMS` — SHA-256 checksums for the handoff files.
- `REVIEW-INSTRUCTIONS.md` — read-only review procedure and commands.
- `supporting/OHB2-BOT-FILE-BROWSER-AND-BINARY-UX-REMEDIATION-REPORT.md` — the implementation/remediation
  report with the full evidence.

> **Patch format note:** `candidate.patch` is a unified diff. A line that appears to contain only a single
> space is a context line and must be preserved byte-for-byte. Do not strip it.

## Explicit exclusions

- No production source change (`bot/`, `automation/`, `tools/`, `main.py` are untouched).
- No Mini App change (`bot/web/` is untouched).
- No DEF-011-A Option B change (`bot/attachments.py`, `bot/handlers.py::_attachment_service`, and
  `tests/test_def011_a_option_b_limits.py` are untouched).
- No F-03/T-5 change (`tests/test_doc_code_parity.py` and the F-03 reports are untouched).
- No change to the existing `docs/reviews/handoff/BOT-FILE-BROWSER/` package.
- No commit, push, PR, merge, deployment, or Autopush activation.

## Finding of this remediation

The naming/identifier defects reported from the transmitted chat text are **not present** in the live source
or in the packaged `candidate.patch`. They were manual transcription errors in the chat export. The live
source uses `conversation_id`, `entries`, `page_entries`, `page_count`, `clamp_page`, and `conversation_for`.
Three regression tests were added to lock the canonical API, evicted-state safety, and confirmed-deletion
cache invalidation.

A separate reviewer should verify this from the patch and the live source, not from the chat transcript.
