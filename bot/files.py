"""خدمة ملفات آمنة للقراءة فقط، مشتركة بين البوت والـ Mini App (OHB2-09-01).

القواعد الأمنية (fail closed):
- **ملكية الشات** بتتأكّد قبل أي عملية ملفات: لازم الشات موجود و`created_by_user_id`
  بتاعه يساوي هوية المالك الحالية من `/users/me`. لو الهوية مش معروفة أو الحقل ناقص
  ⇒ ممنوع (مفيش اعتماد على غياب البيانات).
- **allowlist للمسارات**: القراءة مسموحة بس لمسار ظهر **حرفيًا** في قايمة ملفات نفس
  الشات. أي مسار مطلق، أو فيه مقطع `..`، أو NUL/محارف تحكّم، أو خطوط مائلة عكسية،
  أو مش من القايمة ⇒ مرفوض محليًا.
- **سبب وجود التحقق المحلي**: اتأكّدنا (قراءة فقط) إن نقطة القراءة عند OpenHands
  **مش محصورة** في مساحة عمل الشات — `file_path=/etc/hostname` أو `../../../../etc/hostname`
  بيرجّع محتوى من الحاوية. فالحماية الحقيقية هي الـ allowlist المحلية، مش المنع من فوق.
- **حدود ونتائج منظّمة**: حجم أقصى، وكشف ثنائي/UTF-8، وقص معاينة، ونتائج حالات واضحة.

مفيش رفع ملفات (الـ API مابيدعمش رفع)، ومفيش عميل تاني ولا worker ولا جدول جديد.
"""
from __future__ import annotations

import asyncio
import posixpath
import re
from dataclasses import dataclass
from enum import Enum

from .errors import ApiError, ResponseTooLargeError, error_text

# معرّف الشات بيتحطّ في مسار الـ URL، فبنقصرّه على حروف/أرقام/شرطة/شرطة سفلية
# (UUID الحقيقي 32 حرف hex بيمشي)، عشان نمنع حقن مسار (`/`، `..`، مسافات).
MAX_CONVERSATION_ID_LEN = 64
MAX_PATH_LEN = 1024
# حد صلب للمعاينة: أكبر من كده ⇒ TOO_LARGE (مابنرجّعش المحتوى).
MAX_PREVIEW_BYTES = 256 * 1024
# عدد محارف المعاينة: أكبر من كده ⇒ نقصّ ونعلّم truncated=True.
PREVIEW_CHARS = 100_000

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,%d}$" % MAX_CONVERSATION_ID_LEN)


class FileStatus(str, Enum):
    """نتيجة منظّمة لعملية ملفات (مفيش استثناءات بترفع للمستدعي)."""

    OK = "ok"
    UNAUTHORIZED = "unauthorized"      # الملكية مش مثبتة (fail closed)
    NOT_FOUND = "not_found"            # الشات أو الملف مش موجود
    DELETED = "deleted"                # الشات عليه شاهد حذف (F-1) — يُعرَض كـ not_found
    INVALID_PATH = "invalid_path"      # مسار مرفوض محليًا (مطلق/اجتياز/غير صالح)
    BINARY = "binary"                  # محتوى ثنائي (مش نص)
    NOT_UTF8 = "not_utf8"              # ترميز غير صالح
    TOO_LARGE = "too_large"            # أكبر من الحد الصلب
    UPSTREAM_ERROR = "upstream_error"  # فشل من OpenHands


@dataclass(frozen=True)
class FileListing:
    status: FileStatus
    files: tuple[str, ...] = ()
    error: str | None = None


@dataclass(frozen=True)
class FileContent:
    status: FileStatus
    path: str = ""
    text: str = ""
    truncated: bool = False
    size_bytes: int = 0
    error: str | None = None


def is_valid_conversation_id(value: str | None) -> bool:
    """هل المعرّف آمن للاستخدام في مسار الـ URL؟ (بدون مسافات/سلاش/اجتياز)."""
    return isinstance(value, str) and bool(_ID_RE.match(value))


