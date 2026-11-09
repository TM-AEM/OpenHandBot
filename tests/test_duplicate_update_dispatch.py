"""OHB2-DUPLICATE-TELEGRAM-PROMPT-DISPATCH — اختبارات انحدار على **مدخل معالجة التحديث الكامل**.

المشكلة المُبلَّغ عنها: رسالة واحدة من المستخدم جوه شات تيليجرام موجود (مربوط بمستودع)
اتعالجت **مرتين** — مرة إرسال للشات الموجود A، ومرة إنشاء شات جديد B (بدون مستودع).

السبب الجذري: PTB بيسجّل `_last_update_id` **بعد** ما يحط التحديث في الطابور (مش بعد
تنفيذه) ومفيش ديدَب داخلي، فأي إعادة تسليم (إعادة تشغيل/انقطاع قبل تأكيد الـ offset، أو
تحديث واحد في الطابور مرتين، أو تزامن) بتوصل لـ `handle_text` تاني. وقتها `take_awaiting`
بترجّع حالة مختلفة (مثلاً التوجيه اتبدّل) فينشأ قرار معالجة تاني ⇒ إرسال + إنشاء.

الاختبارات دي بتشتغل على **`Application.process_update`** (نفس اللي PTB بينده بيه)،
بقاعدة SQLite معزولة وعميل OpenHands وهمي (مفيش شبكة). الحاجز الجديد (`handlers.dedupe_update`
في group=-1) بيمنع القرار التاني لأي تحديث مكرّر.

اختبار الطفرة: لو شيلنا الحاجز، اختبارات التكرار بتفشل (بتعمل عمليتين لنفس التحديث).
"""
from __future__ import annotations

import asyncio
import sqlite3
from types import SimpleNamespace

from telegram import CallbackQuery, Chat, Message, Update, User

import bot.handlers as h_mod
from bot import app as app_mod
from bot import outbox
from bot.config import Config
from bot.db import Database

OWNER_ID = 1
OWNER_UUID = "owner-uuid-123"
# معرّفات 32 حرف (شكل UUID) عشان تعدّي تحقّق مسار الـ API.
CID_A = "11111111222233334444555566667777"
CID_B = "aaaaaaaaaaaabbbbccccddddeeeeeeee"
CHAT_ID = 99


def make_config(tmp_path) -> Config:
    return Config(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({OWNER_ID}),
        owner_id=OWNER_ID,
        db_path=str(tmp_path / "t.sqlite3"),
    )


def _conv(cid: str, repo: str | None = None, *, sandbox: str = "RUNNING", sandbox_id: str = "sb-1") -> dict:
    conv = {
        "id": cid,
        "title": f"شات {cid[:4]}",
        "execution_status": "running",
        "sandbox_status": sandbox,
        "sandbox_id": sandbox_id,
        "created_by_user_id": OWNER_UUID,
    }
    if repo:
        conv["selected_repository"] = repo
    return conv


class FakeOpenHands:
    """عميل OpenHands وهمي: بيسجّل كل عملية (إرسال/إنشاء/resume) بدون أي شبكة."""

    def __init__(self, conversations: dict[str, dict] | None = None) -> None:
        self.conversations = conversations or {}
        self.sends: list[tuple[str, str]] = []
        self.creates: list[tuple[str, str | None]] = []
        self.resumes: list[str] = []

    async def get_current_user(self) -> dict:
        return {"id": OWNER_UUID}

    async def get_conversations(self, ids):
        out = []
        for i in ids:
            if i not in self.conversations:
                continue
            conv = dict(self.conversations[i])
            if self.resumes and conv.get("sandbox_status") == "PAUSED":
                conv["sandbox_status"] = "RUNNING"
            out.append(conv)
        return out

    async def resume_sandbox(self, sandbox_id: str) -> None:
        self.resumes.append(sandbox_id)

    async def send_message(self, conversation_id: str, text: str) -> None:
        self.sends.append((conversation_id, text))

    async def start_conversation(self, text: str, repository: str | None, branch: str | None = None) -> str:
        self.creates.append((text, repository))
        return "task-created"

    async def wait_for_start(self, task_id: str) -> str:
        return CID_B


