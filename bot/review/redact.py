"""Deterministic, fail-closed redaction for future review payloads (R3).

This module does not call a model and does not build prompts. It sanitizes text
and unified diffs, removes common secret formats, enforces a strict path
denylist, rejects binary/malformed/traversal paths, and reports truncation
explicitly instead of silently dropping content.
"""
from __future__ import annotations

import json
import re
import shlex
import unicodedata
from dataclasses import dataclass
from urllib.parse import unquote

DEFAULT_MAX_INPUT_CHARS = 120_000
DEFAULT_MAX_OUTPUT_CHARS = 120_000
MAX_INPUT_CHARS_LIMIT = 1_000_000
MAX_OUTPUT_CHARS_LIMIT = 1_000_000
MAX_PATH_CHARS = 512

EXCLUDED_DIRS = ("docs",)
EXCLUDED_SUFFIXES = (".patch", ".zip")
EXCLUDED_BASENAMES = ("package-lock.json",)

STATUS_OK = "ok"
STATUS_TRUNCATED = "truncated"
STATUS_OVERSIZED = "oversized"
STATUS_BLOCKED = "blocked"

_FILE_INCLUDED = "included"
_FILE_EXCLUDED = "excluded"
_FILE_BINARY = "binary"
_FILE_INVALID = "invalid"
_FILE_OMITTED = "omitted_limit"


@dataclass(frozen=True)
class RedactedFile:
    path: str | None
    status: str  # included | excluded | binary | invalid | omitted_limit
    emitted: bool
    reason: str | None = None
    redactions: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True)
class RedactionResult:
    status: str  # ok | truncated | oversized | blocked
    text: str
    input_chars: int
    output_chars: int
    truncated: bool
    blocked_reason: str | None
    excluded_paths: tuple[str, ...]
    redactions: tuple[tuple[str, int], ...]
    files: tuple[RedactedFile, ...]

    @property
    def safe(self) -> bool:
        return self.status in {STATUS_OK, STATUS_TRUNCATED}


class _InvalidPath(ValueError):
    pass


# Keep placeholders out of every generic pattern so a re-scan cannot match them.
_PLACEHOLDER_GUARD = r"(?!\[REDACTED:)"

_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "private_key",
        re.compile(
            r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
        "[REDACTED:private_key]",
    ),
    (
        "authorization_header",
        re.compile(
            r"(?im)^([ \t]*authorization[ \t]*:[ \t]*)(?:bearer|token|basic)[ \t]+[^\s\r\n]+"
        ),
        r"\1[REDACTED:authorization]",
    ),
    (
        "authorization_header",
        re.compile(r"(?i)\bAuthorization\s*:\s*(?:Bearer|token|Basic)\s+[^\s,;]+"),
        "Authorization: [REDACTED:authorization]",
    ),
    (
        "bearer_token",
        re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"),
        "Bearer [REDACTED:bearer]",
    ),
    (
        "connection_credentials",
        re.compile(
            r"(?i)\b([a-z][a-z0-9+.-]*://)(?!\[REDACTED:)([^/\s:@]+):([^@\s/]+)@"
        ),
        r"\1[REDACTED:connection_credentials]@",
    ),
    (
        "github_token",
        re.compile(r"(?i)\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
        "[REDACTED:github_token]",
    ),
    (
        "api_key",
        re.compile(r"(?i)\bsk-[A-Za-z0-9_-]{16,}\b"),
        "[REDACTED:api_key]",
    ),
    (
        "aws_access_key",
        re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
        "[REDACTED:aws_access_key]",
    ),
    (
        "slack_token",
        re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
        "[REDACTED:slack_token]",
    ),
    (
        "stripe_key",
        re.compile(r"\b[sr]k_(?:live|test)_[A-Za-z0-9]{16,}\b"),
        "[REDACTED:stripe_key]",
    ),
    (
        "google_api_key",
        re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
        "[REDACTED:google_api_key]",
    ),
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
        "[REDACTED:jwt]",
    ),
    (
        "generic_secret",
        re.compile(
            r"(?im)^([+\- ]?[ \t]*(?:export[ \t]+)?[A-Za-z0-9_.-]*(?:api[_-]?key|access[_-]?key|"
            r"secret[_-]?key|client[_-]?secret|token|secret|password|passwd|pwd)"
            r"[A-Za-z0-9_.-]*[ \t]*[:=][ \t]*)([\"'])"
            + _PLACEHOLDER_GUARD
            + r"[^\r\n]*?\2[ \t]*$"
        ),
        r"\1\2[REDACTED:generic_secret]\2",
    ),
    (
        "generic_secret",
        re.compile(
            r"(?im)^([+\- ]?[ \t]*(?:export[ \t]+)?[A-Za-z0-9_.-]*(?:api[_-]?key|access[_-]?key|"
            r"secret[_-]?key|client[_-]?secret|token|secret|password|passwd|pwd)"
            r"[A-Za-z0-9_.-]*[ \t]*[:=][ \t]*)"
            + _PLACEHOLDER_GUARD
            + r"(?!(?:str|int|bool|float|None|bytes|dict|list|object)\b)([^\s#]+)"
        ),
        r"\1[REDACTED:generic_secret]",
    ),
    (
        "generic_secret",
        re.compile(
            r"(?i)([\"']?(?:api[_-]?key|access[_-]?key|secret[_-]?key|client[_-]?secret|"
            r"token|secret|password|passwd|pwd)[\"']?\s*[:=]\s*)([\"'])"
            + _PLACEHOLDER_GUARD
            + r"([^\"'\r\n]*?)\2"
        ),
        r"\1\2[REDACTED:generic_secret]\2",
    ),
    (
        "generic_secret",
        re.compile(
            r"(?i)([?&](?:token|secret|api[_-]?key|access[_-]?key|password)=)"
            + _PLACEHOLDER_GUARD
            + r"[^&#\s]+"
        ),
        r"\1[REDACTED:generic_secret]",
    ),
)

