"""تخزين محلي آمن لمرفقات الدفعات (OHB2-P0 — Stage A1 + A2 + A4).

- **A1** (تحقّق/تخزين): جذر staging محلي + تحقّق آمن + تسلسل **row-first**.
- **A2** (دورة حياة الدفعة): ربط الملف بمستخدم+محادثة+دفعة، تثبيت `T0` (مهلة 15 دقيقة،
  بلا تمديد)، وتفويض الملكية/شاهد الحذف (fail closed).
- **A4** (كنس/انتهاء/مراقبة): `AttachmentReaper` — يفرض مهلة الدفعة (15 دقيقة من `T0`
  الثابت)، ينقل الدفعة المنتهية لـ `expired` ثم يکنّس بايتات الـ staging **بعد** القرار
  الدائم (DB-أولًا)، بترتيب آمن/idempotent/قابل لإعادة المحاولة. يُستدعى من **hook بدء
  التشغيل الموجود** فقط (مفيش worker/مجدول/عملية/مالك قاعدة جديد).

**خارج النطاق:** نص مصاحب/نية إرسال (A3)، نقل/تسليم بعيد أو عميل خارجي (B). مفيش
worker/process/مالك قاعدة تاني.

القواعد الأمنية (fail closed):
- **أسماء مُعتِمة فقط**: اسم ملف التخزين = توكن عشوائي (`secrets.token_hex`) بيتولّد
  محليًا؛ عمره ما بيُشتق من اسم المستخدم. اسم العرض بيتخزّن **كبيانات وصفية فقط** ولا
  يُستخدم كمسار أبدًا.
- **حصر في جذر الـ staging**: كل كتابة جوه `<مجلد قاعدة البيانات>/attachment_staging/`
  (وضع `0700`)، بفتح `O_CREAT|O_EXCL|O_NOFOLLOW` ⇒ مفيش استبدال صامت لملف قائم ومفيش
  تتبّع symlink. المسار النهائي بيتأكّد إنه جوه الجذر (defense-in-depth).
- **حدود**: سقف حجم لكل ملف (3 MiB — قيمة **مؤقّتة** PROVISIONAL، D-12) بيتفرض قبل
  الكتابة (الحجم المُعلَن) وأثناءها (الحجم الفعلي، بكتابة مقيّدة). سياسة النوع بترفض
  الأنواع التنفيذية/السكربتية بالامتداد وببصمة المحتوى (proposal §5.7).
- **row-first (F5)**: صف العنصر الدائم (status `pending`) يتسجّل **قبل** أي بايت؛ والحالة
  بتتحوّل لـ `stored` **بس** بعد كتابة كاملة + تحقّق. أي فشل ⇒ الصف يفضل `pending`
  (بلا `stored` وبلا إرسال) عشان كنس A4 يقدر يلاقيه. **مفيش ادّعاء exactly-once** —
  السلوك at-most-once، و SQLite والملفات **مخزنين منفصلين** (مفيش ادّعاء ذرّية عبرهما).

**حدود الموارد (OHB2-REPAIR-PLAN-01)** — تجعل مسار الإدخال/التخزين محدودًا ومقاومًا للفشل
بلا تغيير المعمارية أو سياسة المرفقات:
- **FIX-01**: التنزيل من تيليجرام **متدفّق** بسقف بايت صلب (`max_bytes`)؛ مُكرِّر البثّ
  (طبقة الـ handler) يرفع `AttachmentTooLargeError` عند التجاوز ⇒ رفض حجم مغلق.
- **FIX-02**: تحديد التنزيلات المتزامنة (semaphore) مطبّق في طبقة الـ handler
  (`bot/handlers.py`) حيث التنزيل الفعلي — **مفيش** أي مُجدول/عامل جديد في الوحدة دي.
- **FIX-03**: سقف **لكل دفعة** (عدد العناصر) وسقف **كلي** لبايتات جذر الـ staging؛ أي
  تجاوز ⇒ رفض مغلق (`REJECTED_QUOTA`) بلا كتابة جزئية.
- **FIX-04**: فرض صلاحية جذر الـ staging (`0700`) **يفشل مقفولًا** (فشل الفحص ⇒ رفض،
  مفيش ابتلاع صامت).

**مسارات استلام المرفقات (FIX-R04 / R-1) — كل مسار **مقبول** بحدّ فعلي على البايتات
المستلمة:**
- **بثّ HTTPX** (المسار الأساسي، شبكة تيليجرام): قراءة على قطع + عدّ تراكمي ⇒ توقّف فوري
  عند تجاوز السقف (سقف فعلي على الذاكرة).
- **قراءة ملف محلي مقيّدة** (سيرفر Bot API محلي/اختبار): قراءة على قطع بسقف صلب.
- **مرفوض (fail closed):** `File.download_to_memory` في `python-telegram-bot==22.8` بتلمّ
  **الرد كامل** في الذاكرة وتنادي `out.write(buf)` **مرّة واحدة** ⇒ **مش** مسار محدود،
  وعمره ما بيُقبل كسقف صلب. أي حالة تعتمد عليه (بلا URL بلا عميل بثّ، أو بلا ملف محلي)
  ⇒ `StagingError` (رفض)، **مش** رفض بعد التنزيل الكامل.

**OHB2-REPAIR-PLAN-01-REVIEW-FINDINGS (D-12 / Option A)** — القيم أعلاه للحدود الكمّية
(عدد لكل دفعة، وبايت كلي) تبقى **مؤقّتة (PROVISIONAL) وغير معتمَدة**، و**مش مفروضة
افتراضيًّا**: قرار المالك (Option A) = إبقاء فرض حصص D-12 **معطّلًا افتراضيًّا** لحد ما
يوافق المالك صراحةً، مع الحفاظ على الآلية جاهزة للتفعيل. الآلية **مش** بتتفعّل بأي مسار
ضمني/env/config: التفعيل يتطلّب تمرير حدّ صريح (`max_items_per_batch`/`max_total_bytes`/
`max_bytes_per_batch`) من كود معتمَد صراحةً. أي تفعيل مستقبلي يتطلّب موافقة مالك صريحة +
استراتيجية كنس/تعافٍ معتمَدة. الكنس **الانتهاكي** (LIFE-01) بيمشي من **tick عامل موجود**
(`Watcher`) — مفيش نقطة كنس عند الإدخال (R-3)، ومفيش عامل/مجدول/عملية جديدة.

**جدول الحدود (FIX-R05) — المرجع الوحيد لِما هو فعّال:**

| الحدّ | النوع | الافتراضي | الحالة | المُلاحظة |
| --- | --- | --- | --- | --- |
| `MAX_ATTACHMENT_BYTES` (3 MiB) | لكل ملف | **مفعّل** | سلامة موارد (مستقلّ) | مش D-12؛ حماية أساسية |
| `MAX_ITEMS_PER_BATCH` (10) | عدد/دفعة | **معطّل** | مؤقّت (D-12) | يتطلّب تفعيلًا صريحًا |
| `MAX_STAGING_TOTAL_BYTES` (64 MiB) | بايت كلي | **معطّل** | مؤقّت (D-12) | يتطلّب تفعيلًا صريحًا |
| `max_bytes_per_batch` | بايت/دفعة | **معطّل** (None) | مؤقّت (D-12) | تصميم مُهيّأ، بلا قيمة افتراضية |

- **D-12 لا يزال غير محسوم**؛ لا توجد حصّة D-12 مفروضة افتراضيًّا.
- حدّ الملف الواحد (3 MiB) **مستقلّ** ومفعّل دائمًا (سقف أمان موارد، مش سياسة منتج).
- التفعيل المستقبلي يتطلّب موافقة مالك صريحة + تمرير قيمة صريحة (لا افتراضية).
"""
from __future__ import annotations

import os
import secrets
import stat as _stat
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path

