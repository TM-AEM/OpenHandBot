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
  AUTOPUSH_REPO_URL    clone URL when the work tree is absent (default: TM-AEM/OpenHandBot)
  AUTOPUSH_BRANCH      target branch (default: main)
  AUTOPUSH_REMOTE      remote name (default: origin)
  AUTOPUSH_INTERVAL    loop seconds in --daemon mode (default: 300)
  AUTOPUSH_AUTHOR_NAME / AUTOPUSH_AUTHOR_EMAIL
  GITHUB_TOKEN         push credential (falls back to a stored secret)
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


REPO_DIR = os.environ.get("AUTOPUSH_REPO_DIR") or _default_repo_dir()
REPO_URL = os.environ.get("AUTOPUSH_REPO_URL", DEFAULT_REPO_URL)
BRANCH = os.environ.get("AUTOPUSH_BRANCH", "main")
REMOTE = os.environ.get("AUTOPUSH_REMOTE", "origin")
INTERVAL = int(os.environ.get("AUTOPUSH_INTERVAL", "300"))
AUTHOR_NAME = os.environ.get("AUTOPUSH_AUTHOR_NAME", "openhands-autopush")
AUTHOR_EMAIL = os.environ.get("AUTOPUSH_AUTHOR_EMAIL", "openhands@all-hands.dev")

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


def resolve_token() -> str | None:
    global _token_cache
    if _token_cache:
        return _token_cache
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("AUTOPUSH_GITHUB_TOKEN")
    if not token:
        token = get_secret("GITHUB_TOKEN") or get_secret("AUTOPUSH_GITHUB_TOKEN")
    _token_cache = token
    return token


def fire_callback(status: str = "COMPLETED", error: str | None = None) -> None:
    url = os.environ.get("AUTOMATION_CALLBACK_URL", "")
    if not url:
        return
    body = {"status": status, "run_id": os.environ.get("AUTOMATION_RUN_ID", "")}
    if error:
        body["error"] = error
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
        print(f"Callback error (non-fatal): {exc}")


def redact(text: str) -> str:
    token = _token_cache
    return text.replace(token, "***") if token else text


def git(*args: str, check: bool = True, cwd: str | None = None) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd or REPO_DIR,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    if proc.stdout:
        print(redact(proc.stdout.rstrip()))
    if proc.stderr:
        print(redact(proc.stderr.rstrip()), file=sys.stderr)
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed ({proc.returncode})")
    return proc


def authed_url(url: str, token: str | None) -> str:
    """Embed a token in `url` for one-shot use. Never written to git config."""
    if not token or "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    bare = rest.split("@")[-1]
    return f"{scheme}://x-access-token:{token}@{bare}"


def ensure_repo(token: str | None) -> None:
    if os.path.isdir(os.path.join(REPO_DIR, ".git")):
        return
    parent = os.path.dirname(REPO_DIR.rstrip("/")) or "/"
    name = os.path.basename(REPO_DIR.rstrip("/"))
    os.makedirs(parent, exist_ok=True)
    print(f"Cloning {REPO_URL} -> {REPO_DIR}")
    git("clone", "--branch", BRANCH, authed_url(REPO_URL, token), name, cwd=parent)
    # Never leave the token in the clone's .git/config.
    git("remote", "set-url", REMOTE, REPO_URL)


def current_branch() -> str:
    return git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def has_changes() -> bool:
    return bool(git("status", "--porcelain", check=False).stdout.strip())


def remote_url() -> str:
    return git("remote", "get-url", REMOTE, check=False).stdout.strip()


def commit_all() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    git("add", "-A")
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
            raise RuntimeError("rebase conflict; manual resolution required")


def push_if_ahead(token: str | None) -> bool:
    ahead, _ = ahead_behind()
    if ahead == 0:
        print("Nothing to push (already up to date).")
        return False
    git("push", authed_url(remote_url(), token), f"HEAD:{BRANCH}")
    # Push went to a URL, so git did not advance the remote-tracking ref.
    git("update-ref", f"refs/remotes/{REMOTE}/{BRANCH}", "HEAD")
    print("Pushed to remote.")
    return True


def run_cycle() -> dict:
    token = resolve_token()
    ensure_repo(token)
    branch = current_branch()
    if branch != BRANCH:
        raise RuntimeError(f"on branch '{branch}', expected '{BRANCH}'")

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
                    print(f"cycle error (will retry): {exc}", file=sys.stderr)
                time.sleep(INTERVAL)
        if once:
            run_cycle()
        fire_callback("COMPLETED")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        fire_callback("FAILED", str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