def is_safe_workspace_path(path: str | None) -> bool:
    """مسار نسبي آمن داخل مساحة العمل؟

    بيرفض: الفاضي، المطلق، الشرطة العكسية، أي محرف تحكّم (بما فيه NUL)، أي مقطع
    فاضي/`.`/`..`، وأي مسار ما بيساويش صورته المطبّعة (نمنع `a/../b` وأمثاله).
    """
    if not isinstance(path, str) or not path or len(path) > MAX_PATH_LEN:
        return False
    if path.startswith("/"):
        return False
    if "\\" in path:
        return False
    if any(ord(ch) < 0x20 or ch == "\x7f" for ch in path):
        return False
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return False
    if posixpath.normpath(path) != path:
        return False
    return True


def is_listed_path(path: str | None, listed) -> bool:
    """المسار آمن **و** موجود حرفيًا في قايمة ملفات الشات (allowlist)."""
    return is_safe_workspace_path(path) and path in listed


# --------------------------------------------------------------- shared authz
# خرائط حالة التفويض ⇒ (رمز ثابت، HTTP، رسالة عربية آمنة). تُستخدم في كل الطبقات
# (تصدير البوت + خدمات الـ Mini App) عشان التخطيط يفضل متسق من غير تفاصيل upstream خام.
CONVERSATION_ERRORS: dict["FileStatus", tuple[str, int, str]] = {
    FileStatus.UNAUTHORIZED: ("unauthorized", 403, "مش مسموح لك بالوصول للشات ده."),
    FileStatus.NOT_FOUND: ("not_found", 404, "الشات مش موجود."),
    # F-1: شات عليه شاهد حذف يُعرَض **بنفس** رد «مش موجود» (404) عشان ما نكشفش وجود
    # شات محذوف ولا أي تفاصيل عنه. الرد آمن ومتسق مع عرف الـ API.
    FileStatus.DELETED: ("not_found", 404, "الشات مش موجود."),
    FileStatus.UPSTREAM_ERROR: ("upstream_error", 502, "تعذّر الوصول للشات دلوقتي، جرّب تاني."),
}

# OHB2-09-06: خرائط حالة الملفات المشتركة بين الـ Mini App ومسار البوت — مصدر واحد
# للحقيقة عشان الاتنين يتصرّفوا بنفس الطريقة على نفس الحالة (بدون نسخة مكرّرة).
FILE_STATUS_ERRORS: dict["FileStatus", tuple[str, int]] = {
    FileStatus.UNAUTHORIZED: ("unauthorized", 403),
    FileStatus.NOT_FOUND: ("not_found", 404),
    FileStatus.DELETED: ("not_found", 404),
    FileStatus.INVALID_PATH: ("invalid_path", 400),
    FileStatus.TOO_LARGE: ("too_large", 413),
    FileStatus.UPSTREAM_ERROR: ("upstream_error", 502),
}
FILE_STATUS_MESSAGES: dict["FileStatus", str] = {
    FileStatus.UNAUTHORIZED: "مش مسموح لك بالوصول لملفات الشات ده.",
    FileStatus.NOT_FOUND: "الشات أو الملف مش موجود.",
    FileStatus.DELETED: "الشات أو الملف مش موجود.",
    FileStatus.INVALID_PATH: "مسار الملف غير صالح.",
    FileStatus.BINARY: "الملف مش نص (مش قابل للعرض).",
    FileStatus.NOT_UTF8: "الملف بترميز مش مدعوم (مش قابل للعرض).",
    FileStatus.TOO_LARGE: "حجم الملف كبير أوي للعرض.",
    FileStatus.UPSTREAM_ERROR: "تعذّر الوصول لخدمة الملفات دلوقتي.",
}
# حالات المحتوى اللي بتعتبر «قراءة ناجحة» (محتوى اتقرا فعلاً، بس ممكن يكون مش نص UTF-8).
FILE_CONTENT_STATUSES = frozenset({FileStatus.OK, FileStatus.BINARY, FileStatus.NOT_UTF8})


def file_status_message(status: "FileStatus", error: str | None = None) -> str:
    """رسالة عربي آمنة لحالة ملفات (للـ Mini App والبوت). خطأ upstream المتنقّح بيتفضّل."""
    message = FILE_STATUS_MESSAGES.get(status, "تعذّر الوصول لخدمة الملفات دلوقتي.")
    if status is FileStatus.UPSTREAM_ERROR and error:
        return error  # رسالة ApiError متنقّحة (مفيش تفاصيل خام/أسرار)
    return message


