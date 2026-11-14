"""OHB2-UNSUPPORTED-FILE-SAFE-REJECTION — رفض المرفقات غير المدعومة بأمان.

الهدف: أي مرفق/وسيط (document/photo/audio/video/voice/video_note/animation/sticker)
يترفض **برسالة عربية واحدة**، من غير أي أثر جانبي: مفيش تنزيل (`get_file`)، مفيش حفظ
محلي، مفيش رفع، مفيش صندوق/طلب إنشاء، مفيش نداء OpenHands، مفيش شات جديد، ومفيش وصول
لمسار البرومت النصي.

بنشغّل التطبيق الحقيقي (`build_application`) وبنوجّه تحديثات تيليجرام حقيقية
(`Application.process_update`) عشان نثبت سلوك التسجيل والفلترة الفعلي (مش نداء مباشر
للـ handler). كل النداءات الخارجية معترَضة (مفيش شبكة).
"""
from __future__ import annotations

import asyncio

import pytest
from telegram import (
    Animation,
    Audio,
    Chat,
    Document,
    LivePhoto,
    Message,
    PaidMediaInfo,
    PaidMediaPhoto,
    PhotoSize,
    Sticker,
    Update,
    User,
    Video,
    VideoNote,
    Voice,
)

import bot.handlers as h_mod
from bot import app as app_mod
from bot.config import Config
from bot.db import Database

OWNER_ID = 1
CHAT_ID = 99
REJECT_TEXT = h_mod.UNSUPPORTED_ATTACHMENT_TEXT


def make_config(tmp_path) -> Config:
    return Config(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({OWNER_ID}),
        owner_id=OWNER_ID,
        db_path=str(tmp_path / "t.sqlite3"),
    )


class ForbiddenClient:
    """عميل OpenHands وهمي بيفشّل أي نداء — يثبت إن مسار الرفض ما بيلمسش OpenHands."""

    async def get_conversations(self, ids):
        raise AssertionError("مسار الرفض ما لازمش ينادي OpenHands")

    async def resume_sandbox(self, sandbox_id):
        raise AssertionError("مسار الرفض ما لازمش ينادي OpenHands")

    async def send_message(self, conversation_id, text):
        raise AssertionError("مسار الرفض ما لازمش ينادي OpenHands")

    async def start_conversation(self, text, repository, branch=None):
        raise AssertionError("مسار الرفض ما لازمش ينادي OpenHands")

    async def wait_for_start(self, task_id):
        raise AssertionError("مسار الرفض ما لازمش ينادي OpenHands")


class Harness:
    def __init__(self, tmp_path) -> None:
        self.app = app_mod.build_application(make_config(tmp_path))
        self.app._initialized = True  # نتخطّى initialize() (بيفتح جلسة شبكة حقيقية)
        self.app.bot_data["client"] = ForbiddenClient()
        self.replies: list[str] = []
        self.downloads: list[tuple] = []
        self.creates: list[tuple] = []

    @property
    def db(self) -> Database:
        return self.app.bot_data["db"]

    def _user(self) -> User:
        return User(id=OWNER_ID, first_name="o", is_bot=False)

    def message_update(self, update_id: int, **msg_kw) -> Update:
        chat = Chat(id=CHAT_ID, type="private")
        msg = Message(
            message_id=5, date=None, chat=chat, from_user=self._user(), **msg_kw
        )
        msg.set_bot(self.app.bot)
        up = Update(update_id=update_id, message=msg)
        up.set_bot(self.app.bot)
        return up

    def process(self, update: Update) -> None:
        asyncio.run(self.app.process_update(update))


# ---------------------------------------------------------------- بناء أنواع المرفقات
def _document(**kw):
    return dict(
        document=Document(file_id="doc-1", file_unique_id="u1", file_name="report.pdf", **kw)
    )


def _photo(**kw):
    return dict(photo=[PhotoSize(file_id="ph-1", file_unique_id="u2", width=10, height=10, **kw)])


