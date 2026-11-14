import asyncio

from bot.sender import send_long


class FakeBot:
    def __init__(self):
        self.messages = []
        self.documents = []

    async def send_message(self, chat_id=None, text=None, parse_mode=None, **kw):
        self.messages.append((text, parse_mode))

    async def send_document(self, chat_id=None, document=None, **kw):
        self.documents.append(document)


def test_short_message_single_send():
    bot = FakeBot()
    asyncio.run(send_long(1, "مرحبا", bot))
    assert [m[0] for m in bot.messages] == ["مرحبا"]
    assert bot.documents == []


def test_short_message_is_html_escaped():
    bot = FakeBot()
    asyncio.run(send_long(1, "رد <b>&</b>", bot))
    assert [m[0] for m in bot.messages] == ["رد &lt;b&gt;&amp;&lt;/b&gt;"]


def test_two_parts_still_messages_and_within_limit():
    bot = FakeBot()
    text = "ب" * 5000  # جزئين
    asyncio.run(send_long(1, text, bot))
    assert bot.documents == []
    assert len(bot.messages) == 2
    # كل جزء بعد التهريب جوه حد تيليجرام (4096 بعد فك الكيانات).
    import html

    for sent, _ in bot.messages:
        assert len(html.unescape(sent)) <= 4096


def test_more_than_three_parts_sends_document():
    bot = FakeBot()
    text = "ب" * 20000  # أكثر من 3 أجزاء
    asyncio.run(send_long(1, text, bot))
    assert bot.messages == []
    assert len(bot.documents) == 1


def test_send_long_preserves_all_content():
    # نص بأجزاء متعددة (HTML chars + عربي + سطور جديدة). لازم إعادة تركيب
    # المحتوى بعد فك كيانات HTML ترجّع النص الأصلي كامل بنفس الترتيب.
    import html

    bot = FakeBot()
    text = ("سطر <b>&x</b>\n" * 400).strip()
    asyncio.run(send_long(1, text, bot))
    assert bot.documents == []
    rebuilt = "".join(html.unescape(m[0]) for m in bot.messages)
    assert rebuilt == text


def test_send_long_uses_html_parse_mode():
    from telegram.constants import ParseMode

    bot = FakeBot()
    text = "سطر\n" * 2000
    asyncio.run(send_long(1, text, bot))
    assert bot.messages
    assert all(mode == ParseMode.HTML for _, mode in bot.messages)


# =====================================================================
# TASK 55 (المرحلة B): send_copyable — الرد جوه <pre> قابل للنسخ
# =====================================================================
from bot.sender import COPY_PART_LIMIT, send_copyable  # noqa: E402


def test_send_copyable_wraps_in_pre_and_escapes():
    bot = FakeBot()
    asyncio.run(send_copyable(1, "رد <b>&</b>", bot))
    assert bot.documents == []
    assert [m[0] for m in bot.messages] == ["<pre>رد &lt;b&gt;&amp;&lt;/b&gt;</pre>"]


def test_send_copyable_uses_html_parse_mode():
    from telegram.constants import ParseMode

    bot = FakeBot()
    asyncio.run(send_copyable(1, "نص", bot))
    assert all(mode == ParseMode.HTML for _, mode in bot.messages)


def test_send_copyable_long_splits_at_copy_limit():
    bot = FakeBot()
    text = "ب" * (COPY_PART_LIMIT * 2 + 50)  # 3 أجزاء بحد النسخ
    asyncio.run(send_copyable(1, text, bot))
    assert bot.documents == []
    assert len(bot.messages) == 3
    assert all(m[0].startswith("<pre>") and m[0].endswith("</pre>") for m in bot.messages)


def test_send_copyable_too_long_sends_document():
    bot = FakeBot()
    text = "ب" * (COPY_PART_LIMIT * 4)  # أكثر من 3 أجزاء
    asyncio.run(send_copyable(1, text, bot))
    assert bot.messages == []
    assert len(bot.documents) == 1
