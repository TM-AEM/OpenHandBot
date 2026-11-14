# Auto-push automation (every 300s)

Commits any pending workspace changes and pushes them to `main` of
`TM-AEM/OpenHandBot`. Deterministic — no LLM, no tokens spent.

## What it does (one cycle)

1. Resolve the push credential: `GITHUB_TOKEN` from the environment, otherwise a
   stored secret of the same name.
2. Ensure a git work tree exists (clone `main` if the directory has none).
3. Stage **only allowlisted paths** (`AUTOPUSH_ALLOWLIST`) and commit when there are
   local changes (before syncing, so the rebase never runs against a dirty work tree).
   An empty allowlist (the default) stages nothing; any non-allowlisted changed path
   aborts the cycle (fail closed). `git add -A` / `git add .` are never used.
4. `git fetch origin main`; fast-forward if behind, rebase if diverged
   (a rebase conflict aborts and reports instead of clobbering anything).
5. `git push origin HEAD:main` only when local is ahead of `origin/main`.

Credentials are never written to `.git/config`: authentication uses an ephemeral git
credential helper injected through the child-process environment, so the token the
script resolves is never placed in a remote URL, in subprocess arguments, in
`.git/config`, or in a temp file, and it is scrubbed from every log line and
diagnostic.

The configured repository URL (`AUTOPUSH_REPO_URL`) must not embed credentials
(userinfo). A URL that carries userinfo is refused at startup (fail closed), and any
URL that is shown in logs is printed with its userinfo stripped. Legitimate HTTPS and
SSH URLs (e.g. `https://github.com/owner/repo.git`, `git@github.com:owner/repo.git`)
are supported unchanged.

## Run modes

| Mode | Command | Use |
| --- | --- | --- |
| Once | `python3 main.py --once` | One cycle; the cloud automation entrypoint (also fires the run callback) |
| Daemon | `python3 main.py --daemon` | Loops every `AUTOPUSH_INTERVAL` seconds inside a live session |

Local daemon helper: `./run.sh` (logs to `autopush.log`, default 300s).

## Configuration

| Env var | Default | Purpose |
| --- | --- | --- |
| `AUTOPUSH_REPO_DIR` | cwd if a repo, else `/tmp/autopush-repo` | Work tree |
| `AUTOPUSH_REPO_URL` | `https://github.com/TM-AEM/OpenHandBot.git` | Clone URL (must not embed credentials) |
| `AUTOPUSH_BRANCH` | `main` | Target branch |
| `AUTOPUSH_REMOTE` | `origin` | Remote name |
| `AUTOPUSH_INTERVAL` | `300` | Daemon loop seconds |
| `AUTOPUSH_ALLOWLIST` | — (empty ⇒ stage nothing) | Comma-separated repo-relative paths Autopush may stage |
| `GITHUB_TOKEN` | — | Push credential (falls back to a stored secret) |

## Deploying the cloud automation

```bash
tar -czf /tmp/autopush.tar.gz -C automation/autopush .
TARBALL_PATH=$(curl -s -X POST \
  "https://app.all-hands.dev/api/automation/v1/uploads?name=autopush" \
  -H "Authorization: Bearer $OPENHANDS_API_KEY" \
  -H "Content-Type: application/gzip" \
  --data-binary @/tmp/autopush.tar.gz | jq -r '.tarball_path')
curl -s -X POST "https://app.all-hands.dev/api/automation/v1" \
  -H "Authorization: Bearer $OPENHANDS_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"OpenHandBot autopush\",\"trigger\":{\"type\":\"cron\",\"schedule\":\"*/5 * * * *\",\"timezone\":\"UTC\"},\"tarball_path\":\"$TARBALL_PATH\",\"entrypoint\":\"python3 main.py\"}"
```

> The cloud automation runs in its own fresh sandbox, so it acts on the repo it
> clones there. The **local daemon** is what pushes changes made in a live
> workspace session. Both share this one script.