class Harness:
    """يشغّل التطبيق الحقيقي (نفس تسجيل الـ handlers) ويوجّه تحديثات حقيقية له."""

    def __init__(self, tmp_path, client: FakeOpenHands | None = None) -> None:
        self.app = app_mod.build_application(make_config(tmp_path))
        self.app._initialized = True  # نتخطّى initialize() (بيفتح جلسة شبكة حقيقية)
        self.client = client or FakeOpenHands()
        self.app.bot_data["client"] = self.client
        self.tg_sends: list[str] = []
        self.tg_edits: list[str] = []

    @property
    def db(self) -> Database:
        return self.app.bot_data["db"]

    def _user(self) -> User:
        return User(id=OWNER_ID, first_name="o", is_bot=False)

    def text_update(self, update_id: int, text: str) -> Update:
        chat = Chat(id=CHAT_ID, type="private")
        msg = Message(message_id=5, date=None, chat=chat, from_user=self._user(), text=text)
        msg.set_bot(self.app.bot)
        up = Update(update_id=update_id, message=msg)
        up.set_bot(self.app.bot)
        return up

    def callback_update(self, update_id: int, data: str) -> Update:
        chat = Chat(id=CHAT_ID, type="private")
        msg = Message(message_id=5, date=None, chat=chat, from_user=self._user(), text=None)
        msg.set_bot(self.app.bot)
        cq = CallbackQuery(id="cq-1", from_user=self._user(), chat_instance="ci", data=data, message=msg)
        cq.set_bot(self.app.bot)
        up = Update(update_id=update_id, callback_query=cq)
        up.set_bot(self.app.bot)
        return up

    def process(self, update: Update) -> None:
        asyncio.run(self.app.process_update(update))

    def deliver_pending(self) -> None:
        """يشغّل مسار التسليم الحقيقي لأقدم سجل صندوق معلّق (بدون نافذة تجميع)."""
        rows = self.db.list_outbox_by_status("pending")
        if not rows:
            return
        asyncio.run(outbox.deliver_outbox(self.client, self.db, self.app.bot, rows[0].id))

    def run_creation_worker_once(self) -> None:
        worker = outbox.CreationWorker(self.client, self.db, self.app.bot, "")
        asyncio.run(worker._tick())


def _patch_telegram(monkeypatch):
    """يعترض كل نداءات تيليجرام الصادرة (بدون شبكة)."""

    async def _send_message(self, chat_id=None, text=None, **kw):
        return Message(message_id=1, date=None, chat=Chat(id=chat_id, type="private"))

    async def _answer_callback_query(self, callback_query_id=None, **kw):
        return True

    async def _edit_message_text(self, text=None, **kw):
        return Message(message_id=1, date=None, chat=Chat(id=CHAT_ID, type="private"))

    monkeypatch.setattr("telegram.Bot.send_message", _send_message)
    monkeypatch.setattr("telegram.Bot.answer_callback_query", _answer_callback_query)
    monkeypatch.setattr("telegram.Bot.edit_message_text", _edit_message_text)

    # قائمة الأوامر (شبكة) — ما تتناداش في process_update، بس للأمان.
    async def _noop(self, *a, **k):
        return True

    monkeypatch.setattr("telegram.Bot.set_my_commands", _noop)
    monkeypatch.setattr("telegram.Bot.set_chat_menu_button", _noop)


def _harness(tmp_path, monkeypatch, client=None) -> Harness:
    _patch_telegram(monkeypatch)
    return Harness(tmp_path, client=client)


# ------------------------------------------------------------------ السيناريو 1
def test_one_prompt_existing_repo_conversation_exactly_one_send_zero_creation(tmp_path, monkeypatch):
    h = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")}))
    h.db.set_awaiting(OWNER_ID, CID_A, "route", title="A")

    h.process(h.text_update(1001, "برومت للمستودع"))
    h.deliver_pending()

    assert h.client.sends == [(CID_A, "برومت للمستودع")]
    assert h.client.creates == []
    assert h.db.list_open_creation_jobs() == []


# ------------------------------------------------------------------ السيناريو 2
def test_duplicate_delivery_of_same_update_produces_no_extra_operation(tmp_path, monkeypatch):
    h = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")}))
    h.db.set_awaiting(OWNER_ID, CID_A, "route", title="A")

    update = h.text_update(1002, "برومت")
    h.process(update)
    # نفس التحديث بالظبط (نفس update_id) — زي إعادة تسليم من تيليجرام.
    h.process(update)
    h.deliver_pending()

    assert h.client.sends == [(CID_A, "برومت")]  # إرسال واحد بس
    assert h.client.creates == []  # مفيش إنشاء خالص
    assert len(h.db.list_outbox_by_status("pending") + h.db.list_outbox_by_status("sent")) == 1


# ------------------------------------------------------------------ السيناريو 3
def test_concurrent_processing_of_same_update_no_duplicate(tmp_path, monkeypatch):
    """تحديث واحد في الطابور مرتين + معالجة متزامنة ⇒ قرار معالجة واحد بس.

    ده بيحاكي: PTB بيحط التحديث مرتين في الطابور (أو إعادة تسليم) مع `concurrent_updates`،
    فالمعالج بيتنفّذ مرتين في نفس اللحظة. الحاجز الذرّي (INSERT OR IGNORE) بيخلّي واحد يفوز.
    """
    h = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")}))
    h.db.set_awaiting(OWNER_ID, CID_A, "route", title="A")
    update = h.text_update(1003, "برومت متزامن")

    async def go():
        # تحديثين بنفس update_id بيتعالجوا معًا (زي نفس التحديث اتسلّم مرتين).
        u2 = h.text_update(1003, "برومت متزامن")
        await asyncio.gather(h.app.process_update(update), h.app.process_update(u2))

    asyncio.run(go())
    h.deliver_pending()

    assert len(h.db.list_outbox_by_status("pending") + h.db.list_outbox_by_status("sent")) == 1
    assert h.client.creates == []


