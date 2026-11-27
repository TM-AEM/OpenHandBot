import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from telegram.error import BadRequest, RetryAfter, TelegramError

import bot.handlers as h
from bot import keyboards as kb
from bot import outbox
from bot.db import Database, Watched
from bot.errors import ApiError
from bot.messages import format_conversation_view
from bot.refresh import (
    ConversationRefreshService,
    ConversationRefreshWorker,
    REFRESH_INTERVAL_SECONDS,
    view_fingerprint,
)

OWNER_ID = 7
OWNER_UUID = "owner-uuid-123"
CID = "a" * 32


class Clock:
    def __init__(self):
        self.value = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += timedelta(seconds=seconds)

    def now_iso(self):
        return self.value.isoformat()


class FakeConfig:
    def __init__(self):
        self.allowed_telegram_ids = frozenset({OWNER_ID})
        self.owner_id = OWNER_ID
        self.mini_app_enabled = False
        self.mini_app_url = ""

    def is_allowed(self, user_id):
        return user_id in self.allowed_telegram_ids


class FakeClient:
    def __init__(self, conv=None, exchange=(None, None), *, conv_error=None, exchange_error=None,
                 send_error=None):
        self.conv = conv if conv is not None else {
            "id": CID,
            "title": "شات",
            "execution_status": "running",
            "sandbox_status": "RUNNING",
            "created_by_user_id": OWNER_UUID,
        }
        self.exchange = exchange
        self.conv_error = conv_error
        self.exchange_error = exchange_error
        self.send_error = send_error
        self.conv_calls = 0
        self.sent = []

    async def get_conversations(self, ids):
        self.conv_calls += 1
        if self.conv_error is not None:
            raise self.conv_error
        return [self.conv] if self.conv else []

    async def get_current_user(self):
        return {"id": OWNER_UUID}

    async def get_last_exchange(self, conversation_id):
        if self.exchange_error is not None:
            raise self.exchange_error
        return self.exchange

    async def send_message(self, conversation_id, text):
        if self.send_error is not None:
            raise self.send_error
        self.sent.append((conversation_id, text))


class FakeBot:
    def __init__(self):
        self.edits = []
        self.sent = []
        self.edit_error = None

    async def edit_message_text(self, **kwargs):
        if self.edit_error is not None:
            raise self.edit_error
        self.edits.append(kwargs)

    async def send_message(self, chat_id=None, text=None, **kwargs):
        self.sent.append(text)


def make_service(tmp_path, client=None, bot=None, clock=None):
    db = Database(str(tmp_path / "refresh.sqlite3"))
    service = ConversationRefreshService(
        client or FakeClient(),
        db,
        bot or FakeBot(),
        clock=clock or Clock(),
    )
    return db, service


def record(service, *, text="قديم", markup=None):
    service.record_view(
        telegram_id=OWNER_ID,
        conversation_id=CID,
        chat_id=OWNER_ID,
        message_id=100,
        text=text,
        markup=markup if markup is not None else kb.conversation_actions(CID),
        terminal=False,
    )
    return service.db.get_conversation_view(OWNER_ID, CID)


def parse(value):
    return datetime.fromisoformat(value)


def test_refresh_button_is_removed_from_conversation_keyboard():
    markup = kb.conversation_actions(CID, has_reply=True, reply_cut=True)
    callbacks = [b.callback_data for row in markup.inline_keyboard for b in row if b.callback_data]
    labels = [b.text for row in markup.inline_keyboard for b in row]
    assert f"open:{CID}" not in callbacks
    assert "تحديث" not in labels
    # The shared open callback remains for lists and delete-cancel.
    watches = kb.watches_menu(
        [Watched(CID, "شات", "running")], 0, has_more=False
    )
    assert f"open:{CID}" in [
        b.callback_data for row in watches.inline_keyboard for b in row if b.callback_data
    ]


