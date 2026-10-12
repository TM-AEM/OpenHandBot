import pytest

from bot.config import ConfigError, load_config

TOKEN = "123456:ABCdef-ghiJKL_mnoPQR"
KEY = "sk-oh-test-key-123456"


def test_loads_required_values():
    cfg = load_config(
        {
            "TELEGRAM_BOT_TOKEN": TOKEN,
            "OPENHANDS_API_KEY": KEY,
            "ALLOWED_TELEGRAM_ID": "123",
        }
    )
    assert cfg.allowed_telegram_ids == frozenset({123})
    assert cfg.owner_id == 123
    assert cfg.is_allowed(123)
    assert not cfg.is_allowed(456)
    assert cfg.openhands_base_url == "https://app.all-hands.dev"
    assert cfg.api_base == "https://app.all-hands.dev/api/v1"


def test_multiple_allowed_ids_are_rejected():
    # القرار 5: مستخدم واحد بس. أي أكتر من ID ⇒ رفض واضح (بدون طباعة القيم).
    with pytest.raises(ConfigError) as exc:
        load_config(
            {
                "TELEGRAM_BOT_TOKEN": TOKEN,
                "OPENHANDS_API_KEY": KEY,
                "ALLOWED_TELEGRAM_ID": "10, 20;30",
            }
        )
    assert "مستخدم واحد" in str(exc.value)
    assert "10" not in str(exc.value) and "20" not in str(exc.value)  # مفيش تسريب قيم


def test_duplicate_same_id_is_not_multiple():
    # تكرار نفس الـ ID (بفواصل/مسافات) مش "أكتر من مستخدم".
    cfg = load_config(
        {
            "TELEGRAM_BOT_TOKEN": TOKEN,
            "OPENHANDS_API_KEY": KEY,
            "ALLOWED_TELEGRAM_ID": "7, 7;7",
        }
    )
    assert cfg.allowed_telegram_ids == frozenset({7})
    assert cfg.owner_id == 7


def test_custom_interval_and_db_path():
    cfg = load_config(
        {
            "TELEGRAM_BOT_TOKEN": TOKEN,
            "OPENHANDS_API_KEY": KEY,
            "ALLOWED_TELEGRAM_ID": "1",
            "WATCHER_INTERVAL": "40",
            "DB_PATH": "/tmp/x.sqlite3",
        }
    )
    assert cfg.watcher_interval == 40
    assert cfg.db_path == "/tmp/x.sqlite3"


def test_missing_values_raises():
    with pytest.raises(ConfigError):
        load_config({"TELEGRAM_BOT_TOKEN": TOKEN})


def test_bad_allowed_id_raises():
    with pytest.raises(ConfigError):
        load_config(
            {
                "TELEGRAM_BOT_TOKEN": TOKEN,
                "OPENHANDS_API_KEY": KEY,
                "ALLOWED_TELEGRAM_ID": "abc",
            }
        )


def test_api_base_strips_trailing_slash():
    cfg = load_config(
        {
            "TELEGRAM_BOT_TOKEN": TOKEN,
            "OPENHANDS_API_KEY": KEY,
            "ALLOWED_TELEGRAM_ID": "1",
            "OPENHANDS_BASE_URL": "https://example.test/",
        }
    )
    assert cfg.api_base == "https://example.test/api/v1"
