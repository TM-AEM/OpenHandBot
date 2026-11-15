"""تنزيل مرفق مصادَق من الـ staging المحلي (OHB2-MT-2).

الهدف: مسار تنزيل **مصادَق ومحدود الموارد** لملفات موجودة أصلًا في نظام الـ staging
المحلي، من غير تحميل الملف كله في الذاكرة ومن غير حجز حلقة الأحداث المشتركة.

مبادئ:
- **القراءة مش على حلقة الأحداث:** كل `os.read` بتتنفّذ في خيط عامل عبر
  `starlette.concurrency.run_in_threadpool` (نفس `anyio.to_thread.run_sync`). العملية
  واحدة وحلقة أحداث واحدة (البوت + ASGI)، فالقراءة المتزامنة المباشرة كانت هتحجب
  الـ polling وكل الطلبات (Plan 10 §3، F-01، Strategy B).
- **إغلاق الـ fd حتمي:** مُكرِّر غير متزامن (async generator) بيقفل الوصفة في `finally`
  عند النجاح/الاستثناء/الإلغاء. ملاحظة مهمة: `starlette.iterate_in_threadpool` **لا**
  يقفل المُكرِّر المتزامن عند الإلغاء (لا `finally`/`close`) — عشان كده بنستخدم async
  generator صراحةً بدل مُكرِّر متزامن (Plan 10 §3.1).
- **بلا تحميل كامل:** بنقرأ `chunk_size` بايت في المرة، وبنتوقّف لو الملف اتغيّر حجمه
  عن المتوقّع (كشف تبديل/اقتطاع) بدل ما نكمل لبُعد غير محدود.
- **مفيش ادّعاء تسليم:** الرد بيوصف «السيرفر بعث للمتصفّح» بس؛ الحفظ/الرفع لـ
  OpenHands مش مُرصودين (Plan 09 §18–§19).
"""
from __future__ import annotations

import os
import re
import stat as _stat
from dataclasses import dataclass
from typing import AsyncIterator

from starlette.concurrency import run_in_threadpool
from starlette.responses import StreamingResponse

# شكل رمز الـ staging المُعتِم (نفس `secrets.token_hex(16)` ⇒ 32 محرف hex). المعرّف
# جاي من صفّ القاعدة (سيرفر-موثوق)؛ بنتحقّق منه كطبقة دفاع إضافية قبل أي لمس للمسار.
_STAGING_TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")

# حجم القطعة: 64 KiB — توازن بين عدد الرحلات للخيط والذاكرة (سقف الملف 3 MiB ⇒ ≤48 قطعة).
CHUNK_SIZE = 64 * 1024
# نوع MIME آمن عام (النوع الحقيقي مش مخزَّن محليًّا). `nosniff` بيمنع تخمين المتصفح.
DOWNLOAD_CONTENT_TYPE = "application/octet-stream"
# امتداد بديل لو اسم العرض مفيهوش امتداد صالح.
DEFAULT_DOWNLOAD_NAME = "attachment"

# محارف ASCII آمنة لاسم ملف هيدر `Content-Disposition` (نفس مجموعة التصدير):
# بنمنع CR/LF/اقتباس/محارف تحكّم ⇒ مفيش response-header injection.
_HEADER_SAFE_NAME = frozenset(
    ch for ch in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
)


class AttachmentDownloadError(RuntimeError):
    """فشل تنزيل مرفق: مش موجود/منتهي/غير صالح/عدم تطابق حجم (فشل مغلق)."""

    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class AttachmentDownload:
    """وصف تنزيل جاهز: مسار الملف المحلي (سيرفر-فقط) + الاسم الآمن + الحجم المتوقّع."""

    path: str
    filename: str
    size_bytes: int
    content_type: str = DOWNLOAD_CONTENT_TYPE