def test_exact_reported_symptom_one_update_cannot_send_and_create(tmp_path, monkeypatch):
    """إعادة إنتاج العَرَض المُبلَّغ عنه حرفيًا: تحديث **واحد** بيوصل مرتين — المرة الأولى
    بتوجيه route (إرسال للشات الموجود A)، والمرة التانية بعد ما حالة الانتظار اتبدّلت
    لـ newchat (إنشاء شات جديد B). من غير الحاجز، نفس التحديث بيعمل عمليتين مستقلتين
    (إرسال + إنشاء). بالحاجز: قرار معالجة واحد بس (إرسال لـ A) وصفر إنشاء.
    """
    h = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")}))
    h.db.set_awaiting(OWNER_ID, CID_A, "route", title="A")
    update = h.text_update(1004, "برومت")

    h.process(update)  # المرة الأولى: توجيه route ⇒ إرسال للشات الموجود
    h.db.set_awaiting(OWNER_ID, None, "newchat")  # الحالة اتبدّلت (سباق/إعادة تشغيل)
    h.process(update)  # إعادة تسليم **نفس** التحديث
    h.deliver_pending()
    h.run_creation_worker_once()

    assert h.client.sends == [(CID_A, "برومت")]  # إرسال واحد للشات الموجود
    assert h.client.creates == []  # صفر إنشاء (مفيش شات B)
    assert h.db.list_open_creation_jobs() == []


# ------------------------------------------------------------------ السيناريو 4
def test_two_legitimate_consecutive_messages_both_processed(tmp_path, monkeypatch):
    h = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")}))
    h.db.set_awaiting(OWNER_ID, CID_A, "route", title="A")

    h.process(h.text_update(2001, "أول"))
    h.deliver_pending()
    h.db.set_awaiting(OWNER_ID, CID_A, "route", title="A")  # المستخدم لسه موجّه للشات
    h.process(h.text_update(2002, "تاني"))
    h.deliver_pending()

    assert [c for c, _ in h.client.sends] == [CID_A, CID_A]
    assert h.db.count_processed_updates() == 2  # تحديثين مختلفين ⇒ اتعالجوا الاتنين


# ------------------------------------------------------------------ السيناريو 5
def test_explicit_new_chat_command_exactly_one_conversation(tmp_path, monkeypatch):
    h = _harness(tmp_path, monkeypatch, FakeOpenHands())
    # /newchat ثم اختيار «بدون مستودع» ثم البرومت — عبر مدخل التحديث الكامل.
    h.process(h.callback_update(3001, "newchat"))
    h.process(h.callback_update(3002, "norepo"))
    h.process(h.text_update(3003, "ابدأ شات جديد"))
    h.run_creation_worker_once()

    assert len(h.client.creates) == 1
    assert h.client.creates[0][1] is None  # بدون مستودع
    assert h.client.sends == []
    # إعادة تسليم نفس أمر البرومت ما تعملش شات تاني.
    h.process(h.text_update(3003, "ابدأ شات جديد"))
    h.run_creation_worker_once()
    assert len(h.client.creates) == 1


def test_new_chat_with_repo_creates_one_conversation_with_repo(tmp_path, monkeypatch):
    h = _harness(tmp_path, monkeypatch, FakeOpenHands())
    h.process(h.callback_update(3101, "newchat"))
    # نضبط التوجيه لمستودع (بدل الاعتماد على قايمة مستودعات بعيدة).
    h.db.set_awaiting(OWNER_ID, "owner/repo", "newchat")
    h.process(h.text_update(3102, "ابدأ بمستودع"))
    h.run_creation_worker_once()

    assert h.client.creates == [("ابدأ بمستودع", "owner/repo")]
    assert h.client.sends == []


# ------------------------------------------------------------------ السيناريو 6
def test_existing_conversation_missing_mapping_fails_safe_no_replacement(tmp_path, monkeypatch):
    h = _harness(tmp_path, monkeypatch, FakeOpenHands({}))  # الشات مش موجود
    h.db.set_awaiting(OWNER_ID, CID_A, "reply")

    h.process(h.text_update(4001, "برومت لشات ضايع"))
    h.deliver_pending()

    assert h.client.creates == []  # مفيش شات بديل
    assert h.client.sends == []
    assert h.db.list_open_creation_jobs() == []
    # البرومت لسه مؤهّل (فشل آمن قبل أي POST).
    assert len(h.db.list_outbox_by_status("pending")) == 1


# ------------------------------------------------------------------ السيناريو 7
def test_existing_conversation_repository_and_sandbox_preserved(tmp_path, monkeypatch):
    h = _harness(
        tmp_path, monkeypatch,
        FakeOpenHands({CID_A: _conv(CID_A, "owner/repo", sandbox="PAUSED", sandbox_id="sb-repo-9")}),
    )
    h.db.set_awaiting(OWNER_ID, CID_A, "route", title="A")

    h.process(h.text_update(5001, "برومت"))
    h.deliver_pending()

    assert h.client.resumes == ["sb-repo-9"]  # نفس sandbox الشات، مش sandbox جديد
    assert h.client.sends == [(CID_A, "برومت")]
    assert h.client.creates == []
    assert h.client.conversations[CID_A]["selected_repository"] == "owner/repo"


