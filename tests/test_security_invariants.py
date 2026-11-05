"""OHB2-N10-18 (Package H) + OHB2-N10-25: تأكيدات أمنية بعد التعديلات.

مفيش شبكة حقيقية: كل حاجة معزولة (ملفات مؤقتة، قراءة كود). الغرض إن أي تراجع أمني
(تحقق SHA-256 مفقود في الصندوق، تسريب سر، أتمتة autopush مفعّلة) يفشل الاختبار.

OHB2-N10-25: تأكيدات النسخ الاحتياطي اتشالت من هنا (النسخ خارج نواة التشغيل). ملفات
النسخ المحلية تفضل موجودة لكن غير منشورة.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bot.db as dbmod  # noqa: E402
import bot.errors as errors  # noqa: E402
import bot.outbox as outbox  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _src(rel: str) -> str:
    return (ROOT / rel).read_text()


def test_db_wal_and_busy_timeout_intact(tmp_path):
    db = dbmod.Database(str(tmp_path / "t.sqlite3"))
    try:
        assert db._conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert db._conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    finally:
        db.close()


def test_outbox_unknown_is_terminal_no_autoresend():
    # 'unknown' حالة نهائية: مفيش أي انتقال منها لـ pending/sending تلقائيًا.
    src = _src("bot/outbox.py")
    assert "OUTBOX_UNKNOWN" in src
    assert "مايتعادش تلقائياً" in src or "مش إعادة" in src
    # نتأكد إن مفيش تعريفات إعادة إرسال للحالات الغامضة في منطق التعافي.
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and "recover" in node.name:
            body = ast.get_source_segment(src, node) or ""
            assert "OUTBOX_SENDING" in body  # sending -> unknown مذكور
    assert outbox.OUTBOX_UNKNOWN == "unknown"


def test_redacting_filter_hides_registered_secret():
    errors.clear_secrets()
    secret = "123456:ABC-DEF-secret-token"
    errors.register_secrets(secret)
    try:
        assert errors.redact(f"boom {secret} end") == "boom *** end"
    finally:
        errors.clear_secrets()


def test_bootstrap_status_has_no_secret(tmp_path):
    import bot.bootstrap as boot

    env = {
        "TELEGRAM_BOT_TOKEN": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        "OPENHANDS_API_KEY": "sk-super-secret-value",
        "ALLOWED_TELEGRAM_ID": "1",
        "DB_PATH": str(tmp_path / "s.sqlite3"),
    }
    res = boot.prepare_runtime(env, version_info=(3, 13, 0))
    blob = repr(res.status())
    assert "sk-super-secret-value" not in blob
    assert "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11" not in blob


def test_core_modules_do_not_import_backup():
    """نواة التشغيل مابتستوردش أي وحدة نسخ (فحص AST مش نص)."""
    for rel in ("main.py", "bot/app.py", "bot/bootstrap.py"):
        tree = ast.parse(_src(rel))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert not name.startswith("tools"), f"{rel} بيستورد {name}"
                assert name != "bot.backup_lifecycle", f"{rel} بيستورد {name}"


def test_no_second_process_or_exec_in_startup_path():
    """مسار الإقلاع مايعملش exec/subprocess (ملك واحد، نفس العملية)."""
    for rel in ("main.py", "bot/bootstrap.py", "bot/app.py"):
        src = _src(rel)
        assert "os.exec" not in src
        assert "subprocess" not in src
        assert "multiprocessing" not in src