from . import files
from .db import (
    ATTACHMENT_BATCH_EXPIRED,
    ATTACHMENT_BATCH_PENDING,
    ATTACHMENT_BATCH_STATUSES,
    ATTACHMENT_BATCH_TTL,
    ATTACHMENT_ITEM_REAPED,
    ATTACHMENT_ITEM_STORED,
    AttachmentBatch,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------- سياسة الحجم/النوع
# القيم دي **مؤقّتة** (PROVISIONAL) لحد ما D-12 يتحدّد؛ الافتراضي متحفّظ وقابل للعكس.
MAX_ATTACHMENT_BYTES = 3 * 1024 * 1024  # 3 MiB (مطابق لسقف العميل في proposal §5.7)

# OHB2-REPAIR-PLAN-01/FIX-03: سقوف تخزين الـ staging (PROVISIONAL، متحفّظة وقابلة للعكس).
# القيم دي **مؤقّتة وغير معتمَدة** (D-12 غير محسوم). تحت قرار المالك Option A:
# **مش مفروضة افتراضيًّا** — الافتراضيات أدناه `None` = معطّل. القيم الرقمية محفوظة
# كمرجع للتفعيل المستقبلي الصريح فقط (مش تُستخدم كافتراضي).
MAX_ITEMS_PER_BATCH = 10                     # مرجع مؤقّت — غير مفروض افتراضيًّا (D-12)
MAX_STAGING_TOTAL_BYTES = 64 * 1024 * 1024   # مرجع مؤقّت — غير مفروض افتراضيًّا (D-12)

STAGING_DIRNAME = "attachment_staging"
STAGING_DIR_MODE = 0o700
STAGING_FILE_MODE = 0o600
_TOKEN_HEX_BYTES = 16  # ⇒ 32 محرف hex
_HEAD_BYTES = 4096
_MAX_DISPLAY_NAME = 200

# OHB2-LIFE-01: أقل فترة (ثواني) بين كنسين انتهاكيين متتاليين على tick عامل **موجود**.
# ثابت (مفيش مفتاح إعداد جديد) ⇒ الكنسة الكاملة ما بتشتغلش على كل تحديث/tick.
OPPORTUNISTIC_SWEEP_MIN_INTERVAL_SECONDS = 60.0

# امتدادات تنفيذية/سكربتية مرفوضة (سياسة §5.7: "any, except executable/script types").
_DENIED_EXTENSIONS = frozenset(
    {
        # تنفيذيات
        "exe", "dll", "so", "dylib", "bin", "com", "scr", "msi", "msp", "cpl", "ocx",
        "sys", "drv", "elf", "out", "run", "ko", "o", "a", "lib", "gadget",
        # سكربتات/تنفيذ (ويندوز)
        "bat", "cmd", "ps1", "psd1", "psm1", "vbs", "vbe", "js", "mjs", "cjs", "jse",
        "wsf", "wsh", "ws", "msc", "lnk", "reg", "hta", "pif", "shs", "application",
        # سكربتات (يونكس/عام)
        "sh", "bash", "zsh", "ksh", "csh", "fish", "py", "pyc", "pyo", "pyw", "rb",
        "pl", "pm", "php", "lua", "tcl", "awk", "sed",
        # جافا/أرشيف قابل للتنفيذ
        "jar", "class", "apk", "dex",
        # حِزم/تطبيقات
        "deb", "rpm", "dmg", "pkg", "appimage", "snap", "app", "command", "workflow",
    }
)

# بصمات magic-bytes لأنواع تنفيذية/سكربتية مرفوضة (فحص المحتوى الفعلي المكتوب).
_DENIED_MAGIC: tuple[bytes, ...] = (
    b"\x7fELF",          # ELF
    b"MZ",               # DOS/PE
    b"#!",               # shebang (سكربت)
    b"\xca\xfe\xba\xbe",  # Mach-O fat / Java class
    b"\xfe\xed\xfa\xce",  # Mach-O
    b"\xfe\xed\xfa\xcf",
    b"\xcf\xfa\xed\xfe",
)


class StagingError(RuntimeError):
    """خطأ إعداد/مسار في طبقة الـ staging (رسالة آمنة بلا مسارات مستخدم)."""


class AttachmentTooLargeError(RuntimeError):
    """OHB2-REPAIR-PLAN-01/FIX-01: تجاوز السقف الصلب **أثناء بثّ** التنزيل.

    يرفعه مُكرِّر البايتات (`chunks_factory`) لما مجموع البايتات المقروءة يعدّي السقف،
    عشان نوقف التنزيل فورًا (بلا لمّ الملف كامل في الذاكرة). `AttachmentService.accept`
    بيلتقطه ويترجمه لنتيجة `REJECTED_SIZE` (العنصر يفضل `pending` — فشل مغلق).
    """


class StageStatus(str, Enum):
    """نتيجة منظّمة لعملية تخزين (مفيش استثناءات بتتسرّب للمستدعي)."""

    STORED = "stored"                    # اتخزّن بنجاح + اتحوّل لـ `stored`
    REJECTED_SIZE = "rejected_size"      # أكبر من السقف
    REJECTED_TYPE = "rejected_type"      # نوع تنفيذي/سكربتي مرفوض
    REJECTED_NAME = "rejected_name"      # اسم غير صالح
    REJECTED_EMPTY = "rejected_empty"    # صفر بايت
    REJECTED_BATCH = "rejected_batch"    # الدفعة الأب مش موجودة/مش مملوكة/محادثتها غير صالحة
    REJECTED_QUOTA = "rejected_quota"    # تجاوز سقف الدفعة (عدد) أو السقف الكلي (FIX-03)
    WRITE_FAILED = "write_failed"        # فشل كتابة/مسار
    DB_FAILED = "db_failed"              # فشل قاعدة بيانات (fail closed)


@dataclass(frozen=True)
class StageResult:
    status: StageStatus
    item_id: str | None = None
    staging_token: str | None = None
    size_bytes: int = 0
    error: str | None = None

    @property
    def stored(self) -> bool:
        return self.status is StageStatus.STORED


class _TooLargeError(Exception):
    """تجاوز السقف أثناء الكتابة (قبل أي تجاوز فعلي للقرص)."""


class _CollisionError(Exception):
    """اسم مُعتِم موجود بالفعل ⇒ ممنوع استبداله صامتًا."""


# ------------------------------------------------------------------------ مساعدات
def new_staging_token() -> str:
    """توكن مُعتِم عشوائي لاسم ملف التخزين (مش مشتق من أي مدخل مستخدم)."""
    return secrets.token_hex(_TOKEN_HEX_BYTES)


def staging_root_for(db_path) -> Path:
    """جذر الـ staging = مجلد فرعي مخصّص جوه **مجلد قاعدة البيانات** (R4 §3.3)."""
    parent = Path(str(db_path)).expanduser().parent
    if str(parent) == "":
        parent = Path(".")
    return parent / STAGING_DIRNAME


def sanitize_display_name(name: str | None) -> str | None:
    """اسم عرض آمن **للبيانات الوصفية فقط** (عمره ما يُستخدم كمسار).

    بيشيل أي مكوّن مسار (نأخذ آخر مقطع)، ومحارف التحكّم/NUL، والنقاط الطرفية، ويقصّ الطول.
    """
    if not isinstance(name, str):
        return None
    base = name.replace("\\", "/").rsplit("/", 1)[-1]
    base = "".join(ch for ch in base if ch >= " " and ch != "\x7f")
    base = base.strip().strip(".")
    base = base[:_MAX_DISPLAY_NAME]
    return base or None


def extension_of(name: str | None) -> str:
    """الامتداد (حروف/أرقام) لآخر مقطع من الاسم، أو '' لو مفيش."""
    if not isinstance(name, str):
        return ""
    base = name.replace("\\", "/").rsplit("/", 1)[-1].strip().lower()
    if "." not in base:
        return ""
    ext = base.rsplit(".", 1)[-1]
    return ext if ext.isalnum() else ""


def ensure_staging_root(root: Path) -> Path:
    """ينشئ/يتأكّد من جذر الـ staging كمجلد آمن بصلاحية `0700`.

    بيرفض لو المسار symlink أو مش مجلد (منع تحويل الكتابة خارج الجذر).

    **FIX-04 (fail closed):** لو الصلاحية الفعلية مش `0700`، بنحاول `chmod`؛ ولو الفرض
    فشل (أو الصلاحية لسه غلط بعد المحاولة) ⇒ **بنرفض** (`StagingError`) بدل الابتلاع
    الصامت. الجذر بصلاحية أوسع من `0700` = تعرّض بايتات المرفقات لمستخدمين تانيين ⇒
    ماينفعش نكمل كتابة ونعلن نجاح.
    """
    root = Path(root)
    try:
        root.mkdir(mode=STAGING_DIR_MODE, parents=True, exist_ok=True)
    except OSError as exc:
        raise StagingError(f"تعذّر إنشاء مجلد الـ staging ({type(exc).__name__})") from exc
    if root.is_symlink() or not root.is_dir():
        raise StagingError("مسار الـ staging مش مجلد آمن")
    try:
        mode = os.stat(str(root)).st_mode & 0o777
    except OSError as exc:
        raise StagingError(f"تعذّر فحص صلاحية الـ staging ({type(exc).__name__})") from exc
    if mode != STAGING_DIR_MODE:
        try:
            os.chmod(str(root), STAGING_DIR_MODE)
        except OSError as exc:
            raise StagingError(
                f"تعذّر فرض صلاحية الـ staging 0700 ({type(exc).__name__})"
            ) from exc
        try:
            mode = os.stat(str(root)).st_mode & 0o777
        except OSError as exc:
            raise StagingError(
                f"تعذّر التحقّق من صلاحية الـ staging بعد الفرض ({type(exc).__name__})"
            ) from exc
        if mode != STAGING_DIR_MODE:
            raise StagingError("صلاحية الـ staging لسه مش 0700 بعد الفرض ⇒ رفض")
    return root


def _safe_unlink(path: Path) -> None:
    """حذف best-effort (يفشل بصمت) — بيمسح ملفاتنا الجزئية بس."""
    try:
        os.unlink(str(path))
    except OSError:
        pass


def _is_within(root: Path, path: Path) -> bool:
    root_r = os.path.realpath(str(root))
    path_r = os.path.realpath(str(path))
    return path_r == root_r or path_r.startswith(root_r + os.sep)


def staging_total_bytes(root: Path) -> int:
    """مجموع بايتات الملفات العادية في جذر الـ staging (FIX-03).

    بيعدّ **الملفات العادية بس** (`lstat`، بلا متابعة symlink) ⇒ مدخلات غير آمنة
    (symlink/مجلد) ما بتُحسبش ولا بتُتبع. جذر مفقود ⇒ 0. أي فشل قراءة ⇒ ينتشر
    (المستدعي يفشل مقفولًا بدل ما يقلّل العدّ بصمت).
    """
    root = Path(root)
    try:
        st = os.lstat(str(root))
    except FileNotFoundError:
        return 0
    if _stat.S_ISLNK(st.st_mode) or not _stat.S_ISDIR(st.st_mode):
        return 0
    total = 0
    for entry in root.iterdir():
        try:
            est = os.lstat(str(entry))
        except OSError:
            continue
        if _stat.S_ISREG(est.st_mode):
            total += est.st_size
    return total


def _is_denied_extension(name: str | None) -> bool:
    return extension_of(name) in _DENIED_EXTENSIONS


def _is_denied_magic(head: bytes) -> bool:
    return any(head.startswith(sig) for sig in _DENIED_MAGIC)


def _read_head(path: Path) -> bytes:
    with open(str(path), "rb") as handle:
        return handle.read(_HEAD_BYTES)


def precheck_rejection(
    display_name: str | None,
    declared_size: int | None,
    *,
    max_bytes: int = MAX_ATTACHMENT_BYTES,
) -> StageStatus | None:
    """فحوصات الرفض **الرخيصة** (قبل أي كتابة/صف): الامتداد + الحجم المُعلَن.

    مصدر واحد للسياسة (يمنع تباعد A2/A1). `None` = مقبول مبدئيًّا (التحقّق النهائي
    بالمحتوى/الحجم الفعلي بيفضل في `StagingStore.store`).
    """
    if _is_denied_extension(display_name):
        return StageStatus.REJECTED_TYPE
    if declared_size is not None and int(declared_size) > max_bytes:
        return StageStatus.REJECTED_SIZE
    return None


# ------------------------------------------------------------------ A2: دورة الحياة
# الحالات المؤهّلة للانضمام لملف جديد: الدفعة **pending** بس (لسه محتاجة نص مصاحب).
_ELIGIBLE_BATCH_STATUSES = frozenset({ATTACHMENT_BATCH_PENDING})


def new_batch_id() -> str:
    """معرّف دفعة مُعتِم (نفس نمط A1: `secrets.token_hex`)."""
    return secrets.token_hex(_TOKEN_HEX_BYTES)


def new_item_id() -> str:
    """معرّف عنصر مُعتِم (نفس نمط A1)."""
    return secrets.token_hex(_TOKEN_HEX_BYTES)


def batch_deadline(t0: str, *, ttl: timedelta = ATTACHMENT_BATCH_TTL) -> datetime | None:
    """الموعد النهائي = `T0 + 15 دقيقة` (مرة واحدة، عمره ما بيتمدّد — I4/I6/§8.4).

    بترجّع None لو `t0` مش ختم ISO صالح (⇒ المستدعي يفشل مقفول).
    """
    start = _parse_t0(t0)
    if start is None:
        return None
    return start + ttl


def batch_is_expired(t0: str, now: datetime, *, ttl: timedelta = ATTACHMENT_BATCH_TTL) -> bool:
    """هل فاتت مهلة الدفعة؟ `now > T0 + 15د` (fail closed عند `t0` غير صالح)."""
    deadline = batch_deadline(t0, ttl=ttl)
    if deadline is None:
        return True
    return _as_utc(now) > deadline


def normalize_declared_size(value) -> int | None:
    """OHB2-P0-A2/A1-REV-F4: تطبيع الحجم المُعلَن غير الموثوق قبل تمريره لـ A1.

    - `None` ⇒ None (مفيش حجم معلَن؛ السقف المُتدفّق في A1 يفضل مرجعي).
    - `bool` ⇒ None (مش رقم حقيقي — نتجاهله بدل ما نعتبره 0/1).
    - `int` سالب ⇒ None.
    - `int` ≥ 0 ⇒ نفسه.
    - أي نوع تاني (نص/عشري/كائن) ⇒ **ValueError** (المستدعي يرفض بأمان).

    الحجم **الفعلي** المُتدفّق يفضل هو المرجع (A1)، والسقف المؤقّت (D-12) ما اتغيّرش.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    raise ValueError("declared_size غير صالح")


def _parse_t0(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
    return _as_utc(parsed)


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class BatchDecision(str, Enum):
    """قرار ربط ملف وارد بدفعة (A2)."""

    NEW = "new"          # مفيش دفعة مؤهّلة ⇒ دفعة جديدة (T0 دلوقتي)
    APPEND = "append"    # دفعة قائمة مؤهّلة ⇒ نضيف عنصر، T0 ثابت
    EXPIRED = "expired"  # فيه دفعة لسه pending بس فاتت مهلتها ⇒ ترفض الملف


@dataclass(frozen=True)
class BatchAcceptance:
    """نتيجة قبول/رفض ملف عند حدّ A2 (قبل ما A1 يكتب أي بايت)."""

    decision: BatchDecision
    batch: AttachmentBatch | None = None


def classify_incoming_file(
    db,
    *,
    telegram_id: int,
    conversation_id: str,
    now: datetime,
    ttl: timedelta = ATTACHMENT_BATCH_TTL,
) -> BatchAcceptance:
    """يقرّر إزاي الملف الوارد يتربط بالدفعة (قراءة فقط، بلا كتابة).

    - أحدث دفعة `pending` لنفس المستخدم+المحادثة:
      - **مؤهّلة** (لم تفُت المهلة) ⇒ `APPEND` (لا تمديد لـ `T0`).
      - **منتهية** ⇒ `EXPIRED` (ترفض الملف — مايتضمّنش لدفعة منتهية؛ المستدعي ينهيها
        وبيبدأ دفعة جديدة عند القبول، حسب R4 A1/A4).
    - مفيش دفعة `pending` ⇒ `NEW`.
    """
    existing = db.latest_pending_attachment_batch(int(telegram_id), conversation_id)
    if existing is None:
        return BatchAcceptance(BatchDecision.NEW, None)
    if existing.status not in _ELIGIBLE_BATCH_STATUSES:
        return BatchAcceptance(BatchDecision.NEW, None)
    if batch_is_expired(existing.t0, now, ttl=ttl):
        return BatchAcceptance(BatchDecision.EXPIRED, existing)
    return BatchAcceptance(BatchDecision.APPEND, existing)


# --------------------------------------------------------------------- المخزن
class StagingStore:
    """مخزن محلي آمن لبايتات المرفقات فوق `Database` الموجودة (مفيش مالك تاني).

    `db_path` بيحدّد مكان جذر الـ staging (بجانب قاعدة البيانات — نفس موقع الحالة).
    """

    def __init__(
        self,
        db,
        db_path,
        *,
        max_bytes: int = MAX_ATTACHMENT_BYTES,
        max_items_per_batch: int | None = None,
        max_total_bytes: int | None = None,
        max_bytes_per_batch: int | None = None,
    ) -> None:
        """`max_bytes` (سقف الملف) مفعّل دائمًا. باقي الحصص **معطّلة افتراضيًّا** (`None`)
        لحد موافقة المالك الصريحة (D-12 / Option A) — التفعيل بتمرير حدّ صريح من كود
        معتمَد، بلا أي مسار env/config ضمني.
        """
        self._db = db
        self._root = staging_root_for(db_path)
        self._max_bytes = int(max_bytes)
        self._max_items_per_batch = (
            None if max_items_per_batch is None else int(max_items_per_batch)
        )
        self._max_total_bytes = None if max_total_bytes is None else int(max_total_bytes)
        self._max_bytes_per_batch = (
            None if max_bytes_per_batch is None else int(max_bytes_per_batch)
        )

    @property
    def root(self) -> Path:
        return self._root

    @property
    def max_bytes(self) -> int:
        return self._max_bytes

    @property
    def max_items_per_batch(self) -> int | None:
        return self._max_items_per_batch

    @property
    def max_total_bytes(self) -> int | None:
        return self._max_total_bytes

    @property
    def max_bytes_per_batch(self) -> int | None:
        return self._max_bytes_per_batch

    @property
    def quota_enabled(self) -> bool:
        """هل أي حصّة D-12 مفعّلة؟ (الافتراضي: False ⇒ مفيش فرض)."""
        return (
            self._max_items_per_batch is not None
            or self._max_total_bytes is not None
            or self._max_bytes_per_batch is not None
        )

    def ensure_root(self) -> Path:
        return ensure_staging_root(self._root)

    def _batch_active_files(self, batch_id: str) -> tuple[int, int]:
        """FIX-R02: (عدد، مجموع بايتات) **الملفات الفعلية على القرص** لعناصر الدفعة.

        المحاسبة على **الموارد الفعلية** لا على الصفوف التاريخية: عنصر مرفوض/منتهي/مكنوس
        (بلا ملف) ما بيتحسبش ⇒ الرفض/الانتهاء ما بيستهلكش سعة دائمة. عنصر `stored` بيتحسب
        طول ما ملفه موجود. فشل قراءة القاعدة ينتشر (المستدعي يفشل مقفولًا).
        """
        root = self._root
        count = 0
        total = 0
        for it in self._db.list_attachment_items(batch_id):
            token = it.staging_token
            if not token or not files.is_safe_workspace_path(token):
                continue
            try:
                st = os.lstat(str(root / token))
            except OSError:
                continue
            if _stat.S_ISREG(st.st_mode):
                count += 1
                total += st.st_size
        return count, total

    def quota_block(self, batch_id: str, *, extra_items: int = 1) -> str | None:
        """FIX-03/R02: سقف عدد عناصر الدفعة (لو مفعّل صريحًا).

        بيعدّ **الملفات الفعلية** بس (مش الصفوف التاريخية) ⇒ المرفوض/المنتهي/المكنوس ما
        بيحجبش قبولًا صالحًا. `None` (معطّل) ⇒ مفيش فرض. فشل القراءة ينتشر (فشل مقفول).
        """
        if self._max_items_per_batch is None:
            return None
        if self._max_items_per_batch <= 0:
            return "batch_disabled"
        count, _ = self._batch_active_files(batch_id)
        if count + int(extra_items) > self._max_items_per_batch:
            return "batch_items"
        return None

    def byte_quota_block(self, batch_id: str, *, extra_bytes: int = 0) -> str | None:
        """FIX-R05: سقف بايتات الدفعة (لو مفعّل صريحًا) — على الملفات الفعلية."""
        if self._max_bytes_per_batch is None:
            return None
        if self._max_bytes_per_batch <= 0:
            return "batch_disabled"
        _, total = self._batch_active_files(batch_id)
        if total + int(extra_bytes) > self._max_bytes_per_batch:
            return "batch_bytes"
        return None

    def _effective_cap(self, batch_id: str) -> int:
        """أصغر سقف كتابة فعّال = min(سقف الملف، المتبقّي الكلي، المتبقّي للدفعة).

        الحصص المعطّلة (`None`) ما بتقيّدش. فشل القراءة ينتشر (المستدعي يفشل مقفولًا).
        """
        caps = [self._max_bytes]
        if self._max_total_bytes is not None:
            caps.append(self._max_total_bytes - staging_total_bytes(self._root))
        if self._max_bytes_per_batch is not None:
            _, used = self._batch_active_files(batch_id)
            caps.append(self._max_bytes_per_batch - used)
        return min(caps)

    # -- كتابة مقيّدة تحت اسم مُعتِم، محصورة في الجذر، بلا استبدال وبلا تتبّع symlink --
    def _write_to_path(self, path: Path, chunks, cap: int) -> int:
        try:
            fd = os.open(
                str(path),
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                STAGING_FILE_MODE,
            )
        except FileExistsError as exc:  # ملف قائم ⇒ ممنوع الاستبدال
            raise _CollisionError() from exc
        written = 0
        try:
            with os.fdopen(fd, "wb") as handle:
                for chunk in chunks:
                    if not chunk:
                        continue
                    if written + len(chunk) > cap:
                        raise _TooLargeError()
                    handle.write(chunk)
                    written += len(chunk)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            _safe_unlink(path)  # مفيش ملف جزئي يفضل باسم العنصر
            raise
        return written

    def store(
        self,
        *,
        telegram_id: int,
        batch_id: str,
        item_id: str,
        display_name: str | None = None,
        chunks=None,
        declared_size: int | None = None,
        row_created: bool = False,
        batch_acceptance: "BatchAcceptance | None" = None,
        staging_token: str | None = None,
    ) -> StageResult:
        """التسلسل row-first (F5): صف `pending` ⇒ كتابة ⇒ تحقّق ⇒ `stored`.

        `row_created=True` (A2): صف العنصر `pending` اتعمل **قبل** النداء (مع نتيجة
        التحديث ذرّيًّا) ⇒ ما نعملش INSERT تاني؛ التسلسل row-first محفوظ برضه (الصف
        موجود قبل أي بايت). `batch_acceptance` (A2) بيوثّق قرار الدفعة (NEW/APPEND) لكن
        الكتابة هنا بتعتمد على الـ `row_created` (الصف اتكتب فعلًا). `staging_token` (A2)
        لو اتحدّد بيُستخدم بدل توليد توكن جديد (عشان الصف الدائم يشير لبايتاته — F-1).
        """
        # (0) حراسة الملكية/الربط: الدفعة الأب لازم تكون موجودة ومملوكة للمستخدم ومعرّف
        #     محادثتها صالح (إعادة استخدام المدقّق القياسي). أي فشل ⇒ رفض مغلق.
        try:
            batch = self._db.get_attachment_batch(batch_id, telegram_id=int(telegram_id))
        except Exception as exc:  # noqa: BLE001 — فشل قاعدة ⇒ رفض مغلق
            return StageResult(StageStatus.DB_FAILED, item_id=item_id, error=type(exc).__name__)
        if batch is None or not files.is_valid_conversation_id(batch.conversation_id):
            return StageResult(StageStatus.REJECTED_BATCH, item_id=item_id)

        # (0b) الحجم المُعلَن (metadata) قبل أي استخدام للقرص.
        if declared_size is not None and int(declared_size) > self._max_bytes:
            return StageResult(StageStatus.REJECTED_SIZE, item_id=item_id)

        # (0c) سياسة النوع بالامتداد قبل أي كتابة.
        if _is_denied_extension(display_name):
            return StageResult(StageStatus.REJECTED_TYPE, item_id=item_id)

        safe_name = sanitize_display_name(display_name)
        token = staging_token or new_staging_token()
        if not files.is_safe_workspace_path(token):  # دفاع: التوكن مش مسار
            return StageResult(StageStatus.WRITE_FAILED, item_id=item_id)

        try:
            root = self.ensure_root()
        except StagingError as exc:
            return StageResult(
                StageStatus.WRITE_FAILED, item_id=item_id, staging_token=token, error=str(exc)
            )
        path = root / token
        if not _is_within(root, path):  # دفاع مزدوج: مفيش خروج من الجذر
            return StageResult(StageStatus.WRITE_FAILED, item_id=item_id, staging_token=token)

        # (0d) FIX-03/R02: سقف عدد عناصر الدفعة (لو مفعّل صريحًا). العدّ على **الملفات
        #      الفعلية** (مش الصفوف التاريخية) ⇒ المرفوض/المنتهي/المكنوس ما بيحجبش قبولًا.
        #      `extra_items=1` دايمًا: ملف العنصر الجديد لسه مش موجود على القرص (O_EXCL،
        #      توكن جديد) — حتى في A2 (`row_created=True`) الصف موجود لكن الملف لأ.
        try:
            quota = self.quota_block(batch_id, extra_items=1)
        except Exception as exc:  # noqa: BLE001 — فشل قاعدة/قرص أثناء الفحص ⇒ رفض مغلق
            return StageResult(StageStatus.DB_FAILED, item_id=item_id, error=type(exc).__name__)
        if quota is not None:
            return StageResult(StageStatus.REJECTED_QUOTA, item_id=item_id, staging_token=token)

        # (0f) FIX-R05: سقف بايتات الدفعة (لو مفعّل صريحًا) — على الملفات الفعلية.
        try:
            byte_quota = self.byte_quota_block(batch_id)
        except Exception as exc:  # noqa: BLE001 — فشل قاعدة/قرص ⇒ رفض مغلق
            return StageResult(StageStatus.DB_FAILED, item_id=item_id, error=type(exc).__name__)
        if byte_quota is not None:
            return StageResult(StageStatus.REJECTED_QUOTA, item_id=item_id, staging_token=token)

        # (0g) سقف الكتابة الفعّال = min(سقف الملف، المتبقّي الكلي، المتبقّي للدفعة). الحصص
        #      المعطّلة (`None`) ما بتقيّدش ⇒ الافتراضي سقف الملف (3 MiB) بس.
        try:
            cap = self._effective_cap(batch_id)
        except OSError as exc:
            return StageResult(
                StageStatus.WRITE_FAILED, item_id=item_id, staging_token=token,
                error=type(exc).__name__,
            )
        if cap <= 0:
            # سقف فعّال صفري/سالب ⇒ حصّة ممتلئة ⇒ رفض مغلق (بلا كتابة).
            return StageResult(StageStatus.REJECTED_QUOTA, item_id=item_id, staging_token=token)

        # (1) ROW-FIRST: سجل العنصر الدائم (status `pending`) **قبل** أي بايت.
        #     في A2 الصف اتعمل قبل النداء (مع النتيجة ذرّيًّا) ⇒ نتخطّى الإدراج.
        if not row_created:
            try:
                self._db.add_attachment_item(
                    item_id,
                    batch_id,
                    staging_token=token,
                    display_name=safe_name,
                    size_bytes=None,
                    status=ATTACHMENT_BATCH_PENDING,
                )
            except Exception as exc:  # noqa: BLE001 — فشل قاعدة ⇒ رفض مغلق (مفيش ادّعاء نجاح)
                return StageResult(StageStatus.DB_FAILED, item_id=item_id, error=type(exc).__name__)

        # (2) الكتابة تحت اسم مُعتِم، مقيّدة بالحجم/السقف الكلي.
        try:
            written = self._write_to_path(path, chunks if chunks is not None else (), cap)
        except _TooLargeError:
            # تجاوز السقف: لو السقف الفعّال هو الكلي ⇒ `REJECTED_QUOTA`؛ وإلا `REJECTED_SIZE`.
            status = (
                StageStatus.REJECTED_QUOTA if cap < self._max_bytes else StageStatus.REJECTED_SIZE
            )
            return StageResult(status, item_id=item_id, staging_token=token)
        except _CollisionError:
            return StageResult(
                StageStatus.WRITE_FAILED, item_id=item_id, staging_token=token, error="collision"
            )
        except OSError as exc:
            return StageResult(
                StageStatus.WRITE_FAILED, item_id=item_id, staging_token=token,
                error=type(exc).__name__,
            )

        # (3) تحقّق المحتوى الفعلي المكتوب (حجم/بصمة) — مفيش `stored` قبل كده.
        if written <= 0:
            _safe_unlink(path)
            return StageResult(StageStatus.REJECTED_EMPTY, item_id=item_id, staging_token=token)
        try:
            head = _read_head(path)
        except OSError as exc:
            _safe_unlink(path)
            return StageResult(
                StageStatus.WRITE_FAILED, item_id=item_id, staging_token=token,
                error=type(exc).__name__,
            )
        if _is_denied_magic(head):
            _safe_unlink(path)
            return StageResult(StageStatus.REJECTED_TYPE, item_id=item_id, staging_token=token)

        # (4) الانتقال لـ `stored` **بس** بعد كتابة كاملة + تحقّق.
        try:
            ok = self._db.set_attachment_item_status(
                item_id, ATTACHMENT_ITEM_STORED, size_bytes=written
            )
        except Exception as exc:  # noqa: BLE001 — فشل قاعدة ⇒ رفض مغلق
            _safe_unlink(path)
            return StageResult(
                StageStatus.DB_FAILED, item_id=item_id, staging_token=token,
                error=type(exc).__name__,
            )
        if not ok:  # مفيش صف اتحدّث ⇒ ما نعلنش نجاح
            _safe_unlink(path)
            return StageResult(StageStatus.DB_FAILED, item_id=item_id, staging_token=token)

        return StageResult(
            StageStatus.STORED, item_id=item_id, staging_token=token, size_bytes=written
        )


# --------------------------------------------------- A2: خدمة قبول المرفقات
class AcceptOutcome(str, Enum):
    """نتيجة قبول ملف عند حدّ A2."""

    ACCEPTED = "accepted"                  # اتقبل: صف عنصر دائم + نتيجة مؤهّلة
    STORED = "stored"                      # اتقبل + اتخزّن (بايتات كاملة)
    REJECTED = "rejected"                  # مرفوض قبل أي كتابة (نوع/حجم/حجم معلَن غير صالح)
    AUTH_FAILED = "auth_failed"            # فشل تفويض المحادثة (fail closed)
    DUPLICATE = "duplicate"                # تحديث مكرّر: مفيش قبول جديد ولا عنصر مُنشأ (F-4)


@dataclass(frozen=True)
class AcceptResult:
    outcome: AcceptOutcome
    batch_id: str | None = None
    item_id: str | None = None
    stage: StageStatus | None = None
    message: str | None = None


class AttachmentService:
    """A2: يربط الملفات بمستخدم+محادثة+دفعة، يثبّت `T0` عند أول ملف، وما يمدّدش المهلة.

    تسلسل القبول (fail-closed، R4 A2):
      1. تفويض المحادثة (ملكية/شاهد حذف) **قبل** أي قبول دائم.
      2. فحوصات الرفض الرخيصة (نوع/حجم معلَن).
      3. تصنيف الدفعة: دفعة `pending` **منتهية** ⇒ رفض الملف (بلا كتابة)؛ دفعة مؤهّلة ⇒
         APPEND (بلا تمديد `T0`)؛ مفيش ⇒ NEW (`T0 = now`).
      4. كتابة **النية الدائمة** (صف عنصر `pending`) + نتيجة التحديث ذرّيًّا (row-first).
      5. تنزيل البايتات (مقيّدة) ⇒ A1 يكتبها ويتحقّق ⇒ `stored`.

    **مفيش إرسال بعيد** (A3/B)، ومفيش نص مصاحب (A3)، ومفيش تمديد للمهلة (I6).
    """

    def __init__(self, db, store: StagingStore, client, identity, *, max_bytes=None) -> None:
        self._db = db
        self._store = store
        self._client = client
        self._identity = identity
        self._max_bytes = int(max_bytes if max_bytes is not None else store.max_bytes)

    @property
    def store(self) -> StagingStore:
        """مخزن الـ staging (للوصول لسقف الملف عند بناء مُكرِّر التنزيل — FIX-01)."""
        return self._store

    async def _authorized(self, conversation_id: str, *, db):
        """تفويض المحادثة (ملكية/معرّف/شاهد حذف، فشل مغلق) — نفس تنفيذ كل المسارات."""
        conv, status, _message, _exc = await files.authorize_conversation_detailed(
            self._client, self._identity, conversation_id, db
        )
        return conv, status

    async def accept(
        self,
        *,
        telegram_id: int,
        conversation_id: str,
        display_name: str | None,
        declared_size,
        update_id: int | None,
        now: datetime,
        chunks_factory=None,
    ) -> AcceptResult:
        """يقبل/يرفض ملفًا واردًا. `chunks_factory()` بترجّع مُكرِّر بايتات عند الطلب."""
        # (1) تفويض المحادثة قبل أي قبول دائم (fail closed).
        try:
            conv, status = await self._authorized(conversation_id, db=self._db)
        except Exception as exc:  # noqa: BLE001 — أي فشل تفويض ⇒ رفض مغلق
            return AcceptResult(AcceptOutcome.AUTH_FAILED, message=type(exc).__name__)
        if conv is None:
            return AcceptResult(AcceptOutcome.AUTH_FAILED, message=str(status))

        # (2) تطبيع/فحص الحجم المُعلَن (A1-REV-F4) قبل أي كتابة.
        try:
            declared = normalize_declared_size(declared_size)
        except ValueError:
            return AcceptResult(AcceptOutcome.REJECTED, stage=StageStatus.REJECTED_SIZE)
        if declared is not None and declared > self._max_bytes:
            return AcceptResult(AcceptOutcome.REJECTED, stage=StageStatus.REJECTED_SIZE)
        pre = precheck_rejection(display_name, declared, max_bytes=self._max_bytes)
        if pre is not None:
            return AcceptResult(AcceptOutcome.REJECTED, stage=pre)

        now = _as_utc(now)
        now_iso = now.isoformat()
        item_id = new_item_id()
        # الاسم الآمن يُخزَّن كبيانات وصفية فقط (عمره ما يُستخدم كمسار) — F-2.
        safe_name = sanitize_display_name(display_name)
        # توكن البايتات يُولَّد **قبل** الصف الدائم عشان الصف يشير لملفه (A4 يقدر يكنسه) — F-1.
        staging_token = new_staging_token()

        # (3) تصنيف الدفعة (قراءة فقط). فشل قاعدة ⇒ ينتشر (المستدعي يسجّله فشل، مش نجاح).
        acceptance = classify_incoming_file(
            self._db, telegram_id=int(telegram_id), conversation_id=conversation_id, now=now
        )

        # (3b) R4: الدفعة المنتهية **ترفض الملف** (مايتضمّنش)، والملف **يبدأ دفعة جديدة**.
        #     بنوسم القديمة `expired` (بلا لمس `t0`) قبل إنشاء الجديدة.
        if acceptance.decision is BatchDecision.EXPIRED and acceptance.batch is not None:
            self._db.mark_attachment_batch_status(
                acceptance.batch.batch_id, ATTACHMENT_BATCH_EXPIRED, now=now_iso
            )
            acceptance = BatchAcceptance(BatchDecision.NEW, None)

        # (4) كتابة النية الدائمة (صف عنصر pending) + النتيجة، ذرّيًّا (row-first).
        #     تحديث مكرّر (`update_id` مسجّل قبل كده) ⇒ الكتابة ترجّع None ⇒ **مفيش عنصر
        #     جديد** ⇒ نرجع `DUPLICATE` **قبل** أي تنزيل/كتابة بايتات، وما نصنعش معرّف
        #     عنصر مُفبرَك (F-4). النتيجة الدائمة (duplicate_completed) اتكتبت ذرّيًّا جوّه.
        if acceptance.decision is BatchDecision.APPEND and acceptance.batch is not None:
            batch_id = self._db.accept_attachment_item(
                acceptance.batch,
                item_id=item_id,
                display_name=safe_name,
                now=now_iso,
                update_id=update_id,
                staging_token=staging_token,
            )
        else:
            batch_id = self._db.accept_attachment_item_into_new_batch(
                telegram_id=int(telegram_id),
                conversation_id=conversation_id,
                batch_id=new_batch_id(),
                item_id=item_id,
                t0=now_iso,
                display_name=safe_name,
                now=now_iso,
                update_id=update_id,
                staging_token=staging_token,
            )
        if batch_id is None:
            return AcceptResult(AcceptOutcome.DUPLICATE)

        # (5) تنزيل البايتات (مقيّدة) ⇒ A1 يكتبها ويتحقّق. أي فشل ⇒ العنصر يفضل pending.
        #     FIX-01: مُكرِّر البثّ (في طبقة الـ handler) يقف عند السقف الصلب ويرفع
        #     `AttachmentTooLargeError` (وقف التنزيل فورًا، بلا لمّ الملف في الذاكرة) ⇒
        #     نترجمه لرفض حجم مغلق (بلا `stored`). FIX-02 (تحديد التنزيلات المتزامنة)
        #     مطبّق في طبقة الـ handler (حيث التنزيل فعليًّا).
        try:
            chunks = await chunks_factory() if chunks_factory is not None else ()
        except AttachmentTooLargeError:
            return AcceptResult(
                AcceptOutcome.ACCEPTED, batch_id=batch_id, item_id=item_id,
                stage=StageStatus.REJECTED_SIZE,
            )
        stage = self._store.store(
            telegram_id=int(telegram_id),
            batch_id=batch_id,
            item_id=item_id,
            display_name=display_name,
            chunks=chunks,
            declared_size=declared,
            row_created=True,
            batch_acceptance=acceptance,
            staging_token=staging_token,
        )
        if stage.status is StageStatus.STORED:
            return AcceptResult(
                AcceptOutcome.STORED, batch_id=batch_id, item_id=item_id, stage=stage.status
            )
        return AcceptResult(
            AcceptOutcome.ACCEPTED, batch_id=batch_id, item_id=item_id, stage=stage.status
        )


# =========================================================== OHB2-P0-A4: الكنس/الانتهاء
class SweepOutcome(str, Enum):
    """نتيجة كنس دفعة واحدة (A4) — مُميَّزة عشان الرصد يفصل النجاح عن الفشل/التأجيل."""

    NOTHING = "nothing"                 # لا شيء لکنسه (مفيش عناصر ولا بايتات)
    CLEANED = "cleaned"                 # اتكنس كل شيء بنجاح
    PARTIAL = "partial"                 # اتحذف بعض البايتات، والباقي محتاج إعادة محاولة
    RETRY = "retry"                     # فشل FS مؤقّت/باقي عناصر ⇒ يُعاد في كنسة جاية
    SKIPPED = "skipped"                 # حالة غير مؤهّلة/غامضة/مملوكة-مختلف ⇒ تُترك (بلا تغيير)
    ERROR = "error"                     # فشل قاعدة/غير متوقّع ⇒ يُعاد


@dataclass(frozen=True)
class BatchSweepResult:
    """حصيلة كنس دفعة واحدة (A4). `status` = الحالة النهائية المرصودة للدفعة."""

    batch_id: str
    outcome: SweepOutcome
    status: str
    items: int = 0
    deleted: int = 0
    retry: int = 0
    reason: str | None = None


@dataclass(frozen=True)
class SweepReport:
    """حصيلة كنسة كاملة (A4) — مجمّعة للرصد (بلا أي محتوى/مسارات مستخدم)."""

    scanned: int = 0
    cleaned: int = 0
    partial: int = 0
    retry: int = 0
    skipped: int = 0
    errors: int = 0
    files_deleted: int = 0
    orphans_left: int = 0
    unsafe_left: int = 0
    untracked_left: int = 0


class AttachmentReaper:
    """OHB2-P0-A4: كنس البايتات المحلية للدفعات النهائية/المنتهية بترتيب آمن.

    المبادئ (fail-closed):
    - **DB-أولًا:** القرار الدائم (وسم الدفعة `expired`، ووسم العنصر `reaped` عبر CAS)
      يسبق أي حذف بايتات. فشل الحذف بعده يبقى **مرئيًّا وقابلًا لإعادة المحاولة** (العنصر
      `reaped` ⇒ كنسة تانية تعيد المحاولة) — **مفيش ادّعاء نجاح كاذب**.
    - **حصر صارم:** كل حذف محصور في جذر الـ staging، بلا تتبّع symlink (`lstat`)، وبلا
      حذف جذري/مجلدات غير متحقّق منها.
    - **بلا تخمين:** الحذف **بس** بعد قرار نهائي مؤكَّد (D-34/D-32) + `t0` صالح؛ حالة غير
      معروفة/غامضة/غير مؤهّلة ⇒ تُترك وتُرصد (بلا تخمين).
    - **idempotent:** إعادة الكنس آمنة (ملف مفقود = نجاح؛ عنصر `reaped` = إعادة محاولة).
    - **D-35:** ما بيمسّش `attachment_message_identity` خالص (دليل الهوية مستقل).
    """

    # حالات دفعة تسمح بالكنس **بس** مع قرار نهائي مؤكَّد (نهائية) أو انتهاء مؤكَّد.
    _TERMINAL = frozenset(
        {
            "delivered",
            "expired",
            "rejected",
            "failed",
        }
    )

    def __init__(
        self, db, db_path=None, *, batch_ttl: timedelta = ATTACHMENT_BATCH_TTL, store=None
    ) -> None:
        self._db = db
        # FIX-R04/R-4: جذر الـ staging لازم يكون صريحًا — إمّا مخزن موجود (`store`)، وإمّا
        # `db_path` محدَّد. ممنوع الاختيار الصامت لجذر نسبي (`attachment_staging` في مجلد
        # العمل الحالي) لما الاتنين غايبين ⇒ رفض مغلق بدل مسار غير مقصود.
        if store is None and not db_path:
            raise StagingError(
                "AttachmentReaper يحتاج مخزنًا (`store`) أو `db_path` صريحًا (جذر نسبي مرفوض)"
            )
        # إعادة استخدام نفس مخزن الـ staging (بلا اتصال قاعدة تاني) لما يُمرَّر صراحةً.
        self._store = store if store is not None else StagingStore(db, db_path)
        self._root = self._store.root
        self._ttl = batch_ttl

    @property
    def root(self) -> Path:
        return self._root

    def sweep(self, *, now: datetime) -> SweepReport:
        """كنسة واحدة كاملة. **لا بترمي** (تُسجّل وتُرصد). تُستدعى من hook الإقلاع."""
        now = _as_utc(now)
        now_iso = now.isoformat()
        report = {"scanned": 0, "cleaned": 0, "partial": 0, "retry": 0,
                  "skipped": 0, "errors": 0, "files_deleted": 0}
        known_tokens: set[str] = set()

        # (0a) مجموعة **كل** التوكنات المرتبطة بأي عنصر (بأي حالة) — لتمييز «غير مرتبط»
        #      عن «يتيم» في مسح الجذر (ما نصنّفش ملف عنصر يتيم كملف غير مرتبط).
        try:
            for it in self._db.list_all_attachment_items():
                if it.staging_token:
                    known_tokens.add(it.staging_token)
        except Exception as exc:  # noqa: BLE001
            log.warning("A4 sweep: تعذّر جلب كل العناصر (%s)", type(exc).__name__)
            report["errors"] += 1

        # (0b) حالات دفعة **غير معروفة/غير مدعومة** ⇒ تُرصد وتُترك (fail-closed، بلا كنس).
        #      حماية من تلف/قيمة مستقبلية: ما نصنّفش حالة مجهولة كنجاح.
        try:
            unknown = [
                b for b in self._db.list_all_attachment_batches()
                if b.status not in ATTACHMENT_BATCH_STATUSES
            ]
        except Exception as exc:  # noqa: BLE001
            log.warning("A4 sweep: تعذّر فحص حالات الدفعات (%s)", type(exc).__name__)
            unknown = []
            report["errors"] += 1
        if unknown:
            log.warning("A4 sweep: %s دفعة بحالة غير معروفة ⇒ تُترك للتحقيق", len(unknown))
            report["errors"] += 1

        # (0c) الدفعات **غير المحسومة** (D-32: intent_recorded/dispatching/uncertain) ⇒
        #      تُترك **عمدًا** (بلا كنس) وتُحتسب `skipped` (قرار تأجيل مُرصود، مش نجاح).
        try:
            from .db import ATTACHMENT_BATCH_UNRESOLVED_STATUSES
            for status in ATTACHMENT_BATCH_UNRESOLVED_STATUSES:
                for _b in self._db.list_attachment_batches_by_status(status):
                    report["skipped"] += 1
        except Exception as exc:  # noqa: BLE001
            log.warning("A4 sweep: تعذّر جلب الدفعات غير المحسومة (%s)", type(exc).__name__)
            report["errors"] += 1

        # (1) الدفعات المنتهية: pending فاتت مهلة T0 الثابتة ⇒ وسم `expired` (DB-أولًا).
        try:
            expired = self._db.list_expired_pending_attachment_batches(now_iso=now_iso)
        except Exception as exc:  # noqa: BLE001 — فشل قاعدة ⇒ كنسة فاشلة (تُرصد)
            log.warning("A4 sweep: تعذّر جلب الدفعات المنتهية (%s)", type(exc).__name__)
            return SweepReport(errors=1)
        for batch in expired:
            self._mark_expired(batch, now_iso, report)

        # (2) الدفعات النهائية: كنس بايتاتها (بعد القرار الدائم).
        terminal_batches: list[AttachmentBatch] = []
        for status in self._TERMINAL:
            try:
                terminal_batches.extend(self._db.list_attachment_batches_by_status(status))
            except Exception as exc:  # noqa: BLE001
                log.warning("A4 sweep: تعذّر جلب الدفعات النهائية (%s)", type(exc).__name__)
                report["errors"] += 1
        for batch in terminal_batches:
            self._record(self._sweep_batch(batch, known_tokens), report)

        # (3) دلاء يتيمة (عناصر بلا دفعة) — تُكنس بالتوكن، وتُرصد لو أثرت.
        try:
            orphans = self._sweep_orphan_items(known_tokens)
        except Exception as exc:  # noqa: BLE001
            log.warning("A4 sweep: تعذّر كنس العناصر اليتيمة (%s)", type(exc).__name__)
            orphans = 0
            report["errors"] += 1
        report["orphans_left"] = orphans

        # (4) مسح الجذر: بايتات بلا عنصر مطابق ⇒ تُرصد (بلا حذف عمياء/تبنّي).
        try:
            report["untracked_left"] = self._scan_root_untracked(known_tokens)
        except Exception as exc:  # noqa: BLE001
            log.warning("A4 sweep: تعذّر مسح جذر الـ staging (%s)", type(exc).__name__)
            report["errors"] += 1

        # (5) مخارج آمنة (symlink/مسار غير آمن) — تُرصد كحالة تحتاج تحقيق.
        report["unsafe_left"] = self._count_unsafe_entries()
        self._log_report(report)
        return SweepReport(**report)

    # ------------------------------------------------------------------ داخلي
    def _record(self, result: BatchSweepResult, report: dict) -> None:
        report["scanned"] += 1
        report["files_deleted"] += result.deleted
        if result.outcome is SweepOutcome.CLEANED:
            report["cleaned"] += 1
        elif result.outcome is SweepOutcome.PARTIAL:
            report["partial"] += 1
            report["retry"] += 1
        elif result.outcome is SweepOutcome.RETRY:
            report["retry"] += 1
        elif result.outcome is SweepOutcome.SKIPPED:
            report["skipped"] += 1
        elif result.outcome is SweepOutcome.ERROR:
            report["errors"] += 1
        # NOTHING لا يُحتسب في أي فئة (مفيش عمل).

    def _mark_expired(
        self, batch: AttachmentBatch, now_iso: str, report: dict
    ) -> None:
        """يوسم الدفعة المنتهية `expired` (DB-أولًا). الكنس الفعلي يتولّاه المرور على
        الدفعات النهائية (خطوة 2) بنفس الدورة ⇒ مفيش كنس مزدوج."""
        try:
            self._db.mark_attachment_batch_status(
                batch.batch_id, ATTACHMENT_BATCH_EXPIRED, now=now_iso
            )
        except Exception as exc:  # noqa: BLE001 — فشل قاعدة ⇒ خطأ (يُعاد)
            log.warning(
                "A4 sweep: تعذّر وسم الدفعة %s كمنتهية (%s)",
                batch.batch_id, type(exc).__name__,
            )
            report["errors"] += 1

    def _sweep_batch(
        self, batch: AttachmentBatch, known_tokens: set[str]
    ) -> BatchSweepResult:
        # قرار مؤهّل: نهائي **و** `t0` صالح. غير ذلك ⇒ تُترك (بلا تخمين).
        if batch.status not in self._TERMINAL:
            return BatchSweepResult(batch.batch_id, SweepOutcome.SKIPPED, batch.status,
                                    reason="non_terminal")
        if _parse_t0(batch.t0) is None:
            log.warning("A4 sweep: دفعة %s نهائية بـ t0 غير صالح ⇒ تُترك", batch.batch_id)
            return BatchSweepResult(batch.batch_id, SweepOutcome.SKIPPED, batch.status,
                                    reason="invalid_t0")
        try:
            items = self._db.list_attachment_items(batch.batch_id)
        except Exception as exc:  # noqa: BLE001
            log.warning("A4 sweep: تعذّر جلب عناصر الدفعة %s (%s)",
                        batch.batch_id, type(exc).__name__)
            return BatchSweepResult(batch.batch_id, SweepOutcome.ERROR, batch.status,
                                    reason=type(exc).__name__)
        if not items:
            # حالة (2): دبوس بلا عناصر ⇒ لا شيء لکنسه (تُترك البيانات الوصفية للتحقيق).
            return BatchSweepResult(batch.batch_id, SweepOutcome.NOTHING, batch.status)

        deleted = retry = reconciled = 0
        for item in items:
            token = item.staging_token
            if token:
                known_tokens.add(token)
            if item.status == ATTACHMENT_ITEM_REAPED:
                # كنسة سابقة وسمت العنصر؛ بايتاته ممكن تكون لسه موجودة (فشل حذف سابق).
                res = self._remove_file(token)
                if res == "deleted":
                    deleted += 1
                elif res == "absent":
                    reconciled += 1
                elif res == "retry":
                    retry += 1
                # unsafe ⇒ يُترك ويُرصد
                continue
            if item.status not in (ATTACHMENT_BATCH_PENDING, ATTACHMENT_ITEM_STORED):
                # حالة عنصر غير معروفة/غامضة ⇒ تُترك (بلا تخمين)، تُرصد.
                log.warning("A4 sweep: عنصر %s بحالة غير معروفة/غامضة ⇒ يُترك", item.item_id)
                retry += 1
                continue
            # DB-أولًا: وسم العنصر `reaped` (CAS) **قبل** حذف البايتات.
            try:
                marked = self._db.mark_attachment_item_reaped(item.item_id)
            except Exception as exc:  # noqa: BLE001 — فشل قاعدة ⇒ يُعاد
                log.warning("A4 sweep: تعذّر وسم العنصر %s كمكنوس (%s)",
                            item.item_id, type(exc).__name__)
                retry += 1
                continue
            if not marked:
                # تغيّرت الحالة تحتنا (سباق) ⇒ ما نمسحش؛ إعادة محاولة لاحقة.
                retry += 1
                continue
            res = self._remove_file(token)
            if res == "deleted":
                deleted += 1
            elif res == "absent":
                reconciled += 1
            elif res == "retry":
                retry += 1
        if retry:
            outcome = SweepOutcome.PARTIAL if (deleted or reconciled) else SweepOutcome.RETRY
            return BatchSweepResult(batch.batch_id, outcome, batch.status,
                                    items=len(items), deleted=deleted, retry=retry)
        if deleted or reconciled:
            return BatchSweepResult(batch.batch_id, SweepOutcome.CLEANED, batch.status,
                                    items=len(items), deleted=deleted)
        return BatchSweepResult(batch.batch_id, SweepOutcome.NOTHING, batch.status,
                                items=len(items))

    def _sweep_orphan_items(self, known_tokens: set[str]) -> int:
        """عناصر بلا دفعة أب (دبوس مفقود): وسم `reaped` + حذف بايتاتها. ترجّع المتبقّي."""
        try:
            all_batches = {b.batch_id for b in self._db.list_all_attachment_batches()}
        except Exception as exc:  # noqa: BLE001
            log.warning("A4 sweep: تعذّر جلب كل الدفعات (%s)", type(exc).__name__)
            return 0
        left = 0
        for status in (
            ATTACHMENT_BATCH_PENDING,
            ATTACHMENT_ITEM_STORED,
            ATTACHMENT_ITEM_REAPED,
        ):
            try:
                items = self._db.list_attachment_items_by_status(status)
            except Exception as exc:  # noqa: BLE001
                log.warning("A4 sweep: تعذّر جلب عناصر بحالة %s (%s)",
                            status, type(exc).__name__)
                continue
            for item in items:
                if item.batch_id in all_batches:
                    continue
                token = item.staging_token
                if token:
                    known_tokens.add(token)
                if item.status == ATTACHMENT_ITEM_REAPED:
                    # كنسة سابقة وسمت العنصر لكن بايتاته ممكن تكون لسه موجودة (فشل حذف سابق)
                    # ⇒ نعيد محاولة الحذف (idempotent). القرار الدائم متخذ بالفعل، والقرار
                    # الدائم/الحصر/أمان المسار كلها في `_remove_file` ⇒ بلا حذف تخميني.
                    log.warning("A4 sweep: عنصر يتيم %s (بلا دفعة) مكنوس سابقًا ⇒ إعادة حذف",
                                item.item_id)
                    if self._remove_file(token) == "retry":
                        left += 1
                    continue
                log.warning("A4 sweep: عنصر يتيم %s (بلا دفعة) ⇒ يُكنس", item.item_id)
                try:
                    if not self._db.mark_attachment_item_reaped(item.item_id):
                        left += 1
                        continue
                except Exception:  # noqa: BLE001
                    left += 1
                    continue
                if self._remove_file(token) == "retry":
                    left += 1
        return left

    def _scan_root_untracked(self, known_tokens: set[str]) -> int:
        """يعدّ البايتات في الجذر بلا عنصر مطابق (تُرصد، ما تُحذفش — بلا تبنّي/تخمين)."""
        root = self._validated_root()
        if root is None:
            return 0
        left = 0
        try:
            entries = list(root.iterdir())
        except OSError as exc:
            log.warning("A4 sweep: تعذّر قراءة جذر الـ staging (%s)", type(exc).__name__)
            return 0
        for entry in entries:
            name = entry.name
            if name in known_tokens:
                continue
            if self._is_unsafe_entry(entry):
                continue  # يُحسب في _count_unsafe_entries
            left += 1
        if left:
            log.info("A4 sweep: %s بايت غير مرتبط بعنصر في جذر الـ staging ⇒ تُركت للتحقيق", left)
        return left

    def _count_unsafe_entries(self) -> int:
        """يعدّ مدخلات الجذر غير الآمنة (symlink/غير ملف عادي) — تُرصد بلا متابعة."""
        root = self._validated_root()
        if root is None:
            return 0
        count = 0
        try:
            entries = list(root.iterdir())
        except OSError:
            return 0
        for entry in entries:
            if self._is_unsafe_entry(entry):
                count += 1
                log.warning("A4 sweep: مدخل staging غير آمن ⇒ يُترك بلا متابعة")
        return count

    def _validated_root(self) -> Path | None:
        """يرجّع الجذر لو مجلد حقيقي (مش symlink) موجود، وإلا None (بلا حذف جذري)."""
        root = self._root
        try:
            st = os.lstat(str(root))
        except OSError:
            return None
        if _stat.S_ISLNK(st.st_mode) or not _stat.S_ISDIR(st.st_mode):
            log.warning("A4 sweep: جذر الـ staging مش مجلد حقيقي ⇒ لا كنس")
            return None
        return root

    def _is_unsafe_entry(self, entry: Path) -> bool:
        """symlink أو غير ملف عادي ⇒ غير آمن (يُترك، ما يُتابعش)."""
        try:
            st = os.lstat(str(entry))
        except OSError:
            return True
        if _stat.S_ISLNK(st.st_mode):
            return True
        return not _stat.S_ISREG(st.st_mode)

    def _remove_file(self, token: str | None) -> str:
        """يحذف بايت واحد بالتوكن **بس** لو آمن ومحصور في الجذر.

        ترجّع: `"deleted"` (اتشال)، `"absent"` (مفقود ⇒ نجاح idempotent)، `"retry"`
        (فشل مؤقّت/غير متوقّع ⇒ إعادة محاولة)، `"unsafe"` (توكن/مسار غير آمن أو symlink
        أو غير ملف عادي ⇒ **يُرفض ويُترك**، ما نتابعش الروابط).

        حصر: التوكن مقطع واحد آمن (`is_safe_workspace_path`) + `_is_within(root)` + `lstat`
        (بلا متابعة symlink) + رفض أي مدخل غير ملف عادي. **مفيش حذف جذري/مجلد.**
        """
        if not token or not files.is_safe_workspace_path(token):
            if token:
                log.warning("A4 sweep: توكن غير آمن ⇒ لا حذف")
            return "unsafe"
        root = self._root
        try:
            rst = os.lstat(str(root))
        except FileNotFoundError:
            return "absent"  # جذر مفقود ⇒ مفيش ملف ⇒ نجاح idempotent
        except OSError as exc:
            log.warning("A4 sweep: تعذّر lstat الجذر (%s) ⇒ إعادة محاولة", type(exc).__name__)
            return "retry"
        if _stat.S_ISLNK(rst.st_mode) or not _stat.S_ISDIR(rst.st_mode):
            log.warning("A4 sweep: جذر الـ staging مش مجلد حقيقي ⇒ لا حذف")
            return "unsafe"
        path = root / token
        if not _is_within(root, path):
            log.warning("A4 sweep: مسار خارج الجذر ⇒ لا حذف")
            return "unsafe"
        try:
            st = os.lstat(str(path))
        except FileNotFoundError:
            return "absent"  # مفقود ⇒ نجاح (idempotent)
        except OSError as exc:
            log.warning("A4 sweep: تعذّر lstat (%s) ⇒ إعادة محاولة", type(exc).__name__)
            return "retry"
        if _stat.S_ISLNK(st.st_mode) or not _stat.S_ISREG(st.st_mode):
            log.warning("A4 sweep: مدخل غير ملف عادي ⇒ لا حذف")
            return "unsafe"
        try:
            os.unlink(str(path))
        except FileNotFoundError:
            return "absent"
        except OSError as exc:
            log.warning("A4 sweep: فشل حذف بايت (%s) ⇒ إعادة محاولة", type(exc).__name__)
            return "retry"
        return "deleted"

    def _log_report(self, report: dict) -> None:
        """سجل منظّم **بلا أي محتوى/مسارات/أسرار** — أسماء أحداث وأعداد فقط."""
        log.info(
            "A4 sweep: scanned=%s cleaned=%s partial=%s retry=%s skipped=%s errors=%s "
            "files_deleted=%s orphans_left=%s unsafe_left=%s untracked_left=%s",
            report.get("scanned", 0), report.get("cleaned", 0), report.get("partial", 0),
            report.get("retry", 0), report.get("skipped", 0), report.get("errors", 0),
            report.get("files_deleted", 0), report.get("orphans_left", 0),
            report.get("unsafe_left", 0), report.get("untracked_left", 0),
        )


class OpportunisticSweeper:
    """OHB2-LIFE-01: غلاف **رقيق** حوالين `AttachmentReaper` لتشغيل كنسة محدودة من tick
    عامل **موجود** (`Watcher`) بدل الإقلاع بس — بلا عامل/مجدول/عملية/مالك قاعدة جديد.

    الخصائص (كلها مفروضة هنا، مش مفترضة):
    - **محدودة زمنيًّا:** كنسة واحدة على الأكثر كل `min_interval` ثانية ⇒ مفيش كنسة كاملة
      على كل tick/تحديث.
    - **حرس إعادة دخول:** الكنسة **متزامنة**؛ `_running` بيمنع أي تداخل حتى لو استُدعيت
      من سياقين (نظريًّا) ⇒ مفيش كنسين متوازيين على نفس الاتصال/الجذر.
    - **مفيش ابتلاع فشل:** فشل الكنسة بيتسجّل (بأنواع الأخطاء فقط، بلا محتوى/مسارات) وبيُرصد
      كـ «فشل» صريح، **مش** نجاح كاذب. الحالة الزمنية **ما بتتحدّثش** عند الفشل ⇒ إعادة
      المحاولة مسموحة على الـ tick المؤهّل التالي (مفيش كبت دائم بعد فشل/كنسة جزئية).
    - **idempotent:** بيعيد استخدام `AttachmentReaper.sweep` نفسه (مفيش منطق كنس مكرّر).
    - **حرس الأخطاء يفضل شغّال:** كنسة A4 محصورة/بلا تخمين/بلا متابعة symlink (تفاصيل في
      `AttachmentReaper`). الجذر الآمن بيتأكّد جوه `_remove_file`/`_validated_root`.
    - **ما بيمسّش `T0`/المهلة:** الكنسة بتقرأ `t0` بس (بلا تعديل).

    ملاحظة صدق: ده **كنس انتهاكي**، مش كنس دوري مضمون — أثناء خمول تام (مفيش ticks) ممكن
    البايتات تفضل لحد الـ tick التالي/إعادة التشغيل. الحذف الدوري الصارم يتطلّب قرار
    معمارية منفصل (مجدول/عامل)، وده **مش** مُصرَّح به هنا.
    """

    def __init__(
        self,
        reaper: AttachmentReaper,
        *,
        min_interval: float = OPPORTUNISTIC_SWEEP_MIN_INTERVAL_SECONDS,
        clock=None,
    ) -> None:
        if min_interval is None or float(min_interval) < 0:
            raise ValueError("min_interval لازم يكون رقم غير سالب")
        self._reaper = reaper
        self._min_interval = float(min_interval)
        self._clock = clock or time.monotonic
        self._last_run_at: float | None = None
        self._running = False

    @property
    def reaper(self) -> AttachmentReaper:
        return self._reaper

    def maybe_sweep(self, *, now: datetime | None = None) -> SweepReport | None:
        """يشغّل كنسة **واحدة** لو الفترة عدّت ومفيش كنسة شغّالة.

        ترجّع `SweepReport` لما الكنسة اشتغلت فعلًا، و`None` لما اتخطّت (خنق زمني أو
        إعادة دخول) — الفرق ده مقصود للرصد والاختبارات. **لا بترمي** لأخطاء الكنسة
        المتوقّعة: بتُسجَّل وتُرجَّع `None` (فشل صريح، مش نجاح)، والزمن **ما بيتقدّمش**
        ⇒ إعادة محاولة على الـ tick التالي.
        """
        if self._running:
            return None  # كنسة شغّالة بالفعل ⇒ مفيش تداخل
        mono = self._clock()
        if (
            self._last_run_at is not None
            and (mono - self._last_run_at) < self._min_interval
        ):
            return None  # لسه بدري (خنق) ⇒ مفيش كنسة كاملة على كل tick
        self._running = True
        try:
            sweep_now = now if now is not None else datetime.now(timezone.utc)
            report = self._reaper.sweep(now=sweep_now)
        except Exception as exc:  # noqa: BLE001 — فشل الكنسة ⇒ يُسجَّل، مفيش نجاح كاذب
            log.warning(
                "كنس LIFE-01 الانتهاكي فشل (%s) ⇒ هيتعاود على الـ tick التالي",
                type(exc).__name__,
            )
            return None  # الزمن **ما بيتقدّمش** ⇒ إعادة محاولة مسموحة
        finally:
            self._running = False
        self._last_run_at = mono  # نجاح (حتى لو جزئي) ⇒ نطبّق الخنق لحد الـ tick الجاي
        return report
