"""OHB2-N10-16/N10-25: طبقة إقلاع محايدة للمنصة (Zero-Touch Deployment) — **بدون نسخ**.

المسؤولية: قبل ما نبني التطبيق، نتأكد من المتطلبات ونحضّر وقت التشغيل، ونبلّغ عن أي
حاجز بوضوح **بدون أسرار** و**بدون ادعاء نجاح كاذب**. مفيش تثبيت حزم (ده شغل منصة
الاستضافة)، ومفيش صلاحيات نظام، ومفيش عملية تانية.

OHB2-N10-25: الإقلاع **مستقل تمامًا** عن وحدة النسخ الاحتياطي — مفيش أي استيراد لـ
`tools.backup_sqlite` هنا. النسخ مش جزء من نواة التشغيل؛ غياب وحداته/إعداده/مفاتيحه
مالوش أي تأثير على الإقلاع، والتشخيصات ما بتدّعيش أي جاهزية نسخ.
"""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from bot.config import Config, load_config

log = logging.getLogger("bootstrap")

# أقل نسخة Python مدعومة (CI بيغطي 3.11 و3.13).
MIN_PYTHON = (3, 11)


@dataclass
class BootstrapResult:
    """نتيجة الإقلاع: الإعداد + الحالة + الحواجز (بدون أي سر)."""

    config: Config
    blockers: list[str] = field(default_factory=list)
    ready: bool = True

    def status(self) -> dict:
        """لقطة حالة آمنة (أسماء/أعلام بس — مفيش أي قيمة سر، ومفيش ادعاء نسخ)."""
        return {
            "bootstrap": "READY" if self.ready else "FAILED",
            "database": "READY",
            "blockers": list(self.blockers),
        }


class BootstrapError(RuntimeError):
    """فشل إقلاع حاجز (رسالة آمنة للطبع — بدون أسرار)."""


def check_python(version_info: tuple[int, ...] | None = None) -> None:
    """يتأكد إن نسخة Python مدعومة. يرمي BootstrapError لو أقدم من الحد."""
    vi = version_info if version_info is not None else sys.version_info[:3]
    if tuple(vi[:2]) < MIN_PYTHON:
        raise BootstrapError(
            f"نسخة Python غير مدعومة: {'.'.join(map(str, vi[:2]))} — "
            f"المطلوب {MIN_PYTHON[0]}.{MIN_PYTHON[1]} أو أحدث"
        )


def setup_logging(level: str = "INFO", secrets: tuple[str, ...] = ()) -> None:
    """OHB2-N10-18 (HIGH-1): إعداد لوج مبكر وآمن **قبل** أي فحص إقلاع.

    لازم يتنادى قبل `prepare_runtime()` عشان رسالة حالة الإقلاع (وتنقيح الأسرار) تظهر
    فعلاً. آمن يتنادى أكتر من مرة: بيضبط مستوى الجذر **والـ handlers** (عشان `LOG_LEVEL`
    يتطبّق حتى لو `basicConfig` بقى no-op بعد أول نداء).
    """
    from bot.errors import RedactingFilter, register_secrets

    register_secrets(*secrets)
    level_value = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(level=level_value, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(level_value)
    # فلتر التنقيح + مستوى الـ handlers على كل الـ handlers: أي سر يظهر في رسالة أو
    # traceback يتخفّى، و LOG_LEVEL يتطبّق فعلاً.
    for handler in root.handlers:
        handler.setLevel(level_value)
        if not any(isinstance(f, RedactingFilter) for f in handler.filters):
            handler.addFilter(RedactingFilter())
    # httpx/httpcore بتسجّل URL كامل، وURL تيليجرام فيه التوكن.
    for noisy in ("httpx", "httpcore", "telegram", "apscheduler"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _check_db_path(db_path: Path) -> None:
    """فحص مسار القاعدة قبل البناء: مايكونش مجلد، والأب يقدر يتكتب فيه."""
    if db_path.is_dir():
        raise BootstrapError("DB_PATH بيشاور على مجلد مش ملف قاعدة بيانات")
    parent = db_path.parent if str(db_path.parent) else Path(".")
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise BootstrapError(
            f"مجلد قاعدة البيانات مش موجود ومش ممكن يتعمل ({type(exc).__name__})"
        ) from exc
    if not os.access(parent, os.W_OK):
        raise BootstrapError("مجلد قاعدة البيانات مش قابل للكتابة (صلاحيات)")


def prepare_runtime(
    env: dict | None = None,
    *,
    version_info: tuple[int, ...] | None = None,
) -> BootstrapResult:
    """الإقلاع الآمن المتكرّر (idempotent): فحص → تحقق إعداد → تجهيز مجلدات.

    ما بيثبّتش حزم، وما بياخدش صلاحيات نظام، وما بيشغّلش أي عملية/تطبيق، وما بيلمسش النسخ.
    """
    check_python(version_info)

    # OHB2-N10-18 (HIGH-2): نحافظ على سلوك `.env` القديم بطريقة **حتمية**.
    # - env مُمرّر صريح (اختبارات) ⇒ نستخدمه زي ما هو، مفيش قراءة لأي `.env`.
    # - env=None (مسار التشغيل الحقيقي) ⇒ نحمّل `.env` من **مجلد العمل** فقط (مكان النشر
    #   الموثّق)، من غير تجاوز متغيّرات بيئة العملية (load_dotenv افتراضيًا override=False).
    if env is None:
        env_file = Path.cwd() / ".env"
        if env_file.is_file():
            from dotenv import load_dotenv

            load_dotenv(env_file, override=False)
        env = dict(os.environ)
        config = load_config(env)
    else:
        env = dict(env)
        config = load_config(env)

    db_path = Path(config.db_path)
    _check_db_path(db_path)

    result = BootstrapResult(config=config, blockers=[], ready=True)
    log.info("bootstrap status: %s", _format_status(result.status()))
    return result


def _format_status(status: dict) -> str:
    blockers = status.get("blockers") or []
    base = f"bootstrap={status['bootstrap']} database={status['database']}"
    if blockers:
        # الأسباب آمنة (نوع الخطأ/اسم المتغيّر بس — بدون قيم).
        base += " blockers=[" + "; ".join(blockers) + "]"
    return base
