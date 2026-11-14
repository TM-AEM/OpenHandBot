"""OHB2-STAGE4-F1-FAIL-CLOSED-OPERATIONAL-ACK-FIX — اختبارات انحدار لعيب F1.

**العيب المؤكَّد (F1):** `show_status`/`show_cost` كانوا بيسجّلوا `explicitly_ignored`
(نتيجة **مؤهّلة** للإقرار) لأي `conv is None`، بما فيه **الفشل التشغيلي** upstream
(5xx/429/مهلة/انقطاع). النتيجة: تحديث عرض فشل تشغيليًّا كان بيتقبل كأنه اتعالج ⇒ الحدّ
والـ offset يتقدّموا فوقه ⇒ مفيش إعادة محاولة بعد التعافي (وسلوك غير متّسق مع
`open`/`copy`/`full` و§4/§7/§30.2).

**الإصلاح (Option B، fail-closed):** مسار مفصّل (`_authorized_conversation_status`)
يفرّق:
- **فشل تشغيلي** (5xx/429/بلا كود) ⇒ `FAILED_TRANSIENT` (**غير مؤهّل**، fail-closed) ⇒
  الحدّ/الـ offset **مايتقدّموش** فوقه (نفس سياسة `open`/`copy`/`full`).
- **رفض نهائي مؤكّد** (مش موجود/متشاهد/غير مصرّح، 404/403) ⇒ `explicitly_ignored` (مؤهّل).
- **نجاح العرض** ⇒ `explicitly_ignored` (مؤهّل) — زي ما كان.
- **فشل تسليم تيليجرام** ⇒ `FAILED_TRANSIENT` (غير مؤهّل) — زي ما كان.
- **فشل تسجيل النتيجة** ⇒ **يرفع** (ممنوع نجاح صامت).

مفيش شبكة: قاعدة SQLite معزولة، عميل وهمي، وحلقة الاستطلاع الحقيقية (`TelegramPoller`)
في اختبارات الـ end-to-end.
"""
from __future__ import annotations

import asyncio
import sqlite3
from types import SimpleNamespace

import pytest
from telegram.error import BadRequest

import bot.handlers as h
from bot import update_outcomes as uo
from bot.errors import ApiError
from bot.polling import TelegramPoller

from tests.test_handlers import _cb_update, _ctx_with
from tests.test_stage2_custom_polling import _callback, _with_started_app
from tests.test_duplicate_update_dispatch import OWNER_ID

CONV = {
    "id": "c1",
    "title": "شات",
    "execution_status": "running",
    "metrics": {"accumulated_cost": 1.5},
}


class _Client:
    """عميل وهمي: شات موجود + تحكّم في فشل التفويض.

    `open_error` ⇒ `get_conversations` بترمي (مسار upstream)؛ `conv=None` ⇒ بترجّع `[]`
    (مسار `NOT_FOUND`).
    """

    OWNER_UUID = "owner-uuid-123"

    def __init__(self, conv=CONV, *, open_error=None):
        self._conv = conv
        self._open_error = open_error

    async def get_conversations(self, ids):
        if self._open_error is not None:
            raise self._open_error
        if not self._conv:
            return []
        return [{**self._conv, "created_by_user_id": self.OWNER_UUID}]

    async def get_current_user(self):
        return {"id": self.OWNER_UUID}


class _FailingEditQuery:
    """كولباك يرمي `BadRequest` عند التعديل ⇒ `_edit_or_send` يرجّع False (فشل تسليم)."""

    def __init__(self, data):
        self.data = data
        self.edits = []
        self.answered = 0
        self.message = SimpleNamespace(chat_id=99)

    async def answer(self):
        self.answered += 1

    async def edit_message_text(self, text, **kw):
        raise BadRequest("message to edit not found")


def _update(update_id, data, *, failing_edit=False):
    if failing_edit:
        return SimpleNamespace(
            update_id=update_id,
            effective_user=SimpleNamespace(id=OWNER_ID),
            effective_chat=SimpleNamespace(id=99, type="private"),
            message=None,
            callback_query=_FailingEditQuery(data),
        )
    update = _cb_update(OWNER_ID, data)
    update.update_id = update_id
    return update


