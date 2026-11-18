"""OHB2-WP-04 (الجزء 1) — اختبارات مصنّف الفشل العابر (`_classify_failure`) + تثبيت
**التسلسل** في حلقة الاستطلاع.

المطلوب (DEF-002): الأخطاء الشبكية/التيليجرام **العابرة** تتّصنّف `FAILED_TRANSIENT`
(إعادة محاولة الدفعة)، بينما الفشل المحلي غير الشبكي (`PermissionError`/`FileNotFoundError`/
`ENOSPC`) يفضل `FAILED_PERMANENT`. الاختبار الحاسم: `BadRequest` **مش** عابر رغم إنه فرع
من `NetworkError` في PTB 22.8.

كمان بيثبّت **قيدًا صريحًا** من WP-04 Part 1: `TelegramPoller.process_updates` بيوزّع
التحديثات **بالتسلسل** (`dispatch_and_wait` واحد-واحد) — ممنوع معالجة متوازية
(`OD-04` مسدود). الاختبار ده يكسر لو حصل تحوّل لـ `asyncio.gather`.

الجزء 2 (أوامر `/updates_*`) **غير مُنفَّذ**: مسدود على قرار المالك `OD-02`.
"""
import asyncio
import errno
import sqlite3

import httpx
import pytest
from telegram import Update
from telegram.error import BadRequest, NetworkError, RetryAfter, TimedOut
from telegram.ext import TypeHandler

import bot.handlers as h
from bot import update_outcomes as uo
from bot.errors import ApiError
from bot.handlers import _classify_failure
from bot.polling import TelegramPoller
from tests.test_stage2_custom_polling import _text, _with_started_app


# --------------------------------------------------- transient: telegram / network
@pytest.mark.parametrize(
    "exc",
    [
        RetryAfter(3),
        TimedOut("timed out"),
        NetworkError("net down"),
        asyncio.TimeoutError(),
        httpx.ConnectError("conn"),
        httpx.ReadTimeout("read"),
        httpx.TransportError("transport"),
        ConnectionResetError("reset"),
        BrokenPipeError("pipe"),
        ConnectionRefusedError("refused"),
        OSError(errno.EAGAIN, "again"),
        OSError(errno.ECONNRESET, "reset"),
        OSError(errno.ETIMEDOUT, "timeout"),
    ],
)
def test_transient_network_errors_are_failed_transient(exc):
    assert _classify_failure(exc) == uo.FAILED_TRANSIENT


# --------------------------------------------------- permanent: BadRequest (⊂ NetworkError)
@pytest.mark.parametrize(
    "exc",
    [
        BadRequest("Query is too old and response timeout expired or query id is invalid"),
        BadRequest("Message is not modified"),
        BadRequest("message to edit not found"),
    ],
)
def test_bad_request_is_permanent_not_transient(exc):
    """حاسم: BadRequest فرع من NetworkError لكنه رفض نهائي ⇒ مش عابر."""
    assert isinstance(exc, NetworkError)  # يثبّت الفرضية عن التوريث في PTB 22.8
    assert _classify_failure(exc) == uo.FAILED_PERMANENT


# --------------------------------------------------- permanent: local disk/permission
@pytest.mark.parametrize(
    "exc",
    [
        PermissionError(errno.EACCES, "denied"),
        FileNotFoundError(errno.ENOENT, "missing"),
        IsADirectoryError(errno.EISDIR, "dir"),
        OSError(errno.ENOSPC, "no space"),
    ],
)
def test_local_os_errors_are_permanent_not_transient(exc):
    """OSError محلي غير شبكي ⇒ دائم (مفيش إعادة محاولة صامتة)."""
    assert _classify_failure(exc) == uo.FAILED_PERMANENT


# --------------------------------------------------- preserve existing semantics
def test_transient_sqlite_still_transient():
    exc = sqlite3.OperationalError("database is locked")
    exc.sqlite_errorcode = sqlite3.SQLITE_BUSY
    assert _classify_failure(exc) == uo.FAILED_TRANSIENT


def test_operational_api_error_transient():
    # ApiError تشغيلي (5xx/429/بلا كود) ⇒ عابر (السلوك القائم محفوظ).
    assert _classify_failure(ApiError("boom", 503)) == uo.FAILED_TRANSIENT
    assert _classify_failure(ApiError("net", None)) == uo.FAILED_TRANSIENT


def test_permanent_api_error_permanent():
    assert _classify_failure(ApiError("not found", 404)) == uo.FAILED_PERMANENT


def test_cancelled_is_partial_unknown():
    assert _classify_failure(asyncio.CancelledError()) == uo.PARTIAL_OR_UNKNOWN


def test_unknown_programming_error_is_permanent():
    assert _classify_failure(KeyError("k")) == uo.FAILED_PERMANENT


# --------------------------------------------------- sequential (no concurrency) processing
def test_process_updates_dispatches_sequentially_not_concurrently(tmp_path, monkeypatch):
    """`process_updates` يوزّع التحديثات **واحد-واحد** (تسلسل إجباري، ممنوع التوازي).

    حاسم: لو اتحوّل التوزيع لـ `asyncio.gather`، بيبقى فيه أكتر من handler شغّال في نفس
    الوقت (`max_in_flight > 1`) وترتيب البداية/النهاية يبقى متشابك. الاختبار يثبّت
    `max_in_flight == 1` والترتيب `start1,end1,start2,end2`. ده قيد WP-04 Part 1 الصريح
    (لا معالجة متوازية؛ `OD-04` مسدود).
    """
    async def run(app, _install_bot):
        events: list[tuple[str, int]] = []
        in_flight = {"n": 0, "max": 0}

        async def record(update, context):
            in_flight["n"] += 1
            in_flight["max"] = max(in_flight["max"], in_flight["n"])
            events.append(("start", update.update_id))
            await asyncio.sleep(0.02)  # نافذة تكشف أي تنفيذ متزامن
            events.append(("end", update.update_id))
            in_flight["n"] -= 1
            h.mark_explicitly_ignored(update, context)

        group0 = app.handlers[0]
        idx = next(
            i for i, hh in enumerate(group0)
            if getattr(hh, "callback", None) is h.handle_text
        )
        group0[idx] = TypeHandler(Update, record, strict=False)

        poller = TelegramPoller(app, app.bot_data["db"])
        await poller.process_updates([_text(app, 3101), _text(app, 3102)])
        assert in_flight["max"] == 1, f"تنفيذ متزامن غير مسموح: {events}"
        assert events == [
            ("start", 3101),
            ("end", 3101),
            ("start", 3102),
            ("end", 3102),
        ]

    asyncio.run(_with_started_app(tmp_path, monkeypatch, run))