def _audio():
    return dict(audio=Audio(file_id="au-1", file_unique_id="u3", duration=5))


def _video():
    return dict(video=Video(file_id="vi-1", file_unique_id="u4", width=10, height=10, duration=5))


def _voice():
    return dict(voice=Voice(file_id="vo-1", file_unique_id="u5", duration=5))


def _video_note():
    return dict(video_note=VideoNote(file_id="vn-1", file_unique_id="u6", length=10, duration=5))


def _animation():
    return dict(
        animation=Animation(file_id="an-1", file_unique_id="u7", width=10, height=10, duration=5)
    )


def _sticker():
    return dict(
        sticker=Sticker(
            file_id="st-1",
            file_unique_id="u8",
            width=10,
            height=10,
            type="regular",
            is_animated=False,
            is_video=False,
        )
    )


def _live_photo():
    return dict(
        live_photo=LivePhoto(
            file_id="lp-1", file_unique_id="u9", width=10, height=10, duration=3
        )
    )


def _paid_media():
    return dict(
        paid_media=PaidMediaInfo(
            star_count=1,
            paid_media=[
                PaidMediaPhoto(
                    photo=[PhotoSize(file_id="pm-1", file_unique_id="u10", width=10, height=10)]
                )
            ],
        )
    )


# كل نوع مدعوم للرفض، بالترتيب.
# OHB2-P0-A2: `document` اتشال من هنا — بقى النوع **المدعوم** الوحيد (مساره الجديد
# `handle_attachment`)، ورفضه القديم كان هيكسر سلوك A2. باقي الوسائط بتفضل مرفوضة.
ATTACHMENT_BUILDERS = [
    ("photo", _photo),
    ("audio", _audio),
    ("video", _video),
    ("voice", _voice),
    ("video_note", _video_note),
    ("animation", _animation),
    ("sticker", _sticker),
    ("live_photo", _live_photo),
    ("paid_media", _paid_media),
]


def _patch_telegram(monkeypatch, harness: Harness) -> None:
    """يعترض كل نداءات تيليجرام (مفيش شبكة) ويسجّل الردود والتنزيلات."""

    async def _send_message(self, chat_id=None, text=None, **kw):
        harness.replies.append(text)
        return Message(message_id=1, date=None, chat=Chat(id=chat_id, type="private"))

    async def _get_file(self, file_id=None, **kw):
        harness.downloads.append(("get_file", file_id))
        raise AssertionError("مسار الرفض ما لازمش ينزّل الملف (get_file)")

    async def _download(self, file, **kw):
        harness.downloads.append(("download", getattr(file, "file_id", None)))
        raise AssertionError("مسار الرفض ما لازمش ينزّل الملف (download)")

    async def _noop(self, *a, **k):
        return True

    monkeypatch.setattr("telegram.Bot.send_message", _send_message)
    monkeypatch.setattr("telegram.Bot.get_file", _get_file)
    monkeypatch.setattr("telegram.File.download_to_drive", _download)
    monkeypatch.setattr("telegram.File.download_as_bytearray", _download)
    monkeypatch.setattr("telegram.Bot.set_my_commands", _noop)
    monkeypatch.setattr("telegram.Bot.set_chat_menu_button", _noop)


def _harness(tmp_path, monkeypatch) -> Harness:
    harness = Harness(tmp_path)
    _patch_telegram(monkeypatch, harness)
    return harness


