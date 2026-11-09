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

# OHB2-BOT-REPLY-TXT-FILE-BUTTON: ملف الرد الكامل كـ .txt (إجراء منفصل عن «نسخ الرد»).
TXT_FILENAME = "reply.txt"
# حد رفع المستندات في Bot API = 50 ميجابايت. بنرفض بوضوح بدل ما نرفع ملف مقصوص.
TELEGRAM_DOCUMENT_MAX_BYTES = 50 * 1024 * 1024


class TextDocumentTooLargeError(Exception):
    """الرد الكامل أكبر من حد رفع المستندات في تيليجرام (مفيش قصّ صامت)."""


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


async def send_text_document(chat_id: int, text: str, bot, *, reply_to_message_id: int | None = None) -> None:
    """OHB2-BOT-REPLY-TXT-FILE-BUTTON: يبعت الرد الكامل كملف `.txt` (UTF-8، بلا قصّ).

    - نفس المحتوى الخام الكامل (مفيش تهريب HTML ولا تقسيم).
    - رفع في الذاكرة عبر `InputFile` (مفيش ملفات مؤقتة على القرص).
    - `reply_to_message_id` يربط المستند برسالة الرد الأصلية، مع `allow_sending_without_reply`
      عشان مايفشلش لو الرسالة الأصلية قديمة/اتشالت.
    - لو المحتوى أكبر من حد رفع المستندات ⇒ `TextDocumentTooLargeError` (مفيش قصّ صامت).
    """
    data = text.encode("utf-8")
    if len(data) > TELEGRAM_DOCUMENT_MAX_BYTES:
        raise TextDocumentTooLargeError(
            f"document is {len(data)} bytes > limit {TELEGRAM_DOCUMENT_MAX_BYTES}"
        )
    document = InputFile(data, filename=TXT_FILENAME)
    kwargs: dict = {"chat_id": chat_id, "document": document}
    if reply_to_message_id is not None:
        kwargs["reply_to_message_id"] = reply_to_message_id
        kwargs["allow_sending_without_reply"] = True
    await bot.send_document(**kwargs)
