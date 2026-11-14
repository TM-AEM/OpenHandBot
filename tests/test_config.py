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


# =====================================================================
# OHB2-01: HTTPS enforcement — ممنوع HTTP عادي لمضيف خارجي
# =====================================================================
def _base(**over):
    env = {"TELEGRAM_BOT_TOKEN": TOKEN, "OPENHANDS_API_KEY": KEY, "ALLOWED_TELEGRAM_ID": "1"}
    env.update(over)
    return env


def test_http_external_base_url_is_rejected():
    with pytest.raises(ConfigError) as exc:
        load_config(_base(OPENHANDS_BASE_URL="http://app.all-hands.dev"))
    assert "https" in str(exc.value).lower()


def test_http_public_ip_is_rejected():
    with pytest.raises(ConfigError):
        load_config(_base(OPENHANDS_BASE_URL="http://8.8.8.8:8080"))


def test_https_external_base_url_is_accepted():
    cfg = load_config(_base(OPENHANDS_BASE_URL="https://app.all-hands.dev"))
    assert cfg.openhands_base_url == "https://app.all-hands.dev"


def test_http_loopback_is_allowed_for_local_dev():
    assert load_config(_base(OPENHANDS_BASE_URL="http://localhost:8000")).api_base == "http://localhost:8000/api/v1"
    assert load_config(_base(OPENHANDS_BASE_URL="http://127.0.0.1:8000")).api_base == "http://127.0.0.1:8000/api/v1"


def test_rejection_message_does_not_leak_url_credentials():
    with pytest.raises(ConfigError) as exc:
        load_config(_base(OPENHANDS_BASE_URL="http://user:secretpw@evil.test"))
    assert "secretpw" not in str(exc.value)


# =====================================================================
# OHB2-03: MINI_APP_URL (اختياري، لازم https عام)
# =====================================================================
def test_mini_app_url_defaults_empty():
    assert load_config(_base()).mini_app_url == ""


def test_mini_app_url_valid_https_accepted():
    cfg = load_config(_base(MINI_APP_URL="https://app.example.com/mini"))
    assert cfg.mini_app_url == "https://app.example.com/mini"


def test_mini_app_url_http_rejected():
    with pytest.raises(ConfigError):
        load_config(_base(MINI_APP_URL="http://app.example.com/mini"))


def test_mini_app_url_loopback_rejected():
    with pytest.raises(ConfigError):
        load_config(_base(MINI_APP_URL="https://localhost:8000/mini"))


def test_mini_app_url_garbage_rejected():
    with pytest.raises(ConfigError):
        load_config(_base(MINI_APP_URL="not a url"))