_RESCAN_PATTERNS = tuple(pattern for _, pattern, _ in _SECRET_PATTERNS)


def redact_text(
    text: str,
    *,
    max_input_chars: int = DEFAULT_MAX_INPUT_CHARS,
    max_output_chars: int | None = None,
) -> RedactionResult:
    """Redact a generic text payload. Oversized input is explicit, not truncated."""
    if not isinstance(text, str):
        raise ValueError("text لازم يكون نصًا")
    input_limit = _limit(max_input_chars, MAX_INPUT_CHARS_LIMIT, "max_input_chars")
    output_limit = _limit(
        max_output_chars if max_output_chars is not None else input_limit,
        MAX_OUTPUT_CHARS_LIMIT,
        "max_output_chars",
    )
    input_chars = len(text)
    if input_chars > input_limit:
        return _oversized_result(input_chars)

    redacted, counts = _redact_secrets(text)
    if _contains_secret(redacted):
        return _blocked_result("rescan_found_secret", input_chars, counts)

    truncated = False
    if len(redacted) > output_limit:
        redacted = _truncate_text(redacted, output_limit)
        truncated = True
    return RedactionResult(
        status=STATUS_TRUNCATED if truncated else STATUS_OK,
        text=redacted,
        input_chars=input_chars,
        output_chars=len(redacted),
        truncated=truncated,
        blocked_reason=None,
        excluded_paths=(),
        redactions=_counts_tuple(counts),
        files=(),
    )