class IdentityCache:
    """كاش هوية OpenHands للمالك، مربوط بعميل واحد ثابت الاعتماد (OHB2-09-A2-04).

    - يخزّن **النجاح فقط** (UUID غير فاضي)؛ أي فشل في `/users/me` يرجّع None دلوقتي
      (fail closed) من غير تسميم الكاش، فأول نجاح لاحق بيتخزّن.
    - أول قراءة متزامنة بتتسلسل بقفل عشان مايحصلش سيل طلبات متكرّرة لنفس الهوية.
    - نفس الكائن بيتشارك بين كل عمليات الشات في نفس الخدمة ⇒ نداء `/users/me` واحد.
    """

    def __init__(self, client) -> None:
        self._client = client
        self._owner_id: str | None = None
        self._lock = asyncio.Lock()

    async def owner_id(self) -> str | None:
        if self._owner_id is not None:
            return self._owner_id
        async with self._lock:
            if self._owner_id is not None:  # إعادة فحص بعد اكتساب القفل
                return self._owner_id
            try:
                me = await self._client.get_current_user()
            except ApiError:
                return None  # فشل مؤقّت ⇒ ما نسمّمش الكاش
            uid = me.get("id") if isinstance(me, dict) else None
            if not uid:
                return None  # هوية مفقودة/غير صالحة ⇒ فشل مغلق (بدون تخزين)
            self._owner_id = str(uid)
            return self._owner_id


async def authorize_conversation(
    client, identity: IdentityCache, conversation_id: str, db=None, *, allow_deleted: bool = False
) -> tuple[dict | None, FileStatus]:
    """يتأكّد إن الشات موجود ومملوك لهوية المالك الحالية. يرجّع (الميتاداتا أو None، الحالة).

    **مفيش أي جلب لبيانات محمية هنا** — الدالة بترجّع بس الميتاداتا المتفوَّض عليها.
    الترتيب: فحص المعرّف ⇒ فحص شاهد الحذف المحلي (F-1، لو `db` متاح و`allow_deleted=False`)
    ⇒ جلب الميتاداتا ⇒ جلب/مقارنة الهوية ⇒ قرار. أي فشل (معرّف غير صالح/شات متشاهد/ميتاداتا
    ناقصة/مالك None/غير مطابق/فشل upstream) ⇒ رفض مغلق.

    `allow_deleted=True` استثناء مقصود لعمليتين صريحتين بس (مش قراءة): **إعادة التفاعل
    الصريح (`watch`)** و**إعادة محاولة الحذف** — دول بيعتمدوا على طبقة القاعدة (reengage /
    CAS الحذف) للتعامل مع الحالة المتشاهدة بأمان. كل مسارات القراءة/التصدير/التفاعل
    بتمرّ بالفحص (الافتراضي).
    """
    conv, status, _error = await authorize_conversation_detailed(
        client, identity, conversation_id, db, allow_deleted=allow_deleted
    )
    return conv, status


