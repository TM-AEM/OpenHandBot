"""OHB2-BOT-REPLY-TXT-FILE-BUTTON: زر «ملف النص» — تنزيل الرد الكامل كملف .txt.

إجراء **منفصل** عن «نسخ الرد» (`copy:`) و«عرض كامل» (`full:`): callback مختلف (`txt:`)
ومسار إرسال مختلف (`send_document`). المصدر هو **الرد الكامل** من الـ API (نفس مصدر
copy/full)، مش نص رسالة تيليجرام واحدة. كل نداءات تيليجرام مموّهة (مفيش رسايل حقيقية).
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import bot.handlers as h
import bot.sender as sender
from bot import keyboards as kb
from bot.db import Database
from bot.sender import TXT_FILENAME, TextDocumentTooLargeError, send_text_document

OWNER_UUID = "owner-uuid-123"
CONV = {"id": "A", "title": "شات A", "execution_status": "finished", "selected_repository": "o/r"}
CB = SimpleNamespace(chat_id=99, message_id=555)


# ----------------------------------------------------------------- harness
class FakeConfig:
    def __init__(self, allowed_id=1):
        self.allowed_telegram_ids = frozenset({allowed_id})
        self.owner_id = allowed_id
        self.openhands_base_url = "https://app.all-hands.dev"
        self.mini_app_enabled = False
        self.mini_app_url = ""

    def is_allowed(self, user_id):
        return user_id in self.allowed_telegram_ids


class FakeClient:
    def __init__(self, conv=CONV, user_text="برومتي", reply="ردي", *, exchange_error=None):
        self._conv = conv
        self._user_text = user_text
        self._reply = reply
        self._exchange_error = exchange_error
        self.exchange_calls = 0

    async def get_conversations(self, ids):
        if not self._conv:
            return []
        return [{**self._conv,
                 "created_by_user_id": self._conv.get("created_by_user_id", OWNER_UUID)}]

    async def get_current_user(self):
        return {"id": OWNER_UUID}

    async def get_last_exchange(self, cid):
        self.exchange_calls += 1
        if self._exchange_error:
            raise self._exchange_error
        return (self._user_text, self._reply)


class TxtRecBot:
    """بوت مموّه: يلتقط الرسايل والمستندات ومعاملات الإرسال، مع إمكانية فشل مُبرمَج."""

    def __init__(self, *, fail_document=None):
        self.messages = []
        self.documents = []
        self.doc_kwargs = []
        self.doc_chat_ids = []
        self._fail_document = fail_document

    async def send_message(self, chat_id=None, text=None, **kw):
        self.messages.append((text, kw.get("parse_mode")))

    async def send_document(self, chat_id=None, document=None, **kw):
        if self._fail_document is not None:
            raise self._fail_document
        self.documents.append(document)
        self.doc_chat_ids.append(chat_id)
        self.doc_kwargs.append(kw)


class CQ:
    def __init__(self, data, *, message_id=555):
        self.data = data
        self.edits = []
        self.message = SimpleNamespace(chat_id=99, message_id=message_id)
        self.answered = 0

    async def answer(self):
        self.answered += 1

    async def edit_message_text(self, text, **kw):
        self.edits.append(text)


def _update(q, user_id=1, chat_type="private"):
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_chat=SimpleNamespace(id=99, type=chat_type),
        callback_query=q,
        message=None,
    )


def _ctx(tmp_path, client, bot=None):
    ctx = SimpleNamespace()
    ctx.bot_data = {
        "config": FakeConfig(1),
        "db": Database(str(tmp_path / "t.sqlite3")),
        "client": client,
    }
    ctx.bot = bot if bot is not None else TxtRecBot()
    return ctx


def _run_txt(ctx, q, user_id=1, chat_type="private"):
    asyncio.run(h.send_reply_txt(_update(q, user_id, chat_type), ctx))


# -------------------------------------------- 1. الزر في الكيبورد الصحيح
def test_txt_button_present_with_reply():
    cbs = [b.callback_data for row in kb.conversation_actions("A", has_reply=True).inline_keyboard for b in row]
    assert "txt:A" in cbs


def test_txt_button_label_exact():
    labels = [b.text for row in kb.conversation_actions("A", has_reply=True).inline_keyboard for b in row]
    assert "ملف النص" in labels


def test_txt_button_absent_without_reply():
    cbs = [b.callback_data for row in kb.conversation_actions("A").inline_keyboard for b in row]
    assert not any(c and c.startswith("txt:") for c in cbs)


# -------------------------------------- 2. callback متميّز عن النسخ
def test_txt_callback_distinct_from_copy_and_full():
    markup = kb.conversation_actions("A", has_reply=True, reply_cut=True)
    cbs = [b.callback_data for row in markup.inline_keyboard for b in row]
    assert "copy:A" in cbs and "full:A" in cbs and "txt:A" in cbs
    assert len({"copy:A", "full:A", "txt:A"}) == 3  # ثلاث إجراءات مختلفة


def test_txt_callback_within_telegram_limit():
    cbs = [b.callback_data for row in kb.conversation_actions("a" * 36, has_reply=True).inline_keyboard for b in row]
    for c in cbs:
        assert len(c.encode("utf-8")) <= 64


# ---------------------------------------- 3/4/10. إرسال مستند كامل صحيح
def test_txt_button_sends_txt_document(tmp_path):
    ctx = _ctx(tmp_path, FakeClient(reply="ردي الكامل"))
    _run_txt(ctx, CQ("txt:A"))
    assert len(ctx.bot.documents) == 1
    doc = ctx.bot.documents[0]
    assert doc.filename.endswith(".txt")


def test_txt_document_contains_complete_response(tmp_path):
    reply = "السطر الأول\nالسطر الثاني\nالسطر الثالث"
    ctx = _ctx(tmp_path, FakeClient(reply=reply))
    _run_txt(ctx, CQ("txt:A"))
    assert ctx.bot.documents[0].input_file_content.decode("utf-8") == reply


def test_txt_document_sent_to_correct_chat_and_associated(tmp_path):
    ctx = _ctx(tmp_path, FakeClient())
    _run_txt(ctx, CQ("txt:A", message_id=777))
    kw = ctx.bot.doc_kwargs[0]
    assert ctx.bot.doc_chat_ids[0] == 99
    assert kw["reply_to_message_id"] == 777
    assert kw["allow_sending_without_reply"] is True


def test_txt_document_filename_is_reply_txt(tmp_path):
    ctx = _ctx(tmp_path, FakeClient())
    _run_txt(ctx, CQ("txt:A"))
    assert ctx.bot.documents[0].filename == "reply.txt"
    assert TXT_FILENAME == "reply.txt"


def test_txt_document_mime_is_text_plain(tmp_path):
    ctx = _ctx(tmp_path, FakeClient())
    _run_txt(ctx, CQ("txt:A"))
    assert ctx.bot.documents[0].mimetype.startswith("text/plain")


def test_txt_no_message_body_sent_on_success(tmp_path):
    # النجاح = مستند فقط؛ مفيش نص الرد جوه رسالة (ومفيش كابشن).
    ctx = _ctx(tmp_path, FakeClient(reply="ردي"))
    _run_txt(ctx, CQ("txt:A"))
    assert ctx.bot.messages == []
    assert "caption" not in ctx.bot.doc_kwargs[0]


# ------------------------------------------------ 5. UTF-8 عربي
def test_txt_arabic_utf8_roundtrip(tmp_path):
    reply = "مرحبًا بالعالم — هذا رد عربي كامل."
    ctx = _ctx(tmp_path, FakeClient(reply=reply))
    _run_txt(ctx, CQ("txt:A"))
    raw = ctx.bot.documents[0].input_file_content
    assert isinstance(raw, bytes)
    assert raw.decode("utf-8") == reply


# ------------------------------- 6. إيموجي/ترقيم/سطور فاضية/متعدد الأسطر
def test_txt_preserves_emoji_punctuation_blank_lines(tmp_path):
    reply = "سطر ١ 🎉\n\nسطر ٢ — «اقتباس»، علامات: ؟!؛\n\n\nسطر ٣ ✅"
    ctx = _ctx(tmp_path, FakeClient(reply=reply))
    _run_txt(ctx, CQ("txt:A"))
    assert ctx.bot.documents[0].input_file_content.decode("utf-8") == reply


# -------------------------------------- 7/8. أطول من حد الرسالة و256 محرف
def test_txt_longer_than_message_limit_exported_completely(tmp_path):
    reply = "ب" * 5000  # أطول من حد رسالة تيليجرام (4096)
    ctx = _ctx(tmp_path, FakeClient(reply=reply))
    _run_txt(ctx, CQ("txt:A"))
    assert ctx.bot.documents[0].input_file_content.decode("utf-8") == reply


def test_txt_longer_than_256_chars_exported_completely(tmp_path):
    reply = "ن" * 300
    ctx = _ctx(tmp_path, FakeClient(reply=reply))
    _run_txt(ctx, CQ("txt:A"))
    assert ctx.bot.documents[0].input_file_content.decode("utf-8") == reply


# ------------------- 9. رد مقسوم لعدة رسايل ⇒ ملف واحد بالترتيب الأصلي الكامل
def test_txt_split_across_messages_exported_as_one_complete_response(tmp_path):
    from bot.messages import split_message

    reply = "سطر رقم %d فيه نص كفاية للاختبار\n" * 500
    reply = reply % tuple(range(500))
    parts = split_message(reply)
    assert len(parts) > 3  # الرد اتبعت في البوت مقسومًا لعدة رسايل
    assert "".join(parts) == reply
    ctx = _ctx(tmp_path, FakeClient(reply=reply))
    _run_txt(ctx, CQ("txt:A"))
    assert len(ctx.bot.documents) == 1
    assert ctx.bot.documents[0].input_file_content.decode("utf-8") == reply


# ------------------------------------------------ 11. التفويض/الملكية
def test_txt_unauthorized_user_gets_no_document(tmp_path):
    ctx = _ctx(tmp_path, FakeClient())
    _run_txt(ctx, CQ("txt:A"), user_id=999)
    assert ctx.bot.documents == []
    assert ctx.bot.messages == []


def test_txt_non_private_chat_gets_no_document(tmp_path):
    ctx = _ctx(tmp_path, FakeClient())
    _run_txt(ctx, CQ("txt:A"), chat_type="group")
    assert ctx.bot.documents == []


def test_txt_owner_mismatch_refused(tmp_path):
    other = {**CONV, "created_by_user_id": "someone-else"}
    ctx = _ctx(tmp_path, FakeClient(conv=other))
    _run_txt(ctx, CQ("txt:A"))
    assert ctx.bot.documents == []
    assert ctx.bot.messages  # رسالة رفض آمنة


def test_txt_callback_data_cannot_cross_conversations(tmp_path):
    # تغيير المعرّف في callback data لا يمنح وصولًا: التفويض server-side على المعرّف.
    other = {**CONV, "id": "B", "created_by_user_id": "someone-else"}
    ctx = _ctx(tmp_path, FakeClient(conv=other))
    _run_txt(ctx, CQ("txt:B"))
    assert ctx.bot.documents == []


# ---------------------------------- 12. مرجع غير صالح/متشاهد/مش متاح
def test_txt_invalid_reference_refused(tmp_path):
    ctx = _ctx(tmp_path, FakeClient(conv=None))
    _run_txt(ctx, CQ("txt:not-a-valid-id"))
    assert ctx.bot.documents == []
    assert ctx.bot.messages


def test_txt_deleted_conversation_refused(tmp_path):
    ctx = _ctx(tmp_path, FakeClient())
    ctx.bot_data["db"].delete_conversation("A", "2026-01-01T00:00:00+00:00", remote_confirmed=True)
    _run_txt(ctx, CQ("txt:A"))
    assert ctx.bot.documents == []
    assert ctx.bot.messages


# -------------------- 13. فشل قراءة القاعدة لا يُفسَّر كرد فاضي/محذوف
def test_txt_db_read_failure_fails_closed_no_document(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path, FakeClient())
    db = ctx.bot_data["db"]

    def boom(_cid):
        raise RuntimeError("db down")

    monkeypatch.setattr(db, "is_deleted", boom)
    _run_txt(ctx, CQ("txt:A"))
    assert ctx.bot.documents == []  # مفيش ملف فاضي/مضلّل
    assert ctx.bot.messages  # رفض آمن صريح


# ------------------------------------------- 14. فشل رفع المستند
def test_txt_upload_failure_reports_error_not_success(tmp_path):
    from telegram.error import TelegramError

    bot = TxtRecBot(fail_document=TelegramError("upload failed"))
    ctx = _ctx(tmp_path, FakeClient(reply="ردي"), bot=bot)
    _run_txt(ctx, CQ("txt:A"))
    assert bot.documents == []  # ما ادّعيناش نجاح
    assert bot.messages  # رسالة خطأ عربي


def test_txt_upload_generic_exception_reports_error(tmp_path):
    bot = TxtRecBot(fail_document=RuntimeError("boom"))
    ctx = _ctx(tmp_path, FakeClient(reply="ردي"), bot=bot)
    _run_txt(ctx, CQ("txt:A"))
    assert bot.documents == []
    assert bot.messages


# ---------------------------------------- 15. رد فاضي / مستند أكبر من الحد
def test_txt_empty_reply_no_document(tmp_path):
    ctx = _ctx(tmp_path, FakeClient(reply=""))
    _run_txt(ctx, CQ("txt:A"))
    assert ctx.bot.documents == []
    assert [m[0] for m in ctx.bot.messages] == ["لسه مفيش رد للشات ده."]


def test_txt_none_reply_no_document(tmp_path):
    ctx = _ctx(tmp_path, FakeClient(reply=None))
    _run_txt(ctx, CQ("txt:A"))
    assert ctx.bot.documents == []


def test_txt_oversized_document_refused_not_truncated(tmp_path, monkeypatch):
    monkeypatch.setattr(sender, "TELEGRAM_DOCUMENT_MAX_BYTES", 10)
    ctx = _ctx(tmp_path, FakeClient(reply="ب" * 100))
    _run_txt(ctx, CQ("txt:A"))
    assert ctx.bot.documents == []  # مفيش ملف مقصوص
    assert ctx.bot.messages and "كبير" in ctx.bot.messages[0][0]


def test_send_text_document_raises_when_oversized(monkeypatch):
    monkeypatch.setattr(sender, "TELEGRAM_DOCUMENT_MAX_BYTES", 4)
    bot = TxtRecBot()
    with pytest.raises(TextDocumentTooLargeError):
        asyncio.run(send_text_document(99, "أكثر من أربعة", bot))
    assert bot.documents == []


def test_send_text_document_uploads_in_memory_utf8():
    bot = TxtRecBot()
    asyncio.run(send_text_document(99, "نص 🎉", bot))
    doc = bot.documents[0]
    assert doc.input_file_content == "نص 🎉".encode("utf-8")
    assert doc.filename == "reply.txt"
    assert bot.doc_chat_ids[0] == 99
    assert "reply_to_message_id" not in bot.doc_kwargs[0]  # مفيش ربط لما مفيش رسالة


# ---------------------------------- 16/17. النسخ والأزرار القائمة ما اتغيرتش
def test_copy_reply_behavior_unchanged(tmp_path):
    ctx = _ctx(tmp_path, FakeClient(reply="رد <b> & </b>"))
    asyncio.run(h.copy_reply(_update(CQ("copy:A")), ctx))
    text = ctx.bot.messages[0][0]
    assert text.startswith("<pre>") and text.endswith("</pre>")
    assert "&lt;b&gt;" in text and "&amp;" in text
    assert ctx.bot.documents == []  # النسخ مش بيعمل ملف


def test_full_reply_behavior_unchanged(tmp_path):
    ctx = _ctx(tmp_path, FakeClient(reply="ب" * 5000))
    asyncio.run(h.full_reply(_update(CQ("full:A")), ctx))
    assert len(ctx.bot.messages) == 2  # send_long يقسّم لقطعتين
    assert ctx.bot.documents == []


def test_existing_keyboard_buttons_preserved():
    cbs = [b.callback_data for row in kb.conversation_actions("A", has_reply=True, reply_cut=True).inline_keyboard for b in row]
    for expected in ("copy:A", "full:A", "reply:A", "open:A", "status:A", "list:0", "cancelroute", "delete:A"):
        assert expected in cbs


def test_txt_button_registered_as_own_handler():
    import bot.app as app_module

    src = __import__("inspect").getsource(app_module.build_application)
    assert 'pattern=r"^txt:"' in src
    assert "handlers.send_reply_txt" in src


# -------------------------------- إضافي: فشل إجابة الكولباك مايوقفش التنزيل
def test_txt_callback_answer_failure_still_delivers(tmp_path):
    class FailingAnswerCQ(CQ):
        async def answer(self):
            raise RuntimeError("query too old")

    ctx = _ctx(tmp_path, FakeClient(reply="ردي الكامل"))
    _run_txt(ctx, FailingAnswerCQ("txt:A"))
    assert len(ctx.bot.documents) == 1
    assert ctx.bot.documents[0].input_file_content.decode("utf-8") == "ردي الكامل"