# ============================================================================
# 1) كل نوع: رد عربي واحد بالظبط، ومفيش أي أثر جانبي
# ============================================================================
@pytest.mark.parametrize("name,builder", ATTACHMENT_BUILDERS, ids=[n for n, _ in ATTACHMENT_BUILDERS])
def test_attachment_type_rejected_once_with_no_side_effects(tmp_path, monkeypatch, name, builder):
    harness = _harness(tmp_path, monkeypatch)
    # حالة توجيه معلّقة: لو المرفق وصل لمسار البرومت كان هيرسل/ينشئ — نتأكد إن ده ماحصلش.
    harness.db.set_awaiting(OWNER_ID, "11111111222233334444555566667777", "route", title="A")

    harness.process(harness.message_update(2000, **builder()))

    # 1) رد واحد بالظبط، بالنص العربي الصحيح.
    assert harness.replies == [REJECT_TEXT]
    # 2) مفيش تنزيل ولا حفظ.
    assert harness.downloads == []
    # 3) مفيش صندوق ولا طلب إنشاء ولا شات جديد.
    assert harness.db.count_outbox() == 0
    assert harness.db.list_open_creation_jobs() == []
    # 4) حالة التوجيه ما اتغيّرتش (مفيش استهلاك/إرسال).
    pending, kind, title, _ = harness.db.awaiting_state(OWNER_ID)
    assert (pending, kind, title) == ("11111111222233334444555566667777", "route", "A")


def test_attachment_rejection_does_not_create_local_files(tmp_path, monkeypatch):
    """مفيش أي ملف جديد في مجلد العمل نتيجة الرفض."""
    harness = _harness(tmp_path, monkeypatch)
    before = {p.name for p in tmp_path.iterdir()}
    harness.process(harness.message_update(2100, **_document()))
    after = {p.name for p in tmp_path.iterdir()}
    assert after - before == set()  # مفيش أي ملف جديد (لا مرفق ولا غيره)


def test_attachment_rejection_records_explicitly_ignored_outcome(tmp_path, monkeypatch):
    harness = _harness(tmp_path, monkeypatch)
    harness.process(harness.message_update(2200, **_photo()))
    assert harness.db.update_outcome(2200) == "explicitly_ignored"
    assert harness.db.is_update_acknowledgment_eligible(2200) is True


# ============================================================================
# 2) النص والأوامر ما بتتأثّرش
# ============================================================================
def test_plain_text_still_uses_text_path(tmp_path, monkeypatch):
    """النص العادي بيفضل على مساره: بيتبعت للصندوق كبرومت (مش رد الرفض)."""
    harness = _harness(tmp_path, monkeypatch)
    harness.db.set_awaiting(OWNER_ID, "11111111222233334444555566667777", "route", title="A")

    harness.process(harness.message_update(2300, text="برومت نصي"))

    # مسار النص: بيضيف للصندوق (نية دائمة) — مش رد الرفض.
    assert REJECT_TEXT not in harness.replies
    assert harness.db.count_outbox() == 1


def test_command_still_uses_command_handler(tmp_path, monkeypatch):
    """الأوامر بتفضل لمعالجات الأوامر (مش رفض المرفقات)."""
    harness = _harness(tmp_path, monkeypatch)
    harness.process(harness.message_update(2400, text="/help"))
    assert harness.replies and harness.replies[0] != REJECT_TEXT


# ============================================================================
# 3) الفلترة: التكامل والتفرد (مفيش وقوع/ازدواج)
# ============================================================================
def _handler_filters(app):
    from telegram.ext import MessageHandler

    return [h.filters for group in app.handlers.values() for h in group if isinstance(h, MessageHandler)]