def redact_diff(
    diff_text: str,
    *,
    max_input_chars: int = DEFAULT_MAX_INPUT_CHARS,
    max_output_chars: int | None = None,
) -> RedactionResult:
    """Redact a unified diff, excluding denied paths and preserving diff boundaries."""
    if not isinstance(diff_text, str):
        raise ValueError("diff_text لازم يكون نصًا")
    input_limit = _limit(max_input_chars, MAX_INPUT_CHARS_LIMIT, "max_input_chars")
    output_limit = _limit(
        max_output_chars if max_output_chars is not None else input_limit,
        MAX_OUTPUT_CHARS_LIMIT,
        "max_output_chars",
    )
    input_chars = len(diff_text)
    if input_chars > input_limit:
        return _oversized_result(input_chars)
    if not diff_text:
        return RedactionResult(
            STATUS_OK, "", 0, 0, False, None, (), (), ()
        )

    sections = _split_sections(diff_text)
    prepared: list[tuple[str, RedactedFile]] = []
    excluded_paths: list[str] = []
    total_counts: dict[str, int] = {}

    for section in sections:
        parsed = _section_paths(section)
        if parsed.invalid_reason:
            return _blocked_result(parsed.invalid_reason, input_chars, total_counts)
        safe_primary = _safe_path(parsed.primary)
        if parsed.excluded:
            excluded_paths.extend(_safe_path(path) for path in parsed.excluded_paths)
            prepared.append(
                (
                    "",
                    RedactedFile(
                        path=safe_primary,
                        status=_FILE_EXCLUDED,
                        emitted=False,
                        reason="excluded_path",
                    ),
                )
            )
            continue
        if parsed.binary:
            prepared.append(
                (
                    "",
                    RedactedFile(
                        path=safe_primary,
                        status=_FILE_BINARY,
                        emitted=False,
                        reason="binary",
                    ),
                )
            )
            continue
        if parsed.primary is None:
            return _blocked_result("missing_path", input_chars, total_counts)
        redacted, counts = _redact_secrets(section)
        if _contains_secret(redacted):
            return _blocked_result("rescan_found_secret", input_chars, total_counts)
        for key, value in counts.items():
            total_counts[key] = total_counts.get(key, 0) + value
        prepared.append(
            (
                redacted,
                RedactedFile(
                    path=safe_primary,
                    status=_FILE_INCLUDED,
                    emitted=False,
                    redactions=_counts_tuple(counts),
                ),
            )
        )

    output_parts: list[str] = []
    output_chars = 0
    truncated = False
    files: list[RedactedFile] = []
    for text, file_info in prepared:
        if file_info.status == _FILE_INCLUDED and not truncated:
            if output_chars + len(text) <= output_limit:
                output_parts.append(text)
                output_chars += len(text)
                files.append(
                    RedactedFile(
                        path=file_info.path,
                        status=_FILE_INCLUDED,
                        emitted=True,
                        reason=None,
                        redactions=file_info.redactions,
                    )
                )
                continue
            truncated = True
            files.append(
                RedactedFile(
                    path=file_info.path,
                    status=_FILE_OMITTED,
                    emitted=False,
                    reason="output_limit",
                    redactions=file_info.redactions,
                )
            )
            continue
        if file_info.status == _FILE_INCLUDED:
            files.append(
                RedactedFile(
                    path=file_info.path,
                    status=_FILE_OMITTED,
                    emitted=False,
                    reason="output_limit",
                    redactions=file_info.redactions,
                )
            )
        else:
            files.append(file_info)

    output = "".join(output_parts)
    if _contains_secret(output):
        return _blocked_result("rescan_found_secret", input_chars, total_counts)
    return RedactionResult(
        status=STATUS_TRUNCATED if truncated else STATUS_OK,
        text=output,
        input_chars=input_chars,
        output_chars=len(output),
        truncated=truncated,
        blocked_reason=None,
        excluded_paths=tuple(dict.fromkeys(excluded_paths)),
        redactions=_counts_tuple(total_counts),
        files=tuple(files),
    )


@dataclass(frozen=True)
class _SectionPaths:
    primary: str | None
    excluded: bool
    binary: bool
    invalid_reason: str | None
    excluded_paths: tuple[str, ...] = ()


