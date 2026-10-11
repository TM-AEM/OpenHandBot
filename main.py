"""نقطة تشغيل بوت OpenHandBot (long polling)."""
from __future__ import annotations

import logging
import sys

from bot.app import build_application
from bot.config import ConfigError, load_config


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main() -> int:
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"خطأ في الإعداد: {exc}", file=sys.stderr)
        return 1
    _setup_logging(config.log_level)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    app = build_application(config)
    app.run_polling(drop_pending_updates=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
