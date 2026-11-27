"""OHB2-AUTO-REVIEW-R2: إعدادات المراجعة المستقلة (معطّلة افتراضيًا)."""

from __future__ import annotations

import io
import logging

import pytest

from bot.config import ConfigError, load_config
from bot.errors import RedactingFilter, register_secrets

TOKEN = "123456:ABCdef-ghiJKL_mnoPQR"
KEY = "sk-oh-test-key-123456"
REVIEWER_KEY = "sk-reviewer-test-SENTINEL-123456"
GITHUB_TOKEN = "ghp_review_SENTINEL_123456"


def env(**over):
    base = {
        "TELEGRAM_BOT_TOKEN": TOKEN,
        "OPENHANDS_API_KEY": KEY,
        "ALLOWED_TELEGRAM_ID": "1",
    }
    base.update(over)
    return base


def review_env(**over):
    base = env()
    base.update(
        {
            "REVIEW_ENABLED": "1",
            "REVIEW_REPOS": "Owner/Repo, Other/Repo",
            "REVIEWER_PROVIDER": "testprovider",
            "REVIEWER_API_BASE": "https://reviewer.invalid/v1",
            "REVIEWER_API_KEY": REVIEWER_KEY,
            "REVIEWER_MODEL": "reviewer-model-v1",
            "REVIEW_GITHUB_TOKEN": GITHUB_TOKEN,
            "REVIEW_MAX_INPUT_CHARS": "50000",
            "REVIEW_CI_TIMEOUT_MIN": "10",
            "REVIEW_AUTOFIX_ROUNDS": "0",
        }
    )
    base.update(over)
    return base


def test_review_disabled_by_default():
    cfg = load_config(env())
    assert cfg.review_enabled is False
    assert cfg.review_autofix_rounds == 0
    assert cfg.review_repos == frozenset()
    assert cfg.reviewer_provider == ""
    assert cfg.reviewer_api_base == ""
    assert cfg.reviewer_api_key == ""
    assert cfg.reviewer_model == ""
    assert cfg.review_github_token == ""
    assert cfg.review_max_input_chars == 120_000
    assert cfg.review_ci_timeout_min == 15


def test_empty_optional_credentials_accepted_while_disabled():
    cfg = load_config(
        env(
            REVIEW_ENABLED="0",
            REVIEW_REPOS="",
            REVIEWER_PROVIDER="",
            REVIEWER_API_BASE="",
            REVIEWER_API_KEY="",
            REVIEWER_MODEL="",
            REVIEW_GITHUB_TOKEN="",
        )
    )
    assert cfg.review_enabled is False
    assert cfg.secrets == (TOKEN, KEY)


@pytest.mark.parametrize(
    "missing",
    [
        "REVIEW_REPOS",
        "REVIEWER_PROVIDER",
        "REVIEWER_API_BASE",
        "REVIEWER_API_KEY",
        "REVIEWER_MODEL",
        "REVIEW_GITHUB_TOKEN",
    ],
)
def test_enabled_requires_each_review_setting(missing):
    values = review_env()
    values.pop(missing)
    with pytest.raises(ConfigError) as info:
        load_config(values)
    message = str(info.value)
    assert missing in message
    assert REVIEWER_KEY not in message
    assert GITHUB_TOKEN not in message


def test_enabled_accepts_full_config_and_normalizes():
    cfg = load_config(
        review_env(
            REVIEW_REPOS=" Owner/Repo ; Other/Repo ",
            REVIEWER_PROVIDER="TestProvider",
            REVIEWER_API_BASE="https://reviewer.invalid/v1/",
        )
    )
    assert cfg.review_enabled is True
    assert cfg.review_repos == frozenset({"owner/repo", "other/repo"})
    assert cfg.reviewer_provider == "testprovider"
    assert cfg.reviewer_api_base == "https://reviewer.invalid/v1"
    assert cfg.reviewer_model == "reviewer-model-v1"
    assert cfg.review_max_input_chars == 50000
    assert cfg.review_ci_timeout_min == 10
    assert cfg.review_autofix_rounds == 0
    assert cfg.secrets == (TOKEN, KEY, REVIEWER_KEY, GITHUB_TOKEN)


@pytest.mark.parametrize(
    "value",
    [
        "ftp://reviewer.invalid/v1",
        "http://reviewer.invalid/v1",
        "https://user:pass@reviewer.invalid/v1",
        "https://reviewer.invalid/v1?x=1",
        "https://reviewer.invalid/v1#frag",
        "not-a-url",
    ],
)
def test_invalid_reviewer_api_base_rejected(value):
    with pytest.raises(ConfigError) as info:
        load_config(review_env(REVIEWER_API_BASE=value))
    message = str(info.value)
    assert "REVIEWER_API_BASE" in message
    assert REVIEWER_KEY not in message
    assert GITHUB_TOKEN not in message