# ------------------------------------------------------------------ السيناريو 8
def test_process_restart_and_update_replay_no_duplicate(tmp_path, monkeypatch):
    """إعادة تشغيل: نفس قاعدة البيانات، نفس التحديث بيتسلّم تاني ⇒ مايتعالجش مرتين."""
    h = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")}))
    h.db.set_awaiting(OWNER_ID, CID_A, "route", title="A")
    h.process(h.text_update(6001, "برومت قبل الريستارت"))
    h.deliver_pending()

    # «إعادة تشغيل»: تطبيق جديد على **نفس** قاعدة البيانات (نفس db_path).
    h2 = Harness.__new__(Harness)
    h2.app = app_mod.build_application(make_config(tmp_path))
    h2.app._initialized = True
    h2.client = h.client
    h2.app.bot_data["client"] = h.client
    h2.tg_sends, h2.tg_edits = [], []

    h2.process(h2.text_update(6001, "برومت قبل الريستارت"))  # إعادة تسليم نفس التحديث
    h2.deliver_pending()

    assert h.client.sends == [(CID_A, "برومت قبل الريستارت")]  # إرسال واحد بس
    assert h.client.creates == []


# ------------------------------------------------------------------ السيناريو 9
def test_outbox_recovery_no_duplicate_conversation_creation(tmp_path, monkeypatch):
    h = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")}))
    h.db.set_awaiting(OWNER_ID, CID_A, "route", title="A")
    h.process(h.text_update(7001, "برومت"))
    h.deliver_pending()

    before = len(h.client.sends)
    asyncio.run(outbox.outbox_recover(h.app))
    asyncio.run(outbox.outbox_recover(h.app))

    assert len(h.client.sends) == before  # مفيش إرسال تاني
    assert h.client.creates == []


# ------------------------------------------------------------------ السيناريو 10
def test_failed_or_ambiguous_response_no_unsafe_fallback_creation(tmp_path, monkeypatch):
    client = FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")})

    async def boom(conversation_id, text):
        client.sends.append((conversation_id, text))
        from bot.errors import ApiError

        raise ApiError("تعذّر الاتصال", None)

    client.send_message = boom  # نتيجة غامضة (شبكة)
    h = _harness(tmp_path, monkeypatch, client)
    h.db.set_awaiting(OWNER_ID, CID_A, "route", title="A")

    h.process(h.text_update(8001, "برومت غامض"))
    h.deliver_pending()

    assert h.client.creates == []  # مفيش إنشاء بديل
    # النتيجة غامضة ⇒ 'unknown' (مش إعادة إرسال تلقائية، ولا إنشاء).
    assert len(h.db.list_outbox_by_status("unknown")) == 1


# ------------------------------------------------------------------ السيناريو 11
def test_multiple_handlers_cannot_consume_same_update(tmp_path, monkeypatch):
    """التحديث الواحد بيتنفّذ فيه handler واحد بس لكل مجموعة، والحاجز في group=-1 يمنع الباقي."""
    h = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")}))
    h.db.set_awaiting(OWNER_ID, CID_A, "route", title="A")
    h.process(h.text_update(9001, "برومت"))
    # الحاجز سجّل التحديث، والحالة اتستهلكت مرة واحدة (مفيش تنفيذ تاني).
    assert h.db.get_awaiting(OWNER_ID) == (CID_A, "route")  # route بتتجدد (مش تتلغى)
    assert h.db.count_outbox() == 1


# ------------------------------------------------------------------ السيناريو 12
def test_user_authorization_and_ownership_enforced(tmp_path, monkeypatch):
    h = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")}))
    h.db.set_awaiting(OWNER_ID, CID_A, "route", title="A")

    # مستخدم غير مسموح: مفيش أي عملية (إرسال/إنشاء) ومفيش تسجيل صندوق.
    chat = Chat(id=CHAT_ID, type="private")
    msg = Message(message_id=5, date=None, chat=chat, from_user=User(id=999, first_name="x", is_bot=False), text="ممنوع")
    msg.set_bot(h.app.bot)
    up = Update(update_id=9101, message=msg)
    up.set_bot(h.app.bot)
    h.process(up)
    h.deliver_pending()

    assert h.client.sends == []
    assert h.client.creates == []
    assert h.db.count_outbox() == 0


def test_ownership_mismatch_conversation_not_used(tmp_path, monkeypatch):
    """شات مملوك لمستخدم تاني: رد/توجيه يفشل مقفول، مفيش إرسال ولا إنشاء."""
    foreign = _conv(CID_A, "owner/repo")
    foreign["created_by_user_id"] = "someone-else"
    h = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: foreign}))
    # نفتح الشات عبر callback reply (بيمر بتفويض الملكية) — لازم يترفض.
    h.process(h.callback_update(9201, f"reply:{CID_A}"))
    # مفيش توجيه اتفتح، فبرومت لاحق مالوش وجهة.
    h.process(h.text_update(9202, "برومت"))
    h.deliver_pending()
    assert h.client.sends == []
    assert h.client.creates == []


