"""OHB2-N10-25: إثبات أن نواة التشغيل مستقلة فعلاً عن وحدات النسخ الاحتياطي.

الطريقة: نمنع استيراد `tools*` و`bot.backup_lifecycle` من داخل عملية Python **جديدة**
(عبر حاجب على `sys.meta_path`)، وبعدين نستورد `main`/`bot.bootstrap`/`bot.app` ونبني
تطبيق نووي. لو النواة لسه بتعتمد على النسخ، الاستيراد هيفشل فورًا.

ده مش mock لدالة نسخ — ده حاجب استيراد حقيقي يثبت غياب الاعتماد بالكامل.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_BLOCKER = textwrap.dedent(
    """
    import sys

    BLOCKED_PREFIXES = ("tools", "bot.backup_lifecycle")

    class _BlockBackup:
        def find_spec(self, name, path=None, target=None):
            if any(name == p or name.startswith(p + ".") for p in BLOCKED_PREFIXES):
                raise ImportError(f"BLOCKED backup import: {name}")
            return None

    sys.meta_path.insert(0, _BlockBackup())
    """
)


def _run(code: str) -> subprocess.CompletedProcess:
    full = _BLOCKER + "\n" + textwrap.dedent(code)
    return subprocess.run(
        [sys.executable, "-c", full],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"},
        timeout=120,
    )


def test_main_imports_without_backup_modules():
    proc = _run("import main; print('OK')")
    assert proc.returncode == 0, f"import main فشل مع حجب النسخ:\n{proc.stdout}\n{proc.stderr}"
    assert "OK" in proc.stdout


def test_bootstrap_and_app_import_without_backup_modules():
    proc = _run("import bot.bootstrap, bot.app; print('OK')")
    assert proc.returncode == 0, proc.stderr
    assert "OK" in proc.stdout


def test_build_application_without_backup_modules():
    code = """
        from pathlib import Path
        import tempfile
        from bot.app import build_application
        from bot.config import Config

        tmp = tempfile.mkdtemp()
        cfg = Config(
            telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            openhands_api_key="k",
            allowed_telegram_ids=frozenset({1}),
            owner_id=1,
            db_path=str(Path(tmp) / "t.sqlite3"),
        )
        app = build_application(cfg)
        assert "backup_config" not in app.bot_data
        assert "backup_lifecycle" not in app.bot_data
        print("OK")
    """
    proc = _run(code)
    assert proc.returncode == 0, f"بناء التطبيق فشل مع حجب النسخ:\n{proc.stdout}\n{proc.stderr}"
    assert "OK" in proc.stdout


def test_prepare_runtime_without_backup_modules():
    code = """
        import tempfile
        from pathlib import Path
        import bot.bootstrap as boot

        tmp = tempfile.mkdtemp()
        env = {
            "TELEGRAM_BOT_TOKEN": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "OPENHANDS_API_KEY": "sk-test-not-real-key",
            "ALLOWED_TELEGRAM_ID": "1",
            "DB_PATH": str(Path(tmp) / "bot_state.sqlite3"),
        }
        res = boot.prepare_runtime(env, version_info=(3, 13, 0))
        assert res.ready is True
        assert "backup" not in res.status()
        print("OK")
    """
    proc = _run(code)
    assert proc.returncode == 0, f"الإقلاع فشل مع حجب النسخ:\n{proc.stdout}\n{proc.stderr}"
    assert "OK" in proc.stdout


def test_blocker_actually_blocks_backup_import():
    # شاهد سلبي: الحاجب نفسه شغّال (لو حاولنا نستورد وحدة نسخ هيفشل).
    proc = _run("import tools.backup_sqlite")
    assert proc.returncode != 0, "الحاجب المفروض يمنع استيراد وحدات النسخ"
    assert "BLOCKED backup import" in proc.stderr