# الفشل التشغيلي (5xx/429/مهلة/انقطاع) ⇒ غير مؤهّل.
_OPERATIONAL = [
    pytest.param(ApiError("internal", 500), id="http500"),
    pytest.param(ApiError("bad gateway", 502), id="http502"),
    pytest.param(ApiError("service unavailable", 503), id="http503"),
    pytest.param(ApiError("too many requests", 429), id="http429"),
    pytest.param(ApiError("انتهى الوقت"), id="timeout"),
    pytest.param(ApiError("تعذّر الاتصال"), id="connection"),
]

# الرفض النهائي المؤكّد (4xx) ⇒ مؤهّل (`explicitly_ignored`).
_CONFIRMED_REJECTION = [
    pytest.param(ApiError("not found", 404), id="http404"),
    pytest.param(ApiError("forbidden", 403), id="http403"),
]


# ============================================================================
# 1) show_status — الفشل التشغيلي ⇒ failed_transient (غير مؤهّل)
# ============================================================================
@pytest.mark.parametrize("exc", _OPERATIONAL)
def test_show_status_operational_failure_is_transient_not_eligible(tmp_path, exc):
    ctx = _ctx_with(tmp_path, _Client(open_error=exc))
    update = _update(3001, "status:c1")
    asyncio.run(h.show_status(update, ctx))
    db = ctx.bot_data["db"]
    # الرسالة اتعرّضت للمستخدم (مفيش رجوع صامت).
    assert update.callback_query.edits, "المستخدم لازم يشوف رسالة الفشل"
    # النتيجة: فشل عابر، **مش** تجاهل/نجاح.
    assert db.update_outcome(3001) == uo.FAILED_TRANSIENT
    assert db.is_update_acknowledgment_eligible(3001) is False
    db.close()


# ============================================================================
# 2) show_cost — الفشل التشغيلي ⇒ failed_transient (غير مؤهّل)
# ============================================================================
@pytest.mark.parametrize("exc", _OPERATIONAL)
def test_show_cost_operational_failure_is_transient_not_eligible(tmp_path, exc):
    ctx = _ctx_with(tmp_path, _Client(open_error=exc))
    update = _update(3101, "cost:c1")
    asyncio.run(h.show_cost(update, ctx))
    db = ctx.bot_data["db"]
    assert update.callback_query.edits, "المستخدم لازم يشوف رسالة الفشل"
    assert db.update_outcome(3101) == uo.FAILED_TRANSIENT
    assert db.is_update_acknowledgment_eligible(3101) is False
    db.close()


# ============================================================================
# 3) الرفض النهائي المؤكّد (404/403 + NOT_FOUND) ⇒ explicitly_ignored (مؤهّل)
# ============================================================================
@pytest.mark.parametrize("exc", _CONFIRMED_REJECTION)
def test_show_status_confirmed_rejection_is_ignored_eligible(tmp_path, exc):
    ctx = _ctx_with(tmp_path, _Client(open_error=exc))
    update = _update(3201, "status:c1")
    asyncio.run(h.show_status(update, ctx))
    db = ctx.bot_data["db"]
    assert db.update_outcome(3201) == uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(3201) is True
    db.close()


@pytest.mark.parametrize("exc", _CONFIRMED_REJECTION)
def test_show_cost_confirmed_rejection_is_ignored_eligible(tmp_path, exc):
    ctx = _ctx_with(tmp_path, _Client(open_error=exc))
    update = _update(3301, "cost:c1")
    asyncio.run(h.show_cost(update, ctx))
    db = ctx.bot_data["db"]
    assert db.update_outcome(3301) == uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(3301) is True
    db.close()


@pytest.mark.parametrize("handler,data", [(h.show_status, "status:c1"), (h.show_cost, "cost:c1")],
                         ids=["status", "cost"])
def test_status_cost_not_found_is_ignored_eligible(tmp_path, handler, data):
    """`NOT_FOUND` (قايمة فاضية) ⇒ رفض نهائي مؤكّد ⇒ `explicitly_ignored` مؤهّل."""
    ctx = _ctx_with(tmp_path, _Client(conv=None))
    update = _update(3401, data)
    asyncio.run(handler(update, ctx))
    db = ctx.bot_data["db"]
    assert db.update_outcome(3401) == uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(3401) is True
    db.close()


# ============================================================================
# 4) نجاح العرض ⇒ explicitly_ignored (مؤهّل) — السلوك القائم محفوظ
# ============================================================================
@pytest.mark.parametrize("handler,data", [(h.show_status, "status:c1"), (h.show_cost, "cost:c1")],
                         ids=["status", "cost"])
