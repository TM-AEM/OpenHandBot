"""قاعدة بيانات SQLite لحفظ الشاتات المتابَعة وحالة الحوار وصندوق الصادر."""
from __future__ import annotations

import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

from . import update_outcomes

log = logging.getLogger(__name__)

# OHB2-SW03: سياسة إعادة محاولة **مشتركة** لقراءات SQLite العابرة (busy/locked). معرّفة في
# طبقة القاعدة عشان البوت والـ Mini App يستخدموا نفس الميزانية بالظبط (مفيش تكرار سياسة).
# ميزانية صغيرة عمدًا: مجموع الانتظار ≈ 0.25+0.5+1 = 1.75 ثانية كحد أقصى، وبعدها بنرفع
# الاستثناء الأصلي (مفيش فشل مقفول صامت). في وضع WAL القراءة مش بتتحاصر بالكتّاب، فالفشل
# العابر الحقيقي ضيّق جدًا؛ الفشل الدائم (قاعدة تالفة/مقفولة) **مش** هيتعاد.
DEDUPE_RETRY_DELAYS = (0.25, 0.5, 1.0)
# أكواد SQLite العابرة **الأساسية**: BUSY (5) و LOCKED (6). بنطابق الكود الأساسي
# (`sqlite_errorcode & 0xFF`) لو الكود متاح (Python 3.11+)، عشان الأكواد الممتدة اللي
# أصلها BUSY/LOCKED (BUSY_RECOVERY 261، LOCKED_SHAREDCACHE 262، BUSY_SNAPSHOT 517،
# BUSY_TIMEOUT 773، وأي إضافة مستقبلية) تُصنّف عابرة كذلك. لو الكود مش متاح، بنطابق
# النص المعروف كاحتياطي (نسخ أقدم/أخطاء بدون كود).
_TRANSIENT_SQLITE_CODES = frozenset(
    code
    for code in (getattr(sqlite3, "SQLITE_BUSY", None), getattr(sqlite3, "SQLITE_LOCKED", None))
    if code is not None
)
# قناع الكود الأساسي في SQLite: الكود الأساسي = `result_code & 0xFF`، والأكواد الممتدة
# بتضيف بتات أعلى (مثال: BUSY_SNAPSHOT 517 = 0x205 ⇒ 0x05 = BUSY).
_SQLITE_PRIMARY_CODE_MASK = 0xFF


def is_transient_sqlite_error(exc: Exception) -> bool:
    """هل الخطأ فشل SQLite **عابر** (قفل/انشغال) يستحق إعادة محاولة محدودة؟

    بنطابق **الكود الأساسي** (`sqlite_errorcode & 0xFF`) لو الكود متاح — الطريقة المتينة
    اللي بتغطّي الأكواد الممتدة (BUSY_RECOVERY/BUSY_SNAPSHOT/BUSY_TIMEOUT/LOCKED_SHAREDCACHE…)
    اللي أصلها BUSY أو LOCKED. لو الكود مش متاح، بنطابق نص الرسالة المعروف. أي خطأ تاني
    (قاعدة تالفة، قرص ممتلئ، اتصال مقفول، جدول مش موجود) **دائم** ⇒ False (فشل مقفول فورًا،
    مفيش إعادة محاولة).
    """
    if not isinstance(exc, sqlite3.Error):
        return False
    code = getattr(exc, "sqlite_errorcode", None)
    if isinstance(code, int):
        return (code & _SQLITE_PRIMARY_CODE_MASK) in _TRANSIENT_SQLITE_CODES
    if code is not None:
        return False  # كود بنوع غير متوقّع ⇒ نفس سلوك الأصل (مش عابر)، ومفيش استثناء جديد
    msg = str(exc).lower()
    return "locked" in msg or "busy" in msg


# حالات صندوق الصادر (outbox) — كل انتقال مع سلوك التعافي بعد إعادة التشغيل:
#   pending  : اتسجّل بثبات ولسه ماتحاولش الإرسال. آمن يتعاود بعد restart.
#   claimed  : الـ worker اخده ذرّياً (ملكه)، والـ POST لسه مابدأش. آمن يرجع
#              pending بعد restart (الإرسال مابدأش ⇒ مفيش احتمال ازدواج).
#   sending  : بدأت محاولة الإرسال والنتيجة لسه ماتحسمتش بثبات. بعد restart ⇒ unknown.
#   sent     : اتأكد نجاح الإرسال (رد POST سليم). مايتعادش أبداً.
#   unknown  : نتيجة الإرسال غامضة (timeout/انقطاع/إلغاء) وماينفعش نأكد إن
#              الـ server ماخدش البرومت ⇒ مايتعادش تلقائياً (at-most-once).
#   failed   : رفض نهائي مؤكد (رد 4xx **باستثناء 429**). مايتعادش تلقائياً.

OUTBOX_PENDING = "pending"
OUTBOX_CLAIMED = "claimed"
OUTBOX_SENDING = "sending"
OUTBOX_SENT = "sent"
OUTBOX_UNKNOWN = "unknown"
OUTBOX_FAILED = "failed"
OUTBOX_DISCARDED = "discarded"

# OHB2-POST-PUB-01/F02: حالة إكمال الأثر المحلي (الإشعار/المتابعة) — منفصلة عن نتيجة
# العملية الخارجية (status). العقد: `status` بتقول هل الـ POST الخارجي اتأكد (sent) أم
# لأ؛ `notify_state` بتقول هل **الأثر المحلي** (إشعار المستخدم + تسجيل المتابعة) خلص.
#   ""        : لسه محتاج إكمال محلي (أو مالوش أثر محلي مطلوب).
#   "pending" : عملية محلية بدأت (إشعار write-ahead) ولسه ماتأكدتش — تتعافى بعد restart.
#   "sent"    : الأثر المحلي خلص (الإشعار اتسلّم + المتابعة اتسجّلت).
NOTIFY_NONE = ""
NOTIFY_PENDING = "pending"
NOTIFY_SENT = "sent"

# حالات طلب الشات الجديد (creation job) — الجدول منفصل عن outbox عشان الطلب
# مالوش conversation_id لسه وقت التسجيل. نفس منطق الحجز/الغموض:
#   pending   : اتسجّل بثبات ولسه POST البدء مابدأش. آمن يتعاود بعد restart.
#   claimed   : الـ worker اخده ذرّياً (ملكه)، وPOST البدء لسه مابدأش. آمن يرجع pending.
#   starting  : بدأ POST البدء (أو استطلاع مهمة معروفة) والنتيجة لسه ماتحسمتش.
#               لو فيه task_id محفوظ ⇒ الاستطلاع (GET آمن) بس هو اللي يتعاود.
#   done      : اتأكد بدء الشات واتعرف conversation_id. مايتعادش أبداً.
#   unknown   : نتيجة البدء غامضة (timeout/انقطاع/إلغاء/بدون task_id) ⇒ مايتعادش تلقائياً.
#   failed    : رفض نهائي مؤكد (4xx **باستثناء 429**) أو فشل مهمة مؤكد ⇒ مايتعادش تلقائياً.
CREATION_PENDING = "pending"
CREATION_CLAIMED = "claimed"
CREATION_STARTING = "starting"
CREATION_DONE = "done"
CREATION_UNKNOWN = "unknown"
CREATION_FAILED = "failed"
CREATION_DISCARDED = "discarded"

# OHB2-POST-PUB-01/F02: حالة إكمال الأثر المحلي لطلب الشات الجديد (إشعار الرابط +
# تسجيل المتابعة). نفس عقد الـ outbox: `status=done` = الـ POST الخارجي اتأكد، و
# `notify_state` = الأثر المحلي خلص. الـ watcher وقاعدة «مايتعادش الـ POST أبدًا» بيفضلوا
# على `status` (done نهائي) — الإكمال المحلي مستقل تمامًا.
CREATION_NOTIFY_NONE = ""
CREATION_NOTIFY_PENDING = "pending"
CREATION_NOTIFY_SENT = "sent"

# OHB2-P0-A0: حالات الدفعة/العنصر المحلية للمرفقات (نموذج بيانات A0 — المخطّط فقط).
#   pending          : اتسجّل بثبات (صف موجود) ولسه مافيش محاولة رفع.
#   intent_recorded  : OHB2-P0-A3/D-27 — نيّة محلية متينة (نصّ مصاحب مؤهّل اتخزّن). **مش** إرسال
#                      بعيد؛ الإرسال البعيد لسه حالة مستقبلية (`dispatching`).
#   dispatching      : اتسجّل نية الإرسال **البعيد** (عند الإرسال الفعلي) — مرحلة B.
#   uncertain        : نتيجة الرفع البعيد غامضة (timeout/5xx) ⇒ مصالحة، بلا إعادة عمياء.
#   delivered        : اتأكد التسليم (دليل قراءة/`expires_at`).
#   expired          : فاتت المهلة (T0+15د) قبل التسليم.
#   rejected         : رفض نهائي مؤكد.
#   failed           : فشل نهائي مؤكد.
# الانتقالات سلوك مراحل A2/A3/A4؛ `dispatching` لسه بلا منطق انتقال (مرحلة B).
ATTACHMENT_BATCH_PENDING = "pending"
ATTACHMENT_BATCH_INTENT_RECORDED = "intent_recorded"
ATTACHMENT_BATCH_DISPATCHING = "dispatching"
ATTACHMENT_BATCH_UNCERTAIN = "uncertain"
ATTACHMENT_BATCH_DELIVERED = "delivered"
ATTACHMENT_BATCH_EXPIRED = "expired"
ATTACHMENT_BATCH_REJECTED = "rejected"
ATTACHMENT_BATCH_FAILED = "failed"
ATTACHMENT_BATCH_STATUSES = (
    ATTACHMENT_BATCH_PENDING,
    ATTACHMENT_BATCH_INTENT_RECORDED,
    ATTACHMENT_BATCH_DISPATCHING,
    ATTACHMENT_BATCH_UNCERTAIN,
    ATTACHMENT_BATCH_DELIVERED,
    ATTACHMENT_BATCH_EXPIRED,
    ATTACHMENT_BATCH_REJECTED,
    ATTACHMENT_BATCH_FAILED,
)

# OHB2-P0-A3/D-32 (F1-1a/F1-1b): تصنيف **صريح** لحالات الدفعة عند حدّ توجيه النصّ في A3.
# القاعدة الحاكمة: حالات **غير محسومة** (لسه فيها نيّة/إرسال معلّق) بتحجب البرومت العادي؛
# حالات **نهائية** ما بتحجبش برومتًا جديدًا بذاتها (لكن ما بتصرّحش بتحويل/إعادة نصّ قديم).
#   - unresolved: النيّة/الإرسال لسه معلّق ⇒ **تحجب** (فشل مغلق). `intent_recorded` = نيّة
#     محلية متينة (D-27)؛ `dispatching`/`uncertain` = مراحل B (لسه بلا منطق انتقال).
#   - terminal: نتيجة نهائية ⇒ **لا تحجب** برومتًا جديدًا (بلا غموض).
ATTACHMENT_BATCH_UNRESOLVED_STATUSES = frozenset(
    {
        ATTACHMENT_BATCH_INTENT_RECORDED,
        ATTACHMENT_BATCH_DISPATCHING,
        ATTACHMENT_BATCH_UNCERTAIN,
    }
)
ATTACHMENT_BATCH_TERMINAL_STATUSES = frozenset(
    {
        ATTACHMENT_BATCH_DELIVERED,
        ATTACHMENT_BATCH_EXPIRED,
        ATTACHMENT_BATCH_REJECTED,
        ATTACHMENT_BATCH_FAILED,
    }
)


class AttachmentBatchIntegrityError(RuntimeError):
    """OHB2-P0-A3/F2: حالة دفعة مرفقات **غير معروفة/غير صالحة** ⇒ رفض مغلق.

    تُرفع عند وجود صفّ `attachment_batches` بحالة خارج `ATTACHMENT_BATCH_STATUSES`
    (تلف بيانات، قيمة مستقبلية غير مدعومة، أو NULL). الرفع **مقصود**: بدل ما تُصنَّف
    الحالة المجهولة `NONE` وتسقط بصمت لمسار البرومت/`outbox` (fail-open)، بينتشر
    الاستثناء للمعالج ⇒ يُسجَّل **فشلًا تقنيًّا غير مؤهّل للإقرار** (`failed_*`)، بلا أي
    صفّ `outbox` وبلا أي نداء بعيد. مفيش كتم للاستثناء ولا تحويله لنجاح/رفض مؤهّل.
    """


# OHB2-P0-A1: حالة عنصر مرفق **اتخزّن** بنجاح (بايتات كاملة + تحقّق). العنصر بيفضل
# `pending` (نفس قيمة A0) قبل كده — بما فيها عند الفشل — عشان كنس A4 يلاقي المعلّق.
ATTACHMENT_ITEM_STORED = "stored"
# OHB2-P0-A4/D-35: عنصر اتكنس (بايتات الـ staging اتحذفت بعد قرار نهائي/انتهاء). علامة
# **عنصر** (مش حالة دفعة) عشان ما نغيّرش مجموعة حالات الدفعة المعتمدة (D-32/D-34). العنصر
# الكنسي `reaped` **مش** `stored` ⇒ الرصد يميّز بين المكنوس والمُخزَّن.
ATTACHMENT_ITEM_REAPED = "reaped"

# OHB2-STABILIZATION-F02: أنواع مراجع أعمال الإكمال المحلي المعلّقة (جدول completion_pending).
# معرّفة هنا عشان طبقة الـ DB تقدر تبني استعلامات التسوية/الرصد من غير اعتماد دائري على outbox.
COMPLETION_KIND_OUTBOX = "outbox"
COMPLETION_KIND_CREATION = "creation"

# OHB2-08-05: صندوق الإشعارات (history) — سجل **تراكمي** للإشعارات اللي اتسلّمت فعلًا
# على تيليجرام، عشان المستخدم يرجع يشوفها من الـ Mini App بعد ما الرسالة تتوه في الشات.
# ده **مش** مصدر حقيقة جديد للتسليم: `notification_state`/`watched`/`notifier_pending`
# هما اللي بيحكموا هل الإشعار اتبعت ولا لأ. الصندوق بيسجّل **بعد** نجاح الإرسال بس،
# فبيبقى متسق مع التسليم الفعلي (مفيش ازدواج ومفيش إشعار وهمي).
# أنواع الإشعارات (kind) اللي بتتكتب في الصندوق.
INBOX_KIND_TERMINAL = "terminal"       # شات متابَع وصل حالة نهائية (المراقب)
INBOX_KIND_TIMEOUT = "timeout"         # انتهت مهلة متابعة (24 ساعة)
INBOX_KIND_MISSING = "missing"         # شات متابَع اختفى من OpenHands
INBOX_KIND_STALE_REPORT = "stale_report"  # مفيش تقرير جديد بعد البرومبت
INBOX_KIND_PROACTIVE = "proactive"     # إشعار استباقي عام (المُبلّغ)

# OHB2-PHASE1C: مجموعة الحذف النهائي **الآمنة** (allowlist صريحة). دول بس أنواع **تقارير
# حالة/نتيجة** مش مرتبطة بعملية قابلة للتنفيذ: مفيش outbox/creation job مرتبط بيهم،
# فحذفهم بعد التسليم + القراءة ما بيفقدش دليلًا تشغيليًا.
#   - `proactive` **مستثنى** لأنه إشعار حالة حيّة لمحادثة (مرتبط بعلامة تسوية `notifier_pending`
#     ومفتاح حدث؛ حذفه يهدّد دليل الاسترجاع).
#   - أي نوع **غير معروف** (مش هنا) محمي تلقائيًا — سياسة fail-closed: أي نوع جديد/غريب
#     مايتحذفش نهائيًا لحد ما يتقيّم ويتضاف صراحةً.
INBOX_DELETABLE_KINDS = frozenset(
    {
        INBOX_KIND_TERMINAL,
        INBOX_KIND_TIMEOUT,
        INBOX_KIND_MISSING,
        INBOX_KIND_STALE_REPORT,
    }
)

# أقصى طول لنص الإشعار المحفوظ. ردود الـ agent ممكن تكون ضخمة؛ بنقصّها عشان القاعدة ما
# تتضخّمش. الرسالة الكاملة بتفضل في تيليجرام؛ الصندوق ملخّص قابل للعرض.
INBOX_MAX_MESSAGE_CHARS = 1000
# أقصى عدد إشعارات محفوظة لكل محادثة (تقليم تراكمي عند الإدراج ⇒ نمو محدود).
INBOX_MAX_PER_CONVERSATION = 50
# أقصى عدد إشعارات محفوظة إجمالًا (تقليم عام عند الإدراج ⇒ سقف تخزين صلب حتى مع محادثات
# كتير). بيمنع النمو غير المحدود لو المستخدم راقب مئات الشاتات.
INBOX_MAX_TOTAL = 500
# أقصى عدد عناصر في صفحة قايمة الصندوق (يتفرض في طبقة الـ API).
INBOX_PAGE_SIZE = 10
# أقصى عدد صحيح يقبله SQLite (INTEGER = 64-bit). أي رقم أكبر منه بيرمي OverflowError
# وقت الـ binding. بنستخدمه كسقف مشترك للتحقق من الحدود (AUD-04/AUD-02).
MAX_SQLITE_INT = 2**63 - 1
# AUD-04: أقصى رقم صفحة مسموح لأي قايمة مُرقّمة (offset = page × page_size). بنحدّد رقم
# الصفحة نفسه عشان يفضل offset = page × size داخل نطاق 64-bit حتى لو page_size كبير،
# ومايتحوّلش لـ OverflowError جوّه SQLite. مليون صفحة × 10 = 10M صف أقصى — أوسع بكتير
# من أي بيانات واقعية (سقوف الصندوق/المحادثات أصغر)، فمفيش تقييد عملي للاستخدام الطبيعي.
MAX_PAGE = 1_000_000

# OHB2-08-05 (Batch 3R): حالة تسليم الحدث (مستقلة تمامًا عن حالة القراءة `read_at`).
#   pending   : الحدث اتسجّل بثبات (durable) ولسه ماتسلّمش لتليجرام. **مايتقلّمش أبدًا.**
#   delivered : تليجرام أكّد التسليم. الحدث باقي في الصندوق كسجل تاريخي.
#   failed    : استنفدنا ميزانية المحاولات (رفض دائم أو فشل متكرّر). الحدث **باقي**
#               ظاهر للمستخدم (مفيش فقد صامت)، بس مايتعادش تلقائيًا.
INBOX_DELIVERY_PENDING = "pending"
INBOX_DELIVERY_DELIVERED = "delivered"
INBOX_DELIVERY_FAILED = "failed"
# OHB2-PHASE1C: نتيجة محاولة الحذف النهائي لصف صندوق (مُفرَض على السيرفر، مش على الواجهة).
#   deleted   : الصف كان مؤهّلًا واتحذف فعلًا.
#   protected : الصف موجود لكنه محمي (مش مؤهّل للحذف النهائي) ⇒ مفيش أي تغيير.
#   missing   : الصف مش موجود أصلًا.
INBOX_DELETE_DELETED = "deleted"
INBOX_DELETE_PROTECTED = "protected"
INBOX_DELETE_MISSING = "missing"
# أقصى طول لتصنيف خطأ التسليم المحفوظ (نوع الاستثناء بس — مفيش نص حسّاس/أسرار).
INBOX_MAX_ERROR_CHARS = 120
# أقصى عدد محاولات تسليم للحدث الواحد قبل ما نصنّفه فاشل (ميزانية مستقلة لكل حدث).
INBOX_DELIVERY_MAX_ATTEMPTS = 5
# OHB2-08-05 (Batch 3R-FIX2-F1): مدة صلاحية حجز الحدث (claim lease). حجز أقدم من كده بيتخطّى/
# يتحرّر (العملية اللي أخدته وقعت قبل ما تحرّره) ⇒ الحدث ما يعلقش محجوزًا للأبد. أطول من أي
# إرسال عادي (ثوانٍ) فمايسببش إرسالًا مزدوجًا عمليًا.
INBOX_CLAIM_LEASE = timedelta(minutes=5)


# مهلة أي حالة توجيه (من آخر نشاط). القرار 1: توجيه 10 دقايق.
AWAITING_TTL = timedelta(minutes=10)


# OHB2-P0-A0: مهلة الدفعة الثابتة (15 دقيقة) من **أول** ملف في الدفعة المعلّقة. ثابت P0
# (I4) **منفصل** عن `AWAITING_TTL` (10 دقايق)؛ إعادة استخدام `AWAITING_TTL` كانت هتكسر
# المهلة. `T0` بيتخزّن مرة واحدة عند أول ملف وعمره ما بيتمدّد (I6).
ATTACHMENT_BATCH_TTL = timedelta(minutes=15)


# نافذة تجميع الرسايل المتتالية (القرار 2): أي رسالة جاية خلال 1.5 ثانية من آخر تحديث
# لبرومت لسه 'pending' لنفس الوجهة بتتجمّع معاه في سجل واحد (مش إرسال منفصل).
GROUP_WINDOW = timedelta(seconds=1.5)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _attachment_batch_deadline(t0: str | None) -> datetime | None:
    """الموعد النهائي للدفعة = `T0 + ATTACHMENT_BATCH_TTL` (None لو `t0` غير صالح).

    نفس دلالة `attachments.batch_deadline` (مرجع واحد للمهلة `ATTACHMENT_BATCH_TTL`)؛ نسخة
    محلية صغيرة عشان طبقة القاعدة (A3) ما تعتمدش على وحدة المرفقات العليا (تفادي دورية الاستيراد).
    """
    if not t0:
        return None
    try:
        start = datetime.fromisoformat(t0)
    except (ValueError, TypeError):
        return None
    if not start.tzinfo:
        start = start.replace(tzinfo=timezone.utc)
    return start + ATTACHMENT_BATCH_TTL


def normalize_message_identity(
    telegram_id: object, chat_id: object, message_id: object
) -> tuple[int, int, int] | None:
    """OHB2-P0-A3/D-33/D-34: تحقّق تطبيقي للهوية القانونية للرسالة.

    الهوية = `(telegram_id, chat_id, message_id)`، وكلها يجب أن تكون **أعدادًا صحيحة موجبة**.
    SQLite ديناميكي (تصريح النوع = affinity فقط) ⇒ التحقّق هنا **إلزامي**؛ نرفض: غياب/`None`/
    `bool`/غير `int`/`0`/سالب. `True`/`False` (subclass من `int`) مرفوضان صراحةً. ترجّع
    `None` عند أي قيمة غير صالحة ⇒ المستدعي يفشل مغلقًا (لا يخترع هوية). `update_id` **ليس**
    جزءًا من الهوية (هوية تسليم منفصلة).
    """
    out: list[int] = []
    for value in (telegram_id, chat_id, message_id):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            return None
        out.append(value)
    return (out[0], out[1], out[2])


@dataclass
class Watched:
    conversation_id: str
    title: str
    last_state: str | None
    chat_id: int | None = None
    # وقت (UTC ISO) آخر برومبت اتبعت للشات ده. لو موجود، المراقب ما يعلنش الانتهاء
    # غير لو لقى تقرير أحدث منه (U01). NULL = متابعة يدوية بدون برومبت.
    submitted_at: str | None = None
    added_at: str | None = None
    # TASK 54: عدد محاولات إشعار الانتهاء الفاشلة المتتالية. بيترجع 0 عند بداية دورة
    # إشعار جديدة (حالة غير منتهية جديدة) أو عند إضافة/تحديث المتابعة، وبيمنع تكرار
    # نفس الإشعار بلا حد بعد استنفاد ميزانية المحاولات.
    retry_count: int = 0
    # NTF-13: حالة انتهاء اتّبعت لتليجرام (اتقبلت) لكن تسجيلها الدائم لسه معلّق. NULL =
    # مفيش تسليم معلّق. بتتكتب بعد نجاح الإرسال وقبل التسجيل، وبتتمسح بعد التسجيل الدائم.
    pending_delivery_state: str | None = None
    # NTF-19: معرّف ثابت لكل دورة متابعة (عمود دائم `watch_seq`)، بيتولّد عند الإنشاء/التجديد.
    # التلميحات in-memory (`_marker_pending`) بتتبط بيه، فمتابعة جديدة بمعرّف جديد ما تتأثّرش
    # بتلميح قديم. مش مشتقّ من hash() ولا من الوقت.
    watch_seq: str = ""


@dataclass
class NotificationState:
    conversation_id: str
    status: str | None = None
    # آخر حالة اتّبعت/اتخطّت لها إشعار (تمنع التكرار). None = لسه ماتبلّغش عنها أبدًا.
    notified_status: str | None = None
    retry_count: int = 0
    updated_at: str | None = None
    # OHB2-08-05 (Batch 3R-FIX2): عدّاد انتقالات دائم = **عصر الاكتشاف** لكل انتقال حالة
    # نهائية. بيزيد **مرة واحدة عند اكتشاف** انتقال جديد (مش عند التسليم)، ويثبت خلال كل
    # إعادات المحاولة لنفس الانتقال ⇒ إعادة الاستطلاع/إعادة التشغيل لنفس الانتقال تعيد نفس
    # الرقم (idempotent)، وانتقال جديد لنفس الحالة (finished→running→finished) بياخد رقمًا
    # جديدًا ⇒ حدث منفصل. ده الهوية الموحّدة بين المراقب والمُبلّل.
    transition_seq: int = 0
    # OHB2-08-05 (Batch 3R-FIX2): الحالة النهائية اللي «عصر» `transition_seq` الحالي بيخصّها.
    # بتمنع ترقية العدّاد مرتين لنفس الانتقال المتكرّر، وبتتصفّر عند رؤية حالة غير نهائية
    # (دورة حياة جديدة). NULL = مفيش عصر مفتوح.
    discovered_status: str | None = None


@dataclass
class OutboxItem:
    id: int
    conversation_id: str
    chat_id: int
    text: str
    status: str
    error: str | None
    created_at: str
    updated_at: str
    attempts: int = 0
    # OHB2-07: معرّف العملية اللي العميل يولّده لمنع الازدواج عند إعادة المحاولة.
    client_ref: str | None = None
    # OHB2-POST-PUB-01/F02: حالة إكمال الأثر المحلي (إشعار/متابعة) — منفصلة عن نتيجة
    # العملية الخارجية (`status`). "" = لسه محتاج إكمال، "pending" = بدأ ولسه ماتأكدش
    # (يتعافى)، "sent" = خلص.
    notify_state: str = NOTIFY_NONE


@dataclass
class CreationJob:
    id: int
    chat_id: int
    repo: str | None
    text: str
    status: str
    task_id: str | None
    conversation_id: str | None
    error: str | None
    created_at: str
    updated_at: str
    attempts: int = 0
    # OHB2-07: معرّف العملية اللي العميل يولّده لمنع ازدواج إنشاء الشات عند إعادة المحاولة.
    client_ref: str | None = None
    # OHB2-POST-PUB-01/F02: حالة إكمال الأثر المحلي لطلب الشات الجديد (إشعار الرابط +
    # تسجيل المتابعة). نفس عقد الـ outbox.
    notify_state: str = CREATION_NOTIFY_NONE


@dataclass
class CompletionPending:
    """عمل إكمال محلي معلّق (إشعار/تسجيل متابعة) بعد نجاح العملية الخارجية (F02).

    منفصل تمامًا عن نتيجة العملية الخارجية: وجود صف هنا يعني «الـ POST الخارجي اتأكد،
    ولسه فيه أثر محلي (إشعار المستخدم + تسجيل المتابعة) محتاج إكمال». الإكمال المحلي
    ما بيعملش أي POST خارجي، فالتكرار/التعافي آمن.
    """

    ref_kind: str
    ref_id: int
    chat_id: int
    conversation_id: str
    title: str = ""
    last_state: str | None = None
    submitted_at: str | None = None
    notice_text: str = ""
    attempts: int = 0
    last_error: str | None = None
    # OHB2-STABILIZATION-F02: موعد المحاولة التالية (ISO). NULL/'' = مؤهّل حالًا. بيسمح
    # بجدولة إعادة محاولة دائمة (backoff) فاللي فشل مايفضلش أول عنصر مؤهّل للأبد.
    next_attempt_at: str | None = None
    # OHB2-STABILIZATION-F02: عدد المرات اللي العنصر فشل فيها (مستقل عن `attempts` اللي
    # بيتصفّر عند الجدولة) — بيفرّق بين «مؤجّل» و«مستنفد» بشكل واضح للرصد.
    failures: int = 0
    # OHB2-STABILIZATION-F02: علم «مستنفد/مطلوب تدخّل» (0/1). بيتحدّد لما نوصل
    # COMPLETION_MAX_ATTEMPTS؛ بيبقى ظاهر للمشغّل ومستبعد من العناصر المؤهّلة افتراضيًا.
    exhausted: int = 0
    created_at: str = ""
    updated_at: str = ""


@dataclass
class InboxItem:
    """OHB2-08-05: حدث إشعار واحد في الصندوق (سجل دائم للحدث المُكتشَف).

    الحدث بيتسجّل عند **لحظة اكتشافه المنطقية** (قبل أي محاولة إرسال لتليجرام)، وحالة
    التسليم (`delivery_status`) بتتحدّث **بعد كده** بشكل مستقل — فالصندوق سجل للأحداث
    المُكتشَفة، مش سجل للتسليمات الناجحة بس.
    """

    id: int
    conversation_id: str
    title: str
    kind: str
    message: str
    created_at: str
    read_at: str | None = None
    # OHB2-08-05: مفتاح الهوية المنطقية للحدث (idempotency). NULL للسجلات القديمة اللي
    # اتكتبت قبل إضافة العمود. بيُستخدم لقيد التفرّد الجزئي عشان نفس الحدث ما يتسجّلش مرتين.
    event_key: str | None = None
    # OHB2-08-05 (Batch 3R): بيانات التسليم المستقلة عن حالة القراءة.
    delivery_status: str = INBOX_DELIVERY_DELIVERED
    delivery_attempts: int = 0
    last_attempt_at: str | None = None
    delivered_at: str | None = None
    last_error: str | None = None
    next_retry_at: str | None = None
    # OHB2-08-05 (Batch 3R): وجهة التسليم المحفوظة مع الحدث (المراقب/المُبلّغ) عشان
    # إعادة المحاولة/الاسترجاع يقدروا يبعتوا الحدث حتى لو صف المتابعة اتشال.
    chat_id: int | None = None
    # OHB2-08-05 (Batch 3R-FIX2): الحالة **المرصودة** عند إنشاء الحدث — **وصفية** بس
    # (للعرض/التنسيق). مش الهوية: الهوية هي `transition_seq`.
    transition_status: str | None = None
    # OHB2-08-05 (Batch 3R-FIX2): هوية الانتقال الدائمة (عصر الاكتشاف). قيد التفرّد الجزئي
    # بيشتغل على (المحادثة، `transition_seq`) للصفوف المعلّقة، فانتقالين مختلفين بنفس الحالة
    # بياخدوا رقمين مختلفين ⇒ حدثين منفصلين (حتى لو واحد لسه معلّق). NULL للسجلات القديمة.
    transition_seq: int | None = None
    # OHB2-08-05 (Batch 3R-FIX2-F1): رمز حجز ذرّي (claim lease) لمحاولة تسليم جارية. NULL =
    # مش محجوز (متاح للاسترجاع). بيتكتب في معاملة ذرّية قبل الإرسال وبيتشال بعد المحاولة،
    # فبيمنع المراقب والمُبلّل من إرسال نفس الحدث معًا في نفس اللحظة. مش هُوية دائمة.
    claim_token: str | None = None
    # وقت أخذ الحجز (ISO). بيسمح بحجز له مدة صلاحية: حجز قديم (من عملية وقعت) بيتحرّر تلقائيًا.
    claim_at: str | None = None
    # OHB2-PHASE1C: محور **الأرشفة** (منفصل تمامًا عن القراءة والتسليم). NULL = نشط
    # (ظاهر في الصندوق العادي). وقت ISO = مؤرشف (مخفي من العادي، بيظهر في عرض الأرشيف).
    # الأرشفة **قابلة للعكس** (`archived_at` بس، مفيش أي مساس بالتسليم/العملية/القراءة).
    archived_at: str | None = None

    @property
    def unread(self) -> bool:
        return self.read_at is None

    @property
    def archived(self) -> bool:
        return self.archived_at is not None

    @property
    def delivery_pending(self) -> bool:
        return self.delivery_status == INBOX_DELIVERY_PENDING


@dataclass
class AttachmentBatch:
    """OHB2-P0-A0: صف دفعة مرفقات محلية واحدة (المخطّط فقط — بلا منطق دورة حياة).

    الدفعة **client-side** بالكامل (I4/I6/§8.4): `T0` هو ختم UTC المطلق لأول ملف،
    وبيتخزّن **مرة واحدة** وعمره ما بيتمدّد. الحالة مربوطة بالمستخدم والمحادثة الصريحة.
    """

    batch_id: str
    telegram_id: int
    conversation_id: str
    t0: str
    status: str = ATTACHMENT_BATCH_PENDING
    created_at: str | None = None
    updated_at: str | None = None
    # OHB2-P0-A3/D-27: النصّ المصاحب المؤهّل المخزَّن محليًّا (None قبل تسجيل النيّة).
    intent_text: str | None = None


class AttachmentRoutingState(str, Enum):
    """نتيجة تصنيف حالة المرفقات عند حدّ توجيه النصّ (A3 — D-32)."""

    NONE = "none"                        # مفيش أي دفعة ذات صلة ⇒ البرومت العادي كما هو
    LIVE = "live"                        # دفعة `pending` حيّة **وحيدة** ⇒ مسار النصّ المصاحب
    MULTI_LIVE = "multi_live"            # أكثر من دفعة `pending` حيّة ⇒ غموض (فشل مغلق)
    EXPIRED_PENDING = "expired_pending"  # دفعة `pending` **منتهية** (بلا حيّة) ⇒ لا إحياء
    UNRESOLVED = "unresolved"            # دفعة غير محسومة (نيّة/إرسال معلّق) ⇒ تحجب
    TERMINAL = "terminal"                # دفعة نهائية فقط ⇒ **لا تحجب** برومتًا جديدًا
    # OHB2-P0-A3/D-34: تمييز الحالة النهائية بحسب دليل هوية الرسالة الواردة.
    TERMINAL_ASSOCIATED = "terminal_associated"   # النصّ **مُثبَت** ارتباطه بدفعة نهائية ⇒ حجب
    TERMINAL_UNPROVEN = "terminal_unproven"       # دفعة نهائية + **لا** دليل هوية ⇒ فشل مغلق (D-34)


@dataclass(frozen=True)
class AttachmentRouting:
    """نتيجة `classify_attachment_routing` (A3 — D-32): الحالة + الدفعات ذات الصلة."""

    state: AttachmentRoutingState
    live_batches: tuple[AttachmentBatch, ...] = ()
    unresolved_batches: tuple[AttachmentBatch, ...] = ()


