import os
import re
from dataclasses import dataclass, field
from ipaddress import ip_address
from urllib.parse import urlsplit

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    openhands_api_key: str
    allowed_telegram_ids: frozenset[int] = field(default_factory=frozenset)
    owner_id: int = 0
    openhands_base_url: str = "https://app.all-hands.dev"
    log_level: str = "INFO"
    watcher_interval: int = 25
    db_path: str = "bot_state.sqlite3"
    # رابط الـ Mini App (HTTPS). فاضي = الميزة متوقفة (الزر بيقول "غير متاحة").
    mini_app_url: str = ""

    @property
    def secrets(self) -> tuple[str, str]:
        return (self.telegram_bot_token, self.openhands_api_key)

    def __repr__(self) -> str:  # ما نطبعش الأسرار لو الـ Config اتسجّل بالغلط
        return (
            f"Config(owner_id={self.owner_id}, base_url={self.openhands_base_url!r}, "
            f"interval={self.watcher_interval}, db_path={self.db_path!r})"
        )

    @property
    def api_base(self) -> str:
        return self.openhands_base_url.rstrip("/") + "/api/v1"

    def is_allowed(self, user_id: int | None) -> bool:
        return user_id in self.allowed_telegram_ids


class ConfigError(RuntimeError):
    """خطأ إعداد. الرسالة بتذكر اسم المتغير بس، مش قيمته (ممكن تكون سر)."""


_TOKEN_RE = re.compile(r"^\d{3,}:[A-Za-z0-9_-]{8,}$")
_URL_RE = re.compile(r"^https?://[^\s/]+(/\S*)?$")
MIN_INTERVAL = 5
MAX_INTERVAL = 3600
_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_LOOPBACK_HOSTS = {"localhost"}


def _is_loopback_host(host: str) -> bool:
    """هل المضيف loopback (تطوير محلي)؟ أي حاجة تانية بتتطلب HTTPS."""
    if not host:
        return False
    if host in _LOOPBACK_HOSTS:
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


def _clean(env, name: str, default: str = "") -> str:
    """يقرأ متغير بيئة، يشيل المسافات والأسطر الزيادة وعلامات التنصيص المحيطة."""
    value = (env.get(name) or default).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1].strip()
    return value


def _parse_ids(raw: str) -> list[int]:
    """يرجّع الـ IDs بترتيبهم في النص (بعد إزالة التكرار).

    القرار 5: مستخدم واحد بس مسموح. لو النص فيه أكتر من ID مختلف، بنرفض بوضوح
    (من غير ما نطبع القيم نفسها — ممكن تكون أسرار اتلزقت بالغلط).
    """
    ids: list[int] = []
    for chunk in raw.replace(";", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            value = int(chunk)
        except ValueError as exc:
            # ما نكرّرش القيمة في الرسالة: ممكن حد يكون لزّق سر بالغلط.
            raise ConfigError("ALLOWED_TELEGRAM_ID فيه قيمة مش رقم صحيح") from exc
        if value <= 0:
            raise ConfigError("ALLOWED_TELEGRAM_ID لازم يكون أرقام موجبة")
        if value not in ids:
            ids.append(value)
    if len(ids) > 1:
        raise ConfigError(
            "ALLOWED_TELEGRAM_ID لازم يكون مستخدم واحد بس (القرار 5) — "
            "شيل الزيادة وسيب ID واحد"
        )
    return ids


def load_config(env: dict | None = None) -> Config:
    if env is None:
        load_dotenv()
        env = os.environ

    token = _clean(env, "TELEGRAM_BOT_TOKEN")
    api_key = _clean(env, "OPENHANDS_API_KEY")
    allowed_raw = _clean(env, "ALLOWED_TELEGRAM_ID")

    missing = [
        name
        for name, value in (
            ("TELEGRAM_BOT_TOKEN", token),
            ("OPENHANDS_API_KEY", api_key),
            ("ALLOWED_TELEGRAM_ID", allowed_raw),
        )
        if not value
    ]
    if missing:
        raise ConfigError("متغيرات بيئة ناقصة: " + ", ".join(missing))

    if not _TOKEN_RE.match(token):
        raise ConfigError("TELEGRAM_BOT_TOKEN شكله غلط (المفروض زي 123456:ABC...)، راجع القيمة في BotFather")
    if len(api_key) < 8 or any(ch.isspace() or ord(ch) < 32 for ch in api_key):
        raise ConfigError("OPENHANDS_API_KEY شكله غلط (فيه مسافات أو قصير جداً)، انسخه تاني من الموقع")

    allowed = _parse_ids(allowed_raw)
    if not allowed:
        raise ConfigError("ALLOWED_TELEGRAM_ID لازم يحتوي رقم واحد على الأقل")

    base_url = _clean(env, "OPENHANDS_BASE_URL") or "https://app.all-hands.dev"
    if not _URL_RE.match(base_url):
        raise ConfigError("OPENHANDS_BASE_URL لازم يبدأ بـ http:// أو https://")
    # ممنوع إرسال مفتاح الـ API على HTTP عادي لمضيف خارجي (غير loopback).
    parts = urlsplit(base_url)
    if parts.scheme != "https" and not _is_loopback_host(parts.hostname or ""):
        raise ConfigError(
            "OPENHANDS_BASE_URL لازم يكون https:// لمضيف خارجي — "
            "HTTP العادي مسموح بس للتطوير المحلي (localhost/127.0.0.1)"
        )

    interval_raw = _clean(env, "WATCHER_INTERVAL", "25")
    try:
        interval = int(interval_raw)
    except ValueError as exc:
        raise ConfigError(
            f"WATCHER_INTERVAL لازم يكون رقم صحيح بين {MIN_INTERVAL} و{MAX_INTERVAL} ثانية"
        ) from exc
    if not MIN_INTERVAL <= interval <= MAX_INTERVAL:
        raise ConfigError(
            f"WATCHER_INTERVAL لازم يكون بين {MIN_INTERVAL} و{MAX_INTERVAL} ثانية"
        )

    log_level = (_clean(env, "LOG_LEVEL", "INFO") or "INFO").upper()
    if log_level not in _LOG_LEVELS:
        raise ConfigError("LOG_LEVEL لازم يكون واحد من: " + ", ".join(sorted(_LOG_LEVELS)))

    db_path = _clean(env, "DB_PATH") or "bot_state.sqlite3"

    # رابط الـ Mini App (اختياري). لو موجود لازم يكون https:// عام صالح.
    mini_app_url = _clean(env, "MINI_APP_URL")
    if mini_app_url:
        if not _URL_RE.match(mini_app_url) or not mini_app_url.startswith("https://"):
            raise ConfigError("MINI_APP_URL لازم يكون رابط https:// صالح")
        host = urlsplit(mini_app_url).hostname or ""
        if _is_loopback_host(host):
            raise ConfigError("MINI_APP_URL لازم يكون رابط عام (مش loopback) لأن تيليجرام بيفتحه من جهاز المستخدم")

    return Config(
        telegram_bot_token=token,
        openhands_api_key=api_key,
        allowed_telegram_ids=frozenset(allowed),
        owner_id=allowed[0],
        openhands_base_url=base_url,
        log_level=log_level,
        watcher_interval=interval,
        db_path=db_path,
        mini_app_url=mini_app_url,
    )
