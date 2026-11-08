"""OHB2-PHASE1E: تأكيدات على سير عمل CI وسياسة الفحص الثابت/الأمني.

الغرض: منع أي تراجع صامت في تغطية الفحص (كان pyflakes بيسقط `automation/`)،
أو في أدوات SCA/SAST، أو في شروط تشغيل CI. مفيش شبكة: قراءة ملفات المستودع بس.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
DEV_REQS = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
REQS = (ROOT / "requirements.txt").read_text(encoding="utf-8")


def test_ci_triggers_only_on_main_push_and_pr():
    # CI بيشتغل على push/PR لـ main بس (مفيش تشغيل على أي فرع تاني).
    assert "branches: [main]" in CI
    assert CI.count("branches: [main]") == 2  # push + pull_request
    assert "pull_request:" in CI and "push:" in CI


def test_ci_has_least_privilege_and_read_only_contents():
    assert "permissions:" in CI
    assert "contents: read" in CI
    assert "write" not in CI.lower().replace("write permissions", "")


def _run_commands(text: str) -> str:
    """يرجّع نص أوامر `run:` بس (مش التعليقات) من ملف سير العمل."""
    lines = []
    capturing = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("run:"):
            capturing = True
            lines.append(stripped[4:])
            continue
        if capturing:
            if stripped.startswith("#") or stripped == "":
                continue
            if line.startswith(" " * 10) or line.startswith("\t"):
                lines.append(stripped)
                continue
            capturing = False
    return "\n".join(lines).lower()


def test_ci_never_runs_production_side_effects():
    # مفيش أوامر نشر/دفع/تيليجرام/autopush/تشغيل التطبيق جوه أوامر run:.
    runs = _run_commands(CI)
    for forbidden in ("git push", "deploy", "autopush", "start.sh", "pip install openhands"):
        assert forbidden not in runs, f"CI run: لازم مايشغّلش {forbidden!r}"


def test_ci_static_check_covers_all_first_party_modules():
    # الثغرة اللي كانت: pyflakes على bot/ main.py tests/ بس. لازم يغطّي automation/ كمان.
    assert "pyflakes bot/ automation/ main.py tests/" in CI


def test_ci_runs_dependency_and_sast_checks():
    assert "pip_audit -r requirements-dev.txt" in CI
    assert "bandit -r bot/ automation/ main.py -lll -s B613" in CI


def test_ci_sast_scope_includes_automation():
    # AUD-07: كان bandit على bot/ main.py بس. لازم يغطّي automation/ كمان.
    assert "bandit -r bot/ automation/ main.py -lll -s B613" in CI
    # ومفيش استدعاء bandit بنطاق أضيق سايب في السير عمل.
    assert "bandit -r bot/ main.py" not in CI


def test_bandit_flags_high_severity_in_automation(tmp_path):
    """AUD-07: يثبت إن النطاق الموسّع فعّال — bandit بيفشل (non-zero) عند نتيجة
    عالية الخطورة في كود automation/. بنستخدم subprocess على ملف مصغّر آمن (مفيش تنفيذ
    للكود) ونتأكد إن exit code != 0 عند -lll. كده البوابة مش شكلية."""
    import subprocess
    import sys

    probe = tmp_path / "probe_high.py"
    # subprocess.Popen(shell=True) = B602 (high severity) — كافٍ لإثبات إن البوابة بتفشل.
    probe.write_text(
        "import subprocess\n\n\ndef f(cmd):\n    return subprocess.Popen(cmd, shell=True)\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, "-m", "bandit", "-r", str(probe), "-lll"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "B602" in proc.stdout


def test_ci_runs_tests_and_frontend_without_secrets():
    assert "python -m pytest -q" in CI
    assert "node --test tests/frontend/*.test.js" in CI
    # مفيش أسرار حقيقية مفعّلة في بيئة CI (الاختبارات بتستخدم mocks/fixtures).
    assert "secrets." not in CI
    assert "TELEGRAM_BOT_TOKEN" not in CI
    assert "OPENHANDS_API_KEY" not in CI


def test_ci_matrix_preserves_supported_python_versions():
    assert '"3.11"' in CI and '"3.13"' in CI


def test_dev_requirements_pin_security_tools():
    assert "pip-audit==" in DEV_REQS
    assert "bandit==" in DEV_REQS


def test_runtime_dependencies_are_exactly_pinned():
    # كل تبعية تشغيل مثبّتة بـ == (قابلية إعادة الإنتاج) — بما فيها starlette بعد إصلاح الثغرات.
    for line in REQS.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        assert "==" in line, f"تبعية غير مثبّتة: {line!r}"
