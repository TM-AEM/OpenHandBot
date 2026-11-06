"""OHB2-MINIAPP: اختبارات الحذف **البعيد** لشات OpenHands (تنسيق `bot.deletion`).

بتغطّي: نجاح مؤكّد، 404 (idempotent)، فشل مؤكّد (401/403/422)، حدود المعدّل (429)،
أخطاء الخادم (5xx)، الانقطاع/الرد المشوّه (نتيجة مجهولة ⇒ تسوية)، منع النجاح الكاذب،
منع الإحياء بعد الحذف، والحذف المتكرّر/المتزامن.

كلها بعميل وهمي وقواعد معزولة — مفيش أي اتصال حقيقي بـ OpenHands/تيليجرام.
"""
from __future__ import annotations

import asyncio
import os

from bot import deletion, outbox
from bot.db import Database
from bot.errors import ApiError
from bot.files import FileStatus

CID = "c1"


def _db(tmp_path) -> Database:
    return Database(os.path.join(str(tmp_path), "rd.sqlite3"))


class FakeClient:
    """عميل وهمي متحكَّم فيه لسلوك الحذف البعيد وفحص الوجود.

    `delete_behaviour`:
      - "ok": 200 {"success": true}
      - "404": ApiError(status=404)  (مبهم: ممكن غياب أو فشل خدمة داخلي)
      - ("status", N): ApiError(status=N)
      - "unknown": ApiError بلا status (محاكاة انقطاع/رد مشوّه)
    `exists`/`exists_error`: نتيجة conversation_exists الثابتة، أو خطأ.
    `exists_seq`: سلسلة نتائج متتالية للتحقق من الغياب (القيمة الأخيرة تتكرّر)، و"error"
      يعني ApiError. تُستخدم لاختبار «الغياب لازم يثبت من أكتر من قراءة».
    """

    def __init__(self, delete_behaviour="ok", exists=False, exists_error=False, exists_seq=None):
        self.delete_behaviour = delete_behaviour
        self.exists = exists
        self.exists_error = exists_error
        self.exists_seq = list(exists_seq) if exists_seq is not None else None
        self.delete_calls = 0
        self.exists_calls = 0

    async def delete_conversation(self, conversation_id):
        self.delete_calls += 1
        b = self.delete_behaviour
        if b == "ok":
            return True
        if b == "404":
            raise ApiError("الشات مش موجود.", 404)
        if b == "unknown":
            raise ApiError("تعذّر الاتصال بـ OpenHands (ReadTimeout).")
        if isinstance(b, tuple) and b[0] == "status":
            raise ApiError("خطأ من OpenHands.", b[1])
        raise AssertionError(f"behaviour غير معروف: {b!r}")

    async def conversation_exists(self, conversation_id):
        self.exists_calls += 1
        if self.exists_seq is not None:
            idx = min(self.exists_calls - 1, len(self.exists_seq) - 1)
            val = self.exists_seq[idx]
            if val == "error":
                raise ApiError("تعذّر الاتصال بـ OpenHands.", None)
            return val
        if self.exists_error:
            raise ApiError("تعذّر الاتصال بـ OpenHands.", None)
        return self.exists


def _run(client, db):
    return asyncio.run(deletion.delete_conversation_remote(client, db, CID))


# --------------------------------------------------------------- success paths
def test_confirmed_success_marks_confirmed_and_deletes_locally(tmp_path):
    db = _db(tmp_path)
    db.add_watched(CID, "شات", chat_id=1)
    res = _run(FakeClient("ok"), db)
    assert res.status == deletion.STATUS_DELETED
    assert db.get_watched(CID) is None
    assert db.is_deleted(CID) is True
    assert db.remote_deletion_state(CID) == db.REMOTE_CONFIRMED


def test_404_with_conversation_present_is_failure(tmp_path):
    """404 مبهم + الشات لسه موجود فعلًا ⇒ فشل صريح (مفيش حذف محلي، مفيش نجاح كاذب)."""
    db = _db(tmp_path)
    db.add_watched(CID, "شات", chat_id=1)
    client = FakeClient("404", exists=True)
    res = _run(client, db)
    assert res.status == deletion.STATUS_FAILED
    assert db.get_watched(CID) is not None  # ما اتحذفش محليًا
    assert db.is_deleted(CID) is False  # الحالة المحلية رجعت
    assert db.remote_deletion_state(CID) is None
    assert client.exists_calls >= 1


