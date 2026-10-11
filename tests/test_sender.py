import asyncio

from bot.sender import send_long


class FakeBot:
    def __init__(self):
        self.messages = []
        self.documents = []

    async def send_message(self, chat_id=None, text=None, parse_mode=None, **kw):
        self.messages.append(text)

    async def send_document(self, chat_id=None, document=None, **kw):
        self.documents.append(document)


def test_short_message_single_send():
    bot = FakeBot()
    asyncio.run(send_long(1, "مرحبا", bot))
    assert bot.messages == ["مرحبا"]
    assert bot.documents == []


def test_three_parts_still_messages():
    bot = FakeBot()
    text = "ب" * 5000  # partان
    asyncio.run(send_long(1, text, bot))
    assert bot.documents == []
    assert len(bot.messages) == 2


def test_more_than_three_parts_sends_document():
    bot = FakeBot()
    text = "ب" * 20000  # أكثر من 3 أجزاء
    asyncio.run(send_long(1, text, bot))
    assert bot.messages == []
    assert len(bot.documents) == 1
