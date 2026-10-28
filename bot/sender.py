"""إرسال الرسايل الطويلة: تقسيم، أو ملف .md لو زادت عن 3 أجزاء.

`send_long` بتستقبل نص خام (مش HTML)، وتهرّبه قبل الإرسال عشان أي `<` أو `&`
في رد الـ agent ما يكسّرش رسالة تيليجرام.
"""
from __future__ import annotations

import io

from telegram import InputFile
from telegram.constants import ParseMode

from .messages import MAX_PARTS, escape_html, split_message

COPY_PART_LIMIT = 3900  # هامش أمان تحت 4096


async def _send_report_file(chat_id: int, text: str, bot) -> None:
    """إرسال النص كملف report.md (المسار المشترك لما يزيد عن MAX_PARTS)."""
    buffer = io.BytesIO(text.encode("utf-8"))
    buffer.name = "report.md"
    await bot.send_document(chat_id=chat_id, document=InputFile(buffer, filename="report.md"))


async def send_long(chat_id: int, text: str, bot) -> None:
    parts = split_message(text)
    if len(parts) <= MAX_PARTS:
        for part in parts:
            await bot.send_message(chat_id=chat_id, text=escape_html(part), parse_mode=ParseMode.HTML)
        return
    await _send_report_file(chat_id, text, bot)


async def send_copyable(chat_id: int, text: str, bot) -> None:
    """يبعت النص جوه <pre> (الضغط على code block في تيليجرام بينسخه كله)."""
    parts = split_message(text, limit=COPY_PART_LIMIT)
    if len(parts) <= MAX_PARTS:
        for part in parts:
            await bot.send_message(
                chat_id=chat_id,
                text=f"<pre>{escape_html(part)}</pre>",
                parse_mode=ParseMode.HTML,
            )
        return
    await _send_report_file(chat_id, text, bot)
