"""أهلية النصّ المصاحب وتطبيع Unicode (OHB2-P0-A3 — D-28).

قواعد **D-28** (سياسة مالك، محسومة) — تُنفَّذ **حرفيًّا**، وبلا توسيع:

1. توحيد **نهايات السطر فقط**: `CRLF` ⇒ `LF`، ثم `CR` ⇒ `LF` (لا تطبيع آخر).
2. رفض `NUL` ومحارف التحكّم **C0/C1**، **عدا `TAB` (`U+0009`) و`LF` (`U+000A`)**.
3. اشتراط وجود **محرف واحد غير مسافة على الأقل**.
4. قياس الطول بـ **عدد نقاط Unicode (code points)** للنصّ بعد التوحيد.
5. القبول بحدّ **4096 code point** كحدّ أقصى.
6. رفض ما يتجاوز الحدّ؛ **بلا قصّ صامت أبدًا**.
7. الحفاظ على النصّ العربي وسائر Unicode الصالح كما هو.
8. **بلا `NFC`** وبلا أي تطبيع Unicode أوسع.
9. **بلا حذف صامت** للمحارف الممنوعة (رفض صريح بدل الحذف).

**ترتيب العمليات (صريح، مطابق لسجل القرار D-28):** (أ) توحيد نهايات السطر، ثم (ب) التحقّق
(وجود ≥1 غير مسافة + رفض محارف التحكّم الممنوعة)، ثم (ج) قياس الطول (≤4096 code point) على
النصّ بعد التوحيد.

المقياس **code points** (`len(str)` في Python = عدد نقاط Unicode) — مش bytes ولا graphemes؛
وبالتالي النصّ العربي والرموز المركّبة لا تُحتسب غلط.

الوحدة **نقيّة** (بلا قاعدة بيانات/شبكة/حالة) وقابلة لإعادة الاستخدام. لا تُصرّح بأي إرسال.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# الحدّ الأقصى بعد التوحيد (D-28 بند 5). مقياس: code points.
MAX_ACCOMPANYING_TEXT_CODEPOINTS = 4096

# `TAB` و`LF` مسموحان رغم كونهما محارف تحكّم C0 (D-28 بند 2).
_ALLOWED_CONTROL_CODEPOINTS = frozenset({0x09, 0x0A})


def _is_prohibited_control(ch: str) -> bool:
    """محرف تحكّم ممنوع؟ NUL وC0 (`U+0000–U+001F`) وC1 (`U+0080–U+009F`).

    `TAB`/`LF` مستثنيان (D-28 بند 2). نطاق `C0`/`C1` **حصريًّا** حسب نصّ القرار (لا نوسّع
    لمحارف تحكّم أخرى غير مذكورة مثل `DEL`).
    """
    cp = ord(ch)
    if cp in _ALLOWED_CONTROL_CODEPOINTS:
        return False
    return cp <= 0x1F or 0x80 <= cp <= 0x9F


class TextEligibility(str, Enum):
    """نتيجة أهلية النصّ المصاحب (D-28)."""

    ELIGIBLE = "eligible"
    EMPTY = "empty"                      # نصّ فاضي (بلا محارف أصلًا)
    WHITESPACE_ONLY = "whitespace_only"  # مسافات/نهايات سطر بس ⇒ مفيش محرف غير مسافة
    CONTROL_CHARS = "control_chars"      # فيه محرف تحكّم ممنوع
    TOO_LONG = "too_long"                # يتجاوز 4096 code point


@dataclass(frozen=True)
class TextValidation:
    """نتيجة تحقّق نصّ مصاحب (D-28)."""

    eligibility: TextEligibility
    normalized: str   # النصّ بعد توحيد نهايات السطر (دايمًا موجود، حتى عند الرفض)
    code_points: int  # عدد code points للنصّ بعد التوحيد

    @property
    def eligible(self) -> bool:
        return self.eligibility is TextEligibility.ELIGIBLE


def normalize_line_endings(text: str) -> str:
    """توحيد `CRLF`/`CR` إلى `LF` فقط (D-28 بند 1). بلا أي تطبيع Unicode آخر.

    الترتيب مهمّ: `CRLF` قبل `CR` (وإلا لتحوّل `CRLF` إلى `LF\\n`).
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


def validate_accompanying_text(text: str | None) -> TextValidation:
    """يتحقّق من نصّ مصاحب وفق **D-28** بالترتيب الصريح (توحيد ⇒ تحقّق ⇒ قياس).

    بترجّع `TextValidation` (eligibility + النصّ الموحَّد + عدد code points). المستدعي
    **ما ينشرش** إلّا لما `eligible` تكون True، وبيخزّن `normalized` كما هي (بلا تطبيع آخر).
    """
    if not isinstance(text, str) or text == "":
        return TextValidation(TextEligibility.EMPTY, "", 0)

    # (أ) توحيد نهايات السطر فقط.
    normalized = normalize_line_endings(text)

    # (ب1) وجود محرف واحد غير مسافة على الأقل.
    if normalized.strip() == "":
        return TextValidation(
            TextEligibility.WHITESPACE_ONLY, normalized, len(normalized)
        )

    # (ب2) رفض محارف التحكّم الممنوعة (بلا حذف صامت — رفض صريح).
    if any(_is_prohibited_control(ch) for ch in normalized):
        return TextValidation(
            TextEligibility.CONTROL_CHARS, normalized, len(normalized)
        )

    # (ج) قياس الطول على النصّ بعد التوحيد.
    code_points = len(normalized)
    if code_points > MAX_ACCOMPANYING_TEXT_CODEPOINTS:
        return TextValidation(TextEligibility.TOO_LONG, normalized, code_points)

    return TextValidation(TextEligibility.ELIGIBLE, normalized, code_points)