def test_status_cost_success_is_ignored_eligible(tmp_path, handler, data):
    ctx = _ctx_with(tmp_path, _Client())
    update = _update(3501, data)
    asyncio.run(handler(update, ctx))
    db = ctx.bot_data["db"]
    assert db.update_outcome(3501) == uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(3501) is True
    db.close()


# ============================================================================
# 5) فشل تسليم تيليجرام ⇒ failed_transient (غير مؤهّل) — السلوك القائم محفوظ
# ============================================================================
@pytest.mark.parametrize("handler,data", [(h.show_status, "status:c1"), (h.show_cost, "cost:c1")],
                         ids=["status", "cost"])
def test_status_cost_delivery_failure_is_transient_not_eligible(tmp_path, handler, data):
    ctx = _ctx_with(tmp_path, _Client())
    update = _update(3601, data, failing_edit=True)
    asyncio.run(handler(update, ctx))
    db = ctx.bot_data["db"]
    assert db.update_outcome(3601) == uo.FAILED_TRANSIENT
    assert db.is_update_acknowledgment_eligible(3601) is False
    db.close()


# ============================================================================
# 6) فشل تسجيل النتيجة ⇒ يرفع (ممنوع نجاح/تجاهل صامت)
# ============================================================================
@pytest.mark.parametrize("handler,data", [(h.show_status, "status:c1"), (h.show_cost, "cost:c1")],
                         ids=["status", "cost"])
def test_status_cost_outcome_persistence_failure_propagates(tmp_path, monkeypatch, handler, data):
    """لو تعذّر تسجيل `failed_transient` (قاعدة معطوبة) ⇒ الاستثناء **ينتشر**،

    ومفيش رجوع «نجاح صامت». المستخدم لسه شاف رسالة الفشل (اتعرّضت **قبل** التسجيل).
    """
    ctx = _ctx_with(tmp_path, _Client(open_error=ApiError("internal", 500)))
    db = ctx.bot_data["db"]

    def boom(*_a, **_k):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(db, "mark_update_outcome", boom)
    update = _update(3701, data)
    with pytest.raises(sqlite3.OperationalError):
        asyncio.run(handler(update, ctx))
    # مفيش نتيجة مؤهّلة اتسجّلت.
    assert db.is_update_acknowledgment_eligible(3701) is False
    db.close()


# ============================================================================
# 7) end-to-end عبر حلقة الاستطلاع الحقيقية (TelegramPoller) — الحدّ والـ offset
# ============================================================================
@pytest.mark.parametrize("data,uid", [("status:c1", 4001), ("cost:c1", 4101)],
                         ids=["status", "cost"])
def test_e2e_operational_failure_blocks_boundary_and_offset(tmp_path, monkeypatch, data, uid):
    """فشل تشغيلي ⇒ `failed_transient` مُثبَّت ⇒ الحدّ None والـ offset مايتقدّمش،

    والتحديث اللي بعده **يفضل غير مُقَرّ** (حجب head-of-line مقصود — fail-closed).

    بنحاكي الواقع: لأن الـ offset مااتقدّمش (`None`)، الحلقة بتعيد سحب التحديث الفاشل مع
    اللي بعده في **نفس الدفعة** ⇒ البادئة بتتوقف عند الأول (غير مؤهّل) ⇒ مفيش إقرار.
    """
    async def run(app, install_bot):
        # أول نداء `get_conversations` بيفشل (التحديث الحاجب)، اللي بعده بينجح.
        class _FirstCallFailsClient(_Client):
            def __init__(self):
                super().__init__()
                self._calls = 0

            async def get_conversations(self, ids):
                self._calls += 1
                if self._calls == 1:
                    raise ApiError("internal", 500)
                return await super().get_conversations(ids)

        app.bot_data["client"] = _FirstCallFailsClient()
        db = app.bot_data["db"]
        poller = TelegramPoller(app, db)

        boundary = await poller.process_updates(
            [_callback(app, uid, data), _callback(app, uid + 1, data)]
        )
        assert boundary is None  # أول تحديث غير مؤهّل ⇒ مفيش إقرار
        assert poller._next_offset is None  # الـ offset مااتقدّمش
        assert db.update_outcome(uid) == uo.FAILED_TRANSIENT
        assert db.is_update_acknowledgment_eligible(uid) is False
        # التحديث اللي بعده اتعالج (مؤهّل) بس الحدّ اتوقف عند الأول ⇒ مفيش إقرار (مفيش تجاوز).
        assert db.update_outcome(uid + 1) == uo.EXPLICITLY_IGNORED
        assert db.is_update_acknowledgment_eligible(uid + 1) is True

    asyncio.run(_with_started_app(tmp_path, monkeypatch, run))


