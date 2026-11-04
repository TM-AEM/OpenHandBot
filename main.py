"""نقطة تشغيل بوت OpenHandBot (long polling) — مع طبقة إقلاع Zero-Touch.

الترتيب: لوج مبكر ← إقلاع آمن (فحص متطلبات + تحقق إعداد + تجهيز مجلدات) ← بناء التطبيق ← polling.
مفيش عملية تانية ومفيش exec: نفس العملية بتفضل العملية الرئيسية (ملك polling واحد).
"""
from __future__ import annotations

import logging
import sys

from bot.app import build_application
from bot.bootstrap import BootstrapError, prepare_runtime, setup_logging
from bot.config import ConfigError


def _setup_logging(level: str, secrets: tuple[str, ...] = ()) -> None:
    """توافق خلفي: يفوّض لإعداد اللوج الموحّد في طبقة الإقلاع."""
    setup_logging(level, secrets)


def main() -> int:
    # OHB2-N10-18 (HIGH-1): لوج مبكر قبل أي فحص، عشان رسالة حالة الإقلاع (وتنقيح
    # الأسرار) تظهر فعلاً في اللوجز بدل ما تتوه قبل إعداد الـ logging.
    setup_logging()

    # إقلاع آمن: فحص المتطلبات، تحقق الإعداد، وتجهيز مجلدات التشغيل. أي حاجز ⇒
    # رسالة واضحة وخروج غير صفري (مفيش متابعة صامتة بعد فشل إعداد إلزامي).
    try:
        bootstrap = prepare_runtime()
    except ConfigError as exc:
        logging.getLogger("main").error("فشل الإعداد: %s", exc)
        print(f"خطأ في الإعداد: {exc}", file=sys.stderr)
        return 1
    except BootstrapError as exc:
        logging.getLogger("main").error("فشل الإقلاع: %s", exc)
        print(f"فشل الإقلاع: {exc}", file=sys.stderr)
        return 1

    config = bootstrap.config
    # إعادة تطبيق اللوج بمستوى `LOG_LEVEL` المحلول + تسجيل الأسرار للتنقيح.
    setup_logging(config.log_level, config.secrets)

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
