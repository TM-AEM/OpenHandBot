"""OHB2-09-A2-01: تفويض تصدير الشات (export) قبل أي تنزيل.

المشكلة اللي بنغطّيها: معالج التصدير كان بيعتمد على بوابة المالك (callback owner gate)
بس، وما كانش بيتحقّق من **ملكية الشات** زي `FileService`. الاختبارات دي بتثبت:

- المالك الصح يصدّر.
- مالك تاني / مالك فاضي (null) / هوية مش معروفة / شات مش موجود / معرّف غير صالح /
  مستخدم تليجرام غير مسموح ⇒ **مفيش تنزيل** (export_conversation ما بيتناداش).
- التفويض بيحصل **قبل** التنزيل (ترتيب).
- مفيش fallback غير محدود (الفشل بيوقف، مش بيكمّل).

بتستخدم العميل الوهمي + هارنس الـ handlers الحقيقي.
"""
from __future__ import annotations

import asyncio

import bot.handlers as h
from bot.errors import ApiError, ResponseTooLargeError
from tests.test_handlers import _cb_update, _ctx_with

OWNER_UUID = "owner-uuid-123"


class ExportClient:
    """عميل تصدير وهمي: بيتحكّم في مالك الشات وهوية `/users/me` وبيعدّ نداءات التنزيل."""

    def __init__(self, *, conv_owner=OWNER_UUID, identity=OWNER_UUID, convs_present=True,
                 export_error=None):
        self._conv_owner = conv_owner
        self._identity = identity
        self._convs_present = convs_present
        self._export_error = export_error
        self.export_calls = 0

    async def get_conversations(self, ids):
        if not self._convs_present:
            return []
        conv = {"id": "c1", "title": "شات"}
        if self._conv_owner is not None:
            conv["created_by_user_id"] = self._conv_owner
        return [conv]

    async def get_current_user(self):
        return {"id": self._identity} if self._identity else {}

    async def export_conversation(self, conversation_id):
        self.export_calls += 1
        if self._export_error is not None:
            raise self._export_error
        return b"PK\x03\x04zip"


def _run(tmp_path, client, data="export:c1", user=1):
    ctx = _ctx_with(tmp_path, client)
    update = _cb_update(user, data)
    asyncio.run(h.export_conversation(update, ctx))
    return update, ctx


def test_export_owner_can_export(tmp_path):
    client = ExportClient()
    update, ctx = _run(tmp_path, client)
    assert len(ctx.bot.documents) == 1
    assert client.export_calls == 1


def test_export_other_owner_cannot_export(tmp_path):
    client = ExportClient(conv_owner="someone-else")
    update, ctx = _run(tmp_path, client)
    assert ctx.bot.documents == []
    assert client.export_calls == 0  # مفيش تنزيل
    assert update.callback_query.edits and "مش مسموح" in update.callback_query.edits[-1]


def test_export_null_owner_cannot_export(tmp_path):
    client = ExportClient(conv_owner=None)  # created_by_user_id ناقص ⇒ فشل مغلق
    update, ctx = _run(tmp_path, client)
    assert ctx.bot.documents == []
    assert client.export_calls == 0


def test_export_unknown_identity_cannot_export(tmp_path):
    client = ExportClient(identity=None)  # /users/me مارجّعش id ⇒ فشل مغلق
    update, ctx = _run(tmp_path, client)
    assert ctx.bot.documents == []
    assert client.export_calls == 0


def test_export_missing_conversation_cannot_export(tmp_path):
    client = ExportClient(convs_present=False)
    update, ctx = _run(tmp_path, client)
    assert ctx.bot.documents == []
    assert client.export_calls == 0


def test_export_invalid_conversation_id_cannot_export(tmp_path):
    client = ExportClient()
    update, ctx = _run(tmp_path, client, data="export:bad id!")
    assert ctx.bot.documents == []
    assert client.export_calls == 0


def test_export_non_owner_user_cannot_export(tmp_path):
    """مستخدم تليجرام غير مسموح ⇒ بوابة المالك توقف قبل أي تفويض/تنزيل."""
    client = ExportClient()
    update, ctx = _run(tmp_path, client, user=999)
    assert ctx.bot.documents == []
    assert client.export_calls == 0
    assert update.callback_query.edits == []


def test_export_authorization_precedes_download(tmp_path):
    """التفويض لازم يسبق التنزيل: على الفشل مفيش نداء تنزيل خالص."""
    client = ExportClient(conv_owner="someone-else")
    _run(tmp_path, client)
    assert client.export_calls == 0


def test_export_upstream_error_is_safe_no_document(tmp_path):
    """فشل التنزيل (بعد تفويض ناجح) ⇒ مفيش مستند ورسالة آمنة."""
    client = ExportClient(export_error=ApiError("خدمة مش متاحة", 503))
    update, ctx = _run(tmp_path, client)
    assert ctx.bot.documents == []
    assert client.export_calls == 1
    assert update.callback_query.edits


def test_export_bounded_too_large_is_safe_no_document(tmp_path):
    """حد التصدير المحدود (OHB2-09-03) لسه مطبّق: عدّى الحد ⇒ مفيش مستند."""
    client = ExportClient(export_error=ResponseTooLargeError())
    update, ctx = _run(tmp_path, client)
    assert ctx.bot.documents == []
    assert update.callback_query.edits
