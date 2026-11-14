"""OHB2-SW03: دلالات فلترة الشواهد (نجاح/فراغ/فشل) متطابقة بين البوت والـ Mini App.

الفشل **ينتشر** (مفيش قايمة فاضية مضلّلة)، والفراغ الحقيقي/الفلترة الناجحة لسه `[]` مشروعة.
"""
from __future__ import annotations

import os

import pytest

import bot.handlers as h
from bot import outbox
from bot.config import Config
from bot.db import Database
from bot.web.services import MiniAppService

OWNER_UUID = "owner-uuid-123"
BOT_TOKEN = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"


def _db(tmp_path) -> Database:
    return Database(os.path.join(tmp_path, "sw03f.sqlite3"))


def _config() -> Config:
    return Config(
        telegram_bot_token=BOT_TOKEN,
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({1}),
        owner_id=1,
        db_path=":memory:",
    )


def _conv(cid: str) -> dict:
    return {"id": cid, "title": cid, "execution_status": "running",
            "created_by_user_id": OWNER_UUID}


def _bot_filter(db, items):
    return h._without_deleted(db, items)


def _mini_filter(db, items):
    return MiniAppService(_config(), db)._without_deleted(items)


FILTERS = [("bot", _bot_filter), ("miniapp", _mini_filter)]


@pytest.mark.parametrize("name,flt", FILTERS)
def test_nonempty_no_tombstones_returns_complete_list(tmp_path, name, flt):
    db = _db(tmp_path)
    items = [_conv("c1"), _conv("c2"), _conv("c3")]
    assert [c["id"] for c in flt(db, items)] == ["c1", "c2", "c3"]


@pytest.mark.parametrize("name,flt", FILTERS)
def test_single_tombstone_filtered_out(tmp_path, name, flt):
    db = _db(tmp_path)
    db.delete_conversation("c2", outbox.now_iso(), remote_confirmed=True)
    items = [_conv("c1"), _conv("c2"), _conv("c3")]
    assert [c["id"] for c in flt(db, items)] == ["c1", "c3"]


@pytest.mark.parametrize("name,flt", FILTERS)
def test_all_tombstoned_produces_genuine_empty(tmp_path, name, flt):
    db = _db(tmp_path)
    for cid in ("c1", "c2"):
        db.delete_conversation(cid, outbox.now_iso(), remote_confirmed=True)
    assert flt(db, [_conv("c1"), _conv("c2")]) == []


@pytest.mark.parametrize("name,flt", FILTERS)
def test_genuine_empty_input_no_db_calls(tmp_path, name, flt):
    class _NoCallDB:
        def is_deleted_with_retry(self, cid):  # pragma: no cover
            raise AssertionError("ممنوع نداء القاعدة على مدخل فاضي")

    assert flt(_NoCallDB(), []) == []


@pytest.mark.parametrize("name,flt", FILTERS)
def test_error_on_first_item_propagates(tmp_path, name, flt):
    class _Boom:
        def is_deleted_with_retry(self, cid):
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        flt(_Boom(), [_conv("c1"), _conv("c2")])


@pytest.mark.parametrize("name,flt", FILTERS)
def test_error_after_successful_lookups_no_partial_list(tmp_path, name, flt):
    calls = {"n": 0}

    class _LateFail:
        def is_deleted_with_retry(self, cid):
            calls["n"] += 1
            if calls["n"] == 2:  # فشل بعد نجاح الأول
                raise RuntimeError("late boom")
            return False

    with pytest.raises(RuntimeError, match="late boom"):
        flt(_LateFail(), [_conv("c1"), _conv("c2"), _conv("c3")])
    assert calls["n"] == 2


@pytest.mark.parametrize("name,flt", FILTERS)
def test_f1_all_active_tombstone_states_filtered(tmp_path, name, flt):
    """F-1: كل حالات الشاهد الفعّالة (deleted/deleting/uncertain/legacy) تفضل محجوبة."""
    db = _db(tmp_path)
    now = outbox.now_iso()
    db.delete_conversation("deleted", now, remote_confirmed=True)
    db.begin_remote_deletion("deleting", now)
    db.begin_remote_deletion("uncertain", now)
    db.set_remote_deletion_state("uncertain", db.REMOTE_UNCERTAIN, now)
    db.delete_conversation("legacy", now)  # بلا حالة بعيدة
    items = [_conv(c) for c in ("deleted", "deleting", "uncertain", "legacy", "visible")]
    assert [c["id"] for c in flt(db, items)] == ["visible"]