def test_404_with_confirmed_absence_is_success(tmp_path):
    """404 + غياب مؤكّد (قراءات متتالية فاضية) ⇒ نجاح idempotent مؤكّد."""
    db = _db(tmp_path)
    db.add_watched(CID, "شات", chat_id=1)
    client = FakeClient("404", exists=False)
    res = _run(client, db)
    assert res.status == deletion.STATUS_DELETED
    assert db.get_watched(CID) is None
    assert db.remote_deletion_state(CID) == db.REMOTE_CONFIRMED
    assert client.exists_calls == deletion._ABSENCE_CONFIRMATIONS  # غياب مؤكّد بأكتر من قراءة


def test_404_with_inconclusive_check_is_pending(tmp_path):
    """404 + تعذّر التحقق (فشل القراءة) ⇒ 'pending' (مش نجاح ومش فشل)، والحالة 'uncertain'."""
    db = _db(tmp_path)
    db.add_watched(CID, "شات", chat_id=1)
    res = _run(FakeClient("404", exists_error=True), db)
    assert res.status == deletion.STATUS_PENDING
    assert db.is_deleted(CID) is True  # لسه متشاهد محليًا (مفيش تأكيد ولا رجوع)
    assert db.remote_deletion_state(CID) == db.REMOTE_UNCERTAIN


def test_404_with_stale_absence_needs_confirmation(tmp_path):
    """غياب عارض/قديم (أول قراءة غياب، تاني قراءة موجود) ⇒ ممنوع التأكيد ⇒ فشل + رجوع محلي."""
    db = _db(tmp_path)
    db.add_watched(CID, "شات", chat_id=1)
    client = FakeClient("404", exists_seq=[False, True])
    res = _run(client, db)
    assert res.status == deletion.STATUS_FAILED
    assert db.is_deleted(CID) is False  # رجع محليًا (الغياب ما كانش مؤكّد)
    assert client.exists_calls == 2  # القراءة التانية كشفت إنه لسه موجود


def test_404_absence_retry_exhausted_is_pending(tmp_path):
    """غياب متكرّر لكن قراءة لاحقة فشلت ⇒ تعذّر التأكيد ⇒ 'pending' (مفيش تخمين)."""
    db = _db(tmp_path)
    db.add_watched(CID, "شات", chat_id=1)
    client = FakeClient("404", exists_seq=[False, "error"])
    res = _run(client, db)
    assert res.status == deletion.STATUS_PENDING
    assert db.remote_deletion_state(CID) == db.REMOTE_UNCERTAIN
    assert client.exists_calls == 2


def test_404_pending_survives_restart_and_reconciles(tmp_path):
    """حذف معلّق منشؤه 404 ينجو من restart، والتسوية تحسمه (غياب ⇒ تأكيد)."""
    path = os.path.join(str(tmp_path), "restart404.sqlite3")
    db = Database(path)
    db.add_watched(CID, "شات", chat_id=1)
    # محاولة أولى: 404 + تعذّر التحقق ⇒ 'uncertain' دائم.
    res = _run(FakeClient("404", exists_error=True), db)
    assert res.status == deletion.STATUS_PENDING
    db.close()
    # إعادة فتح (restart): الحالة المعلّقة لسه موجودة.
    db2 = Database(path)
    assert db2.remote_deletion_state(CID) == db2.REMOTE_UNCERTAIN
    assert CID in db2.list_pending_remote_deletions()
    # تسوية بعد restart: الشات غايب فعلاً ⇒ تأكيد الحذف.
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=False), db2))
    assert db2.remote_deletion_state(CID) == db2.REMOTE_CONFIRMED


