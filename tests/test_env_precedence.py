"""OHB2-N10-18 (HIGH-2): توافق `.env` + أولوية متغيّرات البيئة.

القواعد المطلوبة:
- متغيّرات بيئة العملية الحقيقية **تتفوّق** على `.env` (load_dotenv ما بيتجاوزش).
- `.env` لوحدها تكفي (مسار التطوير الموثّق `cp .env.example .env`).
- env مُمرّر صريح (اختبارات) يبقى حتمي ولا يقرأ `.env` المطوّر.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bot.bootstrap as boot  # noqa: E402
import bot.config as config  # noqa: E402

_ENV_KEYS = (
    "TELEGRAM_BOT_TOKEN",
    "OPENHANDS_API_KEY",
    "ALLOWED_TELEGRAM_ID",
    "DB_PATH",
)


def _write_env_file(directory: Path, **pairs: str) -> None:
    lines = [f"{k}={v}" for k, v in pairs.items()]
    (directory / ".env").write_text("\n".join(lines) + "\n")


@pytest.fixture()
def clean_process_env(monkeypatch):
    for k in _ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    return monkeypatch


def test_env_file_only(tmp_path, clean_process_env, monkeypatch):
    _write_env_file(
        tmp_path,
        TELEGRAM_BOT_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        OPENHANDS_API_KEY="sk-from-dotenv-file",
        ALLOWED_TELEGRAM_ID="1",
        DB_PATH=str(tmp_path / "s.sqlite3"),
    )
    monkeypatch.chdir(tmp_path)
    res = boot.prepare_runtime(version_info=(3, 13, 0))  # env=None ⇒ مسار التشغيل
    assert res.config.owner_id == 1
    assert res.config.db_path == str(tmp_path / "s.sqlite3")


def test_process_env_only(tmp_path, clean_process_env, monkeypatch):
    monkeypatch.chdir(tmp_path)  # مفيش .env
    for k in _ENV_KEYS:
        monkeypatch.setenv(
            k,
            {
                "TELEGRAM_BOT_TOKEN": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
                "OPENHANDS_API_KEY": "sk-process-env-value",
                "ALLOWED_TELEGRAM_ID": "7",
                "DB_PATH": str(tmp_path / "p.sqlite3"),
            }[k],
        )
    res = boot.prepare_runtime(version_info=(3, 13, 0))
    assert res.config.owner_id == 7


def test_process_env_wins_over_dotenv(tmp_path, clean_process_env, monkeypatch):
    _write_env_file(
        tmp_path,
        TELEGRAM_BOT_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        OPENHANDS_API_KEY="sk-dotenv-loses",
        ALLOWED_TELEGRAM_ID="1",
        DB_PATH=str(tmp_path / "dotenv.sqlite3"),
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ALLOWED_TELEGRAM_ID", "42")  # متغيّر البيئة لازم يغلب
    monkeypatch.setenv("OPENHANDS_API_KEY", "sk-process-env-wins")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "process.sqlite3"))
    res = boot.prepare_runtime(version_info=(3, 13, 0))
    assert res.config.owner_id == 42
    assert res.config.db_path == str(tmp_path / "process.sqlite3")


def test_explicit_env_is_deterministic_and_ignores_dotenv(tmp_path, monkeypatch):
    # .env موجود لكن لازم يتتجاهل تمامًا لما نمرّر env صريح.
    _write_env_file(
        tmp_path,
        TELEGRAM_BOT_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        OPENHANDS_API_KEY="sk-dotenv-must-be-ignored",
        ALLOWED_TELEGRAM_ID="999",
        DB_PATH=str(tmp_path / "ignored.sqlite3"),
    )
    monkeypatch.chdir(tmp_path)
    explicit = {
        "TELEGRAM_BOT_TOKEN": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        "OPENHANDS_API_KEY": "sk-explicit-injected",
        "ALLOWED_TELEGRAM_ID": "5",
        "DB_PATH": str(tmp_path / "explicit.sqlite3"),
    }
    res = boot.prepare_runtime(explicit, version_info=(3, 13, 0))
    assert res.config.owner_id == 5
    assert res.config.db_path == str(tmp_path / "explicit.sqlite3")


def test_missing_dotenv_and_no_env_raises(tmp_path, clean_process_env, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(config.ConfigError):
        boot.prepare_runtime(version_info=(3, 13, 0))


def test_malformed_dotenv_is_tolerated(tmp_path, clean_process_env, monkeypatch):
    # python-dotenv بترمي/تتجاهل الأسطر المشوهة؛ القيم الصحيحة الباقية لازم تُقرأ.
    (tmp_path / ".env").write_text(
        "this-is-not-a-valid-line\n"
        "TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11\n"
        "OPENHANDS_API_KEY=sk-from-malformed-file\n"
        "ALLOWED_TELEGRAM_ID=3\n"
        f"DB_PATH={tmp_path / 'm.sqlite3'}\n"
    )
    monkeypatch.chdir(tmp_path)
    res = boot.prepare_runtime(version_info=(3, 13, 0))
    assert res.config.owner_id == 3


def test_no_secret_from_dotenv_leaks_into_status(tmp_path, clean_process_env, monkeypatch):
    _write_env_file(
        tmp_path,
        TELEGRAM_BOT_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        OPENHANDS_API_KEY="sk-secret-dotenv-value",
        ALLOWED_TELEGRAM_ID="1",
        DB_PATH=str(tmp_path / "s.sqlite3"),
    )
    monkeypatch.chdir(tmp_path)
    res = boot.prepare_runtime(version_info=(3, 13, 0))
    blob = repr(res.status())
    assert "sk-secret-dotenv-value" not in blob
    assert "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11" not in blob