@pytest.mark.parametrize(
    "over",
    [
        {"REVIEWER_PROVIDER": "bad provider"},
        {"REVIEWER_PROVIDER": "1bad"},
        {"REVIEWER_MODEL": "bad model"},
        {"REVIEWER_MODEL": "x" * 129},
    ],
)
def test_invalid_provider_or_model_rejected(over):
    with pytest.raises(ConfigError) as info:
        load_config(review_env(**over))
    message = str(info.value)
    assert "REVIEWER_" in message
    assert REVIEWER_KEY not in message
    assert GITHUB_TOKEN not in message


@pytest.mark.parametrize(
    "over",
    [
        {"REVIEW_MAX_INPUT_CHARS": "abc"},
        {"REVIEW_MAX_INPUT_CHARS": "0"},
        {"REVIEW_MAX_INPUT_CHARS": "999"},
        {"REVIEW_MAX_INPUT_CHARS": "1000001"},
        {"REVIEW_CI_TIMEOUT_MIN": "abc"},
        {"REVIEW_CI_TIMEOUT_MIN": "0"},
        {"REVIEW_CI_TIMEOUT_MIN": "121"},
        {"REVIEW_AUTOFIX_ROUNDS": "abc"},
        {"REVIEW_AUTOFIX_ROUNDS": "1"},
        {"REVIEW_AUTOFIX_ROUNDS": "-1"},
    ],
)
def test_invalid_numeric_settings_rejected(over):
    with pytest.raises(ConfigError) as info:
        load_config(review_env(**over))
    message = str(info.value)
    assert next(iter(over)) in message
    assert REVIEWER_KEY not in message
    assert GITHUB_TOKEN not in message


@pytest.mark.parametrize(
    "value",
    ["no-slash", "a/b/c", "a/", "/b", "a/..", "a b/c"],
)
def test_invalid_repo_allowlist_rejected(value):
    with pytest.raises(ConfigError) as info:
        load_config(review_env(REVIEW_REPOS=value))
    message = str(info.value)
    assert "REVIEW_REPOS" in message
    assert REVIEWER_KEY not in message
    assert GITHUB_TOKEN not in message


def test_repo_allowlist_normalization():
    cfg = load_config(
        review_env(REVIEW_REPOS=" Owner/Repo ; Other/Repo ")
    )
    assert cfg.review_repos == frozenset({"owner/repo", "other/repo"})


@pytest.mark.parametrize(
    "value",
    ["Owner/Repo, owner/repo", "owner/repo;OWNER/REPO"],
)
def test_repo_allowlist_duplicate_entries_are_rejected(value):
    with pytest.raises(ConfigError) as info:
        load_config(review_env(REVIEW_REPOS=value))
    assert "REVIEW_REPOS" in str(info.value)


def test_review_secrets_are_in_registry_and_not_in_repr_or_errors():
    cfg = load_config(review_env())
    assert REVIEWER_KEY in cfg.secrets
    assert GITHUB_TOKEN in cfg.secrets
    assert REVIEWER_KEY not in repr(cfg)
    assert GITHUB_TOKEN not in repr(cfg)

    with pytest.raises(ConfigError) as info:
        load_config(review_env(REVIEWER_API_BASE="http://reviewer.invalid/v1"))
    assert REVIEWER_KEY not in str(info.value)
    assert GITHUB_TOKEN not in str(info.value)


def test_review_secrets_are_redacted_in_logs():
    cfg = load_config(review_env())
    register_secrets(*cfg.secrets)
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(RedactingFilter())
    logger = logging.getLogger("test.review.secrets")
    logger.handlers = [handler]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.warning("reviewer=%s github=%s", cfg.reviewer_api_key, cfg.review_github_token)
    out = stream.getvalue()
    assert REVIEWER_KEY not in out
    assert GITHUB_TOKEN not in out


def test_non_empty_invalid_optional_credential_still_rejected():
    with pytest.raises(ConfigError) as info:
        load_config(env(REVIEW_ENABLED="0", REVIEWER_API_KEY="short"))
    assert "REVIEWER_API_KEY" in str(info.value)
    assert "short" not in str(info.value)


def test_invalid_review_enabled_value_rejected():
    with pytest.raises(ConfigError) as info:
        load_config(env(REVIEW_ENABLED="maybe"))
    assert "REVIEW_ENABLED" in str(info.value)
    assert "maybe" not in str(info.value)