# --------------------------------------------------------------- definite failures
def test_401_is_definite_failure_no_local_delete(tmp_path):
    db = _db(tmp_path)
    db.add_watched(CID, "شات", chat_id=1)
    res = _run(FakeClient(("status", 401)), db)
    assert res.status == deletion.STATUS_FAILED
    assert db.get_watched(CID) is not None  # ما اتحذفش محليًا
    # فشل مؤكّد ⇒ رجّعنا الحالة المحلية (مفيش شاهد، مفيش إخفاء كاذب).
    assert db.is_deleted(CID) is False
    assert db.remote_deletion_state(CID) is None


def test_403_and_422_are_definite_failures(tmp_path):
    for code in (403, 422):
        sub = tmp_path / f"c{code}"
        sub.mkdir()
        db = _db(sub)
        db.add_watched(CID, "شات", chat_id=1)
        res = _run(FakeClient(("status", code)), db)
        assert res.status == deletion.STATUS_FAILED, code
        assert db.is_deleted(CID) is False  # الحالة المحلية رجعت


# --------------------------------------------------------------- uncertain outcomes
def test_timeout_with_absent_reconciles_to_success(tmp_path):
    """انقطاع (نتيجة مجهولة) + الشات غايب فعلًا ⇒ نثبّت الحذف (مش نجاح أعمى)."""
    db = _db(tmp_path)
    db.add_watched(CID, "شات", chat_id=1)
    res = _run(FakeClient("unknown", exists=False), db)
    assert res.status == deletion.STATUS_DELETED
    assert db.remote_deletion_state(CID) == db.REMOTE_CONFIRMED


def test_timeout_with_present_reports_failure_not_success(tmp_path):
    """انقطاع + الشات لسه موجود ⇒ فشل صريح (مفيش نجاح كاذب) والحالة المحلية رجعت."""
    db = _db(tmp_path)
    db.add_watched(CID, "شات", chat_id=1)
    res = _run(FakeClient("unknown", exists=True), db)
    assert res.status == deletion.STATUS_FAILED
    assert db.is_deleted(CID) is False
    assert db.remote_deletion_state(CID) is None


def test_timeout_with_unverifiable_reports_pending(tmp_path):
    """انقطاع + تعذّر التحقق ⇒ 'pending' (مش نجاح ومش فشل مؤكّد)، الشات متشاهد."""
    db = _db(tmp_path)
    db.add_watched(CID, "شات", chat_id=1)
    res = _run(FakeClient("unknown", exists_error=True), db)
    assert res.status == deletion.STATUS_PENDING
    assert db.is_deleted(CID) is True
    assert db.remote_deletion_state(CID) == db.REMOTE_UNCERTAIN


def test_429_and_500_reconcile(tmp_path):
    """429/5xx نتيجة مجهولة ⇒ تسوية (هنا: موجود ⇒ فشل + رجوع محلي)."""
    for code in (429, 500, 503):
        sub = tmp_path / f"s{code}"
        sub.mkdir()
        db = _db(sub)
        db.add_watched(CID, "شات", chat_id=1)
        res = _run(FakeClient(("status", code), exists=True), db)
        assert res.status == deletion.STATUS_FAILED, code
        assert db.is_deleted(CID) is False


# --------------------------------------------------------------- idempotency / races
def test_repeated_delete_is_idempotent(tmp_path):
    db = _db(tmp_path)
    db.add_watched(CID, "شات", chat_id=1)
    client = FakeClient("ok")
    r1 = _run(client, db)
    r2 = _run(client, db)
    assert r1.status == r2.status == deletion.STATUS_DELETED
    assert client.delete_calls == 1  # النداء البعيد مرة واحدة بس


def test_no_resurrection_after_success(tmp_path):
    db = _db(tmp_path)
    db.add_watched(CID, "شات", chat_id=1)
    _run(FakeClient("ok"), db)
    # أي مسار إنشاء/إحياء غير صريح مرفوض بسبب الشاهد.
    db.add_watched(CID, "شات", chat_id=1, new_lifecycle=False)
    assert db.get_watched(CID) is None


def test_begin_remote_deletion_survives_restart(tmp_path):
    """الوسم 'deleting' دائم: ينجو من إعادة الفتح (restart) قبل أي تسوية."""
    path = os.path.join(str(tmp_path), "restart.sqlite3")
    db = Database(path)
    db.begin_remote_deletion(CID, outbox.now_iso())
    db.close()
    db2 = Database(path)
    assert db2.remote_deletion_state(CID) == db2.REMOTE_DELETING
    assert db2.list_pending_remote_deletions() == [CID]


