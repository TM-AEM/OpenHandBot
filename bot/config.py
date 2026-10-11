import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    openhands_api_key: str
    allowed_telegram_ids: frozenset[int] = field(default_factory=frozenset)
    openhands_base_url: str = "https://app.all-hands.dev"
    log_level: str = "INFO"
    watcher_interval: int = 25
    db_path: str = "bot_state.sqlite3"

    @property
    def api_base(self) -> str:
        return self.openhands_base_url.rstrip("/") + "/api/v1"

    @property
    def owner_id(self) -> int:
        """أول مستخدم مسموح، بيتبعت له إشعارات المراقب لو مفيش قايمة منفصلة."""
        return min(self.allowed_telegram_ids)

    def is_allowed(self, user_id: int | None) -> bool:
        return user_id in self.allowed_telegram_ids


class ConfigError(RuntimeError):
    pass


def _parse_ids(raw: str) -> frozenset[int]:
    ids: set[int] = set()
    for chunk in raw.replace(";", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            ids.add(int(chunk))
        except ValueError as exc:
            raise ConfigError("قايمة الـ ID المسموحة فيها قيمة مش رقم: " + chunk) from exc
    return frozenset(ids)


def load_config(env: dict | None = None) -> Config:
    if env is None:
        load_dotenv()
        env = os.environ

    missing = [
        name
        for name in ("TELEGRAM_BOT_TOKEN", "OPENHANDS_API_KEY", "ALLOWED_TELEGRAM_ID")
        if not env.get(name)
    ]
    if missing:
        raise ConfigError("متغيرات بيئة ناقصة: " + ", ".join(missing))

    allowed = _parse_ids(env["ALLOWED_TELEGRAM_ID"])
    if not allowed:
        raise ConfigError("ALLOWED_TELEGRAM_ID لازم يحتوي رقم واحد على الأقل")

    return Config(
        telegram_bot_token=env["TELEGRAM_BOT_TOKEN"],
        openhands_api_key=env["OPENHANDS_API_KEY"],
        allowed_telegram_ids=allowed,
        openhands_base_url=env.get("OPENHANDS_BASE_URL") or "https://app.all-hands.dev",
        log_level=env.get("LOG_LEVEL", "INFO"),
        watcher_interval=int(env.get("WATCHER_INTERVAL", "25")),
        db_path=env.get("DB_PATH", "bot_state.sqlite3"),
    )
