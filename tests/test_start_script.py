"""OHB2-N10-23: اختبارات نقطة التشغيل الواحدة `start.sh`.

بنشغّل السكربت الحقيقي ضد مفسّر Python **وهمي** (shim) بيتحكّم في: نسخة Python،
الحزم الناقصة، نتيجة pip، والـ exit code للتطبيق. مفيش شبكة، مفيش تيليجرام، مفيش تثبيت حقيقي.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
START = ROOT / "start.sh"

SH = shutil.which("sh") or "/bin/sh"


def _write_shim(bin_dir: Path) -> Path:
    """مفسّر Python وهمي: يحاكي نداءات start.sh بناءً على ملفات تحكّم في مجلد الشيم."""
    shim = bin_dir / "python-shim"
    shim.write_text(
        "#!/usr/bin/env sh\n"
        'DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"\n'
        'case "$1" in\n'
        '  -c) [ -f "$DIR/version_ok" ] && exit 0 || exit 1 ;;\n'
        '  -) cat "$DIR/missing.txt" 2>/dev/null; exit 0 ;;\n'
        '  -m) if [ -f "$DIR/pip_ok" ]; then : > "$DIR/missing.txt"; exit 0; else exit 1; fi ;;\n'
        '  main.py) echo "SHIM_MAIN_RAN"; exit "${SHIM_MAIN_EXIT:-0}" ;;\n'
        "  *) exit 0 ;;\n"
        "esac\n"
    )
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return shim


@pytest.fixture()
def shim(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    exe = _write_shim(bin_dir)
    (bin_dir / "version_ok").write_text("")  # افتراضيًا: نسخة Python مدعومة
    (bin_dir / "missing.txt").write_text("")  # افتراضيًا: مفيش حزم ناقصة

    app = tmp_path / "app"
    app.mkdir()
    shutil.copy2(START, app / "start.sh")
    (app / "main.py").write_text("print('REAL_MAIN')\n")
    (app / "requirements.txt").write_text("python-telegram-bot[all]==22.8\n")
    return {"shim": exe, "bin": bin_dir, "app": app}


def _run(shim, *, cwd: Path | None = None, env: dict | None = None, script: Path | None = None):
    base_env = {**os.environ, "OPENHANDBOT_PYTHON": str(shim["shim"])}
    if env:
        base_env.update(env)
    return subprocess.run(
        [SH, str(script or (shim["app"] / "start.sh"))],
        cwd=str(cwd or shim["app"]),
        capture_output=True,
        text=True,
        env=base_env,
        timeout=60,
    )


# ------------------------------------------------------------------ happy path


def test_clean_startup_execs_main(shim):
    proc = _run(shim, env={"SHIM_MAIN_EXIT": "0"})
    assert proc.returncode == 0
    assert "SHIM_MAIN_RAN" in proc.stdout


def test_exit_status_is_propagated(shim):
    proc = _run(shim, env={"SHIM_MAIN_EXIT": "7"})
    assert proc.returncode == 7  # نفس كود خروج التطبيق (exec ⇒ مفيش غلاف)


def test_runs_from_script_dir_regardless_of_cwd(shim):
    # نشغّل من جذر مختلف: لازم يـ cd لمجلد السكربت ويلاقي main.py.
    proc = _run(shim, cwd=Path("/"))
    assert proc.returncode == 0
    assert "SHIM_MAIN_RAN" in proc.stdout


# ------------------------------------------------------------------ version gate


def test_invalid_python_version_fails_clearly(shim):
    (shim["bin"] / "version_ok").unlink()
    proc = _run(shim)
    assert proc.returncode == 1
    assert "Python" in proc.stderr


# ------------------------------------------------------------------ dependency gate


def test_missing_dependency_off_auto_install_fails_clearly(shim):
    (shim["bin"] / "missing.txt").write_text("telegram httpx")
    proc = _run(shim, env={"OPENHANDBOT_AUTO_INSTALL": "0"})
    assert proc.returncode == 1
    assert "telegram" in proc.stderr
    assert "SHIM_MAIN_RAN" not in proc.stdout  # ماوصلش للتشغيل


def test_auto_install_pip_failure_is_reported(shim):
    (shim["bin"] / "missing.txt").write_text("telegram")
    # pip_ok مش موجود ⇒ الشيم يرجّع فشل
    proc = _run(shim, env={"OPENHANDBOT_AUTO_INSTALL": "1"})
    assert proc.returncode == 1
    assert "فشل" in proc.stderr
    assert "SHIM_MAIN_RAN" not in proc.stdout


def test_auto_install_success_then_starts(shim):
    (shim["bin"] / "missing.txt").write_text("telegram")
    (shim["bin"] / "pip_ok").write_text("")  # الشيم ينجح ويصفّر missing.txt
    proc = _run(shim, env={"OPENHANDBOT_AUTO_INSTALL": "1"})
    assert proc.returncode == 0
    assert "SHIM_MAIN_RAN" in proc.stdout


def test_missing_main_py_fails_clearly(shim):
    (shim["app"] / "main.py").unlink()
    proc = _run(shim)
    assert proc.returncode == 1
    assert "main.py" in proc.stderr


# ------------------------------------------------------------------ process / safety invariants


def test_single_process_exec_no_backgrounding():
    import re

    src = START.read_text()
    assert 'exec "$PY" main.py' in src  # exec واحد ⇒ نفس العملية
    for forbidden in ("nohup", "setsid", "disown"):
        assert forbidden not in src, f"start.sh فيه backgrounding: {forbidden}"
    # ممنوع خلفية (a lone '&' — بس '&&' و'>&2' مسموحين).
    assert not re.search(r"(?<![&>])&(?!&)", src), "start.sh فيه '&' خلفية"


def test_no_destructive_db_operations_in_script():
    src = START.read_text()
    assert "rm " not in src and "rm -" not in src
    assert "sqlite" not in src.lower()
    assert "DROP" not in src and "DELETE" not in src


def test_secret_not_printed_by_script(shim):
    secret = "123456:ABC-DEF-secret-token-value"
    proc = _run(shim, env={"TELEGRAM_BOT_TOKEN": secret, "OPENHANDS_API_KEY": "sk-secret-xyz"})
    assert secret not in proc.stdout
    assert secret not in proc.stderr
    assert "sk-secret-xyz" not in proc.stdout
    assert "sk-secret-xyz" not in proc.stderr


def test_script_is_documented_and_shipped():
    # نقطة التشغيل لازم تكون موثّقة في دليل النشر وقائمة الرفع.
    doc = (ROOT / "docs" / "DEPLOY_KATABUMP.md").read_text()
    assert "start.sh" in doc
    assert (ROOT / "start.sh").is_file()


def test_python_gate_matches_bootstrap_min_python():
    # حرس انحراف: حد النسخة في start.sh لازم يطابق bot/bootstrap.py::MIN_PYTHON.
    import re

    import bot.bootstrap as boot

    src = START.read_text()
    m = re.search(r"version_info\[:2\]\s*>=\s*\((\d+),\s*(\d+)\)", src)
    assert m, "مش لاقي فحص نسخة Python في start.sh"
    assert (int(m.group(1)), int(m.group(2))) == boot.MIN_PYTHON
