"""Auto-push automation: every 300s, commit + push workspace changes to main.

Deterministic (no LLM). Two run modes:

  * Cloud automation entrypoint: `python3 main.py` -- runs one cycle, then fires
    the completion callback (if the automation service provided one).
  * Local daemon: `python3 main.py --daemon` -- loops every INTERVAL seconds
    forever (used to run the automation inside a live session).

When no git work tree is present the script clones the target repo itself, so it
works both against a live workspace and from a fresh automation sandbox.

Env:
  AUTOPUSH_REPO_DIR    repo working tree (default: cwd if a repo, else /tmp/autopush-repo)
  AUTOPUSH_REPO_URL    clone URL when the work tree is absent (default: TM-AEM/OpenHandBot).
                       Must not embed credentials (userinfo); such a URL is refused.
  AUTOPUSH_BRANCH      target branch (default: main)
  AUTOPUSH_REMOTE      remote name (default: origin)
  AUTOPUSH_INTERVAL    loop seconds in --daemon mode (default: 300)
  AUTOPUSH_AUTHOR_NAME / AUTOPUSH_AUTHOR_EMAIL
  AUTOPUSH_ALLOWLIST   comma-separated repo-relative paths Autopush may stage.
                       Empty (default) => refuse to stage anything (fail closed).
  GITHUB_TOKEN         push credential (falls back to a stored secret)

Security model (OHB2-N10-28B):
  * The credential is passed to git through an ephemeral credential helper that
    reads it from the child-process environment. It is NEVER placed in a remote
    URL, in subprocess argv, in .git/config, or in temp files.
  * The configured repository URL (AUTOPUSH_REPO_URL) is validated at startup:
    a URL that embeds credentials (userinfo) is refused, and any URL shown in logs
    or diagnostics is displayed with its userinfo stripped.
  * Staging is fail-closed: only paths explicitly listed in AUTOPUSH_ALLOWLIST
    (and never sensitive/backup/ignored paths) may be staged.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone

DEFAULT_REPO_URL = "https://github.com/TM-AEM/OpenHandBot.git"
DEFAULT_REPO_DIR = "/tmp/autopush-repo"


def _default_repo_dir() -> str:
    cwd = os.getcwd()
    if os.path.isdir(os.path.join(cwd, ".git")):
        return cwd
    return DEFAULT_REPO_DIR


class AutopushError(RuntimeError):
    """A fail-closed Autopush error whose text never contains credential material."""


def _url_embeds_credentials(url: str) -> bool:
    """True when a repository URL embeds credentials (userinfo) that must not be used.

    Any `user:secret@host` userinfo is always rejected. A bare `user@host` is rejected
    for HTTP(S) URLs (a bare token is credential-bearing there) but accepted for SSH
    URLs, where `git@host` is the conventional remote username. scp-like URLs
    (`git@host:path`, no `://`) are accepted.
    """
    if "://" not in url:
        return False
    scheme, rest = url.split("://", 1)
    authority = rest.split("/", 1)[0].split("?", 1)[0]
    if "@" not in authority:
        return False
    userinfo = authority.rsplit("@", 1)[0]
    if ":" in userinfo:
        return True
    return scheme.lower() not in ("ssh", "git+ssh")


def _safe_url(url: str) -> str:
    """Return a display-safe URL with any userinfo stripped (for logs/diagnostics)."""
    if "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    authority = rest.split("/", 1)[0].split("?", 1)[0]
    if "@" not in authority:
        return url
    bare = authority.rsplit("@", 1)[-1]
    return f"{scheme}://{bare}{rest[len(authority):]}"


def _resolve_repo_url(raw: str) -> str:
    """Validate the configured repository URL; fail closed on embedded credentials.

    Credentials must be supplied by the environment credential helper, never embedded
    in the repository URL. A URL carrying userinfo is refused rather than silently used.
    Legitimate HTTPS and SSH URLs are accepted unchanged.
    """
    if _url_embeds_credentials(raw):
        raise AutopushError(
            "AUTOPUSH_REPO_URL must not embed credentials (userinfo); "
            "provide the credential via the environment/credential helper instead"
        )
    return raw


REPO_DIR = os.environ.get("AUTOPUSH_REPO_DIR") or _default_repo_dir()
REPO_URL = _resolve_repo_url(os.environ.get("AUTOPUSH_REPO_URL", DEFAULT_REPO_URL))
BRANCH = os.environ.get("AUTOPUSH_BRANCH", "main")
REMOTE = os.environ.get("AUTOPUSH_REMOTE", "origin")
INTERVAL = int(os.environ.get("AUTOPUSH_INTERVAL", "300"))
AUTHOR_NAME = os.environ.get("AUTOPUSH_AUTHOR_NAME", "openhands-autopush")
AUTHOR_EMAIL = os.environ.get("AUTOPUSH_AUTHOR_EMAIL", "openhands@all-hands.dev")

# Credential helper: git invokes this shell snippet; it reads the token from the
# child-process environment. The token therefore never appears in argv, in a remote
# URL, in .git/config, or in a temp file. `test -n` guards a set-but-empty value.
_CRED_HELPER = (
    '!f() { test -n "$GITHUB_TOKEN" || exit 1; '
    'printf "username=x-access-token\\npassword=%s\\n" "$GITHUB_TOKEN"; }; f'
)

# Placeholder used when no credential is configured, so that (a) no real secret is
# ever synthesized and (b) a synthetic canary cannot be mistaken for a real token.
_PLACEHOLDER_TOKEN = "unset-no-token"

# Environment variables propagated to git subprocesses. A fixed allowlist (instead of
# a full `os.environ` copy) prevents accidental leakage of unrelated process secrets.
_GIT_ENV_KEYS = (
    "PATH", "HOME", "LANG", "LC_ALL", "TZ", "TMPDIR",
    "SSL_CERT_FILE", "SSL_CERT_DIR", "GIT_SSL_CAINFO",
    "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy",
)

# TLS verification must never be disabled for child git commands. This variable is
# deliberately NOT in the allowlist above; we also drop it explicitly in `_child_env`
# so a future allowlist edit cannot silently reintroduce it. CA config
# (`SSL_CERT_FILE`/`SSL_CERT_DIR`/`GIT_SSL_CAINFO`) is still forwarded.
_TLS_DENY_KEYS = ("GIT_SSL_NO_VERIFY",)

# Repo-relative paths Autopush may stage. Empty => refuse to stage anything (fail
# closed). No default entry ever names a sensitive or backup path.
ALLOWLIST: tuple[str, ...] = tuple(
    p.strip()
    for p in os.environ.get("AUTOPUSH_ALLOWLIST", "").split(",")
    if p.strip()
)

# Filenames/segments that must never be staged, even if they appear in the allowlist.
_DENY_SUFFIXES = (
    ".env", ".sqlite", ".sqlite3", ".db", ".db-wal", ".db-shm",
    ".log", ".pyc", ".pem", ".key", ".p12", ".pfx",
)
_DENY_SEGMENTS = frozenset({
    ".git", ".venv", "venv", "env", "__pycache__", "node_modules", "tools", "docs",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".idea", ".vscode", ".agents_tmp",
})
_DENY_BASENAMES = frozenset({
    ".env", "requirements.txt", "requirements-dev.txt", ".gitignore",
    "id_rsa", "id_ed25519", "known_hosts",
})
_DENY_SUBSTRINGS = ("backup", "secret", "credential", "token")


_token_cache: str | None = None


def get_secret(name: str) -> str | None:
    """Fetch a stored secret over REST; return None when unavailable."""
    url = os.environ.get("AGENT_SERVER_URL", "").rstrip("/")
    key = os.environ.get("SESSION_API_KEY") or os.environ.get("OH_SESSION_API_KEYS_0", "")
    if url:
        endpoint = f"{url}/api/settings/secrets/{name}"
    else:
        api = os.environ.get("OPENHANDS_CLOUD_API_URL", "").rstrip("/")
        sandbox = os.environ.get("SANDBOX_ID", "")
        if not (api and sandbox and key):
            return None
        endpoint = f"{api}/api/v1/sandboxes/{sandbox}/settings/secrets/{name}"
    try:
        req = urllib.request.Request(endpoint, headers={"X-Session-API-Key": key})
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode().strip() or None
    except Exception:
        return None


def resolve_token() -> str:
    """Return the push credential, or a non-secret placeholder when none is set."""
    global _token_cache
    if _token_cache:
        return _token_cache
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("AUTOPUSH_GITHUB_TOKEN")
    if not token:
        token = get_secret("GITHUB_TOKEN") or get_secret("AUTOPUSH_GITHUB_TOKEN")
    _token_cache = token or _PLACEHOLDER_TOKEN
    return _token_cache


def fire_callback(status: str = "COMPLETED", error: str | None = None) -> None:
    url = os.environ.get("AUTOMATION_CALLBACK_URL", "")
    if not url:
        return
    body = {"status": status, "run_id": os.environ.get("AUTOMATION_RUN_ID", "")}
    if error:
        body["error"] = redact(error)
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.environ.get('AUTOMATION_CALLBACK_API_KEY', '')}",
        },
    )
    try:
        urllib.request.urlopen(req, timeout=15)
    except Exception as exc:  # pragma: no cover - best effort
        print(f"Callback error (non-fatal): {redact(str(exc))}")


def redact(text: str) -> str:
    """Remove credential material from any text before it is printed or reported."""
    out = text
    for secret in (_token_cache, os.environ.get("GITHUB_TOKEN")):
        if secret and secret != _PLACEHOLDER_TOKEN:
            out = out.replace(secret, "***")
    return out


def _child_env() -> dict:
    """Build a minimal environment for git, injecting the credential helper via env.

    The helper and its token live only in the child process environment; nothing is
    written to argv or to .git/config. TLS verification is preserved (the CA-related
    variables above are forwarded unchanged).
    """
    env = {k: os.environ[k] for k in _GIT_ENV_KEYS if k in os.environ}
    # Defence in depth: even if an allowlist entry is (re)added, TLS-disabling variables
    # must never reach a child git command.
    for denied in _TLS_DENY_KEYS:
        env.pop(denied, None)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "credential.helper"
    env["GIT_CONFIG_VALUE_0"] = _CRED_HELPER
    env["GITHUB_TOKEN"] = _token_cache or _PLACEHOLDER_TOKEN
    return env


def _sanitize_args(args: tuple[str, ...]) -> tuple[str, ...]:
    """Strip credentials from URL arguments; refuse any other token-bearing argument."""
    token = _token_cache
    if not token or token == _PLACEHOLDER_TOKEN:
        return args
    cleaned: list[str] = []
    for arg in args:
        if token in arg:
            if "://" in arg:
                cleaned.append(_strip_url_credentials(arg))
                continue
            raise AutopushError("refusing to run git with a credential in its arguments")
        cleaned.append(arg)
    return tuple(cleaned)


def _strip_url_credentials(url: str) -> str:
    if "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    return f"{scheme}://{rest.split('@')[-1]}"


_git_runner = subprocess.run


def git(*args: str, check: bool = True, cwd: str | None = None) -> subprocess.CompletedProcess:
    safe_args = _sanitize_args(args)
    proc = _git_runner(
        ["git", *safe_args],
        cwd=cwd or REPO_DIR,
        capture_output=True,
        text=True,
        env=_child_env(),
    )
    if proc.stdout:
        print(redact(proc.stdout.rstrip()), flush=True)
    if proc.stderr:
        print(redact(proc.stderr.rstrip()), file=sys.stderr, flush=True)
    if check and proc.returncode != 0:
        # Command text is sanitized (no credential can reach here), so it is safe to
        # include for diagnostics.
        raise AutopushError(f"git {' '.join(safe_args)} failed ({proc.returncode})")
    return proc


def authed_url(url: str) -> str:
    """Strip any embedded userinfo from a URL.

    Kept for compatibility with callers/tests. Credentials are no longer embedded in
    URLs; authentication is supplied by the environment credential helper instead.
    """
    if "://" not in url:
        return url
    return _strip_url_credentials(url)


def ensure_repo(token: str | None = None) -> None:
    if os.path.isdir(os.path.join(REPO_DIR, ".git")):
        return
    parent = os.path.dirname(REPO_DIR.rstrip("/")) or "/"
    name = os.path.basename(REPO_DIR.rstrip("/"))
    os.makedirs(parent, exist_ok=True)
    print(f"Cloning {_safe_url(REPO_URL)} -> {REPO_DIR}")
    # The plain URL is passed (no credential); the env credential helper authenticates.
    git("clone", "--branch", BRANCH, REPO_URL, name, cwd=parent)
    # Belt and braces: keep the remote free of any userinfo.
    git("remote", "set-url", REMOTE, REPO_URL)


def current_branch() -> str:
    return git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def has_changes() -> bool:
    return bool(git("status", "--porcelain", check=False).stdout.strip())


def remote_url() -> str:
    return git("remote", "get-url", REMOTE, check=False).stdout.strip()


def _path_is_allowed(path: str) -> bool:
    """Fail-closed allowlist check for a single repo-relative path."""
    if not path:
        return False
    if path.startswith(("/", "\\")) or os.path.isabs(path):
        return False
    norm = path.replace("\\", "/")
    parts = [p for p in norm.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        return False
    if not parts:
        return False
    basename = parts[-1]
    lowered = norm.lower()
    if basename.lower() in _DENY_BASENAMES:
        return False
    if lowered.endswith(_DENY_SUFFIXES):
        return False
    if any(seg.lower() in _DENY_SEGMENTS for seg in parts[:-1]):
        return False
    if any(s in lowered for s in _DENY_SUBSTRINGS):
        return False
    return norm in ALLOWLIST


def _porcelain_paths() -> list[tuple[str, str]]:
    """Return (status, path) for every changed/untracked path, without staging."""
    proc = git("status", "--porcelain", "-z", "--untracked-files=all", check=False)
    raw = proc.stdout or ""
    entries: list[tuple[str, str]] = []
    fields = raw.split("\0")
    i = 0
    while i < len(fields):
        chunk = fields[i]
        if not chunk:
            i += 1
            continue
        status, path = chunk[:2], chunk[3:]
        entries.append((status, path))
        # Renames/copies carry a second NUL-separated path that we must not treat as
        # an independent entry.
        if status[:1] in ("R", "C"):
            i += 2
        else:
            i += 1
    return entries


def _staged_paths() -> list[str]:
    """Return the repo-relative paths currently staged in the index."""
    proc = git("diff", "--cached", "--name-only", "-z", check=False)
    return [p for p in (proc.stdout or "").split("\0") if p]


def stage_allowlisted() -> list[str]:
    """Stage only allowlisted paths; fail closed if any changed path is disallowed."""
    changed = _porcelain_paths()
    approved = [path for _, path in changed if _path_is_allowed(path)]
    disallowed = [path for _, path in changed if not _path_is_allowed(path)]
    if disallowed:
        preview = ", ".join(disallowed[:5])
        raise AutopushError(
            f"refusing to stage {len(disallowed)} path(s) outside the approved allowlist "
            f"(e.g. {preview})"
        )
    if not approved:
        return []
    # Paths come from git status and have been allowlist-verified; '--' guards against
    # option injection and no broad 'git add -A'/'.' is ever issued.
    git("add", "--", *approved)
    # Verify what actually landed in the index before anything may commit it.
    staged = _staged_paths()
    unexpected = [p for p in staged if not _path_is_allowed(p)]
    if unexpected:
        raise AutopushError(
            f"staged path verification failed: {len(unexpected)} unexpected path(s) "
            f"in the index (e.g. {', '.join(unexpected[:5])})"
        )
    return staged


def commit_all() -> None:
    staged = stage_allowlisted()
    if not staged:
        print("No allowlisted changes to commit.")
        return
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    git(
        "-c",
        f"user.name={AUTHOR_NAME}",
        "-c",
        f"user.email={AUTHOR_EMAIL}",
        "commit",
        "-m",
        f"chore(autopush): sync workspace changes @ {ts}",
    )


def ahead_behind() -> tuple[int, int]:
    ahead = int(git("rev-list", "--count", f"{REMOTE}/{BRANCH}..HEAD", check=False).stdout.strip() or 0)
    behind = int(git("rev-list", "--count", f"HEAD..{REMOTE}/{BRANCH}", check=False).stdout.strip() or 0)
    return ahead, behind


def sync_remote() -> None:
    """Fetch via the named remote (keeps origin/<branch> current); ff or rebase."""
    git("fetch", REMOTE, BRANCH, check=False)
    ahead, behind = ahead_behind()
    if behind and not ahead:
        git("merge", "--ff-only", f"{REMOTE}/{BRANCH}")
    elif behind and ahead:
        proc = git("rebase", f"{REMOTE}/{BRANCH}", check=False)
        if proc.returncode != 0:
            git("rebase", "--abort", check=False)
            raise AutopushError("rebase conflict; manual resolution required")


def push_if_ahead(token: str | None = None) -> bool:
    ahead, _ = ahead_behind()
    if ahead == 0:
        print("Nothing to push (already up to date).")
        return False
    # Push by remote name (no URL, no credential in argv); the env credential helper
    # authenticates the request.
    git("push", REMOTE, f"HEAD:{BRANCH}")
    print("Pushed to remote.")
    return True


def run_cycle() -> dict:
    token = resolve_token()
    ensure_repo(token)
    branch = current_branch()
    if branch != BRANCH:
        raise AutopushError(f"on branch '{branch}', expected '{BRANCH}'")

    # Commit local work BEFORE syncing. Rebasing a dirty work tree aborts as soon
    # as the remote moved a file the local tree also changed ("cannot rebase: You
    # have unstaged changes"), which would fail every cycle and never push.
    if has_changes():
        commit_all()
    else:
        print("No local changes.")

    sync_remote()

    return {"pushed": push_if_ahead(token)}


def main() -> int:
    daemon = "--daemon" in sys.argv
    once = "--once" in sys.argv or not daemon
    try:
        if daemon:
            print(f"autopush daemon started: repo={REPO_DIR} branch={BRANCH} interval={INTERVAL}s")
            while True:
                try:
                    run_cycle()
                except Exception as exc:
                    print(f"cycle error (will retry): {redact(str(exc))}", file=sys.stderr)
                time.sleep(INTERVAL)
        if once:
            run_cycle()
        fire_callback("COMPLETED")
        return 0
    except Exception as exc:
        safe = redact(str(exc))
        print(f"ERROR: {safe}", file=sys.stderr)
        fire_callback("FAILED", safe)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
