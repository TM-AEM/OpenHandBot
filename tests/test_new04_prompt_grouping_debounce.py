"""NEW-04: durable 3-second inactivity grouping, restart, recovery, cancellation."""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from bot import outbox
from bot.db import (
    Database,
    GROUP_WINDOW,
    OUTBOX_CLAIMED,
    OUTBOX_PENDING,
    OUTBOX_SENT,
)
from tests.test_handlers import make_context, make_update
from tests.test_outbox import Bot, Client, make_worker

import bot.handlers as h

T0 = datetime(2026, 11, 22, 12, 0, 0, tzinfo=timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _add_batch(db: Database, *parts: tuple[int, str], start: datetime = T0) -> int:
    first_id, first_text = parts[0]
    outbox_id = db.add_or_group_outbox(
        "c1", 99, first_text, _iso(start), telegram_message_id=first_id
    )
    for offset, (message_id, text) in enumerate(parts[1:], start=1):
        assert db.add_or_group_outbox(
            "c1", 99, text, _iso(start + timedelta(seconds=offset)),
            telegram_message_id=message_id,
        ) == outbox_id
    return outbox_id


def test_group_window_is_three_seconds():
    assert GROUP_WINDOW == timedelta(seconds=3)


def test_pending_batch_survives_restart_and_is_sent_once(tmp_path, monkeypatch):
    path = str(tmp_path / "restart.sqlite3")
    db = Database(path)
    try:
        outbox_id = _add_batch(db, (11, "أ"), (12, "ب"))
    finally:
        db.close()

    reopened = Database(path)
    try:
        client = Client()
        worker = make_worker(reopened, client=client)
        monkeypatch.setattr("bot.db.GROUP_WINDOW", timedelta(0))
        assert asyncio.run(worker._tick()) is True
        assert client.sent == [("c1", "أ\nب")]
        assert reopened.get_outbox(outbox_id).status == OUTBOX_SENT
        assert asyncio.run(worker._tick()) is False
        assert client.sent == [("c1", "أ\nب")]
    finally:
        reopened.close()


def test_expired_deadline_while_process_unavailable_is_recovered(tmp_path, monkeypatch):
    path = str(tmp_path / "expired.sqlite3")
    db = Database(path)
    try:
        outbox_id = _add_batch(db, (21, "جزء أول"), (22, "جزء تاني"))
        # Deadline expired long before the new process starts.
        assert db.get_outbox(outbox_id).updated_at == _iso(T0 + timedelta(seconds=1))
    finally:
        db.close()

    reopened = Database(path)
    try:
        client = Client()
        worker = make_worker(reopened, client=client)
        monkeypatch.setattr("bot.db.GROUP_WINDOW", timedelta(0))
        assert asyncio.run(worker._tick()) is True
        assert client.sent == [("c1", "جزء أول\nجزء تاني")]
    finally:
        reopened.close()


def test_claimed_batch_is_returned_to_pending_after_crash(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "claimed.sqlite3"))
    try:
        outbox_id = _add_batch(db, (31, "أ"), (32, "ب"))
        claimed = db.claim_outbox(_iso(T0 + timedelta(seconds=10)))
        assert claimed is not None and claimed.id == outbox_id
        assert db.get_outbox(outbox_id).status == OUTBOX_CLAIMED

        asyncio.run(outbox.outbox_recover(SimpleNamespace(bot_data={"db": db}, bot=Bot())))
        assert db.get_outbox(outbox_id).status == OUTBOX_PENDING

        client = Client()
        worker = make_worker(db, client=client)
        monkeypatch.setattr("bot.db.GROUP_WINDOW", timedelta(0))
        assert asyncio.run(worker._tick()) is True
        assert client.sent == [("c1", "أ\nب")]
    finally:
        db.close()


def test_worker_waits_for_three_seconds_after_last_part(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "debounce.sqlite3"))
    try:
        outbox_id = _add_batch(db, (81, "أ"), (82, "ب"), (83, "ج"))
        client = Client()
        worker = make_worker(db, client=client)
        clock = [T0 + timedelta(seconds=2)]
        monkeypatch.setattr(outbox, "_utcnow", lambda: clock[0])
        assert asyncio.run(worker._tick()) is False
        assert client.sent == []

        clock[0] = T0 + timedelta(seconds=4.9)
        assert asyncio.run(worker._tick()) is False
        assert client.sent == []

        clock[0] = T0 + timedelta(seconds=5)
        assert asyncio.run(worker._tick()) is True
        assert client.sent == [("c1", "أ\nب\nج")]
        assert db.get_outbox(outbox_id).status == OUTBOX_SENT
    finally:
        db.close()


