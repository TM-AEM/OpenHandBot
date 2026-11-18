"""OHB2 F-03 / `DEF-009` — اختبار انحدار **تمييزي** من طرف إلى طرف لتطبيع الحالة.

الفجوة (F-03 من المراجعة التراكمية): «تطبيع `DEF-009` مش مثبَّت من طرف إلى طرف — مفيش
اختبار يتحقّق من التسمية **المرئية للمستخدم** لمحادثة `execution_status` بتاعها غايب
(`get_status({}) == "unknown"` → `"غير معروف"`).»

الاختبارات دي بتمرّ من **مسار الـ handler الحقيقي** (`bot.handlers.show_status` + تفويض
`FileService`) وتتحقّق من النص اللي المستخدم بيشوفه فعلًا في تيليجرام. وهي **تمييزية**:
- إرجاع `state_label(conv.get("execution_status"))` (بدل `get_status`) ⇒ يفشل (حروف كبيرة
  وسandbox ERROR بيتعرضوا خام).
- شيل `STATE_LABELS["unknown"]` ⇒ يفشل (بيتعرض «unknown» الإنجليزي).
"""
import asyncio

import bot.handlers as h
from tests.test_handlers import DetailClient, _cb_update, _ctx_with


def test_show_status_absent_execution_status_shows_arabic_unknown(tmp_path):
    """محادثة بلا `execution_status` ⇒ «الحالة: غير معروف» (مش «unknown» الخام)."""
    client = DetailClient({"id": "c1", "title": "شات"})  # مفيش execution_status خالص
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "status:c1")

    asyncio.run(h.show_status(update, ctx))

    text = update.callback_query.edits[-1]
    assert "الحالة: غير معروف" in text
    assert "unknown" not in text


def test_show_status_normalizes_uppercase_status(tmp_path):
    """`execution_status` بحروف كبيرة ⇒ تسمية عربية معيارية (مش النص الخام)."""
    client = DetailClient({"id": "c1", "title": "شات", "execution_status": "FINISHED"})
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "status:c1")

    asyncio.run(h.show_status(update, ctx))

    text = update.callback_query.edits[-1]
    assert "الحالة: منتهي" in text
    assert "FINISHED" not in text


def test_show_status_sandbox_error_overrides_execution_status(tmp_path):
    """`sandbox_status=ERROR` يتفوّق على `execution_status` ⇒ «الحالة: خطأ بيئة»."""
    client = DetailClient(
        {"id": "c1", "title": "شات", "execution_status": "running", "sandbox_status": "ERROR"}
    )
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "status:c1")

    asyncio.run(h.show_status(update, ctx))

    text = update.callback_query.edits[-1]
    assert "الحالة: خطأ بيئة" in text
