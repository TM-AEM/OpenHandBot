import pytest

from bot.config import ConfigError, load_config


def test_loads_required_values():
    cfg = load_config(
        {
            "TELEGRAM_BOT_TOKEN": "t",
            "OPENHANDS_API_KEY": "k",
            "ALLOWED_TELEGRAM_ID": "123",
        }
    )
    assert cfg.allowed_telegram_id == 123
    assert cfg.openhands_base_url == "https://app.all-hands.dev"
    assert cfg.api_base == "https://app.all-hands.dev/api/v1"


def test_missing_values_raises():
    with pytest.raises(ConfigError):
        load_config({"TELEGRAM_BOT_TOKEN": "t"})


def test_bad_allowed_id_raises():
    with pytest.raises(ConfigError):
        load_config(
            {
                "TELEGRAM_BOT_TOKEN": "t",
                "OPENHANDS_API_KEY": "k",
                "ALLOWED_TELEGRAM_ID": "abc",
            }
        )


def test_api_base_strips_trailing_slash():
    cfg = load_config(
        {
            "TELEGRAM_BOT_TOKEN": "t",
            "OPENHANDS_API_KEY": "k",
            "ALLOWED_TELEGRAM_ID": "1",
            "OPENHANDS_BASE_URL": "https://example.test/",
        }
    )
    assert cfg.api_base == "https://example.test/api/v1"
