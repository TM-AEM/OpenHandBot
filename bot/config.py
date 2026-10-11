import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    openhands_api_key: str
    allowed_telegram_id: int
    openhands_base_url: str = "https://app.all-hands.dev"
    log_level: str = "INFO"
    watcher_interval: int = 25
    db_path: str = "bot_state.sqlite3"

    @property
    def api_base(self) -> str:
        return self.openhands_base_url.rstrip("/") + "/api/v1"


class ConfigError(RuntimeError):
    pass


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

    try:
        allowed_id = int(env["ALLOWED_TELEGRAM_ID"])
    except ValueError as exc:
        raise ConfigError("ALLOWED_TELEGRAM_ID لازم يكون رقم") from exc

    return Config(
        telegram_bot_token=env["TELEGRAM_BOT_TOKEN"],
        openhands_api_key=env["OPENHANDS_API_KEY"],
        allowed_telegram_id=allowed_id,
        openhands_base_url=env.get("OPENHANDS_BASE_URL") or "https://app.all-hands.dev",
        log_level=env.get("LOG_LEVEL", "INFO"),
        watcher_interval=int(env.get("WATCHER_INTERVAL", "25")),
        db_path=env.get("DB_PATH", "bot_state.sqlite3"),
    )
