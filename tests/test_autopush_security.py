"""OHB2-N10-28B: security regression tests for the autopush automation.

These tests never run the real entry point, never touch the network, and never use a
real credential. They load `automation/autopush/main.py` as an isolated module, inject
a fake subprocess runner, and use a synthetic canary token.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

MOD_PATH = Path(__file__).resolve().parents[1] / "automation" / "autopush" / "main.py"
CANARY = "SYNTHETIC_GITHUB_TOKEN_CANARY_DO_NOT_USE"


@pytest.fixture()
def mod():
    """Load a fresh copy of the autopush module (no import-time side effects)."""
    spec = importlib.util.spec_from_file_location("autopush_main_under_test", MOD_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeProc:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class FakeRunner:
    """Records every invocation and replays queued responses in order."""

    def __init__(self, responses: list[FakeProc] | None = None) -> None:
        self.calls: list[tuple[list[str], dict]] = []
        self.responses = list(responses or [])

    def __call__(self, args, **kwargs):
        self.calls.append((list(args), kwargs))
        if self.responses:
            return self.responses.pop(0)
        return FakeProc()

    def argv_text(self) -> str:
        return " ".join(" ".join(a) for a, _ in self.calls)


def _use_fake(mod, runner: FakeRunner) -> None:
    mod._git_runner = runner


# --------------------------------------------------------------------- credentials


def test_credential_not_embedded_in_remote_url(mod):
    mod._token_cache = CANARY
    url = mod.authed_url("https://github.com/TM-AEM/OpenHandBot.git")
    assert CANARY not in url
    assert "x-access-token" not in url
    assert url == "https://github.com/TM-AEM/OpenHandBot.git"


def test_credential_absent_from_subprocess_argv(mod):
    mod._token_cache = CANARY
    runner = FakeRunner()
    _use_fake(mod, runner)
    # A caller that (incorrectly) passes an authenticated URL must be sanitized.
    mod.git("push", f"https://x-access-token:{CANARY}@github.com/x/y.git", "HEAD:main")
    assert runner.calls, "git was not invoked"
    for args, _ in runner.calls:
        assert all(CANARY not in str(a) for a in args)


def test_non_url_argument_with_credential_is_refused(mod):
    mod._token_cache = CANARY
    runner = FakeRunner()
    _use_fake(mod, runner)
    with pytest.raises(mod.AutopushError):
        mod.git("push", f"credential={CANARY}", "HEAD:main")
    assert not runner.calls, "no git command should run when a credential arg is refused"


def test_credential_absent_from_exception_text(mod):
    mod._token_cache = CANARY
    runner = FakeRunner([FakeProc(returncode=1, stderr=f"auth failed for {CANARY}")])
    _use_fake(mod, runner)
    with pytest.raises(mod.AutopushError) as exc:
        mod.git("fetch", "origin", "main")
    assert CANARY not in str(exc.value)


def test_credential_absent_from_captured_output(mod, capsys):
    mod._token_cache = CANARY
    runner = FakeRunner([FakeProc(returncode=0, stdout=f"leaked {CANARY}", stderr=f"err {CANARY}")])
    _use_fake(mod, runner)
    mod.git("status")
    captured = capsys.readouterr()
    assert CANARY not in captured.out
    assert CANARY not in captured.err
    assert "***" in captured.out


def test_credential_absent_from_callback(mod, monkeypatch):
    captured: dict = {}

    def fake_urlopen(req, timeout=None):
        captured["data"] = req.data
        return None

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("AUTOMATION_CALLBACK_URL", "https://callback.invalid/hook")
    mod._token_cache = CANARY
    mod.fire_callback("FAILED", f"boom {CANARY}")
    body = json.loads(captured["data"].decode())
    assert CANARY not in json.dumps(body)


def test_credential_not_written_to_git_config(mod, tmp_path):
    remote = tmp_path / "remote.git"
    work = tmp_path / "work"
    _real_git(tmp_path, "init", "--bare", str(remote))
    _real_git(tmp_path, "init", "-b", "main", str(work))
    _real_git(work, "config", "user.email", "t@example.com")
    _real_git(work, "config", "user.name", "tester")
    (work / "a.txt").write_text("x\n")
    _real_git(work, "add", "--", "a.txt")
    _real_git(work, "commit", "-m", "init")
    _real_git(work, "remote", "add", "origin", str(remote))

    mod.REPO_DIR = str(work)
    mod._token_cache = CANARY
    # Exercise a real git command through the module (local remote only).
    mod.git("remote", "get-url", "origin")
    config_text = (work / ".git" / "config").read_text()
    assert CANARY not in config_text
    assert "x-access-token" not in config_text
    helper = subprocess.run(
        ["git", "config", "--get", "credential.helper"],
        cwd=str(work), capture_output=True, text=True,
    )
    assert helper.stdout.strip() == ""


def test_failed_credential_operation_does_not_expose_secret(mod, capsys):
    mod._token_cache = CANARY
    runner = FakeRunner([FakeProc(returncode=128, stderr=f"fatal: could not read from {CANARY}")])
    _use_fake(mod, runner)
    with pytest.raises(mod.AutopushError) as exc:
        mod.git("fetch", "origin", "main")
    assert CANARY not in str(exc.value)
    captured = capsys.readouterr()
    assert CANARY not in captured.err


def test_missing_credentials_fail_safe(mod, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("AUTOPUSH_GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(mod, "get_secret", lambda name: None)
    mod._token_cache = None
    assert mod.resolve_token() == mod._PLACEHOLDER_TOKEN
    # The placeholder is not a secret and must not be reported as one.
    env = mod._child_env()
    assert env["GITHUB_TOKEN"] == mod._PLACEHOLDER_TOKEN

    # No credential + nothing ahead => no push attempted, no failure.
    runner = FakeRunner([FakeProc(returncode=0, stdout="0\n"), FakeProc(returncode=0, stdout="0\n")])
    _use_fake(mod, runner)
    assert mod.push_if_ahead() is False
    assert all("push" not in a for a, _ in runner.calls)


# ------------------------------------------------------------------ staging policy


def _status(*paths: str) -> FakeProc:
    return FakeProc(returncode=0, stdout="".join(f"?? {p}\0" for p in paths))


def _cached(*paths: str) -> FakeProc:
    return FakeProc(returncode=0, stdout="".join(f"{p}\0" for p in paths))


def test_approved_path_is_accepted(mod):
    mod.ALLOWLIST = ("allowed.txt",)
    runner = FakeRunner([_status("allowed.txt"), FakeProc(), _cached("allowed.txt")])
    _use_fake(mod, runner)
    staged = mod.stage_allowlisted()
    assert staged == ["allowed.txt"]
    add_calls = [a for a, _ in runner.calls if len(a) >= 2 and a[1] == "add"]
    assert add_calls and add_calls[0] == ["git", "add", "--", "allowed.txt"]


def test_unapproved_modified_path_is_rejected(mod):
    mod.ALLOWLIST = ("allowed.txt",)
    runner = FakeRunner([_status("allowed.txt", "other.txt")])
    _use_fake(mod, runner)
    with pytest.raises(mod.AutopushError):
        mod.stage_allowlisted()
    assert all(not (len(a) >= 2 and a[1] == "add") for a, _ in runner.calls)


def test_unapproved_untracked_path_is_rejected(mod):
    mod.ALLOWLIST = ("allowed.txt",)
    runner = FakeRunner([_status("surprise.txt")])
    _use_fake(mod, runner)
    with pytest.raises(mod.AutopushError):
        mod.stage_allowlisted()


def test_backup_path_is_rejected_even_if_allowlisted(mod):
    mod.ALLOWLIST = ("tools/backup_sqlite.py", "bot/backup_lifecycle.py")
    runner = FakeRunner([_status("tools/backup_sqlite.py", "bot/backup_lifecycle.py")])
    _use_fake(mod, runner)
    with pytest.raises(mod.AutopushError):
        mod.stage_allowlisted()


def test_env_and_database_files_are_rejected(mod):
    mod.ALLOWLIST = (".env", "bot_state.sqlite3")
    runner = FakeRunner([_status(".env", "bot_state.sqlite3")])
    _use_fake(mod, runner)
    with pytest.raises(mod.AutopushError):
        mod.stage_allowlisted()


def test_log_and_generated_files_are_rejected(mod):
    mod.ALLOWLIST = ("app.log", "cache.pyc")
    runner = FakeRunner([_status("app.log", "cache.pyc")])
    _use_fake(mod, runner)
    with pytest.raises(mod.AutopushError):
        mod.stage_allowlisted()


def test_requirements_txt_is_rejected(mod):
    mod.ALLOWLIST = ("requirements.txt",)
    runner = FakeRunner([_status("requirements.txt")])
    _use_fake(mod, runner)
    with pytest.raises(mod.AutopushError):
        mod.stage_allowlisted()


def test_traversal_path_is_rejected(mod):
    mod.ALLOWLIST = ("../outside.txt", "/etc/passwd", "a/../../b.txt")
    runner = FakeRunner([_status("../outside.txt")])
    _use_fake(mod, runner)
    with pytest.raises(mod.AutopushError):
        mod.stage_allowlisted()


def test_unexpected_path_fails_closed(mod):
    mod.ALLOWLIST = ("allowed.txt",)
    runner = FakeRunner([_status("allowed.txt", ".env")])
    _use_fake(mod, runner)
    with pytest.raises(mod.AutopushError):
        mod.stage_allowlisted()
    # Nothing should have been staged.
    assert all(not (len(a) >= 2 and a[1] == "add") for a, _ in runner.calls)


def test_no_broad_staging_command_is_ever_issued(mod):
    mod.ALLOWLIST = ("allowed.txt",)
    runner = FakeRunner([_status("allowed.txt"), FakeProc(), _cached("allowed.txt")])
    _use_fake(mod, runner)
    mod.stage_allowlisted()
    for args, _ in runner.calls:
        assert args[:2] != ["git", "add"] or args[2:] != ["-A"]
        assert args[1:3] != ["add", "-A"]
        assert args[1:3] != ["add", "."]


def test_staged_verification_rejects_unexpected_file(mod):
    mod.ALLOWLIST = ("allowed.txt",)
    # git status shows only the approved path, but the index unexpectedly contains
    # another path => the post-stage verification must fail closed.
    runner = FakeRunner([_status("allowed.txt"), FakeProc(), _cached("allowed.txt", "secret.txt")])
    _use_fake(mod, runner)
    with pytest.raises(mod.AutopushError):
        mod.stage_allowlisted()


def test_failed_validation_prevents_later_publication(mod):
    mod.ALLOWLIST = ("allowed.txt",)
    runner = FakeRunner([_status("allowed.txt", "rogue.txt")])
    _use_fake(mod, runner)
    with pytest.raises(mod.AutopushError):
        mod.commit_all()
    assert all(a[1] != "commit" for a, _ in runner.calls)
    assert all("push" not in a for a, _ in runner.calls)


# ------------------------------------------------------------- operational isolation


def test_module_has_no_import_time_side_effects(mod):
    # Importing the module must not create subprocesses, threads, or run main().
    assert callable(mod.main)
    assert mod.__name__ == "autopush_main_under_test"


def test_no_real_github_write_commands(mod):
    mod.ALLOWLIST = ("allowed.txt",)
    runner = FakeRunner([_status("allowed.txt"), FakeProc(), _cached("allowed.txt")])
    _use_fake(mod, runner)
    mod.stage_allowlisted()
    for args, _ in runner.calls:
        assert "github.com" not in " ".join(args)


def test_no_telegram_or_callback_when_unconfigured(mod, monkeypatch):
    monkeypatch.delenv("AUTOMATION_CALLBACK_URL", raising=False)
    called = {"n": 0}

    def fake_urlopen(*a, **k):
        called["n"] += 1
        return None

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    mod.fire_callback("COMPLETED")
    assert called["n"] == 0


def test_push_uses_remote_name_not_url(mod):
    # ahead_behind -> ahead=1 so a push is attempted.
    runner = FakeRunner([FakeProc(returncode=0, stdout="1\n"), FakeProc(returncode=0, stdout="0\n")])
    _use_fake(mod, runner)
    mod._token_cache = CANARY
    mod.push_if_ahead()
    push_calls = [a for a, _ in runner.calls if len(a) >= 2 and a[1] == "push"]
    assert push_calls, "expected a push"
    assert push_calls[0] == ["git", "push", mod.REMOTE, "HEAD:main"]
    assert all(CANARY not in " ".join(a) for a in push_calls)


# --------------------------------------------- OHB2-N10-28B-L1: repo-URL userinfo


def test_https_url_with_user_and_password_is_rejected(mod):
    assert mod._url_embeds_credentials("https://user:pass@github.com/o/r.git") is True
    with pytest.raises(mod.AutopushError) as exc:
        mod._resolve_repo_url("https://user:pass@github.com/o/r.git")
    # The rejection text must not echo the supplied credential.
    assert "pass" not in str(exc.value)
    assert "user:pass" not in str(exc.value)


def test_https_url_with_token_userinfo_is_rejected(mod):
    url = f"https://x-access-token:{CANARY}@github.com/o/r.git"
    assert mod._url_embeds_credentials(url) is True
    with pytest.raises(mod.AutopushError) as exc:
        mod._resolve_repo_url(url)
    assert CANARY not in str(exc.value)
    assert "x-access-token" not in str(exc.value)


def test_bare_user_https_url_is_rejected(mod):
    # A bare token as username is credential-bearing on HTTP(S).
    assert mod._url_embeds_credentials("https://ghp_tokenonly@github.com/o/r.git") is True
    with pytest.raises(mod.AutopushError):
        mod._resolve_repo_url("https://ghp_tokenonly@github.com/o/r.git")


def test_normal_https_url_is_accepted(mod):
    url = "https://github.com/TM-AEM/OpenHandBot.git"
    assert mod._url_embeds_credentials(url) is False
    assert mod._resolve_repo_url(url) == url


def test_normal_ssh_urls_are_accepted(mod):
    for url in (
        "git@github.com:TM-AEM/OpenHandBot.git",
        "ssh://git@github.com/TM-AEM/OpenHandBot.git",
        "ssh://git@github.com:22/TM-AEM/OpenHandBot.git",
    ):
        assert mod._url_embeds_credentials(url) is False, url
        assert mod._resolve_repo_url(url) == url


def test_url_validation_error_never_exposes_credentials(mod):
    for url in (
        f"https://alice:{CANARY}@github.com/o/r.git",
        f"https://{CANARY}@github.com/o/r.git",
        f"https://alice:{CANARY}@github.com:8443/o/r.git",
    ):
        with pytest.raises(mod.AutopushError) as exc:
            mod._resolve_repo_url(url)
        text = str(exc.value)
        assert CANARY not in text
        assert "alice" not in text


def test_displayed_repo_url_is_stripped_of_userinfo(mod, capsys, tmp_path):
    # ensure_repo() must never print an embedded credential, even if REPO_URL carried one.
    mod.REPO_DIR = str(tmp_path / "clone-target")  # absent => clone path runs
    mod.REPO_URL = f"https://x-access-token:{CANARY}@github.com/o/r.git"
    mod._token_cache = CANARY
    runner = FakeRunner()
    _use_fake(mod, runner)
    mod.ensure_repo()
    captured = capsys.readouterr()
    assert CANARY not in captured.out
    assert CANARY not in captured.err
    assert "x-access-token" not in captured.out
    # The clone argv is also sanitized to the bare URL.
    for args, _ in runner.calls:
        assert all(CANARY not in str(a) for a in args)


def test_safe_url_helper_strips_userinfo(mod):
    assert mod._safe_url("https://user:pass@host/x.git") == "https://host/x.git"
    assert mod._safe_url("https://host/x.git") == "https://host/x.git"
    assert mod._safe_url("git@github.com:o/r.git") == "git@github.com:o/r.git"


# ------------------------------------------------------------------------ helpers


def _real_git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True
    )