# --------------------------------------------------------- اختبارات وحدة للحاجز
def test_dedupe_guard_marks_first_and_rejects_repeat(tmp_path, monkeypatch):
    h = _harness(tmp_path, monkeypatch)
    assert h.db.mark_update_processed(1, "t") is True
    assert h.db.mark_update_processed(1, "t") is False
    assert h.db.mark_update_processed(2, "t") is True
    assert h.db.count_processed_updates() == 2


def test_prune_processed_updates_keeps_recent_window(tmp_path, monkeypatch):
    h = _harness(tmp_path, monkeypatch)
    for i in range(1, 11):
        h.db.mark_update_processed(i, f"2026-01-01T00:00:{i:02d}+00:00")
    removed = h.db.prune_processed_updates(3)
    assert removed == 7
    assert h.db.count_processed_updates() == 3
    # أقدم تحديث اتمسح (مش بيتعالج تاني)، وأحدث 3 لسه موجودين.
    assert h.db.mark_update_processed(10, "t") is False
    assert h.db.mark_update_processed(1, "t") is True


def test_dedupe_guard_registered_in_negative_group(tmp_path, monkeypatch):
    _patch_telegram(monkeypatch)
    app = app_mod.build_application(make_config(tmp_path))
    assert -1 in app.handlers
    from telegram.ext import TypeHandler

    assert any(isinstance(hh, TypeHandler) for hh in app.handlers[-1])


# ============================================================================
# OHB2-DUP-DISPATCH-CRASH: نافذة الفقد (الحاجز قبل الكتابة) + الفشل المقفول.
# ============================================================================
def test_guard_is_read_only_marker_written_with_durable_record(tmp_path, monkeypatch):
    """الحاجز **فحص قراءة** مش تسجيل: بعد ما يعدّي، التحديث **مش** مسجّل «معالَج».

    ده أساس إغلاق نافذة الفقد: لو العملية ماتت **قبل** كتابة السجل الدائم، مفيش «معالَج»
    ⇒ إعادة التسليم بتنفّذ (مفيش فقد). التسجيل بيحصل مع الكتابة الدائمة نفسها.
    """
    h = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")}))
    h.db.set_awaiting(OWNER_ID, CID_A, "route", title="A")
    update = h.text_update(9501, "برومت")

    # الحاجز لوحده (نفس التحديث، قاعدة حقيقية) — بيكمّل من غير ما يسجّل.
    ctx = SimpleNamespace(bot_data={"db": h.db})
    asyncio.run(h_mod.dedupe_update(update, ctx))
    assert h.db.update_is_processed(9501) is False
    assert h.db.count_processed_updates() == 0

    # المعالجة الكاملة: الكتابة الدائمة بتسجّل «معالَج» ذرّيًا.
    h.process(update)
    assert h.db.update_is_processed(9501) is True
    assert h.db.count_outbox() == 1


def test_guard_db_error_fails_closed_stops_handlers_and_logs(tmp_path, monkeypatch, caplog):
    """P2: فشل فحص الحاجز ⇒ فشل مقفول: مفيش معالجة (مفيش صندوق) + خطأ مسجّل بنفسنا.

    بنرمي `ApplicationHandlerStop` عشان نمنع أي معالجة مزدوجة (المجموعة 0 متشتغلش). PTB
    بيبتلع الاستثناء من غير ما يسجّله، فبنضيف `log.exception` عشان الخطأ يظهر (مفيش توه صامت).
    """
    import logging as _logging

    h = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")}))
    h.db.set_awaiting(OWNER_ID, CID_A, "route", title="A")

    def boom(_update_id):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(h.db, "update_is_processed", boom)
    update = h.text_update(9601, "برومت")

    with caplog.at_level(_logging.ERROR, logger="bot.handlers"):
        h.process(update)  # PTB بيبتلع ApplicationHandlerStop ⇒ بيرجع عادي

    assert h.db.count_outbox() == 0  # المجموعة 0 ماشتغلتش (مفيش إرسال)
    assert h.client.sends == []
    assert any("فشل فحص حاجز التحديث" in r.message for r in caplog.records)


def test_same_update_second_write_in_transaction_rejected(tmp_path, monkeypatch):
    """التسجيل الذرّي: كتابة تانية بنفس `update_id` **جوه/بعد** الأولى ⇒ تُرفض (0).

    ده الميكانيزم اللي بيحمي سباق التزامن: الفحص جوه `BEGIN IMMEDIATE` (معاملة الكتابة)
    بيشوف «معالَج» فيرجع 0 بدل ما يعمل سجل تاني. (التزامن على نفس الاتصال مش ممكن في SQLite،
    فالحماية الفعلية للسباق = الفحص جوه المعاملة ده، والاختبار بيتحقّق منه مباشرة.)
    """
    h = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")}))
    db = h.db
    U = 9701
    first = db.add_or_group_outbox(
        CID_A, CHAT_ID, "أ", outbox.now_iso(), reengage=True, update_id=U
    )
    second = db.add_or_group_outbox(
        CID_A, CHAT_ID, "ب", outbox.now_iso(), reengage=True, update_id=U
    )

    assert first > 0
    assert second == 0  # مرفوض: نفس التحديث
    assert db.update_is_processed(U) is True
    assert db.count_outbox() == 1  # سجل واحد بس


