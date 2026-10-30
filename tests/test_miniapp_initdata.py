"""اختبارات التحقق من initData بتاع Telegram Mini App (OHB2-05)."""
from __future__ import annotations

import time

import pytest

from bot.web.initdata import (
    DEFAULT_MAX_AGE,
    InitDataError,
    TelegramUser,
    validate_init_data,
)
from tests._miniapp_helpers import BOT_TOKEN, make_init_data, sign_init_data


def test_valid_initdata_returns_user():
    raw = make_init_data(555)
    user = validate_init_data(raw, BOT_TOKEN)
    assert isinstance(user, TelegramUser)
    assert user.id == 555
    assert user.display_name == "أحمد"


def test_invalid_signature_rejected():
    raw = make_init_data(555)
    # اقلب آخر حرفين من الـ hash ⇒ توقيع غلط.
    tampered = raw[:-2] + ("aa" if not raw.endswith("aa") else "bb")
    with pytest.raises(InitDataError):
        validate_init_data(tampered, BOT_TOKEN)


def test_wrong_bot_token_rejected():
    raw = make_init_data(555)
    with pytest.raises(InitDataError):
        validate_init_data(raw, "999999:ZZZ-DEF1234ghIkl-zyx57W2v1u123ew11")


def test_tampered_user_id_rejected():
    """تغيير user بعد التوقيع ⇒ التوقيع يقع (مفيش ثقة في id جاي من العميل)."""
    from urllib.parse import parse_qsl, urlencode

    fields = {
        "auth_date": str(int(time.time())),
        "query_id": "AAF",
        "user": '{"id": 555}',
    }
    good = sign_init_data(fields)
    original_hash = dict(parse_qsl(good))["hash"]
    forged = urlencode({**fields, "user": '{"id": 999}', "hash": original_hash})
    with pytest.raises(InitDataError):
        validate_init_data(forged, BOT_TOKEN)


def test_expired_auth_date_rejected():
    old = int(time.time()) - (DEFAULT_MAX_AGE + 60)
    raw = make_init_data(555, auth_date=old)
    with pytest.raises(InitDataError):
        validate_init_data(raw, BOT_TOKEN, max_age=DEFAULT_MAX_AGE)


def test_fresh_within_max_age_accepted():
    recent = int(time.time()) - 5
    raw = make_init_data(555, auth_date=recent)
    assert validate_init_data(raw, BOT_TOKEN, max_age=DEFAULT_MAX_AGE).id == 555


def test_future_auth_date_beyond_skew_rejected():
    future = int(time.time()) + 3600
    raw = make_init_data(555, auth_date=future)
    with pytest.raises(InitDataError):
        validate_init_data(raw, BOT_TOKEN)


def test_missing_hash_rejected():
    raw = make_init_data(555)
    without_hash = "&".join(p for p in raw.split("&") if not p.startswith("hash="))
    with pytest.raises(InitDataError):
        validate_init_data(without_hash, BOT_TOKEN)


def test_missing_user_rejected():
    fields = {"auth_date": str(int(time.time())), "query_id": "AAF"}
    raw = sign_init_data(fields)
    with pytest.raises(InitDataError):
        validate_init_data(raw, BOT_TOKEN)


def test_missing_auth_date_rejected():
    fields = {"query_id": "AAF", "user": '{"id": 555}'}
    raw = sign_init_data(fields)
    with pytest.raises(InitDataError):
        validate_init_data(raw, BOT_TOKEN)


def test_empty_and_none_rejected():
    with pytest.raises(InitDataError):
        validate_init_data("", BOT_TOKEN)
    with pytest.raises(InitDataError):
        validate_init_data(None, BOT_TOKEN)  # type: ignore[arg-type]


def test_missing_bot_token_rejected():
    raw = make_init_data(555)
    with pytest.raises(InitDataError):
        validate_init_data(raw, "")


def test_non_dict_user_rejected():
    import json

    fields = {
        "auth_date": str(int(time.time())),
        "query_id": "AAF",
        "user": json.dumps([1, 2, 3]),
    }
    raw = sign_init_data(fields)
    with pytest.raises(InitDataError):
        validate_init_data(raw, BOT_TOKEN)


def test_non_int_user_id_rejected():
    fields = {
        "auth_date": str(int(time.time())),
        "query_id": "AAF",
        "user": '{"id": "555"}',
    }
    raw = sign_init_data(fields)
    with pytest.raises(InitDataError):
        validate_init_data(raw, BOT_TOKEN)