def test_open_records_target_without_changing_last_accessed_contract(tmp_path):
    client = FakeClient(exchange=("برومت", "رد"))
    bot = FakeBot()
    clock = Clock()
    db, service = make_service(tmp_path, client=client, bot=bot, clock=clock)

    q = SimpleNamespace(
        data=f"open:{CID}",
        message=SimpleNamespace(chat_id=OWNER_ID, message_id=100),
        edits=[],
        async_answer=None,
    )

    async def answer():
        return None

    async def edit_message_text(text, **kwargs):
        q.edits.append((text, kwargs))

    q.answer = answer
    q.edit_message_text = edit_message_text
    update = SimpleNamespace(
        update_id=1,
        effective_user=SimpleNamespace(id=OWNER_ID),
        effective_chat=SimpleNamespace(id=OWNER_ID, type="private"),
        message=SimpleNamespace(reply_text=None),
        callback_query=q,
    )
    ctx = SimpleNamespace(
        bot=bot,
        bot_data={
            "config": FakeConfig(),
            "db": db,
            "client": client,
            "refresh_service": service,
        },
    )

    asyncio.run(h.open_conversation(update, ctx))

    target = db.get_conversation_view(OWNER_ID, CID)
    assert target is not None
    assert target.active is True
    assert target.message_id == 100
    assert target.chat_id == OWNER_ID
    assert parse(target.next_check_at) - clock.value == timedelta(seconds=REFRESH_INTERVAL_SECONDS)
    assert db.get_last_accessed_conversation(OWNER_ID) == CID
    assert q.edits


def test_chat_command_records_the_sent_message_for_refresh(tmp_path):
    client = FakeClient(exchange=("برومت", "رد"))
    bot = FakeBot()
    db, service = make_service(tmp_path, client=client, bot=bot)
    db.set_last_accessed_conversation(OWNER_ID, CID)

    sent = SimpleNamespace(chat_id=OWNER_ID, message_id=555)

    async def reply_text(text, **kwargs):
        return sent

    update = SimpleNamespace(
        update_id=2,
        effective_user=SimpleNamespace(id=OWNER_ID),
        effective_chat=SimpleNamespace(id=OWNER_ID, type="private"),
        message=SimpleNamespace(reply_text=reply_text),
        callback_query=None,
    )
    ctx = SimpleNamespace(
        bot=bot,
        bot_data={
            "config": FakeConfig(),
            "db": db,
            "client": client,
            "refresh_service": service,
        },
    )

    asyncio.run(h.chat(update, ctx))

    target = db.get_conversation_view(OWNER_ID, CID)
    assert target is not None
    assert target.message_id == 555


def test_confirmed_prompt_schedules_immediate_refresh(tmp_path):
    client = FakeClient()
    bot = FakeBot()
    clock = Clock()
    db, service = make_service(tmp_path, client=client, bot=bot, clock=clock)
    record(service)

    outbox_id = db.add_outbox(CID, OWNER_ID, "برومت", outbox.now_iso())
    claimed = db.claim_outbox_by_id(outbox_id, outbox.now_iso())
    assert claimed is not None

    asyncio.run(
        outbox._post_claimed(
            client,
            db,
            bot,
            claimed,
            on_sent=lambda conversation_id, chat_id: service.request_immediate(
                conversation_id, chat_id
            ),
        )
    )

    target = db.get_conversation_view(OWNER_ID, CID)
    assert target is not None
    assert target.active is True
    assert parse(target.next_check_at) == clock.value


def test_failed_prompt_does_not_schedule_refresh(tmp_path):
    client = FakeClient(send_error=ApiError("rejected", 400))
    bot = FakeBot()
    db, service = make_service(tmp_path, client=client, bot=bot)
    record(service)
    before = db.get_conversation_view(OWNER_ID, CID)

    outbox_id = db.add_outbox(CID, OWNER_ID, "برومت", outbox.now_iso())
    claimed = db.claim_outbox_by_id(outbox_id, outbox.now_iso())
    assert claimed is not None

    calls = []
    asyncio.run(
        outbox._post_claimed(
            client, db, bot, claimed,
            on_sent=lambda conversation_id, chat_id: calls.append(conversation_id),
        )
    )

    after = db.get_conversation_view(OWNER_ID, CID)
    assert calls == []
    assert after.next_check_at == before.next_check_at