def test_legacy_row_without_parts_preserves_ids_when_grouped(tmp_path):
    db = Database(str(tmp_path / "legacy.sqlite3"))
    try:
        first = db.add_outbox("c1", 99, "قديم", _iso(T0), telegram_message_id=91)
        db._conn.execute(
            "UPDATE outbox SET telegram_message_parts='[]' WHERE id=?", (first,)
        )
        db._conn.commit()
        assert db.add_or_group_outbox(
            "c1", 99, "جديد", _iso(T0 + timedelta(seconds=1)),
            telegram_message_id=92,
        ) == first
        item = db.get_outbox(first)
        assert item.text == "قديم\nجديد"
        assert item.telegram_message_ids == (91, 92)
    finally:
        db.close()


def test_duplicate_message_identity_does_not_create_second_logical_prompt(tmp_path):
    db = Database(str(tmp_path / "duplicate.sqlite3"))
    try:
        first = db.add_or_group_outbox(
            "c1", 99, "أصل", _iso(T0), telegram_message_id=41, update_id=7001
        )
        duplicate = db.add_or_group_outbox(
            "c1", 99, "نسخة مكررة", _iso(T0 + timedelta(seconds=1)),
            telegram_message_id=41, update_id=7002,
        )
        assert duplicate == first
        assert db.count_outbox(OUTBOX_PENDING) == 1
        item = db.get_outbox(first)
        assert item.text == "أصل"
        assert item.telegram_message_ids == (41,)
    finally:
        db.close()


def test_chat_and_destination_isolation(tmp_path):
    db = Database(str(tmp_path / "isolation.sqlite3"))
    try:
        a = db.add_or_group_outbox("c1", 99, "a", _iso(T0), telegram_message_id=51)
        b = db.add_or_group_outbox("c2", 99, "b", _iso(T0), telegram_message_id=52)
        c = db.add_or_group_outbox("c1", 55, "c", _iso(T0), telegram_message_id=53)
        assert len({a, b, c}) == 3
        assert db.count_outbox(OUTBOX_PENDING) == 3
    finally:
        db.close()


def test_selection_change_during_pending_batch_does_not_regroup_across_targets(tmp_path):
    ctx = make_context(1, tmp_path)
    db = ctx.bot_data["db"]
    db.set_last_accessed_conversation(1, "A")
    first = make_update(1, "الجزء الأول")
    first.update_id = 8101
    first.message.message_id = 61
    asyncio.run(h.handle_text(first, ctx))
    assert db.count_outbox(OUTBOX_PENDING) == 1

    db.set_last_accessed_conversation(1, "B")
    second = make_update(1, "الجزء الثاني")
    second.update_id = 8102
    second.message.message_id = 62
    asyncio.run(h.handle_text(second, ctx))

    items = db.list_outbox_by_status(OUTBOX_PENDING)
    assert len(items) == 2
    assert {item.conversation_id for item in items} == {"A", "B"}


def test_refreshed_batch_is_not_claimed_until_new_deadline(tmp_path):
    db = Database(str(tmp_path / "refresh.sqlite3"))
    try:
        outbox_id = db.add_or_group_outbox(
            "c1", 99, "first", _iso(T0), telegram_message_id=73
        )
        assert db.add_or_group_outbox(
            "c1", 99, "second", _iso(T0 + timedelta(seconds=1)),
            telegram_message_id=74,
        ) == outbox_id
        # Old deadline has passed, but the append refreshed updated_at: the worker
        # must not claim a partially-windowed batch.
        assert db.claim_outbox(
            _iso(T0 + timedelta(seconds=1)),
            mature_before=_iso(T0 + timedelta(seconds=0.5)),
        ) is None
        assert db.get_outbox(outbox_id).text == "first\nsecond"
    finally:
        db.close()


def test_concurrent_claim_and_append_never_lose_content(tmp_path):
    db = Database(str(tmp_path / "race.sqlite3"))
    try:
        outbox_id = db.add_or_group_outbox(
            "c1", 99, "first", _iso(T0), telegram_message_id=71
        )
        # Append is inside the old batch's window; claim is allowed only if the row
        # was not refreshed by that append. Whichever transaction wins, no part is lost.
        claimed = db.claim_outbox(
            _iso(T0 + timedelta(seconds=1)),
            mature_before=_iso(T0 + timedelta(seconds=0.5)),
        )
        appended = db.add_or_group_outbox(
            "c1", 99, "second", _iso(T0 + timedelta(seconds=1)),
            telegram_message_id=72,
        )
        if claimed is not None:
            assert claimed.id == outbox_id
            assert appended != outbox_id
            rows = [db.get_outbox(outbox_id), db.get_outbox(appended)]
        else:
            assert appended == outbox_id
            rows = [db.get_outbox(outbox_id)]
        all_text = "\n".join(item.text for item in rows if item is not None)
        all_ids = tuple(
            message_id for item in rows if item is not None
            for message_id in item.telegram_message_ids
        )
        assert "first" in all_text and "second" in all_text
        assert all_ids == (71, 72)
    finally:
        db.close()
