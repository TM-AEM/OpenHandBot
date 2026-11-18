"""OHB2-WP-07 — اختبارات: عدم تجديد مهلة `route` عند نص مسافات فقط، ومواءمة سياسة
الاستطلاع المتسلسل مع الوثائق (`DEF-006`, `DEF-013`).

الجزء المُنفَّذ هنا محصور في العناصر **غير المسدودة** على قرار مالك:
- تجديد مهلة `route` (`db.renew_awaiting`) لازم يحدث **بعد** التحقق من أن النص غير
  فراغ (قرار `WP-07` البند 1) — نص مسافات لا يجدّد المهلة.
- تعليقات `bot/app.py` تطابق `docs/OPERATIONS_RUNBOOK.md` (استطلاع متسلسل، `OD-04`).
تعديل الاتزام التزامن (`OD-04`) وخفض كتل الإدخال/الإخراج (`DEF-011`) خارج النطاق هنا.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import bot.handlers as h
from bot.db import AWAITING_TTL, Database


def _ctx(tmp_path):
    ctx = __import__("tests.test_handlers", fromlist=["make_context"]).make_context(1, tmp_path)
    return ctx


def _text_update(text, update_id):
    from types import SimpleNamespace

    msg = SimpleNamespace(text=text, replies=[], edit_text=None)

    async def _reply(t, **kw):
        msg.replies.append(t)
        return msg

    msg.reply_text = _reply
    return SimpleNamespace(
        update_id=update_id,
        effective_user=SimpleNamespace(id=1),
        effective_chat=SimpleNamespace(id=99, type="private"),
        message=msg,
        callback_query=None,
    )


def test_route_whitespace_does_not_renew_ttl(tmp_path):
    ctx = _ctx(tmp_path)
    db: Database = ctx.bot_data["db"]
    db.set_awaiting(1, "c1", "route", title="شات")
    before = db.awaiting_state(1)[3]

    update = _text_update("   ", 9100)
    asyncio.run(h.handle_text(update, ctx))

    after = db.awaiting_state(1)[3]
    assert after == before, "نص مسافات جدّد مهلة route (ممنوع)"

    update2 = _text_update("برومت حقيقي", 9101)
    asyncio.run(h.handle_text(update2, ctx))
    renewed = db.awaiting_state(1)[3]
    assert renewed > before, "النص الحقيقي لازم يجدّد المهلة"


def test_route_valid_text_renews_ttl(tmp_path):
    ctx = _ctx(tmp_path)
    db: Database = ctx.bot_data["db"]
    # مهلة قاربت على الانتهاء، ثم رسالة حقيقية تجدّدها.
    stale = datetime.now(timezone.utc) - (AWAITING_TTL - timedelta(minutes=1))
    db.set_awaiting(1, "c1", "route", now=stale)
    update = _text_update("برومت", 9102)
    asyncio.run(h.handle_text(update, ctx))
    assert db.awaiting_state(1)[1] == "route"
    assert db.awaiting_state(1)[3] > stale