def test_two_distinct_updates_both_written(tmp_path, monkeypatch):
    """تحديثين مختلفين لوجهتين مختلفتين ⇒ سجلين (مفيش رفض كاذب)."""
    h = _harness(tmp_path, monkeypatch, FakeOpenHands())
    db = h.db
    id1 = db.add_or_group_outbox(
        CID_A, CHAT_ID, "أ", outbox.now_iso(), reengage=True, update_id=9801
    )
    id2 = db.add_or_group_outbox(
        CID_B, CHAT_ID, "ب", outbox.now_iso(), reengage=True, update_id=9802
    )
    assert id1 > 0 and id2 > 0 and id1 != id2
    assert db.update_is_processed(9801) and db.update_is_processed(9802)
    assert db.count_outbox() == 2


def test_crash_between_guard_and_durable_write_does_not_lose_prompt(tmp_path, monkeypatch):
    """نافذة الفقد المُغلقة: عطل **بعد** الحاجز وقبل كتابة السجل الدائم ⇒ إعادة التسليم تنفّذ.

    لو التسجيل كان بيحصل عند الحاجز (التصميم القديم)، كان البرومت بيضيع للأبد. دلوقتي
    الحاجز فحص قراءة، فالتحديث مش مسجّل ⇒ إعادة التسليم بتكتب السجل الدائم وتنفّذ (مفيش فقد).
    """
    h = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")}))
    h.db.set_awaiting(OWNER_ID, CID_A, "route", title="A")
    update = h.text_update(9901, "برومت قبل العطل")

    calls = {"n": 0}
    original = h.db.add_or_group_outbox

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise sqlite3.OperationalError("crash before commit")
        return original(*args, **kwargs)

    monkeypatch.setattr(h.db, "add_or_group_outbox", flaky)

    h.process(update)  # العطل: الاستثناء بيتابتلع في PTB، والتحديث **مش** مسجّل
    assert calls["n"] == 1
    assert h.db.update_is_processed(9901) is False
    assert h.db.count_outbox() == 0

    h.process(update)  # إعادة التسليم: لازم تنفّذ (مفيش فقد)
    h.deliver_pending()

    assert h.client.sends == [(CID_A, "برومت قبل العطل")]
    assert h.db.update_is_processed(9901) is True



# ============================================================================
# OHB2-TRANSIENT-DB-FAILURE: نافذة الفقد عند فشل القاعدة **العابر** + الإصلاح.
# ============================================================================
def test_transient_db_failure_recovers_and_processes_once(tmp_path, monkeypatch):
    """فشل عابر (busy/locked) أثناء فحص الحاجز ⇒ إعادة محاولة **محدودة** ⇒ تنفيذ مرة واحدة.

    قبل الإصلاح: أول رمي كان بيوقف المعالجة فورًا (فشل مقفول) ⇒ **فقد** التحديث. دلوقتي:
    الفشل العابر بيتغطّى بمحاولات قصيرة، والتنفيذ بيكمّل عادي (سجل دائم واحد، مفيش فقد).
    """
    h = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")}))
    h.db.set_awaiting(OWNER_ID, CID_A, "route", title="A")
    update = h.text_update(4001, "برومت")

    calls = {"n": 0}
    orig = h.db.update_is_processed

    def flaky(uid):
        calls["n"] += 1
        if calls["n"] <= 2:  # أول محاولتين تفشلان (عابر)، الثالثة تنجح
            raise sqlite3.OperationalError("database is locked")
        return orig(uid)

    monkeypatch.setattr(h.db, "update_is_processed", flaky)
    monkeypatch.setattr(h_mod, "_DEDUPE_RETRY_DELAYS", (0.0, 0.0, 0.0))

    h.process(update)

    # عدّاد المحاولات يشمل فحص الحاجز + إعادة الفحص جوه معاملة الكتابة الدائم؛ المهم أن
    # الفشل العابر اتغطّى والتنفيذ كمّل.
    assert calls["n"] >= 3
    assert h.db.count_outbox() == 1  # التحديث اتعالج (مفيش فقد)
    assert orig(4001) is True  # نستخدم الأصل (المُرقَّع بيزوّد العدّاد)


def test_persistent_transient_failure_remains_fail_closed(tmp_path, monkeypatch, caplog):
    """فشل عابر **مستمر** (استنفاد الميزانية) ⇒ فشل مقفول: مفيش معالجة + تسجيل واضح.

    الإصلاح ما بيكسرش الفشل المقفول: بعد استنفاد المحاولات، بنرفع ⇒ `ApplicationHandlerStop`
    ⇒ المجموعة 0 ما بتشتغلش (مفيش صندوق، مفيش إرسال).
    """
    import logging as _logging

    h = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")}))
    h.db.set_awaiting(OWNER_ID, CID_A, "route", title="A")
    update = h.text_update(4101, "برومت")

    calls = {"n": 0}

    def always_locked(_uid):
        calls["n"] += 1
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(h.db, "update_is_processed", always_locked)
    monkeypatch.setattr(h_mod, "_DEDUPE_RETRY_DELAYS", (0.0, 0.0, 0.0))

    with caplog.at_level(_logging.ERROR, logger="bot.handlers"):
        h.process(update)

    assert calls["n"] == 1 + len(h_mod._DEDUPE_RETRY_DELAYS)  # 1 أصلية + 3 إعادات
    assert h.db.count_outbox() == 0
    assert h.client.sends == []
    assert any("فشل فحص حاجز التحديث" in r.message for r in caplog.records)