def _split_sections(diff_text: str) -> list[str]:
    lines = diff_text.splitlines(keepends=True)
    sections: list[str] = []
    current: list[str] = []
    for line in lines:
        if line.startswith("diff --git "):
            if current:
                sections.append("".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("".join(current))
    return sections or [diff_text]


def _section_paths(section: str) -> _SectionPaths:
    old: str | None = None
    new: str | None = None
    binary = "\x00" in section or "GIT binary patch" in section
    for line in section.splitlines():
        if line.startswith("diff --git "):
            pair = _parse_diff_git_paths(line[len("diff --git ") :])
            if pair is not None:
                old, new = pair
        elif line.startswith("--- "):
            old = _header_path(line[4:])
        elif line.startswith("+++ "):
            new = _header_path(line[4:])
        elif line.startswith("rename from "):
            old = _strip_quotes(line[len("rename from ") :].strip())
        elif line.startswith("rename to "):
            new = _strip_quotes(line[len("rename to ") :].strip())
        elif line.startswith("Binary files ") and line.rstrip().endswith(" differ"):
            binary = True
            match = re.match(r"Binary files (.+) and (.+) differ$", line.rstrip())
            if match:
                old, new = match.group(1), match.group(2)
        elif line.startswith("literal "):
            binary = True

    try:
        old_norm = _normalize_path(old) if old is not None else None
        new_norm = _normalize_path(new) if new is not None else None
    except _InvalidPath:
        return _SectionPaths(None, False, False, "invalid_path")
    candidates = [path for path in (old_norm, new_norm) if path]
    if not candidates:
        return _SectionPaths(None, False, binary, None if binary else "missing_path")
    primary = new_norm or old_norm
    excluded_candidates = tuple(
        dict.fromkeys(path for path in candidates if _is_excluded(path))
    )
    return _SectionPaths(
        primary, bool(excluded_candidates), binary, None, excluded_candidates
    )


def _parse_diff_git_paths(rest: str) -> tuple[str, str] | None:
    try:
        parts = shlex.split(rest)
    except ValueError:
        parts = []
    if len(parts) >= 2:
        return parts[0], parts[1]
    if len(parts) == 1:
        return parts[0], parts[0]
    match = re.match(r"^(\S+)\s+(\S+)$", rest.strip())
    return (match.group(1), match.group(2)) if match else None


def _header_path(raw: str) -> str | None:
    value = raw.split("\t", 1)[0].strip()
    if value == "/dev/null":
        return None
    return _strip_quotes(value) or None


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        if value[0] == '"':
            try:
                parsed = json.loads(value)
                if isinstance(parsed, str):
                    return parsed
            except ValueError:
                pass
        return value[1:-1]
    return value


def _normalize_path(raw: str) -> str:
    value = _strip_quotes(str(raw).strip())
    if not value:
        raise _InvalidPath()
    value = unicodedata.normalize("NFKC", value)
    value = value.replace("\\", "/")
    for _ in range(2):
        value = unquote(value)
    value = value.replace("\\", "/")
    value = re.sub(r"/+", "/", value)
    while value.startswith("./"):
        value = value[2:]
    if value.startswith(("a/", "b/")):
        value = value[2:]
    value = re.sub(r"/+", "/", value)
    if not value or value.startswith("/") or re.match(r"^[A-Za-z]:/", value):
        raise _InvalidPath()
    parts: list[str] = []
    for part in value.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            raise _InvalidPath()
        parts.append(part)
    normalized = "/".join(parts)
    if not normalized or len(normalized) > MAX_PATH_CHARS:
        raise _InvalidPath()
    if any(ord(ch) < 32 for ch in normalized):
        raise _InvalidPath()
    return normalized


def _is_excluded(path: str) -> bool:
    lower = path.casefold()
    if any(lower == directory or lower.startswith(directory + "/") for directory in EXCLUDED_DIRS):
        return True
    if lower.endswith(EXCLUDED_SUFFIXES):
        return True
    return lower.rsplit("/", 1)[-1] in EXCLUDED_BASENAMES


def _safe_path(path: str | None) -> str | None:
    if path is None:
        return None
    redacted, _ = _redact_secrets(path)
    return "[REDACTED:path]" if _contains_secret(redacted) else redacted


def _redact_secrets(text: str) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    out = text
    for name, pattern, replacement in _SECRET_PATTERNS:
        out, count = pattern.subn(replacement, out)
        if count:
            counts[name] = counts.get(name, 0) + count
    return out, counts


def _contains_secret(text: str) -> bool:
    return any(pattern.search(text) for pattern in _RESCAN_PATTERNS)


def _truncate_text(text: str, limit: int) -> str:
    cut = text.rfind("\n", 0, limit)
    return text[: cut + 1] if cut >= 0 else text[:limit]


def _limit(value: int, maximum: int, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= maximum:
        raise ValueError(f"{name} خارج الحدود")
    return value


def _counts_tuple(counts: dict[str, int]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(counts.items()))


def _oversized_result(input_chars: int) -> RedactionResult:
    return RedactionResult(
        status=STATUS_OVERSIZED,
        text="",
        input_chars=input_chars,
        output_chars=0,
        truncated=True,
        blocked_reason="input_limit",
        excluded_paths=(),
        redactions=(),
        files=(),
    )


def _blocked_result(
    reason: str, input_chars: int, counts: dict[str, int]
) -> RedactionResult:
    return RedactionResult(
        status=STATUS_BLOCKED,
        text="",
        input_chars=input_chars,
        output_chars=0,
        truncated=False,
        blocked_reason=reason,
        excluded_paths=(),
        redactions=_counts_tuple(counts),
        files=(),
    )
