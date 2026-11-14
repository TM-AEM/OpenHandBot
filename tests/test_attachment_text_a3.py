"""OHB2-P0-A3/D-28 — اختبارات أهلية النصّ المصاحب وتطبيع Unicode (وحدة نقيّة).

تغطّي قواعد D-28 **حرفيًّا** وترتيب العمليات (توحيد ⇒ تحقّق ⇒ قياس):
فاضي/مسافات، عربي، Unicode مختلط، توحيد CRLF/CR، قبول TAB/LF، رفض NUL، رفض C0/C1،
حدّ 4096/4097 code point، بلا قصّ صامت، بلا NFC، حفظ Unicode الصالح.

مفيش قاعدة بيانات/شبكة: الدالة نقيّة.
"""
from __future__ import annotations

import unicodedata

from bot.attachment_text import (
    MAX_ACCOMPANYING_TEXT_CODEPOINTS,
    TextEligibility,
    normalize_line_endings,
    validate_accompanying_text,
)


# ------------------------------------------------------------------ فاضي/مسافات
def test_empty_text_is_ineligible():
    v = validate_accompanying_text("")
    assert v.eligibility is TextEligibility.EMPTY
    assert not v.eligible
    assert v.code_points == 0


def test_none_is_ineligible_and_not_crashing():
    v = validate_accompanying_text(None)
    assert v.eligibility is TextEligibility.EMPTY
    assert not v.eligible


def test_whitespace_only_is_ineligible():
    for ws in ("   ", "\t", "\n", " \t\n ", "\u00a0", "\u2003"):
        v = validate_accompanying_text(ws)
        assert v.eligibility is TextEligibility.WHITESPACE_ONLY, repr(ws)
        assert not v.eligible


# ------------------------------------------------------------------ قبول عربي/Unicode
def test_arabic_text_is_eligible_and_preserved():
    text = "أرسل هذا النصّ مع الملف"
    v = validate_accompanying_text(text)
    assert v.eligible
    assert v.normalized == text
    assert v.code_points == len(text)


def test_mixed_unicode_is_eligible_and_preserved():
    text = "Hello مرحبا 123 — ✅ émoji 🚀"
    v = validate_accompanying_text(text)
    assert v.eligible
    assert v.normalized == text


def test_no_nfc_normalization():
    # U+0627 (ا) + U+0654 (همزة أعلاه) يجب أن تبقى محرفين كما هي، **بدون** تحويلها لـ U+0623 (أ).
    decomposed = "ا\u0654"
    assert decomposed != "\u0623"
    v = validate_accompanying_text(decomposed)
    assert v.eligible
    assert v.normalized == decomposed            # مفيش تطبيع
    assert v.code_points == 2                     # محرفان (code points)
    assert unicodedata.normalize("NFC", decomposed) != decomposed  # إثبات إن NFC كان هيغيّرها


# ------------------------------------------------------------------ توحيد نهايات السطر
def test_crlf_and_cr_are_normalized_to_lf():
    assert normalize_line_endings("a\r\nb\rc\nd") == "a\nb\nc\nd"
    v = validate_accompanying_text("سطر١\r\nسطر٢\rسطر٣\nسطر٤")
    assert v.eligible
    assert v.normalized == "سطر١\nسطر٢\nسطر٣\nسطر٤"
    assert "\r" not in v.normalized


def test_crlf_before_cr_ordering():
    # لو عُكس الترتيب لتحوّل CRLF إلى "\n\n".
    assert normalize_line_endings("a\r\nb") == "a\nb"


# ------------------------------------------------------------------ TAB/LF مسموحان
def test_tab_and_lf_are_accepted():
    v = validate_accompanying_text("a\tb\nc")
    assert v.eligible
    assert v.normalized == "a\tb\nc"


# ------------------------------------------------------------------ رفض محارف التحكّم
def test_nul_is_rejected():
    v = validate_accompanying_text("a\x00b")
    assert v.eligibility is TextEligibility.CONTROL_CHARS
    assert not v.eligible
    assert "\x00" in v.normalized  # بلا حذف صامت


def test_prohibited_c0_is_rejected_except_tab_lf():
    for cp in (0x01, 0x07, 0x08, 0x0B, 0x0C, 0x1B, 0x1F):
        v = validate_accompanying_text("x" + chr(cp) + "y")
        assert v.eligibility is TextEligibility.CONTROL_CHARS, hex(cp)


def test_prohibited_c1_is_rejected():
    for cp in (0x80, 0x85, 0x9F):
        v = validate_accompanying_text("x" + chr(cp) + "y")
        assert v.eligibility is TextEligibility.CONTROL_CHARS, hex(cp)


def test_prohibited_chars_are_not_silently_deleted():
    text = "a\x07b\x00c"
    v = validate_accompanying_text(text)
    assert not v.eligible
    # النصّ (بعد التوحيد) محفوظ كما هو — الرفض صريح، مفيش حذف.
    assert v.normalized == text


# ------------------------------------------------------------------ الحدّ 4096/4097
def test_exactly_4096_codepoints_is_eligible():
    text = "a" * MAX_ACCOMPANYING_TEXT_CODEPOINTS
    v = validate_accompanying_text(text)
    assert v.eligible
    assert v.code_points == 4096


def test_4097_codepoints_is_rejected_without_truncation():
    text = "a" * (MAX_ACCOMPANYING_TEXT_CODEPOINTS + 1)
    v = validate_accompanying_text(text)
    assert v.eligibility is TextEligibility.TOO_LONG
    assert v.code_points == 4097
    assert v.normalized == text  # مفيش قصّ صامت


def test_limit_is_measured_after_line_ending_normalization():
    # 2048 × ("a" + CRLF) ⇒ بعد التوحيد 4096 code point ⇒ مؤهّل.
    at_limit = ("a\r\n") * 2048
    v1 = validate_accompanying_text(at_limit)
    assert v1.eligible
    assert v1.code_points == 4096
    # إضافة CRLF واحد ⇒ 4097 code point بعد التوحيد ⇒ مرفوض.
    over = at_limit + "\r\n"
    v2 = validate_accompanying_text(over)
    assert v2.eligibility is TextEligibility.TOO_LONG
    assert v2.code_points == 4097


def test_arabic_length_is_counted_in_codepoints_not_bytes():
    # 2000 محرف عربي ⇒ 2000 code point (مؤهّل) رغم إنّها 4000 byte في UTF-8.
    text = "م" * 2000
    v = validate_accompanying_text(text)
    assert v.eligible
    assert v.code_points == 2000
    assert len(text.encode("utf-8")) == 4000


def test_control_rejection_takes_precedence_over_length():
    # نصّ طويل فيه محرف تحكّم ⇒ رفض التحكّم (التحقّق قبل القياس حسب الترتيب الصريح).
    text = ("a" * 5000) + "\x07"
    v = validate_accompanying_text(text)
    assert v.eligibility is TextEligibility.CONTROL_CHARS