def test_e2e_confirmed_rejection_advances_boundary(tmp_path, monkeypatch):
    """الرفض النهائي المؤكّد (404) ⇒ `explicitly_ignored` مؤهّل ⇒ الحدّ والـ offset يتقدّموا."""
    async def run(app, install_bot):
        app.bot_data["client"] = _Client(open_error=ApiError("not found", 404))
        db = app.bot_data["db"]
        poller = TelegramPoller(app, db)

        boundary = await poller.process_updates([_callback(app, 4201, "status:c1")])
        assert boundary == 4201
        assert poller._next_offset == 4202
        assert db.update_outcome(4201) == uo.EXPLICITLY_IGNORED
        assert db.is_update_acknowledgment_eligible(4201) is True

    asyncio.run(_with_started_app(tmp_path, monkeypatch, run))


def test_e2e_recovery_after_operational_failure(tmp_path, monkeypatch):
    """التعافي عبر إعادة التسليم (الآلية القائمة): فشل عابر ⇒ غير معالَج ⇒ إعادة التسليم

    تنفّذ تاني؛ لو نجحت ⇒ `explicitly_ignored` ⇒ الحدّ يتقدّم. مفيش أثر جانبي مكرّر
    (مسار عرض قراءة فقط).
    """
    async def run(app, install_bot):
        failing = _Client(open_error=ApiError("internal", 500))
        app.bot_data["client"] = failing
        db = app.bot_data["db"]
        poller = TelegramPoller(app, db)

        assert await poller.process_updates([_callback(app, 4301, "status:c1")]) is None
        assert poller._next_offset is None
        assert db.update_is_processed(4301) is False  # الفشل مايسجّلش «معالَج» ⇒ إعادة التسليم تنفّذ

        # «التعافي»: العميل بقى سليم ⇒ إعادة تسليم نفس التحديث تنفّذ وتنجح.
        app.bot_data["client"] = _Client()
        boundary = await poller.process_updates([_callback(app, 4301, "status:c1")])
        assert boundary == 4301
        assert poller._next_offset == 4302
        assert db.update_outcome(4301) == uo.EXPLICITLY_IGNORED

    asyncio.run(_with_started_app(tmp_path, monkeypatch, run))


# ============================================================================
# 8) OHB2-STAGE4-F1-LOW-COVERAGE-CLOSURE — فشل تسليم رسالة الخطأ نفسها
# ============================================================================
# لما الفشل التشغيلي يتحوّل لرسالة خطأ و**تسليم الرسالة** نفسه يفشل (BadRequest)،
# `_safe_edit` بيعيد رفع الاستثناء (مش "not modified") ⇒ التنفيذ يتوقف **قبل** أي تسجيل
# نتيجة. الثابت المطلوب: التحديث **مستحيل يبقى مؤهّل للإقرار** (مفيش `explicitly_ignored`
# ولا تقدّم حدّ/offset). النتيجة المُخزّنة نفسها مش الثابت: في نداء الـ handler مباشرة
# بتبقى `None`؛ عبر حلقة الاستطلاع الحقيقية معالج الأخطاء بيسجّل `failed_permanent`.
# الاتنين **غير مؤهّلين** — وبنأكّد على الأهم (عدم الأهلية + عدم `explicitly_ignored`).
@pytest.mark.parametrize("handler,data", [(h.show_status, "status:c1"), (h.show_cost, "cost:c1")],
                         ids=["status", "cost"])
def test_status_cost_operational_failure_with_error_delivery_failure(tmp_path, handler, data):
    """فشل تشغيلي + فشل تسليم رسالة الخطأ ⇒ **مفيش** `explicitly_ignored`، وغير مؤهّل."""
    ctx = _ctx_with(tmp_path, _Client(open_error=ApiError("internal", 500)))
    update = _update(3801, data, failing_edit=True)
    # `_safe_edit` بيعيد رفع `BadRequest` (مفيش "not modified") ⇒ الاستثناء ينتشر.
    with pytest.raises(BadRequest):
        asyncio.run(handler(update, ctx))
    db = ctx.bot_data["db"]
    # الثابت الحاسم: مفيش تجاهل صريح، والتحديث مش مؤهّل (مفيش إقرار كاذب).
    assert db.update_outcome(3801) != uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(3801) is False
    db.close()