def test_periodic_refresh_edits_changed_view_and_reschedules_35_seconds(tmp_path):
    client = FakeClient(exchange=("برومت", "رد جديد"))
    bot = FakeBot()
    clock = Clock()
    db, service = make_service(tmp_path, client=client, bot=bot, clock=clock)
    target = record(service)

    asyncio.run(service.refresh(target))

    assert len(bot.edits) == 1
    edit = bot.edits[0]
    assert edit["chat_id"] == OWNER_ID
    assert edit["message_id"] == 100
    assert "رد جديد" in edit["text"]
    after = db.get_conversation_view(OWNER_ID, CID)
    assert after.active is True
    assert after.failures == 0
    assert parse(after.next_check_at) - clock.value == timedelta(seconds=REFRESH_INTERVAL_SECONDS)


def test_unchanged_view_does_not_call_telegram_edit(tmp_path):
    client = FakeClient(exchange=("برومت", "رد"))
    bot = FakeBot()
    clock = Clock()
    db, service = make_service(tmp_path, client=client, bot=bot, clock=clock)
    target = record(service)
    asyncio.run(service.refresh(target))
    assert len(bot.edits) == 1

    current = db.get_conversation_view(OWNER_ID, CID)
    asyncio.run(service.refresh(current))
    assert len(bot.edits) == 1
    assert parse(db.get_conversation_view(OWNER_ID, CID).next_check_at) - clock.value == timedelta(
        seconds=REFRESH_INTERVAL_SECONDS
    )


def test_terminal_refresh_edits_once_then_deactivates(tmp_path):
    client = FakeClient(exchange=("برومت", "تم"))
    client.conv["execution_status"] = "finished"
    bot = FakeBot()
    clock = Clock()
    db, service = make_service(tmp_path, client=client, bot=bot, clock=clock)
    target = record(service)

    asyncio.run(service.refresh(target))

    assert len(bot.edits) == 1
    after = db.get_conversation_view(OWNER_ID, CID)
    assert after.active is False
    assert after.next_check_at is None
    assert db.claim_due_conversation_view(clock.now_iso(), service.deadline(120)) is None


def test_transient_api_failure_backs_off_without_deactivating(tmp_path):
    client = FakeClient(conv_error=ApiError("busy", 503))
    bot = FakeBot()
    clock = Clock()
    db, service = make_service(tmp_path, client=client, bot=bot, clock=clock)
    target = record(service)

    asyncio.run(service.refresh(target))

    after = db.get_conversation_view(OWNER_ID, CID)
    assert after.active is True
    assert after.failures == 1
    assert parse(after.next_check_at) > clock.value
    assert bot.edits == []


def test_permanent_api_failure_deactivates_without_edit(tmp_path):
    client = FakeClient(conv_error=ApiError("gone", 404))
    bot = FakeBot()
    db, service = make_service(tmp_path, client=client, bot=bot)
    target = record(service)

    asyncio.run(service.refresh(target))

    after = db.get_conversation_view(OWNER_ID, CID)
    assert after.active is False
    assert bot.edits == []


def test_tombstoned_conversation_deactivates_without_upstream_call(tmp_path):
    client = FakeClient()
    bot = FakeBot()
    db, service = make_service(tmp_path, client=client, bot=bot)
    target = record(service)
    db._conn.execute(
        "INSERT OR IGNORE INTO deleted_conversations(conversation_id, deleted_at) VALUES(?, ?)",
        (CID, outbox.now_iso()),
    )
    db._conn.commit()

    asyncio.run(service.refresh(target))

    assert client.conv_calls == 0
    assert db.get_conversation_view(OWNER_ID, CID).active is False
    assert bot.edits == []


def test_not_modified_edit_is_success_and_updates_fingerprint(tmp_path):
    client = FakeClient(exchange=("برومت", "رد"))
    bot = FakeBot()
    bot.edit_error = BadRequest("Message is not modified")
    db, service = make_service(tmp_path, client=client, bot=bot)
    target = record(service)

    asyncio.run(service.refresh(target))

    expected_text, reply_cut = format_conversation_view(client.conv, "برومت", "رد")
    expected_markup = kb.conversation_actions(
        CID, False, has_reply=True, reply_cut=reply_cut,
        mini_app_url="", files_cb=None,
    )
    after = db.get_conversation_view(OWNER_ID, CID)
    assert after.active is True
    assert after.last_fingerprint == view_fingerprint(expected_text, expected_markup)


