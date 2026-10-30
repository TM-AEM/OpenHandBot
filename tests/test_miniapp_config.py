"""اختبارات إعدادات الـ Mini App الجديدة (OHB2-05)."""
from __future__ import annotations

import pytest

from bot.config import ConfigError, load_config

BASE_ENV = {
    "TELEGRAM_BOT_TOKEN": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
    "OPENHANDS_API_KEY": "secret-key-123456",
    "ALLOWED_TELEGRAM_ID": "555",
}


def env(**over):
    return {**BASE_ENV, **over}


def test_mini_app_defaults_are_off_and_safe():
    cfg = load_config(env())
    assert cfg.mini_app_enabled is False
    assert cfg.mini_app_port == 12000
    assert cfg.mini_app_initdata_max_age == 300
    assert cfg.mini_app_session_ttl == 3600
    assert cfg.mini_app_cookie_secure is True


def test_mini_app_enabled_parsed():
    assert load_config(env(MINI_APP_ENABLED="1")).mini_app_enabled is True
    assert load_config(env(MINI_APP_ENABLED="true")).mini_app_enabled is True
    assert load_config(env(MINI_APP_ENABLED="no")).mini_app_enabled is False
    assert load_config(env(MINI_APP_ENABLED="garbage")).mini_app_enabled is False


def test_mini_app_port_validation():
    assert load_config(env(MINI_APP_PORT="12001")).mini_app_port == 12001
    with pytest.raises(ConfigError):
        load_config(env(MINI_APP_PORT="0"))
    with pytest.raises(ConfigError):
        load_config(env(MINI_APP_PORT="70000"))
    with pytest.raises(ConfigError):
        load_config(env(MINI_APP_PORT="abc"))


def test_mini_app_positive_int_validation():
    assert load_config(env(MINI_APP_INITDATA_MAX_AGE="600")).mini_app_initdata_max_age == 600
    with pytest.raises(ConfigError):
        load_config(env(MINI_APP_INITDATA_MAX_AGE="-5"))
    with pytest.raises(ConfigError):
        load_config(env(MINI_APP_SESSION_TTL="0"))


def test_mini_app_cookie_secure_can_be_disabled_for_dev():
    assert load_config(env(MINI_APP_COOKIE_SECURE="0")).mini_app_cookie_secure is False