@dataclass
class AttachmentItem:
    """OHB2-P0-A0: صف عنصر واحد داخل دفعة مرفقات (المخطّط فقط).

    `staging_token` مرجع **غير شفّاف** لبايتات الـ staging المحلية (اسم الملف الفعلي
    بيحدّده A1)؛ ما بنخزّنش اسم ملف المستخدم ولا أي محتوى.
    """

    item_id: str
    batch_id: str
    staging_token: str | None = None
    display_name: str | None = None
    size_bytes: int | None = None
    status: str = ATTACHMENT_BATCH_PENDING
    created_at: str | None = None
    updated_at: str | None = None


class Database:
    def __init__(self, path: str) -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # WAL + busy_timeout عشان الكتابة من الـ handlers والمراقب في وقت واحد
        # ما ترميش "database is locked".
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        # OHB2-P0-A3/D-35: فرض المفاتيح الأجنبية على **الاتصال الإنتاجي**. SQLite افتراضيًّا
        # OFF، والـpragma **لكل اتصال** (مش عالمي). تُنفَّذ هنا **قبل أي معاملة** (شرط SQLite:
        # لا يمكن تغييرها داخل معاملة نشطة) — بعد `connect` مباشرة. فشل التفعيل ⇒ استثناء
        # (fail-closed) بدل المتابعة بلا حماية FK على ربط الهوية↔الدفعة.
        self._conn.execute("PRAGMA foreign_keys=ON")
        if self._conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise RuntimeError(
                "PRAGMA foreign_keys=ON لم يُفعَّل على اتصال الإنتاج (fail-closed)"
            )
        # NTF-20: hook اختياري ينسّق التلميح in-memory للتسليم المعلّق قبل بدء دورة متابعة
        # جديدة. المراقب بيسجّله (زي set_owner_delivery) عشان كل مستدعي `add_watched`
        # (handlers/outbox/creation) يستفيد من غير ما يعرف المراقب.
        self.on_new_watch_lifecycle = None
        # OHB2-08-03: hook اختياري **مكمّل** ينسّق دليل التسليم in-memory (تلميح
        # `_marker_pending` اللي بيتسجّل لما كتابة العلامة الدائمة نفسها تفشل) عند إزالة
        # المتابعة. المراقب بيسجّله (زي `on_new_watch_lifecycle`)، فأي مسار إزالة (الـ
        # handlers أو الـ Mini App fallback `db.remove_watched` لما المراقب مش متاح) ينسّق
        # التلميح بدل ما يسيبه معلّق ⇒ مايحصلش إشعار مكرّر. اختياري: لو None (استخدام
        # مستقل) السلوك زي ما هو. بيرمي لو فشل، فالإزالة ما تتكمّلش (fail-safe).
        self.on_unwatch = None
        # OHB2-POST-PUB-01/F06: نتيجة فحص التكامل عند بدء التشغيل. None = لسه ماتفحصش،
        # True = سليم، False = فشل/غير مؤكد. الـ readiness بيعتمد عليها (ما بيعلنش READY
        # قبل ما الفحص المطلوب ينجح فعلاً).
        self.integrity_ok: bool | None = None
        self._init_schema()

    def is_healthy(self) -> bool:
        """هل القاعدة اجتازت فحص التكامل المطلوب عند البدء؟ (False قبل الفحص أو بعده)."""
        return self.integrity_ok is True

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS watched (
                conversation_id TEXT PRIMARY KEY,
                title           TEXT NOT NULL DEFAULT '',
                last_state      TEXT,
                chat_id         INTEGER,
                submitted_at    TEXT,
                added_at        TEXT,
                retry_count     INTEGER NOT NULL DEFAULT 0,
                pending_delivery_state TEXT,
                watch_seq       TEXT
            );
            CREATE TABLE IF NOT EXISTS user_state (
                telegram_id INTEGER PRIMARY KEY,
                awaiting_conversation_id TEXT,
                awaiting_kind            TEXT,
                awaiting_at              TEXT,
                awaiting_title           TEXT
            );
            CREATE TABLE IF NOT EXISTS outbox (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                chat_id         INTEGER NOT NULL,
                text            TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'pending',
                error           TEXT,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL,
                attempts        INTEGER NOT NULL DEFAULT 0,
                client_ref      TEXT,
                notify_state    TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_outbox_status ON outbox(status);
            CREATE TABLE IF NOT EXISTS creation_jobs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id         INTEGER NOT NULL,
                repo            TEXT,
                text            TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'pending',
                task_id         TEXT,
                conversation_id TEXT,
                error           TEXT,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL,
                attempts        INTEGER NOT NULL DEFAULT 0,
                client_ref      TEXT,
                notify_state    TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_creation_jobs_status ON creation_jobs(status);
            -- OHB2-POST-PUB-01/F02: أعمال الإكمال المحلي المعلّقة (إشعار + تسجيل متابعة)
            -- بعد نجاح العملية الخارجية. بتُسجَّل write-ahead، وبتتعافى بعد restart،
            -- وبتتشال بعد ما تخلص. منفصلة تمامًا عن نتيجة العملية الخارجية (outbox/creation
            -- .status) ⇒ الإكمال المحلي ما بيعملش POST خارجي أبدًا (at-most-once محفوظ).
            CREATE TABLE IF NOT EXISTS completion_pending (
                ref_kind        TEXT NOT NULL,
                ref_id          INTEGER NOT NULL,
                chat_id         INTEGER NOT NULL,
                conversation_id TEXT NOT NULL,
                title           TEXT NOT NULL DEFAULT '',
                last_state      TEXT,
                submitted_at    TEXT,
                notice_text     TEXT NOT NULL DEFAULT '',
                attempts        INTEGER NOT NULL DEFAULT 0,
                last_error      TEXT,
                next_attempt_at TEXT,
                failures        INTEGER NOT NULL DEFAULT 0,
                exhausted       INTEGER NOT NULL DEFAULT 0,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL,
                PRIMARY KEY (ref_kind, ref_id)
            );
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS notification_state (
                conversation_id TEXT PRIMARY KEY,
                status          TEXT,
                notified_status TEXT,
                retry_count     INTEGER NOT NULL DEFAULT 0,
                updated_at      TEXT,
                transition_seq  INTEGER NOT NULL DEFAULT 0,
                discovered_status TEXT
            );
            CREATE TABLE IF NOT EXISTS notifier_pending (
                conversation_id TEXT PRIMARY KEY,
                state           TEXT NOT NULL,
                updated_at      TEXT,
                event_id        INTEGER,
                transition_seq  INTEGER
            );
            CREATE TABLE IF NOT EXISTS notifier_retry_not_before (
                conversation_id TEXT PRIMARY KEY,
                not_before      TEXT NOT NULL
            );
            -- OHB2-08-05: صندوق الإشعارات — سجل **دائم للأحداث المُكتشَفة** (مش للتسليمات
            -- الناجحة بس). الحدث بيتسجّل عند اكتشافه قبل أي إرسال؛ وحالة التسليم
            -- (`delivery_status`) بتتحدّث بشكل مستقل. بيتعمل هنا بـ IF NOT EXISTS
            -- فالقواعد القديمة بتاخده تلقائيًا (إضافي وغير مدمّر — مفيش فقد بيانات).
            CREATE TABLE IF NOT EXISTS notification_inbox (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                title           TEXT NOT NULL DEFAULT '',
                kind            TEXT NOT NULL DEFAULT '',
                message         TEXT NOT NULL DEFAULT '',
                created_at      TEXT NOT NULL,
                read_at         TEXT,
                event_key       TEXT,
                delivery_status TEXT NOT NULL DEFAULT 'delivered',
                delivery_attempts INTEGER NOT NULL DEFAULT 0,
                last_attempt_at TEXT,
                delivered_at    TEXT,
                last_error      TEXT,
                next_retry_at   TEXT,
                chat_id         INTEGER,
                transition_status TEXT,
                transition_seq  INTEGER,
                claim_token     TEXT,
                claim_at        TEXT,
                archived_at     TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_inbox_unread ON notification_inbox(read_at);
            CREATE INDEX IF NOT EXISTS idx_inbox_conversation
                ON notification_inbox(conversation_id, id);
            -- OHB2-C7 (RESURRECTION-FIX): شاهد حذف **دائم** (tombstone). بيتكتب في نفس
            -- معاملة الحذف، وبيفضل بعد إعادة التشغيل. أي مسار بيعيد إنشاء حالة شات نشطة
            -- (متابعة/إكمال/إشعار/طلب) لازم يرفض معرّف متشاهد (إلا لو المستخدم أعاد
            -- التفاعل صريح ⇒ الـ tombstone يتشال). `CREATE TABLE IF NOT EXISTS` ⇒ القواعد
            -- القديمة بتاخده تلقائيًا (إضافي وغير مدمّر — مفيش فقد بيانات).
            CREATE TABLE IF NOT EXISTS deleted_conversations (
                conversation_id TEXT PRIMARY KEY,
                deleted_at      TEXT,
                remote_state    TEXT,
                remote_updated_at TEXT,
                witness_origin  TEXT,
                witness_attempt_id TEXT,
                witness_preexisting INTEGER NOT NULL DEFAULT 0
            );
            -- OHB2-PHASE1A: جلسات الـ Mini App **دائمة** (بدل in-memory). العمود
            -- `token_hash` هو SHA-256 للتوكن الخام؛ **التوكن الخام ما بيتخزّنش أبدًا**.
            -- `expires_at` ختم زمني من السيرفر (unix float) بيحكم الانتهاء حتى لو العميل
            -- فضل يبعت الكوكي. الحذف من نفس الجدول = إلغاء (revoke) دائم ينجو من restart.
            -- `CREATE TABLE IF NOT EXISTS` ⇒ إضافي وغير مدمّر للقواعد القديمة.
            CREATE TABLE IF NOT EXISTS web_sessions (
                token_hash  TEXT PRIMARY KEY,
                user_id     INTEGER NOT NULL,
                created_at  REAL NOT NULL,
                expires_at  REAL NOT NULL,
                profile     TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_web_sessions_expires ON web_sessions(expires_at);
            -- OHB2-DUPLICATE-TELEGRAM-PROMPT-DISPATCH: سجل **دائم** لمعرّفات تحديثات تيليجرام
            -- اللي اتعالجت، عشان ضمان «تحديث واحد ⇒ قرار معالجة واحد». `update_id` مفتاح
            -- أساسي (فريد على مستوى تيليجرام)، فإعادة تسليم نفس التحديث (شبكة/إعادة تشغيل/
            -- تزامن) بتتصدّ قبل أي عملية خارجية (إرسال أو إنشاء). ده **كشف تكرار** مش ضمان
            -- exactly-once خارجي (نفس عقد المشروع الموثّق). `processed_at` وصفى للتشغيل
            -- والتنظيف. `CREATE TABLE IF NOT EXISTS` ⇒ إضافي وغير مدمّر للقواعد القديمة.
            CREATE TABLE IF NOT EXISTS processed_updates (
                update_id    INTEGER PRIMARY KEY,
                processed_at TEXT NOT NULL,
                -- OHB2-MANUAL-POLLING-OUTCOME: فئة النتيجة الدائمة. NULL للصفوف القديمة
                -- (= غير مؤهّلة للإقرار، fail-closed) لحد ما تُكتب مع العملية الدائمة.
                outcome      TEXT
            );
            -- OHB2-MANUAL-POLLING-OUTCOME: سجل الفشل الدائم للتحديثات اللي **مالهاش** عمل
            -- دائم (تحديث مرفوض/غير مدعوم، أو handler فشل/ابتلع استثناء). وجود صف هنا = فيه
            -- قرار مُوثَّق (fail-closed: مايتقبلش كنجاح). منفصل عن `processed_updates` عشان
            -- ما نغيّرش دلالات الديدَب القائمة. `CREATE TABLE IF NOT EXISTS` ⇒ إضافي.
            CREATE TABLE IF NOT EXISTS update_failures (
                update_id   INTEGER PRIMARY KEY,
                outcome     TEXT NOT NULL,
                reason      TEXT,
                failed_at   TEXT NOT NULL
            );
            -- OHB2-P0-A0 (المخطّط فقط): حالة الدفعة/العنصر المحلية للمرفقات في قاعدة
            -- SQLite القائمة (نفس المالك — I2/I3/I5، بلا قاعدة ثانية/عمّال/مجدول).
            -- الدفعة **client-side** (I4/I6/§8.4): `t0` ختم UTC مطلق لأول ملف،
            -- **ثابت وعمره ما بيتمدّد**؛ ما بنخزّنش `expires_at` مشتق ولا أي شيء يتحدّث
            -- مع كل ملف. الحالة مربوطة بالمستخدم (`telegram_id`) والمحادثة الصريحة
            -- (`conversation_id`) ⇒ العزل بين المستخدمين/المحادثات قابل للفرض بفحص ملكية
            -- الصف. حالة الدفعة من مجموعة `ATTACHMENT_BATCH_STATUSES`. إضافي وغير مدمّر.
            CREATE TABLE IF NOT EXISTS attachment_batches (
                batch_id        TEXT PRIMARY KEY,
                telegram_id     INTEGER NOT NULL,
                conversation_id TEXT NOT NULL,
                t0              TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'pending',
                created_at      TEXT,
                updated_at      TEXT,
                intent_text     TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_attachment_batches_owner
                ON attachment_batches(telegram_id, conversation_id);
            -- عنصر واحد لكل ملف مرفق في الدفعة. `batch_id` مرجع للدفعة الأب (I5:
            -- صفوف دفعة+عنصر متينة). `staging_token` مرجع غير شفّاف لبايتات الـ staging
            -- (اسم الملف الفعلي/دورة الكتابة = A1)؛ ما بنخزّنش محتوى ولا اسم ملف المستخدم.
            CREATE TABLE IF NOT EXISTS attachment_items (
                item_id       TEXT PRIMARY KEY,
                batch_id      TEXT NOT NULL,
                staging_token TEXT,
                display_name  TEXT,
                size_bytes    INTEGER,
                status        TEXT NOT NULL DEFAULT 'pending',
                created_at    TEXT,
                updated_at    TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_attachment_items_batch
                ON attachment_items(batch_id);
            -- OHB2-P0-A3/D-33/D-35: دليل هوية رسالة↔دفعة **متين ومستقلّ** عن
            -- `processed_updates` (التقليم مايلمسوش). الهوية القانونية =
            -- (telegram_id, chat_id, message_id)؛ `update_id` هوية تسليم منفصلة وليست بديلًا
            -- عن `message_id`. الـPK يمنع إعادة ربط رسالة واحدة بدفعة أخرى صامتًا (تعارض ⇒
            -- IntegrityError ⇒ فشل مغلق). الـFK `ON DELETE RESTRICT` (بلا cascade) يمنع حذف
            -- دليل الهوية مع الدفعة — يُفرض فعليًّا عبر `PRAGMA foreign_keys=ON` في `__init__`.
            -- بلا مدّة احتفاظ/بلا عامل تنظيف (D-35 بند 6).
            CREATE TABLE IF NOT EXISTS attachment_message_identity (
                telegram_id     INTEGER NOT NULL,
                chat_id         INTEGER NOT NULL,
                message_id      INTEGER NOT NULL,
                batch_id        TEXT    NOT NULL,
                conversation_id TEXT    NOT NULL,
                created_at      TEXT    NOT NULL,
                PRIMARY KEY (telegram_id, chat_id, message_id),
                FOREIGN KEY (batch_id) REFERENCES attachment_batches(batch_id)
                    ON DELETE RESTRICT
            );
            CREATE INDEX IF NOT EXISTS idx_attachment_message_identity_batch
                ON attachment_message_identity(batch_id);
            """
        )
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        """يضيف الأعمدة/الجداول الجديدة لقواعد موجودة من نسخ أقدم (غير مدمّر)."""
        columns = {r["name"] for r in self._conn.execute("PRAGMA table_info(watched)")}
        if "chat_id" not in columns:
            self._conn.execute("ALTER TABLE watched ADD COLUMN chat_id INTEGER")
        state_cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(user_state)")}
        if state_cols and "awaiting_at" not in state_cols:
            self._conn.execute("ALTER TABLE user_state ADD COLUMN awaiting_at TEXT")
        if state_cols and "awaiting_title" not in state_cols:
            self._conn.execute("ALTER TABLE user_state ADD COLUMN awaiting_title TEXT")
        if "submitted_at" not in columns:
            self._conn.execute("ALTER TABLE watched ADD COLUMN submitted_at TEXT")
        if "added_at" not in columns:
            self._conn.execute("ALTER TABLE watched ADD COLUMN added_at TEXT")
        # TASK 54: عدّاد محاولات إشعار الانتهاء. عمود إضافي بقيمة افتراضية 0، فالصفوف
        # القديمة بتاخد ميزانية محاولات كاملة من غير أي فقد بيانات.
        if "retry_count" not in columns:
            self._conn.execute(
                "ALTER TABLE watched ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0"
            )
        # NTF-13: علامة تسليم معلّق (write-ahead). بتتكتب **بعد** ما تيليجرام يقبل رسالة
        # انتهاء و**قبل** التسجيل الدائم، عشان إزالة المتابعة من أي مسار (أو إعادة تشغيل)
        # تكمّل التسجيل الدائم بدل ما تتسيب حالة قديمة يعيد المُبلّغ إرسالها. عمود إضافي
        # بقيمة NULL افتراضية ⇒ مفيش فقد بيانات للصفوف القديمة.
        if "pending_delivery_state" not in columns:
            self._conn.execute("ALTER TABLE watched ADD COLUMN pending_delivery_state TEXT")
        # NTF-19: معرّف دورة المتابعة (عمود إضافي غير مدمّر). الصفوف القديمة بتاخد NULL ثم
        # تتعبّى فورًا بمعرّف ثابت مولّد من SQLite (تحت)، فكل قراءة ترجّع نفس المعرّف.
        if "watch_seq" not in columns:
            self._conn.execute("ALTER TABLE watched ADD COLUMN watch_seq TEXT")
        # NTF-19: نعبّي المعرّف للصفوف القديمة بمعرّف ثابت **مولّد من SQLite** (randomblob)
        # عشان القراءات المتكرّرة ترجّع نفس المعرّف (مايتولّدش عشوائيًا في كل قراءة).
        self._conn.execute(
            "UPDATE watched SET watch_seq = lower(hex(randomblob(16))) WHERE watch_seq IS NULL"
        )
        # outbox اتعمل في 04A-4 من غير attempts؛ نضيفه لقواعد موجودة.
        outbox_cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(outbox)")}
        if outbox_cols and "attempts" not in outbox_cols:
            self._conn.execute("ALTER TABLE outbox ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0")
        # OHB2-MANUAL-POLLING-OUTCOME: عمود النتيجة على جدول الديدَب (nullable ⇒ الصفوف
        # القديمة بتاخد NULL = غير مؤهّلة، fail-closed؛ غير مدمّر).
        pu_cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(processed_updates)")}
        if pu_cols and "outcome" not in pu_cols:
            self._conn.execute("ALTER TABLE processed_updates ADD COLUMN outcome TEXT")
        # OHB2-07: معرّف العملية اللي العميل يولّده (idempotency). عمود إضافي nullable،
        # والصفوف القديمة بتاخد NULL (مفيش فقد بيانات، والسلوك القديم زي ما هو).
        if outbox_cols and "client_ref" not in outbox_cols:
            self._conn.execute("ALTER TABLE outbox ADD COLUMN client_ref TEXT")
        # OHB2-POST-PUB-01/F02: حالة إكمال الأثر المحلي (nullable ⇒ الصفوف القديمة بتاخد
        # '' = لسه محتاج إكمال محلي لو الـ POST نجح؛ غير مدمّر).
        if outbox_cols and "notify_state" not in outbox_cols:
            self._conn.execute(
                "ALTER TABLE outbox ADD COLUMN notify_state TEXT NOT NULL DEFAULT ''"
            )
        creation_cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(creation_jobs)")}
        if creation_cols and "client_ref" not in creation_cols:
            self._conn.execute("ALTER TABLE creation_jobs ADD COLUMN client_ref TEXT")
        if creation_cols and "notify_state" not in creation_cols:
            self._conn.execute(
                "ALTER TABLE creation_jobs ADD COLUMN notify_state TEXT NOT NULL DEFAULT ''"
            )
        # OHB2-STABILIZATION-F02: أعمدة جدولة إعادة المحاولة/الاستنفاد لجدول الإكمال
        # المعلّق. قواعد قديمة (بعد F02 الأصلي) بتاخدها إضافيًا وغير مدمّر — الصفوف القديمة
        # بتاخد NULL/0 = مؤهّلة حالًا ولسه ماتستنفدتش.
        completion_cols = {
            r["name"] for r in self._conn.execute("PRAGMA table_info(completion_pending)")
        }
        if completion_cols and "next_attempt_at" not in completion_cols:
            self._conn.execute("ALTER TABLE completion_pending ADD COLUMN next_attempt_at TEXT")
        if completion_cols and "failures" not in completion_cols:
            self._conn.execute(
                "ALTER TABLE completion_pending ADD COLUMN failures INTEGER NOT NULL DEFAULT 0"
            )
        if completion_cols and "exhausted" not in completion_cols:
            self._conn.execute(
                "ALTER TABLE completion_pending ADD COLUMN exhausted INTEGER NOT NULL DEFAULT 0"
            )
        # بعد ضمان وجود العمودين (للجداول القديمة كمان)، نعمل فهارس معرّف العملية.
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_outbox_client_ref ON outbox(client_ref)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_creation_jobs_client_ref ON creation_jobs(client_ref)"
        )
        # OHB2-08-04: فهرسان مركّبان مبنيّان على أنماط استعلام فعلية (EXPLAIN QUERY PLAN +
        # قياس). `idx_outbox_status` بيفلتر بـ status بس، فاستعلامات النضج/التجميع بتقرأ كل
        # صفوف الحالة وتعمل ترتيب مؤقّت (USE TEMP B-TREE FOR ORDER BY). الفهرسين دول بيمدّوا
        # مسار الفهرس للحقول اللي بيتفلتر/بيترتّب بيها كمان:
        # - `idx_outbox_status_updated`: بيسرّع `seconds_until_mature` (تحديد موعد نوم الـ
        #   worker — بيتنادى كل دورة) ويخلي الحجز الناضج يفلتر status+updated_at جوه الفهرس.
        # - `idx_outbox_conv_chat_status`: بيسرّع استعلام التجميع في `add_or_group_outbox`
        #   (بيدور على أحدث 'pending' لنفس الوجهة (conversation_id, chat_id)).
        # مفيش مسار كتابة (claim/set_status) بيتأثّر: بيحجز بالـ rowid الأساسي زي ما هو،
        # و`idx_outbox_status` لسه متاح لاستعلامات status-only. إضافي وidempotent.
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_outbox_status_updated ON outbox(status, updated_at)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_outbox_conv_chat_status "
            "ON outbox(conversation_id, chat_id, status)"
        )
        # creation_jobs اتعمل في 04A-6 (جدول جديد)؛ CREATE IF NOT EXISTS فوق بيكفّي
        # للقواعد القديمة، وبنضمن عمود attempts لو الجدول موجود من نسخة أقدم.
        # OHB2-08-01: علامة التسليم المعلّق للمُبلّغ العام (durable). الجدول بيتعمل من
        # `CREATE TABLE IF NOT EXISTS` فوق، فالقواعد القديمة بتاخده تلقائيًا (إضافي وغير
        # مدمّر — مفيش صفوف ولا فقد بيانات). مفيش أي تعديل على أعمدة موجودة.
        # OHB2-08-05: عمود هوية الحدث في الصندوق (nullable ⇒ الصفوف القديمة بتاخد NULL،
        # مفيش فقد بيانات). الفهارس بتتعمل **بعد** ضمان الأعمدة عشان القواعد القديمة ما تفشلش.
        # OHB2-08-05 (Batch 3R): عمود عدّاد الانتقالات للمُبلّغ (nullable بقيمة افتراضية 0).
        state_cols2 = {
            r["name"] for r in self._conn.execute("PRAGMA table_info(notification_state)")
        }
        if state_cols2 and "transition_seq" not in state_cols2:
            self._conn.execute(
                "ALTER TABLE notification_state ADD COLUMN transition_seq "
                "INTEGER NOT NULL DEFAULT 0"
            )
        # OHB2-08-05 (Batch 3R-FIX2): الحالة النهائية اللي عصر `transition_seq` بيخصّها.
        if state_cols2 and "discovered_status" not in state_cols2:
            self._conn.execute(
                "ALTER TABLE notification_state ADD COLUMN discovered_status TEXT"
            )
        # OHB2-08-05 (Batch 3R): ربط علامة تسليم المُبلّغ المعلّقة بحدث الصندوق (event_id)
        # عشان الاسترجاع بعد إعادة التشغيل يعلّم **نفس** الحدث `delivered` بدل ما يسيب حدثًا
        # معلّق للأبد. عمود إضافي nullable (الصفوف القديمة بتاخد NULL).
        np_cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(notifier_pending)")}
        if np_cols and "event_id" not in np_cols:
            self._conn.execute("ALTER TABLE notifier_pending ADD COLUMN event_id INTEGER")
        if np_cols and "transition_seq" not in np_cols:
            self._conn.execute("ALTER TABLE notifier_pending ADD COLUMN transition_seq INTEGER")
        inbox_cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(notification_inbox)")}
        if inbox_cols and "event_key" not in inbox_cols:
            self._conn.execute("ALTER TABLE notification_inbox ADD COLUMN event_key TEXT")
        # OHB2-08-05 (Batch 3R): أعمدة بيانات التسليم. كلها إضافية nullable (أو بقيمة
        # افتراضية) ⇒ الصفوف القديمة مايتفقدش منها حاجة. الصفوف القديمة (اللي كانت
        # بتتسجّل بعد نجاح الإرسال بس) بنعبّيها `delivered` (ده اللي حصل فعلًا)، والصفوف
        # الجديدة بتتسجّل `pending` من البداية.
        if inbox_cols and "delivery_status" not in inbox_cols:
            self._conn.execute(
                "ALTER TABLE notification_inbox ADD COLUMN delivery_status "
                "TEXT NOT NULL DEFAULT 'delivered'"
            )
        if inbox_cols and "delivery_attempts" not in inbox_cols:
            self._conn.execute(
                "ALTER TABLE notification_inbox ADD COLUMN delivery_attempts "
                "INTEGER NOT NULL DEFAULT 0"
            )
        if inbox_cols and "last_attempt_at" not in inbox_cols:
            self._conn.execute("ALTER TABLE notification_inbox ADD COLUMN last_attempt_at TEXT")
        if inbox_cols and "delivered_at" not in inbox_cols:
            self._conn.execute("ALTER TABLE notification_inbox ADD COLUMN delivered_at TEXT")
        if inbox_cols and "last_error" not in inbox_cols:
            self._conn.execute("ALTER TABLE notification_inbox ADD COLUMN last_error TEXT")
        if inbox_cols and "next_retry_at" not in inbox_cols:
            self._conn.execute("ALTER TABLE notification_inbox ADD COLUMN next_retry_at TEXT")
        if inbox_cols and "chat_id" not in inbox_cols:
            self._conn.execute("ALTER TABLE notification_inbox ADD COLUMN chat_id INTEGER")
        # OHB2-08-05 (Batch 3R-FIX): الحالة المرصودة عند إنشاء الحدث — هوية الانتقال
        # المنطقية المشتركة بين المراقب والمُبلّل. عمود إضافي nullable (الصفوف القديمة
        # بتاخد NULL ⇒ مفيش فقد بيانات ولا تأثّر على القيد الموحّد).
        if inbox_cols and "transition_status" not in inbox_cols:
            self._conn.execute(
                "ALTER TABLE notification_inbox ADD COLUMN transition_status TEXT"
            )
        # OHB2-08-05 (Batch 3R-FIX2): عمود هوية الانتقال الدائمة (عصر الاكتشاف). إضافي
        # nullable (الصفوف القديمة بتاخد NULL). **مش** وصف الحالة — الهوية الفعلية.
        if inbox_cols and "transition_seq" not in inbox_cols:
            self._conn.execute(
                "ALTER TABLE notification_inbox ADD COLUMN transition_seq INTEGER"
            )
        # OHB2-08-05 (Batch 3R-FIX2-F1): رمز حجز ذرّي (claim lease) للحدث المعلّق — بيمنع
        # إرسال نفس الحدث من العاملين معًا في نفس اللحظة. إضافي nullable (الصفوف القديمة
        # بتاخد NULL = مش محجوز). بيتشال بعد كل محاولة تسليم (نجحت أو فشلت).
        if inbox_cols and "claim_token" not in inbox_cols:
            self._conn.execute(
                "ALTER TABLE notification_inbox ADD COLUMN claim_token TEXT"
            )
        # وقت أخذ الحجز (ISO) — بيتقرن بـ `claim_token`. بيسمح بحجز له **مدة صلاحية**:
        # حجز قديم (من عملية وقعت قبل ما تحرّره) بيتخطّى/يتحرّر تلقائيًا فما يعلّقش الحدث للأبد.
        if inbox_cols and "claim_at" not in inbox_cols:
            self._conn.execute(
                "ALTER TABLE notification_inbox ADD COLUMN claim_at TEXT"
            )
        # OHB2-PHASE1C: عمود الأرشفة (محور منفصل وقابل للعكس). إضافي nullable ⇒ الصفوف
        # القديمة بتاخد NULL = نشطة (مفيش فقد بيانات، ومفيش تغيير في سلوك القراءة/التسليم).
        if inbox_cols and "archived_at" not in inbox_cols:
            self._conn.execute(
                "ALTER TABLE notification_inbox ADD COLUMN archived_at TEXT"
            )
        if inbox_cols:
            self._conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_inbox_event_key "
                "ON notification_inbox(event_key) WHERE event_key IS NOT NULL"
            )
            # تنظيف: الفهرس القديم (Batch 3R-FIX) كان على (المحادثة، transition_status) وده
            # كان بيحجب انتقالًا حقيقيًا تاني بنفس الحالة — اتصلّح في 3R-FIX2. بنشيله الأول
            # (فهرس بس — مفيش مساس بالبيانات) عشان نستبدله بفهرس الهوية الصح.
            self._conn.execute("DROP INDEX IF EXISTS idx_inbox_transition_unique")
            # OHB2-08-05 (Batch 3R-FIX2): قيد التفرّد الموحّد على **هوية الانتقال**
            # (`transition_seq`)، مش على وصف الحالة. ده اللي بيمنع ازدواج الإشعار لنفس
            # الانتقال بين المراقب والمُبلّل، وفي نفس الوقت **مايحجبش** انتقالًا حقيقيًا
            # مختلفًا بنفس الحالة (ليه رقم عصر مختلف). الصفوف المعلّقة بس داخلة، والقديمة
            # (transition_seq=NULL) برّا. بيتعمل بعد ضمان الأعمدة عشان القواعد القديمة.
            self._conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_inbox_transition_seq_unique "
                "ON notification_inbox(conversation_id, transition_seq) "
                "WHERE transition_seq IS NOT NULL AND delivery_status='pending'"
            )
            # OHB2-08-05 (Batch 3R): فهرس التسليم المعلّق (جزئي، رخيص). بيتعمل بعد ضمان
            # العمود عشان القواعد القديمة ما تفشلش.
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_inbox_delivery_pending "
                "ON notification_inbox(delivery_status, id) "
                "WHERE delivery_status='pending'"
            )
            # تنظيف: `idx_inbox_created(id)` كان زائد (الـ PK فهرس بالفعل) وبيضاعف الكتابة
            # عند كل إدراج/تقليم. بنشيله لو موجود (فهرس بس — مفيش أي مساس بالبيانات).
            self._conn.execute("DROP INDEX IF EXISTS idx_inbox_created")

        # OHB2-MINIAPP: حالة الحذف البعيد على الشاهد (deleting ⇒ uncertain/confirmed).
        # أعمدة إضافية على قاعدة موجودة (غير مدمّر: الصفوف القديمة تاخد NULL).
        tomb_cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(deleted_conversations)")}
        if tomb_cols and "remote_state" not in tomb_cols:
            self._conn.execute("ALTER TABLE deleted_conversations ADD COLUMN remote_state TEXT")
        if tomb_cols and "remote_updated_at" not in tomb_cols:
            self._conn.execute("ALTER TABLE deleted_conversations ADD COLUMN remote_updated_at TEXT")
        # OHB2-PR6: هُوية الشاهد **متينة** (بدل مقارنة الطوابع الزمنية — TS-1).
        #   witness_origin     : NULL = شاهد قديم (حذف محلي سابق)، 'attempt' = محاولة حذف بعيد.
        #   witness_attempt_id : رمز المحاولة المالكة (للـ compare-and-swap).
        #   witness_preexisting: 1 = الصف كان موجودًا **قبل** أول محاولة بعيد (شاهد قديم)،
        #                        0 = الصف أنشأته المحاولة نفسها. عمود **تراكمي** (monotonic):
        #                        ما بيتصفّرش أبدًا، فلو محاولة **جديدة** ورثت شاهدًا قديمًا
        #                        بتبان شاهدًا قديمًا دايمًا (منع إعادة التصنيف غلط — TS-1).
        if tomb_cols and "witness_origin" not in tomb_cols:
            self._conn.execute("ALTER TABLE deleted_conversations ADD COLUMN witness_origin TEXT")
        if tomb_cols and "witness_attempt_id" not in tomb_cols:
            self._conn.execute(
                "ALTER TABLE deleted_conversations ADD COLUMN witness_attempt_id TEXT"
            )
        if tomb_cols and "witness_preexisting" not in tomb_cols:
            self._conn.execute(
                "ALTER TABLE deleted_conversations ADD COLUMN "
                "witness_preexisting INTEGER NOT NULL DEFAULT 0"
            )
            # ترحيل غير مدمّر ولا يعتمد على الوقت: أي شاهد قديم موجود **الآن** (قبل أن
            # يعرف الكود العمود الجديد) هو بالتعريف «سابق لأي محاولة» ⇒ نوسمه 1. هذا
            # idempotent (العمود يتضاف مرة واحدة فقط؛ لو أُضيف من قبل لا نلمس البيانات)
            # وآمن عند الانقطاع (ALTER + UPDATE داخل نفس معاملة `_migrate` الذرّية).
            self._conn.execute(
                "UPDATE deleted_conversations SET witness_preexisting=1 WHERE witness_origin IS NULL"
            )
        # OHB2-P0-A0: جدولا المرفقات (`attachment_batches`/`attachment_items`) جديدان
        # بالكامل ⇒ بيتعملوا في `_init_schema` بـ `CREATE TABLE IF NOT EXISTS` (نفس مسار
        # الإضافة غير المدمّر لكل الجداول الجديدة). القواعد القديمة بتاخد الجدولين تلقائيًا
        # عند أول `Database()` من غير أي مساس بالبيانات الموجودة.
        # OHB2-P0-A3/D-27: عمود `intent_text` يتضاف **إضافيًّا وغير مدمّر** لقواعد أُنشئت
        # قبل A3 (الصفوف القديمة بتاخد NULL = بلا نصّ مصاحب — fail-closed).
        batch_cols = {
            r["name"] for r in self._conn.execute("PRAGMA table_info(attachment_batches)")
        }
        if batch_cols and "intent_text" not in batch_cols:
            self._conn.execute(
                "ALTER TABLE attachment_batches ADD COLUMN intent_text TEXT"
            )

    # ------------------------------------------------- attachment batches (OHB2-P0-A0)
    def create_attachment_batch(
        self,
        batch_id: str,
        telegram_id: int,
        conversation_id: str,
        t0: str,
        status: str = ATTACHMENT_BATCH_PENDING,
        now: str | None = None,
    ) -> None:
        """OHB2-P0-A0: يسجّل صف دفعة مرفقات جديد (المخطّط فقط — بلا دورة حياة).

        `t0` ختم UTC المطلق لأول ملف ويُمرَّر **مرة واحدة**؛ الدالة ما بتحدّثهوش
        (منع تمديد المهلة — I6). `conversation_id` بيُمرَّر من المستدعي بعد التحقق منه
        بـ `files.is_valid_conversation_id` (نطاق A2/A3)؛ المخطّط نفسه ما بيفحصش.
        """
        stamp = now or datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO attachment_batches"
            "(batch_id, telegram_id, conversation_id, t0, status, created_at, updated_at) "
            "VALUES(?, ?, ?, ?, ?, ?, ?)",
            (batch_id, int(telegram_id), conversation_id, t0, status, stamp, stamp),
        )
        self._conn.commit()

    def get_attachment_batch(
        self, batch_id: str, *, telegram_id: int | None = None
    ) -> AttachmentBatch | None:
        """يجيب دفعة بالمعرّف، مع فرض **ملكية** الصف لو `telegram_id` اتحدّد.

        نطاق المالك (عزل بين المستخدمين — §5 بند 8): تمرير `telegram_id` بيخلي دفعة
        مستخدم تاني **مش مرئية**، وهو الأساس اللي A2/A3 يفرضوا بيه العزل.
        """
        if telegram_id is None:
            row = self._conn.execute(
                "SELECT * FROM attachment_batches WHERE batch_id=?", (batch_id,)
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT * FROM attachment_batches WHERE batch_id=? AND telegram_id=?",
                (batch_id, int(telegram_id)),
            ).fetchone()
        return self._row_to_attachment_batch(row) if row else None

    def add_attachment_item(
        self,
        item_id: str,
        batch_id: str,
        staging_token: str | None = None,
        display_name: str | None = None,
        size_bytes: int | None = None,
        status: str = ATTACHMENT_BATCH_PENDING,
        now: str | None = None,
    ) -> None:
        """OHB2-P0-A0: يسجّل صف عنصر واحد جوه دفعة (المخطّط فقط).

        الترتيب اللي بيستخدمه A1 **row-first**: العنصر يتسجّل قبل أي كتابة bytes؛
        `staging_token` مرجع غير شفّاف لبايتات الـ staging (مش اسم ملف المستخدم).
        """
        stamp = now or datetime.now(timezone.utc).isoformat()
        self._insert_attachment_item_nocommit(
            item_id, batch_id, staging_token, display_name, size_bytes, status, stamp
        )
        self._conn.commit()

    def _insert_attachment_item_nocommit(
        self,
        item_id: str,
        batch_id: str,
        staging_token: str | None,
        display_name: str | None,
        size_bytes: int | None,
        status: str,
        stamp: str,
    ) -> None:
        """إدراج صف عنصر **جوه معاملة المستدعي** (بدون commit). مصدر واحد للإدراج."""
        self._conn.execute(
            "INSERT INTO attachment_items"
            "(item_id, batch_id, staging_token, display_name, size_bytes, status, "
            "created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
            (
                item_id,
                batch_id,
                staging_token,
                display_name,
                None if size_bytes is None else int(size_bytes),
                status,
                stamp,
                stamp,
            ),
        )

    def list_attachment_items(self, batch_id: str) -> list[AttachmentItem]:
        """عناصر دفعة واحدة بترتيب إدراج مستقر (المخطّط فقط)."""
        rows = self._conn.execute(
            "SELECT * FROM attachment_items WHERE batch_id=? ORDER BY created_at, item_id",
            (batch_id,),
        ).fetchall()
        return [self._row_to_attachment_item(r) for r in rows]

    def set_attachment_item_status(
        self, item_id: str, status: str, *, size_bytes: int | None = None,
        staging_token: str | None = None,
    ) -> bool:
        """OHB2-P0-A1/A2: يحدّث حالة عنصر (`pending` ⇒ `stored`) اختياريًا مع الحجم/التوكن.

        يرجّع True لو صف واحد اتحدّث، وFalse لو العنصر مش موجود (المستدعي **ما يعلنش
        نجاح** على False — fail closed). مش بيمسّ `t0` (مفيش تمديد للمهلة). الاستعلامات
        ثابتة (بلا بناء نص) ⇒ مفيش مخاطر حقن.
        """
        stamp = datetime.now(timezone.utc).isoformat()
        if size_bytes is not None and staging_token is not None:
            cur = self._conn.execute(
                "UPDATE attachment_items SET status=?, size_bytes=?, staging_token=?, "
                "updated_at=? WHERE item_id=?",
                (status, int(size_bytes), staging_token, stamp, item_id),
            )
        elif size_bytes is not None:
            cur = self._conn.execute(
                "UPDATE attachment_items SET status=?, size_bytes=?, updated_at=? "
                "WHERE item_id=?",
                (status, int(size_bytes), stamp, item_id),
            )
        elif staging_token is not None:
            cur = self._conn.execute(
                "UPDATE attachment_items SET status=?, staging_token=?, updated_at=? "
                "WHERE item_id=?",
                (status, staging_token, stamp, item_id),
            )
        else:
            cur = self._conn.execute(
                "UPDATE attachment_items SET status=?, updated_at=? WHERE item_id=?",
                (status, stamp, item_id),
            )
        self._conn.commit()
        return cur.rowcount == 1

    # ---------------------------------------------- OHB2-P0-A2: دورة حياة الدفعة
    def latest_pending_attachment_batch(
        self, telegram_id: int, conversation_id: str
    ) -> AttachmentBatch | None:
        """أحدث دفعة `pending` لمستخدم+محادثة (أو None).

        A2: بتربط الملف الجديد بالدفعة القائمة **المؤهّلة** (نفس المستخدم والمحادثة،
        لسه `pending`). ترتيب `rowid` = أحدث دفعة اتسجّلت. الدفعات المنتهية/غير الـ
        `pending` ما بترجعش (المستدعي بيقرّر الإنهاء/الدفعة الجديدة).
        """
        row = self._conn.execute(
            "SELECT * FROM attachment_batches WHERE telegram_id=? AND conversation_id=? "
            "AND status=? ORDER BY rowid DESC LIMIT 1",
            (int(telegram_id), conversation_id, ATTACHMENT_BATCH_PENDING),
        ).fetchone()
        return self._row_to_attachment_batch(row) if row else None

    def mark_attachment_batch_status(self, batch_id: str, status: str, *, now: str) -> bool:
        """يحدّث حالة دفعة (مثلاً `pending` ⇒ `expired`). True لو صف واحد اتحدّث.

        **ما بيلمسش `t0`** (مفيش تمديد/تصفير للمهلة أبدًا — I6).
        """
        cur = self._conn.execute(
            "UPDATE attachment_batches SET status=?, updated_at=? WHERE batch_id=?",
            (status, now, batch_id),
        )
        self._conn.commit()
        return cur.rowcount == 1

    # ---------------------------------------------- OHB2-P0-A3: النية المحلية المتينة (D-27/D-29/D-30)
    def list_live_pending_attachment_batches(
        self, telegram_id: int, *, now_iso: str
    ) -> list[AttachmentBatch]:
        """كل الدفعات **الحيّة المعلّقة** للمستخدم عبر **كل** المحادثات (D-29).

        «حيّة» = `status=pending` و`T0 + 15د > now` (نفس `ATTACHMENT_BATCH_TTL`، بلا تمديد).
        الغرض: كشف **الغموض على مستوى المستخدم** (أكثر من دفعة حيّة ⇒ فشل مغلق)، وكشف دفعة
        حيّة **لمحادثة أخرى**. قراءة فقط؛ ما بتحوّلش ولا بتنهي أي دفعة (الإنهاء سلوك منفصل).
        `t0` غير صالح ⇒ الدفعة **مش حيّة** (fail-closed، نفس `batch_deadline`).
        """
        rows = self._conn.execute(
            "SELECT * FROM attachment_batches WHERE telegram_id=? AND status=? "
            "ORDER BY rowid DESC",
            (int(telegram_id), ATTACHMENT_BATCH_PENDING),
        ).fetchall()
        live: list[AttachmentBatch] = []
        for row in rows:
            batch = self._row_to_attachment_batch(row)
            deadline = _attachment_batch_deadline(batch.t0)
            if deadline is None or _parse_iso(now_iso) is None:
                continue  # ختم غير صالح ⇒ مش حيّة (fail-closed)
            if _parse_iso(now_iso) < deadline:
                live.append(batch)
        return live

    def has_expired_pending_attachment_batch(
        self, telegram_id: int, *, now_iso: str
    ) -> bool:
        """هل فيه دفعة `pending` **مش حيّة** (`T0 + 15د <= now`، أو `T0` غير صالح) للمستخدم؟

        يُستخدم لكشف نصّ قد يخصّ دفعة منتهية (D-29 بند 5: لا تحويل تلقائي إلى برومت عادي).
        **fail-closed:** دفعة معلّقة بـ`t0` غير صالح **مش حيّة** (نفس `list_live_...`) ⇒ بتُحسب
        «مش حيّة» هنا كمان، عشان النصّ مايتسرّبش لمسار البرومت العادي بسبب ختم تالف.
        قراءة فقط؛ ما بتحوّلش حالة أي دفعة (الوسم `expired` سلوك A4/مسارات أخرى).
        """
        rows = self._conn.execute(
            "SELECT t0 FROM attachment_batches WHERE telegram_id=? AND status=?",
            (int(telegram_id), ATTACHMENT_BATCH_PENDING),
        ).fetchall()
        if not rows:
            return False  # مفيش دفعة معلّقة أصلًا ⇒ مفيش رفض (المسار العادي كما هو)
        now_dt = _parse_iso(now_iso)
        if now_dt is None:
            # فيه دفعة معلّقة بس «الآن» غير صالح ⇒ ما نقدرش نثبت الحيوية ⇒ فشل مغلق.
            return True
        for row in rows:
            deadline = _attachment_batch_deadline(row["t0"])
            if deadline is None or now_dt >= deadline:
                return True
        return False

    def list_unresolved_attachment_batches(self, telegram_id: int) -> list[AttachmentBatch]:
        """كل الدفعات **غير المحسومة** للمستخدم عبر **كل** المحادثات (D-32/F1-1a).

        «غير محسومة» = حالة ضمن `ATTACHMENT_BATCH_UNRESOLVED_STATUSES`
        (`intent_recorded`/`dispatching`/`uncertain`): لسه فيها نيّة/إرسال معلّق ⇒ **تحجب**
        البرومت العادي (فشل مغلق)، حتى لو الدفعة تخصّ محادثة أخرى لنفس المستخدم.
        نطاق **المالك** إلزامي (`telegram_id`) ⇒ عزل بين المستخدمين. قراءة فقط.
        """
        rows = self._conn.execute(
            "SELECT * FROM attachment_batches WHERE telegram_id=? AND status IN "
            "('intent_recorded','dispatching','uncertain') ORDER BY rowid DESC",
            (int(telegram_id),),
        ).fetchall()
        return [self._row_to_attachment_batch(row) for row in rows]

    def has_terminal_attachment_batch(self, telegram_id: int) -> bool:
        """هل فيه أي دفعة **نهائية** (`delivered`/`expired`/`rejected`/`failed`) للمستخدم؟
        (D-32/F1-1a.)

        غرضها: تمييز «حالة نهائية» عن «مفيش أي دفعة» لأغراض التصنيف/التدقيق فقط — الدفعة
        النهائية **ما بتحجبش** برومتًا جديدًا بذاتها (D-32 بند 2)، والنتيجة السلوكية نفسها
        (`NONE`). نطاق **المالك** إلزامي (`telegram_id`) ⇒ عزل بين المستخدمين. قراءة فقط.
        """
        row = self._conn.execute(
            "SELECT 1 FROM attachment_batches WHERE telegram_id=? "
            "AND status IN ('delivered','expired','rejected','failed') LIMIT 1",
            (int(telegram_id),),
        ).fetchone()
        return row is not None

    def has_unknown_attachment_batch_status(self, telegram_id: int) -> bool:
        """هل فيه صفّ دفعة للمستخدم بحالة **خارج** `ATTACHMENT_BATCH_STATUSES` (أو NULL)؟

        F2 (fail-closed): الحالة المجهولة/التالفة **ممنوع** تُصنَّف `NONE` (اللي كان بيسمح
        بالسقوط الصامت لمسار البرومت/`outbox`). المقارنة في **بايثون** ضد
        `ATTACHMENT_BATCH_STATUSES` نفسها (مصدر واحد، بلا SQL مُركَّب) ⇒ مفيش انحراف، و`None`
        (لو حصل) بيُرفض ضمنًا لأنه مش عضو في المجموعة. عدد الدفعات لكل مستخدم صغير. نطاق
        **المالك** إلزامي. قراءة فقط.
        """
        rows = self._conn.execute(
            "SELECT DISTINCT status FROM attachment_batches WHERE telegram_id=?",
            (int(telegram_id),),
        ).fetchall()
        return any(row["status"] not in ATTACHMENT_BATCH_STATUSES for row in rows)

    # ---------------------------------------------- OHB2-P0-A4: كنس/انتهاء (قراءة + CAS)
    def list_expired_pending_attachment_batches(self, *, now_iso: str) -> list[AttachmentBatch]:
        """كل الدفعات `pending` اللي **فاتت مهلتها** (`T0 + 15د <= now`) عبر **كل** المستخدمين.

        مدخل كنس A4 (قراءة فقط). المهلة تُحسب من `t0` الأصلي **الثابت** (مفيش تمديد/تصفير —
        I4/I6). **fail-closed:** `t0` غير صالح أو «الآن» غير صالح ⇒ تُعتبر **منتهية** (نفس
        دلالة `list_live_pending_attachment_batches`/`has_expired_pending_attachment_batch`)
        عشان ما تفضلش دفعة بلا مهلة قابلة للحساب معلّقة للأبد.
        """
        rows = self._conn.execute(
            "SELECT * FROM attachment_batches WHERE status=? ORDER BY rowid",
            (ATTACHMENT_BATCH_PENDING,),
        ).fetchall()
        now_dt = _parse_iso(now_iso)
        expired: list[AttachmentBatch] = []
        for row in rows:
            batch = self._row_to_attachment_batch(row)
            deadline = _attachment_batch_deadline(batch.t0)
            if deadline is None or now_dt is None or now_dt >= deadline:
                expired.append(batch)
        return expired

    def list_attachment_batches_by_status(self, status: str) -> list[AttachmentBatch]:
        """كل الدفعات بحالة معيّنة عبر كل المستخدمين (قراءة فقط) — مدخل كنس A4 للنهائيات."""
        rows = self._conn.execute(
            "SELECT * FROM attachment_batches WHERE status=? ORDER BY rowid",
            (status,),
        ).fetchall()
        return [self._row_to_attachment_batch(r) for r in rows]

    def list_all_attachment_batches(self) -> list[AttachmentBatch]:
        """كل الدفعات (قراءة فقط) — لكشف الدلاء اليتيمة/العناصر بلا دفعة في A4."""
        rows = self._conn.execute(
            "SELECT * FROM attachment_batches ORDER BY rowid"
        ).fetchall()
        return [self._row_to_attachment_batch(r) for r in rows]

    def list_attachment_items_by_status(self, status: str) -> list[AttachmentItem]:
        """كل العناصر بحالة معيّنة (قراءة فقط) — لكشف/رصد كنس A4."""
        rows = self._conn.execute(
            "SELECT * FROM attachment_items WHERE status=? ORDER BY created_at, item_id",
            (status,),
        ).fetchall()
        return [self._row_to_attachment_item(r) for r in rows]

    def list_all_attachment_items(self) -> list[AttachmentItem]:
        """كل العناصر (قراءة فقط) — لبناء مجموعة التوكنات المرتبطة في A4 (تمييز اليتيم)."""
        rows = self._conn.execute(
            "SELECT * FROM attachment_items ORDER BY created_at, item_id"
        ).fetchall()
        return [self._row_to_attachment_item(r) for r in rows]

    def mark_attachment_item_reaped(self, item_id: str) -> bool:
        """OHB2-P0-A4/D-35: CAS العنصر من `pending`/`stored` ⇒ `reaped` (معاملة واحدة).

        يُنادى **فقط بعد** قرار نهائي/انتهاء مؤكَّد للدفعة (تسلسل DB-أولًا قبل حذف البايتات).
        True لو صف واحد اتحدّث. ما بيمسّش `attachment_message_identity` (دليل الهوية مستقل —
        D-35). عنصر مش موجود أو مش في الحالة المؤهّلة ⇒ False (المستدعي مايعلنش نجاح).
        """
        stamp = datetime.now(timezone.utc).isoformat()
        cur = self._conn.execute(
            "UPDATE attachment_items SET status=?, updated_at=? "
            "WHERE item_id=? AND status IN (?, ?)",
            (
                ATTACHMENT_ITEM_REAPED,
                stamp,
                item_id,
                ATTACHMENT_BATCH_PENDING,
                ATTACHMENT_ITEM_STORED,
            ),
        )
        self._conn.commit()
        return cur.rowcount == 1

    def count_attachment_batches(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM attachment_batches").fetchone()
        return int(row["n"]) if row else 0

    def count_attachment_items(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM attachment_items").fetchone()
        return int(row["n"]) if row else 0

    def classify_attachment_routing(
        self,
        telegram_id: int,
        *,
        now_iso: str,
        chat_id: int | None = None,
        message_id: int | None = None,
    ) -> AttachmentRouting:
        """تصنيف **صريح** لحالة المرفقات عند حدّ توجيه النصّ (A3 — D-32/F1-1a/F1-1b).

        **مصدر قرار واحد** يمنع الشروط المتفرّقة المتضاربة بين القاعدة والمعالج والاختبارات.
        نطاق كل الاستعلامات **بالمالك** (`telegram_id`) ⇒ عزل بين المستخدمين. الترتيب:

        1. **حالات غير محسومة** (`intent_recorded`/`dispatching`/`uncertain`) ⇒ `UNRESOLVED`
           (تحجب؛ حتى لو لمحادثة أخرى).
        2. **أكثر من دفعة `pending` حيّة** ⇒ `MULTI_LIVE` (غموض ⇒ فشل مغلق).
        3. **دفعة `pending` حيّة واحدة** ⇒ `LIVE` (مسار النصّ المصاحب؛ يبقى ربط route/الملكية
           والتحقّق النهائي للمعالج).
        4. **لا حيّة** لكن فيه دفعة `pending` **منتهية** ⇒ `EXPIRED_PENDING` (لا إحياء/لا تحويل).
        5. **لا حيّة ولا منتهية** لكن فيه دفعة **نهائية** ⇒ `TERMINAL` (لا تحجب برومتًا جديدًا).
        6. غير ذلك ⇒ `NONE` (مسار البرومت العادي كما هو).

        **F2 (fail-closed):** لو وُجد أي صفّ بحالة **خارج** `ATTACHMENT_BATCH_STATUSES`
        (أو NULL) ⇒ يرفع `AttachmentBatchIntegrityError` **قبل** أي تصنيف آخر. الحالة المجهولة
        ما بتتحوّلش أبدًا لـ`NONE` (منع السقوط الصامت لمسار البرومت/`outbox`).

        **fail-closed:** استعلام فرعي يفشل (قاعدة معطوبة) ⇒ يرفع الاستثناء للمستدعي (اللي
        بيسجّل فشلًا غير مؤهّل ويوقف). «الآن» غير صالح ⇒ الدفعة مش حيّة (نفس `list_live_...`).

        **D-34 (تعريف `NONE` الصريح — P-1):** `NONE` يُعاد **فقط** بعد تصنيف **ناجح ومكتمل
        ومقيَّد بالمالك** يُثبت أنّه **لا توجد أي حالة دفعة ذات صلة** تربط الرسالة الواردة بدفعة
        قائمة. `NONE` **لا يُعاد أبدًا** عند: وجود دفعة نهائية في نطاق المالك (`TERMINAL_*`)؛
        دفعة نهائية بلا دليل هوية؛ دفعة نهائية تاريخية غير مُثبَتة؛ دفعات متعدّدة تجعل الإسناد
        غامضًا (`MULTI_LIVE`)؛ فشل الاستعلام/نتائج ناقصة/سجلات تالفة (يرفع استثناء). **فقط**
        نتيجة `NONE` مُتحقَّق منها قد تدخل تصنيف البرومت العادي، ورَهينة بكل فحوص المالك/route/
        المحادثة المستقلة. الدفعات النهائية **تحجب** الآن (`TERMINAL_ASSOCIATED`/
        `TERMINAL_UNPROVEN`) بدل السقوط لمسار البرومت (D-34؛ ألغى سلوك D-32 بند 2 القديم
        «TERMINAL وNONE متطابقتان»).
        """
        # F2: فحص سلامة الحالات **أولًا** (fail-closed) — حالة مجهولة ⇒ رفض مغلق صريح.
        if self.has_unknown_attachment_batch_status(telegram_id):
            raise AttachmentBatchIntegrityError(
                "attachment batch with unknown/unsupported status for owner"
            )
        unresolved = self.list_unresolved_attachment_batches(telegram_id)
        if unresolved:
            return AttachmentRouting(
                AttachmentRoutingState.UNRESOLVED,
                unresolved_batches=tuple(unresolved),
            )
        live = self.list_live_pending_attachment_batches(telegram_id, now_iso=now_iso)
        if len(live) > 1:
            return AttachmentRouting(
                AttachmentRoutingState.MULTI_LIVE, live_batches=tuple(live)
            )
        if len(live) == 1:
            return AttachmentRouting(
                AttachmentRoutingState.LIVE, live_batches=(live[0],)
            )
        if self.has_expired_pending_attachment_batch(telegram_id, now_iso=now_iso):
            return AttachmentRouting(AttachmentRoutingState.EXPIRED_PENDING)
        if self.has_terminal_attachment_batch(telegram_id):
            # OHB2-P0-A3/D-34: دفعة نهائية في نطاق المالك ⇒ **فشل مغلق**. غياب دليل الهوية
            # **ليس** دليلًا على رسالة جديدة ⇒ `TERMINAL_UNPROVEN`. وجود دليل هوية ⇒ النصّ
            # **مُثبَت** الارتباط بدفعة نهائية ⇒ `TERMINAL_ASSOCIATED`. الحالتان **تحجبان**
            # (لا برومت عادي/لا `_send_prompt`/لا `outbox`)؛ الفرق دلالي (تتبّع/تدقيق).
            identity = (
                normalize_message_identity(telegram_id, chat_id, message_id)
                if chat_id is not None and message_id is not None
                else None
            )
            if identity is not None and self.message_identity_batch_id(*identity) is not None:
                return AttachmentRouting(AttachmentRoutingState.TERMINAL_ASSOCIATED)
            return AttachmentRouting(AttachmentRoutingState.TERMINAL_UNPROVEN)
        return AttachmentRouting(AttachmentRoutingState.NONE)

    def record_attachment_intent(
        self,
        batch_id: str,
        *,
        telegram_id: int,
        conversation_id: str,
        intent_text: str,
        now: str,
        update_id: int | None,
        chat_id: int | None = None,
        message_id: int | None = None,
    ) -> str | None:
        """OHB2-P0-A3/D-27: يكتب النصّ + الانتقال إلى `intent_recorded` + نتيجة التحديث ذرّيًّا.

        **معاملة واحدة** (`BEGIN IMMEDIATE`): إما الاتنين يتحفظوا أو ولا واحد. **بتعيد التحقّق
        جوّه المعاملة** من الملكية (`telegram_id`) والمحادثة بالضبط (`conversation_id`) والحالة
        (`pending`) والمهلة (`T0 + 15د > now`) — **مش** بتعتمد على قراءة سابقة (منع سباق
        الانتهاء/تغيير الملكية/الحالة). الشرط `status=pending` في الـ`UPDATE` هو حاجز الـCAS
        ضدّ **تسجيلين متزامنين** لنفس الدفعة: الثاني `rowcount=0` ⇒ `None`.

        ترجّع `batch_id` عند النجاح، أو `None` لما الدفعة **مش مؤهّلة** (مش موجودة/مش ملك
        المستخدم/محادثة مختلفة/مش `pending`/منتهية/سباق حالة). النصّ يُخزَّن **كما هو**
        (التطبيع/التحقّق مسؤولية المستدعي — `bot.attachment_text`).

        **مفيش إرسال بعيد ولا صفّ `outbox`** — نيّة محلية فقط (D-27). **مفيش ادّعاء
        exactly-once**؛ التحديث المكرّر (`update_id` مسجّل) بيتسجّل `duplicate_completed`
        ويترجّع `None` بلا أي كتابة (نفس نمط A2).
        """
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            if update_id is not None and self.update_is_processed(update_id):
                self._mark_processed_nocommit(
                    update_id, now, update_outcomes.DUPLICATE_COMPLETED
                )
                conn.commit()
                return None
            row = conn.execute(
                "SELECT * FROM attachment_batches WHERE batch_id=?", (batch_id,)
            ).fetchone()
            if row is None:
                conn.rollback()
                return None
            batch = self._row_to_attachment_batch(row)
            now_dt = _parse_iso(now)
            deadline = _attachment_batch_deadline(batch.t0)
            eligible = (
                batch.telegram_id == int(telegram_id)
                and batch.conversation_id == conversation_id
                and batch.status == ATTACHMENT_BATCH_PENDING
                and now_dt is not None
                and deadline is not None
                and now_dt < deadline
            )
            if not eligible:
                conn.rollback()
                return None
            cur = conn.execute(
                "UPDATE attachment_batches SET status=?, intent_text=?, updated_at=? "
                "WHERE batch_id=? AND status=?",
                (ATTACHMENT_BATCH_INTENT_RECORDED, intent_text, now, batch_id,
                 ATTACHMENT_BATCH_PENDING),
            )
            if cur.rowcount != 1:
                conn.rollback()
                return None
            # OHB2-P0-A3/D-33/D-35: دليل الهوية يُكتب **داخل نفس المعاملة** (ذرّي مع النيّة).
            # الهوية غير صالحة (غياب/سوء شكل) ⇒ **فشل مغلق**: نتراجع بلا نيّة (المعالج يسجّل
            # فشلًا غير مؤهّل) — لا نكتب نيّة بلا دليل هوية. قيد الـPK يمنع إعادة الربط؛ تعارض
            # ⇒ `IntegrityError` ⇒ rollback (fail-closed).
            identity = (
                normalize_message_identity(telegram_id, chat_id, message_id)
                if chat_id is not None and message_id is not None
                else None
            )
            if identity is None:
                conn.rollback()
                return None
            conn.execute(
                "INSERT INTO attachment_message_identity "
                "(telegram_id, chat_id, message_id, batch_id, conversation_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (identity[0], identity[1], identity[2], batch_id, conversation_id, now),
            )
            self._mark_processed_nocommit(
                update_id, now, update_outcomes.DURABLE_INTENT_RECORDED
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return batch_id

    def message_identity_batch_id(
        self, telegram_id: int, chat_id: int, message_id: int
    ) -> str | None:
        """OHB2-P0-A3/D-33: دفعة مرتبطة بهوية رسالة، أو `None` لو مفيش دليل هوية.

        قراءة فقط. **`None` تعني «لا دليل» لا «رسالة جديدة»** (D-34 بند 6): المعالج يعاملها
        كـ`TERMINAL_UNPROVEN` (فشل مغلق) عند وجود دفعة نهائية، لا كبرومت عادي.
        """
        row = self._conn.execute(
            "SELECT batch_id FROM attachment_message_identity "
            "WHERE telegram_id=? AND chat_id=? AND message_id=?",
            (int(telegram_id), int(chat_id), int(message_id)),
        ).fetchone()
        return row["batch_id"] if row is not None else None

    def count_message_identities(self) -> int:
        """عدد صفوف دليل هوية الرسالة (للاختبارات/المراقبة)."""
        return int(
            self._conn.execute(
                "SELECT COUNT(*) FROM attachment_message_identity"
            ).fetchone()[0]
        )

    def record_rejected_ineligible(
        self, *, now: str, update_id: int | None, reason: str | None = None
    ) -> bool:
        """OHB2-P0-A3/D-30: نتيجة رفض نهائية متينة `rejected_ineligible` (مؤهّلة للإقرار).

        قرار **دائم** مسجَّل في `processed_updates.outcome` (معاملة واحدة) ⇒ حدّ الإقرار يقدر
        يتقدّم (مفيش إعادة معالجة لاحقة). **مفيش** كتابة دفعة/`outbox`/إرسال. ترجّع True لو
        اتحفظت، أو False لو مفيش `update_id` صالح (fail-closed: مفيش نتيجة ⇒ غير مؤهّل).

        **حدّ مهم:** ده للحالات **النهائية المؤهّلة** (نصّ غير مؤهّل/غموض/دفعة منتهية). الأعطال
        **التقنية** (فشل قاعدة/تفويض/نتيجة غامضة) **ما بتمرّش** من هنا — بتتسجّل `failed_*`/
        `partial_or_unknown` (غير مؤهّلة) عبر `record_update_failure` (D-30/D-09-R2 fail-closed).
        """
        if update_id is None:
            return False
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            self.mark_update_outcome(
                update_id, now, update_outcomes.REJECTED_INELIGIBLE,
                reason=reason, commit=False,
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return True

    def get_attachment_item(
        self, item_id: str, *, batch_id: str | None = None
    ) -> AttachmentItem | None:
        """عنصر بالمعرّف، مع فرض **انتماء الدفعة** لو `batch_id` اتحدّد.

        A1-REV-F3/عزل: تمرير `batch_id` بيمنع تحديث/قراءة عنصر دفعة تانية.
        """
        if batch_id is None:
            row = self._conn.execute(
                "SELECT * FROM attachment_items WHERE item_id=?", (item_id,)
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT * FROM attachment_items WHERE item_id=? AND batch_id=?",
                (item_id, batch_id),
            ).fetchone()
        return self._row_to_attachment_item(row) if row else None

    def accept_attachment_item(
        self,
        batch: AttachmentBatch,
        *,
        item_id: str,
        display_name: str | None,
        now: str,
        update_id: int | None = None,
        staging_token: str | None = None,
    ) -> str | None:
        """OHB2-P0-A2: كتابة **النية الدائمة** للقبول + نتيجة التحديث **في معاملة واحدة**.

        بيسجّل صف عنصر `pending` (مرجع العنصر اللي A1 هيكتب بايتاته بعدين — row-first)
        ونتيجة التحديث `durable_intent_recorded` **ذرّيًا**: إما الاتنين يتحفظوا أو ولا
        واحد. ده اللي بيمنع «نجاح كاذب» (قبول من غير دليل دائم) أو «حجب الحدّ للأبد»
        (دليل بلا نتيجة). **مفيش ادّعاء exactly-once**: `update_id` مكرّر (نفس الدفعة أو
        دفعة جديدة) بيتسجّل بـ `duplicate_completed` (دليل دائم، بلا ازدواج).

        **شرط مسبق:** المستدعي (A2) لسه متأكّد إن `batch` دفعة `pending` صالحة لنفس
        المستخدم والمحادثة (وإلا مايناديش). الكتابة هنا **مش** بتعيد التحقّق من صلاحية
        الدفعة (تجنّب قراءة-ثم-كتابة عبر `await`؛ العمليات تُسلسَل في العملية الواحدة).

        بترجّع معرّف الدفعة الفعلي اللي العنصر اتسجّل فيه (للـ evidence)، أو **`None`**
        لما التحديث يكون **مكرّرًا** (`update_id` مسجّل قبل كده) ⇒ مفيش عنصر جديد
        اتكتب (F-4). المستدعي **ما يصنعش** معرّف عنصر ولا يفترض قبولًا جديدًا.
        """
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            if update_id is not None and self.update_is_processed(update_id):
                self._mark_processed_nocommit(
                    update_id, now, update_outcomes.DUPLICATE_COMPLETED
                )
                conn.commit()
                return None
            self._insert_attachment_item_nocommit(
                item_id, batch.batch_id, staging_token, display_name, None,
                ATTACHMENT_BATCH_PENDING, now,
            )
            self._mark_processed_nocommit(
                update_id, now, update_outcomes.DURABLE_INTENT_RECORDED
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return batch.batch_id

    def accept_attachment_item_into_new_batch(
        self,
        *,
        telegram_id: int,
        conversation_id: str,
        batch_id: str,
        item_id: str,
        t0: str,
        display_name: str | None,
        now: str,
        update_id: int | None = None,
        staging_token: str | None = None,
    ) -> str | None:
        """OHB2-P0-A2: إنشاء دفعة جديدة + عنصرها + نتيجة التحديث **في معاملة واحدة**.

        دفعة جديدة بتتولّد لما مفيش دفعة `pending` مؤهّلة (أول ملف، أو بعد انتهاء دفعة
        سابقة). `T0 = t0` **يتحطّ مرة واحدة** عند أول ملف (عمره ما بيتمدّد — I6).

        بترجّع معرّف الدفعة الجديدة، أو **`None`** لما التحديث يكون **مكرّرًا**
        (`update_id` مسجّل قبل كده) ⇒ **مافيش** دفعة ولا عنصر جديد اتعملوا (F-4).
        """
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            if update_id is not None and self.update_is_processed(update_id):
                self._mark_processed_nocommit(
                    update_id, now, update_outcomes.DUPLICATE_COMPLETED
                )
                conn.commit()
                return None
            conn.execute(
                "INSERT INTO attachment_batches"
                "(batch_id, telegram_id, conversation_id, t0, status, created_at, updated_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?)",
                (
                    batch_id, int(telegram_id), conversation_id, t0,
                    ATTACHMENT_BATCH_PENDING, now, now,
                ),
            )
            self._insert_attachment_item_nocommit(
                item_id, batch_id, staging_token, display_name, None,
                ATTACHMENT_BATCH_PENDING, now,
            )
            self._mark_processed_nocommit(
                update_id, now, update_outcomes.DURABLE_INTENT_RECORDED
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return batch_id

    @staticmethod
    def _row_to_attachment_batch(row: sqlite3.Row) -> AttachmentBatch:
        return AttachmentBatch(
            batch_id=row["batch_id"],
            telegram_id=row["telegram_id"],
            conversation_id=row["conversation_id"],
            t0=row["t0"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            intent_text=row["intent_text"],
        )

    @staticmethod
    def _row_to_attachment_item(row: sqlite3.Row) -> AttachmentItem:
        return AttachmentItem(
            item_id=row["item_id"],
            batch_id=row["batch_id"],
            staging_token=row["staging_token"],
            display_name=row["display_name"],
            size_bytes=row["size_bytes"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # ----------------------------------------------------------------- watched
    def add_watched(
        self, conversation_id: str, title: str = "", chat_id: int | None = None,
        *, new_lifecycle: bool = True, reengage: bool = False,
    ) -> None:
        # TASK 54: إضافة/تحديث المتابعة = بداية دورة إشعار جديدة ⇒ نصفّر عدّاد المحاولات
        # عشان الإشعار الجديد ياخد ميزانية كاملة (مش ميزانية محاولات إشعار قديم).
        # NTF-19: `new_lifecycle=True` (الافتراضي) = دورة متابعة جديدة ⇒ معرّف جديد
        # (`watch_seq`)، فمتابعة جديدة ما تتأثّرش بتلميح in-memory قديم.
        # NTF-20: لو فيه علامة تسليم معلّق **دائمة** (تسليم ممكن تيليجرام يكون قبله بالفعل
        # بس تسجيله الدائم لسه معلّق)، ما نمسحهاش ونرميها — بنسجّلها (`notified_status=الحالة`)
        # وبنمسح العلامة **في نفس المعاملة**، قبل ما نعمل الدورة الجديدة. كده الدليل ما
        # يتفقدش (مفيش إشعار مكرّر من المُبلّغ) والدورة الجديدة تبدأ نظيفة. لو التسجيل فشل،
        # المعاملة كلها بترجع والعلامة تفضل ⇒ إعادة محاولة آمنة (مفيش حذف صامت).
        # `new_lifecycle=False` = إعادة نداء مكرّرة لنفس المتابعة (double-tap/إعادة محاولة):
        # بنحدّث العنوان/الشات بس، وبنحافظ على المعرّف والعلامة المعلّقة وعدّاد المحاولات.
        now = datetime.now(timezone.utc).isoformat()
        # NTF-20: قبل بدء دورة جديدة، ننسّق أي تلميح in-memory للتسليم المعلّق (لو المراقب
        # سجّل الـ hook). ده بيمنع فقد دليل تسليم اتّبعت فعلاً لما الـ handlers/outbox
        # يبدأوا دورة جديدة من غير ما يعرفوا المراقب.
        if new_lifecycle and self.on_new_watch_lifecycle is not None:
            self.on_new_watch_lifecycle(conversation_id)
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            # OHB2-C7 (RESURRECTION-FIX): منع الإحياء. لو الشات عليه شاهد حذف دائم، أي
            # مسار إنشاء/تحديث متابعة (worker/outbox/استرجاع) بيترفض — إلا لو المستخدم
            # أعاد التفاعل صريح (`reengage=True`، من مسار watch/prompt) فبنشيل الشاهد
            # ونكمل دورة نظيفة. الفحص جوه BEGIN IMMEDIATE ⇒ محصّن ضد حذف متزامن.
            if self.is_deleted(conversation_id):
                if not reengage:
                    conn.rollback()
                    return
                self._clear_tombstone_nocommit(conversation_id)
            if new_lifecycle:
                row = conn.execute(
                    "SELECT pending_delivery_state FROM watched WHERE conversation_id=?",
                    (conversation_id,),
                ).fetchone()
                if row is not None and row["pending_delivery_state"]:
                    # تسجيل التسليم القديم قبل بدء الدورة الجديدة (نفس المعاملة).
                    self._mark_pending_delivered(
                        conversation_id, row["pending_delivery_state"], now
                    )
                conn.execute(
                    "INSERT INTO watched"
                    "(conversation_id, title, chat_id, added_at, retry_count, watch_seq) "
                    "VALUES(?, ?, ?, ?, 0, lower(hex(randomblob(16)))) "
                    "ON CONFLICT(conversation_id) DO UPDATE SET title=excluded.title, "
                    "chat_id=COALESCE(excluded.chat_id, watched.chat_id), "
                    "added_at=COALESCE(watched.added_at, excluded.added_at), "
                    "retry_count=0, pending_delivery_state=NULL, "
                    "watch_seq=lower(hex(randomblob(16)))",
                    (conversation_id, title, chat_id, now),
                )
            else:
                conn.execute(
                    "INSERT INTO watched"
                    "(conversation_id, title, chat_id, added_at, retry_count, watch_seq) "
                    "VALUES(?, ?, ?, ?, 0, lower(hex(randomblob(16)))) "
                    "ON CONFLICT(conversation_id) DO UPDATE SET title=excluded.title, "
                    "chat_id=COALESCE(excluded.chat_id, watched.chat_id)",
                    (conversation_id, title, chat_id, now),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _mark_pending_delivered(self, conversation_id: str, status: str, now: str) -> None:
        """NTF-20: يسجّل حالة تسليم معلّقة (`notified_status`) **داخل معاملة المستدعي**
        بدون commit مستقل — يُستخدم لتسوية التسليم قبل بدء دورة متابعة جديدة."""
        self.record_notification_sent(conversation_id, status, now, _commit=False)

    def reconcile_pending_delivery(self, conversation_id: str) -> str | None:
        """NTF-20: يسوّي أي علامة تسليم معلّق **دائمة** قبل بدء دورة متابعة جديدة.

        بيرجّع الحالة اللي اتسجّلت (أو None لو مفيش علامة معلّقة). التسجيل والمسح في
        معاملة واحدة (`BEGIN IMMEDIATE`): لو التسجيل فشل، العلامة تفضل ⇒ إعادة محاولة
        آمنة. كتابة ضيّقة (عمود واحد + `notification_state`)، ما بتلمسش `watch_seq` ولا
        دورة المتابعة. المراقب بيستخدمها عشان ينسّق الدورة الجديدة مع التلميح in-memory.
        """
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT pending_delivery_state FROM watched WHERE conversation_id=?",
                (conversation_id,),
            ).fetchone()
            if row is None or not row["pending_delivery_state"]:
                conn.commit()
                return None
            status = row["pending_delivery_state"]
            self._mark_pending_delivered(
                conversation_id, status, datetime.now(timezone.utc).isoformat()
            )
            conn.execute(
                "UPDATE watched SET pending_delivery_state=NULL WHERE conversation_id=?",
                (conversation_id,),
            )
            conn.commit()
            return status
        except Exception:
            conn.rollback()
            raise

    def set_pending_delivery(self, conversation_id: str, state: str) -> None:
        """NTF-13: علامة write-ahead — تسليم انتهاء اتّبعت (اتقبل) لكن لسه ماتسجّلش دائمًا.

        بتتكتب **بعد** نجاح الإرسال و**قبل** التسجيل الدائم. بتستخدمها إزالة المتابعة
        لإكمال التسجيل من أي مسار، والمراقب للاسترجاع بعد إعادة التشغيل. كتابة ضيّقة
        (عمود واحد) عشان مايتدهسش باقي الأعمدة.
        """
        self._conn.execute(
            "UPDATE watched SET pending_delivery_state=? WHERE conversation_id=?",
            (state, conversation_id),
        )
        self._conn.commit()

    def clear_pending_delivery(self, conversation_id: str) -> None:
        """NTF-13: يمسح علامة التسليم المعلّق (بعد نجاح التسجيل الدائم)."""
        self._conn.execute(
            "UPDATE watched SET pending_delivery_state=NULL WHERE conversation_id=?",
            (conversation_id,),
        )
        self._conn.commit()

    def mark_submitted(self, conversation_id: str, submitted_at: str) -> None:
        """يسجّل وقت إرسال آخر برومبت للشات (بيتحدّث مع كل برومبت جديد)."""
        self._conn.execute(
            "UPDATE watched SET submitted_at=? WHERE conversation_id=?",
            (submitted_at, conversation_id),
        )
        self._conn.commit()

    def remove_watched(self, conversation_id: str) -> None:
        """يشيل المتابعة، ويكمّل تسجيل أي تسليم معلّق — في معاملة ذرّية واحدة (NTF-15).

        لو فيه علامة تسليم معلّق (اتّبعت لتليجرام بس تسجيله الدائم فشل)، بنسجّلها في
        `notification_state` **قبل** حذف الصف، والاتنين في معاملة واحدة (`BEGIN IMMEDIATE`
        + commit/rollback). كده لو التسجيل فشل، الحذف ما بيحصلش (مفيش ازدواج صامت)،
        والاستثناء بيطلع للمستدعي. لو مفيش صف أصلاً، الحذف بيكمل عادي (سلوك متسق).

        OHB2-08-03: قبل أي كتابة، بننسّق دليل التسليم in-memory عبر `on_unwatch` (لو
        المراقب سجّله) — يثبّت أي تلميح مطابق كعلامة دائمة جوه نفس المعاملة، فالـ fallback
        (لما المراقب مش متاح) ما يفقدش دليل تسليم اتّبعت فعلًا ⇒ مفيش إشعار مكرّر.
        """
        if self.on_unwatch is not None:
            self.on_unwatch(conversation_id)
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT pending_delivery_state FROM watched WHERE conversation_id=?",
                (conversation_id,),
            ).fetchone()
            pending = row["pending_delivery_state"] if row else None
            if pending:
                # كتابة ضيّقة جوه نفس المعاملة (مفيش commit مستقل)، عشان التسجيل والحذف
                # ينجحوا أو يفشلوا مع بعض.
                self.record_notification_sent(
                    conversation_id, pending, datetime.now(timezone.utc).isoformat(),
                    _commit=False,
                )
            conn.execute("DELETE FROM watched WHERE conversation_id=?", (conversation_id,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def remove_watched_completing(
        self, conversation_id: str, pending_status: str, now: str | None = None
    ) -> bool:
        """يزيل المتابعة ويكمّل تسليمًا معلّقًا **معروفًا للمستدعي** في معاملة واحدة (NTF-17).

        زي `remove_watched` بس الحالة المعلّقة بتيجي من المستدعي (الحالة اللي اتّبعت فعلًا
        لما كتابة العلامة الدائمة نفسها فشلت). العلامة الدائمة، لو موجودة، بتاخد الأولوية
        على القيمة المارّرة. بيرجّع True لو كان فيه صف واتشال، وFalse لو مفيش صف (no-op).
        بيرمي لو التسجيل فشل (مفيش حذف جزئي — الذرّية محفوظة).

        OHB2-08-03: بننسّق دليل in-memory عبر `on_unwatch` قبل أي كتابة (زي `remove_watched`).
        """
        if self.on_unwatch is not None:
            self.on_unwatch(conversation_id)
        now = now or datetime.now(timezone.utc).isoformat()
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT pending_delivery_state FROM watched WHERE conversation_id=?",
                (conversation_id,),
            ).fetchone()
            if row is None:
                conn.commit()
                return False
            status = row["pending_delivery_state"] or pending_status
            self.record_notification_sent(conversation_id, status, now, _commit=False)
            conn.execute("DELETE FROM watched WHERE conversation_id=?", (conversation_id,))
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise

    def remove_watched_if_seq(self, conversation_id: str, expected_watch_seq: str) -> bool:
        """NTF-23: إزالة ذرّية **مشروطة** بمعرّف دورة المتابعة (compare-and-swap).

        بتحذف الصف بس لو `watch_seq` لسه مطابق للمعرّف الملتقَط (`expected_watch_seq`)،
        وبتكمّل أي تسليم معلّق في نفس المعاملة. بتمنع سباق الإزالة من لقطة قديمة (NTF-22
        M-1): لو دورة جديدة اتعملت أثناء `await` الشبكة، الـ `DELETE ... AND watch_seq=?`
        بيفشل (صفري) فالدورة الجديدة تفضل سليمة.

        القرار كله في جملة `DELETE` ذرّية واحدة (مفيش SELECT ثم DELETE). لو الدورة اتغيّرت
        (أو الصف مش موجود)، بنرجّع False **بدون أي أثر** — مفيش لمس للعلامة المعلّقة ولا
        `notification_state` (ما نكمّلش/نمسحش دليل دورة تانية).

        بيرجّع True لو الصف المطابق اتشال، وFalse لو الصف مش موجود أو الدورة اتغيّرت.
        بيرمي لو التسجيل فشل (المعاملة كلها بترجع، والصف بيفضل — retry آمن).

        OHB2-08-03: بننسّق دليل in-memory عبر `on_unwatch` قبل أي كتابة. الـ hook مربوط
        بمعرّف دورة المتابعة، فلو الدورة اتغيّرت (الصف مش هيتشال) التلميح المطابق للدورة
        الحالية بيتثبّت كعلامة دائمة — إصلاح تلقائي غير ضار (الدليل مضمون بغض النظر عن
        نتيجة الـ CAS).
        """
        if self.on_unwatch is not None:
            self.on_unwatch(conversation_id)
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT pending_delivery_state FROM watched "
                "WHERE conversation_id=? AND watch_seq=?",
                (conversation_id, expected_watch_seq),
            ).fetchone()
            if row is None:
                conn.commit()
                return False  # الصف مش موجود أو الدورة اتغيّرت ⇒ مفيش أثر
            pending = row["pending_delivery_state"]
            cur = conn.execute(
                "DELETE FROM watched WHERE conversation_id=? AND watch_seq=?",
                (conversation_id, expected_watch_seq),
            )
            if cur.rowcount == 0:
                conn.rollback()
                return False  # اتغيّر بين الـ SELECT والـ DELETE ⇒ مفيش أثر
            if pending:
                # التسجيل جوه نفس المعاملة، **بعد** تثبيت الحذف المطابق (مفيش commit مستقل).
                self.record_notification_sent(
                    conversation_id, pending, datetime.now(timezone.utc).isoformat(),
                    _commit=False,
                )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise

    # ------------------------------------------- deletion tombstone (OHB2-C7)
    def is_deleted(self, conversation_id: str) -> bool:
        """هل الشات عليه شاهد حذف دائم؟ (بيستخدمه كل مسار إعادة إنشاء/إحياء)."""
        row = self._conn.execute(
            "SELECT 1 FROM deleted_conversations WHERE conversation_id=?",
            (conversation_id,),
        ).fetchone()
        return row is not None

    def is_deleted_with_retry(self, conversation_id: str) -> bool:
        """قراءة شاهد الحذف مع إعادة محاولة **محدودة** للفشل العابر بس (OHB2-SW03).

        سياسة مشتركة (البوت + الـ Mini App): محاولة أولى + حتى 3 إعادات بمُدد
        `DEDUPE_RETRY_DELAYS` (0.25/0.5/1.0ث) **للفشل العابر** (SQLite BUSY/LOCKED) بس.
        الفشل الدائم يُرفع فورًا بلا إعادة، وبعد استنفاد الميزانية بنرفع **الاستثناء الأصلي**.
        ممنوع نرجّع `False` (أو أي نتيجة تشبه النجاح) عند فشل القراءة — القراءة الناجحة بس
        هي اللي بتحدّد «متشاهد» من «مش متشاهد» (مفيش فشل يُلبَس لبوس الفراغ).
        """
        attempt = 0
        while True:
            try:
                return self.is_deleted(conversation_id)
            except Exception as exc:  # noqa: BLE001 — التصنيف بيقرّر: عابر يُعاد، دائم يُرفع
                if not is_transient_sqlite_error(exc) or attempt >= len(DEDUPE_RETRY_DELAYS):
                    raise
                delay = DEDUPE_RETRY_DELAYS[attempt]
                attempt += 1
                log.warning(
                    "فحص شاهد الحذف (%s): فشل SQLite عابر (%s) — إعادة محاولة %d/%d بعد %.2fث",
                    conversation_id, type(exc).__name__, attempt, len(DEDUPE_RETRY_DELAYS), delay,
                )
                time.sleep(delay)

    def _tombstone_nocommit(self, conversation_id: str, now: str) -> None:
        """يسجّل شاهد الحذف **داخل معاملة المستدعي** (idempotent: أول مرة بس تحفظ وقت الحذف)."""
        self._conn.execute(
            "INSERT OR IGNORE INTO deleted_conversations(conversation_id, deleted_at) "
            "VALUES(?, ?)",
            (conversation_id, now),
        )

    # --------------------------------- remote deletion state (OHB2-MINIAPP)
    # القيم: None (مفيش حذف بعيد) ⇒ 'deleting' (اتطلب حذف بعيد، النتيجة لسه مجهولة)
    # ⇒ 'uncertain' (فشل/انقطاع — محتاج إعادة محاولة/تسوية) أو 'confirmed' (OpenHands أكّد).
    REMOTE_DELETING = "deleting"
    REMOTE_UNCERTAIN = "uncertain"
    REMOTE_CONFIRMED = "confirmed"

    # OHB2-PR6: هُوية الشاهد المتينة. بدل تمييز «قديم/جديد» بمقارنة الطوابع الزمنية
    # (`deleted_at != remote_updated_at` — عرضة لدقّة الساعة/رجوعها/التطبيع — TS-1)،
    # بنعتمد على أعمدة صريحة:
    #   witness_origin      = 'attempt' لشاهد أنشأته محاولة بعيد، NULL لشاهد قديم.
    #   witness_attempt_id  = رمز المحاولة المالكة (compare-and-swap بين المحاولات).
    #   witness_preexisting = 1 لو الصف كان موجودًا قبل أول محاولة بعيد (شاهد قديم)،
    #                         وبيبقى 1 للأبد (monotonic) ⇒ مايتغيّرش مع إعادات المحاولة.
    # التصنيف ما بيعتمدش على الوقت إطلاقًا ⇒ TS-1 مُلغى.
    WITNESS_ORIGIN_ATTEMPT = "attempt"

    def _begin_attempt_nocommit(self, conversation_id: str, now: str, attempt_id: str) -> bool:
        """يوسم محاولة حذف بعيد **داخل معاملة المستدعي**: شاهد + 'deleting' + هُوية المحاولة.

        `witness_preexisting` بيتحدّد **مرة واحدة** عند أول محاولة على الصف، وبعدها بيتغيّرش
        (monotonic): 1 لو الصف كان موجودًا قبل أول محاولة (شاهد قديم)، و0 لو أول محاولة هي اللي
        أنشأته. إعادات المحاولة اللاحقة **ما بتغيّرش** القيمة (لو `witness_origin` قديم =
        'attempt' يبقى عندنا محاولة سابقة ⇒ نحافظ) ⇒ محاولة جديدة على صف أنشأته بنفسها تفضل
        «جديدة»، ومحاولة على شاهد قديم تفضل «قديمة». التصنيف ما بيعتمدش على الوقت إطلاقًا.

        **حراسة الإنهاء (CAS):** مش بنوسم 'deleting' على شات حالته 'confirmed' — إثبات الحذف
        نهائي وما يتلغيش بمحاولة لاحقة. بيرجّع True لو خدنا الملكية، False لو الشات مؤكّد
        مسبقًا (المستدعي يعالجها كحذف مكتمل).
        """
        existed = self._conn.execute(
            "SELECT 1 FROM deleted_conversations WHERE conversation_id=?",
            (conversation_id,),
        ).fetchone() is not None
        self._tombstone_nocommit(conversation_id, now)
        cur = self._conn.execute(
            "UPDATE deleted_conversations SET remote_state=?, remote_updated_at=?, "
            "witness_origin=?, witness_attempt_id=?, "
            "witness_preexisting=CASE "
            "  WHEN witness_origin=? THEN witness_preexisting "  # محاولة سابقة ⇒ نحافظ
            "  WHEN ? THEN 1 ELSE witness_preexisting END "       # أول محاولة على صف موجود ⇒ قديم
            "WHERE conversation_id=? AND (remote_state IS NULL OR remote_state != ?)",
            (
                self.REMOTE_DELETING, now, self.WITNESS_ORIGIN_ATTEMPT, attempt_id,
                self.WITNESS_ORIGIN_ATTEMPT, 1 if existed else 0, conversation_id,
                self.REMOTE_CONFIRMED,
            ),
        )
        return cur.rowcount == 1

    def begin_remote_deletion(self, conversation_id: str, now: str) -> str | None:
        """يوسم الحذف الجاري (شاهد + 'deleting' + هُوية محاولة) في معاملة ذرّية **قبل** النداء.

        يرجّع `attempt_id` الفريد للمحاولة دي (يُستخدم في الـ compare-and-swap بعد النداء)،
        أو None لو الشات **مؤكّد الحذف مسبقًا** (في الحالة دي ما بناخدش ملكية — إثبات الحذف
        نهائي). لو العملية اتقطعت بعد كده، الحالة تفضل (تنجو من restart) فأي إعادة محاولة/
        تسوية تعرف إن فيه حذف بعيد معلّق، ومايتحياش الشات في الوقت نفسه.
        """
        attempt_id = uuid.uuid4().hex
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            took = self._begin_attempt_nocommit(conversation_id, now, attempt_id)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return attempt_id if took else None

    def _set_remote_state_nocommit(self, conversation_id: str, state: str | None, now: str) -> None:
        """يثبّت حالة الحذف البعيد **داخل معاملة المستدعي** (كتابة غير مشروطة)."""
        self._conn.execute(
            "UPDATE deleted_conversations SET remote_state=?, remote_updated_at=? "
            "WHERE conversation_id=?",
            (state, now, conversation_id),
        )

    def set_remote_deletion_state(self, conversation_id: str, state: str | None, now: str) -> None:
        """يثبّت حالة الحذف البعيد ('deleting'/'uncertain'/'confirmed' أو NULL) — كتابة دائمة.

        كتابة غير مشروطة: تُستخدم في مسارات **ملكية المحاولة** (التسوية) اللي بتتأكد من
        ملكية الشاهد بـ CAS على `witness_attempt_id` قبلها. مش مسار «تصفير بيانات محاولة».
        """
        self._set_remote_state_nocommit(conversation_id, state, now)
        self._conn.commit()

    def revert_remote_deletion_cas(
        self, conversation_id: str, attempt_id: str | None, state: str | None, now: str | None
    ) -> bool:
        """compare-and-swap: يرجّع بيانات الحذف البعيد لحالتها السابقة **بس** لو المحاولة دي
        ما زالت مالكة الشاهد (`witness_attempt_id IS attempt_id`) **والحالة ليست 'confirmed'**.

        `IS ?` (مش `= ?`) مقصود: مالك الشاهد القديم بعد الترحيل `NULL`، و`= NULL` ما بتطابقش
        أبدًا فكانت تسيب الصفوف القديمة المعلّقة عالقة للأبد.

        حرس الإنهاء: `'confirmed'` حالة **نهائية** (إثبات حذف بعيد بدليل إيجابي) ⇒ ممنوع أي
        CAS يرجّعها/يطمسها. يرجّع True لو النجح (احنا المالك)، False لو محاولة أحدث سبقتنا أو
        الحالة مؤكّدة (ما بنلمسش — منع lost-update). الكتابة ذرّية داخل `BEGIN IMMEDIATE`.
        """
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            cur = conn.execute(
                "UPDATE deleted_conversations SET remote_state=?, remote_updated_at=? "
                "WHERE conversation_id=? AND witness_attempt_id IS ? AND remote_state != ?",
                (state, now, conversation_id, attempt_id, self.REMOTE_CONFIRMED),
            )
            ok = cur.rowcount == 1
            conn.commit()
            return ok
        except Exception:
            conn.rollback()
            raise

    def clear_witness_cas(self, conversation_id: str, attempt_id: str | None) -> bool:
        """compare-and-swap: يشيل صف الشاهد **بس** لو المحاولة دي ما زالت مالكة الشاهد
        (`witness_attempt_id IS attempt_id`) **والحالة ليست 'confirmed'**.

        حرس الإنهاء: شاهد 'confirmed' (حذف بعيد مثبت) ما بيتحذفش أبدًا من مسار «الشات لسه
        موجود» ⇒ مفيش إحياء لشات متحذّف. يرجّع True لو النجح (الصف اتشال)، False لو عملية
        أحدث سبقتنا أو الحالة مؤكّدة.
        """
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            cur = conn.execute(
                "DELETE FROM deleted_conversations "
                "WHERE conversation_id=? AND witness_attempt_id IS ? AND remote_state != ?",
                (conversation_id, attempt_id, self.REMOTE_CONFIRMED),
            )
            ok = cur.rowcount == 1
            conn.commit()
            return ok
        except Exception:
            conn.rollback()
            raise

    def remote_deletion_state(self, conversation_id: str) -> str | None:
        """حالة الحذف البعيد للشات (None لو مفيش حذف بعيد اتبدأ)."""
        row = self._conn.execute(
            "SELECT remote_state FROM deleted_conversations WHERE conversation_id=?",
            (conversation_id,),
        ).fetchone()
        return row["remote_state"] if row is not None else None

    def remote_deletion_metadata(self, conversation_id: str) -> tuple[str | None, str | None]:
        """(حالة الحذف البعيد، طابعه الزمني) في قراءة واحدة — للاسترجاع الأمين بعد الفشل.

        بنقرأ الحقلين مع بعض عشان الاسترجاع يعيد الحالة **والطابع** الأصليين بالظبط (مش طابع
        جديد). هُوية المالك (compare-and-swap) بتُقرأ من `witness_attempt_id()` منفصلة.
        """
        row = self._conn.execute(
            "SELECT remote_state, remote_updated_at FROM deleted_conversations "
            "WHERE conversation_id=?",
            (conversation_id,),
        ).fetchone()
        if row is None:
            return (None, None)
        return (row["remote_state"], row["remote_updated_at"])

    def clear_remote_deletion(self, conversation_id: str) -> None:
        """يشيل شاهد الحذف (استرجاع محلي) — يُستخدم لما يثبت إن الشات **لسه موجود** بعيدًا.

        كتابة غير مشروطة: تُستخدم في مسارات ملكية المحاولة اللي بتتحقق من الملكية أولًا.
        """
        self._conn.execute(
            "DELETE FROM deleted_conversations WHERE conversation_id=?",
            (conversation_id,),
        )
        self._conn.commit()

    def list_pending_remote_deletions(self) -> list[str]:
        """معرّفات الشاتات اللي حذفها البعيد لسه معلّق ('deleting'/'uncertain')."""
        rows = self._conn.execute(
            "SELECT conversation_id FROM deleted_conversations "
            "WHERE remote_state IN (?, ?)",
            (self.REMOTE_DELETING, self.REMOTE_UNCERTAIN),
        ).fetchall()
        return [r["conversation_id"] for r in rows]

    def list_pending_remote_deletions_with_owner(self) -> list[tuple[str, str | None]]:
        """زي `list_pending_remote_deletions` لكن مع رمز المحاولة المالكة لكل شات.

        التسوية بتستخدم المالك (`witness_attempt_id`) للـ compare-and-swap، فما تطمسش
        محاولة أحدث بدأت بعد ما قرأنا القايمة.
        """
        rows = self._conn.execute(
            "SELECT conversation_id, witness_attempt_id FROM deleted_conversations "
            "WHERE remote_state IN (?, ?)",
            (self.REMOTE_DELETING, self.REMOTE_UNCERTAIN),
        ).fetchall()
        return [(r["conversation_id"], r["witness_attempt_id"]) for r in rows]

    def list_pending_remote_deletions_detail(self) -> list[dict]:
        """تفاصيل آمنة للحذف البعيد المعلّق ('deleting'/'uncertain') للعرض والتسوية في Mini App."""
        rows = self._conn.execute(
            "SELECT conversation_id, remote_state, remote_updated_at, deleted_at "
            "FROM deleted_conversations "
            "WHERE remote_state IN (?, ?) "
            "ORDER BY COALESCE(remote_updated_at, deleted_at) DESC, conversation_id ASC",
            (self.REMOTE_DELETING, self.REMOTE_UNCERTAIN),
        ).fetchall()
        return [
            {
                "conversation_id": r["conversation_id"],
                "state": r["remote_state"],
                "updated_at": r["remote_updated_at"] or r["deleted_at"] or "",
            }
            for r in rows
        ]

    def claim_remote_reconcile(self, conversation_id: str) -> str | None:
        """يمتلك جولة تسوية لحذف بعيد معلّق ('deleting'/'uncertain') بدون تغيير الحالة أو الطابع.

        يرجّع `attempt_id` جديد للـ CAS (لمنع تداخل محاولة أقدم/أحدث)، أو None لو الشات
        مش معلّق أو اتأكّد حذفه مسبقًا ('confirmed'). لو الشاهد كان قديمًا بلا `witness_origin`
        (`NULL`) بيوسمه `'attempt'` مع `witness_preexisting=1` زي `_begin_attempt_nocommit`.
        """
        attempt_id = uuid.uuid4().hex
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            cur = conn.execute(
                "UPDATE deleted_conversations SET witness_attempt_id=?, witness_origin=?, "
                "witness_preexisting=CASE WHEN witness_origin=? THEN witness_preexisting ELSE 1 END "
                "WHERE conversation_id=? AND remote_state IN (?, ?)",
                (
                    attempt_id,
                    self.WITNESS_ORIGIN_ATTEMPT,
                    self.WITNESS_ORIGIN_ATTEMPT,
                    conversation_id,
                    self.REMOTE_DELETING,
                    self.REMOTE_UNCERTAIN,
                ),
            )
            ok = cur.rowcount == 1
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return attempt_id if ok else None

    def is_legacy_witness(self, conversation_id: str) -> bool:
        """هل الشاهد **سبق** أول محاولة حذف بعيد (حذف محلي قديم)؟

        التصنيف **متين وغير زمني** (OHB2-PR6 / TS-1): بيعتمد على `witness_preexisting`
        (1 = الصف كان موجودًا قبل المحاولة) بدل مقارنة `deleted_at` بـ `remote_updated_at`.
        الصفوف القديمة (المرحّلة) بتاخد 1؛ أي محاولة جديدة على شاهد قديم بتخليه 1 (monotonic)؛
        ومحاولة جديدة على صف أنشأته بنفسها بتخليه 0. القيمة دائمة ⇒ تنجو من الانهيار/إعادة
        التشغيل/إعادة المحاولة، وما بتعتمدش على دقّة الساعة ولا رجوعها ولا التطبيع.
        """
        row = self._conn.execute(
            "SELECT witness_preexisting FROM deleted_conversations WHERE conversation_id=?",
            (conversation_id,),
        ).fetchone()
        if row is None:
            return False
        return bool(row["witness_preexisting"])

    def witness_attempt_id(self, conversation_id: str) -> str | None:
        """رمز محاولة الحذف المالكة للشاهد (None لو مفيش صف أو الشاهد قديم بلا محاولة)."""
        row = self._conn.execute(
            "SELECT witness_attempt_id FROM deleted_conversations WHERE conversation_id=?",
            (conversation_id,),
        ).fetchone()
        return None if row is None else row["witness_attempt_id"]

    def _clear_tombstone_nocommit(self, conversation_id: str) -> None:
        """يشيل شاهد الحذف **داخل معاملة المستدعي** (إعادة تفاعل صريح من المستخدم)."""
        self._conn.execute(
            "DELETE FROM deleted_conversations WHERE conversation_id=?",
            (conversation_id,),
        )

    def delete_conversation(self, conversation_id: str, now: str, *, remote_confirmed: bool = False) -> dict:
        """حذف محلي آمن لشات في **معاملة ذرّية واحدة** (OHB2-C7).

        يشيل كل الأثر المحلي المرتبط بالشات من غير أي نداء خارجي (مفيش حذف بعيد):
        - `watched`: المتابعة + أي علامة تسليم معلّقة (ننسّقها عبر `on_unwatch` أولاً حتى
          ما يتفقدش دليل تسليم اتّبعت فعلًا ⇒ مفيش إشعار مكرّر بعد الحذف).
        - `outbox` غير المنتهي (`pending`/`claimed`): نشطبه كـ `discarded` (CAS من حالتين)
          فمستحيل يتبعت بعده. حالات `sending`/`unknown` (الـ POST ممكن يكون بدأ) **مابنلمسهاش**
          — احترامًا للغموض (مفيش إدّعاء إلغاء، ومفيش إعادة POST تلقائية).
        - `creation_jobs` غير المنتهي (`pending`/`claimed`): نشطبه كـ `discarded` بنفس المنطق.
        - `completion_pending` (كل الأنواع): يتحذف (الآثار المحلية المعلّقة للشات الملغي).
        - `notification_state` / `notifier_pending` / `notifier_retry_not_before`:
          يتحذفوا عشان المُبلّل/المراقب ما يكتشفوش الشات المحذوف كـ «جديد» ويبعتوا إشعار.
        - `notification_inbox`: بيتسيب **كأثر** (تدقيق) — بيتم وسم تسليمه المعلّق كـ `superseded`
          ومسح الحجز/موعد الإعادة عشان مايتسلّمش بعد الحذف، من غير حذف الصفوف.
        - `user_state` (توجيه برومت معلّق لنفس الشات): يتفكّك (عشان مايتوجّهش لشات ملغي).
        - `watcher` hints in-memory: تتنضّف عبر `on_unwatch`.

        بترجّع ملخّص عددّي (للأثر). idempotent: شات محذوف مسبقًا ⇒ أصفار (مفيش خطأ).
        """
        if self.on_unwatch is not None:
            self.on_unwatch(conversation_id)
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT pending_delivery_state FROM watched WHERE conversation_id=?",
                (conversation_id,),
            ).fetchone()
            if row is not None and row["pending_delivery_state"]:
                self.record_notification_sent(
                    conversation_id, row["pending_delivery_state"], now, _commit=False
                )
            watched_deleted = conn.execute(
                "DELETE FROM watched WHERE conversation_id=?", (conversation_id,)
            ).rowcount
            outbox_discarded = conn.execute(
                "UPDATE outbox SET status=?, error=?, updated_at=? WHERE conversation_id=? "
                "AND status IN (?, ?)",
                (OUTBOX_DISCARDED, "اتحذف مع الشات", now, conversation_id,
                 OUTBOX_PENDING, OUTBOX_CLAIMED),
            ).rowcount
            creation_discarded = conn.execute(
                "UPDATE creation_jobs SET status=?, error=?, updated_at=? WHERE conversation_id=? "
                "AND status IN (?, ?)",
                (CREATION_DISCARDED, "اتحذف مع الشات", now, conversation_id,
                 CREATION_PENDING, CREATION_CLAIMED),
            ).rowcount
            completion_deleted = conn.execute(
                "DELETE FROM completion_pending WHERE conversation_id=?", (conversation_id,)
            ).rowcount
            notif_state_deleted = conn.execute(
                "DELETE FROM notification_state WHERE conversation_id=?", (conversation_id,)
            ).rowcount
            conn.execute(
                "DELETE FROM notifier_pending WHERE conversation_id=?", (conversation_id,)
            )
            conn.execute(
                "DELETE FROM notifier_retry_not_before WHERE conversation_id=?", (conversation_id,)
            )
            inbox_superseded = conn.execute(
                "UPDATE notification_inbox SET delivery_status='superseded', claim_token=NULL, "
                "claim_at=NULL, next_retry_at=NULL WHERE conversation_id=? "
                "AND delivery_status IN ('pending', 'failed')",
                (conversation_id,),
            ).rowcount
            conn.execute(
                "UPDATE user_state SET awaiting_conversation_id=NULL, awaiting_kind=NULL, "
                "awaiting_at=NULL, awaiting_title=NULL WHERE awaiting_conversation_id=?",
                (conversation_id,),
            )
            # OHB2-C7 (RESURRECTION-FIX): شاهد الحذف الدائم يُكتب **آخر** حاجة في نفس
            # المعاملة، بعد إزالة كل الأثر المحلي. ترتيبه آخرًا مقصود: خلال المعاملة نفسها
            # (`record_notification_sent` بتتنادى جوّه المعاملة قبل كده) لازم الشات يبان
            # لسه غير محذوف عشان التسجيل الداخلي يكمّل؛ وبعد الـ commit الشاهد فعّال
            # لأي مسار لاحق (ساعتها مستحيل يتخلّل بين الكتابة والـ commit — قفل الكتابة).
            self._tombstone_nocommit(conversation_id, now)
            # OHB2-MINIAPP: لو المستدعي أكّد نجاح الحذف البعيد، نثبّت الحالة 'confirmed'
            # في **نفس** معاملة الحذف المحلي (ذرّي: مفيش حالة «محذوف محليًا بلا نتيجة بعيدة»).
            if remote_confirmed:
                conn.execute(
                    "UPDATE deleted_conversations SET remote_state=?, remote_updated_at=? "
                    "WHERE conversation_id=?",
                    (self.REMOTE_CONFIRMED, now, conversation_id),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return {
            "watched_deleted": int(watched_deleted),
            "outbox_discarded": int(outbox_discarded),
            "creation_discarded": int(creation_discarded),
            "completion_deleted": int(completion_deleted),
            "notif_state_deleted": int(notif_state_deleted),
            "inbox_superseded": int(inbox_superseded),
        }

    # ------------------------------------------------------ Mini App sessions
    # OHB2-PHASE1A: جلسات الـ Mini App **دائمة** في نفس قاعدة SQLite (نفس المالك
    # الواحد للعملية). بنخزّن **هاش** التوكن بس (`token_hash` = SHA-256 hex)؛ التوكن
    # الخام عمود ما بيتخزّنش. كل عملية صغيرة معاملة واحدة (`with self._conn`) — مفيش
    # نداء شبكة جوه أي معاملة، و`sqlite3` بيدير commit/rollback تلقائيًا.

    def add_web_session(
        self, token_hash: str, user_id: int, created_at: float, expires_at: float, profile_json: str
    ) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO web_sessions (token_hash, user_id, created_at, expires_at, profile) "
                "VALUES (?, ?, ?, ?, ?)",
                (token_hash, int(user_id), float(created_at), float(expires_at), profile_json),
            )

    def get_web_session(self, token_hash: str, now: float) -> tuple[int, float, float, str] | None:
        """يرجّع (user_id, created_at, expires_at, profile_json) للجلسة **غير المنتهية**.

        المنتهي ما بيرجّعش أبدًا (fail closed): بنفلتر بـ `expires_at > now` في نفس
        الاستعلام. أي `token_hash` غير موجود/غير صالح ⇒ None."""
        row = self._conn.execute(
            "SELECT user_id, created_at, expires_at, profile FROM web_sessions "
            "WHERE token_hash=? AND expires_at > ?",
            (token_hash, float(now)),
        ).fetchone()
        if row is None:
            return None
        return int(row["user_id"]), float(row["created_at"]), float(row["expires_at"]), row["profile"]

    def delete_web_session(self, token_hash: str) -> None:
        """إلغاء/تسجيل خروج دائم (نجو من restart). غير موجود ⇒ لا شيء (idempotent)."""
        with self._conn:
            self._conn.execute("DELETE FROM web_sessions WHERE token_hash=?", (token_hash,))

    def prune_web_sessions(self, now: float) -> int:
        """يحذف الجلسات المنتهية. يرجّع العدد المحذوف. غير مدمّر للجلسات السارية."""
        with self._conn:
            cur = self._conn.execute("DELETE FROM web_sessions WHERE expires_at <= ?", (float(now),))
            return int(cur.rowcount)

    def count_web_sessions(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM web_sessions").fetchone()
        return int(row["n"])

    def list_watched(self) -> list[Watched]:
        """كل صفوف المتابعة **غير المتشاهدة حذفًا** (منع إفصاح عنوان شات محذوف).

        OHB2-RESIDUAL: بنستبعد أي `conversation_id` عليه شاهد حذف دائم — الحذف المؤكّد
        بيشيل صف المتابعة أصلًا، لكن خلال نافذة `deleting`/`uncertain` الصف بيفضل موجود؛
        الاستبعاد هنا يمنع ظهور عنوانه في قوايم البوت/الـ Mini App (وبيمنح المراقب نفس
        النتيجة اللي بيفرضها حرسه الخاص). الصفوف نفسها ما بتتحذفش (استرجاع الحذف/الإحياء
        الصريح يفضلوا شغالين)، بنستبعدها من العرض بس.
        """
        rows = self._conn.execute(
            "SELECT conversation_id, title, last_state, chat_id, submitted_at, added_at, "
            "retry_count, pending_delivery_state, watch_seq FROM watched "
            "WHERE NOT EXISTS (SELECT 1 FROM deleted_conversations d "
            "WHERE d.conversation_id = watched.conversation_id)"
        ).fetchall()
        return [
            Watched(
                r["conversation_id"], r["title"], r["last_state"], r["chat_id"],
                r["submitted_at"], r["added_at"], r["retry_count"],
                r["pending_delivery_state"], r["watch_seq"],
            )
            for r in rows
        ]

    def get_watched(self, conversation_id: str) -> Watched | None:
        """يجيب صف متابعة واحد (بالحقول الطازجة، خاصة pending_delivery_state) أو None."""
        r = self._conn.execute(
            "SELECT conversation_id, title, last_state, chat_id, submitted_at, added_at, "
            "retry_count, pending_delivery_state, watch_seq FROM watched WHERE conversation_id=?",
            (conversation_id,),
        ).fetchone()
        if r is None:
            return None
        return Watched(
            r["conversation_id"], r["title"], r["last_state"], r["chat_id"],
            r["submitted_at"], r["added_at"], r["retry_count"], r["pending_delivery_state"],
            r["watch_seq"],
        )

    def increment_watched_retry(self, conversation_id: str) -> int:
        """يزوّد عدّاد محاولات إشعار الانتهاء ذرّياً ويرجّع القيمة الجديدة (TASK 54).

        الـ UPDATE والقراءة في جملة واحدة (RETURNING)، فالقرار "استنفدنا الحد؟" مبني على
        عدّاد حقيقي مش snapshot قديم — مستحيل يتخطّى الحد أو يتكرّر الإشعار النهائي.
        """
        row = self._conn.execute(
            "UPDATE watched SET retry_count=retry_count+1 WHERE conversation_id=? "
            "RETURNING retry_count",
            (conversation_id,),
        ).fetchone()
        self._conn.commit()
        return int(row["retry_count"]) if row else 0

    def increment_watched_retry_if_seq(self, conversation_id: str, expected_watch_seq: str) -> int:
        """NTF-23: يزوّد عدّاد المحاولات ذرّياً **مشروطًا** بمعرّف دورة المتابعة.

        زي `increment_watched_retry` بس بشرط `watch_seq` (compare-and-swap). لو الدورة
        اتغيّرت (متابعة جديدة أثناء await)، ما بنزوّدش العدّاد الجديد بقرار قديم —
        بنرجّع 0 (يعني «مافيش صف مطابق»). الـ UPDATE والقراءة في جملة واحدة.
        """
        row = self._conn.execute(
            "UPDATE watched SET retry_count=retry_count+1 "
            "WHERE conversation_id=? AND watch_seq=? RETURNING retry_count",
            (conversation_id, expected_watch_seq),
        ).fetchone()
        self._conn.commit()
        return int(row["retry_count"]) if row else 0

    def advance_watched_state(self, conversation_id: str, state: str) -> None:
        """يسجّل الحالة المسجَّلة ويصفّر عدّاد المحاولات (TASK 54).

        الحالة اللي بتوصل هنا دايمًا مش منتهية (المسار المنتهي بيخرج قبلها)، فتسجيلها
        معناه إن إشعار الانتهاء القديم مات أو ما اتولدش ⇒ بداية دورة إشعار جديدة بميزانية
        كاملة. التصفير والكتابة في جملة واحدة (ذرّية) عشان مفيش حالة وسطية.
        """
        self._conn.execute(
            "UPDATE watched SET last_state=?, retry_count=0 WHERE conversation_id=?",
            (state, conversation_id),
        )
        self._conn.commit()

    def is_watched(self, conversation_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM watched WHERE conversation_id=?", (conversation_id,)
        ).fetchone()
        return row is not None

    def set_last_state(self, conversation_id: str, state: str) -> None:
        self._conn.execute(
            "UPDATE watched SET last_state=? WHERE conversation_id=?", (state, conversation_id)
        )
        self._conn.commit()

    def update_watched_title(self, conversation_id: str, title: str) -> bool:
        """يحدّث عنوان شات متابَع (القرار: المراقب بيخزّن العنوان الطازج).

        - تحديث السجل المطابق بس.
        - مفيش كتابة لو العنوان مش موجود/فاضي أو ما اتغيّرش (مفيش كتابات زيادة).
        - مفيش كتابة لو السجل مش موجود (اتشال/اتمسح) — ما بنعملش صف جديد.
        بيرجّع True لو فيه كتابة فعليّة، وFalse غير كده.
        """
        title = (title or "").strip()
        if not title:
            return False
        row = self._conn.execute(
            "SELECT title FROM watched WHERE conversation_id=?", (conversation_id,)
        ).fetchone()
        if row is None:
            return False
        if (row["title"] or "").strip() == title:
            return False
        self._conn.execute(
            "UPDATE watched SET title=? WHERE conversation_id=?", (title, conversation_id)
        )
        self._conn.commit()
        return True

    # -------------------------------------------------------------- user state
    # حالة توجيه الرسالة الجاية. كل حالة ليها وقت (awaiting_at) وتنتهي بعد AWAITING_TTL.
    #   reply / newchat / reposearch : لمرة واحدة (بتتستهلك أول رسالة).
    #   route : توجيه مستمر لشات معيّن؛ كل رسالة بتجدّد المهلة، وبينتهي بعد AWAITING_TTL
    #           من آخر نشاط أو بالإلغاء.
    def set_awaiting(
        self,
        telegram_id: int,
        conversation_id: str | None,
        kind: str | None,
        title: str | None = None,
        now: datetime | None = None,
        *,
        commit: bool = True,
    ) -> None:
        stamp = (now or datetime.now(timezone.utc)).isoformat() if kind else None
        self._conn.execute(
            "INSERT INTO user_state(telegram_id, awaiting_conversation_id, awaiting_kind, "
            "awaiting_at, awaiting_title) VALUES(?, ?, ?, ?, ?) ON CONFLICT(telegram_id) DO UPDATE SET "
            "awaiting_conversation_id=excluded.awaiting_conversation_id, "
            "awaiting_kind=excluded.awaiting_kind, awaiting_at=excluded.awaiting_at, "
            "awaiting_title=excluded.awaiting_title",
            (telegram_id, conversation_id, kind, stamp, title),
        )
        if commit:
            self._conn.commit()

    def clear_awaiting(self, telegram_id: int) -> None:
        self.set_awaiting(telegram_id, None, None)

    def renew_awaiting(self, telegram_id: int, now: datetime | None = None) -> None:
        """يجدّد مهلة توجيه `route` **بدون استهلاك** (route مستمر مش لمرة واحدة).

        بنستخدمها في `handle_text` بدل `take_awaiting` عشان مسار route مايعملش أي
        استهلاك؛ الاستهلاك الذرّي بقى للحالات لمرة واحدة بس جوه كتابة السجل الدائم.
        """
        stamp = (now or datetime.now(timezone.utc)).isoformat()
        self._conn.execute(
            "UPDATE user_state SET awaiting_at=? WHERE telegram_id=?", (stamp, telegram_id)
        )
        self._conn.commit()

    @staticmethod
    def awaiting_is_expired(since: datetime | None, now: datetime | None = None) -> bool:
        """هل انتهت مهلة حالة الانتظار؟ (نفس معيار `take_awaiting` بالحرف)."""
        if since is None:
            return True
        return (now or datetime.now(timezone.utc)) - since > AWAITING_TTL

    def awaiting_state(
        self, telegram_id: int
    ) -> tuple[str | None, str | None, str | None, datetime | None]:
        """يقرأ حالة الانتظار **بدون استهلاك** (قراءة فقط، بدون أي كتابة).

        P1: بديل `take_awaiting` في `handle_text` — الاستهلاك (مسح الحالة لمرة واحدة أو
        تجديد route) بقى منفصلًا وذرّيًا مع كتابة السجل الدائم. بترجّع
        (conversation_id, kind, title, awaiting_at) أو (None, None, None, None).
        """
        row = self._conn.execute(
            "SELECT awaiting_conversation_id, awaiting_kind, awaiting_title, awaiting_at "
            "FROM user_state WHERE telegram_id=?",
            (telegram_id,),
        ).fetchone()
        if not row or not row["awaiting_kind"]:
            return None, None, None, None
        return (
            row["awaiting_conversation_id"],
            row["awaiting_kind"],
            row["awaiting_title"],
            _parse_iso(row["awaiting_at"]),
        )

    def _clear_awaiting_nocommit(self, telegram_id: int) -> None:
        """يمسح حالة الانتظار **جوه معاملة المستدعي** (بدون commit)."""
        self._conn.execute(
            "UPDATE user_state SET awaiting_conversation_id=NULL, awaiting_kind=NULL, "
            "awaiting_at=NULL, awaiting_title=NULL WHERE telegram_id=?",
            (telegram_id,),
        )

    def consume_one_shot_awaiting(
        self, telegram_id: int, expected_kind: str, update_id: int | None, now: str
    ) -> bool:
        """يستهلك حالة انتظار **لمرة واحدة** ويسجّل «معالَج» **ذرّيًا** (معاملة واحدة).

        P1 (مسارات بلا سجل عمل دائم، زي بحث المستودعات): الحالة والعلامة إما يتحفظوا معًا
        أو ولا واحد. تُرجّع True لو استهلكناها فعلًا، False لو الحالة اتغيّرت/انتهت/مستهلكة
        قبل كده. **بعد** ما الأثر (إرسال القائمة) ينجح — عشان عطل قبل كده يخلّي إعادة
        التسليم تعيد التنفيذ (مفيش فقد)، والتكرار المحتمل (قائمة مكرّرة) غير ضار.
        """
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            if update_id is not None and self.update_is_processed(update_id):
                conn.rollback()
                return False
            row = conn.execute(
                "SELECT awaiting_kind, awaiting_at FROM user_state WHERE telegram_id=?",
                (telegram_id,),
            ).fetchone()
            if row is None or row["awaiting_kind"] != expected_kind:
                conn.rollback()
                return False
            if self.awaiting_is_expired(_parse_iso(row["awaiting_at"]), _parse_iso(now)):
                conn.rollback()
                return False
            self._clear_awaiting_nocommit(telegram_id)
            # OHB2-MANUAL-POLLING-OUTCOME: النتيجة الدائمة ذرّية مع الاستهلاك (إرسال القايمة
            # نجح فعلًا قبل النداء ده).
            self._mark_processed_nocommit(update_id, now, update_outcomes.DURABLE_COMPLETED)
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise

    # ------------------------------------------------- telegram update dedup
    # OHB2-DUPLICATE-TELEGRAM-PROMPT-DISPATCH: مفتاح منع التكرار على مستوى **التحديث**.
    # الضمان: تحديث تيليجرام واحد ⇒ قرار معالجة واحد (إرسال واحد لشات موجود، أو إنشاء
    # شات واحد، أو رد واحد) حتى لو وصل مرتين (إعادة تسليم/إعادة تشغيل/تزامن). المفتاح
    # `update_id` فريد على مستوى تيليجرام، فالإدراج ذرّي (`INSERT OR IGNORE`) بيخلّي أول
    # معالج يفوز والبقية تُرفض قبل أي عملية خارجية. ده **كشف تكرار**، مش ضمان exactly-once
    # خارجي (نفس عقد المشروع: at-most-once + تسوية يدوية للنتائج الغامضة).
    def update_is_processed(self, update_id: int) -> bool:
        """هل التحديث مسجّل «معالَج» بالفعل؟ (فحص قراءة فقط، بدون أي كتابة).

        P1: الحاجز بقى **فحص قراءة** — التسجيل نفسه بيحصل **ذرّيًا مع كتابة السجل الدائم**
        جوه معاملة `add_or_group_outbox`/`add_creation_job`. كده مايحصلش أبدًا إن تحديث
        يتسجّل «معالَج» من غير ما يكون سجله الدائم اتكتب: إما الاتنين يتكتبوا مع بعض (نفس
        المعاملة)، أو ولا واحد (لو العملية ماتت/فشلت قبل الـ commit) ⇒ إعادة التسليم بتنفّذ.
        """
        row = self._conn.execute(
            "SELECT 1 FROM processed_updates WHERE update_id=?", (int(update_id),)
        ).fetchone()
        return row is not None

    def mark_update_processed(self, update_id: int, now: str) -> bool:
        """يسجّل التحديث «معالَج» **ذرّيًا** (INSERT OR IGNORE على مفتاح أساسي).

        True لو أول مرة، False لو موجود قبل كده. الدالة دي مسار **وحدة/متوافق** (بتستخدمها
        اختبارات الحاجز)؛ المسار الحقيقي في البوت بيسجّل ذرّيًا مع السجل الدائم عبر
        `_mark_processed_nocommit` جوه معاملة كتابة العملية.
        """
        cur = self._conn.execute(
            "INSERT OR IGNORE INTO processed_updates(update_id, processed_at) VALUES(?, ?)",
            (int(update_id), now),
        )
        self._conn.commit()
        return cur.rowcount == 1

    def _mark_processed_nocommit(
        self, update_id: int | None, now: str, outcome: str | None = None
    ) -> None:
        """يسجّل «معالَج» داخل معاملة المستدعي (no-op لو `update_id` None).

        P1: بيتنادى **في نفس معاملة** كتابة السجل الدائم (outbox/creation) ⇒ التسجيل
        والكتابة إما ينجحوا معًا أو يفشلوا معًا (ذرّية حقيقية، مش ادّعاء).

        OHB2-MANUAL-POLLING-OUTCOME: `outcome` (لو متمرّر) بيتكتب **في نفس المعاملة** ⇒
        النتيجة الدائمة (دليل الإقرار) بتُحفظ ذرّيًا مع العملية اللي نفّذت النية. لو التحديث
        مسجّل قبل كده (مسار تكرار/تزامن)، بنرقّي النتيجة بـ COALESCE (مفيش clobber بقيمة
        NULL) من غير ما نلمس `processed_at`.
        """
        if update_id is None:
            return
        self._conn.execute(
            "INSERT INTO processed_updates(update_id, processed_at, outcome) VALUES(?, ?, ?) "
            "ON CONFLICT(update_id) DO UPDATE SET "
            "outcome=COALESCE(excluded.outcome, processed_updates.outcome)",
            (int(update_id), now, outcome),
        )

    # ---------------------------------------------- OHB2-MANUAL-POLLING-OUTCOME
    def mark_update_outcome(
        self,
        update_id: int,
        now: str,
        outcome: str,
        *,
        reason: str | None = None,
        commit: bool = True,
    ) -> None:
        """يسجّل **نتيجة دائمة** لتحديث (بـ upsert).

        - النتائج **المؤهّلة** (`durable_*`/`explicitly_ignored`/`duplicate_completed`)
          بتتكتب في `processed_updates.outcome` (دليل الإقرار).
        - النتائج **غير المؤهّلة** (`failed_*`/`partial_or_unknown`) بتتكتب في
          `update_failures` (قرار مُوثَّق) **و** `processed_updates.outcome` (للرصد) —
          فمستحيل تتحوّل لنجاح.

        `commit=False` للاستخدام **جوه معاملة المستدعي** (ذرّية مع العملية الدائمة).
        """
        from . import update_outcomes as _uo

        if _uo.is_ack_eligible(outcome):
            self._conn.execute(
                "INSERT INTO processed_updates(update_id, processed_at, outcome) VALUES(?, ?, ?) "
                "ON CONFLICT(update_id) DO UPDATE SET outcome=excluded.outcome",
                (int(update_id), now, outcome),
            )
        else:
            # **مهم**: الفشل **مايتكتبش** في `processed_updates` — الجدول ده هو مصدر
            # الديدَب (`update_is_processed`)، وكتابة صف فشل فيه كانت هتخلّي إعادة التسليم
            # تُرفض كتكرار ⇒ فقد التحديث. الفشل بيتسجّل في `update_failures` بس، فغياب
            # النتيجة في `processed_updates` = غير مؤهّل (fail-closed) + إعادة التسليم تنفّذ.
            self._conn.execute(
                "INSERT INTO update_failures(update_id, outcome, reason, failed_at) "
                "VALUES(?, ?, ?, ?) "
                "ON CONFLICT(update_id) DO UPDATE SET "
                "outcome=excluded.outcome, reason=excluded.reason, failed_at=excluded.failed_at",
                (int(update_id), outcome, reason, now),
            )
        if commit:
            self._conn.commit()

    def update_outcome(self, update_id: int) -> str | None:
        """فئة نتيجة التحديث كما هي مسجّلة **بثبات**.

        بتقرا `processed_updates.outcome` الأول (دليل الإقرار)، وترجع لـ
        `update_failures.outcome` لو التحديث مسجّل فشل بس (للرصد). `None` لو مالوش أي
        نتيجة مسجّلة (⇒ غير مؤهّل، fail-closed).
        """
        row = self._conn.execute(
            "SELECT outcome FROM processed_updates WHERE update_id=?", (int(update_id),)
        ).fetchone()
        if row is not None and row["outcome"] is not None:
            return row["outcome"]
        return self.update_failure(update_id)

    def update_failure(self, update_id: int) -> str | None:
        """فئة فشل التحديث من `update_failures` (None لو مفيش فشل مسجّل)."""
        row = self._conn.execute(
            "SELECT outcome FROM update_failures WHERE update_id=?", (int(update_id),)
        ).fetchone()
        return row["outcome"] if row else None

    def is_update_acknowledgment_eligible(self, update_id: int) -> bool:
        """هل التحديث مؤهّل للإقرار؟ (fail-closed: أي نتيجة غير مؤهّلة أو NULL ⇒ False)."""
        from . import update_outcomes as _uo

        return _uo.is_ack_eligible(self.update_outcome(update_id))

    def acknowledgment_boundary(self, received_ids: list[int]) -> int | None:
        """أطول بادئة مؤهّلة بترتيب الاستقبال ⇒ معرّف آخر تحديث مؤهّل (أو None).

        بتحسب النتائج من `processed_updates.outcome` **المُـcommit**، فحدّ الإقرار مبني على
        دليل دائم مش على رجوع الـ handler. البادئة بتتوقف عند أول تحديث غير مؤهّل.
        """
        from . import update_outcomes as _uo

        outcomes = {uid: self.update_outcome(uid) for uid in received_ids}
        return _uo.acknowledgment_boundary(received_ids, outcomes)

    def commit_batch_outcomes(
        self, outcomes: list[tuple[int, str]], now: str
    ) -> int | None:
        """يثبّت نتائج دفعة **و** الحدّ المحلي **في معاملة واحدة** (ذرّي/restart-safe).

        - `outcomes`: [(update_id, outcome), ...] **بترتيب الاستقبال**.
        - بيكتب كل نتيجة (نفس دلالات `mark_update_outcome`) + بيحسب حدّ الإقرار من
          **نفس الحالة داخل نفس المعاملة** + بيثبّت الحدّ في `settings` (مفتاح
          `acknowledgment_boundary`) — كله أو ولا حاجة.
        - بترجّع الحدّ الجديد (أو None)، وبيستخدمه أي مستدعي يستطلِع لاحقًا بـ
          `getUpdates(offset=boundary+1)`.

        **مش** إقرار تيليجرام: ده تسجيل محلي بس. الإقرار الفعلي بيحصل لما طلب
        `getUpdates` التالي يحمل موضع أعلى — وده مسؤولية حلقة الاستطلاع (بره نطاق
        التغيير ده؛ دلالات الـ offset/الإقرار متجمّدة).
        """
        from . import update_outcomes as _uo

        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            for update_id, outcome in outcomes:
                if _uo.is_ack_eligible(outcome):
                    conn.execute(
                        "INSERT INTO processed_updates(update_id, processed_at, outcome) "
                        "VALUES(?, ?, ?) "
                        "ON CONFLICT(update_id) DO UPDATE SET outcome=excluded.outcome",
                        (int(update_id), now, outcome),
                    )
                else:
                    # نفس قرار `mark_update_outcome`: الفشل **مايدخلش** `processed_updates`
                    # (مصدر الديدَب) ⇒ إعادة التسليم تنفّذ + الحدّ يتوقف عنده (fail-closed).
                    conn.execute(
                        "INSERT INTO update_failures(update_id, outcome, reason, failed_at) "
                        "VALUES(?, ?, ?, ?) "
                        "ON CONFLICT(update_id) DO UPDATE SET "
                        "outcome=excluded.outcome, reason=excluded.reason, "
                        "failed_at=excluded.failed_at",
                        (int(update_id), outcome, None, now),
                    )
            boundary = _uo.acknowledgment_boundary(
                [uid for uid, _ in outcomes],
                {uid: self._outcome_in_txn(uid) for uid, _ in outcomes},
            )
            if boundary is not None:
                # OHB2-STAGE2 (D4/monotonicity): حارس مونوتونية — الحدّ **مايتراجعش أبدًا**.
                # بنقرا القيمة الحالية **جوه نفس المعاملة** (`BEGIN IMMEDIATE` ⇒ مفيش كتابة
                # متزامنة)، وبنكتب بس لو الحدّ الجديد **أعلى** من المحفوظ. مساواة/أقل ⇒ no-op
                # (الحدّ القديم محفوظ). النتيجة + الحدّ بيتثبّتوا معًا (نفس المعاملة) ⇒ ذرّي.
                row = conn.execute(
                    "SELECT value FROM settings WHERE key=?", (self.ACK_BOUNDARY_KEY,)
                ).fetchone()
                current = (
                    int(row["value"]) if row is not None and row["value"] is not None else None
                )
                if current is None or int(boundary) > current:
                    conn.execute(
                        "INSERT INTO settings(key, value) VALUES(?, ?) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (self.ACK_BOUNDARY_KEY, str(int(boundary))),
                    )
            conn.commit()
            return boundary
        except Exception:
            conn.rollback()
            raise

    def _outcome_in_txn(self, update_id: int) -> str | None:
        row = self._conn.execute(
            "SELECT outcome FROM processed_updates WHERE update_id=?", (int(update_id),)
        ).fetchone()
        return row["outcome"] if row else None

    def get_acknowledgment_boundary(self) -> int | None:
        """الحدّ المحلي المُثبَّت (None لو مفيش). ده **مش** إقرار تيليجرام."""
        raw = self.get_setting(self.ACK_BOUNDARY_KEY)
        return int(raw) if raw is not None else None

    def prune_processed_updates(
        self, keep: int | None = None, boundary: int | None = None
    ) -> int:
        """يقلّم سجل التحديثات المعالَجة بأمان اعتمادًا على **حدّ الإقرار** (Stage 3).

        قاعدة السلامة: صفوف `update_id <= boundary` **مايحتاجهاش** الديدَب بعد كده، لأن حلقة
        الاستطلاع بتستأنف من `boundary+1` (والحدّ مونوتوني) ⇒ تيليجرام **مش** هيعيد تسليمها.
        صفوف `> boundary` (الذيل غير المؤكَّد) بتفضل دايمًا (احتمال إعادة تسليم بعد انهيار).

        - `boundary is None` (مفيش إقرار مؤكَّد إطلاقًا) ⇒ **no-op**: ممكن إعادة تسليم أي حاجة.
        - `keep is None` ⇒ مفيش سقف إضافي: بنشيل **كل** الصفوف `<= boundary`.
        - `keep` (عدد صحيح) ⇒ بنسيب أحدث `keep` صف **من اللي `<= boundary`** بس.

        بترجّع عدد الصفوف المشالة.
        """
        if boundary is None:
            return 0
        # بنرتّب بـ (processed_at, update_id): update_id هو الترتيب الطبيعي للتحديثات،
        # وبنضمّه مع الوقت لتفادي أي التباس لو الساعة اتأخّرت.
        if keep is None:
            cur = self._conn.execute(
                "DELETE FROM processed_updates WHERE update_id <= ?",
                (int(boundary),),
            )
        else:
            cur = self._conn.execute(
                "DELETE FROM processed_updates WHERE update_id <= ? AND update_id NOT IN ("
                "  SELECT update_id FROM processed_updates WHERE update_id <= ? "
                "  ORDER BY processed_at DESC, update_id DESC LIMIT ?"
                ")",
                (int(boundary), int(boundary), int(keep)),
            )
        self._conn.commit()
        return cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0

    def count_processed_updates(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM processed_updates").fetchone()
        return int(row["n"]) if row else 0

    def take_awaiting(
        self, telegram_id: int, now: datetime | None = None
    ) -> tuple[str | None, str | None, str | None]:
        """يقرأ حالة التوجيه ويستهلكها (أو يجدّدها لو route) في معاملة ذرّية واحدة.

        بيرجّع (conversation_id, kind, title). لو الحالة انتهت مهلتها بيمسحها ويرجّع
        kind="expired". الحالات اللي لمرة واحدة بتتمسح، وrouting المستمر بيتجدّد وقته.
        BEGIN IMMEDIATE بياخد قفل الكتابة قبل القراءة، فرسالتين متزامنتين ما يقدروش
        ياخدوا نفس الحالة المستهلكة.
        """
        now = now or datetime.now(timezone.utc)
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT awaiting_conversation_id, awaiting_kind, awaiting_at, awaiting_title "
                "FROM user_state WHERE telegram_id=?",
                (telegram_id,),
            ).fetchone()
            result: tuple[str | None, str | None, str | None] = (None, None, None)
            if row and row["awaiting_kind"]:
                kind = row["awaiting_kind"]
                since = _parse_iso(row["awaiting_at"])
                expired = since is None or now - since > AWAITING_TTL
                if expired:
                    conn.execute(
                        "UPDATE user_state SET awaiting_conversation_id=NULL, awaiting_kind=NULL, "
                        "awaiting_at=NULL, awaiting_title=NULL WHERE telegram_id=?",
                        (telegram_id,),
                    )
                    result = (None, "expired", None)
                elif kind == "route":
                    conn.execute(
                        "UPDATE user_state SET awaiting_at=? WHERE telegram_id=?",
                        (now.isoformat(), telegram_id),
                    )
                    result = (row["awaiting_conversation_id"], kind, row["awaiting_title"])
                else:
                    conn.execute(
                        "UPDATE user_state SET awaiting_conversation_id=NULL, awaiting_kind=NULL, "
                        "awaiting_at=NULL, awaiting_title=NULL WHERE telegram_id=?",
                        (telegram_id,),
                    )
                    result = (row["awaiting_conversation_id"], kind, row["awaiting_title"])
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return result

    def get_awaiting(self, telegram_id: int) -> tuple[str | None, str | None]:
        row = self._conn.execute(
            "SELECT awaiting_conversation_id, awaiting_kind FROM user_state WHERE telegram_id=?",
            (telegram_id,),
        ).fetchone()
        if not row:
            return None, None
        return row["awaiting_conversation_id"], row["awaiting_kind"]

    # ------------------------------------------------------------------- outbox
    def add_outbox(self, conversation_id: str, chat_id: int, text: str, now: str) -> int:
        """يسجّل البرومت في الصندوق (status='pending') قبل أي محاولة إرسال."""
        cur = self._conn.execute(
            "INSERT INTO outbox(conversation_id, chat_id, text, status, created_at, updated_at) "
            "VALUES(?, ?, ?, ?, ?, ?)",
            (conversation_id, chat_id, text, OUTBOX_PENDING, now, now),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def add_or_group_outbox(
        self,
        conversation_id: str,
        chat_id: int,
        text: str,
        now: str,
        window: timedelta | None = None,
        client_ref: str | None = None,
        reengage: bool = False,
        update_id: int | None = None,
        consume_awaiting: tuple[int, str] | None = None,
    ) -> int:
        """تجميع (القرار 2): لو فيه برومت 'pending' لنفس الوجهة اتحدّث خلال `window`،

        نضيف النص عليه بدل ما نعمل سجل جديد. غير كده نسجّل سجل 'pending' جديد.

        الوجهة = (conversation_id, chat_id). العملية كلها جوه BEGIN IMMEDIATE عشان
        رسالتين متزامنتين مايعملوش سجلين منفصلين لنفس الدفعة. بنرجّع id السجل.

        OHB2-07 (idempotency): لو `client_ref` اتزوّد وفيه سجل موجود بنفس
        (conversation_id, chat_id, client_ref)، بنرجّع الـ id بتاعه من غير أي كتابة —
        فإعادة إرسال نفس العملية (double-tap / إعادة محاولة بعد انقطاع الرد) ما بتعملش
        برومت مكرّر.

        OHB2-AUDIT-FIX-01 (سباق إحياء الحذف): `reengage=True` معناه «المستخدم تفاعل صريح
        **دلوقتي**» — مش «عملية بدأت قبل الحذف وخلصت بعده». العملية اللي بتحمل `client_ref`
        (مصدرها الـ Mini App: الـ POST ممكن يخلص بعد الحذف بسبب await الشبكة) **عمرها ما
        تحيي** شات متشاهد: بنرفضها (نرجّع 0، بدون أي كتابة) من غير ما نشيل الشاهد. ده يمنع
        الـ POST المتأخّر (أو إعادة المحاولة/الضغط المزدوج) من إحياء شات اتحذف. العمليات من
        غير `client_ref` (مسار البوت) زي ما هي: الصريح (`reengage=True`) يشيل الشاهد، وغير
        الصريح يُرفض. الفحص كله جوه BEGIN IMMEDIATE ⇒ محصّن ضد حذف متزامن.

        P1 (OHB2-ONE-SHOT-CRASH): `consume_awaiting=(telegram_id, expected_kind)` بيخلّي
        **استهلاك حالة انتظار لمرة واحدة** (reply) يحصل **جوه نفس المعاملة** اللي بتكتب
        السجل الدائم. لو الحالة اتغيّرت/انتهت/مستهلكة، بنرجّع 0 من غير أي كتابة (ما
        نستهلكش حالة مش متوقّعة). لو العملية فشلت، الاتنين يتراجعوا معًا ⇒ مفيش نافذة فقد
        (الحالة تفضل قائمة فإعادة التسليم تنفّذ).
        """
        window = window if window is not None else GROUP_WINDOW
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            # P1 (إغلاق سباق التزامن): الحاجز في group=-1 فحص قراءة، فنداءين متزامنين لنفس
            # `update_id` ممكن يوصلوا هنا الاتنين. الفحص جوه قفل الكتابة (`BEGIN IMMEDIATE`)
            # بيخلّي التاني يشوف «معالَج» ويرجع 0 (مفيش ازدواج). التزامن مُسلسَل: التاني
            # بياخد القفل بعد ما الأول يـcommit.
            if update_id is not None and self.update_is_processed(update_id):
                conn.rollback()
                return 0
            if consume_awaiting is not None:
                # P1: استهلاك حالة الانتظار (لمرة واحدة) ذرّيًا مع كتابة السجل الدائم.
                tg_id, expected_kind = consume_awaiting
                arow = conn.execute(
                    "SELECT awaiting_kind, awaiting_at FROM user_state WHERE telegram_id=?",
                    (tg_id,),
                ).fetchone()
                if arow is None or arow["awaiting_kind"] != expected_kind:
                    conn.rollback()
                    return 0
                if self.awaiting_is_expired(_parse_iso(arow["awaiting_at"]), _parse_iso(now)):
                    self._clear_awaiting_nocommit(tg_id)
                    conn.commit()
                    return 0
            if self.is_deleted(conversation_id):
                # شات متشاهد: مفيش إحياء. عمليات `client_ref` (Mini App) مرفوضة دايمًا،
                # والعمليات من غير `client_ref` (البوت) لازم تكون صريحة (`reengage`).
                if client_ref or not reengage:
                    conn.rollback()
                    return 0
                self._clear_tombstone_nocommit(conversation_id)
            elif client_ref:
                existing = conn.execute(
                    "SELECT id FROM outbox "
                    "WHERE conversation_id=? AND chat_id=? AND client_ref=? "
                    "ORDER BY id DESC LIMIT 1",
                    (conversation_id, chat_id, client_ref),
                ).fetchone()
                if existing is not None:
                    # OHB2-MANUAL-POLLING-OUTCOME: سجل العمل الدائم موجود بالفعل (نفس
                    # client_ref) ⇒ النتيجة «مكتمل مكرّر» (دليل دائم موجود).
                    self._mark_processed_nocommit(
                        update_id, now, update_outcomes.DUPLICATE_COMPLETED
                    )
                    conn.commit()
                    return int(existing["id"])
            row = conn.execute(
                "SELECT id, text, updated_at, client_ref FROM outbox "
                "WHERE conversation_id=? AND chat_id=? AND status=? ORDER BY id DESC LIMIT 1",
                (conversation_id, chat_id, OUTBOX_PENDING),
            ).fetchone()
            now_dt = _parse_iso(now)
            row_dt = _parse_iso(row["updated_at"]) if row else None
            within = (
                row is not None
                and now_dt is not None
                and row_dt is not None
                and now_dt - row_dt <= window
            )
            # بنسمح بالتجميع مع صف لسه 'pending' لو مالوش معرّف عملية، أو معرّفه نفس
            # معرّفنا. لو الصف ليه معرّف تاني ⇒ ما ندمجش (نعمل صف مستقل) عشان
            # الـ idempotency بتاعة العملية التانية ما تتلغيش.
            mergeable = within and (
                not client_ref or row["client_ref"] in (None, client_ref)
            )
            if mergeable:
                merged = row["text"] + "\n" + text
                # نطبع معرّف العملية على الصف لو كان فاضي، عشان إعادة إرسال نفس
                # العملية تلاقيه وما تكرّرش.
                stamped = row["client_ref"] or client_ref
                conn.execute(
                    "UPDATE outbox SET text=?, updated_at=?, client_ref=? WHERE id=?",
                    (merged, now, stamped, row["id"]),
                )
                out_id = int(row["id"])
            else:
                cur = conn.execute(
                    "INSERT INTO outbox"
                    "(conversation_id, chat_id, text, status, created_at, updated_at, client_ref) "
                    "VALUES(?, ?, ?, ?, ?, ?, ?)",
                    (conversation_id, chat_id, text, OUTBOX_PENDING, now, now, client_ref),
                )
                out_id = int(cur.lastrowid)
            # P1: استهلاك حالة الانتظار (لمرة واحدة) **في نفس المعاملة** مع الكتابة الدائمة
            # (outbox/creation) وعلامة «معالَج» ⇒ إما الثلاثة يتحفظوا معًا أو ولا واحد.
            if consume_awaiting is not None:
                self._clear_awaiting_nocommit(consume_awaiting[0])
            # P1: تسجيل «معالَج» **في نفس معاملة** كتابة السجل الدائم ⇒ ذرّية حقيقية
            # (التسجيل والكتابة إما ينجحوا معًا أو يفشلوا معًا). مسارات Mini App:
            # `update_id` None ⇒ no-op (مفيش حاجز تحديث أصلًا).
            # OHB2-MANUAL-POLLING-OUTCOME: النية الدائمة اتكتبت (صف 'pending') ⇒ النتيجة
            # `durable_intent_recorded` (دليل إقرار دائم؛ التسليم الخارجي لسه معلّق).
            self._mark_processed_nocommit(
                update_id, now, update_outcomes.DURABLE_INTENT_RECORDED
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return out_id

    def find_outbox_by_ref(
        self, conversation_id: str, chat_id: int, client_ref: str
    ) -> OutboxItem | None:
        """أحدث سجل صندوق بنفس معرّف العملية (idempotency) أو None."""
        row = self._conn.execute(
            "SELECT * FROM outbox "
            "WHERE conversation_id=? AND chat_id=? AND client_ref=? ORDER BY id DESC LIMIT 1",
            (conversation_id, chat_id, client_ref),
        ).fetchone()
        return self._row_to_outbox(row) if row else None

    def set_outbox_status(
        self, outbox_id: int, status: str, now: str, error: str | None = None, bump: bool = False
    ) -> None:
        if bump:
            self._conn.execute(
                "UPDATE outbox SET status=?, error=?, updated_at=?, attempts=attempts+1 WHERE id=?",
                (status, error, now, outbox_id),
            )
        else:
            self._conn.execute(
                "UPDATE outbox SET status=?, error=?, updated_at=? WHERE id=?",
                (status, error, now, outbox_id),
            )
        self._conn.commit()

    def set_outbox_status_if_in(
        self,
        outbox_id: int,
        new_status: str,
        now: str,
        allowed_statuses,
        error: str | None = None,
    ) -> bool:
        """تحويل حالة **ذرّي مشروط** (compare-and-set) — OHB2-09-05.

        الـ UPDATE نفسه بيشيل شرط الحالة (`WHERE id=? AND status IN (...)`)، فالقرار
        والكتابة في جملة واحدة: لو سجل تاني سبقنا وغيّر الحالة، الـ rowcount هيساوي 0
        وما بيحصلش أي تغيير (مفيش سباق read-then-write). بترجّع True لو الحالة اتغيّرت
        فعلاً. `allowed_statuses` مجموعة/تسلسل حالات المصدر المسموحة.
        """
        allowed = tuple(allowed_statuses)
        if not allowed:
            return False
        placeholders = ", ".join("?" for _ in allowed)
        cur = self._conn.execute(
            f"UPDATE outbox SET status=?, error=?, updated_at=? "
            f"WHERE id=? AND status IN ({placeholders})",
            (new_status, error, now, outbox_id, *allowed),
        )
        changed = cur.rowcount == 1
        self._conn.commit()
        return changed

    def bump_outbox_attempt(self, outbox_id: int, now: str, error: str | None = None) -> int:
        """يزوّد attempts ذرّياً من غير ما يغيّر الحالة، ويرجّع العدّاد الجديد (0 لو مش 'claimed').

        الـ UPDATE والقراءة في جملة واحدة (RETURNING)، فالقيمة الراجعة هي العدّاد الفعلي
        بعد الزيادة — حتى لو أكتر من caller نادوها. ده بيخلّي قرار "وصلنا الحد؟" مبني على
        عدّاد حقيقي مش على snapshot قديم، فمستحيل يتخطّى الحد أو يتكرّر الإشعار النهائي.

        OHB2-N10-28C: (1) ما بنغيّرش الحالة (مفيش رجوع ضمني لـ 'pending' — الحالة بتتظبط
        بنداء CAS صريح من الـ caller). (2) الشرط `status=claimed` بيمنع الـ worker من
        "إحياء" سجل المستخدم شطبه (أو حسمه) بين الحجز والـ POST — لو مش 'claimed'،
        rowcount=0 وبنرجّع 0 (مفيش لمس، ومفيش إعادة إرسال).
        """
        row = self._conn.execute(
            "UPDATE outbox SET error=?, updated_at=?, attempts=attempts+1 "
            "WHERE id=? AND status=? RETURNING attempts",
            (error, now, outbox_id, OUTBOX_CLAIMED),
        ).fetchone()
        self._conn.commit()
        return int(row["attempts"]) if row else 0

    def claim_outbox(self, now: str, mature_before: str | None = None) -> OutboxItem | None:
        """ياخد ذرّياً أقدم عنصر 'pending' ويحوّله 'claimed' (atomic claim).

        الـ SELECT والـ UPDATE في جملة واحدة، فمفيش سباق بين اتنين workers/iterations.
        بترجّع العنصر (بحالته بعد الحجز) أو None لو مفيش 'pending'. 'claimed' مش
        مؤهّل، فمستحيل ناخد نفس السجل مرتين. الـ 'claimed' معناه ملكية ولسه POST
        مابدأش ⇒ لو العملية اتقطعت هنا يتعافى 'pending' (آمن). الـ 'sending' بيتسجّل
        بثبات قبل الـ POST مباشرة (شوف outbox._post_claimed).

        لو `mature_before` اتحدّد، بنحجز بس السجلات اللي updated_at <= mature_before
        (نافذة تجميع القرار 2: نسيب الدفعة تستقر قبل الإرسال). القيمة None بتحافظ على
        السلوك القديم (أي 'pending').
        """
        if mature_before is None:
            sql = (
                "UPDATE outbox SET status=?, updated_at=? "
                "WHERE id=(SELECT id FROM outbox WHERE status=? ORDER BY id LIMIT 1) "
                "RETURNING *"
            )
            params = (OUTBOX_CLAIMED, now, OUTBOX_PENDING)
        else:
            sql = (
                "UPDATE outbox SET status=?, updated_at=? "
                "WHERE id=(SELECT id FROM outbox WHERE status=? AND updated_at<=? ORDER BY id LIMIT 1) "
                "RETURNING *"
            )
            params = (OUTBOX_CLAIMED, now, OUTBOX_PENDING, mature_before)
        row = self._conn.execute(sql, params).fetchone()
        self._conn.commit()
        return self._row_to_outbox(row) if row else None

    def seconds_until_mature(self, now: str, window: timedelta) -> float | None:
        """كم ثانية فاضلة لحد ما أقدم عنصر 'pending' يستوفي نافذة التجميع؟

        None لو مفيش 'pending' خالص. 0.0 لو أقدم عنصر مستوفي بالفعل (جاهز للحجز).
        """
        return self._seconds_until_mature(_parse_iso(now), window)

    def seconds_until_mature_at(self, now_dt: datetime, window: timedelta) -> float | None:
        """زي `seconds_until_mature` بس بياخد datetime محسوب مقدماً (قراءة ساعة واحدة).

        بنستخدمه في worker التجميع: نفس الطابع الزمني بيتحسب مرة واحدة وبيتمرّر هنا
        وبيتحجز بيه، فمفيش قراءتين للساعة ممكن يخلّوا التأخير غير متّسق مع حدّ النضج.
        """
        return self._seconds_until_mature(now_dt, window)

    def _seconds_until_mature(self, now_dt: datetime | None, window: timedelta) -> float | None:
        row = self._conn.execute(
            "SELECT updated_at FROM outbox WHERE status=? ORDER BY updated_at LIMIT 1",
            (OUTBOX_PENDING,),
        ).fetchone()
        if row is None:
            return None
        row_dt = _parse_iso(row["updated_at"])
        if now_dt is None or row_dt is None:
            return 0.0
        return max(0.0, (row_dt + window - now_dt).total_seconds())

    def oldest_pending_id(self) -> int | None:
        """أقدم عنصر 'pending' (للجدولة الفورية من الـ handlers) أو None."""
        row = self._conn.execute(
            "SELECT id FROM outbox WHERE status=? ORDER BY id LIMIT 1", (OUTBOX_PENDING,)
        ).fetchone()
        return int(row["id"]) if row else None

    def get_outbox(self, outbox_id: int, chat_id: int | None = None) -> OutboxItem | None:
        """يجيب سجل صندوق بالمعرّف.

        OHB2-PHASE1D: `chat_id` اختياري لفرض **ملكية** الصف (نطاق المالك). الـ Mini App
        بيمرّره دايمًا؛ المسارات الداخلية (البوت/الـ workers) بتستدعيها من غير نطاق.
        """
        if chat_id is None:
            row = self._conn.execute("SELECT * FROM outbox WHERE id=?", (outbox_id,)).fetchone()
        else:
            row = self._conn.execute(
                "SELECT * FROM outbox WHERE id=? AND chat_id=?", (outbox_id, int(chat_id))
            ).fetchone()
        return self._row_to_outbox(row) if row else None

    def list_outbox_by_status(self, status: str) -> list[OutboxItem]:
        rows = self._conn.execute(
            "SELECT * FROM outbox WHERE status=? ORDER BY id", (status,)
        ).fetchall()
        return [self._row_to_outbox(r) for r in rows]

    def list_open_outbox(self) -> list[OutboxItem]:
        """كل البرومتات غير المنتهية (pending/claimed/sending) — للعرض والعدّ."""
        rows = self._conn.execute(
            "SELECT * FROM outbox WHERE status IN (?, ?, ?) ORDER BY id",
            (OUTBOX_PENDING, OUTBOX_CLAIMED, OUTBOX_SENDING),
        ).fetchall()
        return [self._row_to_outbox(r) for r in rows]

    def count_outbox(self, status: str | None = None) -> int:
        if status is None:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM outbox").fetchone()
        else:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM outbox WHERE status=?", (status,)
            ).fetchone()
        return int(row["n"])

    @staticmethod
    def _row_to_outbox(row: sqlite3.Row) -> OutboxItem:
        return OutboxItem(
            id=row["id"],
            conversation_id=row["conversation_id"],
            chat_id=row["chat_id"],
            text=row["text"],
            status=row["status"],
            error=row["error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            attempts=row["attempts"],
            client_ref=row["client_ref"],
            notify_state=row["notify_state"],
        )

    # ----------------------------------------------------------- creation jobs
    def add_creation_job(
        self,
        chat_id: int,
        repo: str | None,
        text: str,
        now: str,
        client_ref: str | None = None,
        update_id: int | None = None,
        consume_awaiting: tuple[int, str] | None = None,
    ) -> int:
        """يسجّل طلب شات جديد (status='pending') قبل أي POST بدء (مفيش conversation_id).

        OHB2-07 (idempotency): لو `client_ref` اتزوّد وفيه طلب موجود بنفس
        (chat_id, client_ref)، بنرجّع الـ id بتاعه من غير إنشاء طلب جديد — فإعادة
        المحاولة بعد انقطاع الرد ما بتبدأش شات تاني.

        OHB2-PHASE1D-F4: الحماية دي للحالات **النشطة** بس. لو الصف الموجود خلص **من غير
        شات بعيد** (failed/discarded)، إرسال جديد بنفس المعرّف = محاولة إنشاء **جديدة**،
        فبنعمل صف جديد (وإلا طلب ملغي كان بيسدّ نفس (مستودع+نص) للأبد).
        **مهم:** `done` **مش** ضمن دول — لو الرد ضاع بعد نجاح الإنشاء والعميل أعاد
        نفس المعرّف، لازم نرجّع نفس الصف (مفيش شات مكرّر). ops.js بيعمل معرّف جديد بعد
        `done` فمفيش إعادة استخدام في المسار العادي.

        P1 (OHB2-ONE-SHOT-CRASH): `consume_awaiting=(telegram_id, expected_kind)` بخلّي
        استهلاك حالة انتظار لمرة واحدة (newchat) ذرّيًا مع كتابة الطلب الدائم.
        """
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            # P1 (إغلاق سباق التزامن): نفس منطق `add_or_group_outbox` — الفحص جوه قفل
            # الكتابة يمنع إنشاء شات مكرّر لو نفس التحديث وصل مرتين متزامنتين.
            if update_id is not None and self.update_is_processed(update_id):
                conn.rollback()
                return 0
            if consume_awaiting is not None:
                # P1: استهلاك حالة الانتظار (لمرة واحدة) ذرّيًا مع كتابة الطلب الدائم.
                tg_id, expected_kind = consume_awaiting
                arow = conn.execute(
                    "SELECT awaiting_kind, awaiting_at FROM user_state WHERE telegram_id=?",
                    (tg_id,),
                ).fetchone()
                if arow is None or arow["awaiting_kind"] != expected_kind:
                    conn.rollback()
                    return 0
                if self.awaiting_is_expired(_parse_iso(arow["awaiting_at"]), _parse_iso(now)):
                    self._clear_awaiting_nocommit(tg_id)
                    conn.commit()
                    return 0
            if client_ref:
                existing = conn.execute(
                    "SELECT id, status FROM creation_jobs WHERE chat_id=? AND client_ref=? "
                    "ORDER BY id DESC LIMIT 1",
                    (chat_id, client_ref),
                ).fetchone()
                if existing is not None and existing["status"] not in (
                    CREATION_FAILED,
                    CREATION_DISCARDED,
                ):
                    # OHB2-MANUAL-POLLING-OUTCOME: طلب الإنشاء الدائم موجود (نفس client_ref)
                    # ⇒ «مكتمل مكرّر» (دليل دائم).
                    self._mark_processed_nocommit(
                        update_id, now, update_outcomes.DUPLICATE_COMPLETED
                    )
                    conn.commit()
                    return int(existing["id"])
            cur = conn.execute(
                "INSERT INTO creation_jobs(chat_id, repo, text, status, created_at, updated_at, client_ref) "
                "VALUES(?, ?, ?, ?, ?, ?, ?)",
                (chat_id, repo, text, CREATION_PENDING, now, now, client_ref),
            )
            # P1: استهلاك حالة الانتظار (لمرة واحدة) **في نفس المعاملة** مع الكتابة الدائمة
            # (outbox/creation) وعلامة «معالَج» ⇒ إما الثلاثة يتحفظوا معًا أو ولا واحد.
            if consume_awaiting is not None:
                self._clear_awaiting_nocommit(consume_awaiting[0])
            # P1: تسجيل «معالَج» **في نفس معاملة** كتابة السجل الدائم ⇒ ذرّية حقيقية.
            # OHB2-MANUAL-POLLING-OUTCOME: طلب الإنشاء الدائم اتكتب (صف 'pending') ⇒
            # `durable_intent_recorded` (دليل إقرار دائم).
            self._mark_processed_nocommit(
                update_id, now, update_outcomes.DURABLE_INTENT_RECORDED
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return int(cur.lastrowid)

    def find_creation_job_by_ref(self, chat_id: int, client_ref: str) -> CreationJob | None:
        """أحدث طلب شات جديد بنفس معرّف العملية (idempotency) أو None."""
        row = self._conn.execute(
            "SELECT * FROM creation_jobs WHERE chat_id=? AND client_ref=? ORDER BY id DESC LIMIT 1",
            (chat_id, client_ref),
        ).fetchone()
        return self._row_to_creation(row) if row else None

    def get_creation_job(self, job_id: int, chat_id: int | None = None) -> CreationJob | None:
        """يجيب طلب شات جديد بالمعرّف.

        OHB2-PHASE1D: `chat_id` اختياري لفرض **ملكية** الصف (نطاق المالك). الـ Mini App
        بيمرّره دايمًا؛ المسارات الداخلية بتستدعيها من غير نطاق.
        """
        if chat_id is None:
            row = self._conn.execute(
                "SELECT * FROM creation_jobs WHERE id=?", (job_id,)
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT * FROM creation_jobs WHERE id=? AND chat_id=?", (job_id, int(chat_id))
            ).fetchone()
        return self._row_to_creation(row) if row else None

    def list_creation_jobs_for_owner(
        self, chat_id: int, page: int = 0, page_size: int = 10
    ) -> tuple[list[CreationJob], bool]:
        """قايمة طلبات الشات الجديد **المملوكة** لـ `chat_id` (الأحدث أولاً) + has_more.

        OHB2-PHASE1D: نطاق المالك مفروض في الاستعلام نفسه، والترتيب ثابت
        (created_at DESC, id DESC) والترقيم بـ offset — نفس دلالات قايمة الشاتات.

        AUD-04 (دفاع في العمق): رقم الصفحة لازم يكون عددًا صحيحًا داخل [0, MAX_PAGE]
        قبل حساب `offset = page × size`، عشان القيم الكبيرة ما تعملش OverflowError
        جوّه SQLite. رفض القيمة هنا آخر خط دفاع؛ طبقة الـ API بترفضها بـ 400 قبل كده.
        """
        page = int(page)
        if page < 0 or page > MAX_PAGE:
            raise ValueError("رقم الصفحة خارج النطاق المسموح")
        size = int(page_size)
        # `size + 1` (جلب عنصر زيادة لمعرفة has_more) لازم يفضل داخل نطاق SQLite.
        if size < 1 or size >= MAX_SQLITE_INT:
            raise ValueError("حجم الصفحة خارج النطاق المسموح")
        offset = page * size
        if offset > MAX_SQLITE_INT:
            raise ValueError("إزاحة الصفحة خارج نطاق SQLite")
        rows = self._conn.execute(
            "SELECT * FROM creation_jobs WHERE chat_id=? "
            "AND NOT EXISTS (SELECT 1 FROM deleted_conversations d "
            "WHERE d.conversation_id = creation_jobs.conversation_id) "
            "ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            (int(chat_id), size + 1, offset),
        ).fetchall()
        has_more = len(rows) > size
        jobs = [self._row_to_creation(r) for r in rows[:size]]
        return jobs, has_more

    def list_creation_jobs_by_status(self, status: str) -> list[CreationJob]:
        rows = self._conn.execute(
            "SELECT * FROM creation_jobs WHERE status=? ORDER BY id", (status,)
        ).fetchall()
        return [self._row_to_creation(r) for r in rows]

    def list_open_creation_jobs(self) -> list[CreationJob]:
        """كل الطلبات غير المنتهية (pending/claimed/starting) — للعرض والعدّ."""
        rows = self._conn.execute(
            "SELECT * FROM creation_jobs WHERE status IN (?, ?, ?) ORDER BY id",
            (CREATION_PENDING, CREATION_CLAIMED, CREATION_STARTING),
        ).fetchall()
        return [self._row_to_creation(r) for r in rows]

    def count_creation_jobs(self, status: str | None = None) -> int:
        if status is None:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM creation_jobs").fetchone()
        else:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM creation_jobs WHERE status=?", (status,)
            ).fetchone()
        return int(row["n"])

    def claim_creation_job(self, now: str) -> CreationJob | None:
        """حجز ذرّي لأقدم طلب شات جديد 'pending' ⇒ 'claimed' (جملة واحدة)."""
        row = self._conn.execute(
            "UPDATE creation_jobs SET status=?, updated_at=? "
            "WHERE id=(SELECT id FROM creation_jobs WHERE status=? ORDER BY id LIMIT 1) "
            "RETURNING *",
            (CREATION_CLAIMED, now, CREATION_PENDING),
        ).fetchone()
        self._conn.commit()
        return self._row_to_creation(row) if row else None

    def oldest_pending_creation_id(self) -> int | None:
        row = self._conn.execute(
            "SELECT id FROM creation_jobs WHERE status=? ORDER BY id LIMIT 1", (CREATION_PENDING,)
        ).fetchone()
        return int(row["id"]) if row else None

    def set_creation_status(
        self, job_id: int, status: str, now: str, error: str | None = None, bump: bool = False
    ) -> None:
        if bump:
            self._conn.execute(
                "UPDATE creation_jobs SET status=?, error=?, updated_at=?, attempts=attempts+1 "
                "WHERE id=?",
                (status, error, now, job_id),
            )
        else:
            self._conn.execute(
                "UPDATE creation_jobs SET status=?, error=?, updated_at=? WHERE id=?",
                (status, error, now, job_id),
            )
        self._conn.commit()

    def set_creation_status_if_in(
        self,
        job_id: int,
        new_status: str,
        now: str,
        allowed_statuses,
        error: str | None = None,
        chat_id: int | None = None,
    ) -> bool:
        """تحويل حالة طلب شات **ذرّي مشروط** (CAS) — نظير `set_outbox_status_if_in`.

        القرار والكتابة في جملة SQL واحدة؛ لو سبقنا كاتب تاني، الـ rowcount=0 ومفيش
        تغيير. بترجّع True لو الحالة اتغيّرت فعلاً.

        OHB2-PHASE1D: `chat_id` اختياري لفرض **ملكية** الصف في الـ UPDATE (دفاع في العمق).
        المسارات الداخلية (البوت/الـ workers) بتستدعيها من غير نطاق؛ الـ Mini App بيمرّره.
        """
        allowed = tuple(allowed_statuses)
        if not allowed:
            return False
        placeholders = ", ".join("?" for _ in allowed)
        if chat_id is None:
            cur = self._conn.execute(
                f"UPDATE creation_jobs SET status=?, error=?, updated_at=? "
                f"WHERE id=? AND status IN ({placeholders})",
                (new_status, error, now, job_id, *allowed),
            )
        else:
            cur = self._conn.execute(
                f"UPDATE creation_jobs SET status=?, error=?, updated_at=? "
                f"WHERE id=? AND chat_id=? AND status IN ({placeholders})",
                (new_status, error, now, job_id, int(chat_id), *allowed),
            )
        changed = cur.rowcount == 1
        self._conn.commit()
        return changed

    def set_creation_starting(
        self, job_id: int, now: str, task_id: str | None = None
    ) -> None:
        """يسجّل 'starting' فوراً قبل POST البدء. الـ task_id يتسجّل بس لو الـ API رجّعه.

        (setter منخفض المستوى — بيسجّل الحالة بغضّ النظر عن الحالة الحالية. الحماية
        الذرّية لحدّ الإلغاء بتحصل في `claim_creation_starting` اللي الـ worker بيستخدمه.)
        """
        if task_id:
            self._conn.execute(
                "UPDATE creation_jobs SET status=?, task_id=?, updated_at=? WHERE id=?",
                (CREATION_STARTING, task_id, now, job_id),
            )
        else:
            self._conn.execute(
                "UPDATE creation_jobs SET status=?, updated_at=? WHERE id=?",
                (CREATION_STARTING, now, job_id),
            )
        self._conn.commit()

    def claim_creation_starting(
        self, job_id: int, now: str, task_id: str | None = None
    ) -> bool:
        """CAS: (pending/claimed) ⇒ 'starting' (مع task_id لو مُتاح). بترجّع True لو نجح.

        OHB2-N10-28C: الشرط على حالة غير منتهية وقبل الإرسال (`pending`/`claimed`) — لو
        المستخدم شطب الطلب بين الحجز والـ POST، الـ rowcount=0 وبنرجّع False عشان الـ caller
        ما يبعتش الـ POST أصلاً (الشطب قبل الإرسال الفعلي بيوقف الإرسال، at-most-once).
        `pending` مسموح عشان المسار المباشر المتزامن (الاختبارات) بيسجّل ثم يبدأ فوراً.
        """
        if task_id:
            cur = self._conn.execute(
                "UPDATE creation_jobs SET status=?, task_id=?, updated_at=? "
                "WHERE id=? AND status IN (?, ?)",
                (CREATION_STARTING, task_id, now, job_id, CREATION_PENDING, CREATION_CLAIMED),
            )
        else:
            cur = self._conn.execute(
                "UPDATE creation_jobs SET status=?, updated_at=? WHERE id=? AND status IN (?, ?)",
                (CREATION_STARTING, now, job_id, CREATION_PENDING, CREATION_CLAIMED),
            )
        changed = cur.rowcount == 1
        self._conn.commit()
        return changed

    def set_creation_done(self, job_id: int, now: str, conversation_id: str) -> None:
        self._conn.execute(
            "UPDATE creation_jobs SET status=?, conversation_id=?, updated_at=? WHERE id=?",
            (CREATION_DONE, conversation_id, now, job_id),
        )
        self._conn.commit()

    def finish_creation_done(self, job_id: int, now: str, conversation_id: str) -> bool:
        """CAS: (claimed/starting) ⇒ 'done' مع معرّف المحادثة. بترجّع True لو نجح.

        OHB2-N10-28C: CAS على حالة غير نهائية — لو المستخدم شطب الطلب (أو حسمه) أثناء
        الاستطلاع، الـ rowcount=0 (مفيش clobber) وبنرجّع False (مفيش نجاح وهمي).
        """
        cur = self._conn.execute(
            "UPDATE creation_jobs SET status=?, conversation_id=?, updated_at=? "
            "WHERE id=? AND status IN (?, ?)",
            (CREATION_DONE, conversation_id, now, job_id, CREATION_CLAIMED, CREATION_STARTING),
        )
        changed = cur.rowcount == 1
        self._conn.commit()
        return changed

    def discard_outbox(self, outbox_id: int, now: str, reason: str | None = None) -> str:
        """شطب ذرّي لسجل صندوق مع تمييز حدّ الإلغاء (C2).

        بترجّع:
        - `"discarded"`   : كان مؤهّل قبل الإرسال (pending/claimed) واتشطب فوراً.
        - `"not_confirmed"`: الـ POST ممكن يكون بدأ (sending/unknown) ⇒ **مفيش** شطب
          ولا ادّعاء إلغاء؛ الحالة تفضل زي ما هي والـ caller يبلّغ إن الإلغاء غير مؤكد.
        - `"terminal"`    : خلاص في حالة نهائية (sent/failed/discarded) ⇒ مفيش تغيير.
        """
        cur = self._conn.execute(
            "UPDATE outbox SET status=?, error=?, updated_at=? WHERE id=? AND status IN (?, ?)",
            (OUTBOX_DISCARDED, reason, now, outbox_id, OUTBOX_PENDING, OUTBOX_CLAIMED),
        )
        if cur.rowcount == 1:
            self._conn.commit()
            return "discarded"
        row = self._conn.execute("SELECT status FROM outbox WHERE id=?", (outbox_id,)).fetchone()
        self._conn.commit()
        if row is None:
            return "terminal"
        if row["status"] in (OUTBOX_SENDING, OUTBOX_UNKNOWN):
            return "not_confirmed"
        return "terminal"

    def discard_creation_job(
        self, job_id: int, now: str, reason: str | None = None, chat_id: int | None = None
    ) -> str:
        """شطب ذرّي لطلب شات مع تمييز حدّ الإلغاء — نفس دلالات `discard_outbox`.

        OHB2-PHASE1D: `chat_id` اختياري لفرض **ملكية** الصف في الـ UPDATE والقراءة
        اللاحقة (دفاع في العمق). المسارات الداخلية (البوت/الـ workers) بتستدعيها من غير
        نطاق؛ الـ Mini App بيمرّره دايمًا بعد فحص الملكية في الخدمة.
        """
        if chat_id is None:
            cur = self._conn.execute(
                "UPDATE creation_jobs SET status=?, error=?, updated_at=? "
                "WHERE id=? AND status IN (?, ?) AND task_id IS NULL",
                (CREATION_DISCARDED, reason, now, job_id, CREATION_PENDING, CREATION_CLAIMED),
            )
        else:
            cur = self._conn.execute(
                "UPDATE creation_jobs SET status=?, error=?, updated_at=? "
                "WHERE id=? AND chat_id=? AND status IN (?, ?) AND task_id IS NULL",
                (
                    CREATION_DISCARDED,
                    reason,
                    now,
                    job_id,
                    int(chat_id),
                    CREATION_PENDING,
                    CREATION_CLAIMED,
                ),
            )
        if cur.rowcount == 1:
            self._conn.commit()
            return "discarded"
        if chat_id is None:
            row = self._conn.execute(
                "SELECT status, task_id FROM creation_jobs WHERE id=?", (job_id,)
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT status, task_id FROM creation_jobs WHERE id=? AND chat_id=?",
                (job_id, int(chat_id)),
            ).fetchone()
        self._conn.commit()
        if row is None:
            return "terminal"
        if row["status"] in (CREATION_STARTING, CREATION_UNKNOWN):
            return "not_confirmed"
        # OHB2-PHASE1D-F1: `pending`/`claimed` بس عليه `task_id` ⇒ الـ POST البدء رجع
        # فعلاً ⇒ الإلغاء غير مؤكد (مفيش شطب). حرس دفاع في العمق لكل المستدعين.
        if row["status"] in (CREATION_PENDING, CREATION_CLAIMED) and row["task_id"]:
            return "not_confirmed"
        return "terminal"


    @staticmethod
    def _row_to_creation(row: sqlite3.Row) -> CreationJob:
        return CreationJob(
            id=row["id"],
            chat_id=row["chat_id"],
            repo=row["repo"],
            text=row["text"],
            status=row["status"],
            task_id=row["task_id"],
            conversation_id=row["conversation_id"],
            error=row["error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            attempts=row["attempts"],
            client_ref=row["client_ref"],
            notify_state=row["notify_state"],
        )

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------- completion (local effects) F02
    def _upsert_completion_pending_nocommit(
        self,
        ref_kind: str,
        ref_id: int,
        chat_id: int,
        conversation_id: str,
        now: str,
        title: str = "",
        last_state: str | None = None,
        submitted_at: str | None = None,
        notice_text: str = "",
    ) -> None:
        """كتابة intent الإكمال المحلي **بدون commit** (يستخدمها المستدعي في معاملته).

        idempotent: نفس (ref_kind, ref_id) ⇒ تحديث البيانات الوصفية بس، مع **الحفاظ** على
        حالة الجدولة/الاستنفاد (attempts/failures/next_attempt_at/exhausted) — إعادة
        التسجيل مش محاولة جديدة ولا بتصفّر تعافي معلّق.

        OHB2-C7 (RESURRECTION-FIX): لو الشات عليه شاهد حذف دائم ⇒ **مايتعملش intent إكمال**
        (لا إدراج ولا تحديث). ده نقطة الحماية المركزية: `complete_outbox_sent`/
        `complete_creation_done` بيفضلوا يثبّتوا الحالة النهائية للـ POST الناجح (خارجيًا
        تم فعلًا) بس **ما بيخلقوش عمل إكمال محلي** لشات محذوف ⇒ مفيش إحياء ولا إشعار قديم.
        الفحص جوه معاملة المستدعي (BEGIN IMMEDIATE) ⇒ محصّن ضد حذف متزامن.
        """
        if self.is_deleted(conversation_id):
            return
        self._conn.execute(
            "INSERT INTO completion_pending"
            "(ref_kind, ref_id, chat_id, conversation_id, title, last_state, submitted_at,"
            " notice_text, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(ref_kind, ref_id) DO UPDATE SET "
            "chat_id=excluded.chat_id, conversation_id=excluded.conversation_id, "
            "title=excluded.title, last_state=excluded.last_state, "
            "submitted_at=excluded.submitted_at, notice_text=excluded.notice_text, "
            "updated_at=excluded.updated_at",
            (
                ref_kind, ref_id, chat_id, conversation_id, title, last_state,
                submitted_at, notice_text, now, now,
            ),
        )

    def add_completion_pending(
        self,
        ref_kind: str,
        ref_id: int,
        chat_id: int,
        conversation_id: str,
        now: str,
        title: str = "",
        last_state: str | None = None,
        submitted_at: str | None = None,
        notice_text: str = "",
    ) -> None:
        """يسجّل عمل إكمال محلي معلّق (write-ahead، idempotent).

        مسار مستقل (مش جزء من انتقال الحالة الذرّي) — بيتستخدم للتعافي/الاختبارات. المسار
        الإنتاجي للانتقال النهائي بيستخدم `complete_outbox_sent`/`complete_creation_done`
        (انتقال + intent في معاملة واحدة).
        """
        self._upsert_completion_pending_nocommit(
            ref_kind, ref_id, chat_id, conversation_id, now,
            title=title, last_state=last_state, submitted_at=submitted_at,
            notice_text=notice_text,
        )
        self._conn.commit()

    def complete_outbox_sent(
        self,
        outbox_id: int,
        now: str,
        *,
        chat_id: int,
        conversation_id: str,
        title: str = "",
        last_state: str | None = None,
        submitted_at: str | None = None,
        notice_text: str = "",
    ) -> bool:
        """OHB2-STABILIZATION-F02: انتقال `sending`⇒`sent` **و** تسجيل intent الإكمال
        المحلي في **معاملة ذرّية واحدة** (BEGIN IMMEDIATE). يا الاتنين يثبتوا أو ولا واحد.

        ده بيقفل فجوة الـ crash: مستحيل يبقى فيه صف `sent` من غير intent إكمال محفوظ.
        لو الـ CAS فشل (حالة أحدث حسمت السجل) بنرجّع False من غير أي كتابة (مفيش نجاح وهمي).
        """
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            cur = conn.execute(
                "UPDATE outbox SET status=?, error=?, updated_at=? "
                "WHERE id=? AND status=?",
                (OUTBOX_SENT, None, now, outbox_id, OUTBOX_SENDING),
            )
            if cur.rowcount != 1:
                conn.rollback()
                return False
            self._upsert_completion_pending_nocommit(
                COMPLETION_KIND_OUTBOX, outbox_id, chat_id, conversation_id, now,
                title=title, last_state=last_state, submitted_at=submitted_at,
                notice_text=notice_text,
            )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise

    def complete_creation_done(
        self,
        job_id: int,
        now: str,
        conversation_id: str,
        *,
        chat_id: int,
        title: str = "",
        last_state: str | None = "running",
        notice_text: str = "",
    ) -> bool:
        """OHB2-STABILIZATION-F02: انتقال طلب الشات (claimed/starting)⇒`done` **و** تسجيل
        intent الإكمال المحلي في **معاملة ذرّية واحدة**. نفس ضمان `complete_outbox_sent`.

        بيرجّع False لو الـ CAS فشل (المستخدم شطب الطلب أو حسمه) — مفيش clobber ولا نجاح وهمي.
        """
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            cur = conn.execute(
                "UPDATE creation_jobs SET status=?, conversation_id=?, updated_at=? "
                "WHERE id=? AND status IN (?, ?)",
                (CREATION_DONE, conversation_id, now, job_id, CREATION_CLAIMED, CREATION_STARTING),
            )
            if cur.rowcount != 1:
                conn.rollback()
                return False
            self._upsert_completion_pending_nocommit(
                COMPLETION_KIND_CREATION, job_id, chat_id, conversation_id, now,
                title=title, last_state=last_state, notice_text=notice_text,
            )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise

    def get_completion_pending(self, ref_kind: str, ref_id: int) -> CompletionPending | None:
        row = self._conn.execute(
            "SELECT * FROM completion_pending WHERE ref_kind=? AND ref_id=?",
            (ref_kind, ref_id),
        ).fetchone()
        return self._row_to_completion(row) if row else None

    def list_completion_pending(self) -> list[CompletionPending]:
        rows = self._conn.execute(
            "SELECT * FROM completion_pending ORDER BY created_at, ref_kind, ref_id"
        ).fetchall()
        return [self._row_to_completion(r) for r in rows]

    def claim_completion_due(self, now: str, lease_until: str) -> CompletionPending | None:
        """يحجز **ذرّياً** أقدم عنصر إكمال مؤهّل (غير مستنفد وموعد محاولته حان) وياخده.

        - `exhausted=1` **مستبعد** (مايفضلش يعطّل العناصر السليمة).
        - `next_attempt_at` في المستقبل ⇒ مؤجّل، مش مؤهّل (backoff دائم).
        - الحجز = كتابة `next_attempt_at=lease_until` (إجارة قصيرة) في نفس الجملة، فمستحيل
          اتنين worker/دورة ياخدوا نفس الصف (safe concurrent claiming). لو العملية وقعت
          قبل الإكمال، الإجارة بتنتهي والصف يرجع مؤهّل (تعافٍ آمن).
        بترجّع العنصر بعد الحجز أو None لو مفيش مؤهّل.
        """
        row = self._conn.execute(
            "UPDATE completion_pending SET next_attempt_at=? "
            "WHERE (ref_kind, ref_id) = ("
            "  SELECT ref_kind, ref_id FROM completion_pending "
            "  WHERE exhausted=0 AND (next_attempt_at IS NULL OR next_attempt_at <= ?) "
            "  ORDER BY COALESCE(next_attempt_at, created_at), created_at, ref_kind, ref_id "
            "  LIMIT 1) "
            "RETURNING *",
            (lease_until, now),
        ).fetchone()
        self._conn.commit()
        return self._row_to_completion(row) if row else None

    def bump_completion_attempt(
        self,
        ref_kind: str,
        ref_id: int,
        now: str,
        error: str | None = None,
        next_attempt_at: str | None = None,
        max_attempts: int | None = None,
    ) -> int:
        """يزوّد عدّاد المحاولات/الفشل، يجدول إعادة المحاولة، ويرجّع عدد المحاولات الجديد
        (0 لو الصف اتشال).

        لو `max_attempts` اتحدّد ووصلنا له ⇒ نعلّم الصف `exhausted=1` (حالة ظاهرة للمشغّل،
        مايتشالش). الفشل مش بيتحوّل لنجاح أبدًا.
        """
        row = self._conn.execute(
            "UPDATE completion_pending SET attempts=attempts+1, failures=failures+1, "
            "last_error=?, next_attempt_at=?, updated_at=?, "
            "exhausted=CASE WHEN ? IS NOT NULL AND attempts+1 >= ? THEN 1 ELSE exhausted END "
            "WHERE ref_kind=? AND ref_id=? RETURNING attempts",
            (error, next_attempt_at, now, max_attempts, max_attempts, ref_kind, ref_id),
        ).fetchone()
        self._conn.commit()
        return int(row["attempts"]) if row else 0

    def clear_completion_pending(self, ref_kind: str, ref_id: int) -> None:
        self._conn.execute(
            "DELETE FROM completion_pending WHERE ref_kind=? AND ref_id=?",
            (ref_kind, ref_id),
        )
        self._conn.commit()

    def rearm_completion_pending(self, ref_kind: str, ref_id: int, now: str) -> bool:
        """يعيد تأهيل عنصر مستنفد (يرجّعه مؤهّل للمحاولة) — تدخّل المشغّل الصريح.

        بيصفّر `exhausted` و`next_attempt_at` و`attempts` (محاولة جديدة) من غير أي عملية
        خارجية. بترجّع True لو فيه صف اتغيّر.
        """
        cur = self._conn.execute(
            "UPDATE completion_pending SET exhausted=0, next_attempt_at=NULL, attempts=0, "
            "last_error=NULL, updated_at=? WHERE ref_kind=? AND ref_id=?",
            (now, ref_kind, ref_id),
        )
        self._conn.commit()
        return cur.rowcount == 1

    def list_completion_exhausted(self) -> list[CompletionPending]:
        rows = self._conn.execute(
            "SELECT * FROM completion_pending WHERE exhausted=1 "
            "ORDER BY updated_at, ref_kind, ref_id"
        ).fetchall()
        return [self._row_to_completion(r) for r in rows]

    def count_completion_pending(self) -> int:
        """عدد أعمال الإكمال المحلي المعلّقة (لإعلان الحالة الصادقة عند عدم اليقين)."""
        row = self._conn.execute("SELECT COUNT(*) AS n FROM completion_pending").fetchone()
        return int(row["n"])

    def completion_stats(self, now: str) -> dict:
        """ملخّص حالة الإكمال المحلي (محدود، بلا محتوى حساس) للرصد/الجاهزية.

        بيرجّع: pending (الكل)، eligible (غير مستنفد وموعد محاولته حان)، deferred
        (غير مستنفد لكن مجدول لمستقبل)، exhausted (مطلوب تدخّل)، oldest_pending_at.
        """
        row = self._conn.execute(
            "SELECT "
            " COUNT(*) AS pending, "
            " SUM(CASE WHEN exhausted=0 AND (next_attempt_at IS NULL OR next_attempt_at <= ?)"
            "          THEN 1 ELSE 0 END) AS eligible, "
            " SUM(CASE WHEN exhausted=0 AND next_attempt_at IS NOT NULL AND next_attempt_at > ?"
            "          THEN 1 ELSE 0 END) AS deferred, "
            " SUM(CASE WHEN exhausted=1 THEN 1 ELSE 0 END) AS exhausted, "
            " MIN(created_at) AS oldest "
            "FROM completion_pending",
            (now, now),
        ).fetchone()
        return {
            "pending": int(row["pending"] or 0),
            "eligible": int(row["eligible"] or 0),
            "deferred": int(row["deferred"] or 0),
            "exhausted": int(row["exhausted"] or 0),
            "oldest_pending_at": row["oldest"],
        }

    def count_legacy_unresolved_completions(self) -> int:
        """عدد الصفوف القديمة اللي **مستحيل** نحدّد بأمان إن إكمالها المحلي ضاع.

        `outbox` في حالة `sent` أو `creation_jobs` في `done` من غير صف إكمال محفوظ.
        دول ممكن يكونوا (أ) اكتملوا فعلًا قبل الإصلاح الذرّي (الإكمال اتشال بعد النجاح)،
        أو (ب) وقعوا في نافذة الـ crash القديمة. **مفيش أي علامة دائمة تفرّق بينهم**، فبدل
        ما نخترع إشعارات مكرّرة لصفوف مكتملة، بنسيبهم ظاهرين للمشغّل (حالة غير محلولة
        صريحة) مع إمكانية تسوية يدوية لكل مرجع. **مافيش POST خارجي ولا اختلاق نجاح.**
        """
        row = self._conn.execute(
            "SELECT ("
            "  (SELECT COUNT(*) FROM outbox o "
            "     LEFT JOIN completion_pending c ON c.ref_kind=? AND c.ref_id=o.id "
            "   WHERE o.status=? AND c.ref_kind IS NULL "
            "     AND o.chat_id IS NOT NULL AND o.conversation_id IS NOT NULL "
            "     AND o.conversation_id != '' "
            "     AND o.conversation_id NOT IN (SELECT conversation_id FROM deleted_conversations)) + "
            "  (SELECT COUNT(*) FROM creation_jobs j "
            "     LEFT JOIN completion_pending c ON c.ref_kind=? AND c.ref_id=j.id "
            "   WHERE j.status=? AND c.ref_kind IS NULL "
            "     AND j.conversation_id IS NOT NULL AND j.chat_id IS NOT NULL "
            "     AND j.conversation_id NOT IN (SELECT conversation_id FROM deleted_conversations)) "
            ") AS n",
            (COMPLETION_KIND_OUTBOX, OUTBOX_SENT, COMPLETION_KIND_CREATION, CREATION_DONE),
        ).fetchone()
        return int(row["n"] or 0)

    def reconcile_legacy_completion(self, ref_kind: str, ref_id: int, now: str) -> bool:
        """تسوية **يدوية صريحة** لصف قديم واحد (تدخّل المشغّل): ينشئ intent إكمال محلي.

        بتشتغل بس على صف `sent`/`done` من غير intent موجود (وإلا False). بتشتقّ البيانات من
        الحقول الموجودة فعلًا (chat_id، conversation_id، title) — **مفيش POST خارجي**. بعد
        التسوية، الإكمال بيتنفّذ بأمان (idempotent). بترجّع True لو اتسوّى.
        """
        if ref_kind == COMPLETION_KIND_OUTBOX:
            row = self._conn.execute(
                "SELECT o.id, o.conversation_id, o.chat_id, o.updated_at, w.title "
                "FROM outbox o LEFT JOIN watched w ON w.conversation_id = o.conversation_id "
                "WHERE o.id=? AND o.status=? AND o.chat_id IS NOT NULL "
                "  AND o.conversation_id IS NOT NULL AND o.conversation_id != ''",
                (ref_id, OUTBOX_SENT),
            ).fetchone()
            if row is None:
                return False
            # OHB2-C7 (RESURRECTION-FIX): شات متشاهد حذف ⇒ مفيش تسوية (مفيش إحياء).
            if self.is_deleted(row["conversation_id"]):
                return False
            self._upsert_completion_pending_nocommit(
                COMPLETION_KIND_OUTBOX, int(row["id"]), int(row["chat_id"]),
                row["conversation_id"], now, title=row["title"] or "",
                last_state="", submitted_at=row["updated_at"], notice_text="",
            )
        elif ref_kind == COMPLETION_KIND_CREATION:
            row = self._conn.execute(
                "SELECT j.id, j.conversation_id, j.chat_id, j.repo FROM creation_jobs j "
                "WHERE j.id=? AND j.status=? AND j.conversation_id IS NOT NULL "
                "  AND j.chat_id IS NOT NULL",
                (ref_id, CREATION_DONE),
            ).fetchone()
            if row is None:
                return False
            # OHB2-C7 (RESURRECTION-FIX): شات متشاهد حذف ⇒ مفيش تسوية (مفيش إحياء).
            if self.is_deleted(row["conversation_id"]):
                return False
            self._upsert_completion_pending_nocommit(
                COMPLETION_KIND_CREATION, int(row["id"]), int(row["chat_id"]),
                row["conversation_id"], now, title=row["repo"] or "",
                last_state="running", notice_text="",
            )
        else:
            return False
        self._conn.commit()
        return True

    @staticmethod
    def _row_to_completion(row: sqlite3.Row) -> CompletionPending:
        return CompletionPending(
            ref_kind=row["ref_kind"],
            ref_id=row["ref_id"],
            chat_id=row["chat_id"],
            conversation_id=row["conversation_id"],
            title=row["title"] or "",
            last_state=row["last_state"],
            submitted_at=row["submitted_at"],
            notice_text=row["notice_text"] or "",
            attempts=row["attempts"],
            last_error=row["last_error"],
            next_attempt_at=row["next_attempt_at"],
            failures=row["failures"] if "failures" in row.keys() else 0,
            exhausted=row["exhausted"] if "exhausted" in row.keys() else 0,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # ------------------------------------------------------------- preferences
    # إعدادات عامة مفاتيح/قيم. منفصلة عن الأسرار (الأسرار متغيرات بيئة بس). تفضيل
    # الإشعارات الافتراضي «مفعّل» (الميزة شغّالة افتراضيًا)، وبيبقى موجود بعد إعادة التشغيل.
    NOTIFICATIONS_KEY = "notifications_enabled"
    # OHB2-MANUAL-POLLING-OUTCOME: مفتاح الحدّ المحلي للإقرار (مش إقرار تيليجرام).
    ACK_BOUNDARY_KEY = "acknowledgment_boundary"
    _TRUE_VALUES = frozenset({"1", "true", "yes", "on"})

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self._conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self._conn.commit()

    def get_notifications_enabled(self) -> bool:
        """تفضيل الإشعارات الاستباقية. الافتراضي True (مفعّل) لو المفتاح مش موجود."""
        raw = self.get_setting(self.NOTIFICATIONS_KEY)
        if raw is None:
            return True
        return raw.strip().lower() in self._TRUE_VALUES

    def set_notifications_enabled(self, enabled: bool) -> None:
        self.set_setting(self.NOTIFICATIONS_KEY, "1" if enabled else "0")

    def toggle_notifications_once(self, update_id: int | None, now: str) -> bool | None:
        """يبدّل تفضيل الإشعارات **مرة واحدة** لكل `update_id` (P3).

        التبديل وعلامة «معالَج» في **نفس المعاملة** ⇒ إعادة تسليم نفس التحديث
        (`update_id` متكرر) ما بتعكسش الحالة تاني. بترجّع:
        - True  : بقى **مفعّل** (تبديل ناجح من متوقف).
        - False : بقى **متوقف** (تبديل ناجح من مفعّل).
        - None  : مرفوض — نفس التحديث اتعالج قبل كده (مفيش تبديل تاني).

        `update_id` None (مسار غير تيليجرام/اختبار) ⇒ تبديل عادي بدون حاجز.
        """
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            if update_id is not None and self.update_is_processed(update_id):
                conn.rollback()
                return None
            row = conn.execute(
                "SELECT value FROM settings WHERE key=?", (self.NOTIFICATIONS_KEY,)
            ).fetchone()
            raw = row["value"] if row else None
            current = True if raw is None else raw.strip().lower() in self._TRUE_VALUES
            new_state = not current
            conn.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (self.NOTIFICATIONS_KEY, "1" if new_state else "0"),
            )
            # OHB2-MANUAL-POLLING-OUTCOME: التبديل الدائم اتـcommit ⇒ نتيجة مكتملة.
            self._mark_processed_nocommit(
                update_id, now, update_outcomes.DURABLE_COMPLETED
            )
            conn.commit()
            return new_state
        except Exception:
            conn.rollback()
            raise

    # ------------------------------------------------- notification snapshots
    # لقطة حالة كل محادثة (للمُبلّغ العام). `notified_status` = آخر حالة اتّبعت/اتخطّى
    # لها إشعار، وده اللي يمنع التكرار. منفصلة عن جدول watched (مفيش اقتران ضمني).
    _UNCHANGED = object()

    def has_notification_states(self) -> bool:
        """هل فيه أي لقطة إشعار مخزّنة؟ استعلام EXISTS خفيف بدل تحميل كل الصفوف."""
        row = self._conn.execute(
            "SELECT 1 FROM notification_state LIMIT 1"
        ).fetchone()
        return row is not None

    def list_notification_states(self) -> dict[str, NotificationState]:
        rows = self._conn.execute(
            "SELECT conversation_id, status, notified_status, retry_count, updated_at, "
            "transition_seq, discovered_status FROM notification_state"
        ).fetchall()
        return {
            r["conversation_id"]: NotificationState(
                r["conversation_id"], r["status"], r["notified_status"],
                r["retry_count"], r["updated_at"], r["transition_seq"],
                r["discovered_status"],
            )
            for r in rows
        }

    def get_notification_state(self, conversation_id: str) -> NotificationState | None:
        row = self._conn.execute(
            "SELECT conversation_id, status, notified_status, retry_count, updated_at, "
            "transition_seq, discovered_status FROM notification_state WHERE conversation_id=?",
            (conversation_id,),
        ).fetchone()
        if row is None:
            return None
        return NotificationState(
            row["conversation_id"], row["status"], row["notified_status"],
            row["retry_count"], row["updated_at"], row["transition_seq"],
            row["discovered_status"],
        )

    def upsert_notification_state(
        self,
        conversation_id: str,
        *,
        status=_UNCHANGED,
        notified_status=_UNCHANGED,
        retry_count=_UNCHANGED,
        updated_at: str | None = None,
        transition_seq=_UNCHANGED,
        discovered_status=_UNCHANGED,
        _commit: bool = True,
    ) -> None:
        """يحدّث لقطة محادثة واحدة بأعمدة ضيّقة (مفيش استبدال صف كامل ببيانات قديمة).

        بيبني `UPDATE` بالأعمدة المتمرّرة بس، فكاتب متزامن (زي المراقب بيسجّل إشعار
        نجح) مايتدهسش. الصف بيتعمل لو مش موجود (INSERT OR IGNORE)، وبعدها تحديث ضيّق.

        `_commit=False` بيخلي النداء ينضمّ لمعاملة المستدعي بدل ما يعمل commit خاص بيه
        (مستخدم في `remove_watched` عشان التسجيل والحذف يبقوا معاملة واحدة).
        """
        # OHB2-C7 (RESURRECTION-FIX): شات متشاهد حذف ⇒ ما نعملش/نحدّثش لقطة إشعار
        # (منع إشعار قديم عن شات ملغي). محصّن ضد حذف متزامن: الحذف بيكتب الشاهد داخل
        # BEGIN IMMEDIATE، والقراءة دي بتشوفه بمجرد الـ commit.
        if self.is_deleted(conversation_id):
            return
        self._conn.execute(
            "INSERT OR IGNORE INTO notification_state(conversation_id) VALUES(?)",
            (conversation_id,),
        )
        sets: list[str] = []
        params: list[object] = []
        if status is not self._UNCHANGED:
            sets.append("status=?")
            params.append(status)
        if notified_status is not self._UNCHANGED:
            sets.append("notified_status=?")
            params.append(notified_status)
        if retry_count is not self._UNCHANGED:
            sets.append("retry_count=?")
            params.append(retry_count)
        if transition_seq is not self._UNCHANGED:
            sets.append("transition_seq=?")
            params.append(transition_seq)
        if discovered_status is not self._UNCHANGED:
            sets.append("discovered_status=?")
            params.append(discovered_status)
        if updated_at is not None:
            sets.append("updated_at=?")
            params.append(updated_at)
        if sets:
            params.append(conversation_id)
            self._conn.execute(
                f"UPDATE notification_state SET {', '.join(sets)} WHERE conversation_id=?",
                params,
            )
        if _commit:
            self._conn.commit()

    def bump_notification_retry(self, conversation_id: str, now: str) -> int:
        """يزوّد عدّاد محاولات إشعار فاشلة ذرّياً ويرجّع القيمة الجديدة (جملة واحدة)."""
        row = self._conn.execute(
            "INSERT INTO notification_state(conversation_id, retry_count, updated_at) "
            "VALUES(?, 1, ?) "
            "ON CONFLICT(conversation_id) DO UPDATE SET "
            "retry_count=notification_state.retry_count+1, updated_at=excluded.updated_at "
            "RETURNING retry_count",
            (conversation_id, now),
        ).fetchone()
        self._conn.commit()
        return int(row["retry_count"]) if row else 0

    def note_transition(
        self, conversation_id: str, status: str, *, terminal: bool, now: str
    ) -> int:
        """OHB2-08-05 (Batch 3R-FIX2): يسجّل **اكتشاف** انتقال ويرجّع هويته الدائمة.

        الهوية (`transition_seq`) = «عصر اكتشاف» الانتقال:
        - انتقال حالة نهائية **جديد** (حالته مختلفة عن آخر حالة نهائية مُكتشَفة) ⇒ العدّاد
          يزيد مرة واحدة ويثبت خلال كل إعادات المحاولة لنفس الانتقال (idempotent).
        - إعادة استطلاع نفس الانتقال (نفس الحالة النهائية) ⇒ نفس الرقم (مفيش زيادة).
        - رؤية حالة **غير نهائية** ⇒ نقفل العصر الحالي (`discovered_status=NULL`) عشان
          الانتقال التالي لنفس الحالة النهائية ياخد رقمًا جديدًا (finished→running→finished).

        بيُحدّث `status` (الحالة المرصودة) دائمًا. `BEGIN IMMEDIATE` بيخلي التسلسل ذرّيًا
        بين العاملين. المراقب والمُبلّل بينادوا عليها ⇒ يشوفوا **نفس** الهوية لنفس الانتقال.
        """
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            # OHB2-C7 (RESURRECTION-FIX): مفيش إعادة إنشاء لقطة إشعار لشات متشاهد حذف
            # (سباق ممكن: المُبلّل قرأ لقطة قديمة قبل الحذف ثم نادى note_transition بعده).
            if self.is_deleted(conversation_id):
                conn.rollback()
                return 0
            row = conn.execute(
                "SELECT transition_seq, discovered_status FROM notification_state "
                "WHERE conversation_id=?",
                (conversation_id,),
            ).fetchone()
            seq = int(row["transition_seq"]) if row and row["transition_seq"] is not None else 0
            discovered = row["discovered_status"] if row else None
            if terminal:
                if discovered != status:
                    seq += 1
                    discovered = status
            else:
                # رؤية حالة غير نهائية = دورة حياة جديدة ⇒ نقفل العصر (الانتقال القادم
                # لنفس الحالة النهائية ياخد رقمًا جديدًا).
                discovered = None
            conn.execute(
                "INSERT INTO notification_state"
                "(conversation_id, transition_seq, discovered_status, status) "
                "VALUES(?,?,?,?) "
                "ON CONFLICT(conversation_id) DO UPDATE SET "
                "transition_seq=excluded.transition_seq, "
                "discovered_status=excluded.discovered_status, status=excluded.status",
                (conversation_id, seq, discovered, status),
            )
            conn.commit()
            return seq
        except Exception:
            conn.rollback()
            raise

    def record_notification_sent(
        self, conversation_id: str, status: str, now: str, *, _commit: bool = True
    ) -> None:
        """يسجّل إن إشعار الحالة ده اتبعت فعلًا (تليجرام أكّد النجاح).

        بيتنادى من أي مالك إشعار (المراقب أو المُبلّغ) بعد نجاح الإرسال بس، عشان المُبلّغ
        العام ما يعيدش إشعار نفس الحالة لو المتابعة اتشالت بعد ما المراقب بلّغ. النداء ده
        صريح ومقصود (مش أثر جانبي مستتر): نقطة التنسيق الوحيدة بين النظامين.

        `_commit=False` بيخلي الكتابة تنضمّ لمعاملة المستدعي (مستخدم في `remove_watched`).
        """
        self.upsert_notification_state(
            conversation_id, status=status, notified_status=status, retry_count=0,
            updated_at=now, _commit=_commit,
        )

    # --------------------------------------------- notifier durable pending (OHB2-08-01)
    def set_notifier_pending(
        self,
        conversation_id: str,
        state: str,
        now: str,
        event_id: int | None = None,
        transition_seq: int | None = None,
    ) -> None:
        """علامة write-ahead **دائمة** للمُبلّغ: إشعار انتهاء اتّبعت (اتقبل) لكن تسجيله
        الدائم لسه معلّق.

        بتتكتب **بعد** ما تليجرام يأكّد الإرسال و**قبل** تسجيل `notification_state`
        الدائم. عكس التلميح in-memory القديم، العلامة دي بتفضل بعد إعادة تشغيل العملية،
        فالدورة الجاية تسوّيها (تسجّل الحالة الدائمة) **قبل أي إرسال** — فمايحصلش إعادة
        إرسال عمياء. كتابة ضيّقة على جدول مستقل، ما بتلمسش `notification_state`.

        `event_id` = معرّف حدث الصندوق المرتبط، و`transition_seq` = هوية الانتقال،
        (OHB2-08-05 Batch 3R) عشان التسوية بعد إعادة التشغيل تعلّم نفس الحدث `delivered`
        وترقّي عدّاد الانتقالات لآخر انتقال اتسلّم فعلًا.
        """
        self._conn.execute(
            "INSERT INTO notifier_pending"
            "(conversation_id, state, updated_at, event_id, transition_seq) "
            "VALUES(?,?,?,?,?) "
            "ON CONFLICT(conversation_id) DO UPDATE SET "
            "state=excluded.state, updated_at=excluded.updated_at, "
            "event_id=COALESCE(excluded.event_id, notifier_pending.event_id), "
            "transition_seq=COALESCE(excluded.transition_seq, notifier_pending.transition_seq)",
            (conversation_id, state, now, event_id, transition_seq),
        )
        self._conn.commit()

    def get_notifier_pending(self, conversation_id: str) -> str | None:
        """حالة التسليم المعلّق الدائمة لمحادثة، أو None لو مفيش علامة."""
        row = self._conn.execute(
            "SELECT state FROM notifier_pending WHERE conversation_id=?",
            (conversation_id,),
        ).fetchone()
        return row["state"] if row else None

    def get_notifier_pending_row(self, conversation_id: str) -> tuple[int | None, int | None] | None:
        """(event_id, transition_seq) لعلامة التسليم المعلّقة، أو None لو مفيش علامة."""
        row = self._conn.execute(
            "SELECT event_id, transition_seq FROM notifier_pending WHERE conversation_id=?",
            (conversation_id,),
        ).fetchone()
        if row is None:
            return None
        event_id = int(row["event_id"]) if row["event_id"] is not None else None
        seq = int(row["transition_seq"]) if row["transition_seq"] is not None else None
        return event_id, seq

    def list_notifier_pending(self) -> dict[str, str]:
        """كل علامات التسليم المعلّق الدائمة (conversation_id -> state)."""
        rows = self._conn.execute(
            "SELECT conversation_id, state FROM notifier_pending"
        ).fetchall()
        return {r["conversation_id"]: r["state"] for r in rows}

    def clear_notifier_pending(self, conversation_id: str) -> None:
        """يمسح علامة التسليم المعلّق الدائمة (بعد نجاح التسجيل الدائم)."""
        self._conn.execute(
            "DELETE FROM notifier_pending WHERE conversation_id=?", (conversation_id,)
        )
        self._conn.commit()

    def reconcile_notifier_pending(self, conversation_id: str, now: str) -> str | None:
        """يسوّي علامة التسليم المعلّق **الدائمة** في معاملة واحدة ذرّية.

        يسجّل الحالة اللي **اتّبعت فعلًا** (`notification_state.notified_status`) ويمسح
        العلامة في نفس المعاملة (`BEGIN IMMEDIATE`): إما ينجحوا مع بعض أو يفشلوا مع بعض.
        لو التسجيل فشل، العلامة تفضل ⇒ إعادة محاولة آمنة (مفيش فقد دليل، ومفيش إرسال
        تاني). بيرجّع الحالة اللي اتسجّلت، أو None لو مفيش علامة. **ما بيعملش أي إرسال.**

        OHB2-08-05 (Batch 3R): لو العلامة مربوطة بحدث صندوق (`event_id`)، بنعلّمه
        `delivered` **في نفس المعاملة** — فالتسليم الناجح والحدث المتين يتحوّلوا لـ delivered
        مع بعض (مفيش حدث معلّق للأبد بعد إعادة التشغيل).
        """
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT state, event_id FROM notifier_pending "
                "WHERE conversation_id=?",
                (conversation_id,),
            ).fetchone()
            if row is None:
                conn.commit()
                return None
            state = row["state"]
            event_id = row["event_id"]
            self.record_notification_sent(conversation_id, state, now, _commit=False)
            if event_id is not None:
                self.mark_inbox_delivered(int(event_id), now, _commit=False)
            # OHB2-08-05 (Batch 3R-FIX2): `transition_seq` بقى **عصر اكتشاف** بيتثبّت عند
            # الاكتشاف (في `note_transition`)، مش عند التسليم. فالتسوية **ما بتلمسوش** —
            # ترقيته هنا كانت ممكن تنزّله/تدوس على عصر انتقال أحدث.
            conn.execute(
                "DELETE FROM notifier_pending WHERE conversation_id=?", (conversation_id,)
            )
            conn.commit()
            return state
        except Exception:
            conn.rollback()
            raise

    # -------------------------------------- retry-after deadlines (OHB2-08-02R)
    def set_retry_not_before(self, conversation_id: str, not_before_iso: str) -> None:
        """يسجّل **موعد إعادة المحاولة الدائم** لمحادثة (UTC ISO) بعد RetryAfter (429).

        عكس المؤقّت in-memory القديم، الموعد ده بيفضل بعد إعادة تشغيل العملية، فالدورة
        الجاية ما بتحاولش قبل ما الموعد يعدّي. جدول مستقل (كتابة ضيّقة، ما بتلمسش
        `notification_state` ولا `watched`).
        """
        self._conn.execute(
            "INSERT INTO notifier_retry_not_before(conversation_id, not_before) VALUES(?,?) "
            "ON CONFLICT(conversation_id) DO UPDATE SET not_before=excluded.not_before",
            (conversation_id, not_before_iso),
        )
        self._conn.commit()

    def get_retry_not_before(self, conversation_id: str) -> str | None:
        """موعد إعادة المحاولة الدائم لمحادثة (UTC ISO)، أو None لو مفيش."""
        row = self._conn.execute(
            "SELECT not_before FROM notifier_retry_not_before WHERE conversation_id=?",
            (conversation_id,),
        ).fetchone()
        return row["not_before"] if row else None

    def list_retry_not_before(self) -> dict[str, str]:
        """كل مواعيد إعادة المحاولة الدائمة (conversation_id -> UTC ISO)."""
        rows = self._conn.execute(
            "SELECT conversation_id, not_before FROM notifier_retry_not_before"
        ).fetchall()
        return {r["conversation_id"]: r["not_before"] for r in rows}

    def clear_retry_not_before(self, conversation_id: str) -> None:
        """يمسح موعد إعادة المحاولة الدائم (بعد ما يعدّي أو عند إعادة الجدولة)."""
        self._conn.execute(
            "DELETE FROM notifier_retry_not_before WHERE conversation_id=?",
            (conversation_id,),
        )
        self._conn.commit()

    # ------------------------------------------------ notification inbox (OHB2-08-05)
    # OHB2-08-05 (Batch 3R): الصندوق بقى سجل **دائم للأحداث المُكتشَفة**، مش سجل للتسليمات
    # الناجحة بس. الحدث بيتسجّل عند لحظة اكتشافه المنطقية (`add_inbox_event`،
    # delivery_status='pending') **قبل** أي محاولة إرسال، وحالة التسليم بتتحدّث بعد كده
    # بشكل مستقل (`mark_inbox_delivered` / `record_inbox_attempt`). كده الحدث مايتفقدش لو
    # تيليجرام فشل أو العملية وقعت. حالة القراءة (`read_at`) مستقلة تمامًا عن حالة التسليم.
    def add_inbox_event(
        self,
        conversation_id: str,
        title: str,
        kind: str,
        message: str,
        now: str,
        *,
        event_key: str | None = None,
        chat_id: int | None = None,
        transition_status: str | None = None,
        transition_seq: int | None = None,
    ) -> int | None:
        """يسجّل حدث إشعار **دائم** (delivery_status='pending') ويرجّع المعرّف.

        بيتنادى عند لحظة اكتشاف الحدث، **قبل** أي إرسال لتليجرام. الرسالة بتتقصّ عند
        `INBOX_MAX_MESSAGE_CHARS`. التقليم (قراءة أولًا) في نفس المعاملة. الإدراج idempotent
        لو `event_key` موجود (قيد التفرّد الجزئي) ⇒ يرجّع `None` (مفيش صف جديد).

        `chat_id` = وجهة التسليم المحفوظة مع الحدث عشان الاسترجاع/إعادة المحاولة يقدروا
        يبعتوا الحدث من غير الاعتماد على صف المتابعة (اللي ممكن يكون اتشال).

        `transition_status` (Batch 3R-FIX2) = **وصف** الحالة المرصودة (للعرض/التنسيق).
        `transition_seq` = **هوية** الانتقال الدائمة (عصر الاكتشاف). لو فيه صف انتقال معلّق
        بنفس (المحادثة، `transition_seq`)، القيد الموحّد بيرفض الصف الجديد وبنرجّع `None`
        (مفيش ازدواج لنفس الانتقال). انتقال مختلف لنفس الحالة ليه رقم مختلف ⇒ صف منفصل.
        """
        return self._insert_inbox(
            conversation_id, title, kind, message, now,
            event_key=event_key, chat_id=chat_id,
            delivery_status=INBOX_DELIVERY_PENDING, delivered_at=None,
            transition_status=transition_status, transition_seq=transition_seq,
        )

    def add_inbox_item(
        self,
        conversation_id: str,
        title: str,
        kind: str,
        message: str,
        now: str,
        *,
        event_key: str | None = None,
        chat_id: int | None = None,
    ) -> int | None:
        """يسجّل إشعار **اتسلّم فعلًا** (delivery_status='delivered') ويرجّع المعرّف.

        متوافق للخلف: أي كود قديم بيستخدمه لتسجيل تسليم ناجح. الصفوف الجديدة الموصى بيها
        بقت `add_inbox_event` (حدث أولًا) + تحديث التسليم بعدين.
        """
        return self._insert_inbox(
            conversation_id, title, kind, message, now,
            event_key=event_key, chat_id=chat_id,
            delivery_status=INBOX_DELIVERY_DELIVERED, delivered_at=now,
        )

    def _insert_inbox(
        self,
        conversation_id: str,
        title: str,
        kind: str,
        message: str,
        now: str,
        *,
        event_key: str | None,
        chat_id: int | None,
        delivery_status: str,
        delivered_at: str | None,
        transition_status: str | None = None,
        transition_seq: int | None = None,
    ) -> int | None:
        text = message or ""
        if len(text) > INBOX_MAX_MESSAGE_CHARS:
            text = text[:INBOX_MAX_MESSAGE_CHARS]
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            # OHB2-C7 (RESURRECTION-FIX): مفيش إدراج حدث إشعار لشات متشاهد حذف (منع إشعار
            # قديم عن شات ملغي). الفحص جوه المعاملة ⇒ محصّن ضد حذف متزامن.
            if self.is_deleted(conversation_id):
                conn.rollback()
                return None
            cur = conn.execute(
                "INSERT INTO notification_inbox"
                "(conversation_id, title, kind, message, created_at, read_at, event_key, "
                " delivery_status, delivery_attempts, delivered_at, chat_id, "
                " transition_status, transition_seq) "
                "VALUES(?, ?, ?, ?, ?, NULL, ?, ?, 0, ?, ?, ?, ?) "
                "ON CONFLICT(event_key) WHERE event_key IS NOT NULL DO NOTHING",
                (conversation_id, title or "", kind or "", text, now, event_key,
                 delivery_status, delivered_at, chat_id, transition_status, transition_seq),
            )
            if cur.rowcount == 0:
                # نفس الحدث اتسجّل قبل كده (نفس event_key) ⇒ مفيش صف جديد.
                conn.commit()
                return None
            new_id = int(cur.lastrowid)
            self._prune_inbox(conn, conversation_id)
            conn.commit()
            return new_id
        except sqlite3.IntegrityError:
            # OHB2-08-05 (Batch 3R-FIX2): القيد الموحّد (المحادثة، `transition_seq`) رفض
            # صفًا ثانيًا لنفس **الانتقال** (مثلاً المُبلّل لقى نفس الانتقال اللي المراقب
            # سجّله). مش خطأ: نرجّع None (مفيش حدث جديد). أي IntegrityError تانية (مثلاً
            # event_key) بتتفشّل عادي من الـ except العام تحت.
            conn.rollback()
            if transition_seq is not None and self._has_transition_row(
                conversation_id, transition_seq
            ):
                return None
            raise
        except Exception:
            conn.rollback()
            raise

    def _has_transition_row(self, conversation_id: str, transition_seq: int) -> bool:
        """هل فيه صف انتقال **معلّق** بنفس (المحادثة، `transition_seq`)؟ (فحص بعد IntegrityError)."""
        row = self._conn.execute(
            "SELECT 1 FROM notification_inbox "
            "WHERE conversation_id=? AND transition_seq=? AND delivery_status='pending' "
            "LIMIT 1",
            (conversation_id, transition_seq),
        ).fetchone()
        return row is not None

    def find_pending_transition(
        self, conversation_id: str, transition_seq: int
    ) -> InboxItem | None:
        """أحدث صف انتقال **معلّق** بنفس (المحادثة، `transition_seq`) — هوية الانتقال الموحّدة.

        OHB2-08-05 (Batch 3R-FIX2): بيمكّن العاملين من مشاركة **نفس** صف الحدث لنفس
        الانتقال (نفس رقم العصر). لو موجود، التاني بيعيد استخدامه (يسترجعه/يعلّمه) بدل ما
        يسجّل صف تاني. بيطابق قيد التفرّد الجزئي (`delivery_status='pending'`).
        """
        if transition_seq is None:
            return None
        row = self._conn.execute(
            f"SELECT {self._INBOX_COLUMNS} FROM notification_inbox "
            "WHERE conversation_id=? AND transition_seq=? AND delivery_status='pending' "
            "ORDER BY id DESC LIMIT 1",
            (conversation_id, int(transition_seq)),
        ).fetchone()
        return self._inbox_from_row(row) if row else None

    def find_latest_pending_transition(self, conversation_id: str) -> InboxItem | None:
        """أحدث صف انتقال **معلّق** لمحادثة، بغض النظر عن عصر `transition_seq`.

        OHB2-08-05 (Batch 3R-FIX2-N2): هوية الانتقال **الكانونية** للمحادثة دلوقتي = أعلى
        `transition_seq` معلّق. المُبلّل بيستخدمها لتحديد إذا الحدث المعلّق هو *العصر الحالي*
        (يتولّاه عادي) ولا **متجاوز** (superseded، انتقال أحدث عدّاه) — في الحالة التانية
        لسه بيتولّاه لو المتابعة **عالقة** (مسار المراقب مش هيعيد المحاولة) عشان ما يعلقش
        للأبد (عيب N-2). بيرجّع `None` لو مفيش أي صف انتقال معلّق.
        """
        row = self._conn.execute(
            f"SELECT {self._INBOX_COLUMNS} FROM notification_inbox "
            "WHERE conversation_id=? AND transition_seq IS NOT NULL "
            "AND delivery_status='pending' "
            "ORDER BY transition_seq DESC, id DESC LIMIT 1",
            (conversation_id,),
        ).fetchone()
        return self._inbox_from_row(row) if row else None

    def mark_inbox_failed(self, item_id: int, now: str, error: str | None = None) -> bool:
        """يعلّم حدثًا `failed` **بدون** استهلاك محاولة (استنفاد ميزانية/رفض دائم).

        OHB2-08-05 (Batch 3R-FIX): بيمكّن مسار الاسترجاع من تصنيف الحدث فاشل بشكل صريح
        (بدل تركه معلّق للأبد) من غير ما يزوّد عدّاد المحاولات (اللي بالفعل وصل الحد).
        """
        if error is not None:
            error = str(error)[:INBOX_MAX_ERROR_CHARS]
        cur = self._conn.execute(
            "UPDATE notification_inbox SET delivery_status='failed', "
            "last_attempt_at=?, last_error=COALESCE(?, last_error), next_retry_at=NULL, "
            "claim_token=NULL, claim_at=NULL "
            "WHERE id=?",
            (now, error, int(item_id)),
        )
        self._conn.commit()
        return bool(cur.rowcount)

    def _prune_inbox(self, conn, conversation_id: str) -> None:
        """تقليم الصندوق (سياسة صريحة) **داخل معاملة المستدعي**.

        السياسة (OHB2-08-05 Batch 3R-FIX):
        - الصفوف **المعلّقة** (`pending`) و**غير المقروءة** (`read_at IS NULL`)
          **مايتقلّمش أبدًا** — إشعار مستني تسليم أو لسه ماتشافش مايتحذفش صامت.
        - الصفوف **المؤرشفة** (`archived_at IS NOT NULL`) **مايتقلّمش أبدًا** (OHB2-PHASE1C):
          الأرشفة إجراء **مقصود من المستخدم** للاحتفاظ بالإشعار؛ التقليم التلقائي مايلغيهاش.
        - الصفوف **المقروءة وغير المؤرشفة** بس هي المؤهّلة للتقليم، الأقدم أولًا (تحديد
          ثابت: `id ASC`).
        - السقف لكل محادثة (`INBOX_MAX_PER_CONVERSATION`) والسقف العام (`INBOX_MAX_TOTAL`)
          بيفضلوا **سقوفًا ناعمة**: لو الصفوف المحمية لوحدها تعدّي السقف، الجدول يتعدّاه
          (مفيش حذف لصف محمي عشان نرضي سقف). التقليم بيتخطّى الصفوف المحمية باستمرار.
        """
        # 1) تقليم لكل محادثة (المقروءة غير المؤرشفة بس).
        conn.execute(
            "DELETE FROM notification_inbox "
            "WHERE conversation_id=? AND delivery_status!='pending' AND read_at IS NOT NULL "
            "AND archived_at IS NULL "
            "AND id NOT IN ("
            "SELECT id FROM notification_inbox "
            "WHERE conversation_id=? AND delivery_status!='pending' AND read_at IS NOT NULL "
            "AND archived_at IS NULL "
            "ORDER BY id DESC LIMIT ?)",
            (conversation_id, conversation_id, INBOX_MAX_PER_CONVERSATION),
        )
        # 2) تقليم عام (المقروءة غير المؤرشفة بس).
        conn.execute(
            "DELETE FROM notification_inbox "
            "WHERE delivery_status!='pending' AND read_at IS NOT NULL "
            "AND archived_at IS NULL AND id NOT IN ("
            "SELECT id FROM notification_inbox "
            "WHERE delivery_status!='pending' AND read_at IS NOT NULL "
            "AND archived_at IS NULL "
            "ORDER BY id DESC LIMIT ?)",
            (INBOX_MAX_TOTAL,),
        )

    _INBOX_COLUMNS = (
        "id, conversation_id, title, kind, message, created_at, read_at, event_key, "
        "delivery_status, delivery_attempts, last_attempt_at, delivered_at, last_error, "
        "next_retry_at, chat_id, transition_status, transition_seq, claim_token, claim_at, "
        "archived_at"
    )

    @staticmethod
    def _inbox_from_row(r) -> InboxItem:
        return InboxItem(
            r["id"], r["conversation_id"], r["title"], r["kind"], r["message"],
            r["created_at"], r["read_at"], r["event_key"],
            r["delivery_status"], r["delivery_attempts"], r["last_attempt_at"],
            r["delivered_at"], r["last_error"], r["next_retry_at"], r["chat_id"],
            r["transition_status"], r["transition_seq"], r["claim_token"], r["claim_at"],
            r["archived_at"],
        )

    @staticmethod
    def _inbox_visibility_clause(archived: bool) -> str:
        """شرط محور الأرشفة + استبعاد الشاتات المتشاهدة حذفًا (منع إفصاح محتوى شات محذوف).

        `archived=False` (الافتراضي) = الصندوق النشط (غير المؤرشف)؛ `archived=True` =
        الأرشيف بس. وفي **الحالتين** بنستبعد أي صف `conversation_id` عليه شاهد حذف دائم
        (نفس معنى `is_deleted`) — كشرط SQL واحد ⇒ مايظهرش عنوان/نص شات محذوف في الصندوق
        (ولا في عدّاد غير المقروء). الصفوف نفسها **ما بتتحذفش** (بتفضل أثر تدقيق للـ
        تسوية/المنع) وبنستبعدها من العرض بس.
        """
        axis = "archived_at IS NOT NULL" if archived else "archived_at IS NULL"
        return (
            f"({axis}) AND NOT EXISTS (SELECT 1 FROM deleted_conversations d "
            "WHERE d.conversation_id = notification_inbox.conversation_id)"
        )

    def list_inbox(
        self,
        *,
        limit: int = INBOX_PAGE_SIZE,
        offset: int = 0,
        unread_only: bool = False,
        archived: bool = False,
    ) -> list[InboxItem]:
        """قايمة الصندوق (الأحدث أولًا)، بترقيم محدود على مستوى SQL (payload محدود).

        `archived=False` (الافتراضي) = الصندوق النشط (غير المؤرشف). `archived=True` =
        عرض الأرشيف بس. الأرشفة محور مستقل ⇒ ما بتغيّرش ترتيب `id DESC` ولا حالة القراءة.

        AUD-04 (دفاع في العمق): `limit`/`offset` لازم يكونوا داخل نطاق SQLite قبل
        الـ binding؛ أي قيمة أكبر ترفض بدل ما ترمي OverflowError (500).
        """
        limit = int(limit)
        offset = int(offset)
        if limit < 0 or offset < 0 or limit > MAX_SQLITE_INT or offset > MAX_SQLITE_INT:
            raise ValueError("حدود الصفحة خارج النطاق المسموح")
        clauses = [self._inbox_visibility_clause(archived)]
        if unread_only:
            clauses.append("read_at IS NULL")
        where = "WHERE " + " AND ".join(clauses)
        rows = self._conn.execute(
            f"SELECT {self._INBOX_COLUMNS} FROM notification_inbox {where} "
            f"ORDER BY id DESC LIMIT ? OFFSET ?",
            (int(limit), int(offset)),
        ).fetchall()
        return [self._inbox_from_row(r) for r in rows]

    def get_inbox_item(self, item_id: int) -> InboxItem | None:
        """عنصر صندوق واحد بالمعرّف، أو None لو مش موجود."""
        row = self._conn.execute(
            f"SELECT {self._INBOX_COLUMNS} FROM notification_inbox WHERE id=?",
            (int(item_id),),
        ).fetchone()
        return self._inbox_from_row(row) if row else None

    def find_inbox_by_event_key(self, event_key: str) -> InboxItem | None:
        """يبحث عن حدث بمفتاح الهوية (idempotency)، أو None لو مش موجود."""
        if not event_key:
            return None
        row = self._conn.execute(
            f"SELECT {self._INBOX_COLUMNS} FROM notification_inbox WHERE event_key=?",
            (event_key,),
        ).fetchone()
        return self._inbox_from_row(row) if row else None

    def count_inbox(
        self, *, unread_only: bool = False, pending_only: bool = False, archived: bool = False
    ) -> int:
        """عدد عناصر الصندوق (كلها / غير المقروءة / المعلّقة) داخل نطاق الأرشفة.

        `archived=False` (الافتراضي) = العناصر **النشطة** (غير المؤرشفة) بس — فالشارة
        وعدّ غير المقروء بيفضلوا على الصندوق الفعلي (الأرشيف محور مستقل).
        """
        clauses = [self._inbox_visibility_clause(archived)]
        if unread_only:
            clauses.append("read_at IS NULL")
        if pending_only:
            clauses.append("delivery_status='pending'")
        where = "WHERE " + " AND ".join(clauses)
        row = self._conn.execute(
            f"SELECT COUNT(*) AS n FROM notification_inbox {where}"
        ).fetchone()
        return int(row["n"]) if row else 0

    def mark_inbox_read(self, item_id: int, now: str) -> bool:
        """يعلّم عنصر صندوق كمقروء (idempotent). True لو العنصر موجود (حتى لو مقروء)."""
        conn = self._conn
        cur = conn.execute(
            "UPDATE notification_inbox SET read_at=COALESCE(read_at, ?) WHERE id=?",
            (now, int(item_id)),
        )
        conn.commit()
        if cur.rowcount and cur.rowcount > 0:
            return True
        # rowcount=0 ممكن يعني العنصر موجود ومقروء بالفعل (COALESCE ما غيّرش حاجة).
        row = conn.execute(
            "SELECT 1 FROM notification_inbox WHERE id=?", (int(item_id),)
        ).fetchone()
        return row is not None

    def mark_all_inbox_read(self, now: str) -> int:
        """يعلّم كل غير المقروء كمقروء. يرجّع عدد العناصر اللي اتغيّرت."""
        conn = self._conn
        cur = conn.execute(
            "UPDATE notification_inbox SET read_at=? WHERE read_at IS NULL", (now,)
        )
        conn.commit()
        return int(cur.rowcount or 0)

    def archive_inbox_item(self, item_id: int, now: str) -> bool | None:
        """يؤرشف صف صندوق (idempotent). True لو بقى مؤرشف، False لو العنصر مش موجود.

        OHB2-PHASE1C: الأرشفة **قابلة للعكس** ومستقلة تمامًا عن محور التسليم/القراءة —
        بتكتب `archived_at` بس. أرشفة صف مؤرشف بالفعل ما بتغيّرش وقت الأرشفة الأصلي
        (COALESCE) ⇒ idempotent، ومفيش أي مساس بالتسليم/العملية/القراءة.
        """
        conn = self._conn
        cur = conn.execute(
            "UPDATE notification_inbox SET archived_at=COALESCE(archived_at, ?) WHERE id=?",
            (now, int(item_id)),
        )
        conn.commit()
        if cur.rowcount and cur.rowcount > 0:
            return True
        row = conn.execute(
            "SELECT 1 FROM notification_inbox WHERE id=?", (int(item_id),)
        ).fetchone()
        return True if row is not None else False

    def unarchive_inbox_item(self, item_id: int) -> bool | None:
        """يلغي أرشفة صف (idempotent). True لو بقى نشط، False لو العنصر مش موجود.

        ما بيمسحش الصف؛ بيمسح `archived_at` بس ⇒ الصف يرجع للصندوق النشط بنفس الهوية
        وبنفس حالة القراءة/التسليم.
        """
        conn = self._conn
        cur = conn.execute(
            "UPDATE notification_inbox SET archived_at=NULL WHERE id=?", (int(item_id),)
        )
        conn.commit()
        if cur.rowcount and cur.rowcount > 0:
            return True
        row = conn.execute(
            "SELECT 1 FROM notification_inbox WHERE id=?", (int(item_id),)
        ).fetchone()
        return True if row is not None else False

    def has_open_outbox(self, conversation_id: str) -> bool:
        """هل فيه برومت **غير منتهٍ** (pending/claimed/sending) لنفس المحادثة؟

        OHB2-PHASE1C: حارس الحذف النهائي — إشعار لمحادثة عليها عملية إرسال جارية أو
        معلّقة مايتحذفش (حتى لو مُسلَّم+مقروء) عشان ما نفقدش دليل العملية المعلّقة.
        """
        row = self._conn.execute(
            "SELECT 1 FROM outbox WHERE conversation_id=? "
            "AND status IN (?, ?, ?) LIMIT 1",
            (conversation_id, OUTBOX_PENDING, OUTBOX_CLAIMED, OUTBOX_SENDING),
        ).fetchone()
        return row is not None

    def has_notifier_pending(self, conversation_id: str) -> bool:
        """هل فيه علامة تسليم معلّقة (`notifier_pending`) لنفس المحادثة؟

        OHB2-PHASE1C: حارس الحذف النهائي — علامة التسوية المعلّقة دليل تشغيلي حيّ
        (بتُستخدم للاسترجاع/التسوية)، فإشعار نفس المحادثة مايتحذفش نهائيًا.
        """
        row = self._conn.execute(
            "SELECT 1 FROM notifier_pending WHERE conversation_id=? LIMIT 1",
            (conversation_id,),
        ).fetchone()
        return row is not None

    def inbox_item_delete_eligibility(self, item_id: int) -> str:
        """تصنيف أهلية الصف للحذف النهائي: deleted / protected / missing.

        OHB2-PHASE1C — سياسة الحذف النهائي (مُفرَضة على السيرفر، **fail-closed**):
        - `missing`  : الصف مش موجود.
        - `protected`: الصف محمي. الحالات المحمية:
            * `kind` **غير معروف** (مش في `INBOX_DELETABLE_KINDS`) — أي نوع لسه
              ماتقيّمش/غريب بيتعامَل محميًا (ما نفقدش دليلًا ما عرفناش دلالته).
            * `delivery_status != 'delivered'` — لسه معلّق أو فشل (دليل تسليم).
            * غير مقروء (`read_at IS NULL`) — المستخدم لسه ما شافهوش.
            * مرجع في `notifier_pending.event_id` — دليل تسوية معلّق لازم للاسترجاع.
            * المحادثة عليها علامة `notifier_pending` — دليل تسوية حيّ لنفس المحادثة.
            * المحادثة عليها برومت **غير منتهٍ** في `outbox` — عملية جارية/معلّقة.
        - `deleted`  : مؤهّل (نوع آمن + مُسلَّم + مقروء + مفيش دليل تسوية/عملية مرتبط).
          ده **أضيق** من مجموعة التقليم، فما فيش تقليل لأي ضمان.
        """
        row = self._conn.execute(
            "SELECT conversation_id, kind, read_at, delivery_status "
            "FROM notification_inbox WHERE id=?",
            (int(item_id),),
        ).fetchone()
        if row is None:
            return INBOX_DELETE_MISSING
        # سياسة fail-closed: نوع غير معروف (أو `proactive`) ⇒ محمي.
        if row["kind"] not in INBOX_DELETABLE_KINDS:
            return INBOX_DELETE_PROTECTED
        if row["delivery_status"] != INBOX_DELIVERY_DELIVERED or row["read_at"] is None:
            return INBOX_DELETE_PROTECTED
        ref = self._conn.execute(
            "SELECT 1 FROM notifier_pending WHERE event_id=? LIMIT 1", (int(item_id),)
        ).fetchone()
        if ref is not None:
            return INBOX_DELETE_PROTECTED
        conversation_id = row["conversation_id"]
        if self.has_notifier_pending(conversation_id):
            return INBOX_DELETE_PROTECTED
        if self.has_open_outbox(conversation_id):
            return INBOX_DELETE_PROTECTED
        return INBOX_DELETE_DELETED

    def delete_inbox_item(self, item_id: int) -> str:
        """يحذف صف صندوق **نهائيًا** لو مؤهّل، في معاملة ذرّية واحدة.

        يرجّع `deleted` (اتحذف فعلًا) / `protected` (محمي، مفيش تغيير) / `missing`
        (مش موجود). الأهلية بتُعاد فحصها **داخل** المعاملة (`BEGIN IMMEDIATE`) ⇒ مفيش
        سباق مع تسجيل تسليم/ربط `notifier_pending` في نفس اللحظة. الحذف بيلمس جدول
        `notification_inbox` بس — مفيش أي مساس بصفوف outbox/creation/watched/
        notification_state/notifier_pending (مفيش حذف عرضي لسجل عملية أو تسوية).
        """
        ident = int(item_id)
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            verdict = self.inbox_item_delete_eligibility(ident)
            if verdict != INBOX_DELETE_DELETED:
                conn.commit()
                return verdict
            conn.execute("DELETE FROM notification_inbox WHERE id=?", (ident,))
            conn.commit()
            return INBOX_DELETE_DELETED
        except Exception:
            conn.rollback()
            raise

    def mark_inbox_delivered(self, item_id: int, now: str, *, _commit: bool = True) -> bool:
        """يسجّل نجاح تسليم تليجرام للحدث (delivery_status='delivered'). idempotent.

        `_commit=False` بيخلي الكتابة تنضمّ لمعاملة المستدعي (تسجيل ذرّي مع ماسح/متابعة).
        """
        conn = self._conn
        cur = conn.execute(
            "UPDATE notification_inbox SET delivery_status='delivered', "
            "delivered_at=COALESCE(delivered_at, ?), last_attempt_at=?, "
            "next_retry_at=NULL, last_error=NULL, claim_token=NULL, claim_at=NULL WHERE id=?",
            (now, now, int(item_id)),
        )
        if _commit:
            conn.commit()
        return bool(cur.rowcount)

    def record_inbox_attempt(
        self,
        item_id: int,
        now: str,
        *,
        error: str | None = None,
        next_retry_at: str | None = None,
        mark_failed: bool = False,
    ) -> int:
        """يسجّل محاولة تسليم فاشلة للحدث ويرجّع عدّاد المحاولات الجديد.

        `error` = تصنيف آمن (نوع الاستثناء) بيتقصّ عند `INBOX_MAX_ERROR_CHARS`. لو
        `mark_failed` نعلّمه `failed` (استنفدنا الميزانية) من غير مسح الحدث. لو
        `next_retry_at` موجود بنسجّل الموعد (RetryAfter) — **من غير** استهلاك عدّاد عادي
        (المستدعي بيبعت `mark_failed=False` و`next_retry_at` بس).
        """
        if error is not None:
            error = str(error)[:INBOX_MAX_ERROR_CHARS]
        conn = self._conn
        conn.execute(
            "UPDATE notification_inbox SET delivery_attempts=delivery_attempts+1, "
            "last_attempt_at=?, last_error=COALESCE(?, last_error), next_retry_at=?, "
            "claim_token=NULL, claim_at=NULL "
            "WHERE id=?",
            (now, error, next_retry_at, int(item_id)),
        )
        if mark_failed:
            conn.execute(
                "UPDATE notification_inbox SET delivery_status='failed' WHERE id=?",
                (int(item_id),),
            )
        row = conn.execute(
            "SELECT delivery_attempts FROM notification_inbox WHERE id=?", (int(item_id),)
        ).fetchone()
        conn.commit()
        return int(row["delivery_attempts"]) if row else 0

    def set_inbox_retry_deadline(self, item_id: int, next_retry_at: str | None) -> None:
        """يحدّث موعد إعادة المحاولة للحدث من غير ما يستهلك عدّاد محاولات (RetryAfter).

        OHB2-08-05 (Batch 3R-FIX2-F1): بيشيل رمز الحجز كمان — بعد RetryAfter الحدث لازم
        يبقى متاح للاسترجاع (لو سيبنا الحجز، الاسترجاع هيتخطّاه للأبد).
        """
        self._conn.execute(
            "UPDATE notification_inbox SET next_retry_at=?, claim_token=NULL, claim_at=NULL WHERE id=?",
            (next_retry_at, int(item_id)),
        )
        self._conn.commit()

    def list_due_pending_inbox(
        self,
        now: str,
        *,
        limit: int = 20,
        kinds: tuple[str, ...] | None = None,
        exclude_watched: bool = True,
        unclaimed: bool = False,
        claim_cutoff: str | None = None,
    ) -> list[InboxItem]:
        """أحداث تسليم معلّقة **حان وقتها** (next_retry_at فاضي/عدّى)، الأقدم أولًا.

        `kinds` = أنواع الإشعارات المسموحة (لكل مالك تسليم مساحته). `exclude_watched=True`
        يستثني محادثات المراقب الحالية (اللي المراقب مالك تسليمها في مساره النشط) عشان
        حلقة الاسترجاع ما تبعتش مكرّر بالتوازي مع مسار المراقب النشط.

        `unclaimed=True` (Batch 3R-FIX2-F1) يستثني الصفوف **المحجوزة** (`claim_token` مش
        فاضي) — أي حدث بتُحاول تسليمه لحظة كده من عامل تاني — **إلا** الحجز المنتهي
        (`claim_at` أقدم من `claim_cutoff`، من عملية وقعت) فبيعتبر متاح. بيتقرن دائمًا بـ
        `claim_pending_inbox` الذرّي عشان القرار ما يبقاش check-then-act.
        """
        clauses = [
            "delivery_status='pending'",
            "(next_retry_at IS NULL OR next_retry_at<=?)",
        ]
        params: list[object] = [now]
        if kinds is not None:
            placeholders = ",".join("?" for _ in kinds)
            clauses.append(f"kind IN ({placeholders})")
            params.extend(kinds)
        if exclude_watched:
            clauses.append("conversation_id NOT IN (SELECT conversation_id FROM watched)")
        if unclaimed:
            clauses.append(
                "(claim_token IS NULL OR (claim_at IS NOT NULL AND claim_at<=?))"
            )
            params.append(claim_cutoff)
        rows = self._conn.execute(
            f"SELECT {self._INBOX_COLUMNS} FROM notification_inbox "
            f"WHERE {' AND '.join(clauses)} ORDER BY id ASC LIMIT ?",
            (*params, int(limit)),
        ).fetchall()
        return [self._inbox_from_row(r) for r in rows]

    def claim_pending_inbox(
        self, item_id: int, token: str, now: str, *, cutoff: str | None = None
    ) -> bool:
        """يحجز حدثًا معلّقًا **ذرّيًا** لمحاولة تسليم واحدة (claim lease). True = الحجز نجح.

        OHB2-08-05 (Batch 3R-FIX2-F1): `UPDATE ... WHERE id=? AND delivery_status='pending'
        AND claim_token IS NULL` بيسجّل الرمز بس لو الصف لسه معلّق **وغير محجوز**، في معاملة
        ذرّية واحدة. القرار والكتابة في نفس الجملة ⇒ آمن عبر اتصالات SQLite منفصلة (مفيش
        check-then-act). لو عامل تاني حجز الصف بالفعل، `rowcount=0` ونرجّع False (ما نرسلش).

        `now` = وقت الحجز (بيتسجّل في `claim_at`). `cutoff` (اختياري) = حد انتهاء الصلاحية:
        لو موجود، الحجز المنتهي (`claim_at<=cutoff`، من عملية وقعت) بيتخطّى ونستولي عليه
        (بس بنشيل `claim_at` القديم ونسجّل الجديد) — فمافيش حدث يعلق محجوزًا للأبد.
        الرمز بيتشال في `record_inbox_attempt`/`mark_inbox_delivered`/`mark_inbox_failed`.
        """
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            if cutoff is None:
                where = "id=? AND delivery_status='pending' AND claim_token IS NULL"
                args = (token, now, int(item_id))
            else:
                where = (
                    "id=? AND delivery_status='pending' AND "
                    "(claim_token IS NULL OR (claim_at IS NOT NULL AND claim_at<=?))"
                )
                args = (token, now, int(item_id), cutoff)
            cur = conn.execute(
                f"UPDATE notification_inbox SET claim_token=?, claim_at=? WHERE {where}",
                args,
            )
            conn.commit()
            return cur.rowcount == 1
        except Exception:
            conn.rollback()
            raise

    def clear_inbox_claim(self, item_id: int, token: str) -> None:
        """يشيل رمز الحجز (بس لو مطابق للرمز، أمانًا) — للحالات اللي التسليم فيها مابدأش."""
        self._conn.execute(
            "UPDATE notification_inbox SET claim_token=NULL, claim_at=NULL "
            "WHERE id=? AND claim_token=?",
            (int(item_id), token),
        )
        self._conn.commit()

    # -------------------------------------------------------- integrity / upkeep
    def quick_check(self) -> bool:
        """فحص سريع للتكامل (PRAGMA quick_check). True = سليم.

        بيرمي sqlite3.DatabaseError لو فيه تلف في القرص/الملف — ما بنسكتش عليه.
        """
        row = self._conn.execute("PRAGMA quick_check").fetchone()
        return bool(row) and row[0] == "ok"

    def integrity_check(self) -> bool:
        """فحص تكامل كامل (PRAGMA integrity_check). True = سليم."""
        row = self._conn.execute("PRAGMA integrity_check").fetchone()
        return bool(row) and row[0] == "ok"

    def optimize(self) -> None:
        """تحسين دوري: ANALYZE + تفريغ مساحة (incremental vacuum لو مفعّل)."""
        self._conn.execute("PRAGMA optimize")
        try:
            self._conn.execute("PRAGMA incremental_vacuum")
        except sqlite3.OperationalError:
            # incremental_vacuum بيتطلب auto_vacuum؛ لو مش مفعّل نتجاهله بهدوء.
            pass
        self._conn.commit()

    def checkpoint(self, mode: str = "TRUNCATE") -> None:
        """يرجّع بيانات WAL لقاعدة البيانات الرئيسية ويقصّر الـ WAL (upkeep آمن)."""
        self._conn.execute(f"PRAGMA wal_checkpoint({mode})")
        self._conn.commit()

    def run_startup_maintenance(self) -> bool:
        """صيانة تشغيل آمنة: فحص سريع ثم تحسين + checkpoint.

        OHB2-POST-PUB-01/F06: نتيجة الفحص السريع بقت **مرجعية** — بتتخزّن في
        `integrity_ok` وبتتحكم في الجاهزية وبدء الـ workers. بترجّع True لو الفحص السريع
        سليم، وFalse لو القاعدة تالفة أو الفحص نفسه رمى (وبتسجّل سبب واضح).
        ما بتحذفش/تعيد بناء قاعدة تالفة (مفيش إصلاح تلقائي)، وما بترميش.
        """
        try:
            healthy = self.quick_check()
        except sqlite3.DatabaseError as exc:
            log.error("فحص قاعدة البيانات فشل (%s)", type(exc).__name__)
            self.integrity_ok = False
            return False
        if not healthy:
            log.error("قاعدة البيانات فحصها فشل (quick_check != ok)")
            self.integrity_ok = False
            return False
        try:
            self.optimize()
            self.checkpoint()
            # OHB2-PHASE1A: تنظيف جلسات الـ Mini App المنتهية عند الإقلاع (داخل نفس
            # دورة الصيانة — مفيش worker/مجدول جديد). غير حرج: لو فشل ما نوقفش الإقلاع.
            self.prune_web_sessions(time.time())
        except sqlite3.Error as exc:
            # الصيانة مش حرجة: القاعدة سليمة، فمنعطّلش البوت عشانها.
            log.warning("صيانة قاعدة البيانات اتخطّت (%s)", type(exc).__name__)
        self.integrity_ok = True
        return True