def resolve_staged_path(
    root, staging_token: str | None, *, expected_size: int | None, max_bytes: int
) -> tuple[str, int]:
    """يحلّ مسار ملف الـ staging من الرمز المُعتِم، بضوابط fail-closed، ويرجّع (path, size).

    الرمز جاي من صفّ القاعدة (سيرفر-موثوق) — مفيش أي مسار من العميل. الضوابط:
    - الرمز يطابق شكل `token_hex(16)` (مكوّن واحد، حروف hex) وإلا رفض — يمنع أي حقن مسار.
    - الجذر بيُطبَّع بـ `realpath` مرة واحدة؛ المسار = `root/token` (مكوّن واحد ⇒ مفيش
      اجتياز عبر مكوّنات أب).
    - `lstat` على المسار **بلا** اتّباع symlink: symlink (S_ISLNK) أو أي نوع غير ملف عادي
      (`S_ISREG`) ⇒ رفض. كده symlink في آخر مكوّن **مرفوض** (مش متبَع).
    - الحجم لازم يكون داخل `(0, max_bytes]`، ومطابقًا للحجم المخزَّن (`expected_size`) لو
      متوفّر ⇒ كشف تغيّر الحجم على القرص (اقتطاع/تبديل) **بالفشل المغلق** (500).
    - الفتح اللاحق (`open_staged_file`) بيعيد الفحص على الوصفة نفسها (`fstat` + تطابق
      الحجم + `O_NOFOLLOW`) ⇒ مفيش سباق بين الفحص والفتح.

    **حدود معروفة (F-02/F-03، بلا ادّعاء سلامة):** `O_NOFOLLOW` يحمي **آخر** مكوّن بس
    (مكوّنات الأب غير محميّة منفصلًا؛ الجذر مملوك للعملية وبصلاحية `0700` والاسم مُعتِم ⇒
    سطح الهجوم محلي فقط). وفحص الحجم **مش** بيكشف «استبدال بنفس الحجم»، ومفيش بصمة محتوى
    (سلامة المحتوى **غير** مُنفَّذة وغير مُدّعاة).
    """
    if not isinstance(staging_token, str) or not _STAGING_TOKEN_RE.match(staging_token):
        raise AttachmentDownloadError("unavailable", "الملف مش متاح دلوقتي.", 404)
    root = os.path.realpath(str(root))
    path = os.path.join(root, staging_token)
    try:
        st = os.lstat(path)
    except OSError as exc:
        raise AttachmentDownloadError("not_found", "الملف مش متاح دلوقتي.", 404) from exc
    if not _stat.S_ISREG(st.st_mode):
        raise AttachmentDownloadError("unavailable", "الملف مش متاح دلوقتي.", 404)
    size = st.st_size
    if size <= 0 or size > max_bytes:
        raise AttachmentDownloadError("unavailable", "الملف مش متاح دلوقتي.", 404)
    if expected_size is not None and int(expected_size) != size:
        # الملف على القرص اتغيّر عن الحجم المخزَّن ⇒ فشل مغلق (مفيش بثّ محتوى غير موثوق).
        raise AttachmentDownloadError("integrity", "الملف مش متاح دلوقتي.", 500)
    return path, size


def safe_download_filename(display_name: str | None, fallback: str = DEFAULT_DOWNLOAD_NAME) -> str:
    """اسم ملف آمن للتنزيل من `display_name` المخزَّن (سيرفر-موثوق).

    بنأخذ آخر مقطع (نمنع أي مكوّن مسار)، وبنشيل أي محرف مش في المجموعة الآمنة، وبنمنع
    القيم النقطية. لو النتيجة فاضية ⇒ الاسم البديل. **مفيش** اعتماد على أي اسم من العميل.
    """
    if not isinstance(display_name, str):
        return fallback
    base = display_name.replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = "".join(ch for ch in base if ch in _HEADER_SAFE_NAME)
    cleaned = cleaned.strip().strip(".")
    if not cleaned or cleaned in (".", ".."):
        return fallback
    return cleaned