async def authorize_conversation_detailed(
    client, identity: IdentityCache, conversation_id: str, db=None, *, allow_deleted: bool = False
) -> tuple[dict | None, FileStatus, str | None]:
    """نفس تفويض `authorize_conversation` لكن بترجّع كمان رسالة خطأ upstream الآمنة.

    التنفيذ الوحيد للتفويض (مفيش نسخة تانية). الـ Mini App بيستخدم النسخة المختصرة
    (حالة ⇒ HTTP)، والبوت بيستخدم المطوّلة عشان يعرض رسالة الخطأ المتنقّحة عند فشل
    upstream (429/503/مهلة) بدل ما يخسّر التفصيل. **فشل upstream لسه رفض مغلق** —
    مفيش بيانات محمية بتتقرا.

    **F-1 (فرض شاهد الحذف):** لو `db` متاح و`allow_deleted=False` وفيه شاهد حذف فعّال
    للمعرّف، بنرفض **قبل** أي نداء بعيد لـ OpenHands (مفيش جلب ميتاداتا ولا محتوى). الشات
    المتشاهد بيُعرَض بحالة `DELETED` اللي بتتحوّل لنفس رد «مش موجود» (404) عند كل الطبقات —
    كده مفيش كشف لوجود شات محذوف ولا أي تفاصيل عنه. الفحص **فشل مغلق**: أي خطأ في قراءة
    القاعدة ⇒ نعتبره متشاهد (نخفي)، نفس سلوك `_without_deleted` وحماية التصدير القائمة.
    من غير `db` (سياقات مستقلة/اختبارات معزولة بلا قاعدة) أو مع `allow_deleted=True`
    (watch/حذف) الفحص بيتخطّى.
    """
    if not is_valid_conversation_id(conversation_id):
        return None, FileStatus.NOT_FOUND, None
    if db is not None and not allow_deleted:
        try:
            deleted = db.is_deleted(conversation_id)
        except Exception:  # noqa: BLE001 — قاعدة غير متاحة ⇒ فشل مغلق (نخفي، مفيش نداء بعيد)
            return None, FileStatus.DELETED, None
        if deleted:
            return None, FileStatus.DELETED, None
    try:
        convs = await client.get_conversations([conversation_id])
    except ApiError as exc:
        return None, FileStatus.UPSTREAM_ERROR, error_text(exc)
    if not convs:
        return None, FileStatus.NOT_FOUND, None
    owner = await identity.owner_id()
    if not owner:
        return None, FileStatus.UNAUTHORIZED, None
    created_by = convs[0].get("created_by_user_id")
    if not isinstance(created_by, str) or created_by != owner:
        return None, FileStatus.UNAUTHORIZED, None
    return convs[0], FileStatus.OK, None


def classify_text(
    text: str, *, max_bytes: int = MAX_PREVIEW_BYTES, preview_chars: int = PREVIEW_CHARS
) -> tuple[FileStatus, str, bool, int]:
    """يصنّف محتوى نصي ويرجّع (الحالة، نص المعاينة، هل اتقص، الحجم بالبايت).

    - أكبر من الحد الصلب ⇒ TOO_LARGE (من غير محتوى).
    - فيه NUL ⇒ BINARY (مش نص).
    - فيه محرف الاستبدال U+FFFD ⇒ NOT_UTF8 (الفك الأصلي فشل، فالمحتوى مش نص UTF-8 سليم).
    - أكبر من حد المحارف ⇒ OK مع قصّ وtruncated=True.
    """
    size = len(text.encode("utf-8"))
    if size > max_bytes:
        return FileStatus.TOO_LARGE, "", False, size
    if "\x00" in text:
        return FileStatus.BINARY, "", False, size
    if "\ufffd" in text:
        return FileStatus.NOT_UTF8, "", False, size
    if len(text) > preview_chars:
        return FileStatus.OK, text[:preview_chars], True, size
    return FileStatus.OK, text, False, size