def test_e2e_operational_failure_with_error_delivery_failure_blocks_boundary(tmp_path, monkeypatch):
    """E2E: فشل تشغيلي + فشل تسليم رسالة الخطأ ⇒ الحدّ و`_next_offset` **مايتقدّموش**."""
    async def run(app, install_bot):
        app.bot_data["client"] = _Client(open_error=ApiError("internal", 500))

        async def _boom_edit(self, *a, **k):
            raise BadRequest("message to edit not found")

        monkeypatch.setattr("telegram.Bot.edit_message_text", _boom_edit)
        db = app.bot_data["db"]
        poller = TelegramPoller(app, db)

        boundary = await poller.process_updates([_callback(app, 5101, "status:c1")])
        assert boundary is None  # مفيش بادئة مؤهّلة
        assert poller._next_offset is None  # الـ offset مااتقدّمش
        assert db.update_outcome(5101) != uo.EXPLICITLY_IGNORED
        assert db.is_update_acknowledgment_eligible(5101) is False
        assert db.update_is_processed(5101) is False  # إعادة التسليم لسه تنفّذ

    asyncio.run(_with_started_app(tmp_path, monkeypatch, run))


# ============================================================================
# 9) OHB2-STAGE4-F1-LOW-COVERAGE-CLOSURE — فشل `/users/me` (بعد نجاح جلب الشات)
# ============================================================================
class _IdentityFailClient(_Client):
    """`get_conversations` بينجح لكن `/users/me` بيفشل (`ApiError`) ⇒ upstream في نقطة الهوية.

    ده مسار مختلف عن `open_error` (فشل جلب الشات): هنا التفويض يفشل **متأخّرًا** في
    `owner_id_detailed` ⇒ `UPSTREAM_ERROR` + الاستثناء الأصلي (OHB2-SW-04).
    """

    def __init__(self, error):
        super().__init__()
        self._identity_error = error

    async def get_current_user(self):
        raise self._identity_error


def test_authorize_detailed_identity_upstream_preserves_exception():
    """`authorize_conversation_detailed` بتحفظ الاستثناء الأصلي لفشل الهوية (لتصنيفه)."""
    from bot.files import FileStatus, IdentityCache, authorize_conversation_detailed

    client = _IdentityFailClient(ApiError("server", 500))
    conv, status, _msg, exc = asyncio.run(
        authorize_conversation_detailed(client, IdentityCache(client), "c1", None)
    )
    assert conv is None
    assert status is FileStatus.UPSTREAM_ERROR
    assert isinstance(exc, ApiError)
    assert exc.status_code == 500


@pytest.mark.parametrize("exc", _OPERATIONAL)
@pytest.mark.parametrize("handler,data", [(h.show_status, "status:c1"), (h.show_cost, "cost:c1")],
                         ids=["status", "cost"])
def test_status_cost_identity_operational_failure_is_transient_not_eligible(tmp_path, handler, data, exc):
    """فشل `/users/me` التشغيلي (5xx/429/مهلة/انقطاع) ⇒ `failed_transient`، مش تجاهل."""
    ctx = _ctx_with(tmp_path, _IdentityFailClient(exc))
    update = _update(3901, data)
    asyncio.run(handler(update, ctx))
    db = ctx.bot_data["db"]
    assert db.update_outcome(3901) == uo.FAILED_TRANSIENT
    assert db.update_outcome(3901) != uo.EXPLICITLY_IGNORED
    assert db.is_update_acknowledgment_eligible(3901) is False
    db.close()


def test_e2e_identity_operational_failure_blocks_boundary(tmp_path, monkeypatch):
    """E2E: فشل `/users/me` التشغيلي ⇒ الحدّ و`_next_offset` **مايتقدّموش**."""
    async def run(app, install_bot):
        app.bot_data["client"] = _IdentityFailClient(ApiError("server", 500))
        db = app.bot_data["db"]
        poller = TelegramPoller(app, db)

        boundary = await poller.process_updates([_callback(app, 5201, "status:c1")])
        assert boundary is None
        assert poller._next_offset is None
        assert db.update_outcome(5201) == uo.FAILED_TRANSIENT
        assert db.is_update_acknowledgment_eligible(5201) is False

    asyncio.run(_with_started_app(tmp_path, monkeypatch, run))