def open_staged_file(path: str, expected_size: int, *, max_bytes: int) -> int:
    """يفتح ملف staging بأمان ويرجّع وصفة الملف (fd) — أو يرمي `AttachmentDownloadError`.

    الضوابط (كلها fail-closed):
    - `O_NOFOLLOW`: يمنع اتّباع symlink في **آخر** مكوّن من المسار (لو مدعوم).
    - `os.fstat` على الوصفة المفتوحة: لازم يكون ملف عادي (`S_ISREG`) — يرفض الأجهزة/FIFO/
      المقابس. الفحص على الوصفة نفسها (مش على المسار) ⇒ مفيش سباق مسار↔فتح.
    - تطابق الحجم الفعلي مع `expected_size` المخزَّن، وعدم تجاوز `max_bytes`.
    """
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except FileNotFoundError as exc:
        raise AttachmentDownloadError(
            "not_found", "الملف مش متاح دلوقتي.", 404
        ) from exc
    except OSError as exc:
        # ELOOP (symlink) أو أي فشل فتح تاني ⇒ فشل مغلق بلا تفاصيل نظام ملفات.
        raise AttachmentDownloadError(
            "unavailable", "الملف مش متاح دلوقتي.", 404
        ) from exc
    try:
        st = os.fstat(fd)
    except OSError as exc:
        os.close(fd)
        raise AttachmentDownloadError(
            "unavailable", "الملف مش متاح دلوقتي.", 404
        ) from exc
    if not _stat.S_ISREG(st.st_mode):
        os.close(fd)
        raise AttachmentDownloadError("unavailable", "الملف مش متاح دلوقتي.", 404)
    if st.st_size != expected_size or st.st_size > max_bytes:
        os.close(fd)
        raise AttachmentDownloadError(
            "integrity", "الملف مش متاح دلوقتي.", 500
        )
    return fd


def _read_chunk(fd: int, chunk_size: int) -> bytes:
    return os.read(fd, chunk_size)


class OwnedStreamingResponse(StreamingResponse):
    """`StreamingResponse` يضمن إغلاق مُكرِّر الجسم **حتميًّا** عند أي خروج.

    على ASGI ≥ 2.4 (المسار الافتراضي في uvicorn)، عند انقطاع العميل يرمي `stream_response`
    استثناء `OSError` ⇒ `ClientDisconnect`، و**مش** بيقفل المُكرِّر غير المتزامن (الـ fd
    بيتقفل بس عند الـ GC — غير حتمي). عشان كده بنلفّ `__call__` وننادي `aclose()` في
    `finally` لكل خروج (نجاح/خطأ/انقطاع/إلغاء) ⇒ إغلاق الـ fd حتمي (متطلّب F-01).
    """

    async def __call__(self, scope, receive, send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            aclose = getattr(self.body_iterator, "aclose", None)
            if aclose is not None:
                try:
                    await aclose()
                except RuntimeError:
                    # مُكرِّر بيشتغل بالفعل أو حلقة مغلقة ⇒ الـ GC هيتولّى الإغلاق.
                    pass


async def iter_file_chunks(
    fd: int,
    expected_size: int,
    *,
    chunk_size: int = CHUNK_SIZE,
) -> AsyncIterator[bytes]:
    """مُكرِّر غير متزامن يقرأ الملف على دفعات في خيط عامل ويقفل الوصفة دائمًا.

    - كل `os.read` عبر `run_in_threadpool` ⇒ مفيش حجب لحلقة الأحداث المشتركة.
    - `finally` يقفل الوصفة على النجاح/الاستثناء/الإلغاء (انقطاع العميل يلغي الـ await
      ⇒ الاستثناء يمرّ من `finally` ⇒ إغلاق حتمي).
    - لو القراءة رجعت صفر بايت قبل ما نوصّل `expected_size` (اقتطاع/تبديل، أو كنس
      الانتهاء شال الملف بعد الفتح) ⇒ نتوقّف بخطأ بدل ما نكمل — الرد بيُقطع (مفيش
      ادّعاء نجاح كاذب).
    """
    sent = 0
    try:
        while sent < expected_size:
            want = min(chunk_size, expected_size - sent)
            chunk = await run_in_threadpool(_read_chunk, fd, want)
            if not chunk:
                # نهاية ملف مبكّرة ⇒ الملف اتغيّر تحتنا (اقتطاع/تبديل/كنس). نوقف.
                raise AttachmentDownloadError(
                    "integrity", "الملف اتغيّر أثناء التنزيل.", 500
                )
            sent += len(chunk)
            yield chunk
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


__all__ = [
    "CHUNK_SIZE",
    "DOWNLOAD_CONTENT_TYPE",
    "DEFAULT_DOWNLOAD_NAME",
    "AttachmentDownload",
    "AttachmentDownloadError",
    "OwnedStreamingResponse",
    "resolve_staged_path",
    "safe_download_filename",
    "open_staged_file",
    "iter_file_chunks",
]