class FileService:
    """قراءة ملفات آمنة فوق `OpenHandsClient` الموجود (بدون عميل/تخزين تاني).

    **ثبات الهوية (OHB2-09-A2-04):** كائن `OpenHandsClient` مربوط باعتماد خدمة واحد
    غير قابل للتغيير (`Authorization: Bearer <api key>` بتتثبّت عند البناء)، وبالتالي
    `/users/me` بترجّع نفس هوية OpenHands دايماً طول عمر العميل. مفيش "تسجيل دخول"
    ولا تبديل اعتماد/جلسة على مستوى العميل: تبديل الهوية الوحيد الممكن هو إنشاء كائن
    عميل جديد (وكذلك كائن `FileService` جديد)، والكاش هنا **مقيّد بالكائن** فمايتسرّبش
    بين عميلين. فالكاش آمن لموديل "مالك واحد + اعتماد خدمة ثابت".

    الكاش بيخزّن **النجاح بس** (UUID مش فاضي) ولا يخزّن الفشل: أي فشل في `/users/me`
    بيرجّع None دلوقتي (fail closed) من غير تسميم دائم، فأول نجاح لاحق بيتخزّن.
    أول قراءة متزامنة بتتسلسل بقفل عشان مايحصلش سيل طلبات متكرّرة لنفس الهوية.
    """

    def __init__(
        self,
        client,
        *,
        max_bytes: int = MAX_PREVIEW_BYTES,
        preview_chars: int = PREVIEW_CHARS,
        identity: IdentityCache | None = None,
        db=None,
    ) -> None:
        self._client = client
        self._max_bytes = int(max_bytes)
        self._preview_chars = int(preview_chars)
        # كاش الهوية ممكن يتشارك مع الخدمة الأم (نفس العميل) عشان `/users/me` يتنادى
        # مرة واحدة بس عبر كل العمليات. الافتراضي: كاش خاص بالخدمة.
        self._identity = identity if identity is not None else IdentityCache(client)
        # F-1: كائن القاعدة المالك (نفس اتصال العملية) لفرض شاهد الحذف عند التفويض.
        # اختياري: من غير قاعدة (سياقات مستقلة) ما فيش شواهد محلية تُفرَض.
        self._db = db

    async def _owner_identity(self) -> str | None:
        """هوية المالك (UUID) عبر الكاش المشترك، أو None لو مش قادرين نتأكّد (fail closed)."""
        return await self._identity.owner_id()

    async def authorize(self, conversation_id: str, *, allow_deleted: bool = False) -> tuple[dict | None, FileStatus]:
        """يفوّض الوصول لشات واحد: (الميتاداتا أو None، الحالة).

        التفويض كله في الدالة المشتركة `authorize_conversation` (مفيش نسخة تانية)،
        بما فيه فرض شاهد الحذف (F-1) لما تكون القاعدة متاحة. `allow_deleted=True`
        بيتخطّى الفحص لعمليتي watch/حذف بس (استثناء مقصود موثّق).
        """
        return await authorize_conversation(
            self._client, self._identity, conversation_id, self._db, allow_deleted=allow_deleted
        )

    async def list_files(self, conversation_id: str) -> FileListing:
        """قايمة ملفات مساحة عمل شات مصرّح به (مسارات نسبية آمنة بس)."""
        conv, status = await self.authorize(conversation_id)
        if conv is None:
            return FileListing(status)
        try:
            files = await self._client.list_files(conversation_id)
        except ApiError as exc:
            return FileListing(FileStatus.UPSTREAM_ERROR, error=error_text(exc))
        safe = tuple(f for f in files if is_safe_workspace_path(f))
        return FileListing(FileStatus.OK, files=safe)

    async def read_preview(self, conversation_id: str, path: str) -> FileContent:
        """معاينة نصية محدودة لملف **من قايمة ملفات الشات**.

        الترتيب: تفويض الشات ⇒ فحص المسار محليًا ⇒ جلب القايمة (allowlist) ⇒ القراءة
        المحدودة (`read_file_text_bounded`) ⇒ تصنيف المحتوى. الـ allowlist بتتجاب هنا
        (مش من المستدعي) عشان ما نثقش في مدخل. **مفيش أي رجوع** للطريقة غير المحدودة
        `read_file_text`.
        """
        safe_path = path if isinstance(path, str) else ""
        conv, status = await self.authorize(conversation_id)
        if conv is None:
            return FileContent(status, path=safe_path)
        if not is_safe_workspace_path(path):
            return FileContent(FileStatus.INVALID_PATH, path=safe_path)
        try:
            files = await self._client.list_files(conversation_id)
        except ApiError as exc:
            return FileContent(FileStatus.UPSTREAM_ERROR, path=path, error=error_text(exc))
        if path not in files:
            return FileContent(FileStatus.NOT_FOUND, path=path)
        try:
            data = await self._client.read_file_text_bounded(
                conversation_id, path, max_response_bytes=self._max_bytes
            )
        except ResponseTooLargeError:
            # الحد الصلب للرد اتعدّى (قبل تجميع الجسم كله) ⇒ حالة صريحة، مش خطأ عام.
            return FileContent(FileStatus.TOO_LARGE, path=path)
        except ApiError as exc:
            return FileContent(FileStatus.UPSTREAM_ERROR, path=path, error=error_text(exc))
        if data is None:
            return FileContent(FileStatus.UPSTREAM_ERROR, path=path)
        st, text, truncated, size = classify_text(
            data, max_bytes=self._max_bytes, preview_chars=self._preview_chars
        )
        return FileContent(st, path=path, text=text, truncated=truncated, size_bytes=size)
