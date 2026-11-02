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


# ---------------------------------------------------------------- S1 (OHB2-06)
# التحقق من صيغة `hash` قبل المقارنة: أي قيمة مش 64 حرف hex تترفض كخطأ مصادقة
# منظّم (مفيش TypeError يوصل لـ Uvicorn).
def _signed_with_hash(fields: dict[str, str], bad_hash: str) -> str:
    from urllib.parse import urlencode

    return urlencode({**fields, "hash": bad_hash})


_FIELDS = {
    "auth_date": str(int(time.time())),
    "query_id": "AAF",
    "user": '{"id": 555}',
}


def test_non_ascii_hash_rejected():
    # القيمة دي كانت بتسبب TypeError (500) قبل الإصلاح.
    raw = _signed_with_hash(_FIELDS, "é" * 64)
    with pytest.raises(InitDataError):
        validate_init_data(raw, BOT_TOKEN)


def test_empty_hash_rejected():
    raw = _signed_with_hash(_FIELDS, "")
    with pytest.raises(InitDataError):
        validate_init_data(raw, BOT_TOKEN)


def test_short_hash_rejected():
    raw = _signed_with_hash(_FIELDS, "ab" * 10)  # 20 حرف < 64
    with pytest.raises(InitDataError):
        validate_init_data(raw, BOT_TOKEN)


def test_oversized_hash_rejected():
    raw = _signed_with_hash(_FIELDS, "a" * 128)
    with pytest.raises(InitDataError):
        validate_init_data(raw, BOT_TOKEN)


def test_non_hex_hash_rejected():
    raw = _signed_with_hash(_FIELDS, "z" * 64)
    with pytest.raises(InitDataError):
        validate_init_data(raw, BOT_TOKEN)


def test_valid_hex_but_wrong_hash_rejected():
    raw = _signed_with_hash(_FIELDS, "a" * 64)  # صيغة صحيحة لكن توقيع غلط
    with pytest.raises(InitDataError):
        validate_init_data(raw, BOT_TOKEN)


def test_official_telegram_test_vector():
    """فيكتور تيليجرام الرسمي (bots/webapps) — لازم يطابق بالظبط."""
    import hashlib
    import hmac
    from urllib.parse import urlencode

    bot_token = "5768337691:AAH5YkoiEuPk8-FZa32hStHTqXiLPtAEhx8"
    user = (
        '{"id":279058397,"first_name":"Vladislav","last_name":"Kibenko",'
        '"username":"vdkfrost","language_code":"ru","is_premium":true}'
    )
    fields = {
        "auth_date": "1662771648",
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": user,
    }
    expected = "c501b71e775f74ce10e377dea85a7ea24ecd640b223ea86dfe453e0eaed2e2b2"
    data_check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    assert hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest() == expected

    raw = urlencode({**fields, "hash": expected})
    parsed = validate_init_data(raw, bot_token, max_age=0, now=1662771648)
    assert parsed.id == 279058397
    assert parsed.display_name == "Vladislav Kibenko"
    assert parsed.username == "vdkfrost"
    assert parsed.language_code == "ru"
    assert parsed.is_premium is True
