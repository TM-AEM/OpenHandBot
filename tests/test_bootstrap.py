"""OHB2-N10-16: اختبارات طبقة الإقلاع (bootstrap) — معزولة بالكامل.

مفيش أي اتصال شبكة أو خدمة حقيقية. بنستخدم بيئات مغلقة ومجلدات مؤقتة.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bot.bootstrap as boot  # noqa: E402
from bot.config import ConfigError  # noqa: E402


def _env(tmp_path: Path, **extra) -> dict:
    env = {
        "TELEGRAM_BOT_TOKEN": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        "OPENHANDS_API_KEY": "sk-test-not-real-key",
        "ALLOWED_TELEGRAM_ID": "1",
        "DB_PATH": str(tmp_path / "sub" / "bot_state.sqlite3"),
    }
    env.update(extra)
    return env


# ---------------------------------------------------------------- python check


def test_check_python_accepts_supported():
    boot.check_python((3, 11, 0))  # لا يرمي
    boot.check_python((3, 13, 5))
    boot.check_python((4, 0, 0))


def test_check_python_rejects_old():
    with pytest.raises(boot.BootstrapError):
        boot.check_python((3, 10, 9))
    with pytest.raises(boot.BootstrapError):
        boot.check_python((2, 7, 18))


# ---------------------------------------------------------------- happy path


def test_prepare_runtime_first_run_creates_dirs(tmp_path):
    env = _env(tmp_path)
    res = boot.prepare_runtime(env, version_info=(3, 13, 0))
    assert res.ready is True
    assert res.config.db_path == str(tmp_path / "sub" / "bot_state.sqlite3")
    assert (tmp_path / "sub").is_dir()  # مجلد الأب اتعمل
    assert res.status()["bootstrap"] == "READY"
    # OHB2-POST-PUB-01/F06: الإقلاع مابيفتحش القاعدة، فالقيمة الصادقة UNVERIFIED — مش
    # ادّعاء READY. الجاهزية المرجعية بتيجي من Database.run_startup_maintenance.
    assert res.status()["database"] == "UNVERIFIED"
    # الإقلاع مايدّعيش جاهزية أي ميزة خارج نواة التشغيل.
    assert "backup" not in res.status()


def test_prepare_runtime_is_idempotent(tmp_path):
    env = _env(tmp_path)
    r1 = boot.prepare_runtime(env, version_info=(3, 13, 0))
    r2 = boot.prepare_runtime(env, version_info=(3, 13, 0))
    assert r1.ready and r2.ready
    # الملف مااتعملش/مااتغيّرش (لسه مفيش قاعدة)
    assert not Path(r1.config.db_path).exists()


def test_prepare_runtime_repeated_startup_preserves_existing_db(tmp_path):
    db = tmp_path / "bot_state.sqlite3"
    db.write_bytes(b"EXISTING-DB-BYTES")
    env = _env(tmp_path, DB_PATH=str(db))
    boot.prepare_runtime(env, version_info=(3, 13, 0))
    boot.prepare_runtime(env, version_info=(3, 13, 0))
    assert db.read_bytes() == b"EXISTING-DB-BYTES"  # مفيش مسح/إعادة إنشاء


# ---------------------------------------------------------------- failures


def test_prepare_runtime_missing_mandatory_config(tmp_path):
    env = _env(tmp_path)
    del env["TELEGRAM_BOT_TOKEN"]
    with pytest.raises(ConfigError):
        boot.prepare_runtime(env, version_info=(3, 13, 0))


def test_prepare_runtime_invalid_config(tmp_path):
    env = _env(tmp_path, ALLOWED_TELEGRAM_ID="not-a-number")
    with pytest.raises(ConfigError):
        boot.prepare_runtime(env, version_info=(3, 13, 0))


def test_prepare_runtime_unsupported_python(tmp_path):
    with pytest.raises(boot.BootstrapError):
        boot.prepare_runtime(_env(tmp_path), version_info=(3, 9, 0))


def test_prepare_runtime_db_path_is_directory(tmp_path):
    d = tmp_path / "adir"
    d.mkdir()
    env = _env(tmp_path, DB_PATH=str(d))
    with pytest.raises(boot.BootstrapError):
        boot.prepare_runtime(env, version_info=(3, 13, 0))


def test_prepare_runtime_db_parent_not_writable(tmp_path, monkeypatch):
    env = _env(tmp_path)
    monkeypatch.setattr(boot.os, "access", lambda *a, **k: False)
    with pytest.raises(boot.BootstrapError):
        boot.prepare_runtime(env, version_info=(3, 13, 0))


def test_prepare_runtime_db_parent_creation_failure(tmp_path, monkeypatch):
    env = _env(tmp_path)

    def boom(*a, **k):
        raise OSError("nope")

    monkeypatch.setattr(boot.Path, "mkdir", boom)
    with pytest.raises(boot.BootstrapError):
        boot.prepare_runtime(env, version_info=(3, 13, 0))


# ---------------------------------------------------------------- unknown env vars


def test_unknown_env_vars_are_ignored_by_bootstrap(tmp_path):
    # إعداد أي ميزة خارج نواة الإقلاع — وجوده مايغيّرش أي حاجة.
    env = _env(tmp_path, SFTP_HOST="example.invalid", SFTP_USER="u")
    res = boot.prepare_runtime(env, version_info=(3, 13, 0))
    assert res.ready is True
    assert "backup" not in res.status()
    assert res.blockers == []


def test_status_has_no_secret_values(tmp_path):
    env = _env(tmp_path, SFTP_HOST="example.invalid")
    res = boot.prepare_runtime(env, version_info=(3, 13, 0))
    blob = repr(res.status())
    assert env["TELEGRAM_BOT_TOKEN"] not in blob
    assert env["OPENHANDS_API_KEY"] not in blob
