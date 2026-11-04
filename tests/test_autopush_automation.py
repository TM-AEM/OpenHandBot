"""OHB2-N10-16: تأكيد مستقل لأتمتة الـ autopush (كل 300 ث ⇒ push لـ main لو فيه تغييرات).

بنشغّل السكربت الحقيقي `automation/autopush/main.py --once` ضد مستودع مؤقت ومستودع
بعيد محلي (bare) — مفيش أي شبكة ولا مستودع إنتاجي. ده يثبت: (1) بيعمل commit للفروق،
(2) بيعمل push لـ main، (3) لما مفيش تغييرات مابيعملش push.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SCRIPT = Path(__file__).resolve().parents[1] / "automation" / "autopush" / "main.py"


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True
    )


def _make_repos(tmp_path: Path) -> tuple[Path, Path]:
    remote = tmp_path / "remote.git"
    _git(tmp_path, "init", "--bare", str(remote))
    work = tmp_path / "work"
    _git(tmp_path, "init", "-b", "main", str(work))
    _git(work, "config", "user.email", "t@example.com")
    _git(work, "config", "user.name", "tester")
    (work / "README.md").write_text("hello\n")
    _git(work, "add", "-A")
    _git(work, "commit", "-m", "init")
    _git(work, "remote", "add", "origin", str(remote))
    _git(work, "push", "-u", "origin", "main")
    return work, remote


def _run_cycle(work: Path, remote: Path, allowlist: str = "new_feature.txt") -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "AUTOPUSH_REPO_DIR": str(work),
        "AUTOPUSH_REPO_URL": str(remote),
        "AUTOPUSH_BRANCH": "main",
        "AUTOPUSH_INTERVAL": "300",
        "AUTOPUSH_ALLOWLIST": allowlist,
        "GIT_TERMINAL_PROMPT": "0",
    }
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--once"],
        capture_output=True, text=True, env=env, timeout=120,
    )


def _remote_head(remote: Path) -> str:
    return _git(remote, "rev-parse", "main").stdout.strip()


def test_autopush_commits_and_pushes_changes(tmp_path):
    work, remote = _make_repos(tmp_path)
    before = _remote_head(remote)
    (work / "new_feature.txt").write_text("work in progress\n")

    proc = _run_cycle(work, remote)
    assert proc.returncode == 0, proc.stderr

    after = _remote_head(remote)
    assert after != before  # اتعمل push فعلاً
    # الفروق اتcommit فعلاً ووصلت للمستودع البعيد.
    shown = _git(remote, "show", "--stat", "--format=%s", "main").stdout
    assert "autopush" in shown
    assert "new_feature.txt" in shown


def test_autopush_no_changes_makes_no_push(tmp_path):
    work, remote = _make_repos(tmp_path)
    before = _remote_head(remote)
    proc = _run_cycle(work, remote)
    assert proc.returncode == 0, proc.stderr
    assert _remote_head(remote) == before  # مفيش تغييرات ⇒ مفيش push
    assert "Nothing to push" in proc.stdout


def test_autopush_fails_closed_on_unapproved_path(tmp_path):
    """OHB2-N10-28B: مسار غير مسموح ⇒ السكربت يرفض ويخرج بفشل بدون أي push."""
    work, remote = _make_repos(tmp_path)
    before = _remote_head(remote)
    (work / "rogue.txt").write_text("should not be published\n")

    proc = _run_cycle(work, remote, allowlist="approved_only.txt")
    assert proc.returncode == 1
    assert "allowlist" in proc.stderr
    assert _remote_head(remote) == before  # مفيش commit ولا push حصل


def test_autopush_default_allowlist_stages_nothing(tmp_path):
    """افتراضيًا (مفيش allowlist) مفيش أي حاجة بتتـstage ⇒ مفيش push."""
    work, remote = _make_repos(tmp_path)
    before = _remote_head(remote)
    (work / "anything.txt").write_text("x\n")
    proc = _run_cycle(work, remote, allowlist="")
    assert proc.returncode == 1
    assert _remote_head(remote) == before
