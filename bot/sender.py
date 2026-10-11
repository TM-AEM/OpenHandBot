"""إرسال الرسايل الطويلة: تقسيم، أو ملف .md لو زادت عن 3 أجزاء.

`send_long` بتستقبل نص خام (مش HTML)، وتهرّبه قبل الإرسال عشان أي `<` أو `&`
في رد الـ agent ما يكسّرش رسالة تيليجرام.
"""
from __future__ import annotations

import io

from telegram import InputFile
from telegram.constants import ParseMode

from .messages import MAX_PARTS, escape_html, split_message


async def send_long(chat_id: int, text: str, bot) -> None:
    parts = split_message(text)
    if len(parts) <= MAX_PARTS:
        for part in parts:
            await bot.send_message(chat_id=chat_id, text=escape_html(part), parse_mode=ParseMode.HTML)
        return
    buffer = io.BytesIO(text.encode("utf-8"))
    buffer.name = "report.md"
    await bot.send_document(chat_id=chat_id, document=InputFile(buffer, filename="report.md"))
