"""R3: deterministic redaction, path exclusion, bounds, and diff boundaries."""
import pytest

from bot.review.redact import (
    STATUS_BLOCKED,
    STATUS_OK,
    STATUS_OVERSIZED,
    STATUS_TRUNCATED,
    redact_diff,
    redact_text,
)

SECRETS = [
    "ghp_FAKE_REVIEW_TOKEN_1234567890",
    "github_pat_FAKE_REVIEW_TOKEN_1234567890",
    "sk-reviewer-test-SENTINEL-123456",
    "AKIAIOSFODNN7EXAMPLE",
    "xoxb-1234567890-abcdefghij",
    "sk_live_1234567890abcdefghij",
    "AIza" + "a" * 35,
    "eyJ" + "a" * 12 + "." + "b" * 12 + "." + "c" * 12,
    "-----BEGIN RSA PRIVATE KEY-----\nsecret\n-----END RSA PRIVATE KEY-----",
]


def _diff(old: str, new: str, body: str = "@@ -1 +1 @@\n-old\n+new\n") -> str:
    return (
        f"diff --git a/{old} b/{new}\n"
        f"--- a/{old}\n"
        f"+++ b/{new}\n"
        f"{body}"
    )


def _quoted_diff(path: str, body: str = "@@ -1 +1 @@\n-old\n+new\n") -> str:
    return (
        f'diff --git "a/{path}" "b/{path}"\n'
        f'--- "a/{path}"\n'
        f'+++ "b/{path}"\n'
        f"{body}"
    )


@pytest.mark.parametrize("secret", SECRETS)
def test_common_secret_formats_are_redacted(secret):
    result = redact_text(f"prefix {secret} suffix")
    assert result.status == STATUS_OK
    assert secret not in result.text
    assert "[REDACTED:" in result.text
    assert all(secret not in key for key, _ in result.redactions)


def test_authorization_bearer_and_connection_credentials_are_redacted():
    text = (
        "Authorization: Bearer abcdefghijklmnop\n"
        "proxy Authorization: Basic dXNlcjpwYXNz\n"
        "url=https://user:password@example.test/path\n"
        "Bearer standalone-token-123456\n"
    )
    result = redact_text(text)
    assert result.status == STATUS_OK
    assert "abcdefghijklmnop" not in result.text
    assert "dXNlcjpwYXNz" not in result.text
    assert "user:password" not in result.text
    assert "standalone-token-123456" not in result.text
    assert result.text.count("[REDACTED:") >= 4


def test_generic_assignments_and_query_parameters_are_redacted():
    text = (
        'password = "hunter2-long"\n'
        "API_KEY=abcdef123456\n"
        "token=supersecret12345\n"
        "https://example.test/x?token=querysecret123&ok=1\n"
    )
    result = redact_text(text)
    assert result.status == STATUS_OK
    for value in ("hunter2-long", "abcdef123456", "supersecret12345", "querysecret123"):
        assert value not in result.text
    assert "token=[REDACTED:generic_secret]" in result.text


def test_git_shas_are_not_treated_as_secrets():
    sha = "a" * 40
    result = redact_text(f"head={sha}\n")
    assert result.status == STATUS_OK
    assert sha in result.text
    assert result.redactions == ()


def test_text_oversized_is_explicit_not_silently_truncated():
    result = redact_text("x" * 20, max_input_chars=10)
    assert result.status == STATUS_OVERSIZED
    assert result.text == ""
    assert result.truncated is True
    assert result.blocked_reason == "input_limit"


def test_text_output_truncation_is_explicit_and_bounded():
    result = redact_text("line1\nline2\nline3\n", max_output_chars=12)
    assert result.status == STATUS_TRUNCATED
    assert result.truncated is True
    assert len(result.text) <= 12
    assert result.text.endswith("\n")


def test_diff_excluded_paths_are_omitted():
    diff = (
        _diff("docs/secret.md", "docs/secret.md", "@@\n-SECRET-DOC\n+SECRET-DOC2\n")
        + _diff("notes.patch", "notes.patch")
        + _diff("bundle.zip", "bundle.zip")
        + _diff("package-lock.json", "package-lock.json")
        + _diff("src/app.py", "src/app.py")
    )
    result = redact_diff(diff)
    assert result.status == STATUS_OK
    assert set(result.excluded_paths) == {
        "docs/secret.md",
        "notes.patch",
        "bundle.zip",
        "package-lock.json",
    }
    assert "SECRET-DOC" not in result.text
    assert "diff --git a/src/app.py b/src/app.py" in result.text
    statuses = {f.path: f.status for f in result.files}
    assert statuses["docs/secret.md"] == "excluded"
    assert statuses["src/app.py"] == "included"


@pytest.mark.parametrize(
    "path",
    [
        "./docs/secret.md",
        "docs%2Fsecret.md",
        "docs//secret.md",
        "docs\\secret.md",
        "DOCS/secret.md",
        "sub/package-lock.json",
        "UPPER.PATCH",
        "UPPER.ZIP",
    ],
)
def test_alternate_excluded_path_representations_are_still_excluded(path):
    result = redact_diff(_diff(path, path))
    assert result.status == STATUS_OK
    assert result.text == ""
    assert len(result.excluded_paths) == 1


def test_quoted_excluded_path_is_excluded():
    result = redact_diff(_quoted_diff("docs/secret file.md"))
    assert result.status == STATUS_OK
    assert result.text == ""
    assert result.excluded_paths == ("docs/secret file.md",)


