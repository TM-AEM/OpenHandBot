"""نقطة تشغيل بوت OpenHandBot (long polling) — مع طبقة إقلاع Zero-Touch.

الترتيب: لوج مبكر ← إقلاع آمن (فحص متطلبات + تحقق إعداد + تجهيز مجلدات) ← بناء التطبيق ← polling.
مفيش عملية تانية ومفيش exec: نفس العملية بتفضل العملية الرئيسية (ملك polling واحد).
"""
from __future__ import annotations

import asyncio
import logging
import sys

from bot.app import build_application
from bot.bootstrap import BootstrapError, prepare_runtime, setup_logging
from bot.config import ConfigError
from bot.polling import run_bot


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
    # OHB2-POST-PUB-01/F06: فحص تكامل القاعدة **قبل** أي polling — نتيجة الفحص مرجعية.
    # لو القاعدة تالفة/غير مؤكدة، بنرفض الإقلاع كله (مفيش polling، مفيش workers، مفيش
    # ادّعاء جاهزية). بنخزّن النتيجة على التطبيق عشان `_post_init` يعيد استخدامها بدل
    # تكرار الفحص. مفيش حذف/إعادة بناء تلقائية لقاعدة تالفة.
    # (دفاعي: التطبيق الحقيقي دايمًا عنده bot_data["db"]؛ ده يحمي نقاط اعتراض الاختبار.)
    db = getattr(app, "bot_data", {}).get("db")
    if db is not None and not db.run_startup_maintenance():
        app.bot_data["db_checked"] = True
        app.bot_data["startup_failed"] = "database_integrity"
        logging.getLogger("main").error(
            "إقلاع متوقف: فحص تكامل قاعدة البيانات فشل (%s). "
            "راجع القاعدة يدويًا — مفيش إصلاح/حذف تلقائي.",
            config.db_path,
        )
        print("فشل الإقلاع: فحص تكامل قاعدة البيانات فشل — مفيش تشغيل.", file=sys.stderr)
        return 1
    if db is not None:
        app.bot_data["db_checked"] = True
    # OHB2-STAGE2 (D0/D2): بنشغّل حلقة الاستطلاع المخصّصة بدل `run_polling`.
    # `Application` مبني بـ `updater(None)` ⇒ مفيش Updater ⇒ مفيش poller تاني؛ الحلقة الوحيدة
    # في `bot.polling` هي اللي بتسحب. الحلقة بتعمل `deleteWebhook(drop_pending_updates=False)`
    # وبتستأنف من الحدّ الدائم (`B+1`) أو `offset=None` لو مفيش حدّ ⇒ **المعلّق محفوظ دائمًا**
    # (بديل قرار OHB2-02 القديم `drop_pending_updates=True`، المعتمد صراحةً في Stage 2).
    asyncio.run(run_bot(app))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