def test_attachment_and_text_filters_are_mutually_exclusive():
    """أي رسالة بتطابق واحد بالظبط من الفلترين (نص/أوامر أو مرفقات) ⇒ مفيش ازدواج.

    OHB2-P0-A2: المرفقات اتقسمت لفلترين متمايزين (مدعوم=Document، غير مدعوم=الباقي)؛
    الاتحاد لازم يفضل مكمّل لفلتر النص، والفلترين ما يتداخلوش.
    """
    from telegram.ext import filters

    text_f = filters.TEXT & ~filters.COMMAND
    supported_f = app_mod.SUPPORTED_ATTACHMENT_FILTER
    unsupported_f = app_mod.UNSUPPORTED_ATTACHMENT_FILTER
    cases = [
        {"text": "hello"},
        {"text": "/start"},
        _document(),
        {**_document(), "caption": "hello"},
        _photo(),
        _audio(),
        _video(),
        _voice(),
        _video_note(),
        _animation(),
        _sticker(),
        _live_photo(),
        _paid_media(),
        # رسالة تحمل مستندًا + وسيطًا آخر (F-8): لازم تطابق فلترًا واحدًا بالظبط.
        {**_document(), **_animation()},
        {**_document(), **_video()},
        {**_document(), **_audio()},
        {**_document(), **_photo()},
    ]
    for kw in cases:
        chat = Chat(id=1, type="private")
        up = Update(update_id=1, message=Message(message_id=1, date=None, chat=chat, **kw))
        t = text_f.check_update(up)
        s = supported_f.check_update(up)
        u = unsupported_f.check_update(up)
        # فلترا المرفقات متمايزان (مفيش تداخل).
        assert not (s and u), f"تداخل بين المدعوم وغير المدعوم: {kw}"
        # النص والمرفقات متمايزان، والاتحاد يغطّي الرسالة.
        assert not (t and (s or u)), f"ازدواج فلترة على {kw}"
        assert t or s or u, f"رسالة وقعت من كل الفلاتر: {kw}"


def test_attachment_filter_excludes_non_file_attachments():
    """الفلتر صريح: ما بيشملش Location/Contact/Poll (مش ملفات)."""
    from telegram import Location

    chat = Chat(id=1, type="private")
    up = Update(
        update_id=1,
        message=Message(message_id=1, date=None, chat=chat, location=Location(longitude=1.0, latitude=1.0)),
    )
    assert app_mod.UNSUPPORTED_ATTACHMENT_FILTER.check_update(up) is False


def test_attachment_handler_registered(tmp_path, monkeypatch):
    """المعالج متسجّل، والنص/الأوامر ما بتوصلوش (التفرد مفروض بالتسجيل)."""
    app = app_mod.build_application(make_config(tmp_path))
    assert h_mod.handle_unsupported_attachment in {
        h.callback for group in app.handlers.values() for h in group
    }


# ============================================================================
# 4) فشل الرد: مش نجاح كاذب
# ============================================================================
def test_reply_failure_is_recorded_and_not_false_success(tmp_path, monkeypatch):
    """فشل إرسال الرد ⇒ فشل مُسجّل (غير مؤهّل للإقرار)، مش نجاح صامت."""
    harness = _harness(tmp_path, monkeypatch)

    async def _boom(self, chat_id=None, text=None, **kw):
        raise RuntimeError("telegram down")

    monkeypatch.setattr("telegram.Bot.send_message", _boom)

    # PTB بيلتقط الاستثناء ويوجّهه لمعالج الأخطاء؛ process_update ما بيعيدش رفعه.
    harness.process(harness.message_update(2500, **_document()))

    outcome = harness.db.update_outcome(2500)
    assert outcome is not None and outcome != "explicitly_ignored"
    assert harness.db.is_update_acknowledgment_eligible(2500) is False


def test_non_owner_attachment_is_ignored_without_reply(tmp_path, monkeypatch):
    """مستخدم غير مسموح ⇒ مفيش رد خالص (نفس سياسة التفويض القائمة)."""
    harness = _harness(tmp_path, monkeypatch)

    chat = Chat(id=CHAT_ID, type="private")
    msg = Message(
        message_id=5, date=None, chat=chat,
        from_user=User(id=999, first_name="x", is_bot=False), **_document(),
    )
    msg.set_bot(harness.app.bot)
    up = Update(update_id=2600, message=msg)
    up.set_bot(harness.app.bot)
    harness.process(up)

    assert harness.replies == []
    assert harness.db.count_outbox() == 0