def test_permanent_db_failure_not_retried_fails_closed(tmp_path, monkeypatch, caplog):
    """فشل **دائم** (قاعدة تالفة/جدول مش موجود) ⇒ **مفيش** إعادة محاولة، فشل مقفول فورًا.

    التصنيف بيفرّق: الخطأ الدائم (OperationalError "no such table") **مش** عابر ⇒ يُرفع من
    أول مرة، فمافيش انتظار/إعادة (ما بنأخّرش المعالجة بلا داعي).
    """
    import logging as _logging

    h = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")}))
    h.db.set_awaiting(OWNER_ID, CID_A, "route", title="A")
    update = h.text_update(4201, "برومت")

    calls = {"n": 0}

    def permanent(_uid):
        calls["n"] += 1
        raise sqlite3.OperationalError("no such table: processed_updates")

    monkeypatch.setattr(h.db, "update_is_processed", permanent)

    with caplog.at_level(_logging.ERROR, logger="bot.handlers"):
        h.process(update)

    assert calls["n"] == 1  # مفيش إعادة محاولة للفشل الدائم
    assert h.db.count_outbox() == 0
    assert any("فشل فحص حاجز التحديث" in r.message for r in caplog.records)


def test_retry_helper_does_not_retry_non_sqlite_error(monkeypatch):
    """خطأ غير SQLite (مثلاً برمجي) ⇒ **مفيش** إعادة محاولة، يُرفع فورًا (فشل مقفول)."""
    calls = {"n": 0}

    class _DB:
        def update_is_processed(self, _uid):
            calls["n"] += 1
            raise RuntimeError("bug")

    monkeypatch.setattr(h_mod, "_DEDUPE_RETRY_DELAYS", (0.0, 0.0, 0.0))
    try:
        asyncio.run(h_mod._check_update_processed_with_retry(_DB(), 1))
        raise AssertionError("المفروض يرفع")
    except RuntimeError:
        pass
    assert calls["n"] == 1


def test_transient_classifier_matches_busy_locked_by_code():
    """التصنيف: BUSY/LOCKED عابر، وغيرها دائم — بالكود (sqlite_errorcode) وبالنص كاحتياطي."""
    import sqlite3 as _s

    busy = _s.OperationalError("database is locked")
    busy.sqlite_errorcode = _s.SQLITE_BUSY
    locked = _s.OperationalError("database table is locked")
    locked.sqlite_errorcode = _s.SQLITE_LOCKED
    permanent = _s.OperationalError("no such table: x")
    permanent.sqlite_errorcode = getattr(_s, "SQLITE_ERROR", 1)

    assert h_mod._is_transient_sqlite_error(busy) is True
    assert h_mod._is_transient_sqlite_error(locked) is True
    assert h_mod._is_transient_sqlite_error(permanent) is False
    assert h_mod._is_transient_sqlite_error(RuntimeError("x")) is False
    # احتياطي النص (خطأ بدون كود)
    assert h_mod._is_transient_sqlite_error(_s.OperationalError("database is busy")) is True


def test_transient_retry_preserves_dedup_no_double_processing(tmp_path, monkeypatch):
    """بعد نجاح إعادة المحاولة، إعادة تسليم **نفس** التحديث تفضل مرفوضة (مفيش ازدواج)."""
    h = _harness(tmp_path, monkeypatch, FakeOpenHands({CID_A: _conv(CID_A, "owner/repo")}))
    h.db.set_awaiting(OWNER_ID, CID_A, "route", title="A")
    update = h.text_update(4301, "برومت")

    calls = {"n": 0}
    orig = h.db.update_is_processed

    def flaky(uid):
        calls["n"] += 1
        if calls["n"] == 1:
            raise sqlite3.OperationalError("database is locked")
        return orig(uid)

    monkeypatch.setattr(h.db, "update_is_processed", flaky)
    monkeypatch.setattr(h_mod, "_DEDUPE_RETRY_DELAYS", (0.0, 0.0, 0.0))

    h.process(update)
    assert h.db.count_outbox() == 1
    h.deliver_pending()
    assert h.client.sends == [(CID_A, "برومت")]

    # إعادة تسليم نفس التحديث ⇒ مرفوضة (الحاجز شاف العلامة الدائمة)
    h.process(update)
    h.deliver_pending()
    assert h.client.sends == [(CID_A, "برومت")]  # لسه مرة واحدة
    assert h.db.count_outbox() == 1


