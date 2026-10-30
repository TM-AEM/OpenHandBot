"""التحقق من `Telegram.WebApp.initData` على السيرفر (OHB2-05).

المرجع: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app

قواعد أمنية غير قابلة للتفاوض:
- بنستخدم `Telegram.WebApp.initData` الخام بس (مش `initDataUnsafe`).
- بنتحقق من التوقيع (HMAC-SHA256) بمفتاح مشتق من توكن البوت: secret = HMAC_SHA256("WebAppData", token).
- بنتحقق من `auth_date` (الحداثة) و`hash` نفسهم قبل ما نثق في أي حقل.
- بنقرأ `id` المستخدم **بعد** نجاح التوقيع بس. ممنوع نثق في أي id جاي من الجافاسكريبت.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

# مهلة صلاحية افتراضية لـ initData (ثواني). تيليجرام بتوصّي بحد أقصى قصير.
DEFAULT_MAX_AGE = 300
# هامش تسامح للساعة المستقبلية (ثواني) — ساعات الأجهزة بتبقى مقدّمة شوية.
FUTURE_SKEW = 30
_HASH_KEY = "hash"
_SIGNATURE_KEY = "signature"  # Ed25519 (مش مستخدمينه؛ بنتجاهله بأمان)
_WEBAAP_DATA_KEY = b"WebAppData"


class InitDataError(RuntimeError):
    """initData غير صالح (ناقص/توقيع غلط/قديم). رسالة عامة بدون تفاصيل حساسة."""


@dataclass(frozen=True)
class TelegramUser:
    id: int
    first_name: str = ""
    last_name: str = ""
    username: str = ""
    language_code: str = ""
    is_premium: bool = False

    @property
    def display_name(self) -> str:
        name = (self.first_name + " " + self.last_name).strip()
        return name or (self.username or str(self.id))


def _secret_key(bot_token: str) -> bytes:
    return hmac.new(_WEBAAP_DATA_KEY, bot_token.encode(), hashlib.sha256).digest()


def _expected_hash(data_check_string: str, bot_token: str) -> str:
    return hmac.new(_secret_key(bot_token), data_check_string.encode(), hashlib.sha256).hexdigest()


def _data_check_string(pairs: list[tuple[str, str]]) -> str:
    """صفوف `key=value` مرتبة أبجديًا بالمفتاح ومفصولة بـ \\n، بدون hash/signature."""
    filtered = [(k, v) for k, v in pairs if k not in (_HASH_KEY, _SIGNATURE_KEY)]
    filtered.sort(key=lambda kv: kv[0])
    return "\n".join(f"{k}={v}" for k, v in filtered)


def validate_init_data(
    raw: str,
    bot_token: str,
    *,
    max_age: int = DEFAULT_MAX_AGE,
    now: float | None = None,
) -> TelegramUser:
    """يتحقق من initData ويرجّع المستخدم. يرمي `InitDataError` لو فيه أي مشكلة."""
    if not raw or not isinstance(raw, str):
        raise InitDataError("بيانات تهيئة ناقصة")
    if not bot_token:
        raise InitDataError("توكن البوت غير مهيّأ على السيرفر")

    try:
        pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=False)
    except ValueError as exc:
        raise InitDataError("صيغة بيانات التهيئة غلط") from exc

    fields: dict[str, str] = {}
    for key, value in pairs:
        fields.setdefault(key, value)

    provided_hash = fields.get(_HASH_KEY, "")
    if not provided_hash:
        raise InitDataError("التوقيع مفقود")

    expected = _expected_hash(_data_check_string(pairs), bot_token)
    # مقارنة ثابتة الزمن لمنع هجمات التوقيت.
    if not hmac.compare_digest(expected, provided_hash):
        raise InitDataError("التوقيع غير صحيح")

    auth_raw = fields.get("auth_date", "")
    if not auth_raw:
        raise InitDataError("تاريخ المصادقة مفقود")
    try:
        auth_date = int(auth_raw)
    except ValueError as exc:
        raise InitDataError("تاريخ المصادقة غير صالح") from exc

    current = int(now if now is not None else time.time())
    if auth_date > current + FUTURE_SKEW:
        raise InitDataError("تاريخ المصادقة في المستقبل")
    if max_age > 0 and current - auth_date > max_age:
        raise InitDataError("بيانات التهيئة منتهية")

    user_raw = fields.get("user", "")
    if not user_raw:
        raise InitDataError("بيانات المستخدم مفقودة")
    try:
        user = json.loads(user_raw)
    except (ValueError, TypeError) as exc:
        raise InitDataError("بيانات المستخدم غير صالحة") from exc
    if not isinstance(user, dict):
        raise InitDataError("بيانات المستخدم غير صالحة")

    user_id = user.get("id")
    if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0:
        raise InitDataError("معرّف المستخدم غير صالح")

    return TelegramUser(
        id=user_id,
        first_name=str(user.get("first_name") or ""),
        last_name=str(user.get("last_name") or ""),
        username=str(user.get("username") or ""),
        language_code=str(user.get("language_code") or ""),
        is_premium=bool(user.get("is_premium") or False),
    )