@pytest.mark.parametrize(
    "path",
    [
        "../docs/secret.md",
        "a/../docs/secret.md",
        "%2e%2e/docs/secret.md",
        "%252e%252e/docs/secret.md",
    ],
)
def test_path_traversal_or_absolute_paths_fail_closed(path):
    result = redact_diff(_diff(path, path))
    assert result.status == STATUS_BLOCKED
    assert result.text == ""
    assert result.blocked_reason == "invalid_path"


def test_absolute_path_without_diff_prefix_fails_closed():
    diff = (
        "diff --git /docs/secret.md /docs/secret.md\n"
        "--- /docs/secret.md\n"
        "+++ /docs/secret.md\n"
        "@@ -1 +1 @@\n-old\n+new\n"
    )
    result = redact_diff(diff)
    assert result.status == STATUS_BLOCKED
    assert result.blocked_reason == "invalid_path"


def test_rename_from_excluded_old_side_cannot_reenter():
    diff = (
        "diff --git a/docs/secret.md b/src/secret.md\n"
        "similarity index 100%\n"
        "rename from docs/secret.md\n"
        "rename to src/secret.md\n"
    )
    result = redact_diff(diff)
    assert result.status == STATUS_OK
    assert result.text == ""
    assert result.excluded_paths == ("docs/secret.md",)


def test_binary_diff_is_excluded_without_content():
    diff = (
        "diff --git a/image.bin b/image.bin\n"
        "index 1111111..2222222 100644\n"
        "Binary files a/image.bin and b/image.bin differ\n"
    )
    result = redact_diff(diff)
    assert result.status == STATUS_OK
    assert result.text == ""
    assert result.files[0].status == "binary"
    assert result.files[0].emitted is False


def test_binary_with_traversal_path_blocks():
    diff = (
        "diff --git a/../docs/x.bin b/../docs/x.bin\n"
        "Binary files a/../docs/x.bin and b/../docs/x.bin differ\n"
    )
    result = redact_diff(diff)
    assert result.status == STATUS_BLOCKED
    assert result.blocked_reason == "invalid_path"


def test_missing_path_blocks_instead_of_silently_passing():
    result = redact_diff("not a unified diff\n")
    assert result.status == STATUS_BLOCKED
    assert result.blocked_reason == "missing_path"
    assert result.text == ""


def test_diff_unquoted_assignment_is_redacted():
    diff = _diff(
        "src/app.py",
        "src/app.py",
        "@@ -1 +1 @@\n+API_KEY=abcdef123456\n+password=hunter2-long\n",
    )
    result = redact_diff(diff)
    assert result.status == STATUS_OK
    assert "abcdef123456" not in result.text
    assert "hunter2-long" not in result.text
    assert result.text.count("[REDACTED:generic_secret]") == 2


def test_diff_secrets_are_redacted_and_boundaries_preserved():
    diff = _diff(
        "src/app.py",
        "src/app.py",
        "@@ -1,2 +1,2 @@\n"
        '-token = "OLD_SECRET_12345"\n'
        '+token = "NEW_SECRET_12345"\n'
        " password = 'hunter2-long'\n",
    )
    result = redact_diff(diff)
    assert result.status == STATUS_OK
    assert "OLD_SECRET_12345" not in result.text
    assert "NEW_SECRET_12345" not in result.text
    assert "hunter2-long" not in result.text
    assert "diff --git a/src/app.py b/src/app.py" in result.text
    assert "@@ -1,2 +1,2 @@" in result.text
    assert "[REDACTED:generic_secret]" in result.text


def test_excluded_file_secret_never_appears_in_output():
    diff = _diff(
        "docs/secret.md",
        "docs/secret.md",
        "@@ -1 +1 @@\n+ghp_FAKE_REVIEW_TOKEN_1234567890\n",
    )
    result = redact_diff(diff)
    assert result.status == STATUS_OK
    assert result.text == ""
    assert "ghp_FAKE_REVIEW_TOKEN_1234567890" not in result.text


def test_secret_in_path_is_redacted_from_result_metadata():
    secret = "ghp_FAKE_REVIEW_TOKEN_1234567890"
    result = redact_diff(_diff(f"docs/{secret}.md", f"docs/{secret}.md"))
    assert result.status == STATUS_OK
    assert result.text == ""
    assert secret not in str(result)
    assert secret not in repr(result)


def test_diff_output_limit_omits_whole_sections_and_marks_truncated():
    first = _diff("src/a.py", "src/a.py")
    second = _diff("src/b.py", "src/b.py")
    result = redact_diff(first + second, max_output_chars=len(first))
    assert result.status == STATUS_TRUNCATED
    assert result.truncated is True
    assert result.text == first
    assert result.text.startswith("diff --git ")
    statuses = {f.path: f.status for f in result.files}
    assert statuses["src/a.py"] == "included"
    assert statuses["src/b.py"] == "omitted_limit"


def test_diff_first_section_over_limit_is_explicit():
    first = _diff("src/a.py", "src/a.py")
    result = redact_diff(first, max_output_chars=10)
    assert result.status == STATUS_TRUNCATED
    assert result.text == ""
    assert result.files[0].status == "omitted_limit"


def test_diff_oversized_input_is_explicit():
    result = redact_diff(_diff("src/a.py", "src/a.py"), max_input_chars=10)
    assert result.status == STATUS_OVERSIZED
    assert result.text == ""
    assert result.blocked_reason == "input_limit"


def test_empty_diff_and_text_are_safe():
    assert redact_diff("").status == STATUS_OK
    assert redact_text("").status == STATUS_OK


def test_redaction_result_never_contains_original_secret_in_counts():
    secret = "ghp_FAKE_REVIEW_TOKEN_1234567890"
    result = redact_text(f"token={secret}\n")
    assert secret not in str(result)
    assert result.redactions == (("github_token", 1),)
