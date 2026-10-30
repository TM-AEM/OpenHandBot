"""نقطة تشغيل بوت OpenHandBot (long polling)."""
from __future__ import annotations

import logging
import sys

from bot.app import build_application
from bot.config import ConfigError, load_config
from bot.errors import RedactingFilter, register_secrets


def _setup_logging(level: str, secrets: tuple[str, ...] = ()) -> None:
    register_secrets(*secrets)
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # فلتر التنقيح على كل الـ handlers: أي سر يظهر في رسالة أو traceback يتخفّى.
    for handler in logging.getLogger().handlers:
        handler.addFilter(RedactingFilter())
    # httpx/httpcore بتسجّل URL كامل، وURL تيليجرام فيه التوكن.
    for noisy in ("httpx", "httpcore", "telegram", "apscheduler"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def main() -> int:
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"خطأ في الإعداد: {exc}", file=sys.stderr)
        return 1
    _setup_logging(config.log_level, config.secrets)

    app = build_application(config)
    # القرار (OHB2-02): `drop_pending_updates=True` **مقصود**. بعد أي restart/انقطاع،
    # التحديثات القديمة المتراكمة بتترمي بدل ما تتنفّذ كلها مرة واحدة. النتيجة التشغيلية:
    # أوامر/رسائل اتبعتت وقت البوت واقف مش هتتعالج. ده مقبول للاستخدام الفردي (المالك
    # بيتعامل مع البوت لايف)، وبيحمي من "طوفان" أوامر قديمة + تكرار أوامر بعد إعادة التشغيل.
    # تغيير السياسة دي عايز اختبارات لمعالجة التحديثات القديمة ومنع تكرار الأوامر (مؤجّل).
    app.run_polling(drop_pending_updates=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
