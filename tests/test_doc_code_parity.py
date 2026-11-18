"""OHB2-WP-08 (NEW-DEF-08): اختبارات تكافؤ بين الكود والوثائق.

بتمنع انحراف صامت بين المصدر والوثائق التشغيلية:
- متغيّرات البيئة اللي بيعرّفها `bot/config.py` مقابل `.env.example` و`README.md`
  و`docs/OPERATIONS_RUNBOOK.md`.
- جداول SQLite اللي بيعملها `bot/db.py::_init_schema` مقابل ما بتذكره الوثائق.

قراءة ملفات المستودع فقط؛ مفيش شبكة ولا قاعدة حقيقية (نستخرج أسماء الجداول من نص
`_init_schema` عبر `sqlite3` في الذاكرة بدون تشغيل منطق التطبيق).
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CONFIG_SRC = (ROOT / "bot/config.py").read_text(encoding="utf-8")
DB_SRC = (ROOT / "bot/db.py").read_text(encoding="utf-8")
ENV_EXAMPLE = (ROOT / ".env.example").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
RUNBOOK = (ROOT / "docs/OPERATIONS_RUNBOOK.md").read_text(encoding="utf-8")


def _config_env_names() -> set[str]:
    """أسماء متغيّرات البيئة اللي بيقراها `load_config` (عبر `_clean`/`_parse_bool`/...)."""
    names = set(re.findall(r'_clean\(\s*env,\s*"([A-Z_]+)"', CONFIG_SRC))
    names |= set(re.findall(r'_parse_bool\(\s*env,\s*"([A-Z_]+)"', CONFIG_SRC))
    names |= set(re.findall(r'_positive\(\s*"([A-Z_]+)"', CONFIG_SRC))
    return names


def _env_example_names() -> set[str]:
    return set(re.findall(r"^([A-Z_]+)=", ENV_EXAMPLE, flags=re.M))


def _schema_tables() -> set[str]:
    """أسماء الجداول الفعلية من `_init_schema` (تشغيل SQL مقابل قاعدة في الذاكرة)."""
    start = DB_SRC.index("CREATE TABLE IF NOT EXISTS")
    schema_sql = DB_SRC[start: DB_SRC.index('"""', start)]
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(schema_sql)
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    finally:
        conn.close()
    return {r[0] for r in rows}


def test_env_example_covers_every_config_variable():
    config_names = _config_env_names()
    example_names = _env_example_names()
    missing = config_names - example_names
    assert not missing, f".env.example ناقص: {sorted(missing)}"


def test_config_has_no_env_var_absent_from_config_sources():
    # العكس: أي متغيّر في .env.example لازم يقرأه config.py (ما عدا ملفات لا يقرأها).
    config_names = _config_env_names()
    example_names = _env_example_names()
    unexpected = example_names - config_names
    assert not unexpected, f".env.example فيه متغيّرات مش معرّفة في config.py: {sorted(unexpected)}"


def test_readme_documents_every_config_variable():
    config_names = _config_env_names()
    missing = [n for n in config_names if f"`{n}`" not in README]
    assert not missing, f"README ناقص متغيّرات: {sorted(missing)}"


def test_runbook_documents_every_config_variable():
    config_names = _config_env_names()
    missing = [n for n in config_names if f"`{n}`" not in RUNBOOK]
    assert not missing, f"OPERATIONS_RUNBOOK ناقص متغيّرات: {sorted(missing)}"


def test_runbook_documents_every_schema_table():
    tables = _schema_tables()
    missing = [t for t in tables if f"`{t}`" not in RUNBOOK]
    assert not missing, f"OPERATIONS_RUNBOOK ناقص جداول: {sorted(missing)}"


def test_runbook_table_count_matches_schema():
    tables = _schema_tables()
    assert f"**{len(tables)}** جدول" in RUNBOOK, (
        f"RUNBOOK لازم يذكر عدد الجداول الصحيح ({len(tables)})"
    )
