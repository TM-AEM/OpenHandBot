"""OHB2-N10-18 (HIGH-1): إثبات إن حالة الإقلاع بتظهر فعلاً في اللوجز + تنقيح الأسرار.

الخلفية: قبل الإصلاح كان `prepare_runtime()` بيسجّل حالة الإقلاع **قبل** إعداد الـ logging
في `main.py`، فالسطر كان بيتوه. دلوقتي `main.main()` بينادي `setup_logging()` الأول.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bot.bootstrap as boot  # noqa: E402


def _env(tmp_path: Path, **extra) -> dict:
    env = {
        "TELEGRAM_BOT_TOKEN": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        "OPENHANDS_API_KEY": "sk-test-not-real-key",
        "ALLOWED_TELEGRAM_ID": "1",
        "DB_PATH": str(tmp_path / "bot_state.sqlite3"),
    }
    env.update(extra)
    return env


def test_setup_logging_installs_redacting_filter():
    boot.setup_logging("INFO")
    root = logging.getLogger()
    assert root.handlers, "لازم يكون فيه handler واحد على الأقل بعد setup_logging"
    from bot.errors import RedactingFilter

    assert any(
        isinstance(f, RedactingFilter) for h in root.handlers for f in h.filters
    ), "فلتر التنقيح لازم يتركّب على الـ handlers"


def test_setup_logging_is_idempotent_and_applies_level():
    """نداء تاني مايضاعفش الـ handlers ويطبّق LOG_LEVEL على الجذر والـ handlers."""
    boot.setup_logging("INFO")
    n = len(logging.getLogger().handlers)
    boot.setup_logging("DEBUG")
    root = logging.getLogger()
    assert len(root.handlers) == n  # مفيش handlers مكرّرة
    assert root.level == logging.DEBUG
    assert all(h.level == logging.DEBUG for h in root.handlers)


def test_successful_bootstrap_emits_visible_readiness(caplog, tmp_path):
    boot.setup_logging("INFO")
    with caplog.at_level(logging.INFO, logger="bootstrap"):
        boot.prepare_runtime(_env(tmp_path), version_info=(3, 13, 0))
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "bootstrap status" in text
    assert "bootstrap=READY" in text
    assert "database=READY" in text


def test_readiness_log_is_backup_neutral(caplog, tmp_path):
    # OHB2-N10-25: حالة الإقلاع ما بتدّعيش أي جاهزية نسخ (مفيش backup=... خالص).
    boot.setup_logging("INFO")
    with caplog.at_level(logging.INFO, logger="bootstrap"):
        boot.prepare_runtime(_env(tmp_path), version_info=(3, 13, 0))
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "bootstrap=READY" in text
    assert "database=READY" in text
    assert "backup" not in text


def test_backup_env_does_not_change_readiness_log(caplog, tmp_path):
    kh = tmp_path / "known_hosts"
    kh.write_text("")
    boot.setup_logging("INFO")
    env = _env(
        tmp_path,
        SFTP_HOST="sftp.example",
        SFTP_USER="u",
        SFTP_PASSWORD="p",
        SFTP_KNOWN_HOSTS=str(kh),
    )
    with caplog.at_level(logging.INFO, logger="bootstrap"):
        res = boot.prepare_runtime(env, version_info=(3, 13, 0))
    assert res.ready is True
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "bootstrap=READY" in text
    assert "backup" not in text  # مفيش أي ادعاء نسخ حتى لو إعداد SFTP موجود


def test_readiness_log_has_no_secret_values(caplog, tmp_path):
    kh = tmp_path / "known_hosts"
    kh.write_text("")
    boot.setup_logging("INFO")
    env = _env(
        tmp_path,
        SFTP_HOST="sftp.example",
        SFTP_USER="u",
        SFTP_PASSWORD="topsecret-password",
        SFTP_KNOWN_HOSTS=str(kh),
    )
    with caplog.at_level(logging.INFO, logger="bootstrap"):
        boot.prepare_runtime(env, version_info=(3, 13, 0))
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert env["TELEGRAM_BOT_TOKEN"] not in text
    assert env["OPENHANDS_API_KEY"] not in text
    assert "topsecret-password" not in text


def test_main_failure_path_logs_and_prints(monkeypatch, capsys, tmp_path):
    """فشل الإعداد لازم يظهر في اللوج **و** في stderr (مش يختفي)."""
    import main as main_mod

    monkeypatch.setattr("bot.config.load_dotenv", lambda *a, **k: None)
    for k in ("TELEGRAM_BOT_TOKEN", "OPENHANDS_API_KEY", "ALLOWED_TELEGRAM_ID"):
        monkeypatch.delenv(k, raising=False)
    records: list[str] = []

    class _H(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    root = logging.getLogger()
    h = _H()
    root.addHandler(h)
    try:
        rc = main_mod.main()
    finally:
        root.removeHandler(h)

    assert rc == 1
    err = capsys.readouterr().err
    assert "خطأ في الإعداد" in err
    assert any("فشل الإعداد" in m for m in records), "الفشل لازم يتسجّل في اللوج كمان"


def test_main_sets_up_logging_before_bootstrap():
    """HIGH-1: `setup_logging()` لازم تتنادى **قبل** `prepare_runtime()` في `main()`.

    بنقارن أرقام السطور (ترتيب المصدر) مش ترتيب `ast.walk` (اللي BFS ومش مضمون).
    """
    import ast

    import main as main_mod

    src = Path(main_mod.__file__).read_text()
    tree = ast.parse(src)
    main_fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "main"
    )
    calls: dict[str, list[int]] = {"setup_logging": [], "prepare_runtime": []}
    for node in ast.walk(main_fn):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in calls
        ):
            calls[node.func.id].append(node.lineno)
    assert calls["setup_logging"], "main() لازم ينادي setup_logging"
    assert calls["prepare_runtime"], "main() لازم ينادي prepare_runtime"
    assert min(calls["setup_logging"]) < min(calls["prepare_runtime"]), (
        "setup_logging() لازم تتنادى قبل prepare_runtime() (HIGH-1)"
    )