def test_permanent_telegram_edit_failure_deactivates(tmp_path):
    client = FakeClient(exchange=("برومت", "رد"))
    bot = FakeBot()
    bot.edit_error = BadRequest("message to edit not found")
    db, service = make_service(tmp_path, client=client, bot=bot)
    target = record(service)

    asyncio.run(service.refresh(target))

    assert db.get_conversation_view(OWNER_ID, CID).active is False


def test_transient_telegram_edit_failure_backs_off(tmp_path):
    client = FakeClient(exchange=("برومت", "رد"))
    bot = FakeBot()
    bot.edit_error = TelegramError("temporary")
    clock = Clock()
    db, service = make_service(tmp_path, client=client, bot=bot, clock=clock)
    target = record(service)

    asyncio.run(service.refresh(target))

    after = db.get_conversation_view(OWNER_ID, CID)
    assert after.active is True
    assert after.failures == 1
    assert parse(after.next_check_at) > clock.value


def test_retry_after_edit_uses_telegram_delay(tmp_path):
    client = FakeClient(exchange=("برومت", "رد"))
    bot = FakeBot()
    bot.edit_error = RetryAfter(7)
    clock = Clock()
    db, service = make_service(tmp_path, client=client, bot=bot, clock=clock)
    target = record(service)

    asyncio.run(service.refresh(target))

    after = db.get_conversation_view(OWNER_ID, CID)
    assert after.active is True
    assert parse(after.next_check_at) - clock.value == timedelta(seconds=7)


def test_claim_lease_prevents_overlapping_refresh_cycles(tmp_path):
    clock = Clock()
    db, service = make_service(tmp_path, clock=clock)
    record(service)
    db.upsert_conversation_view(
        telegram_id=OWNER_ID,
        conversation_id=CID,
        chat_id=OWNER_ID,
        message_id=100,
        last_fingerprint="old",
        active=True,
        next_check_at=clock.now_iso(),
        now=clock.now_iso(),
    )

    first = db.claim_due_conversation_view(clock.now_iso(), service.deadline(120))
    second = db.claim_due_conversation_view(clock.now_iso(), service.deadline(120))
    assert first is not None
    assert second is None


def test_worker_idles_until_the_exact_refresh_deadline(tmp_path):
    client = FakeClient(exchange=("برومت", "رد"))
    bot = FakeBot()
    clock = Clock()
    db, service = make_service(tmp_path, client=client, bot=bot, clock=clock)
    record(service)
    worker = ConversationRefreshWorker(service, poll_interval=0.01, max_idle=REFRESH_INTERVAL_SECONDS)

    assert abs(worker._idle_delay() - REFRESH_INTERVAL_SECONDS) < 0.01
    assert worker._claim() is None  # not due yet

    clock.advance(REFRESH_INTERVAL_SECONDS)
    target = worker._claim()
    assert target is not None
    asyncio.run(worker._process(target))
    assert len(bot.edits) == 1
    assert abs(worker._idle_delay() - REFRESH_INTERVAL_SECONDS) < 0.01


def test_active_schedule_survives_a_new_service_instance(tmp_path):
    client = FakeClient(exchange=("برومت", "رد"))
    bot = FakeBot()
    clock = Clock()
    db, service = make_service(tmp_path, client=client, bot=bot, clock=clock)
    record(service)
    db.upsert_conversation_view(
        telegram_id=OWNER_ID,
        conversation_id=CID,
        chat_id=OWNER_ID,
        message_id=100,
        last_fingerprint="old",
        active=True,
        next_check_at=clock.now_iso(),
        now=clock.now_iso(),
    )

    restarted = ConversationRefreshService(client, db, bot, clock=clock)
    target = db.claim_due_conversation_view(clock.now_iso(), restarted.deadline(120))
    asyncio.run(restarted.refresh(target))

    assert len(bot.edits) == 1
    assert db.get_conversation_view(OWNER_ID, CID).active is True