def test_transient_retry_does_not_lose_unrelated_updates(tmp_path, monkeypatch):
    """فشل عابر على تحديث واحد لا يؤثّر على تحديثات تانية (مفيش فقد/معالجة خاطئة)."""
    h = _harness(
        tmp_path,
        monkeypatch,
        FakeOpenHands({CID_A: _conv(CID_A, "owner/repo"), CID_B: _conv(CID_B, "owner/repo")}),
    )
    # حالة الانتظار صف واحد لكل مستخدم، فبنضبط الوجهة قبل معالجة كل تحديث على حدة
    # (وجهتان مختلفتان ⇒ سجلان، مفيش دمج).
    h.db.set_awaiting(OWNER_ID, CID_A, "route", title="A")
    bad = h.text_update(4401, "أول")

    calls = {"n": 0}
    orig = h.db.update_is_processed

    def flaky(uid):
        if uid == 4401:
            calls["n"] += 1
            if calls["n"] == 1:  # فشل عابر مرة واحدة ⇒ يتعافى
                raise sqlite3.OperationalError("database is locked")
        return orig(uid)

    monkeypatch.setattr(h.db, "update_is_processed", flaky)
    monkeypatch.setattr(h_mod, "_DEDUPE_RETRY_DELAYS", (0.0, 0.0, 0.0))

    h.process(bad)   # عابر ⇒ يتعافى
    h.db.set_awaiting(OWNER_ID, CID_B, "route", title="B")
    good = h.text_update(4402, "تاني")
    h.process(good)  # سليم ⇒ يعالج

    assert h.db.count_outbox() == 2  # الاتنين اتسجّلوا (مفيش فقد)
    assert orig(4401) is True
    assert orig(4402) is True


def test_dedupe_read_not_blocked_by_concurrent_writer_separate_connections(tmp_path):
    """WAL: قراءة الحاجز على **اتصال منفصل** مش بتتحاصر بكاتب متزامن.

    ده يوضّح إن نافذة الفشل العابر الحقيقية للقراءة ضيّقة جدًا (WAL)، فإعادة المحاولة
    شبكة أمان صغيرة مش مسار أساسي. بنستخدم اتصالين منفصلين على نفس الملف.
    """
    from bot.db import Database

    p = str(tmp_path / "t.sqlite3")
    writer = Database(p)
    reader = Database(p)  # اتصال منفصل
    writer._conn.execute("BEGIN IMMEDIATE")
    writer._conn.execute(
        "INSERT INTO processed_updates(update_id, processed_at) VALUES(?, ?)", (12345, "t")
    )
    try:
        # القارئ (اتصال منفصل) يقرأ فورًا بدون حظر/استثناء في WAL، ومايشوفش الكتابة غير
        # المُـcommit (عزل) ⇒ False.
        assert reader.update_is_processed(12345) is False
        assert reader.update_is_processed(1) is False
    finally:
        writer._conn.rollback()
        writer._conn.close()
        reader._conn.close()


def test_helper_recovers_from_real_sqlite_busy_separate_connections(tmp_path, monkeypatch):
    """إعادة المحاولة بتتعافى من خطأ `SQLITE_BUSY` **حقيقي** (اتصالان منفصلان).

    الكاتب ماسك قفل كتابة، وقارئ بـ `busy_timeout=0` بيحاول `BEGIN IMMEDIATE` ⇒
    `OperationalError` حقيقي بكود `SQLITE_BUSY`. بعد ما الكاتب يسيب القفل، المحاولة
    التانية بتنجح. ده يتحقّق من مسار التصنيف+الإعادة على خطأ SQLite حقيقي مش مُصطنع.
    """
    from bot.db import Database

    p = str(tmp_path / "t.sqlite3")
    writer = Database(p)
    reader = Database(p)  # اتصال منفصل
    reader._conn.execute("PRAGMA busy_timeout=0")  # فشل فوري بدل انتظار

    writer._conn.execute("BEGIN IMMEDIATE")
    writer._conn.execute("INSERT INTO processed_updates(update_id, processed_at) VALUES(1, 't')")

    state = {"n": 0}

    def check(_uid):
        state["n"] += 1
        if state["n"] == 1:
            # أول محاولة: الكاتب ماسك القفل ⇒ خطأ BUSY حقيقي. بنسيبه (rollback) عشان
            # المحاولة الجاية تنجح، وبعدين بنرفع الخطأ الأصلي للـ helper.
            try:
                reader._conn.execute("BEGIN IMMEDIATE")
                reader._conn.rollback()
                return True
            except sqlite3.OperationalError:
                writer._conn.rollback()
                raise
        reader._conn.execute("BEGIN IMMEDIATE")
        reader._conn.rollback()
        return True

    monkeypatch.setattr(h_mod, "_DEDUPE_RETRY_DELAYS", (0.0, 0.0, 0.0))
    try:
        result = asyncio.run(
            h_mod._check_update_processed_with_retry(
                SimpleNamespace(update_is_processed=check), 1
            )
        )
    finally:
        writer._conn.close()
        reader._conn.close()

    assert result is True
    assert state["n"] == 2  # محاولة فاشلة (BUSY حقيقي) + محاولة ناجحة
