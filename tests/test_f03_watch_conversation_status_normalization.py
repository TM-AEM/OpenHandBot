"""OHB2 WP-06 Part 1 / `DEF-009` — اختبار تمييزي لتطبيع الحالة في `watch_conversation`.

الفجوة اللي الاختبار ده بيسدّها: `tests/test_f03_status_label_end_to_end.py` بيغطّي
`show_status` بس. مسار `watch_conversation` — اللي بيخزّن `last_state` اللي
`watches_menu` بيعرضه — ما كانش مغطّى بأي اختبار تمييزي: الاختبارات الموجودة
بتستخدم `execution_status="running"`، والقيمة دي **زي ما هي** بعد التطبيع، فالطفرات
في المسار ده ما كانتش بتتكشف.

الاختبار ده بيفشل لو `watch_conversation` خزّن `conv.get("execution_status")` الخام
بدل `get_status(conv)`:
- `execution_status="FINISHED"` ⇒ لازم يتخزّن `"finished"` (مش `"FINISHED"`)،
  وإلا `watches_menu` هيعرض النص الإنجليزي الخام.
"""
import asyncio

import bot.handlers as h
from tests.test_handlers import DetailClient, _cb_update, _ctx_with


def _stored_last_state(ctx, conversation_id):
    return next(w.last_state for w in ctx.bot_data["db"].list_watched() if w.conversation_id == conversation_id)


def test_watch_conversation_stores_normalized_uppercase_status(tmp_path):
    """`execution_status="FINISHED"` ⇒ `last_state="finished"` (مش النص الخام)."""
    client = DetailClient({"id": "c1", "title": "شات", "execution_status": "FINISHED"})
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "watch:c1")

    asyncio.run(h.watch_conversation(update, ctx))

    assert _stored_last_state(ctx, "c1") == "finished"


def test_watch_conversation_stores_sandbox_error_status(tmp_path):
    """`sandbox_status=ERROR` ⇒ `last_state="sandbox_error"` (نفس تفسير `show_status`)."""
    client = DetailClient(
        {"id": "c1", "title": "شات", "execution_status": "running", "sandbox_status": "ERROR"}
    )
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(1, "watch:c1")

    asyncio.run(h.watch_conversation(update, ctx))

    assert _stored_last_state(ctx, "c1") == "sandbox_error"