# --------------------------------------------------------------- reconciliation
def test_reconcile_absent_finalizes(tmp_path):
    db = _db(tmp_path)
    db.begin_remote_deletion(CID, outbox.now_iso())
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=False), db))
    assert db.remote_deletion_state(CID) == db.REMOTE_CONFIRMED


def test_reconcile_present_restores_local(tmp_path):
    db = _db(tmp_path)
    db.add_watched(CID, "شات", chat_id=1)
    db.begin_remote_deletion(CID, outbox.now_iso())
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists=True), db))
    assert db.is_deleted(CID) is False  # رجع محليًا (الحذف البعيد ما حصلش)
    assert db.remote_deletion_state(CID) is None  # اتصفّرت الحالة (مفيش 'deleting' عالق)


def test_reconcile_present_is_idempotent(tmp_path):
    """التسوية المتكرّرة (موجود ⇒ رجوع) ما تنتجش حالة متناقضة، ومسارات الإحياء تشتغل."""
    db = _db(tmp_path)
    db.add_watched(CID, "شات", chat_id=1)
    db.begin_remote_deletion(CID, outbox.now_iso())
    client = FakeClient(exists=True)
    asyncio.run(deletion.reconcile_pending_deletions(client, db))
    asyncio.run(deletion.reconcile_pending_deletions(client, db))
    assert db.is_deleted(CID) is False
    assert db.remote_deletion_state(CID) is None
    assert db.list_pending_remote_deletions() == []
    # بعد التسوية، إضافة متابعة عادية (دورة حياة جديدة) لازم تنجح (مفيش شاهد عالق).
    db.add_watched(CID, "شات", chat_id=1)
    assert db.get_watched(CID) is not None


def test_reconcile_unverifiable_keeps_pending(tmp_path):
    db = _db(tmp_path)
    db.begin_remote_deletion(CID, outbox.now_iso())
    asyncio.run(deletion.reconcile_pending_deletions(FakeClient(exists_error=True), db))
    assert db.remote_deletion_state(CID) == db.REMOTE_DELETING
    assert CID in db.list_pending_remote_deletions()


# --------------------------------------------------------------- no false success
def test_no_local_delete_on_definite_failure(tmp_path):
    """الفشل المؤكّد مابيحذفش محليًا ومابيقولش نجاح، ويرجّع الحالة المحلية."""
    db = _db(tmp_path)
    db.add_watched(CID, "شات", chat_id=1)
    res = _run(FakeClient(("status", 403)), db)
    assert res.status != deletion.STATUS_DELETED
    assert db.get_watched(CID) is not None
    assert db.is_deleted(CID) is False


def test_service_error_mapping(tmp_path):
    """MiniAppService يحوّل فشل/مجهول لـ CodedApiError منظّم (مفيش نجاح كاذب)."""
    from bot.config import Config
    from bot.web.services import MiniAppService, CodedApiError

    cfg = Config(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        openhands_api_key="k",
        allowed_telegram_ids=frozenset({1}),
        owner_id=1,
        db_path=str(tmp_path / "svc.sqlite3"),
    )
    db = _db(tmp_path)

    class _OwnerClient(FakeClient):
        async def get_conversations(self, ids):
            return [{"id": CID, "title": "شات", "created_by_user_id": "owner-uuid"}]

        async def get_current_user(self):
            return {"id": "owner-uuid"}

    svc = MiniAppService(cfg, db, _OwnerClient(("status", 403)))
    try:
        asyncio.run(svc.delete_conversation(CID))
        raise AssertionError("كان لازم يرفع CodedApiError")
    except CodedApiError as exc:
        assert exc.status_code == 403
        assert "OpenHands" in str(exc)


def test_file_status_enum_untouched():
    """حرس بسيط: رمز الحالة لسه موجود (ما اتغيّرش سلوك مسارات الملفات)."""
    assert FileStatus.NOT_FOUND.value == "not_found"
